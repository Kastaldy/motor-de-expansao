"""Inteligência da rede (`web/server/rede_inteligencia.py`) e as rotas que a servem.

O que se trava aqui é a FORMA de cada leitura, não só a conta — o defeito recorrente do
piloto é valor legítimo no lugar errado (ausência que vira zero, unidade que não casa e
some em silêncio, quartil degenerado que acende alerta).
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import pytest

_REPO = Path(__file__).resolve().parents[2]
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import app as pilot  # noqa: E402
import rede_inteligencia as ri  # noqa: E402

from tests.unit.test_piloto_web_rede import rede  # noqa: E402,F401  (fixture)

# ---------------------------------------------------------------------------
# Distância e fatos territoriais
# ---------------------------------------------------------------------------


def test_distancia_de_um_grau_de_latitude():
    import numpy as np

    d = ri.distancias_m(0.0, 0.0, np.array([1.0]), np.array([0.0]))
    assert 111_000 < d[0] < 111_400


def _unidades():
    return pd.DataFrame([{"unidade_id": "u1", "lat": -23.0, "lng": -46.0}])


def test_concorrencia_separa_cadeia_de_independente_e_raio():
    # ~0,009 grau de latitude = ~1 km
    conc = pd.DataFrame(
        [
            {"lat": -23.004, "lng": -46.0, "classe": "cadeia", "rede": "Smart Fit"},
            {"lat": -23.005, "lng": -46.0, "classe": "independente", "rede": ""},
            {"lat": -23.015, "lng": -46.0, "classe": "cadeia", "rede": "Bluefit"},
            {"lat": -23.2, "lng": -46.0, "classe": "cadeia", "rede": "Longe"},
        ]
    )
    fatos = ri.fatos_territoriais(_unidades(), conc, None, None)["u1"]
    assert fatos["concorrentes_1km"] == 2
    assert fatos["cadeias_1km"] == 1
    assert fatos["independentes_1km"] == 1
    assert fatos["cadeias_2km"] == 2
    assert fatos["cadeia_mais_proxima_rede"] == "Smart Fit"
    assert {r["rede"] for r in fatos["redes_no_entorno"]} == {"Smart Fit", "Bluefit"}


def test_ausencia_de_base_de_concorrentes_e_none_nunca_zero():
    fatos = ri.fatos_territoriais(_unidades(), None, None, None)["u1"]
    assert fatos["concorrentes_1km"] is None
    assert fatos["canibalizacao"] is None
    assert fatos["score_praca"] is None


def test_a_propria_unidade_nao_conta_como_canibalizacao():
    ultra = pd.DataFrame(
        [
            {"unidade": "Ela mesma", "lat": -23.0001, "lng": -46.0},
            {"unidade": "Vizinha", "lat": -23.006, "lng": -46.0},
        ]
    )
    fatos = ri.fatos_territoriais(_unidades(), None, ultra, None)["u1"]
    assert fatos["ultra_mais_proxima_nome"] == "Vizinha"
    assert fatos["canibalizacao"] is True
    assert fatos["ultra_2km"] == 1


def test_praca_do_disco_pondera_por_populacao():
    hexes = pd.DataFrame(
        [
            {"hex_id": "h0", "nome_municipio": "X", "score_setor_2022_calibrado": 80.0,
             "pop_total_setor_2022": 9_000.0, "oferta_efetiva_disponivel": 100.0,
             "renda_per_capita_setor_2022_calibrada": 2_000.0},
            {"hex_id": "h1", "nome_municipio": "X", "score_setor_2022_calibrado": 20.0,
             "pop_total_setor_2022": 1_000.0, "oferta_efetiva_disponivel": 50.0,
             "renda_per_capita_setor_2022_calibrada": 1_000.0},
        ]
    ).set_index("hex_id")
    fatos = ri.fatos_territoriais(_unidades(), None, None, hexes, {"u1": ["h0", "h1", "fora"]})["u1"]
    assert fatos["score_praca"] == pytest.approx(74.0)
    assert fatos["populacao_entorno"] == 10_000
    assert fatos["residual_entorno"] == 150
    assert fatos["hexes_lidos"] == 2
    assert fatos["municipio"] == "X"


def test_entorno_ordena_por_distancia_e_casa_fatos_do_agregador_so_no_mesmo_ponto():
    oferta = pd.DataFrame(
        [
            {"lat": -23.010, "lng": -46.0, "nome": "Longe", "rede": "bluefit", "classe": "cadeia"},
            {"lat": -23.003, "lng": -46.0, "nome": "Perto", "rede": "", "classe": "independente"},
            {"lat": -23.300, "lng": -46.0, "nome": "Fora", "rede": "x", "classe": "cadeia"},
        ]
    )
    agregador = pd.DataFrame(
        [{"lat": -23.00301, "lng": -46.0, "nota_wellhub": 4.8, "qtd_avaliacoes_wellhub": 120,
          "score_vulnerabilidade": 71.0}]
    )
    saida = ri.concorrentes_no_entorno(-23.0, -46.0, oferta, agregador)
    assert [c["nome"] for c in saida] == ["Perto", "Longe"]
    assert saida[0]["vulnerabilidade"] == 71.0 and saida[0]["nota_wellhub"] == 4.8
    assert saida[1]["vulnerabilidade"] is None  # sem par a <= 50 m: ausência, nunca zero
    assert ri.concorrentes_no_entorno(-23.0, -46.0, None) == []


def test_entorno_nao_lista_a_propria_ultra_como_concorrente():
    oferta = pd.DataFrame(
        [
            {"lat": -23.0003, "lng": -46.0, "nome": "Ultra Academia - Aclimação", "rede": "", "classe": "independente"},
            {"lat": -23.008, "lng": -46.0, "nome": "ULTRA ACADEMIA Cambuci", "rede": "", "classe": "independente"},
            {"lat": -23.0002, "lng": -46.0, "nome": "Mesmo ponto, outra grafia", "rede": "", "classe": "independente"},
            {"lat": -23.005, "lng": -46.0, "nome": "Koka Academia", "rede": "", "classe": "independente"},
        ]
    )
    assert [c["nome"] for c in ri.concorrentes_no_entorno(-23.0, -46.0, oferta)] == ["Koka Academia"]


def test_praca_no_raio_de_1km_entra_pela_fracao_da_area():
    hexes = pd.DataFrame(
        [
            {"hex_id": "h0", "nome_municipio": "X", "score_setor_2022_calibrado": 80.0,
             "pop_total_setor_2022": 9_000.0, "oferta_efetiva_disponivel": 100.0},
            {"hex_id": "h1", "nome_municipio": "X", "score_setor_2022_calibrado": 20.0,
             "pop_total_setor_2022": 1_000.0, "oferta_efetiva_disponivel": 50.0},
            {"hex_id": "h2", "nome_municipio": "X", "score_setor_2022_calibrado": 10.0,
             "pop_total_setor_2022": 5_000.0, "oferta_efetiva_disponivel": 70.0},
        ]
    ).set_index("hex_id")
    pesos = {"u1": {"h0": 0.5, "h1": 0.1, "h2": 0.0}}
    fatos = ri.fatos_territoriais(_unidades(), None, None, hexes, {"u1": ["h0", "h1", "h2"]}, pesos)["u1"]
    # 9.000*0,5 + 1.000*0,1 = 4.600; o hexágono fora do círculo (fração 0) não entra
    assert fatos["populacao_entorno"] == 4_600
    assert fatos["residual_entorno"] == 55
    assert fatos["hexes_lidos"] == 2
    assert fatos["score_praca"] == pytest.approx((80 * 4_500 + 20 * 100) / 4_600, abs=0.1)


# ---------------------------------------------------------------------------
# Quadrante
# ---------------------------------------------------------------------------


def _ponto(i, praca, fat, meses=24):
    return {"id": f"u{i}", "nome": f"U{i}", "score_praca": praca, "faturamento": fat, "meses_operacao": meses}


def test_quadrante_usa_medianas_e_classifica_os_quatro():
    pontos = [_ponto(1, 90, 400), _ponto(2, 90, 100), _ponto(3, 10, 400), _ponto(4, 10, 100)]
    q = ri.quadrante_praca_execucao(pontos)
    por_id = {p["id"]: p["quadrante"] for p in q["pontos"]}
    assert por_id == {"u1": "referencia", "u2": "execucao", "u3": "supera", "u4": "limite"}
    assert q["corte_praca"] == 50.0


def test_quadrante_tira_as_novas_por_padrao():
    pontos = [_ponto(i, 50 + i, 100 * i) for i in range(1, 5)] + [_ponto(9, 99, 999, meses=3)]
    assert all(p["id"] != "u9" for p in ri.quadrante_praca_execucao(pontos)["pontos"])
    assert any(p["id"] == "u9" for p in ri.quadrante_praca_execucao(pontos, somente_maduras=False)["pontos"])


def test_quadrante_com_menos_de_quatro_pontos_nao_inventa_corte():
    q = ri.quadrante_praca_execucao([_ponto(1, 90, 400)])
    assert q["corte_praca"] is None and q["n"] == 1


# ---------------------------------------------------------------------------
# Retenção
# ---------------------------------------------------------------------------


def test_retencao_casa_codigo_com_zero_a_esquerda_e_respeita_prob_absoluta():
    tabela = pd.DataFrame(
        [
            {"cod_unidade": "01", "N_ALUNOS": 500, "PROB_CANCEL_90D_MEDIA": 0.2,
             "USAR_PROB_ABSOLUTA": "Sim", "PCT_LTV_FRAGIL": 0.1, "LTV_PROSPECTIVO_12M_MEDIANO": 1200},
            {"cod_unidade": "12", "N_ALUNOS": 800, "PROB_CANCEL_90D_MEDIA": 0.1,
             "USAR_PROB_ABSOLUTA": "Nao", "PCT_LTV_FRAGIL": 0.05, "LTV_PROSPECTIVO_12M_MEDIANO": 1400},
        ]
    )
    saida = ri.retencao_por_unidade(tabela, {"a": "1", "b": 12.0, "c": None})
    assert set(saida) == {"a", "b"}
    assert saida["a"]["prob_cancel_90d_pct"] == 20.0
    assert saida["b"]["prob_cancel_90d_pct"] is None  # o modelo diz: só ranking
    assert saida["a"]["risco_percentil"] > saida["b"]["risco_percentil"]


def test_retencao_nao_ranqueia_unidade_onde_o_modelo_se_declara_instavel():
    tabela = pd.DataFrame(
        [
            {"cod_unidade": "1", "PROB_CANCEL_90D_MEDIA": 0.9, "USAR_PROB_ABSOLUTA": "Sim",
             "CONFIABILIDADE_UNIDADE": "Instavel (N/eventos baixos)"},
            {"cod_unidade": "2", "PROB_CANCEL_90D_MEDIA": 0.2, "USAR_PROB_ABSOLUTA": "Sim",
             "CONFIABILIDADE_UNIDADE": "Absoluto OK"},
            {"cod_unidade": "3", "PROB_CANCEL_90D_MEDIA": 0.1, "USAR_PROB_ABSOLUTA": "Nao",
             "CONFIABILIDADE_UNIDADE": "Apenas Ranking"},
        ]
    )
    saida = ri.retencao_por_unidade(tabela, {"a": "1", "b": "2", "c": "3"})
    assert saida["a"]["utilizavel"] is False
    assert saida["a"]["risco_percentil"] is None and saida["a"]["prob_cancel_90d_pct"] is None
    # a instável (0,9) não entra na distribuição: a de 0,2 vira o topo
    assert saida["b"]["risco_percentil"] == 100.0 and saida["c"]["risco_percentil"] == 50.0


def test_receita_em_risco_pondera_pela_chance_de_cancelar():
    """Alunos x chance em 12 meses x ticket — nao a receita recorrente inteira."""
    tabela = pd.DataFrame(
        [
            {"cod_unidade": "1", "PROB_CANCEL_90D_MEDIA": 0.2, "P_CANCEL_12M_MEDIA": 0.4,
             "N_ALUNOS": 1000, "TICKET_MEDIO_UNIDADE": 117.0, "USAR_PROB_ABSOLUTA": "Sim",
             "CONFIABILIDADE_UNIDADE": "Absoluto OK"},
            # o modelo diz que o absoluto nao vale: sai vazio, nao vira reais com falsa precisao
            {"cod_unidade": "2", "PROB_CANCEL_90D_MEDIA": 0.1, "P_CANCEL_12M_MEDIA": 0.3,
             "N_ALUNOS": 500, "TICKET_MEDIO_UNIDADE": 117.0, "USAR_PROB_ABSOLUTA": "Nao",
             "CONFIABILIDADE_UNIDADE": "Apenas Ranking"},
        ]
    )
    saida = ri.retencao_por_unidade(tabela, {"a": "1", "b": "2"})
    assert saida["a"]["p_cancel_12m_pct"] == 40.0
    assert saida["b"]["p_cancel_12m_pct"] is None  # o modelo diz: so' ranking
    assert saida["b"]["ticket_medio"] == 117.0  # o ticket e' fato, nao previsao

    # A conta e' sobre a operacao: RECORRENTES x chance x receita por recorrente REAL.
    assert ri.receita_recorrente_em_risco(1000, 40.0, 150.0) == 60000.0
    # sem probabilidade (o modelo nao libera o absoluto), nao se inventa o numero
    assert ri.receita_recorrente_em_risco(1000, None, 150.0) is None
    assert ri.receita_recorrente_em_risco(None, 40.0, 150.0) is None


# ---------------------------------------------------------------------------
# Concorrentes novos
# ---------------------------------------------------------------------------


def _snap(semana, chave):
    return {"semana": semana, "fonte": "wellhub", "chave_snapshot": chave}


def test_concorrente_novo_exige_serie_e_ignora_a_primeira_semana():
    coords = pd.DataFrame(
        [
            {"fonte": "wellhub", "chave_snapshot": "antiga", "nome": "Antiga", "lat": -23.001, "lng": -46.0},
            {"fonte": "wellhub", "chave_snapshot": "nova", "nome": "Nova", "lat": -23.002, "lng": -46.0},
        ]
    )
    so_uma = pd.DataFrame([_snap("2026-30", "antiga")])
    assert ri.concorrentes_novos(so_uma, coords, _unidades())["disponivel"] is False

    serie = pd.DataFrame([_snap("2026-30", "antiga"), _snap("2026-31", "antiga"), _snap("2026-31", "nova")])
    saida = ri.concorrentes_novos(serie, coords, _unidades())
    assert saida["disponivel"] is True
    assert [i["nome"] for i in saida["por_unidade"]["u1"]] == ["Nova"]


def test_novo_no_agregador_ignora_a_estreia_de_CADA_fonte_e_nao_lista_a_ultra():
    """Dois defeitos vistos na ficha de Uberlandia em 18/09.

    (1) A estreia descartada era a da SERIE, nao a da FONTE: `unidades` era fotografada desde
    a semana 2026-31 e `wellhub` so' a partir de 2026-36, entao as 22.550 chaves do WellHub
    passavam como recem-chegadas e a ficha listava o bairro inteiro.
    (2) A propria Ultra entrava na lista (Center Shopping a 141 m, Floriano Peixoto, Cesario).
    """
    coords = pd.DataFrame(
        [
            {"fonte": "wellhub", "chave_snapshot": "wh_estreia", "nome": "Ja' estava", "lat": -23.001, "lng": -46.0},
            {"fonte": "wellhub", "chave_snapshot": "wh_nova", "nome": "Nova", "lat": -23.002, "lng": -46.0},
            {"fonte": "wellhub", "chave_snapshot": "wh_ultra", "nome": "Ultra Academia Center Shopping",
             "lat": -23.0015, "lng": -46.0},
            {"fonte": "unidades", "chave_snapshot": "un_estreia", "nome": "Cadeia", "lat": -23.003, "lng": -46.0},
        ]
    )
    serie = pd.DataFrame(
        [
            {"semana": "2026-31", "fonte": "unidades", "chave_snapshot": "un_estreia"},
            {"semana": "2026-36", "fonte": "unidades", "chave_snapshot": "un_estreia"},
            # o WellHub so' comeca a ser fotografado em 2026-36: esta e' a ESTREIA dele
            {"semana": "2026-36", "fonte": "wellhub", "chave_snapshot": "wh_estreia"},
            {"semana": "2026-37", "fonte": "wellhub", "chave_snapshot": "wh_estreia"},
            {"semana": "2026-37", "fonte": "wellhub", "chave_snapshot": "wh_nova"},
            {"semana": "2026-37", "fonte": "wellhub", "chave_snapshot": "wh_ultra"},
        ]
    )
    saida = ri.concorrentes_novos(serie, coords, _unidades())
    assert saida["disponivel"] is True
    # `wh_estreia` nao e' novidade (estreia da fonte) e a Ultra nao e' concorrente nossa
    assert [i["nome"] for i in saida["por_unidade"]["u1"]] == ["Nova"]


def test_sem_snapshots_nao_afirma_ausencia():
    saida = ri.concorrentes_novos(None, None, _unidades())
    assert saida["disponivel"] is False and saida["por_unidade"] == {}


# ---------------------------------------------------------------------------
# Rampa
# ---------------------------------------------------------------------------


def _cheio_rampa():
    linhas = []
    for u in range(6):
        for m in range(1, 5):
            linhas.append({
                "unidade_id": f"u{u}", "unidade_cru": f"U{u}", "uf": "SP",
                "competencia": f"2026-0{m}", "meses_operacao": float(m),
                "faturamento": 10_000.0 * m * (1 + u / 10), "ativos": 100.0 * m,
                "mes_completo": True, "operacao_mes_cheio": True,
            })
    return pd.DataFrame(linhas)


def test_curva_de_rampa_exige_n_minimo_e_sai_ordenada():
    curva = ri.curva_de_rampa(_cheio_rampa())
    assert [p["mes"] for p in curva] == [1, 2, 3, 4]
    assert all(p["n"] == 6 for p in curva)
    menor = _cheio_rampa()
    menor = menor[menor["unidade_id"].isin(["u0", "u1"])]
    assert ri.curva_de_rampa(menor) == []


def test_posicao_na_rampa_marca_abaixo_do_p25():
    cheio = _cheio_rampa()
    cheio.loc[(cheio.unidade_id == "u0") & (cheio.competencia == "2026-03"), "faturamento"] = 1_000.0
    posicao = {p["id"]: p for p in ri.posicao_na_rampa(cheio, "2026-03")}
    assert posicao["u0"]["faixa"] == "abaixo"
    assert posicao["u0"]["desvio_pct"] < 0


# ---------------------------------------------------------------------------
# Sinais antecedentes
# ---------------------------------------------------------------------------


def test_zero_nunca_acende_sinal_de_quartil_alto():
    linhas = []
    for u in range(10):
        for comp in ("2026-04", "2026-07"):
            linhas.append({
                "unidade_id": f"u{u}", "competencia": comp, "operacao_mes_cheio": True,
                "pagantes": 1000.0, "em_cobranca_pct": 0.0,
            })
    cheio = pd.DataFrame(linhas)
    base = pd.DataFrame(
        [{"unidade_id": f"u{u}", "_data": pd.Timestamp("2026-07-31"), "cancelamento_solicitado": 0}
         for u in range(10)]
    )
    sinais = ri.sinais_antecedentes(cheio, base, "2026-07")
    assert all(s["acesos"] == 0 for s in sinais.values())


def test_sinal_de_recorrentes_acende_no_quartil_de_queda():
    linhas = []
    for u in range(10):
        linhas.append({"unidade_id": f"u{u}", "competencia": "2026-04", "operacao_mes_cheio": True,
                       "pagantes": 1000.0, "em_cobranca_pct": 1.0})
        linhas.append({"unidade_id": f"u{u}", "competencia": "2026-07", "operacao_mes_cheio": True,
                       "pagantes": 1000.0 - (400.0 if u == 0 else 0.0), "em_cobranca_pct": 1.0})
    sinais = ri.sinais_antecedentes(pd.DataFrame(linhas), pd.DataFrame(), "2026-07")
    recorrentes = {s["chave"]: s for s in sinais["u0"]["sinais"]}["recorrentes_3m_pct"]
    assert recorrentes["valor"] == -40.0 and recorrentes["aceso"] is True


# ---------------------------------------------------------------------------
# Expansão e mudanças
# ---------------------------------------------------------------------------


@dataclass
class _Alerta:
    codigo: str
    titulo: str
    nivel: str = "grave"


@dataclass
class _Diag:
    severidade: str
    faixa_faturamento: str = "bom"
    faixa_faturamento_rotulo: str = "Bom"
    alertas: tuple = field(default_factory=tuple)


def test_mudancas_so_comparam_quem_existe_nos_dois_meses_e_ordenam_por_gravidade():
    atual = {
        "a": _Diag("alta", alertas=(_Alerta("churn", "Churn mensal"),)),
        "b": _Diag("ok"),
        "c": _Diag("alta"),
    }
    anterior = {"a": _Diag("ok"), "b": _Diag("media")}
    nomes = {"a": "Alfa", "b": "Beta", "c": "Gama"}
    eventos = ri.mudancas_do_mes(atual, anterior, nomes, competencia="2026-07")
    assert eventos[0]["unidade_id"] == "a" and eventos[0]["tipo"] == "severidade"
    assert {e["unidade_id"] for e in eventos} == {"a", "b"}  # Gama não tem mês anterior
    assert any(e["tipo"] == "alerta_novo" for e in eventos)
    assert {e["tom"] for e in eventos if e["unidade_id"] == "b"} == {"pos"}


def test_semana_menos_atravessa_o_ano():
    assert ri._semana_menos("2026-02", 4) == "2025-50"


# ---------------------------------------------------------------------------
# Rotas: contrato e degradação sem os artefatos territoriais
# ---------------------------------------------------------------------------


def test_rota_do_recorte_degrada_dizendo_o_que_falta(rede):  # noqa: F811
    payload = pilot.rede_inteligencia_recorte()
    assert set(payload) >= {"quadrante", "rampa", "sinais", "retencao", "concorrencia_nova", "mudancas", "notas"}
    assert payload["concorrencia_nova"]["disponivel"] is False
    assert any("snapshots" in n for n in payload["notas"])
    assert payload["retencao"]["data_artefato"] is None
    # sem coordenada, nenhuma unidade entra no quadrante — e isso é dito
    assert payload["quadrante"]["n"] == 0
    assert any("fora do quadrante" in n for n in payload["notas"])


def test_rota_do_recorte_respeita_o_filtro_da_carteira(rede):  # noqa: F811
    carteira = pilot.rede_carteira(uf="RJ")
    payload = pilot.rede_inteligencia_recorte(uf="RJ")
    assert payload["retencao"]["no_recorte"] == len(carteira["unidades"])


def test_rota_da_unidade_404_e_contrato(rede):  # noqa: F811
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        pilot.rede_unidade_inteligencia("nao-existe")
    payload = pilot.rede_unidade_inteligencia("botafogo-rj")
    assert payload["territorio"] is None
    assert payload["mapa"] is None  # sem coordenada, sem mapa
    assert payload["planos"] == {"disponivel": False}  # artefato não ingerido: dito, não vazio
    assert set(payload["rampa"]) == {"faturamento", "ativos", "pagantes", "agregadores", "posicao"}
    assert payload["concorrencia_nova"]["itens"] == []


def test_mudanca_carrega_os_campos_que_a_tela_agrupa():
    atual = {"a": _Diag("alta", faixa_faturamento="critico", faixa_faturamento_rotulo="Crítico",
                        alertas=(_Alerta("nps", "NPS"),))}
    anterior = {"a": _Diag("ok")}
    eventos = {e["tipo"]: e for e in ri.mudancas_do_mes(atual, anterior, {"a": "Alfa"}, competencia="2026-07")}
    assert eventos["severidade"]["de"] == "sem alerta" and eventos["severidade"]["para"] == "prioridade alta"
    assert eventos["severidade"]["motivos"] == ["NPS"]
    assert eventos["alerta_novo"]["alerta"] == "NPS"
    assert eventos["faixa"]["para"] == "Crítico"


def test_camadas_de_setor_sem_coordenada_dizem_indisponivel_e_trazem_as_faixas(rede):  # noqa: F811
    corpo = json.loads(pilot.rede_unidade_setores("botafogo-rj").body)
    assert corpo["disponivel"] is False and corpo["setores"] == []
    # a régua vem do núcleo, não é repetida na tela
    assert corpo["faixas"]["renda_domiciliar"] and corpo["faixas"]["densidade"]
    assert corpo["faixas"]["densidade"][-1]["ate"] is None  # a última faixa é aberta


def test_rotas_novas_ficam_atras_do_gate_da_executiva():
    import acesso

    for rota in ("/api/rede/inteligencia", "/api/rede/unidade/x/inteligencia", "/api/rede/unidade/x/setores"):
        assert any(rota.startswith(prefixo) and abas == frozenset({"executiva"})
                   for prefixo, abas in acesso.REGRAS_DE_ACESSO)
