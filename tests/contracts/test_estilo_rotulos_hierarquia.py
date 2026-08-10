"""Contrato do estilo `ultra-labels`: HIERARQUIA tipografica do overlay de rotulos.

O overlay (`openmaptiles-infra/data/styles/ultra-labels/style.json`) e' composto POR CIMA do
choropleth no Relatorio Pontual e no Relatorio Municipal. Ele nao passa por nenhum teste hoje:
e' JSON servido pelo tileserver, entao um erro so aparece no PDF, tarde e visualmente.

O defeito REAL que este contrato tranca (2026-08): o `rotulo-bairro` estava em 24/34/40 px com
tinta a 8% de luminosidade -- MAIOR e MAIS ESCURO que o nome de avenida (18/26/32 a 12%). O
nome de bairro e' referencia de CONTEXTO; o dado e' a cor do choropleth. Com a hierarquia
invertida, o texto virava o assunto do mapa e cobria justamente o que o relatorio existe para
mostrar. Nao havia nada que impedisse a regressao -- nem teste, nem revisao automatica.

Cobre:
  (a) o JSON e' valido e as camadas tem `id` unico (um `id` repetido faz o MapLibre descartar
      a duplicata em silencio, e a camada simplesmente nao desenha);
  (b) o rotulo de bairro NAO e' maior que o nome de via principal em nenhum stop de zoom;
  (c) o rotulo de bairro NAO e' mais escuro que o nome de via principal;
  (d) o bairro tem `text-max-width` -- e' o que faz nome longo QUEBRAR em vez de virar uma
      faixa horizontal atravessando o frame;
  (e) as camadas de simbolo vem DEPOIS das de linha, senao a malha viaria desenha por cima
      dos nomes.

Se este teste falhar, alguem mexeu na tipografia do overlay sem olhar a hierarquia. O criterio
e o historico da calibragem estao no proprio `metadata` do estilo (`ultra:hierarquia-do-bairro`
e `ultra:calibragem-vigente`).
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

# Luminosidade de `hsl(0,0%,L%)`: quanto MAIOR, mais claro -> menos peso visual.
_LUMINOSIDADE = {"rotulo-bairro": None, "rotulo-via-principal": None}


@pytest.fixture(scope="module")
def estilo() -> dict:
    assert ESTILO.is_file(), f"estilo do overlay nao encontrado em {ESTILO}"
    return json.loads(ESTILO.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def camadas(estilo: dict) -> dict[str, dict]:
    return {c["id"]: c for c in estilo["layers"]}


def _stops(camada: dict) -> dict[int, float]:
    """Extrai `{zoom: tamanho}` de um `["interpolate", ["linear"], ["zoom"], z0, s0, ...]`."""
    expr = camada["layout"]["text-size"]
    assert expr[0] == "interpolate", f"{camada['id']}: text-size deixou de ser interpolate"
    pares = expr[3:]
    return {int(pares[i]): float(pares[i + 1]) for i in range(0, len(pares), 2)}


def _luminosidade(camada: dict) -> float:
    cor = camada["paint"]["text-color"]
    assert cor.startswith("hsl(0,0%,"), f"{camada['id']}: cor fora do padrao cinza: {cor}"
    return float(cor.removeprefix("hsl(0,0%,").removesuffix("%)"))


def test_ids_de_camada_sao_unicos(estilo: dict) -> None:
    ids = [c["id"] for c in estilo["layers"]]
    assert len(ids) == len(set(ids)), f"id de camada repetido: {sorted(ids)}"


def test_bairro_nao_e_maior_que_a_via_principal(camadas: dict[str, dict]) -> None:
    bairro = _stops(camadas["rotulo-bairro"])
    via = _stops(camadas["rotulo-via-principal"])
    assert bairro.keys() == via.keys(), (
        "as duas camadas precisam compartilhar os mesmos stops de zoom para serem comparaveis; "
        f"bairro={sorted(bairro)} via={sorted(via)}"
    )
    for zoom in sorted(bairro):
        assert bairro[zoom] <= via[zoom], (
            f"z{zoom}: rotulo de bairro ({bairro[zoom]} px) ficou MAIOR que o nome de via "
            f"principal ({via[zoom]} px) -- hierarquia invertida, o contexto cobre o dado"
        )


def test_bairro_nao_e_mais_escuro_que_a_via_principal(camadas: dict[str, dict]) -> None:
    bairro = _luminosidade(camadas["rotulo-bairro"])
    via = _luminosidade(camadas["rotulo-via-principal"])
    assert bairro >= via, (
        f"tinta do bairro ({bairro}%) mais ESCURA que a da via principal ({via}%) -- "
        "peso visual invertido"
    )


def test_bairro_quebra_nome_longo(camadas: dict[str, dict]) -> None:
    largura = camadas["rotulo-bairro"]["layout"].get("text-max-width")
    assert largura is not None, (
        "`text-max-width` ausente no rotulo-bairro: nome longo volta a virar faixa horizontal "
        "atravessando o frame (o padrao do MapLibre e' 10 em)"
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
