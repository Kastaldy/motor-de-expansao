"""Trava os vocabulários do card "Crescimento da concorrência" entre o servidor e a tela.

O acoplamento é por string literal e o modo de falha é MUDO (achado da revisão de 05/11/2026): um
estado de variação que o servidor passe a emitir e a tela não conheça cai no `default` de
`celulaVariacao` e vira "—" sem erro; um motivo de "sem cadastro" desconhecido faz
`motivoSemCadastro` devolver `null`, e a linha volta a mostrar 0 aberturas onde o fato é "o pacote
não sabe". Este teste liga as duas pontas:

  1. SERVIDOR  `saldo_rede` (`STATUS_VARIACAO_TELA`, `MOTIVOS_RECUSA`, `DIRECOES_SALTO`) e
     `movimentacao_concorrencia` (`MOTIVOS_SEM_CADASTRO`, `ERROS_CONTAGEM`);
  2. TELA      `web/src/lib/types.ts` (as uniões dos campos) e
     `web/src/lib/crescimento-concorrencia.ts` (um ramo para cada valor).

Em Python, e não no vitest, pela razão de `test_paridade_classe_crescimento_web.py`: quem mexe no
servidor roda o pytest. READ-ONLY: só lê os arquivos.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from motor_expansao.dashboard import movimentacao_concorrencia as mov
from motor_expansao.dashboard import saldo_rede as s

_REPO = Path(__file__).resolve().parents[2]
_TYPES = _REPO / "web" / "src" / "lib" / "types.ts"
_LIB = _REPO / "web" / "src" / "lib" / "crescimento-concorrencia.ts"

pytestmark = pytest.mark.skipif(
    not _LIB.is_file(), reason="piloto web (web/src) ausente nesta árvore — nada a comparar"
)


def _interface(nome: str) -> str:
    texto = _TYPES.read_text(encoding="utf-8")
    inicio = texto.find(f"export interface {nome} {{")
    assert inicio != -1, f"interface {nome} sumiu de types.ts: atualize ESTE teste"
    return texto[inicio : texto.find("\n}", inicio)]


def _uniao(interface: str, campo: str) -> set[str]:
    """Os literais da união de `campo` dentro de `interface` (aceita a união em várias linhas)."""
    bloco = _interface(interface)
    m = re.search(rf"^\s*{campo}\??:((?:[^\n]*\n?)(?:\s*\|[^\n]*\n?)*)", bloco, re.M)
    assert m, f"{interface}.{campo} sumiu de types.ts"
    return set(re.findall(r"'([^']+)'", m.group(1)))


def _funcao(nome: str) -> str:
    texto = _LIB.read_text(encoding="utf-8")
    inicio = texto.find(f"export function {nome}(")
    assert inicio != -1, f"{nome} sumiu de crescimento-concorrencia.ts"
    return texto[inicio : texto.find("\n}\n", inicio)]


def test_estado_da_variacao_tem_tipo_e_ramo_na_tela() -> None:
    assert _uniao("RedeCrescimentoRede", "variacao_status") == set(s.STATUS_VARIACAO_TELA)
    casos = set(re.findall(r"case '([^']+)':", _funcao("celulaVariacao")))
    assert casos == set(s.STATUS_VARIACAO_TELA), "todo estado precisa de um `case` em celulaVariacao"


def test_motivo_sem_cadastro_tem_tipo_e_explicacao_na_tela() -> None:
    assert _uniao("RedeCrescimentoRede", "sem_cadastro") == set(mov.MOTIVOS_SEM_CADASTRO)
    explicados = set(re.findall(r"sem_cadastro === '([^']+)'", _funcao("motivoSemCadastro")))
    assert explicados == set(mov.MOTIVOS_SEM_CADASTRO)


def test_motivo_da_recusa_erro_e_sentido_do_salto() -> None:
    assert _uniao("RedeContagemRecusada", "motivo") == set(s.MOTIVOS_RECUSA)
    assert _uniao("RedeContagemSemanal", "erro") == set(mov.ERROS_CONTAGEM)
    assert _uniao("RedeSaltoContagem", "direcao") == set(s.DIRECOES_SALTO)


def test_o_teste_le_o_que_diz_ler() -> None:
    """Contra o teste vácuo: se o parse quebrar, as uniões saem vazias e as igualdades acima
    falhariam — mas só se o lado Python não estiver vazio também."""
    assert len(s.STATUS_VARIACAO_TELA) >= 8 and len(mov.MOTIVOS_SEM_CADASTRO) >= 2
    assert "segurada" in _uniao("RedeCrescimentoRede", "variacao_status")
