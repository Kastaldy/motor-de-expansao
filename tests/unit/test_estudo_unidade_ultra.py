"""ESTUDO DA UNIDADE ULTRA x ESTUDO DE PONTO (emenda da DEC-070, 2026-10-16).

O estudo que originou a regra analisava a REGIAO da Ultra Santana/SP, com a unidade no
centro (a 9 m do ponto): como estudo de ponto, o consumo da propria Santana entrava no
mercado ocupado e o residual saia zero. O que este arquivo trava:

(a) `mercado_na_area(excluir_ultra_proxima=True)` tira do consumo UMA unidade -- a mais
    proxima do ponto, a ate' 150 m -- e so' ela; as OUTRAS Ultras continuam contando;
(b) sem o parametro, os valores sao IDENTICOS aos de antes dele;
(c) unidade inexistente / fora da tolerancia / sem cadastro -> erro CLARO
    (`UnidadeUltraForaDaTolerancia`), nunca no-op silencioso;
(d) cadastro duplicado (o MESMO endereco repetido, ate' 50 m) sai inteiro; outra Ultra
    real dentro dos 150 m continua contando;
(e) a rota `/api/ponto` e a do PDF levam o modo de ponta a ponta, com 400 no erro;
(f) o PDF DECLARA o modo (Big Numbers) e a Conclusao nao acusa a unidade estudada de
    canibalizar a si mesma.
"""

from __future__ import annotations

import asyncio
import sys
import threading
from pathlib import Path

import h3
import pandas as pd
import pytest
from fastapi import HTTPException

from motor_expansao.dashboard import mercado_raio as mr
from motor_expansao.pipelines.calcular_colunas_mercado import (
    CAPACIDADE_DEFAULT_CONCORRENTE_ALUNOS,
)
from motor_expansao.pipelines.pressao_concorrencial_1km import _metros_por_grau

_REPO = Path(__file__).resolve().parents[2]
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import app as pilot  # noqa: E402

LAT, LNG = -23.55, -46.63
CAP = CAPACIDADE_DEFAULT_CONCORRENTE_ALUNOS


def _norte(metros: float) -> tuple[float, float]:
    m_lat, _ = _metros_por_grau(LAT)
    return LAT + metros / m_lat, LNG


def _ultras(*linhas: tuple[float, float, str, str, float | None]) -> pd.DataFrame:
    """(lat, lng, ultra_id, nome, capacidade)."""
    return pd.DataFrame(
        {
            "lat": [r[0] for r in linhas],
            "lng": [r[1] for r in linhas],
            mr.COLUNA_CAPACIDADE: [r[4] for r in linhas],
            mr.COLUNA_ULTRA_ID: [r[2] for r in linhas],
            mr.COLUNA_ULTRA_NOME: [r[3] for r in linhas],
        }
    )


def _mercado(ultra: pd.DataFrame | None, **kw):
    base = dict(
        pop_area=40_000.0,
        cadeias=pd.DataFrame({"lat": [LAT], "lng": [LNG]}),
        ultra=ultra,
        taxa=0.2,
        faixa_oportunidade="alta",
    )
    base.update(kw)
    return mr.mercado_na_area(LAT, LNG, **base)


# Santana colada no ponto (9 m, como no caso real) e outra Ultra a 500 m.
_SANTANA = _norte(9.0) + ("id-santana", "Santana", None)
_OUTRA = _norte(500.0) + ("id-outra", "Vila Guilherme / SP", 3_000.0)


# --------------------------------------------------------------------------- #
# (a) so' a unidade estudada sai                                               #
# --------------------------------------------------------------------------- #
def test_exclui_so_a_unidade_alvo_e_as_outras_ultras_continuam_contando() -> None:
    ultra = _ultras(_SANTANA, _OUTRA)
    ponto = _mercado(ultra)
    unidade = _mercado(ultra, excluir_ultra_proxima=True)
    so_outra = _mercado(_ultras(_OUTRA))

    # A parcela da Ultra no estudo da unidade e' EXATAMENTE a da outra unidade sozinha.
    assert unidade["oferta_consumida_ultra_estimada"] == pytest.approx(
        so_outra["oferta_consumida_ultra_estimada"], rel=1e-9
    )
    assert unidade["oferta_consumida_ultra_estimada"] > 0
    assert unidade["n_ultra_alcancam"] == 1 and ponto["n_ultra_alcancam"] == 2
    # Concorrentes e SAM nao mudam com o modo.
    assert unidade["oferta_consumida_mercado_estimada"] == ponto["oferta_consumida_mercado_estimada"]
    assert unidade["sam_fitness_potencial"] == ponto["sam_fitness_potencial"]
    # O que saiu e' declarado, e fecha a diferenca entre os dois modos.
    est = unidade["unidade_ultra_estudada"]
    assert est["ultra_id"] == "id-santana" and est["nome"] == "Santana"
    assert est["dist_m"] == pytest.approx(9.0, abs=0.5)
    assert est["capacidade_real"] is False  # sem alunos reais -> proxy de 2.500
    assert est["consumo_excluido"] == pytest.approx(
        ponto["oferta_consumida_ultra_estimada"] - unidade["oferta_consumida_ultra_estimada"],
        rel=1e-9,
    )
    assert unidade["modo_estudo"] == mr.MODO_ESTUDO_UNIDADE_ULTRA
    assert unidade["oferta_efetiva_disponivel"] == pytest.approx(
        max(unidade["sam_fitness_potencial"] - unidade["oferta_consumida_total_estimada"], 0)
    )


def test_a_declaracao_diz_quem_saiu_e_quanto_e_cabe_no_pdf() -> None:
    d = _mercado(_ultras(_SANTANA), excluir_ultra_proxima=True)["declaracao_modo"]
    assert d.startswith("Estudo da unidade Ultra Santana: consumo da própria unidade (")
    assert "alunos) desconsiderado" in d
    d.encode("latin-1")  # core font do fpdf2: nada fora de latin-1


def test_nome_do_cadastro_com_uf_sai_curto() -> None:
    assert mr.nome_curto_ultra("Vila Zelina / SP") == "Vila Zelina"
    assert mr.nome_curto_ultra(None) == "sem nome"


# --------------------------------------------------------------------------- #
# (b) sem o parametro = identico a antes                                       #
# --------------------------------------------------------------------------- #
_CHAVES_DE_VALOR = (
    "sam_fitness_potencial",
    "oferta_consumida_mercado_estimada",
    "oferta_consumida_ultra_estimada",
    "oferta_consumida_total_estimada",
    "oferta_efetiva_disponivel",
    "score_oportunidade_residual",
    "n_ultra_alcancam",
    "n_concorrentes_alcancam",
)


def test_sem_o_parametro_os_valores_sao_os_de_sempre() -> None:
    ultra = _ultras(_SANTANA, _OUTRA)
    padrao = _mercado(ultra)
    explicito = _mercado(ultra, excluir_ultra_proxima=False)
    # O frame "de antes" (sem as colunas de identidade) da' os mesmos numeros.
    antigo = _mercado(ultra[["lat", "lng", mr.COLUNA_CAPACIDADE]])
    for k in _CHAVES_DE_VALOR:
        assert padrao[k] == explicito[k] == antigo[k], k
    assert padrao["modo_estudo"] == mr.MODO_ESTUDO_PONTO
    assert padrao["unidade_ultra_estudada"] is None
    assert padrao["declaracao_modo"] is None
    # A Ultra na tolerancia e' OFERECIDA mesmo no estudo de ponto (e' o que a ficha usa).
    assert padrao["ultra_proxima"]["nome"] == "Santana"


# --------------------------------------------------------------------------- #
# (c) erro claro                                                               #
# --------------------------------------------------------------------------- #
def test_sem_ultra_na_tolerancia_e_erro_claro_nunca_no_op() -> None:
    longe = _norte(151.0) + ("id-x", "Longe", None)
    assert _mercado(_ultras(longe))["ultra_proxima"] is None
    with pytest.raises(mr.UnidadeUltraForaDaTolerancia, match="150 m"):
        _mercado(_ultras(longe), excluir_ultra_proxima=True)
    with pytest.raises(mr.UnidadeUltraForaDaTolerancia):
        _mercado(_ultras(), excluir_ultra_proxima=True)
    with pytest.raises(mr.UnidadeUltraForaDaTolerancia, match="cadastro"):
        _mercado(None, excluir_ultra_proxima=True)


def test_as_recusas_dizem_estudo_da_unidade_que_o_front_reconhece() -> None:
    # `ehRecusaDoEstudoDaUnidade` (web/src/lib/estudo-ultra.ts) so' cai no estudo de ponto
    # quando o 400 diz "estudo da unidade"; mudar a frase aqui sem la' faria o front
    # perder a analise em vez de seguir no outro modo.
    for ultra in (None, _ultras(_norte(151.0) + ("id-x", "Longe", None))):
        with pytest.raises(mr.UnidadeUltraForaDaTolerancia) as exc:
            mr.exigir_unidade_ultra(ultra, LAT, LNG)
        assert "estudo da unidade" in str(exc.value).lower()


def test_tolerancia_e_a_do_pin_da_ficha() -> None:
    assert mr.TOLERANCIA_UNIDADE_ULTRA_M == 150.0
    ts = (_REPO / "web" / "src" / "lib" / "estudo-ultra.ts")
    if ts.is_file():
        assert "TOLERANCIA_UNIDADE_ULTRA_M = 150" in ts.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# (d) cadastro duplicado                                                       #
# --------------------------------------------------------------------------- #
def test_cadastro_duplicado_no_mesmo_endereco_sai_inteiro() -> None:
    # O par REAL do cadastro: "Valparaiso / GO" gravada a 6 m de "Vila Zelina / SP". Tirar
    # so' a mais proxima deixava o fantasma no consumo numa ficha que diz que a unidade saiu.
    a = _norte(5.0) + ("id-a", "Vila Zelina / SP", None)
    b = _norte(11.0) + ("id-b", "Valparaiso / GO", None)
    r = _mercado(_ultras(a, b), excluir_ultra_proxima=True)
    est = r["unidade_ultra_estudada"]
    assert est["ultra_id"] == "id-a"
    assert est["n_na_tolerancia"] == 2
    assert est["n_linhas_excluidas"] == 2
    assert r["n_ultra_alcancam"] == 0
    assert r["oferta_consumida_ultra_estimada"] == pytest.approx(0.0, abs=1e-6)
    ponto = _mercado(_ultras(a, b))
    assert est["consumo_excluido"] == pytest.approx(ponto["oferta_consumida_ultra_estimada"])
    assert "repete este endereço em 2 linhas" in r["declaracao_modo"]
    r["declaracao_modo"].encode("latin-1")


def test_outra_ultra_a_mais_de_50_m_da_estudada_continua_contando() -> None:
    # Duas unidades REAIS podem ficar dentro dos 150 m do ponto; so' o MESMO endereco sai.
    a = _norte(5.0) + ("id-a", "Vila Zelina / SP", None)
    b = _norte(120.0) + ("id-b", "Vizinha / SP", None)
    r = _mercado(_ultras(a, b), excluir_ultra_proxima=True)
    assert r["unidade_ultra_estudada"]["n_linhas_excluidas"] == 1
    assert r["n_ultra_alcancam"] == 1
    assert "repete" not in r["declaracao_modo"]


def test_carga_do_cadastro_leva_identidade() -> None:
    mapeadas = pd.DataFrame({
        "ultra_id": ["u1"], "unidade": ["Santana"], "lat": [LAT], "lng": [LNG],
        "flag_coord_valida": [True], "hex_id_res7": [h3.latlng_to_cell(LAT, LNG, 7)],
    })
    perf = pd.DataFrame({
        "unidade": ["Extra"], "lat": [LAT + 0.2], "lng": [LNG], "alunos_total": [1_000],
    })
    u = mr.unidades_ultra_com_capacidade(mapeadas, perf)
    assert u[mr.COLUNA_ULTRA_ID].tolist()[0] == "u1"
    assert u[mr.COLUNA_ULTRA_NOME].tolist() == ["Santana", "Extra"]
    assert pd.isna(u[mr.COLUNA_ULTRA_ID].tolist()[1])


# --------------------------------------------------------------------------- #
# (e) rotas                                                                    #
# --------------------------------------------------------------------------- #
def _staging(dir_: Path) -> None:
    dir_.mkdir(parents=True, exist_ok=True)
    cell = h3.latlng_to_cell(LAT, LNG, 7)
    pd.DataFrame({
        "hex_id": [cell],
        "faixa_oportunidade": ["alta"],
        "taxa_fitness_mercado_calibrada": [0.2],
        "sam_fitness_potencial": [12_000.0],
        "oferta_efetiva_disponivel": [0.0],
        "score_oportunidade_residual": [0.0],
        "oferta_consumida_mercado_estimada": [9_000.0],
        "oferta_consumida_ultra_estimada": [5_000.0],
    }).to_parquet(dir_ / "hexagonos_mercado_mapeado.parquet", index=False)
    pd.DataFrame({
        "concorrente_id": ["c1"], "rede": ["smart_fit"], "lat": [LAT], "lng": [LNG],
        "status_registro": ["valido"],
    }).to_parquet(dir_ / "concorrentes_mapeados.parquet", index=False)
    lat_s, lng_s = _norte(9.0)
    pd.DataFrame({
        "ultra_id": ["id-santana"], "unidade": ["Santana"], "uf": ["SP"],
        "lat": [lat_s], "lng": [lng_s], "flag_coord_valida": [True], "hex_id_res7": [cell],
    }).to_parquet(dir_ / "unidades_ultra_mapeadas.parquet", index=False)


@pytest.fixture
def rota(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from motor_expansao.api import service as api_service
    from motor_expansao.dashboard import censo_point

    setores = pd.DataFrame({"cod_setor": ["355030801000001"], "nome_municipio": ["São Paulo"]})
    monkeypatch.setattr(
        api_service, "_resolver_e_carregar", lambda lat, lng, cfg: ("SP", "3550308", setores)
    )
    monkeypatch.setattr(api_service, "_competitors_ultra", lambda cfg: (None, None))
    monkeypatch.setattr(
        censo_point,
        "analisar_ponto_censitario_setores",
        lambda *a, **k: {"pop_total_raio": 30_000.0, "n_setores": 40},
    )
    staging = tmp_path / "staging"
    _staging(staging)
    monkeypatch.setattr(pilot, "STAGING_DIR", staging)
    mr.carregar_ultra_mercado.cache_clear()
    mr.carregar_cadeias_mercado.cache_clear()
    yield
    mr.carregar_ultra_mercado.cache_clear()
    mr.carregar_cadeias_mercado.cache_clear()


def test_rota_ponto_padrao_e_estudo_de_ponto_e_oferece_a_unidade(rota) -> None:
    m = pilot.ponto(lat=LAT, lng=LNG)["mercado"]
    assert m["modo_estudo"] == "ponto"
    assert m["unidade_ultra_estudada"] is None and m["declaracao_modo"] is None
    assert m["ultra_proxima"]["nome"] == "Santana"
    assert m["ultra_proxima"]["dist_m"] == 9
    assert m["consumo_ultra"] == pytest.approx(CAP, abs=30)  # a Santana conta


def test_rota_ponto_estudo_da_unidade_tira_o_consumo_dela(rota) -> None:
    m = pilot.ponto(lat=LAT, lng=LNG, excluir_ultra_proxima=True)["mercado"]
    assert m["modo_estudo"] == "unidade_ultra"
    assert m["consumo_ultra"] == 0
    assert m["consumo_total"] == m["consumo_concorrentes"]
    assert m["residual"] == max(m["sam"] - m["consumo_total"], 0)
    assert m["unidade_ultra_estudada"]["nome"] == "Santana"
    assert m["unidade_ultra_estudada"]["consumo_excluido"] == pytest.approx(CAP, abs=30)
    assert m["declaracao_modo"].startswith("Estudo da unidade Ultra Santana")


def test_rota_ponto_estudo_da_unidade_longe_de_ultra_e_400(rota) -> None:
    lat2, lng2 = _norte(800.0)
    with pytest.raises(HTTPException) as exc:
        pilot.ponto(lat=lat2, lng=lng2, excluir_ultra_proxima=True)
    assert exc.value.status_code == 400
    assert "150 m" in exc.value.detail


def test_nome_do_parametro_e_o_que_o_front_envia() -> None:
    import inspect

    assert "excluir_ultra_proxima" in inspect.signature(pilot.ponto).parameters
    assert "excluir_ultra_proxima" in inspect.signature(pilot.relatorio_pontual).parameters
    api_ts = _REPO / "web" / "src" / "lib" / "api.ts"
    if api_ts.is_file():
        texto = api_ts.read_text(encoding="utf-8")
        assert "&excluir_ultra_proxima=true" in texto
        assert "q.set('excluir_ultra_proxima', 'true')" in texto


@pytest.fixture
def pdf_espiao(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    outputs = tmp_path / "outputs"
    (outputs / "setores_censitarios_2022_geo").mkdir(parents=True)
    monkeypatch.setattr(pilot, "DATA_DIR", tmp_path)
    monkeypatch.setattr(pilot, "OUTPUTS_DIR", outputs)
    monkeypatch.setattr(pilot, "STAGING_DIR", tmp_path / "staging")
    monkeypatch.setattr(pilot, "ULTRA_DIR", tmp_path / "ultra")
    monkeypatch.setattr(pilot, "CENSO_GEO_DIR", outputs / "setores_censitarios_2022_geo")

    from motor_expansao.api import service as api_service
    from motor_expansao.dashboard import censo_map, censo_point, censo_report

    setores = pd.DataFrame({"cod_setor": ["355030801000001"], "nome_municipio": ["SAO PAULO"]})
    monkeypatch.setattr(
        api_service, "_resolver_e_carregar", lambda lat, lng, cfg: ("SP", "3550308", setores)
    )
    monkeypatch.setattr(api_service, "_competitors_ultra", lambda cfg: (None, None))
    monkeypatch.setattr(api_service, "_nome_municipio_de", lambda df: "SAO PAULO")
    visto: dict[str, object] = {}

    def _mercado_fake(lat, lng, cfg, pop, **k):
        visto["kw_mercado"] = k
        if k.get("excluir_ultra_proxima") and visto.get("sem_ultra"):
            raise mr.UnidadeUltraForaDaTolerancia("Não há unidade Ultra a até 150 m deste ponto.")
        return {"grao": "raio", "modo_estudo": "unidade_ultra" if k else "ponto"}

    monkeypatch.setattr(api_service, "_mercado_do_ponto", _mercado_fake)
    monkeypatch.setattr(
        censo_point, "analisar_ponto_censitario_setores", lambda *a, **k: {"raio_km": 1.0}
    )
    monkeypatch.setattr(censo_point, "agregar_perfil_bairro_distrito", lambda *a, **k: None)
    monkeypatch.setattr(censo_map, "render_mapas_censitarios_combinados", lambda *a, **k: None)
    monkeypatch.setattr(censo_map, "render_foto_satelite_ponto", lambda *a, **k: None)
    monkeypatch.setattr(censo_map, "_BASEMAP_CACHE_DIR", censo_map._BASEMAP_CACHE_DIR)
    monkeypatch.setattr(pilot, "_praca_para_pdf", lambda *a, **k: None)

    def _fake_gerar(result, mapas, **kwargs):
        visto.update(kwargs)
        return b"%PDF-1.4 stub"

    monkeypatch.setattr(censo_report, "gerar_pdf_relatorio_pontual_classico", _fake_gerar)

    def _validar_fake(lat, lng):
        visto["thread_validacao"] = threading.get_ident()
        if visto.get("sem_ultra"):
            raise HTTPException(400, "Não há unidade Ultra a até 150 m deste ponto.")

    monkeypatch.setattr(pilot, "_validar_estudo_da_unidade", _validar_fake)
    registrados: list[str] = []
    visto["registrados"] = registrados

    def _registrar_fake(*a, **k):
        registrados.append("pontual")
        return "rid"

    monkeypatch.setattr(pilot, "_registrar_relatorio_gerado", _registrar_fake)
    return visto


def _pdf(**kw):
    return asyncio.run(pilot.relatorio_pontual(lat=LAT, lng=LNG, **kw))


def test_pdf_leva_o_modo_ao_mercado_com_e_sem_so_estudo(pdf_espiao) -> None:
    _pdf(so_estudo=True, excluir_ultra_proxima=True)
    assert pdf_espiao["kw_mercado"] == {"excluir_ultra_proxima": True}
    assert pdf_espiao["residual"]["modo_estudo"] == "unidade_ultra"
    _pdf(excluir_ultra_proxima=True)
    assert pdf_espiao["kw_mercado"] == {"excluir_ultra_proxima": True}
    # Sem o parametro, a chamada e' a de sempre (nenhum kwarg novo).
    _pdf(so_estudo=True)
    assert pdf_espiao["kw_mercado"] == {}


def test_pdf_estudo_da_unidade_longe_de_ultra_e_400(pdf_espiao) -> None:
    pdf_espiao["sem_ultra"] = True
    with pytest.raises(HTTPException) as exc:
        _pdf(so_estudo=True, excluir_ultra_proxima=True)
    assert exc.value.status_code == 400
    # A recusa vem ANTES: nada registrado como gerado e o mercado nem foi montado.
    assert pdf_espiao["registrados"] == []
    assert "kw_mercado" not in pdf_espiao


def test_validacao_antecipada_roda_fora_do_event_loop(pdf_espiao) -> None:
    """A rota do PDF e' `async def`: a 1a chamada apos um restart le' o cadastro Ultra em
    Parquet, e direto no loop isso parava o unico worker -- inclusive o /api/health
    (revisao do admin, 2026-10-15). A validacao tem de rodar no threadpool."""
    _pdf(so_estudo=True, excluir_ultra_proxima=True)
    assert "thread_validacao" in pdf_espiao
    # `asyncio.run` roda o loop nesta thread; a validacao NAO pode ter rodado nela.
    assert pdf_espiao["thread_validacao"] != threading.get_ident()


def test_recusa_no_threadpool_continua_antes_de_registrar(pdf_espiao) -> None:
    pdf_espiao["sem_ultra"] = True
    with pytest.raises(HTTPException) as exc:
        _pdf(excluir_ultra_proxima=True)
    assert exc.value.status_code == 400
    assert pdf_espiao["thread_validacao"] != threading.get_ident()
    assert pdf_espiao["registrados"] == []


# --------------------------------------------------------------------------- #
# Falha do calculo de mercado NAO volta como estudo de ponto                   #
# --------------------------------------------------------------------------- #
def _cfg(staging: Path):
    from motor_expansao.api.settings import Settings

    return Settings(
        censo_geo_dir=staging, ibge_dir=staging, ultra_dir=staging, staging_dir=staging,
        perfil=pilot.PERFIL,
    )


def test_falha_do_mercado_no_estudo_da_unidade_declara_o_modo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from motor_expansao.api import service as api_service

    def _quebra(*a, **k):
        raise RuntimeError("parquet ilegivel")

    monkeypatch.setattr(mr, "mercado_na_area", _quebra)
    out = api_service._mercado_do_ponto(
        LAT, LNG, _cfg(tmp_path), 30_000.0, excluir_ultra_proxima=True
    )
    assert out["disponivel"] is False
    # O modo pedido segue declarado: sem isto a ficha lia o default "ponto".
    assert out["modo_estudo"] == "unidade_ultra"
    assert out["unidade_ultra_estudada"] is None
    assert "unidade Ultra" in out["motivo"]
    assert out["declaracao_modo"].startswith("Estudo da unidade Ultra")
    assert "nenhum consumo foi retirado" in out["declaracao_modo"]
    # A frase vai ao PDF (core font latin-1): nada fora de latin-1.
    out["declaracao_modo"].encode("latin-1")
    # Estudo de ponto com a mesma falha: nada de modo inventado.
    ponto = api_service._mercado_do_ponto(LAT, LNG, _cfg(tmp_path), 30_000.0)
    assert ponto["disponivel"] is False and "modo_estudo" not in ponto


def test_falha_do_mercado_na_rota_mantem_o_estudo_da_unidade(
    rota, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _quebra(*a, **k):
        raise RuntimeError("parquet ilegivel")

    monkeypatch.setattr(mr, "mercado_na_area", _quebra)
    m = pilot.ponto(lat=LAT, lng=LNG, excluir_ultra_proxima=True)["mercado"]
    assert m["disponivel"] is False
    assert m["modo_estudo"] == "unidade_ultra"
    assert m["declaracao_modo"].startswith("Estudo da unidade Ultra")
    assert m["residual"] is None and m["consumo_total"] is None


def test_conclusao_com_mercado_em_falha_tira_a_unidade_do_centro() -> None:
    from motor_expansao.dashboard.censo_report import _avaliar_conclusao

    result = {
        "pop_total_raio": 20_000, "renda_per_capita_media_raio": 3_000.0,
        "domicilios_total_raio": 8_000, "renda_domiciliar_total_raio": 9_000.0,
        "n_concorrentes": 2, "n_ultra": 1, "ultra_raio": [{"dist_km": 0.009}],
    }
    falha = {"disponivel": False, "modo_estudo": "unidade_ultra", "unidade_ultra_estudada": None}
    parecer = _avaliar_conclusao(result, falha, None, {}, somente_estudo=True)
    textos = " ".join(str(x) for x in parecer.demografico.ressalvas)
    assert "Canibaliza" not in textos
    # Controle: no estudo de ponto a mesma Ultra a 9 m continua no alerta.
    ponto = _avaliar_conclusao(result, {"disponivel": False}, None, {}, somente_estudo=True)
    assert "Canibaliza" in " ".join(str(x) for x in ponto.demografico.ressalvas)


def test_validacao_antecipada_usa_a_mesma_regra_do_mercado(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pilot, "STAGING_DIR", tmp_path / "vazio")
    with pytest.raises(HTTPException) as exc:
        pilot._validar_estudo_da_unidade(LAT, LNG)
    assert exc.value.status_code == 400 and "cadastro" in exc.value.detail
    ultra = _ultras(_SANTANA)
    monkeypatch.setattr(mr, "carregar_ultra_mercado", lambda s: ultra)
    pilot._validar_estudo_da_unidade(LAT, LNG)  # Santana a 9 m: passa
    longe = _ultras(_norte(151.0) + ("id-x", "Longe", None))
    monkeypatch.setattr(mr, "carregar_ultra_mercado", lambda s: longe)
    with pytest.raises(HTTPException, match="150 m"):
        pilot._validar_estudo_da_unidade(LAT, LNG)


# --------------------------------------------------------------------------- #
# (f) o PDF declara o modo                                                     #
# --------------------------------------------------------------------------- #
def test_conclusao_nao_acusa_a_unidade_estudada_de_canibalizar() -> None:
    from motor_expansao.dashboard.censo_report import _conclusao_canibalizacao

    uma = {"n_ultra": 1, "ultra_raio": [{"dist_km": 0.009}]}
    assert _conclusao_canibalizacao(uma) is not None  # estudo de ponto: alerta, como antes
    assert _conclusao_canibalizacao(uma, sem_a_estudada=True) is None
    duas = {"n_ultra": 2, "ultra_raio": [{"dist_km": 0.009}, {"dist_km": 0.5}]}
    alerta = _conclusao_canibalizacao(duas, sem_a_estudada=True)
    assert alerta == "Canibalização da rede: 1 unidade Ultra dentro do raio do estudo; a unidade está a 500 m do ponto."


def test_conclusao_casa_a_estudada_pela_coordenada_do_mercado() -> None:
    from motor_expansao.dashboard.censo_report import _conclusao_canibalizacao

    santana = _norte(9.0)
    outra = _norte(300.0)
    estudada = {"nome": "Santana", "lat": santana[0], "lng": santana[1]}
    # Endereco repetido no cadastro (o par de Vila Zelina): as duas linhas saem.
    dup = {
        "n_ultra": 2,
        "ultra_raio": [
            {"dist_km": 0.005, "lat": santana[0], "lng": santana[1]},
            {"dist_km": 0.011, "lat": _norte(15.0)[0], "lng": LNG},
        ],
    }
    assert _conclusao_canibalizacao(dup, sem_a_estudada=True, estudada=estudada) is None
    # A estudada NAO esta' na lista do censo (veio de outro cadastro): nada sai, e a Ultra
    # real mais proxima do ponto continua no alerta.
    so_outra = {"n_ultra": 1, "ultra_raio": [{"dist_km": 0.3, "lat": outra[0], "lng": outra[1]}]}
    alerta = _conclusao_canibalizacao(so_outra, sem_a_estudada=True, estudada=estudada)
    assert alerta is not None and "a 300 m" in alerta
    # Sem coordenada na estudada: a regra antiga (sai a mais proxima).
    assert _conclusao_canibalizacao(so_outra, sem_a_estudada=True, estudada={"nome": "X"}) is None


def test_big_numbers_declara_o_modo_e_as_parcelas() -> None:
    from motor_expansao.dashboard.censo_report import gerar_pdf_relatorio_pontual_classico

    declaracao = mr.declaracao_estudo_ultra({"nome": "Santana", "consumo_excluido": 2_486.0})
    residual = {
        "grao": "raio",
        "sam_fitness_potencial": 6_418.0,
        "oferta_consumida_mercado_estimada": 4_865.0,
        "oferta_consumida_ultra_estimada": 0.0,
        "oferta_consumida_total_estimada": 4_865.0,
        "oferta_efetiva_disponivel": 1_553.0,
        "score_oportunidade_residual": 62.1,
        "modo_estudo": "unidade_ultra",
        "unidade_ultra_estudada": {"nome": "Santana", "consumo_excluido": 2_486.0},
        "declaracao_modo": declaracao,
    }
    result = {"lat": LAT, "lng": LNG, "raio_km": 1.0, "nome_municipio": "SAO PAULO", "uf": "SP"}
    texto = gerar_pdf_relatorio_pontual_classico(result, None, residual=residual).decode(
        "latin-1", errors="replace"
    )
    assert "conc. 4.865 + outras Ultras 0" in texto
    assert "Estudo da unidade Ultra Santana: consumo da pr" in texto
    # Parenteses saem escapados no fluxo do PDF ("\("): casa o miolo.
    assert "2.486 alunos" in texto and "desconsiderado" in texto
    # Controle: no estudo de ponto nao ha' frase de modo e a parcela e' "Ultra".
    ponto = dict(residual, modo_estudo="ponto", unidade_ultra_estudada=None, declaracao_modo=None)
    texto_ponto = gerar_pdf_relatorio_pontual_classico(result, None, residual=ponto).decode(
        "latin-1", errors="replace"
    )
    assert "Estudo da unidade Ultra" not in texto_ponto
    assert "conc. 4.865 + Ultra 0" in texto_ponto
