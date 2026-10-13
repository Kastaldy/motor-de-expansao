# -*- coding: utf-8 -*-
"""Aproveitamento v3: a conta ganha (1) interacao metragem x concorrencia e (2) crescimento municipal.

(1) Teto de capacidade. Alunos esperados = minimo suave (harmonico) entre a captura da demanda e a capacidade:
      E = 1 / (1/(D*K/(K+C+U)) + 1/(K*dens_max))
    Com pouca concorrencia a captura e' grande e o teto K*dens_max manda: o resultado cresce com a metragem.
    Com muita concorrencia a captura e' pequena e manda a disputa. E' a hipotese do diretor, medida no v2
    (metragem pesa mais onde a concorrencia per capita e' baixa: +0,54 [+0,16; +0,88] em Ultra+EdC).
    Na v2 a formula fazia o contrario (sem concorrencia, E -> D e a metragem deixava de importar).
(2) Crescimento municipal (media das dimensoes, padronizada) multiplica o FATURAMENTO POR ALUNO:
      F = E * ticket * (renda/renda_ref)^elast_ticket * (1 + peso_cres_mun * z)
    porque no v2 o sinal apareceu no faturamento da Ultra (parcial +0,47) e nao no numero de alunos.
Estresse: 2.000 sorteios; dens_max em [2,0; 4,0] alunos/m2, peso_cres_mun em [0; 0,25]. Compara 4 variantes
(v2, +teto, +crescimento, ambos) pela aderencia esperado x real e pela estabilidade.
"""
import importlib.util
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from shapely import wkb

warnings.filterwarnings("ignore")
ISO = Path(r"C:\Users\Felipe\AppData\Local\Temp\claude\C--dev-motor-de-expansao\9259d0a1-7dda-49bd-a390-c88f3d4ac1a6\scratchpad\iso")
spec = importlib.util.spec_from_file_location("v2", ISO / "14_aproveitamento_v2.py"); v2 = importlib.util.module_from_spec(spec); spec.loader.exec_module(v2)
OUT = ISO / "aproveitamento_v3"; OUT.mkdir(exist_ok=True)
RNG = np.random.default_rng(42)
FAIXAS = {**v2.FAIXAS, "dens_max": (2.0, 4.0), "peso_cres_mun": (0.0, 0.25)}
N = 2000
MD = []


def esperado(d, pr, w, renda_ref, cres_hex_z, cres_mun_z, ticket_ref, teto, cresc):
    E = np.zeros(len(d))
    for j, c in enumerate(v2.CEN):
        pop = d[f"pop__{c}"].fillna(0).to_numpy(float); renda = d[f"renda_pc__{c}"].fillna(renda_ref).to_numpy(float)
        D = pop * pr["taxa"] * (renda / renda_ref) ** pr["elast_renda"] * (1 + pr["peso_cresc"] * cres_hex_z)
        C = (d[f"cap_real__{c}"] + d[f"cap_rede__{c}"] + d[f"n_cadeia_proxy__{c}"] * pr["proxy_cadeia"] + d[f"n_indep__{c}"] * pr["proxy_indep"]).fillna(0).to_numpy(float)
        U = d[f"ultra_outras__{c}"].fillna(0).to_numpy(float); K = d["metragem"].to_numpy(float) * pr["dens_ref"]
        cap = D * K / (K + C + U)
        if teto:
            cap = 1.0 / (1.0 / np.maximum(cap, 1e-9) + 1.0 / (d["metragem"].to_numpy(float) * pr["dens_max"]))
        E += w[j] * cap
    if ticket_ref is None:
        return E
    F = E * ticket_ref * (d["renda_pc__carro_10"].fillna(renda_ref).to_numpy(float) / renda_ref) ** pr["elast_ticket"]
    if cresc:
        F = F * (1 + pr["peso_cres_mun"] * cres_mun_z)
    return F


def rodar(d, y, ticket_ref, teto, cresc, grupo="rede"):
    renda_ref = float(np.nanmedian(d["renda_pc__carro_10"]))
    z = lambda s: ((s - s.median()) / s.std()).fillna(0).clip(-2, 2).to_numpy()
    czh, czm = z(d["cres_hex_taxa"]), z(d["dim_media"])
    rng = np.random.default_rng(42)  # mesmos sorteios nas 4 variantes
    apr = np.zeros((N, len(d))); esp = np.zeros((N, len(d))); g = d[grupo].to_numpy()
    for i in range(N):
        pr = {k: rng.uniform(*v) for k, v in FAIXAS.items()}; w = rng.dirichlet([1, 1, 1])
        e = esperado(d, pr, w, renda_ref, czh, czm, ticket_ref, teto, cresc); esp[i] = e; a = y / e
        for gg in np.unique(g):
            m = g == gg; a[m] /= np.median(a[m])
        apr[i] = a
    return apr, esp


def boot_rho(x, y, B=2000):
    rs = []
    for _ in range(B):
        i = RNG.integers(0, len(x), len(x)); rs.append(spearmanr(x[i], y[i])[0])
    return np.percentile(rs, 2.5), np.percentile(rs, 97.5)


def main():
    ac, tree = v2.oferta()
    fech = pd.read_parquet(v2.SC / "fech_mensal_financeiro.parquet")
    fin = fech[fech.origem_faturamento.eq("financeiro") & fech.mes_completo & fech.operacao_mes_cheio]
    fat_ago = fin[fin.competencia == "2026-08"].set_index("unidade_id")["faturamento"].copy(); fat_ago.loc["guaruja-sp"] = 217525.74
    fat_12 = fin[fin.competencia.between("2025-09", "2026-08")].groupby("unidade_id")["faturamento"].median()
    ativos_12 = fech[fech.competencia.between("2025-09", "2026-08")].groupby("unidade_id")["ativos"].median()
    bu = pd.read_parquet(ISO / "testes_v2" / "base_ultra.parquet").rename(columns={"unidade_id": "pid"})
    bu["rede"] = "ultra"; bu["fat_fin_ago"] = bu.pid.map(fat_ago); bu["fat_fin_12m"] = bu.pid.map(fat_12); bu["ativos_ref"] = bu.pid.map(ativos_12)
    ultra_ref = bu.dropna(subset=["lat"])[["pid", "lat", "lng", "ativos_ref"]]
    iso = pd.concat([pd.read_parquet(f, columns=["ponto_id", "tipo", "modo", "limite_s", "poligono_wkb"], filters=[("tipo", "==", "ultra")]) for f in sorted((ISO / "isocronas_v2").glob("metro_*.parquet"))])
    polys = {}
    for c, (modo, lim) in v2.CEN.items():
        s = iso[(iso.modo == modo) & (iso.limite_s == lim) & iso.poligono_wkb.notna()]
        polys[c] = dict(zip(s.ponto_id, gpd.GeoSeries([wkb.loads(b) for b in s.poligono_wkb], crs=4326).to_crs(5880).values))
    A = bu[bu.metragem.notna() & bu.fat_fin_ago.notna() & ~bu.confianca.eq("baixa") & bu["pop__carro_10"].notna()].reset_index(drop=True)
    A = v2.crescimento(v2.componentes(A, polys, ac, tree, ultra_ref, auto_m=2.0))
    ticket = float(np.median(A.fat_fin_ago / A.ativos_ref))
    y = A.fat_fin_ago.to_numpy(float)
    MD.append(f"# Aproveitamento v3 — interação metragem x concorrência e crescimento na conta\n\nUltra, faturamento do Financeiro de agosto/2026 (Guarujá corrigido). N = {len(A)}.\n")
    linhas, res = [], {}
    for nome, teto, cresc in (("v2 (sem teto, sem crescimento)", False, False), ("+ teto de capacidade", True, False), ("+ crescimento", False, True), ("v3: teto + crescimento", True, True)):
        apr, esp = rodar(A, y, ticket, teto, cresc)
        fe = np.median(esp, axis=0); ap = np.median(apr, axis=0)
        rho = spearmanr(fe, y)[0]; lo, hi = boot_rho(fe, y)
        rho_m2 = spearmanr(fe / A.metragem, y / A.metragem)[0]
        rs = [spearmanr(esp[i], y)[0] for i in range(0, N, 10)]
        fr = (apr > 1).mean(axis=0); robusto = int(((fr >= 0.8) | (fr <= 0.2)).sum())
        linhas.append({"variante": nome, "rho_esperado_x_real": rho, "ic95": f"[{lo:+.2f}; {hi:+.2f}]", "rho_por_m2": rho_m2,
                       "rho_sorteios_p10_p90": f"{np.percentile(rs,10):+.2f} a {np.percentile(rs,90):+.2f}", "unidades_leitura_robusta": robusto,
                       "aprov_x_cres_mun": spearmanr(A.dim_media, ap, nan_policy="omit")[0]})
        res[nome] = (apr, esp)
    MD.append(pd.DataFrame(linhas).round(3).to_markdown(index=False))
    # diferencas pareadas por bootstrap (mesmos pontos) contra v2
    fe0 = np.median(res["v2 (sem teto, sem crescimento)"][1], axis=0)
    for nome in list(res)[1:]:
        fe = np.median(res[nome][1], axis=0); ds = []
        for _ in range(2000):
            i = RNG.integers(0, len(y), len(y)); ds.append(spearmanr(fe[i], y[i])[0] - spearmanr(fe0[i], y[i])[0])
        MD.append(f"- ganho de aderência de '{nome}' sobre v2: {spearmanr(fe,y)[0]-spearmanr(fe0,y)[0]:+.3f} IC95 [{np.percentile(ds,2.5):+.3f}; {np.percentile(ds,97.5):+.3f}]")
    # 12 meses como checagem
    apr12, esp12 = rodar(A, A.fat_fin_12m.to_numpy(float), ticket, True, True)
    MD.append(f"\nChecagem com a mediana de 12 meses (v3): esperado x real rho {spearmanr(np.median(esp12,axis=0), A.fat_fin_12m)[0]:+.2f}; concordância do aproveitamento agosto x 12 m {spearmanr(np.median(res['v3: teto + crescimento'][0],axis=0), np.median(apr12,axis=0))[0]:+.2f}.")
    # sensibilidade das premissas novas
    apr, esp = res["v3: teto + crescimento"]
    r = v2.resumo(A, apr, esp, y)
    r = r.merge(A[["pid", "dim_media", "cres_hex_taxa"]], on="pid", how="left")
    r.to_csv(OUT / "ultra_v3_agosto.csv", sep=";", encoding="utf-8-sig", index=False)
    MD.append(f"\n## Leitura por unidade (v3)\n\n{r.leitura.value_counts().to_dict()}\n")
    MD.append(r[["pid", "metragem", "real", "esperado_mediana", "aprov_mediana", "aprov_p10", "aprov_p90", "frac_acima", "leitura"]].round(2).to_markdown(index=False))
    # quem mudou de leitura entre v2 e v3
    r0 = v2.resumo(A, *res["v2 (sem teto, sem crescimento)"], y)[["pid", "leitura", "aprov_mediana"]]
    mud = r0.merge(r[["pid", "leitura", "aprov_mediana"]], on="pid", suffixes=("_v2", "_v3"))
    mud = mud[mud.leitura_v2 != mud.leitura_v3]
    MD.append(f"\n**Mudaram de leitura entre v2 e v3 ({len(mud)}):**\n"); MD.append(mud.round(2).to_markdown(index=False))
    (OUT / "resultados.md").write_text("\n".join(MD), encoding="utf-8")
    print("\n".join(l for l in MD if l.count("|") < 12 or "variante" in l or "rho_esperado" in l))
    print(pd.DataFrame(linhas).round(3).to_string(index=False))
    print(mud.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
