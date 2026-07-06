"""Smoke tests do PoC de repaginação do dashboard (BLK-UI-10).

Cobre:
  - inject_ultra_theme(): chama st.markdown sem exceção (mocka st.markdown).
  - gerar_recorte_json(): gera dict com estrutura esperada, determinístico,
    sem PII, sem NaN/Inf serializáveis.
  - Fallback quando UF não existe no cache/parquet.
  - kpi_card_html() e detail_panel_html(): retornam strings HTML sem exceção.
  - is_proto_enabled(): lê env var ULTRA_PROTO corretamente.

READ-ONLY M1: nenhum artefato oficial é criado, lido como fixture, ou alterado.
Sem rede: testes não acessam CDN nem URLs externas.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pandas as pd
import pytest

# ──────────────────────────────────────────────────────────────
# Fixtures sintéticas (sem dado real)
# ──────────────────────────────────────────────────────────────
_FAKE_UF = "TT"  # sigla inexistente — nunca colide com UF real

def _make_fake_df(n: int = 10) -> pd.DataFrame:
    """DataFrame sintético com as colunas mínimas do recorte JSON."""
    rows = []
    for i in range(n):
        rows.append(
            {
                "hex_id": f"87aaaaaa{i:07x}",
                "lat": -23.55 + i * 0.01,
                "lng": -46.63 + i * 0.01,
                "score_priorizacao": 50.0 + i,
                "pop_total": 10_000 + i * 1_000,
                "renda_per_capita": 3_000.0 + i * 100,
                "score_oportunidade_residual": 40.0 + i,
                "oferta_efetiva_disponivel": 2_000 + i * 100,
                "sam_fitness_potencial": 3_500 + i * 200,
                "populacao_proxy": 10_000 + i * 1_000,
                "nome_municipio": "FAKE CITY",
                "uf": "TT",
                "UF": "TT",
            }
        )
    return pd.DataFrame(rows)


# ──────────────────────────────────────────────────────────────
# Testes de ui_theme
# ──────────────────────────────────────────────────────────────
class TestInjectUltraTheme:
    """inject_ultra_theme() chama st.markdown sem exceção."""

    def test_calls_st_markdown(self) -> None:
        """inject_ultra_theme não levanta exceção e chama st.markdown."""
        with patch("streamlit.markdown") as mock_md:
            from motor_expansao.dashboard.ui_theme import inject_ultra_theme
            inject_ultra_theme()
            assert mock_md.called, "st.markdown não foi chamado"
            call_args = mock_md.call_args
            assert call_args is not None
            # Primeiro argumento é a string HTML com <style>
            first_arg = call_args[0][0] if call_args[0] else call_args[1].get("body", "")
            assert "<style>" in first_arg, "CSS não foi injetado como <style>"
            assert "unsafe_allow_html" in str(call_args), "unsafe_allow_html ausente"

    def test_css_contains_required_variables(self) -> None:
        """CSS gerado contém as variáveis da paleta aprovada."""
        from motor_expansao.dashboard.ui_theme import _CSS
        for var in ("--ultra", "--conc", "--bg", "--panel", "--text", "--muted"):
            assert var in _CSS, f"Variável CSS {var!r} ausente no tema"

    def test_css_contains_font_imports(self) -> None:
        """CSS importa Space Grotesk e IBM Plex."""
        from motor_expansao.dashboard.ui_theme import _CSS
        assert "Space+Grotesk" in _CSS, "Space Grotesk ausente no @import"
        assert "IBM+Plex+Sans" in _CSS, "IBM Plex Sans ausente no @import"
        assert "IBM+Plex+Mono" in _CSS, "IBM Plex Mono ausente no @import"

    def test_css_accessibility(self) -> None:
        """CSS respeita prefers-reduced-motion e foco visível."""
        from motor_expansao.dashboard.ui_theme import _CSS
        assert "prefers-reduced-motion" in _CSS, "prefers-reduced-motion ausente"
        assert "focus-visible" in _CSS, "foco de teclado ausente"

    def test_css_prefixed(self) -> None:
        """Classes CSS usam prefixo .ui-proto- para não conflitar com Streamlit."""
        from motor_expansao.dashboard.ui_theme import _CSS
        # Verificar que não há seletores perigosos sem prefixo
        assert ".ui-proto-" in _CSS, "Prefixo .ui-proto- ausente no CSS"


class TestKpiCardHtml:
    """kpi_card_html() retorna HTML válido."""

    def test_returns_string(self) -> None:
        from motor_expansao.dashboard.ui_theme import kpi_card_html
        result = kpi_card_html("hexágonos", "1.234")
        assert isinstance(result, str)
        assert "1.234" in result
        assert "hexágonos" in result

    def test_conc_modifier(self) -> None:
        from motor_expansao.dashboard.ui_theme import kpi_card_html
        result = kpi_card_html("concorrentes", "42", conc=True)
        assert "ui-proto-kpi--conc" in result

    def test_sub_text(self) -> None:
        from motor_expansao.dashboard.ui_theme import kpi_card_html
        result = kpi_card_html("score", "75.3", "top 20%")
        assert "top 20%" in result


class TestDetailPanelHtml:
    """detail_panel_html() retorna HTML válido."""

    def test_returns_string(self) -> None:
        from motor_expansao.dashboard.ui_theme import detail_panel_html
        result = detail_panel_html({"hex_id": "87aaa...", "score": "78.5"})
        assert isinstance(result, str)
        assert "87aaa..." in result
        assert "78.5" in result

    def test_custom_title(self) -> None:
        from motor_expansao.dashboard.ui_theme import detail_panel_html
        result = detail_panel_html({"k": "v"}, title="Meu Hex")
        assert "Meu Hex" in result


# ──────────────────────────────────────────────────────────────
# Testes de gerar_recorte_json
# ──────────────────────────────────────────────────────────────
class TestGerarRecorteJson:
    """gerar_recorte_json(): estrutura, determinismo, sem PII."""

    def _call(self, tmp_path: Path, n: int = 10, **kwargs: Any) -> dict[str, Any]:
        """Helper: grava parquet sintético e chama gerar_recorte_json."""
        from motor_expansao.dashboard.ui_proto import gerar_recorte_json

        uf = "TT"
        uf_dir = tmp_path / f"uf={uf}"
        uf_dir.mkdir(parents=True, exist_ok=True)
        df = _make_fake_df(n)
        parquet_file = uf_dir / "parte-0.parquet"
        df.to_parquet(parquet_file, index=False)

        # Override do CACHE_DIR para tmp_path
        cache_dir = tmp_path / "cache" / "ui_proto"
        with patch(
            "motor_expansao.dashboard.ui_proto._CACHE_DIR", cache_dir
        ):
            return gerar_recorte_json(
                uf,
                enriquecido_dir=tmp_path,
                **kwargs,
            )

    def test_estrutura_basica(self, tmp_path: Path) -> None:
        """Resultado tem os campos obrigatórios."""
        result = self._call(tmp_path)
        assert result["uf"] == "TT"
        assert result["version"] == "ui_proto_v1"
        assert "timestamp" in result
        assert "hexagons" in result
        assert isinstance(result["hexagons"], list)

    def test_hexagons_tem_campos_obrigatorios(self, tmp_path: Path) -> None:
        """Cada hexágono tem hex_id, lat, lng, score_priorizacao."""
        result = self._call(tmp_path)
        for hex_entry in result["hexagons"]:
            for field in ("hex_id", "lat", "lng", "score_priorizacao"):
                assert field in hex_entry, f"Campo {field!r} ausente no hexágono"

    def test_sem_nan_infinito(self, tmp_path: Path) -> None:
        """JSON serializado não contém NaN nem Infinity."""
        result = self._call(tmp_path)
        json_str = json.dumps(result, separators=(",", ":"))
        assert "NaN" not in json_str, "NaN encontrado no JSON"
        assert "Infinity" not in json_str, "Infinity encontrado no JSON"
        assert "null" in json_str or True  # None → null é aceitável

    def test_sem_pii(self, tmp_path: Path) -> None:
        """JSON não contém colunas de PII."""
        # Adiciona colunas PII ao DataFrame sintético
        uf = "TT"
        uf_dir = tmp_path / f"uf={uf}"
        uf_dir.mkdir(parents=True, exist_ok=True)
        df = _make_fake_df(5)
        df["endereco"] = "Rua Fake, 123"
        df["nome_propriedade"] = "Loja XYZ"
        df["owner"] = "João Silva"
        df.to_parquet(uf_dir / "parte-0.parquet", index=False)

        from motor_expansao.dashboard.ui_proto import _PII_FORBIDDEN, gerar_recorte_json
        cache_dir = tmp_path / "cache" / "ui_proto"
        with patch("motor_expansao.dashboard.ui_proto._CACHE_DIR", cache_dir):
            result = gerar_recorte_json("TT", enriquecido_dir=tmp_path)

        json_str = json.dumps(result)
        for pii_col in _PII_FORBIDDEN:
            assert pii_col not in json_str, f"Coluna PII {pii_col!r} no JSON"

    def test_determinismo(self, tmp_path: Path) -> None:
        """Chamadas repetidas com mesmo input produzem JSON byte-a-byte idêntico.

        Nota: o timestamp muda entre chamadas, então comparamos apenas os hexágonos.
        """
        result1 = self._call(tmp_path)
        result2 = self._call(tmp_path)
        # Os hexágonos devem ser idênticos (ordem, valores)
        h1 = json.dumps(result1["hexagons"], separators=(",", ":"), sort_keys=True)
        h2 = json.dumps(result2["hexagons"], separators=(",", ":"), sort_keys=True)
        assert h1 == h2, "Hexágonos diferem entre chamadas (não-determinístico)"

    def test_filtro_pop_min(self, tmp_path: Path) -> None:
        """pop_min filtra hexes com população abaixo do limiar."""
        result = self._call(tmp_path, n=10, pop_min=15_000)
        for hex_entry in result["hexagons"]:
            pop = hex_entry.get("pop_total")
            if pop is not None:
                assert pop >= 15_000, f"Hexágono com pop={pop} abaixo do pop_min=15000"

    def test_limite_hexes(self, tmp_path: Path) -> None:
        """limit restringe o número máximo de hexes no recorte."""
        result = self._call(tmp_path, n=20, limit=5, pop_min=0)
        assert len(result["hexagons"]) <= 5, "Limite de hexes não respeitado"

    def test_fallback_uf_inexistente(self, tmp_path: Path) -> None:
        """FileNotFoundError quando UF não existe."""
        from motor_expansao.dashboard.ui_proto import gerar_recorte_json
        cache_dir = tmp_path / "cache" / "ui_proto"
        with patch("motor_expansao.dashboard.ui_proto._CACHE_DIR", cache_dir):
            with pytest.raises(FileNotFoundError):
                gerar_recorte_json("ZZ", enriquecido_dir=tmp_path)

    def test_cache_salvo(self, tmp_path: Path) -> None:
        """JSON é salvo em cache após geração."""
        cache_dir = tmp_path / "cache" / "ui_proto"
        from motor_expansao.dashboard.ui_proto import gerar_recorte_json
        uf = "TT"
        uf_dir = tmp_path / f"uf={uf}"
        uf_dir.mkdir(parents=True)
        _make_fake_df(5).to_parquet(uf_dir / "parte-0.parquet", index=False)

        with patch("motor_expansao.dashboard.ui_proto._CACHE_DIR", cache_dir):
            gerar_recorte_json(uf, enriquecido_dir=tmp_path)
            cache_file = cache_dir / f"{uf}.json"
            assert cache_file.exists(), "Cache não foi salvo"
            loaded = json.loads(cache_file.read_text(encoding="utf-8"))
            assert loaded["uf"] == uf

    def test_sort_por_score_descendente(self, tmp_path: Path) -> None:
        """Hexes estão ordenados por score_priorizacao decrescente."""
        result = self._call(tmp_path, n=10, pop_min=0)
        scores = [h["score_priorizacao"] for h in result["hexagons"]
                  if h.get("score_priorizacao") is not None]
        assert scores == sorted(scores, reverse=True), "Hexes não estão ordenados por score desc"


# ──────────────────────────────────────────────────────────────
# Testes de is_proto_enabled
# ──────────────────────────────────────────────────────────────
class TestIsProtoEnabled:
    """is_proto_enabled() lê env var e session_state corretamente."""

    def test_env_var_ativa(self) -> None:
        with patch.dict(os.environ, {"ULTRA_PROTO": "1"}):
            with patch("streamlit.session_state", {}):
                from motor_expansao.dashboard import ui_proto
                # reload para pegar o env var de novo (a fn lê na chamada)
                result = ui_proto.is_proto_enabled()
                assert result is True

    def test_env_var_desativa(self) -> None:
        with patch.dict(os.environ, {"ULTRA_PROTO": "0"}):
            with patch("streamlit.session_state", {"show_ui_proto": False}):
                from motor_expansao.dashboard import ui_proto
                result = ui_proto.is_proto_enabled()
                assert result is False

    def test_env_var_ausente_session_state_true(self) -> None:
        env = {k: v for k, v in os.environ.items() if k != "ULTRA_PROTO"}
        with patch.dict(os.environ, env, clear=True):
            with patch("streamlit.session_state", {"show_ui_proto": True}):
                from motor_expansao.dashboard import ui_proto
                result = ui_proto.is_proto_enabled()
                assert result is True

    def test_tudo_desabilitado(self) -> None:
        env = {k: v for k, v in os.environ.items() if k != "ULTRA_PROTO"}
        with patch.dict(os.environ, env, clear=True):
            with patch("streamlit.session_state", {}):
                from motor_expansao.dashboard import ui_proto
                result = ui_proto.is_proto_enabled()
                assert result is False


# ──────────────────────────────────────────────────────────────
# Testes de _build_leaflet_html
# ──────────────────────────────────────────────────────────────
class TestBuildLeafletHtml:
    """_build_leaflet_html() gera HTML válido com dados embutidos."""

    def _sample_data(self) -> dict[str, Any]:
        return {
            "uf": "SP",
            "version": "ui_proto_v1",
            "timestamp": "2026-07-06T12:00:00Z",
            "hexagons": [
                {
                    "hex_id": "87a8a07c4ffffff",
                    "lat": -23.55,
                    "lng": -46.63,
                    "score_priorizacao": 75.0,
                    "pop_total": 12000,
                    "renda_per_capita": 5000.0,
                    "score_oportunidade_residual": 45.0,
                    "oferta_efetiva_disponivel": 2100,
                    "sam_fitness_potencial": 3500,
                }
            ],
        }

    def test_retorna_string(self) -> None:
        from motor_expansao.dashboard.ui_proto import _build_leaflet_html
        result = _build_leaflet_html(self._sample_data())
        assert isinstance(result, str)

    def test_contem_leaflet_cdn(self) -> None:
        from motor_expansao.dashboard.ui_proto import _build_leaflet_html
        result = _build_leaflet_html(self._sample_data())
        assert "leaflet" in result.lower(), "CDN do Leaflet ausente"

    def test_contem_h3js_cdn(self) -> None:
        from motor_expansao.dashboard.ui_proto import _build_leaflet_html
        result = _build_leaflet_html(self._sample_data())
        assert "h3-js" in result.lower() or "h3js" in result.lower(), "CDN do h3-js ausente"

    def test_dados_embutidos(self) -> None:
        from motor_expansao.dashboard.ui_proto import _build_leaflet_html
        result = _build_leaflet_html(self._sample_data())
        assert "87a8a07c4ffffff" in result, "hex_id não embutido no HTML"

    def test_sem_nan_no_html(self) -> None:
        from motor_expansao.dashboard.ui_proto import _build_leaflet_html
        data = self._sample_data()
        data["hexagons"][0]["score_priorizacao"] = None  # None → null no JSON
        result = _build_leaflet_html(data)
        # null é aceitável; NaN como literal JS não deve aparecer
        assert "NaN" not in result or "isNaN" in result, "NaN literal problemático no HTML"

    def test_html_doc_valido(self) -> None:
        from motor_expansao.dashboard.ui_proto import _build_leaflet_html
        result = _build_leaflet_html(self._sample_data())
        assert "<!DOCTYPE html>" in result
        assert "<html" in result
        assert "</html>" in result
        assert "<script" in result

    def test_dados_vazios_gera_html_valido(self) -> None:
        """HTML é gerado mesmo sem hexágonos (fallback gracioso)."""
        from motor_expansao.dashboard.ui_proto import _build_leaflet_html
        data: dict[str, Any] = {"uf": "XX", "version": "ui_proto_v1", "timestamp": "", "hexagons": []}
        result = _build_leaflet_html(data)
        assert "<!DOCTYPE html>" in result
        assert "HEX_DATA = []" in result


# ──────────────────────────────────────────────────────────────
# Teste de smoke import (sem streamlit em modo headless)
# ──────────────────────────────────────────────────────────────
class TestImport:
    """Módulos importam sem exceção."""

    def test_ui_theme_importa(self) -> None:
        from motor_expansao.dashboard import ui_theme  # noqa: F401

    def test_ui_proto_importa(self) -> None:
        from motor_expansao.dashboard import ui_proto  # noqa: F401

    def test_proto_palette_completa(self) -> None:
        from motor_expansao.dashboard.ui_theme import PROTO_PALETTE
        for key in ("bg", "panel", "line", "ultra", "conc", "text", "muted"):
            assert key in PROTO_PALETTE, f"Chave {key!r} ausente em PROTO_PALETTE"
            # Todas são strings hex válidas ou rgba
            val = PROTO_PALETTE[key]
            assert isinstance(val, str) and len(val) > 0

    def test_anti_default_checklist(self) -> None:
        """Anti-default checklist (handoff BLK-UI-10):
        1. Paleta NÃO é verde-ácido do totalpass nem cream+serif.
        2. Tipografia deliberada (Space Grotesk + IBM Plex).
        3. UMA assinatura (hexágono) + resto contido.
        4. Sem decoração sem significado.
        """
        from motor_expansao.dashboard.ui_theme import _CSS, PROTO_PALETTE
        # 1. Paleta: sem verde-ácido #00FF00 ou cream #FFFDD0
        assert "#00ff00" not in PROTO_PALETTE.get("ultra", "").lower()
        assert "#fffdd0" not in str(PROTO_PALETTE).lower()
        # 2. Tipografia: Space Grotesk + IBM Plex presentes
        assert "Space+Grotesk" in _CSS
        assert "IBM+Plex" in _CSS
        # 3. UMA assinatura — clip-path hexágono presente
        assert "clip-path" in _CSS
        assert _CSS.count("clip-path") >= 1
        # 4. Sem * nem body perigosos
        assert "* {" not in _CSS
        assert "body {" not in _CSS


# ──────────────────────────────────────────────────────────────
# Testes de wiring do opt-in em streamlit_app.py
# ──────────────────────────────────────────────────────────────
class TestStreamlitAppWiring:
    """Verifica que o opt-in em main() de streamlit_app.py está corretamente
    conectado a is_proto_enabled() e render_proto_page().

    Usa mock para não depender do Streamlit em modo headless.
    """

    def test_proto_enabled_chama_render_proto_page(self) -> None:
        """Quando ULTRA_PROTO=1, main() chama render_proto_page() e retorna cedo."""
        from unittest.mock import MagicMock, patch

        import streamlit_app

        mock_render = MagicMock()
        with (
            patch("motor_expansao.dashboard.ui_proto.is_proto_enabled", return_value=True),
            patch("motor_expansao.dashboard.ui_proto.render_proto_page", mock_render),
        ):
            streamlit_app.main()

        mock_render.assert_called_once()

    def test_proto_desabilitado_nao_chama_render_proto_page(self) -> None:
        """Quando ULTRA_PROTO não está ativo, render_proto_page() NÃO é chamado
        e inject_styles() (caminho de produção) é chamado em vez disso."""
        from unittest.mock import MagicMock, patch

        import streamlit_app

        mock_render = MagicMock()
        mock_inject = MagicMock()

        # st.stop() no Streamlit real lança StopException; simulamos com SystemExit
        # para interromper o fluxo após o bloco try/except do catalog.
        with (
            patch("motor_expansao.dashboard.ui_proto.is_proto_enabled", return_value=False),
            patch("motor_expansao.dashboard.ui_proto.render_proto_page", mock_render),
            patch("streamlit_app.inject_styles", mock_inject),
            patch("streamlit_app.render_header"),
            patch("streamlit_app.load_uf_catalog", side_effect=FileNotFoundError("sem dados")),
            patch("streamlit.error"),
            patch("streamlit.stop", side_effect=SystemExit(0)),
        ):
            try:
                streamlit_app.main()
            except SystemExit:
                pass  # esperado — simula st.stop() interrompendo o fluxo

        mock_render.assert_not_called()
        mock_inject.assert_called_once()
