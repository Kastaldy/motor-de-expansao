"""Migrations aplicaveis (`src/motor_expansao/db/migracoes/`) — F1.2/F1.3 do Marco B.

Os `.sql` daqui sao GERADOS do `banco-de-reservas` por `scripts/extrair_migracoes.py`, que
NAO roda no CI: aquela pasta e' outro repositorio, e o CI do motor nao a tem. Entao a
verificacao de que documentacao e migration continuam iguais acontece em dois tempos:

  * na estacao de trabalho -- `extrair_migracoes.py --conferir`, com os dois repos lado a
    lado, prova que o `.sql` versionado e' o que a documentacao diz hoje;
  * aqui, sempre -- o manifesto prova que ninguem editou um `.sql` versionado sem passar
    pelo extrator. E' o defeito que a `convencoes.md` §7 proibe por prosa ("nunca edicao
    destrutiva de uma migration ja' aplicada") e que estes testes passam a pegar.

O gate de SINTAXE usa o parser real do PostgreSQL, offline. Ele existe porque nenhum
comando SQL parte do desenvolvimento (decisao de 25/08): sem ele, um erro de sintaxe so'
apareceria quando o arquivo chegasse em quem aplica.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

MIGRACOES = Path(__file__).resolve().parents[2] / "src" / "motor_expansao" / "db" / "migracoes"
MANIFESTO = MIGRACOES / "manifesto.json"

#: Contagem conferida contra o DUMP do cluster real (`pg_dump --schema-only`, 26/08/2026),
#: que fechou os seis numeros da §0 da `verificacao.md` em 11/42/12/11/5/7 -- indices foram a 43
#: na D23 (`idx_usuarios_login_ativo`) e a 46 na D24 (os tres de `metadados`); TRIGGERS foram a 7
#: na D29 (a guarda de coerencia em `areas_estudo` e `contratos`, migration 017), que tambem
#: levou as FUNCOES de 7 a 8. Sao estes os objetos que as migrations tem de criar -- se um sumir
#: daqui, o banco novo nasce diferente do que ja' esta no ar, e nenhum teste de sintaxe pegaria.
#: A 018 (D30, `sessoes`) somou 1 TABELA e 2 INDICES explicitos, e NENHUMA trigger/funcao: a
#: coluna `ultimo_acesso_em_sessao` e' escrita pela aplicacao de proposito, porque uma trigger
#: `BEFORE UPDATE` tambem dispararia na REVOGACAO e diria que a sessao foi usada no instante em
#: que ela morreu.
OBJETOS_ESPERADOS = {
    "CREATE TABLE": 12,
    "CREATE TRIGGER": 7,
}
INDICES_ESPERADOS = 35   # +1 na D23 (login), +3 na D24 (metadados) e +2 na D30 (sessoes)
FUNCOES_ESPERADAS = 8    # +1 na D29 (`exige_geom_coerente`, uma so' para as duas tabelas)


def _sql() -> list[Path]:
    return sorted(MIGRACOES.glob("*.sql"))


def _manifesto() -> dict:
    return json.loads(MANIFESTO.read_text(encoding="utf-8"))


def test_manifesto_cobre_todos_os_arquivos() -> None:
    arquivos = {p.name for p in _sql()}
    no_manifesto = {item["arquivo"] for item in _manifesto()["migracoes"]}
    assert arquivos == no_manifesto, "manifesto e diretorio divergem — regenere o extrator"


def test_nenhum_sql_foi_editado_a_mao() -> None:
    """O manifesto guarda o sha256 de cada arquivo GERADO. Editar um `.sql` direto — para
    'so' consertar uma coisinha' — quebra a ordem que a `convencoes.md` §7 estabelece:
    modelo muda primeiro na documentacao, depois vira migration."""
    for item in _manifesto()["migracoes"]:
        caminho = MIGRACOES / item["arquivo"]
        # `read_text` normaliza fim de linha (universal newlines), que e' exatamente o
        # que o extrator faz ao calcular o hash. Ler os BYTES crus faria o teste falhar
        # numa estacao Windows com `core.autocrlf` e passar no CI Linux — a pior forma
        # de falhar, porque o defeito viveria so' na maquina de quem revisa.
        atual = hashlib.sha256(caminho.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
        assert atual == item["sha256_arquivo"], (
            f"{item['arquivo']} nao bate com o manifesto. Se a documentacao mudou, rode "
            "`python scripts/extrair_migracoes.py --origem <.../banco-de-reservas/sql>`; "
            "se voce editou o .sql a mao, desfaca e mude a documentacao primeiro."
        )


def test_versoes_sao_sequenciais_e_sem_buraco() -> None:
    """A ordem do manifesto E' a ordem de aplicacao; buraco na numeracao significa
    migration perdida, e o runner caminharia por cima da falta sem perceber."""
    versoes = [item["versao"] for item in _manifesto()["migracoes"]]
    assert versoes == sorted(versoes), "manifesto fora de ordem"
    assert versoes == [f"{n:03d}" for n in range(len(versoes))], (
        f"buraco na numeracao: {versoes}"
    )


def test_a_000_e_nativa_do_motor_e_as_demais_vem_da_documentacao() -> None:
    """A `000` cria a tabela de controle: e' infraestrutura do motor, nao modelo de
    dominio, e por isso nao tem documento no `banco-de-reservas`. Qualquer OUTRA sem
    documento seria migration escrita a mao por fora do fluxo da `convencoes.md` §7."""
    por_versao = {item["versao"]: item["documento"] for item in _manifesto()["migracoes"]}
    assert por_versao["000"] is None
    sem_documento = [v for v, doc in por_versao.items() if doc is None]
    assert sem_documento == ["000"], f"migrations sem documento de origem: {sem_documento}"


def test_nenhuma_migration_carrega_rollback() -> None:
    """Cada documento traz um bloco de rollback ao final, e varios trazem testes que
    FALHAM de proposito. O extrator pega so' o PRIMEIRO bloco ```sql — se um `DROP`
    aparecer aqui, a regra furou e uma migration apagaria o que acabou de criar."""
    for caminho in _sql():
        texto = caminho.read_text(encoding="utf-8")
        for proibido in ("DROP TABLE", "DROP FUNCTION", "DROP TRIGGER", "DROP EXTENSION"):
            assert proibido not in texto, f"{caminho.name} contem {proibido} (bloco de rollback?)"


def test_migrations_sao_transacionais_menos_a_de_extensoes() -> None:
    """`sql/README.md`: "As migrations 002-010 sao inteiras transacionais: se um comando
    falhar, o Query Tool aborta o lote e nada daquele documento e' aplicado". A 001 fica
    de fora porque cria extensoes."""
    for caminho in _sql():
        texto = caminho.read_text(encoding="utf-8")
        if caminho.name.startswith("001"):
            continue
        assert "BEGIN;" in texto and "COMMIT;" in texto, f"{caminho.name} nao e' transacional"


def _nomes_criados(linhas: list[str], padrao: str) -> set[str]:
    """Nomes DISTINTOS de objeto criado, nao ocorrencias de `CREATE`.

    Contar ocorrencias quebra assim que uma migration usa `CREATE OR REPLACE` para
    endurecer uma funcao que ja' existe (foi o que a `011` fez com as cinco de
    auditoria): o cluster continua com 7 funcoes, mas as linhas viram 12. O que tem de
    bater com o dump e' o CONJUNTO de objetos, nao quantas vezes o DDL os menciona.
    """
    achados = set()
    for linha in linhas:
        encontrado = re.match(padrao, linha)
        if encontrado:
            achados.add(encontrado.group(1).lower())
    return achados


def test_objetos_criados_batem_com_o_cluster_real() -> None:
    # So' as migrations do MODELO: a `000` cria a tabela de controle do motor, que nao
    # esta entre as 11 nem e' contada pela §0 da `verificacao.md` (que filtra por lista
    # nominal). Somar as duas aqui faria o numero deixar de significar o modelo.
    do_modelo = [p for p in _sql() if not p.name.startswith("000")]
    todo = "\n".join(p.read_text(encoding="utf-8") for p in do_modelo)
    linhas = todo.splitlines()

    tabelas = _nomes_criados(linhas, r"CREATE TABLE (\w+)")
    assert len(tabelas) == OBJETOS_ESPERADOS["CREATE TABLE"], sorted(tabelas)

    triggers = _nomes_criados(linhas, r"CREATE TRIGGER (\w+)")
    assert len(triggers) == OBJETOS_ESPERADOS["CREATE TRIGGER"], sorted(triggers)

    # `IF NOT EXISTS` e' obrigatorio no padrao: o `sql/README.md` declara os blocos
    # "idempotentes onde da' (IF NOT EXISTS em extensoes e indices)", entao sem ele o
    # grupo capturaria o literal `IF` e os 29 nomes colapsariam num so'.
    indices = _nomes_criados(linhas, r"CREATE (?:UNIQUE )?INDEX (?:IF NOT EXISTS )?(\w+)")
    assert len(indices) == INDICES_ESPERADOS, sorted(indices)

    funcoes = _nomes_criados(linhas, r"CREATE (?:OR REPLACE )?FUNCTION (\w+)")
    assert len(funcoes) == FUNCOES_ESPERADAS, sorted(funcoes)


def test_auditoria_de_rbac_continua_endurecida() -> None:
    """As duas funcoes do D19 sao `SECURITY DEFINER`, e por isso o `search_path` fixo nao
    e' estilo: sem `pg_temp` listado, o Postgres o pesquisa PRIMEIRO e qualquer papel
    sequestra a auditoria com uma tabela temporaria de mesmo nome. Perder estas duas
    linhas numa reextracao seria invisivel — o SQL continuaria valido."""
    texto = (MIGRACOES / "009-historico-perfil-permissoes.sql").read_text(encoding="utf-8")
    # Contar so' o que e' CODIGO: o proprio documento explica em comentario por que o
    # `pg_temp` vai no fim, e contar a prosa junto daria um numero que nao significa nada.
    codigo = [
        linha for linha in texto.splitlines() if not linha.lstrip().startswith("--")
    ]
    definer = sum(1 for linha in codigo if "SECURITY DEFINER" in linha)
    caminho = sum(
        1 for linha in codigo if "SET search_path = pg_catalog, public, pg_temp" in linha
    )
    # 2 gravadoras (`registra_*`, as unicas SECURITY DEFINER) e 4 com search_path fixo:
    # as duas acima mais `rotulo_perfil`/`rotulo_permissao`, que sao STABLE mas leem
    # tabela e cairiam no mesmo sequestro por `pg_temp`.
    assert definer == 2, f"SECURITY DEFINER em {definer} funcoes, esperado 2"
    assert caminho == 4, f"search_path fixo em {caminho} funcoes, esperado 4"


def test_sintaxe_aceita_pelo_parser_do_postgres() -> None:
    """Gate offline: o parser REAL do PostgreSQL (libpg_query) le cada migration.

    Nao substitui a verificacao contra o banco — nao enxerga coluna inexistente nem erro
    de tipo. Cobre a classe de erro que, sem ele, so' apareceria do outro lado.
    """
    # ONDE ESTE GATE NAO RODA, e por que (medido em 31/08/2026):
    #   * estacao Windows com Controle de Aplicativo: o `pglast` usa `libpg_query`, uma DLL
    #     nativa, e a politica do sistema BLOQUEIA o carregamento -- mesmo instalado, o
    #     import falha. Nao ha contorno em codigo;
    #   * `sqlglot` (Python puro) seria a alternativa, mas nao tem distribuicao para o
    #     Python 3.14 desta estacao; `sqlparse` so' tokeniza, nao valida sintaxe.
    # Onde ele ROda: no CI (Linux, sem essa politica), com o `pglast` do lockfile. Enquanto
    # nao houver PR, a validacao efetiva e' a APLICACAO no banco -- o Postgres e' o unico
    # que valida de verdade, inclusive o corpo `plpgsql`, que este gate nunca alcanca.
    pglast = pytest.importorskip(
        "pglast",
        reason=(
            "pglast indisponivel (nao instalado, ou DLL bloqueada por politica do SO). "
            "O gate roda no CI; localmente, quem valida e' aplicar no banco."
        ),
    )
    for caminho in _sql():
        try:
            statements = pglast.parse_sql(caminho.read_text(encoding="utf-8"))
        except Exception as erro:  # noqa: BLE001 - o proprio parser define o tipo
            pytest.fail(f"{caminho.name}: {erro}")
        assert statements, f"{caminho.name} nao produziu statement nenhum"
