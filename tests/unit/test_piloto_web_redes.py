"""Unidades de REDE do agregador no mapa (BLK-MA-17 metade 1, revisado em 2026-08-18).

**O que mudou, e por quê.** Na primeira versão estas unidades eram uma camada própria: ponto
circular azul, lista separada no payload e uma chave de liga/desliga. Não é o que elas são — uma
academia de rede é uma academia de rede, e dar-lhes outra forma obrigava o operador a ligar um
toggle para enxergar concorrência que sempre esteve lá.

Agora elas são **bandeira quadrada com a logo da rede, como todas as outras**, e entram na mesma
lista `pins.concorrentes`. O que as distingue não é a natureza, é o **dado extra** que temos sobre
elas — e isso vira um **halo** em volta do quadrado, mais um bloco no tooltip.

O que esta suíte protege:

  * **Elas são constantes, não opcionais.** Não existe chave, e a lista separada sumiu do payload.
  * **A bandeira é a da rede.** As 83 redes do feed têm logo cadastrado (medido: 100%), então
    nenhuma cai no quadrado de sigla — e a borda de 7 px continua sendo a cor da marca.
  * **O halo é uma variante de ícone, não uma cor de dado.** Chave `<rede>__diag` no dicionário de
    ícones, e o front cai no ícone normal se ela faltar.
  * **`diag` não traz score.** A decisão da DEC-035 vale igual: numa rede, presença e churn medem
    negociação da marca.
  * **A precedência continua valendo.** Só entra quem não tem equivalente em
    `concorrentes_mapeados` — desenhar as colapsadas daria duas bandeiras no mesmo lugar, que
    agora é erro VISÍVEL.
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
    """Três unidades: duas com pin próprio, uma já coberta por bandeira do funil."""
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


def _com_diag(dados: dict) -> list[dict]:
    return [p for p in dados["pins"]["concorrentes"] if p.get("diag")]


# --------------------------------------------------------------------------- #
# Constante, não opcional                                                      #
# --------------------------------------------------------------------------- #
def test_nao_existe_mais_lista_separada_nem_chave(com_redes: Path) -> None:
    """A camada própria saiu do payload: concorrência instalada não é liga/desliga."""
    dados = _muni()
    assert "redes" not in dados, "a lista separada deveria ter sumido do payload"
    assert _com_diag(dados), "as unidades do agregador tem de estar em pins.concorrentes"


def test_a_unidade_do_agregador_e_uma_BANDEIRA_como_as_outras(com_redes: Path) -> None:
    """Mesma lista e mesmo contrato de item — o que muda é a flag e o que ela agrega.

    As cinco chaves testadas são o contrato do pin de concorrente: é por elas que o `IconLayer`
    posiciona (`lat`/`lng`), escolhe a logo (`rede`) e monta o balão (`label`/`nome`). Se a unidade
    do agregador perdesse qualquer uma, ela deixaria de ser desenhável como bandeira — que é o
    ponto todo desta revisão.
    """
    diag = _com_diag(_muni())
    assert diag
    for chave in ("lat", "lng", "rede", "label", "nome"):
        assert chave in diag[0], f"a bandeira do agregador perdeu `{chave}`"
    assert diag[0]["rede"], "sem `rede` nao ha logo para desenhar"
    assert diag[0]["label"], "o balao mostra o `label`, nao o slug"


def test_sem_o_artefato_o_mapa_fica_como_antes(synth_data: Path) -> None:  # noqa: F811
    """Degradação: o CI não tem esse parquet, e o piloto tem de abrir igual."""
    pilot.carregar_redes.cache_clear()
    dados = _muni()
    assert _com_diag(dados) == []
    assert "concorrentes" in dados["pins"]


# --------------------------------------------------------------------------- #
# O halo                                                                        #
# --------------------------------------------------------------------------- #
def test_o_icone_com_halo_e_servido_para_as_redes_que_tem_diagnostico(com_redes: Path) -> None:
    """Chave `<rede>__diag` no dicionário, e SÓ para quem tem unidade com diagnóstico."""
    dados = _muni()
    icones = dados["pins"]["icones"]
    redes_diag = {p["rede"] for p in _com_diag(dados)}
    assert redes_diag, "premissa: ha unidade com diagnostico no recorte"
    for r in redes_diag:
        assert f"{r}{pilot.SUFIXO_ICONE_DIAG}" in icones, f"falta o icone com halo de {r}"


def test_o_halo_nao_e_servido_para_rede_sem_diagnostico(com_redes: Path) -> None:
    """Gerar as 107 variantes sempre dobraria o atlas de textura sem ninguém usar."""
    dados = _muni()
    redes_diag = {p["rede"] for p in _com_diag(dados)}
    com_halo = {k.removesuffix(pilot.SUFIXO_ICONE_DIAG) for k in dados["pins"]["icones"] if k.endswith(pilot.SUFIXO_ICONE_DIAG)}
    assert com_halo == redes_diag


def test_o_icone_com_halo_preserva_a_cor_da_rede(com_redes: Path) -> None:
    """A borda de 7 px é a identidade da marca — o halo é um anel EXTERNO, não a substitui."""
    import base64 as b64
    import urllib.parse

    from motor_expansao.dashboard.competitors import COMPETITOR_BRANDS

    normal = pilot._icone_rede("bluefit")
    com_halo = pilot._icone_rede("bluefit", halo=True)
    assert normal != com_halo

    def _svg(uri: str) -> str:
        dados = uri.split(",", 1)[1]
        return (
            b64.b64decode(dados).decode("utf-8")
            if ";base64" in uri
            else urllib.parse.unquote(dados)
        )

    svg = _svg(com_halo)
    assert str(COMPETITOR_BRANDS["bluefit"]["bg"]) in svg, "a cor da rede sumiu do icone com halo"
    assert pilot.HALO_DIAGNOSTICO in svg, "o halo nao foi desenhado"
    assert 'viewBox="0 0 160 160"' in svg, "o viewBox tem de crescer para caber o anel externo"


# --------------------------------------------------------------------------- #
# O dado extra, e o que ele NÃO traz                                           #
# --------------------------------------------------------------------------- #
def test_a_bandeira_com_diag_carrega_pressao_e_fatos(com_redes: Path) -> None:
    p = _com_diag(_muni())[0]
    assert p["pressao"] == pytest.approx(72.0)
    assert p["nota"] == pytest.approx(4.2)
    assert p["n_aval"] == 88
    assert p["churn"] == "estavel"
    assert p["n_conc"] == 9
    assert p["n_indep"] == 7
    assert p["n_cadeias_feed"] == 1
    assert p["oferta"] == pytest.approx(2.6)
    assert p["dist_m"] == pytest.approx(310.0)


def test_a_bandeira_com_diag_NAO_carrega_score(com_redes: Path) -> None:
    """A trava da DEC-035, no ponto em que o dado chega ao usuário."""
    for p in _com_diag(_muni()):
        assert "score" not in p, "score vazou para a bandeira do agregador (DEC-035)"
        assert "ordenavel" not in p


# --------------------------------------------------------------------------- #
# Precedência — agora um erro VISÍVEL                                          #
# --------------------------------------------------------------------------- #
def test_unidade_colapsada_na_dedup_NAO_vira_segunda_bandeira(com_redes: Path) -> None:
    """`tem_pin_proprio=False` já tem bandeira do funil naquele endereço.

    Antes isto era um detalhe interno; desde que estas unidades usam a MESMA forma dos demais
    concorrentes, desenhá-las de novo põe duas bandeiras da mesma rede coladas no mapa.
    """
    nomes = {p["nome"] for p in _com_diag(_muni())}
    assert nomes == {"Bluefit Centro", "Selfit Norte"}
    assert "Smart Fit Colada" not in nomes


def test_o_pin_de_independente_continua_com_a_terceira_parcela() -> None:
    assert "n_cadeias_do_feed_no_raio" in pilot._COLS_NOMEADAS
