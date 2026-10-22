"""Renda da recomendacao unica: `k_da_malha`, `renda_domiciliar_por_linha` e `montar_recomendacao`.

Testes 10-12 da spec da Fase 2:
  - sem o carimbo k da malha o Top 10 INTEIRO fica indisponivel, e `montar_recomendacao` nunca
    chama `k_calibracao_renda` nem usa o fallback 1,0239;
  - `k_da_malha` e estrito (arquivo/coluna ausente, carimbo ilegivel, dois carimbos, k fora da
    faixa -> None) e le o k em precisao cheia;
  - paridade BIT A BIT `renda_domiciliar_por_linha` x `renda_domiciliar_por_hex` para o mesmo k,
    nas duas origens de renda (setor calibrada e SIDRA), em mais de um municipio, com fator per
    capita DIFERENTE do domiciliar, UF com fator proprio (PE/MS, como na PNAD 2025), municipio
    fora da tabela de uplift (mediana da UF) e os DOIS ramos da E3 (#475): colunas da malha no
    frame e anexadas do artefato da malha no staging. Se so um lado mudar, a paridade quebra.

Staging SINTETICO em tmp_path (tabela municipal de uplift/moradores + carimbo da malha) e versao
de fatores sintetica (`fixar_fatores`), como nos testes da renda.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from motor_expansao.recomendacao import (
    ItemRecomendado,
    Recorte,
    VagaVazia,
    montar_recomendacao,
)
from motor_expansao.recomendacao import montar as montar_mod
from motor_expansao.recomendacao.nucleo import (
    MOTIVO_CANDIDATOS_INSUFICIENTES,
    MOTIVO_RENDA_INDISPONIVEL,
    STATUS_INDISPONIVEL,
    linhas_que_precisam_de_renda,
)
from motor_expansao.renda import hex as renda_hex
from motor_expansao.renda.hex import (
    CENSO_HEX_STAGING_PARQUET,
    CENSO_MALHA_PARQUET,
    COL_RENDA_DOM_MALHA,
    COL_RENDA_PC_MALHA,
    K_CALIBRACAO_FALLBACK,
    KDaMalha,
    k_da_malha,
    renda_domiciliar_por_hex,
    renda_domiciliar_por_linha,
)
from tests.unit.recomendacao_fixtures import REGRA_V1, linha
from tests.unit.renda_fixtures import apontar_staging_renda, fixar_fatores

#: Fator temporal DOMICILIAR nacional da versao sintetica; o per capita e outro de proposito
#: (1,34 x 1,25, como 1,3401 x 1,2470 na PNAD 2025): trocar um pelo outro tem de quebrar teste.
FATOR = 1.25
FATOR_PC = 1.34
K = 1.2345678901234  # precisao cheia de proposito
CARIMBO = f"multiplicativo_global_k={K!r}"

#: Fatores das UFs com excecao aprovada (domiciliar = valores da PNAD 2025), servidos por
#: `fator_por_uf`, que troca o `fator` do modulo da renda -- o nome que `fator_hex` e o ramo da
#: malha usam, nas duas pontas da paridade.
FATOR_DOM_UF = {"PE": 1.3461, "MS": 1.1607}
FATOR_PC_UF = {"PE": 1.4012, "MS": 1.2011}

_TABELA_MUNICIPIOS = pd.DataFrame(
    {
        "uf": ["SP", "SP", "RJ", "PE", "MS"],
        "cod_municipio": ["3550308", "3509502", "3304557", "2611606", "5002704"],
        "uplift_composicao_final": [1.5, 1.2, 1.8, 1.4, 1.3],
        "uplift_confiavel": [True, True, True, True, True],
        "moradores_por_domicilio_municipio": [3.2, 2.5, 2.0, 3.0, 2.8],
    }
)
#: Municipio de SP FORA da tabela: uplift e moradores pela mediana da UF (1,35 e 2,85).
COD_FORA_DA_TABELA = "3500105"


def _carimbar_malha(staging: Path, *carimbos: object) -> None:
    pd.DataFrame({"metodo_calibracao_renda_malha": list(carimbos)}).to_parquet(
        staging / CENSO_MALHA_PARQUET
    )


@pytest.fixture
def staging(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Staging com tabela municipal + fator 1,25 + carimbo da malha k=K."""
    base = tmp_path / "staging"
    base.mkdir()
    _TABELA_MUNICIPIOS.to_parquet(base / "uplift_renda_domiciliar_municipio.parquet")
    fatores = fixar_fatores(monkeypatch, tmp_path, per_capita=FATOR_PC, domiciliar=FATOR)
    monkeypatch.setattr(montar_mod, "carregar_fatores", lambda *_a, **_k: fatores)
    _carimbar_malha(base, CARIMBO, CARIMBO)
    apontar_staging_renda(monkeypatch, base)
    monkeypatch.delenv("MOTOR_DATA_DIR", raising=False)
    return base


@pytest.fixture
def fator_por_uf(staging: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """`staging` + fator temporal POR UF (PE/MS com fator proprio; o resto, o nacional)."""

    def _fator(uf: object, tipo: str) -> float:
        if tipo == "domiciliar":
            return FATOR_DOM_UF.get(str(uf), FATOR)
        return FATOR_PC_UF.get(str(uf), FATOR_PC)

    monkeypatch.setattr(renda_hex, "fator", _fator)
    return staging


# ===========================================================================
# 11. k_da_malha
# ===========================================================================


def test_k_da_malha_valido_em_precisao_cheia(staging: Path) -> None:
    k = k_da_malha(staging)
    assert k == KDaMalha(valor=K, carimbo=CARIMBO)
    assert k is not None and k.valor == K


@pytest.mark.parametrize("k", [0.5, 3.0])
def test_k_da_malha_bordas_da_faixa_sao_validas(tmp_path: Path, k: float) -> None:
    """FAIXA_K e INCLUSIVA (o mesmo criterio de `k_calibracao_renda`)."""
    _carimbar_malha(tmp_path, f"multiplicativo_global_k={k}")
    assert k_da_malha(tmp_path) == KDaMalha(valor=k, carimbo=f"multiplicativo_global_k={k}")


def test_k_da_malha_arquivo_ausente(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        assert k_da_malha(tmp_path) is None
    assert "k da malha indisponivel" in caplog.text


def test_k_da_malha_ignora_o_staging_hex(tmp_path: Path) -> None:
    """So a malha vale: o carimbo do staging hex (outro k) nunca e lido."""
    pd.DataFrame({"metodo_calibracao_renda": ["multiplicativo_global_k=1.0239"]}).to_parquet(
        tmp_path / CENSO_HEX_STAGING_PARQUET
    )
    assert k_da_malha(tmp_path) is None


def test_k_da_malha_coluna_ausente(tmp_path: Path) -> None:
    pd.DataFrame({"outra": ["multiplicativo_global_k=1.2"]}).to_parquet(
        tmp_path / CENSO_MALHA_PARQUET
    )
    assert k_da_malha(tmp_path) is None


@pytest.mark.parametrize(
    "carimbos",
    [
        ("sem_k_nenhum",),
        ("multiplicativo_global_k=abc",),
        (None, None),
        ("multiplicativo_global_k=1.2", "multiplicativo_global_k=1.3"),  # dois carimbos
        ("multiplicativo_global_k=3.5",),  # fora da faixa
        ("multiplicativo_global_k=0.1",),
    ],
)
def test_k_da_malha_recusa(tmp_path: Path, carimbos: tuple) -> None:
    _carimbar_malha(tmp_path, *carimbos)
    assert k_da_malha(tmp_path) is None


def test_k_da_malha_parquet_corrompido(tmp_path: Path) -> None:
    (tmp_path / CENSO_MALHA_PARQUET).write_bytes(b"nao e parquet")
    assert k_da_malha(tmp_path) is None


# ===========================================================================
# 12. Paridade de renda
# ===========================================================================


def _frame_renda() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "hex_id": ["a1", "a2", "a3", "b1", "b2", "c1", "c2", "p1", "p2", "m1", "f1"],
            "uf": ["SP", "SP", "SP", "SP", "SP", "RJ", "RJ", "PE", "PE", "MS", "SP"],
            "cod_municipio": [
                "3550308",
                "3550308",
                "3550308",
                "3509502",
                "3509502",
                "3304557",
                "3304557",
                "2611606",
                "2611606",
                "5002704",
                COD_FORA_DA_TABELA,
            ],
            "renda_per_capita_setor_2022_calibrada": [
                1500.0,
                np.nan,
                2333.33,
                1000.0,
                np.nan,
                np.nan,
                4100.7,
                1234.5,
                np.nan,
                987.65,
                1111.0,
            ],
            "renda_per_capita": [
                1400.0,
                1777.77,
                1400.0,
                900.0,
                950.5,
                1700.0,
                np.nan,
                800.0,
                1333.3,
                700.0,
                1000.0,
            ],
        }
    )


#: Renda de 2022 da MALHA (E3) por hexagono (domiciliar, per capita): so a leitura SETORIAL a usa.
_MALHA = {
    "a1": (5123.45, 1601.08),  # setorial com malha -> ramo da malha
    "a2": (6000.0, 1900.0),  # leitura SIDRA: a malha e ignorada (formula municipal)
    "p1": (4321.0, 1440.33),  # UF com fator proprio no ramo da malha
    "m1": (np.nan, np.nan),  # setorial SEM valor de malha -> formula municipal
}


def _com_malha(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out[COL_RENDA_DOM_MALHA] = [_MALHA.get(h, (np.nan, np.nan))[0] for h in out["hex_id"]]
    out[COL_RENDA_PC_MALHA] = [_MALHA.get(h, (np.nan, np.nan))[1] for h in out["hex_id"]]
    return out


def _gravar_artefato_malha(staging: Path, df: pd.DataFrame) -> None:
    """Artefato da malha com o carimbo k E as colunas da E3 (como o pipeline pos-E3 grava)."""
    malha = _com_malha(df)[["hex_id", COL_RENDA_DOM_MALHA, COL_RENDA_PC_MALHA]]
    malha.assign(metodo_calibracao_renda_malha=CARIMBO).to_parquet(staging / CENSO_MALHA_PARQUET)


def _conferir_paridade(df: pd.DataFrame, staging: Path) -> pd.Series:
    """Paridade bit a bit por municipio; devolve a renda por linha indexada por `hex_id`."""
    k = k_da_malha(staging)
    assert k is not None
    # `renda_domiciliar_por_hex` le o k pelo `k_calibracao_renda` (malha primeiro): o MESMO k.
    assert renda_hex.k_calibracao_renda(staging) == k.valor
    por_linha = renda_domiciliar_por_linha(df, k=k.valor, staging_dir=staging)
    assert por_linha.dtype == "float64"
    assert por_linha.index.equals(df.index)
    origens_vistas = set()
    for (uf, cod), grupo in df.groupby(["uf", "cod_municipio"], sort=True):
        por_hex = renda_domiciliar_por_hex(grupo, uf=uf, cod_municipio=cod, staging_dir=staging)
        assert set(por_hex) == set(grupo["hex_id"])
        for idx, hex_id in grupo["hex_id"].items():
            assert por_linha.loc[idx] == por_hex[hex_id], hex_id  # bit a bit, sem approx
        _v, origem = renda_hex.serie_renda(grupo)
        origens_vistas |= set(origem)
    assert origens_vistas == {"renda_per_capita_setor_2022_calibrada", "renda_per_capita"}
    return pd.Series(por_linha.to_numpy(), index=df["hex_id"].to_numpy())


def test_paridade_bit_a_bit_com_renda_domiciliar_por_hex(fator_por_uf: Path) -> None:
    r = _conferir_paridade(_frame_renda(), fator_por_uf)
    # A UF de CADA linha chega ao fator: PE e MS com o proprio, nao o nacional 1,25.
    assert r["p1"] == 1234.5 / K * ((3.0 * 1.4) * FATOR_DOM_UF["PE"])
    assert r["m1"] == 987.65 / K * ((2.8 * 1.3) * FATOR_DOM_UF["MS"])
    # O fator DOMICILIAR (1,25), nunca o per capita (1,34).
    assert r["a1"] == 1500.0 / K * ((3.2 * 1.5) * FATOR)
    # SIDRA: desfaz o uplift do municipio antes do fator do hex.
    assert r["p2"] == 1333.3 / 1.4 * ((3.0 * 1.4) * FATOR_DOM_UF["PE"])
    # Municipio fora da tabela: uplift e moradores pela mediana da UF (SP: 1,35 e 2,85).
    assert r["f1"] == pytest.approx(1111.0 / K * (2.85 * 1.35 * FATOR), rel=1e-12)


def test_paridade_com_as_colunas_da_malha_no_frame(fator_por_uf: Path) -> None:
    """E3: frame que JA traz as colunas da malha (particao enriquecida pos-E3)."""
    r = _conferir_paridade(_com_malha(_frame_renda()), fator_por_uf)
    assert r["a1"] == 5123.45 * FATOR  # malha x F_dom(uf), sem moradores/uplift/k de novo
    assert r["p1"] == 4321.0 * FATOR_DOM_UF["PE"]
    assert r["a2"] == 1777.77 / 1.5 * ((3.2 * 1.5) * FATOR)  # SIDRA ignora a malha
    assert r["m1"] == 987.65 / K * ((2.8 * 1.3) * FATOR_DOM_UF["MS"])  # malha sem valor


def test_paridade_com_as_colunas_da_malha_anexadas_do_staging(fator_por_uf: Path) -> None:
    """E3: frame SEM as colunas e artefato da malha COM elas -> as duas pontas as anexam."""
    df = _frame_renda()
    _gravar_artefato_malha(fator_por_uf, df)
    r = _conferir_paridade(df, fator_por_uf)
    assert r["a1"] == 5123.45 * FATOR
    assert r["p1"] == 4321.0 * FATOR_DOM_UF["PE"]


def test_renda_por_linha_contrato(staging: Path) -> None:
    df = _frame_renda()
    df.loc[0, "cod_municipio"] = None  # sem municipio -> NaN (contrato do card)
    df.loc[3, "renda_per_capita_setor_2022_calibrada"] = np.nan
    df.loc[3, "renda_per_capita"] = np.nan  # sem renda nenhuma -> NaN
    df.loc[1, "cod_municipio"] = "nan"  # nulo ESCRITO (astype(str)) tambem e nulo
    df.loc[2, "uf"] = None  # sem UF: o fator e da UF -> NaN, nunca o nacional em silencio
    r = renda_domiciliar_por_linha(df, k=K)
    assert np.isnan(r.loc[0]) and np.isnan(r.loc[3])
    assert np.isnan(r.loc[1]) and np.isnan(r.loc[2])
    # 3304557: calibrada / k x (moradores 2.0 x uplift 1.8) x 1.25
    assert r.loc[6] == 4100.7 / K * (2.0 * 1.8 * FATOR)
    # cod_municipio float (3550308.0) e normalizado
    df2 = _frame_renda()
    df2["cod_municipio"] = df2["cod_municipio"].astype(float)
    pd.testing.assert_series_equal(
        renda_domiciliar_por_linha(df2, k=K), renda_domiciliar_por_linha(_frame_renda(), k=K)
    )


def test_renda_por_linha_nunca_le_o_k(staging: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _proibido(*_a, **_k):
        raise AssertionError("k_calibracao_renda nao pode ser chamado")

    monkeypatch.setattr(renda_hex, "k_calibracao_renda", _proibido)
    renda_domiciliar_por_linha(_frame_renda(), k=K)


@pytest.mark.parametrize("k", [0.0, -1.0, float("nan"), float("inf"), True])
def test_renda_por_linha_recusa_k_invalido(k: object) -> None:
    with pytest.raises(ValueError, match="k invalido"):
        renda_domiciliar_por_linha(_frame_renda(), k=k)  # type: ignore[arg-type]


# ===========================================================================
# 10. montar_recomendacao: sem k -> Top 10 indisponivel; com k -> renda do card
# ===========================================================================


def _recorte_df() -> pd.DataFrame:
    linhas = [
        # MV em SP: calibrada 6000/k x 6.0 -> ~29 mil (renda alta)
        linha("mv1", residual=3000.0, populacao=9000.0),
        # renda abaixo de 4.500: 500/k x 6.0 ~ 2.430 -> provadamente nao-MV -> Premium
        linha("pr1", residual=2500.0, populacao=30000.0, score=80.0),
    ]
    df = pd.DataFrame(linhas).drop(columns=["renda_domiciliar"])
    df["renda_per_capita_setor_2022_calibrada"] = [6000.0, 500.0]
    df["renda_per_capita"] = [np.nan, np.nan]
    df["oferta_efetiva_disponivel"] = df["oferta_efetiva_disponivel"].astype("float32")
    df["score_setor_2022_calibrado"] = df["score_setor_2022_calibrado"].astype("float32")
    return df


def _proibir_k_legado(monkeypatch: pytest.MonkeyPatch) -> None:
    def _proibido(*_a, **_k):
        raise AssertionError("montar_recomendacao nao pode chamar k_calibracao_renda")

    monkeypatch.setattr(renda_hex, "k_calibracao_renda", _proibido)


def test_sem_k_o_top10_inteiro_fica_indisponivel(
    staging: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (staging / CENSO_MALHA_PARQUET).unlink()
    # Mesmo com o carimbo do staging hex presente: ele nao vale para a recomendacao.
    pd.DataFrame({"metodo_calibracao_renda": ["multiplicativo_global_k=1.0239"]}).to_parquet(
        staging / CENSO_HEX_STAGING_PARQUET
    )
    _proibir_k_legado(monkeypatch)
    df = _recorte_df()
    r = montar_recomendacao(
        df, recorte=Recorte(nivel="uf", uf="SP"), staging_dir=staging, regra=REGRA_V1
    )
    assert r is not None
    assert r.renda is None
    for seg in (r.mata_virgem, r.premium):
        assert seg.status == STATUS_INDISPONIVEL
        assert len(seg.vagas) == 5
        assert all(
            isinstance(v, VagaVazia) and v.motivo == MOTIVO_RENDA_INDISPONIVEL for v in seg.vagas
        )
    p = r.para_payload()
    assert p["renda"]["disponivel"] is False
    assert p["mata_virgem"]["rotulo_status"] == "Indisponível"


def test_com_k_usa_a_renda_do_card_com_o_k_da_malha(
    staging: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _proibir_k_legado(monkeypatch)
    df = _recorte_df()
    original = df.copy(deep=True)
    r = montar_recomendacao(
        df, recorte=Recorte(nivel="uf", uf="SP"), staging_dir=staging, regra=REGRA_V1
    )
    assert r is not None
    pd.testing.assert_frame_equal(df, original)
    assert r.renda is not None
    assert (r.renda.k, r.renda.carimbo) == (K, f"multiplicativo_global_k={K!r}")
    assert r.renda.fatores_versao == "2026-10_teste_v1"
    assert r.hex_ids == ("mv1", "pr1")
    item = r.mata_virgem.vagas[0]
    assert isinstance(item, ItemRecomendado)
    esperado = 6000.0 / K * (3.2 * 1.5 * FATOR)
    assert item.renda_domiciliar == esperado
    # nunca o fallback 1,0239
    assert item.renda_domiciliar != 6000.0 / K_CALIBRACAO_FALLBACK * (3.2 * 1.5 * FATOR)
    assert item.renda_municipal is False


def test_montar_calcula_renda_so_onde_importa(
    staging: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vistos: list[list[str]] = []
    original = renda_domiciliar_por_linha

    def _espiao(df: pd.DataFrame, **kw):
        vistos.append(sorted(df["hex_id"]))
        return original(df, **kw)

    monkeypatch.setattr(montar_mod, "renda_domiciliar_por_linha", _espiao)
    df = _recorte_df()
    base = df.iloc[[0]]
    extra = pd.concat(
        [
            # residual e score baixos: a renda nao decide nada
            base.assign(
                hex_id="irrelevante",
                oferta_efetiva_disponivel=np.float32(10.0),
                score_setor_2022_calibrado=np.float32(10.0),
            ),
            # residual baixo, mas Premium possivel (score e populacao no corte): precisa da renda
            base.assign(
                hex_id="so_pelo_premium",
                oferta_efetiva_disponivel=np.float32(500.0),
                score_setor_2022_calibrado=np.float32(50.0),
                pop_total_setor_2022=10000.0,
            ),
            # residual baixo, score alto, populacao abaixo do piso do Premium: nao precisa
            base.assign(
                hex_id="pop_abaixo",
                oferta_efetiva_disponivel=np.float32(500.0),
                score_setor_2022_calibrado=np.float32(90.0),
                pop_total_setor_2022=9999.99,
            ),
        ]
    )
    df = pd.concat([df, extra], ignore_index=True)
    montar_recomendacao(df, recorte=Recorte(nivel="brasil"), staging_dir=staging, regra=REGRA_V1)
    assert vistos == [["mv1", "pr1", "so_pelo_premium"]]


def test_linhas_que_precisam_de_renda_nos_cortes() -> None:
    """Os cortes do pre-filtro sao os da regua, INCLUSIVOS no valor cheio (Float32 de origem)."""
    df = pd.DataFrame(
        [
            linha("res_no_corte", residual=2000.0, score=10.0, populacao=1.0),
            linha("res_abaixo", residual=1999.99, score=10.0, populacao=1.0),
            linha("res_nulo", residual=None, score=10.0, populacao=1.0),
            linha("pr_no_corte", residual=10.0, score=50.0, populacao=10000.0),
            linha("pr_score_abaixo", residual=10.0, score=49.96, populacao=10000.0),
            linha("pr_pop_abaixo", residual=10.0, score=90.0, populacao=9999.99),
            linha("pr_sem_pop", residual=10.0, score=90.0, populacao=None),
        ]
    )
    df["oferta_efetiva_disponivel"] = df["oferta_efetiva_disponivel"].astype("float32")
    df["score_setor_2022_calibrado"] = df["score_setor_2022_calibrado"].astype("float32")
    m = linhas_que_precisam_de_renda(df, REGRA_V1)
    assert df.loc[m, "hex_id"].tolist() == ["res_no_corte", "res_nulo", "pr_no_corte"]


def _recorte_rico(rng: np.random.Generator, n: int = 120) -> pd.DataFrame:
    cods = {"SP": ["3550308", "3509502"], "RJ": ["3304557"], "PE": ["2611606"]}
    linhas = []
    for i in range(n):
        uf = str(rng.choice(list(cods)))
        linhas.append(
            linha(
                f"h{i:03d}",
                residual=float(rng.choice([np.nan, rng.uniform(0, 5000)])),
                populacao=float(rng.choice([np.nan, rng.uniform(1000, 60000)])),
                score=float(rng.choice([np.nan, rng.uniform(0, 100)])),
                medido=bool(rng.random() < 0.8),
                uf=uf,
                cod_municipio=str(rng.choice(cods[uf])),
            )
        )
    df = pd.DataFrame(linhas).drop(columns=["renda_domiciliar"])
    df["renda_per_capita_setor_2022_calibrada"] = [
        float(rng.choice([np.nan, rng.uniform(200, 4000)])) for _ in range(n)
    ]
    df["renda_per_capita"] = [float(rng.choice([np.nan, rng.uniform(200, 4000)])) for _ in range(n)]
    return df


def test_mascara_da_renda_nao_muda_o_resultado(
    fator_por_uf: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Calcular a renda so onde importa da o MESMO Top 10 que calcula-la em toda linha."""
    for semente in range(5):
        df = _recorte_rico(np.random.default_rng(semente))
        com_mascara = montar_recomendacao(
            df, recorte=Recorte(nivel="brasil"), staging_dir=fator_por_uf, regra=REGRA_V1
        )
        with monkeypatch.context() as mp:
            mp.setattr(
                montar_mod,
                "linhas_que_precisam_de_renda",
                lambda d, _r: pd.Series(True, index=d.index),
            )
            todas = montar_recomendacao(
                df, recorte=Recorte(nivel="brasil"), staging_dir=fator_por_uf, regra=REGRA_V1
            )
        assert com_mascara is not None and todas is not None
        assert com_mascara.hex_ids, "recorte sem candidato nao prova nada"
        assert com_mascara == todas
        assert com_mascara.para_payload() == todas.para_payload()


def test_montar_premium_com_residual_baixo_e_renda_sidra(staging: Path) -> None:
    """O Premium tipico (residual < 2.000) sai COM renda, e a origem SIDRA chega ao item."""
    df = pd.DataFrame(
        [
            linha("pr_res_baixo", residual=500.0, populacao=40000.0, score=80.0),
            linha("pr_sidra", residual=800.0, populacao=30000.0, score=70.0),
            linha("mv_sidra", residual=3000.0, populacao=9000.0),
        ]
    ).drop(columns=["renda_domiciliar"])
    df["renda_per_capita_setor_2022_calibrada"] = [700.0, np.nan, np.nan]
    df["renda_per_capita"] = [np.nan, 1500.0, 9000.0]
    r = montar_recomendacao(
        df, recorte=Recorte(nivel="brasil"), staging_dir=staging, regra=REGRA_V1
    )
    assert r is not None
    pr = [v for v in r.premium.vagas if isinstance(v, ItemRecomendado)]
    assert [v.hex_id for v in pr] == ["pr_res_baixo", "pr_sidra"]
    assert pr[0].renda_domiciliar == 700.0 / K * ((3.2 * 1.5) * FATOR)
    assert pr[0].renda_municipal is False
    assert pr[1].renda_domiciliar == 1500.0 / 1.5 * ((3.2 * 1.5) * FATOR)
    assert pr[1].renda_municipal is True
    mv = r.mata_virgem.vagas[0]
    assert isinstance(mv, ItemRecomendado) and mv.hex_id == "mv_sidra"
    assert mv.renda_domiciliar == 9000.0 / 1.5 * ((3.2 * 1.5) * FATOR)
    assert mv.renda_municipal is True
    assert r.para_payload()["mata_virgem"]["vagas"][0]["renda_municipal"] is True


def test_montar_residual_no_corte_exato_e_mata_virgem(staging: Path) -> None:
    """Residual 2.000,00 com score abaixo de 50: so o ramo do MV pede a renda, e ele entra."""
    df = _recorte_df()
    df["oferta_efetiva_disponivel"] = np.array([2000.0, 2500.0], dtype="float32")
    df["score_setor_2022_calibrado"] = np.array([30.0, 80.0], dtype="float32")
    r = montar_recomendacao(
        df, recorte=Recorte(nivel="brasil"), staging_dir=staging, regra=REGRA_V1
    )
    assert r is not None
    assert [v.hex_id for v in r.mata_virgem.vagas if isinstance(v, ItemRecomendado)] == ["mv1"]


def test_montar_uf_de_cada_linha_decide_o_mata_virgem(fator_por_uf: Path) -> None:
    """PE e MS com fator proprio: o hexagono de Recife entra (R$ 4.602 com 1,3461; seria R$ 4.274
    com o nacional) e o de Campo Grande fica fora (R$ 4.397 com 1,1607; seria R$ 4.736)."""
    df = pd.DataFrame(
        [
            linha("pe_mv", residual=3000.0, populacao=9000.0, uf="PE", cod_municipio="2611606"),
            linha("ms_quase", residual=3500.0, populacao=9000.0, uf="MS", cod_municipio="5002704"),
        ]
    ).drop(columns=["renda_domiciliar"])
    df["renda_per_capita_setor_2022_calibrada"] = [1005.0, 1285.0]
    df["renda_per_capita"] = [np.nan, np.nan]
    r = montar_recomendacao(
        df, recorte=Recorte(nivel="brasil"), staging_dir=fator_por_uf, regra=REGRA_V1
    )
    assert r is not None
    item = r.mata_virgem.vagas[0]
    assert isinstance(item, ItemRecomendado) and item.hex_id == "pe_mv"
    assert item.renda_domiciliar == 1005.0 / K * ((3.0 * 1.4) * FATOR_DOM_UF["PE"])
    # com o fator nacional os dois trocariam de lado
    assert 1005.0 / K * ((3.0 * 1.4) * FATOR) < 4500.0 <= 1285.0 / K * ((2.8 * 1.3) * FATOR)
    vaga2 = r.mata_virgem.vagas[1]
    assert isinstance(vaga2, VagaVazia) and vaga2.motivo == MOTIVO_CANDIDATOS_INSUFICIENTES
    assert "ms_quase" not in r.hex_ids


def test_montar_pais_sem_regua_devolve_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(montar_mod, "carregar_regra", lambda *_a, **_k: None)
    assert montar_recomendacao(_recorte_df(), recorte=Recorte(nivel="brasil")) is None


@pytest.mark.parametrize(
    "coluna",
    [
        "fonte_pop_hex_base",
        "uf",
        "cod_municipio",
        "renda_per_capita_setor_2022_calibrada",
        "renda_per_capita",
    ],
)
def test_montar_coluna_ausente_falha_antes_do_k(staging: Path, coluna: str) -> None:
    """`uf`/`cod_municipio` e as colunas de leitura da renda sao obrigatorias na montagem: sem
    `uf`, PE/MS cairiam em silencio no fator nacional (a particao lida direto do arquivo nao traz
    a chave hive `uf`); sem as colunas de renda (frame PROJETADO), o Mata Virgem sairia vazio com
    o motivo falso "nao ha outra regiao", ou mudaria com a renda toda municipal."""
    df = _recorte_df().drop(columns=[coluna])
    with pytest.raises(ValueError, match=coluna):
        montar_recomendacao(
            df, recorte=Recorte(nivel="brasil"), staging_dir=staging, regra=REGRA_V1
        )


def test_montar_indice_repetido(staging: Path) -> None:
    df = _recorte_df()
    df.index = [7, 7]
    r = montar_recomendacao(
        df, recorte=Recorte(nivel="brasil"), staging_dir=staging, regra=REGRA_V1
    )
    assert r is not None and r.hex_ids == ("mv1", "pr1")
