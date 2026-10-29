"""O script que mede a régua da Síntese do Relatório Municipal (emenda de 2026-10-29 da DEC-011).

A régua da Síntese são tercis entre as cidades grandes, e a primeira saiu de uma base local, sem
script: na produção ela punha 247 das 313 cidades em "Mercado maduro". O script existe para a
próxima medição ser reproduzível, e estes testes travam as duas coisas que fazem a medição valer:
a CONTA (a mesma de `agregar_municipio`, conferida contra um cálculo feito à parte) e o PORTÃO
(que reprova uma conta ou um recorte diferentes dos do relatório).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from .test_relatorio_municipal import _sample_df

_REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "medir_regua_sintese", _REPO / "scripts" / "medir_regua_sintese.py"
)
assert _spec and _spec.loader
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)

#: (uf, município, hexágonos, consumo, residual, população de setor — None = sem setor,
#: `pop_total` por hexágono). Os totais são da cidade; cada hexágono leva uma fração igual.
_CIDADES = [
    ("SP", "Cidade A", 4, 6000.0, 4000.0, 1_000_000.0, None),
    ("SP", "Cidade B", 2, 3000.0, 7000.0, 200_000.0, None),
    ("SP", "Cidade C", 2, 4000.0, 4000.0, 150_000.0, None),
    ("RJ", "Cidade D", 3, 2000.0, 8000.0, 500_000.0, None),
    ("RJ", "Cidade E", 1, 900.0, 1100.0, 120_000.0, None),
    # Sem população de setor: recua para a SOMA de `pop_total` dos hexágonos, como
    # `agregar_municipio` (2 x 90.000 = 180.000, e por isso entra na régua).
    ("RJ", "Cidade F", 2, 500.0, 1500.0, None, 90_000.0),
    ("SP", "Cidade G", 1, 100.0, 100.0, 50_000.0, None),  # pequena: fica fora da régua
]
_NUMERICAS = (
    "oferta_consumida_mercado_estimada",
    "oferta_efetiva_disponivel",
    "pop_total_setor_2022",
    "pop_total",
)


def _escrever_base(raiz: Path) -> Path:
    """Base no formato do enriquecido: `uf=XX/parte-0.parquet`, colunas em float32 como a real."""
    linhas = []
    for uf, nome, n, consumo, residual, pop_setor, pop_total in _CIDADES:
        for _ in range(n):
            linhas.append(
                {
                    "uf": uf,
                    "nome_municipio": nome,
                    "cidade": nome,
                    "oferta_consumida_mercado_estimada": consumo / n,
                    "oferta_efetiva_disponivel": residual / n,
                    "pop_total_setor_2022": np.nan if pop_setor is None else pop_setor / n,
                    "pop_total": np.nan if pop_total is None else pop_total,
                }
            )
    df = pd.DataFrame(linhas)
    for coluna in _NUMERICAS:
        df[coluna] = df[coluna].astype("float32")
    base = raiz / "hexagonos_dashboard_enriquecido"
    for uf, parte in df.groupby("uf"):
        destino = base / f"uf={uf}"
        destino.mkdir(parents=True)
        parte.drop(columns="uf").to_parquet(destino / "parte-0.parquet", index=False)
    return base


def _esperado() -> tuple[int, tuple[float, ...], tuple[float, ...]]:
    """Os tercis calculados À PARTE, direto da tabela acima, sem passar pelo script."""
    pens, res_mil = [], []
    for _uf, _nome, n, consumo, residual, pop_setor, pop_total in _CIDADES:
        pop = pop_setor if pop_setor is not None else pop_total * n
        if pop < 100_000:
            continue
        pens.append(100 * consumo / (consumo + residual))
        res_mil.append(1000 * residual / pop)
    q = [1 / 3, 0.5, 2 / 3]
    return len(pens), tuple(np.quantile(pens, q)), tuple(np.quantile(res_mil, q))


def _base_com_sao_paulo(raiz: Path) -> Path:
    """A partição de SP com o quadro de exemplo dos testes do relatório (todas as colunas que
    `agregar_municipio` lê), para o portão rodar com a função DE VERDADE."""
    base = raiz / "enriquecido"
    (base / "uf=SP").mkdir(parents=True)
    _sample_df().to_parquet(base / "uf=SP" / "parte-0.parquet", index=False)
    return base


def test_a_conta_e_a_de_agregar_municipio(tmp_path: Path) -> None:
    base = _escrever_base(tmp_path)
    agg = m.agregar_por_municipio(m.ler_base(m.partes_da_base(base)))
    n, penetracao, residual_mil = _esperado()
    tercos = m.tercos(agg)
    assert tercos["n"] == n == 6
    assert tercos["penetracao"] == pytest.approx(penetracao, abs=1e-4)
    assert tercos["residual_mil"] == pytest.approx(residual_mil, abs=1e-4)


def test_cidade_sem_populacao_de_setor_recua_para_pop_total(tmp_path: Path) -> None:
    base = _escrever_base(tmp_path)
    agg = m.agregar_por_municipio(m.ler_base(m.partes_da_base(base)))
    cidade = agg.loc[("RJ", "cidade f")]
    assert cidade["pop"] == pytest.approx(180_000.0)
    assert cidade["res_mil"] == pytest.approx(1000 * 1500 / 180_000, rel=1e-6)


def test_o_portao_bate_com_a_funcao_do_relatorio(tmp_path: Path) -> None:
    base = _base_com_sao_paulo(tmp_path)
    partes = m.partes_da_base(base)
    agg = m.agregar_por_municipio(m.ler_base(partes))
    portao = m.portao(partes, agg, uf="SP", nome="SAO PAULO")
    assert portao["bate"], portao
    assert portao["n_relatorio"] == portao["n_script"] == 4
    # consumo 2.400 e residual 9.902 no quadro de exemplo
    assert portao["oficial"] == pytest.approx(100 * 2400 / (2400 + 9902))


def test_o_portao_reprova_conta_ou_recorte_diferentes(tmp_path: Path) -> None:
    """O portão só vale se reprovar: uma conta 0,01 p.p. fora (o dobro da tolerância) e um
    hexágono a mais no recorte têm de dar "não bate"."""
    base = _base_com_sao_paulo(tmp_path)
    partes = m.partes_da_base(base)
    agg = m.agregar_por_municipio(m.ler_base(partes))
    chave = ("SP", "sao paulo")
    conta_errada = agg.copy()
    conta_errada.loc[chave, "pen"] += 0.01
    assert not m.portao(partes, conta_errada, uf="SP", nome="SAO PAULO")["bate"]
    outro_recorte = agg.copy()
    outro_recorte.loc[chave, "n_hex"] += 1
    assert not m.portao(partes, outro_recorte, uf="SP", nome="SAO PAULO")["bate"]


def test_o_portao_reprova_cidade_que_nao_esta_na_base(tmp_path: Path) -> None:
    base = _escrever_base(tmp_path)
    partes = m.partes_da_base(base)
    agg = m.agregar_por_municipio(m.ler_base(partes))
    assert not m.portao(partes, agg, uf="SP", nome="São Paulo")["bate"]


def test_com_portao_reprovado_a_regua_nao_sai(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    base = _escrever_base(tmp_path)
    monkeypatch.setattr(m, "portao", lambda *_a, **_k: {"bate": False, "motivo": "teste"})
    assert m.main(["--base", str(base)]) == 2
    assert "p33" not in capsys.readouterr().out


def test_com_portao_aprovado_a_regua_sai(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    base = _escrever_base(tmp_path)
    monkeypatch.setattr(
        m,
        "portao",
        lambda *_a, **_k: {
            "bate": True,
            "oficial": 60.0,
            "script": 60.0,
            "n_relatorio": 4,
            "n_script": 4,
        },
    )
    assert m.main(["--base", str(base)]) == 0
    saida = capsys.readouterr().out
    assert "cidades com 100 mil+ hab.: 6" in saida
    assert "penetração p33 / mediana / p67" in saida


def test_base_vazia_nao_inventa_regua(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert m.main(["--base", str(tmp_path / "nao_existe")]) == 1
    assert "p33" not in capsys.readouterr().out
