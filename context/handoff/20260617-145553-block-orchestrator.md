# Handoff — BLK-DIM-13 Block Orchestrator → Planner

## 1. Resumo do bloco

BLK-DIM-13 corrige um bug de wiring de receita no motor property-first de viabilidade (BLK-DIM-11/12).
O simulador financeiro (`simulador.py`) está correto — ele já opera com três fontes de receita separadas
(balcão + agregadores + personal). O problema está no orquestrador (`viabilidade_ponto.py`) e na aba
(`pages.py`): a premissa de demanda que o operador informa representa alunos TOTAIS (balcão + agregadores),
mas é repassada ao simulador integralmente como `alunos_maturidade` (= balcão) ao ticket cheio — e o
simulador ainda soma os 651 agregadores fixos (`SIM_ALUNOS_AGREGADORES_MATURIDADE`) por cima. Double-count.

A correção é pontual e determinística: dividir `demanda_premissa` em `balcao = premissa × share_balcao`
(default ~0,69) + `agregadores = premissa × (1 − share_balcao)` (~0,31), e passar `alunos_agregadores`
explicitamente ao `viabilidade()` em vez de usar o default fixo. Os agregadores passam a escalar com a
premissa, eliminando o double-count. READ-ONLY sobre o M1.

## 2. Análise do bug — evidência do código

### 2.1 Onde o double-count acontece

**`viabilidade_ponto.py` linha 309** (passo 4 do orquestrador):
```python
viab = viabilidade(demanda_premissa, m2, aluguel_pedido, ticket_medio, **kwargs)
```
`demanda_premissa` é passado como `alunos_maturidade` (1º argumento = balcão). O simulador usa esse
valor como balcão E ainda adiciona `alunos_agregadores=SIM_ALUNOS_AGREGADORES_MATURIDADE=651` (default
da função `viabilidade` em `simulador.py` linhas 95 e 207).

**`simulador.py` linha 207** (receita do simulador):
```python
receita_agr = alunos_agregadores * ticket_agregador * (1.0 - inadimplencia)
```
`alunos_agregadores` usa o default `SIM_ALUNOS_AGREGADORES_MATURIDADE = 651` (constante fixa,
`config.py` linha 90) quando nenhum valor é passado pelo chamador.

**`pages.py` linhas 3006–3022** (aba da UI): o toggle "Usar p50 dos comparáveis" preenche o campo
chamado `"Demanda assumida (alunos balcao na maturidade)"` com `faixa_p50_preview`, que é o p50 de
`alunos_total` (balcão + agregadores) da base de calibração. Portanto, o valor que entra é alunos
TOTAIS, não só balcão — e o label da aba reforça a confusão ao chamar de "alunos balcao".

### 2.2 Impacto quantificado (estudo §8, `relatorio.md` linha 170)

| Cenário | Receita atual (errada) | Receita correta (split 69/31) | Delta |
|---|---|---|---|
| p50 = 2.350, 1.500 m² | ~R$ 375 k/mês | ~R$ 282 k/mês | **+33% fantasma** |

### 2.3 Por que o simulador está correto (não deve ser alterado)

`simulador.py` foi projetado para receber `alunos_maturidade` (balcão) separado de
`alunos_agregadores`. O benchmark do docstring (linha 15–18) usa `938 balcão + 651 agregadores` e
bate ~22% de margem (correto). O problema é exclusivamente o wiring no orquestrador.

## 3. Arquivos a modificar

| Arquivo | Natureza da mudança |
|---|---|
| `src/motor_expansao/dimensionamento/viabilidade_ponto.py` | Adicionar `SHARE_BALCAO_DEFAULT = 0.69` + parâmetro `share_balcao` em `analisar_viabilidade_ponto`; derivar `alunos_balcao` e `alunos_agregadores_split` da premissa; passar `alunos_agregadores=` explícito nas chamadas a `viabilidade()`, `aluguel_teto()`, `alunos_minimos_viaveis()` e `grade_sensibilidade()` |
| `src/motor_expansao/dashboard/pages.py` | Corrigir o rótulo do campo de demanda (de "alunos balcao" para "alunos totais na maturidade"); ajustar caption para refletir o split automático |
| `tests/unit/dimensionamento/test_viabilidade_ponto.py` | Adicionar teste de regressão de valor (~R$282k, não ~R$375k) + teste anti-double-count; atualizar testes existentes se assinatura mudar |

**Arquivos que NÃO devem ser tocados:**
- `src/motor_expansao/dimensionamento/simulador.py` — já correto; não alterar DRE
- `src/motor_expansao/dimensionamento/config.py` — `SIM_ALUNOS_AGREGADORES_MATURIDADE=651` continua
  existindo como default do simulador para chamadas diretas fora do orquestrador; não remover
- Quaisquer artefatos ou pipelines do M1

## 4. Critérios de aceite

Do backlog (`tasks/backlog.md`, linhas 567–568):

- **CA-01** Receita usa split balcão/agregador com 2 tickets (R$137 balcão + R$82 agregador).
- **CA-02** Agregadores escalam com a premissa (não constante fixa de 651).
- **CA-03** Zero double-count: `demanda_premissa` não aparece tanto em `alunos_maturidade` quanto em
  `alunos_agregadores` ao mesmo tempo sem o split.
- **CA-04** Teste de regressão de valor: com `demanda_premissa=2350`, `m2=1500`, `aluguel=20000`,
  `share_balcao=0.69`, o `faturamento_mensal_steady` deve ser ~R$282 k (±5%), não ~R$375 k.
- **CA-05** Suíte completa verde + ruff/mypy limpos.
- **CA-06** READ-ONLY M1: zero toque em `score_priorizacao`, pesos, artefatos oficiais.

Inferidos da análise:

- **CA-07** `aluguel_teto()` e `alunos_minimos_viaveis()` também recebem o `alunos_agregadores` derivado
  (não o default fixo) — consistência com o novo wiring.
- **CA-08** `grade_sensibilidade()`: a grade varre `n_alunos_range` como alunos TOTAIS e aplica o split
  internamente em cada célula (ou recebe o split explícito via kwargs).
- **CA-09** O rótulo da aba deixa claro que a premissa é de alunos TOTAIS; o caption informa que o
  split balcão/agregador é automático.
- **CA-10** `SHARE_BALCAO_DEFAULT` deve ser uma constante nomeada (não hardcoded 0.69) para rastreabilidade.

## 5. Guardrails READ-ONLY M1

Este bloco é completamente isolado da camada M1:
- Nenhum dos arquivos a modificar toca `score_priorizacao`, `hex_score_estrutural`, pesos (`renda=0.40`/`pop=0.60`) nem qualquer artefato oficial (`brasil_estrutural.parquet`, `brasil_priorizados.parquet`, etc.).
- `scripts/loop_guard.py` validará automaticamente: os paths modificados (`dimensionamento/viabilidade_ponto.py`, `dashboard/pages.py`, `tests/unit/dimensionamento/`) não pertencem ao conjunto bloqueado (`config.py`/`pipelines/m1/`/`*scoring*`/artefatos M1/`deploy/`/compose/Caddy/etc.).
- A correção é uma operação de wiring de parâmetros dentro da camada paralela BLK-DIM; não recalcula nenhum score.

## 6. Riscos e dependências

| Item | Avaliação |
|---|---|
| Depende de BLK-DIM-12 | A aba `render_viabilidade_ponto` já existe em `pages.py` (linhas 2898–3077). Dependência satisfeita. |
| Depende do estudo `data/reports/estudo_escala_alunos/relatorio.md` | Estudo presente e lido. §5 fornece `share_balcao ≈ 0,69`; §8 fornece o exemplo de cálculo correto e o impacto medido. |
| Risco de quebrar testes existentes | O teste `test_analisar_viabilidade_ponto_completo` usa `demanda_premissa=938.0` (valor de balcão do Excel); com `share_balcao=0.69`, o engine passaria `alunos_balcao ≈ 647` ao simulador, mudando o `faturamento` atual do teste. O Planner deve deliberar se ajusta o teste para o novo comportamento correto. |
| Consistência de `grade_sensibilidade` | A função chama `viabilidade(float(alunos), ...)` tratando `alunos` da grade como balcão. Se a grade deve varrer alunos TOTAIS, precisa aplicar o split internamente. O Planner deve clarificar o contrato. |
| `aluguel_teto` com limite superior | `alug_sup = alunos_maturidade * ticket_medio * 2.0` em `simulador.py` linha 360. Após o fix, receberá `alunos_balcao` (menor). O teto continuará correto pois é o limite de busca do brentq, não o valor final. |
| Risco geral | **Baixo** (correção determinística pontual; 3 arquivos; sem dependência de dados externos; sem I/O de parquet). |

## 7. Próxima Skill: Planner

O Planner deve:
1. Confirmar o contrato do split: `demanda_premissa` sempre representa alunos TOTAIS (balcão + agregadores); `share_balcao` é parâmetro configurável com default 0,69 derivado do estudo §5.
2. Decidir o comportamento de `grade_sensibilidade`: a grade varre alunos TOTAIS (e aplica split internamente) ou varre alunos de balcão (comportamento atual). Recomendar a opção mais consistente com o contrato da aba.
3. Detalhar quais testes existentes precisam ser atualizados (especialmente `test_analisar_viabilidade_ponto_completo` e `test_grade_sensibilidade_*`) e que novos testes de regressão de valor devem ser criados.
4. Confirmar que o rótulo da UI em `pages.py` (linha 3018: `"Demanda assumida (alunos balcao na maturidade)"`) deve ser alterado para refletir alunos TOTAIS e que o caption deve mencionar o split automático.
5. Produzir o plano técnico passo a passo para o Builder, com as linhas exatas a modificar em cada arquivo.

---
Skill atual: Block Orchestrator
Próxima Skill: Planner
