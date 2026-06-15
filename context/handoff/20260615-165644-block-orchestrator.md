# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco
BLK-DIM-02R — Huff com validação real (OSM, saturação, sem vazamento)

## Decisão do BO
**EXECUTAR** — BLK-DIM-02R prossegue para o Planner.

## Justificativa da decisão

O BLK-DIM-08 concluiu com **NO-GO honesto** (AUC residual = 0.4801, IC95 [0.4233, 0.5354],
cruza 0.5, abaixo do baseline pop×renda = 0.5318). O gate de sequência está satisfeito
(BLK-DIM-08 em completed.md). A questão é: o NO-GO do DIM-08 invalida o BLK-DIM-02R?

**Não.** Os dois blocos testam hipóteses DISTINTAS:

- **DIM-08** testou se o *score residual já existente* (`score_oportunidade_residual`, camada
  paralela de mercado) discrimina viável vs. inviável melhor que o acaso — e falhou (AUC ≈ 0.5).
  O residual é calculado hoje como `pop_captação − consumo_concorrencial_proxy`, onde o
  "consumo concorrencial" é um proxy grosseiro (capacidade-padrão × n_concorrentes sem peso
  por distância).

- **DIM-02R** testa se um modelo **gravitacional de Huff com distância real** produz um share
  de captura com β distinguível de zero — substituindo o proxy grosseiro por uma estimativa
  geométrica calibrada. Não é o mesmo que o residual existente: é uma melhoria no COMPONENTE
  de consumo concorrencial do residual, com validação honesta.

**Por que faz sentido executar mesmo com DIM-08 NO-GO:**

1. **O NO-GO do DIM-08 ≠ "captura gravitacional não funciona."** Ele mostrou que o residual
   *com o proxy atual* não discrimina. O Huff tenta endereçar exatamente o componente mais
   frágil desse proxy (consumo concorrencial sem decaimento por distância).

2. **O DIM-08 mostrou 33.8% de variância por região** — há estrutura real nos dados. O Huff
   modela a distribuição de share *dentro* de um mercado local (dado o potencial regional), não
   o potencial absoluto. Isso é ortogonal ao NO-GO de predição absoluta do DIM-01R.

3. **O BLK-DIM-01R (pop+renda → alunos absolutos) deu NO-GO**, e o DIM-02R já foi projetado
   com essa informação: o objetivo é validar se β gravitacional é distinguível de zero (ranking/
   share), **não prever alunos absolutos**. A hipótese é mais fraca e mais honesta.

4. **O resultado pode ser outro NO-GO** — e isso seria igualmente válido. Se β não for
   distinguível de zero, o relatório documenta que a distância para concorrentes não explica
   share de captura com os dados disponíveis, informando a decisão de produto sobre BLK-DIM-DATA
   (se vale buscar dado externo de demanda).

5. **Critério do gate:** "O DIM-08 é quem informa se vale perseguir captura." O DIM-08
   informou: o residual com proxy grosseiro não funciona. Perseguir uma modelagem de captura
   *com modelo geométrico real* (Huff) é a resposta natural — não uma repetição do fracasso.

**Guardrails verificados (NENHUM ativado):**
- M1 READ-ONLY: sim (BLK-DIM-02R não toca config.py raiz/pipelines/m1/artefatos oficiais).
- VPS/deploy/segredos: NÃO — loop-safe, container isolado.
- PII: NÃO — módulo huff.py segue o padrão `assert_sem_pii` do DIM-07/08.
- Ingestão ao vivo: NÃO — consome `concorrentes_mapeados.parquet` e `base_calibracao_multirede.parquet` locais.

**Nota de escopo para o Planner:**
- `huff.py` NÃO existe no repo atual (o spike estava em branch não-mergeada, superseded).
  O Builder cria do zero.
- O vazamento a corrigir: o spike usava `pot = np.where(isnan(pot), y, pot)` — alvo como
  fallback do previsor. Proibido.
- Validação obrigatória: LOO sem vazamento; β com IC; reportar "indistinguível" se p ≥ 0.05.
- Base disponível: `data/staging/base_calibracao_multirede.parquet` (426 un., 275 com coord,
  BLK-DIM-07); concorrência OSM: `data/staging/concorrentes_mapeados.parquet` (3.296 un.).
- Módulos reutilizáveis: `catchment_batch.py` (raio variável), `base_multirede.py` (loaders),
  `growth_api_client.py` (assert_sem_pii), `residual_discriminacao.py` (padrão de validação).
- Metodologia não-negociável (DEC-008): LOO-CV vs baseline da média; BANIR R² in-sample;
  começar simples (linear log-log ou isotônica); IC bootstrap em β; flag de extrapolação.
- Saída esperada: `src/motor_expansao/dimensionamento/huff.py` + testes offline +
  `data/analysis/huff_calibracao.md` (gitignored) com veredito GO/NO-GO de β.

## Tiering de modelo
- Block Orchestrator: sonnet (este handoff)
- Planner: opus
- Builder: opus
- QA: opus 4.8 (sempre)

## Estado do repositório
- Branch: ciclo/loop-20260615-124342
- Suíte ao fechar DIM-08: 902 passed, 4 skipped
- Arquivos novos do DIM-08: `residual_discriminacao.py`, `test_residual_discriminacao.py` (commitados em `62998d2`)
- Paths pré-sujos (EOL/CRLF, NÃO commitar): PRD.md, CLAUDE.md, README.md, .env.example,
  .github/workflows/ci.yml e outros arquivos do worktree rastreados com divergência de EOL.
  O commit do BLK-DIM-02R deve ser **por path** (só os arquivos novos/modificados do bloco).
