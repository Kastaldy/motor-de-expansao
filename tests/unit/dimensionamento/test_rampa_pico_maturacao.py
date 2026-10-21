"""Pico de maturacao da rampa (emenda de 21/10/2026 da DEC-077).

Pedido do Vinicius (21/10/2026): "A rampa de maturacao fica exclusivamente como curva
observada, mas deve receber a opcao de selecionar um pico de maturacao". O pico e' o MES
em que a rampa atinge 100% da demanda madura. A MESMA forma observada (BLK-UNI-03) e'
reescalada no tempo:

    fracao(t) = curva_obs(t x 10 / pico), interpolando linearmente entre meses observados;
    t x 10 / pico <= 1 -> a fracao do mes 1; >= 10 -> 100%.

O QUE ESTE ARQUIVO TRAVA
------------------------
1. Pico 10 (o observado, padrao) e' a curva de HOJE byte a byte: os digests da serie e do
   payload foram MEDIDOS no codigo anterior a emenda (`git archive` de 0a73981d) e sao
   reproduzidos aqui — a unica diferenca no payload e' a chave nova `mes_pico_rampa`.
2. Pico 6 e 18 conferidos a mao em meses escolhidos (a conta esta no comentario).
3. Para TODA opcao: monotonica, (0, 1], o fim da rampa (primeiro mes com 100%) e' o pico,
   e o mes de steady e' max(pico, mes da anuidade).
4. Contrato: `mes_pico_rampa` fora das opcoes -> 422 em portugues (piloto e API publica);
   eco em `premissas`; na reta e' aceito e ignorado (eco null).
5. Planilha com pico != 10: a tabela e o "Mes em que a rampa termina" refletem o pico, e
   recalculada (pacote `formulas`) bate com o motor nos 64 meses.
6. PDF: o rodape diz o pico na curva; na reta, nada.

READ-ONLY sobre o M1.
"""

from __future__ import annotations

import hashlib
import io
import json
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path

import openpyxl
import pytest
from pydantic import ValidationError

from motor_expansao.dimensionamento.config import (
    SIM_CURVA_RAMPA_UNI03,
    SIM_FORMA_RAMPA_CURVA_UNI03,
    SIM_MES_PICO_RAMPA_OBSERVADO,
    SIM_MES_PICO_RAMPA_PADRAO,
    SIM_MESES_PICO_RAMPA,
)
from motor_expansao.dimensionamento.payload_viabilidade import (
    ViabilidadeIn,
    ViabilidadeInputs,
    montar_payload_para_pdf,
    montar_payload_viabilidade,
    premissas_do_body,
)
from motor_expansao.dimensionamento.simulador import (
    Premissas,
    curva_rampa_com_pico,
    simular,
)
from motor_expansao.dimensionamento.simulador_xlsx import ABA_PREMISSAS, gerar_simulador_xlsx
from tests.unit.dimensionamento.test_rampa_curva_uni03 import (
    _divergencias,
    _linha_premissa,
    _recalcular,
)

DEMANDA = 2304.0
INVEST: dict[str, float | int] = {
    "obra": 600_000.0,
    "parcelas_obra": 4,
    "equipamentos": 1_400_000.0,
    "prazo_equipamentos": 60,
    "juros_equipamentos_am": 0.018,
    "taxa_franquia": 160_000.0,
}
GOLDEN_BODY = dict(
    lat=-23.33, lng=-51.16, m2=1500, aluguel=30000, demanda=2304, ticket=147,
    obra=600000, equipamentos=1400000, prazo_equipamentos=60,
    juros_equipamentos_am=0.018, parcelas_obra=4,
)

# MEDIDOS no codigo ANTERIOR a emenda (`git archive 0a73981d`, PYTHONPATH no arquivo), com
# a curva escolhida explicitamente — a "curva de hoje". Nunca refazer contra o codigo novo
# (o teste viraria circular).
SERIE_CURVA_ANTES = {
    "golden": "75528dc1c1cc6b0d1936f14680b788b11d7d5a0648a72551c063be6fb3209c89",
    "studios": "d7e73e38bc499642ed06ee14198aa46fa6b6a443e912c0f200127d908445e3c1",
}
# Payload do golden com a curva, staging vazio (o mesmo de `DIGEST_ANTES_DA_EMENDA["curva"]`
# em test_viabilidade_v2.py, medido em bf250f46 e igual em 0a73981d).
PAYLOAD_CURVA_ANTES = "16c84f0715c73486bdb9108d2ebe84948106cfffc27241c633e737229b7c3785"


def _digest_serie(serie: list[dict]) -> str:
    return hashlib.sha256(json.dumps(serie, sort_keys=True, default=repr).encode()).hexdigest()


def _digest_payload(p: dict) -> str:
    return hashlib.sha256(json.dumps(p, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _payload(body: ViabilidadeIn) -> dict:
    with tempfile.TemporaryDirectory() as d:
        return montar_payload_viabilidade(body, staging_dir=d, setores_df=None)


def _premissas_pico(pico: int, **over: object) -> Premissas:
    kw: dict[str, object] = {
        "ticket_cheio": 147.0,
        "aluguel_mes": 30_000.0,
        "maturacao_meses": 8,
        "carencia_aluguel_meses": 0,
        "forma_rampa": SIM_FORMA_RAMPA_CURVA_UNI03,
        "curva_rampa": curva_rampa_com_pico(pico),
    }
    kw.update(over)
    return Premissas(**kw)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 1. Constantes e pico 10 = a curva de hoje, byte a byte
# ---------------------------------------------------------------------------


def test_opcoes_e_padrao_do_pico() -> None:
    assert SIM_MESES_PICO_RAMPA == (6, 8, 10, 12, 15, 18, 24)
    # o observado e' DERIVADO da curva (primeiro mes com 100%), nao cravado
    assert SIM_MES_PICO_RAMPA_OBSERVADO == 10
    assert SIM_MES_PICO_RAMPA_PADRAO == SIM_MES_PICO_RAMPA_OBSERVADO
    assert SIM_MES_PICO_RAMPA_PADRAO in SIM_MESES_PICO_RAMPA


def test_pico_observado_devolve_a_curva_intacta() -> None:
    assert curva_rampa_com_pico(10) is SIM_CURVA_RAMPA_UNI03


def test_pico_10_e_a_serie_da_curva_de_hoje_byte_a_byte() -> None:
    golden = simular(DEMANDA, _premissas_pico(10), **INVEST)  # type: ignore[arg-type]
    assert _digest_serie(golden.serie_mensal) == SERIE_CURVA_ANTES["golden"]
    studios = simular(
        DEMANDA,
        Premissas(ticket_cheio=147.0, aluguel_mes=30_000.0, tickets_studios=(120.0, 90.0),
                  forma_rampa=SIM_FORMA_RAMPA_CURVA_UNI03, curva_rampa=curva_rampa_com_pico(10)),
        **INVEST,  # type: ignore[arg-type]
    )
    assert _digest_serie(studios.serie_mensal) == SERIE_CURVA_ANTES["studios"]


@pytest.mark.parametrize("extra", [{}, {"mes_pico_rampa": 10}, {"forma_rampa": "curva_uni03"}])
def test_pico_10_e_o_payload_da_curva_de_hoje_mais_a_chave_nova(extra: dict) -> None:
    """Sem pico, com pico 10 e com a curva escolhida: o MESMO payload, que e' o da curva
    de antes da emenda acrescido so' de `premissas.mes_pico_rampa = 10`."""
    p = _payload(ViabilidadeIn(**GOLDEN_BODY, **extra))
    assert p["premissas"].pop("mes_pico_rampa") == 10
    assert _digest_payload(p) == PAYLOAD_CURVA_ANTES


def test_pico_10_monta_as_mesmas_premissas_da_curva_de_hoje() -> None:
    hoje = Premissas(ticket_cheio=147.0, aluguel_mes=30_000.0, tickets_studios=(),
                     forma_rampa=SIM_FORMA_RAMPA_CURVA_UNI03)
    assert premissas_do_body(ViabilidadeIn(**GOLDEN_BODY, mes_pico_rampa=10)) == hoje
    assert premissas_do_body(ViabilidadeIn(**GOLDEN_BODY)) == hoje


# ---------------------------------------------------------------------------
# 2. Reescalonamento conferido a mao
# ---------------------------------------------------------------------------


def test_pico_6_conferido_a_mao() -> None:
    """s = t x 10 / 6. Curva observada (meses 1..10): .68 .77 .84 .88 .90 .92 .97 .97 .99 1.
    t=1: s=1,667 -> .68 + (2/3)(.77-.68) = .74
    t=2: s=3,333 -> .84 + (1/3)(.88-.84) = .853333
    t=3: s=5     -> .90 (mes observado exato)
    t=5: s=8,333 -> .97 + (1/3)(.99-.97) = .976667
    t=6: s=10    -> 1,0 (o pico)."""
    c = curva_rampa_com_pico(6)
    assert c[0] == pytest.approx(0.74, abs=1e-12)
    assert c[1] == pytest.approx(0.853333, abs=1e-12)
    assert c[2] == pytest.approx(0.90, abs=1e-12)
    assert c[4] == pytest.approx(0.976667, abs=1e-12)
    assert c[5] == 1.0
    assert len(c) == 8  # o pico + os 2 meses cheios de cauda da observada


def test_pico_18_conferido_a_mao() -> None:
    """s = t x 10 / 18.
    t=1:  s=0,556 (<= 1) -> .68 (a fracao do mes 1)
    t=2:  s=1,111 -> .68 + (1/9)(.77-.68) = .69
    t=9:  s=5     -> .90
    t=17: s=9,444 -> .99 + (4/9)(1-.99) = .994444
    t=18: s=10    -> 1,0."""
    c = curva_rampa_com_pico(18)
    assert c[0] == pytest.approx(0.68, abs=1e-12)
    assert c[1] == pytest.approx(0.69, abs=1e-12)
    assert c[8] == pytest.approx(0.90, abs=1e-12)
    assert c[16] == pytest.approx(0.994444, abs=1e-12)
    assert c[17] == 1.0
    assert len(c) == 20


@pytest.mark.parametrize("pico", SIM_MESES_PICO_RAMPA)
def test_toda_opcao_e_monotonica_e_fecha_no_pico(pico: int) -> None:
    c = curva_rampa_com_pico(pico)
    assert all(0.0 < f <= 1.0 for f in c)
    assert all(b >= a for a, b in zip(c, c[1:], strict=False))
    assert next(i for i, f in enumerate(c, start=1) if f >= 1.0) == pico
    p = _premissas_pico(pico)  # o nucleo aceita (recusa curva que decresce)
    assert p.mes_maturidade_rampa == pico
    r = simular(DEMANDA, p, **INVEST)  # type: ignore[arg-type]
    # steady = max(pico, mes da anuidade = 12)
    assert r.mes_referencia_steady == max(pico, 12)
    op = [linha for linha in r.serie_mensal if linha["fase"] == "operacao"]
    for linha in op:
        t = int(linha["mes"])
        frac = c[t - 1] if t <= len(c) else 1.0
        assert linha["alunos_total"] == pytest.approx(DEMANDA * frac, abs=1e-9), (pico, t)


def test_pico_mais_lento_paga_mais_tarde() -> None:
    """Sanidade de sentido: mais meses ate' o pico = menos alunos no 1o ano = payback
    igual ou maior. Nao e' numero da DEC; e' a direcao que o operador espera."""
    paybacks = [
        simular(DEMANDA, _premissas_pico(m), **INVEST).payback_meses  # type: ignore[arg-type]
        for m in SIM_MESES_PICO_RAMPA
    ]
    assert paybacks == sorted(paybacks)


# Numeros da tabela da emenda na DEC-077 (golden de Londrina), medidos rodando o motor:
# pico -> (alunos no mes 1, payback, TIR do socio a.a., mes de steady).
EMENDA_PICO: dict[int, tuple[float, float, float, int]] = {
    6: (1704.96, 23.0, 0.6279, 12),
    8: (1618.56, 24.0, 0.5930, 12),
    10: (1566.72, 25.0, 0.5630, 12),
    12: (1566.72, 26.0, 0.5352, 12),
    15: (1566.72, 27.0, 0.4980, 15),
    18: (1566.72, 28.0, 0.4638, 18),
    24: (1566.72, 31.0, 0.4046, 24),
}


@pytest.mark.parametrize("pico", sorted(EMENDA_PICO))
def test_numeros_da_emenda_no_golden(pico: int) -> None:
    alunos_m1, payback, tir, steady = EMENDA_PICO[pico]
    r = simular(DEMANDA, _premissas_pico(pico), **INVEST)  # type: ignore[arg-type]
    op = [linha for linha in r.serie_mensal if linha["fase"] == "operacao"]
    assert op[0]["alunos_total"] == pytest.approx(alunos_m1, abs=0.01)
    assert r.payback_meses == payback
    assert r.tir_socio_anual == pytest.approx(tir, abs=0.00005)
    assert r.mes_referencia_steady == steady


def test_pico_invalido_no_nucleo() -> None:
    with pytest.raises(ValueError, match="mes_pico"):
        curva_rampa_com_pico(0)


# ---------------------------------------------------------------------------
# 3. Contrato: 422, eco, reta
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("pico", [0, 7, 9, 36])
def test_pico_fora_das_opcoes_e_recusado_em_portugues(pico: int) -> None:
    for modelo in (ViabilidadeInputs, ViabilidadeIn):
        kw: dict[str, object] = {"m2": 1500, "aluguel": 30000, "demanda": 1600}
        if modelo is ViabilidadeIn:
            kw.update(lat=-23.5, lng=-46.6)
        with pytest.raises(ValidationError) as exc:
            modelo(**kw, mes_pico_rampa=pico)
        msg = str(exc.value)
        assert "mes_pico_rampa fora das opções" in msg
        assert "6, 8, 10, 12, 15, 18 ou 24 meses" in msg


def test_api_publica_devolve_422_com_pico_fora_das_opcoes() -> None:
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from motor_expansao.api.main import create_app

    corpo = {
        "lat": -23.55,
        "lng": -46.63,
        "viabilidade": {"m2": 1500, "aluguel": 30000, "demanda": 1600, "mes_pico_rampa": 7},
    }
    resp = TestClient(create_app()).post(
        "/api/v1/analisar", json=corpo, headers={"Authorization": "Bearer dev-token"}
    )
    assert resp.status_code == 422
    assert "mes_pico_rampa fora das opções" in resp.text


def test_payload_ecoa_o_pico_e_a_curva_reescalada() -> None:
    p = _payload(ViabilidadeIn(**GOLDEN_BODY, mes_pico_rampa=18))["premissas"]
    assert p["forma_rampa"] == "curva_uni03"
    assert p["mes_pico_rampa"] == 18
    assert p["mes_maturidade_rampa"] == 18
    assert p["curva_rampa"] == [round(f, 4) for f in curva_rampa_com_pico(18)]
    assert p["mes_referencia_steady"] == 18  # max(pico 18, anuidade no mes 12)


def test_na_reta_o_pico_e_aceito_e_ignorado() -> None:
    """A API publica segue aceitando a reta; nela o pico nao vale (eco null), como
    `rampa_meses` na curva."""
    com = _payload(ViabilidadeIn(**GOLDEN_BODY, forma_rampa="reta", mes_pico_rampa=18))
    sem = _payload(ViabilidadeIn(**GOLDEN_BODY, forma_rampa="reta"))
    assert com == sem
    assert com["premissas"]["mes_pico_rampa"] is None
    assert com["premissas"]["mes_maturidade_rampa"] == 8


# ---------------------------------------------------------------------------
# 4. Planilha com pico != 10
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def blob_pico_18() -> bytes:
    return gerar_simulador_xlsx(DEMANDA, _premissas_pico(18), nome_ponto="Pico 18", **INVEST)


def test_xlsx_reflete_o_pico(blob_pico_18: bytes) -> None:
    ws = openpyxl.load_workbook(BytesIO(blob_pico_18))[ABA_PREMISSAS]
    textos = [str(c.value) for linha in ws.iter_rows() for c in linha if isinstance(c.value, str)]
    assert "Curva observada da rampa (% da demanda madura; pico no mês 18)" in textos
    curva = curva_rampa_com_pico(18)
    for i, f in enumerate(curva, start=1):
        assert ws.cell(row=_linha_premissa(ws, f"Curva observada — mês {i}"), column=2).value == f
    with pytest.raises(AssertionError):
        _linha_premissa(ws, f"Curva observada — mês {len(curva) + 1}")


def test_xlsx_pico_18_recalculada_bate_com_o_motor(blob_pico_18: bytes, tmp_path: Path) -> None:
    ler = _recalcular(blob_pico_18, tmp_path)
    r = simular(DEMANDA, _premissas_pico(18), **INVEST)  # type: ignore[arg-type]
    assert _divergencias(ler, r) == []
    ws = openpyxl.load_workbook(BytesIO(blob_pico_18))[ABA_PREMISSAS]
    assert ler(ABA_PREMISSAS, f"B{_linha_premissa(ws, 'Mês em que a rampa termina')}") == 18.0


def _membros(blob: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        return {n: z.read(n) for n in z.namelist() if n != "docProps/core.xml"}


def test_xlsx_pico_10_e_a_planilha_da_curva_de_hoje() -> None:
    """Pela rota (corpo -> Premissas) com pico 10 e pela curva escolhida direto no nucleo:
    o MESMO arquivo membro a membro (so' a data de criacao do docProps varia)."""
    pelo_corpo = premissas_do_body(ViabilidadeIn(**GOLDEN_BODY, mes_pico_rampa=10))
    hoje = Premissas(ticket_cheio=147.0, aluguel_mes=30_000.0, tickets_studios=(),
                     forma_rampa=SIM_FORMA_RAMPA_CURVA_UNI03)
    a = gerar_simulador_xlsx(DEMANDA, pelo_corpo, nome_ponto="x", **INVEST)
    b = gerar_simulador_xlsx(DEMANDA, hoje, nome_ponto="x", **INVEST)
    assert _membros(a) == _membros(b)
    ws = openpyxl.load_workbook(BytesIO(a))[ABA_PREMISSAS]
    textos = [str(c.value) for linha in ws.iter_rows() for c in linha if isinstance(c.value, str)]
    assert "Curva observada da rampa (% da demanda madura)" in textos
    assert not any("pico no mês" in t for t in textos)


# ---------------------------------------------------------------------------
# 5. PDF
# ---------------------------------------------------------------------------


def _texto_pdf(payload: dict) -> str:
    import pypdf

    from motor_expansao.dashboard.censo_report import gerar_pdf_relatorio_pontual_classico

    resultado = {"lat": -23.33, "lng": -51.16, "nome_municipio": "LONDRINA", "uf": "PR",
                 "raio_km": 1.0}
    pdf = gerar_pdf_relatorio_pontual_classico(resultado, None, viabilidade=payload)
    return " ".join(
        " ".join((p.extract_text() or "").split()) for p in pypdf.PdfReader(io.BytesIO(pdf)).pages
    )


def test_pdf_diz_o_pico_na_curva_e_nada_na_reta(tmp_path: Path) -> None:
    curva = _texto_pdf(montar_payload_para_pdf(
        ViabilidadeIn(**GOLDEN_BODY, mes_pico_rampa=15), staging_dir=tmp_path))
    assert "Rampa: curva observada, pico de maturação no mês 15." in curva
    padrao = _texto_pdf(montar_payload_para_pdf(ViabilidadeIn(**GOLDEN_BODY), staging_dir=tmp_path))
    assert "Rampa: curva observada, pico de maturação no mês 10." in padrao
    reta = _texto_pdf(montar_payload_para_pdf(
        ViabilidadeIn(**GOLDEN_BODY, forma_rampa="reta"), staging_dir=tmp_path))
    assert "pico de maturação" not in reta
    for texto in (curva, padrao, reta):
        assert "provisória" not in texto.lower()
