# Modelo em duas partes (alunos × ticket) — protocolo (exploração, dados até dez/2025)

Versão 1.0, 2026-09-28. Escrito antes de rodar. Segunda análise do plano aprovado por Felipe. Resultado em
`resultado_duas_partes.md`.

## Ideia

O faturamento é igual a alunos × ticket. A anatomia dos erros mostrou que o modelo erra sobretudo o volume de alunos, e
o UNI-01 mostrou que os fatores agem em partes diferentes: tamanho e população → alunos; renda e agregador → ticket.

Um modelo em duas partes só difere do modelo de uma equação se cada parte usar variáveis **diferentes**. Com as mesmas
variáveis nas duas, a soma das previsões em log é idêntica à do modelo de uma equação. Por isso as variantes restringem
o que entra em cada parte.

## Variantes (todas fixadas antes)

| id | parte alunos (log ativos) | parte ticket (log faturamento/ativos) |
|---|---|---|
| M0 | uma equação só: log faturamento ~ log m² + log renda c10 + log pop c10 (referência atual) | — |
| M0d | M0 + hipótese do diretor (fração de independentes + m² × fração) | — |
| M1 | log m² + log pop + log renda | log renda |
| M2 | M1 + hipótese do diretor | log renda |
| M3 | M1 + política de agregador da UF | log renda + política de agregador da UF |
| M4 | M2 + política de agregador da UF | log renda + política de agregador da UF |

**Política de agregador da UF:** mediana do % agregador das **outras** unidades da mesma UF (6 últimos meses válidos
até dez/2025, `mes_vida >= 6`). É conhecida antes de abrir; no RJ, por exemplo, é 0%.

## Avaliação

- **Amostra:** as maduras de 2025 do UNI-01 com todas as variáveis de todas as variantes. Todas as variantes usam as
  **mesmas** unidades; quem cair fica listado.
- **LOO:** a previsão de faturamento de cada unidade é feita com ela fora, e nas variantes em duas partes as duas
  partes também são ajustadas sem ela. Métrica: R² fora da amostra sobre o log do faturamento.
- **Retirando a cidade inteira (leave-one-metro-out):** mesma coisa, tirando todas as unidades da cidade (metro) da
  unidade prevista. Mede se o modelo generaliza para uma praça nova.
- Também: erro percentual típico (mediana de |real/previsto − 1|).

## Regra de decisão (fixada antes)

- Uma variante só **supera o M0** se ganhar pelo menos **+0,02** de R² nas duas avaliações (LOO e retirando a cidade).
- Entre as que superam, vale a mais simples.
- Se nenhuma superar, o M0 segue como estrutura do UNI-02. O modelo em duas partes fica como ferramenta de
  **explicação** do erro (volume × preço), não de previsão.

## Limites

- N ≈ 38 e o mesmo dado de todas as análises exploratórias: diferenças abaixo de ~0,03 são ruído. A anatomia mostrou
  que uma única unidade pode mover o R² em mais que isso.
- A confirmação de verdade continua sendo nas unidades que amadurecem em 2026, que dependem da metragem.
