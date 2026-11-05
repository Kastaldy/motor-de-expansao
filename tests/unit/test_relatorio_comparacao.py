"""Deck de comparação: o que ele imprime tem de casar com a TELA de onde saiu.

Duas travas:

- **A unidade de dinheiro** (achado a-03 da conferência de 2026-10-29). A tela manda em
  `porDimensao[].unidade` as sentinelas de `web/src/lib/format.ts` (`UNIDADE_RENDA` e
  `UNIDADE_MOEDA`), e o deck as lê de volta. Até 2026-10-29 o deck comparava com o literal
  `"R$"`, que a tela deixou de mandar em 2026-09-02: desde então a renda saía SEM símbolo no
  PDF, também no Brasil.
- **A paleta de identidade.** O comentário de `CORES_ITEM` sempre disse que este arquivo a
  travava junto com a da tela; o arquivo não existia.

As sentinelas e a paleta são LIDAS do TypeScript, e não repetidas aqui: a trava é contra a
tela de verdade, não contra uma cópia que envelheceria junto com o deck.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from motor_expansao.dashboard import relatorio_comparacao as rc
from motor_expansao.perfil import Moeda

_REPO = Path(__file__).resolve().parents[2]
_FORMAT_TS = _REPO / "web" / "src" / "lib" / "format.ts"
_COMPARACAO_TS = _REPO / "web" / "src" / "lib" / "comparacao.ts"


def _sentinela(nome: str) -> str:
    """O valor da sentinela como a TELA o declara."""
    m = re.search(rf"export const {nome} = '([^']+)'", _FORMAT_TS.read_text(encoding="utf-8"))
    assert m, f"{nome} sumiu de web/src/lib/format.ts"
    return m.group(1)


def test_a_renda_sai_com_o_simbolo_no_brasil() -> None:
    assert rc._valor_com_unidade(4500.0, _sentinela("UNIDADE_RENDA")) == "R$ 4.500"
    assert rc._valor_com_unidade(4500.0, _sentinela("UNIDADE_MOEDA")) == "R$ 4.500"


def test_na_argentina_a_renda_sai_em_usd(monkeypatch: pytest.MonkeyPatch) -> None:
    """Moeda oficial ARS e renda do pacote em USD: "$" seria o símbolo do peso sobre dólar."""
    ar = SimpleNamespace(moeda=Moeda(codigo="ARS", simbolo="$", indicadores_renda="USD"))
    monkeypatch.setattr(rc, "resolver_perfil", lambda: ar)
    assert rc._valor_com_unidade(508.0, _sentinela("UNIDADE_RENDA")) == "USD 508"
    assert rc._valor_com_unidade(508.0, _sentinela("UNIDADE_MOEDA")) == "$ 508"


def test_as_outras_unidades_nao_mudam() -> None:
    assert rc._valor_com_unidade(None, _sentinela("UNIDADE_RENDA")) == "-"
    assert rc._valor_com_unidade(12.34, "%") == "12,3%"
    assert rc._valor_com_unidade(71.26, "score") == "71,3"
    assert rc._valor_com_unidade(1234.0, "alunos") == "1.234"


def test_a_paleta_do_deck_e_a_da_tela() -> None:
    """Se a tela mudar de cor e o PDF não, o relatório deixa de casar com a tela de onde saiu."""
    texto = _COMPARACAO_TS.read_text(encoding="utf-8")
    bloco = re.search(r"export const CORES_IDENTIDADE = \[(.*?)\] as const", texto, re.S)
    assert bloco, "CORES_IDENTIDADE sumiu de web/src/lib/comparacao.ts"
    tela = [
        tuple(int(cor[i : i + 2], 16) for i in (0, 2, 4))
        for cor in re.findall(r"'#([0-9A-Fa-f]{6})'", bloco.group(1))
    ]
    assert tela == list(rc.CORES_ITEM)
    assert len(rc.CORES_ITEM) == rc.MAX_ITENS
