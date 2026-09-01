# E4 — Régua absoluta do gate socioeconômico, por preferência revelada

> Medido em 2026-08-26, relatório escrito em 2026-08-29. O experimento rodou, foi discutido
> e decidiu coisas — mas nunca virou arquivo. Este documento fecha essa dívida.

## Pergunta pré-registrada

**Qual o pior contexto socioeconômico em que uma unidade Ultra madura ainda entrega
faturamento por m² aceitável?**

Diferente do E1 e do E3: aqui **não se busca correlação**, busca-se um **envelope**. Entre as
unidades que performam, qual o mínimo de renda e população observado. Envelope é descritivo e
sobrevive a N pequeno; correlação não.

**Critério de NO-GO, escrito antes:** se as unidades que performam e as que não performam
tiverem a mesma distribuição de contexto, não há piso defensável — e o gate vira decisão
executiva pura, não medição.

## Dados

54 unidades com faturamento (base de **royalties**, `faturamento_financeiro` — não a Growth,
que subdimensiona ~19%), metragem, hexágono e inauguração. Maturidade: mín. 15 meses, mediana
27, máx. 66. Com renda setorial no hexágono: **49**.

Desfecho: faturamento mensal médio dos últimos 12 meses com faturamento > 0, dividido pela
metragem.

| | R$/m²/mês |
|---|---|
| p10 | 97,69 |
| p25 | 125,19 |
| **mediana** | **170,00** |
| p75 | 213,79 |
| p90 | 275,96 |

---

## A leitura que CONDICIONA no desfecho — e por que ela engana

Comparando "quem performa" (n=40, acima do p25 da rede) contra "quem não performa" (n=14):

| contexto | performa (mediana) | não performa | deslocamento |
|---|---|---|---|
| renda setorial | R$ 1.594 | R$ 1.163 | **+431** · IC95 [+57, +1.196] — **não cruza zero** |
| população do hex | 31.252 | 33.354 | −2.102 · IC95 [−35.392, +14.334] — **cruza zero** |

Pelo critério pré-registrado, **a renda passaria**: o IC não cruza zero.

**E é aqui que o experimento quase deu falso positivo.** Os dois grupos são definidos pelo
**próprio desfecho**. Comparar "quem performa" com "quem não performa" condiciona na variável
que se quer explicar, e acha diferença com facilidade mesmo quando a variável não tem poder de
separação útil. É a mesma armadilha que derrubou o E1.

## A leitura que NÃO condiciona — e que decide

A pergunta honesta é a inversa: **dada uma faixa de renda, que fração das unidades performa?**

| faixa de renda do setor | n | acima da mediana da rede | % | fat/m² mediano |
|---|---|---|---|---|
| até R$ 1.100 | 12 | 5 | **42%** | 145,7 |
| R$ 1.100 – 1.600 | 17 | 8 | 47% | 170,2 |
| R$ 1.600 – 2.500 | 8 | 4 | 50% | 173,9 |
| R$ 2.500 ou mais | 12 | 7 | **58%** | 225,6 |

**Spearman(renda setorial, fat/m²) = +0,286 · IC95 [−0,018, +0,554] — cruza zero.**

O gradiente existe e está na direção esperada, mas:

- ele vai de **42% a 58%** — dezesseis pontos percentuais entre o extremo pobre e o extremo
  rico da rede;
- na faixa **mais pobre**, 5 de cada 12 unidades **batem a mediana da rede**;
- o IC da correlação **cruza zero**.

Não existe nível de renda abaixo do qual as unidades param de funcionar. **Não há piso a
extrair.**

## Envelope observado (o que de fato se pode afirmar)

Entre as 40 unidades que performam:

| contexto | mín | p05 | p10 | mediana |
|---|---|---|---|---|
| renda setorial | **R$ 848** | R$ 883 | R$ 978 | R$ 1.594 |
| população do hex | 1.567 | 4.150 | 7.667 | 31.252 |

As oito unidades que performam no contexto mais pobre:

| unidade | município | renda setorial | pop. do hex | fat/m² |
|---|---|---|---|---|
| VALPARAÍSO | Valparaíso de Goiás/GO | 848 | 15.650 | **187,2** |
| SANTA MARIA | Brasília/DF | 878 | 6.497 | **212,5** |
| ARAPOANGA PLANALTINA | Brasília/DF | 885 | 29.225 | 164,2 |
| CARIACICA | Cariacica/ES | 960 | 44.445 | **271,3** |
| CEILÂNDIA | Brasília/DF | 989 | 65.235 | 127,2 |
| CAMPO LARGO | Campo Largo/PR | 1.040 | 12.460 | 182,5 |
| MOOCA | São Paulo/SP | 1.058 | 67.424 | 192,2 |
| CPA | Cuiabá/MT | 1.174 | 14.787 | 144,2 |

Cariacica, a R$ 960 de renda per capita, entrega **271 R$/m²** — acima do p90 da rede.

## Veredito

**NO-GO para piso calibrado de renda.** O gate socioeconômico não pode ser derivado deste
dado: ele é **decisão executiva declarada**, não medição.

**População é ainda mais clara**: as distribuições de quem performa e de quem não performa são
indistinguíveis (IC do deslocamento cruza zero com folga).

## Convergência independente

Este resultado é de **agosto de 2026** e vinha de faturamento por m² na base de royalties. Em
**2026-08-28**, por caminho totalmente diferente — teste de falso-veto do gate de zona morta
contra as 54 unidades maduras, com catchment de 1,5 km — a **DEC-042** chegou à mesma parede:
nenhum piso de renda acima de **R$ 599** sobrevive sem reprovar unidade boa, e o corte teve de
cair de R$ 1.600 para R$ 500.

Duas medições independentes, dois desfechos diferentes, a mesma conclusão: **para uma marca
low-cost/massa, renda da praça não é critério de exclusão** (CLAUDE.md §1).

## Limite, escrito no resultado e não em nota de rodapé

A amostra é onde a Ultra **escolheu** abrir. O envelope responde *"a pior praça em que
operamos e ainda performamos"*, **não** *"a pior praça em que alguém performaria"*. Toda
extrapolação abaixo do envelope observado é opinião, não medição.
