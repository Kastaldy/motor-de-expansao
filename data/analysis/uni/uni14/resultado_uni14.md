# BLK-UNI-14 — validação ampliada

Protocolo `protocolo_uni14.md` v1.1. Rodado em 2026-10-06 15:56.

## Como ler

- **Erro típico** = quanto a previsão erra numa unidade comum (a mediana das unidades). 22% = a unidade típica fatura 22% a mais ou a menos que o previsto.
- **Erro de uma unidade** = real ÷ previsto − 1. Positivo = faturou ACIMA do previsto.
- **Aviso:** todas as unidades daqui já tinham faturamento visto antes (exploratória, UNI-02, turma B, leitura precoce de 29/09). Nada aqui é teste cego: é estimação e conferência. O teste cego são as 5 unidades da turma de 2026 que ainda não foram olhadas, em 2027.

## Respostas (uma por pedido)

**(a) Modelos separados × v2.** Nas 39 maduras: separados 21.8% × v2 23.5%. No teste das 18: 22.9% × 22.1%. Na turma B: 49.2% × 28.8% (n 9). Na turma de 2026 (precoce): 45.7% × 40.5% (n 8). Menor = melhor.

**Sem agregador, na v2:** quem não tem agregador fica +35% em relação a quem aceita os dois apps (7 sem × 17 com). Sem o RJ: +30%. Passou nos 4 portões e ficou congelado para conferência (não adotado).
**Sem agregador, nos modelos separados:** quem não tem agregador fica +115% em relação a quem aceita os dois apps (7 sem × 17 com). Sem o RJ: +71%. Passou nos 4 portões e ficou congelado para conferência (não adotado).

**(b) Turma de 2026, já (precoce, sem veredito):** v2: diferença sem − com os dois +37%, fator estimado +35% → mesma direção do fator (3 sem, 4 com); duas partes: diferença sem − com os dois +89%, fator estimado +115% → mesma direção do fator (3 sem, 4 com). Outros recortes na tabela P2.

**(c) Testes de master (9 braços no critério):** nenhum melhora a precisão pela régua (cair ≥ 2 pontos nas 39 E no teste). Números de cada um na tabela P3 e no gráfico 03.

**(d) Antes e depois** (variação contra a rede madura no mesmo mês; placebo = a mesma conta 6 meses antes, onde há dado): TotalPass desliga (madura, 2 eventos): balcão em R$ +3%, pagantes -10%, placebo do balcão +13% (n 2); TotalPass liga (madura, 7 eventos): balcão em R$ -25%, pagantes -26%, placebo do balcão +8% (n 3); TotalPass liga (na rampa, 7 eventos): balcão em R$ +7%, pagantes +6%, placebo do balcão +131% (n 1); Wellhub desliga (na rampa, 1 evento): balcão em R$ +3%, pagantes -5%, placebo do balcão — (n 0).

## P3 — todos os modelos em todos os testes (erro típico, %)

| modelo | 39 maduras | teste 18 | teste sem nível | região não vista | turma B | turma 2026 | queda nas 39 (pp) [IC 90%] | queda no teste (pp) [IC 90%] | p | leitura |
|---|---|---|---|---|---|---|---|---|---|---|
| v2 (vigente) | 23.5 | 22.1 | 22.3 | 44.8 | 28.8 | 40.5 |  |  |  | vigente |
| duas partes (UNI-09) | 21.8 | 22.9 | 22.7 | 40.9 | 49.2 | 45.7 | +1.7 [-3.6; +4.1] | -0.8 [-9.8; +2.9] |  | referência (UNI-09) |
| v2 sem masters (referência) | 24.3 | 25.4 | 24.5 | 25.4 | 30.5 | 37.7 | -0.8 [-6.0; +6.7] | -3.3 [-7.7; +9.9] |  | referência |
| v2 + masters com peso reduzido | 22.1 | 24.6 | 26.5 | 27.5 | 25.9 | 36.2 | +1.4 [-4.6; +5.7] | -2.5 [-6.6; +9.2] | 0.486 | não melhora |
| v2 com mercado de agregador no lugar das masters | 23.7 | 22.5 | 24.5 | 23.7 | 29.8 | 45.0 | -0.2 [-5.9; +5.7] | -0.4 [-4.6; +11.7] | 0.555 | não melhora |
| v2 + estúdio × renda | 23.3 | 20.6 | 20.8 | 46.2 | 24.4 | 36.0 | +0.2 [-7.5; +3.2] | +1.5 [-2.6; +8.7] | 0.676 | não melhora |
| v2 + tier do Wellhub (cadastro) | 20.6 | 18.7 | 21.0 | 44.1 | 28.7 | 38.5 | +2.9 [-3.0; +4.9] | +3.4 [-1.1; +8.2] | 0.409 | não melhora |
| v2 + R$ por passagem (diagnóstico) | 26.5 | 19.1 | 16.9 | 43.2 | 29.0 | 33.1 | -3.0 [-10.5; +2.2] | +3.0 [-8.0; +12.9] |  | diagnóstico (usa a receita do próprio período) |
| duas partes + masters com peso reduzido | 22.8 | 22.2 | 22.4 | 23.1 | 52.2 | 47.0 | +0.7 [-4.0; +3.3] | -0.0 [-10.6; +3.9] | 0.507 | não melhora |
| duas partes, mercado de agregador só no agregador | 21.5 | 27.5 | 27.8 | 41.7 | 48.1 | 48.6 | +2.0 [-7.2; +4.2] | -5.4 [-14.1; +8.3] | 0.681 | não melhora |
| duas partes, mercado de agregador nas duas | 22.0 | 23.4 | 21.9 | 23.2 | 61.3 | 51.5 | +1.5 [-4.3; +5.9] | -1.3 [-8.4; +8.6] | 0.496 | não melhora |
| duas partes + estúdio × renda (balcão) | 21.3 | 21.6 | 22.1 | 41.8 | 52.2 | 44.0 | +2.2 [-7.1; +4.9] | +0.5 [-10.0; +6.9] | 0.549 | não melhora |
| duas partes + tier do cadastro (agregador) | 20.3 | 19.2 | 21.6 | 41.4 | 49.2 | 43.6 | +3.2 [-2.4; +5.7] | +2.9 [-8.7; +7.1] | 0.317 | não melhora |
| duas partes + R$ por passagem (diagnóstico) | 22.8 | 23.5 | 23.6 | 41.6 | 49.2 | 41.9 | +0.7 [-4.5; +4.4] | -1.4 [-6.0; +9.6] |  | diagnóstico (usa a receita do próprio período) |

Modelos separados com braço contra os separados sem braço (o que vem do braço, e não da separação):

| modelo | queda nas 39 (pp) | queda no teste (pp) |
|---|---|---|
| duas partes + masters com peso reduzido | -1.0 | +0.8 |
| duas partes, mercado de agregador só no agregador | +0.4 | -4.6 |
| duas partes, mercado de agregador nas duas | -0.1 | -0.5 |
| duas partes + estúdio × renda (balcão) | +0.5 | +1.3 |
| duas partes + tier do cadastro (agregador) | +1.6 | +3.7 |
| duas partes + R$ por passagem (diagnóstico) | -0.9 | -0.6 |

Região não vista, por dobra (%):

| modelo | metrô 1 (Brasília) | metrô 0 | demais |
|---|---|---|---|
| v2 (vigente) | 73.4 | 34.3 | 34.6 |
| duas partes (UNI-09) | 62.9 | 38.5 | 36.8 |
| v2 sem masters (referência) | 20.0 | 29.1 | 27.1 |
| v2 + masters com peso reduzido | 20.0 | 29.0 | 30.3 |
| v2 com mercado de agregador no lugar das masters | 21.0 | 26.7 | 34.0 |
| v2 + estúdio × renda | 101.9 | 37.5 | 34.3 |
| v2 + tier do Wellhub (cadastro) | 65.4 | 36.1 | 35.7 |
| v2 + R$ por passagem (diagnóstico) | 47.8 | 38.4 | 33.5 |
| duas partes + masters com peso reduzido | 12.9 | 24.6 | 35.6 |
| duas partes, mercado de agregador só no agregador | 59.9 | 35.7 | 35.8 |
| duas partes, mercado de agregador nas duas | 21.3 | 29.3 | 34.5 |
| duas partes + estúdio × renda (balcão) | 88.9 | 40.0 | 37.5 |
| duas partes + tier do cadastro (agregador) | 61.9 | 41.4 | 37.3 |
| duas partes + R$ por passagem (diagnóstico) | 61.1 | 37.4 | 31.6 |

Unidades por dobra: metrô 1 (Brasília) 16, metrô 0 11, demais 12.

Reprodução do UNI-09: calendário do balcão -0.0622 (publicado −0,062), do agregador +0.1172 (+0,117), s_TP 0.371 (0,371); teste das 18 dos separados 22.9% (publicado 22,9%); nas 39, 21.8% por reajuste completo contra 22.2% publicado (o UNI-09 usou um ajuste de nível aproximado). O s_TP fica fixo (das 39) dentro das dobras.
Tier do cadastro × R$ por passagem nas 39: correlação 0.68. O braço D usa as 39 do treino com tier declarado; nas demais, vale a previsão do modelo base.
Os braços A e B da v2 repetem os do UNI-13: o veredito do UNI-13 continua valendo, este é complementar. Ridge one-hot nas masters equivale a um efeito aleatório de master com variância fixada pelo λ.

## P1 — fator sem agregador (estimado sem a turma de 2026)

- **v2:** +35%; faixa por reamostragem +10% a +117%; da menor à maior unidade +1% a +190%. maduras +130%; jovens +47%; sem precoces +97%; curva pagantes +18%; sem RJ +30%; sem quem mudou de aceite +36%; calendario do balcao +40%. Portões: pelo menos 4 sem agregador OK, sinal estável tirando cada uma OK, maduras e jovens no mesmo sentido OK, curva de pagantes no mesmo sentido OK. Conferência interna (não é teste): nas sem agregador, erro típico 33% sem fator → 34% com o fator estimado sem a própria unidade.
- **duas partes:** +115%; faixa por reamostragem +45% a +285%; da menor à maior unidade +44% a +463%. maduras +326%; jovens +117%; sem precoces +232%; curva pagantes +80%; sem RJ +71%; sem quem mudou de aceite +115%; calendario do total +106%. Portões: pelo menos 4 sem agregador OK, sinal estável tirando cada uma OK, maduras e jovens no mesmo sentido OK, curva de pagantes no mesmo sentido OK. Conferência interna (não é teste): nas sem agregador, erro típico 113% sem fator → 46% com o fator estimado sem a própria unidade.
- Nos modelos separados, a unidade sem agregador é prevista só pelo balcão, que usa o calendário do balcão (−6%); a v2 usa o do total (−2%). Parte da diferença entre os dois fatores vem disso (ver 'calendario do total').

| unidade | UF | regra | aceite | mudou de aceite | metragem | pop abaixo do treino | erro v2 | erro separados | sobra do balcão (0,60) |
|---|---|---|---|---|---|---|---|---|---|
| visconde-de-rio-claro-sp | SP | precoce (aviso) | nenhum |  | time |  | -0% | +43% | 0.54 |
| picarras-sc | SC | jovem | nenhum |  | time | sim | +12% | +49% | 0.90 |
| boqueirao-sp | SP | precoce (aviso) | nenhum |  | time |  | +29% | +113% | 0.91 |
| vicente-pires-rua-8-df | DF | precoce (aviso) | nenhum |  | time |  | +33% | +70% | 1.51 |
| bangu-rj | RJ | madura | nenhum |  | time |  | +78% | +219% | 1.74 |
| flow-pr | PR | jovem | nenhum |  | time |  | +112% | +240% | 2.40 |
| botafogo-rj | RJ | madura | nenhum |  | UNI-02 |  | +187% | +458% | 2.57 |
| mococa-sp | SP | madura | os dois |  | UNI-02 | sim | -51% | -51% |  |
| jardim-apura-sp | SP | madura | os dois |  | UNI-02 |  | -29% | -26% |  |
| cpa-mt | MT | madura | os dois |  | UNI-02 |  | -23% | -23% |  |
| cesario-mg | MG | madura | os dois |  | UNI-02 |  | -21% | -20% |  |
| unai-mg | MG | madura | os dois |  | UNI-02 | sim | -19% | -16% |  |
| alexandrina-go | GO | madura | os dois |  | UNI-02 |  | -18% | -18% |  |
| taguatinga-sul-df | DF | madura | os dois |  | UNI-02 |  | -18% | -17% |  |
| floriano-mg | MG | madura | os dois |  | UNI-02 |  | -2% | -1% |  |
| cotia-sp | SP | madura | os dois |  | UNI-02 |  | -1% | +3% |  |
| paranoa-parque-df | DF | madura | os dois |  | UNI-02 |  | +2% | -1% |  |
| berrini-sp | SP | jovem | os dois |  | time |  | +5% | +4% |  |
| botanic-mall-df | DF | madura | os dois |  | UNI-02 |  | +15% | +15% |  |
| cambui-campinas-sp | SP | madura | os dois |  | UNI-02 |  | +19% | +23% |  |
| ceilandia-qnm33-df | DF | madura | os dois | sim | time |  | +29% | +29% |  |
| valparaiso-go | GO | madura | os dois |  | UNI-02 |  | +51% | +49% |  |
| butanta-sp | SP | madura | os dois |  | UNI-02 |  | +59% | +47% |  |
| cariacica-es | ES | madura | os dois |  | UNI-02 |  | +71% | +76% |  |
| boa-vista-ba | BA | madura | um só | sim | time |  | +14% | +37% |  |
| vila-guanabara-sc | SC | madura | um só | sim | UNI-02 |  | +28% | +47% |  |
| noroeste-df | DF | madura | um só |  | UNI-02 |  | +68% | +83% |  |

Fora da conta (com o motivo): ceilandia-qnn32-df (menos de 2 meses válidos com mês de vida ≥ 3 até 2026-08 (tem 0)); nucleo-bandeirante-df (menos de 2 meses válidos com mês de vida ≥ 3 até 2026-08 (tem 0)); andre-de-barros-pr (menos de 2 meses válidos com mês de vida ≥ 3 até 2026-08 (tem 0)); cachamorra-rj (menos de 2 meses válidos com mês de vida ≥ 3 até 2026-08 (tem 0)); caxias-rj (menos de 2 meses válidos com mês de vida ≥ 3 até 2026-08 (tem 0)); freguesia-rj (menos de 2 meses válidos com mês de vida ≥ 3 até 2026-08 (tem 0)); sao-goncalo-centro-rj (menos de 2 meses válidos com mês de vida ≥ 3 até 2026-08 (tem 0)); via-brasil-shopping-rj (menos de 2 meses válidos com mês de vida ≥ 3 até 2026-08 (tem 0)); limeira-sp (menos de 2 meses válidos com mês de vida ≥ 3 até 2026-08 (tem 0)); patio-brasil-df (sem metragem); center-shopping-mg (sem metragem); sagrada-familia-mt (sem metragem); sao-goncalo-shopping-rj (sem metragem); sao-carlos-centro-sp (sem atributo da v2 no cadastro (master/estúdio)); villa-branca-sp (sem metragem); gama-df (menos de 2 meses válidos com mês de vida ≥ 3 até 2026-08 (tem 1)); icarai-rj (travada fora (UNI-13)); belford-roxo-rj (cega da turma de 2026 (1–2 meses de vida)); novo-gama-df (cega da turma de 2026 (1–2 meses de vida)); paulinia-sp (cega da turma de 2026 (1–2 meses de vida)); domingos-ferreira-pe (cega da turma de 2026 (1–2 meses de vida)); bonsucesso-rj (cega da turma de 2026 (1–2 meses de vida)); jardim-das-americas-mt (turma de 2026 sem previsão congelada (sem master/estúdio)); vila-izabel-pr (turma de 2026 sem previsão congelada (sem master/estúdio)).

## P2 — turma de 2026, já (precoce e já vista; sem veredito)

'Turma de 2026' = as 16 congeladas em 30/09, não 'todas as abertas em 2026'. Rio Claro, Vicente Pires R8 e Boqueirão (abertas em jan–mar) estão na estimação; Laranjeiras e Ceilândia QNM24 (abril), na validação.

| unidade | aceite | meses de vida | regra | mudou de aceite | v2 (vigente) | duas partes (UNI-09) | v2 sem masters (referência) | v2 + masters com peso reduzido | v2 com mercado de agregador no lugar das masters | v2 + estúdio × renda | v2 + tier do Wellhub (cadastro) | v2 + R$ por passagem (diagnóstico) | duas partes + masters com peso reduzido | duas partes, mercado de agregador só no agregador | duas partes, mercado de agregador nas duas | duas partes + estúdio × renda (balcão) | duas partes + tier do cadastro (agregador) | duas partes + R$ por passagem (diagnóstico) | v2 × fator | 2p × fator |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| buritis-mg | os dois | 6–11 | jovem |  | -65% | -65% | -59% | -61% | -65% | -67% | -67% | -70% | -65% | -66% | -65% | -66% | -66% | -68% | -65% | -65% |
| americana-centro-sp | os dois | 6–11 | jovem |  | -40% | -36% | -37% | -37% | -43% | -38% | -45% | -40% | -36% | -37% | -39% | -35% | -40% | -36% | -40% | -36% |
| bertioga-sp | nenhum | 6–11 | jovem |  | +26% | +77% | +39% | +35% | +33% | +34% | +26% | +26% | +69% | +76% | +64% | +86% | +77% | +77% | -7% | -18% |
| guarapari-es | os dois | 6–8 | jovem |  | +44% | +44% | +59% | +55% | +55% | +58% | +39% | +24% | +47% | +51% | +58% | +52% | +40% | +29% | +44% | +44% |
| cidade-ocidental-go | os dois | 5–7 | precoce (aviso) | sim | +41% | +36% | +29% | +32% | +47% | +22% | +38% | +42% | +34% | +34% | +45% | +24% | +35% | +37% | +41% | +36% |
| asa-sul-df | um só | 4–6 | precoce (aviso) |  | -7% | +0% | -11% | -10% | -16% | +5% | -14% | -17% | -1% | -10% | -10% | +8% | -4% | -5% | -7% | +0% |
| ceilandia-qnm24-df | nenhum | 3–4 | precoce (aviso) |  | +26% | +47% | +9% | +14% | +21% | +14% | +26% | +26% | +47% | +46% | +41% | +36% | +47% | +47% | -6% | -32% |
| laranjeiras-rj | nenhum | 3–4 | precoce (aviso) |  | +201% | +495% | +187% | +187% | +195% | +183% | +201% | +201% | +416% | +490% | +378% | +468% | +495% | +495% | +123% | +177% |

| modelo | todas | sem agregador | um só | os dois |
|---|---|---|---|---|
| v2 (vigente) | 40.5% (n 8) | 25.9% (n 3) | 6.8% (n 1) | 42.2% (n 4) |
| duas partes (UNI-09) | 45.7% (n 8) | 76.9% (n 3) | 0.3% (n 1) | 40.3% (n 4) |
| v2 sem masters (referência) | 37.7% (n 8) | 38.7% (n 3) | 11.5% (n 1) | 47.8% (n 4) |
| v2 + masters com peso reduzido | 36.2% (n 8) | 34.8% (n 3) | 10.3% (n 1) | 46.2% (n 4) |
| v2 com mercado de agregador no lugar das masters | 45.0% (n 8) | 33.4% (n 3) | 15.7% (n 1) | 51.0% (n 4) |
| v2 + estúdio × renda | 36.0% (n 8) | 34.2% (n 3) | 4.7% (n 1) | 47.9% (n 4) |
| v2 + tier do Wellhub (cadastro) | 38.5% (n 8) | 25.9% (n 3) | 13.9% (n 1) | 41.7% (n 4) |
| v2 + R$ por passagem (diagnóstico) | 33.1% (n 8) | 25.9% (n 3) | 16.7% (n 1) | 41.2% (n 4) |
| duas partes + masters com peso reduzido | 47.0% (n 8) | 69.0% (n 3) | 1.2% (n 1) | 41.2% (n 4) |
| duas partes, mercado de agregador só no agregador | 48.6% (n 8) | 75.6% (n 3) | 10.0% (n 1) | 44.3% (n 4) |
| duas partes, mercado de agregador nas duas | 51.5% (n 8) | 64.4% (n 3) | 9.9% (n 1) | 51.5% (n 4) |
| duas partes + estúdio × renda (balcão) | 44.0% (n 8) | 86.2% (n 3) | 7.6% (n 1) | 43.1% (n 4) |
| duas partes + tier do cadastro (agregador) | 43.6% (n 8) | 76.9% (n 3) | 4.2% (n 1) | 40.0% (n 4) |
| duas partes + R$ por passagem (diagnóstico) | 41.9% (n 8) | 76.9% (n 3) | 5.1% (n 1) | 36.4% (n 4) |
| v2 × fator | 40.5% (n 8) | 6.7% (n 3) | 6.8% (n 1) | 42.2% (n 4) |
| 2p × fator | 36.1% (n 8) | 31.5% (n 3) | 0.3% (n 1) | 40.3% (n 4) |

| modelo | recorte | sem agregador | com os dois | diferença na turma | fator estimado | leitura |
|---|---|---|---|---|---|---|
| v2 | todas | 3 | 4 | +37% | +35% | mesma direção do fator |
| v2 | sem as unidades de 2 meses | 1 | 4 | +37% | +35% | mesma direção do fator |
| v2 | sem quem mudou de aceite | 3 | 3 | +110% | +35% | mesma direção do fator |
| v2 | curva de pagantes | 3 | 4 | +24% | +35% | mesma direção do fator |
| duas partes | todas | 3 | 4 | +89% | +115% | mesma direção do fator |
| duas partes | sem as unidades de 2 meses | 1 | 4 | +89% | +115% | mesma direção do fator |
| duas partes | sem quem mudou de aceite | 3 | 3 | +176% | +115% | mesma direção do fator |
| duas partes | curva de pagantes | 3 | 4 | +72% | +115% | mesma direção do fator |

A projeção pela curva de rampa nos meses 3–5 de vida tem incerteza grande (no faturamento, ~−34% a +22% em torno da mediana); a curva vem de unidades que abriram com agregador, o que tende a inflar as sem agregador.

## P4 — antes e depois

Datas pela Growth (passagens); o TotalPass só entra no Financeiro a partir de out/2023. 'Sensível' = o Financeiro mostra a fonte antes da data da Growth, ou a unidade volta ao estado anterior em até 6 meses. Placebo = a mesma conta 6 meses antes (o 'depois' do placebo tem 5 meses, para não pegar o mês da mudança). Quase todos os eventos com antes e depois são de TotalPass: nenhum 'Wellhub liga' tem meses depois suficientes (reler por volta de mar/2027).

| tipo | fase | recorte | n | balcão R$ | pagantes | alunos de agregador | total R$ | placebo balcão | n placebo |
|---|---|---|---|---|---|---|---|---|---|
| TotalPass desliga | madura | todos | 2 | +3% | -10% | -63% | -9% | +13% | 2 |
| TotalPass desliga | madura | sem os sensíveis | 1 | +6% | -15% | -53% | -2% | +9% | 1 |
| TotalPass liga | madura | todos | 7 | -25% | -26% | +31% | — | +8% | 3 |
| TotalPass liga | madura | sem os sensíveis | 7 | -25% | -26% | +31% | — | +8% | 3 |
| TotalPass liga | na rampa | todos | 7 | +7% | +6% | +24% | -13% | +131% | 1 |
| TotalPass liga | na rampa | sem os sensíveis | 5 | +6% | +6% | +64% | — | — | 0 |
| Wellhub desliga | na rampa | todos | 1 | +3% | -5% | -97% | -24% | — | 0 |
| Wellhub desliga | na rampa | sem os sensíveis | 1 | +3% | -5% | -97% | -24% | — | 0 |

| unidade | evento | mês | mês de vida | data | pagantes | balcão R$ | alunos de agregador | total R$ | placebo balcão | situação |
|---|---|---|---|---|---|---|---|---|---|---|
| alexandrina-go | TotalPass desliga | 2026-03 | 14 | ok | +13% | +14% | +0% | +5% | +5% | não persiste (1 mês) |
| campo-largo-pr | TotalPass desliga | 2026-05 | 25 | ok | -15% | +6% | -53% | -2% | +9% | ok |
| vila-guanabara-sc | TotalPass desliga | 2026-05 | 15 | ok | -5% | +1% | -70% | -15% | +17% | ok [sensível] |
| boa-vista-ba | Wellhub desliga | 2025-03 | 7 (rampa) | ok | -5% | +3% | -97% | -24% | — | ok |
| santos-sp | TotalPass liga | 2022-10 | 10 (rampa) | só Growth (Financeiro não registrava TotalPass) | +6% | +6% | +114% | — | — | ok |
| taubate-sp | TotalPass liga | 2022-10 | 6 (rampa) | só Growth (Financeiro não registrava TotalPass) | +27% | +38% | +64% | — | — | ok |
| aclimacao-sp | TotalPass liga | 2023-01 | 16 | só Growth (Financeiro não registrava TotalPass) | -31% | -32% | +37% | — | — | ok |
| mooca-sp | TotalPass liga | 2023-01 | 16 | só Growth (Financeiro não registrava TotalPass) | -26% | -34% | +28% | — | — | ok |
| plaza-sul-sp | TotalPass liga | 2023-01 | 16 | só Growth (Financeiro não registrava TotalPass) | -27% | -25% | +50% | — | — | ok |
| vila-mariana-sp | TotalPass liga | 2023-01 | 16 | só Growth (Financeiro não registrava TotalPass) | -25% | -22% | +59% | — | — | ok |
| brasilandia-sp | TotalPass liga | 2023-02 | 8 (rampa) | só Growth (Financeiro não registrava TotalPass) | -23% | -14% | +105% | — | — | ok |
| jundiai-sp | TotalPass liga | 2023-02 | 18 | só Growth (Financeiro não registrava TotalPass) | -39% | -38% | +22% | — | +8% | ok |
| vila-guilherme-sp | TotalPass liga | 2023-02 | 6 (rampa) | só Growth (Financeiro não registrava TotalPass) | -40% | -21% | -0% | — | — | ok |
| aguas-claras-df | TotalPass liga | 2023-10 | 7 (rampa) | só Growth (Financeiro não registrava TotalPass) | +66% | +137% | -45% | — | — | ok |
| lago-sul-df | TotalPass liga | 2023-10 | 23 | só Growth (Financeiro não registrava TotalPass) | +36% | +61% | +9% | — | -24% | ok |
| sobradinho-df | TotalPass liga | 2023-10 | 3 (rampa) | só Growth (Financeiro não registrava TotalPass) | — | — | — | — | — | poucos meses |
| setor-oeste-go | TotalPass liga | 2023-12 | 10 (rampa) | fora (Financeiro mostra a fonte antes) | +19% | +75% | -13% | — | +131% | ok [sensível] |
| jardim-botanico-df | TotalPass liga | 2024-03 | 16 | ok | +15% | +17% | +31% | — | +65% | ok |
| alexandrina-go | TotalPass liga | 2025-06 | 5 (rampa) | fora (Financeiro mostra a fonte antes) | -8% | +7% | +24% | -13% | — | ok [sensível] |
| sao-goncalo-shopping-rj | TotalPass liga | 2025-12 | 3 (rampa) | ok | — | — | — | — | — | poucos meses |
| cidade-ocidental-go | TotalPass liga | 2026-07 | 6 (rampa) | ok | — | — | — | — | — | poucos meses |
| asa-sul-df | Wellhub liga | 2026-05 | 3 (rampa) | ok | — | — | — | — | — | poucos meses |
| jardim-das-americas-mt | Wellhub liga | 2026-07 | 5 (rampa) | ok | — | — | — | — | — | poucos meses |
| sagrada-familia-mt | Wellhub liga | 2026-07 | 10 (rampa) | ok | — | — | — | — | +4% | poucos meses |
| caxias-rj | Wellhub liga | 2026-09 | 3 (rampa) | ok | — | — | — | — | — | sem meses depois (set/2026): só gráfico |
| laranjeiras-rj | Wellhub liga | 2026-09 | 5 (rampa) | ok | — | — | — | — | — | sem meses depois (set/2026): só gráfico |
| vicente-pires-rua-8-df | Wellhub liga | 2026-09 | 8 (rampa) | ok | — | — | — | — | — | sem meses depois (set/2026): só gráfico |
