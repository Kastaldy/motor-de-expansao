from __future__ import annotations

from motor_expansao.perfil import resolver_perfil

# Reguas absolutas do pais da INSTANCIA (Bloco A / DEC-047). No perfil brasileiro sao
# os mesmos numeros de sempre — `data/perfis/BR/perfil.json` os transcreve e
# `tests/contracts/test_perfil_br_reproduz_as_constantes.py` trava a igualdade.
_REGUAS = resolver_perfil().reguas

# Texto exibido nos relatorios PDF quando a metrica nao existe para o recorte (nenhum setor
# censitario intersectado, coluna ausente no parquet, valor NaN). Era a sigla "n/d", trocada
# por extenso a pedido de Juan (2026-07-31): quem le o PDF nao e do time e nao decodificava a
# sigla. Latin-1 safe -> passa pelo `_ascii()` dos geradores sem virar "?" (BLK-ACENTO-02).
# Os cards de valor grande encolhem a fonte ate caber (`_ajustar_fonte_para_largura`), entao a
# string longa nao estoura a grade 4x2 dos Big Numbers.
TEXTO_SEM_DADO = "Não disponível"

REQUIRED_COLUMNS = [
    "hex_id",
    "lat",
    "lng",
    "uf",
    "cidade",
    "regiao",
    "score_priorizacao",
    "hex_score_estrutural",
    "ajuste_executivo",
    "faixa_oportunidade",
    "flag_viavel",
    "flag_prioridade",
    "rank_brasil",
    "rank_uf",
    "rank_cidade",
    "renda_per_capita",
    "populacao_proxy",
]
OPTIONAL_DATASET_COLUMNS = ["confianca_geografica", "cod_municipio"]

#: FONTE UNICA das colunas da camada de mercado/residual por hexagono. Nao existe copia:
#: quem precisa da lista IMPORTA daqui. Os tres consumidores sao
#:   1. `dashboard/constants.HYBRID_LOAD_COLS` (logo abaixo) -> projecao de leitura do
#:      artefato hibrido/enriquecido;
#:   2. `pipelines/gerar_carteira_acionavel.py` -> `LOAD_COLS` e
#:      `carregar_colunas_residual_mercado`, que levam as colunas ao artefato enriquecido;
#:   3. `pipelines/enriquecer_outputs_residual_mercado.py`, que re-importa o nome de (2).
#:
#: Ate' 2026-09-10 (2) tinha um literal PROPRIO com o mesmo nome e o mesmo conteudo, e os
#: dois nao se enxergavam: acrescentar coluna em um so' era no-op SILENCIOSO. Foi o que
#: aconteceu no BLK-CAPACIDADE-01 -- ver o comentario de `n_concorrentes_influencia_1km`
#: mais abaixo. A identidade de objeto entre (1) e (2) e' travada por
#: `tests/unit/test_capacidade_real_residual.py` (identidade, nao igualdade: duas copias
#: iguais passariam num teste de conjunto).
#:
#: Mexer aqui e' mudanca CRITICA pelo `scripts/loop_guard.py`, e e' de proposito: este
#: contrato define a projecao de mercado servida em producao. Mover a lista para um modulo
#: "neutro" a tiraria do gate critico -- o furo que a DEC-048 fechou.
RESIDUAL_MERCADO_COLS = [
    "pop_hex_base",
    "fonte_pop_hex_base",
    "tam_populacao_hex",
    "tam_fitness_potencial",
    "flag_sam_fitness",
    "sam_fitness_potencial",
    "capacidade_default_concorrente_alunos",
    "oferta_consumida_mercado_estimada",
    # CONTAGEM de concorrentes que alcancam o hexagono, e ela precisa CHEGAR (BLK-CAPACIDADE-01).
    # Ate' aqui a tela derivava a contagem de `oferta_consumida / capacidade`, o que so' valia
    # enquanto toda academia consumia os mesmos 2.500 alunos. Com capacidade REAL por unidade a
    # divisao deixa de contar academias -- um Smart Fit de 5.000 vira "2 concorrentes" e desloca
    # o rotulo Livre/Adensar/Disputa por TAMANHO, nao por vizinhanca.
    #
    # Esquecer o nome NESTA lista e' o defeito da familia DEC-038 na forma mais pura: a coluna
    # existe em `hexagonos_mercado_mapeado`, o pipeline roda verde, o artefato sai sem ela e o
    # piloto cai no ramo antigo em silencio. Foi o que aconteceu na primeira regeneracao deste
    # bloco; so' apareceu ao conferir o schema do enriquecido ANTES do deploy.
    "n_concorrentes_influencia_1km",
    "oferta_consumida_ultra_real",
    "n_unidades_ultra_performance_hex",
    "oferta_efetiva_disponivel",
    "penetracao_fitness_mercado_estimada",
    "share_ultra_estimado_hex",
    "score_oportunidade_residual",
    "quartil_oportunidade_residual",
    "prioridade_mercado_mapeado",
    "tese_entrada",
]

HYBRID_LOAD_COLS = [
    "hex_id", "uf", "cidade", "nome_municipio",
    "score_priorizacao", "hex_score_estrutural", "faixa_oportunidade",
    "flag_viavel", "flag_prioridade", "rank_brasil", "rank_uf",
    "score_setor_2022_calibrado", "score_expansao_hibrido", "densidade_pop_setor_hab_km2",
    "top_municipio", "top_hex_intraurbano",
    "flag_censo_elegivel", "flag_censo_disponivel",
    "flag_hex_hibrido_elegivel", "top_municipio_hibrido", "municipio_censo_disponivel",
    "rank_municipio_uf", "rank_municipio_brasil", "rank_hex_intraurbano",
    "rank_hibrido_brasil", "rank_hibrido_uf",
    "top_oportunidade_municipio", "top_oportunidade_brasil", "top_oportunidade_uf",
    "qualidade_join_uf", "flag_join_uf_restrito", "flag_baixa_pop_setor",
    "flag_outlier_espacial", "coverage_pct_setor_2022",
    "motivo_nao_elegivel_censo", "status_espacial_uf", "fonte_camada_censitaria",
    "flag_monitoramento_prioritario", "criterio_score_expansao_hibrido",
    "camada_modelo_hibrido",
    "populacao_proxy", "renda_per_capita", "pop_total_setor_2022",
    "renda_per_capita_setor_2022_calibrada",
    *RESIDUAL_MERCADO_COLS,
]

CENSO_TRACE_LOAD_COLS = [
    "hex_id",
    "uf",
    "cod_municipio",
    "nome_municipio",
    "pop_total_setor_2022",
    "score_setor_2022_calibrado",
    "densidade_pop_setor_hab_km2",
    "coverage_pct_setor_2022",
    "qualidade_join_uf",
    "classe_join_uf",
    "flag_join_uf_restrito",
    "flag_baixa_pop_setor",
    "flag_outlier_espacial",
    "causa_outlier_espacial",
    "delta_vs_vizinhos",
    "metodo_join_setor_2022",
    "motivo_fallback_setor_2022",
    "renda_per_capita_setor_2022_calibrada",
]

HYBRID_ELIGIBILITY_ORDER = ["Elegivel", "Nao elegivel", "Sem camada"]
# Camada de LABEL de exibicao (D1-bis): exibe a elegibilidade hibrida acentuada sem
# tocar o valor bruto gravado em `elegibilidade_hibrida` (comparado em `.isin`).
HYBRID_ELIGIBILITY_LABELS = {
    "Elegivel": "Elegível",
    "Nao elegivel": "Não elegível",
    "Sem camada": "Sem camada",
}
COVERAGE_BUCKET_ORDER = ["100%", "95-99,9%", "85-94,9%", "<85%", "Sem camada"]
JOIN_QUALITY_ORDER = ["A", "B", "C", "Sem camada"]

FAIXA_ORDEM = [
    "prioridade_maxima",
    "alta",
    "media",
    "baixa",
    "descartado",
    "inviavel",
]
# Camada de LABEL de exibicao (D1): exibe as faixas acentuadas via format_func sem
# tocar o valor bruto de FAIXA_ORDEM (usado em `.isin`) nem as chaves de FAIXA_COLORS.
FAIXA_LABELS = {
    "prioridade_maxima": "Prioridade máxima",
    "alta": "Alta",
    "media": "Média",
    "baixa": "Baixa",
    "descartado": "Descartado",
    "inviavel": "Inviável",
}
MAP_POINT_LIMIT = 35000
# Cap efetivo reduzido para UFs grandes (recorte que satura MAP_POINT_LIMIT no
# Mapa Territorial). Mitiga OOM client-side (JS heap/WebGL) ao renderizar ~35k
# hexagonos H3 em GPU em estados como SP/AM/PA/MT/MG/BA. Nao altera score nem
# artefatos M1; nao altera MAP_POINT_LIMIT global (UFs pequenas inalteradas).
MAP_POINT_LIMIT_LARGE = 18000
# Cap de seguranca DURO por camada de pins (IconLayer de concorrentes/Ultra) no
# Mapa Territorial. Limita o payload das IconLayers INDEPENDENTE do total de pins
# (alvo: escalar a ~40k concorrentes sem OOM client-side). Amostragem deterministica
# por ordenacao estavel + head(N); aviso "amostrado" na UI. Nao altera score nem
# artefatos M1; pins sao camada visual de apoio (CLAUDE.md §2).
COMPETITOR_PIN_LIMIT = 6000
ULTRA_PIN_LIMIT = 6000
# BLK-FIX-07-B: clustering server-side dos pins de concorrente em recortes amplos
# (UF inteira / Brasil) -> agrega densidade em vez de cortar pins (Fase A). Camada
# VISUAL apenas: nao altera score, ranking, carteira nem artefatos M1.
COMPETITOR_CLUSTER_RES = 4            # resolucao H3 coarse (~22km/celula) p/ recorte amplo
COMPETITOR_CLUSTER_LIMIT = 2000      # cap duro de bolhas de cluster (garante payload << 3MB)
COMPETITOR_CLUSTER_TOP_REDES = 4     # max redes no breakdown do tooltip antes de "+N redes"
TABLE_ROW_LIMIT = 1000
# SEGUNDA copia do piso de populacao (a primeira e `web/server/app.py`). Duas copias de
# um numero so — exatamente o que o perfil existe para acabar.
POP_MIN_ACIONAVEL = _REGUAS.pop_min_acionavel
BRASIL_CENTER = {"lat": -14.235, "lon": -51.9253}
FLOAT_COLUMNS = [
    "lat",
    "lng",
    "score_priorizacao",
    "hex_score_estrutural",
    "ajuste_executivo",
    "rank_brasil",
    "rank_uf",
    "rank_cidade",
    "renda_per_capita",
    "populacao_proxy",
    "score_setor_2022_calibrado",
    "score_expansao_hibrido",
    "densidade_pop_setor_hab_km2",
    "coverage_pct_setor_2022",
    "rank_municipio_uf",
    "rank_municipio_brasil",
    "rank_hex_intraurbano",
    "rank_hibrido_brasil",
    "rank_hibrido_uf",
    "delta_vs_vizinhos",
    "populacao_corte_hex",
    "pop_hex_base",
    "tam_populacao_hex",
    "tam_fitness_potencial",
    "sam_fitness_potencial",
    "capacidade_default_concorrente_alunos",
    "oferta_consumida_mercado_estimada",
    "oferta_consumida_ultra_real",
    "n_unidades_ultra_performance_hex",
    "oferta_efetiva_disponivel",
    "penetracao_fitness_mercado_estimada",
    "share_ultra_estimado_hex",
    "score_oportunidade_residual",
]
BOOL_COLUMNS = [
    "flag_viavel",
    "flag_prioridade",
    "top_municipio",
    "top_hex_intraurbano",
    "flag_censo_elegivel",
    "flag_censo_disponivel",
    "flag_hex_hibrido_elegivel",
    "top_municipio_hibrido",
    "municipio_censo_disponivel",
    "flag_join_uf_restrito",
    "flag_baixa_pop_setor",
    "flag_outlier_espacial",
    "flag_monitoramento_prioritario",
    "top_oportunidade_municipio",
    "top_oportunidade_brasil",
    "top_oportunidade_uf",
    "flag_pop_min_5k",
    "flag_sam_fitness",
]
TEXT_COLUMNS = [
    "uf",
    "cidade",
    "regiao",
    "nome_municipio",
    "confianca_geografica",
    "qualidade_join_uf",
    "motivo_nao_elegivel_censo",
    "status_espacial_uf",
    "fonte_camada_censitaria",
    "criterio_score_expansao_hibrido",
    "camada_modelo_hibrido",
    "causa_outlier_espacial",
    "metodo_join_setor_2022",
    "motivo_fallback_setor_2022",
    "fonte_populacao_corte",
    "fonte_pop_hex_base",
    "quartil_oportunidade_residual",
    "prioridade_mercado_mapeado",
    "tese_entrada",
]
MAP_SORT_COLUMNS = ["flag_prioridade", "flag_viavel", "score_priorizacao", "rank_brasil"]
MAP_SORT_ASCENDING = [False, False, False, True]

# Colunas que cada modo de mapa consome (fonte unica de "colunas necessarias" do
# mapa). Os builders projetam o slice por essas listas antes de materializar o
# frame do mapa, evitando carregar colunas desnecessarias na fonte do mapa.
MAP_SOURCE_COLUMNS_M1 = [
    "hex_id",
    "lat",
    "lng",
    "cidade",
    "nome_municipio",
    "uf",
    "faixa_oportunidade",
    "score_priorizacao",
    "hex_score_estrutural",
    "flag_viavel",
    "flag_prioridade",
    "score_setor_2022_calibrado",
    "coverage_pct_setor_2022",
    "qualidade_join_uf",
    "flag_censo_disponivel",
    "confianca_geografica",
    "pop_total",
    "populacao_proxy",
    "renda_per_capita",
    "pop_total_setor_2022",
    "renda_per_capita_setor_2022_calibrada",
    "cod_municipio",
    "flag_pop_min_5k",
    "sam_fitness_potencial",
    "oferta_consumida_mercado_estimada",
    "oferta_consumida_ultra_real",
    "oferta_efetiva_disponivel",
    "share_ultra_estimado_hex",
    "score_oportunidade_residual",
    "quartil_oportunidade_residual",
    "fonte_pop_hex_base",
]
MAP_SOURCE_COLUMNS_HYBRID = [
    "hex_id",
    "lat",
    "lng",
    "uf",
    "nome_municipio",
    "faixa_oportunidade",
    "score_setor_2022_calibrado",
    "score_priorizacao",
    "score_expansao_hibrido",
    "densidade_pop_setor_hab_km2",
    "qualidade_join_uf",
    "flag_join_uf_restrito",
    "flag_baixa_pop_setor",
    "flag_outlier_espacial",
    "causa_outlier_espacial",
    "coverage_pct_setor_2022",
    "motivo_nao_elegivel_censo",
    "elegibilidade_hibrida",
    "rank_hex_intraurbano",
    "top_hex_intraurbano",
    "top_oportunidade_municipio",
    "pop_total",
    "populacao_proxy",
    "renda_per_capita",
    "pop_total_setor_2022",
    "renda_per_capita_setor_2022_calibrada",
    "cod_municipio",
    "flag_pop_min_5k",
    "sam_fitness_potencial",
    "oferta_consumida_mercado_estimada",
    "oferta_consumida_ultra_real",
    "oferta_efetiva_disponivel",
    "share_ultra_estimado_hex",
    "score_oportunidade_residual",
    "quartil_oportunidade_residual",
    "fonte_pop_hex_base",
]
COLORS = {
    "bg": "#0A0C18",
    "bg_alt": "#12162A",
    "panel": "rgba(17, 24, 39, 0.88)",
    "panel_solid": "#12172A",
    "panel_soft": "#18203A",
    "border": "rgba(120, 137, 210, 0.24)",
    "text": "#F3F7FF",
    "muted": "#A7B3D1",
    "brand": "#3E2A78",
    "brand_alt": "#19B7FF",
    "accent": "#FF4D8D",
    "accent_alt": "#7C5CFF",
    "good": "#22C55E",
    "bad": "#FF5A6B",
    "warning": "#F59E0B",
    "map_line": "#C8D3EA",
}
FAIXA_COLORS = {
    "prioridade_maxima": "#14C850",
    "alta": "#F59E0B",
    "media": "#DC3232",
    "baixa": "#B41E1E",
    "descartado": "#78788C",
    "inviavel": "#2E3040",
}
# Mapa de cores keyed pelo LABEL de exibicao acentuado (derivado de FAIXA_COLORS + FAIXA_LABELS).
# Uso: graficos que exibem a faixa acentuada no eixo/legenda (build_faixa_comparison_figure)
# preservam a MESMA cor por faixa sem tocar o valor bruto. Se FAIXA_COLORS mudar, este acompanha.
FAIXA_COLORS_POR_LABEL = {FAIXA_LABELS.get(k, k): v for k, v in FAIXA_COLORS.items()}
CENSO_SCORE_COLORS = {
    "0-25": [180, 30, 30, 140],
    "25-50": [220, 50, 50, 140],
    "50-75": [245, 158, 11, 140],
    "75-100": [20, 200, 80, 140],
}

# ---------------------------------------------------------------------------
# Faixas NOMEADAS das camadas do mapa do piloto (BLK-MAPA-FAIXAS-01)
# ---------------------------------------------------------------------------
# FONTE DA VERDADE destas faixas. `web/src/lib/faixas.ts` e' um ESPELHO (mesmo
# padrao de `SCORE_BANDS_HEX` x `RESIDUAL_SCORE_BANDS`), e um teste de contrato
# quebra se os dois divergirem.
#
# Existem porque a legenda do mapa e a etiqueta de cada item do ranking usavam
# REGUAS DIFERENTES para a mesma coisa. Medido em 2026-08-03 na demo de Campinas:
# um hex com 2.400 alunos residuais recebia a etiqueta "Baixa" (o corte era 3.000
# alunos) enquanto a legenda o classificava como "Livre" (2.400 = 96% da
# capacidade de uma unidade). O mesmo hexagono era descrito como quase vazio e
# quase cheio na mesma tela. Com uma definicao unica isso nao volta a acontecer.
#
# Tupla: (score_de, score_ate, nome exibido, cor solida, tom do chip no ranking).
# `score_ate` e' EXCLUSIVO; a ultima faixa fecha em 100 inclusive.
# READ-ONLY sobre o M1: sao rotulos de exibicao sobre a rampa de cor existente.

# Camada 1 do funil — potencial socioeconomico (`score_setor_2022_calibrado`).
# VEREDITO sobre a regiao: quem le o mapa decide abertura, e "Promissor" resolve
# na hora o que "62 pontos" nao resolve.
FAIXAS_MAPA_POTENCIAL: list[tuple[int, int, str, str, str]] = [
    (0, 20, "Desfavorável", "#B92323", "red"),
    (20, 40, "Fraco", "#DC6914", "amber"),
    (40, 60, "Promissor", "#EEC828", "gray"),
    (60, 80, "Forte", "#50C33C", "green"),
    (80, 100, "Excelente", "#0A8226", "blue"),
]

# Camadas 2 e 3 — demanda nao atendida (`score_oportunidade_residual`).
# Vocabulario de SATURACAO, em registro formal. O score aqui NAO e' abstrato:
# `calcular_colunas_mercado` define score = 100 * oferta_efetiva_disponivel / 2.500,
# e 2.500 alunos e' a capacidade de UMA unidade -> 100 = livre, 0 = saturado.
FAIXAS_MAPA_DEMANDA: list[tuple[int, int, str, str, str]] = [
    (0, 20, "Saturado", "#B92323", "red"),
    (20, 40, "Restrito", "#DC6914", "amber"),
    (40, 60, "Moderado", "#EEC828", "gray"),
    (60, 80, "Amplo", "#50C33C", "green"),
    (80, 100, "Livre", "#0A8226", "blue"),
]

# Ancora da camada de demanda: score 100 <=> uma unidade cheia.
# Espelha SCORE_RESIDUAL_CAPACIDADE_REFERENCIA de `pipelines/calcular_colunas_mercado`.
CAPACIDADE_UNIDADE_ALUNOS = _REGUAS.capacidade_unidade_alunos


def faixa_do_score(
    score: float | None, faixas: list[tuple[int, int, str, str, str]]
) -> tuple[str, str]:
    """(nome, tom) da faixa em que `score` cai. `None`/NaN -> ultima faixa nao se
    aplica: devolve ("", "") e o chamador decide o fallback."""
    if score is None or score != score:  # NaN
        return "", ""
    valor = max(0.0, min(100.0, float(score)))
    for de, ate, nome, _cor, tom in faixas:
        if de <= valor < ate:
            return nome, tom
    _de, _ate, nome, _cor, tom = faixas[-1]
    return nome, tom
RESIDUAL_SCORE_BANDS: list[tuple[str, str]] = [
    ("0-10",   "#941212"),
    ("10-20",  "#B92323"),
    ("20-30",  "#DC4141"),
    ("30-40",  "#DC6914"),
    ("40-50",  "#F0941E"),
    ("50-60",  "#EEC828"),
    ("60-70",  "#96D250"),
    ("70-80",  "#50C33C"),
    ("80-90",  "#19A832"),
    ("90-100", "#0A8226"),
]

# Faixas absolutas de DENSIDADE populacional (hab/km2) — estilo GeoFusion (rampa de vermelhos),
# alpha 150 (transparente) p/ as ruas do basemap claro aparecerem por baixo. Cortes (limites
# superiores, hab/km2): 1000 / 5000 / 10000 / 25000 / inf. Paleta = ColorBrewer Reds-5.
# Camada de VISUALIZACAO do Relatorio Pontual Censitario — NAO altera score/artefatos M1.
_DENSIDADE_POP_BANDS_BR: list[tuple[float, str, tuple[int, int, int, int]]] = [
    (1_000.0,   "ate 1.000",         (254, 229, 217, 150)),
    (5_000.0,   "1.001-5.000",       (252, 174, 145, 150)),
    (10_000.0,  "5.001-10.000",      (251, 106, 74,  150)),
    (25_000.0,  "10.001-25.000",     (222, 45,  38,  150)),
    (float("inf"), ">25.000",        (165, 15,  21,  150)),
]

# Faixas absolutas de RENDA PER CAPITA (R$/pessoa/mes) — estilo GeoFusion adaptado a PER CAPITA
# (NAO domiciliar). Cortes recalibrados p/ a escala per capita do projeto: 1000 / 2000 / 3500 /
# 5000 / inf (R$/pessoa). per capita != domiciliar: a classe media urbana-alvo Ultra (18-45) tende
# a R$2.000-5.000/pessoa; >R$5.000/pessoa marca bolsoes de alta renda. Os 4 cortes per capita NAO
# equivalem ao teto domiciliar RENDA_MIN=4500 (escalas distintas; nao confundir).
# Rampa (escolha de Vini 2026-06-17, BLK-UI-08): amarelo-claro (renda baixa) -> amarelo -> dourado
# -> verde-claro -> verde solido (renda alta). Cores absolutas pedidas: #F7F48B / #FFFF00 /
# #FFD21C / #A8FFA8 / #00CC00. alpha 150 = cor da LEGENDA; o FILL no mapa usa _CHOROPLETH_ALPHA.
# Camada de VISUALIZACAO do Relatorio Pontual Censitario — NAO altera score/artefatos M1.
_RENDA_PER_CAPITA_BANDS_BR: list[tuple[float, str, tuple[int, int, int, int]]] = [
    (1_000.0,   "ate R$ 1.000",        (247, 244, 139, 150)),   # #F7F48B
    (2_000.0,   "R$ 1.001-2.000",      (255, 255, 0,   150)),   # #FFFF00
    (3_500.0,   "R$ 2.001-3.500",      (255, 210, 28,  150)),   # #FFD21C
    (5_000.0,   "R$ 3.501-5.000",      (168, 255, 168, 150)),   # #A8FFA8
    (float("inf"), ">R$ 5.000",        (0,   204, 0,   150)),   # #00CC00
]

# As rampas de COR das faixas declaradas no perfil. A regua (cortes e rotulos) e' dado de
# PAIS; a paleta e' identidade da plataforma e nao viaja no perfil — pais cujo choropleth
# nao e' legivel na regua brasileira declara os proprios cortes, e a cor vem daqui.
#
# Cada rampa e' a rampa BRASILEIRA de 5 degraus MAIS um degrau escuro de topo, nesta
# ordem. Isso e' o que torna a regra de atribuicao de `_bands_de_faixas` (prefixo) capaz
# de reproduzir o literal BR byte a byte quando o pais declara 5 faixas.
_RAMPA_RENDA: list[tuple[int, int, int, int]] = [
    (247, 244, 139, 150),   # #F7F48B
    (255, 255, 0,   150),   # #FFFF00
    (255, 210, 28,  150),   # #FFD21C
    (168, 255, 168, 150),   # #A8FFA8
    (0,   204, 0,   150),   # #00CC00
    (20,  170, 80,  150),   # verde-escuro de OFERTA_*_BANDS
]

# Reds do ColorBrewer, como o literal BR, mais o Reds-9 mais escuro (#67000D) no topo.
_RAMPA_DENSIDADE: list[tuple[int, int, int, int]] = [
    (254, 229, 217, 150),
    (252, 174, 145, 150),
    (251, 106, 74,  150),
    (222, 45,  38,  150),
    (165, 15,  21,  150),
    (103, 0,   13,  150),   # #67000D, o Reds mais escuro
]


def _bands_de_faixas(
    faixas,  # tuple[perfil.Faixa, ...]
    rampa: list[tuple[int, int, int, int]] | None = None,
) -> list[tuple[float, str, tuple[int, int, int, int]]]:
    """Faixas do perfil -> formato de bands dos mapas de calor (teto, rotulo, RGBA).

    Atribuicao de cor: as N faixas tomam as N PRIMEIRAS cores da rampa, em ordem. Com 6
    faixas a rampa sai inteira; com 5, identica a brasileira — e e' esse o ponto, porque
    a rampa E' o literal BR mais um degrau de topo.

    ARMADILHA (corrigida em 2026-09-10): a regra anterior era "as N-1 primeiras cores
    mais a ULTIMA", e com N=5 ela PULAVA o 5o degrau — o topo brasileiro (#00CC00) saia
    trocado pelo verde-escuro que so' deveria aparecer com 6 faixas. Um pais que
    declarasse 5 faixas de renda nao reproduziria a rampa BR, contra o que o proprio
    comentario prometia. Medido no artefato de Sao Paulo capital: a faixa de topo pega
    4.659 dos 26.672 setores (17,47%), entao a cor errada nao seria um detalhe de borda.
    Travado por `tests/unit/test_paridade_paleta_web.py`.
    """
    cores = (rampa if rampa is not None else _RAMPA_RENDA)[: len(faixas)]
    return [(f.ate, f.rotulo, cor) for f, cor in zip(faixas, cores, strict=True)]


# Pais com `reguas.faixas_renda` declarado (a Argentina, ancorada na canasta do INDEC)
# usa as faixas do perfil; sem o campo (o Brasil), os literais de sempre, byte a byte —
# travado por tests/contracts/test_perfil_br_reproduz_as_constantes.py.
RENDA_PER_CAPITA_BANDS: list[tuple[float, str, tuple[int, int, int, int]]] = (
    _bands_de_faixas(_REGUAS.faixas_renda.per_capita)
    if _REGUAS.faixas_renda is not None
    else _RENDA_PER_CAPITA_BANDS_BR
)

# Mesma regra da renda, para o choropleth de DENSIDADE (`reguas.faixas_densidade`).
DENSIDADE_POP_BANDS: list[tuple[float, str, tuple[int, int, int, int]]] = (
    _bands_de_faixas(_REGUAS.faixas_densidade, _RAMPA_DENSIDADE)
    if _REGUAS.faixas_densidade is not None
    else _DENSIDADE_POP_BANDS_BR
)

# ── Renda media domiciliar (fase seguinte, portada do prototipo) ──────────────
# renda_media_domiciliar = renda do responsavel (V06004) x uplift de composicao x fator temporal,
# agregada ponderando por DOMICILIOS. Camada de VISUALIZACAO do Relatorio Pontual; NAO altera M1.
#
# uplift de composicao: responsavel -> domicilio inteiro. Mediana nacional 1.632 (~61% da renda vem
# do responsavel). Por MUNICIPIO (IBGE) e, quando disponivel, por SETOR (agregado de parentesco,
# rakeado por municipio: a media ponderada dos setores reproduz o uplift municipal do IBGE).
# FALLBACK do pais da instancia (Bloco B / DEC-047). No Brasil e o 1,632 de sempre, e as
# tabelas por municipio e por setor continuam tendo precedencia sobre ele. Num pais SEM
# essas tabelas — a Argentina — este e o UNICO valor que responde, e e por isso que ele
# precisa vir do perfil: la o exportador ja entrega a renda na escala domiciliar, entao o
# multiplicador correto e 1,0. Sem isto a renda argentina sai 63% acima da real.
UPLIFT_COMPOSICAO_NACIONAL = _REGUAS.uplift_composicao
# Media nacional de moradores por domicilio (IBGE Censo 2022 ~2.79) — fallback quando o municipio
# nao esta na tabela. Usado pela renda media domiciliar por hex (tooltip do Mapa Territorial).
MORADORES_DOMICILIO_NACIONAL = _REGUAS.moradores_por_domicilio
# Os demais insumos da renda exibida (uplift por municipio/setor, moradores por domicilio,
# fator temporal) e as formulas que os aplicam moram em `motor_expansao.renda` desde a E0 do
# plano de correcao da renda: um ponto unico, travado por tests/contracts/test_renda_ponto_unico.py.
# Os dois nacionais acima continuam aqui porque sao reguas do perfil que outros leitores citam.


# Faixas absolutas de RENDA MEDIA DOMICILIAR (R$/domicilio/mes), com uplift + fator temporal.
# MESMA paleta da RENDA_PER_CAPITA_BANDS (amarelo-claro -> amarelo -> dourado -> verde-claro ->
# verde solido) e MESMO formato de rotulo SEM acento — o font do PNG da legenda nao renderiza 'á'
# ("até" saia bugado; per capita ja usa "ate"). Faixas pedidas por Felipe (2026-07-17): 2.000 /
# 4.000 / 8.000 / 14.000 (corte de 4.600 -> 4.000 a pedido de Felipe 2026-07-23). Camada de
# VISUALIZACAO do Relatorio Pontual; NAO altera score/artefatos M1.
_RENDA_MEDIA_DOMICILIAR_BANDS_BR: list[tuple[float, str, tuple[int, int, int, int]]] = [
    (2_000.0,   "ate R$ 2.000",        (247, 244, 139, 150)),   # #F7F48B
    (4_000.0,   "R$ 2.001-4.000",      (255, 255, 0,   150)),   # #FFFF00
    (8_000.0,   "R$ 4.001-8.000",      (255, 210, 28,  150)),   # #FFD21C
    (14_000.0,  "R$ 8.001-14.000",     (168, 255, 168, 150)),   # #A8FFA8
    (float("inf"), ">R$ 14.000",       (0,   204, 0,   150)),   # #00CC00
]

# Mesma regra da per capita: faixas declaradas no perfil vencem; sem elas, o literal BR.
RENDA_MEDIA_DOMICILIAR_BANDS: list[tuple[float, str, tuple[int, int, int, int]]] = (
    _bands_de_faixas(_REGUAS.faixas_renda.domiciliar)
    if _REGUAS.faixas_renda is not None
    else _RENDA_MEDIA_DOMICILIAR_BANDS_BR
)

# Faixas absolutas de RESIDUAL FITNESS DISPONIVEL (`oferta_efetiva_disponivel`), em ALUNOS —
# NAO confundir com `RESIDUAL_SCORE_BANDS`, que e' score 0-100. Ancora: 2.500 alunos = capacidade
# default de 1 unidade (CLAUDE.md §4) -> a legenda le direto como "~N unidades". Regua ABSOLUTA
# (nao quantilica): 68,9% dos 1.542.531 hexes valem exatamente 0 e, entre os positivos, a mediana
# e' 1 e o p99 e' 1.774 -> quantis nacionais colocariam "verde alto" em hexes onde nao cabe 1/30
# de academia (mesmo motivo pelo qual o BLK-CENSO-03 trocou quartil por faixa absoluta).
# Cortes 0 / 1.250 / 2.500 / 5.000 / 10.000 / inf aprovados por Vinicius no gate do BLK-RELPON-10
# (S2 = Alternativa B, 6 faixas; a de 5 faixas saturava Manaus, cujo p75 7.588 e max 13.472 caiam
# na MESMA faixa de topo). Rampa cinza -> amarelo -> ambar -> verde: cinza = `_COR_REPROVADO` e
# verde forte = `_COR_APROVADO_PROPRIO` do Relatorio Municipal (DEC-011/BLK-RELMUN-05).
# Rotulos em ASCII PURO: a legenda e' rasterizada num PNG cujo font (ImageFont.load_default) NAO
# tem glifo acentuado (excecao de RENDER ao §2, como em RENDA_MEDIA_DOMICILIAR_BANDS).
# alpha 150 = cor da LEGENDA; o FILL no mapa usa `_CHOROPLETH_ALPHA`.
# Camada de VISUALIZACAO do Relatorio Pontual Censitario — NAO altera score/artefatos M1.
OFERTA_DISPONIVEL_ALUNOS_BANDS: list[tuple[float, str, tuple[int, int, int, int]]] = [
    (0.0,        "sem residual",   (150, 156, 170, 150)),   # rede saturada
    (1_250.0,    "1-1.250",        (247, 244, 139, 150)),   # < 1/2 unidade
    (2_500.0,    "1.251-2.500",    (255, 255, 0,   150)),   # ~1 unidade
    (5_000.0,    "2.501-5.000",    (255, 210, 28,  150)),   # ~2 unidades
    (10_000.0,   "5.001-10.000",   (168, 255, 168, 150)),   # ~4 unidades
    (float("inf"), "> 10.000",     (20,  170, 80,  150)),   # 4+ unidades
]

# Expansao de Dominio — constantes canonicas
DOMINIO_SCHEMA_MINIMO: frozenset[str] = frozenset({
    "hex_id", "uf", "cod_municipio", "nome_municipio", "lat", "lng",
    "cluster_id", "tese_dominio",
    "ordem_expansao_cidade", "residual_incremental_capturado",
    "residual_cluster_pos_acao", "dist_nova_ancora_mais_proxima_m",
    "rank_dominio_brasil", "rank_dominio_uf", "rank_dominio_cidade",
    "score_dominio_hibrido", "motivo_dominio",
})
DOMINIO_TESES_VALIDAS: frozenset[str] = frozenset({
    "dominar_white_space", "abrir_com_disputa", "proteger_corredor_ultra",
    "adensar_cluster", "monitorar", "bloqueado_canibalizacao",
})

# ── Mapa Territorial Unificado — camadas ──────────────────────────────────────

COLOR_MODES: dict[str, dict] = {
    "m1": {
        "label": "M1",
        "parquet": "hexagonos_brasil_dashboard.parquet",
        "required_cols": ["faixa_oportunidade", "score_priorizacao"],
        "optional_cols": [],
    },
    "hibrido": {
        "label": "Híbrido",
        "parquet": "oportunidades_expansao_hibrido.parquet",
        "required_cols": ["score_expansao_hibrido"],
        "optional_cols": ["score_setor_2022_calibrado"],
    },
    "censitario": {
        "label": "Censitário",
        "parquet": "oportunidades_expansao_hibrido.parquet",
        "required_cols": ["score_setor_2022_calibrado"],
        "optional_cols": [],
    },
    "residual": {
        "label": "Residual Fitness",
        "parquet": "oportunidades_expansao_hibrido.parquet",
        "required_cols": ["score_oportunidade_residual"],
        "optional_cols": ["oferta_efetiva_disponivel"],
    },
    "dominio": {
        "label": "Expansão de Domínio",
        "parquet": "plano_expansao_dominio.parquet",
        "required_cols": ["ordem_expansao_cidade", "tese_dominio"],
        "optional_cols": ["residual_incremental_capturado"],
    },
}
COLOR_MODE_DEFAULT = "m1"
COLOR_MODE_IDS: list[str] = list(COLOR_MODES)

OVERLAYS: dict[str, dict] = {
    "concorrentes": {
        "label": "Concorrentes",
        "default": True,
        "required_cols": ["lat", "lng", "rede"],
        "absent_behavior": "hide_silently",
    },
    "ultra": {
        "label": "Ultra",
        "default": True,
        "required_cols": ["lat", "lng"],
        "absent_behavior": "hide_silently",
    },
    "ancoras_dominio": {
        "label": "Âncoras Domínio",
        "default": False,
        "required_cols": ["lat", "lng", "hex_id"],
        "absent_behavior": "hide_silently",
    },
    "hex_pesquisado": {
        "label": "Hex pesquisado",
        "default": True,
        "required_cols": [],
        "absent_behavior": "hide_when_no_search",
    },
    "descartados_5k": {
        "label": "Descartados <5k hab",
        "default": True,
        "required_cols": ["flag_pop_min_5k"],
        "absent_behavior": "show_neutral",
    },
}
OVERLAY_IDS: list[str] = list(OVERLAYS)


def color_mode_available(df, mode_id: str) -> bool:
    """Retorna True se todas as colunas obrigatorias do modo existirem no DataFrame."""
    cfg = COLOR_MODES.get(mode_id)
    if cfg is None:
        return False
    return all(c in df.columns for c in cfg["required_cols"])


def overlay_available(df, overlay_id: str) -> bool:
    """Retorna True se todas as colunas obrigatorias do overlay existirem no DataFrame."""
    cfg = OVERLAYS.get(overlay_id)
    if cfg is None:
        return False
    return all(c in df.columns for c in cfg["required_cols"])
