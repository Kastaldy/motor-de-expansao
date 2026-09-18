"""Administracao de usuarios (D25) — sem tocar banco nenhum.

O que estes testes guardam nao e' o CRUD: e' a trilha. Uma tela de administracao que muda
acesso e nao registra quem mudou reproduz, em outro lugar, o problema que o D19 resolveu para
`perfil_permissoes`. Por isso o foco esta em: o evento sai, sai na MESMA transacao da mudanca,
sai com o autor certo no lugar certo, e nao sai quando nada mudou.

A confusao mais cara possivel aqui e' trocar as duas pessoas de lugar — `id_usuario` e' QUEM
FEZ e `entidade_id` e' QUEM SOFREU (D24). Invertidos, a auditoria continua parecendo correta e
responde exatamente ao contrario. Tem teste proprio.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC
from typing import Any

import pytest

from motor_expansao import db
from motor_expansao.db import postgres
from motor_expansao.db import usuarios as mod

#: (id, login, nome, email, perfil, ativo, criado, atualizado, senha_propria, deve_trocar_senha)
# As duas ultimas vem da 016. O Vinícius ja' definiu a dele; o `inativo` do teste abaixo nunca
# definiu — e' o par que a tela precisa distinguir.
LINHA_LISTA = (
    7,
    "vinicius",
    "Vinícius Cruz",
    "v@ultra.com",
    "growth",
    True,
    None,
    None,
    True,
    False,
)


class FakeConexao:
    """Dublê que responde por PEDAÇO DE SQL, e não por ordem de chamada.

    Casar por ordem tornaria o teste refém do arranjo interno do módulo — trocar duas
    consultas de lugar quebraria o teste sem quebrar o comportamento. Casar pelo SQL
    exercita a mesma coisa que o banco veria.
    """

    def __init__(self, respostas: dict[str, list[tuple[Any, ...]]]) -> None:
        self.respostas = respostas
        self.executados: list[tuple[str, Any]] = []
        self.autocommit = False
        self._ultimo: list[tuple[Any, ...]] = []

    def execute(self, sql: str, params: Any = None) -> FakeConexao:
        self.executados.append((sql, params))
        self._ultimo = []
        for marca, linhas in self.respostas.items():
            if marca in sql:
                self._ultimo = linhas
                break
        return self

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self._ultimo

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._ultimo[0] if self._ultimo else None

    # -- ajudas de leitura para os testes -----------------------------------
    def sql_que_contem(self, trecho: str) -> list[tuple[str, Any]]:
        return [(s, p) for s, p in self.executados if trecho in s]

    @property
    def eventos(self) -> list[Any]:
        return [p for s, p in self.executados if "INSERT INTO eventos" in s]


class FakePool:
    def __init__(self, con: FakeConexao) -> None:
        self._con = con

    @contextmanager
    def connection(self):  # type: ignore[no-untyped-def]
        yield self._con

    def open(self, wait: bool = False) -> None: ...
    def close(self) -> None: ...


def _instalar(
    monkeypatch: pytest.MonkeyPatch, respostas: dict[str, list[tuple[Any, ...]]]
) -> FakeConexao:
    con = FakeConexao(respostas)
    monkeypatch.setattr(postgres, "_driver", lambda: lambda **_k: FakePool(con))
    monkeypatch.setenv(postgres.ENV_URL, "postgresql://fake/motor")
    return con


@pytest.fixture(autouse=True)
def _limpo() -> Any:
    db.fechar_pool()
    yield
    db.fechar_pool()


def _con_padrao(monkeypatch: pytest.MonkeyPatch, *, perfil: str, ativo: bool) -> FakeConexao:
    return _instalar(
        monkeypatch,
        {
            "FOR UPDATE OF u": [(9, "alvo", perfil, ativo)],
            "FROM perfis WHERE nome_perfil": [(3,)],
        },
    )


# --------------------------------------------------------------------------------------
# Leitura
# --------------------------------------------------------------------------------------


def test_credencial_por_login_traz_id_hash_e_deve_trocar(monkeypatch: pytest.MonkeyPatch) -> None:
    """O que o login do P19 (D30/D31) precisa conferir, numa ida so' ao banco.

    As duas ultimas colunas vem da 019 e nao sao enfeite: `expira_em` e' o que faz a senha
    temporaria morrer, e `redefinida_em` e' o piso da trava de tentativas. Buscar qualquer uma
    depois seria segunda ida ao banco para um dado que ja' estava na mesma linha.
    """
    from datetime import datetime

    prazo = datetime(2026, 9, 18, 12, 0, tzinfo=UTC)
    redefinida = datetime(2026, 9, 18, 10, 0, tzinfo=UTC)
    con = _instalar(
        monkeypatch,
        {"SELECT u.id_usuario, u.senha_hash": [(7, "$argon2id$x", True, prazo, redefinida)]},
    )
    cred = mod.credenciais_por_login("vinicius")

    assert cred is not None
    assert (cred.id_usuario, cred.senha_hash, cred.deve_trocar) == (7, "$argon2id$x", True)
    assert (cred.expira_em, cred.redefinida_em) == (prazo, redefinida)
    # Leitura, nao transacao de escrita: entrar nao muda `usuarios`.
    assert con.sql_que_contem("READ ONLY")
    _sql, params = con.sql_que_contem("SELECT u.id_usuario, u.senha_hash")[0]
    assert params == ("vinicius",)


def test_o_login_e_normalizado_antes_de_consultar(monkeypatch: pytest.MonkeyPatch) -> None:
    con = _instalar(
        monkeypatch, {"SELECT u.id_usuario, u.senha_hash": [(7, "h", False, None, None)]}
    )
    mod.credenciais_por_login("  vinicius  ")
    _sql, params = con.sql_que_contem("SELECT u.id_usuario, u.senha_hash")[0]
    assert params == ("vinicius",), "espaco em volta do login viraria login inexistente"


def test_login_inexistente_e_login_inativo_dao_O_MESMO_None(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Decisao de seguranca, nao economia.

    O `AND u.ativo` da consulta faz o desativado nao voltar linha -- igual a quem nunca existiu.
    Distinguir os dois entregaria ao visitante um oraculo de quem trabalha aqui.
    """
    _instalar(monkeypatch, {"SELECT u.id_usuario, u.senha_hash": []})
    assert mod.credenciais_por_login("fantasma") is None
    assert "AND u.ativo" in mod.SQL_CREDENCIAL_POR_LOGIN


def test_login_vazio_nao_consulta_o_banco(monkeypatch: pytest.MonkeyPatch) -> None:
    con = _instalar(monkeypatch, {"SELECT u.id_usuario, u.senha_hash": [(7, "h", False)]})
    assert mod.credenciais_por_login("") is None
    assert mod.credenciais_por_login("   ") is None
    assert con.executados == [], "consultou o banco sem login para procurar"


def test_o_hash_nao_aparece_no_repr_da_credencial() -> None:
    """A razao do `repr=False`: dataclass imprime todos os campos, e um traceback -- ou um
    `_LOG.debug("%s", cred)` distraido -- levaria o hash para o log. O hash nao e' a senha, mas
    e' material de ataque offline se o log vazar."""
    cred = mod.Credencial(id_usuario=7, deve_trocar=False, senha_hash="$argon2id$SEGREDO")
    assert "SEGREDO" not in repr(cred)
    assert cred.senha_hash == "$argon2id$SEGREDO", "esconder do repr nao pode esconder do codigo"


def test_o_login_nao_trava_a_linha_de_usuarios() -> None:
    """`FOR UPDATE` aqui serializaria as tentativas de login da mesma pessoa e poria ESCRITA no
    caminho de quem so' quer entrar. As duas constantes vizinhas travam de proposito -- elas sao
    dos fluxos de TROCA e de ADMINISTRACAO."""
    assert "FOR UPDATE" not in mod.SQL_CREDENCIAL_POR_LOGIN
    assert "FOR UPDATE" in mod.SQL_ESTADO_DA_SENHA


def test_listar_traz_inativos(monkeypatch: pytest.MonkeyPatch) -> None:
    """Esconder quem foi desativado tornaria a REATIVAÇÃO impossível pela tela."""
    inativo = (
        8,
        "quem_saiu",
        "Quem Saiu",
        "q@ultra.com",
        "expansao",
        False,
        None,
        None,
        False,
        True,
    )
    con = _instalar(monkeypatch, {"FROM usuarios u": [LINHA_LISTA, inativo]})
    lista = mod.listar()
    assert [u.ativo for u in lista] == [True, False]
    assert lista[1].login == "quem_saiu"
    # Leitura entra pelo `conexao()`, que abre a transação READ ONLY.
    assert con.sql_que_contem("READ ONLY")


def test_listar_traz_o_estado_da_senha_de_cada_um(monkeypatch: pytest.MonkeyPatch) -> None:
    """A tela precisa das duas colunas da 016 separadas, e não de uma derivada da outra.

    `senha_propria` responde "já definiu alguma vez?" e `deve_trocar_senha` responde "precisa
    definir agora?". Um admin pode forçar troca de quem já definiu, e nesse caso as duas são
    verdadeiras ao mesmo tempo — colapsá-las numa só perderia justamente esse caso.
    """
    inativo = (
        8,
        "quem_saiu",
        "Quem Saiu",
        "q@ultra.com",
        "expansao",
        False,
        None,
        None,
        False,
        True,
    )
    _instalar(monkeypatch, {"FROM usuarios u": [LINHA_LISTA, inativo]})
    lista = mod.listar()
    assert [u.senha_propria for u in lista] == [True, False]
    assert [u.deve_trocar_senha for u in lista] == [False, True]


def test_o_payload_da_tela_nunca_carrega_o_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    """`senha_hash` não sai do banco — nem inteiro, nem mascarado, nem sob outro nome.

    O `como_json` vai para o navegador de quem administra. A tela precisa saber SE a pessoa já
    definiu a senha dela, e isso é um booleano; o hash não tem por que atravessar a rede.
    """
    _instalar(monkeypatch, {"FROM usuarios u": [LINHA_LISTA]})
    payload = mod.listar()[0].como_json()
    assert "senha_hash" not in payload
    assert not any("hash" in chave for chave in payload)
    assert not any(isinstance(v, str) and v.startswith("$argon2") for v in payload.values())
    assert "senha_hash" not in mod.SQL_LISTAR


def test_listar_nao_filtra_por_ativo_no_sql() -> None:
    """A cláusula não pode voltar por 'limpeza': o inativo é o caso de uso da tela."""
    assert "WHERE" not in mod.SQL_LISTAR.upper().split("ORDER BY")[0]


# --------------------------------------------------------------------------------------
# Troca de perfil
# --------------------------------------------------------------------------------------


def test_trocar_perfil_grava_de_para_e_carimba_o_autor(monkeypatch: pytest.MonkeyPatch) -> None:
    con = _con_padrao(monkeypatch, perfil="expansao", ativo=True)
    saida = mod.alterar_perfil(9, "growth", autor=7)

    assert saida == {"id_usuario": 9, "de": "expansao", "para": "growth", "mudou": True}
    # O autor é o PRIMEIRO comando da transação — se a escrita falhar, ele cai no rollback.
    assert con.executados[0][0] == postgres.SQL_DEFINIR_AUTOR
    assert con.executados[0][1] == ("7",)

    (evento,) = con.eventos
    autor, tipo, entidade, alvo, metadados = evento
    assert tipo == mod.EVENTO_PERFIL_ALTERADO
    assert metadados.obj == {"de": "expansao", "para": "growth"}


def test_as_duas_pessoas_do_evento_nao_se_invertem(monkeypatch: pytest.MonkeyPatch) -> None:
    """`id_usuario` é quem FEZ; `entidade_id` é quem SOFREU (D24).

    Invertidos, a trilha continua parecendo correta e responde ao contrário — por isso a
    checagem é explícita e os dois ids do teste são diferentes de propósito.
    """
    con = _con_padrao(monkeypatch, perfil="expansao", ativo=True)
    mod.alterar_perfil(9, "growth", autor=7)

    autor, _tipo, entidade, alvo, _metadados = con.eventos[0]
    assert autor == 7, "o autor virou o alvo"
    assert alvo == 9, "o alvo virou o autor"
    assert entidade == mod.ENTIDADE_USUARIO


def test_trocar_para_o_mesmo_perfil_nao_gera_evento(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nada a fazer é sucesso, mas não é mudança — uma linha `de: growth, para: growth`
    polui a auditoria com ruído que parece sinal."""
    con = _con_padrao(monkeypatch, perfil="growth", ativo=True)
    saida = mod.alterar_perfil(9, "growth", autor=7)
    assert saida["mudou"] is False
    assert con.eventos == []
    assert con.sql_que_contem("UPDATE usuarios SET id_perfil") == []


def test_usuario_que_nao_existe_e_404_nao_criacao(monkeypatch: pytest.MonkeyPatch) -> None:
    con = _instalar(monkeypatch, {"FOR UPDATE OF u": []})
    with pytest.raises(mod.UsuarioDesconhecido):
        mod.alterar_perfil(9, "growth", autor=7)
    assert con.sql_que_contem("UPDATE usuarios") == []


def test_perfil_inexistente_nao_escreve(monkeypatch: pytest.MonkeyPatch) -> None:
    con = _instalar(
        monkeypatch,
        {"FOR UPDATE OF u": [(9, "alvo", "expansao", True)], "FROM perfis WHERE nome_perfil": []},
    )
    with pytest.raises(mod.PerfilDesconhecido):
        mod.alterar_perfil(9, "inventado", autor=7)
    assert con.eventos == []


def test_a_linha_do_alvo_e_travada_antes_de_ler(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem `FOR UPDATE`, dois admins na mesma pessoa produzem dois eventos com o MESMO `de`:
    a trilha diria que o perfil saiu de `expansao` duas vezes."""
    con = _con_padrao(monkeypatch, perfil="expansao", ativo=True)
    mod.alterar_perfil(9, "growth", autor=7)
    assert con.sql_que_contem("FOR UPDATE OF u")


# --------------------------------------------------------------------------------------
# Ativar / desativar
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("ativo_antes", "pedido", "tipo"),
    [
        (True, False, mod.EVENTO_DESATIVADO),
        (False, True, mod.EVENTO_REATIVADO),
    ],
)
def test_o_evento_certo_para_cada_sentido(
    monkeypatch: pytest.MonkeyPatch, ativo_antes: bool, pedido: bool, tipo: str
) -> None:
    con = _con_padrao(monkeypatch, perfil="expansao", ativo=ativo_antes)
    saida = mod.definir_ativo(9, pedido, autor=7)
    assert saida["mudou"] is True
    assert con.eventos[0][1] == tipo


def test_desativar_e_soft_nunca_delete(monkeypatch: pytest.MonkeyPatch) -> None:
    """`eventos.id_usuario` é `ON DELETE SET NULL`: um DELETE de verdade orfanaria toda a
    autoria da pessoa de uma vez."""
    con = _con_padrao(monkeypatch, perfil="expansao", ativo=True)
    mod.definir_ativo(9, False, autor=7)
    assert con.sql_que_contem("DELETE") == []
    assert con.sql_que_contem("UPDATE usuarios SET ativo")


def test_sem_mudanca_de_status_nao_gera_evento(monkeypatch: pytest.MonkeyPatch) -> None:
    con = _con_padrao(monkeypatch, perfil="expansao", ativo=True)
    assert mod.definir_ativo(9, True, autor=7)["mudou"] is False
    assert con.eventos == []


# --------------------------------------------------------------------------------------
# A trava de auto-alvo
# --------------------------------------------------------------------------------------


def test_ninguem_muda_o_proprio_perfil(monkeypatch: pytest.MonkeyPatch) -> None:
    """Quem se rebaixa por engano perde a tela que usaria para desfazer."""
    con = _con_padrao(monkeypatch, perfil="growth", ativo=True)
    with pytest.raises(mod.AlvoEhOAutor):
        mod.alterar_perfil(7, "expansao", autor=7)
    assert con.executados == [], "a recusa tem de vir ANTES de abrir transação"


def test_ninguem_se_desativa(monkeypatch: pytest.MonkeyPatch) -> None:
    """Auto-desativação derruba a própria sessão, sem ninguém para reverter."""
    _con_padrao(monkeypatch, perfil="growth", ativo=True)
    with pytest.raises(mod.AlvoEhOAutor):
        mod.definir_ativo(7, False, autor=7)


# --------------------------------------------------------------------------------------
# PII
# --------------------------------------------------------------------------------------


def test_metadados_nao_carregam_pii(monkeypatch: pytest.MonkeyPatch) -> None:
    """Convenções §5: nada de nome, e-mail ou login em `metadados` — o id basta, e quem lê
    `eventos` resolve o nome em `usuarios`."""
    con = _con_padrao(monkeypatch, perfil="expansao", ativo=True)
    mod.alterar_perfil(9, "growth", autor=7)
    metadados = con.eventos[0][4].obj
    achatado = " ".join(str(v) for v in metadados.values()).lower()
    for pii in ("@", "vinícius", "alvo"):
        assert pii not in achatado, f"PII em metadados: {metadados}"


def test_o_vocabulario_de_tipo_e_o_do_contrato() -> None:
    """`tipo` fora do `docs/eventos_contrato.md` §2.7 é defeito, não estilo (D11)."""
    assert mod.EVENTO_PERFIL_ALTERADO == "usuario.perfil_alterado"
    assert mod.EVENTO_SENHA_REDEFINIDA == "usuario.senha_redefinida"
    assert mod.EVENTO_TROCA_EXIGIDA == "usuario.troca_exigida"
    assert mod.EVENTO_DESATIVADO == "usuario.desativado"
    assert mod.EVENTO_REATIVADO == "usuario.reativado"
    assert mod.EVENTO_CRIADO == "usuario.criado"
    assert mod.EVENTO_SENHA_DEFINIDA == "usuario.senha_definida"
    assert mod.ENTIDADE_USUARIO == "usuario"


# --------------------------------------------------------------------------------------
# Criação (D26)
# --------------------------------------------------------------------------------------


HASH_FALSO = "$argon2id$v=19$m=65536,t=3,p=4$c2Fs$aGFzaA"


@pytest.fixture
def _sem_argon2(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neutraliza o custo do Argon2 nestes testes, que são sobre a TRILHA e não sobre o hash.

    O hash de verdade tem teste próprio em `test_db_senhas.py`, que faz `importorskip` porque
    `argon2-cffi` entra pelo extra novo `auth` e pode não estar instalado. Aqui, pagar 64 MB e
    ~100 ms por caso tornaria esta suíte lenta sem exercitar nada que ela guarda.
    """
    from motor_expansao.db import senhas

    monkeypatch.setattr(senhas, "hash_da_senha_inicial", lambda: HASH_FALSO)
    monkeypatch.setattr(senhas, "gerar", lambda _s: HASH_FALSO)


def _con_criacao(monkeypatch: pytest.MonkeyPatch, id_novo: int = 42) -> FakeConexao:
    return _instalar(
        monkeypatch,
        {
            "FROM perfis WHERE nome_perfil": [(3,)],
            "INSERT INTO usuarios": [(id_novo,)],
        },
    )


def test_criar_grava_usuario_e_evento_na_mesma_transacao(
    monkeypatch: pytest.MonkeyPatch, _sem_argon2: None
) -> None:
    """Uma unidade de trabalho: a linha e o evento, ou nenhum dos dois."""
    con = _con_criacao(monkeypatch)
    mod.criar(login="ana", nome="Ana Ribeiro", email="ana@ultra.com", perfil="expansao", autor=7)

    # O autor é o PRIMEIRO comando da transação — sem ele as triggers do D19 gravam autoria nula.
    assert con.executados[0][0] == postgres.SQL_DEFINIR_AUTOR
    assert con.executados[0][1] == ("7",)
    assert len(con.sql_que_contem("INSERT INTO usuarios")) == 1
    assert len(con.eventos) == 1
    assert con.eventos[0][1] == mod.EVENTO_CRIADO


def test_as_duas_pessoas_da_criacao_nao_se_invertem(
    monkeypatch: pytest.MonkeyPatch, _sem_argon2: None
) -> None:
    """`id_usuario` é quem CRIOU; `entidade_id` é quem foi criado — e é o id do `RETURNING`.

    É o único caso em que o alvo não existia antes da chamada, então trocar os dois de lugar
    produziria um evento apontando para o admin como se ELE tivesse sido criado.
    """
    con = _con_criacao(monkeypatch, id_novo=42)
    mod.criar(login="ana", nome="Ana", email="ana@ultra.com", perfil="expansao", autor=7)

    autor, tipo, entidade, entidade_id, _metadados = con.eventos[0]
    assert autor == 7, "o autor virou o alvo"
    assert entidade_id == 42, "o alvo virou o autor"
    assert entidade == mod.ENTIDADE_USUARIO
    assert tipo == mod.EVENTO_CRIADO


def test_criar_devolve_o_id_novo_e_avisa_do_authelia(
    monkeypatch: pytest.MonkeyPatch, _sem_argon2: None
) -> None:
    """A tela precisa do id, e precisa do recado: a pessoa ainda não entra."""
    _con_criacao(monkeypatch, id_novo=42)
    saida = mod.criar(login="ana", nome="Ana", email="ana@ultra.com", perfil="growth", autor=7)
    assert saida["id_usuario"] == 42
    assert saida["falta_cadastrar_no_authelia"] is True


def test_metadados_da_criacao_nao_carregam_pii(
    monkeypatch: pytest.MonkeyPatch, _sem_argon2: None
) -> None:
    """Só o perfil. Nunca login, nome ou e-mail — convenções §5 e contrato §4."""
    con = _con_criacao(monkeypatch)
    mod.criar(login="ana", nome="Ana Ribeiro", email="ana@ultra.com", perfil="expansao", autor=7)
    metadados = con.eventos[0][4].obj
    assert metadados == {"perfil": "expansao"}


def test_criar_grava_exatamente_o_que_o_modulo_de_senha_produziu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O que vai para `senha_hash` é a saída de `senhas.hash_da_senha_inicial()`, e nada mais.

    Este teste guarda a LIGAÇÃO, não o algoritmo: a força do hash tem teste próprio em
    `test_db_senhas.py`. O que se impede aqui é a regressão que a `015` descreveu — enquanto a
    coluna não tinha consumidor, qualquer string passava, e as fixtures gravaram
    `hash_de_teste_*`. Por isso a asserção é de identidade com o valor produzido, e o `sentinela`
    é reconhecível: se alguém interpolar a senha, montar um placeholder ou passar `None`, o valor
    gravado deixa de ser este.
    """
    from motor_expansao.db import senhas

    sentinela = "$argon2id$v=19$m=65536,t=3,p=4$U0VOVElORUxB$dmluZG9kb21vZHVsbw"
    monkeypatch.setattr(senhas, "hash_da_senha_inicial", lambda: sentinela)
    monkeypatch.setenv("MOTOR_SENHA_INICIAL", "senha-inicial-do-piloto")

    con = _con_criacao(monkeypatch)
    mod.criar(login="ana", nome="Ana", email="ana@ultra.com", perfil="expansao", autor=7)

    _sql, params = con.sql_que_contem("INSERT INTO usuarios")[0]
    gravado = params[3]
    assert gravado == sentinela, "o hash gravado não é o que o módulo de senha produziu"
    assert "senha-inicial-do-piloto" not in gravado, "a senha em claro vazou para a coluna"


def test_criar_recusa_quando_a_senha_inicial_nao_esta_configurada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem `MOTOR_SENHA_INICIAL`, criar é RECUSADO — e antes de abrir transação.

    Criar alguém com uma senha que ninguém sabe qual é seria pior que não criar: a pessoa
    apareceria na lista, não entraria, e não haveria como descobrir o porquê pela tela.
    """
    from motor_expansao.db import senhas

    monkeypatch.delenv(senhas.ENV_SENHA_INICIAL, raising=False)
    con = _con_criacao(monkeypatch)
    with pytest.raises(senhas.SenhaInicialNaoConfigurada):
        mod.criar(login="ana", nome="Ana", email="ana@ultra.com", perfil="expansao", autor=7)
    assert con.executados == []


def test_criar_com_perfil_inexistente_nao_escreve(
    monkeypatch: pytest.MonkeyPatch, _sem_argon2: None
) -> None:
    """A recusa vem do lookup por NOME, antes de qualquer INSERT — como no `alterar_perfil`."""
    con = _instalar(monkeypatch, {"INSERT INTO usuarios": [(42,)]})  # perfis não responde
    with pytest.raises(mod.PerfilDesconhecido):
        mod.criar(login="ana", nome="Ana", email="ana@ultra.com", perfil="inexistente", autor=7)
    assert con.sql_que_contem("INSERT INTO usuarios") == []
    assert con.eventos == []


@pytest.mark.parametrize(
    ("login", "nome", "email"),
    [
        ("", "Ana", "ana@ultra.com"),
        ("ana", "", "ana@ultra.com"),
        ("ana", "Ana", ""),
        ("ana", "Ana", "sem-arroba"),
    ],
)
def test_criar_recusa_campo_vazio_ou_email_invalido(
    monkeypatch: pytest.MonkeyPatch, _sem_argon2: None, login: str, nome: str, email: str
) -> None:
    """Recusa ANTES de abrir transação: campo vazio é erro de quem digitou."""
    con = _con_criacao(monkeypatch)
    with pytest.raises(ValueError):
        mod.criar(login=login, nome=nome, email=email, perfil="expansao", autor=7)
    assert con.executados == []


def test_criar_nao_trava_o_auto_alvo(monkeypatch: pytest.MonkeyPatch, _sem_argon2: None) -> None:
    """Criar não tem alvo preexistente, então `_recusar_auto_alvo` não se aplica.

    Sem este teste, alguém copiaria `alterar_perfil` inteiro por reflexo e travaria a criação
    sem motivo — e também não há `FOR UPDATE`, porque não há linha anterior para travar.
    """
    con = _con_criacao(monkeypatch)
    mod.criar(login="ana", nome="Ana", email="ana@ultra.com", perfil="expansao", autor=7)
    assert con.sql_que_contem("FOR UPDATE OF u") == []


@pytest.mark.parametrize(
    ("indice", "esperada"),
    [("idx_usuarios_login_ativo", "LoginEmUso"), ("idx_usuarios_email_ativo", "EmailEmUso")],
)
def test_conflito_de_indice_unico_vira_erro_de_dominio(indice: str, esperada: str) -> None:
    """A `UniqueViolation` é traduzida pelo NOME do índice, não pela mensagem.

    Pela mensagem seria frágil: o cluster do Vinícius responde em português, e a rota devolveria
    500 para um conflito que a tela sabe explicar.
    """

    class _Diag:
        constraint_name = indice

    class _Violacao(Exception):
        diag = _Diag()

    traduzido = mod._traduzir_conflito(_Violacao("duplicate key"))
    assert type(traduzido).__name__ == esperada


def test_conflito_desconhecido_nao_e_traduzido() -> None:
    """Violação que não é dos dois índices sobe como está — inventar 409 esconderia defeito."""

    class _Outra(Exception):
        diag = None

    erro = _Outra("algo mais")
    assert mod._traduzir_conflito(erro) is erro


# --------------------------------------------------------------------------------------
# Senha própria (D26)
# --------------------------------------------------------------------------------------


def _con_senha(monkeypatch: pytest.MonkeyPatch, *, ja_definiu: bool) -> FakeConexao:
    return _instalar(
        monkeypatch,
        {"FOR UPDATE OF u": [(7, HASH_FALSO, ja_definiu, True)]},
    )


def test_trocar_a_propria_senha_grava_e_registra(
    monkeypatch: pytest.MonkeyPatch, _sem_argon2: None
) -> None:
    """O UPDATE e o evento na mesma transação, com o autor carimbado primeiro."""
    from motor_expansao.db import senhas

    monkeypatch.setattr(senhas, "verificar", lambda _s, _h: True)
    con = _con_senha(monkeypatch, ja_definiu=False)
    saida = mod.trocar_a_propria_senha(
        autor=7, senha_atual="a-inicial", nova_senha="uma frase longa"
    )

    assert con.executados[0][0] == postgres.SQL_DEFINIR_AUTOR
    assert len(con.sql_que_contem("SET senha_hash")) == 1
    assert con.eventos[0][1] == mod.EVENTO_SENHA_DEFINIDA
    assert saida["primeira_vez"] is True


def test_a_troca_carimba_a_data_e_limpa_a_marca_no_mesmo_update(
    monkeypatch: pytest.MonkeyPatch, _sem_argon2: None
) -> None:
    """Os três campos andam juntos: gravar o hash sem a data deixaria a 016 mentindo."""
    from motor_expansao.db import senhas

    monkeypatch.setattr(senhas, "verificar", lambda _s, _h: True)
    con = _con_senha(monkeypatch, ja_definiu=False)
    mod.trocar_a_propria_senha(autor=7, senha_atual="x", nova_senha="uma frase longa")

    sql, _params = con.sql_que_contem("SET senha_hash")[0]
    assert "senha_definida_em_usuario = now()" in sql
    assert "deve_trocar_senha_usuario = FALSE" in sql


def test_a_troca_e_o_unico_caso_em_que_autor_e_alvo_coincidem(
    monkeypatch: pytest.MonkeyPatch, _sem_argon2: None
) -> None:
    """Aqui autor == alvo de propósito — é a inversão do `_recusar_auto_alvo`.

    Mudar o próprio PERFIL é o que aquela guarda impede; trocar a própria SENHA é a única coisa
    que só a própria pessoa deveria poder fazer.
    """
    from motor_expansao.db import senhas

    monkeypatch.setattr(senhas, "verificar", lambda _s, _h: True)
    con = _con_senha(monkeypatch, ja_definiu=True)
    mod.trocar_a_propria_senha(autor=7, senha_atual="x", nova_senha="uma frase longa")

    autor, _tipo, _ent, entidade_id, _meta = con.eventos[0]
    assert autor == entidade_id == 7


def test_senha_atual_errada_nao_escreve_nada(
    monkeypatch: pytest.MonkeyPatch, _sem_argon2: None
) -> None:
    """Sem a conferência, qualquer requisição com o header de alguém trocaria a senha dele."""
    from motor_expansao.db import senhas

    monkeypatch.setattr(senhas, "verificar", lambda _s, _h: False)
    con = _con_senha(monkeypatch, ja_definiu=True)
    with pytest.raises(mod.SenhaAtualIncorreta):
        mod.trocar_a_propria_senha(autor=7, senha_atual="errada", nova_senha="uma frase longa")
    assert con.sql_que_contem("SET senha_hash") == []
    assert con.eventos == []


def test_a_politica_roda_antes_de_abrir_transacao(monkeypatch: pytest.MonkeyPatch) -> None:
    """Senha curta é erro de quem digitou — não há por que travar linha para descobrir."""
    con = _con_senha(monkeypatch, ja_definiu=False)
    with pytest.raises(Exception) as capturado:
        mod.trocar_a_propria_senha(autor=7, senha_atual="x", nova_senha="curta")
    assert type(capturado.value).__name__ == "SenhaFraca"
    assert con.executados == []


def test_metadados_da_senha_nunca_carregam_a_senha(
    monkeypatch: pytest.MonkeyPatch, _sem_argon2: None
) -> None:
    """Só `primeira_vez`. Nem a senha, nem o hash, nem parte de nenhum dos dois."""
    from motor_expansao.db import senhas

    monkeypatch.setattr(senhas, "verificar", lambda _s, _h: True)
    con = _con_senha(monkeypatch, ja_definiu=False)
    mod.trocar_a_propria_senha(autor=7, senha_atual="a-inicial", nova_senha="uma frase bem longa")
    metadados = con.eventos[0][4].obj
    assert metadados == {"primeira_vez": True}


# --------------------------------------------------------------------------------------
# A senha DE OUTRA PESSOA (15/09): redefinir e exigir troca
# --------------------------------------------------------------------------------------

#: Marca unica do `SQL_ESTADO_DA_SENHA_PARA_ADMIN` -- "FOR UPDATE OF u" casaria tambem com os outros
#: dois SELECTs travados deste modulo.
_MARCA_ESTADO_ADMIN = "u.senha_definida_em_usuario IS NOT NULL, u.deve_trocar_senha_usuario"


def _con_senha_admin(
    monkeypatch: pytest.MonkeyPatch, *, propria: bool, deve_trocar: bool
) -> FakeConexao:
    return _instalar(monkeypatch, {_MARCA_ESTADO_ADMIN: [(9, propria, deve_trocar)]})


def test_redefinir_grava_o_espelho_de_quem_nasce_pela_tela(
    monkeypatch: pytest.MonkeyPatch, _sem_argon2: None
) -> None:
    """Data NULA, marca ligada, PRAZO e momento da redefinicao -- tudo no mesmo UPDATE.

    O prazo e o momento nao sao enfeite: o primeiro e' o que faz a senha temporaria morrer, e o
    segundo e' o PISO da trava de tentativas, sem o qual quem errou cinco vezes antes de ligar
    continuaria barrado com a senha nova na mao.
    """
    from motor_expansao.db import senhas

    con = _con_senha_admin(monkeypatch, propria=True, deve_trocar=False)
    mod.redefinir_senha(9, autor=7)

    sql, params = con.sql_que_contem("SET senha_hash")[0]
    assert "senha_definida_em_usuario = NULL" in sql
    assert "deve_trocar_senha_usuario = TRUE" in sql
    assert "senha_expira_em_usuario = now() + make_interval(hours => %s)" in sql
    assert "senha_redefinida_em_usuario = now()" in sql
    assert params == (HASH_FALSO, senhas.VALIDADE_TEMPORARIA_H, 9)


def test_o_hash_gravado_e_o_da_senha_DEVOLVIDA(monkeypatch: pytest.MonkeyPatch) -> None:
    """A ligacao que sustenta tudo: o que o admin le' e' o que abre a conta.

    Se `gerar_temporaria` e o hash se desencontrassem, a rota entregaria ao administrador uma
    senha que nao funciona -- e o sintoma (pessoa nao entra) seria indistinguivel de senha
    digitada errado. Por isso o dublê aqui CAPTURA o texto que foi hasheado e o compara com o
    que a funcao devolveu.
    """
    from motor_expansao.db import senhas

    hasheadas: list[str] = []
    sentinela = "$argon2id$v=19$m=65536,t=3,p=4$UkVERUZJTklS$c2VudGluZWxh"

    def _gerar(senha: str) -> str:
        hasheadas.append(senha)
        return sentinela

    monkeypatch.setattr(senhas, "gerar", _gerar)
    con = _con_senha_admin(monkeypatch, propria=False, deve_trocar=True)
    saida = mod.redefinir_senha(9, autor=7)

    assert con.sql_que_contem("SET senha_hash")[0][1][0] == sentinela
    assert hasheadas == [saida["senha_temporaria"]]


def test_duas_redefinicoes_dao_senhas_DIFERENTES(
    monkeypatch: pytest.MonkeyPatch, _sem_argon2: None
) -> None:
    """Toda a diferenca em relacao ao que existia ate' 18/09/2026.

    Antes, redefinir entregava `MOTOR_SENHA_INICIAL` -- a MESMA senha para todo mundo, sempre.
    Este teste fica vermelho se alguem voltar a uma senha compartilhada, inclusive por engano
    (uma constante no lugar da chamada ao gerador).
    """
    con = _con_senha_admin(monkeypatch, propria=True, deve_trocar=False)
    primeira = mod.redefinir_senha(9, autor=7)["senha_temporaria"]
    con.executados.clear()
    segunda = mod.redefinir_senha(9, autor=7)["senha_temporaria"]
    assert primeira != segunda


def test_a_senha_temporaria_NUNCA_entra_no_evento(
    monkeypatch: pytest.MonkeyPatch, _sem_argon2: None
) -> None:
    """`eventos` e' append-only e lido por quem audita: senha ali dentro seria vazamento perene."""
    con = _con_senha_admin(monkeypatch, propria=True, deve_trocar=False)
    saida = mod.redefinir_senha(9, autor=7)

    achatado = " ".join(str(v) for v in con.eventos[0][4].obj.values())
    assert saida["senha_temporaria"] not in achatado
    assert not (set(con.eventos[0][4].obj) & {"senha", "senha_temporaria", "hash"})


def test_trocar_a_propria_senha_ZERA_o_prazo(monkeypatch: pytest.MonkeyPatch) -> None:
    """A razao de existir do `ck_usuarios_prazo_exige_troca` (019), em forma executavel.

    Quem sai da senha temporaria para a sua escolheu uma senha que NAO expira. Deixar o prazo da
    temporaria para tras daria senha propria com validade -- e o sintoma seria a pessoa barrada
    com a senha CERTA, lendo "Login ou senha incorretos", dias depois, sem nada que ligue uma
    coisa a outra. O banco recusa a escrita pelo CHECK; este teste pega antes, no SQL.
    """
    assert "senha_expira_em_usuario = NULL" in mod.SQL_DEFINIR_SENHA, (
        "trocar a propria senha parou de zerar o prazo: o CHECK da 019 vai recusar a escrita"
    )
    assert "deve_trocar_senha_usuario = FALSE" in mod.SQL_DEFINIR_SENHA


def test_redefinir_registra_com_as_duas_pessoas_nos_lugares_certos(
    monkeypatch: pytest.MonkeyPatch, _sem_argon2: None
) -> None:
    """Quem redefiniu e' `id_usuario`; de quem era a senha e' `entidade_id` (D24)."""
    con = _con_senha_admin(monkeypatch, propria=True, deve_trocar=False)
    mod.redefinir_senha(9, autor=7)

    assert con.executados[0][0] == postgres.SQL_DEFINIR_AUTOR
    autor, tipo, entidade, entidade_id, _meta = con.eventos[0]
    assert (autor, entidade_id) == (7, 9)
    assert entidade == mod.ENTIDADE_USUARIO
    assert tipo == mod.EVENTO_SENHA_REDEFINIDA


@pytest.mark.parametrize("propria", [True, False])
def test_redefinir_diz_se_apagou_uma_senha_escolhida(
    monkeypatch: pytest.MonkeyPatch, _sem_argon2: None, propria: bool
) -> None:
    """A diferenca entre arrumar o acesso de quem nunca entrou e derrubar a senha de alguem.

    E so' isso: nem a senha, nem o hash, nem parte de nenhum dos dois.
    """
    from motor_expansao.db import senhas

    con = _con_senha_admin(monkeypatch, propria=propria, deve_trocar=not propria)
    saida = mod.redefinir_senha(9, autor=7)
    assert con.eventos[0][4].obj == {
        "tinha_senha_propria": propria,
        # Politica APLICADA, nao segredo: responde "por quanto tempo aquela senha valeu" a quem
        # audita meses depois, quando a constante ja' pode ter outro valor.
        "validade_horas": senhas.VALIDADE_TEMPORARIA_H,
    }
    assert saida["tinha_senha_propria"] is propria


def test_redefinir_registra_mesmo_quando_ja_estava_na_inicial(
    monkeypatch: pytest.MonkeyPatch, _sem_argon2: None
) -> None:
    """O "ja' estava assim" nao e' verificavel pelo hash -- ate' 14/09 havia `hash_de_teste_*`."""
    con = _con_senha_admin(monkeypatch, propria=False, deve_trocar=True)
    mod.redefinir_senha(9, autor=7)
    assert len(con.sql_que_contem("SET senha_hash")) == 1
    assert len(con.eventos) == 1


def test_ninguem_redefine_a_propria_senha_por_aqui(
    monkeypatch: pytest.MonkeyPatch, _sem_argon2: None
) -> None:
    """Quem sabe a sua troca em `/api/me/senha` -- e a recusa vem antes de abrir transacao."""
    con = _con_senha_admin(monkeypatch, propria=True, deve_trocar=False)
    with pytest.raises(mod.AlvoEhOAutor):
        mod.redefinir_senha(7, autor=7)
    assert con.executados == []


def test_redefinir_sem_poder_hashear_nao_escreve_nada(monkeypatch: pytest.MonkeyPatch) -> None:
    """A falha de hash aparece ANTES da transacao -- nada fica meio feito.

    Ate' 18/09/2026 o que faltava aqui era a env `MOTOR_SENHA_INICIAL`; agora a senha nasce do
    proprio modulo e a unica falha possivel neste ponto e' a biblioteca de hash ausente. A
    GARANTIA e' a mesma e e' ela que importa: nenhuma escrita comeca sem a senha pronta, senao
    a linha ficaria com marca de troca e um hash que ninguem conhece -- conta perdida, sem
    caminho de volta a nao ser outro clique de redefinicao.
    """
    from motor_expansao.db import senhas

    def _sem_biblioteca(_senha: str) -> str:
        raise senhas.HashIndisponivel("argon2-cffi não está instalado.")

    monkeypatch.setattr(senhas, "gerar", _sem_biblioteca)
    con = _con_senha_admin(monkeypatch, propria=True, deve_trocar=False)
    with pytest.raises(senhas.HashIndisponivel):
        mod.redefinir_senha(9, autor=7)
    assert con.executados == []


def test_redefinir_alvo_inexistente_e_desconhecido(
    monkeypatch: pytest.MonkeyPatch, _sem_argon2: None
) -> None:
    con = _instalar(monkeypatch, {_MARCA_ESTADO_ADMIN: []})
    with pytest.raises(mod.UsuarioDesconhecido):
        mod.redefinir_senha(404, autor=7)
    assert con.sql_que_contem("SET senha_hash") == []
    assert con.eventos == []


def test_o_admin_nunca_le_o_hash_de_ninguem() -> None:
    """O SELECT do admin nao traz `senha_hash`: o admin nao confere senha de ninguem."""
    assert "senha_hash" not in mod.SQL_ESTADO_DA_SENHA_PARA_ADMIN


def test_exigir_troca_liga_so_a_marca(monkeypatch: pytest.MonkeyPatch) -> None:
    """A senha que a pessoa tem continua valendo -- e a data de quando ela a definiu, tambem."""
    con = _con_senha_admin(monkeypatch, propria=True, deve_trocar=False)
    saida = mod.exigir_troca(9, autor=7)

    sql, params = con.sql_que_contem("SET deve_trocar_senha_usuario")[0]
    assert "senha_hash" not in sql
    assert "senha_definida_em_usuario" not in sql
    assert params == (9,)
    assert saida["mudou"] is True
    autor, tipo, _ent, entidade_id, meta = con.eventos[0]
    assert (autor, entidade_id, tipo) == (7, 9, mod.EVENTO_TROCA_EXIGIDA)
    assert meta is None


def test_exigir_troca_de_quem_ja_esta_marcado_nao_gera_evento(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Coluna booleana: aqui o "ja' estava assim" e' verificavel, entao vale a regra da tela."""
    con = _con_senha_admin(monkeypatch, propria=True, deve_trocar=True)
    assert mod.exigir_troca(9, autor=7)["mudou"] is False
    assert con.sql_que_contem("SET deve_trocar_senha_usuario") == []
    assert con.eventos == []


def test_ninguem_exige_troca_de_si_mesmo(monkeypatch: pytest.MonkeyPatch) -> None:
    con = _con_senha_admin(monkeypatch, propria=True, deve_trocar=False)
    with pytest.raises(mod.AlvoEhOAutor):
        mod.exigir_troca(7, autor=7)
    assert con.executados == []
