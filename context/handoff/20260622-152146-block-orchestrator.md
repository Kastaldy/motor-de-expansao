# Handoff — Block Orchestrator → Planner

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco
BLK-DIM-21 — UI: gráficos financeiros e curva de maturidade na aba de viabilidade

## Criticidade
**Média** — enriquecimento visual; READ-ONLY sobre M1. Esteira: BO → Planner → Builder → QA (sem gate humano; bloco loop-safe).

## Dependências confirmadas
- **BLK-DIM-19** — Fix: flag de viável (payback 60 → 36 meses) e display de payback: CONCLUÍDO (em `tasks/completed.md`).
- **BLK-DIM-20** — UI: parâmetros de fluxo de caixa editáveis (capex parcelado): CONCLUÍDO (em `tasks/completed.md`; QA APROVADO com 1038 passed).

## Objetivo do bloco
Adicionar 4 gráficos Plotly à seção de resultados de viabilidade no dashboard, mantendo todos os cards existentes. Criar a função `gerar_serie_mensal()` em `simulador.py` que extrai e encapsula a lógica do loop interno de maturação, retornando `list[dict]` com campos `mes`, `alunos_balcao`, `faturamento_mensal`, `ebitda_mensal`, `fcf_acumulado`.

**Os 4 gráficos (via `st.plotly_chart(..., use_container_width=True)`, após os cards):**
1. **Curva de maturidade** — linha `alunos_balcao` por mês (1–60), linha tracejada de steady-state, anotação do ponto de maturação. Título: "Rampa de alunos (balcão)".
2. **Faturamento e EBITDA mensal** — barras por mês (faturamento bruto) + linha de EBITDA sobreposta. Faturamento em turquesa `#00BFB3`; EBITDA positivo em verde, negativo em vermelho.
3. **FCF acumulado** — área preenchida por mês; linha horizontal em y=0; anotação do ponto de payback (mês em que FCF ≥ 0). Área positiva em turquesa translúcido, negativa em vermelho translúcido.
4. **DRE breakdown (steady-state)** — barras horizontais empilhadas: faturamento → deduções → impostos → custos variáveis → custos fixos (pessoal + outros) → aluguel → EBITDA. Facilita leitura de onde vai a margem.

**Cores Ultra:** turquesa `#00BFB3`, cinza-escuro `#2E3040`, branco, vermelho para valores negativos. Fundo branco/cinza-claro, fonte legível, estilo "Ultra Clean" (ref: BLK-EST-02).

## Arquivos a analisar (o Planner DEVE ler antes de gerar o plano)

### Núcleo do simulador
- `/repo/src/motor_expansao/dimensionamento/simulador.py` — entender a função `viabilidade()` completa, especialmente o loop interno de maturação (onde ficam `alunos_balcao`, `faturamento_mensal`, `ebitda_mensal`, `fcf_t`). A nova `gerar_serie_mensal()` deve espelhar a assinatura de `viabilidade()` (incluindo os parâmetros de financiamento adicionados no BLK-DIM-20: `capex_financiado_pct`, `prazo_financiamento_meses`, `juros_financiamento_am`) e retornar a série temporal — NÃO duplicar lógica, o loop existente pode delegar para ela.
- `/repo/src/motor_expansao/dimensionamento/viabilidade_ponto.py` — entender como `analisar_viabilidade_ponto()` chama `viabilidade()` para saber se precisa de ajuste de pass-through para `gerar_serie_mensal()`.

### Dashboard
- `/repo/src/motor_expansao/dashboard/pages.py` — localizar `render_viabilidade_ponto` (função que renderiza a aba de viabilidade). Identificar onde os cards são renderizados hoje (pós `st.form_submit_button`) e onde os 4 gráficos serão inseridos (logo após os cards). Verificar os imports de `plotly` já presentes.

### Testes existentes
- `/repo/tests/` — localizar testes de `simulador.py` (provavelmente `tests/test_simulador.py` ou similar) para entender o padrão de asserção e onde adicionar testes de smoke para `gerar_serie_mensal()`.

### Dependências de projeto
- `/repo/pyproject.toml` — confirmar que `plotly>=5.20.0` já está em dependências base (mencionado no backlog; não adicionar deps novas).

## Guardrails invioláveis
- **READ-ONLY sobre M1:** NÃO tocar `config.py` do M1 (em `src/motor_expansao/config.py`), NÃO tocar `dimensionamento/config.py`, NÃO tocar `pipelines/m1/`, NÃO recalcular `score_priorizacao`/`hex_score_estrutural`/pesos/artefatos oficiais.
- **Cards existentes preservados:** os cards numéricos do resultado de viabilidade devem permanecer intactos. Os gráficos são ADICIONADOS após eles.
- **Sem dependências novas:** usar somente `plotly` já disponível no ambiente (dep base `plotly>=5.20.0`). NÃO adicionar `altair`, `bokeh`, `matplotlib` ou qualquer outra lib de visualização.
- **Renderização condicional:** os gráficos só renderizam após o submit do formulário (mesmo comportamento dos cards — não mudar esse padrão).
- **`gerar_serie_mensal()` NÃO duplica lógica:** o loop de maturação em `viabilidade()` pode ser refatorado para delegar à nova função, mantendo o comportamento de `viabilidade()` 100% idêntico (testes de regressão devem passar sem alteração).
- **Sem VPS/deploy/segredos/PII/ingestão ao vivo.**
- **Loop guard:** diff não pode tocar `config.py` M1/`pipelines/m1`/`*scoring*`/artefatos M1/deploy/Dockerfiles/compose/Caddy/authelia/`.env`/`secrets/`/CI.

## Critérios de aceite (do backlog)
1. 4 gráficos renderizados sem erro para qualquer combinação válida de inputs.
2. FCF acumulado mostra visualmente o ponto de payback (anotação no mês em que FCF ≥ 0).
3. Curva de maturidade termina visualmente no steady-state (linha tracejada).
4. `gerar_serie_mensal()` tem testes de smoke em `tests/` (campos presentes, comprimento 60, sem NaN).
5. Suite completa verde (`pytest -q`), `ruff check .` limpo, `mypy` sem erros nos arquivos alterados.
6. `python -c "import streamlit_app"` ok.

## Arquivos prováveis a alterar (Builder)
- `src/motor_expansao/dimensionamento/simulador.py` — nova função `gerar_serie_mensal()`.
- `src/motor_expansao/dashboard/pages.py` — 4 `st.plotly_chart(...)` após os cards.
- `tests/` — testes de smoke para `gerar_serie_mensal()`.

## Observações para o Planner
- O backlog menciona que "Felipe tem um exemplo visual de referência (compartilhar antes da execução do Builder para calibrar layout/cores)". No modo loop autônomo, o Builder deve seguir a especificação literal dos 4 gráficos e as cores Ultra definidas no backlog (`#00BFB3`, `#2E3040`), sem aguardar o exemplo visual — este é um bloco loop-safe e a spec é suficiente.
- O BLK-DIM-20 adicionou 3 novos parâmetros a `viabilidade()`: `capex_financiado_pct`, `prazo_financiamento_meses`, `juros_financiamento_am`. A assinatura de `gerar_serie_mensal()` DEVE incluir esses mesmos parâmetros para que o FCF acumulado (gráfico 3) reflita o financiamento quando configurado.
- Performance: o risco principal é latência de 4 charts no Streamlit. A mitigação é renderizar só após submit (já é o padrão atual) — garantir que o Planner inclua isso no plano.
