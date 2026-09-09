"""DEC-048 — as unidades de REDE do agregador entram no universo de cadeia.

O que estes testes travam sao as decisoes que, tomadas errado, produzem um NUMERO PLAUSIVEL em
vez de um erro:

  · D3  a dedup e' a de `dedup_cadeias_do_feed` (pressao_competitiva.py), via a coluna
        `tem_pin_proprio` ja' materializada em `vulnerabilidade_ma_redes.parquet` -- NAO uma
        reimplementacao aqui. Reimplementar so' com 2 das 3 regras da DEC-034/BLK-MA-17-FU4
        (revisao de codigo, 2026-09-08) deixava passar ~400 duplicatas que so' o casamento por
        NOME pega -- a mecanica da dedup em si tem cobertura propria em
        `tests/unit/vulnerabilidade/test_dedup_por_nome.py` e vizinhos; aqui so' o CONTRATO
        importa: `unir_cadeias` respeita o que `tem_pin_proprio` diz;
  · D4  insumo ausente (arquivo ou coluna) tem de reproduzir o comportamento anterior, senao o
        codigo nao pode entrar antes da regeneracao do parquet;
  · D5  o produtor da oferta saia LIMPO do guard -- regressao de governanca.

Fixtures 100% sinteticas: os parquets reais sao gitignored e nao existem no CI.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from motor_expansao.pipelines.enriquecimento_espacial_hexagonos import unir_cadeias

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


def _feed(*linhas, tem_pin_proprio=True) -> pd.DataFrame:
    """(rede, lat, lng) — o artefato `vulnerabilidade_ma_redes`, ja' com a dedup materializada.

    `tem_pin_proprio=True` por default: a maioria dos testes aqui quer simular a unidade
    SOBREVIVENTE da dedup (o caso "academia nova"). Os testes que exercitam o contrato de
    `tem_pin_proprio` passam o valor explicitamente.
    """
    n = len(linhas)
    pin = tem_pin_proprio if isinstance(tem_pin_proprio, list) else [tem_pin_proprio] * n
    return pd.DataFrame({
        "rede": [x[0] for x in linhas],
        "lat": [x[1] for x in linhas],
        "lng": [x[2] for x in linhas],
        "nome": [f"Unidade {i}" for i in range(n)],
        "tem_pin_proprio": pin,
    })


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


# --- D3: o contrato com `tem_pin_proprio` ------------------------------------

def test_tem_pin_proprio_true_entra_como_nova():
    """Sobrevivente da dedup (o que a DEC-048 chama de "academia nova")."""
    cadastro = _cadastro(("smart_fit", LAT, LNG))
    feed = _feed(("selfit", _desloca(LAT, 900.0), LNG), tem_pin_proprio=True)
    assert len(unir_cadeias(cadastro, feed)) == 2


def test_tem_pin_proprio_false_nao_entra():
    """O CASO DO ACHADO (revisao 2026-09-08): colapsada pela dedup nao pode contar como nova.

    Sem checar `tem_pin_proprio`, esta unidade (mesma coisa que ja' esta' no cadastro, so' que
    geocodificada diferente pelas duas fontes) entraria e infla a oferta em duplicidade.
    """
    cadastro = _cadastro(("selfit", LAT, LNG))
    feed = _feed(("selfit", _desloca(LAT, 900.0), LNG), tem_pin_proprio=False)
    assert len(unir_cadeias(cadastro, feed)) == 1


def test_tem_pin_proprio_ausente_entra_tudo():
    """Artefato antigo (pre-BLK-MA-17), sem a coluna: conservador, mesmo regime de `_oferta_unida`
    (DEC-046) -- sem saber quem sobreviveu a dedup, o codigo nao arrisca descartar concorrencia
    real."""
    cadastro = _cadastro(("smart_fit", LAT, LNG))
    feed = _feed(("selfit", _desloca(LAT, 900.0), LNG)).drop(columns=["tem_pin_proprio"])
    assert len(unir_cadeias(cadastro, feed)) == 2


def test_mistura_de_pin_proprio_filtra_so_as_true():
    cadastro = _cadastro(("smart_fit", LAT, LNG))
    feed = _feed(
        ("selfit", _desloca(LAT, 300.0), LNG),
        ("bluefit", _desloca(LAT, 600.0), LNG),
        tem_pin_proprio=[True, False],
    )
    uni = unir_cadeias(cadastro, feed)
    assert len(uni) == 2
    assert set(uni["rede"]) == {"smart_fit", "selfit"}


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


def test_saida_tem_coordenada_float64_pura():
    """DTYPE da saida, nao so' "nao levantou" — foi por aqui que o pipeline real quebrou.

    O cadastro guarda float64 e o feed guarda `Float64` nullable; o `concat` promove a coluna
    para nullable, e `calc_comp_metrics` faz `.values` direto sobre as duas colunas — o que
    sobre nullable devolve `object` e derruba o `np.radians`. O teste anterior passava porque
    exercitava `unir_cadeias` ISOLADA: verificava que nao levantava, nao o que devolvia.
    """
    cadastro = _cadastro(("smart_fit", LAT, LNG))
    feed = _feed(("selfit", _desloca(LAT, 900.0), LNG))
    feed["lat"] = feed["lat"].astype("Float64")
    feed["lng"] = feed["lng"].astype("Float64")
    uni = unir_cadeias(cadastro, feed)
    assert uni["lat"].dtype == "float64"
    assert uni["lng"].dtype == "float64"
    # a prova de fogo: o array que o consumidor monta tem de ser numerico de verdade
    assert uni[["lat", "lng"]].values.dtype == "float64"


def test_saida_alimenta_calc_comp_metrics_sem_quebrar():
    """Teste de INTEGRACAO curto: `unir_cadeias` -> `calc_comp_metrics`, que e' o caminho real.

    Os testes de unidade nao pegaram o defeito porque nenhum ligava as duas pontas.
    """
    import numpy as np

    from motor_expansao.pipelines.enriquecimento_espacial_hexagonos import calc_comp_metrics

    cadastro = _cadastro(("smart_fit", LAT, LNG))
    feed = _feed(("selfit", _desloca(LAT, 900.0), LNG))
    feed["lat"] = feed["lat"].astype("Float64")
    feed["lng"] = feed["lng"].astype("Float64")
    metrics = calc_comp_metrics(np.radians(np.array([[LAT, LNG]])), unir_cadeias(cadastro, feed))
    assert metrics["n_concorrentes_mapeados_2km"][0] == 2


def test_coordenada_nula_no_feed_e_descartada_sem_excecao():
    cadastro = _cadastro(("smart_fit", LAT, LNG))
    feed = pd.DataFrame({
        "rede": ["selfit"], "lat": [None], "lng": [None], "nome": ["X"],
        "tem_pin_proprio": [True],
    })
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
