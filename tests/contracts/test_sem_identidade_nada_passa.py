"""Sem identidade, nenhuma rota que nao seja declaradamente livre atende -- nos DOIS modos.

Preparacao do P19 (15/09). O corte vai trocar a FONTE da identidade (do header do Authelia para
a sessao do proprio motor), e o que precisa sobreviver a essa troca e' uma propriedade simples:
quem chega sem identidade so' alcanca `ROTAS_LIVRES`. Este teste a fixa contra as rotas que o
FastAPI REGISTROU de fato, e nao contra a tabela declarada -- rota nova sem regra fica vermelha.

Os dois modos, porque a producao usa os dois: com o banco no comando, o RBAC; so' com o JSON, o
mapa de abas -- que e' o unico que a instancia AR tem. O modo JSON e' medido no pior caso: um
curinga com TODAS as abas nao sensiveis, e o fail-closed de producao ligado.

Medido antes da correcao de 15/09: 0 rotas passavam com o banco, e 18 so' com o JSON e curinga.
"""

from __future__ import annotations

import json
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


def _negada(caminho: str, motivo: str | None) -> bool:
    """O middleware nega por DUAS camadas: a allowlist do painel (404) e o gate (403)."""
    return acesso.bloqueio_acessos(caminho, None) or motivo is not None


@pytest.fixture
def _anonimo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nem header nem identidade de dev -- com o sinal de producao DESLIGADO, que e' justamente o
    caso em que a identidade de dev entraria se estivesse configurada."""
    monkeypatch.delenv(rbac.ENV_DEV_USUARIO, raising=False)
    monkeypatch.delenv(rbac.ENV_DEV_IDENTIDADE, raising=False)
    monkeypatch.delenv(rbac.ENV_SINAL_PRODUCAO, raising=False)
    monkeypatch.delenv(acesso.ENV_ADMIN_ACESSOS, raising=False)


def test_ha_rotas_protegidas_para_conferir() -> None:
    """Guarda contra o teste passar em branco: coleta vazia nao prova nada."""
    assert len(_rotas_protegidas()) >= 30


def test_com_o_banco_no_comando_anonimo_nao_passa(_anonimo: None) -> None:
    passaram = [
        (m, c)
        for m, c in _rotas_protegidas()
        if not _negada(c, acesso.motivo_bloqueio_por_banco(c, m, None))
    ]
    assert not passaram, f"rotas atendendo requisicao ANONIMA com o banco: {passaram}"


def test_so_com_o_json_anonimo_nao_passa_nem_com_curinga_largo(
    _anonimo: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    mapa = tmp_path / "acesso_abas.json"
    largo = sorted(acesso.ABAS_VALIDAS - acesso.ABAS_SENSIVEIS)
    mapa.write_text(json.dumps({"*": largo}), encoding="utf-8")
    monkeypatch.setenv("MOTOR_ACESSO_ABAS_PATH", str(mapa))
    monkeypatch.setenv("MOTOR_ACESSO_FAIL_CLOSED", "1")
    monkeypatch.setattr(acesso, "_cache", None)

    passaram = [
        (m, c) for m, c in _rotas_protegidas() if not _negada(c, acesso.motivo_bloqueio(c, None))
    ]
    assert not passaram, f"rotas atendendo requisicao ANONIMA so' com o JSON: {passaram}"


def test_o_curinga_continua_valendo_para_quem_tem_identidade(
    _anonimo: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A correcao fecha o anonimo, e so' ele: quem tem identidade e esta fora do mapa segue
    herdando o curinga -- senao a porta fechada seria a de todo mundo."""
    mapa = tmp_path / "acesso_abas.json"
    mapa.write_text(json.dumps({"*": ["mapa"]}), encoding="utf-8")
    monkeypatch.setenv("MOTOR_ACESSO_ABAS_PATH", str(mapa))
    monkeypatch.setattr(acesso, "_cache", None)
    assert acesso.motivo_bloqueio("/api/uf/SP", "alguem.autenticado") is None
