"""Pressao concorrencial por raio de 1 km com reparticao por AREA (camada paralela).

CONTEXTO — o que existe hoje (`enriquecimento_espacial_hexagonos.py`)
--------------------------------------------------------------------
O motor atual mede a oferta a partir do CENTROIDE do hexagono: para cada hex, soma
todo concorrente ate 2 km com peso linear `max(0, 1 - d/2000)`:

    oferta_efetiva_mapeada_2km[hex] = SOMA_concorrentes max(0, 1 - d_centroide/2000)

Duas consequencias incomodas (numeros MEDIDOS sobre pontos sorteados dentro de um hex
res-7 em Sao Paulo; `tests/unit/test_pressao_concorrencial_1km.py` trava as faixas com
60 amostras):

1. **Nao conserva massa, e o vazamento e' irregular.** Em SAO PAULO, a soma dos pesos
   que um unico concorrente injeta varia entre **0,73 e 0,98** (media 0,80) conforme onde
   ele cai dentro do hexagono: o modelo atual subestima o consumo em ~20% na media, e de
   forma DESIGUAL entre hexes.
   O RECORTE IMPORTA e a direcao NAO e' universal: em Porto Alegre a mesma medicao da
   media 0,95, com 14 de 60 posicoes ACIMA de 1,00 (max 1,04) — la o modelo antigo
   SOBRE-injeta. Em Belem a media cai para 0,68. O que vale em geral e' a irregularidade,
   nao o sinal do desvio.
2. **Ignora a geometria do hexagono.** So a distancia ao centroide conta. Um concorrente
   colado na fronteira entre dois hexes e' tratado como se pertencesse quase todo ao hex
   cujo centroide esta mais perto, mesmo atendendo os dois igualmente.

Observacao contra-intuitiva, mas medida: o raio de 2 km NAO espalha para mais hexes que
o de 1 km. Na malha NACIONAL a distancia entre centroides vizinhos vai de 1.999 a 2.682 m
(mediana 2.496) — a faixa 2.387-2.513 m citada antes era do hexagono de Sao Paulo apenas,
e 67% da malha cai fora dela. Como quase toda a malha fica acima de 2.000 m, um raio de
2 km partindo do centroide quase sempre nao alcanca vizinho (ha 10 hexes no pais com
vizinho a menos de 2.000 m). Medido em Sao Paulo: o modelo atual toca **2,4 hexes** na
media (1 a 3) e o novo toca **3,3** (1 a 4), porque area de intersecao enxerga vizinho
que distancia-ao-centroide nao enxerga.

O QUE ESTE MODULO FAZ
---------------------
Cada concorrente vira uma FONTE com disco de influencia de raio fixo (1 km). A
capacidade dele (2.500 alunos por unidade, o mesmo proxy do Bloco 5) e' repartida
entre os hexagonos que o disco cobre, na proporcao da AREA DE INTERSECAO:

    share(concorrente c -> hex h) = area(disco_c INTERSECAO hex_h) / area(disco_c)
    SOMA_h share(c -> h) = 1                      <- conservacao de massa, exata
    oferta_efetiva_1km_area[h] = SOMA_c share(c -> h)
    consumo_concorrentes_1km_area[h] = oferta_efetiva_1km_area[h] * capacidade

LIMITACAO CONHECIDA — MASSA RETIDA NA BORDA DA BASE (CORRIGIDO). `shares_por_hex`
conserva massa por construcao (soma 1,00 sobre TODAS as celulas H3 que o disco cobre),
mas antes desta correcao `anexar_pressao_1km_area` fazia `merge` contra o DataFrame de
hexes e o share que caia em celula FORA da base — litoral, fronteira, hexagono podado
pelo criterio de fracao de terra (`M1_HEX_LAND_FRACTION_MIN`) — era DESCARTADO em
silencio. Medido na base real, antes do fix: **119 dos 3.179 concorrentes validos
(3,7%) perdiam parte da conta**, mediana 15,8% e ate 100% nos casos em que o concorrente
estava inteiramente fora da malha; no total somiam **27,4 unidades = 68.431 alunos** de
consumo — vies sistematico de SUBESTIMAR a pressao (logo SUPERESTIMAR o residual) em
hexes de litoral/fronteira, justamente onde ficam varias metropoles-alvo da Ultra.

Corrigido por RENORMALIZACAO (decisao de Felipe): `repartir_concorrentes` agora aceita
`hex_ids_validos` e, quando informado, filtra o share de cada concorrente aos hexagonos
que existem na base e redistribui a fracao restante para fechar em 1,0 sobre esse
subconjunto — ANTES de agregar entre concorrentes. `anexar_pressao_1km_area` sempre
passa `set(df_hex["hex_id"])`, entao o `merge` que segue nunca mais descarta massa (os
shares ja chegam filtrados). Um concorrente cujo disco caia 100% fora da base continua
contribuindo zero — nao ha hexagono valido para receber a massa dele, e isso e'
diferente de "perda por acidente": e' o concorrente genuinamente nao pressionar
nenhum hexagono brasileiro coberto pelo motor.

Kernel UNIFORME por decisao de Felipe (2026-08-05): cada m2 do disco pesa igual, o
share e' area pura. Alternativas avaliadas e recusadas nesta rodada: decaimento linear
dentro do disco e raio variavel por porte de rede.

Escala para calibrar expectativa: hex H3 res-7 = **5,16 km2** de area media oficial
(a celula de Sao Paulo tem 5,21; Porto Alegre 4,41; Belem 6,08); disco de 1 km = 3,14 km2.
O disco cabe dentro de um hexagono, mas raramente esta centrado nele: na pratica se
reparte entre 1 e 4 hexes (media 3,3).

EFEITO ESPERADO NO RESIDUAL — cai em praticamente todo lugar, mas NAO e' um "nunca
sobe". Vale separar o que esta PROVADO do que apenas foi observado:

  PROVADO (teste `test_alcance_do_1km_area_contem_o_do_2km`, 120 posicoes sorteadas):
  o ALCANCE do modelo novo contem o do antigo — nenhum hex alcancado pelo raio de 2 km
  fica de fora do disco de 1 km. Logo nenhum hexagono passa de "com pressao" para "sem
  pressao". Motivo geometrico: os hexes tem ~2,4 km de ponta a ponta, entao um
  concorrente a 1-2 km do centroide quase sempre esta a menos de 1 km da BORDA.

  MEDIDO (dados reais, malha NACIONAL de 1.542.531 hexes): cada concorrente passa a
  valer 1,00 unidade em vez de ~0,80 em Sao Paulo, o consumo total sobe +27,9% e o
  residual cai na esmagadora maioria. Mas 81 hexes GANHAM residual — 68 no RS, 8 em SC,
  5 no PR — com ganho maximo de 168 alunos (Pelotas/RS). O criterio e' ganho MATERIAL,
  `delta_consumo < -1 aluno`; pelo criterio estrito (`delta_consumo < 0`) sao 84 hexes
  (71 RS, 8 SC, 5 PR), com 3 ganhando menos de 1 aluno. Conter o alcance nao impede o
  consumo de um hex especifico de diminuir. O fenomeno se concentra no SUL, onde a
  celula H3 e' menor: uma medicao restrita a SP/MG/RJ/PR/BA encontra so' 5 casos e da a
  impressao de que e' desprezivel.

Uma versao anterior deste docstring afirmava "so' para baixo, NUNCA para cima" e tratava
isso como travado em teste. Era um salto: do alcance conter (provado) para o consumo
nunca diminuir (nao decorre, e falso). Como este modulo alimenta a decisao de virar a
base do residual, a diferenca importa — hexes de fronteira podem entrar no funil, e
quem le precisa saber que isso e' possivel, ainda que raro.

O ganho da mudanca nao e' de nivel, e' de justica distributiva: o consumo pousa nos
hexes que o concorrente de fato cobre, em vez de vazar proporcional a distancia ate
centroides.

ESCOPO — colunas NOVAS, em paralelo (decisao de Felipe, 2026-08-05)
-------------------------------------------------------------------
Este modulo NAO altera `oferta_efetiva_mapeada_2km`, `gap_competitivo_2km`,
`pressao_concorrencial_score_2km` nem qualquer coluna consumida por
`som_indice_mapeado`, `tese_entrada`, `prioridade_mercado_mapeado`, carteira ou plano.
Ele so ACRESCENTA colunas `*_1km_area` para comparacao lado a lado. A virada do
residual para a base nova e' decisao seguinte, com o comparativo na mao, e exige DEC.

READ-ONLY sobre o M1: nao toca `score_priorizacao`, `hex_score_estrutural`, pesos nem
artefatos oficiais (CLAUDE.md 1/3/5).
"""

from __future__ import annotations

import math
from collections.abc import Iterable

import h3
import numpy as np
import pandas as pd
from shapely.geometry import Point, Polygon

from motor_expansao.pipelines.calcular_colunas_mercado import (
    CAPACIDADE_DEFAULT_CONCORRENTE_ALUNOS,
)

# Raio de influencia de cada concorrente. Fixo e igual para todas as redes nesta versao.
RAIO_INFLUENCIA_M = 1_000.0
H3_RESOLUTION = 7

# Anel de hexes candidatos ao redor da celula do concorrente. Com res-7 (aresta ~1,22 km)
# e raio de 1 km, o disco nunca escapa do anel 1; o anel 2 (19 celulas) e' folga barata
# contra o caso de canto e contra qualquer futuro aumento do raio ate ~2 km.
GRID_DISK_K = 2

# Segmentos por quadrante do buffer que aproxima o disco. 128 -> poligono de 512 lados,
# area 2,5e-5 menor que o circulo exato (medido). Como o share e' uma RAZAO area/area,
# esse vies se cancela quase inteiro; `test_disco_aproxima_circulo` trava o limite.
QUAD_SEGS = 128

# Tolerancia da conservacao de massa (soma dos shares == 1). Folga para o poligono do
# buffer e para a projecao local; o teste real mede erro na casa de 1e-9.
TOL_MASSA = 1e-6

COLUNAS_1KM_AREA = [
    "oferta_efetiva_1km_area",
    "n_concorrentes_influencia_1km",
    "consumo_concorrentes_1km_area",
    "gap_competitivo_1km_area",
    "pressao_concorrencial_score_1km_area",
    "n_concorrentes_no_hex",
]


def _metros_por_grau(lat0: float) -> tuple[float, float]:
    """Metros por grau de latitude e de longitude na latitude `lat0` (elipsoide WGS84).

    Series padrao de aproximacao do WGS84. Usar as CONSTANTES redondas (110.540 e
    111.320 x cos) em vez destas series custava ~0,05% de escala — pouco em distancia,
    mas o bastante para deformar levemente o disco (que e' circular no plano projetado)
    e deslocar os shares em ~2e-4. Com as series a diferenca contra a AEQD do pyproj cai
    para <1e-5 (`test_projecao_local_bate_com_aeqd`).
    """
    phi = math.radians(lat0)
    m_lat = (
        111_132.92
        - 559.82 * math.cos(2 * phi)
        + 1.175 * math.cos(4 * phi)
        - 0.0023 * math.cos(6 * phi)
    )
    m_lng = (
        111_412.84 * math.cos(phi)
        - 93.5 * math.cos(3 * phi)
        + 0.118 * math.cos(5 * phi)
    )
    return m_lat, m_lng


def _projetar(
    lats: np.ndarray | Iterable[float],
    lngs: np.ndarray | Iterable[float],
    lat0: float,
    lng0: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Projeta (lat, lng) para metros num plano local centrado em (lat0, lng0).

    Equirretangular local com as escalas WGS84 de `_metros_por_grau`. Na janela deste
    calculo (~3 km em volta do concorrente) reproduz a azimutal equidistante do pyproj
    com erro de share ~1,5e-5 — **0,04 aluno** dos 2.500 de um concorrente — sem pagar a
    construcao de um Transformer por concorrente.
    `test_projecao_local_bate_com_aeqd` confronta os dois e trava a diferenca.
    """
    lats_arr = np.asarray(lats, dtype=np.float64)
    lngs_arr = np.asarray(lngs, dtype=np.float64)
    m_por_grau_lat, m_por_grau_lng = _metros_por_grau(lat0)
    x = (lngs_arr - lng0) * m_por_grau_lng
    y = (lats_arr - lat0) * m_por_grau_lat
    return x, y


def _poligono_do_hex(hex_id: str, lat0: float, lng0: float) -> Polygon:
    """Poligono do hexagono H3 projetado no plano local de (lat0, lng0)."""
    boundary = h3.cell_to_boundary(hex_id)
    lats = [p[0] for p in boundary]
    lngs = [p[1] for p in boundary]
    x, y = _projetar(lats, lngs, lat0, lng0)
    return Polygon(zip(x, y, strict=True))


def shares_por_hex(
    lat: float,
    lng: float,
    *,
    raio_m: float = RAIO_INFLUENCIA_M,
    h3_res: int = H3_RESOLUTION,
    k: int = GRID_DISK_K,
) -> dict[str, float]:
    """Reparte o disco de influencia de UM concorrente entre os hexagonos que ele cobre.

    Devolve `{hex_id: share}` com `share` = fracao da AREA do disco que cai naquele
    hexagono. Hexes com share nulo sao omitidos. A soma dos shares e' 1 (ate `TOL_MASSA`):
    o disco de 1 km nunca escapa do anel `k`, entao nada de massa se perde.

    Funcao pura: nao le disco, nao usa rede, nao muta nada.
    """
    celula_central = h3.latlng_to_cell(lat, lng, h3_res)
    candidatos = h3.grid_disk(celula_central, k)

    disco = Point(0.0, 0.0).buffer(raio_m, quad_segs=QUAD_SEGS)
    area_disco = disco.area

    shares: dict[str, float] = {}
    for hex_id in candidatos:
        poligono = _poligono_do_hex(hex_id, lat, lng)
        if not poligono.intersects(disco):
            continue
        area_intersecao = poligono.intersection(disco).area
        if area_intersecao <= 0.0:
            continue
        shares[hex_id] = area_intersecao / area_disco

    total = sum(shares.values())
    if not math.isclose(total, 1.0, abs_tol=TOL_MASSA):
        raise AssertionError(
            f"Conservacao de massa violada em ({lat}, {lng}): soma dos shares = {total!r}. "
            f"O disco de {raio_m:.0f} m escapou do anel k={k}."
        )
    return shares


def repartir_concorrentes(
    df_concorrentes: pd.DataFrame,
    *,
    raio_m: float = RAIO_INFLUENCIA_M,
    h3_res: int = H3_RESOLUTION,
    capacidade_alunos: float = CAPACIDADE_DEFAULT_CONCORRENTE_ALUNOS,
    coluna_lat: str = "lat",
    coluna_lng: str = "lng",
    coluna_capacidade: str | None = None,
    hex_ids_validos: set[str] | None = None,
) -> pd.DataFrame:
    """Agrega os shares de TODOS os concorrentes por hexagono.

    Espera um DataFrame ja filtrado (so registros validos) com colunas de lat/lng.
    Devolve um DataFrame com uma linha por hexagono tocado e as colunas:

      - `hex_id`
      - `oferta_efetiva_1km_area`      soma dos shares (unidades-equivalentes de concorrente)
      - `n_concorrentes_influencia_1km` quantos concorrentes distintos alcancam o hex
      - `consumo_concorrentes_1km_area` oferta * capacidade, em alunos

    `hex_ids_validos`: quando informado, o share de CADA concorrente e' filtrado a esse
    conjunto e RENORMALIZADO para fechar em 1,0 sobre os hexagonos validos que ele
    alcanca — antes de agregar entre concorrentes. Um concorrente sem NENHUM hexagono
    valido no alcance contribui zero (nao ha' massa para redistribuir). Com
    `hex_ids_validos=None` (default), a funcao NAO filtra nem renormaliza — comportamento
    historico, preservado para quem chama sem conhecer a base de hexes de antemao.

    Invariante quando `hex_ids_validos=None`: `oferta_efetiva_1km_area.sum()` == numero
    de concorrentes de entrada com coordenada. Quando `hex_ids_validos` e' informado, a
    soma e' o numero de concorrentes que alcancam PELO MENOS UM hexagono valido (pode ser
    menor que o total de concorrentes, se algum estiver inteiramente fora da base).

    `coluna_capacidade` (BLK-CAPACIDADE-01): quando informada, o consumo deixa de ser
    `oferta x escalar` e passa a ser somado POR UNIDADE -- cada academia derrama no
    hexagono a fracao de area vezes a capacidade DELA. Linha sem valor cai no
    `capacidade_alunos` default, entao a rede sem planilha continua valendo o proxy.

    As DUAS colunas de saida deixam de ser proporcionais quando isso acontece, e essa
    separacao e' o ponto: `oferta_efetiva_1km_area` continua em UNIDADES-EQUIVALENTES
    (e' o que alimenta `gap_competitivo` e a pressao, que perguntam "quantos me cercam")
    e `consumo_concorrentes_1km_area` passa a ser ALUNOS DE VERDADE (e' o que o residual
    subtrai do mercado). Antes, dividir uma pela outra devolvia sempre 2.500; agora nao
    devolve, e por isso quem quiser CONTAR concorrente tem de ler
    `n_concorrentes_influencia_1km`, nunca o consumo dividido pela capacidade.
    """
    lats = pd.to_numeric(df_concorrentes[coluna_lat], errors="coerce")
    lngs = pd.to_numeric(df_concorrentes[coluna_lng], errors="coerce")
    validos = lats.notna() & lngs.notna()

    if coluna_capacidade and coluna_capacidade in df_concorrentes.columns:
        caps = (
            pd.to_numeric(df_concorrentes[coluna_capacidade], errors="coerce")
            .fillna(float(capacidade_alunos))
            .clip(lower=0.0)
        )
    else:
        caps = pd.Series(float(capacidade_alunos), index=df_concorrentes.index)

    acumulado: dict[str, float] = {}
    contagem: dict[str, int] = {}
    alunos: dict[str, float] = {}
    for lat, lng, cap in zip(lats[validos], lngs[validos], caps[validos], strict=True):
        shares = shares_por_hex(float(lat), float(lng), raio_m=raio_m, h3_res=h3_res)
        if hex_ids_validos is not None:
            shares = {h: s for h, s in shares.items() if h in hex_ids_validos}
            total_valido = sum(shares.values())
            if total_valido <= 0.0:
                continue  # concorrente inteiramente fora da base -- nada a redistribuir
            shares = {h: s / total_valido for h, s in shares.items()}
        for hex_id, share in shares.items():
            acumulado[hex_id] = acumulado.get(hex_id, 0.0) + share
            contagem[hex_id] = contagem.get(hex_id, 0) + 1
            alunos[hex_id] = alunos.get(hex_id, 0.0) + share * float(cap)

    if not acumulado:
        return pd.DataFrame(
            {
                "hex_id": pd.Series(dtype="object"),
                "oferta_efetiva_1km_area": pd.Series(dtype="float64"),
                "n_concorrentes_influencia_1km": pd.Series(dtype="int64"),
                "consumo_concorrentes_1km_area": pd.Series(dtype="float64"),
            }
        )

    out = pd.DataFrame(
        {
            "hex_id": list(acumulado.keys()),
            "oferta_efetiva_1km_area": list(acumulado.values()),
            "n_concorrentes_influencia_1km": [contagem[h] for h in acumulado],
        }
    )
    out["consumo_concorrentes_1km_area"] = [alunos[h] for h in acumulado]
    return out.sort_values("hex_id", ignore_index=True)


def _contagem_no_hex(
    df_concorrentes: pd.DataFrame,
    *,
    h3_res: int = H3_RESOLUTION,
    coluna_lat: str = "lat",
    coluna_lng: str = "lng",
) -> pd.DataFrame:
    """Quantas unidades CAEM DENTRO de cada hexagono (a coordenada, nao o disco).

    E' uma pergunta diferente de `n_concorrentes_influencia_1km`, que conta quem ALCANCA o
    hexagono com o disco de 1 km. Aqui conta-se quem esta' fisicamente ali.

    POR QUE ELA EXISTE. A calibracao da taxa de penetracao precisa escolher em QUE lugares
    ela observa a demanda revelada, e "tem academia num raio" nao serve: com o numerador de
    1 km, entram hexagonos que o disco de uma academia apenas ENCOSTA -- eles recebem uma
    fatia minima dos alunos e a populacao INTEIRA, entao medem penetracao proxima de zero
    por dilucao geometrica, nao por escassez de oferta. Medido: 29% da amostra, e o piso de
    5% os censurava em silencio. Com a mascara larga a taxa sai 10,6%; com esta, 17,3%.

    A alternativa barata -- reusar `n_concorrentes_mapeados_1km > 0` -- foi MEDIDA e
    rejeitada: ela devolve 1.695 hexagonos contra 2.451, perdendo 31% deles, e nao e' um
    recorte aleatorio (o raio de 1 km do centroide nao alcanca as bordas do hexagono, cujo
    circunraio e' 1,41 km). A taxa resultante seria 19,45% em vez de 17,31%.
    """
    lat = pd.to_numeric(df_concorrentes.get(coluna_lat), errors="coerce")
    lng = pd.to_numeric(df_concorrentes.get(coluna_lng), errors="coerce")
    validos = lat.notna() & lng.notna()
    if not validos.any():
        return pd.DataFrame({"hex_id": pd.Series(dtype="object"),
                             "n_concorrentes_no_hex": pd.Series(dtype="int64")})

    celulas = [
        h3.latlng_to_cell(float(a), float(b), h3_res)
        for a, b in zip(lat[validos], lng[validos], strict=True)
    ]
    return (
        pd.Series(celulas, name="hex_id")
        .value_counts()
        .rename_axis("hex_id")
        .reset_index(name="n_concorrentes_no_hex")
    )


def anexar_pressao_1km_area(
    df_hex: pd.DataFrame,
    df_concorrentes: pd.DataFrame,
    *,
    raio_m: float = RAIO_INFLUENCIA_M,
    h3_res: int = H3_RESOLUTION,
    capacidade_alunos: float = CAPACIDADE_DEFAULT_CONCORRENTE_ALUNOS,
    coluna_capacidade: str | None = None,
) -> pd.DataFrame:
    """Anexa as colunas `*_1km_area` ao DataFrame de hexagonos, sem tocar as de 2 km.

    Preserva cardinalidade e todas as colunas existentes. Hexes nao alcancados por
    nenhum concorrente recebem oferta 0 -> `gap_competitivo_1km_area` = 1 e
    `pressao_concorrencial_score_1km_area` = 0 (mesma convencao do modelo de 2 km).

    CONSERVA MASSA sobre a base real (corrigido). `repartir_concorrentes` recebe
    `hex_ids_validos=set(df_hex["hex_id"])`, entao cada concorrente ja chega com o share
    filtrado e renormalizado para fechar em 1,0 sobre os hexagonos que EXISTEM em
    `df_hex` -- o `merge` abaixo nao descarta mais massa (so' pode faltar bater algo que
    ja chegou zerado). Excecao inevitavel: um concorrente cujo disco de 1 km cai 100%
    fora da base (litoral, fronteira, hexagono podado por `M1_HEX_LAND_FRACTION_MIN`)
    contribui zero -- nao ha hexagono valido para receber a massa dele. Ver o docstring
    do modulo para o numero medido antes desta correcao.
    """
    n_orig = len(df_hex)
    agregado = repartir_concorrentes(
        df_concorrentes,
        raio_m=raio_m,
        h3_res=h3_res,
        capacidade_alunos=capacidade_alunos,
        coluna_capacidade=coluna_capacidade,
        hex_ids_validos=set(df_hex["hex_id"]),
    )

    out = df_hex.drop(
        columns=[c for c in COLUNAS_1KM_AREA if c in df_hex.columns]
    ).merge(agregado, on="hex_id", how="left", validate="one_to_one")

    out = out.merge(
        _contagem_no_hex(df_concorrentes, h3_res=h3_res),
        on="hex_id",
        how="left",
        validate="one_to_one",
    )
    out["n_concorrentes_no_hex"] = (
        pd.to_numeric(out["n_concorrentes_no_hex"], errors="coerce").fillna(0).astype("int64")
    )

    out["oferta_efetiva_1km_area"] = (
        pd.to_numeric(out["oferta_efetiva_1km_area"], errors="coerce").fillna(0.0)
    )
    out["n_concorrentes_influencia_1km"] = (
        pd.to_numeric(out["n_concorrentes_influencia_1km"], errors="coerce")
        .fillna(0)
        .astype("int64")
    )
    out["consumo_concorrentes_1km_area"] = (
        pd.to_numeric(out["consumo_concorrentes_1km_area"], errors="coerce").fillna(0.0)
    )
    # Mesma forma funcional do modelo de 2 km, para o comparativo ser honesto.
    out["gap_competitivo_1km_area"] = 1.0 / (1.0 + out["oferta_efetiva_1km_area"])
    out["pressao_concorrencial_score_1km_area"] = 100.0 * (
        1.0 - out["gap_competitivo_1km_area"]
    )

    assert len(out) == n_orig, "Cardinalidade alterada ao anexar colunas 1km_area"
    return out


# ── Modelo atual (2 km do centroide), reimplementado para o COMPARATIVO ───────


def oferta_2km_centroide(
    df_hex: pd.DataFrame,
    df_concorrentes: pd.DataFrame,
    *,
    raio_m: float = 2_000.0,
    coluna_lat: str = "lat",
    coluna_lng: str = "lng",
) -> pd.Series:
    """Reproduz `oferta_efetiva_mapeada_2km` do Bloco 3, para comparar os dois modelos.

    Espelha `enriquecimento_espacial_hexagonos.calc_comp_metrics`: peso linear
    `max(0, 1 - d/raio)` da distancia CENTROIDE-DO-HEX ate cada concorrente. Existe aqui
    so' como referencia do comparativo — o pipeline de producao segue usando o Bloco 3.
    """
    from sklearn.neighbors import BallTree

    raio_terra_m = 6_371_000.0
    lats_c = pd.to_numeric(df_concorrentes[coluna_lat], errors="coerce")
    lngs_c = pd.to_numeric(df_concorrentes[coluna_lng], errors="coerce")
    validos = lats_c.notna() & lngs_c.notna()
    coords_conc = np.radians(
        np.column_stack([lats_c[validos].to_numpy(), lngs_c[validos].to_numpy()])
    )
    if len(coords_conc) == 0:
        return pd.Series(0.0, index=df_hex.index, name="oferta_efetiva_mapeada_2km")

    coords_hex = np.radians(
        np.column_stack(
            [
                pd.to_numeric(df_hex[coluna_lat], errors="coerce").to_numpy(),
                pd.to_numeric(df_hex[coluna_lng], errors="coerce").to_numpy(),
            ]
        )
    )
    tree = BallTree(coords_conc, metric="haversine")
    indices, dists_rad = tree.query_radius(
        coords_hex, r=raio_m / raio_terra_m, return_distance=True, sort_results=False
    )

    oferta = np.zeros(len(df_hex), dtype=np.float64)
    for i, (idxs, dr) in enumerate(zip(indices, dists_rad, strict=True)):
        if len(idxs) == 0:
            continue
        dm = dr * raio_terra_m
        oferta[i] = np.maximum(0.0, 1.0 - dm / raio_m).sum()
    return pd.Series(oferta, index=df_hex.index, name="oferta_efetiva_mapeada_2km")


def comparar_modelos(
    df_hex: pd.DataFrame,
    df_concorrentes: pd.DataFrame,
    *,
    capacidade_alunos: float = CAPACIDADE_DEFAULT_CONCORRENTE_ALUNOS,
) -> pd.DataFrame:
    """Tabela hex a hex com os dois modelos lado a lado (insumo do relatorio).

    Colunas: `hex_id`, oferta e consumo em cada modelo, e o delta de consumo
    (`delta_consumo` > 0 = o modelo novo cobra MAIS oferta consumida naquele hex, o que
    DERRUBA o residual dali; < 0 = alivia e o residual sobe).

    LADO DE COMPARACAO: se `df_hex` ja traz `oferta_efetiva_mapeada_2km` — a coluna que o
    Bloco 3 materializou em PRODUCAO — ela e' usada COMO ESTA. `oferta_2km_centroide` so'
    roda quando a coluna nao existe.

    Isto nao e' detalhe. Esta funcao existe para decidir se o residual muda de base. Se
    ela sobrescrevesse o valor de producao pela reimplementacao local, o comparativo
    viraria "modelo novo vs minha copia do modelo antigo", e qualquer divergencia entre a
    copia e o pipeline real (filtro de concorrente, snapshot da coleta, raio) ficaria
    INVISIVEL justamente no numero que sustenta a decisao. `fonte_2km` registra qual dos
    dois caminhos alimentou a comparacao.
    """
    out = anexar_pressao_1km_area(
        df_hex, df_concorrentes, capacidade_alunos=capacidade_alunos
    )
    if "oferta_efetiva_mapeada_2km" in df_hex.columns:
        out["oferta_efetiva_mapeada_2km"] = (
            pd.to_numeric(df_hex["oferta_efetiva_mapeada_2km"], errors="coerce")
            .fillna(0.0)
            .to_numpy()
        )
        out["fonte_2km"] = "producao"
    else:
        out["oferta_efetiva_mapeada_2km"] = oferta_2km_centroide(
            df_hex, df_concorrentes
        ).to_numpy()
        out["fonte_2km"] = "recalculado"
    out["consumo_concorrentes_2km"] = (
        out["oferta_efetiva_mapeada_2km"] * float(capacidade_alunos)
    )
    out["delta_consumo"] = (
        out["consumo_concorrentes_1km_area"] - out["consumo_concorrentes_2km"]
    )
    colunas = [
        "hex_id",
        "fonte_2km",
        "oferta_efetiva_mapeada_2km",
        "consumo_concorrentes_2km",
        "oferta_efetiva_1km_area",
        "n_concorrentes_influencia_1km",
        "consumo_concorrentes_1km_area",
        "delta_consumo",
    ]
    return out[[c for c in colunas if c in out.columns]]
