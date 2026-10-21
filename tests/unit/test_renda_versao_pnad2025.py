"""E2 da correcao da renda (DEC-075): a versao VIGENTE brasileira e a da PNAD Continua 2025.

Trava o que o dono aprovou em 2026-10-20:
  - fatores nacionais (Brasil inteiro, mesma visita, media geometrica v1/v5);
  - excecoes por UF APROVADAS pela regra (L = 7% nas duas visitas, mesmo sinal, n >= 5.000):
    PE e MS -- e so elas;
  - a amarracao com a DEC e com o relatorio de mudanca versionado (sha256);
  - a v0 (CAGED) continua no diretorio e e alcancavel pelo rollback por env;
  - a AR nao muda.

Os numeros da versao sao cravados AQUI de proposito: este e o teste da versao. Superficie
nenhuma crava fator -- elas leem do modulo (varredura de ponto unico).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest

from motor_expansao.renda import (
    ENV_VERSAO,
    carregador,
    carregar_fatores,
    fator,
    fatores_do_health,
    renda_domiciliar,
    renda_per_capita,
)

_REPO = Path(__file__).resolve().parents[2]
VERSAO = "2026-10_pnad2025_v1"
VERSAO_V0 = "2026-08_caged_v0"

NACIONAL = (1.34005575, 1.24695996, 0.93054448)
EXCECOES = {
    "PE": (1.4816307, 1.34606215, 0.90853146),
    "MS": (1.23688697, 1.16070803, 0.93842144),
}


@pytest.fixture(autouse=True)
def _vigente_do_pacote(monkeypatch):
    monkeypatch.delenv(ENV_VERSAO, raising=False)
    monkeypatch.setattr(carregador, "_pais_padrao", lambda: "BR")
    carregar_fatores.cache_clear()
    yield
    carregar_fatores.cache_clear()


def _trio(g) -> tuple[float, float, float]:
    return (g.per_capita, g.domiciliar, g.moradores)


def test_vigente_br_e_a_versao_da_pnad_2025():
    f = carregar_fatores("BR")
    assert f.versao == VERSAO
    assert f.fixada_por_env is False
    assert f.ano_base_renda == 2022 and f.data_referencia_base == "2022-07"
    assert f.ano_alvo == 2025
    assert f.fonte["pesquisa"].startswith("PNAD")
    assert _trio(f.nacional) == pytest.approx(NACIONAL, abs=1e-8)
    assert fatores_do_health() == {"versao": VERSAO, "fixada_por_env": False}


def test_excecoes_aprovadas_sao_pe_e_ms_com_fator_proprio():
    f = carregar_fatores("BR")
    assert sorted(f.excecoes_aprovadas) == ["MS", "PE"]
    assert sorted(f.candidatas_regra) == ["MS", "PE"]
    for uf, esperado in EXCECOES.items():
        assert _trio(f.grupo(uf)) == pytest.approx(esperado, abs=1e-8), uf
        assert fator(uf, "per_capita") == f.excecoes_aprovadas[uf].per_capita
        assert fator(uf, "domiciliar") == f.excecoes_aprovadas[uf].domiciliar
    # PE cresceu acima do pais e MS abaixo: o sinal da regra.
    assert f.grupo("PE").per_capita > f.nacional.per_capita > f.grupo("MS").per_capita
    # Toda outra UF (e UF ausente) usa o nacional.
    for uf in ("SP", "RJ", "AP", "RR", "RO", "PR", None):
        assert f.grupo(uf) is f.nacional, uf
    regra = f.regra_excecao or {}
    assert regra["limiar"] == 0.07 and regra["n_min"] == 5000
    for uf in EXCECOES:
        assert f.evidencias_excecao[uf].startswith("regra de excecao (limiar 7%, n_min 5000)")


def test_versao_amarrada_a_dec_e_ao_relatorio_versionado():
    f = carregar_fatores("BR")
    assert f.dec == "DEC-075"
    assert f.aprovado_por == "Felipe Silva (2026-10-20)"
    assert (_REPO / "docs" / "decisions" / "DEC-075.md").is_file()
    rel = f.relatorio or {}
    caminho = _REPO / rel["caminho"]
    assert caminho.is_file(), caminho
    # O blob do git e LF (`docs/**/*.md text eol=lf`); o checkout no Windows pode ser CRLF.
    conteudo = caminho.read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(conteudo).hexdigest() == rel["sha256"]
    assert VERSAO.encode() in conteudo


def test_rotulo_de_tela_curto_e_sem_fator():
    # Vai para a tela ("Fonte: Censo 2022 ... · <rotulo>"): um fator aqui seria falso para PE e
    # MS, e a proveniencia detalhada e so log e /api/health (decisao do dono).
    assert carregar_fatores("BR").rotulo_referencia == "2025 (PNAD Contínua; Censo jul/2022)"


def test_per_capita_com_o_proprio_fator_na_versao_nova():
    v = np.array([1494.49, 800.0, 12_000.0])
    u = np.array([1.43119, 1.2, 1.9])
    m = np.array([2.8, 3.4, 2.1])
    for uf in ("SP", "PE", "MS"):
        g = carregar_fatores("BR").grupo(uf)
        dom = renda_domiciliar(v, u, uf)
        pc = renda_per_capita(v, u, m, uf)
        # dom / pc = moradores x F_dom / F_pc -- a per capita NAO e a domiciliar / moradores.
        np.testing.assert_allclose(dom / pc, m * g.domiciliar / g.per_capita, rtol=1e-12)
        assert not np.allclose(pc, dom / m, rtol=1e-6), uf


def test_v0_continua_no_diretorio_para_rollback(monkeypatch):
    assert (carregador.DIR_FATORES / "BR" / f"{VERSAO_V0}.json").is_file()
    monkeypatch.setenv(ENV_VERSAO, VERSAO_V0)
    carregar_fatores.cache_clear()
    f = carregar_fatores("BR")
    assert f.versao == VERSAO_V0 and f.fixada_por_env is True
    assert f.excecoes_aprovadas == {}


def test_ar_intocada():
    f = carregar_fatores("AR")
    assert f.versao == "2026-08_sem_atualizacao_v0"
    assert _trio(f.nacional) == (1.0, 1.0, 1.0)
