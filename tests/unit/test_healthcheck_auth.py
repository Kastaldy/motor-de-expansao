"""Sonda `auth` do healthcheck da VPS: o `/api/me` com um cookie de sessão FALSO.

O check existe para o dia em que o `edge` deixa de medir a autenticação: no corte do P19 a raiz
passa a servir o SPA com 200 sempre. Até 24/10/2026 a sonda ia SEM cookie, e o ramo do 503
("banco fora") era inalcançável. Sem token, o `/api/verify` responde 401 antes de abrir conexão
(`sessoes.validar("")` sai com `None`), e banco fora passava como "auth OK". Depois do corte,
banco fora é o piloto BR inteiro fora, e era justamente esse o caso que ninguém acusaria em 5 min.

Os testes travam a cadeia nas duas pontas:
  * o SHELL: a sonda manda o cookie com o nome de PRODUÇÃO (paridade com `acesso.COOKIE_SESSAO`),
    cada código vira o estado certo e o `containers` chama a sonda. A função é a REAL, carregada
    com `source` (sem o `case` final), com `curl`/`docker`/`report` falsos, tudo num processo só;
  * o BACKEND: com o MESMO cookie que o script manda e o banco fora no nível da CONEXÃO (não do
    `validar`, que é justamente o que esconderia o atalho), o `/api/verify` responde 503; com o
    banco de pé e o token desconhecido, 401 e uma consulta feita. SEM cookie, 401 com o banco
    fora e NENHUMA conexão aberta: é a cegueira que motivou a troca, fixada para que ninguém
    "simplifique" a sonda de volta.

Caminhos RELATIVOS ao `cwd` e entrada padrão em DEVNULL, como em `test_healthcheck_banco.py`.
"""

from __future__ import annotations

import contextlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
HEALTHCHECK = ROOT / "scripts" / "healthcheck_vps.sh"
ACESSO = ROOT / "web" / "server" / "acesso.py"

_SERVER = ROOT / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

_PRECISA_BASH = pytest.mark.skipif(
    shutil.which("bash") is None, reason="precisa de bash (Git Bash no Windows)"
)

EDGE = "https://piloto.exemplo.invalid"


def _cookie_da_sonda() -> tuple[str, str]:
    """`(nome, valor)` do cookie que o script manda, lido do PRÓPRIO script."""
    achado = re.search(
        r'^COOKIE_SONDA_AUTH="([^="]+)=([^"]+)"$', HEALTHCHECK.read_text(encoding="utf-8"), re.M
    )
    assert achado is not None, "COOKIE_SONDA_AUTH sumiu do healthcheck (ou mudou de forma)"
    return achado.group(1), achado.group(2)


# --------------------------------------------------------------------------- #
# O shell
# --------------------------------------------------------------------------- #
def _bash(tmp_path: Path, corpo: str) -> str:
    """Carrega o healthcheck REAL sem o `case` final e roda `corpo` no mesmo processo."""
    texto = HEALTHCHECK.read_text(encoding="utf-8")
    corte = texto.index('\ncase "${1:-}" in\n')
    (tmp_path / "biblioteca.sh").write_text(texto[: corte + 1], encoding="utf-8", newline="\n")
    (tmp_path / "env").write_text("", encoding="utf-8")
    ambiente = {k: v for k, v in os.environ.items() if not k.startswith("MONITOR_")}
    ambiente.update(
        {
            "MONITOR_ENV_FILE": "env",
            "MONITOR_STATE_DIR": "estado",
            "MONITOR_LOG_FILE": "log/hc.log",
            "MONITOR_EDGE_URL": EDGE,
        }
    )
    script = (
        "source ./biblioteca.sh\n"
        'report() { printf \'REPORT %s %s | %s\\n\' "$1" "$2" "$3"; }\n'
        "log() { :; }\n" + corpo
    )
    saida = subprocess.run(
        ["bash", "-c", script],
        cwd=tmp_path,
        env=ambiente,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )
    assert saida.returncode == 0, f"o bash saiu com {saida.returncode}: {saida.stderr}"
    return saida.stdout


def _reports(saida: str) -> list[tuple[str, str, str]]:
    linhas = []
    for linha in saida.splitlines():
        if linha.startswith("REPORT "):
            cabeca, _, mensagem = linha[7:].partition(" | ")
            chave, status = cabeca.split()
            linhas.append((chave, status, mensagem))
    return linhas


#: `curl` falso como FUNÇÃO: guarda o argv de cada chamada e devolve o código plantado em
#: `codigo.txt` — o que o real imprime com `-w '%{http_code}'`.
_CURL_FALSO = r"""
curl() { { printf '%s\n' "$@"; echo "--fim--"; } >> curl_argv.log; cat codigo.txt; }
"""


def test_o_nome_do_cookie_da_sonda_e_o_de_PRODUCAO() -> None:
    """Com outro nome, o `/api/verify` volta a ver "sem cookie" e a sonda volta a ser cega.

    O `__Host-` não é enfeite: em produção o nome sem prefixo (`motor_sessao`, só dev) é IGNORADO
    pelo backend (endurecimento de 25/09/2026), então `motor_sessao=` cairia no mesmo atalho do
    token vazio. O prefixo de produção é `__Host-` (a DEC-081 tentou `__Secure-`+`Domain` para o
    SSO de apex+BR+AR, mas a Opção F reverteu por um furo de fixação — o `__Host-` é host-only e
    fecha isso). A sonda acompanha; o nome é lido de `COOKIE_SESSAO` e comparado acima.
    """
    nome, valor = _cookie_da_sonda()
    achado = re.search(r'^COOKIE_SESSAO = "([^"]+)"$', ACESSO.read_text(encoding="utf-8"), re.M)
    assert achado is not None, "COOKIE_SESSAO sumiu de web/server/acesso.py"
    assert nome == achado.group(1), f"a sonda manda {nome!r}, a produção lê {achado.group(1)!r}"
    assert nome.startswith("__Host-")
    assert valor.strip(), "cookie com valor vazio é o mesmo que nenhum cookie"


@_PRECISA_BASH
def test_a_sonda_manda_o_cookie_e_cada_codigo_vira_o_estado_certo(tmp_path: Path) -> None:
    nome, valor = _cookie_da_sonda()
    casos = ("401", "302", "200", "503", "502")
    corpo = _CURL_FALSO + "".join(
        f"printf '%s' {codigo} > codigo.txt; echo 'CASO {codigo}'; check_auth\n" for codigo in casos
    )

    saida = _bash(tmp_path, corpo)

    por_caso: dict[str, tuple[str, str]] = {}
    atual = ""
    for linha in saida.splitlines():
        if linha.startswith("CASO "):
            atual = linha[5:]
        elif linha.startswith("REPORT "):
            ((chave, status, mensagem),) = _reports(linha)
            assert chave == "auth"
            por_caso[atual] = (status, mensagem)
    assert set(por_caso) == set(casos), por_caso

    assert por_caso["401"][0] == "OK"
    assert por_caso["302"][0] == "OK", "antes do corte o Authelia redireciona, e isso é saudável"
    assert por_caso["200"][0] == "FAIL"
    assert "GRAVE" in por_caso["200"][1]
    assert por_caso["503"][0] == "FAIL"
    assert "banco não respondeu" in por_caso["503"][1]
    assert por_caso["502"][0] == "FAIL"
    assert "HTTP 502" in por_caso["502"][1]

    chamadas = [
        bloco.strip().splitlines()
        for bloco in (tmp_path / "curl_argv.log").read_text(encoding="utf-8").split("--fim--")
        if bloco.strip()
    ]
    assert len(chamadas) == len(casos)
    for argv in chamadas:
        assert argv[-1] == f"{EDGE}/api/me"
        i = argv.index("-H")
        assert argv[i + 1] == f"Cookie: {nome}={valor}", argv


@_PRECISA_BASH
def test_o_containers_chama_a_sonda(tmp_path: Path) -> None:
    """A sonda vive em função própria; o que a agenda é o `containers` (cron */5)."""
    nome, _ = _cookie_da_sonda()
    corpo = (
        'docker() { case "$*" in *Health*) echo healthy ;; *) echo running ;; esac; }\n'
        'curl() { case "$*" in\n'
        f"    *{nome}*/api/me) echo 503 ;;\n"
        "    */api/me) echo 401 ;;\n"
        "    *) echo 200 ;;\n"
        "esac; }\n"
        "check_containers\n"
    )

    reports = {chave: (status, msg) for chave, status, msg in _reports(_bash(tmp_path, corpo))}

    assert reports["edge"][0] == "OK"
    assert reports["auth"][0] == "FAIL", (
        "o `containers` não chamou a sonda com o cookie (sem cookie o curl falso dá 401)"
    )
    assert all(
        status == "OK" for chave, (status, _) in reports.items() if chave.startswith("container_")
    )


# --------------------------------------------------------------------------- #
# O backend: o que o `/api/verify` responde ao MESMO cookie
# --------------------------------------------------------------------------- #
class _Url:
    def __init__(self, caminho: str) -> None:
        self.path = caminho


class _Requisicao:
    """O que a rota usa: `.url.path`, `.cookies` e `.scope["headers"]`."""

    def __init__(self, cookies: dict[str, str] | None = None) -> None:
        self.url = _Url("/api/verify")
        self.cookies = cookies or {}
        self.scope: dict[str, Any] = {"headers": []}


class _Conexoes:
    """Dublê de `sessoes.conexao`: conta as aberturas e simula banco fora ou de pé."""

    def __init__(self, *, fora: bool) -> None:
        self.fora = fora
        self.abertas = 0
        self.consultas: list[tuple[Any, ...]] = []

    @contextlib.contextmanager
    def __call__(self):  # noqa: ANN204 — mesma forma de `postgres.conexao`
        self.abertas += 1
        if self.fora:
            raise OSError("connection refused: postgres:5432")
        yield self

    def execute(self, sql: str, parametros: tuple[Any, ...]) -> _Conexoes:
        self.consultas.append(parametros)
        return self

    def fetchall(self) -> list[Any]:
        return []


@pytest.fixture
def _verify(monkeypatch: pytest.MonkeyPatch):  # noqa: ANN202
    """A rota com a autenticação própria LIGADA e em modo de produção."""
    import acesso
    import app as pilot

    from motor_expansao.db import sessoes as db_sessoes

    monkeypatch.setenv(db_sessoes.ENV_AUTENTICACAO_PROPRIA, "1")
    monkeypatch.setattr(acesso, "em_producao", lambda: True)

    def chamar(conexoes: _Conexoes, cookies: dict[str, str] | None) -> Any:
        monkeypatch.setattr(db_sessoes, "conexao", conexoes)
        return pilot.verify(_Requisicao(cookies))

    return chamar, db_sessoes


def test_com_o_cookie_da_sonda_e_o_banco_fora_a_rota_responde_503(_verify) -> None:  # noqa: ANN001
    chamar, _ = _verify
    nome, valor = _cookie_da_sonda()
    conexoes = _Conexoes(fora=True)

    resposta = chamar(conexoes, {nome: valor})

    assert resposta.status_code == 503
    assert conexoes.abertas == 1, "a rota não tentou o banco"


def test_com_o_cookie_da_sonda_e_o_banco_de_pe_a_rota_responde_401_depois_de_consultar(
    _verify,  # noqa: ANN001
) -> None:
    chamar, db_sessoes = _verify
    nome, valor = _cookie_da_sonda()
    conexoes = _Conexoes(fora=False)

    resposta = chamar(conexoes, {nome: valor})

    assert resposta.status_code == 401
    assert [parametros[0] for parametros in conexoes.consultas] == [
        db_sessoes.hash_do_token(valor)
    ], "a consulta não foi pelo token da sonda"


def test_SEM_cookie_a_rota_responde_401_sem_abrir_conexao_mesmo_com_o_banco_fora(
    _verify,  # noqa: ANN001
) -> None:
    """A cegueira da sonda antiga: banco fora e resposta de "tudo certo".

    Se um dia o `validar` deixar de sair cedo com token vazio, este teste fica vermelho — e aí a
    sonda sem cookie voltaria a enxergar o banco. Até lá, o cookie é o que a faz enxergar.
    """
    chamar, _ = _verify
    conexoes = _Conexoes(fora=True)

    resposta = chamar(conexoes, None)

    assert resposta.status_code == 401
    assert conexoes.abertas == 0
