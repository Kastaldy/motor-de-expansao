# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
**BLK-OPS-04 — Validação de schema no carregamento.** Introduzir asserções de schema
**read-only** no caminho de load do dashboard (`data.py`), centralizadas em um módulo novo
`dashboard/schemas.py`, para que o dashboard **falhe de forma clara e útil** (em vez de exibir
lixo ou estourar em ponto distante) quando um Parquet vier corrompido ou com schema/range
inesperado. A validação **lê** as colunas de score dos artefatos M1/enriquecido e **asserta
invariantes** (colunas obrigatórias presentes, dtype numérico, score ∈ `[0,100]`, chaves
`hex_id`/`uf` não-nulas, `hex_id` formalmente válido). Nunca recalcula score, nunca muta,
nunca corrige/preenche dados silenciosamente, nunca reescreve artefato.

## Objetivo
Rejeitar carga ruim no `data.py` com erro claro, mantendo o caminho feliz com overhead
desprezível e sem tocar em score, fórmula ou artefato algum.

## Escopo permitido
- Criar `src/motor_expansao/dashboard/schemas.py`: contrato de schema + função(ões) de
  validação puras (ex.: `validate_m1_frame(df)`, `validate_enriched_frame(df)`), que recebem
  um `pd.DataFrame` já carregado e lançam exceção com mensagem útil ao violar invariante.
- Invariantes mínimas a checar (read-only):
  - **Colunas obrigatórias presentes** — reusar/alinhar com `REQUIRED_COLUMNS` de
    `dashboard/constants.py` (não duplicar a lista; importar dela).
  - **Dtype** — colunas de score/numéricas conversíveis a numérico (coerência de tipo, sem
    mutar o frame de produção).
  - **Score ∈ [0,100]** — para `score_priorizacao` e, quando presentes, `hex_score_estrutural`
    e demais scores (CLAUDE.md §3 define o clip 0–100). NaN deve ser tratado de forma
    explícita e documentada (decidir no Planner: NaN tolerado vs. rejeitado — recomendação:
    tolerar NaN, rejeitar apenas valores fora de faixa, para não quebrar hexes legítimos sem
    score; o Planner ratifica).
  - **Chaves não-nulas** — `hex_id` e `uf` sem nulos.
  - **`hex_id` válido** — validade formal de célula H3 (usar `h3`, já em deps; ou checagem
    barata por formato se validar célula a célula pesar — Planner decide o método barato).
- Integrar a validação nos pontos de load de `data.py`: após `_read_parquet_subset` em
  `read_enriched_uf_partition` e no fluxo que alimenta `_read_m1_frame`/`build_dashboard_dataset`.
  Posição exata e granularidade (validar M1 cru vs. frame enriquecido) ficam para o Planner
  desenhar; o guardrail é que a validação rode no caminho de load real do dashboard.
- Mensagem de erro útil: nomear o arquivo/partição, a coluna e a invariante violada.
- `tests/unit/test_schema_validation.py`: caso feliz passa; faltar coluna, dtype errado e
  score fora de `[0,100]` são rejeitados com erro claro; chave nula e `hex_id` inválido
  rejeitados.

## Fora de escopo
- Alterar fórmulas, pesos, `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto
  prazo, plano de domínio ou qualquer artefato oficial do M1.
- Corrigir/preencher/coagir dados silenciosamente (a validação só **rejeita**, nunca conserta).
- Regerar ou reescrever Parquets.
- Adicionar `pandera` ao deploy: `pandera>=0.19.0` existe **apenas** no extra `ml` do
  `pyproject.toml`, **não** nas dependências core do dashboard. Usar Pandera obrigaria
  mover a dependência para o core e pesar o deploy Streamlit. **Recomendação ao Planner:
  implementar validação manual leve (pandas/numpy/h3, já no core) — não introduzir Pandera.**
  Se o Planner ainda quiser Pandera, é decisão de produto sobre dependências e exige aprovação.
- Mudar performance de load de forma relevante (validação deve ser O(linhas) barata, vetorizada).

## Arquivos que devem ser lidos
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\src\motor_expansao\dashboard\data.py`
  (`_read_parquet_subset`, `read_enriched_uf_partition`, `_prepare_dataframe`, `enrich_dashboard_data`)
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\src\motor_expansao\dashboard\constants.py`
  (`REQUIRED_COLUMNS`, `FLOAT_COLUMNS`, `BOOL_COLUMNS`, `TEXT_COLUMNS`, `OPTIONAL_DATASET_COLUMNS`)
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\streamlit_app.py`
  (linhas ~181-322: `_ensure_dataset`, `_read_m1_frame`, `build_dashboard_dataset`,
  `load_uf_catalog`, `load_uf_slice`, `DATASET_PATH`, `ENRIQUECIDO_DIR`)
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\CLAUDE.md` (§3 Campos mínimos / Artefatos oficiais)

## Arquivos que podem ser alterados
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\src\motor_expansao\dashboard\schemas.py` (NOVO)
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\src\motor_expansao\dashboard\data.py`
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\tests\unit\test_schema_validation.py` (NOVO)
- `tasks/current_task.md` · `tasks/backlog.md` · `tasks/completed.md`
- `context/handoff.md` · `context/handoff/`
- (NÃO alterar `streamlit_app.py` salvo se o Planner concluir que a integração exige um ponto
  de chamada lá; nesse caso é alteração mínima de plumbing, sem lógica de score.)

## Critérios de aceite
- Load rejeita Parquet com coluna obrigatória faltante, com dtype errado em coluna de score,
  com `score_priorizacao` fora de `[0,100]`, com `hex_id`/`uf` nulos e com `hex_id` inválido —
  cada um com mensagem que identifica arquivo/coluna/invariante.
- Caminho feliz (frame válido) continua passando, com overhead desprezível e sem mutar dados.
- `pytest -q tests/unit/test_schema_validation.py` verde.
- `pytest -q` continua na baseline (`532 passed, 1 skipped` ou melhor; nenhum teste existente
  quebrado).
- Nenhuma alteração em score/fórmula/artefato M1 (diff só toca os paths listados).

## Criticidade classificada
**MÉDIA** (esteira sem gate humano: Block Orchestrator → Planner → Builder → QA).

**Justificativa da decisão-chave (o trigger "Crítica" NÃO se aplica aqui):**
O guardrail permanente do CLAUDE.md (§5, fim) e o trigger do run-cycle existem para proteger
contra **mutação/alteração/recálculo** de `score_priorizacao`, `hex_score_estrutural`,
carteira, plano e artefatos oficiais — "sem aprovação explícita". O verbo protegido é
*alterar/recalcular*. BLK-OPS-04 é a operação **dual e oposta**: uma trava defensiva
estritamente **read-only** que apenas **lê** as colunas de score e **asserta** que estão sãs;
no caso de falha ela **rejeita** a carga, não a corrige. Não há escrita em Parquet, não há
fórmula nova, não há mudança de pesos, não há novo número de score em lugar algum. Aplicar
"Crítica" aqui inverteria a intenção do guardrail (proteger o M1), penalizando justamente uma
salvaguarda que torna o M1 mais robusto. Os critérios de aceite e a verificação de diff por
path já garantem que nada do M1 muda. Logo: **Média**, esteira direta sem gate humano.

Alerta explícito registrado (conforme guardrail): o bloco **menciona e lê**
`score_priorizacao`/`hex_score_estrutural`. A QA deve verificar no fechamento que o diff
**não** altera nenhum valor, fórmula ou artefato desses campos — só os valida.

## Esteira recomendada
Block Orchestrator (concluído) → **Planner** → Builder → QA.

## Riscos identificados
- **Falso positivo bloqueando o app:** validação estrita demais (ex.: rejeitar NaN em
  `score_priorizacao`/`hex_score_estrutural`) pode derrubar o dashboard com dados legítimos.
  Mitigação: Planner define a política de NaN (recomendação: tolerar NaN, rejeitar só valores
  fora de `[0,100]`); cobrir o caso "NaN tolerado" em teste.
- **Custo de validar `hex_id` célula-a-célula via `h3`** em frames grandes (Brasil ~milhões de
  linhas). Mitigação: validar por UF (load já é lazy por partição) e/ou usar checagem de
  formato barata; Planner escolhe o método e justifica o overhead desprezível.
- **Duplicação da lista de colunas:** risco de divergir de `constants.REQUIRED_COLUMNS`.
  Mitigação: importar de `constants.py`, não redeclarar.
- **Ponto de integração:** validar cedo demais (M1 cru) vs. tarde (frame enriquecido, que tem
  colunas derivadas e dtypes já coagidos por `_prepare_dataframe`). Planner deve escolher o
  ponto que pega Parquet ruim sem reprovar derivações internas legítimas.

## Guardrails ativos
- Guardrail permanente (CLAUDE.md §5): "visualizações, análise radial e interações de mapa não
  podem recalcular ou alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano
  curto prazo, plano de domínio ou artefatos oficiais do M1 sem aprovação explícita." — Esta
  validação **não** recalcula nem altera; apenas lê e rejeita.
- Guardrail específico do bloco (backlog): validação é **read-only** — nunca corrige/preenche
  dados silenciosamente.
- Regra operacional (CLAUDE.md §2): toda mudança relevante entra com teste; nenhum PR sobe com
  CI quebrado. Commit por path — NUNCA `git add -A`.
- Pandera fora do deploy: manter dependências core do dashboard inalteradas.
