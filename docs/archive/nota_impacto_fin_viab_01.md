# Nota de impacto — FIN-VIAB-01 (reconciliação do simulador de viabilidade)

**Para:** Comitê de Expansão · **De:** Estratégia e Growth · **Data:** 2026-07-24
**Versão:** 3ª rodada — inclui **folha fixa desde o mês 1** e **taxa de franquia parcelada em 4×**
**Caso:** Boulevard Shopping Londrina (1.050 m², aluguel R$ 30.000, ticket R$ 147,
demanda premissa 2.304 alunos, rampa 8 meses, obra R$ 600 mil em 4 parcelas,
equipamentos R$ 1,4 mi em 60 meses a 1,8% a.m., taxa de franquia R$ 160 mil em 4 parcelas)

## O que mudou

A tela e o PDF do **mesmo cenário** vinham divergindo: payback 35 no KPI e 33 no gráfico,
acumulado de 60 meses de R$ 1,89 mi ou R$ 2,05 mi conforme a fonte, aluguel-teto de
R$ 55.535 ou R$ 105.813. A causa era estrutural: existiam **cinco séries mensais
independentes e nove KPIs com implementação dupla**. O FIN-VIAB-01 colapsou tudo num
**motor único** — uma linha do tempo de M-4 a M+60 da qual todo indicador deriva. Tela,
API e PDF agora leem o mesmo objeto e **não recalculam nada**.

Junto vieram correções de conteúdo, em duas ondas. Nas **duas primeiras rodadas**: o **ticket do
agregador** deixou de ser R$ 82 absoluto e virou **60% do ticket cheio**; o **IR/CSLL** deixou de
aplicar alíquotas efetivas sobre a receita líquida e passou a apurar o Lucro Presumido com a
**faixa explícita** do adicional de 10%; a **anuidade** — linha `Simulador!J10`, que existia na
planilha e nunca tinha sido implementada — **entrou no motor**; e a **folha** deixou de ser um
absoluto herdado (R$ 50.128,16) para ser dimensionada por uma régua (17% do faturamento).

Na **3ª rodada** entraram duas decisões de produto de Felipe, ambas de 2026-07-24:

1. **FOLHA FIXA DESDE O MÊS 1.** A 2ª rodada calculava a folha como `17% × faturamento DO MÊS`, o
   que a fazia **encolher junto com a rampa** — no mês 1 ela custava R$ 15.678,87 em vez de
   R$ 49 mil. Isso equivale a supor que se contrata gente na medida em que o aluno entra. Agora a
   folha é dimensionada **uma vez** pelo faturamento **maduro** (17% × R$ 288.257,57 =
   **R$ 49.003,79**) e é paga **integralmente desde o mês 1**, reajustando anualmente como os
   demais custos. **A folha virou custo fixo.**
2. **TAXA DE FRANQUIA PARCELADA EM 4× SEM JUROS.** Antes ela saía inteira do caixa no M-4; agora
   cai em quatro parcelas de R$ 40.000 nos meses de contrato 1..4 (M-4..M-1), junto da obra — a
   pré-abertura fica plana em **R$ 190.000/mês**.

## Antes × depois

Coluna "antes" = o que a ferramenta mostrava **antes do ciclo**. Coluna "depois" = o motor único
com as duas mudanças da 3ª rodada.

| Indicador | Antes (o que a ferramenta mostrava) | Depois (número único) |
|---|---|---|
| Faturamento (steady) | R$ 277.675,90 | **R$ 288.257,57** |
| *dos quais anuidade* | *não existia* | ***R$ 6.241,94*** |
| Mês de referência do steady-state | implícito (maturação, mês 8) | **mês 12**, declarado em `premissas.mes_referencia_steady` |
| **Folha** | R$ 50.128,16 fixos (número absoluto herdado, sem régua) | **R$ 49.003,79 fixos desde o mês 1** (= 17% do faturamento maduro) |
| **Fator `k` (receita → EBITDA)** | não existia como conceito exposto | **0,798985** — a folha **não** entra (é custo fixo) |
| **Custo fixo sem aluguel** | R$ 38.150,00 (só "outros fixos") | **R$ 87.153,79** (outros fixos + folha) |
| EBITDA (steady) | R$ 103.580,72 (37,30%) | **R$ 113.159,69 (39,26%)** |
| IR/CSLL | R$ 30.060,08 | **R$ 29.362,42** |
| **EBITDA do mês 1** | não era exibido | **−R$ 43.464,47** |
| **Break-even** | 632 alunos **de balcão** (medida errada) | **1.152,0 alunos TOTAIS** |
| Break-even de caixa | não existia | **1.542,4 alunos totais** |
| Payback | 35 (KPI) / 33 (gráfico) | **31 meses** |
| **Taxa de franquia no caixa** | R$ 160.000 inteiros no M-4 | **4 × R$ 40.000** (M-4 a M-1); pré-abertura plana em R$ 190.000/mês |
| Aluguel-teto | R$ 105.813,13 (PDF) / R$ 55.535,18 (tela) | **R$ 57.651,51** (teto, 20%), com ideal R$ 43.238,64 e exceção R$ 86.477,27 visíveis nos dois lugares |
| Acumulado M60 | R$ 1.894.476,90 / R$ 2.054.476,90 | **R$ 1.645.454,56** |
| TIR / VPL @ 12% a.a. | não existia | **38,98% a.a. / R$ 849.484,15** |

## Delta isolado de cada correção

### Rodadas 1-2 — baseline: a configuração antiga

Medido no motor novo, revertendo **um coeficiente por vez** a partir da configuração antiga
(que reproduz exatamente o EBITDA de R$ 103.580,72 do "antes"). A anuidade é medida à parte,
como o último degrau, porque só ela muda a **régua** (o mês de referência do steady-state).

> **Esta tabela é o registro histórico das rodadas 1-2** e foi apurada com a **folha percentual**
> que vigorava então. Os efeitos de payback dela (35 → 28) foram parcialmente revertidos pela 3ª
> rodada — a tabela seguinte é a que vale para o número de hoje.

| Correção | Efeito no faturamento | Efeito no EBITDA | Efeito no payback |
|---|---|---|---|
| Ticket do agregador: R$ 82 → 60% do cheio (R$ 88,20) | **+R$ 4.339,72** | +R$ 3.467,37 | 35 → 33 (-2) |
| Folha: R$ 50.128 fixos → régua de 17% | 0 | +R$ 2.923,26 | 35 → 32 (-3) |
| IR/CSLL: efetivo sobre a líquida → faixa do presumido | 0 | 0 (é abaixo do EBITDA; **-R$ 1.848,94** de imposto) | 35 → 34 (-1) |
| **As três juntas** (anuidade ainda desligada) | **+R$ 4.339,72** | **+R$ 5.652,88** | **35 → 29 (-6)** |
| **Anuidade ligada** (R$ 99/ano, só balcão, 47,59% elegíveis, pro-rata) | **+R$ 6.241,94** | **+R$ 3.926,09** | **29 → 28 (-1)** |
| **As quatro juntas** | **+R$ 10.581,67** | **+R$ 9.578,97** | **35 → 28 (-7)** |

Os deltas de EBITDA **não somam** (3.467 + 2.923 = 6.391, contra 5.653 juntos) porque havia
interação: com o faturamento maior trazido pelo agregador, a folha percentual daquela rodada
também custava mais. (Com a folha fixa da 3ª rodada essa interação deixa de existir no steady.)

### 3ª rodada — baseline: o resultado da 2ª rodada

Medido em 2026-07-24, **uma mudança por vez**, a partir do estado anterior (break-even 840,6 ·
payback 28 · TIR 45,48% a.a. · VPL R$ 986.172,80 · acumulado M60 R$ 1.795.729,88):

| Mudança | EBITDA / margem / break-even | Payback e acumulado M60 | TIR e VPL |
|---|---|---|---|
| **Franquia parcelada 4× sem juros** | **inalterados** — parcelamento não é resultado | **idênticos** (payback 31, M60 R$ 1.645.454,56) | **TIR +0,33 pp** · **VPL +R$ 2.241,80** |
| **Folha fixa desde o mês 1** | EBITDA e margem de *steady* **inalterados**; **break-even 840,6 → 1.152,0** (+311,4 alunos); EBITDA do mês 1 de **−R$ 10.139,56 → −R$ 43.464,47** | **payback 28 → 31** · **M60 R$ 1.795.729,88 → R$ 1.645.454,56** (−R$ 150.275,33) | **TIR 45,48% → 38,65%** (−6,83 pp) · **VPL R$ 986.172,80 → R$ 847.242,35** (−R$ 138.930,45) |
| **As duas juntas** | idem acima | payback **31** · M60 **R$ 1.645.454,56** | **TIR 38,98% a.a.** · **VPL R$ 849.484,15** |

**Por que a franquia parcelada quase não move nada — e isso é o esperado.** As quatro parcelas
cabem inteiras dentro da janela de pré-abertura, então **no mês 1 o desembolso acumulado já é o
mesmo** dos R$ 880.000. Payback e acumulado de M60 ficam **idênticos** por construção; muda apenas
o que é sensível à *data* de cada real (TIR e VPL). EBITDA, margem e break-even não mudam porque
parcelamento é caixa, não resultado.

**A folha fixa responde por todo o resto** — e **piora** os indicadores. Isso é correto, não uma
regressão do modelo.

## Por que a folha fixa piora os números — e por que isso é o certo

O modelo da 2ª rodada **diluía a folha na rampa**: como ela era 17% do faturamento *do mês*, no
mês 1 custava R$ 15.678,87 e só chegava aos R$ 49 mil na maturidade. Na prática isso significava
supor que a academia contrata recepção, limpeza, professores e gerência **na medida em que o aluno
entra** — e que, se a demanda não vier, a folha encolhe sozinha. Nenhuma das duas coisas é
verdade: a equipe é dimensionada pela operação que a unidade vai ter e é contratada **para abrir a
porta**.

A consequência de diluir era dupla e ia toda na mesma direção — otimismo:

- **subestimava a queima de caixa dos primeiros meses.** O EBITDA do mês 1 aparecia como
  −R$ 10.139,56 quando o número real é **−R$ 43.464,47**, uma diferença de R$ 33,3 mil **no mês
  mais frágil da unidade**. O plano de capital de giro da abertura estava dimensionado por baixo.
- **subestimava o break-even.** Com a folha encolhendo junto com o volume, o ponto de equilíbrio
  "se ajustava" à queda — o que responde a pergunta errada. A pergunta certa é: *"montei a casa
  para 2.304 alunos; com quantos eu empato?"*, e a resposta é **1.152,0**, não 840,6.

Em troca, o motor ficou estruturalmente mais correto: a folha saiu do fator `k`
(**0,628985 → 0,798985**) e entrou no bloco fixo (**R$ 68.150,00 → R$ 117.153,79**, incluído o
aluguel). A **alavancagem operacional aumentou** — cada aluno adicional contribui mais no topo, e
a falta de alunos dói mais embaixo. É a economia real de uma academia: custo fixo alto, margem
marginal alta.

## O número que o comitê precisa levar: break-even 632 → 1.152

**É a mudança mais consequente do ciclo inteiro.** Não porque o negócio piorou, mas porque o
número que estava na tela **não media o que dizia medir**.

O **632 antigo** era **alunos de balcão**, com os agregadores congelados na premissa (651), e era
exibido e comparado **como se fosse alunos totais** — contra uma demanda total de 2.304. Em
unidades comparáveis, o break-even daquele cenário antigo era **1.208,6 alunos totais**.

Compare as três medições na mesma régua (alunos totais):

| medição | break-even (alunos totais) | leitura |
|---|---|---|
| Antes do ciclo, em unidades comparáveis | **1.208,6** | folha absoluta de R$ 50.128 (fixa), sem anuidade |
| 2ª rodada (folha percentual) | **840,6** | **artefato da diluição** — a folha encolhia com o volume |
| **Hoje** (folha fixa, anuidade ligada) | **1.152,0** | folha fixa de R$ 49.003,79 + anuidade na receita por aluno |

Ou seja: o break-even **sempre esteve na casa dos 1.200**, e a queda para 840,6 na 2ª rodada era
efeito da premissa de folha, não uma melhora do negócio. Corrigida a estrutura, o número volta ao
patamar de sempre — **1.152,0**, ligeiramente abaixo de 1.208,6 porque a anuidade entra na receita
por aluno e o agregador passou a valer 60% do ticket cheio. **O que mudou de verdade é que agora o
número é comparável com a demanda que o operador digita.**

Margens de segurança na régua correta: **2,0×** no break-even de EBITDA (2.304 ÷ 1.152,0) e
**1,49×** no break-even **de caixa** (2.304 ÷ 1.542,4, que também cobre a PMT). Para a margem de
10% que é o critério de `flag_viavel`, são necessários **1.322,6 alunos totais**.

## Os outros movimentos, lidos honestamente

**O payback melhorou (35 → 31), e menos do que a 2ª rodada dizia (28).** As causas da melhora não
são maquiagem contábil: o ticket do agregador passou a 60% do cheio (estava desacoplado e
degradava sozinho quando o ticket subia), a anuidade entrou e a folha ganhou uma régua rastreável.
Mas **três meses da melhora que a 2ª rodada mostrava eram diluição de folha** e voltaram atrás.
Duas das causas remanescentes são **premissas de produto**, e uma delas (o nível da folha) tem um
gate aberto que reverte a conclusão inteira — ver a seção final.

**O acumulado de 60 meses caiu (R$ 1,89-2,05 mi → R$ 1,65 mi) por duas razões distintas.** A
primeira é que o **CAPEX finalmente entrou inteiro na série** — as duas versões antigas diferiam
entre si em exatamente R$ 160.000, o valor da taxa de franquia, que uma série carregava e a outra
não. A segunda é a folha fixa (−R$ 150.275,33 em relação à 2ª rodada). Nenhuma das duas é piora
do negócio: é o mesmo negócio, medido direito.

**O aluguel-teto agora é um número só — e as três faixas viajam junto.** A régua é sobre o
faturamento bruto de steady-state: ideal 15% (R$ 43.238,64), **teto 20% (R$ 57.651,51 — o
canônico)** e exceção 30% (R$ 86.477,27). O canônico exibido no card é o **teto**, não a exceção:
o card mostra o limite que a operação **defende**; 30% é caso de exceção, não referência. As três
aparecem **tanto na tela quanto no PDF** — o PDF exibindo só o canônico era um dos defeitos
apontados pelo QA deste ciclo, já corrigido. O aluguel pedido de R$ 30.000 está **abaixo da faixa
ideal**, a 10,4% do faturamento.

**Os números desconfortáveis que o motor agora mostra.** O EBITDA do mês 1 é **−R$ 43.464,47**;
o do mês 4, **+R$ 21.522,79**; o do mês 8, **+R$ 108.172,47**. O caixa operacional só vira
positivo no **mês 6**. A pré-abertura consome **R$ 190.000/mês** por quatro meses (R$ 880.000
antes de abrir a porta). Isso não é novidade econômica — é a rampa, com a folha inteira — mas
antes ficava escondido pela média de steady-state.

## Como a anuidade foi modelada (e por quê)

Decisão de Felipe (dono do produto) em 2026-07-24, com a periodicidade confirmada por ele:

- **R$ 99 uma vez por ANO**, não por mês. Ler a linha como mensal a levaria de R$ 6,2 mil
  para ~R$ 74,9 mil/mês — **R$ 68,7 mil/mês de faturamento inventado**.
- **Só o aluno de balcão paga.** O aluno de Gympass/TotalPass não tem contrato com a academia;
  o agregador remunera por acesso.
- **Nem todos os alunos chegam aos 12 meses.** A elegibilidade é **derivada do churn**
  (`0,94¹²` = **47,59%**), não um número escolhido à mão — mexer no churn ajusta a
  elegibilidade sozinho.
- **Reconhecimento pro-rata mensal** (R$ 99 ÷ 12 a partir do mês 12), não um lançamento único.
  Os aniversários se espalham pelo ano; o lançamento único criaria um degrau falso no caixa e
  deslocaria o mês de virada do payback sem nenhum ganho de precisão.

Resultado: **R$ 3,9263 por aluno de balcão por mês**, ou **R$ 6.241,94/mês** — **2,2%** do
faturamento. É uma linha pequena e conservadora, e agora aparece explicitamente no payload
(`dre.receita_anuidade`), de modo que ninguém vê o faturamento subir sem saber por quê.

Ela é também a única correção que desloca o **mês de referência do steady-state** de 8 para 12,
porque só a partir do mês 12 o regime é pleno: alunos maduros **e** anuidade em cobrança.

## Conclusão de viabilidade

O Boulevard **permanece viável, com folga menor do que a 2ª rodada indicava**: margem EBITDA
**39,26%** (critério mínimo 10%), payback **31 meses** (limite 36), TIR **38,98% a.a.**, VPL @ 12%
a.a. **R$ 849.484,15** e retorno desalavancado **46,55% a.a.** A margem de segurança da demanda é
de **2,0×** sobre o break-even de EBITDA.

O que mudou de método é o que importa: agora existe **um número por indicador**, e o comitê pode
discutir a premissa em vez de discutir qual das duas telas está certa.

## Sensibilidade — folha a 26% (BLK-VIAB-11)

O ponto pendente mais material, e o que sozinho reverte a conclusão acima. Seis DREs gerenciais
reais apuraram folha de **25-26% da receita bruta** (estável, CV 0,16); o motor roda hoje a **17%**
por decisão de produto. **A estrutura (folha fixa) está decidida; o NÍVEL segue no gate da
controladoria.**

**A 26%, re-medido na estrutura nova (2026-07-24):** a folha sobe de R$ 49.003,79 para
**R$ 74.946,97/mês**, o EBITDA cai para **R$ 87.216,50 (30,26%)**, o break-even sobe para
**1.416,1 alunos totais** (margem de segurança de 1,63×), o EBITDA do mês 1 vai a
**−R$ 69.407,65**, o caixa operacional só vira no mês 8 — e **o payback NÃO OCORRE dentro dos 60
meses**: TIR **−1,05% a.a.**, VPL @ 12% a.a. **−R$ 384.910,19** e acumulado de M60
**−R$ 40.745,08**.

> **Atenção ao comparar com a versão anterior desta nota.** A medição anterior a 26% dizia
> "payback 28 → 54 meses" e "VPL −R$ 174.670,13". Aquilo foi apurado com a folha **percentual**,
> que diluía o custo na rampa. Na estrutura correta, a 26% o projeto **não se paga no horizonte**.
> A pendência ficou materialmente **pior**, não melhor — e é exatamente por isso que a estrutura
> tinha de ser corrigida antes de discutir o nível.

Nenhuma linha de receita nova compensa 9 pontos percentuais de folha: em ordem de grandeza, esta
pendência vale muitas vezes o efeito da anuidade. **É a decisão pendente de maior impacto do
ciclo** — sozinha, ela move o Boulevard de "viável com folga de 2×" para "não se paga em cinco
anos".
