"""Hexágonos órfãos da Fase A (BLK-JOINUF-01, mecanismo 2).

O DEFEITO. A Fase A rodou em 2026-05-15 e nunca mais. A base H3 cresceu DEPOIS, em três
eventos de critério geométrico de borda: +5.305 (centroide, 2026-05-26), +474 (DEC-002) e
+4.107 (DEC-003) = **exatamente 9.886**, batendo por UF em 27/27. Esses hexágonos não têm
LINHA nenhuma no traço censitário — não é join ruim, é ausência — e nenhuma regra de
reclassificação alcança linha ausente.

Duas consequências, e cada uma tem um teste aqui:

1. Sem linha no traço, eles não recebem `cod_municipio` (que só flui por ali). São as
   ÚNICAS 9.886 linhas do artefato sem código, contra ZERO nulos nas outras 1.532.645 —
   e por isso ficavam fora de qualquer regra municipal, inclusive a nota do mecanismo 1.
   O parquet estrutural sempre teve o código para os 1.542.531.
2. Sem dado censitário, não há sinal — e sem sinal não há promoção possível. A malha da
   DEC-045 já cobre 5.612 deles (6,25 milhões de habitantes), incluindo 11 de 11 em
   Fortaleza e 345 de 391 no Rio, que são os casos que o operador reportou.
"""

from __future__ import annotations

import pandas as pd

from motor_expansao.dashboard.data import enrich_dashboard_data
from motor_expansao.pipelines.agregar_censo_hex_da_malha import (
    COL_CARIMBO,
    COL_RENDA,
    COL_SCORE,
    FONTE_ORFAO_ADMITIDO,
    admitir_orfaos_da_malha,
)


def _malha(tmp_path, linhas: list[dict]):
    caminho = tmp_path / "malha.parquet"
    pd.DataFrame(linhas).to_parquet(caminho)
    return caminho


# ---------------------------------------------------------------------------
# Admissão do órfão
# ---------------------------------------------------------------------------


def test_admite_hexagono_que_a_malha_cobre_e_o_traco_nao_tem(tmp_path) -> None:
    caminho = _malha(
        tmp_path,
        [
            {"hex_id": "ja_existe", "uf": "CE", "pop_malha": 10.0, "renda_malha": 900.0, "score_malha": 30.0},
            {"hex_id": "orfao", "uf": "CE", "pop_malha": 75342.0, "renda_malha": 1500.0, "score_malha": 55.0},
        ],
    )
    censo = pd.DataFrame({"hex_id": ["ja_existe"], COL_SCORE: [10.0]})

    out = admitir_orfaos_da_malha(censo, malha_path=caminho)

    assert len(out) == 2
    novo = out[out["hex_id"].eq("orfao")].iloc[0]
    assert novo[COL_SCORE] == 55.0
    assert novo[COL_RENDA] == 1500.0
    assert novo["pop_total_setor_2022"] == 75342.0
    assert novo["fonte_renda_censo_hex"] == FONTE_ORFAO_ADMITIDO
    # A linha que ja existia nao pode ser tocada -- esta funcao SO acrescenta.
    assert out[out["hex_id"].eq("ja_existe")].iloc[0][COL_SCORE] == 10.0


def test_nao_admite_hexagono_sem_score_na_malha(tmp_path) -> None:
    """Admitir linha vazia trocaria "sem dado" por "dado nulo" -- pior, some do radar."""
    caminho = _malha(
        tmp_path,
        [{"hex_id": "vazio", "uf": "AM", "pop_malha": 0.0, "renda_malha": None, "score_malha": None}],
    )
    out = admitir_orfaos_da_malha(pd.DataFrame({"hex_id": ["outro"]}), malha_path=caminho)
    assert list(out["hex_id"]) == ["outro"]


def test_admitido_nao_recebe_qualidade_join_uf(tmp_path) -> None:
    """Eles genuinamente NAO tem medida de join -- inventar uma seria mentir no artefato.

    Quem os promove e a nota de MUNICIPIO, pela mesma regra de todo mundo.
    """
    caminho = _malha(
        tmp_path,
        [{"hex_id": "orfao", "uf": "RJ", "pop_malha": 5.0, "renda_malha": 800.0, "score_malha": 12.0}],
    )
    censo = pd.DataFrame({"hex_id": ["x"], "qualidade_join_uf": ["A"]})
    out = admitir_orfaos_da_malha(censo, malha_path=caminho)
    assert pd.isna(out[out["hex_id"].eq("orfao")].iloc[0]["qualidade_join_uf"])


def test_admitido_herda_o_carimbo_de_calibracao(tmp_path) -> None:
    """Sem o carimbo do `k`, a renda do admitido ficaria em escala indefinida."""
    caminho = _malha(
        tmp_path,
        [{"hex_id": "orfao", "uf": "SP", "pop_malha": 5.0, "renda_malha": 800.0, "score_malha": 12.0}],
    )
    censo = pd.DataFrame({"hex_id": ["x"], COL_CARIMBO: ["multiplicativo_global_k=1.2334632197"]})
    out = admitir_orfaos_da_malha(censo, malha_path=caminho)
    assert out[out["hex_id"].eq("orfao")].iloc[0][COL_CARIMBO] == "multiplicativo_global_k=1.2334632197"


def test_sem_malha_no_disco_e_no_op() -> None:
    censo = pd.DataFrame({"hex_id": ["a", "b"]})
    out = admitir_orfaos_da_malha(censo, malha_path="nao/existe.parquet")
    assert len(out) == 2


# ---------------------------------------------------------------------------
# cod_municipio pelo estrutural
# ---------------------------------------------------------------------------


def _base(hex_id: str) -> dict:
    return {
        "hex_id": hex_id,
        "lat": -22.9,
        "lng": -43.2,
        "uf": "RJ",
        "cidade": "Rio de Janeiro",
        "regiao": "SE",
        "score_priorizacao": 60.0,
        "hex_score_estrutural": 55.0,
        "ajuste_executivo": 5.0,
        "faixa_oportunidade": "alta",
        "flag_viavel": True,
        "flag_prioridade": False,
        "rank_brasil": 1,
        "rank_uf": 1,
        "rank_cidade": 1,
        "renda_per_capita": 3000.0,
        "populacao_proxy": 5000.0,
    }


def test_orfao_ganha_cod_municipio_do_estrutural() -> None:
    """O código sempre existiu no estrutural; o artefato é que só o lia do censo."""
    enriquecido = enrich_dashboard_data(
        pd.DataFrame([_base("orfao")]),
        estrutural_pop_df=pd.DataFrame(
            {"hex_id": ["orfao"], "pop_total": [6748000.0], "cod_municipio": ["3304557"]}
        ),
    )
    assert enriquecido["cod_municipio"].iloc[0] == "3304557"


def test_estrutural_nao_sobrescreve_o_codigo_que_o_censo_ja_trouxe() -> None:
    """Preenche LACUNA. O censo segue sendo a fonte primária das 1.532.645 já preenchidas."""
    enriquecido = enrich_dashboard_data(
        pd.DataFrame([_base("normal")]),
        censo_df=pd.DataFrame({"hex_id": ["normal"], "cod_municipio": ["3304557"]}),
        estrutural_pop_df=pd.DataFrame(
            {"hex_id": ["normal"], "pop_total": [1.0], "cod_municipio": ["9999999"]}
        ),
    )
    assert enriquecido["cod_municipio"].iloc[0] == "3304557"


def test_orfao_com_municipio_bom_vira_granular_de_ponta_a_ponta() -> None:
    """O caso Fortaleza: sem linha no traço, mas o município é classe A.

    Fecha a cadeia inteira do mecanismo 2 -- código pelo estrutural, sinal pela malha e
    promoção pela nota municipal do mecanismo 1, sem régua especial para órfão.
    """
    enriquecido = enrich_dashboard_data(
        pd.DataFrame([_base("orfao")]),
        # o que `admitir_orfaos_da_malha` teria criado no traço
        censo_df=pd.DataFrame(
            {"hex_id": ["orfao"], "score_setor_2022_calibrado": [40.0], "pop_total_setor_2022": [75342.0]}
        ),
        estrutural_pop_df=pd.DataFrame(
            {"hex_id": ["orfao"], "pop_total": [2428708.0], "cod_municipio": ["2304400"]}
        ),
        notas_municipio=pd.DataFrame(
            {
                "cod_municipio": ["2304400"],
                "classe_join_municipio": ["A"],
                "taxa_match_municipio": [0.971],
                "n_setores_municipio": [4408],
            }
        ),
    )
    assert enriquecido["confianca_geografica"].iloc[0] == "granular"
    # E a população exibida deixa de ser a do município inteiro.
    assert enriquecido["populacao_corte_hex"].iloc[0] == 75342.0
