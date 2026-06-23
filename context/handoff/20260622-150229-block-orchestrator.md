# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
BLK-DIM-20 — UI: parâmetros de fluxo de caixa editáveis (capex parcelado — equipamentos e tecnologia)

## Objetivo
Adicionar ao simulador financeiro (`simulador.py`) três novos parâmetros de financiamento de capex (`capex_financiado_pct`, `prazo_financiamento_meses`, `juros_financiamento_am`) que calculam a PMT mensal e a subtraem do FCF durante o prazo de parcelamento, e expor esses campos no expander "Parametros avancados" do dashboard (`pages.py`), mantendo comportamento IDÊNTICO ao atual quando `capex_financiado_pct == 0.0`.

## Escopo permitido

### `src/motor_expansao/dimensionamento/simulador.py`
- Adicionar três parâmetros keyword-only à assinatura de `viabilidade()` (após os parâmetros de capex existentes):
  - `capex_financiado_pct: float = 0.0` (% do capex financiado; 0 = comportamento atual)
  - `prazo_financiamento_meses: int = 36` (prazo de parcelamento, default da planilha)
  - `juros_financiamento_am: float = 0.018` (taxa mensal, default 1,8% a.m.)
- Calcular a PMT antes do loop de payback (linhas 273–291):
  - `C = capex_efetivo * capex_financiado_pct`
  - Se `C > 0` e `juros_financiamento_am > 0`: `pmt = C * r * (1+r)^n / ((1+r)^n - 1)` onde `r = juros_financiamento_am`, `n = prazo_financiamento_meses`
  - Se `C == 0` ou taxa == 0: `pmt = 0.0` (regressão zero garantida)
- Dentro do loop `for t in range(1, 61)`, subtrair `pmt` do `fcf_t` SOMENTE para `t <= prazo_financiamento_meses` (custo financeiro pós-EBITDA, pré-payback)
- `margem_ebitda_pct` e `ebitda_mensal` NÃO são alterados pela PMT (EBITDA é pré-financiamento, conforme spec §8.2 e o texto do backlog)
- Atualizar docstring do `ViabilidadeResult` e de `viabilidade()` para mencionar os novos params e o efeito no FCF

### `src/motor_expansao/dimensionamento/viabilidade_ponto.py`
- NÃO requer alteração: `grade_sensibilidade()` e `analisar_viabilidade_ponto()` já passam `**kwargs` para `viabilidade()` — os 3 novos parâmetros fluirão automaticamente via kwargs quando presentes

### `src/motor_expansao/dashboard/pages.py`
- Dentro do expander `"Parametros avancados"` já existente (linha 3306), APÓS os campos `ticket_medio` e `margem_alvo_pct`, adicionar:
  - `capex_total` (`st.number_input`, label "Capex total (R$)", value=`SIM_CAPEX_DEFAULT`, step=10_000.0, key `"viab_ponto_capex"`)
  - `pct_financiado` (`st.slider`, label "% do capex financiado", min 0, max 100, value 0, step 5, key `"viab_ponto_pct_financiado"`)
  - Condicional `if pct_financiado > 0`:
    - `prazo_financiamento_meses` (`st.number_input`, label "Prazo (meses)", min_value=6, max_value=60, value=36, step=6, key `"viab_ponto_prazo"`)
    - `juros_am_pct` (`st.number_input`, label "Juros a.m. (%)", min_value=0.0, max_value=10.0, value=1.8, step=0.1, key `"viab_ponto_juros"`)
    - `st.caption("Equipamentos e tecnologia parcelados conforme planilha padrão (36 meses, 1,8% a.m.). A PMT entra como custo financeiro no FCF (não altera EBITDA).")`
- Passar os novos valores como kwargs na chamada de `analisar_viabilidade_ponto()` (linha ~3344):
  - `capex=float(capex_total)`
  - `capex_financiado_pct=float(pct_financiado) / 100.0`
  - `prazo_financiamento_meses=int(prazo_financiamento_meses)` (só se `pct_financiado > 0`, caso contrário default 0.0 é suficiente)
  - `juros_financiamento_am=float(juros_am_pct) / 100.0`

### `tests/`
- Adicionar testes em `tests/unit/test_simulador.py` (ou o arquivo já existente de testes do simulador):
  - CA-10a: com `capex_financiado_pct=0.0`, resultado IDÊNTICO ao atual (regressão zero)
  - CA-10b: com `capex_financiado_pct=1.0` (100% financiado), `payback_meses` > resultado sem financiamento (PMT aumenta o custo do FCF)
  - CA-10c: `margem_ebitda_pct` INALTERADA entre cenário sem e com financiamento para o mesmo ponto (EBITDA pré-financiamento)
  - CA-10d: PMT calculada corretamente para um par (C, r, n) conhecido (teste direto da fórmula)

## Fora de escopo
- `config.py` do M1 (pesos, fórmula, `score_priorizacao`, parâmetros canônicos do §3)
- `dimensionamento/config.py` — novos defaults NÃO entram como constantes neste arquivo; ficam inline nos parâmetros de `viabilidade()` para não violar a regra de não tocar o config do dimensionamento
- `margem_ebitda_pct` e `ebitda_mensal` (EBITDA é pré-financiamento; a PMT afeta SOMENTE o `fcf_t` e consequentemente o `payback_meses`)
- `viabilidade_ponto.py` — nenhuma alteração necessária (pass-through via `**kwargs` já está implementado)
- VPS, deploy, Dockerfiles, CI fora do `pytest`/`ruff`/`mypy`
- Artefatos M1 (`brasil_estrutural.parquet`, `brasil_priorizados.parquet` etc.)
- Qualquer outro bloco (BLK-DIM-21, BLK-DIM-22 dependem deste)

## Arquivos que devem ser lidos
- `/repo/src/motor_expansao/dimensionamento/simulador.py` (completo — especialmente linhas 88–122 para assinatura e 260–302 para capex + loop de payback)
- `/repo/src/motor_expansao/dimensionamento/viabilidade_ponto.py` (linhas 219–370 para confirmar pass-through via kwargs)
- `/repo/src/motor_expansao/dashboard/pages.py` (linhas 3300–3380 para o expander e a chamada de `analisar_viabilidade_ponto`)
- `/repo/src/motor_expansao/dimensionamento/config.py` (para `SIM_CAPEX_DEFAULT` e outros defaults que a UI já usa)
- `/repo/tests/` (buscar arquivo de testes do simulador para saber onde adicionar CA-10a..d)

## Arquivos que podem ser alterados
- `/repo/src/motor_expansao/dimensionamento/simulador.py`
- `/repo/src/motor_expansao/dashboard/pages.py`
- `/repo/tests/` (arquivo de testes do simulador; NÃO criar arquivo novo se já existe)

## Critérios de aceite
- CA-10a: `viabilidade(..., capex_financiado_pct=0.0)` retorna resultado byte-idêntico ao `viabilidade(...)` sem o parâmetro (regressão zero)
- CA-10b: `viabilidade(..., capex_financiado_pct=1.0, prazo_financiamento_meses=36, juros_financiamento_am=0.018)` tem `payback_meses` estritamente maior do que o mesmo cenário sem financiamento
- CA-10c: `margem_ebitda_pct` idêntica entre os dois cenários de CA-10b (EBITDA não é afetado pela PMT)
- CA-10d: PMT calculada por `viabilidade()` é numericamente correta para par (C, r, n) de referência (testar via inspeção do FCF acumulado nos primeiros N meses)
- Dashboard: com `pct_financiado > 0`, os campos de prazo e juros aparecem no expander; com `pct_financiado == 0`, ficam ocultos
- `ruff check` e `mypy` limpos nos arquivos alterados
- Suite completa (`pytest -q`) verde — zero falhas, zero novos warnings

## Criticidade classificada
Média (enriquecimento do simulador financeiro; READ-ONLY sobre M1)

## Esteira recomendada
Block Orchestrator (feito) → **Planner** → Builder → QA

Nota: o backlog menciona `[REVISÃO HUMANA]` entre Planner e Builder. No modo LOOP AUTÔNOMO com bloco loop-safe, esse gate é substituído pelo guard automático (`scripts/loop_guard.py`). O bloco é loop-safe conforme a tabela do backlog.

## Riscos identificados
- **Regressão no payback sem financiamento:** risco principal. Mitigação: CA-10a (teste de regressão zero obrigatório) e default `capex_financiado_pct=0.0` que zera `C` → `pmt=0.0` → nenhum custo extra no FCF.
- **PMT afetando EBITDA:** erro de posicionamento no DRE. Mitigação: CA-10c obrigatório; a PMT deve ser subtraída do `fcf_t` após `fcf_t = eb_t - ir_t` (linha 288), não antes.
- **Loop de 60 meses atual:** o loop `for t in range(1, 61)` permanece intocado em estrutura; só o `fcf_t` muda dentro dele via `- pmt if t <= prazo_financiamento_meses else 0.0`.
- **kwargs não chegam à grade de sensibilidade:** confirmar que `grade_sensibilidade()` propaga `**kwargs` para `viabilidade()` (já está implementado nas linhas 255–257, sem alteração necessária).
- **Novos campos de UI dentro do form:** os `st.number_input`/`st.slider` DEVEM estar dentro do bloco `with st.form(...)` corrente (antes do `st.form_submit_button`), não fora.

## Guardrails ativos
- Visualizações, análise radial e interações de mapa não podem recalcular ou alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano domínio ou artefatos oficiais do M1 sem aprovação explícita (§5 permanente).
- `margem_ebitda_pct` é EBITDA pré-financiamento (spec §8.2) — a PMT NÃO entra no EBITDA.
- `config.py` do M1 e `dimensionamento/config.py`: INTOCADOS.
- Loop guard (`scripts/loop_guard.py`) aborta se o diff tocar `config.py`/`pipelines/m1`/`*scoring*`/artefatos M1/`deploy/`/Dockerfiles/compose/Caddy/authelia/`.env`/`secrets/`/CI.
- Sem bypass de testes (`--no-verify`, `-k`, `pytest -x` sem suite completa no QA).
