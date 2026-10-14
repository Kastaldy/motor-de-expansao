# BLK-UNI-15 — melhorias nos três modelos

Protocolo `protocolo_uni15.md` v1.1. Rodado em 2026-10-06 17:58.

## Como ler

- **Três modelos + total:** faturamento (o total direto); balcão (vendas na unidade, sem Tem Saúde); agregador (Wellhub + TotalPass); total recombinado (balcão + agregador somados, com o ajuste de nível do UNI-09).
- **Erro típico:** quanto a previsão erra numa unidade comum (metade das unidades erra menos que isso). 22% = a unidade típica fatura 22% a mais ou a menos que o previsto. Menor = melhor.
- **Cada unidade prevista sem ela:** o modelo é refeito sem a unidade e depois prevê ela. É o erro "fora da amostra".
- **Diferença (pontos):** erro do novo − erro de hoje. Negativa = o novo erra menos.
- **Faixa provável (90%):** 9 em 10 reamostragens das unidades caem dentro. Se cruza o zero, não dá para separar do acaso. 90% e não 95% porque a pergunta é de um lado só ("o novo erra menos?").
- **R²:** quanto da diferença entre unidades o modelo acerta, fora da amostra. 1 = tudo; 0 = igual a chutar a média; negativo = pior que a média.
- **Região nova:** o modelo é refeito sem toda a região metropolitana da unidade (como numa praça onde a rede nunca esteve). "Sem Brasília" tira essa dobra: sem Brasília, o grupo DF/GO fica com 1 unidade e a conta deixa de testar praça nova.
- **Checagem do estudo:** cada teste tem a sua régua, escrita na seção. "Passa" não é adoção.

## Avisos

- Todas as unidades usadas aqui já foram vistas em análises anteriores (UNI-02 a UNI-14). Isto é estimação e conferência; o juiz de verdade é a turma de 2026, conferida em 2027.
- **Nada é adotado sem o Felipe.**
- O 4º item pedido (preço, estúdio e tier com data) está no BLK-UNI-16: depende da coleta de vendas da Growth, que parou em set/2023 por limite de chamadas da API e retoma depois.

## Resposta curta

- **T1 — região no lugar das masters.** Diferença no erro das 39 (novo − hoje, pontos): faturamento R1 -1.7 / R2 -4.6; balcão R1 +3.0 / R2 -0.4; agregador R1 -5.0 / R2 +3.8; total recombinado R1 +1.0 / R2 -1.6. Passam na checagem: nenhuma.
- **T2 — treino ampliado (~60 unidades).** Diferença nas mesmas 57 (com masters, pontos): faturamento -2.2; balcão +0.4; agregador -0.5; total recombinado -0.9. Passam na checagem: nenhuma.
- **T3 — abrir sem agregador (conferência, não é teste).** Sem precoces (5 unidades): faturamento +103% (faixa +36% a +198%), erro nelas 50% → 23%; balcão +284% (faixa +141% a +499%), erro nelas 117% → 36%. Com precoces (10 unidades): faturamento +66% (faixa +20% a +131%), erro nelas 34% → 26%; balcão +190% (faixa +95% a +340%), erro nelas 92% → 37%.
- **T4 — previsão em dois tempos (só depois de abrir).** Erro do nível maduro, v2 ajustada → meses 1–3 + v2: faturamento 26% → 17% (n 42); balcão 26% → 13% (n 47); agregador 40% → 17% (n 40). Passam na checagem: balcão, agregador. Medido em unidades que abriram COM agregador: não vale ainda para quem abre sem.

## T1 — região no lugar das masters (treino 39, teste 18)

**O que é:** R1 junta numa só as masters de fora do DF/GO; R2 troca as masters por região (DF/GO, SP ou outras UFs). Como a master M1 é exatamente o DF/GO, **o teste diz se precisamos de tantas masters, não se região explica melhor que master**.

**Régua (passa):** o erro das 39 cai ≥ 2 pontos e a queda se distingue do acaso (Holm, 2 versões por modelo, 5% de um lado), **e** o erro do teste cai ≥ 2 pontos, com e sem o nível do ano. "Região nova não piora" é mostrada, não decide.

| modelo | versão | n (39 / teste) | R² 39 | erro 39 | R² teste | erro teste | região nova sem Brasília | diferença nas 39 (faixa 90%) | diferença no teste | checagem | por que |
|---|---|---|---|---|---|---|---|---|---|---|---|
| faturamento | com masters (hoje) | 39 / 18 | 0.26 | 23.5% | 0.41 | 22.1% | 34.3% |  |  | hoje |  |
| faturamento | R1: masters de fora do DF/GO juntas | 39 / 18 | 0.39 | 21.8% | 0.52 | 17.5% | 32.8% | -1.7 (-4.3 a +4.0) | -4.6 | não passa | nas 39 cai 1.7 ponto(s), menos de 2; no teste sem o nível do ano cai menos de 2 |
| faturamento | R2: região (DF/GO, SP ou outras) | 39 / 18 | 0.45 | 18.9% | 0.27 | 25.3% | 22.9% | -4.6 (-9.5 a +4.4) | +3.2 | não passa | nas 39 a queda não se distingue do acaso; no teste piora 3.2 ponto(s); no teste sem o nível do ano cai menos de 2 |
| balcão | com masters (hoje) | 39 / 18 | 0.41 | 21.1% | 0.18 | 23.4% | 24.6% |  |  | hoje |  |
| balcão | R1: masters de fora do DF/GO juntas | 39 / 18 | 0.38 | 24.0% | 0.40 | 21.2% | 27.1% | +3.0 (-3.7 a +9.6) | -2.2 | não passa | nas 39 piora 3.0 ponto(s); no teste sem o nível do ano cai menos de 2 |
| balcão | R2: região (DF/GO, SP ou outras) | 39 / 18 | 0.39 | 20.6% | 0.17 | 33.7% | 23.1% | -0.4 (-4.1 a +9.3) | +10.3 | não passa | nas 39 cai 0.4 ponto(s), menos de 2; no teste piora 10.3 ponto(s); no teste sem o nível do ano cai menos de 2 |
| agregador | com masters (hoje) | 39 / 17 | 0.27 | 35.2% | 0.45 | 28.2% | 37.7% |  |  | hoje |  |
| agregador | R1: masters de fora do DF/GO juntas | 39 / 17 | 0.36 | 30.2% | 0.41 | 34.3% | 26.2% | -5.0 (-10.8 a +3.5) | +6.1 | não passa | nas 39 a queda não se distingue do acaso; no teste piora 6.1 ponto(s); no teste sem o nível do ano cai menos de 2 |
| agregador | R2: região (DF/GO, SP ou outras) | 39 / 17 | 0.43 | 39.0% | 0.36 | 33.8% | 40.0% | +3.8 (-3.7 a +18.5) | +5.6 | não passa | nas 39 piora 3.8 ponto(s); no teste piora 5.6 ponto(s) |
| total recombinado | com masters (hoje) | 39 / 18 | 0.29 | 21.8% | 0.04 | 22.9% | 38.5% |  |  | hoje |  |
| total recombinado | R1: masters de fora do DF/GO juntas | 39 / 18 | 0.41 | 22.8% | 0.31 | 19.5% | 33.1% | +1.0 (-4.6 a +5.1) | -3.4 | não passa | nas 39 piora 1.0 ponto(s); no teste sem o nível do ano cai menos de 2 |
| total recombinado | R2: região (DF/GO, SP ou outras) | 39 / 18 | 0.47 | 20.2% | -0.01 | 26.9% | 24.9% | -1.6 (-8.1 a +3.9) | +3.9 | não passa | nas 39 cai 1.6 ponto(s), menos de 2; no teste piora 3.9 ponto(s); no teste sem o nível do ano cai menos de 2 |

R² do agregador: nas 39 é no alvo "como se aceitasse os dois apps"; no teste, no valor real (o erro é o mesmo nos dois).

**Efeito de cada grupo contra o DF/GO** (faixa 90%; faturamento, balcão e agregador pelo coeficiente com faixa robusta; o total pela média nas 39 com reamostragem):

| modelo | versão | grupo | efeito | faixa 90% | unidades do treino no grupo |
|---|---|---|---|---|---|
| faturamento | com masters (hoje) | master M2 | +28% | -2% a +66% | 10 |
| faturamento | com masters (hoje) | master M3 | +2% | -32% a +55% | 5 |
| faturamento | com masters (hoje) | outras masters | +17% | -14% a +57% | 7 |
| faturamento | R1 | fora do DF/GO | +19% | +0% a +41% | 22 |
| faturamento | R2 | SP | +34% | +11% a +62% | 16 |
| faturamento | R2 | outras UFs | -6% | -23% a +14% | 6 |
| balcão | com masters (hoje) | master M2 | +9% | -15% a +41% | 10 |
| balcão | com masters (hoje) | master M3 | -33% | -48% a -13% | 5 |
| balcão | com masters (hoje) | outras masters | -10% | -34% a +24% | 7 |
| balcão | R1 | fora do DF/GO | -6% | -22% a +12% | 22 |
| balcão | R2 | SP | +3% | -16% a +27% | 16 |
| balcão | R2 | outras UFs | -22% | -39% a -0% | 6 |
| agregador | com masters (hoje) | master M2 | +114% | +36% a +237% | 10 |
| agregador | com masters (hoje) | master M3 | +167% | +41% a +407% | 5 |
| agregador | com masters (hoje) | outras masters | +138% | +53% a +269% | 7 |
| agregador | R1 | fora do DF/GO | +131% | +67% a +221% | 22 |
| agregador | R2 | SP | +186% | +103% a +302% | 16 |
| agregador | R2 | outras UFs | +50% | -6% a +142% | 6 |
| total recombinado | com masters (hoje) | master M2 | +26% | +3% a +63% | 10 |
| total recombinado | com masters (hoje) | master M3 | -0% | -27% a +32% | 5 |
| total recombinado | com masters (hoje) | outras masters | +14% | -10% a +55% | 7 |
| total recombinado | R1 | fora do DF/GO | +16% | -1% a +37% | 22 |
| total recombinado | R2 | SP | +33% | +10% a +59% | 16 |
| total recombinado | R2 | outras UFs | -11% | -25% a +11% | 6 |

**Quem passa a aprender com outras unidades na R2** (16 de 23 no teste e nas cegas):

| unidade | conjunto | UF | master | grupo hoje (treino) | grupo R2 (treino) |
|---|---|---|---|---|---|
| mococa-sp | teste (18) | SP | M2 | master M2 (10) | SP (16) |
| jardim-apura-sp | teste (18) | SP | M5 | outras masters (7) | SP (16) |
| cpa-mt | teste (18) | MT | M2 | master M2 (10) | outras UFs (6) |
| unai-mg | teste (18) | MG | M2 | master M2 (10) | outras UFs (6) |
| cesario-mg | teste (18) | MG | M2 | master M2 (10) | outras UFs (6) |
| floriano-mg | teste (18) | MG | M2 | master M2 (10) | outras UFs (6) |
| cotia-sp | teste (18) | SP | M2 | master M2 (10) | SP (16) |
| cambui-campinas-sp | teste (18) | SP | M6 | outras masters (7) | SP (16) |
| vila-guanabara-sc | teste (18) | SC | M4 | outras masters (7) | outras UFs (6) |
| butanta-sp | teste (18) | SP | M5 | outras masters (7) | SP (16) |
| cariacica-es | teste (18) | ES | M7 | outras masters (7) | outras UFs (6) |
| botafogo-rj | teste (18) | RJ | M3 | master M3 (5) | outras UFs (6) |
| belford-roxo-rj | cega da turma 2026 | RJ | M3 | master M3 (5) | outras UFs (6) |
| paulinia-sp | cega da turma 2026 | SP | M6 | outras masters (7) | SP (16) |
| domingos-ferreira-pe | cega da turma 2026 | PE | M2 | master M2 (10) | outras UFs (6) |
| bonsucesso-rj | cega da turma 2026 | RJ | M3 | master M3 (5) | outras UFs (6) |

**Dá para concluir:** se juntar masters ou trocar por região muda o erro nestas unidades. **Não dá:** que região explica melhor que master (DF/GO = M1), nem como fica numa praça com master nova.

## T2 — treino ampliado (39 + 18 + 3 maduras da turma B, com ajuste de nível de 2026)

**Comparação justa:** as mesmas 57 unidades, sempre previstas sem elas. Treino de 39 = cada uma das 39 prevista sem ela + as 18 do teste. Treino ampliado = cada uma das 57 prevista sem ela, com as outras ~59. O total recombinado é refeito em cada rodada (com o seu ajuste de nível).

**Régua (passa):** o erro nas 57 cai ≥ 2 pontos e a queda se distingue do acaso (Holm, 3 versões por modelo, 5% de um lado). A conta sem o nível de cada ano é leitura: se o ganho sumir nela, o texto avisa.

| modelo | versão | n treino | erro 57 (treino 39) | erro 57 (ampliado) | diferença (faixa 90%) | sem o nível do ano | só 39 | só 18 | R² 57 (39 → ampliado) | checagem | por que |
|---|---|---|---|---|---|---|---|---|---|---|---|
| faturamento | com masters (hoje) | 60 | 23.1% | 20.9% | -2.2 (-5.4 a +6.0) | -3.4 | 24% → 25% | 22% → 19% | 0.33 → 0.44 | não passa | a queda não se distingue do acaso |
| faturamento | R1 | 60 | 21.0% | 20.4% | -0.6 (-4.4 a +5.3) | -1.3 | 22% → 25% | 17% → 20% | 0.45 → 0.49 | não passa | nas 57 cai 0.6 ponto(s), menos de 2 |
| faturamento | R2 | 60 | 18.9% | 20.3% | +1.4 (-6.8 a +9.1) | +1.4 | 19% → 25% | 25% → 20% | 0.37 → 0.47 | não passa | nas 57 piora 1.4 ponto(s) |
| balcão | com masters (hoje) | 60 | 21.3% | 21.7% | +0.4 (-2.9 a +5.8) | +1.3 | 21% → 24% | 23% → 21% | 0.30 → 0.33 | não passa | nas 57 piora 0.4 ponto(s) |
| balcão | R1 | 60 | 24.0% | 21.8% | -2.2 (-6.1 a +4.9) | -5.9 | 24% → 22% | 21% → 23% | 0.39 → 0.40 | não passa | a queda não se distingue do acaso |
| balcão | R2 | 60 | 22.9% | 23.5% | +0.6 (-6.6 a +7.4) | +0.6 | 21% → 23% | 34% → 24% | 0.29 → 0.39 | não passa | nas 57 piora 0.6 ponto(s) |
| agregador | com masters (hoje) | 58 | 34.1% | 33.6% | -0.5 (-8.6 a +7.6) | +1.5 | 35% → 36% | 28% → 17% | 0.31 → 0.38 | não passa | nas 57 cai 0.5 ponto(s), menos de 2 |
| agregador | R1 | 58 | 32.0% | 32.4% | +0.4 (-5.4 a +7.5) | +1.0 | 30% → 34% | 34% → 27% | 0.37 → 0.41 | não passa | nas 57 piora 0.4 ponto(s) |
| agregador | R2 | 58 | 37.8% | 30.4% | -7.4 (-13.8 a -0.4) | +0.5 | 39% → 36% | 34% → 21% | 0.41 → 0.47 | não passa | a queda não se distingue do acaso |
| total recombinado | com masters (hoje) | 60 | 22.9% | 22.0% | -0.9 (-4.3 a +7.1) | -2.0 | 22% → 25% | 23% → 21% | 0.18 → 0.32 | não passa | nas 57 cai 0.9 ponto(s), menos de 2 |
| total recombinado | R1 | 60 | 22.2% | 22.3% | +0.1 (-4.8 a +4.9) | -2.9 | 23% → 24% | 20% → 22% | 0.36 → 0.42 | não passa | nas 57 piora 0.1 ponto(s) |
| total recombinado | R2 | 60 | 21.4% | 22.1% | +0.7 (-4.7 a +6.7) | +0.3 | 20% → 24% | 27% → 21% | 0.26 → 0.41 | não passa | nas 57 piora 0.7 ponto(s) |

**Região nova, nas mesmas 39 unidades** (erro típico; treino 39 → ampliado):

| modelo | versão | todas as regiões | sem Brasília |
|---|---|---|---|
| faturamento | com masters (hoje) | 45% → 32% | 34% → 33% |
| faturamento | R1 | 36% → 27% | 33% → 27% |
| faturamento | R2 | 28% → 26% | 23% → 26% |
| balcão | com masters (hoje) | 39% → 29% | 25% → 25% |
| balcão | R1 | 27% → 24% | 27% → 24% |
| balcão | R2 | 23% → 26% | 23% → 25% |
| agregador | com masters (hoje) | 58% → 46% | 38% → 49% |
| agregador | R1 | 55% → 34% | 26% → 34% |
| agregador | R2 | 57% → 36% | 40% → 31% |
| total recombinado | com masters (hoje) | 41% → 31% | 39% → 35% |
| total recombinado | R1 | 35% → 24% | 33% → 26% |
| total recombinado | R2 | 22% → 28% | 25% → 28% |

**Ajuste de nível de 2026** (coeficiente do treino ampliado × calibração de calendário usada no treino de 39). Esse ajuste mistura ano, unidades mais novas e a janela jan–ago, não é só "ano":

| modelo | versão | ajuste no ampliado (faixa 90%) | calibração de calendário |
|---|---|---|---|
| faturamento | com masters (hoje) | +14.6% (-1.7% a +33.6%) | -2.0% |
| balcão | com masters (hoje) | +18.7% (-3.5% a +45.9%) | -6.0% |
| agregador | com masters (hoje) | +21.8% (-9.4% a +63.9%) | +12.4% |
| faturamento | R1 | +14.7% (-0.9% a +32.7%) | -2.0% |
| balcão | R1 | +18.2% (-2.1% a +42.8%) | -6.0% |
| agregador | R1 | +20.1% (-9.8% a +59.9%) | +12.4% |
| faturamento | R2 | +15.2% (-1.5% a +34.8%) | -2.0% |
| balcão | R2 | +13.6% (-6.0% a +37.1%) | -6.0% |
| agregador | R2 | +31.0% (+1.4% a +69.0%) | +12.4% |

**Faixa dos coeficientes principais (com masters; largura da faixa robusta de 90%, em log):**

| modelo | variável | treino 39 | ampliado | ampliado ÷ 39 |
|---|---|---|---|---|
| faturamento | l_m2 | 1.16 | 0.60 | 0.52 |
| faturamento | l_renda_dom | 0.35 | 0.29 | 0.83 |
| faturamento | l_pop | 0.24 | 0.18 | 0.76 |
| faturamento | studios | 0.47 | 0.32 | 0.68 |
| balcão | l_m2 | 0.99 | 0.71 | 0.72 |
| balcão | l_renda_dom | 0.32 | 0.37 | 1.15 |
| balcão | l_pop | 0.20 | 0.23 | 1.14 |
| balcão | studios | 0.44 | 0.41 | 0.95 |
| agregador | l_m2 | 1.80 | 1.12 | 0.63 |
| agregador | l_renda_dom | 0.57 | 0.49 | 0.87 |
| agregador | l_pop | 0.52 | 0.32 | 0.61 |
| agregador | studios | 0.69 | 0.55 | 0.81 |

**Leitura descritiva — Botafogo e Bangu** (RJ, master M3, sem agregador) entram no ampliado. O que isso faz com o grupo delas e com as duas cegas do RJ (previsão em R$ mil/mês, 2026, sem agregador = 0):

| modelo | versão | variante | efeito do grupo | Belford Roxo | Bonsucesso |
|---|---|---|---|---|---|
| faturamento | com masters (hoje) | treino 39 | master M3 +2% | 149 | 133 |
| faturamento | com masters (hoje) | ampliado | master M3 +24% | 188 | 173 |
| faturamento | com masters (hoje) | ampliado sem Botafogo e Bangu | master M3 +1% | 156 | 141 |
| faturamento | com masters (hoje) | ampliado + variável sem agregador | master M3 +1% | 154 | 141 |
| faturamento | R1 | treino 39 | fora do DF/GO +19% | 165 | 149 |
| faturamento | R1 | ampliado | fora do DF/GO +19% | 183 | 168 |
| faturamento | R1 | ampliado sem Botafogo e Bangu | fora do DF/GO +16% | 177 | 160 |
| faturamento | R1 | ampliado + variável sem agregador | fora do DF/GO +17% | 174 | 159 |
| faturamento | R2 | treino 39 | outras UFs -6% | 119 | 104 |
| faturamento | R2 | ampliado | outras UFs +18% | 180 | 166 |
| faturamento | R2 | ampliado sem Botafogo e Bangu | outras UFs +10% | 166 | 149 |
| faturamento | R2 | ampliado + variável sem agregador | outras UFs +11% | 163 | 148 |
| balcão | com masters (hoje) | treino 39 | master M3 -33% | 80 | 71 |
| balcão | com masters (hoje) | ampliado | master M3 +0% | 126 | 114 |
| balcão | com masters (hoje) | ampliado sem Botafogo e Bangu | master M3 -33% | 87 | 76 |
| balcão | com masters (hoje) | ampliado + variável sem agregador | master M3 -32% | 85 | 75 |
| balcão | R1 | treino 39 | fora do DF/GO -6% | 99 | 91 |
| balcão | R1 | ampliado | fora do DF/GO -1% | 123 | 112 |
| balcão | R1 | ampliado sem Botafogo e Bangu | fora do DF/GO -6% | 114 | 102 |
| balcão | R1 | ampliado + variável sem agregador | fora do DF/GO -5% | 112 | 101 |
| balcão | R2 | treino 39 | outras UFs -22% | 77 | 69 |
| balcão | R2 | ampliado | outras UFs +9% | 139 | 128 |
| balcão | R2 | ampliado sem Botafogo e Bangu | outras UFs -2% | 120 | 107 |
| balcão | R2 | ampliado + variável sem agregador | outras UFs -1% | 118 | 107 |

**Dá para concluir:** se mais unidades no treino reduzem o erro nestas mesmas unidades. **Não dá:** separar o efeito de ter mais unidades do de acertar o nível de 2026, porque o ajuste de 2026 é aprendido com o próprio grupo avaliado.

## T3 — abrir sem agregador (faturamento e balcão)

**Conferência interna (não é teste): quem julga são as 5 cegas em 2027.** Todas as unidades sem agregador daqui já foram vistas.

**O que é:** a variável "abre sem agregador" (agregador em menos da metade dos meses) entra no modelo de faturamento e no de balcão. A base é a ampliada do T2 mais as unidades novas, levadas ao nível maduro pela curva de rampa do UNI-03 (faturamento pela curva de faturamento; balcão pela de pagantes, porque não há curva de receita de balcão). Duas leituras: sem as precoces (como no plano) e com elas (aviso: dizem pouco sobre o nível maduro). O total não entra: nas unidades sem agregador o faturamento já é o total, e o modelo de agregador não existe para elas.

**Régua de conferência (do plano):** o erro nelas cai ≥ 10 pontos e o erro geral não piora mais que 0,5 ponto. Difere do plano em dois pontos: o plano lia esse grupo na turma B + turma 2026 e pedia a faixa do efeito; aqui é a base inteira, com a faixa por reamostragem.

**Atenção:** os efeitos de faturamento e de balcão não se comparam diretamente: as unidades novas foram levadas ao maduro por curvas diferentes (a de faturamento carrega a rampa do agregador e tende a inflar as sem agregador).

| leitura | modelo | n base | sem agregador | efeito (faixa 90%) | erro nelas (sem → com) | erro geral (sem → com) | R² (sem → com) | régua de conferência |
|---|---|---|---|---|---|---|---|---|
| sem precoces | faturamento | 67 | 5 | +103% (+36% a +198%) | 50% → 23% | 23.6% → 20.9% | 0.29 → 0.43 | atinge |
| sem precoces | balcão | 67 | 5 | +284% (+141% a +499%) | 117% → 36% | 31.5% → 21.0% | 0.10 → 0.51 | atinge |
| com precoces | faturamento | 74 | 10 | +66% (+20% a +131%) | 34% → 26% | 23.4% → 23.2% | 0.34 → 0.42 | não atinge |
| com precoces | balcão | 74 | 10 | +190% (+95% a +340%) | 92% → 37% | 33.0% → 26.6% | 0.14 → 0.45 | atinge |

**Cada unidade sem agregador** (erro = real ÷ previsto − 1, cada uma prevista sem ela):

| leitura | modelo | unidade | idade | UF | metragem | sem a variável | com a variável |
|---|---|---|---|---|---|---|---|
| sem precoces | faturamento | botafogo-rj | madura | RJ | UNI-02 | +134% | +39% |
| sem precoces | faturamento | bangu-rj | madura | RJ | time | +35% | -26% |
| sem precoces | faturamento | bertioga-sp | jovem | SP | turma 30/09 | +49% | -10% |
| sem precoces | faturamento | flow-pr | jovem | PR | time | +104% | +23% |
| sem precoces | faturamento | picarras-sc | jovem | SC | time | +50% | -12% |
| sem precoces | balcão | botafogo-rj | madura | RJ | UNI-02 | +345% | +60% |
| sem precoces | balcão | bangu-rj | madura | RJ | time | +98% | -36% |
| sem precoces | balcão | bertioga-sp | jovem | SP | turma 30/09 | +111% | -18% |
| sem precoces | balcão | flow-pr | jovem | PR | time | +301% | +55% |
| sem precoces | balcão | picarras-sc | jovem | SC | time | +117% | -21% |
| com precoces | faturamento | botafogo-rj | madura | RJ | UNI-02 | +109% | +46% |
| com precoces | faturamento | bangu-rj | madura | RJ | time | +23% | -19% |
| com precoces | faturamento | bertioga-sp | jovem | SP | turma 30/09 | +45% | +1% |
| com precoces | faturamento | boqueirao-sp | precoce | SP | time | -11% | -29% |
| com precoces | faturamento | ceilandia-qnm24-df | precoce | DF | turma 30/09 | -7% | -23% |
| com precoces | faturamento | flow-pr | jovem | PR | time | +105% | +49% |
| com precoces | faturamento | laranjeiras-rj | precoce | RJ | turma 30/09 | +114% | +108% |
| com precoces | faturamento | picarras-sc | jovem | SC | time | +52% | +2% |
| com precoces | faturamento | vicente-pires-rua-8-df | precoce | DF | time | -6% | -24% |
| com precoces | faturamento | visconde-de-rio-claro-sp | precoce | SP | time | -16% | -33% |
| com precoces | balcão | botafogo-rj | madura | RJ | UNI-02 | +273% | +71% |
| com precoces | balcão | bangu-rj | madura | RJ | time | +78% | -25% |
| com precoces | balcão | bertioga-sp | jovem | SP | turma 30/09 | +107% | -4% |
| com precoces | balcão | boqueirao-sp | precoce | SP | time | +13% | -30% |
| com precoces | balcão | ceilandia-qnm24-df | precoce | DF | turma 30/09 | -11% | -40% |
| com precoces | balcão | flow-pr | jovem | PR | time | +291% | +97% |
| com precoces | balcão | laranjeiras-rj | precoce | RJ | turma 30/09 | +194% | +176% |
| com precoces | balcão | picarras-sc | jovem | SC | time | +124% | -4% |
| com precoces | balcão | vicente-pires-rua-8-df | precoce | DF | time | +1% | -34% |
| com precoces | balcão | visconde-de-rio-claro-sp | precoce | SP | time | -5% | -41% |

**Robustez do efeito** (a mesma conta em recortes):

| leitura | modelo | recorte | sem agregador (n) | efeito |
|---|---|---|---|---|
| sem precoces | faturamento | sem RJ | 3 | +100% |
| sem precoces | faturamento | só maduras | 2 | +91% |
| sem precoces | faturamento | só jovens/precoces | 3 | +101% |
| sem precoces | faturamento | faturamento das novas pela curva de pagantes | 5 | +91% |
| sem precoces | faturamento | sem botafogo-rj | 4 | +89% |
| sem precoces | faturamento | sem bangu-rj | 4 | +116% |
| sem precoces | faturamento | sem bertioga-sp | 4 | +106% |
| sem precoces | faturamento | sem flow-pr | 4 | +94% |
| sem precoces | faturamento | sem picarras-sc | 4 | +107% |
| sem precoces | faturamento | sinal estável tirando cada uma | 5 | sim |
| sem precoces | balcão | sem RJ | 3 | +278% |
| sem precoces | balcão | só maduras | 2 | +258% |
| sem precoces | balcão | só jovens/precoces | 3 | +281% |
| sem precoces | balcão | sem botafogo-rj | 4 | +248% |
| sem precoces | balcão | sem bangu-rj | 4 | +322% |
| sem precoces | balcão | sem bertioga-sp | 4 | +298% |
| sem precoces | balcão | sem flow-pr | 4 | +251% |
| sem precoces | balcão | sem picarras-sc | 4 | +302% |
| sem precoces | balcão | sinal estável tirando cada uma | 5 | sim |
| com precoces | faturamento | sem RJ | 7 | +50% |
| com precoces | faturamento | só maduras | 2 | +91% |
| com precoces | faturamento | só jovens/precoces | 8 | +60% |
| com precoces | faturamento | faturamento das novas pela curva de pagantes | 10 | +52% |
| com precoces | faturamento | sem botafogo-rj | 9 | +57% |
| com precoces | faturamento | sem bangu-rj | 9 | +71% |
| com precoces | faturamento | sem bertioga-sp | 9 | +66% |
| com precoces | faturamento | sem boqueirao-sp | 9 | +70% |
| com precoces | faturamento | sem ceilandia-qnm24-df | 9 | +68% |
| com precoces | faturamento | sem flow-pr | 9 | +57% |
| com precoces | faturamento | sem laranjeiras-rj | 9 | +65% |
| com precoces | faturamento | sem picarras-sc | 9 | +65% |
| com precoces | faturamento | sem vicente-pires-rua-8-df | 9 | +69% |
| com precoces | faturamento | sem visconde-de-rio-claro-sp | 9 | +71% |
| com precoces | faturamento | sinal estável tirando cada uma | 10 | sim |
| com precoces | balcão | sem RJ | 7 | +150% |
| com precoces | balcão | só maduras | 2 | +258% |
| com precoces | balcão | só jovens/precoces | 8 | +174% |
| com precoces | balcão | sem botafogo-rj | 9 | +168% |
| com precoces | balcão | sem bangu-rj | 9 | +202% |
| com precoces | balcão | sem bertioga-sp | 9 | +191% |
| com precoces | balcão | sem boqueirao-sp | 9 | +198% |
| com precoces | balcão | sem ceilandia-qnm24-df | 9 | +199% |
| com precoces | balcão | sem flow-pr | 9 | +165% |
| com precoces | balcão | sem laranjeiras-rj | 9 | +187% |
| com precoces | balcão | sem picarras-sc | 9 | +191% |
| com precoces | balcão | sem vicente-pires-rua-8-df | 9 | +199% |
| com precoces | balcão | sem visconde-de-rio-claro-sp | 9 | +202% |
| com precoces | balcão | sinal estável tirando cada uma | 10 | sim |

**Paralelo com o UNI-14:** lá a mesma pergunta foi medida sem reajustar o modelo (erro mediano das sem agregador − o das que aceitam os dois apps) e deu +35% no faturamento (v2) e +115% no total das duas partes. Aqui é o coeficiente de uma variável dentro do modelo, em outra base: os números não precisam bater, só o sentido.

Unidades novas usadas — sem precoces: americana-centro-sp, berrini-sp, bertioga-sp, buritis-mg, flow-pr, guarapari-es, picarras-sc; com precoces: americana-centro-sp, asa-sul-df, berrini-sp, bertioga-sp, boqueirao-sp, buritis-mg, ceilandia-qnm24-df, cidade-ocidental-go, flow-pr, guarapari-es, laranjeiras-rj, picarras-sc, vicente-pires-rua-8-df, visconde-de-rio-claro-sp.

**Fora da conta (com o motivo):**

| unidade | motivo |
|---|---|
| center-shopping-mg | jovem: sem metragem |
| gama-df | só 1 mês válido com mês de vida ≥ 3 até 2026-08 |
| icarai-rj | travada por nome desde o UNI-14 |
| jardim-das-americas-mt | precoce: sem master, estúdio |
| patio-brasil-df | jovem: sem metragem |
| sagrada-familia-mt | jovem: sem metragem |
| sao-carlos-centro-sp | precoce: sem master, estúdio |
| sao-goncalo-shopping-rj | jovem: sem metragem |
| vila-izabel-pr | precoce: sem master, estúdio |
| villa-branca-sp | jovem: sem metragem |

**Dá para ver** o tamanho da diferença nesta base. **Não dá para concluir** que melhora a previsão de unidade nova.

## T4 — previsão em dois tempos (só depois de abrir: alerta do mês 3)

**Aviso:** medido em unidades que abriram **COM** agregador. Não vale ainda para quem abre sem agregador (as turmas de 2026).

**O que é:** prever o nível maduro (média dos meses 12–18 de vida) usando os meses 1–3 junto com a v2. Faturamento e agregador não usam meses com alunos de TotalPass sem a receita de TotalPass no Financeiro (a linha só existe a partir de out/2023). Em todos entra o ajuste do ano em que a unidade amadureceu (ano com menos de 3 unidades se junta ao seguinte).

**Régua (passa):** "meses 1–3 + v2" cai ≥ 2 pontos contra "v2 ajustada ao maduro" e a queda se distingue do acaso (5% de um lado; 1 comparação por modelo). "v2 como está" é o erro direto da previsão de aprovação, sem nenhum ajuste (inclui a diferença de ano e de janela).

| modelo | n | v2 como está | v2 ajustada (régua) | só meses 1–3 | meses 1–3 + v2 | diferença (faixa 90%) | R² (ajustada → 1–3 + v2) | sem quem abriu sem agregador | checagem |
|---|---|---|---|---|---|---|---|---|---|
| faturamento | 42 | 20.1% | 26.3% | 18.1% | 16.5% | -9.7 (-14.9 a +0.7) | 0.24 → 0.69 | -6.8 (tira 2) | não passa — a queda não se distingue do acaso |
| balcão | 47 | 22.0% | 26.3% | 20.3% | 13.5% | -12.8 (-18.4 a -5.2) | 0.11 → 0.53 | -10.6 (tira 2) | passa |
| agregador | 40 | 39.4% | 40.0% | 25.4% | 16.9% | -23.1 (-35.6 a -13.1) | 0.31 → 0.80 | -23.1 (tira 0) | passa |

Anos do maduro: faturamento: 2023: 3, 2024: 4, 2025: 17, 2026: 18 (grupos 2023 | 2024 | 2025 | 2026) · balcão: 2023: 3, 2024: 9, 2025: 17, 2026: 18 (grupos 2023 | 2024 | 2025 | 2026) · agregador: 2023: 2, 2024: 4, 2025: 17, 2026: 17 (grupos 2023+2024 | 2025 | 2026).
O ajuste de 2026 coincide com as 18 do teste (todas amadurecem em 2026). A previsão da v2 das 39 vem de modelos que viram o desfecho de 2025 das outras unidades (vazamento pequeno, declarado). O total não entra: a linha de faturamento já é o total observado.

**Dá para concluir:** se os meses 1–3 melhoram a leitura do maduro em quem abriu com agregador. **Não dá:** usar isso no alerta do mês 3 de quem abre sem agregador.

