"""BLK-MA-12: testes do sinal 6 — pressão competitiva com decaimento por distância.

Fixtures 100% SINTÉTICAS: os pontos de concorrentes são forjados a distâncias conhecidas de um
centroide conhecido, para que o decaimento seja verificável em número, não em vibe. **Zero I/O** —
nenhum teste lê `data/`.

Os testes que mais importam:

  * **`test_concorrente_perto_pesa_mais_que_longe`** — é a razão de o bloco existir. Uma contagem
    dentro do raio daria peso igual aos dois.
  * **`test_ausencia_de_calculo_nao_vira_pressao_zero`** — na régua do §8.1, `0` é a leitura mais
    OTIMISTA ("ninguém espremendo"). Confundir "não calculei" com "não há" rebaixaria o alvo por
    falta de dado.
  * **`test_kernel_carimbado_na_saida`** — o número não significa nada sem saber que curva o
    produziu.
"""

from __future__ import annotations

import h3
import numpy as np
import pandas as pd
import pytest

from motor_expansao.vulnerabilidade import contrato as c
from motor_expansao.vulnerabilidade import pressao_competitiva as m
from motor_expansao.vulnerabilidade.pressao_competitiva import (
    calcular_pressao_por_hex,
    peso_por_distancia,
)

HEX = h3.latlng_to_cell(-23.5500, -46.6300, 7)
LAT, LNG = h3.cell_to_latlng(HEX)

_GRAU_LAT_M = 111_320.0  # 1 grau de latitude ~ 111,32 km; suficiente para posicionar fixtures


def _ponto_a(metros: float, *, rede: str = "smart_fit") -> dict[str, object]:
    """Um concorrente a `metros` ao NORTE do centroide de HEX."""
    return {
        "rede": rede,
        "lat": LAT + metros / _GRAU_LAT_M,
        "lng": LNG,
        "status_registro": "valido",
    }


def _concorrentes(distancias_m: list[float]) -> pd.DataFrame:
    return pd.DataFrame([_ponto_a(d) for d in distancias_m])


# --------------------------------------------------------------------------- #
# O decaimento
# --------------------------------------------------------------------------- #
def test_concorrente_perto_pesa_mais_que_longe() -> None:
    """O ponto do bloco: distância importa. Contagem num raio daria o mesmo peso aos dois."""
    perto = float(peso_por_distancia(np.array([100.0]))[0])
    longe = float(peso_por_distancia(np.array([1900.0]))[0])
    assert perto > longe
    assert perto == pytest.approx(0.95, abs=1e-9)
    assert longe == pytest.approx(0.05, abs=1e-9)


def test_kernel_linear_zera_na_borda_e_fora() -> None:
    pesos = peso_por_distancia(np.array([0.0, 1000.0, 2000.0, 2001.0, 5000.0]))
    assert list(np.round(pesos, 6)) == [1.0, 0.5, 0.0, 0.0, 0.0]


def test_kernel_potencia_e_monotonico_e_limitado() -> None:
    """O kernel alternativo tem de continuar sendo um PESO: em [0,1] e decrescente."""
    d = np.array([50.0, 100.0, 500.0, 1000.0, 1999.0, 2500.0])
    pesos = peso_por_distancia(d, kernel="potencia")
    assert float(pesos[0]) == pytest.approx(1.0)
    assert all(pesos[i] >= pesos[i + 1] for i in range(len(pesos) - 1))
    assert float(pesos.min()) >= 0.0 and float(pesos.max()) <= 1.0
    assert float(pesos[-1]) == 0.0, "fora do raio o peso e' exatamente zero"


def test_kernel_desconhecido_levanta() -> None:
    with pytest.raises(ValueError, match="kernel fora de"):
        peso_por_distancia(np.array([100.0]), kernel="gaussiano")


def test_raio_e_truncamento_nao_alcance() -> None:
    """Dobrar o raio muda a CURVA inteira, não só o corte — é a curva que define o alcance."""
    d = np.array([1000.0])
    assert float(peso_por_distancia(d, raio_m=2000.0)[0]) == pytest.approx(0.5)
    assert float(peso_por_distancia(d, raio_m=4000.0)[0]) == pytest.approx(0.75)


# --------------------------------------------------------------------------- #
# A agregação por hex
# --------------------------------------------------------------------------- #
def test_pressao_cresce_com_a_concorrencia() -> None:
    """Direção exigida pelo §8.1: mais concorrência -> mais vulnerabilidade."""
    um = calcular_pressao_por_hex([HEX], _concorrentes([500.0]))
    tres = calcular_pressao_por_hex([HEX], _concorrentes([500.0, 600.0, 700.0]))
    assert float(tres.iloc[0]["v6_no_hex"]) > float(um.iloc[0]["v6_no_hex"])


def test_hex_sem_concorrente_no_raio_tem_pressao_zero() -> None:
    """Aqui o zero é MEDIÇÃO (o universo de pontos é conhecido), não ausência de dado."""
    out = calcular_pressao_por_hex([HEX], _concorrentes([50_000.0]))
    assert float(out.iloc[0]["v6_no_hex"]) == 0.0
    assert int(out.iloc[0]["n_concorrentes_no_raio"]) == 0


def test_contagem_crua_viaja_junto_para_auditar_o_decaimento() -> None:
    """Sem a contagem ao lado, não dá para saber se a oferta baixa é pouca gente ou gente longe."""
    out = calcular_pressao_por_hex([HEX], _concorrentes([1900.0, 1950.0, 1980.0]))
    assert int(out.iloc[0]["n_concorrentes_no_raio"]) == 3
    assert float(out.iloc[0]["oferta_ponderada_no_hex"]) < 0.3, "3 concorrentes, todos na borda"


def test_distancia_do_mais_proximo_e_reportada() -> None:
    out = calcular_pressao_por_hex([HEX], _concorrentes([300.0, 1500.0]))
    assert float(out.iloc[0]["dist_concorrente_mais_proximo_m"]) == pytest.approx(300.0, rel=0.02)


def test_v6_fica_no_dominio_do_contrato() -> None:
    """`v6 = 1 - 1/(1+oferta)` nunca alcança 1: a saturação é assintótica."""
    out = calcular_pressao_por_hex([HEX], _concorrentes([10.0] * 200))
    v6 = float(out.iloc[0]["v6_no_hex"])
    assert 0.0 <= v6 < 1.0
    assert v6 > 0.99, "200 concorrentes na porta devem saturar"


def test_kernel_carimbado_na_saida() -> None:
    out = calcular_pressao_por_hex([HEX], _concorrentes([500.0]), kernel="potencia")
    assert str(out.iloc[0]["kernel_pressao"]) == "potencia"
    assert float(out.iloc[0]["raio_pressao_m"]) == c.PRESSAO_RAIO_M


def test_descarta_concorrente_invalido_sem_quebrar() -> None:
    conc = _concorrentes([500.0])
    conc.loc[len(conc)] = {"rede": "x", "lat": np.nan, "lng": np.nan, "status_registro": "valido"}
    conc.loc[len(conc)] = {
        "rede": "y",
        "lat": -23.5,
        "lng": -46.6,
        "status_registro": "descartado_coord",
    }
    out = calcular_pressao_por_hex([HEX], conc)
    assert int(out.iloc[0]["n_concorrentes_no_raio"]) == 1


def test_hex_invalido_e_ignorado_com_aviso() -> None:
    out = calcular_pressao_por_hex([HEX, "NAO_E_HEX", ""], _concorrentes([500.0]))
    assert list(out["hex_id_res7"]) == [HEX]


def test_sem_hex_devolve_frame_vazio_bem_formado() -> None:
    out = calcular_pressao_por_hex([], _concorrentes([500.0]))
    assert out.empty
    assert list(out.columns) == list(c.CONTRATO_COLUNAS_PRESSAO.keys())


def test_schema_em_ordem_e_dtypes() -> None:
    out = calcular_pressao_por_hex([HEX], _concorrentes([500.0]))
    assert list(out.columns) == list(c.CONTRATO_COLUNAS_PRESSAO.keys())
    for coluna, dtype in c.CONTRATO_COLUNAS_PRESSAO.items():
        assert str(out[coluna].dtype) == dtype, coluna


def test_saida_nao_carrega_coordenada() -> None:
    """Entra lat/lng de estabelecimento comercial; sai só agregado por hex (§11 / DEC-012)."""
    out = calcular_pressao_por_hex([HEX], _concorrentes([500.0]))
    for proibida in ("lat", "lng", "latitude", "longitude", "nome", "concorrente_id"):
        assert proibida not in out.columns


def test_funcao_e_pura() -> None:
    conc = _concorrentes([500.0])
    antes = conc.copy()
    calcular_pressao_por_hex([HEX], conc)
    pd.testing.assert_frame_equal(conc, antes)


def test_modulo_nao_importa_demanda_revelada() -> None:
    from .._ast_imports import nomes_importados

    for n in nomes_importados(m):
        assert "demanda_revelada" not in n, n


def test_nao_usa_dependencia_pesada() -> None:
    """`geopandas`/`shapely`/`sklearn` quebrariam o teste de peso do pacote."""
    from .._ast_imports import nomes_importados

    for n in nomes_importados(m):
        for pesada in ("geopandas", "shapely", "sklearn", "scipy", "pyproj"):
            assert pesada not in n, n


# --------------------------------------------------------------------------- #
# BLK-MA-14 / DEC-029 — o grão ACADEMIA
# --------------------------------------------------------------------------- #
def _academias(offsets_m: list[float]) -> pd.DataFrame:
    """Academias a `offsets_m` ao NORTE do centroide de HEX — todas DENTRO do mesmo hexágono.

    As colunas são declaradas mesmo na lista vazia: um `DataFrame([])` sai SEM coluna nenhuma, o
    que não é o frame vazio que o pipeline produz (`coordenadas_por_chave` devolve o schema
    completo). Testar o caso degenerado com um frame que a produção nunca gera testaria outra
    coisa.
    """
    return pd.DataFrame(
        [
            {
                "fonte": "wellhub",
                "chave_snapshot": f"k{i}",
                "lat": LAT + m_ / _GRAU_LAT_M,
                "lng": LNG,
            }
            for i, m_ in enumerate(offsets_m)
        ],
        columns=["fonte", "chave_snapshot", "lat", "lng"],
    )


def test_pressao_varia_ENTRE_academias_do_mesmo_hexagono() -> None:
    """A razão de existir do BLK-MA-14, e o teste que FALHARIA com o grão antigo.

    Duas academias no MESMO hexágono, uma colada no concorrente e outra longe dele. No grão hex as
    duas recebiam o valor do centroide e empatavam por construção (medido no dado real: `0 de
    6.753` hexes com qualquer variação interna). Aqui elas têm de divergir.
    """
    conc = _concorrentes([0.0])  # concorrente no centroide
    ac = _academias([0.0, 1800.0])  # uma colada nele, outra a 1,8 km

    out = m.calcular_pressao_por_academia(ac, conc)
    assert len(out) == 2
    perto = float(out.loc[out["chave_snapshot"] == "k0", "pressao_competitiva"].iloc[0])
    longe = float(out.loc[out["chave_snapshot"] == "k1", "pressao_competitiva"].iloc[0])
    assert perto > longe, "a academia colada no concorrente tem de sofrer mais pressao"
    assert out["pressao_competitiva"].nunique() == 2

    # E o grão hex, no MESMO insumo, dá um valor só — que é exatamente o que se está corrigindo.
    por_hex = calcular_pressao_por_hex([HEX], conc)
    assert len(por_hex) == 1


def test_os_dois_graos_usam_a_MESMA_formula() -> None:
    """Academia no CENTROIDE do hex tem de bater com o grão hex, dígito a dígito.

    É o teste que impede as duas fórmulas de divergirem: elas compartilham `_oferta_por_origem` e
    `_saturar`, e se alguém alterar o kernel num caminho só, os números deixam de ser comparáveis
    — sem nenhum erro visível, porque cada um continuaria internamente coerente.
    """
    conc = _concorrentes([700.0, 1500.0])
    no_centroide = m.calcular_pressao_por_academia(_academias([0.0]), conc)
    por_hex = calcular_pressao_por_hex([HEX], conc)
    assert float(no_centroide.iloc[0]["pressao_competitiva"]) == pytest.approx(
        float(por_hex.iloc[0]["pressao_competitiva_no_hex"])
    )
    assert float(no_centroide.iloc[0]["v6"]) == pytest.approx(
        float(por_hex.iloc[0]["v6_no_hex"])
    )


def test_saida_por_academia_NAO_carrega_coordenada() -> None:
    """O ponto todo da rota B: a coordenada ENTRA no cálculo e não sai dele.

    Sem este teste, "a camada não persiste coordenada" volta a ser prosa — e é justamente a frase
    que, mal interpretada, manteve o sinal um bloco inteiro no grão errado.
    """
    out = m.calcular_pressao_por_academia(_academias([0.0, 500.0]), _concorrentes([300.0]))
    assert list(out.columns) == list(c.CONTRATO_COLUNAS_PRESSAO_ACADEMIA)
    for proibida in ("lat", "lng", "latitude", "longitude", "nome"):
        assert proibida not in out.columns


def test_academia_sem_coordenada_sai_do_calculo_em_vez_de_virar_zero() -> None:
    """`0` afirmaria "ninguém espremendo" — a leitura mais otimista da régua (§8.1)."""
    ac = _academias([0.0])
    ac.loc[len(ac)] = {"fonte": "wellhub", "chave_snapshot": "sem_coord", "lat": None, "lng": None}
    out = m.calcular_pressao_por_academia(ac, _concorrentes([300.0]))
    assert set(out["chave_snapshot"]) == {"k0"}, "a linha sem coordenada nao pode receber pressao"


def test_chave_duplicada_levanta_em_vez_de_escolher_uma() -> None:
    """`(fonte, chave_snapshot)` é a chave primária do score: duplicata aqui envenenaria o join."""
    ac = pd.concat([_academias([0.0]), _academias([500.0])], ignore_index=True)
    with pytest.raises(ValueError, match="duplicado"):
        m.calcular_pressao_por_academia(ac, _concorrentes([300.0]))


def test_frame_de_academias_sem_coluna_obrigatoria_levanta() -> None:
    with pytest.raises(ValueError, match="obrigatoria"):
        m.calcular_pressao_por_academia(
            _academias([0.0]).drop(columns=["chave_snapshot"]), _concorrentes([300.0])
        )


def test_academias_vazio_devolve_frame_bem_formado() -> None:
    out = m.calcular_pressao_por_academia(_academias([]), _concorrentes([300.0]))
    assert list(out.columns) == list(c.CONTRATO_COLUNAS_PRESSAO_ACADEMIA)
    assert out.empty


def test_nao_muta_o_frame_de_academias() -> None:
    ac = _academias([0.0, 900.0])
    antes = ac.copy()
    m.calcular_pressao_por_academia(ac, _concorrentes([300.0]))
    pd.testing.assert_frame_equal(ac, antes)
