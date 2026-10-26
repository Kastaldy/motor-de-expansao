"""A passada completa do login, contra um Postgres DE VERDADE (P19: D30 + D31).

POR QUE ESTE ARQUIVO EXISTE
---------------------------
Todo o resto da epic foi verificado com DUBLÊS: até 24/10/2026 o CI não tinha Postgres (decisão
de 25/08/2026), então `SQL_VALIDAR`, `SQL_CONTAR_RECUSAS`, o `ck_usuarios_prazo_exige_troca` da
019 e o `GREATEST` com `-infinity` só passavam por validação de SINTAXE (`pglast`) e por objetos
falsos que respondem no lugar do banco. Sintaxe correta e comportamento correto são coisas
diferentes, e a distância entre as duas é exatamente o que este arquivo mede.

Ele também é o teste de fumaça para o dia do corte: é o que se roda antes de virar a chave
`MOTOR_AUTENTICACAO_PROPRIA` em qualquer lugar. E é onde os dois instrumentos do operador,
`db conferir` e `db privilegios`, encontram o catálogo de verdade.

NO CI
-----
O job `test` sobe o MESMO PostGIS do `docker-compose.prod.yml`, aplica as migrations do zero e
roda este arquivo (`scripts/ci/banco_de_ensaio.sh verificar`), DEPOIS da suíte unitária -- que
segue sem variável de banco, e onde este arquivo pula como sempre. No passo do banco vale
`MOTOR_BANCO_DE_ENSAIO_OBRIGATORIO=1`: todo pulo por ambiente ausente vira FALHA (ver
`_pular_ou_falhar`), porque um passo que pula fica verde sem ter testado nada.

O banco do CI não tem o D20: os papéis vivem no `banco-de-reservas` e não são recriados aqui. Os
testes do `conferir` e do `privilegios` sabem disso e cobram o que dá para cobrar sem ele.

COMO RODAR
----------
O jeito curto é o comando do CI, no Git Bash, a partir da raiz desta árvore:

    PYTHONPATH="$PWD/src" CI_BANCO_NOME=ci_banco_ensaio_local \\
        bash scripts/ci/banco_de_ensaio.sh verificar
    CI_BANCO_NOME=ci_banco_ensaio_local bash scripts/ci/banco_de_ensaio.sh derrubar

À mão, precisa de um Postgres de ENSAIO migrado até a última migration do manifesto. O caminho
está em `docs/banco_deploy.md` §"Ensaio local"; em resumo:

    docker run -d --name motor-ensaio -e POSTGRES_PASSWORD=<senha> -p 5432:5432 \\
        postgis/postgis:18-3.6
    # criar o banco `banco_de_reservas_ensaio` e o papel `app` conforme o doc
    $env:MOTOR_DATABASE_URL_ADMIN = "postgresql://postgres:<senha>@localhost:5432/banco_de_reservas_ensaio"
    python -m motor_expansao.db aplicar
    python -m pytest tests/integration/test_login_ponta_a_ponta.py -v

Sem a variável, ou com o banco não migrado, a suíte PULA com o motivo escrito. Fora do CI ela
nunca falha por ausência de ambiente -- falhar assim treinaria todo mundo a ignorar vermelho.

TRAVA DE DESTINO
----------------
Este arquivo CRIA usuário, REDEFINE senha e escreve em `eventos`. Apontá-lo para produção por
engano seria estrago real e irreversível (`eventos` é append-only). Por isso ele recusa rodar
se o nome do banco não disser `ensaio` ou `test`, e recusa também uma `MOTOR_DATABASE_URL`
que aponte para OUTRO banco: é por ela que a aplicação escreve -- ver
`_exigir_banco_de_ensaio`.
"""

from __future__ import annotations

import os
import time
import uuid
from typing import Any, NoReturn

import pytest

#: No passo do banco no CI esta variável vale `1` (`scripts/ci/banco_de_ensaio.sh`), e ali o banco
#: de ensaio EXISTE por construção: pular por "ambiente ausente" deixaria o passo verde sem ter
#: testado nada. Com ela, todo pulo deste arquivo vira FALHA, com o mesmo motivo. Fora do CI ela
#: não existe, e pular continua sendo o desenho (ver o cabeçalho).
ENV_OBRIGATORIO = "MOTOR_BANCO_DE_ENSAIO_OBRIGATORIO"


def _obrigatorio() -> bool:
    return os.environ.get(ENV_OBRIGATORIO, "").strip() == "1"


def _pular_ou_falhar(motivo: str) -> NoReturn:
    """Pula -- ou, com `MOTOR_BANCO_DE_ENSAIO_OBRIGATORIO=1`, FALHA pelo mesmo motivo."""
    if _obrigatorio():
        pytest.fail(f"{ENV_OBRIGATORIO}=1 e este teste ia PULAR: {motivo}", pytrace=False)
    pytest.skip(motivo)


if _obrigatorio():
    import psycopg  # sem o driver, o passo do CI QUEBRA na coleta em vez de pular o arquivo
else:
    psycopg = pytest.importorskip("psycopg")

from motor_expansao.db import cli  # noqa: E402
from motor_expansao.db import eventos as db_eventos  # noqa: E402
from motor_expansao.db import postgres as db_postgres  # noqa: E402
from motor_expansao.db import senhas as db_senhas  # noqa: E402
from motor_expansao.db import sessoes as db_sessoes  # noqa: E402
from motor_expansao.db import usuarios as db_usuarios  # noqa: E402

#: Senhas do ensaio. Bem acima de `senhas.MINIMO_DE_CARACTERES` (8 desde 25/09/2026; era 12) e
#: sem forma de credencial real -- este arquivo é lido
#: por gente, e "senha de exemplo" no fonte é como um literal vira default de verdade depois.
SENHA_ESCOLHIDA = "cavalo-bateria-grampo"
SENHA_SEGUINTE = "outra-frase-comprida"


def _url() -> str | None:
    return os.environ.get(cli.ENV_URL_ADMIN) or os.environ.get("MOTOR_DATABASE_URL")


def _destino(url: str) -> tuple[str, str, str]:
    """(servidor, porta, banco) de uma URL de conexão -- o que define ONDE se escreve.

    Usuário e senha ficam de fora de propósito: no runbook (§1.2) a `MOTOR_DATABASE_URL` é o
    papel `app` no MESMO banco da credencial de dono, e isso é legítimo. URL ilegível RECUSA
    sem ecoar o texto dela, que carrega a senha.
    """
    from psycopg.conninfo import conninfo_to_dict

    # O `pytest.fail` fica FORA do `except` de propósito: dentro dele, o erro do psycopg -- que
    # cita o pedaço da URL que não entendeu, senha inclusive -- iria junto como contexto.
    try:
        partes: dict[str, object] | None = conninfo_to_dict(url)
    except psycopg.Error:
        partes = None
    if partes is None:
        pytest.fail(
            "RECUSADO: uma URL de banco do ambiente não é legível. O texto dela não aparece "
            "aqui porque carrega a senha; corrija-a antes de rodar esta suíte.",
            pytrace=False,
        )
    return (
        str(partes.get("host") or ""),
        str(partes.get("port") or "5432"),
        str(partes.get("dbname") or "").lower(),
    )


@pytest.fixture(scope="module")
def _exigir_banco_de_ensaio() -> None:
    """Pula sem ambiente (no CI, FALHA: `_pular_ou_falhar`); RECUSA o que não pareça de ensaio.

    NÃO é `autouse`: quem o exige é o `con`, por PARÂMETRO. Como `autouse`, o pytest não garante
    que ele rode antes dos outros fixtures de módulo, e a conexão tentava abrir com URL nula —
    a suíte morria com `AttributeError` em vez de pular limpo, que é o oposto do desenho.
    """
    url = _url()
    if not url:
        _pular_ou_falhar(
            f"{cli.ENV_URL_ADMIN} não definida — veja o cabeçalho deste arquivo para subir o "
            "Postgres de ensaio."
        )
    # O nome do banco é a última parte do caminho, antes de qualquer `?`.
    nome = url.rsplit("/", 1)[-1].split("?", 1)[0].lower()
    if "ensaio" not in nome and "test" not in nome:
        pytest.fail(
            f"RECUSADO: o banco {nome!r} não parece de ensaio. Esta suíte cria usuário, "
            "redefine senha e escreve em `eventos`, que é append-only. Aponte para um banco "
            "cujo nome contenha `ensaio` ou `test`."
        )
    # A APLICAÇÃO não usa a URL acima: `usuarios`, `sessoes` e `eventos` escrevem pelo pool da
    # `MOTOR_DATABASE_URL`, e o `_ambiente` só a preenche quando ela está vazia. Uma que tivesse
    # sobrado no terminal, apontando para OUTRO banco, recebia as escritas desta suíte sem passar
    # pela trava. Medido em 24/10/2026, com ela num segundo banco do mesmo servidor, de nome sem
    # `ensaio` nem `test`: 7 senhas de lá redefinidas, 22 linhas gravadas em `eventos`, 2 sessões
    # abertas -- e 11 dos 18 testes verdes.
    piloto = os.environ.get("MOTOR_DATABASE_URL", "").strip()
    if piloto and _destino(piloto) != _destino(url.strip()):
        pytest.fail(
            f"RECUSADO: `MOTOR_DATABASE_URL` e {cli.ENV_URL_ADMIN} apontam para bancos "
            "diferentes. A aplicação escreve pela `MOTOR_DATABASE_URL`, então esta suíte "
            "abriria sessão, redefiniria senha e gravaria em `eventos` no OUTRO banco. Aponte "
            "as duas para o mesmo banco de ensaio, ou tire a `MOTOR_DATABASE_URL` do terminal."
        )


@pytest.fixture(scope="module")
def con(_exigir_banco_de_ensaio: None) -> Any:
    """Conexão de ADMIN, para montar cenário e inspecionar o que o código escreveu.

    Banco no nome certo mas fora do ar PULA, e não quebra: é ambiente ausente, a mesma classe de
    `test_api_analisar.py` quando falta a base geo. O caso comum é a variável ter sobrado no
    terminal depois de o container parar. A mensagem diz isso com todas as letras, porque um
    "pulado" que parece "tudo certo" é pior que um vermelho. No passo do banco do CI, onde o
    banco existe por construção, o mesmo caso FALHA.
    """
    # `connect_timeout`: sem ele, com o banco fora do ar no Windows, o psycopg não percebe a recusa
    # da porta fechada e espera o próprio teto, 130 s (medido em 24/10/2026; um socket cru recebe
    # a recusa em 2 s), antes de pular ou falhar. No Linux do CI a recusa chega na hora; aqui, no
    # máximo 10 s. Banco no ar conecta em milissegundos.
    try:
        with psycopg.connect(_url(), autocommit=True, connect_timeout=10) as c:
            yield c
    except psycopg.OperationalError as erro:
        _pular_ou_falhar(
            f"NÃO RODOU: {cli.ENV_URL_ADMIN} está definida, mas o banco não respondeu "
            f"({erro.__class__.__name__}). O container de ensaio está no ar? "
            "Nada abaixo foi verificado."
        )


@pytest.fixture(scope="module", autouse=True)
def _exigir_migracoes(con: Any) -> None:
    faltando = [
        objeto
        for objeto, existe in (
            ("sessoes", con.execute("SELECT to_regclass('sessoes')").fetchone()[0]),
            (
                "usuarios.senha_expira_em_usuario",
                con.execute(
                    "SELECT 1 FROM information_schema.columns WHERE table_name = 'usuarios' "
                    "AND column_name = 'senha_expira_em_usuario'"
                ).fetchone(),
            ),
        )
        if existe is None
    ]
    if faltando:
        _pular_ou_falhar(
            f"banco não migrado (falta {', '.join(faltando)}) — rode `db aplicar` antes"
        )


@pytest.fixture(scope="module", autouse=True)
def _ambiente(con: Any) -> Any:
    """Liga a autenticação própria e garante a senha inicial, que `criar` exige.

    Na saída devolve TUDO o que mexeu -- inclusive `MOTOR_DATABASE_URL` e o pool que o código da
    aplicação abriu. Rodado junto com a suíte inteira, um módulo que deixasse a URL no ambiente
    faria os testes seguintes, que contam com "sem banco", conversarem com o banco de ensaio.
    """
    anterior = {
        k: os.environ.get(k)
        for k in (
            db_sessoes.ENV_AUTENTICACAO_PROPRIA,
            db_senhas.ENV_SENHA_INICIAL,
            "MOTOR_DATABASE_URL",
        )
    }
    os.environ[db_sessoes.ENV_AUTENTICACAO_PROPRIA] = "1"
    os.environ.setdefault(db_senhas.ENV_SENHA_INICIAL, "inicial-do-ensaio-1")
    # O piloto lê `MOTOR_DATABASE_URL`; no ensaio os dois papéis são a mesma pessoa.
    os.environ.setdefault("MOTOR_DATABASE_URL", _url() or "")
    yield
    db_postgres.fechar_pool()
    for k, v in anterior.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


@pytest.fixture(scope="module")
def admin(con: Any) -> int:
    """Quem administra no cenário. Precisa existir ANTES, porque toda escrita carimba autor."""
    return _criar_pessoa(con, "admin")


@pytest.fixture
def pessoa(con: Any, admin: int) -> dict[str, Any]:
    """Uma pessoa NOVA por teste: cada um monta o próprio cenário e não herda estado do vizinho."""
    id_usuario = _criar_pessoa(con, "alvo")
    login = con.execute(
        "SELECT login_usuario FROM usuarios WHERE id_usuario = %s", (id_usuario,)
    ).fetchone()[0]
    return {"id": id_usuario, "login": login}


def _criar_pessoa(con: Any, papel: str) -> int:
    """Insere direto, sem passar por `usuarios.criar`.

    De propósito: `criar` grava evento com autor, e o primeiro usuário do cenário não tem autor
    anterior. Montar cenário não é o que esta suíte testa.
    """
    sufixo = f"{papel}-{uuid.uuid4().hex[:8]}"
    linha = con.execute(
        "INSERT INTO usuarios (login_usuario, nome_usuario, email, senha_hash, id_perfil) "
        "VALUES (%s, %s, %s, %s, (SELECT id_perfil FROM perfis ORDER BY id_perfil LIMIT 1)) "
        "RETURNING id_usuario",
        (sufixo, f"Ensaio {sufixo}", f"{sufixo}@ensaio.local", db_senhas.gerar(SENHA_ESCOLHIDA)),
    ).fetchone()
    return int(linha[0])


def _definir_senha_propria(con: Any, id_usuario: int, senha: str) -> None:
    """Sai do estado 'deve trocar' escrevendo pelo MESMO SQL que a aplicação usa."""
    con.execute(db_usuarios.SQL_DEFINIR_SENHA, (db_senhas.gerar(senha), id_usuario))


# ======================================================================================
# 1. O SCHEMA — onde a contagem simulada em arquivo encontra o banco de verdade
# ======================================================================================


def test_os_seis_numeros_da_secao_zero_batem_com_o_banco(con: Any) -> None:
    """O momento da verdade do `CHECK = 14`.

    `test_migracoes.py` SIMULA a cadeia lendo os `.sql` e chega a 14; `cli.NUMEROS_DA_SECAO_ZERO`
    afirma 14 para o banco. Até 24/10/2026 as duas contas nunca se encontravam, porque o CI não
    tinha Postgres. Aqui elas se encontram -- e, desde então, em todo PR.
    """
    # A consulta recebe a lista NOMINAL das tabelas do modelo: a §0 conta só elas, e não o que
    # mais exista no schema. Chamá-la sem o parâmetro é erro de sintaxe, não contagem errada.
    reais = dict(con.execute(cli.SQL_CONTAGENS, (list(cli.TABELAS_DO_MODELO),)).fetchall())
    for item, esperado in cli.NUMEROS_DA_SECAO_ZERO.items():
        assert reais.get(item) == esperado, (
            f"§0 divergente em {item}: {reais.get(item)} != {esperado}"
        )
    assert reais.get("tabelas") == len(cli.TABELAS_DO_MODELO)


def test_o_CHECK_da_019_recusa_senha_propria_com_prazo(con: Any, pessoa: dict[str, Any]) -> None:
    """A razão de existir do `ck_usuarios_prazo_exige_troca`, contra o banco.

    O estado proibido é: senha que a pessoa escolheu (`deve_trocar = FALSE`) com prazo de
    validade. Se ele fosse possível, a pessoa seria barrada COM A SENHA CERTA, lendo "Login ou
    senha incorretos" — defeito mudo e de diagnóstico caro.
    """
    with pytest.raises(psycopg.errors.CheckViolation):
        con.execute(
            "UPDATE usuarios SET deve_trocar_senha_usuario = FALSE, "
            "senha_expira_em_usuario = now() + interval '1 hour' WHERE id_usuario = %s",
            (pessoa["id"],),
        )


# --------------------------------------------------------------------------------------
# Os dois instrumentos do operador, contra o catálogo de verdade (24/10/2026)
# --------------------------------------------------------------------------------------

#: O que o `privilegios` REPROVA conectado como DONO num banco sem o D20 -- o banco do CI. Ali o
#: veredito é reprovado por construção, e esta é a lista exata do "por construção": cada item tem
#: uma causa que não é defeito do banco. Problema A MAIS é algo que reprovaria também na VPS (uma
#: extensão que o D20 não governa, uma função `SECURITY DEFINER` nova, um parâmetro fixado no
#: banco) -- ou uma checagem NOVA do `privilegios` que o dono reprova por construção, e então ela
#: entra aqui, com a causa ao lado. Problema A MENOS é uma checagem que parou de enxergar, ou que
#: mudou de rótulo.
PRIVILEGIOS_COMO_DONO_SEM_D20 = frozenset(
    {
        # O dono pode tudo -- é exatamente por isso que o piloto não usa a credencial dele.
        "criar objeto no schema public",
        "escrever no historico de permissoes",
        "apagar sessao",
        "alterar o historico de permissoes",
        "apagar do historico de permissoes",
        "esvaziar perfil_permissoes",
        "alterar evento ja' gravado",
        "apagar evento",
        "criar tabela temporaria",
        "ser dono das tabelas auditadas",
        # Seção 2 do D20: os `REVOKE ... FROM PUBLIC`, que nenhum default do Postgres faz.
        "poder que a secao 2 revoga de PUBLIC esta aberto: public (TEMPORARY no banco)",
        "PUBLIC pode executar registra_perfil_permissoes_historico: "
        "falta o REVOKE EXECUTE da secao 2",
        "PUBLIC pode executar registra_perfil_permissoes_truncate: "
        "falta o REVOKE EXECUTE da secao 2",
        # Seção 6 do D20: `ALTER DEFAULT PRIVILEGES`.
        "pg_default_acl sem linha de SEQUENCES: a secao 6 nao rodou",
        "pg_default_acl sem linha de TABLES: a secao 6 nao rodou",
        # Seção 7 do D20: `ENABLE ALWAYS` nas duas triggers de auditoria.
        "trigger trg_perfil_permissoes_auditoria fora de ENABLE ALWAYS",
        "trigger trg_perfil_permissoes_auditoria_truncate fora de ENABLE ALWAYS",
    }
)


def _problemas(saida: str, cabecalho: str) -> list[str]:
    """As linhas `  - ...` do bloco que `conferir`/`privilegios` imprimem no fim ao reprovar.

    Lê a SAÍDA, e não uma estrutura interna, de propósito: o operador decide pelo que o comando
    imprime, e é isso que tem de dizer a verdade. Veredito OK (sem bloco) devolve lista vazia.
    """
    _, achou, resto = saida.partition(cabecalho)
    if not achou:
        return []
    cabeca, *linhas = resto.splitlines()
    problemas = []
    for linha in linhas:
        if not linha.startswith("  - "):
            break
        problemas.append(linha.removeprefix("  - "))
    anunciados = int(cabeca.split()[0])
    assert anunciados == len(problemas), (
        f"o cabeçalho anuncia {anunciados} problema(s) e o bloco lista {len(problemas)}:\n{saida}"
    )
    return problemas


def _triggers_de_auditoria(con: Any) -> dict[str, str]:
    """`tgname -> tgenabled` das triggers da tabela auditada; 'A' só existe depois do D20."""
    linhas = con.execute(
        db_postgres.SQL_TRIGGERS_AUDITORIA, (db_postgres.TABELA_AUDITADA,)
    ).fetchall()
    return {nome: estado for nome, estado in linhas}


def test_o_conferir_aprova_tudo_que_nao_depende_do_D20(con: Any, capsys: Any) -> None:
    """`db conferir` inteiro contra o banco de verdade: o comando que o runbook manda rodar na VPS.

    O banco do CI nasce SEM o D20: o script de papéis vive no `banco-de-reservas` e não é recriado
    aqui, porque um D20 inventado provaria o inventado, e não o real. Sem ele o `conferir` reprova
    POR CONSTRUÇÃO -- é o fail-closed do #447: trigger de auditoria fora de 'A' é problema, não
    aviso. Então há duas respostas legítimas, e o teste lê do catálogo qual vale:

    * sem o D20 (o CI): os ÚNICOS problemas são as triggers fora de 'A', uma linha por trigger.
      Extensões, os seis números da §0, o endurecimento das funções (D19/D21) e o registro das
      migrations têm de passar, todos, contra o PostgreSQL de produção;
    * com o D20 (o ensaio do runbook, §1.2): `CONFERENCIA OK`, código 0.
    """
    triggers = _triggers_de_auditoria(con)
    assert triggers, "nenhuma trigger de auditoria em `perfil_permissoes` — a 009 não aplicou?"

    codigo = cli.main(["conferir"])
    saida = capsys.readouterr().out
    problemas = _problemas(saida, "CONFERENCIA COM ")

    fora_de_a = {nome: estado for nome, estado in triggers.items() if estado != "A"}
    if not fora_de_a:
        assert (codigo, problemas) == (0, []), saida
        assert "CONFERENCIA OK" in saida, saida
        return

    assert codigo == 1, saida
    por_trigger = {
        nome: [p for p in problemas if p.startswith(f"trigger `{nome}` em '{estado}', nao 'A'")]
        for nome, estado in fora_de_a.items()
    }
    alheios = [p for p in problemas if not any(p in lista for lista in por_trigger.values())]
    assert not alheios, (
        "o `conferir` reprovou por algo que NÃO é a ausência do D20:\n"
        + "\n".join(alheios)
        + "\n\nOu é defeito do banco, que reprovaria também na VPS, ou é uma checagem NOVA do "
        "`conferir` que depende do D20 -- e então este teste precisa aprender a reconhecê-la, "
        "como já reconhece as triggers fora de 'A'."
    )
    fora_do_relatorio = sorted(nome for nome, lista in por_trigger.items() if len(lista) != 1)
    assert not fora_do_relatorio, (
        "sem o D20, cada trigger fora de 'A' tem de aparecer UMA vez entre os problemas do "
        f"`conferir`: {fora_do_relatorio}\n{saida}"
    )


def test_o_privilegios_roda_inteiro_no_catalogo_real(con: Any, capsys: Any) -> None:
    """`db privilegios` contra o catálogo de verdade: tudo o que dá para provar sem o papel `app`.

    O VEREDITO deste comando só vale conectado como `app`, e o `app` nasce do D20, que o CI não
    tem (ver o teste do `conferir`, acima). Esse veredito segue manual: ensaio do runbook (§1.2) e
    VPS. O que se prova aqui, em todo PR:

    * as consultas de catálogo dele EXECUTAM no PostgreSQL de produção -- erro de SQL nelas só
      apareceria no dia do repasse, na mão do operador;
    * todo objeto que ele pergunta EXISTE depois das migrations: uma migration que renomeasse a
      sequence de `eventos` faria o instrumento diagnosticar "migration pendente" num banco em dia;
    * conectado como DONO e sem o D20, ele reprova EXATAMENTE pelo que o dono e a falta do D20
      explicam (`PRIVILEGIOS_COMO_DONO_SEM_D20`) -- nem um item a mais, nem um a menos.

    Conectado como `app` (a `MOTOR_DATABASE_URL` do runbook, com o D20 de pé), exige
    `PRIVILEGIOS OK`.
    """
    dono = con.execute(
        "SELECT pg_get_userbyid(relowner) FROM pg_class WHERE oid = to_regclass(%s)",
        (db_postgres.TABELA_AUDITADA,),
    ).fetchone()[0]
    triggers = _triggers_de_auditoria(con)
    assert triggers, "nenhuma trigger de auditoria em `perfil_permissoes` — a 009 não aplicou?"
    estados = set(triggers.values())

    codigo = cli.main(["privilegios"])
    saida = capsys.readouterr().out
    problemas = _problemas(saida, "PRIVILEGIOS COM ")

    assert "o objeto nao existe" not in saida, (
        "o `privilegios` perguntou por objeto que as migrations não criaram:\n" + saida
    )
    conectado = saida.splitlines()[0].removeprefix("papel conectado:").strip()

    if conectado != dono:
        assert (codigo, problemas) == (0, []), saida
        assert "PRIVILEGIOS OK" in saida, saida
    elif "A" not in estados:  # nada do D20 de pé: o banco do CI
        assert codigo == 1, saida
        a_mais = sorted(set(problemas) - PRIVILEGIOS_COMO_DONO_SEM_D20)
        a_menos = sorted(PRIVILEGIOS_COMO_DONO_SEM_D20 - set(problemas))
        assert not a_mais, (
            "o `privilegios` reprovou por algo que o dono e a falta do D20 NÃO explicam:\n"
            + "\n".join(a_mais)
            + "\n\nDuas causas possíveis. (1) Defeito que reprovaria também na VPS: banco "
            "nascido do initdb da imagem, sem o `tmpfs` do compose, cai aqui -- suba pelo "
            "`scripts/ci/banco_de_ensaio.sh`. (2) Checagem NOVA no `privilegios` que o dono "
            "reprova por construção, porque o dono pode tudo: acrescente o rótulo dela a "
            "`PRIVILEGIOS_COMO_DONO_SEM_D20`, com a causa ao lado."
        )
        assert not a_menos, (
            "sem o D20 e conectado como dono, o `privilegios` deixou de acusar -- a checagem parou "
            "de enxergar, ou mudou de rótulo (se foi de propósito, atualize "
            "`PRIVILEGIOS_COMO_DONO_SEM_D20`):\n" + "\n".join(a_menos)
        )
    elif estados != {"A"}:
        pytest.fail(
            f"D20 pela metade: as triggers de auditoria estão em {triggers}. A seção 7 dele tem "
            "DUAS linhas `ALTER TABLE`; rode-a inteira antes de conferir os privilégios."
        )
    # Dono COM o D20: como dono, o veredito é reprovado por construção e não diz nada sobre o
    # banco; o que vale para este caso já foi cobrado acima (rodou inteiro, nenhum objeto ausente).


# ======================================================================================
# 2. A PASSADA — o caminho que uma pessoa real percorre
# ======================================================================================


def test_entra_com_a_senha_certa(con: Any, pessoa: dict[str, Any]) -> None:
    _definir_senha_propria(con, pessoa["id"], SENHA_ESCOLHIDA)
    credencial = db_usuarios.credenciais_por_login(pessoa["login"])

    assert credencial is not None
    assert db_senhas.verificar(SENHA_ESCOLHIDA, credencial.senha_hash)
    assert credencial.expira_em is None, "senha escolhida pela pessoa não expira"

    aberta = db_sessoes.abrir(id_usuario=pessoa["id"])
    valida = db_sessoes.validar(aberta.token)
    assert valida is not None
    assert valida.identidade.id_usuario == pessoa["id"]


def test_cinco_recusas_trancam_a_conta(con: Any, pessoa: dict[str, Any]) -> None:
    """A trava conta o que `login.recusado` gravou, na janela móvel."""
    _definir_senha_propria(con, pessoa["id"], SENHA_ESCOLHIDA)
    for _ in range(db_sessoes.MAX_TENTATIVAS):
        db_eventos.registrar_login_recusado(autor=pessoa["id"], usuario_conhecido=True)

    recusas = db_eventos.contar_recusas_recentes(
        id_usuario=pessoa["id"], minutos=db_sessoes.JANELA_TENTATIVAS_MIN
    )
    assert recusas >= db_sessoes.MAX_TENTATIVAS


def test_o_ACERTO_zera_a_contagem(con: Any, pessoa: dict[str, Any]) -> None:
    """Pedido do dono em 22/09. Sem isto, errar três vezes, entrar e errar mais duas trancaria
    quem provou saber a senha dois minutos antes."""
    for _ in range(3):
        db_eventos.registrar_login_recusado(autor=pessoa["id"], usuario_conhecido=True)
    assert (
        db_eventos.contar_recusas_recentes(
            id_usuario=pessoa["id"], minutos=db_sessoes.JANELA_TENTATIVAS_MIN
        )
        == 3
    )

    time.sleep(1)  # o piso é `>`, então o acerto precisa ser posterior às recusas no relógio
    db_eventos.registrar_login(autor=pessoa["id"])

    assert (
        db_eventos.contar_recusas_recentes(
            id_usuario=pessoa["id"], minutos=db_sessoes.JANELA_TENTATIVAS_MIN
        )
        == 0
    ), "o acerto não zerou a contagem — a subconsulta do último `login` não está pegando"


def test_a_REDEFINICAO_destrava_e_entrega_senha_que_funciona(
    con: Any, pessoa: dict[str, Any], admin: int
) -> None:
    """O caso típico do pedido de ajuda, inteiro: errar cinco vezes, ligar, receber, entrar."""
    _definir_senha_propria(con, pessoa["id"], SENHA_ESCOLHIDA)
    for _ in range(db_sessoes.MAX_TENTATIVAS):
        db_eventos.registrar_login_recusado(autor=pessoa["id"], usuario_conhecido=True)
    assert (
        db_eventos.contar_recusas_recentes(
            id_usuario=pessoa["id"], minutos=db_sessoes.JANELA_TENTATIVAS_MIN
        )
        >= db_sessoes.MAX_TENTATIVAS
    )

    time.sleep(1)
    resultado = db_usuarios.redefinir_senha(pessoa["id"], autor=admin)
    temporaria = resultado["senha_temporaria"]

    credencial = db_usuarios.credenciais_por_login(pessoa["login"])
    assert credencial is not None
    assert db_senhas.verificar(temporaria, credencial.senha_hash), (
        "a senha entregue ao admin NÃO abre a conta — o texto e o hash se desencontraram"
    )
    assert credencial.deve_trocar is True
    assert credencial.expira_em is not None
    assert credencial.redefinida_em is not None

    # O piso da redefinição zera a contagem: sem isto ela receberia a senha nova e seguiria
    # barrada por até 15 minutos, lendo a mesma mensagem de senha errada.
    assert (
        db_eventos.contar_recusas_recentes(
            id_usuario=pessoa["id"],
            minutos=db_sessoes.JANELA_TENTATIVAS_MIN,
            redefinida_em=credencial.redefinida_em,
        )
        == 0
    ), "a redefinição não destravou a conta"


def test_duas_redefinicoes_dao_senhas_diferentes(pessoa: dict[str, Any], admin: int) -> None:
    """Gerar outra INVALIDA a anterior — é assim que "rever a senha" foi resolvido sem guardar
    nada recuperável no banco."""
    primeira = db_usuarios.redefinir_senha(pessoa["id"], autor=admin)["senha_temporaria"]
    segunda = db_usuarios.redefinir_senha(pessoa["id"], autor=admin)["senha_temporaria"]
    assert primeira != segunda

    credencial = db_usuarios.credenciais_por_login(pessoa["login"])
    assert credencial is not None
    assert db_senhas.verificar(segunda, credencial.senha_hash)
    assert not db_senhas.verificar(primeira, credencial.senha_hash), (
        "a senha anterior continuou valendo depois de gerar outra"
    )


def test_a_temporaria_VENCIDA_deixa_de_abrir(con: Any, pessoa: dict[str, Any], admin: int) -> None:
    """Empurra o prazo para o passado e confere que a senha, ainda correta, não vale mais."""
    temporaria = db_usuarios.redefinir_senha(pessoa["id"], autor=admin)["senha_temporaria"]
    con.execute(
        "UPDATE usuarios SET senha_expira_em_usuario = now() - interval '1 minute' "
        "WHERE id_usuario = %s",
        (pessoa["id"],),
    )

    credencial = db_usuarios.credenciais_por_login(pessoa["login"])
    assert credencial is not None
    # A senha CONFERE: quem recusa é o prazo, e é por isso que a checagem vive na rota.
    assert db_senhas.verificar(temporaria, credencial.senha_hash)
    assert credencial.expira_em is not None
    from datetime import UTC, datetime

    assert credencial.expira_em <= datetime.now(UTC), "o prazo não ficou no passado"


def test_trocar_a_propria_senha_LIMPA_o_prazo(con: Any, pessoa: dict[str, Any], admin: int) -> None:
    """Fecha o ciclo: da temporária para a senha da pessoa, sem deixar prazo para trás.

    Se `SQL_DEFINIR_SENHA` parasse de zerar o prazo, o `CHECK` da 019 recusaria a escrita e este
    teste ficaria vermelho AQUI, com `CheckViolation` — que é exatamente o que se quer, porque o
    outro caminho seria a pessoa barrada com a senha certa semanas depois.
    """
    db_usuarios.redefinir_senha(pessoa["id"], autor=admin)
    assert db_usuarios.credenciais_por_login(pessoa["login"]).expira_em is not None

    _definir_senha_propria(con, pessoa["id"], SENHA_SEGUINTE)

    credencial = db_usuarios.credenciais_por_login(pessoa["login"])
    assert credencial is not None
    assert credencial.expira_em is None, "a senha própria ficou com prazo de validade"
    assert credencial.deve_trocar is False
    assert db_senhas.verificar(SENHA_SEGUINTE, credencial.senha_hash)


def test_a_marca_de_troca_fica_no_banco_e_NAO_barra_a_sessao(
    con: Any, pessoa: dict[str, Any], admin: int
) -> None:
    """Redefinir marca a coluna, e a sessão abre e vale assim mesmo.

    Entre 18/09 e 25/09/2026 esta marca BARRAVA as rotas de dados; o dono reverteu para
    RECOMENDADA. As duas metades são medidas aqui contra o banco real: a coluna continua sendo
    escrita (é dela que `/api/me` monta o convite da tela) e a sessão continua válida.
    """
    db_usuarios.redefinir_senha(pessoa["id"], autor=admin)

    with con.cursor() as cur:
        cur.execute(
            "SELECT deve_trocar_senha_usuario FROM usuarios WHERE id_usuario = %s",
            (pessoa["id"],),
        )
        assert cur.fetchone()[0] is True, "redefinir deixou de marcar a troca devida"

    aberta = db_sessoes.abrir(id_usuario=pessoa["id"])
    valida = db_sessoes.validar(aberta.token)

    assert valida is not None, "a sessão foi recusada por uma troca que é apenas recomendada"
    assert valida.identidade.id_usuario == pessoa["id"]


def test_redefinir_REVOGA_as_sessoes_abertas(pessoa: dict[str, Any], admin: int) -> None:
    """Metade da defesa: sem isto, quem tivesse roubado uma sessão continuaria dentro com a
    senha que a vítima acabou de perder."""
    aberta = db_sessoes.abrir(id_usuario=pessoa["id"])
    assert db_sessoes.validar(aberta.token) is not None

    db_usuarios.redefinir_senha(pessoa["id"], autor=admin)
    db_sessoes.revogar_todas_do_usuario(id_usuario=pessoa["id"], autor=admin)

    assert db_sessoes.validar(aberta.token) is None, "a sessão sobreviveu à redefinição"


def test_o_evento_da_redefinicao_tem_as_duas_pessoas_e_nenhuma_senha(
    con: Any, pessoa: dict[str, Any], admin: int
) -> None:
    """`id_usuario` é QUEM FEZ, `entidade_id` é QUEM SOFREU (D24) — e nada mais entra ali."""
    resultado = db_usuarios.redefinir_senha(pessoa["id"], autor=admin)
    linha = con.execute(
        "SELECT id_usuario, entidade, entidade_id, metadados FROM eventos "
        "WHERE tipo = %s AND entidade_id = %s ORDER BY criado_em_evento DESC LIMIT 1",
        (db_usuarios.EVENTO_SENHA_REDEFINIDA, pessoa["id"]),
    ).fetchone()

    assert linha is not None, "a redefinição não gravou evento"
    id_autor, entidade, entidade_id, metadados = linha
    assert (id_autor, entidade, entidade_id) == (admin, db_usuarios.ENTIDADE_USUARIO, pessoa["id"])
    assert resultado["senha_temporaria"] not in str(metadados)
    assert set(metadados) == {"tinha_senha_propria", "validade_horas"}


# --------------------------------------------------------------------------------------
# `db alinhar-senhas` — a preparacao do corte (25/09/2026)
# --------------------------------------------------------------------------------------


def _hash_de(con: Any, id_usuario: int) -> tuple[str | None, Any]:
    with con.cursor() as cur:
        cur.execute(
            "SELECT senha_hash, senha_definida_em_usuario FROM usuarios WHERE id_usuario = %s",
            (id_usuario,),
        )
        return cur.fetchone()


def test_alinhar_conserta_quem_nunca_escolheu_senha(
    con: Any, pessoa: dict[str, Any]
) -> None:
    """O caso que o comando existe para resolver: hash semeado a mao, pessoa trancada.

    Enquanto o Authelia autentica isso e' inofensivo. No dia do corte e' gente que nao entra,
    descoberta uma a uma pelo telefone.
    """
    with con.cursor() as cur:
        cur.execute(
            "UPDATE usuarios SET senha_hash = 'hash_de_teste_1', "
            "senha_definida_em_usuario = NULL WHERE id_usuario = %s",
            (pessoa["id"],),
        )

    antes = db_usuarios.credenciais_por_login(pessoa["login"])
    assert antes is not None
    assert not db_senhas.verificar(db_senhas.senha_inicial(), antes.senha_hash), (
        "cenario invalido: a pessoa ja' entrava antes do comando"
    )

    assert cli.main(["alinhar-senhas"]) == 0

    depois = db_usuarios.credenciais_por_login(pessoa["login"])
    assert depois is not None
    assert db_senhas.verificar(db_senhas.senha_inicial(), depois.senha_hash), (
        "a pessoa continua sem conseguir entrar com a senha inicial"
    )
    assert depois.deve_trocar is True, "a tela precisa CONVIDAR essa pessoa a trocar"


def test_alinhar_NAO_TOCA_quem_escolheu_a_propria_senha(
    con: Any, pessoa: dict[str, Any]
) -> None:
    """A propriedade de seguranca do comando, e a razao de ele nao ser um `UPDATE` cru.

    Quem escolheu senha nao pode ter a senha apagada por um comando de manutencao -- e o DONO
    do banco esta' exatamente nesse grupo. Um comando que "alinha todo mundo" derrubaria a senha
    dele junto, no passo de PREPARACAO do corte.
    """
    _definir_senha_propria(con, pessoa["id"], SENHA_ESCOLHIDA)
    hash_antes, definida_antes = _hash_de(con, pessoa["id"])

    assert cli.main(["alinhar-senhas"]) == 0

    hash_depois, definida_depois = _hash_de(con, pessoa["id"])
    assert hash_depois == hash_antes, "o comando reescreveu a senha de quem a escolheu"
    assert definida_depois == definida_antes
    assert db_senhas.verificar(SENHA_ESCOLHIDA, hash_depois)


def test_alinhar_com_simular_nao_escreve_nada(con: Any, pessoa: dict[str, Any]) -> None:
    with con.cursor() as cur:
        cur.execute(
            "UPDATE usuarios SET senha_hash = 'hash_de_teste_2', "
            "senha_definida_em_usuario = NULL WHERE id_usuario = %s",
            (pessoa["id"],),
        )
    antes, _ = _hash_de(con, pessoa["id"])

    assert cli.main(["alinhar-senhas", "--simular"]) == 0

    depois, _ = _hash_de(con, pessoa["id"])
    assert depois == antes, "`--simular` escreveu no banco"


def test_alinhar_e_IDEMPOTENTE_e_a_contagem_e_honesta(
    con: Any, pessoa: dict[str, Any], capsys: Any
) -> None:
    """Rodar duas vezes nao reescreve, e o numero diz o que FALTA.

    Sem a conferencia do hash, a saida diria "N seriam alinhadas" tanto num banco quebrado
    quanto num ja' certo -- e quem rodasse o comando duas vezes nao distinguiria "funcionou"
    de "nao fez nada". E' a mesma exigencia que o `cmd_expurgar` documenta.
    """
    with con.cursor() as cur:
        cur.execute(
            "UPDATE usuarios SET senha_hash = 'hash_de_teste_3', "
            "senha_definida_em_usuario = NULL WHERE id_usuario = %s",
            (pessoa["id"],),
        )

    assert cli.main(["alinhar-senhas"]) == 0
    primeira, _ = _hash_de(con, pessoa["id"])

    capsys.readouterr()
    assert cli.main(["alinhar-senhas", "--simular"]) == 0
    saida = capsys.readouterr().out
    assert "na senha inicial e NAO conferem         : 0" in saida, saida

    segunda, _ = _hash_de(con, pessoa["id"])
    assert segunda == primeira, "a segunda passada reescreveu o hash"
