#!/usr/bin/env python3
"""rev08_spike_playwright.py — harness de medição do spike deck.gl (BLK-REV-08).

Cronometra os 4 fluxos de dor do dashboard (REV-03..06) contra uma URL
parametrizável, lendo os marcadores `window.__spike*` que o spike expõe via
`performance.now()`:

  render    (REV-03 dor #1)  -> window.__spikeFirstPaintMs
  recolor   (REV-04 dor #2)  -> window.__spikeRecolorMs   (toggle M1<->Residual)
  scenario  (REV-05 dor #3)  -> window.__spikeAddHexMs     (add ao cenário)
  pdf       (REV-06 dor #4)  -> wall-clock clique->download (SÓ --target production)

Agrega mediana / p95 por fluxo e grava JSON em --out.

GUARDA ANTI-PRODUÇÃO: se a --url contém `ultra-expansao.tech` SEM a flag
`--i-confirm-production`, o script ABORTA. A esteira autônoma NUNCA gera
tráfego real contra produção; rodar contra produção é ação/decisão HUMANA
(ver docs/rev08_spike_perf_runbook.md, §6 — comandos na VPS por confirmação).

NÃO adiciona dependência: playwright já está no extra `[scraping]` do
pyproject.toml. O import de playwright é lazy (só ao executar um fluxo com
browser), então `--help` funciona mesmo sem o pacote instalado.

Uso típico (local, spike):
    python scripts/rev08_spike_playwright.py --url http://localhost:8501 \\
        --uf SP --flow all --runs 5 --out data/reports/scratch/rev08_spike.json

READ-ONLY sobre o M1: mede render/UX; não toca score/pesos/artefatos.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

_PROD_HOST = "ultra-expansao.tech"
_MARKERS = {
    "render": "__spikeFirstPaintMs",
    "recolor": "__spikeRecolorMs",
    "scenario": "__spikeAddHexMs",
}
_ALL_FLOWS = ["render", "recolor", "scenario", "pdf"]


def build_parser() -> argparse.ArgumentParser:
    """Constrói o parser da CLI (sem efeitos colaterais — testável por --help)."""
    p = argparse.ArgumentParser(
        prog="rev08_spike_playwright.py",
        description=(
            "Harness Playwright do spike deck.gl (BLK-REV-08). "
            "Cronometra render/recolor/cenário/PDF. NÃO auto-roda contra "
            "produção (guarda anti-produção)."
        ),
    )
    p.add_argument(
        "--url",
        default="http://localhost:8501",
        help="URL do dashboard/spike (default: http://localhost:8501).",
    )
    p.add_argument(
        "--uf",
        default="SP",
        help="Sigla da UF a exercitar (default: SP).",
    )
    p.add_argument(
        "--flow",
        choices=[*_ALL_FLOWS, "all"],
        default="all",
        help="Fluxo de dor a medir (default: all).",
    )
    p.add_argument(
        "--runs",
        type=int,
        default=5,
        help="Repetições por fluxo para agregar mediana/p95 (default: 5).",
    )
    p.add_argument(
        "--out",
        default="",
        help="Caminho do JSON de saída (opcional; senão imprime no stdout).",
    )
    p.add_argument(
        "--target",
        choices=["spike", "production"],
        default="spike",
        help=(
            "spike = protótipo deck.gl (PDF pulado); production = dashboard "
            "real (habilita o fluxo pdf). Default: spike."
        ),
    )
    p.add_argument(
        "--i-confirm-production",
        action="store_true",
        help=(
            "Confirmação HUMANA explícita para rodar contra produção "
            "(ultra-expansao.tech). Sem esta flag, URL de produção aborta."
        ),
    )
    p.add_argument(
        "--headed",
        action="store_true",
        help="Roda o browser com janela visível (default: headless).",
    )
    p.add_argument(
        "--timeout-ms",
        type=int,
        default=60_000,
        help="Timeout de navegação/espera por fluxo em ms (default: 60000).",
    )
    return p


def check_production_guard(url: str, confirmed: bool) -> str | None:
    """Retorna mensagem de erro se a URL for produção sem confirmação, senão None."""
    if _PROD_HOST in url and not confirmed:
        return (
            f"ABORTADO: a URL {url!r} aponta para produção ({_PROD_HOST}).\n"
            "Rodar o harness contra produção gera tráfego real e é ação/decisão\n"
            "HUMANA (não a esteira autônoma). Se for intencional, repita com a\n"
            "flag --i-confirm-production. Ver docs/rev08_spike_perf_runbook.md."
        )
    return None


def _aggregate(samples: list[float]) -> dict[str, Any]:
    """Mediana/p95/min/max/n de uma lista de amostras (ms)."""
    clean = [s for s in samples if s is not None]
    if not clean:
        return {"n": 0, "median_ms": None, "p95_ms": None, "min_ms": None, "max_ms": None}
    ordered = sorted(clean)
    if len(ordered) == 1:
        p95 = ordered[0]
    else:
        # p95 por interpolação simples (quantiles n=20 → índice 18 = 95%).
        p95 = statistics.quantiles(ordered, n=20)[18] if len(ordered) >= 2 else ordered[-1]
    return {
        "n": len(clean),
        "median_ms": round(statistics.median(clean), 3),
        "p95_ms": round(p95, 3),
        "min_ms": round(min(clean), 3),
        "max_ms": round(max(clean), 3),
    }


def _read_spike_marker(page: Any, marker: str) -> float | None:
    """Lê window.<marker> no frame que o contém (o componente Streamlit vive
    num iframe). Retorna o primeiro valor não-nulo encontrado, ou None."""
    for frame in page.frames:
        try:
            val = frame.evaluate(f"() => window.{marker}")
        except Exception:
            val = None
        if val is not None:
            try:
                return float(val)
            except (TypeError, ValueError):
                return None
    return None


def _run_browser_flows(args: argparse.Namespace) -> dict[str, Any]:
    """Executa os fluxos com Playwright. Import lazy (dep opcional)."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - depende do ambiente do humano
        raise SystemExit(
            "playwright não instalado. Instale o extra [scraping] e os browsers:\n"
            "  pip install -e '.[scraping]' && python -m playwright install chromium\n"
            f"(detalhe: {exc})"
        ) from exc

    flows = _ALL_FLOWS if args.flow == "all" else [args.flow]
    samples: dict[str, list[float]] = {f: [] for f in flows}
    notes: list[str] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not args.headed)
        try:
            for _run in range(args.runs):
                page = browser.new_page()
                page.set_default_timeout(args.timeout_ms)
                page.goto(args.url, wait_until="load")
                # O humano ajusta os seletores ao layout real. Aqui tentamos
                # acionar "Gerar recorte" quando presente (spike/proto).
                try:
                    btn = page.get_by_role("button", name="Gerar recorte")
                    if btn.count() > 0:
                        btn.first.click()
                except Exception:
                    pass
                # Espera o primeiro paint dos hexes.
                page.wait_for_timeout(2_000)

                for flow in flows:
                    if flow == "pdf":
                        continue
                    if flow == "recolor":
                        _eval_all_frames(page, "window.__spikeToggleColor && window.__spikeToggleColor()")
                        page.wait_for_timeout(500)
                    elif flow == "scenario":
                        _eval_all_frames(page, "window.__spikeAddHex && window.__spikeAddHex()")
                        page.wait_for_timeout(500)
                    marker = _MARKERS[flow]
                    samples[flow].append(_read_spike_marker(page, marker) or float("nan"))

                if "pdf" in flows:
                    if args.target != "production":
                        notes.append(
                            "fluxo 'pdf' PULADO: o spike não gera PDF (dor "
                            "server-side do app real). Use --target production."
                        )
                    else:
                        ms = _measure_pdf_download(page, args.timeout_ms)
                        if ms is not None:
                            samples["pdf"].append(ms)
                        else:
                            notes.append("fluxo 'pdf': download não capturado (ajuste o seletor).")
                page.close()
        finally:
            browser.close()

    # Limpa NaN das amostras.
    clean = {f: [s for s in v if s == s] for f, v in samples.items()}  # noqa: PLR0124
    return {
        "flows": {f: _aggregate(v) for f, v in clean.items()},
        "notes": sorted(set(notes)),
        "raw_samples_ms": clean,
    }


def _eval_all_frames(page: Any, expr: str) -> None:
    """Avalia uma expressão JS em todos os frames (o componente vive em iframe)."""
    for frame in page.frames:
        try:
            frame.evaluate(f"() => {{ {expr}; }}")
        except Exception:
            pass


def _measure_pdf_download(page: Any, timeout_ms: int) -> float | None:
    """Cronometra clique->download do PDF (só faz sentido em --target production)."""
    import time

    try:
        with page.expect_download(timeout=timeout_ms) as dl_info:
            btn = page.get_by_role("button", name="Gerar relatório")
            t0 = time.perf_counter()
            btn.first.click()
        dl_info.value  # noqa: B018 - força a resolução do download
        return (time.perf_counter() - t0) * 1000.0
    except Exception:
        return None


def main(argv: list[str] | None = None) -> int:
    """Ponto de entrada. Retorna código de saída (0 ok; 2 guarda anti-produção)."""
    args = build_parser().parse_args(argv)

    guard_msg = check_production_guard(args.url, args.i_confirm_production)
    if guard_msg is not None:
        print(guard_msg, file=sys.stderr)
        return 2

    result: dict[str, Any] = {
        "url": args.url,
        "uf": args.uf,
        "flow": args.flow,
        "runs": args.runs,
        "target": args.target,
    }
    result.update(_run_browser_flows(args))

    out_json = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(out_json, encoding="utf-8")
        print(f"Resultado gravado em {out_path}")
    else:
        print(out_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
