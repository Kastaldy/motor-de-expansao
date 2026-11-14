"""Contrato do lote noturno das entradas do modelo de praça (`scripts/cron/run_entradas_oportunidades.sh`).

DEC-086. A rotina roda na VPS, longe de qualquer teste: as regras que custaram caro em
outras rotinas viram texto travado aqui.
"""

from __future__ import annotations

from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
WRAPPER = _REPO / "scripts" / "cron" / "run_entradas_oportunidades.sh"
LINHA_CRON = "15 4 * * * /opt/motor-expansao-infra/run_entradas_oportunidades.sh"


def _executaveis() -> str:
    """O script sem as linhas de comentário."""
    linhas = WRAPPER.read_text(encoding="utf-8").splitlines()
    return "\n".join(linha for linha in linhas if not linha.lstrip().startswith("#"))


def test_a_rotina_existe_e_falha_cedo() -> None:
    texto = WRAPPER.read_text(encoding="utf-8")
    assert texto.startswith("#!/usr/bin/env bash")
    assert "set -euo pipefail" in texto
    assert "\r" not in texto, "a rotina roda no Linux: sem CR"
    codigo = _executaveis()
    assert 'flock -n 9' in codigo, "duas rodadas ao mesmo tempo disputariam o arquivo"
    assert codigo.index('LOG="${LOG_DIR}') < codigo.index("flock -n 9"), "log antes do lock"


def test_o_job_roda_no_container_do_site_com_a_pasta_gravavel_so_na_rodada_real() -> None:
    """A imagem, o `MOTOR_ROTAS_URL` e a malha são os do site: o cálculo é o da sugestão
    da Viabilidade. Só a rodada real monta a pasta da lista gravável."""
    codigo = _executaveis()
    assert "web python -m motor_expansao.dimensionamento.entradas_oportunidades" in codigo
    assert 'docker compose -f "$COMPOSE_FILE" run --rm --no-deps -T' in codigo
    assert 'MONTAGEM=(-u 0:0 -v "${HOST_OPORT}:/oportunidades-rw")' in codigo
    assert "--saida /oportunidades-rw/entradas_c10.parquet" in codigo
    seco = codigo[codigo.index('if [ "$DRY_RUN" = "1" ]; then\n  MONTAGEM=()') :]
    seco = seco[: seco.index("else")]
    assert "--saida /tmp/" in seco and "--limite 5" in seco and "-rw" not in seco


def test_a_url_do_banco_do_shell_nao_vence_o_env() -> None:
    """A variável do shell vence o `.env` na interpolação do compose (docs/banco_deploy.md)."""
    assert "unset MOTOR_DATABASE_URL MOTOR_DATABASE_URL_AR" in _executaveis()


def test_sem_restart_e_sem_deploy() -> None:
    """A aba relê o arquivo pelo mtime: gravar não exige restart. E nenhuma rotina faz
    deploy nem recria container (CLAUDE.md §6)."""
    codigo = _executaveis()
    for proibido in ("restart", "up -d", "--force-recreate", "pull", "ssh ", "scp "):
        assert proibido not in codigo, proibido


def test_o_token_vai_pelo_nome_e_nunca_pelo_valor() -> None:
    codigo = _executaveis()
    assert "-e API_TELEGRAM_TOKEN -e MONITOR_TELEGRAM_CHAT_ID" in codigo
    assert "API_TELEGRAM_TOKEN=$" not in codigo


def test_valhalla_fora_avisa_e_devolve_3_e_qualquer_outra_falha_avisa() -> None:
    codigo = _executaveis()
    bloco3 = codigo[codigo.index("  3)") : codigo.index("  *)")]
    assert "_avisar" in bloco3 and "exit 3" in bloco3
    resto = codigo[codigo.index("  *)") :]
    assert "_avisar" in resto and 'exit "$JOB_RC"' in resto


def test_a_linha_do_crontab_esta_no_script_e_no_runbook() -> None:
    assert LINHA_CRON in WRAPPER.read_text(encoding="utf-8")
    runbook = (_REPO / "docs" / "infra_producao.md").read_text(encoding="utf-8")
    assert LINHA_CRON in runbook
