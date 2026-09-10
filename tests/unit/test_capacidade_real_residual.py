"""Capacidade REAL por unidade no residual (BLK-CAPACIDADE-01).

Ate' aqui toda academia do pais consumia os mesmos **2.500 alunos** — um proxy, e o
proprio nome da constante dizia isso. O crosswalk do BLK-ALUNOS-01 casou 1.202 unidades
com o numero que a rede informou; onde ele existe, nao ha' motivo para usar o proxy.

**A armadilha que estes testes existem para travar.** Quando a capacidade varia por
unidade, `oferta_consumida / 2.500` DEIXA DE SER UMA CONTAGEM. Um Smart Fit de 5.000
alunos apareceria como "2 concorrentes" e mandaria o hexagono de `Adensar` para
`Disputa` por ser GRANDE, nao por ter vizinho. Por isso as duas grandezas se separam:

  * `oferta_efetiva_1km_area`      -> unidades-equivalentes (quem me cerca)
  * `consumo_concorrentes_1km_area`-> alunos de verdade (o que sai do mercado)
  * `n_concorrentes_influencia_1km`-> a contagem, e e' ela que a tela passa a ler
"""

from __future__ import annotations

import pandas as pd
import pytest

from motor_expansao.pipelines.enriquecimento_espacial_hexagonos import (
    anexar_capacidade_real,
    unir_cadeias,
)
from motor_expansao.pipelines.pressao_concorrencial_1km import repartir_concorrentes

CAP_PADRAO = 2_500.0


def _uma(lat: float = -23.55, lng: float = -46.63, **extra) -> pd.DataFrame:
    return pd.DataFrame([{"lat": lat, "lng": lng, **extra}])


# --------------------------------------------------------------------------- #
# O modelo de 1 km com capacidade por unidade                                  #
# --------------------------------------------------------------------------- #


def test_sem_a_coluna_o_consumo_e_o_proxy_vezes_a_oferta() -> None:
    """Compatibilidade com artefato antigo -- e a ressalva honesta sobre ela.

    NAO e' bit a bit. Antes o consumo era `soma(shares) * 2.500`, uma multiplicacao no
    fim; agora e' `soma(share * capacidade)`, acumulada unidade a unidade. A ORDEM das
    operacoes em ponto flutuante mudou, e um caso de uma academia so' devolve
    2499,999999999998 no lugar de 2500. E' erro relativo de ~1e-12 e nao muda decisao
    nenhuma, mas esta escrito aqui para ninguem concluir, mais tarde, que uma diferenca
    na ultima casa entre duas regeneracoes e' sintoma de outra coisa.
    """
    out = repartir_concorrentes(_uma())
    assert out["consumo_concorrentes_1km_area"].sum() == pytest.approx(CAP_PADRAO, rel=1e-9)
    assert round(float(out["oferta_efetiva_1km_area"].sum()), 6) == 1.0


def test_com_a_coluna_o_consumo_e_a_capacidade_da_unidade() -> None:
    out = repartir_concorrentes(
        _uma(capacidade_alunos=5000.0), coluna_capacidade="capacidade_alunos"
    )
    assert round(float(out["consumo_concorrentes_1km_area"].sum()), 3) == 5000.0
    # A oferta em UNIDADES nao se move: continua uma academia.
    assert round(float(out["oferta_efetiva_1km_area"].sum()), 6) == 1.0


def test_unidade_sem_capacidade_cai_no_proxy() -> None:
    """A rede sem planilha continua valendo 2.500 -- ausencia nao vira zero."""
    df = pd.DataFrame(
        [
            {"lat": -23.55, "lng": -46.63, "capacidade_alunos": 4000.0},
            {"lat": -23.55, "lng": -46.63, "capacidade_alunos": None},
        ]
    )
    out = repartir_concorrentes(df, coluna_capacidade="capacidade_alunos")
    assert round(float(out["consumo_concorrentes_1km_area"].sum()), 3) == 6500.0


def test_oferta_e_consumo_deixam_de_ser_proporcionais() -> None:
    """E' o ponto do bloco, e o motivo de a contagem ter de mudar de fonte.

    Enquanto a capacidade era uniforme, consumo/2500 devolvia a contagem. Com capacidade
    real isso vira uma razao sem significado -- e quem dividir vai ler academia GRANDE
    como DUAS academias.
    """
    out = repartir_concorrentes(
        _uma(capacidade_alunos=7500.0), coluna_capacidade="capacidade_alunos"
    )
    oferta = float(out["oferta_efetiva_1km_area"].sum())
    consumo = float(out["consumo_concorrentes_1km_area"].sum())
    assert round(consumo / CAP_PADRAO, 1) == 3.0, "a divisao daria 3 concorrentes..."
    assert round(oferta, 6) == 1.0, "...mas ha UMA academia"
    assert int(out["n_concorrentes_influencia_1km"].max()) == 1


def test_massa_conservada_com_capacidade_variavel() -> None:
    """O share continua fechando em 1,0 por unidade; so' o peso muda."""
    df = pd.DataFrame(
        [
            {"lat": -23.55, "lng": -46.63, "capacidade_alunos": 1000.0},
            {"lat": -23.60, "lng": -46.70, "capacidade_alunos": 3000.0},
        ]
    )
    out = repartir_concorrentes(df, coluna_capacidade="capacidade_alunos")
    assert round(float(out["consumo_concorrentes_1km_area"].sum()), 3) == 4000.0
    assert round(float(out["oferta_efetiva_1km_area"].sum()), 6) == 2.0


def test_capacidade_negativa_e_saneada() -> None:
    out = repartir_concorrentes(
        _uma(capacidade_alunos=-500.0), coluna_capacidade="capacidade_alunos"
    )
    assert float(out["consumo_concorrentes_1km_area"].sum()) == 0.0


# --------------------------------------------------------------------------- #
# O join da capacidade real                                                    #
# --------------------------------------------------------------------------- #


def _crosswalk(tmp_path, linhas: list[dict]):
    caminho = tmp_path / "alunos.parquet"
    pd.DataFrame(linhas).to_parquet(caminho)
    return caminho


def _cadeias() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "rede": ["smart_fit", "bluefit"],
            "lat": [-23.55, -23.60],
            "lng": [-46.63, -46.70],
            "status_registro": ["valido", "valido"],
            "concorrente_id": ["c1", "c2"],
        }
    )


def test_capacidade_real_chega_a_unidade_casada(tmp_path) -> None:
    cw = _crosswalk(
        tmp_path,
        [{"concorrente_id": "c1", "alunos_total": 4200.0, "confianca_match": "alta"}],
    )
    out = anexar_capacidade_real(_cadeias(), crosswalk_path=cw)
    assert out.set_index("concorrente_id").loc["c1", "capacidade_alunos"] == 4200.0


def test_unidade_sem_crosswalk_fica_NULA_e_nao_2500(tmp_path) -> None:
    """Preencher aqui esconderia do artefato quantas sao medidas e quantas estimadas.

    Quem consome decide o default -- e' o `repartir_concorrentes` que aplica o proxy.
    """
    cw = _crosswalk(
        tmp_path,
        [{"concorrente_id": "c1", "alunos_total": 4200.0, "confianca_match": "alta"}],
    )
    out = anexar_capacidade_real(_cadeias(), crosswalk_path=cw)
    assert pd.isna(out.set_index("concorrente_id").loc["c2", "capacidade_alunos"])


def test_confianca_media_nao_vira_capacidade(tmp_path) -> None:
    """A rota de contencao e' inferencia, e capacidade mexe no residual DE TODOS em volta.

    Um numero inferido no tooltip afeta uma linha; virando capacidade, ele desloca a
    oferta de todo hexagono que aquele disco de 1 km alcanca.
    """
    cw = _crosswalk(
        tmp_path,
        [{"concorrente_id": "c1", "alunos_total": 9999.0, "confianca_match": "media"}],
    )
    out = anexar_capacidade_real(_cadeias(), crosswalk_path=cw)
    assert out["capacidade_alunos"].isna().all()


def test_crosswalk_ausente_e_caminho_normal(tmp_path) -> None:
    """O parquet nao e' versionado: sem ele, todo mundo cai no proxy, como antes."""
    out = anexar_capacidade_real(_cadeias(), crosswalk_path=tmp_path / "nao_existe.parquet")
    assert "capacidade_alunos" not in out.columns


def test_unir_cadeias_carrega_o_concorrente_id() -> None:
    """Sem ele a capacidade nao teria por onde casar -- depois so' ha agregado por hex."""
    comp = pd.DataFrame(
        {
            "rede": ["smart_fit"],
            "lat": [-23.55],
            "lng": [-46.63],
            "status_registro": ["valido"],
            "concorrente_id": ["c1"],
        }
    )
    feed = pd.DataFrame(
        {"rede": ["bluefit"], "lat": [-23.60], "lng": [-46.70], "tem_pin_proprio": [True]}
    )
    unido = unir_cadeias(comp, feed)
    assert "concorrente_id" in unido.columns
    assert set(unido["concorrente_id"].dropna()) == {"c1"}
    # A do agregador entra sem id -- ela nao tem, e fingir que tem casaria errado.
    assert unido["concorrente_id"].isna().sum() == 1
