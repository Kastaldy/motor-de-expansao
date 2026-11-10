"""Anotações nos pinos de concorrentes (migration 023): âncora, privacidade do autor e rotas.

O banco (triggers, CHECK, histórico) é provado contra Postgres de verdade em
`tests/integration/test_login_ponta_a_ponta.py`, seção 3. Aqui fica o que só existe na camada do
piloto — e a regra mais cara de errar: **o nome do autor não sai do servidor para quem não é
Growth.** Esconder no front não bastaria; o nome apareceria no F12 → Rede.

Chama as funções de rota DIRETO (sem TestClient), no padrão de `test_piloto_web_admin_usuarios.py`.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi import HTTPException

_REPO = Path(__file__).resolve().parents[2]
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import app as pilot_app  # noqa: E402
import observacoes  # noqa: E402

from motor_expansao.db import observacoes as db_obs  # noqa: E402
from motor_expansao.db.observacoes import (  # noqa: E402
    CamposObservacao,
    Observacao,
    RegistroHistorico,
)

T0 = datetime(2026, 10, 21, 10, 0, tzinfo=UTC)
CARLA, DIEGO, BRUNO, MARINA = 11, 12, 13, 14
NOMES = {
    CARLA: ("Carla Mendes", "expansao"),
    DIEGO: ("Diego Ramos", "expansao"),
    BRUNO: ("Bruno Alves", "lideres"),
    MARINA: ("Marina Souza", "growth"),
}


def _obs(
    id_obs: int,
    autor: int,
    dias: int,
    *,
    versao: int = 1,
    apagada_por: int | None = None,
    comentario: str = "visita",
) -> Observacao:
    return Observacao(
        id_observacao=id_obs,
        id_usuario_autor=autor,
        campos=CamposObservacao(metragem_m2=1200, nota_conservacao=4, comentario=comentario),
        versao=versao,
        criada_em=T0 + timedelta(days=dias),
        atualizada_em=T0 + timedelta(days=dias, hours=versao - 1),
        apagada_em=T0 + timedelta(days=dias + 1) if apagada_por else None,
        apagada_por=apagada_por,
    )


# A Smart Fit do protótipo: Diego anota, Diego anota de novo (com telefone, e a Marina modera),
# Carla anota e edita, Bruno anota.
CENARIO = [
    _obs(1, DIEGO, 0),
    _obs(2, DIEGO, 1, apagada_por=MARINA, comentario="Contato do gerente: João, (11) 9xxxx"),
    _obs(3, CARLA, 7, versao=2),
    _obs(4, BRUNO, 12),
]
HISTORICO = [
    RegistroHistorico(
        3,
        "criada",
        1,
        CamposObservacao(metragem_m2=1300, vagas=20, comentario="antes"),
        T0 + timedelta(days=7),
        CARLA,
    ),
    RegistroHistorico(
        3,
        "editada",
        2,
        CamposObservacao(metragem_m2=1450, vagas=25, comentario="depois"),
        T0 + timedelta(days=9),
        CARLA,
    ),
]


# ---------------------------------------------------------------------------------------
# A âncora da academia
# ---------------------------------------------------------------------------------------


def test_chave_e_estavel_a_jitter_de_coordenada_e_ao_marcador_em_breve() -> None:
    base = observacoes.chave_concorrente("smart_fit", "Smart Fit Centro", -23.5505, -46.6333)
    # ~30 m de re-geocodificação: mesma célula res-5, mesma chave.
    assert observacoes.chave_concorrente("smart_fit", "Smart Fit Centro", -23.5507, -46.6335) == base
    # O marcador de pipeline cai quando a unidade inaugura (DEC-063): não pode trocar a chave.
    assert observacoes.chave_concorrente("smart_fit", "Smart Fit Centro (Em breve)", -23.5505, -46.6333) == base
    assert observacoes.chave_concorrente("bluefit", "Smart Fit Centro", -23.5505, -46.6333) != base
    assert len(base or "") == 40


@pytest.mark.parametrize("lat,lng", [(None, -46.6), ("x", -46.6), (float("nan"), -46.6), (95.0, -46.6)])
def test_chave_recusa_coordenada_invalida(lat: Any, lng: Any) -> None:
    assert observacoes.chave_concorrente("smart_fit", "Centro", lat, lng) is None


# ---------------------------------------------------------------------------------------
# Os campos (as mesmas regras dos CHECK da 023, com recado legível)
# ---------------------------------------------------------------------------------------


def test_campos_normalizados() -> None:
    campos = observacoes.normalizar_campos(
        metragem_m2=1450,
        equipamentos="  Technogym  ",
        vagas="20",
        comodidades=" Spinning, pilates ",
        nota_conservacao=4,
        nota_fachada=4.0,
        nota_atendimento=None,
        alunos_estimados=2400,
        comentario="",
    )
    assert campos == CamposObservacao(
        metragem_m2=1450,
        equipamentos="Technogym",
        vagas=20,
        comodidades="Spinning, pilates",
        nota_conservacao=4,
        nota_fachada=4,
        nota_atendimento=None,
        alunos_estimados=2400,
        comentario=None,
    )
    # Uma nota sozinha já é anotação; zero vagas é dado (não há estacionamento), não vazio.
    assert observacoes.normalizar_campos(nota_atendimento=3).nota_atendimento == 3
    assert observacoes.normalizar_campos(vagas=0).vagas == 0


@pytest.mark.parametrize(
    "campos",
    [
        {},
        {"metragem_m2": "", "equipamentos": "  ", "comentario": ""},
        {"metragem_m2": 49},
        {"metragem_m2": 20_001},
        {"metragem_m2": "muito"},
        {"vagas": -1},
        {"vagas": 5_001},
        {"nota_conservacao": 0},
        {"nota_fachada": 11},
        {"nota_conservacao": 6},  # estrelas: 1 a 5 (prévia de 10/11)
        {"nota_atendimento": "ótimo"},
        {"alunos_estimados": 0},
        {"alunos_estimados": 50_001},
        {"equipamentos": "x" * 1001},
        {"comodidades": "x" * 1001},
        {"comentario": "x" * 2001},
    ],
)
def test_campos_invalidos(campos: dict[str, Any]) -> None:
    with pytest.raises(observacoes.CampoInvalido):
        observacoes.normalizar_campos(**campos)


# Número é número INTEIRO e texto é TEXTO (prévia de 10/11: a tela aceitava letra na metragem e
# nas vagas, e o servidor convertia em silêncio o que não devia).


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("vagas", True),  # bool é int no Python: virava 1 vaga
        ("vagas", "1e3"),  # notação científica: virava 1.000
        ("metragem_m2", "1.5"),  # decimal em texto: virava 2
        ("metragem_m2", "12a"),
        ("metragem_m2", 1450.4),  # número quebrado: era arredondado sem aviso
        ("nota_fachada", 7.5),
        ("alunos_estimados", "inf"),  # derrubava a rota com 500 (OverflowError no int())
        ("alunos_estimados", float("inf")),
        ("alunos_estimados", float("nan")),
    ],
)
def test_numero_que_nao_e_inteiro_e_recusado_com_recado(campo: str, valor: Any) -> None:
    with pytest.raises(observacoes.CampoInvalido, match="precisa ser um número inteiro"):
        observacoes.normalizar_campos(**{campo: valor})


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("comentario", 12),
        ("equipamentos", {"marca": "Technogym"}),
        ("comodidades", ["spinning"]),
        ("comentario", True),
    ],
)
def test_texto_que_nao_e_texto_e_recusado_com_recado(campo: str, valor: Any) -> None:
    with pytest.raises(observacoes.CampoInvalido, match="precisa ser texto"):
        observacoes.normalizar_campos(**{campo: valor})


def test_inteiro_aceita_int_float_inteiro_e_texto_so_de_digitos() -> None:
    campos = observacoes.normalizar_campos(
        metragem_m2=" 1450 ", vagas=0, nota_fachada=4.0, alunos_estimados="2200"
    )
    assert (campos.metragem_m2, campos.vagas, campos.nota_fachada, campos.alunos_estimados) == (
        1450,
        0,
        4,
        2200,
    )


# ---------------------------------------------------------------------------------------
# O que cada pessoa enxerga
# ---------------------------------------------------------------------------------------


def test_pessoa_n_e_por_ordem_da_primeira_anotacao_e_conta_as_apagadas() -> None:
    rotulos = observacoes.rotulos_por_autor(list(reversed(CENARIO)))
    assert rotulos == {DIEGO: "Pessoa 1", CARLA: "Pessoa 2", BRUNO: "Pessoa 3"}


def test_quem_nao_e_growth_nao_recebe_nome_historico_nem_apagada() -> None:
    resposta = observacoes.montar_resposta(
        CENARIO,
        id_viewer=CARLA,
        ver_autor=False,
        pode_anotar=True,
        # Mesmo que o chamador entregue nome e histórico por engano, nada disso sai.
        historico=HISTORICO,
        nomes=NOMES,
    )
    texto = json.dumps(resposta, ensure_ascii=False)
    for nome, _perfil in NOMES.values():
        assert nome not in texto
    assert "(11) 9xxxx" not in texto  # a apagada some inteira
    assert {"autor_nome", "historico", "apagada"}.isdisjoint(
        chave for item in resposta["observacoes"] for chave in item
    )
    itens = {i["id"]: i for i in resposta["observacoes"]}
    assert sorted(itens) == [1, 3, 4]
    assert itens[1]["autor_rotulo"] == "Pessoa 1"
    assert itens[3]["autor_rotulo"] == "Pessoa 2" and itens[3]["minha"] is True
    assert itens[3]["pode_editar"] and itens[3]["pode_apagar"] and itens[3]["editada"]
    # Na anotação dos outros: nem editar nem apagar.
    assert not itens[4]["pode_editar"] and not itens[4]["pode_apagar"]
    assert resposta["pode_moderar"] is False


def test_growth_ve_nome_historico_apagada_e_modera() -> None:
    resposta = observacoes.montar_resposta(
        CENARIO,
        id_viewer=MARINA,
        ver_autor=True,
        pode_anotar=True,
        historico=HISTORICO,
        nomes=NOMES,
    )
    itens = {i["id"]: i for i in resposta["observacoes"]}
    assert sorted(itens) == [1, 2, 3, 4]
    assert itens[1]["autor_nome"] == "Diego Ramos"
    assert itens[2]["apagada"]["por"] == "Marina Souza"
    assert itens[2]["apagada"]["moderacao"] is True
    assert not itens[2]["pode_apagar"]  # já apagada
    # Growth apaga a dos outros (moderação), mas não EDITA o texto de ninguém.
    assert itens[4]["pode_apagar"] and not itens[4]["pode_editar"]
    edicao = itens[3]["historico"][-1]
    assert edicao["acao"] == "editada" and edicao["por"] == "Carla Mendes"
    assert edicao["versao_anterior"]["metragem_m2"] == 1300
    # A versão anterior carrega TODOS os campos, não só os três primeiros.
    assert edicao["versao_anterior"]["vagas"] == 20
    assert set(edicao["versao_anterior"]) == set(observacoes.campos_json(CamposObservacao()))
    assert resposta["pode_moderar"] is True


def test_todos_os_campos_chegam_ao_payload() -> None:
    """Esquecer um campo na lista do payload é o defeito da DEC-038: coluna existe, tela vazia."""
    resposta = observacoes.montar_resposta(
        CENARIO, id_viewer=CARLA, ver_autor=False, pode_anotar=True
    )
    item = resposta["observacoes"][0]
    for campo in observacoes.campos_json(CamposObservacao()):
        assert campo in item, campo
    assert item["nota_conservacao"] == 4


def test_ids_para_nomes_cobre_autor_moderador_e_editor() -> None:
    assert observacoes.ids_para_nomes(CENARIO, HISTORICO) == {DIEGO, CARLA, BRUNO, MARINA}


# ---------------------------------------------------------------------------------------
# As rotas
# ---------------------------------------------------------------------------------------

CHAVE = "c" * 40
ACADEMIA = {"rede": "smart_fit", "nome": "Smart Fit Jardim América", "lat": -23.55, "lng": -46.63}


class _Eu:
    def __init__(self, id_usuario: int, *capacidades: str) -> None:
        self.id_usuario = id_usuario
        self._cap = set(capacidades)

    def pode(self, chave: str) -> bool:
        return chave in self._cap


EXPANSAO = _Eu(CARLA, "concorrente.anotar")
GROWTH = _Eu(MARINA, "concorrente.anotar", "concorrente.ver_autor")


@pytest.fixture
def banco(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Índice de pinos e módulo de dados dublados; registra o que a rota pediu ao banco."""
    chamadas: dict[str, Any] = {"nomes": 0, "historico": 0}
    monkeypatch.setattr(pilot_app, "_indice_de_concorrentes", lambda: {CHAVE: ACADEMIA})
    monkeypatch.setattr(db_obs, "listar", lambda **_k: list(CENARIO))

    def _historico(_ids: Any) -> list[RegistroHistorico]:
        chamadas["historico"] += 1
        return list(HISTORICO)

    def _nomes(_ids: Any) -> dict[int, tuple[str, str]]:
        chamadas["nomes"] += 1
        return dict(NOMES)

    monkeypatch.setattr(db_obs, "historico", _historico)
    monkeypatch.setattr(db_obs, "nomes_dos_autores", _nomes)
    return chamadas


def _como(monkeypatch: pytest.MonkeyPatch, eu: _Eu) -> None:
    monkeypatch.setattr(pilot_app, "_identidade_para_anotar", lambda _u: eu)


def test_rota_nem_consulta_nome_para_quem_nao_e_growth(
    banco: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    _como(monkeypatch, EXPANSAO)
    resposta = pilot_app.concorrente_observacoes(chave=CHAVE, remote_user="carla")
    assert banco == {"nomes": 0, "historico": 0}
    assert "Carla Mendes" not in json.dumps(resposta, ensure_ascii=False)
    assert resposta["academia"] == {"rede": "smart_fit", "nome": "Smart Fit Jardim América"}


def test_rota_de_growth_traz_os_nomes(banco: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    _como(monkeypatch, GROWTH)
    resposta = pilot_app.concorrente_observacoes(chave=CHAVE, remote_user="marina")
    assert banco == {"nomes": 1, "historico": 1}
    assert {i["autor_nome"] for i in resposta["observacoes"]} >= {"Diego Ramos", "Carla Mendes"}


def test_chave_fora_da_base_e_404_antes_de_tocar_o_banco(
    banco: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    _como(monkeypatch, EXPANSAO)
    with pytest.raises(HTTPException) as erro:
        pilot_app.concorrente_observacoes(chave="nao-existe", remote_user="carla")
    assert erro.value.status_code == 404


def test_criar_grava_a_academia_do_indice_e_nao_a_do_corpo(
    banco: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    _como(monkeypatch, EXPANSAO)
    gravado: dict[str, Any] = {}
    monkeypatch.setattr(db_obs, "criar", lambda **k: gravado.update(k) or 99)
    corpo = pilot_app.ObservacaoIn(
        chave=CHAVE, metragem_m2=1450, nota_fachada=5, vagas=30, comentario=" ampliaram "
    )
    pilot_app.concorrente_observacoes_criar(body=corpo, remote_user="carla")
    assert gravado["rede"] == "smart_fit" and gravado["lat"] == -23.55
    assert gravado["autor"] == CARLA and gravado["pais"] == pilot_app.PERFIL.pais
    c = gravado["campos"]
    assert (c.metragem_m2, c.nota_fachada, c.vagas, c.comentario) == (1450, 5, 30, "ampliaram")


def test_nota_fora_de_1_a_5_e_422(banco: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    _como(monkeypatch, EXPANSAO)
    with pytest.raises(HTTPException) as erro:
        pilot_app.concorrente_observacoes_criar(
            body=pilot_app.ObservacaoIn(chave=CHAVE, nota_conservacao=6), remote_user="carla"
        )
    assert erro.value.status_code == 422
    assert "conservação" in erro.value.detail


def test_criar_vazio_e_422(banco: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    _como(monkeypatch, EXPANSAO)
    with pytest.raises(HTTPException) as erro:
        pilot_app.concorrente_observacoes_criar(
            body=pilot_app.ObservacaoIn(chave=CHAVE), remote_user="carla"
        )
    assert erro.value.status_code == 422


@pytest.mark.parametrize(
    "corpo",
    [
        {"vagas": True},
        {"vagas": "1e3"},
        {"alunos_estimados": "inf"},
        {"metragem_m2": "12a"},
        {"comentario": 12},
    ],
)
def test_rota_recusa_tipo_errado_com_422_em_portugues(
    banco: dict[str, Any], monkeypatch: pytest.MonkeyPatch, corpo: dict[str, Any]
) -> None:
    """O modelo HTTP não pode converter antes da regra: com `float`, o Pydantic transformava
    "1e3" em 1000, True em 1 e "inf" em infinito (500 no `int()`); texto errado saía como 422
    em inglês, sem o rótulo da tela."""
    _como(monkeypatch, EXPANSAO)
    with pytest.raises(HTTPException) as erro:
        pilot_app.concorrente_observacoes_criar(
            body=pilot_app.ObservacaoIn.model_validate({"chave": CHAVE, **corpo}),
            remote_user="carla",
        )
    assert erro.value.status_code == 422
    assert "precisa ser" in erro.value.detail


@pytest.mark.parametrize(
    "excecao,status",
    [
        (db_obs.NaoEhOAutor("x"), 403),
        (db_obs.ObservacaoDesconhecida("x"), 404),
        (db_obs.ObservacaoApagada("x"), 409),
        (db_obs.ConflitoDeVersao("x"), 409),
    ],
)
def test_erros_do_banco_viram_status_certo(
    banco: dict[str, Any], monkeypatch: pytest.MonkeyPatch, excecao: Exception, status: int
) -> None:
    _como(monkeypatch, EXPANSAO)

    def _falha(*_a: Any, **_k: Any) -> None:
        raise excecao

    monkeypatch.setattr(db_obs, "editar", _falha)
    corpo = pilot_app.ObservacaoEdicaoIn(chave=CHAVE, versao=1, comentario="nova")
    with pytest.raises(HTTPException) as erro:
        pilot_app.concorrente_observacoes_editar(id_observacao=3, body=corpo, remote_user="carla")
    assert erro.value.status_code == status


def test_apagar_passa_moderacao_so_para_growth(
    banco: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    pedidos: list[bool] = []
    monkeypatch.setattr(db_obs, "apagar", lambda _id, **k: pedidos.append(k["pode_moderar"]) or False)
    for eu in (EXPANSAO, GROWTH):
        _como(monkeypatch, eu)
        pilot_app.concorrente_observacoes_apagar(id_observacao=4, chave=CHAVE, remote_user="x")
    assert pedidos == [False, True]


def test_contagem_degrada_para_vazio_com_o_banco_fora(monkeypatch: pytest.MonkeyPatch) -> None:
    _como(monkeypatch, EXPANSAO)

    def _fora(**_k: Any) -> dict[str, int]:
        from motor_expansao.db import BancoIndisponivel

        raise BancoIndisponivel("fora")

    monkeypatch.setattr(db_obs, "contar", _fora)
    corpo = pilot_app.ContagemObservacoesIn(chaves=[CHAVE])
    assert pilot_app.concorrente_observacoes_contagem(body=corpo, remote_user="carla") == {}


def test_gate_uma_capacidade_para_ler_e_escrever_e_ela_e_sensivel() -> None:
    acesso = pilot_app.acesso
    for caminho, metodo in (
        ("/api/concorrente/observacoes", "GET"),
        ("/api/concorrente/observacoes", "POST"),
        ("/api/concorrente/observacoes/7", "PATCH"),
        ("/api/concorrente/observacoes/7", "DELETE"),
        ("/api/concorrente/observacoes/contagem", "POST"),
    ):
        assert acesso.capacidade_necessaria(caminho, metodo) == "concorrente.anotar"
    assert "concorrente.anotar" in acesso.CAPACIDADES_SENSIVEIS


def test_pino_carrega_a_chave_da_academia() -> None:
    """O front só sabe pedir anotação pela `chave` — se ela não sair no pino, o painel não abre."""
    import inspect

    fonte = inspect.getsource(pilot_app._montar_pins)
    assert fonte.count('"chave": observacoes.chave_concorrente(') == 2  # cadastro e agregador
