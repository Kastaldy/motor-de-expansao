# -*- coding: utf-8 -*-
"""BLK-UNI-00, passo 2: fato unidade x mes (v2, com as correcoes da auditoria de 2026-09-26).

Base: rede_metricas.fechamento_mensal (codigo do motor) sobre a Growth, com o faturamento FECHADO do Financeiro.
Regras aplicadas aqui:
  - RECEITA SO' DO FINANCEIRO: onde origem_faturamento != 'financeiro' (mes aberto, unidade sem Financeiro) as colunas de
    receita ficam NaN; o valor da Growth vai so' para faturamento_growth_auditoria (regra 5 do epic).
  - Zero do Financeiro com ativos > 0 = mes sem lancamento, NAO receita zero: NaN + flag_receita (16 casos medidos).
  - Correcao manual declarada (Guaruja ago/26): faturamento corrigido; tudo que o motor derivou do total dobrado vira NaN.
  - Inauguracao placeholder (23/08/2021, 4 unidades da matriz de SP): mes_vida NaN; mes_vida_minimo = meses desde o
    1o faturamento > 0 no Financeiro (limite inferior da idade).
  - Canibalizacao no tempo: outra Ultra conta so' a partir da inauguracao dela; 0 (nao NaN) quando ha isocrona e nenhuma
    vizinha aberta; NaN se uma vizinha aberta nao tem ativos no mes. plaza-sul-sp (pino errado) fica fora como origem e
    como vizinha.
Saida: data/analysis/uni/fato_unidade_mes.parquet
"""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import shapely
from shapely import wkb

from motor_expansao.dashboard import rede_faturamento_financeiro as rf
from motor_expansao.dashboard import rede_metricas as rm

UNI = Path(__file__).parent
VPS = UNI / "insumos_vps"
ISO = UNI.parent / "isocronas"
s = importlib.util.spec_from_file_location("d01", UNI / "01_depara.py"); d01 = importlib.util.module_from_spec(s); s.loader.exec_module(d01)
s_aj = importlib.util.spec_from_file_location("ajustes", Path(__file__).parent / "_ajustes.py"); ajustes = importlib.util.module_from_spec(s_aj); s_aj.loader.exec_module(ajustes)
# Guaruja ago/26: nao e' mais correcao manual — a planilha atual do Financeiro ja' traz R$ 217.525,74 (a copia da VPS estava velha)
CORRECOES = {}
PLACEHOLDER_INAUG = pd.Timestamp("2021-08-23")
PINO_ERRADO = set()  # plaza-sul-sp e sagrada-familia-mt tiveram o pino corrigido (06_corrigir_pinos.py)
RECEITA_DO_MOTOR = ["faturamento", "faturamento_sem_agregador", "faturamento_agregador", "receita_por_recorrente", "pct_agregador_receita"]
FIN_COLS = ["fin_faturamento", "fin_vendas_ux", "fin_gympass", "fin_totalpass", "fin_tem_saude"]


def financeiro_componentes(fin, catalogo):
    por_nome = {rm._sem_acento(n): uid for uid, u in catalogo.items() for n in u.nomes_crus}
    resg = rm._resgate_por_aperto(por_nome, fin["unidade_ux"])
    fin = fin.assign(unidade_id=fin["unidade_ux"].map(lambda n: por_nome.get(rm._sem_acento(n)) or resg.get(n)))
    cols = [c for c in ("faturamento", "vendas_ux", "gympass", "totalpass", "tem_saude") if c in fin.columns]
    g = fin[fin.unidade_id.notna()].groupby(["unidade_id", "competencia"], as_index=False)[cols].sum(min_count=1)
    return g.rename(columns={c: f"fin_{c}" for c in cols})


def canibalizacao(f, up):
    iso = ajustes.poligonos_ultra(["ponto_id", "tipo", "modo", "limite_s", "poligono_wkb"])
    iso = iso[(iso.modo == "carro") & (iso.limite_s == 600) & iso.poligono_wkb.notna() & ~iso.ponto_id.isin(PINO_ERRADO)].drop_duplicates("ponto_id")
    up = up[~up.unidade_id.isin(PINO_ERRADO)]
    pol = {r.ponto_id: wkb.loads(r.poligono_wkb) for r in iso.itertuples()}
    viz = [(uid, o) for uid, g in pol.items() for o in up.unidade_id[shapely.contains_xy(g, up.lng.to_numpy(float), up.lat.to_numpy(float))] if o != uid]
    V = pd.DataFrame(viz, columns=["unidade_id", "outra"])
    ina = f.groupby("unidade_id").inauguracao.first()
    at = f.set_index(["unidade_id", "competencia"]).ativos
    m = f[["unidade_id", "competencia"]].merge(V, on="unidade_id", how="left")
    m["aberta"] = m.outra.notna() & (pd.to_datetime(m.outra.map(ina)).dt.to_period("M").astype(str) <= m.competencia)
    m["ativos_outra"] = [at.get((o, c), np.nan) if a else 0.0 for o, c, a in zip(m.outra, m.competencia, m.aberta)]
    r = m.groupby(["unidade_id", "competencia"]).agg(n_ultra_outras_abertas__carro_10=("aberta", "sum"),
                                                     ativos_ultra_outras__carro_10=("ativos_outra", lambda s: s.sum() if s.notna().all() else np.nan))
    r = r.reset_index()
    r["tem_isocrona_carro_10"] = r.unidade_id.isin(pol.keys())
    r.loc[~r.tem_isocrona_carro_10, ["n_ultra_outras_abertas__carro_10", "ativos_ultra_outras__carro_10"]] = np.nan
    return r


def main():
    raw = pd.read_parquet(VPS / "growth_api_historico.parquet")
    base = rm.preparar_base(raw)
    fin = ajustes.financeiro()
    fin["unidade_ux"] = fin["unidade_ux"].replace(d01.ALIAS_FINANCEIRO)
    f = rm.fechamento_mensal(base, financeiro=fin)
    print(f"fechamento: {f.shape}, financeiro aplicado em {f.attrs.get('financeiro_aplicado')} linhas, sem par: {f.attrs.get('financeiro_sem_par')}")
    f["competencia"] = f["competencia"].astype(str)
    f = f.merge(financeiro_componentes(fin, rm.catalogo_de(base)), on=["unidade_id", "competencia"], how="left")
    f["faturamento_original"] = f["faturamento"]
    f["flag_receita"] = None
    f["correcao_manual"] = None
    # receita so' do Financeiro
    ux = ~f.origem_faturamento.eq("financeiro")
    f["faturamento_growth_auditoria"] = f.faturamento.where(ux)
    f.loc[ux, RECEITA_DO_MOTOR] = np.nan
    f.loc[ux, "flag_receita"] = "sem_financeiro_neste_mes"
    # zero do Financeiro com academia operando
    z = f.origem_faturamento.eq("financeiro") & f.faturamento.eq(0) & f.ativos.gt(0)
    f.loc[z, RECEITA_DO_MOTOR + FIN_COLS] = np.nan
    f.loc[z, "flag_receita"] = "financeiro_zero_com_ativos (mes sem lancamento)"
    # correcoes manuais
    for (u, c), (v, motivo) in CORRECOES.items():
        k = (f.unidade_id == u) & (f.competencia == c)
        assert k.sum() == 1, (u, c)  # (dicionario vazio hoje; fica o mecanismo)
        f.loc[k, RECEITA_DO_MOTOR + FIN_COLS] = np.nan
        f.loc[k, "faturamento"] = v; f.loc[k, "correcao_manual"] = motivo
    # alias declarado (Sao Carlos): marca as linhas cujo Financeiro so' casou pelo alias
    alias_uid = {"sao-carlos-centro-sp"}
    f.loc[f.unidade_id.isin(alias_uid) & f.origem_faturamento.eq("financeiro"), "flag_receita"] = "financeiro_por_alias_declarado (SÃO CARLOS - SP -> SAO CARLOS - CENTRO - SP)"
    # maturidade
    f["inauguracao"] = pd.to_datetime(f["inauguracao"], errors="coerce")
    f["flag_inauguracao_placeholder"] = f.inauguracao.eq(PLACEHOLDER_INAUG)
    f["inauguracao_competencia"] = f["inauguracao"].dt.to_period("M").astype(str).where(f["inauguracao"].notna())
    f["mes_vida"] = f["meses_operacao"].where(~f.flag_inauguracao_placeholder)
    ini = financeiro_componentes(fin, rm.catalogo_de(base)).query("fin_faturamento > 0").groupby("unidade_id").competencia.min()
    pini = f.unidade_id.map(ini)
    f["mes_vida_minimo"] = [(pd.Period(c, "M") - pd.Period(p, "M")).n if isinstance(p, str) else np.nan for c, p in zip(f.competencia, pini)]
    f.loc[~f.flag_inauguracao_placeholder, "mes_vida_minimo"] = np.nan
    f["pre_inauguracao"] = f["inauguracao_competencia"].notna() & (f["competencia"] < f["inauguracao_competencia"])
    # variacao de ativos contra o mes ANTERIOR (merge), so' entre meses completos
    ant = f[["unidade_id", "competencia", "ativos", "mes_completo"]].copy()
    ant["competencia"] = (pd.PeriodIndex(ant.competencia, freq="M") + 1).astype(str)
    f = f.merge(ant.rename(columns={"ativos": "ativos_mes_anterior", "mes_completo": "mes_completo_anterior"}), on=["unidade_id", "competencia"], how="left")
    ok = f.mes_completo.fillna(False) & f.mes_completo_anterior.fillna(False).astype(bool) & (f.meses_operacao >= 1)
    f["var_ativos_pct"] = np.where(ok, f.ativos / f.ativos_mes_anterior.where(f.ativos_mes_anterior > 0) - 1, np.nan)
    # agregador e receita (definicoes declaradas no dicionario)
    f["pct_agregador_ativos"] = f.agregadores / f.ativos.where(f.ativos > 0)          # estudo de inauguracao: agregadores/ativos (0-1)
    agr = f.fin_gympass.fillna(0) + f.fin_totalpass.fillna(0)
    bruto = f.fin_vendas_ux.fillna(0) + agr
    f["pct_agregador_receita_fin"] = np.where((f.fin_gympass.notna() | f.fin_totalpass.notna()) & (bruto > 0), agr / bruto, np.nan)  # sobre a receita BRUTA (antes do Tem Saude)
    f["pct_tem_saude_fin"] = np.where(f.fin_faturamento > 0, f.fin_tem_saude.fillna(0) / f.fin_faturamento, np.nan)
    cheio = f.mes_completo & f.operacao_mes_cheio & f.origem_faturamento.eq("financeiro")
    f["receita_por_ativo_fin"] = (f.faturamento / f.ativos.where(f.ativos > 0)).where(cheio)
    # canibalizacao no tempo
    up = ajustes.ultra_pontos()[["unidade_id", "lat", "lng"]].dropna()
    f = f.merge(canibalizacao(f, up), on=["unidade_id", "competencia"], how="left")
    # ultima competencia e serie encerrada (vies de sobrevivencia: quem parou de reportar some)
    ult = f.groupby("unidade_id").competencia.max()
    f["ultima_competencia_unidade"] = f.unidade_id.map(ult)
    f["serie_encerrada"] = f.ultima_competencia_unidade < f.competencia.max()
    f = f.sort_values(["unidade_id", "competencia"]).reset_index(drop=True)
    f.to_parquet(UNI / "fato_unidade_mes.parquet", index=False)
    v = f[f.mes_completo & f.operacao_mes_cheio & f.origem_faturamento.eq("financeiro") & f.faturamento.notna()]
    print(f"fato: {f.shape} | {f.unidade_id.nunique()} unidades | {f.competencia.min()}..{f.competencia.max()} | faturamento Financeiro valido (mes cheio): {len(v)} ({v.unidade_id.nunique()} unidades)")
    print(f"flag_receita: {f.flag_receita.value_counts().to_dict()} | canibalizacao >0: {(f.n_ultra_outras_abertas__carro_10 > 0).sum()} | ativos_outras NaN com isocrona: {(f.tem_isocrona_carro_10.fillna(False) & f.ativos_ultra_outras__carro_10.isna()).sum()}")


if __name__ == "__main__":
    main()
