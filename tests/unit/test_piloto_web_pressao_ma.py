"""Overlay de PRESSÃO COMPETITIVA sobre as independentes no piloto (BLK-MA-13 / DEC-028).

O que esta suíte protege, e por que cada item é caro de perder:

  * **A degradação silenciosa.** Sem o artefato, `pressao_ma.disponivel` é `False` e a pílula nem
    aparece. Se isso quebrar, o piloto passa a exigir um parquet que o CI não tem e a tela morre
    para todo mundo — foi assim que o passo 4 ficou vazio em produção uma vez.
  * **Os três estados da cor.** "Medi e não há pressão" (`0.0`), "não medi" (`None`) e "fora do
    universo" (campo ausente) precisam chegar ao front DISTINGUÍVEIS. Colapsá-los faria o mapa
    afirmar ausência de concorrência onde o que existe é ausência de dado — o risco 2 da DEC-027.
  * **A cobertura declarada.** `n_hexes` e `n_com_pressao` são o que a legenda usa para dizer
    "N de M medidos". Sem o par, verde lê como "medi e está livre".
  * **O anti-PII na fronteira WEB.** Este é o único ponto do epic em que a camada cruza para uma
    superfície pública; §11/DEC-012 valem aqui com força total.
  * **O rótulo.** Nada no payload pode dizer "vulnerabilidade" (DEC-028).

Fixtures 100% sintéticas, no molde do `test_piloto_web_crescimento.py`; nenhum teste lê `data/`.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from tests.unit.test_piloto_web_endpoints import (  # noqa: F401
    empty_data,
    pilot,
    synth_data,
)

# Os hexes do enriquecido sintético (ver `_synthetic_enriched`): 4 por município, 2 municípios.
HEX_SP = [f"87a0{h}0000000ffff" for h in range(4)]
HEX_CPS = [f"87a1{h}0000000ffff" for h in range(4)]


def _muni(nome: str = "Sao Paulo") -> dict:
    return pilot.municipio("SP", nome)


def _camada_hex() -> pd.DataFrame:
    """Camada hex-level no contrato do BLK-MA-05, cobrindo os TRÊS estados de propósito.

    - `HEX_SP[0]`: pressão alta (sufocante)
    - `HEX_SP[1]`: pressão `0.0` — MEDIDA, não ausente
    - `HEX_SP[2]`: pressão nula — o score foi calculado sem o insumo
    - `HEX_SP[3]`: **fora** do artefato — nenhuma academia independente mapeada
    """
    linhas = [
        {
            "hex_id_res7": HEX_SP[0],
            "uf": "SP",
            "sinais_disponiveis": "s1,s6",
            "n_sinais_disponiveis": 2,
            "n_independentes_vulneraveis": 7,
            "score_vulnerabilidade_medio": 64.0,
            "score_vulnerabilidade_max": 68.0,
            "sam_fitness_potencial": 4000.0,
            "score_oportunidade_residual": 10.0,
            "hex_quente": True,
            "proximo_de_hex_quente": True,
            "flag_serie_imatura": True,
            "n_com_nota_wellhub": 5,
            "nota_wellhub_mediana": 4.6,
            "pressao_competitiva_no_hex": 85.0,
            "v6_no_hex": 0.85,
            "versao_contrato": "alvos_ma_v1",
        },
        {
            "hex_id_res7": HEX_SP[1],
            "uf": "SP",
            "sinais_disponiveis": "s1,s6",
            "n_sinais_disponiveis": 2,
            "n_independentes_vulneraveis": 2,
            "score_vulnerabilidade_medio": 30.0,
            "score_vulnerabilidade_max": 30.0,
            "sam_fitness_potencial": 100.0,
            "score_oportunidade_residual": 90.0,
            "hex_quente": False,
            "proximo_de_hex_quente": False,
            "flag_serie_imatura": True,
            "n_com_nota_wellhub": 0,
            "nota_wellhub_mediana": None,
            "pressao_competitiva_no_hex": 0.0,
            "v6_no_hex": 0.0,
            "versao_contrato": "alvos_ma_v1",
        },
        {
            "hex_id_res7": HEX_SP[2],
            "uf": "SP",
            "sinais_disponiveis": "s1",
            "n_sinais_disponiveis": 1,
            "n_independentes_vulneraveis": 1,
            "score_vulnerabilidade_medio": 50.0,
            "score_vulnerabilidade_max": 50.0,
            "sam_fitness_potencial": 50.0,
            "score_oportunidade_residual": 50.0,
            "hex_quente": False,
            "proximo_de_hex_quente": False,
            "flag_serie_imatura": True,
            "n_com_nota_wellhub": 0,
            "nota_wellhub_mediana": None,
            "pressao_competitiva_no_hex": None,
            "v6_no_hex": None,
            "versao_contrato": "alvos_ma_v1",
        },
    ]
    df = pd.DataFrame(linhas)
    df["nota_wellhub_mediana"] = df["nota_wellhub_mediana"].astype("Float64")
    df["pressao_competitiva_no_hex"] = df["pressao_competitiva_no_hex"].astype("Float64")
    df["v6_no_hex"] = df["v6_no_hex"].astype("Float64")
    return df


@pytest.fixture
def com_pressao(synth_data: Path) -> Path:  # noqa: F811
    """Fixture do piloto + a camada hex-level do overlay."""
    outputs = synth_data / "outputs"
    outputs.mkdir(parents=True, exist_ok=True)
    _camada_hex().to_parquet(outputs / "alvos_ma_hex.parquet", index=False)
    pilot.carregar_pressao_ma.cache_clear()
    pilot.carregar_uf.cache_clear()
    return synth_data


def _por_id(payload: dict) -> dict[str, dict]:
    return {h["id"]: h for h in payload["hexes"]}


# ---------------------------------------------------------------------------
# Degradação: sem artefato, a camada simplesmente não existe
# ---------------------------------------------------------------------------
def test_sem_artefato_a_camada_nao_esta_disponivel(synth_data: Path) -> None:  # noqa: F811
    payload = _muni()
    assert payload["pressao_ma"]["disponivel"] is False
    # E nenhum hexágono ganha campo `ma_*`: o front não pode receber zeros mentirosos.
    for h in payload["hexes"]:
        assert not [k for k in h if k.startswith("ma_")]


def test_sem_dado_nenhum_a_rota_nao_quebra(empty_data: Path) -> None:  # noqa: F811
    """`empty_data` reproduz o CI: nem enriquecido existe. A rota levanta 404, não 500."""
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as e:
        _muni()
    assert e.value.status_code == 404


def test_artefato_com_hex_duplicado_e_recusado(synth_data: Path) -> None:  # noqa: F811
    """Duas linhas para o mesmo hexágono = o colapso do BLK-MA-13 falhou rio acima.

    Servir assim mesmo faria o `.map` escolher uma das duas em silêncio, e o mapa pintaria uma cor
    que ninguém decidiu. Recusar a camada inteira é a degradação honesta.
    """
    duplicado = pd.concat([_camada_hex(), _camada_hex().head(1)], ignore_index=True)
    duplicado.to_parquet(synth_data / "outputs" / "alvos_ma_hex.parquet", index=False)
    pilot.carregar_pressao_ma.cache_clear()
    assert pilot.carregar_pressao_ma() is None
    assert _muni()["pressao_ma"]["disponivel"] is False


# ---------------------------------------------------------------------------
# Os três estados que a cor precisa distinguir
# ---------------------------------------------------------------------------
def test_pressao_medida_chega_ao_hexagono(com_pressao: Path) -> None:
    h = _por_id(_muni())[HEX_SP[0]]
    assert h["ma_press"] == pytest.approx(85.0)
    assert h["ma_n"] == 7
    assert h["ma_quente"] is True
    assert h["ma_regime"] == "s1,s6"


def test_pressao_zero_e_medicao_nao_ausencia(com_pressao: Path) -> None:
    """`0.0` afirma "medi e não há ninguém espremendo" — não pode virar `None`.

    Na régua do §8.1 essa é a leitura mais OTIMISTA possível; confundi-la com ausência de dado
    inverte o sentido do sinal em silêncio.
    """
    h = _por_id(_muni())[HEX_SP[1]]
    assert h["ma_press"] == 0.0
    assert h["ma_press"] is not None
    assert h["ma_n"] == 2


def test_sem_medicao_de_pressao_fica_nulo_com_o_hex_ainda_no_universo(com_pressao: Path) -> None:
    """O hex tem academia independente (`ma_n`), mas a pressão não foi calculada."""
    h = _por_id(_muni())[HEX_SP[2]]
    assert h["ma_press"] is None
    assert h["ma_n"] == 1


def test_hex_fora_do_universo_nao_ganha_campo_nenhum(com_pressao: Path) -> None:
    """Sem academia independente mapeada, o hexágono não participa desta leitura."""
    h = _por_id(_muni())[HEX_SP[3]]
    assert "ma_press" not in h
    assert "ma_n" not in h


def test_coluna_ausente_no_artefato_vira_NULO_e_nao_False(com_pressao: Path) -> None:
    """Artefato sem `hex_quente` (projeção defensiva) NÃO pode virar "não é quente".

    `bool(None)` é `False`, e um `False` aqui AFIRMA que o hexágono foi avaliado e reprovou. Um
    artefato regerado sem a coluna passaria a negar calor no mapa inteiro, em silêncio.
    """
    df = _camada_hex().drop(columns=["hex_quente"])
    df.to_parquet(com_pressao / "outputs" / "alvos_ma_hex.parquet", index=False)
    pilot.carregar_pressao_ma.cache_clear()

    h = _por_id(_muni())[HEX_SP[0]]
    assert h["ma_quente"] is None
    assert h["ma_press"] == pytest.approx(85.0), "o resto da leitura continua chegando"


# ---------------------------------------------------------------------------
# Cobertura e regime — o que a legenda declara
# ---------------------------------------------------------------------------
def test_metadados_declaram_cobertura_e_regime(com_pressao: Path) -> None:
    meta = _muni()["pressao_ma"]
    assert meta["disponivel"] is True
    assert meta["n_hexes"] == 3, "os 3 hexes de SP que estao no artefato"
    assert meta["n_com_pressao"] == 1, "so' um tem pressao > 0"
    # A fixture tem dois regimes: `s1,s6` em 2 hexes e `s1` em 1. O dominante vem primeiro.
    assert meta["regimes"] == ["s1,s6", "s1"]


def test_regimes_vem_ordenados_por_cobertura(com_pressao: Path) -> None:
    """A ordem segue a COBERTURA, não o alfabeto nem a ordem de leitura do parquet.

    Inverter a cobertura na fixture e exigir que a lista vire é o que dá poder ao teste: com a
    ordem da fixture base ele passaria mesmo se o código devolvesse os regimes na ordem em que os
    encontrou.
    """
    df = _camada_hex()
    # Agora `s1` cobre 2 hexes e `s1,s6` cobre 1 — o inverso da fixture base.
    df.loc[df["hex_id_res7"].isin([HEX_SP[1], HEX_SP[2]]), "sinais_disponiveis"] = "s1"
    df.to_parquet(com_pressao / "outputs" / "alvos_ma_hex.parquet", index=False)
    pilot.carregar_pressao_ma.cache_clear()
    assert _muni()["pressao_ma"]["regimes"] == ["s1", "s1,s6"]


def test_recorte_sem_academia_independente_declara_o_motivo(com_pressao: Path) -> None:
    """Campinas não tem linha nenhuma no artefato: a pílula some, com motivo por extenso."""
    meta = _muni("Campinas")["pressao_ma"]
    assert meta["disponivel"] is False
    assert meta["motivo"]


def test_uf_inteira_tambem_recebe_a_camada(com_pressao: Path) -> None:
    payload = pilot.uf_view("SP")
    assert payload["pressao_ma"]["disponivel"] is True
    assert _por_id(payload)[HEX_SP[0]]["ma_press"] == pytest.approx(85.0)


# ---------------------------------------------------------------------------
# Fronteira anti-PII e rótulo (§11 / DEC-012 / DEC-028)
# ---------------------------------------------------------------------------
def test_payload_nao_carrega_identidade_de_academia(com_pressao: Path) -> None:
    """§11: nunca texto/autor de review, coordenada bruta de estabelecimento ou chave de academia.

    A geometria da camada deriva do `hex_id` e nada mais — este é o único ponto do epic em que ela
    cruza para uma superfície web.
    """
    proibidos = {
        "chave_snapshot",
        "fonte",
        "rede",
        "slug",
        "nome",
        "endereco",
        "endereco_formatado",
        "cep",
        "latitude",
        "longitude",
        "concorrente_id",
    }
    for h in _muni()["hexes"]:
        campos_ma = {k[3:] for k in h if k.startswith("ma_")}
        assert not campos_ma & proibidos, campos_ma


def test_payload_nao_usa_o_vocabulario_de_vulnerabilidade(com_pressao: Path) -> None:
    """DEC-028: enquanto S3/S4 estiverem imaturos, esta camada se chama pressão competitiva.

    Vale para as CHAVES do payload, que é o que o front lê e o que um consumidor futuro copia.
    """
    import json

    payload = _muni()
    texto = json.dumps({"meta": payload["pressao_ma"], "hex": payload["hexes"][0]}).lower()
    for proibido in ("vulnerab", "alvo_ma", "aquisic"):
        assert proibido not in texto


def test_score_de_vulnerabilidade_nao_viaja_no_payload(com_pressao: Path) -> None:
    """O score é `30 + 40·v6` no regime vigente — uma transformação afim da própria pressão.

    Servir os dois mostraria o MESMO fato com dois rótulos e duas escalas, convidando a lê-los como
    grandezas independentes. Fica de fora até o regime mudar (DEC-028).
    """
    h = _por_id(_muni())[HEX_SP[0]]
    assert "ma_score" not in h
    assert not [k for k in h if "score" in k and k.startswith("ma_")]


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
def test_health_observa_o_artefato_do_overlay(com_pressao: Path) -> None:
    """Artefato que a tela consome e que não viaja com o código entra no `/api/health`."""
    artefatos = pilot.health()["artefatos"]
    assert artefatos["pressao_ma_hex"]["ok"] is True


def test_health_aponta_o_artefato_faltando(synth_data: Path) -> None:  # noqa: F811
    saude = pilot.health()
    assert "pressao_ma_hex" in saude["artefatos_faltando"]
    assert saude["status"] == "ok", "artefato opcional ausente nao derruba o health"
