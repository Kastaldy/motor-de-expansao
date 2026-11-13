"""Unidades Ultra incluídas pelo site (DEC-085, migration 024): rotas, permissão e leitura no Mapa.

O banco (prazo de 1 dia na trigger, remover é marcar, nome único entre as vivas) é provado contra
Postgres de verdade em `tests/integration/test_login_ponta_a_ponta.py`, seção 4. Aqui fica o que
só existe no piloto:

* só growth e líderes incluem, alteram e removem — e a recusa sai do SERVIDOR (403);
* nada é gravado sem a confirmação (`confirmado: true`), e a prévia não grava;
* as recusas do cadastro (nome repetido, menos de 200 m, fora do país) chegam como recado;
* a unidade aparece no pino e na busca do Mapa logo depois de salvar, sem reiniciar o site;
* depois do domingo, quando ela já está no parquet, não aparece duas vezes;
* com o banco fora, o Mapa segue com o parquet.

Chama as funções de rota DIRETO (sem TestClient), no padrão de `test_piloto_web_observacoes.py`.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import h3
import pandas as pd
import pytest
from fastapi import HTTPException

_REPO = Path(__file__).resolve().parents[2]
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import app as pilot_app  # noqa: E402

from motor_expansao import cadastro_ultra as cu  # noqa: E402
from motor_expansao.db import BancoIndisponivel  # noqa: E402
from motor_expansao.db import unidades_site as db_us  # noqa: E402

CAPACIDADE = "rede.unidade_incluir"
T0 = datetime(2026, 11, 13, 15, 0, tzinfo=UTC)
TERESOPOLIS = {"unidade": "Teresópolis", "lat": -22.407291, "lng": -42.965760}


class _Eu:
    def __init__(self, id_usuario: int, *capacidades: str) -> None:
        self.id_usuario = id_usuario
        self._cap = set(capacidades)

    def pode(self, chave: str) -> bool:
        return chave in self._cap


GROWTH = _Eu(14, "territorio.explorar", CAPACIDADE)
LIDERES = _Eu(13, "territorio.explorar", CAPACIDADE)
EXPANSAO = _Eu(11, "territorio.explorar")
CONSULTORIA = _Eu(12, "rede.ver")


class _Banco:
    """Dublê de `db/unidades_site`: guarda em memória e aplica o prazo pelo relógio do dublê."""

    def __init__(self) -> None:
        self.linhas: dict[int, cu.UnidadeDoSite] = {}
        self.agora = T0
        self.fora = False

    def _conferir_vivo(self) -> None:
        if self.fora:
            raise BancoIndisponivel("dublê fora do ar")

    def listar_vivas(self, pais: str) -> list[cu.UnidadeDoSite]:
        self._conferir_vivo()
        return [u for u in self.linhas.values() if u.pais == pais and u.removida_em is None]

    def incluir(self, **k: Any) -> int:
        self._conferir_vivo()
        ident = len(self.linhas) + 1
        self.linhas[ident] = cu.UnidadeDoSite(
            id_unidade_site=ident,
            pais=k["pais"],
            unidade=k["unidade"],
            uf=k["uf"],
            cidade=k["cidade"],
            lat=k["lat"],
            lng=k["lng"],
            hex_id_res7=k["hex_id_res7"],
            criada_em=self.agora,
            id_usuario_criou=k["autor"],
            nome_quem_criou=f"Pessoa {k['autor']}",
        )
        return ident

    def _travar(self, ident: int, pais: str) -> cu.UnidadeDoSite:
        u = self.linhas.get(ident)
        if u is None or u.pais != pais:
            raise db_us.UnidadeDesconhecida(f"Unidade {ident} não encontrada.")
        if u.removida_em is not None:
            raise db_us.UnidadeRemovida("Esta unidade já foi removida.")
        if not u.no_prazo(self.agora):
            raise db_us.PrazoEncerrado(db_us.MENSAGEM_PRAZO)
        return u

    def alterar(self, ident: int, **k: Any) -> None:
        u = self._travar(ident, k["pais"])
        self.linhas[ident] = cu.UnidadeDoSite(
            **{**u.__dict__, **{c: k[c] for c in ("unidade", "uf", "cidade", "lat", "lng", "hex_id_res7")}},
        )

    def remover(self, ident: int, *, pais: str, autor: int) -> None:
        u = self._travar(ident, pais)
        self.linhas[ident] = cu.UnidadeDoSite(**{**u.__dict__, "removida_em": self.agora})


@pytest.fixture
def banco(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> _Banco:
    """Cadastro de duas unidades em parquet, banco dublado e a malha devolvendo Teresópolis/RJ."""
    linhas = [
        ("a" * 40, "Cabo Frio / RJ", "RJ", "Cabo Frio", -22.88242, -42.02299),
        ("b" * 40, "Maricá / RJ", "RJ", "Maricá", -22.922484, -42.817391),
    ]
    cadastro = tmp_path / "unidades_ultra_mapeadas.parquet"
    pd.DataFrame(
        [
            {
                "ultra_id": i, "unidade": u, "uf": uf, "cidade": c, "lat": la, "lng": ln,
                "flag_coord_valida": True, "hex_id_res7": h3.latlng_to_cell(la, ln, 7),
            }
            for i, u, uf, c, la, ln in linhas
        ],
        columns=list(cu.COLUNAS_CADASTRO),
    ).to_parquet(cadastro, index=False)
    monkeypatch.setattr(pilot_app, "ULTRA_MAPEADAS_PARQUET", cadastro)
    monkeypatch.setattr(pilot_app, "ULTRA_PERF_PARQUET", tmp_path / "nao-existe.parquet")
    monkeypatch.setattr(pilot_app, "GROWTH_PARQUET", tmp_path / "nao-existe-growth.parquet")

    dub = _Banco()
    for nome in ("listar_vivas", "incluir", "alterar", "remover"):
        monkeypatch.setattr(db_us, nome, getattr(dub, nome))
    monkeypatch.setattr(pilot_app, "_agora_utc", lambda: dub.agora)
    monkeypatch.setattr(
        pilot_app, "municipio_do_ponto", lambda lat, lng: {"uf": "RJ", "municipio": "Teresópolis"}
    )
    monkeypatch.setattr(pilot_app, "_rede_mapa_do_ponto", lambda lat, lng: {"concorrentes": []})
    pilot_app.limpar_caches()
    yield dub
    pilot_app.limpar_caches()


def _como(monkeypatch: pytest.MonkeyPatch, eu: _Eu) -> None:
    monkeypatch.setattr(pilot_app, "_identidade_para_unidade", lambda _u: eu)


def _corpo(**extra: Any) -> Any:
    return pilot_app.UnidadeSiteIn(**{**TERESOPOLIS, **extra})


def _incluir(**extra: Any) -> dict[str, Any]:
    return pilot_app.mapa_unidades_site_incluir(_corpo(confirmado=True, **extra), remote_user=None)


def _nomes_dos_pinos() -> list[str]:
    return list(pilot_app._ultra_pontos_mapa()["nome"])


def _ids_da_busca() -> list[str]:
    return [u["id"] for u in pilot_app.mapa_unidades()["unidades"]]


# ---------------------------------------------------------------------------------------
# Incluir: quem pode, e o que aparece no Mapa
# ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("eu", [GROWTH, LIDERES], ids=["growth", "lideres"])
def test_growth_e_lideres_incluem_e_a_unidade_aparece_no_pino_e_na_busca_sem_restart(
    banco: _Banco, monkeypatch: pytest.MonkeyPatch, eu: _Eu
) -> None:
    _como(monkeypatch, eu)
    # O Mapa já foi desenhado uma vez: os pinos e a busca estão em cache.
    assert "Teresópolis" not in _nomes_dos_pinos()
    assert "cadastro-site-1" not in _ids_da_busca()

    resposta = _incluir()

    assert resposta["incluida"]["id"] == 1
    assert resposta["incluida"]["uf"] == "RJ" and resposta["incluida"]["cidade"] == "Teresópolis"
    assert banco.linhas[1].id_usuario_criou == eu.id_usuario
    assert "Teresópolis" in _nomes_dos_pinos()
    assert "cadastro-site-1" in _ids_da_busca()
    ficha = pilot_app.mapa_unidade("cadastro-site-1")
    assert ficha["unidade"]["nome"] == "Teresópolis"


@pytest.mark.parametrize("eu", [EXPANSAO, CONSULTORIA], ids=["expansao", "consultoria"])
def test_quem_nao_e_growth_nem_lideres_recebe_403_e_nada_e_gravado(
    banco: _Banco, monkeypatch: pytest.MonkeyPatch, eu: _Eu
) -> None:
    _como(monkeypatch, eu)
    with pytest.raises(HTTPException) as erro:
        _incluir()
    assert erro.value.status_code == 403
    with pytest.raises(HTTPException) as erro:
        pilot_app.mapa_unidades_site_previa(_corpo(), remote_user=None)
    assert erro.value.status_code == 403
    assert banco.linhas == {}
    lista = pilot_app.mapa_unidades_site(remote_user=None)
    assert lista["pode_incluir"] is False and lista["unidades"] == []
    assert lista["icone_ultra"] is None


def test_sem_a_confirmacao_nada_e_gravado(banco: _Banco, monkeypatch: pytest.MonkeyPatch) -> None:
    _como(monkeypatch, GROWTH)
    with pytest.raises(HTTPException) as erro:
        pilot_app.mapa_unidades_site_incluir(_corpo(), remote_user=None)
    assert erro.value.status_code == 422
    assert "confirm" in str(erro.value.detail).lower()
    assert banco.linhas == {}


def test_previa_mostra_o_que_sera_gravado_e_nao_grava(banco: _Banco, monkeypatch: pytest.MonkeyPatch) -> None:
    _como(monkeypatch, GROWTH)
    previa = pilot_app.mapa_unidades_site_previa(_corpo(), remote_user=None)
    assert (previa["unidade"], previa["uf"], previa["cidade"]) == ("Teresópolis", "RJ", "Teresópolis")
    assert previa["hex_id_res7"] == h3.latlng_to_cell(TERESOPOLIS["lat"], TERESOPOLIS["lng"], 7)
    assert previa["mais_perto"]["unidade"] == "Maricá / RJ"
    assert previa["prazo_horas"] == 24
    assert banco.linhas == {}


def test_uf_e_cidade_vem_sempre_do_ponto(banco: _Banco, monkeypatch: pytest.MonkeyPatch) -> None:
    """Só nome e coordenada (prévia de 13/11/2026): UF e cidade mandadas no corpo não valem."""
    _como(monkeypatch, GROWTH)
    previa = pilot_app.mapa_unidades_site_previa(_corpo(uf="SP", cidade="Outra Cidade"), remote_user=None)
    assert (previa["uf"], previa["cidade"]) == ("RJ", "Teresópolis")
    _incluir(uf="SP", cidade="Outra Cidade")
    assert (banco.linhas[1].uf, banco.linhas[1].cidade) == ("RJ", "Teresópolis")


@pytest.mark.parametrize(
    "resposta",
    [HTTPException(404, "Nenhum município encontrado"), {"uf": "RJ", "municipio": None}],
    ids=["mar-aberto", "sem-nome-de-municipio"],
)
def test_ponto_sem_municipio_e_recusado_sem_gravar(
    banco: _Banco, monkeypatch: pytest.MonkeyPatch, resposta: Any
) -> None:
    def _ponto(lat: float, lng: float) -> dict[str, Any]:
        if isinstance(resposta, Exception):
            raise resposta
        return resposta

    monkeypatch.setattr(pilot_app, "municipio_do_ponto", _ponto)
    _como(monkeypatch, GROWTH)
    for chamada in (
        lambda: pilot_app.mapa_unidades_site_previa(_corpo(), remote_user=None),
        lambda: _incluir(),
    ):
        with pytest.raises(HTTPException) as erro:
            chamada()
        assert erro.value.status_code == 422
        assert "Não achamos o município deste ponto" in str(erro.value.detail)
    assert banco.linhas == {}


@pytest.mark.parametrize(
    ("extra", "status", "trecho"),
    [
        ({"unidade": "cabo frio / rj", "lat": -22.5, "lng": -42.5}, 409, "Já existe"),
        ({"unidade": "Cabo Frio II", "lat": -22.88142, "lng": -42.02299}, 409, "pode ser a mesma"),
        ({"lat": -42.965760, "lng": -22.407291}, 422, "fora do país"),
        ({"unidade": " "}, 422, "Preencha"),
    ],
    ids=["nome-repetido", "a-menos-de-200-m", "fora-da-caixa", "sem-nome"],
)
def test_recusas_do_cadastro_chegam_como_recado(
    banco: _Banco, monkeypatch: pytest.MonkeyPatch, extra: dict[str, Any], status: int, trecho: str
) -> None:
    _como(monkeypatch, GROWTH)
    for chamada in (
        lambda: pilot_app.mapa_unidades_site_previa(_corpo(**extra), remote_user=None),
        lambda: _incluir(**extra),
    ):
        with pytest.raises(HTTPException) as erro:
            chamada()
        assert erro.value.status_code == status
        assert trecho in str(erro.value.detail)
    assert banco.linhas == {}


def test_a_mesma_unidade_do_site_nao_entra_duas_vezes(banco: _Banco, monkeypatch: pytest.MonkeyPatch) -> None:
    _como(monkeypatch, GROWTH)
    _incluir()
    with pytest.raises(HTTPException) as erro:
        _incluir()
    assert erro.value.status_code == 409
    assert len(banco.linhas) == 1


# ---------------------------------------------------------------------------------------
# O prazo de 1 dia
# ---------------------------------------------------------------------------------------


def test_alterar_e_remover_valem_no_primeiro_dia(banco: _Banco, monkeypatch: pytest.MonkeyPatch) -> None:
    _como(monkeypatch, GROWTH)
    _incluir()
    banco.agora = T0 + timedelta(hours=23, minutes=59)
    pilot_app.mapa_unidades_site_alterar(1, _corpo(lat=-22.4120, lng=-42.9660, confirmado=True), remote_user=None)
    assert banco.linhas[1].lat == pytest.approx(-22.4120)
    assert banco.linhas[1].hex_id_res7 == h3.latlng_to_cell(-22.4120, -42.9660, 7)
    pilot_app.mapa_unidades_site_remover(1, remote_user=None)
    assert banco.linhas[1].removida_em is not None
    assert "Teresópolis" not in _nomes_dos_pinos()
    assert "cadastro-site-1" not in _ids_da_busca()


def test_depois_de_um_dia_alterar_e_remover_dao_409(banco: _Banco, monkeypatch: pytest.MonkeyPatch) -> None:
    _como(monkeypatch, LIDERES)
    _incluir()
    banco.agora = T0 + timedelta(hours=24, minutes=1)
    for chamada in (
        lambda: pilot_app.mapa_unidades_site_alterar(1, _corpo(confirmado=True), remote_user=None),
        lambda: pilot_app.mapa_unidades_site_remover(1, remote_user=None),
    ):
        with pytest.raises(HTTPException) as erro:
            chamada()
        assert erro.value.status_code == 409
        assert "prazo de 1 dia" in str(erro.value.detail)
    assert banco.linhas[1].removida_em is None


def test_alterar_tambem_exige_confirmacao_e_permissao(banco: _Banco, monkeypatch: pytest.MonkeyPatch) -> None:
    _como(monkeypatch, GROWTH)
    _incluir()
    with pytest.raises(HTTPException) as erro:
        pilot_app.mapa_unidades_site_alterar(1, _corpo(lat=-22.4120), remote_user=None)
    assert erro.value.status_code == 422
    _como(monkeypatch, EXPANSAO)
    for chamada in (
        lambda: pilot_app.mapa_unidades_site_alterar(1, _corpo(confirmado=True), remote_user=None),
        lambda: pilot_app.mapa_unidades_site_remover(1, remote_user=None),
    ):
        with pytest.raises(HTTPException) as erro:
            chamada()
        assert erro.value.status_code == 403


def test_lista_mostra_o_prazo_de_cada_unidade(banco: _Banco, monkeypatch: pytest.MonkeyPatch) -> None:
    _como(monkeypatch, GROWTH)
    _incluir()
    banco.agora = T0 + timedelta(hours=2)
    lista = pilot_app.mapa_unidades_site(remote_user=None)
    assert lista["pode_incluir"] is True and lista["prazo_horas"] == 24
    # o ícone do pino da Ultra, para a tela desenhar a logo num recorte que não tinha Ultra
    assert str(lista["icone_ultra"]).startswith("data:image/")
    (item,) = lista["unidades"]
    assert item["no_prazo"] is True
    assert item["prazo_ate"] == (T0 + timedelta(hours=24)).isoformat()
    assert item["incluida_por"] == "Pessoa 14"
    banco.agora = T0 + timedelta(hours=25)
    assert pilot_app.mapa_unidades_site(remote_user=None)["unidades"][0]["no_prazo"] is False


# ---------------------------------------------------------------------------------------
# Depois do domingo, e com o banco fora
# ---------------------------------------------------------------------------------------


def test_unidade_ja_levada_ao_parquet_nao_aparece_duas_vezes(
    banco: _Banco, monkeypatch: pytest.MonkeyPatch
) -> None:
    _como(monkeypatch, GROWTH)
    _incluir()
    banco.agora = T0 + timedelta(days=3)
    base = pd.read_parquet(pilot_app.ULTRA_MAPEADAS_PARQUET)
    composto, levadas = cu.compor_cadastro(base, list(banco.linhas.values()), pais="BR", agora=banco.agora)
    assert [u.id_unidade_site for u in levadas] == [1]
    composto.to_parquet(pilot_app.ULTRA_MAPEADAS_PARQUET, index=False)
    pilot_app.limpar_caches()
    assert _nomes_dos_pinos().count("Teresópolis") == 1
    assert _ids_da_busca().count("cadastro-site-1") == 1


def test_com_o_banco_fora_o_mapa_segue_com_o_parquet(banco: _Banco, monkeypatch: pytest.MonkeyPatch) -> None:
    _como(monkeypatch, GROWTH)
    _incluir()
    banco.fora = True
    pilot_app.limpar_caches()
    assert sorted(_nomes_dos_pinos()) == ["Cabo Frio / RJ", "Maricá / RJ"]
    assert "cadastro-site-1" not in _ids_da_busca()


# ---------------------------------------------------------------------------------------
# O gate e a trilha de acesso
# ---------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("metodo", "rota", "capacidade"),
    [
        ("GET", "/api/mapa/unidades-site", "territorio.explorar"),
        ("POST", "/api/mapa/unidades-site/previa", CAPACIDADE),
        ("POST", "/api/mapa/unidades-site", CAPACIDADE),
        ("PATCH", "/api/mapa/unidades-site/1", CAPACIDADE),
        ("DELETE", "/api/mapa/unidades-site/1", CAPACIDADE),
    ],
)
def test_o_gate_pede_a_capacidade_de_incluir_so_na_escrita(metodo: str, rota: str, capacidade: str) -> None:
    import acesso

    achada = next(
        cap
        for prefixo, metodos, cap in acesso.REGRAS_POR_CAPACIDADE
        if rota.startswith(prefixo) and (metodos is None or metodo in metodos)
    )
    assert achada == capacidade
    assert CAPACIDADE in acesso.CAPACIDADES_SENSIVEIS


@pytest.mark.parametrize(
    ("metodo", "rota", "rotulo"),
    [
        ("POST", "/api/mapa/unidades-site/previa", "Revisou a inclusão de uma unidade Ultra"),
        ("POST", "/api/mapa/unidades-site", "Incluiu uma unidade Ultra"),
        ("PATCH", "/api/mapa/unidades-site/3", "Alterou uma unidade Ultra incluída pelo site"),
        ("DELETE", "/api/mapa/unidades-site/3", "Removeu uma unidade Ultra incluída pelo site"),
        ("GET", "/api/mapa/unidades-site", "Navegou pelo mapa"),
    ],
)
def test_a_trilha_de_acesso_conta_a_inclusao_como_gesto_e_nao_como_navegacao(
    metodo: str, rota: str, rotulo: str
) -> None:
    from motor_expansao.dashboard.acesso_analytics import _feature_do_evento

    assert _feature_do_evento({"metodo": metodo, "rota": rota}) == rotulo
