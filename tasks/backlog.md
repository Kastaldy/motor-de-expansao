# Backlog

## Priorização atual

Próximo ciclo recomendado: validar a estrutura de Skills com uma tarefa real do projeto.

> Blocos BLK-OPS-02/03/04, BLK-ARCH-01 e BLK-SCORE-01/02/03 originados do "Programa de
> Melhorias — Referência do Master Orchestrator" (PRD.md), migrados em 2026-05-29.
> Mapa de dependências e ordem recomendada do programa: ver §3 do PRD.md original.
> Ordem deste backlog: arquitetura (BLK-ARCH-01) à frente da trilha de score (BLK-SCORE-*).

---

## Tarefas pendentes

### BLK-OPS-06 — Alinhar checkout do VPS via `git pull` — CONCLUÍDO (2026-05-29)

Status: CONCLUÍDO (2026-05-29) — APROVADO. Detalhes em `tasks/completed.md`. Mover para a seção
Concluídos no próximo housekeeping do backlog. Execução: `git pull --ff-only` no VPS levou
`/opt/motor-expansao/app` de `64e68b1 → 8218f38` (fast-forward), materializando os 5
`secrets/*.enc.*` como rastreados; HEAD do VPS == origin/main. VPS ainda sem `4ee9685`/`97195e3`
(locais não enviados ao GitHub) — alinhamento 100% via `git push` + novo pull é OPCIONAL.
Criticidade: baixa
Prioridade: alta (próxima da fila)
Tipo: operação / infraestrutura
Skill recomendada: decisão humana + comando direto (per-command no VPS)
Resumo: Fechamento operacional do FU5. O checkout git em `/opt/motor-expansao/app`
(origin = github.com/Kastaldy/motor-de-expansao) está atrás do `origin/main` — não tem
o commit `a2a4cea` que versionou os 5 `secrets/*.enc.*`. No FU5 esses arquivos estavam
untracked no VPS e foram removidos (`rm`), com as versões canônicas vivendo no repo/origin.
Um `git pull` no VPS faz fast-forward e materializa os `.enc.*` como arquivos **rastreados**,
eliminando o estado "atrás do origin" e deixando o checkout limpo/alinhado.
Passos sugeridos (todos per-command, com confirmação explícita — GUARDRAIL CLAUDE.md §6):
1. read-only: `git -C /opt/motor-expansao/app status` e `git -C /opt/motor-expansao/app rev-parse HEAD`
   (confirmar working tree limpo e quão atrás está antes de qualquer pull).
2. read-only: `git -C /opt/motor-expansao/app fetch --dry-run` (ver o que viria).
3. `git -C /opt/motor-expansao/app pull --ff-only` (aplicar; abortar se não for fast-forward).
4. verificar: `secrets/*.enc.*` presentes e tracked; `docker compose` não precisa rebuild
   (mudança é só de arquivos versionados, não de imagem).
Observações:
- Pré-requisito opcional: `git push` do `main` local (hoje `ahead 3` do origin) se quiser que
  o VPS receba também FU4 + housekeeping. NÃO é necessário para os `.enc.*` (já estão no origin
  via `a2a4cea`).
- Não urgente, mas deve ser feita antes do próximo deploy/restore para evitar surpresa de
  estado divergente no servidor.
Dependências: aprovação explícita do usuário, comando a comando, antes de qualquer execução no VPS.

---

### BLK-OPS-07 — Sincronizar VPS 100% com o `main` local (git push + pull)

Status: pendente — executar APÓS concluir BLK-PRD-01 (não rodar neste ciclo)
Criticidade: baixa
Prioridade: média (fechamento de sincronização, ao final do ciclo do BLK-PRD-01)
Tipo: operação / infraestrutura
Skill recomendada: decisão humana + comando direto (per-command no VPS)
Resumo: Fechar a sincronização deixada pendente pelo BLK-OPS-06. Depois daquele bloco, o VPS
(`/opt/motor-expansao/app`) ficou em `8218f38` (origin/main no GitHub no momento), com os 5
`secrets/*.enc.*` já rastreados — MAS o `main` local está à frente do `origin/main` (ahead ~3:
inclui `97195e3` FU4, `4ee9685` BLK-OPS-05 e o fechamento do BLK-OPS-06 `f36adfe`). Para o VPS
refletir 100% o HEAD local, é preciso primeiro publicar o `main` local no GitHub e depois puxar
no VPS.
Passos sugeridos (todos per-command, com confirmação explícita — GUARDRAIL CLAUDE.md §6):
1. local (sua máquina): `git push origin main` (publica FU4 + BLK-OPS-05 + BLK-OPS-06 no GitHub).
   Pré-checagem read-only opcional: `git log --oneline origin/main..main` para ver o que sobe.
2. read-only no VPS: `git -C /opt/motor-expansao/app fetch --dry-run` (confirmar o range que viria).
3. VPS: `git -C /opt/motor-expansao/app pull --ff-only` (abortar se não for fast-forward).
4. verificar no VPS: `git rev-parse HEAD` == `origin/main`; `git status -s` limpo (só os untracked
   não relacionados conhecidos: `authelia/`, `Caddyfile.backup.*`, `docker-compose.prod.yml.backup.*`).
   `docker compose` NÃO precisa rebuild (só arquivos versionados mudam; nenhuma imagem/serviço).
Observações:
- Pré-requisito: BLK-PRD-01 concluído e commitado (a reescrita do PRD.md deve estar no `main` local
  antes do push, para subir tudo de uma vez).
- Antes do push, garantir que as edições pendentes de `tasks/backlog.md` e `PRD.md` estejam
  resolvidas/commitadas como se deseja — o push leva o estado do `main` local.
Dependências: BLK-PRD-01 concluído; aprovação explícita do usuário, comando a comando, antes de
qualquer execução no VPS.

---

### BLK-PRD-01 — Reescrever PRD.md como PRD padrão do projeto

| Campo | Valor |
|---|---|
| **Criticidade** | Média *(doc canônico §2 do CLAUDE.md; Block Orchestrator pode ELEVAR p/ Alta se quiser gate de aprovação do novo formato — nunca rebaixar)* |
| **Prioridade** | Alta |
| **Esteira** | Block Orchestrator → Planner → `[revisão humana do outline]` → Builder → QA |
| **Depende de** | — |
| **Status** | CONCLUÍDO (2026-05-29) — APROVADO pelo QA via /run-cycle (commit `3d1ca1a`, branch `ciclo/BLK-PRD-01`). Detalhes em `tasks/completed.md`. |
| **Skill** | /run-cycle |

**Contexto:** o `PRD.md` atual contém o "Programa de Melhorias — Referência do Master
Orchestrator" — conteúdo **temporário** que substituiu o PRD padrão antigo (apagado por estar
desatualizado). Os 9 blocos desse programa **já foram migrados** para `tasks/backlog.md`
(2026-05-29). Há também uma edição não-commitada pré-existente em `PRD.md` (`M PRD.md`) que será
absorvida/substituída pela reescrita.

**Objetivo:** reescrever `PRD.md` como um **PRD padrão do projeto** — documento de produto
canônico, subordinado ao `CLAUDE.md` (fonte de verdade), sem duplicar o backlog.

**Escopo permitido:**
- Substituir todo o conteúdo de `PRD.md` por um PRD padrão. Estrutura **sugerida** (o Planner
  refina e apresenta o outline para revisão humana antes do Builder escrever, por ser doc canônico):
  - Visão e objetivo do produto (Motor de Expansão Ultra Academia)
  - Público-alvo (18–45) e contextos de uso
  - Escopo do produto / fora de escopo
  - Camadas e trilhas (M1 oficial territorial, censitário, híbrido, mercado/residual, Expansão de Domínio)
  - Score oficial e guardrails canônicos — **referenciar** o `CLAUDE.md` §3/§5, não redefinir valores
  - Requisitos funcionais e não-funcionais (dashboard offline, performance, sem API ao vivo)
  - Métricas de sucesso
  - Roadmap/fases — **referenciar** `tasks/backlog.md` para o detalhe dos blocos, não copiá-los
  - Dependências e restrições (infra/VPS)
- **Commit do `PRD.md` atualizado por path** — este é o entregável final do ciclo (incluído no escopo a pedido do usuário).

**Fora de escopo:**
- Alterar `CLAUDE.md`, código, `config.py`, score, artefatos M1.
- Reescrever, mover ou re-duplicar blocos do `tasks/backlog.md`.

**Arquivos a ler:** `PRD.md` (estado atual + histórico git) · `CLAUDE.md` (fonte canônica) · `tasks/backlog.md` (para referenciar, não duplicar).
**Arquivos a alterar:** `PRD.md`.

**Critérios de aceite:**
- `PRD.md` é um PRD padrão coerente, subordinado ao `CLAUDE.md`, sem duplicar o backlog.
- Nenhum valor canônico contradiz o `CLAUDE.md` (PRD referencia, não redefine pesos/parâmetros).
- `PRD.md` commitado por path (sem arrastar outros arquivos não relacionados).

**Validações obrigatórias:**
```
pytest -q            # doc-only: suíte deve seguir verde (nada de código tocado)
git --no-pager diff --stat -- PRD.md    # escopo: só PRD.md alterado
```

**Guardrails específicos:**
- Doc-only: não toca score/M1/código/artefatos. Por ser canônico, recomenda-se `[revisão humana]`
  do outline proposto pelo Planner antes do Builder escrever.
- Commit isolado por path (`git add PRD.md`); não arrastar a edição pré-existente de outros arquivos.

**Risco:** baixo (documentação). Variância no alinhamento do formato com a expectativa do usuário —
mitigado pela revisão humana do outline.

---

### BLK-OPS-02 — CI completo + build via registry (fora da prod)

| Campo | Valor |
|---|---|
| **Criticidade** | Alta |
| **Esteira** | Block Orchestrator → Planner → `[revisão humana]` → Builder → QA |
| **Depende de** | — |
| **Status** | Pendente |

**Objetivo:** o gate do `main` deve rodar a suíte completa (hoje só 2 arquivos + smoke import),
e o deploy deve usar imagem buildada no CI e empurrada para um registry — o servidor faz `pull`,
não `build`.

**Escopo permitido:**
- Estender `.github/workflows/ci.yml` para rodar `pytest -q` completo (ou o máximo viável).
- Resolver dependências de dados dos testes no runner (fixtures sintéticas / amostras pequenas
  versionadas, **nunca** os Parquets de produção).
- Workflow de build → push de imagem para registry (ex.: GHCR).
- Atualizar runbook de deploy para `pull` em vez de `--build` no servidor.

**Fora de escopo:** alterar lógica de scoring, alterar artefatos M1, executar deploy no VPS.

**Arquivos a ler:** `.github/workflows/ci.yml` · `Dockerfile.streamlit` · `docker-compose.prod.yml` ·
`tests/` (mapear dependências de dados) · `CLAUDE.md` §3.4, §3.5.
**Arquivos a alterar/criar:** `.github/workflows/ci.yml` · novo workflow de build · `tests/fixtures/` ·
`docs/deploy.md`.

**Critérios de aceite:**
- CI roda a suíte completa e fica verde (baseline atual: 532 passed, 1 skipped).
- Build de imagem publica no registry com tag por commit.
- Runbook de deploy descreve `pull` + `up -d` sem `--build` no servidor.

**Validações obrigatórias:**
```
pytest -q                                  # suíte completa, verde
ruff check . && mypy src/                   # qualidade
docker build -f Dockerfile.streamlit -t test:ci .   # build local sanity
```

**Guardrails específicos:**
- Fixtures de teste **não** contêm dados reais de Ultra/Skyfit/Wellhub.
- Deploy efetivo no VPS é passo humano, fora deste bloco.

**Risco:** médio — variância concentrada nas dependências de dados dos 532 testes no runner.
Se o acoplamento a dados locais for grande, considerar quebrar em sub-bloco de fixtures.

---

### BLK-OPS-03 — Manifesto de proveniência nos outputs

| Campo | Valor |
|---|---|
| **Criticidade** | Alta *(toca o pipeline que gera artefatos M1 — additivo, não-mutante)* |
| **Esteira** | Block Orchestrator → Planner → `[revisão humana]` → Builder → QA |
| **Depende de** | — |
| **Status** | Pendente |

**Objetivo:** todo conjunto de outputs carrega sua origem: vintage IBGE, hash do `Ultra.csv`,
`code_commit`, `generated_at`, versões de parâmetros canônicos. Permite distinguir "score mudou
porque o dado mudou" de "mudou porque o código mudou".

**Escopo permitido:**
- Gerar `data/outputs/_manifest.json` no fim de `fase1_bi_exports.py` com os campos acima.
- Expor o manifesto no rodapé/aba do dashboard (read-only).
- Teste validando presença e schema do manifesto.

**Fora de escopo:** **alterar qualquer valor dentro dos artefatos M1.** O manifesto fica ao lado,
nunca dentro do conteúdo de scoring.

**Arquivos a ler:** `src/motor_expansao/pipelines/m1/fase1_bi_exports.py` · `config.py` ·
`src/motor_expansao/core/constants.py`.
**Arquivos a alterar/criar:** `fase1_bi_exports.py` · `_manifest.json` (gerado) ·
componente de rodapé no dashboard · `tests/unit/test_manifest.py`.

**Critérios de aceite:**
- Manifesto gerado contém: `ibge_vintage`, `ultra_csv_sha256`, `code_commit`, `generated_at`,
  `h3_resolution`, `pesos={renda:0.40, pop:0.60}`, `dist_min_ultra_km`, `renda_min`.
- Dashboard exibe a proveniência.

**Validações obrigatórias:**
```
pytest -q tests/unit/test_manifest.py
# Prova de não-mutação dos artefatos M1 (hashes idênticos pré/pós):
sha256sum data/outputs/brasil_priorizados.parquet data/outputs/brasil_estrutural.parquet
# (QA compara com os hashes registrados ANTES da mudança)
```

**Guardrails específicos:**
- QA **deve** verificar que os Parquets M1 (`brasil_priorizados`, `brasil_estrutural`,
  `hexagonos_*_dashboard`) têm hash idêntico antes e depois — provando que só foi **adicionado**
  um manifesto, sem tocar conteúdo. Se algum hash mudar → REPROVAR.

**Risco:** baixo se a não-mutação for provada por hash; médio se a geração do manifesto for
acoplada ao cálculo (deve ser passo final, isolado).

---

### BLK-OPS-04 — Validação de schema no carregamento

| Campo | Valor |
|---|---|
| **Criticidade** | Média |
| **Esteira** | Block Orchestrator → Planner → Builder → QA |
| **Depende de** | — |
| **Status** | Pendente |

**Objetivo:** o dashboard deve falhar de forma clara (não mostrar lixo) se um Parquet vier
corrompido ou com schema/range inesperado.

**Escopo permitido:**
- Asserções de schema no caminho de load (`data.py`): colunas obrigatórias, dtypes, scores em
  `[0, 100]`, chaves não-nulas, `h3` válido. Pandera opcional se já não pesar o deploy.
- Mensagem de erro útil quando a validação falha.

**Fora de escopo:** alterar fórmulas, alterar artefatos, mudar performance de load de forma
relevante (validação deve ser barata).

**Arquivos a ler:** `src/motor_expansao/dashboard/data.py` (`load_uf_slice`,
`read_enriched_uf_partition`, `load_uf_catalog`) · esquema dos outputs.
**Arquivos a alterar/criar:** `data.py` · módulo de schema (ex.: `dashboard/schemas.py`) ·
`tests/unit/test_schema_validation.py`.

**Critérios de aceite:**
- Load rejeita Parquet com coluna faltante, dtype errado ou score fora de `[0,100]`.
- Caminho feliz continua passando com overhead desprezível.

**Validações obrigatórias:**
```
pytest -q tests/unit/test_schema_validation.py
pytest -q   # garantir que nada existente quebrou
```

**Guardrails específicos:** validação é **read-only** — nunca corrige/preenche dados silenciosamente.

**Risco:** baixo.

---

### BLK-ARCH-01 — Concluir migração `src/` e remover legado

| Campo | Valor |
|---|---|
| **Criticidade** | Alta |
| **Esteira** | Block Orchestrator → Planner → `[revisão humana]` → Builder → QA |
| **Depende de** | **BLK-OPS-02** (CI completo verde como rede de segurança) |
| **Status** | Pendente |

**Objetivo:** eliminar a dualidade `src/` vs. legado (`dashboard/` flat, `jobs/`, wrappers de
raiz). Uma única fonte de verdade por função, sem quebrar o dashboard.

**Escopo permitido:**
- Mapear o que ainda é importado dos caminhos legados (`base_h3_brasil.py` raiz, `dashboard/`,
  `jobs/`, `ibge_censo.py`, `poi_enrichment.py`).
- Migrar o que estiver vivo para `src/motor_expansao/`, atualizar imports, remover wrappers e
  legado morto **em passos pequenos e reversíveis**.
- Cada passo: testes verdes antes de avançar.

**Fora de escopo:** mudar comportamento de scoring, mudar artefatos M1, refatorar lógica além do
necessário para mover.

**Arquivos a ler:** árvore completa do repo (`view`), `streamlit_app.py`, todos os imports.
**Arquivos a alterar:** múltiplos — listados pelo Planner após o mapeamento.

**Critérios de aceite:**
- Nenhum import aponta para caminhos legados removidos.
- `import streamlit_app` ok; dashboard sobe localmente.
- Suíte completa verde; comportamento idêntico (scores e artefatos inalterados).

**Validações obrigatórias:**
```
pytest -q
python -c "import streamlit_app; print('ok')"
ruff check . && mypy src/
# Prova de equivalência de M1 (hashes idênticos pré/pós migração):
sha256sum data/outputs/brasil_priorizados.parquet
```

**Guardrails específicos:**
- Migração é **mecânica**, não pode alterar nenhum valor de output M1 (provar por hash).
- Avançar só com CI verde a cada passo — daí a dependência de BLK-OPS-02.

**Risco:** alto e de variância alta (2–5 dias). Quebrar em sub-blocos por área (pipelines /
dashboard / acesso a dados) se o mapeamento revelar acoplamento grande.

---

### BLK-SCORE-01 — Dataset rotulado de validação (Ultra + Skyfit + Wellhub)

| Campo | Valor |
|---|---|
| **Criticidade** | Alta *(read-only sobre M1 — ver §2 do PRD; ratificar com usuário)* |
| **Esteira** | Block Orchestrator → Planner → `[revisão humana]` → Builder → QA |
| **Depende de** | — *(pode rodar em paralelo à Frente A)* |
| **Status** | Pendente |

**Objetivo:** montar a base que liga cada unidade existente (Ultra e Skyfit) ao score do
hex/setor onde ela caiu (M1, censitário, residual, domínio) e ao desfecho observado (alunos
recorrentes; Wellhub/Totalpass como proxy de demanda independente). É insumo do backtest.

**Escopo permitido:**
- Geocodificar cada unidade → célula H3 (res. 7) e setor IBGE correspondente.
- Fazer join com os scores existentes (leitura dos outputs M1 e camadas paralelas).
- Anexar desfechos: `alunos_recorrentes`, sinal Wellhub/Totalpass, `data_abertura` (para maturação).
- Gravar artefato de análise em `data/analysis/dataset_validacao.parquet` — **fora** de
  `data/outputs/` (não é artefato de produto, é insumo de análise).

**Fora de escopo:** **qualquer escrita em artefato M1 ou alteração de score.** Apenas leitura e join.

**Arquivos a ler:** fontes Ultra/Skyfit/Wellhub · `data/outputs/*` (scores) · `core/scoring.py`
(para entender as colunas) · esquema dos setores censitários.
**Arquivos a criar:** script de montagem (ex.: `analysis/build_validation_dataset.py`) ·
`data/analysis/dataset_validacao.parquet` · `tests/unit/test_validation_dataset.py`.

**Critérios de aceite:**
- Cada unidade tem H3/setor resolvidos e os 4 scores anexados.
- Flag de maturação (ex.: `meses_operacao >= N`) presente — unidades imaturas marcadas, não descartadas silenciosamente.
- **Auditoria de qualidade de rótulo:** relatório curto de outliers/nulos em `alunos_recorrentes`,
  com nota explícita sobre a confiabilidade dos números de Skyfit (estimados vs. medidos).

**Validações obrigatórias:**
```
pytest -q tests/unit/test_validation_dataset.py
# Sanidade do join: contagem de unidades de entrada == unidades com score anexado (ou diff explicado)
```

**Guardrails específicos:**
- Dados sensíveis de Ultra/Skyfit/Wellhub **não** entram em logs/handoff em texto agregável a PII.
- Artefato vive em `data/analysis/`, nunca em `data/outputs/`. CSVs com `sep=";"`, `utf-8-sig`;
  `Ultra.csv` permanece `latin-1`.

**Risco:** médio — qualidade dos rótulos de concorrente e maturação de unidades novas são as
maiores fontes de viés. Tratar a auditoria de rótulo como critério de aceite, não opcional.

---

### BLK-SCORE-02 — Poder preditivo dos scores vs. desfecho

| Campo | Valor |
|---|---|
| **Criticidade** | Alta *(read-only sobre M1 — ver §2 do PRD)* |
| **Esteira** | Block Orchestrator → Planner → `[revisão humana]` → Builder → QA |
| **Depende de** | **BLK-SCORE-01** |
| **Status** | Pendente |

**Objetivo:** medir, sobre o dataset rotulado, quanto cada score (M1, censitário, residual,
domínio) prevê `alunos_recorrentes` — por rede e no agregado — e onde discordam do real.

**Escopo permitido:**
- Análise exploratória: correlação score×desfecho, por rede e segmento de maturação.
- Decomposição do M1: renda vs. pop — qual componente carrega o sinal? (testa empiricamente o 0.40/0.60).
- Relatório de achados em `data/analysis/` (markdown + figuras), **sem proposta de mudança ainda**.

**Fora de escopo:** alterar pesos, fórmula ou artefatos M1 — isso é o BLK-SCORE-03.

**Arquivos a ler:** `data/analysis/dataset_validacao.parquet` · `core/scoring.py` · `core/constants.py`.
**Arquivos a criar:** `analysis/score_backtest.py` · relatório `data/analysis/relatorio_backtest.md`.

**Critérios de aceite:**
- Relatório responde, com números: (a) qual score melhor prevê recorrentes; (b) o 0.40/0.60 se
  sustenta?; (c) casos onde score alto ≠ desfecho bom (e hipótese do porquê — ex.: saturação de concorrente).
- Análise controla por maturação (não comparar unidade de 2 meses com uma de 5 anos).

**Validações obrigatórias:**
```
pytest -q             # nada quebrado
python analysis/score_backtest.py   # roda fim a fim e gera o relatório
```

**Guardrails específicos:**
- Estritamente **analítico e read-only**. Nenhuma alteração em `scoring.py`/`constants.py`/artefatos.

**Risco:** baixo a médio (qualidade da análise estatística). N pequeno por rede pode limitar
conclusões — relatar incerteza honestamente, não forçar significância.

---

### BLK-SCORE-03 — Proposta de recalibração + DEC

| Campo | Valor |
|---|---|
| **Criticidade** | **CRÍTICA** |
| **Esteira** | Block Orchestrator → Planner → `[APROVAÇÃO HUMANA OBRIGATÓRIA]` → Builder → QA |
| **Depende de** | **BLK-SCORE-02** |
| **Status** | Pendente |

**Objetivo:** *se* o backtest justificar, propor recalibração dos pesos/fórmula e, somente após
DEC registrada e aprovação humana, implementá-la — preservando reprodutibilidade e versionamento.

**Escopo permitido (em duas fases separadas pelo gate):**
- **Antes do gate (Planner):** proposta de recalibração fundamentada no relatório de BLK-SCORE-02,
  com impacto esperado no ranking, e minuta de DEC (`DEC-00X`).
- **Depois do gate (Builder, só com DEC aprovada):** alterar pesos/fórmula em `core/scoring.py` /
  `core/constants.py`, regerar artefatos via pipeline, registrar nova versão de proveniência.

**Fora de escopo:** qualquer escrita em M1 antes da string `APROVADO POR [usuário] EM [data]` no handoff.

**Arquivos a ler:** `data/analysis/relatorio_backtest.md` · `core/scoring.py` · `core/constants.py` ·
`CLAUDE.md` (DECs existentes).
**Arquivos a alterar (só pós-gate):** `core/scoring.py` · `core/constants.py` · `CLAUDE.md` (nova DEC) ·
regeneração de `data/outputs/` via pipeline.

**Critérios de aceite:**
- DEC registrada em `CLAUDE.md` (ou `DECISIONS.md` se já existir) com justificativa e data.
- Pesos antigos vs. novos documentados; ranking M1 antes/depois comparado e diferenças explicadas.
- Proveniência (BLK-OPS-03) reflete a nova versão.

**Validações obrigatórias:**
```
pytest -q tests/unit/test_scoring.py    # fórmulas — atualizar testes para os novos pesos
pytest -q                               # suíte completa verde
# Regeneração controlada (staging primeiro, nunca sobrescrever prod sem staging):
python -m motor_expansao.pipelines.m1.fase1_bi_exports   # ou comando canônico do repo
```

**Guardrails específicos (invioláveis):**
- Builder **não** altera nada de M1 sem `APROVADO POR [usuário] EM [data]` no handoff.
- Staging primeiro; jamais sobrescrever Parquets de produção sem passo de staging.
- QA verifica explicitamente que `H3_RESOLUTION=7`, `DIST_MIN_ULTRA_KM=1.0` e demais canônicos
  **não** foram tocados — só os pesos aprovados na DEC mudam.

**Risco:** crítico por definição. O gate humano + DEC + staging são a proteção. Não pular nenhum.

---

### BLK-ORQ-02 — Implementar estrutura Fase 2

Status: pendente (depende de BLK-ORQ-01 validado)
Criticidade: alta
Prioridade: média
Tipo: estrutura
Skill recomendada: /run-cycle
Resumo: Criar DECISIONS.md com migração das decisões do CLAUDE.md (DEC-001 a DEC-003),
context/active_context.md, tasks/blocked.md e 5 prompts adicionais
(master_orchestrator, approver, documenter, data_agent, metrics_agent).
Dependências: BLK-ORQ-01
Observações: CLAUDE.md não deve ser reescrito, apenas estendido com seção ## Skills.

---

### BLK-PROD-03 — Avaliar hex_id como category com benchmark

Status: pendente
Criticidade: média
Prioridade: baixa
Tipo: performance
Skill recomendada: /run-cycle
Resumo: hex_id é chave de join; avaliar se category ajuda ou prejudica performance.
Requer benchmark antes de qualquer mudança.
Dependências: nenhuma

---

### BLK-PROD-02 — Limpar leftovers de staging

Status: pendente
Criticidade: baixa
Prioridade: baixa
Tipo: manutenção
Skill recomendada: /run-cycle
Resumo: Remover data/outputs/*.tmp.parquet e diretório tmp_codex_runtime/.
Dependências: aprovação explícita do usuário para remoção de arquivos.
Observações: não executar sem confirmação explícita. Risco de remoção indevida.

---

### BLK-PROD-01 — Refatoração completa do repositório

Status: pendente
Criticidade: estratégica
Prioridade: média
Tipo: refatoração
Skill recomendada: /run-cycle (fluxo estratégico)
Resumo: Migrado do PRD.md. Próxima etapa de planejamento estrutural do repositório.
Dependências: nenhuma bloqueadora
Observações: requer planejamento detalhado antes de execução. Não iniciar sem aprovação.

---

### BLK-PROD-05 — Geocodificação offline/online de endereço

Status: pendente
Criticidade: alta
Prioridade: baixa
Tipo: feature
Skill recomendada: /run-cycle
Resumo: Implementar geocodificação de endereço apenas se dependência externa for
aprovada ou base local viável identificada.
Dependências: aprovação de dependência externa ou base local.

---

### BLK-PROD-06 — Relatório semanal de movimentação concorrencial

Status: pendente
Criticidade: alta
Prioridade: baixa
Tipo: feature / analytics
Skill recomendada: /run-cycle
Resumo: Snapshots, deltas por rede/cidade e impacto nas oportunidades.
Dependências: definição de fonte de dados concorrencial automatizável.

---

### BLK-PROD-07 — Cenários salvos por usuário e histórico de decisão

Status: pendente
Criticidade: alta
Prioridade: baixa
Tipo: feature
Skill recomendada: /run-cycle
Resumo: Apenas se o dashboard evoluir para produto web interno com múltiplos usuários.
Dependências: decisão de produto sobre evolução para web interno.

---


## Concluídos

### BLK-OPS-01-FU5 — Decidir destino dos `secrets/*.enc.*` no VPS

Status: CONCLUÍDO (2026-05-29)
Criticidade: baixa
Prioridade: baixa
Tipo: operação / decisão
Resumo: Decisão tomada (usuário): apagar do VPS, repo = single source of truth.
Durante a execução descobriu-se que `/opt/motor-expansao/app` é um checkout git
(origin = github.com/Kastaldy/motor-de-expansao) e que os 5 `secrets/*.enc.*` lá
estavam **untracked** (`??`), com o checkout do VPS atrás do `origin/main` (sem o
commit `a2a4cea` que os versionou). Antes do `rm`: confirmado que `origin/main`
contém `a2a4cea` e que os sha256 das 5 cópias no VPS batem byte-a-byte com as
versões commitadas (recuperáveis via `git pull`). `rm` dos 5 `.enc.*` untracked
executado no VPS com confirmação comando-a-comando (5 comandos, 1–4 read-only +
5 destrutivo); `secrets/README.md` (rastreado) preservado. `secrets/` no VPS agora
só tem `README.md`. Nenhum segredo em claro tocado; chave privada age nunca esteve
no VPS. Re-criação no deploy/restore via `git pull` (+ `sops -d` quando preciso).
Dependências: atendidas (aprovação explícita do usuário, dada comando-a-comando).

---

### BLK-OPS-05 — Hardening do sistema de orquestração

| Campo | Valor |
|---|---|
| **Criticidade** | Alta *(meta: altera o próprio mecanismo de ciclos)* |
| **Esteira** | Block Orchestrator → Planner → `[revisão humana]` → Builder → QA |
| **Depende de** | — |
| **Status** | Concluído (2026-05-29) — APROVADO pelo QA + dry-run pós-merge validado (BLK-OPS-05-DRYRUN, branch `ciclo/BLK-OPS-05-DRYRUN`, gate 6.a OK: commit isolado por path + handoffs versionados c/ segundos). Detalhes em `tasks/completed.md`. |

**Objetivo:** fechar três lacunas de confiabilidade da orquestração: (1) QA re-executa testes em
vez de confiar no log do Builder; (2) handoffs versionados/auditáveis; (3) disciplina de git por ciclo.

**Escopo permitido:**
- Atualizar `prompts/qa_analyzer.md`: QA roda `pytest -q` por conta própria e cola a saída;
  log reportado pelo Builder **não** é aceito como evidência.
- Handoff versionado: `context/handoff/AAAAMMDD-HHMM-<skill>.md` (append-only) ou log acumulativo,
  preservando estados intermediários do ciclo.
- `.claude/commands/run-cycle.md`: cada ciclo cria branch/commit isolado; ao falhar no meio,
  procedimento de `git reset` documentado e ciclo re-entrante.
- Portar mudanças equivalentes para `.codex/skills/codex-run-cycle/SKILL.md`.

**Fora de escopo:** Fase 2 completa (Master Orchestrator, +5 Skills) — isso é bloco Estratégico à parte.

**Arquivos a ler:** `prompts/*.md` · `.claude/commands/run-cycle.md` ·
`.codex/skills/codex-run-cycle/SKILL.md` · `CLAUDE.md` §4.
**Arquivos a alterar:** os acima.

**Critérios de aceite:**
- Prompt do QA exige re-execução independente de testes.
- Handoffs de um ciclo de exemplo ficam preservados e versionados.
- Ciclo de exemplo gera branch/commit próprio; rollback documentado e testado num dry-run.
- Versão Claude e Codex consistentes.

**Validações obrigatórias:**
```
# Dry-run de um ciclo trivial (ex.: ajuste de doc) end-to-end:
/run-cycle   # com tarefa dummy de criticidade Baixa
git log --oneline -3   # confirma commit isolado do ciclo
ls context/handoff/     # confirma handoffs versionados
```

**Guardrails específicos:**
- Como este bloco modifica a própria esteira, rodá-lo com **observação humana atenta** (gate
  `[revisão humana]`) e validar num ciclo dummy antes de confiar nos ciclos de produção.

**Risco:** médio — alterar o mecanismo enquanto se depende dele. Mitigar com dry-run em tarefa trivial.

---

### BLK-OPS-01 — Backup encriptado de segredos e plano de regeneração

| Campo | Valor |
|---|---|
| **Criticidade** | Alta |
| **Esteira** | Block Orchestrator → Planner → `[revisão humana]` → Builder → QA |
| **Depende de** | — |
| **Status** | Concluído (2026-05-28) — APROVADO COM RESSALVAS. Detalhes em `tasks/completed.md`. |

**Objetivo:** garantir que a perda do VPS não implique perda de segredos/config, e documentar
a regeneração completa dos Parquets a partir das fontes brutas.

**Escopo permitido:**
- Configurar tooling de encriptação de segredos no repo (ex.: SOPS+age ou git-crypt) — apenas a
  infraestrutura, **sem** versionar valores em claro.
- Escrever runbook `docs/backup_restore.md`: o que existe só no servidor (`.env`, `Caddyfile`,
  `authelia/configuration.yml`, `users_database.yml`, `db.sqlite3`), como encriptar/restaurar.
- Documentar a regeneração dos Parquets: IBGE Censo 2022 raw + `Ultra.csv` → pipeline M1 →
  `data/outputs/`, com os comandos exatos e tempo esperado.

**Fora de escopo:** alterar pipeline, alterar M1, executar qualquer coisa no VPS.

**Arquivos a ler:** `CLAUDE.md` §3 · estrutura de `/opt/motor-expansao/`.
**Arquivos a criar:** `docs/backup_restore.md` · `.sops.yaml` (ou equivalente) · `.gitattributes` se git-crypt.

**Critérios de aceite:**
- Runbook revisado descreve restore ponta a ponta de um servidor zerado.
- Tooling de encriptação funciona num arquivo de teste (não num segredo real).
- Nenhum segredo em texto puro entra no git (verificado).

**Validações obrigatórias:**
```
git secrets --scan   # ou: gitleaks detect --no-git -v
# Teste de roundtrip do tooling com arquivo dummy:
echo "dummy: ok" > /tmp/t.yaml && sops -e /tmp/t.yaml | sops -d /dev/stdin
```

**Guardrails específicos:**
- O **Builder NÃO toca o VPS** e NÃO manipula segredos reais. A coleta/encriptação dos segredos
  reais é passo humano, executado a partir do runbook, com confirmação por comando.
- Nenhum valor de segredo aparece em handoff, log de teste ou commit.

**Risco:** baixo, desde que a regra "Builder não acessa segredos reais" seja respeitada.

---

### BLK-OPS-01-FU1 — Stage do `secrets_roundtrip_test.ps1` no próximo commit

Status: CONCLUÍDO (2026-05-28, commit 4ed75d8)
Criticidade: baixa
Resumo: `git add scripts/secrets_roundtrip_test.ps1` aplicado antes do commit
de fechamento. Arquivo entrou no repo.

---

### BLK-OPS-01-FU2 — Executar roundtrip SOPS + gitleaks no ambiente do dev

Status: CONCLUÍDO (2026-05-28)
Criticidade: alta
Tipo: operação / validação
Resumo da execução:
- sops 3.8.1, age 1.1.1 e gitleaks 8.30.1 baixados para `$env:USERPROFILE\tools\`
  (sem privilégio admin; PATH ajustado só na sessão).
- Primeira execução revelou 3 defeitos no tooling entregue por BLK-OPS-01:
  (a) URL do SOPS em `docs/backup_restore.md` §5 incorreta — asset oficial é
      `sops-v3.8.1.exe`, não `sops-v3.8.1.windows.amd64.exe`.
  (b) `scripts/secrets_roundtrip_test.{sh,ps1}` falhavam com `no matching creation
      rules found` porque o `.sops.yaml` tem regras apenas para `secrets/**` e a
      fixture vive em `tests/fixtures/`. Correção: passar `--config /dev/null`.
  (c) Comparação `diff -q` byte-a-byte falhava porque sops normaliza YAML
      (remove aspas redundantes, indentação nested 2→4 espaços). Correção:
      comparação YAML semântica via Python+PyYAML.
- Gitleaks sem config scaneou 13.26 GB em 1h57m e encontrou 3 falsos positivos:
  `.env.example:17 GEOFUSION_API_KEY=` (placeholder), 2x
  `renda_per_capita_setor_2022_calibrada` (nome de coluna de DataFrame em
  `jobs/pipelines/calibrar_renda_setor_2022.py:122` e
  `src/motor_expansao/dashboard/pages.py:2453`). Nenhum segredo real.
- Após correções: roundtrip `ROUNDTRIP OK` + exit 0; gitleaks 0 leaks em 4.63s.
Arquivos alterados pelas correções: `.gitleaks.toml` (novo), `.gitleaksignore`
(novo, 3 FPs registrados), `scripts/secrets_roundtrip_test.{sh,ps1}` (corrigidos),
`docs/backup_restore.md` (§5 URL SOPS + §15.2 gitleaks com config). Commit
corretivo separado.

---

### BLK-OPS-01-FU3 — Atualizar baseline de testes no CLAUDE.md §5

Status: CONCLUÍDO (2026-05-28)
Criticidade: baixa
Tipo: documentação / housekeeping
Resumo: Diagnóstico do QA original interpretou o `509 passed` da linha 94 (descrição
histórica do ciclo Performance e Refatoração de 22-mai) como baseline atual. Decisão:
NÃO reescrever a história do ciclo Performance — adicionar nova linha no topo de §5
declarando explicitamente a baseline atual (`532 passed, 1 skipped, 9 warnings` em
2026-05-28) e marcar que os números menores nos ciclos abaixo são históricos. Também
acrescentado o registro do ciclo BLK-OPS-01 (incluindo FU1, FU2, FU3) em §5.

---

### BLK-OPS-01-FU4 — Corrigir `encrypt_one` no `setup_secrets_vps.sh`

Status: CONCLUÍDO (2026-05-29) — APROVADO pelo QA via /run-cycle (esteira média completa). Detalhes em `tasks/completed.md`.
Criticidade: média
Prioridade: média
Tipo: bug / tooling
Skill recomendada: comando direto (sem /run-cycle)
Resumo: Durante o fechamento real de BLK-OPS-01 em 2026-05-29 (passo 4.5), descobriu-se
que a função `encrypt_one` do script usa `sops -e SRC > DST` com SRC fora de `secrets/`.
Isso falha com "no matching creation rules found" pelo mesmo motivo do defeito 3
(SOPS 3.8.1 não casa `path_regex` com `/`). O workaround manual usado no fechamento
foi `cp SRC DST && sops -e -i DST`. Corrigir a função `encrypt_one` para usar esse
padrão. Adicionar tratamento de erro: se `sops -e -i` falhar, fazer `rm DST` para
não deixar plaintext em `secrets/`.
Dependências: nenhuma.

---

### BLK-20260528-02 — Eliminar warning jwt_secret via force-recreate

Status: concluído (2026-05-28)
Criticidade: baixa
Prioridade: baixa
Tipo: operação / infraestrutura
Skill recomendada: /run-cycle
Resumo: Executar `docker compose up -d --force-recreate authelia` no servidor VPS para
recriar o container do Authelia com os env vars atualizados do docker-compose.prod.yml.
O `AUTHELIA_JWT_SECRET` foi renomeado para `AUTHELIA_IDENTITY_VALIDATION_RESET_PASSWORD_JWT_SECRET`
no compose file (ciclo BLK-20260528-01), mas `docker compose restart` não recria o
container — o warning `jwt_secret deprecated` permanece até o force-recreate.
Downtime esperado: ~10s do Authelia (Caddy e Streamlit não são afetados).
Dependências: nenhuma bloqueadora
Observações: não executar sem confirmação explícita do usuário; aguardar janela de
manutenção conveniente.

---

### BLK-PROD-04 — Avaliar st.fragment para interações do mapa

Status: concluido (2026-05-25)
Criticidade: média
Prioridade: baixa
Tipo: performance / UI
Skill recomendada: /run-cycle
Resumo: Implementado render_mapa_pydeck_fragment (@st.fragment) em pages.py. Reduz reruns da aba ao isolar st.pydeck_chart e captura de clique. QA aprovado: 532 passed, 1 skipped.
Dependências: nenhuma
