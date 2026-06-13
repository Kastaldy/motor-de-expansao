# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
**BLK-DIM-00 — Fundação de dados: ingestão Growth API, catchment, base de calibração das maduras e parse do simulador**

Camada PARALELA ao M1. Engenharia de dados pura — sem modelagem, sem treino, sem alteração de artefatos M1. Fecha parcialmente o gate G1 da DEC-001 ao trazer `inauguracao` real por unidade (substitui `maturacao_indisponivel` constante na camada paralela). Viabiliza DIM-01/02/04. DIM-03 (simulador financeiro/calculadora) é prototipável JA e independente deste bloco — ver `backlog.md`.

## Objetivo
Montar a fundação de dados da epic BLK-DIM sem tocar o M1: (a) ingerir da Growth API os agregados de performance por unidade/periodo via `/historico-dash` e `/historico-dash-view` (ZERO PII em disco), incluindo `inauguracao` real; (b) materializar `pop_captacao` e `renda_per_capita_captacao` por unidade Ultra existente via batch de `analisar_entorno_ponto`; (c) consolidar a base de calibracao das maduras (pagantes steady-state, churn, ticket, curva de maturacao, metragem, pop_captacao); (d) parsear a estrutura/coeficientes do simulador `.xlsx` para preparar o DIM-03.

## Escopo permitido

### Ingestao Growth API
- Endpoints permitidos: `POST /auth/login` (JWT) e `GET /historico-dash` + `GET /historico-dash-view` (agregados por unidade/data).
- Janelas de data configuráveis via `data_inicio`/`data_fim` (formato YYYY-MM-DD, conforme doc §7).
- Auth JWT: token valido 1 hora; renovar automaticamente ao receber HTTP 401 (refazer login + retentar a requisicao original).
- Rate limit: 10 req/5 min por IP → throttle com espacamento entre requisicoes + retry com backoff exponencial ao receber HTTP 429 (aguardar ≥30 s conforme doc §6; registrar log de cada retry).
- Cache local em `data/cache/growth_api/` (gitignored) para evitar re-fetch desnecessario (idempotencia).
- Credenciais via `.env` raiz (variáveis `GROWTH_API_USUARIO` e `GROWTH_API_SENHA`) com `python-dotenv`. NUNCA hardcodar.
- Saida: Parquet em `data/staging/growth_api_historico.parquet` (gitignored). Colunas minimas obrigatorias de `/historico-dash-view`: `unidade`, `data`, `faturamento`, `pagantes`, `ticket_medio`, `cancelados`, `churn`, `ativos_total`, `inadimplente`, `NPS`, `uf`, `inauguracao`. Demais campos numericos do doc §8.2/8.3 (Gympass, Totalpass, passagens etc.) — preservar tudo; nao descartar campos desconhecidos sem inspecao.
- Modulo novo: `src/motor_expansao/dimensionamento/growth_api_client.py` (auth + throttle + cache + fetch).
- **PII: NENHUM campo de aluno** (nome/cpf/email/celular/data_nascimento/cod_aluno/nome_usuario/usuario) pode ser persistido em disco. Os dois endpoints permitidos sao agregados por unidade/data e, pela doc §8.2/8.3, nao listam PII individual — confirmar por assert no codigo antes de qualquer `.to_parquet()`.

### Catchment por unidade
- Rodar `analisar_entorno_ponto` (em `src/motor_expansao/dashboard/censo_point.py`) em batch para cada unidade Ultra ativa (lat/lng de `data/staging/unidades_ultra_performance_hex.parquet`).
- Raio fixo: **1,5 km** (padrao do helper); parametrizar para suportar 1,0–2,0 km via argumento sem alterar o helper.
- Colunas a materializar por unidade: `pop_captacao` (soma da populacao dos setores no raio), `renda_per_capita_captacao` (media ponderada por pop), `n_setores_captacao`, `raio_km`.
- Saida: `data/staging/unidades_ultra_catchment.parquet` (gitignored).
- **NAO sobrescrever** `data/staging/unidades_ultra_performance_hex.parquet` (artefato existente, 54 unidades/57 colunas — READ-ONLY).
- CI: o batch de catchment pode ser lento (cruzamento geométrico real por unidade); isolar em modulo separado (`dimensionamento/catchment_batch.py`) com execucao offline — CI usa mock.

### Base de calibracao das maduras
- Consolidar por unidade, cruzando `unidades_ultra_performance_hex.parquet` (metragem, faturamento, pagantes, alunos_por_m2, ticket) com:
  - `growth_api_historico.parquet` → serie temporal: `pagantes`, `churn`, `cancelados`, `ativos_total`, `inadimplente`, `ticket_medio`.
  - `unidades_ultra_catchment.parquet` → `pop_captacao`, `renda_per_capita_captacao`.
- Derivar por unidade: `pagantes_steady_state` (mediana de `pagantes` nos ultimos N meses maduros; N configuravel, default 6), `churn_steady` (mediana de `churn`), `ticket_steady` (mediana de `ticket_medio`), `meses_desde_inauguracao` (a partir de `inauguracao` do `/historico-dash-view`), `flag_madura` (≥12 meses de operacao — parametrizavel).
- `meses_desde_inauguracao` fecha parcialmente o gate G1 da DEC-001 na camada paralela (nao no M1).
- Saida: `data/staging/base_calibracao_maduras.parquet` (gitignored). Coluna `lacunas` obrigatoria: lista de campos NaN por unidade (insumo de auditoria para o handoff ao DIM-01).
- Chave de join: campo `unidade` da API vs. identificador em `unidades_ultra_performance_hex.parquet` — o Planner deve identificar o campo correto e documentar normalizacao necessaria (strings, acentos, maiusculas/minusculas).

### Parse do simulador financeiro
- Arquivo: `data/ultra/ULTRA padrão   - Simulador Financeiro (1).xlsx` (gitignored, 9 abas: Simulador/Resumo/DRE/Financiamento/Calculo Anuidade/Fluxo de Caixa/FC/Tributos/Fopag).
- Escopo: **leitura e extracao de estrutura apenas** — NAO construir a calculadora nem o goal-seek (isso e DIM-03).
- Extrair: mapeamento de celulas-chave da aba `Simulador` (drivers do spec §8.2: E9, E10, E11, E12, E13, J9, J10, N9, N11, R9, R10, R11) e ratios de custo da aba `DRE` (Marketing 6%, Manutencao 1%, Cartao 1,05%, Devolucoes 0,5%, IR 8% efetivo, CSLL 2,88%). Confirmar/corrigir valores default documentados contra o `.xlsx` real.
- Saida: `data/staging/simulador_estrutura.json` — mapeamento `{driver: {aba, celula, valor_default, unidade, natureza}}`. JSON (nao Parquet) pois e estrutura/metadado. O Planner deve decidir se e gitignored ou commitable (e metadado parametrico, nao dados de aluno — provavelmente commitable, mas confirmar se contem dados confidenciais).
- Dependencia: `openpyxl` (verificar se ja esta em `pyproject.toml`; adicionar se ausente; NAO usar xlwings).
- Modulo: `src/motor_expansao/dimensionamento/simulador_parser.py`.

### Modulo dimensionamento
- Pasta nova: `src/motor_expansao/dimensionamento/` com `__init__.py`.
- Submódulos: `growth_api_client.py`, `catchment_batch.py`, `calibracao_maduras.py`, `simulador_parser.py`.
- Scripts de execucao offline: `scripts/ingerir_growth_api.py`, `scripts/calcular_catchment_maduras.py`, `scripts/consolidar_base_calibracao.py` (ou equivalentes).

### Testes
- Testes unitários com **mock da API** (sem rede real em CI): mock de `requests.get`/`requests.post` simulando respostas JSON da doc §8.2/8.3, incluindo cenários de HTTP 401 (renovacao de token) e HTTP 429 (backoff).
- Teste de parse do simulador: fixture JSON ou subset `.xlsx` minimo sem dados confidenciais (o simulador e financeiro/parametrizado, sem PII de aluno).
- Teste de catchment: mock de `analisar_entorno_ponto` com retorno sintetico — CI nao executa cruzamento geometrico real.
- Teste de consolidacao: fixture sintetica dos Parquets de entrada → verificar colunas de saida, assert anti-PII e coluna `lacunas`.

## Fora de escopo

- **score_priorizacao / hex_score_estrutural / pesos M1 / artefatos oficiais do M1**: absolutamente READ-ONLY. DEC-001 vigente. Nenhum Parquet do M1 pode ser sobrescrito ou recalculado.
- **Endpoints com PII**: `/base-cancelados`, `/cancelamento-solicitado`, `/cancelamento-imediato`, `/nps-detalhado`, `/alunos-frequencia`, `/cancelados-frequencia`, `/relatorio-vendas-operacoes`. NAO chamar neste bloco. PII (nome/CPF/e-mail/celular/data_nascimento/cod_aluno) NAO pode ser persistida em disco em nenhum momento.
- **Modelagem / treinamento**: construir o modelo de aderência (DIM-01), o modelo de captura Huff (DIM-02) ou a calculadora financeira dinamica com goal-seek (DIM-03) sao blocos posteriores. Aqui e so fundacao de dados.
- **Dependencia de API ao vivo no dashboard de producao**: ingestao e offline/batch (script avulso). O Streamlit nao pode chamar a Growth API diretamente.
- **Reconstruir as 9 abas do Excel em Python**: o simulador e so parseado para extracao de estrutura/coeficientes. A calculadora dinamica e o DIM-03.
- **xlwings**: descartado (ver spec §8.5).
- **Commits de dados**: Parquets de staging sao gitignored e NAO devem ser commitados. O `.env` NAO deve ser commitado.
- **Alterar `setor_censitario_intersecao_area_1p5km`**: o helper de catchment e consumido mas nao alterado. Raio de 1,5 km do relatorio censitario e metodo de interseccao INTOCADOS.
- **Deploy VPS / comandos SSH**: nenhum deploy neste bloco. Nenhum comando SSH sem aprovacao explicita por comando individual (guardrail §6 CLAUDE.md).

## Arquivos que devem ser lidos

- `CLAUDE.md` — completo; foco em §2 (regras operacionais, PII, staging), §4 (camada DIM paralela), §6 (guardrails VPS), §8 DEC-001 e DEC-008 (se existir).
- `tasks/current_task.md` — fatos pré-ciclo confirmados (conectividade API HTTP 200, rate limit, credencial, simulador, branch `ciclo/BLK-DIM-00`).
- `tasks/backlog.md` — epic BLK-DIM completa (seção "Epic BLK-DIM") e bloco BLK-DIM-00.
- `modelo_dimensionamento_expansao.md` — spec do CEO completo; foco em §0 (resumo executivo), §3 (catchment indefinido e curva de densidade), §4 (arquitetura 4 camadas), §6 (Fase 0 = este bloco), §8 (simulador financeiro: drivers §8.2, integracao §8.4, implementacao §8.5).
- `data/ultra/Growth_API_Ultra_v1_0_0.pdf` — doc da API: endpoints §8.2 (`/historico-dash`) e §8.3 (`/historico-dash-view`), auth JWT §5, rate limit §6, campos completos, LGPD §10.3. (Leitura via PyMuPDF ou Read direto do PDF.)
- `src/motor_expansao/dashboard/censo_point.py` — assinatura e parametros de `analisar_entorno_ponto`.
- `data/staging/unidades_ultra_performance_hex.parquet` — verificar colunas disponiveis (lat/lng, identificador, metragem, faturamento, pagantes, alunos_por_m2, ticket).
- `pyproject.toml` — verificar dependencias (`openpyxl`, `requests`, `python-dotenv`) e extras definidos.
- `config.py` — parametros canonicos do M1 (garantir que nenhum parametro novo colide).
- `.gitignore` — verificar se os paths de staging ja estao cobertos.

## Arquivos que podem ser alterados / criados

### Novos (criar)
- `src/motor_expansao/dimensionamento/__init__.py`
- `src/motor_expansao/dimensionamento/growth_api_client.py`
- `src/motor_expansao/dimensionamento/catchment_batch.py`
- `src/motor_expansao/dimensionamento/calibracao_maduras.py`
- `src/motor_expansao/dimensionamento/simulador_parser.py`
- `scripts/ingerir_growth_api.py`
- `scripts/calcular_catchment_maduras.py`
- `scripts/consolidar_base_calibracao.py`
- `tests/unit/dimensionamento/` (novos testes com mocks)
- `data/staging/growth_api_historico.parquet` (gitignored — NAO commitar)
- `data/staging/unidades_ultra_catchment.parquet` (gitignored — NAO commitar)
- `data/staging/base_calibracao_maduras.parquet` (gitignored — NAO commitar)
- `data/staging/simulador_estrutura.json` (commitable se nao contiver dados confidenciais — decidir no Planner)
- `data/cache/growth_api/` (gitignored)

### Pode alterar (apenas acrescimos)
- `pyproject.toml` — adicionar `openpyxl` se ausente; extras `[dimensionamento]` se necessario (NAO arrastar xlwings/PostGIS/Prefect/sentry-sdk).
- `.gitignore` — adicionar paths de staging do DIM se ainda nao cobertos.
- `tasks/current_task.md`, `tasks/completed.md`, `tasks/backlog.md` — atualizacoes de status ao fechar.
- `context/handoff.md` + `context/handoff/` — handoffs das proximas Skills.

### NAO tocar (READ-ONLY absoluto)
- `data/staging/unidades_ultra_performance_hex.parquet` — entrada; nao sobrescrever.
- Artefatos M1 oficiais: `brasil_estrutural.parquet`, `brasil_priorizados.parquet`, `hexagonos_brasil_oportunidades.parquet`, `hexagonos_brasil_dashboard.parquet`, `hexagonos_mapa_sample.parquet`, etc.
- `src/motor_expansao/dashboard/censo_point.py` — consumir `analisar_entorno_ponto`, nao alterar.
- `src/motor_expansao/dashboard/censo_map.py`, `censo_report.py` — intocados.
- `config.py` — parametros canonicos do M1.
- `src/motor_expansao/pipelines/m1/` — intocado.

## Critérios de aceite

1. **Ingesta da API verificada:** `growth_api_historico.parquet` existe localmente com colunas minimas (`unidade`, `data`, `faturamento`, `pagantes`, `ticket_medio`, `cancelados`, `churn`, `ativos_total`, `inadimplente`, `uf`, `inauguracao`) e ZERO colunas de PII individual. Auditoria: quantas unidades, range de datas, quantas linhas.
2. **Rate limit respeitado:** cliente nunca envia mais de 10 req em 5 min; em HTTP 429 aguarda ≥30 s e retenta; em HTTP 401 refaz login e retenta 1 vez. Comportamento testado via mock.
3. **PII zero em disco:** assert explícito no codigo de ingestao que nenhuma das colunas `[nome, cpf, email, celular, data_nascimento, cod_aluno, nome_usuario, usuario]` esta no DataFrame antes de salvar.
4. **Catchment materializado:** `unidades_ultra_catchment.parquet` com `pop_captacao`, `renda_per_capita_captacao`, `n_setores_captacao`, `raio_km` por unidade; join correto documentado com o identificador de `unidades_ultra_performance_hex.parquet`.
5. **Base de calibracao consolidada:** `base_calibracao_maduras.parquet` com `pagantes_steady_state`, `churn_steady`, `ticket_steady`, `meses_desde_inauguracao`, `flag_madura` por unidade; coluna `lacunas` listando campos NaN; proporcao de unidades com `inauguracao` real preenchida documentada (meta ≥80%; abaixo disso, impacto em DIM-01 documentado — nao bloqueia fechamento).
6. **Maturacao real disponivel:** `meses_desde_inauguracao` nao e constante em pelo menos parte das unidades — confirma fechamento parcial do gate G1 da DEC-001 na camada paralela.
7. **Parse do simulador:** `simulador_estrutura.json` com mapeamento dos drivers do spec §8.2 (E9, E10, E11, E12, E13, J9, J10, N9, N11, R9, R10, R11) e ratios do DRE; valores confirmados contra o `.xlsx` real.
8. **Testes verdes (CI sem rede real):** todos os testes do modulo `dimensionamento/` passam com mocks; `pytest -q` suite completa verde (baseline: ≥532 passed, 1 skipped); ruff + mypy limpos.
9. **M1 intacto:** nenhum artefato M1 alterado (verificado no QA).
10. **Nada commitado de dados confidenciais:** Parquets de staging e `.env` nao aparecem em `git status` nem em `git diff --cached`.

## Criticidade classificada
**Alta** (engenharia de dados nova; camada PARALELA; READ-ONLY sobre M1; DEC-001 intacta; LGPD/PII como guardrail forte; sem alteracao de formula, pesos ou artefatos oficiais).

Interpretacao operacional (CLAUDE.md §2): LEITURA/ANALISE sem escrita em artefato M1 → Alta (revisao humana antes do Builder).

## Esteira recomendada
Block Orchestrator (este) → **Planner** (Opus) → **[APROVACAO HUMANA do plano tecnico]** → **Builder** (Opus) → **QA** (Opus 4.8)

## Riscos identificados

1. **Rate limit severo (10 req/5 min):** a serie historica completa pode exigir dezenas de janelas de data × unidade. O Planner deve dimensionar o volume total e propor estrategia de janelas (ex.: mensal desde 2023). Mitigacao: cache local obrigatorio; script de ingestao idempotente.
2. **Escopo do login MASTER nao testado alem do /auth:** confirmado HTTP 200 no `/auth/login`. Nao confirmado se `/historico-dash` e `/historico-dash-view` retornam dados de TODAS as unidades. O Planner deve incluir passo de verificacao inicial: apos o primeiro fetch, auditar o campo `unidade` e cruzar com a lista de `unidades_ultra_performance_hex.parquet`.
3. **Identificador de unidade pode exigir normalizacao:** a API retorna `unidade` (string). O Parquet de performance usa identificador proprio. O join pode exigir normalizacao de strings (capitalizacao, acentos, abreviacoes). Builder deve documentar e testar esse mapeamento.
4. **Volume e tempo do catchment batch:** `analisar_entorno_ponto` faz cruzamento geometrico real com setores censitarios. Para 54-60 unidades pode levar minutos. Isolar em script offline; CI usa mock.
5. **Simulador `.xlsx` gitignored:** o arquivo existe na maquina local mas nao no repo. O Builder precisa que o arquivo esteja acessivel no ambiente de execucao. O QA nao pode executar o parser real em CI — usar fixture de mock. Decidir no Planner se `simulador_estrutura.json` pode ser commitado (metadado parametrico, sem PII de aluno — provavelmente sim).
6. **`inauguracao` pode ter NULLs ou inconsistencias:** o campo existe na doc §8.3, mas pode ser nulo para unidades antigas. O gate G1 da DEC-001 so fica totalmente fechado se a cobertura for suficiente para calibrar DIM-01. O criterio de aceite #6 define meta ≥80%; abaixo disso, documentar honestamente.
7. **PII acidental em resposta da API:** a doc §10.3 alerta que dados da API contem informacoes pessoais de alunos. Os dois endpoints permitidos sao agregados e, pela doc §8.2/8.3, nao listam PII individual. Porem, se a API retornar colunas inesperadas (ex.: `nome_gerente`), o assert anti-PII no codigo deve bloquear antes de salvar.
8. **Churn granular fora do escopo:** `/base-cancelados` e similares sao fora do escopo. O campo `churn` disponivel e taxa agregada de `/historico-dash` (%). Para modelo de churn individual futuro (DIM-01+), sera necessaria decisao explicita separada.

## Guardrails ativos

### CLAUDE.md §2 (regras operacionais)
- Tratar `config.py`, `CLAUDE.md` e `PRD.md` como fontes canonicas.
- Staging sempre em Parquet; CSVs locais com `sep=";"` e `encoding="utf-8-sig"`.
- Ao tocar camadas paralelas, preservar 100% das linhas e colunas oficiais do M1.
- **Nao criar dependencia de API ao vivo no dashboard de producao.**
- Toda mudanca relevante entra com teste; nenhum PR sobe com CI quebrado.
- Interpretacao de criticidade: LEITURA/ANALISE sem escrita em artefato M1 → Alta (revisao humana antes do Builder).

### CLAUDE.md §4 (camadas paralelas)
- Camada DIM e PARALELA ao M1. Nenhuma camada paralela pode alterar o M1 sem aprovacao explicita.
- Dashboard funciona offline com Parquets locais — ingestao Growth API e offline/batch.

### CLAUDE.md §6 (guardrails VPS)
- **GUARDRAIL ABSOLUTO: nunca executar qualquer comando no servidor via MCP sem confirmacao explicita do usuario para cada comando individual.** Nenhum deploy neste bloco.

### DEC-001 (CLAUDE.md §8)
- `renda=0.40` / `pop=0.60` / `score_priorizacao` / `hex_score_estrutural` INALTERADOS.
- `maturacao_status` continua `maturacao_indisponivel` no M1; maturacao real via `inauguracao` e adicionada SO na camada paralela DIM.
- Pre-requisito G1 de reabertura: disponibilizar datas de abertura por unidade → parcialmente fechado neste bloco via `/historico-dash-view`.

### Anti-PII (LGPD §10.3 da doc da API + CLAUDE.md §2)
- Endpoints com PII individual fora do escopo: `/base-cancelados`, `/cancelamento-solicitado`, `/cancelamento-imediato`, `/nps-detalhado`, `/alunos-frequencia`, `/cancelados-frequencia`, `/relatorio-vendas-operacoes`.
- Campos proibidos em disco: `nome`, `cpf`, `email`, `celular`, `data_nascimento`, `cod_aluno`, `nome_usuario`, `usuario`.
- Assert explicito no codigo antes de qualquer `df.to_parquet()`.
