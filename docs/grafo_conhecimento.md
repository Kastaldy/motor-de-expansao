# Grafo de conhecimento (graphify) — runbook canônico

> Contrato operacional da camada de navegação por grafo. Executado no BLK-GRAPH-02.
> **READ-ONLY sobre o M1:** nada aqui recalcula ou altera `score_priorizacao`,
> `hex_score_estrutural`, carteira, plano de curto prazo, plano de domínio ou artefato oficial.
> A norma de *quando* usar está no `CLAUDE.md` §2; o detalhe técnico curto, na §7. Este arquivo é o
> aprofundamento.

---

## 1. O que é e para que serve

O `graphify` transforma o repositório em um **grafo de conhecimento** persistente: 421 arquivos
(290 de código extraídos por AST + 131 documentos, contratos e DECs extraídos por LLM) viram
**7.633 nós e 15.362 arestas** (medido em 2026-07-28 sobre o `graphify-out/graph.json` versionado).

Serve para responder, em **uma consulta**, perguntas que hoje custam uma varredura inteira:
"como X funciona", "o que chama Y", "onde vive Z", "o que quebra se eu mudar W". O benchmark do
próprio graphify aponta **~58x menos tokens por consulta** do que ler o corpus equivalente.

**O que ele NÃO é.** O grafo é um **índice de navegação**, não fonte canônica. Parâmetro, fórmula e
guardrail valem pelo `CLAUDE.md` §3/§8 e pelos contratos em `docs/` — sempre. Se a resposta do grafo
divergir do contrato, o contrato ganha e o grafo está desatualizado.

---

## 2. Instalar

```bash
python -m pip install --group graph
```

O grupo `graph` está declarado em `pyproject.toml`, em `[dependency-groups]` (PEP 735):

```toml
graph = [
    "graphifyy[mcp]>=0.9.29,<0.10",
    "mcp>=1.28,<2",
]
```

### Por que `[dependency-groups]` e não um extra opcional

O comando canônico que regenera o lock (`ci.yml:45`) é
`uv pip compile pyproject.toml --all-extras ...`, e ele **não enxerga `[dependency-groups]`**.
Medido em 2026-07-28, em venv descartável:

| Forma de declarar | Pins que o `uv pip compile --all-extras` produz |
|---|---|
| `[dependency-groups]` (adotado) | **214** — os mesmos de hoje, byte a byte |
| `[project.optional-dependencies]` (extra) | **250** (+36, dos quais 25 gramáticas `tree-sitter-*`) |

Como extra, a ferramenta entraria no `constraints.txt` e passaria a ser auditada pelo `pip-audit`
bloqueante do CI — 36 dependências novas podendo reprovar o CI por um código que **não roda no CI,
nem nas imagens de produção, nem no container do loop** (nenhum arquivo de `src/`, `scripts/` ou
`tests/` faz `import graphify`).

Consequência declarada: **o `constraints.txt` NÃO pina o grafo, de propósito.** Não é esquecimento.

### Por que o `mcp` está pinado abaixo de 2

O pacote `mcp` subiu para **2.0.0** e **removeu `AnyUrl` de `mcp.types`**. O `graphify/serve.py:1116`
ainda importa esse símbolo, dentro de um `try/except ImportError` que **mascara o erro real** e
levanta outra mensagem no lugar:

```
ImportError: mcp not installed. Run: pip install "graphifyy[mcp]"
```

Ou seja: com `mcp 2.x` instalado, o servidor sobe, morre, e informa que o pacote **não está
instalado** — uma mensagem que mente e manda a pessoa reinstalar o que já está lá. Medido em
2026-07-28: `mcp 2.0.0` → `TOOLS (0)`, `EXIT 1`, `FAIL`; `mcp 1.29.0` → handshake completo,
10 tools, `EXIT 0`, `PASS`.

O pin é travado por teste que **roda sempre no CI**
(`tests/contracts/test_grafo_ferramenta.py`), justamente porque essa classe de defeito volta em
silêncio. **Reavaliar quando o graphify passar a suportar `mcp 2.x`** — e, quando isso acontecer,
a reconferência é um comando só (seção 5).

---

## 3. Consultar

### Pela linha de comando

```bash
python -m graphify query "como o score_priorizacao é calculado"
python -m graphify path "dashboard" "score_priorizacao"
python -m graphify explain "enrich_dashboard_data"
```

**Sempre `python -m graphify`, nunca o comando `graphify` nu.** O pacote instala `graphify.exe` em
`<python>/Scripts/`, que normalmente **não está no PATH** (o próprio `pip install` avisa isso).

Se a resposta vier cortada, a consulta truncou por orçamento de tokens — aumente com `--budget`.

### Pela tool MCP

O servidor é declarado no `.mcp.json` da raiz e expõe **10 tools**:

| Tool | Para quê |
|---|---|
| `query_graph` | pergunta em linguagem natural, com travessia BFS |
| `get_node` | detalhe de um nó específico |
| `get_neighbors` | vizinhança direta de um nó |
| `get_community` | comunidade (cluster) a que um nó pertence |
| `god_nodes` | nós de altíssimo grau (pontos de acoplamento do repo) |
| `graph_stats` | contagens e trilha de proveniência do grafo |
| `shortest_path` | menor caminho entre dois conceitos |
| `list_prs` | lista PRs abertos |
| `get_pr_impact` | impacto de um PR sobre o grafo |
| `triage_prs` | triagem de PRs por impacto |

As **três últimas** (`list_prs`, `get_pr_impact`, `triage_prs`) executam o `gh` por baixo: dependem
de rede e de autenticação. Por isso ficam **fora** do smoke-test da seção 5 — um teste que depende
de rede é um teste que falha por motivo errado.

---

## 4. O `.mcp.json` e a primeira limitação gêmea

Conteúdo versionado na raiz do repositório:

```json
{
  "mcpServers": {
    "graphify": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "graphify.serve", "graphify-out/graph.json"],
      "env": {
        "GRAPHIFY_QUERY_LOG_DISABLE": "1"
      }
    }
  }
}
```

Detalhes que **não** são arbitrários:

- **`command: "python"` literal**, sem `${VAR:-default}`. O verificador da seção 5 lê esse campo do
  próprio arquivo e o executa — uma expansão faria a prova validar uma coisa diferente da que o
  harness roda.
- **`args` invoca o MÓDULO `graphify.serve`**, não um subcomando. **Não existe subcomando `serve`:**
  `python -m graphify serve` cai no fallback de ajuda e **sai com código 0 sem servir nada** —
  falha silenciosa perfeita.
- **Caminho relativo** (`graphify-out/graph.json`) é exatamente o default de `_default_graph_json()`,
  só que explícito e, por isso, testável.
- **`GRAPHIFY_QUERY_LOG_DISABLE`** é redundante hoje (o log já é opt-in), mas trava por contrato que
  nada será escrito em `~/.cache` caso o default do upstream mude.
- **`graphify` é um identificador ASCII**, sem acento — regra do `CLAUDE.md` §2. Vale para o nome do
  servidor, para os nomes de tool e para o nome do grupo `graph`.

### LIMITAÇÃO GÊMEA 1 — o `.mcp.json` pede aprovação na primeira sessão

Um servidor declarado em `.mcp.json` **não é habilitado automaticamente**: o Claude Code pede
aprovação do usuário na primeira sessão. Este repositório pré-aprova o servidor em
`.claude/settings.json`:

```json
"enabledMcpjsonServers": ["graphify"]
```

Quem usar outro harness — ou uma versão que não reconheça a chave — cai no fluxo de aprovação manual
(`/mcp`). Sem dano: a chave desconhecida é ignorada.

Foi usada a forma **estrita** (`enabledMcpjsonServers`, lista explícita) e **não**
`enableAllProjectMcpServers`, que habilitaria qualquer servidor futuro que alguém acrescentasse ao
arquivo.

### Risco de diretório de trabalho (cwd)

O caminho do grafo é relativo ao cwd do processo. Se o harness lançar o servidor de um diretório
inesperado, o arquivo não resolve. **Duas redes de segurança medidas:** o servidor **não morre**
quando o grafo default não carrega (`serve.py:1176-1182`), e as 10 tools aceitam um `project_path`
absoluto como argumento.

---

## 5. Verificar (prova funcional)

```bash
python scripts/verify_mcp_graphify.py
```

O script sobe o processo **exatamente como o `.mcp.json` manda** (lendo `command`, `args` e `env` do
próprio arquivo) e executa um handshake JSON-RPC real sobre stdio: `initialize` →
`notifications/initialized` → `tools/list` → `tools/call graph_stats` → `tools/call query_graph`.

Saída esperada:

```
LAUNCH: ['python', '-m', 'graphify.serve', 'graphify-out/graph.json']
PROTOCOL   : 2025-06-18
SERVERINFO : {'name': 'graphify', 'version': '1.29.0'}
TOOLS (10) : ['get_community', 'get_neighbors', 'get_node', 'get_pr_impact', 'god_nodes',
              'graph_stats', 'list_prs', 'query_graph', 'shortest_path', 'triage_prs']
graph_stats: Nodes: 7633 | Edges: 15362 | Communities: 424 | EXTRACTED: 97% | INFERRED: 3% | AMBIGUOUS: 0%
EXIT       : 0     STDERR: (vazio)     VERDICT: PASS
```

Exit 0 é PASS. **Se vier `TOOLS (0)` com `ImportError: mcp not installed`,** o pin do `mcp` não
pegou — confira com `python -m pip show mcp`. A mensagem mente (seção 2).

**Este script é a ferramenta de regressão do pin.** Quando o graphify suportar `mcp 2.x`, a
reconferência é ele.

---

## 6. Hooks versionados e a segunda limitação gêmea

O `.githooks/post-commit` é uma cópia **byte a byte** do hook que o `graphify hook install` gera
(9.376 bytes, LF puro). Ele dispara, em segundo plano, um rebuild AST do grafo a cada commit — sem
LLM, sem custo de token, **sem bloquear o `git commit`**. Log em `~/.cache/graphify-rebuild.log`.
Para pular pontualmente: `GRAPHIFY_SKIP_HOOK=1 git commit ...`.

O arquivo é versionado com bit de execução (`100755`) e com `eol=lf` travado no `.gitattributes` —
sem isso, com `core.autocrlf=true`, o checkout em Windows entregaria CRLF e quebraria o shebang
`#!/bin/sh`.

### LIMITAÇÃO GÊMEA 2 — o hook não se instala sozinho

O git, por segurança, **não aplica `core.hooksPath` vindo do repositório**. Cada clone e cada
máquina precisa rodar, **uma vez**:

```bash
git config core.hooksPath .githooks
```

O ganho de versionar o hook é ele ser **revisável e igual para todos** — não auto-instalável.
Container do loop e CI não instalam o pacote; lá o grafo simplesmente não atualiza, o que é o
comportamento desejado.

### A camada semântica NÃO é atualizada pelo hook

O hook cobre só o **código** (AST). Mudança em `.md`/`.yaml` é ignorada, porque a camada semântica
precisa de LLM. Depois de mexer em `docs/`, `tasks/`, `CLAUDE.md` ou nas DECs, rodar **numa sessão
Claude o slash-command**:

```
/graphify . --update
```

**`python -m graphify . --update` NÃO faz isso** (verificado em 2026-07-28): o CLI reescreve o
comando para `extract . --update`, o flag é **ignorado em silêncio**, e o que roda é uma extração
COMPLETA com LLM. Falha cara e silenciosa.

**Consequência a ter em mente:** entre um commit de documentação e o `/graphify . --update` manual,
a camada semântica está **desatualizada**. Se a resposta depender de um documento recém-alterado,
leia o arquivo.

---

## 7. Por que o `post-checkout` NÃO foi versionado

O `graphify hook install` instala **dois** hooks: `post-commit` e `post-checkout`. Só o primeiro
entrou no `.githooks/`. A razão é medida, não estética: o `post-checkout` chama `_rebuild_code`
**sem `changed_paths`**, o que significa **corpus inteiro** — e `_rebuild_code` **não tem parâmetro
de exclusão**. Ele portanto ignora o recorte curado do corpus.

| | Grafo curado (versionado) | Rebuild automático total |
|---|---|---|
| Nós | 7.633 | 13.599 |
| Arestas | 15.362 | 21.063 |
| Bytes do `graph.json` | 10.421.306 | 15.299.593 |
| `context/handoff/` (566 logs) | **fora** do corpus | **dentro** |
| `.graphify_labels.json` curado | preservado | **sobrescrito** |

> Os números do rebuild total e a contagem de logs foram medidos durante o BLK-GRAPH-01/02; as
> colunas do curado foram remedidas em 2026-07-28 sobre o artefato versionado (o BLK-GRAPH-01
> registrou 7.560/15.351/10.157.850, valores de um snapshot anterior).

Ou seja: um `git checkout` de branch bastaria para inflar o grafo em ~78% de nós e jogar 566 logs de
handoff dentro do corpus — exatamente o que o recorte da §7 do `CLAUDE.md` decidiu manter fora.

Rodar `git config core.hooksPath .githooks` **neutraliza** o `post-checkout` local (o git passa a
procurar hooks só em `.githooks/`, onde ele não existe). Reintroduzi-lo tem de ser um ato
**consciente** — há um teste que falha se o arquivo aparecer.

---

## 8. Se o repositório aparecer sujo em `graphify-out/`

**É o hook, não você.** O rebuild em segundo plano modifica artefatos do `graphify-out/` depois de
cada commit. Antes de commitar:

```bash
git checkout -- graphify-out/
```

E **sempre commite por path** — `git add <caminho> [...]`, **nunca** `git add -A` nem `git add .`.
Um `graphify-out/graph.json` regenerado que entra de carona num commit de outra coisa é ruído puro
no diff e não deve acontecer.

---

## 9. Armadilhas conhecidas

1. **`graphify` nu não está no PATH.** Use `python -m graphify`. O `pip install` avisa, e o aviso
   passa despercebido.
2. **Não rode `python -m graphify hook install` neste repositório.** O instalador **re-adiciona**
   a linha `graphify-out/graph.json merge=graphify` ao `.gitattributes` — um caminho **CRÍTICO** no
   `loop_guard`, revertido de propósito no commit `1ebef60`. Se por qualquer motivo rodar, **confira
   o `.gitattributes` depois**. O verbo também não está liberado no `permissions.allow`.
3. **Resíduo `merge.graphify.*` no git config LOCAL.** O `hook install` de 2026-07-27 registrou um
   merge driver que, desde o `1ebef60`, está **órfão e inerte** (nenhum `.gitattributes` o
   referencia). Fica registrado aqui, e **não se mexe** — mas ele volta a valer no primeiro
   `hook install` novo. É a outra ponta da armadilha 2.
4. **Não remova o `-diff linguist-generated=true`** da linha do `graphify-out/graph.json` no
   `.gitattributes`. Sem ela, os ~10 MB / 263 mil linhas de JSON dominam 99% do diff e **afogam o
   revisor automático** — foi o que reprovou o PR #150, fail-closed. É o que mantém os PRs desta
   linhagem revisáveis.
5. **O nome no PyPI é `graphifyy`, com dois `y`.** O nome nu `graphify` está **UNCLAIMED** — se
   alguém o registrar, um `pip install graphify` copiado de um documento antigo executa código de
   terceiro. Typosquatting real, não hipotético.

---

## 10. Dívida registrada

- **O `constraints.txt` não pina o grafo**, por decisão medida (seção 2). Registrado para não ser
  lido como esquecimento em auditoria futura.
- **`graphify-out/graph.json` deve continuar versionado ou virar artefato de CI?** Pergunta em
  aberto. Versionar dá consulta offline e reprodutibilidade; custa ~10 MB por linhagem e exige a
  disciplina da seção 8. Não foi resolvido no BLK-GRAPH-02.
- **Portabilidade do `command`.** O `command: "python"` funciona nesta máquina porque o `python` do
  PATH é o interpretador que tem o pacote. Um `${GRAPHIFY_PYTHON:-python}` foi considerado e
  **descartado sem medição suficiente**; reavaliar só quando existir uma segunda máquina para medir.

---

## Referências

- `CLAUDE.md` §2 (a norma) e §7 (o detalhe técnico curto).
- `.mcp.json`, `.githooks/post-commit`, `.gitattributes`, `.claude/settings.json`.
- `scripts/verify_mcp_graphify.py` — prova funcional.
- `tests/contracts/test_grafo_ferramenta.py` — gate que roda sempre no CI.
- `tests/integration/test_mcp_graphify_server.py` — rede de segurança para quem tem o extra.
- `graphify-out/GRAPH_REPORT.md` — god nodes, coesão e trilha EXTRACTED/INFERRED/AMBIGUOUS.
