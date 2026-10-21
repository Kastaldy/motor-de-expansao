"""Nucleo puro da recomendacao unica (Top 10 = 5 Mata Virgem + 5 Premium; DEC-077).

Cobre os testes 1-9 e 14 da spec da Fase 2: limites inclusivos no valor cheio (inclusive com
Float32 de origem), exclusividade dos segmentos, 5 + 5 com vaga vazia sinalizada, desempate,
determinismo sob permutacao, invariancia de recorte, nao-uso de colunas fora da regra, regua por
parametro, residual estimado (nunca exibido) e fail-closed de colunas. Tudo SINTETICO.
"""

from __future__ import annotations

import copy
import json

import h3
import numpy as np
import pandas as pd
import pytest

from motor_expansao.recomendacao import (
    CHAVES_SEM_DADO,
    ItemRecomendado,
    Recorte,
    VagaVazia,
    candidatos_ordenados,
    classificar,
    recomendar,
)
from motor_expansao.recomendacao.nucleo import (
    MOTIVO_CANDIDATOS_INSUFICIENTES,
    STATUS_COMPLETO,
    STATUS_INCOMPLETO,
)
from tests.unit.recomendacao_fixtures import (
    FONTE_ESTIMADA,
    PROCEDENCIA,
    RECORTE_BR,
    REGRA_V1,
    hexes,
    linha,
    mv,
    premium,
    regra_teste,
)


def _rec(df: pd.DataFrame, regra=REGRA_V1, recorte=RECORTE_BR):
    return recomendar(df, regra, renda=PROCEDENCIA, recorte=recorte)


def _ids(resultado) -> list[str]:
    return [v.hex_id for v in resultado.vagas if isinstance(v, ItemRecomendado)]


# ===========================================================================
# 1. Limites inclusivos no valor cheio
# ===========================================================================


@pytest.mark.parametrize("float32", [True, False])
def test_limites_inclusivos_no_valor_cheio(float32: bool) -> None:
    df = hexes(
        [
            mv("mv_no_limite", renda=4500.0, residual=2000.0),
            mv("mv_renda_abaixo", renda=4499.99, residual=5000.0),
            mv("mv_residual_abaixo", renda=9000.0, residual=1999.99),
            premium("pr_no_limite", score=50.0, populacao=10000.0),
            premium("pr_score_abaixo", score=49.96, populacao=50000.0),
            premium("pr_pop_abaixo", score=90.0, populacao=9999.99),
        ],
        float32=float32,
    )
    r = _rec(df)
    assert _ids(r.mata_virgem) == ["mv_no_limite"]
    # `mv_renda_abaixo` e `mv_residual_abaixo` sao provadamente nao-MV, mas score 30 < 50.
    assert _ids(r.premium) == ["pr_no_limite"]


def test_limites_com_float32_nullable_e_na() -> None:
    """`Float32` nullable (pd.NA) do artefato: converte a float64 exato e NA vira ausente."""
    df = hexes(
        [
            mv("a", residual=2000.0),
            mv("b", residual=None),  # residual ausente -> indeterminado, nunca MV
            premium("c", score=50.0),
        ],
        float32=False,
    )
    df["oferta_efetiva_disponivel"] = df["oferta_efetiva_disponivel"].astype("Float32")
    df["score_setor_2022_calibrado"] = df["score_setor_2022_calibrado"].astype("Float32")
    assert df["oferta_efetiva_disponivel"].isna().sum() == 1
    r = _rec(df)
    assert _ids(r.mata_virgem) == ["a"]
    assert _ids(r.premium) == ["c"]
    assert dict(r.mata_virgem.sem_dado)["sem_residual"] == 1


def test_residual_float32_exposto_em_float64_exato() -> None:
    df = hexes([mv("a", residual=2500.1)])
    item = _rec(df).mata_virgem.vagas[0]
    assert isinstance(item, ItemRecomendado)
    # O Float32 de origem, convertido sem arredondar (nao 2500.1 decimal).
    assert item.residual == float(np.float32(2500.1))


# ===========================================================================
# 2. Exclusividade
# ===========================================================================


def test_mata_virgem_com_score_alto_nunca_aparece_no_premium() -> None:
    rng = np.random.default_rng(20261021)
    for rodada in range(200):
        n = int(rng.integers(5, 40))
        linhas = []
        for i in range(n):
            linhas.append(
                linha(
                    f"r{rodada}_h{i:03d}",
                    renda=float(rng.choice([np.nan, rng.uniform(2000, 12000)])),
                    residual=float(rng.choice([np.nan, rng.uniform(0, 6000)])),
                    populacao=float(rng.choice([np.nan, rng.uniform(1000, 60000)])),
                    score=float(rng.choice([np.nan, rng.uniform(0, 100)])),
                    medido=bool(rng.random() < 0.8),
                )
            )
        # Garante MVs "perigosos": score 90 e populacao alta (passariam no Premium sozinhos).
        for j in range(int(rng.integers(1, 4))):
            linhas.append(mv(f"r{rodada}_mv{j}", score=90.0, populacao=80000.0))
        df = hexes(linhas)
        c = classificar(df, REGRA_V1, renda_disponivel=True)
        assert not (c["mv_elegivel"] & c["premium_elegivel"]).any()
        assert not (c["mv_indeterminado"] & c["premium_elegivel"]).any()
        r = _rec(df)
        mv_ids = set(c.loc[c["mv_elegivel"], "hex_id"])
        assert mv_ids.isdisjoint(_ids(r.premium))
        assert set(_ids(r.mata_virgem)).isdisjoint(_ids(r.premium))


def test_indeterminado_nunca_vira_premium() -> None:
    """Sem renda e com residual alto: talvez seja MV -> nunca Premium (contado)."""
    df = hexes([linha("x", renda=None, residual=5000.0, score=95.0, populacao=90000.0)])
    r = _rec(df)
    assert _ids(r.premium) == []
    assert dict(r.premium.sem_dado)["indeterminado_mv"] == 1
    assert dict(r.mata_virgem.sem_dado)["sem_renda"] == 1


# ===========================================================================
# 3. 5 + 5, vaga vazia, um segmento nunca completa o outro, vizinhos
# ===========================================================================


def test_cinco_mais_cinco_e_vaga_vazia_sem_completar_o_outro() -> None:
    linhas = [mv(f"mv{i}", residual=3000.0 + i) for i in range(7)]
    linhas += [premium(f"pr{i}", populacao=20000.0 + i) for i in range(2)]
    r = _rec(hexes(linhas))
    assert len(r.mata_virgem.vagas) == 5 and len(r.premium.vagas) == 5
    assert r.mata_virgem.status == STATUS_COMPLETO
    assert r.mata_virgem.n_elegiveis == 7
    assert _ids(r.mata_virgem) == ["mv6", "mv5", "mv4", "mv3", "mv2"]
    assert r.premium.status == STATUS_INCOMPLETO
    assert _ids(r.premium) == ["pr1", "pr0"]
    vazias = r.premium.vagas[2:]
    assert all(isinstance(v, VagaVazia) for v in vazias)
    assert [v.posicao for v in vazias] == [3, 4, 5]
    assert {v.motivo for v in vazias} == {MOTIVO_CANDIDATOS_INSUFICIENTES}
    # As sobras do MV (mv0, mv1) NAO completam o Premium.
    assert {"mv0", "mv1"}.isdisjoint(r.hex_ids)
    assert len(r.top10) == 10
    assert [v.posicao for v in r.mata_virgem.vagas] == [1, 2, 3, 4, 5]


def test_sobra_do_premium_nao_completa_o_mata_virgem() -> None:
    """A direcao inversa: 2 Mata Virgem + 7 Premium -> 3 vagas vazias no MV, sobra fora."""
    linhas = [mv(f"mv{i}", residual=3000.0 + i) for i in range(2)]
    linhas += [premium(f"pr{i}", populacao=20000.0 + i) for i in range(7)]
    r = _rec(hexes(linhas))
    assert _ids(r.mata_virgem) == ["mv1", "mv0"]
    assert r.mata_virgem.status == STATUS_INCOMPLETO
    vazias = r.mata_virgem.vagas[2:]
    assert all(
        isinstance(v, VagaVazia) and v.motivo == MOTIVO_CANDIDATOS_INSUFICIENTES for v in vazias
    )
    assert _ids(r.premium) == ["pr6", "pr5", "pr4", "pr3", "pr2"]
    assert {"pr0", "pr1"}.isdisjoint(r.hex_ids)


def test_recorte_vazio_sai_com_vagas_vazias() -> None:
    df = hexes([linha("a")]).iloc[0:0]
    r = _rec(df)
    assert r.n_hexes_recorte == 0
    assert all(isinstance(v, VagaVazia) for v in r.top10)
    assert r.mata_virgem.status == STATUS_INCOMPLETO


def test_dois_vizinhos_do_mesmo_bairro_ocupam_duas_vagas() -> None:
    centro = h3.latlng_to_cell(-23.5505, -46.6333, 7)
    vizinho = next(c for c in h3.grid_disk(centro, 1) if c != centro)
    r = _rec(hexes([mv(centro, residual=4000.0), mv(vizinho, residual=3900.0)]))
    assert _ids(r.mata_virgem) == [centro, vizinho]


# ===========================================================================
# 4. Desempate
# ===========================================================================


def test_desempate_mata_virgem() -> None:
    df = hexes(
        [
            mv("c", residual=2500.0, populacao=9000.0),
            mv("b", residual=2500.0, populacao=9000.0),
            mv("a", residual=2500.0, populacao=8000.0),  # pop menor perde
            mv("z", residual=2500.0001, populacao=1.0),  # maior absoluto vence (sem arredondar)
        ],
        float32=False,
    )
    assert _ids(_rec(df).mata_virgem) == ["z", "b", "c", "a"]


def test_desempate_premium() -> None:
    df = hexes(
        [
            premium("b", populacao=30000.0, score=60.0),
            premium("a", populacao=30000.0, score=60.0),
            # score maior vence no empate de populacao -- com o hex_id alfabeticamente MAIOR,
            # para que ordenar so por hex_id (ou pelo residual) de outra ordem
            premium("z", populacao=30000.0, score=70.0, residual=100.0),
            premium("m", populacao=29999.5, score=99.0),  # pop menor perde
        ]
    )
    assert _ids(_rec(df).premium) == ["z", "a", "b", "m"]


def test_empate_bit_a_bit_vindo_de_float32() -> None:
    v = float(np.float32(2345.67))
    df = hexes([mv("y", residual=v, populacao=7000.0), mv("x", residual=v, populacao=7000.0)])
    assert _ids(_rec(df).mata_virgem) == ["x", "y"]


# ===========================================================================
# 5. Determinismo e nao-mutacao
# ===========================================================================


def _frame_rico(rng: np.random.Generator, n: int = 80) -> pd.DataFrame:
    linhas = []
    for i in range(n):
        linhas.append(
            linha(
                f"h{i:03d}",
                renda=float(rng.choice([np.nan, rng.uniform(2000, 12000)])),
                residual=float(rng.choice([np.nan, rng.uniform(0, 6000)])),
                populacao=float(rng.choice([np.nan, rng.uniform(1000, 60000)])),
                score=float(rng.choice([np.nan, rng.uniform(0, 100)])),
                medido=bool(rng.random() < 0.8),
                uf=str(rng.choice(["SP", "RJ", "MG"])),
                cod_municipio=str(rng.choice(["3550308", "3304557", "3106200", "3509502"])),
                renda_origem=str(
                    rng.choice(["renda_per_capita_setor_2022_calibrada", "renda_per_capita"])
                ),
            )
        )
    return hexes(linhas)


def test_determinismo_sob_permutacao_e_entrada_intacta() -> None:
    rng = np.random.default_rng(7)
    df = _frame_rico(rng)
    original = copy.deepcopy(df)
    base = _rec(df)
    payload = base.para_payload()
    pd.testing.assert_frame_equal(df, original)
    assert base.n_hexes_recorte == len(df)
    for _ in range(50):
        perm = df.iloc[rng.permutation(len(df))]
        # indice reiniciado em metade das vezes: o resultado nao pode depender do rotulo
        if rng.random() < 0.5:
            perm = perm.reset_index(drop=True)
        copia = copy.deepcopy(perm)
        r = _rec(perm)
        assert r == base
        assert r.para_payload() == payload
        pd.testing.assert_frame_equal(perm, copia)


def test_classificar_devolve_copia() -> None:
    df = hexes([mv("a"), premium("b")])
    original = copy.deepcopy(df)
    c = classificar(df, REGRA_V1, renda_disponivel=True)
    pd.testing.assert_frame_equal(df, original)
    assert c is not df
    for col in (
        "mv_elegivel",
        "mv_indeterminado",
        "premium_elegivel",
        "mv_recomendavel",
        "premium_recomendavel",
        "residual_medido",
    ):
        assert c[col].dtype == bool
    assert c["mv_elegivel"].tolist() == [True, False]
    assert c["premium_elegivel"].tolist() == [False, True]


# ===========================================================================
# 6. Invariancia de recorte
# ===========================================================================


def test_top_do_brasil_filtrado_e_o_top_do_recorte() -> None:
    rng = np.random.default_rng(99)
    linhas = []
    municipios = {
        "SP": ["3550308", "3509502"],
        "RJ": ["3304557", "3303302"],
        "MG": ["3106200"],
    }
    i = 0
    for uf, cods in municipios.items():
        for cod in cods:
            for _ in range(int(rng.integers(3, 12))):
                linhas.append(
                    linha(
                        f"h{i:04d}",
                        renda=float(rng.uniform(3000, 12000)),
                        residual=float(rng.uniform(0, 6000)),
                        populacao=float(rng.uniform(4000, 60000)),
                        score=float(rng.uniform(20, 100)),
                        uf=uf,
                        cod_municipio=cod,
                    )
                )
                i += 1
    brasil = hexes(linhas)
    for seg in ("mata_virgem", "premium"):
        ordem_br = candidatos_ordenados(brasil, REGRA_V1, seg, renda_disponivel=True)
        for uf in municipios:
            r_uf = _rec(brasil[brasil["uf"] == uf], recorte=Recorte(nivel="uf", uf=uf))
            esperado = ordem_br.loc[ordem_br["uf"] == uf, "hex_id"].head(5).tolist()
            assert _ids(getattr(r_uf, seg)) == esperado
        for cods in municipios.values():
            for cod in cods:
                r_m = _rec(
                    brasil[brasil["cod_municipio"] == cod],
                    recorte=Recorte(nivel="municipio", cod_municipio=cod),
                )
                esperado = ordem_br.loc[ordem_br["cod_municipio"] == cod, "hex_id"].head(5)
                assert _ids(getattr(r_m, seg)) == esperado.tolist()
        # e o Top do Brasil e o comeco da ordem nacional
        assert _ids(getattr(_rec(brasil), seg)) == ordem_br["hex_id"].head(5).tolist()


# ===========================================================================
# 7. Nao uso de colunas fora da regra
# ===========================================================================


def test_colunas_fora_da_regra_nao_mudam_nada() -> None:
    rng = np.random.default_rng(3)
    df = _frame_rico(rng)
    fora = [
        "score_priorizacao",
        "concorrentes_raio",
        "consumo_concorrentes_raio",
        "viabilidade_payback_meses",
        "aluguel_m2",
        "dist_ultra_km",
        "populacao_corte_hex",
    ]
    for col in fora:
        df[col] = rng.uniform(0, 100, len(df))
    base = _rec(df)
    for _ in range(5):
        outro = df.copy()
        for col in fora:
            outro[col] = rng.uniform(-1e6, 1e6, len(df))
        r = _rec(outro)
        assert r == base
        assert r.para_payload() == base.para_payload()


# ===========================================================================
# 8. Regua por parametro
# ===========================================================================


def test_regua_v2_muda_o_resultado_e_carimba_a_versao() -> None:
    df = hexes(
        [
            mv("mv_a", renda=5000.0, residual=2500.0),
            mv("mv_b", renda=7000.0, residual=2200.0),
            premium("pr_a", populacao=12000.0, score=55.0),
            premium("pr_b", populacao=30000.0, score=65.0),
        ]
    )
    v1 = _rec(df)
    v2_regra = regra_teste(
        versao="2026-11_v2", vagas=3, renda_min=6000.0, score_min=60.0, premium_pop_min=15000.0
    )
    v2 = _rec(df, regra=v2_regra)
    assert _ids(v1.mata_virgem) == ["mv_a", "mv_b"]
    assert _ids(v2.mata_virgem) == ["mv_b"]
    assert _ids(v1.premium) == ["pr_b", "pr_a"]
    assert _ids(v2.premium) == ["pr_b"]
    assert len(v2.mata_virgem.vagas) == 3
    p = v2.para_payload()
    assert p["regra"]["versao"] == "2026-11_v2"
    assert p["regra"]["premium"]["score_min"] == 60.0
    assert v1.para_payload()["regra"]["versao"] == "2026-10_v1"


@pytest.mark.parametrize(
    ("mudanca", "linha_teste", "segmento", "na_v1", "na_v2"),
    [
        # cada caso muda UM numero da regua, com um hexagono entre o valor da v1 e o da v2
        ({"renda_min": 6000.0}, mv("h", renda=5000.0), "mata_virgem", True, False),
        ({"renda_min": 4000.0}, mv("h", renda=4200.0), "mata_virgem", False, True),
        ({"residual_min": 3000.0}, mv("h", residual=2500.0), "mata_virgem", True, False),
        ({"residual_min": 1500.0}, mv("h", residual=1800.0), "mata_virgem", False, True),
        ({"mv_pop_min": 9000.0}, mv("h", populacao=8000.0), "mata_virgem", True, False),
        ({"score_min": 60.0}, premium("h", score=55.0), "premium", True, False),
        ({"score_min": 40.0}, premium("h", score=45.0), "premium", False, True),
        ({"premium_pop_min": 15000.0}, premium("h", populacao=12000.0), "premium", True, False),
        ({"premium_pop_min": 8000.0}, premium("h", populacao=9000.0), "premium", False, True),
    ],
)
def test_cada_numero_da_regua_vem_da_regua(
    mudanca: dict, linha_teste: dict, segmento: str, na_v1: bool, na_v2: bool
) -> None:
    """Nenhum corte fixo no codigo: so o numero trocado decide o hexagono."""
    df = hexes([linha_teste])
    v1 = _ids(getattr(_rec(df), segmento))
    v2 = _ids(getattr(_rec(df, regra=regra_teste(versao="2026-11_v2", **mudanca)), segmento))
    assert v1 == (["h"] if na_v1 else [])
    assert v2 == (["h"] if na_v2 else [])


# ===========================================================================
# 9. Residual estimado
# ===========================================================================

_RESIDUAL_ESTIMADO = 7777.25


def _frame_estimado() -> pd.DataFrame:
    return hexes(
        [
            linha(
                "est",
                renda=9100.0,
                residual=_RESIDUAL_ESTIMADO,
                populacao=50000.0,
                score=90.0,
                medido=False,
            ),
            mv("medido", residual=3000.0),
        ]
    )


def test_residual_estimado_nunca_e_recomendado_nem_exibido() -> None:
    # BR v1: os dois segmentos exigem residual medido -- o estimado nao e Mata Virgem nem
    # Premium, e o numero estimado nao sai em lugar nenhum do payload.
    r = _rec(_frame_estimado())
    assert _ids(r.mata_virgem) == ["medido"]
    assert dict(r.mata_virgem.sem_dado)["residual_estimado"] == 1
    assert _ids(r.premium) == []
    assert dict(r.premium.sem_dado)["residual_estimado"] == 1
    texto = json.dumps(r.para_payload())
    assert str(_RESIDUAL_ESTIMADO) not in texto
    assert "7777" not in texto


def test_premium_sem_exigir_medido_aceita_estimado_mas_nao_exibe() -> None:
    regra = regra_teste(premium_exige_medido=False)
    r = _rec(_frame_estimado(), regra=regra)
    assert _ids(r.premium) == ["est"]
    assert dict(r.premium.sem_dado)["residual_estimado"] == 0
    item = r.premium.vagas[0]
    assert isinstance(item, ItemRecomendado)
    assert item.residual is None and item.residual_medido is False
    assert "7777" not in json.dumps(r.para_payload())


def test_mv_sem_exigir_medido_aceita_estimado_mas_nao_exibe() -> None:
    regra = regra_teste(mv_exige_medido=False)
    r = _rec(_frame_estimado(), regra=regra)
    assert _ids(r.mata_virgem) == ["est", "medido"]
    item = r.mata_virgem.vagas[0]
    assert isinstance(item, ItemRecomendado)
    assert item.residual is None and item.residual_medido is False
    assert "7777" not in json.dumps(r.para_payload())


def test_fonte_desconhecida_conta_como_estimado() -> None:
    df = hexes([mv("a")])
    df["fonte_pop_hex_base"] = None
    r = _rec(df)
    assert _ids(r.mata_virgem) == []
    assert dict(r.mata_virgem.sem_dado)["residual_estimado"] == 1


# ===========================================================================
# Contadores, populacao minima e payload
# ===========================================================================


def test_contadores_tem_todas_as_chaves_com_zero_explicito() -> None:
    r = _rec(hexes([mv("a")]))
    for seg in ("mata_virgem", "premium"):
        res = getattr(r, seg)
        assert [k for k, _ in res.sem_dado] == sorted(CHAVES_SEM_DADO[seg])
        assert set(r.para_payload()[seg]["sem_dado"]) == set(CHAVES_SEM_DADO[seg])


def test_dado_minimo_populacao() -> None:
    df = hexes(
        [
            mv("mv_sem_pop", populacao=None),
            premium("pr_sem_pop", populacao=None),
            premium("pr_pop_baixa", populacao=9000.0),
        ]
    )
    r = _rec(df)
    assert r.hex_ids == ()
    assert dict(r.mata_virgem.sem_dado)["sem_populacao"] == 1
    assert dict(r.premium.sem_dado)["sem_populacao"] == 1
    assert dict(r.premium.sem_dado)["abaixo_da_populacao_minima"] == 1


def test_item_expoe_os_campos_do_card() -> None:
    df = hexes([mv("a", renda=8000.5, residual=3000.0, populacao=12345.0, score=42.5)])
    df["cod_municipio"] = df["cod_municipio"].astype(float)  # 3550308.0 no artefato
    df["renda_origem"] = "renda_per_capita"
    item = _rec(df).mata_virgem.vagas[0]
    assert item == ItemRecomendado(
        segmento="mata_virgem",
        posicao=1,
        hex_id="a",
        renda_domiciliar=8000.5,
        renda_municipal=True,
        populacao=12345.0,
        residual=3000.0,
        residual_medido=True,
        score_censitario=42.5,
        uf="SP",
        cod_municipio="3550308",
        nome_municipio="São Paulo",
        lat=-23.5,
        lng=-46.6,
    )


def test_payload_json_safe_com_chaves_fixas() -> None:
    r = _rec(hexes([mv("a"), premium("b", lat=float("nan"))]))
    p = r.para_payload(nomes={"a": "Pinheiros"})
    assert list(p) == [
        "versao_payload",
        "regra",
        "recorte",
        "n_hexes_recorte",
        "renda",
        "mata_virgem",
        "premium",
        "rotulos",
    ]
    json.dumps(p, allow_nan=False)  # NaN -> None
    vaga_a, vaga_vazia = p["mata_virgem"]["vagas"][0], p["mata_virgem"]["vagas"][1]
    assert list(vaga_a) == list(vaga_vazia)
    assert vaga_a["nome_regiao"] == "Pinheiros"
    assert vaga_vazia["vazia"] is True and vaga_vazia["rotulo_motivo"]
    assert p["premium"]["vagas"][0]["lat"] is None
    assert p["premium"]["vagas"][0]["nome_regiao"] is None
    assert p["mata_virgem"]["rotulo"] == "Mata Virgem"
    assert p["rotulos"]["status"]["indisponivel"] == "Indisponível"
    assert p["renda"] == {
        "disponivel": True,
        "k": 1.2,
        "carimbo": "multiplicativo_global_k=1.2",
        "fatores_versao": "teste_v1",
        "pais": "BR",
    }


def test_payload_leva_floats_crus_sem_arredondar() -> None:
    df = hexes(
        [
            mv(
                "a",
                renda=8000.123456789,
                residual=3000.987654321,
                populacao=12345.678,
                score=42.123,
                lat=-23.55051234567,
                lng=-46.63331234567,
            )
        ],
        float32=False,
    )
    vaga = _rec(df).para_payload()["mata_virgem"]["vagas"][0]
    assert vaga["renda_domiciliar"] == 8000.123456789
    assert vaga["residual"] == 3000.987654321
    assert vaga["populacao"] == 12345.678
    assert vaga["score_censitario"] == 42.123
    assert (vaga["lat"], vaga["lng"]) == (-23.55051234567, -46.63331234567)


def test_segmento_do_hex() -> None:
    r = _rec(hexes([mv("a"), premium("b"), linha("c")]))
    assert r.segmento_do_hex("a") == "mata_virgem"
    assert r.segmento_do_hex("b") == "premium"
    assert r.segmento_do_hex("c") is None
    assert r.hex_ids == ("a", "b")


def test_populacao_minima_do_mv_quando_declarada_barra_o_mv() -> None:
    """Piso de populacao do MV (BR v1 nao tem): barra o MV e e contado."""
    regra = regra_teste(mv_pop_min=10000.0)
    df = hexes([mv("pequeno", populacao=6000.0, score=80.0, renda=9000.0, residual=2500.0)])
    r = _rec(df, regra=regra)
    assert _ids(r.mata_virgem) == []
    assert dict(r.mata_virgem.sem_dado)["abaixo_da_populacao_minima"] == 1
    # 6.000 < 10.000 do Premium: nao passaria no Premium pelos proprios numeros.
    assert dict(r.premium.sem_dado)["indeterminado_mv"] == 0


def test_populacao_abaixo_do_piso_do_mv_nao_prova_nao_mv() -> None:
    """Pseudo-codigo da spec, literal: o piso do MV NAO entra em `prova_nao_mv`.

    Populacao entre o piso do Premium (10 mil) e o do MV (20 mil), renda e residual altos e
    medidos: nao e MV (populacao baixa), mas tambem nao e PROVADAMENTE nao-MV -> indeterminado,
    nunca Premium. Ler o piso como prova seria outra regra (decisao do usuario + DEC-077).
    """
    regra = regra_teste(mv_pop_min=20000.0)
    df = hexes([mv("h", renda=9000.0, residual=2500.0, populacao=15000.0, score=80.0)])
    c = classificar(df, regra, renda_disponivel=True)
    assert c["mv_indeterminado"].tolist() == [True]
    assert c["premium_elegivel"].tolist() == [False]
    r = _rec(df, regra=regra)
    assert r.hex_ids == ()
    assert dict(r.mata_virgem.sem_dado)["abaixo_da_populacao_minima"] == 1
    assert dict(r.premium.sem_dado)["indeterminado_mv"] == 1


def test_sem_populacao_conta_mesmo_com_piso_do_mv_declarado() -> None:
    """Com `mata_virgem.populacao_min`, o MV sem populacao continua em `sem_populacao`."""
    df = hexes([mv("h", populacao=None)])
    for regra in (REGRA_V1, regra_teste(mv_pop_min=20000.0)):
        sem_dado = dict(_rec(df, regra=regra).mata_virgem.sem_dado)
        assert sem_dado["sem_populacao"] == 1
        assert sum(sem_dado.values()) == 1


def test_sem_score_conta_so_quem_tem_populacao() -> None:
    """`sem_score`: provadamente nao-MV, populacao no piso do Premium, sem score. Fora da malha
    censitaria (sem score E sem populacao) nao e "faltou o score"."""
    df = hexes(
        [
            premium("sem_score", score=None, populacao=30000.0),
            premium("fora_da_malha", score=None, populacao=None),
            premium("sem_score_pop_baixa", score=None, populacao=9000.0),
        ]
    )
    sem_dado = dict(_rec(df).premium.sem_dado)
    assert sem_dado["sem_score"] == 1
    assert sem_dado["sem_populacao"] == 0
    assert sem_dado["abaixo_da_populacao_minima"] == 0


@pytest.mark.parametrize("coluna", ["pop_total_setor_2022", "oferta_efetiva_disponivel"])
@pytest.mark.parametrize("sinal", [1.0, -1.0])
def test_infinito_e_valor_ausente(coluna: str, sinal: float) -> None:
    """+-inf nunca e "valor conhecido": nao classifica, nao derruba e nao sai sem numero."""
    df = hexes([mv("mv_ok"), premium("pr_ok"), mv("inf_mv"), premium("inf_pr")], float32=False)
    df.loc[df["hex_id"].str.startswith("inf"), coluna] = sinal * float("inf")
    r = _rec(df)
    assert _ids(r.mata_virgem) == ["mv_ok"]
    if coluna == "pop_total_setor_2022":
        assert _ids(r.premium) == ["pr_ok"]  # sem o dado minimo
    else:
        # residual desconhecido, mas a renda baixa ja prova que nao e MV: segue Premium, como
        # com um residual NaN -- e sem numero de residual na tela.
        assert _ids(r.premium) == ["inf_pr", "pr_ok"]
        assert r.premium.vagas[0].residual is None  # type: ignore[union-attr]
    json.dumps(r.para_payload(), allow_nan=False)


def test_renda_infinita_e_ausente() -> None:
    df = hexes([mv("h", renda=float("inf"))])
    r = _rec(df)
    assert r.hex_ids == ()
    assert dict(r.mata_virgem.sem_dado)["sem_renda"] == 1


def test_cod_municipio_nulo_float32_e_texto_sai_none() -> None:
    df = hexes([mv("a"), mv("b", residual=2900.0), mv("c", residual=2800.0)])
    df["cod_municipio"] = pd.Series([np.float32("nan"), "nan", "<NA>"], dtype=object)
    r = _rec(df)
    assert [v.cod_municipio for v in r.mata_virgem.vagas[:3]] == [None, None, None]


def test_candidatos_ordenados_nao_expoe_residual_estimado() -> None:
    v1 = candidatos_ordenados(_frame_estimado(), REGRA_V1, "premium", renda_disponivel=True)
    assert v1.empty
    regra_pr = regra_teste(premium_exige_medido=False)
    r_pr = candidatos_ordenados(_frame_estimado(), regra_pr, "premium", renda_disponivel=True)
    assert r_pr["hex_id"].tolist() == ["est"]
    assert r_pr["oferta_efetiva_disponivel"].isna().all()
    assert r_pr["residual_medido"].tolist() == [False]
    regra = regra_teste(mv_exige_medido=False)
    r_mv = candidatos_ordenados(_frame_estimado(), regra, "mata_virgem", renda_disponivel=True)
    assert r_mv["hex_id"].tolist() == ["est", "medido"]
    assert np.isnan(r_mv["oferta_efetiva_disponivel"].iat[0])
    assert r_mv["oferta_efetiva_disponivel"].iat[1] == 3000.0
    assert r_mv["residual_medido"].tolist() == [False, True]


# ===========================================================================
# 14. Fail-closed de colunas, hex_id repetido, categoricos
# ===========================================================================


@pytest.mark.parametrize(
    "coluna",
    [
        "hex_id",
        "oferta_efetiva_disponivel",
        "score_setor_2022_calibrado",
        "pop_total_setor_2022",
        "fonte_pop_hex_base",
        "renda_domiciliar",
    ],
)
def test_coluna_obrigatoria_ausente_nomeada(coluna: str) -> None:
    df = hexes([mv("a")]).drop(columns=[coluna])
    with pytest.raises(ValueError, match=coluna):
        _rec(df)


def test_sem_renda_a_coluna_de_renda_nao_e_exigida() -> None:
    df = hexes([mv("a")]).drop(columns=["renda_domiciliar"])
    r = recomendar(df, REGRA_V1, renda=None, recorte=RECORTE_BR)
    assert r.mata_virgem.status == "indisponivel"


def test_hex_id_repetido_entre_candidatos() -> None:
    df = hexes([mv("a"), premium("a")])
    with pytest.raises(ValueError, match="hex_id repetido"):
        _rec(df)


def test_hex_id_repetido_fora_dos_candidatos_nao_importa() -> None:
    df = hexes([mv("a"), linha("x"), linha("x")])
    assert _ids(_rec(df).mata_virgem) == ["a"]


def test_colunas_categoricas_funcionam() -> None:
    df = hexes([mv("a"), premium("b"), linha("c", medido=False)])
    esperado = _rec(df)
    cat = df.copy()
    for col in ("hex_id", "fonte_pop_hex_base", "uf", "nome_municipio"):
        cat[col] = cat[col].astype("category")
    cat["cod_municipio"] = cat["cod_municipio"].astype(float).astype("category")
    cat["oferta_efetiva_disponivel"] = cat["oferta_efetiva_disponivel"].astype("category")
    assert _rec(cat) == esperado


def test_recorte_invalido() -> None:
    with pytest.raises(ValueError, match="nivel"):
        Recorte(nivel="bairro")


def test_estimado_fonte_categorica() -> None:
    df = hexes([mv("a", medido=False)])
    df["fonte_pop_hex_base"] = pd.Categorical([FONTE_ESTIMADA])
    assert _ids(_rec(df).mata_virgem) == []
