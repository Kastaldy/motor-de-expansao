from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from shapely import from_wkb
from shapely.geometry import box

from motor_expansao.pipelines.materializar_setores_censitarios_geo import (
    COLUNAS_ARTEFATO,
    CRS_ORIGEM,
    calcular_k_global,
    escrever_particoes,
    gerar_relatorio,
    ler_particao_setores,
    montar_base_setorial_uf,
)


def _malha_fake() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {
            "cod_setor": ["355030801000001", "355030801000002", "355030802000001"],
            "uf": ["SP", "SP", "SP"],
            "cod_uf": ["35", "35", "35"],
            "cod_municipio": ["3550308", "3550308", "3550308"],
            "nome_municipio": ["SAO PAULO", "SAO PAULO", "SAO PAULO"],
            # BLK-RELMUN-02: NM_BAIRRO materializado (cobertura heterogenea: 1 setor sem bairro).
            "nome_bairro": ["Bela Vista", "Centro", pd.NA],
            "cod_bairro": ["3550308001", "3550308002", pd.NA],
            "situacao_setor": ["Urbana", "Urbana", "Urbana"],
            "area_setor_km2_ibge": [1.0, 1.0, 1.0],
            "geometry": [
                box(-46.70, -23.60, -46.69, -23.59),
                box(-46.69, -23.60, -46.68, -23.59),
                box(-46.68, -23.60, -46.67, -23.59),
            ],
        },
        crs=CRS_ORIGEM,
    )


# Basico e renda vem EMBARALHADOS (ordem diferente da malha) de proposito: o join agora e' por
# CHAVE `cod_setor`, entao a ordem das linhas nao pode mais importar. A verdade por setor e':
#   A=...801000001 -> pop 900,  renda_resp 3000  (renda_pc 1000)
#   B=...801000002 -> pop 1800, renda_resp 4500  (renda_pc 1500)
#   C=...802000001 -> pop 2700, renda_resp 6000  (renda_pc 2000)
def _basico_fake() -> pd.DataFrame:
    # Ordem [B, C, A] — diferente da malha [A, B, C].
    return pd.DataFrame(
        {
            "cod_setor": ["355030801000002", "355030802000001", "355030801000001"],
            "uf": ["SP", "SP", "SP"],
            "cod_uf": ["35", "35", "35"],
            "cod_municipio": ["3550308", "3550308", "3550308"],
            "area_setor_km2_ibge": [1.0, 1.0, 1.0],
            "pop_total_setor_2022": [1800.0, 2700.0, 900.0],
            "domicilios_particulares_ocupados_setor_2022": [600.0, 900.0, 300.0],
            "avg_moradores_domicilio_setor_2022": [3.0, 3.0, 3.0],
        }
    )


def _renda_fake() -> pd.DataFrame:
    # Ordem [C, A, B] — diferente da malha e do basico.
    return pd.DataFrame(
        {
            "cod_setor": ["355030802000001", "355030801000001", "355030801000002"],
            "uf": ["SP", "SP", "SP"],
            "cod_uf": ["35", "35", "35"],
            "renda_responsavel_media_setor_2022": [6000.0, 3000.0, 4500.0],
            "responsaveis_com_renda_setor_2022": [850.0, 280.0, 570.0],
        }
    )


def _m1_reference_fake() -> pd.DataFrame:
    return pd.DataFrame({"renda_per_capita": [800.0, 1200.0, 1600.0, 2200.0, 3200.0]})


def _k_fake() -> float:
    """O k que estes fixtures produzem: 1600 (mediana M1) / 1500 (mediana setorial) = 1,0667.

    Calculado pelo caminho REAL — `montar_base_setorial_uf` exige o k explicito desde
    2026-08-13, justamente para nao existir um caminho em que ele saia de uma UF so.
    """
    k = calcular_k_global(_basico_fake(), _renda_fake(), _m1_reference_fake())
    assert k is not None
    return k


def test_monta_base_setorial_geo_com_schema_crs_e_metricas():
    result = montar_base_setorial_uf(
        _malha_fake(),
        _basico_fake(),
        _renda_fake(),
        uf="SP",
        m1_reference=_m1_reference_fake(),
        k_global=_k_fake(),
        data_materializacao="2026-05-22",
    )

    assert list(result.columns) == COLUNAS_ARTEFATO
    assert len(result) == 3
    assert set(result["uf"]) == {"SP"}
    assert set(result["cod_municipio"]) == {"3550308"}
    assert result["crs_origem"].eq(CRS_ORIGEM).all()
    assert result["area_setor_m2"].gt(0).all()
    assert result["densidade_pop_setor_hab_km2"].gt(0).all()
    assert result["flag_geometria_valida"].all()
    assert result["flag_renda_disponivel"].all()
    assert result["flag_score_calibrado_disponivel"].all()
    assert result["score_setor_2022_calibrado"].between(0, 100).all()
    assert from_wkb(result.loc[0, "geometry_wkb"]).is_valid
    # BLK-RELMUN-02: nome_bairro flui ao artefato (com NA preservado no setor sem bairro).
    assert "nome_bairro" in result.columns
    assert list(result["nome_bairro"].fillna("<NA>")) == ["Bela Vista", "Centro", "<NA>"]


def test_join_por_chave_ignora_ordem_e_setor_faltante():
    # Regressao do bug do join posicional: renda SEM o setor B e em ordem [C, A]. O join por CHAVE
    # deve dar a CADA setor a sua propria renda (ordem irrelevante) e deixar B com renda ausente —
    # nunca a renda de um vizinho, como fazia o antigo alinhamento por posicao.
    renda_incompleta = pd.DataFrame(
        {
            "cod_setor": ["355030802000001", "355030801000001"],  # [C, A], sem B
            "uf": ["SP", "SP"],
            "cod_uf": ["35", "35"],
            "renda_responsavel_media_setor_2022": [6000.0, 3000.0],
            "responsaveis_com_renda_setor_2022": [850.0, 280.0],
        }
    )
    result = montar_base_setorial_uf(
        _malha_fake(),
        _basico_fake(),
        renda_incompleta,
        uf="SP",
        m1_reference=_m1_reference_fake(),
        k_global=_k_fake(),
    ).set_index("cod_setor")

    a, b, c = "355030801000001", "355030801000002", "355030802000001"
    # Basico (embaralhado) casou por chave: cada setor manteve a SUA populacao.
    assert result.loc[a, "pop_total_setor_2022"] == 900.0
    assert result.loc[b, "pop_total_setor_2022"] == 1800.0
    assert result.loc[c, "pop_total_setor_2022"] == 2700.0
    # Renda casou por chave: A e C com a sua renda; renda_pc = renda_resp / avg_moradores (3).
    assert result.loc[a, "renda_responsavel_media_setor_2022"] == 3000.0
    assert result.loc[c, "renda_responsavel_media_setor_2022"] == 6000.0
    assert result.loc[a, "renda_per_capita_setor_2022"] == 1000.0
    assert result.loc[c, "renda_per_capita_setor_2022"] == 2000.0
    # B nao existe na renda -> ausente (nunca a renda de um vizinho deslocada pela posicao).
    assert pd.isna(result.loc[b, "renda_responsavel_media_setor_2022"])
    assert not bool(result.loc[b, "flag_renda_disponivel"])
    assert bool(result.loc[a, "flag_renda_disponivel"])
    assert bool(result.loc[c, "flag_renda_disponivel"])


def test_escreve_e_le_particao_por_uf_municipio(tmp_path: Path):
    df = montar_base_setorial_uf(
        _malha_fake(),
        _basico_fake(),
        _renda_fake(),
        uf="SP",
        m1_reference=_m1_reference_fake(),
        k_global=_k_fake(),
    )
    info = escrever_particoes(df, tmp_path)
    loaded = ler_particao_setores(tmp_path, uf="SP", cod_municipio="3550308")

    assert info == {"arquivos": 1, "linhas": 3}
    assert (tmp_path / "uf=SP" / "cod_municipio=3550308" / "part-000.parquet").exists()
    assert len(loaded) == 3
    assert set(COLUNAS_ARTEFATO).issubset(loaded.columns)


def test_relatorio_descreve_artefato_e_guardrail(tmp_path: Path):
    from motor_expansao.pipelines.materializar_setores_censitarios_geo import UFSummary

    report = gerar_relatorio(
        [
            UFSummary(
                uf="SP",
                municipios=1,
                setores=3,
                arquivos=1,
                tamanho_mb=0.01,
                tempo_s=0.2,
                renda_cobertura_pct=100.0,
                score_cobertura_pct=100.0,
            )
        ],
        tmp_path,
        COLUNAS_ARTEFATO,
    )

    assert "Base censitaria geografica otimizada" in report
    assert "geometry_wkb" in report
    assert "nao altera M1 oficial" in report


# ── k GLOBAL: um so para o Brasil, nunca um por UF ────────────────────────────────────────
# Regressao de 2026-08-12. O `k` era calculado dentro de `_calcular_scores_setoriais`, que
# recebe UMA UF por vez (o orquestrador roda `for uf in ufs`). Numerador nacional, denominador
# estadual => cada UF caia exatamente na mediana nacional, apagando a diferenca de renda entre
# estados. Medido no artefato de producao: AC 455,21 x 2,0556 = 935,73; MA 366,88 x 2,5505 =
# 935,73; DF 1.176,07 x 0,7956 = 935,68 — as 27 medianas viravam o MESMO numero. O efeito no
# que e consumido: o score medio de Sao Luis (68,6) ficava ACIMA do de Sao Paulo capital
# (55,7); com o k nacional vira 43,7 contra 63,4.
#
# Nada travava isso, e a trava tem DUAS pontas, porque o defeito tinha duas:
#   1. a granularidade da chamada  -> `test_materializar_base_geo_carimba_o_mesmo_k_...`
#      exercita `materializar_base_geo` INTEIRO (a funcao que roda o laco por UF). E a unica
#      cobertura da linha `k_global=k_global`; sem ela, apagar essa linha passa despercebido.
#   2. o fallback silencioso       -> `test_sem_k_global_falha_alto_...` garante que omitir o
#      k na presenca de M1 e ERRO, e nao um k por UF calculado sem aviso.


def _cenario_duas_ufs() -> tuple[gpd.GeoDataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """SP (rica) e AC (pobre), 3 setores cada. renda_pc = renda_resp / moradores.

    SP: 1000, 1500, 2000 (mediana 1500) | AC: 400, 500, 600 (mediana 500)
    Mediana NACIONAL dos 6 setores: (600 + 1000) / 2 = 800.
    """
    setores = {
        "SP": ["355030801000001", "355030801000002", "355030802000001"],
        "AC": ["120001305000001", "120001305000002", "120001306000001"],
    }
    renda_resp = {"SP": [3000.0, 4500.0, 6000.0], "AC": [1200.0, 1500.0, 1800.0]}

    malha_rows, basico_rows, renda_rows = [], [], []
    for uf, cods in setores.items():
        cod_uf = cods[0][:2]
        for i, cod in enumerate(cods):
            malha_rows.append(
                {
                    "cod_setor": cod,
                    "uf": uf,
                    "cod_uf": cod_uf,
                    "cod_municipio": cod[:7],
                    "nome_municipio": f"MUN {uf}",
                    "nome_bairro": pd.NA,
                    "cod_bairro": pd.NA,
                    "situacao_setor": "Urbana",
                    "area_setor_km2_ibge": 1.0,
                    "geometry": box(-46.70 + i * 0.01, -23.60, -46.69 + i * 0.01, -23.59),
                }
            )
            basico_rows.append(
                {
                    "cod_setor": cod,
                    "uf": uf,
                    "cod_uf": cod_uf,
                    "cod_municipio": cod[:7],
                    "area_setor_km2_ibge": 1.0,
                    "pop_total_setor_2022": 900.0 * (i + 1),
                    "domicilios_particulares_ocupados_setor_2022": 300.0 * (i + 1),
                    "avg_moradores_domicilio_setor_2022": 3.0,
                }
            )
            renda_rows.append(
                {
                    "cod_setor": cod,
                    "uf": uf,
                    "cod_uf": cod_uf,
                    "renda_responsavel_media_setor_2022": renda_resp[uf][i],
                    "responsaveis_com_renda_setor_2022": 280.0,
                }
            )

    malha = gpd.GeoDataFrame(malha_rows, crs=CRS_ORIGEM)
    m1 = pd.DataFrame({"renda_per_capita": [800.0, 1000.0, 1200.0, 1400.0, 1600.0]})  # mediana 1200
    return malha, pd.DataFrame(basico_rows), pd.DataFrame(renda_rows), m1


def test_k_global_e_nacional_e_nao_depende_da_uf():
    """O k sai do join NACIONAL: 1200 / 800 = 1.5, independente de quantas UFs entram."""
    _, basico, renda, m1 = _cenario_duas_ufs()

    k = calcular_k_global(basico, renda, m1)

    assert k is not None
    assert k == pytest.approx(1.5, abs=1e-6)
    assert calcular_k_global(basico, renda, None) is None


def test_mesmo_k_nas_duas_ufs_preserva_a_diferenca_de_renda_entre_estados():
    """Com k unico, SP continua 3x AC. Era isso que o k por UF destruia."""
    malha, basico, renda, m1 = _cenario_duas_ufs()
    k = calcular_k_global(basico, renda, m1)

    medianas, metodos = {}, {}
    for uf in ("SP", "AC"):
        df = montar_base_setorial_uf(
            malha[malha["uf"] == uf].reset_index(drop=True),
            basico[basico["uf"] == uf].reset_index(drop=True),
            renda[renda["uf"] == uf].reset_index(drop=True),
            uf=uf,
            m1_reference=m1,
            k_global=k,
        )
        medianas[uf] = float(df["renda_per_capita_setor_2022_calibrada"].median())
        metodos[uf] = df["metodo_renda_setor_2022"].iloc[0]

    # O MESMO k carimbado nas duas UFs — o metodo e' rastreavel no artefato.
    assert metodos["SP"] == metodos["AC"] == "v06004_div_v0005_multiplicativo_global_k=1.5000"
    # E a razao real entre os estados sobrevive a calibracao (1500/500 = 3).
    assert medianas["SP"] == pytest.approx(2250.0, abs=1e-6)
    assert medianas["AC"] == pytest.approx(750.0, abs=1e-6)
    assert medianas["SP"] / medianas["AC"] == pytest.approx(3.0, abs=1e-6)


def test_sem_k_global_falha_alto_em_vez_de_recalcular_por_uf():
    """O fallback silencioso virou ERRO.

    Ate 2026-08-13 omitir o `k_global` fazia `_calcular_scores_setoriais` recalcula-lo sobre
    as linhas recebidas — de UMA UF — e as duas UFs colapsavam na mesma mediana (1200), sem
    nenhuma mensagem. Agora ha duas barreiras: omitir o argumento e `TypeError` (ele perdeu o
    default), e passar `None` na presenca de M1 e `ValueError`.
    """
    malha, basico, renda, m1 = _cenario_duas_ufs()
    args = (
        malha[malha["uf"] == "SP"].reset_index(drop=True),
        basico[basico["uf"] == "SP"].reset_index(drop=True),
        renda[renda["uf"] == "SP"].reset_index(drop=True),
    )

    with pytest.raises(TypeError, match="k_global"):
        montar_base_setorial_uf(*args, uf="SP", m1_reference=m1)  # type: ignore[call-arg]

    with pytest.raises(ValueError, match="k_global"):
        montar_base_setorial_uf(*args, uf="SP", m1_reference=m1, k_global=None)

    # Sem M1 nao ha o que calibrar: `k_global=None` e legitimo e nao levanta.
    sem_m1 = montar_base_setorial_uf(*args, uf="SP", m1_reference=None, k_global=None)
    assert sem_m1["metodo_renda_setor_2022"].iloc[0] == "v06004_div_v0005_sem_referencia_m1"


def test_calcular_k_global_recusa_insumo_invalido():
    """Com M1 utilizavel, devolver `None` reabriria o k por UF — entao toda falha e erro."""
    _, basico, renda, m1 = _cenario_duas_ufs()

    with pytest.raises(ValueError, match="Numerador"):
        calcular_k_global(basico, renda, m1.assign(renda_per_capita=0.0))

    with pytest.raises(ValueError, match="Denominador"):
        calcular_k_global(basico, renda.assign(renda_responsavel_media_setor_2022=0.0), m1)

    # Join vazio e o modo de falhar MAIS provavel destes insumos (a chave dos dois CSVs e
    # recuperada, nao lida), entao a mensagem tem de trazer o tamanho do join.
    with pytest.raises(ValueError, match="casou 0 setores"):
        calcular_k_global(basico.assign(cod_setor="1"), renda.assign(cod_setor="2"), m1)

    # A falta da chave aponta o loader do frame CERTO, um remedio por lado.
    with pytest.raises(ValueError, match="carregar_basico"):
        calcular_k_global(basico.drop(columns="cod_setor"), renda, m1)
    with pytest.raises(ValueError, match="carregar_renda"):
        calcular_k_global(basico, renda.drop(columns="cod_setor"), m1)


def test_calcular_k_global_ignora_chave_duplicada_no_insumo():
    """Duplicata de chave nao pode virar produto cartesiano e reponderar a mediana.

    A duplicacao precisa ser PARCIAL e assimetrica: duplicar o frame INTEIRO nao move a mediana,
    e um teste assim fica verde mesmo sem os `drop_duplicates` (medido). Duplicando so o AC, a
    mediana nacional cairia de 800 para 600 e o k iria de 1,5 para 2,0 sem a dedup.
    """
    _, basico, renda, m1 = _cenario_duas_ufs()

    assert calcular_k_global(
        pd.concat([basico, basico[basico["uf"] == "AC"]], ignore_index=True), renda, m1
    ) == pytest.approx(1.5, abs=1e-9)
    # O lado de risco REAL em producao e a renda: a chave dela vem enxertada de um agregado irmao.
    assert calcular_k_global(
        basico, pd.concat([renda, renda[renda["uf"] == "AC"]], ignore_index=True), m1
    ) == pytest.approx(1.5, abs=1e-9)


def test_materializar_base_geo_carimba_o_mesmo_k_nas_duas_ufs(tmp_path: Path, monkeypatch):
    """A UNICA cobertura da linha `k_global=k_global` do orquestrador.

    Os demais testes chamam `montar_base_setorial_uf` direto, ja com o k na mao — logo nao
    veem o laco `for uf in ufs`, que e onde o defeito morava. Este roda `materializar_base_geo`
    inteiro sobre duas UFs de renda MUITO diferente e exige o mesmo carimbo nas duas: apagar o
    `k_global=k_global` da chamada a `montar_base_setorial_uf` dentro de `materializar_base_geo`
    faz este teste, e so ele, falhar. (Referencia pelo simbolo de proposito: numero de linha
    envelhece a cada diff.)
    """
    from motor_expansao.pipelines import materializar_setores_censitarios_geo as mod

    malha, basico, renda, _ = _cenario_duas_ufs()
    # Mediana 987 -> k = 987/800 = 1,23375, deliberadamente NAO redondo (e perto do k real de
    # producao, 1,2334632197). Com um k redondo como 1,5, um `round(k, 4)` no manifesto passaria
    # despercebido — medido: a suite ficava verde.
    m1 = pd.DataFrame({"renda_per_capita": [987.0]})
    k_esperado = calcular_k_global(basico, renda, m1)

    # Os insumos so precisam EXISTIR (ha uma checagem de caminho); a leitura de cada um esta
    # substituida abaixo pelos fixtures em memoria.
    for nome in ("basico.csv", "renda.csv", "malha.shp"):
        (tmp_path / nome).write_text("", encoding="utf-8")
    m1_path = tmp_path / "brasil_estrutural.parquet"
    m1.to_parquet(m1_path, index=False)

    # `_ler_chaves_ordenadas` real devolve uma Series (ou levanta) — nunca None. Devolver None
    # aqui montaria uma combinacao impossivel: chaves ausentes com `cod_setor` ja presente no
    # basico, que e o contrato de que a exigencia de `cod_setor` em `calcular_k_global` depende.
    monkeypatch.setattr(
        mod, "_ler_chaves_ordenadas", lambda *_a, **_k: pd.Series(sorted(basico["cod_setor"]))
    )
    monkeypatch.setattr(mod, "carregar_basico", lambda *_a, **_k: basico)
    monkeypatch.setattr(mod, "carregar_renda", lambda *_a, **_k: renda)
    monkeypatch.setattr(
        mod,
        "carregar_malha_uf",
        lambda _shp, uf: malha[malha["uf"] == uf].reset_index(drop=True),
    )

    saida = tmp_path / "out"
    metadata = mod.materializar_base_geo(
        ufs=["SP", "AC"],
        basico_path=tmp_path / "basico.csv",
        renda_path=tmp_path / "renda.csv",
        shp_path=tmp_path / "malha.shp",
        output_root=saida,
        report_path=tmp_path / "relatorio.md",
        m1_reference_path=m1_path,
    )

    carimbos = {
        uf: ler_particao_setores(saida, uf=uf, cod_municipio=cod)[
            "metodo_renda_setor_2022"
        ].iloc[0]
        for uf, cod in (("SP", "3550308"), ("AC", "1200013"))
    }
    # O MESMO carimbo nas duas UFs — e o carimbo corta em 4 casas, de proposito.
    assert carimbos["SP"] == carimbos["AC"]
    assert carimbos["SP"] == f"v06004_div_v0005_multiplicativo_global_k={k_esperado:.4f}"

    # Ja o manifesto guarda o valor EXATO: igualdade sem tolerancia, mais a prova de que ele
    # nao foi arredondado. Sem esta segunda assercao, trocar a linha por `round(k, 4)` passa.
    assert metadata["k_global"] == k_esperado
    assert metadata["k_global"] != round(metadata["k_global"], 4)
    assert metadata["k_escopo"] == "nacional_unico_27_ufs"

    # E a diferenca entre os estados sobrevive ao pipeline inteiro (1500/500 = 3).
    medianas = {
        uf: float(
            ler_particao_setores(saida, uf=uf, cod_municipio=cod)[
                "renda_per_capita_setor_2022_calibrada"
            ].median()
        )
        for uf, cod in (("SP", "3550308"), ("AC", "1200013"))
    }
    assert medianas["SP"] / medianas["AC"] == pytest.approx(3.0, abs=1e-6)


# ---------------------------------------------------------------------------------------
# Trava de destino ocupado (safra misturada)
# ---------------------------------------------------------------------------------------
#
# `escrever_particoes` sobrescreve o que TOCA e deixa intacto o que nao toca. Sem trava, um
# rerun parcial sobre um destino que ja tem dado deixa particoes da safra anterior — com o `k`
# velho — convivendo com as novas, e o `_metadata.json` e reescrito de qualquer jeito, passando
# a declarar um `k` que nao vale para todos os arquivos. Estes testes prendem a trava.


def _preparar_pipeline_fake(tmp_path: Path, monkeypatch, *, mediana_m1: float):
    """Monta os insumos em memoria e devolve um chamador de `materializar_base_geo`.

    Mesma montagem do teste do carimbo acima: os arquivos so precisam EXISTIR (ha checagem de
    caminho) e a leitura de cada um e substituida por fixture. `mediana_m1` controla o `k`, e
    e o que permite escrever duas safras DIFERENTES no mesmo destino.
    """
    from motor_expansao.pipelines import materializar_setores_censitarios_geo as mod

    malha, basico, renda, _ = _cenario_duas_ufs()
    m1 = pd.DataFrame({"renda_per_capita": [mediana_m1]})

    for nome in ("basico.csv", "renda.csv", "malha.shp"):
        (tmp_path / nome).write_text("", encoding="utf-8")
    m1_path = tmp_path / f"m1_{mediana_m1:.0f}.parquet"
    m1.to_parquet(m1_path, index=False)

    monkeypatch.setattr(
        mod, "_ler_chaves_ordenadas", lambda *_a, **_k: pd.Series(sorted(basico["cod_setor"]))
    )
    monkeypatch.setattr(mod, "carregar_basico", lambda *_a, **_k: basico)
    monkeypatch.setattr(mod, "carregar_renda", lambda *_a, **_k: renda)
    monkeypatch.setattr(
        mod,
        "carregar_malha_uf",
        lambda _shp, uf: malha[malha["uf"] == uf].reset_index(drop=True),
    )

    def executar(saida: Path, **kwargs):
        return mod.materializar_base_geo(
            basico_path=tmp_path / "basico.csv",
            renda_path=tmp_path / "renda.csv",
            shp_path=tmp_path / "malha.shp",
            output_root=saida,
            report_path=tmp_path / "relatorio.md",
            m1_reference_path=m1_path,
            **kwargs,
        )

    return mod, executar


def test_destino_ocupado_recusa_por_padrao(tmp_path: Path, monkeypatch):
    """Sem `sobrescrever`, escrever sobre particao existente e ERRO — nao merge silencioso.

    Esta e a trava principal: e ela que impede a safra misturada de nascer. O default precisa
    ser a recusa, porque o modo de falhar aqui nao quebra nada na hora — produz um artefato
    que PARECE valido e carrega dois `k` diferentes dentro.
    """
    _, executar = _preparar_pipeline_fake(tmp_path, monkeypatch, mediana_m1=987.0)
    saida = tmp_path / "out"

    executar(saida, ufs=["SP", "AC"])
    assert (saida / "uf=SP").is_dir()

    with pytest.raises(FileExistsError, match="Destino ja ocupado"):
        executar(saida, ufs=["SP", "AC"])


def test_destino_vazio_ou_inexistente_nao_precisa_de_sobrescrever(tmp_path: Path, monkeypatch):
    """A trava so dispara com particao `uf=*` presente — diretorio novo ou vazio passa direto.

    Sem esta, a trava viraria um pedagio em toda materializacao limpa e alguem passaria
    `sobrescrever=True` por habito, desarmando a protecao no caso em que ela importa.
    """
    _, executar = _preparar_pipeline_fake(tmp_path, monkeypatch, mediana_m1=987.0)

    executar(tmp_path / "nao_existe_ainda", ufs=["SP"])

    vazio = tmp_path / "vazio"
    vazio.mkdir()
    (vazio / "_metadata.json").write_text("{}", encoding="utf-8")  # arquivo solto nao conta
    executar(vazio, ufs=["SP"])
    assert (vazio / "uf=SP").is_dir()


def test_rerun_parcial_deixa_duas_safras_e_o_manifesto_admite(tmp_path: Path, monkeypatch):
    """Com `sobrescrever`, o rerun parcial e PERMITIDO — e o manifesto para de mentir.

    Reescreve so SP com um `k` diferente e prova as duas metades do contrato:
      1. AC mantem o carimbo ANTIGO (a safra misturada e real, nao teorica);
      2. o manifesto sai `escopo_execucao=parcial` com os filtros, e nao mais indistinguivel
         do manifesto de uma execucao completa.
    Sem o carimbo, quem validasse o artefato pelo `_metadata.json` aprovaria este diretorio.
    """
    _, executar_a = _preparar_pipeline_fake(tmp_path, monkeypatch, mediana_m1=987.0)
    saida = tmp_path / "out"
    meta_a = executar_a(saida, ufs=["SP", "AC"])
    assert meta_a["escopo_execucao"] == "parcial"  # 2 UFs, nao as 27
    assert meta_a["filtros"]["ufs"] == ["AC", "SP"]

    carimbo_ac_antes = ler_particao_setores(saida, uf="AC", cod_municipio="1200013")[
        "metodo_renda_setor_2022"
    ].iloc[0]

    # Segunda safra: outra mediana do M1 -> outro k -> outro carimbo.
    _, executar_b = _preparar_pipeline_fake(tmp_path, monkeypatch, mediana_m1=1600.0)
    meta_b = executar_b(saida, ufs=["SP"], sobrescrever=True)

    carimbo_sp_depois = ler_particao_setores(saida, uf="SP", cod_municipio="3550308")[
        "metodo_renda_setor_2022"
    ].iloc[0]
    carimbo_ac_depois = ler_particao_setores(saida, uf="AC", cod_municipio="1200013")[
        "metodo_renda_setor_2022"
    ].iloc[0]

    assert carimbo_ac_depois == carimbo_ac_antes, "AC nao foi tocada, entao mantem a safra 1"
    assert carimbo_sp_depois != carimbo_ac_depois, "o destino ficou com DUAS safras"

    assert meta_b["escopo_execucao"] == "parcial"
    assert meta_b["filtros"]["ufs"] == ["SP"]
    assert meta_b["k_global"] != meta_a["k_global"]


def test_sobrescrever_remove_municipio_orfao_da_uf_reescrita(tmp_path: Path, monkeypatch):
    """A limpeza e por UF: municipio que sumiu do insumo nao sobrevive na UF reescrita.

    Sem a remocao previa, o writer so sobrescreveria `cod_municipio=` que ele PRODUZ; um
    municipio da safra anterior que nao aparece mais no insumo ficaria orfao no artefato, com
    o `k` velho, e entraria em qualquer leitura por dataset.
    """
    _, executar = _preparar_pipeline_fake(tmp_path, monkeypatch, mediana_m1=987.0)
    saida = tmp_path / "out"
    executar(saida, ufs=["SP", "AC"])

    orfao = saida / "uf=SP" / "cod_municipio=3500000"
    orfao.mkdir(parents=True)
    (orfao / "part-000.parquet").write_bytes(b"safra antiga")
    intocada = saida / "uf=AC" / "cod_municipio=1200013"

    executar(saida, ufs=["SP"], sobrescrever=True)

    assert not orfao.exists(), "o orfao de SP tinha que ter sido removido"
    assert (saida / "uf=SP" / "cod_municipio=3550308").is_dir(), "SP foi reescrita"
    assert intocada.is_dir(), "AC ficou fora de `ufs`, entao nao pode ser tocada"


def test_filtro_de_municipio_nao_apaga_os_demais(tmp_path: Path, monkeypatch):
    """Com filtro de municipio a limpeza NAO roda — apagar mataria o que se quer manter.

    E o unico caso em que a safra misturada e o comportamento pedido, entao ele fica
    permitido e o manifesto registra o filtro. O aviso no log e a contrapartida.
    """
    _, executar = _preparar_pipeline_fake(tmp_path, monkeypatch, mediana_m1=987.0)
    saida = tmp_path / "out"
    executar(saida, ufs=["SP", "AC"])
    vizinho = saida / "uf=SP" / "cod_municipio=3599999"
    vizinho.mkdir(parents=True)
    (vizinho / "part-000.parquet").write_bytes(b"vizinho preservado")

    meta = executar(saida, ufs=["SP"], municipios=["3550308"], sobrescrever=True)

    assert vizinho.is_dir(), "com filtro de municipio nada pode ser apagado"
    assert meta["escopo_execucao"] == "parcial"
    assert meta["filtros"]["municipios"] == ["3550308"]
