"""Testes unitarios do dataset de validacao (BLK-SCORE-01).

APENAS fixtures sinteticas (jamais dados reais; o CI nao tem as fontes gitignored).
Cobre os casos do plano de teste do handoff (com itens 11'/12'/13' da REVISAO 2).
"""

from __future__ import annotations

import pandas as pd
import pytest

from analysis import build_validation_dataset as bvd


# --------------------------------------------------------------------------- #
# normalize_name / normalize_name_skyfit
# --------------------------------------------------------------------------- #
def test_normalize_name_colapsa_acentos_caixa_sufixos():
    a = bvd.normalize_name("Academia Engenharia do Corpo LTDA")
    b = bvd.normalize_name("ENGENHARIA DO CORPO")
    assert a == b == "engenharia do corpo"


def test_normalize_name_skyfit_marca_e_uf():
    # item 11': NOMENCLATURA UNIDADE vs nome_unidade colapsam para a mesma chave
    a = bvd.normalize_name_skyfit("SKYFIT ACADEMIA - ILHA DO GOVERNADOR")
    b = bvd.normalize_name_skyfit("Ilha do Governador (RJ)")
    assert a == b == "ilha do governador"


# --------------------------------------------------------------------------- #
# match_skyfit_coords (item 12') — 4 tiers
# --------------------------------------------------------------------------- #
def _coords_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "nome_unidade": [
                "Ilha do Governador (RJ)",
                "Centro - Sete Lagoas (MG)",
                "Bairro Distante (SP)",
            ],
            "latitude": [-22.80, -19.46, -23.55],
            "longitude": [-43.20, -44.24, -46.63],
            "data_coleta": ["2026-05-26"] * 3,
        }
    )


def test_match_skyfit_coords_nome_exato():
    desf = pd.DataFrame(
        {
            "nome_unidade": ["SKYFIT ACADEMIA - ILHA DO GOVERNADOR"],
            "cidade": ["RIO DE JANEIRO"],
            "uf": ["RJ"],
        }
    )
    out = bvd.match_skyfit_coords(desf, _coords_fixture())
    assert out.loc[0, "hex_origem"] == "nome_exato"
    assert out.loc[0, "hex_precisao"] == "unidade"
    assert out.loc[0, "lat"] == pytest.approx(-22.80)


def test_match_skyfit_coords_nome_fuzzy():
    # pequena variacao grafica -> casa por difflib (cutoff default 0.84)
    desf = pd.DataFrame(
        {
            "nome_unidade": ["SKYFIT ACADEMIA - ILHA DO GOVERNADORR"],
            "cidade": ["RIO DE JANEIRO"],
            "uf": ["RJ"],
        }
    )
    out = bvd.match_skyfit_coords(desf, _coords_fixture())
    assert out.loc[0, "hex_origem"] == "nome_fuzzy"
    assert out.loc[0, "hex_precisao"] == "unidade"


def test_match_skyfit_coords_cidade_centroide():
    # nome nao casa (nem fuzzy), mas cidade+UF batem com a entrada de coords
    desf = pd.DataFrame(
        {
            "nome_unidade": ["SKYFIT ACADEMIA - SHOPPING QUALQUER"],
            "cidade": ["Sete Lagoas"],
            "uf": ["MG"],
        }
    )
    out = bvd.match_skyfit_coords(desf, _coords_fixture())
    assert out.loc[0, "hex_origem"] == "cidade_centroide"
    assert out.loc[0, "hex_precisao"] == "cidade"
    assert out.loc[0, "lat"] == pytest.approx(-19.46)


def test_match_skyfit_coords_nao_resolvido():
    desf = pd.DataFrame(
        {
            "nome_unidade": ["SKYFIT ACADEMIA - INEXISTENTE"],
            "cidade": ["Cidade Fantasma"],
            "uf": ["AC"],
        }
    )
    out = bvd.match_skyfit_coords(desf, _coords_fixture())
    assert out.loc[0, "hex_origem"] == "nao_resolvido"
    assert out.loc[0, "hex_precisao"] == "indisponivel"
    assert pd.isna(out.loc[0, "lat"])


def test_match_skyfit_coords_fora_da_faixa_brasil_nao_resolve():
    # item 13': coord fora da faixa Brasil -> nao resolve
    coords = pd.DataFrame(
        {
            "nome_unidade": ["Lugar Errado (RJ)"],
            "latitude": [48.85],  # Paris
            "longitude": [2.35],
            "data_coleta": ["2026-05-26"],
        }
    )
    desf = pd.DataFrame(
        {"nome_unidade": ["SKYFIT ACADEMIA - LUGAR ERRADO"], "cidade": ["X"], "uf": ["RJ"]}
    )
    out = bvd.match_skyfit_coords(desf, coords)
    assert out.loc[0, "hex_origem"] == "nao_resolvido"
    assert pd.isna(out.loc[0, "lat"])


# --------------------------------------------------------------------------- #
# normalize_name_engcorpo (BLK-SCORE-01a)
# --------------------------------------------------------------------------- #
def test_normalize_name_engcorpo_remove_prefixo_ec_ecb():
    # EC / ECB (planilha) vs nome cru (CSV/staging) colapsam para a mesma chave
    a = bvd.normalize_name_engcorpo("EC - VACARIA, RS")
    b = bvd.normalize_name_engcorpo("ECB - VACARIA, RS")
    c = bvd.normalize_name_engcorpo("Vacaria, RS")
    assert a == b == c == "vacaria rs"


def test_normalize_name_engcorpo_nao_corrompe_ec_interno():
    # so o PREFIXO inicial e removido; 'ec' no meio do nome permanece
    assert bvd.normalize_name_engcorpo("Recife, PE") == "recife pe"
    # token 'ec' isolado e dropado por normalize_name, mas 'recife' fica intacto
    assert "recife" in bvd.normalize_name_engcorpo("EC - Recife, PE")


# --------------------------------------------------------------------------- #
# match_engcorpo_coords (BLK-SCORE-01a) — cascata determinista
# --------------------------------------------------------------------------- #
def _engcorpo_coords_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "nome_unidade": [
                "Vacaria, RS",
                "Esplanada - Caxias do Sul, RS",
                "CT Areias - São José, SC",  # coord invertida (lat/lng trocados)
            ],
            "latitude": [-28.50, -29.19, -48.63],  # 3a fora da faixa (lat<-34)
            "longitude": [-50.93, -51.20, -27.56],
            "data_coleta": ["2026-05-26"] * 3,
        }
    )


def test_match_engcorpo_coords_nome_exato():
    desf = pd.DataFrame(
        {"nome_unidade": ["EC - VACARIA, RS"], "metragem_m2": [1000.0], "alunos_totais": [500.0]}
    )
    out = bvd.match_engcorpo_coords(desf, _engcorpo_coords_fixture())
    assert out.loc[0, "hex_origem"] == "nome_exato"
    assert out.loc[0, "hex_precisao"] == "unidade"
    assert out.loc[0, "lat"] == pytest.approx(-28.50)
    # colunas de desfecho preservadas
    assert out.loc[0, "metragem_m2"] == 1000.0


def test_match_engcorpo_coords_fuzzy_aceito_quando_cidade_uf_batem():
    # variacao grafica no nome completo + MESMA cidade+UF -> casa por fuzzy.
    # (cidade extraida = ultimo segmento apos hifen = "caxias do sul" nos dois lados)
    coords = pd.DataFrame(
        {
            "nome_unidade": ["Centro - Caxias do Sul, RS"],
            "latitude": [-29.14],
            "longitude": [-51.13],
            "data_coleta": ["2026-05-26"],
        }
    )
    desf = pd.DataFrame({"nome_unidade": ["EC - Cetro - Caxias do Sul, RS"]})
    out = bvd.match_engcorpo_coords(desf, coords)
    assert out.loc[0, "hex_origem"] == "nome_fuzzy"
    assert out.loc[0, "hex_precisao"] == "unidade"


def test_match_engcorpo_coords_fuzzy_rejeitado_quando_cidade_ou_uf_divergem():
    # nome fuzzy-proximo MAS cidade/UF diferentes -> NAO casa por fuzzy
    coords = pd.DataFrame(
        {
            "nome_unidade": ["Vacariaa, SC"],  # nome quase igual, UF diferente
            "latitude": [-27.00],
            "longitude": [-49.00],
            "data_coleta": ["2026-05-26"],
        }
    )
    desf = pd.DataFrame({"nome_unidade": ["EC - VACARIA, RS"]})
    out = bvd.match_engcorpo_coords(desf, coords)
    assert out.loc[0, "hex_origem"] != "nome_fuzzy"
    assert out.loc[0, "hex_origem"] == "nao_resolvido"


def test_match_engcorpo_coords_cidade_centroide():
    # nome nao casa (nem fuzzy) mas cidade+UF batem -> centroide
    coords = pd.DataFrame(
        {
            "nome_unidade": ["Diamantino - Caxias do Sul, RS"],
            "latitude": [-29.14],
            "longitude": [-51.13],
            "data_coleta": ["2026-05-26"],
        }
    )
    desf = pd.DataFrame({"nome_unidade": ["EC - SHOPPING INEXISTENTE - Caxias do Sul, RS"]})
    out = bvd.match_engcorpo_coords(desf, coords)
    assert out.loc[0, "hex_origem"] == "cidade_centroide"
    assert out.loc[0, "hex_precisao"] == "cidade"
    assert out.loc[0, "lat"] == pytest.approx(-29.14)


def test_match_engcorpo_coords_nao_resolvido():
    desf = pd.DataFrame({"nome_unidade": ["EC - LUGAR FANTASMA, AC"]})
    out = bvd.match_engcorpo_coords(desf, _engcorpo_coords_fixture())
    assert out.loc[0, "hex_origem"] == "nao_resolvido"
    assert out.loc[0, "hex_precisao"] == "indisponivel"
    assert pd.isna(out.loc[0, "lat"])


def test_match_engcorpo_coords_coord_fora_faixa_brasil():
    # caso CT Areias: lat/lng invertidos -> lat fora da faixa -> nao resolve
    desf = pd.DataFrame({"nome_unidade": ["EC - AREIAS, SC"]})
    # nome bate (CT Areias - São José, SC), mas a coord esta fora da faixa Brasil
    out = bvd.match_engcorpo_coords(desf, _engcorpo_coords_fixture())
    assert out.loc[0, "hex_origem"] == "nao_resolvido"
    assert pd.isna(out.loc[0, "lat"])


def test_match_engcorpo_coords_determinismo():
    desf = pd.DataFrame(
        {"nome_unidade": ["EC - VACARIA, RS", "EC - LUGAR FANTASMA, AC"]}
    )
    coords = _engcorpo_coords_fixture()
    o1 = bvd.match_engcorpo_coords(desf, coords)
    o2 = bvd.match_engcorpo_coords(desf, coords)
    assert o1["hex_origem"].tolist() == o2["hex_origem"].tolist()
    assert o1["lat"].fillna(-999).tolist() == o2["lat"].fillna(-999).tolist()


# --------------------------------------------------------------------------- #
# resolve_hex
# --------------------------------------------------------------------------- #
def test_resolve_hex_valido_e_nulo():
    pytest.importorskip("h3")
    df = pd.DataFrame(
        {
            "rede": ["ultra", "ultra"],
            "hex_id": [None, None],
            "lat": [-23.55, None],
            "lng": [-46.63, None],
        }
    )
    out = bvd.resolve_hex(df)
    assert out.loc[0, "hex_resolvido"] is True or bool(out.loc[0, "hex_resolvido"])
    assert out.loc[0, "hex_id"]
    assert not bool(out.loc[1, "hex_resolvido"])
    assert out.loc[1, "hex_id"] is None


def test_resolve_hex_preserva_existente():
    df = pd.DataFrame(
        {"rede": ["engcorpo"], "hex_id": ["87a90a010ffffff"], "lat": [None], "lng": [None]}
    )
    out = bvd.resolve_hex(df)
    assert out.loc[0, "hex_id"] == "87a90a010ffffff"
    assert bool(out.loc[0, "hex_resolvido"])
    assert out.loc[0, "hex_origem"] == "hex_staging"


# --------------------------------------------------------------------------- #
# join_scores
# --------------------------------------------------------------------------- #
def test_join_scores_presente_e_ausente():
    df = pd.DataFrame({"rede": ["skyfit", "skyfit"], "hex_id": ["HEXA", "HEXB"]})
    prio = pd.DataFrame({"hex_id": ["HEXA"], "score_priorizacao": [70.0],
                         "cod_municipio": ["3550308"], "nome_municipio": ["Sao Paulo"], "uf": ["SP"]})
    merc = pd.DataFrame({"hex_id": ["HEXA"], "score_setor_2022_calibrado": [55.0],
                         "score_oportunidade_residual": [40.0],
                         "cod_municipio": ["3550308"], "nome_municipio": ["Sao Paulo"], "uf": ["SP"]})
    dom = pd.DataFrame({"hex_id": ["HEXA"], "score_dominio_hibrido": [60.0]})
    out = bvd.join_scores(df, priorizados=prio, mercado=merc, dominio=dom)

    assert out.loc[0, "score_priorizacao"] == 70.0
    assert bool(out.loc[0, "score_priorizacao_disponivel"])
    assert out.loc[0, "score_setor_2022_calibrado"] == 55.0
    assert out.loc[0, "score_oportunidade_residual"] == 40.0
    assert out.loc[0, "score_dominio_hibrido"] == 60.0
    assert out.loc[0, "cod_municipio"] == "3550308"

    # HEXB ausente em todas as fontes -> nulos + flags False
    assert not bool(out.loc[1, "score_priorizacao_disponivel"])
    assert not bool(out.loc[1, "score_setor_2022_disponivel"])
    assert not bool(out.loc[1, "score_residual_disponivel"])
    assert not bool(out.loc[1, "score_dominio_disponivel"])
    assert pd.isna(out.loc[1, "score_priorizacao"])


def test_join_scores_preserva_cod_municipio_string_zeros():
    df = pd.DataFrame({"rede": ["skyfit"], "hex_id": ["HEXA"]})
    prio = pd.DataFrame({"hex_id": ["HEXA"], "score_priorizacao": [10.0],
                         "cod_municipio": ["0123456"], "nome_municipio": ["X"], "uf": ["AC"]})
    merc = pd.DataFrame({"hex_id": ["HEXA"], "score_setor_2022_calibrado": [1.0],
                         "score_oportunidade_residual": [2.0],
                         "cod_municipio": ["0123456"], "nome_municipio": ["X"], "uf": ["AC"]})
    dom = pd.DataFrame({"hex_id": [], "score_dominio_hibrido": []})
    out = bvd.join_scores(df, priorizados=prio, mercado=merc, dominio=dom)
    assert out.loc[0, "cod_municipio"] == "0123456"


# --------------------------------------------------------------------------- #
# join_label_by_name (EngCorpo)
# --------------------------------------------------------------------------- #
def test_join_label_by_name_casado_e_nao_casado():
    left = pd.DataFrame({"nome_norm": ["matriz rs", "fantasma"], "nome_unidade": ["EC - Matriz, RS", "X"]})
    right = pd.DataFrame({"nome_norm": ["matriz rs"], "hex_id_res7": ["87abc"], "lat": [-30.0], "lng": [-51.0]})
    out = bvd.join_label_by_name(left, right, value_cols=["hex_id_res7", "lat", "lng"])
    assert bool(out.loc[0, "rotulo_casado"])
    assert out.loc[0, "hex_id_res7"] == "87abc"
    assert not bool(out.loc[1, "rotulo_casado"])
    assert out.loc[1, "hex_id_res7"] is None


# --------------------------------------------------------------------------- #
# unify_wellhub
# --------------------------------------------------------------------------- #
def test_unify_wellhub_duas_parcerias():
    df = pd.DataFrame({"rede": ["skyfit"], "alunos_gympass": [100], "alunos_totalpass": [50]})
    out = bvd.unify_wellhub(df)
    assert out.loc[0, "n_parcerias_wellhub"] == 2
    assert bool(out.loc[0, "sinal_wellhub"])


def test_unify_wellhub_nenhuma_parceria():
    df = pd.DataFrame({"rede": ["skyfit"], "alunos_gympass": [0], "alunos_totalpass": [0]})
    out = bvd.unify_wellhub(df)
    assert out.loc[0, "n_parcerias_wellhub"] == 0
    assert not bool(out.loc[0, "sinal_wellhub"])


def test_unify_wellhub_sem_colunas_resulta_na():
    df = pd.DataFrame({"rede": ["engcorpo"]})
    out = bvd.unify_wellhub(df)
    assert out.loc[0, "n_parcerias_wellhub"] == 0
    assert pd.isna(out.loc[0, "sinal_wellhub"])


# --------------------------------------------------------------------------- #
# canonical_students
# --------------------------------------------------------------------------- #
def test_canonical_students_por_rede():
    df = pd.DataFrame(
        {
            "rede": ["ultra", "skyfit", "engcorpo"],
            "alunos_total": [1000, None, None],
            "ativos_pag": [None, None, None],
            "alunos_evo": [None, 2000, None],
            "alunos_totais": [None, None, 3000],
        }
    )
    out = bvd.canonical_students(df)
    assert out.loc[0, "alunos_recorrentes"] == 1000 and out.loc[0, "alunos_origem"] == "alunos_total" and bool(out.loc[0, "alunos_medido"])
    assert out.loc[1, "alunos_recorrentes"] == 2000 and out.loc[1, "alunos_origem"] == "Alunos EVO" and bool(out.loc[1, "alunos_medido"])
    assert out.loc[2, "alunos_recorrentes"] == 3000 and out.loc[2, "alunos_origem"] == "Alunos Totais" and not bool(out.loc[2, "alunos_medido"])


def test_canonical_students_ultra_fallback_ativos_pag():
    df = pd.DataFrame({"rede": ["ultra"], "alunos_total": [None], "ativos_pag": [777]})
    out = bvd.canonical_students(df)
    assert out.loc[0, "alunos_recorrentes"] == 777
    assert out.loc[0, "alunos_origem"] == "ativos_pag"


# --------------------------------------------------------------------------- #
# maturacao
# --------------------------------------------------------------------------- #
def test_maturacao_status_constante():
    df = pd.DataFrame({"rede": ["ultra", "skyfit"], "alunos_medido": [True, True]})
    out = bvd.add_quality_flags(df)
    assert (out["maturacao_status"] == "maturacao_indisponivel").all()


# --------------------------------------------------------------------------- #
# Sanidade do join (entrada == saida) + build end-to-end
# --------------------------------------------------------------------------- #
def _ultra_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "rede": ["ultra"],
            "unidade_id": ["ultra__a__0"],
            "nome_unidade": ["Ultra Centro"],
            "lat": [-23.55],
            "lng": [-46.63],
            "hex_id": ["HEXA"],
            "uf": ["SP"],
            "score_priorizacao": [88.0],
            "alunos_total": [1500.0],
            "ativos_pag": [1400.0],
            "alunos_gympass": [200],
            "alunos_totalpass": [100],
            "faturamento": [500000.0],
            "metragem_m2": [1800.0],
        }
    )


def _skyfit_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "rede": ["skyfit", "skyfit"],
            "unidade_id": ["skyfit__44", "skyfit__99"],
            "nome_unidade": ["Skyfit A", "Skyfit B"],
            "lat": [-22.80, None],
            "lng": [-43.20, None],
            "hex_id": [None, None],
            "hex_origem": ["nome_exato", "nao_resolvido"],
            "hex_precisao": ["unidade", "indisponivel"],
            "uf": ["RJ", ""],
            "alunos_evo": [2997.0, 1000.0],
            "alunos_gympass": [1014, 0],
            "alunos_totalpass": [563, 0],
        }
    )


def _engcorpo_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "rede": ["engcorpo"],
            "unidade_id": ["engcorpo__matriz__0"],
            "nome_unidade": ["EC - Matriz, RS"],
            "lat": [None],
            "lng": [None],
            "hex_id": ["HEXC"],
            "uf": [None],
            "metragem_m2": [5863.0],
            "alunos_totais": [9615.0],
            "alunos_gympass": [1173.0],
            "rotulo_casado_staging": [True],
        }
    )


def _score_fixtures():
    prio = pd.DataFrame({"hex_id": ["HEXA"], "score_priorizacao": [88.0],
                         "cod_municipio": ["3550308"], "nome_municipio": ["Sao Paulo"], "uf": ["SP"]})
    merc = pd.DataFrame(
        {
            "hex_id": ["HEXA", "HEXC"],
            "score_setor_2022_calibrado": [55.0, 30.0],
            "score_oportunidade_residual": [40.0, 20.0],
            "cod_municipio": ["3550308", "4304606"],
            "nome_municipio": ["Sao Paulo", "Caxias do Sul"],
            "uf": ["SP", "RS"],
        }
    )
    dom = pd.DataFrame({"hex_id": ["HEXA"], "score_dominio_hibrido": [60.0]})
    return prio, merc, dom


def test_build_end_to_end_tres_redes():
    pytest.importorskip("h3")
    prio, merc, dom = _score_fixtures()
    ds = bvd.build(
        ultra=_ultra_fixture(),
        skyfit=_skyfit_fixture(),
        engcorpo=_engcorpo_fixture(),
        priorizados=prio,
        mercado=merc,
        dominio=dom,
    )
    # sanidade do join: entrada (1+2+1=4) == saida
    assert len(ds) == 4
    assert set(ds["rede"]) == {"ultra", "skyfit", "engcorpo"}
    assert list(ds.columns) == list(bvd.SCHEMA_COLUMNS)
    # colunas novas presentes
    assert "hex_origem" in ds.columns and "hex_precisao" in ds.columns
    # maturacao constante
    assert (ds["maturacao_status"] == "maturacao_indisponivel").all()
    # Skyfit B nao resolvido
    sky_b = ds[ds["unidade_id"] == "skyfit__99"].iloc[0]
    assert not bool(sky_b["hex_resolvido"])
    # Ultra resolvido com score
    ultra = ds[ds["rede"] == "ultra"].iloc[0]
    assert bool(ultra["hex_resolvido"])
    assert ultra["score_priorizacao"] == 88.0
    assert bool(ultra["alunos_medido"])
    # EngCorpo estimado
    ec = ds[ds["rede"] == "engcorpo"].iloc[0]
    assert not bool(ec["alunos_medido"])
    assert ec["rotulo_confiabilidade"] == "estimado"
    assert ec["cod_municipio"] == "4304606"


def test_build_sem_duplicacao_quando_hex_repetido_no_score():
    pytest.importorskip("h3")
    # hex repetido nas fontes de score nao deve multiplicar linhas
    prio = pd.DataFrame({"hex_id": ["HEXA", "HEXA"], "score_priorizacao": [88.0, 50.0],
                         "cod_municipio": ["1", "1"], "nome_municipio": ["A", "A"], "uf": ["SP", "SP"]})
    merc = pd.DataFrame({"hex_id": ["HEXA"], "score_setor_2022_calibrado": [55.0],
                         "score_oportunidade_residual": [40.0],
                         "cod_municipio": ["1"], "nome_municipio": ["A"], "uf": ["SP"]})
    dom = pd.DataFrame({"hex_id": [], "score_dominio_hibrido": []})
    ds = bvd.build(ultra=_ultra_fixture(), priorizados=prio, mercado=merc, dominio=dom)
    assert len(ds) == 1


def test_audit_report_sem_pii():
    pytest.importorskip("h3")
    prio, merc, dom = _score_fixtures()
    ds = bvd.build(
        ultra=_ultra_fixture(),
        skyfit=_skyfit_fixture(),
        engcorpo=_engcorpo_fixture(),
        priorizados=prio,
        mercado=merc,
        dominio=dom,
    )
    stats = bvd.audit_labels(ds, entradas_por_rede={"ultra": 1, "skyfit": 2, "engcorpo": 1})
    report = bvd.render_audit_report(stats)
    # nenhum nome de unidade deve vazar no relatorio
    for nome in ["Ultra Centro", "Skyfit A", "Skyfit B", "EC - Matriz"]:
        assert nome not in report
    assert "hex_origem" in report
    assert "maturacao_indisponivel" in report


# --------------------------------------------------------------------------- #
# load_engcorpo (BLK-SCORE-01a) — fallback staging + nao-descarte
# --------------------------------------------------------------------------- #
def _write_engcorpo_sources(tmp_path, *, planilha_nomes, coords, staging_rows):
    """Materializa xlsx/csv/parquet sinteticos para exercitar ``load_engcorpo``."""
    xlsx = tmp_path / "academias.xlsx"
    plan = pd.DataFrame(
        {
            "Unidade": planilha_nomes,
            "Metragem M²": [1000.0] * len(planilha_nomes),
            "Alunos Totais": [500.0] * len(planilha_nomes),
            "Total Alunos Gympass": [50.0] * len(planilha_nomes),
        }
    )
    with pd.ExcelWriter(xlsx) as xw:
        plan.to_excel(xw, sheet_name="Academias", index=False)

    csv = tmp_path / "coords.csv"
    pd.DataFrame(coords).to_csv(csv, sep=";", encoding="utf-8-sig", index=False)

    pq = tmp_path / "staging.parquet"
    pd.DataFrame(staging_rows).to_parquet(pq, index=False)
    return xlsx, csv, pq


def test_load_engcorpo_fallback_staging(tmp_path):
    pytest.importorskip("openpyxl")
    # CSV nao resolve "EC - SO STAGING, RS"; staging tem o hex por nome.
    xlsx, csv, pq = _write_engcorpo_sources(
        tmp_path,
        planilha_nomes=["EC - VACARIA, RS", "EC - SO STAGING, RS"],
        coords={
            "nome_unidade": ["Vacaria, RS"],
            "latitude": [-28.50],
            "longitude": [-50.93],
            "data_coleta": ["2026-05-26"],
        },
        staging_rows={
            "rede": ["engenharia_do_corpo"],
            "status_registro": ["valido"],
            "nome_unidade": ["So Staging, RS"],
            "hex_id_res7": ["87abc0000ffffff"],
            "lat": [-30.0],
            "lng": [-51.0],
        },
    )
    out = bvd.load_engcorpo(xlsx, csv, pq)
    # entrada == saida (nada descartado)
    assert len(out) == 2
    by_name = {n: i for i, n in enumerate(out["nome_unidade"])}
    i_csv = by_name["EC - VACARIA, RS"]
    i_stg = by_name["EC - SO STAGING, RS"]
    assert out.loc[i_csv, "hex_origem"] == "nome_exato"
    assert out.loc[i_stg, "hex_origem"] == "hex_staging"
    assert out.loc[i_stg, "hex_id"] == "87abc0000ffffff"
    assert bool(out.loc[i_stg, "rotulo_casado_staging"])


def test_load_engcorpo_nao_casado_marcado_nunca_descartado(tmp_path):
    pytest.importorskip("openpyxl")
    # unidade sem match no CSV nem no staging -> permanece, marcada nao-casada
    xlsx, csv, pq = _write_engcorpo_sources(
        tmp_path,
        planilha_nomes=["EC - VACARIA, RS", "EC - INEXISTENTE, AC"],
        coords={
            "nome_unidade": ["Vacaria, RS"],
            "latitude": [-28.50],
            "longitude": [-50.93],
            "data_coleta": ["2026-05-26"],
        },
        staging_rows={
            "rede": ["engenharia_do_corpo"],
            "status_registro": ["valido"],
            "nome_unidade": ["Vacaria, RS"],
            "hex_id_res7": ["87abc0000ffffff"],
            "lat": [-28.50],
            "lng": [-50.93],
        },
    )
    out = bvd.load_engcorpo(xlsx, csv, pq)
    assert len(out) == 2  # nº entrada == nº saida
    i_nao = {n: i for i, n in enumerate(out["nome_unidade"])}["EC - INEXISTENTE, AC"]
    assert out.loc[i_nao, "hex_origem"] == "nao_resolvido"
    assert not bool(out.loc[i_nao, "rotulo_casado_staging"])
    assert pd.isna(out.loc[i_nao, "lat"])
