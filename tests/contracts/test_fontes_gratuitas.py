"""
tests/unit/test_fontes_gratuitas.py — Testes das fontes de dados gratuitas

Cobre:
  - IBGECenso: _features_padrao, _sidra_renda_populacao, falha de rede
  - POIEnricher: buscar_academias_osm, erro de rede, score sem Google key
  - calcular_hex_score: range 0-100, maior renda = maior score, série constante
  - verificar_canibalizacao: detecta unidade próxima, retorna False sem unidades
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Mockar api.config e jobs.pipelines.* antes de importar os módulos do projeto
# (os arquivos estão na raiz do repositório, não em subpacotes)
# ---------------------------------------------------------------------------
_mock_settings = MagicMock()
_mock_settings.GOOGLE_MAPS_API_KEY = ""
_mock_settings.DIST_MIN_ULTRA_KM = 1.0
_mock_settings.RENDA_MIN = 4500.0
_mock_settings.H3_RESOLUTION = 7
_mock_settings.AREA_MIN_M2 = 1200.0
_mock_settings.AREA_IDEAL_MIN_M2 = 1500.0
_mock_settings.AREA_IDEAL_MAX_M2 = 2000.0
_mock_settings.PE_DIREITO_MIN = 3.5
_mock_settings.M1_SCORE_OFICIAL = "score_priorizacao"
_mock_settings.M1_PRIORIZACAO_TOP_PCT_POR_UF = 0.20
_mock_settings.M1_OSM_ENABLED = False
_mock_settings.M1_SETOR_CENSITARIO_OBRIGATORIO = False
_mock_settings.M1_POP_MINIMA_PROXY = 1

_mock_api_config = MagicMock(settings=_mock_settings)
_mock_api = MagicMock()
_mock_api.config = _mock_api_config

sys.modules.setdefault("api", _mock_api)
sys.modules.setdefault("api.config", _mock_api_config)

# hex_enrichment.py importa jobs.pipelines.ibge_censo / poi_enrichment
# ---------------------------------------------------------------------------
# IBGECenso
# ---------------------------------------------------------------------------

class TestIBGECensoFeaturesPadrao:
    def test_retorna_zeros(self):
        from ibge_censo import IBGECenso
        resultado = IBGECenso._features_padrao()
        assert resultado["renda_per_capita"] == 0.0
        assert resultado["pop_total"] == 0.0
        assert resultado["n_domicilios"] == 0.0
        assert resultado["densidade_dom"] == 0.0
        assert resultado["area_km2"] == 0.0
        assert resultado["fonte"] == "fallback_padrao"

    def test_todas_chaves_presentes(self):
        from ibge_censo import IBGECenso
        resultado = IBGECenso._features_padrao()
        chaves_esperadas = {"renda_per_capita", "pop_total",
                            "n_domicilios", "densidade_dom", "area_km2", "fonte",
                            "fonte_renda", "fonte_populacao", "nivel_geografico_ibge",
                            "fallback_setor_censitario", "motivo_fallback_setor"}
        assert chaves_esperadas.issubset(set(resultado.keys()))


class TestIBGECensoSidraRenda:
    def test_valor_reticencias_retorna_zero(self):
        """_sidra_renda_populacao deve lidar com valor '...' sem quebrar."""
        from ibge_censo import IBGECenso
        censo = IBGECenso()
        resposta_renda = MagicMock()
        resposta_renda.status_code = 200
        resposta_renda.json.return_value = [
            {"D1C": "cod", "D2C": "var", "V": "..."},
            {"D1C": "3550308", "D2C": "allxp", "V": "..."},
        ]
        resposta_pop = MagicMock()
        resposta_pop.status_code = 200
        resposta_pop.json.return_value = [{"V": "0"}]

        with patch("requests.get", side_effect=[resposta_renda, resposta_pop]):
            resultado = censo._sidra_renda_populacao.__wrapped__(censo, "3550308")

        assert resultado["renda_per_capita"] == 0
        assert isinstance(resultado, dict)

    def test_valor_numerico_parseado_corretamente(self):
        from ibge_censo import IBGECenso
        censo = IBGECenso()
        resposta_renda = MagicMock()
        resposta_renda.status_code = 200
        resposta_renda.json.return_value = [
            {"D1C": "cod"},
            {"D1C": "3550308", "V": "2500,50"},
        ]
        resposta_pop = MagicMock()
        resposta_pop.status_code = 200
        resposta_pop.json.return_value = [
            {"V": "0"},
            {"V": "15000"},
            {"V": "12000"},
        ]

        with patch("requests.get", side_effect=[resposta_renda, resposta_pop]):
            resultado = censo._sidra_renda_populacao.__wrapped__(censo, "3550308")

        assert resultado["renda_per_capita"] == pytest.approx(2500.50)
        assert resultado["pop_total"] == pytest.approx(27000.0)

    def test_falha_de_rede_retorna_padrao(self):
        from ibge_censo import IBGECenso
        censo = IBGECenso()
        with patch("requests.get", side_effect=ConnectionError("timeout")):
            resultado = censo._sidra_renda_populacao.__wrapped__(censo, "3550308")
        assert resultado["renda_per_capita"] == 0.0
        assert resultado["fonte"].startswith("ibge_sidra_municipio_2022")

    def test_geocodigo_municipio_retorna_none_em_falha(self):
        from ibge_censo import IBGECenso
        censo = IBGECenso()
        with patch("requests.get", side_effect=ConnectionError("sem rede")):
            cod = censo._geocodigo_municipio.__wrapped__(censo, -23.5, -46.6)
        assert cod is None


# ---------------------------------------------------------------------------
# POIEnricher
# ---------------------------------------------------------------------------

class TestPOIEnricher:
    @staticmethod
    def _cache_teste(nome: str) -> Path:
        path = Path("data/osm_cache") / nome
        if path.exists():
            path.unlink()
        return path

    def test_buscar_academias_osm_retorna_lista(self):
        from poi_enrichment import POIEnricher
        enricher = POIEnricher()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "elements": [
                {"id": 1, "lat": -23.5, "lon": -46.6,
                 "tags": {"name": "SmartFit", "leisure": "fitness_centre"}},
                {"id": 2, "lat": -23.51, "lon": -46.61,
                 "tags": {"name": "Bluefit", "sport": "gym"}},
            ]
        }
        with patch("requests.post", return_value=mock_resp), \
             patch("time.sleep"):
            resultado = enricher.buscar_academias_osm(-23.5, -46.6)

        assert len(resultado) == 2
        assert resultado[0]["nome"] == "SmartFit"
        assert resultado[0]["fonte"] == "osm"

    def test_buscar_academias_osm_retorna_lista_vazia_em_erro(self):
        from poi_enrichment import POIEnricher
        enricher = POIEnricher()
        with patch("requests.post", side_effect=ConnectionError("sem rede")):
            resultado = enricher.buscar_academias_osm(-23.5, -46.6)
        assert resultado == []

    def test_score_vitalidade_sem_google_key_retorna_50(self):
        from poi_enrichment import POIEnricher
        with patch("api.config.settings") as mock_settings:
            mock_settings.GOOGLE_MAPS_API_KEY = ""
            enricher = POIEnricher()
            enricher._google_key = ""
            score = enricher.score_vitalidade_comercial(-23.5, -46.6)
        assert score == 50.0

    def test_buscar_pois_google_sem_key_retorna_lista_vazia(self):
        from poi_enrichment import POIEnricher
        enricher = POIEnricher()
        enricher._google_key = ""
        resultado = enricher.buscar_pois_google(-23.5, -46.6, tipo="gym")
        assert resultado == []

    def test_features_para_hex_sem_google_key(self):
        from poi_enrichment import POIEnricher
        enricher = POIEnricher()
        enricher._google_key = ""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"elements": []}
        with patch("requests.post", return_value=mock_resp), \
             patch("time.sleep"), \
             patch("poi_enrichment.h3.cell_to_latlng", return_value=(-23.5, -46.6)):
            resultado = enricher.features_para_hex("877b59a69ffffff")
        assert resultado["score_vitalidade"] == 50.0
        assert "n_academias_osm" in resultado

    def test_carregar_academias_cidade_popula_cache(self):
        """carregar_academias_cidade() deve popular self._cache_academias."""
        from poi_enrichment import POIEnricher
        enricher = POIEnricher()
        cache_path = self._cache_teste("bbox_ok_test.json")
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "elements": [
                {"id": 10, "lat": -16.68, "lon": -49.25,
                 "tags": {"name": "Academia X", "leisure": "fitness_centre"}},
                {"id": 11, "lat": -16.70, "lon": -49.27,
                 "tags": {"name": "Academy Y", "sport": "gym"}},
            ]
        }
        with patch("requests.post", return_value=mock_resp), \
             patch.object(POIEnricher, "_bbox_cache_path", return_value=cache_path):
            resultado = enricher.carregar_academias_cidade(-17.0, -16.5, -49.6, -49.0)

        assert len(resultado) == 2
        assert hasattr(enricher, "_cache_academias")
        assert len(enricher._cache_academias) == 2
        assert enricher._cache_academias[0]["nome"] == "Academia X"

    def test_carregar_academias_cidade_erro_levanta_excecao(self):
        from poi_enrichment import POIEnricher
        enricher = POIEnricher()
        cache_path = self._cache_teste("bbox_erro_test.json")
        with patch("requests.post", side_effect=ConnectionError("timeout")), \
             patch("time.sleep"), \
             patch.object(POIEnricher, "_bbox_cache_path", return_value=cache_path):
            with pytest.raises(RuntimeError, match="Falha ao consultar Overpass"):
                enricher.carregar_academias_cidade(-17.0, -16.5, -49.6, -49.0)
        assert enricher._cache_academias is None

    def test_carregar_academias_cidade_tenta_endpoint_reserva(self):
        from poi_enrichment import POIEnricher
        enricher = POIEnricher()
        cache_path = self._cache_teste("bbox_reserva_test.json")
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "elements": [
                {"id": 10, "lat": -16.68, "lon": -49.25,
                 "tags": {"name": "Academia X", "leisure": "fitness_centre"}},
            ]
        }

        def side_effect(url, **kwargs):
            if "overpass-api.de" in url:
                raise ConnectionError("429")
            return mock_resp

        with patch("requests.post", side_effect=side_effect), \
             patch("time.sleep"), \
             patch.object(POIEnricher, "_bbox_cache_path", return_value=cache_path):
            resultado = enricher.carregar_academias_cidade(-17.0, -16.5, -49.6, -49.0)

        assert len(resultado) == 1
        assert enricher._cache_academias[0]["nome"] == "Academia X"

    def test_contar_academias_proximas_com_cache(self):
        """Conta usando self._cache_academias — sem HTTP."""
        from poi_enrichment import POIEnricher
        enricher = POIEnricher()
        enricher._cache_academias = [
            {"lat": -16.682, "lng": -49.254},   # ~0m — dentro
            {"lat": -16.690, "lng": -49.260},   # ~1050m — dentro
            {"lat": -16.730, "lng": -49.300},   # ~5.5km — fora
            {"lat": None,    "lng": None},       # inválido — ignorado
        ]
        n = enricher.contar_academias_proximas(-16.682, -49.254, raio_metros=1500)
        assert n == 2

    def test_contar_academias_proximas_sem_cache_faz_fallback_osm(self):
        """Sem cache, cai em buscar_academias_osm()."""
        from poi_enrichment import POIEnricher
        enricher = POIEnricher()
        assert enricher._cache_academias is None
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"elements": [{"id": 1, "lat": -16.68, "lon": -49.25,
                                                      "tags": {}}]}
        with patch("requests.post", return_value=mock_resp), patch("time.sleep"):
            n = enricher.contar_academias_proximas(-16.68, -49.25, raio_metros=1500)
        assert n == 1


# ---------------------------------------------------------------------------
# IBGECenso — set_municipio_padrao / resolver_municipio
# ---------------------------------------------------------------------------

class TestIBGECensoMunicipioPadrao:
    def test_set_municipio_padrao_elimina_geocodificacao(self):
        """Após set_municipio_padrao, _geocodigo_municipio não deve ser chamado."""
        from ibge_censo import IBGECenso
        censo = IBGECenso()
        censo.set_municipio_padrao("5208707", "GO")
        assert censo._municipio_padrao == "5208707"
        assert censo._uf_padrao == "GO"

        resp_sidra = MagicMock()
        resp_sidra.status_code = 200
        resp_sidra.json.return_value = [{"V": "0"}, {"V": "1800,00"}]

        with patch("requests.get", return_value=resp_sidra) as mock_get, \
             patch("time.sleep"):
            resultado = censo._features_municipio_sidra(-16.68, -49.25)

        # Deve ter chamado SIDRA (1 ou 2 vezes), nunca Nominatim
        urls_chamadas = [str(call) for call in mock_get.call_args_list]
        assert not any("nominatim" in u.lower() for u in urls_chamadas), \
            "Nominatim não deve ser chamado quando municipio_padrao está definido"
        assert resultado["fonte"].startswith("ibge_sidra_municipio_2022")

    def test_resolver_municipio_chama_ibge_localidades(self):
        """resolver_municipio deve consultar a API IBGE de localidades."""
        from ibge_censo import IBGECenso
        censo = IBGECenso()
        municipios_mock = [
            {"nome": "Goiania", "id": 5208707,
             "microrregiao": {"mesorregiao": {"UF": {"sigla": "GO"}}}},
        ]
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = municipios_mock

        with patch("requests.get", return_value=resp):
            cod = censo.resolver_municipio("Goiania", "GO")

        assert cod == "5208707"
        assert censo._municipio_padrao == "5208707"
        assert censo._uf_padrao == "GO"

    def test_resolver_municipio_nao_encontrado_retorna_none(self):
        from ibge_censo import IBGECenso
        censo = IBGECenso()
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = []  # nenhum município

        with patch("requests.get", return_value=resp):
            cod = censo.resolver_municipio("CidadeInexistente", "XX")

        assert cod is None
        assert getattr(censo, "_municipio_padrao", None) is None


# ---------------------------------------------------------------------------
# calcular_hex_score
# ---------------------------------------------------------------------------

class TestCalcularHexScore:
    def _df_base(self):
        return pd.DataFrame({
            "hex_id":           ["aaa", "bbb", "ccc"],
            "renda_per_capita": [1000.0, 3000.0, 5000.0],
            "pop_total":        [500.0, 1500.0, 3000.0],
            "n_academias_osm":  [0, 1, 5],
            "score_vitalidade": [30.0, 60.0, 90.0],
        })

    def test_score_entre_0_e_100(self):
        from hex_enrichment import calcular_hex_score
        df = calcular_hex_score(self._df_base())
        assert (df["hex_score"] >= 0).all()
        assert (df["hex_score"] <= 100).all()

    def test_maior_renda_gera_maior_score(self):
        from hex_enrichment import calcular_hex_score
        df = pd.DataFrame({
            "renda_per_capita": [1000.0, 5000.0],
            "pop_total":        [1000.0, 1000.0],
            "n_academias_osm":  [0, 0],
            "score_vitalidade": [50.0, 50.0],
        })
        df_scored = calcular_hex_score(df)
        assert df_scored.iloc[1]["hex_score"] > df_scored.iloc[0]["hex_score"]

    def test_score_com_colunas_ausentes_usa_fallback(self):
        from hex_enrichment import calcular_hex_score
        df = pd.DataFrame({
            "n_academias_osm":  [0, 2],
            "score_vitalidade": [50.0, 80.0],
        })
        df_scored = calcular_hex_score(df)
        assert (df_scored["hex_score"] >= 0).all()
        assert (df_scored["hex_score"] <= 100).all()

    def test_score_estrutural_exclui_hex_sem_populacao_do_ranking(self):
        from hex_enrichment import calcular_hex_score_estrutural
        df = pd.DataFrame({
            "hex_id": ["a", "b"],
            "renda_per_capita": [1500.0, 4500.0],
            "pop_total": [0.0, 0.0],
        })
        df_scored = calcular_hex_score_estrutural(df)

        assert df_scored.loc[0, "populacao_proxy"] == pytest.approx(0.0)
        assert pd.isna(df_scored.loc[0, "pop_pct_nacional"])
        assert pd.isna(df_scored.loc[1, "pop_pct_nacional"])
        assert df_scored.loc[0, "hex_score_estrutural"] == pytest.approx(0.0)
        assert df_scored.loc[1, "hex_score_estrutural"] == pytest.approx(0.0)
        assert df_scored.loc[0, "score_priorizacao"] == pytest.approx(0.0)
        assert df_scored.loc[1, "score_priorizacao"] == pytest.approx(0.0)


class TestNormalizarSerie:
    def test_serie_constante_retorna_50(self):
        from hex_enrichment import normalizar_serie
        serie = pd.Series([100.0, 100.0, 100.0])
        resultado = normalizar_serie(serie)
        assert (resultado == 50.0).all()

    def test_normalizacao_min_max(self):
        from hex_enrichment import normalizar_serie
        serie = pd.Series([0.0, 50.0, 100.0])
        resultado = normalizar_serie(serie)
        assert resultado.iloc[0] == pytest.approx(0.0)
        assert resultado.iloc[1] == pytest.approx(50.0)
        assert resultado.iloc[2] == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# verificar_canibalizacao
# ---------------------------------------------------------------------------

class TestVerificarCanibalizacao:
    def test_sem_unidades_retorna_false(self):
        from hex_enrichment import verificar_canibalizacao
        resultado = verificar_canibalizacao("877b59a69ffffff", [])
        assert resultado["tem_ultra_proxima"] is False
        assert resultado["dist_ultra_mais_proxima_km"] is None

    def test_detecta_unidade_proxima(self):
        from hex_enrichment import verificar_canibalizacao
        lat, lng = -23.5505, -46.6333  # São Paulo centro
        unidade_proxima = (lat + 0.001, lng + 0.001)  # ~150m de distância
        hex_id = "877b59a69ffffff"
        with patch("hex_enrichment.h3.cell_to_latlng", return_value=(lat, lng)):
            resultado = verificar_canibalizacao(hex_id, [unidade_proxima])
        assert resultado["tem_ultra_proxima"] is True

    def test_unidade_distante_nao_canibaliza(self):
        from hex_enrichment import verificar_canibalizacao
        lat, lng = -23.5505, -46.6333
        unidade_distante = (lat + 0.1, lng + 0.1)  # ~14km de distância
        hex_id = "877b59a69ffffff"
        with patch("hex_enrichment.h3.cell_to_latlng", return_value=(lat, lng)):
            resultado = verificar_canibalizacao(hex_id, [unidade_distante])
        assert resultado["tem_ultra_proxima"] is False


# ---------------------------------------------------------------------------
# rodar_pipeline_hex — resolver_municipio chamado apenas 1 vez
# ---------------------------------------------------------------------------

class TestRodarPipelineHexOtimizado:
    def test_resolver_municipio_chamado_uma_vez(self):
        """rodar_pipeline_hex deve chamar resolver_municipio exatamente 1 vez."""
        import hex_enrichment
        from hex_enrichment import rodar_pipeline_hex

        hexagonos_fake = ["87a8c0d03ffffff", "87a8c0d08ffffff", "87a8c0d09ffffff"]

        with patch.object(hex_enrichment, "gerar_hexagonos_cidade",
                          return_value=hexagonos_fake), \
             patch("hex_enrichment.IBGECenso") as MockCenso, \
             patch("hex_enrichment.POIEnricher") as MockPOI, \
             patch("hex_enrichment.h3.cell_to_latlng",
                   side_effect=[(-16.95, -49.25), (-16.93, -49.29),
                                 (-16.91, -49.31)] * 4):

            mock_censo = MockCenso.return_value
            mock_censo.resolver_municipio.return_value = "5208707"
            mock_censo._sidra_renda_populacao.return_value = {
                "renda_per_capita": 1800.0, "pop_total": 120000.0,
                "n_domicilios": 40000.0,
                "densidade_dom": 50.0, "fonte": "ibge_sidra_municipio_2022",
            }
            mock_censo.features_para_coordenada.return_value = {
                "renda_per_capita": 1800.0, "pop_total": 120000.0,
                "n_domicilios": 40000.0,
                "densidade_dom": 50.0, "fonte": "ibge_sidra_municipio_2022",
            }
            mock_poi = MockPOI.return_value
            mock_poi.carregar_academias_cidade.return_value = []
            mock_poi.contar_academias_proximas.return_value = 0

            with patch("hex_enrichment.pd.DataFrame.to_parquet"):
                rodar_pipeline_hex("Goiania", "GO", raio_km=5.0)

        # resolver_municipio chamado exatamente 1 vez, não 1 por hexágono
        assert mock_censo.resolver_municipio.call_count == 1
        assert mock_censo.resolver_municipio.call_args == (("Goiania", "GO"),)

    def test_carregar_academias_cidade_chamado_uma_vez(self):
        """carregar_academias_cidade deve ser chamado 1 vez (bulk), não N vezes."""
        import hex_enrichment
        from hex_enrichment import rodar_pipeline_hex

        hexagonos_fake = ["87a8c0d03ffffff", "87a8c0d08ffffff"]

        with patch.object(hex_enrichment, "gerar_hexagonos_cidade",
                          return_value=hexagonos_fake), \
             patch("hex_enrichment.IBGECenso") as MockCenso, \
             patch("hex_enrichment.POIEnricher") as MockPOI, \
             patch("hex_enrichment.h3.cell_to_latlng",
                   side_effect=[(-16.95, -49.25), (-16.93, -49.29)] * 4):

            mock_censo = MockCenso.return_value
            mock_censo.resolver_municipio.return_value = "5208707"
            mock_censo._sidra_renda_populacao.return_value = {}
            mock_censo.features_para_coordenada.return_value = {
                "renda_per_capita": 0, "pop_total": 0,
                "n_domicilios": 0, "densidade_dom": 0, "fonte": "fallback_padrao",
            }
            mock_poi = MockPOI.return_value
            mock_poi.carregar_academias_cidade.return_value = []
            mock_poi.contar_academias_proximas.return_value = 0

            with patch("hex_enrichment.pd.DataFrame.to_parquet"):
                rodar_pipeline_hex("Goiania", "GO", raio_km=5.0)

        # 1 chamada para toda a cidade, não 1 por hexágono
        assert mock_poi.carregar_academias_cidade.call_count == 1
