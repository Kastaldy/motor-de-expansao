"""Mercado NO RAIO do ponto (ou numa geometria desenhada) -- runtime, READ-ONLY (DEC-069).

O PROBLEMA QUE ESTE MODULO FECHA
--------------------------------
Ate' a DEC-069 a ficha do ponto, o PDF do piloto e o PDF da API/bot liam SAM, consumo e
residual de UMA linha de `hexagonos_mercado_mapeado.parquet`: a do hexagono res-7 que
contem o ponto (`api.service._residual_do_ponto`). Tres defeitos de leitura, medidos no
caso de Santana/SP (-23,48516 / -46,61771, a 9 m da Ultra Santana):

1. GRAO MISTO. Populacao, renda e domicilios saiam do RAIO de 1,0 km (3,14 km2); SAM e
   consumo, do HEXAGONO (5,16 km2, centroide a 1.250 m do ponto). A pagina punha os dois
   lado a lado sem dizer.
2. TERMO ESCONDIDO. O residual do hexagono desconta concorrentes E Ultra, mas so' o termo
   de concorrentes aparecia. SAM 12.038 - consumo 9.170 = 2.868 na cabeca de quem le; o
   artefato diz 0, porque ainda tira 5.000 da Ultra que nao estavam na pagina.
3. DUPLA CONTAGEM DA ULTRA. Sem alunos reais no hexagono, o pipeline cai em
   `n_unidades_ultra_2km x 2.500` (`calcular_colunas_mercado.py`): conta inteira toda
   unidade a ate' 2 km do CENTROIDE, sem conservar massa -- a Ultra Vila Guilherme, que ja'
   desconta seus alunos reais no hexagono DELA, desconta mais 2.500 aqui. (Corrigir isso NO
   PIPELINE e' outra DEC, Critica; aqui so' o runtime deixa de herdar o defeito.)

A REGRA (DEC-069)
-----------------
Tudo no MESMO recorte do ponto -- o raio de 1,0 km (DEC-021) ou, para o lote de geometria
(DEC-070), o poligono desenhado:

    SAM_area      = pop_area x taxa_fitness_mercado_calibrada          (se o gate passa)
    consumo_i     = capacidade_i x area(disco 1 km da unidade INTERSECAO area) / area(disco)
    consumo_conc  = SOMA_i consumo_i   sobre o universo de CADEIA do pipeline
    consumo_ultra = SOMA_j consumo_j   sobre as unidades Ultra
    residual      = max(SAM_area - (consumo_conc + consumo_ultra), 0)

O consumo e' o MESMO modelo de area de influencia de 1 km que o pipeline usa desde a
DEC-051 (`pressao_concorrencial_1km`), com a mesma projecao local e o mesmo disco: cada
unidade derrama sua capacidade na proporcao da area do disco dela que cai dentro do
recorte. Isso CONSERVA MASSA (unidade no centro de um raio de 1 km conta inteira; a 2 km
conta zero) e e' o que elimina a dupla contagem: a Ultra entra pelo mesmo disco que as
concorrentes, e nao por contagem num raio de 2 km.

Gate: faixa M1 elegivel do HEXAGONO do ponto (a faixa e' do M1 e nao existe por raio) E
`pop_area >= POP_MIN_SAM_GATE` -- a regua da DEC-007 com a populacao trocada pela do
recorte. Reprovado, SAM = 0 com o motivo dito, igual ao pipeline (`flag_sam`).

Score do residual: a regua ABSOLUTA do pipeline, `100 x residual / 2.500` com clip em
[0, 100] (`SCORE_RESIDUAL_CAPACIDADE_REFERENCIA`). Ela converte alunos em score sem
percentil nenhum, entao se aplica ao raio sem reescala. NAO e' o score do hexagono.

O QUE NAO MUDA. Nada e' recalculado no M1 nem no artefato de mercado: a taxa e a faixa
sao LIDAS do hexagono do ponto, o universo de cadeia e montado pelas MESMAS funcoes do
pipeline (`unir_cadeias` -> `excluir_estudios_boutique` -> `anexar_capacidade_real`,
DEC-048/056/057, com a dedup DEC-034/062 ja' materializada em `tem_pin_proprio`) e a
capacidade default e' a constante do pipeline, importada. As metas absolutas dos Big
Numbers (2.000/2.000) foram MANTIDAS por decisao do dono, como a DEC-021 fez com as de
populacao.

DEGRADACAO. Sem o insumo de concorrentes ou de Ultra (instancia sem `data/staging`, ou
o perfil AR), os campos de consumo e residual saem `None` com motivo -- NUNCA zero. Zero
de consumo afirmaria mercado livre por ausencia de dado.
"""

from __future__ import annotations

import logging
import math
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform as _shp_transform

from motor_expansao.pipelines.calcular_colunas_mercado import (
    CAPACIDADE_DEFAULT_CONCORRENTE_ALUNOS,
    POP_MIN_SAM_GATE,
    SCORE_RESIDUAL_CAPACIDADE_REFERENCIA,
)

# A MESMA projecao local e o MESMO disco do modelo de 1 km do pipeline. `_projetar` e'
# privado la', mas reimplementa-lo aqui seria a segunda regua que a DEC-044 ensinou a
# evitar: um share calculado com outra escala de metros por grau nao bateria com o
# `consumo_concorrentes_1km_area` do artefato nem no caso trivial.
from motor_expansao.pipelines.pressao_concorrencial_1km import (
    QUAD_SEGS,
    RAIO_INFLUENCIA_M,
    _projetar,
)

_LOG = logging.getLogger(__name__)

# Raio canonico do Relatorio Pontual (DEC-021). Repetido como literal, e NAO importado de
# `censo_point`, porque aquele modulo puxa pyproj/geopandas no import e este precisa ser
# barato -- a igualdade e' travada por `test_raio_default_casa_com_o_do_censo`.
RAIO_MERCADO_DEFAULT_KM = 1.0

# Identificadores CRUS do grao (payload), sem acento (CLAUDE.md secao 2).
GRAO_RAIO = "raio"
GRAO_GEOMETRIA = "geometria"

# Faixas do M1 que abrem o SAM -- o MESMO conjunto literal do gate da DEC-007 em
# `calcular_colunas_mercado.calcular` (la' ele e' inline, sem constante para importar).
# A igualdade e' travada por `test_faixas_elegiveis_casam_com_o_pipeline`, que le o
# fonte do pipeline: se alguem mudar la', este teste fica vermelho.
FAIXAS_SAM_ELEGIVEIS = frozenset({"baixa", "media", "alta", "prioridade_maxima"})

# Motivos do gate (texto ao usuario, com acento).
MOTIVO_FAIXA_INELEGIVEL = "Hexágono do ponto fora das faixas elegíveis do M1: SAM zerado pelo gate."
MOTIVO_FAIXA_DESCONHECIDA = (
    "Hexágono do ponto fora da base de mercado: sem faixa M1 para abrir o SAM."
)
MOTIVO_POP_INSUFICIENTE = (
    f"População da área analisada abaixo de {POP_MIN_SAM_GATE:,}".replace(",", ".")
    + " habitantes: SAM zerado pelo gate."
)

# Nomes dos insumos em `data/staging` -- os mesmos que o pipeline le.
ARQ_CONCORRENTES = "concorrentes_mapeados.parquet"
ARQ_REDES_AGREGADOR = "vulnerabilidade_ma_redes.parquet"
ARQ_ALUNOS_REAIS = "alunos_reais_por_unidade.parquet"
ARQ_ULTRA = "unidades_ultra_mapeadas.parquet"
ARQ_ULTRA_PERFORMANCE = "unidades_ultra_performance_hex.parquet"

# Casamento coordenada-a-coordenada entre o cadastro da Ultra e o arquivo de performance.
# Medido em 2026-10-14: as 53 unidades de performance com coordenada caem a 0,0 m da
# unidade mapeada correspondente. 50 m e' o piso de dedup da DEC-034, reusado.
_MATCH_ULTRA_M = 50.0

COLUNA_CAPACIDADE = "capacidade_alunos"

# Abaixo disto a intersecao e' ruido dos POLIGONOS que aproximam os dois circulos (512
# lados cada): dois discos TANGENTES se sobrepoem em ~1e-7 da area. 1e-6 = 0,0025 aluno de
# um concorrente de 2.500 -- nada na conta, e impede que unidade tangente conte como
# "alcanca o raio".
_FRACAO_MINIMA = 1e-6


# --------------------------------------------------------------------------- #
# Geometria pura                                                               #
# --------------------------------------------------------------------------- #
def area_local(
    lat: float,
    lng: float,
    *,
    raio_km: float = RAIO_MERCADO_DEFAULT_KM,
    geometria: BaseGeometry | None = None,
) -> BaseGeometry:
    """O recorte do ponto no plano LOCAL (metros) centrado em (lat, lng).

    Sem `geometria`: o disco de `raio_km`, com o mesmo `QUAD_SEGS` do disco de influencia.
    Com `geometria` (shapely em GRAUS, convencao GeoJSON x=lng, y=lat): o poligono
    projetado no mesmo plano. O chamador passa como (lat, lng) um ponto DENTRO dele (o
    `representative_point`), que vira a origem da projecao.
    """
    if geometria is None:
        return Point(0.0, 0.0).buffer(float(raio_km) * 1_000.0, quad_segs=QUAD_SEGS)

    def _proj(xs, ys, zs=None):  # x = lng, y = lat
        x, y = _projetar(np.asarray(ys, dtype=float), np.asarray(xs, dtype=float), lat, lng)
        return x, y

    return _shp_transform(_proj, geometria)


def fracao_do_disco(
    x: float, y: float, area: BaseGeometry, *, raio_influencia_m: float = RAIO_INFLUENCIA_M
) -> float:
    """Fracao (0-1) do disco de influencia de uma unidade em (x, y) que cai dentro de `area`.

    E' o `share` do pipeline (`shares_por_hex`) com o hexagono trocado pelo recorte do
    ponto. Unidade no centro de um raio de 1 km -> 1,0; a 2 km -> 0,0; a 1 km -> a lente.
    """
    disco = Point(float(x), float(y)).buffer(raio_influencia_m, quad_segs=QUAD_SEGS)
    if not disco.intersects(area):
        return 0.0
    fracao = float(disco.intersection(area).area / disco.area)
    return fracao if fracao > _FRACAO_MINIMA else 0.0


def consumo_na_area(
    unidades: pd.DataFrame | None,
    area: BaseGeometry,
    lat0: float,
    lng0: float,
    *,
    raio_influencia_m: float = RAIO_INFLUENCIA_M,
    capacidade_default: float = CAPACIDADE_DEFAULT_CONCORRENTE_ALUNOS,
    coluna_capacidade: str = COLUNA_CAPACIDADE,
) -> dict[str, float | int] | None:
    """Alunos que as `unidades` consomem dentro de `area` (plano local de lat0/lng0).

    `None` quando o insumo nao existe -- o chamador NAO pode ler isso como zero.
    Capacidade por unidade quando a coluna existe (DEC-057); o resto, `capacidade_default`.
    """
    if unidades is None:
        return None
    vazio = {"alunos": 0.0, "equivalentes": 0.0, "n_unidades": 0, "n_capacidade_real": 0}
    if unidades.empty:
        return vazio

    lat = pd.to_numeric(unidades["lat"], errors="coerce").to_numpy(dtype=float)
    lng = pd.to_numeric(unidades["lng"], errors="coerce").to_numpy(dtype=float)
    validos = np.isfinite(lat) & np.isfinite(lng)
    if coluna_capacidade in unidades.columns:
        cap_bruta = pd.to_numeric(unidades[coluna_capacidade], errors="coerce").to_numpy(dtype=float)
    else:
        cap_bruta = np.full(len(unidades), np.nan)
    tem_real = np.isfinite(cap_bruta) & (cap_bruta > 0)
    caps = np.where(tem_real, cap_bruta, float(capacidade_default))

    x, y = _projetar(lat[validos], lng[validos], lat0, lng0)
    caps, tem_real = caps[validos], tem_real[validos]

    # Pre-filtro barato pela caixa do recorte acrescida do raio de influencia: so' quem
    # pode tocar a area paga a intersecao de poligonos.
    minx, miny, maxx, maxy = area.bounds
    perto = (
        (x >= minx - raio_influencia_m) & (x <= maxx + raio_influencia_m)
        & (y >= miny - raio_influencia_m) & (y <= maxy + raio_influencia_m)
    )

    alunos = equivalentes = 0.0
    n = n_real = 0
    for xi, yi, cap, real in zip(x[perto], y[perto], caps[perto], tem_real[perto], strict=True):
        f = fracao_do_disco(xi, yi, area, raio_influencia_m=raio_influencia_m)
        if f <= 0.0:
            continue
        alunos += f * float(cap)
        equivalentes += f
        n += 1
        n_real += int(bool(real))
    return {"alunos": alunos, "equivalentes": equivalentes, "n_unidades": n, "n_capacidade_real": n_real}


# --------------------------------------------------------------------------- #
# A conta                                                                      #
# --------------------------------------------------------------------------- #
def _finito(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def mercado_na_area(
    lat: float,
    lng: float,
    *,
    pop_area: float | None,
    cadeias: pd.DataFrame | None,
    ultra: pd.DataFrame | None,
    taxa: float | None,
    faixa_oportunidade: str | None,
    raio_km: float = RAIO_MERCADO_DEFAULT_KM,
    geometria: BaseGeometry | None = None,
) -> dict[str, Any]:
    """SAM, consumo (concorrentes + Ultra) e residual DENTRO do recorte do ponto.

    Funcao pura: nao le disco, nao muta entrada. `geometria` (graus, x=lng) troca o raio
    pelo poligono desenhado (DEC-070); sem ela, o raio de `raio_km` em volta de (lat, lng).

    As chaves de valor tem os MESMOS nomes das colunas do artefato de mercado
    (`sam_fitness_potencial`, `oferta_consumida_*`, `oferta_efetiva_disponivel`,
    `score_oportunidade_residual`) porque e' isso que o gerador do PDF ja' le -- o
    significado muda para o recorte, o contrato de leitura nao.
    """
    area = area_local(lat, lng, raio_km=raio_km, geometria=geometria)
    pop = _finito(pop_area)
    taxa_f = _finito(taxa)
    faixa = None if faixa_oportunidade is None or pd.isna(faixa_oportunidade) else str(faixa_oportunidade)

    motivos: list[str] = []

    # --- gate (DEC-007 com a populacao do recorte) ---
    faixa_ok = faixa in FAIXAS_SAM_ELEGIVEIS if faixa is not None else False
    pop_ok = None if pop is None else pop >= POP_MIN_SAM_GATE
    flag_sam = None if pop_ok is None else (faixa_ok and pop_ok)
    motivo_gate = None
    if faixa is None:
        motivo_gate = MOTIVO_FAIXA_DESCONHECIDA
    elif not faixa_ok:
        motivo_gate = MOTIVO_FAIXA_INELEGIVEL
    elif pop_ok is False:
        motivo_gate = MOTIVO_POP_INSUFICIENTE

    # --- SAM ---
    if taxa_f is None:
        sam = None
        motivos.append("Sem taxa de penetração calibrada (base de mercado ausente).")
    elif pop is None:
        sam = None
        motivos.append("Sem população do censo no recorte.")
    else:
        sam = max(pop, 0.0) * taxa_f if flag_sam else 0.0

    # --- consumo ---
    conc = consumo_na_area(cadeias, area, lat, lng)
    ult = consumo_na_area(ultra, area, lat, lng)
    if conc is None:
        motivos.append("Sem base de concorrentes de cadeia montada: consumo não calculado.")
    if ult is None:
        motivos.append("Sem cadastro de unidades Ultra: consumo da rede própria não calculado.")
    consumo_conc = None if conc is None else conc["alunos"]
    consumo_ultra = None if ult is None else ult["alunos"]
    consumo_total = (
        None if consumo_conc is None or consumo_ultra is None else consumo_conc + consumo_ultra
    )

    # --- residual e score (regua ABSOLUTA do pipeline) ---
    if sam is None or consumo_total is None:
        residual = None
        score = None
    else:
        residual = max(sam - consumo_total, 0.0)
        score = min(max(100.0 * residual / SCORE_RESIDUAL_CAPACIDADE_REFERENCIA, 0.0), 100.0)

    return {
        "grao": GRAO_GEOMETRIA if geometria is not None else GRAO_RAIO,
        "raio_km": None if geometria is not None else float(raio_km),
        "area_km2": float(area.area) / 1e6,
        "pop_area": pop,
        "taxa_fitness_mercado": taxa_f,
        "faixa_oportunidade": faixa,
        "gate_faixa_elegivel": bool(faixa_ok),
        "gate_pop_ok": pop_ok,
        "pop_minima_gate": POP_MIN_SAM_GATE,
        "flag_sam": flag_sam,
        "motivo_gate": motivo_gate,
        "sam_fitness_potencial": sam,
        "oferta_consumida_mercado_estimada": consumo_conc,
        "oferta_consumida_ultra_estimada": consumo_ultra,
        "oferta_consumida_total_estimada": consumo_total,
        "oferta_efetiva_disponivel": residual,
        "score_oportunidade_residual": score,
        "oferta_equivalente_concorrentes": None if conc is None else conc["equivalentes"],
        "n_concorrentes_alcancam": None if conc is None else conc["n_unidades"],
        "n_concorrentes_capacidade_real": None if conc is None else conc["n_capacidade_real"],
        "n_ultra_alcancam": None if ult is None else ult["n_unidades"],
        "n_ultra_alunos_reais": None if ult is None else ult["n_capacidade_real"],
        "disponivel": sam is not None,
        "motivo": " ".join(motivos) or None,
    }


# --------------------------------------------------------------------------- #
# Insumos (lidos UMA vez por processo)                                         #
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=2)
def carregar_cadeias_mercado(staging_dir_str: str) -> pd.DataFrame | None:
    """Universo de CADEIA do residual, montado pelas MESMAS funcoes do pipeline.

    `concorrentes_mapeados` + unidades de rede do agregador que o cadastro nao tem
    (DEC-048, dedup DEC-034/062 via `tem_pin_proprio`) -> sem estudios boutique
    (DEC-056) -> capacidade real por unidade quando o crosswalk existe (DEC-057).
    `None` quando o cadastro falta: e' o caso previsto (staging nao montado / perfil AR).
    """
    staging = Path(staging_dir_str)
    caminho = staging / ARQ_CONCORRENTES
    if not caminho.is_file():
        return None
    try:
        # Import LAZY: o modulo do pipeline puxa sklearn no import, e so' este caminho
        # precisa dele.
        from motor_expansao.pipelines.enriquecimento_espacial_hexagonos import (
            anexar_capacidade_real,
            excluir_estudios_boutique,
            unir_cadeias,
        )

        df_comp = pd.read_parquet(caminho)
        redes_path = staging / ARQ_REDES_AGREGADOR
        df_redes = pd.read_parquet(redes_path) if redes_path.is_file() else None
        cadeias = unir_cadeias(df_comp, df_redes)
        cadeias = excluir_estudios_boutique(cadeias)
        cadeias = anexar_capacidade_real(cadeias, crosswalk_path=staging / ARQ_ALUNOS_REAIS)
    except Exception as exc:  # noqa: BLE001
        _LOG.warning("mercado no raio: universo de cadeia indisponivel (%r)", exc)
        return None
    colunas = ["lat", "lng"] + ([COLUNA_CAPACIDADE] if COLUNA_CAPACIDADE in cadeias.columns else [])
    return cadeias[colunas].reset_index(drop=True)


def _dist_m(lat: float, lng: float, lats: np.ndarray, lngs: np.ndarray) -> np.ndarray:
    r = 6_371_000.0
    la1, lo1 = math.radians(lat), math.radians(lng)
    la2, lo2 = np.radians(lats), np.radians(lngs)
    h = np.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(h))


def unidades_ultra_com_capacidade(
    mapeadas: pd.DataFrame, performance: pd.DataFrame | None
) -> pd.DataFrame:
    """Unidades Ultra com `capacidade_alunos` = alunos REAIS quando houver, NaN no resto.

    O pipeline casa a performance por HEXAGONO (`anexar_oferta_ultra_real`) porque escreve
    por hexagono; aqui o consumo e' por UNIDADE, entao o casamento e' por coordenada
    (<= `_MATCH_ULTRA_M`), com o hexagono como segunda chave para a linha de performance sem
    coordenada (so' quando ha' UMA unidade candidata no hexagono). Linha de performance que
    nao casa com nenhuma unidade mapeada ENTRA como unidade propria: ela existe e tem
    alunos, e descarta-la subestimaria o consumo.
    """
    base = mapeadas.copy()
    if "flag_coord_valida" in base.columns:
        base = base[base["flag_coord_valida"].fillna(True).astype(bool)]
    base["lat"] = pd.to_numeric(base["lat"], errors="coerce")
    base["lng"] = pd.to_numeric(base["lng"], errors="coerce")
    base = base.dropna(subset=["lat", "lng"]).reset_index(drop=True)
    base[COLUNA_CAPACIDADE] = np.nan
    if performance is None or performance.empty or "alunos_total" not in performance.columns:
        return base[["lat", "lng", COLUNA_CAPACIDADE]]

    perf = performance.copy()
    perf["alunos"] = pd.to_numeric(perf["alunos_total"], errors="coerce")
    perf = perf[perf["alunos"].notna() & (perf["alunos"] > 0)]
    sem_coord = pd.Series(np.nan, index=perf.index)
    plat = pd.to_numeric(perf["lat"], errors="coerce") if "lat" in perf.columns else sem_coord
    plng = pd.to_numeric(perf["lng"], errors="coerce") if "lng" in perf.columns else sem_coord

    extras: list[dict[str, float]] = []
    blat, blng = base["lat"].to_numpy(dtype=float), base["lng"].to_numpy(dtype=float)
    hex_base = base["hex_id_res7"].astype("string") if "hex_id_res7" in base.columns else None
    for i, (la, lo) in enumerate(zip(plat, plng, strict=True)):
        alunos = float(perf["alunos"].iloc[i])
        if pd.notna(la) and pd.notna(lo) and len(base):
            d = _dist_m(float(la), float(lo), blat, blng)
            j = int(np.argmin(d))
            if d[j] <= _MATCH_ULTRA_M:
                atual = base.at[j, COLUNA_CAPACIDADE]
                base.at[j, COLUNA_CAPACIDADE] = alunos + (0.0 if pd.isna(atual) else float(atual))
                continue
            extras.append({"lat": float(la), "lng": float(lo), COLUNA_CAPACIDADE: alunos})
            continue
        hx = perf["hex_id_res7"].iloc[i] if "hex_id_res7" in perf.columns else None
        if hex_base is not None and hx is not None and pd.notna(hx):
            cand = base.index[(hex_base == str(hx)) & base[COLUNA_CAPACIDADE].isna()]
            if len(cand) == 1:
                base.at[cand[0], COLUNA_CAPACIDADE] = alunos
    saida = base[["lat", "lng", COLUNA_CAPACIDADE]]
    if extras:
        saida = pd.concat([saida, pd.DataFrame(extras)], ignore_index=True)
    return saida


@lru_cache(maxsize=2)
def carregar_ultra_mercado(staging_dir_str: str) -> pd.DataFrame | None:
    """Unidades Ultra com a capacidade de cada uma. `None` sem o cadastro da rede."""
    staging = Path(staging_dir_str)
    caminho = staging / ARQ_ULTRA
    if not caminho.is_file():
        return None
    try:
        mapeadas = pd.read_parquet(caminho)
        perf_path = staging / ARQ_ULTRA_PERFORMANCE
        perf = pd.read_parquet(perf_path) if perf_path.is_file() else None
        return unidades_ultra_com_capacidade(mapeadas, perf)
    except Exception as exc:  # noqa: BLE001
        _LOG.warning("mercado no raio: cadastro Ultra indisponivel (%r)", exc)
        return None
