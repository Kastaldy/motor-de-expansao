# BLK-UNI-02 — Confirmação do modelo de faturamento maduro (pré-registro)

Versão 1.0, 2026-09-28. Escrito antes de calcular qualquer previsão ou erro nas unidades de teste. O congelamento
(SHA-256) fica em `REGISTRO_CONGELAMENTO.txt`. Roda uma vez.

## 1. O que se testa

Um modelo ajustado com o que se sabia até dez/2025 consegue prever o faturamento maduro de unidades que ele **nunca
viu**, melhor que a viabilidade de hoje?

## 2. Amostras (rolling-origin)

- **Treino:** as maduras de 2025 do UNI-01 (amostra primária com metragem, N = 39). Desfecho = média do log do
  faturamento do Financeiro nos meses válidos de 2025 com `mes_vida >= 12`.
- **Teste:** unidades **fora do treino** com pelo menos 3 meses válidos em jan–ago/2026 com `mes_vida >= 12`, e com
  metragem.
  - Desfecho: a mesma medida, em 2026.
  - Metragem: a oficial (`dados_academias.xlsx`) ou, na falta dela, a estimativa por satélite corrigida pelo viés da
    calibração (÷ 1,12; `coleta_metragem/metragem_estimada.csv`).
  - A fonte da metragem fica marcada por unidade.
- **Ajuste de calendário (principal):** o faturamento de 2026 é comparado com previsões em "reais de 2026". O fator é
  a mediana, **nas unidades de treino**, da diferença entre o log do faturamento maduro de 2026 e o de 2025. Usa só
  unidades de treino, nunca as de teste. A sensibilidade roda sem o ajuste.

## 3. Modelos comparados (fixados antes)

| id | modelo | como prevê o faturamento de uma unidade de teste |
|---|---|---|
| **ATUAL** | regra da viabilidade de hoje (só metragem) | `faixa_alunos_por_densidade(m², base de treino)` p50 × receita por aluno mediana do treino (2025) × calendário |
| **M0** | modelo do estudo | `log fat ~ log m² + log renda c10 + log pop c10`, ajustado no treino, × calendário |
| **M0d** | M0 + hipótese do diretor | M0 + fração de independentes + log m² × fração |
| **INGÊNUO** | sem informação | mediana do faturamento do treino × calendário |

## 4. Métricas (nas unidades de teste)

- **Erro típico:** mediana de |real / previsto − 1|.
- **Viés:** mediana de (real / previsto − 1).
- **Ordenação:** Spearman entre previsto e real, com IC 90% por bootstrap (2.000 reamostragens de unidades).
- **Faixa p10–p90 do M0:** quantis dos resíduos LOO do treino aplicados à previsão. Reporta-se a cobertura no teste
  (esperado ≈ 80%).

## 5. Critério de confirmação (fixado antes)

- **O M0 se confirma** se as duas condições valerem:
  1. seu erro típico é **menor** que o do ATUAL e que o do INGÊNUO;
  2. o IC 90% do Spearman entre previsto e real **exclui zero**.
- **O M0d (hipótese do diretor)** só se confirma se, além disso, o erro típico dele for menor que o do M0.
  - Declarado de antemão: com N ≈ 15–20, uma interação quase certamente não se distingue.
- Se nada se confirmar, reporta-se tal qual. Não há segunda rodada no mesmo dado.

## 6. Sensibilidades

- (a) Só unidades com metragem oficial (sem estimativa por satélite).
- (b) Estimativa por satélite sem a correção de viés.
- (c) Sem ajuste de calendário.

## 7. Descritivos

- Erro por unidade de teste, com UF, fonte da metragem e se aceita agregador.
- As unidades do RJ sem agregador ficam destacadas: o modelo nunca viu unidade sem agregador.

## 8. Limites declarados

- **N de teste pequeno** (≈ 15–20): o teste só distingue diferenças grandes.
- **Metragem por satélite** tem erro típico de ~20% (calibração com 9 medições).
- **Unidades de teste** abriram em 2025. O maduro delas são os meses 12–20 de vida; o UNI-03 mostrou que o nível dos
  meses 11–13 já é o maduro.
- **Mesmo produto, praças novas:** o teste inclui UFs com pouca ou nenhuma unidade no treino (RJ, MG). É o caso real de
  expansão.
