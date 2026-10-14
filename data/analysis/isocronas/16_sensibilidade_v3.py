# Sensibilidade da v3: cada premissa varia sozinha (demais no meio da faixa); mede rho do ranking entre os extremos,
# quantas unidades trocam de lado de 1 e a variacao da aderencia esperado x real.
import importlib.util, warnings
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import spearmanr
warnings.filterwarnings("ignore")
ISO = Path(r"C:\Users\Felipe\AppData\Local\Temp\claude\C--dev-motor-de-expansao\9259d0a1-7dda-49bd-a390-c88f3d4ac1a6\scratchpad\iso")
spec = importlib.util.spec_from_file_location("v3", ISO / "15_aproveitamento_v3.py"); v3 = importlib.util.module_from_spec(spec); spec.loader.exec_module(v3)
v2 = v3.v2
import geopandas as gpd
from shapely import wkb
ac, tree = v2.oferta()
fech = pd.read_parquet(v2.SC / "fech_mensal_financeiro.parquet")
fin = fech[fech.origem_faturamento.eq("financeiro") & fech.mes_completo & fech.operacao_mes_cheio]
fat = fin[fin.competencia == "2026-08"].set_index("unidade_id")["faturamento"].copy(); fat.loc["guaruja-sp"] = 217525.74
at12 = fech[fech.competencia.between("2025-09", "2026-08")].groupby("unidade_id")["ativos"].median()
bu = pd.read_parquet(ISO / "testes_v2" / "base_ultra.parquet").rename(columns={"unidade_id": "pid"})
bu["rede"] = "ultra"; bu["fat"] = bu.pid.map(fat); bu["ativos_ref"] = bu.pid.map(at12)
ultra_ref = bu.dropna(subset=["lat"])[["pid", "lat", "lng", "ativos_ref"]]
iso = pd.concat([pd.read_parquet(f, columns=["ponto_id", "tipo", "modo", "limite_s", "poligono_wkb"], filters=[("tipo", "==", "ultra")]) for f in sorted((ISO / "isocronas_v2").glob("metro_*.parquet"))])
polys = {c: dict(zip(s.ponto_id, gpd.GeoSeries([wkb.loads(b) for b in s.poligono_wkb], crs=4326).to_crs(5880).values)) for c, (m, l) in v2.CEN.items() for s in [iso[(iso.modo == m) & (iso.limite_s == l) & iso.poligono_wkb.notna()]]}
A = bu[bu.metragem.notna() & bu.fat.notna() & ~bu.confianca.eq("baixa") & bu["pop__carro_10"].notna()].reset_index(drop=True)
A = v2.crescimento(v2.componentes(A, polys, ac, tree, ultra_ref, auto_m=2.0))
y = A.fat.to_numpy(float); ticket = float(np.median(A.fat / A.ativos_ref)); rr = float(np.nanmedian(A["renda_pc__carro_10"]))
z = lambda s: ((s - s.median()) / s.std()).fillna(0).clip(-2, 2).to_numpy()
czh, czm = z(A["cres_hex_taxa"]), z(A["dim_media"])
mid = {k: (a + b) / 2 for k, (a, b) in v3.FAIXAS.items()}
def ap(pr, w=(1/3, 1/3, 1/3)):
    e = v3.esperado(A, pr, np.array(w), rr, czh, czm, ticket, True, True); a = y / e; return a / np.median(a), e
ref, eref = ap(mid)
lin = []
for k, (a, b) in v3.FAIXAS.items():
    lo, elo = ap({**mid, k: a}); hi, ehi = ap({**mid, k: b})
    lin.append({"premissa": k, "faixa": f"{a} a {b}", "rho_rank_entre_extremos": spearmanr(lo, hi)[0], "trocam_de_lado": int(((lo > 1) != (hi > 1)).sum()),
                "aderencia_min": min(spearmanr(elo, y)[0], spearmanr(ehi, y)[0]), "aderencia_max": max(spearmanr(elo, y)[0], spearmanr(ehi, y)[0])})
for nome, w in (("só carro 5 min", (1, 0, 0)), ("só carro 10 min", (0, 1, 0)), ("só a pé 15 min", (0, 0, 1))):
    x, ex = ap(mid, w); lin.append({"premissa": f"área: {nome}", "faixa": "vs peso igual", "rho_rank_entre_extremos": spearmanr(ref, x)[0], "trocam_de_lado": int(((ref > 1) != (x > 1)).sum()), "aderencia_min": spearmanr(ex, y)[0], "aderencia_max": spearmanr(eref, y)[0]})
t = pd.DataFrame(lin).sort_values("rho_rank_entre_extremos"); print(t.round(2).to_string(index=False))
# contribuicao de cada componente na aderencia: remove um por vez
print("\nAderência no meio das faixas:", round(spearmanr(eref, y)[0], 3))
for nome, pr in (("sem renda na demanda", {**mid, "elast_renda": 0}), ("sem renda no ticket", {**mid, "elast_ticket": 0}), ("sem crescimento (hex e município)", {**mid, "peso_cresc": 0, "peso_cres_mun": 0}), ("sem concorrência", {**mid, "proxy_indep": 0, "proxy_cadeia": 0})):
    print(f"  {nome}: {spearmanr(ap(pr)[1], y)[0]:+.3f}")
A2 = A.copy()
for c in v2.CEN: A2[f"cap_real__{c}"] = 0; A2[f"cap_rede__{c}"] = 0; A2[f"n_cadeia_proxy__{c}"] = 0; A2[f"n_indep__{c}"] = 0; A2[f"ultra_outras__{c}"] = 0
e = v3.esperado(A2, mid, np.array((1/3, 1/3, 1/3)), rr, czh, czm, ticket, True, True); print(f"  sem concorrência e sem canibalização: {spearmanr(e, y)[0]:+.3f}")
e = v3.esperado(A, {**mid, "dens_max": 1e9}, np.array((1/3, 1/3, 1/3)), rr, czh, czm, ticket, True, True); print(f"  sem teto de capacidade: {spearmanr(e, y)[0]:+.3f}")
print(f"  só metragem: {spearmanr(A.metragem, y)[0]:+.3f} | só pop carro 10: {spearmanr(A['pop__carro_10'], y)[0]:+.3f} | só renda carro 10: {spearmanr(A['renda_pc__carro_10'], y)[0]:+.3f}")
