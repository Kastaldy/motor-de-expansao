"""O perfil `master` so' alcanca as leituras recortadas da Visao Executiva -- e nada mais.

Decisao de 17/11/2026 (DEC-087, migration 025): o master franqueado entra no piloto com UMA
capacidade, `rede.ver_propria`, e o gate a aceita no lugar de `rede.ver` so' numa allowlist
FECHADA (`acesso.rota_da_rede_propria`). Este teste varre as rotas que o FastAPI REGISTROU de fato,
e nao a tabela declarada, no molde de `test_sem_identidade_nada_passa.py`: o conjunto do que passa
tem de ser EXATAMENTE as seis leituras abaixo.

Por que travar o conjunto inteiro, e nao so' "os exports nao passam": o prefixo `/api/rede/` cobre
rota nova sem ninguem decidir nada. Uma rota `/api/rede/qualquer-coisa` que nasca amanha com dado
de toda a rede passaria a atender o master em silencio se a allowlist fosse por prefixo -- com o
conjunto travado aqui, ela fica fora do master por construcao, e mudar isso exige mudar este teste
(e aplicar o recorte `_recorte_da_rede` na rota nova).

O que este teste NAO prova: que cada rota da allowlist RECORTA as unidades. Isso e' da rota, e
tem teste proprio do lado do `app.py`. Aqui se prova so' onde o master consegue CHEGAR.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import acesso  # noqa: E402
import app as pilot_app  # noqa: E402

from motor_expansao.db import rbac  # noqa: E402

#: As UNICAS (metodo, rota concreta) que o master alcanca. `{...}` vira `x`, como no molde.
ALCANCE_DO_MASTER = frozenset(
    {
        ("GET", "/api/rede/filtros"),
        ("GET", "/api/rede/carteira"),
        ("GET", "/api/rede/inteligencia"),
        ("GET", "/api/rede/unidade/x"),
        ("GET", "/api/rede/unidade/x/inteligencia"),
        ("GET", "/api/rede/unidade/x/setores"),
    }
)


def _rotas_protegidas() -> list[tuple[str, str]]:
    """(metodo, caminho concreto) de toda rota /api/* registrada que NAO e' livre."""
    saida: list[tuple[str, str]] = []
    for rota in pilot_app.app.routes:
        molde = getattr(rota, "path", "")
        if not molde.startswith("/api/") or molde in acesso.ROTAS_LIVRES:
            continue
        concreto = re.sub(r"\{[^}]+\}", "x", molde)
        for metodo in sorted(getattr(rota, "methods", None) or ()):
            if metodo in ("HEAD", "OPTIONS"):
                continue
            saida.append((metodo, concreto))
    return saida


def _negada(caminho: str, usuario: str, motivo: str | None) -> bool:
    """O middleware nega por DUAS camadas: a allowlist do painel (404) e o gate (403)."""
    return acesso.bloqueio_acessos(caminho, usuario) or motivo is not None


@pytest.fixture
def _master(monkeypatch: pytest.MonkeyPatch) -> str:
    """Identidade dublada do master: so' `rede.ver_propria`, sem painel de acessos na env."""
    monkeypatch.delenv(rbac.ENV_DEV_USUARIO, raising=False)
    monkeypatch.delenv(rbac.ENV_DEV_IDENTIDADE, raising=False)
    monkeypatch.delenv(rbac.ENV_SINAL_PRODUCAO, raising=False)
    monkeypatch.delenv(acesso.ENV_ADMIN_ACESSOS, raising=False)

    def falsa(_remote_user: object) -> rbac.Identidade:
        return rbac.Identidade(
            id_usuario=99,
            login="dalmo_ribeiro",
            perfil="master",
            permissoes=frozenset({acesso.CAPACIDADE_REDE_PROPRIA}),
            paises=frozenset({"BR"}),
        )

    monkeypatch.setattr(rbac, "identidade", falsa)
    return "dalmo_ribeiro"


def test_ha_rotas_para_conferir_e_o_alcance_esta_registrado() -> None:
    """Guarda contra o teste passar em branco, e contra uma entrada da allowlist que nao casa com
    rota nenhuma (renomearam a rota e a lista ficou para tras)."""
    rotas = set(_rotas_protegidas())
    assert len(rotas) >= 30
    faltando = sorted(ALCANCE_DO_MASTER - rotas)
    assert not faltando, f"rotas do alcance do master que o app nao registra mais: {faltando}"


def test_o_master_so_passa_nas_leituras_da_executiva(_master: str) -> None:
    passaram = {
        (m, c)
        for m, c in _rotas_protegidas()
        if not _negada(c, _master, acesso.motivo_bloqueio_por_banco(c, m, _master))
    }
    a_mais = sorted(passaram - ALCANCE_DO_MASTER)
    a_menos = sorted(ALCANCE_DO_MASTER - passaram)
    assert not a_mais, (
        f"rotas que atendem o master SEM estar no alcance decidido: {a_mais}. Se e' de proposito, "
        "a rota tem de aplicar `_recorte_da_rede` e entrar em `acesso.ROTAS_DA_REDE_PROPRIA` e aqui."
    )
    assert not a_menos, f"o master perdeu leituras da Executiva: {a_menos}"


def test_as_leituras_do_master_tambem_respeitam_o_gate_de_pais(_master: str) -> None:
    """A allowlist nao cria superficie: as seis rotas seguem exigindo a `executiva` da instancia."""
    for _metodo, caminho in ALCANCE_DO_MASTER:
        assert acesso.superficie_necessaria(caminho) == frozenset({"executiva"}), caminho


# ---------------------------------------------------------------------------
# A tela Masters (027, emenda 2 da DEC-089, 19/11/2026): o master com login próprio abre o PRÓPRIO
# painel. Mesma trava, para a outra allowlist (`acesso.ROTAS_DOS_MASTERS_PROPRIOS`): o conjunto do
# que passa é EXATAMENTE as leituras da Executiva e as do painel do master. Cada rota de masters
# recorta o master pedido (`_masters_do_pedido`), com teste próprio do lado do `app.py`.
# ---------------------------------------------------------------------------

#: As leituras da tela Masters que o master alcança (as do próprio painel e o PDF do relatório).
ALCANCE_DO_MASTER_NA_TELA_MASTERS = frozenset(
    {
        ("GET", "/api/masters"),
        ("GET", "/api/masters/x"),
        ("GET", "/api/masters/x/mapa"),
        ("GET", "/api/masters/x/mapa/camadas"),
        ("GET", "/api/masters/x/setores-pontos"),
        ("GET", "/api/masters/x/setores/x/x"),
        ("GET", "/api/masters/x/recomendacao"),
        ("GET", "/api/masters/x/crescimento"),
        ("GET", "/api/masters/x/estudo"),
        ("GET", "/api/masters/relatorio/x"),
        # O Início do master (19/11/2026): o pedido de imóvel e o estudo de um ponto.
        ("POST", "/api/masters/solicitar-imovel"),
        ("POST", "/api/masters/estudo"),
    }
)


@pytest.fixture
def _master_com_a_tela(monkeypatch: pytest.MonkeyPatch, _master: str) -> str:
    """O master da 025 + 027: `rede.ver_propria` e `masters.ver_proprio`."""

    def falsa(_remote_user: object) -> rbac.Identidade:
        return rbac.Identidade(
            id_usuario=99,
            login=_master,
            perfil="master",
            permissoes=frozenset(
                {acesso.CAPACIDADE_REDE_PROPRIA, acesso.CAPACIDADE_MASTERS_PROPRIO}
            ),
            paises=frozenset({"BR"}),
        )

    monkeypatch.setattr(rbac, "identidade", falsa)
    return _master


def test_o_alcance_na_tela_masters_esta_registrado() -> None:
    faltando = sorted(ALCANCE_DO_MASTER_NA_TELA_MASTERS - set(_rotas_protegidas()))
    assert not faltando, f"rotas da tela Masters que o app nao registra mais: {faltando}"


def test_o_master_com_login_proprio_so_passa_no_proprio_painel(_master_com_a_tela: str) -> None:
    passaram = {
        (m, c)
        for m, c in _rotas_protegidas()
        if not _negada(
            c, _master_com_a_tela, acesso.motivo_bloqueio_por_banco(c, m, _master_com_a_tela)
        )
    }
    esperado = ALCANCE_DO_MASTER | ALCANCE_DO_MASTER_NA_TELA_MASTERS
    a_mais = sorted(passaram - esperado)
    a_menos = sorted(esperado - passaram)
    assert not a_mais, (
        f"rotas que atendem o master SEM estar no alcance decidido: {a_mais}. Se e' de proposito, "
        "a rota tem de aplicar o recorte e entrar na allowlist do `acesso.py` e aqui."
    )
    assert not a_menos, f"o master perdeu leituras: {a_menos}"
