"""Monitor do banco no healthcheck da VPS — o subcomando `banco`, diário.

O `containers` (a cada 5 min) só sabe se o `motor_expansao_postgres` está de pé. O que importa
DEPOIS disso existia apenas como linha de log: o backup e o expurgo saem com `exit 1` e ninguém
lê. Este subcomando fecha o buraco, e estes testes travam o que um `bash -n` não vê:

  * o trio de sempre (função, `case`, string de uso) — o que se atualiza pela metade;
  * os DEFAULTS de caminho têm paridade com os wrappers de cron. A produção aponta outros, por
    env, porque desde 17/10/2026 os dois crons rodam na conta `deploy`;
  * as frases que o monitor procura no log SÃO as que os wrappers escrevem. Os testes montam o
    log falso RECORTANDO o `echo` dos wrappers, nunca reescrevendo a frase aqui — duas redações da
    mesma regra se desencontram em silêncio (a lição da DEC-044);
  * a régua de 26 h pega o dia perdido no próprio dia, com o check às 12:00 UTC;
  * a EXECUÇÃO, em duas camadas:
      - de ponta a ponta, o subcomando inteiro com árvore falsa, `docker`/`curl` falsos e um
        "container" de mentira que roda o `sh -c` do monitor DE VERDADE: estado por chave,
        mensagens do Telegram e nenhum segredo plantado (no `.env`, no ambiente do host ou no do
        container) aparecendo na saída, no log, no Telegram ou no argv do host;
      - as MATRIZES de casos (dump, log do backup, expurgo, medição) chamando as funções do
        script REAL — carregado com `source`, sem o `case` final — com `report`/`log` capturados,
        todos os casos de uma matriz num processo só. No Windows cada `fork` do MSYS custa caro e
        spawn repetido é onde esta estação fica instável; uma rodada inteira por caso levava 100 s.

Os testes que executam o shell rodam com caminhos RELATIVOS ao `cwd` (lição de
`test_wrapper_cron_weekly_90`): caminho absoluto do Windows interpolado no Git Bash dá um verde
que não prova nada. E não redirecionam a entrada do pytest para `/dev/null`: no Git Bash isso
quebra todo `subprocess` com `WinError 6`.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HEALTHCHECK = ROOT / "scripts" / "healthcheck_vps.sh"
BACKUP = ROOT / "scripts" / "cron" / "run_backup_banco.sh"
EXPURGO = ROOT / "scripts" / "cron" / "run_expurgo_sessoes.sh"

# Segredos PLANTADOS. Nenhum pode aparecer em nada que o monitor produza.
SEGREDO_ENV_DONO = "SEGREDO-dono-no-env-7f3a"
SEGREDO_ENV_RESTIC = "SEGREDO-restic-no-env-91c2"
SEGREDO_ENV_URL = "SEGREDO-url-no-env-55d0"
TOKEN_TELEGRAM = "SEGREDO-token-telegram-a1b2"
#: `POSTGRES_PASSWORD` no ambiente do HOST: se o monitor expandisse `$POSTGRES_*` do lado de fora,
#: é este valor que iria parar no argv do docker e no psql.
SEGREDO_HOST = "SEGREDO-pg-no-host-0b8e"
#: A senha DENTRO do container falso. Lida de arquivo pelo docker falso — o processo do monitor
#: nunca a tem no ambiente —, e o único lugar legítimo dela é o `PGPASSWORD` do psql.
SEGREDO_CONTAINER = "SEGREDO-senha-do-container-c4d1"

SEGREDOS_PROIBIDOS = (
    SEGREDO_ENV_DONO,
    SEGREDO_ENV_RESTIC,
    SEGREDO_ENV_URL,
    TOKEN_TELEGRAM,
    SEGREDO_HOST,
    SEGREDO_CONTAINER,
)

#: Todas as chaves de estado do subcomando.
CHAVES = (
    "banco_dump",
    "banco_semanal",
    "banco_backup",
    "banco_offbox",
    "banco_expurgo",
    "banco_medicao",
    "banco_tamanho",
    "banco_conexoes",
    "banco_transacoes",
    "banco_locks",
)

#: Saída SAUDÁVEL do psql: bytes, conexões, max_connections, ociosas em transação, idade da mais
#: antiga (s), esperando lock, idade da mais antiga (s).
PSQL_SAUDAVEL = "8388608 3 100 0 0 0 0"

_PRECISA_BASH = pytest.mark.skipif(
    shutil.which("bash") is None, reason="precisa de bash (Git Bash no Windows)"
)


# --------------------------------------------------------------------------- #
# Leitura dos scripts
# --------------------------------------------------------------------------- #
def _texto(caminho: Path) -> str:
    return caminho.read_text(encoding="utf-8")


def _linhas_executaveis(caminho: Path) -> list[str]:
    """O script sem as linhas de comentário — o que se mede é sempre o que EXECUTA."""
    return [linha for linha in _texto(caminho).splitlines() if not linha.lstrip().startswith("#")]


def _secao_banco() -> str:
    """O trecho EXECUTÁVEL das funções do `banco` (do 1º helper até o `case`)."""
    executavel = "\n".join(_linhas_executaveis(HEALTHCHECK))
    i = executavel.index("ultima_execucao() {")
    j = executavel.index('case "${1:-}" in', i)
    return executavel[i:j]


def _default(caminho: Path, variavel: str) -> str:
    """O default `${ENV:-valor}` atribuído a `variavel` num script."""
    achado = re.search(rf'^{variavel}="\$\{{[A-Z_]+:-([^}}]*)\}}"', _texto(caminho), re.MULTILINE)
    assert achado is not None, f"{variavel} sem default em {caminho.name}"
    return achado.group(1)


def _constante(variavel: str) -> str:
    """O valor literal de uma constante `VAR="..."` do healthcheck."""
    achado = re.search(rf'^{variavel}="([^"$]*)"$', _texto(HEALTHCHECK), re.MULTILINE)
    assert achado is not None, f"{variavel} sumiu do healthcheck"
    return achado.group(1)


def _eco(wrapper: Path, trecho: str, quando: datetime, *, simular: str = "") -> str:
    """A linha que o wrapper ESCREVE no log, recortada do `echo` dele — nunca uma cópia."""
    achados = re.findall(r'echo "([^"]*' + re.escape(trecho) + r'[^"]*)"', _texto(wrapper))
    assert len(achados) == 1, f"{trecho!r}: {len(achados)} `echo` em {wrapper.name}, esperado 1"
    return (
        achados[0]
        .replace("$(date -u +%FT%TZ)", quando.strftime("%Y-%m-%dT%H:%M:%SZ"))
        .replace("${SIMULAR}", simular)
        .replace("${CONTAINER}", "motor_expansao_postgres")
        .replace("${CONTAINER_PG}", "motor_expansao_postgres")
    )


def _ha(horas: float) -> datetime:
    return datetime.now(UTC) - timedelta(hours=horas)


def _envelhecer(caminho: Path, horas: float) -> None:
    antigo = time.time() - horas * 3600
    os.utime(caminho, (antigo, antigo))


# --------------------------------------------------------------------------- #
# A VPS falsa
# --------------------------------------------------------------------------- #
_DOCKER_FALSO = r"""#!/usr/bin/env bash
# docker FALSO. Registra o argv do HOST e, para `exec`, roda o comando como se fosse DENTRO de um
# container: com o ambiente dele (POSTGRES_*, a senha lida de ARQUIVO — o host nunca a vê) e um
# `psql` falso no PATH. Assim o `sh -c` do monitor roda de verdade.
{ printf '%s\n' "$@"; echo "--fim-da-chamada--"; } >> docker_argv.log
[ "${1:-}" = exec ] || exit 0
shift
if [ -f docker_falha ]; then
    echo "Error response from daemon: container is not running" >&2
    exit 1
fi
# Daemon que não responde: a resposta (boa) só sai depois de 5 s, e o `timeout` do monitor tem de
# cortar antes. Sem ele, o cron do root ficaria pendurado e, aqui, a medição sairia verde.
[ -f docker_pendura ] && sleep 5
# Como o real, só repassa a entrada padrão com `-i`: sem a flag, o processo do container lê EOF, e
# o SQL do monitor (que entra pela entrada padrão) nunca chega ao psql.
interativo=0
while [ "${1#-}" != "$1" ]; do
    [ "$1" = -i ] && interativo=1
    shift
done
[ "$interativo" = 1 ] || exec </dev/null
echo "$1" > docker_container.log
shift
exec env POSTGRES_USER=usuario-do-container POSTGRES_DB=banco-do-container \
    POSTGRES_PASSWORD="$(cat container_senha.txt)" PATH="$PWD/container_bin:$PATH" "$@"
"""

_PSQL_FALSO = r"""#!/usr/bin/env bash
# psql FALSO, "dentro" do container: registra argv, PGPASSWORD e o SQL, e devolve a saída plantada
# SÓ se a consulta chegou — como o real, que com a entrada padrão vazia não executa nem imprime nada.
printf '%s\n' "$@" > psql_argv.log
printf '%s' "${PGPASSWORD:-}" > psql_pgpassword.log
cat > psql_stdin.log
if grep -q pg_database_size psql_stdin.log; then cat psql_saida.txt; fi
"""

_CURL_FALSO = r"""#!/usr/bin/env bash
# curl FALSO: só registra o TEXTO que iria ao Telegram (a URL, que leva o token, não é gravada).
for a in "$@"; do
    case "$a" in text=*) printf '%s\n' "${a#text=}" >> telegram.log ;; esac
done
exit 0
"""

#: Substitutos de `report` e `log` para as matrizes: imprimem em vez de mandar ao Telegram.
_CAPTURA = r"""
report() { printf 'REPORT %s %s | %s\n' "$1" "$2" "$3"; }
log() { printf 'LOG %s\n' "$*"; }
"""


@dataclass
class Rodada:
    estados: dict[str, str]
    log: str
    telegram: list[str]
    stdout: str
    stderr: str
    docker_argv: str
    psql_argv: list[str]
    psql_senha: str
    psql_sql: str
    container: str

    def tudo_que_o_monitor_produziu(self) -> str:
        """O que sai do monitor para fora do container: saída, log, Telegram e argv do host."""
        return "\n".join([self.stdout, self.stderr, self.log, *self.telegram, self.docker_argv])


@dataclass
class Caso:
    """O que uma chamada de função registrou: `report` por chave e as linhas de `log`."""

    reports: dict[str, tuple[str, str]] = field(default_factory=dict)
    logs: list[str] = field(default_factory=list)

    def status(self, chave: str) -> str | None:
        return self.reports[chave][0] if chave in self.reports else None

    def mensagem(self, chave: str) -> str:
        return self.reports[chave][1]


class VpsFalsa:
    """Árvore no molde da produção: dumps e logs na conta `deploy`, estado e log do monitor."""

    def __init__(self, base: Path) -> None:
        self.base = base
        for nome, corpo in (
            ("bin/docker", _DOCKER_FALSO),
            ("bin/curl", _CURL_FALSO),
            ("container_bin/psql", _PSQL_FALSO),
        ):
            alvo = base / nome
            alvo.parent.mkdir(parents=True, exist_ok=True)
            alvo.write_text(corpo, encoding="utf-8", newline="\n")
            os.chmod(alvo, 0o755)
        shutil.copy(HEALTHCHECK, base / "healthcheck_vps.sh")
        texto = _texto(HEALTHCHECK)
        corte = texto.index('\ncase "${1:-}" in\n')
        (base / "biblioteca.sh").write_text(texto[: corte + 1], encoding="utf-8", newline="\n")
        (base / "env").write_text(
            f"API_TELEGRAM_TOKEN={TOKEN_TELEGRAM}\n"
            "MONITOR_TELEGRAM_CHAT_ID=-100123\n"
            f"POSTGRES_OWNER_PASSWORD={SEGREDO_ENV_DONO}\n"
            f"BACKUP_RESTIC_PASSWORD={SEGREDO_ENV_RESTIC}\n"
            f"MOTOR_DATABASE_URL=postgresql://app:{SEGREDO_ENV_URL}@postgres:5432/banco_de_reservas\n",
            encoding="utf-8",
            newline="\n",
        )
        (base / "container_senha.txt").write_text(SEGREDO_CONTAINER, encoding="utf-8")
        self.psql(PSQL_SAUDAVEL)
        (base / "deploy" / "logs").mkdir(parents=True, exist_ok=True)

    # -- entradas --------------------------------------------------------------------------
    def psql(self, saida: str) -> None:
        (self.base / "psql_saida.txt").write_text(saida + "\n", encoding="utf-8", newline="\n")

    def dump(
        self,
        pasta: str,
        horas: float,
        *,
        corpo: bytes = b"PGDMP\x01\x0e\x00" + b"dados" * 40,
        checksum: str = "ok",
        nome: str | None = None,
        raiz: str = "deploy/backups/banco",
    ) -> Path:
        """Um dump como o `run_backup_banco.sh` grava: carimbo UTC no nome + sidecar `.sha256`."""
        nome = nome or f"banco_de_reservas_{_ha(horas):%Y%m%dT%H%M%SZ}.dump"
        destino = self.base / raiz / pasta
        destino.mkdir(parents=True, exist_ok=True)
        arquivo = destino / nome
        arquivo.write_bytes(corpo)
        hash_gravado = {"ok": hashlib.sha256(corpo).hexdigest(), "errado": "0" * 64}.get(checksum)
        if hash_gravado is not None:
            (destino / f"{nome}.sha256").write_text(
                f"{hash_gravado}  {nome}\n", encoding="utf-8", newline="\n"
            )
        return arquivo

    def escrever(self, relativo: str, *linhas: str) -> Path:
        caminho = self.base / relativo
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(
            "".join(f"{linha}\n" for linha in linhas), encoding="utf-8", newline="\n"
        )
        return caminho

    def log_backup(self, *linhas: str) -> None:
        self.escrever("deploy/logs/backup_banco.log", *linhas)

    def log_expurgo(self, *linhas: str) -> None:
        self.escrever("deploy/logs/expurgo_sessoes.log", *linhas)

    # -- cenários prontos --------------------------------------------------------------------
    @staticmethod
    def linhas_backup_ok(horas: float = 6.8, *, offbox: bool = True) -> list[str]:
        meio = (
            ["no errors were found"]
            if offbox
            else [
                _eco(BACKUP, "copia off-box DESLIGADA", _ha(horas)),
                _eco(BACKUP, "O backup existe apenas no MESMO disco", _ha(horas)),
            ]
        )
        fim = "fim (local + off-box)" if offbox else "fim (somente local)"
        return [
            _eco(BACKUP, "backup do banco - inicio", _ha(horas)),
            "   dump: banco_de_reservas_x.dump (1234 bytes)",
            *meio,
            _eco(BACKUP, fim, _ha(horas - 0.01)),
        ]

    @staticmethod
    def linhas_expurgo_ok(horas: float = 7.3, *, simular: str = "") -> list[str]:
        return [
            _eco(EXPURGO, "expurgo da origem das sessoes - inicio", _ha(horas), simular=simular),
            "retencao da origem: 90 dias",
            "sessoes com origem alem do prazo: 0",
            "nada a expurgar",
            _eco(EXPURGO, "expurgo da origem das sessoes - fim", _ha(horas - 0.01)),
        ]

    def saudavel(self) -> VpsFalsa:
        self.dump("diario", 6.8)
        self.dump("semanal", 54)
        self.log_backup(*self.linhas_backup_ok())
        self.log_expurgo(*self.linhas_expurgo_ok())
        return self

    # -- execução ----------------------------------------------------------------------------
    def _bash(self, script: str, extra: dict[str, str]) -> subprocess.CompletedProcess[str]:
        ambiente = {k: v for k, v in os.environ.items() if not k.startswith("MONITOR_")}
        ambiente.update(
            {
                "MONITOR_ENV_FILE": "env",
                "MONITOR_STATE_DIR": "estado",
                "MONITOR_LOG_FILE": "log/hc.log",
                "MONITOR_BANCO_BACKUP_DIR": "deploy/backups/banco",
                "MONITOR_BANCO_BACKUP_LOG": "deploy/logs/backup_banco.log",
                "MONITOR_BANCO_EXPURGO_LOG": "deploy/logs/expurgo_sessoes.log",
                "POSTGRES_PASSWORD": SEGREDO_HOST,
                "POSTGRES_USER": "usuario-do-HOST",
                "POSTGRES_DB": "banco-do-HOST",
                **extra,
            }
        )
        for nome in (
            "telegram.log",
            "docker_argv.log",
            "docker_container.log",
            "psql_argv.log",
            "psql_pgpassword.log",
            "psql_stdin.log",
        ):
            (self.base / nome).unlink(missing_ok=True)
        saida = subprocess.run(
            ["bash", "-c", 'PATH="$PWD/bin:$PATH"\n' + script],
            cwd=self.base,
            env=ambiente,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=180,
            check=False,
        )
        assert saida.returncode == 0, f"o bash saiu com {saida.returncode}: {saida.stderr}"
        return saida

    def ler(self, nome: str) -> str:
        caminho = self.base / nome
        return caminho.read_text(encoding="utf-8") if caminho.exists() else ""

    def rodar(self, **extra: str) -> Rodada:
        """O subcomando INTEIRO, como o cron do root o chama."""
        saida = self._bash("bash ./healthcheck_vps.sh banco", extra)
        return Rodada(
            estados={
                p.stem: p.read_text(encoding="utf-8").split()[0]
                for p in (self.base / "estado").glob("*.state")
            },
            log=self.ler("log/hc.log"),
            telegram=[linha for linha in self.ler("telegram.log").splitlines() if linha],
            stdout=saida.stdout,
            stderr=saida.stderr,
            docker_argv=self.ler("docker_argv.log"),
            psql_argv=self.ler("psql_argv.log").splitlines(),
            psql_senha=self.ler("psql_pgpassword.log"),
            psql_sql=self.ler("psql_stdin.log"),
            container=self.ler("docker_container.log").strip(),
        )

    def funcoes(self, corpo: str, **extra: str) -> dict[str, Caso]:
        """Carrega o script REAL sem o `case` e roda `corpo`; `echo "CASO x"` separa os casos."""
        saida = self._bash("source ./biblioteca.sh\n" + _CAPTURA + corpo, extra)
        produzido = saida.stdout + saida.stderr + self.ler("docker_argv.log")
        for segredo in SEGREDOS_PROIBIDOS:
            assert segredo not in produzido, f"o segredo {segredo!r} vazou"
        casos: dict[str, Caso] = {}
        atual = Caso()
        for linha in saida.stdout.splitlines():
            if linha.startswith("CASO "):
                atual = casos.setdefault(linha[5:], Caso())
            elif linha.startswith("REPORT "):
                cabeca, _, mensagem = linha[7:].partition(" | ")
                chave, status = cabeca.split()
                atual.reports[chave] = (status, mensagem)
            elif linha.startswith("LOG "):
                atual.logs.append(linha[4:])
        assert saida.stderr == "", saida.stderr
        return casos


@pytest.fixture
def vps(tmp_path: Path) -> VpsFalsa:
    return VpsFalsa(tmp_path)


def _sem_segredo(rodada: Rodada) -> None:
    produzido = rodada.tudo_que_o_monitor_produziu()
    for segredo in SEGREDOS_PROIBIDOS:
        assert segredo not in produzido, f"o segredo {segredo!r} vazou para a saída do monitor"
    # Do lado de DENTRO, o psql não pode receber a senha pelo argv (visível em `ps`).
    assert all(SEGREDO_CONTAINER not in arg for arg in rodada.psql_argv)


# --------------------------------------------------------------------------- #
# Contrato textual
# --------------------------------------------------------------------------- #
def test_healthcheck_expoe_subcomando_banco() -> None:
    """Função + `case` + string de uso: o trio que costuma ser atualizado pela metade."""
    texto = _texto(HEALTHCHECK)
    assert "check_banco()" in texto, "a função do subcomando não existe"
    assert "banco) check_banco ;;" in texto, "o `case` não roteia o subcomando"
    assert "|banco|" in texto, "a string de uso não lista o subcomando"


def test_arquivo_continua_em_LF() -> None:
    """Em BYTES: `read_text` traduz CRLF na leitura e cegaria a guarda. CRLF quebra o shebang."""
    assert b"\r" not in HEALTHCHECK.read_bytes()


@pytest.mark.parametrize(
    ("variavel_monitor", "wrapper", "variavel_wrapper"),
    [
        ("BANCO_BACKUP_DIR", BACKUP, "DEST_DIR"),
        ("BANCO_BACKUP_LOG", BACKUP, "LOG_CRON"),
        ("BANCO_EXPURGO_LOG", EXPURGO, "LOG_CRON"),
        ("BANCO_CONTAINER", BACKUP, "CONTAINER"),
        ("BANCO_CONTAINER", EXPURGO, "CONTAINER_PG"),
    ],
)
def test_defaults_tem_paridade_com_os_wrappers(
    variavel_monitor: str, wrapper: Path, variavel_wrapper: str
) -> None:
    """O default do monitor é o caminho do runbook — o mesmo que o wrapper usa sem env.

    A produção NÃO usa esses caminhos (os crons rodam na conta `deploy`) e os aponta por env no
    crontab do root. Mas quem instalar pelo runbook tem de ver o monitor achar o backup sem
    configurar nada: default divergente seria FAIL eterno numa instalação correta.
    """
    assert _default(HEALTHCHECK, variavel_monitor) == _default(wrapper, variavel_wrapper)


def test_caminhos_e_limiares_saem_por_env() -> None:
    """Limiar e caminho são de OPERAÇÃO, não de código: o root os ajusta no crontab."""
    texto = _texto(HEALTHCHECK)
    for variavel in (
        "MONITOR_BANCO_BACKUP_DIR",
        "MONITOR_BANCO_BACKUP_LOG",
        "MONITOR_BANCO_EXPURGO_LOG",
        "MONITOR_BANCO_CONTAINER",
        "MONITOR_BANCO_SEMANAL_MAX_DIAS",
        "MONITOR_BANCO_EXPURGO_MAX_HORAS",
        "MONITOR_BANCO_EM_ANDAMENTO_MIN",
        "MONITOR_BANCO_TAMANHO_MAX_MB",
        "MONITOR_BANCO_CONEXOES_PCT_MAX",
        "MONITOR_BANCO_OCIOSA_MAX_MIN",
        "MONITOR_BANCO_LOCK_MAX_MIN",
        "MONITOR_BANCO_TIMEOUT_S",
        "MONITOR_AVISO_REMIND_SECS",
    ):
        assert f"${{{variavel}:-" in texto, f"{variavel} não é configurável"
    assert 'BANCO_DUMP_MAX_HORAS="${MONITOR_BANCO_DUMP_MAX_HORAS:-26}"' in texto


@pytest.mark.parametrize(
    ("constante", "wrapper"),
    [
        ("BANCO_BACKUP_INICIO", BACKUP),
        ("BANCO_BACKUP_FIM", BACKUP),
        ("BANCO_OFFBOX_DESLIGADA", BACKUP),
        ("BANCO_SO_LOCAL", BACKUP),
        ("BANCO_EXPURGO_INICIO", EXPURGO),
        ("BANCO_EXPURGO_FIM", EXPURGO),
    ],
)
def test_frases_procuradas_sao_as_que_os_wrappers_escrevem(constante: str, wrapper: Path) -> None:
    """Se um wrapper mudar a frase, o monitor perde a execução — este teste avisa antes da VPS."""
    frase = _constante(constante)
    ecos = [linha for linha in _linhas_executaveis(wrapper) if "echo " in linha]
    assert any(frase in linha for linha in ecos), f"{frase!r} não é escrita por {wrapper.name}"


def _horario_documentado(texto: str, script: str) -> int:
    """Minuto do dia da linha de crontab que um cabeçalho documenta para `script`."""
    achado = re.search(rf"^#.*?'?(\d+) (\d+) \* \* \* [^\n]*{re.escape(script)}", texto, re.M)
    assert achado is not None, f"nenhuma linha de crontab de {script}"
    return int(achado.group(2)) * 60 + int(achado.group(1))


def test_limiar_de_26h_pega_o_dia_perdido_no_proprio_dia() -> None:
    """Com o check às 12:00 UTC, o dump do dia tem ~7 h e um dia perdido deixa o anterior com ~31 h.

    A régua só separa os dois enquanto o check rodar mais de `limiar - 24` h depois do cron: com
    o check logo depois das 05:10, o dia perdido só apareceria no check do dia seguinte.
    """
    texto = _texto(HEALTHCHECK)
    check = _horario_documentado(texto, "healthcheck_vps.sh banco")
    for wrapper, script, variavel in (
        (BACKUP, "run_backup_banco.sh", "BANCO_DUMP_MAX_HORAS"),
        (EXPURGO, "run_expurgo_sessoes.sh", "BANCO_EXPURGO_MAX_HORAS"),
    ):
        cron = _horario_documentado(_texto(wrapper), script)
        limiar_min = int(_default(HEALTHCHECK, variavel)) * 60
        idade_no_dia = check - cron
        idade_com_um_dia_perdido = idade_no_dia + 24 * 60
        assert 0 < idade_no_dia <= limiar_min, f"{script}: o check acusaria o dia que rodou"
        assert idade_com_um_dia_perdido > limiar_min, f"{script}: o dia perdido passaria batido"


def test_credenciais_expandem_DENTRO_do_container() -> None:
    """`sh -c` entre aspas SIMPLES: `$POSTGRES_*` chega literal ao container.

    Com aspas duplas, o host expandiria as variáveis DELE (vazias, ou pior, outras) e a senha
    passaria pelo argv do `docker`, legível em `ps` por qualquer usuário da máquina.
    """
    secao = _secao_banco()
    # A aspa simples ABRINDO o argumento do `sh -c` é o que importa.
    assert '\'PGPASSWORD="$POSTGRES_PASSWORD" PGCONNECT_TIMEOUT=10 exec psql' in secao
    assert '-U "$POSTGRES_USER" -d "$POSTGRES_DB"' in secao
    assert "-e PGPASSWORD" not in secao, "a senha não deve viajar do host"


@pytest.mark.parametrize(
    "proibido", ["docker inspect", "printenv", ".Config.Env", "env |", "set |"]
)
def test_monitor_do_banco_nunca_despeja_ambiente(proibido: str) -> None:
    """Incidente de 17/10/2026: um filtro de `docker inspect` mal feito imprimiu segredo de env."""
    assert proibido not in _secao_banco()


def test_monitor_do_banco_nao_le_o_env_do_banco() -> None:
    """O único segredo que o healthcheck toca é o token do bot; senha do banco fica no container."""
    secao = _secao_banco()
    assert "get_env_var" not in secao
    assert "POSTGRES_OWNER_PASSWORD" not in secao


# --------------------------------------------------------------------------- #
# De ponta a ponta: o subcomando inteiro
# --------------------------------------------------------------------------- #
@_PRECISA_BASH
def test_tudo_saudavel_fica_verde_em_silencio(vps: VpsFalsa) -> None:
    rodada = vps.saudavel().rodar()

    assert rodada.estados == dict.fromkeys(CHAVES, "OK"), rodada.log
    assert rodada.telegram == [], "verde não manda mensagem"
    assert rodada.stdout == "" and rodada.stderr == ""
    # O default do container é o da produção, e as credenciais vieram do container.
    assert rodada.container == "motor_expansao_postgres"
    assert rodada.psql_senha == SEGREDO_CONTAINER, "a senha não chegou ao psql pelo ambiente"
    assert rodada.psql_argv[-4:] == ["-U", "usuario-do-container", "-d", "banco-do-container"]
    assert "$POSTGRES_PASSWORD" in rodada.docker_argv, "o host expandiu as variáveis do container"
    assert "pg_database_size" in rodada.psql_sql and "idle in transaction" in rodada.psql_sql
    # As flags que fazem o psql devolver UMA linha só de números. Sem `-q` sai a etiqueta `SET`,
    # sem `-t` sai cabeçalho, sem `-A -F " "` sai tabela alinhada e sem `-X` vale o `.psqlrc` do
    # container: qualquer uma faltando deixa o monitor cego PARA SEMPRE na VPS. O psql falso daqui
    # não formata nada, então a guarda é sobre o argv que ele recebeu.
    assert {"-X", "-q", "-A", "-t"} <= set(rodada.psql_argv), rodada.psql_argv
    assert rodada.psql_argv[rodada.psql_argv.index("-F") + 1] == " ", rodada.psql_argv
    assert rodada.psql_argv[rodada.psql_argv.index("-v") + 1] == "ON_ERROR_STOP=1"
    assert "banco: medido (8 MB; conexões 3/100" in rodada.log
    _sem_segredo(rodada)


@_PRECISA_BASH
def test_tudo_quebrado_acusa_cada_aspecto_na_propria_chave(vps: VpsFalsa) -> None:
    """Cada defeito na sua chave: um não silencia o outro (molde dos agregadores)."""
    vps.dump("diario", 3, checksum="errado")
    vps.log_backup(
        _eco(BACKUP, "backup do banco - inicio", _ha(5)),
        _eco(BACKUP, "nao esta de pe", _ha(5)),
    )
    # A execução REAL falhou; a simulação manual depois dela não pode mascarar isso.
    vps.log_expurgo(
        _eco(EXPURGO, "expurgo da origem das sessoes - inicio", _ha(6)),
        "psycopg.OperationalError: connection failed",
        *vps.linhas_expurgo_ok(1, simular="--simular"),
    )
    vps.psql(f"{6 * 1024**3} 90 100 2 3600 1 900")

    rodada = vps.rodar()

    falhas = {k for k, v in rodada.estados.items() if v == "FAIL"}
    assert falhas == set(CHAVES) - {"banco_offbox", "banco_medicao"}, rodada.log
    assert rodada.estados["banco_medicao"] == "OK"
    assert "banco_offbox" not in rodada.estados, "off-box de execução que morreu é desconhecido"
    assert len(rodada.telegram) == 8 and all(m.startswith("🔴 ") for m in rodada.telegram)
    mensagens = "\n".join(rodada.telegram)
    assert "CORROMPIDO" in mensagens
    assert "NENHUMA cópia semanal" in mensagens
    assert "nao esta de pe" in mensagens, "o motivo escrito pelo wrapper não chegou ao alerta"
    assert "A última execução do expurgo das sessões" in mensagens
    assert "6144 MB" in mensagens and "90 conexões" in mensagens
    assert "idle in transaction) há 60 min" in mensagens
    assert "esperando lock, a mais antiga há 15 min" in mensagens
    _sem_segredo(rodada)


@_PRECISA_BASH
def test_limiares_e_container_saem_do_ambiente_do_cron(vps: VpsFalsa) -> None:
    """Os `MONITOR_BANCO_*` da linha do crontab chegam ÀS RÉGUAS, e não só existem no texto.

    Cada limiar vai ao ambiente com um valor que INVERTE o veredito do padrão, então uma régua que
    lesse um número fixo ou a variável errada erraria aqui — e o
    `test_caminhos_e_limiares_saem_por_env`, que só lê o texto do script, não veria. O dump e o
    expurgo valem os mesmos 26 h por padrão e andam lado a lado no código: por isso vão em direções
    OPOSTAS (o dump de 30 h fica verde com o limiar frouxo; o expurgo de 7 h falha com o apertado),
    e um lido no lugar do outro troca os dois vereditos.
    """
    vps.dump("diario", 30)
    vps.dump("semanal", 54)
    # Execução sem a linha de fim, de 9 min: em andamento pelo padrão (60), falha com o limiar de 1.
    vps.log_backup(_eco(BACKUP, "backup do banco - inicio", _ha(0.15)))
    vps.log_expurgo(*vps.linhas_expurgo_ok())
    vps.psql("8388608 3 100 1 61 1 61")

    rodada = vps.rodar(
        MONITOR_BANCO_DUMP_MAX_HORAS="48",
        MONITOR_BANCO_SEMANAL_MAX_DIAS="1",
        MONITOR_BANCO_EXPURGO_MAX_HORAS="1",
        MONITOR_BANCO_EM_ANDAMENTO_MIN="1",
        MONITOR_BANCO_TAMANHO_MAX_MB="1",
        MONITOR_BANCO_CONEXOES_PCT_MAX="3",
        MONITOR_BANCO_OCIOSA_MAX_MIN="1",
        MONITOR_BANCO_LOCK_MAX_MIN="1",
        MONITOR_BANCO_CONTAINER="outro_postgres",
    )

    esperado = dict.fromkeys(set(CHAVES) - {"banco_offbox"}, "FAIL") | {
        "banco_dump": "OK",
        "banco_medicao": "OK",
    }
    assert rodada.estados == esperado, rodada.log
    assert rodada.container == "outro_postgres"
    assert "30 h pela régua carimbo" in rodada.log
    mensagens = "\n".join(rodada.telegram)
    assert "Expurgo das sessões sem rodar há 7 h (limiar 1 h" in mensagens
    _sem_segredo(rodada)


@_PRECISA_BASH
def test_ciclo_completo_do_aviso_e_da_falha(vps: VpsFalsa) -> None:
    """A máquina de estados do `report`, nos DOIS níveis, em cinco rodadas.

    1. off-box desligada + dump corrompido -> 🟡 e 🔴, uma vez cada;
    2. de novo, logo em seguida -> nada (o lembrete do FAIL é de 1 h; o do AVISO, de 7 dias);
    3. as duas chaves "envelhecem" 2 h -> lembrete 🔴, e só ele. A cadência do FAIL é a de TODO o
       script (containers, borda, auth...) e o `report` passou a escolhê-la junto com a do AVISO:
       um FAIL lendo a cadência do AVISO, ou o contrário, só aparece nesta rodada;
    4. o AVISO "envelhece" 8 dias -> lembrete 🟡, e só ele;
    5. off-box ligada e dump bom -> 🟢 para os dois.
    """
    vps.saudavel()
    vps.log_backup(*vps.linhas_backup_ok(offbox=False))
    corrompido = vps.dump("diario", 1, checksum="errado")

    primeira = vps.rodar()
    assert primeira.estados["banco_offbox"] == "AVISO"
    assert primeira.estados["banco_dump"] == "FAIL"
    assert len(primeira.telegram) == 2
    assert any(m.startswith("🟡 [VPS Ultra] Backup do banco SÓ LOCAL") for m in primeira.telegram)
    assert any(
        m.startswith("🔴 [VPS Ultra] Backup do banco INUTILIZÁVEL") for m in primeira.telegram
    )

    segunda = vps.rodar()
    assert segunda.telegram == [], "sem transição e sem lembrete vencido não sai mensagem"
    assert segunda.estados["banco_offbox"] == "AVISO"

    duas_horas_atras = int(time.time()) - 2 * 3600
    for chave, status in (("banco_dump", "FAIL"), ("banco_offbox", "AVISO")):
        (vps.base / "estado" / f"{chave}.state").write_text(
            f"{status} {duas_horas_atras}\n", encoding="utf-8", newline="\n"
        )
    terceira = vps.rodar()
    assert len(terceira.telegram) == 1, terceira.telegram
    assert terceira.telegram[0].startswith(
        "🔴 [VPS Ultra] (ainda em falha) Backup do banco INUTILIZÁVEL"
    )

    estado = vps.base / "estado" / "banco_offbox.state"
    estado.write_text(f"AVISO {int(time.time()) - 8 * 86400}\n", encoding="utf-8", newline="\n")
    quarta = vps.rodar()
    assert len(quarta.telegram) == 1
    assert quarta.telegram[0].startswith("🟡 [VPS Ultra] (lembrete) Backup do banco SÓ LOCAL")

    vps.log_backup(*vps.linhas_backup_ok(offbox=True))
    corrompido.unlink()
    corrompido.with_name(f"{corrompido.name}.sha256").unlink()
    quinta = vps.rodar()
    assert quinta.estados["banco_offbox"] == "OK" and quinta.estados["banco_dump"] == "OK"
    assert sorted(quinta.telegram) == [
        "🟢 [VPS Ultra] Recuperado: banco_dump",
        "🟢 [VPS Ultra] Recuperado: banco_offbox",
    ]
    for rodada in (primeira, segunda, terceira, quarta, quinta):
        _sem_segredo(rodada)


# --------------------------------------------------------------------------- #
# Matrizes: as funções do script real, todos os casos num processo só
# --------------------------------------------------------------------------- #
#: Um dump bom para a cópia semanal, nos casos que não são sobre ela.
_SEMANAL_BOA = 54


@_PRECISA_BASH
def test_matriz_do_dump_diario_e_da_copia_semanal(vps: VpsFalsa) -> None:
    casos = (
        "ok", "velho_pelo_carimbo", "velho_pelo_mtime_sem_carimbo", "carimbo_vence_mtime",
        "vazio", "sem_assinatura", "sem_checksum", "corrompido", "nenhum", "parcial_mais_novo",
        "o_mais_novo_e_que_conta", "semanal_velha", "semanal_ausente", "semanal_corrompida",
    )  # fmt: skip

    def dump(
        caso: str,
        pasta: str,
        horas: float,
        *,
        corpo: bytes = b"PGDMP\x01\x0e\x00" + b"dados" * 40,
        checksum: str = "ok",
        nome: str | None = None,
    ) -> Path:
        return vps.dump(
            pasta, horas, corpo=corpo, checksum=checksum, nome=nome, raiz=f"casos/{caso}"
        )

    for caso in casos:
        if not caso.startswith("semanal_"):
            dump(caso, "semanal", _SEMANAL_BOA)
    dump("ok", "diario", 6.8)
    # mtime de AGORA e carimbo de 30 h: é o carimbo que manda (restore rejuvenesce mtime).
    dump("velho_pelo_carimbo", "diario", 30)
    _envelhecer(dump("velho_pelo_mtime_sem_carimbo", "diario", 0, nome="banco.dump"), 30)
    _envelhecer(dump("carimbo_vence_mtime", "diario", 2), 40)
    dump("vazio", "diario", 2, corpo=b"")
    dump("sem_assinatura", "diario", 2, corpo=b"-- PostgreSQL database dump (SQL puro)\n")
    dump("sem_checksum", "diario", 2, checksum="ausente")
    dump("corrompido", "diario", 2, checksum="errado")
    bom = dump("parcial_mais_novo", "diario", 6.8)
    # Mais NOVO que o dump bom e sem sha256: se fosse escolhido, o dump daria FAIL.
    (bom.parent / f"banco_de_reservas_{_ha(0):%Y%m%dT%H%M%SZ}.dump.parcial").write_bytes(b"PGDMP")
    dump("o_mais_novo_e_que_conta", "diario", 120, checksum="errado")
    dump("o_mais_novo_e_que_conta", "diario", 2)
    for caso in ("semanal_velha", "semanal_ausente", "semanal_corrompida"):
        dump(caso, "diario", 6.8)
    dump("semanal_velha", "semanal", 9 * 24 + 1)
    dump("semanal_corrompida", "semanal", _SEMANAL_BOA, checksum="errado")

    resultado = vps.funcoes(
        "".join(f'echo "CASO {c}"; BANCO_BACKUP_DIR="casos/{c}" banco_dumps\n' for c in casos)
    )

    esperado_dump = {
        "ok": ("OK", ""),
        "velho_pelo_carimbo": ("FAIL", "PARADO: o dump mais novo tem 30 h"),
        "velho_pelo_mtime_sem_carimbo": ("FAIL", "régua mtime (fallback: nome sem carimbo)"),
        "carimbo_vence_mtime": ("OK", ""),
        "vazio": ("FAIL", "está VAZIO"),
        "sem_assinatura": ("FAIL", "assinatura PGDMP"),
        "sem_checksum": ("FAIL", ".sha256, então a integridade não tem como ser provada"),
        "corrompido": ("FAIL", "CORROMPIDO"),
        "nenhum": ("FAIL", "NENHUM dump em casos/nenhum/diario"),
        "parcial_mais_novo": ("OK", ""),
        "o_mais_novo_e_que_conta": ("OK", ""),
    }
    for caso, (status, trecho) in esperado_dump.items():
        assert resultado[caso].status("banco_dump") == status, (caso, resultado[caso])
        assert trecho in resultado[caso].mensagem("banco_dump"), (caso, resultado[caso])
        assert resultado[caso].status("banco_semanal") == "OK", (caso, resultado[caso])
    assert any("sha256 confere" in linha for linha in resultado["ok"].logs)

    esperado_semanal = {
        "semanal_velha": "com 9 dias e 1 h (limiar 8 dias",
        "semanal_ausente": "NENHUMA cópia semanal",
        "semanal_corrompida": "INUTILIZÁVEL",
    }
    for caso, trecho in esperado_semanal.items():
        assert resultado[caso].status("banco_dump") == "OK", (caso, resultado[caso])
        assert resultado[caso].status("banco_semanal") == "FAIL", (caso, resultado[caso])
        assert trecho in resultado[caso].mensagem("banco_semanal"), (caso, resultado[caso])


@_PRECISA_BASH
def test_matriz_do_log_do_backup(vps: VpsFalsa) -> None:
    inicio = _eco(BACKUP, "backup do banco - inicio", _ha(5))
    falhou = [inicio, _eco(BACKUP, "nao esta de pe", _ha(5))]
    vps.escrever("backup/ok_offbox_ligada.log", *vps.linhas_backup_ok())
    vps.escrever("backup/so_local.log", *vps.linhas_backup_ok(offbox=False))
    vps.escrever("backup/falhou.log", *falhou)
    vps.escrever("backup/falhou_sem_aviso.log", inicio, "pg_dump: error: query failed")
    vps.escrever("backup/em_andamento.log", _eco(BACKUP, "backup do banco - inicio", _ha(0.15)))
    vps.escrever("backup/sem_execucao.log", "linha que nao e de execucao nenhuma")
    vps.escrever("backup/falha_antiga_sucesso_novo.log", *falhou, *vps.linhas_backup_ok(horas=2))
    vps.escrever("backup/sucesso_antigo_falha_nova.log", *vps.linhas_backup_ok(horas=30), *falhou)
    vps.escrever(
        "backup/mascara.log",
        inicio,
        "!! restic falhou em s3:https://chave:segredo-da-url@bucket.exemplo PGPASSWORD=segredo-eco",
    )
    # Sem carimbo legível a régua cai no mtime do log: recente = em andamento; velho = falhou.
    sem_carimbo = ">> [sem-data] backup do banco - inicio"
    vps.escrever("backup/sem_carimbo_recente.log", sem_carimbo)
    _envelhecer(vps.escrever("backup/sem_carimbo_velho.log", sem_carimbo), 3)
    # Off-box: cada uma das DUAS frases basta SOZINHA. Ali a frase ausente quer dizer "ligada", e a
    # redundância existe para o dia em que o wrapper reescrever uma delas — sem ela, verde falso.
    vps.escrever(
        "backup/so_a_frase_desligada.log",
        inicio,
        _eco(BACKUP, "copia off-box DESLIGADA", _ha(5)),
        _eco(BACKUP, "fim (local + off-box)", _ha(4.99)).replace("local + off-box", "reescrito"),
    )
    vps.escrever(
        "backup/so_o_fim_somente_local.log",
        inicio,
        "!! AVISO: o aviso do off-box foi reescrito",
        _eco(BACKUP, "fim (somente local)", _ha(4.99)),
    )
    casos = [
        "ok_offbox_ligada", "so_local", "falhou", "falhou_sem_aviso", "em_andamento",
        "ausente", "sem_execucao", "falha_antiga_sucesso_novo", "sucesso_antigo_falha_nova",
        "mascara", "sem_carimbo_recente", "sem_carimbo_velho", "so_a_frase_desligada",
        "so_o_fim_somente_local",
    ]  # fmt: skip

    resultado = vps.funcoes(
        "".join(
            f'echo "CASO {c}"; BANCO_BACKUP_LOG="backup/{c}.log" banco_backup_log\n' for c in casos
        )
    )

    assert resultado["ok_offbox_ligada"].reports == {
        "banco_backup": ("OK", ""),
        "banco_offbox": ("OK", ""),
    }
    assert resultado["so_local"].status("banco_backup") == "OK"
    assert resultado["so_local"].status("banco_offbox") == "AVISO"
    assert "SÓ LOCAL" in resultado["so_local"].mensagem("banco_offbox")
    for caso in ("so_a_frase_desligada", "so_o_fim_somente_local"):
        assert resultado[caso].status("banco_backup") == "OK", (caso, resultado[caso])
        assert resultado[caso].status("banco_offbox") == "AVISO", (caso, resultado[caso])
    assert resultado["falha_antiga_sucesso_novo"].status("banco_backup") == "OK"
    for caso, trecho in {
        "falhou": "Último aviso do script: !! container motor_expansao_postgres nao esta de pe",
        "falhou_sem_aviso": "Último aviso do script: nenhum",
        "sucesso_antigo_falha_nova": "NÃO terminou",
        "ausente": "Log do backup do banco ausente (backup/ausente.log)",
        "sem_execucao": "sem NENHUMA execução registrada",
        "sem_carimbo_velho": "pela régua mtime",
    }.items():
        assert resultado[caso].status("banco_backup") == "FAIL", (caso, resultado[caso])
        assert trecho in resultado[caso].mensagem("banco_backup"), (caso, resultado[caso])
        assert "banco_offbox" not in resultado[caso].reports, (
            "off-box de execução morta: não se sabe"
        )
    for caso in ("em_andamento", "sem_carimbo_recente"):
        assert resultado[caso].reports == {}, (caso, resultado[caso])
        assert any("backup em andamento" in linha for linha in resultado[caso].logs)
    mascarada = resultado["mascara"].mensagem("banco_backup")
    assert "segredo-da-url" not in mascarada and "segredo-eco" not in mascarada
    assert "https://***@bucket.exemplo" in mascarada and "PGPASSWORD=***" in mascarada


@_PRECISA_BASH
def test_matriz_do_expurgo(vps: VpsFalsa) -> None:
    real_falhou = [
        _eco(EXPURGO, "expurgo da origem das sessoes - inicio", _ha(6)),
        _eco(EXPURGO, "nao esta de pe", _ha(6)),
    ]
    vps.escrever("expurgo/ok.log", *vps.linhas_expurgo_ok())
    vps.escrever("expurgo/velho.log", *vps.linhas_expurgo_ok(40))
    vps.escrever("expurgo/so_simulacao.log", *vps.linhas_expurgo_ok(2, simular="--simular"))
    vps.escrever("expurgo/nao_terminou.log", *real_falhou)
    vps.escrever(
        "expurgo/em_andamento.log",
        _eco(EXPURGO, "expurgo da origem das sessoes - inicio", _ha(5 / 60)),
    )
    vps.escrever(
        "expurgo/simulacao_depois_da_falha.log",
        *real_falhou,
        *vps.linhas_expurgo_ok(1, simular="--simular"),
    )
    vps.escrever(
        "expurgo/simulacao_nao_rejuvenesce.log",
        *vps.linhas_expurgo_ok(40),
        *vps.linhas_expurgo_ok(1, simular="--simular"),
    )
    casos = [
        "ok", "velho", "ausente", "so_simulacao", "nao_terminou", "em_andamento",
        "simulacao_depois_da_falha", "simulacao_nao_rejuvenesce",
    ]  # fmt: skip

    resultado = vps.funcoes(
        "".join(
            f'echo "CASO {c}"; BANCO_EXPURGO_LOG="expurgo/{c}.log" banco_expurgo\n' for c in casos
        )
    )

    assert resultado["ok"].reports == {"banco_expurgo": ("OK", "")}
    for caso, trecho in {
        "velho": "sem rodar há 40 h (limiar 26 h, régua carimbo)",
        "ausente": "Log do expurgo das sessões ausente",
        "so_simulacao": "rodada com --simular não conta",
        "nao_terminou": "NÃO terminou",
        "simulacao_depois_da_falha": "nao esta de pe",
        "simulacao_nao_rejuvenesce": "sem rodar há 40 h",
    }.items():
        assert resultado[caso].status("banco_expurgo") == "FAIL", (caso, resultado[caso])
        assert trecho in resultado[caso].mensagem("banco_expurgo"), (caso, resultado[caso])
    assert resultado["em_andamento"].reports == {}
    assert any("expurgo em andamento" in linha for linha in resultado["em_andamento"].logs)


@_PRECISA_BASH
def test_matriz_da_medicao_dentro_do_container(vps: VpsFalsa) -> None:
    """Cada limiar nos dois lados da borda, o monitor cego e os limiares/container por env."""
    mb = 1024 * 1024
    saidas = {
        "saudavel": PSQL_SAUDAVEL,
        "tamanho_no_limiar": f"{5120 * mb} 3 100 0 0 0 0",
        "tamanho_acima": f"{5120 * mb + 1} 3 100 0 0 0 0",
        "conexoes_abaixo": "8388608 79 100 0 0 0 0",
        "conexoes_no_limiar": "8388608 80 100 0 0 0 0",
        "transacao_no_limiar": "8388608 3 100 1 600 0 0",
        "transacao_acima": "8388608 3 100 2 601 0 0",
        "lock_no_limiar": "8388608 3 100 0 0 1 300",
        "lock_acima": "8388608 3 100 0 0 1 301",
        "saida_fora_do_formato": "ERROR:  relation does not exist\n1 2 3",
        "saida_negativa": "8388608 3 100 1 -5 0 0",
        "saida_vazia": "",
        "limiares_por_env": "8388608 3 100 1 61 1 61",
    }
    limiares_baixos = "BANCO_TAMANHO_MAX_MB=1 BANCO_CONEXOES_PCT_MAX=3 BANCO_OCIOSA_MAX_MIN=1 BANCO_LOCK_MAX_MIN=1"
    corpo = ""
    for caso, saida in saidas.items():
        (vps.base / f"saida_{caso}.txt").write_text(saida + "\n", encoding="utf-8", newline="\n")
        prefixo = limiares_baixos if caso == "limiares_por_env" else ""
        corpo += (
            f'echo "CASO {caso}"; cp saida_{caso}.txt psql_saida.txt; {prefixo} banco_medidas\n'
        )
    corpo += 'echo "CASO docker_falhou"; : > docker_falha; banco_medidas; rm -f docker_falha\n'
    corpo += 'echo "CASO docker_pendurado"; cp saida_saudavel.txt psql_saida.txt\n'
    corpo += ": > docker_pendura; BANCO_TIMEOUT_S=1 banco_medidas; rm -f docker_pendura\n"
    corpo += 'echo "CASO container_por_env"; cp saida_saudavel.txt psql_saida.txt\n'
    corpo += "BANCO_CONTAINER=outro_postgres banco_medidas\n"

    resultado = vps.funcoes(corpo)

    medidas = ("banco_tamanho", "banco_conexoes", "banco_transacoes", "banco_locks")
    assert resultado["saudavel"].reports == dict.fromkeys(("banco_medicao", *medidas), ("OK", ""))
    assert any("medido (8 MB; conexões 3/100" in linha for linha in resultado["saudavel"].logs)
    borda = {
        "tamanho_no_limiar": None,
        "tamanho_acima": "banco_tamanho",
        "conexoes_abaixo": None,
        "conexoes_no_limiar": "banco_conexoes",
        "transacao_no_limiar": None,
        "transacao_acima": "banco_transacoes",
        "lock_no_limiar": None,
        "lock_acima": "banco_locks",
    }
    for caso, que_falha in borda.items():
        falhas = {k for k in medidas if resultado[caso].status(k) == "FAIL"}
        assert falhas == ({que_falha} if que_falha else set()), (caso, resultado[caso])
    casos_cegos = (
        "saida_fora_do_formato", "saida_negativa", "saida_vazia", "docker_falhou",
        "docker_pendurado",
    )  # fmt: skip
    for caso in casos_cegos:
        assert resultado[caso].status("banco_medicao") == "FAIL", (caso, resultado[caso])
        assert "Monitor cego conta como falha" in resultado[caso].mensagem("banco_medicao")
        assert not set(medidas) & set(resultado[caso].reports), "veredito sem medição"
    assert "relation does not exist" not in "".join(
        m for c in resultado.values() for _, m in c.reports.values()
    )
    assert {k for k in medidas if resultado["limiares_por_env"].status(k) == "FAIL"} == set(medidas)
    assert resultado["container_por_env"].status("banco_medicao") == "OK"
    assert vps.ler("docker_container.log").strip() == "outro_postgres"
