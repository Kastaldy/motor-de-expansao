"""Testes do BLK-ATR-04: visualizacao dos resultados do funil de atratividade.

Fixtures 100% SINTETICAS (zero PII, zero leitura de arquivo real; DEC-012).
Os testes verificam que cada funcao gera um PNG valido, que o markdown nao tem PII,
que o modulo e isolado e que as figuras sao fechadas apos cada chamada.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib  # type: ignore[import-untyped]

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

from motor_expansao.demanda_revelada import estrutura_funil as ef
from motor_expansao.demanda_revelada import viz_atratividade as viz
from motor_expansao.demanda_revelada.contrato import COLUNAS_PII_PROIBIDAS


# --------------------------------------------------------------------------- #
# Fixtures sinteticas
# --------------------------------------------------------------------------- #
def _df_join_sintetico(n: int = 80, *, seed: int = 42) -> pd.DataFrame:
    """Join demanda x mercado sintetico que passa o gate."""
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {
            "hex_id": [f"87abc{i:07d}ffff" for i in range(n)],
            "membros": rng.integers(10, 500, n).astype(float),
            "renda_per_capita": rng.uniform(1800.0, 6000.0, n),
            "populacao_corte_hex": rng.uniform(6000.0, 30000.0, n),
            "score_priorizacao": rng.uniform(0, 100, n),
            "score_oportunidade_residual": rng.uniform(0, 100, n),
            "share_captura_huff": rng.uniform(0.2, 1.0, n),
            "score_setor_2022_calibrado": rng.uniform(0, 100, n),
            "uf": rng.choice(["SP", "RJ", "MG", "PR", "RS"], n),
        }
    )


def _df_mercado_sintetico(n: int = 200, *, seed: int = 0) -> pd.DataFrame:
    """Mercado sintetico (para cobertura_huff)."""
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {
            "hex_id": [f"87abc{i:07d}ffff" for i in range(n)],
            "share_captura_huff": np.concatenate(
                [
                    np.full(n // 2, 1.0),  # metade sem competicao
                    rng.uniform(0.1, 0.9, n - n // 2),  # metade competitiva
                ]
            ),
            "uf": rng.choice(["SP", "RJ", "MG", "PR"], n),
        }
    )


@pytest.fixture(scope="module")
def df_join() -> pd.DataFrame:
    """Join sintetico que passa o gate (escopo de modulo para reusar em testes 5/6)."""
    return _df_join_sintetico(n=80, seed=42)


@pytest.fixture(scope="module")
def df_pos_gate(df_join: pd.DataFrame) -> pd.DataFrame:
    """Pos-gate do join sintetico."""
    pos, _ = ef.aplicar_gate_atratividade(df_join)
    return pos


@pytest.fixture(scope="module")
def df_norm(df_pos_gate: pd.DataFrame) -> pd.DataFrame:
    """Eixos normalizados do pos-gate."""
    return ef.normalizar_eixos(df_pos_gate)


@pytest.fixture(scope="module")
def result_funil(df_join: pd.DataFrame) -> ef.EstruturaFunilResult:
    """Resultado do harness ATR-03 (computado uma vez por modulo de teste)."""
    return ef.avaliar_estrutura_funil(df_join)


# --------------------------------------------------------------------------- #
# 1. cobertura_huff gera PNG > 1kB
# --------------------------------------------------------------------------- #
def test_grafico_cobertura_huff_gera_png(tmp_path: Path) -> None:
    df_mkt = _df_mercado_sintetico(n=200)
    out = viz.gerar_grafico_cobertura_huff(df_mkt, out_dir=tmp_path)
    assert out.exists(), "PNG nao gerado"
    assert out.stat().st_size > 1024, "PNG menor que 1 kB"
    assert out.name == "cobertura_huff.png"


# --------------------------------------------------------------------------- #
# 2. gate_por_uf gera PNG > 1kB
# --------------------------------------------------------------------------- #
def test_grafico_gate_por_uf_gera_png(
    tmp_path: Path, df_join: pd.DataFrame, df_pos_gate: pd.DataFrame
) -> None:
    out = viz.gerar_grafico_gate_por_uf(df_join, df_pos_gate, out_dir=tmp_path)
    assert out.exists(), "PNG nao gerado"
    assert out.stat().st_size > 1024, "PNG menor que 1 kB"
    assert out.name == "gate_por_uf.png"


# --------------------------------------------------------------------------- #
# 3. distribuicoes_eixos gera PNG > 1kB
# --------------------------------------------------------------------------- #
def test_grafico_distribuicoes_eixos_gera_png(tmp_path: Path, df_norm: pd.DataFrame) -> None:
    out = viz.gerar_grafico_distribuicoes_eixos(df_norm, out_dir=tmp_path)
    assert out.exists(), "PNG nao gerado"
    assert out.stat().st_size > 1024, "PNG menor que 1 kB"
    assert out.name == "distribuicoes_eixos.png"


# --------------------------------------------------------------------------- #
# 4. quadrantes gera PNG > 1kB
# --------------------------------------------------------------------------- #
def test_grafico_quadrantes_gera_png(tmp_path: Path, df_pos_gate: pd.DataFrame) -> None:
    out = viz.gerar_grafico_quadrantes(df_pos_gate, out_dir=tmp_path)
    assert out.exists(), "PNG nao gerado"
    assert out.stat().st_size > 1024, "PNG menor que 1 kB"
    assert out.name == "quadrantes_residual_disputa.png"


# --------------------------------------------------------------------------- #
# 5. r2_modelos gera PNG > 1kB
# --------------------------------------------------------------------------- #
def test_grafico_r2_modelos_gera_png(
    tmp_path: Path, result_funil: ef.EstruturaFunilResult
) -> None:
    out = viz.gerar_grafico_r2_modelos(result_funil, out_dir=tmp_path)
    assert out.exists(), "PNG nao gerado"
    assert out.stat().st_size > 1024, "PNG menor que 1 kB"
    assert out.name == "r2_modelos.png"


# --------------------------------------------------------------------------- #
# 6. correlacoes gera PNG > 1kB
# --------------------------------------------------------------------------- #
def test_grafico_correlacoes_gera_png(
    tmp_path: Path, result_funil: ef.EstruturaFunilResult
) -> None:
    out = viz.gerar_grafico_correlacoes(result_funil, out_dir=tmp_path)
    assert out.exists(), "PNG nao gerado"
    assert out.stat().st_size > 1024, "PNG menor que 1 kB"
    assert out.name == "correlacoes_eixos.png"


# --------------------------------------------------------------------------- #
# 7. markdown menciona pelo menos um PNG
# --------------------------------------------------------------------------- #
def test_relatorio_markdown_referencia_pngs(
    tmp_path: Path, result_funil: ef.EstruturaFunilResult
) -> None:
    # Paths ficticios (nao precisam existir -- so testamos o conteudo do markdown)
    paths_png = {
        "cobertura_huff": tmp_path / "cobertura_huff.png",
        "gate_por_uf": tmp_path / "gate_por_uf.png",
        "distribuicoes": tmp_path / "distribuicoes_eixos.png",
        "quadrantes": tmp_path / "quadrantes_residual_disputa.png",
        "r2_modelos": tmp_path / "r2_modelos.png",
        "correlacoes": tmp_path / "correlacoes_eixos.png",
    }
    out = viz.gerar_relatorio_markdown(result_funil, paths_png, out_dir=tmp_path)
    assert out.exists(), "Markdown nao gerado"
    texto = out.read_text(encoding="utf-8")
    # Verifica que pelo menos um dos nomes de PNG e mencionado
    assert any(nome in texto for nome in paths_png), (
        "Markdown nao menciona nenhum nome de PNG"
    )
    assert "BLK-ATR-04" in texto


# --------------------------------------------------------------------------- #
# 8. markdown nao tem PII
# --------------------------------------------------------------------------- #
def test_relatorio_markdown_sem_pii(
    tmp_path: Path, result_funil: ef.EstruturaFunilResult
) -> None:
    paths_png: dict[str, Path] = {}
    out = viz.gerar_relatorio_markdown(result_funil, paths_png, out_dir=tmp_path)
    texto = out.read_text(encoding="utf-8").lower()
    import re

    for col in COLUNAS_PII_PROIBIDAS:
        found = re.search(rf"\b{re.escape(col.lower())}\b", texto)
        assert found is None, f"PII '{col}' encontrado no markdown"


# --------------------------------------------------------------------------- #
# 9. Isolamento de imports
# --------------------------------------------------------------------------- #
def test_isolamento_imports() -> None:
    """Verifica que viz_atratividade nao faz import de modulos proibidos.

    Inspeciona o codigo-fonte do modulo buscando imports proibidos diretamente,
    ja que o pytest carrega o dashboard em outros testes da suite e sys.modules
    nao e confiavel como indicador de importacao pelo modulo alvo.
    """
    import importlib.util

    spec = importlib.util.find_spec("motor_expansao.demanda_revelada.viz_atratividade")
    assert spec is not None and spec.origin is not None
    source = Path(spec.origin).read_text(encoding="utf-8")

    proibidos_grep = [
        "pipelines.m1",
        "motor_expansao.dashboard",
        "motor_expansao.api",
        "motor_expansao.censo",
        "from ..pipelines",
        "from motor_expansao.pipelines.m1",
        "from motor_expansao.dashboard",
        "from motor_expansao.api",
    ]
    for token in proibidos_grep:
        # Ignora comentarios (linhas com # antes do token)
        for linha in source.splitlines():
            stripped = linha.strip()
            if stripped.startswith("#"):
                continue
            if token in linha:
                raise AssertionError(
                    f"Import proibido '{token}' encontrado em viz_atratividade.py: {linha!r}"
                )



# --------------------------------------------------------------------------- #
# 10. Figuras fechadas apos cada chamada de geracao de grafico
# --------------------------------------------------------------------------- #
def test_figuras_fechadas_apos_geracao(
    tmp_path: Path, df_join: pd.DataFrame, df_pos_gate: pd.DataFrame,
    df_norm: pd.DataFrame, result_funil: ef.EstruturaFunilResult
) -> None:
    """Nenhuma figura matplotlib deve ficar aberta apos cada chamada."""
    # Fechar qualquer figura residual de outros testes
    plt.close("all")

    df_mkt = _df_mercado_sintetico(n=50)

    viz.gerar_grafico_cobertura_huff(df_mkt, out_dir=tmp_path)
    assert len(plt.get_fignums()) == 0, "Figura nao fechada apos cobertura_huff"

    viz.gerar_grafico_gate_por_uf(df_join, df_pos_gate, out_dir=tmp_path)
    assert len(plt.get_fignums()) == 0, "Figura nao fechada apos gate_por_uf"

    viz.gerar_grafico_distribuicoes_eixos(df_norm, out_dir=tmp_path)
    assert len(plt.get_fignums()) == 0, "Figura nao fechada apos distribuicoes_eixos"

    viz.gerar_grafico_quadrantes(df_pos_gate, out_dir=tmp_path)
    assert len(plt.get_fignums()) == 0, "Figura nao fechada apos quadrantes"

    viz.gerar_grafico_r2_modelos(result_funil, out_dir=tmp_path)
    assert len(plt.get_fignums()) == 0, "Figura nao fechada apos r2_modelos"

    viz.gerar_grafico_correlacoes(result_funil, out_dir=tmp_path)
    assert len(plt.get_fignums()) == 0, "Figura nao fechada apos correlacoes"
