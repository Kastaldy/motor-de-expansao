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
