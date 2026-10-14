# Rascunho de épico — Inteligência de Unidade (expansão ↔ operações)

> Rascunho de 2026-09-25 para discussão. Não está no `tasks/backlog.md`. Camada paralela, READ-ONLY sobre o M1.

## Objetivo

Um único entendimento do que faz uma unidade faturar e reter bem, usado nos dois sentidos:
- **Expansão:** projetar o faturamento maduro de um ponto com região, tamanho e concorrência. É o substituto da viabilidade atual, que só lê metragem.
- **Operações:** comparar cada unidade com o que a praça dela sustenta (aproveitamento), para orientar ticket, retenção e mix de agregadores.

## Regra de método (vale para todos os blocos)

1. **Explorar primeiro, confirmar depois, em dados diferentes.** A exploração usa o período até dez/2025. A confirmação usa jan–ago/2026 e as unidades abertas depois da exploração, pelo backtest rolling-origin que o Projeto Lifetime já usa.
2. **Critério escrito antes de rodar a confirmação**, no molde do E7.
3. **Maturidade sempre controlada.** A DEC-014 mostrou que a parte previsível da retenção por unidade era a maturidade, não a geografia.
4. **Nenhum outlier excluído para ganhar métrica.** Só erro de dado corrigido (como o Guarujá) ou unidade imatura.

## Blocos

| bloco | entrega | insumos já disponíveis |
|---|---|---|
| UNI-00 Painel da rede | Base única unidade × mês: faturamento do Financeiro, ativos, recorrentes, agregadores, churn, vendas e visitas (Growth); metragem e vagas; isócronas e renda; concorrência com alunos reais; crescimento; variáveis de abertura do estudo de inauguração; agregados do Lifetime por unidade | tudo no repositório, na VPS e no OneDrive |
| UNI-01 Exploração | Hipóteses listadas e medidas no período de exploração: região × ticket, % agregador por UF (RJ = 0%, SP = 50%), tamanho × concorrência, crescimento, curva de rampa, retenção por coorte | UNI-00 |
| UNI-02 Faturamento maduro esperado | Modelo de faturamento (hoje: metragem + renda 10 min + população; R² fora da amostra 0,39–0,45) refinado com o que sobreviver à UNI-01 e confirmado no período novo; faixa p10–p90 | UNI-00, UNI-01 |
| UNI-03 Curva de rampa | Substitui a rampa linear de 8 meses do simulador pela curva observada (86% do patamar no mês 3, estabiliza em ~6 meses; recorrentes e agregadores separados) | estudo de inauguração, Growth |
| UNI-04 Retenção e churn de unidade | Churn e retenção explicados por maturidade, região e operação; ponte com o Projeto Lifetime (risco por aluno agregado por unidade) | Lifetime, Growth |
| UNI-05 Viabilidade v2 (produto) | Challenger rodando ao lado da viabilidade atual; troca por DEC quando o challenger ganhar no período de confirmação | UNI-02, UNI-03 |
| UNI-06 Aproveitamento na Visão Executiva (produto) | Real × esperado por unidade, com faixa, como diagnóstico para operações | UNI-02 |

## Ganchos já identificados

- **Botafogo e o RJ:** o estudo de inauguração mostra unidades do RJ com 0% de agregadores e receita por aluno bem maior. Isso é candidato direto a explicar os maiores erros do modelo de faturamento, sem dado novo.
- **Churn previsível pela região (R² 0,38):** medido sem controle de maturidade. Precisa ser refeito controlando maturidade antes de qualquer conclusão (DEC-014).
- **Metragem explica o patamar de alunos** nas duas análises (inauguração e regressão); a região explica o ticket.
