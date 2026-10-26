"""Testes da matriz de classes do guard (BLK-ORQ-20): CRITICO / GOVERNANCA / LIMPO.

O `loop_guard.py` deixou de ser so a rede do ralph e passou a ser tambem o motor do check `guard`
do CI. Este arquivo tranca:

* a classificacao PURA (`classificar`), sem git;
* a REGRESSAO dos scores paralelos servidos em producao (`calcular_colunas_mercado.py`,
  `relatorio_municipal.py` etc.), que ANTES passavam batido pelo regex `*scoring*`;
* a REGRESSAO do "PR que desarma o proprio check `test`" (F1): o job `test` roda em
  `pull_request`, isto e, A PARTIR DO HEAD DO PR — entao `pyproject.toml` (testpaths/ruff),
  `conftest.py`, `constraints.txt`, config do gitleaks/Trivy e os `Dockerfile.*` sao CRITICO;
* a REGRESSAO da COBERTURA de producao (F7): caminhos que um bloco "Media" (auto-mergeavel!)
  ainda podia alterar mudando um numero que o comite le como verdade;
* a classe GOVERNANCA (o guard, CLAUDE.md, backlog, runner do loop...), que antes era 100%
  desprotegida — um agente podia reescrever o guarda que o julga;
* os caminhos que precisam continuar LIMPOS (display puro do dashboard, testes, docs), senao o
  auto-merge dos blocos Baixa/Media morre de falso-positivo;
* a COBERTURA do banco de producao (epic do banco, 2026-10-24): o pacote `src/motor_expansao/db/`
  inteiro e os crons do banco (backup/expurgo e o proximo que levar `banco`/`sessoes` no nome)
  sao CRITICO; o conferidor do corte, o rastreio de vazamento e o contrato da porta unica (D28)
  sao GOVERNANCA; os demais testes do banco, os crons das outras frentes e o extrator de
  migrations seguem LIMPOS;
* a CITACAO do git: caminho com acento chega entre aspas e com octal nos DOIS modos, e o guard
  a desfaz antes de casar -- sem isso, toda regra ancorada (a do banco inclusive) era contornavel;
* o contrato de saida dos modos `--stdin` e `--json` consumidos pelo job do CI.

O arquivo legado `test_loop_guard.py` (matriz do ralph) continua valendo; a unica linha alterada
la foi a que declarava `dimensionamento/config.py` como permitido — ver `test_caminhos_criticos`.
"""
from __future__ import annotations

import io
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts import loop_guard
from scripts.loop_guard import CLASSE_CRITICO, CLASSE_GOVERNANCA, classificar


def _classe(path: str) -> str | None:
    violacoes = classificar([path])
    return violacoes[0].classe if violacoes else None


# --------------------------------------------------------------------------------------------
# Classificacao pura
# --------------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "path",
    [
        # Nucleo do M1 (ja protegido antes).
        "src/motor_expansao/pipelines/m1/hex_enrichment.py",
        "src/motor_expansao/config.py",
        "src/motor_expansao/core/constants.py",
        "src/motor_expansao/dashboard/constants.py",
        "tests/unit/test_scoring.py",
        "data/staging/brasil_priorizados.parquet",
        "data/outputs/hexagonos_brasil_dashboard.parquet",
        "data/outputs/top_oportunidades_resumo.csv",
        # REGRESSAO — scores PARALELOS servidos em producao (o regex `*scoring*` nao casava).
        "src/motor_expansao/pipelines/calcular_colunas_mercado.py",  # flag_sam (DEC-006/DEC-007)
        "src/motor_expansao/pipelines/pop_corte.py",
        "src/motor_expansao/pipelines/gerar_carteira_acionavel.py",
        "src/motor_expansao/pipelines/gerar_plano_expansao_curto_prazo.py",
        "src/motor_expansao/pipelines/enriquecer_outputs_residual_mercado.py",
        "src/motor_expansao/dashboard/relatorio_municipal.py",  # limiares DEC-011
        # Ponto unico da renda exibida (E0): formula, fatores versionados e o VIGENTE.
        "src/motor_expansao/renda/formula.py",
        "src/motor_expansao/renda/fatores/BR/VIGENTE",
        "src/motor_expansao/renda/fatores/BR/2026-08_caged_v0.json",
        "src/motor_expansao/renda/atualizar_fatores.py",
        # Recomendacao unica (DEC-077): regua versionada, VIGENTE e o nucleo do Top 10.
        "src/motor_expansao/recomendacao/qualquer.py",
        "src/motor_expansao/recomendacao/nucleo.py",
        "src/motor_expansao/recomendacao/regra/BR/VIGENTE",
        "src/motor_expansao/recomendacao/regra/BR/2026-10_v1.json",
        "data/staging/hexagonos_mercado_mapeado.parquet",
        "data/outputs/carteira_expansao_acionavel.parquet",
        "data/outputs/plano_expansao_curto_prazo.parquet",
        # F7 — insumos/scores paralelos servidos em producao (censitario/hibrido/oferta/dominio).
        "src/motor_expansao/pipelines/calibrar_renda_setor_2022.py",
        "src/motor_expansao/pipelines/modelo_hibrido_expansao.py",
        "src/motor_expansao/pipelines/normalizar_concorrentes.py",
        "src/motor_expansao/pipelines/normalizar_unidades_ultra.py",
        "src/motor_expansao/pipelines/calcular_penetracao_ultra_hex.py",
        "src/motor_expansao/pipelines/gerar_relatorio_expansao_dominio.py",
        # F7 — premissas financeiras + lista anti-PII (`PII_COLUNAS_PROIBIDAS`) do motor de
        # viabilidade. NAO e "config.py de modulo paralelo generico": e o caminho EXATO.
        "src/motor_expansao/dimensionamento/config.py",
        # F7 — artefato enriquecido servido ao dashboard (o regex `hexagonos_brasil` nao casava).
        "data/outputs/hexagonos_dashboard_enriquecido/uf=SP/parte-0.parquet",
        # Producao / VPS / segredos / CI.
        "deploy/deploy.sh",
        "Dockerfile.web",
        "Dockerfile.api",
        "Dockerfile.loop",  # o regex antigo `^Dockerfile\.(streamlit|api)$` deixava o loop de fora
        ".dockerignore",
        "docker-compose.prod.yml",
        ".env",
        "secrets/age.enc.env",
        ".gitattributes",
        ".github/workflows/ci.yml",
        # DECISAO documentada: workflows sao CRITICO (rodam com secrets e definem os proprios
        # checks obrigatorios). CRITICO e avaliado antes de GOVERNANCA, entao guard.yml cai aqui.
        ".github/workflows/guard.yml",
        # F1 — arquivos que ARMAM o check `test` (que roda a partir do HEAD do PR).
        "pyproject.toml",  # testpaths=[] / ruff extend-exclude=["src"] => `test` verde sem rodar nada
        "constraints.txt",  # supply chain: entra na imagem de producao
        "conftest.py",
        "tests/conftest.py",  # conftest em QUALQUER nivel neutraliza a suite
        ".gitleaks.toml",
        ".gitleaksignore",
        ".trivyignore",
        # N1 — config de ferramenta na raiz tem PRECEDENCIA sobre o pyproject (ja protegido):
        # pytest.ini/tox.ini vencem [tool.pytest.ini_options], ruff.toml/.ruff.toml vencem
        # [tool.ruff], mypy.ini/.mypy.ini vencem [tool.mypy]. setup.py/setup.cfg/sitecustomize.py
        # EXECUTAM codigo no `pip install -e .` / import do job `test`. Adicionar um destes novo na
        # raiz desarma ruff/mypy/pytest sem tocar o pyproject.
        "setup.py",
        "setup.cfg",
        "pytest.ini",
        "tox.ini",
        "ruff.toml",
        ".ruff.toml",
        "mypy.ini",
        ".mypy.ini",
        "sitecustomize.py",
        # N1 — .pth injeta codigo no import do Python (em QUALQUER diretorio, nao so raiz).
        "extra.pth",
        "src/motor_expansao/injeta.pth",
        # N3 — malha IBGE VERSIONADA: insumo que define o universo de hexes e a fracao-de-terra do
        # M1 (DEC-002/003). Um "Media" auto-mergeavel que a edite move o M1 sem tocar codigo.
        "data/ibge/municipios_SP.geojson",
        "data/raw/ibge/malha_brasil.geojson",
        # N3 — lancadores do loop que LEEM o CLAUDE_CODE_OAUTH_TOKEN do .env e o injetam no container.
        "iniciar-loop.cmd",
        "scripts/iniciar_loop.ps1",
        # Banco de producao (autoriza o piloto desde 23/10/2026; autentica no P19 - DEC-067): o
        # pacote INTEIRO, inclusive modulo e migration que ainda nao existem, e os crons que o
        # operam com a senha do papel dono. Ate' aqui tudo isto saia LIMPO -> "Media" auto-merge.
        "src/motor_expansao/db/__init__.py",
        "src/motor_expansao/db/__main__.py",
        "src/motor_expansao/db/cli.py",
        "src/motor_expansao/db/eventos.py",
        "src/motor_expansao/db/postgres.py",
        "src/motor_expansao/db/rbac.py",
        "src/motor_expansao/db/senhas.py",
        "src/motor_expansao/db/sessoes.py",
        "src/motor_expansao/db/usuarios.py",
        "src/motor_expansao/db/modulo_futuro.py",
        "src/motor_expansao/db/migracoes/000-migracoes-aplicadas.sql",
        "src/motor_expansao/db/migracoes/021-migration-futura.sql",
        "src/motor_expansao/db/migracoes/manifesto.json",
        "scripts/cron/run_backup_banco.sh",
        "scripts/cron/run_expurgo_sessoes.sh",
        # F1 -- script que o job `test` executa a partir do HEAD do PR (banco de ensaio): quem o
        # controla deixa o `test` verde sem migrar nada. O diretorio inteiro, inclusive o proximo.
        "scripts/ci/banco_de_ensaio.sh",
        "scripts/ci/script_de_ci_futuro.py",
    ],
)
def test_caminhos_criticos(path: str) -> None:
    assert _classe(path) == CLASSE_CRITICO, f"deveria ser CRITICO: {path}"


@pytest.mark.parametrize(
    "path",
    [
        "scripts/loop_guard.py",  # auto-edicao do guarda
        ".claude/settings.json",
        "REVIEW.md",
        "CLAUDE.md",
        "tasks/backlog.md",
        "run-ralph-loop.sh",
        ".gitignore",
        ".github/CODEOWNERS",  # resto de .github/ (fora de workflows/) = governanca
        # F7 — camadas de PRODUCAO que calculam/exibem os numeros que o comite ve.
        "src/motor_expansao/dashboard/data.py",
        "src/motor_expansao/dashboard/utils.py",
        "src/motor_expansao/dashboard/censo_point.py",
        "src/motor_expansao/dashboard/censo_map.py",
        "src/motor_expansao/dashboard/censo_report.py",
        # DEC-070/071 — o mercado do ponto (SAM/consumo/residual nas tres superficies) e os
        # limites da area desenhada: produzem numero servido, nasceram fora da lista.
        "src/motor_expansao/dashboard/mercado_raio.py",
        "src/motor_expansao/dashboard/geometria_desenhada.py",
        # DEC-074 -- raio de 2 km / isocrona e o fator que escala as reguas absolutas.
        "src/motor_expansao/dashboard/alcance_ponto.py",
        # DEC-022 — piloto web servido em producao: backend E frontend sob governanca.
        "web/server/app.py",
        "web/src/screens/MapScreen.tsx",
        "web/package.json",
        "src/motor_expansao/api/main.py",
        "src/motor_expansao/api/maps_geocoder.py",
        "src/motor_expansao/dimensionamento/viabilidade_ponto.py",  # DEC-009
        "src/motor_expansao/lifetime/score_retencao_territorial.py",  # DEC-012 (PII na origem)
        "src/motor_expansao/demanda_revelada/ingestao.py",
        # BLK-MA-02 (D5, gate 2026-07-29) — mesmo perfil das duas acima: ingestao de fonte com PII
        # na origem, snapshots derivados persistidos e poda que APAGA disco. Alargamento de guarda.
        "src/motor_expansao/vulnerabilidade/snapshots.py",
        # N3 — governanca da esteira + config/insumo de PRODUCAO que um "Media" auto-mergeavel nao
        # deve mover sem olho humano (no ralph e AVISO; no CI exige label).
        "prompts/builder.md",
        ".codex/skills/codex-run-cycle/SKILL.md",
        "scripts/housekeeping_move_block.py",
        "data/osm_cache/bbox_ok_test.json",
        # Instrumentos de veredito sobre identidade no banco: nao escrevem, mas o veredito deles
        # decide um corte de acesso (conferidor) e aponta QUEM gerou um arquivo (rastreio).
        "scripts/conferir_usuarios_banco.py",
        "scripts/rastrear_arquivo.py",
        # Contrato da porta unica (D28): a allowlist dele e' a unica trava contra uma segunda
        # conexao, sem carimbo de auditoria, aberta em codigo que o guard ve como LIMPO.
        "tests/contracts/test_conexao_por_uma_porta_so.py",
    ],
)
def test_caminhos_governanca(path: str) -> None:
    assert _classe(path) == CLASSE_GOVERNANCA, f"deveria ser GOVERNANCA: {path}"


@pytest.mark.parametrize(
    "path",
    [
        # Trabalho comum que PRECISA seguir auto-mergeavel (Baixa/Media) — zero falso-positivo.
        # Se qualquer um destes virar violacao, o auto-merge dos blocos Baixa/Media morre.
        "tests/unit/test_foo.py",
        "tests/unit/test_relatorio_municipal.py",
        "tests/unit/test_calcular_colunas_mercado_gate.py",
        # Contraprova da regra da renda: os TESTES do modulo e o runbook seguem limpos.
        "tests/unit/test_renda_modulo.py",
        "docs/runbook_atualizacao_renda.md",
        # Contraprova da regra da recomendacao unica: os TESTES dela seguem limpos.
        "tests/unit/test_recomendacao_nucleo.py",
        "tests/unit/dimensionamento/test_huff.py",
        "tests/integration/test_streamlit_app.py",
        "docs/x.md",
        "docs/infra_producao.md",
        # Modulos do dashboard fora das listas nominais de GOVERNANCA seguem limpos
        # (DEC-022: a UI Streamlit saiu; schemas/viabilidade_charts sao motor auxiliar).
        "src/motor_expansao/dashboard/schemas.py",
        "src/motor_expansao/dashboard/viabilidade_charts.py",
        "context/handoff/20260713-000000-planner.md",
        "tasks/completed.md",
        # Guardrail que ja existia: NAO casar `config.py`/`constants.py` de modulo paralelo
        # GENERICO. O regex de CRITICO e ancorado ao caminho EXATO de `dimensionamento/config.py`,
        # entao os vizinhos abaixo seguem limpos.
        "src/motor_expansao/dimensionamento/constants.py",
        "src/motor_expansao/dimensionamento/huff.py",
        "src/motor_expansao/dimensionamento/aderencia.py",
        "src/motor_expansao/lifetime_utils.py",  # nao e o pacote `lifetime/`
        # Contraprova N1: o regex de config de raiz e ANCORADO (`^...$`) — so a raiz. Um arquivo em
        # subdiretorio ou que apenas CONTEM "setup"/"pytest"/"ruff" no nome segue LIMPO.
        "src/motor_expansao/setup_helpers.py",
        "tests/unit/test_setup.py",
        "docs/pytest.ini.md",
        # Contraprova N1 (.pth): so casa quem TERMINA em `.pth`; nome parecido segue limpo.
        "docs/pathlib.md",
        "src/motor_expansao/pathfinder.py",
        # Contraprova N3: `data/ibge` casa so o prefixo REAL da malha; doc/relatorio sobre IBGE ou
        # outro dado em `data/` (ex.: censo agregado) NAO e arrastado.
        "docs/ibge_notas.md",
        "data/reports/base_h3_brasil.md",
        # BLK-GRAPH-02: o tooling do grafo e' LIVRE no guard (o que escala o PR e' .gitattributes
        # + pyproject.toml, nao estes).
        ".mcp.json",
        ".githooks/post-commit",
        "scripts/verify_mcp_graphify.py",
        # Contraprova do banco: os TESTES dele (unidade, integracao e contrato), o extrator de
        # migrations (o que ele gera cai em `db/migracoes/`, ja' CRITICO), a doc e os vizinhos de
        # nome parecido seguem limpos -- a regra e' o diretorio `db/`, nao a palavra "db".
        "tests/unit/test_db_rbac.py",
        "tests/unit/test_db_sessoes.py",
        "tests/unit/test_migracoes.py",
        "tests/unit/test_conferir_usuarios_banco.py",
        "tests/unit/test_wrapper_cron_expurgo_sessoes.py",
        "tests/integration/test_login_ponta_a_ponta.py",
        "tests/contracts/test_compose_banco.py",
        "tests/contracts/test_ip_nao_entra_em_eventos.py",
        "tests/contracts/test_sem_credencial_morta.py",
        "scripts/extrair_migracoes.py",
        "docs/banco_deploy.md",
        "src/motor_expansao/db_utils.py",
        "src/motor_expansao/dbx/conexao.py",
        "src/motor_expansao/dashboard/db.py",
        # Contraprova do `scripts/ci/`: a regra e' o DIRETORIO, nao o prefixo "ci" no nome.
        "scripts/ci_helpers.py",
        # Os crons das OUTRAS frentes seguem LIMPOS por escopo: a regra do banco casa o NOME
        # (`banco`/`sessoes`), e estende-la a eles e' decisao propria -- esta lista a torna
        # explicita, em vez de deixa-la implicita na ausencia de um teste.
        "scripts/cron/run_alerta_borda.sh",
        "scripts/cron/run_atualizacao_crescimento.sh",
        "scripts/cron/run_growth_daily.sh",
        "scripts/cron/run_regen_mercado.sh",
        "scripts/cron/run_relatorio_acessos.sh",
        "scripts/cron/run_snapshot_agregadores.sh",
        "scripts/cron/run_snapshot_concorrentes.sh",
        "scripts/cron/run_weekly_90.sh",
    ],
)
def test_caminhos_limpos(path: str) -> None:
    assert _classe(path) is None, f"NAO deveria ser protegido (falso-positivo): {path}"


def test_config_py_de_modulo_paralelo_generico_segue_limpo() -> None:
    """O regex de CRITICO e ancorado ao caminho EXATO — nao volta a casar `config.py` generico.

    Regressao do falso-positivo historico (BLK-LOOP-02) que abortava o loop por casar qualquer
    `config.py`. So `dimensionamento/config.py` e CRITICO, e por CONTEUDO (premissas financeiras +
    `PII_COLUNAS_PROIBIDAS`), nao por se chamar `config.py`.
    """
    assert _classe("src/motor_expansao/dimensionamento/config.py") == CLASSE_CRITICO
    for generico in (
        "src/motor_expansao/demanda_revelada/config.py",  # cai em GOVERNANCA pelo PACOTE, nao pelo nome
        "src/motor_expansao/dashboard/config.py",
    ):
        assert _classe(generico) != CLASSE_CRITICO, f"nao pode ser CRITICO so por se chamar config.py: {generico}"
    assert _classe("scripts/config.py") is None
    assert _classe("fora_primeira_fase/api_postgis/config.py") is None


def test_conftest_em_qualquer_nivel_e_critico() -> None:
    """F1: um `conftest.py` (raiz ou aninhado) neutraliza a suite inteira que o check `test` roda."""
    for path in ("conftest.py", "tests/conftest.py", "tests/unit/dimensionamento/conftest.py"):
        assert _classe(path) == CLASSE_CRITICO, f"conftest deveria ser CRITICO: {path}"
    # ...mas nao pode pegar um teste comum que apenas MENCIONE conftest no nome.
    assert _classe("tests/unit/test_conftest_helpers.py") is None


def test_blk_orq_24_backlog_bloqueia_completed_libera_auto_merge() -> None:
    """BLK-ORQ-24: a invariante que faz o modo auto-merge funcionar.

    O PR de ciclo no modo auto-merge leva SO codigo + testes + o append em ``completed.md``, e
    DIFERE o stub de ``backlog.md`` para um PR de housekeeping em lote. Isso so mergeia sozinho se:

    * ``tasks/backlog.md`` for GOVERNANCA -> qualquer PR que o toque exige label humana (e onde o
      marcador ``loop-safe`` deve ser concedido sob olho humano); e
    * ``tasks/completed.md`` for LIMPO -> o append de conclusao do ciclo passa o guard sem label.

    Se estas duas classes se inverterem, o objetivo da DEC-016 (loop mergeando sozinho) quebra: ou
    o append de conclusao passa a exigir label (nada auto-mergeia), ou o backlog vira auto-editavel
    (um PR se auto-concede ``loop-safe``).
    """
    assert _classe("tasks/backlog.md") == CLASSE_GOVERNANCA
    assert _classe("tasks/completed.md") is None


def test_n1_config_de_raiz_e_ancorada() -> None:
    """N1: config de ferramenta na raiz e CRITICO, mas o regex e ANCORADO (`^...$`) a raiz."""
    for raiz in ("setup.py", "setup.cfg", "pytest.ini", "tox.ini", "ruff.toml", ".ruff.toml",
                 "mypy.ini", ".mypy.ini", "sitecustomize.py"):
        assert _classe(raiz) == CLASSE_CRITICO, f"config de raiz deveria ser CRITICO: {raiz}"
    # Fora da raiz (subdiretorio) o regex NAO casa — senao qualquer `tests/pytest.ini`/doc viraria
    # falso-positivo e mataria o auto-merge. `conftest.py` aninhado segue coberto por regra propria.
    for fora in ("tests/pytest.ini", "src/ruff.toml", "docs/setup.py.md", "tests/unit/test_setup.py"):
        assert _classe(fora) != CLASSE_CRITICO, f"config em subdir nao e casada por este regex: {fora}"


def test_n1_pth_em_qualquer_diretorio_e_critico() -> None:
    """N1: um `.pth` injeta codigo no import; casa em raiz ou aninhado, mas so quem TERMINA em .pth."""
    for pth in ("extra.pth", "src/motor_expansao/injeta.pth", "venv/lib/site-packages/x.pth"):
        assert _classe(pth) == CLASSE_CRITICO, f".pth deveria ser CRITICO: {pth}"
    for limpo in ("src/motor_expansao/pathfinder.py", "docs/pathlib.md", "data/x.pth.txt"):
        assert _classe(limpo) is None, f"nome parecido com .pth nao pode virar CRITICO: {limpo}"


def test_n3_malha_ibge_e_critico_mas_nao_arrasta_outros_data() -> None:
    """N3: a malha IBGE versionada e CRITICO; `data/ibge` casa so o prefixo real."""
    assert _classe("data/ibge/municipios_SP.geojson") == CLASSE_CRITICO
    assert _classe("data/raw/ibge/malha_brasil.geojson") == CLASSE_CRITICO
    # Nao arrasta doc sobre IBGE nem outros dados em `data/`.
    assert _classe("docs/ibge_notas.md") is None
    assert _classe("data/reports/base_h3_brasil.md") is None


def test_n3_lancadores_do_loop_sao_critico_por_token() -> None:
    """N3: os lancadores manuseiam o CLAUDE_CODE_OAUTH_TOKEN -> CRITICO (nao GOVERNANCA)."""
    assert _classe("iniciar-loop.cmd") == CLASSE_CRITICO
    assert _classe("scripts/iniciar_loop.ps1") == CLASSE_CRITICO


# --------------------------------------------------------------------------------------------
# Banco de producao (epic do banco, 2026-10-24): o banco AUTORIZA o piloto e vai AUTENTICAR
# --------------------------------------------------------------------------------------------
_RAIZ = Path(__file__).resolve().parents[2]


def _motivo(path: str) -> str:
    violacoes = classificar([path])
    return violacoes[0].motivo if violacoes else ""


@pytest.mark.parametrize(
    ("path", "classe", "trecho_do_motivo"),
    [
        # Migrations: a regra MAIS especifica vem antes da do pacote, entao o motivo diz o que e'.
        ("src/motor_expansao/db/migracoes/012-seed-rbac-real.sql", CLASSE_CRITICO, "migrations do banco"),
        ("src/motor_expansao/db/migracoes/manifesto.json", CLASSE_CRITICO, "migrations do banco"),
        # Autenticacao/autorizacao: o sucessor do `authelia/`, que ja' era CRITICO.
        ("src/motor_expansao/db/rbac.py", CLASSE_CRITICO, "autenticacao/autorizacao"),
        ("src/motor_expansao/db/usuarios.py", CLASSE_CRITICO, "autenticacao/autorizacao"),
        ("src/motor_expansao/db/senhas.py", CLASSE_CRITICO, "autenticacao/autorizacao"),
        ("src/motor_expansao/db/sessoes.py", CLASSE_CRITICO, "autenticacao/autorizacao"),
        # O resto do pacote cai na regra do diretorio: porta unica, runner como dono, eventos.
        ("src/motor_expansao/db/postgres.py", CLASSE_CRITICO, "pacote do banco"),
        ("src/motor_expansao/db/cli.py", CLASSE_CRITICO, "pacote do banco"),
        ("src/motor_expansao/db/eventos.py", CLASSE_CRITICO, "pacote do banco"),
        ("src/motor_expansao/db/__init__.py", CLASSE_CRITICO, "pacote do banco"),
        ("src/motor_expansao/db/modulo_futuro.py", CLASSE_CRITICO, "pacote do banco"),
        # Crons que operam o banco na VPS com a senha do papel dono.
        ("scripts/cron/run_backup_banco.sh", CLASSE_CRITICO, "senha do papel dono"),
        ("scripts/cron/run_expurgo_sessoes.sh", CLASSE_CRITICO, "senha do papel dono"),
        # Instrumentos de veredito: GOVERNANCA (label humana no PR; AVISO no ralph).
        ("scripts/conferir_usuarios_banco.py", CLASSE_GOVERNANCA, "veredito sobre identidade"),
        ("scripts/rastrear_arquivo.py", CLASSE_GOVERNANCA, "veredito sobre identidade"),
        # O teste que E' a regra da porta unica (D28) nao fica livre: ele e' a unica trava sobre
        # modulo LIMPO de `src/` que roda em producao. Os OUTROS contratos do banco seguem limpos
        # -- o que eles vigiam ja' passa por gate (db/ e compose CRITICO, web/server GOVERNANCA)
        # ou nao roda sozinho em producao (script avulso de `scripts/`).
        ("tests/contracts/test_conexao_por_uma_porta_so.py", CLASSE_GOVERNANCA, "porta unica do banco"),
        # O banco de ensaio do CI arma o check `test` (F1): CRITICO pelo motivo do CI, nao do banco.
        ("scripts/ci/banco_de_ensaio.sh", CLASSE_CRITICO, "job `test` executa a partir do HEAD"),
    ],
)
def test_banco_classe_e_motivo_certos(path: str, classe: str, trecho_do_motivo: str) -> None:
    """Cada caminho do banco cai na classe certa E com o motivo da sua camada.

    O motivo vai para a tabela do check `guard`: e' o que diz ao revisor POR QUE o PR pede label.
    Uma regra generica antes da especifica reportaria a migration como "pacote do banco".
    """
    assert _classe(path) == classe, path
    assert trecho_do_motivo in _motivo(path), (path, _motivo(path))


def test_todo_arquivo_real_do_pacote_db_e_critico() -> None:
    """Nenhum arquivo REAL de `src/motor_expansao/db/` escapa -- nem o que nascer amanha.

    A regra do pacote e' o diretorio inteiro, e nao uma lista: foi por lista que as regras do
    dashboard deixaram passar `mercado_raio`/`geometria_desenhada`/`alcance_ponto` (DEC-070/071/
    074), que nasceram depois dela. Este teste anda no disco, entao uma regra que um dia encolha
    para lista de nomes falha aqui no primeiro modulo que ficar de fora.
    """
    pacote = _RAIZ / "src" / "motor_expansao" / "db"
    arquivos = sorted(
        p.relative_to(_RAIZ).as_posix()
        for p in pacote.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    )
    nomes = {Path(a).name for a in arquivos}
    # Contra o teste vazio: o pacote tem de existir e trazer os modulos que motivaram a regra.
    assert {"rbac.py", "sessoes.py", "senhas.py", "usuarios.py", "postgres.py", "cli.py"} <= nomes
    assert any(a.endswith(".sql") for a in arquivos), "nenhuma migration encontrada no disco"
    fora = [a for a in arquivos if _classe(a) != CLASSE_CRITICO]
    assert not fora, f"arquivo do banco fora do CRITICO: {fora}"


def test_banco_vizinhos_nao_sao_arrastados() -> None:
    """A regra e' o DIRETORIO `db/` e scripts NOMEADOS -- nao a palavra "db" ou "banco"."""
    for limpo in (
        "src/motor_expansao/db_utils.py",  # sem a barra, nao e' o pacote
        "src/motor_expansao/dbx/conexao.py",
        "src/motor_expansao/dashboard/db.py",
        "tests/unit/test_db_conexao.py",  # os testes do banco seguem limpos (o gate deles e' o CI)
        "tests/unit/test_conferir_usuarios_banco.py",
        "scripts/extrair_migracoes.py",  # gera arquivo em `db/migracoes/`, que ja' e' CRITICO
        "docs/banco_conexao.md",
    ):
        assert _classe(limpo) is None, f"vizinho do banco virou protegido (falso-positivo): {limpo}"
    # O piloto web que CONSOME o banco segue na classe que ja' tinha: nem subiu, nem caiu.
    assert _classe("web/server/acesso.py") == CLASSE_GOVERNANCA


def test_cron_do_banco_e_reconhecido_pelo_nome_nao_pela_lista_dos_dois_de_hoje() -> None:
    """A regra dos crons casa o NOME (`banco`/`sessoes`), e nao a lista dos dois que existem hoje.

    O proximo cron do banco (restore, copia off-box, um ajudante que os wrappers carreguem) le a
    mesma senha do papel dono no `.env` de producao. Numa regra por lista ele nasceria LIMPO --
    a licao das regras que "nasceram fora da lista" (DEC-070/071/074), a mesma que fez o pacote
    `db/` entrar inteiro. Os crons das OUTRAS frentes seguem LIMPOS (ver `test_caminhos_limpos`).
    """
    for futuro in (
        "scripts/cron/run_restore_banco.sh",
        "scripts/cron/run_backup_banco_offbox.sh",
        "scripts/cron/run_expurgo_sessoes_vencidas.sh",
        "scripts/cron/lib_banco.sh",
        "scripts/cron/banco/comum.sh",
    ):
        assert _classe(futuro) == CLASSE_CRITICO, futuro
        assert "senha do papel dono" in _motivo(futuro), (futuro, _motivo(futuro))
    # Contra a regra que encolhe de volta para a lista: os dois de hoje existem no disco e
    # seguem cobertos pelo MESMO motivo.
    cron = _RAIZ / "scripts" / "cron"
    assert (cron / "run_backup_banco.sh").is_file()
    assert (cron / "run_expurgo_sessoes.sh").is_file()
    # A regra e' o diretorio dos crons instalados na VPS: doc com o mesmo nome segue limpa.
    assert _classe("docs/cron/run_backup_banco.md") is None


def test_todos_os_motivos_sao_ascii_obs1() -> None:
    """OBS-1: nenhum `motivo` pode carregar caractere fora de ASCII (quebra em locale nao-UTF-8)."""
    for _rx, motivo in [*loop_guard._DENY_CRITICO, *loop_guard._DENY_GOVERNANCA]:
        assert motivo.isascii(), f"motivo com caractere nao-ASCII: {motivo!r}"


def test_classificar_e_puro_ordenado_e_sem_duplicata() -> None:
    violacoes = classificar(
        [
            "tasks/backlog.md",
            "src/motor_expansao/config.py",
            "src/motor_expansao/config.py",  # duplicata
            "",  # linha vazia ignorada
            "docs/x.md",  # limpo
        ]
    )
    assert [(v.path, v.classe) for v in violacoes] == [
        ("src/motor_expansao/config.py", CLASSE_CRITICO),
        ("tasks/backlog.md", CLASSE_GOVERNANCA),
    ]
    assert all(v.motivo for v in violacoes), "toda violacao carrega motivo legivel"


def test_critico_tem_precedencia_sobre_governanca() -> None:
    # `.github/workflows/guard.yml` casa as duas listas; CRITICO vence e gera UMA so violacao.
    violacoes = classificar([".github/workflows/guard.yml"])
    assert len(violacoes) == 1
    assert violacoes[0].classe == CLASSE_CRITICO


# --------------------------------------------------------------------------------------------
# Contrato de CLI: --stdin / --json / exclusividade
# --------------------------------------------------------------------------------------------
def _run_stdin(monkeypatch: pytest.MonkeyPatch, paths: list[str], *, json_out: bool) -> int:
    monkeypatch.setattr("sys.stdin", io.StringIO("\n".join(paths) + "\n"))
    argv = ["--stdin"] + (["--json"] if json_out else [])
    return loop_guard.main(argv)


def test_stdin_limpo_exit_zero(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    rc = _run_stdin(monkeypatch, ["docs/x.md", "tests/unit/test_foo.py"], json_out=False)
    assert rc == 0
    assert "GUARD OK" in capsys.readouterr().out


def test_stdin_json_limpo(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    rc = _run_stdin(monkeypatch, ["docs/x.md", "src/motor_expansao/dashboard/components.py"], json_out=True)
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload == {"limpo": True, "violacoes": []}


def test_stdin_json_com_violacoes(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = _run_stdin(
        monkeypatch,
        ["docs/x.md", "src/motor_expansao/pipelines/calcular_colunas_mercado.py", "CLAUDE.md"],
        json_out=True,
    )
    payload = json.loads(capsys.readouterr().out)
    assert rc == 1, "no CI, tocar caminho protegido (qualquer classe) e exit 1"
    assert payload["limpo"] is False
    assert [(v["path"], v["classe"]) for v in payload["violacoes"]] == [
        ("CLAUDE.md", CLASSE_GOVERNANCA),
        ("src/motor_expansao/pipelines/calcular_colunas_mercado.py", CLASSE_CRITICO),
    ]
    assert all(v["motivo"] for v in payload["violacoes"])


def test_stdin_governanca_sozinha_falha_no_ci(monkeypatch: pytest.MonkeyPatch) -> None:
    # No CI, mexer so em governanca (ex.: reescrever o proprio guard) ja exige gate humano.
    assert _run_stdin(monkeypatch, ["scripts/loop_guard.py"], json_out=False) == 1


def test_stdin_pr_que_desarma_o_check_test_e_pego(monkeypatch: pytest.MonkeyPatch) -> None:
    """F1 end-to-end: o PR "inocente" que so mexe em teste + pyproject NAO passa mais.

    Cenario do red team: o PR poe `testpaths=[]` no `pyproject.toml`, o job `test` (que roda a
    partir do HEAD do PR) fica VERDE sem executar nada, e o resto do diff parece trivial. O guard
    roda a partir da BASE e e o unico que enxerga isso.
    """
    assert _run_stdin(monkeypatch, ["tests/unit/test_foo.py", "pyproject.toml"], json_out=False) == 1
    assert _run_stdin(monkeypatch, ["docs/x.md", "conftest.py"], json_out=False) == 1
    assert _run_stdin(monkeypatch, ["docs/x.md", ".gitleaksignore"], json_out=False) == 1
    assert _run_stdin(monkeypatch, ["docs/x.md", "constraints.txt"], json_out=False) == 1
    # O banco de ensaio do CI: `exit 0` no `verificar` = `test` verde sem migration nenhuma.
    assert _run_stdin(monkeypatch, ["docs/x.md", "scripts/ci/banco_de_ensaio.sh"], json_out=False) == 1


def test_stdin_bloco_media_nao_muda_numero_de_producao_sem_gate(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """F7 end-to-end: um "Media" auto-mergeavel nao altera silenciosamente o dashboard/API."""
    rc = _run_stdin(
        monkeypatch,
        ["src/motor_expansao/dashboard/data.py", "src/motor_expansao/pipelines/modelo_hibrido_expansao.py"],
        json_out=True,
    )
    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert [(v["path"], v["classe"]) for v in payload["violacoes"]] == [
        ("src/motor_expansao/dashboard/data.py", CLASSE_GOVERNANCA),
        ("src/motor_expansao/pipelines/modelo_hibrido_expansao.py", CLASSE_CRITICO),
    ]


def test_stdin_pr_de_display_puro_segue_auto_mergeavel(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Contraprova do F7: ampliar a cobertura NAO pode matar o auto-merge do trabalho comum."""
    rc = _run_stdin(
        monkeypatch,
        [
            "src/motor_expansao/dashboard/schemas.py",
            "src/motor_expansao/dashboard/viabilidade_charts.py",
            "tests/unit/test_entorno_ponto_motor.py",
            "docs/relatorio_pontual_censitario.md",
        ],
        json_out=True,
    )
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload == {"limpo": True, "violacoes": []}


def test_stdin_bloco_media_que_mexe_so_no_banco_nao_auto_mergeia(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """O furo que motivou a regra: um "Media" que toca SO o banco (+ teste) passava LIMPO.

    Sem violacao o `guard` fica verde e, pela DEC-016, o auto-merge fecha o PR sozinho -- com o
    banco autorizando o piloto em producao. Agora e' exit 1 e so' passa com `critica-aprovada`.
    """
    rc = _run_stdin(
        monkeypatch,
        ["src/motor_expansao/db/rbac.py", "tests/unit/test_db_rbac.py"],
        json_out=True,
    )
    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert payload["limpo"] is False
    assert [(v["path"], v["classe"]) for v in payload["violacoes"]] == [
        ("src/motor_expansao/db/rbac.py", CLASSE_CRITICO),
    ]


def test_stdin_replay_dos_prs_do_banco_que_o_guard_via_limpo(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Os diffs REAIS do #447 e do #455, reclassificados pela regua nova.

    O #447 corrigiu o `conferir` e o `privilegios` do `cli.py` (aprovavam bancos quebrados) e
    mexeu no hash de senha; o guard antigo so' o marcou pelo `.gitignore`, que aqui fica de fora.
    O #455 criou o conferidor do corte e saiu inteiro LIMPO.
    """
    rc = _run_stdin(
        monkeypatch,
        [
            "src/motor_expansao/db/cli.py",
            "src/motor_expansao/db/postgres.py",
            "src/motor_expansao/db/senhas.py",
            "tests/unit/test_db_cli.py",
            "tests/unit/test_db_senhas.py",
        ],
        json_out=True,
    )
    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert [(v["path"], v["classe"]) for v in payload["violacoes"]] == [
        ("src/motor_expansao/db/cli.py", CLASSE_CRITICO),
        ("src/motor_expansao/db/postgres.py", CLASSE_CRITICO),
        ("src/motor_expansao/db/senhas.py", CLASSE_CRITICO),
    ]

    rc = _run_stdin(
        monkeypatch,
        [
            "docs/banco_deploy.md",
            "scripts/conferir_usuarios_banco.py",
            "tests/unit/test_conferir_usuarios_banco.py",
        ],
        json_out=True,
    )
    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert [(v["path"], v["classe"]) for v in payload["violacoes"]] == [
        ("scripts/conferir_usuarios_banco.py", CLASSE_GOVERNANCA),
    ]


def test_stdin_texto_mostra_classe_e_motivo(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = _run_stdin(monkeypatch, ["src/motor_expansao/config.py"], json_out=False)
    err = capsys.readouterr().err
    assert rc == 1
    assert "[CRITICO]" in err
    assert "src/motor_expansao/config.py" in err
    assert "config.py raiz" in err


def test_base_e_stdin_sao_mutuamente_exclusivos() -> None:
    with pytest.raises(SystemExit) as exc:
        loop_guard.main(["--base", "HEAD~1", "--stdin"])
    assert exc.value.code == 2


def test_fonte_obrigatoria() -> None:
    with pytest.raises(SystemExit) as exc:
        loop_guard.main([])
    assert exc.value.code == 2


# --------------------------------------------------------------------------------------------
# Modo --base (ralph): comportamento preservado — so CRITICO aborta o loop
# --------------------------------------------------------------------------------------------
def test_base_aborta_em_critico(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        loop_guard, "_changed_paths", lambda base: {"src/motor_expansao/pipelines/m1/hex_enrichment.py"}
    )
    assert loop_guard.main(["--base", "abc1234"]) == 1


def test_base_nao_aborta_em_governanca(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # O proprio loop faz housekeeping em backlog/CLAUDE.md a cada ciclo: GOVERNANCA e AVISO, nao
    # abort (o CI e quem exige o label humano para essas mudancas).
    monkeypatch.setattr(loop_guard, "_changed_paths", lambda base: {"tasks/backlog.md", "CLAUDE.md"})
    rc = loop_guard.main(["--base", "abc1234"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "GUARD AVISO" in captured.err
    assert "GUARD OK" in captured.out


def test_base_limpo(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(loop_guard, "_changed_paths", lambda base: {"docs/x.md"})
    rc = loop_guard.main(["--base", "abc1234"])
    assert rc == 0
    assert "GUARD OK: 1 caminho(s) alterado(s), nenhum proibido." in capsys.readouterr().out


def test_base_aborta_o_loop_ao_desarmar_a_suite(monkeypatch: pytest.MonkeyPatch) -> None:
    """F1 no ralph: os novos CRITICO tambem abortam o loop (nao so o CI)."""
    for path in (
        "pyproject.toml",
        "conftest.py",
        "constraints.txt",
        "Dockerfile.loop",
        "scripts/ci/banco_de_ensaio.sh",
    ):
        monkeypatch.setattr(loop_guard, "_changed_paths", lambda base, _p=path: {_p})
        assert loop_guard.main(["--base", "abc1234"]) == 1, f"loop deveria abortar em {path}"


def test_base_so_avisa_em_camada_de_producao_governanca(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """F7 no ralph: os novos GOVERNANCA sao AVISO, nao abort — o gate deles e o label no PR."""
    monkeypatch.setattr(
        loop_guard,
        "_changed_paths",
        lambda base: {"src/motor_expansao/dashboard/data.py", "src/motor_expansao/api/main.py"},
    )
    rc = loop_guard.main(["--base", "abc1234"])
    captured = capsys.readouterr()
    assert rc == 0, "GOVERNANCA nao pode matar o loop (contrato --base preservado)"
    assert "GUARD AVISO" in captured.err
    assert "GUARD OK" in captured.out


def test_base_aborta_o_loop_ao_tocar_o_banco(monkeypatch: pytest.MonkeyPatch) -> None:
    """Banco no ralph: CRITICO ABORTA o loop -- loop-safe nao persiste PII nem toca segredo."""
    for path in (
        "src/motor_expansao/db/sessoes.py",
        "src/motor_expansao/db/migracoes/021-migration-futura.sql",
        "scripts/cron/run_backup_banco.sh",
    ):
        monkeypatch.setattr(loop_guard, "_changed_paths", lambda base, _p=path: {_p})
        assert loop_guard.main(["--base", "abc1234"]) == 1, f"loop deveria abortar em {path}"


def test_base_so_avisa_nos_instrumentos_de_veredito_do_banco(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Os instrumentos de veredito sao GOVERNANCA: AVISO no ralph, label humana no PR."""
    monkeypatch.setattr(
        loop_guard, "_changed_paths", lambda base: {"scripts/conferir_usuarios_banco.py"}
    )
    rc = loop_guard.main(["--base", "abc1234"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "GUARD AVISO" in captured.err
    assert "scripts/conferir_usuarios_banco.py" in captured.err


# --------------------------------------------------------------------------------------------
# N10 — lista de caminhos truncada pela API do GitHub: fail-closed no --stdin (CI)
# --------------------------------------------------------------------------------------------
def test_n10_stdin_lista_truncada_reprova_fail_closed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """No teto (>= 3000) o guard REPROVA sem classificar — todos os caminhos aqui sao LIMPOS.

    `gh pr diff --name-only` pode truncar o diff da API num PR gigante; um caminho protegido alem
    do teto ficaria invisivel e o guard reportaria 'limpo'. Fail-closed impede esse buraco.
    """
    paths = [f"docs/f{i}.md" for i in range(loop_guard._STDIN_TRUNCATION_LIMIT)]
    rc = _run_stdin(monkeypatch, paths, json_out=True)
    payload = json.loads(capsys.readouterr().out)
    assert rc == 1, "lista no teto e reprovada mesmo com todos os caminhos limpos"
    assert payload["limpo"] is False
    assert len(payload["violacoes"]) == 1
    viol = payload["violacoes"][0]
    assert viol["path"] == loop_guard._TRUNCATION_SENTINEL
    assert viol["classe"] == CLASSE_CRITICO
    assert "trunc" in viol["motivo"].lower()


def test_n10_stdin_texto_truncado_reprova(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    paths = [f"docs/f{i}.md" for i in range(loop_guard._STDIN_TRUNCATION_LIMIT + 500)]
    rc = _run_stdin(monkeypatch, paths, json_out=False)
    assert rc == 1
    assert "GUARD" in capsys.readouterr().err


def test_n10_stdin_abaixo_do_teto_segue_normal(monkeypatch: pytest.MonkeyPatch) -> None:
    """Um caminho a menos que o teto NAO dispara o fail-closed (segue classificando normalmente)."""
    paths = [f"docs/f{i}.md" for i in range(loop_guard._STDIN_TRUNCATION_LIMIT - 1)]
    assert _run_stdin(monkeypatch, paths, json_out=False) == 0, "abaixo do teto e limpo => exit 0"


def test_n10_base_nao_sofre_truncamento(monkeypatch: pytest.MonkeyPatch) -> None:
    """O fail-closed e SO do --stdin (CI). O --base do ralph le o git local, sem truncamento de API."""
    muitos = {f"docs/f{i}.md" for i in range(loop_guard._STDIN_TRUNCATION_LIMIT + 100)}
    monkeypatch.setattr(loop_guard, "_changed_paths", lambda base: muitos)
    assert loop_guard.main(["--base", "abc1234"]) == 0, "--base nao aplica o teto de truncamento"


# --------------------------------------------------------------------------------------------
# OBS-1 — saida sempre ASCII (nao quebra em runner com locale nao-UTF-8)
# --------------------------------------------------------------------------------------------
def test_obs1_json_de_violacao_e_ascii_puro(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = _run_stdin(monkeypatch, ["src/motor_expansao/config.py", "CLAUDE.md"], json_out=True)
    out = capsys.readouterr().out
    assert rc == 1
    out.encode("ascii")  # nao levanta UnicodeEncodeError
    assert out.isascii(), "json.dumps(..., ensure_ascii=True) deve produzir saida 100% ASCII"
    payload = json.loads(out)
    assert payload["limpo"] is False


def test_obs1_json_de_truncamento_e_ascii_puro(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = [f"docs/f{i}.md" for i in range(loop_guard._STDIN_TRUNCATION_LIMIT)]
    _run_stdin(monkeypatch, paths, json_out=True)
    out = capsys.readouterr().out
    assert out.isascii()


# --------------------------------------------------------------------------------------------
# Citacao do git: caminho com acento chega ENTRE ASPAS e com octal, nos DOIS modos
# --------------------------------------------------------------------------------------------
# Medido no #136: `gh pr diff --name-only` (o comando do job `guard`) lista um arquivo com acento
# como `"Motor de Expans\303\243o - Refer\303\252ncia (standalone).html"`, e o `git diff
# --name-only` do ralph faz o mesmo (`core.quotePath`, ligado por padrao). Sem desfazer a
# citacao, NENHUMA regra ancorada casava -- a do banco inclusive.
@pytest.mark.parametrize(
    ("citado", "desfeito", "classe"),
    [
        ('"src/motor_expansao/db/sess\\303\\243o.py"', "src/motor_expansao/db/sessão.py", CLASSE_CRITICO),
        (
            '"src/motor_expansao/db/migracoes/021-sess\\303\\243o.sql"',
            "src/motor_expansao/db/migracoes/021-sessão.sql",
            CLASSE_CRITICO,
        ),
        ('"scripts/ci/ensaio_\\303\\251.sh"', "scripts/ci/ensaio_é.sh", CLASSE_CRITICO),
        ('"scripts/cron/run_restaura\\303\\247\\303\\243o_banco.sh"', "scripts/cron/run_restauração_banco.sh", CLASSE_CRITICO),
        # F1 pela porta dos fundos: `conftest.py` numa pasta com acento neutraliza a suite.
        ('"tests/integra\\303\\247\\303\\243o/conftest.py"', "tests/integração/conftest.py", CLASSE_CRITICO),
        ('"src/motor_expansao/pipelines/m1/a\\303\\247\\303\\243o.py"', "src/motor_expansao/pipelines/m1/ação.py", CLASSE_CRITICO),
        ('"web/src/screens/Configura\\303\\247\\303\\265es.tsx"', "web/src/screens/Configurações.tsx", CLASSE_GOVERNANCA),
        # Aspa e barra invertida no nome tambem saem com escape (`\"` e `\\`).
        ('"src/motor_expansao/db/a\\"b\\\\c.py"', 'src/motor_expansao/db/a"b\\c.py', CLASSE_CRITICO),
        # O caso REAL do #136: desfeito, segue LIMPO -- a correcao nao cria falso-positivo.
        (
            '"Motor de Expans\\303\\243o - Refer\\303\\252ncia (standalone).html"',
            "Motor de Expansão - Referência (standalone).html",
            None,
        ),
    ],
)
def test_caminho_citado_pelo_git_e_desfeito_antes_de_classificar(
    citado: str, desfeito: str, classe: str | None
) -> None:
    assert loop_guard._desfazer_citacao_do_git(citado) == desfeito
    violacoes = classificar([citado])
    if classe is None:
        assert violacoes == [], violacoes
    else:
        # A violacao carrega o caminho DESFEITO: e' ele que o revisor le na tabela do CI.
        assert [(v.path, v.classe) for v in violacoes] == [(desfeito, classe)]


def test_citacao_fora_do_padrao_do_git_erra_para_o_lado_de_pegar() -> None:
    """Escape que o git nao produz: sai so' a aspa, e a regra ancorada casa o esqueleto ASCII."""
    assert (
        loop_guard._desfazer_citacao_do_git('"src/motor_expansao/db/x\\777.py"')
        == "src/motor_expansao/db/x\\777.py"
    )
    for estranho in (
        '"src/motor_expansao/db/x\\777.py"',  # octal acima de 377
        '"src/motor_expansao/db/x\\q.py"',  # escape que nao existe
        '"src/motor_expansao/db/x\\30.py"',  # octal incompleto
        '"src/motor_expansao/db/x\\"',  # barra no fim, sem o que escapar
    ):
        assert _classe(estranho) == CLASSE_CRITICO, estranho
    # Sem aspa nas DUAS pontas nao ha' citacao: o caminho volta intacto, byte a byte.
    for cru in ("src/motor_expansao/db/rbac.py", '"src/x.py', 'src/x.py"', '"', ""):
        assert loop_guard._desfazer_citacao_do_git(cru) == cru


def test_stdin_caminho_com_acento_no_formato_do_gh_nao_escapa(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """O furo ponta a ponta no modo do CI: antes da correcao, este payload saia `limpo: true`."""
    rc = _run_stdin(
        monkeypatch,
        ['"src/motor_expansao/db/sess\\303\\243o.py"', "tests/unit/test_db_sessoes.py"],
        json_out=True,
    )
    out = capsys.readouterr().out
    assert rc == 1
    assert out.isascii(), "o JSON segue ASCII (ensure_ascii) mesmo com o caminho desfeito"
    payload = json.loads(out)
    assert payload["limpo"] is False
    assert [(v["path"], v["classe"]) for v in payload["violacoes"]] == [
        ("src/motor_expansao/db/sessão.py", CLASSE_CRITICO),
    ]


@pytest.mark.skipif(shutil.which("git") is None, reason="precisa de git")
def test_base_caminho_com_acento_no_git_de_verdade_aborta_o_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """O mesmo furo no ralph, com o `git diff --name-only` DE VERDADE, e nao um monkeypatch."""

    def git(*args: str) -> str:
        # `stdin=DEVNULL`: no Windows, herdar o stdin que o pytest redireciona falha de vez em
        # quando ao duplicar o handle (WinError 50/6) -- ruido do ambiente, nao do guard.
        proc = subprocess.run(
            ["git", *args],
            cwd=tmp_path,
            check=True,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
        )
        return proc.stdout.strip()

    git("init", "-q", ".")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    git("config", "core.autocrlf", "false")
    git("config", "core.quotePath", "true")  # o padrao do git, fixado contra config global
    (tmp_path / "LEIA-ME.md").write_bytes(b"base\n")
    git("add", "-A")
    git("commit", "-qm", "base")
    base = git("rev-parse", "HEAD")
    modulo = tmp_path / "src" / "motor_expansao" / "db" / "sessão.py"
    modulo.parent.mkdir(parents=True)
    modulo.write_bytes(b"x = 1\n")
    git("add", "-A")
    git("commit", "-qm", "modulo do banco com acento no nome")
    # Pre-condicao: o git REALMENTE cita o caminho -- senao este teste nao mede o furo.
    assert git("diff", "--name-only", f"{base}..HEAD") == '"src/motor_expansao/db/sess\\303\\243o.py"'

    monkeypatch.chdir(tmp_path)
    assert loop_guard.main(["--base", base]) == 1
    err = capsys.readouterr().err
    assert "[CRITICO] src/motor_expansao/db/sessão.py" in err
