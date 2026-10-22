"""Recomendacao unica na WEB (DEC-077, Fase 4): o Top 10 nas rotas do piloto.

O modulo (`motor_expansao.recomendacao`) tem a suite dele; aqui se trava a INTEGRACAO:

- o bloco `recomendacao` abre o payload de `/api/municipio`, `/api/uf` e `/api/hexagonos`
  (presenca da chave = discriminador do front), com 2 x 5 vagas e JSON estrito;
- o passo 5 do municipio e o da UF apresentam o MESMO Top 10 do bloco -- calculado sobre o
  recorte INTEIRO, nao sobre o passo 3 --, e os 10 sempre chegam ao mapa;
- sem o carimbo k da malha: bloco indisponivel, sem 500, mapa e camadas 1 a 4 intactos;
- camadas 1 a 4 com os mesmos numeros do legado e sem frase de veredito;
- nomes das regioes = os de `bairros_por_hex`; renda da vaga = a do card do hexagono;
- uma funcao so' chama o modulo; o Top 10 do Brasil fica em cache por identidade do dado;
- a subida valida a regua e o carimbo k.

O cenario usa celulas H3 res-7 DE VERDADE (os nomes saem do centro do bbox do setor) e o
staging com o carimbo k da malha. Sem as colunas da E3 no artefato, a renda e' a formula
municipal com uplift/moradores NACIONAIS do perfil (staging sem as tabelas, como em dev):
calibrada 3.000 -> renda domiciliar ~13,8 mil (passa na Mata Virgem); 500 -> ~2,3 mil (prova
de que NAO e Mata Virgem).

Chama as funcoes de rota DIRETO (sem TestClient), como o resto da suite do piloto.
"""

from __future__ import annotations

import dataclasses
import inspect
import json
import logging
import os
from pathlib import Path

import h3
import pandas as pd
import pytest
from fastapi import HTTPException

from motor_expansao.recomendacao import COLUNAS_OBRIGATORIAS, Recorte
from motor_expansao.recomendacao import subida as subida_mod
from motor_expansao.renda import (
    COL_RENDA_DOM_MALHA,
    COL_RENDA_PC_MALHA,
    COLS_RENDA_LEITURA,
    COLS_RENDA_MALHA,
    InsumoRendaInvalido,
    fator,
)
from motor_expansao.renda import hex as renda_hex
from tests.unit.test_piloto_web_endpoints import _clear_caches, _point_app_at, pilot

K_CARIMBO = "multiplicativo_global_k=1.2334632196696071"
CALIB_ALTA = 3000.0
CALIB_BAIXA = 500.0
SEGMENTOS = ("mata_virgem", "premium")


def _celulas(lat: float, lng: float, anel: int) -> list[str]:
    return sorted(h3.grid_disk(h3.latlng_to_cell(lat, lng, 7), anel))


_SP = _celulas(-23.55, -46.63, 2)
_CAMP = _celulas(-22.90, -47.06, 1)

#: Papel -> hexagono de Sao Paulo (capital).
SP = {
    papel: _SP[i]
    for i, papel in enumerate(
        [
            "mv_a",  # residual 8.000 -> MV1
            "mv_b",  # residual 7.000 e 5 concorrentes (saturado no passo 3) -> MV2
            "mv_c",  # residual 6.000, pop 30.000 -> MV3 (empate no residual com mv_d)
            "mv_d",  # residual 6.000, pop 25.000 -> MV4 (sem setor: sem nome)
            "mv_e",  # residual 5.000, renda MUNICIPAL -> MV5
            "mv_f",  # residual 4.000 -> 6o candidato, fica fora das 5 vagas
            "estimado",  # renda e residual altissimos, residual ESTIMADO -> nunca aparece
            "pr_a",  # residual 0, score 80, pop 40.000 -> P1
            "pr_b",  # renda baixa, residual 3.000, score 60, pop 35.000 -> P2
            "pr_c",  # residual 0, score 55, pop 20.000 -> P3
            "neutro_score",  # score 40: nem MV nem Premium
            "neutro_pop",  # pop 5.000: abaixo do piso do Premium
        ]
    )
}
CAMP = {
    "mv_a": _CAMP[0],  # residual 5.500
    "mv_b": _CAMP[1],  # residual 4.500
    "pr_a": _CAMP[2],  # pop 30.000
    "pr_b": _CAMP[3],  # pop 25.000
    "neutro": _CAMP[4],
}
TO = h3.latlng_to_cell(-10.18, -48.33, 7)  # Palmas: residual 9.000, o maior do pais

COD_SP, COD_CAMP, COD_TO = "3550308", "3509502", "1721000"


def _linha(
    hex_id: str,
    muni: str,
    cod: str,
    *,
    residual: float,
    pop: float,
    score: float,
    calib: float = CALIB_ALTA,
    municipal: float = 2500.0,
    medido: bool = True,
    conc: int = 0,
) -> dict[str, object]:
    lat, lng = h3.cell_to_latlng(hex_id)
    return {
        "hex_id": hex_id,
        "lat": lat,
        "lng": lng,
        "nome_municipio": muni,
        "cod_municipio": cod,
        "score_priorizacao": 70.0,
        "score_setor_2022_calibrado": score,
        "score_expansao_hibrido": 60.0,
        "score_oportunidade_residual": min(100.0, 100.0 * residual / 2500.0),
        "oferta_efetiva_disponivel": residual,
        "oferta_consumida_mercado_estimada": 0.0,
        "n_concorrentes_influencia_1km": conc,
        "capacidade_default_concorrente_alunos": 2500.0,
        "sam_fitness_potencial": residual + 1000.0,
        "populacao_corte_hex": pop,
        "pop_total": 1_000_000.0,
        "pop_total_setor_2022": pop,
        "fonte_pop_hex_base": "censo_2022_setor" if medido else "m1_municipal_proxy_per_hex",
        "renda_per_capita": municipal,
        "renda_per_capita_setor_2022_calibrada": calib,
        "faixa_oportunidade": "alta",
        "n_unidades_ultra_performance_hex": 0,
        "densidade_pop_setor_hab_km2": 5000.0,
    }


def _particao_sp(*, saturado: bool) -> pd.DataFrame:
    def conc(padrao: int) -> int:
        return 5 if saturado else padrao

    sp = [
        _linha(
            SP["mv_a"], "Sao Paulo", COD_SP, residual=8000.0, pop=20000.0, score=70.0, conc=conc(0)
        ),
        _linha(SP["mv_b"], "Sao Paulo", COD_SP, residual=7000.0, pop=15000.0, score=72.0, conc=5),
        _linha(
            SP["mv_c"], "Sao Paulo", COD_SP, residual=6000.0, pop=30000.0, score=65.0, conc=conc(1)
        ),
        _linha(
            SP["mv_d"], "Sao Paulo", COD_SP, residual=6000.0, pop=25000.0, score=64.0, conc=conc(2)
        ),
        _linha(
            SP["mv_e"],
            "Sao Paulo",
            COD_SP,
            residual=5000.0,
            pop=12000.0,
            score=63.0,
            calib=float("nan"),
            municipal=3000.0,
            conc=conc(0),
        ),
        _linha(
            SP["mv_f"], "Sao Paulo", COD_SP, residual=4000.0, pop=11000.0, score=62.0, conc=conc(0)
        ),
        _linha(
            SP["estimado"],
            "Sao Paulo",
            COD_SP,
            residual=9500.0,
            pop=50000.0,
            score=90.0,
            medido=False,
            conc=conc(0),
        ),
        _linha(
            SP["pr_a"], "Sao Paulo", COD_SP, residual=0.0, pop=40000.0, score=80.0, conc=conc(3)
        ),
        _linha(
            SP["pr_b"],
            "Sao Paulo",
            COD_SP,
            residual=3000.0,
            pop=35000.0,
            score=60.0,
            calib=CALIB_BAIXA,
            conc=conc(0),
        ),
        _linha(
            SP["pr_c"], "Sao Paulo", COD_SP, residual=0.0, pop=20000.0, score=55.0, conc=conc(0)
        ),
        _linha(
            SP["neutro_score"],
            "Sao Paulo",
            COD_SP,
            residual=0.0,
            pop=50000.0,
            score=40.0,
            calib=CALIB_BAIXA,
            conc=conc(0),
        ),
        _linha(
            SP["neutro_pop"],
            "Sao Paulo",
            COD_SP,
            residual=0.0,
            pop=5000.0,
            score=70.0,
            calib=CALIB_BAIXA,
            conc=conc(0),
        ),
        _linha(
            CAMP["mv_a"],
            "Campinas",
            COD_CAMP,
            residual=5500.0,
            pop=15000.0,
            score=66.0,
            conc=conc(0),
        ),
        _linha(
            CAMP["mv_b"],
            "Campinas",
            COD_CAMP,
            residual=4500.0,
            pop=14000.0,
            score=61.0,
            conc=conc(0),
        ),
        _linha(
            CAMP["pr_a"], "Campinas", COD_CAMP, residual=0.0, pop=30000.0, score=75.0, conc=conc(0)
        ),
        _linha(
            CAMP["pr_b"], "Campinas", COD_CAMP, residual=0.0, pop=25000.0, score=65.0, conc=conc(0)
        ),
        _linha(
            CAMP["neutro"],
            "Campinas",
            COD_CAMP,
            residual=0.0,
            pop=6000.0,
            score=35.0,
            calib=CALIB_BAIXA,
            conc=conc(0),
        ),
    ]
    return pd.DataFrame(sp)


def _particao_to() -> pd.DataFrame:
    return pd.DataFrame([_linha(TO, "Palmas", COD_TO, residual=9000.0, pop=15000.0, score=68.0)])


def _setores_sp() -> pd.DataFrame:
    """Setores sinteticos de Sao Paulo: o centro do bbox cai no hexagono do papel."""
    linhas: list[dict[str, object]] = []

    def setor(hex_id: str, bairro: str, pop: float) -> None:
        lat, lng = h3.cell_to_latlng(hex_id)
        linhas.append(
            {
                "nome_bairro": bairro,
                "nome_subdistrito": None,
                "nome_distrito": "Distrito sintético",
                "nome_municipio": "São Paulo",
                "bbox_minx": lng - 0.001,
                "bbox_miny": lat - 0.001,
                "bbox_maxx": lng + 0.001,
                "bbox_maxy": lat + 0.001,
                "pop_total_setor_2022": pop,
            }
        )

    # mv_a e mv_b tem o MESMO bairro dominante: na lista, cada um mostra o 2o bairro.
    setor(SP["mv_a"], "Pinheiros", 9000.0)
    setor(SP["mv_a"], "Jardins", 1000.0)
    setor(SP["mv_b"], "Pinheiros", 5000.0)
    setor(SP["mv_b"], "Vila Madalena", 3000.0)
    setor(SP["mv_c"], "Moema", 8000.0)
    # mv_d: nenhum setor -> regiao sem nome (o front mostra o municipio)
    setor(SP["mv_e"], "Itaim Bibi", 6000.0)
    setor(SP["pr_a"], "Perdizes", 20000.0)
    setor(SP["pr_b"], "Lapa", 15000.0)
    setor(SP["pr_c"], "Butantã", 9000.0)
    return pd.DataFrame(linhas)


def _crescimento_municipal() -> pd.DataFrame:
    """Com o veredito que a TELA deixa de ler (o PDF ainda le)."""
    base = {
        "cres_saldo_empresas": 900.0,
        "cres_salario": 2100.0,
        "cres_salario_var": 2.0,
        "cres_setor": "Comércio",
        "cres_uf_mediana": 9.0,
        "cres_dims": "Renda:12.0:%:30:2020→2024",
        "cres_series": "Renda|R$|2020|2024|2000,2100,2200,2300,2400",
    }
    return pd.DataFrame(
        [
            {
                **base,
                "cod6": "355030",
                "cres_chave_nome": "SP|SAO PAULO",
                "cres_tendencia": "Em alta",
                "cres_emp_pct": 12.0,
                "cres_confiab": "alta",
                "v_frase": "São Paulo cresceu em empresas. É praça para entrar.",
            },
            {
                **base,
                "cod6": "350950",
                "cres_chave_nome": "SP|CAMPINAS",
                "cres_tendencia": None,
                "cres_emp_pct": 4.2,
                "cres_confiab": "muito_baixa",
                "v_frase": "Campinas cresceu em renda. Vale ficar de olho, não abrir agora.",
            },
        ]
    )


def _com_malha_e3(df: pd.DataFrame) -> pd.DataFrame:
    """As colunas da malha (E3) no artefato: renda de 2022 do hexagono pela malha de setores.

    Quatro vezes a calibrada mantem a mesma classificacao (alta passa na Mata Virgem, baixa
    prova que nao e'); a renda passa a ser `malha x F_dom(uf)`, sem uplift/moradores.
    """
    out = df.copy()
    out[COL_RENDA_DOM_MALHA] = out["renda_per_capita_setor_2022_calibrada"] * 4.0
    out[COL_RENDA_PC_MALHA] = out[COL_RENDA_DOM_MALHA] / 2.8
    return out


def _montar(
    raiz: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    com_k: bool = True,
    saturado: bool = False,
    e3: bool = False,
    e3_so_no_staging: bool = False,
) -> Path:
    """Monta o cenario no `raiz`.

    `e3`: as colunas da malha (E3) no ARTEFATO enriquecido. `e3_so_no_staging`: as mesmas
    colunas so' na MALHA do staging, com o artefato sem elas -- o estado de producao entre a
    troca da malha e a remontagem do enriquecido (o snapshot de 18/10 + o staging da VPS).
    """
    enr = raiz / "outputs" / "hexagonos_dashboard_enriquecido"
    sp = _particao_sp(saturado=saturado)
    for uf, df in (("SP", _com_malha_e3(sp) if e3 else sp), ("TO", _particao_to())):
        (enr / f"uf={uf}").mkdir(parents=True)
        df.to_parquet(enr / f"uf={uf}" / "part-0.parquet")  # escrita do TESTE, nao do app
    geo = raiz / "outputs" / "setores_censitarios_2022_geo" / "uf=SP" / f"cod_municipio={COD_SP}"
    geo.mkdir(parents=True)
    _setores_sp().to_parquet(geo / "part-000.parquet")
    staging = raiz / "staging"
    staging.mkdir()
    _crescimento_municipal().to_parquet(staging / "crescimento_municipal.parquet", index=False)
    if com_k:
        todos = [*SP.values(), *CAMP.values(), TO]
        malha = pd.DataFrame(
            {"hex_id": todos, "metodo_calibracao_renda_malha": [K_CARIMBO] * len(todos)}
        )
        if e3_so_no_staging:
            base = _com_malha_e3(pd.concat([sp, _particao_to()], ignore_index=True))
            base = base.set_index("hex_id")
            for coluna in COLS_RENDA_MALHA:
                malha[coluna] = malha["hex_id"].map(base[coluna]).to_numpy()
        malha.to_parquet(staging / renda_hex.CENSO_MALHA_PARQUET)
    _point_app_at(monkeypatch, raiz)
    monkeypatch.setattr(pilot, "CONCORRENTES_PATH", staging / "concorrentes_mapeados.parquet")
    monkeypatch.setattr(
        pilot, "DASHBOARD_NACIONAL_PATH", raiz / "outputs" / "hexagonos_brasil_dashboard.parquet"
    )
    monkeypatch.setattr(pilot, "MERCADO_PARQUET", staging / "hexagonos_mercado_mapeado.parquet")
    _clear_caches()
    return raiz


@pytest.fixture
def top10_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    yield _montar(tmp_path, monkeypatch)
    _clear_caches()


@pytest.fixture
def top10_sem_k(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    yield _montar(tmp_path, monkeypatch, com_k=False)
    _clear_caches()


@pytest.fixture
def top10_saturado(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    yield _montar(tmp_path, monkeypatch, saturado=True)
    _clear_caches()


@pytest.fixture
def top10_e3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    yield _montar(tmp_path, monkeypatch, e3=True)
    _clear_caches()


@pytest.fixture
def top10_e3_staging(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    yield _montar(tmp_path, monkeypatch, e3_so_no_staging=True)
    _clear_caches()


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------


def _vagas(bloco: dict, segmento: str) -> list[dict]:
    return bloco[segmento]["vagas"]


def _preenchidas(bloco: dict) -> list[dict]:
    return [v for s in SEGMENTOS for v in _vagas(bloco, s) if not v["vazia"]]


def _ids(bloco: dict, segmento: str | None = None) -> list[str]:
    segs = SEGMENTOS if segmento is None else (segmento,)
    return [v["hex_id"] for s in segs for v in _vagas(bloco, s) if not v["vazia"]]


def _assinatura(bloco: dict) -> list[tuple]:
    return [
        (v["segmento"], v["posicao"], v["hex_id"], v["vazia"])
        for s in SEGMENTOS
        for v in _vagas(bloco, s)
    ]


def _conferir_forma(payload: dict) -> dict:
    """Chave `recomendacao` PRIMEIRA, 2 x 5 vagas e JSON estrito; devolve o bloco."""
    assert next(iter(payload)) == "recomendacao", "o bloco tem de abrir o payload"
    bloco = payload["recomendacao"]
    vagas = bloco["regra"]["vagas_por_segmento"]
    assert vagas == 5
    for s in SEGMENTOS:
        assert len(_vagas(bloco, s)) == vagas
        assert [v["posicao"] for v in _vagas(bloco, s)] == list(range(1, vagas + 1))
        chaves = {frozenset(v) for v in _vagas(bloco, s)}
        assert len(chaves) == 1, "vaga vazia e preenchida tem de ter o MESMO conjunto de chaves"
    json.dumps(payload, allow_nan=False)
    return bloco


# ---------------------------------------------------------------------------
# 1) O bloco nas tres rotas
# ---------------------------------------------------------------------------


def test_municipio_traz_o_bloco_com_2x5_vagas(top10_data: Path) -> None:
    bloco = _conferir_forma(pilot.municipio("SP", "Sao Paulo"))
    assert bloco["recorte"] == {
        "nivel": "municipio",
        "uf": "SP",
        "cod_municipio": COD_SP,
        "nome": "Sao Paulo",
    }
    assert bloco["renda"]["disponivel"] is True and bloco["renda"]["carimbo"] == K_CARIMBO
    assert _ids(bloco, "mata_virgem") == [
        SP["mv_a"],
        SP["mv_b"],
        SP["mv_c"],
        SP["mv_d"],
        SP["mv_e"],
    ]
    assert bloco["mata_virgem"]["status"] == "completo"
    assert bloco["mata_virgem"]["n_elegiveis"] == 6  # mv_f ficou fora das 5 vagas
    assert _ids(bloco, "premium") == [SP["pr_a"], SP["pr_b"], SP["pr_c"]]
    assert bloco["premium"]["status"] == "incompleto"
    vazias = [v for v in _vagas(bloco, "premium") if v["vazia"]]
    assert [v["motivo"] for v in vazias] == ["candidatos_insuficientes"] * 2
    # Residual ESTIMADO nunca aparece -- nem na lista nem como numero.
    assert SP["estimado"] not in _ids(bloco)
    assert bloco["mata_virgem"]["sem_dado"]["residual_estimado"] == 1
    # Renda municipal sinalizada na vaga (o front escreve "(municipal)").
    mv5 = _vagas(bloco, "mata_virgem")[4]
    assert mv5["hex_id"] == SP["mv_e"] and mv5["renda_municipal"] is True


def test_uf_traz_o_bloco_com_2x5_vagas(top10_data: Path) -> None:
    bloco = _conferir_forma(pilot.uf_view("SP"))
    assert bloco["recorte"]["nivel"] == "uf" and bloco["recorte"]["uf"] == "SP"
    assert _ids(bloco, "mata_virgem") == [
        SP["mv_a"],
        SP["mv_b"],
        SP["mv_c"],
        SP["mv_d"],
        CAMP["mv_a"],
    ]
    assert _ids(bloco, "premium") == [
        SP["pr_a"],
        SP["pr_b"],
        CAMP["pr_a"],
        CAMP["pr_b"],
        SP["pr_c"],
    ]
    assert bloco["premium"]["status"] == "completo"


def test_hexagonos_brasil_uf_municipio_trazem_o_bloco(top10_data: Path) -> None:
    brasil = pilot.hexagonos()
    assert list(brasil) == ["recomendacao", "cobertura"]
    bloco = _conferir_forma(brasil)
    assert bloco["recorte"]["nivel"] == "brasil" and bloco["recorte"]["nome"] == pilot.PERFIL.nome
    assert brasil["cobertura"] == {"hexes_no_recorte": 18, "ufs_no_recorte": 2}
    assert brasil["cobertura"]["hexes_no_recorte"] == bloco["n_hexes_recorte"]

    uf = pilot.hexagonos(uf="sp")  # minusculo de proposito
    assert list(uf) == ["recomendacao", "cobertura"]
    assert _conferir_forma(uf)["recorte"]["nivel"] == "uf"
    assert uf["cobertura"] == {"hexes_no_recorte": 17, "ufs_no_recorte": 1}

    muni = pilot.hexagonos(uf="SP", municipio="Campinas")
    assert _conferir_forma(muni)["recorte"]["nome"] == "Campinas"
    assert muni["cobertura"] == {"hexes_no_recorte": 5, "ufs_no_recorte": 1}
    # Do legado nao sobra nada: nem lista com indice/quadrante, nem as reguas antigas.
    for corpo in (brasil, uf, muni):
        assert not {"itens", "reguas"} & set(corpo)
        assert "hexes_acionaveis_pais" not in corpo["cobertura"]
        assert "topo_sem_medicao" not in corpo["cobertura"]


def test_hexagonos_municipio_exige_uf(top10_data: Path) -> None:
    with pytest.raises(HTTPException) as erro:
        pilot.hexagonos(municipio="Campinas")
    assert erro.value.status_code == 400
    # Municipio inexistente: o MESMO 404 de /api/municipio (a selecao e' a mesma).
    with pytest.raises(HTTPException) as erro:
        pilot.hexagonos(uf="SP", municipio="Nao Existe")
    assert erro.value.status_code == 404
    with pytest.raises(HTTPException) as erro_muni:
        pilot.municipio("SP", "Nao Existe")
    assert erro.value.detail == erro_muni.value.detail


def test_hexagonos_ignora_limite_e_por_municipio(top10_data: Path) -> None:
    """`limite`/`por_municipio` continuam na assinatura (o legado usa) e nao mexem no Top 10."""
    assert pilot.hexagonos(uf="SP") == pilot.hexagonos(uf="SP", limite=1, por_municipio=True)
    assert pilot.hexagonos() == pilot.hexagonos(limite=500, por_municipio=True)


def test_o_primeiro_mata_virgem_do_brasil_nao_vem_da_uf_que_lidera_por_soma(
    top10_data: Path,
) -> None:
    """O Top 10 nacional e' por HEXAGONO: o campeao esta na UF que perde por soma."""
    assert pilot.estados()["estados"][0]["uf"] == "SP", "fixture: SP deveria somar mais"
    bloco = pilot.hexagonos()["recomendacao"]
    mv1 = _vagas(bloco, "mata_virgem")[0]
    assert (mv1["uf"], mv1["nome_municipio"], mv1["residual"]) == ("TO", "Palmas", 9000.0)
    assert _ids(bloco, "mata_virgem") == [TO, SP["mv_a"], SP["mv_b"], SP["mv_c"], SP["mv_d"]]
    assert _ids(bloco, "premium") == [
        SP["pr_a"],
        SP["pr_b"],
        CAMP["pr_a"],
        CAMP["pr_b"],
        SP["pr_c"],
    ]


# ---------------------------------------------------------------------------
# 2) O passo 5 apresenta o bloco
# ---------------------------------------------------------------------------


def test_passo5_do_municipio_espelha_o_bloco(top10_data: Path) -> None:
    payload = pilot.municipio("SP", "Sao Paulo")
    bloco, passo5 = payload["recomendacao"], payload["passos"][4]
    preenchidas = _preenchidas(bloco)
    assert passo5["n"] == 5 and passo5["titulo"] == "Para onde crescer"
    assert passo5["funil_big"] == len(preenchidas) == 8
    assert passo5["funil_unit"] == "vagas preenchidas"
    assert passo5["funil_from"] == "12 hexágonos do município"
    assert passo5["metrica"] == "top 10"
    assert passo5["hexes"] == _ids(bloco)
    assert [i["hex_id"] for i in passo5["itens"]] == _ids(bloco)
    assert [i["rank"] for i in passo5["itens"]] == list(range(1, 9))
    for item, vaga in zip(passo5["itens"], preenchidas, strict=True):
        assert item["tipo_item"] == "hex"
        assert (item["segmento"], item["posicao_segmento"]) == (vaga["segmento"], vaga["posicao"])
        assert item["tag"] == bloco[vaga["segmento"]]["rotulo"]
        for chave in (
            "renda_domiciliar",
            "populacao",
            "residual",
            "score_censitario",
            "cod_municipio",
        ):
            assert item[chave] == vaga[chave], chave
        if vaga["segmento"] == "mata_virgem":
            assert (item["label"], item["valor"], item["tom"]) == (
                "residual",
                round(vaga["residual"]),
                "green",
            )
        else:
            assert (item["label"], item["valor"], item["tom"]) == (
                "população",
                round(vaga["populacao"]),
                "blue",
            )
        assert "municipio" not in item, "o item do municipio nao tem drill-down"
        assert item["sub"] == f"hex {vaga['hex_id'][:9]}…"
    assert "comportam entrada" not in passo5["funil_from"]


def test_passo5_da_uf_espelha_o_bloco(top10_data: Path) -> None:
    payload = pilot.uf_view("SP")
    bloco, passo5 = payload["recomendacao"], payload["passos"][4]
    assert passo5["funil_big"] == 10 and passo5["funil_unit"] == "vagas preenchidas"
    assert passo5["funil_from"] == "17 hexágonos do estado"
    assert passo5["hexes"] == _ids(bloco)
    for item, vaga in zip(passo5["itens"], _preenchidas(bloco), strict=True):
        assert item["tipo_item"] == "hex"
        assert item["municipio"] == vaga["nome_municipio"]
        assert item["cod_municipio"] == vaga["cod_municipio"]
        assert item["sub"].startswith(f"{vaga['nome_municipio']} · hex ")
    assert "Abrir" in passo5["narrativa"]
    assert "município na fila" not in passo5["funil_unit"]


def test_passo5_top10_le_o_municipio_inteiro_e_ignora_a_concorrencia(top10_data: Path) -> None:
    """O hexagono com 5 concorrentes sai do passo 3 (saturacao) e ENTRA como Mata Virgem no
    Top 10: a regra nao olha concorrencia e le TODOS os hexagonos do municipio."""
    passos = pilot.municipio("SP", "Sao Paulo")["passos"]
    assert SP["mv_b"] not in passos[2]["hexes"], "fixture: mv_b deveria estar saturado"
    assert SP["mv_b"] in passos[4]["hexes"]
    item = next(i for i in passos[4]["itens"] if i["hex_id"] == SP["mv_b"])
    assert (item["segmento"], item["posicao_segmento"]) == ("mata_virgem", 2)


def test_passo5_br_sem_indice_de_praca(top10_data: Path) -> None:
    passo5 = pilot.municipio("SP", "Sao Paulo")["passos"][4]
    assert passo5["metrica"] == "top 10"
    for item in passo5["itens"]:
        assert not {"quadrante", "nota_socio", "nota_demanda", "conc", "indice"} & set(item)
    assert "índice de praça" not in json.dumps(passo5, ensure_ascii=False)


def test_tudo_saturado_o_top10_continua_e_nao_manda_trocar_de_municipio(
    top10_saturado: Path,
) -> None:
    passos = pilot.municipio("SP", "Sao Paulo")["passos"]
    passo3, passo5 = passos[2], passos[4]
    assert passo3["funil_big"] == 0 and passo3["hexes"] == []
    assert "Nenhuma" in passo3["narrativa"]
    assert passo5["funil_big"] == 8 and len(passo5["hexes"]) == 8
    for proibida in ("não gera fila", "Avalie outro município", "comportam", "sai daqui"):
        assert proibida not in passo5["narrativa"] + passo3["narrativa"], proibida


def test_uf_saturada_top10_de_hexagonos_continua(top10_saturado: Path) -> None:
    passos = pilot.uf_view("SP")["passos"]
    assert passos[2]["funil_big"] == 0
    passo5 = passos[4]
    assert passo5["itens"] and all(
        i["tipo_item"] == "hex" and i["municipio"] for i in passo5["itens"]
    )
    assert "a fila fica vazia" not in passo5["narrativa"]
    assert "Amplie o recorte" not in passo5["narrativa"]
    # O artefato de crescimento EXISTE (so' nao ha cidade na base da leitura): o passo 4
    # nao pode afirmar que ele nao foi carregado.
    assert "não foi carregado" not in passos[3]["narrativa"]
    assert "Nenhuma cidade chegou" in passos[3]["narrativa"]


def test_os_10_entram_em_citados_e_no_mapa(
    top10_data: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Com o mapa cortado em 1 hexagono por residual, os do Top 10 entram assim mesmo --
    inclusive o Premium de residual 0, que o corte tiraria.

    O piso do passo 1 vai para fora da escala para que as camadas 1 a 4 nao citem NINGUEM
    (no dado real o passo 1 so' cita os 200 primeiros): ai so' a uniao com o Top 10 poe os
    10 no mapa. O Top 10 nao depende desse piso -- tem regua propria.
    """
    monkeypatch.setattr(pilot, "SCORE_CORTE_QUENTE", 101.0)
    for payload in (pilot.municipio("SP", "Sao Paulo", limite=1), pilot.uf_view("SP", limite=1)):
        assert not any(p["hexes"] for p in payload["passos"][:4]), "as camadas 1 a 4 citaram"
        no_mapa = {h["id"] for h in payload["hexes"]}
        ids = _ids(payload["recomendacao"])
        assert set(ids) <= no_mapa, sorted(set(ids) - no_mapa)
        assert SP["pr_a"] in ids, "fixture: o Premium de residual 0 deveria estar no Top 10"
        # O corte FOI exercitado: o maior residual + o Top 10, e nada mais.
        assert len(no_mapa) == len(set(ids) | {SP["estimado"]}) < payload["n_hex_total"]


def test_sem_k_bloco_indisponivel_sem_500(top10_sem_k: Path) -> None:
    """Staging sem o carimbo k da malha: o Top 10 fica INDISPONIVEL (nunca 500, nunca lista
    com renda em outra escala) e o resto da tela segue."""
    for payload in (pilot.municipio("SP", "Sao Paulo"), pilot.uf_view("SP")):
        bloco = _conferir_forma(payload)
        assert bloco["renda"]["disponivel"] is False
        for s in SEGMENTOS:
            assert bloco[s]["status"] == "indisponivel"
            assert {v["motivo"] for v in _vagas(bloco, s)} == {"renda_indisponivel"}
        passo5 = payload["passos"][4]
        assert passo5["funil_big"] == 0 and passo5["hexes"] == [] and passo5["itens"] == []
        assert "indisponível" in passo5["narrativa"]
        assert "Renda indisponível" in passo5["narrativa"]
        # A caixa do funil nao diz "0 vagas preenchidas" (a regua rodou e ninguem passou):
        # diz que o Top 10 esta suspenso, como a narrativa.
        assert passo5["funil_unit"] == "vagas — Top 10 indisponível"
        assert all(p["n"] == n for p, n in zip(payload["passos"], range(1, 6), strict=True))
        assert payload["passos"][0]["funil_big"] > 0, "as camadas 1 a 4 seguem"
        assert payload["hexes"], "o mapa segue"
    brasil = pilot.hexagonos()["recomendacao"]
    assert brasil["renda"]["disponivel"] is False


# ---------------------------------------------------------------------------
# 3) Camadas 1 a 4: mesmos numeros, sem veredito
# ---------------------------------------------------------------------------


def _numeros(passo: dict) -> tuple:
    itens = [
        (i.get("rank"), i.get("hex_id"), i.get("municipio"), i.get("valor"), i.get("tag"))
        for i in passo["itens"]
    ]
    return passo["funil_big"], passo["hexes"], itens


def test_camadas_1_a_4_numeros_iguais_ao_legado(top10_data: Path) -> None:
    regra = pilot._regra_recomendacao()
    df = pilot.carregar_uf("SP")
    sel, cod, nome = pilot._recorte_do_municipio(df, "SP", "Sao Paulo")
    bloco = pilot._bloco_recomendacao(
        sel, Recorte(nivel="municipio", uf="SP", cod_municipio=cod, nome=nome), regra=regra
    )
    com = pilot.montar_funil(sel, "Sao Paulo", {}, recomendacao=bloco)
    sem = pilot.montar_funil(sel, "Sao Paulo", {})
    for a, b in zip(com[:4], sem[:4], strict=True):
        assert _numeros(a) == _numeros(b), f"passo {a['n']} mudou de numero"
    assert all(com[i]["hexes"] for i in range(3)), "fixture: os passos 1 a 3 deveriam acender"
    assert com[4]["metrica"] == "top 10" and sem[4]["metrica"] == "índice de praça"

    bloco_uf = pilot._bloco_recomendacao(df, Recorte(nivel="uf", uf="SP", nome="SP"), regra=regra)
    com_uf = pilot.montar_funil_uf(df, "SP", recomendacao=bloco_uf)
    sem_uf = pilot.montar_funil_uf(df, "SP")
    for a, b in zip(com_uf[:4], sem_uf[:4], strict=True):
        assert _numeros(a) == _numeros(b), f"passo {a['n']} da UF mudou de numero"


_PROIBIDAS_NA_TELA = (
    "praça para entrar",
    "entrar agora",
    "ficar de olho",
    "comporta",
    "comportam",
    "sai daqui",
    "Alto potencial não basta",
    "As áreas sem concorrência seguem valendo",
    "fila de",
    "Avalie outro município",
    "Quem escolhe e ordena o ponto",
    "índice de praça",
    "2 km",
)


def _textos(passos: list[dict]) -> str:
    return " | ".join(f"{p['narrativa']} {p['funil_unit']} {p['funil_from']}" for p in passos)


def test_nenhuma_frase_de_veredito_nas_narrativas_da_tela(top10_data: Path) -> None:
    telas = {
        "municipio SP": pilot.municipio("SP", "Sao Paulo")["passos"],
        "municipio Campinas": pilot.municipio("SP", "Campinas")["passos"],
        "uf SP": pilot.uf_view("SP")["passos"],
    }
    for nome, passos in telas.items():
        texto = _textos(passos)
        for proibida in _PROIBIDAS_NA_TELA:
            assert proibida not in texto, f"{nome}: a tela com regua ainda diz {proibida!r}"
    # Anti-vacuidade: o mesmo dado, no caminho legado, TRARIA o veredito e a fila.
    df = pilot.carregar_uf("SP")
    legado = _textos(pilot.montar_funil(df[df["nome_municipio"] == "Sao Paulo"], "Sao Paulo", {}))
    assert "praça para entrar" in legado and "fila de" in legado


def _outra_regua():
    """Regua com TODOS os numeros diferentes da BR v1 (que coincidiria com qualquer literal)."""
    regra = pilot._regra_recomendacao()
    return dataclasses.replace(
        regra,
        vagas_por_segmento=4,
        mata_virgem=dataclasses.replace(
            regra.mata_virgem, renda_domiciliar_min=6000.0, residual_min=3000.0
        ),
        premium=dataclasses.replace(regra.premium, score_min=55.0, populacao_min=12000.0),
    )


def test_narrativa_do_passo5_segue_a_regua(top10_data: Path) -> None:
    """A narrativa e a metrica do passo 5 (municipio e UF) e a frase do passo 4 da UF leem os
    numeros da regua do BLOCO -- nunca um literal (spec 1.4). Com a v1 os literais coincidem
    com a regua e nenhum outro teste veria a diferenca."""
    outra = _outra_regua()
    df = pilot.carregar_uf("SP")
    sel, cod, nome = pilot._recorte_do_municipio(df, "SP", "Sao Paulo")
    bloco = pilot._bloco_recomendacao(
        sel, Recorte(nivel="municipio", uf="SP", cod_municipio=cod, nome=nome), regra=outra
    )
    bloco_uf = pilot._bloco_recomendacao(df, Recorte(nivel="uf", uf="SP", nome="SP"), regra=outra)
    passo5 = pilot.montar_funil(sel, "Sao Paulo", {}, recomendacao=bloco)[4]
    passos_uf = pilot.montar_funil_uf(df, "SP", recomendacao=bloco_uf)
    for p5, inicio in ((passo5, "Top 8 de Sao Paulo"), (passos_uf[4], "Top 8 de SP")):
        txt = p5["narrativa"]
        assert txt.startswith(inicio), txt
        assert p5["metrica"] == "top 8"
        assert "até 4 regiões" in txt
        assert pilot._moeda_renda(6000.0) in txt and pilot._moeda_renda(4500.0) not in txt
        assert "3.000 alunos" in txt and "2.000 alunos" not in txt
        assert "score censitário de 55 ou mais" in txt
        assert "12.000 habitantes" in txt and "10.000 habitantes" not in txt
        assert "Top 10" not in txt
    narrativa_cres_uf = passos_uf[3]["narrativa"]
    assert "Esta leitura não entra no Top 8." in narrativa_cres_uf
    assert "Top 10" not in narrativa_cres_uf


def test_crescimento_da_tela_escreve_percentual_com_virgula(top10_data: Path) -> None:
    """Passo 4 do municipio com regua: o ramo descritivo (sem o veredito) escreve o
    percentual como o tooltip e o PDF, "+12,0%" -- nao "+12.0%"."""
    texto = pilot.municipio("SP", "Sao Paulo")["passos"][3]["narrativa"]
    for esperado in ("+12,0%", "+9,0%", "+2,0%"):
        assert esperado in texto, texto
    for proibido in ("+12.0%", "+9.0%", "+2.0%"):
        assert proibido not in texto, texto
    # O legado (o texto que o PDF Pontual le e a instancia sem regua mostra) nao muda: o
    # mesmo ramo descritivo, sem o veredito, segue com o `+.1f` de sempre.
    df = pilot.carregar_uf("SP")
    sp = df[df["nome_municipio"] == "Sao Paulo"].drop(columns=["v_frase"], errors="ignore")
    legado = pilot._narrativa_crescimento(sp, "Sao Paulo")
    assert "+12.0%" in legado and "+12,0%" not in legado


def test_pct_sinal() -> None:
    assert pilot._pct_sinal(12.0) == "+12,0%"
    assert pilot._pct_sinal(-3.46) == "-3,5%"
    assert pilot._pct_sinal(0.0) == "+0,0%"
    assert pilot._pct_sinal(1234.5) == "+1.234,5%"
    # Ausente: o texto de "sem dado", sem sinal nem "%".
    assert pilot._pct_sinal(float("nan")) == pilot._fmt(float("nan"))


def test_municipio_sem_tendencia_aponta_as_cinco_leituras(top10_data: Path) -> None:
    """Sem tendencia de emprego, o texto nao lista o emprego entre as "outras" leituras logo
    depois de dizer que ele nao tem tendencia."""
    texto = pilot.municipio("SP", "Campinas")["passos"][3]["narrativa"]
    assert "não tem tendência confiável no CAGED" in texto
    assert (
        "As cinco leituras de crescimento do município (renda, população, empresas, prédios e "
        "emprego) estão em Detalhes, abaixo." in texto
    )
    assert "outras leituras" not in texto


def test_uf_sem_medicao_no_estado_nao_afirma_artefato_nao_carregado(top10_data: Path) -> None:
    """TO: o artefato de crescimento ESTA carregado (tem SP), mas nenhuma cidade de TO tem
    medicao. O texto diz o que falta no estado, sem afirmar uma falha de carga que nao houve."""
    passos = pilot.uf_view("TO")["passos"]
    assert passos[2]["funil_big"] == 1, "fixture: o passo 3 de TO nao esta vazio"
    assert (
        passos[3]["narrativa"] == "A leitura de crescimento não está disponível para este estado."
    )


def test_uf_com_medicao_mas_sem_cidade_medida_na_leitura(top10_data: Path) -> None:
    """Ha medicao de emprego no ESTADO, mas nenhuma das cidades da leitura (passo 3) a tem:
    o texto conta as cidades da leitura, em linguagem de negocio."""
    df = pilot.carregar_uf("SP").copy()
    regra = pilot._regra_recomendacao()
    bloco = pilot._bloco_recomendacao(df, Recorte(nivel="uf", uf="SP", nome="SP"), regra=regra)
    # So' um hexagono FORA da leitura (residual 0, nao chega ao passo 3) guarda a medicao.
    fora = df["hex_id"] == SP["neutro_score"]
    df.loc[~fora, "cres_emp_pct"] = float("nan")
    passos = pilot.montar_funil_uf(df, "SP", recomendacao=bloco)
    assert passos[2]["funil_big"] > 0 and passos[3]["funil_big"] == 0
    assert passos[3]["narrativa"] == (
        "Nenhuma das 2 cidades desta leitura tem medição de emprego formal no CAGED."
    )


def test_passo2_da_uf_concorda_o_numero(top10_data: Path) -> None:
    """Passo 2 da UF com regua: a mesma frase do municipio, com "1 região ... tem"."""
    texto = pilot.uf_view("TO")["passos"][1]["narrativa"]
    assert texto == (
        "Descontando a oferta já instalada, 1 região de alto potencial tem residual fitness "
        "real — 9.000 alunos não atendidos."
    )


def test_caminho_br_da_uf_nao_calcula_o_indice_de_praca(
    top10_data: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Com regua, nada da UF le o indice de praca: ele so' e' anotado para a fila LEGADA."""

    def proibido(*_a, **_k):
        raise AssertionError("o caminho com regua da UF calculou o indice de praca")

    df = pilot.carregar_uf("SP")
    monkeypatch.setattr(pilot, "_anotar_indice_praca", proibido)
    assert pilot.uf_view("SP")["passos"][4]["metrica"] == "top 10"
    # Anti-vacuidade: a fila legada (instancia sem regua) e' quem o anota.
    with pytest.raises(AssertionError, match="indice de praca"):
        pilot.montar_funil_uf(df, "SP")


# ---------------------------------------------------------------------------
# 4) Nomes, renda e projecoes
# ---------------------------------------------------------------------------


def test_nomes_das_regioes_sao_os_de_bairros_por_hex(top10_data: Path) -> None:
    ordenados = pilot._bairros_ordenados("SP", COD_SP)
    canonico = pilot.bairros_por_hex("SP", COD_SP)
    assert ordenados and set(ordenados) == set(canonico)
    for hex_id, lista in ordenados.items():
        assert lista[0] == canonico[hex_id], f"1o bairro de {hex_id} difere do mapa municipal"

    nomes = {
        v["hex_id"]: v["nome_regiao"]
        for v in _preenchidas(pilot.municipio("SP", "Sao Paulo")["recomendacao"])
    }
    # Mesmo bairro dominante dentro do Top 10: cada um leva o seu 2o bairro.
    assert nomes[SP["mv_a"]] == "Pinheiros / Jardins"
    assert nomes[SP["mv_b"]] == "Pinheiros / Vila Madalena"
    assert nomes[SP["mv_c"]] == canonico[SP["mv_c"]] == "Moema"
    assert nomes[SP["pr_c"]] == "Butantã"
    assert nomes[SP["mv_d"]] is None, "hexagono sem setor: sem nome (o front mostra o municipio)"
    # E o passo 5 titula pelo mesmo nome (ou pelo municipio, quando falta).
    itens = {i["hex_id"]: i for i in pilot.municipio("SP", "Sao Paulo")["passos"][4]["itens"]}
    assert itens[SP["mv_a"]]["titulo"] == "Pinheiros / Jardins"
    assert itens[SP["mv_d"]]["titulo"] == "Sao Paulo"


def test_paridade_de_nomes_com_cnefe_e_cascata(top10_data: Path) -> None:
    """A paridade `_bairros_ordenados` x `bairros_por_hex` nos caminhos que o dado real usa:
    setor sem `nome_bairro` (cai no distrito, pela cascata) e bairro reescrito pelo CNEFE
    (DEC-076). Sem isto, `_bairros_ordenados` podia perder o CNEFE ou a cascata e o Top 10
    mostrar outro nome que o mapa e a ficha para o mesmo hexagono."""
    setores = _setores_sp()
    lat, lng = h3.cell_to_latlng(SP["mv_d"])
    setores.loc[len(setores)] = {
        "nome_bairro": None,
        "nome_subdistrito": None,
        "nome_distrito": "Vila Mariana",
        "nome_municipio": "São Paulo",
        "bbox_minx": lng - 0.001,
        "bbox_miny": lat - 0.001,
        "bbox_maxx": lng + 0.001,
        "bbox_maxy": lat + 0.001,
        "pop_total_setor_2022": 7000.0,
    }
    setores["cod_setor"] = [f"3550308050{i:05d}" for i in range(len(setores))]
    geo = top10_data / "outputs" / "setores_censitarios_2022_geo" / "uf=SP"
    setores.to_parquet(geo / f"cod_municipio={COD_SP}" / "part-000.parquet")
    idx_moema = int(setores.index[setores["nome_bairro"] == "Moema"][0])
    cnefe = top10_data / "staging" / "bairro_cnefe_setor" / "uf=SP"
    cnefe.mkdir(parents=True)
    pd.DataFrame(
        {
            "cod_setor": [setores.loc[idx_moema, "cod_setor"]],
            "bairro_cnefe": ["JARDIM PAULISTANO"],
            "classe": ["BAIRRO"],
        }
    ).to_parquet(cnefe / "part-000.parquet")
    _clear_caches()

    canonico = pilot.bairros_por_hex("SP", COD_SP)
    ordenados = pilot._bairros_ordenados("SP", COD_SP)
    # Anti-vacuidade: a cascata e o CNEFE de fato mudaram nomes nesta fixture.
    assert canonico[SP["mv_d"]] == "Vila Mariana", "fixture: a cascata deveria nomear mv_d"
    assert canonico[SP["mv_c"]] != "Moema", "fixture: o CNEFE deveria reescrever mv_c"
    assert set(ordenados) == set(canonico)
    for hex_id, lista in ordenados.items():
        assert lista[0] == canonico[hex_id], hex_id
    # E a rota usa os mesmos nomes.
    nomes = {
        v["hex_id"]: v["nome_regiao"]
        for v in _preenchidas(pilot.municipio("SP", "Sao Paulo")["recomendacao"])
    }
    assert nomes[SP["mv_d"]] == "Vila Mariana"
    assert nomes[SP["mv_c"]] == canonico[SP["mv_c"]]


def test_card_e_top10_mostram_a_mesma_renda(top10_data: Path) -> None:
    """A renda da vaga e' a MESMA do card do hexagono (mesma conta, mesmo k da malha)."""
    for payload in (pilot.municipio("SP", "Sao Paulo"), pilot.uf_view("SP")):
        card = {h["id"]: h["renda_dom"] for h in payload["hexes"]}
        vagas = _preenchidas(payload["recomendacao"])
        assert vagas
        for vaga in vagas:
            assert vaga["renda_domiciliar"] is not None
            assert round(vaga["renda_domiciliar"]) == card[vaga["hex_id"]], vaga["hex_id"]


def test_card_e_top10_mostram_a_mesma_renda_com_a_malha_e3(top10_e3: Path) -> None:
    """O mesmo, com as colunas da malha (E3) no artefato: a renda sai `malha x F_dom` nas
    duas superficies -- e nao a formula municipal numa e a da malha na outra."""
    payload = pilot.municipio("SP", "Sao Paulo")
    card = {h["id"]: h["renda_dom"] for h in payload["hexes"]}
    vagas = {v["hex_id"]: v for v in _preenchidas(payload["recomendacao"])}
    for hex_id, vaga in vagas.items():
        assert round(vaga["renda_domiciliar"]) == card[hex_id], hex_id
    # Anti-vacuidade: a vaga calibrada leu a MALHA (nao a formula municipal de antes).
    esperado = CALIB_ALTA * 4.0 * fator("SP", "domiciliar")
    assert vagas[SP["mv_a"]]["renda_domiciliar"] == pytest.approx(esperado)
    assert vagas[SP["mv_a"]]["renda_municipal"] is False


def test_card_e_top10_mostram_a_mesma_renda_com_a_malha_e3_so_no_staging(
    top10_e3_staging: Path,
) -> None:
    """O caso de PRODUCAO entre a troca da malha no staging e a remontagem do enriquecido: as
    colunas da E3 so' na malha do staging. O modulo da recomendacao as anexa de la (a politica
    de `renda.hex._com_colunas_malha`, a mesma do PDF); o card, o tooltip e a ficha tem de ler
    a MESMA malha -- senao a Mata Virgem "acima do piso de renda" abre na ficha com a formula
    municipal, abaixo do piso (74 de 74 vagas divergiam no snapshot de 18/10 com o staging da
    VPS)."""
    enr = top10_e3_staging / "outputs" / "hexagonos_dashboard_enriquecido"
    colunas_do_artefato = set(pd.read_parquet(enr / "uf=SP" / "part-0.parquet").columns)
    assert not set(COLS_RENDA_MALHA) & colunas_do_artefato, "fixture: a E3 so' no staging"
    dom = CALIB_ALTA * 4.0 * fator("SP", "domiciliar")
    pc = CALIB_ALTA * 4.0 / 2.8 * fator("SP", "per_capita")
    for payload in (pilot.municipio("SP", "Sao Paulo"), pilot.uf_view("SP")):
        card = {h["id"]: h for h in payload["hexes"]}
        vagas = {v["hex_id"]: v for v in _preenchidas(payload["recomendacao"])}
        assert vagas
        for hex_id, vaga in vagas.items():
            assert round(vaga["renda_domiciliar"]) == card[hex_id]["renda_dom"], hex_id
        # Anti-vacuidade: os dois leram a MALHA do staging, e nao a formula municipal.
        assert vagas[SP["mv_a"]]["renda_domiciliar"] == pytest.approx(dom)
        assert card[SP["mv_a"]]["renda_dom"] == round(dom)
        # A per capita do tooltip le a mesma malha (a coluna per capita da E3).
        assert card[SP["mv_a"]]["renda"] == round(pc)
    # Oportunidades (o imovel no hexagono) mostra o numero do tooltip do MESMO hexagono.
    ids = [SP["mv_a"], SP["mv_c"]]
    saida = pilot._op_renda_pc_por_hex(pd.DataFrame({"hex_id": ids, "uf": ["SP"] * len(ids)}))
    linhas = pilot.carregar_uf("SP").set_index("hex_id", drop=False)
    for idx, hex_id in enumerate(ids):
        assert saida[idx] == pilot._renda_per_capita_hex(linhas.loc[hex_id]), hex_id
    assert saida[0] == round(pc)


def test_malha_anterior_a_e3_no_staging_nao_muda_o_card(top10_data: Path) -> None:
    """Malha SEM as colunas da E3 (a de antes do deploy de dado): nada a anexar, e o card
    segue na formula municipal de sempre -- a mesma que o modulo usa nesse caso."""
    df = pilot.carregar_uf("SP")
    assert not set(COLS_RENDA_MALHA) & set(df.columns)
    vaga = next(
        v
        for v in _preenchidas(pilot.municipio("SP", "Sao Paulo")["recomendacao"])
        if v["hex_id"] == SP["mv_a"]
    )
    linha = df.set_index("hex_id", drop=False).loc[SP["mv_a"]]
    assert pilot._renda_domiciliar_hex(linha) == round(vaga["renda_domiciliar"])
    assert vaga["renda_domiciliar"] != pytest.approx(CALIB_ALTA * 4.0 * fator("SP", "domiciliar"))


def test_malha_ilegivel_nao_derruba_o_mapa(top10_data: Path) -> None:
    """Malha corrompida no staging: o card cai na formula municipal (registra no stderr), o
    Top 10 fica indisponivel e a rota responde -- nunca 500 (spec, "sem k")."""
    (top10_data / "staging" / renda_hex.CENSO_MALHA_PARQUET).write_bytes(b"nao e parquet")
    _clear_caches()
    payload = pilot.municipio("SP", "Sao Paulo")
    assert payload["hexes"], "o mapa segue"
    assert payload["recomendacao"]["renda"]["disponivel"] is False


def test_projecoes_trazem_as_colunas_da_regua(top10_data: Path) -> None:
    exigidas = {
        *COLUNAS_OBRIGATORIAS,
        "cod_municipio",
        "nome_municipio",
        "lat",
        "lng",
        *COLS_RENDA_LEITURA,
        *COLS_RENDA_MALHA,
    }
    assert exigidas <= set(pilot._COLS_DESEJADAS)
    assert exigidas <= set(pilot._COLS_RECOMENDACAO)
    assert "uf" in pilot._COLS_RECOMENDACAO, "o recorte Brasil le a UF da chave hive"
    df = pilot.carregar_uf("SP")
    assert {"uf", "fonte_pop_hex_base"} <= set(df.columns)


def test_uma_funcao_so_chama_o_modulo() -> None:
    fonte = inspect.getsource(pilot)
    assert fonte.count("montar_recomendacao(") == 1, "a conta de onde expandir mora num lugar so'"
    assert "montar_recomendacao(" in inspect.getsource(pilot._recomendacao_do_recorte)


# ---------------------------------------------------------------------------
# 5) Cache do Brasil e subida
# ---------------------------------------------------------------------------


def test_brasil_fica_em_cache(top10_data: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    chamadas: list[str] = []
    original = pilot.montar_recomendacao

    def contar(*args, **kwargs):
        chamadas.append(kwargs["recorte"].nivel)
        return original(*args, **kwargs)

    monkeypatch.setattr(pilot, "montar_recomendacao", contar)
    primeira = pilot.hexagonos()
    assert pilot.hexagonos() == primeira
    assert chamadas == ["brasil"], "o Top 10 do Brasil foi recalculado sem o dado mudar"
    # A rota devolve COPIA: mexer na resposta nao contamina a proxima.
    primeira["recomendacao"]["mata_virgem"]["vagas"].clear()
    assert len(pilot.hexagonos()["recomendacao"]["mata_virgem"]["vagas"]) == 5

    # Trocar um arquivo da base muda a identidade e recalcula.
    arquivo = (
        top10_data / "outputs" / "hexagonos_dashboard_enriquecido" / "uf=TO" / "part-0.parquet"
    )
    st = arquivo.stat()
    os.utime(arquivo, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
    pilot.hexagonos()
    assert chamadas == ["brasil", "brasil"]


def test_brasil_recalcula_quando_a_regua_ou_a_malha_muda(
    top10_data: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A chave do cache do Brasil e' a VERSAO DA REGUA e a identidade do dado (spec 1.6), nao
    so' as particoes: com outra regua (versao nova, ou fixada por env + `limpar_cache`) o
    Brasil nao pode seguir servindo o Top 10 da regua antiga enquanto `/api/uf` e
    `/api/municipio` ja usam a nova; e a malha com o carimbo k muda a renda."""
    chamadas: list[str] = []
    original = pilot.montar_recomendacao

    def contar(*args, **kwargs):
        chamadas.append(kwargs["recorte"].nivel)
        return original(*args, **kwargs)

    monkeypatch.setattr(pilot, "montar_recomendacao", contar)
    regra = pilot._regra_recomendacao()
    assert pilot.hexagonos()["recomendacao"]["regra"]["mata_virgem"]["residual_min"] == 2000.0
    outra = dataclasses.replace(
        regra, mata_virgem=dataclasses.replace(regra.mata_virgem, residual_min=3000.0)
    )
    monkeypatch.setattr(pilot, "_regra_recomendacao", lambda: outra)
    corpo = pilot.hexagonos()
    assert chamadas == ["brasil", "brasil"], "o Brasil seguiu com o Top 10 da regua antiga"
    assert corpo["recomendacao"]["regra"]["mata_virgem"]["residual_min"] == 3000.0
    # E a mesma regua com a MESMA identidade nao recalcula...
    pilot.hexagonos()
    assert chamadas == ["brasil", "brasil"]
    # ...mas a malha do staging (carimbo k e colunas da E3) faz parte da identidade.
    malha = top10_data / "staging" / renda_hex.CENSO_MALHA_PARQUET
    st = malha.stat()
    os.utime(malha, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
    pilot.hexagonos()
    assert chamadas == ["brasil", "brasil", "brasil"]


def test_brasil_sai_do_indisponivel_quando_a_malha_chega(top10_sem_k: Path) -> None:
    """A malha com o carimbo k chega ao staging DEPOIS da subida: o Top 10 do Brasil nao pode
    ficar preso em "indisponivel" ate um restart."""
    assert pilot.hexagonos()["recomendacao"]["renda"]["disponivel"] is False
    todos = [*SP.values(), *CAMP.values(), TO]
    pd.DataFrame(
        {"hex_id": todos, "metodo_calibracao_renda_malha": [K_CARIMBO] * len(todos)}
    ).to_parquet(top10_sem_k / "staging" / renda_hex.CENSO_MALHA_PARQUET)
    bloco = pilot.hexagonos()["recomendacao"]
    assert bloco["renda"]["disponivel"] is True
    assert _preenchidas(bloco)


def test_coluna_obrigatoria_ausente_falha_alto(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Projecao ou artefato sem `fonte_pop_hex_base`: o modulo levanta `ValueError` nomeando a
    coluna, e a rota NAO pode cair em silencio no caminho legado (sem o bloco, com a fila pelo
    indice de praca) -- isso e' bug de projecao, nao "sem recomendacao" (spec 1.2)."""
    _montar(tmp_path, monkeypatch)
    enr = tmp_path / "outputs" / "hexagonos_dashboard_enriquecido"
    _particao_sp(saturado=False).drop(columns=["fonte_pop_hex_base"]).to_parquet(
        enr / "uf=SP" / "part-0.parquet"
    )
    _particao_to().drop(columns=["fonte_pop_hex_base"]).to_parquet(enr / "uf=TO" / "part-0.parquet")
    _clear_caches()
    try:
        for chamada in (
            lambda: pilot.municipio("SP", "Sao Paulo"),
            lambda: pilot.uf_view("SP"),
            lambda: pilot.hexagonos(uf="SP"),
            lambda: pilot.hexagonos(uf="SP", municipio="Campinas"),
            lambda: pilot.hexagonos(),
        ):
            with pytest.raises(ValueError, match="fonte_pop_hex_base"):
                chamada()
    finally:
        _clear_caches()


def test_subida_da_recomendacao(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _point_app_at(monkeypatch, tmp_path)  # staging vazio: sem o carimbo k
    # O pais da instancia, nao o do perfil do ambiente (que o teste nao controla).
    monkeypatch.setattr(subida_mod, "carregar_regra", lambda: pilot.carregar_regra("BR"))

    # dev/teste: so' WARNING, e a versao da regua no log.
    monkeypatch.delenv("MOTOR_DATA_DIR", raising=False)
    with caplog.at_level(logging.INFO):
        pilot._init_recomendacao_no_boot()
    assert any(
        r.levelno == logging.WARNING and "k da malha" in r.getMessage() for r in caplog.records
    )
    assert "regua versao=2026-10_v1" in caplog.text

    # producao (`MOTOR_DATA_DIR`) sem o carimbo k: a SUBIDA cai.
    monkeypatch.setenv("MOTOR_DATA_DIR", str(tmp_path))
    with pytest.raises(InsumoRendaInvalido):
        pilot._init_recomendacao_no_boot()

    # pais sem regua: so' o log, nada a validar.
    caplog.clear()
    monkeypatch.setattr(pilot, "_regra_recomendacao", lambda: None)

    def nao_chamar(*_a, **_k):  # pragma: no cover - so' dispara se a guarda falhar
        raise AssertionError("pais sem regua nao valida o carimbo k")

    monkeypatch.setattr(pilot, "_validar_recomendacao_na_subida", nao_chamar)
    with caplog.at_level(logging.INFO):
        pilot._init_recomendacao_no_boot()
    assert "sem regua" in caplog.text
    _clear_caches()
