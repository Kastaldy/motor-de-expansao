# -*- coding: utf-8 -*-
"""Coleta agregada de vendas por unidade x mes (Growth API /relatorio-vendas-operacoes), para o estudo de preco.

LGPD: a resposta traz nome, cod_aluno e usuario. Essas colunas sao descartadas logo depois da chamada, antes de
qualquer outra operacao; so' contagens e estatisticas de valor por unidade x mes x produto sao gravadas. O caminho
com cache em disco do cliente (_get_historico) NAO e' usado. Rate limit 10 req/5 min respeitado pelo cliente.
Rodar com PYTHONPATH=src. Saida: precos/vendas_unidade_mes.parquet.
"""
import sys
import warnings
from pathlib import Path

import pandas as pd

from motor_expansao.dimensionamento.growth_api_client import GrowthAPIClient

warnings.filterwarnings("ignore")
AQUI = Path(__file__).resolve().parent
PII = ["nome", "cod_aluno", "usuario"]
CHEIO = (80.0, 200.0)  # faixa de preco de tabela do GOLD mensal (abaixo = promocao; acima = multi-mes)


def moda(s):
    s = s.round(2)
    return float(s.mode().iloc[0]) if len(s) else float("nan")


def agregar(d, comp):
    d = d.drop(columns=[c for c in PII if c in d.columns])
    d["valor"] = pd.to_numeric(d.valor, errors="coerce")
    d["dv"] = pd.to_datetime(d.data_venda, dayfirst=True, errors="coerce")
    fora = int((d.dv.dt.strftime("%Y-%m") != comp).sum())
    rec = d[d.tipo_produto == "RECORRENTE"]
    linhas = []
    for u, h in rec.groupby("unidade"):
        gold = h[h.produto == "GOLD"]
        cheio = gold[gold.valor.between(*CHEIO)]
        promo = gold[gold.valor < CHEIO[0]]
        linhas.append(dict(unidade=u, competencia=comp, n_recorrente=len(h), receita_recorrente=float(h.valor.sum()),
                           n_gold=len(gold), n_gold_cheio=len(cheio), n_gold_promo=len(promo), n_gold_multimes=int((gold.valor > CHEIO[1]).sum()),
                           preco_gold_moda=moda(cheio.valor), preco_gold_mediana=float(cheio.valor.median()) if len(cheio) else float("nan"),
                           preco_gold_max=float(cheio.valor.max()) if len(cheio) else float("nan"),
                           promo_moda=moda(promo.valor), n_studio=int(h.produto.str.contains("STUDIO", na=False).sum()),
                           n_goldpro=int((h.produto == "GOLDPRO").sum()), preco_goldpro_moda=moda(h[(h.produto == "GOLDPRO") & h.valor.between(80, 300)].valor)))
    tot = d.groupby("unidade").size().rename("n_vendas_total")
    out = pd.DataFrame(linhas)
    if not out.empty:
        out = out.merge(tot, left_on="unidade", right_index=True, how="left")
    return out, len(d), fora


def main():
    ini = sys.argv[1] if len(sys.argv) > 1 else "2023-01"
    fim = sys.argv[2] if len(sys.argv) > 2 else "2026-08"
    meses = pd.period_range(ini, fim, freq="M")
    c = GrowthAPIClient()
    partes, log = [], []
    for p in meses:
        di, df = p.start_time.strftime("%Y-%m-%d"), p.end_time.strftime("%Y-%m-%d")
        try:
            d = pd.DataFrame(c._request("GET", "/relatorio-vendas-operacoes", params={"data_inicio": di, "data_fim": df}) or [])
        except Exception as e:  # noqa: BLE001
            log.append(f"{p}: ERRO {type(e).__name__} {str(e)[:120]}"); print(log[-1], flush=True); continue
        if d.empty:
            log.append(f"{p}: vazio"); print(log[-1], flush=True); continue
        a, n, fora = agregar(d, str(p))
        del d
        partes.append(a)
        log.append(f"{p}: {n} vendas, {a.unidade.nunique()} unidades, fora da janela {fora}")
        print(log[-1], flush=True)
        pd.concat(partes, ignore_index=True).to_parquet(AQUI / "vendas_unidade_mes.parquet", index=False)
    (AQUI / "coleta_log.txt").write_text("\n".join(log) + "\n", encoding="utf-8")
    print("fim", flush=True)


if __name__ == "__main__":
    main()
