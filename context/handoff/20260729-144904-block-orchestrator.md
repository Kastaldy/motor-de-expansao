# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator (sonnet) — BLK-MA-03, 2026-07-29

## Próxima Skill recomendada
Planner (opus, override +1 conforme `tasks/current_task.md` — Passo 4)

## Bloco refinado

**BLK-MA-03 — Sinal 1 do score de vulnerabilidade (presença em agregador WellHub/TotalPass),
hex-level, reuso 100% de `fonte`/`rede`/`hex_id_res7` já materializados pelo BLK-MA-02.**

Segundo bloco de código de produção da epic BLK-MA. Não cria pipeline novo, não lê CSV cru, não
reclassifica nome — só agrega colunas que já existem no snapshot (`snapshots_concorrentes_v1`) para
produzir o insumo bruto do **sinal 1** (contrato §4), que o BLK-MA-04 vai normalizar/ponderar.

## Objetivo

Criar um módulo novo em `src/motor_expansao/vulnerabilidade/` que, a partir da série de snapshots já
materializada pelo BLK-MA-02, calcula por `hex_id_res7` quantos dos 2 agregadores (TotalPass/WellHub)
têm pelo menos uma academia **independente** observada — o insumo bruto do sinal 1 — sem calcular
`v1` normalizado nem tocar `score_vulnerabilidade` (isso é BLK-MA-04).

## Escopo permitido

- **Criar `src/motor_expansao/vulnerabilidade/presenca_agregador.py`**, com a função pública
  `extrair_presenca_agregador(base_dir: Path | None = None, *, snapshots: Sequence[pd.DataFrame] |
  None = None) -> pd.DataFrame` — mesma assinatura/molde de `extrair_churn_staleness`
  (`churn_staleness.py:251`): exatamente um entre `base_dir` (delega para `snapshots.ler_snapshots`,
  reuso — **não reimplementar** leitura de partição) e `snapshots` (injetado, função pura, sem I/O).
- **Universo do sinal 1 (fecha a decisão do Passo 3, item 1/4):** só entram linhas com
  `fonte in {"totalpass", "wellhub"}` **E** `rede == "independente"`. Ficam de fora, sempre: (a)
  `fonte == "unidades"` (cadeias, mesmo que por erro algum dia viessem com `rede == "independente"`);
  (b) linhas TP/WH cujo `rede` bateu com uma marca conhecida do classificador (ex.: uma unidade Smart
  Fit listada dentro do TotalPass) — fecha o falso positivo citado no Passo 3 item 4 ("cadeia grande
  ausente do WellHub não é independente frágil").
- **Redução "observação mais recente por chave" ANTES de agregar por hex** — nova primitiva pura
  (ex.: `_reduzir_para_observacao_mais_recente`), que, dentro de `(fonte, chave_snapshot)`, mantém só
  a linha de maior `snapshot_date`. Necessária porque o caller pode injetar/ler várias semanas
  retidas (até 26, `RETENCAO_SEMANAS`) — sem a redução, a mesma academia seria contada 1x por semana
  observada, inflando `n_academias_independentes_*`.
- **Agregação por `hex_id_res7`** (contagem de **chaves distintas**, não de linhas): `fontes_presentes`
  (string ASCII, subconjunto ordenado de `{"totalpass","wellhub"}` unido por vírgula),
  `n_agregadores_presentes` (`int64`, `len(fontes_presentes)` — estruturalmente **1 ou 2**, nunca 0,
  ver "Riscos identificados" R1), `n_academias_independentes_totalpass` e
  `n_academias_independentes_wellhub` (`int64`, contagem de chaves distintas por fonte no hex).
- **Novas constantes** (recomendo em `vulnerabilidade/contrato.py`, mesmo padrão de
  `FONTES_VALIDAS`/`CHAVE_ORIGEM_VALIDAS`): `VERSAO_CONTRATO_PRESENCA_AGREGADOR =
  "presenca_agregador_v1"`; `FONTES_AGREGADORES: frozenset[str] = frozenset({"totalpass",
  "wellhub"})`; `CATEGORIA_INDEPENDENTE = "independente"` — **replicada localmente, NÃO importada**
  de `demanda_revelada.classificacao_rede_menor` (ver R4/CA-9 abaixo — motivo: não piorar o
  vazamento transitivo de import já registrado como Item 2 do `BLK-MA-02-FU1`); e
  `CONTRATO_COLUNAS_PRESENCA_AGREGADOR: dict[str, str]` com as 6 colunas acima (nesta ordem):
  `hex_id_res7, fontes_presentes, n_agregadores_presentes, n_academias_independentes_totalpass,
  n_academias_independentes_wellhub, versao_contrato`.
- **`_assert_schema_presenca_agregador`** — mesmo padrão de `_assert_schema_churn`/
  `_assert_schema_snapshot`: falha para coluna extra/faltante/fora de ordem, `hex_id_res7` fora de
  res-7, `n_agregadores_presentes` fora de `{1,2}`, `fontes_presentes` inconsistente com a contagem
  observada, chave (`hex_id_res7`) duplicada. **Trava executável explícita** (molde
  `_COLUNAS_DE_SCORE_PROIBIDAS` de `churn_staleness.py:56-58`) que **rejeita** `v1`,
  `score_vulnerabilidade`, `n_sinais_disponiveis`, `flag_score_provisorio` se alguém "adiantar" o
  score aqui — normalização/pesos são do BLK-MA-04, não deste bloco.
- **Reexportar** a função pública + as novas constantes/contrato em `vulnerabilidade/__init__.py`.
- **Testes** em `tests/unit/vulnerabilidade/test_presenca_agregador.py`, 100% fixtures sintéticas
  (molde `test_churn_staleness.py`/`test_snapshots.py`), cobrindo pelo menos: exclusão de
  `fonte=="unidades"` mesmo com `rede` forjada; exclusão de TP/WH com `rede` de marca conhecida;
  redução por observação mais recente (chave que muda de hex entre 2 semanas — só a mais nova
  conta); `n_agregadores_presentes` nunca fora de `{1,2}`; rejeição de `v1`/`score_vulnerabilidade`
  injetados; extensão do teste de isolamento de import por AST (ver "Decisões a fechar pelo
  Planner" item 4).
- **Registrar o bloco BLK-MA-03 estruturado em `tasks/backlog.md`** (decisão E2, já fechada por
  Vinicius) — inserir **logo após a linha 1628** (fim do `BLK-MA-02-FU1`, antes de `###
  BLK-ATR-05` na linha 1631), no formato tabela usado pelo `BLK-MA-02-FU1` (`backlog.md:1567-1628`),
  com `**Autonomia** | manual (NÃO loop-safe)`.

## Fora de escopo

- **Universo NOMEADO (Opção B / D1-B)** — reter `nome_estabelecimento`/`slug` em `_ler_csv_tp_wh`
  (`concorrentes_densos.py:127`) — **DEFERIDO** pela decisão S1. Não tocar `concorrentes_densos.py`.
- **Sinal 2 (rating)** — permanece `n/d`, depende do BLK-MA-08 (ajuste de coletor).
- **`v1` normalizado** (0,0/0,5/1,0 do contrato §8.1), `score_vulnerabilidade`, pesos,
  `n_sinais_disponiveis`, `flag_score_provisorio`, qualquer normalização percentil — **BLK-MA-04**.
- **Cruzamento com hex quente**, `h3.grid_disk(k=1)`, join com carteira/mercado,
  `alvos_ma_priorizados.csv` — **BLK-MA-05**.
- **Os itens do `BLK-MA-02-FU1`** (`flag_troca_chave_na_serie`, vazamento transitivo de import,
  os 6 menores) — bloco **irmão** já registrado (`backlog.md:1567-1628`), com dono e critério de
  aceite próprios. Não misturar.
- Qualquer artefato M1: `score_priorizacao`, `hex_score_estrutural`, pesos `renda=0.40`/`pop=0.60`,
  carteira, plano curto prazo, plano de domínio, artefatos oficiais.
- `normalizar_concorrentes.py`, `calcular_colunas_mercado.py` (`_DENY_CRITICO`) — leitura como
  molde apenas, nunca importar/alterar.
- `snapshots.py`/`churn_staleness.py` do BLK-MA-02 — **ler como precedente, não editar** (os
  ajustes desses arquivos são do `BLK-MA-02-FU1`, bloco separado).
- `scripts/loop_guard.py` — **não precisa mudar**: `_DENY_GOVERNANCA` já cobre
  `^src/motor_expansao/(lifetime|demanda_revelada|vulnerabilidade)/` desde a D5 do BLK-MA-02
  (`loop_guard.py:176`, confirmado nesta investigação). Qualquer arquivo novo dentro de
  `vulnerabilidade/` já cai em `governanca` automaticamente.

## Arquivos que devem ser lidos

- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\CLAUDE.md` (completo; em especial §1,
  §2, §5, §6.1, §8)
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\docs\vulnerabilidade_ma_contrato.md`
  (§1 "Insumo real conferido", §3 D1, §4 tabela dos 6 sinais, §7 D3, §8 D4 — em especial §8.1/§8.2/
  §8.4, §11, §12, §13, §14)
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\src\motor_expansao\vulnerabilidade\contrato.py`
  (`CONTRATO_COLUNAS_SNAPSHOT:178-189`, `CONTRATO_COLUNAS_CHURN:193-211`, `FONTES_VALIDAS:63`,
  `H3_RES_CONTRATO:38`)
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\src\motor_expansao\vulnerabilidade\snapshots.py`
  (`ler_snapshots:575-600`, `_preparar_parte:132-150` — como `rede`/`fonte` já nascem no snapshot)
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\src\motor_expansao\vulnerabilidade\churn_staleness.py`
  (molde inteiro — em especial `_COLUNAS_DE_SCORE_PROIBIDAS:56-58`, `_assert_schema_churn:216-248`,
  `extrair_churn_staleness:251-295` como assinatura a espelhar)
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\src\motor_expansao\vulnerabilidade\__init__.py`
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\src\motor_expansao\demanda_revelada\classificacao_rede_menor.py`
  (`classificar_rede:241`, `CATEGORIA_INDEPENDENTE:58` — só para confirmar o valor a replicar, **não
  importar**)
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\tests\unit\vulnerabilidade\test_snapshots.py`
  (`test_isolamento_imports:167-190` — molde do teste AST a estender; `dirs_sinteticos:61-110` — molde
  de fixture)
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\tests\unit\vulnerabilidade\test_churn_staleness.py`
  (molde de teste do extrator, inclusive `test_assert_schema_churn_falha_se_alguem_adiantar_o_score` e
  `test_extrator_nao_produz_score`)
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\scripts\loop_guard.py` (linhas 152-190,
  `_DENY_GOVERNANCA` — confirma que `vulnerabilidade/` já está coberto)
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\tasks\backlog.md` (linhas 1547-1629 —
  onde inserir o BLK-MA-03 estruturado, e o molde de formato do `BLK-MA-02-FU1`)
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\context\handoff\20260729-121047-block-orchestrator.md`
  (achados A1-A11 herdados, não repetir investigação)
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\context\handoff\20260729-134525-qa.md`
  (ressalvas M1/M2/m1-m6 do MA-02 — não são deste bloco, mas o Item 2 [vazamento transitivo de
  import] condiciona a decisão de replicar `CATEGORIA_INDEPENDENTE` em vez de importar)
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\tasks\current_task.md` (decisões B1/S1/E2
  vinculantes, contexto herdado, tiering, branch)

## Arquivos que podem ser alterados

**Criar:**
- `src\motor_expansao\vulnerabilidade\presenca_agregador.py`
- `tests\unit\vulnerabilidade\test_presenca_agregador.py`

**Editar:**
- `src\motor_expansao\vulnerabilidade\contrato.py` (novas constantes +
  `CONTRATO_COLUNAS_PRESENCA_AGREGADOR`, ver "Escopo permitido")
- `src\motor_expansao\vulnerabilidade\__init__.py` (reexport)
- `tests\unit\vulnerabilidade\test_snapshots.py` (estender a tupla de módulos de
  `test_isolamento_imports` — ver "Decisões a fechar pelo Planner" item 4; se o Planner preferir
  duplicar o teste em `test_presenca_agregador.py`, justificar o desvio)
- `tasks\backlog.md` (E2 — bloco BLK-MA-03 estruturado; **é governança** → PR merge-humano)
- `tasks\completed.md` (fechamento, Passo 6, ao final do ciclo)
- `context\handoff.md` e `context\handoff\*` (snapshots append-only)

**NÃO alterar:** `config.py` · `pipelines/m1/` · `normalizar_concorrentes.py` ·
`calcular_colunas_mercado.py` · `concorrentes_densos.py` · `snapshots.py` · `churn_staleness.py`
(precedente MA-02, ajustes são do `BLK-MA-02-FU1`) · `scripts/loop_guard.py` (já cobre o pacote) ·
`.gitignore` · `pyproject.toml` · `graphify-out/*` · `PRD.md`.

## Critérios de aceite

1. **CA-1 — Universo do sinal 1 fechado corretamente.** `extrair_presenca_agregador` considera
   **somente** linhas com `fonte in {"totalpass","wellhub"}` **e** `rede == "independente"`. Teste
   dedicado com fixture que mistura (a) `fonte=="unidades"` com `rede` forjada como "independente",
   (b) TP/WH com `rede` de marca conhecida, (c) TP/WH genuinamente `rede=="independente"` — só (c)
   entra na contagem de qualquer hex.
2. **CA-2 — Unidade de análise = hex, contando chaves distintas.** `n_academias_independentes_*`
   conta `chave_snapshot` **distintas** por `(hex_id_res7, fonte)`, nunca linhas brutas.
3. **CA-3 — Redução para observação mais recente antes da agregação.** Com a mesma chave observada
   em 2+ semanas retidas, só a linha de `snapshot_date` mais recente entra na contagem. Teste com 3
   semanas onde a chave muda de `hex_id_res7` entre semanas (recolocação) prova que só a posição mais
   recente é contada — nunca as duas.
4. **CA-4 — Contrato de 6 colunas travado.** `CONTRATO_COLUNAS_PRESENCA_AGREGADOR` nesta ordem:
   `hex_id_res7, fontes_presentes, n_agregadores_presentes, n_academias_independentes_totalpass,
   n_academias_independentes_wellhub, versao_contrato`; `_assert_schema_presenca_agregador` falha
   para coluna extra/faltante/fora de ordem, `hex_id_res7` fora de res-7, `n_agregadores_presentes`
   fora de `{1,2}`, `fontes_presentes` inconsistente com a contagem, `hex_id_res7` duplicado.
5. **CA-5 — Trava executável contra score adiantado.** `_assert_schema_presenca_agregador` rejeita
   `v1`, `score_vulnerabilidade`, `n_sinais_disponiveis`, `flag_score_provisorio` se presentes —
   teste que injeta cada coluna e prova o `ValueError` (molde
   `test_assert_schema_churn_falha_se_alguem_adiantar_o_score`).
6. **CA-6 — Limite estrutural documentado, não bug.** Teste/assert comprova que
   `n_agregadores_presentes` nunca é `0` (o módulo só emite linha para hex com ≥1 observação); o
   docstring do módulo registra explicitamente que "0 agregadores" (`v1=1,0` do contrato §8.1) **não
   é alcançável** por este módulo isoladamente — decisão consciente de escopo, não lacuna a fechar
   aqui (ver "Riscos identificados" R1).
7. **CA-7 — Isolamento de import (AST).** O módulo novo entra na varredura de
   `test_isolamento_imports` (ou equivalente); nenhum import de `pipelines.m1`,
   `motor_expansao.dashboard`, `motor_expansao.api`, qualquer nome com `censo`,
   `motor_expansao.config`/`config`, `normalizar_concorrentes`.
8. **CA-8 — Zero PII / zero releitura de CSV cru.** O módulo só lê as colunas já materializadas
   pelo snapshot (`fonte, rede, hex_id_res7, chave_snapshot, snapshot_date`); nunca chama
   `ler_feeds`/`_ler_csv_bruto`; nunca reclassifica nome. Teste garante que a saída não tem coluna
   fora das 6 do contrato.
9. **CA-9 — Reuso, não reimplementação (`CATEGORIA_INDEPENDENTE` local).** O módulo **não** importa
   `classificar_rede`/`CATEGORIA_INDEPENDENTE` de `demanda_revelada.classificacao_rede_menor`; a
   constante `CATEGORIA_INDEPENDENTE = "independente"` é replicada localmente em
   `vulnerabilidade/contrato.py`, com comentário explicando o motivo (não piorar o vazamento
   transitivo de import — Item 2 do `BLK-MA-02-FU1`). Teste de isolamento (CA-7) cobre a ausência do
   import.
10. **CA-10 — Acentuação (§2).** Identificadores/colunas/enums/nomes de arquivo 100% ASCII (testável
    por varredura, molde `test_identificadores_do_contrato_sao_ascii`); prosa/docstrings acentuadas
    em português.
11. **CA-11 — Delegação de I/O, não reimplementação.** Quando `base_dir` é passado,
    `extrair_presenca_agregador` delega para `snapshots.ler_snapshots` (reuso); a função central de
    agregação é pura e testável só com `snapshots` injetado (mesma dualidade de
    `extrair_churn_staleness`).
12. **CA-12 — Suíte sem regressão.** Baseline medida nesta investigação: **2186 testes coletados**
    (`python -m pytest --collect-only -q`, 2026-07-29, bate com a re-verificação do QA do BLK-MA-02
    no mesmo commit). Após o bloco: `2186 + N` coletados, 0 falhas **novas** (a falha pré-existente
    `test_run_readonly_m1_por_mtime` de `BLK-FIX-LTV-01` continua sendo a única), `ruff` limpo.
13. **CA-13 — READ-ONLY M1 provado pelo diff.** O diff do ciclo não toca `config.py`,
    `pipelines/m1/`, `normalizar_concorrentes.py`, `calcular_colunas_mercado.py`, nenhum artefato
    oficial; `python scripts/loop_guard.py` não acusa `CRITICO` (só `governanca`, já esperado por
    tocar `vulnerabilidade/` e `tasks/backlog.md`).
14. **CA-14 — Backlog estruturado.** O bloco BLK-MA-03 entra em `tasks/backlog.md`, inserido
    imediatamente após a linha 1628 (fim do `BLK-MA-02-FU1`, antes de `### BLK-ATR-05`), no formato
    tabela do `BLK-MA-02-FU1`, com `**Autonomia** | manual (NÃO loop-safe)` — nunca `loop-safe`.

## Criticidade classificada

**MÉDIA** — confirmada de forma independente (concordo com o orquestrador).

- **NÃO é Crítica:** verifiquei e **declaro explicitamente** que o bloco não toca
  `score_priorizacao`, `hex_score_estrutural`, os pesos `renda=0.40`/`pop=0.60`, a carteira, o plano
  curto prazo, o plano de domínio nem qualquer artefato oficial do M1. `scripts/loop_guard.py` não
  precisa de nenhuma edição (o pacote já está em `_DENY_GOVERNANCA` desde a D5 do BLK-MA-02).
- **NÃO é Alta como o MA-02:** não cria pipeline de ingestão novo, não lê CSV cru, não persiste dado
  derivado de PII na origem pela primeira vez (isso já foi feito e testado pelo BLK-MA-02) e não apaga
  nada em disco. É agregação pura sobre um contrato de coluna já materializado e já coberto por
  fixtures sintéticas — "nova função, melhoria localizada" na tabela do Passo 2 do orquestrador.
- **Ressalva que NÃO eleva a criticidade, mas eleva o RISCO de retrabalho:** a decisão de unidade de
  análise (hex, não academia — R2 abaixo) é uma reinterpretação defensável, porém não-literal, do
  §8.1 do contrato. Não é um risco de M1/PII/infra (por isso não é Alta/Crítica), mas é a decisão de
  maior custo de erro do bloco — daí o override de tiering (+1 no Planner/Builder) já registrado em
  `tasks/current_task.md` seguir válido e recomendado.
- **Não é loop-safe.** `tasks/backlog.md` é governança (E2) → PR merge-humano de qualquer forma; não
  marcar `| **Autonomia** | loop-safe |` ao registrar o bloco.

## Esteira recomendada

Block Orchestrator (concluído) → **Planner (opus)** → **Builder (opus)** → **QA (opus)** → Passo 6
em modo **MERGE-HUMANO** (o PR toca `tasks/backlog.md` = governança; auto-merge de Média não se
aplica).

## Riscos identificados

- **R1 (ALTO, achado central da investigação) — "0 agregadores" (`v1=1,0` do §8.1) é
  estruturalmente inalcançável a partir deste módulo isolado.** TotalPass e WellHub são fontes
  **só-positivas**: uma linha na fonte diz "esta academia ESTÁ presente aqui", mas a ausência de uma
  linha nunca prova "esta academia NÃO está em lugar nenhum" — só prova "não observamos". Sem um
  registro externo e completo do universo de academias independentes do Brasil, o módulo não
  consegue distinguir "hex sem nenhuma academia independente real" de "hex com academias
  independentes que nenhum agregador cobre". É a MESMA classe de problema do item 4 do Passo 3
  (falso positivo de cadeia), generalizada: aqui não há UNIVERSO externo contra o qual checar
  ausência, então só "presença observada" é computável. Decisão registrada neste handoff: aceitar o
  limite no MVP (CA-6 documenta e testa o limite, não tenta contorná-lo); `v1=1,0` só se torna
  alcançável se/quando o BLK-MA-04/05 cruzar com uma fonte externa de universo (ex.:
  `oferta_academias_menores`/camada de mercado) — fora de escopo aqui, fica como decisão explícita a
  confirmar pelo Planner ou pelo BLK-MA-04.
- **R2 (ALTO, decisão semântica que reinterpreta o texto literal do §8.1) — unidade de análise =
  HEX, não academia.** O contrato descreve `v1` como contagem **por academia** (0/1/2 agregadores),
  o que pressupõe casar a MESMA academia entre TotalPass e WellHub. Isso exige identidade
  cross-provider (nome/slug retidos), que é exatamente a Opção B / D1-B, **DEFERIDA** pela decisão
  S1. Sem ela: (a) ao nível de listing (`chave_snapshot`), a chave já embute `fonte`
  (`chave_do_slug`/`chave_hash_estavel` em `contrato.py:395-413`), então uma mesma academia em TP e
  em WH gera **duas chaves diferentes**, nunca uma — "quantos agregadores cobrem ESTA linha" seria
  sempre `1`, um sinal sem variância, inútil para ranking; (b) a única granularidade onde "menos
  agregadores → mais vulnerável" carrega variância real com os dados disponíveis é o **hex**: um hex
  pode ter cobertura só-TotalPass, só-WellHub, ou ambos. Este handoff resolve a ambiguidade adotando
  hex como unidade — é o mesmo padrão de "métrica de hex propagada por `hex_id_res7`" já usado no
  contrato §9/D5 (hotness do hex broadcast para a lista de academias via join). **Concordo que é a
  leitura mais defensável dado o dado real, mas reconheço que é uma reinterpretação, não uma
  aplicação literal do §8.1** — o Planner (tier opus, +1) deve confirmar ou desafiar antes do
  Builder; se desafiar, a alternativa exigiria antecipar parte da Opção B/D1-B, o que reabriria S1.
- **R3 (MÉDIO) — Gap de feed não é distinguível de ausência real de cobertura, com dados de uma só
  fonte.** Se TotalPass não rodar por várias semanas, o módulo simplesmente não verá TotalPass
  naquele hex — indistinguível de "TotalPass genuinamente não cobre esse hex". A redução "mais
  recente por chave dentro da janela retida" (CA-3) mitiga parcialmente (usa o dado mais recente
  disponível de cada fonte, não descarta por causa da outra fonte), mas não resolve se **ambas**
  fontes ficarem sem rodar por mais que `RETENCAO_SEMANAS=26`. A flag de staleness formal
  (contrato §12: "marcados com flag de staleness quando desatualizados") é responsabilidade do
  BLK-MA-06; este bloco só precisa preservar `snapshot_date` no caminho de leitura (não descartar) —
  não precisa emitir a flag ele mesmo.
- **R4 (BAIXO) — reimportar `classificar_rede`/`CATEGORIA_INDEPENDENTE` repetiria o vazamento
  transitivo de import já registrado.** O Item 2 do `BLK-MA-02-FU1` documenta que importar de
  `demanda_revelada.classificacao_rede_menor` carrega `motor_expansao.dashboard.*` +
  `sklearn`/`scipy`/`shapely` (7,5s) por causa do `__init__.py` do `demanda_revelada`. Mitigado por
  CA-9 (replicar a constante localmente) — decisão de não piorar um débito que já tem dono e bloco
  próprio (`BLK-MA-02-FU1` Item 2, bloqueante para o BLK-MA-06).
- **R5 (BAIXO) — a cláusula "marca com contagem de unidades == 1" do D1 não é computável dentro do
  pacote `vulnerabilidade/` hoje.** O D1 define independente como "classificação `independente` do
  classificador **OU** marca com contagem de unidades == 1"; a segunda cláusula exigiria contar
  filiais por rede (lógica equivalente a `_colapsar_baixa_cardinalidade` de
  `classificacao_rede_menor.py:258-275`, que usa `N < 3`, não `N == 1`, e opera sobre outra fonte de
  dados — `oferta_academias_menores`). Este bloco usa só a primeira cláusula
  (`rede == "independente"`, já materializada). Registrar como simplificação consciente do MVP, não
  bloqueante.

## Guardrails ativos

- **READ-ONLY sobre o M1 (CLAUDE.md §1/§5; contrato §14).** Nada aqui recalcula ou altera
  `score_priorizacao`, `hex_score_estrutural`, os pesos `renda=0.40`/`pop=0.60`, a carteira, o plano
  curto prazo, o plano de domínio ou artefatos oficiais do M1. Imposto por `scripts/loop_guard.py` +
  `.github/workflows/guard.yml`.
- **Anti-PII (DEC-012 / contrato §11).** Só agregados por hex; o módulo não lê CSV cru nem
  coordenada/nome — só as 5 colunas já não-PII do snapshot (`fonte, rede, hex_id_res7,
  chave_snapshot, snapshot_date`); fixtures 100% sintéticas.
- **Acentuação (CLAUDE.md §2).** Prosa acentuada em texto de usuário/docstring; **nunca** acentuar
  identificadores, nomes de coluna, valores de enum ou nomes de arquivo.
- **CSV do projeto (CLAUDE.md §2).** Este bloco não cria I/O de CSV novo; staging (se algum
  artefato intermediário for materializado) só em Parquet.
- **Sem API externa ao vivo (CLAUDE.md §2 / contrato §2).** Nenhuma dependência nova.
- **DEC-013.** Extensão do lote de scrapers já existente, não pipeline novo — este bloco não altera
  coletor algum.
- **Toda mudança relevante entra com teste; nenhum PR sobe com CI quebrado (CLAUDE.md §2).**

## Decisões a fechar pelo Planner

1. **Confirmar ou desafiar a leitura HEX-level de "presença em agregador" (R2).** É a decisão
   semântica de maior impacto do bloco — reinterpreta o §8.1 literal (per-academia) para o único
   nível computável sem a Opção B/D1-B. Se o Planner desafiar, a alternativa reabre S1 (fora do
   escopo deste ciclo).
2. **Nome exato do módulo/função.** Proposto: `presenca_agregador.py` /
   `extrair_presenca_agregador`. Ajustar se o Planner preferir outro nome mais alinhado ao vocabulário
   do BLK-MA-04.
3. **Onde declarar `CATEGORIA_INDEPENDENTE`/`FONTES_AGREGADORES`.** Recomendo `contrato.py` (mesmo
   padrão de `FONTES_VALIDAS`/`CHAVE_ORIGEM_VALIDAS`) em vez de local ao módulo novo — mas é uma
   escolha de organização, não de substância.
4. **Se o teste de isolamento de import deve ser estendido em `test_snapshots.py`** (fonte única
   hoje, tupla `(pacote, c, m, mchurn)` em `test_isolamento_imports`) **ou duplicado** em
   `test_presenca_agregador.py`. Recomendo estender a tupla existente, para não fragmentar a prova em
   dois lugares que podem divergir.
5. **Se vale a pena expor, já neste bloco, um `n_academias_independentes_total`** (soma das duas
   colunas por fonte) como coluna redundante de conveniência, ou deixar o BLK-MA-04 somar — proposta
   deste handoff é NÃO expor (6 colunas, não 7), mas é decisão de conveniência, não de substância.
