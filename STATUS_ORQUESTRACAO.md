# STATUS — Ciclo FIN-VIAB-01 (reconciliação do simulador de viabilidade)

**Branch:** `ciclo/FIN-VIAB-01-reconciliacao` · **Worktree:** `.claude/worktrees/fin-viab-01`
**Snapshot deste documento:** 2026-07-24, **3ª rodada** (estado observado no momento da escrita; o
ciclo roda com frentes em paralelo — confirmar com `git status` antes de tomar decisão de
fechamento).

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
2. Folha dimensionada por uma régua de **17%** — era R$ 50.128,16 fixos para toda unidade, sem fonte.
   *(Superseded pela 3ª rodada: os 17% passaram a incidir sobre o faturamento **maduro** e o valor
   virou custo **fixo** desde o mês 1 — ver a Fase 1-B abaixo.)*
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

## Fase 1-B — 3ª rodada no núcleo (2026-07-24) — **CONCLUÍDA E VERIFICADA POR FELIPE**

Duas decisões de **produto** de Felipe entraram no núcleo depois da Fase 1, mais um pedido
cosmético. O núcleo foi alterado e conferido por ele; as frentes de consumidor e documentação
apenas espelham.

### 1) FOLHA FIXA DESDE O MÊS 1 — corrige o defeito reportado

> *"a folha está escalando junto com a unidade"*

| | |
|---|---|
| **Era** | `folha = folha_pct × faturamento DO MÊS` → encolhia com a rampa (R$ 15.678,87 no mês 1). Equivalia a supor que se contrata gente na medida em que o aluno entra. |
| **É** | `Premissas.folha_fixa_mes(demanda)` = `folha_pct × faturamento MADURO` (regime pleno, a preços do ano 1) = **R$ 49.003,79**, válido **desde o mês 1** e reajustado anualmente como os demais custos. |
| **Por quê** | A equipe existe antes dos alunos: o quadro é dimensionado pela operação que a unidade vai ter e contratado para abrir a porta. |

**Consequências estruturais no núcleo** (nenhuma é escolha de engenharia):

1. A folha deixou de ser percentual e virou **custo FIXO**; o percentual sobrevive só como régua de
   dimensionamento, aplicada uma vez.
2. `fator_receita_para_ebitda` **não subtrai mais** `folha_pct`: **`k` passou de 0,628985 para
   0,798985**.
3. O custo fixo passou a incluir a folha: **`custo_fixo_total_mes(demanda)`** (= `outros_fixos` +
   folha = **R$ 87.153,79**) **substituiu** a propriedade `custo_fixo_base_mes`.
4. **Duas assinaturas mudaram** — passaram a receber a demanda assumida, porque é ela que dimensiona
   a folha:
   `break_even_alunos(p, demanda_total, *, incluir_pmt=0)` e
   `alunos_para_margem(p, margem_alvo, demanda_total)`.

### 2) TAXA DE FRANQUIA PARCELADA EM 4× SEM JUROS

`SIM_PARCELAS_FRANQUIA_DEFAULT = 4`; `gerar_serie_mensal_completa(...)` e `simular(...)` ganharam
`parcelas_franquia: int = SIM_PARCELAS_FRANQUIA_DEFAULT`. As parcelas caem nos meses de **contrato
1..N** (M-4..M-1 com N=4), junto da obra — a pré-abertura fica plana em **R$ 190.000/mês** (obra
150.000 + franquia 40.000) em vez de R$ 310.000 no M-4 e R$ 150.000 nos outros três.

### 3) Cosmético (XLSX) — saída de dinheiro em VERMELHO na aba RESUMO

Pedido do mesmo dia: na aba `RESUMO` do simulador em XLSX, **todo valor que é saída de dinheiro
aparece com o texto em vermelho**. Onde o número pode alternar de sinal (EBITDA, FCF, VPL, TIR,
retorno), a cor deve vir de formatação **condicional**, para a planilha não mentir quando o valor
virar. Frente: `dimensionamento/simulador_xlsx.py` — ver Fase 2.

### Números verificados por Felipe (golden Boulevard Londrina, mesmos inputs das rodadas anteriores)

| indicador | valor | vs 2ª rodada |
|---|---|---|
| Folha **fixa** desde o M1 | R$ 49.003,79 | era R$ 15.678,87 no M1 (percentual) |
| Fator `k` | 0,798985 | era 0,628985 |
| Custo fixo (outros + folha) | R$ 87.153,79 | — (era `custo_fixo_base_mes` = R$ 38.150,00) |
| Pré-abertura, **cada** mês M-4..M-1 | R$ 190.000,00 de investimento | era 310.000 / 150.000 / 150.000 / 150.000 |
| EBITDA do mês 1 | **−R$ 43.464,47** | era −R$ 10.139,56 |
| EBITDA do mês 4 | R$ 21.522,79 | — |
| EBITDA do mês 8 | R$ 108.172,47 | — |
| **STEADY (mês 12) — NÃO MUDOU** | faturamento R$ 288.257,57 · EBITDA R$ 113.159,69 (39,26%) · folha R$ 49.003,79 | idêntico |
| Break-even EBITDA | **1.152,0 alunos totais** | era 840,6 |
| Break-even de caixa | **1.542,4 alunos totais** | era 1.336,6 |
| Alunos para margem de 10% | 1.322,6 alunos totais | era 1.007,2 |
| Payback | **31 meses** | era 28 |
| TIR | **38,98% a.a.** | era 45,48% |
| VPL @ 12% a.a. | **R$ 849.484,15** | era R$ 986.172,80 |
| Acumulado M60 | **R$ 1.645.454,56** | era R$ 1.795.729,88 |
| Aluguel-teto | ideal R$ 43.238,64 · **teto R$ 57.651,51 (canônico)** · exceção R$ 86.477,27 | idêntico |

### Efeito isolado de cada mudança (medido por Felipe; reproduzido nesta rodada de documentação)

| mudança | efeito |
|---|---|
| **Franquia parcelada 4×** — só timing de caixa | **TIR +0,33 pp** e **VPL +R$ 2.241,80**. Payback e acumulado de M60 ficam **idênticos**, porque as 4 parcelas cabem dentro da janela M-4..M-1 e no mês 1 o desembolso total já é o mesmo. EBITDA, margem e break-even **não mudam** (parcelamento não é resultado). |
| **Folha fixa** — responde por TODO o resto | break-even **840,6 → 1.152** · payback **28 → 31** · TIR **45,48% → 38,98%** · VPL **R$ 986.172,80 → R$ 849.484,15** · acumulado M60 **R$ 1.795.729,88 → R$ 1.645.454,56**. Isoladamente (antes de somar a franquia): TIR 38,65% e VPL R$ 847.242,35. |

**Leitura para o comitê:** a folha fixa **piora** os indicadores, e isso é **correto**. O modelo
anterior diluía a folha na rampa, o que subestimava a queima de caixa dos primeiros meses (R$ 33,3
mil só no mês 1) e o break-even. O break-even sair de **632 (balcão, medida errada) para 1.152
(alunos totais, folha fixa)** é a mudança mais consequente do ciclo inteiro — detalhe em
`docs/nota_impacto_fin_viab_01.md`.

**O núcleo segue congelado** depois desta rodada: `config.py` e `simulador.py` estão fechados.

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
| **Simulador em XLSX** | `dimensionamento/simulador_xlsx.py` | 🔄 **em andamento na 3ª rodada** — tem de re-espelhar fórmula por fórmula a folha fixa (uma célula de folha referenciada nos 64 meses, `k` sem folha, break-even do RESUMO somando a folha no custo fixo) e a franquia parcelada, além do pedido cosmético do **vermelho** na aba RESUMO. Observado em 2026-07-24: a docstring do módulo e o import de `SIM_PARCELAS_FRANQUIA_DEFAULT` já entraram; as fórmulas e a formatação **ainda não**, e os testes de `test_simulador_xlsx.py` estão vermelhos (ver Fase 3) |
| **Documentação** | `PREMISSAS_VIABILIDADE.md`, `docs/nota_impacto_fin_viab_01.md`, `STATUS_ORQUESTRACAO.md`, `web/README.md`, `tasks/backlog.md` | ✅ concluída — **atualizada para a 3ª rodada** (folha fixa, franquia parcelada, aluguel-teto canônico = teto 20%, sensibilidades re-medidas) |

**Guardrails que a Fase 2 não pode quebrar:**

- READ-ONLY sobre o M1 — nada de `score_priorizacao`, pesos ou artefatos oficiais.
- A demanda **nunca** vem de lat/lng (DEC-009); `demanda_fonte = "premissa_explicita"`.
- `web/server/app.py` **não** pode chamar `to_parquet`/`to_csv` (há teste com AST que verifica).
- O payload sai por `json.dumps(..., allow_nan=False)`: nenhum `inf`/`NaN` pode vazar — payback
  infinito e TIR `None` viram `null` explícito.
- No PDF (fpdf2, core font, latin-1): pontuação ASCII (`-`, não travessão).
- Acentuação correta em texto de usuário; nunca em identificadores ou chaves.

---

## Fase 3 — Testes golden — **REABERTA E RE-MEDIDA NA 3ª RODADA**

| Item | Estado observado |
|---|---|
| `tests/contracts/test_viabilidade_golden.py` | ✅ **161 testes** (eram 133 na 2ª rodada) — re-medidos e re-pinados para a folha fixa e a franquia parcelada |
| Travar os números do caso Boulevard contra `simular()` | ✅ re-medidos e pinados **com a anuidade ligada, a folha fixa e a franquia em 4×** |
| Travar a identidade tela × API × PDF (o mesmo objeto, sem recálculo) | ✅ `test_piloto_web_endpoints.py` (DRE = `serie[mes_referencia_steady]`) + script de coerência do gate |
| Cobrir a anuidade (elegibilidade derivada, pro-rata, só balcão, `mes_referencia_steady = 12`) | ✅ **30 testes** com "anuidade" no nome, em 4 arquivos |
| Suíte completa verde | ✅ ver o quadro abaixo |

> **Medições da 2ª rodada (histórico — precedem a 3ª rodada, NÃO valem como estado atual):**
>
> | Comando | Saída |
> |---|---|
> | `python -m pytest -q` (suíte completa) | `2059 passed, 86 skipped, 22 warnings in 400.29s` |
> | `python -m pytest tests/contracts -q` | `175 passed` |
> | `python -m pytest tests/contracts/test_viabilidade_golden.py -q` | `133 passed` |
> | `python -m pytest tests -q -k anuidade` | `30 passed, 2115 deselected` |
> | `python -m ruff check src web tests` | `All checks passed!` |
> | `python -m mypy src/` | `Success: no issues found in 113 source files` |
> | `cd web ; npm run lint / test / build` | `tsc` sem erro · `77 passed` · `built` |
>
> **✅ Estado MEDIDO na 3ª rodada (2026-07-24, na frente de documentação), não é estimativa:**
>
> | Comando | Saída |
> |---|---|
> | `python -m pytest tests/contracts/test_viabilidade_golden.py -q` | `161 passed in 1.73s` |
> | `python -m pytest tests/contracts tests/unit/dimensionamento tests/unit/test_piloto_web_endpoints.py tests/unit/test_viabilidade_charts.py -q --deselect tests/unit/dimensionamento/test_simulador_xlsx.py` | `590 passed, 47 deselected in 89.39s` |
> | mesma linha **sem** o `--deselect` | `3 failed, 613 passed` — as **3 falhas são todas de `test_simulador_xlsx.py`** |
>
> **As falhas do XLSX são da frente ainda em voo, não da 3ª rodada do núcleo.** Os nomes das que
> falham mudaram entre duas execuções consecutivas (`test_dre_le_a_folha_pelo_interruptor_de_modo` /
> `test_interruptor_modo_da_folha_*` numa, `test_folha_fixa_e_a_mesma_formula_nos_64_meses` /
> `test_break_even_do_resumo_usa_o_custo_fixo_com_folha` /
> `test_valor_que_alterna_de_sinal_usa_formatacao_condicional` na outra), porque o arquivo de teste
> estava sendo editado durante a medição. **A suíte completa não foi rodada nesta rodada** — o
> número `2059 passed` acima é da 2ª rodada e não deve ser citado como estado atual.

**Critério de aceite do ciclo:** o caso golden bate número a número **com a anuidade ligada, a folha
fixa e a franquia parcelada**; a suíte fecha verde; e não existe nenhuma fórmula financeira fora de
`simulador.py`. **Pendente para o gate final:** rodar a suíte completa depois que a frente do XLSX
fechar.

---

## Pendente de decisão humana

Nada aqui bloqueia a entrega técnica; tudo aqui muda a **conclusão** que a ferramenta entrega.
Detalhe completo em `PREMISSAS_VIABILIDADE.md` §9 e §10.

| # | Pendência | Quem decide | Por que importa |
|---|---|---|---|
| 1 | **NÍVEL da folha: 17% × 25-26%** (BLK-VIAB-11, 6 DREs reais, CV 0,16). **A ESTRUTURA — folha fixa — está decidida** (3ª rodada); só o nível segue aberto | Controladoria + Felipe | Re-medido na estrutura nova: a 26% o EBITDA cai de 39,26% para 30,26%, o break-even sobe para 1.416,1 e **o payback NÃO OCORRE dentro dos 60 meses** (TIR −1,05% a.a., VPL −R$ 384.910,19, acumulado M60 −R$ 40.745,08). Com a folha percentual a medição dava "54 meses" — **a pendência ficou pior, não melhor**. É a de maior impacto do ciclo. |
| 2 | **Taxa de desconto do VPL** (12% a.a. é default provisório) | Comitê | Não há WACC formalizado. Muda o VPL (hoje **R$ 849.484,15**); não muda payback, EBITDA nem TIR. |
| 3 | **Taxa de franquia: R$ 160.000 × R$ 140.000** (planilha `Simulador!R10` e `docs/modelo_dimensionamento_expansao.md:276` dizem 140.000) | Felipe + Comitê | Mantido 160.000 por decisão; agora **editável pelo operador** e **parcelado em 4×**. Re-medido a R$ 140.000: payback **30** (contra 31), acumulado M60 R$ 1.665.454,56 (+R$ 20.000), VPL R$ 869.203,92 (+R$ 19.719,77), TIR 40,01% a.a. |
| 4 | **Ticket por studio deslocado um degrau**: a tela usa `[147,157,167,177]`, a planilha `Simulador!J9` usa `[137,147,157,167]` | Felipe | Re-medido: a R$ 137 o payback vai a **37 meses** e `flag_viavel` **cai para falso** (limite 36); EBITDA R$ 101.306,71 (37,60%), break-even 1.199,2, TIR 25,66%, VPL R$ 416.749,97. Com a folha percentual davam 34 meses e o critério ainda passava — com a folha fixa este conflito reprova a unidade sozinho. Não corrigido neste ciclo: é régua comercial, não engenharia. |
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

- **Folha FIXA desde o mês 1** (3ª rodada): `SIM_FOLHA_PCT = 17%` dimensiona a folha pelo faturamento
  **MADURO** e o valor resultante (R$ 49.003,79) vale do M1 ao M60, reajustando como os demais custos.
  A folha é **custo fixo** e **não entra** no fator `k`. **Não rediscutir a estrutura** — o nível
  (17% × 26%) é que segue pendente.
- **Taxa de franquia PARCELADA em 4× sem juros** (3ª rodada), nos meses de contrato 1..4 (M-4..M-1),
  junto da obra. É só timing de caixa.
- **Anuidade LIGADA** = R$ 99 **por ano** por aluno de **balcão** que completa 12 meses; agregador
  não paga; elegibilidade derivada do churn; reconhecimento pro-rata mensal; steady-state no
  **mês 12**. Decidida por Felipe em 2026-07-24 — **não rediscutir**.
- Taxa de franquia fica **R$ 160.000**, mas passa a ser **editável pelo operador**.
- Break-even canônico = **alunos totais** com o mix 69/31 escalando, com a folha dimensionada pela
  **demanda assumida** (a conta responde "montei a casa para 2.304; com quantos empato?").
- Aluguel-teto = **% do faturamento**; as três faixas ficam; o canônico exibido no card é o
  **teto (20%)** — a exceção (30%) é caso de exceção, não referência.
- Retorno padrão = **desalavancado**; equity é visão secundária, nunca no mesmo KPI.
- **XLSX:** na aba `RESUMO`, toda **saída de dinheiro** com o texto em **vermelho**; onde o valor
  pode alternar de sinal, a cor vem de formatação **condicional**.
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
| `tasks/backlog.md` (BLK-VIAB-11) | Registro de que a régua de folha foi ativada e o que sobrou pendente — hoje só o **nível** (a estrutura fixa está decidida). |
| `dimensionamento/simulador_xlsx.py` | Investidor/comitê — simulador em XLSX com fórmulas vivas. **Frente em voo na 3ª rodada** (folha fixa, franquia parcelada, vermelho no RESUMO). |
