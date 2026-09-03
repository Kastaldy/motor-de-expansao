"""Camada de servico da API (BLK-API-03) — FINA e READ-ONLY.

Resolve coordenada -> particao censitaria e delega ao motor (`censo_*`), sem
editar nada. Fluxo:
  1. ``(lat,lng)`` -> ``(uf, cod_municipio)`` por ponto-em-poligono na malha IBGE
     (`data/ibge/municipios_*.geojson`, parse puro com json + shapely; sem geopandas).
  2. ``read_censo_geo_partition(base_dir, uf, cod_municipio)`` -> ``setores_df``.
  3. ``analisar_ponto_censitario_setores(lat, lng, setores_df)`` -> ``result`` (KPIs).
  4. monta o dict de resposta com carimbo de versao (Decisao 6).

So importa `censo_*`; nunca os edita. Os imports do motor (pandas/pyproj) sao
LAZY, dentro de `analisar_ponto`, para nao pesar a subida do app.
"""

from __future__ import annotations

import json
import unicodedata
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from shapely import STRtree
from shapely.geometry import Point, shape

from motor_expansao.api import __version__
from motor_expansao.api.errors import APIError
from motor_expansao.api.settings import Settings
from motor_expansao.perfil import resolver_perfil

# Nome da coluna de score setorial usada nos KPIs (carimbo `versao_score`).
_VERSAO_SCORE = "score_setor_2022_calibrado"

# Resolvido UMA vez, no import — mesmo padrao de `coord.py`/`maps_geocoder.py` (DEC-047).
# So' usado para NOMEAR a fonte de censo e o pais nas mensagens de erro abaixo; a malha
# em si continua vindo de `settings.ibge_dir`, que e' o que muda por instancia.
_PERFIL = resolver_perfil()


# Tolerancia do "encoste" na malha municipal, em GRAUS (~0.018 deg ~ 2 km no Brasil).
# Motivo: a malha IBGE e um recorte de TERRA; um ponto legitimo pode cair num vao dela —
# na agua a poucas centenas de metros da praia (orla), numa lagoa/represa, ou na fresta
# entre dois poligonos vizinhos. Sem tolerancia, `within` estrito devolve None e o usuario
# recebe "Coordenada fora do Brasil" para um endereco que existe (ex.: Janga/Paulista-PE).
# 2 km cobre o pior caso do centroide de um hex res-7 (circunraio ~1,5 km) sem alcançar o
# municipio errado do outro lado de uma baia.
_TOLERANCIA_MALHA_GRAUS = 0.018


class _MalhaMunicipal:
    """Indice espacial (STRtree) dos municipios IBGE para resolver ponto->municipio."""

    def __init__(self, tree: STRtree, meta: list[tuple[str, str]], geoms: list) -> None:
        self._tree = tree
        self._meta = meta  # lista paralela de (uf, cod_municipio)
        self._geoms = geoms  # lista paralela de geometrias (p/ medir a distancia do encoste)

    def resolver(self, lat: float, lng: float) -> tuple[str, str] | None:
        ponto = Point(lng, lat)  # GeoJSON/shapely usam (x=lng, y=lat)
        # 1) Caminho exato: STRtree avalia predicate(ponto, poligono); queremos
        # poligono.contains(ponto), equivalente a ponto.within(poligono) -> "within".
        for idx in self._tree.query(ponto, predicate="within"):
            return self._meta[int(idx)]
        # 2) Encoste: nenhum poligono CONTEM o ponto (orla/lagoa/fresta da malha). Cai no
        # municipio mais proximo, desde que dentro da tolerancia. Fora dela -> None (ex.:
        # oceano aberto, pais vizinho), preservando a rejeicao de coordenada realmente fora.
        try:
            idx = self._tree.nearest(ponto)
        except Exception:  # arvore vazia / shapely sem `nearest` -> comportamento antigo
            return None
        if idx is None:
            return None
        i = int(idx)
        if self._geoms[i].distance(ponto) <= _TOLERANCIA_MALHA_GRAUS:
            return self._meta[i]
        return None


@lru_cache(maxsize=4)
def _carregar_malha(ibge_dir_str: str) -> _MalhaMunicipal:
    """Carrega e indexa a malha municipal IBGE uma vez por processo (cacheado)."""
    ibge_dir = Path(ibge_dir_str)
    geoms: list[object] = []
    meta: list[tuple[str, str]] = []
    for gj in sorted(ibge_dir.glob("municipios_*.geojson")):
        uf = gj.stem.split("_", 1)[1].upper()  # municipios_SP -> SP
        try:
            data = json.loads(gj.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for feat in data.get("features", []):
            props = feat.get("properties") or {}
            cod = str(
                props.get("codarea")
                or props.get("CD_MUN")
                or props.get("cod_municipio")
                or ""
            ).strip()
            geom = feat.get("geometry")
            if not cod or not geom:
                continue
            try:
                geoms.append(shape(geom))
                meta.append((uf, cod))
            except Exception:  # geometria malformada -> ignora o municipio
                continue
    if not geoms:
        # Ate' 2026-09-03 esta mensagem cravava "IBGE" — verdade para o Brasil, falsa em
        # qualquer outra instancia. A Argentina nao materializa `ibge/municipios_*.geojson`
        # ainda (o Relatorio Pontual dela e' trabalho futuro), e o operador via um erro que
        # citava o instituto de OUTRO pais.
        raise APIError(
            500,
            f"Malha municipal ({_PERFIL.fontes.censo.nome}) ausente ou vazia",
            "erro_interno",
        )
    return _MalhaMunicipal(STRtree(geoms), meta, geoms)


def _resolver_e_carregar(lat: float, lng: float, settings: Settings):
    """Resolve ``(uf, cod_municipio)`` e carrega ``setores_df``. Levanta 400/404."""
    malha = _carregar_malha(str(settings.ibge_dir))
    resolvido = malha.resolver(lat, lng)
    if resolvido is None:
        # Mensagem PRECISA: o que falhou foi o ponto-em-poligono na malha municipal, nao o
        # bounding box do Brasil (esse fica em `coord.validar_brasil`). Dizer "fora do Brasil"
        # para um ponto a 2 km da costa confundia o operador (relato de Felipe em 2026-07-24).
        # "de" e nao "do"/"da" antes do nome do pais, de proposito (mesma convencao de
        # `coord.ForaDoPaisError`): sidesteps o genero gramatical sem precisar carrega-lo
        # no perfil.
        raise APIError(
            400,
            f"Coordenada fora da malha municipal do {_PERFIL.fontes.censo.nome} (mar "
            f"aberto, fora de {_PERFIL.nome} ou a mais de 2 km de qualquer municipio)",
            "coordenada_invalida",
        )
    uf, cod_municipio = resolvido

    # Import adiado ate' AQUI (e nao no topo da funcao): o ramo 400 acima nao precisa do
    # motor de censo, e adiar evita puxar a cadeia dashboard.data -> dashboard.schemas ->
    # h3 so' para levantar um erro de coordenada. Mesmo espirito dos imports LAZY do
    # modulo (ver docstring do topo do arquivo).
    from motor_expansao.dashboard.data import read_censo_geo_partition

    setores_df = read_censo_geo_partition(settings.censo_geo_dir, uf, cod_municipio)
    if setores_df is None or setores_df.empty:
        raise APIError(
            404,
            f"Materialize setores_censitarios_2022_geo/ para {uf}/{cod_municipio}",
            "base_geo_ausente",
        )
    return uf, cod_municipio, setores_df


def _nome_municipio_de(setores_df) -> str | None:
    """Nome do municipio a partir do proprio `setores_df` (rotulo do painel de perfil).

    O dashboard tira isto do `context`; a API nao tem esse dicionario, mas a particao geo
    ja traz a coluna. Gracioso: parquet antigo sem a coluna -> `None` (o painel omite o
    "Municipio/UF", sem quebrar o resto).
    """
    if setores_df is None or "nome_municipio" not in setores_df.columns:
        return None
    valores = setores_df["nome_municipio"].dropna()
    return str(valores.iloc[0]) if not valores.empty else None


# --- camada de mercado/SAM + concorrentes + Ultra (opcional) ----------------

_SAM_COLS = [
    "score_oportunidade_residual",
    "oferta_efetiva_disponivel",
    "sam_fitness_potencial",
    "oferta_consumida_mercado_estimada",
]


@lru_cache(maxsize=4)
def _carregar_pontos(path_str: str, colunas: tuple[str, ...]):
    """Carrega um parquet pequeno (concorrentes/Ultra) com as colunas dadas; None se ausente."""
    import pandas as pd

    path = Path(path_str)
    if not path.is_file():
        return None
    try:
        return pd.read_parquet(path, columns=list(colunas))
    except Exception:
        return None


# --- oferta unida do Relatorio Pontual (DEC-046) -----------------------------
#
# Ate' a DEC-046 a oferta vinha SO' de `concorrentes_mapeados.parquet`, que e' um cadastro
# de CADEIAS: 4.499 pontos, 104 redes, ZERO independentes -- por construcao (DEC-033), nao
# por falha de coleta. Medido: 53,46% dos enderecos urbanos do pais devolviam ZERO
# concorrente em 1 km, e 13 das 40 maiores cidades saiam zeradas no centro.
#
# A uniao das 3 fontes corrige a COBERTURA. A coluna `classe` e' o que impede a correcao de
# INVERTER o criterio PASS/FAIL da ficha: com o universo indo de 4,5 mil para ~24,5 mil
# pontos, um teto absoluto de 3 reprovaria 70% das pracas onde a propria Ultra opera hoje
# (medido: 27 -> 105 das 150 unidades). Por isso a ficha le `n_concorrentes_cadeia`
# (regua INTACTA) e o total entra como fato exibido -- D2/D3 da DEC-046.
#
# Identificadores CRUS, sem acento (regra do CLAUDE.md secao 2): sao comparados em codigo
# e em teste.
#
# A FONTE CANONICA do vocabulario e' `dashboard.censo_point` (o motor define, a API produz
# conforme). Aqui sao repetidos como literais, e nao importados, porque o import do motor e'
# LAZY neste modulo de proposito -- ele puxa pandas/pyproj e so' deve custar isso no caminho
# de analise. A igualdade entre os dois pares e' travada por
# `test_classe_da_oferta_casa_com_o_vocabulario_do_motor`, para a duplicacao nao driftar.
CLASSE_CADEIA = "cadeia"
CLASSE_INDEPENDENTE = "independente"

FONTE_MAPEADOS = "concorrentes_mapeados"
FONTE_REDES_AGREGADOR = "vulnerabilidade_ma_redes"
FONTE_INDEPENDENTES = "vulnerabilidade_ma_nomeadas"
FONTES_OFERTA = (FONTE_MAPEADOS, FONTE_REDES_AGREGADOR, FONTE_INDEPENDENTES)

# D5 da DEC-046: independente colapsa contra QUALQUER cadeia a <= 50 m. Reusa o piso da
# DEC-034 e NAO casa nome -- independente nao tem `rede` com que casar.
_DEDUP_INDEPENDENTE_M = 50.0

_COLS_OFERTA = ["rede", "nome", "lat", "lng", "classe"]


def _ler_fonte_oferta(path: Path, obrigatorias: tuple[str, ...], opcionais: tuple[str, ...]):
    """Le um parquet de oferta projetando SO' as colunas que existem no schema.

    `read_parquet(columns=[...])` levanta quando uma coluna nao existe, e um `except` no
    chamador transformaria isso em "fonte ausente": a fonte INTEIRA sumiria em silencio por
    causa de uma coluna opcional. E' a forma do defeito que a DEC-038 pagou caro (a coluna
    existia, so' nao chegava, e o sintoma era campo vazio sem erro nenhum).

    Devolve `None` quando o arquivo falta ou quando falta coluna OBRIGATORIA -- os dois
    casos sao "esta fonte nao entrou", e quem chama registra isso em `fontes_unidas`.
    """
    import pandas as pd
    import pyarrow.parquet as pq

    if not path.is_file():
        return None
    try:
        disponiveis = set(pq.read_schema(path).names)
        if not set(obrigatorias).issubset(disponiveis):
            return None
        extras = [c for c in opcionais if c in disponiveis]
        return pd.read_parquet(path, columns=[*obrigatorias, *extras])
    except Exception:
        return None


@lru_cache(maxsize=2)
def _oferta_unida(staging_dir_str: str):
    """(df_oferta, fontes_presentes) — uniao das 3 fontes, com `classe` por linha.

    READ-ONLY: nao escreve nada e nao recalcula artefato do M1. O custo e' UNICO por
    processo (`lru_cache`): ~575 ms a frio para 24.314 pontos e 0,004 ms quente — a dedup
    espacial da cKDTree domina o custo a frio. Medido em 2026-09-01.

    `fontes_presentes` e' o que sustenta o D7 da DEC-046: sem ele, fonte ausente vira
    contagem menor, contagem menor vira PASS no criterio de concorrencia, e um ponto
    saturado e' APROVADO por ausencia de dado com o PDF de aparencia normal.
    """
    import pandas as pd

    staging = Path(staging_dir_str)
    presentes: list[str] = []
    partes: list[pd.DataFrame] = []

    # (1) CADEIAS mapeadas. `status_registro` filtra o que a coleta ja' descartou -- a
    # funcao irma do piloto (`_carregar_concorrentes`) sempre filtrou e esta NAO, o que
    # fazia o mesmo processo responder 77 concorrentes num ponto do Rio onde ha 11
    # validos (64 `bodytech` empilhadas numa unica coordenada). D4 da DEC-046.
    mapeados = _ler_fonte_oferta(
        staging / f"{FONTE_MAPEADOS}.parquet",
        ("rede", "lat", "lng"),
        ("nome_unidade", "status_registro", "flag_coord_valida"),
    )
    if mapeados is not None:
        presentes.append(FONTE_MAPEADOS)
        if "status_registro" in mapeados.columns:
            mapeados = mapeados[mapeados["status_registro"].astype(str) == "valido"]
        if "flag_coord_valida" in mapeados.columns:
            mapeados = mapeados[mapeados["flag_coord_valida"].fillna(True).astype(bool)]
        partes.append(
            pd.DataFrame({
                "rede": mapeados["rede"].astype("string"),
                "nome": (
                    mapeados["nome_unidade"].astype("string")
                    if "nome_unidade" in mapeados.columns
                    else pd.Series([pd.NA] * len(mapeados), dtype="string")
                ),
                "lat": pd.to_numeric(mapeados["lat"], errors="coerce"),
                "lng": pd.to_numeric(mapeados["lng"], errors="coerce"),
                "classe": CLASSE_CADEIA,
            })
        )

    # (2) Unidades de REDE que o agregador lista. `tem_pin_proprio` ja' carrega a dedup da
    # DEC-034 MATERIALIZADA na geracao: quem e' False colapsa contra um ponto ja' mapeado e
    # nao pode ganhar pin proprio, senao volta o pin duplicado que a DEC-034 existe para
    # impedir. Ausencia da coluna -> entra tudo (artefato antigo; e' o comportamento
    # conservador, porque a alternativa seria descartar a fonte inteira).
    redes = _ler_fonte_oferta(
        staging / f"{FONTE_REDES_AGREGADOR}.parquet",
        ("rede", "lat", "lng"),
        ("nome", "tem_pin_proprio"),
    )
    if redes is not None:
        presentes.append(FONTE_REDES_AGREGADOR)
        if "tem_pin_proprio" in redes.columns:
            redes = redes[redes["tem_pin_proprio"].fillna(False).astype(bool)]
        partes.append(
            pd.DataFrame({
                "rede": redes["rede"].astype("string"),
                "nome": (
                    redes["nome"].astype("string")
                    if "nome" in redes.columns
                    else pd.Series([pd.NA] * len(redes), dtype="string")
                ),
                "lat": pd.to_numeric(redes["lat"], errors="coerce"),
                "lng": pd.to_numeric(redes["lng"], errors="coerce"),
                "classe": CLASSE_CADEIA,
            })
        )

    cadeias = (
        pd.concat(partes, ignore_index=True) if partes else pd.DataFrame(columns=_COLS_OFERTA)
    )
    cadeias = cadeias.dropna(subset=["lat", "lng"])

    # (3) INDEPENDENTES. Nao tem coluna `rede` — e' o que as define, e e' de onde a `classe`
    # sai por construcao, sem heuristica de nome.
    indep = _ler_fonte_oferta(
        staging / f"{FONTE_INDEPENDENTES}.parquet", ("nome", "lat", "lng"), ()
    )
    if indep is not None:
        presentes.append(FONTE_INDEPENDENTES)
        indep = pd.DataFrame({
            "rede": pd.Series([pd.NA] * len(indep), dtype="string"),
            "nome": indep["nome"].astype("string"),
            "lat": pd.to_numeric(indep["lat"], errors="coerce"),
            "lng": pd.to_numeric(indep["lng"], errors="coerce"),
            "classe": CLASSE_INDEPENDENTE,
        }).dropna(subset=["lat", "lng"])
        indep = _dedup_independentes(indep, cadeias)
    else:
        indep = pd.DataFrame(columns=_COLS_OFERTA)

    # Concat so' do que tem linha: o pandas depreciou concatenar frame vazio (o dtype dele
    # entra na inferencia do resultado) e isso emitiria FutureWarning em toda chamada.
    vivos = [parte for parte in (cadeias, indep) if not parte.empty]
    if not vivos:
        return None, tuple(presentes)
    unida = pd.concat(vivos, ignore_index=True)
    return unida[_COLS_OFERTA].reset_index(drop=True), tuple(presentes)


def _dedup_independentes(indep, cadeias):
    """Descarta independente a <= `_DEDUP_INDEPENDENTE_M` de QUALQUER cadeia (D5, DEC-046).

    Sem indice espacial isto seria 19.329 x 5.217 pares -- ~100 milhoes, centenas de MB.
    A cKDTree sobre coordenadas cartesianas na esfera resolve em milissegundos e o raio
    vira a CORDA equivalente ao arco de 50 m (a diferenca corda/arco a 50 m e' de ordem
    1e-11 do raio da Terra: irrelevante, e para MENOS, entao nunca colapsa a mais).
    """
    import numpy as np

    if indep.empty or cadeias.empty:
        return indep

    from scipy.spatial import cKDTree

    def _xyz(lat, lng):
        la, lo = np.radians(np.asarray(lat, dtype=float)), np.radians(np.asarray(lng, dtype=float))
        return np.column_stack((np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)))

    raio_terra_m = 6_371_000.0
    corda = 2.0 * np.sin(_DEDUP_INDEPENDENTE_M / (2.0 * raio_terra_m))
    arvore = cKDTree(_xyz(cadeias["lat"], cadeias["lng"]))
    vizinho = arvore.query_ball_point(_xyz(indep["lat"], indep["lng"]), r=corda)
    manter = np.array([len(v) == 0 for v in vizinho], dtype=bool)
    return indep.loc[manter]


def fontes_oferta_presentes(settings: Settings) -> tuple[str, ...]:
    """Quais das 3 fontes de oferta foram efetivamente lidas. Sustenta o D7 da DEC-046."""
    _df, presentes = _oferta_unida(str(settings.staging_dir))
    return presentes


def _competitors_ultra(settings: Settings):
    """(competitors_df, ultra_df) da staging, ou (None, None) se ausente. READ-ONLY.

    Desde a DEC-046 `competitors_df` e' a UNIAO das 3 fontes de oferta, com a coluna
    `classe` distinguindo `cadeia` de `independente`. A aridade e o contrato de `None`
    ficam INTACTOS de proposito: dois testes monkeypatcham esta funcao com
    `lambda cfg: (None, None)` e as 3 rotas do piloto a chamam desempacotando um par.
    Quem precisa saber QUAIS fontes entraram usa `fontes_oferta_presentes`.
    """
    comp, _presentes = _oferta_unida(str(settings.staging_dir))
    ultra = _carregar_pontos(
        str(settings.staging_dir / "unidades_ultra_mapeadas.parquet"), ("lat", "lng")
    )
    return comp, ultra


def _residual_do_ponto(lat: float, lng: float, settings: Settings) -> dict:
    """SAM/residual do hex H3 (res 7) do ponto, sem carregar a base de 1,5M.

    Espelha `lookup_hex_by_coord` (h3.latlng_to_cell + match por hex_id), filtrando
    direto no parquet de mercado (1 linha). READ-ONLY; nao recalcula nada do M1.
    """
    residual: dict[str, float | None] = {k: None for k in _SAM_COLS}
    mercado = Path(settings.staging_dir / "hexagonos_mercado_mapeado.parquet")
    if not mercado.is_file():
        return residual
    try:
        import h3
        import pyarrow.compute as pc
        import pyarrow.dataset as ds

        cell = h3.latlng_to_cell(lat, lng, 7)
        tbl = ds.dataset(mercado).to_table(
            filter=pc.field("hex_id") == cell, columns=["hex_id", *_SAM_COLS]
        )
        if tbl.num_rows:
            row = tbl.slice(0, 1).to_pylist()[0]
            for k in _SAM_COLS:
                v = row.get(k)
                if v is not None:
                    residual[k] = float(v)
    except Exception:
        pass
    return residual


def _hexes_vizinhos_do_ponto(lat: float, lng: float, settings: Settings, k: int = 5):
    """Hexes H3 (res 7) do disco de raio `k` em torno do ponto, com o valor de cada camada hex.

    Espelha `_residual_do_ponto`: filtra direto no parquet de mercado por um conjunto pequeno de
    chaves (91 hexes em k=5) e poucas colunas -> leitura barata, NAO carrega a base de 1,5 M.
    Insumo dos choropleths POR HEXAGONO do slide-hero: Residual Fitness (`oferta_efetiva_disponivel`,
    BLK-RELPON-10) e Socioeconomia (`score_setor_2022_calibrado`, BLK-RELPON-13). READ-ONLY; nao
    recalcula nada do M1. Devolve `None` (fallback gracioso -> camada ausente no PDF) em qualquer falha.
    """
    mercado = Path(settings.staging_dir / "hexagonos_mercado_mapeado.parquet")
    if not mercado.is_file():
        return None
    try:
        import h3
        import pyarrow.compute as pc
        import pyarrow.dataset as ds

        dataset = ds.dataset(mercado)
        # Servir tambem `score_setor_2022_calibrado` quando existir: a partir do BLK-RELPON-13 o
        # painel Socioeconomia do hero e desenhado por hexagono e depende dessa coluna estar no
        # `hexes_df`. Sem ela (parquet antigo), a camada cai no fallback textual em vez de crashar.
        disponiveis = set(dataset.schema.names)
        colunas = ["hex_id", "oferta_efetiva_disponivel"]
        if "score_setor_2022_calibrado" in disponiveis:
            colunas.append("score_setor_2022_calibrado")

        centro = h3.latlng_to_cell(lat, lng, 7)  # 7 = H3_RESOLUTION (M1), LIDO
        celulas = list(h3.grid_disk(centro, k))
        tbl = dataset.to_table(
            filter=pc.field("hex_id").isin(celulas),
            columns=colunas,
        )
        if not tbl.num_rows:
            return None
        return tbl.to_pandas()
    except Exception:
        return None


def analisar_ponto(lat: float, lng: float, consumidor: str | None, settings: Settings) -> dict:
    """Executa o estudo do ponto e devolve o dict de KPIs (-> `AnalisarResponseJSON`).

    Levanta `APIError`: 400 (ponto sem municipio), 404 (base geo ausente).
    """
    # Import lazy do motor (puxa pandas/pyproj) — so no caminho de analise.
    from motor_expansao.dashboard.censo_point import (
        RAIO_CENSITARIO_DEFAULT_KM,
        analisar_ponto_censitario_setores,
    )

    _uf, _cod, setores_df = _resolver_e_carregar(lat, lng, settings)

    comp_df, ultra_df = _competitors_ultra(settings)
    result = analisar_ponto_censitario_setores(
        lat, lng, setores_df, raio_km=RAIO_CENSITARIO_DEFAULT_KM,
        competitors_df=comp_df, ultra_df=ultra_df,
    )

    return {
        "lat": lat,
        "lng": lng,
        "raio_km": result.get("raio_km", RAIO_CENSITARIO_DEFAULT_KM),
        "area_km2": result.get("area_km2"),
        "metodo": result.get("metodo"),
        "n_setores": result.get("n_setores", 0),
        "pop_total_raio": result.get("pop_total_raio"),
        "renda_per_capita_media_raio": result.get("renda_per_capita_media_raio"),
        "renda_media_domiciliar_raio": result.get("renda_media_domiciliar_raio"),
        "renda_domiciliar_total_raio": result.get("renda_domiciliar_total_raio"),
        "domicilios_total_raio": result.get("domicilios_total_raio"),
        "metodo_renda_domiciliar_raio": result.get("metodo_renda_domiciliar_raio"),
        # ADITIVO (2026-08-14): fracao (0-1) do raio cuja renda depende de uplift
        # EXTRAPOLADO — a ressalva de leitura cautelosa que antes morria no result.
        "fracao_uplift_extrapolado_raio": result.get("fracao_uplift_extrapolado_raio"),
        "densidade_pop_raio_hab_km2": result.get("densidade_pop_raio_hab_km2"),
        "score_setor_medio": result.get("score_setor_medio"),
        "score_setor_max": result.get("score_setor_max"),
        # DEC-046 (emenda a DEC-005): `n_concorrentes` MANTEM o nome e passa a valer o TOTAL
        # de academias no raio (cadeia + independente). Quem decide veredito le
        # `n_concorrentes_cadeia`; `fontes_oferta` diz de quais das 3 fontes o numero saiu,
        # para que fonte ausente nao vire contagem menor sem ninguem perceber.
        "n_concorrentes": result.get("n_concorrentes", 0),
        "n_concorrentes_cadeia": result.get("n_concorrentes_cadeia", 0),
        "n_academias_total": result.get("n_academias_total", 0),
        "fontes_oferta": list(fontes_oferta_presentes(settings)),
        "oferta_completa": set(fontes_oferta_presentes(settings)) == set(FONTES_OFERTA),
        "n_ultra": result.get("n_ultra", 0),
        "versao_contrato": __version__,
        "versao_score": _VERSAO_SCORE,
        "gerado_em": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "consumidor": consumidor,
    }


def _reuse_contextily_session() -> None:
    """Faz o contextily reusar UMA `requests.Session` (pool de conexao) ao buscar
    tiles, em vez de abrir uma conexao HTTPS NOVA por tile (`tile.py` usa
    `requests.get` direto). Cada conexao nova re-parseava o bundle `certifi`
    (~450 ms de CPU); em area densa sao ~200 tiles -> ~90 s desperdicados. Com a
    sessao unica o cert carrega ~1x e o PDF cai de ~117 s para ~24 s.

    Idempotente, best-effort (se contextily nao estiver instalado, nao faz nada).
    READ-ONLY sobre o M1: so muda como os tiles sao baixados, nao o relatorio.
    """
    try:
        import contextily.tile as _ct  # lazy: so com o extra [basemap]

        if getattr(_ct, "_ultra_session_reused", False):
            return
        import requests

        _sess = requests.Session()

        class _ReqShim:
            """Encaminha `.get` para a sessao (pool) e o resto para o modulo requests."""

            def get(self, *args, **kwargs):
                return _sess.get(*args, **kwargs)

            def __getattr__(self, name):
                return getattr(requests, name)

        _ct.requests = _ReqShim()
        _ct._ultra_session_reused = True
    except Exception:
        pass


def gerar_pdf_ponto(
    lat: float,
    lng: float,
    consumidor: str | None,
    settings: Settings,
    *,
    rotulo: str | None = None,
) -> bytes:
    """Gera o PDF de 8 paginas do Relatorio Pontual Censitario (BLK-API-04).

    Enriquecido (READ-ONLY): mapas com *ruas* (basemap online, DEC-004) + pins de
    concorrentes/Ultra, e Big Numbers de SAM/residual via `residual`. Fallback
    gracioso para `basemap=False` se a busca de tiles falhar (offline).

    BLK-RELPON-14: a pagina "Imagem do Entorno" (mapa de quadra) saiu do gerador ->
    o PDF base caiu de 8 para 7 paginas. Aqui nada mais precisava mudar: a API nunca
    montou essa camada a mao (ela vinha pronta do dict de `render_mapas_censitarios_combinados`).

    `rotulo`: nome do endereco/estabelecimento para a capa (no lugar de "Coordenada: ...").
    """
    _reuse_contextily_session()  # acelera a busca de tiles (~117s -> ~24s em area densa)

    from motor_expansao.dashboard.censo_map import render_mapas_censitarios_combinados
    from motor_expansao.dashboard.censo_point import (
        RAIO_CENSITARIO_DEFAULT_KM,
        agregar_perfil_bairro_distrito,
        analisar_ponto_censitario_setores,
    )
    from motor_expansao.dashboard.censo_report import gerar_pdf_relatorio_pontual_classico

    uf, _cod, setores_df = _resolver_e_carregar(lat, lng, settings)
    comp_df, ultra_df = _competitors_ultra(settings)
    result = analisar_ponto_censitario_setores(
        lat, lng, setores_df, raio_km=RAIO_CENSITARIO_DEFAULT_KM,
        competitors_df=comp_df, ultra_df=ultra_df,
    )
    # BLK-RELPON-07: sem este agregado o slide "Perfil do Bairro/Distrito" cai no
    # default gracioso (`flag_perfil_disponivel=False`) e sai `TEXTO_SEM_DADO` -- era o estado
    # do PDF do bot ate aqui. O dashboard (pages.py) ja fazia esta chamada; a API nao.
    # `nome_municipio`/`uf` sao so rotulos do painel: o agregado resolve por
    # `cod_bairro` (ou `nome_distrito` no fallback) sobre o proprio `setores_df`.
    perfil_bairro = agregar_perfil_bairro_distrito(
        setores_df,
        cod_bairro=result.get("cod_bairro_ponto"),
        nome_bairro=result.get("nome_bairro_ponto"),
        nome_distrito=result.get("nome_distrito_ponto"),
        nome_municipio=_nome_municipio_de(setores_df),
        uf=uf,
    )

    ultra_dir = settings.ultra_dir if Path(settings.ultra_dir).is_dir() else None
    # Pasta de logos das concorrentes (logo_<rede>.png). Com ela, os pins do mapa de
    # Concorrentes mostram o LOGO da rede; sem ela, caem em sigla de texto.
    # Guard explícito: evita Path(None).is_dir() que lança TypeError.
    logos_dir = (
        settings.competitors_logos_dir
        if settings.competitors_logos_dir is not None
        and Path(settings.competitors_logos_dir).is_dir()
        else None
    )

    # BLK-RELPON-10: insumo do choropleth de Residual Fitness (slide-hero). Na API nao ha `df`
    # em escopo como no dashboard -> le so o disco de 91 hexes do parquet de mercado. None ->
    # camada `residual` ausente -> fallback textual no slide (offline-safe). READ-ONLY.
    hexes_df = _hexes_vizinhos_do_ponto(lat, lng, settings)

    def _mapas(basemap: bool):
        return render_mapas_censitarios_combinados(
            lat, lng, setores_df, raio_km=RAIO_CENSITARIO_DEFAULT_KM,
            competitors_df=comp_df, ultra_df=ultra_df,
            basemap=basemap, ultra_logo_dir=ultra_dir, logos_dir=logos_dir,
            hexes_df=hexes_df,
            # Arruamento mais visivel sob o choropleth: resgata tambem as ruas
            # residenciais CINZA-CLARAS do Voyager (ceil 160->215) e deixa a cor das
            # faixas mais translucida (alpha 140->110). So a API ajusta isto; o dashboard
            # segue com os defaults do modulo. (Diagnostico Parque Bosque Maia, 2026-06-12.)
            # SEM `choropleth_alpha`: o default do modulo vale para API/bot, piloto e
            # dashboard (DEC-021). O 110 daqui existia para as ruas aparecerem por baixo
            # da cor — o overlay do BLK-BASEMAP-06 as desenha POR CIMA desde entao.
            street_ceil=215, street_gain=1.3, street_cap=200,
        )

    # Tenta com ruas (online); cai para offline; em ultimo caso, sem mapas.
    try:
        mapas = _mapas(True)
    except Exception:
        try:
            mapas = _mapas(False)
        except Exception:
            mapas = None

    # TESTE (BLK-SAT, ainda NAO definitivo): foto de satelite do ponto (Esri, z18/z19
    # conforme disponibilidade) entrando na pagina "Fotos do Imovel" que ja existe.
    # `render_foto_satelite_ponto` devolve None se a rede falhar -> o PDF sai igual ao
    # de hoje, sem a pagina. Nao altera nenhum numero do relatorio.
    from motor_expansao.dashboard.censo_map import render_foto_satelite_ponto

    # Chave do ArcGIS Location Platform via settings (env API_ARCGIS_API_KEY). Sem
    # ela, o render devolve None e o PDF sai sem a pagina de satelite (DEC-018).
    foto_sat = render_foto_satelite_ponto(lat, lng, api_key=settings.arcgis_api_key or None)

    residual = _residual_do_ponto(lat, lng, settings)
    # Variante "Apresentacao Classica Ultra" (BLK-EST-05): a API/bot espelha o
    # MESMO modelo que o dashboard passou a gerar por padrao (pages.py usa
    # template="classico"). Com o BLK-RELPON-14 a classica virou o gerador UNICO
    # do Pontual (a `_censitario` e so um wrapper deprecado) — esta chamada ja
    # aponta para o lugar certo e NAO deve migrar.
    #
    # PAGINAS OPCIONAIS QUE FICAM DE FORA AQUI (`viabilidade`, `info_imovel`, `fotos`):
    # os insumos NAO existem neste escopo, entao nao ha o que repassar — e fabricar
    # valores falsearia o relatorio. O que faltaria para habilita-las:
    #   - `viabilidade`: exige metragem/aluguel/ticket do imovel + `gerar_serie_mensal`
    #     e `montar_payload_viabilidade` (fluxo da aba Viabilidade do dashboard, que
    #     guarda `viab_relatorio_ctx` em `session_state`). Nada disso chega na rota.
    #   - `info_imovel`: mesma origem (formulario de endereco/valor/pe-direito/vagas).
    #   - `fotos`: upload de arquivo; o request da API e JSON e nao carrega binario.
    # Habilitar exigiria ESTENDER `AnalisarRequest` (campos do imovel + fotos em
    # base64/multipart) e propagar por `routes/analisar.py` -> `gerar_pdf_ponto`.
    # Decisao: fora do escopo do BLK-RELPON-14; o PDF do bot segue com as 8 paginas
    # base + a vista aerea.
    #
    # BLK-CONC-ESTUDO: a pagina de CONCLUSAO passou a sair TAMBEM sem `viabilidade`, em
    # modo so-estudo -- metas censitarias do raio e leitura de mercado do hexagono, SEM os
    # gates de imovel e de retorno. Este e' o UNICO ponto do sistema que liga o flag: o
    # piloto web chama a mesma funcao sem ele e segue com as 7 paginas de antes quando o
    # operador nao preenche a Viabilidade (escopo fechado por Juan em 2026-08-12).
    return gerar_pdf_relatorio_pontual_classico(
        result, mapas, residual=residual, perfil_bairro=perfil_bairro, ultra_dir=ultra_dir,
        solicitante=consumidor, rotulo=rotulo, foto_satelite=foto_sat,
        # API/bot nao tem upload de fotos do imovel -> a vista aerea e a unica imagem
        # da pagina e usa a area de conteudo inteira (no dashboard fica no tamanho padrao).
        foto_satelite_grande=True,
        conclusao_so_estudo=True,
    )


# ===========================================================================
# Relatorio Municipal (BLK-RELMUN) — PDF de 9 paginas por municipio.
#
# Diferente do Pontual: agrega TODOS os hexes de UM municipio (nao um raio de
# ponto). Fonte = `hexagonos_mercado_mapeado.parquet` (1,5M hexes). Opcao A de
# RAM: a base inteira e carregada 1x por processo (~1,9 GB residente) e as
# consultas por municipio sao fatias baratas. READ-ONLY sobre o M1 — reusa o
# gerador do dashboard (`relatorio_municipal`), sem recalcular score/mercado.
# ===========================================================================

_MERCADO_PARQUET = "hexagonos_mercado_mapeado.parquet"


def _norm(texto: object) -> str:
    """Normaliza para casar municipio: sem acento, sem espaco nas pontas, casefold."""
    s = unicodedata.normalize("NFKD", str(texto))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.strip().casefold()


def _normalizar_cod(valor: object) -> str | None:
    """cod_municipio pode vir como float/int/str; devolve string de digitos ou None.

    NaN precisa virar None EXPLICITAMENTE: `str(float("nan"))` e' `"nan"`, uma string
    verdadeira que passa no `if cod:` do chamador e vai procurar a particao
    `cod_municipio=nan/` -- que nunca existe. O sintoma seria o relatorio sair mudo,
    sem bairro nenhum, como se o municipio nao tivesse.
    """
    if valor is None:
        return None
    if isinstance(valor, float) and valor != valor:  # NaN
        return None
    s = str(valor).strip()
    if s.endswith(".0"):
        s = s[:-2]
    if not s or s.casefold() in {"nan", "none", "<na>"}:
        return None
    return s


def _primeiro_cod_municipio(df_muni: object) -> object:
    """1o `cod_municipio` nao-nulo do slice do municipio (None se a coluna faltar/for toda nula).

    O slice tem uma linha por hexagono e todas do MESMO municipio, entao qualquer valor
    preenchido serve -- o que nao serve e' assumir que a primeira linha tem um.
    """
    coluna = getattr(df_muni, "get", lambda _k: None)("cod_municipio")
    if coluna is None:
        return None
    validos = coluna.dropna()
    return validos.iloc[0] if not validos.empty else None


@lru_cache(maxsize=8)
def _carregar_parquet_full(path_str: str):
    """Le um parquet INTEIRO (pequeno: concorrentes/ultra/dominio). None se ausente."""
    import pandas as pd

    path = Path(path_str)
    if not path.is_file():
        return None
    try:
        return pd.read_parquet(path)
    except Exception:
        return None


@lru_cache(maxsize=1)
def _carregar_mercado_full(path_str: str):
    """Carrega a base de mercado (hexagonos) INTEIRA, 1x por processo (~1,9 GB).

    Lazy: so materializa na 1a chamada municipal — o fluxo Pontual nunca paga isso.
    """
    import pandas as pd

    return pd.read_parquet(path_str)


def _mercado_df(settings: Settings):
    return _carregar_mercado_full(str(settings.staging_dir / _MERCADO_PARQUET))


def _dominio_df(settings: Settings):
    """`plano_expansao_dominio.parquet` (opcional; melhora as zonas D2). None se ausente."""
    for p in (
        settings.staging_dir / "plano_expansao_dominio.parquet",
        Path(settings.censo_geo_dir).parent / "plano_expansao_dominio.parquet",
    ):
        df = _carregar_parquet_full(str(p))
        if df is not None:
            return df
    return None


@lru_cache(maxsize=2)
def _indice_municipios(path_str: str) -> dict[str, dict[str, dict]]:
    """Indexa `uf -> {nome_normalizado -> {nome, cod}}` lendo SO 3 colunas (barato).

    Nao carrega a base de 1,9 GB — le `uf/nome_municipio/cod_municipio` (~50 MB) e
    deduplica para ~5.300 municipios. Usado para listar/validar municipio no bot.
    """
    import pandas as pd

    df = pd.read_parquet(path_str, columns=["uf", "nome_municipio", "cod_municipio"])
    df = df.dropna(subset=["uf", "nome_municipio"])
    df["uf"] = df["uf"].astype(str).str.strip().str.upper()
    df["nome_municipio"] = df["nome_municipio"].astype(str).str.strip()
    df = df[df["nome_municipio"].str.len() > 0].drop_duplicates(["uf", "nome_municipio"])
    idx: dict[str, dict[str, dict]] = {}
    for uf, nome, cod in zip(df["uf"], df["nome_municipio"], df["cod_municipio"], strict=False):
        idx.setdefault(uf, {}).setdefault(_norm(nome), {"nome": nome, "cod": cod})
    return idx


def listar_ufs(settings: Settings) -> list[str]:
    """UFs disponiveis na base de mercado (ordenadas)."""
    idx = _indice_municipios(str(settings.staging_dir / _MERCADO_PARQUET))
    return sorted(idx.keys())


def listar_municipios(uf: str, settings: Settings) -> list[str]:
    """Municipios de uma UF (nomes reais, ordenados)."""
    idx = _indice_municipios(str(settings.staging_dir / _MERCADO_PARQUET))
    d = idx.get(str(uf).strip().upper(), {})
    return sorted({v["nome"] for v in d.values()})


def resolver_municipio(uf: str, texto: str, settings: Settings) -> tuple[str | None, list[str]]:
    """Casa o texto digitado a um municipio da UF (sem acento/caso).

    Retorna `(nome_exato | None, candidatos)`:
      - match exato normalizado  -> (nome, [nome])
      - 1 candidato por substring -> (nome, [nome])
      - ambiguo / nao encontrado  -> (None, ate 10 sugestoes)
    """
    idx = _indice_municipios(str(settings.staging_dir / _MERCADO_PARQUET))
    d = idx.get(str(uf).strip().upper(), {})
    if not d:
        return None, []
    alvo = _norm(texto)
    if not alvo:
        return None, []
    if alvo in d:
        return d[alvo]["nome"], [d[alvo]["nome"]]
    cands = sorted({v["nome"] for k, v in d.items() if alvo in k or k.startswith(alvo)})
    if len(cands) == 1:
        return cands[0], cands
    return None, cands[:10]


def gerar_pdf_municipio(
    uf: str,
    municipio: str,
    consumidor: str | None,
    settings: Settings,
    *,
    solicitante: str | None = None,
    unidade: str = "bairro",
) -> bytes:
    """Gera o PDF do Relatorio Municipal (BLK-RELMUN). READ-ONLY.

    `unidade` escolhe a leitura: "bairro" (default, 12 paginas) ou "hexagono" (10 paginas,
    o relatorio classico). No modo hexagono a leitura da particao geo de bairros e' PULADA --
    e' a parte cara do caminho e nada dela seria usado.

    Resolve o municipio (aceita nome sem acento), agrega os hexes, renderiza os 6
    mapas (basemap online com fallback offline) e monta o PDF pelo gerador do
    dashboard. Levanta 404 se o municipio nao existe/nao tem hexes na UF.
    """
    _reuse_contextily_session()  # mesma aceleracao de tiles do Pontual

    from motor_expansao.dashboard.relatorio_municipal import (
        _carregar_bairros_por_hex,
        agregar_municipio,
        carregar_bairros_geo,
        carregar_poligono_municipio,
        carregar_renda_domiciliar_por_hex,
        gerar_payloads_download_relatorio_municipal,
        render_mapas_municipio,
    )

    uf = str(uf).strip().upper()
    nome_exato, cands = resolver_municipio(uf, municipio, settings)
    if nome_exato is None:
        msg = f"Municipio '{municipio}' nao encontrado em {uf}"
        if cands:
            msg += ". Voce quis dizer: " + ", ".join(cands[:6]) + "?"
        raise APIError(404, msg, "municipio_nao_encontrado")

    df = _mercado_df(settings)
    col = "nome_municipio" if "nome_municipio" in df.columns else "cidade"
    df_muni = df.loc[df[col].astype(str).str.strip().str.casefold() == nome_exato.casefold()]
    if df_muni.empty:
        raise APIError(404, f"Municipio '{nome_exato}' ({uf}) sem hexagonos", "municipio_sem_dados")

    comp_df = _carregar_parquet_full(str(settings.staging_dir / "concorrentes_mapeados.parquet"))
    ultra_df = _carregar_parquet_full(str(settings.staging_dir / "unidades_ultra_mapeadas.parquet"))
    dominio_df = _dominio_df(settings)

    # Bairros reais (best-effort): usa cod_municipio da propria linha + particao geo.
    cod: str | None = None
    bairros: dict | None = None
    bairros_geo: dict | None = None
    try:
        # Primeiro valor NAO-NULO, nao `iloc[0]`: a coluna vem do censo trace e fica vazia nos
        # hexes sem setor casado (no Rio, 51 das 240 linhas). Se a 1a linha do slice calhasse de
        # ser uma dessas, TODA a camada de bairro sumia do relatorio -- e sem erro nenhum.
        cod = _normalizar_cod(_primeiro_cod_municipio(df_muni))
        if cod:
            bairros = _carregar_bairros_por_hex(uf, cod, settings.censo_geo_dir)
    except Exception:
        bairros = None
    # BLK-RELMUN-06: limite territorial dos bairros (mesma particao geo, segunda leitura).
    # Em try/except PROPRIO: uma falha aqui so tira o slide "Bairros Oficiais", nao pode
    # levar junto o rotulo por hex da pagina "Bairros por Zona", que ja funcionava.
    try:
        if cod and unidade != "hexagono":
            bairros_geo = carregar_bairros_geo(uf, cod, settings.censo_geo_dir)
    except Exception:
        bairros_geo = None
    # Renda DOMICILIAR por hexagono para a tabela de comparacao: vale nas DUAS unidades
    # (a tabela e' sempre por hexagono), entao fica fora do guard de `unidade` acima.
    # try/except proprio: falha aqui so tira a coluna de renda, nao o resto do relatorio.
    renda_dom: dict | None = None
    try:
        if cod:
            renda_dom = carregar_renda_domiciliar_por_hex(uf, cod, settings.censo_geo_dir)
    except Exception:
        renda_dom = None

    # BLK-RELMUN-05: divisa REAL do municipio (malha IBGE, ja montada neste container) para
    # recortar os pins. `None` -> recorte por hexes res-7; o relatorio sai igual, so menos exato.
    poligono = carregar_poligono_municipio(settings.ibge_dir, uf, cod)

    result = agregar_municipio(
        df, nome_municipio=nome_exato, uf=uf, dominio_df=dominio_df,
        competitors_df=comp_df, ultra_df=ultra_df, bairros_por_hex=bairros,
        bairros_geo=bairros_geo, renda_domiciliar_por_hex=renda_dom,
        df_pre_filtrado=df_muni, poligono_municipio=poligono,
    )
    if result.get("n_hex_total", 0) == 0:
        raise APIError(404, f"Municipio '{nome_exato}' ({uf}) sem hexagonos", "municipio_sem_dados")

    # Popula o cache de logos das redes (_ICON_CACHE) ANTES de renderizar os mapas e o PDF.
    # Sem isto, tanto os pins do mapa quanto o breakdown "Concorrentes por rede" (slide 8)
    # caem na sigla de texto — as logos das academias nao aparecem. Espelha o fluxo Pontual,
    # onde render_mapas_censitarios_combinados chama preload_logos (censo_map.py). Idempotente
    # e cacheado por processo.
    from motor_expansao.dashboard.competitors import preload_logos

    logos_dir = (
        settings.competitors_logos_dir
        if settings.competitors_logos_dir is not None
        and Path(settings.competitors_logos_dir).is_dir()
        else None
    )
    ultra_dir = settings.ultra_dir if Path(settings.ultra_dir).is_dir() else None
    if logos_dir is not None:
        preload_logos(logos_dir, ultra_dir=ultra_dir)

    def _mapas(basemap: bool):
        return render_mapas_municipio(
            df_muni, result, competitors_df=comp_df, ultra_df=ultra_df, basemap=basemap,
            poligono_municipio=poligono, unidade=unidade,
        )

    try:
        mapas = _mapas(True)
    except Exception:
        try:
            mapas = _mapas(False)
        except Exception:
            mapas = None

    payloads = gerar_payloads_download_relatorio_municipal(
        result, mapas, ultra_dir=ultra_dir, solicitante=solicitante or consumidor,
        unidade=unidade,
    )
    return payloads.pdf_bytes
