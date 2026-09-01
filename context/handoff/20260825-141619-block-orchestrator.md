# Handoff — Block Orchestrator

> Gerado em 2026-08-25, na branch `ciclo/BLK-MA-21`. Cópia append-only em
> `context/handoff/20260825-141619-block-orchestrator.md`.

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
**BLK-MA-21 — Cron MENSAL dos agregadores (WellHub + TotalPass): liga o relógio dos independentes.**
Entrega, numa ÚNICA entrega, a curadoria de diretórios (bloqueador 2), o wrapper de cron mensal, a
resolução da colisão de partição do snapshot (opção `a`: `semana=X/fonte=Y`), uma retenção que sirva
às duas cadências, o carimbo de `fontes_lidas` no parquet e o check de idade no healthcheck. O
bloqueador (1) — caixa `Totalpass`/`TotalPass` no repo do coletor — já caiu (`GymScraping` PR #11,
`6311cb9`).

## Objetivo
Deixar o cron mensal dos agregadores pronto para ser agendado na VPS (passo manual do Felipe), sem
que ligar o caminho de leitura correto (bloqueador 2) ative, sem defesa, a colisão de partição que
hoje é mascarada por um frame vazio inofensivo.

## Escopo permitido

Mapeamento dos 6 itens do backlog para artefatos concretos deste repo — todos são **código/teste
neste repo**, não curadoria manual nem runbook solto:

1. **Curadoria V2 versionada** (script novo, localização a decidir pelo Planner — ex.:
   `scripts/curadoria_agregadores.sh`/`.py` ou função em
   `src/motor_expansao/vulnerabilidade/`). Fonte e destino, verificados de primeira mão:
   - **WellHub:** copiar de `Wellhub/csvs_musculacao/*.csv` (repo `GymScraping`) — **não** de
     `Wellhub/csvs/*.csv`, que hoje é o universo SEM filtro (ver achado abaixo) — para
     `concorrentes/wellhub/csvs/` (minúsculo; é `DIR_WELLHUB_DEFAULT` em
     `src/motor_expansao/vulnerabilidade/snapshots.py:87`).
   - **TotalPass:** copiar de `TotalPass/csvs/*.csv` (já sai filtrado por musculação no próprio
     coletor — `TotalPass/coletor_totalpass.py:138-140`, filtro hardcoded, sem flag para desligar,
     vocabulário V2 igual ao WellHub) para `concorrentes/totalpass/csvs/` (minúsculo;
     `DIR_TOTALPASS_DEFAULT`, mesma linha do arquivo acima).
   - Nenhum script deste tipo existe hoje em nenhum dos dois repos (`grep -rn "csvs_musculacao\|
     curadoria" tasks/backlog.md tasks/completed.md docs/` só acha prosa/DECs, nunca código; e
     `grep -rli "wellhub\|totalpass\|musculacao" GymScraping/scripts` = 0 arquivo).
2. **Wrapper `run_snapshot_agregadores.sh`** — código neste repo, mesmo molde do
   `scripts/cron/run_snapshot_concorrentes.sh` já existente (precedente do semanal, lido por
   inteiro): `--dir-wellhub`/`--dir-totalpass` explícitos, `flock -n`, `--retencao-semanas`,
   `DRY_RUN=1` obrigatório antes de agendar. Invoca o MESMO `python -m
   motor_expansao.vulnerabilidade.snapshots --fontes totalpass wellhub` (já é a forma prevista pelo
   comentário em `snapshots.py:1042-1044` e por `docs/infra_producao.md:263-264`).
3. **Resolver a colisão** (opção `a`) em `src/motor_expansao/vulnerabilidade/snapshots.py`:
   `escrever_particao_semana` (linhas 740-797, hoje particiona só por `semana`),
   `_schema_arrow_snapshot` (814-819) e `ler_snapshots` (832-869, hoje só declara
   `partitioning=ds.partitioning(pa.schema([("semana", pa.string())]), flavor="hive")`). Teste que
   prove que `unidades` e `wellhub` coexistem na mesma semana **e** teste que trave um leitor com
   particionamento de 1 chave contra devolver `fonte = None` em silêncio (o risco que a DEC-026 já
   combateu com `schema=` explícito).
4. **Nova retenção** — `RETENCAO_SEMANAS = 26` em `src/motor_expansao/vulnerabilidade/contrato.py:51`
   e `podar_snapshots` em `snapshots.py:872-906` (hoje keep-newest-N sobre filhos DIRETOS
   `semana=AAAA-SS`; com a opção `a` os filhos diretos continuam sendo `semana=X`, mas cada um pode
   ter 1 ou 2 folhas de `fonte` dentro — a aritmética "26 semanas = 26 observações do agregador" só
   vale se a poda também mudar de "por partição" para "por fonte dentro da partição", ou se aceitar
   que uma folha de `fonte` fique presa à retenção da outra).
5. **Carimbar `fontes_lidas`** — hoje só existe no dict de auditoria retornado por `materializar`/
   `executar` (`snapshots.py:944-951`), nunca no parquet. Decisão de forma: coluna nova no contrato
   de 12 colunas (`CONTRATO_COLUNAS_SNAPSHOT`, `contrato.py`, bump de
   `VERSAO_CONTRATO_SNAPSHOT = "snapshots_concorrentes_v3"`) vs. inferir a partir da própria folha
   `fonte=Y` que a opção (a) já cria (mas isso responde "que fontes esta PARTIÇÃO tem", não "que
   fontes esta EXECUÇÃO tentou ler" — a auditoria de execução continua sendo outra coisa).
6. **Check de idade no `scripts/healthcheck_vps.sh`** — hoje `check_coleta()` (linhas 144-165) só
   confere se existe um `relatorio_crescimento_*.txt` de HOJE (cron semanal); não sabe nada sobre
   `snapshots_concorrentes`. Precisa de lógica nova (subcomando ou extensão de `check_coleta`) que
   confira a idade da partição/folha mais recente de `fonte=wellhub`/`fonte=totalpass`.

**A inversão a respeitar (crítica para o Planner sequenciar o PR):** item 1 (curadoria) e item 3
(colisão) têm de sair na MESMA entrega. Hoje, com o caminho errado, `ler_feeds` devolve zero linhas,
`materializar` produz frame vazio e `escrever_particao_semana` sai cedo em WARNING **sem apagar nada**
(`snapshots.py:750-766`, confirmado lendo o código: a checagem `if df.empty` vem antes de qualquer
`mkdir`/`write_dataset`). Corrigir só o caminho (item 1) sem corrigir a colisão (item 3) faz o mensal
passar a gravar de verdade — e `existing_data_behavior="delete_matching"` (linha 795) apaga a
partição inteira da semana toda vez que o semanal (`--fontes unidades`) reescrever aquele domingo,
destruindo ~21h de coleta com `exit 0` nos dois runs.

## Fora de escopo

- **TotalPass como FONTE do score** — BLK-MA-20 (grão do S1, dedup calibrada com par real, DEC de
  bump do score). Este bloco só GRAVA a partição; não decide se/como o extrator passa a consumi-la.
  Mas a fronteira PRECISA estar escrita na DEC deste bloco (ver GATE, pergunta G5) — o próprio
  BLK-MA-20 confirma que a cadeia `ler_feeds → ... → calcular_score_vulnerabilidade` roda com as duas
  fontes **sem editar uma linha de código**, então gravar a partição sozinho já muda o que o score
  consome, mesmo sem nenhum PR do BLK-MA-20.
- Pesos do D4 (congelados); qualquer artefato/score/peso oficial do M1.
- Integração dos agregadores ao residual (parte 3 da DEC-013) — epic futura, fora daqui.
- Mudanças no repositório `GymScraping` (`../GymScraping`, fora deste repo). Achados sobre ele
  (abaixo) são NOTA para o Planner/gate, não trabalho a executar aqui.
- Qualquer comando na VPS, por qualquer via (MCP `ssh-vps-ultra`, `ssh`, `scp`) — guardrail §6,
  reafirmado pelo critério de aceite (8) do bloco.

## Arquivos que devem ser lidos

- `src/motor_expansao/vulnerabilidade/snapshots.py` (módulo inteiro — já lido e verificado nesta
  passagem).
- `src/motor_expansao/vulnerabilidade/contrato.py` (`RETENCAO_SEMANAS`, `STALE_SEMANAS`,
  `VERSAO_CONTRATO_SNAPSHOT`, `CONTRATO_COLUNAS_SNAPSHOT`, `FONTES_VALIDAS`).
- `src/motor_expansao/vulnerabilidade/churn_staleness.py` (consumidor da série; `MIN_SEMANAS`/
  `STALE_SEMANAS`).
- `scripts/cron/run_snapshot_concorrentes.sh` (molde direto do wrapper mensal).
- `scripts/healthcheck_vps.sh` (função `check_coleta`, linhas 144-165, e o padrão `report`/
  `send_telegram` a reusar).
- `docs/infra_producao.md` (linhas ~145-330: seção do GymScraping, "Pendentes (futuro)" e o runbook
  completo do snapshot semanal — molde de prosa para a seção mensal).
- `docs/decisions/DEC-013.md`, `DEC-026.md` (precedentes: automação recorrente + `schema=` explícito
  contra coluna nula silenciosa).
- `tasks/backlog.md` — blocos BLK-MA-21 (linha 1850), BLK-MA-06 (linha 1539) e BLK-MA-20
  (linha 1715), lidos por inteiro nesta passagem.
- No repo irmão `../GymScraping` (READ-ONLY, fora do escopo de escrita): `Wellhub/coletor_wellhub.py`,
  `Wellhub/split_by_state.py`, `Wellhub/MIGRACAO_NOTA.md`, `TotalPass/coletor_totalpass.py`,
  `TotalPass/extracao.py` — todos já lidos/grepados nesta passagem (ver achados abaixo).

## Arquivos que podem ser alterados

- `src/motor_expansao/vulnerabilidade/snapshots.py`
- `src/motor_expansao/vulnerabilidade/contrato.py`
- `scripts/cron/run_snapshot_agregadores.sh` (novo)
- Script/módulo novo de curadoria (caminho a decidir pelo Planner)
- `scripts/healthcheck_vps.sh`
- `docs/infra_producao.md` (seção "Pendentes (futuro)" → runbook mensal real)
- `tests/unit/vulnerabilidade/test_snapshots.py` (ou equivalente — testes novos/alterados)
- `docs/decisions/DEC-0XX.md` (nova DEC deste bloco, criada no GATE)
- `tasks/backlog.md`, `tasks/completed.md` (bookkeeping, passo do orquestrador — não do Builder)

**Fora de alcance de escrita, em qualquer hipótese:** `config.py`, `src/motor_expansao/pipelines/m1/`,
`normalizar_concorrentes.py`, `calcular_colunas_mercado.py`, artefatos oficiais do M1, `graphify-out/*`,
`PRD.md`, `context/handoff.md` (fora deste próprio handoff), `tasks/current_task.md`.

## Achados do orquestrador (verificados de primeira mão — mudam o plano)

1. **Todas as afirmações técnicas do bloco sobre este repo CONFEREM**, lidas linha a linha:
   `existing_data_behavior="delete_matching"` (`snapshots.py:795`); a saída antecipada em frame vazio
   SEM apagar partição (`:750-766`); `RETENCAO_SEMANAS = 26` (`contrato.py:51`); `STALE_SEMANAS = 12`;
   `VERSAO_CONTRATO_SNAPSHOT = "snapshots_concorrentes_v3"`; `_assert_schema_snapshot` levanta em
   schema fora do contrato; e `ds.dataset(...)` sobre a SÉRIE de snapshots aparece só em
   `ler_snapshots` — os outros 3 usos de `ds.dataset` no pacote (`api/service.py`, `dashboard/data.py`,
   `pipelines/m1/fase1_bi_exports.py`) leem datasets DIFERENTES (mercado/dashboard enriquecido), não a
   série de concorrentes.
2. **O bloqueador (2), localizado com precisão.** O motor lê (default)
   `DIR_WELLHUB_DEFAULT = Path("concorrentes/wellhub/csvs")` e
   `DIR_TOTALPASS_DEFAULT = Path("concorrentes/totalpass/csvs")` (`snapshots.py:86-87`), caminhos
   relativos ao mount `HOST_CONCORRENTES:/app/concorrentes:ro` do wrapper (default
   `HOST_CONCORRENTES=/opt/gymscraping`, `run_snapshot_concorrentes.sh:69`). No repo do coletor
   (verificado localmente em `../GymScraping`), os diretórios reais na RAIZ do repo são
   `Wellhub/csvs/` e `TotalPass/csvs/` (maiúsculo) — não `wellhub/`/`totalpass/` sob um subdiretório
   `concorrentes/`. Ou seja, o descasamento não é só de CAIXA: é caixa + AUSÊNCIA do prefixo
   `concorrentes/` no layout do coletor. A curadoria (item 1) precisa criar a árvore
   `concorrentes/{wellhub,totalpass}/csvs/` do zero (local e, depois, na VPS), não só renomear.
3. **ACHADO NOVO, não coberto pelo texto do backlog: a fonte certa de WellHub para a curadoria NÃO é
   `Wellhub/csvs/`, e a diferença é grande.** Medido de primeira mão: `Wellhub/csvs/
   unidades_wellhub_sp.csv` tem 16.432 linhas; `Wellhub/csvs_musculacao/
   unidades_wellhub_sp_musculacao.csv` tem 6.850. `Wellhub/MIGRACAO_NOTA.md` explica por quê: a
   rodada de 2026-08-05/06 rodou com `--no-musculacao-filter` (grava TUDO) porque o WellHub tinha
   acabado de renomear a taxonomia e o filtro antigo estava perdendo unidade real; a DEC-025
   consertou o vocabulário (`TERMOS_MUSCULACAO` em `Wellhub/split_by_state.py`, travado por
   `test_vocabulario_congelado`) e regenerou **só** `Wellhub/csvs_musculacao/` com o critério V2
   (22.173 linhas nacionais, por essa nota). **Ou seja, hoje `Wellhub/csvs/` = universo SEM filtro de
   musculação, e `Wellhub/csvs_musculacao/` = universo V2 correto** — usar o primeiro por engano
   dobra (ou mais) o universo WellHub com academias fora do critério de negócio aprovado.
   **Fragilidade a declarar no GATE:** se uma coleta FUTURA do WellHub rodar em modo DEFAULT (sem
   `--no-musculacao-filter`), o próprio código do coletor (`coletor_wellhub.py:208-216`) passa a
   NÃO gerar `csvs_musculacao/` por considerá-lo redundante (porque `csvs/` já sairia filtrado nesse
   modo) — nesse cenário a curadoria teria de ler `csvs/`, não `csvs_musculacao/`. Um script de
   curadoria que hardcode um único diretório-fonte fica frágil a essa mudança de modo; o `DRY_RUN`
   do wrapper (item 2) precisa expor a contagem (`linhas_snapshot`) para o operador notar se o
   universo saiu maior do que o esperado, do mesmo jeito que pegou o bloqueador (2) original.
   **TotalPass não tem esse problema**: o filtro V2 (`tem_musculacao`, mesmo vocabulário do WellHub)
   está HARDCODED no coletor (`TotalPass/coletor_totalpass.py:138-140`, sem flag para desligar), então
   `TotalPass/csvs/*.csv` é sempre a fonte certa.
4. **`check_coleta` do healthcheck confirmado cego a agregadores.** Só compara
   `relatorio_crescimento_*.txt` de hoje contra a data corrente; não existe verificação nenhuma sobre
   `snapshots_concorrentes/`.
5. **Nenhum script de curadoria existe em nenhum dos dois repos.** Confirma o texto do bloco ("hoje
   não existe em script nenhum"): item 1 é código 100% novo.

## Critérios de aceite (mapeados aos 8 do backlog)

1. Bloqueador (2) resolvido — curadoria versionada (item 1) copia da fonte CERTA por agregador (ver
   achado 3): `Wellhub/csvs_musculacao/` para WellHub, `TotalPass/csvs/` para TotalPass.
2. Colisão resolvida pela opção (a) em `snapshots.py`, com teste de coexistência de 2 fontes na
   mesma semana **e** teste que trave dataset de 1 chave devolvendo `fonte=None` em silêncio.
3. Retenção nova com a aritmética das duas cadências (semanal vs. mensal) declarada por escrito na
   DEC.
4. `fontes_lidas` carimbado no parquet (não só na auditoria impressa).
5. `DRY_RUN` como passo obrigatório do runbook (`docs/infra_producao.md`), no mesmo padrão do
   BLK-MA-06.
6. Check de idade da partição de agregador em `scripts/healthcheck_vps.sh`.
7. Fronteira com o BLK-MA-20 escrita na DEC deste bloco — explicitamente, porque gravar a partição já
   muda o que o score consome sem nenhum código do MA-20 (achado do próprio backlog, confirmado no
   código: `snapshots.py`/`presenca_agregador.py` não filtram por fonte antes de alimentar o score).
8. READ-ONLY sobre o M1; suíte verde; `loop_guard` sem CRÍTICO; **nenhum comando executado na VPS por
   agente, em nenhuma etapa** deste ciclo.

## Criticidade classificada
**Alta.** Não é Crítica pelo guardrail deste orquestrador: o bloco não toca `score_priorizacao`,
`hex_score_estrutural`, carteira, plano curto prazo, plano de domínio nem nenhum artefato oficial do
M1 — escreve só em `data/staging/snapshots_concorrentes/` (READ-ONLY sobre o M1, confirmado lendo o
código). É Alta porque cria um cron de produção na VPS, invoca o único módulo do pacote que apaga
arquivo em disco (poda de retenção) e exige DEC própria antes do Builder — mantém a pré-classificação
do backlog.

## Esteira recomendada
Block Orchestrator (concluído) → **Planner** → `[GATE humano — DEC própria]` → Builder → QA →
`[aplicação na VPS: passo MANUAL, comando a comando — §6, do Felipe]`.

## Riscos identificados

- **A inversão de ordem** (ver Escopo permitido): item 1 sem item 3 na mesma entrega ativa a colisão
  de partição e destrói ~21h de coleta com `exit 0` — falha SILENCIOSA, sem sinal de erro no cron.
- **Fonte de curadoria frágil a mudança de modo do coletor WellHub** (achado 3) — um script que
  hardcode `csvs_musculacao/` sem checagem de plausibilidade fica quebrado no dia em que a coleta
  upstream mudar de modo (default vs. `--no-musculacao-filter`), com sintoma silencioso (universo
  maior que o esperado, não erro).
- **TotalPass "entra pela porta dos fundos" no score.** O BLK-MA-20 mediu que a cadeia inteira roda
  com as duas fontes sem editar uma linha — gravar a partição mensal, sozinha, já muda o que
  `calcular_score_vulnerabilidade` consome. A DEC deste bloco precisa declarar a fronteira
  explicitamente (não é suficiente dizer "fora de escopo" em prosa se o código não impõe nada).
- **Retenção de 2 níveis mal especificada** pode fazer "26 semanas" deixar de significar "26
  observações do agregador" assim que a partição virar `semana=X/fonte=Y` — a aritmética precisa ser
  declarada por fonte, não só por partição.
- **Sequencial vs. paralelo dos dois coletores** (WellHub ~20h03, TotalPass ~1h40, medidos) muda o
  desenho do wrapper e a exposição da VPS (KVM4, 6 containers permanentes) a duas sessões HTTP
  concorrentes na mesma janela — decisão de produto, não só de engenharia.
- **Espaço em disco real da VPS e grade horária do cron não foram medidos** — o guardrail §6 proíbe
  comando na VPS sem confirmação explícita, então isso só pode ser conferido pelo Felipe.

## Perguntas fechadas para o GATE humano (o Planner formaliza como D1..Dn)

- **G1 — Cadência exata.** Dia do mês e horário do cron mensal, dado que a janela sequencial mede
  ~21h45 e a VPS roda 6 containers permanentes.
- **G2 — Sequencial vs. paralelo** dos dois coletores (WellHub 20h03 + TotalPass 1h40 medidos):
  paralelo encurta a janela para ~20h mas duplica a carga HTTP simultânea na mesma vCPU.
- **G3 — Fonte de curadoria por agregador e robustez a mudança de modo.** Confirmar o par
  `Wellhub/csvs_musculacao/` + `TotalPass/csvs/` (achado 3) como contrato do script, e decidir se o
  `DRY_RUN` precisa de um limiar de plausibilidade de `linhas_snapshot` (ex.: WellHub muito acima do
  esperado ⇒ abortar) para pegar a fragilidade descrita.
- **G4 — Novo valor de retenção**: constante simples (`≥53` ou `78` semanas, sem mudar a semântica de
  poda) vs. poda por FONTE dentro da partição de 2 níveis (correto para as duas cadências, mais
  trabalho de engenharia). Qual entra nesta entrega.
- **G5 — A fronteira com o BLK-MA-20, em texto de DEC.** Como impedir (ou deliberadamente permitir,
  com aviso) que o TotalPass comece a ser consumido pelo score assim que a primeira partição mensal
  for gravada, antes do BLK-MA-20 decidir grão do S1 e calibrar a dedup. Opções a levar ao Felipe:
  (a) a DEC autoriza a gravação mas proíbe por escrito qualquer leitura do `score.py` sobre a fonte
  `totalpass` até o BLK-MA-20 fechar; (b) o wrapper agenda só `--fontes wellhub` no início e
  `--fontes totalpass` entra depois, manualmente, quando o BLK-MA-20 aprovar; (c) outra, proposta pelo
  Planner.
- **G6 — Onde vive o script de curadoria** (item 1): módulo Python versionado neste repo (com teste)
  vs. shell script cru — e se ele precisa rodar TAMBÉM no `../GymScraping` (fora do escopo de escrita
  deste bloco, mas pode ser um passo do runbook que o Felipe executa lá antes do `scp`).

## Guardrails ativos

- **Nenhum comando na VPS por agente**, em hipótese alguma — nem MCP `ssh-vps-ultra`, nem `ssh`, nem
  `scp`. Aplicação é MANUAL, comando a comando, do Felipe (CLAUDE.md §6).
- **READ-ONLY sobre o M1** — não tocar `config.py`, `src/motor_expansao/pipelines/m1/`,
  `normalizar_concorrentes.py`, `calcular_colunas_mercado.py` nem artefato oficial.
- **Não commitar** `graphify-out/*` (worktree pré-sujo, hook post-commit regenera),
  `PRD.md`, `context/handoff.md`, `tasks/current_task.md`.
- Toda mudança relevante entra com teste; nenhum PR sobe com CI quebrado (CLAUDE.md, regra geral).
- CSV do projeto: `sep=";"`, `encoding="utf-8-sig"`; Parquet para staging.
- Acentuação correta em texto de usuário; NUNCA em identificadores/chaves/slugs (CLAUDE.md §2) — vale
  para qualquer string nova de log/runbook/DEC deste bloco.
- Bloco **NÃO é loop-safe** (cron de produção + gate humano) — não marcar `Autonomia: loop-safe` no
  backlog em nenhuma hipótese.
