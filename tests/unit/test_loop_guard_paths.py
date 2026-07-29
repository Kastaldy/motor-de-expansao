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
* o contrato de saida dos modos `--stdin` e `--json` consumidos pelo job do CI.

O arquivo legado `test_loop_guard.py` (matriz do ralph) continua valendo; a unica linha alterada
la foi a que declarava `dimensionamento/config.py` como permitido — ver `test_caminhos_criticos`.
"""
from __future__ import annotations

import io
import json

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
        "Dockerfile.streamlit",
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
        "streamlit_app.py",
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
        ".streamlit/config.toml",
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
        "tests/unit/dimensionamento/test_huff.py",
        "tests/integration/test_streamlit_app.py",
        "docs/x.md",
        "docs/infra_producao.md",
        # DISPLAY PURO do dashboard (cor, layout, widget) — de proposito FORA da GOVERNANCA.
        "src/motor_expansao/dashboard/components.py",
        "src/motor_expansao/dashboard/pages.py",
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
            "src/motor_expansao/dashboard/components.py",
            "src/motor_expansao/dashboard/pages.py",
            "tests/unit/test_streamlit_app.py",
            "docs/streamlit_dashboard_m1.md",
        ],
        json_out=True,
    )
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload == {"limpo": True, "violacoes": []}


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
    for path in ("pyproject.toml", "conftest.py", "constraints.txt", "Dockerfile.loop"):
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
