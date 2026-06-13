"""Testes do cliente Growth API (mocks de `requests`; sem rede; CI-safe)."""

from __future__ import annotations

import json
from collections import deque

import pandas as pd
import pytest

from motor_expansao.dimensionamento import config
from motor_expansao.dimensionamento.growth_api_client import (
    GrowthAPIClient,
    GrowthAPIError,
    GrowthAPIRateLimitError,
    GrowthAPIServerError,
    assert_sem_pii,
    normalizar_unidade,
    to_dataframe,
)


class _FakeResponse:
    def __init__(self, status_code: int, payload: object | None = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self) -> object:
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class _FakeSession:
    """Sessao mockada: roteia por (method, url) via uma fila de respostas."""

    def __init__(self) -> None:
        self.post_responses: deque[_FakeResponse] = deque()
        self.request_responses: deque[_FakeResponse] = deque()
        self.calls: list[tuple[str, str]] = []

    def post(self, url, json=None, **kwargs):  # noqa: A002 - assina requests
        self.calls.append(("POST", url))
        return self.post_responses.popleft()

    def request(self, method, url, params=None, headers=None, **kwargs):
        self.calls.append((method, url))
        return self.request_responses.popleft()


def _client(tmp_path, session) -> GrowthAPIClient:
    return GrowthAPIClient(
        usuario="u",
        senha="p",
        base_url="https://api.test/growth",
        cache_dir=tmp_path / "cache",
        session=session,
        load_env=False,
    )


# --- normalizar_unidade / assert_sem_pii ------------------------------------
def test_normalizar_unidade_strip_accents_upper():
    assert normalizar_unidade("  São  Paulo ") == "SAO PAULO"
    assert normalizar_unidade(None) == ""
    assert normalizar_unidade(float("nan")) == ""


def test_normalizar_unidade_remove_sufixo_uf():
    # A Growth API anexa " - XX" (sigla UF); o performance parquet nao.
    assert normalizar_unidade("Aguas Lindas - GO") == "AGUAS LINDAS"
    assert normalizar_unidade("VILA MARIANA - SP") == "VILA MARIANA"
    # nao deve cortar palavra real de 2 letras sem o hifen-separador
    assert normalizar_unidade("SE") == "SE"


def test_assert_sem_pii_ok():
    df = pd.DataFrame({"unidade": ["X"], "faturamento": [1.0]})
    assert_sem_pii(df)  # nao levanta


def test_assert_sem_pii_detecta_coluna_proibida():
    df = pd.DataFrame({"unidade": ["X"], "CPF": ["000"]})
    with pytest.raises(ValueError, match="PII"):
        assert_sem_pii(df)


def test_assert_sem_pii_case_insensitive():
    df = pd.DataFrame({"Email": ["a@b"]})
    with pytest.raises(ValueError):
        assert_sem_pii(df)


# --- login ------------------------------------------------------------------
def test_login_guarda_token(tmp_path):
    sess = _FakeSession()
    sess.post_responses.append(
        _FakeResponse(200, {"error": False, "message": "ok", "data": {"token": "abc"}})
    )
    cli = _client(tmp_path, sess)
    token = cli.login()
    assert token == "abc"
    assert cli._token == "abc"


def test_login_sem_token_levanta(tmp_path):
    sess = _FakeSession()
    sess.post_responses.append(_FakeResponse(200, {"error": False, "data": {}}))
    cli = _client(tmp_path, sess)
    with pytest.raises(GrowthAPIError):
        cli.login()


def test_credenciais_ausentes_levanta(tmp_path, monkeypatch):
    monkeypatch.delenv("GROWTH_API_USUARIO", raising=False)
    monkeypatch.delenv("GROWTH_API_SENHA", raising=False)
    cli = GrowthAPIClient(
        usuario=None, senha=None, cache_dir=tmp_path, session=_FakeSession(), load_env=False
    )
    with pytest.raises(GrowthAPIError, match="Credenciais"):
        cli.login()


# --- error envelope ---------------------------------------------------------
def test_envelope_error_true_levanta(tmp_path):
    sess = _FakeSession()
    sess.post_responses.append(
        _FakeResponse(200, {"error": False, "data": {"token": "t"}})
    )
    sess.request_responses.append(
        _FakeResponse(200, {"error": True, "message": "falhou", "data": None})
    )
    cli = _client(tmp_path, sess)
    cli.login()
    with pytest.raises(GrowthAPIError, match="falhou"):
        cli.get_historico_dash_view("2022-04-01", "2022-04-30")


def test_http_422_levanta(tmp_path):
    sess = _FakeSession()
    sess.post_responses.append(_FakeResponse(200, {"data": {"token": "t"}}))
    sess.request_responses.append(_FakeResponse(422, text="data invalida"))
    cli = _client(tmp_path, sess)
    cli.login()
    with pytest.raises(GrowthAPIError, match="422"):
        cli.get_historico_dash_view("bad", "bad")


# --- 401 relogin ------------------------------------------------------------
def test_401_refaz_login_e_retenta(tmp_path):
    sess = _FakeSession()
    # login inicial
    sess.post_responses.append(_FakeResponse(200, {"data": {"token": "t1"}}))
    # 1a request -> 401
    sess.request_responses.append(_FakeResponse(401, text="expirou"))
    # relogin
    sess.post_responses.append(_FakeResponse(200, {"data": {"token": "t2"}}))
    # retry -> 200 com dados
    sess.request_responses.append(
        _FakeResponse(200, {"error": False, "data": [{"unidade": "X", "data": "2022-04-01"}]})
    )
    cli = _client(tmp_path, sess)
    cli.login()
    out = cli.get_historico_dash_view("2022-04-01", "2022-04-30")
    assert out == [{"unidade": "X", "data": "2022-04-01"}]
    assert cli._token == "t2"
    # dois logins (inicial + relogin)
    assert sum(1 for m, _ in sess.calls if m == "POST") == 2


# --- 429 backoff ------------------------------------------------------------
def test_429_backoff_e_retenta(tmp_path, monkeypatch):
    sleeps: list[float] = []
    # mock time.sleep tanto no throttle quanto no wait do tenacity
    monkeypatch.setattr(
        "motor_expansao.dimensionamento.growth_api_client.time.sleep",
        lambda s: sleeps.append(s),
    )
    monkeypatch.setattr("tenacity.nap.time.sleep", lambda s: sleeps.append(s))

    sess = _FakeSession()
    sess.post_responses.append(_FakeResponse(200, {"data": {"token": "t"}}))
    sess.request_responses.append(_FakeResponse(429, text="rate"))
    sess.request_responses.append(
        _FakeResponse(200, {"error": False, "data": [{"unidade": "X"}]})
    )
    cli = _client(tmp_path, sess)
    cli.login()
    out = cli.get_historico_dash("2022-04-01", "2022-04-30")
    assert out == [{"unidade": "X"}]
    # houve ao menos 1 espera >= BACKOFF_MIN_S
    assert any(s >= config.BACKOFF_MIN_S for s in sleeps)


def test_429_persistente_levanta(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "motor_expansao.dimensionamento.growth_api_client.time.sleep", lambda s: None
    )
    monkeypatch.setattr("tenacity.nap.time.sleep", lambda s: None)
    sess = _FakeSession()
    sess.post_responses.append(_FakeResponse(200, {"data": {"token": "t"}}))
    for _ in range(5):
        sess.request_responses.append(_FakeResponse(429, text="rate"))
    cli = _client(tmp_path, sess)
    cli.login()
    with pytest.raises(GrowthAPIRateLimitError):
        cli.get_historico_dash("2022-04-01", "2022-04-30")


# --- throttle (janela deslizante) -------------------------------------------
def test_throttle_dorme_quando_estoura_janela(tmp_path, monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr(
        "motor_expansao.dimensionamento.growth_api_client.time.sleep",
        lambda s: sleeps.append(s),
    )
    # relogio controlado
    clock = {"t": 1000.0}
    monkeypatch.setattr(
        "motor_expansao.dimensionamento.growth_api_client.time.monotonic",
        lambda: clock["t"],
    )
    sess = _FakeSession()
    sess.post_responses.append(_FakeResponse(200, {"data": {"token": "t"}}))
    cli = _client(tmp_path, sess)
    cli.login()
    # encher a janela com RATE_LIMIT_REQS timestamps "agora"
    cli._req_timestamps = deque([1000.0] * config.RATE_LIMIT_REQS)
    cli._throttle()
    # deve ter dormido ~ a janela inteira
    assert sleeps and sleeps[0] >= config.RATE_LIMIT_WINDOW_S - 1


# --- cache idempotente ------------------------------------------------------
def test_cache_hit_evita_rede(tmp_path):
    sess = _FakeSession()
    sess.post_responses.append(_FakeResponse(200, {"data": {"token": "t"}}))
    sess.request_responses.append(
        _FakeResponse(200, {"error": False, "data": [{"unidade": "X"}]})
    )
    cli = _client(tmp_path, sess)
    cli.login()
    out1 = cli.get_historico_dash_view("2022-04-01", "2022-04-30")
    # 2a chamada: nao ha mais resposta na fila; se chamar a rede, KeyError/IndexError
    out2 = cli.get_historico_dash_view("2022-04-01", "2022-04-30")
    assert out1 == out2 == [{"unidade": "X"}]
    # arquivo de cache existe
    cache_files = list((tmp_path / "cache").glob("*.json"))
    assert len(cache_files) == 1
    assert json.loads(cache_files[0].read_text(encoding="utf-8")) == [{"unidade": "X"}]


def test_force_refresh_ignora_cache(tmp_path):
    sess = _FakeSession()
    sess.post_responses.append(_FakeResponse(200, {"data": {"token": "t"}}))
    sess.request_responses.append(
        _FakeResponse(200, {"error": False, "data": [{"unidade": "A"}]})
    )
    sess.request_responses.append(
        _FakeResponse(200, {"error": False, "data": [{"unidade": "B"}]})
    )
    cli = _client(tmp_path, sess)
    cli.login()
    out1 = cli.get_historico_dash_view("2022-04-01", "2022-04-30")
    out2 = cli.get_historico_dash_view("2022-04-01", "2022-04-30", force_refresh=True)
    assert out1 == [{"unidade": "A"}]
    assert out2 == [{"unidade": "B"}]


def test_to_dataframe():
    df = to_dataframe([{"unidade": "X", "faturamento": 1}])
    assert list(df.columns) == ["unidade", "faturamento"]
    assert len(df) == 1


def test_server_error_eh_retentavel(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "motor_expansao.dimensionamento.growth_api_client.time.sleep", lambda s: None
    )
    monkeypatch.setattr("tenacity.nap.time.sleep", lambda s: None)
    sess = _FakeSession()
    sess.post_responses.append(_FakeResponse(200, {"data": {"token": "t"}}))
    sess.request_responses.append(_FakeResponse(503, text="down"))
    sess.request_responses.append(
        _FakeResponse(200, {"error": False, "data": [{"unidade": "X"}]})
    )
    cli = _client(tmp_path, sess)
    cli.login()
    out = cli.get_historico_dash("2022-04-01", "2022-04-30")
    assert out == [{"unidade": "X"}]


def test_server_error_persistente_levanta(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "motor_expansao.dimensionamento.growth_api_client.time.sleep", lambda s: None
    )
    monkeypatch.setattr("tenacity.nap.time.sleep", lambda s: None)
    sess = _FakeSession()
    sess.post_responses.append(_FakeResponse(200, {"data": {"token": "t"}}))
    for _ in range(5):
        sess.request_responses.append(_FakeResponse(500, text="down"))
    cli = _client(tmp_path, sess)
    cli.login()
    with pytest.raises(GrowthAPIServerError):
        cli.get_historico_dash("2022-04-01", "2022-04-30")
