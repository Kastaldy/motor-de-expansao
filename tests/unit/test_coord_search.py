from __future__ import annotations

import pandas as pd
import pytest

from motor_expansao.dashboard.data import lookup_hex_by_coord, parse_coordinate_input

# ── parse_coordinate_input ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text,expected",
    [
        ("-23.55,-46.63", (-23.55, -46.63)),
        ("-23.55, -46.63", (-23.55, -46.63)),
        ("-23.55 -46.63", (-23.55, -46.63)),
        ("-23,55;-46,63", (-23.55, -46.63)),
        ("-23,55; -46,63", (-23.55, -46.63)),
        ("-23,55 -46,63", (-23.55, -46.63)),
        ("-23,55,-46,63", (-23.55, -46.63)),
        ("  -15.77 , -47.93  ", (-15.77, -47.93)),
    ],
)
def test_parse_formatos_validos(text, expected):
    result = parse_coordinate_input(text)
    assert result is not None
    assert result == pytest.approx(expected, abs=1e-5)


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "ABC",
        "nao_e_numero",
        "-23.55",          # apenas uma coordenada
        "20.0,-50.0",      # lat fora do Brasil (norte demais)
        "-23.55,-5.0",     # lng fora do Brasil (leste demais)
        "-40.0,-46.63",    # lat fora do Brasil (sul demais)
        "-23.55,-80.0",    # lng fora do Brasil (oeste demais)
    ],
)
def test_parse_entrada_invalida_retorna_none(text):
    assert parse_coordinate_input(text) is None


def test_parse_none_retorna_none():
    assert parse_coordinate_input(None) is None  # type: ignore[arg-type]


def test_parse_limites_brasil():
    # ponto extremo norte (RR)
    assert parse_coordinate_input("5.0,-60.0") is not None
    # ponto extremo sul (RS)
    assert parse_coordinate_input("-33.0,-53.0") is not None
    # fora do norte
    assert parse_coordinate_input("6.0,-60.0") is None
    # fora do sul
    assert parse_coordinate_input("-34.0,-53.0") is None


# ── lookup_hex_by_coord ───────────────────────────────────────────────────────


def _base_df(hex_id: str, lat: float = -23.55, lng: float = -46.63) -> pd.DataFrame:
    return pd.DataFrame([{
        "hex_id": hex_id,
        "lat": lat,
        "lng": lng,
        "uf": "SP",
        "cidade": "Sao Paulo",
        "score_priorizacao": 80.0,
        "rank_brasil": 100,
    }])


def test_lookup_encontra_hex_quando_coordenada_pertence_ao_hex():
    import h3
    lat, lng = -23.55, -46.63
    hex_id = h3.latlng_to_cell(lat, lng, 7)
    df = _base_df(hex_id, lat, lng)
    result = lookup_hex_by_coord(lat, lng, df)
    assert result is not None
    assert result["hex_id"] == hex_id
    assert result["_not_found"] is False
    assert result["_searched_lat"] == pytest.approx(lat)
    assert result["_searched_lng"] == pytest.approx(lng)


def test_lookup_retorna_not_found_quando_hex_nao_esta_na_base():
    lat, lng = -15.77, -47.93  # Brasilia, diferente de SP
    df = _base_df("hex_sp_qualquer", -23.55, -46.63)
    result = lookup_hex_by_coord(lat, lng, df)
    assert result is not None
    assert result["_not_found"] is True
    assert "hex_id" in result


def test_lookup_nao_altera_score_priorizacao():
    import h3
    lat, lng = -23.55, -46.63
    hex_id = h3.latlng_to_cell(lat, lng, 7)
    df = _base_df(hex_id, lat, lng)
    result = lookup_hex_by_coord(lat, lng, df)
    assert result is not None
    assert result.get("score_priorizacao") == 80.0


# ── resolve_endereco_http (BLK-UI-08 / DEC-010) — SEMPRE com urllib mockado ────


class _FakeResp:
    """Stub de resposta urllib: expõe read() (JSON do Nominatim) + context manager."""

    def __init__(self, body: bytes = b""):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, _n=None):
        return self._body


def _nominatim_body(lat: float, lng: float) -> bytes:
    """Corpo JSON minimo no formato jsonv2 do Nominatim (lat/lon como string)."""
    return f'[{{"lat": "{lat}", "lon": "{lng}"}}]'.encode()


def test_resolve_endereco_http_resolve_coordenada_do_redirect(monkeypatch):
    """Sucesso: o JSON do Nominatim (mock) traz lat/lon -> retorna (lat, lng) no Brasil."""
    from motor_expansao.api import maps_geocoder

    monkeypatch.setattr(
        maps_geocoder.urllib.request,
        "urlopen",
        lambda *a, **k: _FakeResp(_nominatim_body(-23.5613, -46.6565)),
    )
    out = maps_geocoder.resolve_endereco_http("Av. Paulista 1000, Sao Paulo", timeout=1.0)
    assert out is not None
    assert out == pytest.approx((-23.5613, -46.6565), abs=1e-4)


def test_resolve_endereco_http_falha_de_rede_retorna_none(monkeypatch):
    """Exceção de rede/timeout -> None (sem propagar exceção); CI nunca bate na rede."""
    from motor_expansao.api import maps_geocoder

    def _boom(*a, **k):
        raise TimeoutError("sem rede")

    monkeypatch.setattr(maps_geocoder.urllib.request, "urlopen", _boom)
    assert maps_geocoder.resolve_endereco_http("Rua Inexistente 999", timeout=0.1) is None


def test_resolve_endereco_http_sem_resultado_retorna_none(monkeypatch):
    """JSON vazio do Nominatim (endereco sem match) -> None."""
    from motor_expansao.api import maps_geocoder

    monkeypatch.setattr(
        maps_geocoder.urllib.request,
        "urlopen",
        lambda *a, **k: _FakeResp(b"[]"),
    )
    assert maps_geocoder.resolve_endereco_http("zzzzz nao existe", timeout=1.0) is None


def test_resolve_endereco_http_fora_do_brasil_retorna_none(monkeypatch):
    """Coordenada resolvida fora do bounding box do Brasil -> None."""
    from motor_expansao.api import maps_geocoder

    monkeypatch.setattr(
        maps_geocoder.urllib.request,
        "urlopen",
        lambda *a, **k: _FakeResp(_nominatim_body(48.8566, 2.3522)),  # Paris
    )
    assert maps_geocoder.resolve_endereco_http("Tour Eiffel", timeout=1.0) is None


def test_resolve_endereco_http_vazio_retorna_none():
    from motor_expansao.api import maps_geocoder

    assert maps_geocoder.resolve_endereco_http("   ") is None


def test_resolve_endereco_http_usa_cache_sem_rede(tmp_path, monkeypatch):
    """Cache local gitignored: 1º hit grava; 2º hit lê do disco sem chamar urlopen."""
    from motor_expansao.api import maps_geocoder

    calls = {"n": 0}

    def _urlopen(*a, **k):
        calls["n"] += 1
        return _FakeResp(_nominatim_body(-23.5613, -46.6565))

    monkeypatch.setattr(maps_geocoder.urllib.request, "urlopen", _urlopen)

    first = maps_geocoder.resolve_endereco_http("Av. Paulista 1000", cache_dir=tmp_path)
    assert first is not None
    assert calls["n"] == 1

    # Segunda chamada com a MESMA query lê do cache, sem nova requisição.
    second = maps_geocoder.resolve_endereco_http("Av. Paulista 1000", cache_dir=tmp_path)
    assert second == first
    assert calls["n"] == 1


# ── extract_any_coord (BLK-UI-09: link do Maps, regex pura, sem rede) ──────────


def test_extract_any_coord_url_longa_pino_brasil():
    """URL longa com !3d/!4d (pino do place no Brasil) -> (lat, lng) do pino."""
    from motor_expansao.api.maps_geocoder import extract_any_coord

    url = (
        "https://www.google.com/maps/place/Av.+Paulista/"
        "@-23.5613,-46.6565,17z/data=...!3d-23.5613!4d-46.6565"
    )
    lat, lng = extract_any_coord(url)
    assert (lat, lng) == pytest.approx((-23.5613, -46.6565), abs=1e-4)


def test_extract_any_coord_url_camera_at_brasil():
    """URL com @lat,lng (sem !3d/!4d) -> centro da câmera no Brasil."""
    from motor_expansao.api.maps_geocoder import extract_any_coord

    url = "https://www.google.com/maps/@-15.7797,-47.9297,15z"
    lat, lng = extract_any_coord(url)
    assert (lat, lng) == pytest.approx((-15.7797, -47.9297), abs=1e-4)


def test_extract_any_coord_fora_do_brasil_rejeitado_pelo_bbox():
    """URL fora do Brasil (Paris) -> extrai par bruto, mas _validate_brazil_bbox -> None."""
    from motor_expansao.api.maps_geocoder import extract_any_coord
    from motor_expansao.dashboard.data import _validate_brazil_bbox

    url = "https://www.google.com/maps/place/Tour+Eiffel/data=...!3d48.8566!4d2.3522"
    lat, lng = extract_any_coord(url)
    assert lat is not None and lng is not None
    assert _validate_brazil_bbox(float(lat), float(lng)) is None


def test_extract_any_coord_url_sem_coordenada():
    """URL longa sem coordenada extraível -> (None, None)."""
    from motor_expansao.api.maps_geocoder import extract_any_coord

    url = "https://www.google.com/maps/search/?api=1&query=academia"
    assert extract_any_coord(url) == (None, None)


def test_extract_any_coord_link_curto_nao_resolve_offline():
    """Link curto (maps.app.goo.gl) não traz coordenada na string -> (None, None)."""
    from motor_expansao.api.maps_geocoder import extract_any_coord

    assert extract_any_coord("https://maps.app.goo.gl/abc123") == (None, None)


# ── helpers de roteamento da cascata (BLK-UI-09, funções de módulo puras) ──────


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("https://www.google.com/maps/@-23.55,-46.63,15z", True),
        ("http://maps.app.goo.gl/abc", True),
        ("Av. Paulista 1000, Sao Paulo", False),
        ("-23.55,-46.63", False),
        ("", False),
    ],
)
def test_parece_link(raw, expected):
    from motor_expansao.dashboard.pages import _parece_link

    assert _parece_link(raw) is expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("https://maps.app.goo.gl/abc123", True),
        ("https://goo.gl/maps/xyz", True),
        ("https://www.google.com/maps/place/x/@-23.5,-46.6,17z", False),
        ("Av. Paulista 1000", False),
    ],
)
def test_e_link_curto_maps(raw, expected):
    from motor_expansao.dashboard.pages import _e_link_curto_maps

    assert _e_link_curto_maps(raw) is expected


# ── resolve_short_link (BLK-UI-09 / DEC-010 emenda Opção B) — urllib MOCKADO ───


class _FakeRedirectResp:
    """Stub de resposta urllib que expõe geturl() (URL final após redirects)."""

    def __init__(self, final_url: str):
        self._final_url = final_url

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def geturl(self):
        return self._final_url


def test_resolve_short_link_segue_redirect_para_url_longa(monkeypatch):
    """Sucesso: geturl() (mock) devolve URL longa com !3d/!4d -> string retornada."""
    from motor_expansao.api import maps_geocoder

    longa = "https://www.google.com/maps/place/x/@-23.5613,-46.6565,17z/data=...!3d-23.5613!4d-46.6565"
    monkeypatch.setattr(
        maps_geocoder.urllib.request,
        "urlopen",
        lambda *a, **k: _FakeRedirectResp(longa),
    )
    out = maps_geocoder.resolve_short_link("https://maps.app.goo.gl/abc123", timeout=1.0)
    assert out == longa
    # E a URL longa resolvida deve render coordenada do Brasil ao passar por extract_any_coord.
    lat, lng = maps_geocoder.extract_any_coord(out)
    assert (lat, lng) == pytest.approx((-23.5613, -46.6565), abs=1e-4)


def test_resolve_short_link_falha_de_rede_retorna_none(monkeypatch):
    """Exceção de rede/timeout -> None (sem propagar exceção); CI nunca bate na rede."""
    from motor_expansao.api import maps_geocoder

    def _boom(*a, **k):
        raise TimeoutError("sem rede")

    monkeypatch.setattr(maps_geocoder.urllib.request, "urlopen", _boom)
    assert maps_geocoder.resolve_short_link("https://maps.app.goo.gl/abc", timeout=0.1) is None


def test_resolve_short_link_vazio_retorna_none():
    from motor_expansao.api import maps_geocoder

    assert maps_geocoder.resolve_short_link("   ") is None
