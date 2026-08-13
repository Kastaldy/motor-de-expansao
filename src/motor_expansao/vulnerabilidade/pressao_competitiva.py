"""BLK-MA-12: sinal 6 (pressão competitiva) com decaimento explícito por distância.

Calcula, por `hex_id_res7`, quanta concorrência **efetiva** cerca aquele ponto — onde "efetiva"
significa ponderada pela distância, não contada dentro de um raio. Entrega o componente `v6` do §8.1
como **FATO SEM PESO**: ele viaja até a saída, é auditável, e **não entra em `Σ(wi · vi)`**. Ligar o
peso é decisão de gate (§8.3: os pesos são congelados e "só mudam com novo gate"), e o molde de
"fato antes de peso" é o mesmo do `status_churn` (G-D2) e do rating do WellHub (DEC-026).

POR QUE RECALCULAR EM VEZ DE LER `pressao_concorrencial_score_2km`. O §8.1 define
`v6 = pressao_concorrencial_score_2km / 100`, coluna já materializada em
`hexagonos_mercado_mapeado.parquet`. Este módulo reproduz essa coluna e foi **medido contra ela em
2026-08-13: Pearson e Spearman = 1,0000 sobre os 4.899 hexes da carteira, mesma média, mesmos 227
hexes com sinal.** Mesma fórmula, mesmo kernel, mesmo raio — a igualdade é o teste, não a
coincidência.

**O que o recálculo NÃO conserta, e é preciso dizer alto:** ele NÃO atualiza o insumo. Os dois
caminhos leem o MESMO `concorrentes_mapeados.parquet`, que está defasado — gerado de **28** arquivos
de rede quando `concorrentes/unidades_*.csv` tem **104** em disco (medido 2026-08-13). São ~76 redes
invisíveis, e o efeito não é ruído neutro: onde falta coleta a pressão sai **zero**, que na régua do
§8.1 é a afirmação "não há concorrência espremendo" — a mais otimista possível. Corrigir isso é
regenerar o parquet de pontos com `normalizar_concorrentes`, fora do escopo deste módulo; o que ele
faz é **avisar** (ver `ler_concorrentes`) em vez de deixar o zero passar calado.

O que o recálculo entrega de fato:

  1. **O kernel vira parâmetro em vez de premissa embutida.** Trocar a curva ou o raio é argumento
     de chamada, e o carimbo (`kernel_pressao`, `raio_pressao_m`) viaja na saída — o número passa a
     ser interpretável sem abrir o pipeline de mercado.
  2. **Independência do artefato de 213 MB.** Lê 255 KB de pontos e serve QUALQUER hex, inclusive os
     de academias fora da malha da carteira — que é o caso do universo de M&A.
  3. **Auditoria do decaimento.** A contagem CRUA viaja ao lado da oferta ponderada, então dá para
     distinguir "pouca gente" de "gente longe" — impossível olhando só o score final.

**Cobertura, para calibrar expectativa antes de qualquer peso:** no recorte da carteira só
**227 de 4.899 hexes (4,6%)** têm pressão positiva. Um sinal que é zero em 95,4% do universo não
ordena nada, e parte desses zeros é a defasagem acima. É por isso que ele nasce como FATO, para ser
LIDO antes de ser pesado.

O DECAIMENTO, e por que ele importa. Contar concorrentes num raio trata quem está a 1,9 km igual a
quem está na porta, e ignora quem está a 2,1 km. Com o kernel triangular do contrato de mercado
(`w = max(0, 1 - d/raio)`), o peso medido por concorrente na carteira real varia de **0,005 a
0,974** (mediana 0,352) — a distância discrimina de fato. O kernel de potência inversa (molde do
Huff) fica disponível como alternativa, mas **não é o default**: o `beta` do Huff é re-calibrado a
cada rodada contra um desfecho observado (β = 1,845 no dimensionamento, β = 0,5 na demanda
revelada — 3,7x de diferença), e o score de vulnerabilidade **não tem desfecho** contra o qual
calibrar (§8: é heurística auditável, não modelo preditivo). Herdar um β sem alvo seria arbitrar
com aparência de calibração.

GRÃO — a ressalva que acompanha o sinal: a pressão é propriedade do **HEX**, não da academia. Todas
as academias do mesmo hex recebem o mesmo `v6`. Diferente do `v1` (onde a emenda BLK-MA-03 registrou
esse viés como desconfortável), aqui a grandeza **é** intrínseca ao território — como a hotness do
§9/D5 —, então propagar por hex é fiel ao que se mede. Calcular por unidade exigiria a coordenada da
academia, que esta camada deliberadamente **não persiste** (anti-PII, §11/DEC-012); do centroide do
hex, o resultado seria idêntico para todas as academias do hex de qualquer forma. O sufixo `_no_hex`
carrega a ressalva até o consumidor.

GUARDRAILS: READ-ONLY sobre o M1 e sobre a camada de mercado (lê pontos, nunca reescreve); anti-PII
(entra coordenada de ESTABELECIMENTO COMERCIAL já versionada em `data/staging`, sai só agregado por
hex — nenhuma coordenada e nenhum nome cruzam a fronteira de saída); sem dependência pesada (só
`numpy`/`pandas`/`h3`, nada de `geopandas`/`shapely`/`sklearn`).
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from pathlib import Path

import h3
import numpy as np
import pandas as pd

from .contrato import (
    CONTRATO_COLUNAS_PRESSAO,
    KERNEIS_PRESSAO,
    PRESSAO_BETA_POTENCIA,
    PRESSAO_DIST_MIN_M,
    PRESSAO_KERNEL_DEFAULT,
    PRESSAO_RAIO_M,
    VERSAO_CONTRATO_PRESSAO,
)

_logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[3]
CONCORRENTES_PATH_DEFAULT = ROOT / "data" / "staging" / "concorrentes_mapeados.parquet"

_RAIO_TERRA_M = 6_371_008.8

# Colunas que NUNCA podem sair deste módulo: a entrada tem coordenada, a saída não.
_COLUNAS_PROIBIDAS_SAIDA: frozenset[str] = frozenset(
    {"lat", "lng", "latitude", "longitude", "nome", "nome_unidade", "concorrente_id"}
)


def _haversine_m(
    lat1: np.ndarray, lng1: np.ndarray, lat2: np.ndarray, lng2: np.ndarray
) -> np.ndarray:
    """Distância geodésica em metros, vetorizada. Sem `geopandas`, sem `pyproj`."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp = p2 - p1
    dl = np.radians(lng2) - np.radians(lng1)
    a = np.sin(dp / 2.0) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2.0) ** 2
    return 2.0 * _RAIO_TERRA_M * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def peso_por_distancia(
    dist_m: np.ndarray,
    *,
    kernel: str = PRESSAO_KERNEL_DEFAULT,
    raio_m: float = PRESSAO_RAIO_M,
    beta: float = PRESSAO_BETA_POTENCIA,
) -> np.ndarray:
    """Distâncias (m) -> peso em `[0, 1]`. É AQUI que o decaimento vive, e ele é explícito.

    | kernel | fórmula | onde já é usado no repo |
    |---|---|---|
    | `linear` | `max(0, 1 - d/raio)` | contrato da camada de mercado (o `pressao_..._2km`) |
    | `potencia` | `(d_min/max(d, d_min))^beta`, zerado fora do raio | molde do Huff |

    O `linear` é o **default** de propósito: é o kernel que a camada de mercado já usa, então o
    número sai comparável com `pressao_concorrencial_score_2km`. O `potencia` existe para quem
    quiser testar sensibilidade, e vem normalizado para `1.0` na distância mínima — sem isso ele
    explodiria perto de zero e deixaria de ser um peso.

    Fora do raio o peso é **exatamente zero** nos dois kernels: o raio é truncamento computacional,
    e quem define o alcance efetivo é a forma da curva, não o corte.
    """
    if kernel not in KERNEIS_PRESSAO:
        raise ValueError(f"kernel fora de {sorted(KERNEIS_PRESSAO)}: {kernel!r}")
    d = np.asarray(dist_m, dtype="float64")
    dentro = d <= float(raio_m)
    if kernel == "linear":
        peso = np.maximum(0.0, 1.0 - d / float(raio_m))
    else:
        piso = np.maximum(d, float(PRESSAO_DIST_MIN_M))
        peso = (float(PRESSAO_DIST_MIN_M) / piso) ** float(beta)
    return np.where(dentro, peso, 0.0)


def _centroides(hexes: Iterable[str]) -> tuple[list[str], np.ndarray, np.ndarray]:
    """Hexes -> (validos, lat, lng) do centroide. Hex inválido é descartado com aviso."""
    validos: list[str] = []
    lats: list[float] = []
    lngs: list[float] = []
    invalidos = 0
    for hex_id in hexes:
        texto = str(hex_id)
        if not texto or not h3.is_valid_cell(texto):
            invalidos += 1
            continue
        lat, lng = h3.cell_to_latlng(texto)
        validos.append(texto)
        lats.append(float(lat))
        lngs.append(float(lng))
    if invalidos:
        _logger.warning("hex ignorado por `hex_id` invalido no calculo de pressao: %d", invalidos)
    return validos, np.asarray(lats, dtype="float64"), np.asarray(lngs, dtype="float64")


def calcular_pressao_por_hex(
    hexes: Iterable[str],
    concorrentes: pd.DataFrame,
    *,
    kernel: str = PRESSAO_KERNEL_DEFAULT,
    raio_m: float = PRESSAO_RAIO_M,
    beta: float = PRESSAO_BETA_POTENCIA,
) -> pd.DataFrame:
    """Hexes + pontos de concorrentes -> pressão competitiva por hex. Função **pura**.

    A saturação é a MESMA do contrato de mercado, para o número ficar comparável:

        oferta = Σ_c peso(d(hex, c))
        gap    = 1 / (1 + oferta)
        pressao = 100 · (1 - gap)          ∈ [0, 100)
        v6      = pressao / 100            ∈ [0, 1)

    `gap` decresce com a oferta, logo `pressao` CRESCE com a concorrência — a direção que o §8.1
    exige (`↑ = ↑ vulnerabilidade`). Hex sem concorrente algum no raio sai com `oferta = 0` e
    portanto `pressao = 0`: aqui, e só aqui, o zero é uma medição e não uma ausência, porque o
    universo de pontos é conhecido. **Se o insumo de pontos estiver defasado, esse zero passa a ser
    mentira** — daí a auditoria devolver `n_concorrentes_considerados`.
    """
    validos, lat_h, lng_h = _centroides(hexes)
    if not validos:
        return pd.DataFrame(
            {col: pd.Series(dtype=dtype) for col, dtype in CONTRATO_COLUNAS_PRESSAO.items()}
        )

    pontos = concorrentes
    if "status_registro" in pontos.columns:
        pontos = pontos[pontos["status_registro"].astype(str) == "valido"]
    lat_c = pd.to_numeric(pontos["lat"], errors="coerce").to_numpy(dtype="float64")
    lng_c = pd.to_numeric(pontos["lng"], errors="coerce").to_numpy(dtype="float64")
    finito = np.isfinite(lat_c) & np.isfinite(lng_c)
    lat_c, lng_c = lat_c[finito], lng_c[finito]

    oferta = np.zeros(len(validos), dtype="float64")
    n_no_raio = np.zeros(len(validos), dtype="int64")
    dist_min = np.full(len(validos), np.nan, dtype="float64")

    if lat_c.size:
        # Laço por HEX (não produto cartesiano completo de uma vez): 4.899 x 3.179 caberia, mas o
        # universo real de academias é ~50k hexes e a matriz cheia passaria de 1 GB.
        for i in range(len(validos)):
            d = _haversine_m(
                np.full(lat_c.shape, lat_h[i]), np.full(lng_c.shape, lng_h[i]), lat_c, lng_c
            )
            peso = peso_por_distancia(d, kernel=kernel, raio_m=raio_m, beta=beta)
            oferta[i] = float(peso.sum())
            dentro = d <= float(raio_m)
            n_no_raio[i] = int(dentro.sum())
            if d.size:
                dist_min[i] = float(d.min())

    gap = 1.0 / (1.0 + oferta)
    pressao = 100.0 * (1.0 - gap)

    out = pd.DataFrame(
        {
            "hex_id_res7": pd.Series(validos, dtype="string"),
            "pressao_competitiva_no_hex": pd.Series(pressao, dtype="float64"),
            "v6_no_hex": pd.Series(pressao / 100.0, dtype="float64"),
            "oferta_ponderada_no_hex": pd.Series(oferta, dtype="float64"),
            "n_concorrentes_no_raio": pd.Series(n_no_raio, dtype="int64"),
            "dist_concorrente_mais_proximo_m": pd.Series(dist_min, dtype="float64"),
            "kernel_pressao": pd.Series([str(kernel)] * len(validos), dtype="string"),
            "raio_pressao_m": pd.Series([float(raio_m)] * len(validos), dtype="float64"),
            "versao_contrato": pd.Series([VERSAO_CONTRATO_PRESSAO] * len(validos), dtype="string"),
        }
    )
    _assert_schema_pressao(out)
    return out


def _assert_schema_pressao(df: pd.DataFrame) -> None:
    """Falha alto fora do contrato, e barra qualquer coordenada na saída (anti-PII)."""
    esperado = list(CONTRATO_COLUNAS_PRESSAO.keys())
    if list(df.columns) != esperado:
        raise AssertionError(f"frame de pressao fora do contrato: {list(df.columns)}")
    vazando = sorted(set(df.columns) & _COLUNAS_PROIBIDAS_SAIDA)
    if vazando:
        raise AssertionError(f"coordenada/identidade na saida da pressao (anti-PII): {vazando}")
    if df.empty:
        return
    if bool(df["hex_id_res7"].duplicated().any()):
        raise AssertionError("`hex_id_res7` duplicado no frame de pressao")
    v6 = pd.to_numeric(df["v6_no_hex"], errors="coerce")
    if bool(((v6 < 0.0) | (v6 >= 1.0)).any()):
        raise AssertionError("`v6_no_hex` fora de [0, 1)")
    if bool((pd.to_numeric(df["oferta_ponderada_no_hex"], errors="coerce") < 0.0).any()):
        raise AssertionError("`oferta_ponderada_no_hex` negativa")
    if bool((pd.to_numeric(df["n_concorrentes_no_raio"], errors="coerce") < 0).any()):
        raise AssertionError("`n_concorrentes_no_raio` negativo")


def ler_concorrentes(caminho: Path = CONCORRENTES_PATH_DEFAULT) -> pd.DataFrame:
    """Lê os pontos de concorrentes e AVISA se o insumo estiver defasado.

    O aviso não é decorativo: onde falta coleta, a pressão sai `0`, que é a leitura mais otimista
    possível na régua do §8.1. Um sinal silenciosamente zerado por defasagem de insumo é pior que
    sinal ausente, porque `0` afirma e ausência não.
    """
    if not caminho.exists():
        raise FileNotFoundError(f"pontos de concorrentes nao encontrados: {caminho}")
    df = pd.read_parquet(caminho)
    if "arquivo_origem" in df.columns:
        redes_no_parquet = int(df["arquivo_origem"].nunique())
        csvs = list((ROOT / "concorrentes").glob("unidades_*.csv"))
        if csvs and len(csvs) > redes_no_parquet:
            _logger.warning(
                "insumo de concorrentes DEFASADO: o parquet cobre %d arquivo(s) de rede e ha %d "
                "CSV(s) em disco. Onde falta coleta a pressao sai ZERO, que e' a leitura mais "
                "otimista. Regenerar com `normalizar_concorrentes` antes de pesar o sinal.",
                redes_no_parquet,
                len(csvs),
            )
    return df


__all__ = [
    "CONCORRENTES_PATH_DEFAULT",
    "calcular_pressao_por_hex",
    "ler_concorrentes",
    "peso_por_distancia",
]
