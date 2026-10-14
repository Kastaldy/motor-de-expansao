# Fachada dentro da v2 — teste EXPLORATÓRIO (2026-09-30)

As notas já foram vistas; não é confirmação. A confirmação limpa são as notas restantes do Juan (protocolo_fachada.md v1.3).

Resíduo fora da amostra (treino de 2025 por LOO; teste do UNI-02 com calendário). Nas unidades com nota, a correção pela fachada é ajustada sem a própria unidade (LOO). Erro típico = mediana de |erro| no faturamento.

| modelo base | amostra | N | erro base | + só correção de nível | + fachada | IC 90% da diferença (fachada − nível) | Spearman base → + fachada | efeito da fachada (% por ponto) |
|---|---|---|---|---|---|---|---|---|
| M0 (praça) | sem Botafogo | 24 | 20.2% | 21.2% | 25.8% | [-4.8; +11.4] p.p. | +0.51 → +0.46 | +8% |
| M0 (praça) | com Botafogo | 25 | 20.8% | 27.0% | 25.6% | [-1.3; +2.6] p.p. | +0.49 → +0.35 | +2% |
| v2 (praça + estúdios + master real) | sem Botafogo | 24 | 21.8% | 17.5% | 18.9% | [-2.1; +9.9] p.p. | +0.58 → +0.52 | +6% |
| v2 (praça + estúdios + master real) | com Botafogo | 25 | 22.5% | 16.4% | 17.7% | [+0.1; +3.7] p.p. | +0.53 → +0.46 | -0% |

Notas usadas: 42 unidades (Felipe, Vini e Juan; média quando há mais de uma). Juan: coluna `Notas`.
