"""Benchmark por coorte de maturidade (BLK-EXEC-04).

O que estes testes protegem, alem da conta: a **DEC-014**. O eixo territorial de retencao
deu NO-GO e a parte previsivel do desempenho e' o tempo de operacao, nao o lugar. Ha um
teste de AST aqui justamente para que a geografia nao volte pela porta dos fundos.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pandas as pd
import pytest

from motor_expansao.dashboard import rede_coorte as rc


def _rede(quantidades: dict[str, int], **extras: object) -> pd.DataFrame:
    """Uma linha por unidade, com `meses_operacao` no meio de cada coorte pedida."""
    meio = {"0_5": 3, "6_11": 8, "12_23": 18, "24_47": 36, "48_mais": 60}
    linhas: list[dict[str, object]] = []
    contador = 0
    for coorte, quantidade in quantidades.items():
        for _ in range(quantidade):
            contador += 1
            linhas.append(
                {
                    "unidade_id": f"u{contador:03d}",
                    "competencia": "2026-07",
                    "meses_operacao": float(meio[coorte]),
                    "mes_completo": True,
                    "operacao_mes_cheio": True,
                    "faturamento": 100_000.0 + 1_000.0 * contador,
                    "churn_pct": 5.0,
                    **extras,
                }
            )
    return rc.anotar_coortes(pd.DataFrame(linhas))


@pytest.mark.parametrize(
    "meses, esperado",
    [
        (0, "0_5"),
        (5, "0_5"),
        (6, "6_11"),
        (11, "6_11"),
        (12, "12_23"),
        (23, "12_23"),
        (24, "24_47"),
        (47, "24_47"),
        (48, "48_mais"),
        (240, "48_mais"),
        (None, "indefinida"),
        (float("nan"), "indefinida"),
        (-1, "indefinida"),
    ],
)
def test_atribuir_coorte(meses: object, esperado: str) -> None:
    assert rc.atribuir_coorte(meses) == esperado


def test_escada_de_degradacao() -> None:
    """coorte propria (n >= 8) -> coorte vizinha -> rede toda -> sem dado."""
    # Coorte propria grande o bastante: usa a propria.
    rede = _rede({"12_23": 12, "24_47": 12})
    assert rc.comparar(rede, "u001", ["faturamento"]).degradacao == "coorte"

    # Coorte propria pequena (3 pares descontando a propria unidade) -> vizinha.
    rede = _rede({"12_23": 4, "24_47": 12})
    comparacao = rc.comparar(rede, "u001", ["faturamento"])
    assert comparacao.degradacao == "coorte_vizinha"
    assert comparacao.n == 12

    # Nem a propria nem a vizinha tem pares: cai na rede toda.
    rede = _rede({"0_5": 3, "6_11": 2, "12_23": 12})
    comparacao = rc.comparar(rede, "u001", ["faturamento"])
    assert comparacao.degradacao == "rede"

    # Rede inteira pequena demais: assume "sem dado" em vez de fingir precisao.
    rede = _rede({"12_23": 3})
    assert rc.comparar(rede, "u001", ["faturamento"]).degradacao == "sem_dado"


def test_degradacao_e_sempre_servida() -> None:
    """Licao do `fonte_base_calibracao`: degradar em silencio muda o significado do numero.

    O degrau usado vai no payload E no PDF, sempre -- inclusive no caminho feliz.
    """
    rede = _rede({"12_23": 12})
    for unidade in rede["unidade_id"]:
        comparacao = rc.comparar(rede, unidade, ["faturamento"])
        assert comparacao.degradacao in rc.ROTULO_DEGRADACAO
        assert comparacao.base_rotulo == rc.ROTULO_DEGRADACAO[comparacao.degradacao]
    ausente = rc.comparar(rede, "nao-existe", ["faturamento"])
    assert ausente.degradacao == "sem_dado"


def test_a_unidade_nao_entra_na_propria_referencia() -> None:
    rede = _rede({"12_23": 10})
    comparacao = rc.comparar(rede, "u001", ["faturamento"])
    assert comparacao.n == 9
    assert comparacao.referencias["faturamento"].n == 9


def test_peer_set_exclui_mes_incompleto_e_unidade_nova() -> None:
    rede = _rede({"12_23": 12})
    rede.loc[rede["unidade_id"] == "u002", "mes_completo"] = False
    rede.loc[rede["unidade_id"] == "u003", "operacao_mes_cheio"] = False
    rede = rc.anotar_coortes(rede)
    assert int(rede["no_peer_set"].sum()) == 10
    assert rc.comparar(rede, "u001", ["faturamento"]).n == 9


def test_percentil_e_relativo_aos_pares() -> None:
    rede = _rede({"24_47": 10})
    percentis = rc.comparar(rede, "u001", ["faturamento"]).percentis
    assert percentis["faturamento"] == pytest.approx(0.0), "a de menor faturamento e' o piso"
    percentis = rc.comparar(rede, "u010", ["faturamento"]).percentis
    assert percentis["faturamento"] == pytest.approx(100.0)


def test_coorte_ignora_filtro_da_tela() -> None:
    """O peer set sai da rede INTEIRA, jamais do recorte filtrado.

    Filtrar "master = PR" e comparar contra 2 pares seria ruido -- e reintroduziria a
    geografia que a DEC-014 tirou. O modulo nem sequer aceita um recorte: quem chama passa
    o mes inteiro.
    """
    rede_toda = _rede({"24_47": 20})
    referencia = rc.comparar(rede_toda, "u001", ["faturamento"])
    recorte = rede_toda[rede_toda["unidade_id"].isin(["u001", "u002", "u003"])]
    # Comparar contra o recorte mudaria a referencia; a assinatura obriga a passar a rede.
    assert rc.comparar(recorte, "u001", ["faturamento"]).degradacao == "sem_dado"
    assert referencia.degradacao == "coorte"
    assert referencia.n == 19


def test_maturidade_indefinida_cai_direto_na_rede() -> None:
    rede = _rede({"12_23": 12})
    rede.loc[rede["unidade_id"] == "u001", "meses_operacao"] = None
    rede = rc.anotar_coortes(rede)
    comparacao = rc.comparar(rede, "u001", ["faturamento"])
    assert comparacao.coorte == rc.COORTE_INDEFINIDA
    assert comparacao.degradacao == "rede"
    assert bool(rede.set_index("unidade_id").loc["u001", "no_peer_set"]) is False


def test_resumo_de_coortes_mantem_a_ordem_de_maturidade() -> None:
    rede = _rede({"24_47": 3, "0_5": 2, "12_23": 1})
    assert [c["chave"] for c in rc.resumo_coortes(rede)] == ["0_5", "12_23", "24_47"]
    assert [c["n"] for c in rc.resumo_coortes(rede)] == [2, 1, 3]


def test_rede_vazia_nao_quebra() -> None:
    vazio = rc.anotar_coortes(pd.DataFrame())
    assert not len(vazio)
    assert rc.resumo_coortes(vazio) == []
    assert rc.comparar(vazio, "qualquer", ["faturamento"]).degradacao == "sem_dado"


def test_benchmark_nao_usa_geografia() -> None:
    """DEC-014 escrita em codigo: o modulo nao pode referenciar eixo territorial nenhum.

    Um teste de prosa envelhece; este falha no CI no minuto em que alguem escrever
    `df["uf"]` aqui dentro para "melhorar" a comparacao.
    """
    fonte = Path(rc.__file__).read_text(encoding="utf-8")
    arvore = ast.parse(fonte)
    proibidos = {"lat", "lng", "uf", "cidade", "municipio", "estado", "regiao", "hex_id"}
    ofensas: list[tuple[str, int]] = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.Constant) and isinstance(no.value, str):
            if no.value.lower() in proibidos:
                ofensas.append((no.value, no.lineno))
        if isinstance(no, ast.Attribute) and no.attr.lower() in proibidos:
            ofensas.append((no.attr, no.lineno))
        if isinstance(no, ast.Name) and no.id.lower() in proibidos:
            ofensas.append((no.id, no.lineno))
    assert not ofensas, f"coorte e' por MATURIDADE, nao por geografia (DEC-014): {ofensas}"
