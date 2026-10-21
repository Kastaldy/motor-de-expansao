"""Modulo unico da renda exibida (`motor_expansao.renda`, E0): formula, loader e isolamento.

Cobre os testes 1, 2, 3 e 6 da secao 10.4 item 6 do plano de correcao da renda:
  1. cada renda com o seu fator;
  2. sem dupla correcao (as duas armadilhas da secao 9.3, como casos negativos);
  3. consistencia dom / pc = moradores x F_dom / F_pc;
  6. loader: ausente, invalido, faixa, coerencia, pais, excecao e rollback por env.

Os fatores sinteticos tem F_pc != F_dom (os da PNAD 2025 do plano): e so assim que um teste
consegue PROVAR que a per capita usa o proprio fator. Com a versao 0 (F_pc == F_dom) as
duas grafias coincidem e o defeito passaria calado.
"""

from __future__ import annotations

import ast
import inspect
import json
import logging
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from motor_expansao.renda import (
    ENV_VERSAO,
    FatoresRendaInvalidos,
    InsumoRendaInvalido,
    carregador,
    carregar_fatores,
    configurar_staging,
    fator,
    fator_composto_domiciliar,
    fator_hex,
    fatores_do_health,
    insumos,
    k_calibracao_renda,
    renda_domiciliar,
    renda_domiciliar_hex,
    renda_domiciliar_por_hex,
    renda_per_capita,
    renda_per_capita_hex,
    validar_na_subida,
)
from motor_expansao.renda import hex as renda_hex

_REPO = Path(__file__).resolve().parents[2]

# Fatores PNAD 2025 do plano (secao 9.3), arredondados: F_dom = F_pc x queda de moradores.
F_PC = 1.340
F_DOM = 1.247
F_MOR = 0.9306
PE_PC, PE_DOM, PE_MOR = 1.4816, 1.3461, 0.9085

# Setor real do plano: 355030846000572, Sao Paulo.
V06004, UPLIFT, MORADORES = 1494.49, 1.43119, 2.8


def _versao(versao: str = "2026-10_teste_v1", pais: str = "BR", **trocas) -> dict:
    dados = {
        "versao": versao,
        "pais": pais,
        "ano_base_renda": 2022,
        "data_referencia_base": "2022-07",
        "ano_alvo": 2025,
        "fonte": {"pesquisa": "PNAD Continua (sintetica)", "visitas": [1, 5]},
        "data_extracao": "2026-10-20",
        "metodo": "crescimento na mesma visita, media geometrica v1/v5",
        "nacional": {"per_capita": F_PC, "domiciliar": F_DOM, "moradores": F_MOR},
        "regra_excecao": {"limiar": 0.07, "n_min": 5000, "visitas_consistentes": True},
        "candidatas_regra": ["MS", "PE"],
        "excecoes_aprovadas": {
            "PE": {
                "per_capita": PE_PC,
                "domiciliar": PE_DOM,
                "moradores": PE_MOR,
                "evidencia": "desvio de mesmo sinal nas duas visitas",
            }
        },
        "ponte_ipca": None,
        "dec": "DEC-075",
        "aprovado_por": "teste",
        "relatorio": None,
        "rotulo_referencia": "2025 (PNAD Continua; Censo jul/2022)",
        "artefatos_obrigatorios": [],
        "artefato_k_obrigatorio": False,
    }
    dados.update(trocas)
    return dados


def _gravar(raiz: Path, dados: dict, *, vigente: bool = True, nome: str | None = None) -> Path:
    dir_pais = raiz / dados.get("pais", "BR")
    dir_pais.mkdir(parents=True, exist_ok=True)
    versao = nome or dados["versao"]
    caminho = dir_pais / f"{versao}.json"
    caminho.write_text(json.dumps(dados), encoding="utf-8")
    if vigente:
        (dir_pais / "VIGENTE").write_text(versao + "\n", encoding="utf-8")
    return caminho


@pytest.fixture(autouse=True)
def _isolar(monkeypatch):
    monkeypatch.delenv(ENV_VERSAO, raising=False)
    carregar_fatores.cache_clear()
    yield
    carregar_fatores.cache_clear()
    configurar_staging(None)


@pytest.fixture
def sinteticos(tmp_path, monkeypatch):
    """Versao sintetica vigente em `tmp_path/BR`, servida como a dos fatores do pacote."""
    _gravar(tmp_path, _versao())
    monkeypatch.setattr(carregador, "DIR_FATORES", tmp_path)
    monkeypatch.setattr(carregador, "_pais_padrao", lambda: "BR")
    carregar_fatores.cache_clear()
    return tmp_path


# --------------------------------------------------------------------------------
# 1. Cada renda com o seu fator
# --------------------------------------------------------------------------------


def test_domiciliar_e_per_capita_com_o_proprio_fator_escalar(sinteticos):
    assert renda_domiciliar(V06004, UPLIFT, "SP") == (V06004 * UPLIFT) * F_DOM
    assert renda_per_capita(V06004, UPLIFT, MORADORES, "SP") == (
        (V06004 * UPLIFT) * F_PC
    ) / MORADORES


def test_domiciliar_e_per_capita_vetorizadas(sinteticos):
    rng = np.random.default_rng(7)
    v = rng.uniform(300, 20_000, 500)
    u = rng.uniform(1.2, 2.0, 500)
    m = rng.uniform(1.5, 4.5, 500)
    np.testing.assert_array_equal(renda_domiciliar(v, u, "SP"), (v * u) * F_DOM)
    np.testing.assert_array_equal(renda_per_capita(v, u, m, "SP"), ((v * u) * F_PC) / m)
    sv, su, sm = pd.Series(v), pd.Series(u), pd.Series(m)
    pd.testing.assert_series_equal(renda_domiciliar(sv, su, "SP"), (sv * su) * F_DOM)
    pd.testing.assert_series_equal(
        renda_per_capita(sv, su, sm, "SP"), ((sv * su) * F_PC) / sm
    )


def test_uf_com_excecao_aprovada_usa_o_fator_proprio(sinteticos):
    assert fator("PE", "per_capita") == PE_PC
    assert fator(" pe ", "domiciliar") == PE_DOM
    assert renda_domiciliar(V06004, UPLIFT, "PE") == (V06004 * UPLIFT) * PE_DOM
    assert renda_per_capita(V06004, UPLIFT, MORADORES, "PE") == (
        (V06004 * UPLIFT) * PE_PC
    ) / MORADORES


@pytest.mark.parametrize("uf", [None, float("nan"), "SP", "XX", "MS"])
def test_uf_sem_excecao_aprovada_usa_o_nacional(sinteticos, uf):
    # MS e candidata da regra, mas nao foi aprovada: candidata nao vira fator.
    assert fator(uf, "per_capita") == F_PC
    assert fator(uf, "domiciliar") == F_DOM


def test_tipo_de_fator_invalido(sinteticos):
    with pytest.raises(ValueError, match="tipo de fator"):
        fator("SP", "moradores")


def test_fator_composto_domiciliar(sinteticos):
    assert fator_composto_domiciliar(UPLIFT, "SP") == UPLIFT * F_DOM
    assert fator_composto_domiciliar(UPLIFT, "PE") == UPLIFT * PE_DOM


# --------------------------------------------------------------------------------
# 2. Sem dupla correcao (secao 9.3)
# --------------------------------------------------------------------------------


def test_armadilha_1_per_capita_nao_e_derivada_da_domiciliar(sinteticos):
    pc = renda_per_capita(V06004, UPLIFT, MORADORES, "SP")
    derivada = renda_domiciliar(V06004, UPLIFT, "SP") / MORADORES
    # O valor do plano: R$ 1.023,61. A armadilha daria R$ 952,57 (-6,9%), com a queda
    # de moradores 2022 -> 2025 embutida na per capita.
    assert pc == pytest.approx(1023.61, abs=0.01)
    assert derivada == pytest.approx(952.57, abs=0.01)
    assert pc != derivada
    assert derivada / pc == pytest.approx(F_DOM / F_PC)


def test_armadilha_2_queda_de_moradores_entra_uma_vez_so(sinteticos):
    # `renda_domiciliar` nao recebe moradores: nao ha por onde aplicar a queda de novo.
    assert "moradores" not in inspect.signature(renda_domiciliar).parameters
    dom = renda_domiciliar(V06004, UPLIFT, "SP")
    pc_2022 = (V06004 * UPLIFT) / MORADORES
    duas_vezes = pc_2022 * MORADORES * F_MOR * F_DOM
    # Plano: R$ 2.667,20 certo; R$ 2.482,09 com a queda aplicada duas vezes.
    assert dom == pytest.approx(2667.20, abs=0.01)
    assert duas_vezes == pytest.approx(2482.09, abs=0.05)  # plano usa fatores sem arredondar
    assert dom != pytest.approx(duas_vezes, rel=1e-3)


def test_hex_per_capita_usa_o_proprio_fator(sinteticos, tmp_path):
    staging = tmp_path / "staging"
    _gravar_uplift_municipio(staging)
    configurar_staging(staging)
    base = 1000.0
    pc = renda_per_capita_hex(base, "SP", "3550308")
    dom = renda_domiciliar_hex(base, "SP", "3550308")
    assert pc == round(base * (3.2 * 1.5) * F_PC) / 3.2
    assert dom == base * ((3.2 * 1.5) * F_DOM)
    assert pc != pytest.approx(dom / 3.2, rel=1e-3)


# --------------------------------------------------------------------------------
# 3. Consistencia dom / pc = moradores x F_dom / F_pc
# --------------------------------------------------------------------------------


@pytest.mark.parametrize(("uf", "f_pc", "f_dom"), [("SP", F_PC, F_DOM), ("PE", PE_PC, PE_DOM)])
def test_consistencia_dom_sobre_pc(sinteticos, uf, f_pc, f_dom):
    rng = np.random.default_rng(11)
    v = rng.uniform(300, 20_000, 200)
    u = rng.uniform(1.2, 2.0, 200)
    m = rng.uniform(1.5, 4.5, 200)
    razao = renda_domiciliar(v, u, uf) / renda_per_capita(v, u, m, uf)
    np.testing.assert_allclose(razao, m * f_dom / f_pc, rtol=1e-12)


def test_consistencia_implica_moradores_do_ano_alvo(sinteticos):
    # dom / pc = moradores de 2022 x queda = moradores implicitos de 2025 (plano: 2,6057).
    dom = renda_domiciliar(V06004, UPLIFT, "SP")
    pc = renda_per_capita(V06004, UPLIFT, MORADORES, "SP")
    assert dom / pc == pytest.approx(2.6057, abs=1e-3)


# --------------------------------------------------------------------------------
# Versao 0: nenhum numero exibido muda
# --------------------------------------------------------------------------------


def test_v0_br_reproduz_o_fator_e_o_rotulo_de_producao():
    f = carregar_fatores("BR")
    assert f.versao == "2026-08_caged_v0"
    assert f.nacional.per_capita == 1.1641
    assert f.nacional.domiciliar == 1.1641
    assert f.nacional.moradores == 1.0
    assert f.excecoes_aprovadas == {}
    assert f.rotulo_referencia == "06/2026 (CAGED; Censo jul/2022 x 1.1641)"
    # O rotulo e o MESMO que `_carregar_fator_temporal` montava a partir do JSON da VPS.
    fim = str(f.fonte["competencia_atual_fim"])
    assert f.rotulo_referencia == (
        f"{fim[4:]}/{fim[:4]} (CAGED; Censo jul/2022 x {float(f.fonte['fator_temporal_renda'])})"
    )
    assert f.artefato_k_obrigatorio is True
    assert f.fixada_por_env is False


def test_v0_ar_e_sem_atualizacao():
    f = carregar_fatores("AR")
    assert f.versao == "2026-08_sem_atualizacao_v0"
    assert (f.nacional.per_capita, f.nacional.domiciliar, f.nacional.moradores) == (1.0, 1.0, 1.0)
    assert f.rotulo_referencia == "julho/2022 (Censo IBGE)"
    assert f.artefatos_obrigatorios == ()
    assert f.artefato_k_obrigatorio is False


def test_todo_pais_empacotado_carrega():
    paises = sorted(p.name for p in carregador.DIR_FATORES.iterdir() if p.is_dir())
    assert {"AR", "BR"} <= set(paises)
    for pais in paises:
        assert carregar_fatores(pais).pais == pais


def test_v0_bit_a_bit_com_a_formula_de_antes(monkeypatch):
    monkeypatch.setattr(carregador, "_pais_padrao", lambda: "BR")
    rng = np.random.default_rng(3)
    v = rng.uniform(300, 20_000, 300)
    u = rng.uniform(1.2, 2.0, 300)
    m = rng.uniform(1.5, 4.5, 300)
    antigo_dom = (v * u) * 1.1641  # censo_point: (renda * uplift) * FATOR_TEMPORAL_RENDA
    np.testing.assert_array_equal(renda_domiciliar(v, u, "SP"), antigo_dom)
    np.testing.assert_array_equal(renda_per_capita(v, u, m, "SP"), antigo_dom / m)
    assert round(fator_composto_domiciliar(1.43119, "SP"), 4) == round(1.43119 * 1.1641, 4)


def test_v0_hex_bit_a_bit_com_o_app_de_antes(monkeypatch, tmp_path):
    monkeypatch.setattr(carregador, "_pais_padrao", lambda: "BR")
    staging = tmp_path / "staging"
    _gravar_uplift_municipio(staging)
    configurar_staging(staging)
    fator_antigo = (3.2 * 1.5) * 1.1641  # renda_hex.fator_domiciliar de antes da E0
    assert fator_hex("SP", "3550308", "domiciliar") == fator_antigo
    for base in (123.456, 987.0, 1451.97, 33333.3):
        dom_antigo = round(base * fator_antigo)  # _num(base * fator)
        assert round(renda_domiciliar_hex(base, "SP", "3550308")) == dom_antigo
        assert renda_per_capita_hex(base, "SP", "3550308") == dom_antigo / 3.2
    df = pd.DataFrame({"hex_id": ["a", "b"], "renda_per_capita": [1500.0, float("nan")]})
    out = renda_domiciliar_por_hex(df, uf="SP", cod_municipio="3550308", staging_dir=staging)
    assert out == {"a": (1500.0 / 1.5) * fator_antigo}


def test_fatores_do_health(sinteticos):
    assert fatores_do_health() == {"versao": "2026-10_teste_v1", "fixada_por_env": False}


# --------------------------------------------------------------------------------
# 6. Loader
# --------------------------------------------------------------------------------


def _carregar(raiz: Path, pais: str = "BR"):
    return carregar_fatores(pais, raiz=raiz)


def test_loader_le_a_versao_sintetica(tmp_path):
    _gravar(tmp_path, _versao())
    f = _carregar(tmp_path)
    assert f.versao == "2026-10_teste_v1"
    assert f.excecoes_aprovadas["PE"].per_capita == PE_PC
    assert f.candidatas_regra == ("MS", "PE")


def test_loader_diretorio_do_pais_ausente(tmp_path):
    with pytest.raises(FatoresRendaInvalidos, match="diretorio do pais"):
        _carregar(tmp_path)


def test_loader_vigente_ausente(tmp_path):
    _gravar(tmp_path, _versao(), vigente=False)
    with pytest.raises(FatoresRendaInvalidos, match="VIGENTE ausente"):
        _carregar(tmp_path)


def test_loader_vigente_vazio(tmp_path):
    _gravar(tmp_path, _versao())
    (tmp_path / "BR" / "VIGENTE").write_text("  \n", encoding="utf-8")
    with pytest.raises(FatoresRendaInvalidos, match="vazio"):
        _carregar(tmp_path)


def test_loader_arquivo_da_versao_ausente(tmp_path):
    _gravar(tmp_path, _versao())
    (tmp_path / "BR" / "VIGENTE").write_text("2099-01_nao_existe", encoding="utf-8")
    with pytest.raises(FatoresRendaInvalidos, match="nao existe"):
        _carregar(tmp_path)


def test_loader_json_invalido(tmp_path):
    caminho = _gravar(tmp_path, _versao())
    caminho.write_text("{ isto nao e json", encoding="utf-8")
    with pytest.raises(FatoresRendaInvalidos, match="JSON invalido"):
        _carregar(tmp_path)


def test_loader_json_que_nao_e_objeto(tmp_path):
    caminho = _gravar(tmp_path, _versao())
    caminho.write_text("[1.1641]", encoding="utf-8")
    with pytest.raises(FatoresRendaInvalidos, match="objeto JSON"):
        _carregar(tmp_path)


@pytest.mark.parametrize("chave", list(carregador._CHAVES_OBRIGATORIAS))
def test_loader_chave_faltando(tmp_path, chave):
    dados = _versao()
    del dados[chave]
    _gravar(tmp_path, dados, nome="2026-10_teste_v1")  # sem `pais`, grava em BR/
    with pytest.raises(FatoresRendaInvalidos, match=chave):
        _carregar(tmp_path)


@pytest.mark.parametrize("chave", ["per_capita", "domiciliar", "moradores"])
def test_loader_fator_nacional_faltando(tmp_path, chave):
    dados = _versao()
    del dados["nacional"][chave]
    _gravar(tmp_path, dados)
    with pytest.raises(FatoresRendaInvalidos, match=f"nacional.{chave}"):
        _carregar(tmp_path)


def test_loader_fonte_sem_pesquisa(tmp_path):
    _gravar(tmp_path, _versao(fonte={"visitas": [1, 5]}))
    with pytest.raises(FatoresRendaInvalidos, match="fonte.pesquisa"):
        _carregar(tmp_path)


def test_loader_versao_difere_do_nome_do_arquivo(tmp_path):
    _gravar(tmp_path, _versao(versao="2026-10_outra"), nome="2026-10_teste_v1")
    with pytest.raises(FatoresRendaInvalidos, match="difere do nome do arquivo"):
        _carregar(tmp_path)


def test_loader_pais_errado(tmp_path):
    dados = _versao(pais="AR")
    dir_br = tmp_path / "BR"
    dir_br.mkdir()
    (dir_br / "2026-10_teste_v1.json").write_text(json.dumps(dados), encoding="utf-8")
    (dir_br / "VIGENTE").write_text("2026-10_teste_v1", encoding="utf-8")
    with pytest.raises(FatoresRendaInvalidos, match="difere do pais pedido"):
        _carregar(tmp_path)


@pytest.mark.parametrize("pais", ["br", "BRA", "../BR", ""])
def test_loader_pais_invalido(tmp_path, pais):
    with pytest.raises(FatoresRendaInvalidos, match="pais invalido"):
        _carregar(tmp_path, pais)


@pytest.mark.parametrize(
    "nacional",
    [
        {"per_capita": 1.81, "domiciliar": 1.81, "moradores": 1.0},
        {"per_capita": 0.89, "domiciliar": 0.89, "moradores": 1.0},
        {"per_capita": 1.5, "domiciliar": 0.6, "moradores": 0.4},
        {"per_capita": 1.0, "domiciliar": 1.9, "moradores": 1.9},
    ],
)
def test_loader_fator_fora_da_faixa(tmp_path, nacional):
    _gravar(tmp_path, _versao(nacional=nacional))
    with pytest.raises(FatoresRendaInvalidos, match="fora da faixa"):
        _carregar(tmp_path)


def test_loader_fator_de_excecao_fora_da_faixa(tmp_path):
    dados = _versao()
    dados["excecoes_aprovadas"]["PE"]["domiciliar"] = 2.0
    _gravar(tmp_path, dados)
    with pytest.raises(FatoresRendaInvalidos, match="excecoes_aprovadas.PE.domiciliar"):
        _carregar(tmp_path)


@pytest.mark.parametrize("valor", [True, "1.34", None])
def test_loader_fator_que_nao_e_numero(tmp_path, valor):
    dados = _versao()
    dados["nacional"]["per_capita"] = valor
    _gravar(tmp_path, dados)
    with pytest.raises(FatoresRendaInvalidos, match="deveria ser numero"):
        _carregar(tmp_path)


def test_loader_incoerencia_nacional(tmp_path):
    # 1,340 x 0,9306 / 1,30 - 1 = -4,1%: muito alem dos 0,5%.
    _gravar(tmp_path, _versao(nacional={"per_capita": F_PC, "domiciliar": 1.30, "moradores": F_MOR}))
    with pytest.raises(FatoresRendaInvalidos, match="incoerente"):
        _carregar(tmp_path)


def test_loader_coerencia_dentro_da_tolerancia(tmp_path):
    # +0,4%: passa (a PNAD real ficou entre -0,005% e +0,011%).
    dom = F_PC * F_MOR / 1.004
    _gravar(tmp_path, _versao(nacional={"per_capita": F_PC, "domiciliar": dom, "moradores": F_MOR}))
    assert _carregar(tmp_path).nacional.domiciliar == dom


def test_loader_incoerencia_na_excecao(tmp_path):
    dados = _versao()
    dados["excecoes_aprovadas"]["PE"]["moradores"] = 0.95
    _gravar(tmp_path, dados)
    with pytest.raises(FatoresRendaInvalidos, match="excecoes_aprovadas.PE.*incoerente"):
        _carregar(tmp_path)


def test_loader_excecao_sem_moradores(tmp_path):
    dados = _versao()
    del dados["excecoes_aprovadas"]["PE"]["moradores"]
    _gravar(tmp_path, dados)
    with pytest.raises(FatoresRendaInvalidos, match="excecoes_aprovadas.PE.moradores"):
        _carregar(tmp_path)


def test_loader_excecao_sem_evidencia(tmp_path):
    dados = _versao()
    del dados["excecoes_aprovadas"]["PE"]["evidencia"]
    _gravar(tmp_path, dados)
    with pytest.raises(FatoresRendaInvalidos, match="evidencia"):
        _carregar(tmp_path)


def test_loader_excecao_fora_das_candidatas(tmp_path):
    _gravar(tmp_path, _versao(candidatas_regra=["MS"]))
    with pytest.raises(FatoresRendaInvalidos, match="nao esta em `candidatas_regra`"):
        _carregar(tmp_path)


def test_loader_relatorio_sem_hash(tmp_path):
    _gravar(tmp_path, _versao(relatorio={"caminho": "docs/x.md"}))
    with pytest.raises(FatoresRendaInvalidos, match="relatorio.sha256"):
        _carregar(tmp_path)


def test_loader_artefato_k_nao_booleano(tmp_path):
    _gravar(tmp_path, _versao(artefato_k_obrigatorio="sim"))
    with pytest.raises(FatoresRendaInvalidos, match="artefato_k_obrigatorio"):
        _carregar(tmp_path)


def test_rollback_por_env_versao_inexistente_e_erro(tmp_path, monkeypatch):
    _gravar(tmp_path, _versao())
    monkeypatch.setenv(ENV_VERSAO, "2025-01_nunca_publicada")
    with pytest.raises(FatoresRendaInvalidos, match=f"nao existe.*{ENV_VERSAO}|{ENV_VERSAO}.*nao existe"):
        _carregar(tmp_path)


def test_rollback_por_env_versao_existente_e_usada(tmp_path, monkeypatch, caplog):
    _gravar(tmp_path, _versao("2026-08_anterior", nacional={"per_capita": 1.1641, "domiciliar": 1.1641, "moradores": 1.0}, excecoes_aprovadas={}))
    _gravar(tmp_path, _versao())  # a vigente e a nova
    monkeypatch.setenv(ENV_VERSAO, "2026-08_anterior")
    with caplog.at_level(logging.WARNING, logger="motor_expansao.renda"):
        f = _carregar(tmp_path)
    assert f.versao == "2026-08_anterior"
    assert f.fixada_por_env is True
    assert f.nacional.per_capita == 1.1641
    assert any("ROLLBACK" in r.getMessage() and r.levelno == logging.WARNING for r in caplog.records)


def test_rollback_por_env_chega_ao_health(sinteticos, monkeypatch):
    _gravar(sinteticos, _versao("2026-08_anterior", excecoes_aprovadas={}), vigente=False)
    monkeypatch.setenv(ENV_VERSAO, "2026-08_anterior")
    carregar_fatores.cache_clear()
    assert fatores_do_health() == {"versao": "2026-08_anterior", "fixada_por_env": True}


@pytest.mark.parametrize("versao", ["../AR/2026-08_sem_atualizacao_v0", ".oculta", "a/b"])
def test_rollback_por_env_nao_escapa_do_diretorio(tmp_path, monkeypatch, versao):
    _gravar(tmp_path, _versao())
    monkeypatch.setenv(ENV_VERSAO, versao)
    with pytest.raises(FatoresRendaInvalidos, match="nome de versao invalido"):
        _carregar(tmp_path)


# --------------------------------------------------------------------------------
# k e subida
# --------------------------------------------------------------------------------


def _gravar_uplift_municipio(staging: Path) -> None:
    staging.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "uf": ["SP"],
            "cod_municipio": ["3550308"],
            "uplift_composicao_final": [1.5],
            "uplift_confiavel": [True],
            "moradores_por_domicilio_municipio": [3.2],
        }
    ).to_parquet(staging / insumos.UPLIFT_MUNICIPIO_ARQUIVO)


def _gravar_carimbo_k(staging: Path, carimbo: str) -> None:
    staging.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"metodo_calibracao_renda_malha": [carimbo]}).to_parquet(
        staging / renda_hex.CENSO_MALHA_PARQUET
    )


def test_k_le_o_carimbo_da_malha(tmp_path):
    _gravar_carimbo_k(tmp_path, "multiplicativo_global_k=1.2335")
    assert k_calibracao_renda(tmp_path) == 1.2335


def test_k_ilegivel_em_dev_cai_no_fallback_com_aviso(tmp_path, monkeypatch, caplog):
    monkeypatch.delenv("MOTOR_DATA_DIR", raising=False)
    with caplog.at_level(logging.WARNING, logger="piloto.renda"):
        assert k_calibracao_renda(tmp_path) == renda_hex.K_CALIBRACAO_FALLBACK
    assert any("fallback" in r.getMessage() for r in caplog.records)


@pytest.mark.parametrize("carimbo", [None, "sem_k_nenhum", "multiplicativo_global_k=9.9"])
def test_k_ilegivel_em_producao_levanta(tmp_path, monkeypatch, carimbo):
    if carimbo is not None:
        _gravar_carimbo_k(tmp_path, carimbo)
    monkeypatch.setattr(carregador, "_pais_padrao", lambda: "BR")
    monkeypatch.setenv("MOTOR_DATA_DIR", str(tmp_path))
    with pytest.raises(InsumoRendaInvalido, match="k de calibracao"):
        k_calibracao_renda(tmp_path)


def test_k_ilegivel_em_producao_de_pais_sem_k_cai_no_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(carregador, "_pais_padrao", lambda: "AR")
    monkeypatch.setenv("MOTOR_DATA_DIR", str(tmp_path))
    assert k_calibracao_renda(tmp_path) == renda_hex.K_CALIBRACAO_FALLBACK


def test_subida_em_dev_sem_artefatos_so_avisa(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(carregador, "_pais_padrao", lambda: "BR")
    monkeypatch.delenv("MOTOR_DATA_DIR", raising=False)
    with caplog.at_level(logging.WARNING):
        f = validar_na_subida(tmp_path)
    assert f.versao == "2026-08_caged_v0"
    assert any("ausente" in r.getMessage() for r in caplog.records)


def test_subida_em_producao_sem_artefato_levanta(tmp_path, monkeypatch):
    monkeypatch.setattr(carregador, "_pais_padrao", lambda: "BR")
    monkeypatch.setenv("MOTOR_DATA_DIR", str(tmp_path))
    _gravar_uplift_municipio(tmp_path)  # falta o de setor
    _gravar_carimbo_k(tmp_path, "multiplicativo_global_k=1.2335")
    with pytest.raises(InsumoRendaInvalido, match="uplift_composicao_setor.parquet"):
        validar_na_subida(tmp_path)


def test_subida_em_producao_com_k_ilegivel_levanta(tmp_path, monkeypatch):
    monkeypatch.setattr(carregador, "_pais_padrao", lambda: "BR")
    monkeypatch.setenv("MOTOR_DATA_DIR", str(tmp_path))
    _gravar_uplift_municipio(tmp_path)
    (tmp_path / insumos.UPLIFT_SETOR_ARQUIVO).write_bytes(b"")
    with pytest.raises(InsumoRendaInvalido, match="k de calibracao"):
        validar_na_subida(tmp_path)


def _gravar_uplift_setor(staging: Path) -> None:
    staging.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"cod_setor": ["355030801000001"], "uplift_composicao_setor": [1.4]}).to_parquet(
        staging / insumos.UPLIFT_SETOR_ARQUIVO
    )


def test_subida_em_producao_completa_passa(tmp_path, monkeypatch):
    monkeypatch.setattr(carregador, "_pais_padrao", lambda: "BR")
    monkeypatch.setenv("MOTOR_DATA_DIR", str(tmp_path))
    _gravar_uplift_municipio(tmp_path)
    _gravar_uplift_setor(tmp_path)
    _gravar_carimbo_k(tmp_path, "multiplicativo_global_k=1.2335")
    assert validar_na_subida(tmp_path).versao == "2026-08_caged_v0"


@pytest.mark.parametrize("defeito", ["sem_coluna", "corrompido"])
def test_subida_em_producao_com_artefato_presente_mas_ilegivel_levanta(
    tmp_path, monkeypatch, defeito
):
    # `is_file` sozinho deixava subir; o hex quebrava depois, rota a rota, com 500.
    monkeypatch.setattr(carregador, "_pais_padrao", lambda: "BR")
    monkeypatch.setenv("MOTOR_DATA_DIR", str(tmp_path))
    _gravar_uplift_setor(tmp_path)
    _gravar_carimbo_k(tmp_path, "multiplicativo_global_k=1.2335")
    arq = tmp_path / insumos.UPLIFT_MUNICIPIO_ARQUIVO
    if defeito == "sem_coluna":
        pd.DataFrame({"uf": ["SP"], "cod_municipio": ["3550308"]}).to_parquet(arq)
    else:
        arq.write_bytes(b"isto nao e parquet")
    with pytest.raises(InsumoRendaInvalido, match="uplift_renda_domiciliar_municipio.*ilegivel"):
        validar_na_subida(tmp_path)


def test_subida_em_dev_com_artefato_ilegivel_so_avisa(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(carregador, "_pais_padrao", lambda: "BR")
    monkeypatch.delenv("MOTOR_DATA_DIR", raising=False)
    _gravar_uplift_municipio(tmp_path)
    (tmp_path / insumos.UPLIFT_SETOR_ARQUIVO).write_bytes(b"lixo")
    with caplog.at_level(logging.WARNING):
        assert validar_na_subida(tmp_path).versao == "2026-08_caged_v0"
    assert any("ilegivel" in r.getMessage() for r in caplog.records)


def test_subida_ar_em_producao_nao_exige_artefato(tmp_path, monkeypatch):
    monkeypatch.setattr(carregador, "_pais_padrao", lambda: "AR")
    monkeypatch.setenv("MOTOR_DATA_DIR", str(tmp_path))
    assert validar_na_subida(tmp_path).pais == "AR"


def test_subida_com_fatores_invalidos_levanta(sinteticos):
    (sinteticos / "BR" / "VIGENTE").write_text("", encoding="utf-8")
    carregar_fatores.cache_clear()
    with pytest.raises(FatoresRendaInvalidos):
        validar_na_subida(sinteticos)


# --------------------------------------------------------------------------------
# Isolamento: o bot nao pode depender do modulo (DEC-049)
# --------------------------------------------------------------------------------

_MODULOS_DO_BOT = (
    "src/motor_expansao/perfil.py",
    "src/motor_expansao/api/coord.py",
    "src/motor_expansao/api/geo.py",
    "src/motor_expansao/api/settings.py",
)


@pytest.mark.parametrize("arquivo", _MODULOS_DO_BOT)
def test_modulos_do_bot_nao_importam_renda(arquivo):
    arvore = ast.parse((_REPO / arquivo).read_text(encoding="utf-8"))
    for no in ast.walk(arvore):
        if isinstance(no, ast.ImportFrom):
            nomes = [no.module or ""] + [f"{no.module}.{a.name}" for a in no.names]
        elif isinstance(no, ast.Import):
            nomes = [a.name for a in no.names]
        else:
            continue
        assert not any(n.startswith("motor_expansao.renda") for n in nomes), (arquivo, nomes)


def test_importar_os_modulos_do_bot_nao_carrega_renda():
    codigo = (
        "import sys\n"
        "import motor_expansao.perfil, motor_expansao.api.coord, "
        "motor_expansao.api.geo, motor_expansao.api.settings\n"
        # O ponto de entrada do container do bot e os modulos que ele importa tarde: um import
        # novo no topo do `telegram_bot` (ex.: `api.service`) passaria sem teste vermelho.
        "import motor_expansao.api.telegram_bot, motor_expansao.api.relatorio_acessos, "
        "motor_expansao.api.maps_geocoder\n"
        "print(sorted(m for m in sys.modules if m.startswith('motor_expansao.renda')))\n"
    )
    saida = subprocess.run(
        [sys.executable, "-c", codigo],
        capture_output=True,
        text=True,
        cwd=_REPO,
        env={**_env_sem_data_dir(), "PYTHONPATH": str(_REPO / "src")},
        timeout=120,
        check=True,
    )
    assert saida.stdout.strip() == "[]"


def _env_sem_data_dir() -> dict[str, str]:
    import os

    return {k: v for k, v in os.environ.items() if k != "MOTOR_DATA_DIR"}



# --------------------------------------------------------------------------------
# Reconstrucao da V06004 (unica outra conta com moradores; R3 do fio de alarme)
# --------------------------------------------------------------------------------


def test_v06004_de_fallback_escalar():
    from motor_expansao.renda import v06004_de_fallback

    assert v06004_de_fallback(1234.5, 400.0, 3.1) == 1234.5
    assert v06004_de_fallback(None, 400.0, 3.1) == 400.0 * 3.1
    assert v06004_de_fallback(float("nan"), 400.0, 3.1) == 400.0 * 3.1
    assert v06004_de_fallback(None, None, 3.1) is None
    assert v06004_de_fallback(None, 400.0, None) is None
    assert math.isnan(v06004_de_fallback(float("nan"), float("nan"), 3.1))


def test_v06004_de_fallback_serie_so_preenche_o_que_falta():
    from motor_expansao.renda import v06004_de_fallback

    v = pd.Series([1000.0, np.nan, np.nan])
    pc = pd.Series([1.0, 412.37, np.nan])
    m = pd.Series([9.0, 2.83917, 3.0])
    out = v06004_de_fallback(v, pc, m)
    assert out.iloc[0] == 1000.0
    assert out.iloc[1] == 412.37 * 2.83917  # bit a bit com a forma antiga
    assert math.isnan(out.iloc[2])
