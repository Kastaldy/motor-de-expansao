"""Botao "Estudo" da analise de ponto: `so_estudo` em `POST /api/relatorio/pontual`.

Decisao 4 do Vinicius (2026-10-14): o PDF do Estudo e' EXCLUSIVAMENTE demografico -- o
modo so-estudo do bot (BLK-CONC-ESTUDO / DEC-030) --, com a Conclusao so' com o selo
DEMOGRAFICO e SEM nenhum dado financeiro (viabilidade, DRE, aluguel, payback, teto). As
paginas da praca ("Pressao concorrencial" / "Como a cidade esta indo") FICAM: nao sao
financeiras.

Dois niveis, no molde de `test_relatorio_pontual_origem_centroide_rota.py`:

1. ESPIAO no gerador: o que a rota ENTREGA a ele (kwargs), inclusive o cinto de seguranca
   -- com `so_estudo=True` a viabilidade e os dados do imovel sao descartados MESMO que o
   cliente os mande.
2. PDF DE VERDADE: o gerador real roda e o texto cru do PDF (compressao OFF no
   `_UltraPDF`) e' varrido atras dos termos financeiros. O controle (mesma chamada sem
   `so_estudo`) prova que a varredura enxerga esses termos quando eles existem -- sem ele
   o teste passaria verde com um grep cego.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

_REPO = Path(__file__).resolve().parents[2]
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import app as pilot  # noqa: E402

_LAT, _LNG = -23.55, -46.63

_RESULT = {"lat": _LAT, "lng": _LNG, "nome_municipio": "SAO PAULO", "uf": "SP", "raio_km": 1.0}

_MERCADO = {
    "grao": "raio",
    "sam_fitness_potencial": 3_000.0,
    "oferta_consumida_mercado_estimada": 1_200.0,
    "oferta_consumida_ultra_estimada": 300.0,
    "oferta_consumida_total_estimada": 1_500.0,
    "oferta_efetiva_disponivel": 1_500.0,
    "score_oportunidade_residual": 60.0,
}

# Payload PLANO de viabilidade (retrocompat de `_viab_normalizado`), o mesmo dos testes
# vizinhos -- e' o caminho `viabilidade_json`, que a rota aceita sem rodar o motor.
_VIAB = {
    "alunos_breakeven": 520,
    "aluguel_teto": 24500.0,
    "margem_ebitda_pct": 0.18,
    "payback_meses": 26.0,
    "roic_anual": 0.22,
    "faturamento_mensal": 150_000.0,
    "ebitda_mensal": 27_000.0,
    "faixa_p10": 400,
    "faixa_p90": 1000,
    "flag_viavel": True,
    "flag_fora_envelope": False,
}
_INFO_IMOVEL = {"metragem_m2": 1500, "aluguel_pedido": 38_000.0, "valor_venda": 9_000_000.0}

# Marcadores de DADO financeiro no texto do PDF. "aluguel" minusculo NAO entra: a nota da
# Conclusao so-estudo diz, de proposito, que o imovel (metragem, aluguel) NAO foi avaliado.
_TERMOS_FINANCEIROS = (
    "Payback",
    "EBITDA",
    "Aluguel-teto",
    "Aluguel pedido",
    "Valor de venda",
    "Faturamento",
    "DRE",
)


def _point_app_at(monkeypatch: pytest.MonkeyPatch, data_dir: Path) -> None:
    outputs = data_dir / "outputs"
    monkeypatch.setattr(pilot, "DATA_DIR", data_dir)
    monkeypatch.setattr(pilot, "OUTPUTS_DIR", outputs)
    monkeypatch.setattr(pilot, "STAGING_DIR", data_dir / "staging")
    monkeypatch.setattr(pilot, "IBGE_DIR", data_dir / "ibge")
    monkeypatch.setattr(pilot, "ULTRA_DIR", data_dir / "ultra")
    monkeypatch.setattr(pilot, "CENSO_GEO_DIR", outputs / "setores_censitarios_2022_geo")


_PRACA_SENTINELA = object()


@pytest.fixture
def rota_stub(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Colaboradores pesados viram stubs; o GERADOR fica real (cada teste decide)."""
    (tmp_path / "outputs" / "setores_censitarios_2022_geo").mkdir(parents=True)
    _point_app_at(monkeypatch, tmp_path)

    from motor_expansao.api import service as api_service
    from motor_expansao.dashboard import censo_map, censo_point

    setores = pd.DataFrame({"cod_setor": ["355030801000001"], "nome_municipio": ["SAO PAULO"]})
    monkeypatch.setattr(
        api_service, "_resolver_e_carregar", lambda lat, lng, cfg: ("SP", "3550308", setores)
    )
    monkeypatch.setattr(api_service, "_competitors_ultra", lambda cfg: (None, None))
    monkeypatch.setattr(api_service, "_nome_municipio_de", lambda df: "SAO PAULO")
    monkeypatch.setattr(
        api_service, "_mercado_do_ponto", lambda lat, lng, cfg, pop, **k: dict(_MERCADO)
    )
    monkeypatch.setattr(
        censo_point, "analisar_ponto_censitario_setores", lambda *a, **k: dict(_RESULT)
    )
    monkeypatch.setattr(censo_point, "agregar_perfil_bairro_distrito", lambda *a, **k: None)
    monkeypatch.setattr(censo_map, "render_mapas_censitarios_combinados", lambda *a, **k: None)
    monkeypatch.setattr(censo_map, "render_foto_satelite_ponto", lambda *a, **k: None)
    monkeypatch.setattr(censo_map, "_BASEMAP_CACHE_DIR", censo_map._BASEMAP_CACHE_DIR)


@pytest.fixture
def gerador_espiao(rota_stub, monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    from motor_expansao.dashboard import censo_report

    # A praca e' montada pela propria rota; aqui ela devolve uma sentinela para o teste
    # poder afirmar que o modo Estudo a ENTREGA ao gerador (as paginas da praca ficam).
    monkeypatch.setattr(pilot, "_praca_para_pdf", lambda *a, **k: _PRACA_SENTINELA)
    visto: dict[str, object] = {}

    def _fake_gerar(result, mapas, **kwargs):
        visto["result"] = result
        visto.update(kwargs)
        return b"%PDF-1.4 stub"

    monkeypatch.setattr(censo_report, "gerar_pdf_relatorio_pontual_classico", _fake_gerar)
    return visto


def _chamar_rota(**kwargs):
    return asyncio.run(pilot.relatorio_pontual(lat=_LAT, lng=_LNG, **kwargs))


# --------------------------------------------------------------------------- #
# 1) O que a rota entrega ao gerador                                           #
# --------------------------------------------------------------------------- #
def test_so_estudo_liga_a_conclusao_demografica_sem_viabilidade(gerador_espiao) -> None:
    _chamar_rota(rotulo="Santana", so_estudo=True)
    assert gerador_espiao["conclusao_so_estudo"] is True
    assert gerador_espiao["viabilidade"] is None
    # As paginas da praca NAO sao financeiras e ficam no Estudo.
    assert gerador_espiao["praca"] is _PRACA_SENTINELA


def test_so_estudo_descarta_viabilidade_e_imovel_mesmo_que_o_cliente_mande(gerador_espiao) -> None:
    """Cinto de seguranca: o modo existe para NAO sair dado financeiro."""
    _chamar_rota(
        so_estudo=True,
        viabilidade_json=json.dumps(_VIAB),
        viabilidade_inputs_json=json.dumps({"lat": _LAT, "lng": _LNG, "m2": 1500}),
        info_imovel=json.dumps(_INFO_IMOVEL),
    )
    assert gerador_espiao["viabilidade"] is None
    assert gerador_espiao["info_imovel"] is None
    assert gerador_espiao["conclusao_so_estudo"] is True


def test_sem_so_estudo_o_comportamento_e_o_de_antes(gerador_espiao) -> None:
    _chamar_rota(viabilidade_json=json.dumps(_VIAB), info_imovel=json.dumps(_INFO_IMOVEL))
    assert gerador_espiao["conclusao_so_estudo"] is False
    assert gerador_espiao["viabilidade"] == _VIAB
    assert gerador_espiao["info_imovel"] == _INFO_IMOVEL


def test_o_pdf_recebe_o_mercado_do_raio(gerador_espiao) -> None:
    """DEC-070: o `residual` do gerador e' o dict de `_mercado_do_ponto` (raio), nao o hex."""
    _chamar_rota(so_estudo=True)
    assert gerador_espiao["residual"]["grao"] == "raio"
    assert gerador_espiao["residual"]["oferta_consumida_ultra_estimada"] == 300.0


def test_nome_do_query_param_e_o_mesmo_que_o_front_envia() -> None:
    api_ts = _REPO / "web" / "src" / "lib" / "api.ts"
    if not api_ts.is_file():
        pytest.skip("piloto web (web/src) ausente nesta arvore")
    assert "so_estudo" in inspect.signature(pilot.relatorio_pontual).parameters
    assert "q.set('so_estudo', 'true')" in api_ts.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# 2) PDF de verdade                                                            #
# --------------------------------------------------------------------------- #
pytest.importorskip(
    "h3",
    reason="censo_report importa h3; sem o binario nativo so o CI roda",
    exc_type=ImportError,
)


def _texto(pdf: bytes) -> str:
    return pdf.decode("latin-1", errors="replace")


@pytest.fixture
def gerador_real(rota_stub, monkeypatch: pytest.MonkeyPatch) -> None:
    # Sem praca (montar `PracaDoPonto` de verdade exige a cidade inteira); a entrega dela
    # ao gerador e' coberta pelo espiao acima.
    monkeypatch.setattr(pilot, "_praca_para_pdf", lambda *a, **k: None)


def test_pdf_do_estudo_nao_tem_nenhum_termo_financeiro(gerador_real) -> None:
    resp = _chamar_rota(
        so_estudo=True,
        viabilidade_json=json.dumps(_VIAB),
        info_imovel=json.dumps(_INFO_IMOVEL),
    )
    texto = _texto(resp.body)
    assert texto.startswith("%PDF")
    for termo in _TERMOS_FINANCEIROS:
        assert termo not in texto, f"o PDF do Estudo vazou dado financeiro: {termo!r}"
    # A Conclusao sai (selo demografico), com a nota do modo so-estudo.
    assert "Conclus" in texto
    assert "ESTUDO" in texto


def test_controle_o_mesmo_pedido_sem_so_estudo_tem_os_termos(gerador_real) -> None:
    """Sem este controle a varredura acima poderia estar cega (texto comprimido, outra
    codificacao) e o teste passaria verde por construcao."""
    resp = _chamar_rota(viabilidade_json=json.dumps(_VIAB), info_imovel=json.dumps(_INFO_IMOVEL))
    texto = _texto(resp.body)
    assert "Payback" in texto
    assert "EBITDA" in texto
    assert "Aluguel pedido" in texto


def test_sem_viabilidade_e_sem_so_estudo_continua_sem_conclusao(gerador_real) -> None:
    """Comportamento historico do piloto: operador nao preencheu a Viabilidade e nao pediu
    o Estudo -> PDF sem pagina de Conclusao (o flag segue opt-in)."""
    texto = _texto(_chamar_rota().body)
    assert "ESTUDO" not in texto


def test_big_numbers_do_estudo_fecham_a_conta_do_raio(gerador_real) -> None:
    """DEC-070: card de consumo INSTALADO com a decomposicao conc. + Ultra."""
    texto = _texto(_chamar_rota(so_estudo=True).body)
    assert "Mercado ocupado" in texto
    assert "conc. 1.200 + Ultra 300" in texto
