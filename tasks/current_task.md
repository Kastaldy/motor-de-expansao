# Current Task

## Bloco atual

ID: BLK-DIM-00
Nome: Fundação de dados — catchment, base de calibração das maduras e ingestão (Growth API + simulador)
Status: QA APROVADO — aguardando fechamento (housekeeping move + commit por path do orquestrador)
Tipo: feature (engenharia de dados; READ-ONLY sobre M1)
Criticidade: alta
Esteira: Block Orchestrator → Planner → [APROVAÇÃO HUMANA] → Builder → QA
Skill atual: QA CONCLUÍDO — VEREDITO APROVADO
Próxima Skill: Fechamento manual (orquestrador)
dry_run: false

## Decisões aprovadas no gate humano (2026-06-13)
- D1 (histórico): data_inicio = **2022-04-01** (janela mensal até hoje, ~50 meses)
- D4 (madura): `flag_madura = meses_desde_inauguracao >= 8` (MESES_MADURA=8)
- D3 (catchment): raio **1,5 km** (RAIO_CATCHMENT_KM=1.5)
- D2 (simulador): `data/staging/simulador_estrutura.json` é **COMMITABLE** (versionar; NÃO gitignored)
- D5 (helper): `analisar_ponto_censitario_setores` (geométrico, setores reais)
- D6 (steady): N_MESES_STEADY = 6 (mediana dos últimos 6 meses)
- D7 (endpoint): ingerir só `/historico-dash-view` (superset), confirmando campos no 1º fetch

## Tiering de modelo (Passo 4) — Alta
- Block Orchestrator: sonnet
- Planner: opus
- Builder: opus
- QA: opus 4.8 (sempre)

## Objetivo
Montar a fundação de dados da epic BLK-DIM (camada paralela de Dimensionamento e Viabilidade),
SEM tocar o M1: (a) ingerir da Growth API os agregados por unidade/período (`/historico-dash` +
`/historico-dash-view`) — ZERO PII em disco — incluindo `inauguracao` (maturação real, fecha o gate
G1 da DEC-001); (b) extrair coeficientes/estrutura do simulador financeiro `.xlsx`; (c) materializar
`pop_captação`/`renda_per_capita_captação` por unidade via batch de `analisar_entorno_ponto`;
(d) consolidar a base de calibração das ~54-60 maduras (pagantes steady, churn, ticket, curva de
maturação, metragem, pop_captação). Tudo em staging Parquet gitignored.

## Fatos confirmados (pré-ciclo)
- Conectividade Growth API: `POST /auth/login` → HTTP 200, token JWT OK. Login é MASTER (vê todas as unidades).
- Rate limit: 10 req / 5 min por IP (HTTP 429) → ingestão throttled + backoff + cache.
- Credencial em `.env` raiz (gitignored, confirmado) via `python-dotenv`; `requests`+`dotenv` disponíveis.
- Simulador `data/ultra/ULTRA padrão   - Simulador Financeiro (1).xlsx` (gitignored), 9 abas
  (Simulador/Resumo/DRE/Financiamento/Cálculo Anuidade/Fluxo de Caixa/FC/Tributos/Fopag).
- Doc da API: `data/ultra/Growth_API_Ultra_v1_0_0.pdf`; base URL `https://services.ultraacademia.com.br/growth_api_ultra`.

## Branch do ciclo
ciclo/BLK-DIM-00 (a partir de main @ cfd9ac8)

## Paths prováveis do ciclo (commit por path no fechamento)
- scripts/growth_api_client.py (novo — cliente API com auth/throttle/backoff)
- src/motor_expansao/dimensionamento/ (novo módulo: ingestão/catchment/calibração)
- data/staging/*.parquet (gitignored — saídas; NÃO commit)
- tests/ (novos testes sintéticos/unit — mock da API, sem rede real em CI)
- tasks/current_task.md, tasks/completed.md, tasks/backlog.md (stub via helper 6.0)
- context/handoff.md + context/handoff/

## Fora de escopo (invioláveis)
- score_priorizacao/hex_score_estrutural/pesos/artefatos oficiais do M1 (READ-ONLY; DEC-001)
- Endpoints com PII (`/base-cancelados`, `/nps-detalhado`, `/alunos-frequencia`,
  `/cancelados-frequencia`, `/relatorio-vendas-operacoes`, `/cancelamento-*`): NÃO persistir PII
  (nome/CPF/e-mail/celular/data_nascimento) em disco. Preferir agregados; se precisar de churn
  granular, agregar na borda e descartar PII (LGPD §10.3).
- Dependência de API ao vivo no dashboard de produção (ingestão é offline/batch).
- Construir/treinar modelo (isso é DIM-01+); aqui é só fundação de dados.

## Resultado do Builder (2026-06-13)
- Verificação de escopo MASTER: CONFIRMADO (88 unidades na view; 54/54 match perf = 100%).
- Parquets materializados (staging gitignored): `growth_api_historico.parquet` (61.844 linhas,
  93 unidades, 2022-04 → 2026-06, 100% inauguracao real), `unidades_ultra_catchment.parquet`
  (54 unid., 53 válidas, 1 sem lat/lng), `base_calibracao_maduras.parquet` (54 unid., 54 maduras,
  meses_desde_inauguracao nunique=29, 1 lacuna). `simulador_estrutura.json` COMMITABLE (D2).
- Validações: 47 passed (dimensionamento) + 183 (streamlit integ.); ruff/mypy limpos; import ok;
  3 parquets PII-free; git sem parquet/env/xlsx/cache rastreado.
- Próxima Skill: QA (gate único de suite full).

## Resultado do QA (2026-06-13) — VEREDITO: APROVADO
- Suite full (gate único): `780 passed, 4 skipped` em `-n auto` E serial (IDÊNTICAS → sem flakiness).
- ruff: All checks passed!; mypy dimensionamento: Success (7 files); imports streamlit_app + growth_api_client: ok.
- Anti-PII: `assert_sem_pii` antes de cada `to_parquet` (3/3); 3 parquets inspecionados (29/9/22 cols) = ZERO PII;
  nenhum endpoint PII referenciado no módulo.
- READ-ONLY M1: nenhum artefato M1 no diff; perf parquet não sobrescrito; pesos 0.40/0.60 intocados (DEC-001).
- Vazamento: só `simulador_estrutura.json` (D2) commitable; parquets gitignored; JSON sem PII/dado financeiro real.
- No-bypass: confirmado (full rodou completa, sem `-p no:xdist`; fixtures sintéticas são isolamento legítimo).
- Housekeeping `--check`: FALHA pré-move (esperado — move é do orquestrador no fechamento).
- Ressalva opcional (não bloqueia): branch de ABORT de escopo master em `ingerir_growth_api.py` sem teste próprio (CLI offline).
- Decisão: fechar ciclo.

## Worktree pré-sujo (não tocar)
- data/raw/ibge/malha_brasil.geojson (D) — não relacionado
- data/raw/ibge/malha_uf_brasil.geojson (D) — não relacionado
