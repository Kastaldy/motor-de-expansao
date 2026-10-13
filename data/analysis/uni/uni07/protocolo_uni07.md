# BLK-UNI-07 — Incerteza do modelo e faixas de segurança

Versão 1.0, 2026-09-30. Escrito antes de rodar e revisado por um revisor adversarial, também antes de rodar (§8).
Só análise.

## 1. Pergunta

Quanto a previsão da v2 pode errar, e como transformar isso em **faixas de segurança** para os indicadores da
viabilidade (faturamento, alunos, margem, payback, chance de ser viável)?

**Modelo:** a v2 de trabalho adotada pelo Felipe em 29/09 (praça + estúdios + master real). O M0 (só praça) é reportado
como referência.

## 2. Erros fora da amostra

Log do real − log do previsto:
- **Treino** (39 maduras de 2025): resíduo LOO. Cada unidade é prevista por um modelo ajustado sem ela.
- **Teste** (18 do UNI-02): previsão do modelo ajustado nas 39, com o calendário de 2026 (−2%). É um teste **fora do
  tempo**.
- **Desvio-padrão** do erro em log e erro típico em % (mediana de |erro|), no treino, no teste e juntos (57).
- **Checagens de sanidade:**
  - 39 unidades de treino e 18 de teste;
  - todas com master;
  - o M0 reproduz o UNI-02 no teste (erro típico ~22%, viés ~+1%).

## 3. Faixas e calibração

Faixas de 80% (p10–p90) e de 50% (p25–p75):
- **(A) Só o treino:** quantis dos 39 resíduos LOO, aplicados ao teste. É a **única checagem limpa fora do tempo**. No
  UNI-02, com o M0, ela cobriu 67%.
- **(B) Conjunta, sem a própria unidade:** a faixa de cada unidade sai dos resíduos das outras 56. **Não é teste
  limpo:** a faixa de cada unidade de teste já contém os erros das outras 17 de 2026.

**Cobertura:**
- % do real dentro da faixa;
- IC 90% exato (Clopper-Pearson);
- para (A) e (B), no teste (18); para (B), também no total (57).

**Regra de adoção (fixada antes):**
1. se a faixa de 80% de (A) cobrir entre 70% e 90% no teste, **adota-se (A)**;
2. senão, se (B) cobrir entre 70% e 90% no **total** (57), adota-se (B), com o aviso de que não há teste limpo;
3. senão, adota-se (B) com o aviso "cobertura **abaixo**/**acima** da prometida", conforme o lado.

**Limite declarado:**
- com quantis por interpolação linear e ~40–57 erros, a cobertura esperada da faixa de "80%" é ~77–78%;
- o IC binomial não inclui o erro da própria estimativa da faixa.

## 4. O erro é igual para todas as unidades?

Mediana de |erro| por grupo:
- metragem oficial × satélite;
- terço do faturamento previsto;
- estado (SP / DF-GO / outros);
- com × sem estúdio.

"Treino × teste" é reportado à parte, como erro fora do tempo, e não serve de critério, porque uma unidade nova não tem
esse atributo.

**Faixa por grupo:** a regra se aplica **literalmente**. **Todos** os grupos da divisão precisam ter ≥ 10 unidades,
**e** a razão entre as medianas precisa ser ≥ 1,5. Se disparar, as faixas por grupo são reportadas e levadas à decisão
do Felipe; nesta versão, a §5 usa a faixa única.

## 5. Faixas de segurança dos indicadores

**Premissas:** simulador de produção com as premissas-padrão (impressas no resultado e conferidas contra o
`config.py`) e a rampa observada do UNI-03 (64% no mês 0, 100% no mês 11):
- ticket R$ 137;
- agregador a 60%;
- 69% de balcão;
- aluguel R$ 20 mil;
- obra R$ 2,34 mi;
- **custo do estúdio:** unidade com estúdio soma R$ 6 mil/mês de custo fixo (`SIM_CUSTO_STUDIO`, como na produção),
  supondo **1 estúdio**, porque o cadastro só diz se tem ou não.

**Cenários** (unidade típica = mediana das 57 previsões no nível de 2026, e cada unidade de teste):
- p10, **p50** e p90 da faixa adotada, aplicados à previsão;
- para as unidades de teste, a faixa é a sem a própria unidade;
- saídas: faturamento maduro, alunos, **margem EBITDA** e payback.

**Chance de ser viável** (margem ≥ 30% e payback ≤ 36 meses): fração dos erros do conjunto da faixa adotada, **sem o
da própria unidade**, que, aplicados à previsão, dão uma unidade viável.

**Conferência** (sem vazamento, só com os 39 erros do treino, nas 18 de teste): compara-se a chance com o que **seria
viável no simulador** com o faturamento real (custos-padrão).
- Brier contra o Brier da taxa-base p̄(1 − p̄);
- quantas "≥ 50%" seriam viáveis.

**Depois de abrir:** o UNI-03 mede outra coisa, o erro dos **alunos** maduros (meses 11–13) projetados do mês 3/6, e
não do faturamento anual. Reporta-se como referência, com as coberturas da confirmação (mês 3: 77%; mês 6: 64%, abaixo
do nominal), **sem** comparar diretamente com a faixa de antes de abrir.

## 6. Limites

- N = 57. O p10 e o p90 apoiam-se em ~4–6 unidades de cada lado.
- **Custos-padrão:** a chance de viabilidade é da praça com custo típico, não da unidade real.
- **Botafogo fica na base de erros** (regra 4 do epic). Ela só saiu do teste de fachada.
- **A v2 foi escolhida vendo o teste** (estúdios + master, pós-hoc). A cobertura no teste é um pouco otimista, e a
  conferência limpa é a turma de 2026 congelada.
- **Custo do estúdio:** a suposição de 1 estúdio pode subestimar o custo de unidades com mais de um.

## 7. Arquivos

`uni07/01_incerteza.py` → `resultado_uni07.md`, `erros_fora_da_amostra.csv`, `faixas_indicadores.csv`. Congelamento
(com o código reusado e o simulador de produção) em `REGISTRO_CONGELAMENTO.txt`.

## 8. Revisão antes de rodar (2026-09-30)

O que mudou:
- chance de viabilidade sem o próprio erro, e conferência só com os erros do treino;
- (B) declarada como não limpa;
- regra de adoção com (A) primeiro, fallback explícito e aviso pelo lado;
- p50 no lugar do ponto;
- margem reportada;
- regra de grupo literal, e treino × teste fora do critério;
- mês 3 como outra grandeza, com as coberturas;
- Brier contra a taxa-base e "seria viável no simulador";
- custo do estúdio;
- hashes do código reusado e do simulador;
- checagens de sanidade;
- unidade típica no nível de 2026.
