# Simulação — unidade em Manaus (pino NOVA CIDADE MANAUS), v2 de trabalho

**Aproximação declarada:** a isócrona de 10 min de carro foi trocada por um círculo de área equivalente (o `osmium` não está no ambiente que funciona). Calibração abaixo.

- Nas 39 unidades de treino, o círculo de 5 km contra a isócrona real: população ×0.87 (p10 ×0.51, p90 ×1.22); renda ×1.01 (p10 ×0.91, p90 ×1.15); efeito na previsão de faturamento do M0: mediana +3%, erro típico 6%.

## Praça (área a ~10 min de carro, aproximada por círculo)

| raio (área) | população | renda per capita | dentro da faixa da rede? |
|---|---|---|---|
| 4,2 km (isócrona pequena, p25) | 380,244 | R$ 1,089 | sim |
| 5,0 km (típica, p50) | 525,532 | R$ 1,073 | sim |
| 5,8 km (grande, p75) | 717,371 | R$ 1,022 | sim |

Rede (isócrona real de 10 min): população mediana 341,257, renda mediana R$ 1,953.

## Previsão da v2 (faturamento maduro mensal, nível 2026)

| praça | master | previsto | faixa p10 · p50 · p90 |
|---|---|---|---|
| 4,2 km (isócrona pequena, p25) | desconhecida → 'outras' | R$ 261 mil | 165 · 246 · 411 mil |
| 5,0 km (típica, p50) | desconhecida → 'outras' | R$ 247 mil | 156 · 233 · 389 mil |
| 5,0 km (típica, p50) | como M1 (DF/GO) | R$ 216 mil | 137 · 204 · 341 mil |
| 5,0 km (típica, p50) | como M2 (matriz) | R$ 269 mil | 170 · 255 · 425 mil |
| 5,0 km (típica, p50) | como M3 | R$ 217 mil | 137 · 205 · 342 mil |
| 5,8 km (grande, p75) | desconhecida → 'outras' | R$ 232 mil | 147 · 219 · 366 mil |

## Viabilidade (simulador de produção; praça típica, master desconhecida)

Premissas: aluguel R$ 80,000; obra R$ 2,500,000; equipamentos R$ 1,500,000 em 60x a 2% a.m.; estúdio (+R$ 6,000/mês); balcão 69%, agregador a 60% do ticket; rampa observada (0.64, 11).

| cenário | ticket | alunos maduros | faturamento maduro | margem EBITDA | payback (meses) | viável? |
|---|---|---|---|---|---|---|
| pessimista (p10) | R$ 137 (média da rede, como o modelo aprendeu) | 1,317 | R$ 156 mil | -17% | >60 | não |
| pessimista (p10) | R$ 167 declarado (conta: mesma demanda) | 1,317 | R$ 188 mil | -3% | >60 | não |
| central (p50) | R$ 137 (média da rede, como o modelo aprendeu) | 1,988 | R$ 233 mil | 10% | >60 | não |
| central (p50) | R$ 167 declarado (conta: mesma demanda) | 1,988 | R$ 282 mil | 19% | >60 | não |
| otimista (p90) | R$ 137 (média da rede, como o modelo aprendeu) | 3,348 | R$ 389 mil | 31% | >60 | não |
| otimista (p90) | R$ 167 declarado (conta: mesma demanda) | 3,348 | R$ 471 mil | 37% | 43 | não |

**Chance de ser viável com ticket R$ 137: 5%** (39 erros do treino aplicados à previsão central).

**Chance de ser viável com ticket R$ 167: 5%** (39 erros do treino aplicados à previsão central).

Para ser viável (margem ≥ 30% e payback ≤ 36) com esses custos e ticket R$ 167, a demanda precisa equivaler a ~R$ 416 mil/mês no nível que o modelo prevê (~3,577 alunos maduros) — +68% acima da previsão central.

