# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Sumário do bloco
O BLK-DIM-03R substitui os três números mágicos do simulador financeiro do spike
(`pessoal_pct=0.30`, `outros_custos_pct=0.05`, `custo_fixo_base_mes=5000`) por coeficientes
fundamentados no DRE real do Excel, extraídos pelo BLK-DIM-00 e disponíveis em
`data/staging/simulador_estrutura.json`. O teste precisa ser des-circularizado: em vez de
validar a margem contra constantes ajustadas para passar, deve validar contra o benchmark do
spec §8.2 (margem EBITDA ~23% no ano 2+ para os defaults do Excel).

## Escopo confirmado

**Entra:**
- Criar `src/motor_expansao/dimensionamento/simulador.py` com a função `viabilidade()` e
  helpers `aluguel_teto`, `alunos_minimos_viaveis`, `m2_otimo` (estrutura idêntica ao spike,
  mas parâmetros fundamentados)
- Criar `tests/unit/dimensionamento/test_simulador.py` com testes des-circularizados
- O simulador deve usar os coeficientes do `simulador_estrutura.json` (via constantes
  extraídas do JSON), não hard-codar valores mágicos
- Os testes devem validar margem/ROIC contra os defaults reais do Excel (§8.2), não contra
  constantes auto-ajustadas

**Não entra:**
- Reconstruir as 9 abas do Excel (só a linha de resultado do DRE, ~15 fórmulas)
- Dirigir o .xlsx via xlwings
- Qualquer escrita em M1: `score_priorizacao`, pesos, artefatos oficiais, `config.py` raiz
- VPS, deploy, segredos, PII

## Arquivos-alvo
- `src/motor_expansao/dimensionamento/simulador.py` — CRIAR (não existe na branch atual)
- `tests/unit/dimensionamento/test_simulador.py` — CRIAR (não existe na branch atual)
- `data/staging/simulador_estrutura.json` — READ-ONLY (fonte dos coeficientes reais)
- `src/motor_expansao/dimensionamento/config.py` — pode receber constantes dos custos fixos
  absolutos (se o Planner optar por centralizá-las aqui)

## Análise de risco
**Guardrails verificados:**
- READ-ONLY sobre M1: confirmado — módulo `dimensionamento/` é camada paralela isolada; nenhuma
  escrita em `config.py` raiz, `pipelines/m1/`, artefatos oficiais.
- Sem VPS/deploy/segredos: confirmado — módulo puro Python, sem IO externo.
- Sem PII: confirmado — simulador financeiro opera sobre parâmetros numéricos agregados.
- Loop-safe: confirmado — consome `data/staging/simulador_estrutura.json` (commitable, sem dado
  vivo), sem ingestão ao vivo.

**Risco principal — gap estrutural do DRE real vs. spike:**
O Excel possui custos FIXOS ABSOLUTOS que o spike aproximou com `pessoal_pct` e
`outros_custos_pct` (ratios sobre receita líquida). Isso é uma distorção: os custos reais não
escalam com a receita. O `simulador_estrutura.json` captura apenas os ratios `%` da aba DRE
(royalties, marketing, manutenção, cartões, devoluções) — NÃO capturou os valores absolutos.

**Risco secundário — benchmark §8.2 inacessível só com balcão:**
O spec §8.2 cita "~23% ano 2+" usando o modelo COMPLETO do Excel com 3 fontes de receita
(balcão + agregadores + personal). Com apenas balcão (938 alunos × R$137) e os custos fixos
reais, a margem steady-state é ~−13% — porque o pessoal (R$50.128/mês) é maior que o EBITDA
gerado só pelo balcão. O Planner precisa decidir o caminho de reconciliação (ver seção abaixo).

## Contexto para o Planner

### Estado atual da branch `ciclo/BLK-DIM-03R`
- `simulador.py` NÃO existe na branch (era do spike `ciclo/BLK-DIM-03`, não mergeado)
- `test_simulador.py` NÃO existe na branch
- O módulo `dimensionamento/` existe com: `config.py`, `simulador_parser.py`,
  `calibracao_maduras.py`, `catchment_batch.py`, `ingestao.py`, `growth_api_client.py`

### Coeficientes disponíveis no `simulador_estrutura.json` (prontos, sem número mágico)
Ratios `%` da aba DRE:
- `devolucoes_pct_receita = 0.005`
- `marketing_pct_receita = 0.02`
- `manutencao_pct_receita = 0.02`
- `cartoes_pct_receita = 0.0105`
- `royalties_pct_receita = None (formula)` → usar driver `royalties_pct = 0.08` (célula N11)

Impostos regime presumido:
- `pis = 0.0065`, `cofins = 0.03`, `iss = 0.03`
- `ir_aliquota = formula "=32%*25%" → 0.08`
- `csll_aliquota = formula "=32%*9%" → 0.0288`

Drivers do Simulador:
- `alunos_balcao_maturidade = 938`, `alunos_inicial = 500`
- `alunos_agregadores_maturidade = 651`, `churn = 0.06`, `maturacao_meses = 8`
- `mensalidade = formula (cenário 0 → R$137)`, `aluguel_mes = 20_000`
- `royalties_pct = 0.08`, `capex_total = formula → default ~R$2.340.000`

### Custos fixos absolutos do Excel (NÃO no JSON — extraídos manualmente do DRE)
Valores mensais constantes em todo o horizonte (DRE linhas 50-59 e Fopag linha 44):

| Item | Linha DRE | Valor mensal |
|---|---|---|
| Pessoal (total c/ encargos) | 55 (origem: Fopag) | R$ 50.128,16 |
| IPTU | 52 | R$ 2.000,00 |
| Água/Luz/Gás | 53 | R$ 17.000,00 |
| Telefone/Internet | 54 | R$ 500,00 |
| Terceirizados (Limpeza) | 56 | R$ 14.000,00 |
| Taxa de Tecnologia | 58 | R$ 2.150,00 |
| Assessorias | 59 | R$ 2.500,00 |
| Outros | 69 | R$ 2.000,00 |
| Personal (receita fixa) | 24 | R$ 5.000,00/mês |

Total fixos (excluindo aluguel e personal): R$ 90.278,16/mês

### Fontes de receita do Excel (3 linhas — NÃO só balcão)
| Fonte | Mês 12 | Mês steady-state |
|---|---|---|
| Mensalidade balcão (938 alunos × R$137) | R$ 128.506 | R$ 128.506 |
| Personal (fixo) | R$ 5.000 | R$ 5.000 |
| Agregadores (651 alunos × ~R$82) | R$ 53.512 | R$ 53.512+ |
| **Total receita bruta** | **R$ 188.875** | **~R$ 206.453** (mês 24) |

### Margem EBITDA real do Excel por mês (sobre receita líquida)
- Mês 9: 15,5% | Mês 12: 22,0% | Mês 24: 27,4%
- Spec §8.2 cita "~23% ano 2+" — bate com meses 13-24

### Decisão de design que o Planner deve tomar
O spike só modelou balcão. O benchmark §8.2 de ~23% é inacessível com balcão sozinho + custos
fixos reais. O Planner deve escolher um dos três caminhos:

**Caminho A (simples, escopo menor):** manter só balcão; usar custos fixos reais absolutos;
documentar que o benchmark de margem com balcão sozinho é negativo (correto — reflete a
realidade do Excel); o teste valida a aritmética (margem cresce com alunos, decai com aluguel),
não um valor absoluto específico de 23%.

**Caminho B (recomendado — mais fiel ao Excel e ao spec):** adicionar `alunos_agregadores`
(default 651) e `ticket_agregador` (default ~R$82) e `personal_mes` (default R$5.000) como
parâmetros da função `viabilidade()`. Com os 3 drivers ativos e custos fixos reais, a margem
fica ~22% no mês 12 → o teste pode validar contra [18%, 26%] sem circularidade.

**Caminho C (intermediário):** parâmetro `receita_adicional_mes` (flat) que captura personal +
agregadores. Mais simples que B, menos fiel, mas permite o benchmark.

### Números mágicos do spike a eliminar (e substituição)
| Parâmetro spike | Valor mágico | Substituto real |
|---|---|---|
| `pessoal_pct = 0.30` | inventado | Pessoal = R$50.128 fixo/mês (Fopag) |
| `outros_custos_pct = 0.05` | inventado | IPTU+Água+Tel+Limpeza+Tec+Assess+Outros = R$38.150 fixo/mês |
| `custo_fixo_base_mes = 5_000` | inventado | Não existe como item separado no Excel |

### Estrutura do simulador spike (preservar, adaptar parâmetros)
Extraída de `git show ciclo/BLK-DIM-03:src/motor_expansao/dimensionamento/simulador.py`:
- Dataclass `ViabilidadeResult` com 9 campos
- `viabilidade(alunos_maturidade, m2, aluguel_mes, ticket_medio, ...)` → `ViabilidadeResult`
- `aluguel_teto(alunos_maturidade, m2, ticket_medio, margem_alvo=0.10, **kwargs)` via brentq
- `alunos_minimos_viaveis(m2, aluguel_mes, ticket_medio, margem_alvo=0.0, **kwargs)` via brentq
- `m2_otimo(alunos_maturidade, aluguel_por_m2, ticket_medio, coef_capex_m2, ...)` via brentq
- Lógica de payback por rampa linear (meses 1..maturacao_meses)
- ROIC = NOPAT_anual / capex
- `flag_viavel = margem >= 0.10 AND payback <= 60`

### Dependências
- `scipy` já em `[dev]` — sem dependência nova
- `data/staging/simulador_estrutura.json` já existe — sem regeneração necessária
