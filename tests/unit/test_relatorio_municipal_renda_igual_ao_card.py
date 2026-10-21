"""A renda domiciliar por hexagono do Relatorio Municipal e' a MESMA do card do REP.

Ate 2026-10-16 o PDF montava a renda do hexagono por `carregar_renda_domiciliar_por_hex`, que
joga o setor censitario INTEIRO no hexagono do centro do bbox dele. O card (`_hex_dict`) le a
coluna do hexagono, agregada da malha por area. Mesmo Censo 2022, mesmo fator temporal, numeros
diferentes: em Sao Roque/SP o 87a810361ffffff saia R$ 13.261 no PDF e R$ 4.924 no card.

Hermetico: staging sintetico em tmp_path; as fronteiras de dado do preparo sao dubles.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest
from pytest import approx

import motor_expansao.dashboard.relatorio_municipal as relmun
from motor_expansao.api import service
from motor_expansao.api.settings import Settings
from motor_expansao.dashboard import constants as _const

_SERVER = Path(__file__).resolve().parents[2] / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))
import app as pilot  # noqa: E402

_COD = "3550605"


@pytest.fixture
def staging(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Uplift/moradores municipais, fator temporal 1,25 e carimbo k=1,1 sinteticos."""
    st = tmp_path / "staging"
    st.mkdir()
    pd.DataFrame(
        {
            "uf": ["SP"],
            "cod_municipio": [_COD],
            "uplift_composicao_final": [1.5],
            "uplift_confiavel": [True],
            "moradores_por_domicilio_municipio": [3.0],
        }
    ).to_parquet(st / "uplift_renda_domiciliar_municipio.parquet")
    (st / "fator_temporal_renda.json").write_text(
        json.dumps({"fator_temporal_renda": 1.25, "competencia_atual_fim": "202606"}),
        encoding="utf-8",
    )
    pd.DataFrame({"metodo_calibracao_renda": ["multiplicativo_global_k=1.1"]}).to_parquet(
        st / "censo2022_setores_calibrado.parquet"
    )
    monkeypatch.setattr(pilot, "STAGING_DIR", st)
    for attr in (
        "UPLIFT_COMPOSICAO_PATH", "UPLIFT_COMPOSICAO_SETOR_PATH", "FATOR_TEMPORAL_RENDA_PATH",
        "FATOR_TEMPORAL_RENDA", "DATA_REFERENCIA_RENDA",
    ):
        monkeypatch.setattr(_const, attr, getattr(_const, attr))
    for cache in (
        "_uplift_cache", "_uplift_uf_cache", "_moradores_cache", "_moradores_uf_cache",
        "_uplift_setor_cache", "_uplift_setor_extrapolado_cache",
    ):
        monkeypatch.setattr(_const, cache, None)
    pilot._fator_temporal_renda.cache_clear()
    pilot._k_calibracao_renda.cache_clear()
    pilot._fator_temporal_renda()  # o boot do web reaponta `constants` para o STAGING_DIR
    yield st
    pilot._fator_temporal_renda.cache_clear()
    pilot._k_calibracao_renda.cache_clear()


def _df_muni() -> pd.DataFrame:
    # h3 com calibrada nula cai, NA LINHA, na municipal (SIDRA) -- o ramo do uplift.
    return pd.DataFrame(
        {
            "hex_id": ["h1", "h2", "h3"],
            "nome_municipio": ["São Roque"] * 3,
            "uf": ["SP"] * 3,
            "cod_municipio": [_COD] * 3,
            "renda_per_capita_setor_2022_calibrada": [1500.0, 2400.0, None],
            "renda_per_capita": [1800.0, 1800.0, 1800.0],
        }
    )


def _renda_do_card(df: pd.DataFrame) -> dict[str, float]:
    """O que o card do REP mostra em "Renda domiciliar" para cada hexagono."""
    out = df.copy()
    out["renda_leitura"], out["renda_origem"] = pilot._serie_renda(out)
    fator = pilot._fator_domiciliar("SP", _COD)
    return {r["hex_id"]: pilot._renda_domiciliar_hex(r, fator) for _, r in out.iterrows()}


@pytest.fixture
def renda_entregue(staging: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict:
    """Roda o preparo unico e devolve o `renda_domiciliar_por_hex` que chega ao agregador."""
    cap: dict = {}
    monkeypatch.setattr(service, "_competitors_ultra", lambda s: (None, None))
    monkeypatch.setattr(service, "_dominio_df", lambda s: None)
    monkeypatch.setattr(relmun, "_carregar_bairros_por_hex", lambda uf, cod, d, **k: None)
    monkeypatch.setattr(relmun, "carregar_bairros_geo", lambda uf, cod, d, **k: None)
    monkeypatch.setattr(relmun, "carregar_poligono_municipio", lambda *a, **k: None)

    def _agregar(df, **k):
        cap.update(k)
        return {"uf": "SP", "nome_municipio": "São Roque", "n_hex_total": 3}

    monkeypatch.setattr(relmun, "agregar_municipio", _agregar)
    monkeypatch.setattr(relmun, "render_mapas_municipio", lambda *a, **k: {})

    class _P:
        pdf_bytes = b"%PDF-1.4"
        pdf_filename = "r.pdf"

    monkeypatch.setattr(
        relmun, "gerar_payloads_download_relatorio_municipal", lambda *a, **k: _P()
    )
    settings = Settings(
        staging_dir=staging, censo_geo_dir=tmp_path, ibge_dir=tmp_path, ultra_dir=tmp_path
    )
    service.montar_pdf_municipio(
        _df_muni(), uf="SP", nome_municipio="São Roque", settings=settings, unidade="hexagono"
    )
    return cap["renda_domiciliar_por_hex"]


def test_renda_domiciliar_do_pdf_e_a_do_card(renda_entregue: dict) -> None:
    card = _renda_do_card(_df_muni())
    assert set(renda_entregue) == set(card)
    for hex_id, valor in card.items():
        assert renda_entregue[hex_id] == approx(valor, abs=1.0), hex_id


def test_valores_ancorados_na_formula(renda_entregue: dict) -> None:
    """calibrada / k x moradores x uplift x temporal; a municipal / uplift no lugar de / k."""
    fator = 3.0 * 1.5 * 1.25
    assert renda_entregue["h1"] == approx(1500.0 / 1.1 * fator)
    assert renda_entregue["h2"] == approx(2400.0 / 1.1 * fator)
    assert renda_entregue["h3"] == approx(1800.0 / 1.5 * fator)
