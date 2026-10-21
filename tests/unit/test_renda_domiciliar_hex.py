"""Testes da renda media domiciliar por HEX no tooltip do PILOTO WEB (web/server/app.py).

Substitui os testes de `dashboard.components._renda_media_domiciliar_series` — modulo
DELETADO no corte do Streamlit (DEC-022). A implementacao de PRODUCAO agora e a do
backend do piloto: `_derivar` (precedencia da renda de leitura) e `_renda_domiciliar_hex`
/ `_renda_per_capita_hex` (renda de leitura x fator do hex; vazio quando falta renda OU
cod_municipio). Desde a E0 o fator do hex (moradores x uplift MUNICIPAIS x fator temporal) e
a conta moram em `motor_expansao.renda.hex` (`fator_hex`), e o fator temporal vem de uma
versao de fatores lida pelo loader -- aqui SINTETICA, servida por `fixar_fatores`.

READ-ONLY sobre o M1 e HERMETICO: os artefatos de staging (tabela municipal de
uplift/moradores) e a versao de fatores sao SINTETICOS em tmp_path — nenhum `data/` em
disco. Formula (corrigida em 2026-08-13): BASE x moradores_muni x uplift_muni x fator_temporal,
onde BASE desfaz a escala da coluna de origem (calibrada / k; renda_per_capita / uplift).
Demais invariantes preservados: fallback calibrada -> renda_per_capita (por LINHA desde a
DEC-058; era por COLUNA ate' 2026-09-10), cod_municipio ausente/NaN -> vazio (sem
estimativa de nivel UF) e cascata municipio -> mediana UF -> nacional dos fatores. No
piloto o "NaN" do tooltip e servido como None (payload JSON-safe via `_num`).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pytest import approx

from motor_expansao.dashboard import constants as _const
from motor_expansao.renda import InsumoRendaInvalido, carregar_fatores, fator, fator_hex
from tests.unit.renda_fixtures import apontar_staging_renda, fixar_fatores

_REPO = Path(__file__).resolve().parents[2]  # tests/unit/ -> raiz do worktree
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import app as pilot  # noqa: E402  (backend do piloto; web/server no sys.path acima)

# ---------------------------------------------------------------------------
# Artefatos SINTETICOS de staging + isolamento do modulo da renda.
#
# `_renda_staging_configurado()` (lru_cache) aponta `motor_expansao.renda.insumos` para
# `pilot.STAGING_DIR` e zera os caches lazy. Os fixtures reapontam STAGING_DIR para tmp_path,
# registram o apontamento e os caches no monkeypatch (`apontar_staging_renda`, restauracao
# pos-teste) e limpam as lru_cache antes E depois — nenhum estado vaza entre testes nem para
# outros arquivos. O fator temporal sintetico e uma versao de fatores (`fixar_fatores`).
# ---------------------------------------------------------------------------

FATOR_TEMPORAL = 1.25  # sintetico, dentro da faixa plausivel [0,9; 1,8] do loader

# 2026-08-13: a coluna calibrada carrega o `k` da calibragem, e a renda domiciliar tem de
# DESFAZE-LO antes de aplicar `moradores x uplift x temporal` — senao o k vira um fator extra
# sobre um uplift que ja converte a escala (+23,35% medido em producao).
#
# 2026-08-14: o k passou a ser lido do CARIMBO do staging hex (`metodo_calibracao_renda` em
# censo2022_setores_calibrado.parquet) — a fonte de onde a coluna calibrada de fato veio; o
# manifesto do artefato GEO tem OUTRO k e desfazia a escala errada. `K` aqui e' a constante
# SINTETICA que o fixture grava no carimbo — pinada de proposito (nada de derivar do codigo:
# um teste que le o esperado da propria funcao testada nao pega regressao nenhuma).
K = 1.1

# Fatores municipais resultantes (moradores x uplift x FATOR_TEMPORAL):
#   3550308: 3.2 x 1.5 x 1.25 = 6.0   | 3509502: 2.5 x 1.2 x 1.25 = 3.75
#   3304557: 2.0 x 1.8 x 1.25 = 4.5
_TABELA_MUNICIPIOS = pd.DataFrame(
    {
        "uf": ["SP", "SP", "RJ"],
        "cod_municipio": ["3550308", "3509502", "3304557"],
        "uplift_composicao_final": [1.5, 1.2, 1.8],
        "uplift_confiavel": [True, True, True],
        "moradores_por_domicilio_municipio": [3.2, 2.5, 2.0],
    }
)


def _apontar_staging(monkeypatch: pytest.MonkeyPatch, staging: Path) -> None:
    monkeypatch.setattr(pilot, "STAGING_DIR", staging)
    # Registra o apontamento e os caches do modulo da renda: o piloto os muta no
    # `_renda_staging_configurado`, e o monkeypatch os restaura no fim do teste.
    apontar_staging_renda(monkeypatch, staging)
    pilot._renda_staging_configurado.cache_clear()
    pilot._k_calibracao_renda.cache_clear()


def _escrever_carimbo_k(staging: Path, carimbo: str) -> None:
    """Grava o staging hex sintetico com o carimbo de calibracao (fonte do k do piloto)."""
    pd.DataFrame({"metodo_calibracao_renda": [carimbo]}).to_parquet(
        staging / pilot._CENSO_HEX_STAGING_PARQUET
    )


@pytest.fixture
def staging_sintetico(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Staging com a tabela municipal sintetica + fator temporal 1.25 + carimbo k=1.1."""
    staging = tmp_path / "staging"
    staging.mkdir()
    _TABELA_MUNICIPIOS.to_parquet(staging / "uplift_renda_domiciliar_municipio.parquet")
    fixar_fatores(monkeypatch, tmp_path, per_capita=FATOR_TEMPORAL)
    _escrever_carimbo_k(staging, f"multiplicativo_global_k={K}")
    _apontar_staging(monkeypatch, staging)
    yield staging
    pilot._renda_staging_configurado.cache_clear()
    pilot._k_calibracao_renda.cache_clear()


@pytest.fixture
def staging_vazio(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Staging VAZIO (o cenario do CI): uplift/moradores caem nos fallbacks nacionais.

    O fator temporal NAO e fixado: e o da versao VIGENTE do pacote (a v0 brasileira), como em
    qualquer instancia sem `MOTOR_DATA_DIR`.
    """
    staging = tmp_path / "staging"
    staging.mkdir()
    monkeypatch.delenv("MOTOR_DATA_DIR", raising=False)
    _apontar_staging(monkeypatch, staging)
    yield staging
    pilot._renda_staging_configurado.cache_clear()
    pilot._k_calibracao_renda.cache_clear()


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "hex_id": ["a", "b", "c"],
            "uf": ["SP", "SP", "RJ"],
            "cod_municipio": ["3550308", "3509502", "3304557"],
            "renda_per_capita_setor_2022_calibrada": [1500.0, 2000.0, np.nan],
            "renda_per_capita": [1400.0, 1900.0, 1700.0],
        }
    )


def _serie_renda_dom(df: pd.DataFrame) -> pd.Series:
    """Renda media domiciliar por linha, pelo MESMO fluxo do endpoint `uf_view`:
    `_derivar` (renda_leitura) -> `_renda_domiciliar_hex` por linha (fator municipal do modulo
    da renda). dtype=object preserva os None do payload."""
    derivado = pilot._derivar(df)
    valores: dict[object, object] = {}
    for idx, linha in derivado.iterrows():
        valores[idx] = pilot._renda_domiciliar_hex(linha)
    return pd.Series(valores, dtype=object)


# ===========================================================================
# Formula e variacao municipal
# ===========================================================================


def test_formula_usa_moradores_e_uplift_municipais(staging_sintetico: Path) -> None:
    assert fator_hex("SP", "3550308", "domiciliar") == approx(6.0)
    assert fator_hex("SP", "3509502", "domiciliar") == approx(3.75)
    r = _serie_renda_dom(_frame())
    assert r.loc[0] == round(1500 / K * 6.0)   # base sem o k, x fator municipal
    assert r.loc[1] == round(2000 / K * 3.75)


def test_varia_por_municipio(staging_sintetico: Path) -> None:
    """Mesma renda per capita, municipios distintos -> fatores distintos -> rendas
    distintas. Com a tabela sintetica os fatores diferem POR CONSTRUCAO (o teste
    antigo, sobre a tabela real, so podia afirmar isso condicionalmente)."""
    df = pd.DataFrame(
        {
            "hex_id": ["a", "b"],
            "uf": ["SP", "SP"],
            "cod_municipio": ["3550308", "3509502"],
            "renda_per_capita_setor_2022_calibrada": [1000.0, 1000.0],
        }
    )
    r = _serie_renda_dom(df)
    assert r.loc[0] == round(1000 / K * 6.0)
    assert r.loc[1] == round(1000 / K * 3.75)
    assert r.loc[0] != r.loc[1]


# ===========================================================================
# Fallback de renda (calibrada -> renda_per_capita)
# ===========================================================================


def test_fallback_para_renda_per_capita_quando_coluna_calibrada_ausente(
    staging_sintetico: Path,
) -> None:
    df = _frame().drop(columns=["renda_per_capita_setor_2022_calibrada"])
    r = _serie_renda_dom(df)
    # Ramo de FALLBACK: `renda_per_capita` (SIDRA) JA e renda domiciliar per capita, entao a
    # base divide pelo UPLIFT do municipio — nao pelo k. Sem isso o uplift entrava DUAS vezes
    # (+54,4% medido, e com dispersao, porque o uplift varia entre municipios).
    assert r.loc[0] == round(1400 / 1.5 * 6.0)   # SP/3550308, uplift 1.5
    assert r.loc[2] == round(1700 / 1.8 * 4.5)   # RJ/3304557, uplift 1.8


def test_calibrada_nula_por_linha_cai_para_a_municipal_daquela_linha(
    staging_sintetico: Path,
) -> None:
    """DEC-058: a precedencia da renda e' por LINHA, nao por COLUNA.

    Ate' 2026-09-10 `_derivar` escolhia UMA coluna de origem para o frame inteiro e a linha
    com a calibrada NULA saia sem renda nenhuma -- mesmo tendo a municipal ao lado. Medido
    no artefato de producao: 234.147 hexagonos (15,18%) nesse estado (AM 129.823, PA 45.941,
    RR 15.562, MT 11.091), todos exibindo tooltip vazio.

    Note a FORMA do caso: a coluna do setor esta' PRESENTE e nula NAQUELA linha. E' o estado
    real de producao -- e era justamente o que o teste antigo (coluna ausente) nao cobria.
    """
    derivado = pilot._derivar(_frame())
    # linhas 0 e 1: setor tem valor -> setor vence
    assert derivado.loc[0, "renda_leitura"] == approx(1500.0)
    assert derivado.loc[0, "renda_origem"] == "renda_per_capita_setor_2022_calibrada"
    # linha 2: setor PRESENTE e NULO -> cai para a municipal DAQUELA linha
    assert derivado.loc[2, "renda_leitura"] == approx(1700.0)
    assert derivado.loc[2, "renda_origem"] == "renda_per_capita"

    r = _serie_renda_dom(_frame())
    # E a escala e' desfeita pelo ramo CERTO: municipal divide pelo uplift (1.8), nao pelo k.
    assert r.loc[2] == round(1700 / 1.8 * 4.5)


def test_renda_origem_e_serie_por_linha_e_nunca_escalar(staging_sintetico: Path) -> None:
    """CONTRATO DE FORMA (DEC-058): `renda_origem` e' uma coluna, com um valor por linha.

    Trava a regressao exata que o PR #327 sofreu: com a origem ESCALAR o aviso
    `renda_municipal` do payload nascia constante `False` em 1.542.531 de 1.542.531
    hexagonos, e quatro ramos de rotulo do front ficavam inalcancaveis. O que este teste
    acrescenta ao de cima e' a FORMA: exige origem DIFERENTE entre duas linhas do MESMO
    frame, entao nenhuma redacao que devolva um valor unico para o frame inteiro passa --
    nem mesmo uma que, por acaso, escolha a coluna certa.
    """
    derivado = pilot._derivar(_frame())
    origens = derivado["renda_origem"]
    assert isinstance(origens, pd.Series)
    assert len(origens) == len(derivado)
    assert origens.nunique() > 1, "renda_origem ficou constante: voltou a ser escolha por COLUNA"
    assert set(origens.dropna()) == {
        "renda_per_capita_setor_2022_calibrada",
        "renda_per_capita",
    }


def test_sem_renda_em_nenhuma_das_colunas_a_origem_e_nula(staging_sintetico: Path) -> None:
    """Linha sem valor em NENHUMA das origens: renda NaN e origem None -- nao "municipal".

    `renda_municipal` do payload le' `renda_origem == "renda_per_capita"`; se a ausencia
    total virasse essa string, o front afirmaria "estimativa municipal" para um tooltip
    vazio.
    """
    df = pd.DataFrame(
        {
            "hex_id": ["a"],
            "uf": ["SP"],
            "cod_municipio": ["3550308"],
            "renda_per_capita_setor_2022_calibrada": [np.nan],
            "renda_per_capita": [np.nan],
        }
    )
    derivado = pilot._derivar(df)
    assert np.isnan(derivado.loc[0, "renda_leitura"])
    assert derivado.loc[0, "renda_origem"] is None


def test_sem_nenhuma_renda_retorna_none(staging_sintetico: Path) -> None:
    df = _frame().drop(columns=["renda_per_capita_setor_2022_calibrada", "renda_per_capita"])
    r = _serie_renda_dom(df)
    assert all(v is None for v in r)


# ===========================================================================
# Sem municipio resolvido -> None (nunca estimativa de nivel UF)
# ===========================================================================


def test_sem_cod_municipio_retorna_none(staging_sintetico: Path) -> None:
    df = _frame().drop(columns=["cod_municipio"])
    r = _serie_renda_dom(df)
    assert all(v is None for v in r)


def test_cod_municipio_nan_por_linha_retorna_none(staging_sintetico: Path) -> None:
    """Hex sem municipio resolvido (cod_municipio NaN, uf presente) -> None, e NAO uma
    estimativa de nivel UF — mesmo com um fator municipal valido em maos."""
    df = pd.DataFrame(
        {
            "hex_id": ["a", "b"],
            "uf": ["SP", "SP"],
            "cod_municipio": ["3550308", np.nan],
            "renda_per_capita_setor_2022_calibrada": [1500.0, 900.0],
        }
    )
    r = _serie_renda_dom(df)
    assert r.loc[0] == round(1500 / K * 6.0)  # municipio resolvido
    assert r.loc[1] is None  # cod_municipio NaN -> tooltip vazio (nao fallback UF)
    # O guardrail vive na PROPRIA funcao: a linha sem cod nao ganha renda nem de nivel UF
    # (SP tem mediana na tabela sintetica, e mesmo assim fica vazia).
    linha_sem_cod = pilot._derivar(df).loc[1]
    assert pilot._renda_domiciliar_hex(linha_sem_cod) is None
    assert pilot._renda_per_capita_hex(linha_sem_cod) is None


# ===========================================================================
# Cascata dos fatores (municipio -> mediana UF -> nacional) e indice
# ===========================================================================


def test_fallback_municipio_ausente_usa_mediana_da_uf_e_depois_nacional(
    staging_sintetico: Path,
) -> None:
    # Municipio fora da tabela -> medianas da UF: moradores med(3.2, 2.5) = 2.85 e
    # uplift med(1.5, 1.2) = 1.35 (so linhas `uplift_confiavel`).
    assert fator_hex("SP", "3599999", "domiciliar") == approx(2.85 * 1.35 * FATOR_TEMPORAL)
    # UF fora da tabela -> constantes nacionais (2.79 x 1.632).
    esperado = (
        _const.MORADORES_DOMICILIO_NACIONAL * _const.UPLIFT_COMPOSICAO_NACIONAL * FATOR_TEMPORAL
    )
    assert fator_hex("ZZ", "9999999", "domiciliar") == approx(esperado)


def test_sem_artefatos_em_dev_cai_no_nacional_com_o_fator_da_versao_vigente(
    staging_vazio: Path,
) -> None:
    """Staging vazio sem `MOTOR_DATA_DIR` (dev/CI): uplift e moradores NACIONAIS do perfil e o
    fator temporal da versao VIGENTE do pacote -- degradacao que mantem o tooltip vivo sem os
    parquets. Ate a E0 o fator caia em 1,0 em silencio (o JSON do staging faltava); agora ele
    vem da imagem, entao dev e producao exibem a mesma escala."""
    f_dom = fator(None, "domiciliar")
    # O F_dom nacional da versao VIGENTE empacotada (lido do modulo, nunca cravado aqui).
    assert f_dom == carregar_fatores().nacional.domiciliar
    esperado = (_const.MORADORES_DOMICILIO_NACIONAL * _const.UPLIFT_COMPOSICAO_NACIONAL) * f_dom
    assert fator_hex("SP", "3550308", "domiciliar") == esperado
    # A subida em dev nao derruba nada: so avisa.
    pilot._init_renda_paths_no_boot()
    r = _serie_renda_dom(_frame())
    # Sem o staging hex, o k cai na CONSTANTE de fallback (nao no K sintetico do carimbo).
    assert r.loc[0] == round(1500.0 / pilot._K_CALIBRACAO_FALLBACK * esperado)


def test_sem_artefatos_em_producao_a_subida_falha(
    staging_vazio: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Com `MOTOR_DATA_DIR` setado (producao) e o staging sem os artefatos obrigatorios da
    versao vigente, o boot do piloto CAI com erro explicito -- nada do fallback silencioso de
    antes, nem do `try/except` que engolia a falha no hook de startup."""
    monkeypatch.setenv("MOTOR_DATA_DIR", os.fspath(staging_vazio.parent))
    with pytest.raises(InsumoRendaInvalido, match="uplift_renda_domiciliar_municipio"):
        pilot._init_renda_paths_no_boot()


def test_ancoragem_no_ibge_o_teste_que_teria_pego_o_defeito(staging_sintetico: Path) -> None:
    """As duas travas de ESCALA que faltavam. Nenhum teste antigo amarrava o hex a uma
    referencia externa nem a superficie do ponto — por isso o defeito viveu.

    (a) Ramo de fallback: `renda_per_capita` do SIDRA JA e renda domiciliar per capita. Logo
        `renda_per_capita x moradores x fator_temporal` E a renda do domicilio, e o uplift NAO
        pode aparecer. Se aparecer, o numero sai inflado pelo proprio uplift.
    (b) Ramo calibrado: a renda domiciliar nao pode carregar o `k`.
    """
    moradores, uplift = 3.2, 1.5  # SP/3550308 na tabela sintetica
    df = pd.DataFrame(
        {
            "hex_id": ["a"],
            "uf": ["SP"],
            "cod_municipio": ["3550308"],
            "renda_per_capita": [1400.0],  # SIDRA: renda DOMICILIAR per capita
        }
    )
    esperado = 1400.0 * moradores * FATOR_TEMPORAL  # sem uplift nenhum
    assert _serie_renda_dom(df).loc[0] == round(esperado)

    df_cal = pd.DataFrame(
        {
            "hex_id": ["a"],
            "uf": ["SP"],
            "cod_municipio": ["3550308"],
            "renda_per_capita_setor_2022_calibrada": [1500.0],
        }
    )
    v06004_per_capita = 1500.0 / K
    assert _serie_renda_dom(df_cal).loc[0] == round(
        v06004_per_capita * moradores * uplift * FATOR_TEMPORAL
    )


def test_renda_per_capita_do_hex_e_a_domiciliar_per_capita(staging_sintetico: Path) -> None:
    """O tooltip do hex e o Relatorio Pontual passam a falar a mesma grandeza.

    Antes o hex exibia a coluna calibrada crua (V06004/moradores x k) enquanto o ponto exibia a
    renda domiciliar per capita — dois numeros para a mesma coordenada.
    """
    df = pd.DataFrame(
        {
            "hex_id": ["a"],
            "uf": ["SP"],
            "cod_municipio": ["3550308"],
            "renda_per_capita_setor_2022_calibrada": [1500.0],
        }
    )
    linha = pilot._derivar(df).loc[0]
    dom = pilot._renda_domiciliar_hex(linha)
    pc = pilot._renda_per_capita_hex(linha)

    # A invariante: domiciliar = per capita x moradores do municipio (3.2) -- com F_pc == F_dom,
    # como na versao sintetica deste arquivo (E0: cada renda com o seu fator).
    assert pc == approx(dom / 3.2, rel=1e-3)
    # E nao e mais a coluna calibrada crua.
    assert pc != approx(1500.0, rel=1e-3)


def test_payload_do_hex_serve_a_per_capita_domiciliar(staging_sintetico: Path) -> None:
    """Trava do PAYLOAD: nao basta a funcao certa existir, `_hex_dict` tem de chama-la.

    Medido por mutacao: sem este teste, trocar o campo `renda` de volta para `renda_leitura`
    (a coluna calibrada crua) passa por TODOS os outros testes deste arquivo.
    """
    df = pd.DataFrame(
        {
            "hex_id": ["a"],
            "lat": [-23.55],
            "lng": [-46.63],
            "uf": ["SP"],
            "cod_municipio": ["3550308"],
            "renda_per_capita_setor_2022_calibrada": [1500.0],
        }
    )
    linha = pilot._derivar(df).loc[0]
    payload = pilot._hex_dict(linha)

    assert payload["renda"] == approx(pilot._renda_per_capita_hex(linha))
    assert payload["renda"] != approx(1500.0, rel=1e-3)  # nao e a calibrada crua
    # A invariante do tooltip: domiciliar = per capita x moradores do municipio (3.2).
    assert payload["renda_dom"] == approx(payload["renda"] * 3.2, rel=1e-3)


def test_payload_sinaliza_fallback_municipal_da_renda(staging_sintetico: Path) -> None:
    """`renda_municipal` avisa o operador quando a renda exibida NAO e' do setor.

    Regressao (pedido de Felipe, 2026-09-08): o hex sem renda de setor cai para
    `renda_per_capita` (SIDRA municipal, o MESMO numero repetido em toda a cidade) e o
    tooltip/ficha mostravam um numero com cara de precisao intraurbana sem avisar a origem.

    A FORMA DO CASO E' O PONTO (DEC-058). Ate' 2026-09-10 este teste montava o hex de
    fallback OMITINDO a coluna do setor -- estado que NAO existe em producao, onde o
    artefato nacional tem a coluna no schema para todos os 1.542.531 hexagonos. Por isso
    ele passava enquanto o aviso era constante `False` nos 1.542.531. Aqui os DOIS hexes
    vivem no MESMO frame, com a coluna PRESENTE, e o segundo tem valor NULO -- a forma real
    dos 234.147 (15,18%) medidos em producao.
    """
    frame = pd.DataFrame(
        {
            "hex_id": ["a", "b"],
            "lat": [-23.55, -23.55],
            "lng": [-46.63, -46.63],
            "uf": ["SP", "SP"],
            "cod_municipio": ["3550308", "3550308"],
            "renda_per_capita_setor_2022_calibrada": [1500.0, np.nan],
            "renda_per_capita": [1400.0, 1800.0],
        }
    )
    derivado = pilot._derivar(frame)

    payload_setor = pilot._hex_dict(derivado.loc[0])
    assert payload_setor["renda_municipal"] is False
    assert payload_setor["renda"] is not None

    payload_municipal = pilot._hex_dict(derivado.loc[1])
    assert payload_municipal["renda_municipal"] is True
    # E o numero aparece: antes da DEC-058 esta linha nao exibia renda NENHUMA.
    assert payload_municipal["renda"] is not None


def test_payload_sinaliza_fallback_municipal_da_populacao(staging_sintetico: Path) -> None:
    """`pop_municipal` avisa o operador quando a populacao exibida NAO e' do setor.

    Mesma familia do teste de renda acima (pedido de Felipe, 2026-09-08): quando
    `fonte_populacao_corte` (produzida por `pop_corte.derive_pop_cut_columns`) vem
    "total_municipal", o `pop_leitura`/`pop` exibido e' o SIDRA da cidade inteira, o
    MESMO numero repetido em todo hexagono -- sem o flag o operador nao tem como saber.
    Ao contrario da renda, aqui o fallback ja' vem PRONTO do pipeline como uma coluna
    de origem (`fonte_populacao_corte`), nao por presenca/ausencia de coluna.
    """
    granular = pd.DataFrame(
        {
            "hex_id": ["a"],
            "lat": [-23.55],
            "lng": [-46.63],
            "uf": ["SP"],
            "cod_municipio": ["3550308"],
            "populacao_corte_hex": [1200.0],
            "fonte_populacao_corte": ["setor_2022"],
        }
    )
    municipal = pd.DataFrame(
        {
            "hex_id": ["b"],
            "lat": [-23.55],
            "lng": [-46.63],
            "uf": ["SP"],
            "cod_municipio": ["3550308"],
            "populacao_corte_hex": [50000.0],
            "fonte_populacao_corte": ["total_municipal"],
        }
    )

    linha_granular = pilot._derivar(granular).loc[0]
    payload_granular = pilot._hex_dict(linha_granular)
    assert payload_granular["pop_municipal"] is False
    assert payload_granular["pop"] == 1200

    linha_municipal = pilot._derivar(municipal).loc[0]
    payload_municipal = pilot._hex_dict(linha_municipal)
    assert payload_municipal["pop_municipal"] is True
    assert payload_municipal["pop"] == 50000


def test_k_da_calibracao_le_o_carimbo_do_staging_hex(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O k vem do carimbo `metodo_calibracao_renda` do STAGING HEX — a fonte de onde a
    coluna calibrada de fato nasce. O manifesto do artefato GEO tem OUTRO k (calibracao
    independente) e nao pode ser usado aqui: desfazia a escala errada (~17% no tooltip).

    Carimbo ausente/ilegivel ou k implausivel cai na constante conhecida — NUNCA em 1,0
    em silencio (reintroduziria a dupla contagem sem pista).
    """
    staging = tmp_path / "staging"
    staging.mkdir()
    monkeypatch.setattr(pilot, "STAGING_DIR", staging)

    for carimbo, esperado in (
        ("multiplicativo_global_k=1.4321", 1.4321),
        ("multiplicativo_global_k=0.5", 0.5),                      # fronteira, plausivel
        ("multiplicativo_global_k=0.4", pilot._K_CALIBRACAO_FALLBACK),  # fora da faixa
        ("multiplicativo_global_k=9.9", pilot._K_CALIBRACAO_FALLBACK),
        ("sem_k_no_texto", pilot._K_CALIBRACAO_FALLBACK),          # carimbo sem k=
    ):
        _escrever_carimbo_k(staging, carimbo)
        pilot._k_calibracao_renda.cache_clear()
        assert pilot._k_calibracao_renda() == approx(esperado)

    # Parquet sem a coluna do carimbo -> fallback.
    pd.DataFrame({"outra_coluna": [1.0]}).to_parquet(staging / pilot._CENSO_HEX_STAGING_PARQUET)
    pilot._k_calibracao_renda.cache_clear()
    assert pilot._k_calibracao_renda() == approx(pilot._K_CALIBRACAO_FALLBACK)

    # Arquivo ausente -> fallback.
    (staging / pilot._CENSO_HEX_STAGING_PARQUET).unlink()
    pilot._k_calibracao_renda.cache_clear()
    assert pilot._k_calibracao_renda() == approx(pilot._K_CALIBRACAO_FALLBACK)
    pilot._k_calibracao_renda.cache_clear()


def test_k_do_carimbo_manda_na_formula_do_hex(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Trava de FONTE: trocar o carimbo do staging muda a renda do hex na mesma proporcao.

    E' o teste que pega a regressao de voltar a ler o k do manifesto do GEO (ou de qualquer
    outra fonte fixa): com o carimbo sintetico em 2.0, a base tem de sair EXATAMENTE
    calibrada/2.0 — nenhuma constante do codigo reproduz isso por coincidencia.
    """
    staging = tmp_path / "staging"
    staging.mkdir()
    _TABELA_MUNICIPIOS.to_parquet(staging / "uplift_renda_domiciliar_municipio.parquet")
    fixar_fatores(monkeypatch, tmp_path, per_capita=FATOR_TEMPORAL)
    _escrever_carimbo_k(staging, "multiplicativo_global_k=2.0")
    _apontar_staging(monkeypatch, staging)

    df = pd.DataFrame(
        {
            "hex_id": ["a"],
            "uf": ["SP"],
            "cod_municipio": ["3550308"],
            "renda_per_capita_setor_2022_calibrada": [1500.0],
        }
    )
    r = _serie_renda_dom(df)
    assert r.loc[0] == round(1500.0 / 2.0 * 6.0)  # base = calibrada / k_do_carimbo
    pilot._renda_staging_configurado.cache_clear()
    pilot._k_calibracao_renda.cache_clear()


def test_preserva_indice_nao_sequencial(staging_sintetico: Path) -> None:
    df = _frame()
    df.index = [10, 20, 30]
    derivado = pilot._derivar(df)
    assert list(derivado.index) == [10, 20, 30]
    r = _serie_renda_dom(df)
    assert list(r.index) == [10, 20, 30]
    # A linha do rotulo 10 casa com o SEU municipio — sem mistura posicional.
    assert r.loc[10] == round(1500 / K * 6.0)
