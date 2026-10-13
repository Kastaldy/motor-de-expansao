# BLK-UNI-16 — preço de tabela do plano

Protocolo `protocolo_uni16.md` v1.1. Rodado em 2026-10-07 10:59.

## Como ler

- **Preço relativo:** o preço cheio do Gold que a unidade mais praticou no 1º ano, contra a mediana das unidades maduras no mesmo período. 10% acima ≈ um degrau de R$ 10–15 na tabela.
- **Efeito:** quanto o faturamento (ou o balcão, ou o agregador) muda numa unidade com preço 10% acima, com o resto do modelo igual (metragem, renda, população, master, estúdio).
- **Faixa de 90%:** 9 em 10 vezes o efeito verdadeiro cai dentro. Se cruza o zero, não dá para separar do acaso. O veredito ainda desconta que são 3 modelos testados (por isso uma faixa que não cruza o zero pode sair "não se distingue").
- **Erro típico:** quanto a previsão erra numa unidade comum, com cada unidade prevista sem ela. Menor = melhor. **R²:** quanto da diferença entre unidades o modelo acerta fora da amostra (1 = tudo; 0 = igual a chutar a média).
- **Unidades:** as 57 do modelo; 38 têm preço de tabela no 1º ano. Sem preço: 10 por falta de dado de venda (abriram antes da coleta) e 9 porque só venderam com promoção ou outro plano. Essas entram com uma marca, nos dois lados.

## Avisos

- A venda registra a primeira cobrança: nos meses de promoção (R$ 9,90) o preço do plano não aparece.
- O preço do 1º ano pode ter subido porque a unidade encheu (reação à demanda): isso puxa para um efeito positivo.
- Prever não é causar. As 57 unidades já foram muito usadas. **"Não se distingue de zero" não prova que o preço não importa**: a variação de preço entre unidades é pequena e o teste tem pouca força.
- **Nada é adotado sem o Felipe.**

## Resposta curta

- **Efeito:** faturamento +9.4% por 10% de preço (faixa -2.4% a +22.6%) — não se distingue de zero; balcão +15.5% por 10% de preço (faixa -1.0% a +34.8%) — não se distingue de zero; agregador -1.8% por 10% de preço (faixa -18.4% a +18.2%) — não se distingue de zero.
- **Portão de adoção** (o erro cai ≥ 2 pontos no faturamento e no total): **não passa**. faturamento 25.2% → 26.6%; balcão 21.7% → 24.5%; agregador 30.2% → 30.7%; total recombinado 23.0% → 25.5%.

## Efeito (principal)

| modelo | n | com preço | efeito de +10% no preço | faixa 90% | p | leitura |
|---|---|---|---|---|---|---|
| faturamento | 57 | 38 | +9.4% | -2.4% a +22.6% | 0.191 | não se distingue de zero |
| balcão | 57 | 38 | +15.5% | -1.0% a +34.8% | 0.123 | não se distingue de zero |
| agregador | 56 | 37 | -1.8% | -18.4% a +18.2% | 0.869 | não se distingue de zero |

## Portão de adoção (erro de cada unidade prevista sem ela)

| modelo | n | sem o preço | com o preço | diferença (faixa 90%) | R² (sem → com) | só nas com preço |
|---|---|---|---|---|---|---|
| faturamento | 57 | 25.2% | 26.6% | +1.4 (-2.9 a +7.8) | 0.39 → 0.40 | +7.7 (n 38) |
| balcão | 57 | 21.7% | 24.5% | +2.8 (-5.2 a +5.5) | 0.28 → 0.32 | +3.0 (n 38) |
| agregador | 56 | 30.2% | 30.7% | +0.5 (-0.4 a +1.5) | 0.42 → 0.39 | +0.4 (n 37) |
| total recombinado | 57 | 23.0% | 25.5% | +2.5 (-4.1 a +6.0) | 0.24 → 0.27 | +4.0 (n 38) |

## Leituras (sem veredito)

| modelo | leitura | n | efeito de +10% no preço | faixa 90% |
|---|---|---|---|---|
| faturamento | só as unidades com preço | 38 | +10.5% | -8.0% a +32.6% |
| faturamento | sem Botafogo | 56 | +6.1% | -3.8% a +17.0% |
| faturamento | preço de HOJE no cadastro (depois do resultado), mesmas unidades | 38 | +10.3% | -6.8% a +30.6% |
| faturamento | referência só do mesmo mês | 57 | +11.3% | -1.4% a +25.7% |
| balcão | só as unidades com preço | 38 | +16.7% | -9.6% a +50.6% |
| balcão | sem Botafogo | 56 | +9.1% | -2.1% a +21.7% |
| balcão | preço de HOJE no cadastro (depois do resultado), mesmas unidades | 38 | +15.6% | -3.6% a +38.6% |
| balcão | referência só do mesmo mês | 57 | +16.9% | -0.8% a +37.8% |
| agregador | só as unidades com preço | 37 | -0.9% | -18.2% a +20.1% |
| agregador | sem Botafogo | 56 | -1.8% | -18.4% a +18.2% |
| agregador | preço de HOJE no cadastro (depois do resultado), mesmas unidades | 37 | -1.2% | -23.8% a +28.1% |
| agregador | referência só do mesmo mês | 56 | +1.2% | -15.8% a +21.8% |
| balcão (decomposição) | alunos de balcão (log de pagantes) | 57 | +9.7% | -5.5% a +27.3% |
| balcão (decomposição) | ticket do balcão (balcão ÷ pagantes) | 57 | +5.3% | +2.6% a +8.1% |

Preço relativo das 38 unidades: mediana +0%, de -17% a +17% das maduras.

