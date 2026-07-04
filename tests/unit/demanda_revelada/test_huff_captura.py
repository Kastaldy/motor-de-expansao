"""BLK-TP-07: testes offline (seed-fixo, sem I/O de rede) do Huff de captura por hex.

Fixtures 100% SINTETICAS (nunca a fonte real NAO_ABRA/ nem parquet real): hexes H3 validos +
concorrentes sinteticos + `membros`. Cobre: pureza/anti-vazamento do share (share nunca recebe o
alvo), GO (sinal forte) / NO-GO (ruido), IC determinista (seed 42), anti-PII, isolamento de import
(AST+grep), baseline geometrico reportado, join por hex_id inner.
"""

from __future__ import annotations

import ast
import inspect
import re

import h3
import numpy as np
import pandas as pd
import pytest

from motor_expansao.demanda_revelada import huff_captura as m
from motor_expansao.demanda_revelada.contrato import COLUNAS_PII_PROIBIDAS
from motor_expansao.demanda_revelada.huff_captura import (
    HuffCapturaResult,
    _assert_sem_pii_no_relatorio,
    _preparar_join_real,
    calcular_share_por_hex,
    calibrar_huff_captura,
    n_conc_no_raio_hex,
    relatorio_huff_captura,
    share_hex,
    share_huff,
)


# --------------------------------------------------------------------------- #
# Helpers sinteticos: hexes H3 reais em torno de um ponto + concorrentes
# --------------------------------------------------------------------------- #
def _hexes_reais(n: int, *, lat0: float = -23.55, lng0: float = -46.63) -> list[str]:
    """N hexes H3 res-7 DISTINTOS numa grade sintetica em torno de (lat0, lng0)."""
    seen: dict[str, None] = {}
    passo = 0.02
    lado = int(np.ceil(np.sqrt(n))) + 2
    for i in range(lado):
        for j in range(lado):
            h = h3.latlng_to_cell(lat0 + i * passo, lng0 + j * passo, 7)
            if h not in seen:
                seen[h] = None
            if len(seen) >= n:
                return list(seen.keys())
    return list(seen.keys())


@pytest.fixture
def dados_forte() -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    """`membros` cresce forte e monotonicamente com o share Huff -> esperado GO.

    Constroi concorrentes de modo que o share varie por hex e correlacione com membros:
    membros ~ funcao crescente do share + ruido pequeno.
    """
    rng = np.random.default_rng(7)
    n = 400
    hexes = _hexes_reais(n)
    # concorrentes espalhados: densidade de concorrentes controla o share (mais conc -> menor share)
    conc_lat: list[float] = []
    conc_lng: list[float] = []
    n_conc_por_hex = rng.integers(0, 6, n)
    for h, k in zip(hexes, n_conc_por_hex, strict=True):
        la, lo = h3.cell_to_latlng(h)
        for _ in range(int(k)):
            conc_lat.append(la + rng.normal(0.0, 0.01))
            conc_lng.append(lo + rng.normal(0.0, 0.01))
    clat = np.asarray(conc_lat, dtype=float)
    clng = np.asarray(conc_lng, dtype=float)
    # share verdadeiro do beta 1.5 (puro) para ancorar o alvo
    share = calcular_share_por_hex(hexes, clat, clng, 1.5)
    log_mem = 3.0 * np.nan_to_num(share, nan=0.0) + rng.normal(0.0, 0.15, n)
    membros = np.expm1(np.clip(log_mem, 0.0, None)).round().astype(int) + 1
    df = pd.DataFrame(
        {
            "hex_id": hexes,
            "membros": membros,
            "alunos_parceiras": rng.integers(0, 400, n),
            "n_acad_parceiras": rng.integers(0, 20, n),
            "n_concorrente_lc": n_conc_por_hex,
            "dist_concorrente_lc_min_m": rng.uniform(100.0, 5000.0, n),
            "uf": np.where(
                np.arange(n) % 3 == 0, "SP", np.where(np.arange(n) % 3 == 1, "MG", "RJ")
            ),
        }
    )
    return df, clat, clng


@pytest.fixture
def dados_ruido() -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    """`membros` INDEPENDENTE do share (ruido puro) -> esperado NO-GO (IC cruza zero)."""
    rng = np.random.default_rng(42)
    n = 400
    hexes = _hexes_reais(n)
    conc_lat: list[float] = []
    conc_lng: list[float] = []
    for h in hexes:
        la, lo = h3.cell_to_latlng(h)
        for _ in range(int(rng.integers(0, 6))):
            conc_lat.append(la + rng.normal(0.0, 0.01))
            conc_lng.append(lo + rng.normal(0.0, 0.01))
    clat = np.asarray(conc_lat, dtype=float)
    clng = np.asarray(conc_lng, dtype=float)
    df = pd.DataFrame(
        {
            "hex_id": hexes,
            "membros": rng.integers(0, 5000, n),  # sem relacao com share
            "alunos_parceiras": rng.integers(0, 400, n),
            "n_acad_parceiras": rng.integers(0, 20, n),
            "n_concorrente_lc": rng.integers(0, 6, n),
            "dist_concorrente_lc_min_m": rng.uniform(100.0, 5000.0, n),
            "uf": ["SP"] * n,
        }
    )
    return df, clat, clng


# --------------------------------------------------------------------------- #
# 1. Pureza do share
# --------------------------------------------------------------------------- #
def test_share_hex_puro():
    """share em [0,1]; sem concorrentes -> 1.0; monotonico decrescente na distancia."""
    hexo = h3.latlng_to_cell(-23.55, -46.63, 7)
    lat0, lng0 = h3.cell_to_latlng(hexo)
    # sem concorrentes -> monopolio local
    assert share_hex(hexo, np.array([]), np.array([]), 1.5) == 1.0
    # 1 concorrente perto -> share < 1 e em [0,1]
    perto = share_hex(hexo, np.array([lat0 + 0.002]), np.array([lng0 + 0.002]), 1.5)
    assert 0.0 <= perto <= 1.0
    # concorrente mais LONGE (dentro da janela) -> share MAIOR que o concorrente perto
    longe = share_hex(hexo, np.array([lat0 + 0.02]), np.array([lng0 + 0.02]), 1.5)
    assert longe >= perto
    # hex invalido -> nan
    assert np.isnan(share_hex("nao_e_hex", np.array([lat0]), np.array([lng0]), 1.5))


def test_share_nao_recebe_alvo():
    """ANTI-VAZAMENTO (DEC-009): o caminho de calculo do share NUNCA referencia `membros`/`y`.

    Inspeciona a fonte de `share_hex` e do nucleo `share_huff`: nem `membros` nem `alunos` (o alvo)
    aparecem na assinatura ou no corpo. O share depende SO da geometria + beta.
    """
    # Inspeciona SO o codigo executavel (remove docstrings/comentarios): a garantia anti-vazamento
    # e sobre o corpo do share, nao sobre a prosa que explicitamente cita `membros` como o alvo.
    def _codigo_sem_docstring(fn) -> str:
        tree = ast.parse(inspect.getsource(fn))
        func = tree.body[0]
        if (
            func.body
            and isinstance(func.body[0], ast.Expr)
            and isinstance(func.body[0].value, ast.Constant)
            and isinstance(func.body[0].value.value, str)
        ):
            func.body = func.body[1:]  # remove a docstring
        return ast.unparse(func)

    src_hex = _codigo_sem_docstring(share_hex)
    src_nucleo = _codigo_sem_docstring(share_huff)
    for termo in ("membros", "alunos", "y_true", "target"):
        assert termo not in src_hex, f"share_hex referencia o alvo '{termo}'"
        assert termo not in src_nucleo, f"share_huff referencia o alvo '{termo}'"
    # a assinatura de share_hex nao recebe o alvo
    params = set(inspect.signature(share_hex).parameters)
    assert "membros" not in params and "y" not in params


# --------------------------------------------------------------------------- #
# 2/3. GO / NO-GO
# --------------------------------------------------------------------------- #
def test_go_sinal_forte(dados_forte):
    """Sinal forte (membros cresce com o share) -> GO honesto (ancora ou suporte)."""
    df, clat, clng = dados_forte
    res = calibrar_huff_captura(df, clat, clng, incluir_sensibilidades=False)
    assert res.veredito == "GO"
    assert res.go is True
    assert res.tipo_go in {"ancora_r2", "suporte_rho"}
    assert res.rho_oof > 0.0
    # beta selecionado pertence a grade
    assert res.beta_selecionado in (0.5, 1.0, 1.5, 2.0, 3.0)


def test_nogo_ruido(dados_ruido):
    """Ruido puro -> NO-GO (ancora e suporte falham)."""
    df, clat, clng = dados_ruido
    res = calibrar_huff_captura(df, clat, clng, incluir_sensibilidades=False)
    assert res.veredito == "NO-GO"
    assert res.go is False
    ancora_ok = (
        res.r2_oof_log > 0.05
        and res.ic95_r2_oof[0] > 0.0
        and res.r2_oof_log > res.r2_oof_baseline_geometrico
    )
    suporte_ok = res.rho_oof >= 0.30 and res.ic95_rho_oof[0] > 0.0
    assert not ancora_ok
    assert not suporte_ok


# --------------------------------------------------------------------------- #
# 4. IC determinista
# --------------------------------------------------------------------------- #
def test_ic_determinista(dados_forte):
    """Mesma seed -> mesmo IC95 (R2 e rho), mesmo R2/rho oof e mesmo beta (reprodutibilidade)."""
    df, clat, clng = dados_forte
    r1 = calibrar_huff_captura(df, clat, clng, incluir_sensibilidades=False)
    r2 = calibrar_huff_captura(df, clat, clng, incluir_sensibilidades=False)
    assert r1.ic95_r2_oof == pytest.approx(r2.ic95_r2_oof)
    assert r1.ic95_rho_oof == pytest.approx(r2.ic95_rho_oof)
    assert r1.r2_oof_log == pytest.approx(r2.r2_oof_log)
    assert r1.rho_oof == pytest.approx(r2.rho_oof)
    assert r1.beta_selecionado == r2.beta_selecionado


# --------------------------------------------------------------------------- #
# 5. Anti-PII
# --------------------------------------------------------------------------- #
def test_zero_pii(dados_forte):
    """Nenhuma coluna de COLUNAS_PII_PROIBIDAS como TOKEN isolado no relatorio/result."""
    df, clat, clng = dados_forte
    res = calibrar_huff_captura(df, clat, clng, incluir_sensibilidades=False)
    texto = relatorio_huff_captura(res)
    _assert_sem_pii_no_relatorio(texto)  # nao levanta sobre a saida honesta
    baixo = texto.lower()
    for col in COLUNAS_PII_PROIBIDAS:
        assert re.search(rf"\b{re.escape(col.lower())}\b", baixo) is None, (
            f"PII '{col}' vazou no relatorio"
        )
    # o result nao carrega campo com nome de coluna proibida
    for campo in vars(res):
        assert campo not in COLUNAS_PII_PROIBIDAS


# --------------------------------------------------------------------------- #
# 6. Isolamento de import (AST + grep textual)
# --------------------------------------------------------------------------- #
def test_isolamento_import():
    """O modulo nao importa de pipelines.m1/dashboard/censo/api/config (DEC-012)."""
    src = inspect.getsource(m)
    tree = ast.parse(src)
    mods: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mods.append(node.module or "")
        elif isinstance(node, ast.Import):
            mods.extend(a.name for a in node.names)
    proibidos = ("pipelines.m1", "dashboard", "censo", "motor_expansao.api")
    bad = [mod for mod in mods if any(p in mod for p in proibidos)]
    assert not bad, f"imports proibidos no modulo: {bad}"
    # `config` da raiz (import direto de `config`): nao pode ser importado.
    assert "config" not in mods
    # rede extra: nenhuma LINHA de import textual referencia os proibidos (docstring nao conta)
    linhas_import = [ln for ln in src.splitlines() if ln.strip().startswith(("import ", "from "))]
    for ln in linhas_import:
        for proibido in ("pipelines.m1", "dashboard", "censo_", "motor_expansao.api"):
            assert proibido not in ln, f"import textual proibido '{proibido}': {ln!r}"


# --------------------------------------------------------------------------- #
# 7. Baseline geometrico reportado
# --------------------------------------------------------------------------- #
def test_baseline_geometrico_reportado(dados_forte):
    """O baseline geometrico (contagem-no-raio sem beta) e computado e reportado AO LADO."""
    df, clat, clng = dados_forte
    res = calibrar_huff_captura(df, clat, clng, incluir_sensibilidades=False)
    # campo existe e e float (pode ser negativo se contagem nao ordena -- valido)
    assert isinstance(res.r2_oof_baseline_geometrico, float)
    assert res.ic95_r2_oof_baseline_geometrico[0] <= res.ic95_r2_oof_baseline_geometrico[1]
    texto = relatorio_huff_captura(res)
    assert "baseline GEOMETRICO" in texto or "baseline geometrico" in texto.lower()
    # o GO-ancora exige superar o baseline geometrico (parte do criterio)
    if res.tipo_go == "ancora_r2":
        assert res.r2_oof_log > res.r2_oof_baseline_geometrico


# --------------------------------------------------------------------------- #
# 8. Join por hex_id inner
# --------------------------------------------------------------------------- #
def test_join_por_hex_id_inner():
    """`_preparar_join_real` traz so colunas agregadas e casa `uf`/ultra do mercado por hex_id."""
    dem = pd.DataFrame(
        {
            "hex_id": ["a", "b", "c"],
            "membros": [10, 20, 30],
            "alunos_parceiras": [1, 2, 3],
            "n_acad_parceiras": [1, 1, 1],
            "n_concorrente_lc": [0, 1, 2],
            "dist_concorrente_lc_min_m": [100.0, 200.0, 300.0],
        }
    )
    mkt = pd.DataFrame(
        {
            "hex_id": ["b", "c", "d"],
            "uf": ["SP", "MG", "RJ"],
            "n_unidades_ultra_1km": [0, 1, 2],
            "dist_ultra_mais_proxima_m": [500.0, 600.0, 700.0],
        }
    )
    j = _preparar_join_real(dem, mkt)
    # left-join preserva as 3 linhas da demanda; uf casada so em b, c
    assert len(j) == 3
    assert set(j["hex_id"]) == {"a", "b", "c"}
    assert j.loc[j["hex_id"] == "b", "uf"].iloc[0] == "SP"
    assert pd.isna(j.loc[j["hex_id"] == "a", "uf"].iloc[0])
    # nenhuma coluna PII entra
    for col in COLUNAS_PII_PROIBIDAS:
        assert col not in j.columns


# --------------------------------------------------------------------------- #
# Extra: contrato do result + n_conc_no_raio
# --------------------------------------------------------------------------- #
def test_result_tipo(dados_forte):
    """O orquestrador devolve o dataclass esperado com campos-chave coerentes."""
    df, clat, clng = dados_forte
    res = calibrar_huff_captura(df, clat, clng, incluir_sensibilidades=False)
    assert isinstance(res, HuffCapturaResult)
    assert res.n_join == len(df)
    assert res.n_treinamento <= res.n_join
    assert res.metodo_validacao in {"kfold_5x5", "kfold_10x5", "loo"}
    assert isinstance(res.concentracao_uf, dict)
    assert set(res.rmse_oof_por_beta.keys()) == {0.5, 1.0, 1.5, 2.0, 3.0}


def test_n_conc_no_raio_hex():
    """Baseline geometrico: conta concorrentes no raio; hex invalido -> nan."""
    hexo = h3.latlng_to_cell(-23.55, -46.63, 7)
    lat0, lng0 = h3.cell_to_latlng(hexo)
    dentro_lat = np.array([lat0 + 0.001, lat0 + 0.002])
    dentro_lng = np.array([lng0 + 0.001, lng0 + 0.002])
    assert n_conc_no_raio_hex(hexo, dentro_lat, dentro_lng) == 2.0
    assert np.isnan(n_conc_no_raio_hex("nao_e_hex", dentro_lat, dentro_lng))
