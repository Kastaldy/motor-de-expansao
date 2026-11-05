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
    extremo de coleta parcial. Até 2026-11 ela ficava fora como `sumiu`, e uma execução com metade
    das redes passava na guarda (achado da revisão de 05/11)."""
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
