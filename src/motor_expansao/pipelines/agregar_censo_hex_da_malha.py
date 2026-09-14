"""Agrega a camada censitaria de HEXAGONO a partir da malha de SETORES.

Por que este pipeline existe
----------------------------
A camada censitaria vive em dois graos e, ate 2026-08-31, cada um tinha a sua propria
cadeia de producao a partir dos CSVs brutos do Censo 2022:

- GRAO DO SETOR (`data/outputs/setores_censitarios_2022_geo/`): produzido por
  `materializar_setores_censitarios_geo.py`, que REPARA o `CD_SETOR` corrompido em
  notacao cientifica enxertando a chave de um agregado irmao intacto, com verificacao
  de >= 99% de UF batendo entre o valor corrompido e a chave recuperada.
- GRAO DO HEXAGONO (`censo2022_setores_calibrado*.parquet`): produzido por
  `fase_a_censo2022_setores.py`, em TRES caminhos que particionam o pais sem
  sobreposicao (core GO/RJ/SP, expandido DF/MG/RS, nacional nas outras 21 UFs), cada
  um casando setor com renda por vias diferentes -- chave crua no core, POSICAO dentro
  da UF nos outros dois.

Medido em 7 capitais (844 hexagonos povoados), a renda no grao do hexagono NAO reproduz
a renda da malha: Spearman de +0,09 (Rio) a +0,85 (Curitiba), erro de score p90 de 37,6
pontos, e 28,6% dos hexagonos com erro acima de 20 pontos. A ESCALA esta certa em toda
parte; o que quebra e a ORDEM. Verdade externa (nome de bairro/distrito) diz que a malha
e a leitura certa nas tres cidades onde da para testar: o artefato colocava Ermelino
Matarazzo e Tremembe como os hexagonos mais ricos de Sao Paulo (Itaim Bibi em 56),
Guadalupe/Anchieta e Santa Cruz entre os 6 mais ricos do Rio, e nao tinha o Batel no
top 6 de Curitiba.

O conserto e estrutural, nao um patch de valor: a renda do hexagono passa a ser AGREGADA
da malha de setores -- a mesma que o Relatorio Pontual ja serve --, ponderada por
POPULACAO, que e o que a grandeza exige (renda per capita e uma razao; a media de razoes
ponderada por area responde "renda por metro quadrado", nao "por pessoa"). Com isso os
dois graos passam a ter UMA fonte, e a divergencia entre a ficha do imovel e o mapa
deixa de poder existir por construcao.

O que este pipeline NAO faz
---------------------------
- NAO recalcula `pop_total_setor_2022`. A populacao do artefato ja reproduz a malha
  (Spearman +0,88, razao mediana 0,994) e alimenta `pop_hex_base` -> SAM -> residual.
  Trocar a populacao arrastaria a cadeia inteira de mercado sem defeito que o justifique.
  So a RENDA muda, e o score muda por consequencia dela.
- NAO toca o M1: `score_priorizacao`, `hex_score_estrutural`, pesos e artefatos oficiais
  ficam intactos (a renda do M1 e a SIDRA municipal, outra coluna).
- NAO muda a regua da DEC-040. `calcular_score_calibrado` e chamada como esta.

READ-ONLY sobre o M1.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from motor_expansao.pipelines.calibrar_renda_setor_2022 import calcular_score_calibrado
except ModuleNotFoundError:  # execucao como script solto
    from calibrar_renda_setor_2022 import calcular_score_calibrado  # type: ignore[no-redef]


DEFAULT_GEO_ROOT = Path("data/outputs/setores_censitarios_2022_geo")
DEFAULT_OUTPUT_PATH = Path("data/staging/censo2022_hex_da_malha.parquet")
DEFAULT_REPORT_PATH = Path("data/reports/censo_hex_da_malha.md")

H3_RESOLUTION = 7
# Area do hexagono H3 res-7. Constante do projeto (CLAUDE.md secao 3); a densidade no grao
# do hexagono e derivada dela, entao fica aqui explicita em vez de recalculada.
AREA_HEX_KM2 = 5.161293

COLUNAS_SETOR = (
    "cod_setor",
    "uf",
    "cod_municipio",
    "pop_total_setor_2022",
    "renda_per_capita_setor_2022_calibrada",
    "geometry_wkb",
    "bbox_minx",
    "bbox_miny",
    "bbox_maxx",
    "bbox_maxy",
)

METODO = "agregado_da_malha_setorial_ponderado_por_populacao"


# ---------------------------------------------------------------------------
# Atribuicao setor -> hexagono
# ---------------------------------------------------------------------------


def _candidatos(geom, bbox: tuple[float, float, float, float], h3mod) -> set[str]:
    """Celulas H3 que PODEM intersectar o setor.

    `geo_to_cells` faz preenchimento por centroide de celula: para um setor menor que
    uma celula ele devolve conjunto VAZIO. Por isso o conjunto de candidatas parte dos
    quatro cantos do bbox e do centroide -- que cobrem o caso comum -- e so entao soma
    o preenchimento, para os setores rurais grandes. Sem os cantos, um setor que cruza
    a fronteira de dois hexagonos seria atribuido inteiro a um deles e a populacao do
    vizinho sumiria em silencio.
    """
    minx, miny, maxx, maxy = bbox
    cells = {
        h3mod.latlng_to_cell(lat, lng, H3_RESOLUTION)
        for lat, lng in (
            (miny, minx), (miny, maxx), (maxy, minx), (maxy, maxx),
            (geom.centroid.y, geom.centroid.x),
        )
    }
    try:
        cells |= set(h3mod.geo_to_cells(geom, H3_RESOLUTION))
    except Exception:  # geometria degenerada: os cantos ja bastam
        pass
    return cells


def agregar_setores(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega um DataFrame de setores (com `geometry_wkb`) para o grao do hexagono.

    Pura: nao muta `df`, nao le nem escreve disco.

    A fracao de area de cada setor e NORMALIZADA para somar 1 antes de distribuir a
    populacao. Sem isso, erro de projecao/topologia nas bordas faria a soma das fracoes
    ficar abaixo de 1 e a populacao evaporar -- alguns habitantes por setor, invisiveis
    em qualquer teste de valor e visiveis so no total nacional.
    """
    import h3 as h3mod
    from shapely import wkb as shapely_wkb
    from shapely.geometry import Polygon

    cache: dict[str, Polygon] = {}

    def poligono(cell: str) -> Polygon:
        pol = cache.get(cell)
        if pol is None:
            pol = Polygon([(lng, lat) for lat, lng in h3mod.cell_to_boundary(cell)])
            cache[cell] = pol
        return pol

    acumulado: dict[str, list[float]] = {}
    for linha in df.itertuples(index=False):
        pop = getattr(linha, "pop_total_setor_2022", np.nan)
        renda = getattr(linha, "renda_per_capita_setor_2022_calibrada", np.nan)
        if not np.isfinite(pop) or pop <= 0:
            continue
        try:
            geom = shapely_wkb.loads(bytes(linha.geometry_wkb))
        except Exception:
            continue
        if geom.is_empty:
            continue
        if not geom.is_valid:
            geom = geom.buffer(0)
        area_total = geom.area
        if area_total <= 0:
            continue

        bbox = (linha.bbox_minx, linha.bbox_miny, linha.bbox_maxx, linha.bbox_maxy)
        pedacos: list[tuple[str, float]] = []
        for cell in _candidatos(geom, bbox, h3mod):
            inter = geom.intersection(poligono(cell))
            if inter.is_empty:
                continue
            fracao = inter.area / area_total
            if fracao > 0:
                pedacos.append((cell, fracao))
        if not pedacos:
            continue
        soma = sum(f for _, f in pedacos)
        if soma <= 0:
            continue

        tem_renda = bool(np.isfinite(renda))
        for cell, fracao in pedacos:
            pop_pedaco = pop * (fracao / soma)
            alvo = acumulado.setdefault(cell, [0.0, 0.0, 0.0, 0.0])
            alvo[0] += pop_pedaco                      # populacao atribuida
            alvo[3] += 1.0                             # setores contribuintes
            if tem_renda:
                alvo[1] += renda * pop_pedaco          # numerador da renda
                alvo[2] += pop_pedaco                  # populacao COM renda

    if not acumulado:
        return pd.DataFrame(
            columns=["hex_id", "pop_malha", "renda_malha", "pop_com_renda_malha",
                     "n_setores_malha", "cobertura_renda_malha"]
        )

    out = pd.DataFrame(
        [
            {
                "hex_id": cell,
                "pop_malha": v[0],
                # Renda ponderada pela populacao dos setores QUE TEM renda -- nao pela
                # populacao total do hexagono. Ponderar pelo total trataria setor sem
                # renda como renda zero e puxaria o hexagono para baixo em silencio.
                "renda_malha": (v[1] / v[2]) if v[2] > 0 else np.nan,
                "pop_com_renda_malha": v[2],
                "n_setores_malha": int(v[3]),
                "cobertura_renda_malha": (v[2] / v[0]) if v[0] > 0 else np.nan,
            }
            for cell, v in acumulado.items()
        ]
    )
    return out.sort_values("hex_id").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Varredura da malha
# ---------------------------------------------------------------------------


def listar_particoes(geo_root: Path, ufs: tuple[str, ...] | None = None) -> list[Path]:
    partes = sorted(geo_root.glob("uf=*/cod_municipio=*/part-*.parquet"))
    if ufs:
        alvo = {u.upper() for u in ufs}
        partes = [p for p in partes if p.parent.parent.name.split("=", 1)[1].upper() in alvo]
    return partes


def agregar_particoes(
    caminhos: list[Path], progresso: int = 250, ilegiveis: list[Path] | None = None
) -> pd.DataFrame:
    """Agrega uma lista de particoes municipais.

    Particao ilegivel (parquet truncado/corrompido) NAO derruba a varredura -- 5.571
    arquivos e um deles ruim nao pode custar a corrida inteira. Mas tambem NAO some em
    silencio: o caminho vai para `ilegiveis` e o chamador e obrigado a decidir. Pular sem
    reportar seria a mesma falha silenciosa que este pipeline existe para consertar.
    """
    frames: list[pd.DataFrame] = []
    for i, caminho in enumerate(caminhos, 1):
        try:
            df = pd.read_parquet(caminho, columns=[c for c in COLUNAS_SETOR])
        except Exception as erro:  # parquet corrompido / truncado
            print(f"  ILEGIVEL: {caminho} ({type(erro).__name__})", flush=True)
            if ilegiveis is not None:
                ilegiveis.append(caminho)
            continue
        parcial = agregar_setores(df)
        if not parcial.empty:
            parcial["uf"] = caminho.parent.parent.name.split("=", 1)[1]
            frames.append(parcial)
        if progresso and i % progresso == 0:
            print(f"  {i}/{len(caminhos)} particoes", flush=True)
    if not frames:
        return pd.DataFrame()
    todos = pd.concat(frames, ignore_index=True)
    # Um hexagono pode ser tocado por setores de MUNICIPIOS diferentes (e ate de UFs
    # diferentes na divisa). Reagregar por hex_id, e nao concatenar, e o que impede o
    # mesmo hexagono de aparecer duas vezes com metade da populacao cada.
    todos["num"] = todos.renda_malha * todos.pop_com_renda_malha
    agg = todos.groupby("hex_id", as_index=False).agg(
        pop_malha=("pop_malha", "sum"),
        pop_com_renda_malha=("pop_com_renda_malha", "sum"),
        num=("num", "sum"),
        n_setores_malha=("n_setores_malha", "sum"),
        uf=("uf", "first"),
    )
    agg["renda_malha"] = np.where(agg.pop_com_renda_malha > 0, agg.num / agg.pop_com_renda_malha, np.nan)
    agg["cobertura_renda_malha"] = np.where(
        agg.pop_malha > 0, agg.pop_com_renda_malha / agg.pop_malha, np.nan
    )
    agg["densidade_malha_hab_km2"] = agg.pop_malha / AREA_HEX_KM2
    return agg.drop(columns=["num"]).sort_values("hex_id").reset_index(drop=True)


def anexar_score(agg: pd.DataFrame, pop_hex: pd.DataFrame | None = None) -> pd.DataFrame:
    """Calcula o score da DEC-040 com a renda da MALHA.

    `pop_hex` (colunas `hex_id`, `pop_total_setor_2022`) e a populacao do ARTEFATO. Ela
    e preferida a `pop_malha` de proposito: a populacao do artefato ja reproduz a malha e
    alimenta `pop_hex_base` -> SAM -> residual. Manter a populacao de la faz o score mudar
    SO pela renda, que e o defeito medido -- e deixa a cadeia de mercado fora do diff.
    """
    out = agg.copy()
    if pop_hex is not None and not pop_hex.empty:
        out = out.merge(pop_hex[["hex_id", "pop_total_setor_2022"]], on="hex_id", how="left")
        pop = out.pop_total_setor_2022.fillna(out.pop_malha)
    else:
        pop = out.pop_malha
    renda = out.renda_malha
    valido = renda.notna() & pop.notna() & (pop > 0)
    hexs = np.full(len(out), np.nan)
    ajus = np.full(len(out), np.nan)
    score = np.full(len(out), np.nan)
    if valido.any():
        h, a, s = calcular_score_calibrado(
            renda[valido].to_numpy(float), pop[valido].to_numpy(float)
        )
        hexs[valido.to_numpy()] = h
        ajus[valido.to_numpy()] = a
        score[valido.to_numpy()] = s
    out["hex_score_estrutural_calibrado_malha"] = hexs
    out["ajuste_calibrado_malha"] = ajus
    out["score_malha"] = score
    out["pop_score_malha"] = pop
    out["metodo_agregacao_censo_hex"] = METODO
    out["data_agregacao_censo_hex"] = date.today().isoformat()
    return out


def k_exato_da_malha(geo_root: Path = DEFAULT_GEO_ROOT, amostra: int = 12) -> float:
    """`k` MEDIDO na malha setorial (razao calibrada/bruta), conferido em N particoes.

    Nao le o carimbo `metodo_renda_setor_2022`: ele grava `k=1.2335`, arredondado, para um
    k real de 1,2334632197. Confere em varias particoes porque um k que variasse por UF
    seria justamente o defeito que a DEC-032 corrigiu.
    """
    caminhos = listar_particoes(Path(geo_root))
    if not caminhos:
        raise ValueError(f"nenhuma particao em {geo_root}")
    passo = max(1, len(caminhos) // amostra)
    medidos: list[float] = []
    for caminho in caminhos[::passo][:amostra]:
        try:
            df = pd.read_parquet(
                caminho,
                columns=["renda_per_capita_setor_2022", "renda_per_capita_setor_2022_calibrada"],
            )
            medidos.append(k_exato(df["renda_per_capita_setor_2022"],
                                   df["renda_per_capita_setor_2022_calibrada"]))
        except Exception:
            continue
    if not medidos:
        raise ValueError("nao foi possivel medir o k da malha em nenhuma particao")
    if max(medidos) - min(medidos) > _TOL_K:
        raise ValueError(
            f"a malha usa k DIFERENTES entre particoes ({min(medidos):.10f} a "
            f"{max(medidos):.10f}) — e' o defeito da DEC-032 de volta"
        )
    return medidos[0]


# ---------------------------------------------------------------------------
# Sobreposicao na cadeia
# ---------------------------------------------------------------------------

COL_RENDA = "renda_per_capita_setor_2022_calibrada"
COL_SCORE = "score_setor_2022_calibrado"
COL_FONTE = "fonte_renda_censo_hex"
COL_CARIMBO = "metodo_calibracao_renda"

FONTE_MALHA = "malha_setorial_pop_ponderada"
FONTE_REESCALADA = "fase_a_posicional_reescalado_ao_k_da_malha"

_RE_K = re.compile(r"k=([0-9]+(?:\.[0-9]+)?)")


def _k_do_carimbo(serie: pd.Series | None) -> float | None:
    """`k` lido do carimbo do PROPRIO frame, quando ele ja tem um.

    Serve so a idempotencia: um frame ja sobreposto carrega o carimbo da malha, e ler
    dali faz o fator de reescala virar 1,0. Nao substitui `k_exato` na medicao inicial --
    os carimbos do repo estao arredondados, e a medicao e' o que vale.
    """
    if serie is None or len(serie) == 0:
        return None
    limpa = serie.dropna().astype(str)
    if limpa.empty:
        return None
    achados = {m.group(1) for m in (_RE_K.search(v) for v in limpa.unique()) if m}
    if len(achados) != 1:
        return None
    try:
        return float(achados.pop())
    except ValueError:
        return None


CENSO_HEX_PARQUETS = (
    Path("data/staging/censo2022_setores_calibrado.parquet"),
    Path("data/staging/censo2022_setores_calibrado_piloto_expandido.parquet"),
    Path("data/staging/censo2022_setores_calibrado_nacional_completo.parquet"),
)

# Tolerancia do `k` medido: e um multiplicativo global, entao a razao calibrada/bruta tem
# de ser a MESMA linha a linha a menos de ruido de ponto flutuante.
_TOL_K = 1e-9


def k_exato(bruta: pd.Series, calibrada: pd.Series) -> float:
    """O `k` MEDIDO na propria coluna, nao lido do carimbo.

    Os carimbos do repo estao ARREDONDADOS -- o geo grava `k=1.2335` para um k real de
    1,2334632197 e o staging hex grava `k=1.0239` para 1,0238667497. Reescalar por um k
    arredondado injeta erro em toda a coluna, e e' exatamente a classe de defeito que
    este pipeline conserta: acreditar no rotulo em vez de medir o fato. O carimbo continua
    sendo escrito, mas como DESCRICAO do que foi feito, nunca como insumo do calculo.

    Levanta se a razao nao for constante -- k nao constante significa que a coluna nao
    passou por um multiplicativo global, e reescalar seria mentira.
    """
    b = pd.to_numeric(bruta, errors="coerce")
    c = pd.to_numeric(calibrada, errors="coerce")
    valido = b.notna() & c.notna() & (b > 0)
    if not valido.any():
        raise ValueError("sem par (renda bruta, renda calibrada) para medir o k")
    razao = (c[valido] / b[valido]).astype("float64")
    if float(razao.max() - razao.min()) > _TOL_K:
        raise ValueError(
            f"k nao e constante na coluna (min {razao.min():.10f}, max {razao.max():.10f}) — "
            "a calibracao nao foi um multiplicativo global e reescalar seria invalido"
        )
    return float(razao.median())


# Tolerancia RELATIVA entre parquets distintos. Medido em 2026-08-31: o parquet core usa
# k = 1,0238667496554432 e os outros dois usam 1,0239 cravado -- o MESMO k, um em precisao
# cheia e dois arredondados no carimbo (0,0033% de diferenca). E' ruido de arredondamento,
# nao calibracao divergente; 20% (o gap malha x hexagono) nao passaria nem perto.
_TOL_K_ENTRE_FONTES = 1e-4


def k_exato_do_censo_hex(paths: tuple[Path, ...] = CENSO_HEX_PARQUETS) -> float:
    """`k` medido nos parquets de censo por hexagono; exige que os tres CONCORDEM.

    Dentro de cada parquet o `k` tem de ser exato (`k_exato` levanta se variar). ENTRE
    parquets a tolerancia e relativa, porque dois deles gravaram o valor arredondado --
    ver `_TOL_K_ENTRE_FONTES`.
    """
    medidos: dict[str, float] = {}
    for p in paths:
        if not p.exists():
            continue
        df = pd.read_parquet(
            p, columns=["renda_per_capita_setor_2022", "renda_per_capita_setor_2022_calibrada"]
        )
        medidos[p.name] = k_exato(df["renda_per_capita_setor_2022"],
                                  df["renda_per_capita_setor_2022_calibrada"])
    if not medidos:
        raise ValueError(f"nenhum parquet de censo por hexagono encontrado em {paths}")
    valores = list(medidos.values())
    if (max(valores) - min(valores)) / max(valores) > _TOL_K_ENTRE_FONTES:
        raise ValueError(f"os parquets de censo por hexagono usam k DIFERENTES: {medidos}")
    return float(np.median(valores))


def sobrepor_renda_da_malha(
    censo: pd.DataFrame,
    malha_path: Path = DEFAULT_OUTPUT_PATH,
) -> pd.DataFrame:
    """Substitui renda e score do censo no grao do hexagono pelos agregados da MALHA.

    Contrato:
    - MUDA VALOR, NAO MUDA COBERTURA. Onde a malha nao alcanca (hexagono sem setor
      povoado intersectando), o valor antigo e MANTIDO, apenas REESCALADO para o `k` da
      malha. Sao 114.038 hexagonos, mediana de populacao 0 e p90 de 1 habitante -- mas
      zerar a renda deles mexeria em `has_censo_signal` -> `confianca_geografica` ->
      `populacao_corte_hex` -> `flag_sam` (DEC-006/007), trocando um conserto de VALOR
      por um de COBERTURA sem necessidade.
    - UM UNICO `k` na coluna ao final. Antes desta funcao a mesma coluna homonima saia
      com k=1,0239 no grao do hexagono e k=1,2335 no grao do setor -- 20,5% de diferenca
      entre o Mapa e o Relatorio Pontual para o MESMO endereco. Os dois k sao lidos dos
      CARIMBOS, e a funcao ABORTA se algum for ilegivel: reescalar com k errado repete o
      defeito de 2026-08-14 (renda do tooltip 17% abaixo do IBGE).
    - Carimba `fonte_renda_censo_hex` linha a linha, para a auditoria distinguir o que
      veio da malha do que so' foi reescalado.

    Pura: nao muta `censo`. Sem o parquet da malha, devolve `censo` intacto.
    """
    if not Path(malha_path).exists() or censo.empty or "hex_id" not in censo.columns:
        return censo

    malha = pd.read_parquet(malha_path, columns=["hex_id", "renda_malha", "score_malha", "k_malha"])
    k_malha = float(pd.to_numeric(malha["k_malha"], errors="coerce").dropna().median())

    # IDEMPOTENCIA. `calcular_colunas_mercado` le o proprio artefato como entrada, entao
    # esta funcao roda sobre um frame que ela mesma ja pode ter reescalado. Se o carimbo do
    # frame ja e' o da malha, `k_antigo == k_malha` e o fator vira 1,0 -- aplicar duas vezes
    # e' igual a aplicar uma. Sem esta guarda, a segunda passada multiplicaria o residuo por
    # 1,2047 de novo (+45% acumulado), e nada quebraria: os numeros continuariam plausiveis.
    k_antigo = _k_do_carimbo(censo.get(COL_CARIMBO)) or k_exato_do_censo_hex()

    out = censo.merge(malha, on="hex_id", how="left")
    tem_malha = out["renda_malha"].notna()

    fator = k_malha / k_antigo
    renda_antiga = pd.to_numeric(out.get(COL_RENDA), errors="coerce") * fator
    out[COL_RENDA] = out["renda_malha"].where(tem_malha, renda_antiga)
    if COL_SCORE in out.columns:
        out[COL_SCORE] = out["score_malha"].where(tem_malha, pd.to_numeric(out[COL_SCORE], errors="coerce"))

    out[COL_FONTE] = np.where(tem_malha, FONTE_MALHA, FONTE_REESCALADA)
    out[COL_CARIMBO] = f"multiplicativo_global_k={k_malha}"
    return out.drop(columns=["renda_malha", "score_malha", "k_malha"])


#: Procedencia dos hexagonos ADMITIDOS (nao apenas revalorados) pela malha.
FONTE_ORFAO_ADMITIDO = "malha_setorial_orfao_admitido"


def admitir_orfaos_da_malha(
    censo: pd.DataFrame,
    malha_path: Path = DEFAULT_OUTPUT_PATH,
) -> pd.DataFrame:
    """Cria linha de censo para hexagono que a malha cobre e o traco NAO tem.

    POR QUE. `sobrepor_renda_da_malha`, logo acima, tem contrato de "MUDA VALOR, NAO MUDA
    COBERTURA" e continua tendo -- esta funcao e' a outra metade, separada de proposito.
    A Fase A rodou em 2026-05-15 e nunca mais; a base H3 cresceu depois em tres eventos de
    criterio geometrico de borda (+5.305 centroide, +474 DEC-002, +4.107 DEC-003 =
    exatamente 9.886, batendo por UF em 27/27). Esses hexagonos nao tem LINHA nenhuma no
    traco censitario -- nao e' que o join foi ruim, e' que eles nao existiam quando ele
    rodou. Nenhuma regra de reclassificacao alcanca linha AUSENTE.

    5.612 deles a malha ja cobre (6,25 milhoes de habitantes), incluindo 11 de 11 em
    Fortaleza e 345 de 391 no Rio -- os casos que o operador reportou. Admiti-los aqui e'
    o conserto barato: nenhum join espacial e' refeito, so' se usa o que a DEC-045 ja
    calculou e materializou.

    NAO define `qualidade_join_uf`: eles genuinamente nao tem medida de join. Quem os
    promove a granular e' a nota de MUNICIPIO (BLK-JOINUF-01 mecanismo 1), pela mesma
    regra de todo mundo -- sem regua especial.

    Pura: nao muta `censo`. Sem o parquet da malha, devolve `censo` intacto.
    """
    if not Path(malha_path).exists() or "hex_id" not in censo.columns:
        return censo

    malha = pd.read_parquet(
        malha_path, columns=["hex_id", "uf", "pop_malha", "renda_malha", "score_malha"]
    )
    faltantes = malha[~malha["hex_id"].isin(set(censo["hex_id"]))]
    # So' entra quem a malha realmente mede: sem score nao ha sinal censitario, e admitir
    # linha vazia trocaria "sem dado" por "dado nulo" -- pior, porque some do radar.
    faltantes = faltantes[faltantes["score_malha"].notna()]
    if faltantes.empty:
        return censo

    novos = pd.DataFrame(
        {
            "hex_id": faltantes["hex_id"].to_numpy(),
            "uf": faltantes["uf"].to_numpy(),
            COL_SCORE: pd.to_numeric(faltantes["score_malha"], errors="coerce").to_numpy(),
            COL_RENDA: pd.to_numeric(faltantes["renda_malha"], errors="coerce").to_numpy(),
            "pop_total_setor_2022": pd.to_numeric(
                faltantes["pop_malha"], errors="coerce"
            ).to_numpy(),
            COL_FONTE: FONTE_ORFAO_ADMITIDO,
        }
    )
    if COL_CARIMBO in censo.columns:
        carimbo = censo[COL_CARIMBO].dropna()
        if not carimbo.empty:
            novos[COL_CARIMBO] = carimbo.iloc[0]
    return pd.concat([censo, novos], ignore_index=True)


#: Coluna de rotulo do orfao que NAO foi admitido -- o residuo declarado da DEC-055.
COL_MOTIVO_SEM_CENSO = "motivo_sem_censo"

#: Vocabulario FECHADO, de dois valores. SEM ACENTO por serem IDENTIFICADORES (CLAUDE.md
#: §2): o valor bruto viaja no parquet e no payload, e a versao acentuada e' camada de
#: LABEL de exibicao, do lado da tela. Acentuar aqui quebraria a comparacao por literal.
MOTIVO_SETOR_SEM_RENDA = "setor_sem_renda_publicada"
MOTIVO_SEM_SETOR_POVOADO = "sem_setor_povoado_no_hex"
MOTIVOS_SEM_CENSO = (MOTIVO_SETOR_SEM_RENDA, MOTIVO_SEM_SETOR_POVOADO)


def rotular_orfaos_sem_censo(
    censo: pd.DataFrame,
    universo: pd.Series | list[str] | None,
    malha_path: Path = DEFAULT_OUTPUT_PATH,
) -> pd.DataFrame:
    """Carimba `motivo_sem_censo` no orfao que a malha NAO consegue admitir.

    POR QUE. `admitir_orfaos_da_malha`, logo acima, recupera 5.600 linhas dos 9.886
    orfaos (4.970 sobrevivem ao merge com a base M1; 630 sao hexagonos que nem estao
    nela). Sobra um residuo VISIVEL de 4.916 hexagonos, e ate aqui o operador lia neles
    `"Nao informado"` -- que ele interpreta como falha do motor. Sao duas coisas
    diferentes, e ambas foram MEDIDAS no artefato vivo:

    - **642** tem hexagono na malha, mas o setor por baixo nao tem renda publicada pelo
      IBGE -- `score_malha` nulo, e por isso a admissao os recusa de proposito (linha
      sem score trocaria "sem dado" por "dado nulo"). Este grupo nunca tinha sido
      contado por ninguem: o backlog registrava o residuo como 4.274.
    - **4.274** nao tem hexagono nenhum na malha: nenhum setor POVOADO cai no centro
      da lasca de borda. Medido: eles NAO estao no mar (so' 6 de 4.916 sem setor
      algum embaixo) e NAO estao em municipio sem particao GEO (0 de 4.916).

    ROTULAR, NAO PROMOVER. A medicao do BLK-ORFAOS-01 fechou o veredito: o teto de um
    conserto perfeito e' 6.532 habitantes no pais inteiro (p50 de 0,02 hab por
    hexagono) e ZERO deles entraria na fila do funil. Completar `_candidatos` em
    `agregar_setores` para alcanca-los RENORMALIZARIA a fracao de area de cada setor e
    redistribuiria populacao para fora dos hexagonos interiores -- mexeria em
    `score_setor_2022_calibrado` NACIONALMENTE por 6.532 habitantes. Rejeitado.

    Funcao SEPARADA das outras duas de proposito, mesmo molde da DEC-055:
    `sobrepor_renda_da_malha` muda VALOR, `admitir_orfaos_da_malha` muda COBERTURA e
    esta so' carimba PROCEDENCIA -- nao escreve score, renda nem populacao em linha
    nenhuma.

    `universo` sao os `hex_id` da base M1 (o traco censitario, por construcao, NAO tem
    linha para quem se quer rotular). Sem ele, ou sem o parquet da malha no disco, a
    funcao e' no-op: rotular sem a malha nao teria como distinguir os dois motivos, e
    inventar um seria o defeito que este rotulo existe para consertar.

    Pura: nao muta `censo`, nao toca as linhas que ja existem. Idempotente -- na segunda
    passada os rotulados ja estao em `censo` e nada e' acrescentado.
    """
    if universo is None or "hex_id" not in censo.columns or not Path(malha_path).exists():
        return censo

    faltam = pd.Index(pd.Series(universo, dtype="object").dropna().astype(str).unique())
    faltam = faltam.difference(pd.Index(censo["hex_id"].dropna().astype(str).unique()))
    if faltam.empty:
        return censo

    malha = pd.read_parquet(malha_path, columns=["hex_id", "score_malha"])
    na_malha = pd.Index(malha["hex_id"].dropna().astype(str).unique())
    # Hexagono que a malha MEDE (score presente) e que mesmo assim nao esta no traco e'
    # caso de ADMISSAO, nao de rotulo -- provavelmente a admissao nem rodou. Carimba-lo
    # de "sem setor" seria afirmar o oposto do que a malha mostra, entao ele fica sem
    # rotulo: o vocabulario e' fechado e nao tem valor para "nao sei".
    medidos = pd.Index(malha.loc[malha["score_malha"].notna(), "hex_id"].dropna().astype(str).unique())
    faltam = faltam.difference(medidos)
    if faltam.empty:
        return censo

    novos = pd.DataFrame(
        {
            "hex_id": faltam.to_numpy(),
            COL_MOTIVO_SEM_CENSO: np.where(
                faltam.isin(na_malha), MOTIVO_SETOR_SEM_RENDA, MOTIVO_SEM_SETOR_POVOADO
            ),
        }
    )
    return pd.concat([censo, novos], ignore_index=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--geo-root", type=Path, default=DEFAULT_GEO_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--uf", action="append", default=None, help="limita a UFs (repetivel)")
    parser.add_argument(
        "--pop-hex",
        type=Path,
        default=Path("data/staging/hexagonos_mercado_mapeado.parquet"),
        help="artefato de onde vem `pop_total_setor_2022` (populacao do hexagono)",
    )
    args = parser.parse_args()

    caminhos = listar_particoes(args.geo_root, tuple(args.uf) if args.uf else None)
    if not caminhos:
        raise SystemExit(f"nenhuma particao em {args.geo_root}")
    print(f"particoes: {len(caminhos)}", flush=True)

    ilegiveis: list[Path] = []
    agg = agregar_particoes(caminhos, ilegiveis=ilegiveis)
    if ilegiveis:
        print(f"\nATENCAO: {len(ilegiveis)} particao(oes) ILEGIVEL(EIS) — os hexagonos desses")
        print("municipios ficam SEM censo neste artefato. Nao e' um aviso cosmetico:")
        for caminho in ilegiveis:
            print(f"  - {caminho}")
    pop_hex = None
    if args.pop_hex and args.pop_hex.exists():
        pop_hex = pd.read_parquet(args.pop_hex, columns=["hex_id", "pop_total_setor_2022"])
    resultado = anexar_score(agg, pop_hex)
    # `k` da malha vai JUNTO com a coluna que ele calibra. Guardar o numero e nao so' o
    # rotulo e' o que permite reescalar depois sem adivinhar: o carimbo do geo esta'
    # arredondado (`k=1.2335` para 1,2334632197).
    k_malha = k_exato_da_malha(args.geo_root)
    resultado["k_malha"] = k_malha
    resultado["metodo_calibracao_renda_malha"] = f"multiplicativo_global_k={k_malha}"

    args.output.parent.mkdir(parents=True, exist_ok=True)
    resultado.to_parquet(args.output, index=False)
    print(f"escrito: {args.output}  ({len(resultado):,} hexagonos)")
    print(json.dumps({
        "hexagonos": int(len(resultado)),
        "com_renda": int(resultado.renda_malha.notna().sum()),
        "populacao_total": float(resultado.pop_malha.sum()),
        "ufs": int(resultado.uf.nunique()),
    }, indent=2))


if __name__ == "__main__":
    main()
