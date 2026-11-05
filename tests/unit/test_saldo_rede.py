"""Saldo semanal por rede a partir do histórico de contagem do coletor.

As fixtures são sintéticas, mas os CASOS são reais e medidos no arquivo de produção
(`/opt/gymscraping-infra/historico_contagem.csv`, 1.428 linhas de dado em 2026-09-22):

  * **a Selfit de 2026-09-13** — `231 -> 119` (**-48,5%**) com `data_coleta` voltando para
    `2026-05-26`, que é o baseline do repositório reaparecendo depois de o lote morrer no coletor
    #28 de 90. É o incidente que a DEC-061 registra, e aqui ele é o teste da guarda;
  * **o universo que cresce** — 90 redes em junho, 107 em setembro, 17 entrando depois de 19/07;
  * **a defasagem normal** — 154 das 1.428 linhas (10,8%) já nascem com `data_coleta` anterior à
    execução, o que é a razão de ela ser agravante e não gatilho;
  * **a execução fora de domingo** — `2026-07-22` é quarta.

READ-ONLY sobre o M1.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from motor_expansao.dashboard import saldo_rede as s


def _escrever_historico(caminho: Path, linhas: list[tuple[str, str, int, str]]) -> Path:
    """Escreve o CSV no formato REAL do coletor, com CRLF de propósito.

    O CRLF não é capricho de fixture: foi o `\\r` no último campo que fez a primeira medição desta
    análise contar 1.428 de 1.428 linhas como defasadas, quando são 154. Se o leitor regredir e
    parar de fazer `strip`, é aqui que se descobre.
    """
    caminho.parent.mkdir(parents=True, exist_ok=True)
    corpo = "data_execucao;rede;unidades;data_coleta\r\n" + "".join(
        f"{d};{r};{n};{c}\r\n" for d, r, n, c in linhas
    )
    caminho.write_text(corpo, encoding="utf-8")
    return caminho


# --------------------------------------------------------------------------- #
# Leitura
# --------------------------------------------------------------------------- #
def test_leitura_tira_o_cr_e_tipa(tmp_path: Path) -> None:
    caminho = _escrever_historico(
        tmp_path / "hist.csv",
        [
            ("2026-09-13", "selfit", 119, "2026-05-26"),
            ("2026-09-13", "smart_fit", 500, "2026-09-13"),
        ],
    )
    hist = s.ler_historico_contagem(caminho)

    assert list(hist.columns) == list(s.CONTRATO_COLUNAS_HISTORICO)
    assert hist["unidades"].dtype == "int64"
    # O teste que pega a regressão do `\r`: sem strip, isto viria "2026-09-13\r" e a comparação
    # com a data de execução falharia em TODA linha.
    assert set(hist["data_coleta"]) == {"2026-05-26", "2026-09-13"}


def test_csv_com_BOM_e_lido_sem_sujar_o_header(tmp_path: Path) -> None:
    """Achado da revisão automática no PR #393, travado.

    O arquivo da VPS hoje não tem BOM, mas o padrão de CSV do projeto é `utf-8-sig` e os módulos
    irmãos que leem feed de coletor já o aplicam. Com `utf-8` puro e BOM, o header vira
    `\\ufeffdata_execucao`: a coluna "não existe", e o erro acusa o CONTRATO — apontando para o
    lugar errado, longe da causa. É a mesma família do defeito que o `\\r` já produziu aqui.
    """
    caminho = tmp_path / "hist_bom.csv"
    caminho.write_text(
        "﻿data_execucao;rede;unidades;data_coleta\r\n2026-09-20;selfit;231;2026-09-20\r\n",
        encoding="utf-8",
    )
    hist = s.ler_historico_contagem(caminho)

    assert list(hist.columns) == list(s.CONTRATO_COLUNAS_HISTORICO)
    assert str(hist.iloc[0]["rede"]) == "selfit"


def test_data_coleta_vazia_sobrevive_como_vazia(tmp_path: Path) -> None:
    """Coletor que não devolveu nada != coletado hoje. São 12 linhas assim em produção."""
    caminho = _escrever_historico(
        tmp_path / "hist.csv", [("2026-06-29", "a_melhor_academia", 0, "")]
    )
    hist = s.ler_historico_contagem(caminho)
    assert str(hist.iloc[0]["data_coleta"]) == ""
    assert int(hist.iloc[0]["unidades"]) == 0


def test_execucao_duplicada_levanta(tmp_path: Path) -> None:
    """O histórico é append-only; a mesma execução duas vezes falsearia a semana inteira."""
    caminho = _escrever_historico(
        tmp_path / "hist.csv",
        [("2026-09-20", "selfit", 231, "2026-09-20"), ("2026-09-20", "selfit", 231, "2026-09-20")],
    )
    with pytest.raises(ValueError, match="duplicado"):
        s.ler_historico_contagem(caminho)


# --------------------------------------------------------------------------- #
# Execucoes e pivot
# --------------------------------------------------------------------------- #
def test_so_domingos_filtra_a_execucao_de_quarta(tmp_path: Path) -> None:
    """`2026-07-22` é quarta-feira — caso REAL da série de produção."""
    caminho = _escrever_historico(
        tmp_path / "hist.csv",
        [
            ("2026-07-19", "selfit", 231, "2026-07-19"),
            ("2026-07-22", "selfit", 231, "2026-07-22"),
            ("2026-07-26", "selfit", 231, "2026-07-26"),
        ],
    )
    hist = s.ler_historico_contagem(caminho)

    assert s.execucoes(hist) == ["2026-07-19", "2026-07-22", "2026-07-26"]
    assert s.execucoes(hist, so_domingos=True) == ["2026-07-19", "2026-07-26"]


def test_pivot_deixa_NULO_a_rede_que_nao_existia(tmp_path: Path) -> None:
    """Nulo != zero. Zero é coletor que voltou vazio; nulo é rede fora da cobertura.

    Preencher com zero faria as 17 redes que entraram depois de julho parecerem ter fechado todas
    as unidades e reaberto na semana seguinte.
    """
    caminho = _escrever_historico(
        tmp_path / "hist.csv",
        [
            ("2026-07-19", "selfit", 231, "2026-07-19"),
            ("2026-09-20", "selfit", 231, "2026-09-20"),
            ("2026-09-20", "gofit", 12, "2026-09-20"),  # entrou depois
            ("2026-09-20", "vazia", 0, ""),  # mapeada, coletor voltou vazio
        ],
    )
    largo = s.pivot_contagem(s.ler_historico_contagem(caminho))

    assert pd.isna(largo.loc["gofit", "2026-07-19"]), "rede fora da cobertura tem de ser NULA"
    assert int(largo.loc["vazia", "2026-09-20"]) == 0, "coletor vazio e' ZERO, nao nulo"
    assert int(largo.loc["selfit", "2026-09-20"]) == 231


# --------------------------------------------------------------------------- #
# Saldo
# --------------------------------------------------------------------------- #
def test_rede_nova_nao_vira_saldo_positivo(tmp_path: Path) -> None:
    """Ampliação de COBERTURA do coletor não é crescimento de mercado.

    As 17 redes que entraram depois de 19/07 somam centenas de unidades; contá-las como `delta`
    positivo inventaria um salto de mercado que não houve.
    """
    caminho = _escrever_historico(
        tmp_path / "hist.csv",
        [
            ("2026-07-19", "selfit", 231, "2026-07-19"),
            ("2026-09-20", "selfit", 234, "2026-09-20"),
            ("2026-09-20", "gofit", 12, "2026-09-20"),
        ],
    )
    saldo = s.saldo_entre_execucoes(
        s.ler_historico_contagem(caminho), de="2026-07-19", ate="2026-09-20"
    )

    gofit = saldo[saldo["rede"] == "gofit"].iloc[0]
    assert str(gofit["status"]) == "novo"
    assert pd.isna(gofit["delta"]), "rede nova nao pode entrar no somatorio do saldo"

    selfit = saldo[saldo["rede"] == "selfit"].iloc[0]
    assert int(selfit["delta"]) == 3
    assert str(selfit["status"]) == "variou"
    # O saldo do periodo e' a soma dos COMPARAVEIS: +3, nao +15.
    assert int(saldo["delta"].sum()) == 3


def test_rede_que_some_fica_com_delta_nulo(tmp_path: Path) -> None:
    caminho = _escrever_historico(
        tmp_path / "hist.csv",
        [
            ("2026-07-19", "extinta", 9, "2026-07-19"),
            ("2026-07-19", "selfit", 231, "2026-07-19"),
            ("2026-09-20", "selfit", 231, "2026-09-20"),
        ],
    )
    saldo = s.saldo_entre_execucoes(
        s.ler_historico_contagem(caminho), de="2026-07-19", ate="2026-09-20"
    )
    extinta = saldo[saldo["rede"] == "extinta"].iloc[0]
    assert str(extinta["status"]) == "sumiu"
    assert pd.isna(extinta["delta"])
    assert str(saldo[saldo["rede"] == "selfit"].iloc[0]["status"]) == "estavel"


def test_execucao_inexistente_levanta(tmp_path: Path) -> None:
    caminho = _escrever_historico(tmp_path / "hist.csv", [("2026-09-20", "selfit", 231, "")])
    hist = s.ler_historico_contagem(caminho)
    with pytest.raises(ValueError, match="nao existe"):
        s.saldo_entre_execucoes(hist, de="2026-01-01", ate="2026-09-20")


# --------------------------------------------------------------------------- #
# Guarda de coleta parcial (DEC-061)
# --------------------------------------------------------------------------- #
def _historico_do_incidente(tmp_path: Path) -> pd.DataFrame:
    """A foto de 2026-09-13: Selfit 231 -> 119, com `data_coleta` de maio."""
    linhas = [("2026-09-06", "selfit", 231, "2026-09-06"), ("2026-09-13", "selfit", 119, "2026-05-26")]
    # Enchimento com PROPORCAO realista, e o numero importa: no incidente o feed tinha ~4.600
    # unidades, a Selfit perdeu 112 e o TOTAL caiu so' **2,5%**. Uma fixture pequena demais faz a
    # queda da Selfit arrastar o total e o teste passa a medir a regua ERRADA -- foi exatamente o
    # que aconteceu na 1a versao deste arquivo (13 redes, total -15,75%, acima do limite de 10%).
    # Com 30 redes de 40, o total vai a 1.431 e cai 7,8%: abaixo do limiar, como no caso real.
    for i in range(30):
        linhas.append(("2026-09-06", f"rede_{i}", 40, "2026-09-06"))
        linhas.append(("2026-09-13", f"rede_{i}", 40, "2026-09-13"))
    return s.ler_historico_contagem(_escrever_historico(tmp_path / "hist.csv", linhas))


def test_guarda_pega_a_selfit_de_13_09(tmp_path: Path) -> None:
    """O caso que a DEC-061 registra — e a razão de a régua ser POR REDE.

    Naquele domingo o total mal se moveu (as outras redes ficaram com a contagem anterior), então
    um limiar de total não pegaria. O colapso por rede é a assinatura.
    """
    laudo = s.avaliar_queda_da_execucao(_historico_do_incidente(tmp_path), execucao="2026-09-13")

    assert laudo["aprovado"] is False
    assert laudo["referencia"] == "2026-09-06"
    desabaram = laudo["redes_que_desabaram"]
    assert isinstance(desabaram, list) and len(desabaram) == 1
    assert desabaram[0]["rede"] == "selfit"
    assert desabaram[0]["queda_pct"] == pytest.approx(48.5, abs=0.1)
    # O AGRAVANTE: coleta de maio numa execucao de setembro = baseline do repositorio.
    assert desabaram[0]["coleta_defasada"] is True
    assert any("coleta DEFASADA" in m for m in laudo["motivos"])
    # E o total, sozinho, NAO teria reprovado.
    assert float(laudo["queda_total_pct"]) < s.TOLERANCIA_QUEDA_TOTAL_PCT


def test_defasagem_sozinha_nao_reprova(tmp_path: Path) -> None:
    """A propriedade que a medição impôs: 10,8% das linhas já nascem defasadas.

    Se `data_coleta` velha reprovasse por si, a guarda barraria ~11% de toda semana — e o sinal
    viraria ruído no primeiro domingo.
    """
    caminho = _escrever_historico(
        tmp_path / "hist.csv",
        [
            ("2026-09-06", "aera_pilates", 33, "2026-05-26"),
            ("2026-09-13", "aera_pilates", 33, "2026-05-26"),
        ],
    )
    laudo = s.avaliar_queda_da_execucao(s.ler_historico_contagem(caminho), execucao="2026-09-13")

    assert laudo["aprovado"] is True
    assert laudo["motivos"] == []
    assert "aera_pilates" in laudo["redes_defasadas"], "mas ela CONTINUA visivel no diagnostico"


def test_rede_pequena_nao_dispara_a_regua_por_rede(tmp_path: Path) -> None:
    """Abaixo de `MIN_UNIDADES_GUARDA_REDE` uma unidade a menos já passa de 30%."""
    caminho = _escrever_historico(
        tmp_path / "hist.csv",
        [("2026-09-06", "minuscula", 3, "2026-09-06"), ("2026-09-13", "minuscula", 1, "2026-09-13")],
    )
    laudo = s.avaliar_queda_da_execucao(s.ler_historico_contagem(caminho), execucao="2026-09-13")
    assert laudo["aprovado"] is True


def test_primeira_execucao_passa_sem_referencia(tmp_path: Path) -> None:
    """A guarda mede QUEDA, não tamanho — não pode travar o começo da série."""
    caminho = _escrever_historico(tmp_path / "hist.csv", [("2026-06-29", "selfit", 229, "2026-06-29")])
    laudo = s.avaliar_queda_da_execucao(s.ler_historico_contagem(caminho), execucao="2026-06-29")
    assert laudo["aprovado"] is True
    assert laudo["referencia"] is None


def test_queda_difusa_reprova_pelo_total(tmp_path: Path) -> None:
    """A rede de segurança: muitas redes perdendo pouco passa por rede e some no total."""
    linhas = []
    for i in range(10):
        linhas.append(("2026-09-06", f"rede_{i}", 20, "2026-09-06"))
        linhas.append(("2026-09-13", f"rede_{i}", 15, "2026-09-13"))  # -25%: abaixo dos 30%
    laudo = s.avaliar_queda_da_execucao(
        s.ler_historico_contagem(_escrever_historico(tmp_path / "hist.csv", linhas)),
        execucao="2026-09-13",
    )
    assert laudo["aprovado"] is False
    assert any("total caiu" in m for m in laudo["motivos"])


def test_o_total_que_reprova_por_si_fica_marcado_e_a_rede_sozinha_nao(tmp_path: Path) -> None:
    """A tela escreve "o total caiu" só quando foi o TOTAL que reprovou, não quando foi uma rede."""
    difusa = []
    for i in range(10):
        difusa.append(("2026-09-06", f"rede_{i}", 20, "2026-09-06"))
        difusa.append(("2026-09-13", f"rede_{i}", 15, "2026-09-13"))
    laudo = s.avaliar_queda_da_execucao(
        s.ler_historico_contagem(_escrever_historico(tmp_path / "difusa.csv", difusa)),
        execucao="2026-09-13",
    )
    assert laudo["queda_total_reprovou"] is True
    selfit = s.avaliar_queda_da_execucao(_historico_do_incidente(tmp_path), execucao="2026-09-13")
    assert selfit["queda_total_reprovou"] is False


def test_guarda_conta_a_rede_ausente_como_zero(tmp_path: Path) -> None:
    """A régua da DEC-061 (`snapshots.py`, `c_agora.get(rede, 0)`): perder a rede inteira é o caso
    extremo de coleta parcial. Vale para o laudo de diagnóstico `avaliar_queda_da_execucao`, que o
    card não chama: no card a rede ausente fica uma semana e sai (`test_rede_ausente_fica_uma_semana_e_depois_sai`)."""
    linhas = [(d, f"rede_{i}", 40, d) for d in ("2026-10-25",) for i in range(30)]
    linhas += [(d, f"rede_{i}", 40, d) for d in ("2026-11-01",) for i in range(15)]
    laudo = s.avaliar_queda_da_execucao(
        s.ler_historico_contagem(_escrever_historico(tmp_path / "hist.csv", linhas)), execucao="2026-11-01"
    )
    assert laudo["aprovado"] is False
    assert len(laudo["redes_que_desabaram"]) == 15, "cada ausente cai de 40 para 0"
    assert laudo["queda_total_reprovou"] is True


# --------------------------------------------------------------------------- #
# O card: julgamento POR REDE, contra a última contagem BOA dela
# --------------------------------------------------------------------------- #
def _enchimento(datas: list[str], n_redes: int = 30) -> list[tuple[str, str, int, str]]:
    """Redes estáveis de 40 unidades, coletadas no dia (proporção do caso real)."""
    return [(d, f"rede_{i}", 40, d) for d in datas for i in range(n_redes)]


def _hist(tmp_path: Path, linhas: list[tuple[str, str, int, str]]) -> pd.DataFrame:
    return s.ler_historico_contagem(_escrever_historico(tmp_path / "hist.csv", linhas))


def _ate(hist: pd.DataFrame, data: str) -> pd.DataFrame:
    return hist[hist["data_execucao"] <= data]


def _situacoes(hist: pd.DataFrame, rede: str) -> list[str]:
    return [str(f["redes"][rede]["situacao"]) for f in s.acompanhar_redes(hist) if rede in f["redes"]]


def test_o_crash_de_13_09_nao_vira_rebote(tmp_path: Path) -> None:
    """O caso real: a Selfit cai de 231 para 119 com `data_coleta` de maio (o baseline do
    repositório) e volta a 231. Contra a vizinha, o dia 20 leria +112 unidades que ninguém abriu."""
    linhas = _enchimento(["2026-09-06", "2026-09-13", "2026-09-20"]) + [
        ("2026-09-06", "selfit", 231, "2026-09-06"),
        ("2026-09-13", "selfit", 119, "2026-05-26"),
        ("2026-09-20", "selfit", 231, "2026-09-20"),
    ]
    hist = _hist(tmp_path, linhas)

    no_dia_13 = s.contagem_da_tela(_ate(hist, "2026-09-13"))
    assert no_dia_13["unidades"]["selfit"] == 231, "a coleta velha não entra"
    assert no_dia_13["variacao"]["selfit"] == {"delta": None, "status": "nao_recoletada"}
    assert no_dia_13["nao_recoletadas"] == ["selfit"]

    no_dia_20 = s.contagem_da_tela(hist)
    assert no_dia_20["variacao"]["selfit"] == {"delta": 0, "status": "estavel"}, "sem o rebote de +112"
    # A régua da vizinha, para registro: é ela que inventaria as 112 unidades.
    vizinha = s.saldo_entre_execucoes(hist, de="2026-09-13", ate="2026-09-20")
    assert int(vizinha[vizinha["rede"] == "selfit"].iloc[0]["delta"]) == 112


def test_queda_com_coleta_nova_e_segurada_e_as_outras_redes_seguem(tmp_path: Path) -> None:
    """Uma rede quebrada não prende o card: só ela fica na última contagem boa."""
    linhas = _enchimento(["2026-10-25", "2026-11-01"]) + [
        ("2026-10-25", "selfit", 233, "2026-10-25"),
        ("2026-11-01", "selfit", 119, "2026-11-01"),
        ("2026-10-25", "pratique", 190, "2026-10-25"),
        ("2026-11-01", "pratique", 192, "2026-11-01"),
    ]
    tela = s.contagem_da_tela(_hist(tmp_path, linhas))
    assert tela["data"] == "2026-11-01"
    assert tela["unidades"]["selfit"] == 233
    assert tela["variacao"]["selfit"] == {"delta": None, "status": "segurada"}
    assert tela["seguradas"] == [
        {"rede": "selfit", "antes": 233, "agora": 119, "direcao": "queda", "desde": "2026-11-01"}
    ]
    assert tela["variacao"]["pratique"] == {"delta": 2, "status": "variou"}, "a outra rede anda"


def test_queda_real_que_se_mantem_numa_coleta_nova_e_confirmada(tmp_path: Path) -> None:
    """Rede de 6 que fecha 2 (-33%): fica segurada uma semana e entra quando a coleta seguinte
    mostra o mesmo patamar. Sem a confirmação, ela ficaria presa na contagem velha para sempre."""
    datas = ["2026-10-04", "2026-10-11", "2026-10-18", "2026-10-25"]
    linhas = _enchimento(datas) + [(d, "pequena", n, d) for d, n in zip(datas, [6, 4, 4, 4], strict=True)]
    hist = _hist(tmp_path, linhas)
    assert _situacoes(hist, "pequena") == ["estreia", "segurada", "confirmada", "aceita"]

    na_confirmacao = s.contagem_da_tela(_ate(hist, "2026-10-18"))
    assert na_confirmacao["variacao"]["pequena"] == {"delta": -2, "status": "confirmada"}
    assert na_confirmacao["confirmadas"] == [
        {"rede": "pequena", "antes": 6, "agora": 4, "direcao": "queda", "desde": "2026-10-11"}
    ]


def test_reexecucao_sem_recoletar_nao_confirma_a_queda(tmp_path: Path) -> None:
    """Achado da revisão de 05/11: rodar o relatório de novo numa quarta, sem recoletar, repetia a
    contagem quebrada com outra data e a "confirmava"; o domingo consertado lia +112. A mesma
    `data_coleta` não confirma nada: a confirmação exige uma coleta MAIS NOVA que a segurada."""
    linhas = _enchimento(["2026-09-06", "2026-09-13", "2026-09-16", "2026-09-20"]) + [
        ("2026-09-06", "selfit", 231, "2026-09-06"),
        ("2026-09-13", "selfit", 119, "2026-09-13"),  # coleta nova, mas quebrada
        ("2026-09-16", "selfit", 119, "2026-09-13"),  # o relatório de novo, a mesma coleta
        ("2026-09-20", "selfit", 231, "2026-09-20"),
    ]
    hist = _hist(tmp_path, linhas)
    assert _situacoes(hist, "selfit") == ["estreia", "segurada", "segurada", "aceita"]
    assert s.contagem_da_tela(hist)["variacao"]["selfit"] == {"delta": 0, "status": "estavel"}


def test_confirmar_exige_o_mesmo_patamar_e_o_mesmo_sentido(tmp_path: Path) -> None:
    """Uma recuperação parcial (119 -> 200, ainda -13% da base) não é a queda se mantendo, e uma
    queda que despenca de novo (119 -> 60) também não: as duas seguem seguradas ou entram pela
    régua normal, nunca como "confirmada"."""
    datas = ["2026-09-06", "2026-09-13", "2026-09-20"]
    recupera = _enchimento(datas) + [(d, "selfit", n, d) for d, n in zip(datas, [231, 119, 200], strict=True)]
    assert _situacoes(_hist(tmp_path, recupera), "selfit") == ["estreia", "segurada", "aceita"]
    despenca = _enchimento(datas) + [(d, "selfit", n, d) for d, n in zip(datas, [231, 119, 60], strict=True)]
    assert _situacoes(_hist(tmp_path, despenca), "selfit") == ["estreia", "segurada", "segurada"]


def test_salto_para_cima_e_segurado_e_a_correcao_volta_sem_alarde(tmp_path: Path) -> None:
    """Achado da revisão: conserto de coletor que duplica unidades (100 -> 200) entrava como
    crescimento, e a correção (200 -> 100) era recusada como "coleta incompleta"."""
    datas = ["2026-10-04", "2026-10-11", "2026-10-18", "2026-10-25"]
    linhas = _enchimento(datas) + [(d, "inflada", n, d) for d, n in zip(datas, [100, 200, 100, 100], strict=True)]
    hist = _hist(tmp_path, linhas)
    assert _situacoes(hist, "inflada") == ["estreia", "segurada", "aceita", "aceita"]
    assert all(f["valores"]["inflada"] == 100 for f in s.acompanhar_redes(hist))


def test_salto_para_cima_que_se_mantem_e_confirmado(tmp_path: Path) -> None:
    datas = ["2026-10-04", "2026-10-11", "2026-10-18"]
    linhas = _enchimento(datas) + [(d, "ampliada", n, d) for d, n in zip(datas, [100, 160, 161], strict=True)]
    tela = s.contagem_da_tela(_hist(tmp_path, linhas))
    assert tela["variacao"]["ampliada"] == {"delta": 61, "status": "confirmada"}
    assert tela["confirmadas"][0]["direcao"] == "subida"


def test_duas_redes_pequenas_oscilando_nao_prendem_o_card(tmp_path: Path) -> None:
    """A simulação da revisão de 05/11: julgando a semana inteira, duas redes de 5 a 9 unidades
    caindo em semanas alternadas prendiam as outras ~100 redes numa contagem velha."""
    datas = ["2026-10-04", "2026-10-11", "2026-10-18", "2026-10-25", "2026-11-01"]
    linhas = _enchimento(datas)
    linhas += [(d, "osc_a", n, d) for d, n in zip(datas, [8, 5, 8, 5, 8], strict=True)]
    linhas += [(d, "osc_b", n, d) for d, n in zip(datas, [8, 8, 5, 8, 5], strict=True)]
    linhas += [(d, "cresce", 100 + i, d) for i, d in enumerate(datas)]
    tela = s.contagem_da_tela(_hist(tmp_path, linhas))
    assert tela["data"] == "2026-11-01"
    assert tela["variacao"]["cresce"] == {"delta": 1, "status": "variou"}
    assert [x["rede"] for x in tela["seguradas"]] == ["osc_b"]


def test_rede_nao_recoletada_fica_sem_variacao_e_nao_vira_zero(tmp_path: Path) -> None:
    """A falha mais comum hoje (achado da revisão): o lote devolve a safra anterior à rede que não
    rodou, com a `data_coleta` antiga. "Estável, 0" diria que ela não se mexeu; o fato é "não
    sabemos"."""
    linhas = _enchimento(["2026-10-25", "2026-11-01"]) + [
        ("2026-10-25", "selfit", 233, "2026-10-25"),
        ("2026-11-01", "selfit", 233, "2026-10-25"),
    ]
    tela = s.contagem_da_tela(_hist(tmp_path, linhas))
    assert tela["unidades"]["selfit"] == 233
    assert tela["variacao"]["selfit"] == {"delta": None, "status": "nao_recoletada"}
    assert tela["nao_recoletadas"] == ["selfit"]


def test_rede_ausente_fica_uma_semana_e_depois_sai(tmp_path: Path) -> None:
    linhas = _enchimento(["2026-10-18", "2026-10-25", "2026-11-01"]) + [("2026-10-18", "extinta", 12, "2026-10-18")]
    hist = _hist(tmp_path, linhas)
    na_ausencia = s.contagem_da_tela(_ate(hist, "2026-10-25"))
    assert na_ausencia["unidades"]["extinta"] == 12
    assert na_ausencia["variacao"]["extinta"] == {"delta": None, "status": "ausente"}
    assert na_ausencia["ausentes"] == ["extinta"]
    depois = s.contagem_da_tela(hist)
    assert "extinta" not in depois["unidades"]
    assert depois["variacao"]["extinta"] == {"delta": None, "status": "sumiu"}
    assert depois["removidas"] == ["extinta"]


def test_queda_difusa_segura_a_execucao_inteira_e_a_repeticao_entra(tmp_path: Path) -> None:
    """A guarda do TOTAL da DEC-061 segue valendo: muitas redes perdendo pouco, com coleta nova."""
    datas = ["2026-10-25", "2026-11-01", "2026-11-08"]
    linhas = [(d, f"rede_{i}", n, d) for d, n in zip(datas, [20, 15, 15], strict=True) for i in range(10)]
    hist = _hist(tmp_path, linhas)

    na_queda = s.contagem_da_tela(_ate(hist, "2026-11-01"))
    assert na_queda["data"] == "2026-10-25"
    assert na_queda["recusadas"] == [{"execucao": "2026-11-01", "motivo": "total", "queda_total_pct": 25.0}]

    depois = s.contagem_da_tela(hist)
    assert (depois["data"], depois["data_anterior"], depois["total_confirmado"]) == ("2026-11-08", "2026-10-25", True)
    assert depois["variacao"]["rede_0"] == {"delta": -5, "status": "variou"}


def test_estudio_sai_antes_da_guarda(tmp_path: Path) -> None:
    """O card não mostra estúdio boutique (DEC-056): ele não entra nem na conta do total."""
    linhas = [(d, "pratique", 40, d) for d in ("2026-10-25", "2026-11-01")] + [
        ("2026-10-25", "velocity", 125, "2026-10-25"),
        ("2026-11-01", "velocity", 100, "2026-11-01"),  # -20%: abaixo da régua por rede, -15% no total
    ]
    hist = _hist(tmp_path, linhas)
    assert s.contagem_da_tela(hist)["data"] == "2026-10-25", "sem excluir, o estúdio reprova o total"
    tela = s.contagem_da_tela(hist, excluir={"velocity"})
    assert tela["data"] == "2026-11-01"
    assert "velocity" not in tela["unidades"] and "velocity" not in tela["variacao"]


def test_variacao_da_tela_marca_a_estreia_como_novo(tmp_path: Path) -> None:
    """Mesma semântica do Telegram: rede que entra na cobertura é `novo`, sem `+n`."""
    linhas = _enchimento(["2026-10-25", "2026-11-01"]) + [("2026-11-01", "estreante", 12, "2026-11-01")]
    tela = s.contagem_da_tela(_hist(tmp_path, linhas))
    assert tela["variacao"]["estreante"] == {"delta": None, "status": "novo"}
    assert tela["variacao"]["rede_0"] == {"delta": 0, "status": "estavel"}


def test_historico_vazio_nao_tem_contagem_e_nao_levanta(tmp_path: Path) -> None:
    tela = s.contagem_da_tela(_hist(tmp_path, []))
    assert tela["data"] is None and tela["unidades"] == {} and tela["recusadas"] == []
    assert tela["seguradas"] == [] and tela["nao_recoletadas"] == []


def test_o_vocabulario_da_tela_cobre_toda_situacao(tmp_path: Path) -> None:
    """Toda situação de leitura vira um status que a tela conhece (a paridade com o TypeScript
    fica em `test_paridade_crescimento_concorrencia_web.py`)."""
    traducao = {"estreia": "novo", "removida": "sumiu", "aceita": "variou"}
    for situacao in s.SITUACOES_LEITURA:
        assert traducao.get(situacao, situacao) in s.STATUS_VARIACAO_TELA, situacao


def test_a_serie_de_dois_anos_monta_em_tempo_de_requisicao(tmp_path: Path) -> None:
    """Achado da revisão: a versão por execução custava 3 a 7 s com 104 execuções (crescia mais que
    linear). O acompanhamento por rede é uma passada por execução; o teto aqui é folgado de
    propósito, para medir a ordem de grandeza e não a máquina."""
    import time

    datas = [str(d.date()) for d in pd.date_range("2025-01-05", periods=104, freq="7D")]
    linhas = [(d, f"rede_{i:03d}", 40 + (k % 3), d) for k, d in enumerate(datas) for i in range(107)]
    hist = _hist(tmp_path, linhas)
    inicio = time.perf_counter()
    tela = s.contagem_da_tela(hist)
    assert tela["data"] == datas[-1]
    assert time.perf_counter() - inicio < 5.0


# --------------------------------------------------------------------------- #
# Leitura tolerante (a da tela)
# --------------------------------------------------------------------------- #
def test_leitura_tolerante_tira_a_execucao_duplicada_INTEIRA_e_conta_a_linha_sem_data(
    tmp_path: Path,
) -> None:
    """Um domingo que rodou duas vezes não pode devolver o card ao pacote de setembro, e nenhuma das
    cópias é escolhida em silêncio: o dia inteiro sai e volta nomeado."""
    caminho = _escrever_historico(
        tmp_path / "hist.csv",
        [
            ("2026-10-25", "selfit", 231, "2026-10-25"),
            ("2026-10-25", "panobianco", 150, "2026-10-25"),
            ("2026-11-01", "selfit", 233, "2026-11-01"),
            ("2026-11-01", "selfit", 233, "2026-11-01"),
            ("2026-11-01", "panobianco", 151, "2026-11-01"),
            ("2026-11-0", "selfit", 1, ""),  # arquivo cortado no meio da cópia
        ],
    )
    with pytest.raises(ValueError, match="duplicado"):
        s.ler_historico_contagem(caminho)

    hist, descartes = s.ler_historico_tolerante(caminho)
    assert descartes == {"execucoes_duplicadas": ["2026-11-01"], "linhas_sem_data": 1}
    assert set(hist["data_execucao"].astype(str)) == {"2026-10-25"}, "a panobianco de 01/11 sai junto"

    tela = s.contagem_da_tela(
        hist, execucoes_duplicadas=descartes["execucoes_duplicadas"], linhas_sem_data=descartes["linhas_sem_data"]
    )
    assert tela["data"] == "2026-10-25"
    assert tela["execucao_mais_recente"] == "2026-11-01"
    assert tela["linhas_sem_data"] == 1, "a linha sem data também vira aviso na tela"
    assert tela["recusadas"] == [{"execucao": "2026-11-01", "motivo": "duplicada", "queda_total_pct": None}]


# --------------------------------------------------------------------------- #
# Revisão de 05/11 (2ª rodada): regras de várias semanas, a guarda do total e as datas
# --------------------------------------------------------------------------- #
def test_queda_em_dois_degraus_confirma_no_patamar_novo_e_guarda_o_desde(tmp_path: Path) -> None:
    """231 -> 119 -> 60 -> 60: a segunda queda continua segurada (não confirma a primeira), e o
    patamar novo entra quando se repete. O `desde` é o da PRIMEIRA semana segurada. Sem o
    `pendente` andando, a rede ficaria presa em 231 para sempre."""
    datas = ["2026-10-04", "2026-10-11", "2026-10-18", "2026-10-25"]
    linhas = _enchimento(datas) + [(d, "selfit", n, d) for d, n in zip(datas, [231, 119, 60, 60], strict=True)]
    hist = _hist(tmp_path, linhas)
    assert _situacoes(hist, "selfit") == ["estreia", "segurada", "segurada", "confirmada"]

    no_meio = s.contagem_da_tela(_ate(hist, "2026-10-18"))
    assert no_meio["unidades"]["selfit"] == 231
    assert no_meio["seguradas"] == [
        {"rede": "selfit", "antes": 231, "agora": 60, "direcao": "queda", "desde": "2026-10-11"}
    ]
    tela = s.contagem_da_tela(hist)
    assert tela["unidades"]["selfit"] == 60
    assert tela["variacao"]["selfit"] == {"delta": -171, "status": "confirmada"}
    assert tela["confirmadas"] == [
        {"rede": "selfit", "antes": 231, "agora": 60, "direcao": "queda", "desde": "2026-10-11"}
    ]


def test_rede_que_volta_e_some_de_novo_fica_mais_uma_semana(tmp_path: Path) -> None:
    """A volta da rede (mesmo sem coleta nova, ou com salto segurado) zera a ausência: ela só sai
    depois de faltar DUAS execuções seguidas."""
    datas = ["2026-10-04", "2026-10-11", "2026-10-18", "2026-10-25", "2026-11-01"]
    linhas = _enchimento(datas) + [
        ("2026-10-04", "volta", 12, "2026-10-04"),
        ("2026-10-18", "volta", 12, "2026-10-04"),  # volta sem coleta nova
        ("2026-10-04", "salta", 40, "2026-10-04"),
        ("2026-10-18", "salta", 100, "2026-10-18"),  # volta com salto brusco
    ]
    hist = _hist(tmp_path, linhas)
    assert _situacoes(hist, "volta") == ["estreia", "ausente", "nao_recoletada", "ausente", "removida"]
    assert _situacoes(hist, "salta") == ["estreia", "ausente", "segurada", "ausente", "removida"]


def test_total_que_continua_caindo_nao_e_confirmado(tmp_path: Path) -> None:
    """20 -> 17 -> 15 -> 15: a segunda recusa caiu MAIS que a primeira, então não a confirma; só o
    patamar que se repete (15 e 15) entra."""
    datas = ["2026-10-25", "2026-11-01", "2026-11-08", "2026-11-15"]
    linhas = [(d, f"rede_{i}", n, d) for d, n in zip(datas, [20, 17, 15, 15], strict=True) for i in range(10)]
    hist = _hist(tmp_path, linhas)

    no_meio = s.contagem_da_tela(_ate(hist, "2026-11-08"))
    assert no_meio["data"] == "2026-10-25"
    assert no_meio["recusadas"] == [
        {"execucao": "2026-11-01", "motivo": "total", "queda_total_pct": 15.0},
        {"execucao": "2026-11-08", "motivo": "total", "queda_total_pct": 25.0},
    ]
    tela = s.contagem_da_tela(hist)
    assert (tela["data"], tela["data_anterior"], tela["total_confirmado"]) == ("2026-11-15", "2026-10-25", True)
    assert tela["variacao"]["rede_0"] == {"delta": -5, "status": "variou"}


def test_reprovacao_antiga_nao_confirma_queda_nova(tmp_path: Path) -> None:
    """20, 17, 20, 20, 17: a recuperação apaga a recusa pendente, e a queda nova de 15/11 é julgada
    do zero (fica de fora), em vez de "confirmar" contra a recusa de 25/10."""
    datas = ["2026-10-18", "2026-10-25", "2026-11-01", "2026-11-08", "2026-11-15"]
    linhas = [(d, f"rede_{i}", n, d) for d, n in zip(datas, [20, 17, 20, 20, 17], strict=True) for i in range(10)]
    tela = s.contagem_da_tela(_hist(tmp_path, linhas))
    assert (tela["data"], tela["total_confirmado"]) == ("2026-11-08", False)
    assert tela["recusadas"] == [{"execucao": "2026-11-15", "motivo": "total", "queda_total_pct": 15.0}]


def test_guarda_do_total_ignora_rede_sem_coleta(tmp_path: Path) -> None:
    """~10,8% das linhas de toda semana não são recoletadas. Somá-las à base diluiria a guarda: aqui
    a rede de 500 parada faria a queda de 15% virar 4,3% e entrar."""
    linhas = [(d, f"rede_{i}", n, d) for d, n in (("2026-10-25", 20), ("2026-11-01", 17)) for i in range(10)]
    linhas += [("2026-10-25", "grande", 500, "2026-10-25"), ("2026-11-01", "grande", 500, "2026-10-25")]
    tela = s.contagem_da_tela(_hist(tmp_path, linhas))
    assert tela["data"] == "2026-10-25"
    assert tela["recusadas"] == [{"execucao": "2026-11-01", "motivo": "total", "queda_total_pct": 15.0}]


def test_guarda_do_total_ignora_o_salto_que_se_confirma(tmp_path: Path) -> None:
    """A rede cujo salto se confirma na mesma execução não entra na soma: o +100 dela esconderia a
    queda difusa das outras."""
    datas = ["2026-10-18", "2026-10-25", "2026-11-01"]
    linhas = [(d, f"rede_{i}", n, d) for d, n in zip(datas, [20, 20, 17], strict=True) for i in range(10)]
    linhas += [(d, "grande", n, d) for d, n in zip(datas, [100, 200, 200], strict=True)]
    tela = s.contagem_da_tela(_hist(tmp_path, linhas))
    assert tela["data"] == "2026-10-25"
    assert tela["recusadas"] == [{"execucao": "2026-11-01", "motivo": "total", "queda_total_pct": 15.0}]


def test_recusada_antiga_nao_reaparece(tmp_path: Path) -> None:
    """A recusa de antes da contagem anterior já não explica nada na tela."""
    datas = ["2026-10-25", "2026-11-01", "2026-11-08", "2026-11-15"]
    linhas = [(d, f"rede_{i}", n, d) for d, n in zip(datas, [20, 15, 20, 20], strict=True) for i in range(10)]
    tela = s.contagem_da_tela(_hist(tmp_path, linhas))
    assert (tela["data"], tela["data_anterior"], tela["recusadas"]) == ("2026-11-15", "2026-11-08", [])


def test_mesma_coleta_da_execucao_recusada_nao_confirma_o_total(tmp_path: Path) -> None:
    """O relatório rodado de novo repete as linhas da execução recusada, com a MESMA data de coleta:
    isso não é recoleta e não confirma a queda. A recoleta de verdade, no domingo, confirma."""
    linhas = [(d, f"rede_{i}", n, c) for d, n, c in (
        ("2026-10-25", 20, "2026-10-25"),
        ("2026-11-01", 15, "2026-11-01"),
        ("2026-11-04", 15, "2026-11-01"),  # o relatório de novo, sem recoletar
        ("2026-11-08", 15, "2026-11-08"),
    ) for i in range(10)]
    hist = _hist(tmp_path, linhas)

    na_quarta = s.contagem_da_tela(_ate(hist, "2026-11-04"))
    assert (na_quarta["data"], na_quarta["total_confirmado"]) == ("2026-10-25", False)
    assert na_quarta["unidades"]["rede_0"] == 20
    assert na_quarta["sem_coleta_nova"] == ["2026-11-04"]
    assert na_quarta["execucao_mais_recente"] == "2026-11-04"

    no_domingo = s.contagem_da_tela(hist)
    assert (no_domingo["data"], no_domingo["data_anterior"], no_domingo["total_confirmado"]) == (
        "2026-11-08",
        "2026-10-25",
        True,
    )
    assert no_domingo["variacao"]["rede_0"] == {"delta": -5, "status": "variou"}


def test_safra_da_execucao_recusada_nao_entra_como_coleta_nova(tmp_path: Path) -> None:
    """O passo 2.5 devolve a quem falhou o CSV do lote anterior, que é o RECUSADO: as 3 redes que
    não recoletaram leem 29 com a data dele. Elas ficam "sem coleta" na última contagem boa (40),
    e não entram como -11 sem aviso nenhum."""
    linhas = [(d, f"rede_{i}", n, d) for d, n in (("2026-10-25", 40), ("2026-11-01", 29)) for i in range(30)]
    linhas += [("2026-11-08", f"rede_{i}", 40, "2026-11-08") for i in range(27)]
    linhas += [("2026-11-08", f"rede_{i}", 29, "2026-11-01") for i in range(27, 30)]
    tela = s.contagem_da_tela(_hist(tmp_path, linhas))
    assert (tela["data"], tela["data_anterior"]) == ("2026-11-08", "2026-10-25")
    assert tela["unidades"]["rede_27"] == 40
    assert tela["variacao"]["rede_27"] == {"delta": None, "status": "nao_recoletada"}
    assert tela["nao_recoletadas"] == ["rede_27", "rede_28", "rede_29"]
    assert tela["variacao"]["rede_0"] == {"delta": 0, "status": "estavel"}


def test_execucao_sem_coleta_nova_nao_vira_a_foto(tmp_path: Path) -> None:
    """O relatório rodado de novo numa quarta, sem recoletar: o card segue no domingo, com a
    variação dele, em vez de trocar a data e mostrar "sem coleta" em todas as redes."""
    linhas = _enchimento(["2026-10-25", "2026-11-01"]) + [
        ("2026-10-25", "selfit", 231, "2026-10-25"),
        ("2026-11-01", "selfit", 233, "2026-11-01"),
    ]
    linhas += [("2026-11-04", f"rede_{i}", 40, "2026-11-01") for i in range(30)]
    linhas += [("2026-11-04", "selfit", 233, "2026-11-01")]
    tela = s.contagem_da_tela(_hist(tmp_path, linhas))
    assert (tela["data"], tela["data_anterior"]) == ("2026-11-01", "2026-10-25")
    assert tela["variacao"]["selfit"] == {"delta": 2, "status": "variou"}
    assert tela["nao_recoletadas"] == []
    assert (tela["sem_coleta_nova"], tela["execucao_mais_recente"]) == (["2026-11-04"], "2026-11-04")


def test_lote_em_que_todos_os_coletores_falham_nao_avanca_a_data(tmp_path: Path) -> None:
    """Dois domingos sem nenhuma recoleta (o passo 2.5 devolve a safra a todos): a data do card não
    anda, e por isso o aviso de contagem velha volta a valer. A rede que saiu nesse meio aparece
    como saída quando a coleta volta."""
    linhas = _enchimento(["2026-10-25", "2026-11-01", "2026-11-22"])
    linhas += [(d, f"rede_{i}", 40, "2026-11-01") for d in ("2026-11-08", "2026-11-15") for i in range(30)]
    linhas += [("2026-10-25", "extinta", 12, "2026-10-25"), ("2026-11-01", "extinta", 12, "2026-11-01")]
    hist = _hist(tmp_path, linhas)

    parado = s.contagem_da_tela(_ate(hist, "2026-11-15"))
    assert (parado["data"], parado["data_anterior"]) == ("2026-11-01", "2026-10-25")
    assert parado["sem_coleta_nova"] == ["2026-11-08", "2026-11-15"]
    assert parado["unidades"]["extinta"] == 12

    voltou = s.contagem_da_tela(hist)
    assert (voltou["data"], voltou["data_anterior"], voltou["sem_coleta_nova"]) == ("2026-11-22", "2026-11-01", [])
    assert "extinta" not in voltou["unidades"]
    assert voltou["variacao"]["extinta"] == {"delta": None, "status": "sumiu"}
    assert voltou["removidas"] == ["extinta"]


def test_data_de_coleta_futura_ou_fora_do_iso_nao_congela_a_rede(tmp_path: Path) -> None:
    """Uma data futura (ou fora do ISO) gravada uma vez virava o piso da rede, e nenhuma coleta
    depois passava dela. Agora ela não conta como coleta; com hora junto, vale o dia."""
    datas = ["2026-10-11", "2026-10-18", "2026-10-25"]
    linhas = _enchimento(datas) + [
        ("2026-10-11", "panobianco", 180, "2026-10-11"),
        ("2026-10-18", "panobianco", 181, "2027-10-11"),
        ("2026-10-25", "panobianco", 185, "2026-10-25"),
        ("2026-10-11", "outra", 50, "2026-10-11"),
        ("2026-10-18", "outra", 51, "26/10/2026"),
        ("2026-10-25", "outra", 52, "2026-10-25"),
        ("2026-10-11", "com_hora", 60, "2026-10-11 08:00"),
        ("2026-10-18", "com_hora", 61, "2026-10-18 09:00"),
        ("2026-10-25", "com_hora", 61, "2026-10-25 07:30"),
    ]
    hist = _hist(tmp_path, linhas)
    assert _situacoes(hist, "panobianco") == ["estreia", "nao_recoletada", "aceita"]
    assert _situacoes(hist, "outra") == ["estreia", "nao_recoletada", "aceita"]
    assert _situacoes(hist, "com_hora") == ["estreia", "aceita", "aceita"]
    tela = s.contagem_da_tela(hist)
    assert tela["variacao"]["panobianco"] == {"delta": 5, "status": "variou"}
    assert tela["variacao"]["outra"] == {"delta": 2, "status": "variou"}


def test_coletor_vazio_nao_serve_de_base_e_a_primeira_coleta_e_estreia(tmp_path: Path) -> None:
    """(0, data vazia) é coletor que não devolveu nada. A primeira leitura com dado é cobertura
    nova ("nova"), não "+14" de crescimento."""
    datas = ["2026-10-18", "2026-10-25", "2026-11-01"]
    linhas = _enchimento(datas) + [
        ("2026-10-18", "vazia", 0, ""),
        ("2026-10-25", "vazia", 0, ""),
        ("2026-11-01", "vazia", 14, "2026-11-01"),
    ]
    hist = _hist(tmp_path, linhas)
    assert _situacoes(hist, "vazia") == ["estreia", "nao_recoletada", "estreia"]
    tela = s.contagem_da_tela(hist)
    assert (tela["unidades"]["vazia"], tela["variacao"]["vazia"]) == (14, {"delta": None, "status": "novo"})


def test_coleta_vazia_depois_de_contagem_boa_fica_sem_coleta(tmp_path: Path) -> None:
    """O coletor que voltou vazio (12 linhas assim em produção) não zera a rede, grande ou pequena."""
    linhas = _enchimento(["2026-10-25", "2026-11-01"]) + [
        ("2026-10-25", "selfit", 233, "2026-10-25"),
        ("2026-11-01", "selfit", 0, ""),
        ("2026-10-25", "mini", 3, "2026-10-25"),
        ("2026-11-01", "mini", 0, ""),
    ]
    tela = s.contagem_da_tela(_hist(tmp_path, linhas))
    assert (tela["unidades"]["selfit"], tela["unidades"]["mini"]) == (233, 3)
    assert tela["variacao"]["selfit"] == {"delta": None, "status": "nao_recoletada"}
    assert tela["variacao"]["mini"] == {"delta": None, "status": "nao_recoletada"}


def test_leitura_tolerante_pula_linha_com_campo_a_mais(tmp_path: Path) -> None:
    """Uma linha com campo a mais derrubava a leitura inteira (e o card voltava ao pacote)."""
    caminho = _escrever_historico(
        tmp_path / "hist.csv",
        [
            ("2026-10-25", "selfit", 231, "2026-10-25"),
            ("2026-10-25", "panobianco", 150, "2026-10-25"),
            ("2026-11-01", "selfit", 233, "2026-11-01;x"),
            ("2026-11-01", "panobianco", 151, "2026-11-01"),
        ],
    )
    with pytest.raises(pd.errors.ParserError):
        s.ler_historico_contagem(caminho)
    hist, descartes = s.ler_historico_tolerante(caminho)
    assert descartes == {"execucoes_duplicadas": [], "linhas_sem_data": 1}
    assert len(hist) == 3
    assert "selfit" not in set(hist[hist["data_execucao"] == "2026-11-01"]["rede"].astype(str))
