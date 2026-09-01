"""Indice conjuntivo da praca: boa no socioeconomico E com demanda nao atendida.

POR QUE ESTE MODULO EXISTE
--------------------------
Ate' 2026-08-28 a camada 5 do funil ordenava a fila por `oferta_efetiva_disponivel`
(residual em alunos) e mais nada. Como o residual e' populacao quase pura
(Spearman 0,995 contra `pop_hex_base`), ordenar por ele e' ordenar por quantidade de
gente -- e dentro de uma cidade a maior quantidade de gente esta' na periferia densa.
Medido nas 8 maiores capitais, `rho(residual, renda)` e' NEGATIVO em todas
(-0,06 em Sao Paulo a -0,58 em Campo Grande), e a fila de 10 caia no percentil 20-49
de renda DO PROPRIO CONJUNTO que ja' tinha passado no gate.

O dono descreveu a dor assim: "queremos estar em regioes com um potencial
socioeconomico bom e ao mesmo tempo em regioes com demanda nao atendida". O "ao mesmo
tempo" e' a palavra operativa: a ordenacao precisa premiar quem e' bom nos DOIS eixos.

O QUE ESTE MODULO NAO E'
------------------------
NAO e' previsao de faturamento. O experimento E3 mediu 4 preditores territoriais contra
desempenho real de 267 unidades de 3 redes: todos os intervalos de confianca cruzam
zero. Territorio RANQUEIA praca, nao PREVE desempenho de unidade. Logo o indice aqui e'
POLITICA DE EXPANSAO DECLARADA -- uma regra de priorizacao que a empresa escolheu -- e a
tela precisa dize-lo com essas palavras, nunca vesti-lo de previsao.

READ-ONLY sobre o M1: nada aqui recalcula `score_priorizacao`, pesos ou artefato oficial.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# --- Regua absoluta da demanda ------------------------------------------------
# Mesma filosofia da DEC-040 (que tirou o score censitario do percentil): ancoras fixas
# e com significado de negocio, para que o numero signifique a mesma coisa em Sao Paulo
# e em Campo Grande.
#
#   2.000 alunos -> 0    e' o piso do gate (`OFERTA_DESTAQUE_MIN`), ~1 unidade de espaco
#                        na capacidade real medida (~2.300 alunos/unidade, E2).
#  20.000 alunos -> 100  e' ~8 unidades de espaco; acima disso a diferenca deixa de ser
#                        decisoria, porque so' se abre uma unidade por vez.
#
# LOG e nao linear pelo mesmo motivo que a populacao e' log na DEC-040: a diferenca entre
# 2 mil e 6 mil alunos de residual muda a decisao; entre 16 mil e 20 mil, nao muda.
DEMANDA_MIN_ALUNOS = 2_000.0
DEMANDA_MAX_ALUNOS = 20_000.0

# --- Peso dos dois eixos ------------------------------------------------------
# Escolhido por Felipe em 2026-08-28 sobre a medicao das 8 capitais.
#
# RESSALVA HONESTA, que o painel de metodologia publica: os dois eixos NAO tem a mesma
# dispersao. Dentro do gate, o eixo socioeconomico tem desvio-padrao 15,1 e o de demanda,
# 25,2 -- a demanda e' ~1,7x mais espalhada. Peso NOMINAL 70/30 produz, por isso, uma
# influencia REAL proxima do equilibrio entre os dois. Nao existe escolha de ancora que
# iguale as dispersoes sem esmagar o eixo de demanda (medido: mesmo 2.000->30.000 ainda
# da' dp 21,5), entao a assimetria e' declarada em vez de escondida.
PESO_SOCIO = 0.70
PESO_DEMANDA = 0.30

# --- Sobre a pressao competitiva ----------------------------------------------
# A camada 3 do funil DEIXOU de eliminar hexagono por simplesmente ter concorrente
# (2026-08-28). Duas razoes, ambas medidas:
#
# (1) Estava cortando as MELHORES pracas. Nas 8 capitais, sem excecao, o score
#     socioeconomico mediano dos hexagonos ELIMINADOS era MAIOR que o dos mantidos
#     (Sao Paulo 56,8 contra 55,0; Rio 54,9 contra 44,2; Campo Grande 51,1 contra 34,9).
#     Concorrente e' sinal de que o mercado existe -- e o filtro lia como desqualificacao.
#
# (2) Estava penalizando concorrencia DUAS VEZES. A camada 2 ja' subtrai a oferta
#     instalada (`residual = SAM - oferta consumida`); a camada 3 entao eliminava de novo
#     o mesmo hexagono, agora de forma categorica.
#
# O corte passou a ser so' de SATURACAO EXTREMA: sai quem tem mais de `CONC_ADENSAR_MAX`
# concorrentes -- exatamente o que a tela ja' chama de "Disputa".
#
# DE PROPOSITO NAO HA' VOCABULARIO DE PRESSAO AQUI. Ele ja' existe, publicado e testado,
# em `app._etiqueta` (ramo "conc. 2 km"): Livre / Adensar / Disputa, derivado de
# `n_concorrentes_est`. Criar aqui uma segunda nocao de pressao (saturacao continua, por
# exemplo) colocaria duas reguas diferentes na mesma tela -- o defeito que a DEC-040
# acabou de corrigir no score. Uma regua so'.

# --- Quadrantes ---------------------------------------------------------------
# Corte em 50 nos DOIS eixos, ambos absolutos. Em nota de demanda, 50 equivale a ~6.300
# alunos de residual; em nota socioeconomica, ao score 50 da DEC-040. Medido no gate das
# 8 capitais, parte o conjunto em quatro grupos quase iguais (24,8% / 23,5% / 24,6% /
# 27,1%) -- e' uma particao informativa, nao um rotulo que cai todo de um lado.
QUADRANTE_CORTE = 50.0

QUADRANTE_LABELS = {
    "prioridade": "Prioridade",
    "praca_forte": "Praça forte, espaço apertado",
    "volume": "Volume, praça mediana",
    "marginal": "Marginal",
}

QUADRANTE_EXPLICACAO = {
    "prioridade": "Bom nos dois eixos: gente com renda para treinar e demanda ainda não atendida.",
    "praca_forte": "Praça socioeconomicamente forte, mas com pouco espaço sobrando — entrada disputada.",
    "volume": "Muita demanda não atendida, em praça de perfil socioeconômico mediano.",
    "marginal": "Passa no mínimo dos dois eixos, sem se destacar em nenhum.",
}


def _serie(valores) -> pd.Series:
    return pd.to_numeric(pd.Series(valores).reset_index(drop=True), errors="coerce")


def nota_demanda(residual_alunos) -> pd.Series:
    """Residual em alunos -> nota absoluta 0-100, em escala log.

    Abaixo de `DEMANDA_MIN_ALUNOS` a nota e' 0 (e o hexagono nem chega aqui: o gate da
    camada 2 ja' o barrou); acima de `DEMANDA_MAX_ALUNOS` satura em 100.
    """
    x = _serie(residual_alunos).clip(lower=DEMANDA_MIN_ALUNOS, upper=DEMANDA_MAX_ALUNOS)
    bruto = 100.0 * np.log10(x / DEMANDA_MIN_ALUNOS) / np.log10(DEMANDA_MAX_ALUNOS / DEMANDA_MIN_ALUNOS)
    return pd.Series(bruto, index=x.index).where(_serie(residual_alunos).notna())


def indice_praca(nota_socio, nota_dem) -> pd.Series:
    """Media ponderada das duas notas absolutas. 0-100.

    Soma ponderada e NAO produto: o produto zeraria a praca excelente e ja' disputada,
    que o dono pediu explicitamente para MANTER na lista ("nao quero que exclua da
    recomendacao areas muito boas mesmo que ja' estejam saturadas em tese"). A conjuncao
    ("bom nos dois") e' garantida pelo GATE, que ja' exige minimo nos dois eixos --
    score >= SCORE_CORTE_QUENTE e residual >= OFERTA_DESTAQUE_MIN --, e nao pela forma
    algebrica da combinacao.
    """
    ns = _serie(nota_socio)
    nd = _serie(nota_dem)
    return (PESO_SOCIO * ns + PESO_DEMANDA * nd).clip(lower=0.0, upper=100.0)


def rotulo_quadrante(nota_socio, nota_dem) -> pd.Series:
    """Par de notas -> quadrante BRUTO (`prioridade`/`praca_forte`/`volume`/`marginal`)."""
    ns = _serie(nota_socio)
    nd = _serie(nota_dem)
    forte_socio = ns >= QUADRANTE_CORTE
    forte_dem = nd >= QUADRANTE_CORTE
    out = pd.Series("marginal", index=ns.index, dtype="object")
    out[forte_socio & ~forte_dem] = "praca_forte"
    out[~forte_socio & forte_dem] = "volume"
    out[forte_socio & forte_dem] = "prioridade"
    return out.where(ns.notna() & nd.notna())
