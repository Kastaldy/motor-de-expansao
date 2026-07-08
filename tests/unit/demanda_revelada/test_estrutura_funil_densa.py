"""Testes do BLK-ATR-03-FU1: estrutura (matriz vs composto) sobre o Huff DENSO.

Fixtures 100% SINTETICAS (zero PII, zero leitura de arquivo/parquet real; DEC-012). Como o share
denso vem de geometria H3 real, os `hex_id` das fixtures sao REAIS (res-7 via `h3.latlng_to_cell`)
-- hexes fake dariam share NaN. NUNCA chama `calibrar_huff_captura`/`calcular_share_por_hex` sobre
a base real: so fixtures pequenas.
"""

from __future__ import annotations

import ast
import inspect

import h3
import numpy as np
import pandas as pd

from motor_expansao.demanda_revelada import estrutura_funil as ef
from motor_expansao.demanda_revelada import estrutura_funil_densa as efd
from motor_expansao.demanda_revelada.contrato import COLUNAS_PII_PROIBIDAS
from motor_expansao.demanda_revelada.estrutura_funil import EstruturaFunilResult
from motor_expansao.demanda_revelada.huff_captura import BETA_GRID


# --------------------------------------------------------------------------- #
# Helpers de fixture sintetica (hexes H3 res-7 REAIS)
# --------------------------------------------------------------------------- #
def _hexes_validos(n: int, *, lat0: float = -23.55, lng0: float = -46.63) -> list[str]:
    """N hexes H3 res-7 DISTINTOS numa grade sintetica em torno de (lat0, lng0)."""
    seen: dict[str, None] = {}
    passo = 0.02
    lado = int(np.ceil(np.sqrt(n))) + 2
    for i in range(lado):
        for j in range(lado):
            h = h3.latlng_to_cell(lat0 + i * passo, lng0 + j * passo, 7)
            seen.setdefault(h, None)
            if len(seen) >= n:
                return list(seen.keys())
    return list(seen.keys())


def _conc_densos_perto(hexes: list[str]) -> tuple[np.ndarray, np.ndarray]:
    """Concorrentes no centroide de METADE dos hexes (garante share < 1 nesses)."""
    lat: list[float] = []
    lng: list[float] = []
    for idx, h in enumerate(hexes):
        if idx % 2 == 0:  # metade recebe concorrente no proprio centroide
            la, lo = h3.cell_to_latlng(h)
            lat.append(la)
            lng.append(lo)
    return np.asarray(lat, dtype=float), np.asarray(lng, dtype=float)


def _join_sintetico(n: int = 300, *, seed: int = 42) -> pd.DataFrame:
    """Join demanda x mercado sintetico que PASSA o gate ATR-02 (pop>=5000, renda>=1500).

    `membros` depende de forma COMPLEMENTAR dos 3 eixos (sociodemo + mercado + disputa) -> cenario
    de sinal, para exercitar o caminho do harness sem forcar valor exato de R2.
    """
    rng = np.random.default_rng(seed)
    hexes = _hexes_validos(n)
    n = len(hexes)  # grade pode devolver >= n distintos
    socio = rng.uniform(0, 100, n)
    merc = rng.uniform(0, 100, n)
    share = rng.uniform(0.2, 1.0, n)  # placeholder; sera SUBSTITUIDO pelo share denso
    linear = 0.9 * socio + 0.9 * merc + 40.0 * (1.0 - share)
    membros = np.clip(linear + rng.normal(0, 8, n), 0, None).round()
    return pd.DataFrame(
        {
            "hex_id": hexes,
            "membros": membros,
            "score_priorizacao": socio,
            "score_oportunidade_residual": merc,
            "share_captura_huff": share,
            "score_setor_2022_calibrado": rng.uniform(0, 100, n),
            "renda_per_capita": rng.uniform(1800.0, 6000.0, n),
            "populacao_corte_hex": rng.uniform(6000.0, 30000.0, n),
            "uf": rng.choice(["SP", "RJ", "MG"], n),
        }
    )


def _df_denso_fake(conc_lat: np.ndarray, conc_lng: np.ndarray) -> pd.DataFrame:
    """Frame no formato do `concorrentes_densos.parquet` (so `lat`/`lng` importam a `_coords_densas`)."""
    return pd.DataFrame({"lat": conc_lat, "lng": conc_lng})


# --------------------------------------------------------------------------- #
# 1. substituir_share_denso recomputa o share sobre a base densa
# --------------------------------------------------------------------------- #
def test_substituir_share_denso_recomputa():
    df = _join_sintetico(120)
    df["share_captura_huff"] = 1.0  # share antigo = monopolio total
    membros_antes = df["membros"].copy()
    conc_lat, conc_lng = _conc_densos_perto(df["hex_id"].tolist())

    out = efd.substituir_share_denso(df, conc_lat, conc_lng, beta=1.5)

    share = out["share_captura_huff"].to_numpy(dtype=float)
    # os hexes com concorrente no centroide (metade) ficam com share < 1.0
    assert np.nanmin(share) < 1.0
    # `membros` intocado
    pd.testing.assert_series_equal(out["membros"], membros_antes)
    # nao mutou o frame original
    assert (df["share_captura_huff"] == 1.0).all()


# --------------------------------------------------------------------------- #
# 2. DEC-009: o share independe de `membros`
# --------------------------------------------------------------------------- #
def test_share_nao_usa_membros():
    df_a = _join_sintetico(120)
    df_b = df_a.copy()
    df_b["membros"] = df_b["membros"] * 7 + 123  # alvo totalmente diferente
    conc_lat, conc_lng = _conc_densos_perto(df_a["hex_id"].tolist())

    out_a = efd.substituir_share_denso(df_a, conc_lat, conc_lng, beta=1.0)
    out_b = efd.substituir_share_denso(df_b, conc_lat, conc_lng, beta=1.0)

    assert np.array_equal(
        out_a["share_captura_huff"].to_numpy(dtype=float),
        out_b["share_captura_huff"].to_numpy(dtype=float),
        equal_nan=True,
    )


# --------------------------------------------------------------------------- #
# 3. avaliar_estrutura_densa roda e devolve (result, beta) coerentes
# --------------------------------------------------------------------------- #
def test_avaliar_estrutura_densa_roda():
    df = _join_sintetico(300)
    conc_lat, conc_lng = _conc_densos_perto(df["hex_id"].tolist())
    df_denso = _df_denso_fake(conc_lat, conc_lng)

    result, beta = efd.avaliar_estrutura_densa(df, df_denso)

    assert isinstance(result, EstruturaFunilResult)
    assert beta in BETA_GRID
    assert result.veredito in {"GO-composto", "matriz"}
    assert result.modelos["composto"].n > 0


# --------------------------------------------------------------------------- #
# 4. Relatorio denso sem PII
# --------------------------------------------------------------------------- #
def test_relatorio_denso_sem_pii():
    df = _join_sintetico(300)
    conc_lat, conc_lng = _conc_densos_perto(df["hex_id"].tolist())
    df_denso = _df_denso_fake(conc_lat, conc_lng)

    result, _beta = efd.avaliar_estrutura_densa(df, df_denso)
    texto = ef.relatorio_estrutura_funil(result)

    # rede de seguranca do harness (nao levanta) + checagem redundante por token isolado
    ef._assert_sem_pii_no_relatorio(texto)
    import re

    baixo = texto.lower()
    for col in COLUNAS_PII_PROIBIDAS:
        assert re.search(rf"\b{re.escape(col.lower())}\b", baixo) is None, (
            f"PII '{col}' vazou no relatorio denso"
        )


# --------------------------------------------------------------------------- #
# 5. Isolamento de import (AST) -- pacote disjunto (DEC-012)
# --------------------------------------------------------------------------- #
def test_isolamento_imports_ast():
    src = inspect.getsource(efd)
    tree = ast.parse(src)
    mods: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mods.append(node.module or "")
        elif isinstance(node, ast.Import):
            mods.extend(a.name for a in node.names)
    proibidos = (
        "motor_expansao.pipelines",
        "motor_expansao.dashboard",
        "motor_expansao.api",
        "motor_expansao.censo",
    )
    bad = [mod for mod in mods if any(mod.startswith(p) or p in mod for p in proibidos)]
    assert not bad, f"imports proibidos no modulo: {bad}"
    # `config` da raiz (import direto de `config`): nao pode ser importado.
    assert "config" not in mods
    # rede extra textual: nenhuma LINHA de import referencia os proibidos.
    linhas_import = [
        ln for ln in src.splitlines() if ln.strip().startswith(("import ", "from "))
    ]
    for ln in linhas_import:
        for proibido in ("pipelines", "dashboard", "censo_", "motor_expansao.api"):
            assert proibido not in ln, f"import textual proibido '{proibido}': {ln!r}"


# --------------------------------------------------------------------------- #
# 6. `membros` intocado apos substituir_share_denso
# --------------------------------------------------------------------------- #
def test_membros_intocado():
    df = _join_sintetico(150)
    membros_antes = df["membros"].copy()
    conc_lat, conc_lng = _conc_densos_perto(df["hex_id"].tolist())

    out = efd.substituir_share_denso(df, conc_lat, conc_lng, beta=2.0)

    pd.testing.assert_series_equal(out["membros"], membros_antes)
