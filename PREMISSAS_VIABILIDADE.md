# Premissas do Simulador de Viabilidade

> **Fonte única.** Todo coeficiente financeiro do Motor de Viabilidade vive em
> `src/motor_expansao/dimensionamento/config.py` e é consumido por
> `src/motor_expansao/dimensionamento/simulador.py`. Backend, frontend e PDF apenas
> **leem** o resultado — nenhuma fórmula financeira pode ser reescrita fora do simulador.
>
> Ciclo: **FIN-VIAB-01** (reconciliação do simulador) · Atualizado em **2026-07-24**
> (**3ª rodada** — duas decisões de produto de Felipe entraram no núcleo: **folha fixa desde o
> mês 1** e **taxa de franquia parcelada em 4×**. Ver §4.1 e §6.)
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
| `SIM_FOLHA_PCT` | `0.17` | % do **faturamento MADURO** (regime pleno) → **R$/mês fixo desde o mês 1** | decisão de Felipe, 2026-07-24 — estrutura em §4.1, nível no conflito **A** da §9 | Felipe + Controladoria | `config.py` → `Premissas.folha_pct` → **`Premissas.folha_fixa_mes(demanda)`**; linha `folha` da série |
| *(derivado)* `folha_fixa_mes(demanda)` | **R$ 49.003,79** no caso de referência | R$/mês | `folha_pct × faturamento_maduro(demanda)`, a preços do ano 1 | — | `Premissas.folha_fixa_mes()`; reajusta anualmente como os demais custos |
| *(derivado)* `custo_fixo_total_mes(demanda)` | **R$ 87.153,79** no caso de referência | R$/mês (sem aluguel) | `outros_fixos_mes + folha_fixa_mes(demanda)` | — | `Premissas.custo_fixo_total_mes()`; **substituiu** a propriedade `custo_fixo_base_mes` |
| `SIM_PESSOAL_MES` | `50 128,16` | R$/mês | Fopag com encargos (DRE linha 55) | **congelado (legado)** | `config.py`; **não alimenta mais a folha** — só default de `viabilidade()`/`gerar_serie_mensal()` |
| `pessoal_mes_override` | `None` | R$/mês | escotilha de compatibilidade | Engenharia (compat) | `Premissas`; quando preenchido, este valor absoluto **substitui** o dimensionamento por percentual (`folha_pct` é ignorado). A folha já é fixa nos dois modos |
| `SIM_OUTROS_FIXOS_MES` | `38 150,00` | R$/mês | Excel, DRE linhas 52-59 e 69 — **seis** componentes que fecham exatamente nos 38.150: IPTU 2.000 + água/luz 17.000 + telefone 500 + limpeza 14.000 + tecnologia 2.150 + assessorias 2.500. (O "outros 2.000" que aparecia nesta lista era **espúrio**: as sete componentes somavam 40.150, R$ 2.000 acima da própria constante. Corrigido no comentário do `config.py` em 2026-07-24; o valor **não** mudou.) | Controladoria | `config.py` → `Premissas.outros_fixos_mes` |
| `aluguel_mes` | — (input) | R$/mês | **input manual do operador** — escopo fechado, não é estimado pelo motor | Operador | `Premissas.aluguel_mes` |
| `SIM_CUSTO_PRE_OPERACIONAL_MES` | `0.0` | R$/mês | **explicitação de ausência** — hoje o modelo assume zero custo de contratação/treinamento/pré-venda | Felipe | `config.py` → `Premissas.custo_pre_operacional_mes`; linhas M-4..M-1 |
| `SIM_CUSTO_STUDIO` | `6 000,00` | R$/mês por studio | fopag adicional por studio extra | Felipe | `config.py`; **consumida** por `web/server/app.py::_premissas_do_body`, que soma `n_studios × SIM_CUSTO_STUDIO` a `outros_fixos_mes` |
| `SIM_STUDIOS_DEFAULT` | `0` | un. (0..3) | configuração padrão de unidade | Felipe | `config.py`; **declarada e não consumida** — ver §8 |

**Natureza do custo (explícita no resultado):** variável (% da receita líquida), **folha (custo
FIXO** dimensionado pelo faturamento maduro — ver §4.1) e fixo absoluto (outros fixos + aluguel +
pré-operacional). O custo operacional é **integral desde o mês 1** — não acompanha a rampa de
alunos. As únicas variações legítimas no tempo são a carência de aluguel e o reajuste anual.

### 4.1 Regra da folha — FIXA desde o mês 1 (decisão de Felipe, 2026-07-24 — não rediscutir)

**O que era:** `folha = folha_pct × faturamento DO MÊS`. Como o faturamento rampa por 8 meses, a
folha rampava junto — no caso de referência ela entrava com **R$ 15.678,87 no mês 1** e só chegava
aos ~R$ 49 mil na maturidade. Isso equivale a supor que **se contrata gente na medida em que o
aluno entra**, o que não é como a unidade abre. Foi exatamente o defeito reportado: *"a folha está
escalando junto com a unidade"*.

**O que é agora:** `Premissas.folha_fixa_mes(demanda)` = `folha_pct × faturamento MADURO` (regime
pleno, casa cheia e anuidade em cobrança, **a preços do ano 1**), e esse valor vale **desde o mês
1**, reajustando anualmente como os demais custos. No caso de referência: 17% × R$ 288.257,57 =
**R$ 49.003,79/mês**, do M1 ao M60.

**Por quê:** a equipe existe antes dos alunos. O quadro de pessoal de uma unidade de 1.050 m² é
dimensionado pela operação que ela vai ter — recepção, limpeza, professores por horário, gerência
— e é contratado para abrir a porta, não conforme a matrícula chega. Dimensionar pelo faturamento
maduro e pagar integralmente desde o mês 1 é o que o caixa real faz.

**Quatro consequências estruturais** (todas já no núcleo; nenhuma é escolha de engenharia):

1. **A folha deixou de ser percentual e virou CUSTO FIXO.** O percentual sobrevive apenas como
   *régua de dimensionamento*, aplicada uma única vez.
2. **Ela saiu do fator `k`.** `fator_receita_para_ebitda` não subtrai mais `folha_pct`:
   `k = (1 − deduções) × (1 − impostos − custo variável)` = `0,995 × 0,803` = **0,798985**
   (era **0,628985**). Quem lê `k` como "quanto de cada R$ 1 de faturamento sobra antes do custo
   fixo" continua certo — o que mudou é que a folha agora está do outro lado da conta.
3. **O custo fixo cresceu.** Sem aluguel: de **R$ 38.150,00** (só `outros_fixos`) para
   **R$ 87.153,79** (`outros_fixos` + folha). Com o aluguel de R$ 30.000 do caso de referência, o
   bloco fixo que o break-even divide por `k` vai de **R$ 68.150,00 para R$ 117.153,79**. A
   **alavancagem operacional aumentou**: mais custo fixo e mais contribuição marginal por aluno —
   cada aluno vale mais no topo, e a queda dói mais embaixo.
4. **Duas assinaturas mudaram**, porque é a demanda assumida que dimensiona a folha:
   `break_even_alunos(p, demanda_total, *, incluir_pmt=0)` e
   `alunos_para_margem(p, margem_alvo, demanda_total)`. A pergunta que o break-even responde passou
   a ser a correta: *"montei a casa para 2.304 alunos; com quantos eu empato?"* — e não *"com
   quantos eu empato se eu também encolher a equipe proporcionalmente?"*.

**Efeito no caso de referência:** o mês de *steady* **não muda** (lá o faturamento já é o maduro,
então a folha percentual e a folha fixa coincidem: R$ 49.003,79 nos dois modelos). O que muda são
os meses de rampa e tudo que deriva deles — EBITDA do mês 1 de **−R$ 10.139,56 para −R$ 43.464,47**,
break-even de **840,6 para 1.152,0** alunos totais, payback de **28 para 31 meses**. Números
completos em §15 e no antes × depois de `docs/nota_impacto_fin_viab_01.md`.

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
| `SIM_PARCELAS_FRANQUIA_DEFAULT` | `4` | parcelas **sem juros** | decisão de Felipe, 2026-07-24 — ver §6.1 | Felipe + Comitê | `config.py` → argumento `parcelas_franquia` de `gerar_serie_mensal_completa()` e `simular()`; parcelas nos meses de **contrato 1..N** (M-4..M-1 com N=4), junto da obra |
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

### 6.1 Taxa de franquia parcelada em 4× sem juros (decisão de Felipe, 2026-07-24)

Antes a taxa saía **inteira do caixa no M-4**, junto da primeira parcela da obra: o desembolso do
M-4 era de R$ 310.000 (obra 150.000 + franquia 160.000) contra R$ 150.000 nos três meses seguintes.
Agora ela é parcelada em **4× sem juros**, nos meses de **contrato 1..N** — os mesmos M-4..M-1 da
obra —, o que deixa a pré-abertura plana em **R$ 190.000 por mês** (obra 150.000 + franquia 40.000).

**Isto é só timing de caixa, e o efeito é pequeno de propósito:** as quatro parcelas cabem
inteiras dentro da janela de pré-abertura, então **no mês 1 o desembolso acumulado já é o mesmo**.
EBITDA, margem e break-even **não mudam** (parcelamento não é resultado); payback e acumulado de
M60 ficam **idênticos**. Muda apenas o que é sensível à *data* de cada real: **TIR +0,33 pp** e
**VPL +R$ 2.241,80** (medido, §15). Se um dia o número de parcelas passar da janela de pré-abertura,
as parcelas restantes cairão nos primeiros meses de operação — a série já trata esse caso.

---

## 7. Aluguel-teto

| parâmetro | default | unidade | fonte | quem pode alterar | onde vive |
|---|---|---|---|---|---|
| `SIM_ALUGUEL_TETO_IDEAL` | `0.15` | % do faturamento bruto | régua de ocupação da rede | Felipe | `config.py` → `aluguel_teto_clusters()` |
| `SIM_ALUGUEL_TETO_TETO` | `0.20` | % do faturamento bruto | idem — **é o valor canônico exibido** | Felipe | idem; payload `aluguel_teto.canonico` |
| `SIM_ALUGUEL_TETO_EXCECAO` | `0.30` | % do faturamento bruto | idem — **exceção, não referência**; segue impressa no detalhe | Felipe | idem |

Base de cálculo: **faturamento bruto de steady-state** — o do `mes_referencia_steady` (mês 12),
anuidade inclusa. É a única definição de aluguel-teto do sistema (tela **e** PDF), e as **três
faixas** viajam no payload: sumir com ideal e teto no PDF, deixando só o canônico, foi um dos
defeitos apontados pelo QA deste ciclo. A inversão por margem EBITDA-alvo (`aluguel_teto()`) está
**deprecated**: devolvia R$ 105.813,13 onde a tela mostrava R$ 55.535,18 no mesmo cenário.

**O canônico exibido no card grande é o `teto` (20%), não a `excecao` (30%)** — decisão de Felipe
(2026-07-24): o card tem de mostrar o limite que a operação **defende**; 30% é caso de exceção, não
referência. As três faixas seguem impressas no detalhe, todas da mesma base.

No caso de referência: ideal R$ 43.238,64 · **teto/canônico R$ 57.651,51** · exceção R$ 86.477,27.
O aluguel pedido de R$ 30.000 é **10,4%** do faturamento — abaixo da faixa ideal.

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

### `SIM_STUDIOS_DEFAULT = 0` (e `SIM_CUSTO_STUDIO`, que **deixou de ser órfã**)

- **`SIM_CUSTO_STUDIO = 6 000,00` foi LIGADA neste ciclo.** `web/server/app.py::_premissas_do_body`
  soma `n_studios × SIM_CUSTO_STUDIO` a `outros_fixos_mes` (com `n_studios = 2`, o custo fixo vai de
  R$ 68.150,00 para R$ 80.150,00, ou seja −R$ 12.000 no EBITDA). Antes, a tela **tinha** um seletor
  de studios (0..3) que só afetava o **ticket** (via `TICKET_POR_STUDIO` no frontend) e nunca o
  custo: uma unidade com 3 studios rodava com o mesmo custo fixo de uma sem nenhum. A **fonte**
  ("fopag adicional por studio extra") continua sem célula da planilha nem linha de DRE — calibrar o
  valor é da controladoria. Nota: o studio entra em `outros_fixos_mes`, **não** na folha dimensionada
  por `SIM_FOLHA_PCT` (§4.1) — se o quadro de pessoal do studio já estivesse dentro dos 17%, isso
  seria dupla contagem, e é uma pergunta aberta para a controladoria.
- **`SIM_STUDIOS_DEFAULT = 0` continua órfã.** Re-verificado em 2026-07-24: **nenhum consumidor** em
  `src/`, `web/` ou `tests/`. Decisão: ou vira o default do seletor da tela, ou sai. Manter declarada
  e desligada é o pior dos mundos, porque parece implementada.

---

## 9. Conflitos abertos

Três divergências **conhecidas, não resolvidas**, entre o código e a fonte documental. Nenhuma
bloqueia o ciclo; todas precisam de decisão nomeada.

### (a) FOLHA — a nota tem DUAS dimensões: a ESTRUTURA (decidida) e o NÍVEL (pendente)

Desde a 3ª rodada é obrigatório separar as duas, porque só uma foi resolvida:

| dimensão | pergunta | estado |
|---|---|---|
| **ESTRUTURA** | a folha é **custo fixo** ou **percentual da receita do mês**? | **DECIDIDA — custo fixo desde o mês 1** (Felipe, 2026-07-24). Regra e consequências em §4.1. Não rediscutir. |
| **NÍVEL** | o percentual que **dimensiona** esse custo fixo é 17% ou 25-26%? | **PENDENTE de gate da controladoria** (BLK-VIAB-11 aberto, criticidade Média). |

**Sobre o nível:**

| | |
|---|---|
| **O que o código faz hoje** | `SIM_FOLHA_PCT = 0,17`, aplicado **uma vez** sobre o faturamento **maduro** → R$ 49.003,79/mês fixos. |
| **O que a evidência diz** | O **BLK-VIAB-11** apurou **25-26%** em **6 DREs gerenciais reais** (Augusta, Bangu, Cabo Frio, Icaraí, Praia Grande, Vila Guilherme; jun-jul/2026). Folha real de **R$ 38 mil a R$ 99 mil/mês**, **estável como % da receita bruta (CV 0,16)** e instável por m² (CV 0,34). SP e RJ praticamente idênticos → sem ajuste regional. |
| **Por que 17% mesmo assim** | 17% mantém o **nível** próximo do status quo (R$ 50.128 fixos ÷ R$ 277.676 = 18,05% no caso antigo). A 3ª rodada mexeu na **estrutura**, não no nível — e trocar as duas coisas ao mesmo tempo tornaria impossível atribuir o delta. Note a ironia útil: com a folha fixa, o nível de 17% reproduz quase exatamente o R$ 50.128 absoluto do modelo original, agora dimensionado por uma régua rastreável em vez de um número herdado. |
| **Impacto do nível (re-medido na estrutura NOVA, 2026-07-24)** | A 17%: folha **R$ 49.003,79**, EBITDA **R$ 113.159,69 (39,26%)**, break-even **1.152,0**, payback **31**, TIR **38,98% a.a.**, VPL **R$ 849.484,15**, M60 **R$ 1.645.454,56**. **A 26%: folha R$ 74.946,97, EBITDA R$ 87.216,50 (30,26%), break-even 1.416,1, EBITDA do mês 1 de −R$ 69.407,65 e o payback NÃO OCORRE dentro dos 60 meses** (`inf`) — TIR **−1,05% a.a.**, VPL **−R$ 384.910,19**, acumulado de M60 **−R$ 40.745,08**. |
| **Atenção ao comparar com material anterior** | A leitura anterior desta linha dizia "payback 28 → 54 meses" e "VPL −R$ 174.670,13". Aquilo foi medido com a folha **percentual**, que diluía o custo na rampa. Na estrutura correta a 26% o projeto **não se paga no horizonte** — a pendência ficou materialmente **pior**, não melhor. |
| **Status** | **PENDENTE de gate da controladoria.** É a decisão pendente de maior impacto do ciclo: sozinha, ela inverte a conclusão de go/no-go do Boulevard. |

### (b) TAXA DE FRANQUIA — R$ 160.000 (código) × R$ 140.000 (planilha e spec)

| | |
|---|---|
| **Código** | `SIM_TAXA_FRANQUIA = 160 000,00`. |
| **Fonte documental** | `data/staging/simulador_estrutura.json`, célula **`Simulador!R10`** → `valor_default: 140000`, natureza "contrato". E `docs/modelo_dimensionamento_expansao.md:276` → "Taxa de franquia · R10 · R$140k · contrato". |
| **Decisão** | **Mantido R$ 160.000** por decisão de Felipe (2026-07-24): é o valor em produção e o que o comitê já viu. Passa a ser **editável pelo operador** (exposto no schema da API) e **parcelado em 4× sem juros** (§6.1), o que resolve o caso prático sem forçar a escolha do default. |
| **Sensibilidade (re-medida, 2026-07-24)** | Com R$ 140.000: payback **30 meses** (contra 31), acumulado de M60 **R$ 1.665.454,56** (+R$ 20.000 exatos), VPL **R$ 869.203,92** (+R$ 19.719,77 — menos que os R$ 20 mil nominais, porque o desembolso é descontado), TIR **40,01% a.a.** e retorno desalavancado **46,99%** (era 46,55%). EBITDA, margem e break-even não mudam. |
| **Status** | Divergência **aceita e documentada**, não resolvida. Reconciliar planilha × contrato real é tarefa de quem mantém a planilha. |

### (c) TICKET POR STUDIO — a tela está deslocada um degrau

| | |
|---|---|
| **Frontend** | `web/src/screens/ViabilityScreen.tsx:34` → `TICKET_POR_STUDIO = [147, 157, 167, 177]` (0 → 147, 1 → 157, 2 → 167, 3 → 177). |
| **Planilha** | `Simulador!J9` → `=IF(N12=0,137,IF(N12=1,147,IF(N12=2,157,IF(N12=3,167,0))))` → **[137, 147, 157, 167]**. Confirmado em `simulador_estrutura.json` e em `docs/modelo_dimensionamento_expansao.md:271` ("Mensalidade · J9 · R$137 por cenário"). |
| **Efeito** | A tela cobra **um degrau a mais** em todos os cenários de studio. O caso de referência (0 studios) roda a R$ 147 na tela e a R$ 137 na planilha. |
| **Sensibilidade (re-medida, 2026-07-24)** | A R$ 137 o caso golden faz faturamento **R$ 269.412,97**, folha **R$ 45.800,20** (a régua de 17% acompanha o faturamento maduro menor), EBITDA **R$ 101.306,71 (37,60%)**, break-even **1.199,2** e payback **37 meses** — ou seja, **estoura o critério de 36 meses** e `flag_viavel` cai para falso. TIR **25,66% a.a.**, VPL **R$ 416.749,97**. Na medição anterior (folha percentual) davam 34 meses e o critério ainda passava; com a folha fixa, este conflito passou a ser capaz de reprovar a unidade sozinho. |
| **Status** | **Aberto.** Não corrigido neste ciclo: mexer no ticket muda a conclusão de todos os cenários já apresentados, e a régua comercial vigente (R$ 147 como entrada) é decisão de produto, não de engenharia. Precisa de Felipe. |

---

## 10. Pendente de aval

**Taxa de desconto do VPL — `SIM_TAXA_DESCONTO_AA = 0,12` a.a.**

É um **default provisório**, escolhido para destravar a entrega de TIR/VPL no FIN-VIAB-01. Não há
custo de capital formalizado pela Ultra, nem WACC aprovado, nem taxa de referência decidida pelo
comitê. O número **muda o VPL, não muda o payback, o EBITDA nem a TIR** (a TIR é a raiz do fluxo,
independe da taxa) — a decisão é sobre a régua de comparação, não sobre a economia da unidade.

No caso de referência, a 12% a.a.: **VPL = R$ 849.484,15**, contra **TIR de 38,98% a.a.**

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

Boulevard Shopping Londrina. Reproduzido diretamente de `simular()` em 2026-07-24, **na 3ª rodada**
(folha fixa + franquia parcelada) — os números abaixo são saída real do motor, não estimativa.

**Inputs:** m² = 1.050 · aluguel = R$ 30.000 · ticket cheio = R$ 147 · studios = 0 ·
demanda total = 2.304 alunos · rampa 8 meses · obra R$ 600.000 em 4 parcelas ·
equipamentos R$ 1.400.000 em 60 meses a 1,8% a.m. · taxa de franquia R$ 160.000 **em 4 parcelas** ·
carência 0.

| indicador | valor |
|---|---|
| **Mês de referência do steady-state** | **12** (= `max(maturação 8, anuidade 12)`; servido em `premissas.mes_referencia_steady`) |
| Ticket agregador | R$ 88,20 (60% do cheio) |
| Ticket blended | R$ 120,23 |
| Receita por aluno total (regime pleno) | R$ 122,94 (mensalidade + anuidade — régua do break-even) |
| Elegibilidade da anuidade | **47,59%** (= 0,94¹²) → R$ 3,9263 por aluno de balcão por mês |
| **Fator `k` (receita → EBITDA)** | **0,798985** (a folha **não** entra — §4.1) |
| **Folha — FIXA desde o mês 1** | **R$ 49.003,79/mês** (17% do faturamento maduro de R$ 288.257,57) |
| **Custo fixo sem aluguel** (`custo_fixo_total_mes`) | **R$ 87.153,79** (outros fixos 38.150,00 + folha 49.003,79) |
| **Pré-abertura, CADA mês de M-4 a M-1** | investimento **R$ 190.000,00** (obra 150.000 + franquia 40.000) |
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
| Break-even EBITDA | **1.152,0 alunos totais** |
| Break-even de caixa | **1.542,4 alunos totais** |
| Alunos para margem de 10% | **1.322,6 alunos totais** |
| Payback | **31 meses** (número único: KPI, gráfico e PDF) |
| 1º mês de caixa operacional positivo | mês 6 |
| Retorno desalavancado | 46,55% a.a. |
| TIR | 38,98% a.a. |
| VPL @ 12% a.a. | R$ 849.484,15 |
| Acumulado M60 | R$ 1.645.454,56 |
| Aluguel-teto | ideal R$ 43.238,64 · **canônico (teto) R$ 57.651,51** · exceção R$ 86.477,27 |
| Série mensal | 64 linhas (M-4 a M+60), 4 de pré-abertura |
| **EBITDA do mês 1** | **−R$ 43.464,47** (a folha é integral e os alunos rampam por 8 meses) |
| EBITDA do mês 4 | R$ 21.522,79 |
| EBITDA do mês 8 | R$ 108.172,47 |

**Steady-state não mudou na 3ª rodada.** Faturamento, EBITDA, margem, folha do mês 12, IR/CSLL e
aluguel-teto são idênticos aos da rodada anterior — no mês 12 o faturamento já é o maduro, então
folha percentual e folha fixa dão o mesmo R$ 49.003,79. Tudo o que mudou está na **rampa** e no que
deriva dela (break-even, payback, TIR, VPL, acumulado).

**Isolamento das duas mudanças da 3ª rodada** (medido em 2026-07-24, uma por vez):

| mudança | efeito |
|---|---|
| **Franquia parcelada 4×** — só timing de caixa | TIR **+0,33 pp** · VPL **+R$ 2.241,80** · payback, acumulado de M60, EBITDA, margem e break-even **idênticos** |
| **Folha fixa desde o mês 1** — responde por todo o resto | break-even **840,6 → 1.152,0** · payback **28 → 31** · TIR **45,48% → 38,65%** (antes de somar a franquia) · VPL **R$ 986.172,80 → R$ 847.242,35** · M60 **R$ 1.795.729,88 → R$ 1.645.454,56** · EBITDA do mês 1 **−R$ 10.139,56 → −R$ 43.464,47** |

**Referência com a anuidade desligada** (`anuidade_valor = 0`), re-medida na estrutura nova, para
quem precisar comparar com material anterior: steady no **mês 8** · faturamento R$ 282.015,62 ·
folha R$ 47.942,66 · EBITDA R$ 109.233,60 (38,73%) · break-even **1.166,9** · payback **32** ·
TIR 36,40% a.a. · VPL R$ 752.610,14 · acumulado M60 R$ 1.503.326,98 · aluguel-teto canônico
R$ 56.403,12.

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

**Assinaturas que mudaram na 3ª rodada** (a folha fixa é dimensionada pela demanda assumida, então
as duas funções passaram a **receber** a demanda — chamada sem ela agora é `TypeError`, não um
número errado silencioso):

```python
break_even_alunos(p, demanda_total, *, incluir_pmt=0.0)     # antes: (p, *, incluir_pmt=0.0)
alunos_para_margem(p, margem_alvo, demanda_total)           # antes: (p, margem_alvo)
gerar_serie_mensal_completa(..., parcelas_franquia=4)       # argumento novo
simular(..., parcelas_franquia=4)                          # argumento novo
```

A propriedade `Premissas.custo_fixo_base_mes` **não existe mais**: foi substituída pelo método
`custo_fixo_total_mes(demanda_total)`, que inclui a folha.
