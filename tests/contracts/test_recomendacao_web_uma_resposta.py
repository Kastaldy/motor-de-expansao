"""Contrato: o Top 10 da recomendacao unica (DEC-077) e' UMA resposta, qualquer que seja a porta.

A tela pergunta "onde expandir?" por tres rotas -- o drill-down do municipio
(`/api/municipio`), a visao do estado (`/api/uf`) e Oportunidades (`/api/hexagonos`). Se duas
delas derem Top 10 diferentes para o MESMO recorte, o usuario ve duas recomendacoes e nao tem
como saber qual vale: e' a familia de defeito que a recomendacao unica existe para matar (a
fila do mapa, o ranking nacional e o PDF ja recomendaram coisas diferentes para o mesmo lugar).

Por construcao, as rotas usam a MESMA selecao (`_recorte_do_municipio`/`carregar_uf`) e a
MESMA funcao (`_recomendacao_do_recorte`). Este contrato trava o resultado: mesmos hex_ids,
mesmos segmentos, mesma ordem, mesmas vagas vazias e o mesmo recorte carimbado. E a
invariancia de recorte: quem esta no Top 10 do Brasil esta no Top 10 da propria UF, no mesmo
segmento.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.unit.test_piloto_web_recomendacao_top10 import (  # noqa: F401
    SEGMENTOS,
    _assinatura,
    pilot,
    top10_data,
    top10_e3,
    top10_e3_staging,
)


def _anti_vacuidade(bloco: dict) -> None:
    for segmento in SEGMENTOS:
        assert any(not v["vazia"] for v in bloco[segmento]["vagas"]), (
            f"fixture sem {segmento} preenchido: o contrato compararia vagas vazias"
        )


def test_mesmo_top10_em_municipio_e_hexagonos(top10_data: Path) -> None:  # noqa: F811
    for municipio in ("Sao Paulo", "Campinas"):
        da_tela = pilot.municipio("SP", municipio)["recomendacao"]
        de_oportunidades = pilot.hexagonos(uf="SP", municipio=municipio)["recomendacao"]
        _anti_vacuidade(da_tela)
        assert _assinatura(da_tela) == _assinatura(de_oportunidades), municipio
        assert da_tela["recorte"] == de_oportunidades["recorte"]
        # Nao so' a ordem: o bloco inteiro (numeros, nomes, regua, renda) e' o mesmo.
        assert da_tela == de_oportunidades


def test_mesmo_top10_em_uf_e_hexagonos(top10_data: Path) -> None:  # noqa: F811
    da_tela = pilot.uf_view("SP")["recomendacao"]
    de_oportunidades = pilot.hexagonos(uf="SP")["recomendacao"]
    _anti_vacuidade(da_tela)
    assert _assinatura(da_tela) == _assinatura(de_oportunidades)
    assert da_tela["recorte"] == de_oportunidades["recorte"]
    assert da_tela == de_oportunidades


def test_top10_do_brasil_cai_no_top10_da_propria_uf(top10_data: Path) -> None:  # noqa: F811
    """A regra nao depende do recorte: o melhor do pais e' melhor tambem dentro da UF dele."""
    brasil = pilot.hexagonos()["recomendacao"]
    _anti_vacuidade(brasil)
    por_uf: dict[str, dict] = {}
    for segmento in SEGMENTOS:
        for vaga in brasil[segmento]["vagas"]:
            if vaga["vazia"]:
                continue
            uf = vaga["uf"]
            if uf not in por_uf:
                por_uf[uf] = pilot.uf_view(uf)["recomendacao"]
            ids_da_uf = [v["hex_id"] for v in por_uf[uf][segmento]["vagas"] if not v["vazia"]]
            assert vaga["hex_id"] in ids_da_uf, (
                f"{vaga['hex_id']} esta no Top 10 do Brasil ({segmento}) e fora do Top 10 de {uf}"
            )
    assert len(por_uf) >= 2, "fixture: o Top 10 do Brasil deveria cruzar mais de uma UF"


#: Campos da vaga que dependem do RECORTE por definicao: a posicao no segmento e o rotulo da
#: regiao (que desempata nomes repetidos dentro do Top 10 daquele recorte).
_DEPENDEM_DO_RECORTE = frozenset({"posicao", "nome_regiao"})


def _bairro_dominante(vaga: dict) -> str | None:
    nome = vaga["nome_regiao"]
    return nome.split(" / ")[0] if nome else None


@pytest.mark.parametrize("cenario", ["top10_data", "top10_e3", "top10_e3_staging"])
def test_brasil_e_uf_mostram_a_mesma_vaga(cenario: str, request: pytest.FixtureRequest) -> None:
    """O Top 10 do Brasil le por OUTRO leitor (`_ler_base_recomendacao_brasil`, pyarrow sobre
    `_COLS_RECOMENDACAO`) que a UF (`carregar_uf`). O mesmo hexagono tem de sair com a MESMA
    vaga nas duas portas -- renda, populacao, residual, score, nome, coordenada --, nao so' o
    mesmo hex_id: um leitor que perdesse as colunas da malha (E3) ou mudasse o tipo de
    `cod_municipio` daria outra renda (e poderia mudar quem passa na Mata Virgem) sem que a
    assinatura acusasse. Com a E3 no artefato e so' no staging, tambem.
    """
    request.getfixturevalue(cenario)
    brasil = pilot.hexagonos()["recomendacao"]
    _anti_vacuidade(brasil)
    por_uf: dict[str, dict] = {}
    comparadas = 0
    for segmento in SEGMENTOS:
        for vaga in brasil[segmento]["vagas"]:
            if vaga["vazia"]:
                continue
            uf = vaga["uf"]
            if uf not in por_uf:
                por_uf[uf] = pilot.hexagonos(uf=uf)["recomendacao"]
            par = next(v for v in por_uf[uf][segmento]["vagas"] if v["hex_id"] == vaga["hex_id"])
            assert {k: x for k, x in vaga.items() if k not in _DEPENDEM_DO_RECORTE} == {
                k: x for k, x in par.items() if k not in _DEPENDEM_DO_RECORTE
            }, vaga["hex_id"]
            # O rotulo desempata nomes repetidos DENTRO do Top 10 ("A / B"), entao pode ganhar
            # o 2o bairro num recorte e nao no outro; o bairro dominante e' o mesmo.
            assert _bairro_dominante(vaga) == _bairro_dominante(par), vaga["hex_id"]
            comparadas += 1
    assert comparadas >= 5, "fixture: poucas vagas comparadas para o contrato valer"
