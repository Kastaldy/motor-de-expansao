# -*- coding: utf-8 -*-
"""Exploratoria do BLK-UNI, lote 2 (06/10): (a) onde mora o erro da v2 (outliers x unidade tipica); (b) a mudanca de
estrategia do agregador apontada pelo Felipe (unidades passaram a inaugurar com o beneficio ativo; agregador ganhando
mercado); (c) series do painel que nunca entraram no estudo (etapa 1 do plano em uni09/plano_melhoria_duas_partes.md):
persistencia do balcao, captacao x retencao, receita por passagem e data do credenciamento; (d) painel de correlacoes
simples de todas as variaveis da unidade contra cada parte da receita.
So' descritivo. Mesmas fontes do lote 1; NADA da Base Consolidada nem de LOCAL_ vai para o OneDrive.
Uso: 02_outliers_estrategia_series.py  (.venv, PYTHONPATH=src)."""
import importlib.util
import sys
import types
from pathlib import Path

try:
    import h3  # noqa: F401
except ImportError:  # 06/10: o Controle de Aplicativo do Windows passou a bloquear a DLL do h3; este lote nao usa h3,
    for _k in [k for k in sys.modules if k == "h3" or k.startswith("h3.")]:  # so' a cadeia de imports o puxa
        del sys.modules[_k]
    sys.modules["h3"] = types.ModuleType("h3")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402

AQUI = Path(__file__).resolve().parent
UNI = AQUI.parent
OUT = Path(r"C:\Users\Felipe\OneDrive - Grupo Ultra\Área de Trabalho\Análises - Motor de Expansão\Exploratória BLK-UNI\02 - Outliers, estratégia e séries novas")
JAN, JAN_ANT = ("2026-03", "2026-08"), ("2025-03", "2025-08")
CORES_UF = {"DF": "#1f77b4", "GO": "#17becf", "SP": "#d62728", "RJ": "#2ca02c", "MG": "#9467bd", "PR": "#8c564b", "MT": "#e377c2",
            "ES": "#ff7f0e", "SC": "#bcbd22", "BA": "#7f7f7f", "PE": "#393b79", "RS": "#637939", "AM": "#843c39"}
plt.rcParams.update({"figure.dpi": 110, "savefig.dpi": 150, "font.size": 9, "axes.grid": True, "grid.alpha": .3})


BASE_ISO = {"iso_renda_pc": "renda per capita", "iso_pop": "população", "iso_dens_hab_km2": "densidade (hab/km²)", "iso_domicilios": "domicílios",
            "iso_area_km2": "área (km²)", "iso_km_rua": "km de rua", "iso_oferta_ponderada": "oferta de academias (rede 1, indep. 0,5)",
            "iso_n_academias": "nº de academias", "iso_n_cadeia_mapeada": "nº de academias de rede", "iso_n_independente_agregador": "nº de independentes no app",
            "iso_n_ultra": "nº de Ultras", "conc_cap_real": "alunos reais dos concorrentes", "conc_cap_rede": "capacidade dos concorrentes de rede",
            "conc_n_cadeia_proxy": "concorrentes de rede sem dado", "conc_n_indep": "nº de independentes", "conc_alunos_por_mil_hab": "alunos de concorrentes por mil hab.",
            "canib_frac_max": "canibalização (maior fração)", "canib_n_pares": "canibalização (nº de pares)"}
SUF_ISO = {"__carro_5": "carro 5 min", "__carro_10": "carro 10 min", "__pe_15": "a pé 15 min", "__circulo_1km": "círculo 1 km"}
APP = {"dist_ultra_m": "distância ao casamento da Ultra no app (alta = não listada)", "preco_ultra": "preço do plano da Ultra no app",
       "ord_ultra": "tier da Ultra no app (feed)", "ord_ultra_cadastro": "tier da Ultra no app (cadastro)", "n_conc_c10": "nº de concorrentes no app (carro 10)",
       "n_conc_com_preco_c10": "nº de concorrentes com preço no app (carro 10)", "ord_mediana_c10": "tier mediano dos concorrentes (carro 10)",
       "preco_mediana_c10": "preço mediano dos concorrentes (carro 10)", "pct_acima_ultra_c10": "% concorrentes com tier ACIMA da Ultra",
       "pct_mesmo_ultra_c10": "% concorrentes com tier IGUAL à Ultra", "pct_abaixo_ultra_c10": "% concorrentes com tier ABAIXO da Ultra",
       "gap_ord_c10": "tier da Ultra − mediana dos concorrentes"}
FIXO = {"tam_metragem_m2": "metragem oficial", "m2_combinada": "metragem (oficial ou satélite)", "tam_vagas": "vagas de estacionamento",
        "tam_vagas_por_1000m2": "vagas por 1.000 m²", "cad_preco_gold": "preço do plano Gold", "cad_mod_studios": "tem estúdio", "cad_mod_piscina": "tem piscina",
        "cad_mod_bike": "tem bike", "cad_mod_lutas": "tem lutas", "cad_mod_pilates": "tem pilates", "poi_em_shopping": "em shopping",
        "renda_dom_iso10": "renda domiciliar (carro 10)", "inauguracao_ano_frac": "data de inauguração (mais recente = maior)",
        "cres_dim_media": "crescimento do município (média)", "cres_dim_renda_pct": "crescimento do município: renda", "cres_dim_pop_pct": "crescimento do município: população",
        "cres_dim_empresas_por1k": "município: empresas por mil hab.", "cres_dim_emprego_pct": "crescimento do município: emprego",
        "cres_dim_predios_pct": "crescimento do município: prédios", "cres_hex_taxa": "crescimento do hexágono",
        "poi_F1": "escritórios por habitante (a pé 15)", "poi_F1_all": "empresas por habitante (a pé 15)", "poi_F1_c10": "escritórios por habitante (carro 10)",
        "poi_F2_c10": "varejo/serviços por habitante (carro 10)", "poi_F2": "varejo/serviços por habitante (a pé 15)",
        "poi_F5": "academias CNPJ fora do mapeado por mil hab.", "poi_n_f5": "nº de academias CNPJ fora do mapeado", "poi_n_mall": "nº de shoppings (a pé 15)",
        "poi_n_estacao": "nº de estações (a pé 15)", "poi_n_hiper": "nº de atacarejos (a pé 15)", "poi_edu_cnpj": "faculdades CNPJ (carro 10)", "poi_edu_osm": "faculdades OSM (carro 10)"}


def rotulo(v):
    if v in FIXO:
        return FIXO[v]
    for suf, r in SUF_ISO.items():
        if v.endswith(suf) and v[: -len(suf)] in BASE_ISO:
            return f"{BASE_ISO[v[: -len(suf)]]} — {r}"
    for pre, app in (("tp_", "TotalPass"), ("wh_", "Wellhub")):
        if v.startswith(pre) and v[3:] in APP:
            return f"{app}: {APP[v[3:]]}"
    return v


def mod(nome, p):
    s = importlib.util.spec_from_file_location(nome, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def cor(uf):
    return CORES_UF.get(uf, "#444444")


def salvar(fig, nome):
    fig.tight_layout(); fig.savefig(OUT / nome, bbox_inches="tight"); plt.close(fig)


def et(e):
    """Erro tipico: mediana de |real/previsto - 1|, com e = log real - log previsto."""
    return float(np.median(np.abs(np.exp(np.asarray(e, float)) - 1)))


def curto(u):
    for s in ("-df", "-sp", "-go", "-rj", "-mg", "-pr", "-mt", "-es", "-sc", "-ba", "-pe", "-rs", "-am"):
        u = u.replace(s, "")
    return u


def janela(f, ok, ini, fim, mv_min=12, min_meses=3, cols=("faturamento", "B", "WH", "TP", "AG", "pagantes", "ativos")):
    g = f[ok & (f.competencia >= ini) & (f.competencia <= fim) & (f.mv >= mv_min)]
    n = g.groupby("unidade_id").size(); g = g[g.unidade_id.isin(n[n >= min_meses].index)]
    U = g.groupby("unidade_id")[list(cols)].mean(); U["n_meses"] = n.reindex(U.index)
    return U


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tm = mod("tm", UNI / "termometro" / "01_termometro.py"); ex = tm.ex
    f, d = ex.carregar()
    tr, te, DUM, cal, A, dummies = tm.bases(f, d)
    d = d.drop(columns=[c for c in d.columns if c.startswith("tpd_")])      # derivado LOCAL_: nunca sai daqui
    f = f.copy()
    f["B"] = f.fin_vendas_ux - f.fin_tem_saude.fillna(0)
    f["WH"], f["TP"] = f.fin_gympass.fillna(0), f.fin_totalpass.fillna(0)
    f["AG"] = f.WH + f.TP
    ok = f.valido & f.fin_vendas_ux.notna()
    planilhas, notas = {}, []

    # ============ 1) onde mora o erro da v2
    V2 = ["l_m2", "l_renda_dom", "l_pop"] + DUM + ["studios"]
    y = tr.l_fat.to_numpy(float); X = tm.X_(tr, V2)
    b, e, hh, _ = ex.ols(y, X)
    e_tr = pd.Series(e / (1 - hh), index=tr.index)
    e_te = pd.Series(te.l_fat.to_numpy(float) - (tm.X_(te, V2) @ b + cal["l_fat"]), index=te.index)
    E = pd.concat([pd.DataFrame({"grupo": "maduras 2025 (LOO)", "e": e_tr}), pd.DataFrame({"grupo": "teste 2026", "e": e_te})])
    E["erro_pct"] = 100 * (np.exp(E.e) - 1); E["e2"] = E.e ** 2
    E["real_mil"] = np.exp(pd.concat([tr.l_fat, te.l_fat])) / 1e3; E["previsto_mil"] = E.real_mil / np.exp(E.e)
    E = E.sort_values("e2", ascending=False)
    E["pct_acum_erro_quadratico"] = 100 * E.e2.cumsum() / E.e2.sum()
    top5 = {gname: E[E.grupo == gname].index[:5] for gname in E.grupo.unique()}
    # refit sem os 5 maiores erros do treino: o resto das previsoes muda?
    keep = tr.index.difference(top5["maduras 2025 (LOO)"])
    trk = tr.loc[keep]; V2k = [c for c in V2 if c in ("l_m2", "l_renda_dom", "l_pop") or trk[c].std() > 0]
    bk, ek, hk, _ = ex.ols(trk.l_fat.to_numpy(float), tm.X_(trk, V2k))
    e_trk = pd.Series(ek / (1 - hk), index=keep)
    e_tek = pd.Series(te.l_fat.to_numpy(float) - (tm.X_(te, V2k) @ bk + cal["l_fat"]), index=te.index)
    R1 = pd.DataFrame([
        {"recorte": "maduras 2025 (LOO), todas as 39", "erro_tipico_pct": 100 * et(e_tr), "rmse_log": float(np.sqrt((e_tr ** 2).mean()))},
        {"recorte": "maduras 2025, sem os 5 maiores erros (mesmo modelo)", "erro_tipico_pct": 100 * et(e_tr.drop(top5["maduras 2025 (LOO)"])),
         "rmse_log": float(np.sqrt((e_tr.drop(top5["maduras 2025 (LOO)"]) ** 2).mean()))},
        {"recorte": "as mesmas 34, com o modelo REAJUSTADO sem os 5", "erro_tipico_pct": 100 * et(e_trk), "rmse_log": float(np.sqrt((e_trk ** 2).mean()))},
        {"recorte": "teste 2026, todas as 18", "erro_tipico_pct": 100 * et(e_te), "rmse_log": float(np.sqrt((e_te ** 2).mean()))},
        {"recorte": "teste 2026, sem os 5 maiores erros (mesmo modelo)", "erro_tipico_pct": 100 * et(e_te.drop(top5["teste 2026"])),
         "rmse_log": float(np.sqrt((e_te.drop(top5["teste 2026"]) ** 2).mean()))},
        {"recorte": "teste 2026, todas as 18, modelo reajustado sem os 5 do treino", "erro_tipico_pct": 100 * et(e_tek), "rmse_log": float(np.sqrt((e_tek ** 2).mean()))}])
    sh5 = {gname: float(E[E.grupo == gname].e2.nlargest(5).sum() / E[E.grupo == gname].e2.sum()) for gname in top5}
    fig, axs = plt.subplots(1, 2, figsize=(16, 7), gridspec_kw={"width_ratios": [1.5, 1]})
    Es = E.sort_values("erro_pct")
    cores = ["#4c72b0" if g_ == "maduras 2025 (LOO)" else "#c44e52" for g_ in Es.grupo]
    axs[0].barh(range(len(Es)), Es.erro_pct, color=cores)
    axs[0].set_yticks(range(len(Es))); axs[0].set_yticklabels(Es.index, fontsize=6)
    for v in (-25, 25):
        axs[0].axvline(v, color="k", ls=":", lw=.8)
    axs[0].axvline(0, color="k", lw=.8)
    axs[0].set_xlabel("erro = real / previsto − 1 (%)")
    axs[0].set_title("Erro da v2 unidade a unidade (azul: maduras 2025 sem a própria unidade; vermelho: teste 2026). Pontilhado = ±25%")
    for gname, c_ in (("maduras 2025 (LOO)", "#4c72b0"), ("teste 2026", "#c44e52")):
        s_ = E[E.grupo == gname].sort_values("e2", ascending=False)
        axs[1].plot(np.arange(1, len(s_) + 1), 100 * s_.e2.cumsum() / s_.e2.sum(), "-o", ms=3, color=c_, label=f"{gname}: 5 maiores = {100 * sh5[gname]:.0f}% do erro quadrático")
    axs[1].axvline(5, color="gray", ls=":")
    axs[1].set_xlabel("nº de unidades (da que mais erra para a que menos erra)"); axs[1].set_ylabel("% acumulado do erro quadrático")
    axs[1].set_title("Concentração: poucas unidades fazem a maior parte do erro QUADRÁTICO"); axs[1].legend(fontsize=7, loc="center right")
    txt = "\n".join(f"{r.recorte}: erro típico {r.erro_tipico_pct:.1f}%" for r in R1.itertuples())
    axs[1].text(0, -.13, "Erro típico (mediana) — o que muda sem os outliers:\n" + txt, transform=axs[1].transAxes, fontsize=7.5, va="top",
                bbox=dict(boxstyle="round", fc="white", alpha=.9))
    salvar(fig, "01_onde_mora_o_erro_v2.png")
    planilhas["01_erro_por_unidade"] = E.drop(columns=["e2"]).rename(columns={"e": "erro_log"})
    planilhas["01_erro_resumo"] = R1
    notas.append(f"01: 5 maiores = {100 * sh5['maduras 2025 (LOO)']:.0f}% (treino) e {100 * sh5['teste 2026']:.0f}% (teste) do erro quadrático; "
                 + "; ".join(f"{r.recorte} {r.erro_tipico_pct:.1f}%" for r in R1.itertuples()))

    # ============ 2) ficha dos outliers (leitura, nao teste)
    met = pd.read_csv(UNI / "coleta_metragem" / "metragem_estimada_2026-09-29.csv", sep=";", encoding="utf-8-sig", index_col=0).metragem_estimada_m2
    base = pd.concat([tr.assign(jan_ini="2025-01", jan_fim="2025-12"), te.assign(jan_ini="2026-01", jan_fim="2026-08")])
    F = pd.DataFrame(index=E.index)
    F["m2"] = np.exp(base.l_m2.reindex(F.index)); F["renda_dom"] = np.exp(base.l_renda_dom.reindex(F.index)); F["pop_iso10"] = np.exp(base.l_pop.reindex(F.index))
    pa = []
    for u in F.index:
        a_, z_ = base.loc[u, "jan_ini"], base.loc[u, "jan_fim"]
        g_ = f[ok & (f.unidade_id == u) & (f.competencia >= a_) & (f.competencia <= z_)]
        pa.append(g_.AG.sum() / (g_.B.sum() + g_.AG.sum()) if len(g_) else np.nan)
    F["pct_agregador"] = 100 * np.array(pa)
    F["dens_iso10"] = d.iso_dens_hab_km2__carro_10.reindex(F.index); F["academias_iso10"] = d.iso_n_academias__carro_10.reindex(F.index)
    F["preco_gold"] = d.cad_preco_gold.reindex(F.index); F["vagas"] = d.tam_vagas.reindex(F.index)
    num_cols = list(F.columns)
    F["erro_pct"] = E.erro_pct; F["grupo"] = E.grupo; F["uf"] = d.uf.reindex(F.index); F["master"] = A.master_id.reindex(F.index)
    F["estudio"] = base.studios.reindex(F.index); F["shopping"] = d.poi_em_shopping.reindex(F.index)
    F["inauguracao"] = d.inauguracao.reindex(F.index).astype(str).str[:7]
    F["m2_fonte"] = np.where(d.tam_metragem_m2.reindex(F.index).notna(), "oficial", np.where(met.reindex(F.index).notna(), "satélite", "?"))
    top = F.reindex(E.index[:16])
    pct = F[num_cols].rank(pct=True).reindex(top.index)
    fig, ax = plt.subplots(figsize=(14, 8.5))
    ax.imshow(pct.to_numpy(float), cmap="RdBu_r", vmin=0, vmax=1, aspect="auto")
    fmt = {"m2": "{:,.0f}", "renda_dom": "R$ {:,.0f}", "pop_iso10": "{:,.0f}", "pct_agregador": "{:.0f}%", "dens_iso10": "{:,.0f}",
           "academias_iso10": "{:.0f}", "preco_gold": "R$ {:.0f}", "vagas": "{:.0f}"}
    for i, u in enumerate(top.index):
        for j, c in enumerate(num_cols):
            v = top.loc[u, c]
            ax.text(j, i, "—" if pd.isna(v) else fmt[c].format(v).replace(",", "."), ha="center", va="center", fontsize=7)
    ax.set_xticks(range(len(num_cols)))
    ax.set_xticklabels(["metragem", "renda domiciliar\n(isócrona 10 min)", "população\n(isócrona 10 min)", "% agregador\nna receita",
                        "densidade\n(hab/km²)", "academias\nna isócrona", "preço Gold", "vagas"], fontsize=8)
    ax.set_yticks(range(len(top)))
    ax.set_yticklabels([f"{u} ({r.uf}, {r.master}{', estúdio' if r.estudio == 1 else ''}{', shopping' if r.shopping is True else ''}, m² {r.m2_fonte})  {r.erro_pct:+.0f}%"
                        for u, r in top.iterrows()], fontsize=7)
    for t_, g_ in zip(ax.get_yticklabels(), top.grupo):
        t_.set_color("#4c72b0" if g_ == "maduras 2025 (LOO)" else "#c44e52")
    ax.grid(False)
    ax.set_title("As 16 unidades que a v2 mais erra: cor = posição entre as 57 (azul = entre as menores, vermelho = entre as maiores). Número = valor real.\n"
                 "Azul no nome = maduras 2025; vermelho = teste 2026. Erro à direita (positivo = faturou acima do previsto).", fontsize=9)
    salvar(fig, "02_ficha_dos_outliers.png")
    planilhas["02_ficha_57_unidades"] = F

    # ============ 3) estrategia: inaugurar com agregador?
    ini = f[f.flag_inauguracao_placeholder.fillna(False).astype(bool) == False]  # noqa: E712
    ini = ini[ini.mes_vida.notna()]
    tem_m1 = ini[ini.mes_vida == 1].unidade_id.unique()
    C = []
    for u in tem_m1:
        g_ = ini[ini.unidade_id == u].sort_values("mes_vida")
        m13 = g_[g_.mes_vida.between(1, 3)]
        pas = g_[["mes_vida", "passagens_gympass", "passagens_totalpass"]]
        wh1 = pas[pas.passagens_gympass > 0].mes_vida.min(); tp1 = pas[pas.passagens_totalpass > 0].mes_vida.min()
        rec = m13.AG.sum() / (m13.B.sum() + m13.AG.sum()) if (m13.B.sum() + m13.AG.sum()) > 0 else np.nan
        C.append({"unidade_id": u, "inauguracao": str(g_.inauguracao_competencia.iloc[0]), "uf": g_.uf.iloc[0],
                  "wellhub_no_mes1": bool((g_[g_.mes_vida == 1].passagens_gympass > 0).any()),
                  "totalpass_no_mes1": bool((g_[g_.mes_vida == 1].passagens_totalpass > 0).any()),
                  "mes_vida_1o_wellhub": wh1, "mes_vida_1o_totalpass": tp1, "pct_agregador_receita_m1a3": rec,
                  "ultimo_mes_vida_observado": g_.mes_vida.max()})
    C = pd.DataFrame(C).set_index("unidade_id")
    C["algum_agregador_no_mes1"] = C.wellhub_no_mes1 | C.totalpass_no_mes1
    C["semestre"] = C.inauguracao.str[:4] + np.where(C.inauguracao.str[5:7].astype(int) <= 6, "-S1", "-S2")
    S = C.groupby("semestre").agg(unidades=("uf", "size"), pct_com_agregador_mes1=("algum_agregador_no_mes1", "mean"),
                                  pct_wellhub_mes1=("wellhub_no_mes1", "mean"), pct_totalpass_mes1=("totalpass_no_mes1", "mean"),
                                  pct_agregador_receita_m1a3_mediana=("pct_agregador_receita_m1a3", "median"))
    S_sem_dfgo = C[~C.uf.isin(["DF", "GO"])].groupby("semestre").agg(unidades=("uf", "size"), pct_com_agregador_mes1=("algum_agregador_no_mes1", "mean"))
    fig, axs = plt.subplots(1, 3, figsize=(18, 5.2))
    xi = np.arange(len(S))
    axs[0].bar(xi - .27, 100 * S.pct_com_agregador_mes1, .27, label="algum agregador", color="#8172b2")
    axs[0].bar(xi, 100 * S.pct_wellhub_mes1, .27, label="Wellhub", color="#dd8452")
    axs[0].bar(xi + .27, 100 * S.pct_totalpass_mes1, .27, label="TotalPass", color="#55a868")
    axs[0].set_xticks(xi); axs[0].set_xticklabels([f"{s}\n(n {n})" for s, n in zip(S.index, S.unidades)], fontsize=7)
    axs[0].set_ylabel("% das unidades inauguradas no semestre"); axs[0].set_title("Inaugurou já com agregador? (passagem no 1º mês de vida)"); axs[0].legend(fontsize=7)
    axs[1].plot(xi, 100 * S.pct_agregador_receita_m1a3_mediana, "k-o")
    axs[1].set_xticks(xi); axs[1].set_xticklabels(S.index, fontsize=7, rotation=45)
    axs[1].set_ylabel("% da receita (mediana das unidades do semestre)"); axs[1].set_title("Peso do agregador nos 3 primeiros meses, por semestre de inauguração")
    for nome_, col_, c_ in (("Wellhub", "mes_vida_1o_wellhub", "#dd8452"), ("TotalPass", "mes_vida_1o_totalpass", "#55a868")):
        xx = pd.to_datetime(C.inauguracao + "-01"); yy = C[col_]
        axs[2].scatter(xx[yy.notna()], yy[yy.notna()], s=22, color=c_, alpha=.75, label=f"{nome_} (mês de vida da 1ª passagem)")
        sem = yy.isna()
        axs[2].scatter(xx[sem], np.full(sem.sum(), -2 if nome_ == "Wellhub" else -4), marker="x", s=22, color=c_, label=f"{nome_}: nunca teve passagem")
    axs[2].axhline(1, color="k", lw=.6, ls=":"); axs[2].set_ylabel("mês de vida em que começou"); axs[2].set_xlabel("data de inauguração")
    axs[2].set_title("Quando cada unidade entrou no agregador (abaixo de 0 = nunca entrou)"); axs[2].legend(fontsize=6.5)
    salvar(fig, "03_estrategia_inaugurar_com_agregador.png")
    planilhas["03_por_semestre"] = S; planilhas["03_sem_DF_GO"] = S_sem_dfgo; planilhas["03_por_unidade"] = C
    notas.append("03: % com algum agregador no mês 1 por semestre: " + ", ".join(f"{s} {100 * v:.0f}% (n {n})" for s, v, n in zip(S.index, S.pct_com_agregador_mes1, S.unidades)))

    # ============ 4) a MESMA unidade ao longo do tempo (painel balanceado)
    meses = sorted(f[(f.competencia >= "2025-01") & (f.competencia <= "2026-08")].competencia.unique())
    h = f[ok & f.competencia.isin(meses) & (f.mv >= 12)]
    cnt = h.groupby("unidade_id").size(); bal = cnt[cnt == len(meses)].index
    hb = h[h.unidade_id.isin(bal)].copy()
    hb["pass_ag"] = hb.passagens_gympass + hb.passagens_totalpass; hb["alunos_ag"] = hb.alunos_gympass + hb.alunos_totalpass
    hb["pct_ag"] = hb.AG / (hb.B + hb.AG)
    P = hb.groupby("competencia").agg(balcao_mil=("B", "median"), agregador_mil=("AG", "median"), faturamento_mil=("faturamento", "median"),
                                      pct_agregador=("pct_ag", "median"), pagantes=("pagantes", "median"), alunos_agregador=("alunos_ag", "median"),
                                      passagens_agregador=("pass_ag", "median"))
    for c in ("balcao_mil", "agregador_mil", "faturamento_mil"):
        P[c] = P[c] / 1e3
    yoy = []
    for m in meses:
        if m >= "2026-01":
            m0 = f"{int(m[:4]) - 1}{m[4:]}"
            a_ = hb[hb.competencia == m0].set_index("unidade_id"); z_ = hb[hb.competencia == m].set_index("unidade_id")
            yoy.append({"competencia": m, "balcao_var_mediana_pct": 100 * (np.exp(np.log(z_.B / a_.B).median()) - 1),
                        "agregador_var_mediana_pct": 100 * (np.exp(np.log(z_.AG / a_.AG).replace([np.inf, -np.inf], np.nan).median()) - 1),
                        "faturamento_var_mediana_pct": 100 * (np.exp(np.log(z_.faturamento / a_.faturamento).median()) - 1),
                        "pagantes_var_mediana_pct": 100 * (np.exp(np.log(z_.pagantes / a_.pagantes).median()) - 1),
                        "alunos_agregador_var_mediana_pct": 100 * (np.exp(np.log(z_.alunos_ag / a_.alunos_ag).replace([np.inf, -np.inf], np.nan).median()) - 1)})
    YOY = pd.DataFrame(yoy).set_index("competencia")
    fig, axs = plt.subplots(1, 3, figsize=(18, 5))
    ix = np.arange(len(P))
    axs[0].plot(ix, P.balcao_mil, "-o", ms=3, color="#4c72b0", label="balcão"); axs[0].plot(ix, P.agregador_mil, "-o", ms=3, color="#dd8452", label="agregador")
    axs[0].plot(ix, P.faturamento_mil, "-o", ms=3, color="k", label="faturamento")
    axs[0].set_xticks(ix[::2]); axs[0].set_xticklabels(P.index[::2], rotation=45); axs[0].set_ylabel("R$ mil/mês (mediana)")
    axs[0].set_title(f"As MESMAS {len(bal)} unidades, maduras em todos os meses de jan/25 a ago/26"); axs[0].legend(fontsize=7)
    axs[1].plot(ix, P.pagantes, "-o", ms=3, color="#4c72b0", label="pagantes (balcão)"); axs[1].plot(ix, P.alunos_agregador, "-o", ms=3, color="#dd8452", label="alunos de agregador")
    axs[1].set_xticks(ix[::2]); axs[1].set_xticklabels(P.index[::2], rotation=45); axs[1].set_ylabel("alunos (mediana)"); axs[1].legend(fontsize=7)
    axs[1].set_title("Volume: balcão × agregador nas mesmas unidades")
    iy = np.arange(len(YOY)); w = .2
    for k_, (col_, c_, rot) in enumerate((("balcao_var_mediana_pct", "#4c72b0", "balcão R$"), ("agregador_var_mediana_pct", "#dd8452", "agregador R$"),
                                          ("pagantes_var_mediana_pct", "#8da0cb", "pagantes"), ("alunos_agregador_var_mediana_pct", "#fc8d62", "alunos de agregador"))):
        axs[2].bar(iy + (k_ - 1.5) * w, YOY[col_], w, color=c_, label=rot)
    axs[2].axhline(0, color="k", lw=.8); axs[2].set_xticks(iy); axs[2].set_xticklabels(YOY.index, rotation=45)
    axs[2].set_ylabel("variação contra o mesmo mês de 2025 (mediana das unidades, %)"); axs[2].legend(fontsize=7)
    axs[2].set_title("2026 contra 2025, mesma unidade e mesmo mês (tira a sazonalidade)")
    salvar(fig, "04_mesmas_unidades_ao_longo_do_tempo.png")
    planilhas["04_painel_mensal"] = P; planilhas["04_2026_vs_2025"] = YOY
    notas.append(f"04: {len(bal)} unidades balanceadas; variação mediana 2026 x 2025: " + ", ".join(f"{c} {YOY[c].median():+.1f}%" for c in YOY.columns))

    # ============ 5) troca balcao x agregador na mesma unidade (mar-ago 2025 -> mar-ago 2026)
    U0 = janela(f, ok, *JAN_ANT); U1 = janela(f, ok, *JAN)
    amb = U0.index.intersection(U1.index)
    D5 = pd.DataFrame({"dl_balcao": np.log(U1.B / U0.B).reindex(amb), "dl_agregador": np.log(U1.AG / U0.AG).reindex(amb).replace([np.inf, -np.inf], np.nan),
                       "dl_faturamento": np.log(U1.faturamento / U0.faturamento).reindex(amb), "pct_ag_2025": (U0.AG / (U0.B + U0.AG)).reindex(amb),
                       "pct_ag_2026": (U1.AG / (U1.B + U1.AG)).reindex(amb), "uf": d.uf.reindex(amb)})
    s5 = D5.dropna(subset=["dl_balcao", "dl_agregador"])
    fig, axs = plt.subplots(1, 2, figsize=(14, 6))
    axs[0].scatter(100 * (np.exp(s5.dl_agregador) - 1), 100 * (np.exp(s5.dl_balcao) - 1), c=[cor(u) for u in s5.uf], s=35, edgecolor="k", lw=.3)
    for u, x_, y_ in zip(s5.index, 100 * (np.exp(s5.dl_agregador) - 1), 100 * (np.exp(s5.dl_balcao) - 1)):
        axs[0].annotate(curto(u)[:16], (x_, y_), fontsize=6, alpha=.7, xytext=(2, 2), textcoords="offset points")
    r_all = stats.spearmanr(s5.dl_agregador, s5.dl_balcao)[0]; ss = s5[~s5.uf.isin(["DF", "GO"])]
    r_sem = stats.spearmanr(ss.dl_agregador, ss.dl_balcao)[0]
    axs[0].axhline(0, color="k", lw=.7); axs[0].axvline(0, color="k", lw=.7)
    axs[0].set_xlabel("variação do agregador (R$, mar–ago 2026 contra mar–ago 2025, %)"); axs[0].set_ylabel("variação do balcão (R$, %)")
    axs[0].set_title(f"Quem ganhou agregador perdeu balcão? Spearman {r_all:+.2f} (sem DF+GO {r_sem:+.2f}); n {len(s5)}")
    axs[1].hist(100 * (np.exp(D5.dl_faturamento.dropna()) - 1), bins=20, color="gray", edgecolor="k")
    axs[1].axvline(100 * (np.exp(D5.dl_faturamento.median()) - 1), color="r", label=f"mediana {100 * (np.exp(D5.dl_faturamento.median()) - 1):+.1f}%")
    axs[1].set_xlabel("variação do faturamento total (%)"); axs[1].set_ylabel("unidades"); axs[1].legend()
    axs[1].set_title("E o faturamento total da mesma unidade, no mesmo período?")
    fig.legend(handles=[plt.Line2D([], [], marker="o", ls="", color=c, label=u) for u, c in CORES_UF.items() if u in set(s5.uf)], loc="upper center", ncol=12, fontsize=7, bbox_to_anchor=(.5, 1.04))
    salvar(fig, "05_troca_balcao_agregador_mesma_unidade.png")
    planilhas["05_variacao_por_unidade"] = D5
    notas.append(f"05: n {len(s5)}; Spearman Δagregador x Δbalcão {r_all:+.2f} (sem DF+GO {r_sem:+.2f}); Δfaturamento mediano {100 * (np.exp(D5.dl_faturamento.median()) - 1):+.1f}%")

    # ============ 6) persistencia: a abertura ja' diz o patamar?
    g6 = f[ok & f.mes_vida.notna()]
    early = g6[g6.mes_vida.between(1, 3)].groupby("unidade_id").agg(B_ini=("B", "mean"), AG_ini=("AG", "mean"), n_ini=("B", "size"))
    madu = g6[g6.mes_vida.between(12, 18)].groupby("unidade_id").agg(B_mad=("B", "mean"), AG_mad=("AG", "mean"), n_mad=("B", "size"))
    P6 = early[early.n_ini >= 2].join(madu[madu.n_mad >= 3], how="inner")
    P6["uf"] = d.uf.reindex(P6.index)
    fig, axs = plt.subplots(1, 2, figsize=(14, 6))
    res6 = {}
    for ax, (a_, z_, rot, c_) in zip(axs, (("B_ini", "B_mad", "Balcão", "#4c72b0"), ("AG_ini", "AG_mad", "Agregador", "#dd8452"))):
        s_ = P6[(P6[a_] > 0) & (P6[z_] > 0)]
        ax.scatter(s_[a_] / 1e3, s_[z_] / 1e3, c=[cor(u) for u in s_.uf], s=35, edgecolor="k", lw=.3)
        for u, x_, y_ in zip(s_.index, s_[a_] / 1e3, s_[z_] / 1e3):
            ax.annotate(curto(u)[:16], (x_, y_), fontsize=6, alpha=.7, xytext=(2, 2), textcoords="offset points")
        rho = stats.spearmanr(s_[a_], s_[z_])[0]; res6[rot] = (rho, len(s_), float(np.median(s_[z_] / s_[a_])))
        lo, hi = min(s_[a_].min(), s_[z_].min()) / 1e3, max(s_[a_].max(), s_[z_].max()) / 1e3
        ax.plot([lo, hi], [lo, hi], "k:", lw=.8)
        ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlabel(f"{rot}: média dos meses de vida 1–3 (R$ mil)"); ax.set_ylabel(f"{rot}: média dos meses de vida 12–18 (R$ mil)")
        ax.set_title(f"{rot}: a abertura já diz o patamar? Spearman {rho:+.2f} (n {len(s_)}); maduro = {res6[rot][2]:.2f}× a abertura (mediana)")
    salvar(fig, "06_persistencia_abertura_x_maduro.png")
    planilhas["06_persistencia"] = P6
    notas.append("06: " + "; ".join(f"{k} Spearman {v[0]:+.2f} n {v[1]} maduro/abertura {v[2]:.2f}x" for k, v in res6.items()))

    # ============ 7) captacao x retencao (maduras na janela)
    fl = janela(f, ok, *JAN, cols=("pagantes", "ativos", "novos_alunos", "vendas", "convertidos", "visitas", "cancelados", "B"))
    fl["taxa_saida_pagantes"] = fl.cancelados / fl.pagantes; fl["taxa_saida_ativos"] = fl.cancelados / fl.ativos
    fl["uf"] = d.uf.reindex(fl.index)
    # qual entrada fecha a conta do estoque? delta pagantes/ativos x (entrada - cancelados), mes a mes
    q = f[ok & (f.mv >= 12)].sort_values(["unidade_id", "competencia"]).copy()
    for c in ("pagantes", "ativos"):
        q[f"d_{c}"] = q.groupby("unidade_id")[c].diff()
    idn = []
    for est in ("pagantes", "ativos"):
        for ent in ("novos_alunos", "vendas", "convertidos"):
            z = q[[f"d_{est}", ent, "cancelados"]].dropna()
            idn.append({"estoque": est, "entrada": ent, "corr_delta_x_entrada_menos_cancelados": float(np.corrcoef(z[f"d_{est}"], z[ent] - z.cancelados)[0, 1]),
                        "n_meses": len(z)})
    IDN = pd.DataFrame(idn)
    lp = np.log(fl.pagantes); dec = {}
    for ent in ("novos_alunos", "vendas"):
        ln = np.log(fl[ent]); lc = np.log(fl.taxa_saida_pagantes)
        dec[ent] = {"parte_entrada": float(np.cov(lp, ln)[0, 1] / lp.var()), "parte_saida": float(np.cov(lp, -lc)[0, 1] / lp.var())}
    fig, axs = plt.subplots(1, 3, figsize=(18, 5.5))
    for ax, (xc, rot) in zip(axs[:2], (("novos_alunos", "novos alunos por mês"), ("taxa_saida_pagantes", "cancelados ÷ pagantes (por mês)"))):
        ax.scatter(fl[xc], fl.pagantes, c=[cor(u) for u in fl.uf], s=35, edgecolor="k", lw=.3)
        for u, x_, y_ in zip(fl.index, fl[xc], fl.pagantes):
            ax.annotate(curto(u)[:14], (x_, y_), fontsize=6, alpha=.7, xytext=(2, 2), textcoords="offset points")
        rho = stats.spearmanr(fl[xc], fl.pagantes)[0]
        ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlabel(rot); ax.set_ylabel("pagantes (balcão)"); ax.set_title(f"Pagantes × {rot}: Spearman {rho:+.2f} (n {len(fl)})")
    ks = list(dec)
    axs[2].bar(np.arange(len(ks)) - .2, [100 * dec[k]["parte_entrada"] for k in ks], .4, label="entrada (captação)", color="#4c72b0")
    axs[2].bar(np.arange(len(ks)) + .2, [100 * dec[k]["parte_saida"] for k in ks], .4, label="saída (retenção)", color="#c44e52")
    axs[2].set_xticks(range(len(ks))); axs[2].set_xticklabels([f"entrada = {k}" for k in ks]); axs[2].axhline(0, color="k", lw=.7)
    axs[2].set_ylabel("% da diferença de pagantes entre unidades"); axs[2].legend(fontsize=7)
    axs[2].set_title("O que separa unidade grande de pequena: captar mais ou perder menos?")
    salvar(fig, "07_captacao_x_retencao.png")
    planilhas["07_fluxos_por_unidade"] = fl; planilhas["07_qual_entrada_fecha_conta"] = IDN
    planilhas["07_decomposicao"] = pd.DataFrame(dec).T
    notas.append("07: decomposição " + "; ".join(f"{k}: entrada {100 * v['parte_entrada']:.0f}% saída {100 * v['parte_saida']:.0f}%" for k, v in dec.items())
                 + " | identidade " + "; ".join(f"{r.estoque}/{r.entrada} corr {r.corr_delta_x_entrada_menos_cancelados:+.2f}" for r in IDN.itertuples()))

    # ============ 8) receita por passagem (data as trocas de tier e o atraso do Financeiro)
    r8 = f[f.mes_completo.astype(bool) & f.fin_gympass.notna()].sort_values(["unidade_id", "competencia"]).copy()
    for fonte, fin, pas in (("wh", "fin_gympass", "passagens_gympass"), ("tp", "fin_totalpass", "passagens_totalpass")):
        r8[f"rpp_{fonte}_l0"] = (r8[fin] / r8[pas]).where((r8[fin] > 0) & (r8[pas] > 0))
        r8[f"rpp_{fonte}_l1"] = (r8[fin] / r8.groupby("unidade_id")[pas].shift(1)).where(r8[fin] > 0)
        r8.loc[~(r8[f"rpp_{fonte}_l1"] > 0), f"rpp_{fonte}_l1"] = np.nan
    vol = {}
    for c in ("rpp_wh_l0", "rpp_wh_l1", "rpp_tp_l0", "rpp_tp_l1"):
        lg = np.log(r8[c])
        vol[c] = float(r8.assign(z=lg.groupby(r8.unidade_id).diff().abs()).z.median())
    best = {fo: ("l0" if vol[f"rpp_{fo}_l0"] <= vol[f"rpp_{fo}_l1"] else "l1") for fo in ("wh", "tp")}
    fig, axs = plt.subplots(2, 2, figsize=(18, 12), gridspec_kw={"height_ratios": [1, 2.2]})
    for k_, (fo, rot) in enumerate((("wh", "Wellhub"), ("tp", "TotalPass"))):
        col = f"rpp_{fo}_{best[fo]}"
        Q = r8[r8.competencia >= "2023-01"].groupby("competencia")[col].describe()[["25%", "50%", "75%", "count"]]
        iq = np.arange(len(Q))
        axs[0, k_].plot(iq, Q["50%"], "k-o", ms=3); axs[0, k_].fill_between(iq, Q["25%"], Q["75%"], alpha=.2, color="gray")
        axs[0, k_].set_xticks(iq[::3]); axs[0, k_].set_xticklabels(Q.index[::3], rotation=45); axs[0, k_].set_ylabel("R$ por passagem")
        lag_txt = "mesmo mês" if best[fo] == "l0" else "passagens do mês anterior"
        axs[0, k_].set_title(f"{rot}: receita por passagem na rede (mediana e metade central). Alinhamento: {lag_txt} "
                             f"(variação mês a mês {vol[col]:.2f} contra {vol[f'rpp_{fo}_' + ('l1' if best[fo] == 'l0' else 'l0')]:.2f})", fontsize=8)
        H = r8[r8.competencia >= "2024-01"].pivot_table(index="unidade_id", columns="competencia", values=col)
        H = H[H.notna().sum(axis=1) >= 6]
        Hn = np.log(H.div(H.median(axis=1), axis=0))
        Hn = Hn.loc[H.notna().sum(axis=1).sort_values(ascending=False).index]
        im = axs[1, k_].imshow(Hn.to_numpy(float), cmap="RdBu_r", vmin=-.6, vmax=.6, aspect="auto", interpolation="nearest")
        axs[1, k_].set_yticks(range(len(Hn))); axs[1, k_].set_yticklabels([curto(u)[:18] for u in Hn.index], fontsize=5)
        axs[1, k_].set_xticks(range(0, Hn.shape[1], 3)); axs[1, k_].set_xticklabels(Hn.columns[::3], rotation=45, fontsize=7); axs[1, k_].grid(False)
        axs[1, k_].set_title(f"{rot}: cada unidade contra a própria mediana (vermelho = paga mais por passagem; troca de cor = degrau)", fontsize=8)
        fig.colorbar(im, ax=axs[1, k_], fraction=.03, label="log da razão")
        planilhas[f"08_{rot}_rpp_unidade_mes"] = H
        planilhas[f"08_{rot}_rpp_rede"] = Q
    salvar(fig, "08_receita_por_passagem.png")
    notas.append(f"08: alinhamento escolhido {best}; volatilidade {vol}")

    # ============ 9) painel de correlacoes simples (60 maduras, mar-ago/26)
    U = janela(f, ok, *JAN)
    m2 = d.tam_metragem_m2.combine_first(met).reindex(U.index)
    alvo = pd.DataFrame({"faturamento": np.log(U.faturamento), "balcão": np.log(U.B), "agregador": np.log(U.AG.where(U.AG > 0)),
                         "% agregador": U.AG / (U.B + U.AG), "faturamento/m²": np.log(U.faturamento / m2), "balcão/m²": np.log(U.B / m2),
                         "agregador/m²": np.log(U.AG.where(U.AG > 0) / m2)})
    excl = ("lat", "lng", "rampa", "lt_", "tpd_", "iso_truncada", "iso_snap", "cres_cod", "poi_frac")
    V = d.reindex(U.index)
    V = V[[c for c in V.select_dtypes("number").columns if not c.startswith(excl)]].copy()
    for c in ("cad_mod_piscina", "cad_mod_studios", "cad_mod_bike", "cad_mod_lutas", "cad_mod_pilates", "poi_em_shopping"):
        V[c] = d[c].reindex(U.index).map({True: 1.0, False: 0.0})
    V["m2_combinada"] = m2; V["renda_dom_iso10"] = np.exp(A.l_renda_dom.reindex(U.index))
    V["inauguracao_ano_frac"] = pd.to_datetime(d.inauguracao.reindex(U.index), errors="coerce").map(lambda t: t.year + t.month / 12 if pd.notna(t) else np.nan)
    V = V.drop(columns=[c for c in ("iso_metro",) if c in V.columns])      # id de regiao metropolitana, nao e' medida
    V = V.loc[:, V.notna().sum() >= 30]
    V = V.loc[:, V.nunique() >= 2]
    kept, dup = [], {}
    for c in V.columns:                                                       # tira duplicatas exatas (ex.: preco e ordinal do tier)
        par = next((k for k in kept if abs(V[[c, k]].dropna().corr(method="spearman").iloc[0, 1]) >= .999), None)
        if par is None:
            kept.append(c)
        else:
            dup[c] = par
    V = V[kept]
    rows = []
    dfgo = d.uf.reindex(U.index).isin(["DF", "GO"])
    for c in V.columns:
        r_ = {"variavel": c, "n": int(V[c].notna().sum())}
        for a_ in alvo.columns:
            z = pd.concat([V[c], alvo[a_]], axis=1).dropna()
            r_[a_] = stats.spearmanr(z.iloc[:, 0], z.iloc[:, 1])[0] if len(z) >= 15 else np.nan
            zs = z[~dfgo.reindex(z.index)]
            r_[f"{a_} (sem DF+GO)"] = stats.spearmanr(zs.iloc[:, 0], zs.iloc[:, 1])[0] if len(zs) >= 15 else np.nan
        rows.append(r_)
    CR = pd.DataFrame(rows).set_index("variavel")
    CR["max_abs"] = CR[list(alvo.columns)].abs().max(axis=1)
    CR = CR.sort_values("max_abs", ascending=False)
    crit = 1.96 / np.sqrt(len(U) - 1)
    show = CR.head(45)
    fig, ax = plt.subplots(figsize=(11, 15))
    im = ax.imshow(show[list(alvo.columns)].to_numpy(float), cmap="RdBu_r", vmin=-.7, vmax=.7, aspect="auto")
    for i in range(len(show)):
        for j, a_ in enumerate(alvo.columns):
            v = show.iloc[i][a_]
            if pd.notna(v):
                ax.text(j, i, f"{v:+.2f}", ha="center", va="center", fontsize=6.5, fontweight="bold" if abs(v) >= crit else "normal",
                        color="k" if abs(v) < .5 else "w")
    ax.set_xticks(range(len(alvo.columns))); ax.set_xticklabels(alvo.columns, rotation=30, ha="right")
    ax.set_yticks(range(len(show))); ax.set_yticklabels([f"{rotulo(v)} (n {n})" for v, n in zip(show.index, show.n)], fontsize=6.5); ax.grid(False)
    fig.colorbar(im, ax=ax, fraction=.03, label="correlação de Spearman")
    ax.set_title(f"As 45 variáveis com a maior correlação simples contra alguma parte da receita ({len(U)} maduras, mar–ago/2026).\n"
                 f"Negrito = |r| ≥ {crit:.2f} (acima do acaso com essa amostra). Simples: NÃO controla m², renda nem estado.", fontsize=9)
    salvar(fig, "09_painel_correlacoes.png")
    CR.insert(0, "nome", [rotulo(v) for v in CR.index])
    planilhas["09_correlacoes_todas"] = CR
    planilhas["09_duplicatas_retiradas"] = pd.DataFrame({"retirada": list(dup), "igual_a": list(dup.values())})

    # elasticidades do grafico 04 do lote 1 (para a pergunta "quanto maior melhor?")
    el = []
    U["renda_dom"] = np.exp(A.l_renda_dom.reindex(U.index)); U["pop"] = np.exp(A.l_pop.reindex(U.index)); U["m2"] = m2
    for parte in ("B", "AG"):
        for x in ("renda_dom", "pop", "m2"):
            s_ = U[(U[parte] > 0) & U[x].notna()]
            xx, yy = np.log(s_[x]), np.log(s_[parte]); bb = np.polyfit(xx, yy, 1)
            el.append({"parte": parte, "variavel": x, "elasticidade": bb[0], "corr": np.corrcoef(xx, yy)[0, 1], "r2": np.corrcoef(xx, yy)[0, 1] ** 2,
                       "efeito_de_dobrar_pct": 100 * (2 ** bb[0] - 1), "n": len(s_)})
    planilhas["09_elasticidades_lote1"] = pd.DataFrame(el)

    leia = pd.DataFrame({"campo": ["Fonte", "Balcão / agregador", "01–02", "03", "04–05", "06", "07", "08", "09", "Cuidado", "O que NÃO está aqui", "Gerado por"],
                         "descrição": [
                             "Painel do estudo BLK-UNI (Financeiro + Growth em fato_unidade_mes) e cadastro da VPS (dim_unidade).",
                             "Balcão = vendas_ux − tem_saude; agregador = gympass + totalpass (Financeiro).",
                             "Erro da v2: maduras 2025 com previsão sem a própria unidade (LOO) e teste 2026 (18). Erro típico = mediana de |real/previsto − 1|.",
                             "Inauguração com agregador = passagem (Growth) > 0 no 1º mês de vida; só unidades com o mês 1 observado e sem data placeholder.",
                             "Painel balanceado: só unidades maduras (≥ 12 meses) em TODOS os meses da janela; compara a mesma unidade consigo mesma.",
                             "Abertura = média dos meses de vida 1–3 (≥ 2); maduro = 12–18 (≥ 3). Mistura calendário.",
                             "Definições de novos_alunos/vendas/convertidos/cancelados da Growth NÃO confirmadas (aba 07_qual_entrada_fecha_conta testa qual fecha a conta do estoque).",
                             "Receita por passagem = Financeiro ÷ passagens (Growth); o alinhamento (mesmo mês ou mês anterior) é o de menor oscilação mês a mês.",
                             "Correlação simples de Spearman; com 60 unidades, |r| < 0,25 é indistinguível de acaso, e muitas variáveis só repetem renda/m².",
                             "Tudo aqui é exploratório. Variável escolhida por estes gráficos só vale como hipótese a validar fora da amostra (turma B / turma 2026).",
                             "Nada da Base Consolidada nem de arquivos LOCAL_ (pasta sincronizada com a nuvem).",
                             "data/analysis/uni/exploratoria/02_outliers_estrategia_series.py (repositório motor-de-expansao)."]})
    with pd.ExcelWriter(OUT / "numeros_dos_graficos.xlsx") as w:
        leia.to_excel(w, sheet_name="LEIA-ME", index=False)
        pd.DataFrame({"resumo": notas}).to_excel(w, sheet_name="RESUMO", index=False)
        for nome, df in planilhas.items():
            df.to_excel(w, sheet_name=nome[:31])
    for n_ in notas:
        print(n_)
    print(pd.DataFrame(el).round(2).to_string())
    print("top correlações:\n", CR.head(25)[list(alvo.columns) + ["n"]].round(2).to_string())
    print(f"ok: {len(list(OUT.glob('*.png')))} gráficos em {OUT}")


if __name__ == "__main__":
    main()
