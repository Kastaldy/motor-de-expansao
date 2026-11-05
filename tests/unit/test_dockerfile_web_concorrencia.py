"""Backstop de concorrencia do `web` (solidificacao do pentest, item 1 do achado #1).

Trava por contrato que o CMD do `uvicorn` no Dockerfile.web traz `--limit-concurrency`:
sem ele, uma enxurrada de requisicoes empilha conexoes/threadpool no worker unico. E' o
par do `--limit-concurrency` que a API deveria ter; aqui fica guardado contra regressao.
"""

from __future__ import annotations

from pathlib import Path

_RAIZ = Path(__file__).resolve().parents[2]


def test_dockerfile_web_limita_concorrencia_do_uvicorn() -> None:
    txt = (_RAIZ / "Dockerfile.web").read_text(encoding="utf-8")
    # O CMD final do uvicorn tem de pinar --limit-concurrency (backstop de flood).
    cmd = [ln for ln in txt.splitlines() if ln.strip().startswith("CMD") and "uvicorn" in ln]
    assert cmd, "nao achei o CMD do uvicorn no Dockerfile.web"
    assert "--limit-concurrency" in cmd[-1], (
        "o CMD do uvicorn do web precisa de --limit-concurrency (backstop de concorrencia)"
    )
