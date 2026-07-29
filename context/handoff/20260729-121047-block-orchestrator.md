# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner (criticidade **Alta** → Planner obrigatório, e gate humano de engenharia antes do Builder)

## Bloco refinado

**BLK-MA-02 — Materializador de snapshots semanais + extrator de churn/staleness (funil de M&A, Plano B).**

Primeiro bloco com código de produção da epic BLK-MA (o BLK-MA-01 foi só-doc). Entrega o caminho ponta
a ponta dos sinais **S3 (churn)** e **S4 (staleness)** do `score_vulnerabilidade`, conforme
`docs/vulnerabilidade_ma_contrato.md` §6 (D2) e §13:

1. **Materializador** — lê os CSVs crus dos coletores (TotalPass/WellHub e cadeias), aplica a
   **limpeza de ruído** obrigatória, deriva a chave de snapshot e a impressão digital dos campos
   raspados, e grava a partição da semana em
   `data/staging/snapshots_concorrentes/semana=AAAA-SS/parte-*.parquet` (gitignored).
2. **Extrator** — lê a série de snapshots e deriva, por estabelecimento, `status_churn`,
   `semanas_sem_mudanca` e as flags de maturidade (`flag_serie_imatura`,
   `flag_staleness_interpretavel`).

O bloco **não** calcula `v3`/`v4` nem `score_vulnerabilidade` (isso é BLK-MA-04) e **não** toca em
nada do M1.

## Objetivo

Criar o pacote paralelo `src/motor_expansao/vulnerabilidade/` com o materializador de snapshots
semanais (com limpeza de ruído e chave auditável) e o extrator de churn/staleness com flags de série
imatura, 100% READ-ONLY sobre o M1 e anti-PII por construção, validado só por fixtures sintéticas.

## Escopo permitido

- **Criar o pacote `src/motor_expansao/vulnerabilidade/`** (novo, isolado), com quatro arquivos:
  - `__init__.py` — re-exporta a API pública.
  - `contrato.py` — constantes e contratos de coluna puros, **sem I/O** (molde:
    `src/motor_expansao/demanda_revelada/contrato.py`). Contém `MIN_SEMANAS = 8`,
    `STALE_SEMANAS = 12`, `RETENCAO_SEMANAS = 26`, `H3_RES_CONTRATO = 7`,
    `VERSAO_CONTRATO_SNAPSHOT`, `VERSAO_CONTRATO_CHURN`, o envelope geográfico do Brasil, o bbox por
    UF, as listas de padrões de ruído, `COLUNAS_PII_PROIBIDAS` e os dois dicts de schema.
  - `snapshots.py` — **materializador**.
  - `churn_staleness.py` — **extrator**.
- **Materializador (`snapshots.py`)**, com esta fronteira exata:
  - **Entrada:** caminhos de diretório como **parâmetros** (defaults iguais aos de
    `concorrentes_densos.py:57-59`: `concorrentes/totalpass/csvs`, `concorrentes/wellhub/csvs`,
    `concorrentes/Unidades`) + `snapshot_date: date | None`.
  - **Etapas puras e testáveis isoladamente:** `ler_feeds(...)` → `limpar_ruido(df)` →
    `derivar_chave(df)` → `calcular_hash_campos_raspados(df)` → `montar_snapshot(df)`.
  - **Saída:** `DataFrame` no contrato do snapshot; e, com `escrever=True`, a partição
    `semana=AAAA-SS/parte-*.parquet` sob `data/staging/snapshots_concorrentes/`.
  - `podar_snapshots(base_dir, retencao_semanas=RETENCAO_SEMANAS)` — remove partições `semana=` mais
    antigas que a retenção; **só é chamada pelo orquestrador de disco** (`executar()`), nunca por
    `materializar(escrever=False)`.
- **Extrator (`churn_staleness.py`)**, com esta fronteira exata:
  - **Entrada:** `base_dir` dos snapshots **ou** uma lista de `DataFrame` injetada (para teste sem
    I/O — molde `revalidar_huff_densa(..., df_join=...)` em `concorrentes_densos.py:427`).
  - **Saída:** `DataFrame` agregado por `chave_snapshot`, no contrato `churn_staleness_v1`.
  - **Não** calcula `v3`/`v4`, não normaliza por percentil, não pondera, não escreve
    `score_vulnerabilidade`.
- **Limpeza de ruído** (contrato §6, as 4 classes): coords `0;0` e fora do envelope do Brasil;
  rótulos de teste; entradas de tecnologia/onboarding do TotalPass; coords inconsistentes com a `uf`
  declarada. Deve devolver um **dicionário de contagens por `motivo_descarte`** (auditoria) e
  **nunca** persistir o texto ofensor.
- **Validação da estabilidade do `slug`** (§6, caveat do UUID) como função pura + rebaixamento
  automático de chave (ver "Critérios de aceite").
- **Testes** em `tests/unit/vulnerabilidade/` com fixtures 100% sintéticas em `tmp_path`.
- **Registrar o bloco BLK-MA-02 estruturado em `tasks/backlog.md`** (decisão E2 do orquestrador).

## Fora de escopo

- **Qualquer artefato, score, peso ou pipeline do M1.** Nada de `score_priorizacao`,
  `hex_score_estrutural`, `renda=0.40`/`pop=0.60`, `brasil_estrutural`, `brasil_priorizados`,
  `hexagonos_brasil_*`, carteira, plano curto prazo, plano de domínio.
- **`src/motor_expansao/pipelines/normalizar_concorrentes.py`** — está em `_DENY_CRITICO` do
  `loop_guard` (`scripts/loop_guard.py:83`, "score/insumo paralelo servido em producao"). Pode ser
  **lido como molde**, nunca alterado, e o pacote novo **não deve importá-lo**.
- `concorrentes_mapeados.parquet` e `_ler_csv_tp_wh` — o BLK-MA-02 **não** reimplementa nem altera a
  ingestão existente; ela continua servindo o Huff/residual. O materializador é um **caminho de
  leitura paralelo** sobre os mesmos CSVs.
- Sinal 1 (presença em agregador) e universo nomeado → **BLK-MA-03**.
- Sinal 2 (rating) → **BLK-MA-08** (ajuste de coletor).
- `score_vulnerabilidade`, normalização percentil, pesos, `n_sinais_disponiveis`,
  `flag_score_provisorio` → **BLK-MA-04**.
- Cruzamento com hex quente, `h3.grid_disk(k=1)`, join READ-ONLY na carteira, entregável comercial →
  **BLK-MA-05**.
- Plug no `run_weekly_90.sh` / VPS / cron / runbook → **BLK-MA-06**.
- Reputação externa (Google Places) → **BLK-MA-07**.
- Nenhuma alteração em `.gitignore` (já coberto — ver Achados) e nenhuma DEC nova (contrato §14:
  "sem DEC neste bloco").

## Arquivos que devem ser lidos

- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\CLAUDE.md` (§1, §2, §5, §6.1, §8)
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\docs\vulnerabilidade_ma_contrato.md`
  (§1 "Insumo real conferido", §3, §4, §6, §8.4, §11, §12, §13, §14)
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\src\motor_expansao\demanda_revelada\concorrentes_densos.py`
  (precedente canônico de ingestão anti-PII: `_ler_csv_tp_wh:127`, `_ler_csv_unidades:144`,
  `_COLUNAS_DROP_FRONTEIRA:73`, `_finalizar_schema:309`, `_assert_schema:326`, `materializar:353`)
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\src\motor_expansao\demanda_revelada\contrato.py`
  (molde de `contrato.py` puro + `COLUNAS_PII_PROIBIDAS`)
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\tests\unit\demanda_revelada\test_concorrentes_densos.py`
  (molde de fixture sintética `dirs_sinteticos:32-87` e do teste de isolamento de import por AST
  `test_isolamento_imports:210-227`)
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\src\motor_expansao\pipelines\m1\fase1_bi_exports.py`
  (`write_enriched_dashboard_partitioned:588-608` e `read_enriched_dashboard:611-619` — precedente de
  escrita/leitura hive `parte-{i}.parquet`)
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\src\motor_expansao\pipelines\materializar_setores_censitarios_geo.py`
  (`escrever_particoes:527-538`, `ler_particao_setores:541-556` — precedente alternativo, sem pyarrow)
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\src\motor_expansao\pipelines\normalizar_concorrentes.py`
  (**só leitura**: `_sha1_id:29`, `_coord_valida:33`, envelope `LAT_MIN..LNG_MAX:24-25`)
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\src\motor_expansao\demanda_revelada\classificacao_rede_menor.py`
  (`classificar_rede:241`, `CATEGORIA_INDEPENDENTE:58`)
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\docs\infra_producao.md` (linhas
  129-187 — o que o cron semanal realmente faz e o que está pendente)
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\scripts\loop_guard.py` (linhas 64-190)
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\.gitignore` (linhas 16-47)

## Arquivos que podem ser alterados

**Criar:**
- `src\motor_expansao\vulnerabilidade\__init__.py`
- `src\motor_expansao\vulnerabilidade\contrato.py`
- `src\motor_expansao\vulnerabilidade\snapshots.py`
- `src\motor_expansao\vulnerabilidade\churn_staleness.py`
- `tests\unit\vulnerabilidade\__init__.py`
- `tests\unit\vulnerabilidade\test_snapshots.py`
- `tests\unit\vulnerabilidade\test_churn_staleness.py`

**Editar:**
- `tasks\backlog.md` (E2 — bloco BLK-MA-02 estruturado; **é governança** → PR merge-humano)
- `tasks\completed.md` (fechamento, Passo 6)
- `context\handoff.md` e `context\handoff\*` (snapshots append-only)

**Condicional — só se o gate humano aprovar (ver "Decisões a fechar"):**
- `docs\vulnerabilidade_ma_contrato.md` (emendas ao §6: coluna `fonte`, `chave_origem`, gaps de
  cadência do feed, chave por hex)
- `scripts\loop_guard.py` + `tests\unit\test_loop_guard_paths.py` (1 linha: estender
  `_DENY_GOVERNANCA` para cobrir o pacote novo)

**NÃO alterar:** `.gitignore` · `config.py` · `pipelines/m1/` · `normalizar_concorrentes.py` ·
`concorrentes_densos.py` · `pyproject.toml` (hatchling já inclui subpacotes via
`packages = ["src/motor_expansao"]`, `pyproject.toml:148`) · `graphify-out/*` · `PRD.md`.

## Critérios de aceite

1. **CA-1 — Pacote novo e isolado.** `src/motor_expansao/vulnerabilidade/` existe e um teste de
   **isolamento de import por AST** (molde `test_concorrentes_densos.py:210-227`) prova que nenhum
   módulo do pacote importa `pipelines.m1`, `motor_expansao.dashboard`, `motor_expansao.api`,
   qualquer nome contendo `censo`, `motor_expansao.config`/`config`, nem
   `pipelines.normalizar_concorrentes`.
2. **CA-2 — Schema do snapshot travado.** O Parquet do snapshot tem **exatamente** estas 10 colunas
   (ASCII), em ordem, com dtypes coagidos, e um `_assert_schema` no molde de
   `concorrentes_densos.py:326` falha se sobrar/faltar coluna, se a chave tiver NaN/vazio, se algum
   `hex_id_res7` não for res-7, ou se houver chave duplicada dentro da mesma semana:
   `snapshot_date` (string ISO `AAAA-MM-DD`) · `slug` (string, nullable) · `concorrente_id` (string)
   · `chave_snapshot` (string) · `chave_origem` (string, `slug`|`concorrente_id`) · `hex_id_res7`
   (string) · `rede` (string) · `fonte` (string, `totalpass`|`wellhub`|`unidades`) ·
   `hash_campos_raspados` (string) · `versao_contrato` (string).
   *(`semana` é chave de partição hive, não coluna do arquivo — igual ao `uf` do enriquecido.)*
3. **CA-3 — Anti-PII por construção (D7/DEC-012).** Teste que grava o snapshot a partir de CSVs
   sintéticos com `nome`, `latitude`, `longitude`, `cidade`, `uf`, `cep`, `endereco_formatado`,
   `modalidades` e **relê o Parquet do disco**, assertando que **nenhuma** dessas colunas está
   presente e que nenhuma célula contém o nome sintético injetado.
4. **CA-4 — Partição correta e idempotente.** `materializar(..., escrever=True)` grava em
   `.../semana=AAAA-SS/parte-*.parquet`; rodar duas vezes a **mesma** semana não duplica linhas; a
   semana usa `date.isocalendar()` com **`iso_year`, não `date.year`** — teste de fronteira com
   `2026-12-28` (ISO `2026-53`) e `2027-01-01` (ISO **`2026-53`**, não `2027-01`), e com
   zero-padding (`2026-05`, nunca `2026-5`).
5. **CA-5 — Limpeza de ruído, com auditoria e sem PII.** `limpar_ruido` descarta e conta, por
   `motivo_descarte` (ASCII): `coord_zero_zero`, `coord_fora_envelope_brasil`,
   `coord_fora_bbox_uf`, `rotulo_de_teste`, `entrada_tecnologia_totalpass`. Teste com uma linha
   sintética de cada classe (inclusive "Teste Raised", "Zon Tecnologia", "SAGAZ Sistemas",
   "TSITECH Solucoes", "DATAFITNESS - TTP", "Batatao Jeans - Fornecedor X") + linhas boas que
   **não** podem ser descartadas. O retorno de auditoria contém **só contagens**, nunca o texto.
6. **CA-6 — `hash_campos_raspados` estável e sensível.** (a) `data_coleta` **não** entra no hash
   (teste: duas semanas idênticas exceto `data_coleta` → mesmo hash); (b) `modalidades`/`atividades`
   são normalizadas (trim + lower + tokens ordenados) antes de hashear (teste: mesma lista em ordem
   diferente → mesmo hash); (c) mudança real em qualquer campo do conjunto → hash diferente;
   (d) o conjunto de campos hasheados é **fixo por `fonte`** e documentado no `contrato.py`.
7. **CA-7 — Estabilidade do `slug` é comportamento testável, não relatório.**
   `avaliar_estabilidade_slug(snapshots)` devolve `taxa_slug_presente`,
   `taxa_slug_unico_no_snapshot`, `taxa_slug_persistente` (fração dos slugs da semana N-1 presentes
   em N, só sobre semanas consecutivas **observadas** da mesma `fonte`) e `taxa_slug_com_uuid`
   (regex de UUID). O materializador **rebaixa** a chave para `concorrente_id` (marcando
   `chave_origem="concorrente_id"`) quando o `slug` estiver ausente, **ou** não for único no
   snapshot, **ou** `taxa_slug_persistente < LIMIAR_SLUG_ESTAVEL`. Teste com 4 fixtures
   multi-semana: slug estável · slug com UUID que muda toda semana · slug duplicado na mesma semana
   · slug ausente (feed `unidades`) — cada uma produzindo o `chave_origem` esperado.
   **Limite explícito:** com série real inexistente (ver Achado A1), este CA valida o
   **comportamento**, não o veredito sobre dados reais — o veredito fica para BLK-MA-06+.
8. **CA-8 — Extrator: os 4 estados de churn.** Fixture sintética de ≥10 semanas cobrindo, com
   valores exatos assertados: `novo` · `estavel` · `piscando` (some e reaparece, com
   `n_desaparecimentos >= 1`) · `sumiu_recente` (ausente na última semana observada).
9. **CA-9 — Gap de feed não é churn.** Se uma `fonte` inteira não tem linhas em determinada semana,
   nenhuma chave dessa fonte pode receber `sumiu_recente` nem incrementar `n_desaparecimentos` por
   causa dessa semana. Teste dedicado — **este é o caso real** (o feed TP/WH é mensal e hoje nem
   roda; ver Achado A1).
10. **CA-10 — Staleness e maturidade.** `semanas_sem_mudanca` conta semanas **observadas** desde a
    última alteração de `hash_campos_raspados` e **reseta** quando o hash muda (teste com reset no
    meio da série). `flag_serie_imatura = (n_semanas_serie < MIN_SEMANAS)` e
    `flag_staleness_interpretavel = (n_semanas_serie >= STALE_SEMANAS)`; testes nos três regimes:
    série de 4 semanas (imatura=True, interpretável=False), de 9 (False/False), de 13 (False/True).
11. **CA-11 — Retenção.** `podar_snapshots` remove **apenas** diretórios `semana=` sob o `base_dir`
    dado, mais antigos que `RETENCAO_SEMANAS`, e nunca é chamada por `materializar(escrever=False)`.
    Teste em `tmp_path` com 30 semanas → sobram 26; teste de segurança: um diretório irmão fora do
    padrão `semana=` **não** é removido.
12. **CA-12 — Zero fonte real.** Nenhum teste lê `concorrentes/`, `data/staging/` real nem qualquer
    Parquet do repositório; tudo em `tmp_path`. Testes que dependeriam de dados reais usam
    `pytest.mark.skipif` no molde de `test_concorrentes_densos.py:117-120`.
13. **CA-13 — CSV do projeto.** Todo CSV sintético de fixture é escrito e lido com `sep=";"` e
    `encoding="utf-8-sig"` (§2). Staging só em Parquet.
14. **CA-14 — Acentuação (§2).** Docstrings/prosa em português acentuado; **todos** os
    identificadores, nomes de coluna, valores de enum (`estavel`, `piscando`, `sumiu_recente`,
    `novo`, `totalpass`, `wellhub`, `unidades`, `coord_zero_zero`, ...) e nomes de arquivo em ASCII.
15. **CA-15 — READ-ONLY sobre o M1, provado pelo diff.** O diff do ciclo não toca `config.py`,
    `pipelines/m1/`, `normalizar_concorrentes.py`, `calcular_colunas_mercado.py`, nenhum artefato
    oficial nem `concorrentes_mapeados.parquet`. `python scripts/loop_guard.py` não acusa `CRITICO`.
16. **CA-16 — Suíte sem regressão.** Baseline medida hoje: **2056 testes coletados**
    (`python -m pytest --collect-only -q`, 2026-07-29). Após o bloco: `2056 + N` coletados, `0`
    falhas, `ruff` limpo.

## Criticidade classificada

**ALTA** — confirmada de forma independente (concordo com o orquestrador).

- **NÃO é Crítica:** verifiquei e **declaro explicitamente** que o bloco **não toca**
  `score_priorizacao`, `hex_score_estrutural`, os pesos `renda=0.40`/`pop=0.60`, a carteira, o plano
  curto prazo, o plano de domínio nem qualquer artefato oficial do M1 — e sequer precisa ler
  `concorrentes_mapeados.parquet`. Nenhuma DEC nova é necessária (contrato §14). As decisões de
  produto D1–D8 já passaram por gate humano em 2026-07-23.
- **Não é Média:** cria um **pipeline de ingestão novo**, **persiste dados derivados de fonte real
  com PII na origem** sob requisito anti-PII (D7/DEC-012), **apaga arquivos em disco** (poda de
  retenção) e é o módulo que será plugado no cron de produção pelo BLK-MA-06.
- **Não é loop-safe.** Alta + toca `tasks/backlog.md` (governança) + ingestão com PII na origem.
  **Não** marcar `| **Autonomia** | loop-safe |` ao registrar o bloco no backlog.

## Esteira recomendada

Block Orchestrator (concluído) → **Planner (opus)** → **[gate humano de engenharia — Vinicius:
as 7 decisões escaladas abaixo]** → **Builder (opus)** → **QA (opus)** → Passo 6 em modo
**MERGE-HUMANO** (o PR toca `tasks/backlog.md` = governança; auto-merge não se aplica).

## Riscos identificados

- **R1 (ALTO) — O insumo não existe e não tem produtor agendado.** O feed onde vivem os
  independentes (TotalPass/WellHub) **não roda em cron nenhum hoje** e está listado como
  *Pendentes (futuro)* com cadência prevista **mensal** (`docs/infra_producao.md:186`; DEC-013 §7.3).
  O cron semanal atualiza **só** `Unidades/unidades_<rede>.csv` — cadeias, não independentes
  (`infra_producao.md:149`). Consequência: o extrator entregue por este bloco ficará em
  `flag_serie_imatura=True` **indefinidamente** até o BLK-MA-06 plugar o materializador no cron;
  e mesmo depois, `MIN_SEMANAS=8` só é atingido ~8 semanas após o plug (`STALE_SEMANAS=12`, ~3
  meses). **Não bloqueia este bloco** (fixtures sintéticas), mas invalida a expectativa do contrato
  §6 de que "o cron acumula snapshots desde ~26/06/2026".
- **R2 (ALTO) — Os CSVs crus são sobrescritos em cada coleta.** `infra_producao.md:149` deixa claro
  que a coleta *atualiza* os CSVs; o único histórico existente é `historico_contagem.csv`
  (contagens **por rede**, não por estabelecimento). Logo o snapshot **tem de ser tirado dentro da
  mesma execução do runner**, imediatamente após a coleta — se rodar depois, a semana é perdida para
  sempre. Restrição de design que o BLK-MA-06 herda e que o materializador precisa suportar
  (função pura + orquestrador de disco chamável por um passo de shell).
- **R3 (ALTO) — A chave `slug` só existe no feed que não roda; o feed que roda não tem `slug`.**
  `Unidades/unidades_<rede>.csv` emite apenas `nome_unidade`, `latitude`, `longitude`,
  `data_coleta`. Logo, na prática, o churn de curto prazo será **100% via fallback
  `concorrente_id`** — e o `concorrente_id` de hoje (`sha1(rede|nome|lat|lng)`,
  `normalizar_concorrentes.py:29`) **não é estável a jitter de lat/lng**: qualquer re-geocodificação
  vira **falso churn**, exatamente o sinal de maior peso (S3 ≈ 0,467). Mitigação proposta em D3 das
  decisões escaladas.
- **R4 (MÉDIO) — `hash_campos_raspados` mal definido mata o sinal 4.** Se `data_coleta` entrar no
  hash, `semanas_sem_mudanca` nunca passa de 0 e a staleness fica morta; se `modalidades` não for
  normalizada, reordenação vira mudança falsa. Coberto por CA-6.
- **R5 (MÉDIO) — Gap de feed lido como churn.** Com cadência mensal (ou falha de coleta), 3 em cada
  4 semanas não têm linhas TP/WH; um extrator ingênuo marcaria o universo inteiro como
  `sumiu_recente`. Coberto por CA-9; é o defeito mais provável do bloco.
- **R6 (MÉDIO) — Ambiguidade de diretório dos CSVs de cadeia.** Dois módulos apontam para lugares
  diferentes: `concorrentes_densos.py:59` usa `concorrentes/Unidades`, enquanto
  `normalizar_concorrentes.py:22` faz glob de `unidades_*.csv` na **raiz** de `concorrentes/`.
  Ambos estão ausentes localmente (a raiz só tem logos `.png`). Mitigação: **nunca hardcodar** —
  diretórios sempre como parâmetro, defaults iguais aos de `concorrentes_densos.py`.
- **R7 (MÉDIO) — `existing_data_behavior` do precedente pyarrow.**
  `write_enriched_dashboard_partitioned` usa `delete_matching`
  (`fase1_bi_exports.py:606`). Para escrita de **uma** semana por vez o comportamento é correto e
  idempotente; para uma escrita com o frame inteiro, apagaria partições. Escolher o precedente com
  consciência disso (CA-4).
- **R8 (BAIXO) — Guarda de governança contornada pelo pacote novo.** `_DENY_GOVERNANCA` cobre
  `^src/motor_expansao/(lifetime|demanda_revelada)/` com o motivo "camadas paralelas com insumo de
  PII na origem (DEC-012)" (`loop_guard.py:180`). Um pacote `vulnerabilidade/` — que tem exatamente
  esse perfil — escapa da rede. Ver decisão escalada D5.
- **R9 (BAIXO) — Custo do bbox por UF.** O critério "coords inconsistentes com `cidade`/`uf`" não
  tem insumo pronto no repo. Derivar da malha IBGE acoplaria a camada a um artefato pesado do M1.
  Ver decisão escalada D4.

## Guardrails ativos

- **READ-ONLY sobre o M1 (CLAUDE.md §1/§5; contrato §14).** Visualizações, análises e camadas
  paralelas não podem recalcular nem alterar `score_priorizacao`, `hex_score_estrutural`, os pesos
  `renda=0.40`/`pop=0.60`, a carteira, o plano curto prazo, o plano de domínio ou artefatos oficiais
  do M1 sem aprovação explícita. Imposto por `scripts/loop_guard.py` + `.github/workflows/guard.yml`.
- **Anti-PII (DEC-012 / contrato §11).** Só agregados; a geometria deriva do `hex_id`, nunca da
  coordenada GPS bruta; a fonte real nunca é versionada; testes só com fixtures sintéticas.
- **Acentuação (CLAUDE.md §2).** Prosa acentuada em texto de usuário; **nunca** acentuar
  identificadores, `key=`, valores brutos de enum, nomes de coluna ou slugs.
- **CSV do projeto (CLAUDE.md §2).** `sep=";"`, `encoding="utf-8-sig"`. Staging sempre em Parquet.
- **Sem API externa ao vivo (CLAUDE.md §2).** O Plano B não tem dependência externa; o dashboard
  segue offline sobre Parquets locais.
- **DEC-013.** A camada de M&A é **extensão** do lote de scrapers, não pipeline novo de coleta —
  este bloco não altera coletor algum.
- **Toda mudança relevante entra com teste; nenhum PR sobe com CI quebrado (CLAUDE.md §2).**

---

## Achados da investigação no código real (provados contra o repositório de hoje)

> O contrato foi escrito em 2026-07-23 e descreve **intenção**. O que segue foi verificado no
> repositório em 2026-07-29, com `arquivo:linha`.

**A1 — O produtor do insumo não existe, e a cadência prevista é mensal, não semanal.** *(muda o
plano)*
- `docs/infra_producao.md:186` — "**Pendentes (futuro):** cron **mensal** dos agregadores
  WellHub/TotalPass (~20h, invocação separada)". Confirmado por `docs/decisions/DEC-013.md:7`
  (item 3): "Cadência prevista: **mensal** (~20h), separada da semanal."
- `docs/infra_producao.md:149` — "A coleta atualiza só os CSVs `Unidades/unidades_<rede>.csv`".
- `docs/infra_producao.md:136-143` — o `run_weekly_90.sh` faz: pull/build → coleta dos 90 →
  relatório de crescimento (`contagem_atual.csv` / `contagem_anterior.csv` /
  `historico_contagem.csv`, **por rede**) → regen mercado/residual → restart. **Nenhum passo
  arquiva o feed por estabelecimento.**
- Consequências: (i) hoje há **zero** semanas de série por estabelecimento; (ii) os independentes
  vivem no feed **sem cron**; (iii) o snapshot precisa ser tirado **dentro** da execução do runner
  (R2); (iv) o extrator precisa ser robusto a **gaps** de semana (R5/CA-9).

**A2 — `data/staging/snapshots_concorrentes/` não existe e nada no repo o gera.** Confirmado: o
diretório está ausente e a string aparece **apenas** em `docs/vulnerabilidade_ma_contrato.md:153` e
`:375` e em `tasks/current_task.md` — nenhuma ocorrência em `.py`, `.sh` ou `.yml`.

**A3 — O `.gitignore` NÃO precisa ser estendido.** `.gitignore:19` já traz `data/staging/*`, que
cobre `data/staging/snapshots_concorrentes/`; somam-se `*.parquet` (`:26`) e `*.csv` (`:27`), e
`concorrentes/` (`:25`). A única exceção dentro de `data/staging` é
`!data/staging/simulador_estrutura.json` (`:43`). As negações versionam fixtures via
`!tests/fixtures/` e `!tests/fixtures/**` (`:46-47`). **Nenhuma alteração necessária.**

**A4 — Precedente de ingestão anti-PII (o molde que o bloco deve seguir).**
`src/motor_expansao/demanda_revelada/concorrentes_densos.py`:
- `_ler_csv_tp_wh:127-141` — lê `latitude`/`longitude`/`nome` com `sep=";"`, `encoding="utf-8-sig"`;
  classifica a rede pelo `nome` **só em memória** (`classificar_rede`, `:138`) e emite **apenas**
  `hex_id_res7` / `rede_normalizada` / `fonte` (`:139-141`). **`slug`, `cidade`, `uf`, `cep`,
  `endereco_formatado`, `modalidades`, `data_coleta`, `latitude`, `longitude` estão na lista de drop
  na fronteira** (`_COLUNAS_DROP_FRONTEIRA:73-86`). Confere com o contrato §3.
- `_ler_csv_unidades:144-161` — feed de cadeia: só `nome_unidade`/`latitude`/`longitude`/
  `data_coleta`; a rede vem do **nome do arquivo** (`unidades_<rede>.csv`).
- Padrão anti-PII praticado: geometria pelo **centroide do hex** (`_centroide_hex:112`, via
  `h3.cell_to_latlng`), nunca a coord bruta; contrato de colunas em dict
  (`CONTRATO_COLUNAS_CONCORRENTES_DENSOS:89`); `_assert_schema:326` falha em coluna fora do
  contrato, chave vazia, hex fora de res-7 ou chave duplicada; carimbo `versao_contrato`.

**A5 — Caminhos reais dos CSVs crus (todos gitignored e ausentes localmente).**
- `concorrentes/totalpass/csvs/unidades_totalpass_<uf>.csv` — schema TP: `slug;nome;latitude;
  longitude;cidade;uf;cep;endereco_formatado;modalidades;data_coleta`. (`unidades_totalpass_ac.csv`
  do contrato = Acre; casa com a fixture `tp / "unidades_totalpass_sp.csv"` em
  `test_concorrentes_densos.py:41`.)
- `concorrentes/wellhub/csvs/*.csv` — mesmo schema, com `atividades` no lugar de `modalidades`
  (`test_concorrentes_densos.py:70`).
- `concorrentes/Unidades/unidades_<rede>.csv` — `nome_unidade;latitude;longitude;data_coleta`.
- **Ambiguidade real (R6):** `normalizar_concorrentes.py:22` faz glob de `unidades_*.csv` na **raiz**
  de `concorrentes/`, não em `concorrentes/Unidades/`. Localmente, `concorrentes/` existe com 196
  entradas, mas **só logos `.png`**; as três subpastas de CSV **não existem**. Não há amostra
  versionada de CSV cru — `*.csv` é ignorado globalmente.

**A6 — Precedente de escrita de Parquet particionado (o Builder deve reusar, não inventar).**
- **Opção A (pyarrow, hive, `parte-{i}.parquet`)** — `write_enriched_dashboard_partitioned` em
  `src/motor_expansao/pipelines/m1/fase1_bi_exports.py:588-608`: `ds.write_dataset(...)` com
  `partitioning=ds.partitioning(pa.schema([("uf", pa.string())]), flavor="hive")`,
  `basename_template="parte-{i}.parquet"`, `existing_data_behavior="delete_matching"`. Leitura:
  `read_enriched_dashboard:611-619` (`ds.dataset(..., partitioning="hive")` + filtro). **É o
  precedente que casa com o `parte-*.parquet` do contrato §6.** Cuidado com `delete_matching` (R7);
  a coluna de partição precisa ser `str`, não `categorical` (`:596-598`).
- **Opção B (pandas puro, `part-000.parquet`)** — `escrever_particoes` em
  `src/motor_expansao/pipelines/materializar_setores_censitarios_geo.py:527-538`, com leitor
  `ler_particao_setores:541-556`. Mais simples, sem dependência de `pyarrow.dataset`.

**A7 — Precedente de fixtures sintéticas para camada com fonte real gitignored (DEC-012).**
- `tests/unit/demanda_revelada/test_concorrentes_densos.py:1-8` (docstring declara "Fixtures 100%
  SINTETICAS"), `_escrever_csv:27-29` (`sep=";"`, `utf-8-sig`), `dirs_sinteticos:32-87` (3 pastas em
  `tmp_path` com casos de dedup embutidos), `base_atual_fake:90-103` (Parquet fake em `tmp_path`),
  `test_isolamento_imports:210-227` (AST sobre os imports reais),
  `@pytest.mark.skipif(not m.DIR_TOTALPASS_DEFAULT.exists(), ...)`:117-120 (sanity que só roda local).
- `tests/fixtures/` versionado (`.gitignore:46-47`) contém `demanda_revelada_fake.html`,
  `oferta_academias_menores_fake.xlsx`, `rede_menor_fake.xlsx` — precedente de fixture sintética
  **versionada** quando o formato é caro de gerar. Para este bloco, `tmp_path` basta.

**A8 — O que já existe sobre concorrentes (e que o BLK-MA-02 NÃO reimplementa).**
- `src/motor_expansao/pipelines/normalizar_concorrentes.py` → `data/staging/concorrentes_mapeados.parquet`,
  com colunas `concorrente_id, rede, nome_unidade, lat, lng, data_coleta, arquivo_origem,
  flag_coord_valida, flag_duplicado_rede_coord, status_registro, hex_id_res7` (`:105-116`).
  `concorrente_id = sha1("rede|nome|lat:.6f|lng:.6f")` (`_sha1_id:28-31`) — **é o `concorrente_id`
  citado no contrato §6**. Envelope Brasil `LAT −34..6 / LNG −75..−28` (`:24-25`, `_coord_valida:33`).
  **Este arquivo está em `_DENY_CRITICO` do `loop_guard` (`loop_guard.py:83`) — não tocar.**
- `src/motor_expansao/pipelines/calcular_colunas_mercado.py` consome esse Parquet
  (`CONCORRENTES_PATH:28`) e produz as colunas de mercado/residual. Também `_DENY_CRITICO`
  (`loop_guard.py:77-80`). **Fora de escopo.**
- `classificar_rede` (`classificacao_rede_menor.py:241`) devolve a categoria da rede, com
  `independente` como bucket residual (`CATEGORIA_INDEPENDENTE:58`) e colapso anti-reidentificação
  de redes com `< 3` filiais (`:258-275`) — é o classificador que o BLK-MA-03 vai usar para o D1;
  o BLK-MA-02 só o chama para preencher a coluna `rede` do snapshot.

**A9 — Baseline de testes AGORA.** `python -m pytest --collect-only -q` →
**2056 testes coletados** em 185s (2026-07-29). O `CLAUDE.md` §5 cita `2006` — **histórico**, como o
próprio §5 avisa. Usar **2056** como linha de base deste ciclo.

**A10 — Packaging.** `pyproject.toml:1-3` usa hatchling e `pyproject.toml:148` declara
`packages = ["src/motor_expansao"]` → um subpacote novo é incluído automaticamente. **Nenhuma
alteração de packaging necessária.**

**A11 — Classificação do pacote novo no `loop_guard`.** `_DENY_GOVERNANCA` inclui
`^src/motor_expansao/(lifetime|demanda_revelada)/` — "camadas paralelas com insumo de PII na origem
(DEC-012)" (`loop_guard.py:179-182`), travado por `tests/unit/test_loop_guard_paths.py:149-150`. Um
pacote `vulnerabilidade/` **não** casa nenhuma regra → seria classificado `LIMPO`. Ver D5.
*(Irrelevante para o modo de merge deste ciclo: `tasks/backlog.md` já é GOVERNANÇA —
`loop_guard.py:174` — logo o PR é merge-humano de qualquer forma.)*

---

## Decisões fechadas pelo Block Orchestrator

**D-BO-1 — Caminho do módulo: `src/motor_expansao/vulnerabilidade/` (pacote novo).**
Justificativa ancorada no repo: (a) o próprio backlog pré-aprova o nome no "Escopo permitido" do
epic (`tasks/backlog.md:1530-1531`); (b) `demanda_revelada/` já tem 18 módulos e é o pacote da
DEC-012 sobre demanda revelada/Huff — o funil de M&A ali seria arquivamento errado; (c)
`src/motor_expansao/lifetime/` é o **precedente exato** de "camada paralela nova ganha pacote
próprio" (DEC-014, M2 READ-ONLY, 4 módulos); (d) a epic ainda terá score (MA-04), lista comercial
(MA-05) e integração de cron (MA-06) — precisa de casa própria; (e) hatchling inclui o subpacote
sem mexer no `pyproject.toml`.

**D-BO-2 — Fronteira materializador ↔ extrator: dois módulos no mesmo pacote, acoplados só pelo
Parquet.** `snapshots.py` (CSV cru → 1 partição de semana) e `churn_staleness.py` (série de
partições → estados de churn/staleness). O extrator **nunca** lê CSV; o materializador **nunca**
olha para semanas anteriores (exceto na função de validação de estabilidade do `slug` e na poda de
retenção, ambas explícitas). Entradas/saídas exatas na seção "Escopo permitido".

**D-BO-3 — O extrator para no `status_churn`/`semanas_sem_mudanca`.** Não produz `v3`/`v4`, não
normaliza, não pondera, não escreve `score_vulnerabilidade`. Isso é BLK-MA-04 (contrato §8.1/§13).

**D-BO-4 — Nenhuma alteração em `.gitignore`** (Achado A3).

**D-BO-5 — Criticidade ALTA confirmada, não-loop-safe** (ver seção "Criticidade classificada").

---

## Decisões a fechar pelo Planner ou pelo gate humano

**D1 — Coluna `fonte` e `chave_origem` no payload do snapshot (emenda ao contrato §6).**
O contrato fixa 6 campos: `{snapshot_date, slug, concorrente_id, hex_id_res7, rede,
hash_campos_raspados}`. **Recomendo +3**, com justificativa técnica:
- **`fonte`** — sem ela o extrator não distingue "o feed não rodou nesta semana" de "o
  estabelecimento sumiu" (R5/CA-9), e não sabe qual conjunto de campos entrou no hash (os feeds têm
  colunas diferentes — A5). **Considero necessária, não opcional.**
- **`chave_origem`** (`slug` | `concorrente_id`) — torna o rebaixamento de chave auditável; sem ela
  o churn é ininterpretável quando o feed alterna entre chaves.
- **`versao_contrato`** — precedente do repo (`concorrentes_densos.py:97`,
  `demanda_revelada/contrato.py:31`).
→ **Quem decide:** Planner propõe, gate humano ratifica a emenda em
`docs/vulnerabilidade_ma_contrato.md` §6.

**D2 — `semana` como partição derivada de `snapshot_date` (não fornecida pelo chamador).**
Recomendo derivar sempre de `date.isocalendar()` com `iso_year` (CA-4). Confirmar que
`data_coleta` chega em ISO `AAAA-MM-DD` — as fixtures do repo usam esse formato
(`test_concorrentes_densos.py:53`), mas **não há amostra real versionada para conferir**; o parser
deve ser defensivo e **falhar alto** (não silenciosamente) em formato inesperado.

**D3 — Definição do `concorrente_id` do snapshot (mitiga R3).** O `concorrente_id` de produção é
`sha1(rede|nome|lat:.6f|lng:.6f)` (`normalizar_concorrentes.py:29`) — **instável a jitter de
coordenada**, e ele será a chave efetiva na prática (o feed com cron não tem `slug`).
**Recomendo divergir**, definindo uma chave própria do snapshot,
`sha1(fonte|rede|nome_normalizado|hex_id_res7)`, que absorve jitter dentro do hex e é anti-PII por
construção — **sem tocar** `normalizar_concorrentes.py` (arquivo `_DENY_CRITICO`) e mantendo o
`concorrente_id` canônico também na linha, para rastreabilidade. **Trade-off honesto:** dois
estabelecimentos da mesma rede com nomes normalizados iguais no mesmo hex colidiriam. Decisão de
engenharia com impacto direto no sinal de maior peso (S3 ≈ 0,467) → **gate humano**.

**D4 — Fonte do critério "coords inconsistentes com `cidade`/`uf`" (R9).** Não há insumo pronto.
Opções: (a) **bbox por UF versionado no `contrato.py`** (27 retângulos, dado público, chaves ASCII,
tolerância ~0,5°) — barato, sem acoplamento; (b) derivar da malha IBGE — caro e acopla a camada
paralela a um artefato pesado do M1. **Recomendo (a).** Nota: a coluna `uf` **só existe no feed
TP/WH**; no feed `unidades` a regra se reduz ao envelope do Brasil.

**D5 — Estender `_DENY_GOVERNANCA` do `loop_guard` para cobrir o pacote novo (R8/A11).**
O regex `^src/motor_expansao/(lifetime|demanda_revelada)/` existe justamente para "camadas paralelas
com insumo de PII na origem (DEC-012)" — perfil idêntico ao de `vulnerabilidade/`. **Recomendo
estender para `(lifetime|demanda_revelada|vulnerabilidade)`** (1 linha em `loop_guard.py:180` + 1
caso em `tests/unit/test_loop_guard_paths.py`). É **alargamento** de guarda, nunca afrouxamento, e o
PR já é merge-humano. **Contra-argumento legítimo:** é escopo adjacente ao bloco. → **Gate humano
decide.**

**D6 — Registrar no contrato o desalinhamento de cadência (A1/R1).** O §6 afirma que "o cron acumula
snapshots desde ~26/06/2026", o que é falso: nada acumula por estabelecimento, e o feed dos
independentes é **mensal e pendente**. Recomendo uma emenda curta ao §6/§12 e a antecipação de uma
decisão de produto para o BLK-MA-06: **plugar o materializador no runner semanal para o feed
`unidades` já agora** (série começa a acumular) **versus esperar** o cron mensal dos agregadores.
Isso muda em ~2 a 3 meses a data em que BLK-MA-04/05 deixam de sair `flag_score_provisorio`. →
**Decisão de produto, gate humano.**

**D7 — `LIMIAR_SLUG_ESTAVEL`.** Sugiro `0.90` para `taxa_slug_persistente` como default do
rebaixamento automático de chave (CA-7). Sem série real, é um número **arbitrado**, não medido —
registrar como tal no `contrato.py` e revisitar no BLK-MA-06.
