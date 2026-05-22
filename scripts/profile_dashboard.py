"""
Baseline de performance do dashboard Streamlit (Bloco 1 do ciclo de Performance).

Mede, a frio, o custo de cada etapa de carga do app sem alterar o runtime:
`load_data`, `load_hybrid_data`, `load_censo_trace_data`, `load_estrutural_pop`
e o merge `enrich_dashboard_data`. Reporta tempo, RSS por etapa e o peso de
memoria (`memory_usage(deep=True)`) do frame enriquecido por UF.

Apenas leitura: nao escreve em `data/staging`/`data/outputs` nem toca o app.
Gera/atualiza `data/reports/perf_baseline_dashboard.md`.

Uso: python scripts/profile_dashboard.py
"""
from __future__ import annotations

import gc
import logging
import platform
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Streamlit emite warnings de "missing ScriptRunContext" fora do runtime; sao
# esperados num harness de medicao e poluem a saida.
logging.getLogger("streamlit").setLevel(logging.ERROR)

import pandas as pd  # noqa: E402

REPORT_PATH = ROOT / "data" / "reports" / "perf_baseline_dashboard.md"

# Insumos lidos pelos loaders (apenas para registrar tamanho em disco no relatorio).
INPUT_ARTIFACTS = [
    "data/outputs/hexagonos_brasil_dashboard.parquet",
    "data/outputs/oportunidades_expansao_hibrido.parquet",
    "data/staging/censo2022_setores_calibrado.parquet",
    "data/staging/censo2022_setores_calibrado_piloto_expandido.parquet",
    "data/staging/censo2022_setores_validado_v2.parquet",
    "data/staging/brasil_estrutural.parquet",
]

MB = 1024 * 1024


def _make_rss_sampler():
    """Retorna (sampler, descricao_backend). psutil mede RSS real; fallback usa
    tracemalloc (heap Python, subestima arrays numpy) quando psutil ausente."""
    try:
        import psutil

        proc = psutil.Process()

        def sample() -> float | None:
            return proc.memory_info().rss / MB

        return sample, f"psutil {psutil.__version__} (RSS do processo)"
    except Exception:
        import tracemalloc

        if not tracemalloc.is_tracing():
            tracemalloc.start()

        def sample() -> float | None:
            current, _peak = tracemalloc.get_traced_memory()
            return current / MB

        return sample, "tracemalloc (heap Python; subestima numpy, nao e RSS)"


def _fmt(value, digits: int = 1) -> str:
    if value is None:
        return "n/d"
    return f"{value:,.{digits}f}".replace(",", "_")


def main() -> int:
    rss, rss_backend = _make_rss_sampler()
    import streamlit_app as app  # import tardio: side-effects de modulo do app

    gc.collect()
    rss_baseline = rss()
    steps: list[dict] = []

    def measure(label: str, fn):
        gc.collect()
        before = rss()
        t0 = time.perf_counter()
        result = fn()
        elapsed = time.perf_counter() - t0
        gc.collect()
        after = rss()
        rows = len(result) if hasattr(result, "__len__") else None
        steps.append(
            {
                "step": label,
                "seconds": elapsed,
                "rss_before": before,
                "rss_after": after,
                "rss_delta": (after - before) if (before is not None and after is not None) else None,
                "rows": rows,
            }
        )
        return result

    m1 = measure("load_data", app.load_data)
    hybrid = measure("load_hybrid_data", app.load_hybrid_data)
    censo = measure("load_censo_trace_data", app.load_censo_trace_data)
    estrutural = measure("load_estrutural_pop", app.load_estrutural_pop)
    enriched = measure(
        "enrich_dashboard_data",
        lambda: app.enrich_dashboard_data(m1, hybrid, censo, estrutural_pop_df=estrutural),
    )

    total_seconds = sum(s["seconds"] for s in steps)
    peak_rss = max((s["rss_after"] for s in steps if s["rss_after"] is not None), default=None)

    # Peso de memoria do frame enriquecido, total e por UF.
    enriched_total_deep = enriched.memory_usage(deep=True).sum() / MB
    per_uf: list[dict] = []
    if "uf" in enriched.columns:
        for uf, group in enriched.groupby("uf", observed=True):
            per_uf.append(
                {
                    "uf": str(uf),
                    "hexes": len(group),
                    "mem_deep_mb": group.memory_usage(deep=True).sum() / MB,
                }
            )
        per_uf.sort(key=lambda r: r["hexes"], reverse=True)

    _write_report(
        rss_backend=rss_backend,
        rss_baseline=rss_baseline,
        steps=steps,
        total_seconds=total_seconds,
        peak_rss=peak_rss,
        enriched=enriched,
        enriched_total_deep=enriched_total_deep,
        per_uf=per_uf,
    )

    print(f"Baseline gravado em {REPORT_PATH.relative_to(ROOT)}")
    print(f"Cold start total: {total_seconds:.1f}s | RSS pico: {_fmt(peak_rss)} MB | backend: {rss_backend}")
    print(f"Frame enriquecido: {len(enriched):,} linhas x {enriched.shape[1]} colunas | {enriched_total_deep:,.0f} MB (deep)")
    return 0


def _write_report(
    *,
    rss_backend: str,
    rss_baseline,
    steps: list[dict],
    total_seconds: float,
    peak_rss,
    enriched: pd.DataFrame,
    enriched_total_deep: float,
    per_uf: list[dict],
) -> None:
    lines: list[str] = []
    lines.append("# Baseline de performance do dashboard")
    lines.append("")
    lines.append(f"> Gerado por `scripts/profile_dashboard.py` em {date.today().isoformat()}.")
    lines.append("> Reproduzir: `python scripts/profile_dashboard.py`. Mede a carga a frio dos loaders")
    lines.append("> e do merge `enrich_dashboard_data`, sem alterar o runtime do app.")
    lines.append("")

    lines.append("## Ambiente")
    lines.append("")
    lines.append(f"- Python: {platform.python_version()} ({platform.system()} {platform.release()})")
    lines.append(f"- pandas: {pd.__version__}")
    lines.append(f"- Backend de memoria: {rss_backend}")
    lines.append(f"- RSS no import do app (baseline): {_fmt(rss_baseline)} MB")
    lines.append("")

    lines.append("## Insumos em disco")
    lines.append("")
    lines.append("| artefato | tamanho (MB) | presente |")
    lines.append("| --- | ---: | :---: |")
    for rel in INPUT_ARTIFACTS:
        p = ROOT / rel
        if p.exists():
            size = p.stat().st_size / MB
            lines.append(f"| `{rel}` | {size:,.1f} | sim |")
        else:
            lines.append(f"| `{rel}` | n/d | nao |")
    lines.append("")

    lines.append("## Custo por etapa (cold start)")
    lines.append("")
    lines.append("| etapa | linhas | tempo (s) | RSS antes (MB) | RSS depois (MB) | RSS delta (MB) |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
    for s in steps:
        rows = f"{s['rows']:,}".replace(",", "_") if s["rows"] is not None else "n/d"
        lines.append(
            f"| `{s['step']}` | {rows} | {s['seconds']:.2f} | "
            f"{_fmt(s['rss_before'])} | {_fmt(s['rss_after'])} | {_fmt(s['rss_delta'])} |"
        )
    lines.append(f"| **total** |  | **{total_seconds:.2f}** |  | **{_fmt(peak_rss)}** (pico) |  |")
    lines.append("")
    lines.append(
        f"Frame enriquecido final: **{len(enriched):,}** linhas x **{enriched.shape[1]}** colunas, "
        f"**{enriched_total_deep:,.0f} MB** em memoria (`memory_usage(deep=True)`)."
    )
    lines.append("")

    if per_uf:
        lines.append("## Peso de memoria por UF (frame enriquecido, deep)")
        lines.append("")
        lines.append("Ordenado por numero de hexagonos. O app hoje retem o frame nacional inteiro")
        lines.append("mesmo exibindo 1 UF por vez; esta tabela dimensiona o ganho do carregamento lazy.")
        lines.append("")
        lines.append(
            f"Nota: a soma por UF (TOTAL abaixo) excede o frame nacional ({enriched_total_deep:,.0f} MB) "
            "porque fatiar por UF duplica o dicionario das colunas `category`; trate os valores por UF "
            "como teto superior do slice isolado, nao como fracao exata do frame unico."
        )
        lines.append("")
        lines.append("| UF | hexagonos | memoria deep (MB) |")
        lines.append("| --- | ---: | ---: |")
        for r in per_uf:
            lines.append(f"| {r['uf']} | {r['hexes']:,} | {r['mem_deep_mb']:,.1f} |")
        total_hexes = sum(r["hexes"] for r in per_uf)
        total_mem = sum(r["mem_deep_mb"] for r in per_uf)
        lines.append(f"| **TOTAL** | **{total_hexes:,}** | **{total_mem:,.1f}** |")
        lines.append("")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
