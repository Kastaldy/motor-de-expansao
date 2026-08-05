"""Trava o vocabulario de `cres_hex_classe` nas TRES pontas em que ele viaja.

O acoplamento e por string literal e o modo de falha e MUDO: `crescClasseToColor`
(`web/src/lib/colors.ts`) compara a classe contra literais e, se nenhum casar, cai no
`return [...CRESC_SEM]` — cinza de "sem medicao". Renomear a classe em qualquer uma
das pontas pinta a camada 4 inteira de cinza sem erro, sem log e sem teste vermelho.

As tres pontas:

  1. PRODUTOR  `data/reports/crescimento/08_populacao_e_hex.py` (`CORTES`) grava o
     identificador ASCII no parquet;
  2. BACKEND   `web/server/app.py` (`_ROTULO_CLASSE`) traduz o identificador no rotulo
     acentuado que a API envia;
  3. FRONT     `colors.ts` (`crescClasseToColor`) compara esse rotulo para escolher a cor.

Este teste liga 1→2 (as chaves do dicionario sao exatamente os cortes gravados) e 2→3
(os literais do TypeScript sao exatamente os valores que a API envia). Sem o elo 1→2 a
normalizacao do parquet passaria batida; sem o 2→3, a renomeacao de um rotulo.

Por que em Python e nao no vitest: quem mexe no gerador ou no backend roda o pytest,
nao o `npm run test` do `web/`. Mesmo argumento — e mesma tecnica de parse textual —
de `test_paridade_faixa_labels_web.py` e `tests/contracts/test_faixas_mapa_espelho.py`.

READ-ONLY: le os tres arquivos, nao escreve nada.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_COLORS_TS = _REPO / "web" / "src" / "lib" / "colors.ts"
_GERADOR = _REPO / "data" / "reports" / "crescimento" / "08_populacao_e_hex.py"
_SERVER = _REPO / "web" / "server"

if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

# O piloto web so existe na branch do piloto; sem ele nao ha contrato a travar.
pytestmark = pytest.mark.skipif(
    not (_REPO / "web" / "src").is_dir(),
    reason="piloto web (web/src) ausente nesta arvore — nada a comparar",
)


def _rotulo_classe() -> dict[str, str]:
    import app as pilot

    return dict(pilot._ROTULO_CLASSE)


def _literais_do_front() -> list[str]:
    """Literais comparados dentro de `crescClasseToColor`, na ordem em que aparecem."""
    assert _COLORS_TS.is_file(), (
        f"{_COLORS_TS.relative_to(_REPO).as_posix()} nao existe.\n"
        "Se o modulo foi movido, atualize ESTE teste — ele e a unica trava entre o "
        "vocabulario da API e a cor do mapa na camada 4."
    )
    fonte = _COLORS_TS.read_text(encoding="utf-8")
    m = re.search(
        r"export function crescClasseToColor\s*\([^)]*\)\s*:\s*RGBA\s*\{(?P<corpo>.*?)\n\}",
        fonte,
        re.DOTALL,
    )
    assert m, "nao achei `crescClasseToColor` em colors.ts — a assinatura mudou?"
    return re.findall(r"classe\s*===\s*'([^']+)'", m.group("corpo"))


def _cortes_do_gerador() -> list[str]:
    """Nomes de classe gravados no parquet por `CORTES`, no `08_populacao_e_hex.py`."""
    assert _GERADOR.is_file(), f"{_GERADOR} nao existe — o gerador foi movido?"
    fonte = _GERADOR.read_text(encoding="utf-8")
    m = re.search(r"^CORTES\s*=\s*\[(?P<corpo>.*?)\]\s*$", fonte, re.DOTALL | re.MULTILINE)
    assert m, "nao achei `CORTES` no gerador — a constante foi renomeada?"
    return re.findall(r'"([^"]+)"\s*\)', m.group("corpo"))


# ------------------------------------------------------------- 1 -> 2 (parquet/backend)
def test_o_backend_traduz_exatamente_as_classes_que_o_gerador_grava() -> None:
    gravadas = set(_cortes_do_gerador())
    traduzidas = set(_rotulo_classe())
    assert gravadas == traduzidas, (
        "o gerador e o backend discordam sobre o vocabulario bruto de `cres_hex_classe`.\n"
        f"  so no gerador (08_populacao_e_hex.py): {sorted(gravadas - traduzidas)}\n"
        f"  so no backend  (_ROTULO_CLASSE)      : {sorted(traduzidas - gravadas)}\n"
        "Classe gravada sem entrada no mapa chega crua ao front e nao casa cor nenhuma."
    )


def test_o_identificador_gravado_nao_tem_acento() -> None:
    """CLAUDE.md §2: valor bruto de enum e chave de comparacao, nao texto de tela.

    Era exatamente esta a divida — `cres_hex_classe` saia "Estável" enquanto o irmao
    `cres_tendencia` saia "Estavel", e os dois apareciam no mesmo balao de tooltip.
    """
    acentuadas = [c for c in _cortes_do_gerador() if not c.isascii()]
    assert not acentuadas, (
        f"o gerador grava identificador acentuado: {acentuadas}. "
        "O acento vive no rotulo de exibicao (`_ROTULO_CLASSE`), nao no parquet."
    )


# ---------------------------------------------------------------- 2 -> 3 (backend/front)
def test_o_front_compara_exatamente_os_rotulos_que_a_api_envia() -> None:
    do_front = set(_literais_do_front())
    da_api = set(_rotulo_classe().values())
    assert do_front == da_api, (
        "`crescClasseToColor` e a API discordam sobre o rotulo de `cres_hex_classe`.\n"
        f"  so no front (colors.ts)        : {sorted(do_front - da_api)}\n"
        f"  so na API   (_ROTULO_CLASSE)   : {sorted(da_api - do_front)}\n"
        "Rotulo sem par cai no fallback cinza: a camada 4 inteira fica 'sem medicao'."
    )


def test_o_fallback_cinza_continua_existindo() -> None:
    """A funcao PRECISA degradar: ha hexagono legitimamente sem medicao (fora das 12
    UFs cobertas ou fora da mancha urbana). O que este teste garante e que o cinza
    seja o caminho do DESCONHECIDO, nao o caminho de todos."""
    fonte = _COLORS_TS.read_text(encoding="utf-8")
    m = re.search(
        r"export function crescClasseToColor\s*\([^)]*\)\s*:\s*RGBA\s*\{(?P<corpo>.*?)\n\}",
        fonte,
        re.DOTALL,
    )
    assert m and "CRESC_SEM" in m.group("corpo"), (
        "`crescClasseToColor` perdeu o fallback de 'sem medicao' — hexagono sem "
        "leitura passaria a nao ter cor definida."
    )
