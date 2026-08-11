"""Contrato do estilo `ultra-labels`: HIERARQUIA tipografica do overlay de rotulos.

O overlay (`openmaptiles-infra/data/styles/ultra-labels/style.json`) e' composto POR CIMA do
choropleth no Relatorio Pontual E no Relatorio Municipal. Ele nao passava por nenhum teste:
e' JSON servido pelo tileserver, entao um erro so aparecia no PDF, tarde e visualmente.

O defeito REAL que este contrato tranca (BLK-BASEMAP-07): o `rotulo-bairro` estava em 24/34/40 px
com tinta a 8% de luminosidade -- MAIOR e MAIS ESCURO que o nome de avenida (18/26/32 a 12%). O
nome de bairro e' referencia de CONTEXTO; o dado e' a cor do choropleth. Com a hierarquia
invertida, o texto virava o assunto do mapa e cobria justamente o que o relatorio existe para
mostrar.

DOIS ZOOMS, DOIS RELATORIOS -- e' o eixo que a primeira versao deste contrato errou. O Pontual
renderiza o mosaico em z15 (frame de 2,29 km); o Municipal, em z11-z13 (dezenas de km). Baixar o
rotulo de bairro nos stops BAIXOS quebraria o Municipal, onde o rotulo de `place` e' o nome do
MUNICIPIO e deve mesmo dominar -- e onde a `rotulo-via-secundaria` (minzoom 15) nem desenha. Por
isso `city`/`town`/`village` vivem em `rotulo-localidade`, camada propria, que NAO e' subordinada
as vias. A subordinacao vale so para `rotulo-bairro` (suburb/neighbourhood/quarter).

Cobre:
  (a) JSON valido e `id` de camada unico (id repetido faz o MapLibre descartar a duplicata em
      silencio, e a camada simplesmente nao desenha);
  (b) o rotulo de bairro nao e' maior nem mais escuro que o nome de via principal, avaliado por
      AMOSTRAGEM de zoom -- nao exigindo stops identicos, que sao naturalmente divergentes neste
      arquivo (`rotulo-via-secundaria` usa {15,17}, `rotulo-agua` {12,16});
  (c) `rotulo-localidade` PRESERVA a proeminencia (>= via principal) nos zooms do Municipal;
  (d) nenhum rotulo de CONTEXTO (bairro, agua) passa o nome de via principal -- a agua ja tinha
      furado essa regra em z15;
  (e) piso ABSOLUTO de corpo: subordinar nao pode virar sumir. O BLK-BASEMAP-06 calibrou os
      tamanhos como piso absoluto e uma checagem so RELATIVA passaria com 4/6/8 px;
  (f) todo rotulo de contexto tem `text-max-width` (nome longo quebra em vez de virar faixa
      horizontal atravessando o frame);
  (g) as camadas de simbolo vem DEPOIS das de linha, senao a malha viaria desenha sobre os nomes.

Se este teste falhar, alguem mexeu na tipografia do overlay sem olhar a hierarquia. O criterio, a
calibragem medida e a armadilha do `@2x` estao no `metadata` do estilo
(`ultra:hierarquia-do-bairro`, `ultra:calibragem-vigente`).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ESTILO = (
    Path(__file__).resolve().parents[2]
    / "openmaptiles-infra"
    / "data"
    / "styles"
    / "ultra-labels"
    / "style.json"
)

# Zooms REAIS de render, medidos em `ultra:calibragem-vigente` e por `_zoom_for_bounds`:
# Municipal cai em z11-z13; Pontual (frame de 2,29 km) em z15.
ZOOMS_MUNICIPAL = (11, 12, 13)
ZOOMS_PONTUAL = (14, 15, 16, 17)
ZOOMS = ZOOMS_MUNICIPAL + ZOOMS_PONTUAL

# Corpo minimo em STYLE px nos zooms do Pontual. Com o fator `@2x` vigente (x1,216 style->PNG),
# 18 style px chegam ao PNG com ~22 px -- piso, nao alvo.
PISO_STYLE_PX = 18.0

# Rotulos de CONTEXTO: existem para orientar, nunca para competir com o dado (a cor) nem com a
# malha viaria. `rotulo-localidade` NAO entra aqui: nome de municipio deve dominar.
CONTEXTO = ("rotulo-bairro", "rotulo-agua")


@pytest.fixture(scope="module")
def estilo() -> dict:
    assert ESTILO.is_file(), f"estilo do overlay nao encontrado em {ESTILO}"
    return json.loads(ESTILO.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def camadas(estilo: dict) -> dict[str, dict]:
    return {c["id"]: c for c in estilo["layers"]}


def _tamanho(camada: dict, zoom: float) -> float:
    """`text-size` da camada NO zoom dado, interpolando o `["interpolate", ["linear"], ...]`.

    Avaliar por zoom (e nao comparar listas de stops) e' o que permite comparar camadas com
    conjuntos de stops diferentes -- o normal neste arquivo.
    """
    expr = camada["layout"]["text-size"]
    assert expr[0] == "interpolate", f"{camada['id']}: text-size deixou de ser interpolate"
    pares = expr[3:]
    zs = [float(pares[i]) for i in range(0, len(pares), 2)]
    ss = [float(pares[i + 1]) for i in range(0, len(pares), 2)]
    if zoom <= zs[0]:
        return ss[0]
    if zoom >= zs[-1]:
        return ss[-1]
    for i in range(len(zs) - 1):
        if zs[i] <= zoom <= zs[i + 1]:
            fatia = (zoom - zs[i]) / (zs[i + 1] - zs[i])
            return ss[i] + (ss[i + 1] - ss[i]) * fatia
    raise AssertionError(f"{camada['id']}: zoom {zoom} fora dos stops {zs}")


def _luminosidade(camada: dict) -> float:
    """Luminosidade do `hsl(H,S%,L%)`: quanto MAIOR, mais claro -> menos peso visual."""
    cor = camada["paint"]["text-color"]
    assert cor.startswith("hsl(") and cor.endswith("%)"), f"{camada['id']}: cor inesperada: {cor}"
    return float(cor.rsplit(",", 1)[1].removesuffix("%)"))


def test_ids_de_camada_sao_unicos(estilo: dict) -> None:
    ids = [c["id"] for c in estilo["layers"]]
    assert len(ids) == len(set(ids)), f"id de camada repetido: {sorted(ids)}"


@pytest.mark.parametrize("zoom", ZOOMS)
def test_contexto_nao_e_maior_que_a_via_principal(camadas: dict[str, dict], zoom: int) -> None:
    via = _tamanho(camadas["rotulo-via-principal"], zoom)
    for cid in CONTEXTO:
        assert _tamanho(camadas[cid], zoom) <= via, (
            f"z{zoom}: `{cid}` ({_tamanho(camadas[cid], zoom):.1f} px) ficou MAIOR que o nome de "
            f"via principal ({via:.1f} px) -- hierarquia invertida, o contexto cobre o dado"
        )


def test_bairro_nao_e_mais_escuro_que_a_via_principal(camadas: dict[str, dict]) -> None:
    bairro = _luminosidade(camadas["rotulo-bairro"])
    via = _luminosidade(camadas["rotulo-via-principal"])
    assert bairro >= via, (
        f"tinta do bairro ({bairro}%) mais ESCURA que a da via principal ({via}%) -- "
        "peso visual invertido"
    )


@pytest.mark.parametrize("zoom", ZOOMS_MUNICIPAL)
def test_localidade_mantem_proeminencia_no_municipal(camadas: dict[str, dict], zoom: int) -> None:
    """Nome de MUNICIPIO nao pode ser subordinado a nome de rua.

    Nos zooms do Relatorio Municipal a `rotulo-via-secundaria` (minzoom 15) nem desenha, entao o
    rotulo de `place` e' a unica ancora geografica do mapa. Foi exatamente o que a primeira versao
    do BLK-BASEMAP-07 quebrou, ao cortar `city`/`town` junto com `suburb`.
    """
    localidade = _tamanho(camadas["rotulo-localidade"], zoom)
    via = _tamanho(camadas["rotulo-via-principal"], zoom)
    assert localidade >= via, (
        f"z{zoom}: nome de municipio ({localidade:.1f} px) ficou MENOR que o nome de via "
        f"principal ({via:.1f} px) -- no Relatorio Municipal isso apaga a unica referencia "
        f"geografica do mapa"
    )


@pytest.mark.parametrize("zoom", ZOOMS_PONTUAL)
def test_bairro_tem_piso_absoluto_de_corpo(camadas: dict[str, dict], zoom: int) -> None:
    """Subordinar o bairro as vias nao pode virar apaga-lo.

    As checagens de hierarquia sao RELATIVAS e passariam com 4/6/8 px; a unica outra trava
    numerica do repo mede densidade de mosaico e nem le este arquivo.
    """
    px = _tamanho(camadas["rotulo-bairro"], zoom)
    assert px >= PISO_STYLE_PX, (
        f"z{zoom}: rotulo de bairro com {px:.1f} style px, abaixo do piso de {PISO_STYLE_PX} "
        f"-- no PNG final chega com ~{px * 1.216:.0f} px e some no PDF"
    )


@pytest.mark.parametrize("cid", CONTEXTO)
def test_rotulo_de_contexto_quebra_nome_longo(camadas: dict[str, dict], cid: str) -> None:
    largura = camadas[cid]["layout"].get("text-max-width")
    assert largura is not None, (
        f"`text-max-width` ausente em `{cid}`: nome longo volta a virar faixa horizontal "
        f"atravessando o frame (o padrao do MapLibre e' 10 em)"
    )
    assert largura <= 8, f"`text-max-width` {largura} alto demais para quebrar nome longo"


def test_simbolos_desenham_por_cima_das_linhas(estilo: dict) -> None:
    tipos = [c["type"] for c in estilo["layers"]]
    ultima_linha = max(i for i, t in enumerate(tipos) if t == "line")
    primeiro_simbolo = min(i for i, t in enumerate(tipos) if t == "symbol")
    assert primeiro_simbolo > ultima_linha, (
        "camada de simbolo antes de uma camada de linha: a malha viaria passa a desenhar por "
        "cima dos nomes"
    )
