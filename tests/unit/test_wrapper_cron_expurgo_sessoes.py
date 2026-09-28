"""O wrapper do expurgo da origem das sessoes (P15, prazo fechado em 23/09/2026).

Estes testes leem o SCRIPT, sem disparar `bash`. E' decisao, nao preguica: os wrappers que
executam o shell (`test_wrapper_cron_weekly_90.py`) sao justamente os que falham de forma
instavel nesta estacao (`WinError 50` ao spawnar em execucoes sucessivas), e um teste que
falha sozinho ensina a ignorar vermelho. O que se guarda aqui e' ESTRUTURA, e estrutura se
le'.

O teste mais importante do arquivo e' o da ORDEM ENTRE OS DOIS CRONS: nenhum dos dois
arquivos, sozinho, garante que o expurgo roda ANTES do backup -- e se a ordem inverter, o
dump passa a carregar por ate' 28 dias exatamente o dado que o expurgo existe para remover.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_CRON = Path(__file__).resolve().parents[2] / "scripts" / "cron"
EXPURGO = _CRON / "run_expurgo_sessoes.sh"
BACKUP = _CRON / "run_backup_banco.sh"


def _texto(caminho: Path) -> str:
    return caminho.read_text(encoding="utf-8")


def _horario_do_cron(texto: str, script: str) -> tuple[int, int]:
    """(hora, minuto) da linha de crontab que o cabecalho do script documenta."""
    padrao = rf"^#\s+\(\s*crontab -l.*?echo '(\d+)\s+(\d+)\s+[^']*{re.escape(script)}"
    achado = re.search(padrao, texto, re.MULTILINE)
    assert achado is not None, f"nao achei a linha de crontab de {script} no cabecalho"
    return int(achado.group(2)), int(achado.group(1))


def test_o_expurgo_roda_ANTES_do_backup() -> None:
    """A ordem entre os dois crons E' a politica de retencao.

    O backup dumpa o banco inteiro e a copia semanal fica 28 dias. Se o expurgo rodasse
    DEPOIS, cada dump do dia carregaria os IPs ja' vencidos, e a copia off-box os guardaria
    por quatro semanas -- ou seja, a retencao de 90 dias viraria 118 na pratica, sem ninguem
    perceber. Nenhum dos dois arquivos garante isso sozinho; e' o par que garante.
    """
    h_exp, m_exp = _horario_do_cron(_texto(EXPURGO), "run_expurgo_sessoes.sh")
    h_bkp, m_bkp = _horario_do_cron(_texto(BACKUP), "run_backup_banco.sh")

    assert (h_exp, m_exp) < (h_bkp, m_bkp), (
        f"o expurgo ({h_exp:02d}:{m_exp:02d}) passou a rodar DEPOIS do backup "
        f"({h_bkp:02d}:{m_bkp:02d}) — o dump voltaria a carregar IP vencido"
    )


def test_o_script_NAO_carrega_SQL() -> None:
    """A consulta e o prazo vivem em `db/sessoes.py`, com teste e sabotagem.

    Repeti-los aqui criaria duas redacoes da mesma regra, e a segunda e' sempre a que
    ninguem lembra de atualizar -- o defeito que este repositorio ja' pagou caro em
    `qualidade_join_uf` (DEC-050) e na cascata do funil (DEC-044).
    """
    codigo = "\n".join(
        linha for linha in _texto(EXPURGO).splitlines() if not linha.lstrip().startswith("#")
    ).upper()
    for verbo in ("UPDATE ", "DELETE ", "SELECT ", "INTERVAL"):
        assert verbo not in codigo, f"o wrapper passou a carregar SQL proprio: {verbo!r}"


def test_a_senha_NAO_vai_na_URL() -> None:
    """Senha fora da URL, em `PGPASSWORD`.

    Senha com `@`, `:` ou `/` quebra uma URL montada por concatenacao, e a mensagem que o
    operador ve' e' "autenticacao falhou" -- que manda investigar a senha, nao a montagem.
    Custou uma depuracao em 23/09/2026, na propria estacao de desenvolvimento.
    """
    texto = _texto(EXPURGO)
    achado = re.search(r'MOTOR_DATABASE_URL_ADMIN="([^"]+)"', texto)
    assert achado is not None, "nao achei a montagem da URL"
    url = achado.group(1)
    assert ":" not in url.split("@")[0].split("//")[1], f"a senha voltou para a URL: {url}"
    assert "PGPASSWORD" in texto


def test_a_senha_nao_aparece_no_argv_do_docker() -> None:
    """`-e VAR` SEM valor herda do ambiente. Com valor, a senha fica visivel em `ps` para
    qualquer usuario da maquina. Mesmo cuidado do `run_backup_banco.sh`."""
    texto = _texto(EXPURGO)
    assert "-e MOTOR_DATABASE_URL_ADMIN -e PGPASSWORD" in texto
    assert "-e PGPASSWORD=" not in texto
    assert "-e MOTOR_DATABASE_URL_ADMIN=" not in texto


def test_falha_cedo_e_alto() -> None:
    """`set -euo pipefail` e as tres guardas: `.env` sem credencial, `APP_DIR` inexistente e
    Postgres fora do ar. Cron que falha em silencio e' pior que cron que nao existe."""
    texto = _texto(EXPURGO)
    assert "set -euo pipefail" in texto
    assert "nao esta de pe" in texto
    assert "ausentes em" in texto
    assert "nao existe" in texto


def _so_o_codigo(caminho: Path) -> str:
    """O script SEM as linhas de comentario.

    Existe porque a primeira versao destes testes varria o texto cru, e a PROSA deste
    wrapper explica cada flag que ela usa -- entao remover `--no-deps` do comando deixava o
    teste verde, casando com o comentario que o descreve. E' a terceira vez que este erro
    aparece nesta sessao: guarda que le' comentario nao guarda comportamento.
    """
    return "\n".join(
        linha for linha in _texto(caminho).splitlines() if not linha.lstrip().startswith("#")
    )


def test_nao_sobe_o_banco_sozinho() -> None:
    """`--no-deps`: se o Postgres estiver fora, a falha tem de ser clara. Um cron que sobe o
    banco as 4h40 esconde a queda ate' alguem estranhar o grafico."""
    assert "--no-deps" in _so_o_codigo(EXPURGO)


def test_o_smoke_documentado_e_o_que_NAO_escreve() -> None:
    """A instalacao manda rodar com `--simular` primeiro. Um smoke que ja' escreve nao e'
    smoke -- e aqui o que ele escreveria seria a remocao de dado."""
    texto = _texto(EXPURGO)
    assert "--simular" in texto
    instalacao = texto[texto.index("INSTALACAO") : texto.index("DIARIO, e nao semanal")]
    assert "--simular   # smoke" in instalacao


@pytest.mark.parametrize("script", [EXPURGO, BACKUP])
def test_os_dois_crons_existem_e_sao_executaveis_por_conteudo(script: Path) -> None:
    """Guarda contra o teste acima virar vacuo: se um dos arquivos sumir ou for renomeado,
    a comparacao de horario compararia com o nada."""
    assert script.is_file(), f"{script.name} sumiu"
    assert _texto(script).startswith("#!/usr/bin/env bash")
