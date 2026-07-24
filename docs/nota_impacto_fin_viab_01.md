# Nota de impacto — FIN-VIAB-01 (reconciliação do simulador de viabilidade)

**Para:** Comitê de Expansão · **De:** Estratégia e Growth · **Data:** 2026-07-24
**Caso:** Boulevard Shopping Londrina (1.050 m², aluguel R$ 30.000, ticket R$ 147,
demanda premissa 2.304 alunos, rampa 8 meses, obra R$ 600 mil em 4 parcelas,
equipamentos R$ 1,4 mi em 60 meses a 1,8% a.m., taxa de franquia R$ 160 mil)

## O que mudou

A tela e o PDF do **mesmo cenário** vinham divergindo: payback 35 no KPI e 33 no gráfico,
acumulado de 60 meses de R$ 1,89 mi ou R$ 2,05 mi conforme a fonte, aluguel-teto de
R$ 55.535 ou R$ 105.813. A causa era estrutural: existiam **cinco séries mensais
independentes e nove KPIs com implementação dupla**. O FIN-VIAB-01 colapsou tudo num
**motor único** — uma linha do tempo de M-4 a M+60 da qual todo indicador deriva. Tela,
API e PDF agora leem o mesmo objeto e **não recalculam nada**.

Junto vieram quatro correções de conteúdo: o **ticket do agregador** deixou de ser R$ 82
absoluto e virou **60% do ticket cheio**; a **folha** deixou de ser R$ 50.128 fixos e
virou **17% do faturamento bruto**; o **IR/CSLL** deixou de aplicar alíquotas efetivas
sobre a receita líquida e passou a apurar o Lucro Presumido com a **faixa explícita** do
adicional de 10%; e a **anuidade** — linha `Simulador!J10` que existia na planilha e nunca
tinha sido implementada — **entrou no motor**.

## Antes × depois

| Indicador | Antes (o que a ferramenta mostrava) | Depois (número único) |
|---|---|---|
| Faturamento (steady) | R$ 277.675,90 | **R$ 288.257,57** |
| *dos quais anuidade* | *não existia* | ***R$ 6.241,94*** |
| Mês de referência do steady-state | implícito (maturação, mês 8) | **mês 12**, declarado em `premissas.mes_referencia_steady` |
| EBITDA | R$ 103.580,72 (37,30%) | **R$ 113.159,69 (39,26%)** |
| IR/CSLL | R$ 30.060,08 | **R$ 29.362,42** |
| Break-even | 632 alunos **de balcão** | **840,6 alunos TOTAIS** |
| Payback | 35 (KPI) / 33 (gráfico) | **28 meses** |
| Aluguel-teto | R$ 105.813,13 (PDF) / R$ 55.535,18 (tela) | **R$ 86.477,27** (com as faixas ideal R$ 43.238,64 e teto R$ 57.651,51 visíveis nos dois lugares) |
| Acumulado M60 | R$ 1.894.476,90 / R$ 2.054.476,90 | **R$ 1.795.729,88** |
| TIR / VPL @ 12% a.a. | não existia | **45,48% a.a. / R$ 986.172,80** |

## Delta isolado de cada correção

Medido no motor novo, revertendo **um coeficiente por vez** a partir da configuração antiga
(que reproduz exatamente o EBITDA de R$ 103.580,72 do "antes"). A anuidade é medida à parte,
como o último degrau, porque só ela muda a **régua** (o mês de referência do steady-state):

| Correção | Efeito no faturamento | Efeito no EBITDA | Efeito no payback |
|---|---|---|---|
| Ticket do agregador: R$ 82 → 60% do cheio (R$ 88,20) | **+R$ 4.339,72** | +R$ 3.467,37 | 35 → 33 (-2) |
| Folha: R$ 50.128 fixos → 17% da bruta | 0 | +R$ 2.923,26 | 35 → 32 (-3) |
| IR/CSLL: efetivo sobre a líquida → faixa do presumido | 0 | 0 (é abaixo do EBITDA; **-R$ 1.848,94** de imposto) | 35 → 34 (-1) |
| **As três juntas** (anuidade ainda desligada) | **+R$ 4.339,72** | **+R$ 5.652,88** | **35 → 29 (-6)** |
| **Anuidade ligada** (R$ 99/ano, só balcão, 47,59% elegíveis, pro-rata) | **+R$ 6.241,94** | **+R$ 3.926,09** | **29 → 28 (-1)** |
| **As quatro juntas** | **+R$ 10.581,67** | **+R$ 9.578,97** | **35 → 28 (-7)** |

Os deltas de EBITDA **não somam** (3.467 + 2.923 = 6.391, contra 5.653 juntos) porque há
interação: com o faturamento maior trazido pelo agregador, a folha de 17% também custa mais.
Pela mesma razão a anuidade entrega R$ 3.926 de EBITDA sobre R$ 6.242 de receita — o resto
vai embora em deduções, impostos, custo variável e folha.

**A anuidade também mexe no break-even e no fluxo:** break-even de EBITDA cai de **859,6 para
840,6** alunos totais, o acumulado de M60 sobe **+R$ 159.101,27** e o VPL @ 12% a.a. sobe
**+R$ 111.066,14**. Ela é a única correção que desloca o **mês de referência do steady-state**
de 8 para 12, porque só a partir do mês 12 o regime é pleno: alunos maduros **e** anuidade em
cobrança.

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

## Leitura honesta dos movimentos que mais chamam atenção

**O payback melhorou (35 → 28) e o break-even "piorou" (632 → 840,6). As duas leituras puxam
para lados opostos, e a segunda é a que importa.**

A melhora do payback tem três causas somáveis e nenhuma delas é maquiagem contábil: o ticket
do agregador passou a **60% do cheio** (estava desacoplado, degradava sozinho quando o ticket
subia e subestimava a receita), a folha virou **17% do faturamento** (era R$ 50.128 fixos,
18,05% do faturamento antigo — o nível mudou pouco, mas ela passou a **escalar com o volume**)
e a **anuidade** entrou. Ainda assim, duas dessas três são **premissas de produto**, e uma
delas (o nível da folha) tem um gate aberto que pode reverter o resultado inteiro — ver a
seção de sensibilidade no fim.

A "piora" do break-even é de outra natureza: é **correção de unidade de medida**. O 632 antigo
era **alunos de balcão** com os agregadores congelados na premissa (651), e era exibido e
comparado na tela **como se fosse alunos totais** — contra uma demanda total de 2.304. Em
unidades comparáveis, o break-even do cenário antigo era **1.208,6 alunos totais**; o de hoje é
**840,6**. Medido de forma consistente, portanto, o break-even **caiu** — e o número exibido
agora é diretamente comparável com a demanda que o operador digita. A margem de segurança do
Boulevard é de **2,7×** (2.304 ÷ 840,6). O break-even **de caixa** — que também cobre a PMT —
é de **1.336,6 alunos**, ainda **1,7×** abaixo da demanda premissa. Para margem de 10% (o
critério de `flag_viavel`), são necessários **1.007,2 alunos totais**.

Por que a segunda importa mais: a melhora do payback muda o **quanto** o projeto parece bom; a
correção do break-even muda **o que o número significa**. Enquanto a régua estava errada, todo
comparativo com a demanda estava errado junto — inclusive nos cenários já apresentados ao
comitê.

**O acumulado de 60 meses (R$ 1,89-2,05 mi → R$ 1,80 mi) caiu porque o CAPEX finalmente entrou
inteiro na série.** As duas versões antigas diferiam entre si em exatamente R$ 160.000 — o
valor da taxa de franquia, que uma série carregava e a outra não. O número de hoje é o correto,
não uma piora do negócio.

**O aluguel-teto agora é um número só — e as três faixas viajam junto.** A régua é sobre o
faturamento bruto de steady-state: ideal 15% (R$ 43.238,64), teto 20% (R$ 57.651,51) e exceção
30% (R$ 86.477,27 — o canônico). As três aparecem **tanto na tela quanto no PDF**; o PDF
exibindo só o canônico era um dos defeitos apontados pelo QA deste ciclo, já corrigido. O
aluguel pedido de R$ 30.000 está **abaixo da faixa ideal**, a 10,4% do faturamento.

**Um número desconfortável que o motor agora mostra:** o **EBITDA do mês 1 é R$ -10.139,56**.
O custo operacional é integral desde a abertura, enquanto os alunos rampam por 8 meses. O
caixa operacional só vira positivo no **mês 6**. Isso não é novidade econômica — é a rampa —
mas antes ficava escondido pela média de steady-state.

## Conclusão de viabilidade

O Boulevard **permanece viável e ficou mais folgado**: margem EBITDA 39,26% (critério mínimo
10%), payback 28 meses (limite 36), TIR 45,48% a.a. e retorno desalavancado 46,55% a.a. A
diferença é que agora existe **um número por indicador**, e o comitê pode discutir a premissa
em vez de discutir qual das duas telas está certa.

## Sensibilidade — folha a 26% (BLK-VIAB-11)

O ponto pendente mais material, e o que sozinho reverte a conclusão acima. Seis DREs gerenciais
reais apuraram folha de **25-26% da receita bruta** (estável, CV 0,16); o motor roda hoje a
**17%** por decisão de produto, e a calibração do nível segue no gate da controladoria.

**A 26%:** a folha sobe de R$ 49.003,79 para **R$ 74.946,97**, o EBITDA cai para
**R$ 87.216,50 (30,26%)**, o break-even sobe para **987,8 alunos totais**, o payback vai de
**28 para 54 meses**, o acumulado de 60 meses despenca de R$ 1,80 mi para **R$ 189.087,77** e o
**VPL @ 12% a.a. fica negativo (-R$ 174.670,13)**. Ou seja: a unidade **deixaria de atender o
critério de payback de 36 meses** e voltaria para a mesa.

Em ordem de grandeza, essa pendência vale **7× o efeito da anuidade** — nenhuma linha de
receita nova compensa 9 pontos percentuais de folha. É a decisão pendente de maior impacto do
ciclo.
