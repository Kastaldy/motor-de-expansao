# -*- coding: utf-8 -*-
"""BLK-UNI-00, passo 3: atributos fixos por unidade (1 linha por unidade_id) — dim_unidade.parquet (v2, pos-auditoria).

Blocos (prefixo): (id/flags) | tam_ tamanho | cad_ cadastro | iso_ isocronas | conc_ concorrencia | canib_ sobreposicao
Ultra | cres_ crescimento | poi_ POIs | tp_/wh_ planos | lt_ Lifetime | rampa_ abertura/rampa (explicativas, so' ate a
liberacao) | rampadesc_ descritores de rampa que usam meses POSTERIORES a liberacao (desfecho/descricao, nunca explicativa).
Regras: NaN nunca vira zero; erro de dado mantem a linha, a flag e anula o atributo afetado; nada le o scratchpad da sessao.
Saidas: dim_unidade.parquet, ordem_tiers_totalpass.csv, ordem_tiers_wellhub.csv
"""
import importlib.util
import json
import re
from pathlib import Path

import geopandas as gpd
import h3
import numpy as np
import pandas as pd
import shapely
from shapely import STRtree, wkb
from shapely.geometry import Point

from motor_expansao.dashboard import planos_agregador as pa
from motor_expansao.pipelines.enriquecimento_espacial_hexagonos import REDES_ESTUDIO_BOUTIQUE

UNI = Path(__file__).parent
REPO = UNI.parents[2]
VPS, LOC = UNI / "insumos_vps", UNI / "insumos_locais"
ISO = UNI.parent / "isocronas"


def mod(nome, caminho):
    s = importlib.util.spec_from_file_location(nome, caminho); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


poi = mod("poi06", UNI.parent / "poi" / "06_teste_poi.py")
poi.ISO = ISO  # academias_pontos/ultra_pontos da copia do repo (nao do scratchpad)
ajustes = mod("ajustes", UNI / "_ajustes.py")
poi.OUT = ajustes.POI_DIR  # saidas do teste de POI com as unidades de pino corrigido substituidas

CEN = {"carro_5": ("carro", 300), "carro_10": ("carro", 600), "pe_15": ("pe", 900)}
CENARIOS_ISO = ["carro_5", "carro_10", "pe_15", "circulo_1km"]
PLACEHOLDER_INAUG = pd.Timestamp("2021-08-23")
DEC053_DERIVADA = {"sao-carlos-centro-sp", "vila-izabel-pr", "jardim-das-americas-mt"}  # inauguracao = 1a data da serie
ANOMALIAS_CONFERIR = {"brasilandia-sp": "vale de receita -45% out/25-mai/26 com ativos estaveis", "vila-guilherme-sp": "vale de receita -45% out/25-mai/26 com ativos estaveis",
                      "suzano-sp": "-52% de ativos abr-ago/26 (agregadores 2.964 -> 919)"}
FLAGS = {"lago-sul-df": "isocrona_pe_degenerada (0,16 km2): atributos a pe anulados"}
PINO_ERRADO = set()  # plaza-sul-sp e sagrada-familia-mt corrigidos em 2026-09-28 (06_corrigir_pinos.py)
# O piloto casa a propria Ultra a <= 120 m; aqui 300 m (pino do cadastro fica 130-250 m da linha 'Ultra Academia' do feed em
# 6 unidades; linhas 'ultra academia' sao raras e as unidades distam > 1 km). Distancia gravada em tp/wh_dist_ultra_m.
CASAR_ULTRA_M = 300.0
# Musculacao no Wellhub: vocabulario V2 da DEC-025 sobre `modalidades` (a coluna gravada so' procura 'musculacao' e
# descartava 2.949 academias = 13,35% do feed; medido na auditoria)
MUSC_V2 = re.compile(r"muscula|treino de forca|fisiculturismo|levantamento de peso|treino hibrido")
# Premissa declarada (a mesma do 17_regressao): alunos por cadeia sem dado = 1.800, por independente = 400
ALUNOS_CADEIA_PROXY, ALUNOS_INDEP = 1800, 400


# ------------------------------------------------------------------ concorrencia (copia de 14_aproveitamento_v2, caminhos do repo)
def oferta():
    ac = pd.read_parquet(ISO / "academias_pontos.parquet")
    ac = ac[ac["tipo"] != "cadeia_agregador_com_pin"].reset_index(drop=True)
    cw = pd.read_parquet(VPS / "alunos_reais_por_unidade.parquet")
    cw = cw[(cw.confianca_match == "alta") & (cw.alunos_total > 0)]
    ac["cap_real"] = ac["id"].map(cw.groupby("concorrente_id")["alunos_total"].median())
    ac["cap_rede"] = ac["rede"].map(cw.groupby("rede")["alunos_total"].median())
    ac["classe"] = np.where(ac.cap_real.notna(), "real", np.where(ac.cap_rede.notna(), "mediana_rede", np.where(ac.tipo == "independente_agregador", "indep", "cadeia_proxy")))
    g = gpd.GeoSeries([Point(x, y) for x, y in zip(ac.lng, ac.lat)], crs=4326).to_crs(5880)
    ac["x"] = [p.x for p in g.values]; ac["y"] = [p.y for p in g.values]
    return ac, STRtree(g.values)


def componentes(df, polys5880, ac, tree, auto_m=2.0):
    gp = gpd.GeoSeries([Point(x, y) for x, y in zip(df.lng, df.lat)], crs=4326).to_crs(5880)
    linhas = []
    for uid, pt in zip(df.unidade_id, gp.values):
        o = {"unidade_id": uid}
        for c in CEN:
            p = polys5880[c].get(uid)
            if p is None:
                continue
            sub = ac.iloc[tree.query(p, predicate="contains")]
            sub = sub[np.hypot(sub.x - pt.x, sub.y - pt.y) >= auto_m]
            o[f"conc_cap_real__{c}"] = float(sub.cap_real.fillna(0).sum())
            o[f"conc_cap_rede__{c}"] = float(sub.loc[sub.classe == "mediana_rede", "cap_rede"].sum())
            o[f"conc_n_cadeia_proxy__{c}"] = int((sub.classe == "cadeia_proxy").sum())
            o[f"conc_n_indep__{c}"] = int((sub.classe == "indep").sum())
        linhas.append(o)
    return pd.DataFrame(linhas)


# ------------------------------------------------------------------ rampa
def _estabiliza(s, tol):
    """1o mes de vida m >= 1 que inicia 3 meses seguidos (m, m+1, m+2) com |var| <= tol (var do mes m contra m-1)."""
    for m in sorted(k for k in s.index if k >= 1):
        tr = [s.get(m + i, np.nan) for i in range(3)]
        if all(np.isfinite(tr)) and all(abs(v) <= tol for v in tr):
            return int(m)
    return None


def rampa(f):
    rows = []
    for uid, g in f.groupby("unidade_id"):
        g = g.sort_values("competencia")
        ina = g.inauguracao_competencia.dropna()
        ina = None if (not len(ina) or g.flag_inauguracao_placeholder.any()) else ina.iat[0]
        comp = g.dropna(subset=["mes_vida"]).set_index("mes_vida")
        completo = lambda k: k in comp.index and bool(comp.mes_completo.get(k, False))
        val = lambda k, col: comp[col].get(k, np.nan) if completo(k) else np.nan
        obs = ina is not None and ina >= "2022-04" and completo(1)
        o = {"unidade_id": uid, "rampa_observavel": obs}
        if obs:
            c12 = str(pd.Period(ina, "M") + 12)
            for k in (1, 3, 6, 12):
                o[f"rampa_ativos_m{k}"] = val(k, "ativos"); o[f"rampa_recorrentes_m{k}"] = val(k, "pagantes"); o[f"rampa_agregadores_m{k}"] = val(k, "agregadores")
                cheio = completo(k) and bool(comp.operacao_mes_cheio.get(k, False))
                o[f"rampa_faturamento_fin_m{k}"] = comp.faturamento.get(k, np.nan) if cheio else np.nan
            o["rampa_pct_agregador_ativos_m1"] = val(1, "pct_agregador_ativos"); o["rampa_pct_agregador_ativos_m12"] = val(12, "pct_agregador_ativos")
            o["rampa_pct_agregador_receita_m12_fin"] = val(12, "pct_agregador_receita_fin")
            o["rampa_pct_m3_sobre_m12"] = o["rampa_ativos_m3"] / o["rampa_ativos_m12"] if o["rampa_ativos_m12"] else np.nan
            o["rampa_cresc_m1_m3"] = o["rampa_ativos_m3"] / o["rampa_ativos_m1"] - 1 if o["rampa_ativos_m1"] else np.nan
            o["rampa_novos_alunos_m0"] = comp.novos_alunos.get(0, np.nan); o["rampa_novos_alunos_m1"] = val(1, "novos_alunos"); o["rampa_vendas_m0"] = comp.vendas.get(0, np.nan)
            var = comp.var_ativos_pct
            m = _estabiliza(var, 0.05)
            o["rampa_tempo_estabilizar"] = m
            fim = None
            if m is not None:
                tri = g[g.mes_vida.isin([m, m + 1, m + 2])]
                pat = tri.ativos.mean(); fim = tri.competencia.max()
                o["rampa_patamar_ativos"] = pat; o["rampa_competencia_fim_patamar"] = fim
                o["rampa_velocidade_inicial"] = o["rampa_ativos_m3"] / pat if pat else np.nan
            o["rampa_competencia_liberacao"] = str(pd.Period(max(x for x in (c12, fim) if x), "M") + 1)
            r12 = g[g.mes_vida.between(1, 12) & g.mes_completo]
            if len(r12):
                i = r12.pagantes.idxmax(); o["rampa_mes_pico_recorrentes"] = r12.mes_vida[i]
                o["rampa_queda_recorrentes_pico_ate_m12"] = o["rampa_recorrentes_m12"] / r12.pagantes[i] - 1 if np.isfinite(o["rampa_recorrentes_m12"]) else np.nan
                o["rampa_conversao_mediana_m1_m12"] = r12.conversao_pct.median()
            o["rampa_churn_pct_m12"] = val(12, "churn_pct")
            o["rampa_churn_mediana_m6_m12"] = g.loc[g.mes_vida.between(6, 12) & g.mes_completo, "churn_pct"].median()
            # ---- descritores que olham ALEM da liberacao (nunca explicativa; ver dicionario)
            o["rampadesc_estabilizou_ate_hoje"] = m is not None
            o["rampadesc_meses_observados"] = int(g.loc[g.mes_completo, "mes_vida"].max()) if g.mes_completo.any() else np.nan
            o["rampadesc_tempo_estabilizar_tol10"] = _estabiliza(var, 0.10); o["rampadesc_tempo_estabilizar_tol3"] = _estabiliza(var, 0.03)
            gf = g[g.origem_faturamento.eq("financeiro") & g.operacao_mes_cheio & g.faturamento.notna()]
            vf = pd.Series(gf.faturamento.to_numpy(float), index=gf.mes_vida.to_numpy())
            vf = pd.Series(vf.to_numpy() / vf.reindex(vf.index - 1).to_numpy() - 1, index=vf.index)
            o["rampadesc_tempo_estabilizar_faturamento"] = _estabiliza(vf, 0.05)
            if fim is not None:
                dep = g[(g.competencia > fim) & g.mes_completo]
                if len(dep):
                    mx, mn = dep.ativos.max() / o["rampa_patamar_ativos"] - 1, dep.ativos.min() / o["rampa_patamar_ativos"] - 1
                    o["rampadesc_var_pos_patamar_max"], o["rampadesc_var_pos_patamar_min"] = mx, mn
                    o["rampadesc_formato_pos_patamar"] = ("oscila" if (mn < -0.10 and mx > 0.10) else "patamar_e_queda" if mn < -0.10
                                                          else "patamar_e_novo_crescimento" if mx > 0.10 else "rampa_e_patamar")
                else:
                    o["rampadesc_formato_pos_patamar"] = "sem_meses_pos_patamar"
            else:
                o["rampadesc_formato_pos_patamar"] = "censurada"
        rows.append(o)
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ planos
def ordem_tiers(p):
    t = p.groupby("plano").preco.agg(preco_modal=lambda s: s.mode().iat[0] if s.notna().any() else np.nan, n="size", nunique="nunique").reset_index()
    assert (t["nunique"] <= 1).all(), "plano com mais de um preco: parar e revisar"
    t["ordinal"] = t.preco_modal.rank(method="dense")
    t.loc[t.preco_modal.isna(), "ordinal"] = 0
    return t.sort_values("ordinal")


def planos(D, polys, fonte, status_base):
    p = pd.read_parquet(VPS / f"planos_{fonte}.parquet")
    ordem = ordem_tiers(p)
    ordem.to_csv(UNI / f"ordem_tiers_{fonte}.csv", sep=";", encoding="utf-8-sig", index=False)
    p["ordinal"] = p.plano.map(ordem.set_index("plano").ordinal)
    p["e_ultra"] = pa._e_ultra(p.nome)
    rx = pa.padrao_de_redes(REDES_ESTUDIO_BOUTIQUE)
    p["estudio"] = p.nome.map(lambda n: bool(re.search(rx, pa._sem_acento(n)))) if rx else False
    musc = p.modalidades.fillna("").map(lambda m: bool(MUSC_V2.search(pa._sem_acento(m)))) if fonte == "wellhub" else p.musculacao.fillna(False).astype(bool)
    taxa = (float(p.musculacao.mean()), float(musc.mean()))
    ul = p[p.e_ultra].reset_index(drop=True)
    conc = p[~p.e_ultra & ~p.estudio & musc].reset_index(drop=True)
    pre = "tp" if fonte == "totalpass" else "wh"
    cand = []
    for uid, a, b in zip(D.unidade_id, D.lat.astype(float), D.lng.astype(float)):
        if np.isfinite(a) and np.isfinite(b) and len(ul):
            d = pa._distancias_m(a, b, ul.lat.to_numpy(float), ul.lng.to_numpy(float)); j = int(np.argmin(d)); cand.append((d[j], uid, j))
    usado, casa, dist = set(), {}, {}
    for d, uid, j in sorted(cand):
        dist[uid] = d
        if d <= CASAR_ULTRA_M and j not in usado:
            casa[uid] = j; usado.add(j)
    rows = []
    for uid in D.unidade_id:
        j = casa.get(uid)
        o = {"unidade_id": uid, f"{pre}_dist_ultra_m": dist.get(uid, np.nan), f"{pre}_plano_ultra": ul.plano[j] if j is not None else None,
             f"{pre}_preco_ultra": ul.preco[j] if j is not None else np.nan, f"{pre}_ord_ultra": ul.ordinal[j] if j is not None else np.nan}
        g = polys.get(uid)
        o[f"{pre}_status_c10"] = "sem_poligono" if g is None else status_base.get(uid, "ok")
        if g is not None:
            dentro = conc[shapely.contains_xy(g, conc.lng.to_numpy(float), conc.lat.to_numpy(float))]
            cp = dentro[dentro.preco.notna()]
            o[f"{pre}_n_conc_c10"] = len(dentro); o[f"{pre}_n_conc_com_preco_c10"] = len(cp)
            if len(cp) >= 3:
                o[f"{pre}_ord_mediana_c10"] = cp.ordinal.median(); o[f"{pre}_preco_mediana_c10"] = cp.preco.median()
                u = o[f"{pre}_ord_ultra"]
                if np.isfinite(u) and u > 0:
                    o[f"{pre}_pct_acima_ultra_c10"] = (cp.ordinal > u).mean(); o[f"{pre}_pct_mesmo_ultra_c10"] = (cp.ordinal == u).mean()
                    o[f"{pre}_pct_abaixo_ultra_c10"] = (cp.ordinal < u).mean(); o[f"{pre}_gap_ord_c10"] = u - o[f"{pre}_ord_mediana_c10"]
        rows.append(o)
    r = pd.DataFrame(rows)
    r[f"{pre}_data_coleta"] = f"{p.data_coleta.min()}..{p.data_coleta.max()}"
    print(f"{fonte}: musculacao coluna gravada {taxa[0]:.3f} -> usada {taxa[1]:.3f} | Ultra casada {len(casa)} (entre 120 e 300 m: {sum(120 < dist[u] <= CASAR_ULTRA_M for u in casa)})", flush=True)
    return r


# ------------------------------------------------------------------ main
def main():
    D = pd.read_parquet(UNI / "depara_unidade.parquet")
    D["inauguracao"] = pd.to_datetime(D.inauguracao)
    D["flag_inauguracao_placeholder"] = D.inauguracao.eq(PLACEHOLDER_INAUG)
    D["inauguracao_origem"] = np.where(D.unidade_id.isin(DEC053_DERIVADA), "derivada_serie (DEC-053)", np.where(D.flag_inauguracao_placeholder, "placeholder", "cadastro_growth"))
    up = ajustes.ultra_pontos()[["unidade_id", "lat", "lng", "confianca", "origem_coord", "pin_cadastro"]]
    D = D.merge(up, on="unidade_id", how="left").rename(columns={"confianca": "confianca_coord"})
    D["flag_erro_dado"] = D.unidade_id.map(FLAGS)
    D.loc[D.flag_erro_dado.isna() & D.confianca_coord.isin(["baixa", "nenhuma"]), "flag_erro_dado"] = "coord_baixa"
    D.loc[D.unidade_id.isin(PINO_ERRADO), "confianca_coord"] = "baixa"
    D["anomalia_conferir"] = D.unidade_id.map(ANOMALIAS_CONFERIR)
    D["pino_corrigido"] = D.unidade_id.map(pd.read_parquet(ajustes.CORR / "ultra_pontos_corrigidos.parquet").set_index("unidade_id").fonte)
    D["hex_id_res7"] = [h3.latlng_to_cell(a, b, 7) if np.isfinite(a) else None for a, b in zip(D.lat.astype(float), D.lng.astype(float))]
    geo = set()
    # ---- tamanho (xlsx: SO' Metragem e Vagas; a demografia GeoFusion fica fora, regra da spec)
    xl = pd.read_excel(LOC / "dados_academias.xlsx", sheet_name="Plan1").set_index("LOCALIZACAO")
    D["tam_metragem_m2"] = D.localizacao_xlsx.map(xl["Metragem"]); D["tam_vagas"] = D.localizacao_xlsx.map(xl["Vagas "])
    D["tam_vagas_por_1000m2"] = 1000 * D.tam_vagas / D.tam_metragem_m2
    D["tipo_imovel"] = None; D["fachada"] = None  # sem fonte para a Ultra (so' em_shopping, via POI)
    # ---- cadastro: so' os campos usados (sem franqueado/consultor/master_franquia; life_time/ltv sao desfecho)
    cad = json.load(open(VPS / "cadastro_unidades_campos_usados.json", encoding="utf-8"))["unidades"]
    D["cad_preco_gold"] = D.unidade_id.map(lambda u: pd.to_numeric(cad.get(u, {}).get("gold"), errors="coerce"))
    D["cad_tier_wellhub"] = D.unidade_id.map(lambda u: cad.get(u, {}).get("wellhub"))
    D["cad_tier_totalpass"] = D.unidade_id.map(lambda u: cad.get(u, {}).get("totalpass"))
    for m in ("piscina", "studios", "bike", "lutas", "pilates"):
        D[f"cad_mod_{m}"] = D.unidade_id.map(lambda u: (cad.get(u, {}).get("modalidades") or {}).get(m))
    # ---- isocronas (base_ultra) e oferta mapeada
    bu = ajustes.base_ultra().drop_duplicates("unidade_id").set_index("unidade_id")
    for c in CENARIOS_ISO:
        for v in ["pop", "renda_pc", "domicilios", "area_km2", "km_rua", "truncada", "oferta_ponderada", "n_academias", "n_cadeia_mapeada", "n_independente_agregador", "n_ultra"]:
            col = f"{v}__{c}"
            if col in bu.columns:
                D[f"iso_{col}"] = D.unidade_id.map(bu[col]); geo.add(f"iso_{col}")
        if f"pop__{c}" in bu.columns:
            D[f"iso_dens_hab_km2__{c}"] = D[f"iso_pop__{c}"] / D[f"iso_area_km2__{c}"]; geo.add(f"iso_dens_hab_km2__{c}")
    D["iso_metro"] = D.unidade_id.map(bu["metro"]); D["iso_snap_dist_m"] = D.unidade_id.map(bu["snap_dist_m"]); geo |= {"iso_metro", "iso_snap_dist_m"}
    # ---- poligonos Ultra
    iso = ajustes.poligonos_ultra(["ponto_id", "tipo", "modo", "limite_s", "truncada", "poligono_wkb"])
    P4326, P5880, trunc = {c: {} for c in CEN}, {c: {} for c in CEN}, {}
    for c, (modo, lim) in CEN.items():
        s = iso[(iso.modo == modo) & (iso.limite_s == lim) & iso.poligono_wkb.notna()].drop_duplicates("ponto_id")
        gs = gpd.GeoSeries([wkb.loads(b) for b in s.poligono_wkb], crs=4326)
        P4326[c] = dict(zip(s.ponto_id, gs.values)); P5880[c] = dict(zip(s.ponto_id, gs.to_crs(5880).values))
        if c == "carro_10":
            trunc = dict(zip(s.ponto_id, s.truncada))
    # ---- concorrencia com alunos reais (foto de hoje)
    ac, tree = oferta()
    comp = componentes(D[D.lat.notna()][["unidade_id", "lat", "lng"]], P5880, ac, tree)
    D = D.merge(comp, on="unidade_id", how="left"); geo |= {c for c in comp.columns if c.startswith("conc_")}
    for c in CEN:
        alunos = D[f"conc_cap_real__{c}"] + D[f"conc_cap_rede__{c}"] + D[f"conc_n_cadeia_proxy__{c}"] * ALUNOS_CADEIA_PROXY + D[f"conc_n_indep__{c}"] * ALUNOS_INDEP
        D[f"conc_alunos_por_mil_hab__{c}"] = 1000 * alunos / D[f"iso_pop__{c}"].where(D[f"iso_pop__{c}"] > 0); geo.add(f"conc_alunos_por_mil_hab__{c}")
    # ---- canibalizacao estatica
    cb = ajustes.base_canibal()
    lado = pd.concat([cb.rename(columns={"a": "u", "frac_a": "frac"})[["u", "limite_min", "frac"]], cb.rename(columns={"b": "u", "frac_b": "frac"})[["u", "limite_min", "frac"]]])
    tem_pol = D.unidade_id.isin(P4326["carro_10"].keys())
    for lim in sorted(lado.limite_min.unique()):
        g = lado[lado.limite_min == lim].groupby("u").frac
        D[f"canib_frac_max__carro_{int(lim)}"] = D.unidade_id.map(g.max()).where(~tem_pol, D.unidade_id.map(g.max()).fillna(0))
        D[f"canib_n_pares__carro_{int(lim)}"] = D.unidade_id.map(g.size()).where(~tem_pol, D.unidade_id.map(g.size()).fillna(0))
        geo |= {f"canib_frac_max__carro_{int(lim)}", f"canib_n_pares__carro_{int(lim)}"}
    # ---- crescimento: municipio pelo universo COMPLETO (brasil_estrutural), fallback por nome da cidade do cadastro
    cm = pd.read_parquet(VPS / "crescimento_municipal.parquet")
    ch = pd.read_parquet(VPS / "crescimento_hex.parquet").set_index("hex_id")
    est = pd.read_parquet(REPO / "data" / "staging" / "brasil_estrutural.parquet", columns=["hex_id", "cod_municipio", "nome_municipio"]).drop_duplicates("hex_id").set_index("hex_id")
    D["cres_cod6"] = D.hex_id_res7.map(est.cod_municipio.astype(str).str[:6])
    D["cres_nome_municipio_hex"] = D.hex_id_res7.map(est.nome_municipio)
    norm = lambda s: pa._sem_acento(s).upper().strip()
    D["cres_municipio_origem"] = np.where(D.cres_cod6.notna(), "hex_estrutural", None)
    if "cres_chave_nome" in cm.columns:
        nome2cod = cm.dropna(subset=["cres_chave_nome"]).drop_duplicates("cres_chave_nome").set_index("cres_chave_nome").cod6
        chave_cad = D.uf + "|" + D.cidade_cadastro.fillna("").map(norm)
        via_nome = D.cres_cod6.isna() & chave_cad.isin(nome2cod.index)
        D.loc[via_nome, "cres_cod6"] = chave_cad[via_nome].map(nome2cod)
        D.loc[via_nome, "cres_municipio_origem"] = "nome_cadastro"
    D["cres_municipio_diverge_cadastro"] = D.cidade_cadastro.notna() & D.cres_nome_municipio_hex.notna() & (D.cidade_cadastro.fillna("").map(norm) != D.cres_nome_municipio_hex.fillna("").map(norm))
    cmi = cm.set_index("cod6")
    for c in ("dim_media", "dim_renda_pct", "dim_pop_pct", "dim_empresas_por1k", "dim_emprego_pct", "dim_predios_pct", "cres_confiab"):
        if c in cmi.columns:
            D[c if c.startswith("cres_") else f"cres_{c}"] = D.cres_cod6.map(cmi[c])
    for c in ("cres_hex_taxa", "cres_hex_classe"):
        if c in ch.columns:
            D[c] = D.hex_id_res7.map(ch[c])
    geo |= {c for c in D.columns if c.startswith("cres_")}
    # ---- POI
    ok = D.lat.notna() & D.unidade_id.isin(set(bu.index))
    Dp = D[ok]
    Pf, _ = poi.familias("ultra_v2", Dp.unidade_id.tolist(), Dp.unidade_id.map(bu["pop__pe_15"]).to_numpy(float),
                         Dp.unidade_id.map(bu["pop__carro_10"]).to_numpy(float), Dp.lat.to_numpy(float), Dp.lng.to_numpy(float))
    Pf = Pf.drop(columns=["metro"]).add_prefix("poi_").reset_index().rename(columns={"ponto_id": "unidade_id"})
    D = D.merge(Pf, on="unidade_id", how="left"); geo |= {c for c in D.columns if c.startswith("poi_")}
    # ---- planos (status: truncada / coord_baixa entram como marca; contagem pode estar subestimada)
    status = {u: ("truncada" if trunc.get(u) else "ok") for u in P4326["carro_10"]}
    for u in D.loc[D.confianca_coord.isin(["baixa", "nenhuma"]), "unidade_id"]:
        if u in status:
            status[u] = "coord_baixa"
    for fonte in ("totalpass", "wellhub"):
        r = planos(D, P4326["carro_10"], fonte, status)
        D = D.merge(r, on="unidade_id", how="left"); geo |= {c for c in r.columns if c.endswith("_c10")}
    for pre, col, fonte in (("tp", "cad_tier_totalpass", "totalpass"), ("wh", "cad_tier_wellhub", "wellhub")):
        ordem = pd.read_csv(UNI / f"ordem_tiers_{fonte}.csv", sep=";").set_index("plano").ordinal
        mapa_o = {str(k).upper(): v for k, v in ordem.items()}
        chave = D[col].fillna("").str.upper().str.replace(r"^TP\s*", "TP ", regex=True).str.strip()
        nao = D[col].fillna("").str.upper().str.startswith("N")
        D[f"{pre}_ord_ultra_cadastro"] = chave.map(mapa_o).where(~nao)
        D[f"{pre}_tem_agregador_cadastro"] = pd.Series(np.where(D[col].isna(), None, ~nao), index=D.index, dtype=object)
    # ---- Lifetime
    lt = pd.read_parquet(LOC / "unidade_para_motor.parquet")
    assert lt.FONTE_SCORES.dropna().str.startswith("vintage:").all()
    cod2 = lambda x: str(x).strip().upper().zfill(2) if str(x).strip().isdigit() else str(x).strip().upper()
    lt["cod2"] = lt.COD_UNIDADE.map(cod2)
    dl = pd.read_csv(UNI / "depara_lifetime.csv", sep=";", dtype=str).dropna(subset=["unidade_id"])
    lt = lt.merge(dl[["cod2", "unidade_id"]], on="cod2", how="inner")
    assert not lt.unidade_id.duplicated().any()
    lt = lt.set_index("unidade_id")
    mapa = {"COD_UNIDADE": "lt_cod_unidade", "SNAPSHOT_SCORES": "lt_snapshot_scores", "FONTE_SCORES": "lt_fonte_scores", "EB_RETENCAO_60D": "lt_eb_retencao_60d",
            "EB_CHURN_60D": "lt_eb_churn_60d", "EB_CHURN_60D_IC90_LO": "lt_eb_churn_60d_ic90_lo", "EB_CHURN_60D_IC90_HI": "lt_eb_churn_60d_ic90_hi",
            "EB_PESO_DADO_PROPRIO": "lt_eb_peso_dado_proprio", "EB_METODO": "lt_eb_metodo", "EB_SNAPSHOT_FIT": "lt_eb_snapshot_fit", "EB_NOWCAST_FIM": "lt_eb_nowcast_fim",
            "PROB_CANCEL_90D_MEDIA": "lt_prob_cancel_90d_media", "PROB_CANCEL_90D_P50": "lt_prob_cancel_90d_p50",
            "E_MESES_ATIVOS_12M_MEDIANO": "lt_e_meses_ativos_12m_mediano", "LTV_PROSPECTIVO_12M_MEDIANO": "lt_ltv_prospectivo_12m_mediano",
            "CONFIABILIDADE_UNIDADE": "lt_confiabilidade", "USAR_PROB_ABSOLUTA": "lt_usar_prob_absoluta", "USAR_RANKING": "lt_usar_ranking",
            "TEM_PERFIL_VINTAGE": "lt_tem_perfil_vintage", "N_ALUNOS": "lt_n_alunos_pontuados"}
    for a, b in mapa.items():
        if a in lt.columns:
            D[b] = D.unidade_id.map(lt[a])
    if {"PCT_ALTO_90D", "PCT_CRITICO_90D"} <= set(lt.columns):
        D["lt_pct_risco_alto_critico_90d"] = D.unidade_id.map(lt.PCT_ALTO_90D + lt.PCT_CRITICO_90D)
    eb = pd.read_parquet(LOC / "unidade_retencao_eb_v1.parquet")
    if "COD_UNIDADE" in eb.columns:
        eb["cod2"] = eb.COD_UNIDADE.map(cod2)
        eb = eb.merge(dl[["cod2", "unidade_id"]], on="cod2", how="inner").drop_duplicates("unidade_id").set_index("unidade_id")
        for a, b in (("FAIXA_MATURIDADE", "lt_eb_faixa_maturidade"), ("TAXA_CRUA_60D", "lt_eb_taxa_crua_60d"), ("N", "lt_eb_n_fit")):
            if a in eb.columns:
                D[b] = D.unidade_id.map(eb[a])
    D.loc[~D.lt_usar_ranking.eq("Sim"), ["lt_prob_cancel_90d_media", "lt_prob_cancel_90d_p50", "lt_pct_risco_alto_critico_90d"]] = np.nan
    D["lt_prob_90d_uso"] = np.where(D.lt_eb_retencao_60d.isna(), "sem_lifetime", np.where(D.lt_usar_prob_absoluta.eq("Sim"), "absoluto", np.where(D.lt_usar_ranking.eq("Sim"), "so_ranking", "nao_usar")))
    # ---- rampa
    f = pd.read_parquet(UNI / "fato_unidade_mes.parquet")
    D = D.merge(rampa(f), on="unidade_id", how="left")
    ini = f[f.origem_faturamento.eq("financeiro") & f.faturamento.gt(0)].groupby("unidade_id").competencia.min()
    D["rampa_mes_inicio_faturamento_fin"] = D.unidade_id.map(ini)
    D["rampa_delta_inicio_meses"] = [(pd.Period(a, "M") - pd.Period(b, "M")).n if isinstance(a, str) and isinstance(b, str) else np.nan
                                     for a, b in zip(D.rampa_mes_inicio_faturamento_fin, D.inauguracao.dt.to_period("M").astype(str).where(D.inauguracao.notna()))]
    D["rampa_patamar_por_m2"] = D.rampa_patamar_ativos / D.tam_metragem_m2
    for c in ("rampa_ret12_coorte_m0_vs_m3a11_pp", "rampa_n_alunos_prevenda", "rampa_ret12_prevenda_vs_m0_pp"):
        D[c] = np.nan  # PENDENTE: exige export agregado por unidade do Projeto Lifetime (base aluno a aluno)
    D["ultima_competencia"] = D.unidade_id.map(f.groupby("unidade_id").competencia.max())
    D["serie_encerrada"] = D.ultima_competencia < f.competencia.max()
    # ---- erros de dado: anula o que a flag compromete
    geo_cols = sorted(c for c in geo if c in D.columns)
    pe_cols = [c for c in D.columns if "pe_15" in c or c in ("poi_F1", "poi_F2", "poi_F3", "poi_F1_all", "poi_F2_all", "poi_F2b", "poi_frac_exato_F2", "poi_em_shopping", "poi_n_mall", "poi_n_estacao", "poi_n_hiper")]
    for c in set(geo_cols) | set(pe_cols):
        if D[c].dtype == bool:
            D[c] = D[c].astype("boolean")  # booleano anulavel: o erro de dado vira NA, nao False
    D.loc[D.unidade_id.isin(PINO_ERRADO), geo_cols] = np.nan
    D.loc[D.unidade_id.eq("lago-sul-df"), pe_cols] = np.nan
    D = D.drop(columns=["nomes_crus"]).sort_values(["excluida_rede", "uf", "unidade_id"]).reset_index(drop=True)
    D.to_parquet(UNI / "dim_unidade.parquet", index=False)
    print(f"dim_unidade: {D.shape} | " + str({p: sum(c.startswith(p) for c in D.columns) for p in ("tam_", "cad_", "iso_", "conc_", "canib_", "cres_", "poi_", "tp_", "wh_", "lt_", "rampa_", "rampadesc_")}))


if __name__ == "__main__":
    main()
