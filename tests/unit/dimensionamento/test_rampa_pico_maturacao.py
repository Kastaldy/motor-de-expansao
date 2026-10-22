"""Pico de maturacao da rampa (emenda de 21/10/2026 da DEC-078).

Pedido do Vinicius (21/10/2026): "A rampa de maturacao fica exclusivamente como curva
observada, mas deve receber a opcao de selecionar um pico de maturacao". O pico e' o MES
em que a rampa atinge 100% da demanda madura. A MESMA forma observada (BLK-UNI-03) e'
reescalada no tempo, com os DOIS extremos medidos ancorados (mes 1 = abertura observada,
68%; mes `pico` = 100%):

    fracao(t) = curva_obs(1 + (t - 1) x 9 / (pico - 1)), interpolando linearmente entre
    meses observados; >= 10 -> 100%.

(Revisao de 21/10/2026: a 1a versao, `curva_obs(t x 10 / pico)`, abria o pico 6 em 74% e
deixava o pico 24 parado dois meses em 68% -- a abertura, que e' dado medido, mudava.)

Emenda de 22/10/2026 (MES 0): "a rampa de alunos deve seguir o padrao do estudo, comecando
a valer com valores desde o mes 0". A curva passa a ser indexada por MES DE VIDA, como no
estudo (0 = a inauguracao, 80%), e o mes de vida k e' o mes de OPERACAO k + 1 do simulador.
O pico e' o mes de VIDA com 100%; o fim da rampa do motor (`mes_maturidade_rampa`) e' o
pico + 1. Os meses 0 (80%) e 1 (68%) ficam os medidos em todo pico.

O QUE ESTE ARQUIVO TRAVA
------------------------
1. Pico 10 (o observado, padrao) e' a tabela P1 do estudo desde o mes 0, mes a mes na serie;
   e, do 2o mes de operacao em diante, a curva de 21/10 (sem o mes 0) deslocada de um mes.
2. Pico 6 e 18 conferidos a mao em meses escolhidos (a conta esta no comentario).
3. Para TODA opcao: meses 0 e 1 medidos, monotonica do mes 1 em diante, (0, 1], o 1o mes
   de vida com 100% e' o pico, e o mes de steady e' max(pico + 1, mes da anuidade).
4. Contrato: `mes_pico_rampa` fora de 1..36 -> 422 em portugues (piloto e API publica);
   eco em `premissas`; na reta e' aceito e ignorado (eco null).
5. Planilha com pico != 10: a tabela e o "Mes de operacao em que a rampa termina" refletem o pico, e
   recalculada (pacote `formulas`) bate com o motor nos 64 meses.
6. PDF: o rodape diz o pico na curva; na reta, nada.

READ-ONLY sobre o M1.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
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
    SIM_MES_PICO_RAMPA_MAX,
    SIM_MES_PICO_RAMPA_MIN,
    SIM_MES_PICO_RAMPA_OBSERVADO,
    SIM_MES_PICO_RAMPA_PADRAO,
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

# Tabela P1 do estudo (BLK-UNI-03, alunos, mediana), meses de VIDA 0..12, com as regras da
# DEC-078 escritas A MAO (nao lidas do config): mes 8 = maximo acumulado (97%), teto 100%.
TABELA_P1_DESDE_O_MES_0 = (0.80, 0.68, 0.77, 0.84, 0.88, 0.90, 0.92, 0.97, 0.97, 0.99, 1.0, 1.0, 1.0)
# A curva de 21/10/2026 (sem o mes 0; o mes de operacao t lia o mes de vida t), escrita a mao.
CURVA_SEM_MES_0 = (0.68, 0.77, 0.84, 0.88, 0.90, 0.92, 0.97, 0.97, 0.99, 1.0, 1.0, 1.0)


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


# Todo mes do intervalo do contador "-/+" (22/10/2026): 1..36.
PICOS = tuple(range(SIM_MES_PICO_RAMPA_MIN, SIM_MES_PICO_RAMPA_MAX + 1))


def test_intervalo_e_padrao_do_pico() -> None:
    # o mesmo intervalo do contador da rampa antiga (`rampa_meses`, 1..36)
    assert (SIM_MES_PICO_RAMPA_MIN, SIM_MES_PICO_RAMPA_MAX) == (1, 36)
    # o observado e' DERIVADO da curva (primeiro mes com 100%), nao cravado
    assert SIM_MES_PICO_RAMPA_OBSERVADO == 10
    assert SIM_MES_PICO_RAMPA_PADRAO == SIM_MES_PICO_RAMPA_OBSERVADO
    assert SIM_MES_PICO_RAMPA_MIN <= SIM_MES_PICO_RAMPA_PADRAO <= SIM_MES_PICO_RAMPA_MAX


def test_pico_observado_devolve_a_curva_intacta() -> None:
    assert curva_rampa_com_pico(10) is SIM_CURVA_RAMPA_UNI03


def test_pico_10_e_a_tabela_do_estudo_desde_o_mes_0() -> None:
    """O 1o mes de operacao (a inauguracao) e' o mes 0 do estudo: 80% da demanda madura."""
    assert SIM_CURVA_RAMPA_UNI03 == TABELA_P1_DESDE_O_MES_0
    r = simular(DEMANDA, _premissas_pico(10), **INVEST)  # type: ignore[arg-type]
    op = [linha for linha in r.serie_mensal if linha["fase"] == "operacao"]
    for t, linha in enumerate(op[:14], start=1):
        frac = TABELA_P1_DESDE_O_MES_0[t - 1] if t <= len(TABELA_P1_DESDE_O_MES_0) else 1.0
        assert linha["alunos_total"] == pytest.approx(DEMANDA * frac, abs=1e-9), t
    assert op[0]["alunos_total"] == pytest.approx(1843.2, abs=1e-9)  # 80% de 2.304


@pytest.mark.parametrize("pico", [6, 10, 18])
def test_do_2o_mes_em_diante_e_a_curva_sem_mes_0_deslocada(pico: int) -> None:
    """Conferencia independente do deslocamento: do 2o mes de operacao em diante, os alunos
    sao os da curva de 21/10 (sem o mes 0) um mes mais tarde. Em pico 10, contra a curva
    escrita a mao; nos outros, contra a forma reescalada a partir dela."""
    if pico == 10:
        sem_mes_0 = CURVA_SEM_MES_0
    else:
        sem_mes_0 = curva_rampa_com_pico(pico, (0.80, *CURVA_SEM_MES_0))[1:]
    r = simular(DEMANDA, _premissas_pico(pico), **INVEST)  # type: ignore[arg-type]
    op = [linha for linha in r.serie_mensal if linha["fase"] == "operacao"]
    for t in range(2, 30):
        f = sem_mes_0[t - 2] if t - 2 < len(sem_mes_0) else 1.0
        assert op[t - 1]["alunos_total"] == pytest.approx(DEMANDA * f, abs=1e-9), (pico, t)


@pytest.mark.parametrize("extra", [{}, {"mes_pico_rampa": 10}, {"forma_rampa": "curva_uni03"}])
def test_pico_10_sem_pico_e_curva_escolhida_dao_o_mesmo_payload(extra: dict) -> None:
    """Sem pico, com pico 10 e com a curva escolhida: o MESMO payload. O pico ecoado e' o
    mes de VIDA (10); o fim da rampa servido, o mes de OPERACAO (11)."""
    p = _payload(ViabilidadeIn(**GOLDEN_BODY, **extra))
    assert p["premissas"]["mes_pico_rampa"] == 10
    assert p["premissas"]["mes_maturidade_rampa"] == 11
    assert p["premissas"]["curva_rampa"][:2] == [0.8, 0.68]
    assert _digest_payload(p) == _digest_payload(_payload(ViabilidadeIn(**GOLDEN_BODY)))


def test_pico_10_monta_as_mesmas_premissas_da_curva_de_hoje() -> None:
    hoje = Premissas(ticket_cheio=147.0, aluguel_mes=30_000.0, tickets_studios=(),
                     forma_rampa=SIM_FORMA_RAMPA_CURVA_UNI03)
    assert premissas_do_body(ViabilidadeIn(**GOLDEN_BODY, mes_pico_rampa=10)) == hoje
    assert premissas_do_body(ViabilidadeIn(**GOLDEN_BODY)) == hoje


# ---------------------------------------------------------------------------
# 2. Reescalonamento conferido a mao
# ---------------------------------------------------------------------------


def test_pico_6_conferido_a_mao() -> None:
    """Indice = mes de VIDA. O mes 0 fica 80%; para k >= 1, s = 1 + (k - 1) x 9 / 5 sobre
    a curva observada (meses 1..10): .68 .77 .84 .88 .90 .92 .97 .97 .99 1.
    k=1: s=1   -> .68 (a abertura observada, ancorada)
    k=2: s=2,8 -> .77 + (0,8)(.84-.77) = .826
    k=3: s=4,6 -> .88 + (0,6)(.90-.88) = .892
    k=5: s=8,2 -> .97 + (0,2)(.99-.97) = .974
    k=6: s=10  -> 1,0 (o pico)."""
    c = curva_rampa_com_pico(6)
    assert c[0] == pytest.approx(0.80, abs=1e-12)
    assert c[1] == pytest.approx(0.68, abs=1e-12)
    assert c[2] == pytest.approx(0.826, abs=1e-12)
    assert c[3] == pytest.approx(0.892, abs=1e-12)
    assert c[5] == pytest.approx(0.974, abs=1e-12)
    assert c[6] == 1.0
    assert len(c) == 9  # mes 0 + os meses 1..6 + os 2 meses cheios de cauda da observada


def test_pico_18_conferido_a_mao() -> None:
    """Indice = mes de VIDA; mes 0 = 80%; para k >= 1, s = 1 + (k - 1) x 9 / 17.
    k=1:  s=1        -> .68 (a abertura observada, ancorada)
    k=2:  s=1,529412 -> .68 + (0,529412)(.77-.68) = .727647
    k=9:  s=5,235294 -> .90 + (0,235294)(.92-.90) = .904706
    k=17: s=9,470588 -> .99 + (0,470588)(1-.99)   = .994706
    k=18: s=10       -> 1,0."""
    c = curva_rampa_com_pico(18)
    assert c[0] == pytest.approx(0.80, abs=1e-12)
    assert c[1] == pytest.approx(0.68, abs=1e-12)
    assert c[2] == pytest.approx(0.727647, abs=1e-12)
    assert c[9] == pytest.approx(0.904706, abs=1e-12)
    assert c[17] == pytest.approx(0.994706, abs=1e-12)
    assert c[18] == 1.0
    assert len(c) == 21


@pytest.mark.parametrize("pico", PICOS[1:])
def test_toda_opcao_abre_no_nivel_observado(pico: int) -> None:
    """Os meses 0 e 1 sao DADO MEDIDO (a inauguracao e a abertura da rede): o pico so' move
    o tempo ate' 100%, e nenhum mes fica parado na abertura (o mes 2 ja' sobe). Pico 1 fica
    de fora: do mes 1 em diante a rampa ja' e' cheia (`test_pico_1_abre_cheio`)."""
    c = curva_rampa_com_pico(pico)
    assert c[0] == SIM_CURVA_RAMPA_UNI03[0] == 0.80
    assert c[1] == SIM_CURVA_RAMPA_UNI03[1] == 0.68
    assert c[2] > c[1]


def test_pico_1_abre_cheio() -> None:
    c = curva_rampa_com_pico(1)
    assert c[0] == 0.80  # o mes 0 (inauguracao) segue o medido
    assert set(c[1:]) == {1.0}


@pytest.mark.parametrize("pico", PICOS)
def test_toda_opcao_e_monotonica_e_fecha_no_pico(pico: int) -> None:
    c = curva_rampa_com_pico(pico)
    assert all(0.0 < f <= 1.0 for f in c)
    assert all(b >= a for a, b in zip(c[1:], c[2:], strict=False))  # do mes 1 em diante
    assert next(k for k, f in enumerate(c) if f >= 1.0) == pico  # mes de VIDA
    p = _premissas_pico(pico)  # o nucleo aceita (recusa curva que decresce do mes 1 em diante)
    assert p.mes_maturidade_rampa == pico + 1  # mes de OPERACAO
    r = simular(DEMANDA, p, **INVEST)  # type: ignore[arg-type]
    # steady = max(pico + 1, mes da anuidade = 12)
    assert r.mes_referencia_steady == max(pico + 1, 12)
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
        for m in PICOS
    ]
    assert paybacks == sorted(paybacks)


# Numeros da tabela da emenda na DEC-078 (golden de Londrina), medidos rodando o motor:
# pico -> (alunos no 1o mes de operacao, payback, TIR do socio a.a., mes de steady).
# Remedidos com o MES 0 (22/10/2026): o 1o mes e' 80% (o mes 0 do estudo) em todo pico.
EMENDA_PICO: dict[int, tuple[float, float, float, int]] = {
    6: (1843.2, 24.0, 0.5860, 12),
    8: (1843.2, 25.0, 0.5621, 12),
    10: (1843.2, 25.0, 0.5412, 12),
    12: (1843.2, 26.0, 0.5194, 13),
    15: (1843.2, 27.0, 0.4906, 16),
    18: (1843.2, 28.0, 0.4641, 19),
    24: (1843.2, 31.0, 0.4162, 25),
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


def test_pico_tardio_mede_o_steady_no_2o_ano_com_reajuste() -> None:
    """Revisao de 21/10/2026: com o fim da rampa depois do mes 12 de OPERACAO o regime pleno
    e' medido nele, que ja' tem o degrau do reajuste anual (mes 13). Com o mes 0 (22/10), o
    fim da rampa e' o pico + 1: a partir do pico 12 o steady sai a precos do 2o ano. O DRE
    de steady sobe so' pelo reajuste (os alunos sao os mesmos). A nota da tela deixa de dizer
    "nao a margem de steady-state" nesse caso (`efeitoDaRampaNoSteady`). Se um dia o steady
    passar a precos do ano 1 (decisao pendente do dono, DEC-078), este teste muda junto."""
    r11 = simular(DEMANDA, _premissas_pico(11), **INVEST)  # type: ignore[arg-type]
    r15 = simular(DEMANDA, _premissas_pico(15), **INVEST)  # type: ignore[arg-type]
    assert (r11.mes_referencia_steady, r15.mes_referencia_steady) == (12, 16)
    assert r15.faturamento_mensal_steady > r11.faturamento_mensal_steady
    assert r15.ebitda_mensal > r11.ebitda_mensal
    # mesmos alunos no mes de referencia: a diferenca e' preco, nao rampa
    s11 = next(x for x in r11.serie_mensal if x["mes"] == 12)
    s15 = next(x for x in r15.serie_mensal if x["mes"] == 16)
    assert s15["alunos_total"] == pytest.approx(s11["alunos_total"], abs=1e-9)
    # a margem quase nao se move: o efeito e' de nivel
    assert abs(r15.margem_ebitda_pct - r11.margem_ebitda_pct) < 0.001


def test_pico_invalido_no_nucleo() -> None:
    with pytest.raises(ValueError, match="mes_pico"):
        curva_rampa_com_pico(0)


# ---------------------------------------------------------------------------
# 3. Contrato: 422, eco, reta
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("pico", [-1, 0, 37, 99])
def test_pico_fora_do_intervalo_e_recusado_em_portugues(pico: int) -> None:
    for modelo in (ViabilidadeInputs, ViabilidadeIn):
        kw: dict[str, object] = {"m2": 1500, "aluguel": 30000, "demanda": 1600}
        if modelo is ViabilidadeIn:
            kw.update(lat=-23.5, lng=-46.6)
        with pytest.raises(ValidationError) as exc:
            modelo(**kw, mes_pico_rampa=pico)
        msg = str(exc.value)
        assert "mes_pico_rampa fora do intervalo" in msg
        assert "Use um mês de 1 a 36" in msg


@pytest.mark.parametrize("pico", [1, 7, 9, 36])
def test_todo_mes_do_intervalo_e_aceito(pico: int) -> None:
    """O contador anda de mes em mes: 7 e 9 (fora das antigas 7 opcoes) valem."""
    assert ViabilidadeInputs(m2=1500, aluguel=30000, demanda=1600, mes_pico_rampa=pico).mes_pico_rampa == pico


def test_api_publica_devolve_422_com_pico_fora_do_intervalo() -> None:
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from motor_expansao.api.main import create_app

    corpo = {
        "lat": -23.55,
        "lng": -46.63,
        "viabilidade": {"m2": 1500, "aluguel": 30000, "demanda": 1600, "mes_pico_rampa": 37},
    }
    resp = TestClient(create_app()).post(
        "/api/v1/analisar", json=corpo, headers={"Authorization": "Bearer dev-token"}
    )
    assert resp.status_code == 422
    assert "mes_pico_rampa fora do intervalo" in resp.text


def test_payload_ecoa_o_pico_e_a_curva_reescalada() -> None:
    p = _payload(ViabilidadeIn(**GOLDEN_BODY, mes_pico_rampa=18))["premissas"]
    assert p["forma_rampa"] == "curva_uni03"
    assert p["mes_pico_rampa"] == 18  # mes de VIDA
    assert p["mes_maturidade_rampa"] == 19  # mes de OPERACAO = pico + 1
    assert p["curva_rampa"] == [round(f, 4) for f in curva_rampa_com_pico(18)]
    assert p["mes_referencia_steady"] == 19  # max(pico 18 + 1, anuidade no mes 12)


def test_corpo_antigo_com_rampa_meses_sem_forma_segue_na_reta() -> None:
    """Revisao de 21/10/2026: ate' a emenda, `rampa_meses = N` sem `forma_rampa` era a
    reta de N meses. Cair na curva ignoraria o N em silencio (payback 39 -> 25 no golden
    com N = 14). Sem `rampa_meses` (a tela), vale a curva."""
    antigo = _payload(ViabilidadeIn(**GOLDEN_BODY, rampa_meses=14))
    pr = antigo["premissas"]
    assert pr["forma_rampa"] == "reta"
    assert pr["mes_maturidade_rampa"] == 14
    assert pr["mes_pico_rampa"] is None
    assert antigo["retorno"]["payback"] == 39.0
    assert _payload(ViabilidadeIn(**GOLDEN_BODY))["premissas"]["forma_rampa"] == "curva_uni03"
    # a curva EXPLICITA vence o `rampa_meses` (aceito e ignorado, como antes)
    curva = _payload(ViabilidadeIn(**GOLDEN_BODY, rampa_meses=14, forma_rampa="curva_uni03"))
    assert curva["premissas"]["forma_rampa"] == "curva_uni03"
    assert curva["premissas"]["mes_maturidade_rampa"] == 11
    publico = ViabilidadeInputs(m2=1500, aluguel=30000, demanda=1600, rampa_meses=14)
    assert premissas_do_body(publico).forma_rampa == "reta"


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
    # rotulo por mes de VIDA (0 = inauguracao), como no estudo
    for k, f in enumerate(curva):
        rotulo = f"Curva observada — mês {k}" + (" (inauguração)" if k == 0 else "")
        assert ws.cell(row=_linha_premissa(ws, rotulo), column=2).value == f
    with pytest.raises(AssertionError):
        _linha_premissa(ws, f"Curva observada — mês {len(curva)}")


def test_xlsx_pico_18_recalculada_bate_com_o_motor(blob_pico_18: bytes, tmp_path: Path) -> None:
    ler = _recalcular(blob_pico_18, tmp_path)
    r = simular(DEMANDA, _premissas_pico(18), **INVEST)  # type: ignore[arg-type]
    assert _divergencias(ler, r) == []
    ws = openpyxl.load_workbook(BytesIO(blob_pico_18))[ABA_PREMISSAS]
    linha = _linha_premissa(ws, "Mês de operação em que a rampa termina")
    assert ler(ABA_PREMISSAS, f"B{linha}") == 19.0  # mes de OPERACAO = pico 18 + 1


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


_LITERAL_TJ = re.compile(rb"\(((?:\\.|[^\\)])*)\)\s*Tj")
_ESCAPES_PDF = {b"n": b"\n", b"r": b"\r", b"t": b"\t", b"(": b"(", b")": b")", b"\\": b"\\"}


def texto_cru_do_pdf(pdf: bytes) -> str:
    """Texto do PDF SEM extrator: `pypdf` nao esta no [dev] e o CI nao o instala (a mesma
    tecnica de `test_relatorio_pontual_aviso_rodape.py`). O `_UltraPDF` grava o texto das
    paginas sem compressao (so' as imagens vao em FlateDecode), entao cada `cell()` e' um
    literal `(texto) Tj` nos bytes, em latin-1. Os trechos saem na ordem do arquivo, unidos
    por espaco, com espacos normalizados."""
    trechos = [
        re.sub(rb"\\(.)", lambda m: _ESCAPES_PDF.get(m.group(1), m.group(1)), m.group(1))
        for m in _LITERAL_TJ.finditer(pdf)
    ]
    return " ".join(b" ".join(trechos).decode("latin-1").split())


def _texto_pdf(payload: dict) -> str:
    from motor_expansao.dashboard.censo_report import gerar_pdf_relatorio_pontual_classico

    resultado = {"lat": -23.33, "lng": -51.16, "nome_municipio": "LONDRINA", "uf": "PR",
                 "raio_km": 1.0}
    return texto_cru_do_pdf(gerar_pdf_relatorio_pontual_classico(resultado, None, viabilidade=payload))


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
