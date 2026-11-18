"""Recorte do MASTER franqueado na Visao Executiva (perfil `master`, 17/11/2026).

O master entra na aba `executiva` e enxerga SO as unidades dele -- as que o cadastro
(`master_franquia`) atribui ao(s) master(s) vinculado(s) ao usuario (`usuario_masters`). O que
estes testes travam, todos do lado do SERVIDOR (a tela nunca recebe o dado alheio para depois
esconde-lo):

* carteira, filtros e inteligencia saem do recorte; os AGREGADOS da rede (MEDIA da linha da
  rede inteira, `totais.rede`, ranking, curva de rampa) ficam, porque sao a regua de
  comparacao -- o TOTAL da rede inteira nao (sem a chave `total` na linha da rede);
* unidade de outro master e' 404 na ficha, nos setores e na inteligencia -- 404, e nao 403,
  para nao confirmar que ela existe;
* pares de praca e nomes de Ultra vizinhas nao vazam unidade de fora;
* exports, PDFs, escrita e as rotas fora da allowlist sao 403 para o master (2a camada);
* fail-closed: master sem vinculo ve carteira VAZIA e banco fora e' 503, nunca a rede;
* quem tem `rede.ver`, e o modo sem banco, nao mudam em nada.

Chama as rotas DIRETO (sem TestClient), como o resto da suite do piloto, com o RBAC do banco
substituido por dubles (`rbac.identidade`, `rbac.masters_do_usuario`, `acesso.banco_no_comando`).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from fastapi import HTTPException

_REPO = Path(__file__).resolve().parents[2]
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import acesso  # noqa: E402
import app as pilot  # noqa: E402

from motor_expansao import db  # noqa: E402
from motor_expansao.db import rbac  # noqa: E402
from tests.unit.test_piloto_web_rede import rede  # noqa: E402,F401  (fixture)

MES = "2026-07"
MASTER = "dalmo_ribeiro"
REDE_INTEIRA = "ana"
SEM_PERFIL_DA_REDE = "bruno"
DETALHE_403 = "Seu usuário não tem acesso a esta área do piloto. Fale com o Felipe."
DETALHE_404 = "Unidade não encontrada na sua carteira."
DETALHE_503 = "Acesso indisponível no momento. Tente novamente em instantes."


def _identidade(login: str, permissoes: set[str], id_usuario: int) -> rbac.Identidade:
    return rbac.Identidade(
        id_usuario=id_usuario,
        login=login,
        perfil="t",
        permissoes=frozenset(permissoes),
        paises=frozenset({pilot.PERFIL.pais}),
    )


class _Banco:
    """Duble do RBAC: quem e' quem, e os masters de cada usuario."""

    def __init__(self) -> None:
        self.masters: dict[int, frozenset[str]] = {42: frozenset({"Dalmo Ribeiro"})}
        self.identidade_cai = False
        self.masters_cai = False
        self.consultas_de_masters = 0

    def identidade(self, remote_user: object) -> rbac.Identidade | None:
        if self.identidade_cai:
            raise db.BancoIndisponivel("banco fora (duble)")
        usuarios = {
            MASTER: _identidade(MASTER, {"rede.ver_propria"}, 42),
            REDE_INTEIRA: _identidade(REDE_INTEIRA, {"rede.ver", "rede.cadastro_editar"}, 7),
            SEM_PERFIL_DA_REDE: _identidade(SEM_PERFIL_DA_REDE, {"territorio.explorar"}, 9),
        }
        return usuarios.get(str(remote_user)) if isinstance(remote_user, str) else None

    def masters_do_usuario(self, id_usuario: int) -> frozenset[str]:
        self.consultas_de_masters += 1
        if self.masters_cai:
            raise db.BancoSemProvaDeQueda("pool saturado (duble)")
        return self.masters.get(id_usuario, frozenset())


@pytest.fixture
def banco(rede: Path, monkeypatch: pytest.MonkeyPatch) -> _Banco:  # noqa: F811
    """Banco NO COMANDO, com o RBAC substituido pelo duble."""
    duble = _Banco()
    monkeypatch.setattr(acesso, "banco_no_comando", lambda: True)
    monkeypatch.setattr(rbac, "identidade", duble.identidade)
    # `raising=False`: a funcao nasce no `rbac.py` na mesma entrega (frente do banco).
    monkeypatch.setattr(rbac, "masters_do_usuario", duble.masters_do_usuario, raising=False)
    return duble


def _status(chamada: Any) -> tuple[int, Any]:
    with pytest.raises(HTTPException) as erro:
        chamada()
    return erro.value.status_code, erro.value.detail


# ---------------------------------------------------------------------------
# Carteira
# ---------------------------------------------------------------------------


def test_carteira_do_master_so_traz_as_unidades_dele(banco: _Banco) -> None:
    payload = pilot.rede_carteira(mes=MES, remote_user=MASTER)
    assert {u["id"] for u in payload["unidades"]} == {"icarai-rj"}
    assert payload["totais"]["no_recorte"] == 1
    # Os KPIs e as series sao do RECORTE: o faturamento do topo e' o da unidade dele.
    icarai = payload["unidades"][0]
    assert payload["kpis"]["faturamento"]["atual"] == icarai["metricas"]["faturamento"]["atual"]
    # Os agregados da REDE ficam: e' contra eles que o master se compara.
    assert payload["totais"]["rede"] == 5
    assert payload["rede_inteira"]["n_unidades"] == 5
    assert payload["rede_inteira"]["media"]["faturamento"]["atual"] is not None
    # E nenhum nome de outra unidade atravessa no payload.
    texto = json.dumps(payload, ensure_ascii=False)
    for outro in ("BOTAFOGO", "BANGU", "AUGUSTA", "BERRINI", "Fernando Nero", "MARISE"):
        assert outro not in texto, outro


def _numeros(valor: Any) -> list[float]:
    """Todo número do payload, em qualquer profundidade (bool fica de fora)."""
    if isinstance(valor, bool):
        return []
    if isinstance(valor, (int, float)):
        return [float(valor)]
    if isinstance(valor, dict):
        return [n for v in valor.values() for n in _numeros(v)]
    if isinstance(valor, (list, tuple)):
        return [n for v in valor for n in _numeros(v)]
    return []


def test_linha_da_rede_do_master_so_com_a_media(banco: _Banco) -> None:
    """Felipe, 17/11/2026: o TOTAL da rede inteira vazava ao master pela linha da rede.

    Ele leva SÓ a média por unidade (a régua do "% vs média"), sem a chave `total`; quem tem
    `rede.ver` segue com as duas leituras, idênticas às de antes.
    """
    ana = pilot.rede_carteira(mes=MES, remote_user=REDE_INTEIRA)["rede_inteira"]
    assert set(ana) == {"media", "total", "n_unidades", "n_comparaveis"}
    assert set(ana["total"]) == {"faturamento", "ativos", "churn_pct", "cancelados", "nps"}

    payload = pilot.rede_carteira(mes=MES, remote_user=MASTER)
    linha = payload["rede_inteira"]
    assert "total" not in linha
    assert set(linha) == {"media", "n_unidades", "n_comparaveis"}
    # A média é a MESMA da rede (régua fixa, não a do recorte), e as contagens ficam.
    assert linha["media"] == ana["media"]
    assert linha["n_unidades"] == ana["n_unidades"] and linha["n_comparaveis"] == ana["n_comparaveis"]

    # E o faturamento total da rede não reaparece em nenhum outro canto do payload.
    total_fat = ana["total"]["faturamento"]
    alvos = {float(v) for v in (total_fat["atual"], total_fat["m1"]) if v is not None}
    assert alvos, "sem total na rede o teste não provaria nada"
    assert not alvos & set(_numeros(payload))


def test_master_de_outro_na_query_da_carteira_vazia(banco: _Banco) -> None:
    """`?master=` de OUTRO master estreita dentro do recorte: vazio, nunca as unidades dele."""
    payload = pilot.rede_carteira(mes=MES, master="Fernando Nero", remote_user=MASTER)
    assert payload["unidades"] == []
    assert payload["totais"]["no_recorte"] == 0
    # E a busca por nome de outra unidade tambem nao fura o recorte.
    assert pilot.rede_carteira(mes=MES, busca="botafogo", remote_user=MASTER)["unidades"] == []


def test_nome_do_master_casa_sem_caixa_nem_espaco(banco: _Banco) -> None:
    banco.masters[42] = frozenset({"  dalmo ribeiro "})
    payload = pilot.rede_carteira(mes=MES, remote_user=MASTER)
    assert {u["id"] for u in payload["unidades"]} == {"icarai-rj"}


@pytest.mark.parametrize("vinculo", [frozenset(), frozenset({"Quem Nao Existe"}), frozenset({"  "})])
def test_master_sem_vinculo_ve_carteira_vazia_e_nunca_a_rede(
    banco: _Banco, vinculo: frozenset[str]
) -> None:
    banco.masters[42] = vinculo
    payload = pilot.rede_carteira(mes=MES, remote_user=MASTER)
    assert payload["unidades"] == []
    assert payload["totais"]["no_recorte"] == 0
    assert payload["kpis"]["faturamento"]["atual"] is None
    filtros = pilot.rede_filtros(mes=MES, remote_user=MASTER)
    assert filtros["masters"] == [] and filtros["consultores"] == [] and filtros["ufs"] == []
    assert _status(lambda: pilot.rede_unidade("icarai-rj", mes=MES, remote_user=MASTER)) == (
        404,
        DETALHE_404,
    )


def test_nota_das_unidades_sem_par_nao_cita_nome_para_o_master(
    banco: _Banco, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A planilha do Financeiro traz unidades sem par na Growth, por NOME: so' quem ve a rede."""
    linhas = [
        {
            "cod_unidade": cod, "unidade_planilha": nome, "unidade_ux": nome,
            "tem_depara": True, "competencia": mes, "faturamento": 250_000.0,
            "vendas_ux": 200_000.0, "gympass": 50_000.0, "totalpass": 0.0, "tem_saude": 0.0,
        }
        # ICARAI casa com a Growth (a nota so' sai com o Financeiro na serie); a outra nao
        for cod, nome in (("02", "ICARAI - RJ"), ("99", "UNIDADE FANTASMA - SP"))
        for mes in ("2026-06", "2026-07")
    ]
    monkeypatch.setattr(pilot, "_rede_faturamento_financeiro", lambda: pd.DataFrame(linhas))
    pilot.limpar_caches()

    rede_toda = pilot.rede_carteira(mes=MES, remote_user=REDE_INTEIRA)
    assert "UNIDADE FANTASMA - SP" in rede_toda["fonte_faturamento"]["unidades_sem_par"]

    do_master = pilot.rede_carteira(mes=MES, remote_user=MASTER)
    assert do_master["fonte_faturamento"]["unidades_sem_par"] == []
    assert "FANTASMA" not in json.dumps(do_master, ensure_ascii=False)
    ficha = pilot.rede_unidade("icarai-rj", mes=MES, remote_user=MASTER)
    assert ficha["fonte_faturamento"]["unidades_sem_par"] == []
    assert "FANTASMA" not in json.dumps(ficha, ensure_ascii=False)


def test_nota_de_fonte_restrita_nao_cita_unidade_sem_par() -> None:
    """A frase que cita as unidades sem par, direto na funcao: so' sai sem `restrito`."""
    cheio = pd.DataFrame(
        {"unidade_id": ["icarai-rj"], "competencia": ["2026-07"], "origem_faturamento": ["financeiro"]}
    )
    cheio.attrs["financeiro_sem_par"] = ["UNIDADE FANTASMA - SP"]
    recorte = cheio[["unidade_id", "origem_faturamento"]].copy()
    contexto = {"cheio": cheio, "serie_meses": ["2026-07"]}
    assert any("FANTASMA" in n for n in pilot._notas_da_fonte(contexto, recorte))
    assert not any("FANTASMA" in n for n in pilot._notas_da_fonte(contexto, recorte, restrito=True))


# ---------------------------------------------------------------------------
# Filtros
# ---------------------------------------------------------------------------


def test_filtros_do_master_so_com_o_vocabulario_dele(banco: _Banco) -> None:
    filtros = pilot.rede_filtros(mes=MES, remote_user=MASTER)
    assert filtros["masters"] == ["Dalmo Ribeiro"]
    assert filtros["masters_franquia"] == ["Dalmo Ribeiro"]
    assert filtros["consultores"] == ["JAILSON"]
    assert filtros["ufs"] == ["RJ"]
    assert filtros["masters_regiao"] == ["RJ/SP 01"]
    assert filtros["qualidade"]["unidades"] == 1
    assert filtros["cadastro"]["campos_editaveis"] == []
    # As reguas sao da rede e ficam.
    assert filtros["reguas"] == pilot.rede_filtros(mes=MES, remote_user=REDE_INTEIRA)["reguas"]


def test_filtro_por_franqueado_nao_atravessa_o_recorte_do_master(banco: _Banco) -> None:
    """O master so' ve os franqueados das unidades dele, e pedir o de fora da' vazio."""
    from motor_expansao.dashboard import rede_cadastro

    rede_cadastro.atribuir("icarai-rj", {"franqueado": "Dalmo Ribeiro"}, base=pilot.CADASTRO_DIR)
    rede_cadastro.atribuir("botafogo-rj", {"franqueado": "Fernando / Franklin"}, base=pilot.CADASTRO_DIR)
    pilot.limpar_caches()

    assert pilot.rede_filtros(mes=MES, remote_user=MASTER)["franqueados"] == ["Dalmo Ribeiro"]
    assert pilot.rede_filtros(mes=MES, remote_user=REDE_INTEIRA)["franqueados"] == [
        "Dalmo Ribeiro", "Fernando / Franklin",
    ]
    alheio = pilot.rede_carteira(mes=MES, franqueado="Fernando / Franklin", remote_user=MASTER)
    assert alheio["unidades"] == [] and alheio["totais"]["no_recorte"] == 0
    assert "BOTAFOGO" not in json.dumps(alheio, ensure_ascii=False)
    proprio = pilot.rede_carteira(mes=MES, franqueado="Dalmo Ribeiro", remote_user=MASTER)
    assert {u["id"] for u in proprio["unidades"]} == {"icarai-rj"}


# ---------------------------------------------------------------------------
# Ficha, setores e inteligencia da unidade
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "chamada",
    [
        lambda: pilot.rede_unidade("botafogo-rj", mes=MES, remote_user=MASTER),
        lambda: pilot.rede_unidade_setores("botafogo-rj", remote_user=MASTER),
        lambda: pilot.rede_unidade_inteligencia("botafogo-rj", mes=MES, remote_user=MASTER),
        # id que nem existe tem a MESMA resposta: o 404 nao separa "nao existe" de "nao e' seu"
        lambda: pilot.rede_unidade("nao-existe", mes=MES, remote_user=MASTER),
    ],
)
def test_unidade_de_outro_master_e_404(banco: _Banco, chamada: Any) -> None:
    assert _status(chamada) == (404, DETALHE_404)


def test_ficha_da_propria_unidade_sem_campo_editavel(banco: _Banco) -> None:
    ficha = pilot.rede_unidade("icarai-rj", mes=MES, remote_user=MASTER)
    assert ficha["unidade"]["id"] == "icarai-rj"
    assert ficha["cadastro"]["campos_editaveis"] == []
    # O benchmark de coorte (p25/p50/p75) e' agregado: fica.
    assert ficha["coorte"]["metricas"]
    # Quem ve a rede segue com o lapis.
    ana = pilot.rede_unidade("icarai-rj", mes=MES, remote_user=REDE_INTEIRA)
    assert ana["cadastro"]["campos_editaveis"]
    assert json.loads(pilot.rede_unidade_setores("icarai-rj", remote_user=MASTER).body) is not None


def _com_territorio(monkeypatch: pytest.MonkeyPatch) -> None:
    """Praca para todas as unidades, e a vizinha de ICARAI e' a BOTAFOGO (de outro master)."""
    ids = sorted(pilot._rede_ids())
    territorio = {
        uid: {"score_praca": 30.0 + i, "concorrentes_1km": 3, "canibalizacao": uid == "icarai-rj"}
        for i, uid in enumerate(ids)
    }
    territorio["icarai-rj"].update(ultra_mais_proxima_nome="BOTAFOGO - RJ", ultra_mais_proxima_m=800.0)
    monkeypatch.setattr(pilot, "_rede_territorio", lambda: territorio)
    monkeypatch.setattr(
        pilot,
        "_rede_pontos",
        lambda: pd.DataFrame([{"unidade_id": "icarai-rj", "lat": -22.90, "lng": -43.10}]),
    )
    mapa = {
        "lat": -22.90,
        "lng": -43.10,
        "raio_m": 2000,
        "concorrentes": [],
        "logos": {},
        "icone_ultra": None,
        "ultra": [
            {"lat": -22.91, "lng": -43.11, "nome": "BOTAFOGO - RJ", "distancia_m": 800},
            # a propria rede do master, com outra grafia mas no mesmo ponto: o nome fica
            {"lat": -22.9001, "lng": -43.1001, "nome": "Ultra Icarai II", "distancia_m": 60},
        ],
    }
    monkeypatch.setattr(pilot, "_rede_mapa_unidade", lambda _uid: mapa)


def test_inteligencia_da_unidade_sem_pares_nem_nomes_de_fora(
    banco: _Banco, monkeypatch: pytest.MonkeyPatch
) -> None:
    _com_territorio(monkeypatch)

    ana = pilot.rede_unidade_inteligencia("icarai-rj", mes=MES, remote_user=REDE_INTEIRA)
    assert len(ana["quadrante"]["pares"]) > 1, "sem pares na rede o teste nao provaria nada"
    assert ana["territorio"]["ultra_mais_proxima_nome"] == "BOTAFOGO - RJ"

    payload = pilot.rede_unidade_inteligencia("icarai-rj", mes=MES, remote_user=MASTER)
    assert {p["id"] for p in payload["quadrante"]["pares"]} == {"icarai-rj"}
    # O quadrante continua o da REDE: mesmos cortes e mesmo n.
    for chave in ("corte_praca", "corte_desempenho", "n"):
        assert payload["quadrante"][chave] == ana["quadrante"][chave]
    assert payload["territorio"]["ultra_mais_proxima_nome"] == "Outra unidade Ultra"
    assert payload["territorio"]["ultra_mais_proxima_m"] == 800.0  # distancia pode ficar
    nomes = [u["nome"] for u in payload["mapa"]["ultra"]]
    assert nomes == ["Outra unidade Ultra", "Ultra Icarai II"]
    assert "BOTAFOGO" not in json.dumps(payload, ensure_ascii=False)
    # A curva de rampa e' da rede (agregado) e fica.
    assert payload["rampa"]["faturamento"]["curva"] == ana["rampa"]["faturamento"]["curva"]
    # O dado cacheado da rede nao foi mexido: quem ve a rede segue vendo o nome.
    de_novo = pilot.rede_unidade_inteligencia("icarai-rj", mes=MES, remote_user=REDE_INTEIRA)
    assert de_novo["territorio"]["ultra_mais_proxima_nome"] == "BOTAFOGO - RJ"


def test_inteligencia_do_recorte_so_com_as_unidades_dele(
    banco: _Banco, monkeypatch: pytest.MonkeyPatch
) -> None:
    _com_territorio(monkeypatch)
    payload = pilot.rede_inteligencia_recorte(mes=MES, remote_user=MASTER)
    assert payload["retencao"]["no_recorte"] == 1
    assert {p["id"] for p in payload["quadrante"]["pontos"]} <= {"icarai-rj"}
    assert [c["vizinha"] for c in payload["canibalizacao"]] == ["Outra unidade Ultra"]
    assert {c["id"] for c in payload["canibalizacao"]} == {"icarai-rj"}
    assert all(m["unidade_id"] == "icarai-rj" for m in payload["mudancas"])
    assert "BOTAFOGO" not in json.dumps(payload, ensure_ascii=False)

    ana = pilot.rede_inteligencia_recorte(mes=MES, remote_user=REDE_INTEIRA)
    assert [c["vizinha"] for c in ana["canibalizacao"]] == ["BOTAFOGO - RJ"]
    # A movimentacao da concorrencia e' NACIONAL e nao segue o recorte.
    assert payload["movimentacao"] == ana["movimentacao"]


# ---------------------------------------------------------------------------
# Fora da allowlist: 403 para o master (2a camada)
# ---------------------------------------------------------------------------


_FORA_DA_ALLOWLIST = [
    pytest.param(lambda u: pilot.rede_carteira_csv(mes=MES, remote_user=u), id="carteira.csv"),
    pytest.param(lambda u: pilot.rede_carteira_xlsx(mes=MES, remote_user=u), id="carteira.xlsx"),
    pytest.param(lambda u: pilot.rede_carteira_pdf(mes=MES, remote_user=u), id="carteira.pdf"),
    pytest.param(lambda u: pilot.rede_unidade_pdf("icarai-rj", mes=MES, remote_user=u), id="ficha.pdf"),
    pytest.param(
        lambda u: pilot.rede_unidade_concorrencia_pdf("icarai-rj", mes=MES, remote_user=u),
        id="concorrencia.pdf",
    ),
    pytest.param(lambda u: pilot.rede_unidades_sem_rede(remote_user=u), id="unidades-sem-rede"),
    pytest.param(
        lambda u: pilot.rede_unidade_sem_rede("cadastro-u1", remote_user=u), id="unidade-sem-rede"
    ),
    pytest.param(lambda u: pilot.executiva("RJ", mes=MES, remote_user=u), id="executiva-uf"),
    pytest.param(
        lambda u: pilot.rede_cadastro_atribuir(
            "icarai-rj",
            pilot.CadastroIn(versao=1, campos={"master_franquia": "Dalmo Ribeiro"}),
            remote_user=u,
            remote_email=None,
        ),
        id="put-cadastro",
    ),
]


@pytest.mark.parametrize("chamada", _FORA_DA_ALLOWLIST)
def test_fora_da_allowlist_o_master_leva_403(banco: _Banco, chamada: Any) -> None:
    assert _status(lambda: chamada(MASTER)) == (403, DETALHE_403)


def test_cadastro_nao_muda_quando_o_master_tenta_escrever(banco: _Banco) -> None:
    antes = pilot._rede_cadastro().de("botafogo-rj")
    with pytest.raises(HTTPException):
        pilot.rede_cadastro_atribuir(
            "botafogo-rj",
            pilot.CadastroIn(versao=1, campos={"master_franquia": "Dalmo Ribeiro"}),
            remote_user=MASTER,
            remote_email=None,
        )
    pilot.limpar_caches()
    assert pilot._rede_cadastro().de("botafogo-rj") == antes


def test_exports_seguem_para_quem_ve_a_rede(banco: _Banco) -> None:
    """A 2a camada so' nega quem tem o recorte: para os outros perfis, nada muda."""
    assert pilot.rede_carteira_csv(mes=MES, remote_user=REDE_INTEIRA).status_code == 200
    assert pilot.executiva("RJ", mes=MES, remote_user=REDE_INTEIRA)["unidades"]
    assert banco.consultas_de_masters == 0, "quem tem rede.ver nao consulta vinculo de master"


def test_perfil_sem_capacidade_da_rede_leva_403_no_recorte(banco: _Banco) -> None:
    assert _status(lambda: pilot.rede_carteira(mes=MES, remote_user=SEM_PERFIL_DA_REDE)) == (
        403,
        DETALHE_403,
    )
    assert _status(lambda: pilot.rede_carteira(mes=MES, remote_user="desconhecido")) == (
        403,
        DETALHE_403,
    )


# ---------------------------------------------------------------------------
# Fail-closed com o banco fora
# ---------------------------------------------------------------------------


def _chamadas_da_allowlist() -> tuple[Any, ...]:
    return (
        lambda: pilot.rede_carteira(mes=MES, remote_user=MASTER),
        lambda: pilot.rede_filtros(mes=MES, remote_user=MASTER),
        lambda: pilot.rede_unidade("icarai-rj", mes=MES, remote_user=MASTER),
        lambda: pilot.rede_inteligencia_recorte(mes=MES, remote_user=MASTER),
    )


@pytest.mark.parametrize("modo", ["producao", "dev"])
def test_banco_fora_e_503_e_nunca_a_rede(
    banco: _Banco, monkeypatch: pytest.MonkeyPatch, modo: str
) -> None:
    """Queda PROVADA (`BancoIndisponivel`): 503 nas rotas que recortam, em qualquer modo.

    Nelas, devolver `None` entregaria a rede inteira ao master -- tambem em dev.
    """
    monkeypatch.setenv("MOTOR_ACESSO_FAIL_CLOSED", "1" if modo == "producao" else "0")
    banco.identidade_cai = True
    for chamada in _chamadas_da_allowlist():
        assert _status(chamada) == (503, DETALHE_503)


def test_banco_fora_na_2a_camada_fecha_em_producao(
    banco: _Banco, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Producao: sem saber quem pede, o export nao sai (o gate ja' nega `rede.ver`)."""
    monkeypatch.setenv("MOTOR_ACESSO_FAIL_CLOSED", "1")
    banco.identidade_cai = True
    assert _status(lambda: pilot.rede_carteira_csv(mes=MES, remote_user=MASTER)) == (
        503,
        DETALHE_503,
    )


def test_banco_fora_na_2a_camada_segue_o_fail_open_de_dev(
    banco: _Banco, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dev (fail-open): o gate ja' deixa passar com o banco fora, e a rota fora da allowlist
    nao recorta nada -- a 2a camada nao transforma o 200 de antes em 503 para todo perfil."""
    monkeypatch.setenv("MOTOR_ACESSO_FAIL_CLOSED", "0")
    banco.identidade_cai = True
    assert pilot.rede_carteira_csv(mes=MES, remote_user=REDE_INTEIRA).status_code == 200


def test_banco_sem_prova_de_queda_e_o_piloto_ocupado_com_retry(
    banco: _Banco, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pool saturado/lock sem prova de queda: a MESMA resposta do gate, com `Retry-After`
    (a SPA repete sozinha). Com a queda provada, o "acesso indisponivel"."""
    banco.masters_cai = True  # o duble levanta `BancoSemProvaDeQueda`
    monkeypatch.setattr(acesso, "banco_em_falha", lambda: False)
    for chamada in _chamadas_da_allowlist():
        with pytest.raises(HTTPException) as erro:
            chamada()
        assert erro.value.status_code == 503
        assert erro.value.detail == pilot.DETALHE_PILOTO_OCUPADO
        assert erro.value.headers == {"Retry-After": pilot.RETRY_AFTER_PILOTO_OCUPADO_S}
    monkeypatch.setattr(acesso, "banco_em_falha", lambda: True)
    for chamada in _chamadas_da_allowlist():
        assert _status(chamada) == (503, DETALHE_503)


@pytest.mark.parametrize(
    "caminho",
    [
        "/api/rede/unidade/botafogo-rj?.pdf",
        "/api/rede/unidade/botafogo-rj#.pdf",
        "/api/rede/unidade/botafogo-rj?/concorrencia.pdf",
        "/api/rede/carteira?.csv",
    ],
)
def test_caminho_com_interrogacao_ou_cerquilha_decodificada_e_400(caminho: str) -> None:
    """`%3F`/`%23` chegam DECODIFICADOS no `scope["path"]`: o gate (que le `request.url.path`,
    cortado no `?`/`#`) veria a FICHA, da allowlist do master, e o roteador despacharia o PDF.
    O middleware recusa antes de qualquer gate -- nenhuma rota legitima tem esses caracteres."""
    import asyncio

    from starlette.requests import Request

    escopo = {
        "type": "http",
        "method": "GET",
        "path": caminho,
        "raw_path": caminho.encode(),
        "root_path": "",
        "scheme": "https",
        "query_string": b"",
        "headers": [(b"host", b"piloto.exemplo"), (b"remote-user", MASTER.encode())],
        "server": ("piloto.exemplo", 443),
    }
    # O caso que motivou: o caminho que o GATE le e' o da ficha, nao o do PDF.
    assert Request(escopo).url.path != caminho

    async def _nunca(_req: Any) -> Any:
        raise AssertionError("a rota nao pode rodar")

    resposta = asyncio.run(pilot._controle_de_acesso_por_aba(Request(escopo), _nunca))
    assert resposta.status_code == 400


# ---------------------------------------------------------------------------
# Quem ve a rede, e o modo sem banco: nada muda
# ---------------------------------------------------------------------------


def test_quem_tem_rede_ver_ve_a_rede_como_antes(
    banco: _Banco, monkeypatch: pytest.MonkeyPatch
) -> None:
    com_banco = pilot.rede_carteira(mes=MES, remote_user=REDE_INTEIRA)
    assert len(com_banco["unidades"]) == 5
    monkeypatch.setattr(acesso, "banco_no_comando", lambda: False)
    sem_banco = pilot.rede_carteira(mes=MES)
    assert com_banco == sem_banco
    assert pilot.rede_filtros(mes=MES, remote_user=REDE_INTEIRA) == pilot.rede_filtros(mes=MES)


def test_modo_sem_banco_nao_consulta_o_rbac_e_nao_recorta(
    rede: Path, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    def nunca(*_a: Any, **_k: Any) -> Any:
        raise AssertionError("sem banco, o RBAC nao pode ser consultado")

    monkeypatch.setattr(acesso, "banco_no_comando", lambda: False)
    monkeypatch.setattr(rbac, "identidade", nunca)
    monkeypatch.setattr(rbac, "masters_do_usuario", nunca, raising=False)
    payload = pilot.rede_carteira(mes=MES, remote_user=MASTER)
    assert len(payload["unidades"]) == 5
    assert pilot.rede_carteira_csv(mes=MES, remote_user=MASTER).status_code == 200
    assert pilot.rede_unidade("botafogo-rj", mes=MES, remote_user=MASTER)["unidade"]["id"] == "botafogo-rj"


def test_recorte_da_rede_e_sincrono() -> None:
    """Vai ao Postgres com driver sincrono: nunca `async def` (trava do event loop)."""
    import inspect

    assert not inspect.iscoroutinefunction(pilot._recorte_da_rede)
    assert not inspect.iscoroutinefunction(pilot._exigir_rede_inteira)
