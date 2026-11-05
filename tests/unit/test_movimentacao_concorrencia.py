"""Movimentação da concorrência (`motor_expansao.dashboard.movimentacao_concorrencia`).

Trava a forma: leitura NAO_USAR/ruído não vira evento, a Ultra e o estúdio não contam como
concorrente, e o raio corta pela distância real.
"""

from __future__ import annotations

import pandas as pd

from motor_expansao.dashboard import movimentacao_concorrencia as mov


def _cadastro():
    base = {"periodo": "validado", "de": "2026-08-02", "ate": "2026-09-06", "rede": "pratique",
            "nome_antes": None, "nome_depois": "Pratique X", "latitude": "-23.0", "longitude": "-46.0",
            "distancia_m": None, "leitura": "usar", "status": "entrou_abriu_ou_apareceu_no_site"}
    linhas = [
        {},
        {"status": "saiu_fechou_ou_sumiu_do_site", "nome_depois": None, "nome_antes": "Pratique Y", "latitude": "-23.005"},
        {"rede": "smart_fit", "leitura": "NAO_USAR_teto_de_1000_do_coletor"},
        {"leitura": "ruido_recalibracao_de_geocodificacao", "status": "mudou_coordenada"},
        {"status": "mudou_coordenada"},
        {"leitura": "usar_com_cautela_foto_nao_validada", "de": "2026-05-28", "ate": "2026-08-02", "latitude": "-23.5"},
        {"rede": "velocity", "nome_depois": "Velocity Z"},
    ]
    return pd.DataFrame([{**base, **linha} for linha in linhas])


def test_cadastro_so_leva_leituras_utilizaveis_e_movimento_de_mercado():
    q = mov.normalizar_cadastro(_cadastro())
    # a abertura e o fechamento da Pratique a 556 m viram troca de cadastro e saem juntos
    assert list(zip(q["tipo"], q["confianca"], strict=True)) == [("abertura", "cautela"), ("abertura", "alta")]


def test_em_breve_so_o_que_ainda_nao_inaugurou_e_wellhub_mapeia_tipo():
    eb = mov.normalizar_em_breve(pd.DataFrame([
        {"rede": "ad3", "nome_anunciado": "AD3 A", "primeira_evidencia": "2026-06-01", "ultima_evidencia_anunciada": "2026-09-10",
         "latitude": "-23.001", "longitude": "-46.0", "situacao_06_09": "ainda_em_breve_em_06_09"},
        {"rede": "ad3", "nome_anunciado": "AD3 B", "primeira_evidencia": "2026-06-01", "ultima_evidencia_anunciada": "2026-09-10",
         "latitude": "-23.001", "longitude": "-46.0", "situacao_06_09": "inaugurada_ate_06_09"},
    ]))
    assert eb["nome"].tolist() == ["AD3 A"]
    wh = mov.normalizar_wellhub(pd.DataFrame([
        {"de": "2026-08-31", "ate": "2026-09-05", "tipo": "entrada", "nome": "Academia Nova", "latitude": "-23.002",
         "longitude": "-46.0", "rede_agregador": None},
        {"de": "2026-08-31", "ate": "2026-09-05", "tipo": "saida", "nome": "Ultra Academia - Centro", "latitude": "-23.002",
         "longitude": "-46.0", "rede_agregador": None},
    ]))
    assert wh["tipo"].tolist() == ["entrou_agregador", "saiu_agregador"]


def test_entorno_tira_ultra_e_estudio_ordena_e_conta():
    cadastro = _cadastro()
    cadastro.loc[1, "latitude"] = "-23.05"  # fechamento a 5,5 km: fora do raio e sem par de troca
    eventos = pd.concat([
        mov.normalizar_cadastro(cadastro),
        mov.normalizar_wellhub(pd.DataFrame([
            {"de": "2026-08-31", "ate": "2026-09-05", "tipo": "saida", "nome": "Ultra Academia - Centro",
             "latitude": "-23.002", "longitude": "-46.0", "rede_agregador": None},
        ])),
    ], ignore_index=True)
    filtrados = mov.filtrar_concorrencia(eventos, {"velocity"})
    itens = mov.eventos_no_entorno(-23.0, -46.0, filtrados)
    assert [(i["tipo"], i["nome"]) for i in itens] == [("abertura", "Pratique X")]
    assert itens[0]["distancia_m"] == 0
    c = mov.contar(itens)
    assert (c["abertura"], c["fechamento"], c["saiu_agregador"]) == (1, 0, 0)
    assert mov.eventos_no_entorno(-23.0, -46.0, None) == []
    assert {p["confianca"] for p in mov.periodos(filtrados)} == {"alta", "cautela"}


def test_abre_e_fecha_da_mesma_rede_perto_e_troca_de_cadastro_nao_movimento():
    q = mov.normalizar_cadastro(_cadastro().iloc[[0, 1]].assign(latitude=["-23.0", "-23.004"]))
    assert q.empty
    longe = mov.normalizar_cadastro(_cadastro().iloc[[0, 1]].assign(latitude=["-23.0", "-23.05"]))
    assert sorted(longe["tipo"]) == ["abertura", "fechamento"]


def test_resumo_por_rede_soma_saldo_e_separa_o_conferido_e_agregador_fica_a_parte():
    eventos = pd.DataFrame([
        {"fonte": "cadastro", "tipo": "abertura", "confianca": "alta", "rede": "pratique"},
        {"fonte": "cadastro", "tipo": "inauguracao", "confianca": "cautela", "rede": "pratique"},
        {"fonte": "cadastro", "tipo": "fechamento", "confianca": "alta", "rede": "selfit"},
        {"fonte": "em_breve", "tipo": "em_breve", "confianca": "alta", "rede": "selfit"},
        {"fonte": "wellhub", "tipo": "entrou_agregador", "confianca": "alta", "rede": None, "de": "2026-08-31", "ate": "2026-09-05"},
        {"fonte": "wellhub", "tipo": "saiu_agregador", "confianca": "alta", "rede": "bluefit", "de": "2026-09-05", "ate": "2026-09-12"},
    ])
    redes = mov.resumo_por_rede(eventos)
    assert [(r["rede"], r["aberturas"], r["aberturas_conferidas"], r["saldo"], r["em_breve"]) for r in redes] == [
        ("pratique", 2, 1, 2, 0), ("selfit", 0, 0, -1, 1),
    ]
    agg = {a["grupo"]: a for a in mov.resumo_agregadores(eventos)}
    assert (agg["independentes"]["entradas"], agg["redes"]["saidas"], agg["redes"]["ate"]) == (1, 1, "2026-09-12")
    assert mov.resumo_por_rede(None) == [] and mov.resumo_agregadores(None) == []


def test_saida_e_entrada_no_mesmo_ponto_sao_renomeacao_e_nao_movimento():
    """A Braves renomeou 7 unidades de uma vez e a ficha leu 7 saidas + 7 entradas (18/09)."""
    def linha(tipo, nome, lat, lng):
        return {"fonte": "wellhub", "tipo": tipo, "confianca": "alta", "rede": None,
                "nome": nome, "lat": lat, "lng": lng, "de": "2026-09-05", "ate": "2026-09-12"}

    quadro = pd.DataFrame(
        [
            linha("saiu_agregador", "Braves Gym Club - Uberlandia", -18.912412, -48.266396),
            linha("entrou_agregador", "Braves - Uberlandia", -18.912412, -48.266396),  # MESMO ponto
            linha("saiu_agregador", "Fechou de verdade", -23.5, -46.6),
            linha("entrou_agregador", "Entrou de verdade", -22.9, -43.2),
        ]
    )
    saida = mov.descartar_trocas_de_nome_no_agregador(quadro)
    assert sorted(saida["nome"]) == ["Entrou de verdade", "Fechou de verdade"]
    # periodos diferentes nao casam: so' se descarta o par da MESMA foto
    outro = quadro.copy()
    outro.loc[1, "de"] = "2026-08-01"
    assert len(mov.descartar_trocas_de_nome_no_agregador(outro)) == 4


def test_operador_novo_no_mesmo_endereco_nao_e_renomeacao():
    """Coordenada igual NAO basta: oito dos 38 pares medidos em 18/09 eram troca de dono.

    "Baby Gym Paulinia" -> "Brinca e Voa" no mesmo ponto e' mercado se mexendo. So' cai o
    par que divide um termo PROPRIO — e "academia" nao conta, senao qualquer vizinho casaria.
    """
    def linha(tipo, nome):
        return {"fonte": "wellhub", "tipo": tipo, "confianca": "alta", "rede": None,
                "nome": nome, "lat": -23.0, "lng": -46.0, "de": "2026-09-05", "ate": "2026-09-12"}

    trocou_de_dono = pd.DataFrame([linha("saiu_agregador", "Academia Total Force"), linha("entrou_agregador", "JF7 Fitness")])
    assert len(mov.descartar_trocas_de_nome_no_agregador(trocou_de_dono)) == 2

    # so' o generico em comum tambem nao basta
    generico = pd.DataFrame([linha("saiu_agregador", "Ultra Academia - Centro"), linha("entrou_agregador", "Academia Nova")])
    assert len(mov.descartar_trocas_de_nome_no_agregador(generico)) == 2

    # termo proprio em comum, mesmo com o resto do nome diferente: e' renomeacao
    renomeou = pd.DataFrame([linha("saiu_agregador", "Academia DNA - Vilhena"), linha("entrou_agregador", "DNA ACADEMIA")])
    assert len(mov.descartar_trocas_de_nome_no_agregador(renomeou)) == 0


def test_contagem_oficial_para_no_fim_validado_e_nao_na_foto_corrompida():
    tabela = pd.DataFrame({"rede": ["selfit", "nova"], "2026-08-30": [230, None], "2026-09-06": [231, 5], "2026-09-13": [119, 5]})
    c = mov.contagem_oficial(tabela, "2026-09-06")
    assert c.to_dict("records") == [
        {"rede": "selfit", "unidades": 231, "data": "2026-09-06"},
        {"rede": "nova", "unidades": 5, "data": "2026-09-06"},
    ]
    assert mov.contagem_oficial(tabela, "2026-09-01")["unidades"].tolist() == [230]
    assert mov.contagem_oficial(tabela, "2026-01-01").empty


def test_rede_mapeada_sem_movimentacao_entra_zerada_e_estudio_fica_fora():
    """A tabela carrega o TAMANHO do mercado, nao so' quem se mexeu (Felipe, 17/09)."""
    redes = [{"rede": "pratique", "aberturas": 2, "fechamentos": 0, "saldo": 2, "em_breve": 0, "unidades": 184}]
    totais = {"pratique": 184, "smart_fit": 1000, "cia_athletica": 19, "velocity": 125, "ultra": 92}
    saida = mov.incluir_redes_sem_movimentacao(redes, totais, excluir={"velocity"})
    # as paradas vem depois das que se mexeram, da maior para a menor; estudio e Ultra fora
    assert [r["rede"] for r in saida] == ["pratique", "smart_fit", "cia_athletica"]
    parada = saida[1]
    assert (parada["unidades"], parada["aberturas"], parada["fechamentos"], parada["saldo"]) == (1000, 0, 0, 0)
    assert parada["aberturas_conferidas"] == 0 and parada["em_breve"] == 0
    # sem contagem nenhuma, a lista original volta intacta
    assert mov.incluir_redes_sem_movimentacao(redes, {}) == redes


# --------------------------------------------------------------------------- #
# O card inteiro: contagem SEMANAL + movimento do pacote (`crescimento_por_rede`)
# --------------------------------------------------------------------------- #
def _eventos_do_pacote():
    return pd.DataFrame([
        {"fonte": "cadastro", "tipo": "abertura", "confianca": "alta", "rede": "pratique",
         "de": "2026-08-02", "ate": "2026-09-06"},
        {"fonte": "cadastro", "tipo": "fechamento", "confianca": "cautela", "rede": "pratique",
         "de": "2026-05-28", "ate": "2026-08-02"},
        {"fonte": "em_breve", "tipo": "em_breve", "confianca": "alta", "rede": "smart_fit",
         "de": "2026-07-01", "ate": "2026-09-06"},
        {"fonte": "wellhub", "tipo": "entrou_agregador", "confianca": "alta", "rede": None,
         "de": "2026-08-31", "ate": "2026-09-12"},
    ])


def _contagem_do_pacote():
    """A contagem de 06/09 que o pacote trouxe (a Smart Fit ainda presa no teto de 1.000)."""
    return pd.DataFrame({
        "rede": ["pratique", "smart_fit", "selfit", "skyfit", "bluefit", "velocity", "ultra"],
        "unidades": [184, 1000, 231, 205, 118, 125, 92],
        "data": ["2026-09-06"] * 7,
    })


def _semanal():
    """O que `saldo_rede.contagem_da_tela` devolve numa semana com uma rede de cada situação."""
    return {
        "data": "2026-11-01",
        "data_anterior": "2026-10-25",
        "execucao_mais_recente": "2026-11-01",
        "linhas_sem_data": 0,
        "unidades": {"pratique": 190, "smart_fit": 1061, "selfit": 233, "skyfit": 140, "bluefit": 120,
                     "velocity": 130, "ultra": 171, "estreante": 12},
        "variacao": {
            "pratique": {"delta": 1, "status": "variou"},
            "smart_fit": {"delta": 2, "status": "variou"},
            "selfit": {"delta": None, "status": "segurada"},
            "skyfit": {"delta": -70, "status": "confirmada"},
            "bluefit": {"delta": None, "status": "nao_recoletada"},
            "velocity": {"delta": 5, "status": "variou"},
            "ultra": {"delta": 1, "status": "variou"},
            "estreante": {"delta": None, "status": "novo"},
        },
        "recusadas": [],
        "seguradas": [{"rede": "selfit", "antes": 233, "agora": 119, "direcao": "queda", "desde": "2026-11-01"}],
        "confirmadas": [{"rede": "skyfit", "antes": 210, "agora": 140, "direcao": "queda", "desde": "2026-10-25"}],
        "nao_recoletadas": ["bluefit"],
        "ausentes": [],
        "removidas": [],
        "total_confirmado": False,
    }


def test_card_le_unidades_da_contagem_semanal_e_movimento_do_pacote():
    """O defeito de 04/11/2026: as unidades vinham da contagem de 06/09 do pacote e ficaram paradas."""
    card = mov.crescimento_por_rede(_eventos_do_pacote(), _contagem_do_pacote(), _semanal(), excluir={"velocity"})
    assert (card["disponivel"], card["tem_cadastro"], card["contagem_origem"], card["data_contagem"]) == (
        True, True, "semanal", "2026-11-01",
    )
    linhas = {r["rede"]: r for r in card["redes"]}
    # estúdio (DEC-056) e a própria Ultra ficam fora da contagem E da tabela
    assert set(linhas) == {"pratique", "smart_fit", "selfit", "skyfit", "bluefit", "estreante"}
    # cada coluna com a sua fonte: unidades de 01/11, movimento de setembro
    pratique = linhas["pratique"]
    assert (pratique["unidades"], pratique["aberturas_conferidas"], pratique["fechamentos"]) == (190, 1, 1)
    assert (pratique["variacao"], pratique["variacao_status"], pratique["sem_cadastro"]) == (1, "variou", None)
    # a Smart Fit tem contagem inteira, mas NENHUMA leitura de cadastro: zero ali seria afirmação
    assert (linhas["smart_fit"]["unidades"], linhas["smart_fit"]["sem_cadastro"]) == (1061, "teto_coletor")
    assert linhas["smart_fit"]["em_breve"] == 1, "o pipeline 'Em breve' dela não era NAO_USAR"
    # rede que o coletor passou a cobrir depois do pacote: sem leitura de setembro, e `novo` na variação
    assert linhas["estreante"]["sem_cadastro"] == "fora_da_cobertura"
    assert (linhas["estreante"]["variacao"], linhas["estreante"]["variacao_status"]) == (None, "novo")
    # a rede segurada mostra a última contagem boa e leva junto o número que ficou de fora
    selfit = linhas["selfit"]
    assert (selfit["unidades"], selfit["variacao"], selfit["variacao_status"], selfit["lido"]) == (
        233, None, "segurada", 119,
    )
    assert linhas["bluefit"]["variacao_status"] == "nao_recoletada" and linhas["bluefit"]["lido"] is None
    # mercado: só quem tem contagem; a variação total soma o que a tela mostra com número
    # (variou, estável e confirmada) e deixa de fora novo, segurada e não recoletada
    assert (card["redes_mapeadas"], card["unidades_mapeadas"]) == (6, 190 + 1061 + 233 + 140 + 120 + 12)
    assert card["variacao_total"] == 1 + 2 - 70
    assert card["contagem"]["data_anterior"] == "2026-10-25"
    assert card["contagem"]["nao_recoletadas"] == ["bluefit"]
    assert "unidades" not in card["contagem"], "o laudo não repete o que já viaja nas linhas"
    assert {(p["fonte"], p["confianca"]) for p in card["periodos"]} == {
        ("cadastro", "alta"), ("cadastro", "cautela"), ("em_breve", "alta"), ("wellhub", "alta"),
    }


def test_card_sem_contagem_semanal_cai_para_a_do_pacote_e_diz_de_quando():
    card = mov.crescimento_por_rede(
        _eventos_do_pacote(), _contagem_do_pacote(), {"erro": "ausente"}, excluir={"velocity"}
    )
    assert (card["contagem_origem"], card["data_contagem"], card["contagem"]["erro"]) == (
        "pacote", "2026-09-06", "ausente",
    )
    assert {r["rede"]: r["unidades"] for r in card["redes"]}["smart_fit"] == 1000
    assert all(r["variacao"] is None and r["variacao_status"] is None for r in card["redes"])
    assert card["variacao_total"] is None


def test_card_sem_o_pacote_mostra_so_a_contagem():
    """O pacote não se regenera: perdê-lo não pode apagar a contagem semanal."""
    card = mov.crescimento_por_rede(None, None, _semanal(), excluir={"velocity"})
    assert (card["disponivel"], card["tem_cadastro"], card["contagem_origem"]) == (True, False, "semanal")
    assert {r["rede"] for r in card["redes"]} == {"pratique", "smart_fit", "selfit", "skyfit", "bluefit", "estreante"}
    assert all(r["sem_cadastro"] is None for r in card["redes"]), "sem pacote, as colunas somem inteiras"
    assert card["agregadores"] == [] and card["periodos"] == []


def test_card_sem_nenhuma_fonte_nao_esta_disponivel():
    card = mov.crescimento_por_rede(None, None, {"erro": "ilegivel"})
    assert card["disponivel"] is False and card["redes"] == []
    assert card["contagem"]["erro"] == "ilegivel", "a tela diz POR QUE está vazia"


def test_semanal_sem_contagem_boa_nao_conta_como_contagem():
    vazia = {**_semanal(), "data": None, "data_anterior": None, "unidades": {}, "variacao": {}}
    card = mov.crescimento_por_rede(_eventos_do_pacote(), _contagem_do_pacote(), vazia)
    assert (card["contagem_origem"], card["data_contagem"]) == ("pacote", "2026-09-06")


def test_todo_motivo_sem_cadastro_emitido_esta_no_vocabulario():
    """Os motivos que o card emite são exatamente os que a tela sabe explicar (a paridade com o
    TypeScript fica em `test_paridade_crescimento_concorrencia_web.py`)."""
    card = mov.crescimento_por_rede(_eventos_do_pacote(), _contagem_do_pacote(), _semanal())
    emitidos = {r["sem_cadastro"] for r in card["redes"]} - {None}
    assert emitidos == set(mov.MOTIVOS_SEM_CADASTRO)
    assert set(mov.REDES_FORA_DO_CADASTRO.values()) <= set(mov.MOTIVOS_SEM_CADASTRO)
