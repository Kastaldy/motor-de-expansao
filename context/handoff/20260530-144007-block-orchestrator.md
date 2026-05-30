# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
BLK-FIX-01 — Corrigir clipping/validação de `score_expansao_hibrido`.

O validador read-only de schema do dashboard (`schemas.py`, criado no BLK-OPS-04, já
em main) rejeita o campo `score_expansao_hibrido` porque o cálculo híbrido pode produzir
valores ligeiramente acima de 100 (~100.001), estourando a checagem de faixa estrita
`[0,100]`. Isso bloqueia o dashboard de carregar Parquets reais e impede o BLK-OPS-04 de
ir a produção no VPS.

Fatos técnicos confirmados na investigação:
- `src/motor_expansao/pipelines/modelo_hibrido_expansao.py:115` `calcular_score_expansao_hibrido`
  retorna `score_priorizacao + (score_setor_2022_calibrado / LOCAL_BONUS_DIVISOR)`, SEM clip.
  `LOCAL_BONUS_DIVISOR = 100_000.0` (linha 55) ⇒ bônus ≤ ~0.001 ⇒ híbrido ≤ ~100.001 quando
  `score_priorizacao` ≈ 100.
- `src/motor_expansao/dashboard/schemas.py:89` valida `numeric[mask].between(0, 100).all()`
  — faixa estrita, SEM tolerância. `_SCORE_RANGE_OPTIONAL` (linhas 12-17) inclui
  `score_expansao_hibrido`. Daí a rejeição.

TENSÃO DE DESIGN: o docstring do módulo (linhas 8-14) define `score_expansao_hibrido` como
CHAVE DE ORDENAÇÃO LEXICOGRÁFICA — M1 (`score_priorizacao`) é o critério primário e o bônus
censitário (≤0.001) atua apenas como micro-desempate local entre hexes dentro do município
aprovado. Ou seja, ele NÃO é, por desenho, um score limitado a [0,100]; o "estouro" é
intencional e carrega informação (o desempate). Clipá-lo a 100 ZERA o desempate justamente
nos hexes de maior prioridade (`score_priorizacao` ≈ 100), quebrando a razão de existir do
campo.

DISTINÇÃO IMPORTANTE (confirmada): `score_dominio_hibrido` (Bloco 17) é OUTRO score, já
calculado com `clip(0.60*censo + 0.40*residual, 0, 100)` em `dashboard/data.py:1043-1047`.
NÃO confundir com `score_expansao_hibrido`. O BLK-FIX-01 não toca `score_dominio_hibrido`.

## Objetivo
Permitir que o dashboard valide e carregue os Parquets reais (desbloqueando o deploy do
BLK-OPS-04) sem quebrar o desenho lexicográfico de `score_expansao_hibrido` nem mutar
qualquer score/artefato M1 oficial.

## Escopo permitido
- Investigar e propor a correção em `src/motor_expansao/dashboard/schemas.py` (validador
  read-only) e/ou em `src/motor_expansao/pipelines/modelo_hibrido_expansao.py` (fórmula
  híbrida), conforme a alternativa escolhida pelo Planner.
- Testes em `tests/unit/test_schema_validation.py` e, se a fórmula for tocada, teste de
  unidade do cálculo híbrido.
- SE (e somente se) a fórmula for alterada: regenerar APENAS os Parquets DERIVADOS afetados
  (ver seção "Escopo de regeneração"), com staging antes de sobrescrever produção.
- Housekeeping de tasks/handoff.

## Espaço de solução (alternativas para o Planner; NÃO decidido aqui)
- (i) **Clipar a fórmula** `score_expansao_hibrido` a [0,100] em
  `modelo_hibrido_expansao.py`.
  - Prós: alinha valor ao nome "score [0,100]"; passa no validador estrito sem tolerância.
  - Contras: ZERA o micro-desempate (bônus ≤0.001) nos hexes com `score_priorizacao` ≈ 100,
    quebrando a ordenação lexicográfica — propósito central do campo. Exige REGENERAR
    Parquets derivados.
  - Criticidade: ALTERA fórmula de score ⇒ **Crítica + DEC** pela nova regra §2.
- (ii) **Tolerância 1e-2 no validador** (`schemas.py`): trocar `between(0,100)` por uma
  checagem com folga (ex.: `-tol ≤ v ≤ 100+tol`, tol=1e-2) só para esse campo (ou para os
  scores que podem ter bônus aditivo).
  - Prós: NÃO toca a fórmula, NÃO regenera Parquet, preserva integralmente o desempate;
    100.001 ≤ 100.01 passa.
  - Contras: tolerância "mágica" que mascara que o score legitimamente excede 100; pode
    deixar passar futuros valores de até 100.01 por outras causas.
  - Criticidade: só validador read-only, sem tocar score/artefato ⇒ **Alta**.
- (iii) **Remover `score_expansao_hibrido` da checagem [0,100]** (tirá-lo de
  `_SCORE_RANGE_OPTIONAL`) e validá-lo só como numérico/conversível (chave de ordenação
  não-limitada), honrando o design.
  - Prós: honra o contrato (não é score [0,100]); NÃO toca fórmula, NÃO regenera Parquet;
    sem tolerância "mágica".
  - Contras: reduz a cobertura de validação de faixa desse campo específico (continua sendo
    validado como numérico/não-nulo, mas não quanto a faixa).
  - Criticidade: só validador read-only ⇒ **Alta**.
- Combinações são possíveis (ex.: (iii) + asserção explícita de teto técnico ~100.001 num
  teste). O Planner decide e justifica; o humano aprova.

## Fora de escopo
- Alterar `score_priorizacao`, `hex_score_estrutural`, pesos M1 ou os 4 artefatos M1 oficiais.
- Tocar `score_dominio_hibrido` (Bloco 17, score distinto, já clipado).
- BLK-FIX-02 (MessageSizeError) — bloco separado.
- Qualquer mudança em `LOCAL_BONUS_DIVISOR` ou na semântica do desempate sem aprovação.
- Commitar `CLAUDE.md` (edição não relacionada deste worktree).

## Arquivos que devem ser lidos
- `src/motor_expansao/pipelines/modelo_hibrido_expansao.py` (docstring linhas 1-20; linhas 48-126)
- `src/motor_expansao/dashboard/schemas.py` (linhas 8-95)
- `src/motor_expansao/dashboard/data.py` (linhas 1027-1047 — `score_dominio_hibrido`, p/ não confundir)
- `tests/unit/test_schema_validation.py`
- `CLAUDE.md` §2 (nova regra de criticidade), §3 (score oficial), §4 (camadas híbridas), §5 (guardrail permanente)
- `tasks/backlog.md` (BLK-FIX-01)

## Arquivos que podem ser alterados
- `src/motor_expansao/dashboard/schemas.py` (alternativas ii/iii)
- `src/motor_expansao/pipelines/modelo_hibrido_expansao.py` (somente alternativa i — Crítica+DEC)
- `tests/unit/test_schema_validation.py` · (eventual) teste do cálculo híbrido
- `tasks/current_task.md` · `tasks/backlog.md` · `tasks/completed.md`
- `context/handoff.md` · `context/handoff/`
- (Parquets em `data/outputs/` são gerados, não versionados — não commitar.)

## Escopo de regeneração de Parquets (scope c/d do backlog)
SE a fórmula mudar (alternativa i), os Parquets DERIVADOS que carregam `score_expansao_hibrido`
precisariam ser regenerados:
- `data/outputs/oportunidades_expansao_hibrido.parquet`
- `data/outputs/monitoramento_expansao_hibrido_base.parquet`
- `data/outputs/hexagonos_dashboard_enriquecido/uf=XX/parte-*.parquet` (enriquecido particionado)
- a jusante: `carteira_expansao_acionavel`/`plano_expansao_curto_prazo` e penetração, se
  derivarem do híbrido (verificar antes de regenerar).
GUARDRAIL: os 4 artefatos M1 oficiais — `brasil_priorizados.parquet`,
`brasil_estrutural.parquet`, `hexagonos_brasil_oportunidades.parquet`,
`hexagonos_brasil_dashboard.parquet` — NÃO contêm `score_expansao_hibrido` e NÃO podem ser
mutados. Staging em Parquet antes de sobrescrever produção. Nas alternativas (ii) e (iii)
NENHUM Parquet é regenerado.

## Critérios de aceite
- O dashboard valida e carrega os Parquets reais com `score_expansao_hibrido` presente sem
  `SchemaValidationError` (desbloqueia BLK-OPS-04).
- O micro-desempate lexicográfico de `score_expansao_hibrido` é PRESERVADO (hexes com
  `score_priorizacao` ≈ 100 mantêm ordenação distinta pelo bônus censitário) — salvo decisão
  explícita e aprovada de clipar.
- `score_priorizacao`, `hex_score_estrutural`, pesos M1 e os 4 artefatos M1 oficiais
  INALTERADOS (verificável por diff/hash).
- `score_dominio_hibrido` intocado.
- Teste cobrindo o caso de borda (~100.001) verde; suíte `pytest -q` sem regressão
  (baseline 532 passed / 1 skipped).
- Se a fórmula NÃO for tocada (ii/iii): nenhum Parquet regenerado.

## Criticidade classificada
**Alta no caso plausível recomendado; Crítica+DEC se o Planner optar por alterar a fórmula.**

Justificativa (aplicando a regra §2 de 2026-05-30):
- `score_expansao_hibrido` é score HÍBRIDO/operacional de CAMADA PARALELA, não o score M1
  oficial (`score_priorizacao`/`hex_score_estrutural`). Os Parquets candidatos a regeneração
  são DERIVADOS (enriquecido/monitoramento), não os 4 artefatos M1 oficiais. O backlog
  classifica Alta.
- A regra §2 distingue por AÇÃO:
  - Alternativas (ii) tolerância e (iii) exclusão da checagem só mexem no VALIDADOR read-only,
    sem escrita em artefato M1 e sem alterar fórmula/pesos ⇒ **Alta** (revisão humana antes
    do Builder). **DEC NÃO obrigatório.**
  - Alternativa (i) clip ALTERA a FÓRMULA de um score (ainda que híbrido) e exige regenerar
    Parquets derivados. Aplicando a regra ao pior caso plausível, "ALTERAÇÃO de fórmula"
    ⇒ **Crítica + DEC obrigatório** (registrar decisão de design da quebra do desempate).
- Recomendação pelo pior caso plausível: o Planner deve apresentar as 3 alternativas; se
  propuser (i) → **Crítica + DEC**; se propuser (ii) ou (iii) → **Alta**. Em AMBOS os casos há
  **gate humano obrigatório após o Planner** antes do Builder.

## Esteira recomendada
Block Orchestrator → Planner → [APROVAÇÃO HUMANA] → Builder → QA

## Riscos identificados
- **Quebra silenciosa do desempate** se a fórmula for clipada: hexes de topo perdem ordenação
  fina; impacto downstream em carteira/plano/penetração que consomem o híbrido.
- **Tolerância "mágica" (ii)** pode mascarar regressões futuras que empurrem o score acima de
  100 por outras causas, não só o bônus ≤0.001.
- **Redução de cobertura (iii)**: campo deixa de ter checagem de faixa (mantém numérico/não-nulo).
- **Regeneração de Parquets (i)**: risco de sobrescrever produção sem staging, ou de regenerar
  artefato a jusante que não precisava — exige inventário antes de rodar.
- Confundir `score_expansao_hibrido` com `score_dominio_hibrido` (mitigado: distinção
  documentada acima).

## Guardrails ativos
- §5 (guardrail permanente): visualizações, análise radial e interações de mapa NÃO podem
  recalcular ou alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto
  prazo, plano domínio ou artefatos oficiais do M1 sem aprovação explícita.
- §2 (nova regra 2026-05-30): LEITURA/ANÁLISE de score sem escrita em artefato M1 → Alta
  (revisão humana antes do Builder); ALTERAÇÃO de fórmula, pesos ou qualquer artefato M1 →
  Crítica (aprovação obrigatória + DEC).
- §2: ao tocar camadas paralelas, preservar 100% das linhas e colunas oficiais do M1; toda
  mudança relevante entra com teste; nenhum PR sobe com CI quebrado; staging sempre em Parquet.
- §3 (parâmetros canônicos): `M1_SCORE_OFICIAL = "score_priorizacao"`;
  `score_priorizacao = clip(hex_score_estrutural + ajuste_executivo, 0, 100)`; pesos M1
  `renda=0.40`, `pop=0.60` — INALTERÁVEIS neste bloco.
- Commit por path; NUNCA `git add -A`; `CLAUDE.md` NÃO entra no commit deste ciclo.
- Gate humano obrigatório após o Planner (Alta e Crítica). Builder só após "aprovar" explícito.
