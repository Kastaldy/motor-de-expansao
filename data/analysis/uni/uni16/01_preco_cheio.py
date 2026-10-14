# -*- coding: utf-8 -*-
"""BLK-UNI-16 (protocolo_uni16.md v1.1, 07/10): preco de TABELA do plano (Gold) observado nos meses de vida 1-12, como entrada
antes de abrir, nos TRES modelos (faturamento, balcao, agregador) + total recombinado. 57 unidades juntas com ajuste de nivel
de 2026; duas marcas (sem dado de venda / sem preco cheio) nos dois lados. Principal = efeito (HC3, t, faixa 90%, Holm k=3,
dois lados a 10%); portao = erro de cada unidade prevista sem ela cai >= 2 pontos (faturamento E total).
Modos (um por vez): --seca | --ensaio | --registrar | --rodar   (.venv, PYTHONPATH=src). Sem Base Consolidada."""
import glob
import hashlib
import importlib.util
import re
import sys
import types
import unicodedata
import warnings
from datetime import datetime
from pathlib import Path

try:
    import h3  # noqa: F401
except ImportError:
    for _k in [k for k in sys.modules if k == "h3" or k.startswith("h3.")]:
        del sys.modules[_k]
    sys.modules["h3"] = types.ModuleType("h3")

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.stats import t as T_  # noqa: E402

warnings.filterwarnings("ignore")
AQUI = Path(__file__).resolve().parent
UNI = AQUI.parent
REPO = UNI.parent.parent.parent
PROT, REG_PRE, RES = AQUI / "protocolo_uni16.md", AQUI / "REGISTRO_PRE.txt", AQUI / "resultado_uni16.md"
MARCA, REG_POS = AQUI / "RODADA_INICIADA.txt", AQUI / "REGISTRO_POS.txt"
OUT = Path(r"C:\Users\Felipe\OneDrive - Grupo Ultra\Área de Trabalho\Análises - Motor de Expansão\Exploratória BLK-UNI\11 - Preço de tabela na abertura")
ENSAIO = Path(r"C:\Users\Felipe\AppData\Local\Temp\claude\C--dev-motor-de-expansao\9259d0a1-7dda-49bd-a390-c88f3d4ac1a6\scratchpad\uni16_ensaio")
VENDAS = UNI / "precos" / "vendas_unidade_mes.parquet"
ALFA, Z90 = 0.10, 1.6449
MODELOS = ("faturamento", "balcão", "agregador")
TRAVA = (38, 22, 16, {"faturamento": 57, "balcão": 57, "agregador": 56})   # --seca de 07/10
plt.rcParams.update({"figure.dpi": 110, "savefig.dpi": 150, "font.size": 9, "axes.grid": True, "grid.alpha": .3})


def mod(nome, p):
    s = importlib.util.spec_from_file_location(nome, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def insumos():
    u15 = mod("u15_ins", UNI / "uni15" / "01_melhorias.py")
    b = {k: v for k, v in u15.insumos().items() if k not in ("protocolo", "script")}
    b.update({"protocolo": PROT, "script": Path(__file__), "mod_uni15": UNI / "uni15" / "01_melhorias.py", "vendas": VENDAS,
              "coletor_vendas": UNI / "precos" / "01_coletar_vendas.py", "depara": UNI / "depara_unidade.parquet"})
    return b


# ------------------------------------------------------------------ variavel
def _norm(s):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().upper().strip())


def mapa_nomes():
    dp = pd.read_parquet(UNI / "depara_unidade.parquet"); m = {}
    for _, r in dp.iterrows():
        for nm in [r.nome] + re.split(r"[|;]", str(r.nomes_crus or "")):
            if nm and nm != "None":
                k = _norm(nm); m.setdefault(k, set()).add(r.unidade_id); m.setdefault(re.sub(r" - [A-Z]{2}$", "", k), set()).add(r.unidade_id)
    return m


def vendas_com_id(Bs):
    m = mapa_nomes(); v = pd.read_parquet(VENDAS)
    v["unidade_id"] = v.unidade.map(lambda n: next(iter(m[_norm(n)])) if m.get(_norm(n)) and len(m[_norm(n)]) == 1 else None)
    v = v[v.unidade_id.notna()].copy()
    d = Bs["d"]; ina = pd.to_datetime(d.inauguracao).dt.to_period("M")
    ph = d.flag_inauguracao_placeholder.fillna(False).astype(bool) if "flag_inauguracao_placeholder" in d else pd.Series(False, index=d.index)
    v["k"] = [np.nan if (pd.isna(ina.get(u)) or bool(ph.get(u, False))) else float((pd.Period(c, "M") - ina[u]).n) for c, u in zip(v.competencia, v.unidade_id)]
    return v


def referencia(v, janela):
    ok = v[(v.n_gold_cheio >= 10) & (v.k >= 12)]
    meses = sorted(v.competencia.unique()); P = pd.PeriodIndex(ok.competencia, freq="M")
    return pd.Series({c: float(ok.preco_gold_moda[(P >= pd.Period(c, "M") - janela) & (P <= pd.Period(c, "M") + janela)].median()) for c in meses})


def preco_tabela(Bs, unidades, janela=1):
    v = vendas_com_id(Bs); ref = referencia(v, janela)
    rows = []
    for u in unidades:
        h = v[(v.unidade_id == u) & v.k.between(1, 12)]
        c = h[h.n_gold_cheio >= 10]
        rel = np.log(c.preco_gold_moda.to_numpy(float) / c.competencia.map(ref).to_numpy(float))
        rows.append({"unidade_id": u, "meses_com_venda": len(h), "meses_com_preco_cheio": len(c),
                     "preco_mediano": float(c.preco_gold_moda.median()) if len(c) else np.nan,
                     "l_preco_rel": float(np.median(rel)) if len(c) >= 3 else np.nan})
    return pd.DataFrame(rows).set_index("unidade_id")


def com_preco(D, PR):
    D = D.copy(); pr = PR.reindex(D.index)
    D["l_preco_rel_bruto"] = pr.l_preco_rel
    D["sem_dado_venda"] = (pr.meses_com_venda.fillna(0) < 3).astype(float)
    D["sem_preco_cheio"] = ((D.sem_dado_venda == 0) & D.l_preco_rel_bruto.isna()).astype(float)
    D["l_preco_rel"] = D.l_preco_rel_bruto.fillna(D.l_preco_rel_bruto.mean())
    return D


# ------------------------------------------------------------------ teste
def efeito(u15, D, cols, y, var="l_preco_rel"):
    y = np.asarray(y, float); b, se = u15.hc3(D, cols, y); gl = len(y) - len(cols) - 1
    tt = b[var] / se[var]
    return float(b[var]), float(se[var]), float(2 * (1 - T_.cdf(abs(tt), gl))), gl


def pct10(b):
    return 100 * (1.1 ** b - 1)


def faixa(b, se, gl):
    q = T_.ppf(.95, gl)
    return pct10(b - q * se), pct10(b + q * se)


def rodar(Bs, u15, P, PR0):
    fp = u15.fac(Bs, P.index); Y = u15.alvos(P, fp)
    V2 = Bs["V2"]; base = V2 + ["ano2026", "sem_dado_venda", "sem_preco_cheio"]; novo = base + ["l_preco_rel"]
    cc_all = (P.l_preco_rel_bruto.notna()).to_numpy()
    linhas, port, leit = [], [], []
    for mod_ in MODELOS:
        y = Y[mod_]; ok = np.isfinite(y)
        b, se, p, gl = efeito(u15, P[ok], novo, y[ok]); lo, hi = faixa(b, se, gl)
        linhas.append({"modelo": mod_, "n": int(ok.sum()), "n_com_preco": int((ok & cc_all).sum()), "elasticidade": b, "erro_padrao_hc3": se, "graus_liberdade": gl,
                       "efeito_10pct_pct": pct10(b), "faixa90_lo_pct": lo, "faixa90_hi_pct": hi, "p": p})
        e0, e1 = u15.loo(P[ok], base, y[ok]), u15.loo(P[ok], novo, y[ok]); dd = u15.dif_boot(e1, e0)
        s = cc_all[ok]; dds = u15.dif_boot(e1[s], e0[s])
        port.append({"modelo": mod_, "n": int(ok.sum()), "erro_sem_preco_pct": 100 * u15.et(e0), "erro_com_preco_pct": 100 * u15.et(e1), "dif_pontos": 100 * dd[0],
                     "dif_faixa90_lo": 100 * dd[1], "dif_faixa90_hi": 100 * dd[2], "R2_sem": u15.r2(y[ok], e0), "R2_com": u15.r2(y[ok], e1),
                     "so_com_preco_n": int(s.sum()), "so_com_preco_dif_pontos": 100 * dds[0]})
        cc = ok & cc_all; colsc = V2 + ["ano2026", "l_preco_rel"]
        for rot, msk, D_, cols in ((f"só as unidades com preço", cc, P, colsc), ("sem Botafogo", ok & (P.index != "botafogo-rj"), P, novo)):
            b2, se2, p2, gl2 = efeito(u15, D_[msk], cols, y[msk]); l2, h2 = faixa(b2, se2, gl2)
            leit.append({"modelo": mod_, "leitura": rot, "n": int(msk.sum()), "efeito_10pct_pct": pct10(b2), "faixa90": f"{l2:+.1f}% a {h2:+.1f}%", "p": p2})
        cad = Bs["d"].cad_preco_gold.reindex(P.index).astype(float)
        Q = P.copy(); Q["l_preco_rel"] = np.log(cad / cad[cc_all].median()); mq = cc & Q.l_preco_rel.notna().to_numpy()
        b3, se3, p3, gl3 = efeito(u15, Q[mq], colsc, y[mq]); l3, h3_ = faixa(b3, se3, gl3)
        leit.append({"modelo": mod_, "leitura": "preço de HOJE no cadastro (depois do resultado), mesmas unidades", "n": int(mq.sum()),
                     "efeito_10pct_pct": pct10(b3), "faixa90": f"{l3:+.1f}% a {h3_:+.1f}%", "p": p3})
        R0 = com_preco(P.drop(columns=["l_preco_rel_bruto", "sem_dado_venda", "sem_preco_cheio", "l_preco_rel"]), PR0)
        b4, se4, p4, gl4 = efeito(u15, R0[ok], novo, y[ok]); l4, h4 = faixa(b4, se4, gl4)
        leit.append({"modelo": mod_, "leitura": "referência só do mesmo mês", "n": int(ok.sum()), "efeito_10pct_pct": pct10(b4), "faixa90": f"{l4:+.1f}% a {h4:+.1f}%", "p": p4})
    T = pd.DataFrame(linhas)
    ps = T.p.sort_values(); ok_ = True                    # Holm k = 3, 10% dos dois lados
    for i, (ix, p) in enumerate(ps.items()):
        ok_ = ok_ and p <= ALFA / (len(ps) - i); T.loc[ix, "holm_ok"] = ok_
    T["leitura"] = np.where(T.holm_ok.astype(bool), "tem efeito", "não se distingue de zero")
    yT = P.Y_tot.to_numpy(float); eT = {}
    for nome, cols in (("sem", base), ("com", novo)):
        e = np.full(len(P), np.nan)
        for i in range(len(P)):
            m = np.ones(len(P), bool); m[i] = False
            e[i] = yT[i] - u15.pred2p(Bs, u15.fit2p(Bs, P[m], cols, fp[m]), P.iloc[[i]], cols, fp[[i]])[0]
        eT[nome] = e
    dd = u15.dif_boot(eT["com"], eT["sem"]); dds = u15.dif_boot(eT["com"][cc_all], eT["sem"][cc_all])
    port.append({"modelo": "total recombinado", "n": len(P), "erro_sem_preco_pct": 100 * u15.et(eT["sem"]), "erro_com_preco_pct": 100 * u15.et(eT["com"]),
                 "dif_pontos": 100 * dd[0], "dif_faixa90_lo": 100 * dd[1], "dif_faixa90_hi": 100 * dd[2], "R2_sem": u15.r2(yT, eT["sem"]), "R2_com": u15.r2(yT, eT["com"]),
                 "so_com_preco_n": int(cc_all.sum()), "so_com_preco_dif_pontos": 100 * dds[0]})
    PT = pd.DataFrame(port)
    g = lambda m_: float(PT[PT.modelo == m_].dif_pontos.iloc[0])
    portao = (g("faturamento") <= -2) and (g("total recombinado") <= -2)
    for nome, yy in (("alunos de balcão (log de pagantes)", P.l_pag.to_numpy(float)), ("ticket do balcão (balcão ÷ pagantes)", P.Y_B.to_numpy(float) - P.l_pag.to_numpy(float))):
        ok = np.isfinite(yy); b5, se5, p5, gl5 = efeito(u15, P[ok], novo, yy[ok]); l5, h5 = faixa(b5, se5, gl5)
        leit.append({"modelo": "balcão (decomposição)", "leitura": nome, "n": int(ok.sum()), "efeito_10pct_pct": pct10(b5), "faixa90": f"{l5:+.1f}% a {h5:+.1f}%", "p": p5})
    return T, PT, pd.DataFrame(leit), portao


# ------------------------------------------------------------------ saidas
def graficos(out, T, PT):
    out.mkdir(parents=True, exist_ok=True)
    fig, axs = plt.subplots(1, 2, figsize=(14, 5))
    y_ = np.arange(len(T))
    axs[0].errorbar(T.efeito_10pct_pct, y_, xerr=[T.efeito_10pct_pct - T.faixa90_lo_pct, T.faixa90_hi_pct - T.efeito_10pct_pct], fmt="o", color="#4c72b0", capsize=4)
    axs[0].axvline(0, color="k", lw=.8); axs[0].set_yticks(y_); axs[0].set_yticklabels([f"{m}\n(n {n}; com preço {c})" for m, n, c in zip(T.modelo, T.n, T.n_com_preco)])
    axs[0].set_xlabel("efeito de um preço 10% acima da rede (%), faixa de 90%"); axs[0].set_title("Efeito do preço de tabela")
    x = np.arange(len(PT))
    axs[1].bar(x - .2, PT.erro_sem_preco_pct, .4, color="#bbbbbb", label="sem o preço"); axs[1].bar(x + .2, PT.erro_com_preco_pct, .4, color="#4c72b0", label="com o preço")
    axs[1].set_xticks(x); axs[1].set_xticklabels([f"{m}\n(n {n})" for m, n in zip(PT.modelo, PT.n)]); axs[1].set_ylabel("erro típico, cada unidade prevista sem ela (%)")
    axs[1].legend(fontsize=7); axs[1].set_title("Portão de adoção")
    fig.tight_layout(); fig.savefig(out / "01_preco_tabela.png", bbox_inches="tight"); plt.close(fig)


def escrever(destino, ensaio, T, PT, L, portao, PR, P):
    f1 = lambda x: "—" if pd.isna(x) else f"{x:.1f}%"
    pr = PR.l_preco_rel.dropna()
    n_dado, n_cheio = int(P.sem_dado_venda.sum()), int(P.sem_preco_cheio.sum())
    Lm = [f"# BLK-UNI-16 — preço de tabela do plano{' (ENSAIO COM RUÍDO — NÃO INTERPRETAR)' if ensaio else ''}", "",
          f"Protocolo `protocolo_uni16.md` v1.1. Rodado em {datetime.now():%Y-%m-%d %H:%M}.", "",
          "## Como ler", "",
          "- **Preço relativo:** o preço cheio do Gold que a unidade mais praticou no 1º ano, contra a mediana das unidades maduras "
          "no mesmo período. 10% acima ≈ um degrau de R$ 10–15 na tabela.",
          "- **Efeito:** quanto o faturamento (ou o balcão, ou o agregador) muda numa unidade com preço 10% acima, com o resto do modelo "
          "igual (metragem, renda, população, master, estúdio).",
          "- **Faixa de 90%:** 9 em 10 vezes o efeito verdadeiro cai dentro. Se cruza o zero, não dá para separar do acaso. O veredito "
          "ainda desconta que são 3 modelos testados (por isso uma faixa que não cruza o zero pode sair \"não se distingue\").",
          "- **Erro típico:** quanto a previsão erra numa unidade comum, com cada unidade prevista sem ela. Menor = melhor. "
          "**R²:** quanto da diferença entre unidades o modelo acerta fora da amostra (1 = tudo; 0 = igual a chutar a média).",
          f"- **Unidades:** as 57 do modelo; {len(pr)} têm preço de tabela no 1º ano. Sem preço: {n_dado} por falta de dado de venda (abriram "
          f"antes da coleta) e {n_cheio} porque só venderam com promoção ou outro plano. Essas entram com uma marca, nos dois lados.", "",
          "## Avisos", "",
          "- A venda registra a primeira cobrança: nos meses de promoção (R$ 9,90) o preço do plano não aparece.",
          "- O preço do 1º ano pode ter subido porque a unidade encheu (reação à demanda): isso puxa para um efeito positivo.",
          "- Prever não é causar. As 57 unidades já foram muito usadas. **\"Não se distingue de zero\" não prova que o preço não importa**: "
          "a variação de preço entre unidades é pequena e o teste tem pouca força.",
          "- **Nada é adotado sem o Felipe.**", "",
          "## Resposta curta", "",
          "- **Efeito:** " + "; ".join(f"{r.modelo} {r.efeito_10pct_pct:+.1f}% por 10% de preço (faixa {r.faixa90_lo_pct:+.1f}% a {r.faixa90_hi_pct:+.1f}%) — {r.leitura}"
                                       for _, r in T.iterrows()) + ".",
          "- **Portão de adoção** (o erro cai ≥ 2 pontos no faturamento e no total): **" + ("passa" if portao else "não passa") + "**. " + "; ".join(
              f"{r.modelo} {f1(r.erro_sem_preco_pct)} → {f1(r.erro_com_preco_pct)}" for _, r in PT.iterrows()) + ".", "",
          "## Efeito (principal)", "",
          "| modelo | n | com preço | efeito de +10% no preço | faixa 90% | p | leitura |", "|---|---|---|---|---|---|---|"] + [
        f"| {r.modelo} | {r.n} | {r.n_com_preco} | {r.efeito_10pct_pct:+.1f}% | {r.faixa90_lo_pct:+.1f}% a {r.faixa90_hi_pct:+.1f}% | {r.p:.3f} | {r.leitura} |"
        for _, r in T.iterrows()]
    Lm += ["", "## Portão de adoção (erro de cada unidade prevista sem ela)", "",
           "| modelo | n | sem o preço | com o preço | diferença (faixa 90%) | R² (sem → com) | só nas com preço |", "|---|---|---|---|---|---|---|"] + [
        f"| {r.modelo} | {r.n} | {f1(r.erro_sem_preco_pct)} | {f1(r.erro_com_preco_pct)} | {r.dif_pontos:+.1f} ({r.dif_faixa90_lo:+.1f} a {r.dif_faixa90_hi:+.1f}) | "
        f"{r.R2_sem:.2f} → {r.R2_com:.2f} | {r.so_com_preco_dif_pontos:+.1f} (n {r.so_com_preco_n}) |" for _, r in PT.iterrows()]
    Lm += ["", "## Leituras (sem veredito)", "", "| modelo | leitura | n | efeito de +10% no preço | faixa 90% |", "|---|---|---|---|---|"] + [
        f"| {r.modelo} | {r.leitura} | {r.n} | {r.efeito_10pct_pct:+.1f}% | {r.faixa90} |" for _, r in L.iterrows()]
    Lm += ["", f"Preço relativo das {len(pr)} unidades: mediana {100 * (np.exp(pr.median()) - 1):+.0f}%, de {100 * (np.exp(pr.min()) - 1):+.0f}% a "
           f"{100 * (np.exp(pr.max()) - 1):+.0f}% das maduras.", ""]
    destino.write_text("\n".join(Lm) + "\n", encoding="utf-8")
    return "\n".join(Lm)


def main():
    modo = [m for m in ("--seca", "--ensaio", "--registrar", "--rodar") if m in sys.argv]
    if len(modo) != 1:
        sys.exit("use exatamente um modo")
    modo = modo[0]
    if modo == "--registrar":
        if REG_PRE.exists():
            sys.exit("RECUSADO: REGISTRO_PRE ja existe")
        txt = [f"REGISTRO PRE-RODADA BLK-UNI-16 (protocolo v1.1) — {datetime.now():%Y-%m-%d %H:%M}"] + [f"{k}: {Path(p).name}  SHA-256 {sha(p)}" for k, p in insumos().items()]
        REG_PRE.write_text("\n".join(txt) + "\n", encoding="utf-8"); print("SHA REGISTRO_PRE:", sha(REG_PRE)); return
    if modo == "--rodar":
        if MARCA.exists() or RES.exists() or REG_POS.exists():
            sys.exit("RECUSADO: rodada real ja aconteceu (ou comecou)")
        linhas = REG_PRE.read_text(encoding="utf-8").splitlines()
        for k, p in insumos().items():
            reg = next(l_ for l_ in linhas if l_.startswith(f"{k}:")).split("SHA-256 ")[1].strip()
            assert sha(p) == reg, f"{k} mudou depois do REGISTRO_PRE"
        MARCA.write_text(f"rodada iniciada em {datetime.now():%Y-%m-%d %H:%M}\n", encoding="utf-8")
    u14 = mod("u14", UNI / "uni14" / "01_validacao_ampliada.py"); u15 = mod("u15", UNI / "uni15" / "01_melhorias.py")
    Bs = u14.base(); Bs["u14"] = u14
    tr, te, _, _, _ = u15.montar_bases(Bs)
    P0 = pd.concat([tr, te])
    PR, PR0 = preco_tabela(Bs, P0.index, janela=1), preco_tabela(Bs, P0.index, janela=0)
    P = com_preco(P0, PR)
    n_mod = {m: int(np.isfinite(y).sum()) for m, y in u15.alvos(P, u15.fac(Bs, P.index)).items()}
    cont = (int(P.l_preco_rel_bruto.notna().sum()), int(P.l_preco_rel_bruto.reindex(tr.index).notna().sum()), int(P.l_preco_rel_bruto.reindex(te.index).notna().sum()), n_mod)
    if modo == "--seca":
        print("com preço (total, 39, 18), n por modelo:", cont, "| sem dado:", int(P.sem_dado_venda.sum()), "| sem preço cheio:", int(P.sem_preco_cheio.sum()))
        print("preço relativo (%):", (100 * (np.exp(PR.l_preco_rel.dropna()) - 1)).describe().round(1).to_dict())
        print("meses com preço cheio:", PR.meses_com_preco_cheio.describe().round(1).to_dict(), "| l_pag na base:", "l_pag" in P)
        print("sem preço cheio:", sorted(P.index[P.sem_preco_cheio == 1])); print("sem dado:", sorted(P.index[P.sem_dado_venda == 1]))
        return
    if modo == "--ensaio":
        rz = np.random.default_rng(11)
        ya = P.Y_A.notna().to_numpy()
        P["Y_B"] = rz.normal(11.8, .3, len(P)); P["Y_A"] = np.where(ya, P.Y_B - 1.1 + rz.normal(0, .3, len(P)), np.nan)
        P["Y_tot"] = np.log(np.exp(P.Y_B) + np.nan_to_num(np.exp(P.Y_A))); P["l_pag"] = P.Y_B - 4.9 + rz.normal(0, .1, len(P))
        dest = outd = ENSAIO; dest.mkdir(parents=True, exist_ok=True)
    else:
        dest, outd = AQUI, OUT
    if modo == "--rodar":
        assert TRAVA is not None and cont == TRAVA, cont
    T, PT, L, portao = rodar(Bs, u15, P, PR0)
    graficos(outd, T, PT)
    with pd.ExcelWriter(outd / "preco_tabela.xlsx") as w:
        pd.DataFrame({"campo": ["O que é", "Como ler", "Aviso", "Gerado por"], "descrição": [
            "BLK-UNI-16: o preço de tabela do plano Gold (1º ano) melhora a previsão dos três modelos e do total?",
            "Efeito = mudança (%) numa unidade com preço 10% acima das maduras, com o resto igual. Erro típico = quanto a previsão erra numa unidade comum.",
            "A venda registra a primeira cobrança (promoção de R$ 9,90 esconde o preço). Unidades já vistas; prever não é causar. Nada adotado sem o Felipe.",
            "data/analysis/uni/uni16/01_preco_cheio.py (protocolo v1.1)"]}).to_excel(w, sheet_name="LEIA-ME", index=False)
        T.to_excel(w, sheet_name="efeito", index=False); PT.to_excel(w, sheet_name="portao", index=False); L.to_excel(w, sheet_name="leituras", index=False)
        PR.to_excel(w, sheet_name="preco_por_unidade")
    txt = escrever(dest / RES.name, modo == "--ensaio", T, PT, L, portao, PR, P)
    if modo == "--rodar":
        REG_POS.write_text(f"BLK-UNI-16 rodado em {datetime.now():%Y-%m-%d %H:%M}.\n{RES.name}  SHA-256 {sha(RES)}\nREGISTRO_PRE.txt  SHA-256 {sha(REG_PRE)}\n", encoding="utf-8")
    print(txt if modo == "--rodar" else f"ensaio ok: {dest}")


if __name__ == "__main__":
    main()
