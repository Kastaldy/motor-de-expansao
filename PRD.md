# PRD - Guia Operacional para Agentes de IA
**Projeto:** Motor de expansao - Ultra Academia
**Ultima atualizacao:** 2026-05-14
**Ciclo ativo:** Handoff, refatoracao segura e preparacao VPS fechados

## Instrucoes obrigatorias
1. Ler `CLAUDE.md` antes de qualquer acao.
2. Tratar `CLAUDE.md`, `config.py` e este PRD como fontes de verdade operacional.
3. Executar apenas o proximo bloco cujo cabecalho esteja com `[ ]`.
4. Antes de editar, ler os arquivos reais envolvidos e rodar `git status --short`.
5. Nao reverter nem sobrescrever mudancas existentes sem aprovacao explicita.
6. Atualizar `CLAUDE.md` e `PRD.md` se mudar regra, target, semantica de coluna, fluxo ou decisao relevante.
7. Se houver ambiguidade entre codigo e documentacao, corrigir primeiro a documentacao e depois o codigo.
8. Nao encerrar bloco sem editar arquivo, registrar observacoes e rodar validacao minima.
9. Tentar manter `CLAUDE.md` e `PRD.md` com no maximo `200` linhas.
10. Quando um ciclo fechar, consolidar o historico em `Estado atual` e substituir blocos antigos pelo backlog ativo.

## Estado atual
- Ciclo de handoff/deploy e refatoracao segura concluido em 2026-05-14.
- Repositorio preparado para equipe: Streamlit offline, Docker de producao e docs de VPS mantidos.
- M1 oficial preservado: `score_priorizacao`, `hex_score_estrutural`, pesos `renda=0.40` e `pop=0.60` nao foram alterados.
- Artefatos oficiais recalculados em 2026-05-12 seguem como base vigente; validacao final desta fase rodou contra os arquivos locais existentes.
- Branch historico `codex-dashboard-m1-streamlit` permanece apenas como historico; mudancas anteriores foram promovidas para `main` em 2026-05-14.
- Estrutura nova: pacote interno em `src/motor_expansao/` com `dashboard`, `core`, `data` e `pipelines/m1`.
- Entrypoints legados preservados na raiz: `streamlit_app.py`, `base_h3_brasil.py`, `hex_enrichment.py`, `fase1_bi_exports.py`.
- Arquivos fora do deploy inicial foram concentrados em `fora_primeira_fase/`: API/PostGIS, M2/M3, pesquisas, Power BI e testes associados.
- Testes reorganizados em `tests/unit/`, `tests/integration/` e `tests/contracts/`; coleta oficial em `pyproject.toml`.
- CI rapido aponta para os novos caminhos de testes.
- Diretorios temporarios antigos em `fixtures/` seguem com alguns avisos de permissao no `git status`; nao foram removidos sem aprovacao.

## Artefatos minimos do dashboard
Manter em `data/outputs/` no ambiente da equipe ou montados como volume na VPS:

| arquivo | uso |
| --- | --- |
| `hexagonos_brasil_dashboard.parquet` | base oficial M1, KPIs, ranking e mapa executivo |
| `oportunidades_expansao_hibrido.parquet` | enriquecimento hibrido/censitario e filtros combinados |
| `carteira_expansao_acionavel.parquet` | aba de carteira operacional |
| `plano_expansao_curto_prazo.parquet` | aba de plano curto prazo |

Validar com:

```bash
python scripts/check_artifacts.py
```

## Comandos de referencia

Setup local:
```bash
python -m pip install -e ".[dev]"
copy .env.example .env
python -m streamlit run streamlit_app.py
```

Suite rapida:
```bash
python -m pytest -q tests/integration/test_streamlit_app.py tests/integration/test_carteira_plano_nacional.py
python -c "import streamlit_app; print('ok')"
```

Suite M1:
```bash
python -m pytest -q tests/integration/test_base_h3_brasil.py tests/integration/test_hex_enrichment_brasil.py tests/integration/test_fase1_bi_exports.py tests/contracts/test_fontes_gratuitas.py
```

Suite completa:
```bash
python -m pytest -q
```

Deploy VPS:
```bash
python scripts/check_artifacts.py
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
curl -fsS http://127.0.0.1:8501/_stcore/health
```

Recalculo analitico M1, fora do deploy Streamlit inicial:
```bash
python base_h3_brasil.py
python hex_enrichment.py --brasil
python fase1_bi_exports.py
```

## Docs de referencia
- `README.md`: quickstart, testes, deploy e mapa de docs.
- `docs/handoff_repositorio.md`: contrato de handoff e checklist para a equipe.
- `docs/artefatos_dados.md`: manifesto de dados e politica de versionamento.
- `docs/deploy_vps_streamlit.md`: runbook Streamlit/Docker para VPS.
- `docs/streamlit_dashboard_m1.md`: governanca e uso do dashboard.
- `docs/modelo_mercado_hexagonos.md`: contrato tecnico da camada de mercado.

## Blocos concluidos

### Bloco 1 - Diagnostico e baseline [x]
**Concluido:** 2026-05-14
- Inventario do repo, modulos, imports, monolitos e artefatos sensiveis.
- Validacao: suite rapida e import do Streamlit passaram.

### Bloco 2 - Higiene segura do repositorio [x]
**Concluido:** 2026-05-14
- `.gitignore` atualizado para temporarios; `ci.yml` raiz e `setup.py` legados removidos.
- Validacao: `scripts/check_artifacts.py` e suite rapida passaram.

### Bloco 3 - Pacote interno com entrypoints preservados [x]
**Concluido:** 2026-05-14
- Criado `src/motor_expansao/` com subpacotes minimos e teste de import.
- Validacao: imports e 18 testes passando.

### Bloco 4 - Extracao incremental do dashboard [x]
**Concluido:** 2026-05-14
- Extraidos `dashboard/data.py`, `dashboard/components.py` e `dashboard/pages.py`; `streamlit_app.py` segue entrypoint.
- Validacao: 22 testes passando e import ok.

### Bloco 5 - Isolamento das regras puras do M1 [x]
**Concluido:** 2026-05-14
- Criados `core/constants.py` e `core/scoring.py`; `hex_enrichment.py` preservou API legada.
- Validacao: 43 testes M1 passando; import ok.

### Bloco 6 - Pipelines, testes e handoff final [x]
**Objetivo:** organizar pipelines/testes e fechar a refatoracao com validacao operacional.
**Concluido:** 2026-05-14

**Checklist:**
- [x] Criar ou consolidar modulos em `src/motor_expansao/pipelines/m1/` com wrappers legados na raiz.
- [x] Mover testes para `tests/unit/`, `tests/integration/` e `tests/contracts/` em lotes pequenos, sem apagar cenarios.
- [x] Atualizar `pyproject.toml`, README, CI e docs somente com comandos reais.
- [x] Rodar `scripts/check_artifacts.py`, suite rapida, suite M1, suite completa e import smoke.
- [x] Registrar conclusao, validacoes e riscos residuais neste PRD.

**Observacoes (2026-05-14):**
- `base_h3_brasil.py`, `hex_enrichment.py` e `fase1_bi_exports.py` da raiz agora sao wrappers; a implementacao esta em `src/motor_expansao/pipelines/m1/`.
- `hex_enrichment` ganhou `main()` explicito e usa o export BI empacotado.
- `tests/` foi reorganizado por categoria; `pyproject.toml` define `testpaths = ["tests"]` e `pythonpath = [".", "src"]`.
- `conftest.py` usa `tmp_path` local em `tmp_codex_runtime/manual_pytest` para evitar falhas de permissao no temp do Windows.
- `fora_primeira_fase/m2_m3_imobiliario/score_consolidado.py` recebeu compatibilidade H3 v3/v4, fallback numerico para `NaN`, deduplicacao de `hex_id` antes de merge e preservacao de `status` no output.
- Contratos de mercado foram ajustados para validar cobertura e consistencia interna sem exigir igualdade entre staging de mercado antigo e output hibrido recalculado.
- Teste de contrato do M1 foi alinhado a `M1_POP_MINIMA_PROXY=1`: hex sem populacao fica fora dos percentis e com score zero.

**Validacao final:**
```bash
python scripts/check_artifacts.py
python -m pytest -q
python -c "import streamlit_app; import base_h3_brasil; import hex_enrichment; import fase1_bi_exports; print('ok')"
```
Resultado: artefatos criticos e staging opcionais presentes; `215 passed, 4 warnings`; import ok. Warnings restantes: GeoPandas alerta CRS geografico em testes sinteticos da Fase A.

## Backlog do proximo ciclo
- Hardening operacional da VPS: HTTPS/proxy reverso, autenticacao ou VPN, monitoramento de uptime.
- Limpeza assistida dos diretorios temporarios antigos com permissao negada em `fixtures/`.
- Avaliar se camada de mercado por hexagono deve ser regenerada apos o recalculo M1 de 2026-05-12.
