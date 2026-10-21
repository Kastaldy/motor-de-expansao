"""E3: as ROTAS do piloto carregam as colunas da renda da malha ate a conta do hexagono.

`test_renda_hex_malha_e3.py` trava a formula (`_renda_*_hex` com a linha montada a mao). O que
ele nao alcanca e a PASSAGEM das colunas: cada superficie le o hexagono por uma lista propria de
colunas (`_COLS_DESEJADAS` no tooltip/ficha via `carregar_uf`, `_COLS_NACIONAL` em
`/api/hexagonos`, a lista de `_op_renda_pc_por_hex` em Oportunidades) ou por um join proprio
(`_rede_territorio`, a ficha da rede na Executiva, que le o artefato de MERCADO, sem as colunas).
Se uma lista perder a coluna, a superficie volta em silencio a formula municipal e mostra para o
MESMO hexagono um numero diferente do tooltip -- a familia de defeito da DEC-038. Aqui cada rota
le um artefato de brinquedo e a renda tem de sair `coluna_malha x F`, igual entre superficies.

Chama as funcoes de rota DIRETO (sem TestClient), como o resto da suite do piloto.
"""

from __future__ import annotations

import sys
from pathlib import Path

import h3
import pandas as pd
import pytest

_SERVER = Path(__file__).resolve().parents[2] / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import app as pilot  # noqa: E402

from motor_expansao.renda import (  # noqa: E402
    COL_RENDA_DOM_MALHA,
    COL_RENDA_PC_MALHA,
    COLS_RENDA_MALHA,
    fator,
)
from motor_expansao.renda import hex as renda_hex  # noqa: E402
from tests.unit.test_piloto_web_endpoints import (  # noqa: E402
    _clear_caches,
    _montar_base_nacional,
    _nacional_duas_ufs,
    _point_app_at,
)

CALIBRADA = "renda_per_capita_setor_2022_calibrada"


def _dom_malha(i: int) -> float:
    return 5000.0 + 37.0 * i


def _pc_malha(i: int) -> float:
    return 2000.0 + 11.0 * i


@pytest.fixture
def base_e3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Enriquecido nacional de brinquedo: SP COM as colunas da malha, TO sem valor nelas."""
    dados = _nacional_duas_ufs()
    sp = dados["SP"].reset_index(drop=True)
    sp[COL_RENDA_DOM_MALHA] = [_dom_malha(i) for i in range(len(sp))]
    sp[COL_RENDA_PC_MALHA] = [_pc_malha(i) for i in range(len(sp))]
    to = dados["TO"].copy()
    to[COL_RENDA_DOM_MALHA] = float("nan")  # hexagono sem setor: formula municipal
    to[COL_RENDA_PC_MALHA] = float("nan")
    _montar_base_nacional(
        tmp_path / "outputs" / "hexagonos_dashboard_enriquecido", {"SP": sp, "TO": to}
    )
    staging = tmp_path / "staging"
    staging.mkdir()
    pd.DataFrame(
        {"hex_id": ["x"], "metodo_calibracao_renda_malha": ["multiplicativo_global_k=1.1"]}
    ).to_parquet(staging / renda_hex.CENSO_MALHA_PARQUET)  # o `k` do carimbo
    _point_app_at(monkeypatch, tmp_path)
    monkeypatch.setattr(pilot, "MERCADO_PARQUET", staging / "hexagonos_mercado_mapeado.parquet")
    yield tmp_path
    _clear_caches()


def _esperado_sp() -> dict[str, tuple[int, int]]:
    sp = _nacional_duas_ufs()["SP"].reset_index(drop=True)
    return {
        h: (round(_dom_malha(i) * fator("SP", "domiciliar")), round(_pc_malha(i) * fator("SP", "per_capita")))
        for i, h in enumerate(sp["hex_id"])
    }


def test_as_listas_de_colunas_pedem_a_malha() -> None:
    # Barato e direto: a lista e o ponto onde a coluna se perde sem erro.
    assert set(COLS_RENDA_MALHA) <= set(pilot._COLS_DESEJADAS)
    assert set(COLS_RENDA_MALHA) <= set(pilot._COLS_NACIONAL)


def test_tooltip_e_ficha_via_carregar_uf(base_e3: Path) -> None:
    df = pilot.carregar_uf("SP")
    assert set(COLS_RENDA_MALHA) <= set(df.columns)
    esperado = _esperado_sp()
    for _, linha in df.iterrows():
        dom, pc = esperado[linha["hex_id"]]
        assert pilot._renda_domiciliar_hex(linha) == dom
        assert pilot._renda_per_capita_hex(linha) == pc


def test_ranking_nacional_usa_a_malha_e_cai_na_municipal_sem_ela(base_e3: Path) -> None:
    itens = pilot.hexagonos(limite=500)["itens"]
    esperado = _esperado_sp()
    vistos = {i["hex_id"]: i for i in itens}
    assert set(esperado) <= set(vistos), "fixture nao acendeu o ranking -- o teste nao provaria nada"
    for hid, (_, pc) in esperado.items():
        assert vistos[hid]["renda"] == pc
    to = next(i for i in itens if i["uf"] == "TO")
    k = renda_hex.k_calibracao_renda(pilot.STAGING_DIR)
    assert to["renda"] == round(renda_hex.renda_per_capita_hex(2600.0 / k, "TO", to["cod_municipio"]))


def test_oportunidades_usa_a_malha(base_e3: Path) -> None:
    esperado = _esperado_sp()
    ids = sorted(esperado)
    df = pd.DataFrame({"hex_id": ids, "uf": ["SP"] * len(ids)})
    saida = pilot._op_renda_pc_por_hex(df)
    for idx, hid in enumerate(ids):
        assert saida[idx] == esperado[hid][1]


def test_mesmo_hexagono_mesmo_numero_entre_superficies(base_e3: Path) -> None:
    df = pilot.carregar_uf("SP").set_index("hex_id", drop=False)
    nacional = {i["hex_id"]: i["renda"] for i in pilot.hexagonos(limite=500)["itens"]}
    ids = sorted(_esperado_sp())
    oport = pilot._op_renda_pc_por_hex(pd.DataFrame({"hex_id": ids, "uf": ["SP"] * len(ids)}))
    for idx, hid in enumerate(ids):
        tooltip = pilot._renda_per_capita_hex(df.loc[hid])
        assert tooltip == nacional[hid] == oport[idx]


# --------------------------------------------------------------------------------
# Ficha da rede (Executiva): le o artefato de MERCADO e junta a malha do staging
# --------------------------------------------------------------------------------


def test_ficha_da_rede_junta_a_malha_ao_artefato_de_mercado(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _point_app_at(monkeypatch, tmp_path)
    staging = tmp_path / "staging"
    staging.mkdir()
    centro = h3.latlng_to_cell(-23.55, -46.63, 7)
    disco = sorted(h3.grid_disk(centro, 1))
    pd.DataFrame(
        {
            "hex_id": disco,
            "uf": "SP",
            "cod_municipio": "3550308",
            "renda_per_capita": 2500.0,
            CALIBRADA: 2600.0,
            "pop_total_setor_2022": 9000.0,
        }
    ).to_parquet(staging / "hexagonos_mercado_mapeado.parquet")  # SEM as colunas da malha
    dom, pc = 5321.0, 1987.0
    pd.DataFrame(
        {
            "hex_id": disco,
            "metodo_calibracao_renda_malha": "multiplicativo_global_k=1.1",
            COL_RENDA_DOM_MALHA: dom,
            COL_RENDA_PC_MALHA: pc,
        }
    ).to_parquet(staging / renda_hex.CENSO_MALHA_PARQUET)

    lat, lng = h3.cell_to_latlng(centro)
    monkeypatch.setattr(
        pilot, "_rede_pontos", lambda: pd.DataFrame({"unidade_id": ["u1"], "lat": [lat], "lng": [lng]})
    )
    monkeypatch.setattr(pilot, "_rede_oferta_sem_estudio", lambda: None)
    monkeypatch.setattr(pilot, "_rede_ler_opcional", lambda *_a, **_k: None)
    monkeypatch.setattr(
        pilot.rede_inteligencia, "fatos_territoriais", lambda pontos, *_a: {"u1": {}}
    )
    try:
        fatos = pilot._rede_territorio.__wrapped__()
        assert fatos["u1"]["renda_domiciliar"] == round(dom * fator("SP", "domiciliar"))
        assert fatos["u1"]["renda_per_capita"] == round(pc * fator("SP", "per_capita"))

        # Sem o join (malha anterior a E3): a formula municipal, outro numero -- e o que o
        # teste acima pega se o bloco `faltam_malha` sumir.
        (staging / renda_hex.CENSO_MALHA_PARQUET).unlink()
        pd.DataFrame(
            {"hex_id": ["x"], "metodo_calibracao_renda_malha": ["multiplicativo_global_k=1.1"]}
        ).to_parquet(staging / renda_hex.CENSO_MALHA_PARQUET)
        _clear_caches()
        sem = pilot._rede_territorio.__wrapped__()
        assert sem["u1"]["renda_domiciliar"] != fatos["u1"]["renda_domiciliar"]
    finally:
        _clear_caches()
