# -*- coding: utf-8 -*-
"""Anatomia dos erros do modelo base (exploracao, dados ate dez/2025) — primeira analise do plano aprovado em 28/09.

Modelo base: log faturamento ~ log m2 + log renda c10 + log pop c10, nas maduras de 2025 (amostra primaria do UNI-01).
1. Erro fora da amostra (LOO) por unidade: real / previsto - 1.
2. Decomposicao EXATA: log fat = log alunos + log ticket e o mesmo regressor => erro LOO do faturamento = erro LOO de
   alunos + erro LOO de ticket (em log). Mostra se a unidade erra por volume ou por preco.
3. Correlacao do erro com uma lista de variaveis FIXADA ANTES de olhar (Spearman; exploratorio, sem correcao).
4. Ficha dos casos extremos e comparacao quartil de cima x quartil de baixo.
5. Sensibilidade: o mesmo na janela jan-set/2025 (antes do vale de receita de Brasilandia/Vila Guilherme).
"""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

AQUI = Path(__file__).resolve().parent
s_ = importlib.util.spec_from_file_location("ex", AQUI / "01_exploracao.py"); ex = importlib.util.module_from_spec(s_); s_.loader.exec_module(ex)

# lista fixada antes (nome legivel -> coluna do dim ou do desfecho)
CANDIDATAS = {
    "preço do plano Gold": "cad_preco_gold", "tier Wellhub (cadastro)": "wh_ord_ultra_cadastro",
    "tem TotalPass (cadastro)": "tp_tem_agregador_cadastro", "% agregador (2025)": "agr", "churn (2025)": "churn",
    "idade média (meses, 2025)": "idade", "fração de independentes c10": "frac_indep",
    "saturação (alunos conc./mil hab c10)": "conc_alunos_por_mil_hab__carro_10", "nº academias c10": "iso_n_academias__carro_10",
    "sobreposição com outra Ultra (c10)": "canib_frac_max__carro_10", "outras Ultras na isócrona c10": "iso_n_ultra__carro_10",
    "em shopping": "poi_em_shopping", "escritórios a pé (F1)": "poi_F1", "comércio a pé (F2)": "poi_F2",
    "densidade (hab/km² c10)": "iso_dens_hab_km2__carro_10", "população a pé 15 min": "iso_pop__pe_15",
    "renda a pé 15 min": "iso_renda_pc__pe_15", "crescimento do município": "cres_dim_media", "crescimento do hexágono": "cres_hex_taxa",
    "vagas por 1.000 m²": "tam_vagas_por_1000m2", "retenção EB 60d (Lifetime)": "lt_eb_retencao_60d",
    "metragem (m²)": "tam_metragem_m2",
}


def loo(D, y, xs):
    X = np.column_stack([np.ones(len(D))] + [D[c].to_numpy(float) for c in xs]); yy = D[y].to_numpy(float)
    XtXi = np.linalg.pinv(X.T @ X); b = XtXi @ X.T @ yy; e = yy - X @ b
    h = np.einsum("ij,jk,ik->i", X, XtXi, X)
    el = e / (1 - h)
    return pd.Series(el, index=D.index), 1 - np.sum(el ** 2) / np.sum((yy - yy.mean()) ** 2)


def rodar(f, d, A, ini, fim):
    Y = ex.desfechos(f, ini, fim)
    g = f[f.valido & (f.competencia >= ini) & (f.competencia <= fim) & (f.mv >= 12)]
    Y["idade"] = g.groupby("unidade_id").mv.mean()
    Y["fat_real"] = np.exp(Y.l_fat); Y["alunos_real"] = np.exp(Y.l_ativos); Y["ticket_real"] = np.exp(Y.l_ticket)
    D = A.join(Y, how="inner").dropna(subset=["l_fat", "l_m2", "l_renda", "l_pop"])
    out = {}
    for y in ("l_fat", "l_ativos", "l_ticket"):
        out[y], out["r2_" + y] = loo(D, y, ex.BASE)
    E = pd.DataFrame({"e_fat": out["l_fat"], "e_alunos": out["l_ativos"], "e_ticket": out["l_ticket"]})
    assert np.allclose(E.e_fat, E.e_alunos + E.e_ticket), "decomposicao nao fecha"
    return D.join(E), {k: v for k, v in out.items() if k.startswith("r2_")}


def main():
    f, d = ex.carregar()
    A = ex.atributos(d)
    D, r2 = rodar(f, d, A, ex.INI, ex.FIM)
    Db, _ = rodar(f, d, A, ex.INI, ex.FIM_B)
    ctx = d[["nome", "uf", "cidade_cadastro", "anomalia_conferir", "flag_erro_dado"] + [c for c in CANDIDATAS.values() if c in d.columns]]
    D = D.join(ctx[[c for c in ctx.columns if c not in D.columns]])
    D["erro_pct"] = np.exp(D.e_fat) - 1
    D["fat_prev"] = D.fat_real / np.exp(D.e_fat)
    D["rank_B"] = Db.e_fat.rank(ascending=False).reindex(D.index)
    D.round(4).to_csv(AQUI / "anatomia_erros.csv", sep=";", encoding="utf-8-sig")

    # correlacoes com a lista fixada
    cor = []
    for nome, c in CANDIDATAS.items():
        x = pd.to_numeric(D[c], errors="coerce") if c in D.columns else None
        if x is None or x.notna().sum() < 12 or x.nunique() < 2:
            continue
        rows = {"variável": nome, "N": int(x.notna().sum())}
        for e in ("e_fat", "e_alunos", "e_ticket"):
            r, p = stats.spearmanr(x, D[e], nan_policy="omit")
            rows[e], rows["p_" + e] = r, p
        cor.append(rows)
    C = pd.DataFrame(cor).sort_values("e_fat", key=lambda s: -s.abs())
    C.to_csv(AQUI / "anatomia_erros_correlacoes.csv", sep=";", encoding="utf-8-sig", index=False)

    # quartis
    q_hi, q_lo = D.e_fat.quantile(0.75), D.e_fat.quantile(0.25)
    top, bot = D[D.e_fat >= q_hi], D[D.e_fat <= q_lo]
    comp = []
    for nome, c in CANDIDATAS.items():
        if c in D.columns:
            x = pd.to_numeric(D[c], errors="coerce")
            comp.append((nome, x[top.index].median(), x.median(), x[bot.index].median()))
    uf_media = D.groupby("uf").erro_pct.agg(["size", "median"]).sort_values("size", ascending=False)

    pct = lambda v: "–" if pd.isna(v) else f"{100 * v:+.0f}%"
    num = lambda v: "–" if pd.isna(v) else (f"{v:,.0f}" if abs(v) >= 100 else f"{v:.2f}")
    L = ["# Anatomia dos erros do modelo base (maduras de 2025)", "",
         f"Modelo base: log faturamento ~ log m² + log renda c10 + log pop c10. N = {len(D)}. Erro = real / previsto − 1, fora da amostra (LOO).", "",
         f"- Quanto a base explica, fora da amostra: faturamento R² {r2['r2_l_fat']:.2f}; **alunos R² {r2['r2_l_ativos']:.2f}; ticket R² {r2['r2_l_ticket']:.2f}**.",
         f"- Erro típico (mediana do |erro|): {100 * (np.exp(D.e_fat.abs()) - 1).median():.0f}%. "
         f"Da variância do erro de faturamento, alunos respondem por {D.e_alunos.var() / D.e_fat.var():.0%} e ticket por {D.e_ticket.var() / D.e_fat.var():.0%} "
         f"(covariância {2 * np.cov(D.e_alunos, D.e_ticket)[0, 1] / D.e_fat.var():+.0%}).", "",
         "## Unidades com maior erro", "",
         "| unidade | UF | m² | fat. real | previsto | erro | por alunos | por ticket | Gold | % agreg. | churn | idade | rank jan–set |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    ext = pd.concat([D.sort_values("e_fat", ascending=False).head(7), D.sort_values("e_fat").head(7).iloc[::-1]])
    for u, r in ext.iterrows():
        L.append(f"| {r['nome']} | {r.uf} | {num(r.tam_metragem_m2)} | {num(r.fat_real)} | {num(r.fat_prev)} | **{pct(r.erro_pct)}** | "
                 f"{pct(np.exp(r.e_alunos) - 1)} | {pct(np.exp(r.e_ticket) - 1)} | {num(r.cad_preco_gold)} | {pct(r.agr).lstrip('+')} | {r.churn:.1f} | "
                 f"{r.idade:.0f} | {num(r.rank_B)} |")
        if isinstance(r.anomalia_conferir, str) or isinstance(r.flag_erro_dado, str):
            L[-1] = L[-1][:-1] + f" ⚠ {r.anomalia_conferir if isinstance(r.anomalia_conferir, str) else r.flag_erro_dado} |"
    L += ["", "(as 7 primeiras linhas faturam acima do previsto; as 7 últimas, abaixo. 'por alunos' e 'por ticket' somam o erro, em log.)", "",
          "## O erro anda junto com o quê? (Spearman; lista fixada antes; exploratório)", "",
          f"Com {len(C)} variáveis e N ≈ {len(D)}, espera-se ~{0.05 * len(C):.0f} correlação com p < 0,05 por acaso.", "",
          "| variável | N | erro do faturamento | erro de alunos | erro de ticket |", "|---|---|---|---|---|"]
    for _, r in C.iterrows():
        m = lambda e: f"{r[e]:+.2f}{'*' if r['p_' + e] < 0.05 else ''}"
        L.append(f"| {r['variável']} | {r.N} | {m('e_fat')} | {m('e_alunos')} | {m('e_ticket')} |")
    L += ["", "\\* p < 0,05 sem correção.", "", "## Quartil de cima × de baixo do erro (medianas)", "",
          "| variável | acima do previsto (quartil sup.) | todas | abaixo do previsto (quartil inf.) |", "|---|---|---|---|"]
    for nome, a, m_, b in comp:
        L.append(f"| {nome} | {num(a)} | {num(m_)} | {num(b)} |")
    L += ["", "## Erro por UF (mediana)", "", "| UF | N | erro mediano |", "|---|---|---|"] + [f"| {u} | {int(r['size'])} | {pct(r['median'])} |" for u, r in uf_media.iterrows()]
    (AQUI / "anatomia_erros.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
