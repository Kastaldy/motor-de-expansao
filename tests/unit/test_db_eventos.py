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
    assert mod.registrar_relatorio(
        autor=7, relatorio="pontual", formato="pdf", report_id=meu
    ) == meu
    assert con.eventos[0][2].obj["report_id"] == meu


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
    mod.registrar_relatorio(
        autor=7, relatorio="pontual", formato="pdf", alvo={chave: "abc123"}
    )
    assert con.eventos[0][2].obj[chave] == "abc123"


@pytest.mark.parametrize("errada", ["id_imovel", "imovel", "hexagono", "unidade"])
def test_chave_de_alvo_fora_do_contrato_e_RECUSADA(con: FakeConexao, errada: str) -> None:
    """O defeito de errar a chave é SILENCIOSO: a escrita passa, o evento cai fora do
    índice parcial, e ninguém descobre até a tabela crescer. O contrato avisa disso com
    todas as letras — então aqui a escrita não passa."""
    with pytest.raises(mod.AlvoForaDoContrato):
        mod.registrar_relatorio(
            autor=7, relatorio="pontual", formato="pdf", alvo={errada: "x"}
        )
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


def test_escrita_passa_pela_transacao_e_nunca_pela_conexao() -> None:
    """`conexao()` abre `READ ONLY` e o servidor recusaria o INSERT; `transacao()` é a via
    de escrita e é ela que declara `app.id_usuario` para as triggers do D19."""
    from pathlib import Path

    fonte = Path(mod.__file__).read_text(encoding="utf-8")
    assert "from .postgres import transacao" in fonte
    assert "conexao(" not in fonte


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
    """"Marcou" e "desmarcou" respondem perguntas diferentes: quantos imoveis entraram na fila
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
