"""Monta o relatório de um ou de todos os masters a partir dos arquivos de entrada.

Pensado para o servidor: um comando, sem interação, que escreve os PDFs numa pasta por
trimestre e um `_manifest.json` com o que saiu e os avisos (unidade sem dados, município da
config que não existe na base). A revisão humana acontece antes do ENVIO ao master.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import pandas as pd

from motor_expansao.masters import analise as A
from motor_expansao.masters import area as AR
from motor_expansao.masters import dados as D
from motor_expansao.masters import funcionamento as F
from motor_expansao.masters import mapa as MP
from motor_expansao.masters.relatorio_pdf import DadosRelatorio, cartoes_da_analise, gerar_pdf
from motor_expansao.masters.territorios import Master, MetaAberturas, municipios_sem_match


@dataclass(frozen=True)
class Entradas:
    planilha: Path
    territorios: Path
    mercado: Path
    concorrentes: Path
    dim_unidade: Path
    fato_unidade_mes: Path
    #: Estudo de área: unidades Ultra do motor, setores do Censo (GEO) e o staging dos insumos
    #: da renda e do bairro do CNEFE. Sem `censo_geo_dir`, as páginas de área não saem.
    ultra: Path | None = None
    censo_geo_dir: Path | None = None
    staging_dir: Path | None = None
    #: Pasta com a capa e o fundo do Relatório Municipal (`relatorio_capa_bg.png` etc.).
    assets_dir: Path | None = None


@dataclass
class Base:
    """Tudo o que é lido uma vez e servido a todos os masters."""

    inauguradas: pd.DataFrame
    pipeline: pd.DataFrame
    mercado: pd.DataFrame
    concorrentes: pd.DataFrame
    dim: pd.DataFrame
    fato: pd.DataFrame
    ultra: pd.DataFrame | None = None
    censo_geo_dir: Path | None = None
    staging_dir: Path | None = None
    assets_dir: Path | None = None
    referencia_ocupacao: dict | None = None

    @property
    def data_ref(self) -> pd.Timestamp:
        ult = self.fato.loc[self.fato["mes_completo"], "competencia"].max()
        return pd.Period(ult, freq="M").to_timestamp(how="end").normalize()

    @property
    def snapshot_mercado(self) -> str:
        datas = pd.to_datetime(
            self.mercado["data_snapshot_mercado"].dropna().unique(), errors="coerce"
        )
        return max(datas).strftime("%d/%m/%Y") if len(datas) else "data desconhecida"


def carregar_base(
    e: Entradas,
    masters: list[Master],
    planilha: tuple[pd.DataFrame, pd.DataFrame] | None = None,
) -> Base:
    """Lê as entradas uma vez. `planilha` = (inauguradas, pipeline) já no formato da planilha:
    o piloto passa as tabelas da ingestão (`ingestao.planilha_do_relatorio`), porque a planilha
    crua não chega ao servidor; sem ela, lê `e.planilha`."""
    inaug, pipe = planilha if planilha is not None else D.ler_planilha_masters(e.planilha)
    ufs: set[str] = set()
    for m in masters:
        ufs |= m.ufs_envolvidas
    dim, fato = D.ler_unidades(e.dim_unidade, e.fato_unidade_mes)
    return Base(
        inaug,
        pipe,
        D.ler_mercado(e.mercado, ufs or {"SP"}),
        D.ler_concorrentes(e.concorrentes),
        dim,
        fato,
        D.ler_ultra(e.ultra) if e.ultra and Path(e.ultra).exists() else None,
        e.censo_geo_dir if e.censo_geo_dir and Path(e.censo_geo_dir).exists() else None,
        e.staging_dir,
        e.assets_dir,
        A.referencia_ocupacao(D.ler_mercado_brasil(e.mercado)),
    )


def _inteiro(v: object) -> int:
    return int(v) if isinstance(v, (int, float)) else 0


def _regiao_das_inauguradas(
    inaug: pd.DataFrame, dim: pd.DataFrame, master: Master, mercado: pd.DataFrame
) -> pd.Series:
    """`regiao_id` de cada linha da aba Inauguradas: pela coordenada do painel (nome+UF, ou só o
    nome quando ele é único) e o município do hexágono; sem o painel, pela UF quando ela cabe numa
    região só do master."""
    linhas: list[dict] = []
    for nome, uf in zip(inaug["unidade"], inaug["uf"], strict=True):
        mesmo = dim[dim["chave_nome"] == A.normalizar(nome)]
        hit = mesmo[mesmo["uf"] == str(uf).upper()]
        if hit.empty and len(mesmo) == 1:
            hit = mesmo
        lin = hit.iloc[0].to_dict() if len(hit) else {}
        linhas.append(
            {
                "uf": str(uf).upper(),
                "lat": lin.get("lat"),
                "lng": lin.get("lng"),
                "cidade_cadastro": lin.get("cidade_cadastro"),
            }
        )
    df = pd.DataFrame(linhas, index=inaug.index)
    df["municipio_ref"] = A.municipio_da_coordenada(df, mercado)
    reg = A.atribuir_regiao(
        df.fillna({"municipio_ref": ""}), master, col_uf="uf", col_mun="municipio_ref"
    )
    por_uf = {uf: [r.id for r in master.regioes if uf in r.ufs] for uf in set(df["uf"])}
    sem = df["lat"].isna()
    reg[sem] = [por_uf[u][0] if len(por_uf[u]) == 1 else None for u in df.loc[sem, "uf"]]
    return reg


def so_a_regiao(master: Master, regiao_id: str) -> Master:
    """O master com uma região só, para o relatório daquela região (17/11, Juan: "tem que ser
    um de RJ e um de SP"). A meta do contrato é do master inteiro, então a quantidade e a meta do
    ano não vão para o relatório de uma região; o prazo e quem conta, sim."""
    r = next(x for x in master.regioes if x.id == regiao_id)
    return replace(
        master,
        id=f"{master.id}_{regiao_id}",
        nome_exibicao=f"{master.nome_exibicao} · {r.nome}",
        regioes=(r,),
        meta=MetaAberturas(
            prazo=master.meta.prazo, conta_tambem=master.meta.conta_tambem, fonte=master.meta.fonte
        ),
    )


def montar_dados(
    master: Master,
    base: Base,
    gerado_em: pd.Timestamp,
    teste: bool = True,
    modelo: str = "antigo",
    regiao_id: str | None = None,
) -> tuple[DadosRelatorio, dict]:
    """Os dados de um relatório. Com `regiao_id`, o de UMA região do master: mercado, mapas,
    bairros e slides novos da região; unidades, assinadas e as que contam para a meta, só as dela."""
    inauguradas, pipeline = base.inauguradas, base.pipeline
    unidades, sem_dados = A.unidades_do_master(inauguradas, base.dim, master, base.mercado)
    if regiao_id is not None:
        cheio = master
        master = so_a_regiao(cheio, regiao_id)
        if "regiao_id" in unidades.columns:
            unidades = unidades[unidades["regiao_id"] == regiao_id].reset_index(drop=True)
        do_master = pipeline["master"].map(A.normalizar) == A.normalizar(cheio.nome_planilha)
        reg_pipe = pd.Series(
            [
                (r.id if (r := cheio.regiao_do_pipeline(f"{un} {cid or ''}", uf)) else None)
                for un, cid, uf in zip(
                    pipeline["unidade"],
                    pipeline.get("cidade", pd.Series([None] * len(pipeline), index=pipeline.index)),
                    pipeline["uf"],
                    strict=True,
                )
            ],
            index=pipeline.index,
        )
        pipeline = pipeline[~do_master | (reg_pipe == regiao_id)]
        inauguradas = inauguradas[
            _regiao_das_inauguradas(inauguradas, base.dim, cheio, base.mercado) == regiao_id
        ]
    ultra = base.ultra if base.ultra is not None else base.dim
    regioes = A.comparar_regioes(base.mercado, master, base.concorrentes, ultra)
    metas, metas_resumo = A.proposta_metas(regioes, unidades, pipeline, master, base.data_ref)
    d = DadosRelatorio(
        master=master,
        gerado_em=gerado_em,
        data_ref=base.data_ref,
        snapshot_mercado=base.snapshot_mercado,
        regioes=regioes,
        unidades=unidades,
        metas=metas,
        metas_resumo=metas_resumo,
        meta_contrato=A.progresso_meta(
            inauguradas,
            pipeline,
            master,
            gerado_em,
            _inteiro(metas_resumo["aberturas_12m"]),
            base.dim,
        ),
        teste=teste,
        referencia_ocupacao=base.referencia_ocupacao,
        assets_dir=base.assets_dir,
        **_estudo_de_area(master, base, unidades),
    )
    if modelo != "antigo":
        d.funcionamento = F.montar(master, base.dim, base.fato, base.mercado, base.data_ref)
    municipios_base = base.mercado.groupby("uf")["nome_municipio"].unique().to_dict()
    aviso = {
        "master": master.id,
        "n_unidades": int(len(unidades)),
        "unidades_sem_dados": sem_dados,
        "municipios_sem_match": municipios_sem_match(master, municipios_base),
        "pipeline_sem_regiao": metas_resumo.get("n_pipeline_fora", 0),
    }
    return d, aviso


def _marcar_unidades_do_master(
    pontos: pd.DataFrame, unidades: pd.DataFrame, raio_km: float = 1.0
) -> pd.DataFrame:
    """`do_master` nos pinos Ultra do motor: cada unidade do master casa com o pino livre mais perto.

    As duas bases têm coordenadas próprias (o pino do motor e o do painel das unidades podem
    diferir algumas centenas de metros). Unidade do master sem pino a até `raio_km` entra como
    ponto novo, para não sumir do mapa.
    """
    out = pontos.assign(do_master=False)
    livres = set(out.index)
    extras = []
    for la, lo in zip(unidades.get("lat", []), unidades.get("lng", []), strict=True):
        if pd.isna(la) or pd.isna(lo):
            continue
        dist = {i: A.distancia_km(la, lo, out.at[i, "lat"], out.at[i, "lng"]) for i in livres}
        perto = min(dist, key=dist.__getitem__) if dist else None
        if perto is not None and dist[perto] <= raio_km:
            out.at[perto, "do_master"] = True
            livres.discard(perto)
        else:
            extras.append({"lat": la, "lng": lo, "do_master": True})
    return pd.concat([out, pd.DataFrame(extras)], ignore_index=True) if extras else out


def _regiao_dos_pontos(pontos: pd.DataFrame, m: pd.DataFrame) -> list:
    """A área de cada unidade Ultra do mapa, para o mapa de cada área no relatório com duas ou
    mais (19/11/2026, Juan: o DF/GO com um mapa para o DF e outro para Goiás): a do hexágono do
    pino (`hex_id_res7`), a mesma regra que punha a unidade no relatório de cada área; a unidade do
    master sem pino fica com a do hexágono do território mais perto dela."""
    if pontos.empty or m.empty:
        return [None] * len(pontos)
    por_hex = dict(zip(m["hex_id"].astype(str), m["regiao_id"], strict=True))
    lat = m["lat"].to_numpy(dtype=float)
    lng = m["lng"].to_numpy(dtype=float)
    reg = m["regiao_id"].to_numpy(dtype=object)
    coslat = float(np.cos(np.radians(np.nanmean(lat))))
    hexes = (
        pontos["hex_id_res7"] if "hex_id_res7" in pontos else pd.Series(None, index=pontos.index)
    )
    out = []
    for h, la, lo in zip(
        hexes, pontos["lat"].astype(float), pontos["lng"].astype(float), strict=True
    ):
        r = por_hex.get(str(h)) if isinstance(h, str) else None
        if r is None:
            r = reg[int(np.nanargmin((lat - la) ** 2 + ((lng - lo) * coslat) ** 2))]
        out.append(r)
    return out


def _estudo_de_area(master: Master, base: Base, unidades: pd.DataFrame) -> dict:
    """Municípios, bairros e as camadas dos mapas do território (`masters.area`)."""
    if not master.regioes:
        return {}
    m = base.mercado.assign(regiao_id=A.atribuir_regiao(base.mercado, master))
    m = m[m["regiao_id"].notna()]
    conc = base.concorrentes["hex_id_res7"].value_counts()
    hexes = pd.DataFrame(
        {
            "hex_id": m["hex_id"],
            "lat": m["lat"],
            "lng": m["lng"],
            "regiao_id": m["regiao_id"],
            "populacao": m["pop_hex_base"],
            "espaco_livre": m["oferta_efetiva_disponivel"],
            "n_concorrentes": m["hex_id"].map(conc).fillna(0),
            # Quantas alcançam o hexágono (1 km), a contagem do motor: a de influência (DEC-057)
            # e, em artefato antigo, a de mapeadas a 1 km.
            "n_concorrentes_1km": next(
                (
                    m[c]
                    for c in ("n_concorrentes_influencia_1km", "n_concorrentes_mapeados_1km")
                    if c in m
                ),
                pd.Series(float("nan"), index=m.index),
            ),
        }
    )
    ultra = (
        base.ultra
        if base.ultra is not None
        else pd.DataFrame(columns=["lat", "lng", "hex_id_res7"])
    )
    up = ultra[ultra["hex_id_res7"].isin(set(m["hex_id"]))][["lat", "lng", "hex_id_res7"]]
    up = up.reset_index(drop=True)
    no_territorio = unidades[unidades["regiao_id"].notna()] if "regiao_id" in unidades else unidades
    up = _marcar_unidades_do_master(up, no_territorio)
    up["regiao_id"] = _regiao_dos_pontos(up, m)
    up = up.drop(columns="hex_id_res7")
    saida: dict = {
        "hexes": hexes[hexes["populacao"] > 0].reset_index(drop=True),
        "ultra_pontos": up,
        # O contorno de cada área, da união de TODOS os hexágonos dela (os vazios também, senão
        # o contorno sai cheio de buracos): o mapa do território só demarca a área (19/11/2026).
        "contornos": {
            str(rid): MP.contorno(list(g["hex_id"].astype(str)))
            for rid, g in m.groupby("regiao_id")
        },
    }
    if base.censo_geo_dir is None:
        return saida
    municipios = AR.municipios_do_territorio(base.mercado, master)
    setores = AR.ler_setores(municipios, base.censo_geo_dir, base.staging_dir)
    if setores.empty:
        return saida
    area = setores["area_setor_km2_ibge"]
    saida["setores_mapa"] = pd.DataFrame(
        {
            "lat": setores["lat"],
            "lng": setores["lng"],
            "renda_dom": setores["renda_dom"],
            "domicilios": setores["domicilios_particulares_ocupados_setor_2022"],
            "densidade": setores["pop_total_setor_2022"] / area.where(area > 0),
            "regiao_id": setores["regiao_id"],
        }
    )
    saida["visao"] = AR.visao_municipios(setores, base.mercado, master)
    saida["bairros"] = AR.bairros(setores, master, set(ultra["hex_id_res7"]))
    return saida


def rotulo_trimestre(ts: pd.Timestamp) -> str:
    return f"{ts.year}T{(ts.month - 1) // 3 + 1}"


def nome_do_arquivo(master_id: str, gerado_em: pd.Timestamp, modelo: str) -> str:
    sufixo = "" if modelo == "antigo" else f"_{modelo}"
    return f"relatorio_master_{master_id}_{rotulo_trimestre(gerado_em)}{sufixo}.pdf"


def _apontar_insumos_da_renda(staging: Path | str) -> None:
    """Aponta os insumos da renda para o staging do relatório SÓ se ainda não apontam para ele.

    `insumos.configurar_staging` zera os caches de renda do PROCESSO inteiro, que as outras telas
    do piloto também leem: chamar a cada PDF ou estudo jogava fora o cache de todo mundo a cada
    pedido, inclusive no meio de uma requisição concorrente (achado da revisão automática do
    #568). No piloto o staging é o mesmo da subida, e nada é reapontado.
    """
    from motor_expansao.renda import insumos

    if Path(insumos.staging_dir()).resolve() != Path(staging).resolve():
        insumos.configurar_staging(staging)


def pdf_do_master(
    e: Entradas,
    master: Master,
    gerado_em: pd.Timestamp,
    regiao_id: str | None = None,
    planilha: tuple[pd.DataFrame, pd.DataFrame] | None = None,
    teste: bool = True,
    modelo: str = "novo",
) -> tuple[bytes, str]:
    """O relatório de UM master (ou de uma região dele) em memória, sem gravar nada: o que o botão
    da tela Masters pede ao piloto (BLK-MASTERS-04). Devolve (PDF, nome do arquivo).

    `modelo="novo"` = o modelo antigo mais os padrões das unidades quando a região tem dado.
    """
    if e.staging_dir is not None:
        _apontar_insumos_da_renda(e.staging_dir)  # uplift e moradores da renda exibida
    base = carregar_base(e, [master], planilha=planilha)
    d, _ = montar_dados(master, base, gerado_em, teste=teste, modelo=modelo, regiao_id=regiao_id)
    return gerar_pdf(d, modelo), nome_do_arquivo(d.master.id, gerado_em, modelo)


def estudo_do_master(
    e: Entradas,
    master: Master,
    gerado_em: pd.Timestamp,
    planilha: tuple[pd.DataFrame, pd.DataFrame] | None = None,
) -> dict:
    """O "Onde expandir" da aba Expansão da tela do master (BLK-MASTERS-04; 18/11/2026, Juan: "a
    recomendação, igual está no relatório, para onde expandir"): os cartões da Análise de
    Oportunidade, pela MESMA função do PDF (`cartoes_da_analise`), do master inteiro."""
    if e.staging_dir is not None:
        _apontar_insumos_da_renda(e.staging_dir)  # uplift e moradores da renda exibida
    base = carregar_base(e, [master], planilha=planilha)
    d, _ = montar_dados(master, base, gerado_em, modelo="antigo")
    return {
        "analise": [
            {"cor": cor, "titulo": titulo, "texto": texto}
            for cor, titulo, texto in cartoes_da_analise(d)
        ]
    }


def gerar(
    e: Entradas,
    masters: list[Master],
    saida: Path,
    gerado_em: pd.Timestamp | None = None,
    teste: bool = True,
    modelo: str = "antigo",
    por_regiao: bool = False,
) -> dict:
    """Um relatório por master; com `por_regiao`, um por região dos masters com mais de uma."""
    gerado_em = gerado_em or pd.Timestamp.now().normalize()
    if e.staging_dir is not None:
        _apontar_insumos_da_renda(e.staging_dir)  # uplift e moradores da renda exibida
    base = carregar_base(e, masters)
    pasta = saida / rotulo_trimestre(gerado_em)
    pasta.mkdir(parents=True, exist_ok=True)
    manifesto: dict = {
        "modelo": modelo,  # antigo = 10 slides; novo = + slides a mais; so_novos = teste (BLK-MASTERS-02)
        "gerado_em": gerado_em.isoformat(),
        "dados_unidades_ate": base.data_ref.date().isoformat(),
        "snapshot_mercado": base.snapshot_mercado,
        "relatorios": [],
    }
    alvos = [
        (m, rid)
        for m in masters
        for rid in ([r.id for r in m.regioes] if por_regiao and len(m.regioes) > 1 else [None])
    ]
    for m, rid in alvos:
        try:
            d, aviso = montar_dados(m, base, gerado_em, teste=teste, modelo=modelo, regiao_id=rid)
            if modelo == "so_novos" and not F.tem_dados(d.funcionamento):
                manifesto["relatorios"].append({**aviso, "status": "sem_dados_na_regiao"})
                continue
            arq = pasta / nome_do_arquivo(d.master.id, gerado_em, modelo)
            arq.write_bytes(gerar_pdf(d, modelo))
            manifesto["relatorios"].append({**aviso, "arquivo": arq.name, "status": "ok"})
        except Exception as exc:  # um master com problema não derruba os outros
            manifesto["relatorios"].append(
                {"master": m.id, "status": "erro", "erro": f"{type(exc).__name__}: {exc}"}
            )
    (pasta / "_manifest.json").write_text(
        json.dumps(manifesto, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    return manifesto
