"""Motor de diagnostico da rede (BLK-EXEC-03).

O risco que estes testes cobrem nao e' "a conta esta errada" -- e' "a tela vira ruido".
Uma fila com 85% da rede dentro (o que o corte por quartil produzia) nao e' fila, e o time
de campo volta para a planilha. Por isso ha um teste de BANDA, e nao so de limiar.
"""

from __future__ import annotations

import re

import pandas as pd
import pytest

from motor_expansao.dashboard import rede_diagnostico as rd
from tests.unit.rede_fixtures import fechamento_sintetico


def _linha(**valores: object) -> pd.DataFrame:
    """Um unico unidade-mes fechado, saudavel por padrao, com o que for sobrescrito."""
    padrao: dict[str, object] = {
        "unidade_id": "u1",
        "unidade_cru": "UNIDADE 1",
        "competencia": "2026-07",
        "mes_completo": True,
        "operacao_mes_cheio": True,
        "faturamento": 200_000.0,
        "churn_pct": 4.0,
        "conversao_pct": 60.0,
        "nps": 75.0,
        "pct_agregador_alunos": 30.0,
        "saldo_operacional": 50.0,
    }
    padrao.update(valores)
    return pd.DataFrame([padrao])


def _codigos(fech: pd.DataFrame, competencia: str = "2026-07") -> set[str]:
    diag = rd.diagnosticar(fech, competencia)
    return {a.codigo for d in diag.values() for a in d.alertas}


# ---------------------------------------------------------------------------
# Matriz regua x (abaixo, na regua, acima)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "codigo, coluna, abaixo, na_regua, acima, acende_acima",
    [
        ("churn", "churn_pct", 7.9, rd.REGUA_CHURN_PCT, 8.1, True),
        ("conversao", "conversao_pct", 39.9, rd.REGUA_CONVERSAO_PCT, 40.1, False),
        ("nps", "nps", 39.9, rd.REGUA_NPS, 40.1, False),
        (
            "agregador",
            "pct_agregador_alunos",
            69.9,
            rd.REGUA_DEPENDENCIA_AGREGADOR_PCT,
            70.1,
            True,
        ),
    ],
)
def test_matriz_de_reguas(
    codigo: str, coluna: str, abaixo: float, na_regua: float, acima: float, acende_acima: bool
) -> None:
    """A regua e' um corte estrito: EM CIMA dela nao acende, so do lado errado."""
    assert (codigo in _codigos(_linha(**{coluna: acima}))) is acende_acima
    assert (codigo in _codigos(_linha(**{coluna: abaixo}))) is (not acende_acima)
    assert codigo not in _codigos(_linha(**{coluna: na_regua})), (
        "estar exatamente na regua nao e' violacao"
    )


def test_saldo_negativo_exige_persistencia() -> None:
    """Um mes ruim nao e' alerta; tres meses fechados seguidos, sim.

    E' o mecanismo que separa oscilacao de deterioracao -- e o que impede a fila de encher
    toda vez que um mes vem fraco.
    """
    def serie(saldos: list[float]) -> pd.DataFrame:
        meses = ["2026-05", "2026-06", "2026-07"][-len(saldos) :]
        return pd.concat(
            [_linha(competencia=c, saldo_operacional=s) for c, s in zip(meses, saldos, strict=True)],
            ignore_index=True,
        )

    assert "saldo" not in _codigos(serie([50.0, 50.0, -10.0]))
    assert "saldo" not in _codigos(serie([50.0, -10.0, -10.0]))
    assert "saldo" in _codigos(serie([-10.0, -10.0, -10.0]))


def test_queda_de_faturamento_compara_com_a_media_de_tres_meses() -> None:
    meses = ["2026-04", "2026-05", "2026-06", "2026-07"]
    estavel = pd.concat([_linha(competencia=c) for c in meses], ignore_index=True)
    assert "queda_faturamento" not in _codigos(estavel)

    caiu = pd.concat(
        [_linha(competencia=c, faturamento=v) for c, v in zip(meses, [200_000.0] * 3 + [150_000.0], strict=True)],
        ignore_index=True,
    )
    assert "queda_faturamento" in _codigos(caiu)


def test_meta_de_nps_nao_e_regua_de_alerta() -> None:
    """`NPS_IDEAL = 60` e' meta oficial exibida; o alerta dispara bem mais abaixo.

    38% da rede esta abaixo de 60 -- numero certo para uma linha de referencia no grafico,
    errado para uma fila de visita.
    """
    assert rd.META_NPS == 60.0
    assert rd.REGUA_NPS < rd.META_NPS
    assert "nps" not in _codigos(_linha(nps=55.0))


def test_metricas_a_validar_nunca_alertam() -> None:
    """`inadimplente` e `treino_ativo` nao tem denominador confirmado com a Growth.

    Alertar sobre um numero que nao se sabe ler manda o time visitar unidade por causa de
    erro de leitura nossa.
    """
    proibidas = rd.metricas_proibidas_em_alerta()
    assert proibidas == frozenset({"inadimplente", "treino_ativo"})
    absurdo = _linha(inadimplente=99_999.0, treino_ativo=9_999.0)
    assert not _codigos(absurdo)
    for regua in rd.REGUAS_VIGENTES.values():
        assert regua["metrica"] not in proibidas


# ---------------------------------------------------------------------------
# Severidade e fila
# ---------------------------------------------------------------------------


def test_severidade_um_grave_ou_tres_medios() -> None:
    assert rd.diagnosticar(_linha(), "2026-07")["u1"].severidade == "ok"
    assert rd.diagnosticar(_linha(churn_pct=8.5), "2026-07")["u1"].severidade == "media"
    assert rd.diagnosticar(_linha(churn_pct=15.0), "2026-07")["u1"].severidade == "alta"
    dois_medios = _linha(churn_pct=8.5, conversao_pct=35.0)
    assert rd.diagnosticar(dois_medios, "2026-07")["u1"].severidade == "media"
    tres_medios = _linha(churn_pct=8.5, conversao_pct=35.0, nps=30.0)
    assert rd.diagnosticar(tres_medios, "2026-07")["u1"].severidade == "alta"


def test_banda_alvo_da_fila_acionavel() -> None:
    """Teste-GUARDIAO: a fatia `alta` tem de caber numa semana de trabalho de campo.

    Roda sobre uma rede sintetica com a mesma distribuicao marginal da producao (quantis
    medidos em jul/2026, ver `rede_fixtures.QUANTIS_PRODUCAO`). Se alguem afrouxar uma
    regua ou baixar `MEDIOS_PARA_ALTA`, a fatia estoura a banda e o CI reprova ANTES de a
    tela virar parede cinza.
    """
    fech = fechamento_sintetico()
    diag = rd.diagnosticar(fech, "2026-07")
    comparaveis = [d for d in diag.values() if d.severidade != "sem_base"]
    fatia = sum(1 for d in comparaveis if d.severidade == "alta") / len(comparaveis)
    piso, teto = rd.BANDA_ALVO_ALTA
    assert piso <= fatia <= teto, (
        f"fatia 'alta' em {fatia:.0%} fora da banda {piso:.0%}-{teto:.0%}: "
        "a fila deixou de ser acionavel"
    )
    # ...e a rede nao pode ficar TODA limpa: um motor que nunca acende tambem e' inutil.
    assert any(d.severidade != "ok" for d in comparaveis)


def test_unidade_inaugurada_no_mes_nao_recebe_alerta() -> None:
    nova = _linha(operacao_mes_cheio=False, churn_pct=30.0, nps=-50.0)
    diagnostico = rd.diagnosticar(nova, "2026-07")["u1"]
    assert diagnostico.severidade == "sem_base"
    assert diagnostico.alertas == ()
    assert diagnostico.prioridade == 0.0


def test_prioridade_ordena_por_gravidade_antes_do_porte() -> None:
    """Tamanho e' desempate, nunca inversao: 1 grave numa unidade pequena vem antes de
    1 medio numa grande."""
    fech = pd.concat(
        [
            _linha(unidade_id="grande", faturamento=700_000.0, churn_pct=8.5),
            _linha(unidade_id="pequena", faturamento=30_000.0, churn_pct=15.0),
        ],
        ignore_index=True,
    )
    diag = rd.diagnosticar(fech, "2026-07")
    assert diag["pequena"].prioridade > diag["grande"].prioridade


def test_faixa_de_faturamento_e_a_do_time_de_campo() -> None:
    assert rd.faixa_faturamento(149_000)[1] == "Crítico"
    assert rd.faixa_faturamento(199_000)[1] == "Regular"
    assert rd.faixa_faturamento(249_000)[1] == "Bom"
    assert rd.faixa_faturamento(299_000)[1] == "Excelente"
    assert rd.faixa_faturamento(500_000)[1] == "Excelente+"
    assert rd.faixa_faturamento(None)[0] == "sem_dado"


# ---------------------------------------------------------------------------
# Contrato de texto e de pureza
# ---------------------------------------------------------------------------


def _textos_de_usuario() -> list[str]:
    """Toda string do motor que chega aos olhos de alguem (payload, tela, CSV, PDF)."""
    fech = fechamento_sintetico(unidades=40)
    textos: list[str] = [rd.ROTULO_SEVERIDADE[s] for s in rd.SEVERIDADES]
    textos += [str(r["rotulo"]) for r in rd.REGUAS_VIGENTES.values()]
    textos += [str(r.get("unidade", "")) for r in rd.REGUAS_VIGENTES.values()]
    textos += [rotulo for _, _, rotulo in rd.FAIXAS_FATURAMENTO]
    for diagnostico in rd.diagnosticar(fech, "2026-07").values():
        textos.append(diagnostico.resumo)
        textos.extend(a.titulo for a in diagnostico.alertas)
        textos.extend(a.detalhe for a in diagnostico.alertas)
        textos.extend(r.titulo for r in diagnostico.recomendacoes)
        textos.extend(r.corpo for r in diagnostico.recomendacoes)
    return textos


# Palavras que em portugues SEMPRE levam acento. Ficam de fora as ambiguas ("sao"
# aparece em nome cru de unidade, que e' dado e nao texto) e as que existem sem acento
# noutro sentido.
_SEMPRE_ACENTUADAS = (
    "nao", "mes", "regua", "reguas", "periodo", "conversao", "dependencia", "diagnostico",
    "numero", "numeros", "critico", "inadimplencia", "retencao", "decisao", "manutencao",
    "migracao", "reativacao", "estavel", "evitavel", "saida", "cobranca", "tres", "corroi",
    "comparavel", "comparaveis", "atencao", "comparacao", "media", "ja", "esta", "ha",
    "e'",
)


def test_textos_de_usuario_sao_acentuados() -> None:
    """Regra permanente do `CLAUDE.md` §2: texto de usuario leva acentuacao correta.

    Acento portugues cabe inteiro em latin-1, entao a exigencia do PDF (ver o teste
    seguinte) nunca foi motivo para escrever "nao" e "mes" na tela. O que o PDF proibe e'
    a TIPOGRAFIA fora de latin-1, nao o acento.

    Identificadores (chaves de payload, codigos de alerta, valores de enum) continuam SEM
    acento de proposito -- so o que e' exibido passa por aqui.
    """
    padrao = re.compile(r"\b(?:" + "|".join(re.escape(p) for p in _SEMPRE_ACENTUADAS) + r")\b")
    ofensas = sorted(
        {(m, texto[:70]) for texto in _textos_de_usuario() for m in padrao.findall(texto.lower())}
    )
    assert not ofensas, f"texto de usuario sem acento (CLAUDE.md §2): {ofensas[:6]}"


def test_textos_sobrevivem_a_latin1() -> None:
    """O MESMO texto vai para o JSON (UTF-8) e para o PDF (fpdf2, core font latin-1).

    Fora de latin-1, o fpdf2 troca por "?" em SILENCIO -- travessao, bullet, seta,
    reticencias unicode e aspas curvas sao os reincidentes. Acento portugues passa; o que
    nao pode e' a tipografia.
    """
    fech = fechamento_sintetico(unidades=40)
    textos: list[str] = [
        rd.ROTULO_SEVERIDADE[s] for s in rd.SEVERIDADES
    ] + [str(r["rotulo"]) for r in rd.REGUAS_VIGENTES.values()]
    for diagnostico in rd.diagnosticar(fech, "2026-07").values():
        textos.append(diagnostico.resumo)
        textos.extend(a.titulo for a in diagnostico.alertas)
        textos.extend(a.detalhe for a in diagnostico.alertas)
        textos.extend(r.titulo for r in diagnostico.recomendacoes)
        textos.extend(r.corpo for r in diagnostico.recomendacoes)
    assert len(textos) > 20, "a matriz de textos ficou vazia - o teste seria vacuo"
    for texto in textos:
        texto.encode("latin-1")  # levanta UnicodeEncodeError se houver caractere proibido


def test_diagnosticar_e_pura() -> None:
    """Nao muta a entrada e devolve o mesmo resultado duas vezes seguidas."""
    fech = fechamento_sintetico(unidades=20)
    antes = fech.copy(deep=True)
    primeiro = rd.diagnosticar(fech, "2026-07")
    segundo = rd.diagnosticar(fech, "2026-07")
    pd.testing.assert_frame_equal(fech, antes)
    assert {k: v.severidade for k, v in primeiro.items()} == {
        k: v.severidade for k, v in segundo.items()
    }


def test_competencia_base_nunca_e_mes_aberto() -> None:
    """No dia 2 do mes, o acumulado de dois dias acenderia queda na rede inteira."""
    fech = pd.concat(
        [
            _linha(competencia="2026-06"),
            _linha(competencia="2026-07"),
            _linha(competencia="2026-08", mes_completo=False),
        ],
        ignore_index=True,
    )
    assert rd.competencia_base(fech) == "2026-07"
    assert rd.competencia_base(fech, competencia="2026-06") == "2026-06"
    assert rd.competencia_base(pd.DataFrame()) is None


def test_reguas_vigentes_sao_servidas_inteiras() -> None:
    """A tela mostra a regua que o motor aplica -- nao ha um segundo lugar onde editar."""
    for chave, regua in rd.REGUAS_VIGENTES.items():
        assert {"rotulo", "metrica", "sentido", "limiar"} <= set(regua)
        assert isinstance(regua["limiar"], float)
        assert chave in rd._RECOMENDACOES, f"regua {chave} sem recomendacao correspondente"
