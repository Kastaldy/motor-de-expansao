# STATUS — Ciclo FIN-VIAB-01 (reconciliação do simulador de viabilidade)

**Branch:** `ciclo/FIN-VIAB-01-reconciliacao` · **Worktree:** `.claude/worktrees/fin-viab-01`
**Snapshot deste documento:** 2026-07-24 (estado observado no momento da escrita; o ciclo roda
com frentes em paralelo — confirmar com `git status` antes de tomar decisão de fechamento).

---

## Por que o ciclo existe

A auditoria encontrou **17 defeitos** na camada de viabilidade financeira, todos com a mesma
causa raiz: **cinco séries mensais independentes e nove KPIs com implementação dupla**. Tela,
API e PDF do **mesmo cenário** produziam números diferentes — payback 35 no KPI e 33 no gráfico,
acumulado de 60 meses R$ 1,89 mi ou R$ 2,05 mi, aluguel-teto R$ 55.535 ou R$ 105.813.

**Regra de ouro do ciclo:** ninguém recalcula nada. `simular()` devolve um `ViabilidadeResult`
com tudo pronto; backend, frontend e PDF apenas **leem** `r.*` e `r.serie_mensal`. Nenhuma
fórmula financeira pode existir fora de `simulador.py`.

---

## Fase 1 — Auditoria e reescrita do núcleo — **CONCLUÍDA**

| Item | Estado |
|---|---|
| `dimensionamento/config.py` reescrito como **fonte única** de premissas | ✅ concluído e verificado |
| `dimensionamento/simulador.py` reescrito como **motor único** | ✅ concluído e verificado |
| Série única M-4 a M+60 (`gerar_serie_mensal_completa`) com CAPEX integral | ✅ |
| `simular()` devolvendo todos os KPIs de uma só série | ✅ |
| Funções antigas mantidas como **adaptadores** (`viabilidade`, `gerar_serie_mensal`, `aluguel_teto`, `alunos_minimos_viaveis`) para não quebrar backtest/batch/excel/risco | ✅ |
| Caso golden (Boulevard Londrina) reproduzido direto do motor | ✅ conferido em 2026-07-24 |

**Correções de conteúdo entregues na Fase 1:**

1. Ticket do agregador **acoplado** ao ticket cheio (60%) — era R$ 82 absoluto e degradava
   silenciosamente quando o ticket subia.
2. Folha como **17% do faturamento bruto** — era R$ 50.128,16 fixos para toda unidade.
3. IR/CSLL pelo **Lucro Presumido com faixa explícita** do adicional de 10% — era alíquota
   efetiva sobre a receita líquida, com o adicional embutido como se toda a base excedesse.
4. Break-even em **alunos TOTAIS** com o mix 69/31 escalando — era alunos de balcão com os
   agregadores congelados, e era comparado na tela como se fosse total.
5. Aluguel-teto como **% do faturamento bruto** (única definição do sistema) — eram duas
   definições concorrentes.
6. Retorno **desalavancado** como padrão, com equity separado — o ROIC antigo misturava
   numerador antes do financiamento com denominador de capex cheio.
7. Inadimplência, share de balcão, reajuste, carência, custo pré-operacional, valor residual e
   critérios de `flag_viavel` deixaram de ser literais espalhados e ganharam dono único.
8. TIR e VPL passaram a existir.
9. **Anuidade** (`Simulador!J10`) implementada e **ligada** — R$ 99/ano por aluno de balcão que
   completa 12 meses, elegibilidade derivada do churn, reconhecimento pro-rata mensal. Ver a
   decisão logo abaixo e `PREMISSAS_VIABILIDADE.md` §2.1.

**O núcleo está congelado.** Nenhuma frente deste ciclo deve editar `config.py` ou
`simulador.py`.

---

## Fase 2 — Correções nos consumidores — **EM ANDAMENTO**

Cada consumidor precisa parar de recalcular e passar a ler o resultado do motor. Frentes em
paralelo, uma por arquivo:

| Frente | Arquivos | Estado observado |
|---|---|---|
| **Backend / payload** | `web/server/app.py` | 🔄 modificado — `viabilidade_payload_v1` já emite `premissas.anuidade_*`, `premissas.mes_referencia_steady` e `dre.receita_anuidade` / `.receita_liquida` / `.receita_pos_impostos` (verificado no arquivo) |
| **Motor do ponto** | `dimensionamento/viabilidade_ponto.py` | 🔄 modificado |
| **Gráficos** | `dashboard/viabilidade_charts.py` | 🔄 modificado |
| **PDF** | `dashboard/censo_report.py` | 🔄 modificado |
| **Frontend** | `web/src/lib/types.ts`, `format.ts`, `report.ts` | 🔄 modificado |
| **Documentação** | `PREMISSAS_VIABILIDADE.md`, `docs/nota_impacto_fin_viab_01.md`, `STATUS_ORQUESTRACAO.md`, `web/README.md`, `tasks/backlog.md` | ✅ concluída |

**Guardrails que a Fase 2 não pode quebrar:**

- READ-ONLY sobre o M1 — nada de `score_priorizacao`, pesos ou artefatos oficiais.
- A demanda **nunca** vem de lat/lng (DEC-009); `demanda_fonte = "premissa_explicita"`.
- `web/server/app.py` **não** pode chamar `to_parquet`/`to_csv` (há teste com AST que verifica).
- O payload sai por `json.dumps(..., allow_nan=False)`: nenhum `inf`/`NaN` pode vazar — payback
  infinito e TIR `None` viram `null` explícito.
- No PDF (fpdf2, core font, latin-1): pontuação ASCII (`-`, não travessão).
- Acentuação correta em texto de usuário; nunca em identificadores ou chaves.

---

## Fase 3 — Testes golden — **FECHADA**

| Item | Estado observado |
|---|---|
| `tests/contracts/test_viabilidade_golden.py` | ✅ criado (ainda untracked no worktree) — 133 testes |
| Travar os números do caso Boulevard contra `simular()` | ✅ re-medidos e pinados **com a anuidade ligada** |
| Travar a identidade tela × API × PDF (o mesmo objeto, sem recálculo) | ✅ `test_piloto_web_endpoints.py` (DRE = `serie[mes_referencia_steady]`) + script de coerência do gate |
| Cobrir a anuidade (elegibilidade derivada, pro-rata, só balcão, `mes_referencia_steady = 12`) | ✅ **30 testes** com "anuidade" no nome, em 4 arquivos |
| Suíte completa verde | ✅ ver o quadro abaixo |

> **✅ Estado MEDIDO no gate de fechamento (2026-07-24), não é estimativa.** Os comandos e as
> saídas reais:
>
> | Comando | Saída |
> |---|---|
> | `python -m pytest -q` (suíte completa) | `2059 passed, 86 skipped, 22 warnings in 400.29s` — **0 falhas** |
> | `python -m pytest tests/contracts -q` | `175 passed` |
> | `python -m pytest tests/contracts/test_viabilidade_golden.py -q` | `133 passed` |
> | `python -m pytest tests -q -k anuidade` | `30 passed, 2115 deselected` |
> | `python -m ruff check src web tests` | `All checks passed!` |
> | `python -m mypy src/` | `Success: no issues found in 113 source files` |
> | `cd web ; npm run lint / test / build` | `tsc` sem erro · `77 passed` · `built` |
>
> O parágrafo anterior desta seção dizia que o golden estava defasado em R$ 282.015,62 e que não
> existia teste de anuidade. Isso valia no momento em que foi escrito (frentes em paralelo) e
> **deixou de valer**: o golden foi re-medido com a anuidade ligada e hoje pina R$ 288.257,57.
> Arquivos com cobertura de anuidade: `tests/contracts/test_viabilidade_golden.py`,
> `tests/unit/dimensionamento/test_viabilidade_ponto.py`, `tests/unit/test_piloto_web_endpoints.py`
> e `tests/unit/test_viabilidade_charts.py`.

**Critério de aceite do ciclo:** o caso golden bate número a número **com a anuidade ligada**; a
suíte fecha verde; e não existe nenhuma fórmula financeira fora de `simulador.py`.

---

## Pendente de decisão humana

Nada aqui bloqueia a entrega técnica; tudo aqui muda a **conclusão** que a ferramenta entrega.
Detalhe completo em `PREMISSAS_VIABILIDADE.md` §9 e §10.

| # | Pendência | Quem decide | Por que importa |
|---|---|---|---|
| 1 | **Nível da folha: 17% × 25-26%** (BLK-VIAB-11, 6 DREs reais, CV 0,16) | Controladoria + Felipe | A 26%, o EBITDA do Boulevard cai de 39,26% para 30,26% e o payback vai de **28 para 54 meses** — a unidade deixaria de atender o critério de 36 meses, e o VPL @ 12% a.a. viraria negativo. É a pendência de maior impacto do ciclo. |
| 2 | **Taxa de desconto do VPL** (12% a.a. é default provisório) | Comitê | Não há WACC formalizado. Muda o VPL (hoje R$ 986.172,80); não muda payback, EBITDA nem TIR. |
| 3 | **Taxa de franquia: R$ 160.000 × R$ 140.000** (planilha `Simulador!R10` e `docs/modelo_dimensionamento_expansao.md:276` dizem 140.000) | Felipe + Comitê | Mantido 160.000 por decisão; agora **editável pelo operador**. A R$ 140.000 o acumulado M60 e o VPL ganham +R$ 20.000; payback não muda. |
| 4 | **Ticket por studio deslocado um degrau**: a tela usa `[147,157,167,177]`, a planilha `Simulador!J9` usa `[137,147,157,167]` | Felipe | A R$ 137 o payback do Boulevard vai de 28 para 34 meses. Não corrigido neste ciclo — é régua comercial, não engenharia. |
| 5 | **Linhas da planilha ainda ausentes do motor**: **matrícula** (`Simulador!J11`) e **múltiplo de valuation 1,5×** (`Simulador!R11`) como valor terminal | Comitê + DEC | As duas **aumentariam** o resultado. A omissão é conservadora, mas é a primeira diferença a checar ao comparar com números vindos do Excel. **A anuidade saiu desta pendência** — foi decidida e implementada (ver a linha "RESOLVIDA" abaixo). |
| 6 | **`SIM_IMPOSTO_FATURAMENTO = 0,16` segue órfã e desligada** | Controladoria | Sem fonte rastreável. Ligá-la trocaria R$ 19.073/mês por R$ 46.121/mês de imposto (+R$ 27,0 mil). Não ligar sem gate. |
| 7 | **`SIM_STUDIOS_DEFAULT` continua declarada e sem nenhum consumidor** (re-verificado no fechamento, 2026-07-24) | Felipe | `SIM_CUSTO_STUDIO` **deixou de ser órfã neste ciclo**: `app.py::_premissas_do_body` soma `n_studios * SIM_CUSTO_STUDIO` a `outros_fixos_mes` (medido no POST real: `n_studios=2` -> custos fixos R$ 68.150,00 -> R$ 80.150,00, ou seja -R$ 12.000 no EBITDA). Resta só `SIM_STUDIOS_DEFAULT`, que nada lê: ou vira o default da tela, ou sai. |

### RESOLVIDA — Anuidade (`Simulador!J10`), 2026-07-24

Era a pendência 5 deste quadro ("pendente de Comitê + DEC") e o texto **ficou falso**: a decisão
existe. **Felipe (dono do produto) decidiu e confirmou a periodicidade em 2026-07-24.** Estado
atual:

| O que | Estado |
|---|---|
| **Decidida** | R$ 99 **uma vez por ano** por aluno de **balcão** que completa 12 meses. Agregador não paga. Elegibilidade **derivada do churn** (`0,94¹²` = 47,59%). Reconhecimento **pro-rata mensal** (99/12) a partir do mês 12. |
| **Implementada** | `SIM_ANUIDADE_VALOR = 99.0` + `_MES_INICIO` / `_APENAS_BALCAO` / `_ELEGIVEL_PCT` / `_PRO_RATA` em `config.py`; mecânica em `simulador.py` (linha `receita_anuidade` da série e `receita_por_aluno_total` do break-even). |
| **Exposta no payload** | `premissas.anuidade_valor`, `.anuidade_mes_inicio`, `.anuidade_apenas_balcao`, `.anuidade_elegivel_pct`, `.mes_referencia_steady`; `dre.receita_anuidade`, `.receita_liquida`, `.receita_pos_impostos`. O operador vê a linha — não um faturamento maior sem causa, que era a objeção nº 1 do gate de QA. |
| **Documentada** | `PREMISSAS_VIABILIDADE.md` §2.1 (regra + o porquê de cada escolha) e §15 (caso de referência re-medido); `docs/nota_impacto_fin_viab_01.md` (antes × depois + delta isolado da anuidade). |
| **Consequência estrutural** | O mês de referência do steady-state passa de `maturacao_meses` (8) para `max(maturacao_meses, anuidade_mes_inicio)` = **12**. Servido em `premissas.mes_referencia_steady`; **ninguém recalcula** — foi assim que o waterfall do PDF passou a plotar um mês diferente do card ao lado. |
| **Coberta por teste** | ✅ **sim** — 30 testes com "anuidade" no nome (`pytest tests -k anuidade`), em 4 arquivos: o golden de `tests/contracts/`, `test_viabilidade_ponto.py`, `test_piloto_web_endpoints.py` e `test_viabilidade_charts.py`. Cobrem a elegibilidade derivada do churn, o pro-rata, a exclusão do agregador, a aditividade mês a mês e `mes_referencia_steady = 12`. |

**O gate de QA estava certo no resto.** Ele apontou dois defeitos reais — as três faixas do
aluguel-teto sumindo no PDF e o waterfall plotando um mês diferente do card ao lado — e os dois
foram corrigidos. O que ele errou foi **desligar a anuidade** (`SIM_ANUIDADE_VALOR = 0.0`) por não
conseguir verificar a aprovação: a aprovação existia. As correções do QA **não** devem ser
desfeitas.

---

## Decisões do dono do produto já tomadas (não rediscutir)

- Folha = **17% do faturamento bruto** (`SIM_FOLHA_PCT`), já ativa no núcleo.
- **Anuidade LIGADA** = R$ 99 **por ano** por aluno de **balcão** que completa 12 meses; agregador
  não paga; elegibilidade derivada do churn; reconhecimento pro-rata mensal; steady-state no
  **mês 12**. Decidida por Felipe em 2026-07-24 — **não rediscutir**.
- Taxa de franquia fica **R$ 160.000**, mas passa a ser **editável pelo operador**.
- Break-even canônico = **alunos totais** com o mix 69/31 escalando.
- Aluguel-teto = **% do faturamento**; as três faixas ficam; o canônico é **30% (exceção)**.
- Retorno padrão = **desalavancado**; equity é visão secundária, nunca no mesmo KPI.
- **Intocados:** horizonte de 60 meses, regime de Lucro Presumido e aluguel como input manual.

## Escopo explicitamente fechado

Valor do aluguel (input do operador), fórmulas de renda per capita e domiciliar, Residual Fitness
(não vira regra de viabilidade), contagem de concorrentes, metodologia de p10/p90, botão
"Aprovado para comitê", horizonte de 60 meses e regime tributário.

---

## Artefatos do ciclo

| Documento | Para quem |
|---|---|
| `PREMISSAS_VIABILIDADE.md` | Referência técnica — todo parâmetro do simulador com default, fonte, autoridade e onde vive. |
| `docs/nota_impacto_fin_viab_01.md` | Comitê — como a conclusão do Boulevard muda, com antes × depois e delta isolado. |
| `STATUS_ORQUESTRACAO.md` | Este documento — estado do ciclo por fase. |
| `web/README.md` (seção de viabilidade) | Quem opera e mantém o piloto web. |
| `tasks/backlog.md` (BLK-VIAB-11) | Registro de que a folha percentual foi ativada e o que sobrou pendente. |
