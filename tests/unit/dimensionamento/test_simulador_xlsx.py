"""Testes do simulador financeiro XLSX com formulas vivas (FIN-VIAB-01).

LIMITE CONHECIDO: openpyxl NAO avalia formulas. Entao aqui NAO se testa o
resultado de nenhuma formula. Testa-se o que da para testar sem um motor de
calculo:
  - a estrutura do arquivo (8 abas, 64 colunas de mes, sublinhas de custo);
  - que as celulas de DRE/fluxo/resumo contem FORMULA (comecam com "="), e nao
    valor cravado — se alguem trocar formula por valor, o teste quebra;
  - que os VALORES DO MOTOR gravados na aba Afericao conferem com `simular()` ao
    vivo. Isso e o que garante que o PARAMETRO DE COMPARACAO dentro do arquivo
    esta certo: e a afericao que defende o arquivo na frente do investidor, e um
    parametro errado la tornaria a aba inutil (ou pior, tranquilizadora a toa).
"""

from __future__ import annotations

import re
import unicodedata
import warnings
import zipfile
from io import BytesIO

import openpyxl
import pytest

from motor_expansao.dimensionamento.config import SIM_OUTROS_FIXOS_MES
from motor_expansao.dimensionamento.simulador import Premissas, simular
from motor_expansao.dimensionamento.simulador_xlsx import (
    _DRE_ROW,
    _FLX_ROW,
    _FOLHA_MODO_ROW,
    _MES_COL_INI,
    _OUTROS_FIXOS_DECOMP,
    _RESUMO_ROW_INI,
    ABA_AFERICAO,
    ABA_DRE,
    ABA_FLUXO,
    ABA_FOLHA,
    ABA_PREMISSAS,
    ABA_RESUMO,
    ABAS_ESPERADAS,
    gerar_simulador_xlsx,
)

# Caso golden (Boulevard Londrina) — os mesmos inputs do resto do ciclo.
_DEMANDA = 2304.0
_INVEST = {
    "obra": 600_000.0,
    "parcelas_obra": 4,
    "equipamentos": 1_400_000.0,
    "prazo_equipamentos": 60,
    "juros_equipamentos_am": 0.018,
    "taxa_franquia": 160_000.0,
}


def _premissas() -> Premissas:
    return Premissas(ticket_cheio=147.0, aluguel_mes=30_000.0, maturacao_meses=8)


@pytest.fixture(scope="module")
def blob() -> bytes:
    return gerar_simulador_xlsx(
        _DEMANDA, _premissas(), nome_ponto="Boulevard Londrina", **_INVEST
    )


@pytest.fixture(scope="module")
def wb(blob: bytes) -> openpyxl.Workbook:
    return openpyxl.load_workbook(BytesIO(blob), data_only=False)


@pytest.fixture(scope="module")
def resultado():
    return simular(_DEMANDA, _premissas(), **_INVEST)


def _norm(texto: str) -> str:
    """Compara rotulos sem depender de acento nem de travessao vs hifen."""
    sem = unicodedata.normalize("NFKD", str(texto))
    sem = "".join(c for c in sem if not unicodedata.combining(c))
    for traco in ("—", "–", "−"):
        sem = sem.replace(traco, "-")
    return re.sub(r"\s+", " ", sem).strip().lower()


# ---------------------------------------------------------------------------
# Arquivo e estrutura
# ---------------------------------------------------------------------------


def test_arquivo_e_xlsx_valido(blob: bytes) -> None:
    assert blob[:2] == b"PK", "xlsx e um container ZIP"
    with zipfile.ZipFile(BytesIO(blob)) as z:
        assert z.testzip() is None
        nomes = z.namelist()
    assert "xl/workbook.xml" in nomes
    assert any(n.startswith("xl/worksheets/sheet") for n in nomes)


def test_reabre_sem_warning_de_corrupcao(blob: bytes) -> None:
    with warnings.catch_warnings(record=True) as capturados:
        warnings.simplefilter("always")
        openpyxl.load_workbook(BytesIO(blob), data_only=False)
    assert [str(w.message) for w in capturados] == []


def test_oito_abas_na_ordem_esperada(wb: openpyxl.Workbook) -> None:
    assert wb.sheetnames == list(ABAS_ESPERADAS)
    assert len(ABAS_ESPERADAS) == 8


def test_recalculo_ao_abrir_esta_ligado(wb: openpyxl.Workbook) -> None:
    # Sem valor em cache, o Excel precisa recalcular na abertura.
    assert wb.calculation.fullCalcOnLoad is True


# ---------------------------------------------------------------------------
# Linha do tempo
# ---------------------------------------------------------------------------


def test_dre_tem_64_colunas_de_mes_comecando_em_m_menos_4(wb: openpyxl.Workbook) -> None:
    ws = wb[ABA_DRE]
    rotulos: list[str] = []
    col = _MES_COL_INI
    while True:
        v = ws.cell(row=4, column=col).value
        if not isinstance(v, str) or not re.fullmatch(r"M-?\d+", v):
            break
        rotulos.append(v)
        col += 1
    assert len(rotulos) == 64
    assert rotulos[0] == "M-4"
    assert rotulos[:5] == ["M-4", "M-3", "M-2", "M-1", "M1"]
    assert rotulos[-1] == "M60"
    # Nao existe "M0": a linha do tempo pula de M-1 para M1, como o motor.
    assert "M0" not in rotulos


def test_linha_do_tempo_da_dre_bate_com_a_serie_do_motor(
    wb: openpyxl.Workbook, resultado
) -> None:
    ws = wb[ABA_DRE]
    meses_planilha = [
        ws.cell(row=_DRE_ROW["mes"], column=_MES_COL_INI + j).value for j in range(64)
    ]
    assert meses_planilha == [int(r["mes"]) for r in resultado.serie_mensal]


def test_fluxo_usa_a_mesma_linha_do_tempo_da_dre(wb: openpyxl.Workbook) -> None:
    ws = wb[ABA_FLUXO]
    rotulos = [ws.cell(row=4, column=_MES_COL_INI + j).value for j in range(64)]
    assert rotulos[0] == "M-4"
    assert rotulos[-1] == "M60"


def test_dre_tem_coluna_de_steady_apos_os_meses(wb: openpyxl.Workbook) -> None:
    ws = wb[ABA_DRE]
    cel = ws.cell(row=4, column=_MES_COL_INI + 64)
    assert "Steady" in str(cel.value)
    # A coluna de steady e FORMULA (INDEX/MATCH pelo mes de referencia), nao um
    # numero cravado — se a maturacao mudar, ela acompanha.
    formula = ws.cell(row=_DRE_ROW["faturamento"], column=_MES_COL_INI + 64).value
    assert str(formula).startswith("=INDEX(")
    assert "MATCH(" in str(formula)


# ---------------------------------------------------------------------------
# Sublinhas exigidas
# ---------------------------------------------------------------------------


def test_dre_tem_as_4_sublinhas_de_custo_variavel(wb: openpyxl.Workbook) -> None:
    ws = wb[ABA_DRE]
    esperado = {
        "cvar_royalties": "royalties",
        "cvar_marketing": "marketing",
        "cvar_manutencao": "manutencao",
        "cvar_cartoes": "cartao",
    }
    assert len(esperado) == 4
    for key, trecho in esperado.items():
        rotulo = _norm(ws.cell(row=_DRE_ROW[key], column=1).value)
        assert trecho in rotulo, f"{key}: {rotulo!r}"


def test_dre_detalha_outros_fixos_em_linhas_redondas(wb: openpyxl.Workbook) -> None:
    """As componentes fecham EXATAMENTE no total do motor, sem rateio.

    O comentario do config.py listava SETE componentes somando R$ 40.150, contra os
    R$ 38.150 da constante; as SEIS reais fecham no centavo e o "Outros (2.000)" era
    espurio. Importa porque ratear as sete para fechar no total dava "IPTU R$ 1.900,37"
    e "Telefone R$ 475,09" — valores que ninguem defende linha a linha na frente de um
    investidor, que e o proposito desta planilha.
    """
    ws = wb[ABA_DRE]
    assert len(_OUTROS_FIXOS_DECOMP) == 6
    soma = sum(v for _k, _l, v in _OUTROS_FIXOS_DECOMP)
    assert soma == pytest.approx(SIM_OUTROS_FIXOS_MES, abs=0.01), (
        f"a decomposicao soma {soma} e a constante vale {SIM_OUTROS_FIXOS_MES}: "
        "se divergirem, a planilha rateia e os valores saem quebrados"
    )
    for key, label, valor in _OUTROS_FIXOS_DECOMP:
        rotulo = _norm(ws.cell(row=_DRE_ROW[key], column=1).value)
        assert _norm(label) in rotulo, f"{key}: {rotulo!r}"
        # Valores REDONDOS: nada de centavo vindo de rateio.
        assert valor == round(valor, 2) and valor % 50 == 0, f"{label} = {valor}"


def test_fluxo_detalha_o_financiamento_e_o_investimento(wb: openpyxl.Workbook) -> None:
    ws = wb[ABA_FLUXO]
    for key in ("saldo_inicial", "juros", "pmt", "amortizacao", "saldo_final",
                "inv_obra", "inv_franquia", "inv_equip_vista", "payback"):
        assert ws.cell(row=_FLX_ROW[key], column=1).value, f"linha {key} sem rótulo"


# ---------------------------------------------------------------------------
# Sao FORMULAS, nao valores cravados
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "aba,linhas",
    [
        (ABA_DRE, ("faturamento", "receita_liquida", "impostos", "cvar_total", "folha",
                   "outros_total", "aluguel", "custos_op", "ebitda", "margem_ebitda",
                   "ir_total", "juros", "resultado_desalav")),
        (ABA_FLUXO, ("ebitda", "ir_csll", "pmt", "amortizacao", "saldo_final",
                     "investimento", "fcf", "fcf_acumulado")),
    ],
)
def test_linhas_da_linha_do_tempo_sao_formulas(
    wb: openpyxl.Workbook, aba: str, linhas: tuple[str, ...]
) -> None:
    ws = wb[aba]
    mapa = _DRE_ROW if aba == ABA_DRE else _FLX_ROW
    for key in linhas:
        for j in range(64):
            v = ws.cell(row=mapa[key], column=_MES_COL_INI + j).value
            assert isinstance(v, str) and v.startswith("="), (
                f"{aba}/{key} mês {j}: esperava fórmula, veio {v!r}"
            )


def test_resumo_nao_tem_numero_digitado(wb: openpyxl.Workbook) -> None:
    ws = wb[ABA_RESUMO]
    formulas = 0
    for row in range(_RESUMO_ROW_INI, ws.max_row + 1):
        v = ws.cell(row=row, column=2).value
        if v is None:
            continue
        assert isinstance(v, str) and v.startswith("="), (
            f"Resumo linha {row}: KPI cravado como valor ({v!r})"
        )
        formulas += 1
    assert formulas >= 25


def test_folha_calcula_custo_por_cargo_com_formula(wb: openpyxl.Workbook) -> None:
    ws = wb[ABA_FOLHA]
    # Qtd x Salario x (1 + Encargos) por cargo, e TOTAL somando.
    achou = 0
    for row in range(1, ws.max_row + 1):
        v = ws.cell(row=row, column=5).value
        if isinstance(v, str) and re.fullmatch(r"=B\d+\*C\d+\*\(1\+D\d+\)", v):
            achou += 1
    assert achou >= 5, "quadro de pessoal deveria calcular o custo por fórmula"
    assert any(
        isinstance(ws.cell(row=r, column=5).value, str)
        and str(ws.cell(row=r, column=5).value).startswith("=SUM(E")
        for r in range(1, ws.max_row + 1)
    )


def test_dre_le_a_folha_pelo_interruptor_de_modo(wb: openpyxl.Workbook) -> None:
    """A DRE alterna entre `folha_pct x faturamento` e o TOTAL do quadro de pessoal."""
    formula = str(wb[ABA_DRE].cell(row=_DRE_ROW["folha"], column=_MES_COL_INI + 15).value)
    assert "quadro de pessoal" in formula
    assert f"{ABA_PREMISSAS}!" in formula

    # A ponte DRE -> Folha passa pela aba Premissas: uma celula aponta para o
    # interruptor e outra para o TOTAL do quadro.
    ws = wb[ABA_PREMISSAS]
    pontes = {
        _norm(ws.cell(row=r, column=1).value or ""): str(ws.cell(row=r, column=2).value)
        for r in range(4, ws.max_row + 1)
    }
    assert pontes["modo da folha (interruptor)"] == f"={ABA_FOLHA}!$B${_FOLHA_MODO_ROW}"
    assert pontes["total do quadro de pessoal (aba folha)"].startswith(f"={ABA_FOLHA}!$E$")


# ---------------------------------------------------------------------------
# Interruptor de modo da folha
# ---------------------------------------------------------------------------


def test_interruptor_modo_da_folha_existe_com_default_percentual(
    wb: openpyxl.Workbook,
) -> None:
    ws = wb[ABA_FOLHA]
    assert _norm(ws.cell(row=_FOLHA_MODO_ROW, column=1).value) == "modo da folha"
    assert ws.cell(row=_FOLHA_MODO_ROW, column=2).value == "percentual da receita"


def test_interruptor_modo_da_folha_tem_validacao_de_lista(wb: openpyxl.Workbook) -> None:
    ws = wb[ABA_FOLHA]
    alvo = f"B{_FOLHA_MODO_ROW}"
    candidatos = [
        dv for dv in ws.data_validations.dataValidation
        if dv.type == "list" and alvo in str(dv.sqref)
    ]
    assert candidatos, "interruptor sem validação de lista"
    dv = candidatos[0]
    assert "percentual da receita" in dv.formula1
    assert "quadro de pessoal" in dv.formula1


def test_folha_avisa_que_os_salarios_sao_estimativa(wb: openpyxl.Workbook) -> None:
    ws = wb[ABA_FOLHA]
    texto = _norm(
        " ".join(
            str(ws.cell(row=r, column=1).value or "") for r in range(1, _FOLHA_MODO_ROW)
        )
    )
    assert "estimativa" in texto, "a aba tem de avisar, em texto visível, que é estimativa"


def test_quadro_default_fica_proximo_de_17pct_da_bruta_do_golden(resultado) -> None:
    from motor_expansao.dimensionamento.simulador_xlsx import (
        _ENCARGOS_DEFAULT,
        _QUADRO_PESSOAL_DEFAULT,
    )

    total = sum(q * s for _c, q, s in _QUADRO_PESSOAL_DEFAULT) * (1 + _ENCARGOS_DEFAULT)
    # A folha do caso golden e 17% da bruta; o quadro estimado nao pode estar longe,
    # senao abrir o detalhe na frente do investidor mostraria outra empresa.
    assert abs(total - resultado.folha_mensal) < 500.0, (
        f"quadro estimado R$ {total:,.2f} vs folha do motor R$ {resultado.folha_mensal:,.2f}"
    )


# ---------------------------------------------------------------------------
# Aba Afericao — o parametro de comparacao dentro do arquivo
# ---------------------------------------------------------------------------


def _afericao(wb: openpyxl.Workbook) -> dict[str, tuple[object, object]]:
    ws = wb[ABA_AFERICAO]
    out: dict[str, tuple[object, object]] = {}
    for row in range(1, ws.max_row + 1):
        rotulo = ws.cell(row=row, column=1).value
        motor = ws.cell(row=row, column=2).value
        formula = ws.cell(row=row, column=3).value
        if rotulo and isinstance(formula, str) and formula.startswith("="):
            out[_norm(rotulo)] = (motor, formula)
    return out


def test_afericao_cobre_ao_menos_20_kpis(wb: openpyxl.Workbook) -> None:
    assert len(_afericao(wb)) >= 20


def test_afericao_explica_para_que_serve(wb: openpyxl.Workbook) -> None:
    ws = wb[ABA_AFERICAO]
    cabecalho = _norm(
        " ".join(str(ws.cell(row=r, column=1).value or "") for r in range(1, 5))
    )
    assert "motor" in cabecalho and "formula" in cabecalho


def test_afericao_tem_delta_e_status_como_formula(wb: openpyxl.Workbook) -> None:
    ws = wb[ABA_AFERICAO]
    vistos = 0
    for row in range(1, ws.max_row + 1):
        if not ws.cell(row=row, column=1).value:
            continue
        delta = ws.cell(row=row, column=4).value
        status = ws.cell(row=row, column=5).value
        if not (isinstance(delta, str) and delta.startswith("=")):
            continue
        assert "C" in delta and "B" in delta, delta
        assert isinstance(status, str) and "DIVERGENTE" in status and "OK" in status
        assert "0.01" in status, "a tolerância declarada é R$ 0,01"
        vistos += 1
    assert vistos >= 20


def test_afericao_grava_os_valores_do_motor_corretos(wb: openpyxl.Workbook, resultado) -> None:
    """O parametro de comparacao dentro do arquivo tem de ser o numero do motor."""
    afer = _afericao(wb)
    serie = {int(r["mes"]): r for r in resultado.serie_mensal}
    steady = serie[int(resultado.mes_referencia_steady)]

    esperado = {
        "mes de referencia do steady": float(resultado.mes_referencia_steady),
        "alunos totais no mes de referencia": steady["alunos_total"],
        "faturamento bruto (steady)": resultado.faturamento_mensal_steady,
        "dos quais receita de anuidade": resultado.receita_anuidade_mensal,
        "deducoes (devolucoes)": steady["deducoes"],
        "receita liquida": resultado.receita_liquida,
        "impostos sobre receita": steady["impostos"],
        "receita pos-impostos": resultado.receita_pos_impostos,
        "custo variavel": resultado.custos_variaveis_mensal,
        "folha": resultado.folha_mensal,
        "outros custos fixos": steady["outros_fixos"],
        "aluguel": steady["aluguel"],
        "custos operacionais totais": resultado.custos_op_mensal,
        "ebitda": resultado.ebitda_mensal,
        "margem ebitda": resultado.margem_ebitda_pct,
        "ir/csll": resultado.ir_csll_mensal,
        "despesa financeira (juros do mes de referencia)": resultado.despesa_financeira_mensal,
        "resultado desalavancado apos ir": resultado.resultado_apos_ir_mensal,
        "pmt do financiamento": resultado.pmt_mensal,
        "juros totais do financiamento": resultado.juros_totais,
        "capex total": resultado.capex_total,
        "investimento total": resultado.investimento_total,
        "break-even de ebitda (alunos totais)": resultado.alunos_break_even_total,
        "break-even de caixa (alunos totais)": resultado.alunos_break_even_caixa_total,
        "payback (meses)": resultado.payback_meses,
        "tir mensal": resultado.tir_mensal,
        "tir anual": resultado.tir_anual,
        "vpl na taxa de desconto": resultado.vpl,
        "fcf acumulado no fim do horizonte": resultado.acumulado_mes_final,
        "retorno anual desalavancado": resultado.retorno_anual_desalavancado,
        "retorno anual do equity": resultado.retorno_anual_equity,
        "ticket blended": resultado.ticket_blended,
        "aluguel-teto - faixa ideal": resultado.aluguel_teto["ideal"],
        "aluguel-teto - teto (canonico)": resultado.aluguel_teto["teto"],
        "aluguel-teto - excecao": resultado.aluguel_teto["excecao"],
        "ebitda do mes 1 (negativo por construcao)": serie[1]["ebitda_mensal"],
    }
    assert len(esperado) >= 20

    for rotulo, valor_motor in esperado.items():
        assert rotulo in afer, f"rótulo {rotulo!r} ausente da aba Aferição"
        gravado = afer[rotulo][0]
        assert isinstance(gravado, (int, float)), f"{rotulo}: {gravado!r} não é número"
        assert abs(float(gravado) - float(valor_motor)) < 0.01, (
            f"{rotulo}: planilha grava {gravado!r}, motor calcula {valor_motor!r}"
        )


def test_afericao_referencia_celulas_e_nao_repete_o_valor(wb: openpyxl.Workbook) -> None:
    for rotulo, (_motor, formula) in _afericao(wb).items():
        assert re.search(r"=[A-Za-z'].*![$]?[A-Z]{1,3}[$]?\d+", str(formula)), (
            f"{rotulo}: coluna da fórmula deveria referenciar outra aba, veio {formula!r}"
        )


# ---------------------------------------------------------------------------
# Guardrails
# ---------------------------------------------------------------------------


def test_nenhum_valor_estatico_e_inf_ou_nan(wb: openpyxl.Workbook) -> None:
    for aba in wb.sheetnames:
        for row in wb[aba].iter_rows():
            for c in row:
                if isinstance(c.value, float):
                    assert c.value == c.value, f"{aba}!{c.coordinate} é NaN"
                    assert abs(c.value) != float("inf"), f"{aba}!{c.coordinate} é inf"


def test_formulas_usam_virgula_como_separador_de_argumentos(wb: openpyxl.Workbook) -> None:
    """openpyxl grava en-US; ponto e virgula aqui quebraria a abertura no Excel."""
    for aba in wb.sheetnames:
        for row in wb[aba].iter_rows():
            for c in row:
                v = c.value
                if isinstance(v, str) and v.startswith("="):
                    assert ";" not in v, f"{aba}!{c.coordinate}: {v!r}"


def test_ranges_entre_abas_sao_sintaticamente_validos(wb: openpyxl.Workbook) -> None:
    """Regressao: `Aba!$B$5:Aba!$B$9` e sintaxe INVALIDA (a aba vem uma vez so)."""
    for aba in wb.sheetnames:
        for row in wb[aba].iter_rows():
            for c in row:
                v = c.value
                if not (isinstance(v, str) and v.startswith("=")):
                    continue
                for trecho in re.findall(r"[$]?[A-Z]{1,3}[$]?\d+:[^,)\s]+", v):
                    depois = trecho.split(":", 1)[1]
                    assert "!" not in depois, f"{aba}!{c.coordinate}: {v!r}"


def test_premissas_marca_editavel_derivada_e_fonte(wb: openpyxl.Workbook) -> None:
    ws = wb[ABA_PREMISSAS]
    editaveis = derivadas = 0
    for row in range(4, ws.max_row + 1):
        rotulo = ws.cell(row=row, column=1).value
        valor = ws.cell(row=row, column=2)
        if not rotulo or valor.value is None:
            continue
        quem = ws.cell(row=row, column=5).value
        fonte = ws.cell(row=row, column=4).value
        assert quem, f"linha {row} sem 'Quem pode alterar'"
        assert fonte, f"linha {row} sem 'Fonte'"
        if isinstance(valor.value, str) and valor.value.startswith("="):
            derivadas += 1
        else:
            editaveis += 1
    assert editaveis >= 40
    assert derivadas >= 15


def test_premissas_puxa_os_defaults_do_objeto_recebido() -> None:
    """Nenhuma constante e redigitada: mudar a premissa muda a celula."""
    p = Premissas(ticket_cheio=199.0, aluguel_mes=41_000.0, maturacao_meses=10)
    wb2 = openpyxl.load_workbook(
        BytesIO(gerar_simulador_xlsx(1_500.0, p, **_INVEST)), data_only=False
    )
    ws = wb2[ABA_PREMISSAS]
    achados: dict[str, object] = {}
    for row in range(4, ws.max_row + 1):
        rotulo = _norm(ws.cell(row=row, column=1).value or "")
        achados[rotulo] = ws.cell(row=row, column=2).value
    assert achados["ticket cheio (balcao)"] == 199.0
    assert achados["aluguel"] == 41_000.0
    assert achados["maturacao da rampa"] == 10
    assert achados["demanda total (alunos na maturidade)"] == 1_500.0


def test_folha_absoluta_abre_no_modo_quadro_e_fecha_no_centavo() -> None:
    """Com `pessoal_mes_override`, a folha e ABSOLUTA e o quadro tem de somar exato.

    Nesse caminho o interruptor ja abre em "quadro de pessoal" (a DRE le o TOTAL da
    aba), entao um residuo de arredondamento no rateio dos salarios faria a planilha
    divergir do motor por centavos.
    """
    from motor_expansao.dimensionamento.simulador_xlsx import (
        _ENCARGOS_DEFAULT,
        _FOLHA_CARGO_ROW_INI,
        _quadro_pessoal,
    )

    override = 50_128.16
    p = Premissas(ticket_cheio=147.0, aluguel_mes=30_000.0, pessoal_mes_override=override)
    quadro = _quadro_pessoal(p)
    total = sum(q * s for _c, q, s in quadro) * (1 + _ENCARGOS_DEFAULT)
    assert abs(total - override) < 0.005, f"quadro soma {total!r}, override é {override!r}"

    wb2 = openpyxl.load_workbook(
        BytesIO(gerar_simulador_xlsx(_DEMANDA, p, dict(_INVEST))), data_only=False
    )
    ws = wb2[ABA_FOLHA]
    assert ws.cell(row=_FOLHA_MODO_ROW, column=2).value == "quadro de pessoal"
    assert ws.cell(row=_FOLHA_CARGO_ROW_INI, column=3).value is not None
    afer = _afericao(wb2)
    assert abs(float(afer["folha"][0]) - override) < 0.01


def test_aceita_investimento_como_dict_posicional(resultado) -> None:
    """Contrato com a rota do piloto web: `gerar(demanda, premissas, investimento)`.

    A rota passa o investimento POSICIONAL, como dict, e `rotulo`/`m2` como kwargs
    opcionais. Um nome diferente aqui viraria TypeError em runtime (HTTP 500 no
    lugar do arquivo).
    """
    blob2 = gerar_simulador_xlsx(
        _DEMANDA, _premissas(), dict(_INVEST), rotulo="Ponto A", m2=1800.0
    )
    wb2 = openpyxl.load_workbook(BytesIO(blob2), data_only=False)
    assert wb2.sheetnames == list(ABAS_ESPERADAS)
    # O dict posicional tem de ter REALMENTE alimentado o investimento.
    afer = _afericao(wb2)
    assert abs(float(afer["investimento total"][0]) - resultado.investimento_total) < 0.01
    assert abs(float(afer["pmt do financiamento"][0]) - resultado.pmt_mensal) < 0.01
    # rotulo e m2 aparecem no cabeçalho (enfeite, não entram em conta nenhuma).
    titulo = str(wb2[ABA_PREMISSAS].cell(row=1, column=1).value)
    assert "Ponto A" in titulo and "m²" in titulo


def test_dict_de_investimento_ignora_chave_desconhecida() -> None:
    blob2 = gerar_simulador_xlsx(
        _DEMANDA, _premissas(), {**_INVEST, "chave_que_nao_existe": 1}
    )
    assert blob2[:2] == b"PK"


def test_nomes_definidos_sao_ascii(wb: openpyxl.Workbook) -> None:
    nomes = list(wb.defined_names)
    assert nomes, "nenhum nome definido registrado"
    for n in nomes:
        assert n.isascii(), f"identificador acentuado: {n}"
        assert n.startswith("prem_")
