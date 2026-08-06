"""Pressao concorrencial por raio de 1 km com reparticao por AREA (camada paralela).

CONTEXTO — o que existe hoje (`enriquecimento_espacial_hexagonos.py`)
--------------------------------------------------------------------
O motor atual mede a oferta a partir do CENTROIDE do hexagono: para cada hex, soma
todo concorrente ate 2 km com peso linear `max(0, 1 - d/2000)`:

    oferta_efetiva_mapeada_2km[hex] = SOMA_concorrentes max(0, 1 - d_centroide/2000)

Duas consequencias incomodas (numeros MEDIDOS, 400 pontos sorteados dentro de um hex
res-7 em Sao Paulo — `tests/unit/test_pressao_concorrencial_1km.py` trava as faixas):

1. **Nao conserva massa, e o vazamento e' irregular.** A soma dos pesos que um unico
   concorrente injeta no sistema varia entre **0,73 e 0,98** (media 0,80) conforme onde
   ele cai dentro do hexagono. Ou seja: o modelo atual subestima o consumo de cada
   concorrente em ~20% na media, e de forma DESIGUAL entre hexes — dois concorrentes
   identicos contam diferente so' por causa da posicao relativa ao centroide.
2. **Ignora a geometria do hexagono.** So a distancia ao centroide conta. Um concorrente
   colado na fronteira entre dois hexes e' tratado como se pertencesse quase todo ao hex
   cujo centroide esta mais perto, mesmo atendendo os dois igualmente.

Observacao contra-intuitiva, mas medida: o raio de 2 km NAO espalha para mais hexes que
o de 1 km. Em res-7 os centroides vizinhos ficam a **2.387-2.513 m** um do outro, entao
um raio de 2 km partindo do centroide mal alcanca os vizinhos — o modelo atual toca
**2,4 hexes** na media (1 a 3). O modelo novo toca **3,3** (1 a 4), porque area de
intersecao enxerga vizinho que distancia-ao-centroide nao enxerga.

O QUE ESTE MODULO FAZ
---------------------
Cada concorrente vira uma FONTE com disco de influencia de raio fixo (1 km). A
capacidade dele (2.500 alunos por unidade, o mesmo proxy do Bloco 5) e' repartida
entre os hexagonos que o disco cobre, na proporcao da AREA DE INTERSECAO:

    share(concorrente c -> hex h) = area(disco_c INTERSECAO hex_h) / area(disco_c)
    SOMA_h share(c -> h) = 1                      <- conservacao de massa, exata
    oferta_efetiva_1km_area[h] = SOMA_c share(c -> h)
    consumo_concorrentes_1km_area[h] = oferta_efetiva_1km_area[h] * capacidade

Kernel UNIFORME por decisao de Felipe (2026-08-05): cada m2 do disco pesa igual, o
share e' area pura. Alternativas avaliadas e recusadas nesta rodada: decaimento linear
dentro do disco e raio variavel por porte de rede.

Escala para calibrar expectativa: hex H3 res-7 = **5,21 km2**; disco de 1 km = 3,14 km2.
O disco cabe dentro de um hexagono, mas raramente esta centrado nele: na pratica se
reparte entre 1 e 4 hexes (media 3,3).

EFEITO ESPERADO NO RESIDUAL — so' para baixo, NUNCA para cima. Duas medidas sustentam
isso, ambas travadas em teste:

  a) Cada concorrente passa a valer 1,00 unidade em vez de 0,80 -> o consumo total
     atribuido a concorrentes SOBE ~25%. Residual = SAM - consumo, logo o residual cai.
  b) O ALCANCE do modelo novo CONTEM o do antigo. Em 500 posicoes sorteadas, nao houve
     UM caso de hex alcancado pelo raio de 2 km e nao alcancado pelo disco de 1 km — o
     inverso ocorreu 396 vezes. Motivo geometrico: os hexes tem ~2,4 km de ponta a
     ponta, entao um concorrente a 1-2 km do centroide quase sempre esta a menos de
     1 km da BORDA, e seu disco ainda cobre pedaco do hex.

Consequencia pratica: nenhum hexagono ganha residual com a mudanca. Uns perdem muito
(onde ha concorrente colado), outros ficam iguais. O ganho nao e' de nivel, e' de
justica distributiva — o consumo pousa nos hexes que o concorrente de fato cobre, em vez
de vazar proporcional a distancia ate centroides.

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
) -> pd.DataFrame:
    """Agrega os shares de TODOS os concorrentes por hexagono.

    Espera um DataFrame ja filtrado (so registros validos) com colunas de lat/lng.
    Devolve um DataFrame com uma linha por hexagono tocado e as colunas:

      - `hex_id`
      - `oferta_efetiva_1km_area`      soma dos shares (unidades-equivalentes de concorrente)
      - `n_concorrentes_influencia_1km` quantos concorrentes distintos alcancam o hex
      - `consumo_concorrentes_1km_area` oferta * capacidade, em alunos

    Invariante: `oferta_efetiva_1km_area.sum()` == numero de concorrentes de entrada.
    """
    lats = pd.to_numeric(df_concorrentes[coluna_lat], errors="coerce")
    lngs = pd.to_numeric(df_concorrentes[coluna_lng], errors="coerce")
    validos = lats.notna() & lngs.notna()

    acumulado: dict[str, float] = {}
    contagem: dict[str, int] = {}
    for lat, lng in zip(lats[validos], lngs[validos], strict=True):
        for hex_id, share in shares_por_hex(
            float(lat), float(lng), raio_m=raio_m, h3_res=h3_res
        ).items():
            acumulado[hex_id] = acumulado.get(hex_id, 0.0) + share
            contagem[hex_id] = contagem.get(hex_id, 0) + 1

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
    out["consumo_concorrentes_1km_area"] = (
        out["oferta_efetiva_1km_area"] * float(capacidade_alunos)
    )
    return out.sort_values("hex_id", ignore_index=True)


def anexar_pressao_1km_area(
    df_hex: pd.DataFrame,
    df_concorrentes: pd.DataFrame,
    *,
    raio_m: float = RAIO_INFLUENCIA_M,
    h3_res: int = H3_RESOLUTION,
    capacidade_alunos: float = CAPACIDADE_DEFAULT_CONCORRENTE_ALUNOS,
) -> pd.DataFrame:
    """Anexa as colunas `*_1km_area` ao DataFrame de hexagonos, sem tocar as de 2 km.

    Preserva cardinalidade e todas as colunas existentes. Hexes nao alcancados por
    nenhum concorrente recebem oferta 0 -> `gap_competitivo_1km_area` = 1 e
    `pressao_concorrencial_score_1km_area` = 0 (mesma convencao do modelo de 2 km).
    """
    n_orig = len(df_hex)
    agregado = repartir_concorrentes(
        df_concorrentes,
        raio_m=raio_m,
        h3_res=h3_res,
        capacidade_alunos=capacidade_alunos,
    )

    out = df_hex.drop(
        columns=[c for c in COLUNAS_1KM_AREA if c in df_hex.columns]
    ).merge(agregado, on="hex_id", how="left", validate="one_to_one")

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
    """
    out = anexar_pressao_1km_area(
        df_hex, df_concorrentes, capacidade_alunos=capacidade_alunos
    )
    out["oferta_efetiva_mapeada_2km"] = oferta_2km_centroide(df_hex, df_concorrentes).values
    out["consumo_concorrentes_2km"] = (
        out["oferta_efetiva_mapeada_2km"] * float(capacidade_alunos)
    )
    out["delta_consumo"] = (
        out["consumo_concorrentes_1km_area"] - out["consumo_concorrentes_2km"]
    )
    colunas = [
        "hex_id",
        "oferta_efetiva_mapeada_2km",
        "consumo_concorrentes_2km",
        "oferta_efetiva_1km_area",
        "n_concorrentes_influencia_1km",
        "consumo_concorrentes_1km_area",
        "delta_consumo",
    ]
    return out[[c for c in colunas if c in out.columns]]
