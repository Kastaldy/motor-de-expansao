"""DEC-048 — as unidades de REDE do agregador entram no universo de cadeia.

O que estes testes travam sao as decisoes que, tomadas errado, produzem um NUMERO PLAUSIVEL em
vez de um erro:

  · D3  a dedup da DEC-034 tem DOIS bracos, e cada um pega um caso que o outro perde:
        casar a rede ate' 150 m salva concorrente REAL que a distancia pura apagaria; o piso de
        50 m recupera o mesmo endereco com slug divergente. Perder um braco nao levanta nada --
        so' muda a contagem;
  · D3  ordem estavel: sem ela o total publicado muda de uma safra para outra sozinho;
  · D4  insumo ausente tem de reproduzir o comportamento anterior, senao o codigo nao pode
        entrar antes da regeneracao do parquet;
  · D5  o produtor da oferta saia LIMPO do guard -- regressao de governanca.

Fixtures 100% sinteticas: os parquets reais sao gitignored e nao existem no CI.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from motor_expansao.pipelines.enriquecimento_espacial_hexagonos import (
    DEDUP_CADEIA_COORD_M,
    DEDUP_CADEIA_REDE_M,
    unir_cadeias,
)

LAT, LNG = -23.55, -46.63


def _desloca(lat: float, metros: float) -> float:
    """Desloca a latitude em `metros` (1 grau de latitude ~ 111.320 m)."""
    return lat + metros / 111_320.0


def _cadastro(*linhas) -> pd.DataFrame:
    """(rede, lat, lng, status_registro) — o cadastro `concorrentes_mapeados`."""
    return pd.DataFrame({
        "rede": [x[0] for x in linhas],
        "lat": [x[1] for x in linhas],
        "lng": [x[2] for x in linhas],
        "status_registro": [x[3] if len(x) > 3 else "valido" for x in linhas],
    })


def _feed(*linhas, nomes=None) -> pd.DataFrame:
    """(rede, lat, lng) — o feed do agregador."""
    return pd.DataFrame({
        "rede": [x[0] for x in linhas],
        "lat": [x[1] for x in linhas],
        "lng": [x[2] for x in linhas],
        "nome": nomes or [f"Unidade {i}" for i in range(len(linhas))],
    })


# --- os limiares da DEC-034 --------------------------------------------------

def test_limiares_sao_os_da_dec034():
    assert DEDUP_CADEIA_REDE_M == 150.0
    assert DEDUP_CADEIA_COORD_M == 50.0


# --- D4: insumo ausente reproduz o comportamento anterior --------------------

def test_sem_o_feed_o_universo_e_so_o_cadastro():
    cadastro = _cadastro(("smart_fit", LAT, LNG), ("bluefit", _desloca(LAT, 800.0), LNG))
    assert len(unir_cadeias(cadastro, None)) == 2


def test_feed_vazio_equivale_a_ausente():
    cadastro = _cadastro(("smart_fit", LAT, LNG))
    assert len(unir_cadeias(cadastro, _feed())) == 1


def test_descartes_do_cadastro_nao_entram():
    """`status_registro` != valido e' o que a coleta ja' jogou fora."""
    cadastro = _cadastro(
        ("smart_fit", LAT, LNG),
        ("bodytech", _desloca(LAT, 900.0), LNG, "descartado_duplicado"),
    )
    assert len(unir_cadeias(cadastro, None)) == 1


# --- D3: os DOIS bracos da dedup --------------------------------------------

def test_mesma_rede_a_menos_de_150m_colapsa():
    """Braco do NOME: a mesma Selfit com coordenada levemente diferente nao entra duas vezes."""
    cadastro = _cadastro(("selfit", LAT, LNG))
    feed = _feed(("selfit", _desloca(LAT, 100.0), LNG))
    assert len(unir_cadeias(cadastro, feed)) == 1


def test_rede_DIFERENTE_a_120m_e_academia_NOVA():
    """O braco do nome existe para isto: a distancia pura apagaria um concorrente REAL.

    Duas academias de marcas distintas a 120 m sao duas academias, nao um registro duplicado.
    """
    cadastro = _cadastro(("selfit", LAT, LNG))
    feed = _feed(("panobianco", _desloca(LAT, 120.0), LNG))
    assert len(unir_cadeias(cadastro, feed)) == 2


def test_qualquer_rede_a_menos_de_50m_colapsa():
    """Piso de coordenada: mesmo endereco com slug divergente nao pode virar duas academias."""
    cadastro = _cadastro(("skyfit", LAT, LNG))
    feed = _feed(("sky_fit", _desloca(LAT, 20.0), LNG))
    assert len(unir_cadeias(cadastro, feed)) == 1


def test_mesma_rede_longe_e_unidade_nova():
    cadastro = _cadastro(("selfit", LAT, LNG))
    feed = _feed(("selfit", _desloca(LAT, 900.0), LNG))
    assert len(unir_cadeias(cadastro, feed)) == 2


# --- D3: ordem estavel -------------------------------------------------------

def test_dedup_e_deterministica_sob_reordenacao_do_feed():
    """Sem ordem estavel o total publicado mudaria de safra para safra sozinho."""
    cadastro = _cadastro(("selfit", LAT, LNG))
    pontos = [("selfit", _desloca(LAT, 300.0 * i), LNG) for i in range(1, 7)]
    direto = len(unir_cadeias(cadastro, _feed(*pontos)))
    invertido = len(unir_cadeias(cadastro, _feed(*reversed(pontos))))
    assert direto == invertido


# --- contrato de saida -------------------------------------------------------

def test_saida_serve_ao_calculo_de_metricas():
    """`calc_comp_metrics` le `rede`, `lat`, `lng` e `status_registro` — todas tem de vir."""
    cadastro = _cadastro(("smart_fit", LAT, LNG))
    uni = unir_cadeias(cadastro, _feed(("selfit", _desloca(LAT, 900.0), LNG)))
    assert {"rede", "lat", "lng", "status_registro"}.issubset(uni.columns)
    assert (uni["status_registro"] == "valido").all()
    assert uni["lat"].notna().all() and uni["lng"].notna().all()


def test_coordenada_nullable_float64_do_feed_e_aceita():
    """O artefato do agregador guarda `Float64` NULLABLE; `.values` dele vira `object`."""
    cadastro = _cadastro(("smart_fit", LAT, LNG))
    feed = _feed(("selfit", _desloca(LAT, 900.0), LNG))
    feed["lat"] = feed["lat"].astype("Float64")
    feed["lng"] = feed["lng"].astype("Float64")
    assert len(unir_cadeias(cadastro, feed)) == 2


def test_coordenada_nula_no_feed_e_descartada_sem_excecao():
    cadastro = _cadastro(("smart_fit", LAT, LNG))
    feed = pd.DataFrame({"rede": ["selfit"], "lat": [None], "lng": [None], "nome": ["X"]})
    assert len(unir_cadeias(cadastro, feed)) == 1


# --- D5: regressao de governanca ---------------------------------------------

def test_produtor_da_oferta_e_critico_no_guard():
    """Ele saia LIMPO: a regex dizia `enriquecer`, que nao casa `enriquecimento_...`.

    Sem isto, a PROPRIA mudanca desta DEC seria auto-mergeavel como "Media", sem gate humano.
    """
    raiz = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(raiz / "scripts"))
    import loop_guard

    alvos = [
        "src/motor_expansao/pipelines/enriquecimento_espacial_hexagonos.py",
        "src/motor_expansao/pipelines/enriquecer_outputs_residual_mercado.py",
        "src/motor_expansao/pipelines/calcular_colunas_mercado.py",
    ]
    classes = {v.path: v.classe for v in loop_guard.classificar(alvos)}
    for alvo in alvos:
        assert classes.get(alvo) == "critico", alvo


def test_guard_nao_passou_a_pegar_pipeline_qualquer():
    """A regex ficou mais larga; nao pode ter virado um `pipelines/*` indiscriminado."""
    raiz = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(raiz / "scripts"))
    import loop_guard

    limpo = "src/motor_expansao/pipelines/base_h3_brasil.py"
    assert not loop_guard.classificar([limpo])
