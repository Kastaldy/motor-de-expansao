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

# Nome da coluna de score setorial usada nos KPIs (carimbo `versao_score`).
_VERSAO_SCORE = "score_setor_2022_calibrado"


class _MalhaMunicipal:
    """Indice espacial (STRtree) dos municipios IBGE para resolver ponto->municipio."""

    def __init__(self, tree: STRtree, meta: list[tuple[str, str]]) -> None:
        self._tree = tree
        self._meta = meta  # lista paralela de (uf, cod_municipio)

    def resolver(self, lat: float, lng: float) -> tuple[str, str] | None:
        ponto = Point(lng, lat)  # GeoJSON/shapely usam (x=lng, y=lat)
        # STRtree avalia predicate(ponto, poligono); queremos poligono.contains(ponto),
        # equivalente a ponto.within(poligono) -> predicate="within".
        for idx in self._tree.query(ponto, predicate="within"):
            return self._meta[int(idx)]
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
        raise APIError(500, "Malha municipal IBGE ausente ou vazia", "erro_interno")
    return _MalhaMunicipal(STRtree(geoms), meta)


def _resolver_e_carregar(lat: float, lng: float, settings: Settings):
    """Resolve ``(uf, cod_municipio)`` e carrega ``setores_df``. Levanta 400/404."""
    from motor_expansao.dashboard.data import read_censo_geo_partition

    malha = _carregar_malha(str(settings.ibge_dir))
    resolvido = malha.resolver(lat, lng)
    if resolvido is None:
        raise APIError(400, "Coordenada fora do Brasil", "coordenada_invalida")
    uf, cod_municipio = resolvido

    setores_df = read_censo_geo_partition(settings.censo_geo_dir, uf, cod_municipio)
    if setores_df is None or setores_df.empty:
        raise APIError(
            404,
            f"Materialize setores_censitarios_2022_geo/ para {uf}/{cod_municipio}",
            "base_geo_ausente",
        )
    return uf, cod_municipio, setores_df


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


def _competitors_ultra(settings: Settings):
    """(competitors_df, ultra_df) da staging, ou (None, None) se ausente. READ-ONLY."""
    comp = _carregar_pontos(
        str(settings.staging_dir / "concorrentes_mapeados.parquet"), ("rede", "lat", "lng")
    )
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
        "densidade_pop_raio_hab_km2": result.get("densidade_pop_raio_hab_km2"),
        "score_setor_medio": result.get("score_setor_medio"),
        "score_setor_max": result.get("score_setor_max"),
        "n_concorrentes": result.get("n_concorrentes", 0),
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
    """Gera o PDF de 7 paginas do Relatorio Pontual Censitario (BLK-API-04).

    Enriquecido (READ-ONLY): mapas com *ruas* (basemap online, DEC-004) + pins de
    concorrentes/Ultra, e Big Numbers de SAM/residual via `residual`. Fallback
    gracioso para `basemap=False` se a busca de tiles falhar (offline).

    `rotulo`: nome do endereco/estabelecimento para a capa (no lugar de "Coordenada: ...").
    """
    _reuse_contextily_session()  # acelera a busca de tiles (~117s -> ~24s em area densa)

    from motor_expansao.dashboard.censo_map import render_mapas_censitarios_combinados
    from motor_expansao.dashboard.censo_point import (
        RAIO_CENSITARIO_DEFAULT_KM,
        analisar_ponto_censitario_setores,
    )
    from motor_expansao.dashboard.censo_report import gerar_pdf_relatorio_pontual_classico

    _uf, _cod, setores_df = _resolver_e_carregar(lat, lng, settings)
    comp_df, ultra_df = _competitors_ultra(settings)
    result = analisar_ponto_censitario_setores(
        lat, lng, setores_df, raio_km=RAIO_CENSITARIO_DEFAULT_KM,
        competitors_df=comp_df, ultra_df=ultra_df,
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

    def _mapas(basemap: bool):
        return render_mapas_censitarios_combinados(
            lat, lng, setores_df, raio_km=RAIO_CENSITARIO_DEFAULT_KM,
            competitors_df=comp_df, ultra_df=ultra_df,
            basemap=basemap, ultra_logo_dir=ultra_dir, logos_dir=logos_dir,
            # Arruamento mais visivel sob o choropleth: resgata tambem as ruas
            # residenciais CINZA-CLARAS do Voyager (ceil 160->215) e deixa a cor das
            # faixas mais translucida (alpha 140->110). So a API ajusta isto; o dashboard
            # segue com os defaults do modulo. (Diagnostico Parque Bosque Maia, 2026-06-12.)
            street_ceil=215, street_gain=1.3, street_cap=200, choropleth_alpha=110,
        )

    # Tenta com ruas (online); cai para offline; em ultimo caso, sem mapas.
    try:
        mapas = _mapas(True)
    except Exception:
        try:
            mapas = _mapas(False)
        except Exception:
            mapas = None

    residual = _residual_do_ponto(lat, lng, settings)
    # Variante "Apresentacao Classica Ultra" (BLK-EST-05): a API/bot espelha o
    # MESMO modelo que o dashboard passou a gerar por padrao (pages.py usa
    # template="classico"). Drop-in: mesma assinatura do gerador recente.
    return gerar_pdf_relatorio_pontual_classico(
        result, mapas, residual=residual, ultra_dir=ultra_dir,
        solicitante=consumidor, rotulo=rotulo,
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
    """cod_municipio pode vir como float/int/str; devolve string de digitos ou None."""
    if valor is None:
        return None
    s = str(valor).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s or None


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
) -> bytes:
    """Gera o PDF de 9 paginas do Relatorio Municipal (BLK-RELMUN). READ-ONLY.

    Resolve o municipio (aceita nome sem acento), agrega os hexes, renderiza os 5
    mapas (basemap online com fallback offline) e monta o PDF pelo gerador do
    dashboard. Levanta 404 se o municipio nao existe/nao tem hexes na UF.
    """
    _reuse_contextily_session()  # mesma aceleracao de tiles do Pontual

    from motor_expansao.dashboard.relatorio_municipal import (
        _carregar_bairros_por_hex,
        agregar_municipio,
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
    bairros: dict | None = None
    try:
        cod = _normalizar_cod(df_muni.iloc[0].get("cod_municipio"))
        if cod:
            bairros = _carregar_bairros_por_hex(uf, cod, settings.censo_geo_dir)
    except Exception:
        bairros = None

    result = agregar_municipio(
        df, nome_municipio=nome_exato, uf=uf, dominio_df=dominio_df,
        competitors_df=comp_df, ultra_df=ultra_df, bairros_por_hex=bairros,
    )
    if result.get("n_hex_total", 0) == 0:
        raise APIError(404, f"Municipio '{nome_exato}' ({uf}) sem hexagonos", "municipio_sem_dados")

    def _mapas(basemap: bool):
        return render_mapas_municipio(
            df_muni, result, competitors_df=comp_df, ultra_df=ultra_df, basemap=basemap,
        )

    try:
        mapas = _mapas(True)
    except Exception:
        try:
            mapas = _mapas(False)
        except Exception:
            mapas = None

    ultra_dir = settings.ultra_dir if Path(settings.ultra_dir).is_dir() else None
    payloads = gerar_payloads_download_relatorio_municipal(
        result, mapas, ultra_dir=ultra_dir, solicitante=solicitante or consumidor,
    )
    return payloads.pdf_bytes
