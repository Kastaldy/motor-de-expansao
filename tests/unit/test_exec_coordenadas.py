"""Coordenadas das unidades na Visão Executiva do piloto web.

Regressão do defeito medido em produção em 2026-08-03: a lista lateral vinha da base
Growth (102 unidades, atualizada diariamente) e os pins do mapa de um parquet curado
congelado (54 unidades). Só 52 das 85 unidades da lista apareciam no mapa — no RJ,
2 de 9. Estes testes fixam o contrato do join que fechou a lacuna:

  - `_chave_unidade` aceita as três grafias de sufixo de UF ("/ RJ", " - RJ", " RJ")
    e NÃO come letras de nomes que terminam em sigla de UF sem separador;
  - a base curada tem PRECEDÊNCIA sobre o cadastro amplo (o cadastro tem pontos
    errados conhecidos, ex.: `TAUBATE`);
  - o cadastro amplo COMPLETA as unidades que a curada não tem;
  - a tabela de aliases resolve os nomes comerciais divergentes;
  - `ADMINISTRACAO` não é unidade e fica fora da visão.

READ-ONLY sobre o M1: os testes só leem parquets sintéticos em `tmp_path`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

_REPO = Path(__file__).resolve().parents[2]  # tests/unit/ -> raiz do worktree
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import app as pilot  # noqa: E402  (backend do piloto; web/server no sys.path acima)

_CACHED = ("_carregar_ultra_pontos", "_carregar_ultra_mapeadas", "_ultra_coord_map", "_carregar_growth")


def _clear_caches() -> None:
    pilot.limpar_caches()


# --- fixtures ---------------------------------------------------------------

# Ponto correto de Taubaté; o cadastro amplo real traz um segundo ponto na Grande SP
# para o mesmo nome — a curada precisa vencer.
_TAUBATE_OK = (-23.0227, -45.5818)
_TAUBATE_ERRADO = (-23.6415, -46.7844)


def _perf_hex() -> pd.DataFrame:
    """Base curada (espelha `unidades_ultra_performance_hex.parquet`)."""
    return pd.DataFrame(
        [
            {"unidade": "BOTAFOGO", "lat": -22.9504, "lng": -43.1870},
            {"unidade": "TAUBATE", "lat": _TAUBATE_OK[0], "lng": _TAUBATE_OK[1]},
            {"unidade": "CAMPO LIMPO", "lat": None, "lng": None},  # sem coordenada
        ]
    )


def _mapeadas() -> pd.DataFrame:
    """Cadastro amplo (espelha `unidades_ultra_mapeadas.parquet`)."""
    return pd.DataFrame(
        [
            # grafias de sufixo que a normalização antiga não cobria
            {"unidade": "Icaraí RJ", "uf": "RJ", "cidade": "Niterói", "lat": -22.9086, "lng": -43.1075},
            {"unidade": "Bangú / RJ", "uf": "RJ", "cidade": "Rio de Janeiro", "lat": -22.8798, "lng": -43.4690},
            # alvo de alias
            {"unidade": "Shopping Partage RJ", "uf": "RJ", "cidade": "São Gonçalo", "lat": -22.8209, "lng": -43.0462},
            # alvo do alias de prefixo: a Growth chama de "CAXIAS", o cadastro de
            # "Duque de Caxias" — nenhuma normalização liga os dois.
            {"unidade": "Duque de Caxias", "uf": "RJ", "cidade": "Duque de Caxias", "lat": -22.7926, "lng": -43.3131},
            # divergente da curada: aqui o ponto está errado (Grande SP)
            {"unidade": "Taubaté / SP", "uf": "SP", "cidade": "São Paulo", "lat": _TAUBATE_ERRADO[0], "lng": _TAUBATE_ERRADO[1]},
            # UF divergente entre as bases: Growth marca DF, cadastro marca GO
            {"unidade": "Novo Gama / GO", "uf": "GO", "cidade": "Novo Gama", "lat": -16.0500, "lng": -48.0400},
            # descartada pela flag
            {"unidade": "Fantasma / RJ", "uf": "RJ", "cidade": "Rio de Janeiro", "lat": -22.0, "lng": -43.0},
        ]
    ).assign(flag_coord_valida=lambda d: d["unidade"].ne("Fantasma / RJ"))


def _growth() -> pd.DataFrame:
    """Base Growth diária, com faturamento CUMULATIVO no mês (como a real)."""
    unidades = [
        ("BOTAFOGO - RJ", "RJ"),
        ("ICARAI - RJ", "RJ"),
        ("BANGU - RJ", "RJ"),
        ("SAO GONCALO SHOPPING - RJ", "RJ"),
        ("CAXIAS - RJ", "RJ"),  # não existe em nenhuma base de coordenada
        ("ADMINISTRACAO", "RJ"),  # não é unidade física
    ]
    linhas = []
    for nome, uf in unidades:
        for mes in (6, 7):
            for dia in range(1, 29):
                linhas.append(
                    {
                        "unidade": nome,
                        "uf": uf,
                        "inauguracao": "01/01/2020",
                        "data": f"{dia:02d}/{mes:02d}/2026",
                        "faturamento": 5000.0 * dia,
                        "pagantes": 500.0,
                        "cancelados": 2.0 * dia,
                        "ativos_total": 800.0,
                        "alunos_gympass": 100.0,
                        "alunos_totalpass": 50.0,
                        "ticket_medio_pagantes": 120.0,
                        "NPS": 70.0,
                    }
                )
    return pd.DataFrame(linhas)


@pytest.fixture
def app_com_dados(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    staging = tmp_path / "staging"
    staging.mkdir(parents=True)
    _perf_hex().to_parquet(staging / "unidades_ultra_performance_hex.parquet")
    _mapeadas().to_parquet(staging / "unidades_ultra_mapeadas.parquet")
    _growth().to_parquet(staging / "growth_api_historico.parquet")
    monkeypatch.setattr(pilot, "STAGING_DIR", staging)
    monkeypatch.setattr(pilot, "ULTRA_PERF_PARQUET", staging / "unidades_ultra_performance_hex.parquet")
    monkeypatch.setattr(pilot, "ULTRA_MAPEADAS_PARQUET", staging / "unidades_ultra_mapeadas.parquet")
    monkeypatch.setattr(pilot, "GROWTH_PARQUET", staging / "growth_api_historico.parquet")
    _clear_caches()
    yield tmp_path
    _clear_caches()


# --- normalização -----------------------------------------------------------


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("BANGU - RJ", "BANGU"),  # hífen (o único que a normalização antiga cobria)
        ("Bangú / RJ", "BANGU"),  # barra + acento
        ("Icaraí RJ", "ICARAI"),  # espaço + acento
        ("  bangu   -  rj  ", "BANGU"),  # caixa, espaços colapsados
        ("Sao Pedro da Aldeia / RJ", "SAO PEDRO DA ALDEIA"),
        ("SAO GONCALO - CENTRO - RJ", "SAO GONCALO - CENTRO"),  # só o sufixo final sai
        (None, ""),
        (float("nan"), ""),
    ],
)
def test_chave_unidade_remove_sufixo_de_uf(entrada, esperado) -> None:
    assert pilot._chave_unidade(entrada) == esperado


@pytest.mark.parametrize(
    "nome",
    [
        "NATAL",  # terminaria em "AL" (Alagoas)
        "VISCONDE DE RIO CLARO",  # terminaria em "RO" (Rondônia)
        "AMERICANA CENTRO",  # idem
        "BAURU COTAS III",
        "ARIBIRI E",
    ],
)
def test_chave_unidade_nao_come_letras_sem_separador(nome: str) -> None:
    """Sem separador antes da sigla, não é sufixo de UF — é parte do nome."""
    assert pilot._chave_unidade(nome) == nome


# --- precedência e cobertura das fontes -------------------------------------


def test_base_curada_tem_precedencia_sobre_cadastro(app_com_dados) -> None:
    """`TAUBATE` está nas duas fontes com pontos diferentes; a curada é a correta."""
    lat, lng = pilot._coord_da_unidade("TAUBATE - SP", "SP")
    assert (round(lat, 4), round(lng, 4)) == _TAUBATE_OK
    assert (round(lat, 4), round(lng, 4)) != _TAUBATE_ERRADO


def test_cadastro_completa_o_que_a_curada_nao_tem(app_com_dados) -> None:
    """Unidades ausentes da curada passam a ter pin — o defeito que motivou a correção."""
    assert pilot._coord_da_unidade("ICARAI - RJ", "RJ") == pytest.approx((-22.9086, -43.1075))
    assert pilot._coord_da_unidade("BANGU - RJ", "RJ") == pytest.approx((-22.8798, -43.4690))


def test_alias_resolve_nome_comercial_divergente(app_com_dados) -> None:
    """"SAO GONCALO SHOPPING" no Growth = "Shopping Partage" no cadastro."""
    assert pilot._coord_da_unidade("SAO GONCALO SHOPPING - RJ", "RJ") == pytest.approx(
        (-22.8209, -43.0462)
    )


def test_fallback_por_chave_quando_uf_diverge(app_com_dados) -> None:
    """Growth marca a unidade como DF; o cadastro, como GO. O pin ainda tem de sair."""
    assert pilot._coord_da_unidade("NOVO GAMA - DF", "DF") == pytest.approx((-16.05, -48.04))


def test_alias_resolve_prefixo_de_nome_que_a_normalizacao_nao_liga(app_com_dados) -> None:
    """A Growth chama "CAXIAS - RJ"; o cadastro, "Duque de Caxias".

    `_chave_unidade` remove SUFIXO de UF, nunca PREFIXO de nome — "CAXIAS" jamais
    viraria "DUQUE DE CAXIAS". Sem o alias a unidade fica sem pin nas duas telas, que
    foi o defeito relatado em produção em 2026-08-07.
    """
    assert pilot._coord_da_unidade("CAXIAS - RJ", "RJ") == pytest.approx((-22.7926, -43.3131))


def test_valores_do_alias_sao_chaves_ja_normalizadas() -> None:
    """Invariante do dict: o VALOR é comparado com `_chave_unidade(nome_do_cadastro)`.

    Um valor que não seja ele mesmo uma chave normalizada não casa com nada e vira
    no-op SILENCIOSO — o alias parece aplicado e a unidade continua sem pin. A pegadinha
    real: `_chave_unidade` preserva espaços internos, então o alvo de "Duque de Caxias"
    é "DUQUE DE CAXIAS" e não "DUQUEDECAXIAS".
    """
    for (chave_growth, uf), alvo in pilot._EXEC_ALIAS_COORD.items():
        assert pilot._chave_unidade(alvo) == alvo, f"alvo nao normalizado: {alvo!r}"
        assert pilot._chave_unidade(chave_growth) == chave_growth, f"chave nao normalizada: {chave_growth!r}"
        assert uf == uf.upper().strip() and len(uf) == 2


def test_sem_cadastro_devolve_none(app_com_dados) -> None:
    assert pilot._coord_da_unidade("UNIDADE INEXISTENTE - RJ", "RJ") is None
    assert pilot._coord_da_unidade("", "RJ") is None


def test_flag_coord_invalida_e_descartada(app_com_dados) -> None:
    assert pilot._coord_da_unidade("FANTASMA - RJ", "RJ") is None


def test_sem_parquets_nao_quebra(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Degradação graciosa: sem os parquets (cenário do CI) o mapa fica vazio, não estoura."""
    monkeypatch.setattr(pilot, "ULTRA_PERF_PARQUET", tmp_path / "nao_existe.parquet")
    monkeypatch.setattr(pilot, "ULTRA_MAPEADAS_PARQUET", tmp_path / "tambem_nao.parquet")
    _clear_caches()
    try:
        assert pilot._coord_da_unidade("BOTAFOGO - RJ", "RJ") is None
    finally:
        _clear_caches()


# --- contrato da rota -------------------------------------------------------


def test_executiva_conta_unidades_no_mapa(app_com_dados) -> None:
    body = pilot.executiva("RJ")
    nomes = {u["nome"] for u in body["unidades"]}
    com_coord = {u["nome"] for u in body["unidades"] if u["lat"] is not None}

    # ADMINISTRACAO não é unidade física -> fora da lista e dos totais.
    assert "ADMINISTRACAO" not in nomes
    assert body["totais"]["unidades"] == 5

    # As 5 ganham pin; CAXIAS entrou pelo alias de prefixo ("Duque de Caxias").
    assert com_coord == {
        "BOTAFOGO - RJ",
        "ICARAI - RJ",
        "BANGU - RJ",
        "SAO GONCALO SHOPPING - RJ",
        "CAXIAS - RJ",
    }
    assert body["totais"]["com_coordenada"] == 5


# --- pins do Mapa Territorial (`_ultra_pontos_mapa`) ------------------------


def test_pins_do_mapa_unem_curada_e_cadastro(app_com_dados) -> None:
    """Defeito de 2026-08-07: o Mapa Territorial só desenhava as 54 linhas da planilha
    GeoFusion congelada, então a rede aberta depois disso não existia para ele."""
    nomes = set(pilot._ultra_pontos_mapa()["nome"])
    assert {"BOTAFOGO", "TAUBATE"} <= nomes, "as unidades da curada continuam no mapa"
    assert {"Icaraí RJ", "Bangú / RJ", "Duque de Caxias"} <= nomes, "o cadastro completa o mapa"


def test_pins_do_mapa_respeitam_a_precedencia_da_curada(app_com_dados) -> None:
    """`TAUBATE` está nas duas fontes com pontos distintos: um pin só, o da curada."""
    df = pilot._ultra_pontos_mapa()
    taubate = df[df["nome"].map(pilot._chave_unidade).eq("TAUBATE")]
    assert len(taubate) == 1, "a mesma unidade não pode virar dois pins"
    ponto = (round(float(taubate.iloc[0]["lat"]), 4), round(float(taubate.iloc[0]["lng"]), 4))
    assert ponto == _TAUBATE_OK
    assert ponto != _TAUBATE_ERRADO


def test_pins_do_mapa_descartam_flag_coord_invalida(app_com_dados) -> None:
    assert "Fantasma / RJ" not in set(pilot._ultra_pontos_mapa()["nome"])


def test_uniao_do_mapa_nao_contamina_o_indice_da_visao_executiva(app_com_dados) -> None:
    """Guardrail de desenho: `_ultra_coord_map` separa as fontes porque a precedência é
    ENTRE FONTES — foi misturando as duas que `TAUBATE` foi parar na Grande SP. O dict
    `curada` tem de continuar vindo só da curada, mesmo com o mapa unindo as bases."""
    curada, _, _ = pilot._ultra_coord_map()
    assert set(curada) == {"BOTAFOGO", "TAUBATE"}, "o cadastro vazou para o índice da curada"
    assert "DUQUE DE CAXIAS" not in curada


def test_pins_do_mapa_sem_parquets_nao_quebra(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Degradação graciosa: sem os parquets (cenário do CI) o mapa fica vazio, não estoura."""
    monkeypatch.setattr(pilot, "ULTRA_PERF_PARQUET", tmp_path / "nao_existe.parquet")
    monkeypatch.setattr(pilot, "ULTRA_MAPEADAS_PARQUET", tmp_path / "tambem_nao.parquet")
    _clear_caches()
    try:
        df = pilot._ultra_pontos_mapa()
        assert len(df) == 0
        assert list(df.columns) == ["nome", "lat", "lng"]
    finally:
        _clear_caches()


def test_executiva_centro_usa_so_quem_tem_coordenada(app_com_dados) -> None:
    """O centro é a média dos pins; sem isso o mapa abre longe da rede."""
    body = pilot.executiva("RJ")
    lats = [u["lat"] for u in body["unidades"] if u["lat"] is not None]
    assert body["centro"]["lat"] == pytest.approx(sum(lats) / len(lats), abs=1e-5)
