"""
jobs/scrapers/imovel_scraper.py — M3 Motor Imobiliário
Coleta imóveis comerciais via ZAP Imóveis, VivaReal e OLX.

Uso:
    python -m jobs.scrapers.imovel_scraper --cidade "São Paulo" --uf SP
"""

import asyncio
import re
import argparse
from datetime import datetime
from typing import Any

import structlog
import pandas as pd
from playwright.async_api import async_playwright, Page

from jobs.scrapers.base_scraper import BaseScraper
from api.config import settings

log = structlog.get_logger()


def _parse_numero(texto: str | None) -> float | None:
    """Extrai número de strings como 'R$ 45.000', '900 m²', '3,5 m'."""
    if not texto:
        return None
    numeros = re.findall(r"[\d.,]+", texto.replace(".", "").replace(",", "."))
    if not numeros:
        return None
    try:
        return float(numeros[0])
    except ValueError:
        return None


class ZapImoveisScraper(BaseScraper):
    """
    M3 — Scraper do ZAP Imóveis para comerciais de alto padrão.
    Foco: galpões e lojas com área ≥ 600m² para aluguel.

    Estratégia: Playwright (JS pesado) + parsing de cards.
    Rate limiting respeitoso com delays aleatórios.
    """

    NOME = "zap"
    BASE_URL = "https://www.zapimoveis.com.br/aluguel/salas-comerciais"

    async def coletar(self, cidade: str, uf: str = "") -> list[dict[str, Any]]:
        resultados = []
        cidade_slug = cidade.lower().replace(" ", "-")
        uf_lower = uf.lower()

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 900},
            )
            page: Page = await context.new_page()

            try:
                # URL de busca: salas/galpões para aluguel na cidade
                url = (
                    f"{self.BASE_URL}/{uf_lower}+{cidade_slug}"
                    f"/?areaMinima={int(settings.AREA_MIN_M2)}&tipoImovel=Galpao,Loja,SalaComercial"
                )
                log.info("zap_acessando", url=url)
                await page.goto(url, timeout=self.TIMEOUT, wait_until="networkidle")
                await self._delay_async()

                # Salvar snapshot para testes de contrato
                html = await page.content()
                await self._salvar_snapshot(html, f"{cidade_slug}_{uf_lower}")

                # Scroll para carregar lazy-loaded cards
                for _ in range(3):
                    await page.evaluate("window.scrollBy(0, window.innerHeight)")
                    await asyncio.sleep(1.5)

                # ----------------------------------------------------------------
                # Seletores ZAP — inspecionar e ajustar conforme HTML real
                # ZAP usa data attributes ou classes geradas — adaptar aqui
                # ----------------------------------------------------------------
                cards = await page.query_selector_all(
                    "[data-type='property'], .card-container, [class*='ListingCard']"
                )

                log.info("zap_cards_encontrados", cidade=cidade, total=len(cards))

                for card in cards:
                    try:
                        dados = await self._extrair_card(card, cidade, uf)
                        if dados and dados.get("area_m2"):
                            resultados.append(dados)
                    except Exception as e:
                        log.warning("zap_card_erro", erro=str(e))
                        continue

            except Exception as e:
                log.error("zap_page_erro", cidade=cidade, erro=str(e))
                raise
            finally:
                await browser.close()

        log.info("zap_coleta_concluida", cidade=cidade, total=len(resultados))
        return resultados

    async def _extrair_card(self, card, cidade: str, uf: str) -> dict[str, Any] | None:
        """Extrai dados estruturados de um card de imóvel."""

        # Título / descrição
        titulo_el = await card.query_selector("h2, h3, [class*='title'], [class*='Title']")
        titulo = await titulo_el.inner_text() if titulo_el else None

        # Preço de aluguel
        preco_el = await card.query_selector(
            "[class*='price'], [class*='Price'], [data-cy='listing-price']"
        )
        preco_texto = await preco_el.inner_text() if preco_el else None
        preco_aluguel = _parse_numero(preco_texto)

        # Área
        area_el = await card.query_selector(
            "[class*='area'], [aria-label*='área'], [aria-label*='area']"
        )
        area_texto = await area_el.inner_text() if area_el else None
        area_m2 = _parse_numero(area_texto)

        # Endereço
        end_el = await card.query_selector(
            "[class*='address'], [class*='Address'], [data-cy='listing-address']"
        )
        endereco = await end_el.inner_text() if end_el else None

        # URL do imóvel
        link_el = await card.query_selector("a")
        url_relativa = await link_el.get_attribute("href") if link_el else None
        url = f"https://www.zapimoveis.com.br{url_relativa}" if url_relativa else None

        return {
            "titulo": titulo.strip() if titulo else None,
            "tipo": "comercial",
            "area_m2": area_m2,
            "preco_aluguel": preco_aluguel,
            "endereco": endereco.strip() if endereco else None,
            "cidade": cidade,
            "uf": uf,
            "fonte": "zap",
            "url": url,
            "coletado_em": datetime.now().isoformat(),
        }


class VivarealScraper(BaseScraper):
    """
    M3 — Scraper do VivaReal (mesmo grupo do ZAP).
    API interna similar — ambos usam a plataforma OLX Group.
    """

    NOME = "vivareal"
    BASE_URL = "https://www.vivareal.com.br/aluguel/comercial"

    async def coletar(self, cidade: str, uf: str = "") -> list[dict[str, Any]]:
        resultados = []
        cidade_slug = cidade.lower().replace(" ", "-")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                url = (
                    f"{self.BASE_URL}/{uf.lower()}/{cidade_slug}/"
                    f"?areaMinima={int(settings.AREA_MIN_M2)}"
                )
                await page.goto(url, timeout=self.TIMEOUT, wait_until="networkidle")
                await self._delay_async()

                html = await page.content()
                await self._salvar_snapshot(html, f"{cidade_slug}")

                # VivaReal — seletores similares ao ZAP (mesma plataforma)
                cards = await page.query_selector_all(
                    "[data-type='property'], .property-card, [class*='PropertyCard']"
                )

                for card in cards:
                    try:
                        titulo_el = await card.query_selector("h2, h3, [class*='title']")
                        titulo = await titulo_el.inner_text() if titulo_el else None

                        preco_el = await card.query_selector("[class*='price']")
                        preco_texto = await preco_el.inner_text() if preco_el else None

                        area_el = await card.query_selector("[class*='area']")
                        area_texto = await area_el.inner_text() if area_el else None

                        end_el = await card.query_selector("[class*='address']")
                        endereco = await end_el.inner_text() if end_el else None

                        link_el = await card.query_selector("a")
                        href = await link_el.get_attribute("href") if link_el else None

                        area_m2 = _parse_numero(area_texto)
                        if area_m2 and area_m2 >= settings.AREA_MIN_M2:
                            resultados.append({
                                "titulo": titulo.strip() if titulo else None,
                                "tipo": "comercial",
                                "area_m2": area_m2,
                                "preco_aluguel": _parse_numero(preco_texto),
                                "endereco": endereco.strip() if endereco else None,
                                "cidade": cidade,
                                "uf": uf,
                                "fonte": "vivareal",
                                "url": f"https://www.vivareal.com.br{href}" if href else None,
                                "coletado_em": datetime.now().isoformat(),
                            })
                    except Exception:
                        continue

            finally:
                await browser.close()

        return resultados


class OlxComercialScraper(BaseScraper):
    """
    M3 — Scraper OLX para imóveis comerciais.
    OLX tem API mais acessível via requests — sem necessidade de Playwright.
    """

    NOME = "olx"

    async def coletar(self, cidade: str, uf: str = "") -> list[dict[str, Any]]:
        import httpx

        resultados = []
        uf_lower = uf.lower()

        # OLX API endpoint (verificar se ainda ativo)
        url = f"https://www.olx.com.br/api/ad-search"
        params = {
            "category": "imoveis",
            "subcategory": "comercial",
            "state": uf_lower,
            "city": cidade,
            "size": 50,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    anuncios = data.get("ads", data.get("data", []))
                    for a in anuncios:
                        resultados.append({
                            "titulo": a.get("title"),
                            "tipo": "comercial",
                            "area_m2": _parse_numero(a.get("area")),
                            "preco_aluguel": _parse_numero(str(a.get("price", ""))),
                            "endereco": a.get("location", {}).get("address"),
                            "cidade": cidade,
                            "uf": uf,
                            "fonte": "olx",
                            "url": a.get("url"),
                            "coletado_em": datetime.now().isoformat(),
                        })
            except Exception as e:
                log.warning("olx_api_falhou", erro=str(e), msg="Tentar scraping direto")

        return resultados


async def rodar_coleta_imoveis(cidade: str, uf: str) -> pd.DataFrame:
    """
    Roda todos os scrapers de imóveis em paralelo para uma cidade.
    Consolida, deduplica e exporta para staging.
    """
    log.info("coleta_imoveis_iniciada", cidade=cidade, uf=uf)

    scrapers = [
        ZapImoveisScraper(),
        VivarealScraper(),
        OlxComercialScraper(),
    ]

    # Rodar scrapers (sequencial para respeitar rate limiting)
    todos = []
    for scraper in scrapers:
        try:
            resultados = await scraper.rodar(cidade=cidade, uf=uf)
            todos.extend(resultados)
        except Exception as e:
            log.error("scraper_falhou_continuando", scraper=scraper.NOME, erro=str(e))

    if not todos:
        log.warning("nenhum_imovel_coletado", cidade=cidade)
        return pd.DataFrame()

    df = pd.DataFrame(todos)

    # Deduplicação básica por URL
    if "url" in df.columns:
        df = df.drop_duplicates(subset=["url"], keep="first")

    # Exportar staging
    cidade_slug = cidade.lower().replace(" ", "_")
    output_path = f"data/staging/imoveis_{cidade_slug}_{uf.lower()}.parquet"
    df.to_parquet(output_path, index=False)

    log.info(
        "coleta_imoveis_concluida",
        cidade=cidade,
        total_bruto=len(todos),
        total_dedup=len(df),
        output=output_path,
    )
    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Coleta de imóveis comerciais")
    parser.add_argument("--cidade", required=True)
    parser.add_argument("--uf", required=True)
    args = parser.parse_args()

    asyncio.run(rodar_coleta_imoveis(args.cidade, args.uf))
