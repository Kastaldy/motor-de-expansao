"""Travas de seguranca do backend do piloto web (BLK-SEC-05).

Cobrem:
  - guardrail path-traversal em `_uf_partition` (sink de todas as leituras por UF) e
    na validacao de fronteira do `RelatorioMunicipalIn.uf`;
  - tetos anti-DoS de upload de foto (constantes).

Segue o padrao de `test_piloto_web_api.py`: poe `web/server` no sys.path e chama as
funcoes direto (sem TestClient/httpx).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import app as pilot_app  # noqa: E402  (backend do piloto; web/server no sys.path acima)
from fastapi import HTTPException  # noqa: E402
from pydantic import ValidationError  # noqa: E402


@pytest.mark.parametrize(
    "mau",
    ["../../etc/passwd", "x/../../y", "S/P", "abc", "s", "12", "..", "SP/..", "", "  "],
)
def test_uf_partition_recusa_uf_perigosa(mau: str) -> None:
    with pytest.raises(HTTPException) as exc:
        pilot_app._uf_partition(mau)
    assert exc.value.status_code == 400


@pytest.mark.parametrize("uf", ["SP", "sp", "Rj", "MG"])
def test_uf_partition_aceita_sigla_valida(uf: str) -> None:
    part = pilot_app._uf_partition(uf)
    assert part.name == f"uf={uf.upper()}"  # so a sigla normalizada compoe o caminho


@pytest.mark.parametrize("mau", ["../../etc", "ABC", "S", "s/p", "12"])
def test_relatorio_municipal_in_recusa_uf_invalida(mau: str) -> None:
    with pytest.raises(ValidationError):
        pilot_app.RelatorioMunicipalIn(uf=mau, municipio="Cidade")


def test_relatorio_municipal_in_aceita_uf_valida() -> None:
    modelo = pilot_app.RelatorioMunicipalIn(uf="sp", municipio="Campinas")
    assert modelo.uf == "sp"
    assert modelo.municipio == "Campinas"


def test_relatorio_municipal_in_recusa_municipio_absurdo() -> None:
    with pytest.raises(ValidationError):
        pilot_app.RelatorioMunicipalIn(uf="SP", municipio="x" * 500)


def test_limites_de_foto_sao_sensatos() -> None:
    assert pilot_app._FOTOS_MAX >= 2  # o PDF usa 2; sobra margem minima
    assert 0 < pilot_app._FOTO_MAX_BYTES <= 32 * 1024 * 1024


# ── OpenAPI/docs desligados por padrao (pentest 2026-08-19) ──────────────────
def test_openapi_e_docs_desligados_por_padrao() -> None:
    """Sem MOTOR_PILOTO_DOCS=1 (o caso de producao), o piloto NAO expoe schema/UI:
    um autenticado nao deve conseguir enumerar a superficie por /openapi.json|/docs|/redoc.
    """
    assert pilot_app.app.openapi_url is None
    assert pilot_app.app.docs_url is None
    assert pilot_app.app.redoc_url is None


# ── Gate de concorrencia nas rotas de relatorio pesadas (pentest 2026-08-19) ──
def test_rotas_pesadas_passam_pelo_semaforo() -> None:
    """`/relatorio/municipal` e `/simulador/xlsx` devem serializar pelo `_PDF_SEMAFORO`
    como /pontual e /comparacao ja' faziam — senao um flood satura o threadpool do
    uvicorn e derruba ate' o /api/health.
    """
    import asyncio
    import inspect

    # As rotas viraram finas e assincronas; o corpo pesado do municipal virou helper sync.
    assert asyncio.iscoroutinefunction(pilot_app.relatorio_municipal)
    assert asyncio.iscoroutinefunction(pilot_app.simulador_xlsx)
    assert not asyncio.iscoroutinefunction(pilot_app._gerar_relatorio_municipal_response)

    # E ambas realmente entram no semaforo antes de delegar ao threadpool.
    assert "_PDF_SEMAFORO" in inspect.getsource(pilot_app.relatorio_municipal)
    assert "_PDF_SEMAFORO" in inspect.getsource(pilot_app.simulador_xlsx)


# ── IP real na trilha DEC-027: ultimo hop do XFF, nao o forjavel [0] ─────────
def test_ip_real_pega_ultimo_hop_do_xff() -> None:
    """O Caddy anexa o peer real ao FIM do X-Forwarded-For; os tokens a' esquerda sao
    controlados pelo cliente. A trilha (pentest 2026-08-19) deve pegar o ULTIMO."""
    # Cliente forja 8.8.8.8; o Caddy anexa o IP real -> pegamos o real.
    assert pilot_app._ip_real_do_xff("8.8.8.8, 203.0.113.7", "10.0.0.1") == "203.0.113.7"
    # Sem XFF: cai no IP do socket.
    assert pilot_app._ip_real_do_xff(None, "203.0.113.7") == "203.0.113.7"
    # XFF de um hop so'.
    assert pilot_app._ip_real_do_xff("203.0.113.7", None) == "203.0.113.7"
    # XFF vazio/em branco -> fallback do socket, nunca string vazia.
    assert pilot_app._ip_real_do_xff("   ", "10.0.0.1") == "10.0.0.1"
