"""Prova funcional do servidor MCP do graphify (BLK-GRAPH-02).

Sobe o processo exatamente como o `.mcp.json` manda e faz initialize + tools/list +
tools/call por JSON-RPC sobre stdio. Nao depende do harness do Claude Code.

Uso:  python scripts/verify_mcp_graphify.py     (exit 0 = PASS)

Requer o grupo `graph` do pyproject: python -m pip install --group graph
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ESPERADO = [
    "get_community",
    "get_neighbors",
    "get_node",
    "get_pr_impact",
    "god_nodes",
    "graph_stats",
    "list_prs",
    "query_graph",
    "shortest_path",
    "triage_prs",
]


def main() -> int:
    srv = json.loads((RAIZ / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]["graphify"]
    cmd = [srv["command"], *srv.get("args", [])]
    env = {**os.environ, **srv.get("env", {})}
    print("LAUNCH:", cmd, "\nCWD   :", RAIZ)

    errf = tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace")
    p = subprocess.Popen(
        cmd,
        cwd=RAIZ,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=errf,
        text=True,
        encoding="utf-8",
        bufsize=1,
    )

    def send(o: dict) -> None:
        assert p.stdin is not None
        p.stdin.write(json.dumps(o) + "\n")
        p.stdin.flush()

    send(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "blk-graph-02-probe", "version": "1"},
            },
        }
    )
    send({"jsonrpc": "2.0", "method": "notifications/initialized"})
    send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    send({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "graph_stats", "arguments": {}}})
    send(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "query_graph",
                "arguments": {"question": "score_priorizacao", "depth": 2, "token_budget": 600},
            },
        }
    )

    got: dict[int, dict] = {}
    deadline = time.time() + 120
    assert p.stdout is not None
    while time.time() < deadline and len(got) < 4:
        line = p.stdout.readline()
        if not line:
            break
        try:
            m = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(m, dict) and "id" in m:
            got[m["id"]] = m

    assert p.stdin is not None
    p.stdin.close()
    try:
        rc = p.wait(timeout=20)
    except subprocess.TimeoutExpired:
        p.kill()
        rc = p.wait()

    def texto(i: int) -> str:
        c = (got.get(i, {}).get("result", {}) or {}).get("content") or [{}]
        return (c[0] or {}).get("text", "")

    init = got.get(1, {}).get("result", {})
    tools = [t["name"] for t in got.get(2, {}).get("result", {}).get("tools", [])]
    print("PROTOCOL   :", init.get("protocolVersion"))
    print("SERVERINFO :", init.get("serverInfo"))
    print(f"TOOLS ({len(tools)}) : {sorted(tools)}")
    print("graph_stats:", " | ".join(texto(3).splitlines())[:400])
    print("query_graph:", " | ".join(texto(4).splitlines())[:300])
    print("EXIT       :", rc)
    errf.seek(0)
    print("STDERR     :", errf.read()[-800:] or "(vazio)")

    ok = (
        sorted(tools) == ESPERADO
        and "error" not in got.get(3, {})
        and "error" not in got.get(4, {})
        and texto(3).strip() != ""
        and texto(4).strip() != ""
    )
    print("VERDICT    :", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
