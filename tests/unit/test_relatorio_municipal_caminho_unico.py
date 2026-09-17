"""O Relatorio Municipal sai do MESMO preparo no motor (web) e no bot do Telegram.

Antes, `web/server/app.py` montava o relatorio a mao e o bot ia por
`service.gerar_pdf_municipio`: os dois chamavam o mesmo gerador, mas com insumos
diferentes -- o motor imprimia renda per capita sob o rotulo "Renda domiciliar" e a
pagina "Bairros Oficiais" vazia; o bot misturava municipios homonimos de outras UFs
(Rio Branco/AC + Rio Branco/MT: o mapa enquadrava os dois estados e os hexagonos
sumiam da Visao Geral) e deixava as academias independentes de fora.

Hermeticos: todos os leitores de dado sao monkeypatchados nas fronteiras.
"""

from __future__ import annotations

import pandas as pd
import pytest

import motor_expansao.dashboard.relatorio_municipal as relmun
from motor_expansao.api import service
from motor_expansao.api.settings import Settings


def _df_homonimos() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "hex_id": ["ac1", "ac2", "mt1"],
            "nome_municipio": ["Rio Branco", "Rio Branco", "Rio Branco"],
            "uf": ["AC", "AC", "MT"],
            "cod_municipio": ["1200401", "1200401", "5107206"],
        }
    )


@pytest.fixture
def capturado(monkeypatch: pytest.MonkeyPatch, tmp_path) -> dict:
    """Fronteiras do preparo trocadas por dublês que registram o que receberam."""
    cap: dict = {}

    monkeypatch.setattr(service, "_mercado_df", lambda s: _df_homonimos())
    monkeypatch.setattr(
        service, "resolver_municipio", lambda uf, m, s: ("Rio Branco", ["Rio Branco"])
    )
    monkeypatch.setattr(service, "_dominio_df", lambda s: None)

    def _uniao(settings):
        cap["uniao_dec046"] = True
        return pd.DataFrame({"rede": [pd.NA], "lat": [0.0], "lng": [0.0]}), None

    monkeypatch.setattr(service, "_competitors_ultra", _uniao)
    monkeypatch.setattr(relmun, "_carregar_bairros_por_hex", lambda uf, cod, d: {"ac1": "Centro"})

    def _geo(uf, cod, d):
        cap["bairros_geo_cod"] = cod
        return {"bairros": ["Centro"]}

    monkeypatch.setattr(relmun, "carregar_bairros_geo", _geo)
    monkeypatch.setattr(
        relmun, "carregar_renda_domiciliar_por_hex", lambda uf, cod, d: {"ac1": 5000.0}
    )
    monkeypatch.setattr(relmun, "carregar_poligono_municipio", lambda *a, **k: None)

    def _agregar(df, **k):
        cap["agregar"] = k
        return {"uf": k.get("uf"), "nome_municipio": k.get("nome_municipio"), "n_hex_total": 2}

    monkeypatch.setattr(relmun, "agregar_municipio", _agregar)

    def _render(df_muni, result, **k):
        cap["render_unidade"] = k.get("unidade")
        cap["render_poligono_kwarg"] = "poligono_municipio" in k
        return {"cobertura": b"PNG"}

    monkeypatch.setattr(relmun, "render_mapas_municipio", _render)

    def _payloads(result, mapas=None, **k):
        cap["payload_unidade"] = k.get("unidade")
        cap["payload_mapas"] = mapas

        class _P:
            pdf_bytes = b"%PDF-1.4"
            pdf_filename = "r.pdf"

        return _P()

    monkeypatch.setattr(relmun, "gerar_payloads_download_relatorio_municipal", _payloads)
    cap["settings"] = Settings(
        staging_dir=tmp_path, censo_geo_dir=tmp_path, ibge_dir=tmp_path, ultra_dir=tmp_path
    )
    return cap


def test_telegram_nao_mistura_municipio_homonimo_de_outra_uf(capturado: dict) -> None:
    """Rio Branco/AC nao pode levar junto os hexagonos de Rio Branco/MT."""
    service.gerar_pdf_municipio("AC", "Rio Branco", None, capturado["settings"], unidade="hexagono")
    df_muni = capturado["agregar"]["df_pre_filtrado"]
    assert set(df_muni["uf"]) == {"AC"}
    assert sorted(df_muni["hex_id"]) == ["ac1", "ac2"]
    assert capturado["bairros_geo_cod"] == "1200401"


def test_telegram_hexagono_leva_bairros_renda_e_independentes(capturado: dict) -> None:
    service.gerar_pdf_municipio("AC", "Rio Branco", None, capturado["settings"], unidade="hexagono")
    k = capturado["agregar"]
    assert k["bairros_geo"], "modo hexagono tem de receber os bairros (pagina Bairros Oficiais)"
    assert k["renda_domiciliar_por_hex"] == {"ac1": 5000.0}
    assert capturado.get("uniao_dec046") is True, "concorrentes tem de vir da uniao DEC-046"
    assert capturado["render_unidade"] == "hexagono"
    assert capturado["payload_unidade"] == "hexagono"
    assert capturado["payload_mapas"] == {"cobertura": b"PNG"}, "os mapas tem de chegar ao PDF"
    assert capturado["render_poligono_kwarg"], "BLK-RELMUN-05: divisa repassada ao render"


def test_montagem_unica_usa_a_base_de_quem_chama(capturado: dict) -> None:
    """O motor passa a propria base (enriquecido por UF) e ganha o mesmo preparo do bot."""
    df_uf = _df_homonimos().iloc[:2].assign(extra=1)
    pdf = service.montar_pdf_municipio(
        df_uf, uf="AC", nome_municipio="Rio Branco", settings=capturado["settings"],
        unidade="hexagono",
    )
    assert pdf.startswith(b"%PDF")
    k = capturado["agregar"]
    assert "extra" in k["df_pre_filtrado"].columns
    assert k["bairros_geo"] and k["renda_domiciliar_por_hex"]


def test_base_sem_codigo_resolve_o_municipio_pela_malha(capturado: dict, monkeypatch) -> None:
    """Na particao enriquecida o `cod_municipio` pode vir todo nulo (3.236 de 5.570 municipios
    na foto local de 11/06). Sem codigo, o preparo perdia renda, bairros e divisa EM SILENCIO."""
    from motor_expansao.dashboard import data as dash_data

    chamadas: list[tuple] = []

    def _resolver(base_dir, uf, nome):
        chamadas.append((uf, nome))
        return "1200401"

    monkeypatch.setattr(dash_data, "resolve_cod_municipio_from_geo_dir", _resolver)
    df_uf = _df_homonimos().iloc[:2].assign(cod_municipio=None)
    service.montar_pdf_municipio(
        df_uf, uf="AC", nome_municipio="Rio Branco", settings=capturado["settings"],
        unidade="hexagono",
    )
    assert chamadas == [("AC", "Rio Branco")]
    assert capturado["bairros_geo_cod"] == "1200401"
    assert capturado["agregar"]["renda_domiciliar_por_hex"] == {"ac1": 5000.0}
