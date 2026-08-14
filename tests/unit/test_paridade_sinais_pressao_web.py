"""Trava a paridade do vocabulário de SINAIS entre o contrato Python e a tela (BLK-MA-13).

O modo de falha é MUDO, e é o mesmo da paridade de `cres_hex_classe`: o overlay declara no
tooltip e na legenda **sob qual régua** o número foi composto, traduzindo `sinais_disponiveis`
(`"s1,s6"`) por um mapa de rótulos em `web/src/lib/pressao-ma.ts`. Um sinal que exista no
contrato e não exista naquele mapa sai CRU na tela (`s5`) — feio, mas visível; o inverso, um
rótulo que descreve um sinal que o contrato não emite mais, é pior: descreve uma régua morta com
ar de vigente.

Declarar o regime não é enfeite. Réguas de regimes diferentes **não são comparáveis entre si**
(emenda BLK-MA-04-FU1): um `{s1,s6}` e um `{s1,s3,s4}` renormalizam pesos de formas diferentes, e
comparar dois hexágonos sem saber disso é o erro que a linha do tooltip existe para evitar.

Por que em Python e não no vitest: quem mexe em `SINAIS_ORDEM`/`SINAIS_INATIVOS` roda o pytest, não
o `npm run test` do `web/`. Mesma técnica de parse textual de `test_paridade_classe_crescimento_web`.

READ-ONLY: lê os dois arquivos, não escreve nada.
"""

from __future__ import annotations

import re
from pathlib import Path

from motor_expansao.vulnerabilidade.contrato import SINAIS_ORDEM

_REPO = Path(__file__).resolve().parents[2]
_PRESSAO_TS = _REPO / "web" / "src" / "lib" / "pressao-ma.ts"

# `  s1: 'presença em agregador',`
_ENTRADA = re.compile(r"^\s*(s\d+):\s*'([^']+)'", re.MULTILINE)


def _rotulos_do_ts() -> dict[str, str]:
    fonte = _PRESSAO_TS.read_text(encoding="utf-8")
    inicio = fonte.index("export const SINAL_ROTULO")
    fim = fonte.index("}", inicio)
    return dict(_ENTRADA.findall(fonte[inicio:fim]))


def test_todo_sinal_do_contrato_tem_rotulo_de_tela() -> None:
    rotulos = _rotulos_do_ts()
    faltando = [s for s in SINAIS_ORDEM if s not in rotulos]
    assert not faltando, (
        f"sinais sem rotulo em pressao-ma.ts: {faltando}. Eles apareceriam CRUS no tooltip "
        "('s5' em vez de um nome), e a declaracao de regime deixaria de informar."
    )


def test_nenhum_rotulo_descreve_sinal_que_o_contrato_nao_emite() -> None:
    """O inverso, e é o pior dos dois: régua morta com ar de vigente."""
    rotulos = _rotulos_do_ts()
    sobrando = sorted(set(rotulos) - set(SINAIS_ORDEM))
    assert not sobrando, (
        f"rotulo para sinal fora de SINAIS_ORDEM: {sobrando}. A ordem canonica vive em "
        "`contrato.py` — se o sinal saiu de la, o rotulo tem de sair daqui."
    )


def test_o_inativo_tambem_tem_rotulo() -> None:
    """O `s2` está em `SINAIS_INATIVOS` e nunca chega à tela hoje.

    O mapa é do CONTRATO, não do que está ativo: o dia em que o BLK-MA-08 remover o `s2` daquela
    tupla, o sinal passa a viajar no payload — e sem rótulo ele estrearia cru na tela, no mesmo
    PR em que alguém estaria comemorando ter ligado o sinal.
    """
    assert "s2" in _rotulos_do_ts()


def test_nenhum_rotulo_usa_vocabulario_de_vulnerabilidade() -> None:
    """DEC-028: enquanto S3/S4 estiverem imaturos, nada nesta camada se chama vulnerabilidade."""
    texto = " ".join(_rotulos_do_ts().values()).lower()
    for proibido in ("vulnerab", "alvo", "aquisi"):
        assert proibido not in texto, f"vocabulario proibido pela DEC-028 no rotulo: {proibido}"
