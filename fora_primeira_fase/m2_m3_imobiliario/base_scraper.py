"""
jobs/scrapers/base_scraper.py — Classe base para todos os scrapers
Implementa retry, rate limiting, logging e persistência de snapshots.
"""

import asyncio
import random
import time
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog
from playwright.async_api import Browser, Page, async_playwright

log = structlog.get_logger()


class BaseScraper(ABC):
    """
    Classe base para scrapers do Motor de Expansão.
    Implementa: retry, delays, snapshots, logging estruturado.
    """

    NOME: str = "base_scraper"
    DELAY_MIN: float = 2.0
    DELAY_MAX: float = 5.0
    MAX_RETRIES: int = 3
    TIMEOUT: int = 30_000  # ms para Playwright

    def __init__(self, salvar_snapshot: bool = True):
        self.salvar_snapshot = salvar_snapshot
        self.snapshot_dir = Path(f"data/snapshots/{self.NOME}")
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)

    def _delay(self) -> None:
        """Delay aleatório entre requests."""
        delay = random.uniform(self.DELAY_MIN, self.DELAY_MAX)
        time.sleep(delay)

    async def _delay_async(self) -> None:
        delay = random.uniform(self.DELAY_MIN, self.DELAY_MAX)
        await asyncio.sleep(delay)

    async def _salvar_snapshot(self, conteudo: str, identificador: str) -> None:
        """Salva snapshot do HTML para testes de contrato."""
        if not self.salvar_snapshot:
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.snapshot_dir / f"{identificador}_{ts}.html"
        path.write_text(conteudo, encoding="utf-8")
        log.debug("snapshot_salvo", scraper=self.NOME, path=str(path))

    @abstractmethod
    async def coletar(self, **kwargs) -> list[dict[str, Any]]:
        """Implementar em cada scraper específico."""
        ...

    async def rodar(self, **kwargs) -> list[dict[str, Any]]:
        """Executa o scraper com tratamento de erros e logging."""
        log.info("scraper_iniciado", scraper=self.NOME, params=kwargs)
        inicio = datetime.now()

        try:
            resultados = await self.coletar(**kwargs)
            duracao = (datetime.now() - inicio).total_seconds()
            log.info(
                "scraper_concluido",
                scraper=self.NOME,
                total=len(resultados),
                duracao_s=round(duracao, 1),
            )
            return resultados
        except Exception as e:
            log.error("scraper_falhou", scraper=self.NOME, erro=str(e))
            raise


class WellhubScraper(BaseScraper):
    """
    M2 — Scraper do Wellhub (ex-Gympass) para mapear academias credenciadas.
    Coleta: nome, endereço, cidade, lat/lng de academias por cidade.

    Wellhub usa renderização JS — requer Playwright.
    """

    NOME = "wellhub"
    BASE_URL = "https://wellhub.com/pt-br/parceiros/academias"

    async def coletar(self, cidade: str, uf: str = "") -> list[dict[str, Any]]:
        """
        Coleta academias do Wellhub para uma cidade.
        Retorna lista de dicts com dados da academia.
        """
        resultados = []

        async with async_playwright() as p:
            browser: Browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
            )
            page: Page = await context.new_page()

            try:
                url = f"{self.BASE_URL}?city={cidade.lower().replace(' ', '-')}"
                log.info("wellhub_acessando", url=url)

                await page.goto(url, timeout=self.TIMEOUT, wait_until="networkidle")
                await self._delay_async()

                # Salvar snapshot para testes de contrato
                html = await page.content()
                await self._salvar_snapshot(html, f"{cidade.lower().replace(' ', '_')}")

                # ----------------------------------------------------------------
                # ADAPTAR seletores conforme estrutura real do Wellhub
                # Os seletores abaixo são exemplos — inspecionar o HTML real
                # ----------------------------------------------------------------
                cards = await page.query_selector_all("[data-testid='gym-card'], .gym-card, .partner-card")

                for card in cards:
                    try:
                        nome_el = await card.query_selector("h2, h3, [class*='name'], [class*='title']")
                        nome = await nome_el.inner_text() if nome_el else None

                        endereco_el = await card.query_selector("[class*='address'], [class*='location']")
                        endereco = await endereco_el.inner_text() if endereco_el else None

                        rede_el = await card.query_selector("[class*='brand'], [class*='network']")
                        rede = await rede_el.inner_text() if rede_el else None

                        if nome:
                            resultados.append({
                                "nome": nome.strip(),
                                "endereco": endereco.strip() if endereco else None,
                                "rede": rede.strip() if rede else None,
                                "cidade": cidade,
                                "uf": uf,
                                "fonte": "wellhub",
                                "coletado_em": datetime.now().isoformat(),
                            })
                    except Exception as e:
                        log.warning("wellhub_card_erro", erro=str(e))
                        continue

                log.info("wellhub_cards_coletados", cidade=cidade, total=len(resultados))

            except Exception as e:
                log.error("wellhub_page_erro", cidade=cidade, erro=str(e))
                raise
            finally:
                await browser.close()

        return resultados


class TotalpassScraper(BaseScraper):
    """
    M2 — Scraper do TotalPass para academias credenciadas.
    Estrutura similar ao Wellhub — adaptar seletores conforme HTML real.
    """

    NOME = "totalpass"
    BASE_URL = "https://totalpass.com/parceiros"

    async def coletar(self, cidade: str, uf: str = "") -> list[dict[str, Any]]:
        resultados = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                url = f"{self.BASE_URL}?cidade={cidade}"
                await page.goto(url, timeout=self.TIMEOUT, wait_until="networkidle")
                await self._delay_async()

                html = await page.content()
                await self._salvar_snapshot(html, f"{cidade.lower().replace(' ', '_')}")

                # TODO: Adaptar seletores ao HTML real do TotalPass
                cards = await page.query_selector_all(".gym-item, .academia-card, [class*='partner']")

                for card in cards:
                    try:
                        nome_el = await card.query_selector("h2, h3, .name, .title")
                        nome = await nome_el.inner_text() if nome_el else None

                        end_el = await card.query_selector(".address, .endereco, [class*='address']")
                        endereco = await end_el.inner_text() if end_el else None

                        if nome:
                            resultados.append({
                                "nome": nome.strip(),
                                "endereco": endereco.strip() if endereco else None,
                                "cidade": cidade,
                                "uf": uf,
                                "fonte": "totalpass",
                                "coletado_em": datetime.now().isoformat(),
                            })
                    except Exception:
                        continue

            finally:
                await browser.close()

        return resultados


class SmartfitScraper(BaseScraper):
    """
    M2 — Scraper SmartFit via API interna (JSON) ou sitemap.
    SmartFit expõe dados de unidades em JSON — mais estável que HTML parsing.
    """

    NOME = "smartfit"

    async def coletar(self, **kwargs) -> list[dict[str, Any]]:
        import httpx

        resultados = []

        # SmartFit geralmente expõe um endpoint tipo /api/units ou similar
        # Inspecionar Network tab do browser na página "Nossas unidades"
        urls_candidatas = [
            "https://www.smartfit.com.br/academia/busca",
            "https://www.smartfit.com.br/api/locations",
        ]

        async with httpx.AsyncClient(timeout=self.TIMEOUT / 1000) as client:
            for url in urls_candidatas:
                try:
                    resp = await client.get(url, headers={"Accept": "application/json"})
                    if resp.status_code == 200:
                        data = resp.json()
                        # Estrutura varia — adaptar ao JSON real
                        unidades = data if isinstance(data, list) else data.get("locations", data.get("units", []))
                        for u in unidades:
                            resultados.append({
                                "nome": u.get("name", u.get("nome", "")),
                                "endereco": u.get("address", u.get("endereco", "")),
                                "lat": u.get("latitude", u.get("lat")),
                                "lng": u.get("longitude", u.get("lng")),
                                "cidade": u.get("city", u.get("cidade", "")),
                                "uf": u.get("state", u.get("uf", "")),
                                "rede": "SmartFit",
                                "tipo": "rede_grande",
                                "fonte": "smartfit",
                                "coletado_em": datetime.now().isoformat(),
                            })
                        log.info("smartfit_coletado", total=len(resultados))
                        break
                except Exception as e:
                    log.warning("smartfit_tentativa_falhou", url=url, erro=str(e))
                    continue

        return resultados
