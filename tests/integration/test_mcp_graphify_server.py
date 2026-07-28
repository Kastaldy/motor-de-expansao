"""Smoke do servidor MCP do graphify sobre stdio (BLK-GRAPH-02).

ESTE TESTE SKIPa NO CI E NO CONTAINER DO LOOP, porque nenhum dos dois instala o grupo `graph`
do `pyproject.toml`. Dito sem eufemismo: ELE NAO E O GATE. A validacao executada do bloco e:

  (a) `tests/contracts/test_grafo_ferramenta.py`, que NAO importa `mcp` nem `graphify`, NAO usa
      rede e por isso roda SEMPRE -- e' ele quem trava o pin `mcp<2`, o contrato do `.mcp.json`,
      o `.gitattributes` e o `.githooks/`;
  (b) a execucao MANUAL e OBRIGATORIA de `python scripts/verify_mcp_graphify.py`, cuja saida
      integral vai colada no handoff do Builder e no corpo do PR.

O papel deste arquivo e ser rede de seguranca para quem TEM o grupo instalado (estacao de
trabalho): se o handshake real quebrar -- por bump do `mcp`, por mudanca no CLI do graphify ou por
edicao infeliz do `.mcp.json` -- a suite local acusa antes do PR.

As tools `list_prs`/`get_pr_impact`/`triage_prs` shellam o `gh` (rede + auth) e por isso ficam
FORA da prova: teste que depende de rede falha por motivo errado.

POR QUE `subprocess` E NAO `from verify_mcp_graphify import main`: o script faz um handshake
JSON-RPC sobre stdio com um processo filho. Reexecuta-lo como processo separado confina pipes,
handles e qualquer estado de `anyio`/`asyncio` fora do processo de teste -- que, sob
`pytest -n auto`, e' um worker do xdist falando com o controlador exatamente por stdin/stdout. O
plano do bloco previa as duas formas; esta e a de menor acoplamento.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("mcp", reason="grupo `graph` nao instalado (CI/loop nao instalam)")

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "verify_mcp_graphify.py"


def test_mcp_do_graphify_responde_ao_handshake_real() -> None:
    """Sobe o servidor como o `.mcp.json` manda e exige `VERDICT: PASS` (exit 0)."""
    assert SCRIPT.is_file(), (
        "`scripts/verify_mcp_graphify.py` ausente. Ele e a prova funcional VERSIONADA do bloco: "
        "quando o graphify suportar `mcp 2.x`, reconferir o pin tem de ser um comando so."
    )

    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=RAIZ,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )

    assert proc.returncode == 0, (
        "handshake MCP falhou (VERDICT: FAIL). Causa mais provavel, MEDIDA em 2026-07-28: `mcp` "
        "2.x instalado. O 2.0.0 removeu `AnyUrl` de `mcp.types`, que `graphify/serve.py:1116` "
        "ainda importa, e o `try/except` do upstream mascara o erro com a mensagem ENGANOSA "
        "'mcp not installed'. Confira com `python -m pip show mcp` e reinstale com "
        "`python -m pip install --group graph` (o grupo pina `mcp>=1.28,<2`).\n"
        f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
    )
    assert "VERDICT    : PASS" in proc.stdout, (
        f"exit 0 sem `VERDICT: PASS` na saida -- prova inconsistente.\n{proc.stdout}"
    )
