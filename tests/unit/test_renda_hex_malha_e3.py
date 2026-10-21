"""E3 do plano de correcao da renda: moradores e uplift DO SETOR na renda do hexagono.

Antes da E3 a renda domiciliar do hexagono usava moradores e uplift do MUNICIPIO:

    dom = (S_hex / k) x moradores_municipio x uplift_municipio x F

A E3 agrega a renda de 2022 da MALHA de setores (uplift e moradores de cada setor, pela regra
de fracao de area da DEC-045) e a exibicao aplica SO o fator temporal, uma vez:

    dom_hex = renda_domiciliar_2022_malha            x F_dom
    pc_hex  = renda_per_capita_domiciliar_2022_malha x F_pc

O que este arquivo trava:
  1. a agregacao com setores de brinquedo (pesos por domicilios e por populacao; a identidade
     dom / pc = moradores do hexagono; colunas existentes e score intactos);
  2. a formula do hexagono com as colunas: so F, uma vez, cada renda com o proprio fator;
  3. o fallback: sem as colunas (ou sem valor, ou origem municipal) = formula de antes, bit a bit;
  4. a sobreposicao do traco censitario carrega as colunas, e malha antiga nao as inventa;
  5. as superficies do piloto (tooltip/ficha via `_renda_*_hex`) herdam pela linha.
"""

from __future__ import annotations

import sys
from pathlib import Path

import h3
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import box

from motor_expansao.pipelines import agregar_censo_hex_da_malha as malha
from motor_expansao.renda import (
    COL_RENDA_DOM_MALHA,
    COL_RENDA_PC_MALHA,
    COLS_RENDA_MALHA,
    colunas_malha_por_hex,
    fator,
    renda_domiciliar_hex,
    renda_domiciliar_por_hex,
    renda_per_capita_hex,
    rendas_2022_setores,
)
from motor_expansao.renda import hex as renda_hex
from tests.unit.renda_fixtures import apontar_staging_renda, fixar_fatores

F_PC = 1.30
F_DOM = 1.20  # != F_PC de proposito: pega quem aplicar o fator de um tipo no outro
CALIBRADA = "renda_per_capita_setor_2022_calibrada"

# Tabela municipal sintetica (o caminho de antes): moradores x uplift = 3,2 x 1,5.
_MUNICIPIOS = pd.DataFrame(
    {
        "uf": ["SP"],
        "cod_municipio": ["3550308"],
        "uplift_composicao_final": [1.5],
        "uplift_confiavel": [True],
        "moradores_por_domicilio_municipio": [3.2],
    }
)


@pytest.fixture
def staging(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    raiz = tmp_path / "staging"
    raiz.mkdir()
    _MUNICIPIOS.to_parquet(raiz / "uplift_renda_domiciliar_municipio.parquet")
    pd.DataFrame(
        {"cod_setor": ["s1", "s2"], "uplift_composicao_setor": [1.40, 1.60]}
    ).to_parquet(raiz / "uplift_composicao_setor.parquet")
    fixar_fatores(monkeypatch, tmp_path, per_capita=F_PC, domiciliar=F_DOM)
    apontar_staging_renda(monkeypatch, raiz)
    return raiz


# --------------------------------------------------------------------------------
# 1. Agregacao com setores de brinquedo
# --------------------------------------------------------------------------------

_CELULA = h3.latlng_to_cell(-23.55, -46.63, 7)


def _quadrado(dlat: float, dlng: float, lado: float = 0.002):
    lat, lng = h3.cell_to_latlng(_CELULA)
    return box(lng + dlng, lat + dlat, lng + dlng + lado, lat + dlat + lado)


def _setores() -> pd.DataFrame:
    """Tres setores DENTRO da mesma celula. s3 nao tem uplift proprio (cai no municipio).

    Moradores = pop / domicilios EXATOS, para a identidade dom / pc = moradores valer.
    """
    geoms = [_quadrado(0.0, 0.0), _quadrado(0.003, 0.003), _quadrado(-0.004, -0.004)]
    pop = np.array([300.0, 500.0, 200.0])
    dom = np.array([100.0, 250.0, 50.0])
    return pd.DataFrame(
        {
            "cod_setor": ["s1", "s2", "s3"],
            "uf": ["SP"] * 3,
            "cod_municipio": ["3550308"] * 3,
            "pop_total_setor_2022": pop,
            "domicilios_particulares_ocupados_setor_2022": dom,
            "avg_moradores_domicilio_setor_2022": pop / dom,
            "renda_responsavel_media_setor_2022": [2000.0, 3000.0, 1000.0],
            "renda_per_capita_setor_2022": [2000.0 * dom[0] / pop[0], 3000.0 * dom[1] / pop[1],
                                            1000.0 * dom[2] / pop[2]],
            "renda_per_capita_setor_2022_calibrada": [800.0, 1900.0, 300.0],
            "geometry_wkb": [g.wkb for g in geoms],
            "bbox_minx": [g.bounds[0] for g in geoms],
            "bbox_miny": [g.bounds[1] for g in geoms],
            "bbox_maxx": [g.bounds[2] for g in geoms],
            "bbox_maxy": [g.bounds[3] for g in geoms],
        }
    )


def test_rendas_2022_do_setor_sem_fator(staging):
    dom, pc = rendas_2022_setores(_setores())
    uplift = np.array([1.40, 1.60, 1.5])  # s3 cai no uplift do municipio
    v = np.array([2000.0, 3000.0, 1000.0])
    np.testing.assert_allclose(dom.to_numpy(), v * uplift, rtol=1e-12)
    np.testing.assert_allclose(pc.to_numpy(), v * uplift / np.array([3.0, 2.0, 4.0]), rtol=1e-12)


def test_rendas_2022_reconstroem_a_v06004_pela_per_capita_bruta(staging):
    df = _setores()
    df.loc[0, "renda_responsavel_media_setor_2022"] = np.nan
    dom, _ = rendas_2022_setores(df)
    # per capita bruta x moradores = 2000 (a V06004 de antes) -- nunca a calibrada.
    assert dom.iloc[0] == pytest.approx(2000.0 * 1.40, rel=1e-12)


def test_agregacao_pondera_dom_por_domicilios_e_pc_por_populacao(staging):
    df = _setores()
    out = malha.agregar_setores(df).set_index("hex_id")
    assert list(out.index) == [_CELULA]
    linha = out.loc[_CELULA]
    v = np.array([2000.0, 3000.0, 1000.0])
    u = np.array([1.40, 1.60, 1.5])
    pop = np.array([300.0, 500.0, 200.0])
    domic = np.array([100.0, 250.0, 50.0])
    esperado_dom = (v * u * domic).sum() / domic.sum()
    esperado_pc = (v * u / (pop / domic) * pop).sum() / pop.sum()
    assert linha[COL_RENDA_DOM_MALHA] == pytest.approx(esperado_dom, rel=1e-12)
    assert linha[COL_RENDA_PC_MALHA] == pytest.approx(esperado_pc, rel=1e-12)
    # Identidade: dom / pc = moradores DO HEXAGONO (pop / domicilios dos pedacos).
    assert linha[COL_RENDA_DOM_MALHA] / linha[COL_RENDA_PC_MALHA] == pytest.approx(
        pop.sum() / domic.sum(), rel=1e-12
    )


def test_pesos_novos_normalizam_a_fracao_de_area_do_setor_de_borda(staging, monkeypatch):
    # Setor que CRUZA a borda: so duas das celulas que ele toca entram como candidatas, entao
    # as fracoes de area somam MENOS de 1 (o caso "erro de projecao/topologia" da DEC-045).
    # Os dois pesos novos tem de ser repartidos por `fracao / soma` -- como a populacao --,
    # senao domicilios e populacao do setor evaporam na borda.
    from shapely.geometry import Polygon

    lat, lng = h3.cell_to_latlng(_CELULA)
    geom = box(lng - 0.01, lat - 0.01, lng + 0.01, lat + 0.01)

    def _pol(cell: str) -> Polygon:
        return Polygon([(x, y) for y, x in h3.cell_to_boundary(cell)])

    vizinha = next(
        c for c in sorted(h3.grid_ring(_CELULA, 1)) if geom.intersection(_pol(c)).area > 0
    )
    candidatas = {_CELULA, vizinha}
    monkeypatch.setattr(malha, "_candidatos", lambda *_a, **_k: set(candidatas))

    pop, domic = 900.0, 300.0
    df = _setores().iloc[[0]].copy()
    df["pop_total_setor_2022"] = pop
    df["domicilios_particulares_ocupados_setor_2022"] = domic
    df["avg_moradores_domicilio_setor_2022"] = pop / domic
    df["geometry_wkb"] = [geom.wkb]
    df["bbox_minx"], df["bbox_miny"], df["bbox_maxx"], df["bbox_maxy"] = geom.bounds

    fracoes = {c: geom.intersection(_pol(c)).area / geom.area for c in candidatas}
    soma = sum(fracoes.values())
    assert soma < 0.99, "o setor de brinquedo nao cruzou a borda -- o teste nao provaria nada"

    out = malha.agregar_setores(df).set_index("hex_id")
    assert set(out.index) == candidatas
    for cell, fracao in fracoes.items():
        assert out.loc[cell, malha.COL_PESO_DOM] == pytest.approx(domic * fracao / soma, rel=1e-9)
        assert out.loc[cell, malha.COL_PESO_PC] == pytest.approx(pop * fracao / soma, rel=1e-9)
    # Um setor so: a renda de cada celula e a do proprio setor (numerador e peso com a MESMA
    # fracao normalizada; desencontrar os dois escala a renda por `soma`).
    dom_s, pc_s = (s.iloc[0] for s in rendas_2022_setores(df))
    for cell in candidatas:
        assert out.loc[cell, COL_RENDA_DOM_MALHA] == pytest.approx(dom_s, rel=1e-12)
        assert out.loc[cell, COL_RENDA_PC_MALHA] == pytest.approx(pc_s, rel=1e-12)
    # Massa conservada: nada some na borda.
    assert out[malha.COL_PESO_DOM].sum() == pytest.approx(domic, rel=1e-12)
    assert out[malha.COL_PESO_PC].sum() == pytest.approx(pop, rel=1e-12)


@pytest.mark.parametrize("domicilios_ruins", [np.nan, 0.0])
def test_setor_sem_domicilios_fica_fora_so_da_domiciliar(staging, domicilios_ruins):
    # s2 sem domicilios (nulo ou zero): nao pode contaminar a domiciliar do hexagono com NaN
    # nem derrubar a linha para a formula municipal -- a media sai so dos demais setores.
    df = _setores()
    df.loc[1, "domicilios_particulares_ocupados_setor_2022"] = domicilios_ruins
    linha = malha.agregar_setores(df).set_index("hex_id").loc[_CELULA]
    v = np.array([2000.0, 1000.0])          # s1 e s3
    u = np.array([1.40, 1.5])
    domic = np.array([100.0, 50.0])
    assert np.isfinite(linha[COL_RENDA_DOM_MALHA])
    assert linha[COL_RENDA_DOM_MALHA] == pytest.approx((v * u * domic).sum() / domic.sum(), rel=1e-12)
    assert linha[malha.COL_PESO_DOM] == pytest.approx(domic.sum(), rel=1e-12)
    # A per capita usa os moradores do setor, nao os domicilios: s2 continua nela.
    assert linha[malha.COL_PESO_PC] == pytest.approx(1000.0, rel=1e-12)


def test_agregacao_nao_muda_as_colunas_existentes(staging):
    df = _setores()
    novo = malha.agregar_setores(df)
    sem_e3 = malha.agregar_setores(
        df.drop(columns=["renda_responsavel_media_setor_2022", "renda_per_capita_setor_2022",
                         "avg_moradores_domicilio_setor_2022",
                         "domicilios_particulares_ocupados_setor_2022"])
    )
    for c in ("hex_id", "pop_malha", "renda_malha", "pop_com_renda_malha", "n_setores_malha",
              "cobertura_renda_malha"):
        pd.testing.assert_series_equal(novo[c], sem_e3[c])
    assert sem_e3[COL_RENDA_DOM_MALHA].isna().all()
    # O score le so `renda_malha` e populacao: identico com e sem as colunas novas.
    pd.testing.assert_series_equal(
        malha.anexar_score(novo)["score_malha"], malha.anexar_score(sem_e3)["score_malha"]
    )


def test_reagregacao_entre_particoes_preserva_as_medias(staging, tmp_path):
    # Mesmo hexagono tocado por duas particoes (municipios diferentes): reagregado por peso.
    df = _setores()
    raiz = tmp_path / "geo"
    for cod, idx in (("3550308", [0, 1]), ("3509502", [2])):
        destino = raiz / "uf=SP" / f"cod_municipio={cod}"
        destino.mkdir(parents=True)
        df.iloc[idx].to_parquet(destino / "part-000.parquet")
    junto = malha.agregar_setores(df).set_index("hex_id")
    separado = malha.agregar_particoes(malha.listar_particoes(raiz), progresso=0).set_index("hex_id")
    for c in (COL_RENDA_DOM_MALHA, COL_RENDA_PC_MALHA, "renda_malha"):
        assert separado.loc[_CELULA, c] == pytest.approx(junto.loc[_CELULA, c], rel=1e-12)


# --------------------------------------------------------------------------------
# 2. Formula do hexagono com as colunas: so F, uma vez
# --------------------------------------------------------------------------------


def test_hex_com_malha_aplica_so_o_fator_do_tipo(staging):
    linha = {COL_RENDA_DOM_MALHA: 4749.55, COL_RENDA_PC_MALHA: 1766.19}
    dom = renda_domiciliar_hex(1000.0, "SP", "3550308", linha=linha, origem=CALIBRADA)
    pc = renda_per_capita_hex(1000.0, "SP", "3550308", linha=linha, origem=CALIBRADA)
    assert dom == 4749.55 * F_DOM
    assert pc == 1766.19 * F_PC
    # A base municipal, os moradores e o uplift do municipio nao entram.
    assert dom != pytest.approx(1000.0 * 3.2 * 1.5 * F_DOM)
    # Nem a per capita derivada da domiciliar (armadilha 1 da secao 9.3).
    assert pc != pytest.approx(dom / (4749.55 / 1766.19))


def test_hex_com_malha_nao_depende_do_municipio(staging):
    linha = {COL_RENDA_DOM_MALHA: 5000.0, COL_RENDA_PC_MALHA: 2000.0}
    a = renda_domiciliar_hex(1000.0, "SP", "3550308", linha=linha, origem=CALIBRADA)
    b = renda_domiciliar_hex(1000.0, "SP", "9999999", linha=linha, origem=CALIBRADA)
    assert a == b == 5000.0 * fator("SP", "domiciliar")


# --------------------------------------------------------------------------------
# 3. Fallback = formula de antes, bit a bit
# --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("linha", "origem"),
    [
        (None, CALIBRADA),                                              # artefato antigo
        ({}, CALIBRADA),                                                # sem as colunas
        ({COL_RENDA_DOM_MALHA: np.nan, COL_RENDA_PC_MALHA: None}, CALIBRADA),  # hex sem setor
        ({COL_RENDA_DOM_MALHA: 0.0, COL_RENDA_PC_MALHA: -1.0}, CALIBRADA),     # invalido
        ({COL_RENDA_DOM_MALHA: 9999.0, COL_RENDA_PC_MALHA: 9999.0}, "renda_per_capita"),  # SIDRA
    ],
)
def test_fallback_e_a_formula_de_antes(staging, linha, origem):
    for base in (123.456, 1451.97, 33333.3):
        assert renda_domiciliar_hex(base, "SP", "3550308", linha=linha, origem=origem) == (
            renda_domiciliar_hex(base, "SP", "3550308")
        )
        assert renda_per_capita_hex(base, "SP", "3550308", linha=linha, origem=origem) == (
            renda_per_capita_hex(base, "SP", "3550308")
        )
    assert renda_domiciliar_hex(None, "SP", "3550308", linha=linha, origem=origem) is None


def test_mapa_do_pdf_municipal_usa_a_malha_por_linha(staging):
    df = pd.DataFrame(
        {
            "hex_id": ["a", "b", "c"],
            CALIBRADA: [1100.0, 1100.0, np.nan],
            "renda_per_capita": [1500.0, 1500.0, 1500.0],
            COL_RENDA_DOM_MALHA: [5000.0, np.nan, 7000.0],
            COL_RENDA_PC_MALHA: [2000.0, np.nan, 3000.0],
        }
    )
    pd.DataFrame({"metodo_calibracao_renda_malha": ["multiplicativo_global_k=1.1"]}).to_parquet(
        staging / renda_hex.CENSO_MALHA_PARQUET
    )
    out = renda_domiciliar_por_hex(df, uf="SP", cod_municipio="3550308", staging_dir=staging)
    sem = renda_domiciliar_por_hex(
        df.drop(columns=list(COLS_RENDA_MALHA)), uf="SP", cod_municipio="3550308",
        staging_dir=staging,
    )
    assert out["a"] == 5000.0 * F_DOM               # malha
    assert out["b"] == sem["b"]                      # hex sem malha: formula de antes
    assert out["c"] == sem["c"]                      # origem municipal (SIDRA): formula de antes


def test_frame_sem_as_colunas_le_a_malha_do_staging(staging):
    # O bot recorta o artefato de MERCADO (sem as colunas): o modulo as anexa do staging, senao
    # o mesmo municipio sairia com um numero no PDF do bot e outro no do piloto.
    pd.DataFrame(
        {
            "hex_id": ["a", "b"],
            "metodo_calibracao_renda_malha": ["multiplicativo_global_k=1.1"] * 2,
            COL_RENDA_DOM_MALHA: [5000.0, np.nan],
            COL_RENDA_PC_MALHA: [2000.0, np.nan],
        }
    ).to_parquet(staging / renda_hex.CENSO_MALHA_PARQUET)
    df = pd.DataFrame(
        {"hex_id": ["a", "b"], "uf": ["SP", "SP"], "cod_municipio": ["3550308"] * 2,
         CALIBRADA: [1100.0, 1100.0]}
    )
    dom = renda_domiciliar_por_hex(df, uf="SP", cod_municipio="3550308", staging_dir=staging)
    assert dom["a"] == 5000.0 * F_DOM
    assert dom["b"] == renda_domiciliar_hex(1100.0 / 1.1, "SP", "3550308")
    pc = renda_hex.renda_per_capita_por_linha(df, staging_dir=staging)
    assert pc.iloc[0] == 2000.0 * F_PC
    assert list(df.columns) == ["hex_id", "uf", "cod_municipio", CALIBRADA]  # nao muta


def test_per_capita_por_linha_respeita_a_precedencia(staging):
    df = pd.DataFrame(
        {
            "hex_id": ["a"],
            "uf": ["SP"],
            "cod_municipio": ["3550308"],
            CALIBRADA: [1100.0],
            "renda_per_capita": [1500.0],
            COL_RENDA_PC_MALHA: [2000.0],
        }
    )
    pd.DataFrame({"metodo_calibracao_renda_malha": ["multiplicativo_global_k=1.1"]}).to_parquet(
        staging / renda_hex.CENSO_MALHA_PARQUET
    )
    setor = renda_hex.renda_per_capita_por_linha(df, staging_dir=staging)
    assert setor.iloc[0] == 2000.0 * F_PC
    # O painel per capita MUNICIPAL le so a SIDRA: a malha nao entra.
    sidra = renda_hex.renda_per_capita_por_linha(
        df, precedencia=("renda_per_capita",), staging_dir=staging
    )
    assert sidra.iloc[0] == renda_hex.renda_per_capita_por_linha(
        df.drop(columns=[COL_RENDA_PC_MALHA]), precedencia=("renda_per_capita",),
        staging_dir=staging,
    ).iloc[0]


def test_colunas_malha_por_hex(staging):
    assert colunas_malha_por_hex(["x"], staging).empty  # sem artefato
    pd.DataFrame({"hex_id": ["x"], "renda_malha": [1.0]}).to_parquet(
        staging / renda_hex.CENSO_MALHA_PARQUET
    )
    assert colunas_malha_por_hex(["x"], staging).empty  # malha anterior a E3
    pd.DataFrame(
        {"hex_id": ["x", "y"], COL_RENDA_DOM_MALHA: [5.0, 6.0], COL_RENDA_PC_MALHA: [2.0, 3.0]}
    ).to_parquet(staging / renda_hex.CENSO_MALHA_PARQUET)
    out = colunas_malha_por_hex(["y", "z"], staging)
    assert list(out.index) == ["y"]
    assert out.loc["y", COL_RENDA_DOM_MALHA] == 6.0


# --------------------------------------------------------------------------------
# 4. Sobreposicao no traco censitario
# --------------------------------------------------------------------------------


def _malha_parquet(path: Path, *, com_e3: bool) -> Path:
    df = pd.DataFrame(
        {
            "hex_id": ["h1", "h2"],
            "uf": ["SP", "SP"],
            "pop_malha": [100.0, 50.0],
            "renda_malha": [1200.0, 900.0],
            "score_malha": [40.0, 20.0],
            "k_malha": [1.2334632197, 1.2334632197],
        }
    )
    if com_e3:
        df[COL_RENDA_DOM_MALHA] = [4000.0, 3000.0]
        df[COL_RENDA_PC_MALHA] = [1500.0, 1100.0]
    df.to_parquet(path)
    return path


def _censo() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "hex_id": ["h1", "h3"],
            "uf": ["SP", "SP"],
            CALIBRADA: [1000.0, 800.0],
            "score_setor_2022_calibrado": [30.0, 10.0],
            "metodo_calibracao_renda": ["multiplicativo_global_k=1.2334632197"] * 2,
        }
    )


def test_sobreposicao_carrega_as_colunas_e_nao_muda_as_outras(tmp_path):
    antiga = malha.sobrepor_renda_da_malha(_censo(), _malha_parquet(tmp_path / "a.parquet", com_e3=False))
    nova = malha.sobrepor_renda_da_malha(_censo(), _malha_parquet(tmp_path / "n.parquet", com_e3=True))
    assert not set(COLS_RENDA_MALHA) & set(antiga.columns)  # malha antiga: nada inventado
    pd.testing.assert_frame_equal(nova[antiga.columns], antiga)
    assert nova.set_index("hex_id").loc["h1", COL_RENDA_DOM_MALHA] == 4000.0
    assert pd.isna(nova.set_index("hex_id").loc["h3", COL_RENDA_DOM_MALHA])
    # Idempotente: rodar de novo sobre a saida nao duplica nem muda nada.
    de_novo = malha.sobrepor_renda_da_malha(nova, tmp_path / "n.parquet")
    pd.testing.assert_frame_equal(de_novo[nova.columns], nova)


def test_orfao_admitido_leva_as_colunas(tmp_path):
    caminho = _malha_parquet(tmp_path / "n.parquet", com_e3=True)
    out = malha.admitir_orfaos_da_malha(_censo(), caminho).set_index("hex_id")
    assert out.loc["h2", COL_RENDA_PC_MALHA] == 1100.0
    antiga = malha.admitir_orfaos_da_malha(_censo(), _malha_parquet(tmp_path / "a.parquet", com_e3=False))
    assert not set(COLS_RENDA_MALHA) & set(antiga.columns)


# --------------------------------------------------------------------------------
# 5. Superficies do piloto herdam pela linha
# --------------------------------------------------------------------------------


def test_piloto_tooltip_e_ficha_herdam(staging, monkeypatch):
    servidor = Path(__file__).resolve().parents[2] / "web" / "server"
    if str(servidor) not in sys.path:
        sys.path.insert(0, str(servidor))
    import app as pilot

    monkeypatch.setattr(pilot, "STAGING_DIR", staging)
    pilot._renda_staging_configurado.cache_clear()
    pilot._k_calibracao_renda.cache_clear()
    pd.DataFrame({"metodo_calibracao_renda_malha": ["multiplicativo_global_k=1.1"]}).to_parquet(
        staging / renda_hex.CENSO_MALHA_PARQUET
    )
    try:
        base = pd.Series(
            {
                "hex_id": "a",
                "uf": "SP",
                "cod_municipio": "3550308",
                "renda_leitura": 1100.0,
                "renda_origem": CALIBRADA,
            }
        )
        com = base.copy()
        com[COL_RENDA_DOM_MALHA] = 5000.0
        com[COL_RENDA_PC_MALHA] = 2000.0
        assert pilot._renda_domiciliar_hex(com) == round(5000.0 * F_DOM)
        assert pilot._renda_per_capita_hex(com) == round(2000.0 * F_PC)
        # Sem as colunas: o numero de antes.
        assert pilot._renda_domiciliar_hex(base) == round(1100.0 / 1.1 * 3.2 * 1.5 * F_DOM)
    finally:
        pilot._renda_staging_configurado.cache_clear()
        pilot._k_calibracao_renda.cache_clear()
