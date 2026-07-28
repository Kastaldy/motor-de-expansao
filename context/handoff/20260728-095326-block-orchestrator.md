# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
**Planner** (criticidade Alta + existe uma QUESTÃO DE PROJETO EM ABERTO cuja resposta muda o recorte
A/B — ver "Evidência levantada", item 1). Depois do Planner: **aprovação humana** → Builder → QA.

## Bloco refinado
**BLK-GRAPH-02 — Tornar o grafo uma FERRAMENTA, não uma instrução (Escopo A somente).**
Hoje o grafo do graphify existe versionado na branch `graph-01` (`graphify-out/graph.json`,
`GRAPH_REPORT.md`, `.graphify_labels.json`), mas o *uso* dele não viaja com o repo: não existe
`.mcp.json`, os hooks de rebuild vivem em `.git/hooks/` (não versionados) e a regra de consultar o
grafo mora na §7 do `CLAUDE.md` ("Onde aprofundar"), que é lida como bibliografia, não como norma.
O bloco entrega três coisas: (1) `.mcp.json` versionado expondo o servidor MCP do graphify;
(2) a regra movida da §7 para a §2 (`Regras operacionais rapidas`), deixando na §7 só o detalhe
técnico; (3) hooks versionados em `.githooks/` com a limitação do `core.hooksPath` documentada.
O **Escopo B** (declarar o graphify em `pyproject.toml`/`constraints.txt`) fica **FORA deste PR**.

## Objetivo
Fazer o grafo chegar ao agente como ferramenta e como norma — sem depender de cada pessoa ler um
ponteiro na §7 e decidir obedecer.

## Escopo permitido

### A1 — `.mcp.json` versionado na raiz
- Schema (confirmado na doc oficial do Claude Code): chave raiz `mcpServers`, com
  `type: "stdio"`, `command`, `args`, `env` opcional; aceita expansão `${VAR}` / `${VAR:-default}`.
- Invocação **correta e medida** do servidor: `python -m graphify.serve <caminho-do-graph.json>`.
  O `graph_path` é **posicional** (alias `--graph`), default `graphify-out/graph.json`.
  **NÃO existe** subcomando `serve` no CLI (`python -m graphify serve` cai no fallback de ajuda e
  sai 0 sem servir nada) — a rota é o **módulo** `graphify.serve`, cujo entry point declarado é
  `graphify-mcp = graphify.serve:_main`.
- Tools realmente expostas (lidas de `serve.py`, não presumidas): `query_graph`, `get_node`,
  `get_neighbors`, `get_community`, `god_nodes`, `graph_stats`, `shortest_path`, **e mais três que o
  backlog não listava**: `list_prs`, `get_pr_impact`, `triage_prs`.
- Decidir com o Planner a forma do `command` à luz da evidência do item 1 abaixo (`python` puro vs
  `${GRAPHIFY_PYTHON:-python}`; `python` vs `python3` fora do Windows).

### A2 — Mover a regra da §7 para a §2 do `CLAUDE.md`
- Hoje a regra vive nas linhas **144–149** da §7 (`## 7. Onde aprofundar`, linha 143).
- Destino: bloco **`**Regras operacionais rapidas (dia a dia):**`** da §2, que começa na **linha 38**
  (§2 = `## 2. Regras operacionais`, linha 20).
- Na §7 permanece só o detalhe técnico: limites do grafo (a–d da linha 149), rebuild/atualização e o
  que ficou fora do corpus. A §2 recebe a NORMA curta ("antes de varrer arquivos, consultar o grafo").
- Manter o padrão de escrita do `CLAUDE.md` (arquivo legado é sem acentuação; não introduzir regressão
  nem "corrigir" o arquivo inteiro — isso seria expansão de escopo).

### A3 — Hooks versionados em `.githooks/`
- Copiar os dois hooks já instalados (`.git/hooks/post-commit`, 9.376 bytes; `.git/hooks/post-checkout`,
  8.981 bytes) para `.githooks/`, versionados e revisáveis.
- Documentar **explicitamente** que `git config core.hooksPath .githooks` **NÃO é automático**: o git,
  por segurança, não aceita `core.hooksPath` vindo do repositório. Cada clone roda o comando uma vez.
  O ganho é o hook ser revisável e igual para todos, não auto-instalável.
- Runbook: **não existe hoje nenhum doc de graphify em `docs/`** (`git grep -l graphify -- docs/` = vazio;
  a documentação só existe no `CLAUDE.md` §7). Criar `docs/` novo + 1 linha no índice `docs/README.md`
  é o caminho natural e **não** escala criticidade (`docs/` não está em nenhuma lista do `loop_guard`).

## Fora de escopo
- **Escopo B inteiro**: declarar `graphify`/`graphifyy[mcp]` em `pyproject.toml` ou `constraints.txt`.
  Ambos são **CRÍTICO** medido (ver "Criticidade classificada"). Vira bloco/PR próprio.
- Tocar `.gitattributes` (CRÍTICO — e é exatamente onde mora a armadilha do `hook install`).
- Reconstruir o grafo, rodar `--update`, mudar o recorte do corpus (`context/handoff/` e imagens
  seguem fora de propósito), regenerar `graph.json`.
- Qualquer coisa no M1: score, pesos, pipelines, artefatos oficiais. **READ-ONLY sobre o M1.**
- **Achado colateral (registrar, NÃO agir):** `.github/workflows/guard.yml` já implementa
  `DONOS = {"kastaldy", "vinhoabencoado"}`, mas a **DEC-019 está `PROPOSTA`** no índice do `CLAUDE.md`
  §8 e no corpo da própria DEC. O código executa uma decisão que a documentação diz não estar aprovada.
  Ou a DEC vira APROVADA, ou o `guard.yml` volta a um dono só. **Não é deste bloco** — alerta para o
  humano na etapa de aprovação.
- Resolver a divergência de sintaxe do `--update` (ver "Riscos", R6) além de checá-la antes de copiar
  o texto para a §2.

## Evidência levantada (a QUESTÃO DE PROJETO EM ABERTO — medida, não presumida)

### 1. O servidor MCP existe, mas **não funciona hoje nem na máquina que gerou o grafo**
`serve.py` importa o SDK `mcp`, que **não é dependência-base do `graphifyy`** — é um extra.

```
$ python -m pip show graphifyy
Name: graphifyy | Version: 0.9.25
Requires: networkx, numpy, rapidfuzz, tree-sitter, tree-sitter-* (NENHUM 'mcp')

$ python -m pip show mcp
WARNING: Package(s) not found: mcp

$ python -m graphify.serve graphify-out/graph.json
Traceback (most recent call last):
  ... serve.py line 1719, in serve
ImportError: mcp not installed. Run: pip install "graphifyy[mcp]"
(exit code 1)
```

**Consequência direta para o recorte:** o critério de aceite do backlog — *"`.mcp.json` versionado e
funcional num clone limpo (testar de verdade, não presumir)"* — **não é satisfazível pelo Escopo A
sozinho**, porque a instalação é justamente o Escopo B. E mais: o Escopo B como está redigido no
backlog (declarar `graphify`) seria **insuficiente** — o necessário é o extra **`graphifyy[mcp]`**.
O Planner precisa escolher conscientemente entre (i) redefinir o critério de aceite de A para
"`.mcp.json` correto + documentado + degradação verificada", deixando "funcional" para o PR do B,
ou (ii) puxar o B para dentro e aceitar Crítica. **Recomendação do BO: (i)** — não prender o valor
principal a uma aprovação Crítica, que é o que o próprio backlog recomenda.

### 2. Resposta à pergunta (a) — falha graciosa? **SIM**
- O processo falha **rápido e determinístico**: sai com exit 1 e mensagem acionável
  (`pip install "graphifyy[mcp]"`). Não trava, não pendura o stdio.
- Doc oficial do Claude Code (confirmada por consulta dirigida): quando o `command` de um servidor MCP
  falha ao iniciar, o Claude Code **pula aquele servidor, registra o motivo no log e mantém a sessão**;
  o usuário vê `✘ failed to connect` em `/mcp`. Timeout via `MCP_TIMEOUT` (~30 s por padrão).
- **Portanto um `.mcp.json` versionado é INERTE e seguro onde o extra não está instalado** — o pior
  caso é uma linha de erro visível em `/mcp`, não uma sessão quebrada. Isso desarma o principal medo
  do bloco e sustenta a recomendação (i) acima.

### 3. Resposta à pergunta (c) — A depende de B para ser portátil? **Não para ser SEGURO; sim para ser FUNCIONAL**
- O `command` **é** portátil sem o B: `python` resolve pelo PATH em qualquer máquina; caminho absoluto
  de interpretador (rejeitado pelo backlog, com razão) não é necessário.
- A doc do Claude Code **não documenta** `uvx`/`pipx run` como prática suportada para servidores MCP
  (o exemplo canônico é `npx -y`, mundo Node). Registrar como **não recomendado**, não como opção.
- `${VAR:-default}` **é** suportado no `.mcp.json` → `"command": "${GRAPHIFY_PYTHON:-python}"` é uma
  alavanca de portabilidade barata (Windows usa `python`; Linux/container costuma exigir `python3`).
- O **CLI continua funcionando sem o extra** — verificado de verdade:
  `python -m graphify query "loop_guard classificacao de caminhos" --budget 300` retornou 187 nós,
  exit 0. Ou seja, a regra da §2 (A2) **entrega valor mesmo se o MCP ficar inerte** até o PR do B.
  Isso torna A2+A3 imunes ao impasse do A1.

### 4. Pré-aprovação do servidor project-scoped (limitação gêmea da do `core.hooksPath`)
Servidores declarados em `.mcp.json` **exigem aprovação do usuário na primeira sessão**. Existem chaves
de pré-aprovação em `.claude/settings.json`: `enableAllProjectMcpServers`, `enabledMcpjsonServers`,
`disabledMcpjsonServers`. `.claude/` é **GOVERNANÇA** no `loop_guard` — usá-las **não** escala o PR para
Crítica (segue Alta). Decisão do Planner: usar `enabledMcpjsonServers: ["graphify"]` (mais estrito que
`enableAllProjectMcpServers`) ou apenas documentar o passo manual. Em qualquer caso, **documentar** que
a aprovação não é automática, pelo mesmo motivo do `core.hooksPath`.

### 5. Estado do repositório na branch (verificado agora)
- `git status --porcelain` → **vazio**. O rebuild disparado pelo hook `post-checkout` ao criar a branch
  **não** sujou `graphify-out/`. Nada a limpar hoje — mas o Builder deve re-conferir antes de cada
  commit, porque o hook dispara a cada commit/checkout.
- `.mcp.json` **não existe**; `.githooks/` **não existe**; `core.hooksPath` **não está definido**.
- `.git/hooks/` contém apenas `post-commit` e `post-checkout` do graphify (fora os `.sample`).

## Arquivos que devem ser lidos
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\CLAUDE.md` (§2 linha 20 / bloco de regras
  rápidas linha 38; §7 linha 143, regra nas linhas 144–149)
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\tasks\backlog.md` (bloco BLK-GRAPH-02,
  linhas 110–210)
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\scripts\loop_guard.py` (classes
  `_DENY_CRITICO` / `_DENY_GOVERNANCA`)
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\.gitattributes` (linha 39: o `-diff
  linguist-generated=true` do `graph.json` que NÃO pode ser removido)
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\.gitignore` (linhas 151–168: o que de
  `graphify-out/` é versionado e o que é ignorado)
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\.claude\settings.json` (versionado; onde
  entrariam as chaves de pré-aprovação do MCP)
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\docs\README.md` (índice temático; recebe
  a linha do runbook novo)
- Referência externa (site-packages, **somente leitura**):
  `...\site-packages\graphify\serve.py` (tools reais, linhas 1196–1304; `_main` linha 1929) e
  `...\site-packages\graphify\hooks.py` (`.gitattributes` na linha 554; `_hooks_dir` respeita
  `core.hooksPath` nas linhas 399–407)

## Arquivos que podem ser alterados
- `.mcp.json` (**novo** — livre no `loop_guard`)
- `.githooks/post-commit`, `.githooks/post-checkout` (**novos** — livres)
- `CLAUDE.md` (§2 + §7 — **GOVERNANÇA**)
- `docs/<runbook-novo>.md` + `docs/README.md` (livres; nome a definir pelo Planner)
- `.claude/settings.json` (**apenas se** o Planner adotar a pré-aprovação — GOVERNANÇA, não escala)
- `tasks/backlog.md` e `tasks/completed.md` (housekeeping do fechamento — GOVERNANÇA/livre)

**NÃO commitar:** `pyproject.toml`, `constraints.txt`, `.gitattributes` (os três CRÍTICOS),
`graphify-out/*` (regenerado pelo hook, não é entrega deste bloco), `PRD.md`, `context/handoff.md`,
`tasks/current_task.md`.

## Critérios de aceite
1. `.mcp.json` versionado na raiz, com `mcpServers.<nome>.command`/`args` apontando para
   `python -m graphify.serve graphify-out/graph.json` (módulo, **não** subcomando), JSON válido.
2. A degradação foi **verificada de verdade** (não presumida) no estado atual — sem o extra `[mcp]` o
   servidor sai com `ImportError` + exit 1 e a sessão do Claude Code sobrevive. Registrar o comando e a
   saída no handoff do Builder.
3. A regra de consultar o grafo está na **§2** do `CLAUDE.md`, dentro de `Regras operacionais rapidas`;
   a §7 mantém apenas o detalhe técnico (limites, rebuild, corpus). Sem duplicação da norma nas duas.
4. `.githooks/` contém os dois hooks, e a limitação do `core.hooksPath` ("o git não aplica
   `core.hooksPath` vindo do repositório; cada clone roda o comando uma vez") está documentada
   **explicitamente**, junto com a limitação gêmea da aprovação do `.mcp.json`.
5. `python scripts/loop_guard.py --base main` (ou `--stdin` com o diff do PR) **sem nenhum CRÍTICO** —
   só GOVERNANÇA (`CLAUDE.md`, `tasks/backlog.md`, e `.claude/settings.json` se usado).
6. `.gitattributes` **inalterado** — em especial a linha 39 (`graphify-out/graph.json -diff
   linguist-generated=true`) preservada e **nenhuma** linha `merge=graphify` adicionada.
7. `ruff` e `mypy` limpos; suíte verde (baseline a medir no momento — ver `CLAUDE.md` §5; a contagem
   escrita lá envelhece e não serve de tripwire).
8. `git status --porcelain` conferido antes do commit: `graphify-out/` não pode entrar por acidente.

## Criticidade classificada
**ALTA** — confirmada empiricamente, não presumida. `scripts/loop_guard.py --stdin` com os caminhos
do Escopo A devolveu:

```
{"limpo": false, "violacoes": [
  {"path": "CLAUDE.md",        "classe": "governanca", ...},
  {"path": "tasks/backlog.md", "classe": "governanca", ...}]}
```

`.mcp.json`, `.githooks/*`, `docs/*`, `tasks/completed.md` → **não casam nenhuma regra** (livres).
Com o Escopo B junto, aparecem `pyproject.toml` e `constraints.txt` como **`critico`** (e
`.gitattributes` também) → escalaria para **Crítica**. **O Escopo A sozinho mantém o PR em Alta**,
exigindo só a label `aprovado-humano`.

## Esteira recomendada
Block Orchestrator (concluído) → **Planner** → **[aprovação humana]** → Builder → QA.

## Riscos identificados
- **R1 (o principal) — o critério de aceite do backlog é insatisfazível no Escopo A.** "Funcional num
  clone limpo" exige `pip install "graphifyy[mcp]"`, que é o Escopo B. O Planner **precisa** redefinir
  o critério de A (recomendado) ou assumir Crítica. Ignorar isso entrega um PR que o QA reprova por um
  critério impossível.
- **R2 — `python -m graphify hook install` re-adiciona `graphify-out/graph.json merge=graphify` ao
  `.gitattributes`** (confirmado em `hooks.py`, `_install_merge_driver`, linha 554) → path **CRÍTICO**,
  escala o PR sem querer. **Não rodar `hook install` neste ciclo**; copiar os hooks já existentes.
- **R3 — resíduo do BLK-GRAPH-01 ainda ativo (novo, não estava no backlog):** o git config **local**
  ainda tem `merge.graphify.name` e `merge.graphify.driver` apontando para um `graphify.exe` de caminho
  absoluto. A linha do `.gitattributes` foi revertida em `1ebef60`, então o driver está órfão e inerte
  hoje — mas é a metade de um estado inconsistente e reaparece no primeiro `hook install`.
- **R4 — `core.hooksPath` muda o alvo do `hook install`:** `_hooks_dir()` (hooks.py, linhas 399–407)
  **respeita** `core.hooksPath`. Depois que o Builder documentar/aplicar `core.hooksPath .githooks`, um
  futuro `hook install` passa a escrever **dentro do diretório versionado** (produz diff no repo) e o
  graphify **erra** se o caminho não for POSIX (linha 395). Documentar no runbook.
- **R5 — remover o `-diff linguist-generated=true` do `graph.json` afoga o `claude-review`.** Foi
  exatamente o que reprovou o PR #150 (termina `success` sem saída estruturada → gate fail-closed).
  Não encostar na linha 39 do `.gitattributes`.
- **R6 — divergência doc↔ferramenta no comando de update, que o A2 vai COPIAR:** a §7 (linha 147) manda
  rodar `python -m graphify . --update`, mas o `--help` do CLI só documenta `update <path>`, e o próprio
  CLI imprime *"Run /graphify --update in your AI assistant"* (forma de slash-command, não de shell).
  O `cli.py` reescreve `graphify <path> ...` → `graphify extract <path> ...` (linhas 3712–3713), então a
  forma da §7 provavelmente vira `extract . --update`. **Verificar antes de promover o texto a NORMA na
  §2** — mover para a §2 uma linha de comando errada é pior do que deixá-la na §7.
- **R7 — base do PR.** Esta branch saiu de `graph-01` (`be7787a`), que carrega 7 commits sobre a `main`.
  Abrir o PR com **base `graph-01`** para ter diff limpo; se abrir contra a `main`, o diff combinado
  passa de 265k linhas e afoga o `claude-review` (mesmo modo de falha do R5).
- **R8 — PR Crítico exige DUAS labels cumulativas** (`critica-aprovada` **E** `aprovado-humano`). Não se
  substituem. Só vira problema se o Escopo B escorregar para dentro — mais um motivo para mantê-lo fora.
- **R9 — `graphify` nu não está no PATH** (o pacote instala `graphify.exe` em `<python>/Scripts/`).
  Sempre `python -m graphify`.

## Guardrails ativos
- **READ-ONLY sobre o M1** (`CLAUDE.md` §5): nada neste bloco recalcula ou altera `score_priorizacao`,
  `hex_score_estrutural`, carteira, plano de curto prazo, plano de domínio ou qualquer artefato oficial
  do M1. É camada de tooling/governança.
- **§6.1 / DEC-016:** bloco **não é loop-safe** (sem marcador `Autonomia: loop-safe` no backlog) porque
  toca `CLAUDE.md` = GOVERNANÇA. Criticidade **Alta** → merge exige a label **`aprovado-humano`** de
  humano ≠ autor. **Deploy nunca é automático** (não se aplica aqui: nada vai para a VPS).
- **§2 (acentuação):** texto novo voltado ao usuário com acentuação correta; **nunca** acentuar
  identificadores (chaves de JSON, nomes de tool do MCP, nomes de arquivo, `key=`). Os nomes das tools
  (`query_graph`, `god_nodes`, …) e o nome do servidor no `.mcp.json` são identificadores — sem acento.
- **§2:** ler o repositório real antes de editar; `CLAUDE.md`, `config.py` e `PRD.md` são fontes canônicas.
- **Regra de manutenção do `CLAUDE.md` (topo do arquivo):** manter curto. A A2 é um **movimento** de
  texto (§7 → §2), não uma expansão; o saldo de linhas deve ficar neutro ou negativo.
- **Guard por path:** `.gitattributes`, `pyproject.toml` e `constraints.txt` são CRÍTICOS e estão fora
  deste PR por decisão de recorte.
