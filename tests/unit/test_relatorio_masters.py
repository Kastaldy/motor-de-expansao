"""Relatório trimestral dos masters: territórios, análises e PDF (só dados sintéticos)."""

from __future__ import annotations

import h3
import pandas as pd
import pytest

from motor_expansao.masters import analise as A
from motor_expansao.masters import area as AR
from motor_expansao.masters.gerar import (
    Base,
    _marcar_unidades_do_master,
    _regiao_dos_pontos,
    montar_dados,
)
from motor_expansao.masters.relatorio_pdf import _t, fmt_pct, fmt_reais, gerar_pdf
from motor_expansao.masters.territorios import masters_de_dict, municipios_sem_match, normalizar

CONFIG = {
    "masters": [
        {
            "id": "lit",
            "nome_planilha": "Litoral/ABC — TESTE",
            "nome_exibicao": "Litoral/ABC - TESTE",
            "regioes": [
                {
                    "id": "abcd",
                    "nome": "ABCD",
                    "tipo": "exclusividade",
                    "municipios": {"SP": ["Santo André", "São Bernardo do Campo"]},
                },
                {
                    "id": "litoral",
                    "nome": "Litoral",
                    "tipo": "exclusividade",
                    "municipios": {"SP": ["Santos", "Guarujá"]},
                },
            ],
        },
        {
            "id": "go",
            "nome_planilha": "GO — TESTE",
            "regioes": [
                {
                    "id": "go",
                    "nome": "Goiás",
                    "tipo": "exclusividade",
                    "ufs": ["GO"],
                    "excluir": {"GO": ["Formosa"]},
                }
            ],
        },
    ]
}


@pytest.fixture
def masters():
    return masters_de_dict(CONFIG)


# --------------------------------------------------------------------------- territórios


def test_normalizar_tira_acento_e_pontuacao():
    assert normalizar("São José dos Campos") == "sao jose dos campos"
    assert normalizar("Ponta da Praia - Canal 7 (Santos)") == "ponta da praia canal 7 santos"
    assert normalizar("Santa Bárbara d'Oeste") == normalizar("Santa Barbara d Oeste")


def test_regiao_por_uf_com_excecao_e_por_lista(masters):
    go, lit = masters["go"], masters["lit"]
    assert go.regiao_de("GO", "Goiânia").id == "go"
    assert go.regiao_de("GO", "Formosa") is None
    assert go.regiao_de("DF", "Brasília") is None
    assert lit.regiao_de("SP", "SANTOS").id == "litoral"
    assert lit.regiao_de("SP", "São Paulo") is None


def test_pipeline_cita_municipio_entre_parenteses_sem_confundir_santo_andre(masters):
    lit = masters["lit"]
    assert lit.regiao_do_pipeline("Ponta da Praia - Canal 7 (Santos)", "SP").id == "litoral"
    assert lit.regiao_do_pipeline("Planalto SBC (São Bernardo do Campo)", "SP").id == "abcd"
    assert lit.regiao_do_pipeline("Santo André", "SP").id == "abcd"
    assert lit.regiao_do_pipeline("Campinas", "SP") is None


def test_municipio_da_config_que_nao_existe_na_base_vira_aviso(masters):
    faltando = municipios_sem_match(
        masters["lit"], {"SP": ["Santo André", "São Bernardo do Campo", "Santos"]}
    )
    assert faltando == [("litoral", "SP", "guaruja")]


def test_master_duplicado_na_config_falha():
    with pytest.raises(ValueError):
        masters_de_dict({"masters": [CONFIG["masters"][0], CONFIG["masters"][0]]})


# --------------------------------------------------------------------------- regiões


#: Um hexágono res-7 real por município (Santos na coordenada da unidade do painel).
COORD = {
    "h1": (-23.66, -46.53, "3547809"),  # Santo André
    "h2": (-23.69, -46.56, "3548708"),  # São Bernardo do Campo
    "h3": (-23.966, -46.330, "3548500"),  # Santos
    "h4": (-23.99, -46.26, "3518701"),  # Guarujá
    "h5": (-23.55, -46.63, "3550308"),  # São Paulo
}
HEX = {k: h3.latlng_to_cell(la, lo, 7) for k, (la, lo, _) in COORD.items()}


def _mercado() -> pd.DataFrame:
    linhas = [
        # hex, uf, municipio, pop, sam, conc, ultra, livre
        ("h1", "SP", "Santo André", 1000, 500, 100, 0, 400),
        ("h2", "SP", "São Bernardo do Campo", 1000, 500, 200, 0, 300),
        ("h3", "SP", "Santos", 1000, 400, 200, 100, 100),
        ("h4", "SP", "Guarujá", 500, 100, 20, 0, 80),
        ("h5", "SP", "São Paulo", 9000, 9000, 1, 1, 8998),  # fora do território: não entra
    ]
    df = pd.DataFrame(
        linhas,
        columns=[
            "hex_id",
            "uf",
            "nome_municipio",
            "pop_hex_base",
            "sam_fitness_potencial",
            "oferta_consumida_mercado_estimada",
            "oferta_consumida_ultra_estimada",
            "oferta_efetiva_disponivel",
        ],
    )
    df["lat"] = df["hex_id"].map(lambda k: COORD[k][0])
    df["lng"] = df["hex_id"].map(lambda k: COORD[k][1])
    df["cod_municipio"] = df["hex_id"].map(lambda k: COORD[k][2])
    df["hex_id"] = df["hex_id"].map(HEX)
    df["data_snapshot_mercado"] = "2026-07-14"
    return df


def test_comparar_regioes_soma_so_o_territorio_e_ordena_por_espaco_livre(masters):
    conc = pd.DataFrame(
        {
            "concorrente_id": [1, 2, 3],
            "rede": ["x"] * 3,
            "hex_id_res7": [HEX["h1"], HEX["h3"], HEX["h5"]],
        }
    )
    r = A.comparar_regioes(_mercado(), masters["lit"], conc, None)
    assert list(r["regiao_id"]) == ["abcd", "litoral"]
    abcd = r.iloc[0]
    assert abcd["espaco_livre_alunos"] == 700
    assert abcd["pct_ocupado"] == pytest.approx(300 / 1000)
    assert abcd["n_concorrentes"] == 1
    assert r.iloc[1]["pct_ocupado"] == pytest.approx(320 / 500)
    assert abcd["unidades_teoricas"] == pytest.approx(700 / A.CAPACIDADE_UNIDADE_ALUNOS)


def test_capacidade_igual_a_do_residual():
    from motor_expansao.pipelines.calcular_colunas_mercado import (
        CAPACIDADE_DEFAULT_CONCORRENTE_ALUNOS,
    )

    assert A.CAPACIDADE_UNIDADE_ALUNOS == CAPACIDADE_DEFAULT_CONCORRENTE_ALUNOS


# --------------------------------------------------------------------------- unidades


@pytest.mark.parametrize(
    ("mes_vida", "pct", "esperado"),
    [
        (2, 99.0, "rampa"),
        (10, 80.0, "acima"),
        (10, 75.0, "acima"),
        (10, 50.0, "media"),
        (10, 25.0, "abaixo"),
        (10, float("nan"), "sem_dados"),
        (float("nan"), 50.0, "sem_dados"),
    ],
)
def test_veredito(mes_vida, pct, esperado):
    assert A.veredito(mes_vida, pct) == esperado


def _painel():
    """12 unidades de rede + 1 do master (Santos, a melhor) + 1 vizinha que abre perto dela."""
    meses = pd.period_range("2025-01", "2026-08", freq="M")
    dim, fato = [], []
    for k in range(12):
        uid = f"rede{k}"
        dim.append(
            {
                "unidade_id": uid,
                "nome": f"REDE {k}",
                "uf": "SP",
                "cidade_cadastro": "CAMPINAS",
                "inauguracao": pd.Timestamp("2022-01-01"),
                "lat": -22.9 + k,
                "lng": -47.0,
                "excluida_rede": False,
            }
        )
        for i, p in enumerate(meses):
            fato.append(
                {
                    "unidade_id": uid,
                    "competencia": str(p),
                    "mes_vida": 37 + i,
                    "mes_completo": True,
                    "pre_inauguracao": False,
                    "faturamento": 100_000 + 5_000 * k,
                    "ativos": 1000 + 50 * k,
                    "churn_pct": 6.0,
                    "nps": 50.0,
                }
            )
    dim.append(
        {
            "unidade_id": "santos",
            "nome": "SANTOS",
            "uf": "SP",
            "cidade_cadastro": "SANTOS",
            "inauguracao": pd.Timestamp("2022-01-01"),
            "lat": -23.966,
            "lng": -46.330,
            "excluida_rede": False,
        }
    )
    dim.append(
        {
            "unidade_id": "boq",
            "nome": "BOQUEIRAO",
            "uf": "SP",
            "cidade_cadastro": "SANTOS",
            "inauguracao": pd.Timestamp("2026-03-10"),
            "lat": -23.966,
            "lng": -46.323,
            "excluida_rede": False,
        }
    )
    for i, p in enumerate(meses):
        cai = p >= pd.Period("2026-03", "M")
        fato.append(
            {
                "unidade_id": "santos",
                "competencia": str(p),
                "mes_vida": 37 + i,
                "mes_completo": True,
                "pre_inauguracao": False,
                "faturamento": 400_000 * (0.8 if cai else 1.0),
                "ativos": 4000 * (0.8 if cai else 1.0),
                "churn_pct": 5.0,
                "nps": 60.0,
            }
        )
        if p >= pd.Period("2026-03", "M"):
            fato.append(
                {
                    "unidade_id": "boq",
                    "competencia": str(p),
                    "mes_vida": (p - pd.Period("2026-03", "M")).n + 1,
                    "mes_completo": True,
                    "pre_inauguracao": False,
                    "faturamento": 200_000,
                    "ativos": 2000,
                    "churn_pct": 4.0,
                    "nps": 70.0,
                }
            )
    dim = pd.DataFrame(dim)
    dim["chave_nome"] = dim["nome"].map(normalizar)
    return dim, pd.DataFrame(fato)


def _planilhas():
    inaug = pd.DataFrame(
        {
            "master_secao": ["Litoral/ABC — TESTE"] * 2,
            "unidade": ["Santos", "Boqueirão"],
            "uf": ["SP", "SP"],
            "meta": [None, None],
            "operacao": ["Litoral/ABC — TESTE"] * 2,
        }
    )
    pipe = pd.DataFrame(
        {
            "master": ["Litoral/ABC — TESTE"] * 2,
            "unidade": ["Santo André", "Ponta da Praia (Santos)"],
            "cidade": [None, None],
            "uf": ["SP", "SP"],
            "fase": ["Obras", "Minuta"],
            "dentro_territorio": ["Sim"] * 2,
        }
    )
    return inaug, pipe


def test_diagnostico_compara_na_mesma_idade_e_poe_rampa_na_nova(masters):
    dim, fato = _painel()
    inaug, _ = _planilhas()
    un, faltando = A.unidades_do_master(inaug, dim, masters["lit"])
    assert faltando == []
    assert list(un["nome_exibicao"]) == ["Santos", "Boqueirão"]
    assert set(un["regiao_nome"]) == {"Litoral"}
    dg = A.diagnostico_unidades(un, fato).set_index("unidade_id")
    assert dg.loc["santos", "veredito"] == "acima"  # 320 mil contra rede de 100-155 mil
    assert dg.loc["santos", "competencia_ref"] == "2026-08"
    assert dg.loc["boq", "mes_vida"] == 6


def test_efeito_vizinha_desconta_a_rede_e_soma_o_par(masters):
    dim, fato = _painel()
    inaug, _ = _planilhas()
    un, _ = A.unidades_do_master(inaug, dim, masters["lit"])
    ev = A.efeito_vizinhas(un, dim, fato, nomes=A.nomes_exibicao(inaug, dim))
    assert len(ev) == 1
    e = ev.iloc[0]
    assert e["vizinha_nome"] == "Boqueirão"
    assert e["distancia_km"] < 1
    assert e["var_ativos_rede"] == pytest.approx(0.0)
    assert e["efeito_ativos"] == pytest.approx(-0.2)
    assert e["var_ativos_par"] == pytest.approx((3200 + 2000) / 4000 - 1)


def test_maiores_restos_distribui_o_total_exato():
    s = A._maiores_restos(pd.Series({"a": 5.0, "b": 3.0, "c": 2.0}), 3)
    assert s.sum() == 3
    assert s["a"] >= s["b"] >= s["c"]
    assert A._maiores_restos(pd.Series({"a": 0.0}), 2).sum() == 0


# --------------------------------------------------------------------------- PDF


def test_texto_do_pdf_fica_em_latin1():
    assert _t("Litoral/ABC — GEMPRO → ok…") == "Litoral/ABC - GEMPRO -> ok..."
    assert _t("São José · 4º") == "São José · 4º"
    assert fmt_pct(0.32, sinal=True) == "+32%"
    assert fmt_reais(509_506) == "R$ 510 mil"


def test_pdf_do_master_de_ponta_a_ponta(masters):
    dim, fato = _painel()
    inaug, pipe = _planilhas()
    base = Base(
        inaug,
        pipe,
        _mercado(),
        pd.DataFrame({"concorrente_id": [], "rede": [], "hex_id_res7": []}),
        dim,
        fato,
    )
    d, aviso = montar_dados(masters["lit"], base, pd.Timestamp("2026-11-15"))
    assert aviso["pipeline_sem_regiao"] == 0
    assert d.metas_resumo["n_pipeline"] == 2
    assert d.metas["novas_buscas"].sum() == d.metas_resumo["novas_buscas"]
    pdf = gerar_pdf(d)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 20_000


# --------------------------------------------------------------------------- estudo de área


def _setor(cod_setor, cod_mun, nome_mun, bairro, lat, lng, pop, dom, renda):
    return {
        "cod_setor": cod_setor,
        "cod_municipio": cod_mun,
        "nome_municipio": nome_mun,
        "nome_bairro": bairro,
        "nome_subdistrito": None,
        "nome_distrito": None,
        "area_setor_km2_ibge": 0.5,
        "pop_total_setor_2022": pop,
        "domicilios_particulares_ocupados_setor_2022": dom,
        "avg_moradores_domicilio_setor_2022": pop / dom,
        "renda_responsavel_media_setor_2022": renda,
        "renda_per_capita_setor_2022": renda / (pop / dom),
        "bbox_minx": lng - 0.001,
        "bbox_miny": lat - 0.001,
        "bbox_maxx": lng + 0.001,
        "bbox_maxy": lat + 0.001,
    }


#: Dois setores do Gonzaga no hexágono da unidade de Santos e a Ponta da Praia noutro hexágono.
PONTA = (-23.985, -46.300)


def _malha(raiz):
    """Partições do artefato GEO de setores (uf=SP/cod_municipio=N/part-000.parquet) em `raiz`."""
    santos = [
        _setor("1", "3548500", "Santos", "Gonzaga", -23.966, -46.330, 6000, 2000, 5000.0),
        _setor("2", "3548500", "Santos", "Gonzaga", -23.9662, -46.3302, 1000, 1000, 2000.0),
        _setor("3", "3548500", "Santos", "Ponta da Praia", *PONTA, 8000, 3000, 9000.0),
    ]
    andre = [
        _setor("4", "3547809", "Santo André", "Vila Gilda", -23.66, -46.53, 3000, 1000, 20000.0)
    ]
    for cod, linhas in (("3548500", santos), ("3547809", andre)):
        pasta = raiz / "uf=SP" / f"cod_municipio={cod}"
        pasta.mkdir(parents=True)
        pd.DataFrame(linhas).to_parquet(pasta / "part-000.parquet")
    return raiz


@pytest.fixture
def renda_identidade(monkeypatch):
    """A renda exibida do setor vira a própria V06004: o teste confere a agregação, não o fator."""
    monkeypatch.setattr(AR, "renda_domiciliar_setor", lambda v, *_: v)


def test_bairros_renda_ponderada_pelos_domicilios_e_ocupado_pela_unidade(
    masters, tmp_path, renda_identidade
):
    assert h3.latlng_to_cell(*PONTA, 7) != HEX["h3"]
    mun = AR.municipios_do_territorio(_mercado(), masters["lit"])
    assert set(mun["regiao_id"]) == {"abcd", "litoral"}
    assert "3550308" not in set(mun["cod_municipio"])  # São Paulo fica fora do território
    st = AR.ler_setores(mun, _malha(tmp_path))
    b = AR.bairros(st, masters["lit"], {HEX["h3"]}).set_index("localidade")
    assert b.loc["Gonzaga", "populacao"] == 7000
    assert b.loc["Gonzaga", "renda_dom"] == pytest.approx((5000 * 2000 + 2000 * 1000) / 3000)
    assert bool(b.loc["Gonzaga", "ocupado"]) is True
    assert bool(b.loc["Ponta da Praia", "ocupado"]) is False
    assert b.loc["Vila Gilda", "regiao_nome"] == "ABCD"
    # Vila Gilda tem a maior renda, mas só 3 mil moradores: fica fora do "maior renda".
    top = AR.top_bairros_renda(b.reset_index())
    assert list(top["localidade"]) == ["Ponta da Praia", "Gonzaga"]
    v = AR.visao_municipios(st, _mercado(), masters["lit"]).set_index("nome_municipio")
    assert v.loc["Santos", "populacao"] == 15000
    assert v.loc["Santos", "espaco_livre"] == 100


def test_unidade_cai_na_regiao_pelo_municipio_da_coordenada():
    # No cadastro a "cidade" é o bairro; a coordenada está em Santos.
    un = pd.DataFrame({"cidade_cadastro": ["VILA GUANABARA"], "lat": [-23.966], "lng": [-46.330]})
    assert list(A.municipio_da_coordenada(un, _mercado())) == ["Santos"]
    assert list(A.municipio_da_coordenada(un, None)) == ["VILA GUANABARA"]


def test_unidade_do_master_casa_com_o_pino_livre_mais_perto():
    pinos = pd.DataFrame({"lat": [-23.9665, -23.9640], "lng": [-46.3296, -46.3150]})
    meus = pd.DataFrame({"lat": [-23.9665, -23.9661, -22.0], "lng": [-46.3296, -46.3230, -47.0]})
    up = _marcar_unidades_do_master(pinos, meus)
    # A 1ª fica com o pino igual; a 2ª, a 0,7 km dele, vai para o outro (0,8 km); a 3ª não tem pino.
    assert list(up["do_master"]) == [True, True, True]
    assert len(up) == 3


def test_cada_unidade_vai_para_a_area_do_hexagono_do_pino():
    """O mapa de cada área (19/11/2026, Juan: o DF/GO com um mapa para o DF e outro para Goiás)
    põe a unidade na área do hexágono do pino, a regra do relatório por área; a unidade do master
    sem pino fica com a área do hexágono mais perto."""
    m = pd.DataFrame(
        {
            "hex_id": [HEX["h1"], HEX["h3"]],
            "lat": [COORD["h1"][0], COORD["h3"][0]],
            "lng": [COORD["h1"][1], COORD["h3"][1]],
            "regiao_id": ["abcd", "litoral"],
        }
    )
    pontos = pd.DataFrame(
        {
            # O pino de Santos, com a coordenada puxada para o ABC: vale o hexágono do pino.
            "lat": [-23.70, -23.67, -23.97],
            "lng": [-46.50, -46.54, -46.33],
            "hex_id_res7": [HEX["h3"], None, None],
        }
    )
    assert _regiao_dos_pontos(pontos, m) == ["litoral", "abcd", "litoral"]
    assert _regiao_dos_pontos(pontos.iloc[:0], m) == []


def test_pdf_com_estudo_de_area(masters, tmp_path, renda_identidade):
    dim, fato = _painel()
    inaug, pipe = _planilhas()
    ultra = pd.DataFrame(
        {
            "ultra_id": ["a", "b"],
            "unidade": ["Santos", "Guarujá"],
            "uf": ["SP", "SP"],
            "lat": [-23.966, -23.99],
            "lng": [-46.330, -46.26],
            "hex_id_res7": [HEX["h3"], HEX["h4"]],
        }
    )
    base = Base(
        inaug,
        pipe,
        _mercado(),
        pd.DataFrame({"concorrente_id": [1], "rede": ["x"], "hex_id_res7": [HEX["h1"]]}),
        dim,
        fato,
        ultra=ultra,
        censo_geo_dir=_malha(tmp_path),
    )
    d, _ = montar_dados(masters["lit"], base, pd.Timestamp("2026-11-15"))
    assert d.tem_area
    # Santos casa com o pino do motor; Boqueirão, sem pino a até 1 km, entra como ponto novo.
    assert int(d.ultra_pontos["do_master"].sum()) == 2
    assert int(d.regioes.set_index("regiao_id").loc["litoral", "n_ultra"]) == 2
    pdf = gerar_pdf(d)
    assert pdf.startswith(b"%PDF")
    # Legenda do mapa do território acima do mapa (18/11): as regiões e as logos só do que existe.
    from dataclasses import replace

    from motor_expansao.masters.relatorio_pdf import legenda_do_mapa

    itens = legenda_do_mapa(d)
    # O limite de cada área e uma logo só, "Unidades" (19/11/2026, Juan: "junte os dois").
    assert itens == [*(("limite", r.nome) for r in d.master.regioes), ("unidades", "Unidades")]
    sem_ultra = legenda_do_mapa(replace(d, ultra_pontos=pd.DataFrame()))
    assert not any(tipo == "unidades" for tipo, _ in sem_ultra)
    # O contorno de cada área vem pronto, de todos os hexágonos dela.
    assert set(d.contornos) == {r.id for r in d.master.regioes}
    # As 10 páginas do modelo do estudo de área (capa ... análise de oportunidade), com o mapa e
    # os mapas de calor UMA VEZ POR ÁREA: o "lit" tem duas, então 12 (19/11/2026, Juan: "um por
    # área").
    assert pdf.count(b"/Type /Page") - pdf.count(b"/Type /Pages") == 12
    # Cada área só com o que é dela: os hexágonos, as unidades e o contorno.
    from motor_expansao.masters.relatorio_pdf import _por_area

    areas = _por_area(d)
    assert [nome for _, nome in areas] == [r.nome for r in d.master.regioes]
    for da, _ in areas:
        (r,) = da.master.regioes
        assert set(da.hexes["regiao_id"]) <= {r.id}
        assert set(da.ultra_pontos["regiao_id"]) <= {r.id}
        assert set(da.contornos) == {r.id}
    assert sum(len(da.hexes) for da, _ in areas) == len(d.hexes)


def test_referencia_ocupacao_usa_so_cidades_grandes():
    m = pd.DataFrame(
        {
            "uf": ["DF", "SP", "SP", "SP"],
            "nome_municipio": ["Brasília", "Santos", "Santos", "Cidadezinha"],
            "sam_fitness_potencial": [100_000.0, 20_000.0, 20_000.0, 1_000.0],
            "oferta_consumida_mercado_estimada": [70_000.0, 8_000.0, 4_000.0, 1_000.0],
            "oferta_consumida_ultra_estimada": [5_000.0, 0.0, 0.0, 0.0],
        }
    )
    r = A.referencia_ocupacao(m)
    assert r["n_cidades"] == 2  # a Cidadezinha (mercado de 1 mil) fica fora da régua
    assert r["mais_ocupada"] == "Brasília"
    assert r["mais_ocupada_pct"] == pytest.approx(0.75)
    assert r["mediana"] == pytest.approx((0.75 + 0.30) / 2)
    assert r["brasil"] == pytest.approx(88_000 / 141_000)


def test_progresso_da_meta_conta_atribuidas_e_as_do_contrato():
    cfg = {
        "masters": [
            {
                **CONFIG["masters"][0],
                "meta_aberturas": {
                    "quantidade": 4,
                    "prazo": "2027-03-11",
                    "conta_tambem": ["Santos"],
                },
            }
        ]
    }
    m = masters_de_dict(cfg)["lit"]
    inaug = pd.DataFrame(
        {
            "unidade": ["Santos", "Boqueirão", "Outra"],
            "meta": ["Holding (operação própria)", "Litoral/ABC — TESTE", "GO — TESTE"],
        }
    )
    pipe = pd.DataFrame({"master": ["Litoral/ABC — TESTE"] * 3, "unidade": ["a", "b", "c"]})
    r = A.progresso_meta(inaug, pipe, m, pd.Timestamp("2026-11-16"), aberturas_12m=2)
    assert r["contam"] == ["Santos", "Boqueirão"]  # Boqueirão pela planilha, Santos pelo contrato
    assert r["pct"] == pytest.approx(0.5)
    assert r["pct_com_pipeline"] == pytest.approx(5 / 4)
    assert r["faltam"] == 2
    assert r["meses_ate_prazo"] == 4
    assert r["ritmo_necessario_mes"] == pytest.approx(0.5)
    # Sem meta na config: sem %, mas com o que conta e o pipeline.
    sem = A.progresso_meta(
        inaug, pipe, masters_de_dict(CONFIG)["lit"], pd.Timestamp("2026-11-16"), 2
    )
    assert sem["quantidade"] is None and sem["n_contam"] == 1 and sem["n_pipeline"] == 3
    # Sem o painel, todas ficam sem data: os 4 trimestres do ano saem zerados.
    assert r["sem_data"] == ["Santos", "Boqueirão"] and r["n_ano"] == 0
    assert [t["acumulado"] for t in r["trimestres"]] == [0, 0, 0, 0]


def test_meta_do_ano_sobe_a_cada_trimestre_com_abertura():
    # 17/11 (Juan): a meta é anual (4 trimestres), em %, subindo a cada trimestre com abertura.
    cfg = {"masters": [{**CONFIG["masters"][0], "meta_aberturas": {"por_ano": 4}}]}
    m = masters_de_dict(cfg)["lit"]
    assert m.meta.por_ano == 4
    inaug = pd.DataFrame(
        {
            "unidade": ["Santos", "Boqueirão", "Novo Gama", "Rocinha", "Antiga"],
            "uf": ["SP", "SP", "GO", "RJ", "SP"],
            "meta": ["Litoral/ABC — TESTE"] * 5,
        }
    )
    dim = pd.DataFrame(
        {
            "chave_nome": [A.normalizar(n) for n in ("SANTOS", "BOQUEIRAO", "NOVO GAMA", "ANTIGA")],
            # Novo Gama: GO na planilha e DF no painel; o nome é único, então casa.
            "uf": ["SP", "SP", "DF", "SP"],
            "inauguracao": pd.to_datetime(["2026-02-10", "2026-08-01", "2026-09-30", "2025-05-01"]),
        }
    )
    pipe = pd.DataFrame({"master": [], "unidade": []})
    r = A.progresso_meta(inaug, pipe, m, pd.Timestamp("2026-08-15"), 0, dim)
    assert r["sem_data"] == ["Rocinha"]  # fora do painel: fica fora da conta do ano
    # A de 2025 não conta no ano; a de 30/09 ainda não abriu em 15/08 (dia do relatório).
    assert r["ano"] == 2026 and r["n_ano"] == 2 and r["pct_ano"] == pytest.approx(0.5)
    tri = [(str(t["trimestre"]), t["novas"], t["acumulado"], t["futuro"]) for t in r["trimestres"]]
    assert tri == [
        ("2026Q1", 1, 1, False),
        ("2026Q2", 0, 1, False),
        ("2026Q3", 1, 2, False),
        ("2026Q4", 0, 2, True),
    ]
    assert [t["pct"] for t in r["trimestres"]] == pytest.approx([0.25, 0.25, 0.5, 0.5])
    # O trimestre do relatório (15/08 = 3º tri) é o "atual", em andamento (17/11).
    assert [t["atual"] for t in r["trimestres"]] == [False, False, True, False]
    # Sem a meta do ano, o acumulado segue, sem %.
    sem = A.meta_do_ano([pd.Timestamp("2026-02-10")], None, pd.Timestamp("2026-03-01"))
    assert sem[0]["acumulado"] == 1 and pd.isna(sem[0]["pct"]) and sem[1]["futuro"]


def test_assinadas_por_fase_da_mais_perto_de_abrir():
    from motor_expansao.masters.relatorio_funcionamento import assinadas_por_fase

    pipe = [
        {"unidade": "Guará", "fase": "Buscando Imóvel"},
        {"unidade": "Itaipu", "fase": "sem status II"},
        {"unidade": "Tijuca", "fase": "Pré Venda"},
        {"unidade": "Itaboraí", "fase": "Obras"},
        {"unidade": "Macaé", "fase": "Obras"},
    ]
    assert assinadas_por_fase(pipe) == [
        ("Pré Venda", ["Tijuca"]),
        ("Obras", ["Itaboraí", "Macaé"]),
        ("Buscando Imóvel", ["Guará"]),
        ("sem status", ["Itaipu"]),
    ]


def _painel_completo():
    """O painel sintético com as colunas que os slides a mais leem."""
    dim, fato = _painel()
    dim = dim.assign(
        tam_metragem_m2=[1000.0 + 50 * i for i in range(len(dim))],
        iso_renda_pc__pe_15=[2000.0 + 200 * i for i in range(len(dim))],
        iso_pop__pe_15=[15_000.0] * len(dim),
        iso_n_academias__pe_15=[3.0] * len(dim),
        rampa_ativos_m1=[700.0] * len(dim),
        rampa_ativos_m3=[850.0] * len(dim),
        rampa_ativos_m6=[950.0] * len(dim),
        rampa_ativos_m12=[1000.0] * len(dim),
    )
    fato = fato.assign(
        faturamento_agregador=fato["faturamento"] * 0.2, agregadores=fato["ativos"] * 0.3
    )
    return dim, fato


def test_comportamento_por_regiao_com_a_media_da_rede(masters):
    from motor_expansao.masters import funcionamento as F

    dim, fato = _painel_completo()
    r = F.montar(masters["lit"], dim, fato, _mercado(), pd.Timestamp("2026-08-31"))
    comp = r["comportamento"]
    # A média de corte é a da rede inteira: as 13 maduras, Santos inclusive.
    assert comp["n_rede"] == 13
    grupos = {g["id"]: g for g in comp["grupos"]}
    # Santos (madura) está no Litoral; Boqueirão (6 meses) não tem os 12 meses da janela.
    assert grupos["litoral"]["n_maduras"] == 1 and grupos["abcd"]["n_maduras"] == 0
    renda = {t["col"]: t for t in grupos["litoral"]["tracos"]}["iso_renda_pc__pe_15"]
    assert renda["leitura"] == "poucas unidades" and renda["n"] == 1
    # % de alunos de agregador: as 12 de rede, fora das regiões do master.
    assert comp["pct_agregador_alunos_outras"] == pytest.approx(0.3)


def _comportamento_sintetico():
    """20 unidades maduras numa região de DF e 10 fora: renda sobe e população cai com o faturamento."""
    n_reg, n_fora = 20, 10
    ids = [f"u{i}" for i in range(n_reg + n_fora)]
    fat = [150_000.0 + 10_000 * i for i in range(n_reg)] + [250_000.0] * n_fora
    u = pd.DataFrame(
        {
            "unidade_id": ids,
            "regiao_id": ["df"] * n_reg + [None] * n_fora,
            "iso_renda_pc__pe_15": [1_000.0 + 300 * i for i in range(n_reg)] + [3_000.0] * n_fora,
            "iso_pop__carro_5": [200_000.0 - 8_000 * i for i in range(n_reg)] + [80_000.0] * n_fora,
            "tam_metragem_m2": [1_500.0] * 3 + [None] * (n_reg - 3) + [1_400.0] * n_fora,
            "rampa_ativos_m3": [1_500.0] * (n_reg + n_fora),
        }
    )
    maduras = pd.DataFrame(
        {
            "unidade_id": ids,
            "fat_mes": fat,
            "pct_agregador_alunos": [0.3] * n_reg + [0.5] * n_fora,
        }
    )
    master = masters_de_dict(
        {
            "masters": [
                {
                    "id": "df",
                    "nome_planilha": "DF — TESTE",
                    "regioes": [
                        {
                            "id": "df",
                            "nome": "Distrito Federal",
                            "tipo": "exclusividade",
                            "ufs": ["DF"],
                        }
                    ],
                }
            ]
        }
    )["df"]
    return u, maduras, master


def test_comportamento_acima_e_abaixo_da_media_com_a_forca():
    from motor_expansao.masters import funcionamento as F

    u, maduras, master = _comportamento_sintetico()
    r = F.comportamento(u, maduras, master, n_boot=300)
    media = (sum(150_000.0 + 10_000 * i for i in range(20)) + 250_000.0 * 10) / 30
    assert r["media_rede"] == pytest.approx(media)
    df = r["grupos"][0]
    assert df["id"] == "df" and df["n_maduras"] == 20
    # Acima da média (~243 mil): as 10 de faturamento a partir de 250 mil (i >= 10).
    assert (df["n_acima"], df["n_abaixo"]) == (10, 10)
    t = {x["col"]: x for x in df["tracos"]}
    assert t["iso_renda_pc__pe_15"]["acima"] == pytest.approx(1_000.0 + 300 * 14.5)
    assert t["iso_renda_pc__pe_15"]["leitura"] == "anda junto"
    # "Acerto": comparando duas unidades, a de renda maior fatura mais em 100% das vezes.
    assert t["iso_renda_pc__pe_15"]["acerto"] == pytest.approx(1.0)
    assert t["iso_pop__carro_5"]["leitura"] == "anda ao contrário"
    assert t["iso_pop__carro_5"]["acerto"] == pytest.approx(0.0)
    # O número real embaixo do selo: as 10 acima estão na metade com mais renda (e menos
    # população); sem selo de relação, sem contagem.
    assert t["iso_renda_pc__pe_15"]["do_lado"] == 10
    assert t["iso_pop__carro_5"]["do_lado"] == 10
    assert t["rampa_ativos_m3"]["do_lado"] is None
    # Estúdio fora do painel sintético: traço sem dado, nunca erro.
    assert t["cad_mod_studios"]["leitura"] == "poucas unidades"
    # Metragem em só 3 unidades da região: sem força e sem o lado de cima (menos de 5).
    assert t["tam_metragem_m2"]["leitura"] == "poucas unidades"
    assert t["tam_metragem_m2"]["n_acima"] == 0
    # Traço sem variação: a faixa não sai do zero -> sem relação clara (nunca um veredito).
    assert t["rampa_ativos_m3"]["leitura"] == "sem relação clara"
    # Só as regiões do master saem como grupo; a rede entra só na média e no mix das outras.
    assert len(r["grupos"]) == 1 and r["n_rede"] == 30
    assert df["pct_agregador_alunos"] == pytest.approx(0.3)
    assert r["pct_agregador_alunos_outras"] == pytest.approx(0.5)


def test_pdf_so_com_os_slides_a_mais(monkeypatch):
    from motor_expansao.masters import funcionamento as F

    # Região = SP inteiro: as 13 maduras do painel sintético (o mínimo de 15 vira 10 aqui).
    monkeypatch.setattr(F, "N_MIN_RELACAO", 10)
    sp = masters_de_dict(
        {
            "masters": [
                {
                    "id": "sp",
                    "nome_planilha": "Litoral/ABC — TESTE",
                    "regioes": [
                        {"id": "sp", "nome": "São Paulo", "tipo": "exclusividade", "ufs": ["SP"]}
                    ],
                }
            ]
        }
    )["sp"]
    dim, fato = _painel_completo()
    dim = dim.assign(iso_pop__carro_5=[50_000.0 + 1_000 * i for i in range(len(dim))])
    inaug, pipe = _planilhas()
    base = Base(
        inaug,
        pipe,
        _mercado(),
        pd.DataFrame({"concorrente_id": [], "rede": [], "hex_id_res7": []}),
        dim,
        fato,
    )
    d, _ = montar_dados(sp, base, pd.Timestamp("2026-11-15"), modelo="so_novos")
    pdf = gerar_pdf(d, "so_novos")
    # Por região com unidades suficientes: Padrões das unidades, Comportamento e Outros achados (a
    # rampa não sai: o painel sintético não tem unidade com o 1º ano; "O 1º ano da unidade" entrou
    # em Outros achados em 17/11); depois, a página de metas (17/11).
    assert pdf.count(b"/Type /Page") - pdf.count(b"/Type /Pages") == 4
    with pytest.raises(ValueError):
        gerar_pdf(d, "outro")


def test_regiao_sem_dado_nao_tem_slide_a_mais(masters):
    from motor_expansao.masters import funcionamento as F

    dim, fato = _painel_completo()
    fn = F.montar(masters["go"], dim, fato, _mercado(), pd.Timestamp("2026-08-31"))
    assert not F.tem_dados(fn)  # Goiás sem nenhuma unidade: a seção inteira não sai
    so = F.so_com_dados(F.montar(masters["lit"], dim, fato, _mercado(), pd.Timestamp("2026-08-31")))
    assert so["comportamento"]["grupos"] == []  # Litoral com 1 madura, ABCD sem nenhuma
    assert so["_fora"]["comportamento"] == ["ABCD", "Litoral"]
    assert so["_slides"] == {"comportamento": False}
    assert not F.tem_dados(so)


def test_numero_grande_do_comportamento_em_vezes_ou_porcentagem():
    from motor_expansao.masters.relatorio_funcionamento import comparacao

    def t(acima, abaixo, n_acima=10, n_abaixo=10):
        return {"acima": acima, "abaixo": abaixo, "n_acima": n_acima, "n_abaixo": n_abaixo}

    assert comparacao(t(4_863.0, 1_891.0)) == ("2,6×", "maior nas que faturam acima")
    assert comparacao(t(29_000.0, 124_000.0)) == ("4,3×", "menor nas que faturam acima")
    # Abaixo de 1,25x a diferença sai em %, com o lado no complemento.
    assert comparacao(t(1_694.0, 1_500.0)) == ("13%", "maior nas que faturam acima")
    assert comparacao(t(1_500.0, 1_500.0)) == ("=", "igual nos dois lados")
    # Um lado com menos de 5 unidades, ou valor sem dado: sem número grande.
    assert comparacao(t(2_000.0, 1_000.0, n_abaixo=4)) is None
    assert comparacao(t(float("nan"), 1_000.0)) is None


def test_selo_ao_contrario_sai_pelo_lado_que_fatura_mais():
    from motor_expansao.masters.relatorio_funcionamento import (
        _acerto_do_selo,
        _rotulo_leitura,
        frase_contagem,
    )

    pop = {"col": "iso_pop__carro_5", "formato": "mil", "leitura": "anda ao contrário"}
    # "Maior, fatura menos" soava como "ter população é ruim": sai "menor, fatura mais".
    assert _rotulo_leitura(pop) == "menor, fatura mais"
    assert _rotulo_leitura({**pop, "formato": "sim_nao"}) == "sem, fatura mais"
    assert _rotulo_leitura({**pop, "leitura": "anda junto"}) == "maior, fatura mais"
    # O "acontece em" do selo usa o complemento: a menor fatura mais em 75% das comparações.
    assert _acerto_do_selo({**pop, "acerto": 0.25}) == pytest.approx(0.75)
    # Embaixo do selo, o número real (17/11: "75 de cada 100" era lido como unidades da região).
    pop_df = {**pop, "do_lado": 8, "n_acima": 11, "rotulo": "População em 5 min de carro"}
    assert frase_contagem(pop_df) == (
        "**8 das 11** que faturam acima estão na metade das unidades da região com menos população"
    )
    renda = {
        "col": "iso_renda_pc__pe_15",
        "formato": "reais",
        "leitura": "anda junto",
        "do_lado": 6,
        "n_acima": 10,
    }
    assert (
        frase_contagem(renda)
        == "**6 das 10** que faturam acima estão na metade das unidades da região com mais renda"
    )
    estudio = {
        "col": "cad_mod_studios",
        "formato": "sim_nao",
        "leitura": "anda junto",
        "do_lado": 6,
        "n_acima": 8,
        "rotulo": "Tem estúdio",
    }
    assert frase_contagem(estudio) == "**6 das 8** que faturam acima têm estúdio"
    assert frase_contagem({**pop_df, "do_lado": None}) is None


def test_apresentacao_diz_o_padrao_em_palavras():
    from motor_expansao.masters.relatorio_funcionamento import frases_padrao

    def traco(col, formato, acima, abaixo, leitura):
        return {
            "col": col,
            "formato": formato,
            "acima": acima,
            "abaixo": abaixo,
            "n_acima": 11,
            "n_abaixo": 9,
            "leitura": leitura,
        }

    regiao = {
        "tracos": [
            traco("iso_pop__carro_5", "mil", 29_000.0, 124_000.0, "anda ao contrário"),
            traco("iso_renda_pc__pe_15", "reais", 4_863.0, 1_891.0, "anda junto"),
            traco("cad_mod_studios", "sim_nao", 0.91, 0.56, "sem relação clara"),
            # Selo "junto" com o valor típico apontando para o outro lado: sem o número.
            traco("tam_metragem_m2", "m2", 1_400.0, 1_500.0, "anda junto"),
        ]
    }
    assert frases_padrao(regiao) == [
        ("**menos população em 5 min de carro** (4,3× menor)", "anda ao contrário"),
        ("**mais renda por pessoa em 15 min a pé** (2,6× maior)", "anda junto"),
        ("**mais metragem**", "anda junto"),
    ]
    sem_padrao = {"tracos": [traco("cad_mod_studios", "sim_nao", 0.9, 0.5, "sem relação clara")]}
    assert frases_padrao(sem_padrao) == []


def test_veracidade_confere_com_a_pesquisa_so_no_grupo_inteiro():
    from motor_expansao.masters import funcionamento as F

    u, maduras, master = _comportamento_sintetico()
    # A região é TODO o DF da rede: confere com a medida da pesquisa para o DF.
    u = u.assign(uf=["DF"] * 20 + ["SP"] * 10)
    g = F.comportamento(u, maduras, master, n_boot=200)["grupos"][0]
    assert g["n_total"] == 20
    conf = g["conferencia"]
    assert conf["grupo"] == "DF"
    itens = {i["col"]: i for i in conf["itens"]}
    # Valor típico acima x abaixo: o da pesquisa e o de hoje (população: 84 mil x 164 mil).
    assert itens["iso_pop__carro_5"]["pesquisa"] == pytest.approx((29_037.0, 124_270.0))
    assert itens["iso_pop__carro_5"]["hoje"] == pytest.approx((84_000.0, 164_000.0))
    # A razão de hoje (0,51) passa de 25% da razão da pesquisa (0,23): não bate.
    assert itens["iso_pop__carro_5"]["bate"] is False
    # Renda de carro fora do painel sintético: sem número de hoje e sem conferência.
    assert all(pd.isna(v) for v in itens["iso_renda_pc__carro_5"]["hoje"])
    assert itens["iso_renda_pc__carro_5"]["bate"] is None
    # Uma unidade do DF fora da região: o grupo deixa de ser o da pesquisa, sem referência.
    u2 = u.assign(regiao_id=["df"] * 19 + [None] + [None] * 10)
    conf2 = F.comportamento(u2, maduras, master, n_boot=200)["grupos"][0]["conferencia"]
    assert conf2["grupo"] is None and all(i["pesquisa"] is None for i in conf2["itens"])


def test_rampa_de_maturacao_mes_sobre_o_12_e_o_marco_de_90():
    from motor_expansao.masters import funcionamento as F

    _, _, master = _comportamento_sintetico()
    linhas, unidades = [], []
    for i in range(14):
        uid = f"r{i}"
        na_regiao = i < 7
        unidades.append(
            {
                "unidade_id": uid,
                "regiao_id": "df" if na_regiao else None,
                # r6 tem data de inauguração provisória no painel: fora da rampa.
                "rampa_observavel": i != 6,
            }
        )
        ini, fim = (0.6, 1.0) if na_regiao else (0.8, 1.0)
        for k in range(1, 13):
            if i == 5 and k == 12:
                continue  # r5 sem o 12º mês fechado: fora da rampa
            linhas.append(
                {
                    "unidade_id": uid,
                    "mes_vida": k,
                    "mes_completo": True,
                    "ativos": 1000 * (ini + (fim - ini) * (k - 1) / 11),
                }
            )
    r = F.rampa(pd.DataFrame(unidades), pd.DataFrame(linhas), master)
    reg, outras = r["grupos"]["df"], r["outras"]
    assert reg["n"] == 5 and outras["n"] == 7  # r5 e r6 ficam fora
    assert reg["curva"][0] == pytest.approx(0.6) and reg["curva"][-1] == pytest.approx(1.0)
    assert outras["curva"][0] == pytest.approx(0.8)
    # 90% do 12º mês: no 10º mês na região (0,6 -> 1,0) e no 7º nas outras (0,8 -> 1,0).
    assert (reg["mes_marco"], outras["mes_marco"]) == (10, 7)
    assert reg["alunos_m12"] == pytest.approx(1000.0)


def test_padrao_de_faturamento_so_meses_inteiros_e_as_partes_do_3o_mes():
    from motor_expansao.masters import funcionamento as F

    _, _, master = _comportamento_sintetico()
    unidades, linhas = [], []
    for i in range(14):
        uid, na_regiao = f"f{i}", i < 7
        unidades.append({"unidade_id": uid, "regiao_id": "df" if na_regiao else None})
        fat0 = 0.5 if na_regiao else 0.8
        for k in range(1, 19):
            passo = min(k - 1, 11) / 11
            linhas.append(
                {
                    "unidade_id": uid,
                    "mes_vida": k,
                    "mes_completo": True,
                    "operacao_mes_cheio": k > 1,  # o mês da abertura sai parcial: fora
                    "faturamento": 100_000 * (fat0 + (1 - fat0) * passo),
                    "ativos": 1_000 * (0.8 + 0.2 * passo),
                }
            )
    r = F.padrao_faturamento(pd.DataFrame(unidades), pd.DataFrame(linhas), master)
    reg, outras = r["grupos"]["df"], r["outras"]
    assert reg["n"] == 7 and outras["n"] == 7
    assert pd.isna(reg["curva"][0])  # 1º mês parcial
    assert reg["curva"][2] == pytest.approx(0.5 + 0.5 * 2 / 11)
    assert reg["curva"][17] == pytest.approx(1.0)  # depois do 12º, o nível se mantém
    assert (reg["mes_marco"], outras["mes_marco"]) == (10, 7)
    assert (reg["cheias_m3"], reg["n_m3"]) == (0, 7)
    assert reg["alunos_m3"] == pytest.approx(0.8 + 0.2 * 2 / 11)
    # Faturamento por aluno do 3º sobre o do 12º = parte do faturamento / parte dos alunos.
    assert reg["ticket_rel_m3"] == pytest.approx((0.5 + 0.5 * 2 / 11) / (0.8 + 0.2 * 2 / 11))


def test_ocupacao_e_vizinhas_por_regiao():
    from motor_expansao.masters import funcionamento as F

    _, _, master = _comportamento_sintetico()
    u = pd.DataFrame(
        {
            "unidade_id": [f"o{i}" for i in range(8)],
            "regiao_id": ["df"] * 4 + [None] * 4,
            "tam_metragem_m2": [
                1_000.0,
                1_500.0,
                2_000.0,
                None,
                1_000.0,
                1_000.0,
                1_000.0,
                1_000.0,
            ],
            # Conta a própria unidade: 2 = uma outra Ultra a 5 min.
            "iso_n_ultra__carro_5": [2, 2, 1, 1, 1, 1, 1, 3],
        }
    )
    maduras = pd.DataFrame({"unidade_id": u["unidade_id"], "ativos": [2_000.0] * 8})
    fato = pd.DataFrame(
        [
            {
                "unidade_id": f"o{i}",
                "competencia": "2026-08",
                "mes_vida": 20,
                "mes_completo": True,
                "n_ultra_outras_abertas__carro_10": [3, 1, 0, 2, 0, 0, 0, 1][i],
                "novos_alunos": 100.0,
            }
            for i in range(8)
        ]
    )
    r = F.ocupacao_vizinhas(u, fato, maduras, master)
    reg, outras = r["grupos"]["df"], r["outras"]
    assert reg["n_densidade"] == 3 and reg["densidade"] == pytest.approx(2_000 / 1_500)
    assert outras["densidade"] == pytest.approx(2.0)
    assert (reg["viz5"], reg["n_viz5"]) == (2, 4) and (outras["viz5"], outras["n_viz5"]) == (1, 4)
    assert (reg["viz10"], reg["n_viz10"]) == (3, 4) and reg["media_viz10"] == pytest.approx(1.5)
    # Sem mês 1 a 12 no painel sintético: sem entradas do 1º ano.
    assert reg["n_entradas_com"] == 0 and pd.isna(reg["entradas_com"])


def test_faturamento_e_tendencia_mesmas_unidades_e_faixas_de_renda():
    from motor_expansao.masters import funcionamento as F

    _, _, master = _comportamento_sintetico()
    n_reg, n_fora = 16, 6
    ids = [f"t{i}" for i in range(n_reg + n_fora)]
    u = pd.DataFrame(
        {
            "unidade_id": ids,
            "regiao_id": ["df"] * n_reg + [None] * n_fora,
            "iso_renda_pc__pe_15": [1_000.0 + 500 * i for i in range(n_reg)] + [2_000.0] * n_fora,
        }
    )
    maduras = pd.DataFrame(
        {
            "unidade_id": ids,
            "fat_mes": [100_000.0 + 10_000 * i for i in range(n_reg)] + [200_000.0] * n_fora,
            "ativos": [1_000.0] * (n_reg + n_fora),
        }
    )
    linhas = []
    for i, uid in enumerate(ids):
        for comp, fator in (("2025-06", 1.0), ("2025-07", 1.0), ("2025-08", 1.0)) + tuple(
            (c, 1.1 if i < n_reg else 0.9) for c in ("2026-06", "2026-07", "2026-08")
        ):
            linhas.append(
                {
                    "unidade_id": uid,
                    "competencia": comp,
                    "mes_vida": 20 if comp < "2026" else 32,
                    "mes_completo": True,
                    "faturamento": 100_000 * fator,
                    "ativos": 1_000.0,
                    "pagantes": 600.0,
                    "agregadores": 400.0,
                    "churn_pct": 6.0,
                    "novos_alunos": 100.0,
                }
            )
    r = F.faturamento_tendencia(
        u, pd.DataFrame(linhas), maduras, master, pd.Timestamp("2026-08-31")
    )
    reg, outras = r["grupos"]["df"], r["outras"]
    # Mesmas unidades, um ano depois: +10% na região, -10% nas outras.
    assert reg["var"]["faturamento"] == pytest.approx(0.10) and reg["cresceram"] == n_reg
    assert outras["var"]["faturamento"] == pytest.approx(-0.10) and outras["cresceram"] == 0
    assert reg["var"]["pagantes"] == pytest.approx(0.0)
    # Três faixas de renda com o faturamento subindo junto.
    fats = [t["fat"] for t in reg["tercos_renda"]]
    assert len(fats) == 3 and fats[0] < fats[1] < fats[2]
    # Calendário: só junho a agosto têm unidades suficientes, iguais à média delas.
    assert reg["calendario"][5] == pytest.approx(0.0) and pd.isna(reg["calendario"][0])


def test_ritmo_no_slide_da_rampa_e_o_resto_no_primeiro_ano():
    from motor_expansao.masters.relatorio_funcionamento import ritmo_maturacao

    def curva(*v, ate=12):
        return list(v) + [1.0] * (ate - len(v))

    # Números do DF de hoje: alunos a 90% no 6º mês (resto, 4º); faturamento no 10º (resto, 7º).
    rp = {
        "n": 18,
        "curva": curva(0.66, 0.75, 0.81, 0.87, 0.88, 0.90, 0.92, 0.98),
        "mes_marco": 6,
        "ja_no_marco": 10,
    }
    rp_resto = {"n": 33, "curva": curva(0.77, 0.85, 0.88, 0.90), "mes_marco": 4}
    ft = {
        "n": 18,
        "curva": curva(0.41, 0.59, 0.64, 0.70, 0.77, 0.81, 0.86, 0.88, 0.89, 0.92, ate=17) + [0.99],
        "mes_marco": 10,
        "ja_no_marco": 12,
        "alunos_m3": 0.81,
        "ticket_rel_m3": 0.81,
    }
    ft_resto = {
        "n": 33,
        "curva": curva(0.58, 0.73, 0.81, ate=17) + [0.93],
        "mes_marco": 7,
        "alunos_m3": 0.88,
        "ticket_rel_m3": 0.93,
    }
    r = ritmo_maturacao(rp, rp_resto, ft, ft_resto)
    # A frase-resumo vai para o slide da rampa (Juan, 17/11: "serve muito como o resumo").
    assert r["manchete"] == (
        "Nesta região, os alunos demoram um pouco mais para chegar e o "
        "faturamento demora mais para estabilizar."
    )
    # Leitura direta: em quantos meses estabiliza, região x resto da rede.
    assert r["itens"] == [
        {"chave": "alunos", "meses": 6, "resto": 4, "estavel": True, "ja": 10, "n": 18},
        {"chave": "faturamento", "meses": 10, "resto": 7, "estavel": True, "ja": 12, "n": 18},
    ]


def test_conclusao_em_pontos_e_a_frase_final():
    from motor_expansao.masters.relatorio_funcionamento import CONCLUSAO, textos_conclusao

    df = {"conferencia": {"grupo": "DF"}}
    reg = {
        "n_var": 14,
        "app_ja_tinha": 14,
        "var": {"faturamento": 0.07, "agregadores": 0.37},
    }
    pontos = textos_conclusao(df, reg, 0.35)
    # Faturamento e renda saíram (17/11): ficam os alunos de app e quem entra na inauguração.
    assert len(pontos) == 2
    # Agregadores (17/11: "agregadores", não "alunos de app"): cresceram nas mesmas unidades, que já
    # aceitavam agregadores (não foi "liberar o app").
    # Sem o resto da rede (17/11: tirar "(resto da rede: +7%)" e "(resto da rede: 49%)").
    assert pontos[0] == (
        "**Agregadores:** cresceram 37% em 12 meses, nas mesmas unidades, que já aceitavam "
        "agregadores um ano antes; hoje são 35% dos alunos."
    )
    assert pontos[1].startswith(
        "**Quem entra na inauguração fica mais:** numa inauguração com 1.500 alunos, cerca de 120 a mais"
    )
    # Outra Ultra a até 5 min entra como 3º ponto (17/11: "junte o slide 4 no 5").
    com_viz = textos_conclusao(df, reg, 0.35, {"viz5": 11, "n_viz5": 28})
    assert com_viz[:2] == pontos
    assert com_viz[2] == (
        "**Outra Ultra a até 5 min de carro:** a unidade nova recebe cerca de 15% menos alunos novos "
        "no 1º ano. Na região, 11 das 28 estão assim."
    )
    # Alguma unidade sem app um ano antes: a frase não afirma que todas já aceitavam.
    assert "já aceitavam" not in textos_conclusao(df, {**reg, "app_ja_tinha": 12}, 0.35)[0]
    # SP: retenção sem diferença clara (+1,9 em 7 de 13) = o ponto não sai (18/11, Juan: tirar "Quem
    # entra na inauguração fica quase igual").
    sp = textos_conclusao({"conferencia": {"grupo": "SP"}}, reg, 0.57)
    assert len(sp) == 1 and not any("inauguração" in p for p in sp)
    # Outra Ultra a até 5 min só no DF (18/11, Juan: "tire de SP e mantenha em DF"): o -15% é da rede,
    # puxado pelo DF; em SP e em região fora dos grupos da pesquisa, o ponto não sai.
    viz = {"viz5": 2, "n_viz5": 30}
    assert len(textos_conclusao({"conferencia": {"grupo": "SP"}}, reg, 0.57, viz)) == 1
    assert len(textos_conclusao({"conferencia": {"grupo": None}}, reg, 0.57, viz)) == 2
    # A frase final de toda região, com o uso: ajudar na abertura de outras unidades.
    assert CONCLUSAO == (
        "Esta análise não é uma regra nem uma receita para faturar mais: é um padrão que encontramos "
        "nas unidades desta região, que pode ajudar na abertura de outras unidades."
    )


def test_ja_estabilizadas_conta_unidade_a_unidade():
    from motor_expansao.masters import funcionamento as F

    # Três unidades: a 1ª passa de 90% no 2º mês, a 2ª no 6º, a 3ª só no 12º.
    frac = pd.DataFrame(
        [
            [0.5, 0.95] + [1.0] * 10,
            [0.5, 0.6, 0.7, 0.8, 0.85, 0.91] + [1.0] * 6,
            [0.5] * 11 + [1.0],
        ],
        columns=range(1, 13),
    )
    assert F._ja_estabilizadas(frac, 6) == 2
    assert F._ja_estabilizadas(frac, 12) == 3
    assert F._ja_estabilizadas(frac, None) == 0


def test_mapas_de_calor_usam_as_reguas_do_motor():
    # 17/11 (Juan): cores, faixas e números do motor nos mapas de calor, no lugar dos quintis.
    from motor_expansao.dashboard.constants import (
        OFERTA_DISPONIVEL_ALUNOS_BANDS,
        RENDA_MEDIA_DOMICILIAR_BANDS,
    )
    from motor_expansao.masters.relatorio_pdf import (
        CONC_1KM_BANDS,
        _sobre_branco,
        classes_do_motor,
    )

    renda = pd.Series([1500.0, 2000.0, 2001.0, 9000.0, 20_000.0, float("nan")])
    cores, legenda = classes_do_motor(renda, RENDA_MEDIA_DOMICILIAR_BANDS)
    esperado = [_sobre_branco(c) for _, _, c in RENDA_MEDIA_DOMICILIAR_BANDS]
    # Até 2.000 inclusive na 1ª faixa (como `valor <= corte` no mapa); 9.000 na 4ª; 20.000 no topo.
    assert [tuple(c) for c in cores[:5]] == [pytest.approx(esperado[i]) for i in (0, 0, 1, 3, 4)]
    assert [r for _, r in legenda] == [
        "até R$ 2.000",
        "R$ 2.001-4.000",
        "R$ 4.001-8.000",
        "R$ 8.001-14.000",
        ">R$ 14.000",
        "sem dado",
    ]
    # Espaço livre: o 0 é a faixa "sem residual" do próprio motor.
    _, leg_ofer = classes_do_motor(pd.Series([0.0, 3000.0]), OFERTA_DISPONIVEL_ALUNOS_BANDS)
    assert leg_ofer[0][1] == "sem residual" and len(leg_ofer) == 6
    # Concorrentes que alcançam o hexágono: 1, 2, 3 e 4 ou mais; o zero vira "nenhuma".
    _, leg_conc = classes_do_motor(pd.Series([0, 1, 5]), CONC_1KM_BANDS, zero="nenhuma")
    assert [r for _, r in leg_conc] == [
        "nenhuma",
        "1 concorrente",
        "2 concorrentes",
        "3 concorrentes",
        "4 ou mais",
    ]


def test_escala_de_concorrentes_igual_a_do_mapa_web():
    # A escala de concorrentes a 1 km existe no mapa web (`CONC_1KM_HEX`); a cópia do relatório
    # tem que andar junto (mesma trava de `test_paridade_paleta_web.py` para o score).
    import re
    from pathlib import Path

    from motor_expansao.masters.relatorio_pdf import CONC_1KM_HEX, CONC_1KM_ROTULOS

    ts = Path(__file__).resolve().parents[2] / "web" / "src" / "lib" / "colors.ts"
    if not ts.is_file():
        pytest.skip("piloto web ausente nesta árvore")
    fonte = ts.read_text(encoding="utf-8")
    cores = re.search(r"export const CONC_1KM_HEX = \[([^\]]*)\]", fonte)
    rotulos = re.search(r"export const CONC_1KM_ROTULOS = \[([^\]]*)\]", fonte)
    assert cores and rotulos
    assert tuple(re.findall(r"'(#[0-9A-Fa-f]{6})'", cores.group(1))) == CONC_1KM_HEX
    assert tuple(re.findall(r"'([^']+)'", rotulos.group(1))) == CONC_1KM_ROTULOS


def test_relatorio_de_uma_regiao_do_master():
    # 17/11 (Juan): o RJ/SP 01 juntava RJ e SP; tem que sair um relatório por região.
    import h3

    from motor_expansao.masters.gerar import _regiao_das_inauguradas, so_a_regiao

    cfg = {
        "masters": [
            {
                **CONFIG["masters"][0],
                "meta_aberturas": {
                    "quantidade": 5,
                    "por_ano": 2,
                    "prazo": "2027-03-11",
                    "conta_tambem": ["Santos"],
                },
            }
        ]
    }
    m = masters_de_dict(cfg)["lit"]
    sub = so_a_regiao(m, "litoral")
    assert sub.id == "lit_litoral" and [r.id for r in sub.regioes] == ["litoral"]
    assert sub.nome_exibicao == "Litoral/ABC - TESTE · Litoral"
    # A meta do contrato é do master inteiro: no relatório de uma região, só o prazo e quem conta.
    assert sub.meta.quantidade is None and sub.meta.por_ano is None
    assert sub.meta.prazo == "2027-03-11" and sub.meta.conta_tambem == ("Santos",)
    # A região de cada inaugurada sai da coordenada do painel e do município do hexágono.
    santos, andre = (-23.96, -46.33), (-23.66, -46.53)
    mercado = pd.DataFrame(
        {
            "hex_id": [h3.latlng_to_cell(*santos, 7), h3.latlng_to_cell(*andre, 7)],
            "nome_municipio": ["Santos", "Santo André"],
        }
    )
    dim = pd.DataFrame(
        {
            "chave_nome": [A.normalizar("Gonzaga"), A.normalizar("Centro SA")],
            "uf": ["SP", "SP"],
            "lat": [santos[0], andre[0]],
            "lng": [santos[1], andre[1]],
            "cidade_cadastro": [None, None],
        }
    )
    inaug = pd.DataFrame({"unidade": ["Gonzaga", "Centro SA", "Fora do painel"], "uf": ["SP"] * 3})
    # Sem o painel e com a UF em duas regiões, não dá para dizer: fica fora dos dois relatórios.
    assert list(_regiao_das_inauguradas(inaug, dim, m, mercado)) == ["litoral", "abcd", None]


def test_ate_quando_a_analise_de_padroes_vale():
    """18/11 (Juan): até quando a análise vale e quando pode ser refeita com mais unidades."""
    from motor_expansao.masters import funcionamento as F
    from motor_expansao.masters.relatorio_funcionamento import texto_validade
    from motor_expansao.masters.territorios import masters_de_dict

    master = masters_de_dict(
        {
            "masters": [
                {
                    "id": "m",
                    "nome_planilha": "M",
                    "nome_exibicao": "M",
                    "regioes": [{"id": "df", "nome": "Distrito Federal", "ufs": ["DF"]}],
                }
            ]
        }
    )["m"]
    u = pd.DataFrame({"unidade_id": ["a", "b", "c"], "regiao_id": ["df", "df", None]})
    fato = pd.DataFrame(
        {
            "unidade_id": ["a", "a", "b", "b", "c"],
            "competencia": ["2020-01", "2020-02", "2026-08", "2026-09", "2027-01"],
            "pre_inauguracao": [False, False, True, False, False],
        }
    )
    # "b" abre em set/2026 (ago/2026 era pré-inauguração): fecha 12 meses com os dados de ago/2027.
    val = F.validade(u, fato, master)["df"]
    assert val == {"n": 2, "mes_todas": "2027-08"}
    g = {"n_maduras": 1, "rotulo": "Distrito Federal"}
    texto = texto_validade(g, val, pd.Timestamp("2026-08-31"), pd.Timestamp("2026-11-18"))
    assert texto == (
        "Esta análise usou 1 das 2 unidades da região (dados até ago/2026). Vale até o "
        "relatório do 4º trimestre de 2027, quando as 2 terão 12 meses de dados e ela poderá ser "
        "refeita com todas."
    )
    # Todas já com 12 meses: só quantas e até quando são os dados.
    todas = texto_validade(
        {**g, "n_maduras": 2}, val, pd.Timestamp("2027-08-31"), pd.Timestamp("2027-11-18")
    )
    assert todas == "Esta análise usou as 2 unidades da região (dados até ago/2027)."
    assert texto_validade(g, None, pd.Timestamp("2026-08-31"), pd.Timestamp("2026-11-18")) is None


def test_pdf_do_master_em_memoria_sem_gravar_nada(masters, monkeypatch, tmp_path):
    """O que o botão da tela Masters pede ao piloto (BLK-MASTERS-04): o PDF em memória, com o nome
    do arquivo, a partir das tabelas da ingestão (e não da planilha crua), sem gravar nada."""
    from motor_expansao.masters import gerar as G

    dim, fato = _painel()
    inaug, pipe = _planilhas()
    recebido = {}

    def base_falsa(e, ms, planilha=None):
        recebido["planilha"], recebido["masters"] = planilha, [m.id for m in ms]
        vazio = pd.DataFrame({"concorrente_id": [], "rede": [], "hex_id_res7": []})
        return Base(*planilha, _mercado(), vazio, dim, fato)

    monkeypatch.setattr(G, "carregar_base", base_falsa)
    entradas = G.Entradas(
        planilha=tmp_path / "nao_existe.xlsx",
        territorios=tmp_path / "t.json",
        mercado=tmp_path / "m.parquet",
        concorrentes=tmp_path / "c.parquet",
        dim_unidade=tmp_path / "d.parquet",
        fato_unidade_mes=tmp_path / "f.parquet",
    )
    pdf, nome = G.pdf_do_master(
        entradas,
        masters["lit"],
        pd.Timestamp("2026-11-15"),
        planilha=(inaug, pipe),
        # O fato sintético não tem as colunas dos padrões; o caminho em memória é o mesmo.
        modelo="antigo",
    )
    assert pdf.startswith(b"%PDF") and len(pdf) > 20_000
    assert nome == "relatorio_master_lit_2026T4.pdf"
    assert recebido["planilha"][0] is inaug and recebido["masters"] == ["lit"]
    assert list(tmp_path.iterdir()) == []  # nada gravado


def test_top5_bairros_e_a_regra_do_slide_e_da_tela() -> None:
    """Os Top 5 do slide e o cartão "Alta renda" da Análise de Oportunidade (que a tela do master
    também mostra) saem da mesma função: só bairros sem Ultra; por população, a ordem dos
    bairros; por renda, só os de `POP_MIN_BAIRRO` habitantes ou mais."""
    from motor_expansao.masters.relatorio_pdf import top5_bairros

    b = pd.DataFrame(
        {
            "localidade": ["A", "B", "C", "D", "E", "F", "G"],
            "populacao": [90_000, 80_000, 70_000, 60_000, 50_000, 40_000, 3_000],
            "renda_dom": [2_000.0, 9_000.0, 4_000.0, 7_000.0, 3_000.0, 8_000.0, 50_000.0],
            "ocupado": [False, True, False, False, False, False, False],
        }
    )
    assert list(top5_bairros(b, "populacao")["localidade"]) == ["A", "C", "D", "E", "F"]
    # G (3 mil habitantes) não entra por renda; B tem Ultra.
    assert list(top5_bairros(b, "renda")["localidade"]) == ["F", "D", "C", "E", "A"]
    # Master sem região: sem bairros, sem quebrar (a tela pede a análise; o PDF nem chega lá).
    assert top5_bairros(pd.DataFrame(), "renda").empty
    assert top5_bairros(pd.DataFrame(), "populacao").empty
