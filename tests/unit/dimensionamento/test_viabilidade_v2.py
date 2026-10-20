"""Viabilidade v2 (DEC-075 ampliada): carregador, modelo, conversao, token, c10 e payload.

Os coeficientes daqui sao FICTICIOS (`COEF_FICTICIO`), gravados num `tmp_path`: nunca no
lugar do arquivo real (`dimensionamento/v2_coeficientes.json`, que chega pelo Felipe). O
teste de ACEITACAO com o JSON real fica no fim, marcado `skip` enquanto ele nao existir.
"""

from __future__ import annotations

import hashlib
import json
import math
import tempfile
from pathlib import Path

import pandas as pd
import pytest
from pydantic import ValidationError
from shapely import to_wkb
from shapely.geometry import box

from motor_expansao.dimensionamento import viabilidade_v2 as v2
from motor_expansao.dimensionamento.config import SIM_FORMA_RAMPA_CURVA_UNI03, SIM_FORMA_RAMPA_RETA
from motor_expansao.dimensionamento.demanda_v2 import (
    CoeficientesInvalidos,
    EntradasInvalidas,
    EntradasV2,
    converter_em_alunos,
    prever_faturamento_v2,
    sem_agregador,
    token_procedencia,
    validar_coeficientes,
)
from motor_expansao.dimensionamento.entradas_c10 import (
    EntradasC10Indisponiveis,
    agregar_entradas_c10,
)
from motor_expansao.dimensionamento.payload_viabilidade import (
    ViabilidadeIn,
    montar_payload_viabilidade,
    premissas_do_body,
)

COEF_FICTICIO = {
    "versao": "teste-ficticio",
    "fonte": "tests/unit/dimensionamento/test_viabilidade_v2.py (FICTICIO)",
    "data": "2026-10-20",
    "beta": {
        "intercepto": 3.025,
        "ln_m2": 0.5,
        "ln_renda_dom_c10": 0.4,
        "ln_pop_c10": 0.2,
        "studios": 0.227,
    },
    "xtx_inv": [[0.05 if i == j else 0.0 for j in range(5)] for i in range(5)],
    "sigma": 0.25,
    "cal_2026": math.log(0.98),
    "envelope": {
        "ln_m2": [math.log(880), math.log(2500)],
        "ln_renda_dom_c10": [math.log(2000), math.log(15000)],
        "ln_pop_c10": [math.log(50000), math.log(1_500_000)],
    },
    "faixa": {"p10": 0.63, "p90": 1.58, "provisoria": True},
    "sha256_insumos": {"fato_unidade_mes.parquet": "a" * 64},
}

ENTRADAS = EntradasV2(m2=1500, studios=0, pop_c10=300_000, dom_c10=100_000, renda_pc_c10=1_800)
GOLDEN = dict(
    lat=-23.33, lng=-51.16, m2=1500, aluguel=30000, demanda=2304, ticket=147,
    obra=600000, equipamentos=1400000, prazo_equipamentos=60,
    juros_equipamentos_am=0.018, parcelas_obra=4,
)


def _gravar(tmp_path: Path, dados) -> Path:
    p = tmp_path / "v2_coeficientes.json"
    p.write_text(dados if isinstance(dados, str) else json.dumps(dados), encoding="utf-8")
    return p


@pytest.fixture
def coef(tmp_path, monkeypatch):
    """Coeficientes FICTICIOS instalados no caminho que o carregador le."""
    monkeypatch.delenv("MOTOR_VIABILIDADE_V2", raising=False)
    caminho = _gravar(tmp_path, COEF_FICTICIO)
    monkeypatch.setattr(v2, "caminho_coeficientes", lambda: caminho)
    v2.limpar_cache()
    yield v2.carregar_coeficientes()
    v2.limpar_cache()


# --------------------------------------------------------------------------- carregador
def test_arquivo_ausente_deixa_a_v2_indisponivel_com_motivo(tmp_path, monkeypatch):
    monkeypatch.delenv("MOTOR_VIABILIDADE_V2", raising=False)
    with pytest.raises(v2.V2Indisponivel, match="ainda não tem coeficientes"):
        v2.carregar_coeficientes(tmp_path / "nao_existe.json")
    estado = v2.estado_v2(True, tmp_path / "nao_existe.json")
    assert estado["disponivel"] is False and "coeficientes" in estado["motivo"]


@pytest.mark.parametrize(
    "estragar, trecho",
    [
        (lambda d: "{nao e json", "ilegível"),
        (lambda d: {**d, "extra": 1}, "desconhecida"),
        (lambda d: {k: v for k, v in d.items() if k != "sigma"}, "sigma"),
        (lambda d: {**d, "beta": {**d["beta"], "mr_M2": 0.1}}, "desconhecida"),
        (lambda d: {**d, "beta": {k: v for k, v in d["beta"].items() if k != "studios"}}, "studios"),
        (lambda d: {**d, "sigma": -1}, "positivo"),
        (lambda d: {**d, "sigma": "0.2"}, "número"),
        (lambda d: {**d, "faixa": {"p10": 1.2, "p90": 1.58, "provisoria": True}}, "faixa.p10"),
        (lambda d: {**d, "faixa": {"p10": 0.6, "p90": 1.58, "provisoria": "sim"}}, "provisoria"),
        (lambda d: {**d, "sha256_insumos": {"x": "abc"}}, "sha256"),
        (lambda d: {**d, "envelope": {**d["envelope"], "ln_m2": [8, 7]}}, "mínimo maior"),
        (lambda d: {**d, "xtx_inv": [[1, 2, 0, 0, 0], [0, 1, 0, 0, 0], [0, 0, 1, 0, 0],
                                     [0, 0, 0, 1, 0], [0, 0, 0, 0, 1]]}, "simétrica"),
        (lambda d: {**d, "data": "20/10/2026"}, "AAAA-MM-DD"),
    ],
)
def test_json_invalido_deixa_a_v2_indisponivel_nunca_erro_500(tmp_path, monkeypatch, estragar, trecho):
    monkeypatch.delenv("MOTOR_VIABILIDADE_V2", raising=False)
    v2.limpar_cache()
    caminho = _gravar(tmp_path, estragar(json.loads(json.dumps(COEF_FICTICIO))))
    with pytest.raises(v2.V2Indisponivel, match=trecho):
        v2.carregar_coeficientes(caminho)
    assert v2.estado_v2(True, caminho)["disponivel"] is False


def test_json_valido_carrega_com_o_sha_do_arquivo(coef):
    bruto = v2.caminho_coeficientes().read_bytes()
    assert coef.sha256 == hashlib.sha256(bruto).hexdigest()
    assert coef.beta_de("studios") == 0.227 and coef.faixa_provisoria is True
    estado = v2.estado_v2(True)
    assert estado == {
        "disponivel": True, "motivo": None, "versao": "teste-ficticio",
        "sha256": coef.sha256, "faixa_provisoria": True,
    }
    assert v2.estado_v2(False)["motivo"] == v2.MOTIVO_SEM_ROTAS


@pytest.mark.parametrize("valor", ["0", "false", "off", "nao", "NAO"])
def test_chave_de_servidor_desliga_a_v2_mesmo_com_coeficientes(coef, monkeypatch, valor):
    monkeypatch.setenv("MOTOR_VIABILIDADE_V2", valor)
    with pytest.raises(v2.V2Indisponivel, match="desligada"):
        v2.carregar_coeficientes()
    assert v2.estado_v2(True)["disponivel"] is False


def test_ausencia_nao_e_memoizada_o_json_que_chega_depois_vale(tmp_path, monkeypatch):
    monkeypatch.delenv("MOTOR_VIABILIDADE_V2", raising=False)
    caminho = tmp_path / "v2_coeficientes.json"
    with pytest.raises(v2.V2Indisponivel):
        v2.carregar_coeficientes(caminho)
    _gravar(tmp_path, COEF_FICTICIO)
    assert v2.carregar_coeficientes(caminho).versao == "teste-ficticio"


# --------------------------------------------------------------------------- modelo
def test_p50_e_exp_de_x_beta_mais_cal_sem_o_deslocamento_de_6pct(coef):
    prev = prever_faturamento_v2(ENTRADAS, coef)
    b = COEF_FICTICIO["beta"]
    renda_dom = 1_800 * 300_000 / 100_000
    eta = (b["intercepto"] + b["ln_m2"] * math.log(1500) + b["ln_renda_dom_c10"] * math.log(renda_dom)
           + b["ln_pop_c10"] * math.log(300_000))
    esperado = math.exp(eta + math.log(0.98))
    assert prev.fat_p50 == pytest.approx(esperado, rel=1e-12)
    assert prev.fat_p10 == pytest.approx(0.63 * esperado, rel=1e-12)
    assert prev.fat_p90 == pytest.approx(1.58 * esperado, rel=1e-12)
    assert prev.faixa_provisoria is True and prev.flag_extrapolacao is False


def test_estudio_e_binario_e_soma_o_beta_em_log(coef):
    sem = prever_faturamento_v2(ENTRADAS, coef).fat_p50
    com = prever_faturamento_v2(EntradasV2(**{**ENTRADAS.__dict__, "studios": 1}), coef).fat_p50
    assert com / sem == pytest.approx(math.exp(0.227), rel=1e-12)
    with pytest.raises(EntradasInvalidas):
        prever_faturamento_v2(EntradasV2(**{**ENTRADAS.__dict__, "studios": 2}), coef)


def test_renda_domiciliar_e_per_capita_vezes_pessoas_sobre_domicilios(coef):
    """Mutacao: usar a per capita direto (ou a renda do relatorio) muda o p50."""
    assert ENTRADAS.renda_dom_c10 == pytest.approx(5_400.0)
    menos_dom = EntradasV2(**{**ENTRADAS.__dict__, "dom_c10": 50_000})
    razao = prever_faturamento_v2(menos_dom, coef).fat_p50 / prever_faturamento_v2(ENTRADAS, coef).fat_p50
    assert razao == pytest.approx(2.0**0.4, rel=1e-12)


def test_flag_de_extrapolacao_na_borda_do_envelope(coef):
    na_borda = EntradasV2(**{**ENTRADAS.__dict__, "m2": 880.0})
    assert prever_faturamento_v2(na_borda, coef).flag_extrapolacao is False
    fora = EntradasV2(**{**ENTRADAS.__dict__, "m2": 879.0})
    prev = prever_faturamento_v2(fora, coef)
    assert prev.flag_extrapolacao is True and prev.fora_do_envelope == ("ln_m2",)
    fora2 = EntradasV2(**{**ENTRADAS.__dict__, "pop_c10": 2_000_000, "dom_c10": 2_000_000 / 3})
    assert prever_faturamento_v2(fora2, coef).fora_do_envelope == ("ln_pop_c10",)


def test_entrada_nao_positiva_nao_entra_no_log(coef):
    for campo in ("m2", "pop_c10", "dom_c10", "renda_pc_c10"):
        with pytest.raises(EntradasInvalidas):
            prever_faturamento_v2(EntradasV2(**{**ENTRADAS.__dict__, campo: 0.0}), coef)


def test_erro_padrao_usa_sigma_e_a_alavanca(coef):
    prev = prever_faturamento_v2(ENTRADAS, coef)
    x = [1.0, *prev.ln_x.values(), 0.0]
    assert prev.ep_log == pytest.approx(0.25 * math.sqrt(1 + 0.05 * sum(v * v for v in x)))


# --------------------------------------------------------------------------- conversao
def _premissas(**kw):
    return premissas_do_body(ViabilidadeIn(**{**GOLDEN, **kw}))


@pytest.mark.parametrize("n_studios", [0, 1, 2])
def test_conversao_volta_ao_faturamento_previsto_com_0_1_2_estudios(n_studios):
    p = _premissas(n_studios=n_studios)
    conv = converter_em_alunos(200_000, 300_000, 450_000, p)
    assert conv.fixo == pytest.approx(p.faturamento_maduro(0))
    for fat, alunos in ((200_000, conv.alunos_p10), (300_000, conv.alunos_p50), (450_000, conv.alunos_p90)):
        assert p.faturamento_maduro(alunos) == pytest.approx(fat, rel=1e-12)


def test_trocar_o_ticket_depois_da_semente_fixa_o_faturamento_e_move_os_alunos():
    """Decisao declarada (critica A2): o FATURAMENTO previsto fica; os alunos sao refeitos."""
    barato = converter_em_alunos(1, 300_000, 1, _premissas(ticket=137))
    caro = converter_em_alunos(1, 300_000, 1, _premissas(ticket=167))
    assert caro.alunos_p50 < barato.alunos_p50
    assert _premissas(ticket=167).faturamento_maduro(caro.alunos_p50) == pytest.approx(300_000)


def test_segundo_estudio_nao_muda_o_faturamento_previsto_e_custa_mais(coef):
    """Efeito declarado: `studios` e' binario no modelo, o custo e' por estudio (DEC-068)."""
    corpo = dict(lat=-23.33, lng=-51.16, m2=1500)
    um = v2.montar_sugestao_v2(v2.DemandaV2In(**corpo, n_studios=1), pop_c10=3e5, dom_c10=1e5,
                               renda_pc_c10=1800, coef=coef)
    dois = v2.montar_sugestao_v2(v2.DemandaV2In(**corpo, n_studios=2), pop_c10=3e5, dom_c10=1e5,
                                 renda_pc_c10=1800, coef=coef)
    assert um["faturamento"] == dois["faturamento"]
    assert _premissas(n_studios=2).custo_studios_mes - _premissas(n_studios=1).custo_studios_mes == 6000


def test_piso_de_um_aluno():
    assert converter_em_alunos(0, 1, 0, _premissas()).alunos_p10 == 1.0


# --------------------------------------------------------------------------- token
LONDRINA = dict(lat=-23.33, lng=-51.16)
MANAUS = dict(lat=-3.0, lng=-60.0)


def test_token_e_deterministico_e_muda_com_cada_parte():
    base = token_procedencia(ENTRADAS, "s" * 64, 300_000.0, **LONDRINA)
    assert base == token_procedencia(ENTRADAS, "s" * 64, 300_000.0, **LONDRINA)
    assert base.startswith("v2-")
    variantes = [
        token_procedencia(EntradasV2(**{**ENTRADAS.__dict__, "m2": 1501}), "s" * 64, 300_000.0, **LONDRINA),
        token_procedencia(EntradasV2(**{**ENTRADAS.__dict__, "studios": 1}), "s" * 64, 300_000.0, **LONDRINA),
        token_procedencia(EntradasV2(**{**ENTRADAS.__dict__, "pop_c10": 300_001}), "s" * 64, 300_000.0, **LONDRINA),
        token_procedencia(ENTRADAS, "t" * 64, 300_000.0, **LONDRINA),
        token_procedencia(ENTRADAS, "s" * 64, 300_000.5, **LONDRINA),
        token_procedencia(ENTRADAS, "s" * 64, 300_000.0, **MANAUS),
        token_procedencia(ENTRADAS, "s" * 64, 300_000.0, lat=-23.3301, lng=-51.16),
        token_procedencia(ENTRADAS, "s" * 64, 300_000.0, lat=-23.33, lng=-51.1601),
    ]
    assert base not in variantes and len(set(variantes)) == len(variantes)


def test_token_arredonda_o_ponto_em_5_casas_declaradas():
    from motor_expansao.dimensionamento.demanda_v2 import CASAS_PONTO_TOKEN

    assert CASAS_PONTO_TOKEN == 5
    base = token_procedencia(ENTRADAS, "s" * 64, 300_000.0, **LONDRINA)
    # abaixo da 5a casa (~1 m) e' o MESMO ponto: ida e volta pelo JSON nao muda o hash.
    assert base == token_procedencia(ENTRADAS, "s" * 64, 300_000.0, lat=-23.330001, lng=-51.160002)


# --------------------------------------------------------------------------- c10
def _malha() -> pd.DataFrame:
    """Dois setores quadrados lado a lado; colunas do relatorio com valores absurdos de
    proposito (a v2 NAO pode le-las: sem uplift, sem renda do responsavel)."""
    a = box(-46.62, -23.52, -46.61, -23.51)
    b = box(-46.61, -23.52, -46.60, -23.51)
    return pd.DataFrame(
        {
            "cod_setor": ["A", "B"],
            "geometry_wkb": [to_wkb(a), to_wkb(b)],
            "flag_geometria_valida": [True, True],
            "pop_total_setor_2022": [1000.0, 3000.0],
            "domicilios_particulares_ocupados_setor_2022": [400.0, 1000.0],
            "renda_per_capita_setor_2022_calibrada": [2000.0, 1000.0],
            "renda_per_capita_setor_2022": [9.0, 9.0],
            "renda_responsavel_media_setor_2022": [1e9, 1e9],
            "avg_moradores_domicilio_setor_2022": [99.0, 99.0],
        }
    )


def test_c10_pondera_pela_area_intersectada_e_renda_pela_populacao():
    # cobre A inteiro e METADE de B
    iso = box(-46.63, -23.53, -46.605, -23.50)
    e = agregar_entradas_c10(_malha(), iso, -23.515, -46.615)
    assert e.n_setores == 2 and e.renda_fonte == "calibrada"
    assert e.pop_c10 == pytest.approx(1000 + 1500, rel=2e-3)
    assert e.dom_c10 == pytest.approx(400 + 500, rel=2e-3)
    pop_b = e.pop_c10 - 1000
    assert e.renda_pc_c10 == pytest.approx((2000 * 1000 + 1000 * pop_b) / (1000 + pop_b), rel=1e-9)
    assert e.renda_dom_c10 == pytest.approx(e.renda_pc_c10 * e.pop_c10 / e.dom_c10)


def test_c10_cai_na_bruta_so_quando_a_calibrada_e_toda_nula():
    malha = _malha()
    malha["renda_per_capita_setor_2022_calibrada"] = float("nan")
    e = agregar_entradas_c10(malha, box(-46.63, -23.53, -46.59, -23.50), -23.515, -46.615)
    assert e.renda_fonte == "bruta" and e.renda_pc_c10 == pytest.approx(9.0)


def test_c10_sem_setor_na_area_ou_sem_domicilio_e_indisponivel():
    with pytest.raises(EntradasC10Indisponiveis, match="Nenhum setor"):
        agregar_entradas_c10(_malha(), box(-40, -20, -39.9, -19.9), -19.95, -39.95)
    malha = _malha()
    malha["domicilios_particulares_ocupados_setor_2022"] = 0.0
    with pytest.raises(EntradasC10Indisponiveis, match="domicílios"):
        agregar_entradas_c10(malha, box(-46.63, -23.53, -46.59, -23.50), -23.515, -46.615)
    with pytest.raises(EntradasC10Indisponiveis):
        agregar_entradas_c10(None, box(-46.63, -23.53, -46.59, -23.50), -23.515, -46.615)


# --------------------------------------------------------------------------- payload
def _sugestao(coef, **kw):
    corpo = v2.DemandaV2In(lat=GOLDEN["lat"], lng=GOLDEN["lng"], m2=GOLDEN["m2"],
                           ticket=GOLDEN["ticket"], **kw)
    return v2.montar_sugestao_v2(corpo, pop_c10=3e5, dom_c10=1e5, renda_pc_c10=1800, coef=coef)


def _corpo_v2(sug, **kw):
    ref = {k: sug["entradas"][k] for k in ("pop_c10", "dom_c10", "renda_pc_c10")}
    base = {**GOLDEN, "demanda": round(sug["alunos"]["p50"]), "modelo_demanda": "v2",
            "demanda_v2": {"token": sug["token"], **ref}}
    return ViabilidadeIn(**{**base, **kw})


def _payload(body):
    with tempfile.TemporaryDirectory() as d:
        return montar_payload_viabilidade(body, staging_dir=d, setores_df=None)


# Digests do payload do golden com staging VAZIO (deterministico), MEDIDOS no commit
# anterior a esta mudanca (bf250f46) e iguais depois: o modo densidade sai byte a byte.
DIGEST_DENSIDADE = {
    "golden": "c3b87e104db972a9cbf4f627ea8d5c56e42e160a9142eceffcf7dec3549d67d2",
    "studios": "d6006dcc5503855d550f13c006b485976acc8ab39a60291e74231da38ae80e5b",
    "curva": "16c84f0715c73486bdb9108d2ebe84948106cfffc27241c633e737229b7c3785",
}


def _digest(p) -> str:
    return hashlib.sha256(json.dumps(p, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


@pytest.mark.parametrize("modelo", [None, "densidade"])
def test_modo_densidade_e_byte_a_byte_o_de_antes(modelo):
    extra = {} if modelo is None else {"modelo_demanda": modelo}
    assert _digest(_payload(ViabilidadeIn(**GOLDEN, **extra))) == DIGEST_DENSIDADE["golden"]
    studios = {"n_studios": 2, "tickets_studios": [210, 190]}
    assert _digest(_payload(ViabilidadeIn(**GOLDEN, **studios, **extra))) == DIGEST_DENSIDADE["studios"]
    curva = {"forma_rampa": "curva_uni03"}
    assert _digest(_payload(ViabilidadeIn(**GOLDEN, **curva, **extra))) == DIGEST_DENSIDADE["curva"]


def test_modo_v2_carimba_a_demanda_sugerida_e_usa_a_curva(coef):
    sug = _sugestao(coef)
    p = _payload(_corpo_v2(sug))
    assert p["demanda_fonte"] == "modelo_v2"
    assert p["premissas"]["forma_rampa"] == SIM_FORMA_RAMPA_CURVA_UNI03
    bloco = p["demanda_v2"]
    assert bloco["token"] == sug["token"] and bloco["faixa_provisoria"] is True
    assert bloco["faturamento"] == sug["faturamento"]
    assert bloco["rampa_reta_forcada_sem_agregador"] is False
    assert p["versao"] == "viabilidade_payload_v1"


def test_demanda_editada_continua_valendo_e_e_carimbada_como_editada(coef):
    sug = _sugestao(coef)
    p = _payload(_corpo_v2(sug, demanda=round(sug["alunos"]["p50"]) + 50))
    assert p["demanda_fonte"] == "premissa_editada"
    assert p["demanda_v2"]["demanda_sugerida"] == sug["alunos"]["p50"]
    assert p["demanda_premissa"] == round(sug["alunos"]["p50"]) + 50


def test_token_de_outra_metragem_nao_confere(coef):
    sug = _sugestao(coef)
    with pytest.raises(v2.TokenV2Invalido):
        _payload(_corpo_v2(sug, m2=1600))
    with pytest.raises(v2.TokenV2Invalido):
        _payload(_corpo_v2(sug, n_studios=1))
    falso = _corpo_v2(sug).demanda_v2.model_copy(update={"pop_c10": 400_000.0})
    with pytest.raises(v2.TokenV2Invalido):
        _payload(_corpo_v2(sug).model_copy(update={"demanda_v2": falso}))


def test_token_de_outro_ponto_nao_confere_londrina_para_manaus(coef):
    """Achado da revisao de 2026-10-20: a sugestao tirada em Londrina era ACEITA numa
    requisicao perto de Manaus e carimbava `modelo_v2`. O ponto agora esta' no token."""
    sug = _sugestao(coef)
    assert sug["ponto"] == {"lat": GOLDEN["lat"], "lng": GOLDEN["lng"]}
    with pytest.raises(v2.TokenV2Invalido, match="ponto"):
        _payload(_corpo_v2(sug, **MANAUS))
    # O mesmo token no ponto certo segue valendo.
    assert _payload(_corpo_v2(sug))["demanda_fonte"] == "modelo_v2"


def test_pdf_com_token_de_outro_ponto_avisa_no_slide_e_nao_sai_calado(coef):
    from motor_expansao.dashboard.censo_report import _viab_linha_demanda_v2, _viab_normalizado
    from motor_expansao.dimensionamento.payload_viabilidade import montar_payload_para_pdf

    sug = _sugestao(coef)
    with tempfile.TemporaryDirectory() as d:
        saida = montar_payload_para_pdf(_corpo_v2(sug, **MANAUS), staging_dir=d, setores_df=None)
    assert saida is not None, "o PDF nao pode perder a pagina de viabilidade"
    assert saida["demanda_v2_aviso"] == "nao_reconhecida"
    assert "demanda_v2" not in saida  # os numeros sao do modo densidade, com a demanda do corpo
    assert saida["demanda_premissa"] == round(sug["alunos"]["p50"])
    linha = _viab_linha_demanda_v2(_viab_normalizado(saida))
    assert linha is not None and "não foi reconhecida" in linha
    linha.encode("latin-1")  # fonte core do fpdf2: nada fora de latin-1


def test_pdf_com_v2_indisponivel_avisa_no_slide(coef, tmp_path, monkeypatch):
    from motor_expansao.dashboard.censo_report import _viab_linha_demanda_v2, _viab_normalizado
    from motor_expansao.dimensionamento.payload_viabilidade import montar_payload_para_pdf

    sug = _sugestao(coef)
    monkeypatch.setattr(v2, "caminho_coeficientes", lambda: tmp_path / "sumiu.json")
    v2.limpar_cache()
    with tempfile.TemporaryDirectory() as d:
        saida = montar_payload_para_pdf(_corpo_v2(sug), staging_dir=d, setores_df=None)
    assert saida is not None and saida["demanda_v2_aviso"] == "indisponivel"
    linha = _viab_linha_demanda_v2(_viab_normalizado(saida))
    assert linha is not None and "indisponível" in linha
    linha.encode("latin-1")


def test_pdf_com_token_valido_nao_carrega_aviso(coef):
    from motor_expansao.dimensionamento.payload_viabilidade import montar_payload_para_pdf

    sug = _sugestao(coef)
    with tempfile.TemporaryDirectory() as d:
        saida = montar_payload_para_pdf(_corpo_v2(sug), staging_dir=d, setores_df=None)
    assert saida is not None and "demanda_v2_aviso" not in saida
    assert saida["demanda_fonte"] == "modelo_v2"


def test_trocar_o_ticket_nao_invalida_o_token(coef):
    sug = _sugestao(coef)
    p = _payload(_corpo_v2(sug, ticket=167))
    assert p["demanda_fonte"] == "premissa_editada"  # o p50 em alunos mudou com o ticket


def test_modo_v2_sem_coeficientes_e_indisponivel(tmp_path, monkeypatch, coef):
    sug = _sugestao(coef)
    monkeypatch.setattr(v2, "caminho_coeficientes", lambda: tmp_path / "sumiu.json")
    with pytest.raises(v2.V2Indisponivel):
        _payload(_corpo_v2(sug))


@pytest.mark.parametrize(
    "share, reta",
    [(1.0, True), (0.999, True), (0.9989, False), (0.69, False)],
)
def test_sem_agregador_forca_a_reta_com_flag_na_borda(coef, share, reta):
    assert sem_agregador(share) is reta
    sug = _sugestao(coef, share_balcao=share)
    p = _payload(_corpo_v2(sug, share_balcao=share))
    esperado = SIM_FORMA_RAMPA_RETA if reta else SIM_FORMA_RAMPA_CURVA_UNI03
    assert p["premissas"]["forma_rampa"] == esperado
    assert p["demanda_v2"]["rampa_reta_forcada_sem_agregador"] is reta


def test_sem_agregador_forca_a_reta_ate_com_a_curva_escolhida(coef):
    sug = _sugestao(coef, share_balcao=1.0)
    p = _payload(_corpo_v2(sug, share_balcao=1.0, forma_rampa="curva_uni03"))
    assert p["premissas"]["forma_rampa"] == SIM_FORMA_RAMPA_RETA


def test_densidade_sem_agregador_nao_e_forcada():
    body = ViabilidadeIn(**GOLDEN, share_balcao=1.0, forma_rampa="curva_uni03")
    assert premissas_do_body(body).forma_rampa == SIM_FORMA_RAMPA_CURVA_UNI03


def test_v2_com_reta_escolhida_respeita_a_escolha(coef):
    sug = _sugestao(coef)
    p = _payload(_corpo_v2(sug, forma_rampa="reta"))
    assert p["premissas"]["forma_rampa"] == SIM_FORMA_RAMPA_RETA
    assert p["demanda_v2"]["rampa_reta_forcada_sem_agregador"] is False


def test_contrato_do_corpo():
    with pytest.raises(ValidationError, match="exige demanda_v2"):
        ViabilidadeIn(**GOLDEN, modelo_demanda="v2")
    ref = {"token": "v2-" + "0" * 64, "pop_c10": 1, "dom_c10": 1, "renda_pc_c10": 1}
    with pytest.raises(ValidationError, match="só vale"):
        ViabilidadeIn(**GOLDEN, demanda_v2=ref)
    with pytest.raises(ValidationError, match="desconhecido"):
        ViabilidadeIn(**GOLDEN, modelo_demanda="masters")
    with pytest.raises(ValidationError):
        ViabilidadeIn(**GOLDEN, modelo_demanda="v2", demanda_v2={**ref, "extra": 1})


# --------------------------------------------------------------------------- aceitacao
def _coeficientes_reais():
    caminho = Path(v2.__file__).with_name("v2_coeficientes.json")
    if not caminho.exists():
        return None
    return validar_coeficientes(json.loads(caminho.read_text("utf-8")), "real")


@pytest.mark.skipif(
    _coeficientes_reais() is None,
    reason="v2_coeficientes.json ainda nao exportado pelo Felipe (DEC-075 ampliada)",
)
def test_aceitacao_reproduz_as_previsoes_da_turma_2026():
    coef = _coeficientes_reais()
    assert coef is not None
    assert coef.aceitacao_turma_2026, "o JSON real tem de trazer as entradas X da turma 2026"
    for u in coef.aceitacao_turma_2026:
        # dom_c10 = 1 e renda_pc = renda_dom/pop: reproduz a renda_dom do X exportado.
        e = EntradasV2(m2=u["m2"], studios=int(u["studios"]), pop_c10=u["pop_c10"], dom_c10=u["pop_c10"],
                       renda_pc_c10=u["renda_dom_c10"])
        assert prever_faturamento_v2(e, coef).fat_p50 == pytest.approx(
            u["fat_previsto_cal2026"], rel=1e-9
        ), u["unidade"]


def test_schema_aceita_o_bloco_de_aceitacao():
    dados = {**COEF_FICTICIO, "aceitacao_turma_2026": [
        {"unidade": "U1", "m2": 1500, "renda_dom_c10": 5400, "pop_c10": 3e5, "studios": 0,
         "fat_previsto_cal2026": 1.0}]}
    assert validar_coeficientes(dados, "x").aceitacao_turma_2026[0]["unidade"] == "U1"
    dados["aceitacao_turma_2026"][0]["studios"] = 2
    with pytest.raises(CoeficientesInvalidos):
        validar_coeficientes(dados, "x")
