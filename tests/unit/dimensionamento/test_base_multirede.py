"""Testes do BLK-DIM-07 (base multi-rede + raio variavel).

Tudo offline, seeds fixos, sem ler os xlsx reais (gitignored) nem o censo (~1.17 GB):
- parsing/normalizacao de nome (a parte de RISCO -- match ingenuo = 0%);
- loaders SkyFit/Engenharia com xlsx+csv SINTETICOS gravados em tmp_path;
- haversine, raio variavel (monotonicidade), densidade de marca propria;
- validar_raio_variavel com `calcular_catchment_unidade` MONKEYPATCHADO (sem censo);
- guard anti-PII no salvar.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from motor_expansao.dimensionamento import base_multirede as bm

# --------------------------------------------------------------------------- #
# Parsing / normalizacao
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "raw,esperado",
    [
        ("Abaetetuba (PA)", ("abaetetuba", "PA")),
        ("Diamantino - Caxias do Sul, RS", ("caxias do sul", "RS")),
        ("Sao Paulo (SP)", ("sao paulo", "SP")),
        ("Cidade Sem Uf", ("cidade sem uf", "")),
    ],
)
def test_parse_cidade_uf_do_csv(raw, esperado):
    assert bm.parse_cidade_uf_do_csv(raw) == esperado


@pytest.mark.parametrize(
    "raw,esperado",
    [
        ("EC - VACARIA, RS", ("vacaria", "RS")),
        ("ECB - DESVIO RIZZO, RS", ("desvio rizzo", "RS")),
        ("ENGENHARIA DO CORPO - TUBARAO", ("tubarao", "")),
        ("EC - CAMPO GRANDE,MS", ("campo grande", "MS")),
    ],
)
def test_eng_token_uf(raw, esperado):
    assert bm._eng_token_uf(raw) == esperado


def test_match_ingenuo_por_nome_falha():
    # O caveat do bloco: nome interno != cidade -> normalizacao crua nao casa.
    assert bm._norm_cidade("EC - MATRIZ, RS") != bm._norm_cidade("Vacaria, RS")


# --------------------------------------------------------------------------- #
# Geometria / raio variavel / densidade de marca
# --------------------------------------------------------------------------- #


def test_haversine_conhecido():
    # ~ distancia Sao Paulo (Se) -> Campinas ~ 90 km (tolerancia ampla).
    d = bm.haversine_km(-23.55, -46.63, -22.90, -47.06)
    assert 80.0 < d < 100.0
    assert bm.haversine_km(0.0, 0.0, 0.0, 0.0) == pytest.approx(0.0, abs=1e-9)


def test_raio_variavel_monotonico_e_limitado():
    # Mais densidade/concorrencia -> raio MENOR; sempre dentro de [MIN, MAX].
    r_vazio = bm.raio_variavel_km(0.0, 0.0)
    r_denso = bm.raio_variavel_km(20000.0, 10.0)
    assert r_vazio == pytest.approx(bm.RAIO_KM_MAX, abs=1e-6)
    assert r_denso < r_vazio
    assert bm.RAIO_KM_MIN <= r_denso <= bm.RAIO_KM_MAX
    # monotonia em concorrencia
    assert bm.raio_variavel_km(0.0, 8.0) < bm.raio_variavel_km(0.0, 1.0)


def test_densidade_marca_propria_conta_same_brand():
    # 2 unidades 'a' coladas (<1.5km) + 1 'a' longe + 1 'b' colada na 'a' longe.
    base = pd.DataFrame(
        {
            "unidade": ["a1", "a2", "a3", "b1"],
            "marca": ["x", "x", "x", "y"],
            "uf": ["SP"] * 4,
            "cidade": ["c"] * 4,
            "lat": [-23.550, -23.551, -23.900, -23.9005],
            "lng": [-46.630, -46.631, -46.900, -46.9005],
            "alunos_reais": [100, 100, 100, 100],
            "metragem": [np.nan] * 4,
            "flag_qualidade_match": ["direto"] * 4,
        }
    )
    out = bm.derivar_densidade_marca_propria(base.assign(raio_km=1.5))
    by = out.set_index("unidade")["n_mesma_marca_no_raio"].to_dict()
    assert by["a1"] == 1 and by["a2"] == 1  # se enxergam
    assert by["a3"] == 0  # marca x sozinha la longe
    assert by["b1"] == 0  # 'y' nao conta vizinho de outra marca ('a3' e marca x)


def test_densidade_marca_ignora_coord_nan():
    base = pd.DataFrame(
        {
            "unidade": ["a1", "a2"],
            "marca": ["x", "x"],
            "uf": ["SP", "SP"],
            "cidade": ["c", "c"],
            "lat": [-23.55, np.nan],
            "lng": [-46.63, np.nan],
            "alunos_reais": [100, 100],
            "metragem": [np.nan, np.nan],
            "flag_qualidade_match": ["direto", "nao_casado"],
        }
    )
    out = bm.derivar_densidade_marca_propria(base.assign(raio_km=1.5))
    assert out.set_index("unidade")["n_mesma_marca_no_raio"]["a1"] == 0


# --------------------------------------------------------------------------- #
# Loaders com fixtures sinteticas (sem tocar os xlsx reais)
# --------------------------------------------------------------------------- #


def _escrever_skyfit_xlsx(path):
    # 2 linhas de metadado no topo + header na 3a linha (como o arquivo real).
    header = ["ID SKY", "NOMENCLATURA UNIDADE", "ENDERECO", "CIDADE", "ESTADO",
              "Alunos EVO", "Alunos Gympass", "Alunos TotalPass"]
    linhas = [
        [1, "Unidade Alfa", "Rua A", "Vacaria", "RS", 1000, 100, 50],
        [2, "Unidade Beta", "Rua B", "Cidade Ambigua", "SP", 800, 0, 0],
    ]
    df = pd.DataFrame([[None] * 8, [None] * 8, header, *linhas])
    df.to_excel(path, sheet_name="Sell Out", header=False, index=False)


def _escrever_skyfit_csv(path):
    pd.DataFrame(
        {
            "nome_unidade": ["Vacaria (RS)", "Cidade Ambigua (SP)", "Cidade Ambigua (SP)"],
            "latitude": [-28.5, -23.5, -23.6],
            "longitude": [-50.9, -46.6, -46.7],
            "data_coleta": ["2026-05-26"] * 3,
        }
    ).to_csv(path, index=False, encoding="utf-8-sig")


def test_carregar_skyfit_cidade_uf_e_ambiguo(tmp_path):
    xlsx = tmp_path / "sky.xlsx"
    csv = tmp_path / "sky.csv"
    _escrever_skyfit_xlsx(xlsx)
    _escrever_skyfit_csv(csv)
    out = bm.carregar_skyfit(alunos_xlsx=xlsx, coords_csv=csv)
    assert set(out.columns) == set(bm.BASE_COLUNAS)
    by = out.set_index("cidade")
    # Vacaria: 1 coord -> casa por cidade_uf, alunos 1000+100+50=1150
    assert by.loc["vacaria", "flag_qualidade_match"] == "cidade_uf"
    assert by.loc["vacaria", "alunos_reais"] == 1150
    assert np.isfinite(by.loc["vacaria", "lat"])
    # Cidade Ambigua: 2 coords no csv -> ambiguo, sem coord auto-atribuida
    assert by.loc["cidade ambigua", "flag_qualidade_match"] == "ambiguo"
    assert pd.isna(by.loc["cidade ambigua", "lat"])
    assert (out["marca"] == "skyfit").all()


def _escrever_eng_xlsx(path):
    df = pd.DataFrame(
        {
            "ID": [1, 2, 3],
            "Unidade": ["EC - VACARIA, RS", "EC - BLUMENAU, SC", "EC - MATRIZ, RS"],
            "Metragem M2": [1500, 1800, 5000],
            "Alunos Totais": [2200, 2600, 9000],
        }
    )
    df.to_excel(path, sheet_name="Academias", index=False)


def _escrever_eng_csv(path):
    pd.DataFrame(
        {
            "nome_unidade": ["Vacaria, RS", "Blumenau, SC", "Porto Alegre, RS"],
            "latitude": [-28.5, -26.9, -30.0],
            "longitude": [-50.9, -49.0, -51.2],
            "data_coleta": ["2026-05-26"] * 3,
        }
    ).to_csv(path, index=False, encoding="utf-8-sig")


def test_carregar_engenharia_fuzzy_e_nao_casado(tmp_path):
    xlsx = tmp_path / "eng.xlsx"
    csv = tmp_path / "eng.csv"
    _escrever_eng_xlsx(xlsx)
    _escrever_eng_csv(csv)
    out = bm.carregar_engenharia(alunos_xlsx=xlsx, coords_csv=csv)
    by = out.set_index("unidade")
    # Vacaria/Blumenau casam por cidade (token == cidade do csv)
    assert by.loc["EC - VACARIA, RS", "flag_qualidade_match"] == "fuzzy"
    assert by.loc["EC - BLUMENAU, SC", "flag_qualidade_match"] == "fuzzy"
    assert by.loc["EC - VACARIA, RS", "alunos_reais"] == 2200
    # MATRIZ (bairro de POA) nao casa "porto alegre" por token de cidade -> nao_casado
    assert by.loc["EC - MATRIZ, RS", "flag_qualidade_match"] == "nao_casado"
    assert pd.isna(by.loc["EC - MATRIZ, RS", "lat"])
    assert (out["marca"] == "engenharia_do_corpo").all()


# --------------------------------------------------------------------------- #
# validar_raio_variavel com catchment MONKEYPATCHADO (sem censo)
# --------------------------------------------------------------------------- #


def test_validar_raio_veredito_estabilidade(tmp_path, monkeypatch):
    # base sintetica: penetracao instavel no raio fixo, estavel no variavel.
    n = 12
    base = pd.DataFrame(
        {
            "unidade": [f"u{i}" for i in range(n)],
            "marca": ["ultra"] * n,
            "uf": ["DF"] * n,
            "cidade": ["c"] * n,
            "lat": np.linspace(-15.9, -15.7, n),
            "lng": np.linspace(-48.0, -47.8, n),
            "alunos_reais": np.linspace(1500, 3000, n),
            "metragem": [np.nan] * n,
            "flag_qualidade_match": ["direto"] * n,
        }
    )
    # concorrentes fake (parquet temporario)
    conc = tmp_path / "conc.parquet"
    pd.DataFrame({"lat": [-15.8, -15.75], "lng": [-47.9, -47.85]}).to_parquet(conc)

    # catchment fake: pop ~ raio^2 * densidade fixa -> no raio variavel a penetracao fica estavel
    def fake_catch(lat, lng, setores, raio_km=1.5):
        pop = 10000.0 * (raio_km**2)
        return {"pop_captacao": pop, "renda_per_capita_captacao": 3000.0,
                "n_setores_captacao": 5, "raio_km": raio_km}

    monkeypatch.setattr(bm, "calcular_catchment_unidade", fake_catch)
    enr, met = bm.validar_raio_variavel(
        base, setores_loader=lambda d, uf: pd.DataFrame({"x": [1]}), conc_path=conc
    )
    assert met["n_unidades_com_coord"] == n
    assert "raio_km" in enr.columns and "pop_captacao_variavel" in enr.columns
    assert met["veredito"] in {
        "raio_variavel_aceito",
        "raio_variavel_aceito_para_estabilidade",
        "raio_fixo_mantido",
    }
    assert np.isfinite(met["cv_reducao_relativa"])


# --------------------------------------------------------------------------- #
# Montagem + anti-PII
# --------------------------------------------------------------------------- #


def test_salvar_base_anti_pii(tmp_path):
    base = pd.DataFrame(
        {
            "unidade": ["a"],
            "marca": ["ultra"],
            "uf": ["SP"],
            "cidade": ["c"],
            "lat": [-23.5],
            "lng": [-46.6],
            "alunos_reais": [2000],
            "metragem": [1500.0],
            "flag_qualidade_match": ["direto"],
        }
    )
    out = tmp_path / "base.parquet"
    bm.salvar_base(base, path=out)
    assert out.exists()
    # coluna proibida de PII -> levanta ValueError (assert_sem_pii, LGPD §10.3)
    ruim = base.assign(nome=["Fulano"])
    with pytest.raises(ValueError, match="PII"):
        bm.salvar_base(ruim, path=tmp_path / "ruim.parquet")
