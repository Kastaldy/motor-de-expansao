"""BLK-DIM-07 -- base de calibracao multi-rede + raio variavel.

Junta as 3 redes com alunos reais + coordenadas LOCAIS (Ultra, Engenharia do Corpo,
SkyFit) numa unica base de calibracao, com:
  1. RECONCILIACAO DE NOMES auditada (match ingenuo por nome = 0%, medido 2026-06-15):
     - Ultra: join direto (alunos+coords no mesmo parquet).
     - SkyFit: join por cidade+UF (xlsx CIDADE/ESTADO <-> cidade parseada do CSV "Cidade (UF)").
       Cidade com >1 unidade no CSV = AMBIGUO -> nao auto-atribui (vai p/ BLK-DIM-09).
     - Engenharia: crosswalk fuzzy nome-interno/cidade por UF (difflib, stdlib); corte limpo ~67%.
       Bairros sem cidade no rotulo (Matriz/Esplanada/...) ficam 'nao_casado' (BLK-DIM-09).
  2. Coluna `marca` (separa marca de regiao downstream; ticket semelhante entre redes ->
     o efeito de marca NAO e preco, e pull de marca + DOMINIO de area -- Felipe 2026-06-15).
  3. Raio de captacao VARIAVEL por contexto urbano (regra EXOGENA: oferta concorrente/km2 +
     densidade pop; PROIBIDO derivar do nº de alunos -- anti-circular).
  4. Densidade de marca propria / dominio no catchment (confundidor: Engenharia "fechou" o Sul).

READ-ONLY sobre o M1 (DEC-001/DEC-008): nao recalcula score nem toca artefatos oficiais.
Anti-PII: nenhum `nome` de pessoa em disco; `assert_sem_pii` antes de qualquer `to_parquet`;
relatorios agregados sem listar unidades nominalmente.
"""

from __future__ import annotations

import logging
import math
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

from motor_expansao.dimensionamento import config
from motor_expansao.dimensionamento.aderencia import _r2_loo_para_alpha
from motor_expansao.dimensionamento.catchment_batch import (
    GEO_BASE_DIR_DEFAULT,
    calcular_catchment_unidade,
)
from motor_expansao.dimensionamento.growth_api_client import assert_sem_pii

_logger = logging.getLogger(__name__)

# --- Fontes (arquivos LOCAIS; xlsx gitignored em data/validacao) ------------
ULTRA_PERF_PATH = config.STAGING_DIR / "unidades_ultra_performance_hex.parquet"
ENG_ALUNOS_XLSX = Path("data/validacao/academias_engenharia_do_corpo.xlsx")
ENG_COORDS_CSV = Path("concorrentes/Unidades/unidades_engenharia_do_corpo.csv")
SKY_ALUNOS_XLSX = Path("data/validacao/Sky Fit dados.xlsx")
SKY_COORDS_CSV = Path("concorrentes/Unidades/unidades_skyfit.csv")
CONCORRENTES_PATH = config.STAGING_DIR / "concorrentes_mapeados.parquet"

SAIDA_BASE = config.STAGING_DIR / "base_calibracao_multirede.parquet"

# Piso de viabilidade observado nas 3 redes (~2.000 alunos). NAO e capacidade
# (capacidade_default_concorrente_alunos=2500 = o que comporta). Usado downstream (BLK-DIM-08).
PISO_VIABILIDADE_ALUNOS: int = 2_000

# Regra de raio variavel (EXOGENA -- so contexto urbano; NUNCA o nº de alunos).
RAIO_KM_MIN: float = 0.8   # capital densa, muita oferta/m2
RAIO_KM_MAX: float = 3.0   # interior, deslocamento facil, pouca oferta
RAIO_KM_FIXO_BASELINE: float = config.RAIO_CATCHMENT_KM  # 1.5 (baseline de comparacao)

# Limiar de aceite do crosswalk fuzzy (Engenharia), escala difflib [0,1]. Corte limpo
# medido em ~0.95 (>=0.95) vs <0.70 -> 0.90 e seguro. Usa stdlib (sem dependencia nova).
LIMIAR_FUZZY: float = 0.90
# Banda de neutralidade do R2_LOO no veredito do raio (|delta| <= isso = "neutro", nao melhora/piora).
LIMIAR_R2_DELTA: float = 0.02

BASE_COLUNAS = (
    "unidade",            # rotulo da unidade (NAO e PII de pessoa)
    "marca",              # 'ultra' | 'engenharia_do_corpo' | 'skyfit'
    "uf",
    "cidade",
    "lat",
    "lng",
    "alunos_reais",
    "metragem",
    "flag_qualidade_match",  # 'direto' | 'cidade_uf' | 'fuzzy' | 'ambiguo' | 'nao_casado'
)

_UF_SET = frozenset(
    "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split()
)
_EC_PREFIXO_RE = re.compile(r"^\s*(ecb|ec|engenharia do corpo)\s*-\s*", re.IGNORECASE)
_UF_SUFIXO_RE = re.compile(r",?\s*([A-Za-z]{2})\s*$")

# ---------------------------------------------------------------------------
# Normalizacao / parsing de nome (a parte de RISCO -- match ingenuo = 0%)
# ---------------------------------------------------------------------------


def _strip(s: object) -> str:
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    t = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return " ".join(t.lower().split())


def _norm_cidade(s: object) -> str:
    """Cidade normalizada para chave de join: minuscula, sem acento, sem pontuacao."""
    t = _strip(s)
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    return " ".join(t.split())


def parse_cidade_uf_do_csv(nome_unidade: object) -> tuple[str, str]:
    """Extrai (cidade_norm, uf) de "Cidade (UF)" ou "Bairro - Cidade, UF".

    Ex.: "Abaetetuba (PA)" -> ("abaetetuba", "PA");
         "Diamantino - Caxias do Sul, RS" -> ("caxias do sul", "RS").
    """
    raw = str(nome_unidade or "")
    uf = ""
    m = re.search(r"\(([A-Za-z]{2})\)\s*$", raw)
    if m and m.group(1).upper() in _UF_SET:
        uf = m.group(1).upper()
        raw = raw[: m.start()].strip()
    else:
        m = re.search(r",\s*([A-Za-z]{2})\s*$", raw)
        if m and m.group(1).upper() in _UF_SET:
            uf = m.group(1).upper()
            raw = raw[: m.start()].strip()
    if " - " in raw:
        raw = raw.split(" - ")[-1]
    return _norm_cidade(raw), uf


def _eng_token_uf(unidade: object) -> tuple[str, str]:
    """De "EC - VACARIA, RS" -> ("vacaria", "RS"); "ENGENHARIA DO CORPO - TUBARAO" -> ("tubarao","")."""
    raw = str(unidade or "")
    uf = ""
    m = _UF_SUFIXO_RE.search(raw)
    if m and m.group(1).upper() in _UF_SET:
        uf = m.group(1).upper()
        raw = raw[: m.start()]
    raw = _EC_PREFIXO_RE.sub("", raw)
    return _norm_cidade(raw), uf


def _detectar_header(path: Path, sheet: str, tokens: tuple[str, ...]) -> int:
    """Acha a linha de cabecalho varrendo as primeiras linhas por tokens conhecidos."""
    preview = pd.read_excel(path, sheet_name=sheet, header=None, nrows=8)
    for i in range(len(preview)):
        linha = " ".join(_strip(v) for v in preview.iloc[i].tolist())
        if all(_strip(tok) in linha for tok in tokens):
            return i
    return 0


def _ler_csv_coords(path: Path) -> pd.DataFrame:
    """Le CSV de coords (nome_unidade, latitude, longitude) tolerando sep , ou ;."""
    ultima: pd.DataFrame | None = None
    for sep in (",", ";", "\t"):
        d = pd.read_csv(path, sep=sep, encoding="utf-8-sig", engine="python")
        d = d.rename(columns={c: str(c).lower() for c in d.columns})
        ultima = d
        if d.shape[1] >= 3 and any("lat" in c for c in d.columns):
            return d
    if ultima is None:
        raise ValueError(f"Nao consegui ler coords de {path}")
    return ultima


# ---------------------------------------------------------------------------
# Loaders por rede (concretos)
# ---------------------------------------------------------------------------


def carregar_ultra(path: Path = ULTRA_PERF_PATH) -> pd.DataFrame:
    """Ultra: alunos_total + coords + metragem (ja tem tudo, sem join externo)."""
    u = pd.read_parquet(path)
    return pd.DataFrame(
        {
            "unidade": u["unidade"].astype(str),
            "marca": "ultra",
            "uf": u["uf"].astype(str).str.upper(),
            "cidade": u["cidade"].map(_norm_cidade),
            "lat": pd.to_numeric(u["lat"], errors="coerce"),
            "lng": pd.to_numeric(u["lng"], errors="coerce"),
            "alunos_reais": pd.to_numeric(u["alunos_total"], errors="coerce"),
            "metragem": pd.to_numeric(u.get("metragem"), errors="coerce"),
            "flag_qualidade_match": "direto",
        }
    )[list(BASE_COLUNAS)]


def carregar_skyfit(
    alunos_xlsx: Path = SKY_ALUNOS_XLSX, coords_csv: Path = SKY_COORDS_CSV
) -> pd.DataFrame:
    """SkyFit: alunos (xlsx, CIDADE+ESTADO) <-> coords (csv "Cidade (UF)") por cidade+UF.

    alunos_reais = soma das colunas "Alunos *" (EVO+Gympass+TotalPass). Cidade com >1
    unidade no csv = AMBIGUO -> nao auto-atribui coords (resolver no BLK-DIM-09).
    """
    hdr = _detectar_header(alunos_xlsx, "Sell Out", ("cidade", "estado", "alunos evo"))
    a = pd.read_excel(alunos_xlsx, sheet_name="Sell Out", header=hdr)
    cmap = {_strip(c): c for c in a.columns}
    col_cid, col_est = cmap.get("cidade"), cmap.get("estado")
    cols_al = [cmap[k] for k in cmap if k.startswith("alunos ")]
    a = a.dropna(subset=[col_cid, col_est], how="any").copy()
    a["cidade"] = a[col_cid].map(_norm_cidade)
    a["uf"] = a[col_est].astype(str).str.strip().str.upper()
    a["alunos_reais"] = (
        a[cols_al].apply(pd.to_numeric, errors="coerce").sum(axis=1, min_count=1)
    )
    a["rotulo"] = a[col_cid].astype(str)

    c = _ler_csv_coords(coords_csv)
    parsed = c["nome_unidade"].apply(lambda s: pd.Series(parse_cidade_uf_do_csv(s)))
    c["cidade"], c["uf"] = parsed[0], parsed[1]
    n_por_cidade = c.groupby(["cidade", "uf"]).size().rename("n_csv")
    # Lookup so para cidades com EXATAMENTE 1 unidade (sem ambiguidade).
    unicas = c.merge(n_por_cidade, on=["cidade", "uf"]).query("n_csv == 1")
    lk = unicas.set_index(["cidade", "uf"])[["latitude", "longitude"]]
    cidades_multi = set(
        n_por_cidade[n_por_cidade > 1].index.tolist()
    )  # (cidade, uf) ambiguos

    linhas: list[dict] = []
    for _, r in a.iterrows():
        chave = (r["cidade"], r["uf"])
        lat = lng = float("nan")
        if chave in lk.index:
            lat = float(lk.loc[chave, "latitude"])
            lng = float(lk.loc[chave, "longitude"])
            flag = "cidade_uf"
        elif chave in cidades_multi:
            flag = "ambiguo"
        else:
            flag = "nao_casado"
        linhas.append(
            {
                "unidade": r["rotulo"],
                "marca": "skyfit",
                "uf": r["uf"],
                "cidade": r["cidade"],
                "lat": lat,
                "lng": lng,
                "alunos_reais": r["alunos_reais"],
                "metragem": float("nan"),
                "flag_qualidade_match": flag,
            }
        )
    return pd.DataFrame(linhas)[list(BASE_COLUNAS)]


def carregar_engenharia(
    alunos_xlsx: Path = ENG_ALUNOS_XLSX, coords_csv: Path = ENG_COORDS_CSV
) -> pd.DataFrame:
    """Engenharia: alunos (xlsx) <-> coords (csv) por crosswalk fuzzy cidade/UF (difflib, stdlib).

    xlsx usa nome interno ("EC - VACARIA, RS"); csv usa cidade ("Vacaria, RS"). Match por
    token de cidade DENTRO da mesma UF, com `SequenceMatcher.ratio() >= LIMIAR_FUZZY`,
    atribuicao gulosa por score (cada coord usada 1x). Bairros sem cidade no rotulo
    (Matriz/Esplanada/...) ficam 'nao_casado' -> BLK-DIM-09.
    """
    from difflib import SequenceMatcher

    hdr = _detectar_header(alunos_xlsx, "Academias", ("unidade", "alunos totais"))
    a = pd.read_excel(alunos_xlsx, sheet_name="Academias", header=hdr)
    col_un = next(c for c in a.columns if "unidade" in _strip(c))
    col_al = next(c for c in a.columns if "alunos totais" in _strip(c))
    col_m = next((c for c in a.columns if "metragem" in _strip(c)), None)
    a = a.dropna(subset=[col_un], how="any").copy()
    toks_ufs = a[col_un].apply(lambda s: pd.Series(_eng_token_uf(s)))
    a["tok"], a["uf"] = toks_ufs[0], toks_ufs[1]
    a["alunos_reais"] = pd.to_numeric(a[col_al], errors="coerce")
    a["metragem"] = pd.to_numeric(a[col_m], errors="coerce") if col_m else float("nan")

    c = _ler_csv_coords(coords_csv)
    parsed = c["nome_unidade"].apply(lambda s: pd.Series(parse_cidade_uf_do_csv(s)))
    c["cidade"], c["uf"] = parsed[0], parsed[1]

    # Ordena candidatos por melhor score para atribuicao gulosa (coord usada 1x).
    propostas: list[tuple[float, int, int]] = []  # (score, idx_xlsx, idx_csv)
    for ia, ra in a.iterrows():
        cand = c[c["uf"] == ra["uf"]]
        if cand.empty or not ra["tok"]:
            continue
        melhor_s, melhor_ic = -1.0, -1
        for ic_cand, cidade_cand in cand["cidade"].items():
            s = SequenceMatcher(None, str(ra["tok"]), str(cidade_cand)).ratio()
            if s > melhor_s:
                melhor_s, melhor_ic = s, int(ic_cand)
        if melhor_ic >= 0 and melhor_s >= LIMIAR_FUZZY:
            propostas.append((float(melhor_s), int(ia), melhor_ic))
    propostas.sort(reverse=True)
    usados_csv: set[int] = set()
    casado_xlsx: dict[int, int] = {}
    for _score, ia, ic in propostas:
        if ia in casado_xlsx or ic in usados_csv:
            continue
        casado_xlsx[ia] = ic
        usados_csv.add(ic)

    linhas: list[dict] = []
    for ia, ra in a.iterrows():
        ic_m = casado_xlsx.get(ia)
        if ic_m is not None:
            lat = float(pd.to_numeric(c.loc[ic_m, "latitude"], errors="coerce"))
            lng = float(pd.to_numeric(c.loc[ic_m, "longitude"], errors="coerce"))
            cidade, flag = str(c.loc[ic_m, "cidade"]), "fuzzy"
        else:
            lat = lng = float("nan")
            cidade, flag = str(ra["tok"]), "nao_casado"
        linhas.append(
            {
                "unidade": str(ra[col_un]),
                "marca": "engenharia_do_corpo",
                "uf": ra["uf"],
                "cidade": cidade,
                "lat": lat,
                "lng": lng,
                "alunos_reais": ra["alunos_reais"],
                "metragem": ra["metragem"],
                "flag_qualidade_match": flag,
            }
        )
    return pd.DataFrame(linhas)[list(BASE_COLUNAS)]


# ---------------------------------------------------------------------------
# Geometria (haversine) + raio variavel + densidade de marca propria (dominio)
# ---------------------------------------------------------------------------


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Distancia em km entre 2 pontos (esfera). Vetorizavel via numpy se necessario."""
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _conc_por_km2(
    lat: float, lng: float, conc_lat: np.ndarray, conc_lng: np.ndarray, raio_km: float = 1.0
) -> float:
    """Concorrentes/km2 num raio (haversine vetorizado vs. concorrentes_mapeados)."""
    if not np.isfinite(lat) or not np.isfinite(lng) or conc_lat.size == 0:
        return 0.0
    r = 6371.0088
    p1 = math.radians(lat)
    p2 = np.radians(conc_lat)
    dphi = np.radians(conc_lat - lat)
    dlmb = np.radians(conc_lng - lng)
    h = np.sin(dphi / 2) ** 2 + math.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    dist = 2 * r * np.arcsin(np.sqrt(h))
    n = int(np.sum(dist <= raio_km))
    return n / (math.pi * raio_km**2)


def raio_variavel_km(densidade_hab_km2: float, n_concorrentes_km2: float) -> float:
    """Raio de captacao EXOGENO: cai com densidade urbana e oferta concorrente/km2.

    Capital densa com muita oferta/m2 (ex.: Av. Paulista) -> raio curto; interior com
    deslocamento facil e pouca oferta (ex.: Araraquara) -> raio largo. PROIBIDO usar o
    nº de alunos (anti-circular). Indice de "atrito" [0,1] mapeado para [MIN, MAX].
    """
    dens = max(float(densidade_hab_km2 or 0.0), 0.0)
    conc = max(float(n_concorrentes_km2 or 0.0), 0.0)
    atrito = 1.0 - math.exp(-(dens / 5000.0 + conc / 2.0))
    atrito = min(max(atrito, 0.0), 1.0)
    return RAIO_KM_MAX - atrito * (RAIO_KM_MAX - RAIO_KM_MIN)


def derivar_densidade_marca_propria(
    base: pd.DataFrame, raio_col: str = "raio_km"
) -> pd.DataFrame:
    """Adiciona `n_mesma_marca_no_raio` e `dist_mesma_marca_min_km` por unidade.

    Confundidor de DOMINIO (Felipe 2026-06-15): a penetracao alta da Engenharia no Sul
    vem de saturacao de marca propria, NAO de mercado intrinseco. Conta vizinhos da MESMA
    marca cujo centro cai dentro do raio (variavel se `raio_col` existir, senao baseline).
    Marca/UF com NaN de coord nao contam. Catchment compartilhado e tratado no BLK-DIM-08.
    """
    out = base.copy()
    out["n_mesma_marca_no_raio"] = 0
    out["dist_mesma_marca_min_km"] = float("nan")
    for _marca, g in out.groupby("marca"):
        pts = g[["lat", "lng"]].apply(pd.to_numeric, errors="coerce")
        idxs = g.index.tolist()
        for i in idxs:
            lat_i, lng_i = pts.loc[i, "lat"], pts.loc[i, "lng"]
            if not (np.isfinite(lat_i) and np.isfinite(lng_i)):
                continue
            raio = float(out.loc[i, raio_col]) if raio_col in out.columns else RAIO_KM_FIXO_BASELINE
            n, dmin = 0, math.inf
            for j in idxs:
                if j == i:
                    continue
                lat_j, lng_j = pts.loc[j, "lat"], pts.loc[j, "lng"]
                if not (np.isfinite(lat_j) and np.isfinite(lng_j)):
                    continue
                d = haversine_km(lat_i, lng_i, lat_j, lng_j)
                dmin = min(dmin, d)
                if d <= raio:
                    n += 1
            out.loc[i, "n_mesma_marca_no_raio"] = n
            out.loc[i, "dist_mesma_marca_min_km"] = dmin if math.isfinite(dmin) else float("nan")
    return out


# ---------------------------------------------------------------------------
# Validacao do raio variavel SEM dado de origem dos alunos
# ---------------------------------------------------------------------------


def _cv(serie: np.ndarray) -> float:
    """Coeficiente de variacao (std/mean) de valores positivos finitos."""
    v = serie[np.isfinite(serie) & (serie > 0)]
    if v.size < 2 or v.mean() == 0:
        return float("nan")
    return float(v.std(ddof=1) / v.mean())


def _r2_loo_log_pop(pop: np.ndarray, alunos: np.ndarray) -> float:
    """R2_LOO de log(alunos) ~ log(pop) (Ridge alpha=1, reusa _r2_loo_para_alpha)."""
    ok = np.isfinite(pop) & (pop > 0) & np.isfinite(alunos) & (alunos > 0)
    if int(ok.sum()) < 5:
        return float("nan")
    X = np.log(pop[ok]).reshape(-1, 1)
    y = np.log(alunos[ok])
    r2, _rmse, _pred = _r2_loo_para_alpha(X, y, alpha=1.0)
    return float(r2)


def validar_raio_variavel(
    base: pd.DataFrame,
    *,
    geo_base_dir: Path | str = GEO_BASE_DIR_DEFAULT,
    setores_loader=None,
    conc_path: Path = CONCORRENTES_PATH,
) -> tuple[pd.DataFrame, dict]:
    """Compara raio FIXO 1.5 km vs. raio VARIAVEL pela estabilidade da penetracao.

    Sem origem dos alunos, validamos a regra de raio INDIRETAMENTE: e ACEITA se reduz o
    CV(penetracao = alunos_reais/pop_captacao) E melhora o R2_LOO de log(alunos)~log(pop)
    vs. raio fixo. Caso contrario, mantem-se 1.5 km (resultado VALIDO).

    Computa `pop_captacao` em 3 reguas (fixo 1.5; variavel por densidade+concorrencia;
    fixo 1.0 como 3a regua de controle) reusando `calcular_catchment_unidade` (helper
    geometrico INTOCADO, igual ao DIM-00). So unidades com coord entram. Retorna
    (base_enriquecida, metricas).
    """
    from motor_expansao.dashboard.data import read_censo_geo_partition

    if setores_loader is None:
        setores_loader = read_censo_geo_partition
    geo_base_dir = Path(geo_base_dir)

    conc = pd.read_parquet(conc_path)
    conc_lat = pd.to_numeric(conc.get("lat"), errors="coerce").to_numpy(dtype=float)
    conc_lng = pd.to_numeric(conc.get("lng"), errors="coerce").to_numpy(dtype=float)
    okc = np.isfinite(conc_lat) & np.isfinite(conc_lng)
    conc_lat, conc_lng = conc_lat[okc], conc_lng[okc]

    work = base[base["lat"].notna() & base["lng"].notna()].copy().reset_index(drop=True)
    cache_uf: dict[str, pd.DataFrame] = {}

    pop_fixo15, pop_fixo10, pop_var, raios, n_conc = [], [], [], [], []
    for _, row in work.iterrows():
        uf = str(row["uf"] or "").upper()
        lat, lng = float(row["lat"]), float(row["lng"])
        if uf and uf not in cache_uf:
            try:
                cache_uf[uf] = setores_loader(geo_base_dir, uf)
            except Exception as exc:  # pragma: no cover - IO defensivo
                _logger.warning("Falha setores UF=%s: %s", uf, exc)
                cache_uf[uf] = pd.DataFrame()
        setores = cache_uf.get(uf, pd.DataFrame())

        c15 = calcular_catchment_unidade(lat, lng, setores, raio_km=RAIO_KM_FIXO_BASELINE)
        c10 = calcular_catchment_unidade(lat, lng, setores, raio_km=1.0)
        dens = (
            c15["pop_captacao"] / (math.pi * RAIO_KM_FIXO_BASELINE**2)
            if np.isfinite(c15["pop_captacao"])
            else 0.0
        )
        nck = _conc_por_km2(lat, lng, conc_lat, conc_lng, raio_km=1.0)
        raio = raio_variavel_km(dens, nck)
        cvar = calcular_catchment_unidade(lat, lng, setores, raio_km=raio)

        pop_fixo15.append(c15["pop_captacao"])
        pop_fixo10.append(c10["pop_captacao"])
        pop_var.append(cvar["pop_captacao"])
        raios.append(raio)
        n_conc.append(nck)

    work["pop_captacao_fixo_1p5"] = pop_fixo15
    work["pop_captacao_fixo_1p0"] = pop_fixo10
    work["raio_km"] = raios
    work["n_concorrentes_km2"] = n_conc
    work["pop_captacao_variavel"] = pop_var

    alunos = pd.to_numeric(work["alunos_reais"], errors="coerce").to_numpy(dtype=float)
    pen_fixo = alunos / np.asarray(pop_fixo15, dtype=float)
    pen_var = alunos / np.asarray(pop_var, dtype=float)

    cvf = _cv(pen_fixo)
    cvv = _cv(pen_var)
    r2f = _r2_loo_log_pop(np.asarray(pop_fixo15, dtype=float), alunos)
    r2v = _r2_loo_log_pop(np.asarray(pop_var, dtype=float), alunos)
    raio_mediano = float(np.nanmedian(raios)) if raios else float("nan")

    # CV cai materialmente? (>= 20% de reducao relativa). R2 melhora / e neutro?
    cv_material = bool(
        np.isfinite(cvf) and np.isfinite(cvv) and cvf > 0 and (cvv <= 0.8 * cvf)
    )
    r2_melhora = bool(np.isfinite(r2f) and np.isfinite(r2v) and (r2v > r2f + LIMIAR_R2_DELTA))
    r2_neutro = bool(np.isfinite(r2f) and np.isfinite(r2v) and (abs(r2v - r2f) <= LIMIAR_R2_DELTA))
    if cv_material and r2_melhora:
        veredito = "raio_variavel_aceito"
    elif cv_material and r2_neutro:
        # Faz o trabalho dele (penetracao comparavel) sem piorar a previsao de alunos
        # -- que pop sozinha nao da em raio nenhum (DIM-01R). Recomendado p/ o residual (DIM-08).
        veredito = "raio_variavel_aceito_para_estabilidade"
    else:
        veredito = "raio_fixo_mantido"
    cv_reducao = (
        float(1.0 - cvv / cvf)
        if (np.isfinite(cvf) and np.isfinite(cvv) and cvf > 0)
        else float("nan")
    )

    metricas: dict[str, object] = {
        "n_unidades_com_coord": int(len(work)),
        "cv_penetracao_fixo_1p5": cvf,
        "cv_penetracao_variavel": cvv,
        "r2_loo_fixo_1p5": r2f,
        "r2_loo_variavel": r2v,
        "raio_variavel_km_mediano": raio_mediano,
        "cv_reducao_relativa": cv_reducao,
        "veredito": veredito,
    }
    return work, metricas


# ---------------------------------------------------------------------------
# Montagem da base + auditoria de match + relatorio
# ---------------------------------------------------------------------------


def montar_base_multirede() -> tuple[pd.DataFrame, dict]:
    """Junta as 3 redes na base de calibracao e devolve (base, auditoria_match).

    auditoria_match: contagens POR REDE (sem listar unidades nominalmente). As
    nao-casadas/ambiguas sao a entrada do BLK-DIM-09 (crosswalk manual).
    """
    base = pd.concat(
        [carregar_ultra(), carregar_engenharia(), carregar_skyfit()], ignore_index=True
    )[list(BASE_COLUNAS)]

    auditoria: dict = {}
    for marca, g in base.groupby("marca"):
        casadas = int((g["lat"].notna() & g["lng"].notna()).sum())
        auditoria[str(marca)] = {
            "n_total": int(len(g)),
            "n_casadas": casadas,
            "taxa_match": round(casadas / max(len(g), 1), 3),
            "por_flag": {
                str(k): int(v) for k, v in g["flag_qualidade_match"].value_counts().items()
            },
        }
    return base, auditoria


def salvar_base(base: pd.DataFrame, path: Path = SAIDA_BASE) -> None:
    """Persiste a base SO depois do guard anti-PII (levanta se houver coluna proibida)."""
    assert_sem_pii(base)
    path.parent.mkdir(parents=True, exist_ok=True)
    base.to_parquet(path, index=False)
    _logger.info("base_calibracao_multirede salva: %d linhas -> %s", len(base), path)


def escrever_relatorio(
    auditoria: dict, metricas: dict, *, path: Path = Path("data/analysis/catchment_variavel.md")
) -> None:
    """Materializa data/analysis/catchment_variavel.md (gitignored, sem PII)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    L: list[str] = []
    L.append("# Base multi-rede + raio variavel -- BLK-DIM-07")
    L.append("")
    L.append("READ-ONLY sobre o M1 (DEC-001/DEC-008). Sem PII (so contagens agregadas).")
    L.append("")
    L.append("## Reconciliacao de nomes (taxa de match por rede)")
    L.append("")
    L.append("| marca | n_total | n_casadas | taxa_match | flags |")
    L.append("| --- | ---: | ---: | ---: | --- |")
    for marca, a in sorted(auditoria.items()):
        flags = ", ".join(f"{k}={v}" for k, v in sorted(a["por_flag"].items()))
        L.append(
            f"| {marca} | {a['n_total']} | {a['n_casadas']} | {a['taxa_match']:.0%} | {flags} |"
        )
    L.append("")
    L.append("Nao-casadas/ambiguas = entrada do BLK-DIM-09 (crosswalk manual).")
    L.append("")
    L.append("## Validacao do raio variavel (estabilidade da penetracao)")
    L.append("")
    L.append("Sem origem dos alunos, a regra de raio e ACEITA se reduz o CV da penetracao")
    L.append("E melhora o R2_LOO de log(alunos)~log(pop) vs. raio fixo 1.5 km.")
    L.append("")
    L.append("| metrica | valor |")
    L.append("| --- | ---: |")
    for k in (
        "n_unidades_com_coord",
        "raio_variavel_km_mediano",
        "cv_penetracao_fixo_1p5",
        "cv_penetracao_variavel",
        "cv_reducao_relativa",
        "r2_loo_fixo_1p5",
        "r2_loo_variavel",
    ):
        v = metricas.get(k)
        vs = f"{v:.4f}" if isinstance(v, float) else str(v)
        L.append(f"| {k} | {vs} |")
    L.append("")
    L.append(f"**Veredito:** `{metricas.get('veredito')}`.")
    L.append("")
    L.append("## Leitura honesta (dois efeitos separados)")
    L.append("")
    L.append(
        "1. **Estabilidade da penetracao** (o trabalho do raio variavel): se `cv_reducao_relativa` "
        "for material (>= 20%), o raio por contexto torna a penetracao COMPARAVEL entre regioes "
        "(corrige o artefato de penetracao > 100% do raio fixo). E o que o BLK-DIM-08 (residual) precisa."
    )
    L.append(
        "2. **Previsao de alunos por pop** (`r2_loo_*`): se ambos ~0, pop sozinha NAO preve a demanda "
        "absoluta em raio NENHUM -- consistente com o NO-GO do BLK-DIM-01R. O raio variavel NAO "
        "conserta isso (nem deveria); quem ataca demanda e o residual + features (DIM-05/08), nao o raio."
    )
    L.append(
        "Veredito `aceito_para_estabilidade` = use o raio variavel para penetracao/residual, "
        "mas NAO o leia como 'agora pop preve alunos'. Rejeitar tambem e VALIDO (1.5 km ja serve). "
        "O catchment usa o helper geometrico do DIM-00 (metodo/raio de intersecao INTOCADOS)."
    )
    path.write_text("\n".join(L), encoding="utf-8")


__all__ = [
    "PISO_VIABILIDADE_ALUNOS",
    "RAIO_KM_MIN",
    "RAIO_KM_MAX",
    "LIMIAR_FUZZY",
    "BASE_COLUNAS",
    "parse_cidade_uf_do_csv",
    "haversine_km",
    "carregar_ultra",
    "carregar_engenharia",
    "carregar_skyfit",
    "raio_variavel_km",
    "derivar_densidade_marca_propria",
    "validar_raio_variavel",
    "montar_base_multirede",
    "salvar_base",
    "escrever_relatorio",
]


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    _base, _aud = montar_base_multirede()
    print("auditoria match:", _aud)
    _enr, _met = validar_raio_variavel(_base)
    print("metricas raio:", _met)
    salvar_base(_base)
    escrever_relatorio(_aud, _met)
