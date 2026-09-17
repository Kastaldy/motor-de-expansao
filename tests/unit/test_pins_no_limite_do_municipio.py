"""Pins presos ao MUNICIPIO quando o perfil zera a margem (emenda a DEC-035).

A DEC-035 desenha, alem dos pins nos hexagonos do municipio, tudo o que cai no bbox dos
centroides + `PIN_MARGEM_M` — a margem e' o raio de 2 km da pressao. Na Argentina isso
vaza: as comunas de CABA sao pequenas e coladas, e abrir a Comuna 1 desenhava concorrente
das comunas vizinhas. A margem passa a vir do perfil (`reguas.pin_margem_m`); a AR declara
0, e o Brasil, sem o campo, continua em 2000 m.

O que esta suite prova:

  * **Com margem 0, as tres camadas ficam no municipio** — concorrentes, independentes e
    unidades de rede. Na fixture sintetica Campinas esta a ~1,5 km de Sao Paulo, ou seja,
    DENTRO da margem de 2 km: e' exatamente o caso que vazava.
  * **A margem e' lida na hora da chamada.** Um default de argumento congelado no `def`
    ignoraria o perfil sem erro nenhum; o monkeypatch no modulo e' o que prova a leitura.
  * **Os pins de dentro continuam chegando** — zerar a margem nao pode esvaziar o recorte.

O lado brasileiro (margem 2000 m, vizinho dentro do raio ENTRA) segue provado, sem edicao,
em `test_piloto_web_independentes.py` e `test_piloto_web_redes.py`.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from tests.unit.test_piloto_web_endpoints import (  # noqa: F401
    pilot,
    synth_data,
)
from tests.unit.test_piloto_web_independentes import _nomeadas
from tests.unit.test_piloto_web_redes import _redes

HEX_SP = [f"87a0{h}0000000ffff" for h in range(4)]


def _concorrentes() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "rede": "smart_fit",
                "nome_unidade": f"Smart Fit {i}",
                "lat": -23.55 + 0.001 * i,
                "lng": -46.63,
                "hex_id_res7": HEX_SP[i],
                "status_registro": "valido",
            }
            for i in range(2)
        ]
    )


@pytest.fixture
def pins_em_sp(synth_data: Path) -> Path:  # noqa: F811
    """As tres camadas com TODOS os itens nos hexagonos de Sao Paulo."""
    staging = synth_data / "staging"
    staging.mkdir(parents=True, exist_ok=True)
    _concorrentes().to_parquet(staging / "concorrentes_mapeados.parquet", index=False)
    _nomeadas().to_parquet(staging / "vulnerabilidade_ma_nomeadas.parquet", index=False)
    _redes().to_parquet(staging / "vulnerabilidade_ma_redes.parquet", index=False)
    pilot.limpar_caches()
    pilot.carregar_independentes.cache_clear()
    pilot.carregar_redes.cache_clear()
    return synth_data


@pytest.fixture
def margem_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pilot, "PIN_MARGEM_M", 0.0)


def _muni(nome: str) -> dict:
    return pilot.municipio("SP", nome)


def test_premissa_com_a_margem_de_2km_o_vizinho_ENTRA(pins_em_sp: Path) -> None:
    """Sem esta premissa os testes de margem zero passariam por acidente de fixture."""
    dados = _muni("Campinas")
    assert dados["pins"]["concorrentes"]
    assert dados["independentes"]["total"] > 0


def test_margem_zero_concorrentes_e_redes_ficam_no_municipio(
    pins_em_sp: Path, margem_zero: None
) -> None:
    # Na mesma lista `pins.concorrentes` vivem as bandeiras do funil E as unidades de rede.
    assert _muni("Campinas")["pins"]["concorrentes"] == []


def test_margem_zero_independentes_ficam_no_municipio(
    pins_em_sp: Path, margem_zero: None
) -> None:
    bloco = _muni("Campinas")["independentes"]
    assert bloco["total"] == 0
    assert bloco["itens"] == []


def test_margem_zero_mantem_os_pins_de_dentro(pins_em_sp: Path, margem_zero: None) -> None:
    dados = _muni("Sao Paulo")
    nomes = {p.get("nome") for p in dados["pins"]["concorrentes"]}
    assert {"Smart Fit 0", "Smart Fit 1"} <= nomes
    assert any(p.get("diag") for p in dados["pins"]["concorrentes"])
    assert dados["independentes"]["total"] == 3
