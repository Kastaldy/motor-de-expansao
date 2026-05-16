# Validacao Penetracao Ultra por Hex

**Data:** 2026-05-15  
**Unidades analisadas:** 54  
**Regra top/bottom:** tercis por metrica; maior valor = melhor desempenho.

## Amostra

| Fonte de populacao do hex | n |
| --- | ---: |
| censo_2022_hex | 28 |
| m1_municipal_proxy | 21 |
| hex_nao_encontrado | 4 |
| sem_hex_id_res7 | 1 |

| Metrica | n valido | n nulo | Min | P25 | Mediana | P75 | Max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Alunos totais | 54 | 0 | 1,206 | 1,667 | 2,304 | 2,820 | 6,251 |
| Faturamento | 54 | 0 | 76,568 | 141,853 | 198,450 | 258,621 | 617,061 |
| Penetracao alunos totais | 49 | 5 | 0.01% | 0.42% | 2.70% | 4.79% | 13.14% |
| Receita por habitante | 49 | 5 | 0.01 | 0.33 | 2.11 | 3.76 | 9.10 |
| Ticket medio por aluno | 54 | 0 | 51.56 | 71.12 | 84.12 | 98.39 | 154.88 |
| Pagantes | 54 | 0 | 529 | 1,116 | 1,496 | 1,995 | 3,984 |

## Regra de Classificacao

Top e bottom sao definidos separadamente para cada lente de desempenho: alunos totais, faturamento, penetracao, receita por habitante, ticket medio e pagantes.

| Metrica | n valido | Bottom <= P33 | Top >= P67 | Top n | Bottom n |
| --- | ---: | ---: | ---: | ---: | ---: |
| Alunos totais | 54 | 1,940 | 2,685 | 18 | 18 |
| Faturamento | 54 | 154,554 | 238,238 | 18 | 18 |
| Penetracao alunos totais | 49 | 0.80% | 4.13% | 17 | 17 |
| Receita por habitante | 49 | 0.98 | 2.82 | 17 | 16 |
| Ticket medio por aluno | 54 | 75.36 | 94.38 | 18 | 18 |
| Pagantes | 54 | 1,241 | 1,902 | 18 | 18 |

## Correlacoes

Tabela ordenada por maior associacao absoluta de Spearman. Pearson e Spearman usam apenas pares validos; pares com n<5 ou sem variacao ficam fora desta tabela.

Nota: penetracao e receita por habitante usam `pop_hex_base` como denominador; associacoes com populacao, densidade do hex, delta e ratio de densidade sao diagnosticas e nao causais.

| Metrica | Variavel | n | Pearson | Spearman |
| --- | --- | ---: | ---: | ---: |
| Penetracao alunos totais | Populacao do hex | 49 | -0.463 | -0.950 |
| Penetracao alunos totais | Densidade do hex | 49 | -0.447 | -0.940 |
| Receita por habitante | Populacao do hex | 49 | -0.464 | -0.939 |
| Receita por habitante | Densidade do hex | 49 | -0.448 | -0.934 |
| Penetracao alunos totais | Ratio densidade hex/GeoFusion | 49 | -0.231 | -0.798 |
| Receita por habitante | Ratio densidade hex/GeoFusion | 49 | -0.232 | -0.796 |
| Penetracao alunos totais | Delta densidade hex vs GeoFusion | 49 | -0.448 | -0.785 |
| Receita por habitante | Delta densidade hex vs GeoFusion | 49 | -0.449 | -0.775 |
| Receita por habitante | Score hibrido | 49 | -0.230 | 0.414 |
| Pagantes | Delta densidade hex vs GeoFusion | 49 | 0.157 | 0.397 |
| Penetracao alunos totais | Score hibrido | 49 | -0.307 | 0.395 |
| Ticket medio por aluno | Delta densidade hex vs GeoFusion | 49 | 0.223 | 0.375 |
| Pagantes | Ratio densidade hex/GeoFusion | 49 | 0.035 | 0.366 |
| Receita por habitante | Densidade GeoFusion 1km | 49 | 0.093 | 0.362 |
| Faturamento | Delta densidade hex vs GeoFusion | 49 | 0.222 | 0.355 |
| Penetracao alunos totais | Densidade GeoFusion 1km | 49 | 0.138 | 0.348 |
| Pagantes | Densidade GeoFusion 1km | 54 | -0.152 | -0.345 |
| Ticket medio por aluno | Ratio densidade hex/GeoFusion | 49 | 0.131 | 0.345 |
| Faturamento | Ratio densidade hex/GeoFusion | 49 | 0.065 | 0.328 |
| Ticket medio por aluno | Renda per capita M1 | 49 | 0.272 | 0.315 |
| Ticket medio por aluno | Score M1 | 49 | 0.203 | 0.284 |
| Receita por habitante | Concorrentes 2km | 49 | 0.092 | 0.279 |
| Faturamento | Populacao do hex | 49 | 0.235 | 0.278 |
| Faturamento | Densidade do hex | 49 | 0.222 | 0.274 |
| Penetracao alunos totais | Concorrentes 2km | 49 | 0.121 | 0.270 |
| Alunos totais | Delta densidade hex vs GeoFusion | 49 | 0.043 | 0.265 |
| Ticket medio por aluno | Populacao do hex | 49 | 0.235 | 0.263 |
| Pagantes | Populacao do hex | 49 | 0.169 | 0.253 |
| Ticket medio por aluno | Densidade GeoFusion 1km | 54 | -0.117 | -0.252 |
| Alunos totais | Densidade do hex | 49 | 0.043 | 0.248 |
| Alunos totais | Ratio densidade hex/GeoFusion | 49 | 0.006 | 0.247 |
| Pagantes | Densidade do hex | 49 | 0.156 | 0.242 |
| Alunos totais | Populacao do hex | 49 | 0.053 | 0.234 |
| Ticket medio por aluno | Densidade do hex | 49 | 0.222 | 0.234 |
| Faturamento | Densidade GeoFusion 1km | 54 | 0.016 | -0.230 |
| Pagantes | Score hibrido | 49 | 0.040 | -0.217 |

## Padroes Top vs Bottom

Medianas dos top tercis contra bottom tercis. Esta leitura destaca contrastes operacionais, mas nao substitui analise causal.

| Corte de desempenho | Variavel | Top mediana | Bottom mediana | Delta |
| --- | --- | ---: | ---: | ---: |
| Alunos totais | Populacao do hex | 198,861.0 | 53,503.9 | 145,357.1 |
| Alunos totais | Densidade do hex | 34,501.0 | 9,947.7 | 24,553.3 |
| Alunos totais | Renda per capita M1 | 2,713.4 | 2,713.4 | 0.0 |
| Alunos totais | Score M1 | 100.0 | 100.0 | 0.0 |
| Alunos totais | Score hibrido | 100.0 | 100.0 | -0.0 |
| Alunos totais | Concorrentes 1km | 1.0 | 1.0 | 0.0 |
| Alunos totais | Distancia concorrente mais proximo | 954.8 | 846.4 | 108.4 |
| Alunos totais | Densidade GeoFusion 1km | 5,553.7 | 7,547.5 | -1,993.8 |
| Alunos totais | Metragem | 1,600.0 | 1,378.0 | 222.0 |
| Alunos totais | Alunos agregadores | 1,118.5 | 482.0 | 636.5 |
| Faturamento | Populacao do hex | 418,608.0 | 65,235.3 | 353,372.7 |
| Faturamento | Densidade do hex | 80,819.9 | 11,294.0 | 69,525.9 |
| Faturamento | Renda per capita M1 | 2,999.2 | 2,713.4 | 285.8 |
| Faturamento | Score M1 | 100.0 | 100.0 | 0.0 |
| Faturamento | Score hibrido | 100.0 | 100.0 | -0.0 |
| Faturamento | Concorrentes 1km | 0.0 | 1.0 | -1.0 |
| Faturamento | Distancia concorrente mais proximo | 1,064.6 | 803.0 | 261.6 |
| Faturamento | Densidade GeoFusion 1km | 4,801.4 | 8,436.2 | -3,634.8 |
| Faturamento | Metragem | 1,550.0 | 1,400.0 | 150.0 |
| Faturamento | Alunos agregadores | 760.5 | 539.5 | 221.0 |
| Penetracao alunos totais | Populacao do hex | 33,186.6 | 2,817,381.0 | -2,784,194.4 |
| Penetracao alunos totais | Densidade do hex | 6,009.0 | 486,907.5 | -480,898.5 |
| Penetracao alunos totais | Renda per capita M1 | 2,713.4 | 2,999.2 | -285.8 |
| Penetracao alunos totais | Score M1 | 100.0 | 100.0 | 0.0 |
| Penetracao alunos totais | Score hibrido | 100.0 | 100.0 | 0.0 |
| Penetracao alunos totais | Concorrentes 1km | 1.0 | 0.0 | 1.0 |
| Penetracao alunos totais | Distancia concorrente mais proximo | 954.8 | 1,177.7 | -222.9 |
| Penetracao alunos totais | Densidade GeoFusion 1km | 6,473.0 | 4,034.0 | 2,439.0 |
| Penetracao alunos totais | Metragem | 1,400.0 | 1,500.0 | -100.0 |
| Penetracao alunos totais | Alunos agregadores | 546.0 | 681.0 | -135.0 |
| Receita por habitante | Populacao do hex | 33,186.6 | 2,817,381.0 | -2,784,194.4 |
| Receita por habitante | Densidade do hex | 6,009.0 | 486,992.8 | -480,983.8 |
| Receita por habitante | Renda per capita M1 | 2,713.4 | 2,999.2 | -285.8 |
| Receita por habitante | Score M1 | 100.0 | 100.0 | 0.0 |
| Receita por habitante | Score hibrido | 100.0 | 100.0 | 0.0 |
| Receita por habitante | Concorrentes 1km | 1.0 | 0.0 | 1.0 |
| Receita por habitante | Distancia concorrente mais proximo | 954.8 | 1,229.6 | -274.8 |
| Receita por habitante | Densidade GeoFusion 1km | 6,473.0 | 4,019.3 | 2,453.6 |
| Receita por habitante | Metragem | 1,500.0 | 1,500.0 | 0.0 |
| Receita por habitante | Alunos agregadores | 546.0 | 679.5 | -133.5 |

## Outliers

Outliers foram detectados por IQR e mantidos na analise.

| Metrica | Unidade | UF | Tipo | Valor | Fonte pop |
| --- | --- | --- | --- | ---: | --- |
| Alunos totais | PRAIA GRANDE | SP | alto | 6,251 | hex_nao_encontrado |
| Pagantes | BOTAFOGO | RJ | alto | 3,984 | m1_municipal_proxy |
| Faturamento | BOTAFOGO | RJ | alto | 617,061 | m1_municipal_proxy |
| Faturamento | NOROESTE | DF | alto | 525,038 | m1_municipal_proxy |
| Faturamento | PRAIA GRANDE | SP | alto | 454,048 | hex_nao_encontrado |
| Faturamento | SANTOS | SP | alto | 451,068 | m1_municipal_proxy |
| Penetracao alunos totais | SUZANO | SP | alto | 13.14% | censo_2022_hex |
| Receita por habitante | ASA NORTE | DF | alto | 9.10 | censo_2022_hex |
| Ticket medio por aluno | BOTAFOGO | RJ | alto | 154.88 | m1_municipal_proxy |

## Achados e Cautelas

- Amostra pequena: 54 unidades no total, 49 com populacao de hex valida; os resultados indicam hipoteses operacionais, nao causalidade.
- Parte da amostra usa populacao municipal proxy; densidade e penetracao nesses casos devem ser lidas com cautela e nao comparadas como se fossem setor censitario real.
- Penetracao e receita por habitante usam `pop_hex_base` no denominador; correlacoes fortes com populacao ou densidade do hex sao diagnostico da formula, nao evidencia causal.
- Maior associacao monotona observada para Alunos totais: Delta densidade hex vs GeoFusion (Spearman=0.265, n=49).
- Maior associacao monotona observada para Faturamento: Delta densidade hex vs GeoFusion (Spearman=0.355, n=49).
- Maior associacao nao derivada diretamente de pop_hex para Penetracao alunos totais: Score hibrido (Spearman=0.395, n=49).
- Maior associacao nao derivada diretamente de pop_hex para Receita por habitante: Score hibrido (Spearman=0.414, n=49).
- No corte por penetracao, o maior contraste entre top e bottom tercil aparece em Densidade GeoFusion 1km: mediana top=6,473.0, bottom=4,034.0.
- Foram encontrados 9 outliers por regra IQR; eles foram mantidos na analise e listados para leitura individual.
- Nao e possivel inferir churn, conversao, causalidade de concorrencia ou capacidade ideal por hex apenas com esta amostra; o Bloco 5 deve tratar TAM/SAM como calibracao inicial conservadora.

_Gerado por `jobs/pipelines/validar_penetracao_ultra_hex.py`_