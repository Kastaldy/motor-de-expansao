# -*- coding: utf-8 -*-
"""Fontes ajustadas do painel UNI-00 (um lugar so', lido por 01-05).

financeiro(): planilha do Financeiro ingerida pelo proprio motor (rede_faturamento_financeiro.ler_planilha) a partir da
    versao baixada por Felipe em 2026-09-28 — a copia da VPS (ingerida em 2026-09-08) tinha 1 celula velha (Guaruja ago/26,
    R$ 547.745 contra R$ 217.525,74 na planilha atual; as outras 6.527 celulas identicas). Corta no ultimo mes FECHADO
    (a coluna do mes aberto vem 0,00 enquanto e' preenchida — regra do proprio modulo do motor).
Pinos corrigidos (06_corrigir_pinos.py): plaza-sul-sp e sagrada-familia-mt — pino, poligonos, atributos, canibalizacao e POI.
"""
from pathlib import Path

import pandas as pd

UNI = Path(__file__).parent
ISO = UNI.parent / "isocronas"
CORR = UNI / "correcoes_pinos"
FIN_ARQ = UNI / "insumos_locais" / "faturamento_financeiro_2026-09-28.parquet"
FIN_ULTIMO_MES_FECHADO = "2026-08"
POI_DIR = UNI / "poi_painel"


def financeiro():
    f = pd.read_parquet(FIN_ARQ)
    return f[f.competencia <= FIN_ULTIMO_MES_FECHADO].reset_index(drop=True)


def corrigidas():
    return set(pd.read_parquet(CORR / "ultra_pontos_corrigidos.parquet").unidade_id)


def ultra_pontos():
    up = pd.read_parquet(ISO / "ultra_pontos.parquet")
    c = pd.read_parquet(CORR / "ultra_pontos_corrigidos.parquet").set_index("unidade_id")
    k = up.unidade_id.isin(c.index)
    for col in ("lat", "lng", "confianca", "origem_coord"):
        up.loc[k, col] = up.loc[k, "unidade_id"].map(c[col]).to_numpy()
    return up


def poligonos_ultra(colunas):
    base = pd.concat([pd.read_parquet(p, columns=colunas, filters=[("tipo", "==", "ultra")]) for p in sorted((ISO / "poligonos_v2").glob("metro_*.parquet"))])
    base = base[~base.ponto_id.isin(corrigidas())]
    novo = pd.read_parquet(CORR / "poligonos_corrigidos.parquet", columns=colunas)
    return pd.concat([base, novo], ignore_index=True)


def base_ultra():
    bu = pd.read_parquet(ISO / "testes_v2" / "base_ultra.parquet")
    novo = pd.read_parquet(CORR / "base_ultra_linhas_corrigidas.parquet")
    bu = bu[~bu.unidade_id.isin(set(novo.unidade_id))]
    return pd.concat([bu, novo.reindex(columns=bu.columns)], ignore_index=True)


def base_canibal():
    cb = pd.read_parquet(ISO / "testes_v2" / "base_canibal.parquet")
    c = corrigidas()
    cb = cb[~cb.a.isin(c) & ~cb.b.isin(c)]
    return pd.concat([cb, pd.read_parquet(CORR / "canibal_pares_corrigidos.parquet")], ignore_index=True)
