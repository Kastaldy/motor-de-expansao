"""A passada completa do login, contra um Postgres DE VERDADE (P19: D30 + D31).

POR QUE ESTE ARQUIVO EXISTE
---------------------------
Todo o resto da epic foi verificado com DUBLÊS: o CI não tem Postgres (decisão de 25/08/2026),
então `SQL_VALIDAR`, `SQL_CONTAR_RECUSAS`, o `ck_usuarios_prazo_exige_troca` da 019 e o
`GREATEST` com `-infinity` só passaram por validação de SINTAXE (`pglast`) e por objetos falsos
que respondem no lugar do banco. Sintaxe correta e comportamento correto são coisas diferentes,
e a distância entre as duas é exatamente o que este arquivo mede.

Ele também é o teste de fumaça para o dia do corte: é o que se roda antes de virar a chave
`MOTOR_AUTENTICACAO_PROPRIA` em qualquer lugar.

COMO RODAR
----------
Precisa de um Postgres de ENSAIO já migrado (000 → 019). O caminho está em
`docs/banco_deploy.md` §"Ensaio local"; em resumo:

    docker run -d --name motor-ensaio -e POSTGRES_PASSWORD=<senha> -p 5432:5432 \\
        postgis/postgis:18-3.6
    # criar o banco `banco_de_reservas_ensaio` e o papel `app` conforme o doc
    $env:MOTOR_DATABASE_URL_ADMIN = "postgresql://postgres:<senha>@localhost:5432/banco_de_reservas_ensaio"
    python -m motor_expansao.db aplicar
    python -m pytest tests/integration/test_login_ponta_a_ponta.py -v

Sem a variável, ou com o banco não migrado, a suíte PULA com o motivo escrito. Ela nunca falha
por ausência de ambiente -- falhar assim treinaria todo mundo a ignorar vermelho.

TRAVA DE DESTINO
----------------
Este arquivo CRIA usuário, REDEFINE senha e escreve em `eventos`. Apontá-lo para produção por
engano seria estrago real e irreversível (`eventos` é append-only). Por isso ele recusa rodar
se o nome do banco não disser `ensaio` ou `test` -- ver `_exigir_banco_de_ensaio`.
"""

from __future__ import annotations

import os
import time
import uuid
from typing import Any

import pytest

psycopg = pytest.importorskip("psycopg")

from motor_expansao.db import cli  # noqa: E402
from motor_expansao.db import eventos as db_eventos  # noqa: E402
from motor_expansao.db import senhas as db_senhas  # noqa: E402
from motor_expansao.db import sessoes as db_sessoes  # noqa: E402
from motor_expansao.db import usuarios as db_usuarios  # noqa: E402

#: Senhas do ensaio. Acima do piso de 12 e sem forma de credencial real -- este arquivo é lido
#: por gente, e "senha de exemplo" no fonte é como um literal vira default de verdade depois.
SENHA_ESCOLHIDA = "cavalo-bateria-grampo"
SENHA_SEGUINTE = "outra-frase-comprida"


def _url() -> str | None:
    return os.environ.get(cli.ENV_URL_ADMIN) or os.environ.get("MOTOR_DATABASE_URL")


@pytest.fixture(scope="module")
def _exigir_banco_de_ensaio() -> None:
    """Pula sem ambiente; RECUSA ambiente que não pareça de ensaio.

    NÃO é `autouse`: quem o exige é o `con`, por PARÂMETRO. Como `autouse`, o pytest não garante
    que ele rode antes dos outros fixtures de módulo, e a conexão tentava abrir com URL nula —
    a suíte morria com `AttributeError` em vez de pular limpo, que é o oposto do desenho.
    """
    url = _url()
    if not url:
        pytest.skip(
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


@pytest.fixture(scope="module")
def con(_exigir_banco_de_ensaio: None) -> Any:
    """Conexão de ADMIN, para montar cenário e inspecionar o que o código escreveu.

    Banco no nome certo mas fora do ar PULA, e não quebra: é ambiente ausente, a mesma classe de
    `test_api_analisar.py` quando falta a base geo. O caso comum é a variável ter sobrado no
    terminal depois de o container parar. A mensagem diz isso com todas as letras, porque um
    "pulado" que parece "tudo certo" é pior que um vermelho.
    """
    try:
        with psycopg.connect(_url(), autocommit=True) as c:
            yield c
    except psycopg.OperationalError as erro:
        pytest.skip(
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
        pytest.skip(f"banco não migrado (falta {', '.join(faltando)}) — rode `db aplicar` antes")


@pytest.fixture(scope="module", autouse=True)
def _ambiente(con: Any) -> Any:
    """Liga a autenticação própria e garante a senha inicial, que `criar` exige."""
    anterior = {
        k: os.environ.get(k)
        for k in (db_sessoes.ENV_AUTENTICACAO_PROPRIA, db_senhas.ENV_SENHA_INICIAL)
    }
    os.environ[db_sessoes.ENV_AUTENTICACAO_PROPRIA] = "1"
    os.environ.setdefault(db_senhas.ENV_SENHA_INICIAL, "inicial-do-ensaio-1")
    # O piloto lê `MOTOR_DATABASE_URL`; no ensaio os dois papéis são a mesma pessoa.
    os.environ.setdefault("MOTOR_DATABASE_URL", _url() or "")
    yield
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
    afirma 14 para o banco. As duas contas nunca se encontraram, porque o CI não tem Postgres.
    Aqui elas se encontram.
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
    assert valida.deve_trocar is False


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


def test_a_sessao_carrega_a_marca_de_troca(con: Any, pessoa: dict[str, Any], admin: int) -> None:
    """É o que o portão de sessão lê a cada requisição para aplicar o bloqueio (D31)."""
    db_usuarios.redefinir_senha(pessoa["id"], autor=admin)
    aberta = db_sessoes.abrir(id_usuario=pessoa["id"])
    valida = db_sessoes.validar(aberta.token)

    assert valida is not None
    assert valida.deve_trocar is True, "a sessão não sabe que a pessoa deve trocar a senha"


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
