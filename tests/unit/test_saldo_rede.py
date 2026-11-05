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


# --------------------------------------------------------------------------- #
# Série que a TELA lê: cada execução contra a última ACEITA
# --------------------------------------------------------------------------- #
def _enchimento(datas: list[str], n_redes: int = 30) -> list[tuple[str, str, int, str]]:
    """Redes estáveis de 40 unidades, na proporção do caso real (ver `_historico_do_incidente`)."""
    return [(d, f"rede_{i}", 40, d) for d in datas for i in range(n_redes)]


def _como(laudos: list[dict[str, object]]) -> list[tuple[object, object]]:
    return [(laudo["execucao"], laudo["como"]) for laudo in laudos]


def test_serie_julga_contra_a_ultima_aceita_e_o_rebote_some(tmp_path: Path) -> None:
    """O caso real: Selfit 231 -> 119 (crash de 13/09) -> 231. Contra a vizinha, o dia 20 leria
    +112 unidades que ninguém abriu; contra a última aceita (06/09), lê zero."""
    datas = ["2026-09-06", "2026-09-13", "2026-09-20", "2026-09-27"]
    linhas = _enchimento(datas) + [
        ("2026-09-06", "selfit", 231, "2026-09-06"),
        ("2026-09-13", "selfit", 119, "2026-05-26"),
        ("2026-09-20", "selfit", 231, "2026-09-20"),
        ("2026-09-27", "selfit", 233, "2026-09-27"),
    ]
    hist = s.ler_historico_contagem(_escrever_historico(tmp_path / "hist.csv", linhas))

    laudos = s.avaliar_serie(hist)
    assert _como(laudos) == [
        ("2026-09-06", "primeira"),
        ("2026-09-13", "recusada"),
        ("2026-09-20", "aprovada"),
        ("2026-09-27", "aprovada"),
    ]
    assert laudos[2]["referencia"] == "2026-09-06", "o dia 20 e' julgado contra 06/09, nao contra 13/09"
    # A régua da vizinha, para registro: é ela que inventaria as 112 unidades.
    vizinha = s.saldo_entre_execucoes(hist, de="2026-09-13", ate="2026-09-20")
    assert int(vizinha[vizinha["rede"] == "selfit"].iloc[0]["delta"]) == 112

    tela = s.contagem_da_tela(hist)
    assert (tela["data"], tela["data_anterior"]) == ("2026-09-27", "2026-09-20")
    assert tela["variacao"]["selfit"] == {"delta": 2, "status": "variou"}
    assert tela["recusadas"] == [], "13/09 ficou antes da aceita anterior: nao explica nada da tela de hoje"


def test_queda_que_se_repete_e_confirmada_e_a_serie_nao_congela(tmp_path: Path) -> None:
    """Rede de 6 unidades que fecha 2 (-33%): sem a confirmação, toda semana seguinte seria julgada
    contra a mesma contagem velha e reprovada para sempre, e a tela pararia junto."""
    datas = ["2026-10-04", "2026-10-11", "2026-10-18", "2026-10-25"]
    linhas = _enchimento(datas) + [
        ("2026-10-04", "pequena", 6, "2026-10-04"),
        ("2026-10-11", "pequena", 4, "2026-10-11"),
        ("2026-10-18", "pequena", 4, "2026-10-18"),
        ("2026-10-25", "pequena", 4, "2026-10-25"),
    ]
    hist = s.ler_historico_contagem(_escrever_historico(tmp_path / "hist.csv", linhas))

    assert _como(s.avaliar_serie(hist)) == [
        ("2026-10-04", "primeira"),
        ("2026-10-11", "recusada"),
        ("2026-10-18", "confirmada"),
        ("2026-10-25", "aprovada"),
    ]
    na_confirmacao = s.contagem_da_tela(hist[hist["data_execucao"] <= "2026-10-18"])
    assert na_confirmacao["confirmada"] is True
    assert na_confirmacao["quedas_confirmadas"] == [
        {"rede": "pequena", "antes": 6, "agora": 4, "coleta_defasada": False}
    ]
    # A variação da semana confirmada cobre DUAS semanas (contra 04/10), e a recusa diz por quê.
    assert na_confirmacao["data_anterior"] == "2026-10-04"
    assert na_confirmacao["variacao"]["pequena"] == {"delta": -2, "status": "variou"}
    assert [r["execucao"] for r in na_confirmacao["recusadas"]] == ["2026-10-11"]


def test_duas_recusas_diferentes_nao_se_confirmam(tmp_path: Path) -> None:
    """Confirmar exige a MESMA contagem duas vezes: quedas em redes diferentes não são o mesmo fato."""
    datas = ["2026-09-06", "2026-09-13", "2026-09-20"]
    linhas = _enchimento(datas) + [
        ("2026-09-06", "selfit", 231, "2026-09-06"),
        ("2026-09-13", "selfit", 119, "2026-09-13"),
        ("2026-09-20", "selfit", 231, "2026-09-20"),
        ("2026-09-06", "panobianco", 150, "2026-09-06"),
        ("2026-09-13", "panobianco", 150, "2026-09-13"),
        ("2026-09-20", "panobianco", 60, "2026-09-20"),
    ]
    hist = s.ler_historico_contagem(_escrever_historico(tmp_path / "hist.csv", linhas))
    assert _como(s.avaliar_serie(hist))[1:] == [("2026-09-13", "recusada"), ("2026-09-20", "recusada")]

    tela = s.contagem_da_tela(hist)
    assert tela["data"] == "2026-09-06" and tela["data_anterior"] is None
    assert tela["execucao_mais_recente"] == "2026-09-20"
    recusadas = {r["execucao"]: r for r in tela["recusadas"]}
    assert [q["rede"] for q in recusadas["2026-09-13"]["redes"]] == ["selfit"]
    assert [q["rede"] for q in recusadas["2026-09-20"]["redes"]] == ["panobianco"]


def test_tela_diz_quando_a_ultima_contagem_ficou_de_fora(tmp_path: Path) -> None:
    datas = ["2026-10-25", "2026-11-01", "2026-11-08"]
    linhas = _enchimento(datas) + [
        ("2026-10-25", "selfit", 231, "2026-10-25"),
        ("2026-11-01", "selfit", 233, "2026-11-01"),
        ("2026-11-08", "selfit", 119, "2026-05-26"),
    ]
    tela = s.contagem_da_tela(s.ler_historico_contagem(_escrever_historico(tmp_path / "hist.csv", linhas)))
    assert (tela["data"], tela["data_anterior"], tela["execucao_mais_recente"]) == (
        "2026-11-01",
        "2026-10-25",
        "2026-11-08",
    )
    assert tela["unidades"]["selfit"] == 233
    (recusa,) = tela["recusadas"]
    assert recusa["execucao"] == "2026-11-08" and recusa["motivo"] == "queda"
    assert recusa["redes"] == [{"rede": "selfit", "antes": 233, "agora": 119, "coleta_defasada": True}]
    assert recusa["queda_total_pct"] is None, "foi a rede que reprovou, nao o total"


def test_estudio_sai_antes_da_guarda_e_nao_segura_as_outras_redes(tmp_path: Path) -> None:
    """O card não mostra estúdio boutique (DEC-056): o tombo de um não pode prender as outras redes."""
    linhas = _enchimento(["2026-10-25", "2026-11-01"]) + [
        ("2026-10-25", "velocity", 125, "2026-10-25"),
        ("2026-11-01", "velocity", 20, "2026-11-01"),
    ]
    hist = s.ler_historico_contagem(_escrever_historico(tmp_path / "hist.csv", linhas))
    assert s.contagem_da_tela(hist)["data"] == "2026-10-25", "sem excluir, o tombo do estudio reprova 01/11"
    tela = s.contagem_da_tela(hist, excluir={"velocity"})
    assert tela["data"] == "2026-11-01"
    assert "velocity" not in tela["unidades"] and "velocity" not in tela["variacao"]


def test_variacao_da_tela_mantem_novo_fora_da_conta(tmp_path: Path) -> None:
    """Mesma semântica do Telegram: rede que entra na cobertura é `novo`, sem `+n`."""
    linhas = _enchimento(["2026-10-25", "2026-11-01"]) + [("2026-11-01", "estreante", 12, "2026-11-01")]
    tela = s.contagem_da_tela(s.ler_historico_contagem(_escrever_historico(tmp_path / "hist.csv", linhas)))
    assert tela["variacao"]["estreante"] == {"delta": None, "status": "novo"}
    assert tela["variacao"]["rede_0"] == {"delta": 0, "status": "estavel"}


def test_historico_vazio_nao_tem_contagem_e_nao_levanta(tmp_path: Path) -> None:
    tela = s.contagem_da_tela(s.ler_historico_contagem(_escrever_historico(tmp_path / "hist.csv", [])))
    assert tela["data"] is None and tela["unidades"] == {} and tela["recusadas"] == []


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

    tela = s.contagem_da_tela(hist, execucoes_duplicadas=descartes["execucoes_duplicadas"])
    assert tela["data"] == "2026-10-25"
    assert tela["execucao_mais_recente"] == "2026-11-01"
    assert tela["recusadas"] == [
        {"execucao": "2026-11-01", "motivo": "duplicada", "redes": [], "queda_total_pct": None}
    ]
