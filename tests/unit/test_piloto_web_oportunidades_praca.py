"""Faturamento projetado da aba de oportunidades pelo MODELO DE PRACA (DEC-086).

O imovel com as entradas da isocrona no lote noturno (`entradas_c10.parquet`, ao lado do
`viaveis.parquet`) recebe o p50 do modelo do simulador, com a faixa p10-p90; sem elas, a
curva de densidade de antes. A lista e' relida quando a lista, as entradas ou os
coeficientes mudam -- sem `restart`.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import pytest

from motor_expansao.dimensionamento import viabilidade_v2 as v2
from motor_expansao.dimensionamento.config import V2_TETO_M2
from motor_expansao.dimensionamento.demanda_v2 import EntradasV2, prever_faturamento_v2
from motor_expansao.dimensionamento.entradas_oportunidades import ARQUIVO_SAIDA, COLUNAS

from .dimensionamento.test_viabilidade_v2 import COEF_FICTICIO, _gravar

_REPO = Path(__file__).resolve().parents[2]
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import app as pilot_app  # noqa: E402

ALUNOS_DENSIDADE = 1_000.0
ENT = {"pop_c10": 300_000.0, "dom_c10": 100_000.0, "renda_pc_c10": 1_800.0}


def _imovel(iid: str, lat: float, lng: float, area: float = 1_500.0) -> dict[str, object]:
    return {
        "imovel_id": iid, "titulo": f"Imovel {iid}", "tipo": "galpao", "uf": "SP",
        "municipio": "Sao Paulo", "area_relevante_m2": area, "preco_aluguel": 30_000.0,
        "hex_id": f"87{iid}ffffff", "m1_residual_fitness": 50.0, "m1_residual_total": 100.0,
        "status": "ativo", "latitude": lat, "longitude": lng,
    }


def _entradas(caminho: Path, linhas: list[dict[str, object]]) -> None:
    df = pd.DataFrame([{c: linha.get(c) for c in COLUNAS} for linha in linhas])
    df.to_parquet(caminho)


@pytest.fixture
def cenario(monkeypatch, tmp_path):
    """Lista e entradas no `tmp_path`, coeficientes FICTICIOS e a densidade fixa em 1.000."""
    monkeypatch.delenv("MOTOR_VIABILIDADE_V2", raising=False)
    monkeypatch.delenv("MOTOR_OPORTUNIDADES_ENTRADAS_PATH", raising=False)
    coef_path = _gravar(tmp_path, COEF_FICTICIO)
    monkeypatch.setattr(v2, "caminho_coeficientes", lambda: coef_path)
    v2.limpar_cache()
    lista = tmp_path / "viaveis.parquet"
    monkeypatch.setattr(pilot_app, "OPORTUNIDADES_PATH", lista)
    monkeypatch.setattr(pilot_app, "_OPORTUNIDADES_CACHE", None)
    monkeypatch.setattr(pilot_app, "_OPORTUNIDADES_CHAVE", None)
    monkeypatch.setattr(pilot_app, "DOSSIES_DIR", tmp_path / "sem-dossies")
    monkeypatch.setattr(pilot_app, "_alunos_p50_por_m2", lambda m2: ALUNOS_DENSIDADE if m2 else None)

    def _montar(imoveis, entradas=None):
        pd.DataFrame(imoveis).to_parquet(lista)
        if entradas is not None:
            _entradas(lista.with_name(ARQUIVO_SAIDA), entradas)
        return lista

    yield _montar
    pilot_app._OPORTUNIDADES_CACHE = None
    pilot_app._OPORTUNIDADES_CHAVE = None
    v2.limpar_cache()


def _itens() -> dict[str, dict]:
    return {o["id"]: o for o in pilot_app.api_oportunidades(limite=3000)["itens"]}


def _ok(lat: float, lng: float) -> dict[str, object]:
    return {"lat5": round(lat, 5), "lng5": round(lng, 5), "status": "ok", **ENT}


def test_imovel_com_entradas_usa_o_modelo_do_simulador(cenario):
    cenario([_imovel("a", -23.5, -46.6)], [_ok(-23.5, -46.6)])
    item = _itens()["a"]
    coef = v2.carregar_coeficientes()
    prev = prever_faturamento_v2(EntradasV2(m2=1_500.0, studios=0, **ENT), coef)
    assert item["fat_fonte"] == "praca"
    assert item["fat_proj"] == pytest.approx(prev.fat_p50, abs=0.01)
    assert item["fat_p10"] == pytest.approx(prev.fat_p10, abs=0.01)
    assert item["fat_p90"] == pytest.approx(prev.fat_p90, abs=0.01)
    assert item["fat_extrapolacao"] is False and item["m2_modelo"] == 1_500.0


def test_alunos_do_modelo_sao_a_conversao_da_sugestao_do_simulador(cenario):
    cenario([_imovel("a", -23.5, -46.6)], [_ok(-23.5, -46.6)])
    item = _itens()["a"]
    corpo = v2.DemandaV2In(lat=-23.5, lng=-46.6, m2=1_500.0)
    sug = v2.montar_sugestao_v2(corpo, coef=v2.carregar_coeficientes(), **ENT)
    assert item["alunos_p50"] == pytest.approx(sug["alunos"]["p50"], abs=0.1)


def test_sem_entrada_ou_com_falha_permanente_cai_na_curva_de_densidade(cenario):
    falha = {"lat5": -22.9, "lng5": -43.2, "status": "sem_isocrona", "motivo": "Sem via."}
    cenario(
        [_imovel("com", -23.5, -46.6), _imovel("sem", -19.9, -43.9), _imovel("falha", -22.9, -43.2)],
        [_ok(-23.5, -46.6), falha],
    )
    itens = _itens()
    assert itens["com"]["fat_fonte"] == "praca"
    for iid in ("sem", "falha"):
        assert itens[iid]["fat_fonte"] == "densidade"
        assert itens[iid]["fat_proj"] == pytest.approx(ALUNOS_DENSIDADE * pilot_app._ticket_proj_mensal())
        assert itens[iid]["fat_p10"] is None and itens[iid]["fat_p90"] is None
        assert itens[iid]["fat_extrapolacao"] is None and itens[iid]["m2_modelo"] is None


def test_chave_da_v2_desligada_poe_a_lista_inteira_na_densidade(cenario, monkeypatch):
    cenario([_imovel("a", -23.5, -46.6)], [_ok(-23.5, -46.6)])
    monkeypatch.setenv("MOTOR_VIABILIDADE_V2", "0")
    assert _itens()["a"]["fat_fonte"] == "densidade"


def test_area_acima_do_teto_conta_so_ate_o_teto_no_modelo(cenario):
    cenario(
        [_imovel("grande", -23.5, -46.6, area=3_000.0), _imovel("teto", -23.5, -46.6, area=V2_TETO_M2)],
        [_ok(-23.5, -46.6)],
    )
    itens = _itens()
    assert itens["grande"]["m2_modelo"] == V2_TETO_M2
    assert itens["grande"]["fat_proj"] == pytest.approx(itens["teto"]["fat_proj"], abs=0.01)
    assert itens["grande"]["area"] == 3_000, "a area exibida segue a do anuncio"


def test_entradas_que_chegam_depois_entram_sem_restart(cenario):
    lista = cenario([_imovel("a", -23.5, -46.6)])
    assert _itens()["a"]["fat_fonte"] == "densidade"
    _entradas(lista.with_name(ARQUIVO_SAIDA), [_ok(-23.5, -46.6)])
    assert _itens()["a"]["fat_fonte"] == "praca", "o lote noturno vale sem reiniciar o site"


def test_trocar_a_lista_nao_exige_mais_restart(cenario):
    lista = cenario([_imovel("a", -23.5, -46.6)])
    assert set(_itens()) == {"a"}
    pd.DataFrame([_imovel("a", -23.5, -46.6), _imovel("b", -19.9, -43.9)]).to_parquet(lista)
    st = os.stat(lista)
    os.utime(lista, ns=(st.st_atime_ns, st.st_mtime_ns + 2_000_000_000))
    assert set(_itens()) == {"a", "b"}


def test_sem_mudanca_devolve_o_mesmo_cache(cenario):
    cenario([_imovel("a", -23.5, -46.6)], [_ok(-23.5, -46.6)])
    primeira = pilot_app._carregar_oportunidades()
    assert pilot_app._carregar_oportunidades() is primeira


def test_entradas_ilegiveis_nao_derrubam_a_lista(cenario):
    lista = cenario([_imovel("a", -23.5, -46.6)])
    lista.with_name(ARQUIVO_SAIDA).write_bytes(b"nao e parquet")
    assert _itens()["a"]["fat_fonte"] == "densidade"


def test_lista_pela_metade_no_meio_do_envio_segue_a_anterior(cenario):
    """O envio é `scp` por cima do arquivo (não atômico). Uma leitura no meio dele falha:
    a lista ANTERIOR segue servida, e a próxima chamada tenta de novo — sem guardar a
    assinatura do arquivo quebrado como se fosse a da lista anterior."""
    lista = cenario([_imovel("a", -23.5, -46.6)])
    assert set(_itens()) == {"a"}
    lista.write_bytes(b"PAR1 pela metade")
    assert set(_itens()) == {"a"}, "a anterior segue servida"
    pd.DataFrame([_imovel("a", -23.5, -46.6), _imovel("b", -19.9, -43.9)]).to_parquet(lista)
    st = os.stat(lista)
    os.utime(lista, ns=(st.st_atime_ns, st.st_mtime_ns + 2_000_000_000))
    assert set(_itens()) == {"a", "b"}


def test_primeira_leitura_quebrada_sobe_o_erro_como_antes(cenario):
    lista = cenario([_imovel("a", -23.5, -46.6)])
    lista.write_bytes(b"nao e parquet")
    # O pyarrow levanta `ArrowInvalid`, que é um `ValueError`.
    with pytest.raises((ValueError, OSError)):
        pilot_app._carregar_oportunidades()
    assert pilot_app._OPORTUNIDADES_CACHE is None and pilot_app._OPORTUNIDADES_CHAVE is None
