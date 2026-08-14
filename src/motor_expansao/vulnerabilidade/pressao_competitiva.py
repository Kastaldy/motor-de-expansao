"""BLK-MA-12: sinal 6 (pressão competitiva) com decaimento explícito por distância.

Calcula, por `hex_id_res7`, quanta concorrência **efetiva** cerca aquele ponto — onde "efetiva"
significa ponderada pela distância, não contada dentro de um raio. Entrega o componente `v6` do §8.1
como **FATO SEM PESO**: ele viaja até a saída, é auditável, e **não entra em `Σ(wi · vi)`**. Ligar o
peso é decisão de gate (§8.3: os pesos são congelados e "só mudam com novo gate"), e o molde de
"fato antes de peso" é o mesmo do `status_churn` (G-D2) e do rating do WellHub (DEC-026).

POR QUE RECALCULAR EM VEZ DE LER `pressao_concorrencial_score_2km`. O §8.1 define
`v6 = pressao_concorrencial_score_2km / 100`, coluna já materializada em
`hexagonos_mercado_mapeado.parquet`. Este módulo reproduz a fórmula daquela coluna, e a prova disso
tem duas metades, ambas medidas em 2026-08-13 sobre os 4.899 hexes da carteira:

  - **Contra o MESMO insumo, é idêntico:** Pearson e Spearman = **1,0000**, mesma média, mesmos 227
    hexes com sinal. A igualdade é o teste da implementação.
  - **Depois de regenerar o insumo, diverge — e é assim que tem de ser:** Pearson **0,9356**. A
    coluna oficial continua calculada sobre 28 redes; este módulo passou a ver 104.

`concorrentes_mapeados.parquet` foi regenerado em 2026-08-13 (28 -> **104** arquivos de rede, 3.179
-> **4.366** pontos válidos, +37,3%), entrando redes inteiras que estavam invisíveis — `skyfit`
sozinha tem 482 unidades. **A camada de mercado NÃO foi recalculada junto** (isso exige
`enriquecimento_espacial_hexagonos`, 213 MB e dezenas de minutos, sobre artefato CRÍTICO), então a
divergência acima é o estado atual e esperado: aqui o número está atualizado, lá não.

O que o recálculo entrega:

  1. **O kernel vira parâmetro em vez de premissa embutida.** Trocar a curva ou o raio é argumento
     de chamada, e o carimbo (`kernel_pressao`, `raio_pressao_m`) viaja na saída — o número passa a
     ser interpretável sem abrir o pipeline de mercado.
  2. **Independência do artefato de 213 MB.** Lê ~350 KB de pontos e serve QUALQUER hex, inclusive
     os de academias fora da malha da carteira — que é o caso do universo de M&A.
  3. **Atualidade.** Ler a coluna materializada congelaria o sinal na última rodada do pipeline de
     mercado; ler os pontos custa 1 s e reflete a coleta mais recente.
  4. **Auditoria do decaimento.** A contagem CRUA viaja ao lado da oferta ponderada, então dá para
     distinguir "pouca gente" de "gente longe" — impossível olhando só o score final.

**COBERTURA — o número que calibra qualquer conversa sobre peso.** Mesmo com o insumo corrigido, só
**268 de 4.899 hexes (5,5%)** da carteira têm pressão positiva. Antes da regeneração eram 227
(4,6%): a defasagem do insumo explicava **cerca de 1 ponto percentual**, não a cobertura baixa. Os
outros ~94% são reais — a maior parte da carteira não tem concorrente de cadeia num raio de 2 km.
Um sinal que é zero em 94% do universo não ordena, ele empata; é por isso que nasce como FATO, para
ser LIDO antes de ser pesado. (E o zero aqui é MEDIÇÃO, não ausência: o universo de pontos é
conhecido. `ler_concorrentes` avisa se o insumo voltar a ficar defasado.)

O DECAIMENTO, e por que ele importa. Contar concorrentes num raio trata quem está a 1,9 km igual a
quem está na porta, e ignora quem está a 2,1 km. Com o kernel triangular do contrato de mercado
(`w = max(0, 1 - d/raio)`), o peso medido por concorrente na carteira real varia de **0,005 a
0,974** (mediana 0,352) — a distância discrimina de fato. O kernel de potência inversa (molde do
Huff) fica disponível como alternativa, mas **não é o default**: o `beta` do Huff é re-calibrado a
cada rodada contra um desfecho observado (β = 1,845 no dimensionamento, β = 0,5 na demanda
revelada — 3,7x de diferença), e o score de vulnerabilidade **não tem desfecho** contra o qual
calibrar (§8: é heurística auditável, não modelo preditivo). Herdar um β sem alvo seria arbitrar
com aparência de calibração.

GRÃO — **corrigido no BLK-MA-14 (DEC-029); o texto anterior estava errado e vale registrar por quê.**
Ele dizia que a pressão é propriedade do HEX e que "calcular por unidade exigiria a coordenada da
academia, que esta camada deliberadamente não persiste". A segunda metade confundia **CALCULAR** com
**PERSISTIR**: a coordenada existe no feed cru e passa pelas mãos do materializador antes de a
projeção das 12 colunas descartá-la — dá para medir a distância a partir dela e devolver só o
agregado, sem que ela toque disco. A frase fechou uma porta que estava aberta, e o sinal ficou um
bloco inteiro no grão errado por causa dela.

O erro não era teórico. Medido em 2026-08-14 sobre 5.823 independentes de SP: erro absoluto médio
**7,82** pontos entre os dois grãos, p90 **22,15**, **máximo 65,97**; amplitude média de **14,89**
pontos DENTRO do mesmo hexágono, apagada por construção; **33%** das academias mudariam de faixa. O
caso que decide: o hexágono `87a812a15ffffff` mede pressão **1,2** e a academia dentro dele, **67,2**
— espremida, aparecendo como território livre.

Hoje os DOIS grãos existem e não são intercambiáveis:

  - `calcular_pressao_por_academia` — mede da coordenada da UNIDADE. É o insumo do `v6` desde o
    BLK-MA-14, porque "independente espremida" (§8.1) é propriedade da academia.
  - `calcular_pressao_por_hex` — mede do centroide do TERRITÓRIO. É a grandeza comparável com o
    `pressao_concorrencial_score_2km` da camada de mercado, e a única que faz sentido pintar num
    mapa. Continua disponível, com `pressao_grao = "hex"` carimbado na saída do score.

O anti-PII segue intacto e agora é EXECUTÁVEL nos dois caminhos: a coordenada entra no cálculo e
`_assert_schema_pressao_academia` barra qualquer tentativa de fazê-la sair.

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
    CONTRATO_COLUNAS_PRESSAO_ACADEMIA,
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


def _pontos_validos(concorrentes: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Coordenadas finitas dos concorrentes com `status_registro == "valido"` (quando existir)."""
    pontos = concorrentes
    if "status_registro" in pontos.columns:
        pontos = pontos[pontos["status_registro"].astype(str) == "valido"]
    lat = pd.to_numeric(pontos["lat"], errors="coerce").to_numpy(dtype="float64")
    lng = pd.to_numeric(pontos["lng"], errors="coerce").to_numpy(dtype="float64")
    finito = np.isfinite(lat) & np.isfinite(lng)
    return lat[finito], lng[finito]


def _oferta_por_origem(
    lat_o: np.ndarray,
    lng_o: np.ndarray,
    lat_c: np.ndarray,
    lng_c: np.ndarray,
    *,
    kernel: str,
    raio_m: float,
    beta: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Núcleo comum aos dois grãos: para cada ORIGEM, a oferta ponderada dos concorrentes.

    A origem é o centroide do hexágono (`calcular_pressao_por_hex`) ou a coordenada da academia
    (`calcular_pressao_por_academia`) — a matemática é a MESMA, e é por isso que ela mora aqui em
    vez de duplicada nas duas. Se o kernel mudasse só num dos caminhos, os dois grãos deixariam de
    ser comparáveis sem ninguém notar.

    Laço por origem, não produto cartesiano completo: 19.329 academias x 4.499 pontos numa matriz
    cheia passaria de 600 MB.
    """
    oferta = np.zeros(len(lat_o), dtype="float64")
    n_no_raio = np.zeros(len(lat_o), dtype="int64")
    dist_min = np.full(len(lat_o), np.nan, dtype="float64")
    if not lat_c.size:
        return oferta, n_no_raio, dist_min

    for i in range(len(lat_o)):
        d = _haversine_m(
            np.full(lat_c.shape, lat_o[i]), np.full(lng_c.shape, lng_o[i]), lat_c, lng_c
        )
        peso = peso_por_distancia(d, kernel=kernel, raio_m=raio_m, beta=beta)
        oferta[i] = float(peso.sum())
        n_no_raio[i] = int((d <= float(raio_m)).sum())
        if d.size:
            dist_min[i] = float(d.min())
    return oferta, n_no_raio, dist_min


def _saturar(oferta: np.ndarray) -> np.ndarray:
    """`oferta -> pressao ∈ [0, 100)`. A saturação do contrato de mercado, num lugar só."""
    return 100.0 * (1.0 - 1.0 / (1.0 + oferta))


def calcular_pressao_por_academia(
    academias: pd.DataFrame,
    concorrentes: pd.DataFrame,
    *,
    kernel: str = PRESSAO_KERNEL_DEFAULT,
    raio_m: float = PRESSAO_RAIO_M,
    beta: float = PRESSAO_BETA_POTENCIA,
) -> pd.DataFrame:
    """Academias com coordenada + pontos de concorrentes -> pressão POR UNIDADE. Função **pura**.

    `academias` precisa de `fonte`, `chave_snapshot`, `lat` e `lng`. **A coordenada entra e não
    sai**: ela é lida para medir a distância e o frame devolvido tem só o agregado
    (`CONTRATO_COLUNAS_PRESSAO_ACADEMIA`), travado pelo `_assert_schema_pressao_academia`.

    POR QUE ESTE GRÃO EXISTE (BLK-MA-14, objeção de Vinicius em 2026-08-14). O §8.1 dizia
    "independente espremida", que é propriedade da ACADEMIA, mas media a distância a partir do
    **centroide do hexágono** — e todas as academias do mesmo hex empatavam por construção (medido:
    `0 de 6.753` hexes com qualquer variação interna). O erro não é acadêmico: sobre 5.823
    independentes de SP, o erro absoluto médio é **7,82** pontos, o p90 **22,15** e o **máximo
    65,97**; 33% das academias mudariam de faixa. O pior caso medido é a refutação da defesa "mas a
    correlação é 0,92": o hexágono `87a812a15ffffff` marca pressão **1,2** e a academia dentro dele
    tem **67,2** — uma unidade espremida aparecendo como território livre, que é exatamente o falso
    negativo que o sinal existe para não produzir.

    A fórmula é a MESMA do grão hex (`_oferta_por_origem` + `_saturar`); o que muda é a ORIGEM da
    medição. Isso é deliberado: os dois números continuam na mesma régua e comparáveis.
    """
    if kernel not in KERNEIS_PRESSAO:
        raise ValueError(f"kernel fora de {sorted(KERNEIS_PRESSAO)}: {kernel!r}")
    faltando = [c for c in ("fonte", "chave_snapshot", "lat", "lng") if c not in academias.columns]
    if faltando:
        raise ValueError(f"frame de academias sem coluna(s) obrigatoria(s): {faltando}")

    base = academias.copy()
    base["lat"] = pd.to_numeric(base["lat"], errors="coerce")
    base["lng"] = pd.to_numeric(base["lng"], errors="coerce")
    # Coordenada ausente/inválida é DESCARTADA com aviso, nunca imputada: sem origem não há
    # distância, e um `0` ali afirmaria "ninguém espremendo" — a leitura mais otimista da régua.
    invalidas = int((~np.isfinite(base["lat"]) | ~np.isfinite(base["lng"])).sum())
    if invalidas:
        _logger.warning("academia sem coordenada valida, fora do calculo de pressao: %d", invalidas)
    base = base[np.isfinite(base["lat"]) & np.isfinite(base["lng"])]
    if base.empty:
        return pd.DataFrame(
            {c: pd.Series(dtype=d) for c, d in CONTRATO_COLUNAS_PRESSAO_ACADEMIA.items()}
        )
    if bool(base.duplicated(subset=["fonte", "chave_snapshot"]).any()):
        raise ValueError("frame de academias com `(fonte, chave_snapshot)` duplicado")

    lat_c, lng_c = _pontos_validos(concorrentes)
    oferta, n_no_raio, dist_min = _oferta_por_origem(
        base["lat"].to_numpy(dtype="float64"),
        base["lng"].to_numpy(dtype="float64"),
        lat_c,
        lng_c,
        kernel=kernel,
        raio_m=raio_m,
        beta=beta,
    )
    pressao = _saturar(oferta)

    out = pd.DataFrame(
        {
            "fonte": base["fonte"].astype("string").to_numpy(),
            "chave_snapshot": base["chave_snapshot"].astype("string").to_numpy(),
            "pressao_competitiva": pd.Series(pressao, dtype="float64"),
            "v6": pd.Series(pressao / 100.0, dtype="float64"),
            "oferta_ponderada": pd.Series(oferta, dtype="float64"),
            "n_concorrentes_no_raio": pd.Series(n_no_raio, dtype="int64"),
            "dist_concorrente_mais_proximo_m": pd.Series(dist_min, dtype="float64"),
            "kernel_pressao": pd.Series([str(kernel)] * len(base), dtype="string"),
            "raio_pressao_m": pd.Series([float(raio_m)] * len(base), dtype="float64"),
            "versao_contrato": pd.Series([VERSAO_CONTRATO_PRESSAO] * len(base), dtype="string"),
        }
    )
    for coluna, dtype in CONTRATO_COLUNAS_PRESSAO_ACADEMIA.items():
        out[coluna] = out[coluna].astype(dtype)
    _assert_schema_pressao_academia(out)
    return out


def _assert_schema_pressao_academia(df: pd.DataFrame) -> None:
    """Contrato do grão academia + a trava anti-PII, que aqui é o ponto todo.

    A coordenada ENTRA nesta função e não pode sair dela. Este guard é o que transforma essa frase
    em código — sem ele, "a camada não persiste coordenada" voltaria a ser prosa.
    """
    esperado = list(CONTRATO_COLUNAS_PRESSAO_ACADEMIA.keys())
    if list(df.columns) != esperado:
        raise AssertionError(f"frame de pressao por academia fora do contrato: {list(df.columns)}")
    vazando = sorted(set(df.columns) & _COLUNAS_PROIBIDAS_SAIDA)
    if vazando:
        raise AssertionError(f"coordenada/identidade na saida da pressao (anti-PII): {vazando}")
    if df.empty:
        return
    if bool(df.duplicated(subset=["fonte", "chave_snapshot"]).any()):
        raise AssertionError("`(fonte, chave_snapshot)` duplicado no frame de pressao")
    v6 = pd.to_numeric(df["v6"], errors="coerce")
    if bool(((v6 < 0.0) | (v6 >= 1.0)).any()):
        raise AssertionError("`v6` fora de [0, 1)")
    if bool((pd.to_numeric(df["oferta_ponderada"], errors="coerce") < 0.0).any()):
        raise AssertionError("`oferta_ponderada` negativa")


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

    lat_c, lng_c = _pontos_validos(concorrentes)
    # MESMO núcleo do grão academia: se as duas fórmulas divergirem, os dois números deixam de ser
    # comparáveis e ninguém percebe — o kernel e a saturação vivem num lugar só de propósito.
    oferta, n_no_raio, dist_min = _oferta_por_origem(
        lat_h, lng_h, lat_c, lng_c, kernel=kernel, raio_m=raio_m, beta=beta
    )
    pressao = _saturar(oferta)

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
    "calcular_pressao_por_academia",
    "calcular_pressao_por_hex",
    "ler_concorrentes",
    "peso_por_distancia",
]
