# BLK-UNI-05 — Viabilidade v2 × atual (comparação, só análise)

Versão 1.0, 2026-09-28. Escrito antes de rodar. Nada vai para produção; a troca só acontece por DEC.

## 1. Pergunta

Se a viabilidade v2 (modelo do UNI-02 + rampa observada do UNI-03 + faixa de incerteza) tivesse sido usada para
aprovar as unidades, ela teria dado respostas mais próximas da realidade que a viabilidade de hoje?

## 2. Unidades

- **Principal:** as 18 unidades de teste do UNI-02 (abertas em 2025, maduras em 2026, nunca vistas pelo modelo).
- **Secundária:** as 39 maduras de 2025 (treino), com previsões leave-one-out. A unidade prevista sai do ajuste do
  modelo e também da base de densidade.

## 3. Cenários no simulador de produção

Todos com as **mesmas premissas-padrão de custo**:
- ticket R$ 137, agregador a 60% dele, 69% de balcão;
- aluguel R$ 20 mil;
- obra R$ 2,34 mi sem financiamento;
- franquia padrão.

O custo real de cada unidade (aluguel, obra) não está disponível. Assim, a comparação isola **demanda e rampa**, que são
o que muda entre as duas viabilidades.

| cenário | demanda (alunos no maduro) | rampa |
|---|---|---|
| **REAL** | o faturamento maduro que a unidade de fato teve, convertido em alunos pela receita por aluno do simulador | observada (UNI-03: 64% no mês 1, 100% no mês 11) |
| **ATUAL** (como a ferramenta faz) | p50 de `faixa_alunos_por_densidade(m²)`, com base de densidade = treino | 500 alunos, reta até o mês 8 |
| **V2** | faturamento previsto pelo M0 (UNI-02), convertido em alunos | observada |
| **V2 pessimista** | p10 da faixa da V2 | observada |
| decomposição A | demanda do ATUAL | observada |
| decomposição B | demanda da V2 | 500 alunos, reta até o mês 8 |

- **Conversão faturamento → alunos:** `alunos = (faturamento − fixo) / receita por aluno`, ambos tirados do próprio
  simulador em regime pleno. Com isso o simulador reproduz o faturamento de entrada.
- **Faixa da V2:** p10 e p90 dos erros fora da amostra juntados (LOO do treino + teste do UNI-02). No UNI-02, a faixa
  só do treino cobriu 67%, por isso a v2 usa a faixa mais larga.

## 4. Métricas

- **Faturamento maduro:** erro típico e viés de cada cenário contra o REAL.
- **Payback (meses):** mediana de |cenário − REAL| e viés (negativo = promete payback mais rápido que o real, ou seja,
  otimista).
- **Decisão "viável"** (a regra da ferramenta: margem ≥ 30% e payback ≤ 36 meses): concordância com o REAL, número de
  **aprovações indevidas** (cenário diz viável e o REAL não) e de rejeições indevidas.

## 5. Critério (fixado antes, nas 18 unidades principais)

A V2 é **recomendada para ir a DEC** se, contra o ATUAL, as duas condições valerem:
1. tiver erro de payback menor (mediana de |erro|);
2. tiver **menos aprovações indevidas**, ou o mesmo número com erro de payback menor.

Se não, reporta-se o resultado e a V2 não é recomendada.

## 6. Limites

- O payback REAL é **simulado**: é o que o simulador dá com o faturamento que a unidade de fato teve. As unidades
  têm 1–2 anos, e o payback verdadeiro ainda não aconteceu.
- Os custos são padrão, iguais para todas as unidades.
- N = 18: diferenças pequenas não se distinguem.
