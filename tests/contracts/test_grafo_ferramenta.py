"""Contrato do grafo como FERRAMENTA (BLK-GRAPH-02).

O BLK-GRAPH-01 entregou o grafo e o versionou, mas o *uso* dele nao viajava: sem `.mcp.json`,
sem dependencia declarada, sem hook revisavel, e com a regra escondida na secao "Onde aprofundar"
do `CLAUDE.md`. Este arquivo trava o resultado do BLK-GRAPH-02 -- cada assercao aqui corresponde
a um defeito MEDIDO em 2026-07-28, nao a uma preferencia de estilo.

PRINCIPIO DE PROJETO -- ancora ausente e FALHA, nunca skip (mesmo de `test_docs_vs_codigo.py`).
Este modulo NAO importa `mcp` nem `graphify` e NAO depende de rede: ele le arquivos versionados
com a stdlib. Logo ele RODA SEMPRE, inclusive no CI e no container do loop, que nao instalam o
grupo `graph`. Essa e a diferenca deliberada para `tests/integration/test_mcp_graphify_server.py`,
que SKIPa sem o extra e por isso NAO e o gate.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
MCP_JSON = RAIZ / ".mcp.json"
SETTINGS_JSON = RAIZ / ".claude" / "settings.json"
PYPROJECT = RAIZ / "pyproject.toml"
GITATTRIBUTES = RAIZ / ".gitattributes"
CLAUDE_MD = RAIZ / "CLAUDE.md"
RUNBOOK = RAIZ / "docs" / "grafo_conhecimento.md"
DEC_019 = RAIZ / "docs" / "decisions" / "DEC-019.md"

#: Os 10 nomes que o servidor expoe (medido por handshake JSON-RPC real em 2026-07-28).
TOOLS_ESPERADAS = (
    "get_community",
    "get_neighbors",
    "get_node",
    "get_pr_impact",
    "god_nodes",
    "graph_stats",
    "list_prs",
    "query_graph",
    "shortest_path",
    "triage_prs",
)


def _ler(caminho: Path) -> str:
    assert caminho.is_file(), (
        f"arquivo canonico ausente: {caminho.relative_to(RAIZ)}. "
        "Ele faz parte do contrato do BLK-GRAPH-02; recrie-o em vez de afrouxar o teste."
    )
    return caminho.read_text(encoding="utf-8")


def _mcp() -> dict:
    return json.loads(_ler(MCP_JSON))


def _servidor_graphify() -> dict:
    return _mcp()["mcpServers"]["graphify"]


def _pyproject() -> dict:
    return tomllib.loads(_ler(PYPROJECT))


# --------------------------------------------------------------------------------------
# .mcp.json
# --------------------------------------------------------------------------------------


def test_mcp_json_e_json_valido_e_declara_o_servidor_graphify() -> None:
    brutos = MCP_JSON.read_bytes() if MCP_JSON.is_file() else b""
    assert brutos, f"{MCP_JSON.relative_to(RAIZ)} ausente ou vazio."
    assert not brutos.startswith(b"\xef\xbb\xbf"), (
        "`.mcp.json` foi gravado com BOM UTF-8. Parsers JSON estritos rejeitam o BOM e o servidor "
        "nunca sobe. No Windows isso acontece ao usar `Out-File`/`Set-Content` sem `-Encoding utf8`."
    )

    dados = _mcp()
    assert set(dados) == {"mcpServers"}, (
        f"chaves de topo inesperadas em `.mcp.json`: {sorted(dados)}. O contrato prevê apenas "
        "`mcpServers` -- chave extra costuma ser config de outro harness entrando de carona."
    )
    assert "graphify" in dados["mcpServers"], (
        "o servidor `graphify` sumiu do `.mcp.json`; sem ele o grafo volta a ser uma instrucao "
        "de documento em vez de uma ferramenta."
    )

    srv = _servidor_graphify()
    assert srv.get("type") == "stdio", f"`type` deve ser 'stdio', veio {srv.get('type')!r}."
    assert isinstance(srv.get("command"), str) and srv["command"].strip(), (
        "`command` deve ser uma string nao vazia."
    )
    assert isinstance(srv.get("args"), list) and all(isinstance(a, str) for a in srv["args"]), (
        "`args` deve ser uma lista de strings."
    )


def test_mcp_json_invoca_o_MODULO_serve_e_nao_um_subcomando() -> None:
    args = _servidor_graphify()["args"]
    assert args[:2] == ["-m", "graphify.serve"], (
        f"`args` deve comecar com ['-m', 'graphify.serve'], veio {args[:2]!r}. ARMADILHA MEDIDA: "
        "NAO existe subcomando `serve` no CLI -- `python -m graphify serve` cai no fallback de "
        "ajuda e SAI COM CODIGO 0 SEM SERVIR NADA. O harness veria um servidor que morre calado."
    )


def test_mcp_json_usa_command_literal_e_nao_expansao_de_variavel() -> None:
    command = _servidor_graphify()["command"]
    assert "${" not in command, (
        f"`command` contem expansao de variavel ({command!r}). Decisao D10 do BLK-GRAPH-02: "
        "`scripts/verify_mcp_graphify.py` le este campo do proprio `.mcp.json` e o executa via "
        "subprocess -- com `${...}` a prova ou falha, ou passa a provar algo diferente do que o "
        "harness roda. Portabilidade se resolve no runbook (`pip install --group graph`), nao aqui."
    )
    assert command == "python", (
        f"`command` deve ser 'python' literal, veio {command!r}. Trocar o interpretador exige "
        "medicao em segunda maquina (follow-up registrado em `docs/grafo_conhecimento.md` §10)."
    )


def test_mcp_json_aponta_para_o_caminho_canonico_do_grafo() -> None:
    args = _servidor_graphify()["args"]
    assert args[2] == "graphify-out/graph.json", (
        f"o alvo do servidor deve ser 'graphify-out/graph.json', veio {args[2]!r}."
    )
    # NAO se asserta `is_file()` de proposito: o artefato nao existe em toda linhagem/branch
    # (a `main` nao o tem). Um gate que quebrasse numa base sem o artefato viraria ruido e
    # acabaria desligado -- o que se trava aqui e o CONTRATO do caminho, nao a presenca do dado.


def test_nome_do_servidor_mcp_e_identificador_ascii() -> None:
    for nome in _mcp()["mcpServers"]:
        assert re.fullmatch(r"[a-z][a-z0-9_-]*", nome), (
            f"nome de servidor MCP invalido: {nome!r}. `CLAUDE.md` §2: IDENTIFICADOR nunca leva "
            "acento nem maiuscula/espaco -- acentuacao correta vale para texto de usuario, e "
            "para exibir bonito usa-se camada de label."
        )


def test_settings_json_pre_aprova_exatamente_os_servidores_do_mcp_json() -> None:
    settings = json.loads(_ler(SETTINGS_JSON))
    habilitados = settings.get("enabledMcpjsonServers")
    assert habilitados is not None, (
        "`.claude/settings.json` nao tem `enabledMcpjsonServers`. Sem a chave, um servidor de "
        "`.mcp.json` exige aprovacao manual do usuario na primeira sessao (limitacao gemea 1)."
    )
    assert set(habilitados) == set(_mcp()["mcpServers"]), (
        f"drift entre `.mcp.json` ({sorted(_mcp()['mcpServers'])}) e a pre-aprovacao "
        f"({sorted(habilitados)}). Renomear o servidor sem atualizar a chave faz o harness voltar "
        "a pedir aprovacao manual EM SILENCIO."
    )
    assert "enableAllProjectMcpServers" not in settings, (
        "`enableAllProjectMcpServers` habilitaria QUALQUER servidor futuro do `.mcp.json` sem "
        "revisao. O contrato usa a forma estrita, com lista explicita."
    )


# --------------------------------------------------------------------------------------
# pyproject.toml -- a descoberta M6 virando regressao automatica
# --------------------------------------------------------------------------------------


def test_dependency_group_graph_declara_graphifyy_e_fixa_mcp_abaixo_de_2() -> None:
    grupos = _pyproject().get("dependency-groups", {})
    assert "graph" in grupos, (
        "`[dependency-groups].graph` sumiu do `pyproject.toml`. Sem ele o graphify volta a ser "
        "uma dependencia nao declarada, instalada a mao em cada maquina."
    )
    entradas = grupos["graph"]

    assert any(e.startswith("graphifyy[mcp]") for e in entradas), (
        f"o grupo `graph` deve declarar `graphifyy[mcp]`; veio {entradas!r}."
    )
    for entrada in entradas:
        nome = re.split(r"[\[<>=!~;\s]", entrada, maxsplit=1)[0]
        assert nome != "graphify", (
            f"entrada {entrada!r} usa o nome NU `graphify`. O pacote correto no PyPI e `graphifyy` "
            "(DOIS 'y'); `graphify` esta UNCLAIMED -- declarar o nome nu abre typosquatting real."
        )

    mcp = [e for e in entradas if re.match(r"^mcp\b", e)]
    assert mcp, f"o grupo `graph` nao pina o `mcp`; veio {entradas!r}."
    assert any("<2" in e for e in mcp), (
        f"o pin de `mcp` perdeu o teto `<2` (veio {mcp!r}). O PIN NAO E COSMETICO: mcp 2.0.0 "
        "removeu AnyUrl de mcp.types; graphify/serve.py:1116 ainda importa. Sem o pin o servidor "
        "morre com a mensagem enganosa 'mcp not installed'. Medido 2026-07-28."
    )


def test_graphify_nao_e_extra_para_o_lock_nao_incha() -> None:
    extras = _pyproject().get("project", {}).get("optional-dependencies", {})
    assert "graph" not in extras, (
        "o grupo `graph` virou um EXTRA em `[project.optional-dependencies]`. MEDIDO 2026-07-28: "
        "o comando canonico de refresh do lock (`ci.yml:45`, `uv pip compile --all-extras`) NAO "
        "enxerga `[dependency-groups]` (214 pins, identicos), mas puxa +36 pins como extra (250, "
        "dos quais 25 gramaticas tree-sitter) -- que passariam a poder reprovar o `pip-audit` "
        "bloqueante por um codigo que nao roda no CI nem em producao."
    )


# --------------------------------------------------------------------------------------
# .githooks/ e .gitattributes
# --------------------------------------------------------------------------------------


def test_githooks_versiona_o_post_commit_com_lf_e_sem_o_post_checkout() -> None:
    hook = RAIZ / ".githooks" / "post-commit"
    assert hook.is_file(), "`.githooks/post-commit` ausente -- o hook volta a nao ser revisavel."
    dados = hook.read_bytes()
    assert dados.startswith(b"#!/bin/sh"), (
        f"`.githooks/post-commit` nao comeca com o shebang `#!/bin/sh` (veio {dados[:20]!r})."
    )
    assert b"graphify-hook-start" in dados, (
        "`.githooks/post-commit` nao contem o marcador `graphify-hook-start`: ou nao e o hook do "
        "graphify, ou foi editado a mao (o contrato e' copia BYTE A BYTE do gerado pelo upstream)."
    )
    assert b"\r\n" not in dados, (
        "`.githooks/post-commit` tem CRLF. Com `core.autocrlf=true` no Windows o checkout quebra o "
        "shebang `#!/bin/sh` e o hook morre calado. A regra `.githooks/* text eol=lf` do "
        "`.gitattributes` existe exatamente para isso."
    )

    assert not (RAIZ / ".githooks" / "post-checkout").exists(), (
        "`.githooks/post-checkout` foi (re)introduzido. Decisao D4 do BLK-GRAPH-02, MEDIDA: esse "
        "hook chama `_rebuild_code` SEM `changed_paths` (corpus inteiro) e `_rebuild_code` nao tem "
        "parametro de exclusao -- um `git checkout` inflaria o grafo curado de 7.633 nos / 15.362 "
        "arestas para 13.599 / 21.063, jogando os 566 logs de `context/handoff/` dentro do corpus "
        "e sobrescrevendo o `.graphify_labels.json`. Reintroduzir tem de ser ato CONSCIENTE."
    )


def test_gitattributes_protege_o_graph_json_e_fixa_eol_dos_hooks() -> None:
    linhas = [ln.strip() for ln in _ler(GITATTRIBUTES).splitlines() if ln.strip() and not ln.lstrip().startswith("#")]

    assert not any("merge=graphify" in ln for ln in linhas), (
        "`graphify-out/graph.json merge=graphify` voltou ao `.gitattributes`. Foi revertida no "
        "commit `1ebef60` (escalava o PR para Critica). O instalador do upstream "
        "(`python -m graphify hook install`) RE-ADICIONA essa linha -- por isso o verbo nao esta "
        "no `permissions.allow` e o runbook proibe roda-lo neste repo."
    )

    referencias = [ln for ln in linhas if "graphify-out/graph.json" in ln]
    assert referencias, "sumiu a regra de `graphify-out/graph.json` do `.gitattributes`."
    for ln in referencias:
        assert "-diff" in ln, (
            f"a linha {ln!r} perdeu o `-diff`. Sem ele os ~10 MB / 263k linhas do `graph.json` "
            "dominam 99% do diff e AFOGAM o `claude-review` -- foi o que reprovou o PR #150 "
            "fail-closed. E o que mantem os PRs desta linhagem revisaveis."
        )

    assert any(".githooks/" in ln and "eol=lf" in ln for ln in linhas), (
        "falta a regra de EOL dos hooks (`.githooks/* text eol=lf`). O `*.sh` nao cobre "
        "`.githooks/post-commit`, que NAO tem extensao."
    )


# --------------------------------------------------------------------------------------
# CLAUDE.md -- a NORMA e o comando que o CLI ignora
# --------------------------------------------------------------------------------------


def _secao(texto: str, inicio: str, fim: str) -> str:
    i = texto.find(inicio)
    assert i != -1, (
        f"heading {inicio!r} nao encontrado no `CLAUDE.md`. Se a secao foi renomeada, atualize a "
        "ancora CONSCIENTEMENTE -- ancora ausente e FALHA, nunca skip."
    )
    j = texto.find(fim, i)
    assert j != -1, f"heading {fim!r} nao encontrado apos {inicio!r} no `CLAUDE.md`."
    return texto[i:j]


def test_norma_do_grafo_esta_na_secao_2_e_nao_duplicada_na_secao_7() -> None:
    texto = _ler(CLAUDE_MD)
    sec2 = _secao(texto, "## 2. Regras operacionais", "## 3. Nucleo oficial M1")
    sec7 = _secao(texto, "## 7. Onde aprofundar", "## 8. Decisoes registradas")

    assert "python -m graphify query" in sec2, (
        "a NORMA de consultar o grafo saiu da §2 (`Regras operacionais`). Na §7 ('Onde "
        "aprofundar') ela e lida como bibliografia, nao como regra -- que era o defeito original."
    )
    assert "Grafo antes de varredura" not in sec7, (
        "a NORMA foi duplicada na §7. Fato duplicado em dois lugares e fato que envelhece em um "
        "deles; a §7 fica so com o detalhe tecnico."
    )
    assert "LIMITES do grafo" not in sec2, (
        "o detalhe tecnico (LIMITES) vazou para a §2, que precisa ficar curta e normativa."
    )


def test_claude_md_nao_recomenda_a_forma_de_update_que_o_cli_ignora() -> None:
    """A forma CLI existe no doc apenas como ADVERTENCIA, nunca como recomendacao.

    Nota de execucao (BLK-GRAPH-02): o plano pedia a string `python -m graphify . --update`
    AUSENTE do `CLAUDE.md`, mas o proprio texto literal da §7 aprovado no mesmo plano cita a
    string dentro de uma negacao ("... NAO faz isso"). As duas exigencias sao incompativeis ao pe
    da letra. Resolvido pela INTENCAO, que o nome do teste declara: o contrato e' "nao recomendar".
    Advertir e o oposto de recomendar -- e apagar a advertencia perderia informacao medida.
    """
    texto = _ler(CLAUDE_MD)
    assert "/graphify . --update" in texto, (
        "sumiu do `CLAUDE.md` a forma CORRETA de atualizar a camada semantica: o SLASH-COMMAND "
        "`/graphify . --update`, rodado numa sessao Claude."
    )

    errada = "python -m graphify . --update"
    inicio = 0
    while (i := texto.find(errada, inicio)) != -1:
        contexto = texto[i : i + len(errada) + 60]
        assert "NAO faz isso" in contexto, (
            "o `CLAUDE.md` cita `python -m graphify . --update` fora de uma advertencia. MEDIDO "
            "2026-07-28: o CLI reescreve para `extract . --update`, o flag e IGNORADO EM SILENCIO "
            "e o que roda e uma extracao COMPLETA com LLM. Use `/graphify . --update`."
        )
        inicio = i + len(errada)


def test_dec_019_registrada_como_aprovada() -> None:
    assert "**PROPOSTA**" not in _ler(DEC_019), (
        "`docs/decisions/DEC-019.md` ainda se declara PROPOSTA. Ela foi APROVADA por Vinicius "
        "Cruz (@VinhoAbencoado) em 2026-07-28 e ja estava implementada no `guard.yml` desde "
        "2026-07-23 -- este e exatamente o drift registro-vs-codigo que o bloco veio consertar."
    )
    linhas = [ln for ln in _ler(CLAUDE_MD).splitlines() if "DEC-019" in ln and ln.startswith("|")]
    assert linhas, "a linha da DEC-019 sumiu do indice do §8 do `CLAUDE.md`."
    for ln in linhas:
        assert ln.rstrip().endswith("| APROVADA |"), (
            f"o indice do §8 ainda nao registra a DEC-019 como APROVADA: {ln!r}"
        )


# --------------------------------------------------------------------------------------
# Runbook
# --------------------------------------------------------------------------------------


def test_runbook_do_grafo_existe_e_documenta_as_duas_limitacoes_gemeas() -> None:
    texto = _ler(RUNBOOK)
    for ancora, porque in (
        ("core.hooksPath", "limitacao gemea 2: o git nao aplica `core.hooksPath` vindo do repo"),
        ("enabledMcpjsonServers", "limitacao gemea 1: `.mcp.json` pede aprovacao na 1a sessao"),
        ("--group graph", "o comando de instalacao"),
        ("mcp", "o porque do pin `mcp<2`"),
    ):
        assert ancora in texto, f"`docs/grafo_conhecimento.md` nao documenta {ancora!r} ({porque})."

    assert "grafo_conhecimento.md" in _ler(RAIZ / "docs" / "README.md"), (
        "`docs/README.md` (indice tematico canonico) nao referencia o runbook novo -- doc fora do "
        "indice e doc que ninguem acha."
    )


def test_script_de_prova_funcional_esta_versionado_e_cobre_as_dez_tools() -> None:
    """A prova funcional e ferramenta de REGRESSAO, nao rascunho de sessao.

    Quando o graphify passar a suportar `mcp 2.x`, reconferir o pin precisa ser UM comando.
    """
    texto = _ler(RAIZ / "scripts" / "verify_mcp_graphify.py")
    for tool in TOOLS_ESPERADAS:
        assert tool in texto, (
            f"`scripts/verify_mcp_graphify.py` nao verifica a tool {tool!r}. O handshake real de "
            "2026-07-28 devolveu exatamente 10 tools; conferir menos e afrouxar a prova."
        )
