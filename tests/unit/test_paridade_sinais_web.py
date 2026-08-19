"""Todo sinal do contrato tem rótulo de tela, e nenhum rótulo descreve sinal extinto.

O acoplamento é por string literal e o modo de falha é MUDO nos dois sentidos:

  * **Sinal sem rótulo** — ele aparece CRU no tooltip (`s5`). Acontece exatamente no PR em que
    alguém liga um sinal novo: o trabalho de ativar o sinal é celebrado e a tela estreia com um
    código sem significado. O `s2` é o caso concreto à espera: basta o BLK-MA-08 removê-lo de
    `SINAIS_INATIVOS` para ele passar a viajar no payload.
  * **Rótulo órfão** — descreve um sinal que o contrato não emite mais. Pior que o primeiro: a
    tela não fica feia, fica desatualizada com ar de vigente.

Por que em Python e não no vitest: quem mexe em `SINAIS_ORDEM` roda o pytest, não o `npm run test`
do `web/`. Mesma técnica de parse textual de `test_paridade_classe_crescimento_web.py`.

READ-ONLY: lê o TS e as constantes, não escreve nada.
"""

from __future__ import annotations

import re
from pathlib import Path

from motor_expansao.vulnerabilidade.contrato import SINAIS_INATIVOS, SINAIS_ORDEM

_REPO = Path(__file__).resolve().parents[2]
_SINAIS_TS = _REPO / "web" / "src" / "lib" / "sinais.ts"

# `  s1: {` — abre a entrada de um sinal no mapa `SINAIS`.
_ENTRADA = re.compile(r"^\s*(s\d+):\s*\{", re.MULTILINE)


def _sinais_do_ts() -> set[str]:
    fonte = _SINAIS_TS.read_text(encoding="utf-8")
    inicio = fonte.index("export const SINAIS")
    fim = fonte.index("\n}", inicio)
    return set(_ENTRADA.findall(fonte[inicio:fim]))


def test_todo_sinal_do_contrato_tem_rotulo() -> None:
    faltando = sorted(set(SINAIS_ORDEM) - _sinais_do_ts())
    assert not faltando, (
        f"sinais sem rotulo em `web/src/lib/sinais.ts`: {faltando}. Eles apareceriam CRUS no "
        "tooltip ('s5' em vez de um nome), e a linha que explica o que foi medido deixaria de "
        "explicar."
    )


def test_nenhum_rotulo_descreve_sinal_extinto() -> None:
    """O inverso, e o pior dos dois: régua morta com ar de vigente."""
    sobrando = sorted(_sinais_do_ts() - set(SINAIS_ORDEM))
    assert not sobrando, (
        f"rotulo para sinal fora de SINAIS_ORDEM: {sobrando}. A ordem canonica vive em "
        "`contrato.py` — se o sinal saiu de la, o rotulo tem de sair daqui."
    )


def test_o_sinal_inativo_tambem_tem_rotulo() -> None:
    """O `s2` nunca chega à tela hoje — e é exatamente por isso que ele precisa do rótulo agora.

    O mapa é do CONTRATO, não do que está ativo. No dia em que o BLK-MA-08 o remover de
    `SINAIS_INATIVOS`, ele passa a viajar no payload; sem rótulo, estrearia cru.
    """
    assert set(SINAIS_INATIVOS) <= _sinais_do_ts()
