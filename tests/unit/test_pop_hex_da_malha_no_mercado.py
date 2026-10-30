"""Populacao do hexagono pela MALHA no mercado (`censo_2022_malha`; emenda da DEC-077).

O defeito: na orla e na beira de rio nenhum centroide de setor cai dentro do hexagono, a
`pop_total_setor_2022` do traco censitario fica nula e o residual saia do proxy municipal
(`populacao_proxy / total_hex_municipio`, a media da cidade). O enriquecido ja' carregava a
`pop_malha` desses hexagonos, e o mercado nao.

Tres grupos:
- o preenchimento (puro): so' preenche, nao toca quem ja' tem populacao, e' idempotente;
- o rotulo e a cadeia de `calcular` (pop_hex_base, SAM, residual) e a recomendacao, que
  passa a aceitar o rotulo novo como MEDIDO;
- o contrato com artefato (pula sem os parquets): nenhum hexagono com populacao no
  enriquecido fica com populacao nula no mercado.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from motor_expansao.pipelines import calcular_colunas_mercado as mercado_module
from motor_expansao.pipelines.agregar_censo_hex_da_malha import (
    COL_POP_DA_MALHA,
    FONTE_POP_MALHA,
    preencher_populacao_da_malha,
)
from motor_expansao.pipelines.calcular_colunas_mercado import calcular
from motor_expansao.recomendacao.nucleo import FONTES_MEDIDAS, classificar
from tests.unit.recomendacao_fixtures import FONTE_ESTIMADA, REGRA_V1, hexes, mv, premium

# ---------------------------------------------------------------------------
# Preenchimento (puro)
# ---------------------------------------------------------------------------


@pytest.fixture
def malha(tmp_path: Path) -> Path:
    caminho = tmp_path / "malha.parquet"
    pd.DataFrame(
        {
            "hex_id": ["centroide", "orla", "agua", "fora_do_censo"],
            "pop_malha": [999.0, 4321.5, 0.0, 77.0],
        }
    ).to_parquet(caminho, index=False)
    return caminho


def _censo() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "hex_id": ["centroide", "orla", "agua", "sem_malha"],
            "pop_total_setor_2022": [1234.25, None, None, None],
        }
    )


def test_preenche_so_a_populacao_nula(malha):
    out = preencher_populacao_da_malha(_censo(), malha_path=malha)
    pop = out.set_index("hex_id")["pop_total_setor_2022"]
    marca = out.set_index("hex_id")[COL_POP_DA_MALHA]

    # Quem ja' tem populacao pelo centroide fica IDENTICO, mesmo com a malha dizendo outra coisa.
    assert pop["centroide"] == 1234.25
    assert not marca["centroide"]
    # Nula + malha com gente -> valor da malha, marcado.
    assert pop["orla"] == 4321.5
    assert marca["orla"]
    # Malha com zero habitante nao preenche (seria trocar "sem dado" por zero).
    assert np.isnan(pop["agua"])
    assert not marca["agua"]
    # Sem linha na malha: fica nula.
    assert np.isnan(pop["sem_malha"])
    assert not marca["sem_malha"]


def test_nao_cria_nem_remove_linha(malha):
    entrada = _censo()
    out = preencher_populacao_da_malha(entrada, malha_path=malha)
    assert out["hex_id"].tolist() == entrada["hex_id"].tolist()


def test_nao_muta_a_entrada(malha):
    entrada = _censo()
    copia = entrada.copy()
    preencher_populacao_da_malha(entrada, malha_path=malha)
    pd.testing.assert_frame_equal(entrada, copia)


def test_idempotente_quando_le_o_proprio_artefato(malha):
    """O mercado le o PROPRIO artefato: na 2a passada a populacao preenchida ja' esta' la'."""
    primeira = preencher_populacao_da_malha(_censo(), malha_path=malha)
    artefato = primeira.drop(columns=[COL_POP_DA_MALHA]).assign(
        fonte_pop_hex_base=np.where(primeira[COL_POP_DA_MALHA], FONTE_POP_MALHA, "censo_2022_setor")
    )
    segunda = preencher_populacao_da_malha(artefato, malha_path=malha)
    pd.testing.assert_series_equal(
        segunda["pop_total_setor_2022"], primeira["pop_total_setor_2022"]
    )
    # E o rotulo de malha continua de malha (sem a reabertura viraria "centroide").
    assert segunda[COL_POP_DA_MALHA].tolist() == primeira[COL_POP_DA_MALHA].tolist()


def test_releitura_pega_a_malha_nova(malha, tmp_path):
    """Valor antigo da malha no artefato nao sobrevive a uma malha regenerada."""
    artefato = _censo().assign(fonte_pop_hex_base="censo_2022_setor")
    artefato.loc[artefato.hex_id == "orla", ["pop_total_setor_2022", "fonte_pop_hex_base"]] = [
        10.0,
        FONTE_POP_MALHA,
    ]
    out = preencher_populacao_da_malha(artefato, malha_path=malha)
    assert out.set_index("hex_id").loc["orla", "pop_total_setor_2022"] == 4321.5


def test_sem_malha_a_populacao_sai_intacta(tmp_path):
    out = preencher_populacao_da_malha(_censo(), malha_path=tmp_path / "nao_existe.parquet")
    pd.testing.assert_series_equal(out["pop_total_setor_2022"], _censo()["pop_total_setor_2022"])
    assert not out[COL_POP_DA_MALHA].any()


# ---------------------------------------------------------------------------
# Rotulo e cadeia de `calcular`
# ---------------------------------------------------------------------------


def _base_mercado(pop, marca):
    n = len(pop)
    return pd.DataFrame(
        {
            "hex_id": [f"h{i}" for i in range(n)],
            "flag_censo_elegivel": [True] * n,
            "pop_total_setor_2022": pop,
            "renda_per_capita_setor_2022_calibrada": [2000.0] * n,
            "populacao_proxy": [500_000.0] * n,
            "pop_total": [500_000.0] * n,
            "faixa_oportunidade": ["alta"] * n,
            "renda_per_capita": [2000.0] * n,
            "score_priorizacao": [70.0] * n,
            "flag_hex_hibrido_elegivel": [False] * n,
            "score_expansao_hibrido": [None] * n,
            "flag_viavel": [True] * n,
            "top_municipio": [True] * n,
            "flag_white_space_2km": [True] * n,
            "flag_canibalizacao_ultra_1km": [False] * n,
            "n_concorrentes_mapeados_2km": [0] * n,
            "oferta_efetiva_mapeada_2km": [0.0] * n,
            "gap_competitivo_2km": [1.0] * n,
            "pressao_concorrencial_score_2km": [0.0] * n,
            "oferta_efetiva_1km_area": [0.0] * n,
            "gap_competitivo_1km_area": [1.0] * n,
            "total_hex_municipio": [100] * n,
            COL_POP_DA_MALHA: marca,
        }
    )


def test_calcular_rotula_a_populacao_da_malha():
    df = _base_mercado([8000.0, 9000.0, None], [False, True, False])
    out = calcular(df.copy()).set_index("hex_id")

    assert out.loc["h0", "fonte_pop_hex_base"] == "censo_2022_setor"
    assert out.loc["h1", "fonte_pop_hex_base"] == FONTE_POP_MALHA
    assert out.loc["h2", "fonte_pop_hex_base"] == "m1_municipal_proxy_per_hex"
    # A populacao-base do residual e' a do lugar, nao a media da cidade (500.000 / 100).
    assert out.loc["h1", "pop_hex_base"] == pytest.approx(9000.0)
    assert out.loc["h2", "pop_hex_base"] == pytest.approx(5000.0)


def test_calcular_nao_deixa_a_coluna_transitoria_no_artefato():
    out = calcular(_base_mercado([8000.0, 9000.0], [False, True]).copy())
    assert COL_POP_DA_MALHA not in out.columns


def test_calcular_sem_a_coluna_transitoria_reproduz_o_rotulo_antigo():
    """Frame que nao passou pelo preenchimento (teste antigo, chamada direta): nada muda."""
    df = _base_mercado([8000.0, None], [False, False]).drop(columns=[COL_POP_DA_MALHA])
    out = calcular(df.copy()).set_index("hex_id")
    assert out.loc["h0", "fonte_pop_hex_base"] == "censo_2022_setor"
    assert out.loc["h1", "fonte_pop_hex_base"] == "m1_municipal_proxy_per_hex"


def test_residual_da_malha_igual_ao_de_um_hex_medido_com_a_mesma_populacao():
    """Mesma populacao, mesma oferta: o residual nao depende de por qual regua ela foi medida."""
    out = calcular(_base_mercado([9000.0, 9000.0], [False, True]).copy()).set_index("hex_id")
    for col in ("pop_hex_base", "tam_fitness_potencial", "sam_fitness_potencial",
                "oferta_efetiva_disponivel", "flag_sam", "populacao_corte_hex"):
        assert out.loc["h0", col] == out.loc["h1", col], col


def test_main_aborta_sem_a_malha(tmp_path, monkeypatch):
    """Sem a malha o mercado voltaria a media da cidade em silencio nos hexagonos de orla."""
    monkeypatch.setattr(mercado_module, "MALHA_PATH", tmp_path / "nao_existe.parquet")
    with pytest.raises(FileNotFoundError, match="censo2022_hex_da_malha|nao_existe"):
        mercado_module.main()


# ---------------------------------------------------------------------------
# Recomendacao: o rotulo novo e' MEDIDO
# ---------------------------------------------------------------------------


def test_rotulo_da_malha_e_medido_na_recomendacao():
    assert FONTE_POP_MALHA in FONTES_MEDIDAS
    assert "censo_2022_setor" in FONTES_MEDIDAS
    assert FONTE_ESTIMADA not in FONTES_MEDIDAS

    linhas = hexes(
        [
            mv("mv_setor"),
            mv("mv_malha", fonte_pop_hex_base=FONTE_POP_MALHA),
            mv("mv_estimado", medido=False),
            premium("pr_malha", fonte_pop_hex_base=FONTE_POP_MALHA),
            premium("pr_estimado", medido=False),
        ]
    )
    cl = classificar(linhas, REGRA_V1, renda_disponivel=True).set_index("hex_id")
    assert cl.loc["mv_setor", "mv_recomendavel"]
    assert cl.loc["mv_malha", "residual_medido"] and cl.loc["mv_malha", "mv_recomendavel"]
    assert cl.loc["pr_malha", "residual_medido"] and cl.loc["pr_malha", "premium_recomendavel"]
    assert not cl.loc["pr_estimado", "premium_recomendavel"]
    assert not cl.loc["mv_estimado", "mv_recomendavel"]


# ---------------------------------------------------------------------------
# Contrato com artefato
# ---------------------------------------------------------------------------

MERCADO_PATH = Path("data/staging/hexagonos_mercado_mapeado.parquet")
ENRIQUECIDO_DIR = Path("data/outputs/hexagonos_dashboard_enriquecido")

com_artefato = pytest.mark.skipif(
    not MERCADO_PATH.exists() or not any(ENRIQUECIDO_DIR.glob("uf=*/*.parquet")),
    reason="artefatos de mercado/enriquecido nao materializados neste checkout",
)


@com_artefato
def test_populacao_do_enriquecido_chega_ao_mercado():
    """Nenhum hexagono com populacao no enriquecido pode ficar com populacao nula no mercado.

    Chave a chave, e com o VALOR igual: e' a mesma populacao que a tela mostra e o residual usa.
    """
    import pyarrow.dataset as ds

    enr = ds.dataset(str(ENRIQUECIDO_DIR), partitioning="hive").to_table(
        columns=["hex_id", "pop_total_setor_2022"]
    ).to_pandas()
    mer = pd.read_parquet(MERCADO_PATH, columns=["hex_id", "pop_total_setor_2022", "fonte_pop_hex_base"])
    j = enr.merge(mer, on="hex_id", how="inner", suffixes=("_enr", "_mer"))
    com_pop = j["pop_total_setor_2022_enr"].gt(0)
    faltam = j[com_pop & j["pop_total_setor_2022_mer"].isna()]
    assert faltam.empty, f"{len(faltam)} hexagonos com populacao no enriquecido e nula no mercado"
    estimados = j[com_pop & ~j["fonte_pop_hex_base"].isin(FONTES_MEDIDAS)]
    assert estimados.empty, f"{len(estimados)} hexagonos com populacao do Censo e residual estimado"
    diferenca = (j.loc[com_pop, "pop_total_setor_2022_enr"] - j.loc[com_pop, "pop_total_setor_2022_mer"]).abs()
    assert diferenca.max() < 1e-6, f"maior divergencia de populacao: {diferenca.max()}"
