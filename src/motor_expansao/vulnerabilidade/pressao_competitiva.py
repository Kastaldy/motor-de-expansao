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
import math
from collections.abc import Iterable
from pathlib import Path
from typing import NamedTuple

import h3
import numpy as np
import pandas as pd

from .contrato import (
    CONTRATO_COLUNAS_PRESSAO,
    CONTRATO_COLUNAS_PRESSAO_ACADEMIA,
    DEDUP_CADEIA_FEED_M,
    DEDUP_CADEIA_FEED_PISO_M,
    DEDUP_H3_RES,
    DEDUP_INDEPENDENTES_M,
    DEDUP_K_MARGEM_ANEIS,
    DEDUP_NOME_H3_RES,
    KERNEIS_PRESSAO,
    PESO_OFERTA_CADEIA,
    PESO_OFERTA_INDEPENDENTE,
    PRESSAO_BETA_POTENCIA,
    PRESSAO_DIST_MIN_M,
    PRESSAO_KERNEL_DEFAULT,
    PRESSAO_RAIO_M,
    UNIVERSO_OFERTA_CADEIAS,
    UNIVERSO_OFERTA_COM_INDEPENDENTES,
    UNIVERSOS_OFERTA,
    VERSAO_CONTRATO_PRESSAO,
)
from .identidade import DIST_MAX_MESMO_NOME_M, mesma_unidade

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


def _pontos_validos_frame(concorrentes: pd.DataFrame) -> pd.DataFrame:
    """Pontos com `status_registro == "valido"` e coordenada finita -> frame `[lat, lng, rede]`.

    Extraído de `_pontos_validos` no BLK-MA-17 porque a dedup contra o feed do agregador precisa da
    `rede`, que a tupla de arrays descarta. `_pontos_validos` delega e continua devolvendo a tupla,
    então nenhum chamador antigo muda.

    **É contra ESTE frame que a dedup casa, nunca contra o parquet cru.** A diferença não é de
    estilo: um ponto `descartado_duplicado`/`descartado_coord` não entra na oferta, então deixá-lo
    absorver uma unidade do feed apagaria concorrência real com base num ponto que ninguém está
    contando — o falso zero de novo, por outra porta.

    `rede` ausente no insumo vira `<NA>`: a coluna existe sempre, e o casamento por rede
    simplesmente nunca dispara (o piso de distância pura continua valendo).
    """
    pontos = concorrentes
    if "status_registro" in pontos.columns:
        pontos = pontos[pontos["status_registro"].astype(str) == "valido"]
    lat = pd.to_numeric(pontos["lat"], errors="coerce").to_numpy(dtype="float64")
    lng = pd.to_numeric(pontos["lng"], errors="coerce").to_numpy(dtype="float64")
    if "rede" in pontos.columns:
        rede = pontos["rede"].astype("string").to_numpy()
    else:
        rede = np.full(len(lat), pd.NA, dtype="object")
    # `nome` (BLK-MA-17-FU4): a dedup por distancia pura deixava passar 407 duplicatas entre 150 m
    # e 1 km -- a mesma academia geocodificada diferente pelas duas fontes. Quem as separa de uma
    # academia irma de verdade e' o NOME, e para compara-lo ele precisa chegar ate' aqui.
    if "nome_unidade" in pontos.columns:
        nome = pontos["nome_unidade"].astype("string").to_numpy()
    elif "nome" in pontos.columns:
        nome = pontos["nome"].astype("string").to_numpy()
    else:
        nome = np.full(len(lat), pd.NA, dtype="object")
    finito = np.isfinite(lat) & np.isfinite(lng)
    return pd.DataFrame(
        {
            "lat": pd.Series(lat[finito], dtype="float64"),
            "lng": pd.Series(lng[finito], dtype="float64"),
            "rede": pd.Series(rede[finito], dtype="string"),
            "nome": pd.Series(nome[finito], dtype="string"),
        }
    )


def _pontos_validos(concorrentes: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Coordenadas finitas dos concorrentes com `status_registro == "valido"` (quando existir)."""
    frame = _pontos_validos_frame(concorrentes)
    return (
        frame["lat"].to_numpy(dtype="float64"),
        frame["lng"].to_numpy(dtype="float64"),
    )


def _k_do_bucket(distancia_m: float, *, resolucao: int = DEDUP_H3_RES) -> int:
    """Raio de `grid_disk` (em anéis) que cobre `distancia_m` na `resolucao` dada.

    **É o erro silencioso mais provável de qualquer dedup com bucket H3**, e por isso ele é
    derivado em vez de cravado: `DEDUP_H3_RES = 11` tem aresta média de ~29 m, então `grid_disk(1)`
    cobre ~50 m e **não** cobre 150 m. Um `k` fixo herdado da dedup de independentes faria a busca
    simplesmente não achar o vizinho — a dedup deixaria de deduplicar, sem levantar nada.

    A conta, num reticulado hexagonal de aresta `e` (= circunraio) e passo entre centros
    `s = e·√3`: dois pontos a `d` metros estão em células cujos CENTROS distam no máximo `d + 2e`
    (cada ponto está a até `e` do seu centro); e toda célula com centro a até `k·s·√3/2 = k·1,5·e`
    está dentro de `grid_disk(k)`. Logo `k >= (d + 2e) / (1,5·e)`, mais `DEDUP_K_MARGEM_ANEIS` de
    folga porque as células do H3 não são hexágonos regulares idênticos.

    Travado por teste de EQUIVALÊNCIA contra a varredura completa — a única forma de provar que a
    otimização não mudou resultado.
    """
    aresta = float(h3.average_hexagon_edge_length(int(resolucao), unit="m"))
    minimo = math.ceil((float(distancia_m) + 2.0 * aresta) / (1.5 * aresta))
    return max(1, minimo + int(DEDUP_K_MARGEM_ANEIS))


class _OfertaPorOrigem(NamedTuple):
    """O que `_oferta_por_origem` devolve, decomposto por tipo e por procedência do ponto.

    `oferta_independentes`/`n_independentes_no_raio` são a decomposição por TIPO (BLK-MA-16);
    `oferta_cadeias_feed`/`n_cadeias_feed_no_raio`, a decomposição por PROCEDÊNCIA dentro do bloco
    de cadeias (BLK-MA-17). Os dois recortes são independentes e nenhum é subconjunto do outro.
    """

    oferta_total: np.ndarray
    oferta_independentes: np.ndarray
    n_no_raio: np.ndarray
    n_independentes_no_raio: np.ndarray
    dist_min: np.ndarray
    oferta_cadeias_feed: np.ndarray
    n_cadeias_feed_no_raio: np.ndarray


def _oferta_por_origem(
    lat_o: np.ndarray,
    lng_o: np.ndarray,
    lat_c: np.ndarray,
    lng_c: np.ndarray,
    *,
    kernel: str,
    raio_m: float,
    beta: float,
    lat_i: np.ndarray | None = None,
    lng_i: np.ndarray | None = None,
    peso_independente: float = PESO_OFERTA_INDEPENDENTE,
    auto_pos: np.ndarray | None = None,
    cadeia_do_feed: np.ndarray | None = None,
    auto_pos_cadeia: np.ndarray | None = None,
) -> _OfertaPorOrigem:
    """Núcleo comum aos dois grãos: para cada ORIGEM, a oferta ponderada dos concorrentes.

    A origem é o centroide do hexágono (`calcular_pressao_por_hex`) ou a coordenada da academia
    (`calcular_pressao_por_academia`) — a matemática é a MESMA, e é por isso que ela mora aqui em
    vez de duplicada nas duas. Se o kernel mudasse só num dos caminhos, os dois grãos deixariam de
    ser comparáveis sem ninguém notar.

    DOIS CONJUNTOS DE PONTOS, DOIS PESOS (BLK-MA-16). As cadeias entram com `PESO_OFERTA_CADEIA`;
    as independentes (`lat_i`/`lng_i`, opcionais) com `peso_independente` — `0,5` por decisão de
    produto. O peso multiplica o do decaimento, ou seja, age no NUMERADOR da oferta, antes da
    saturação. Sem `lat_i`, o comportamento é byte a byte o de antes do bloco.

    UM BLOCO DE CADEIAS, DUAS PROCEDÊNCIAS (BLK-MA-17). `lat_c`/`lng_c` já chegam CONCATENADOS —
    os pontos de `concorrentes_mapeados` seguidos das unidades de rede do agregador que sobreviveram
    à dedup. Todas com `PESO_OFERTA_CADEIA`, porque todas são unidades de rede: `cadeia_do_feed` é
    uma máscara booleana sobre esse array e serve **só para decompor a saída**, nunca para pesar
    diferente. Manter um array só é o que garante que a aritmética do total não dependa da
    procedência.

    `auto_pos[i]` é a posição da ORIGEM `i` dentro do conjunto de independentes, ou `-1`. Existe
    porque no grão academia a origem **é um dos pontos**: sem zerar essa parcela, cada academia
    receberia `peso(d = 0) x 0,5 = 0,5` de oferta de si mesma — `sat(0,5) = 33,3` pontos de pressão
    fantasma em quem não tem mais ninguém por perto, justamente nos casos que o sinal existe para
    distinguir. A exclusão é POR POSIÇÃO (derivada da chave), nunca por distância zero: duas
    academias no mesmo endereço existem, e são duas linhas.

    `auto_pos_cadeia[i]` é o MESMO mecanismo do lado das cadeias, e o erro que ele evita é o dobro
    do outro: peso `1,0` em vez de `0,5`, isto é `sat(1,0) = 50,0` pontos de pressão fantasma. Ele
    cobre os DOIS casos — a unidade de rede que sobreviveu à dedup (a posição é a dela própria) e a
    que colapsou (a posição é a do ponto do parquet que a absorveu, e sem isso ela se
    auto-pressionaria através do próprio pin do funil).

    Laço por origem, não produto cartesiano completo: 19.329 academias x 23.828 pontos numa matriz
    cheia passaria de 3 GB.
    """
    n_origens = len(lat_o)
    oferta = np.zeros(n_origens, dtype="float64")
    oferta_ind = np.zeros(n_origens, dtype="float64")
    n_no_raio = np.zeros(n_origens, dtype="int64")
    n_ind_no_raio = np.zeros(n_origens, dtype="int64")
    dist_min = np.full(n_origens, np.nan, dtype="float64")
    oferta_feed = np.zeros(n_origens, dtype="float64")
    n_feed_no_raio = np.zeros(n_origens, dtype="int64")

    tem_indep = lat_i is not None and lng_i is not None and len(lat_i) > 0
    vazio = _OfertaPorOrigem(
        oferta, oferta_ind, n_no_raio, n_ind_no_raio, dist_min, oferta_feed, n_feed_no_raio
    )
    if not lat_c.size and not tem_indep:
        return vazio

    for i in range(n_origens):
        distancias: list[np.ndarray] = []
        if lat_c.size:
            d_c = _haversine_m(
                np.full(lat_c.shape, lat_o[i]), np.full(lng_c.shape, lng_o[i]), lat_c, lng_c
            )
            peso_c = peso_por_distancia(d_c, kernel=kernel, raio_m=raio_m, beta=beta)
            dentro_c = d_c <= float(raio_m)
            proprio_c = int(auto_pos_cadeia[i]) if auto_pos_cadeia is not None else -1
            if proprio_c >= 0:
                # Mesmo tratamento das linhas do bloco de independentes: zera a parcela, a contagem
                # E a distância da própria unidade, senão `dist_concorrente_mais_proximo_m` sairia
                # `0,0` para toda unidade de rede que estivesse no conjunto de pontos.
                peso_c = peso_c.copy()
                peso_c[proprio_c] = 0.0
                dentro_c = dentro_c.copy()
                dentro_c[proprio_c] = False
                d_c = d_c.copy()
                d_c[proprio_c] = np.inf
            contribuicao_c = peso_c * PESO_OFERTA_CADEIA
            oferta[i] += float(contribuicao_c.sum())
            n_no_raio[i] += int(dentro_c.sum())
            if cadeia_do_feed is not None:
                oferta_feed[i] = float(contribuicao_c[cadeia_do_feed].sum())
                n_feed_no_raio[i] = int(dentro_c[cadeia_do_feed].sum())
            distancias.append(d_c)

        if tem_indep:
            d_i = _haversine_m(
                np.full(lat_i.shape, lat_o[i]),  # type: ignore[union-attr]
                np.full(lng_i.shape, lng_o[i]),  # type: ignore[union-attr]
                lat_i,  # type: ignore[arg-type]
                lng_i,  # type: ignore[arg-type]
            )
            peso_i = peso_por_distancia(d_i, kernel=kernel, raio_m=raio_m, beta=beta)
            dentro_i = d_i <= float(raio_m)
            proprio = int(auto_pos[i]) if auto_pos is not None else -1
            if proprio >= 0:
                # Zera a parcela E a distância da própria academia, para ela não contaminar nem a
                # oferta nem o `dist_concorrente_mais_proximo_m` (que sairia sempre `0,0`).
                peso_i = peso_i.copy()
                peso_i[proprio] = 0.0
                dentro_i = dentro_i.copy()
                dentro_i[proprio] = False
                d_i = d_i.copy()
                d_i[proprio] = np.inf
            parcela = float((peso_i * float(peso_independente)).sum())
            oferta[i] += parcela
            oferta_ind[i] = parcela
            n_ind_no_raio[i] = int(dentro_i.sum())
            n_no_raio[i] += n_ind_no_raio[i]
            distancias.append(d_i)

        # `default` em vez de `if distancias`: com a auto-exclusão a única distância pode ter
        # virado `inf` (a própria academia), e um gerador vazio faria `min()` levantar. `NaN`
        # aqui significa "não havia de quem medir" — que é o mesmo que a função já devolvia.
        menor = min((float(d.min()) for d in distancias if d.size), default=float("inf"))
        dist_min[i] = menor if np.isfinite(menor) else np.nan
    return _OfertaPorOrigem(
        oferta, oferta_ind, n_no_raio, n_ind_no_raio, dist_min, oferta_feed, n_feed_no_raio
    )


def _saturar(oferta: np.ndarray) -> np.ndarray:
    """`oferta -> pressao ∈ [0, 100)`. A saturação do contrato de mercado, num lugar só."""
    return 100.0 * (1.0 - 1.0 / (1.0 + oferta))


def dedup_independentes(
    independentes: pd.DataFrame, *, distancia_m: float = DEDUP_INDEPENDENTES_M
) -> tuple[pd.DataFrame, dict[tuple[str, str], int]]:
    """Colapsa a MESMA academia listada em fontes diferentes. Devolve `(pontos, posicao_por_chave)`.

    O DEFEITO QUE ELA FECHA, e por que ele é invisível hoje. A chave de churn embute a `fonte`
    (§8.1, emenda BLK-MA-03), então a mesma academia em TotalPass e WellHub é **sempre duas
    linhas**. Somando as duas como oferta, toda academia listada nos dois apps pressiona em dobro —
    erro sistemático, em massa, e silencioso. Em 2026-08-14 o snapshot só tem WellHub, então **este
    código não muda nenhum número hoje**: ele existe para o defeito não entrar junto com a primeira
    coleta que trouxer as duas fontes.

    O CRITÉRIO É ARBITRADO, não medido — não há par TP x WH nesta estação para calibrar (ver
    `DEDUP_INDEPENDENTES_M`). Distância pura, e só entre fontes DIFERENTES: duas linhas da MESMA
    fonte a 40 m são duas academias (a chave já é única por fonte), enquanto duas linhas de fontes
    distintas a 40 m são, muito provavelmente, uma só vista duas vezes.

    O sobrevivente é o **primeiro em ordem `(fonte, chave_snapshot)`** — determinismo por
    construção, para a mesma entrada dar o mesmo artefato em qualquer máquina.

    O segundo elemento do retorno mapeia **toda** chave de entrada (inclusive as colapsadas) para a
    posição do seu representante no frame devolvido. É ele que permite ao chamador excluir a
    própria academia da própria oferta mesmo quando ela foi a linha absorvida.
    """
    colunas = ["fonte", "chave_snapshot", "lat", "lng"]
    faltando = [c for c in colunas if c not in independentes.columns]
    if faltando:
        raise ValueError(f"frame de independentes sem coluna(s) obrigatoria(s): {faltando}")
    # Chave repetida sobrescreveria a entrada de `posicao_por_chave`, e a auto-exclusão da
    # linha perdida passaria a apontar para o índice de OUTRA academia — exclusão silenciosa do
    # ponto errado. O molde é o mesmo de `calcular_pressao_por_academia` (BLK-MA-17-FU1).
    if bool(independentes.duplicated(subset=["fonte", "chave_snapshot"]).any()):
        raise ValueError("frame de independentes com `(fonte, chave_snapshot)` duplicado")

    base = independentes[colunas].copy()
    base["lat"] = pd.to_numeric(base["lat"], errors="coerce")
    base["lng"] = pd.to_numeric(base["lng"], errors="coerce")
    base = base[np.isfinite(base["lat"]) & np.isfinite(base["lng"])]
    base = base.sort_values(["fonte", "chave_snapshot"], kind="stable").reset_index(drop=True)
    if base.empty:
        return base, {}

    fontes = base["fonte"].astype(str).to_numpy()
    chaves = base["chave_snapshot"].astype(str).to_numpy()
    lat = base["lat"].to_numpy(dtype="float64")
    lng = base["lng"].to_numpy(dtype="float64")
    celulas = [
        h3.latlng_to_cell(float(la), float(ln), DEDUP_H3_RES)
        for la, ln in zip(lat, lng, strict=True)
    ]

    # Bucket espacial: sem ele a comparação seria de todos contra todos (19.329^2 = 373 M pares).
    # O `k` sai do limiar, nunca de um literal (BLK-MA-17-FU1). Até 2026-08-18 ele era `1`
    # cravado: na `DEDUP_H3_RES = 11`, cuja aresta média medida é 28,66 m, o anel `k = 1`
    # **não cobre** os 50 m do limiar. Uma dedup sub-coberta não levanta erro — ela devolve
    # "nenhum colapso", que é exatamente o que uma dedup correta devolve quando não há
    # duplicata, e o defeito só aparece contra varredura completa (`test_equivalencia`).
    k = _k_do_bucket(distancia_m)
    ocupantes: dict[str, list[int]] = {}
    mantidos: list[int] = []
    pos_de: dict[int, int] = {}
    posicao_por_chave: dict[tuple[str, str], int] = {}
    colapsadas = 0

    for i in range(len(base)):
        representante: int | None = None
        for vizinha in h3.grid_disk(celulas[i], k):
            for j in ocupantes.get(vizinha, ()):
                if fontes[j] == fontes[i]:
                    continue
                d = float(
                    _haversine_m(
                        np.array([lat[i]]), np.array([lng[i]]), np.array([lat[j]]), np.array([lng[j]])
                    )[0]
                )
                if d <= float(distancia_m):
                    representante = j
                    break
            if representante is not None:
                break

        if representante is None:
            pos_de[i] = len(mantidos)
            mantidos.append(i)
            ocupantes.setdefault(celulas[i], []).append(i)
        else:
            pos_de[i] = pos_de[representante]
            colapsadas += 1
        posicao_por_chave[(fontes[i], chaves[i])] = pos_de[i]

    if colapsadas:
        _logger.info(
            "dedup de independentes entre fontes: %d linha(s) colapsada(s) de %d "
            "(raio %.0f m; grid_disk k=%d)",
            colapsadas,
            len(base),
            float(distancia_m),
            k,
        )
    return base.iloc[mantidos].reset_index(drop=True), posicao_por_chave


def dedup_cadeias_do_feed(
    cadeias_feed: pd.DataFrame,
    pontos_mapeados: pd.DataFrame,
    *,
    distancia_m: float = DEDUP_CADEIA_FEED_M,
    piso_m: float = DEDUP_CADEIA_FEED_PISO_M,
) -> tuple[pd.DataFrame, dict[tuple[str, str], int]]:
    """Colapsa a unidade de REDE do agregador contra o pin de cadeia do funil. Devolve
    `(sobreviventes, posicao_por_chave)`.

    O DEFEITO QUE ELA PERMITE FECHAR. As 2.844 unidades de rede que o WellHub lista são
    concorrência real e **não entram na oferta hoje** — o insumo do sinal 6 é
    `concorrentes_mapeados.parquet`, que nasce dos coletores `unidades_*.csv` (feeds do site de cada
    rede). Pelo critério desta função, **1.673 delas colapsam** contra um ponto já mapeado e **1.171
    entram** — academias reais que não pressionavam ninguém no cálculo. Acrescentá-las sem dedup
    faria o contrário: dobraria a oferta das 1.673 que já estão desenhadas.

    O CRITÉRIO, por unidade do feed — colapsa **se e somente se** existe ponto mapeado com
    `(rede igual E d <= distancia_m)` **OU** `(d <= piso_m)`. A justificativa medida dos dois ramos
    e a tabela de sensibilidade vivem em `DEDUP_CADEIA_FEED_M` (`contrato.py`), com os dois custos
    assimétricos que ela resolve: 37 concorrentes reais que a distância pura apagaria, e 8
    endereços iguais com slug de rede divergente que só o piso recupera.

    **NÃO reusa `dedup_independentes`**, e isso é desenho, não duplicação: aquela exige
    `fonte`/`chave_snapshot` nos DOIS lados (o parquet de cadeias não tem nenhum dos dois) e usa
    distância pura. São regras diferentes, com custos assimétricos opostos — juntá-las numa função
    parametrizada esconderia isso.

    **DUAS PASSAGENS, desde o BLK-MA-17-FU1/FU2.** Primeiro contra os pontos mapeados; se não
    colapsar, contra os SOBREVIVENTES do próprio feed, e aí só entre `fonte` DIFERENTES. A segunda
    existe porque a mesma unidade listada por TotalPass e WellHub viraria duas linhas de oferta: as
    gêmeas se pressionariam (até `49,96` pontos onde não há concorrente nenhum) e, pior, toda
    academia num raio de 2 km contaria dois concorrentes onde há um — a auto-exclusão só zera a
    posição do próprio observador. Colapsar dentro da MESMA fonte está proibido e foi medido: dos 5
    pares de cadeias a `<= 50 m`, os cinco são `wellhub x wellhub` e três são redes distintas
    dividindo prédio.

    O REPRESENTANTE é o ponto QUALIFICADO MAIS PRÓXIMO (desempate pelo menor índice), e o
    sobrevivente entra na ordem estável `(fonte, chave_snapshot)`: as duas escolhas existem para o
    mesmo insumo dar o mesmo artefato em qualquer máquina, sem depender da ordem em que o
    `grid_disk` devolve as células.

    O SEGUNDO ELEMENTO DO RETORNO mapeia **toda** chave do feed — colapsada ou não — para a posição
    do seu representante no array **CONCATENADO** `[pontos_mapeados ; sobreviventes]`, que é
    exatamente o bloco de cadeias que `_oferta_por_origem` recebe. É ele que fecha a auto-pressão
    nos dois casos: para a sobrevivente, a posição é a dela; para a colapsada, a do ponto do parquet
    que a absorveu — sem isso ela se auto-pressionaria através do próprio pin do funil, e o erro
    (`sat(1,0) = 50` pontos) seria maior justamente em quem não tem mais ninguém por perto.
    """
    colunas = ["fonte", "chave_snapshot", "lat", "lng", "rede"]
    # `nome` e' OPCIONAL: sem ele a passagem por nome simplesmente nao roda, e a funcao se comporta
    # como antes do BLK-MA-17-FU4. Nenhum chamador antigo quebra.
    if "nome" in cadeias_feed.columns:
        colunas = [*colunas, "nome"]
    faltando = [c for c in colunas if c not in cadeias_feed.columns]
    if faltando:
        raise ValueError(f"frame de cadeias do feed sem coluna(s) obrigatoria(s): {faltando}")
    # Chave repetida sobrescreveria a entrada de `posicao_por_chave`, e a auto-exclusão da
    # linha perdida passaria a apontar para o índice de OUTRA academia — exclusão silenciosa do
    # ponto errado. O molde é o mesmo de `calcular_pressao_por_academia` (BLK-MA-17-FU1).
    if bool(cadeias_feed.duplicated(subset=["fonte", "chave_snapshot"]).any()):
        raise ValueError("frame de cadeias do feed com `(fonte, chave_snapshot)` duplicado")
    faltando_mapa = [c for c in ("lat", "lng") if c not in pontos_mapeados.columns]
    if faltando_mapa:
        raise ValueError(f"frame de pontos mapeados sem coluna(s): {faltando_mapa}")

    base = cadeias_feed[colunas].copy()
    base["lat"] = pd.to_numeric(base["lat"], errors="coerce")
    base["lng"] = pd.to_numeric(base["lng"], errors="coerce")
    base = base[np.isfinite(base["lat"]) & np.isfinite(base["lng"])]
    base = base.sort_values(["fonte", "chave_snapshot"], kind="stable").reset_index(drop=True)

    offset = int(len(pontos_mapeados))
    if base.empty:
        return base, {}

    lat_m = pd.to_numeric(pontos_mapeados["lat"], errors="coerce").to_numpy(dtype="float64")
    lng_m = pd.to_numeric(pontos_mapeados["lng"], errors="coerce").to_numpy(dtype="float64")
    if "rede" in pontos_mapeados.columns:
        rede_m = pontos_mapeados["rede"].astype("string").fillna("").astype(str).to_numpy()
    else:
        rede_m = np.full(offset, "", dtype=object)

    # Bucket espacial dos pontos JÁ MAPEADOS: sem ele a comparação seria 2.844 x 4.366 pares por
    # rodada. O `k` sai do limiar, nunca de um literal — ver `_k_do_bucket`.
    limiar = max(float(distancia_m), float(piso_m))
    k = _k_do_bucket(limiar)
    ocupantes: dict[str, list[int]] = {}
    for j in range(offset):
        if not (np.isfinite(lat_m[j]) and np.isfinite(lng_m[j])):
            continue
        celula = h3.latlng_to_cell(float(lat_m[j]), float(lng_m[j]), DEDUP_H3_RES)
        ocupantes.setdefault(celula, []).append(j)

    # ---- passagem por NOME (BLK-MA-17-FU4): bucket PROPRIO, numa resolucao grossa ----
    # Os 1.200 m do casamento por nome custariam `grid_disk(k=31)` na `DEDUP_H3_RES = 11` (2.977
    # celulas por ponto). Na `DEDUP_NOME_H3_RES = 8` (aresta 531 m) o mesmo alcance sai com k=4,
    # 61 celulas -- 49x menos varredura para a mesma cobertura.
    nome_m = (
        pontos_mapeados["nome"].astype("string").fillna("").astype(str).to_numpy()
        if "nome" in pontos_mapeados.columns
        else np.full(offset, "", dtype=object)
    )
    usa_nome = "nome" in base.columns and bool((nome_m != "").any())
    k_nome = _k_do_bucket(DIST_MAX_MESMO_NOME_M, resolucao=DEDUP_NOME_H3_RES)
    ocupantes_nome: dict[str, list[int]] = {}
    if usa_nome:
        for j in range(offset):
            if not (np.isfinite(lat_m[j]) and np.isfinite(lng_m[j])):
                continue
            cel = h3.latlng_to_cell(float(lat_m[j]), float(lng_m[j]), DEDUP_NOME_H3_RES)
            ocupantes_nome.setdefault(cel, []).append(j)

    fontes = base["fonte"].astype(str).to_numpy()
    chaves = base["chave_snapshot"].astype(str).to_numpy()
    redes = base["rede"].astype("string").fillna("").astype(str).to_numpy()
    nomes = (
        base["nome"].astype("string").fillna("").astype(str).to_numpy()
        if usa_nome
        else np.full(len(base), "", dtype=object)
    )
    lat = base["lat"].to_numpy(dtype="float64")
    lng = base["lng"].to_numpy(dtype="float64")

    mantidos: list[int] = []
    posicao_por_chave: dict[tuple[str, str], int] = {}
    # Bucket dos SOBREVIVENTES do proprio feed (BLK-MA-17-FU2). Cresce durante o laco: a mesma
    # unidade listada por DOIS agregadores so' e' comparavel depois que a primeira sobreviveu.
    ocupantes_feed: dict[str, list[int]] = {}
    posicao_do_sobrevivente: dict[int, int] = {}
    colapsadas = 0
    colapsadas_entre_fontes = 0
    colapsadas_por_nome = 0

    for i in range(len(base)):
        celula = h3.latlng_to_cell(float(lat[i]), float(lng[i]), DEDUP_H3_RES)
        anel = h3.grid_disk(celula, k)
        candidatos: list[int] = []
        for vizinha in anel:
            candidatos.extend(ocupantes.get(vizinha, ()))
        representante: int | None = None
        melhor = float("inf")
        for j in candidatos:
            d = float(
                _haversine_m(
                    np.array([lat[i]]), np.array([lng[i]]), np.array([lat_m[j]]), np.array([lng_m[j]])
                )[0]
            )
            mesma_rede = bool(redes[i]) and redes[i] == rede_m[j]
            if not ((mesma_rede and d <= float(distancia_m)) or d <= float(piso_m)):
                continue
            if d < melhor or (d == melhor and representante is not None and j < representante):
                melhor = d
                representante = j

        if representante is not None:
            posicao_por_chave[(fontes[i], chaves[i])] = representante
            colapsadas += 1
            continue

        # PASSAGEM POR NOME (BLK-MA-17-FU4). A distancia pura deixava passar 407 duplicatas entre
        # 150 m e 1 km: as duas fontes geocodificam o MESMO endereco com desvio muito maior que o
        # limiar (`Bodytech Uberlandia - NV Boulevard` contra nome identico a 299 m;
        # `SKYFIT ACADEMIA - BACABAL` contra `Bacabal (MA)` a 940 m). Subir o limiar de distancia
        # apagaria academia real; quem separa os dois casos e' o nome -- ver `identidade.py`.
        if usa_nome and nomes[i]:
            cel_n = h3.latlng_to_cell(float(lat[i]), float(lng[i]), DEDUP_NOME_H3_RES)
            melhor_n = float("inf")
            rep_nome: int | None = None
            for viz in h3.grid_disk(cel_n, k_nome):
                for j in ocupantes_nome.get(viz, ()):
                    if redes[i] != rede_m[j] or not nome_m[j]:
                        continue
                    d = float(
                        _haversine_m(
                            np.array([lat[i]]),
                            np.array([lng[i]]),
                            np.array([lat_m[j]]),
                            np.array([lng_m[j]]),
                        )[0]
                    )
                    if d > DIST_MAX_MESMO_NOME_M or d >= melhor_n:
                        continue
                    if mesma_unidade(nomes[i], nome_m[j], redes[i]):
                        melhor_n = d
                        rep_nome = j
            if rep_nome is not None:
                posicao_por_chave[(fontes[i], chaves[i])] = rep_nome
                colapsadas_por_nome += 1
                continue

        # SEGUNDA PASSAGEM (BLK-MA-17-FU2): contra os sobreviventes do proprio feed, e so' entre
        # `fonte` DIFERENTES -- o mesmo recorte que `dedup_independentes` usa, e pela mesma razao.
        # Sem ela, a mesma unidade de rede listada por TotalPass e WellHub vira DUAS linhas de
        # oferta: as gemeas se pressionam (`sat(1,0)` -> ate' 49,96 pts onde nao ha' concorrente
        # nenhum) e, pior, todo mundo num raio de 2 km passa a contar dois concorrentes onde ha' um,
        # porque a auto-exclusao so' zera a posicao do proprio observador.
        #
        # Colapsar dentro da MESMA fonte esta' PROIBIDO, e foi medido: dos 5 pares de cadeias do
        # feed a <= 50 m, os cinco sao `wellhub x wellhub` e TRES sao redes distintas dividindo
        # predio (skyfit x panobianco a 2,9 m; selfit x power_fit a 22,5 m; force_one x world_gym a
        # 39,9 m). A guarda de fonte os pula por construcao.
        gemea: int | None = None
        melhor_gemea = float("inf")
        for vizinha in anel:
            for j in ocupantes_feed.get(vizinha, ()):
                if fontes[j] == fontes[i]:
                    continue
                d = float(
                    _haversine_m(
                        np.array([lat[i]]), np.array([lng[i]]), np.array([lat[j]]), np.array([lng[j]])
                    )[0]
                )
                mesma_rede = bool(redes[i]) and redes[i] == redes[j]
                if not ((mesma_rede and d <= float(distancia_m)) or d <= float(piso_m)):
                    continue
                if d < melhor_gemea or (d == melhor_gemea and gemea is not None and j < gemea):
                    melhor_gemea = d
                    gemea = j

        if gemea is not None:
            posicao_por_chave[(fontes[i], chaves[i])] = posicao_do_sobrevivente[gemea]
            colapsadas_entre_fontes += 1
            continue

        posicao = offset + len(mantidos)
        posicao_por_chave[(fontes[i], chaves[i])] = posicao
        posicao_do_sobrevivente[i] = posicao
        mantidos.append(i)
        ocupantes_feed.setdefault(celula, []).append(i)

    if colapsadas or colapsadas_entre_fontes or colapsadas_por_nome:
        _logger.info(
            "dedup de cadeias do feed: %d de %d colapsada(s) por DISTANCIA contra o insumo "
            "mapeado, %d por NOME (ate' %.0f m) e %d contra outra fonte do proprio feed "
            "(mesma rede a %.0f m ou qualquer rede a %.0f m; grid_disk k=%d)",
            colapsadas,
            len(base),
            colapsadas_por_nome,
            float(DIST_MAX_MESMO_NOME_M),
            colapsadas_entre_fontes,
            float(distancia_m),
            float(piso_m),
            k,
        )
    return base.iloc[mantidos].reset_index(drop=True), posicao_por_chave


def calcular_pressao_por_academia(
    academias: pd.DataFrame,
    concorrentes: pd.DataFrame,
    *,
    independentes: pd.DataFrame | None = None,
    cadeias_do_feed: pd.DataFrame | None = None,
    peso_independente: float = PESO_OFERTA_INDEPENDENTE,
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

    UNIVERSO DE OFERTA (BLK-MA-16). Sem `independentes`, só as cadeias contam e o resultado é o
    histórico — `universo_oferta = "cadeias"`. Com `independentes`, elas entram com metade do peso
    de uma unidade de rede e o carimbo vira `"cadeias_e_independentes"`. **É condicional ao insumo,
    no molde da DEC-036**: nenhuma rodada muda de régua sem o chamador fornecer o frame.

    O que a inclusão corrige, medido em SP (2026-08-14, 7.106 independentes): a fração com pressão
    **`0` cai de 29,2% para 3,9%**. Aquele zero não era território livre — era o insumo, que só
    enxerga cadeia, respondendo a pergunta errada. O que ela custa: a saturação comprime o topo
    (amplitude entre os 200 mais pressionados de 7,74 para 4,19 pontos), e é por isso que a virada
    do default é decisão de gate e não desta função.

    COBERTURA DA OFERTA DE CADEIA (BLK-MA-17). `cadeias_do_feed` é a TERCEIRA lista de pontos: as
    unidades de REDE que o agregador lista e que `concorrentes_mapeados.parquet` não cobre. Elas
    entram no bloco de cadeias com `PESO_OFERTA_CADEIA = 1,0` — são unidades de rede, e o `0,5` é da
    independente por decisão de produto —, deduplicadas por `dedup_cadeias_do_feed` (2.844 no feed,
    **1.171** depois da dedup). É o MESMO
    defeito que a DEC-033 corrigiu, do outro lado do universo: lá as independentes não contavam,
    aqui parte das cadeias não contava, e nos dois casos por cobertura do insumo, não por desenho da
    fórmula. Simétrico a `independentes`: **condicional ao insumo**, e sem o frame a aritmética é
    byte a byte a de antes.
    """
    if kernel not in KERNEIS_PRESSAO:
        raise ValueError(f"kernel fora de {sorted(KERNEIS_PRESSAO)}: {kernel!r}")
    if not 0.0 <= float(peso_independente) <= float(PESO_OFERTA_CADEIA):
        raise ValueError(
            f"`peso_independente` fora de [0, {PESO_OFERTA_CADEIA}]: {peso_independente!r} — uma "
            "independente nao pode pressionar MAIS que uma unidade de rede"
        )
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

    pontos_c = _pontos_validos_frame(concorrentes)
    lat_c = pontos_c["lat"].to_numpy(dtype="float64")
    lng_c = pontos_c["lng"].to_numpy(dtype="float64")

    lat_i: np.ndarray | None = None
    lng_i: np.ndarray | None = None
    auto_pos: np.ndarray | None = None
    mascara_feed: np.ndarray | None = None
    auto_pos_cadeia: np.ndarray | None = None
    universo = UNIVERSO_OFERTA_CADEIAS

    chaves_base = list(
        zip(base["fonte"].astype(str), base["chave_snapshot"].astype(str), strict=True)
    )

    if cadeias_do_feed is not None:
        universo = UNIVERSO_OFERTA_COM_INDEPENDENTES
        sobreviventes, posicao_cadeia = dedup_cadeias_do_feed(cadeias_do_feed, pontos_c)
        lat_c = np.concatenate([lat_c, sobreviventes["lat"].to_numpy(dtype="float64")])
        lng_c = np.concatenate([lng_c, sobreviventes["lng"].to_numpy(dtype="float64")])
        # A máscara SÓ decompõe a saída: o peso é o mesmo nos dois lados do bloco de cadeias.
        mascara_feed = np.concatenate(
            [
                np.zeros(len(pontos_c), dtype=bool),
                np.ones(len(sobreviventes), dtype=bool),
            ]
        )
        # Auto-exclusão POR CHAVE, cobrindo os dois casos (sobrevivente e colapsada) — nunca por
        # distância zero, que confundiria "sou eu" com "há outra academia no mesmo endereço".
        auto_pos_cadeia = np.array(
            [posicao_cadeia.get(chave, -1) for chave in chaves_base], dtype="int64"
        )

    if independentes is not None:
        universo = UNIVERSO_OFERTA_COM_INDEPENDENTES
        pontos_i, posicao_por_chave = dedup_independentes(independentes)
        lat_i = pontos_i["lat"].to_numpy(dtype="float64")
        lng_i = pontos_i["lng"].to_numpy(dtype="float64")
        # A auto-exclusão é resolvida pela CHAVE, e pelo mapa da dedup em vez do índice cru: se a
        # própria academia foi a linha absorvida no colapso, quem representa ela na oferta é a
        # sobrevivente do grupo — e é essa parcela que precisa ser zerada, não a que sumiu.
        auto_pos = np.array(
            [posicao_por_chave.get(chave, -1) for chave in chaves_base], dtype="int64"
        )

    resultado = _oferta_por_origem(
        base["lat"].to_numpy(dtype="float64"),
        base["lng"].to_numpy(dtype="float64"),
        lat_c,
        lng_c,
        kernel=kernel,
        raio_m=raio_m,
        beta=beta,
        lat_i=lat_i,
        lng_i=lng_i,
        peso_independente=peso_independente,
        auto_pos=auto_pos,
        cadeia_do_feed=mascara_feed,
        auto_pos_cadeia=auto_pos_cadeia,
    )
    pressao = _saturar(resultado.oferta_total)

    out = pd.DataFrame(
        {
            "fonte": base["fonte"].astype("string").to_numpy(),
            "chave_snapshot": base["chave_snapshot"].astype("string").to_numpy(),
            "pressao_competitiva": pd.Series(pressao, dtype="float64"),
            "v6": pd.Series(pressao / 100.0, dtype="float64"),
            "oferta_ponderada": pd.Series(resultado.oferta_total, dtype="float64"),
            "n_concorrentes_no_raio": pd.Series(resultado.n_no_raio, dtype="int64"),
            "dist_concorrente_mais_proximo_m": pd.Series(resultado.dist_min, dtype="float64"),
            "oferta_independentes": pd.Series(resultado.oferta_independentes, dtype="float64"),
            "n_independentes_no_raio": pd.Series(
                resultado.n_independentes_no_raio, dtype="int64"
            ),
            "oferta_cadeias_do_feed": pd.Series(resultado.oferta_cadeias_feed, dtype="float64"),
            "n_cadeias_do_feed_no_raio": pd.Series(
                resultado.n_cadeias_feed_no_raio, dtype="int64"
            ),
            "kernel_pressao": pd.Series([str(kernel)] * len(base), dtype="string"),
            "raio_pressao_m": pd.Series([float(raio_m)] * len(base), dtype="float64"),
            "universo_oferta": pd.Series([universo] * len(base), dtype="string"),
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
    _assert_universo_e_decomposicao(
        df,
        coluna_oferta="oferta_ponderada",
        coluna_parte="oferta_independentes",
        coluna_parte_feed="oferta_cadeias_do_feed",
    )


def _assert_universo_e_decomposicao(
    df: pd.DataFrame, *, coluna_oferta: str, coluna_parte: str, coluna_parte_feed: str
) -> None:
    """Invariantes do BLK-MA-16 e do BLK-MA-17, comuns aos dois grãos.

    Nenhuma parte pode exceder o todo nem ser negativa, a SOMA das duas também não (elas são
    recortes disjuntos: independente do agregador contra unidade de rede do agregador), e **no
    universo `cadeias` as duas partes e as duas contagens têm de ser exatamente zero**: um resíduo
    ali significaria que pontos entraram numa rodada que se declara sem eles — o carimbo estaria
    mentindo, que é o defeito exato que ele existe para não deixar acontecer.
    """
    universo = set(df["universo_oferta"].astype(str).unique())
    fora = sorted(universo - set(UNIVERSOS_OFERTA))
    if fora:
        raise AssertionError(f"`universo_oferta` fora de {list(UNIVERSOS_OFERTA)}: {fora}")

    total = pd.to_numeric(df[coluna_oferta], errors="coerce")
    partes = {
        coluna_parte: pd.to_numeric(df[coluna_parte], errors="coerce"),
        coluna_parte_feed: pd.to_numeric(df[coluna_parte_feed], errors="coerce"),
    }
    for nome, parte in partes.items():
        if bool((parte < 0.0).any()):
            raise AssertionError(f"`{nome}` negativa")
        # Tolerância de ponto flutuante: a parte é somada dentro do total, então a diferença
        # legítima é zero e qualquer folga aqui é só ruído de acumulação.
        if bool((parte > total + 1e-9).any()):
            raise AssertionError(f"`{nome}` maior que `{coluna_oferta}`")
    soma_partes = partes[coluna_parte] + partes[coluna_parte_feed]
    if bool((soma_partes > total + 1e-9).any()):
        raise AssertionError(
            f"`{coluna_parte}` + `{coluna_parte_feed}` maior que `{coluna_oferta}`"
        )

    contagens = ("n_independentes_no_raio", "n_cadeias_do_feed_no_raio")
    for nome in contagens:
        if bool((df[nome].astype("int64") < 0).any()):
            raise AssertionError(f"`{nome}` negativo")
        if bool((df[nome].astype("int64") > df["n_concorrentes_no_raio"]).any()):
            raise AssertionError(f"`{nome}` maior que `n_concorrentes_no_raio`")
    soma_contagens = (
        df["n_independentes_no_raio"].astype("int64")
        + df["n_cadeias_do_feed_no_raio"].astype("int64")
    )
    if bool((soma_contagens > df["n_concorrentes_no_raio"].astype("int64")).any()):
        raise AssertionError(
            "`n_independentes_no_raio` + `n_cadeias_do_feed_no_raio` maior que "
            "`n_concorrentes_no_raio`"
        )

    so_cadeias = df["universo_oferta"].astype(str) == UNIVERSO_OFERTA_CADEIAS
    if bool(so_cadeias.any()):
        for nome, parte in partes.items():
            if bool((parte[so_cadeias] != 0.0).any()):
                raise AssertionError(
                    f"`{nome}` diferente de zero com `universo_oferta = "
                    f"{UNIVERSO_OFERTA_CADEIAS}` — o carimbo estaria mentindo"
                )
        for nome in contagens:
            if bool((df.loc[so_cadeias, nome].astype("int64") != 0).any()):
                raise AssertionError(
                    f"`{nome}` diferente de zero com `universo_oferta = "
                    f"{UNIVERSO_OFERTA_CADEIAS}`"
                )


def calcular_pressao_por_hex(
    hexes: Iterable[str],
    concorrentes: pd.DataFrame,
    *,
    independentes: pd.DataFrame | None = None,
    cadeias_do_feed: pd.DataFrame | None = None,
    peso_independente: float = PESO_OFERTA_INDEPENDENTE,
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

    pontos_c = _pontos_validos_frame(concorrentes)
    lat_c = pontos_c["lat"].to_numpy(dtype="float64")
    lng_c = pontos_c["lng"].to_numpy(dtype="float64")

    lat_i: np.ndarray | None = None
    lng_i: np.ndarray | None = None
    mascara_feed: np.ndarray | None = None
    universo = UNIVERSO_OFERTA_CADEIAS
    if cadeias_do_feed is not None:
        universo = UNIVERSO_OFERTA_COM_INDEPENDENTES
        sobreviventes, _posicoes_cadeia = dedup_cadeias_do_feed(cadeias_do_feed, pontos_c)
        lat_c = np.concatenate([lat_c, sobreviventes["lat"].to_numpy(dtype="float64")])
        lng_c = np.concatenate([lng_c, sobreviventes["lng"].to_numpy(dtype="float64")])
        mascara_feed = np.concatenate(
            [np.zeros(len(pontos_c), dtype=bool), np.ones(len(sobreviventes), dtype=bool)]
        )
    if independentes is not None:
        universo = UNIVERSO_OFERTA_COM_INDEPENDENTES
        pontos_i, _posicoes = dedup_independentes(independentes)
        lat_i = pontos_i["lat"].to_numpy(dtype="float64")
        lng_i = pontos_i["lng"].to_numpy(dtype="float64")
    # Sem `auto_pos` nem `auto_pos_cadeia`: a origem aqui é o CENTROIDE do território, não uma
    # academia — não há "si mesma" para excluir. É a única diferença de tratamento entre os dois
    # grãos, e ela vale para as DUAS listas.

    # MESMO núcleo do grão academia: se as duas fórmulas divergirem, os dois números deixam de ser
    # comparáveis e ninguém percebe — o kernel e a saturação vivem num lugar só de propósito.
    resultado = _oferta_por_origem(
        lat_h,
        lng_h,
        lat_c,
        lng_c,
        kernel=kernel,
        raio_m=raio_m,
        beta=beta,
        lat_i=lat_i,
        lng_i=lng_i,
        peso_independente=peso_independente,
        cadeia_do_feed=mascara_feed,
    )
    pressao = _saturar(resultado.oferta_total)

    out = pd.DataFrame(
        {
            "hex_id_res7": pd.Series(validos, dtype="string"),
            "pressao_competitiva_no_hex": pd.Series(pressao, dtype="float64"),
            "v6_no_hex": pd.Series(pressao / 100.0, dtype="float64"),
            "oferta_ponderada_no_hex": pd.Series(resultado.oferta_total, dtype="float64"),
            "n_concorrentes_no_raio": pd.Series(resultado.n_no_raio, dtype="int64"),
            "dist_concorrente_mais_proximo_m": pd.Series(resultado.dist_min, dtype="float64"),
            "oferta_independentes_no_hex": pd.Series(
                resultado.oferta_independentes, dtype="float64"
            ),
            "n_independentes_no_raio": pd.Series(
                resultado.n_independentes_no_raio, dtype="int64"
            ),
            "oferta_cadeias_do_feed_no_hex": pd.Series(
                resultado.oferta_cadeias_feed, dtype="float64"
            ),
            "n_cadeias_do_feed_no_raio": pd.Series(
                resultado.n_cadeias_feed_no_raio, dtype="int64"
            ),
            "kernel_pressao": pd.Series([str(kernel)] * len(validos), dtype="string"),
            "raio_pressao_m": pd.Series([float(raio_m)] * len(validos), dtype="float64"),
            "universo_oferta": pd.Series([universo] * len(validos), dtype="string"),
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
    _assert_universo_e_decomposicao(
        df,
        coluna_oferta="oferta_ponderada_no_hex",
        coluna_parte="oferta_independentes_no_hex",
        coluna_parte_feed="oferta_cadeias_do_feed_no_hex",
    )


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
    "dedup_cadeias_do_feed",
    "dedup_independentes",
    "ler_concorrentes",
    "peso_por_distancia",
]
