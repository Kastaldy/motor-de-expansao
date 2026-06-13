"""Cliente da Growth API Ultra (camada de Dimensionamento, BLK-DIM).

Responsabilidades:
- autenticacao (`POST /auth/login`) com relogin transparente em HTTP 401;
- throttle de janela deslizante (<= 10 req / 5 min) + backoff >= 30 s em HTTP 429;
- cache idempotente em disco por (endpoint, data_inicio, data_fim);
- guard anti-PII (`assert_sem_pii`) usado antes de qualquer persistencia.

NUNCA persiste PII; os endpoints consumidos (`/historico-dash`,
`/historico-dash-view`) retornam apenas agregados por unidade/data. READ-ONLY
sobre o M1.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import unicodedata
from collections import deque
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from dotenv import load_dotenv
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from motor_expansao.dimensionamento import config

logger = logging.getLogger(__name__)


class GrowthAPIError(RuntimeError):
    """Erro de negocio da Growth API (campo `error=True` ou HTTP nao tratado)."""


class GrowthAPIRateLimitError(GrowthAPIError):
    """HTTP 429 — usado para o backoff via tenacity."""


class GrowthAPIServerError(GrowthAPIError):
    """HTTP 5xx — retentavel via tenacity."""


class _Unauthorized(Exception):
    """Sinaliza HTTP 401 para o fluxo de relogin (interno)."""


def _strip_accents(value: str) -> str:
    norm = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in norm if not unicodedata.combining(ch))


# Sufixo " - XX" (sigla de UF) que a Growth API anexa ao nome da unidade
# (ex.: "AGUAS LINDAS - GO") e que NAO existe no performance parquet
# (ex.: "AGUAS LINDAS"). Removido para o join 1:1 por `unidade`.
_UF_SUFFIX_RE = re.compile(r"\s*-\s*[A-Z]{2}$")


def normalizar_unidade(value: object) -> str:
    """Normaliza o identificador `unidade` para join estavel.

    Maiuscula, sem acentos, sem espacos nas pontas, espacos internos colapsados
    e remocao do sufixo de UF (" - XX") que a Growth API anexa. Verificado no 1o
    fetch real: com esta normalizacao as 54 unidades do performance parquet casam
    100% com a `/historico-dash-view`. Compartilhada com o catchment e a
    consolidacao.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = _strip_accents(str(value)).upper().strip()
    text = " ".join(text.split())
    return _UF_SUFFIX_RE.sub("", text).strip()


def assert_sem_pii(df: pd.DataFrame) -> None:
    """Levanta `ValueError` se qualquer coluna PII proibida estiver presente.

    Comparacao case-insensitive contra `config.PII_COLUNAS_PROIBIDAS`. Chamada
    OBRIGATORIA antes de qualquer `to_parquet` na camada de Dimensionamento.
    """
    cols_lower = {str(c).strip().lower() for c in df.columns}
    proibidas = {c.lower() for c in config.PII_COLUNAS_PROIBIDAS}
    encontradas = sorted(cols_lower & proibidas)
    if encontradas:
        raise ValueError(
            "Colunas PII proibidas encontradas (LGPD §10.3): "
            f"{encontradas}. Nenhum dado PII pode ser persistido em disco."
        )


class GrowthAPIClient:
    """Cliente HTTP da Growth API com auth/throttle/backoff/cache.

    Credenciais via `.env` raiz (`GROWTH_API_USUARIO`/`GROWTH_API_SENHA`),
    carregadas por `load_dotenv()`. Nunca hardcodadas.
    """

    def __init__(
        self,
        usuario: str | None = None,
        senha: str | None = None,
        base_url: str | None = None,
        cache_dir: Path | None = None,
        session: requests.Session | None = None,
        load_env: bool = True,
    ) -> None:
        if load_env:
            load_dotenv()
        self._usuario = usuario or os.environ.get("GROWTH_API_USUARIO")
        self._senha = senha or os.environ.get("GROWTH_API_SENHA")
        self.base_url = (
            base_url
            or os.environ.get("GROWTH_API_BASE_URL")
            or config.GROWTH_API_BASE_URL
        ).rstrip("/")
        self.cache_dir = Path(cache_dir) if cache_dir is not None else config.CACHE_DIR
        self._session = session or requests.Session()
        self._token: str | None = None
        self._token_emitido_em: float | None = None
        # Janela deslizante de timestamps das ultimas reqs.
        self._req_timestamps: deque[float] = deque()

    # --- credenciais / login ------------------------------------------------
    def _require_credentials(self) -> tuple[str, str]:
        if not self._usuario or not self._senha:
            raise GrowthAPIError(
                "Credenciais ausentes: defina GROWTH_API_USUARIO e GROWTH_API_SENHA "
                "no .env raiz (gitignored)."
            )
        return self._usuario, self._senha

    def login(self) -> str:
        usuario, senha = self._require_credentials()
        url = f"{self.base_url}{config.ENDPOINT_LOGIN}"
        resp = self._session.post(url, json={"usuario": usuario, "senha": senha})
        payload = self._parse_response(resp)
        token = (payload or {}).get("token")
        if not token:
            raise GrowthAPIError("Login sem token na resposta da Growth API.")
        self._token = str(token)
        self._token_emitido_em = time.monotonic()
        logger.info("Growth API login OK (token renovado).")
        return self._token

    def _headers(self) -> dict[str, str]:
        if not self._token:
            self.login()
        return {"Authorization": f"Bearer {self._token}"}

    # --- parsing / erros ----------------------------------------------------
    @staticmethod
    def _parse_response(resp: requests.Response) -> Any:
        """Checa HTTP + envelope `{error, message, data}` e retorna `data`."""
        if resp.status_code == 401:
            raise _Unauthorized()
        if resp.status_code == 429:
            raise GrowthAPIRateLimitError("HTTP 429 — rate limit (10 req/5 min).")
        if resp.status_code in (400, 422):
            raise GrowthAPIError(
                f"HTTP {resp.status_code} — requisicao invalida: {resp.text[:300]}"
            )
        if resp.status_code >= 500:
            raise GrowthAPIServerError(f"HTTP {resp.status_code} — erro do servidor.")
        if resp.status_code != 200:
            raise GrowthAPIError(f"HTTP {resp.status_code}: {resp.text[:300]}")
        try:
            body = resp.json()
        except ValueError as exc:  # pragma: no cover - resposta nao-JSON inesperada
            raise GrowthAPIError("Resposta nao-JSON da Growth API.") from exc
        if isinstance(body, dict):
            if body.get("error"):
                raise GrowthAPIError(
                    f"Growth API error=True: {body.get('message', 'sem mensagem')}"
                )
            return body.get("data")
        return body

    # --- throttle -----------------------------------------------------------
    def _throttle(self) -> None:
        """Janela deslizante: no maximo `RATE_LIMIT_REQS` em `RATE_LIMIT_WINDOW_S`."""
        window = config.RATE_LIMIT_WINDOW_S
        limite = config.RATE_LIMIT_REQS
        agora = time.monotonic()
        while self._req_timestamps and (agora - self._req_timestamps[0]) >= window:
            self._req_timestamps.popleft()
        if len(self._req_timestamps) >= limite:
            espera = window - (agora - self._req_timestamps[0]) + 0.1
            if espera > 0:
                logger.info("Throttle: aguardando %.1fs para liberar a janela.", espera)
                time.sleep(espera)
            agora = time.monotonic()
            while self._req_timestamps and (agora - self._req_timestamps[0]) >= window:
                self._req_timestamps.popleft()
        self._req_timestamps.append(time.monotonic())

    # --- requisicao base ----------------------------------------------------
    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Wrapper unico: throttle + auth + relogin (401) + backoff (429/5xx)."""

        @retry(
            retry=retry_if_exception_type(
                (GrowthAPIRateLimitError, GrowthAPIServerError)
            ),
            wait=wait_exponential(
                multiplier=config.BACKOFF_MIN_S, min=config.BACKOFF_MIN_S
            ),
            stop=stop_after_attempt(5),
            reraise=True,
            before_sleep=lambda rs: logger.warning(
                "Backoff Growth API (tentativa %s): %s",
                rs.attempt_number,
                rs.outcome.exception() if rs.outcome else "?",
            ),
        )
        def _do() -> Any:
            self._throttle()
            url = f"{self.base_url}{path}"
            try:
                resp = self._session.request(
                    method, url, params=params, headers=self._headers()
                )
                return self._parse_response(resp)
            except _Unauthorized:
                # Token expirado/invalido (§5.4): relogin e retenta 1x.
                logger.info("HTTP 401 — refazendo login e retentando.")
                self.login()
                self._throttle()
                resp = self._session.request(
                    method, url, params=params, headers=self._headers()
                )
                return self._parse_response(resp)

        return _do()

    # --- cache ---------------------------------------------------------------
    def _cache_path(self, endpoint: str, data_inicio: str | None, data_fim: str | None) -> Path:
        slug = endpoint.strip("/").replace("/", "_")
        di = data_inicio or "none"
        dfim = data_fim or "none"
        return self.cache_dir / f"{slug}_{di}_{dfim}.json"

    def _read_cache(self, path: Path) -> list[dict] | None:
        if not path.is_file():
            return None
        try:
            with path.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except (ValueError, OSError):  # pragma: no cover - cache corrompido
            return None

    def _write_cache(self, path: Path, data: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)

    def _get_historico(
        self,
        endpoint: str,
        data_inicio: str | None,
        data_fim: str | None,
        force_refresh: bool,
    ) -> list[dict]:
        params: dict[str, Any] = {}
        if data_inicio:
            params["data_inicio"] = data_inicio
        if data_fim:
            params["data_fim"] = data_fim
        cache_path = self._cache_path(endpoint, data_inicio, data_fim)
        if not force_refresh:
            cached = self._read_cache(cache_path)
            if cached is not None:
                logger.info("Cache hit: %s", cache_path.name)
                return cached
        data = self._request("GET", endpoint, params=params)
        result: list[dict] = list(data) if data else []
        self._write_cache(cache_path, result)
        return result

    def get_historico_dash(
        self,
        data_inicio: str | None = None,
        data_fim: str | None = None,
        force_refresh: bool = False,
    ) -> list[dict]:
        return self._get_historico(
            config.ENDPOINT_HISTORICO, data_inicio, data_fim, force_refresh
        )

    def get_historico_dash_view(
        self,
        data_inicio: str | None = None,
        data_fim: str | None = None,
        force_refresh: bool = False,
    ) -> list[dict]:
        return self._get_historico(
            config.ENDPOINT_HISTORICO_VIEW, data_inicio, data_fim, force_refresh
        )


def to_dataframe(registros: Iterable[dict]) -> pd.DataFrame:
    """Constroi DataFrame a partir dos registros agregados da API."""
    return pd.DataFrame(list(registros))
