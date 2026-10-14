# BLK-UNI-04 (parte A) — Renda da praça × churn: confirmação e ponte com a DEC-014

Versão 1.1, 2026-09-28. Escrito antes de rodar qualquer teste desta etapa. A v1.0 passou por revisão adversarial (10 achados, incorporados). O congelamento fica em
`REGISTRO_CONGELAMENTO.txt`. Roda uma vez.

## 0. De onde vem

- **UNI-01, T17:** nas 39 unidades maduras em 2025 com todos os dados, o churn mensal cai **−1,29 ponto** por desvio-padrão do log da
  renda da isócrona de carro 10 min (IC 90% −1,72 a −0,86; média de 7,0%; ΔR² LOO +0,49). Foi o efeito mais forte da
  exploração.
- **DEC-014** (jul/2026) concluiu que a retenção territorial "colapsa" com a maturidade controlada.
- **Checado antes deste protocolo:** a `renda_per_capita` que a DEC-014 usou é a do M1, e ela é **municipal** — um
  valor só por município (os 296 hexágonos de São Paulo têm todos R$ 2.713; os 999 de Brasília, R$ 2.999). A rede se
  concentra em SP e DF, então aquele teste não via a diferença de renda entre bairros.

## 1. Perguntas e testes

**Q1 — confirmação em unidades novas (decide).** A relação aparece nas unidades que amadureceram só em 2026?
- **Amostra:** unidades que **só amadureceram em 2026**, ou seja, nenhum mês com `mes_vida >= 12` até dez/2025, e com
  pelo menos 3 meses válidos em jan–ago/2026 com `mes_vida >= 12`. N esperado ≈ 15–20. As que já eram maduras em
  2025 mas ficaram fora do UNI-01 por falta de meses válidos são listadas e não entram.
- **Modelo principal:** `churn ~ log pop c10 + log(idade média) + renda`. A idade média em meses nos meses usados é
  controle de maturidade: foi ela que derrubou a renda na DEC-014. Sem a idade, o modelo sai como sensibilidade.
  - Sem m², porque as unidades novas quase não têm metragem.
  - Para garantir que isso não muda nada, o mesmo modelo sem m² é rodado nas unidades do T17, como ponte.
- **Renda:** `log iso_renda_pc__carro_10`, padronizado com a média e o desvio-padrão da amostra exata do T17 (39
  unidades). O script confere que reproduz o T17 (N = 39, efeito −1,29) antes de seguir.
- **Critério:**
  - **confirmou**: o IC 90% (HC3) fica inteiro abaixo de zero;
  - **não confirmou**: o IC 90% fica inteiro acima de −0,5 ponto (a faixa de irrelevância do UNI-01);
  - **inconclusivo**: o resto.
  - **Precedência** (a mesma do UNI-01): "não confirmou" é checado primeiro. Um IC inteiro entre −0,5 e 0 é efeito
    real, mas pequeno demais para importar.

**Q2 — persistência no tempo (secundário).** As unidades do T17, com o churn médio de jan–ago/2026 e o modelo
do T17 (`log m² + log pop + renda`). Não é dado independente (mesmas unidades); só mostra se o padrão se mantém.

**Q3 — outra medida de retenção e a renda da DEC-014 (ponte).**
- **Amostra:** as unidades de Q1 e de Q2 que têm os dois desfechos do Lifetime e as duas medidas de renda. É a
  **mesma** amostra para as duas rendas.
- **Desfechos do Lifetime** (foto de 2026):
  - `lt_eb_churn_60d`: churn de 60 dias, com encolhimento empírico-bayesiano;
  - `lt_e_meses_ativos_12m_mediano`: meses ativos esperados em 12.
- **Duas medidas de renda, cada uma sozinha com `log pop` e `log(idade média)`:**
  - a renda da isócrona;
  - a renda **municipal** do M1 (`renda_per_capita` do hexágono da unidade), a da DEC-014.
- **Reporta-se:** o efeito por desvio-padrão e o ΔR² LOO de cada uma. Também a correlação de Spearman entre o churn
  da Growth e as duas medidas do Lifetime (as fontes concordam?).

**Q4 — decomposição (descritivo).** Nas unidades do T17 (2025), sempre na mesma amostra (casos completos de todos os
controles), o efeito da renda no churn antes e depois de somar, um de cada vez e depois juntos:
- log do ticket;
- % agregador;
- % inadimplente (`inadimplente / pagantes`);
- % em cobrança (`em_cobranca / pagantes`).

Se o efeito some com o ticket, a renda anda junto com plano e preço.

**Cautela com a inadimplência:** o cancelamento por falta de pagamento entra nos próprios `cancelados`, e o
denominador é quase o mesmo do churn. Controlar por ela é controlar por parte do desfecho, então a queda do efeito é
quase por construção. Por isso a Q4 é **decomposição**, não prova de mecanismo. Reporta-se também a correlação entre
renda e idade.

## 2. Definições comuns

- Mês válido: o mesmo do UNI-01 (Financeiro presente, mês completo, operação cheia, `ativos > 0`).
- N mínimo por modelo: 12 unidades, como no UNI-01.
- Churn: `churn_pct` da Growth, cancelados sobre pagantes do mês anterior, em pontos percentuais.
- Nenhuma unidade é excluída por ser atípica.

## 3. Limites

- A Q1 tem N pequeno; "inconclusivo" é possível e não refuta o T17.
- O Lifetime é foto de 2026, com encolhimento na direção da média da rede, o que achata diferenças.
- O churn da Growth mede só o balcão (recorrentes); o agregador não entra no denominador.
