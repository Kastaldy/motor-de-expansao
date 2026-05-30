import pandas as pd

from hex_enrichment import (
    calcular_hex_score_estrutural,
    calcular_hex_score_final,
    enriquecer_concorrencia_priorizados,
    preparar_base_oportunidades,
    resumir_validacao_nacional,
    selecionar_areas_prioritarias,
)
from ibge_censo import IBGECenso
from poi_enrichment import POIEnricher


def test_calcular_hex_score_estrutural_separa_base_ajuste_e_score_priorizacao():
    df = pd.DataFrame(
        [
            {"hex_id": "a", "renda_per_capita": 6000.0, "pop_total": 600.0},
            {"hex_id": "b", "renda_per_capita": 5000.0, "pop_total": 300.0},
            {"hex_id": "c", "renda_per_capita": 3000.0, "pop_total": 500.0},
            {"hex_id": "d", "renda_per_capita": 4000.0, "pop_total": 400.0},
            {"hex_id": "e", "renda_per_capita": 2000.0, "pop_total": 200.0},
            {"hex_id": "f", "renda_per_capita": 1000.0, "pop_total": 100.0},
        ]
    )

    resultado = calcular_hex_score_estrutural(df).set_index("hex_id")

    # Pesos vigentes: renda=0.40, pop=0.60 (aprovado diretoria 2026-04-24)
    assert resultado.loc["a", "renda_pct_nacional"] == 1.0
    assert resultado.loc["a", "pop_pct_nacional"] == 1.0
    assert resultado.loc["a", "hex_score_estrutural"] == 100.0
    assert resultado.loc["a", "ajuste_executivo"] == 5.0
    assert resultado.loc["a", "score_priorizacao"] == 100.0

    # b: renda_pct=0.8, pop_pct=0.4 → 100*(0.40*0.8 + 0.60*0.4) = 56.0
    assert resultado.loc["b", "hex_score_estrutural"] == 56.0
    assert resultado.loc["b", "ajuste_executivo"] == 2.0
    assert resultado.loc["b", "score_priorizacao"] == 58.0

    # c: renda_pct=0.4, pop_pct=0.8 → 100*(0.40*0.4 + 0.60*0.8) = 64.0
    assert resultado.loc["c", "hex_score_estrutural"] == 64.0
    assert resultado.loc["c", "ajuste_executivo"] == 1.0
    assert resultado.loc["c", "score_priorizacao"] == 65.0

    assert resultado.loc["e", "ajuste_executivo"] == -8.0
    assert resultado.loc["e", "score_priorizacao"] == 12.0
    assert resultado.loc["f", "hex_score_estrutural"] == 0.0
    assert resultado.loc["f", "score_priorizacao"] == 0.0


def test_calcular_hex_score_estrutural_exclui_hexagonos_sem_populacao():
    df = pd.DataFrame(
        [
            {"hex_id": "urbano", "renda_per_capita": 5000.0, "pop_total": 500.0},
            {"hex_id": "agua",   "renda_per_capita": 5000.0, "pop_total": 0.0},
            {"hex_id": "rural",  "renda_per_capita": 0.0,    "pop_total": 0.0},
        ]
    )
    resultado = calcular_hex_score_estrutural(df).set_index("hex_id")

    # Hexágono urbano: tem população, entra no ranking
    assert not resultado.loc["urbano", "hex_sem_populacao"]
    assert resultado.loc["urbano", "score_priorizacao"] > 0

    # Hexágonos sem população: flag True, score forçado a zero
    assert resultado.loc["agua", "hex_sem_populacao"]
    assert resultado.loc["agua", "score_priorizacao"] == 0.0
    assert resultado.loc["agua", "hex_score_estrutural"] == 0.0

    assert resultado.loc["rural", "hex_sem_populacao"]
    assert resultado.loc["rural", "score_priorizacao"] == 0.0

    # Percentis de água/rural devem ser NaN (excluídos do ranking)
    assert pd.isna(resultado.loc["agua", "renda_pct_nacional"])
    assert pd.isna(resultado.loc["rural", "pop_pct_nacional"])


def test_detecta_coluna_codigo_municipio_sidra():
    df = pd.DataFrame(
        {
            "D1C": ["5208707", "3509502", "4106902"],
            "D1N": ["Goiania", "Campinas", "Curitiba"],
            "V": ["2668.8", "2678.6", "3137.92"],
        }
    )

    assert IBGECenso._detectar_coluna_codigo_municipio(df) == "D1C"


def test_contar_academias_em_lote_respeita_raio():
    poi = POIEnricher()
    df_hex = pd.DataFrame(
        [
            {"lat": -16.6800, "lng": -49.2500},
            {"lat": -16.7000, "lng": -49.3000},
        ]
    )
    academias = [
        {"osm_id": 1, "lat": -16.6805, "lng": -49.2505},
        {"osm_id": 2, "lat": -16.8000, "lng": -49.4000},
    ]

    contagens = poi.contar_academias_em_lote(df_hex, academias=academias, raio_metros=1500)

    assert contagens.tolist() == [1, 0]


def test_resumir_validacao_nacional_detecta_anomalias_por_uf():
    df = pd.DataFrame(
        [
            {
                "uf": "GO",
                "hex_score": 80.0,
                "n_academias_osm": 2,
                "renda_per_capita": 2600.0,
                "pop_total": 1000.0,
                "lat": -16.67,
                "lng": -49.25,
            },
            {
                "uf": "GO",
                "hex_score": 60.0,
                "n_academias_osm": 1,
                "renda_per_capita": 2600.0,
                "pop_total": 900.0,
                "lat": -16.68,
                "lng": -49.26,
            },
            {
                "uf": "AC",
                "hex_score": 50.0,
                "n_academias_osm": 0,
                "renda_per_capita": 0.0,
                "pop_total": 0.0,
                "lat": -9.97,
                "lng": -67.81,
            },
            {
                "uf": "AC",
                "hex_score": 50.0,
                "n_academias_osm": 0,
                "renda_per_capita": 0.0,
                "pop_total": 0.0,
                "lat": -9.98,
                "lng": -67.82,
            },
        ]
    )

    resumo = resumir_validacao_nacional(df)

    assert resumo["total_hexagonos"] == 4
    assert resumo["preenchimento_renda_pct"] == 50.0
    assert resumo["preenchimento_pop_pct"] == 50.0
    assert any(item["uf"] == "AC" for item in resumo["anomalias_uf"])


def test_selecionar_areas_prioritarias_top_20_por_uf():
    df = pd.DataFrame(
        [
            {"hex_id": "go1", "lat": 0, "lng": 0, "uf": "GO", "regiao": "CO", "cod_municipio": "1", "nome_municipio": "A", "renda_per_capita": 1, "pop_total": 10, "populacao_proxy": 10, "fonte_demografica": "ibge", "hex_score_estrutural": 10},
            {"hex_id": "go2", "lat": 0, "lng": 0, "uf": "GO", "regiao": "CO", "cod_municipio": "1", "nome_municipio": "A", "renda_per_capita": 1, "pop_total": 20, "populacao_proxy": 20, "fonte_demografica": "ibge", "hex_score_estrutural": 20},
            {"hex_id": "go3", "lat": 0, "lng": 0, "uf": "GO", "regiao": "CO", "cod_municipio": "1", "nome_municipio": "A", "renda_per_capita": 1, "pop_total": 30, "populacao_proxy": 30, "fonte_demografica": "ibge", "hex_score_estrutural": 30},
            {"hex_id": "go4", "lat": 0, "lng": 0, "uf": "GO", "regiao": "CO", "cod_municipio": "1", "nome_municipio": "A", "renda_per_capita": 1, "pop_total": 40, "populacao_proxy": 40, "fonte_demografica": "ibge", "hex_score_estrutural": 40},
            {"hex_id": "go5", "lat": 0, "lng": 0, "uf": "GO", "regiao": "CO", "cod_municipio": "1", "nome_municipio": "A", "renda_per_capita": 1, "pop_total": 50, "populacao_proxy": 50, "fonte_demografica": "ibge", "hex_score_estrutural": 50},
            {"hex_id": "sp1", "lat": 0, "lng": 0, "uf": "SP", "regiao": "SE", "cod_municipio": "2", "nome_municipio": "B", "renda_per_capita": 1, "pop_total": 10, "populacao_proxy": 10, "fonte_demografica": "ibge", "hex_score_estrutural": 15},
            {"hex_id": "sp2", "lat": 0, "lng": 0, "uf": "SP", "regiao": "SE", "cod_municipio": "2", "nome_municipio": "B", "renda_per_capita": 1, "pop_total": 20, "populacao_proxy": 20, "fonte_demografica": "ibge", "hex_score_estrutural": 25},
            {"hex_id": "sp3", "lat": 0, "lng": 0, "uf": "SP", "regiao": "SE", "cod_municipio": "2", "nome_municipio": "B", "renda_per_capita": 1, "pop_total": 30, "populacao_proxy": 30, "fonte_demografica": "ibge", "hex_score_estrutural": 35},
            {"hex_id": "sp4", "lat": 0, "lng": 0, "uf": "SP", "regiao": "SE", "cod_municipio": "2", "nome_municipio": "B", "renda_per_capita": 1, "pop_total": 40, "populacao_proxy": 40, "fonte_demografica": "ibge", "hex_score_estrutural": 45},
            {"hex_id": "sp5", "lat": 0, "lng": 0, "uf": "SP", "regiao": "SE", "cod_municipio": "2", "nome_municipio": "B", "renda_per_capita": 1, "pop_total": 50, "populacao_proxy": 50, "fonte_demografica": "ibge", "hex_score_estrutural": 55},
        ]
    )

    priorizados, validacao = selecionar_areas_prioritarias(df, top_pct_por_uf=0.20)

    assert set(priorizados["hex_id"]) == {"go5", "sp5"}
    assert validacao["total_priorizados"] == 2
    assert validacao["pct_volume_priorizado"] == 20.0


def test_selecionar_areas_prioritarias_nao_ultrapassa_top_pct_em_bases_nao_multiplas_de_5():
    df = pd.DataFrame(
        [
            {"hex_id": f"df{i}", "lat": 0, "lng": 0, "uf": "DF", "regiao": "CO", "cod_municipio": "5300108", "nome_municipio": "Brasilia", "renda_per_capita": 1, "pop_total": i, "populacao_proxy": i, "fonte_demografica": "ibge", "hex_score_estrutural": i}
            for i in range(1, 10)
        ]
    )

    priorizados, _ = selecionar_areas_prioritarias(df, top_pct_por_uf=0.20)

    assert len(priorizados) == 1
    assert priorizados["hex_id"].tolist() == ["df9"]


def test_preparar_base_oportunidades_preenche_nome_municipio_via_lookup_ibge(monkeypatch):
    monkeypatch.setattr(
        "hex_enrichment.carregar_lookup_municipios_ibge",
        lambda: pd.DataFrame([{"cod_municipio": "3550308", "nome_municipio": "Sao Paulo"}]),
    )

    df_estrutural = pd.DataFrame(
        [
            {"hex_id": "h1", "lat": 0, "lng": 0, "uf": "SP", "regiao": "SE", "cod_municipio": "3550308", "nome_municipio": "", "renda_per_capita": 3000, "populacao_proxy": 9000, "hex_score_estrutural": 90},
        ]
    )
    df_priorizados = pd.DataFrame(
        [
            {"hex_id": "h1", "uf": "SP", "cod_municipio": "3550308", "criterio_prioridade": "top_20%_uf", "threshold_prioridade_uf": 90.0},
        ]
    )

    resultado, _ = preparar_base_oportunidades(df_estrutural, df_priorizados)

    assert resultado.loc[0, "nome_municipio"] == "Sao Paulo"
    assert resultado.loc[0, "municipio_label"] == "Sao Paulo"


def test_enriquecer_concorrencia_priorizados_explicita_erro_sem_zero_silencioso():
    df = pd.DataFrame(
        [
            {"hex_id": "ok1", "lat": -16.68, "lng": -49.25, "uf": "GO", "regiao": "CO", "cod_municipio": "1", "nome_municipio": "Ok", "hex_score_estrutural": 80.0},
            {"hex_id": "ok2", "lat": -16.69, "lng": -49.26, "uf": "GO", "regiao": "CO", "cod_municipio": "1", "nome_municipio": "Ok", "hex_score_estrutural": 70.0},
            {"hex_id": "er1", "lat": -23.55, "lng": -46.63, "uf": "SP", "regiao": "SE", "cod_municipio": "2", "nome_municipio": "Erro", "hex_score_estrutural": 90.0},
        ]
    )

    class FakePOI:
        def buscar_academias_bbox_adaptativo(self, **kwargs):
            if "cidade_SP_2" in kwargs["contexto"]:
                raise RuntimeError("timeout")
            return [{"osm_id": 1, "lat": -16.6805, "lng": -49.2505}]

        def contar_academias_em_lote(self, df_hex, academias, raio_metros=1500, chunk_size=50_000):
            assert raio_metros == 1500
            return [1] * len(df_hex)

    df_osm, metricas = enriquecer_concorrencia_priorizados(df, poi=FakePOI())

    assert set(df_osm.loc[df_osm["osm_status"] == "ok", "n_academias_osm"].tolist()) == {1}
    assert df_osm.loc[df_osm["hex_id"] == "er1", "n_academias_osm"].isna().all()
    assert df_osm.loc[df_osm["hex_id"] == "er1", "osm_status"].iloc[0] == "erro"
    assert (metricas["status"] == "erro").sum() == 1


def test_calcular_hex_score_final_normaliza_globalmente():
    df = pd.DataFrame(
        [
            {"hex_id": "a", "hex_score_estrutural": 90.0, "score_concorrencia": 10.0},
            {"hex_id": "b", "hex_score_estrutural": 60.0, "score_concorrencia": 50.0},
            {"hex_id": "c", "hex_score_estrutural": 30.0, "score_concorrencia": 90.0},
        ]
    )

    resultado = calcular_hex_score_final(df)

    assert resultado["hex_score_final"].min() == 0.0
    assert resultado["hex_score_final"].max() == 100.0


def test_preparar_base_oportunidades_classifica_regras_e_rankings():
    df_estrutural = pd.DataFrame(
        [
            {"hex_id": "h1", "lat": 0, "lng": 0, "uf": "SP", "regiao": "SE", "cod_municipio": "3550308", "nome_municipio": "", "renda_per_capita": 3000, "populacao_proxy": 9000, "hex_score_estrutural": 90},
            {"hex_id": "h2", "lat": 0, "lng": 1, "uf": "SP", "regiao": "SE", "cod_municipio": "3550308", "nome_municipio": "", "renda_per_capita": 3000, "populacao_proxy": 1000, "hex_score_estrutural": 70},
            {"hex_id": "h3", "lat": 1, "lng": 0, "uf": "RJ", "regiao": "SE", "cod_municipio": "3304557", "nome_municipio": "", "renda_per_capita": 1000, "populacao_proxy": 9000, "hex_score_estrutural": 50},
            {"hex_id": "h4", "lat": 1, "lng": 1, "uf": "RJ", "regiao": "SE", "cod_municipio": "3304557", "nome_municipio": "", "renda_per_capita": 1000, "populacao_proxy": 1000, "hex_score_estrutural": 30},
        ]
    )
    df_priorizados = pd.DataFrame(
        [
            {"hex_id": "h1", "uf": "SP", "cod_municipio": "3550308", "criterio_prioridade": "top_20%_uf", "threshold_prioridade_uf": 70.0},
            {"hex_id": "h3", "uf": "RJ", "cod_municipio": "3304557", "criterio_prioridade": "top_20%_uf", "threshold_prioridade_uf": 50.0},
        ]
    )

    resultado, validacao = preparar_base_oportunidades(df_estrutural, df_priorizados)

    h1 = resultado.loc[resultado["hex_id"] == "h1"].iloc[0]
    h2 = resultado.loc[resultado["hex_id"] == "h2"].iloc[0]
    h3 = resultado.loc[resultado["hex_id"] == "h3"].iloc[0]
    h4 = resultado.loc[resultado["hex_id"] == "h4"].iloc[0]

    assert h1["faixa_oportunidade"] == "prioridade_maxima"
    assert h2["faixa_oportunidade"] == "alta"
    assert h3["faixa_oportunidade"] == "media"
    assert h4["faixa_oportunidade"] == "descartado"

    assert h1["motivo_priorizacao"] == "combinado"
    assert h2["motivo_priorizacao"] == "renda_alta"
    assert h3["motivo_priorizacao"] == "alta_populacao"
    assert h4["motivo_priorizacao"] == "sem_destaque"

    assert bool(h1["flag_viavel"]) is True
    assert bool(h2["flag_viavel"]) is True
    assert bool(h3["flag_viavel"]) is False
    assert bool(h4["flag_viavel"]) is False

    assert h2["observacao_estrategica"] == "Alta renda, baixa densidade"
    assert h3["observacao_estrategica"] == "Regiao fora do target ideal"
    assert h4["motivo_alerta"] == "renda_baixa | baixa_densidade | score_baixo"

    assert h1["rank_brasil"] == 1
    assert h2["rank_brasil"] == 2
    assert h1["rank_uf"] == 1
    assert h2["rank_uf"] == 2
    assert h1["rank_cidade"] == 1
    assert h2["rank_cidade"] == 2
    assert bool(h1["flag_prioridade"]) is True
    assert bool(h2["flag_prioridade"]) is False
    assert h1["ajuste_executivo"] == 5.0
    assert h1["score_priorizacao"] == 95.0
    assert h1["score_oficial"] == 95.0
    assert h1["score_oficial_nome"] == "score_priorizacao"
    assert h1["osm_status"] == "nao_aplicado_mvp_nacional"
    assert bool(h1["fallback_setor_censitario"]) is True
    assert validacao["pct_viavel"] == 50.0


def test_preparar_base_oportunidades_desempata_de_forma_deterministica():
    df_estrutural = pd.DataFrame(
        [
            {"hex_id": "b", "lat": 0, "lng": 0, "uf": "SP", "regiao": "SE", "cod_municipio": "3550308", "nome_municipio": "", "renda_per_capita": 2000, "populacao_proxy": 5000, "hex_score_estrutural": 80},
            {"hex_id": "a", "lat": 0, "lng": 0, "uf": "SP", "regiao": "SE", "cod_municipio": "3550308", "nome_municipio": "", "renda_per_capita": 2000, "populacao_proxy": 5000, "hex_score_estrutural": 80},
        ]
    )
    df_priorizados = pd.DataFrame(columns=["hex_id", "uf", "cod_municipio", "criterio_prioridade", "threshold_prioridade_uf"])

    resultado, _ = preparar_base_oportunidades(df_estrutural, df_priorizados)

    assert resultado["hex_id"].tolist() == ["a", "b"]
    assert resultado["rank_brasil"].tolist() == [1, 2]
    assert resultado["rank_uf"].tolist() == [1, 2]
    assert resultado["rank_cidade"].tolist() == [1, 2]


def test_preparar_base_oportunidades_marca_sem_populacao_como_inviavel():
    df_estrutural = pd.DataFrame(
        [
            {"hex_id": "urbano", "lat": 0, "lng": 0, "uf": "SP", "regiao": "SE", "cod_municipio": "3550308", "nome_municipio": "", "renda_per_capita": 3000, "populacao_proxy": 5000, "hex_score_estrutural": 80, "hex_sem_populacao": False},
            {"hex_id": "rio",    "lat": 1, "lng": 1, "uf": "SP", "regiao": "SE", "cod_municipio": "3550308", "nome_municipio": "", "renda_per_capita": 0,    "populacao_proxy": 0,    "hex_score_estrutural": 0,  "hex_sem_populacao": True},
        ]
    )
    df_priorizados = pd.DataFrame(columns=["hex_id", "uf", "cod_municipio", "criterio_prioridade", "threshold_prioridade_uf"])

    resultado, _ = preparar_base_oportunidades(df_estrutural, df_priorizados)

    rio = resultado.loc[resultado["hex_id"] == "rio"].iloc[0]
    urbano = resultado.loc[resultado["hex_id"] == "urbano"].iloc[0]

    assert rio["faixa_oportunidade"] == "inviavel"
    assert bool(rio["flag_viavel"]) is False
    assert rio["observacao_estrategica"] == "Area inviavel (agua/rural sem populacao)"
    assert urbano["faixa_oportunidade"] != "inviavel"
