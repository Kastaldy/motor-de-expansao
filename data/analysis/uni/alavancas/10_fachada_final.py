# -*- coding: utf-8 -*-
"""Fachada — teste FINAL com a planilha completa do Juan (protocolo_fachada.md v1.3, congelado em 2026-09-30 antes das notas
restantes). Leitura principal: 'loja de rua' (poi_em_shopping == False), sem Botafogo, so' nas unidades novas do Juan que
NINGUEM tinha visto (fora as 14 notas da leitura parcial e as 6 de controle). 'Confirma' se o IC 90% do Spearman nota x
residuo (faturamento acima do previsto pelo M0, mesma regra do 08) excluir zero com sinal positivo. Reporta tambem as outras
amostras. Nenhuma exclusao por desempenho. .venv, PYTHONPATH=src.
Uso: 10_fachada_final.py <planilha_completa_do_juan.xlsx>"""
import hashlib
import importlib.util
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

AQUI = Path(__file__).resolve().parent
UNI = AQUI.parent
COL = UNI / "coleta_metragem"
PARCIAL = COL / "planilha_fachada_juan_2026-09-29_parcial.xlsx"
COPIA = COL / "planilha_fachada_juan_2026-09-30_completa.xlsx"


def mod(nome, p):
    s = importlib.util.spec_from_file_location(nome, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def notas_juan(arq):
    j = pd.read_excel(arq, sheet_name="Juan")
    col = "Notas" if "Notas" in j.columns and j["Notas"].notna().any() else "nota_fachada_1a5"
    return j[j[col].notna()].set_index("unidade_id")[col].astype(float), col, j


def main():
    arq = Path(sys.argv[1])
    if not COPIA.exists():
        shutil.copy2(arq, COPIA)
    assert sha(arq) == sha(COPIA), "a copia datada difere da planilha informada"
    m08 = mod("m08", AQUI / "08_fachada_juan.py")
    nota_j, col, jj = notas_juan(COPIA)
    vistos = set(notas_juan(PARCIAL)[0].index)
    cal_ids = set(pd.read_csv(COL / "_gabarito_nao_abrir" / "fachada_juan_calibracao.csv", sep=";", encoding="utf-8-sig").unidade_id)
    t = m08.cons.ler(); t = t[t.nota_fachada_1a5.notna()]
    nota_fv = t.groupby("unidade_id").nota_fachada_1a5.mean()
    conc = pd.DataFrame({"juan": nota_j[nota_j.index.isin(cal_ids)], "felipe_vini": nota_fv.reindex([u for u in nota_j.index if u in cal_ids])})
    n_dif = int((conc.juan - conc.felipe_vini).abs().gt(1).sum())
    novas = nota_j[~nota_j.index.isin(cal_ids) & (nota_j.index != "botafogo-rj")]
    nao_vistas = novas[~novas.index.isin(vistos)]
    todas = pd.concat([nota_fv.drop(index=["botafogo-rj"], errors="ignore"), novas])
    _, d = m08.ex.carregar()
    shop = d.poi_em_shopping.reindex(sorted(set(todas.index)))
    rua = set(shop[shop.eq(False)].index); sem_info = set(shop[shop.isna()].index)
    R = m08.residuos(sorted(set(todas.index)))
    rng = np.random.default_rng(20261010)

    def D(s):
        return pd.DataFrame({"nota": s}).join(R, how="inner")
    amostras = [
        ("**PRINCIPAL — novas não vistas, loja de rua**", nao_vistas[nao_vistas.index.isin(rua)]),
        ("novas não vistas, com shopping", nao_vistas),
        ("todas as novas do Juan, loja de rua", novas[novas.index.isin(rua)]),
        ("todas as novas do Juan, com shopping", novas),
        ("todas as notas (Felipe, Vini e Juan), loja de rua", todas[todas.index.isin(rua)]),
        ("todas as notas (Felipe, Vini e Juan), com shopping", todas),
    ]
    L = ["# Fachada — teste final com a planilha completa do Juan (protocolo v1.3)", "",
         f"Planilha: `{COPIA.name}` (SHA-256 `{sha(COPIA)[:16]}…`), coluna `{col}`: {len(nota_j)} notas de {len(jj)} linhas "
         f"({int(nota_j.index.isin(cal_ids).sum())} de controle; {len(novas)} novas; {len(nao_vistas)} novas que ninguém tinha visto). "
         f"Protocolo `protocolo_fachada.md` (SHA-256 `{sha(AQUI / 'protocolo_fachada.md')[:16]}…`). Botafogo fora (decisão do Felipe).",
         f"Shopping (`poi_em_shopping`): loja de rua {len(rua)}, em shopping {int(shop.eq(True).sum())}, sem informação {len(sem_info)} (ficam fora das amostras 'loja de rua').",
         "**Concordância nas unidades de controle** (Juan × média Felipe/Vini): " + "; ".join(f"{u} {r.juan:g} × {r.felipe_vini:g}" for u, r in conc.iterrows()) +
         f". Diferença de mais de 1 ponto em {n_dif} de {len(conc)} (regra: 3 ou mais → réguas diferentes; a leitura principal já é dentro do avaliador).", "",
         "| amostra | N | Spearman nota × faturamento acima do previsto | IC 90% | inclinação | leitura |", "|---|---|---|---|---|---|"]
    res = {}
    for nome, s in amostras:
        n, rho, lo, hi, sl, leit = m08.teste(D(s), rng)
        res[nome] = leit
        L.append(f"| {nome} | {n} | {rho:+.2f} | [{lo:+.2f}; {hi:+.2f}] | {100 * (np.exp(sl) - 1):+.0f}% por ponto | **{leit}** |" if n >= 6 else f"| {nome} | {n} | – | – | – | sem amostra |")
    Dt = D(todas)
    L += ["", "Faturamento acima/abaixo do previsto por nota (todas, sem Botafogo): " +
          "; ".join(f"nota {k:g}: {100 * (np.exp(v.residuo.mean()) - 1):+.0f}% (n={len(v)})" for k, v in Dt.assign(nr=Dt.nota.round()).groupby("nr")) + ".", "",
          "| unidade (novas não vistas) | loja de rua | origem | nota | faturou vs. previsto |", "|---|---|---|---|---|"]
    for u, r in D(nao_vistas).sort_values("residuo").iterrows():
        L.append(f"| {u} | {'sim' if u in rua else ('não' if u not in sem_info else '?')} | {r.origem} | {r.nota:g} | {100 * (np.exp(r.residuo) - 1):+.0f}% |")
    L += ["", f"**Leitura principal (v1.3): {res[amostras[0][0]].upper()}.**"]
    (AQUI / "resultado_fachada_final.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
