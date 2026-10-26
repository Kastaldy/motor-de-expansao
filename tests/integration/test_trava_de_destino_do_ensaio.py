"""A trava de destino do teste de integração do banco -- provada SEM banco nenhum.

`test_login_ponta_a_ponta.py` escreve de verdade: cria usuário, redefine senha e grava em
`eventos`, que é append-only. A trava dele recusa banco cujo nome não diga `ensaio`/`test`, e
desde 24/10/2026 recusa também a `MOTOR_DATABASE_URL` que aponte para OUTRO banco: é por ela que
a aplicação escreve, e o `_ambiente` só a preenche quando ela está vazia. Antes disso, com ela
esquecida num segundo banco, a suíte redefiniu 7 senhas de lá e gravou 22 linhas em `eventos`
-- com 11 dos 18 testes verdes.

A trava roda ANTES de qualquer conexão, então dá para prová-la aqui, na suíte unitária, com URLs
que não levam a lugar nenhum (porta 1). O arquivo roda num SUBPROCESSO porque a trava é fixture de
módulo, e fixture não se chama direto.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("psycopg")

RAIZ = Path(__file__).resolve().parents[2]
ALVO = "tests/integration/test_login_ponta_a_ponta.py"
#: Marcador de que a recusa não ecoa a URL. Não é senha de nada.
SEGREDO = "marcador-que-nao-pode-vazar"
#: `connect_timeout` porque, no Windows, o psycopg não percebe a recusa de uma porta fechada e
#: espera o próprio teto, 130 s (medido; um socket cru recebe a recusa em 2 s). No Linux a
#: recusa chega na hora; aqui, no máximo 2 s.
ENSAIO = f"postgresql://dono:{SEGREDO}@127.0.0.1:1/banco_de_reservas_ensaio?connect_timeout=2"


def _rodar(**ambiente: str) -> str:
    """Roda o teste de integração com estas variáveis de banco e NENHUMA outra."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("MOTOR_DATABASE_URL")}
    env.pop("MOTOR_BANCO_DE_ENSAIO_OBRIGATORIO", None)
    env["PYTHONIOENCODING"] = "utf-8"
    env.update(ambiente)
    feito = subprocess.run(
        [sys.executable, "-m", "pytest", ALVO, "-x", "-q", "-rs", "-p", "no:cacheprovider"],
        cwd=RAIZ,
        env=env,
        # Sem isto, no Windows, herdar o stdin do pytest-pai falha (WinError 6/50) quando ele
        # não é um console -- o mesmo molde dos outros testes com subprocesso deste repo.
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    saida = feito.stdout + feito.stderr
    assert SEGREDO not in saida, "a saída do teste ECOOU a senha da URL:\n" + saida
    return saida


def test_recusa_a_url_da_aplicacao_apontando_para_outro_banco() -> None:
    saida = _rodar(
        MOTOR_DATABASE_URL_ADMIN=ENSAIO,
        MOTOR_DATABASE_URL=f"postgresql://app:{SEGREDO}@127.0.0.1:1/banco_de_reservas",
    )
    assert "RECUSADO: `MOTOR_DATABASE_URL`" in saida, saida


def test_aceita_as_duas_no_mesmo_banco_com_papeis_diferentes() -> None:
    """O caso do runbook (§1.2): dono na URL de DDL, `app` na da aplicação, MESMO banco.

    A trava deixa passar; quem para é a conexão, porque não há banco na porta 1 -- e sem o modo
    obrigatório isso é PULO, com o motivo escrito.
    """
    saida = _rodar(
        MOTOR_DATABASE_URL_ADMIN=ENSAIO,
        MOTOR_DATABASE_URL=(
            f"postgresql://app:{SEGREDO}@127.0.0.1:1/banco_de_reservas_ensaio?connect_timeout=2"
        ),
    )
    assert "RECUSADO" not in saida, saida
    assert "NÃO RODOU" in saida, saida


def test_url_ilegivel_recusa_sem_ecoar_a_senha() -> None:
    """O erro do psycopg cita o trecho que não entendeu; a recusa não pode carregá-lo junto."""
    saida = _rodar(
        MOTOR_DATABASE_URL_ADMIN=ENSAIO,
        MOTOR_DATABASE_URL=f"host=127.0.0.1 {SEGREDO}",
    )
    assert "RECUSADO: uma URL de banco do ambiente" in saida, saida
