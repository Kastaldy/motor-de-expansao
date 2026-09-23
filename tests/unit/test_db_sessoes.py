"""Sessao propria do piloto (D30 + decisao 2 do P19) — sem tocar banco nenhum.

O que estes testes guardam, em ordem de importancia:

1. **A trava anti-divergencia.** `sessoes.SQL_VALIDAR` e' um SUPERCONJUNTO do
   `rbac.SQL_IDENTIDADE`, e o proprio modulo declara isso como risco. Duas redacoes da
   mesma regra nao dao erro -- desencontram em SILENCIO (licao da DEC-044). O teste compara
   a parte compartilhada e fixa exatamente quais sao os extras.
2. **O token nunca vai ao banco.** O que viaja no parametro e' o hash, sempre.
3. **A trava de 5 min do toque**, que e' a razao pela qual a decisao 2 nao escolheu escrita
   por requisicao.
4. **A chave dormente**, que e' o que permite esta branch existir sem cortar o login.
"""

from __future__ import annotations

import re
from contextlib import contextmanager
from typing import Any

import pytest

from motor_expansao import db
from motor_expansao.db import postgres, rbac, sessoes


class FakeCursor:
    """`execute()` do psycopg3 devolve um Cursor, e e' de la' que sai o `rowcount`.

    O fake EXPOE `rowcount` de proposito: o codigo o le' com `getattr(..., 0)`, e um fake
    sem o atributo faria todos os testes de escrita passarem lendo o default -- ou seja,
    verdes sem exercitar a leitura que importa.
    """

    def __init__(self, linhas: list[tuple[Any, ...]], rowcount: int) -> None:
        self.linhas = linhas
        self.rowcount = rowcount

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self.linhas

    def fetchone(self) -> tuple[Any, ...] | None:
        return self.linhas[0] if self.linhas else None


class FakeConexao:
    def __init__(self, linhas: list[tuple[Any, ...]], rowcount: int = 0) -> None:
        self.linhas = linhas
        self.rowcount = rowcount
        self.executados: list[tuple[str, Any]] = []
        self.autocommit = False

    def execute(self, sql: str, params: Any = None) -> FakeCursor:
        self.executados.append((sql, params))
        return FakeCursor(self.linhas, self.rowcount)

    @contextmanager
    def transaction(self):  # type: ignore[no-untyped-def]
        yield self


class FakePool:
    def __init__(self, con: FakeConexao) -> None:
        self._con = con

    @contextmanager
    def connection(self):  # type: ignore[no-untyped-def]
        yield self._con

    def open(self, wait: bool = False) -> None: ...
    def close(self) -> None: ...


def _instalar(
    monkeypatch: pytest.MonkeyPatch,
    linhas: list[tuple[Any, ...]] | None = None,
    rowcount: int = 0,
) -> FakeConexao:
    con = FakeConexao(linhas or [], rowcount)
    monkeypatch.setattr(postgres, "_driver", lambda: lambda **_k: FakePool(con))
    monkeypatch.setenv(postgres.ENV_URL, "postgresql://fake/motor")
    return con


@pytest.fixture(autouse=True)
def _limpo(monkeypatch: pytest.MonkeyPatch) -> Any:
    db.fechar_pool()
    monkeypatch.delenv(sessoes.ENV_AUTENTICACAO_PROPRIA, raising=False)
    yield
    db.fechar_pool()


def _sql_do(con: FakeConexao, fragmento: str) -> tuple[str, Any]:
    """O primeiro comando executado que casa o fragmento. Falha se nenhum casar."""
    for sql, params in con.executados:
        if fragmento in sql:
            return sql, params
    raise AssertionError(
        f"nenhum comando executado contem {fragmento!r}; executados: "
        + ", ".join(sql.strip().split("\n")[0] for sql, _ in con.executados)
    )


# --------------------------------------------------------------------------------------
# 1. A trava anti-divergencia (o teste mais importante deste arquivo)
# --------------------------------------------------------------------------------------

#: As tres primeiras colunas de `SQL_IDENTIDADE`, na ordem. Se o RBAC mudar isto, a sessao
#: tem de mudar junto -- e e' o teste abaixo que obriga.
_COLUNAS_COMPARTILHADAS = ("u.id_usuario", "p.nome_perfil", "pe.chave")

#: O que a sessao acrescenta, e NADA MAIS. Fixado para que uma coluna nova entre com
#: decisao, nao de carona.
#: `deve_trocar_senha_usuario` entrou na D31: a troca virou BLOQUEIO, e o portao de sessao
#: precisa saber disso a cada requisicao guardada. Buscar a parte seria segunda ida ao banco
#: para um dado que ja' esta' na linha que este JOIN le'.
_EXTRAS_DA_SESSAO = (
    "u.login_usuario",
    "s.id_sessao",
    "s.ultimo_acesso_em_sessao",
    "u.deve_trocar_senha_usuario",
)


def _colunas_do_select(sql: str) -> list[str]:
    corpo = re.search(r"SELECT\s+(.*?)\s+FROM", sql, re.IGNORECASE | re.DOTALL)
    assert corpo is not None, f"SQL sem SELECT ... FROM legivel: {sql[:80]!r}"
    return [c.strip() for c in corpo.group(1).split(",")]


def test_a_validacao_de_sessao_nao_divergiu_do_rbac() -> None:
    """A parte compartilhada e' IGUAL, e os extras sao exatamente os tres declarados.

    Por que isto existe: a D30 decidiu que validar sessao entra como um JOIN na consulta de
    identidade que JA' acontece -- e, para nao mexer no `rbac.py` (que esta' no caminho de
    autorizacao vivo), a consulta foi escrita duas vezes. O modulo declara o risco no
    docstring; este teste e' o que impede a declaracao de ser so' prosa.
    """
    do_rbac = _colunas_do_select(rbac.SQL_IDENTIDADE)
    da_sessao = _colunas_do_select(sessoes.SQL_VALIDAR)

    assert tuple(do_rbac) == _COLUNAS_COMPARTILHADAS, (
        "o SELECT do `rbac.SQL_IDENTIDADE` mudou: atualize `_COLUNAS_COMPARTILHADAS` e "
        "confira se `sessoes.SQL_VALIDAR` precisa mudar junto"
    )
    assert tuple(da_sessao[: len(do_rbac)]) == _COLUNAS_COMPARTILHADAS, (
        "`sessoes.SQL_VALIDAR` deixou de comecar pelas mesmas colunas do RBAC -- as duas "
        "redacoes divergiram, que e' o defeito SILENCIOSO que este teste existe para pegar"
    )
    assert tuple(da_sessao[len(do_rbac) :]) == _EXTRAS_DA_SESSAO

    # Os JOINs do RBAC continuam todos presentes na consulta de sessao.
    for juncao in ("JOIN perfis p", "LEFT JOIN perfil_permissoes pp", "LEFT JOIN permissoes pe"):
        assert juncao in sessoes.SQL_VALIDAR, f"a consulta de sessao perdeu `{juncao}`"


def test_a_comparacao_acima_enxerga_sql_de_verdade() -> None:
    """Sem esta metade, o teste acima e' garantia FALSA.

    Um regex que parou de casar -- SQL remontado, constante renomeada -- deixaria o
    primeiro teste verde para sempre comparando listas vazias. E' a mesma licao que esta
    suite ja' aprendeu caro em `test_ip_nao_entra_em_eventos.py`: guarda que nao pode falhar
    nao guarda nada.
    """
    assert len(_colunas_do_select(rbac.SQL_IDENTIDADE)) == 3
    # DERIVADO de `_EXTRAS_DA_SESSAO`, e nao um numero cravado. Ate' 18/09/2026 este `6` era
    # literal, entao acrescentar uma coluna a' consulta exigia lembrar de bumpar DOIS lugares --
    # e o segundo falhava com "assert 7 == 6", que nao explica nada a quem chegou agora. O teste
    # continua servindo ao que existe para fazer: um regex quebrado devolveria 0 ou 1 coluna e
    # nenhuma das duas assercoes fecharia.
    assert len(_colunas_do_select(sessoes.SQL_VALIDAR)) == 3 + len(_EXTRAS_DA_SESSAO)


def test_os_tres_filtros_de_sessao_viva_estao_na_consulta() -> None:
    """Revogada, teto absoluto e inatividade. Perder um e' aceitar sessao morta."""
    sql = sessoes.SQL_VALIDAR
    assert "revogada_em_sessao IS NULL" in sql
    assert "expira_em_sessao > now()" in sql
    assert "ultimo_acesso_em_sessao > now() - make_interval(mins => %s)" in sql
    # `u.ativo` (D9/D23): desativar alguem nega na requisicao SEGUINTE, sem revogar sessao
    # por sessao.
    assert "u.ativo" in sql


# --------------------------------------------------------------------------------------
# 2. O token nunca vai ao banco
# --------------------------------------------------------------------------------------


def test_o_que_vai_ao_banco_e_o_HASH_nunca_o_token(monkeypatch: pytest.MonkeyPatch) -> None:
    con = _instalar(monkeypatch, [(42, "2026-09-18T00:00:00Z")])
    aberta = sessoes.abrir(id_usuario=7)

    _sql, params = _sql_do(con, "INSERT INTO sessoes")
    assert sessoes.hash_do_token(aberta.token) in params
    assert aberta.token not in params, "o token EM CLARO chegou ao banco"
    assert aberta.id_sessao == 42


def test_o_hash_nao_e_o_token_e_e_estavel() -> None:
    token = sessoes.novo_token()
    assert sessoes.hash_do_token(token) != token
    assert sessoes.hash_do_token(token) == sessoes.hash_do_token(token)
    assert len(sessoes.hash_do_token(token)) == 64  # sha256 em hex


def test_tokens_nao_repetem() -> None:
    assert len({sessoes.novo_token() for _ in range(50)}) == 50


def test_validar_manda_o_hash_e_a_inatividade(monkeypatch: pytest.MonkeyPatch) -> None:
    con = _instalar(monkeypatch, [(7, "growth", "rede.ver", "vinicius", 42, None, False)])
    valida = sessoes.validar("token-de-teste")

    _sql, params = _sql_do(con, "FROM sessoes s")
    assert params == (sessoes.hash_do_token("token-de-teste"), sessoes.INATIVIDADE_MIN)
    assert valida is not None
    assert valida.identidade.id_usuario == 7
    assert valida.identidade.login == "vinicius", "o login veio sintetizado, nao do banco"
    assert valida.id_sessao == 42


def test_validar_agrega_as_permissoes_de_varias_linhas(monkeypatch: pytest.MonkeyPatch) -> None:
    _instalar(
        monkeypatch,
        [
            (7, "growth", "rede.ver", "vinicius", 42, None, False),
            (7, "growth", "viabilidade.simular", "vinicius", 42, None, False),
        ],
    )
    valida = sessoes.validar("t")
    assert valida is not None
    assert valida.identidade.pode("rede.ver")
    assert valida.identidade.pode("viabilidade.simular")


def test_perfil_sem_permissao_nenhuma_existe_e_nao_pode_nada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`chave` nula pelo LEFT JOIN: a pessoa EXISTE e nao pode nada -- diferente de `None`."""
    _instalar(monkeypatch, [(7, "novato", None, "alguem", 42, None, False)])
    valida = sessoes.validar("t")
    assert valida is not None
    assert valida.identidade.permissoes == frozenset()


def test_sem_linha_nao_ha_sessao(monkeypatch: pytest.MonkeyPatch) -> None:
    _instalar(monkeypatch, [])
    assert sessoes.validar("t") is None


def test_token_vazio_nao_consulta_o_banco(monkeypatch: pytest.MonkeyPatch) -> None:
    """Curto-circuito: sem token nao ha' o que perguntar, e perguntar custaria uma ida."""
    con = _instalar(monkeypatch, [(7, "growth", "rede.ver", "v", 42, None, False)])
    assert sessoes.validar("") is None
    assert con.executados == [], "consultou o banco com token vazio"


# --------------------------------------------------------------------------------------
# 3. A trava de 5 min do toque
# --------------------------------------------------------------------------------------


def test_o_toque_manda_a_trava_no_proprio_UPDATE(monkeypatch: pytest.MonkeyPatch) -> None:
    """A trava vive no `WHERE`, e nao num `if` do Python: assim duas requisicoes
    simultaneas da mesma sessao nao se atropelam -- a segunda nao acha linha."""
    con = _instalar(monkeypatch, rowcount=1)
    assert sessoes.tocar(id_sessao=42, id_usuario=7) is True

    sql, params = _sql_do(con, "UPDATE sessoes SET ultimo_acesso_em_sessao")
    assert params == (42, sessoes.TRAVA_TOQUE_MIN)
    assert "ultimo_acesso_em_sessao < now() - make_interval(mins => %s)" in sql
    assert "revogada_em_sessao IS NULL" in sql, "tocaria sessao ja' revogada"


def test_o_toque_relata_quando_a_trava_barrou(monkeypatch: pytest.MonkeyPatch) -> None:
    """`rowcount = 0` = a trava barrou. Relatar isso e' o que permite medir e testar."""
    _instalar(monkeypatch, rowcount=0)
    assert sessoes.tocar(id_sessao=42, id_usuario=7) is False


# --------------------------------------------------------------------------------------
# 4. Revogacao — e o autor certo no carimbo
# --------------------------------------------------------------------------------------


def test_revogar_e_UPDATE_e_nunca_DELETE(monkeypatch: pytest.MonkeyPatch) -> None:
    """Auditoria: "foi encerrada, quando" e' dado. Apagar responderia "nunca existiu" --
    e o papel `app` nem tem `DELETE` em `sessoes` (D20/D30), entao seria negado."""
    con = _instalar(monkeypatch, rowcount=1)
    assert sessoes.revogar(token="t", id_usuario=7) is True

    sql, params = _sql_do(con, "UPDATE sessoes SET revogada_em_sessao")
    assert params == (sessoes.hash_do_token("t"),)
    assert "DELETE" not in sql.upper()


def test_logout_repetido_nao_e_erro(monkeypatch: pytest.MonkeyPatch) -> None:
    _instalar(monkeypatch, rowcount=0)
    assert sessoes.revogar(token="t", id_usuario=7) is False


def test_revogar_todas_devolve_quantas_cairam(monkeypatch: pytest.MonkeyPatch) -> None:
    con = _instalar(monkeypatch, rowcount=3)
    assert sessoes.revogar_todas_do_usuario(id_usuario=7) == 3
    _sql, params = _sql_do(con, "WHERE id_usuario = %s AND revogada_em_sessao IS NULL")
    assert params == (7,)


def test_o_carimbo_separa_quem_agiu_de_quem_sofreu(monkeypatch: pytest.MonkeyPatch) -> None:
    """Admin redefinindo a senha de outra pessoa: o ato e' DELE.

    Sem o `autor`, a auditoria atribuiria a acao a' vitima -- e o §3.7 existe justamente
    para responder QUEM agiu. O carimbo e' o PRIMEIRO comando da transacao (D28), entao
    basta olhar o primeiro executado.
    """
    con = _instalar(monkeypatch, rowcount=1)
    sessoes.revogar_todas_do_usuario(id_usuario=7, autor=99)

    primeiro_sql, primeiro_params = con.executados[0]
    assert "set_config" in primeiro_sql
    assert primeiro_params == ("99",), "carimbou a vitima como autora"


def test_sem_autor_o_carimbo_e_a_propria_pessoa(monkeypatch: pytest.MonkeyPatch) -> None:
    """Troca da PROPRIA senha: quem age e quem sofre coincidem, e o default cobre isso."""
    con = _instalar(monkeypatch, rowcount=1)
    sessoes.revogar_todas_do_usuario(id_usuario=7)
    assert con.executados[0][1] == ("7",)


# --------------------------------------------------------------------------------------
# 5. A chave dormente e os numeros da decisao 2
# --------------------------------------------------------------------------------------


def test_a_autenticacao_propria_nasce_DESLIGADA() -> None:
    """E' o que permite esta branch ir para producao sem cortar o login de ninguem."""
    assert sessoes.ligada() is False


@pytest.mark.parametrize("valor", ["1", "true", "TRUE", "sim", "yes"])
def test_a_chave_liga_com_os_valores_do_idioma_da_casa(
    monkeypatch: pytest.MonkeyPatch, valor: str
) -> None:
    monkeypatch.setenv(sessoes.ENV_AUTENTICACAO_PROPRIA, valor)
    assert sessoes.ligada() is True


@pytest.mark.parametrize("valor", ["", "0", "nao", "abacaxi", "   "])
def test_lixo_na_chave_nao_liga_nada(monkeypatch: pytest.MonkeyPatch, valor: str) -> None:
    """Fail-closed: chave de autenticacao nao se liga por typo."""
    monkeypatch.setenv(sessoes.ENV_AUTENTICACAO_PROPRIA, valor)
    assert sessoes.ligada() is False


def test_os_numeros_sao_os_da_decisao_2() -> None:
    """8h/30min/5min, REPRODUZINDO o Authelia.

    O nome deste teste carrega a decisao de proposito: mexer nestes numeros derrubou o
    login da rede por ~4h em 06/08/2026, e mudar a constante sem reabrir a decisao 2 e'
    exatamente o que nao pode acontecer em silencio.
    """
    assert sessoes.DURACAO_SESSAO_H == 8
    assert sessoes.INATIVIDADE_MIN == 30
    assert sessoes.TRAVA_TOQUE_MIN == 5


def test_abrir_manda_a_duracao_da_decisao_2(monkeypatch: pytest.MonkeyPatch) -> None:
    con = _instalar(monkeypatch, [(42, None)])
    sessoes.abrir(id_usuario=7)
    _sql, params = _sql_do(con, "INSERT INTO sessoes")
    # Por POSICAO, e nao `[-1]`: a 020 acrescentou `ip` e `user_agent` DEPOIS da duracao,
    # e o indice negativo passou a apontar para o user-agent. O teste ficava vermelho
    # dizendo "None != 8", que nao explica nada a quem chegou agora.
    assert params[2] == sessoes.DURACAO_SESSAO_H


# --------------------------------------------------------------------------------------
# De onde a sessao veio (020) — `ip` e `user_agent`
# --------------------------------------------------------------------------------------


def test_abrir_grava_a_origem(monkeypatch: pytest.MonkeyPatch) -> None:
    """As duas colunas da 020 entram no MESMO INSERT da sessao."""
    con = _instalar(monkeypatch, [(42, None)])
    sessoes.abrir(id_usuario=7, ip="203.0.113.9", user_agent="Mozilla/5.0 (Teste)")

    sql, params = [(s, p) for s, p in con.executados if "INSERT INTO sessoes" in s][0]
    assert "ip_sessao" in sql and "user_agent_sessao" in sql
    assert params[3] == "203.0.113.9"
    assert params[4] == "Mozilla/5.0 (Teste)"


def test_origem_DESCONHECIDA_e_estado_legitimo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sessao sem origem nao pode derrubar o login.

    Falhar aqui por falta de header trocaria um dado ACESSORIO (de onde veio) por o
    principal (entrar). Os dois sao opcionais e nulos por default.
    """
    con = _instalar(monkeypatch, [(42, None)])
    sessoes.abrir(id_usuario=7)
    _sql, params = [(s, p) for s, p in con.executados if "INSERT INTO sessoes" in s][0]
    assert params[3] is None
    assert params[4] is None


def test_user_agent_gigante_e_TRUNCADO_e_nao_recusado(monkeypatch: pytest.MonkeyPatch) -> None:
    """O header vem do CLIENTE e pode ter qualquer tamanho.

    A 020 recusa um `CHECK` de comprimento no banco exatamente por isto: la', um
    `User-Agent` gigante viraria erro de escrita, ou seja, LOGIN QUE FALHA -- negacao de
    servico por cabecalho, de graca. Aqui o excesso e' cortado.
    """
    con = _instalar(monkeypatch, [(42, None)])
    sessoes.abrir(id_usuario=7, user_agent="A" * 5000)
    _sql, params = [(s, p) for s, p in con.executados if "INSERT INTO sessoes" in s][0]
    assert len(params[4]) == sessoes.TETO_USER_AGENT


def test_user_agent_vazio_vira_NULO_e_nao_string_vazia(monkeypatch: pytest.MonkeyPatch) -> None:
    """`''` afirmaria que o cliente se identificou com nada; nulo diz que nao se sabe."""
    con = _instalar(monkeypatch, [(42, None)])
    sessoes.abrir(id_usuario=7, user_agent="   ")
    _sql, params = [(s, p) for s, p in con.executados if "INSERT INTO sessoes" in s][0]
    assert params[4] is None


def test_este_modulo_NAO_le_header_nenhum() -> None:
    """A resolucao do IP mora em UM lugar so', e nao e' aqui.

    Usar o PRIMEIRO token do `X-Forwarded-For` em vez do ultimo foi vulnerabilidade real
    (pentest de 19/08/2026: `X-Forwarded-For: 8.8.8.8` fazia a acao constar de um IP
    arbitrario). O resolvedor correto e' `app.py::_ip_real_do_xff`; uma segunda redacao aqui
    seria a que esquece a licao -- e este teste fica vermelho se ela aparecer.
    """
    import ast
    from pathlib import Path

    # Por AST, e nao por texto: a primeira versao deste teste varria o fonte cru e ficava
    # VERMELHA por causa da PROSA -- a docstring do `abrir` cita o `X-Forwarded-For` de
    # proposito, para ensinar a licao do pentest. Comentario que explica a regra nao e'
    # codigo que a viola, e um teste que nao distingue os dois ensina a apagar a explicacao.
    arvore = ast.parse(Path(sessoes.__file__).read_text(encoding="utf-8"))
    lidos: list[str] = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.Attribute) and no.attr in {"headers", "cookies"}:
            lidos.append(no.attr)
        if isinstance(no, ast.Name) and no.id == "request":
            lidos.append(no.id)
    assert lidos == [], f"o modulo de sessao passou a ler a requisicao: {sorted(set(lidos))}"


# --------------------------------------------------------------------------------------
# Retencao da ORIGEM — o P15 fechado em 23/09/2026 (3 meses)
# --------------------------------------------------------------------------------------


def test_a_retencao_e_de_tres_meses_e_bate_com_a_trilha() -> None:
    """90 dias, e o numero nao e' novo.

    E' o MESMO prazo que a DEC-027 ja' pratica para a trilha de acesso em arquivo, que guarda
    o MESMO dado (IP e user-agent). Dois prazos diferentes para o mesmo dado seriam duas
    politicas de privacidade dentro do mesmo sistema -- e a que alguem citasse seria sempre a
    outra.
    """
    assert sessoes.RETENCAO_ORIGEM_DIAS == 90


def test_o_expurgo_ANONIMIZA_e_nao_apaga() -> None:
    """O que tem prazo e' o DADO PESSOAL, nao o registro da sessao.

    Zeradas as duas colunas, a linha continua respondendo "entrou em tal dia, revogada em tal
    outro" -- auditoria sem PII. `DELETE` destruiria esse historico e contrariaria o desenho da
    018, onde revogar e' `UPDATE` e nunca `DELETE` (o papel `app` nem tem `DELETE`).
    """
    sql = sessoes.SQL_EXPURGAR_ORIGEM
    assert sql.strip().startswith("UPDATE sessoes")
    assert "DELETE" not in sql.upper()
    assert "ip_sessao = NULL" in sql and "user_agent_sessao = NULL" in sql


def test_o_expurgo_conta_da_COLETA_e_nao_do_vencimento() -> None:
    """`criado_em_sessao`, nao `expira_em_sessao`: o prazo de retencao conta de quando o dado
    foi COLETADO. Usar o vencimento daria 8h a mais, de graca, e por um motivo que nao existe."""
    for sql in (sessoes.SQL_EXPURGAR_ORIGEM, sessoes.SQL_CONTAR_ORIGEM_VENCIDA):
        assert "criado_em_sessao < now() - make_interval(days => %s)" in sql
        assert "expira_em_sessao" not in sql


def test_o_expurgo_e_IDEMPOTENTE_por_construcao() -> None:
    """O `WHERE` exige pelo menos uma coluna preenchida.

    Sem isso, cada execucao reescreveria todas as linhas velhas: o `rowcount` passaria a dizer
    "quantas sao velhas" em vez de "quantas foram expurgadas AGORA", e o operador perderia o
    unico sinal de que o expurgo esta' em dia.
    """
    assert "(ip_sessao IS NOT NULL OR user_agent_sessao IS NOT NULL)" in sessoes.SQL_EXPURGAR_ORIGEM


def test_a_contagem_usa_O_MESMO_recorte_do_expurgo() -> None:
    """Duas redacoes do mesmo recorte divergem em silencio, e aqui a divergencia seria cara: o
    `--simular` diria um numero e a execucao faria outra coisa."""
    import re

    def _recorte(sql: str) -> str:
        return re.sub(r"\s+", " ", sql[sql.upper().index("WHERE") :]).strip()

    assert _recorte(sessoes.SQL_EXPURGAR_ORIGEM) == _recorte(sessoes.SQL_CONTAR_ORIGEM_VENCIDA)
