# -*- coding: utf-8 -*-
"""BLK-UNI, 06/10: 'turma B' = unidades que estavam fora de todo modelo por falta de m2 e ganharam metragem APROXIMADA do
time de expansao (coleta_metragem/metragem_time_expansao_2026-10-06.csv). Etapa 3 do plano (uni09/plano_melhoria_duas_partes.md).
Revisado de forma adversarial antes de rodar (workflow wf_5bad03ed-9a5, 12 achados confirmados e aplicados).

Modos (um por vez, nesta ordem):
  --congelar : preve o faturamento maduro com a v2 TRAVADA (39 maduras de 2025, nivel 2026) para a metragem principal e as
               variantes declaradas; grava previsoes + REGISTRO com SHA-256. Recusa sobrescrever. Nao usa o desfecho dessas
               unidades (treino exige l_m2, que e' nulo para elas; calendario usa so' treino x 2026).
  --politica : abrir sem agregador x com agregador por m2 (lote 3 refeito), com e sem a metragem do time. Descritivo.
  --ler-v2   : SO' com decisao do Felipe (abrir o desfecho tira da turma B o papel de juiz cego das etapas 2-5 do plano).
Sem Base Consolidada nem LOCAL_ no OneDrive. Uso: 04_turma_b_metragem.py --congelar|--politica|--ler-v2  (.venv, PYTHONPATH=src)."""
import hashlib
import importlib.util
import sys
import types
from datetime import datetime
from pathlib import Path

try:
    import h3  # noqa: F401
except ImportError:  # 06/10: o Controle de Aplicativo do Windows bloqueia a DLL do h3; este script nao usa h3
    for _k in [k for k in sys.modules if k == "h3" or k.startswith("h3.")]:
        del sys.modules[_k]
    sys.modules["h3"] = types.ModuleType("h3")

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

AQUI = Path(__file__).resolve().parent
UNI = AQUI.parent
MET_TIME = UNI / "coleta_metragem" / "metragem_time_expansao_2026-10-06.csv"
MET_SAT = UNI / "coleta_metragem" / "metragem_estimada_2026-09-29.csv"
CURVA = UNI / "uni03" / "curva_uni03.csv"
DIR_PREV = UNI / "previsao_turma_b"
VERSAO = 1
PREV = DIR_PREV / f"previsoes_turma_b_v2_congel{VERSAO}.csv"
REG = DIR_PREV / f"REGISTRO_CONGELAMENTO_turma_b_congel{VERSAO}.txt"
OUT_BASE = Path(r"C:\Users\Felipe\OneDrive - Grupo Ultra\Área de Trabalho\Análises - Motor de Expansão\Exploratória BLK-UNI")
OUT_POL = OUT_BASE / "04 - Política sem agregador por m²"
OUT_V2 = OUT_BASE / "05 - Turma B (v2 congelada x real)"
JAN26 = ("2026-01", "2026-08")
# variantes de metragem declaradas ANTES de qualquer leitura (achado grave da revisao): principal = numero do time
VARIANTES = {"boa-vista-ba": {"vini_bruto_960": 960.0, "vini_regra_satelite_857": 960.0 / 1.12},   # planilha_vini_2026-09-29: telhado 480 x 2 pav.
             "ceilandia-qnm33-df": {"faixa_min_1700": 1700.0, "faixa_max_1800": 1800.0}}
MADURAS_ESPERADAS = ["boa-vista-ba", "ceilandia-qnm33-df", "bangu-rj"]      # unicas que podem ter >= 3 meses com mes de vida >= 12 em jan-ago/26
EXPOSICAO = [
    "boa-vista-ba: amostra_uni01.csv (l_fat de 2025) e resultados que a citam; lote 1 (receita media mar-ago/26 por unidade); lote 2/06 (abertura x maduro).",
    "ceilandia-qnm33-df, bangu-rj: lote 1 (receita media mar-ago/26 por unidade); lote 2/06 (abertura x maduro, rotulado).",
    "bangu, picarras, flow, visconde-de-rio-claro, vicente-pires-rua-8, boqueirao: lote 3/02 (faturamento nos meses de vida 3, 6 e 12, rotulado).",
    "Escolhas feitas DEPOIS dessas exposicoes: ponto medio da QNM33, mapeamento dos nomes do relato, mezanino nao tratado (sem a area dele),",
    "uso da v2 e da regra de leitura do UNI-02. Por isso: conferencia com EXPOSICAO PARCIAL, nao teste cego."]
plt.rcParams.update({"figure.dpi": 110, "savefig.dpi": 150, "font.size": 9, "axes.grid": True, "grid.alpha": .3})


def mod(nome, p):
    s = importlib.util.spec_from_file_location(nome, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def et(e):
    return float(np.median(np.abs(np.exp(np.asarray(e, float)) - 1)))


def salvar(fig, out, nome):
    fig.tight_layout(); fig.savefig(out / nome, bbox_inches="tight"); plt.close(fig)


def insumos():
    return {"metragem_time": MET_TIME, "metragem_satelite": MET_SAT, "curva_uni03": CURVA, "fato_unidade_mes": UNI / "fato_unidade_mes.parquet",
            "dim_unidade": UNI / "dim_unidade.parquet", "master_id_cadastro": UNI / "alavancas" / "master_id_cadastro.csv",
            "confirmacao_uni02": UNI / "uni02" / "confirmacao_por_unidade.csv", "mod_termometro": UNI / "termometro" / "01_termometro.py",
            "mod_evidencias": UNI / "manaus_volume" / "02_evidencias.py", "mod_alavancas": UNI / "alavancas" / "01_alavancas.py",
            "mod_incerteza": UNI / "uni07" / "01_incerteza.py", "mod_exploracao": UNI / "uni01" / "01_exploracao.py",
            "mod_lote3": AQUI / "03_politica_sem_agregador.py", "script": Path(__file__)}


def modelo():
    tm = mod("tm", UNI / "termometro" / "01_termometro.py"); ex = tm.ex
    f, d = ex.carregar()
    tr, te, DUM, cal, A, dummies = tm.bases(f, d)
    assert len(tr) == 39 and len(te) == 18 and "mr_M3" in DUM, (len(tr), len(te), DUM)
    V2 = ["l_m2", "l_renda_dom", "l_pop"] + DUM + ["studios"]
    y = tr.l_fat.to_numpy(float)
    b, e, hh, _ = ex.ols(y, tm.X_(tr, V2))
    loo = e / (1 - hh)
    r2 = float(ex.r2_loo(y, e, hh))
    e_te = te.l_fat.to_numpy(float) - (tm.X_(te, V2) @ b + cal["l_fat"])
    assert abs(r2 - 0.264) <= 0.005 and abs(et(e_te) - 0.221) <= 0.003, (r2, et(e_te))     # mesma v2 do teste (01_termometro.py:215)
    return dict(tm=tm, ex=ex, f=f, d=d, tr=tr, te=te, DUM=DUM, cal=cal, A=A, dummies=dummies, V2=V2, b=b, loo=loo, r2=r2, et_te=et(e_te))


def congelar():
    if PREV.exists() or REG.exists():
        sys.exit(f"RECUSADO: {PREV.name} ou {REG.name} ja existe. Congelamento novo = VERSAO nova, antes de qualquer leitura.")
    M = modelo(); tm, d, tr, te, A, V2, b, loo, cal = M["tm"], M["d"], M["tr"], M["te"], M["A"], M["V2"], M["b"], M["loo"], M["cal"]
    mt = pd.read_csv(MET_TIME, sep=";", encoding="utf-8").set_index("unidade_id")
    assert mt.index.isin(d.index).all(), set(mt.index) - set(d.index)
    assert not mt.index.isin(tr.index).any() and not mt.index.isin(te.index).any(), "turma B nao pode estar no treino nem no teste"
    assert d.loc[mt.index, "tam_metragem_m2"].isna().all(), "alguma da turma B ja tem metragem oficial"
    base = A.reindex(mt.index).drop(columns=["l_m2"], errors="ignore")
    fora = base[base[["l_renda_dom", "l_pop", "studios", "master_id"]].isna().any(axis=1)].index
    linhas = [(u, "principal_time", float(mt.loc[u, "metragem_m2"])) for u in mt.index if u not in fora]
    linhas += [(u, v, m2) for u, vs in VARIANTES.items() if u not in fora for v, m2 in vs.items()]
    B = M["dummies"](base.loc[[u for u, _, _ in linhas]].copy())
    B["variante"] = [v for _, v, _ in linhas]; B["metragem_m2"] = [m for _, _, m in linhas]
    B["l_m2"] = np.log(B.metragem_m2)
    l_prev = tm.X_(B, V2) @ b + cal["l_fat"]
    q10, q90 = np.quantile(loo, [.1, .9])
    cad = d.reindex(B.index)
    P = pd.DataFrame({"variante": B.variante, "metragem_m2": B.metragem_m2, "metragem_obs": mt.observacao.reindex(B.index).fillna("").to_numpy(),
                      "renda_dom": np.exp(B.l_renda_dom), "pop_iso10": np.exp(B.l_pop), "studios": B.studios, "master_id": B.master_id,
                      "l_prev_fat_2026": l_prev, "prev_fat_2026": np.exp(l_prev), "faixa80_nominal_lo": np.exp(l_prev + q10),
                      "faixa80_nominal_hi": np.exp(l_prev + q90),
                      "aceita_wellhub_cadastro": cad.wh_tem_agregador_cadastro.to_numpy(), "aceita_totalpass_cadastro": cad.tp_tem_agregador_cadastro.to_numpy(),
                      "confianca_coord": cad.confianca_coord.to_numpy(), "origem_coord": cad.origem_coord.to_numpy(),
                      "iso_truncada_c10": cad.iso_truncada__carro_10.to_numpy(), "iso_area_km2_c10": cad.iso_area_km2__carro_10.to_numpy(),
                      "em_shopping": cad.poi_em_shopping.to_numpy()}, index=B.index)
    for c, rot in (("l_m2", "m2"), ("l_renda_dom", "renda"), ("l_pop", "pop")):
        lo, hi = tr[c].min(), tr[c].max()
        P[f"fora_faixa_treino_{rot}"] = np.where(B[c] < lo, "abaixo", np.where(B[c] > hi, "acima", ""))
    P.index.name = "unidade_id"
    DIR_PREV.mkdir(exist_ok=True)
    P.to_csv(PREV, sep=";", encoding="utf-8-sig", float_format="%.6f")
    cand = UNI.parent.parent.parent / "tasks"  # so' para lembrar onde ancorar o SHA
    txt = [f"REGISTRO DE CONGELAMENTO — turma B, congelamento {VERSAO} (v2 travada) — {datetime.now():%Y-%m-%d %H:%M}", "",
           f"previsoes: {PREV.name}  SHA-256 {sha(PREV)}", ""] + [f"insumo {k}: {Path(p).name}  SHA-256 {sha(p)}" for k, p in insumos().items()] + [
           "", f"modelo: v2 = log fat ~ {' + '.join(V2)}; OLS nas {len(tr)} maduras de 2025 (teste com {len(te)}); nivel 2026 = + cal['l_fat'] = {cal['l_fat']:+.6f}",
           f"proveniencia: R2 LOO {M['r2']:.4f} (esperado 0,264); erro tipico nas 18 do teste {100 * M['et_te']:.2f}% (esperado 22,1%)",
           f"coeficientes: {dict(zip(['const'] + V2, np.round(b, 6)))}",
           f"faixa de 80% NOMINAL: quantis 10/90 dos erros LOO do treino ({q10:+.4f}, {q90:+.4f} em log); cobriu 72% no teste (uni07/resultado_uni07.md)",
           f"fora da previsao (sem renda/pop/estudio/master no cadastro): {list(fora) or 'nenhuma'}",
           f"variantes de metragem (declaradas antes de ler): {VARIANTES}",
           "", "EXPOSICAO (o que ja foi visto destas unidades antes do congelamento):"] + [f"- {x}" for x in EXPOSICAO] + [
           "", "FORA DO SUPORTE DO TREINO (registrado; a leitura separa por isso):",
           "- aceite de agregador: no treino 39/39 aceitam Wellhub; aqui varias nao aceitam nenhum (colunas aceita_*). As dummies de master",
           "  carregam composicao de agregador no treino (uni09/resultado_uni09.md), entao 'nao aceita nenhum' e' extrapolacao da v2.",
           "- pino/isocrona: confianca_coord 'baixa' (treino: 0), iso truncada (treino: 0/39), area da isocrona < minimo do treino (colunas no CSV).",
           "- metragem do time: APROXIMADA, sem definicao de area (util/bruta/ABL) nem calibracao contra a oficial; mezanino ambiguo em",
           "  bangu e vicente-pires-rua-8 (sem a area dele, nao ha variante). Elasticidade do m2 na v2 ~0,58: 10% de m2 ~ 5,7% na previsao.",
           "", "REGRA DE LEITURA (modo --ler-v2; so' com decisao do Felipe):",
           "- desfecho = mesma definicao do teste UNI-02: media do log do faturamento nos meses validos com mes de vida >= 12, >= 3 meses,",
           f"  janela {JAN26[0]}..{JAN26[1]} (ex.desfechos). N esperado: <= 3 ({', '.join(MADURAS_ESPERADAS)}).",
           "- nenhum agregado com n < 4 e' interpretado: leitura UNIDADE A UNIDADE, erro = real/previsto - 1 e o percentil desse erro na",
           "  distribuicao dos erros LOO do treino; separada entre 'aceita algum agregador' e 'nao aceita nenhum'; principal e variantes lado a lado.",
           "- jovens: trajetoria contra a curva congelada do UNI-03 (faturamento, p10-p90) x previsao; desvio 'dentro do erro da v2' se cabe",
           "  na faixa combinada nivel x rampa. Descritivo, nao teste.",
           "- outra janela (BLK-UNI-12): recalibrar o calendario como em 01_termometro.py:146-147 (mediana de Y_janela - Y25 nas do treino",
           "  presentes na janela) e reaplicar a MESMA previsao em log; a regra de meses e' a mesma.",
           "- conferencia, sem criterio de adocao (a adocao e' do Felipe)."]
    REG.write_text("\n".join(txt) + "\n", encoding="utf-8")
    print("\n".join(txt)); print(P.drop(columns=["metragem_obs", "origem_coord"]).round(3).to_string())
    print(f"\nSHA do REGISTRO (ancorar em {cand / 'backlog.md'}): {sha(REG)}")


def politica():
    lote3 = mod("l3", AQUI / "03_politica_sem_agregador.py")
    OUT_POL.mkdir(parents=True, exist_ok=True)
    d = pd.read_parquet(UNI / "dim_unidade.parquet"); d = d[~d.excluida_rede].set_index("unidade_id")
    f = pd.read_parquet(UNI / "fato_unidade_mes.parquet")
    f = f[f.unidade_id.isin(d.index) & f.mes_vida.notna() & ~f.flag_inauguracao_placeholder.fillna(False).astype(bool)].copy()
    met_sat = pd.read_csv(MET_SAT, sep=";", encoding="utf-8-sig", index_col=0).metragem_estimada_m2
    mt = pd.read_csv(MET_TIME, sep=";", encoding="utf-8").set_index("unidade_id").metragem_m2.astype(float)
    of = d.tam_metragem_m2
    fontes = {"todas as fontes (oficial → time → satélite)": of.combine_first(mt).combine_first(met_sat),
              "sem a metragem do time (oficial → satélite)": of.combine_first(met_sat),
              "só a metragem oficial": of}
    rot_fonte = pd.Series(np.where(of.notna(), "oficial", np.where(mt.reindex(d.index).notna(), "time", np.where(met_sat.reindex(d.index).notna(), "satélite", "sem"))), index=d.index)
    f["B"] = f.fin_vendas_ux - f.fin_tem_saude.fillna(0)
    f["pas"] = f.passagens_gympass + f.passagens_totalpass
    fin_ok = f.fin_vendas_ux.notna() & f.mes_completo.astype(bool)          # MESMO filtro do lote 3
    gr = []
    for u, g_ in f.groupby("unidade_id"):
        if not (g_.mes_vida == 1).any():
            continue
        first = g_[g_.pas > 0].mes_vida.min()
        sem = (pd.isna(first) or first > 3) and g_.mes_vida.max() >= 3
        com = (first <= 1) and str(g_.inauguracao_competencia.iloc[0]) >= "2024-01"
        gr.append({"unidade_id": u, "grupo": lote3.G_SEM if sem else (lote3.G_COM if com else "fora"), "fonte_m2": rot_fonte.get(u, "sem")})
    GR = pd.DataFrame(gr).set_index("unidade_id"); GR = GR[GR.grupo != "fora"]
    h = f[fin_ok & f.mes_vida.between(1, 12)].join(GR[["grupo", "fonte_m2"]], on="unidade_id", how="inner")
    comp = GR.groupby(["grupo", "fonte_m2"]).size().unstack(fill_value=0)
    fig, axs = plt.subplots(2, 4, figsize=(23, 10), sharey="row")
    cur = []
    paineis = list(fontes.items()) + [("todas as fontes, SEM RJ, DF e GO", fontes["todas as fontes (oficial → time → satélite)"])]
    for j, (nome_f, m2) in enumerate(paineis):
        hh = h.assign(m2=h.unidade_id.map(m2)); hh = hh[hh.m2.notna()]
        if "SEM RJ" in nome_f:
            hh = hh[~hh.uf.isin(["RJ", "DF", "GO"])]
        hh["fat_m2"] = hh.faturamento / hh.m2; hh["pag_m2"] = hh.pagantes / hh.m2
        for i, (col, rot) in enumerate((("fat_m2", "faturamento total R$ por m²"), ("pag_m2", "pagantes de balcão por m²"))):
            ax = axs[i, j]
            for gname, c_ in lote3.COR.items():
                s_ = hh[hh.grupo == gname]
                q = s_.groupby("mes_vida")[col].agg(["median", "size"])
                ax.plot(q.index, q["median"], "-o", ms=3, color=c_, label=gname)
                for x_, (m_, n_) in q.iterrows():
                    ax.annotate(f"{int(n_)}", (x_, m_), fontsize=6, color=c_, xytext=(0, 5), textcoords="offset points", ha="center")
                raw = s_.groupby("mes_vida")["faturamento" if col == "fat_m2" else "pagantes"].median()
                cur.append(q.assign(metrica=col, grupo=gname, fonte=nome_f, mediana_bruta_mesmo_subconjunto=raw).reset_index())
            ax.set_title(f"{rot}\n{nome_f}", fontsize=8.5); ax.set_xlabel("mês de vida")
            if j == 0:
                ax.set_ylabel(rot)
    axs[0, 0].legend(fontsize=7)
    txt = "Unidades por grupo e fonte da metragem:\n" + comp.to_string()
    fig.text(.01, -.06, txt, fontsize=7.5, family="monospace", va="top")
    fig.suptitle("Abrir sem agregador × com agregador, por m². Número no ponto = unidades. Se a diferença some sem a metragem do time, vinha da fonte; "
                 "se some sem RJ/DF/GO, vinha do estado — não da política.", y=1.01)
    salvar(fig, OUT_POL, "01_politica_por_m2_tres_fontes.png")
    C = pd.concat(cur)
    leia = pd.DataFrame({"campo": ["Pergunta", "Grupos", "Metragem", "Filtro de mês", "Cuidado", "O que NÃO está aqui", "Gerado por"], "descrição": [
        "Abrir só com balcão (política desde Botafogo, mar/2025) muda o faturamento e os pagantes POR m²?",
        f"Os mesmos do lote 3: '{lote3.G_SEM}' × '{lote3.G_COM}'.",
        "Três versões: todas as fontes (oficial → time de expansão → satélite), sem o time (oficial → satélite) e só oficial. A do time é aproximada e sem "
        "calibração; a do satélite foi corrigida pelo viés 1,12 (erro típico 20%). A fonte anda junto com o grupo (aba composicao).",
        "O mesmo do lote 3: Financeiro presente e mês completo. As colunas mediana_bruta_mesmo_subconjunto trazem o valor sem dividir por m² no mesmo recorte.",
        "Os grupos diferem em ESTADO (sem agregador tem muito RJ; com agregador, muito DF/GO) e em ÉPOCA (2026 × 2024–25). Leitura descritiva, não efeito "
        "causal. Poucas unidades sem agregador passaram do mês 9.",
        "Nada da Base Consolidada nem de arquivos LOCAL_ (pasta sincronizada com a nuvem).",
        "data/analysis/uni/exploratoria/04_turma_b_metragem.py --politica"]})
    with pd.ExcelWriter(OUT_POL / "numeros_dos_graficos.xlsx") as w:
        leia.to_excel(w, sheet_name="LEIA-ME", index=False)
        comp.to_excel(w, sheet_name="composicao")
        GR.to_excel(w, sheet_name="grupos")
        C.to_excel(w, sheet_name="curvas", index=False)
    print(comp.to_string())
    print(C.pivot_table(index=["fonte", "metrica", "mes_vida"], columns="grupo", values=["median", "size"]).loc[(slice(None), slice(None), [1, 3, 6, 9]), :].round(2).to_string())
    print(f"ok: {OUT_POL}")


def ler_v2():
    linhas = REG.read_text(encoding="utf-8").splitlines()
    def sha_de(prefixo):
        return next(l_ for l_ in linhas if l_.startswith(prefixo)).split("SHA-256 ")[1].strip()
    assert sha(PREV) == sha_de("previsoes:"), "previsoes da turma B mudaram depois do congelamento"
    for k in ("fato_unidade_mes", "dim_unidade", "metragem_time"):
        assert sha(insumos()[k]) == sha_de(f"insumo {k}:"), f"insumo {k} mudou depois do congelamento"
    M = modelo(); ex, f, loo = M["ex"], M["f"], M["loo"]
    P = pd.read_csv(PREV, sep=";", encoding="utf-8-sig", index_col=0)
    OUT_V2.mkdir(parents=True, exist_ok=True)
    Y = ex.desfechos(f, *JAN26)
    R = P.copy()
    R["real_fat_2026"] = np.exp(Y.l_fat.reindex(R.index)); R["meses_maduros_janela"] = Y.n_meses.reindex(R.index)
    R["erro_pct"] = 100 * (R.real_fat_2026 / R.prev_fat_2026 - 1)
    R["percentil_do_erro_no_LOO"] = [100 * float(np.mean(loo <= np.log(r / p))) if pd.notna(r) else np.nan for r, p in zip(R.real_fat_2026, R.prev_fat_2026)]
    R["aceita_algum_agregador"] = R.aceita_wellhub_cadastro.astype(str).eq("True") | R.aceita_totalpass_cadastro.astype(str).eq("True")
    mad = sorted(set(R.index[R.real_fat_2026.notna()]))
    cv = pd.read_csv(CURVA, sep=";", encoding="utf-8-sig"); cv = cv[cv.serie == "faturamento"].set_index("k")
    q10, q90 = np.quantile(loo, [.1, .9])
    Pp = P[P.variante == "principal_time"]
    n = len(Pp); cols = 3; lin = int(np.ceil(n / cols))
    fig, axs = plt.subplots(lin, cols, figsize=(17, 4 * lin), squeeze=False)
    jov = []
    for ax, (u, r) in zip(axs.flat, Pp.iterrows()):
        s_ = f[(f.unidade_id == u) & f.mes_vida.notna() & (f.mes_vida >= 1)].sort_values("mes_vida")
        ok = s_.valido.to_numpy()
        ax.plot(s_.mes_vida[ok], s_.faturamento[ok] / 1e3, "k-o", ms=3, label="real (mês válido)")
        k = cv.index[cv.index >= 1].to_numpy()
        ax.plot(k, r.prev_fat_2026 * cv.loc[k, "p50"] / 1e3, color="#c44e52", ls="--", lw=1, label="trajetória típica (UNI-03, regime com agregador)")
        ax.fill_between(k, r.prev_fat_2026 * np.exp(q10) * cv.loc[k, "p10"] / 1e3, r.prev_fat_2026 * np.exp(q90) * cv.loc[k, "p90"] / 1e3,
                        color="#c44e52", alpha=.10, label="faixa combinada nível (LOO p10–p90) × rampa (p10–p90)")
        ax.axhline(r.prev_fat_2026 / 1e3, color="#c44e52", lw=1.2, label="v2: previsto maduro (congelado)")
        ax.axhspan(r.faixa80_nominal_lo / 1e3, r.faixa80_nominal_hi / 1e3, color="#4c72b0", alpha=.06, label="faixa 80% nominal do nível (72% no teste)")
        for _, rv in P[(P.index == u) & (P.variante != "principal_time")].iterrows():
            ax.axhline(rv.prev_fat_2026 / 1e3, color="#8172b2", lw=.9, ls="-.")
            ax.annotate(rv.variante, (1, rv.prev_fat_2026 / 1e3), fontsize=6, color="#8172b2")
        tit = f"{u} — {int(r.metragem_m2)} m² (time), {'estúdio, ' if r.studios == 1 else ''}{r.master_id}, {'aceita agregador' if R.loc[[u]].aceita_algum_agregador.iloc[0] else 'NÃO aceita agregador'}"
        if u in mad:
            rr = R[(R.index == u) & (R.variante == "principal_time")].iloc[0]
            tit += f"\nMADURA: real R$ {rr.real_fat_2026 / 1e3:.0f} mil × previsto {rr.prev_fat_2026 / 1e3:.0f} ({rr.erro_pct:+.0f}%; percentil {rr.percentil_do_erro_no_LOO:.0f} do LOO)"
        else:
            u3 = s_[ok].tail(3)
            u3 = u3[u3.mes_vida <= 12]
            if len(u3):
                esp = r.prev_fat_2026 * cv.reindex(u3.mes_vida.astype(int)).p50.to_numpy()
                dv = 100 * (u3.faturamento.mean() / np.nanmean(esp) - 1)
                lo_ = r.prev_fat_2026 * np.exp(q10) * cv.reindex(u3.mes_vida.astype(int)).p10.to_numpy()
                hi_ = r.prev_fat_2026 * np.exp(q90) * cv.reindex(u3.mes_vida.astype(int)).p90.to_numpy()
                dentro = bool(np.nanmean(lo_) <= u3.faturamento.mean() <= np.nanmean(hi_))
                jov.append({"unidade_id": u, "meses_de_vida": f"{int(u3.mes_vida.min())}–{int(u3.mes_vida.max())}", "real_medio": u3.faturamento.mean(),
                            "trajetoria_tipica": float(np.nanmean(esp)), "desvio_vs_trajetoria_tipica_pct": dv, "dentro_da_faixa_combinada": dentro})
                tit += f"\njovem (meses {int(u3.mes_vida.min())}–{int(u3.mes_vida.max())}): {dv:+.0f}% contra a trajetória típica ({'dentro' if dentro else 'fora'} da faixa combinada)"
        fx = [c.replace("fora_faixa_treino_", "") + " " + str(r[c]) for c in P.columns if c.startswith("fora_faixa") and isinstance(r[c], str) and r[c]]
        if fx:
            tit += f"\nfora da faixa do treino: {', '.join(fx)}"
        ax.set_title(tit, fontsize=7.5); ax.set_xlabel("mês de vida"); ax.set_ylabel("faturamento (R$ mil/mês)")
    for ax in list(axs.flat)[n:]:
        ax.axis("off")
    list(axs.flat)[0].legend(fontsize=6)
    fig.suptitle("Turma B: previsão CONGELADA da v2 × faturamento real. Conferência com exposição parcial, unidade a unidade (n ≤ 3 maduras: nenhum agregado).", y=1.01)
    salvar(fig, OUT_V2, "01_turma_b_previsto_x_real.png")
    J = pd.DataFrame(jov).set_index("unidade_id") if jov else pd.DataFrame()
    leia = pd.DataFrame({"campo": ["Turma B", "Previsão", "Leitura", "Cuidado", "Gerado por"], "descrição": [
        "Unidades sem m² que receberam metragem APROXIMADA do time de expansão (06/10/2026). São Carlos Centro fora da previsão (sem cadastro de master/estúdio).",
        f"v2 travada, congelada com SHA antes desta leitura: data/analysis/uni/previsao_turma_b/{REG.name}. Variantes de metragem declaradas antes.",
        "Maduras: mesma regra do teste de 2026, unidade a unidade, com o percentil do erro na distribuição LOO. Jovens: contra a curva congelada do UNI-03.",
        "Exposição parcial (ver REGISTRO); várias unidades fora do suporte do treino (não aceitam agregador, pino de baixa confiança, isócrona truncada).",
        "data/analysis/uni/exploratoria/04_turma_b_metragem.py --ler-v2"]})
    with pd.ExcelWriter(OUT_V2 / "numeros_dos_graficos.xlsx") as w:
        leia.to_excel(w, sheet_name="LEIA-ME", index=False)
        R.to_excel(w, sheet_name="previsto_x_real")
        J.to_excel(w, sheet_name="jovens")
    print(R[["variante", "metragem_m2", "prev_fat_2026", "real_fat_2026", "meses_maduros_janela", "erro_pct", "percentil_do_erro_no_LOO", "aceita_algum_agregador"]].round(1).to_string())
    print(J.round(1).to_string())


if __name__ == "__main__":
    modos = {"--congelar": congelar, "--politica": politica, "--ler-v2": ler_v2}
    escolhido = [m for m in modos if m in sys.argv]
    if len(escolhido) != 1:
        sys.exit("use exatamente um modo: --congelar | --politica | --ler-v2")
    modos[escolhido[0]]()
