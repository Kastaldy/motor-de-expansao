"""Bloco C — o gate de PAÍS: "esta instância oferece esta rota de verdade?"

Até aqui (Bloco A + Bloco B) o backend já lê o perfil para RÓTULO e para RÉGUA; nada
ainda impedia um usuário com a aba "mapa" de bater direto em `/api/estados` numa
instância argentina e receber o funil inteiro — código plausível, sobre dado que a
Argentina não tem pronto (0.6). `REGRAS_DE_ACESSO` (web/server/acesso.py) não fecha
isso: é tabela de UNIÃO sobre a permissão do USUÁRIO ("/api/uf/" aceita
`{"mapa","oportunidades"}`, e a Argentina TEM "mapa" — passaria).

Este arquivo trava a tabela NOVA, `SUPERFICIE_DA_ROTA`, que responde uma pergunta
diferente ("esta INSTÂNCIA tem a superfície?"), casada por CONJUNÇÃO contra
`perfil.superficies`, e a checagem irmã `ROTAS_QUE_EXIGEM_MALHA_MUNICIPAL` — para as
quatro rotas que dependem da malha adm2 (`api/service._carregar_malha`), um recurso
que `superficies` não modela porque `ponto`/`municipal` não são abas (§3 item 5 do
plano multi-país).

Medido contra os DOIS perfis reais (não um perfil sintético): o Brasil sai 100%
inerte — toda rota do app libera, como hoje — e a Argentina libera exatamente
`mapa` + `viabilidade`, bloqueando `oportunidades`, `imobiliaria`, `executiva` e as
quatro rotas de malha, cada uma com 404 nomeando o que falta.
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import acesso  # noqa: E402  (modulo do piloto; web/server no sys.path acima)

from motor_expansao.perfil import PERFIL_BR_EMBARCADO, Perfil, carregar_perfil  # noqa: E402

_PERFIL_AR_JSON = PERFIL_BR_EMBARCADO.parents[1] / "AR" / "perfil.json"


@pytest.fixture(scope="module")
def br() -> Perfil:
    return carregar_perfil(PERFIL_BR_EMBARCADO)


@pytest.fixture(scope="module")
def ar() -> Perfil:
    return carregar_perfil(_PERFIL_AR_JSON)


# --------------------------------------------------------------------------------
# Brasil: o gate tem de ser INERTE — mesma garantia de `test_brasil_habilita_..."
# --------------------------------------------------------------------------------


def test_brasil_libera_toda_rota_com_superficie_declarada(br: Perfil) -> None:
    """Nenhuma rota de `SUPERFICIE_DA_ROTA` pode bloquear o Brasil.

    `test_brasil_habilita_todas_as_superficies` (Bloco A) já prova que
    `perfil.superficies` do Brasil tem as cinco abas; este teste prova que isso
    BASTA para o gate nunca disparar — se um dia uma rota nova pedir uma superficie
    fora do vocabulario de `ABAS_VALIDAS`, este teste acusa antes do deploy.
    """
    for prefixo, _exigidas in acesso.SUPERFICIE_DA_ROTA:
        assert acesso.motivo_bloqueio_pais(prefixo, br) is None, prefixo


def test_brasil_tem_a_malha_entao_as_quatro_rotas_de_ponto_liberam(br: Perfil) -> None:
    for rota in acesso.ROTAS_QUE_EXIGEM_MALHA_MUNICIPAL:
        assert acesso.motivo_bloqueio_pais(rota, br) is None, rota


# --------------------------------------------------------------------------------
# Argentina: exatamente o que a decisao 0.6 manda — nem mais, nem menos
# --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "rota",
    [
        "/api/geocode",
        "/api/cobertura/CB",
        "/api/relatorio/comparacao",
        "/api/viabilidade",
        "/api/faixa-alunos",
        "/api/simulador/xlsx",
        "/api/uf/CB",
        "/api/municipio/CB/Capital",
        "/api/municipios/CB",
        "/api/oportunidades",  # a LISTA agregada — alimenta a ficha do hexagono do mapa
        "/api/imobiliaria/evento/abrir",
        "/api/foto-concorrente/x.jpg",
        "/api/pin-concorrente/x.png",
    ],
)
def test_argentina_libera_mapa_e_viabilidade(ar: Perfil, rota: str) -> None:
    assert acesso.motivo_bloqueio_pais(rota, ar) is None, rota


@pytest.mark.parametrize(
    ("rota", "superficie_que_falta"),
    [
        ("/api/estados", "oportunidades"),
        ("/api/hexagonos", "oportunidades"),
        ("/api/oportunidades/123", "imobiliaria"),  # o DOSSIE, com PII de corretor
        ("/api/rede/carteira", "executiva"),
        ("/api/executiva/SP", "executiva"),
    ],
)
def test_argentina_bloqueia_o_que_a_decisao_06_nao_libera(
    ar: Perfil, rota: str, superficie_que_falta: str
) -> None:
    """Mesmo com "mapa" concedida, a UNIAO de `REGRAS_DE_ACESSO` nao pode vazar aqui.

    `/api/estados` aceita SO' `{"oportunidades"}` no gate de usuario — jamais passaria
    por "mapa" mesmo hoje. E' `/api/oportunidades/123` (dossie) e as rotas de
    `/api/rede/`/`/api/executiva/` que fariam a diferenca ficar invisivel se este
    gate herdasse `REGRAS_DE_ACESSO` em vez de ter tabela propria.
    """
    detalhe = acesso.motivo_bloqueio_pais(rota, ar)
    assert detalhe is not None, f"{rota} deveria estar bloqueada na Argentina"
    assert repr(superficie_que_falta) in detalhe
    assert "Argentina" in detalhe


@pytest.mark.parametrize(
    "rota",
    ["/api/ponto", "/api/resolver-ponto", "/api/relatorio/municipal", "/api/relatorio/pontual"],
)
def test_argentina_com_malha_libera_as_quatro_rotas_de_ponto(ar: Perfil, rota: str) -> None:
    """P7 fechada em 2026-09-03: a malha adm2 chegou (dados/malha_admin do Juan,
    529 departamentos -> ibge/municipios_<UF>.geojson via exportador) e o perfil AR
    real virou malha_municipal_disponivel=true — as rotas de ponto liberam, e com o
    /api/relatorio/pontual o carimbo do Bloco C+ no PDF sai da dormencia."""
    assert acesso.motivo_bloqueio_pais(rota, ar) is None, rota


@pytest.mark.parametrize(
    "rota",
    ["/api/ponto", "/api/resolver-ponto", "/api/relatorio/municipal", "/api/relatorio/pontual"],
)
def test_pais_sem_malha_bloqueia_as_quatro_rotas_com_404_nomeado(ar: Perfil, rota: str) -> None:
    """O comportamento que motivou o campo, agora provado com perfil SINTETICO (o
    proximo pais sem malha): as quatro rotas que estourariam 500 na primeira
    coordenada clicada viram 404 nomeado ANTES de chegar la'."""
    sem_malha = dataclasses.replace(ar, malha_municipal_disponivel=False)
    detalhe = acesso.motivo_bloqueio_pais(rota, sem_malha)
    assert detalhe is not None, rota
    assert "malha municipal" in detalhe
    assert "Argentina" in detalhe


def test_rotas_livres_nunca_sao_alcancadas_pelo_gate_de_pais(ar: Perfil) -> None:
    """`/api/metodologia`, `/api/me` etc. — livres por desenho, nos dois gates."""
    for rota in acesso.ROTAS_LIVRES:
        assert acesso.motivo_bloqueio_pais(rota, ar) is None, rota


# --------------------------------------------------------------------------------
# A tabela em si: forma e semantica
# --------------------------------------------------------------------------------


def test_ponto_e_municipal_nao_aparecem_em_superficie_da_rota() -> None:
    """`ponto`/`municipal` NAO SAO ABAS — se aparecessem aqui, `SUPERFICIE_VALIDAS`
    (Bloco A) teria de crescer para alem de `ABAS_VALIDAS`, e essa nao e' a decisao."""
    todas_exigidas: set[str] = set()
    for _prefixo, exigidas in acesso.SUPERFICIE_DA_ROTA:
        todas_exigidas |= exigidas
    assert todas_exigidas <= acesso.ABAS_VALIDAS
    assert "ponto" not in todas_exigidas
    assert "municipal" not in todas_exigidas


def test_rotas_de_malha_nao_duplicam_entrada_em_superficie_da_rota() -> None:
    """As quatro rotas de malha tem checagem PROPRIA — nao devem ganhar tambem uma
    entrada em `SUPERFICIE_DA_ROTA` que a checagem de malha jamais executaria (a
    ordem de `motivo_bloqueio_pais` testa superficie primeiro)."""
    prefixos_superficie = {p for p, _ in acesso.SUPERFICIE_DA_ROTA}
    for rota in acesso.ROTAS_QUE_EXIGEM_MALHA_MUNICIPAL:
        assert rota not in prefixos_superficie, rota

