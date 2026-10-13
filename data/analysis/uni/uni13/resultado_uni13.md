# BLK-UNI-13 — resultado

Protocolo `protocolo_uni13.md` v1.1. Rodado em 2026-10-06 14:36. v2 conferida: R² LOO 0.264, erro nas 18 22.1%.
ESTIMAÇÃO com exposição: o θ̂_sem é quase calculável com números já vistos. O juiz é a turma de 2026 (contraste dentro da turma), e a leitura de 2027 provavelmente será inconclusiva.

## Parte I — fator para unidade sem agregador

- Amostra: 28 unidades fora do treino (21 maduras, 7 jovens). Aceite: nenhum 5, um só 3, os dois 20.
- **θ̂_sem = +0.595 em log (+81%).** Amplitude do bootstrap (n = 5, descritiva): +15% a +178%. Intervalo de ordem [x(1), x(5)]: +14% a +192%.
- Estratos: só maduras +130%; só jovens +59%.
- Sensibilidades: curva `pagantes` +81%; sem RJ +28%; calendário do balcão +89% (cal total -0.020, cal balcão -0.062).
- Portões: n_nenhum_>=4 OK; sinal_estavel_tirando_cada OK; estratos_mesmo_sinal OK; curva_pagantes_mesmo_sinal OK.
- **Fator congelado para conferência (não adotado).**
- Checagem interna, NÃO é teste (fator estimado sem a própria unidade): erro típico nas 'nenhum' v2 78.1% → v2 × fator 39.1%.
- Leitura estrutural (σ = fração dos ALUNOS de agregador que voltam pelo balcão; teto 1): com a = 0.29 e premissa 0,60, σ̂ = 2.28 → a substituição sozinha NÃO explica o desvio. Grade na planilha.

| unidade | UF | master | estúdio | regra | aceite | m² (fonte) | pop abaixo do treino | erro da v2 |
|---|---|---|---|---|---|---|---|---|
| picarras-sc | SC | M2 | não | jovem | nenhum | 1500 (time) | sim | +12% |
| bertioga-sp | SP | M5 | não | jovem | nenhum | 1073 (satélite) | sim | +26% |
| bangu-rj | RJ | M3 | sim | madura | nenhum | 1500 (time) |  | +78% |
| flow-pr | PR | M4 | não | jovem | nenhum | 1300 (time) |  | +112% |
| botafogo-rj | RJ | M3 | sim | madura | nenhum | 1230 (UNI-02) |  | +187% |
| buritis-mg | MG | M2 | sim | jovem | os dois | 1399 (satélite) | sim | -65% |
| mococa-sp | SP | M2 | não | madura | os dois | 1311 (UNI-02) | sim | -51% |
| americana-centro-sp | SP | M6 | não | jovem | os dois | 679 (satélite) |  | -40% |
| jardim-apura-sp | SP | M5 | não | madura | os dois | 1200 (UNI-02) |  | -29% |
| cpa-mt | MT | M2 | não | madura | os dois | 1500 (UNI-02) |  | -23% |
| cesario-mg | MG | M2 | não | madura | os dois | 1073 (UNI-02) |  | -21% |
| unai-mg | MG | M2 | não | madura | os dois | 800 (UNI-02) | sim | -19% |
| alexandrina-go | GO | M1 | não | madura | os dois | 1400 (UNI-02) |  | -18% |
| taguatinga-sul-df | DF | M1 | sim | madura | os dois | 1400 (UNI-02) |  | -18% |
| floriano-mg | MG | M2 | não | madura | os dois | 1126 (UNI-02) |  | -2% |
| cotia-sp | SP | M2 | não | madura | os dois | 750 (UNI-02) |  | -1% |
| paranoa-parque-df | DF | M1 | sim | madura | os dois | 2000 (UNI-02) |  | +2% |
| berrini-sp | SP | M2 | não | jovem | os dois | 980 (time) |  | +5% |
| botanic-mall-df | DF | M1 | sim | madura | os dois | 1206 (UNI-02) |  | +15% |
| cambui-campinas-sp | SP | M6 | não | madura | os dois | 880 (UNI-02) |  | +19% |
| ceilandia-qnm33-df | DF | M1 | sim | madura | os dois | 1750 (time) |  | +29% |
| guarapari-es | ES | M7 | não | jovem | os dois | 1877 (satélite) |  | +44% |
| valparaiso-go | GO | M1 | sim | madura | os dois | 1800 (UNI-02) |  | +51% |
| butanta-sp | SP | M5 | sim | madura | os dois | 1453 (UNI-02) |  | +59% |
| cariacica-es | ES | M7 | sim | madura | os dois | 1300 (UNI-02) |  | +71% |
| boa-vista-ba | BA | M2 | sim | madura | um só | 1600 (time) |  | +14% |
| vila-guanabara-sc | SC | M4 | não | madura | um só | 1500 (UNI-02) |  | +28% |
| noroeste-df | DF | M1 | sim | madura | um só | 2000 (UNI-02) |  | +68% |

Elegíveis excluídas: asa-sul-df (menos de 3 meses na regra (madura ou jovem 6-11)); patio-brasil-df (sem metragem); vicente-pires-rua-8-df (menos de 3 meses na regra (madura ou jovem 6-11)); cidade-ocidental-go (menos de 3 meses na regra (madura ou jovem 6-11)); center-shopping-mg (sem metragem); jardim-das-americas-mt (menos de 3 meses na regra (madura ou jovem 6-11)); sagrada-familia-mt (sem metragem); icarai-rj (travada fora (protocolo v1.1)); sao-goncalo-shopping-rj (sem metragem); villa-branca-sp (sem metragem); visconde-de-rio-claro-sp (menos de 3 meses na regra (madura ou jovem 6-11)).

## Parte II — masters

| modelo | LOO 39 | teste 18 | teste recentrado | metrô de fora | viés teste | queda LOO (pp) [IC 90%] | queda teste (pp) [IC 90%] | p | c2 | c3 | leitura |
|---|---|---|---|---|---|---|---|---|---|---|---|
| v2 | 23.5% | 22.1% | 22.3% | 44.8% | +0% |  | | | | | |
| A_masters_encolhidas | 22.1% | 24.6% | 26.5% | 27.5% | +9% | +1.4 [-4.6; +5.7] | -2.5 [-6.3; +9.2] | 0.488 | False | False | não melhora |
| B_mercado_agregador | 23.7% | 22.5% | 24.5% | 23.7% | +3% | -0.2 [-5.9; +5.3] | -0.4 [-4.7; +12.0] | 0.556 | False | False | não melhora |
| ref_v2_sem_masters | 24.3% | 25.4% | 24.5% | 25.4% | +10% |  | | | | | referência |

Erro típico deixando um metrô de fora, por dobra (%; n = 16 no metrô 1, 11 no metrô 0, 12 nas demais):

| modelo | metrô 1 | metrô 0 | demais |
|---|---|---|---|
| v2 | 73.4 | 34.3 | 34.6 |
| A_masters_encolhidas | 20.0 | 29.0 | 30.3 |
| B_mercado_agregador | 21.0 | 26.7 | 34.0 |
| ref_v2_sem_masters | 20.0 | 29.1 | 27.1 |

- Braço A: λ escolhido nas 39 = 32; nas dobras: [8, 16, 32, 64, 1000].
- Braço B (const, l_m2, l_renda_dom, l_pop, x1_parceiros_mil, x2_indep_ag, studios): [6.439, 0.559, 0.254, 0.051, 0.375, -0.172, 0.243]. Com log pop no modelo, x1 equivale à contagem de parceiros e o coeficiente de log pop deixa de ser comparável ao da v2.
- O c3 do braço B é um reteste nas 18 que deram origem à pista (uni09/resultado_uni09.md:44); com estúdios, a master acerta o nível (CADERNO:568-569).

## Turma de 2026 — previsões congeladas

`previsoes_turma_2026_uni13.csv`: as 14 com previsão (a turma tem 16). O fator só nas 5 cegas e só se os portões passaram.

