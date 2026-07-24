# Premissas do Simulador de Viabilidade

> **Fonte única.** Todo coeficiente financeiro do Motor de Viabilidade vive em
> `src/motor_expansao/dimensionamento/config.py` e é consumido por
> `src/motor_expansao/dimensionamento/simulador.py`. Backend, frontend e PDF apenas
> **leem** o resultado — nenhuma fórmula financeira pode ser reescrita fora do simulador.
>
> Ciclo: **FIN-VIAB-01** (reconciliação do simulador) · Atualizado em **2026-07-24**
> Guardrail permanente: camada **paralela**, READ-ONLY sobre o M1 (DEC-001/DEC-008/DEC-009).

---

## 1. Como ler este documento

| Coluna | O que significa |
|---|---|
| **parâmetro** | Nome da constante em `config.py` ou do campo em `Premissas` / na assinatura de `simular()`. |
| **default** | Valor vigente hoje no código. |
| **unidade** | `%` = fração decimal · `R$` = reais · `meses` · `un.` = unidades (alunos, parcelas). |
| **fonte** | De onde o número veio, com célula/linha rastreável quando existe. |
| **quem pode alterar** | Quem tem autoridade para mudar o valor (ver legenda abaixo). |
| **onde vive** | Arquivo e ponto de consumo. |

**Legenda de autoridade:**

- **Operador** — editável na tela de Viabilidade a cada simulação (não muda o default do sistema).
- **Felipe (dono do produto)** — decisão de produto; muda o default do sistema.
- **Controladoria** — gate contábil/fiscal; nível de custo e regime tributário.
- **Comitê + DEC** — muda a conclusão de go/no-go; exige decisão registrada.
- **Engenharia** — só refatoração; alterar o **valor** não é prerrogativa da engenharia.

---

## 2. Receita e demanda

| parâmetro | default | unidade | fonte | quem pode alterar | onde vive |
|---|---|---|---|---|---|
| `ticket_cheio` | — (input obrigatório) | R$/aluno/mês | planilha `Simulador!J9` (ver conflito **C** na §9) | Operador | `Premissas.ticket_cheio`; sidebar da Viabilidade |
| `SIM_MENSALIDADE_BALCAO` | `137` | R$/aluno/mês | `Simulador!J9`, cenário 0 studios | Felipe | `config.py`; **fallback do backend** quando o operador não informa ticket (`web/server/app.py`, `viabilidade_ponto.py`, `pages.py`, `backtest_dim.py`). A tela envia `147` — ver conflito **C** na §9 |
| `SIM_TICKET_AGREGADOR_FATOR` | `0.60` | % do ticket cheio | comentário original de `viabilidade_ponto.py` ("~60% do ticket"), formalizado no FIN-VIAB-01 | Felipe | `config.py` → `Premissas.ticket_agregador_fator` → `Premissas.ticket_agregador` |
| `SIM_TICKET_AGREGADOR` | `82` | R$/aluno/mês | aba `Simulador`, linha 11 | **congelado (legado)** | `config.py`; só alimenta `viabilidade()` legado e `ticket_agregador_absoluto` |
| `SIM_SHARE_BALCAO` | `0.69` | % dos alunos totais | mix real da rede (69 balcão / 31 agregadores) | Felipe | `config.py` → `Premissas.share_balcao`; payload `premissas.share_balcao` e `split` |
| `SIM_CHURN` | `0.06` | % ao mês | `Simulador!E12` | Controladoria | `config.py` → `Premissas.churn` |
| `SIM_INADIMPLENCIA` | `0.02` | % da receita | DRE (estava **hardcoded em dois lugares** antes do FIN-VIAB-01) | Controladoria | `config.py` → `Premissas.inadimplencia` |
| `SIM_PERSONAL_MES_RECEITA` | `5 000` | R$/mês | DRE linha 24 (receita fixa de personal) | Controladoria | `config.py` → `Premissas.personal_mes` |
| `SIM_ANUIDADE_VALOR` | `99` | R$/**ano** por aluno de balcão | `Simulador!J10` (linha "Anuidade / manutenção") | Felipe (dono do produto) | `config.py` → `Premissas.anuidade_valor`; payload `premissas.anuidade_valor` e `dre.receita_anuidade` |
| `SIM_ANUIDADE_MES_INICIO` | `12` | mês de operação | `Simulador!J12` ("mês de início da cobrança de taxas") | Felipe (dono do produto) | `config.py` → `Premissas.anuidade_mes_inicio`; payload `premissas.anuidade_mes_inicio`. **Também desloca o `mes_referencia_steady`** — ver §2.1 |
| `SIM_ANUIDADE_APENAS_BALCAO` | `True` | booleano | decisão de Felipe (2026-07-24): o agregador remunera por acesso, o aluno de Gympass/TotalPass não paga anuidade à academia | Felipe (dono do produto) | `config.py` → `Premissas.anuidade_apenas_balcao`; payload `premissas.anuidade_apenas_balcao` |
| `SIM_ANUIDADE_ELEGIVEL_PCT` | `None` (= **deriva do churn**) | % dos alunos de balcão | derivado, não arbitrado: `(1 − churn)^12` = `0,94^12` = **47,59%** | Felipe (dono do produto) | `config.py` → `Premissas.anuidade_elegivel_efetivo`; payload `premissas.anuidade_elegivel_pct` |
| `SIM_ANUIDADE_PRO_RATA` | `True` | booleano | decisão de Felipe (2026-07-24): reconhecimento mensal de `99 ÷ 12` a partir do mês 12 | Felipe (dono do produto) | `config.py` → `Premissas.anuidade_por_aluno_balcao_mes`; linha `receita_anuidade` da série |
| `demanda_total` | — (input obrigatório) | alunos totais | **premissa explícita do operador** (DEC-009 — nunca prevista pela geografia) | Operador | argumento de `simular()`; payload `demanda_premissa` / `demanda_fonte` |
| `SIM_ALUNOS_INICIAL` | `500` | alunos | `Simulador!E9` | Felipe | `config.py` → `Premissas.alunos_inicial` (piso da rampa) |
| `SIM_MATURACAO_MESES` | `8` | meses | `Simulador!E13` | Felipe | `config.py` → `Premissas.maturacao_meses`; entra no mês de *steady* junto com `SIM_ANUIDADE_MES_INICIO` — ver §2.1 |
| `SIM_ALUNOS_BALCAO_MATURIDADE` | `938` | alunos | `Simulador!E10` | **congelado (legado)** | `config.py`; só o caminho `viabilidade()` legado |
| `SIM_ALUNOS_AGREGADORES_MATURIDADE` | `651` | alunos | `Simulador!E11` | **congelado (legado)** | `config.py`; só o caminho `viabilidade()` legado |
| `rampa_apenas_balcao` | `False` | booleano | contrato de rampa do FIN-VIAB-01 | Engenharia (compat) | `Premissas`; `True` só nos adaptadores históricos |
| `ticket_agregador_absoluto` | `None` | R$/aluno/mês | compatibilidade com chamadas antigas | Engenharia (compat) | `Premissas`; quando preenchido, desliga o fator de 60% |

**Derivados (não são inputs — o motor calcula):** `ticket_agregador` (= `ticket_cheio × 0,60`),
`ticket_blended` (ticket médio por aluno **total**, já líquido de churn e inadimplência),
`contribuicao_por_aluno_total` e `receita_por_aluno_total` (mensalidade **+ anuidade** em regime
pleno — é a régua do break-even). No caso de referência: R$ 147,00 cheio → R$ 88,20 agregador →
**R$ 120,23 blended**.

### 2.1 Regra da anuidade (decidida por Felipe em 2026-07-24 — não rediscutir)

A anuidade é a linha `Simulador!J10` da planilha, que o motor nunca tinha implementado. Ela foi
**ligada** neste ciclo por decisão explícita do dono do produto, que confirmou também a
periodicidade. As cinco escolhas abaixo são de produto, e cada uma tem um porquê:

| Escolha | Por quê |
|---|---|
| **R$ 99 uma vez por ANO**, não por mês | Foi a periodicidade confirmada por Felipe. Ler J10 como mensal multiplicaria a linha por 12: ela viraria **~R$ 74,9 mil/mês** em vez de R$ 6,2 mil — **+R$ 68,7 mil/mês de faturamento inventado**, mais que a diferença entre viável e inviável. |
| **Só o balcão paga** (`apenas_balcao = True`) | O aluno de agregador (Gympass/TotalPass) não tem contrato com a academia: o agregador remunera **por acesso**. Cobrar anuidade dele seria inventar receita de um contrato que não existe. |
| **Elegibilidade derivada do churn**, não fixada à mão | Pedido literal de Felipe: "nem todos os alunos chegam a 12 meses". `(1 − churn)^12` = `0,94^12` = **47,59%**. Como é derivada, mexer no churn ajusta a elegibilidade sozinho — não há um número mágico paralelo para alguém esquecer de atualizar. `SIM_ANUIDADE_ELEGIVEL_PCT` continua existindo como escotilha: se for preenchido com um número, ele **vence** a derivação. |
| **Reconhecimento pro-rata mensal** (`99 ÷ 12` a partir do mês 12), não um lançamento único | Os aniversários dos alunos se espalham pelo ano inteiro. Um lançamento único no mês 12 criaria um **degrau falso** no caixa e no gráfico de FCF acumulado, deslocando o mês de virada do payback sem nenhum ganho de precisão econômica. Mesma lógica da simplificação do adicional de IRPJ (§11). |
| **O mês de referência do steady-state passa de 8 para 12** | Consequência estrutural, não escolha estética: só a partir do mês 12 o regime é pleno (alunos **maduros** *e* anuidade **em cobrança**). Se a DRE de steady continuasse no mês 8, ela ficaria sem a anuidade enquanto o break-even já a considera — duas réguas diferentes para o mesmo cenário, que é exatamente a classe de defeito que este ciclo existe para matar. |

**O mês é servido, não recalculado.** O motor devolve `mes_referencia_steady`
(= `max(maturacao_meses, anuidade_mes_inicio)` = **12**) e a API o expõe em
`premissas.mes_referencia_steady`. Tela, gráficos e PDF **leem daí**. Nenhum consumidor pode
inferir o mês de steady por conta própria — foi assim que o waterfall do PDF passou a plotar um
mês diferente do card ao lado no mesmo slide.

**No caso de referência:** elegibilidade **47,59%** → **R$ 3,9263** de anuidade por aluno de
balcão por mês → **R$ 6.241,94/mês** dentro de um faturamento de R$ 288.257,57 (**2,2%**).

---

## 3. Deduções e impostos sobre a receita

| parâmetro | default | unidade | fonte | quem pode alterar | onde vive |
|---|---|---|---|---|---|
| `SIM_DEVOLUCOES_PCT` | `0.005` | % do faturamento bruto | DRE `F30` | Controladoria | `config.py` → `Premissas.devolucoes_pct`; payload `premissas.deducoes_pct` |
| `SIM_PIS` | `0.0065` | % da receita líquida | Tributos `E38` | Controladoria | `config.py` → `Premissas.pis` |
| `SIM_COFINS` | `0.03` | % da receita líquida | Tributos `E40` | Controladoria | `config.py` → `Premissas.cofins` |
| `SIM_ISS` | `0.03` | % da receita líquida | Tributos `E42` | Controladoria | `config.py` → `Premissas.iss` |
| *(derivado)* `impostos_receita_pct` | `0.0665` | % da receita líquida | PIS + COFINS + ISS | — | `Premissas.impostos_receita_pct`; payload `premissas.impostos_receita_pct` |
| `SIM_IMPOSTO_FATURAMENTO` | `0.16` | % do faturamento bruto | **sem fonte rastreável** | ver §8 — **órfã, não ligar** | `config.py`; **não consumida** |

---

## 4. Custos operacionais

| parâmetro | default | unidade | fonte | quem pode alterar | onde vive |
|---|---|---|---|---|---|
| `SIM_ROYALTIES_PCT` | `0.08` | % da receita líquida | `Simulador!N11` (contrato de franquia) | Comitê + DEC | `config.py` → `Premissas.royalties_pct` |
| `SIM_MARKETING_PCT` | `0.02` | % da receita líquida | DRE `F63` | Controladoria | `config.py` → `Premissas.marketing_pct` |
| `SIM_MANUTENCAO_PCT` | `0.02` | % da receita líquida | DRE `F67` | Controladoria | `config.py` → `Premissas.manutencao_pct` |
| `SIM_CARTOES_PCT` | `0.0105` | % da receita líquida | DRE `F79` | Controladoria | `config.py` → `Premissas.cartoes_pct` |
| *(derivado)* `custo_variavel_pct` | `0.1305` | % da receita líquida | royalties + marketing + manutenção + cartões | — | `Premissas.custo_variavel_pct`; payload `premissas.custo_variavel_pct` |
| `SIM_FOLHA_PCT` | `0.17` | % do **faturamento bruto** | decisão de Felipe, 2026-07-24 — ver conflito **A** na §9 | Felipe + Controladoria | `config.py` → `Premissas.folha_pct`; linha `folha` da série |
| `SIM_PESSOAL_MES` | `50 128,16` | R$/mês | Fopag com encargos (DRE linha 55) | **congelado (legado)** | `config.py`; **não alimenta mais a folha** — só default de `viabilidade()`/`gerar_serie_mensal()` |
| `pessoal_mes_override` | `None` | R$/mês | escotilha de compatibilidade | Engenharia (compat) | `Premissas`; quando preenchido, a folha vira custo fixo e `folha_pct` é ignorado |
| `SIM_OUTROS_FIXOS_MES` | `38 150,00` | R$/mês | Excel, DRE linhas 52-59 e 69 (IPTU 2.000 + água/luz 17.000 + telefone 500 + limpeza 14.000 + tecnologia 2.150 + assessorias 2.500 + outros 2.000) | Controladoria | `config.py` → `Premissas.outros_fixos_mes` |
| `aluguel_mes` | — (input) | R$/mês | **input manual do operador** — escopo fechado, não é estimado pelo motor | Operador | `Premissas.aluguel_mes` |
| `SIM_CUSTO_PRE_OPERACIONAL_MES` | `0.0` | R$/mês | **explicitação de ausência** — hoje o modelo assume zero custo de contratação/treinamento/pré-venda | Felipe | `config.py` → `Premissas.custo_pre_operacional_mes`; linhas M-4..M-1 |
| `SIM_CUSTO_STUDIO` | `6 000,00` | R$/mês por studio | fopag adicional por studio extra | Felipe | `config.py`; **declarada e não consumida** — ver §8 |
| `SIM_STUDIOS_DEFAULT` | `0` | un. (0..3) | configuração padrão de unidade | Felipe | `config.py`; **declarada e não consumida** — ver §8 |

**Natureza do custo (explícita no resultado desde o FIN-VIAB-01):** variável (% da receita líquida),
folha (% do faturamento bruto) e fixo absoluto (outros fixos + aluguel + pré-operacional). O custo
operacional é **integral desde o mês 1** — não acompanha a rampa de alunos. As únicas variações
legítimas no tempo são a carência de aluguel e o reajuste anual.

---

## 5. IR/CSLL — Lucro Presumido

| parâmetro | default | unidade | fonte | quem pode alterar | onde vive |
|---|---|---|---|---|---|
| `SIM_BASE_PRESUMIDA_PCT` | `0.32` | % da receita bruta | Lucro Presumido, serviços (legislação) | Controladoria | `config.py` → `Premissas.base_presumida_pct` |
| `SIM_IRPJ_ALIQUOTA` | `0.15` | % da base presumida | legislação | Controladoria | `config.py` → `Premissas.irpj_aliquota` |
| `SIM_IRPJ_ADICIONAL_ALIQUOTA` | `0.10` | % da base excedente | legislação | Controladoria | `config.py` → `Premissas.irpj_adicional_aliquota` |
| `SIM_IRPJ_ADICIONAL_LIMITE_MES` | `20 000,00` | R$/mês | R$ 60.000/trimestre **rateado pro-rata mensal** — ver §11 | Controladoria | `config.py` → `Premissas.irpj_adicional_limite_mes` |
| `SIM_CSLL_ALIQUOTA` | `0.09` | % da base presumida | legislação | Controladoria | `config.py` → `Premissas.csll_aliquota` |
| `ir_modo` | `presumido_faixa` | enum | modo canônico do FIN-VIAB-01 | Controladoria | `Premissas.ir_modo`; `efetivo_legado` só nos adaptadores |
| `SIM_IR_EFETIVO` | `0.08` | % da receita líquida | Tributos `E44` (= 32% × 25%) | **congelado (legado)** | `config.py`; só no modo `efetivo_legado` |
| `SIM_CSLL_EFETIVO` | `0.0288` | % da receita líquida | Tributos `E46` (= 32% × 9%) | **congelado (legado)** | `config.py`; só no modo `efetivo_legado` |

**Regime tributário (Lucro Presumido) é escopo fechado.** No caso de referência o adicional de 10%
está ativo: base presumida = R$ 288.257,57 × 32% = R$ 92.242,42, acima do limite pro-rata de
R$ 20.000/mês → IR/CSLL = **R$ 29.362,42/mês**.

---

## 6. Investimento, financiamento, linha do tempo e retorno

| parâmetro | default | unidade | fonte | quem pode alterar | onde vive |
|---|---|---|---|---|---|
| `obra` | — (input) | R$ | CAPEX de obra, pago em parcelas **sem juros** (equity) | Operador | argumento de `simular()`; payload `investimento.obra` |
| `SIM_PARCELAS_OBRA_DEFAULT` | `4` | parcelas | cronograma padrão de obra (M-4..M-1) | Operador | `config.py` → argumento `parcelas_obra` |
| `equipamentos` | — (input) | R$ | CAPEX financiado (Price) | Operador | argumento de `simular()`; payload `investimento.equipamentos` |
| `prazo_equipamentos` | — (input) | meses | contrato de financiamento | Operador | argumento de `simular()` |
| `juros_equipamentos_am` | — (input) | % ao mês | contrato de financiamento | Operador | argumento de `simular()` |
| `SIM_TAXA_FRANQUIA` | `160 000,00` | R$ | conflito **B** na §9 (planilha diz 140.000) | Felipe + Comitê | `config.py` → argumento `taxa_franquia`; **editável pelo operador** |
| `SIM_CAPEX_DEFAULT` | `2 340 000` | R$ | `Simulador!R9`, cenário 0 (`FC!C11:C16`) | **congelado (legado)** | `config.py`; só o caminho `viabilidade()` legado |
| `SIM_ALUGUEL_MES` | `20 000` | R$/mês | `Simulador!N9` | **congelado (legado)** | `config.py`; o aluguel real é input manual |
| `SIM_MESES_PRE_ABERTURA` | `4` | meses | linha do tempo M-4..M-1 | Felipe | `config.py` → `Premissas.meses_pre_abertura` |
| `SIM_HORIZONTE_MESES` | `60` | meses | **escopo fechado** (horizonte de 60 meses) | Comitê + DEC | `config.py` → `Premissas.horizonte_meses` |
| `SIM_CARENCIA_ALUGUEL_MESES` | `0` | meses | negociação do contrato de locação; conta a partir de **M-4** (entrega), não da abertura | Operador | `config.py` → `Premissas.carencia_aluguel_meses` |
| `SIM_REAJUSTE_TICKET_AA` | `0.04` | % ao ano | premissa de reajuste (degrau anual a partir do mês 13) | Felipe | `config.py` → `Premissas.reajuste_ticket_aa` |
| `SIM_REAJUSTE_ALUGUEL_AA` | `0.04` | % ao ano | idem | Felipe | `config.py` → `Premissas.reajuste_aluguel_aa` |
| `SIM_REAJUSTE_CUSTOS_AA` | `0.04` | % ao ano | idem (aplica a `outros_fixos`) | Felipe | `config.py` → `Premissas.reajuste_custos_aa` |
| `SIM_TAXA_DESCONTO_AA` | `0.12` | % ao ano | **provisório — pendente de aval** (ver §10) | Comitê + DEC | `config.py` → `Premissas.taxa_desconto_aa`; VPL |
| `SIM_VALOR_RESIDUAL_MES_60` | `0.0` | R$ | **explicitação de ausência** — o corte em 60 meses ignora valor terminal | Comitê + DEC | `config.py` → `Premissas.valor_residual_mes_60` |
| `SIM_CAPEX_RENOVACAO` | `0.0` | R$ | **explicitação de ausência** — o corte em 60 meses ignora CAPEX de renovação | Comitê + DEC | `config.py` → `Premissas.capex_renovacao` |
| `SIM_MARGEM_VIAVEL_MIN` | `0.10` | % de margem EBITDA | critério de `flag_viavel` (era literal em `simulador.py`) | Comitê + DEC | `config.py` |
| `SIM_PAYBACK_VIAVEL_MAX` | `36` | meses | critério de `flag_viavel` (era literal em `simulador.py`) | Comitê + DEC | `config.py` |

**A PMT é nominal e não sofre reajuste.** O reajuste anual é um degrau por ano cheio a partir do
mês 13; a pré-abertura não reajusta.

**Óticas de retorno.** O padrão exibido é o **desalavancado** (resultado antes da PMT ÷ investimento
cheio = CAPEX + taxa de franquia). O retorno de **equity** (resultado depois da PMT ÷ obra + franquia)
é visão secundária e **nunca aparece no mesmo KPI** — o ROIC anterior misturava numerador
desalavancado com denominador de capex cheio, e o modelo se beneficiava do financiamento duas vezes.

---

## 7. Aluguel-teto

| parâmetro | default | unidade | fonte | quem pode alterar | onde vive |
|---|---|---|---|---|---|
| `SIM_ALUGUEL_TETO_IDEAL` | `0.15` | % do faturamento bruto | régua de ocupação da rede | Felipe | `config.py` → `aluguel_teto_clusters()` |
| `SIM_ALUGUEL_TETO_TETO` | `0.20` | % do faturamento bruto | idem | Felipe | idem |
| `SIM_ALUGUEL_TETO_EXCECAO` | `0.30` | % do faturamento bruto | idem — **é o valor canônico exibido** | Felipe | idem; payload `aluguel_teto.canonico` |

Base de cálculo: **faturamento bruto de steady-state** — o do `mes_referencia_steady` (mês 12),
anuidade inclusa. É a única definição de aluguel-teto do sistema (tela **e** PDF), e as **três
faixas** viajam no payload: sumir com ideal e teto no PDF, deixando só o canônico, foi um dos
defeitos apontados pelo QA deste ciclo. A inversão por margem EBITDA-alvo (`aluguel_teto()`) está
**deprecated**: devolvia R$ 105.813,13 onde a tela mostrava R$ 55.535,18 no mesmo cenário.

No caso de referência: ideal R$ 43.238,64 · teto R$ 57.651,51 · **exceção/canônico R$ 86.477,27**.

---

## 8. Constantes órfãs

São constantes que **existem em `config.py` mas não têm fonte rastreável e não estão ligadas ao
motor**. Ficam documentadas aqui exatamente para que ninguém as "conserte" ligando-as.

### `SIM_IMPOSTO_FATURAMENTO = 0.16`

- **Estado:** órfã. Não é importada por `simulador.py` nem por nenhum consumidor. Mantida só para
  não quebrar `import` de terceiros.
- **Fonte:** **nenhuma**. Não há célula da planilha nem linha de DRE que produza 16%. O regime
  vigente é PIS + COFINS + ISS (`Tributos E38/E40/E42`), que **têm** célula rastreável.
- **A armadilha:** ela parece uma alíquota "consolidada" mais simples, mas a base é outra —
  16% do **faturamento bruto** contra 6,65% da **receita líquida**. Ligá-la no caso de referência
  trocaria **R$ 18.373/mês por R$ 44.428/mês** na base antiga do simulador (**+R$ 26 mil/mês**);
  na base corrigida de hoje (faturamento R$ 288.257,57) a troca seria de **R$ 19.073,28 para
  R$ 46.121,21** — **+R$ 27.047,93/mês**, o que sozinho derrubaria o EBITDA de R$ 113,2 mil para
  R$ 86,1 mil e a margem de 39,3% para ~29,9%.
- **Decisão:** **não ligar** sem gate humano da controladoria. Se um dia for ligada, é substituição
  de regime — PIS/COFINS/ISS teriam de sair juntos, não somar.

### `SIM_TICKET_AGREGADOR = 82`

- **Estado:** semi-órfã. Ainda é importada, mas só como **piso absoluto** para chamadas históricas
  (`viabilidade()` e `aluguel_teto()` legados) que não passam ticket.
- **Fonte:** "aba `Simulador`, linha 11 (~R$82/aluno/mês)" — uma **leitura aproximada**, sem célula
  nomeada; a planilha não tem um driver de ticket de agregador equivalente ao `J9` do balcão.
- **A armadilha:** era um valor **absoluto e desacoplado** do ticket cheio. Quando o operador subia
  o ticket de R$ 147 para R$ 177 (studios), o agregador degradava silenciosamente de 55,8% para
  46,3% do ticket cheio — ninguém via, e a receita ficava sistematicamente subestimada nos cenários
  de ticket alto. O caminho canônico é `SIM_TICKET_AGREGADOR_FATOR = 0,60`.
- **Decisão:** manter congelada. Nenhum código novo deve importá-la.

### `SIM_CUSTO_STUDIO = 6 000,00` e `SIM_STUDIOS_DEFAULT = 0`

- **Estado:** órfãs. Verificado em 2026-07-24: **nenhum consumidor** em `src/`, `web/` ou `tests/`.
- **Fonte:** "fopag adicional por studio extra" — sem célula da planilha nem linha de DRE.
- **A armadilha:** a tela **tem** um seletor de studios (0..3), o que dá a impressão de que o custo
  do studio já entra no DRE. **Não entra.** Hoje os studios só afetam o **ticket** (via
  `TICKET_POR_STUDIO` no frontend), nunca o custo. Uma unidade com 3 studios roda com a mesma folha
  e o mesmo custo fixo de uma sem nenhum.
- **Decisão:** ou ligar `SIM_CUSTO_STUDIO` no custo fixo (mudança de conclusão → Felipe), ou removê-la.
  Manter declarada e desligada é o pior dos mundos, porque parece implementada.

---

## 9. Conflitos abertos

Três divergências **conhecidas, não resolvidas**, entre o código e a fonte documental. Nenhuma
bloqueia o ciclo; todas precisam de decisão nomeada.

### (a) FOLHA — 17% (código) × 25-26% (DREs reais)

| | |
|---|---|
| **O que o código faz hoje** | `SIM_FOLHA_PCT = 0,17` do faturamento bruto, **ativado no FIN-VIAB-01** por decisão de Felipe (2026-07-24). |
| **O que a evidência diz** | O **BLK-VIAB-11** apurou **25-26%** em **6 DREs gerenciais reais** (Augusta, Bangu, Cabo Frio, Icaraí, Praia Grande, Vila Guilherme; jun-jul/2026). Folha real de **R$ 38 mil a R$ 99 mil/mês**, **estável como % da receita bruta (CV 0,16)** e instável por m² (CV 0,34). SP e RJ praticamente idênticos → sem ajuste regional. |
| **Por que 17% mesmo assim** | 17% mantém o **nível** próximo do status quo (R$ 50.128 fixos ÷ R$ 277.676 = 18,05% no caso antigo). A mudança do FIN-VIAB-01 é de **estrutura** — a folha passa a escalar com o volume — não de nível. Trocar as duas coisas ao mesmo tempo tornaria impossível atribuir o delta. |
| **Impacto do nível** | A 17%, a folha do caso golden é **R$ 49.003,79** e o EBITDA fecha em **R$ 113.159,69 (39,26%)**. A 26%, a folha vai a **R$ 74.946,97** e o EBITDA cai para **R$ 87.216,50 (30,26%)** — o payback salta de **28 para 54 meses**, o acumulado de M60 despenca de R$ 1.795.729,88 para **R$ 189.087,77** e o VPL @ 12% a.a. vira **negativo (−R$ 174.670,13)**. Medido com a anuidade ligada, não estimado. |
| **Status** | **PENDENTE de gate da controladoria** (BLK-VIAB-11 segue aberto, criticidade Média, apenas para calibrar o **nível**). |

### (b) TAXA DE FRANQUIA — R$ 160.000 (código) × R$ 140.000 (planilha e spec)

| | |
|---|---|
| **Código** | `SIM_TAXA_FRANQUIA = 160 000,00`. |
| **Fonte documental** | `data/staging/simulador_estrutura.json`, célula **`Simulador!R10`** → `valor_default: 140000`, natureza "contrato". E `docs/modelo_dimensionamento_expansao.md:276` → "Taxa de franquia · R10 · R$140k · contrato". |
| **Decisão** | **Mantido R$ 160.000** por decisão de Felipe (2026-07-24): é o valor em produção e o que o comitê já viu. Passa a ser **editável pelo operador** (exposto no schema da API), o que resolve o caso prático sem forçar a escolha do default. |
| **Sensibilidade** | Com R$ 140.000, o caso golden mantém payback **28 meses** e ganha **+R$ 20.000** no acumulado de M60 (R$ 1.815.729,88) e no VPL (R$ 1.006.172,80); retorno desalavancado sobe de 46,55% para 46,99%. |
| **Status** | Divergência **aceita e documentada**, não resolvida. Reconciliar planilha × contrato real é tarefa de quem mantém a planilha. |

### (c) TICKET POR STUDIO — a tela está deslocada um degrau

| | |
|---|---|
| **Frontend** | `web/src/screens/ViabilityScreen.tsx:34` → `TICKET_POR_STUDIO = [147, 157, 167, 177]` (0 → 147, 1 → 157, 2 → 167, 3 → 177). |
| **Planilha** | `Simulador!J9` → `=IF(N12=0,137,IF(N12=1,147,IF(N12=2,157,IF(N12=3,167,0))))` → **[137, 147, 157, 167]**. Confirmado em `simulador_estrutura.json` e em `docs/modelo_dimensionamento_expansao.md:271` ("Mensalidade · J9 · R$137 por cenário"). |
| **Efeito** | A tela cobra **um degrau a mais** em todos os cenários de studio. O caso de referência (0 studios) roda a R$ 147 na tela e a R$ 137 na planilha. |
| **Sensibilidade** | A R$ 137 o caso golden faz faturamento **R$ 269.412,97**, EBITDA **R$ 101.306,71 (37,60%)** e payback **34 meses** (contra 28). |
| **Status** | **Aberto.** Não corrigido neste ciclo: mexer no ticket muda a conclusão de todos os cenários já apresentados, e a régua comercial vigente (R$ 147 como entrada) é decisão de produto, não de engenharia. Precisa de Felipe. |

---

## 10. Pendente de aval

**Taxa de desconto do VPL — `SIM_TAXA_DESCONTO_AA = 0,12` a.a.**

É um **default provisório**, escolhido para destravar a entrega de TIR/VPL no FIN-VIAB-01. Não há
custo de capital formalizado pela Ultra, nem WACC aprovado, nem taxa de referência decidida pelo
comitê. O número **muda o VPL, não muda o payback, o EBITDA nem a TIR** (a TIR é a raiz do fluxo,
independe da taxa) — a decisão é sobre a régua de comparação, não sobre a economia da unidade.

No caso de referência, a 12% a.a.: **VPL = R$ 986.172,80**, contra **TIR de 45,48% a.a.**

**Ação pendente:** o comitê precisa fixar a taxa (ou declarar que 12% é a régua oficial). Enquanto
não houver decisão, todo VPL exibido deve ser lido como "descontado a 12% a.a., taxa provisória".

---

## 11. Simplificação declarada

**Adicional de 10% do IRPJ aplicado pro-rata mensal.**

A legislação apura o adicional de 10% do IRPJ **por trimestre**, sobre a parcela da base presumida
que excede **R$ 60.000 no trimestre**. O simulador roda em passo **mensal** e aplica o limite
rateado: `SIM_IRPJ_ADICIONAL_LIMITE_MES = 20 000,00` (= 60.000 ÷ 3).

**Por que:** aplicar o corte trimestral no motor mensal criaria um **degrau artificial** na série de
caixa — dois meses sem adicional e um mês com o adicional inteiro —, o que distorceria o gráfico de
FCF acumulado e o mês de virada do payback sem nenhum ganho de precisão econômica.

**Quando é equivalente:** quando os três meses do trimestre são **estáveis** (o caso normal em
steady-state). O rateio e o corte trimestral produzem a mesma soma anual.

**Quando diverge:** nos meses de rampa, em que a base cresce mês a mês. O erro é de **timing**
(alguns reais antecipados ou postergados dentro do trimestre), não de nível — e some assim que a
unidade atinge a maturidade.

Esta é a **única** simplificação fiscal do motor. Regime (Lucro Presumido), base presumida (32%) e
alíquotas são os da legislação.

---

## 12. Linhas da planilha ainda ausentes do motor

A **anuidade saiu desta lista** em 2026-07-24: foi decidida por Felipe, implementada, exposta no
`viabilidade_payload_v1` e está ligada por default (`SIM_ANUIDADE_VALOR = 99.0`). Regra e
justificativa em **§2.1**. O que **continua ausente** são duas linhas:

| linha da planilha | célula | valor | o que falta no motor |
|---|---|---|---|
| Matrícula | `Simulador!J11` | R$ 0 (default) | Receita de adesão por novo aluno. **Não existe** na série mensal — não há constante, não há campo em `Premissas` e não há relógio de início (o `SIM_ANUIDADE_MES_INICIO` é só da anuidade). |
| Múltiplo de valuation | `Simulador!R11` | **1,5×** receita | Valor terminal no fim do horizonte. O motor tem o campo (`SIM_VALOR_RESIDUAL_MES_60`) mas ele está em **zero** — o corte em 60 meses hoje ignora completamente o valor da unidade em operação. |

**Efeito prático:** o payback e o VPL exibidos continuam **piores** do que a planilha entregaria.
Ao comparar com números vindos do Excel, esta é a primeira diferença a checar. Implementar qualquer
uma delas é mudança de conclusão de viabilidade → **Comitê + DEC**.

---

## 13. Parâmetros vizinhos (fora do simulador, mas no payload)

Vivem em `src/motor_expansao/dimensionamento/viabilidade_ponto.py` e aparecem no
`viabilidade_payload_v1`. Não são coeficientes financeiros; são regras de leitura do ponto.

| parâmetro | default | unidade | fonte | quem pode alterar | onde vive |
|---|---|---|---|---|---|
| `POP_ZONA_MORTA_MIN` | `5 000` | habitantes | alinhado ao `POP_MIN_ACIONAVEL` do dashboard | Felipe | `viabilidade_ponto.py`; payload `flag_zona_morta` |
| `RENDA_ZONA_MORTA_MIN` | `1 600` | R$ per capita | régua mínima do entorno | Felipe | `viabilidade_ponto.py`; payload `motivo_zona_morta` |
| `ENVELOPE_MIN` / `ENVELOPE_MAX` | `600` / `3 000` | m² | base de calibração Ultra (636-2.800 m² + folga; MAPE 85% além) | Engenharia + Felipe | `viabilidade_ponto.py`; payload `flag_fora_envelope` |
| `N_MIN_COMPARAVEIS` | `3` | un. | mínimo de comparáveis para não alargar a faixa | Engenharia | `viabilidade_ponto.py`; payload `faixa_alunos.n_comparaveis` |
| `ALUNOS_RANGE_DEFAULT` | `(200 … 1200)` | alunos | eixo da grade de sensibilidade | Felipe | `viabilidade_ponto.py`; payload `grade` |
| `ALUGUEL_RANGE_FATOR` | `(0,6 … 1,5)` | × aluguel pedido | eixo da grade de sensibilidade | Felipe | `viabilidade_ponto.py`; payload `grade` |
| `SHARE_BALCAO_DEFAULT` | `0.69` | % | **duplicata** de `SIM_SHARE_BALCAO` — o canônico é o do `config.py` | Engenharia (remover) | `viabilidade_ponto.py` |
| `DEMANDA_FONTE_PREMISSA` | `"premissa_explicita"` | string | **DEC-009** — a demanda nunca vem de lat/lng | Comitê + DEC | `viabilidade_ponto.py`; payload `demanda_fonte` |

**Escopo fechado, fora deste documento:** fórmulas de renda per capita e domiciliar, Residual
Fitness (não vira regra de viabilidade), contagem de concorrentes, metodologia de p10/p90 e o botão
"Aprovado para comitê".

---

## 14. Constantes de `config.py` que não são do simulador

Para que ninguém precise reler o arquivo procurando o que faltou: `config.py` também carrega a
camada de ingestão do BLK-DIM, que **não** tem relação com viabilidade financeira.

| grupo | constantes | função |
|---|---|---|
| Growth API | `GROWTH_API_BASE_URL`, `RATE_LIMIT_REQS` (10), `RATE_LIMIT_WINDOW_S` (300 s), `BACKOFF_MIN_S` (30 s), `TOKEN_TTL_S` (3600 s), `ENDPOINT_LOGIN`, `ENDPOINT_HISTORICO`, `ENDPOINT_HISTORICO_VIEW` | cliente da Growth API (doc v1.0.0 §5-6) |
| Diretórios | `CACHE_DIR`, `STAGING_DIR` | caminhos de cache e staging |
| Anti-PII (LGPD §10.3) | `PII_COLUNAS_PROIBIDAS` | colunas proibidas em disco; `assert_sem_pii` levanta antes de qualquer `to_parquet` |
| Consolidação (gate D1/D3/D4/D6, 2026-06-13) | `DATA_INICIO_HISTORICO` (2022-04-01), `N_MESES_STEADY` (6), `MESES_MADURA` (8), `RAIO_CATCHMENT_KM` (1,5) | janela histórica, steady-state e catchment |

---

## 15. Caso de referência verificado

Boulevard Shopping Londrina. Reproduzido diretamente de `simular()` em 2026-07-24 — os números
abaixo são saída real do motor, não estimativa.

**Inputs:** m² = 1.050 · aluguel = R$ 30.000 · ticket cheio = R$ 147 · studios = 0 ·
demanda total = 2.304 alunos · rampa 8 meses · obra R$ 600.000 em 4 parcelas ·
equipamentos R$ 1.400.000 em 60 meses a 1,8% a.m. · taxa de franquia R$ 160.000 · carência 0.

| indicador | valor |
|---|---|
| **Mês de referência do steady-state** | **12** (= `max(maturação 8, anuidade 12)`; servido em `premissas.mes_referencia_steady`) |
| Ticket agregador | R$ 88,20 (60% do cheio) |
| Ticket blended | R$ 120,23 |
| Elegibilidade da anuidade | **47,59%** (= 0,94¹²) → R$ 3,9263 por aluno de balcão por mês |
| Faturamento (steady) | R$ 288.257,57 |
| *dos quais anuidade* | *R$ 6.241,94* |
| Deduções | R$ 1.441,29 |
| Receita líquida | R$ 286.816,28 |
| Impostos sobre receita | R$ 19.073,28 |
| Receita pós-impostos | R$ 267.743,00 |
| Custos operacionais | R$ 154.583,31 (variável 37.429,52 + folha 49.003,79 + fixo 68.150,00) |
| EBITDA | R$ 113.159,69 — **39,26%** |
| IR/CSLL | R$ 29.362,42 (faixa do adicional de 10%) |
| PMT | R$ 38.348,75 · juros totais R$ 900.925,18 |
| Break-even EBITDA | **840,6 alunos totais** |
| Break-even de caixa | **1.336,6 alunos totais** |
| Alunos para margem de 10% | **1.007,2 alunos totais** |
| Payback | **28 meses** (número único: KPI, gráfico e PDF) |
| 1º mês de caixa operacional positivo | mês 6 |
| Retorno desalavancado | 46,55% a.a. |
| TIR | 45,48% a.a. |
| VPL @ 12% a.a. | R$ 986.172,80 |
| Acumulado M60 | R$ 1.795.729,88 |
| Aluguel-teto | ideal R$ 43.238,64 · teto R$ 57.651,51 · **canônico (exceção) R$ 86.477,27** |
| Série mensal | 64 linhas (M-4 a M+60), 4 de pré-abertura |
| EBITDA do mês 1 | **R$ -10.139,56** (negativo — o custo é integral desde o mês 1) |

**Referência com a anuidade desligada** (`anuidade_valor = 0`), para quem precisar comparar com
material anterior a 2026-07-24: faturamento R$ 282.015,62 · EBITDA R$ 109.233,60 (38,73%) ·
break-even 859,6 · payback 29 · TIR 42,21% a.a. · VPL R$ 875.106,66 · acumulado M60
R$ 1.636.628,61 · aluguel-teto canônico R$ 84.604,69.

---

## 16. Funções deprecated

Existem só para não quebrar `backtest_viabilidade`, `batch_viabilidade`, `excel_export` e `risco`.
**Nenhum código novo pode chamá-las.**

| deprecated | canônico | por quê |
|---|---|---|
| `viabilidade()` | `simular()` | folha absoluta, IR/CSLL efetivo sobre a líquida, sem pré-abertura, sem reajuste |
| `gerar_serie_mensal()` | `gerar_serie_mensal_completa()` | só 60 linhas de operação, sem CAPEX na série → payback do gráfico ≠ payback do KPI |
| `aluguel_teto()` | `aluguel_teto_clusters()` | inversão por margem EBITDA-alvo; devolvia R$ 105.813,13 onde a tela mostrava R$ 55.535,18 |
| `alunos_minimos_viaveis()` | `break_even_alunos()` | variava só o balcão com os agregadores congelados; o resultado era rotulado como alunos totais |
