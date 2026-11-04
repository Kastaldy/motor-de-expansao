"""Contrato da rotina mensal do pico por estado (`scripts/cron/run_pico_por_uf.sh`).

Emenda de 2026-10-29 da DEC-078. A rotina roda na VPS uma vez por mês, longe de qualquer teste:
por isso as regras que custaram caro em outras rotinas viram texto travado aqui.
"""

from __future__ import annotations

from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
WRAPPER = _REPO / "scripts" / "cron" / "run_pico_por_uf.sh"


def _executaveis() -> str:
    """O script sem as linhas de comentário."""
    linhas = WRAPPER.read_text(encoding="utf-8").splitlines()
    return "\n".join(linha for linha in linhas if not linha.lstrip().startswith("#"))


def test_a_rotina_existe_e_falha_cedo() -> None:
    texto = WRAPPER.read_text(encoding="utf-8")
    assert texto.startswith("#!/usr/bin/env bash")
    assert "set -euo pipefail" in texto
    assert "\r" not in texto, "a rotina roda no Linux: sem CR"


def test_o_job_resolve_o_perfil_de_producao() -> None:
    """Lição do BLK-SAUDE-08: sem MOTOR_DATA_DIR e o bind do perfil, o pacote procura o perfil
    ao lado do pacote instalado e o job morre no import."""
    codigo = _executaveis()
    assert 'PERFIL_MOUNT="${HOST_DATA}/perfil.json:/app/data/perfil.json:ro"' in codigo
    i = codigo.index('python -m motor_expansao.dimensionamento.pico_por_uf "${JOB_ARGS[@]}"')
    job = codigo[codigo.rindex("docker run", 0, i) : i]
    assert "-e MOTOR_DATA_DIR=/app/data" in job
    assert '-v "$PERFIL_MOUNT"' in job


def test_o_modo_seco_nao_escreve_nem_avisa() -> None:
    codigo = _executaveis()
    assert 'MOUNT_STAGING="${MOUNT_STAGING}:ro"' in codigo
    assert "JOB_ARGS+=(--seco)" in codigo
    assert "JOB_ARGS+=(--avisar)" in codigo


def test_sem_restart_e_sem_deploy() -> None:
    """A leitura relê o arquivo pelo mtime: publicar não exige restart. E nenhuma rotina faz
    deploy nem recria container (CLAUDE.md §6)."""
    codigo = _executaveis()
    for proibido in ("docker restart", "docker compose", "--force-recreate", "ssh ", "scp "):
        assert proibido not in codigo, proibido


def test_o_token_vai_pelo_nome_e_nunca_pelo_valor() -> None:
    """`-e NOME` sem valor: o token não aparece no argv do docker (visível em `ps`)."""
    codigo = _executaveis()
    assert "-e API_TELEGRAM_TOKEN -e MONITOR_TELEGRAM_CHAT_ID" in codigo
    assert "API_TELEGRAM_TOKEN=$" not in codigo


def test_falha_que_nao_e_o_portao_avisa_ops() -> None:
    codigo = _executaveis()
    assert "2) echo" in codigo  # portão reprovado: o próprio job já avisou
    assert '*) _avisar_falha "job do pico por estado' in codigo


def test_a_linha_do_crontab_esta_documentada() -> None:
    assert "0 4 3 * * /opt/motor-expansao-infra/run_pico_por_uf.sh" in WRAPPER.read_text(
        encoding="utf-8"
    )
