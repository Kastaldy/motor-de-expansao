"""Reancoragem BLK-WEB-19 (DEC-022): motor do Relatorio Municipal sem Streamlit.

Os fluxos de UI (`render_relatorio_municipal_download_topo`, `render_relatorio_municipal_expander`
e `_gerar_payload_relatorio_municipal` em `pages.py`) eram cobertos SOMENTE por
`tests/integration/test_streamlit_app.py`, que sera deletado no corte do Streamlit. Aqueles
testes mockavam `agregar_municipio`/`render_mapas_municipio`/`gerar_payloads_...`; o que eles
provavam de verdade eram INVARIANTES do motor compartilhado, reancoradas aqui contra as funcoes
puras: o gate `n_hex_total == 0` (municipio sem hex avisa e pula, sem excecao), a degradacao
silenciosa dos kwargs `dominio_df`/`bairros_por_hex` quando os loaders nao entregam nada
(PR #171), a cadeia completa agregar -> mapas -> payload com as MESMAS chamadas da UI, o lote
que nao aborta nos municipios vazios e o backfill de `uf` quando o seletor tem varias UFs.

NAO duplica `tests/unit/test_relatorio_municipal.py` (agregacao D1-D7, PDF, pins, basemap):
aqui entram apenas os cenarios que so existiam atraves da UI. Nenhum teste bate na rede.
"""

from __future__ import annotations

import math
import re

import h3
import pandas as pd
import pytest

from motor_expansao.dashboard import relatorio_municipal as rm
from motor_expansao.dashboard.relatorio_municipal import (
    _municipio_mask,
    agregar_municipio,
    gerar_payloads_download_relatorio_municipal,
    render_mapas_municipio,
)
from motor_expansao.perfil import PERFIL_BR_EMBARCADO, carregar_perfil


def _hex(lat: float, lng: float) -> str:
    return h3.latlng_to_cell(lat, lng, 7)


def _row(
    lat: float,
    lng: float,
    municipio: str,
    uf: str,
    *,
    oferta: float,
    consumo: float,
) -> dict:
    return {
        "hex_id": _hex(lat, lng),
        "lat": lat,
        "lng": lng,
        "nome_municipio": municipio,
        "cidade": municipio,
        "uf": uf,
        "sam_fitness_potencial": 4000.0,
        "oferta_efetiva_disponivel": oferta,
        "score_setor_2022_calibrado": 70.0,
        "score_oportunidade_residual": 55.0,
        "pop_total_setor_2022": 1500.0,
        "pop_total": 2000.0,
        "renda_per_capita": 3000.0,
        "penetracao_fitness_mercado_estimada": 12.5,
        "oferta_consumida_mercado_estimada": consumo,
    }


def _df_nacional() -> pd.DataFrame:
    """Base NACIONAL (como o `df` que a UI recebe): SAO PAULO com 4 hexes (2 destacados,
    oferta >= 2000) + MANAUS com 1 hex modesto. E o recorte multi-municipio que os fluxos
    de topo/lote fatiam por `_municipio_mask` antes de agregar."""
    sp = [
        _row(-23.55, -46.63, "SAO PAULO", "SP", oferta=4451.0, consumo=1000.0),
        _row(-23.56, -46.64, "SAO PAULO", "SP", oferta=4451.0, consumo=1000.0),
        _row(-23.54, -46.62, "SAO PAULO", "SP", oferta=500.0, consumo=200.0),
        _row(-23.57, -46.65, "SAO PAULO", "SP", oferta=500.0, consumo=200.0),
    ]
    am = [_row(-3.10, -60.02, "MANAUS", "AM", oferta=2600.0, consumo=300.0)]
    return pd.DataFrame(sp + am)


# ---------------------------------------------------------------------------
# Gate da UI: n_hex_total == 0 -> aviso e pulo, nunca excecao
# ---------------------------------------------------------------------------


def test_agregar_municipio_ausente_devolve_zero_hex_sem_excecao():
    """O topo/lote da UI decide avisar ("Nenhum hexágono encontrado") e NAO gerar PDF
    olhando so para `n_hex_total` — o contrato e que municipio fora do recorte degrade
    para o dicionario zerado, sem levantar."""
    res = agregar_municipio(_df_nacional(), nome_municipio="CIDADE INEXISTENTE", uf="SP")

    assert res["n_hex_total"] == 0
    assert res["n_hex_amarelos"] == 0
    assert res["soma_oferta_amarelos"] == 0.0
    assert res["espaco_para_academias"] == 0
    assert res["mercado_disponivel_pessoas"] == 0.0
    assert res["zonas"] == [] and res["zonas_geo"] == []
    assert res["n_ultra"] == 0 and res["n_concorrentes"] == 0
    assert math.isnan(res["penetracao_fitness_pct"])


def test_agregar_municipio_df_pre_filtrado_vazio_equivale_a_ausente():
    """A UI sempre pre-filtra (`df_pre_filtrado=df_muni`, Fix 2 BLK-PERF-01a); quando a
    mascara nao acha nada o frame chega VAZIO e o gate precisa continuar funcionando por
    esse caminho tambem (e o caso real do municipio 'B' no lote)."""
    df = _df_nacional()
    vazio = df.loc[_municipio_mask(df, "CIDADE INEXISTENTE")].copy()
    assert vazio.empty

    res = agregar_municipio(df, nome_municipio="CIDADE INEXISTENTE", uf=None, df_pre_filtrado=vazio)

    assert res["n_hex_total"] == 0
    assert res["zonas_geo"] == [] and res["bairros_por_zona"] == []


# ---------------------------------------------------------------------------
# PR #171: degradacao silenciosa dos kwargs quando os loaders nao entregam nada
# ---------------------------------------------------------------------------


def test_agregar_municipio_dominio_vazio_ou_malformado_degrada_silencioso():
    """A UI repassa o `dominio_df` que `load_plano_dominio` devolver — inclusive DataFrame
    VAZIO (parquet ausente) ou sem as colunas de cluster. Qualquer forma degenerada tem de
    degradar para zonas vazias (Paginas 5-6 em modo simplificado), nunca excecao."""
    df = _df_nacional()

    for dominio in (
        pd.DataFrame(),  # loader sem parquet
        pd.DataFrame([{"lat": -23.55, "lng": -46.63}]),  # sem cluster_id/nome_municipio
        pd.DataFrame(  # dominio de OUTRO municipio
            [{"nome_municipio": "MANAUS", "cluster_id": "c9", "residual_total_cluster": 10.0}]
        ),
    ):
        res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP", dominio_df=dominio)
        assert res["zonas"] == []
        assert res["n_zonas"] == 0
        # As metricas centrais nao sao contaminadas pela degradacao do dominio.
        assert res["n_hex_total"] == 4
        assert res["n_hex_amarelos"] == 2


def test_agregar_municipio_bairros_dict_vazio_equivale_a_none():
    """Offline, `_resolve_bairros_por_hex_municipio` devolve `{}` (nao `None`) — e o valor
    que a UI passa em `bairros_por_hex`. O contrato do PR #171 e que `{}` produza EXATAMENTE
    o comportamento do default: zonas geometricas presentes, porem sem nenhum bairro."""
    df = _df_nacional()
    df_sp = df.loc[_municipio_mask(df, "SAO PAULO")].copy()

    res_default = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP")
    res_vazio = agregar_municipio(
        df, nome_municipio="SAO PAULO", uf="SP", bairros_por_hex={}, df_pre_filtrado=df_sp
    )

    assert res_vazio["bairros_por_zona"] == res_default["bairros_por_zona"]
    assert res_vazio["n_bairros_total"] == 0
    assert all(z["bairros"] == [] for z in res_vazio["bairros_por_zona"])


def test_agregar_municipio_chamada_completa_da_ui_igual_a_minima():
    """A UI SEMPRE chama `agregar_municipio` com o kwargs completo (dominio/competidores/
    ultra/bairros/df_pre_filtrado), mesmo quando todos os loaders degradaram para None/{}.
    O resultado tem de ser identico ao da chamada minima — senao o PDF gerado pela UI
    divergiria do PDF dos testes de motor."""
    df = _df_nacional()
    df_sp = df.loc[_municipio_mask(df, "SAO PAULO")].copy()

    res_min = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP")
    res_ui = agregar_municipio(
        df,
        nome_municipio="SAO PAULO",
        uf="SP",
        dominio_df=None,
        competitors_df=None,
        ultra_df=None,
        bairros_por_hex={},
        df_pre_filtrado=df_sp,
    )

    assert set(res_ui) == set(res_min)
    for key in res_min:
        a, b = res_ui[key], res_min[key]
        if isinstance(a, float) and isinstance(b, float) and math.isnan(b):
            assert math.isnan(a), key
        else:
            assert a == b, key


# ---------------------------------------------------------------------------
# Cadeia completa da UI (sem mocks, sem streamlit): agregar -> mapas -> payload
# ---------------------------------------------------------------------------


def _payload_como_a_ui(df: pd.DataFrame, nome: str, uf: str | None):
    """Reproduz `pages._gerar_payload_relatorio_municipal` com as funcoes REAIS: e a unidade
    que o lote e o topo compartilham, ate hoje provada apenas com os tres alvos mockados."""
    df_muni = df.loc[_municipio_mask(df, nome)].copy()
    res = agregar_municipio(
        df,
        nome_municipio=nome,
        uf=uf,
        dominio_df=None,
        competitors_df=None,
        ultra_df=None,
        bairros_por_hex={},
        df_pre_filtrado=df_muni,
    )
    if res["n_hex_total"] == 0:
        return None
    mapas = render_mapas_municipio(df_muni, res, basemap=False)
    return gerar_payloads_download_relatorio_municipal(res, mapas)


def test_cadeia_ui_gera_pdf_valido_e_filename_canonico():
    """O fluxo de 1 municipio da UI, com as funcoes reais de ponta a ponta: o payload sai
    com PDF integro (9 paginas) e o filename canonico uf+municipio que o download usa."""
    payload = _payload_como_a_ui(_df_nacional(), "SAO PAULO", "SP")

    assert payload is not None
    assert payload.pdf_bytes.startswith(b"%PDF-1.4")
    assert b"/Count 11" in payload.pdf_bytes
    assert payload.pdf_filename == "relatorio_municipal_sp_sao_paulo.pdf"


def test_cadeia_ui_uf_none_backfill_pelo_frame():
    """No lote com VARIAS UFs selecionadas a UI passa `uf=None`; o agregador tem de
    recuperar a UF do proprio frame do municipio para o cabecalho e o filename nao sairem
    sem estado (invariante implicita nos testes de lote da UI)."""
    df = _df_nacional()
    res = agregar_municipio(df, nome_municipio="MANAUS", uf=None)
    assert res["uf"] == "AM"

    payload = _payload_como_a_ui(df, "MANAUS", None)
    assert payload is not None
    assert payload.pdf_filename == "relatorio_municipal_am_manaus.pdf"


def test_cadeia_ui_lote_municipio_sem_hex_nao_aborta_os_demais():
    """Reancora `test_render_relatorio_municipal_topo_lote_municipio_sem_hex_nao_aborta`:
    no lote A/B/C, o municipio sem hexagono devolve None (a UI so avisa) e os OUTROS seguem
    gerando payloads com filenames distintos — a falha de um nao derruba o loop."""
    df = _df_nacional()
    nomes = ["SAO PAULO", "CIDADE INEXISTENTE", "MANAUS"]

    payloads = {nome: _payload_como_a_ui(df, nome, None) for nome in nomes}

    assert payloads["CIDADE INEXISTENTE"] is None
    gerados = [p for p in payloads.values() if p is not None]
    assert len(gerados) == 2
    assert all(p.pdf_bytes.startswith(b"%PDF") for p in gerados)
    assert len({p.pdf_filename for p in gerados}) == 2


# ---------------------------------------------------------------------------
# Argentina (BLK-INTL-10): o municipal sai com a base AR e sem cara de Brasil
# ---------------------------------------------------------------------------

# Colunas que o exportador AR (`exportar_piloto_ar.py`) NAO emite. Medido na base real
# (`motor_data_ar`, 2026-09-16): sem elas a rota /api/relatorio/municipal devolvia 500
# "'numpy.float64' object has no attribute 'dropna'" para qualquer departamento.
_COLUNAS_AUSENTES_NA_AR = (
    "penetracao_fitness_mercado_estimada",
    "pop_total_setor_2022",
    "fonte_populacao_corte",
)


@pytest.fixture
def perfil_ar(monkeypatch):
    """O modulo le o perfil na CHAMADA (`resolver_perfil()`), entao trocar o resolvedor basta:
    e o mesmo efeito de subir o container com o `perfil.json` argentino."""
    perfil = carregar_perfil(PERFIL_BR_EMBARCADO.parents[1] / "AR" / "perfil.json")
    monkeypatch.setattr(rm, "resolver_perfil", lambda: perfil)
    return perfil


def _df_argentino() -> pd.DataFrame:
    linhas = [
        _row(-34.60, -58.37, "Comuna 1", "CA", oferta=4451.0, consumo=1000.0),
        _row(-34.61, -58.38, "Comuna 1", "CA", oferta=500.0, consumo=200.0),
    ]
    df = pd.DataFrame(linhas)
    return df.drop(columns=[c for c in _COLUNAS_AUSENTES_NA_AR if c in df.columns])


def test_agregar_municipio_sem_as_colunas_que_a_base_ar_nao_tem():
    """Coluna ausente vira Series de NaN, nao escalar: a penetracao sai n/d e a populacao cai
    para `pop_total` em vez de derrubar a agregacao inteira."""
    res = agregar_municipio(_df_argentino(), nome_municipio="Comuna 1", uf="CA")

    assert res["n_hex_total"] == 2
    assert math.isnan(res["penetracao_fitness_media"])
    assert res["pop_total_municipio"] == pytest.approx(4000.0)


def test_renda_sai_no_simbolo_da_moeda_de_renda_do_perfil(perfil_ar):
    """A renda AR chega em USD enquanto a moeda do pais e ARS ("$"): o rotulo e o codigo
    `USD`, nunca o `R$` fixo nem o `$` do peso."""
    assert rm._renda(1234.56, 2) == "USD 1.234,56"


def test_renda_no_perfil_br_continua_em_reais():
    assert rm._renda(1234.56, 2) == "R$ 1.234,56"
    assert rm._renda(float("nan")) == rm.TEXTO_SEM_DADO


def test_instituto_do_censo_vem_do_perfil(perfil_ar):
    assert rm._instituto_censo() == "INDEC"


def test_instituto_do_censo_no_perfil_br_e_o_ibge():
    assert rm._instituto_censo() == "IBGE"


def _texto_do_pdf(pdf_bytes: bytes) -> bytes:
    """So' os operandos de texto (`(...) Tj`). As imagens vao sem compressao no PDF e, num
    relatorio real de 3 MB, "R$" aparece dezenas de vezes por ACASO dentro delas."""
    return b"\n".join(re.findall(rb"\(([^\n]*)\) ?Tj", pdf_bytes))


def test_pdf_argentino_nao_cita_ibge_nem_reais(perfil_ar):
    payload = _payload_como_a_ui(_df_argentino(), "Comuna 1", "CA")

    assert payload is not None
    assert payload.pdf_bytes.startswith(b"%PDF-1.4")
    texto = _texto_do_pdf(payload.pdf_bytes)
    assert b"IBGE" not in texto
    assert b"R$" not in texto
    assert b"INDEC" in texto
    assert b"USD" in texto
