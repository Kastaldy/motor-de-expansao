"""A calibracao da taxa de penetracao por DEMANDA REVELADA (DEC-060).

**O conceito, porque ele ja' foi mal entendido uma vez e custou trabalho.** O modelo NAO
preve alunos a partir da populacao. Ele INFERE um piso de demanda a partir da oferta que
SOBREVIVE: se tres academias de rede estao de pe numa praca e cada uma precisa de ~2.325
alunos, entao pelo menos ~7.000 alunos existem ali. Quem testar "populacao preve alunos"
para julgar esta funcao estara testando um espantalho.

**Os tres defeitos que a DEC-060 corrige, e o que cada teste aqui protege:**

  * TERRITORIO -- o numerador contava academias num disco de 2 km do CENTROIDE (12,57 km2)
    e dividia pela populacao de UM hexagono (5,16 km2), contando cada academia 2,33 vezes.
  * MASCARA -- com o numerador de 1 km, "tem academia num raio de 2 km" passa a incluir
    hexagonos que o disco apenas ENCOSTA: fatia minima de alunos, populacao inteira. Eram
    29% da amostra e o clip de 5% os censurava em silencio.
  * CAPACIDADE -- o proxy de 2.000 alunos, contra 2.325 medidos em 1.226 unidades reais.

Os testes sao de FORMA e de DIRECAO, nao golden de valor: o numero exato se move a cada
coleta semanal, mas as propriedades abaixo nao podem se mover nunca.
"""

from __future__ import annotations

import pandas as pd
import pytest

from motor_expansao.pipelines.calcular_colunas_mercado import (
    TAXA_FITNESS_MERCADO_FALLBACK,
    calibrar_taxa_fitness_mercado,
)
from motor_expansao.pipelines.pressao_concorrencial_1km import (
    COLUNAS_1KM_AREA,
    _contagem_no_hex,
)


def _hexes(linhas: list[dict]) -> pd.DataFrame:
    """Frame minimo com as colunas que a calibracao le."""
    base = {
        "pop_hex_base": 10_000.0,
        "n_concorrentes_no_hex": 0,
        "consumo_concorrentes_1km_area": 0.0,
        "oferta_consumida_ultra_real": 0.0,
        "n_concorrentes_mapeados_2km": 0,
        "n_unidades_ultra_2km": 0,
    }
    return pd.DataFrame([{**base, **linha} for linha in linhas])


# --------------------------------------------------------------------------- #
# A mascara: so' entra quem CONTEM academia                                     #
# --------------------------------------------------------------------------- #


def test_hexagono_que_so_ENCOSTA_no_disco_fica_fora_da_amostra() -> None:
    """E' o defeito que valia +6,77 pontos, e o mais dificil de ver.

    Os dois hexagonos recebem alunos do disco de 1 km de alguma academia. Mas so' um deles
    CONTEM a academia; o outro so' e' tocado pela borda, recebe uma fatia minima e a
    populacao inteira. Incluir o segundo derruba a mediana por dilucao geometrica, e nao
    porque exista mercado desatendido ali.
    """
    df = _hexes([
        {"n_concorrentes_no_hex": 1, "consumo_concorrentes_1km_area": 2_000.0},
        {"n_concorrentes_no_hex": 0, "consumo_concorrentes_1km_area": 70.0},
    ] * 12)  # 12 na mascara: acima do piso de 10, senao a funcao devolve o fallback

    # So' os 12 que CONTEM academia entram: 2.000/10.000 = 20%. Se os de borda entrassem,
    # os 70/10.000 = 0,7% deles cairiam sob o piso de 5% e a mediana desabaria para 12,5%.
    assert calibrar_taxa_fitness_mercado(df) == pytest.approx(0.20)


def test_a_mascara_NAO_e_a_contagem_de_influencia() -> None:
    """`n_concorrentes_influencia_1km` responde quem ALCANCA; a mascara, quem esta' DENTRO.

    Trocar uma pela outra reintroduz exatamente o defeito acima — e as duas colunas sao
    vizinhas no mesmo artefato, entao a troca e' um erro plausivel.
    """
    df = _hexes([{"n_concorrentes_no_hex": 1, "consumo_concorrentes_1km_area": 1_500.0}] * 12)
    df["n_concorrentes_influencia_1km"] = 9  # presente e IGNORADA de proposito
    assert calibrar_taxa_fitness_mercado(df) == pytest.approx(0.15)


# --------------------------------------------------------------------------- #
# O numerador                                                                   #
# --------------------------------------------------------------------------- #


def test_usa_o_consumo_de_1km_e_nao_a_contagem_de_2km() -> None:
    """As duas fontes presentes e DISCORDANDO: tem de vencer a de 1 km."""
    df = _hexes([{
        "n_concorrentes_no_hex": 1,
        "consumo_concorrentes_1km_area": 1_000.0,
        "n_concorrentes_mapeados_2km": 5,   # daria 5 x 2.000 / 10.000 = 100% -> clip 50%
    }] * 12)
    assert calibrar_taxa_fitness_mercado(df) == pytest.approx(0.10)


def test_o_termo_ultra_usa_alunos_REAIS() -> None:
    """`oferta_consumida_ultra_estimada` carrega a dupla contagem de 2 km e nao pode entrar.

    86% dela (792.500 de 922.307 alunos) vem do fallback `n_unidades_ultra_2km x 2.500`
    espalhado por 290 hexagonos para 53 unidades reais — o mesmo defeito que a correcao do
    territorio elimina. Se alguem trocar a coluna, este teste cai.
    """
    df = _hexes([{
        "n_concorrentes_no_hex": 1,
        "consumo_concorrentes_1km_area": 1_000.0,
        "oferta_consumida_ultra_real": 500.0,
    }] * 12)
    df["oferta_consumida_ultra_estimada"] = 9_000.0  # presente e IGNORADA
    assert calibrar_taxa_fitness_mercado(df) == pytest.approx(0.15)


def test_a_taxa_corrigida_e_MENOR_que_a_antiga_no_mesmo_frame() -> None:
    """Direcao, nao valor. A antiga conta cada academia ~2,3x; a nova conserva massa."""
    linhas = [{
        "n_concorrentes_no_hex": 1,
        "consumo_concorrentes_1km_area": 2_325.0,
        "n_concorrentes_mapeados_2km": 2,
        "pop_hex_base": 30_000.0,
    }] * 12
    nova = calibrar_taxa_fitness_mercado(_hexes(linhas))
    antiga = calibrar_taxa_fitness_mercado(
        _hexes(linhas).drop(columns=["n_concorrentes_no_hex"])
    )
    assert nova < antiga


# --------------------------------------------------------------------------- #
# O ramo de tras — nunca em silencio                                            #
# --------------------------------------------------------------------------- #


def test_sem_as_colunas_novas_cai_no_ramo_antigo_E_AVISA(capsys) -> None:
    df = _hexes([{"n_concorrentes_mapeados_2km": 1, "pop_hex_base": 20_000.0}] * 12)
    df = df.drop(columns=["n_concorrentes_no_hex", "consumo_concorrentes_1km_area"])
    taxa = calibrar_taxa_fitness_mercado(df)

    saida = capsys.readouterr().out
    assert "AVISO" in saida
    assert "n_concorrentes_no_hex" in saida
    assert "Bloco 3" in saida, "o aviso tem de dizer O QUE RODAR, nao so' que falhou"
    assert taxa == pytest.approx(0.10)


def test_amostra_pequena_demais_devolve_o_fallback() -> None:
    df = _hexes([{"n_concorrentes_no_hex": 1, "consumo_concorrentes_1km_area": 1_000.0}] * 9)
    assert calibrar_taxa_fitness_mercado(df) == TAXA_FITNESS_MERCADO_FALLBACK


def test_populacao_zero_nunca_entra_na_conta() -> None:
    """Divisao por zero viraria inf e envenenaria a mediana."""
    df = _hexes(
        [{"n_concorrentes_no_hex": 1, "consumo_concorrentes_1km_area": 1_000.0}] * 12
        + [{"n_concorrentes_no_hex": 1, "consumo_concorrentes_1km_area": 500.0,
            "pop_hex_base": 0.0}] * 5
    )
    taxa = calibrar_taxa_fitness_mercado(df)
    assert taxa == pytest.approx(0.10)


def test_o_clip_continua_valendo_nas_duas_pontas() -> None:
    df = _hexes(
        [{"n_concorrentes_no_hex": 1, "consumo_concorrentes_1km_area": 90_000.0}] * 6
        + [{"n_concorrentes_no_hex": 1, "consumo_concorrentes_1km_area": 1.0}] * 6
    )
    # mediana entre o teto (0,50) e o piso (0,05)
    assert calibrar_taxa_fitness_mercado(df) == pytest.approx(0.275)


# --------------------------------------------------------------------------- #
# A coluna nova, no produtor                                                    #
# --------------------------------------------------------------------------- #


def test_contagem_no_hex_conta_a_COORDENADA_e_nao_o_disco() -> None:
    import h3

    lat, lng = -23.5505, -46.6333
    alvo = h3.latlng_to_cell(lat, lng, 7)
    out = _contagem_no_hex(pd.DataFrame({"lat": [lat, lat], "lng": [lng, lng]}))
    assert list(out["hex_id"]) == [alvo]
    assert int(out["n_concorrentes_no_hex"].iloc[0]) == 2


def test_contagem_no_hex_ignora_coordenada_invalida() -> None:
    out = _contagem_no_hex(
        pd.DataFrame({"lat": [-23.5, None, float("nan")], "lng": [-46.6, -46.6, None]})
    )
    assert int(out["n_concorrentes_no_hex"].sum()) == 1


def test_contagem_no_hex_sem_nenhuma_coordenada_valida_nao_levanta() -> None:
    out = _contagem_no_hex(pd.DataFrame({"lat": [None], "lng": [None]}))
    assert out.empty
    assert list(out.columns) == ["hex_id", "n_concorrentes_no_hex"]


def test_a_coluna_esta_no_contrato_de_1km() -> None:
    """Sem isso, uma reexecucao de `anexar_pressao_1km_area` deixaria a coluna velha para
    tras em vez de substitui-la — o `drop` de reentrancia percorre esta lista."""
    assert "n_concorrentes_no_hex" in COLUNAS_1KM_AREA
