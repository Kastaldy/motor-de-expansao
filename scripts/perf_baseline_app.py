"""
Baseline de performance ponta-a-ponta do app (BLK-REV-01).

Harness de medicao headless (sem Streamlit rodando, sem browser) que importa as
funcoes puras de `data.py`/`components.py`/`censo_*`/`relatorio_municipal.py` e mede
o LADO PYTHON/SERVIDOR dos 6 caminhos de uso, frio (1a chamada) e quente (2a chamada
imediata no mesmo processo), por tamanho de UF (RO pequena / SC media / AM grande):

  B1. Carga inicial por UF          -> read_enriched_uf_partition
  B2. Troca de UF/municipio         -> apply_global_filters
  B3. Render do mapa M1             -> build_map_figure (custo Python; WebGL nao medido)
  B4. Troca de modo de cor          -> build_hybrid_map_figure(color_col=...)
  B5. Cenario multiplo              -> agregar_cenario_multihex
  B6. PDF Pontual / Municipal       -> gerar_pdf_* com mapas=None (fpdf2 offline)

Escreve o relatorio `data/analysis/perf_baseline_app_2026.md` (gitignored).

READ-ONLY sobre o M1: NADA em `src/`, `config.py`, `pipelines/m1/`, `streamlit_app.py`
ou artefatos oficiais e tocado. Nenhuma funcao chamada recalcula score. O script sai
com codigo 0 e e auto-validante.

Uso: python scripts/perf_baseline_app.py
"""
from __future__ import annotations

import gc
import logging
import os
import platform
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Streamlit emite "missing ScriptRunContext" fora do runtime; esperado num harness.
logging.getLogger("streamlit").setLevel(logging.ERROR)

import pandas as pd  # noqa: E402

from motor_expansao.dashboard.censo_point import (  # noqa: E402
    analisar_ponto_censitario_setores,
)
from motor_expansao.dashboard.censo_report import (  # noqa: E402
    gerar_pdf_relatorio_pontual_censitario,
)
from motor_expansao.dashboard.components import (  # noqa: E402
    build_hybrid_map_figure,
    build_map_figure,
)
from motor_expansao.dashboard.data import (  # noqa: E402
    agregar_cenario_multihex,
    apply_global_filters,
    read_censo_geo_partition,
    read_enriched_uf_partition,
)
from motor_expansao.dashboard.relatorio_municipal import (  # noqa: E402
    agregar_municipio,
    gerar_pdf_relatorio_municipal,
)

MB = 1024 * 1024
GB = 1024 * MB

ENRIQUECIDO_DIR = ROOT / "data" / "outputs" / "hexagonos_dashboard_enriquecido"
CENSO_GEO_DIR = ROOT / "data" / "outputs" / "setores_censitarios_2022_geo"
REPORT_PATH = ROOT / "data" / "analysis" / "perf_baseline_app_2026.md"
BASELINE_MAI_PATH = ROOT / "data" / "reports" / "perf_baseline_dashboard.md"

UFS = ["RO", "SC", "AM"]  # pequena / media / grande
CIDADES = {"RO": "Porto Velho", "SC": "Florianópolis", "AM": "Manaus"}
COLOR_COLS = [
    "score_expansao_hibrido",
    "score_setor_2022_calibrado",
    "score_oportunidade_residual",
    "score_priorizacao",
]


def _make_rss_sampler():
    """Retorna (sampler, descricao_backend). psutil mede RSS real; fallback usa
    tracemalloc (heap Python, subestima arrays numpy) quando psutil ausente."""
    try:
        import psutil

        proc = psutil.Process()
        return (
            lambda: proc.memory_info().rss / MB
        ), f"psutil {psutil.__version__} (RSS do processo)"
    except Exception:
        import tracemalloc

        if not tracemalloc.is_tracing():
            tracemalloc.start()
        return (
            lambda: tracemalloc.get_traced_memory()[0] / MB
        ), "tracemalloc (heap Python; subestima numpy, nao e RSS)"


rss, RSS_BACKEND = _make_rss_sampler()


def bench(fn):
    """Roda fn() frio e quente; retorna (t_frio_s, t_quente_s, pico_mem_MB, resultado_quente).

    Frio = 1a chamada apos gc.collect(); quente = 2a chamada imediata no mesmo processo
    (sem re-ler disco / sem @st.cache). Pico = maior RSS amostrado nas 3 fronteiras.
    """
    gc.collect()
    m0 = rss()
    t0 = time.perf_counter()
    out = fn()
    t_frio = time.perf_counter() - t0
    m1 = rss()
    t0 = time.perf_counter()
    out = fn()
    t_quente = time.perf_counter() - t0
    m2 = rss()
    pico = max((v for v in (m0, m1, m2) if v is not None), default=None)
    return t_frio, t_quente, pico, out


def _fmt(value, digits: int = 3) -> str:
    if value is None:
        return "n/d"
    return f"{value:,.{digits}f}".replace(",", "_")


def _row(caminho: str, uf_tam: str, tf, tq, pico, nota: str = "") -> dict:
    return {
        "caminho": caminho,
        "uf_tam": uf_tam,
        "t_frio_s": tf,
        "t_quente_s": tq,
        "pico_mem_MB": pico,
        "nota": nota,
    }


def main() -> int:
    rows: list[dict] = []
    dfs: dict[str, pd.DataFrame] = {}

    # ------------------------------------------------------------------ B1
    print("[B1] Carga inicial por UF (read_enriched_uf_partition)...")
    for uf in UFS:
        tf, tq, pico, df = bench(
            lambda uf=uf: read_enriched_uf_partition(ENRIQUECIDO_DIR, uf)
        )
        dfs[uf] = df
        rows.append(
            _row(
                "1. Carga inicial (read_enriched_uf_partition)",
                f"{uf} ({len(df):,} hexes)".replace(",", "_"),
                tf,
                tq,
                pico,
                "frio nao e 100% frio de disco (page cache do SO pode estar quente)",
            )
        )
        print(f"   {uf}: frio {tf:.3f}s / quente {tq:.3f}s / {len(df):,} hexes")

    # ------------------------------------------------------------------ B2
    print("[B2] Filtro por municipio (apply_global_filters)...")
    for uf in UFS:
        df = dfs[uf]
        cidade = CIDADES[uf]
        tf, tq, pico, sub = bench(
            lambda df=df, uf=uf, cidade=cidade: apply_global_filters(
                df, selected_ufs=[uf], selected_cities=[cidade], selected_faixas=[]
            )
        )
        rows.append(
            _row(
                "2. Filtro por municipio (apply_global_filters)",
                f"{cidade}/{uf} ({len(sub):,} hexes)".replace(",", "_"),
                tf,
                tq,
                pico,
            )
        )
        print(f"   {cidade}/{uf}: frio {tf:.3f}s / quente {tq:.3f}s / {len(sub):,} hexes")

    # ------------------------------------------------------------------ B3
    print("[B3] Render mapa M1 (build_map_figure)...")
    for uf in UFS:
        df = dfs[uf]
        tf, tq, pico, (deck, n) = bench(
            lambda df=df, uf=uf: build_map_figure(
                df,
                selected_ufs=[uf],
                selected_cities=[],
                competitors_df=None,
                ultra_df=None,
            )
        )
        rows.append(
            _row(
                "3. Render mapa M1 (build_map_figure)",
                f"{uf} (cap {n:,})".replace(",", "_"),
                tf,
                tq,
                pico,
                "so custo Python; WebGL/paint = browser (nao medido)",
            )
        )
        print(f"   {uf}: frio {tf:.3f}s / quente {tq:.3f}s / cap servido {n:,}")

    # ------------------------------------------------------------------ B4
    print("[B4] Troca de modo de cor (build_hybrid_map_figure)...")
    df_am = dfs["AM"]
    for col in COLOR_COLS:
        tf, tq, pico, (deck, n) = bench(
            lambda col=col: build_hybrid_map_figure(
                df_am,
                selected_ufs=["AM"],
                selected_cities=[],
                color_col=col,
                competitors_df=None,
                ultra_df=None,
            )
        )
        rows.append(
            _row(
                "4. Troca de cor (build_hybrid_map_figure)",
                f"AM - {col} (cap {n:,})".replace(",", "_"),
                tf,
                tq,
                pico,
                "rerun do Streamlit reexecuta o builder inteiro; este e o custo integral",
            )
        )
        print(f"   AM/{col}: frio {tf:.3f}s / quente {tq:.3f}s / cap servido {n:,}")

    # ------------------------------------------------------------------ B5
    print("[B5] Cenario multi-hex (agregar_cenario_multihex)...")
    df_sc = dfs["SC"]
    sample_ids = df_sc["hex_id"].dropna().head(20).tolist()
    for k in (1, 5, 20):
        ids = sample_ids[:k]
        tf, tq, pico, _r = bench(lambda ids=ids: agregar_cenario_multihex(df_sc, ids))
        rows.append(
            _row(
                "5. Cenario multi-hex (agregar_cenario_multihex)",
                f"SC - {k} hex",
                tf,
                tq,
                pico,
            )
        )
        print(f"   SC/{k} hex: frio {tf:.3f}s / quente {tq:.3f}s")

    # ------------------------------------------------------------------ B6
    print("[B6] PDF Pontual e Municipal (fpdf2, mapas=None)...")
    # 6a. Pontual — Florianopolis (setores geo)
    try:
        setores = read_censo_geo_partition(CENSO_GEO_DIR, "SC", "4205407")
        res_pontual = analisar_ponto_censitario_setores(-27.5954, -48.5480, setores)
        tf, tq, pico, pdf = bench(
            lambda: gerar_pdf_relatorio_pontual_censitario(res_pontual, mapas=None)
        )
        rows.append(
            _row(
                "6a. PDF Pontual (fpdf2, mapas=None)",
                f"Floripa/SC ({len(pdf) // 1024} KB)",
                tf,
                tq,
                pico,
                "offline; composicao de mapas PNG (contextily) NAO medida",
            )
        )
        print(f"   Pontual Floripa/SC: frio {tf:.3f}s / quente {tq:.3f}s / {len(pdf) // 1024} KB")
    except Exception as exc:  # noqa: BLE001 — defensivo; nao abortar o script
        rows.append(
            _row(
                "6a. PDF Pontual (fpdf2, mapas=None)",
                "Floripa/SC",
                None,
                None,
                None,
                f"n/d - {type(exc).__name__}: {str(exc)[:80]}",
            )
        )
        print(f"   Pontual Floripa/SC: n/d - {type(exc).__name__}: {exc}")

    # 6b. Municipal — Florianopolis (df de SC)
    try:
        mres = agregar_municipio(df_sc, nome_municipio="Florianópolis", uf="SC")
        tf, tq, pico, mpdf = bench(
            lambda: gerar_pdf_relatorio_municipal(mres, mapas=None)
        )
        rows.append(
            _row(
                "6b. PDF Municipal (fpdf2, mapas=None)",
                f"Floripa/SC ({len(mpdf) // 1024} KB)",
                tf,
                tq,
                pico,
                "offline; composicao de mapas PNG (contextily) NAO medida",
            )
        )
        print(f"   Municipal Floripa/SC: frio {tf:.3f}s / quente {tq:.3f}s / {len(mpdf) // 1024} KB")
    except Exception as exc:  # noqa: BLE001 — defensivo; nao abortar o script
        rows.append(
            _row(
                "6b. PDF Municipal (fpdf2, mapas=None)",
                "Floripa/SC",
                None,
                None,
                None,
                f"n/d - {type(exc).__name__}: {str(exc)[:80]}",
            )
        )
        print(f"   Municipal Floripa/SC: n/d - {type(exc).__name__}: {exc}")

    _write_report(rows)
    print(f"\nRelatorio gravado em {REPORT_PATH.relative_to(ROOT)} ({len(rows)} linhas de benchmark)")
    return 0


def _env_lines() -> list[str]:
    ram_total = "n/d"
    try:
        import psutil

        ram_total = f"{psutil.virtual_memory().total / GB:,.1f} GB"
    except Exception:
        pass
    cpu = platform.processor() or "n/d"
    return [
        f"- Python: {platform.python_version()} ({platform.system()} {platform.release()})",
        f"- pandas: {pd.__version__}",
        f"- CPU: {cpu} ({os.cpu_count()} logicos)",
        f"- RAM total: {ram_total}",
        f"- Backend de memoria: {RSS_BACKEND}",
    ]


def _write_report(rows: list[dict]) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    lines: list[str] = []
    lines.append("# Baseline de performance ponta-a-ponta do app (BLK-REV-01)")
    lines.append("")
    lines.append(f"> Gerado por `scripts/perf_baseline_app.py` em {now}.")
    lines.append("> Reproduzir: `python scripts/perf_baseline_app.py`.")
    lines.append(
        "> Mede o LADO PYTHON/SERVIDOR dos 6 caminhos de uso (frio/quente, por tamanho de UF),"
    )
    lines.append("> sem Streamlit rodando e sem browser. READ-ONLY sobre o M1 (nada em `src/`).")
    lines.append("")

    lines.append("## Ambiente")
    lines.append("")
    lines.extend(_env_lines())
    lines.append("")
    lines.append(
        "Metodo: cada caminho roda `fn()` duas vezes no mesmo processo — **frio** (1a chamada apos "
        "`gc.collect()`) e **quente** (2a chamada imediata, sem re-ler disco / sem `@st.cache`). "
        "`pico_mem_MB` = maior RSS amostrado nas 3 fronteiras da medicao. UFs escolhidas por tamanho: "
        "RO (pequena), SC (media), AM (grande)."
    )
    lines.append("")

    lines.append("## Resultados por caminho")
    lines.append("")
    lines.append("| caminho | UF/tamanho | t_frio_s | t_quente_s | pico_mem_MB | nota |")
    lines.append("| --- | --- | ---: | ---: | ---: | --- |")
    for r in rows:
        lines.append(
            f"| {r['caminho']} | {r['uf_tam']} | {_fmt(r['t_frio_s'])} | "
            f"{_fmt(r['t_quente_s'])} | {_fmt(r['pico_mem_MB'], 1)} | {r['nota']} |"
        )
    lines.append("")

    lines.append("## Comparativo com baseline mai/2026")
    lines.append("")
    if BASELINE_MAI_PATH.exists():
        lines.append(
            f"O baseline anterior (`{BASELINE_MAI_PATH.relative_to(ROOT)}`) media a **carga NACIONAL "
            "inteira** (cold start dos loaders + merge `enrich_dashboard_data`), com ancoras: cold start "
            "total na casa das dezenas de segundos e RSS pico nacional na casa das centenas de MB. **Nao e "
            "a mesma metrica** que esta aqui: aquele mede a carga do frame nacional unico; **este mede os 6 "
            "caminhos de uso por UF** (com carga lazy por particao). Portanto o comparativo e de CONTEXTO "
            "historico (o ganho da arquitetura lazy), nao de regressao direta linha-a-linha."
        )
    else:
        lines.append(
            f"Baseline anterior nao encontrado em `{BASELINE_MAI_PATH.relative_to(ROOT)}`; sem comparativo historico."
        )
    lines.append("")

    lines.append("## O que NAO foi medido e por que")
    lines.append("")
    lines.append(
        "- **Render WebGL / paint no browser**: o harness constroi o `pydeck.Deck` em Python mas nao "
        "renderiza pixels; o custo de GPU/paint e client-side e fica fora do escopo deste baseline."
    )
    lines.append(
        "- **Latencia de interacao/clique no mapa**: e browser-side (rerun disparado pelo `on_select`); "
        "nao reproduzivel headless."
    )
    lines.append(
        "- **Composicao dos mapas PNG dos PDFs (contextily/matplotlib + tiles)**: medimos o backbone "
        "`fpdf2` com `mapas=None` para isolar o lado Python; a geracao dos PNGs de mapa (com fetch de "
        "tiles) e um caminho de rede separado, nao medido aqui."
    )
    lines.append(
        "- **Overlays de concorrentes/Ultra nos mapas**: passados como `None` nos benchmarks B3/B4 para "
        "isolar o custo Python de render dos hexagonos (downsample + cap + color-map + tooltip), que e o "
        "alvo do bloco; os pins sao overlay separado."
    )
    lines.append(
        "- **\"Frio\" nao e 100% frio de disco**: o page cache do SO pode estar quente entre execucoes; "
        "o \"frio\" aqui e o custo de leitura + preparo do frame na 1a chamada do processo, nao um cold "
        "boot de disco."
    )
    lines.append("")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
