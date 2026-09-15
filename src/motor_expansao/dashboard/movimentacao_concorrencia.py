"""Movimentação da concorrência — quem abriu, fechou, anunciou ou mudou no agregador.

Fonte: o pacote garimpado da VPS em 2026-09-15 (`Movimentacao_Concorrencia/movimentacao`),
porque o coletor SOBRESCREVE os CSVs de unidades todo domingo e o snapshot por unidade do
motor só começou em 06/09. O pacote traz três arquivos com coordenada, e só eles entram:

- `01_cadastro_aberturas_fechamentos.csv`: unidades de CADEIA que entraram/saíram entre fotos.
  `leitura = usar` (02/08 -> 06/09, fotos validadas contra a contagem oficial) vira confiança
  `alta`; `usar_com_cautela_foto_nao_validada` (28/05 -> 02/08) vira `cautela`. `NAO_USAR_*`
  (Smart Fit: teto de 1.000 do coletor) e `ruido_*` (recalibração de geocodificação) FICAM FORA.
  Mudança de coordenada e "mesmo nome em outro lugar" não são movimento de mercado e também saem.
- `03_pipeline_anunciado_em_breve.csv`: unidades anunciadas como "Em breve" ainda não inauguradas.
- `06_wellhub_entradas_saidas.csv`: academias (rede ou independente) que entraram/saíram do Wellhub.

"Saiu do site" nem sempre é fechamento (página removida, coletor que parou de achar a unidade)
e "entrou no Wellhub" pode ser credenciamento, não inauguração — a tela diz as duas coisas.

Camada visual e READ-ONLY sobre o M1. Funções puras; o script de ingestão lê a pasta.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ARQUIVO_STAGING = "movimentacao_concorrencia.parquet"
#: Total de unidades por rede na contagem oficial (o número do relatório do Telegram).
ARQUIVO_CONTAGEM_STAGING = "contagem_redes_concorrencia.parquet"
ARQUIVO_CONTAGEM = "contagem_oficial_por_rede_por_domingo.csv"

ARQUIVO_CADASTRO = "01_cadastro_aberturas_fechamentos.csv"
ARQUIVO_EM_BREVE = "03_pipeline_anunciado_em_breve.csv"
ARQUIVO_WELLHUB = "06_wellhub_entradas_saidas.csv"

#: Ordem de leitura na tela: o que aumenta a disputa primeiro.
TIPOS: dict[str, str] = {
    "abertura": "Aberturas",
    "inauguracao": "Inaugurações de \"Em breve\"",
    "em_breve": "Anunciadas \"Em breve\"",
    "fechamento": "Fechamentos ou saídas do site",
    "entrou_agregador": "Entraram no Wellhub",
    "saiu_agregador": "Saíram do Wellhub",
}

STATUS_CADASTRO = {
    "entrou_abriu_ou_apareceu_no_site": "abertura",
    "inauguracao": "inauguracao",
    "inaugurou_saiu_do_em_breve": "inauguracao",
    "saiu_fechou_ou_sumiu_do_site": "fechamento",
}
LEITURA_CONFIANCA = {"usar": "alta", "usar_com_cautela_foto_nao_validada": "cautela"}

#: Abertura e fechamento da MESMA rede, no MESMO período, a até esta distância são uma troca
#: de cadastro (renomeação + coordenada recalibrada), não duas movimentações. O pacote já casa
#: a mesma unidade a 150 m; medido em 15/09, sobravam 32 pares entre 150 m e 1 km (29 na foto
#: não validada) — em Valparaíso de Goiás, "BR 040 (GO)" abria enquanto "BR 040 – Valparaíso
#: de Goiás (GO)" fechava.
DIST_TROCA_CADASTRO_M = 1_000.0

COLUNAS = ("fonte", "tipo", "confianca", "rede", "nome", "lat", "lng", "de", "ate")
RAIO_ENTORNO_M = 2_000.0


def _texto(serie: pd.Series) -> pd.Series:
    return serie.astype("string").str.strip().replace("", pd.NA)


def _quadro(df: pd.DataFrame, **colunas: Any) -> pd.DataFrame:
    saida = pd.DataFrame({c: colunas.get(c, pd.NA) for c in COLUNAS}, index=df.index)
    saida["lat"] = pd.to_numeric(saida["lat"], errors="coerce")
    saida["lng"] = pd.to_numeric(saida["lng"], errors="coerce")
    return saida.dropna(subset=["lat", "lng"])


def normalizar_cadastro(df: pd.DataFrame) -> pd.DataFrame:
    """Aberturas, inaugurações e fechamentos de cadeia, só nas leituras utilizáveis."""
    confianca = df["leitura"].map(LEITURA_CONFIANCA)
    tipo = df["status"].map(STATUS_CADASTRO)
    ok = confianca.notna() & tipo.notna()
    df = df[ok]
    nome = _texto(df["nome_depois"]).fillna(_texto(df["nome_antes"]))
    quadro = _quadro(
        df, fonte="cadastro", tipo=tipo[ok], confianca=confianca[ok], rede=_texto(df["rede"]),
        nome=nome, lat=df["latitude"], lng=df["longitude"], de=df["de"], ate=df["ate"],
    )
    return descartar_trocas_de_cadastro(quadro)


def descartar_trocas_de_cadastro(quadro: pd.DataFrame, limite_m: float = DIST_TROCA_CADASTRO_M) -> pd.DataFrame:
    """Tira os pares abertura x fechamento da mesma rede e período a até `limite_m` (um par por fechamento)."""
    fora: set[Any] = set()
    for _, grupo in quadro.groupby(["rede", "de", "ate"], dropna=False):
        aberturas = grupo[grupo["tipo"].isin(["abertura", "inauguracao"])]
        fechamentos = grupo[grupo["tipo"] == "fechamento"]
        if not len(aberturas) or not len(fechamentos):
            continue
        livres = list(fechamentos.index)
        for i, a in aberturas.iterrows():
            if not livres:
                break
            f = fechamentos.loc[livres]
            d = _distancias_m(float(a["lat"]), float(a["lng"]), f["lat"].to_numpy(float), f["lng"].to_numpy(float))
            k = int(np.argmin(d))
            if d[k] <= limite_m:
                fora.update({i, livres[k]})
                livres.pop(k)
    return quadro.drop(index=list(fora))


def normalizar_em_breve(df: pd.DataFrame) -> pd.DataFrame:
    """Anúncios "Em breve" que ainda não inauguraram na última foto."""
    df = df[df["situacao_06_09"].astype(str).str.startswith("ainda_em_breve")]
    return _quadro(
        df, fonte="em_breve", tipo="em_breve", confianca="alta", rede=_texto(df["rede"]),
        nome=_texto(df["nome_anunciado"]), lat=df["latitude"], lng=df["longitude"],
        de=df["primeira_evidencia"], ate=df["ultima_evidencia_anunciada"],
    )


def normalizar_wellhub(df: pd.DataFrame) -> pd.DataFrame:
    """Entradas e saídas do Wellhub (redes e independentes)."""
    tipo = df["tipo"].map({"entrada": "entrou_agregador", "saida": "saiu_agregador"})
    df, tipo = df[tipo.notna()], tipo[tipo.notna()]
    return _quadro(
        df, fonte="wellhub", tipo=tipo, confianca="alta", rede=_texto(df["rede_agregador"]),
        nome=_texto(df["nome"]), lat=df["latitude"], lng=df["longitude"], de=df["de"], ate=df["ate"],
    )


def _ler_csv(caminho: Path) -> pd.DataFrame:
    return pd.read_csv(caminho, sep=None, engine="python", dtype=str, encoding="utf-8-sig")


def montar(pasta: Path) -> pd.DataFrame:
    """Lê os três CSVs do pacote e devolve os eventos com coordenada. Arquivo ausente = sem eventos dele."""
    partes = []
    for nome, funcao in (
        (ARQUIVO_CADASTRO, normalizar_cadastro),
        (ARQUIVO_EM_BREVE, normalizar_em_breve),
        (ARQUIVO_WELLHUB, normalizar_wellhub),
    ):
        caminho = Path(pasta) / nome
        if caminho.is_file():
            partes.append(funcao(_ler_csv(caminho)))
    if not partes:
        raise FileNotFoundError(f"nenhum CSV de movimentação em {pasta}")
    quadro = pd.concat(partes, ignore_index=True)
    for c in ("fonte", "tipo", "confianca", "rede", "nome", "de", "ate"):
        quadro[c] = quadro[c].astype("string")
    return quadro.reset_index(drop=True)


def _distancias_m(lat: float, lng: float, lats: np.ndarray, lngs: np.ndarray) -> np.ndarray:
    raio_terra = 6_371_008.8
    p1, p2 = np.radians(lat), np.radians(lats)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lngs - lng) / 2) ** 2
    return 2 * raio_terra * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def _limpo(v: Any) -> Any:
    return None if v is None or (not isinstance(v, str) and pd.isna(v)) else v


def filtrar_concorrencia(eventos: pd.DataFrame | None, excluir_redes: Iterable[str] = ()) -> pd.DataFrame | None:
    """Tira a própria Ultra e as redes excluídas (estúdios boutique, DEC-056)."""
    if eventos is None:
        return None
    rede = eventos["rede"].astype("string").fillna("")
    nome = eventos["nome"].astype("string").fillna("")
    fora = rede.isin(set(excluir_redes)) | rede.str.lower().eq("ultra")
    fora = fora | nome.str.contains(r"\bultra\s+academia\b", case=False, regex=True)
    return eventos[~fora.to_numpy(dtype=bool)].reset_index(drop=True)


def contagem_vazia() -> dict[str, int]:
    return dict.fromkeys(TIPOS, 0)


def eventos_no_entorno(
    lat: float, lng: float, eventos: pd.DataFrame | None, *, raio_m: float = RAIO_ENTORNO_M
) -> list[dict[str, Any]]:
    """Eventos a até `raio_m`, na ordem de `TIPOS` e, dentro do tipo, do mais perto ao mais longe."""
    if eventos is None or not len(eventos):
        return []
    d = _distancias_m(lat, lng, eventos["lat"].to_numpy(dtype=float), eventos["lng"].to_numpy(dtype=float))
    perto = eventos[d <= raio_m].assign(distancia_m=d[d <= raio_m])
    ordem = {t: i for i, t in enumerate(TIPOS)}
    perto = perto.assign(_ordem=perto["tipo"].map(ordem)).sort_values(["_ordem", "distancia_m"], kind="stable")
    return [
        {
            "fonte": str(r.fonte),
            "tipo": str(r.tipo),
            "confianca": str(r.confianca),
            "rede": _limpo(r.rede),
            "nome": _limpo(r.nome),
            "distancia_m": round(float(r.distancia_m)),
            "de": _limpo(r.de),
            "ate": _limpo(r.ate),
        }
        for r in perto.itertuples(index=False)
    ]


def contar(itens: Iterable[dict[str, Any]]) -> dict[str, int]:
    contagem = contagem_vazia()
    for item in itens:
        if item["tipo"] in contagem:
            contagem[item["tipo"]] += 1
    return contagem


def periodos(eventos: pd.DataFrame | None) -> list[dict[str, Any]]:
    """Janelas cobertas por fonte e confiança — o que a tela precisa dizer junto dos números."""
    if eventos is None or not len(eventos):
        return []
    grupos = eventos.groupby(["fonte", "confianca"], dropna=False)
    return [
        {
            "fonte": str(fonte),
            "confianca": str(confianca),
            "de": _limpo(g["de"].min()),
            "ate": _limpo(g["ate"].max()),
            "n": len(g),
        }
        for (fonte, confianca), g in grupos
    ]


def resumo_por_rede(eventos: pd.DataFrame | None) -> list[dict[str, Any]]:
    """Crescimento de cada REDE no pacote inteiro: aberturas, fechamentos, saldo e "Em breve".

    Vale o cadastro das redes (e o pipeline "Em breve"); o Wellhub fica em `resumo_agregadores`,
    senão uma unidade de rede credenciada no agregador contaria como abertura. As colunas
    `*_conferidas` separam o que veio das fotos validadas (confiança `alta`).
    """
    if eventos is None or not len(eventos):
        return []
    cad = eventos[eventos["fonte"].isin(["cadastro", "em_breve"]) & eventos["rede"].notna()]
    linhas = []
    for rede, g in cad.groupby("rede"):
        alta = g["confianca"].eq("alta")
        abre = g["tipo"].isin(["abertura", "inauguracao"])
        fecha = g["tipo"].eq("fechamento")
        linhas.append(
            {
                "rede": str(rede),
                "aberturas": int(abre.sum()),
                "aberturas_conferidas": int((abre & alta).sum()),
                "fechamentos": int(fecha.sum()),
                "fechamentos_conferidos": int((fecha & alta).sum()),
                "em_breve": int(g["tipo"].eq("em_breve").sum()),
                "saldo": int(abre.sum() - fecha.sum()),
            }
        )
    return sorted(linhas, key=lambda r: (-r["saldo"], -r["aberturas"], -r["em_breve"], r["rede"]))


def resumo_agregadores(eventos: pd.DataFrame | None) -> list[dict[str, Any]]:
    """Entradas e saídas do agregador, separando independentes de unidades de rede."""
    if eventos is None or not len(eventos):
        return []
    saida = []
    for fonte, g in eventos[eventos["fonte"].eq("wellhub")].groupby("fonte"):
        for grupo, mascara in (("independentes", g["rede"].isna()), ("redes", g["rede"].notna())):
            parte = g[mascara]
            entradas = int(parte["tipo"].eq("entrou_agregador").sum())
            saidas = int(parte["tipo"].eq("saiu_agregador").sum())
            saida.append(
                {
                    "agregador": str(fonte),
                    "grupo": grupo,
                    "entradas": entradas,
                    "saidas": saidas,
                    "saldo": entradas - saidas,
                    "de": _limpo(g["de"].min()),
                    "ate": _limpo(g["ate"].max()),
                }
            )
    return saida


def contagem_oficial(tabela: pd.DataFrame, ate: str | None) -> pd.DataFrame:
    """Unidades por rede no domingo `ate` (ou no último domingo ANTERIOR a ele que exista na série).

    A data vem do fim do período validado do cadastro, e não do último domingo da série: a foto
    de 13/09 está corrompida pelo crash do lote (Selfit caiu de 231 para 119 sem fechar nada).
    """
    datas = sorted(c for c in tabela.columns if c != "rede")
    if ate is not None:
        datas = [d for d in datas if d <= ate]
    if not datas:
        return pd.DataFrame(columns=["rede", "unidades", "data"])
    data = datas[-1]
    saida = pd.DataFrame(
        {"rede": tabela["rede"].astype(str), "unidades": pd.to_numeric(tabela[data], errors="coerce"), "data": data}
    )
    return saida.dropna(subset=["unidades"]).astype({"unidades": int}).reset_index(drop=True)


def fim_validado(eventos: pd.DataFrame) -> str | None:
    """Último dia do período VALIDADO do cadastro (confiança alta)."""
    alta = eventos[eventos["fonte"].eq("cadastro") & eventos["confianca"].eq("alta")]
    return _limpo(alta["ate"].max()) if len(alta) else None
