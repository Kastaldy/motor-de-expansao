"""DEC-080 na API pública: `tipo_imovel` liga o card "Faixa de aluguel da região" do PDF."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from motor_expansao.api import service
from motor_expansao.api.schemas import AnalisarRequest
from motor_expansao.api.settings import Settings
from motor_expansao.dimensionamento.payload_viabilidade import ViabilidadeInputs


def _base(tmp_path: Path) -> Path:
    caminho = tmp_path / "viaveis.parquet"
    pd.DataFrame(
        [
            {"uf": "ES", "municipio": "Vitória", "tipo": "loja", "area_relevante_m2": 1000.0,
             "preco_aluguel": v * 1000.0, "status": "ativo"}
            for v in (10, 20, 30, 40, 50)
        ]
    ).to_parquet(caminho)
    from motor_expansao.api.routes import aluguel_referencia as rota

    rota._tabela.cache_clear()
    return caminho


def _montar(tmp_path, info, viab=None, tipo="loja", com_base=True):
    cfg = Settings(oportunidades_path=_base(tmp_path) if com_base else None)
    return service._info_imovel_com_aluguel(
        info, viab, tipo, "ES", {"nome_municipio": "VITORIA"}, cfg
    )


def test_schema_aceita_so_os_tres_tipos_brutos():
    assert AnalisarRequest(lat=-20.3, lng=-40.3, tipo_imovel="galpao").tipo_imovel == "galpao"
    try:
        AnalisarRequest(lat=-20.3, lng=-40.3, tipo_imovel="Galpão")
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("tipo fora do vocabulário deveria dar 422")


def test_card_com_aluguel_informado_compara_com_a_faixa(tmp_path):
    info = _montar(tmp_path, {"metragem_m2": 1500, "aluguel_pedido": 66000})
    assert info["tipo_imovel"] == "Comercial"
    bloco = info["aluguel_referencia"]
    assert (bloco["faixa_min"], bloco["faixa_max"]) == (30000, 60000)
    assert bloco["comparacao"] == "47% acima da mediana · 10% acima da faixa"


def test_so_viabilidade_cria_a_pagina_com_o_card(tmp_path):
    viab = ViabilidadeInputs(m2=1500, aluguel=45000, demanda=800)
    info = _montar(tmp_path, None, viab)
    assert info["aluguel_referencia"]["comparacao"] == "na mediana · dentro da faixa"


def test_bloco_do_cliente_e_descartado(tmp_path):
    forjado = {"faixa_min": 1, "faixa_max": 2, "rs_m2_p25": 1, "rs_m2_p75": 2}
    info = _montar(tmp_path, {"metragem_m2": 1500, "aluguel_referencia": forjado}, com_base=False)
    assert "aluguel_referencia" not in info


def test_sem_info_nem_viabilidade_nada_muda(tmp_path):
    assert _montar(tmp_path, None) is None
