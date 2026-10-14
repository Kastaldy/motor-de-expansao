# Quanto cada ajuste melhora de verdade (EXPLORATÓRIO, sem pré-registro)

## 1. Mix: fixar 'outros' no padrão

65 unidades, validação LOO (proporção de agregadores nos ativos, UX).

| regra | erro médio (p.f.) | erro nas 'outros' | erro em SP e DF/GO | Spearman |
|---|---|---|---|---|
| padrão da rede (média) | 13.6 | 11.2 | 14.3 | -1.00 |
| por estado | 9.8 | 11.2 | 9.4 | +0.66 |
| híbrida (SP e DF/GO pelo modelo; outros = padrão) | 9.8 | 11.2 | 9.4 | +0.60 |

## 2. Renda + escritórios + estado juntos: volume (alunos) e faturamento

Treino: 39 maduras de 2025; teste: as 18 unidades do UNI-02. Erro típico = mediana de |erro|.

| modelo | faturamento: erro típico | Spearman | alunos (volume): erro típico | Spearman | R² LOO faturamento (treino) |
|---|---|---|---|---|---|
| M0 (m², renda, população) | 21.5% | +0.50 | 16.3% | +0.54 | 0.306 |
| M0 + estado | 24.9% | +0.36 | 20.6% | +0.35 | 0.329 |
| M0 + escritórios | 24.8% | +0.51 | 19.8% | +0.46 | 0.310 |
| M0 + estado + escritórios | 26.0% | +0.35 | 18.8% | +0.34 | 0.309 |

## 3. A v2 com as alavancas declaradas pelo operador (18 unidades de teste)

Aritmética do simulador: mesmos alunos da v2, com o preço do Gold do cadastro e a política de agregador (Botafogo é a única que não aceita).

| cenário | erro típico | viés (mediana) | Spearman | Botafogo: previsto → real |
|---|---|---|---|---|
| v2 (só praça) | 21.5% | +0.7% | +0.50 | R$ 244,762 → R$ 697,407 |
| v2 + preço declarado | 24.3% | -0.2% | +0.67 | R$ 313,113 → R$ 697,407 |
| v2 + agregador declarado | 21.5% | +0.7% | +0.56 | R$ 276,870 → R$ 697,407 |
| v2 + preço + agregador | 24.3% | -0.2% | +0.68 | R$ 353,853 → R$ 697,407 |

Preço do Gold nas 18: mediana R$ 147 (de R$ 117 a R$ 177); o simulador usa R$ 137.

