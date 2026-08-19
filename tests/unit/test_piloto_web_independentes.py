"""Pins das academias INDEPENDENTES no piloto (BLK-MA-15 / emenda à DEC-028).

O que esta suíte protege:

  * **A degradação silenciosa.** Sem o artefato, `independentes.disponivel` é `False` e a pílula
    nem aparece. Se isso quebrar, o piloto passa a exigir um parquet que o CI não tem.
  * **A separação dos universos.** Os pins de independente NÃO podem se misturar aos de
    concorrente: a interseção entre eles é vazia por construção (o universo de M&A exclui cadeias),
    e juntá-los daria a uma Smart Fit a aparência de alvo de aquisição.
  * **O truncamento declarado.** O teto corta por `head()`; corte silencioso mente sobre a
    densidade — defeito que o teto de pins de concorrente já registrou.
  * **A fronteira do §11.** A emenda autorizou identidade de ESTABELECIMENTO; nada de PESSOA.
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

HEX_SP = [f"87a0{h}0000000ffff" for h in range(4)]


def _muni(nome: str = "Sao Paulo") -> dict:
    return pilot.municipio("SP", nome)


def _nomeadas() -> pd.DataFrame:
    linhas = [
        {
            "fonte": "wellhub",
            "chave_snapshot": f"k{i}",
            "nome": nome,
            "lat": -23.55 + 0.001 * i,
            "lng": -46.63,
            "hex_id_res7": hexid,
            "status_churn": "estavel",
            "nota_wellhub": 4.5,
            "qtd_avaliacoes_wellhub": 120,
            "v6": 0.6,
            "pressao_competitiva": 60.0,
            "pressao_grao": "academia",
            "sinais_disponiveis": "s1,s6",
            "n_sinais_disponiveis": 2,
            "score_vulnerabilidade": 54.0,
            "score_vulnerabilidade_ordenavel": 54.0,
            "flag_score_provisorio": False,
            # AUDITORIA da pressao (BLK-MA-18): 4 concorrentes que valem 1,5 EFETIVOS. A distancia
            # entre os dois numeros e' o ponto — sem ela, `60,0` nao e' conferivel no mapa.
            "n_concorrentes_no_raio": 4,
            "n_independentes_no_raio": 3,
            "oferta_ponderada": 1.5,
            "dist_concorrente_mais_proximo_m": 640.0,
            "versao_contrato": "alvos_ma_nomeados_v3",
        }
        for i, (nome, hexid) in enumerate(
            [("Academia Alfa", HEX_SP[0]), ("Academia Beta", HEX_SP[0]), ("Gama Fit", HEX_SP[1])]
        )
    ]
    df = pd.DataFrame(linhas)
    for col, dtype in (
        ("nota_wellhub", "Float64"),
        ("qtd_avaliacoes_wellhub", "Int64"),
        ("pressao_competitiva", "Float64"),
        ("n_concorrentes_no_raio", "Int64"),
        ("n_independentes_no_raio", "Int64"),
        ("oferta_ponderada", "Float64"),
        ("dist_concorrente_mais_proximo_m", "Float64"),
    ):
        df[col] = df[col].astype(dtype)
    return df


@pytest.fixture
def com_independentes(synth_data: Path) -> Path:  # noqa: F811
    staging = synth_data / "staging"
    staging.mkdir(parents=True, exist_ok=True)
    _nomeadas().to_parquet(staging / "vulnerabilidade_ma_nomeadas.parquet", index=False)
    pilot.carregar_independentes.cache_clear()
    pilot.carregar_uf.cache_clear()
    return synth_data


# --------------------------------------------------------------------------- #
# Degradação
# --------------------------------------------------------------------------- #
def test_sem_artefato_a_camada_nao_esta_disponivel(synth_data: Path) -> None:  # noqa: F811
    bloco = _muni()["independentes"]
    assert bloco["disponivel"] is False
    assert bloco["itens"] == []


def test_com_artefato_os_pins_chegam(com_independentes: Path) -> None:
    bloco = _muni()["independentes"]
    assert bloco["disponivel"] is True
    assert bloco["total"] == 3
    nomes = {p["nome"] for p in bloco["itens"]}
    assert nomes == {"Academia Alfa", "Academia Beta", "Gama Fit"}


def test_o_pin_carrega_os_numeros_da_academia(com_independentes: Path) -> None:
    """É o pedido original: passar o mouse na unidade e ver o score."""
    pin = next(p for p in _muni()["independentes"]["itens"] if p["nome"] == "Academia Alfa")
    assert pin["score"] == pytest.approx(54.0)
    assert pin["pressao"] == pytest.approx(60.0)
    # Nota e contagem SEMPRE juntas (DEC-026).
    assert pin["nota"] == pytest.approx(4.5)
    assert pin["n_aval"] == 120
    assert pin["regime"] == "s1,s6"
    assert pin["provisorio"] is False


def test_academia_LONGE_de_outro_municipio_nao_entra(com_independentes: Path) -> None:
    """O recorte é por hexágono do município MAIS a margem do raio da pressão (DEC-035).

    **Este teste mudou de enunciado no BLK-MA-17 metade 1.** Antes ele afirmava "o recorte é por
    hexágono do município" e usava Campinas — mas na fixture sintética São Paulo e Campinas ficam a
    **~1,5 km** um do outro (`0.01` grau), enquanto os municípios reais estão a ~90 km. Ou seja, a
    fixture não distinguia "outro município" de "fora do alcance", e o teste passava por acidente de
    geometria sintética.

    A regra correta é a da DEC-035: entra quem está no município **ou** dentro de `PIN_MARGEM_M` do
    recorte, porque o raio de 2 km da pressão atravessa divisa municipal e quem está do outro lado
    CONTA na conta do tooltip. Fora dessa margem, continua fora — que é o que este teste prova.
    """
    longe = _nomeadas()
    longe["lat"] = -22.0  # ~170 km ao norte: fora de qualquer margem
    # E o hex TAMBEM sai do municipio: o recorte e' `hex ∈ sel` **OU** margem, entao mover so' a
    # coordenada deixaria o ramo do hex casando e o teste provaria o contrario do que diz.
    longe["hex_id_res7"] = "87a9900000000ffff"
    longe.to_parquet(
        com_independentes / "staging" / "vulnerabilidade_ma_nomeadas.parquet", index=False
    )
    pilot.carregar_independentes.cache_clear()

    assert _muni("Sao Paulo")["independentes"]["total"] == 0


def test_academia_do_municipio_VIZINHO_dentro_do_raio_ENTRA(com_independentes: Path) -> None:
    """A correção da DEC-035, e a razão de ela existir.

    A auditoria do pin promete "conta os pins no mapa e o número fecha". Antes desta metade, quem
    estava do outro lado da divisa entrava em `n_concorrentes_no_raio` e **não era desenhado** —
    medido em SP: a conta já não fechava em 16,4% dos casos, por esta causa e mais duas.

    Na fixture, as academias vivem nos hexes de São Paulo e Campinas está a ~1,5 km: dentro da
    margem. Antes, `total` era `0` aqui; agora elas aparecem no recorte de Campinas, que é
    exatamente o comportamento que faz a conta fechar.
    """
    assert _muni("Campinas")["independentes"]["total"] > 0


def test_academia_sem_coordenada_nao_vira_pin(com_independentes: Path) -> None:
    """Ela existe no artefato (tem score), mas não é desenhável."""
    df = _nomeadas()
    df.loc[df["nome"] == "Gama Fit", ["lat", "lng"]] = None
    df.to_parquet(com_independentes / "staging" / "vulnerabilidade_ma_nomeadas.parquet", index=False)
    pilot.carregar_independentes.cache_clear()
    nomes = {p["nome"] for p in _muni()["independentes"]["itens"]}
    assert "Gama Fit" not in nomes
    assert len(nomes) == 2


# --------------------------------------------------------------------------- #
# Separação dos universos e fronteira
# --------------------------------------------------------------------------- #
def test_pins_de_independente_NAO_se_misturam_aos_de_concorrente(com_independentes: Path) -> None:
    """Universos de semântica oposta: quem disputa x quem se compra.

    A interseção entre eles é vazia por construção — o universo de M&A exclui cadeias. Se as duas
    listas virassem uma, uma Smart Fit apareceria com cara de alvo de aquisição.
    """
    payload = _muni()
    assert "independentes" in payload
    assert payload["independentes"]["itens"] is not payload["pins"]["concorrentes"]
    nomes_indep = {p["nome"] for p in payload["independentes"]["itens"]}
    nomes_conc = {p["nome"] for p in payload["pins"]["concorrentes"]}
    assert not (nomes_indep & nomes_conc)


def test_payload_nao_carrega_dado_de_pessoa(com_independentes: Path) -> None:
    """A emenda autorizou identidade de ESTABELECIMENTO. §11 segue vedando o resto."""
    proibidos = {"review", "autor", "autor_review", "cpf", "email", "telefone", "chave_snapshot"}
    for pin in _muni()["independentes"]["itens"]:
        assert not (set(pin) & proibidos), set(pin)


def test_truncamento_e_declarado(com_independentes: Path, monkeypatch) -> None:
    """Corte silencioso mentiria sobre a densidade do recorte."""
    monkeypatch.setattr(pilot, "COMPETITOR_PIN_LIMIT", 1)
    pilot.carregar_independentes.cache_clear()
    bloco = _muni()["independentes"]
    assert bloco["truncado"] is True
    assert bloco["total"] == 3
    assert len(bloco["itens"]) == 1


def test_health_observa_o_artefato_nomeado(com_independentes: Path) -> None:
    assert pilot.health()["artefatos"]["independentes_nomeadas"]["ok"] is True


# --------------------------------------------------------------------------- #
# BLK-MA-18 — a conta por trás da pressão
# --------------------------------------------------------------------------- #
def test_o_pin_carrega_a_conta_por_tras_da_pressao(com_independentes: Path) -> None:
    """Sem isto, `60,0` é um número que o operador não tem como conferir.

    A saturação gasta metade da escala numa única unidade equivalente, então o valor exibido não é
    "60% de pressão" — é `1,5 concorrentes efetivos`. A contagem crua ao lado permite bater com o
    que se vê no mapa; a distância explica a diferença entre as duas.
    """
    pin = next(p for p in _muni()["independentes"]["itens"] if p["nome"] == "Academia Alfa")
    assert pin["n_conc"] == 4
    assert pin["n_indep"] == 3
    assert pin["oferta"] == 1.5
    assert pin["dist_m"] == 640.0


def test_sem_auditoria_no_artefato_o_pin_nao_inventa_zero(com_independentes: Path) -> None:
    """Artefato antigo (sem as colunas) degrada para nulo — nunca para `0 concorrentes`.

    `0` afirmaria território livre; a ausência diz que ninguém mediu. É a mesma regra do `v6`.
    """
    df = _nomeadas().drop(
        columns=[
            "n_concorrentes_no_raio",
            "n_independentes_no_raio",
            "oferta_ponderada",
            "dist_concorrente_mais_proximo_m",
        ]
    )
    df.to_parquet(com_independentes / "staging" / "vulnerabilidade_ma_nomeadas.parquet", index=False)
    pilot.carregar_independentes.cache_clear()
    pin = _muni()["independentes"]["itens"][0]
    assert pin["n_conc"] is None
    assert pin["oferta"] is None
    assert pin["dist_m"] is None
    # O resto do pin continua servido: a auditoria e' opcional, o score nao.
    assert pin["score"] == 54.0
