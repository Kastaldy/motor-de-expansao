"""Proveniencia da renda exibida (E0 do plano de correcao da renda; DEC-072).

Toda renda que passa pelo modulo `motor_expansao.renda` tem de dizer de que versao de fatores
e de quando ela e:
  - JSON: chave top-level `renda_meta` (a `proveniencia()` SEM o `rotulo_pdf`) nos payloads do
    ponto, da UF/municipio, da rede e da API externa, e no `/api/me` (o front le dali);
  - healthchecks: `renda_fatores = {versao, fixada_por_env}` -- metodologia publica, sem
    caminho nem infra (o `/api/health` do piloto foi enxugado no pentest, Onda B #8);
  - PDFs: a linha `rotulo_pdf` (ASCII) na nota de fontes das paginas que exibem essa renda.

Payloads de renda CRUA (`/api/hexagonos`, `setores-heatmap`, `oportunidades`) NAO levam a chave
ainda: a renda deles nao passa pelo modulo (fica para a E1). Travado aqui tambem, para a chave
nao aparecer neles por engano e afirmar uma atualizacao temporal que nao foi aplicada.

Texto do PDF: o `_UltraPDF` dos dois relatorios e o `UltraPDF` do PDF da rede geram SEM
compressao, entao cada `cell()`/linha de `multi_cell()` vira um literal `(texto) Tj` nos bytes
crus. `_texto_do_pdf` junta esses literais com espaco -- e assim a linha que o `multi_cell`
quebrou em duas volta a ser uma frase so. Nao ha extrator de PDF no ambiente (pypdf/pymupdf
fora do [dev]) e este arquivo nao adiciona dependencia nova.
"""

from __future__ import annotations

import ast
import asyncio
import re
import sys
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest

from motor_expansao.renda import (
    carregar_fatores,
    fatores_do_health,
    proveniencia,
    renda_meta,
)

RAIZ = Path(__file__).resolve().parents[2]
SERVER = RAIZ / "web" / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))


def _texto_do_pdf(pdf: bytes) -> str:
    """Os literais `(...) Tj` do PDF, juntos por espaco e com o espaco normalizado."""
    cru = pdf.decode("latin-1", errors="replace")
    pedacos = []
    for m in re.finditer(r"\(((?:\\.|[^\\)])*)\)\s*Tj", cru):
        pedacos.append(re.sub(r"\\(.)", r"\1", m.group(1)))
    return re.sub(r"\s+", " ", " ".join(pedacos))


def _rotulo_pdf() -> str:
    return str(proveniencia()["rotulo_pdf"])


# ---------------------------------------------------------------------------
# O dict
# ---------------------------------------------------------------------------


def test_renda_meta_e_a_proveniencia_sem_o_rotulo_do_pdf():
    meta = renda_meta()
    completa = proveniencia()
    assert "rotulo_pdf" not in meta
    assert meta == {k: v for k, v in completa.items() if k != "rotulo_pdf"}
    assert set(meta) == {
        "versao_fator", "pais", "ano_base", "data_referencia_base", "ano_alvo", "fonte",
        "rotulo", "fixada_por_env", "excecoes_uf",
    }


def test_renda_meta_devolve_dict_novo_a_cada_chamada():
    """Quem recebe pode mexer (o payload e montado por cima) sem contaminar o proximo."""
    a = renda_meta()
    a["rotulo"] = "contaminado"
    a["excecoes_uf"].append("XX")
    assert renda_meta()["rotulo"] != "contaminado"
    assert "XX" not in renda_meta()["excecoes_uf"]


def test_bloco_do_health_so_tem_versao_e_fixacao():
    f = carregar_fatores()
    assert fatores_do_health() == {"versao": f.versao, "fixada_por_env": False}


def test_rotulo_pdf_e_ascii_e_cabe_no_latin1():
    """O PDF usa a fonte core (latin-1): travessao, bullet e reticencias virariam '?'."""
    for pais in ("BR", "AR"):
        rotulo = carregar_fatores(pais).rotulo_pdf
        assert rotulo.isascii(), pais
        assert "..." not in rotulo


# ---------------------------------------------------------------------------
# Piloto web
# ---------------------------------------------------------------------------


def test_api_me_traz_renda_meta_top_level_e_nao_no_perfil():
    import app as pilot

    resposta = pilot.me(remote_user=None)
    assert resposta["renda_meta"] == renda_meta()
    assert "renda_meta" not in resposta["perfil"]


def test_health_do_piloto_tem_a_versao_de_fatores_e_nada_alem():
    import app as pilot

    corpo = asyncio.run(pilot.health())
    assert corpo == {"status": "ok", "renda_fatores": fatores_do_health()}
    # Sem caminho, sem infra (pentest Onda B #8): nada que pareca path no corpo inteiro.
    assert "/" not in repr(corpo["renda_fatores"]["versao"])


def test_boot_do_piloto_loga_versao_pais_e_fixacao(caplog):
    import app as pilot

    with caplog.at_level("INFO", logger="piloto.renda"):
        pilot._init_renda_paths_no_boot()
    f = carregar_fatores()
    linhas = [r for r in caplog.records if r.name == "piloto.renda"]
    assert any(
        f"versao={f.versao}" in r.getMessage()
        and f"pais={f.pais}" in r.getMessage()
        and "fixada_por_env=False" in r.getMessage()
        and r.levelname == "INFO"
        for r in linhas
    )


def _funcao(arvore: ast.Module, nome: str) -> ast.FunctionDef:
    for no in ast.walk(arvore):
        if isinstance(no, ast.FunctionDef) and no.name == nome:
            return no
    raise AssertionError(f"funcao {nome} sumiu de app.py")


def test_payloads_de_renda_crua_nao_afirmam_proveniencia():
    """`/api/hexagonos`, `setores-heatmap` e `oportunidades` servem renda CRUA (sem uplift e sem
    fator temporal): ate a E1 nao passam pelo modulo e NAO podem carregar `renda_meta` -- ela
    afirmaria uma atualizacao que nao foi aplicada. Varredura no fonte, molde do ponto unico."""
    arvore = ast.parse((SERVER / "app.py").read_text(encoding="utf-8"))
    for nome in ("_ranking_hexagonos", "_setores_heatmap_features", "_carregar_oportunidades"):
        fonte = ast.unparse(_funcao(arvore, nome))
        assert "renda_meta" not in fonte, nome


def test_payloads_que_passam_pelo_modulo_carregam_renda_meta():
    """As funcoes que montam os payloads com renda do modulo chamam `_renda.renda_meta()`."""
    arvore = ast.parse((SERVER / "app.py").read_text(encoding="utf-8"))
    for nome in (
        "_payload_ponto", "uf_view", "municipio", "_rede_setores_entorno",
        "rede_inteligencia_recorte", "rede_unidade_inteligencia", "me",
    ):
        assert "_renda.renda_meta()" in ast.unparse(_funcao(arvore, nome)), nome


# ---------------------------------------------------------------------------
# API externa
# ---------------------------------------------------------------------------


def test_schema_do_analisar_preserva_renda_meta():
    """Sem o campo no Pydantic o FastAPI FILTRA a chave: o `model_dump` e o que vai ao cliente."""
    from motor_expansao.api.schemas import AnalisarResponseJSON

    base = {
        "lat": -23.5, "lng": -46.6, "raio_km": 1.0, "metodo": "m",
        "versao_contrato": "v", "versao_score": "s", "gerado_em": "2026-10-20T00:00:00Z",
    }
    corpo = AnalisarResponseJSON(**base, renda_meta=renda_meta()).model_dump()
    assert corpo["renda_meta"] == renda_meta()
    # Opcional no schema: quem monta sem ela nao quebra (o servico sempre preenche).
    assert AnalisarResponseJSON(**base).model_dump()["renda_meta"] is None


def test_analisar_ponto_da_api_preenche_renda_meta(monkeypatch):
    from motor_expansao.api import service
    from motor_expansao.api.settings import Settings
    from motor_expansao.dashboard import censo_point

    monkeypatch.setattr(service, "_resolver_e_carregar", lambda lat, lng, s: ("SP", "3550308", None))
    monkeypatch.setattr(service, "_competitors_ultra", lambda s: (None, None))
    monkeypatch.setattr(service, "fontes_oferta_presentes", lambda s: ())
    monkeypatch.setattr(
        censo_point, "analisar_ponto_censitario_setores",
        lambda *a, **k: {"raio_km": 1.0, "metodo": "m", "n_setores": 0},
    )
    dados = service.analisar_ponto(-23.5, -46.6, "teste", Settings())
    assert dados["renda_meta"] == renda_meta()


def test_health_da_api_externa_tem_a_versao_de_fatores():
    """Chama o endpoint das DUAS rotas direto (sem `httpx`/TestClient, ausentes no [dev])."""
    from motor_expansao.api.main import create_app

    app = create_app()
    rotas = {r.path: r.endpoint for r in app.routes if getattr(r, "path", "").endswith("/health")}
    assert {"/health", "/api/v1/health"} <= set(rotas)
    for rota in ("/health", "/api/v1/health"):
        corpo = asyncio.run(rotas[rota]())
        assert corpo["renda_fatores"] == fatores_do_health(), rota
        assert corpo["status"] == "ok"


def test_api_le_os_insumos_do_mesmo_staging_que_a_subida_validou(tmp_path, monkeypatch):
    """`API_STAGING_DIR` divergente do staging do perfil: a leitura segue o validado."""
    from motor_expansao.api import settings as api_settings
    from motor_expansao.api.main import create_app
    from motor_expansao.renda import insumos
    from tests.unit.renda_fixtures import apontar_staging_renda

    perfil_staging = tmp_path / "perfil_staging"
    validado = tmp_path / "api_staging"
    perfil_staging.mkdir()
    validado.mkdir()
    apontar_staging_renda(monkeypatch, perfil_staging)  # registra a restauracao pos-teste
    monkeypatch.setenv("API_STAGING_DIR", str(validado))
    api_settings.get_settings.cache_clear()
    try:
        create_app()
        assert insumos.staging_dir() == validado
    finally:
        api_settings.get_settings.cache_clear()


def test_openapi_documenta_renda_meta_e_renda_fatores():
    yaml = pytest.importorskip("yaml")
    spec = yaml.safe_load((RAIZ / "docs" / "api_geoespacial_openapi.yaml").read_text(encoding="utf-8"))
    schemas = spec["components"]["schemas"]
    assert set(schemas["RendaMeta"]["properties"]) == set(renda_meta())
    assert "renda_meta" in schemas["AnalisarResponseJSON"]["properties"]
    assert "renda_fatores" in schemas["HealthResponse"]["properties"]


# ---------------------------------------------------------------------------
# PDFs (pagina FIXA, auto_page_break OFF: a linha tem de caber acima do rodape)
# ---------------------------------------------------------------------------


def _png(w: int = 300, h: int = 200) -> bytes:
    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", (w, h), (0, 167, 157)).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def censo_report():
    pytest.importorskip("h3", exc_type=ImportError)
    from motor_expansao.dashboard import censo_report as cr

    return cr


def test_relatorio_pontual_traz_o_rotulo_nos_big_numbers_e_nos_mapas_de_calor(censo_report):
    result = {"lat": -23.55, "lng": -46.63, "nome_municipio": "SAO PAULO", "uf": "SP", "raio_km": 1.0}
    mapas = {k: _png() for k in ("densidade", "renda", "score", "renda_domiciliar")}
    pdf = censo_report.gerar_pdf_relatorio_pontual_classico(result, mapas)
    texto = _texto_do_pdf(pdf)
    # Uma vez nos Big Numbers (abaixo da nota de fontes) e uma nos Mapas de calor.
    assert texto.count(_rotulo_pdf()) == 2


def test_rotulo_dos_big_numbers_cabe_acima_do_rodape(censo_report, monkeypatch):
    """O rodape e desenhado DEPOIS da nota: o y de quando ele e chamado e o fim do texto."""
    ys: list[float] = []
    original = censo_report._draw_footer

    def espiao(pdf, **kw):
        ys.append(pdf.get_y())
        original(pdf, **kw)

    monkeypatch.setattr(censo_report, "_draw_footer", espiao)
    pdf = censo_report._UltraPDF()
    censo_report._big_numbers_page(pdf, {"lat": -23.55, "lng": -46.63}, None, {})
    assert ys and ys[-1] <= censo_report._PAGE_H - 22


@pytest.mark.parametrize("pais", ["BR", "AR"])
def test_rotulo_dos_mapas_de_calor_cabe_na_linha_do_titulo(censo_report, monkeypatch, pais):
    """Na linha do titulo da secao (o grid vai ate o rodape), numa linha so, sem descer sobre
    os mapas e sem encolher abaixo do piso legivel."""
    from motor_expansao.renda import formula

    monkeypatch.setattr(formula, "carregar_fatores", lambda *a, **k: carregar_fatores(pais))
    pdf = censo_report._UltraPDF()
    pdf.add_page()
    censo_report._nota_renda_na_linha_do_titulo(pdf)
    texto = censo_report._rotulo_renda_pdf()
    assert texto == carregar_fatores(pais).rotulo_pdf
    assert pdf.font_size_pt >= 6.0
    assert pdf.get_string_width(texto) <= censo_report._AVISO_NO_PONTO_LARGURA
    linha = censo_report._CLASSICO_MARGIN + censo_report._CLASSICO_BAND_H + 12.0 + 8.0
    assert linha + 12.0 <= censo_report._CLASSICO_MAPS_TOP


def _tabela(n: int) -> dict[str, Any]:
    linhas = [
        {"hex_id": f"87a8100{i:02d}ffffff", "bairro": "Centro", "pop": 1000.0, "renda": 5000.0,
         "densidade": 8000.0, "score": 50.0, "residual": 2500.0, "destacado": True}
        for i in range(n)
    ]
    return {"linhas": linhas, "n_total": 40, "n_exibidas": n, "fonte_renda": "domiciliar",
            "renda_constante": False}


def test_relatorio_municipal_tabela_traz_o_rotulo_e_cabe(monkeypatch):
    from motor_expansao.dashboard import relatorio_municipal as rm

    ys: list[float] = []
    original = rm._draw_footer

    def espiao(pdf, **kw):
        ys.append(pdf.get_y())
        original(pdf, **kw)

    monkeypatch.setattr(rm, "_draw_footer", espiao)
    pdf = rm._UltraPDF()
    # A tabela cheia (15 linhas, o limite) e o pior caso de altura.
    rm._tabela_hexes_page(pdf, {"tabela_hexes": _tabela(rm._TABELA_HEXES_LIMITE)}, {})
    assert ys and ys[-1] <= rm._PAGE_H - 22
    assert _rotulo_pdf() in _texto_do_pdf(bytes(pdf.output()))


@pytest.mark.parametrize("fonte", ["censo", "m1"])
def test_tabela_com_renda_que_nao_passa_pelo_modulo_nao_leva_o_rotulo(fonte):
    """Per capita calibrada crua ou M1: nao e atualizada no tempo, entao nao cita fatores."""
    from motor_expansao.dashboard import relatorio_municipal as rm

    tabela = {**_tabela(3), "fonte_renda": fonte}
    pdf = rm._UltraPDF()
    rm._tabela_hexes_page(pdf, {"tabela_hexes": tabela}, {})
    assert _rotulo_pdf() not in _texto_do_pdf(bytes(pdf.output()))


def test_paginas_da_praca_trazem_o_rotulo():
    pytest.importorskip("h3", exc_type=ImportError)
    from motor_expansao.dashboard import relatorio_municipal as rm
    from tests.unit.test_relatorio_municipal_praca import _df_cidade, _praca

    praca = _praca(_df_cidade(2))
    for pagina in (rm._praca_calor_page, rm._praca_onde_crescer_page):
        pdf = rm._UltraPDF()
        pagina(pdf, {}, praca, {}, primary=rm.ULTRA_TURQUESA, secondary=rm.ULTRA_MAGENTA)
        assert pdf.pages_count == 1, pagina.__name__
        assert _rotulo_pdf() in _texto_do_pdf(bytes(pdf.output())), pagina.__name__


def test_pdf_de_concorrencia_traz_o_rotulo_so_quando_exibe_renda():
    from motor_expansao.dashboard import rede_export
    from tests.unit.test_concorrencia_pdf import PONTO, _concorrente, _ficha, _inteligencia

    for concorrentes in ([_concorrente("Bluefit Botafogo")], []):
        com = _texto_do_pdf(rede_export.concorrencia_pdf(_ficha(), _inteligencia(concorrentes), PONTO))
        # So na pagina 1 (a da regiao), nunca repetido nas paginas da lista.
        assert com.count(_rotulo_pdf()) == 1, len(concorrentes)
    sem_censo = {"raio_km": 1.0, "censo": {"disponivel": False}}
    sem = _texto_do_pdf(rede_export.concorrencia_pdf(_ficha(), _inteligencia([]), sem_censo))
    assert _rotulo_pdf() not in sem


@pytest.mark.parametrize("pais", ["BR", "AR"])
def test_nota_da_renda_do_pdf_de_concorrencia_cabe_no_vao(monkeypatch, pais):
    """Entre os cartoes da regiao (terminam em y=376) e a legenda (398), numa linha, sem cair
    no corpo 6 (o do numero dos marcadores, que o PDF nao pode mais ter)."""
    from motor_expansao.dashboard import rede_export
    from motor_expansao.dashboard.pdf_base import UltraPDF
    from motor_expansao.renda import formula

    monkeypatch.setattr(formula, "carregar_fatores", lambda *a, **k: carregar_fatores(pais))
    pdf = UltraPDF()
    pdf.add_page()
    largura = rede_export.PAGINA_LARGURA - rede_export._MARGEM - (
        rede_export._MARGEM + rede_export._LADO_DO_MAPA + 20.0
    )
    rede_export._nota_da_renda(pdf, 0.0, 380.0, largura)
    assert pdf.font_size_pt >= 6.5
    assert pdf.get_string_width(carregar_fatores(pais).rotulo_pdf) <= largura
    assert pdf.get_y() <= 398.0


def test_texto_do_pdf_junta_linhas_quebradas():
    """O extrator deste arquivo: dois `Tj` viram uma frase, com o escape de parentese desfeito."""
    pdf = b"BT (Renda: Censo 2022 \\(jul/2022\\) atualizada) Tj ET BT (para 06/2026) Tj ET"
    assert _texto_do_pdf(pdf) == "Renda: Censo 2022 (jul/2022) atualizada para 06/2026"


def test_boot_com_versao_fixada_por_env_loga_warning_e_o_health_diz(caplog, monkeypatch):
    """Rollback por env: o boot sobe em WARNING e o `/api/health` publica `fixada_por_env`."""
    import app as pilot

    from motor_expansao.renda import ENV_VERSAO

    versao = carregar_fatores().versao
    monkeypatch.setenv(ENV_VERSAO, versao)
    carregar_fatores.cache_clear()
    try:
        with caplog.at_level("INFO", logger="piloto.renda"):
            pilot._init_renda_paths_no_boot()
        avisos = [r for r in caplog.records if r.name == "piloto.renda" and r.levelname == "WARNING"]
        assert any("fixada_por_env=True" in r.getMessage() for r in avisos)
        assert asyncio.run(pilot.health())["renda_fatores"] == {"versao": versao, "fixada_por_env": True}
        assert renda_meta()["fixada_por_env"] is True
    finally:
        monkeypatch.delenv(ENV_VERSAO)
        carregar_fatores.cache_clear()


@pytest.mark.parametrize(
    ("compose", "servicos"),
    [("docker-compose.prod.yml", ("api", "web")), ("docker-compose.ar.yml", ("web_ar",))],
)
def test_compose_repassa_a_fixacao_de_versao_aos_containers(compose, servicos):
    """O compose nao tem `env_file`: sem a var listada, o rollback do runbook nao chega."""
    yaml = pytest.importorskip("yaml")
    from motor_expansao.renda import ENV_VERSAO

    spec = yaml.safe_load((RAIZ / compose).read_text(encoding="utf-8"))
    for nome in servicos:
        servico = spec["services"][nome]
        assert "env_file" not in servico  # se ganhar env_file, rever este teste
        env = servico["environment"]
        assert env[ENV_VERSAO] == f"${{{ENV_VERSAO}:-}}", (compose, nome)
