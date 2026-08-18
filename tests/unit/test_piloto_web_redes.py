"""Pins das unidades de REDE do agregador no piloto (BLK-MA-17 metade 1 / DEC-035).

O que esta suíte protege:

  * **A decisão da DEC-035: fato sim, score não.** O payload destas unidades não pode ter `score`
    nem `ordenavel`. S1 mede política comercial (a negociação com o agregador é centralizada) e S3
    é correlacionado — top 5 = 48,4% das unidades, máx 440 numa rede: a Panobianco saindo do WellHub
    viraria 440 `sumiu_recente` no mesmo dia. Se o score vazar para cá, a tela passa a afirmar sobre
    redes o que esses sinais não sabem.
  * **A precedência de pin.** Só as unidades sem equivalente em `concorrentes_mapeados`
    (`tem_pin_proprio`) são desenhadas. As outras já têm o pin do funil no mesmo endereço, e um
    segundo pin ali faria a contagem do tooltip parar de fechar — o defeito que esta metade veio
    corrigir.
  * **A separação dos três universos.** `pins.concorrentes` (cadeia mapeada pelo site da rede),
    `redes` (cadeia listada só pelo agregador) e `independentes` são listas próprias. Juntar as duas
    primeiras esconderia justamente a lacuna que a DEC-034 mediu: 1.171 unidades sem pin.
  * **A degradação silenciosa.** Sem o artefato, `redes.disponivel` é `False` e o piloto abre como
    antes — o CI não tem esse parquet.
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


def _redes() -> pd.DataFrame:
    """Três unidades de rede: duas com pin próprio, uma já coberta pelo funil."""
    linhas = [
        {
            "fonte": "wellhub",
            "chave_snapshot": f"r{i}",
            "nome": nome,
            "rede": rede,
            "lat": -23.55 + 0.001 * i,
            "lng": -46.63,
            "hex_id_res7": HEX_SP[0],
            "status_churn": "estavel",
            "nota_wellhub": 4.2,
            "qtd_avaliacoes_wellhub": 88,
            "pressao_competitiva": 72.0,
            "pressao_grao": "academia",
            "universo_oferta": "cadeias_e_independentes",
            "n_concorrentes_no_raio": 9,
            "n_independentes_no_raio": 7,
            "n_cadeias_do_feed_no_raio": 1,
            "oferta_ponderada": 2.6,
            "dist_concorrente_mais_proximo_m": 310.0,
            "tem_pin_proprio": pin,
            "versao_contrato": "redes_ma_nomeadas_v2",
        }
        for i, (nome, rede, pin) in enumerate(
            [
                ("Bluefit Centro", "bluefit", True),
                ("Selfit Norte", "selfit", True),
                ("Smart Fit Colada", "smart_fit", False),
            ]
        )
    ]
    df = pd.DataFrame(linhas)
    for col, dtype in (
        ("nota_wellhub", "Float64"),
        ("qtd_avaliacoes_wellhub", "Int64"),
        ("pressao_competitiva", "Float64"),
        ("n_concorrentes_no_raio", "Int64"),
        ("n_independentes_no_raio", "Int64"),
        ("n_cadeias_do_feed_no_raio", "Int64"),
        ("oferta_ponderada", "Float64"),
        ("dist_concorrente_mais_proximo_m", "Float64"),
        ("tem_pin_proprio", "boolean"),
    ):
        df[col] = df[col].astype(dtype)
    return df


@pytest.fixture
def com_redes(synth_data: Path) -> Path:  # noqa: F811
    staging = synth_data / "staging"
    staging.mkdir(parents=True, exist_ok=True)
    _redes().to_parquet(staging / "vulnerabilidade_ma_redes.parquet", index=False)
    pilot.carregar_redes.cache_clear()
    pilot.carregar_uf.cache_clear()
    return synth_data


# --------------------------------------------------------------------------- #
# Degradação                                                                   #
# --------------------------------------------------------------------------- #
def test_sem_artefato_a_camada_nao_esta_disponivel(synth_data: Path) -> None:  # noqa: F811
    pilot.carregar_redes.cache_clear()
    bloco = _muni()["redes"]
    assert bloco["disponivel"] is False
    assert bloco["itens"] == []


def test_com_artefato_os_pins_chegam(com_redes: Path) -> None:
    bloco = _muni()["redes"]
    assert bloco["disponivel"] is True
    assert len(bloco["itens"]) > 0


# --------------------------------------------------------------------------- #
# A decisão da DEC-035: fato sim, score não                                    #
# --------------------------------------------------------------------------- #
def test_o_payload_do_pin_de_rede_NAO_tem_score(com_redes: Path) -> None:
    """A trava da decisão, no ponto em que ela chega ao usuário."""
    itens = _muni()["redes"]["itens"]
    assert itens
    for item in itens:
        assert "score" not in item, "score vazou para o pin de REDE (DEC-035)"
        assert "ordenavel" not in item
        assert "provisorio" not in item


def test_o_pin_de_rede_exibe_pressao_e_os_fatos(com_redes: Path) -> None:
    """O que a DEC-035 autoriza: S6 (geográfico) + os três fatos sem peso."""
    item = _muni()["redes"]["itens"][0]
    assert item["pressao"] == pytest.approx(72.0)
    assert item["nota"] == pytest.approx(4.2)
    assert item["n_aval"] == 88
    assert item["churn"] == "estavel"
    assert item["rede"]
    assert item["nome"]


def test_a_auditoria_da_pressao_chega_completa_no_pin_de_rede(com_redes: Path) -> None:
    """As três parcelas + oferta + distância. Sem elas o número não é conferível."""
    item = _muni()["redes"]["itens"][0]
    assert item["n_conc"] == 9
    assert item["n_indep"] == 7
    assert item["n_cadeias_feed"] == 1
    assert item["oferta"] == pytest.approx(2.6)
    assert item["dist_m"] == pytest.approx(310.0)


# --------------------------------------------------------------------------- #
# Precedência de pin — herdada da dedup da DEC-034                             #
# --------------------------------------------------------------------------- #
def test_so_as_unidades_SEM_equivalente_no_funil_viram_pin(com_redes: Path) -> None:
    """`tem_pin_proprio=False` já tem o pin do funil: desenhar de novo daria dois no mesmo lugar."""
    bloco = _muni()["redes"]
    nomes = {i["nome"] for i in bloco["itens"]}
    assert nomes == {"Bluefit Centro", "Selfit Norte"}
    assert "Smart Fit Colada" not in nomes, (
        "unidade COLAPSADA na dedup foi desenhada — o tooltip volta a nao fechar"
    )
    assert bloco["total"] == 2


# --------------------------------------------------------------------------- #
# Os três universos são listas próprias                                        #
# --------------------------------------------------------------------------- #
def test_redes_e_uma_lista_separada_de_concorrentes_e_independentes(com_redes: Path) -> None:
    """Juntá-las esconderia a lacuna que a DEC-034 mediu (1.171 unidades sem pin)."""
    dados = _muni()
    assert "redes" in dados
    assert "independentes" in dados
    assert "concorrentes" in dados["pins"]

    nomes_rede = {i["nome"] for i in dados["redes"]["itens"]}
    nomes_conc = {i.get("nome") for i in dados["pins"]["concorrentes"]}
    assert nomes_rede & nomes_conc == set(), "a mesma unidade apareceu nas duas listas"


# --------------------------------------------------------------------------- #
# A coluna que faltava no pin de INDEPENDENTE (BLK-MA-18 -> DEC-035)           #
# --------------------------------------------------------------------------- #
def test_o_pin_de_independente_ganhou_a_terceira_parcela_da_conta() -> None:
    """`n_cadeias_feed` existia no artefato desde a DEC-034 e não chegava à tela.

    Sem ela, `n_conc` não fecha com `n_indep` + pins de cadeia e a explicação não está em lugar
    nenhum — medido: 7.218 de 19.329 linhas (37,3%) têm a parcela maior que zero.
    """
    assert "n_cadeias_do_feed_no_raio" in pilot._COLS_NOMEADAS
