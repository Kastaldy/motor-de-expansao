# -*- coding: utf-8 -*-
"""EXPLORATORIO (sem pre-registro; pedido do Felipe em 2026-09-29): quanto cada ajuste muda de verdade.
(1) mix: regra hibrida (SP e DF/GO pelo modelo; 'outros' no padrao da rede) x regra por estado, validacao cruzada.
(2) volume e faturamento: M0 + estado + escritorios juntos, treino 39 (2025) -> teste 18 (UNI-02).
(3) v2 + alavancas declaradas (preco real do Gold e politica de agregador, aritmetica do simulador; estudios; master)
    nas 18 unidades de teste: o erro cai?
Rodar com PYTHONPATH=src no .venv do projeto.
"""
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

AQUI = Path(__file__).resolve().parent
UNI = AQUI.parent


def mod(nome, p):
    s = importlib.util.spec_from_file_location(nome, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


_argv = sys.argv; sys.argv = [_argv[0], "alunos"]
mx = mod("mx", UNI / "mix" / "01_mix.py"); sys.argv = _argv
ex = mx.ex
c5 = mod("c5", UNI / "uni05" / "01_comparacao.py")
from motor_expansao.dimensionamento.config import SIM_ALUGUEL_MES  # noqa: E402
from motor_expansao.dimensionamento.simulador import Premissas  # noqa: E402

BASE = ["l_m2", "l_renda", "l_pop"]
L = ["# Quanto cada ajuste melhora de verdade (EXPLORATÓRIO, sem pré-registro)", ""]


def X_(D, cols):
    return np.column_stack([np.ones(len(D))] + [D[c].to_numpy(float) for c in cols])


# ---------------- (1) mix hibrido
f, d = ex.carregar()
A = mx.atributos(d)
Y = mx.desfecho(f, "2025-01", "2026-08", 6)
g = f[f.valido & f.competencia.between("2025-01", "2026-08") & (f.mv >= 6) & f.pct_agregador_ativos.notna()]
Y["mv_medio"] = g.groupby("unidade_id").mv.mean().reindex(Y.index)
D = A.join(Y, how="inner"); D = D[(D.aceita_wh + D.aceita_tp) >= 1].copy()
D["jovem"] = (D.mv_medio < 12).astype(float); D["so_um"] = ((D.aceita_wh + D.aceita_tp) == 1).astype(float)
grp = np.where(D.uf == "SP", "SP", np.where(D.uf.isin(["DF", "GO"]), "DFGO", "outros"))
D["g_SP"], D["g_outros"], D["grp"] = (grp == "SP").astype(float), (grp == "outros").astype(float), grp
D = D.dropna(subset=["mix", "l_renda", "l_pop"])
ctrl = ["l_renda", "l_pop", "jovem", "so_um"]
y = D.mix.to_numpy(float)
res = {"padrão da rede (média)": [], "por estado": [], "híbrida (SP e DF/GO pelo modelo; outros = padrão)": []}
for i in range(len(D)):
    tr, te = D.drop(D.index[i]), D.iloc[[i]]
    res["padrão da rede (média)"].append(tr.mix.mean())
    b = np.linalg.lstsq(X_(tr, ctrl + ["g_SP", "g_outros"]), tr.mix.to_numpy(float), rcond=None)[0]
    p_est = float(X_(te, ctrl + ["g_SP", "g_outros"]) @ b)
    res["por estado"].append(p_est)
    res["híbrida (SP e DF/GO pelo modelo; outros = padrão)"].append(tr.mix.mean() if te.grp.iloc[0] == "outros" else p_est)
L += ["## 1. Mix: fixar 'outros' no padrão", "", f"{len(D)} unidades, validação LOO (proporção de agregadores nos ativos, UX).", "",
      "| regra | erro médio (p.f.) | erro nas 'outros' | erro em SP e DF/GO | Spearman |", "|---|---|---|---|---|"]
ou = D.grp.to_numpy() == "outros"
for k, p in res.items():
    e = np.abs(y - np.array(p))
    L.append(f"| {k} | {100 * e.mean():.1f} | {100 * e[ou].mean():.1f} | {100 * e[~ou].mean():.1f} | {stats.spearmanr(p, y)[0]:+.2f} |")

# ---------------- (2) volume e faturamento: M0 + estado + escritorios (treino 39 -> teste 18)
A2 = ex.atributos(d)
A2["escritorios"] = pd.to_numeric(d.poi_F1, errors="coerce")
g2 = np.where(d.uf == "SP", "SP", np.where(d.uf.isin(["DF", "GO"]), "DFGO", "outros"))
A2["g_SP"], A2["g_outros"] = pd.Series((g2 == "SP").astype(float), index=d.index), pd.Series((g2 == "outros").astype(float), index=d.index)
Y25, Y26 = ex.desfechos(f, "2025-01", "2025-12"), ex.desfechos(f, "2026-01", "2026-08")
tr = A2.join(Y25, how="inner").dropna(subset=["l_fat"] + BASE + ["frac_indep"])
t2 = pd.read_csv(UNI / "uni02" / "confirmacao_por_unidade.csv", sep=";", encoding="utf-8-sig", index_col=0)
te = A2.drop(columns=["l_m2"]).join(np.log(t2.m2).rename("l_m2")).join(Y26, how="inner").loc[t2.index]
cal = float(np.median(Y26.loc[tr.index.intersection(Y26.index), "l_fat"] - Y25.loc[tr.index.intersection(Y26.index), "l_fat"]))
cal_a = float(np.median(Y26.loc[tr.index.intersection(Y26.index), "l_ativos"] - Y25.loc[tr.index.intersection(Y26.index), "l_ativos"]))
L += ["", "## 2. Renda + escritórios + estado juntos: volume (alunos) e faturamento", "",
      f"Treino: {len(tr)} maduras de 2025; teste: as {len(te)} unidades do UNI-02. Erro típico = mediana de |erro|.", "",
      "| modelo | faturamento: erro típico | Spearman | alunos (volume): erro típico | Spearman | R² LOO faturamento (treino) |", "|---|---|---|---|---|---|"]
modelos = {"M0 (m², renda, população)": BASE, "M0 + estado": BASE + ["g_SP", "g_outros"], "M0 + escritórios": BASE + ["escritorios"],
           "M0 + estado + escritórios": BASE + ["g_SP", "g_outros", "escritorios"]}
for nome, cols in modelos.items():
    trc, tec = tr.dropna(subset=cols), te.dropna(subset=cols)
    lin = []
    for yv, cc in (("l_fat", cal), ("l_ativos", cal_a)):
        b = np.linalg.lstsq(X_(trc, cols), trc[yv].to_numpy(float), rcond=None)[0]
        p = X_(tec, cols) @ b + cc
        e = np.abs(np.exp(tec[yv].to_numpy(float) - p) - 1)
        lin += [f"{100 * np.median(e):.1f}%", f"{stats.spearmanr(p, tec[yv])[0]:+.2f}"]
    bb, ee, hh, _ = ex.ols(trc.l_fat.to_numpy(float), X_(trc, cols))
    L.append(f"| {nome} | " + " | ".join(lin) + f" | {ex.r2_loo(trc.l_fat.to_numpy(float), ee, hh):.3f} |")

# ---------------- (3) v2 + alavancas declaradas nas 18 unidades de teste
c = pd.read_csv(UNI / "uni05" / "comparacao_por_unidade.csv", sep=";", encoding="utf-8-sig")
c = c[c.grupo == "teste"].set_index("unidade_id")
preco = pd.to_numeric(d.cad_preco_gold, errors="coerce").reindex(c.index)
aceita = (d.wh_tem_agregador_cadastro.map({True: True, False: False}).fillna(True) | d.tp_tem_agregador_cadastro.map({True: True, False: False}).fillna(True)).reindex(c.index)
P0 = Premissas(ticket_cheio=137.0, share_balcao=0.69, aluguel_mes=float(SIM_ALUGUEL_MES))


def fat_ajustado(fat_v2, ticket, share):
    alunos = c5.alunos_de(fat_v2)  # demanda da v2 com o modelo de negocio padrao
    return Premissas(ticket_cheio=float(ticket), share_balcao=float(share), aluguel_mes=float(SIM_ALUGUEL_MES)).faturamento(alunos, com_anuidade=True)


real = c.fat_real
cen = {"v2 (só praça)": c.fat_V2,
       "v2 + preço declarado": pd.Series([fat_ajustado(v, preco.get(u, 137) if pd.notna(preco.get(u)) else 137, 0.69) for u, v in c.fat_V2.items()], index=c.index),
       "v2 + agregador declarado": pd.Series([fat_ajustado(v, 137, 0.69 if aceita[u] else 1.0) for u, v in c.fat_V2.items()], index=c.index),
       "v2 + preço + agregador": pd.Series([fat_ajustado(v, preco.get(u, 137) if pd.notna(preco.get(u)) else 137, 0.69 if aceita[u] else 1.0) for u, v in c.fat_V2.items()], index=c.index)}
L += ["", "## 3. A v2 com as alavancas declaradas pelo operador (18 unidades de teste)", "",
      "Aritmética do simulador: mesmos alunos da v2, com o preço do Gold do cadastro e a política de agregador (Botafogo é a única que não aceita).", "",
      "| cenário | erro típico | viés (mediana) | Spearman | Botafogo: previsto → real |", "|---|---|---|---|---|"]
for k, p in cen.items():
    e = real / p - 1
    L.append(f"| {k} | {100 * e.abs().median():.1f}% | {100 * e.median():+.1f}% | {stats.spearmanr(p, real)[0]:+.2f} | R$ {p['botafogo-rj']:,.0f} → R$ {real['botafogo-rj']:,.0f} |")
L += ["", f"Preço do Gold nas 18: mediana R$ {preco.median():.0f} (de R$ {preco.min():.0f} a R$ {preco.max():.0f}); o simulador usa R$ 137.", ""]
(AQUI / "resultado_quanto_melhora.md").write_text("\n".join(L) + "\n", encoding="utf-8")
print("\n".join(L))
