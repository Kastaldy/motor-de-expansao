# -*- coding: utf-8 -*-
"""Releitura (pedido do Felipe, 07/10) dos testes antigos com a MEDIDA DE EFEITO, porque a regua de 2 pontos (39 + teste) tinha
poder de 1-4% para efeito moderado (simulacao de 07/10). LEITURA, sem veredito: as unidades ja foram vistas e os testes ja
rodaram. Metodo fixado antes de rodar (este docstring):
- base: as 57 do modelo juntas (39 de 2025 + 18 de 2026) com ajuste de nivel de 2026 (ano2026), como no T2 do UNI-15;
- tres modelos: faturamento (v2), balcao, agregador (alvo 'como se aceitasse os dois apps');
- para cada variavel testada antes, o coeficiente somado a v2, com faixa robusta (HC3) de 90%; casos completos daquela variavel;
- masters: teste conjunto (Wald com HC3) das 3 dummies; regiao: R1 (fora do DF/GO) e R2 (SP, outras UFs) no lugar das masters;
- variaveis: masters (UNI-14/15), regiao R1/R2 (UNI-15 T1), tier do Wellhub do cadastro (UNI-14 D), estudio x renda (UNI-14 C),
  mercado de agregador x1 e x2 (UNI-14 B);
- Holm dentro de cada modelo (familia = as variaveis da tabela), 10% dos dois lados, so' como referencia.
Treino ampliado (UNI-15 T2) nao e' variavel: fica de fora (o que muda la' e' o numero de unidades, nao um efeito).
Saida: releitura/resultado_releitura.md + OneDrive '12 - Releitura com medida de efeito'. (.venv, PYTHONPATH=src)"""
import importlib.util
import sys
import types
import warnings
from datetime import datetime
from pathlib import Path

try:
    import h3  # noqa: F401
except ImportError:
    for _k in [k for k in sys.modules if k == "h3" or k.startswith("h3.")]:
        del sys.modules[_k]
    sys.modules["h3"] = types.ModuleType("h3")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.stats import chi2, norm as N  # noqa: E402

warnings.filterwarnings("ignore")
AQUI = Path(__file__).resolve().parent
UNI = AQUI.parent
OUT = Path(r"C:\Users\Felipe\OneDrive - Grupo Ultra\Área de Trabalho\Análises - Motor de Expansão\Exploratória BLK-UNI\12 - Releitura com medida de efeito")
Z90, ALFA = 1.6449, 0.10
MODELOS = ("faturamento", "balcão", "agregador")


def mod(nome, p):
    s = importlib.util.spec_from_file_location(nome, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def hc3_full(u15, D, cols, y):
    y = np.asarray(y, float); X = u15.X_(D, cols); XtXi = np.linalg.pinv(X.T @ X); b = XtXi @ X.T @ y; e = y - X @ b
    h = np.einsum("ij,jk,ik->i", X, XtXi, X); w = (e / np.clip(1 - h, 1e-6, None)) ** 2
    idx = ["const"] + list(cols)
    return pd.Series(b, index=idx), pd.DataFrame(XtXi @ (X.T * w) @ X @ XtXi, index=idx, columns=idx)


def main():
    u14 = mod("u14", UNI / "uni14" / "01_validacao_ampliada.py"); u15 = mod("u15", UNI / "uni15" / "01_melhorias.py")
    Bs = u14.base(); Bs["u14"] = u14
    tr, te, _, _, _ = u15.montar_bases(Bs)
    P = pd.concat([tr, te]); fp = u15.fac(Bs, P.index); Y = u15.alvos(P, fp)
    V2, DUM = Bs["V2"], Bs["DUM"]
    base_sem_m = ["l_m2", "l_renda_dom", "l_pop", "studios", "ano2026"]
    testes = [  # (rotulo, teste anterior, colunas extras, colunas da base, variaveis do efeito)
        ("masters (conjunto)", "UNI-14/15: nenhum braço passou", [], base_sem_m + DUM, DUM),
        ("região R1: fora do DF/GO", "UNI-15 T1: não passou", ["reg_fora"], base_sem_m, ["reg_fora"]),
        ("região R2: SP", "UNI-15 T1: não passou", ["reg_SP", "reg_outros"], base_sem_m, ["reg_SP"]),
        ("região R2: outras UFs", "UNI-15 T1: não passou", ["reg_SP", "reg_outros"], base_sem_m, ["reg_outros"]),
        ("tier do Wellhub do cadastro", "UNI-14 D: o mais perto, não passou", ["wh_ord_cad"], V2 + ["ano2026"], ["wh_ord_cad"]),
        ("estúdio × renda", "UNI-14 C: não passou", ["inter_est_renda"], V2 + ["ano2026"], ["inter_est_renda"]),
        ("mercado de agregador: parceiros por mil hab.", "UNI-14 B: não passou", ["x1_parceiros_mil", "x2_indep_ag"], V2 + ["ano2026"], ["x1_parceiros_mil"]),
        ("mercado de agregador: independentes", "UNI-14 B: não passou", ["x1_parceiros_mil", "x2_indep_ag"], V2 + ["ano2026"], ["x2_indep_ag"]),
    ]
    linhas = []
    for mod_ in MODELOS:
        y_all = Y[mod_]
        for rot, antes, extra, base, alvo in testes:
            cols = list(dict.fromkeys(base + extra))
            ok = np.isfinite(y_all) & P[cols].notna().all(axis=1).to_numpy()
            b, V = hc3_full(u15, P[ok], cols, y_all[ok])
            if len(alvo) > 1:
                bb = b[alvo].to_numpy(); W = float(bb @ np.linalg.pinv(V.loc[alvo, alvo].to_numpy()) @ bb)
                p = float(1 - chi2.cdf(W, len(alvo)))
                ef, lo, hi = "; ".join(f"{c.replace('mr_', '')} {100 * (np.exp(b[c]) - 1):+.0f}%" for c in alvo), np.nan, np.nan
            else:
                c = alvo[0]; se = float(np.sqrt(V.loc[c, c])); p = float(2 * (1 - N.cdf(abs(b[c] / se))))
                ef, lo, hi = f"{100 * (np.exp(b[c]) - 1):+.0f}%", 100 * (np.exp(b[c] - Z90 * se) - 1), 100 * (np.exp(b[c] + Z90 * se) - 1)
            linhas.append({"modelo": mod_, "variavel": rot, "teste_anterior": antes, "n": int(ok.sum()), "efeito": ef, "faixa90_lo_pct": lo, "faixa90_hi_pct": hi, "p": p})
    T = pd.DataFrame(linhas)
    for mod_ in MODELOS:
        m = T.modelo == mod_; ps = T.loc[m, "p"].sort_values(); ok_ = True
        for i, (ix, p) in enumerate(ps.items()):
            ok_ = ok_ and p <= ALFA / (len(ps) - i); T.loc[ix, "holm_ok"] = ok_
    T["leitura"] = np.where(T.p <= ALFA, np.where(T.holm_ok.astype(bool), "efeito claro (sobrevive à correção)", "efeito, mas não sobrevive à correção"), "não se distingue de zero")
    nota = {"tier do Wellhub do cadastro": "unidade por nível de tier (ordinal)", "estúdio × renda": "por 1 desvio-padrão de renda, nas com estúdio",
            "mercado de agregador: parceiros por mil hab.": "por +1 em log", "mercado de agregador: independentes": "por +1 em log"}
    L = ["# Releitura dos testes antigos com a medida de efeito (LEITURA, sem veredito)", "",
         f"Rodado em {datetime.now():%Y-%m-%d %H:%M}. Método no topo de `releitura/01_releitura_efeito.py`, escrito antes de rodar.", "",
         "## Por que reler", "",
         "A régua antiga (cair ≥ 2 pontos no erro das 39 E no teste das 18) detecta um efeito real moderado em só 1–4% das vezes "
         "(simulação de 07/10). Então \"não passou\" quase não dizia nada sobre existir efeito. Aqui a pergunta é outra: **a variável "
         "tem efeito, e de que tamanho?**", "",
         "## Como ler", "",
         "- **Efeito:** quanto o faturamento (ou o balcão, ou o agregador) muda com a variável, com o resto do modelo igual. Masters e "
         "região: contra o DF/GO (master M1).",
         "- **Faixa de 90%:** se cruza o zero, não dá para separar do acaso. **p:** chance de um efeito desse tamanho aparecer por acaso.",
         "- **Correção:** com 8 variáveis por modelo, alguma \"acerta\" por acaso; \"sobrevive à correção\" desconta isso (Holm).",
         "- **Aviso:** as 57 unidades já foram vistas e estes testes já rodaram. É leitura, não teste novo. Ter efeito também não é o mesmo "
         "que melhorar a previsão de unidade nova: o efeito pode existir e ser pequeno demais para mudar o erro.", "",
         "| modelo | variável | teste anterior | n | efeito | faixa 90% | p | leitura |", "|---|---|---|---|---|---|---|---|"]
    for _, r in T.iterrows():
        fx = "—" if pd.isna(r.faixa90_lo_pct) else f"{r.faixa90_lo_pct:+.0f}% a {r.faixa90_hi_pct:+.0f}%"
        L.append(f"| {r.modelo} | {r.variavel}{(' (' + nota[r.variavel] + ')') if r.variavel in nota else ''} | {r.teste_anterior} | {r.n} | {r.efeito} | {fx} | {r.p:.3f} | {r.leitura} |")
    L += ["", "Masters (conjunto): teste das 3 dummies juntas (M2, M3, outras contra M1 = DF/GO); o efeito de cada uma vem ao lado, sem faixa.", ""]
    (AQUI / "resultado_releitura.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(OUT / "releitura_efeito.xlsx") as w:
        pd.DataFrame({"campo": ["O que é", "Como ler", "Aviso"], "descrição": [
            "Releitura dos testes antigos (masters, região, tier, estúdio × renda, mercado de agregador) com a medida de efeito, nos três modelos.",
            "Efeito com faixa de 90%; se a faixa cruza o zero, não dá para separar do acaso. 'Sobrevive à correção' desconta as 8 variáveis por modelo.",
            "Leitura: unidades já vistas e testes já rodados. Efeito não é o mesmo que melhorar a previsão."]}).to_excel(w, sheet_name="LEIA-ME", index=False)
        T.to_excel(w, sheet_name="efeitos", index=False)
    (OUT / "resultado_releitura.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
