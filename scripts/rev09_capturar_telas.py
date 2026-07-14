"""BLK-REV-09 — captura as telas do dashboard renderizado para avaliacao heuristica de UX.

Sobe-se o app a parte; este script so NAVEGA e CAPTURA (READ-ONLY: nao escreve em
data/staging, nao toca score/carteira/artefatos do M1).

Uso:
    PYTHONPATH=src python -m streamlit run streamlit_app.py --server.port 8501 --server.headless true
    python scripts/rev09_capturar_telas.py data/reports/rev09_telas_novo

Requer o extra `[scraping]` (playwright). Relatorio da passagem de 2026-07-13:
`data/reports/rev09_passagem_heuristica_ux.md`.

Nota de metodo: seleciona-se a PRIMEIRA UF da lista (= AC) de proposito. O Acre nao tem
unidades Ultra e tem densidade baixa, o que expoe o comportamento do app em estados-limite
(rede vazia, hexes abaixo do corte de 5k hab) — varios achados so aparecem nesse cenario.
"""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

URL = "http://localhost:8501/"
VIEWPORT = {"width": 1600, "height": 1000}
ABAS = ["Mapa", "Executivo", "Expansão de Domínio", "Carteira e Plano", "Viabilidade"]


def settle(page: Page, ms: int = 3000) -> None:
    """O Streamlit re-renderiza em ondas: espera o spinner sumir + uma folga."""
    try:
        page.wait_for_selector('[data-testid="stStatusWidget"]', state="detached", timeout=10_000)
    except Exception:
        pass
    page.wait_for_timeout(ms)


def medir_layout(page: Page) -> dict[str, float | int | None]:
    """Mede a 'dobra': a que distancia do topo o mapa comeca, e quanta moldura ha antes dele."""
    return page.evaluate(
        """() => {
            const topo = (el) => el ? el.getBoundingClientRect().top + window.scrollY : null;
            const deck = document.querySelector('[data-testid="stDeckGlJsonChart"]');
            return {
                topo_do_mapa_px: topo(deck) ?? topo(document.querySelector('canvas')),
                altura_viewport: window.innerHeight,
                n_expanders: document.querySelectorAll('[data-testid="stExpander"]').length,
                n_captions: document.querySelectorAll('[data-testid="stCaptionContainer"]').length,
                n_metrics: document.querySelectorAll('[data-testid="stMetric"]').length,
            };
        }"""
    )


def main() -> int:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "data/reports/rev09_telas_novo")
    out.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport=VIEWPORT)
        page.goto(URL, wait_until="networkidle", timeout=90_000)
        settle(page, 8000)
        page.screenshot(path=str(out / "01_landing.png"))

        # O app faz st.stop() sem UF: seleciona a PRIMEIRA da lista (ver nota de metodo).
        page.locator('[data-testid="stSelectbox"]').first.click()
        page.wait_for_timeout(800)
        page.locator('[role="option"]').first.click()
        settle(page, 9000)

        for i, aba in enumerate(ABAS, start=2):
            try:
                page.get_by_text(aba, exact=True).first.click(timeout=15_000)
                settle(page, 8000)
            except Exception as exc:  # noqa: BLE001 — captura best-effort, nao deve abortar o resto
                print(f"! falha ao abrir a aba {aba}: {exc}")
                continue
            slug = aba.lower().replace(" ", "_").replace("ã", "a").replace("í", "i")
            page.screenshot(path=str(out / f"{i:02d}_aba_{slug}.png"))
            if aba == "Mapa":
                medidas = medir_layout(page)
                print("=== MEDIDAS (aba Mapa) ===")
                for k, v in medidas.items():
                    print(f"  {k}: {v}")
                topo = medidas.get("topo_do_mapa_px")
                if topo:
                    print(f"  --> mapa comeca a {topo:.0f}px = {topo / VIEWPORT['height']:.2f} telas de rolagem")

                # Abre a Legenda (colapsada por padrao) e rola ate o mapa para evidenciar o custo.
                try:
                    page.get_by_text("Legenda", exact=True).first.click()
                    settle(page, 2500)
                except Exception:
                    pass
                page.mouse.move(800, 600)
                for _ in range(6):  # o Streamlit rola num container interno: usar a roda
                    page.mouse.wheel(0, 400)
                    page.wait_for_timeout(700)
                page.wait_for_timeout(4000)
                page.screenshot(path=str(out / "02b_mapa_com_legenda.png"))

        browser.close()

    print(f"telas em: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
