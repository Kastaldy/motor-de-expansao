"""Testes do spike deck.gl (BLK-REV-08) — SPIKE DESCARTÁVEL.

Cobre (D6 do handoff), tudo determinístico e SEM browser/rede/CDN:
  1. gerar_recorte_spike_json retorna dict com uf/version/timestamp/view/hexagons.
  2. Todo hex tem `h` (hex_id) não-vazio; `bm1`/`br` inteiros em 0..9.
  3. Cap respeitado: com >limit linhas corta à effective_limit; mode_stress não corta.
  4. Zero PII e zero geometria (nem lat/lng por hex) em qualquer hex.
  5. Determinismo: mesmos inputs → hexagons/view byte-idênticos.
  6. _build_deckgl_html contém CDN/deck.gl/H3HexagonLayer/dados; sem PII.
  7. is_spike_enabled respeita env var ULTRA_SPIKE_DECKGL e session_state.

READ-ONLY M1: nenhum artefato oficial é criado, lido como fixture ou alterado.
Sem rede: nada acessa CDN nem URLs externas.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pandas as pd
import pytest

_FAKE_UF = "TT"  # sigla inexistente — nunca colide com UF real


def _make_fake_df(n: int = 10) -> pd.DataFrame:
    """DataFrame sintético com as colunas lidas pelo recorte do spike."""
    rows = []
    for i in range(n):
        rows.append(
            {
                "hex_id": f"87aaaaaa{i:07x}",
                "lat": -23.55 + i * 0.01,
                "lng": -46.63 + i * 0.01,
                "score_priorizacao": 50.0 + i,
                "score_oportunidade_residual": 40.0 + i,
                "pop_total": 10_000 + i * 1_000,
                "populacao_proxy": 10_000 + i * 1_000,
                "oferta_efetiva_disponivel": 2_000 + i * 100,
            }
        )
    return pd.DataFrame(rows)


def _write_parquet(tmp_path: Path, df: pd.DataFrame, uf: str = _FAKE_UF) -> Path:
    uf_dir = tmp_path / f"uf={uf}"
    uf_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(uf_dir / "parte-0.parquet", index=False)
    return uf_dir


def _call(
    tmp_path: Path, n: int = 10, uf: str = _FAKE_UF, **kwargs: Any
) -> dict[str, Any]:
    """Grava parquet sintético e chama gerar_recorte_spike_json com cache isolado."""
    from motor_expansao.dashboard.ui_spike_deckgl import gerar_recorte_spike_json

    _write_parquet(tmp_path, _make_fake_df(n), uf=uf)
    cache_dir = tmp_path / "cache" / "ui_spike_deckgl"
    with patch(
        "motor_expansao.dashboard.ui_spike_deckgl._CACHE_DIR", cache_dir
    ):
        return gerar_recorte_spike_json(uf, enriquecido_dir=tmp_path, **kwargs)


# ──────────────────────────────────────────────────────────────
# 1. Estrutura do dict
# ──────────────────────────────────────────────────────────────
class TestEstrutura:
    def test_campos_obrigatorios(self, tmp_path: Path) -> None:
        result = _call(tmp_path)
        assert result["uf"] == _FAKE_UF
        assert result["version"] == "ui_spike_deckgl_v1"
        assert "timestamp" in result
        assert "view" in result
        assert isinstance(result["view"], dict)
        for k in ("longitude", "latitude", "zoom"):
            assert k in result["view"]
        assert isinstance(result["hexagons"], list)
        assert len(result["hexagons"]) == 10

    def test_fallback_uf_inexistente(self, tmp_path: Path) -> None:
        from motor_expansao.dashboard.ui_spike_deckgl import gerar_recorte_spike_json

        cache_dir = tmp_path / "cache" / "ui_spike_deckgl"
        with patch(
            "motor_expansao.dashboard.ui_spike_deckgl._CACHE_DIR", cache_dir
        ), pytest.raises(FileNotFoundError):
            gerar_recorte_spike_json("ZZ", enriquecido_dir=tmp_path)

    def test_cache_salvo(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "cache" / "ui_spike_deckgl"
        _write_parquet(tmp_path, _make_fake_df(5))
        from motor_expansao.dashboard.ui_spike_deckgl import gerar_recorte_spike_json

        with patch(
            "motor_expansao.dashboard.ui_spike_deckgl._CACHE_DIR", cache_dir
        ):
            gerar_recorte_spike_json(_FAKE_UF, enriquecido_dir=tmp_path)
        cache_file = cache_dir / f"{_FAKE_UF}.json"
        assert cache_file.exists()
        loaded = json.loads(cache_file.read_text(encoding="utf-8"))
        assert loaded["uf"] == _FAKE_UF


# ──────────────────────────────────────────────────────────────
# 2. Chaves curtas e bandas em 0..9
# ──────────────────────────────────────────────────────────────
class TestPayload:
    def test_chaves_curtas_e_bandas(self, tmp_path: Path) -> None:
        result = _call(tmp_path)
        for hexd in result["hexagons"]:
            assert set(hexd.keys()) == {"h", "bm1", "br", "s", "sr", "p", "o"}
            assert isinstance(hexd["h"], str) and hexd["h"], "hex_id vazio"
            assert isinstance(hexd["bm1"], int) and 0 <= hexd["bm1"] <= 9
            assert isinstance(hexd["br"], int) and 0 <= hexd["br"] <= 9

    def test_banda_extremos(self, tmp_path: Path) -> None:
        """Scores 0, 10, 100 e >100 caem em faixas válidas (0 e 9)."""
        from motor_expansao.dashboard.ui_spike_deckgl import _band_index_vec

        s = pd.Series([0.0, 5.0, 10.0, 55.0, 100.0, 150.0, float("nan")])
        idx = _band_index_vec(s)
        assert list(idx) == [0, 0, 0, 5, 9, 9, 0]

    def test_sort_por_score_desc(self, tmp_path: Path) -> None:
        result = _call(tmp_path, n=10)
        scores = [h["s"] for h in result["hexagons"] if h["s"] is not None]
        assert scores == sorted(scores, reverse=True)


# ──────────────────────────────────────────────────────────────
# 3. Cap respeitado + mode_stress
# ──────────────────────────────────────────────────────────────
class TestCap:
    def test_cap_corta_a_limit(self, tmp_path: Path) -> None:
        """Com limit pequeno e n>limit (mas n<=35000), corta a limit."""
        result = _call(tmp_path, n=20, limit=5)
        assert len(result["hexagons"]) == 5

    def test_cap_nao_corta_abaixo_do_limit(self, tmp_path: Path) -> None:
        result = _call(tmp_path, n=8, limit=35000)
        assert len(result["hexagons"]) == 8

    def test_mode_stress_nao_corta(self, tmp_path: Path) -> None:
        result = _call(tmp_path, n=20, limit=5, mode_stress=True)
        assert len(result["hexagons"]) == 20

    def test_cap_large_quando_supera_map_point_limit(self, tmp_path: Path) -> None:
        """len>MAP_POINT_LIMIT → cap = MAP_POINT_LIMIT_LARGE (18000), ignora limit alto."""
        from motor_expansao.dashboard import ui_spike_deckgl as mod

        # Evita gerar 35001 linhas: rebaixa os limiares por patch.
        with patch.object(mod, "MAP_POINT_LIMIT", 10), patch.object(
            mod, "MAP_POINT_LIMIT_LARGE", 4
        ):
            result = _call(tmp_path, n=20, limit=35000)
        assert len(result["hexagons"]) == 4


# ──────────────────────────────────────────────────────────────
# 4. Zero PII e zero geometria
# ──────────────────────────────────────────────────────────────
class TestSemPiiGeometria:
    def test_sem_pii_nem_geometria(self, tmp_path: Path) -> None:
        df = _make_fake_df(5)
        df["endereco"] = "Rua Fake, 123"
        df["nome_propriedade"] = "Loja XYZ"
        df["owner"] = "João Silva"
        df["geometry_wkb"] = b"\x00\x01"
        _write_parquet(tmp_path, df)

        from motor_expansao.dashboard.ui_spike_deckgl import (
            _GEOMETRY_FORBIDDEN,
            _PII_FORBIDDEN,
            gerar_recorte_spike_json,
        )

        cache_dir = tmp_path / "cache" / "ui_spike_deckgl"
        with patch(
            "motor_expansao.dashboard.ui_spike_deckgl._CACHE_DIR", cache_dir
        ):
            result = gerar_recorte_spike_json(_FAKE_UF, enriquecido_dir=tmp_path)

        # Nenhuma chave proibida em qualquer hex.
        proibidas = _PII_FORBIDDEN | _GEOMETRY_FORBIDDEN
        for hexd in result["hexagons"]:
            assert not (set(hexd.keys()) & proibidas)
            assert "lat" not in hexd and "lng" not in hexd

        # E não vaza no JSON serializado.
        blob = json.dumps(result, ensure_ascii=False)
        for col in _PII_FORBIDDEN:
            assert col not in blob

    def test_sem_nan_infinito(self, tmp_path: Path) -> None:
        result = _call(tmp_path)
        blob = json.dumps(result, separators=(",", ":"))
        assert "NaN" not in blob
        assert "Infinity" not in blob


# ──────────────────────────────────────────────────────────────
# 5. Determinismo
# ──────────────────────────────────────────────────────────────
class TestDeterminismo:
    def test_hexagons_e_view_identicos(self, tmp_path: Path) -> None:
        r1 = _call(tmp_path)
        r2 = _call(tmp_path)
        h1 = json.dumps(r1["hexagons"], separators=(",", ":"), sort_keys=True)
        h2 = json.dumps(r2["hexagons"], separators=(",", ":"), sort_keys=True)
        assert h1 == h2
        assert r1["view"] == r2["view"]


# ──────────────────────────────────────────────────────────────
# 6. HTML deck.gl
# ──────────────────────────────────────────────────────────────
class TestBuildDeckglHtml:
    def _sample(self) -> dict[str, Any]:
        return {
            "uf": "SP",
            "version": "ui_spike_deckgl_v1",
            "timestamp": "2026-07-16T12:00:00Z",
            "view": {"longitude": -46.63, "latitude": -23.55, "zoom": 9.0},
            "hexagons": [
                {"h": "87a8a07c4ffffff", "bm1": 7, "br": 4, "s": 75.0,
                 "sr": 45.0, "p": 12000, "o": 2100}
            ],
        }

    def test_retorna_string(self) -> None:
        from motor_expansao.dashboard.ui_spike_deckgl import _build_deckgl_html

        assert isinstance(_build_deckgl_html(self._sample()), str)

    def test_contem_cdn_deckgl_e_layer(self) -> None:
        from motor_expansao.dashboard.ui_spike_deckgl import _build_deckgl_html

        html = _build_deckgl_html(self._sample())
        assert "deck.gl" in html
        assert "H3HexagonLayer" in html
        assert "getHexagon" in html
        assert "updateTriggers" in html
        assert "__spikeFirstPaintMs" in html

    def test_dados_embutidos(self) -> None:
        from motor_expansao.dashboard.ui_spike_deckgl import _build_deckgl_html

        html = _build_deckgl_html(self._sample())
        assert "87a8a07c4ffffff" in html

    def test_sem_pii_no_html(self) -> None:
        from motor_expansao.dashboard.ui_spike_deckgl import (
            _PII_FORBIDDEN,
            _build_deckgl_html,
        )

        html = _build_deckgl_html(self._sample())
        for col in _PII_FORBIDDEN:
            assert col not in html

    def test_html_doc_valido(self) -> None:
        from motor_expansao.dashboard.ui_spike_deckgl import _build_deckgl_html

        html = _build_deckgl_html(self._sample())
        assert "<!DOCTYPE html>" in html
        assert "<html" in html and "</html>" in html
        assert "<script" in html

    def test_dados_vazios_gera_html(self) -> None:
        from motor_expansao.dashboard.ui_spike_deckgl import _build_deckgl_html

        data: dict[str, Any] = {
            "uf": "XX", "version": "ui_spike_deckgl_v1", "timestamp": "",
            "view": {"longitude": 0, "latitude": 0, "zoom": 4}, "hexagons": [],
        }
        html = _build_deckgl_html(data)
        assert "<!DOCTYPE html>" in html
        assert "var HEX_DATA = []" in html


# ──────────────────────────────────────────────────────────────
# 7. is_spike_enabled
# ──────────────────────────────────────────────────────────────
class TestIsSpikeEnabled:
    def test_env_var_ativa(self) -> None:
        with patch.dict(os.environ, {"ULTRA_SPIKE_DECKGL": "1"}), patch(
            "streamlit.session_state", {}
        ):
            from motor_expansao.dashboard import ui_spike_deckgl

            assert ui_spike_deckgl.is_spike_enabled() is True

    def test_env_var_desativa(self) -> None:
        with patch.dict(os.environ, {"ULTRA_SPIKE_DECKGL": "0"}), patch(
            "streamlit.session_state", {"show_ui_spike_deckgl": False}
        ):
            from motor_expansao.dashboard import ui_spike_deckgl

            assert ui_spike_deckgl.is_spike_enabled() is False

    def test_session_state_true(self) -> None:
        env = {k: v for k, v in os.environ.items() if k != "ULTRA_SPIKE_DECKGL"}
        with patch.dict(os.environ, env, clear=True), patch(
            "streamlit.session_state", {"show_ui_spike_deckgl": True}
        ):
            from motor_expansao.dashboard import ui_spike_deckgl

            assert ui_spike_deckgl.is_spike_enabled() is True

    def test_tudo_desabilitado(self) -> None:
        env = {k: v for k, v in os.environ.items() if k != "ULTRA_SPIKE_DECKGL"}
        with patch.dict(os.environ, env, clear=True), patch(
            "streamlit.session_state", {}
        ):
            from motor_expansao.dashboard import ui_spike_deckgl

            assert ui_spike_deckgl.is_spike_enabled() is False


# ──────────────────────────────────────────────────────────────
# Import + smoke do harness Playwright (sem browser/rede)
# ──────────────────────────────────────────────────────────────
class TestImport:
    def test_modulo_importa(self) -> None:
        from motor_expansao.dashboard import ui_spike_deckgl  # noqa: F401

    def test_harness_guard_anti_producao(self) -> None:
        """A guarda anti-produção é função pura, testável sem browser/rede."""
        import importlib.util

        script = (
            Path(__file__).resolve().parents[2]
            / "scripts"
            / "rev08_spike_playwright.py"
        )
        spec = importlib.util.spec_from_file_location("rev08_harness", script)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        # URL de produção sem confirmação → mensagem de abort.
        msg = mod.check_production_guard(
            "https://dashboard.ultra-expansao.tech", confirmed=False
        )
        assert msg is not None and "ABORTADO" in msg
        # Com confirmação → None (segue).
        assert (
            mod.check_production_guard(
                "https://dashboard.ultra-expansao.tech", confirmed=True
            )
            is None
        )
        # Localhost → None.
        assert mod.check_production_guard("http://localhost:8501", confirmed=False) is None
        # --help do parser não lança.
        assert mod.build_parser().prog == "rev08_spike_playwright.py"
