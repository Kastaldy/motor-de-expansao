# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator (opus, +1 sobre a tabela de Alta) — BLK-MA-04, 2026-07-30

## Próxima Skill recomendada
**Planner** — e, depois dele, **`[GATE HUMANO OBRIGATÓRIO]`** antes do Builder (criticidade Alta,
decisão C1 do ciclo). Há **5 decisões de produto** que o Planner não pode fechar sozinho (seção
"Decisões que sobem ao gate").

## Bloco refinado

**BLK-MA-04 — Score de vulnerabilidade (D4): composição ponderada de S1/S3/S4, renormalização por
sinal ausente/imaturo e flags de qualidade.**

Materializa em código a heurística do §8 do `docs/vulnerabilidade_ma_contrato.md`, consumindo os
DOIS insumos já entregues e fechados:

- **S1** — `presenca_agregador_v1` (BLK-MA-03), **uma linha por `hex_id_res7`**, 10 colunas
  (`presenca_agregador.py:268-322`; contrato em `contrato.py:237-248`).
- **S3/S4** — `churn_staleness_v1` (BLK-MA-02), **uma linha por `(fonte, chave_snapshot)`**, 17
  colunas (`churn_staleness.py:251-295`; contrato em `contrato.py:207-225`).

O bloco produz um **módulo novo e PURO** no mesmo pacote, sem I/O, sem tocar os dois extratores.
É camada **PARALELA e READ-ONLY sobre o M1**: `score_vulnerabilidade` **não é** `score_priorizacao`
nem `hex_score_estrutural`.

## Objetivo
Transformar os insumos brutos de S1/S3/S4 num `score_vulnerabilidade ∈ [0,100]` auditável, com
componentes `vi` expostos, renormalização por linha para sinal ausente/imaturo e as flags de
qualidade do §8.4 — sem calcular hotness, sem entregável comercial e sem escrever em disco.

---

## Achados que MUDAM o plano (medidos por mim hoje, contra o repositório de hoje)

Sonda própria (fixtures 100% sintéticas, caminho puro `snapshots=[...]`, zero I/O; script em
scratchpad, não versionado). Série de ramp-up de 3 semanas, 5 chaves, 2 hexes:

### A1 — CONFIRMADO: o score sai em `{0, 50}` no ramp-up (Q1 do enunciado)
`n_agregadores_no_hex` saiu `{1, 2}` (domínio travado por `presenca_agregador.py:208-211`) →
`v1 ∈ {0.0, 0.5}` → com S3/S4 renormalizados para fora e peso de S1 igual a `1,00`, o score assume
**exatamente dois valores: `0` e `50`**. A conclusão herdada do BLK-MA-03 **se sustenta** contra o
§8.2/§8.3/§8.4 vigentes e contra o que os módulos realmente emitem.

### A2 — NOVO (não está em nenhum handoff nem no contrato): o §8.4 descarta S3 **exatamente quando ele dispara**
Medi que `status_churn == "sumiu_recente"` **coexiste** com `flag_serie_imatura == True`:

```
chave_snapshot  fonte      rede          status_churn     n_semanas_serie  flag_serie_imatura
k_some          totalpass  independente  sumiu_recente    3                True
```

`status_churn` é calculado **independentemente** da maturidade (`churn_staleness.py:168-175`): só o
estado `novo` reusa `MIN_SEMANAS`. Consequência: pela regra literal do §8.4 ("série imatura →
renormaliza para fora"), durante ~8 meses uma academia que **verificavelmente sumiu do agregador**
recebe o mesmo score de uma que nunca se mexeu. É o único lever capaz de tirar o ramp-up de `{0,50}`
— e é decisão de produto (D2 abaixo), não do Planner.

### A3 — NOVO: o frame de churn traz **cadeias**; o universo de M&A precisa ser filtrado NESTE bloco
`extrair_churn_staleness` devolve TODAS as chaves, inclusive `fonte == "unidades"` (feed de
CADEIAS): a sonda saiu com `{'totalpass': 3, 'unidades': 1, 'wellhub': 1}`. O filtro de universo
(TP/WH × `independente`) existe **só** dentro do S1 (`_filtrar_universo_sinal_1`,
`presenca_agregador.py:117-129`). Se o BLK-MA-04 pontuar o frame de churn cru, **pontua Smart Fit
como alvo de aquisição**. O §8 do contrato não diz isso em lugar nenhum — assume "academias".

### A4 — CONFIRMADO: o join `many_to_one` fecha, e o `left_only` é 0 na MESMA série
`universo.merge(presenca, on="hex_id_res7", how="left", validate="many_to_one")` → cardinalidade
preservada, `left_only = 0`. Isso vale **por construção** (churn e presença usam a MESMA observação
mais recente da chave: `churn_staleness.py:183` usa `presentes[-1]`; `presenca_agregador.py:110-114`
usa `drop_duplicates(keep="last")` sobre `semana`), mas **só se os dois frames vierem da mesma
série**. Não é invariante do tipo — é invariante do INSUMO, e precisa de assert.

### A5 — NOVO: `novo` é um `status_churn` real e **não tem `v3` no §8.1**
`STATUS_CHURN_VALIDOS` tem 4 valores (`contrato.py:66`); o §8.1 mapeia 3 (`sumiu_recente`=1.0,
`piscando`=0.7, `estavel`=0.0). Na sonda, **4 das 5 linhas saíram `novo`**. `novo` ⟺
`flag_serie_imatura` (docstring de `extrair_churn_staleness`), logo pela regra do §8.4 ele nunca
precisa de valor — mas um `dict[status]` que estoure `KeyError` (ou, pior, devolva `0.0` em
silêncio, lendo "sumiu" como "estável") é defeito. Tem de ser mapeado **explicitamente para
ausente** e travado por teste.

### A6 — NOVO: §8.1 e §8.2 se CONTRADIZEM sobre a normalização de `v4` (Q4 do enunciado)
- §8.1: `v4 = min(semanas_sem_mudanca / STALE_SEMANAS, 1)` — razão absoluta.
- §8.2: "**Percentil por universo** ... para os sinais contínuos (rating, **staleness**,
  popularidade, pressão)".

Não dá para cumprir os dois. E o percentil é a opção pior, por 4 razões medidas/estruturais:
(a) percentil-por-universo torna o score **não reproduzível**: acrescentar uma UF muda o score de
todas as academias — mata a exigência-título do D4 ("AUDITÁVEL"); (b) é **degenerado no ramp-up** —
na sonda, `semanas_sem_mudanca` saiu `{2: 4 linhas, 1: 1 linha}`, um empate quase total, e o
percentil de um empate ou injeta vulnerabilidade fictícia em todos ou vira constante; (c) `v4` só
ENTRA no score quando `flag_staleness_interpretavel` — o universo do percentil seria um subconjunto
que muda a cada semana; (d) os OUTROS "contínuos" que o §8.2 cita (rating, popularidade, pressão)
estão **todos inativos** no Plano B (S2 = `n/d` por D3; S5/S6 fora do MVP) — ou seja, **o percentil
por universo não tem consumidor algum neste bloco**.

### A7 — as duas ressalvas herdadas NÃO são insumo do score (Q2 do enunciado)
- **`flag_troca_chave_na_serie`** (nasce permanentemente `True` — `BLK-MA-02-FU1` Item 1): **não é
  input de nenhum `vi`** no §8.1, nem flag de qualidade do §8.4. O score **não deve consumi-la nem
  propagá-la**. Consequência de backlog: o rótulo "**bloqueante para o BLK-MA-04**"
  (`tasks/backlog.md:1572,1581`) **deixa de valer** se este bloco não a consumir — vira bloqueante
  de quem for EXIBI-LA (BLK-MA-05/06). É reclassificação de backlog → sobe ao gate (D5).
- **`n_academias_independentes_*`** (super-conta sob rotação de chave — `BLK-MA-03-FU1` Item 1):
  também **não é input** de `v1` (que depende só de `n_agregadores_no_hex`). Achado adicional meu,
  que AGRAVA a ressalva: na sonda, o hex A saiu com `n_academias_independentes_totalpass = 2`
  contando `k_some`, que o S3 classificou `sumiu_recente` — a coluna conta academias **que já
  sumiram** (consequência da decisão R3 do MA-03, janela não encurtada). Recomendação: **não
  propagar** essas duas colunas para a saída do score; quem quiser "densidade do alvo" (BLK-MA-05)
  que faça o seu próprio join com `presenca_agregador_v1` e carregue a ressalva.

### A8 — `loop_guard`: nada a mudar
`scripts/loop_guard.py:175-178` já cobre `^src/motor_expansao/(lifetime|demanda_revelada|vulnerabilidade)/`
em **`_DENY_GOVERNANCA`** ("camadas paralelas com insumo de PII na origem (DEC-012)"), e
`_DENY_CRITICO` é avaliado ANTES (`:218` vs `:223`). Módulo e teste novos caem em `governanca`,
**zero `CRITICO`**. `tests/unit/test_loop_guard_paths.py:153` já parametriza o pacote.

### A9 — baseline de testes MEDIDA nesta base
`python -m pytest --collect-only -q` → **`2231 tests collected in 166.53s`**. Bate com a medição do
orquestrador. Falha pré-existente conhecida:
`tests/unit/test_score_retencao_territorial.py::test_run_readonly_m1_por_mtime` (BLK-FIX-LTV-01).
`pytest -n auto` **não funciona** neste ambiente (xdist 3.8.0, `WinError 6`) — rodar serial.

---

## Delimitação técnica (o que o Planner deve detalhar, e o que já está FECHADO por mim)

### F1 — Unidade de linha da saída: **ACADEMIA** (= `(fonte, chave_snapshot)`), não hex. FECHADO.
Evidência convergente no texto vigente: (a) §10/D6 nomeia a camada scored
`data/staging/vulnerabilidade_ma_academias.parquet`; (b) §9/D5 faz o join do hotness "**na lista de
academias**" por `academia.hex_id_res7 == carteira.hex_id`; (c) a emenda do §8.1 diz que `v1` é
"**propagado às academias do hex pelo BLK-MA-04 via join `validate="many_to_one"`**"; (d) S3/S4 só
existem no grão da chave — agregá-los ao hex aqui destruiria a unidade do funil (o alvo de aquisição
é um estabelecimento). O CSV hex-level do exemplo do §10/D6
(`n_independentes_vulneraveis`, `score_vulnerabilidade_medio`) é o **entregável do BLK-MA-05**,
derivado por agregação DESTE frame.
**Ressalva a escrever no docstring:** "academia" aqui é uma **chave de snapshot**, não um
estabelecimento nomeado (D1-B deferida) — a mesma academia em TP e WH são DUAS linhas (travado por
`test_churn_staleness.py::test_mesma_academia_em_duas_fontes_sao_duas_linhas`).

### F2 — Universo do score. FECHADO.
`fonte in FONTES_AGREGADORES` **E** `rede == CATEGORIA_INDEPENDENTE`, aplicado sobre o frame de
churn (achado A3). **Reusar** `_filtrar_universo_sinal_1` de `presenca_agregador.py` — há precedente
deliberado e idêntico de reuso de privada entre módulos irmãos deste pacote
(`presenca_agregador.py:69`: `from .churn_staleness import _montar_serie_longa`, "a validacao e UMA
so"). **NÃO** mover o predicado para `contrato.py`: aquele arquivo é, por contrato explícito, "**SEM
I/O e SEM pandas** — só stdlib" (`contrato.py:5`).
A `rede` do frame de churn já é a da **última observação presente** (`rede_ultima`,
`churn_staleness.py:184`), então o filtro herda automaticamente o P2 do MA-03 (classificação mais
recente vence).

### F3 — Regime de disponibilidade por linha. FECHADO (matemática), com uma decisão de produto (D2).
- `S1` disponível ⟺ a linha casou no join (`v1` não nulo). **Nunca renormalizado para fora por
  meia-faixa** (emenda G1, ratificada — não reabrir).
- `S2` **sempre indisponível** (D3, até BLK-MA-08).
- `S3` disponível ⟺ `flag_serie_imatura == False`.
- `S4` disponível ⟺ `flag_staleness_interpretavel == True`.

Como `STALE_SEMANAS (12) > MIN_SEMANAS (8)`, `S4` disponível **implica** `S3` disponível. Logo só
existem 3 regimes (mais as bordas de S1 ausente):

| regime | pesos efetivos (renormalizados) | domínio do score |
|---|---|---|
| `{S1}` | `S1 = 1,00` | **`{0, 50}`** |
| `{S1, S3}` | `0,15/0,50 = 0,30` · `0,35/0,50 = 0,70` | 8 valores discretos |
| `{S1, S3, S4}` | `≈0,20` · `≈0,467` · `≈0,333` (os efetivos do D4) | contínuo em [0,100] |

**Exigência de implementação:** a renormalização é **genérica** (dividir pela soma dos pesos
disponíveis), a partir de uma constante única com os **pesos-alvo do D4** (`S1=0,15`, `S2=0,25`,
`S3=0,35`, `S4=0,25`). **NÃO hardcodar** `0,20/0,467/0,333`: eles são CONSEQUÊNCIA de `S2` estar
fora e devem ser **asseridos por teste**, não digitados. Assim o BLK-MA-08 reativa `S2` sem tocar a
fórmula.

### F4 — Bordas obrigatórias. FECHADO.
- `n_sinais_disponiveis == 0` → `score_vulnerabilidade` **NULO**, jamais `0`. `0` significa "não
  vulnerável" e seria uma mentira semântica.
- `v1` ausente (linha sem par em S1) → **renormalizar S1 para fora**, jamais imputar `0.0` (que lê
  como "2 agregadores", injetando falso negativo) nem `0.5`.
- `v3` para `status_churn == "novo"` → **ausente**, explícito e testado (achado A5).
- `NaN` na saída significa SEMPRE "sinal não disponível" e **nunca** pode ser tratado como `0` em
  soma alguma.

### F5 — Onde materializar. FECHADO.
- **Módulo novo:** `src/motor_expansao/vulnerabilidade/score.py` (nome curto, no molde dos irmãos
  `snapshots` / `churn_staleness` / `presenca_agregador`; o pacote já carrega "vulnerabilidade").
  Função pública: `calcular_score_vulnerabilidade(...)`.
- **Constantes de contrato** em `contrato.py` (stdlib puro): `VERSAO_CONTRATO_SCORE =
  "score_vulnerabilidade_v1"`, `CONTRATO_COLUNAS_SCORE`, `PESOS_ALVO_SINAIS` (os 4 do D4) e
  `V3_POR_STATUS_CHURN`.
- **ZERO I/O.** Este bloco **não escreve Parquet nem CSV**: os artefatos
  `data/staging/vulnerabilidade_ma_academias.parquet` e `data/outputs/alvos_ma_priorizados.csv`
  são **D6 = BLK-MA-05** (§13). Precedente direto: `presenca_agregador.py` não escreve nada
  (comprovado pela sonda C do QA do MA-03). Materializar um artefato `{0,50}` em produção agora
  seria escopo do MA-05 **e** má ideia de produto.
- **Assinatura no molde XOR dos irmãos**: `base_dir` (conveniência, delega aos dois extratores sobre
  a MESMA série) **XOR** frames injetados (`churn=`, `presenca=`), que é como os testes rodam puros.
- **Testes:** `tests/unit/vulnerabilidade/test_score.py`.
- **Dois testes EXISTENTES que precisam ser estendidos** (senão o guardrail do pacote fica com
  buraco): `test_contrato.py::test_identificadores_do_contrato_sao_ascii` (acrescentar as chaves dos
  dicionários novos à lista `alvos`, `test_contrato.py:103-118`) e
  `test_snapshots.py::test_isolamento_imports` (acrescentar o módulo novo à tupla varrida — foi
  exatamente o que o MA-03 fez com `mpresenca`).

### F6 — Contrato de saída (proposta do BO; o Planner fecha a lista e a ordem)
Uma linha por `(fonte, chave_snapshot)` do universo de M&A:

| # | coluna | dtype | papel |
|---|---|---|---|
| 1 | `chave_snapshot` | `string` | a chave (opaca, sha1-40) |
| 2 | `fonte` | `string` | `totalpass` \| `wellhub` |
| 3 | `rede` | `string` | sempre `independente` (o filtro F2) |
| 4 | `hex_id_res7` | `string` | chave do join com S1 e, no MA-05, com o hotness |
| 5 | `v1` | `float64` | `{0.0, 0.5}` ∪ NaN — **categórico, NUNCA percentil** |
| 6 | `v3` | `float64` | `{0.0, 0.7, 1.0}` ∪ NaN (`novo` → NaN) |
| 7 | `v4` | `float64` | `[0,1]` ∪ NaN |
| 8 | `sinais_disponiveis` | `string` | `"s1"`/`"s1,s3"`/`"s1,s3,s4"` — ordem canônica, molde de `fontes_presentes_no_hex` |
| 9 | `n_sinais_disponiveis` | `int64` | §8.4 |
| 10 | `score_vulnerabilidade` | `float64` | `[0,100]` ∪ NaN |
| 11 | `flag_serie_imatura` | `bool` | §8.4, propagada do churn |
| 12 | `flag_staleness_interpretavel` | `bool` | propagada do churn |
| 13 | `flag_score_provisorio` | `bool` | §8.4: S3 **e** S4 indisponíveis |
| 14 | `n_agregadores_no_hex` | `int64` | auditoria de `v1`; **sufixo `_no_hex` preservado** (carrega o viés da emenda G1) |
| 15 | `fontes_presentes_no_hex` | `string` | idem |
| 16 | `semana_ultima_observacao` | `string` | relógio do PIPELINE (do churn) |
| 17 | `snapshot_date_ultimo` | `string` | relógio do COLETOR (do churn) — insumo da flag de staleness do BLK-MA-06 |
| 18 | `versao_contrato` | `string` | `score_vulnerabilidade_v1` |

**Requisito duro:** a renormalização tem de ser **reconstituível a partir das colunas da saída**, sem
reler o insumo (por isso `sinais_disponiveis` + os `vi`). **Fora, de propósito:**
`flag_troca_chave_na_serie` e `n_academias_independentes_*` (achado A7).

### F7 — `_assert_schema_score` no molde dos irmãos, com uma trava a MAIS
Além de colunas/ordem/dtypes/domínios, ele deve **rejeitar**:
- **colunas do M1** — `score_priorizacao`, `hex_score_estrutural`, `score_oficial`,
  `renda_pct_nacional`, `pop_pct_nacional`: torna o READ-ONLY do §5 **executável**, no espírito das
  travas `_COLUNAS_DE_SCORE_PROIBIDAS` dos dois irmãos;
- **colunas do BLK-MA-05** — `sam_fitness_potencial`, `score_oportunidade_residual`, `hex_quente`,
  `tese_entrada`, `oferta_efetiva_disponivel`: impede vazamento de escopo para o bloco seguinte, do
  mesmo jeito que os irmãos impediram o vazamento PARA cá.

---

## Decisões que sobem ao GATE HUMANO (o Planner NÃO decide sozinho)

| # | Decisão | Recomendação do BO |
|---|---|---|
| **D1** | **O que entregar no regime `{0,50}`** (Q1). Opções: **(a)** emitir o score como o §8.5 manda, com `flag_score_provisorio`, e deixar a apresentação para o BLK-MA-05; **(b)** emitir também uma coluna de **banda** rotulada; **(c)** suprimir o score enquanto provisório e emitir só banda; **(d)** adiar a materialização do epic até a maturidade. | **(a)**. O contrato §8.4/§8.5 **já prevê** o caso e a flag; banda é decisão de APRESENTAÇÃO, que é BLK-MA-05; e (c) destrói o número auditável que é o produto do D4. Registrar em CONTRAPARTIDA um aviso duro: **o BLK-MA-05 não pode ordenar carteira por `score_vulnerabilidade` enquanto `flag_score_provisorio` for `True`** — dentro de `{0,50}` a ordem é arbitrária. |
| **D2** | **Exceção assimétrica para `sumiu_recente` imaturo** (achado A2). Deixar S3 **entrar** no score quando `status_churn == "sumiu_recente"`, mesmo com série imatura? | **Levar como pergunta, com recomendação FRACA a favor.** A favor: sumiço é evidência POSITIVA e o risco que a maturidade protege (falso churn) já é neutralizado pela regra `(fonte, rede)` do MA-02; e é o único caminho para o ramp-up ordenar alguma coisa. Contra: **muda a semântica do §8.4**, ratificada no gate de 2026-07-23. **NÃO altera peso nenhum** (guardrail do D4 respeitado) — muda a regra de DISPONIBILIDADE. Se aprovada, vira emenda ao §8.4 e teste próprio. |
| **D3** | **Contradição §8.1 × §8.2 na normalização de `v4`** (achado A6). | **`v4 = min(semanas_sem_mudanca / STALE_SEMANAS, 1)`** (§8.1), e **emendar o §8.2** registrando que percentil-por-universo **não tem consumidor no Plano B** (S2 `n/d`, S5/S6 fora do MVP) e fica reservado para quando S2/S5/S6 existirem. `v1` e `v3` seguem categóricos por texto explícito do §8.2 + emenda G1. |
| **D4** | **Emenda ao contrato neste bloco** (§8.1 `novo`→ausente; §8.2 `v4`; §8.4 se D2 passar; §8.5 grão da linha = academia). Precedente: MA-02 e MA-03 emendaram o contrato no próprio ciclo, **sem DEC** (§14: "sem DEC neste bloco"). | Aprovar a emenda no mesmo PR, com marcação `[emenda BLK-MA-04]`, como os dois blocos anteriores fizeram. **Não é DEC** (não há API externa nem mudança no M1). |
| **D5** | **Reclassificar as duas ressalvas herdadas** (achado A7): `BLK-MA-02-FU1` Item 1 hoje está marcado "**bloqueante para o BLK-MA-04**" e o `BLK-MA-03-FU1` como "**antes do BLK-MA-04**". Se este bloco **não consome** as colunas afetadas, nenhum dos dois bloqueia. | **Desbloquear**, editando as 2 linhas do `tasks/backlog.md` (`:1572`, `:1653`) para apontar o dono real (**BLK-MA-05/06**, quem exibir). Alternativa conservadora: rodar o `BLK-MA-02-FU1` antes — custa um ciclo inteiro e **não muda uma linha** deste bloco. |

**Pendência de backlog já herdada e ainda não feita** (QA do MA-02, "Riscos remanescentes"):
registrar o **cron MENSAL dos agregadores** como `Depende de` explícito do BLK-MA-04. Como este
bloco **não** lê fonte real (fixtures sintéticas), ele **não** é bloqueado por isso — a dependência
é do VALOR do output, não da entrega do código. Registrar como nota no bloco, não como bloqueio.

---

## Escopo permitido
- Criar `src/motor_expansao/vulnerabilidade/score.py` (módulo PURO, sem I/O) com
  `calcular_score_vulnerabilidade` e `_assert_schema_score`.
- Acrescentar a `src/motor_expansao/vulnerabilidade/contrato.py` (stdlib puro, **sem pandas**):
  `VERSAO_CONTRATO_SCORE`, `CONTRATO_COLUNAS_SCORE`, `PESOS_ALVO_SINAIS`, `V3_POR_STATUS_CHURN`.
- Exportar a API nova em `src/motor_expansao/vulnerabilidade/__init__.py`.
- Criar `tests/unit/vulnerabilidade/test_score.py` (fixtures **100% sintéticas**).
- Estender `tests/unit/vulnerabilidade/test_contrato.py` (lista `alvos` do teste ASCII) e
  `tests/unit/vulnerabilidade/test_snapshots.py` (tupla do `test_isolamento_imports`).
- Emendar `docs/vulnerabilidade_ma_contrato.md` (§8.1/§8.2/§8.5, e §8.4 se o gate aprovar o D2),
  marcando `[emenda BLK-MA-04]` — no molde exato dos dois blocos anteriores.
- Registrar o bloco em `tasks/backlog.md` (**BLK-MA-04 ainda NÃO tem seção própria**: só existe como
  bullet da decomposição do BLK-MA-01, `tasks/backlog.md:1552`) e o fechamento em
  `tasks/completed.md`; snapshots em `context/handoff/`.

## Fora de escopo
- **Qualquer artefato/peso/score do M1** — `score_priorizacao`, `hex_score_estrutural`, pesos
  `renda=0.40`/`pop=0.60`, carteira, plano curto prazo, plano de domínio.
- **Reabrir os pesos do D4** (S1=0,15 / S2=0,25 / S3=0,35 / S4=0,25) — decididos no gate de
  2026-07-23. Se algo parecer errado: **registrar como observação e escalar**, nunca alterar.
- **Reabrir a granularidade hex do `v1`** (emenda G1, ratificada em 2026-07-29).
- **Sinal 2 / rating** — `n/d` permanente (D3) até o **BLK-MA-08**.
- **Hotness, `h3.grid_disk(k=1)`, a INVERSÃO aplicada, lista comercial e os artefatos do D6**
  (`vulnerabilidade_ma_academias.parquet`, `alvos_ma_priorizados.csv`) — **BLK-MA-05**.
- **Plug no `run_weekly_90.sh` / cron / runbook** — **BLK-MA-06**.
- **Editar `snapshots.py`, `churn_staleness.py` ou `presenca_agregador.py`** (salvo, se o gate
  aprovar, promover `_filtrar_universo_sinal_1` — mas o reuso da privada, com precedente, é
  preferível).
- **Corrigir as ressalvas dos FU1** (`flag_troca_chave_na_serie`, `n_academias_independentes_*`,
  ponto cego do AST, acentuação de prosa herdada) — são `BLK-MA-02-FU1` / `BLK-MA-03-FU1`.
- `MIN_SEMANAS` / `STALE_SEMANAS` / `RETENCAO_SEMANAS` — valores do gate de 2026-07-23; revisitar só
  no BLK-MA-06.
- **Ler fonte real, escrever em disco, persistir PII, criar dependência de API ao vivo.**
- `PRD.md`, `.gitignore`, `pyproject.toml`, `scripts/loop_guard.py`, `graphify-out/*`.

## Arquivos que devem ser lidos
- `docs/vulnerabilidade_ma_contrato.md` — §8 **inteiro** (8.1 com a emenda BLK-MA-03, 8.2, 8.3, 8.4,
  8.5), mais §1, §2 (a INVERSÃO), §4, §7 (D3), §9 (D5), §10 (D6), §11, §12, §13, §14, §15.
- `src/motor_expansao/vulnerabilidade/contrato.py` — `CONTRATO_COLUNAS_CHURN` (`:207-225`),
  `CONTRATO_COLUNAS_PRESENCA_AGREGADOR` (`:237-248`), `MIN_SEMANAS`/`STALE_SEMANAS` (`:43-44`),
  `STATUS_CHURN_VALIDOS` (`:66`), `FONTES_AGREGADORES` (`:72`), `CATEGORIA_INDEPENDENTE` (`:79`),
  e a regra "**sem I/O e sem pandas**" (`:5`).
- `src/motor_expansao/vulnerabilidade/churn_staleness.py` — `_estado_por_chave:128-213` (como
  `status_churn`, `semanas_sem_mudanca` e as 3 flags nascem) e `extrair_churn_staleness:251-295`.
- `src/motor_expansao/vulnerabilidade/presenca_agregador.py` — `_filtrar_universo_sinal_1:117-129`,
  `_agregar_por_hex:132-173`, `_assert_schema_presenca_agregador:176-265`, o docstring do módulo
  (granularidade hex e o limite "0 agregadores") e o reuso de privada em `:69`.
- `src/motor_expansao/vulnerabilidade/__init__.py`.
- `tests/unit/vulnerabilidade/test_presenca_agregador.py` (molde de fixture sintética `_linha`,
  `_frame`, e o par de testes P1/P2) e `tests/unit/vulnerabilidade/test_churn_staleness.py`.
- `tests/unit/vulnerabilidade/test_contrato.py:102-122` (teste ASCII a estender).
- `context/handoff/20260729-134525-qa.md` e `context/handoff/20260729-162056-qa.md` (as ressalvas).
- `context/handoff/20260729-123146-planner.md` e `20260729-151112-planner.md` (contratos de coluna).
- `CLAUDE.md` §1/§2/§3/§4/§5/§6.1/§8.
- `scripts/loop_guard.py:152-190` (para confirmar que nada muda).

## Arquivos que podem ser alterados
- `src/motor_expansao/vulnerabilidade/score.py` **(novo)**
- `src/motor_expansao/vulnerabilidade/contrato.py`
- `src/motor_expansao/vulnerabilidade/__init__.py`
- `tests/unit/vulnerabilidade/test_score.py` **(novo)**
- `tests/unit/vulnerabilidade/test_contrato.py`
- `tests/unit/vulnerabilidade/test_snapshots.py` (só a tupla do `test_isolamento_imports`)
- `docs/vulnerabilidade_ma_contrato.md` (emenda `[emenda BLK-MA-04]`)
- `tasks/backlog.md` (seção nova do BLK-MA-04 + as 2 linhas do D5, se aprovado)
- `tasks/completed.md` (Passo 6)
- `context/handoff/` (snapshots)

**NÃO commitar:** `graphify-out/*` (pré-sujo, regerado pelo hook), `PRD.md`, `context/handoff.md`,
`tasks/current_task.md`.

## Critérios de aceite

**Fórmula e regime**
- **CA-1** — `PESOS_ALVO_SINAIS` carrega os 4 pesos do D4 (`0,15 / 0,25 / 0,35 / 0,25`) e a
  renormalização é **genérica**; teste assere que, com S2 fora e S3/S4 maduros, os pesos efetivos
  saem `≈0,20 / ≈0,4667 / ≈0,3333` — **calculados, não digitados**.
- **CA-2** — os 3 regimes de F3 produzem `n_sinais_disponiveis ∈ {1,2,3}` e os pesos efetivos
  tabelados; teste por regime.
- **CA-3** — `v1` derivado de `n_agregadores_no_hex` por mapa categórico (`2→0.0`, `1→0.5`);
  teste prova que **nenhum percentil** toca `v1` nem `v3`.
- **CA-4** — `v3` pelo mapa `V3_POR_STATUS_CHURN` com `novo` → **ausente**; teste cobre os 4 status.
- **CA-5** — `v4 = min(semanas_sem_mudanca / STALE_SEMANAS, 1)`, com clip em `1`, e **só entra**
  quando `flag_staleness_interpretavel`.
- **CA-6** — regime `{S1}` produz `score_vulnerabilidade ∈ {0, 50}` e `flag_score_provisorio=True`
  em **todas** as linhas — o achado A1, congelado por teste (é a evidência que o gate vai reler).
- **CA-7** — `n_sinais_disponiveis == 0` → score **nulo**, nunca `0`; `v1` ausente **não** é imputado.

**Universo, join e cardinalidade**
- **CA-8** — linha com `fonte == "unidades"` (cadeia) **nunca** entra na saída (achado A3), mesmo
  com `rede` forjada como `independente`.
- **CA-9** — join com S1 por `hex_id_res7` com `validate="many_to_one"`; teste assere `len`
  inalterado e `left_only == 0` para insumos da mesma série; e teste da borda (hex sem par em S1 →
  `v1` nulo, S1 renormalizado para fora, score ainda calculado).
- **CA-10** — a saída **não** contém `flag_troca_chave_na_serie` nem `n_academias_independentes_*`
  (achado A7), e a razão está no docstring.

**Contrato, guardrails e higiene**
- **CA-11** — `_assert_schema_score` valida colunas/ordem/dtypes/domínios e **rejeita** colunas do M1
  e colunas do BLK-MA-05 (F7), com teste por coluna proibida.
- **CA-12** — o módulo **não escreve nada em disco** e **não lê fonte real** (grep por
  `to_parquet`/`to_csv`/`open(`/`mkdir` + varredura AST no molde do
  `test_sem_caminho_real_nos_testes`); função **pura** (frame de entrada não mutado; resultado
  independente da ordem dos insumos).
- **CA-13** — isolamento de import: o módulo novo entra na tupla do `test_isolamento_imports`; não
  importa `pipelines/m1`, `dashboard`, `api`, `censo_*`, `config.py` raiz nem
  `normalizar_concorrentes`.
- **CA-14** — anti-PII (DEC-012): nenhuma coluna de `COLUNAS_PII_PROIBIDAS` na saída; fixtures 100%
  sintéticas; nenhum número de produção gerado.
- **CA-15** — §2 acentuação: **prosa acentuada** (docstrings e comentários, inclusive no arquivo de
  teste — é a ressalva `m4`/`m2` que os DOIS blocos anteriores levaram); **identificadores, nomes de
  coluna, valores de enum e chaves de dicionário 100% ASCII**, travados pelo teste ASCII estendido.
- **CA-16** — emenda do contrato aplicada e marcada `[emenda BLK-MA-04]`, cobrindo o que o gate
  aprovar nos D2/D3/D4; sem DEC nova.
- **CA-17** — READ-ONLY sobre o M1 **provado pelo diff** (`git status --porcelain` +
  `git diff --stat`: nada em `config.py`, `pipelines/`, `normalizar_concorrentes.py`,
  `calcular_colunas_mercado.py` ou artefato oficial) e `loop_guard --stdin` **sem `CRITICO`**
  (só `governanca`).
- **CA-18** — suíte completa sem regressão contra a baseline **2231 coletados**; `ruff check .
  --no-cache` limpo; falha pré-existente `test_run_readonly_m1_por_mtime` continua sendo a única.
- **CA-19** — `tasks/backlog.md` com seção própria do BLK-MA-04, `| **Autonomia** | **manual (NÃO
  loop-safe)** |` (mesmo perfil do pacote: insumo com PII na origem), **LF preservado** (DEC-017) e
  `python scripts/garimpeiro_select_block.py --list` **não** listando o bloco.

## Criticidade classificada
**ALTA** — confirmada e re-verificada por mim, não herdada por inércia:
- **nada** aqui toca `score_priorizacao`, `hex_score_estrutural`, pesos do M1, carteira, plano ou
  artefato oficial (F5 + F7 + CA-17); o pacote é DISJUNTO e o `loop_guard` o classifica
  `governanca`, não `critico` (achado A8);
- a interpretação operacional de 2026-05-30 no `CLAUDE.md` amarra **Crítica** a alteração de
  fórmula/pesos/artefato **do M1** — este é um score PARALELO;
- o gate de produto do D4 **já ocorreu** (2026-07-23) e o contrato §14 diz "sem DEC neste bloco";
- **Alta já entrega o gate humano antes do Builder**, que é a proteção que importa — e este ciclo
  **precisa** dele: são 5 decisões de produto (D1–D5).

> **ALERTA (guardrail do meu prompt):** se, durante o Planner ou o Builder, aparecer QUALQUER
> escrita em artefato do M1, leitura-e-reescrita de carteira/plano, ou reuso dos pesos
> `renda=0.40`/`pop=0.60`, o bloco **para** e é **reclassificado como CRÍTICA** (aprovação explícita
> + DEC). Nada do que delimitei acima chega perto disso.

## Esteira recomendada
**Block Orchestrator (feito) → Planner (opus) → `[GATE HUMANO OBRIGATÓRIO — D1..D5]` → Builder
(opus) → QA (opus, regra dura) → Fechamento Passo 6 em modo MERGE-HUMANO** (o ciclo toca
`tasks/backlog.md` e `docs/`, ambos `governanca`; auto-merge de Baixa/Média da DEC-016 **não** se
aplica a Alta, que exige a label `aprovado-humano`).

## Riscos identificados
- **R1 (ALTO, de PRODUTO, é o motivo do gate)** — o score sai em `{0,50}` por ~8–12 meses (A1).
  Mitigação: `flag_score_provisorio` + aviso duro de que o BLK-MA-05 não pode ordenar por ele
  enquanto for `True`. **Decisão D1.**
- **R2 (ALTO, de PRODUTO)** — pelo §8.4 literal, `sumiu_recente` imaturo **não pontua** (A2): durante
  o ramp-up, quem sumiu do agregador e quem nunca se mexeu recebem o mesmo score. **Decisão D2.**
- **R3 (MÉDIO, corrigível no plano)** — pontuar cadeia como alvo de M&A se o universo não for
  filtrado (A3). Mitigação: F2 + CA-8.
- **R4 (MÉDIO)** — insumos de séries DIFERENTES quebram a invariância do join (A4). Mitigação:
  `base_dir` único derivando os dois frames + assert de `left_only` + teste de borda (CA-9).
- **R5 (MÉDIO)** — a renormalização por linha torna scores de linhas com regimes diferentes
  **não comparáveis** (uma linha `{S1}` e uma `{S1,S3,S4}` não estão na mesma régua). É inerente ao
  §8.4; mitigação prevista pelo próprio contrato: `n_sinais_disponiveis` + `sinais_disponiveis` na
  saída, e a proibição de ordenar carteira misturando regimes (nota para o BLK-MA-05).
- **R6 (MÉDIO)** — percentil-por-universo destruiria a auditabilidade e é degenerado no ramp-up
  (A6). Mitigação: **decisão D3** + emenda ao §8.2.
- **R7 (BAIXO, herdado e registrado)** — `flag_troca_chave_na_serie` permanentemente `True` e
  `n_academias_independentes_*` inflada: **neutralizados por não-consumo** (A7). Se um bloco futuro
  quiser exibi-las, os FU1 voltam a ser bloqueantes.
- **R8 (BAIXO, herdado)** — o insumo real **não existe**: o cron MENSAL dos agregadores segue
  pendente (§12, caminho crítico). Nenhum número de produção sai deste bloco; tudo é fixture
  sintética. Não bloqueia a ENTREGA do código.
- **R9 (BAIXO, de tooling)** — `pytest -n auto` inutilizável neste ambiente (xdist 3.8.0,
  `WinError 6`); o QA roda **serial**, como o CI.
- **R10 (BAIXO, de processo)** — a pilha de branches está em **3 níveis** sem merge
  (`ciclo/BLK-MA-02` → `03` → `04`), e os três tocam `tasks/backlog.md`, que a `main` também mexe.
  Risco assumido e registrado na decisão B1 do ciclo — se a revisão do MA-02 pedir mudança, as bases
  dos outros dois precisam ser refeitas.

## Guardrails ativos
- **READ-ONLY sobre o M1 (CLAUDE.md §1/§5; contrato §14).** `score_vulnerabilidade` é **PARALELO**:
  não é `score_priorizacao` nem `hex_score_estrutural`; nada recalcula ou altera pesos
  `renda=0.40`/`pop=0.60`, carteira, plano curto prazo, plano de domínio ou artefato oficial.
  Imposto por código (`scripts/loop_guard.py` + `.github/workflows/guard.yml`).
- **Pesos do D4 CONGELADOS** (gate de 2026-07-23): `S1=0,15 / S2=0,25 / S3=0,35 / S4=0,25`. Não
  reabrir — observação e escalada, nunca alteração.
- **Emenda G1 CONGELADA** (2026-07-29): `v1` é medido por **hex**, é **categórico** e **nunca**
  percentilizado; domínio `{0.0, 0.5}`; **não** é renormalizado para fora por meia-faixa.
- **Sinal 2 (rating) = `n/d` permanente** (D3) até o **BLK-MA-08**.
- **Anti-PII (DEC-012).** Só agregados; geometria deriva do `hex_id`, nunca de GPS bruto; fonte real
  **nunca** versionada; fixtures **sintéticas**; nenhuma coluna de `COLUNAS_PII_PROIBIDAS` na saída.
- **Sem API externa ao vivo (§2).** Plano B é 100% interno; dashboard segue offline sobre Parquets.
- **Acentuação (§2).** Prosa em português acentuado; **identificadores, nomes de coluna, valores de
  enum e slugs em ASCII** — a camada de exibição acentuada, se houver, é do BLK-MA-05.
- **CSV do projeto `sep=";"` / `utf-8-sig`; staging sempre em Parquet** (não se aplica aqui: este
  bloco não escreve).
- **Não commitar `graphify-out/*`** (pré-sujo do hook `post-commit`), `PRD.md`,
  `context/handoff.md`, `tasks/current_task.md`.
- **Um bloco por vez.** BLK-MA-05 (hotness/INVERSÃO/entregável) e BLK-MA-06 (cron) são blocos
  próprios; os FU1 são blocos próprios.
