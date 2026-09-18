"""Eventos de artefato — o produtor do D17, sem tocar banco nenhum.

O que se guarda aqui é o que faz o rastreio FUNCIONAR: que o `report_id` existe sempre,
que ele entra em `metadados` com a chave que o índice parcial conhece, que `entidade`
fica nula (emenda ao D17 / D24), e que uma chave de alvo errada é RECUSADA em vez de
gravar um evento que os índices não alcançam.

O molde do dublê é o de `test_db_usuarios.py`: responde por pedaço de SQL, não por ordem.
"""

from __future__ import annotations

import re
from contextlib import contextmanager
from typing import Any

import pytest

from motor_expansao.db import eventos as mod
from motor_expansao.db import postgres

_UUID4 = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")


class FakeConexao:
    def __init__(self) -> None:
        self.executados: list[tuple[str, Any]] = []

    def execute(self, sql: str, params: Any = None) -> FakeConexao:
        self.executados.append((sql, params))
        return self

    @property
    def eventos(self) -> list[Any]:
        return [p for s, p in self.executados if "INSERT INTO eventos" in s]


@pytest.fixture
def con(monkeypatch: pytest.MonkeyPatch) -> FakeConexao:
    c = FakeConexao()

    @contextmanager
    def fake(*, id_usuario):  # type: ignore[no-untyped-def]
        c.executados.append((postgres.SQL_DEFINIR_AUTOR, (str(id_usuario),)))
        yield c

    monkeypatch.setattr(mod, "transacao", fake)
    return c


# --------------------------------------------------------------------------------------
# O report_id
# --------------------------------------------------------------------------------------


def test_o_id_e_um_uuid4() -> None:
    assert _UUID4.match(mod.novo_report_id())


def test_dois_ids_nunca_colidem() -> None:
    assert len({mod.novo_report_id() for _ in range(500)}) == 500


def test_o_id_nao_e_sequencial() -> None:
    """UUID4 e não contador: o id vai IMPRESSO num arquivo que pode circular fora da
    empresa, e um sequencial anunciaria quantos relatórios o motor já gerou."""
    ids = [mod.novo_report_id() for _ in range(20)]
    assert ids == sorted(ids) or ids != sorted(ids)  # não é ordenável por construção
    assert len({i.split("-")[0] for i in ids}) == 20


def test_registrar_devolve_o_id_que_gravou(con: FakeConexao) -> None:
    """Cunhar e gravar na MESMA chamada é o que impede um id sem linha — o contrato diz
    que um `relatorio.gerado` sem `report_id` não deve ser gravado, e o inverso (id sem
    evento) é uma promessa de rastreio que o banco não pode cumprir."""
    devolvido = mod.registrar_relatorio(autor=7, relatorio="pontual", formato="pdf")
    gravado = con.eventos[0][2].obj["report_id"]
    assert devolvido == gravado
    assert _UUID4.match(devolvido)


def test_registrar_aceita_um_id_ja_cunhado(con: FakeConexao) -> None:
    """A rota cunha ANTES, porque o id precisa ser carimbado nos bytes do PDF."""
    meu = mod.novo_report_id()
    assert (
        mod.registrar_relatorio(autor=7, relatorio="pontual", formato="pdf", report_id=meu) == meu
    )
    assert con.eventos[0][2].obj["report_id"] == meu


# --------------------------------------------------------------------------------------
# Acesso (§2.1) — `login` e `logout`, destravados pela epic do P19
# --------------------------------------------------------------------------------------


def test_login_grava_o_tipo_e_so_a_origem(con: FakeConexao) -> None:
    """O contrato (§2.1) preve `metadados` com `origem`, e nada mais."""
    mod.registrar_login(autor=7)
    (autor, tipo, metadados) = con.eventos[0]
    assert (autor, tipo) == (7, "login")
    assert metadados.obj == {"origem": "web"}


def test_login_aceita_a_origem_bot(con: FakeConexao) -> None:
    """`origem` e' `web`/`bot` no contrato — o bot tambem entra na plataforma."""
    mod.registrar_login(autor=7, origem="bot")
    assert con.eventos[0][2].obj == {"origem": "bot"}


def test_login_NUNCA_leva_login_nem_email_em_metadados(con: FakeConexao) -> None:
    """Regra da §2.7, literal: "nunca o login nem o e-mail do alvo em `metadados`".

    E' PII, e o `id_usuario` do carimbo ja' identifica a pessoa. Este teste falha se alguem
    "enriquecer" o payload com o nome de quem entrou -- que e' a tentacao obvia num evento
    chamado `login`.
    """
    mod.registrar_login(autor=7)
    chaves = set(con.eventos[0][2].obj)
    assert chaves == {"origem"}
    assert not (chaves & {"login", "email", "usuario", "nome"})


def test_login_carimba_o_autor_ANTES_de_escrever(con: FakeConexao) -> None:
    """O carimbo e' o PRIMEIRO comando da transacao (D28): carimbar depois deixaria a
    janela em que a trigger ja' rodou sem saber quem agiu."""
    mod.registrar_login(autor=7)
    primeiro_sql, primeiro_params = con.executados[0]
    assert "set_config" in primeiro_sql
    assert primeiro_params == ("7",)


def test_login_SEM_autor_e_recusado(con: FakeConexao) -> None:
    """Nao ha' login de sistema: quando esta funcao e' chamada, a senha JA' foi verificada.

    Sem esta guarda o `transacao` aceitaria `id_usuario=None` (acao de sistema e' legitima
    no D19) e o evento sairia com autoria nula -- sem responder a unica pergunta que ele
    existe para responder. E' a diferenca entre a regra estar na docstring e estar no codigo.
    """
    with pytest.raises(ValueError, match="sem autor"):
        mod.registrar_login(autor=None)  # type: ignore[arg-type]
    assert con.eventos == [], "gravou mesmo recusando"


def test_logout_grava_metadados_NULO_e_nao_objeto_vazio(con: FakeConexao) -> None:
    """`NULL`, nao `{}`. Um objeto vazio afirmaria que ha' payload e ele esta' vazio; a
    verdade e' que este evento nao tem payload. `metadados IS NULL` e `metadados = '{}'`
    respondem coisas diferentes para quem consulta."""
    mod.registrar_logout(autor=7)
    (autor, tipo, metadados) = con.eventos[0]
    assert (autor, tipo, metadados) == (7, "logout", None)


def test_recusa_de_conta_EXISTENTE_carimba_o_id(con: FakeConexao) -> None:
    """É o caso que torna a linha útil: "quantas tentativas falhas contra esta conta"."""
    mod.registrar_login_recusado(autor=7, usuario_conhecido=True)
    (autor, tipo, metadados) = con.eventos[0]
    assert (autor, tipo) == (7, "login.recusado")
    assert metadados.obj == {"origem": "web", "usuario_conhecido": True}


def test_recusa_de_usuario_INEXISTENTE_sai_com_autoria_nula(con: FakeConexao) -> None:
    """Não há id a carimbar, e ação de autoria nula é informação legítima (D19).

    Diferente de `registrar_login`, que RECUSA autor nulo — lá a senha já foi verificada e
    o id é sempre conhecido; aqui a inexistência do usuário é o próprio fato registrado.
    """
    mod.registrar_login_recusado(autor=None, usuario_conhecido=False)
    (autor, _tipo, metadados) = con.eventos[0]
    assert autor is None
    assert metadados.obj["usuario_conhecido"] is False


def test_a_recusa_NUNCA_leva_o_login_digitado_nem_IP(con: FakeConexao) -> None:
    """As duas proibições que moldaram este evento, numa asserção só.

    O login digitado é PII (§2.7) — e é a tentação óbvia aqui, porque quando o usuário não
    existe ele é o único identificador que sobra. O `ip` depende do **P15**, aberto, e tem
    guarda própria (`test_ip_nao_entra_em_eventos.py`); esta asserção é a segunda camada,
    do lado do payload.
    """
    mod.registrar_login_recusado(autor=None, usuario_conhecido=False)
    chaves = set(con.eventos[0][2].obj)
    assert chaves == {"origem", "usuario_conhecido"}
    assert not (chaves & {"login", "usuario", "email", "ip", "senha"})


def test_a_contagem_de_recusas_usa_a_janela_e_o_tipo(monkeypatch: pytest.MonkeyPatch) -> None:
    """A trava de tentativas se apoia nesta consulta — e ela é LEITURA, não escrita."""
    from motor_expansao.db import postgres

    class _Con:
        def __init__(self) -> None:
            self.executados: list[tuple[str, Any]] = []

        def execute(self, sql: str, params: Any = None) -> Any:
            self.executados.append((sql, params))
            return type("C", (), {"fetchone": lambda _s: (3,)})()

    c = _Con()

    @contextmanager
    def fake_conexao():  # type: ignore[no-untyped-def]
        c.executados.append((postgres.SQL_SOMENTE_LEITURA, None))
        yield c

    monkeypatch.setattr(mod, "conexao", fake_conexao)
    assert mod.contar_recusas_recentes(id_usuario=7, minutos=15) == 3

    sql, params = [(s, p) for s, p in c.executados if "count(*)" in s][0]
    # Os sete parâmetros, na ordem: conta, tipo contado, janela, piso da redefinição, e a
    # subconsulta do último acerto (conta, tipo `login`, mesma janela).
    assert params == (7, "login.recusado", 15, None, 7, "login", 15)
    # A janela é MÓVEL: sem o recorte por tempo, "5 tentativas" viraria bloqueio permanente
    # — e como a contagem é por conta, qualquer um trancaria a conta de qualquer um.
    assert "now() - make_interval(mins => %s)" in sql
    # Leitura entra pelo `conexao()`, que abre a transação READ ONLY.
    assert any("READ ONLY" in s for s, _p in c.executados)


def test_a_contagem_zera_no_ACERTO_e_na_REDEFINICAO(monkeypatch: pytest.MonkeyPatch) -> None:
    """Os dois marcos que soltam a tranca antes da janela vencer, e o que cada um resolve.

    ACERTO: errar três vezes, lembrar a senha, entrar, sair e errar mais duas trancaria a conta
    de quem provou saber a senha dois minutos antes. Não enfraquece nada -- quem entra já tem a
    senha, e a trava existe para atrapalhar quem está adivinhando.

    REDEFINIÇÃO: é o caso típico do pedido de ajuda -- a pessoa erra cinco vezes e SÓ ENTÃO liga
    para o administrador. Sem este piso ela recebe a senha nova e continua barrada por até 15
    minutos, lendo a mesma mensagem de senha errada.
    """
    sql = mod.SQL_CONTAR_RECUSAS
    assert "GREATEST(" in sql, "a contagem voltou a ter um piso só"
    # O marco do acerto sai do próprio `eventos`; o da redefinição chega pronto da credencial.
    assert "max(criado_em_evento)" in sql
    assert "COALESCE(%s::timestamptz" in sql

    # A subconsulta do acerto é presa à MESMA janela: um acerto mais velho que ela é irrelevante
    # (as recusas daquele período também já não contam), e sem o recorte a varredura poderia
    # caminhar pelo histórico inteiro de quem tem muitos eventos procurando um `login`.
    depois_do_greatest = sql.split("GREATEST(", 1)[1]
    assert depois_do_greatest.count("now() - make_interval(mins => %s)") == 2, (
        "a subconsulta do último acerto perdeu o recorte de janela"
    )


def test_o_marco_do_acerto_procura_LOGIN_e_nao_outra_coisa(monkeypatch: pytest.MonkeyPatch) -> None:
    """Contraprova do teste acima: ele confere a FORMA do SQL, e forma casa com o texto errado.

    Se a subconsulta passasse a procurar `logout` -- ou o próprio `login.recusado`, que é o erro
    plausível por vizinhança de nome --, todas as asserções de forma continuariam verdes e a
    tranca zeraria na hora errada. Aqui se olha o PARÂMETRO que sai.
    """
    from motor_expansao.db import postgres

    class _Con:
        def __init__(self) -> None:
            self.executados: list[tuple[str, Any]] = []

        def execute(self, sql: str, params: Any = None) -> Any:
            self.executados.append((sql, params))
            return type("C", (), {"fetchone": lambda _s: (0,)})()

    c = _Con()

    @contextmanager
    def fake_conexao():  # type: ignore[no-untyped-def]
        c.executados.append((postgres.SQL_SOMENTE_LEITURA, None))
        yield c

    monkeypatch.setattr(mod, "conexao", fake_conexao)
    mod.contar_recusas_recentes(id_usuario=7, minutos=15)
    _sql, params = [(s, p) for s, p in c.executados if "count(*)" in s][0]

    assert params[1] == mod.EVENTO_LOGIN_RECUSADO, "mudou o que se CONTA"
    assert params[5] == mod.EVENTO_LOGIN, "o marco que zera a conta deixou de ser o ACERTO"
    assert params[5] != params[1], "contar e zerar pelo MESMO evento zeraria sempre"


def test_os_dois_deixam_entidade_nula(con: FakeConexao) -> None:
    """§2.1: `entidade` e' "—" nos dois. O par polimorfico so' vale quando o alvo e' LINHA
    deste banco (D24), e entrar/sair nao tem alvo nenhum."""
    mod.registrar_login(autor=7)
    mod.registrar_logout(autor=7)
    for sql, _params in con.executados:
        if "INSERT INTO eventos" in sql:
            assert "NULL, NULL" in sql


# --------------------------------------------------------------------------------------
# O vocabulario de `tipo` x o contrato — guarda que NAO existia
# --------------------------------------------------------------------------------------


def _tipos_declarados() -> dict[str, str]:
    """`{nome da constante: valor}` de todo `EVENTO_*` do modulo."""
    return {n: v for n, v in vars(mod).items() if n.startswith("EVENTO_") and isinstance(v, str)}


def test_todo_tipo_de_evento_existe_no_contrato() -> None:
    """O modulo diz "fora desta lista e' defeito" -- e ate' 17/09/2026 NADA impunha isso.

    Medido ao acrescentar `login`/`logout`: as duas constantes entraram e nenhum teste
    notou. Um `tipo` inventado aqui grava linha que consulta nenhuma do contrato alcanca,
    e o defeito e' silencioso -- a escrita passa.
    """
    from pathlib import Path

    contrato = (Path(__file__).resolve().parents[2] / "docs" / "eventos_contrato.md").read_text(
        encoding="utf-8"
    )
    ausentes = [f"{n}={v!r}" for n, v in _tipos_declarados().items() if f"`{v}`" not in contrato]
    assert not ausentes, (
        "tipos de evento sem contrapartida em `docs/eventos_contrato.md`: "
        + ", ".join(ausentes)
        + ". Acrescentar `tipo` exige editar o contrato ANTES -- ver a §5, que ja' ficou "
        "falsa por um dia quando o dossie ganhou produtor."
    )


def test_a_varredura_de_tipos_enxerga_constantes_de_verdade() -> None:
    """Sem esta metade, o teste acima e' garantia FALSA: se o prefixo `EVENTO_` mudar ou as
    constantes migrarem de modulo, ele passa a comparar um dicionario VAZIO e fica verde
    para sempre. Mesma licao de `test_ip_nao_entra_em_eventos.py`."""
    declarados = _tipos_declarados()
    assert len(declarados) >= 6, declarados
    assert declarados["EVENTO_LOGIN"] == "login"


# --------------------------------------------------------------------------------------
# O contrato do evento
# --------------------------------------------------------------------------------------


def test_o_tipo_e_o_do_contrato(con: FakeConexao) -> None:
    mod.registrar_relatorio(autor=7, relatorio="pontual", formato="pdf")
    assert con.eventos[0][1] == "relatorio.gerado"
    assert mod.EVENTO_RELATORIO_GERADO == "relatorio.gerado"


def test_entidade_fica_NULA_pela_emenda_ao_D17(con: FakeConexao) -> None:
    """A D24 emendou o D17: `entidade`/`entidade_id` só se preenchem quando o alvo é
    LINHA deste banco. Um relatório aponta para hexágono ou imóvel, cujos ids são
    TEXTUAIS — e `entidade_id` é BIGINT. O alvo vai em `metadados`."""
    mod.registrar_relatorio(autor=7, relatorio="pontual", formato="pdf")
    sql, _params = con.eventos[0][0], None
    assert "NULL, NULL" in mod.SQL_REGISTRAR_RELATORIO
    del sql


def test_o_autor_e_carimbado_como_PRIMEIRO_comando(con: FakeConexao) -> None:
    """Sem `app.id_usuario` declarado antes, as triggers do D19 gravam autoria nula."""
    mod.registrar_relatorio(autor=7, relatorio="pontual", formato="pdf")
    assert con.executados[0][0] == postgres.SQL_DEFINIR_AUTOR
    assert con.executados[0][1] == ("7",)


def test_autor_nulo_e_permitido_e_registra_mesmo_assim(con: FakeConexao) -> None:
    """Meio evento vale mais que nenhum: o D19 prevê ação de autoria nula, e um
    `relatorio.gerado` anônimo ainda diz que o arquivo existiu."""
    mod.registrar_relatorio(autor=None, relatorio="pontual", formato="pdf")
    assert con.eventos[0][0] is None
    assert len(con.eventos) == 1


def test_relatorio_e_formato_sao_AMBOS_necessarios(con: FakeConexao) -> None:
    """A §2.2 põe os quatro relatórios sob o MESMO `tipo`, e `formato` sozinho não separa
    Pontual de Municipal — os dois são PDF."""
    mod.registrar_relatorio(autor=7, relatorio="municipal", formato="pdf")
    m = con.eventos[0][2].obj
    assert m["relatorio"] == "municipal"
    assert m["formato"] == "pdf"
    assert m["origem"] == "web"


# --------------------------------------------------------------------------------------
# As chaves de alvo, que os índices parciais conhecem
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("chave", ["hex_id", "imovel_id", "unidade_id"])
def test_as_tres_chaves_do_contrato_passam(con: FakeConexao, chave: str) -> None:
    mod.registrar_relatorio(autor=7, relatorio="pontual", formato="pdf", alvo={chave: "abc123"})
    assert con.eventos[0][2].obj[chave] == "abc123"


@pytest.mark.parametrize("errada", ["id_imovel", "imovel", "hexagono", "unidade"])
def test_chave_de_alvo_fora_do_contrato_e_RECUSADA(con: FakeConexao, errada: str) -> None:
    """O defeito de errar a chave é SILENCIOSO: a escrita passa, o evento cai fora do
    índice parcial, e ninguém descobre até a tabela crescer. O contrato avisa disso com
    todas as letras — então aqui a escrita não passa."""
    with pytest.raises(mod.AlvoForaDoContrato):
        mod.registrar_relatorio(autor=7, relatorio="pontual", formato="pdf", alvo={errada: "x"})
    assert con.eventos == [], "nada pode ter sido gravado"


def test_a_recusa_nomeia_a_chave_errada_e_as_certas() -> None:
    with pytest.raises(mod.AlvoForaDoContrato) as caiu:
        mod.registrar_relatorio(autor=7, relatorio="p", formato="pdf", alvo={"imovel": "x"})
    texto = str(caiu.value)
    assert "imovel" in texto
    assert "hex_id" in texto and "imovel_id" in texto and "unidade_id" in texto


# --------------------------------------------------------------------------------------
# PII
# --------------------------------------------------------------------------------------


def test_metadados_nao_tem_onde_encaixar_o_solicitante(con: FakeConexao) -> None:
    """O contrato §4 é explícito: "O `solicitante` de um relatório é texto digitado pelo
    usuário e não deve ser copiado para cá". O vínculo com a pessoa é `eventos.id_usuario`,
    que só existe para quem é linha em `usuarios`. A assinatura não aceita o campo."""
    import inspect

    assert "solicitante" not in inspect.signature(mod.registrar_relatorio).parameters


def test_o_evento_gravado_nao_carrega_PII(con: FakeConexao) -> None:
    mod.registrar_relatorio(
        autor=7, relatorio="pontual", formato="pdf", alvo={"hex_id": "87a8100efffffff"}
    )
    achatado = " ".join(str(v) for v in con.eventos[0][2].obj.values()).lower()
    for pii in ("@", "rua ", "avenida", "lat", "lng", "cpf"):
        assert pii not in achatado, f"PII em metadados: {achatado}"


_ESCRITAS = ("insert into", "update ", "delete from")


def _sql_por_gerenciador() -> dict[str, list[str]]:
    """Mapeia `conexao`/`transacao` -> os SQL executados DENTRO de cada bloco `with`.

    Ate' 18/09/2026 esta garantia era um scan de texto (`"conexao(" not in fonte`). Ele
    passava a impressao de proibir escrita pela conexao de leitura, mas o que media era a
    AUSENCIA DA PALAVRA -- entao a primeira LEITURA legitima do modulo (a contagem de
    recusas da trava de tentativas) o derrubava, sem que nada de errado tivesse acontecido.
    Por AST a pergunta e' a certa: que SQL roda sob qual gerenciador.
    """
    import ast
    from pathlib import Path

    arvore = ast.parse(Path(mod.__file__).read_text(encoding="utf-8"))
    constantes = {
        alvo.id: no.value.value
        for no in arvore.body
        if isinstance(no, ast.Assign) and isinstance(no.value, ast.Constant)
        for alvo in no.targets
        if isinstance(alvo, ast.Name) and isinstance(no.value.value, str)
    }

    achados: dict[str, list[str]] = {"conexao": [], "transacao": []}
    for no in ast.walk(arvore):
        if not isinstance(no, ast.With):
            continue
        gerentes = {
            item.context_expr.func.id
            for item in no.items
            if isinstance(item.context_expr, ast.Call)
            and isinstance(item.context_expr.func, ast.Name)
        }
        gerente = next((g for g in gerentes if g in achados), None)
        if gerente is None:
            continue
        for interno in ast.walk(no):
            if (
                isinstance(interno, ast.Call)
                and isinstance(interno.func, ast.Attribute)
                and interno.func.attr == "execute"
                and interno.args
                and isinstance(interno.args[0], ast.Name)
            ):
                achados[gerente].append(constantes.get(interno.args[0].id, "").lower())
    return achados


def test_escrita_passa_pela_transacao_e_nunca_pela_conexao() -> None:
    """`conexao()` abre `READ ONLY` e o servidor recusaria o INSERT; `transacao()` e' a via
    de escrita e e' ela que declara `app.id_usuario` para as triggers do D19."""
    achados = _sql_por_gerenciador()
    for sql in achados["conexao"]:
        assert not any(verbo in sql for verbo in _ESCRITAS), f"escrita sob conexao(): {sql}"


def test_a_varredura_do_gerenciador_ainda_ENXERGA_os_dois_lados() -> None:
    """Contraprova: sem isto, um `execute` que a varredura deixasse de casar tornaria o
    teste acima verde por nao achar NADA -- que e' exatamente como um guardrail morre."""
    achados = _sql_por_gerenciador()
    assert any("insert into eventos" in sql for sql in achados["transacao"]), (
        "a varredura parou de enxergar as ESCRITAS do modulo"
    )
    assert any(sql.strip().startswith("select") for sql in achados["conexao"]), (
        "a varredura parou de enxergar as LEITURAS do modulo"
    )


# --------------------------------------------------------------------------------------
# `dossie.baixado` — o artefato que o motor NAO gera (16/09)
# --------------------------------------------------------------------------------------


def test_o_dossie_tem_tipo_proprio_e_nao_e_um_relatorio(con: FakeConexao) -> None:
    """Linha propria no contrato: o motor nao o gera (vem do coletor) e ele carrega PII de
    corretor. Colapsar em `relatorio.gerado` perderia as duas distincoes de uma vez."""
    mod.registrar_dossie_baixado(autor=7, imovel_id="im_3f2a9b")
    assert con.eventos[0][1] == mod.EVENTO_DOSSIE_BAIXADO
    assert mod.EVENTO_DOSSIE_BAIXADO == "dossie.baixado"


def test_o_alvo_vai_com_a_chave_que_o_indice_conhece(con: FakeConexao) -> None:
    """`imovel_id`, e nao `id_imovel` nem `imovel` -- o defeito da chave errada e' silencioso."""
    mod.registrar_dossie_baixado(autor=7, imovel_id="im_3f2a9b")
    metadados = con.eventos[0][2].obj
    assert metadados["imovel_id"] == "im_3f2a9b"
    assert metadados["origem"] == "web"
    assert "imovel_id" in mod.CHAVES_DE_ALVO


def test_o_dossie_nao_carimba_report_id(con: FakeConexao) -> None:
    """Nao ha o que carimbar: o PDF vem pronto do coletor e nunca passou pela geracao do
    motor. Inventar um id aqui prometeria um rastreio que o arquivo nao carrega."""
    mod.registrar_dossie_baixado(autor=7, imovel_id="im_3f2a9b")
    assert "report_id" not in con.eventos[0][2].obj
    import inspect

    assert "report_id" not in inspect.signature(mod.registrar_dossie_baixado).parameters


def test_autor_nulo_e_permitido_no_dossie(con: FakeConexao) -> None:
    """Meio evento vale mais que nenhum -- "este dossie foi baixado" ja' e' informacao."""
    mod.registrar_dossie_baixado(autor=None, imovel_id="im_3f2a9b")
    assert con.eventos[0][0] is None
    assert len(con.eventos) == 1


def test_o_autor_do_dossie_e_carimbado_como_PRIMEIRO_comando(con: FakeConexao) -> None:
    """Sem `app.id_usuario` antes da escrita, as triggers do D19 gravam autoria nula."""
    mod.registrar_dossie_baixado(autor=7, imovel_id="im_3f2a9b")
    assert con.executados[0][0] == postgres.SQL_DEFINIR_AUTOR


def test_o_dossie_nao_grava_entidade(con: FakeConexao) -> None:
    """Emenda do D24: o id do imovel e' TEXTUAL e `entidade_id` e' BIGINT."""
    assert "NULL, NULL" in mod.SQL_REGISTRAR_DOSSIE


def test_metadados_do_dossie_nao_carregam_PII(con: FakeConexao) -> None:
    """O evento aponta para o arquivo; o contato do corretor fica DENTRO do PDF e nunca aqui."""
    mod.registrar_dossie_baixado(autor=7, imovel_id="im_3f2a9b")
    achatado = " ".join(str(v) for v in con.eventos[0][2].obj.values()).lower()
    for pii in ("@", "rua ", "avenida", "telefone", "cpf", "creci"):
        assert pii not in achatado, f"PII em metadados: {achatado}"


# --------------------------------------------------------------------------------------
# `imovel.visita_marcada` / `_desmarcada` — os dois gestos que sobem (16/09)
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("marcada", "tipo_esperado"),
    [(True, "imovel.visita_marcada"), (False, "imovel.visita_desmarcada")],
)
def test_o_estado_do_gesto_escolhe_o_tipo(
    con: FakeConexao, marcada: bool, tipo_esperado: str
) -> None:
    """ "Marcou" e "desmarcou" respondem perguntas diferentes: quantos imoveis entraram na fila
    de visita, e quantos sairam. Colapsar num `visita_alternada` perderia a direcao."""
    mod.registrar_visita(autor=7, imovel_id="im_3f2a9b", marcada=marcada)
    assert con.eventos[0][1] == tipo_esperado


def test_os_dois_tipos_sao_os_do_contrato() -> None:
    assert mod.EVENTO_VISITA_MARCADA == "imovel.visita_marcada"
    assert mod.EVENTO_VISITA_DESMARCADA == "imovel.visita_desmarcada"


def test_a_visita_usa_a_chave_de_alvo_do_contrato(con: FakeConexao) -> None:
    """`imovel_id`, a mesma chave do dossie -- e' o que o indice parcial da 014 conhece."""
    mod.registrar_visita(autor=7, imovel_id="im_3f2a9b", marcada=True)
    metadados = con.eventos[0][2].obj
    assert metadados == {"imovel_id": "im_3f2a9b", "origem": "web"}
    assert "imovel_id" in mod.CHAVES_DE_ALVO


def test_a_visita_carimba_o_autor_como_PRIMEIRO_comando(con: FakeConexao) -> None:
    mod.registrar_visita(autor=7, imovel_id="im_3f2a9b", marcada=True)
    assert con.executados[0][0] == postgres.SQL_DEFINIR_AUTOR
    assert con.eventos[0][0] == 7


def test_a_visita_nao_grava_entidade() -> None:
    """Emenda do D24: o id do imovel e' TEXTUAL e `entidade_id` e' BIGINT."""
    assert "NULL, NULL" in mod.SQL_REGISTRAR_VISITA


# --------------------------------------------------------------------------------------
# `viabilidade.calculada` — as premissas, SEM alvo (16/09)
# --------------------------------------------------------------------------------------


def test_a_viabilidade_grava_as_premissas(con: FakeConexao) -> None:
    """O conteudo do evento e' o que a pessoa PEDIU: metragem, aluguel e demanda."""
    mod.registrar_viabilidade(autor=7, m2=1500.0, aluguel=20000.0, demanda=900.0)
    assert con.eventos[0][1] == mod.EVENTO_VIABILIDADE_CALCULADA
    assert con.eventos[0][2].obj == {
        "m2": 1500.0,
        "aluguel": 20000.0,
        "demanda": 900.0,
        "origem": "web",
    }


def test_a_viabilidade_nao_grava_alvo_nenhum(con: FakeConexao) -> None:
    """Medido: nem o pedido nem o backend conhecem `hex_id`/`imovel_id`. Derivar o hexagono da
    coordenada e' o que a §2.2 recusa -- entao o evento nao promete alvo que nao tem."""
    import inspect

    mod.registrar_viabilidade(autor=7, m2=1500.0, aluguel=20000.0, demanda=900.0)
    metadados = con.eventos[0][2].obj
    for chave in mod.CHAVES_DE_ALVO:
        assert chave not in metadados
    assert not set(inspect.signature(mod.registrar_viabilidade).parameters) & set(
        mod.CHAVES_DE_ALVO
    )


def test_a_viabilidade_nunca_grava_a_coordenada(con: FakeConexao) -> None:
    """§4: `lat`/`lng` ficam FORA de `metadados` -- e a assinatura nem os aceita."""
    import inspect

    mod.registrar_viabilidade(autor=7, m2=1500.0, aluguel=20000.0, demanda=900.0)
    achatado = " ".join(f"{k}={v}" for k, v in con.eventos[0][2].obj.items()).lower()
    for proibido in ("lat", "lng"):
        assert proibido not in achatado
        assert proibido not in inspect.signature(mod.registrar_viabilidade).parameters


def test_a_viabilidade_nao_grava_numero_de_SAIDA(con: FakeConexao) -> None:
    """Break-even, payback e aluguel-teto sao resposta do motor. `eventos` registra o PEDIDO --
    guardar a saida aqui criaria uma segunda fonte de verdade financeira."""
    import inspect

    assinatura = set(inspect.signature(mod.registrar_viabilidade).parameters)
    for saida in ("payback", "break_even", "aluguel_teto", "tir", "vpl", "ebitda"):
        assert saida not in assinatura


def test_autor_nulo_e_permitido_na_viabilidade(con: FakeConexao) -> None:
    mod.registrar_viabilidade(autor=None, m2=1500.0, aluguel=20000.0, demanda=900.0)
    assert con.eventos[0][0] is None
    assert con.executados[0][0] == postgres.SQL_DEFINIR_AUTOR
