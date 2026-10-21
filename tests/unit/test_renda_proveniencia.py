"""Versao de fatores da renda: so OPERACIONAL, nunca para o usuario (E0; DEC-072).

A proveniencia da renda e dado INTERNO (decisao do Felipe): nenhum payload de usuario, schema
da API externa ou PDF a exibe. O que fica e o que serve ao rollback:
  - healthchecks: `renda_fatores = {versao, fixada_por_env}` -- sem caminho nem infra (o
    `/api/health` do piloto foi enxugado no pentest, Onda B #8);
  - log do boot: INFO com versao/pais, WARNING quando a versao foi FIXADA por env;
  - compose: `MOTOR_FATORES_RENDA_VERSAO` repassada aos containers.

E trava que a chave `renda_meta` NAO volte aos payloads (ponto, /api/me, UF, municipio, rede)
nem ao contrato da API externa.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

from motor_expansao.renda import carregar_fatores, fatores_do_health

RAIZ = Path(__file__).resolve().parents[2]
SERVER = RAIZ / "web" / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))


def test_bloco_do_health_so_tem_versao_e_fixacao():
    f = carregar_fatores()
    assert fatores_do_health() == {"versao": f.versao, "fixada_por_env": False}


def test_modulo_da_renda_nao_expoe_proveniencia_ao_usuario():
    import motor_expansao.renda as renda

    assert not hasattr(renda, "renda_meta")
    assert not hasattr(renda, "proveniencia")
    for pais in ("BR", "AR"):
        assert not hasattr(carregar_fatores(pais), "rotulo_pdf"), pais


# ---------------------------------------------------------------------------
# Nenhum payload de usuario carrega a proveniencia
# ---------------------------------------------------------------------------


def test_nenhum_payload_do_piloto_carrega_renda_meta():
    """Varredura do fonte inteiro do backend do piloto: ponto (GET/alcance/geometria), /api/me,
    /api/uf, /api/municipio e as rotas da rede montam o payload ali."""
    fonte = (SERVER / "app.py").read_text(encoding="utf-8")
    assert "renda_meta" not in fonte


def test_api_me_nao_traz_renda_meta():
    import app as pilot

    resposta = pilot.me(remote_user=None)
    assert "renda_meta" not in resposta
    assert "renda_meta" not in resposta["perfil"]


def test_api_externa_nao_traz_renda_meta():
    from motor_expansao.api.schemas import AnalisarResponseJSON

    assert "renda_meta" not in AnalisarResponseJSON.model_fields
    fonte = (RAIZ / "src" / "motor_expansao" / "api" / "service.py").read_text(encoding="utf-8")
    assert "renda_meta" not in fonte


# ---------------------------------------------------------------------------
# Health e boot (rollback)
# ---------------------------------------------------------------------------


def test_health_do_piloto_tem_a_versao_de_fatores_e_nada_alem():
    import app as pilot

    corpo = asyncio.run(pilot.health())
    assert corpo == {"status": "ok", "renda_fatores": fatores_do_health()}
    # Sem caminho, sem infra (pentest Onda B #8): nada que pareca path no corpo inteiro.
    assert "/" not in repr(corpo["renda_fatores"]["versao"])


def test_boot_do_piloto_loga_versao_pais_e_fixacao(caplog):
    import app as pilot

    with caplog.at_level("INFO", logger="piloto.renda"):
        pilot._init_renda_paths_no_boot()
    f = carregar_fatores()
    linhas = [r for r in caplog.records if r.name == "piloto.renda"]
    assert any(
        f"versao={f.versao}" in r.getMessage()
        and f"pais={f.pais}" in r.getMessage()
        and "fixada_por_env=False" in r.getMessage()
        and r.levelname == "INFO"
        for r in linhas
    )


def test_health_da_api_externa_tem_a_versao_de_fatores():
    """Chama o endpoint das DUAS rotas direto (sem `httpx`/TestClient, ausentes no [dev])."""
    from motor_expansao.api.main import create_app

    app = create_app()
    rotas = {r.path: r.endpoint for r in app.routes if getattr(r, "path", "").endswith("/health")}
    assert {"/health", "/api/v1/health"} <= set(rotas)
    for rota in ("/health", "/api/v1/health"):
        corpo = asyncio.run(rotas[rota]())
        assert corpo["renda_fatores"] == fatores_do_health(), rota
        assert corpo["status"] == "ok"


def test_api_le_os_insumos_do_mesmo_staging_que_a_subida_validou(tmp_path, monkeypatch):
    """`API_STAGING_DIR` divergente do staging do perfil: a leitura segue o validado."""
    from motor_expansao.api import settings as api_settings
    from motor_expansao.api.main import create_app
    from motor_expansao.renda import insumos
    from tests.unit.renda_fixtures import apontar_staging_renda

    perfil_staging = tmp_path / "perfil_staging"
    validado = tmp_path / "api_staging"
    perfil_staging.mkdir()
    validado.mkdir()
    apontar_staging_renda(monkeypatch, perfil_staging)  # registra a restauracao pos-teste
    monkeypatch.setenv("API_STAGING_DIR", str(validado))
    api_settings.get_settings.cache_clear()
    try:
        create_app()
        assert insumos.staging_dir() == validado
    finally:
        api_settings.get_settings.cache_clear()


def test_openapi_documenta_renda_fatores_e_nao_renda_meta():
    yaml = pytest.importorskip("yaml")
    spec = yaml.safe_load((RAIZ / "docs" / "api_geoespacial_openapi.yaml").read_text(encoding="utf-8"))
    schemas = spec["components"]["schemas"]
    assert "RendaMeta" not in schemas
    assert "renda_meta" not in schemas["AnalisarResponseJSON"]["properties"]
    assert "renda_fatores" in schemas["HealthResponse"]["properties"]


def test_boot_com_versao_fixada_por_env_loga_warning_e_o_health_diz(caplog, monkeypatch):
    """Rollback por env: o boot sobe em WARNING e o `/api/health` publica `fixada_por_env`."""
    import app as pilot

    from motor_expansao.renda import ENV_VERSAO

    versao = carregar_fatores().versao
    monkeypatch.setenv(ENV_VERSAO, versao)
    carregar_fatores.cache_clear()
    try:
        with caplog.at_level("INFO", logger="piloto.renda"):
            pilot._init_renda_paths_no_boot()
        avisos = [r for r in caplog.records if r.name == "piloto.renda" and r.levelname == "WARNING"]
        assert any("fixada_por_env=True" in r.getMessage() for r in avisos)
        assert asyncio.run(pilot.health())["renda_fatores"] == {"versao": versao, "fixada_por_env": True}
    finally:
        monkeypatch.delenv(ENV_VERSAO)
        carregar_fatores.cache_clear()


@pytest.mark.parametrize(
    ("compose", "servicos"),
    [("docker-compose.prod.yml", ("api", "web")), ("docker-compose.ar.yml", ("web_ar",))],
)
def test_compose_repassa_a_fixacao_de_versao_aos_containers(compose, servicos):
    """O compose nao tem `env_file`: sem a var listada, o rollback do runbook nao chega."""
    yaml = pytest.importorskip("yaml")
    from motor_expansao.renda import ENV_VERSAO

    spec = yaml.safe_load((RAIZ / compose).read_text(encoding="utf-8"))
    for nome in servicos:
        servico = spec["services"][nome]
        assert "env_file" not in servico  # se ganhar env_file, rever este teste
        env = servico["environment"]
        assert env[ENV_VERSAO] == f"${{{ENV_VERSAO}:-}}", (compose, nome)
