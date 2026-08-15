# Handoff — Block Orchestrator

> Gerado em 2026-08-15, na branch `ciclo/BLK-MA-17`. Substitui o handoff do QA do BLK-MA-04
> (2026-07-30), que estava stale. Cópia append-only em
> `context/handoff/20260815-164027-block-orchestrator.md`.

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
**Planner** — e o Planner PARA no gate humano antes do Builder. Há decisões de escopo e de DEC que
não são do agente (seção "Decisões que sobem ao GATE HUMANO", D1–D8).

## Bloco refinado

**BLK-MA-17 — Unidades de REDE presentes nos agregadores ganham o diagnóstico visível.**

O snapshot da semana `2026-33` tem **22.173 linhas: 19.329 independentes e 2.844 de REDE**, em 83
redes (medido hoje, não copiado do backlog). As 2.844 são unidades de cadeia listadas no WellHub que
`_filtrar_universo_sinal_1` corta antes do score. O bloco tem **duas metades separáveis, com gates
diferentes**, e a segunda **não depende** da DEC que trava a primeira:

- **Metade 1 — EXIBIR o diagnóstico nas unidades de rede.** Muda o UNIVERSO declarado da camada
  (§3/D1 do contrato: "TotalPass/WellHub × independente"), hoje travado por assert **na entrada e na
  saída** do score. **Exige DEC própria.** Envolve um universo de exibição próprio (nunca afrouxar o
  predicado comum), pin próprio a partir da coordenada do feed (molde BLK-MA-15) e regra de
  precedência para os **1.665 (58,5%)** que virariam dois pins no mesmo lugar.
- **Metade 2 — CONTÁ-LAS COMO OFERTA no S6.** Não mexe no universo do score: elas são concorrência
  por definição, e o insumo de oferta é montado **noutro lugar, por outro predicado** (provado em Q3).
  Corrige um número que já está na tela: **1.134 unidades de rede (39,9%) não têm nenhum ponto de
  cadeia a menos de 150 m** em `concorrentes_mapeados.parquet` — são academias reais que hoje **não
  pressionam ninguém** no cálculo.

**Recomendação de escopo (vai ao gate, D1): entregar SÓ a metade 2 neste ciclo.** Ela corrige um
defeito medido, não depende de DEC de universo, e vive inteira em
`src/motor_expansao/vulnerabilidade/` — enquanto a metade 1 mexe em `web/`, onde `origin/main` tem 16
commits não mergeados reescrevendo `web/server/app.py` (P0-3 do Passo 0).

## Objetivo

Fazer as unidades de rede que o WellHub lista **pressionarem** no sinal 6 (metade 2, recomendada
para este ciclo) e, atrás de DEC própria, **aparecerem com diagnóstico** no piloto (metade 1) —
tudo READ-ONLY sobre o M1.

## Escopo permitido

### Metade 2 (recomendada para este ciclo)
- Acrescentar as unidades de REDE do feed (`coordenadas_por_chave`, `rede != "independente"`) ao
  conjunto de oferta do sinal 6, com **peso de cadeia** (`PESO_OFERTA_CADEIA = 1.0`).
- **Dedup contra `concorrentes_mapeados.parquet`** para que a mesma unidade nunca conte duas vezes,
  com o limiar decidido no gate (D5) e travado por teste.
- **Estender a auto-exclusão ao lado cadeia** (D6): hoje `auto_pos` só zera a parcela da própria
  academia no bloco de independentes.
- Decomposição/auditoria da oferta nova (colunas), carimbo e **bump de versão** conforme o gate (D4).
- Emenda ao §8.1 de `docs/vulnerabilidade_ma_contrato.md` (a mesma seção que a DEC-030 emendou).
- Testes: dedup travada nos dois sentidos, auto-exclusão, efeito medido antes/depois, default do
  pipeline, e a flag de reprodução do número histórico.

### Metade 1 (só se o gate liberar; **exige DEC**)
- Universo de EXIBIÇÃO próprio para unidades de rede — **sem tocar** `_filtrar_universo_sinal_1`.
- Propagar **fatos** (`status_churn`, `nota_wellhub`, `qtd_avaliacoes_wellhub`) e o **S6**; **não**
  emitir `score_vulnerabilidade` para elas (recomendação do backlog, a ratificar no gate — D8).
- Pin próprio a partir da coordenada do feed, com regra de precedência explícita contra o pin de
  cadeia do funil, e a auditoria da pressão no tooltip (molde BLK-MA-18).
- Artefato nomeado nasce **gitignored**, sob `data/staging/` (`_assert_destino_gitignored`).

## Fora de escopo

- Qualquer artefato, peso ou score do M1. **READ-ONLY inviolável.**
- Afrouxar `_filtrar_universo_sinal_1` (quebraria `n_academias_independentes_totalpass`/`_wellhub`,
  que passariam a contar redes com o nome dizendo o contrário).
- Colocar unidade de rede na **lista comercial de alvos** de M&A (BLK-MA-05) — a lista continua só
  com independentes, travado por teste.
- Régua de score própria para rede (bloco futuro, se a DEC concluir que faz falta).
- BLK-MA-05, MA-06, MA-08, MA-09; o cron; a coleta.
- Mexer na saturação `1 − 1/(1+oferta)` ou no kernel — o achatamento do topo é conhecido e
  registrado em `contrato.py` (comentário de `PESO_OFERTA_INDEPENDENTE`).

## Arquivos que devem ser lidos

- `CLAUDE.md` (§1, §2, §4, §6.1, §8)
- `tasks/backlog.md` — seção `### BLK-MA-17` (linhas 1595-1678)
- `tasks/current_task.md` — Passo 0 do orquestrador + a seção deste handoff
- `docs/vulnerabilidade_ma_contrato.md` — §2 (INVERSÃO), §3/D1 (universo), §8.1 (emendas BLK-MA-14 e
  BLK-MA-16), §8.4 (universo do score, bordas de ausência), §14, §15
- `docs/decisions/DEC-027.md` (S6 condicional, `w6 = 0,10`), `docs/decisions/DEC-029.md` (grão
  academia, rota B sem bump de série), `docs/decisions/DEC-030.md` **local** (independentes na
  oferta; **atenção: colide com a DEC-030 de `origin/main`** — ver Q7)
- `src/motor_expansao/vulnerabilidade/presenca_agregador.py` (`_filtrar_universo_sinal_1`, 141-153)
- `src/motor_expansao/vulnerabilidade/score.py` (`_preparar_universo` 170-177; `_juntar_pressao`
  204-291; asserts de universo 496-504; carimbos 531-550)
- `src/motor_expansao/vulnerabilidade/pressao_competitiva.py` (`_oferta_por_origem` 214-303;
  `dedup_independentes` 311-397; `calcular_pressao_por_academia` 400-528;
  `_assert_universo_e_decomposicao` 557-596; `_pontos_validos` 193-201; `ler_concorrentes` 707-728)
- `src/motor_expansao/vulnerabilidade/alvos_ma.py` (`_pressao_por_academia` 554-604; `main` 607-656;
  CLI 488-551)
- `src/motor_expansao/vulnerabilidade/alvos_nomeados.py` (molde do artefato nomeado)
- `src/motor_expansao/vulnerabilidade/contrato.py` (400-530: constantes de pressão, universo de
  oferta, pesos, dedup, contratos de coluna)
- `src/motor_expansao/vulnerabilidade/snapshots.py` (`coordenadas_por_chave`, 519-580)
- `tests/unit/vulnerabilidade/test_universo_oferta_s6.py`, `test_score.py` (991-1030),
  `test_presenca_agregador.py` (204-215), `tests/unit/test_piloto_web_independentes.py`
- `web/server/app.py` (95-113, 400-500, 2140-2150) — só se a metade 1 entrar

## Arquivos que podem ser alterados

### Metade 2
- `src/motor_expansao/vulnerabilidade/pressao_competitiva.py`
- `src/motor_expansao/vulnerabilidade/contrato.py`
- `src/motor_expansao/vulnerabilidade/alvos_ma.py`
- `src/motor_expansao/vulnerabilidade/score.py` (**só** carimbo/versão; os asserts de universo ficam
  intactos)
- `tests/unit/vulnerabilidade/test_universo_oferta_s6.py` (+ arquivo de teste novo, se preferir)
- `tests/unit/vulnerabilidade/test_score.py`
- `docs/vulnerabilidade_ma_contrato.md` (emenda ao §8.1)
- `docs/decisions/DEC-0NN.md` + `docs/decisions/README.md` + `CLAUDE.md` §8 (1 linha) — se o gate
  decidir por DEC (D2/D3)
- `tasks/backlog.md`, `tasks/completed.md` (bookkeeping do fechamento)

### Metade 1 (adicionalmente, só com DEC aprovada)
- `src/motor_expansao/vulnerabilidade/alvos_nomeados.py` (ou módulo novo para o universo de exibição)
- `web/server/app.py`, `web/src/components/HexMap.tsx`, `web/src/lib/types.ts`,
  `web/src/screens/MapScreen.tsx`
- `tests/unit/test_piloto_web_independentes.py` (+ testes novos)

### PROIBIDOS (o `loop_guard` derruba, e o guardrail é do CLAUDE.md)
`config.py` · `src/motor_expansao/pipelines/m1/` · `normalizar_concorrentes.py` ·
`calcular_colunas_mercado.py` · artefatos oficiais do M1 · `deploy/`, `Dockerfile.*`, compose,
Caddy, `.env`, CI. **Não commitar** `graphify-out/*` (regerado pelo hook post-commit), `PRD.md`,
`context/handoff.md`, `tasks/current_task.md`.

## Critérios de aceite

### Metade 2
1. A mesma unidade **nunca conta duas vezes**: teste que injeta uma unidade de rede do feed a `< d`
   de um ponto de `concorrentes_mapeados` e prova que a oferta não dobra; e o simétrico, com uma
   unidade a `> d`, provando que ela ENTRA.
2. **Auto-exclusão do lado cadeia** travada por teste: uma unidade de rede como origem não recebe
   `sat(1,0) = 50` pontos de pressão de si mesma.
3. **Efeito medido antes/depois** registrado no commit, com o método reproduzível (a medição-base
   deste handoff está em Q1/Q3 e pode ser reusada).
4. O carimbo não mente: `_assert_universo_e_decomposicao` continua valendo e a decomposição nova
   (D4) é somável ao total, com a parte zerada no universo `cadeias`.
5. `--oferta-so-cadeias` continua reproduzindo o número histórico (é a única régua comparável com
   `pressao_concorrencial_score_2km`).
6. `_filtrar_universo_sinal_1` **intacto**; `n_academias_independentes_totalpass`/`_wellhub`
   inalteradas; `test_reusa_filtro_de_universo_do_sinal_1` continua verde (ele assere identidade de
   objeto entre os dois módulos).
7. A lista de alvos de M&A segue **só com independentes**.
8. READ-ONLY sobre o M1; suíte verde (baseline **3.184 testes coletados**, medida hoje).

### Metade 1 (se entrar)
9. DEC própria aprovada, decidindo o que é propagado (fatos e/ou score) e a **precedência de pin**.
10. Universo de exibição **separado**; nenhum assert de universo do score afrouxado.
11. Artefato nomeado nasce gitignored (`_assert_destino_gitignored`), anti-PII no molde do BLK-MA-15.
12. Nenhuma unidade de rede na lista comercial de alvos, travado por teste.

## Criticidade classificada

**ALTA** (as duas metades).

- Metade 1: muda o universo DECLARADO da camada (§3/D1) — o backlog já a classifica Alta e exige DEC.
- Metade 2: muda **quem conta como oferta** de um componente **ATIVO** do score (`w6 = 0,10`,
  DEC-027) e desloca `score_vulnerabilidade` em **37,1% do universo** (medido, ver Q1). É o mesmo
  eixo que a DEC-030 tratou como Alta, e com um agravante que a DEC-030 não tinha: lá o Spearman era
  `1,000000` (não reordenava); aqui é **0,991157** — **a ordem muda**.
- **NÃO é Crítica:** nada aqui escreve em artefato do M1 nem reusa `renda=0.40`/`pop=0.60`. A
  carteira de mercado é lida (hotness) e nunca reescrita. **Se em qualquer momento aparecer escrita
  em artefato do M1, o bloco PARA e é reclassificado como CRÍTICA.**

## Esteira recomendada

`Block Orchestrator` (feito) → **`Planner`** → **`[GATE HUMANO — escopo D1 + DEC D2/D3]`** →
`Builder` → `QA` → `fechar-ciclo`.

Tiering (do Passo 4, mantido): Planner = opus · Builder = opus · QA = opus.

## Riscos identificados

1. **O carimbo `universo_oferta` passa a mentir por omissão.** Depois da metade 2 o valor continua
   `cadeias_e_independentes`, mas o conjunto de pontos é outro — duas rodadas com o mesmo carimbo
   dariam números diferentes (61,4 contra 62,8 de média). É o defeito exato que o carimbo existe
   para impedir. Mitigação: D4 (bump de versão e/ou terceiro valor de enum).
2. **A auditoria do BLK-MA-18 degrada.** O tooltip promete "confere olhando o próprio mapa", mas as
   1.134 unidades novas **não são desenhadas em lugar nenhum** (o mapa só pinta os 4.499 pins de
   cadeia e as independentes nomeadas). Depois da metade 2, `n_conc` conta o que o operador não vê.
   Mitigação: D7 — decompor a contagem, declarar, ou entregar o pin da metade 1 junto.
3. **Auto-pressão de 50 pontos** se a metade 2 entrar sem estender a auto-exclusão (D6). Inócuo hoje
   (as linhas de rede são descartadas no join do score), **letal** se a metade 1 entrar depois.
4. **Colisão de DEC não resolvida** (P0-2 / Q7): a `DEC-030` local (MA-16) e a de `origin/main` (dois
   selos) são documentos diferentes com o mesmo número. Qualquer DEC nova deste bloco tem de nascer
   em **033**, e a 030 local terá de ser renumerada antes do merge. **Não decidir sozinho.**
5. **Pilha de 22 commits sem PR** (P0-1). Este ciclo empilha por cima. A metade 1 mexeria em
   `web/server/app.py`, que `origin/main` está reescrevendo → conflito provável. A metade 2 não
   colide.
6. **Limiar de dedup não calibrado.** `DEDUP_INDEPENDENTES_M = 50` é declaradamente arbitrado. A
   escolha muda o resultado de forma material: **1.418 (50 m) / 1.134 (150 m) / 834 (300 m)**
   unidades entram como oferta nova. Mitigação: D5, com a sensibilidade registrada na DEC.
7. **Falso zero residual não some.** Depois da metade 2 os zeros caem só de **5,5% para 5,3%** — as
   1.134 unidades estão majoritariamente perto de quem já tinha pressão. Quem vender o bloco como
   "acaba com o falso zero" estará errado; o que ele faz é corrigir a MAGNITUDE (37,1% do universo).
8. **`_pontos_validos` filtra `status_registro == "valido"`** (4.366 dos 4.499). A dedup da metade 2
   tem de casar contra os pontos que realmente entram na oferta, não contra o parquet cru — senão
   uma unidade "descartada_duplicado" mascara a entrada de um ponto legítimo.

## Guardrails ativos

- **READ-ONLY sobre o M1 (§1/§3/§5 do CLAUDE.md, §14 do contrato do epic).** Nada aqui recalcula ou
  altera `score_priorizacao`, `hex_score_estrutural`, pesos `renda=0.40`/`pop=0.60`, carteira, plano
  curto prazo, plano de domínio ou artefatos oficiais. Imposto por `scripts/loop_guard.py` +
  `.github/workflows/guard.yml`.
- **Anti-PII (DEC-012 / §11).** Coordenada e nome só no artefato NOMEADO, que é **gitignored** e vive
  sob `data/staging/`. `_assert_schema_pressao_academia` barra coordenada na saída da pressão —
  qualquer mudança na metade 2 mantém esse guard.
- **Acentuação (regra permanente).** Prosa de usuário em português acentuado; **identificadores,
  chaves de payload, valores de enum e nomes de coluna sempre em ASCII** (`universo_oferta`,
  `cadeias_e_independentes`, `pressao_grao`).
- **CSV do projeto** `sep=";"`, `encoding="utf-8-sig"`.
- **Não loop-safe** (`Autonomia: manual` no backlog) — muda o universo da camada.
- **Grafo antes de varredura** (§2): consultar `python -m graphify query` antes de grep amplo.

---

# Respostas Q1-Q7 (medidas nesta sessão, 2026-08-15)

Ambiente: branch `ciclo/BLK-MA-17`; insumo real **disponível nesta estação** —
`concorrentes/wellhub/csvs/` (27 UFs), `data/staging/snapshots_concorrentes/semana=2026-33/` e
`data/staging/concorrentes_mapeados.parquet`. Nada foi escrito; todas as medições são leitura.

## Q1 — Os números do backlog ainda batem? **SIM, todos, ao dígito.**

Medido com o código real (`coordenadas_por_chave`, `ler_snapshots`, `ler_concorrentes`), não com
fixtures:

| Afirmação do backlog | Medido hoje | Bate? |
|---|---|---|
| 22.173 linhas no snapshot `2026-33` | **22.173** (feed e snapshot, idênticos) | sim |
| 19.329 independentes + 2.844 de rede | **19.329 / 2.844** | sim |
| 83 redes distintas | **83** | sim |
| 1.134 unidades de rede (39,9%) sem ponto de cadeia a <150 m | **1.134 (39,9%)** | sim |
| 1.665 / 2.844 (58,5%) casam com pin do funil da MESMA rede | **1.665 (58,5%)** | sim |
| 1.167 não casam apesar de a rede existir no funil | **1.167** (+ 12 em redes ausentes do funil) | sim |
| redes com casamento zero: `performance` 0/88, `one` 0/29, `contorno_do_corpo` 1/61, `power_fit` 5/76, `selfit` 69/202 | **idênticos** | sim |

Extras medidos, que o backlog não tem:
- Só há a fonte **`wellhub`** no feed (TotalPass vazio nesta estação): 22.173 de 22.173.
- Concentração: `panobianco` 440, `skyfit` 350, `bluefit` 219, `selfit` 202, `pratique` 165 — o top-5
  é 1.376 de 2.844 (**48,4%**), exatamente a concentração que o backlog usa para recusar o S3 nas
  redes.
- `concorrentes_mapeados.parquet`: 4.499 linhas, **4.366 válidas** (93 `descartado_duplicado`, 40
  `descartado_coord`), 104 redes. A oferta usa só as válidas (`_pontos_validos`).
- **Sensibilidade do limiar de dedup** (unidades de rede sem ponto de cadeia próximo):
  **50 m → 1.418 (49,9%)** · **150 m → 1.134 (39,9%)** · **300 m → 834 (29,3%)**.

## Q2 — Onde exatamente o universo é travado?

| # | Arquivo:linha | O que faz | Compartilhado com o S1? |
|---|---|---|---|
| 1 | `presenca_agregador.py:141-153` — `_filtrar_universo_sinal_1` | `fonte ∈ FONTES_AGREGADORES` **e** `rede == "independente"`. É a definição única do universo. | **SIM — é o próprio predicado do S1.** Afrouxar aqui faz `n_academias_independentes_totalpass`/`_wellhub` contarem redes. |
| 2 | `presenca_agregador.py:338` | aplica (1) dentro de `extrair_presenca_agregador`, depois da redução (P2). | SIM |
| 3 | `score.py:170-177` — `_preparar_universo` | chama (1) sobre o frame de churn. **Trava de ENTRADA do score.** | SIM (é o mesmo objeto; `test_score.py:1026` assere identidade `is`) |
| 4 | `score.py:497-501` | `_assert_schema_score`: `fonte` fora dos agregadores → `ValueError`. **Trava de SAÍDA.** | não (é do score) |
| 5 | `score.py:502-504` | `_assert_schema_score`: `rede != "independente"` → `ValueError`. **Trava de SAÍDA.** | não |
| 6 | `score.py:276` — `_juntar_pressao` | `merge(..., how="left")` no universo já filtrado: as linhas de pressão de unidades de rede **existem e são descartadas aqui** (o docstring assume isso: "sobram linhas de pressão sem par à esquerda — esperado"). | não |
| 7 | `alvos_nomeados.py:98-101,132-138` | o **score é o lado que sobrevive** no join `one_to_one`; academia do feed sem score não entra ("pode ser cadeia, que o universo de M&A exclui de propósito"). `rede` fica fora do artefato por ser constante (linhas 51-53). | não |
| 8 | `web/server/app.py:98-113` + `_pins_independentes` (≈437-500) | o piloto lê só o artefato nomeado; o comentário declara que a interseção com os pins de cadeia é **vazia por construção**. | não |
| 9 | testes | `test_score.py:991` (`test_cadeia_nunca_entra_no_score`), `:1012`, `:1019`, `:1026`; `test_presenca_agregador.py:204,213`; `tests/unit/test_piloto_web_independentes.py:139` | — |

**Consequência de desenho:** os itens 1-3 são o mesmo objeto. A metade 1 **não pode** relaxá-lo — o
caminho é um universo de EXIBIÇÃO próprio, como o backlog já recomendava, e os itens 4/5 continuam
guardando a saída do score.

**Achado que barateia a metade 1:** o S6 das 2.844 unidades de rede **já é calculado hoje** —
`_pressao_por_academia` passa o feed INTEIRO como origem para `calcular_pressao_por_academia`
(`alvos_ma.py:603`), e o número só é jogado fora no join do item 6. A metade 1 não precisa de
matemática nova; precisa de universo, artefato, superfície e DEC.

## Q3 — A metade 2 realmente não muda universo? **SIM, são funções e frames separados.**

| | universo do SCORE | universo da OFERTA do S6 |
|---|---|---|
| onde | `presenca_agregador.py:141` (`_filtrar_universo_sinal_1`), chamado por `score.py:177` | `alvos_ma.py:595-601` (`_pressao_por_academia`), predicado inline `academias["rede"] == CATEGORIA_INDEPENDENTE` |
| sobre qual frame | frame de **churn** (série de snapshots) | frame de **feed cru** (`coordenadas_por_chave`) |
| o que decide | quem recebe score de M&A | quem conta como concorrência |
| trava de saída | `score.py:497-504` | `_assert_universo_e_decomposicao` (`pressao_competitiva.py:557`) |

São **duas funções distintas, em módulos distintos, sobre frames distintos**. Acrescentar as
unidades de rede ao conjunto de oferta é uma **terceira lista de pontos**, aditiva: não passa perto
de `_filtrar_universo_sinal_1` nem dos asserts do score. **A metade 2 continua barata.**

Ressalva registrada: o predicado da oferta e o do score codificam a MESMA definição de
"independente" (`CATEGORIA_INDEPENDENTE`), então há duas escritas da mesma ideia — mas em papéis
opostos (uma seleciona alvos, a outra seleciona concorrência). Não unificar.

## Q4 — `dedup_independentes` serve? **Parcialmente. Falta o quê, exatamente:**

O backlog está certo. Lendo `pressao_competitiva.py:311-397`:

1. **Só colapsa entre FONTES DIFERENTES** (`if fontes[j] == fontes[i]: continue`, linha 368). Para
   casar feed-de-rede com parquet-de-cadeia é preciso que os dois lados tenham valores de `fonte`
   distintos — funciona **se** o chamador rotular os pontos do parquet com uma `fonte` sintética.
2. **Exige as colunas `fonte`, `chave_snapshot`, `lat`, `lng`** (linha 335). O parquet de cadeias tem
   `concorrente_id`, `rede`, `nome_unidade`, `lat`, `lng`, ... — **não tem nenhuma das duas
   primeiras**. É preciso adaptar (`fonte="concorrentes_mapeados"`, `chave_snapshot=concorrente_id`).
3. **Devolve UM conjunto de pontos com UM peso.** O `_oferta_por_origem` tem dois blocos com dois
   pesos (cadeias `1.0`, independentes `0.5`). As unidades de rede do feed pesam `1.0` → o lugar
   natural delas é **concatenadas ao bloco de cadeias**, não ao de independentes. A dedup passa a ser
   cadeia-contra-cadeia, entre fontes — caso que a função aceita, mas cujo NOME não descreve
   (`dedup_independentes`). Renomear/generalizar para `dedup_entre_fontes` é a mudança limpa.
4. **O limiar é outro.** `DEDUP_INDEPENDENTES_M = 50` foi arbitrado para o par TP×WH (mesmo app,
   mesma geocodificação). Aqui o par é "site da rede" × "app do WellHub", que geocodificam
   diferente — e a diferença é material (Q1: 1.418 contra 1.134 contra 834). **Decisão de gate (D5).**
5. **A auto-exclusão (`auto_pos`) só cobre o bloco de independentes** (linhas 281-290). Se as
   unidades de rede entrarem no bloco de cadeias sem exclusão própria, cada unidade de rede como
   origem soma `peso(d=0) × 1,0 = 1,0` → **`sat(1,0) = 50,0` pontos de pressão fantasma**. Hoje isso
   é invisível (o score descarta as linhas de rede), mas a metade 1 tornaria visível. **D6.**
6. O que **serve como está**: o bucket H3 (`DEDUP_H3_RES = 11`) e o determinismo do sobrevivente
   ("primeiro em ordem `(fonte, chave_snapshot)`"), que valem igual no caso novo.

## Q5 — Carimbos e bumps de série

**Contagens MEDIDAS no código (não na prosa), importando `contrato.py`:**

| Contrato | Colunas | Versão |
|---|---|---|
| `CONTRATO_COLUNAS_SCORE` | **26** | `score_vulnerabilidade_v5` |
| `CONTRATO_COLUNAS_PRESSAO_ACADEMIA` | 13 | `pressao_competitiva_v2` |
| `CONTRATO_COLUNAS_PRESSAO` (hex) | 12 | `pressao_competitiva_v2` |
| `CONTRATO_COLUNAS_ALVOS_MA` | 18 | `alvos_ma_v2` |
| `CONTRATO_COLUNAS_ALVOS_NOMEADOS` | **23** | `alvos_ma_nomeados_v3` |
| `CONTRATO_COLUNAS_SNAPSHOT` | 12 | `snapshots_concorrentes_v3` |
| `CONTRATO_COLUNAS_CHURN` | 19 | `churn_staleness_v2` |
| `CONTRATO_COLUNAS_PRESENCA_AGREGADOR` | 10 | `presenca_agregador_v1` |

**Os dois números do backlog estão certos e falam de artefatos diferentes:** 26 é o **score**
(`score_vulnerabilidade_v5`, pós-MA-16) e 23 é o **artefato nomeado** (`alvos_ma_nomeados_v3`,
pós-MA-18). Não há contradição.

**A metade 2 exige bump?** **Recomendo que SIM** — mas é decisão de gate (D4). O precedente do
projeto é bumpar por quebra **semântica**, não só de schema: a DEC-025 bumpou
`snapshots_concorrentes_v1 → v2` por mudança de vocabulário, "com quebra de comparabilidade
declarada". Aqui a quebra é medida: **Spearman 0,991157** (a DEC-030 tinha `1,000000`), **10,9% das
academias mudam de faixa de 10 pontos**. Sem bump, dois parquets com o mesmo
`versao_contrato = pressao_competitiva_v2` e o mesmo `universo_oferta = cadeias_e_independentes`
teriam números diferentes — e essa é exatamente a situação que os carimbos existem para impedir.

**Carimbo:** o enum `UNIVERSOS_OFERTA` responde *"quem conta como concorrência"* por CATEGORIA
(cadeia/independente). A metade 2 não cria categoria nova — ela **melhora a cobertura da categoria
cadeia**. Recomendação: **manter os dois valores do enum**, bumpar
`pressao_competitiva_v2 → v3` e `score_vulnerabilidade_v5 → v6`, e acrescentar **decomposição de
auditoria** (ex.: `n_cadeias_do_feed_no_raio` / `oferta_cadeias_do_feed`) para o
`_assert_universo_e_decomposicao` continuar podendo provar que o carimbo não mente. Alternativa a
registrar no gate: um terceiro valor de enum. **D4.**

## Q6 — Baseline de testes, MEDIDA agora

```
python -m pytest --collect-only -q   ->   3184 tests collected in 235.75s
```

**3.184 testes coletados** (serial; `-n auto` continua quebrado neste ambiente — xdist 3.8.0,
`WinError 6`). Zero erros de coleta. Números de ciclos antigos (2311 no BLK-MA-04, 2006 no CLAUDE.md
§5) são **históricos e não servem de tripwire**.

## Q7 — Colisão de DEC (P0-2): **confirmada. O primeiro número livre é DEC-033.**

- **`docs/decisions/DEC-030.md` local** (`ciclo/BLK-MA-17`): *"As independentes entram na oferta do
  sinal 6"* (BLK-MA-16, 2026-08-14).
- **`docs/decisions/DEC-030.md` em `origin/main`**: *"A Conclusão do Relatório Pontual passa a ter
  DOIS selos"* (2026-08-14). O próprio arquivo avisa: *"nasceu como DEC-029 e foi renumerada antes
  do merge — conferir na abertura do PR se 030 continua livre"*.
- `origin/main` também tem **DEC-031** (régua do percentil de renda setorial, Crítica) e **DEC-032**
  (`k` nacional único, Crítica).
- **DEC-027, DEC-028 e DEC-029 NÃO existem em `origin/main`** — são locais, da pilha do épico BLK-MA.

Portanto: **033 é o primeiro número livre**, e a DEC-030 local terá de ser renumerada antes de
qualquer merge (arrastando `docs/decisions/README.md`, `CLAUDE.md` §8, as citações em
`docs/vulnerabilidade_ma_contrato.md`, `contrato.py`, `pressao_competitiva.py`, `alvos_ma.py` e nos
testes). **Isto vai ao gate (D3), não se decide aqui.**

Achado lateral: o `docs/decisions/README.md` de `origin/main` **para na DEC-026** — as 030/031/032 de
lá nunca entraram no índice. Reconciliar o índice é trabalho de bookkeeping, não deste bloco, mas
quem renumerar precisa saber.

---

# Medição própria: qual é o tamanho da metade 2

Rodada com o código real, nacionalmente, sobre as 19.329 independentes (universo
`cadeias_e_independentes`, grão academia), acrescentando à oferta as **1.134** unidades de rede sem
ponto de cadeia a <150 m, com peso de cadeia `1,0`:

| Métrica | Antes | Depois |
|---|---|---|
| pressão média | 61,415 | **62,767** |
| pressão `0` | 1.068 (5,5%) | 1.026 (5,3%) |
| academias com pressão alterada | — | **7.176 (37,1%)** |
| delta médio / p90 / máximo | — | **+1,352 / +4,019 / +52,879** |
| mudam de faixa de 10 pontos | — | **2.116 (10,9%)** |
| Spearman antes × depois | — | **0,991157** |

Leitura, em duas frases:
1. **A ordem muda.** A DEC-030 pôde dizer "não embaralha o ranking" (`Spearman = 1,000000`); esta não
   pode. `0,991157` sobre 19.329 linhas reordena a shortlist.
2. **O efeito é concentrado, não difuso.** Média `+1,35`, mas máximo `+52,88` — e no regime real
   (`{s1,s6}`, onde o score é `30 + 40·v6`) isso é **+0,54 ponto de score em média e até +21,2
   pontos** na academia mais afetada.

O falso zero quase não se move (5,5% → 5,3%): as unidades de rede invisíveis estão majoritariamente
perto de quem já tinha pressão. **O bloco corrige magnitude, não cobertura** — vender o contrário
seria repetir o erro que a DEC-030 corrigiu.

---

# Decisões que sobem ao GATE HUMANO

> Nenhuma delas é do agente. O Planner deve parar aqui.

**D1 — Escopo do ciclo: as duas metades, ou só a metade 2?**
*Recomendação: **só a metade 2**.* Ela corrige um defeito medido (37,1% do universo), não depende de
DEC de universo, e vive inteira em `src/motor_expansao/vulnerabilidade/` — enquanto a metade 1 mexe
em `web/server/app.py`, que `origin/main` está reescrevendo em 16 commits não mergeados (P0-3).

**D2 — A metade 2 exige DEC própria?**
*Recomendação: **SIM**, uma DEC que emenda a DEC-030 (a local, de MA-16).* O backlog diz que ela "não
muda universo" — verdade quanto ao universo do SCORE (Q3), mas ela muda **quem conta como oferta**,
que é literalmente o objeto da DEC-030, e desloca o score de 37,1% das linhas **reordenando**
(Spearman 0,991157). Sem DEC, a régua muda sem registro.

**D3 — Numeração da DEC.**
*Recomendação: **DEC-033**, e renumerar a DEC-030 local antes do merge.* Medido em Q7: `origin/main`
já ocupa 030/031/032 com outros conteúdos. **Decisão humana obrigatória** — envolve reescrever
citações em 6+ arquivos e no `CLAUDE.md` §8.

**D4 — Carimbo e bump de série.**
*Recomendação: manter os dois valores de `UNIVERSOS_OFERTA`, **bumpar `pressao_competitiva_v2 → v3`
e `score_vulnerabilidade_v5 → v6`**, e acrescentar decomposição de auditoria da oferta de cadeia.*
O enum classifica CATEGORIA (que não muda); o que muda é cobertura, e é a versão que distingue
rodadas. Alternativa a considerar: terceiro valor de enum (mais explícito, mais caro — toca todos os
asserts e a CLI).

**D5 — Limiar da dedup contra `concorrentes_mapeados`.**
*Recomendação: **150 m**, como constante própria (`DEDUP_CADEIA_FEED_M`), não reusar os 50 m de
`DEDUP_INDEPENDENTES_M`.* Os 50 m foram arbitrados para TP×WH (mesma geocodificação); aqui os feeds
são de origens diferentes. Sensibilidade medida: **50 m → 1.418 · 150 m → 1.134 · 300 m → 834**
unidades entram. O erro é assimétrico nas duas direções e a escolha precisa ficar registrada.

**D6 — Auto-exclusão no lado cadeia.**
*Recomendação: **fazer agora, dentro da metade 2**.* Sem ela, uma unidade de rede como origem soma
`sat(1,0) = 50` pontos de pressão de si mesma. Hoje é invisível (o join do score descarta essas
linhas); com a metade 1 vira erro de 50 pontos na tela. Custo baixo agora, alto depois.

**D7 — A auditoria do tooltip (BLK-MA-18) depois da metade 2.**
*Recomendação: decompor a contagem no artefato nomeado (`n_conc` separando "desenhado no mapa" de
"contado e não desenhado"), OU declarar a limitação em texto.* Hoje o tooltip promete conferência
visual, e as 1.134 unidades novas não têm pin em lugar nenhum. É o argumento mais forte a favor de
entregar a metade 1 junto — se o gate quiser as duas, este é o motivo técnico.

**D8 — (só se a metade 1 entrar) O que é propagado às unidades de rede, e a precedência de pin.**
*Recomendação: **fatos + S6, sem `score_vulnerabilidade`** (proposta do backlog: S1 e S3 medem outra
coisa numa rede — a negociação com o agregador é centralizada, e 440 unidades da Panobianco virariam
`sumiu_recente` no mesmo dia). Precedência: **o pin do funil vence** quando há casamento da mesma
rede a <150 m (1.665 casos); os 1.179 restantes ganham pin próprio a partir da coordenada do feed.*
Vantagem colateral medida (Q2): o S6 dessas unidades **já é calculado hoje** e descartado no join —
a metade 1 não precisa de matemática nova.
