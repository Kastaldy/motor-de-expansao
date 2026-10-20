"""Rampa pela CURVA OBSERVADA na rede (DEC-075, BLK-UNI-03).

O QUE ESTE ARQUIVO TRAVA
------------------------
1. A curva que o motor usa e' DERIVADA da tabela P1 do estudo por tres regras
   declaradas (sem o mes 0, maximo acumulado, teto de 100%) — o teste refaz a conta.
2. A curva e' aplicada MES A MES: alunos(t) = demanda x fracao(t), demanda cheia depois.
3. A RETA continua byte a byte a de antes: os digests da serie foram medidos com o
   codigo da `origin/main` ANTERIOR a esta mudanca (git archive) e reproduzidos aqui.
   Se um campo novo entrar na serie mensal, refaca o digest contra a main de ANTES da
   mudanca — nunca contra o proprio codigo novo, que tornaria o teste circular.
4. Os NUMEROS da DEC-075 (caso golden Boulevard Londrina, reta x curva) — medidos
   rodando o motor; a DEC cita estes valores e nao outros.
5. O contrato do payload (`forma_rampa`): default curva, reta escolhivel, 422 em
   portugues, eco no payload.
6. A planilha .xlsx com a curva: recalculada, bate com o motor nos 64 meses; e trocar a
   celula "Forma da rampa" para "reta" reproduz o motor na reta.

READ-ONLY sobre o M1.
"""

from __future__ import annotations

import hashlib
import json
import sys
import warnings
from dataclasses import replace
from io import BytesIO
from pathlib import Path

import openpyxl
import pytest
from openpyxl.utils import get_column_letter
from pydantic import ValidationError

from motor_expansao.dimensionamento.config import (
    SIM_CURVA_RAMPA_UNI03,
    SIM_CURVA_UNI03_ALUNOS_P1,
    SIM_FORMA_RAMPA_CURVA_UNI03,
    SIM_FORMA_RAMPA_PADRAO,
    SIM_FORMA_RAMPA_RETA,
)
from motor_expansao.dimensionamento.payload_viabilidade import (
    ViabilidadeIn,
    ViabilidadeInputs,
    premissas_do_body,
)
from motor_expansao.dimensionamento.simulador import (
    Premissas,
    simular,
    viabilidade,
)
from motor_expansao.dimensionamento.simulador_xlsx import (
    _DRE_ROW,
    _FLX_ROW,
    _MES_COL_INI,
    ABA_AFERICAO,
    ABA_DRE,
    ABA_FLUXO,
    ABA_PREMISSAS,
    gerar_simulador_xlsx,
)

CENTAVO = 0.01
RATE = 1e-9

# Caso golden (Boulevard Shopping Londrina) — os mesmos inputs de test_viabilidade_golden.
DEMANDA = 2304.0
INVEST: dict[str, float | int] = {
    "obra": 600_000.0,
    "parcelas_obra": 4,
    "equipamentos": 1_400_000.0,
    "prazo_equipamentos": 60,
    "juros_equipamentos_am": 0.018,
    "taxa_franquia": 160_000.0,
}


def _premissas(**over: object) -> Premissas:
    kw: dict[str, object] = {
        "ticket_cheio": 147.0,
        "aluguel_mes": 30_000.0,
        "maturacao_meses": 8,
        "carencia_aluguel_meses": 0,
    }
    kw.update(over)
    return Premissas(**kw)  # type: ignore[arg-type]


def _rodar(forma: str, demanda: float = DEMANDA, **over: object):
    return simular(demanda, _premissas(forma_rampa=forma, **over), **INVEST)  # type: ignore[arg-type]


def _operacao(r) -> list[dict]:
    return [linha for linha in r.serie_mensal if linha["fase"] == "operacao"]


# ---------------------------------------------------------------------------
# 1. A curva: transcricao e derivacao
# ---------------------------------------------------------------------------


def test_transcricao_da_tabela_p1_coluna_alunos_mediana() -> None:
    """data/analysis/uni/uni03/resultado_uni03.md, tabela P1, meses 0..12 (alunos, mediana)."""
    assert SIM_CURVA_UNI03_ALUNOS_P1 == (
        0.80, 0.68, 0.77, 0.84, 0.88, 0.90, 0.92, 0.97, 0.95, 0.99, 1.00, 1.01, 1.01,
    )


def test_tabela_p1_no_disco_bate_com_a_transcricao() -> None:
    """Le a tabela do estudo e confere a coluna — a transcricao nao pode divergir do .md."""
    md = Path(__file__).resolve().parents[3] / "data/analysis/uni/uni03/resultado_uni03.md"
    if not md.exists():
        pytest.skip("estudo UNI-03 fora deste checkout")
    texto = md.read_text(encoding="utf-8")
    secao_p1 = texto.split("## P1", 1)[1].split("## P2", 1)[0]
    lidos: dict[int, float] = {}
    for linha in secao_p1.splitlines():
        celulas = [c.strip() for c in linha.strip().strip("|").split("|")]
        if len(celulas) >= 2 and celulas[0].isdigit() and celulas[1].endswith("%"):
            lidos[int(celulas[0])] = int(celulas[1].rstrip("%")) / 100
    assert [lidos[m] for m in range(13)] == list(SIM_CURVA_UNI03_ALUNOS_P1)


def test_curva_do_motor_e_derivada_da_p1_pelas_tres_regras() -> None:
    """Sem o mes 0, maximo acumulado (nunca decresce) e teto de 100%."""
    derivada, maximo = [], 0.0
    for f in SIM_CURVA_UNI03_ALUNOS_P1[1:]:
        maximo = max(maximo, f)
        derivada.append(min(maximo, 1.0))
    assert tuple(derivada) == SIM_CURVA_RAMPA_UNI03
    # As duas correcoes que a regra faz de fato (o resto e' a tabela crua):
    assert SIM_CURVA_RAMPA_UNI03[7] == 0.97  # mes 8: 95% bruto -> 97% do mes 7
    assert SIM_CURVA_RAMPA_UNI03[10:] == (1.00, 1.00)  # meses 11-12: 101% -> 100%


# ---------------------------------------------------------------------------
# 2. Aplicacao mes a mes e mes de maturidade
# ---------------------------------------------------------------------------


def test_curva_aplicada_mes_a_mes_e_demanda_cheia_depois() -> None:
    op = _operacao(_rodar(SIM_FORMA_RAMPA_CURVA_UNI03))
    for linha in op:
        t = int(linha["mes"])
        frac = SIM_CURVA_RAMPA_UNI03[t - 1] if t <= 12 else 1.0
        assert linha["alunos_total"] == pytest.approx(DEMANDA * frac, abs=1e-9), t
        # o split e' o mesmo da reta: balcao + agregador fecham o total (sem studio)
        assert linha["alunos_balcao"] + linha["alunos_agregadores"] == pytest.approx(
            linha["alunos_total"], abs=1e-9
        )


def test_curva_ignora_alunos_iniciais_e_maturacao() -> None:
    a = _rodar(SIM_FORMA_RAMPA_CURVA_UNI03)
    b = _rodar(SIM_FORMA_RAMPA_CURVA_UNI03, alunos_inicial=50.0, maturacao_meses=30)
    assert a.serie_mensal == b.serie_mensal


def test_studios_rampam_junto_com_a_curva() -> None:
    p = _premissas(forma_rampa=SIM_FORMA_RAMPA_CURVA_UNI03, tickets_studios=(120.0, 90.0))
    op = _operacao(simular(DEMANDA, p, **INVEST))  # type: ignore[arg-type]
    m1 = op[0]
    assert m1["alunos_total"] == pytest.approx(DEMANDA * 0.68)
    assert m1["alunos_studios"] == pytest.approx(DEMANDA * 0.68 * p.share_studios_total)


def test_mes_de_maturidade_nas_duas_formas() -> None:
    assert _premissas(forma_rampa=SIM_FORMA_RAMPA_CURVA_UNI03).mes_maturidade_rampa == 10
    assert _premissas(forma_rampa=SIM_FORMA_RAMPA_RETA).mes_maturidade_rampa == 8
    nunca_cheia = _premissas(forma_rampa=SIM_FORMA_RAMPA_CURVA_UNI03, curva_rampa=(0.5, 0.9))
    assert nunca_cheia.mes_maturidade_rampa == 3  # o mes seguinte ao ultimo da tabela


def test_steady_da_curva_e_o_mesmo_mes_e_o_mesmo_numero_da_reta() -> None:
    """Com a anuidade no mes 12, o regime pleno e' o mes 12 nas duas formas (max(10, 12) e
    max(8, 12)) e la' a demanda e' cheia: margem, EBITDA e faturamento maduros NAO mudam."""
    reta, curva = _rodar(SIM_FORMA_RAMPA_RETA), _rodar(SIM_FORMA_RAMPA_CURVA_UNI03)
    assert curva.mes_referencia_steady == reta.mes_referencia_steady == 12
    assert curva.ebitda_mensal == reta.ebitda_mensal
    assert curva.faturamento_mensal_steady == reta.faturamento_mensal_steady
    assert curva.margem_ebitda_pct == reta.margem_ebitda_pct
    # sem anuidade o steady e' o fim da rampa de cada forma
    sem = {"anuidade_valor": 0.0}
    assert _rodar(SIM_FORMA_RAMPA_CURVA_UNI03, **sem).mes_referencia_steady == 10
    assert _rodar(SIM_FORMA_RAMPA_RETA, **sem).mes_referencia_steady == 8


# ---------------------------------------------------------------------------
# 3. A reta continua byte a byte a de antes (digest medido na main anterior)
# ---------------------------------------------------------------------------


def _digest(serie: list[dict]) -> str:
    return hashlib.sha256(json.dumps(serie, sort_keys=True, default=repr).encode()).hexdigest()


def test_reta_reproduz_o_motor_anterior_byte_a_byte() -> None:
    """Digests da serie mensal medidos com `git archive origin/main` ANTES desta mudanca."""
    golden = simular(DEMANDA, _premissas(), **INVEST)  # type: ignore[arg-type]
    studios = simular(
        DEMANDA, Premissas(ticket_cheio=147.0, aluguel_mes=30_000.0, tickets_studios=(120.0, 90.0)),
        **INVEST,  # type: ignore[arg-type]
    )
    legado = viabilidade(938, 1500, 30_000.0, 137.0)
    assert _digest(golden.serie_mensal) == (
        "cc52c0100e8994f747521a8ca3e4d337a4210a882074cfb9792f2252bcdc1b96"
    )
    assert _digest(studios.serie_mensal) == (
        "32cc6c4a805fa379cf286681f7312464935722dcc2c87103ce66e2e4c76b5c8c"
    )
    assert _digest(legado.serie_mensal) == (
        "4d4f6c713f5bedf37c410c6382dd520a909435a802d617eb81b193c3be6efdd4"
    )


def test_default_do_nucleo_e_reta_e_o_do_produto_e_a_curva() -> None:
    """O nucleo fica na reta (adaptadores e golden historicos); o produto escolhe a curva."""
    assert Premissas(ticket_cheio=147.0).forma_rampa == SIM_FORMA_RAMPA_RETA
    assert SIM_FORMA_RAMPA_PADRAO == SIM_FORMA_RAMPA_CURVA_UNI03
    assert _rodar(SIM_FORMA_RAMPA_RETA).serie_mensal == simular(
        DEMANDA, _premissas(), **INVEST  # type: ignore[arg-type]
    ).serie_mensal


# ---------------------------------------------------------------------------
# 4. Validacao do nucleo
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("over", "trecho"),
    [
        ({"forma_rampa": "exponencial"}, "forma_rampa deve ser"),
        ({"forma_rampa": "curva_uni03", "curva_rampa": (0.5, 1.2)}, "curva_rampa"),
        ({"forma_rampa": "curva_uni03", "curva_rampa": (0.0, 1.0)}, "curva_rampa"),
        ({"forma_rampa": "curva_uni03", "curva_rampa": ()}, "curva_rampa"),
        ({"forma_rampa": "curva_uni03", "rampa_apenas_balcao": True}, "rampa_apenas_balcao"),
    ],
)
def test_premissas_recusa_rampa_que_o_modelo_nao_representa(over: dict, trecho: str) -> None:
    with pytest.raises(ValueError, match=trecho):
        Premissas(ticket_cheio=147.0, **over)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 5. Os numeros da DEC-075 (golden Boulevard Londrina, reta x curva)
# ---------------------------------------------------------------------------

# forma -> (payback, TIR socio a.a., TIR negocio a.a., VPL socio, VPL negocio,
#           cheque total, mes do cheque, 1o mes de caixa operacional positivo,
#           acumulado M60, faturamento do ano 1, EBITDA do ano 1, EBITDA do mes 1)
DEC075: dict[str, tuple[float, ...]] = {
    SIM_FORMA_RAMPA_RETA: (
        31.0, 0.38980333133523914, 0.31739237238430995, 276103.238284283,
        312177.17579961044, 1142112.6247071032, 5, 6, 1645454.5567363773,
        2631281.5853913524, 696509.0805967503, -43464.46942978802,
    ),
    SIM_FORMA_RAMPA_CURVA_UNI03: (
        25.0, 0.563040601998507, 0.3914006573354487, 557920.6631000271,
        596304.9065311713, 902874.7867824477, 2, 3, 1962919.6267281913,
        3091252.5641750325, 1064018.993080229, 37346.44224587534,
    ),
}
# alunos totais nos meses 1/3/6/8/10/12
DEC075_ALUNOS = {
    SIM_FORMA_RAMPA_RETA: (725.5, 1176.5, 1853.0, 2304.0, 2304.0, 2304.0),
    SIM_FORMA_RAMPA_CURVA_UNI03: (1566.72, 1935.36, 2119.68, 2234.88, 2304.0, 2304.0),
}


@pytest.mark.parametrize("forma", sorted(DEC075))
def test_numeros_da_dec_075_no_golden(forma: str) -> None:
    r = _rodar(forma)
    op = _operacao(r)
    obtido = (
        r.payback_meses, r.tir_socio_anual, r.tir_negocio_anual, r.vpl_socio, r.vpl_negocio,
        r.cheque_total, r.mes_cheque_total, r.mes_caixa_operacional_positivo,
        r.acumulado_mes_final, sum(x["faturamento_mensal"] for x in op[:12]),
        sum(x["ebitda_mensal"] for x in op[:12]), op[0]["ebitda_mensal"],
    )
    esperado = DEC075[forma]
    assert obtido[0] == esperado[0]
    assert obtido[1] == pytest.approx(esperado[1], abs=RATE)
    assert obtido[2] == pytest.approx(esperado[2], abs=RATE)
    for i in (3, 4, 5, 8, 9, 10, 11):
        assert obtido[i] == pytest.approx(esperado[i], abs=CENTAVO), i
    assert (obtido[6], obtido[7]) == (esperado[6], esperado[7])
    assert tuple(op[m - 1]["alunos_total"] for m in (1, 3, 6, 8, 10, 12)) == pytest.approx(
        DEC075_ALUNOS[forma], abs=1e-9
    )


@pytest.mark.parametrize(
    ("forma", "menor_viavel"),
    [(SIM_FORMA_RAMPA_RETA, 2164), (SIM_FORMA_RAMPA_CURVA_UNI03, 2037)],
)
def test_menor_demanda_viavel_no_golden(forma: str, menor_viavel: int) -> None:
    """A curva baixa em 127 alunos a menor demanda que passa no veredito (payback <= 36 e
    margem >= 30%) — e' a medida da amarra do BLK-UNI-05 (mais aprovacoes)."""
    assert _rodar(forma, float(menor_viavel)).flag_viavel
    assert not _rodar(forma, float(menor_viavel - 1)).flag_viavel


# ---------------------------------------------------------------------------
# 6. Payload: `forma_rampa`
# ---------------------------------------------------------------------------

_BODY: dict[str, object] = {
    "lat": -23.5, "lng": -46.6, "m2": 1500, "aluguel": 30000, "demanda": 1600, "ticket": 177,
}


def test_payload_default_e_a_curva_e_aceita_a_reta() -> None:
    assert premissas_do_body(ViabilidadeIn(**_BODY)).forma_rampa == SIM_FORMA_RAMPA_CURVA_UNI03
    reta = premissas_do_body(ViabilidadeIn(**_BODY, forma_rampa="reta", rampa_meses=10))
    assert reta.forma_rampa == SIM_FORMA_RAMPA_RETA
    assert reta.maturacao_meses == 10


def test_payload_na_reta_monta_as_mesmas_premissas_de_antes() -> None:
    """Na reta, o corpo vira EXATAMENTE as Premissas que o codigo anterior montava (que nao
    passava forma nenhuma e caia no default do nucleo, a reta)."""
    p = premissas_do_body(ViabilidadeIn(**_BODY, forma_rampa="reta"))
    assert p == Premissas(ticket_cheio=177.0, aluguel_mes=30_000.0, tickets_studios=())
    # e a curva so' difere na forma
    curva = premissas_do_body(ViabilidadeIn(**_BODY))
    assert replace(curva, forma_rampa=SIM_FORMA_RAMPA_RETA) == p


def test_payload_recusa_forma_desconhecida_em_portugues() -> None:
    with pytest.raises(ValidationError) as exc:
        ViabilidadeInputs(m2=1500, aluguel=30000, demanda=1600, forma_rampa="logistica")
    msg = str(exc.value)
    assert "forma_rampa desconhecida" in msg
    assert "curva_uni03" in msg and "reta" in msg


_SERVER = Path(__file__).resolve().parents[3] / "web" / "server"


@pytest.fixture(scope="module")
def pilot_app():
    if str(_SERVER) not in sys.path:
        sys.path.insert(0, str(_SERVER))
    import app  # noqa: PLC0415  (backend do piloto; web/server no sys.path acima)

    return app


def test_payload_ecoa_a_forma_e_o_fim_da_rampa(pilot_app) -> None:
    curva = pilot_app.viabilidade(pilot_app.ViabilidadeIn(**_BODY))["premissas"]
    assert curva["forma_rampa"] == "curva_uni03"
    assert curva["mes_maturidade_rampa"] == 10
    assert curva["curva_rampa"] == list(SIM_CURVA_RAMPA_UNI03)
    assert curva["maturacao_meses"] == 8  # parametro da reta, ecoado mas sem efeito

    reta = pilot_app.viabilidade(
        pilot_app.ViabilidadeIn(**_BODY, forma_rampa="reta", rampa_meses=6)
    )["premissas"]
    assert reta["forma_rampa"] == "reta"
    assert reta["mes_maturidade_rampa"] == 6
    assert reta["curva_rampa"] is None


# ---------------------------------------------------------------------------
# 7. Planilha .xlsx com a curva
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def blob_curva() -> bytes:
    return gerar_simulador_xlsx(
        DEMANDA, _premissas(forma_rampa=SIM_FORMA_RAMPA_CURVA_UNI03), nome_ponto="Curva", **INVEST
    )


def _linha_premissa(ws, rotulo: str) -> int:
    for row in range(1, ws.max_row + 1):
        if ws.cell(row=row, column=1).value == rotulo:
            return row
    raise AssertionError(f"premissa {rotulo!r} nao achada")


def test_xlsx_traz_a_forma_e_a_tabela_da_curva(blob_curva: bytes) -> None:
    ws = openpyxl.load_workbook(BytesIO(blob_curva))[ABA_PREMISSAS]
    assert ws.cell(row=_linha_premissa(ws, "Forma da rampa"), column=2).value == "curva observada"
    for i, f in enumerate(SIM_CURVA_RAMPA_UNI03, start=1):
        row = _linha_premissa(ws, f"Curva observada — mês {i}")
        assert ws.cell(row=row, column=2).value == f
    mes_mat = ws.cell(row=_linha_premissa(ws, "Mês em que a rampa termina"), column=2).value
    assert isinstance(mes_mat, str) and "COUNTIF" in mes_mat


def _recalcular(blob: bytes, pasta: Path):
    formulas = pytest.importorskip("formulas", reason="instale `formulas` para recalcular")
    caminho = pasta / "simulador.xlsx"
    caminho.write_bytes(blob)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        sol = formulas.ExcelModel().loads(str(caminho)).finish().calculate()
    base = f"'[{caminho.name}]"

    def ler(aba: str, coord: str) -> float:
        valor = sol[f"{base}{aba.upper()}'!{coord}"]
        try:
            valor = valor.value[0, 0]
        except (AttributeError, TypeError, IndexError):
            pass
        assert not isinstance(valor, str), f"{aba}!{coord} devolveu {valor!r}"
        return float(valor)

    return ler


_DRE_VS_MOTOR = {
    "alunos_total": "alunos_total", "alunos_balcao": "alunos_balcao",
    "alunos_agregadores": "alunos_agregadores", "faturamento": "faturamento_mensal",
    "custos_op": "custos_op", "ebitda": "ebitda_mensal",
}
_FLX_VS_MOTOR = {"fcf": "fcf_mensal", "fcf_acumulado": "fcf_acumulado"}


def _divergencias(ler, r) -> list[str]:
    erros = []
    for j, linha in enumerate(r.serie_mensal):
        letra = get_column_letter(_MES_COL_INI + j)
        for aba, mapa, rows in ((ABA_DRE, _DRE_VS_MOTOR, _DRE_ROW), (ABA_FLUXO, _FLX_VS_MOTOR, _FLX_ROW)):
            for key, campo in mapa.items():
                obtido = ler(aba, f"{letra}{rows[key]}")
                if abs(obtido - float(linha[campo])) > CENTAVO:
                    erros.append(f"{aba}/{key} M{linha['mes']}: {obtido} x {linha[campo]}")
    return erros


def test_xlsx_curva_recalculada_bate_com_o_motor(blob_curva: bytes, tmp_path: Path) -> None:
    ler = _recalcular(blob_curva, tmp_path)
    r = _rodar(SIM_FORMA_RAMPA_CURVA_UNI03)
    assert _divergencias(ler, r) == []
    # e a afericao inteira fecha (inclui o mes de steady e os KPIs)
    ws = openpyxl.load_workbook(BytesIO(blob_curva))[ABA_AFERICAO]
    conferidas = 0
    for row in range(1, ws.max_row + 1):
        motor, formula = ws.cell(row=row, column=2).value, ws.cell(row=row, column=3).value
        if isinstance(formula, str) and formula.startswith("=") and isinstance(motor, (int, float)):
            assert ler(ABA_AFERICAO, f"C{row}") == pytest.approx(float(motor), abs=CENTAVO), row
            conferidas += 1
    assert conferidas >= 40


def test_xlsx_trocar_a_celula_para_reta_reproduz_o_motor_na_reta(
    blob_curva: bytes, tmp_path: Path
) -> None:
    wb = openpyxl.load_workbook(BytesIO(blob_curva))
    ws = wb[ABA_PREMISSAS]
    ws.cell(row=_linha_premissa(ws, "Forma da rampa"), column=2).value = "reta"
    buf = BytesIO()
    wb.save(buf)
    ler = _recalcular(buf.getvalue(), tmp_path)
    assert _divergencias(ler, _rodar(SIM_FORMA_RAMPA_RETA)) == []
