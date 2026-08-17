"""Valida a Rede de Seguranca 1 do run-ralph-loop.sh (BLK-SEC-05): a regex que
aborta o loop se houver credencial sensivel no ambiente.

Le a regex REAL do script (nao uma copia) e confere que ela casa as credenciais que
DEVE barrar e NAO casa o token de auth do proprio loop nem config benigna. Portavel
(so `re`, sem depender de `grep` no PATH).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "run-ralph-loop.sh"


def _regex_do_script() -> str:
    texto = _SCRIPT.read_text(encoding="utf-8")
    m = re.search(r"grep -Eiq '([^']+)'", texto)
    assert m, "nao achei a linha `grep -Eiq '...'` (Rede de Seguranca 1) no run-ralph-loop.sh"
    return m.group(1)


@pytest.mark.parametrize(
    "linha_env",
    [
        "VPS_KEY=abc",
        "SSH_PRIVATE_KEY=abc",
        "CLICKUP_WRITE=abc",
        "DEPLOY_KEY=abc",
        "GROWTH_API_TOKEN=abc",
        "MEU_TOKEN_PROD=abc",
        "GH_TOKEN=abc",
        "GITHUB_TOKEN=abc",
        "AUTO_MERGE_PAT=abc",
        "AUTHELIA_JWT_SECRET=abc",
        "API_TELEGRAM_TOKEN=abc",
        "API_BOT_SENHA=abc",
        "API_TOKENS=abc",
        "API_API_CALL_TOKEN=abc",
    ],
)
def test_regex_aborta_com_credencial_sensivel(linha_env: str) -> None:
    assert re.search(_regex_do_script(), linha_env, re.IGNORECASE), (
        f"{linha_env} deveria casar a regex e abortar o loop"
    )


@pytest.mark.parametrize(
    "linha_env",
    [
        "CLAUDE_CODE_OAUTH_TOKEN=abc",  # auth do proprio loop — NUNCA pode abortar
        "API_ENVIRONMENT=development",  # config benigna (por isso nao usamos `API_` cru)
        "API_BASE_URL=http://api:8077",
        "API_PREFIX=/api/v1",
        "PATH=/usr/bin",
        "HOME=/home/appuser",
    ],
)
def test_regex_nao_aborta_com_env_benigno(linha_env: str) -> None:
    assert not re.search(_regex_do_script(), linha_env, re.IGNORECASE), (
        f"{linha_env} NAO deveria casar a regex (falso-positivo travaria o loop)"
    )
