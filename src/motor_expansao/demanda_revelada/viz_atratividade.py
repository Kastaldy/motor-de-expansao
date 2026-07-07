"""BLK-ATR-04: visualizacao dos resultados do funil de atratividade.

Gera 6 PNGs + 1 markdown-resumo em `data/analysis/viz_atratividade/` consumindo
os parquets existentes e o harness ATR-03 inline. READ-ONLY M1 (DEC-001/009/012).

GUARDRAILS (DEC-012 / CLAUDE.md §5):
  - Pacote DISJUNTO: NUNCA importa de `pipelines/`, `pipelines/m1/`, `dashboard/`,
    `censo_*`, `api/`, nem `config.py` raiz.
  - READ-ONLY sobre o M1: nao recalcula score/pesos/artefatos oficiais.
  - Sem PII em nenhuma imagem/legenda (so contagens/metricas agregadas).
  - `data/analysis/viz_atratividade/` e gitignored -- nao commitar PNGs.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import matplotlib  # type: ignore[import-untyped]

matplotlib.use("Agg")  # backend headless -- ANTES de qualquer import pyplot

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from .contrato import COLUNAS_PII_PROIBIDAS  # noqa: E402
from .estrutura_funil import EstruturaFunilResult  # noqa: E402

_logger = logging.getLogger(__name__)

# DPI de saida: boa qualidade sem arquivo enorme.
_DPI = 120


# --------------------------------------------------------------------------- #
# Rede de seguranca anti-PII
# --------------------------------------------------------------------------- #
def _assert_sem_pii_no_relatorio(texto: str) -> None:
    """Falha se qualquer coluna de COLUNAS_PII_PROIBIDAS aparecer como token isolado."""
    baixo = texto.lower()
    presentes = {
        c for c in COLUNAS_PII_PROIBIDAS if re.search(rf"\b{re.escape(c.lower())}\b", baixo)
    }
    if presentes:  # pragma: no cover - rede de seguranca
        raise AssertionError(f"PII vazou no relatorio BLK-ATR-04: {presentes}")


# --------------------------------------------------------------------------- #
# (a) Cobertura Huff por UF
# --------------------------------------------------------------------------- #
def gerar_grafico_cobertura_huff(df_mercado: pd.DataFrame, *, out_dir: Path) -> Path:
    """(a) Barras por UF de % hexes com share_captura_huff < 1.0.

    Parametros
    ----------
    df_mercado : DataFrame com colunas `share_captura_huff` e `uf`.
    out_dir    : diretorio de saida (criado se nao existir).

    Retorna
    -------
    Path do PNG gerado.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = df_mercado.copy()
    if "share_captura_huff" not in df.columns or "uf" not in df.columns:
        df["share_captura_huff"] = pd.Series(dtype=float)
        df["uf"] = pd.Series(dtype=str)

    share = pd.to_numeric(df.get("share_captura_huff", pd.Series(dtype=float)), errors="coerce")
    competitivo = (share < 1.0).fillna(False)
    df = df.copy()
    df["_competitivo"] = competitivo

    por_uf = (
        df.groupby("uf")["_competitivo"]
        .mean()
        .mul(100.0)
        .sort_values(ascending=False)
        .reset_index()
    )
    por_uf.columns = ["uf", "pct_competitivo"]  # type: ignore[assignment]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(por_uf["uf"], por_uf["pct_competitivo"], color="#2196F3", edgecolor="white")
    ax.set_xlabel("UF")
    ax.set_ylabel("% hexes competitivos (share < 1.0)")
    ax.set_title("(a) Cobertura Huff por UF -- % hexes com concorrente na janela\n"
                 "Estado atual -- base densa ATR-01 nao materializada")
    ax.set_ylim(0, 105)
    for i, row in por_uf.iterrows():
        ax.text(i, row["pct_competitivo"] + 0.5, f"{row['pct_competitivo']:.1f}%",
                ha="center", va="bottom", fontsize=7)
    fig.tight_layout()

    out_path = out_dir / "cobertura_huff.png"
    fig.savefig(out_path, dpi=_DPI)
    plt.close(fig)
    return out_path


# --------------------------------------------------------------------------- #
# (b) Impacto do gate por UF
# --------------------------------------------------------------------------- #
def gerar_grafico_gate_por_uf(
    df_join: pd.DataFrame, df_pos_gate: pd.DataFrame, *, out_dir: Path
) -> Path:
    """(b) Barras empilhadas por UF: aprovados vs reprovados pelo gate ATR-02.

    Parametros
    ----------
    df_join    : join demanda x mercado ANTES do gate (com coluna `uf`).
    df_pos_gate: join APOS o gate ATR-02.
    out_dir    : diretorio de saida.

    Retorna
    -------
    Path do PNG gerado.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Contagem pre-gate por UF
    total_por_uf = df_join.groupby("uf").size().rename("total")
    aprov_por_uf = df_pos_gate.groupby("uf").size().rename("aprovados")

    stats = pd.DataFrame({"total": total_por_uf, "aprovados": aprov_por_uf}).fillna(0)
    stats["aprovados"] = stats["aprovados"].astype(int)
    stats["reprovados"] = stats["total"] - stats["aprovados"]

    # Somente UFs com >= 5 hexes no join
    stats = stats[stats["total"] >= 5].sort_values("total", ascending=False)

    if stats.empty:
        # Fallback: plota vazio com mensagem
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(0.5, 0.5, "Sem UFs com >= 5 hexes no join", ha="center", va="center",
                transform=ax.transAxes)
        ax.set_title("(b) Impacto do gate ATR-02 por UF")
        fig.tight_layout()
        out_path = out_dir / "gate_por_uf.png"
        fig.savefig(out_path, dpi=_DPI)
        plt.close(fig)
        return out_path

    ufs = stats.index.tolist()
    aprovados = stats["aprovados"].tolist()
    reprovados = stats["reprovados"].tolist()

    fig, ax = plt.subplots(figsize=(max(8, len(ufs) * 0.6), 5))
    x = np.arange(len(ufs))
    bar_aprov = ax.bar(x, aprovados, label="Aprovados", color="#4CAF50", edgecolor="white")
    ax.bar(x, reprovados, bottom=aprovados, label="Reprovados", color="#F44336", edgecolor="white")

    ax.set_xticks(x)
    ax.set_xticklabels(ufs, rotation=45, ha="right")
    ax.set_xlabel("UF")
    ax.set_ylabel("N hexes")
    ax.set_title("(b) Impacto do gate ATR-02 por UF\n(pop >= 5000 AND renda >= 1500)")
    ax.legend(loc="upper right")

    # Anotacao de % aprovados em cada barra
    for xi, aprov, total in zip(x, aprovados, stats["total"].tolist(), strict=True):
        if total > 0:
            pct = 100.0 * aprov / total
            ax.text(float(xi), total + 0.5, f"{pct:.0f}%", ha="center", va="bottom", fontsize=7)

    del bar_aprov  # nao usado mais
    fig.tight_layout()

    out_path = out_dir / "gate_por_uf.png"
    fig.savefig(out_path, dpi=_DPI)
    plt.close(fig)
    return out_path


# --------------------------------------------------------------------------- #
# (c) Distribuicoes dos 3 eixos normalizados
# --------------------------------------------------------------------------- #
def gerar_grafico_distribuicoes_eixos(df_norm: pd.DataFrame, *, out_dir: Path) -> Path:
    """(c) 3 histogramas dos eixos normalizados (sociodemo, mercado, disputa).

    Parametros
    ----------
    df_norm : DataFrame apos `normalizar_eixos`, com colunas `eixo_*_norm`.
    out_dir : diretorio de saida.

    Retorna
    -------
    Path do PNG gerado.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    eixos = [
        ("eixo_sociodemo_norm", "Sociodemo (score_priorizacao)", "#3F51B5"),
        ("eixo_mercado_norm", "Mercado (score_oportunidade_residual)", "#009688"),
        ("eixo_disputa_norm", "Disputa (1 - share_huff)", "#FF5722"),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    for ax, (col, label, cor) in zip(axes, eixos, strict=True):
        if col in df_norm.columns:
            vals = pd.to_numeric(df_norm[col], errors="coerce").dropna().to_numpy()
        else:
            vals = np.array([])

        if len(vals) > 0:
            ax.hist(vals, bins=20, range=(0, 100), color=cor, alpha=0.8, edgecolor="white")
            med = float(np.median(vals))
            ax.axvline(med, color="black", linestyle="--", linewidth=1.5, label=f"Mediana {med:.1f}")
            ax.legend(fontsize=8)
        else:
            ax.text(0.5, 0.5, "sem dados", ha="center", va="center", transform=ax.transAxes)

        ax.set_title(label, fontsize=9)
        ax.set_xlabel("Percentil 0-100")
        ax.set_ylabel("N hexes" if ax is axes[0] else "")
        ax.set_xlim(0, 100)

    fig.suptitle("(c) Distribuicoes dos eixos normalizados (pos-gate)", fontsize=11)
    fig.tight_layout()

    out_path = out_dir / "distribuicoes_eixos.png"
    fig.savefig(out_path, dpi=_DPI)
    plt.close(fig)
    return out_path


# --------------------------------------------------------------------------- #
# (d) Quadrantes residual x disputa
# --------------------------------------------------------------------------- #
def gerar_grafico_quadrantes(df_pos_gate: pd.DataFrame, *, out_dir: Path) -> Path:
    """(d) Scatter/matriz de 4 quadrantes residual x disputa com contagens.

    Parametros
    ----------
    df_pos_gate : DataFrame apos gate com `score_oportunidade_residual` e `share_captura_huff`.
    out_dir     : diretorio de saida.

    Retorna
    -------
    Path do PNG gerado.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    residual = pd.to_numeric(
        df_pos_gate.get("score_oportunidade_residual", pd.Series(dtype=float)),
        errors="coerce",
    ).to_numpy(dtype=float)
    share = pd.to_numeric(
        df_pos_gate.get("share_captura_huff", pd.Series(dtype=float)),
        errors="coerce",
    ).to_numpy(dtype=float)
    disputa = 1.0 - share  # mais share => menos oportunidade de disputa

    ok = np.isfinite(residual) & np.isfinite(disputa)
    residual = residual[ok]
    disputa = disputa[ok]

    med_r = float(np.median(residual)) if len(residual) else 50.0
    med_d = float(np.median(disputa)) if len(disputa) else 0.5

    # Quadrantes: alto/baixo residual x alta/baixa disputa
    alto_r = residual >= med_r
    alta_d = disputa >= med_d

    q1 = int(np.sum(alto_r & alta_d))     # alto residual, alta disputa
    q2 = int(np.sum(alto_r & ~alta_d))    # alto residual, baixa disputa
    q3 = int(np.sum(~alto_r & alta_d))    # baixo residual, alta disputa
    q4 = int(np.sum(~alto_r & ~alta_d))   # baixo residual, baixa disputa

    fig, ax = plt.subplots(figsize=(8, 6))

    if len(residual) > 0:
        ax.scatter(residual, disputa, alpha=0.3, s=6, color="#607D8B", rasterized=True)

    ax.axvline(med_r, color="black", linestyle="--", linewidth=1.2, alpha=0.7)
    ax.axhline(med_d, color="black", linestyle="--", linewidth=1.2, alpha=0.7)

    # Anotacoes dos quadrantes (texto centralizado em cada quadrante)
    x_max = float(np.max(residual)) if len(residual) else 100.0
    y_max = float(np.max(disputa)) if len(disputa) else 1.0
    x_min = float(np.min(residual)) if len(residual) else 0.0
    y_min = float(np.min(disputa)) if len(disputa) else 0.0

    for tx, ty, label, n_q in [
        ((med_r + x_max) / 2, (med_d + y_max) / 2, "Mercado grande\ne disputado", q1),
        ((med_r + x_max) / 2, (y_min + med_d) / 2, "Nicho defensavel\n(oportunidade prime)", q2),
        ((x_min + med_r) / 2, (med_d + y_max) / 2, "Espaco saturado", q3),
        ((x_min + med_r) / 2, (y_min + med_d) / 2, "Mercado maduro", q4),
    ]:
        ax.text(
            tx, ty, f"{label}\nn={n_q:,}",
            ha="center", va="center", fontsize=8,
            bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "alpha": 0.7},
        )

    ax.set_xlabel("Score Oportunidade Residual")
    ax.set_ylabel("1 - share_captura_huff (disputa)")
    ax.set_title(
        "(d) Quadrantes residual x disputa\n"
        f"Cortes: mediana residual={med_r:.1f}, mediana disputa={med_d:.3f}"
    )
    fig.tight_layout()

    out_path = out_dir / "quadrantes_residual_disputa.png"
    fig.savefig(out_path, dpi=_DPI)
    plt.close(fig)
    return out_path


# --------------------------------------------------------------------------- #
# (e) R2_oof por modelo com IC95
# --------------------------------------------------------------------------- #
def gerar_grafico_r2_modelos(result: EstruturaFunilResult, *, out_dir: Path) -> Path:
    """(e) Barras horizontais de R2_oof por modelo com IC95 como barras de erro.

    Parametros
    ----------
    result  : EstruturaFunilResult do harness ATR-03.
    out_dir : diretorio de saida.

    Retorna
    -------
    Path do PNG gerado.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    ordem = ["baseline", "sociodemo", "mercado", "disputa", "censitario", "composto", "pesos_iguais"]
    entradas = []
    for chave in ordem:
        m = result.modelos.get(chave)
        if m is None or not np.isfinite(m.r2_oof):
            continue
        entradas.append(m)

    if not entradas:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(0.5, 0.5, "Sem modelos com R2 valido", ha="center", va="center",
                transform=ax.transAxes)
        ax.set_title(f"(e) R2_oof por modelo -- Veredito: {result.veredito}")
        fig.tight_layout()
        out_path = out_dir / "r2_modelos.png"
        fig.savefig(out_path, dpi=_DPI)
        plt.close(fig)
        return out_path

    nomes = [m.nome for m in entradas]
    r2s = [m.r2_oof for m in entradas]
    # IC95 como xerr: [r2 - ic_inf, ic_sup - r2] por barra
    xerr_low = [max(0.0, r - ic[0]) if np.isfinite(ic[0]) else 0.0
                for r, ic, m in zip(r2s, [m.ic95_r2 for m in entradas], entradas, strict=True)]
    xerr_high = [max(0.0, ic[1] - r) if np.isfinite(ic[1]) else 0.0
                 for r, ic, m in zip(r2s, [m.ic95_r2 for m in entradas], entradas, strict=True)]

    cores = []
    for m in entradas:
        if m.nome == "baseline":
            cores.append("#9E9E9E")
        elif m.nome in ("composto_ridge",):
            cores.append("#1A237E")
        else:
            cores.append("#42A5F5")

    fig, ax = plt.subplots(figsize=(9, max(3, len(entradas) * 0.55)))
    y_pos = np.arange(len(entradas))

    ax.barh(y_pos, r2s, xerr=[xerr_low, xerr_high],
            color=cores, edgecolor="white", capsize=4, error_kw={"elinewidth": 1.5})
    ax.axvline(0, color="black", linewidth=1.2, linestyle="--")
    ax.set_yticks(y_pos)
    ax.set_yticklabels(nomes, fontsize=8)
    ax.set_xlabel("R2_oof (IC95 como barras de erro)")
    ax.set_title(f"(e) R2_oof por modelo\nVeredito: {result.veredito}")
    ax.invert_yaxis()

    fig.tight_layout()

    out_path = out_dir / "r2_modelos.png"
    fig.savefig(out_path, dpi=_DPI)
    plt.close(fig)
    return out_path


# --------------------------------------------------------------------------- #
# (f) Heatmap correlacoes cruzadas
# --------------------------------------------------------------------------- #
def gerar_grafico_correlacoes(result: EstruturaFunilResult, *, out_dir: Path) -> Path:
    """(f) Heatmap 3x3 das correlacoes cruzadas entre eixos normalizados.

    Parametros
    ----------
    result  : EstruturaFunilResult com `correlacoes_cruzadas`.
    out_dir : diretorio de saida.

    Retorna
    -------
    Path do PNG gerado.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cruzadas = result.correlacoes_cruzadas
    labels = ["sociodemo", "mercado", "disputa"]
    # Matriz 3x3 simetrica
    mat = np.eye(3, dtype=float)
    # pares: sociodemo=0, mercado=1, disputa=2
    mat[0, 1] = mat[1, 0] = float(cruzadas.get("sociodemo_x_mercado", float("nan")))
    mat[0, 2] = mat[2, 0] = float(cruzadas.get("sociodemo_x_disputa", float("nan")))
    mat[1, 2] = mat[2, 1] = float(cruzadas.get("mercado_x_disputa", float("nan")))

    fig, ax = plt.subplots(figsize=(5, 4))
    # Substitui NaN por 0 para o heatmap (valor neutro)
    mat_display = np.where(np.isfinite(mat), mat, 0.0)
    im = ax.imshow(mat_display, cmap="RdBu_r", vmin=-1.0, vmax=1.0, aspect="auto")
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    ax.set_xticks(np.arange(3))
    ax.set_yticks(np.arange(3))
    ax.set_xticklabels(labels)
    ax.set_yticklabels(labels)
    ax.set_title("(f) Correlacoes cruzadas entre eixos normalizados\n(Spearman)")

    # Anotacoes de valor em cada celula
    for i in range(3):
        for j in range(3):
            v = mat[i, j]
            txt = f"{v:.3f}" if np.isfinite(v) else "n/d"
            text_color = "white" if abs(mat_display[i, j]) > 0.6 else "black"
            ax.text(j, i, txt, ha="center", va="center", fontsize=9, color=text_color)

    fig.tight_layout()

    out_path = out_dir / "correlacoes_eixos.png"
    fig.savefig(out_path, dpi=_DPI)
    plt.close(fig)
    return out_path


# --------------------------------------------------------------------------- #
# Relatorio markdown
# --------------------------------------------------------------------------- #
def gerar_relatorio_markdown(
    result: EstruturaFunilResult,
    paths_png: dict[str, Path],
    *,
    out_dir: Path,
) -> Path:
    """Gera relatorio_viz.md com achados e caminhos dos PNGs.

    Parametros
    ----------
    result   : EstruturaFunilResult do harness ATR-03.
    paths_png: dict[str, Path] mapeando nome curto -> Path do PNG.
    out_dir  : diretorio de saida.

    Retorna
    -------
    Path do markdown gerado.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    def _f(v: float, nd: int = 4) -> str:
        return f"{v:.{nd}f}" if np.isfinite(v) else "n/d"

    def _ic(t: tuple[float, float]) -> str:
        return f"[{_f(t[0])}, {_f(t[1])}]"

    L: list[str] = []
    L.append("# Relatorio de Visualizacao dos Resultados do Funil -- BLK-ATR-04")
    L.append("")
    L.append(
        "READ-ONLY sobre o M1 (DEC-001/DEC-008/DEC-009). Pacote disjunto (DEC-012). "
        "Sem PII (so contagens/metricas agregadas)."
    )
    L.append("")
    L.append("## Veredito")
    L.append("")
    L.append(f"**{result.veredito}** -- {result.motivo_veredito}")
    L.append("")
    L.append("## Amostra")
    L.append("")
    L.append(f"- N join (demanda x mercado): **{result.n_join}**")
    L.append(f"- N pos-gate ATR-02: **{result.n_pos_gate}** ({result.pct_retido_gate:.1f}% retido)")
    L.append(f"- Cobertura universo Motor: **~{result.pct_cobertura_universo:.2f}%**")
    L.append(f"- Metodo de validacao: `{result.metodo_validacao}`")
    L.append("")
    L.append("## Tabela de modelos (R2_oof + IC95)")
    L.append("")
    L.append("| modelo | n | R2_oof | IC95 R2 | rho_oof |")
    L.append("| --- | ---: | ---: | :--- | ---: |")
    ordem = ["baseline", "sociodemo", "mercado", "disputa", "censitario", "composto", "pesos_iguais"]
    for chave in ordem:
        m = result.modelos.get(chave)
        if m is None:
            continue
        L.append(
            f"| {m.nome} | {m.n} | {_f(m.r2_oof)} | {_ic(m.ic95_r2)} | {_f(m.rho_oof)} |"
        )
    L.append("")
    L.append("## Quadrantes (contagens)")
    L.append("")
    L.append(
        "Quadrantes por mediana de `score_oportunidade_residual` e `1 - share_captura_huff`. "
        "Ver grafico (d) para detalhes."
    )
    L.append("")
    L.append("## Graficos gerados")
    L.append("")
    for nome, p in paths_png.items():
        L.append(f"- **{nome}**: `{p}`")
    L.append("")
    L.append("## Confounds / nota honesta")
    L.append("")
    L.append("```")
    L.append(result.nota_honesta.rstrip("\n"))
    L.append("```")
    L.append("")

    texto = "\n".join(L)
    _assert_sem_pii_no_relatorio(texto)

    out_path = out_dir / "relatorio_viz.md"
    out_path.write_text(texto, encoding="utf-8")
    _logger.info("relatorio BLK-ATR-04 escrito: %s", out_path)
    return out_path


# --------------------------------------------------------------------------- #
# Orquestrador completo (pragma: no cover -- operacao cara com dados reais)
# --------------------------------------------------------------------------- #
def executar(mkt_path: Path, dem_path: Path, *, out_dir: Path) -> None:  # pragma: no cover
    """Orquestrador de disco: carrega parquets, roda harness ATR-03, gera todos os PNGs.

    NAO rodar em teste/building -- operacao cara com dados reais.
    """
    import pyarrow.parquet as pq

    from .estrutura_funil import (
        aplicar_gate_atratividade,
        avaliar_estrutura_funil,
        normalizar_eixos,
    )

    mkt_path = Path(mkt_path)
    dem_path = Path(dem_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    _logger.info("BLK-ATR-04: carregando parquets...")

    cols_mkt = [
        "hex_id", "score_priorizacao", "score_oportunidade_residual", "share_captura_huff",
        "score_setor_2022_calibrado", "renda_per_capita", "uf", "populacao_corte_hex",
        "confianca_geografica", "pop_total_setor_2022", "pop_total", "populacao_proxy",
        "qualidade_join_uf", "flag_censo_disponivel",
    ]
    disponiveis = set(pq.ParquetFile(mkt_path).schema.names)
    df_mkt = pd.read_parquet(mkt_path, columns=[c for c in cols_mkt if c in disponiveis])
    df_dem = pd.read_parquet(dem_path, columns=["hex_id", "membros"])

    df_join = df_dem.merge(df_mkt, on="hex_id", how="inner")
    _logger.info("Join: %d hexes", len(df_join))

    df_pos, _ = aplicar_gate_atratividade(df_join)
    df_norm = normalizar_eixos(df_pos)

    _logger.info("Rodando harness ATR-03...")
    result = avaliar_estrutura_funil(df_join)

    _logger.info("Gerando graficos...")
    paths_png: dict[str, Path] = {}
    paths_png["cobertura_huff"] = gerar_grafico_cobertura_huff(df_mkt, out_dir=out_dir)
    paths_png["gate_por_uf"] = gerar_grafico_gate_por_uf(df_join, df_pos, out_dir=out_dir)
    paths_png["distribuicoes"] = gerar_grafico_distribuicoes_eixos(df_norm, out_dir=out_dir)
    paths_png["quadrantes"] = gerar_grafico_quadrantes(df_pos, out_dir=out_dir)
    paths_png["r2_modelos"] = gerar_grafico_r2_modelos(result, out_dir=out_dir)
    paths_png["correlacoes"] = gerar_grafico_correlacoes(result, out_dir=out_dir)
    gerar_relatorio_markdown(result, paths_png, out_dir=out_dir)
    _logger.info("BLK-ATR-04 concluido: %s", out_dir)


if __name__ == "__main__":  # pragma: no cover
    import logging as _logging

    _logging.basicConfig(level=logging.INFO)
    executar(
        Path("data/staging/hexagonos_mercado_mapeado.parquet"),
        Path("data/staging/demanda_revelada_h3.parquet"),
        out_dir=Path("data/analysis/viz_atratividade"),
    )


__all__ = [
    "gerar_grafico_cobertura_huff",
    "gerar_grafico_gate_por_uf",
    "gerar_grafico_distribuicoes_eixos",
    "gerar_grafico_quadrantes",
    "gerar_grafico_r2_modelos",
    "gerar_grafico_correlacoes",
    "gerar_relatorio_markdown",
    "executar",
]
