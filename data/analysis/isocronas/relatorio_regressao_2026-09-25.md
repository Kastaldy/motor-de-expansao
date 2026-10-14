# Regressão com validação fora da amostra (2026-09-25)

> Script `17_regressao.py` (variáveis fixadas antes de rodar); tabelas em `regressao/resultados.md`. READ-ONLY sobre o M1.

**Método:** regressão linear em log (OLS e ridge). Validação deixando uma unidade de fora por vez (LOO) e deixando um estado inteiro de fora (GroupKFold por UF). Modelos aninhados para medir o ganho de cada bloco de variáveis. Pesos padronizados com IC95 por bootstrap. Área de referência: isócrona de carro de 10 min. Crescimento ausente imputado pela mediana.

## R2 — faturamento Ultra (Financeiro, agosto/2026, N = 54)

| modelo | R² fora da amostra (LOO) | por UF |
|---|---|---|
| só intercepto | −0,04 | −0,11 |
| + metragem | +0,17 | +0,11 |
| + renda | **+0,41** [+0,17; +0,55] | +0,37 |
| + população | **+0,45** [+0,19; +0,62] | +0,42 |
| + concorrência, interação, canibalização | +0,39 a +0,40 | +0,29 a +0,34 |
| + crescimento | +0,32 | +0,19 |

- **Modelo recomendado:** faturamento ∝ metragem^0,66 × renda^0,50 × população^−0,17.
  - Erro típico fora da amostra de 27% com metragem e renda; 25% no modelo completo.
- **Pesos (padronizados, IC95):** renda +0,64 [+0,22; +1,08]; metragem +0,37 [+0,15; +0,61]; população −0,30 [−0,66; −0,08].
- A metragem sozinha dá +0,21 [+0,04; +0,37]; a renda sobre ela, +0,24 [+0,03; +0,40]. Concorrência, interação e canibalização não acrescentam fora da amostra. O crescimento piora: −0,08 [−0,17; −0,01].

## R1 — alunos Ultra + Engenharia do Corpo (N = 89)

- **Só a metragem explica:** R² fora da amostra +0,28 [+0,11; +0,40], ganho +0,22 [+0,07; +0,35]. Nada mais acrescenta; o crescimento piora.
- **Pesos:** metragem +0,40 [+0,20; +0,61]; interação metragem x concorrência −0,26 [−0,56; +0,04].

## Leitura

1. Há um modelo com poder real para **faturamento**: metragem e renda (10 min de carro) explicam cerca de 45% da variação entre unidades, validado fora da amostra e estável por estado. A renda age no faturamento (ticket e mix), não no número de alunos.
2. A hipótese do diretor aparece no sinal certo nas duas regressões: a metragem rende menos onde a concorrência per capita é maior (−0,20 e −0,26). Mas não melhora a previsão e o IC cruza zero. Fica como hipótese plausível, não como variável da conta.
3. Crescimento, concorrência e canibalização não sobrevivem à validação fora da amostra. O sinal de crescimento das análises anteriores estava no resíduo do modelo estrutural, não no faturamento direto.
4. Ressalvas: N pequeno (54 e 89); os alunos da EdC e da Ultra vêm de fotos de datas diferentes; população entra com sinal negativo (unidades em áreas muito densas faturam menos, com a renda controlada), o que pede cautela antes de uso em produto.
5. **Diferença para o E7 (DEC-043):** lá o desfecho era faturamento por m² com renda do catchment de 1,5 km, e deu negativo. Aqui o desfecho é faturamento com a metragem livre (coeficiente 0,66, ou seja, retorno decrescente por m²) e renda de 10 min de carro. Vale reabrir o E7 com esta especificação, pré-registrada, antes de qualquer uso no produto.
