# -*- coding: utf-8 -*-
"""Teste pre-registrado de POI (protocolo_poi_uni00.md v1).

  --etapa portoes : SEM desfecho (P1 colinearidade, P2 suporte F3, P3 idade/metragem, P4 poder). Grava
                    saidas/portoes.md e saidas/portoes.json. P4 usa os residuos do modelo BASE (declarado).
  --etapa teste   : S1 (Ultra, faturamento Financeiro 2025) e S2 (Smart Fit, alunos 2025) + criterio da §7
                    + relatado-sem-decidir da §8. Exige REGISTRO_CONGELAMENTO.txt.
"""
import hashlib
import json
import sys
import unicodedata
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from scipy.stats import spearmanr
from shapely import wkb
from sklearn.linear_model import RidgeCV
from sklearn.model_selection import GroupKFold
from sklearn.neighbors import BallTree
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")
ROOT = Path(r"C:\dev\motor-de-expansao")
SC = Path(r"C:\Users\Felipe\AppData\Local\Temp\claude\C--dev-motor-de-expansao\9259d0a1-7dda-49bd-a390-c88f3d4ac1a6\scratchpad")
ISO = SC / "iso"
POIDIR = ROOT / "data" / "analysis" / "poi"
OUT = POIDIR / "saidas"
FAMS = ["F1", "F2", "F3", "F5"]
SINAL = {"F1": 1, "F2": 1, "F3": 1, "F5": -1}
ESTOQUE = "20250101"
R_TERRA = 6371008.8


# =================== features ===================
def haversine(la1, lo1, la2, lo2):
    la1, lo1, la2, lo2 = map(np.radians, (la1, lo1, la2, lo2))
    a = np.sin((la2 - la1) / 2) ** 2 + np.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2
    return 2 * R_TERRA * np.arcsin(np.sqrt(a))


_MALLS = {}


def malls_5880():
    """Poligonos de shop=mall (01c) em EPSG:5880 + STRtree. Carregado uma vez."""
    if not _MALLS:
        from shapely import STRtree
        m = pd.read_parquet(ROOT / "data" / "staging" / "poi" / "osm_malls_poligonos.parquet")
        gs = gpd.GeoSeries([wkb.loads(b) for b in m.poligono_wkb], crs=4326).to_crs(5880).make_valid()
        _MALLS["geoms"] = np.array(gs.values); _MALLS["tree"] = STRtree(_MALLS["geoms"])
    return _MALLS


def f3_por_unidade(anc, pontos):
    """pontos: DataFrame (origem, ponto_id, lat, lng, tem_pe). F3 binaria + fatos descritivos.
    Shopping 'proprio' = poligono de shop=mall a <= 150 m da unidade (inclui estar dentro); ancoras de mall a <= 150 m
    desse poligono saem (auditoria 2: centroide de shopping grande fica > 150 m da academia que esta dentro)."""
    rows = []
    g = {k: v for k, v in anc.groupby(["origem", "ponto_id"])}
    M = malls_5880()
    up = gpd.GeoSeries(gpd.points_from_xy(pontos.lng, pontos.lat), crs=4326).to_crs(5880).values
    for r, u in zip(pontos.itertuples(), up):
        a = g.get((r.origem, r.ponto_id))
        proprios = M["geoms"][M["tree"].query(u, predicate="dwithin", distance=150)]
        em_shop, n = bool(len(proprios)), {"mall": 0, "estacao": 0, "hiper": 0}
        if a is not None and len(a) and len(proprios):
            am = a.tipo.eq("mall").to_numpy()
            if am.any():
                pa = gpd.GeoSeries(gpd.points_from_xy(a.lng[am], a.lat[am]), crs=4326).to_crs(5880).values
                perto = np.array([min(shapely.distance(x, pp) for pp in proprios) <= 150 for x in pa])
                keep = np.ones(len(a), bool); keep[np.nonzero(am)[0][perto]] = False
                a = a[keep]
        if a is not None and len(a):
            # 1o agrupa ancoras do mesmo tipo a < 300 m (ligacao simples); 2o descarta o cluster de mall que
            # tenha QUALQUER membro a < 150 m da unidade (o proprio shopping, mesmo duplicado no OSM)
            for t, at in a.groupby("tipo"):
                la_, lo_ = at.lat.to_numpy(float), at.lng.to_numpy(float); k_ = len(at)
                rot = np.arange(k_)
                for i in range(k_):
                    viz = np.nonzero(haversine(la_[i], lo_[i], la_, lo_) < 300)[0]
                    rr = rot[viz].min(); rot[np.isin(rot, rot[viz])] = rr
                d = haversine(r.lat, r.lng, la_, lo_)
                cl = list(np.unique(rot))
                if t == "mall":
                    proprio = [c_ for c_ in cl if (d[rot == c_] < 150).any()]
                    em_shop = em_shop or bool(proprio)
                    cl = [c_ for c_ in cl if c_ not in proprio]
                n[t] = len(cl)
        rows.append({"origem": r.origem, "ponto_id": r.ponto_id, "F3": float(sum(n.values()) > 0) if r.tem_pe else np.nan, "em_shopping": em_shop,
                     "n_mall": n["mall"], "n_estacao": n["estacao"], "n_hiper": n["hiper"]})
    return pd.DataFrame(rows)


def fitness_fora_mapeado():
    """CNPJ 9313 dentro de carro_10, marcando os que estao a < 150 m de academia mapeada ou Ultra."""
    fz = pd.read_parquet(OUT / "fitness_carro10.parquet")
    ref = pd.concat([pd.read_parquet(ISO / "academias_pontos.parquet", columns=["lat", "lng"]),
                     pd.read_parquet(ISO / "ultra_pontos.parquet", columns=["lat", "lng"])]).dropna()
    tree = BallTree(np.radians(ref[["lat", "lng"]].to_numpy(float)), metric="haversine")
    u = fz[["lat", "lng"]].drop_duplicates().reset_index(drop=True)
    cnt = tree.query_radius(np.radians(u[["lat", "lng"]].to_numpy(float)), r=150 / R_TERRA, count_only=True)
    u["perto_mapeado"] = cnt > 0
    return fz.merge(u, on=["lat", "lng"], how="left")


def contar_f5(fz, origem, ids, corte=None):
    """corte: None -> ESTOQUE; Series ponto_id -> 'AAAAMMDD' (estoque anterior a inauguracao)."""
    s = fz[fz.origem.eq(origem) & ~fz.perto_mapeado & fz.geo_nivel.eq("cep_numero")]  # regra dos 150 m so' vale com ponto exato
    if corte is None:
        s = s[s.data_inicio.fillna("99999999") < ESTOQUE]
    else:
        s = s[s.data_inicio.fillna("99999999") < s.ponto_id.map(corte).fillna("00000000")]
    return s.groupby("ponto_id").size().reindex(ids).fillna(0).to_numpy(float)


def familias(origem, ids, pop_pe15, pop_c10, lat, lng):
    fam = pd.read_parquet(OUT / "familias_por_poligono.parquet")
    fam = fam[fam.origem.eq(origem)]
    pe = fam[fam.area.eq("pe_15")].set_index("ponto_id").reindex(ids)
    c10 = fam[fam.area.eq("carro_10")].set_index("ponto_id").reindex(ids)
    inten = lambda n, pop: np.log1p(np.asarray(n, float)) - np.log1p(np.asarray(pop, float))
    anc = pd.read_parquet(OUT / "ancoras_pe15.parquet")
    tem_pe = pe.F1_fil.notna().to_numpy()
    f3 = f3_por_unidade(anc[anc.origem.eq(origem)], pd.DataFrame({"origem": origem, "ponto_id": ids, "lat": lat, "lng": lng, "tem_pe": tem_pe})).set_index("ponto_id").reindex(ids)
    fz = fitness_fora_mapeado()
    n5 = np.where(c10.F1_fil_c10.notna().to_numpy(), contar_f5(fz, origem, ids), np.nan)
    D = pd.DataFrame({
        "F1": inten(pe.F1_fil, pop_pe15), "F2": inten(pe.F2_fil, pop_pe15), "F3": f3.F3.to_numpy(float),
        "F5": np.log1p(1000 * n5 / np.clip(pop_c10, 1, None)),
        # sensibilidades / descritivos
        "F1_all": inten(pe.F1_all, pop_pe15), "F2_all": inten(pe.F2_all, pop_pe15),
        "F1_c10": inten(c10.F1_fil_c10, pop_c10), "F2_c10": inten(c10.F2_fil_c10, pop_c10),
        "F2b": inten(pe.F2b_cnefe, pop_pe15),
        "frac_exato_F2": (pe.F2_fil_exato / pe.F2_fil.replace(0, np.nan)).to_numpy(float),
        "em_shopping": f3.em_shopping.to_numpy(bool), "n_mall": f3.n_mall.to_numpy(), "n_estacao": f3.n_estacao.to_numpy(), "n_hiper": f3.n_hiper.to_numpy(),
        "edu_cnpj": c10.edu_cnpj.to_numpy(), "edu_osm": c10.edu_osm.to_numpy(), "n_f5": n5, "metro": pe.metro.to_numpy(),
    }, index=pd.Index(ids, name="ponto_id"))
    return D, fz


# =================== amostras ===================
FUNIL = {}
def fech():
    f = pd.read_parquet(SC / "fech_mensal_financeiro.parquet")
    f.loc[(f.unidade_id == "guaruja-sp") & (f.competencia == "2026-08"), "faturamento"] = 217525.74
    return f


def idade_meses(inaug, ref):
    inaug = pd.to_datetime(inaug); ref = pd.Timestamp(ref)
    return (ref.year - inaug.dt.year) * 12 + (ref.month - inaug.dt.month)


def faixas_idade(meses, faixas):
    """faixas: lista de (nome, lo, hi) exceto a referencia (>= 24)."""
    return pd.DataFrame({n: ((meses >= lo) & (meses <= hi)).astype(float) for n, lo, hi in faixas})


def amostra_S1():
    b = pd.read_parquet(ISO / "testes_v2" / "base_ultra.parquet")
    B = b[b.metragem.notna() & ~b.confianca.eq("baixa") & b["pop__carro_10"].notna()]
    # plaza-sul-sp: pino na Rua Itaucama, 1,34 km do endereco real (Shopping Plaza Sul, Praca Leonor Kaupa 100;
    # listagens publicas WellHub/TotalPass/Waze). Isocrona medida no lugar errado -> fora, antes de ver desfecho.
    B = B[B.unidade_id.ne("plaza-sul-sp")].reset_index(drop=True)
    f = fech()
    inaug = f.groupby("unidade_id").inauguracao.first().reindex(B.unidade_id).to_numpy()
    # idade no mes MEDIANO dos meses validos de 2025 (auditoria: data fixa jogava unidade de 4 meses na referencia >= 24)
    v = validos(f, "2025-01", "2025-12")
    mes_med = v.groupby("unidade_id").competencia.agg(lambda s: pd.Period(sorted(s)[len(s) // 2], "M").to_timestamp()).reindex(B.unidade_id)
    ina = pd.to_datetime(pd.Series(inaug))
    B["idade_m"] = (mes_med.dt.year.to_numpy() - ina.dt.year.to_numpy()) * 12 + (mes_med.dt.month.to_numpy() - ina.dt.month.to_numpy())
    assert B.idade_m.notna().all() and (B.idade_m >= 6).all(), "idade fora das faixas"
    B["inaug_yyyymmdd"] = pd.to_datetime(pd.Series(inaug)).dt.strftime("%Y%m%d").to_numpy()
    Xb = pd.DataFrame({"log_m2": np.log(B.metragem), "log_renda": np.log(B["renda_pc__carro_10"].clip(lower=300)), "log_pop": np.log1p(B["pop__carro_10"])})
    Xb = pd.concat([Xb, faixas_idade(B.idade_m, [("idade_6_11", 6, 11), ("idade_12_23", 12, 23)])], axis=1)
    conc = np.log1p(1000 * B["oferta_ponderada__carro_10"] / B["pop__carro_10"].clip(lower=1))
    D, fz = familias("ultra_v2", B.unidade_id.tolist(), B["pop__pe_15"].to_numpy(), B["pop__carro_10"].to_numpy(), B.lat.to_numpy(), B.lng.to_numpy())
    D["F5_pre_inaug"] = np.log1p(1000 * contar_f5(fz, "ultra_v2", B.unidade_id.tolist(), B.set_index("unidade_id").inaug_yyyymmdd) / B["pop__carro_10"].clip(lower=1).to_numpy())
    return B, Xb, conc.to_numpy(), D


def nz(s):
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower().strip()


def amostra_S2():
    al = pd.read_parquet(SC / "vps" / "alunos_reais_por_unidade.parquet")
    sf = al[al.rede.eq("smart_fit") & al.confianca_match.eq("alta")].copy()
    FUNIL["S2 smart_fit alta no crosswalk"] = len(sf)
    fam = pd.read_parquet(OUT / "familias_por_poligono.parquet")
    ids = set(fam[fam.origem.eq("smartfit")].ponto_id)
    sf = sf[sf.concorrente_id.isin(ids)].drop_duplicates("concorrente_id")
    at = pd.concat([pd.read_parquet(f, columns=["ponto_id", "tipo", "cenario", "pop", "renda_pc", "oferta_ponderada", "area_km2", "lat", "lng"])
                    for f in sorted((ISO / "atributos_v2").glob("*.parquet"))])
    at = at[at.tipo.eq("academia") & at.ponto_id.isin(ids)].drop_duplicates(["ponto_id", "cenario"])
    pv = at.pivot_table(index="ponto_id", columns="cenario", values=["pop", "renda_pc", "oferta_ponderada", "area_km2"], aggfunc="first")
    ll = at.groupby("ponto_id")[["lat", "lng"]].first()
    k = pd.read_excel(ROOT / "data" / "validacao" / "KPIs_Smart_2025_02 (1).xlsx", sheet_name="Base")
    k["kk"] = k.Nome.map(nz) + "|" + k.Sigla.str[3:5]
    k = k.drop_duplicates(["Sigla", "Data_Ref"])
    # o crosswalk usou o nome do ULTIMO mes (trava abaixo); a ambiguidade de nome so' importa nesse mes.
    # Serie, maturidade e desfecho vao por Sigla com o historico INTEIRO (renomeacao nao quebra; auditoria 2)
    dt_cw = set(al.loc[al.rede.eq("smart_fit"), "fonte_alunos"].str.extract(r"\((\d{4}-\d{2}-\d{2})\)")[0])
    assert dt_cw == {k.Data_Ref.max().strftime("%Y-%m-%d")}, (dt_cw, k.Data_Ref.max())
    ult = k[k.Data_Ref.eq(k.Data_Ref.max())]
    amb = set(ult.kk[ult.kk.duplicated()])
    kk2sig = ult[~ult.kk.isin(amb)].set_index("kk").Sigla
    FUNIL["S2 alta + isocrona"] = len(sf)
    sf["kk"] = sf.rotulo_fonte.map(nz) + "|" + sf.uf
    sf = sf[~sf.kk.duplicated(keep=False)]  # duas unidades com o mesmo nome|UF recebiam o mesmo y
    FUNIL["S2 nome|UF unico no crosswalk"] = len(sf)
    sf["sigla"] = sf.kk.map(kk2sig)
    sf = sf[sf.sigla.notna()]
    FUNIL["S2 casada a Sigla (nome unico no ultimo mes)"] = len(sf)
    first = k.groupby("Sigla").Data_Ref.min()
    sf["primeiro"] = sf.sigla.map(first)
    sf = sf[sf.primeiro <= pd.Timestamp("2024-07-31")].reset_index(drop=True)
    FUNIL["S2 madura (no painel ate 2024-07)"] = len(sf)
    sf["idade_m"] = np.where(sf.primeiro <= pd.Timestamp("2023-01-31"), 999, idade_meses(sf.primeiro, "2025-07-01"))
    assert (sf.idade_m >= 12).all()
    sf["franquia"] = sf.sigla.map(k.groupby("Sigla").Propriedade.agg(lambda s: s.mode().iat[0])).eq("Franquia").astype(float)
    g = lambda v, c: pv[(v, c)].reindex(sf.concorrente_id).to_numpy(float)
    pop_c10, pop_pe = g("pop", "carro_10min"), g("pop", "pe_15min")
    ok = np.isfinite(pop_c10) & (pop_c10 > 0) & np.isfinite(pop_pe) & np.isfinite(g("renda_pc", "carro_10min"))
    sf = sf[ok].reset_index(drop=True); pop_c10, pop_pe = pop_c10[ok], pop_pe[ok]
    FUNIL["S2 com atributos da isocrona"] = len(sf)
    Xb = pd.DataFrame({"log_renda": np.log(np.clip(g("renda_pc", "carro_10min"), 300, None)), "log_pop": np.log1p(pop_c10)})
    Xb = pd.concat([Xb, faixas_idade(sf.idade_m, [("idade_12_23", 12, 23)]), sf[["franquia"]]], axis=1)
    conc = np.log1p(1000 * g("oferta_ponderada", "carro_10min") / np.clip(pop_c10, 1, None))
    D, _ = familias("smartfit", sf.concorrente_id.tolist(), pop_pe, pop_c10, ll.lat.reindex(sf.concorrente_id).to_numpy(), ll.lng.reindex(sf.concorrente_id).to_numpy())
    return sf, Xb, conc, D, k


def amostra_multirede(marca):
    p = pd.read_parquet(ISO / "multirede" / "perfil.parquet")
    p = p[p.marca.eq(marca) & (p.alunos_reais > 0) & p["pop__carro_10"].notna()]
    if marca == "engenharia_do_corpo":
        p = p[p.metragem.notna()]
    p = p.reset_index(drop=True)
    Xb = pd.DataFrame({"log_renda": np.log(p["renda_pc__carro_10"].clip(lower=300)), "log_pop": np.log1p(p["pop__carro_10"])})
    if marca == "engenharia_do_corpo":
        Xb.insert(0, "log_m2", np.log(p.metragem))
    conc = np.log1p(1000 * p["oferta_ponderada__carro_10"] / p["pop__carro_10"].clip(lower=1)).to_numpy()
    D, _ = familias("multirede", p.ponto_id.tolist(), p["pop__pe_15"].to_numpy(), p["pop__carro_10"].to_numpy(), p.lat.to_numpy(), p.lng.to_numpy())
    return p, Xb, conc, D


# =================== estatistica ===================
def com_intercepto(X):
    return np.column_stack([np.ones(len(X)), X])


def oof_loo(X, y):
    Xi = com_intercepto(X)
    beta, *_ = np.linalg.lstsq(Xi, y, rcond=None)
    e = y - Xi @ beta
    h = np.einsum("ij,ji->i", Xi, np.linalg.pinv(Xi.T @ Xi) @ Xi.T)
    return y - e / (1 - h)


def oof_grupos(X, y, folds):
    Xi = com_intercepto(X); p = np.empty(len(y))
    for tr, te in folds:
        b, *_ = np.linalg.lstsq(Xi[tr], y[tr], rcond=None); p[te] = Xi[te] @ b
    return p


def r2(y, p):
    return 1 - ((y - p) ** 2).sum() / ((y - y.mean()) ** 2).sum()


def coef_ols(X, y):
    Z = (X - X.mean(0)) / np.where(X.std(0) > 0, X.std(0), 1)
    b, *_ = np.linalg.lstsq(com_intercepto(Z), y, rcond=None)
    return b[-1] / y.std()


def delta(Xb, f, y, oof):
    return r2(y, oof(np.column_stack([Xb, f]), y)) - r2(y, oof(Xb, y))


def permutador(grupos, rng):
    """None -> permutacao livre; senao permuta so' DENTRO de cada grupo (dependencia espacial; auditoria)."""
    if grupos is None:
        return lambda e: rng.permutation(e)
    idx = [np.nonzero(grupos == g)[0] for g in np.unique(grupos)]
    idx = [i for i in idx if len(i) > 1]

    def perm(e):
        e2 = e.copy()
        for i in idx:
            e2[i] = e[rng.permutation(i)]
        return e2
    return perm


def freedman_lane(Xb, f, y, oof, B, perm):
    Xi = com_intercepto(Xb); b, *_ = np.linalg.lstsq(Xi, y, rcond=None); yh = Xi @ b; e = y - yh
    obs = delta(Xb, f, y, oof)
    cnt = sum(delta(Xb, f, yh + perm(e), oof) >= obs for _ in range(B))
    return obs, (1 + cnt) / (B + 1)


def holm(ps):
    ps = np.asarray(ps, float); k = len(ps); o = np.argsort(ps); adj = np.empty(k); cum = 0
    for j, i in enumerate(o):
        cum = max(cum, (k - j) * ps[i]); adj[i] = min(1.0, cum)
    return adj


def boot_ic(Xb, f, y, oof, rng, nb=2000, grupos=None):
    """IC informativo; com grupos, bootstrap de cluster (reamostra grupos inteiros)."""
    pa, pb = oof(Xb, y), oof(np.column_stack([Xb, f]), y); n = len(y); ds = []
    if grupos is not None:
        gi = [np.nonzero(grupos == g)[0] for g in np.unique(grupos)]
    for _ in range(nb):
        if grupos is None:
            i = rng.integers(0, n, n)
        else:
            i = np.concatenate([gi[j] for j in rng.integers(0, len(gi), len(gi))])
        ds.append(r2(y[i], pb[i]) - r2(y[i], pa[i]))
    return np.percentile(ds, [2.5, 97.5])


def poder(Xb, f, y, oof, alfa, sinal, pr2s, reps, B, rng, grupos):
    perm = permutador(grupos, rng)
    Xi = com_intercepto(Xb); b, *_ = np.linalg.lstsq(Xi, y, rcond=None); yh = Xi @ b; e = y - yh
    fp = f - Xi @ np.linalg.lstsq(Xi, f, rcond=None)[0]
    # auditoria 2: a permutacao restrita preserva a media de e por grupo, entao a associacao REAL F-desfecho
    # entre grupos sobreviveria no y simulado. Remove de e a parte linear em [media_g(fp), fp - media_g(fp)].
    if grupos is not None:
        mg = pd.Series(fp).groupby(grupos).transform("mean").to_numpy()
        Z = np.column_stack([mg, fp - mg])
    else:
        Z = fp[:, None]
    e = e - Z @ (np.linalg.pinv(Z) @ e)
    out = {}
    for pr2 in pr2s:
        beta = sinal * np.sqrt(pr2 / (1 - pr2) * e.var() / fp.var())
        hits = []
        for _ in range(reps):
            ys = yh + perm(e) + beta * fp
            d, p = freedman_lane(Xb, f, ys, oof, B, perm)
            hits.append(bool((d > 0) and (np.sign(coef_ols(np.column_stack([Xb, f]), ys)) == sinal) and (p < alfa)))
        r = float(np.mean(hits)); out[pr2] = (r, float(np.sqrt(r * (1 - r) / reps)))
    return out


def veredito(c1, c1b, c2):
    """§7 (v1.1): C1r = C1 e C1b. c2 in {True, False, None (nao avaliavel)}."""
    c1r = bool(c1 and c1b)
    if c1r and c2 is True:
        return "ENTRA"
    if c1r and c2 is None:
        return "candidata não confirmada"
    if c1r:
        return "sinal só na Ultra, não replica"
    if c2 is True:
        return "sinal só na Smart Fit (hipótese, não entra)"
    return "sem ganho detectável neste N"


def _trava_veredito():
    esperado = {(True, True, True): "ENTRA", (True, True, None): "candidata não confirmada", (True, True, False): "sinal só na Ultra, não replica",
                (True, False, True): "sinal só na Smart Fit (hipótese, não entra)", (False, True, True): "sinal só na Smart Fit (hipótese, não entra)",
                (False, False, True): "sinal só na Smart Fit (hipótese, não entra)", (True, False, False): "sem ganho detectável neste N",
                (True, False, None): "sem ganho detectável neste N", (False, False, False): "sem ganho detectável neste N",
                (False, True, None): "sem ganho detectável neste N", (False, False, None): "sem ganho detectável neste N", (False, True, False): "sem ganho detectável neste N"}
    for k_, v in esperado.items():
        assert veredito(*k_) == v, (k_, veredito(*k_), v)


# =================== etapas ===================
def _completos(df, X, conc, D, nome):
    m = np.isfinite(D[FAMS].to_numpy(float)).all(1) & np.isfinite(X.to_numpy(float)).all(1) & np.isfinite(conc)
    if (~m).sum():
        print(f"{nome}: {(~m).sum()} unidade(s) sem feature completa, fora", flush=True)
    return df[m].reset_index(drop=True), X[m].reset_index(drop=True), conc[m], D[m]


def dados_base():
    B, X1, conc1, D1 = _completos(*amostra_S1(), "S1")
    sf, X2, conc2, D2, k = amostra_S2()
    sf, X2, conc2, D2 = _completos(sf, X2, conc2, D2, "S2")
    return B, X1, conc1, D1, sf, X2, conc2, D2, k


def xbase(X, conc, fam):
    X = X.to_numpy(float)
    return np.column_stack([X, conc]) if fam == "F5" else X


def folds_metro(grupos, n=10):
    return list(GroupKFold(n_splits=n).split(np.zeros(len(grupos)), groups=grupos))


def etapa_portoes():
    _trava_veredito()
    rng = np.random.default_rng(20260925)
    B, X1, conc1, D1, sf, X2, conc2, D2, k = dados_base()
    md = [f"# Portões sem desfecho — protocolo_poi_uni00 v1.1\n\nS1 Ultra N = {len(B)} (plaza-sul-sp fora: pino errado); S2 Smart Fit N = {len(sf)} (confiança alta, nome|UF único, madura, com isócrona).\n"]
    md.append(f"Idade S1 (mês mediano válido de 2025): mín {B.idade_m.min()}, faixas 6–11 = {int(((B.idade_m >= 6) & (B.idade_m <= 11)).sum())}, 12–23 = {int(((B.idade_m >= 12) & (B.idade_m <= 23)).sum())}, ≥ 24 = {int((B.idade_m >= 24).sum())}. S2: 12–23 = {int(((sf.idade_m >= 12) & (sf.idade_m <= 23)).sum())}, ≥ 24 = {int((sf.idade_m >= 24).sum())}.\n")
    js = {"n_S1": len(B), "n_S2": len(sf)}
    cov = X1.assign(log_area_pe15=np.log(B["area_km2__pe_15"].to_numpy()), log_area_c10=np.log(B["area_km2__carro_10"].to_numpy()), conc=conc1, idade_m=B.idade_m.to_numpy())
    C = pd.DataFrame({f: [np.corrcoef(D1[f], cov[c])[0, 1] for c in cov.columns] for f in FAMS}, index=cov.columns)
    md.append("## P1 colinearidade (Pearson, S1)\n"); md.append(C.round(2).to_markdown())
    CF = D1[FAMS].corr(); md.append("\nEntre famílias:\n"); md.append(CF.round(2).to_markdown())
    base_cols = [c for c in cov.columns if c not in ("conc", "idade_m")]
    sobrevive = []
    for f in FAMS:
        rmax = C.loc[base_cols + (["conc"] if f == "F5" else []), f].abs().max()
        if rmax >= 0.7:
            md.append(f"- {f}: |r| máx. com a base = {rmax:.2f} >= 0,7 -> NÃO IDENTIFICÁVEL, sai do teste"); continue
        if any(abs(CF.loc[f, g]) >= 0.8 for g in sobrevive):
            md.append(f"- {f}: |r| >= 0,8 com família anterior -> fundida na anterior"); continue
        sobrevive.append(f)
    n1 = int(D1.F3.sum()); md.append(f"\n## P2 suporte F3 (S1): {n1} com F3 = 1, {len(D1) - n1} com F3 = 0; em shopping (fato): {int(D1.em_shopping.sum())}")
    if "F3" in sobrevive and (n1 < 10 or len(D1) - n1 < 10):
        sobrevive.remove("F3"); md.append("-> F3 NÃO TESTÁVEL")
    md.append(f"(S2: {int(D2.F3.sum())} de {len(D2)} com F3 = 1; em shopping {int(D2.em_shopping.sum())})")
    md.append("\n## P3 idade e metragem\n")
    for f in FAMS:
        md.append(f"- {f}: r(idade) = {np.corrcoef(D1[f], B.idade_m)[0, 1]:+.2f}; r(log m²) = {np.corrcoef(D1[f], X1.log_m2)[0, 1]:+.2f}")
    E, XE, _, DE = amostra_multirede("engenharia_do_corpo")
    guard = {}
    for f in FAMS:
        ff = np.concatenate([D1[f].to_numpy(float), DE[f].to_numpy(float)]); mm = np.concatenate([X1.log_m2.to_numpy(), XE.log_m2.to_numpy()])
        okf = np.isfinite(ff) & np.isfinite(mm)
        rho = spearmanr(ff[okf], mm[okf])[0]
        assert np.isfinite(rho), f"guarda C2 {f} indefinida"
        guard[f] = bool(abs(rho) >= 0.3)
        md.append(f"- guarda C2 {f}: ρ(F, log m²) Ultra+EdC (N = {okf.sum()} de {len(ff)}) = {rho:+.2f} -> {'C2 NÃO AVALIÁVEL' if guard[f] else 'C2 avaliável'}")
    D1.drop(columns=["metro"]).to_csv(OUT / "fatos_poi_ultra.csv", sep=";", encoding="utf-8-sig")  # fato descritivo (sem desfecho)
    md.append("\n## Funil da S2\n\n" + "\n".join(f"- {k_}: {v}" for k_, v in FUNIL.items()) + f"\n- S2 com features completas: {len(sf)}")
    m = len(sobrevive); alfa = 0.05 / max(m, 1)
    md.append(f"\n## P4 poder (famílias testadas: {sobrevive}; limiar do 1º passo do Holm = {alfa:.4f}; permutação restrita dentro de UF em S1 e de metrô em S2)\n")
    y1 = np.log(desfecho_S1(B)[0]); y2 = np.log(desfecho_S2(sf, k))  # so' o residuo do modelo BASE entra (declarado)
    ok1, ok2 = np.isfinite(y1), np.isfinite(y2)
    g1, g2 = B.uf.to_numpy()[ok1], D2.metro.to_numpy()[ok2]
    fo2 = folds_metro(g2)
    pw, pw10 = [], {}
    for f in sobrevive:
        p1 = poder(xbase(X1, conc1, f)[ok1], D1[f].to_numpy(float)[ok1], y1[ok1], oof_loo, alfa, SINAL[f], (0.03, 0.05, 0.10, 0.20), 200, 399, rng, g1)
        p2 = poder(xbase(X2, conc2, f)[ok2], D2[f].to_numpy(float)[ok2], y2[ok2], lambda X, y: oof_grupos(X, y, fo2), alfa, SINAL[f], (0.01, 0.02, 0.05), 100, 199, rng, g2)
        pw10[f] = p1[0.10][0]
        pw.append({"familia": f, **{f"S1 pr2={k_}": f"{v[0]:.2f} ± {v[1]:.2f}" for k_, v in p1.items()}, **{f"S2 pr2={k_}": f"{v[0]:.2f} ± {v[1]:.2f}" for k_, v in p2.items()}})
        print(f"poder {f} feito", flush=True)
    md.append(pd.DataFrame(pw).to_markdown(index=False))
    md.append(f"\n(Poder de S1 medido com α/{m} (regra pré-P5); o limiar real de S1 após o P5 é 0,05/len(s1_fams), então o poder de S1 publicado é conservador.)")
    md.append(f"\n(± = erro Monte Carlo. S1: 200 réplicas, B = 399, LOO. S2: 100 réplicas, B = 199, GroupKFold por metrô. N efetivo: S1 {ok1.sum()}, S2 {ok2.sum()}.)")
    s1_fams = [f for f in sobrevive if pw10[f] >= 0.20]  # P5 (emenda v1.1)
    md.append(f"\n## P5 (v1.1): famílias com poder < 0,20 em S1 (R² parcial 0,10) saem do Holm de S1\n\nS1 testa {s1_fams}; S2 testa {sobrevive}.")
    js.update({"s1_fams": s1_fams, "s2_fams": sobrevive})
    js.update({"sobrevivem": sobrevive, "guarda_C2_nao_avaliavel": guard, "poder": pw, "alfa_holm_1o_passo": alfa, "n_S1_desfecho": int(ok1.sum()), "n_S2_desfecho": int(ok2.sum())})
    (OUT / "portoes.md").write_text("\n".join(md), encoding="utf-8")
    (OUT / "portoes.json").write_text(json.dumps(js, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("\n".join(md))


def validos(f, ini, fim):
    return f[f.mes_completo & f.operacao_mes_cheio & f.origem_faturamento.eq("financeiro") & (f.meses_operacao >= 6) & f.competencia.between(ini, fim)]


def desfecho_S1(B, ini="2025-01", fim="2025-12", col="faturamento"):
    f = validos(fech(), ini, fim).drop_duplicates(["unidade_id", "competencia"])
    g = f.groupby("unidade_id")[col].agg(["median", "count"])
    s = g.loc[g["count"] >= 3, "median"]
    return B.unidade_id.map(s).to_numpy(float), None


def desfecho_S2(sf, k):
    kk = k[k.Data_Ref.between(pd.Timestamp("2025-01-01"), pd.Timestamp("2025-12-31"))].groupby("Sigla")["Alunos Totais SF"].agg(["median", "count"])
    s = kk.loc[kk["count"] >= 3, "median"]
    return sf.sigla.map(s).to_numpy(float)


def etapa_teste():
    _trava_veredito()
    reg = POIDIR / "REGISTRO_CONGELAMENTO.txt"
    assert reg.exists(), "congelar antes (REGISTRO_CONGELAMENTO.txt)"
    for linha in reg.read_text(encoding="utf-8").splitlines():
        if linha.startswith("sha256 "):
            _, h, arq = linha.split(" ", 2)
            atual = hashlib.sha256((ROOT / arq).read_bytes()).hexdigest()
            assert atual == h, f"{arq} mudou depois do congelamento"
    port = json.loads((OUT / "portoes.json").read_text(encoding="utf-8"))
    fams = port["sobrevivem"]; guard = port["guarda_C2_nao_avaliavel"]; s1_fams = port["s1_fams"]; s2_fams = port["s2_fams"]
    rng = np.random.default_rng(99)
    B, X1, conc1, D1, sf, X2, conc2, D2, k = dados_base()
    md = [f"# Teste pré-registrado de POI — protocolo v1.1\n\nFamílias testadas (portões): {fams}\n"]
    js = {}
    # ---------- S1
    y1 = np.log(desfecho_S1(B)[0]); ok = np.isfinite(y1)
    y1, D1s, X1s, c1s, Bs = y1[ok], D1[ok], X1[ok].reset_index(drop=True), conc1[ok], B[ok].reset_index(drop=True)
    g1 = Bs.uf.to_numpy(); perm1 = permutador(g1, rng)
    res1 = []
    for f in s1_fams:
        Xb = xbase(X1s, c1s, f); ff = D1s[f].to_numpy(float)
        d, p = freedman_lane(Xb, ff, y1, oof_loo, 999, perm1)
        ea = y1 - oof_loo(Xb, y1); eb = y1 - oof_loo(np.column_stack([Xb, ff]), y1)
        i = int(np.argmax(ea ** 2 - eb ** 2)); m_ = np.ones(len(y1), bool); m_[i] = False
        cf = coef_ols(np.column_stack([Xb, ff]), y1); ic = boot_ic(Xb, ff, y1, oof_loo, rng)
        res1.append({"familia": f, "dR2_LOO_OLS": d, "IC95_boot": f"[{ic[0]:+.3f}; {ic[1]:+.3f}]", "p_perm": p, "coef_padr": cf,
                     "sinal_ok": bool(np.sign(cf) == SINAL[f]), "mais_influente": Bs.unidade_id[i], "dR2_sem_ela": delta(Xb[m_], ff[m_], y1[m_], oof_loo)})
    t1 = pd.DataFrame(res1)
    t1["p_holm"] = holm(t1.p_perm) if len(t1) else []
    md.append(f"## S1 — Ultra, faturamento Financeiro 2025 (N = {len(y1)}; R² LOO base = {r2(y1, oof_loo(X1s.to_numpy(float), y1)):+.3f})\n")
    md.append(t1.round(4).to_markdown(index=False))
    # ---------- S2
    y2 = np.log(desfecho_S2(sf, k)); ok2 = np.isfinite(y2)
    y2, D2s, X2s, c2s = y2[ok2], D2[ok2], X2[ok2].reset_index(drop=True), conc2[ok2]
    g2 = D2s.metro.to_numpy(); fo = folds_metro(g2); oofg = lambda X, y: oof_grupos(X, y, fo); perm2 = permutador(g2, rng)
    res2 = []
    for f in s2_fams:
        Xb = xbase(X2s, c2s, f); ff = D2s[f].to_numpy(float)
        d, p = freedman_lane(Xb, ff, y2, oofg, 999, perm2)
        cf = coef_ols(np.column_stack([Xb, ff]), y2); ic = boot_ic(Xb, ff, y2, oofg, rng, grupos=g2)
        res2.append({"familia": f, "dR2_GKF_metro_OLS": d, "IC95_boot_cluster": f"[{ic[0]:+.3f}; {ic[1]:+.3f}]", "p_perm": p,
                     "coef_padr": cf, "sinal_ok": bool(np.sign(cf) == SINAL[f]), "dR2_LOO_OLS": delta(Xb, ff, y2, oof_loo)})
    t2 = pd.DataFrame(res2)
    t2["p_holm"] = holm(t2.p_perm) if len(t2) else []
    md.append(f"\n## S2 — Smart Fit, alunos 2025 (N = {len(y2)}; R² GroupKFold-metrô base = {r2(y2, oofg(X2s.to_numpy(float), y2)):+.3f})\n")
    md.append(t2.round(4).to_markdown(index=False))
    crit = []
    T1, T2 = t1.set_index("familia"), t2.set_index("familia")
    for f in fams:
        if f in T1.index:
            c1 = bool(T1.dR2_LOO_OLS[f] > 0 and T1.sinal_ok[f] and T1.p_holm[f] < 0.05); c1b = bool(T1.dR2_sem_ela[f] > 0)
        else:
            c1, c1b = False, False  # P5: nao avaliavel em S1
        c2 = None if guard.get(f) else bool(T2.dR2_GKF_metro_OLS[f] > 0 and T2.sinal_ok[f] and T2.p_holm[f] < 0.05)
        crit.append({"familia": f, "C1": c1 if f in T1.index else "não avaliável (P5)", "C1b": c1b if f in T1.index else "-", "C2": c2, "veredito": veredito(c1, c1b, c2)})
    md.append("\n## Critério (§7)\n"); md.append(pd.DataFrame(crit).to_markdown(index=False))
    js.update({"S1": t1.to_dict("records"), "S2": t2.to_dict("records"), "criterio": crit})
    ser = lambda o: o.item() if hasattr(o, "item") else str(o)
    (OUT / "resultado_teste_poi.md").write_text("\n".join(md), encoding="utf-8")  # checkpoint antes da §8
    (OUT / "resultado_teste_poi.json").write_text(json.dumps(js, ensure_ascii=False, indent=1, default=ser), encoding="utf-8")
    print("\n".join(md), flush=True)
    # ---------- relatado sem decidir (§8)
    md.append("\n## Relatado sem decidir (§8) — p sem correção, leitura exploratória\n")
    linhas = []

    def lin(amostra, var, Xb, ff, y, oof, nome_oof, grupos=None):
        o = np.isfinite(ff) & np.isfinite(y) & np.isfinite(Xb).all(1)
        if o.sum() < 10:
            return
        Xb, ff, y = Xb[o], ff[o], y[o]
        gg = grupos[o] if grupos is not None else None
        if nome_oof == "LOO":
            oof = oof_loo
        else:  # GroupKFold: dobras refeitas sobre a amostra mascarada (auditoria 2)
            fo_ = folds_metro(gg, min(10 if "metr" in nome_oof else 8, len(np.unique(gg))))
            oof = lambda X, y_: oof_grupos(X, y_, fo_)
        d, p = freedman_lane(Xb, ff, y, oof, 499, permutador(gg, rng))
        linhas.append({"amostra": amostra, "variavel": var, "validacao": nome_oof, "N": int(o.sum()), "dR2": d, "p_perm": p, "coef_padr": coef_ols(np.column_stack([Xb, ff]), y)})

    for f in fams:
        Xb = xbase(X1s, c1s, f); ff = D1s[f].to_numpy(float)
        lin("S1", f, Xb, ff, y1, None, "GroupKFold UF", g1)
        pr = lambda X: np.array([make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 3, 30))).fit(np.delete(X, i, 0), np.delete(y1, i)).predict(X[i:i + 1])[0] for i in range(len(y1))])
        linhas.append({"amostra": "S1", "variavel": f, "validacao": "LOO ridge", "N": len(y1), "dR2": r2(y1, pr(np.column_stack([Xb, ff]))) - r2(y1, pr(Xb)), "p_perm": np.nan, "coef_padr": np.nan})
    for var, base_f in [("F1_all", "F1"), ("F2", "F2"), ("F2_all", "F2"), ("F1_c10", "F1"), ("F2_c10", "F2"), ("F2b", "F2"), ("F5", "F5"), ("F5_pre_inaug", "F5")]:
        lin("S1", var, xbase(X1s, c1s, base_f), D1s[var].to_numpy(float), y1, None, "LOO", g1)
    m12 = (Bs.idade_m >= 12).to_numpy()
    for f in fams:
        lin("S1 idade>=12", f, xbase(X1s, c1s, f)[m12], D1s[f].to_numpy(float)[m12], y1[m12], None, "LOO", g1[m12])
        lin("S1 + dummy DF", f, np.column_stack([xbase(X1s, c1s, f), Bs.uf.eq("DF").to_numpy(float)]), D1s[f].to_numpy(float), y1, None, "LOO", g1)
    y1b = np.log(desfecho_S1(B, "2026-01", "2026-08")[0])[ok]; y3 = np.log(desfecho_S1(B, col="ativos")[0])[ok]
    for f in fams:
        lin("S1 estabilidade 2026-01..08", f, xbase(X1s, c1s, f), D1s[f].to_numpy(float), y1b, None, "LOO", g1)
        lin("S3 Ultra ativos 2025", f, xbase(X1s, c1s, f), D1s[f].to_numpy(float), y3, None, "LOO", g1)
    for var, base_f in [("F2", "F2"), ("F5", "F5")]:
        lin("S2", var, xbase(X2s, c2s, base_f), D2s[var].to_numpy(float), y2, None, "GroupKFold metrô", g2)
    if fams:
        comc = "F5" in fams
        Xb = np.column_stack([X1s.to_numpy(float), c1s]) if comc else X1s.to_numpy(float); FF = D1s[fams].to_numpy(float)
        linhas.append({"amostra": "S1", "variavel": "todas as famílias", "validacao": "LOO", "N": len(y1), "dR2": r2(y1, oof_loo(np.column_stack([Xb, FF]), y1)) - r2(y1, oof_loo(Xb, y1)), "p_perm": np.nan, "coef_padr": np.nan})
        Xb = np.column_stack([X2s.to_numpy(float), c2s]) if comc else X2s.to_numpy(float); FF = D2s[fams].to_numpy(float)
        linhas.append({"amostra": "S2", "variavel": "todas as famílias", "validacao": "GroupKFold metrô", "N": len(y2), "dR2": r2(y2, oofg(np.column_stack([Xb, FF]), y2)) - r2(y2, oofg(Xb, y2)), "p_perm": np.nan, "coef_padr": np.nan})
    for marca in ("skyfit", "engenharia_do_corpo"):
        P_, Xm, cm, Dm = amostra_multirede(marca); ym = np.log(P_.alunos_reais.to_numpy(float))
        for f in fams:
            lin(marca, f, xbase(Xm, cm, f), Dm[f].to_numpy(float), ym, None, "LOO")
    md.append(pd.DataFrame(linhas).round(4).to_markdown(index=False))
    js["relatado"] = linhas
    (OUT / "resultado_teste_poi.md").write_text("\n".join(md), encoding="utf-8")
    (OUT / "resultado_teste_poi.json").write_text(json.dumps(js, ensure_ascii=False, indent=1, default=ser), encoding="utf-8")
    print("\n".join(md[-2:]))


if __name__ == "__main__":
    etapa = sys.argv[sys.argv.index("--etapa") + 1]
    {"portoes": etapa_portoes, "teste": etapa_teste}[etapa]()
