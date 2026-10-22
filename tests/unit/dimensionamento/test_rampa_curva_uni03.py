"""Rampa pela CURVA OBSERVADA na rede (DEC-077, BLK-UNI-03).

O QUE ESTE ARQUIVO TRAVA
------------------------
1. A curva que o motor usa e' DERIVADA da tabela P1 do estudo por tres regras
   declaradas (sem o mes 0, maximo acumulado, teto de 100%) — o teste refaz a conta.
2. A curva e' aplicada MES A MES: alunos(t) = demanda x fracao(t), demanda cheia depois.
3. A RETA continua byte a byte a de antes: os digests da serie foram medidos com o
   codigo da `origin/main` ANTERIOR a esta mudanca (git archive) e reproduzidos aqui.
   Se um campo novo entrar na serie mensal, refaca o digest contra a main de ANTES da
   mudanca — nunca contra o proprio codigo novo, que tornaria o teste circular.
4. Os NUMEROS da DEC-077 (caso golden Boulevard Londrina, reta x curva) — medidos
   rodando o motor; a DEC cita estes valores e nao outros.
5. O contrato do payload (`forma_rampa`): default CURVA desde a emenda de 21/10/2026
   (Vinicius: "A rampa de maturacao fica exclusivamente como curva observada"; antes era
   a reta, com a curva so' como padrao da demanda da v2), reta ainda ACEITA (API publica),
   422 em portugues, eco no payload, e UMA constante do config reverte o padrao. O pico
   de maturacao escolhivel mora em `test_rampa_pico_maturacao.py`.
6. A planilha .xlsx com a curva: recalculada, bate com o motor nos 64 meses; e trocar a
   celula "Forma da rampa" para "reta" reproduz o motor na reta. A planilha da RETA nao
   tem nada da curva (e' a de antes da DEC).
7. As sensibilidades e cenarios de fronteira citados na DEC-077.

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
    forma_rampa_padrao,
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
    """O mes 0 entra como medido (emenda de 22/10/2026); do mes 1 em diante, maximo
    acumulado (nunca decresce) e teto de 100%. Indice = mes de VIDA."""
    derivada, maximo = [min(SIM_CURVA_UNI03_ALUNOS_P1[0], 1.0)], 0.0
    for f in SIM_CURVA_UNI03_ALUNOS_P1[1:]:
        maximo = max(maximo, f)
        derivada.append(min(maximo, 1.0))
    assert tuple(derivada) == SIM_CURVA_RAMPA_UNI03
    # O mes 0 (inauguracao + pre-venda) fica ACIMA do mes 1, como no estudo:
    assert SIM_CURVA_RAMPA_UNI03[:2] == (0.80, 0.68)
    # As duas correcoes que a regra faz de fato (o resto e' a tabela crua):
    assert SIM_CURVA_RAMPA_UNI03[8] == 0.97  # mes 8: 95% bruto -> 97% do mes 7
    assert SIM_CURVA_RAMPA_UNI03[11:] == (1.00, 1.00)  # meses 11-12: 101% -> 100%


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
    # o 1o mes de operacao e' o mes 0 do estudo (80%)
    assert m1["alunos_total"] == pytest.approx(DEMANDA * 0.80)
    assert m1["alunos_studios"] == pytest.approx(DEMANDA * 0.80 * p.share_studios_total)


def test_mes_de_maturidade_nas_duas_formas() -> None:
    # curva: o mes de OPERACAO 11 = o mes de vida 10 (o pico observado)
    assert _premissas(forma_rampa=SIM_FORMA_RAMPA_CURVA_UNI03).mes_maturidade_rampa == 11
    assert _premissas(forma_rampa=SIM_FORMA_RAMPA_RETA).mes_maturidade_rampa == 8
    nunca_cheia = _premissas(forma_rampa=SIM_FORMA_RAMPA_CURVA_UNI03, curva_rampa=(0.5, 0.9))
    assert nunca_cheia.mes_maturidade_rampa == 3  # o mes seguinte ao ultimo da tabela


def test_steady_da_curva_e_o_mesmo_mes_e_o_mesmo_numero_da_reta() -> None:
    """Com a anuidade no mes 12, o regime pleno e' o mes 12 nas duas formas (max(11, 12) e
    max(8, 12)) e la' a demanda e' cheia: margem, EBITDA e faturamento maduros NAO mudam."""
    reta, curva = _rodar(SIM_FORMA_RAMPA_RETA), _rodar(SIM_FORMA_RAMPA_CURVA_UNI03)
    assert curva.mes_referencia_steady == reta.mes_referencia_steady == 12
    assert curva.ebitda_mensal == reta.ebitda_mensal
    assert curva.faturamento_mensal_steady == reta.faturamento_mensal_steady
    assert curva.margem_ebitda_pct == reta.margem_ebitda_pct
    # sem anuidade o steady e' o fim da rampa de cada forma
    sem = {"anuidade_valor": 0.0}
    assert _rodar(SIM_FORMA_RAMPA_CURVA_UNI03, **sem).mes_referencia_steady == 11
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


def test_padrao_do_produto_e_a_curva_e_o_do_nucleo_segue_a_reta() -> None:
    """MUDANCA DA EMENDA de 21/10/2026 (Vinicius: "A rampa de maturacao fica exclusivamente
    como curva observada"). ANTES: padrao do produto = reta e a curva so' com a demanda da
    v2 (`SIM_FORMA_RAMPA_PADRAO_DEMANDA_V2`, constante que deixou de existir). AGORA: o
    produto inteiro (qualquer origem da demanda) nasce na curva. O default do NUCLEO
    (`Premissas`) segue a reta: adaptadores historicos, backtest e o golden do FIN-VIAB-01."""
    assert Premissas(ticket_cheio=147.0).forma_rampa == SIM_FORMA_RAMPA_RETA
    assert SIM_FORMA_RAMPA_PADRAO == SIM_FORMA_RAMPA_CURVA_UNI03
    assert forma_rampa_padrao() == SIM_FORMA_RAMPA_CURVA_UNI03
    from motor_expansao.dimensionamento import config

    assert not hasattr(config, "SIM_FORMA_RAMPA_PADRAO_DEMANDA_V2")
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
        # a rampa nunca decresce (achado 5 do revisor): 0,9 -> 0,8 e' recusado
        ({"forma_rampa": "curva_uni03", "curva_rampa": (0.5, 0.9, 0.8, 1.0)}, "decrescer"),
        ({"forma_rampa": "curva_uni03", "rampa_apenas_balcao": True}, "rampa_apenas_balcao"),
    ],
)
def test_premissas_recusa_rampa_que_o_modelo_nao_representa(over: dict, trecho: str) -> None:
    with pytest.raises(ValueError, match=trecho):
        Premissas(ticket_cheio=147.0, **over)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 5. Os numeros da DEC-077 (golden Boulevard Londrina, reta x curva)
# ---------------------------------------------------------------------------

# forma -> (payback, TIR socio a.a., TIR negocio a.a., VPL socio, VPL negocio,
#           cheque total, mes do cheque, 1o mes de caixa operacional positivo,
#           acumulado M60, faturamento do ano 1, EBITDA do ano 1, EBITDA do mes 1)
DEC077: dict[str, tuple[float, ...]] = {
    SIM_FORMA_RAMPA_RETA: (
        31.0, 0.38980333133523914, 0.31739237238430995, 276103.238284283,
        312177.17579961044, 1142112.6247071032, 5, 6, 1645454.5567363773,
        2631281.5853913524, 696509.0805967503, -43464.46942978802,
    ),
    # Remedido com o MES 0 (emenda de 22/10/2026): o 1o mes de operacao e' o mes 0 do
    # estudo (80%). Antes: payback 25, TIR socio 56,30%, EBITDA do mes 1 R$ 37.346.
    SIM_FORMA_RAMPA_CURVA_UNI03: (
        25.0, 0.5411899347245155, 0.38257900431266045, 526240.8295748833,
        564211.2734843439, 899972.7780034468, 3, 4, 1924681.2209409254,
        3035849.4392342325, 1019752.7272994039, 63906.2017143704,
    ),
}
# alunos totais nos meses de OPERACAO 1/3/6/8/10/12 (na curva, meses de vida 0/2/5/7/9/11)
DEC077_ALUNOS = {
    SIM_FORMA_RAMPA_RETA: (725.5, 1176.5, 1853.0, 2304.0, 2304.0, 2304.0),
    SIM_FORMA_RAMPA_CURVA_UNI03: (1843.2, 1774.08, 2073.6, 2234.88, 2280.96, 2304.0),
}


@pytest.mark.parametrize("forma", sorted(DEC077))
def test_numeros_da_dec_075_no_golden(forma: str) -> None:
    r = _rodar(forma)
    op = _operacao(r)
    obtido = (
        r.payback_meses, r.tir_socio_anual, r.tir_negocio_anual, r.vpl_socio, r.vpl_negocio,
        r.cheque_total, r.mes_cheque_total, r.mes_caixa_operacional_positivo,
        r.acumulado_mes_final, sum(x["faturamento_mensal"] for x in op[:12]),
        sum(x["ebitda_mensal"] for x in op[:12]), op[0]["ebitda_mensal"],
    )
    esperado = DEC077[forma]
    assert obtido[0] == esperado[0]
    assert obtido[1] == pytest.approx(esperado[1], abs=RATE)
    assert obtido[2] == pytest.approx(esperado[2], abs=RATE)
    for i in (3, 4, 5, 8, 9, 10, 11):
        assert obtido[i] == pytest.approx(esperado[i], abs=CENTAVO), i
    assert (obtido[6], obtido[7]) == (esperado[6], esperado[7])
    assert tuple(op[m - 1]["alunos_total"] for m in (1, 3, 6, 8, 10, 12)) == pytest.approx(
        DEC077_ALUNOS[forma], abs=1e-9
    )


@pytest.mark.parametrize(
    ("forma", "menor_viavel"),
    [(SIM_FORMA_RAMPA_RETA, 2164), (SIM_FORMA_RAMPA_CURVA_UNI03, 2052)],
)
def test_menor_demanda_viavel_no_golden(forma: str, menor_viavel: int) -> None:
    """A curva baixa em 112 alunos a menor demanda que passa no veredito (payback <= 36 e
    margem >= 30%) — e' a medida da amarra do BLK-UNI-05 (mais aprovacoes). Era 127 antes
    do mes 0 (2037): a curva inteira passou a acontecer um mes mais tarde."""
    assert _rodar(forma, float(menor_viavel)).flag_viavel
    assert not _rodar(forma, float(menor_viavel - 1)).flag_viavel


# ---------------------------------------------------------------------------
# 6. Payload: `forma_rampa`
# ---------------------------------------------------------------------------

_BODY: dict[str, object] = {
    "lat": -23.5, "lng": -46.6, "m2": 1500, "aluguel": 30000, "demanda": 1600, "ticket": 177,
}


def test_payload_default_e_a_curva_e_ainda_aceita_a_reta() -> None:
    """MUDANCA DA EMENDA de 21/10/2026: sem `forma_rampa` sai a CURVA (antes, a reta). A
    reta segue ACEITA por compatibilidade da API publica (a tela nao a oferece)."""
    assert premissas_do_body(ViabilidadeIn(**_BODY)).forma_rampa == SIM_FORMA_RAMPA_CURVA_UNI03
    curva = premissas_do_body(ViabilidadeIn(**_BODY, forma_rampa="curva_uni03"))
    assert curva.forma_rampa == SIM_FORMA_RAMPA_CURVA_UNI03
    reta = premissas_do_body(ViabilidadeIn(**_BODY, forma_rampa="reta", rampa_meses=10))
    assert reta.forma_rampa == SIM_FORMA_RAMPA_RETA
    assert reta.maturacao_meses == 10


def test_payload_sem_forma_e_a_curva_de_hoje_e_a_reta_explicita_e_a_de_antes() -> None:
    """Sem `forma_rampa` o corpo vira EXATAMENTE as Premissas da curva escolhida (pico
    observado, a curva UNI-03 intacta). Com a reta explicita, as Premissas que o codigo
    anterior a DEC-077 montava (o default do nucleo)."""
    antes = Premissas(ticket_cheio=177.0, aluguel_mes=30_000.0, tickets_studios=())
    assert premissas_do_body(ViabilidadeIn(**_BODY, forma_rampa="reta")) == antes
    curva = premissas_do_body(ViabilidadeIn(**_BODY, forma_rampa="curva_uni03"))
    assert premissas_do_body(ViabilidadeIn(**_BODY)) == curva
    assert curva.curva_rampa == SIM_CURVA_RAMPA_UNI03
    # e a curva so' difere na forma
    assert replace(curva, forma_rampa=SIM_FORMA_RAMPA_RETA) == antes


def test_uma_constante_do_config_reverte_o_padrao(monkeypatch, pilot_app) -> None:
    """Achado 1 do revisor: o padrao tem UMA fonte, lida em tempo de chamada. Trocar
    `SIM_FORMA_RAMPA_PADRAO` (hoje a curva) de volta para a reta muda o corpo sem forma
    (tela sem escolha, API, PDF, planilha) e o eco do payload, que e' o que a tela mostra
    — inclusive no modo da demanda sugerida, que nao tem mais padrao proprio. A escolha
    explicita segue vencendo."""
    from motor_expansao.dimensionamento import config

    monkeypatch.setattr(config, "SIM_FORMA_RAMPA_PADRAO", SIM_FORMA_RAMPA_RETA)
    assert premissas_do_body(ViabilidadeIn(**_BODY)).forma_rampa == SIM_FORMA_RAMPA_RETA
    eco = pilot_app.viabilidade(pilot_app.ViabilidadeIn(**_BODY))["premissas"]
    assert eco["forma_rampa"] == SIM_FORMA_RAMPA_RETA
    assert eco["mes_maturidade_rampa"] == 8
    assert eco["mes_pico_rampa"] is None
    curva = premissas_do_body(ViabilidadeIn(**_BODY, forma_rampa="curva_uni03"))
    assert curva.forma_rampa == SIM_FORMA_RAMPA_CURVA_UNI03


def test_caminhos_legados_seguem_a_mesma_constante(monkeypatch) -> None:
    """Achado 4 da revisao de 2026-10-20: `_premissas_do_ponto` (dashboard, backtest,
    batch) usava o default do DATACLASS e ficaria na reta com a constante trocada. Hoje
    sai a reta (nada muda); com a constante trocada, a curva. Escolha explicita vence, e
    `rampa_apenas_balcao` (so' a reta e' suportada) nao quebra."""
    from motor_expansao.dimensionamento import config
    from motor_expansao.dimensionamento.viabilidade_ponto import _premissas_do_ponto

    # Desde a emenda de 21/10/2026 o padrao e' a curva tambem nestes caminhos.
    hoje = _premissas_do_ponto(147.0, 30000.0, 0.6, None, {})
    assert hoje.forma_rampa == SIM_FORMA_RAMPA_CURVA_UNI03
    # com o padrao na curva, o modo legado "apenas balcao" (so' a reta e' suportada) nao quebra
    balcao = _premissas_do_ponto(147.0, 30000.0, 0.6, None, {"rampa_apenas_balcao": True})
    assert balcao.forma_rampa == SIM_FORMA_RAMPA_RETA

    monkeypatch.setattr(config, "SIM_FORMA_RAMPA_PADRAO", SIM_FORMA_RAMPA_RETA)
    assert _premissas_do_ponto(147.0, 30000.0, 0.6, None, {}).forma_rampa == SIM_FORMA_RAMPA_RETA
    escolhida = _premissas_do_ponto(
        147.0, 30000.0, 0.6, None, {"forma_rampa": "curva_uni03"}
    )
    assert escolhida.forma_rampa == SIM_FORMA_RAMPA_CURVA_UNI03
    so_balcao = _premissas_do_ponto(147.0, 30000.0, 0.6, None, {"rampa_apenas_balcao": True})
    assert so_balcao.forma_rampa == SIM_FORMA_RAMPA_RETA


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
    padrao = pilot_app.viabilidade(pilot_app.ViabilidadeIn(**_BODY))["premissas"]
    assert padrao["forma_rampa"] == "curva_uni03"  # a curva desde a emenda de 21/10/2026
    assert padrao["mes_maturidade_rampa"] == 11  # mes de OPERACAO = pico + 1
    assert padrao["mes_pico_rampa"] == 10  # mes de VIDA
    assert padrao["curva_rampa"] == list(SIM_CURVA_RAMPA_UNI03)

    curva = pilot_app.viabilidade(
        pilot_app.ViabilidadeIn(**_BODY, forma_rampa="curva_uni03")
    )["premissas"]
    assert curva == padrao
    assert curva["maturacao_meses"] == 8  # parametro da reta, ecoado mas sem efeito

    reta = pilot_app.viabilidade(
        pilot_app.ViabilidadeIn(**_BODY, forma_rampa="reta", rampa_meses=6)
    )["premissas"]
    assert reta["forma_rampa"] == "reta"
    assert reta["mes_maturidade_rampa"] == 6
    assert reta["curva_rampa"] is None
    assert reta["mes_pico_rampa"] is None


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
    for k, f in enumerate(SIM_CURVA_RAMPA_UNI03):  # rotulo por mes de VIDA, como no estudo
        row = _linha_premissa(ws, f"Curva observada — mês {k}" + (" (inauguração)" if k == 0 else ""))
        assert ws.cell(row=row, column=2).value == f
    mes_mat = ws.cell(
        row=_linha_premissa(ws, "Mês de operação em que a rampa termina"), column=2
    ).value
    # a regra do motor (PRIMEIRO mes com 100%), nao a contagem de meses abaixo de 100%
    assert isinstance(mes_mat, str) and "COUNTIF" not in mes_mat and ">=1" in mes_mat


def _rotulos(ws) -> list[str]:
    return [
        str(ws.cell(row=r, column=c).value)
        for r in range(1, ws.max_row + 1)
        for c in range(1, min(ws.max_column, 8) + 1)
        if isinstance(ws.cell(row=r, column=c).value, str)
    ]


def test_xlsx_da_reta_nao_tem_nada_da_curva() -> None:
    """A planilha de quem nao pediu a curva e' a de antes da DEC-077: sem a premissa
    "Forma da rampa", sem o bloco da curva, sem a validacao de lista e sem os nomes novos.
    (O snapshot contra a `origin/main` confirmou o arquivo inteiro igual membro a membro.)"""
    wb = openpyxl.load_workbook(BytesIO(gerar_simulador_xlsx(DEMANDA, _premissas(), **INVEST)))
    ws = wb[ABA_PREMISSAS]
    textos = _rotulos(ws)
    assert "Forma da rampa" not in textos
    assert not any(t.startswith("Curva observada") for t in textos)
    assert "Mês em que a rampa termina" not in textos
    assert not any("curva observada" in str(dv.formula1) for dv in ws.data_validations.dataValidation)
    assert not {"prem_forma_rampa", "prem_mes_mat_rampa"} & set(wb.defined_names)
    # e os textos do mes 1 sao os de antes (validos na reta)
    assert "(é por isso que o EBITDA do mês 1 é bem negativo)" in " ".join(_rotulos(wb[ABA_DRE]))
    assert "EBITDA do mês 1 (negativo por construção)" in _rotulos(wb[ABA_AFERICAO])


def test_xlsx_da_curva_nao_afirma_ebitda_negativo_no_mes_1(blob_curva: bytes) -> None:
    """Achado 2 do revisor: na curva o golden da +R$ 37.346 no mes 1. A planilha da curva
    (que troca de forma pela celula) nao pode afirmar "negativo por construcao"."""
    wb = openpyxl.load_workbook(BytesIO(blob_curva))
    tudo = " ".join(t for aba in wb.worksheets for t in _rotulos(aba))
    assert "negativo por construção" not in tudo.lower()
    assert "é bem negativo)" not in tudo
    assert "pode sair positivo" in " ".join(_rotulos(wb[ABA_DRE]))
    assert "EBITDA do mês 1 (início da rampa)" in _rotulos(wb[ABA_AFERICAO])


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


def test_xlsx_fim_da_rampa_e_o_primeiro_mes_cheio_como_no_motor(
    blob_curva: bytes, tmp_path: Path
) -> None:
    """Achado 5 do revisor: a celula da curva e' editavel. Com o mes de vida 11 digitado
    abaixo de 100% DEPOIS do mes 10 cheio, a contagem antiga (`COUNTIF(<1)+1`) daria 12; a
    regra do motor (primeiro mes com 100%) da o mes de operacao 11 (= mes de vida 10). A
    planilha usa a regra do motor. A contagem tambem erraria pelo mes 0 (80%), que conta
    como abaixo de 100% sem ser o fim da rampa."""
    wb = openpyxl.load_workbook(BytesIO(blob_curva))
    ws = wb[ABA_PREMISSAS]
    ws.cell(row=_linha_premissa(ws, "Curva observada — mês 11"), column=2).value = 0.95
    buf = BytesIO()
    wb.save(buf)
    ler = _recalcular(buf.getvalue(), tmp_path)
    linha = _linha_premissa(ws, "Mês de operação em que a rampa termina")
    assert ler(ABA_PREMISSAS, f"B{linha}") == 11.0
    assert _premissas(forma_rampa=SIM_FORMA_RAMPA_CURVA_UNI03).mes_maturidade_rampa == 11


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


# ---------------------------------------------------------------------------
# 8. Sensibilidades e cenarios de fronteira citados na DEC-077 (golden)
# ---------------------------------------------------------------------------

# cenario -> (overrides das Premissas, overrides do investimento, forma -> (payback,))
_FRONTEIRA: dict[str, tuple[dict[str, object], dict[str, object], dict[str, tuple]]] = {
    "p10": ({}, {}, {SIM_FORMA_RAMPA_RETA: (float("inf"),), SIM_FORMA_RAMPA_CURVA_UNI03: (float("inf"),)}),
    "p90": ({}, {}, {SIM_FORMA_RAMPA_RETA: (18.0,), SIM_FORMA_RAMPA_CURVA_UNI03: (14.0,)}),
    "carencia_4": ({"carencia_aluguel_meses": 4}, {},
                   {SIM_FORMA_RAMPA_RETA: (28.0,), SIM_FORMA_RAMPA_CURVA_UNI03: (23.0,)}),
    "equipamento_a_vista": ({}, {"prazo_equipamentos": 0},
                            {SIM_FORMA_RAMPA_RETA: (33.0,), SIM_FORMA_RAMPA_CURVA_UNI03: (30.0,)}),
    "sem_anuidade": ({"anuidade_valor": 0.0}, {},
                     {SIM_FORMA_RAMPA_RETA: (32.0,), SIM_FORMA_RAMPA_CURVA_UNI03: (26.0,)}),
    "franquia_a_vista": ({}, {"parcelas_franquia": 1},
                         {SIM_FORMA_RAMPA_RETA: (31.0,), SIM_FORMA_RAMPA_CURVA_UNI03: (25.0,)}),
}
_DEMANDA_FRONTEIRA = {"p10": 1189.0, "p90": 3034.0}


@pytest.mark.parametrize("forma", [SIM_FORMA_RAMPA_RETA, SIM_FORMA_RAMPA_CURVA_UNI03])
@pytest.mark.parametrize("cenario", sorted(_FRONTEIRA))
def test_cenarios_de_fronteira_da_dec_075(cenario: str, forma: str) -> None:
    over_p, over_inv, esperado = _FRONTEIRA[cenario]
    r = simular(
        _DEMANDA_FRONTEIRA.get(cenario, DEMANDA),
        _premissas(forma_rampa=forma, **over_p),
        **{**INVEST, **over_inv},  # type: ignore[arg-type]
    )
    assert r.payback_meses == esperado[forma][0]


def test_sensibilidade_curva_de_faturamento_no_lugar_da_de_alunos() -> None:
    """A curva de FATURAMENTO da P1 (52% ... 102%) pelas mesmas tres regras, aplicada como
    se fosse a de alunos: payback 28 e TIR do socio 46,4% (a DEC cita, nao e' o modelo)."""
    bruta = (0.52, 0.64, 0.75, 0.77, 0.83, 0.85, 0.87, 0.90, 0.95, 0.94, 0.98, 1.02)
    derivada, maximo = [], 0.0
    for f in bruta:
        maximo = max(maximo, f)
        derivada.append(min(maximo, 1.0))
    r = _rodar(SIM_FORMA_RAMPA_CURVA_UNI03, curva_rampa=tuple(derivada))
    assert r.payback_meses == 28.0
    assert r.tir_socio_anual == pytest.approx(0.464, abs=0.0005)


def test_sensibilidade_reta_recalibrada_do_estudo() -> None:
    """A reta recalibrada da UNI-03 (62% do nivel maduro no mes 1 da forma do simulador,
    100% no mes 8): payback 26 e TIR do socio 53,2% — quase a historia da curva."""
    r = _rodar(SIM_FORMA_RAMPA_RETA, alunos_inicial=0.62 * DEMANDA, maturacao_meses=8)
    assert r.payback_meses == 26.0
    assert r.tir_socio_anual == pytest.approx(0.532, abs=0.0005)
