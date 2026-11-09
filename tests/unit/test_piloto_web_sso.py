"""`POST /api/sso/ticket` e `GET /api/sso/entrar` — o SSO por ticket de uso unico (DEC-083).

Funcoes chamadas DIRETO, sem TestClient/httpx (padrao da suite do piloto, como
`test_piloto_web_verify.py`). O que estes testes guardam:

  - **Emissao gateada por pais** (DEC-081): so' emite ticket para pais que a pessoa TEM
    (`pais in identidade.paises`); fail-closed (403) no resto; 401 sem sessao; 422 pais invalido;
    404 com a chave desligada.
  - **Consumo preso ao host**: so' abre sessao se `pais_destino == PERFIL.pais`; ticket
    invalido/usado/expirado (ou para outro host) cai no login, nunca concede em silencio.
  - **`_rd_local_seguro`**: so' caminho local; `//evil`, `http://...`, vazio viram `/`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

_REPO = Path(__file__).resolve().parents[2]
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import acesso  # noqa: E402
import app as pilot  # noqa: E402

from motor_expansao.db import sessoes as db_sessoes  # noqa: E402
from motor_expansao.db import sso_tickets as db_sso  # noqa: E402
from motor_expansao.db.rbac import Identidade  # noqa: E402


class _Url:
    def __init__(self, caminho: str) -> None:
        self.path = caminho


class _Cli:
    def __init__(self, host: str) -> None:
        self.host = host


class _Req:
    """Fake de requisicao: cookies, headers (que a rota de consumo LE, p/ IP/user-agent) e client."""

    def __init__(
        self,
        cookies: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        client_host: str | None = None,
    ) -> None:
        self.cookies = cookies or {}
        self._headers = {k.lower(): v for k, v in (headers or {}).items()}
        self.client = _Cli(client_host) if client_host else None
        self.url = _Url("/api/sso/entrar")

    @property
    def headers(self) -> Any:
        return self._headers


def _sessao(paises: frozenset[str] | None = None, id_sessao: int = 42) -> Any:
    if paises is None:
        paises = frozenset({pilot.PERFIL.pais})
    return db_sessoes.SessaoValida(
        identidade=Identidade(
            id_usuario=7, login="vinicius", perfil="growth", permissoes=frozenset(), paises=paises
        ),
        id_sessao=id_sessao,
        ultimo_acesso=None,
    )


@pytest.fixture
def _ligado(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(db_sessoes.ENV_AUTENTICACAO_PROPRIA, "1")


def _com_cookie() -> _Req:
    # Fora de producao o nome do cookie e' o SEM prefixo (COOKIE_SESSAO_DEV); `_token_de_sessao`
    # so' aceita o alternativo fora de producao, e os testes rodam sem MOTOR_CADASTRO_DIR.
    return _Req(cookies={acesso.COOKIE_SESSAO_DEV: "tok"})


# --- POST /api/sso/ticket ----------------------------------------------------------------


def test_ticket_404_com_a_chave_desligada() -> None:
    # Sem o fixture `_ligado`: `MOTOR_AUTENTICACAO_PROPRIA` ausente -> a porta nao existe.
    with pytest.raises(pilot.HTTPException) as e:
        pilot.sso_ticket(pilot.TicketSSOIn(pais="BR"), _com_cookie())
    assert e.value.status_code == 404


def test_ticket_422_pais_invalido(_ligado: None) -> None:
    for ruim in ("B", "BRA", "12", ""):
        with pytest.raises(pilot.HTTPException) as e:
            pilot.sso_ticket(pilot.TicketSSOIn(pais=ruim), _com_cookie())
        assert e.value.status_code == 422, ruim


def test_ticket_401_sem_sessao(_ligado: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db_sessoes, "validar", lambda _t: None)
    with pytest.raises(pilot.HTTPException) as e:
        pilot.sso_ticket(pilot.TicketSSOIn(pais="BR"), _com_cookie())
    assert e.value.status_code == 401


def test_ticket_403_pais_fora_dos_da_pessoa(
    _ligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A pessoa so' tem BR; pede ticket para AR -> fail-closed.
    monkeypatch.setattr(db_sessoes, "validar", lambda _t: _sessao(paises=frozenset({"BR"})))
    with pytest.raises(pilot.HTTPException) as e:
        pilot.sso_ticket(pilot.TicketSSOIn(pais="AR"), _com_cookie())
    assert e.value.status_code == 403


def test_ticket_200_emite_para_pais_que_a_pessoa_tem(
    _ligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        db_sessoes, "validar", lambda _t: _sessao(paises=frozenset({"BR", "AR"}), id_sessao=88)
    )
    vistos: dict[str, Any] = {}

    def _emitir(*, id_usuario: int, pais_destino: str, id_sessao_origem: int | None = None) -> Any:
        vistos.update(
            id_usuario=id_usuario, pais_destino=pais_destino, id_sessao_origem=id_sessao_origem
        )
        return db_sso.TicketEmitido(token="tok-sso-xyz", id_ticket=1, expira_em=None)

    monkeypatch.setattr(db_sso, "emitir", _emitir)

    resp = pilot.sso_ticket(pilot.TicketSSOIn(pais="AR"), _com_cookie())
    assert resp.status_code == 200
    assert json.loads(resp.body) == {"ticket": "tok-sso-xyz"}
    # emite para o pais pedido, pelo dono da sessao, carimbando a sessao de origem
    assert vistos == {"id_usuario": 7, "pais_destino": "AR", "id_sessao_origem": 88}


# --- GET /api/sso/entrar (passo 1: confirmacao, NAO consome) -----------------------------


def test_entrar_404_com_a_chave_desligada() -> None:
    with pytest.raises(pilot.HTTPException) as e:
        pilot.sso_entrar(_Req(), t="x", rd="/")
    assert e.value.status_code == 404


def test_entrar_ticket_invalido_cai_no_login(
    _ligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(db_sso, "espiar", lambda _t: None)
    resp = pilot.sso_entrar(_Req(), t="qualquer", rd="/mapa")
    assert resp.status_code == 303
    assert "/entrar.html" in resp.headers["location"]


def test_entrar_pais_errado_cai_no_login(
    _ligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    outro = "AR" if pilot.PERFIL.pais != "AR" else "BR"
    monkeypatch.setattr(
        db_sso, "espiar", lambda _t: db_sso.TicketEspiado(login="x", pais_destino=outro)
    )
    resp = pilot.sso_entrar(_Req(), t="tok", rd="/")
    assert resp.status_code == 303
    assert "/entrar.html" in resp.headers["location"]


def test_entrar_get_mostra_confirmacao_sem_consumir(
    _ligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    # O GET NAO consome: espia (mostra DE QUEM e' a conta) e seta o nonce da confirmacao.
    consumos: list[str] = []

    def _spy(t: str) -> None:
        consumos.append(t)

    monkeypatch.setattr(db_sso, "consumir", _spy)
    monkeypatch.setattr(
        db_sso,
        "espiar",
        lambda _t: db_sso.TicketEspiado(login="felipe", pais_destino=pilot.PERFIL.pais),
    )
    resp = pilot.sso_entrar(_Req(), t="tok", rd="/mapa")
    assert resp.status_code == 200
    assert b"felipe" in resp.body  # mostra o login antes de ativar (defesa login-CSRF)
    assert "set-cookie" in resp.headers
    assert pilot._COOKIE_SSO_CONFIRMA_DEV in resp.headers["set-cookie"]
    assert consumos == [], "o GET nao pode gastar o ticket"
    # CLICKJACKING: a pagina NAO pode ser enquadrada (senao a vitima clica sem ver a conta).
    assert resp.headers.get("x-frame-options") == "DENY"
    assert resp.headers.get("content-security-policy") == "frame-ancestors 'none'"


# --- POST /api/sso/entrar (passo 2: consumo confirmado) ----------------------------------


def _spy_consumir(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    consumos: list[str] = []

    def _spy(t: str) -> None:
        consumos.append(t)

    monkeypatch.setattr(db_sso, "consumir", _spy)
    return consumos


def test_post_sem_nonce_nao_consome(_ligado: None, monkeypatch: pytest.MonkeyPatch) -> None:
    # Auto-POST cross-site do atacante: sem o cookie `__Host-` que o GET setou -> rejeitado,
    # e o ticket NAO e' gasto.
    consumos = _spy_consumir(monkeypatch)
    resp = pilot.sso_entrar_confirmar(_Req(), t="tok", rd="/", csrf="qualquer")
    assert resp.status_code == 303
    assert "/entrar.html" in resp.headers["location"]
    assert consumos == []


def test_post_nonce_divergente_nao_consome(
    _ligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    consumos = _spy_consumir(monkeypatch)
    req = _Req(cookies={pilot._COOKIE_SSO_CONFIRMA_DEV: "nonce-A"})
    resp = pilot.sso_entrar_confirmar(req, t="tok", rd="/", csrf="nonce-B")
    assert resp.status_code == 303
    assert "/entrar.html" in resp.headers["location"]
    assert consumos == []


def test_post_confirmado_consome_e_abre_sessao(
    _ligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        db_sso,
        "consumir",
        lambda _t: db_sso.TicketConsumido(id_usuario=7, pais_destino=pilot.PERFIL.pais),
    )
    abriu: dict[str, Any] = {}

    def _abrir(*, id_usuario: int, ip: Any = None, user_agent: Any = None) -> Any:
        abriu.update(id_usuario=id_usuario)
        return db_sessoes.SessaoAberta(token="nova-sessao", id_sessao=1, expira_em=None)

    monkeypatch.setattr(db_sessoes, "abrir", _abrir)
    req = _Req(
        cookies={pilot._COOKIE_SSO_CONFIRMA_DEV: "nonce-ok"},
        headers={"user-agent": "x"},
        client_host="1.2.3.4",
    )
    resp = pilot.sso_entrar_confirmar(req, t="tok", rd="/mapa", csrf="nonce-ok")
    assert resp.status_code == 303
    assert resp.headers["location"] == "/mapa"
    assert resp.headers.get("referrer-policy") == "no-referrer"
    assert "set-cookie" in resp.headers  # abriu sessao LOCAL neste host
    assert abriu == {"id_usuario": 7}


# --- _rd_local_seguro --------------------------------------------------------------------


def test_rd_local_seguro_so_aceita_caminho_local() -> None:
    assert pilot._rd_local_seguro("/") == "/"
    assert pilot._rd_local_seguro("/mapa?uf=SP") == "/mapa?uf=SP"
    # todo controle C0 e' rejeitado (nao so' LF/CR): o tab-stripping do browser viraria
    # `/<TAB>/evil` em `//evil` se o valor vazasse num Location nao-quotado.
    controles = [chr(9), chr(0), chr(11), chr(10), chr(13)]  # tab, nul, vtab, LF, CR
    ruins = ['', '//evil.com', 'http://evil.com', 'https://x', '/a' + chr(92) + 'b']
    ruins += ['/a' + c + 'b' for c in controles]
    for ruim in ruins:
        assert pilot._rd_local_seguro(ruim) == '/', repr(ruim)


def test_redige_o_ticket_na_trilha() -> None:
    # O `?t=` (credencial) e' redigido antes da trilha (retencao longa); o `rd` fica.
    saida = pilot._redigir_ticket_na_trilha('/api/sso/entrar', 't=segredo-xyz&rd=%2Fmapa')
    assert 'segredo-xyz' not in saida
    assert 'redigido' in saida and 'rd=' in saida
    # outras rotas passam intactas; sem `t=` nada muda
    assert pilot._redigir_ticket_na_trilha('/api/uf/SP', 't=x') == 't=x'
    assert pilot._redigir_ticket_na_trilha('/api/sso/entrar', 'rd=%2F') == 'rd=%2F'
