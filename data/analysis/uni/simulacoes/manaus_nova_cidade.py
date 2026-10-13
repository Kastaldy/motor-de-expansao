# -*- coding: utf-8 -*-
"""Simulacao pontual (2026-09-30, pedido do Felipe): unidade com estudio, 2.000 m2, aluguel R$ 80 mil, obra R$ 2,5 mi,
equipamentos R$ 1,5 mi financiados em 60x a 2% a.m., plano cheio R$ 167, no pino NOVA CIDADE MANAUS
(data/staging/unidades_ultra_mapeadas.parquet). v2 de trabalho (praca + estudios + master) + faixa do UNI-07.
APROXIMACAO DECLARADA: sem osmium no .venv (o venv-iso esta bloqueado pelo Windows), a isocrona de 10 min de carro vira
um CIRCULO de area equivalente (p25/p50/p75 das isocronas da rede); calibrado contra as isocronas reais das 39 de treino.
.venv, PYTHONPATH=src."""
import importlib.util
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point

from motor_expansao.dimensionamento import config as cfg
from motor_expansao.dimensionamento.simulador import Premissas, simular

AQUI = Path(__file__).resolve().parent
UNI = AQUI.parent
REPO = UNI.parent.parent.parent
SC = Path(r"C:\Users\Felipe\AppData\Local\Temp\claude\C--dev-motor-de-expansao\9259d0a1-7dda-49bd-a390-c88f3d4ac1a6\scratchpad")


def mod(nome, p):
    s = importlib.util.spec_from_file_location(nome, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


i04 = mod("i04", SC / "iso" / "04_atributos.py")
u7 = mod("u7", UNI / "uni07" / "01_incerteza.py")
ex, alav, c5 = u7.ex, u7.alav, u7.c5
X_ = u7.X_
BASE = ["l_m2", "l_renda", "l_pop"]
PIN = dict(lat=-3.03514, lng=-59.996833)
M2, ALUGUEL, OBRA, EQUIP, PRAZO, JUROS, TICKET = 2000.0, 80_000.0, 2_500_000.0, 1_500_000.0, 60, 0.02, 167.0


def attrs_circulo(lat, lng, raio_km, ctx):
    p = gpd.GeoSeries([Point(lng, lat)], crs=4326).to_crs(5880).iloc[0]
    return i04.atributos_poligono(p.buffer(raio_km * 1000), ctx, (p.x, p.y))


def setores_no_bbox(mtr):
    """Copia do i04.setores_no_bbox lendo cada arquivo com ParquetFile (o pyarrow do .venv falha ao juntar a coluna 'uf'
    com a chave de particao 'uf=' do caminho). Mesmas colunas, filtros e transformacoes."""
    import pyarrow.parquet as pq
    from shapely import wkb
    cols = ["cod_setor", "geometry_wkb", "pop_total_setor_2022", "domicilios_particulares_ocupados_setor_2022",
            "renda_per_capita_setor_2022_calibrada", "renda_per_capita_setor_2022", "flag_geometria_valida", "bbox_minx", "bbox_miny", "bbox_maxx", "bbox_maxy"]
    frames = []
    for ufdir in i04.GEO.glob("uf=*"):
        for mdir in ufdir.glob("cod_municipio=*"):
            f = next(mdir.glob("*.parquet"), None)
            if f is None:
                continue
            pf = pq.ParquetFile(f)
            bb = pf.read(columns=["bbox_minx", "bbox_miny", "bbox_maxx", "bbox_maxy"]).to_pandas()
            if bb.empty or bb["bbox_maxx"].max() < mtr["lng_min"] or bb["bbox_minx"].min() > mtr["lng_max"] or bb["bbox_maxy"].max() < mtr["lat_min"] or bb["bbox_miny"].min() > mtr["lat_max"]:
                continue
            nomes = pf.schema_arrow.names
            df = pf.read(columns=[c for c in cols if c in nomes]).to_pandas()
            if "flag_geometria_valida" not in df:
                df["flag_geometria_valida"] = True
            df = df[(df["bbox_maxx"] >= mtr["lng_min"]) & (df["bbox_minx"] <= mtr["lng_max"]) & (df["bbox_maxy"] >= mtr["lat_min"]) & (df["bbox_miny"] <= mtr["lat_max"])]
            frames.append(df)
    s = pd.concat(frames, ignore_index=True)
    s = s[s["flag_geometria_valida"].fillna(True)]
    g = gpd.GeoDataFrame(s.drop(columns=["geometry_wkb"]), geometry=[wkb.loads(x) for x in s["geometry_wkb"]], crs=4674).to_crs(5880)
    g["renda"] = g["renda_per_capita_setor_2022_calibrada"].fillna(g["renda_per_capita_setor_2022"])
    g["area"] = g.geometry.area
    g["rp"] = g.geometry.representative_point()
    return g.reset_index(drop=True)


def contexto(lat, lng, margem=0.2):
    mtr = dict(lat_min=lat - margem, lat_max=lat + margem, lng_min=lng - margem, lng_max=lng + margem)
    g = setores_no_bbox(mtr)
    vazio = pd.DataFrame({"lat": [], "lng": [], "tipo": []})
    return i04.Contexto(g, vazio, vazio)


def sim(fat, ticket, estudio=True, com_equip=True):
    al = c5.alunos_de(fat)  # alunos pela receita por aluno do simulador no ticket padrao (a demanda da v2)
    p = Premissas(ticket_cheio=float(ticket), share_balcao=cfg.SIM_SHARE_BALCAO, aluguel_mes=ALUGUEL,
                  alunos_inicial=float(c5.RAMPA_OBS[0] * al), maturacao_meses=int(c5.RAMPA_OBS[1]),
                  outros_fixos_mes=float(cfg.SIM_OUTROS_FIXOS_MES) + (float(cfg.SIM_CUSTO_STUDIO) if estudio else 0.0))
    kw = dict(equipamentos=EQUIP, prazo_equipamentos=PRAZO, juros_equipamentos_am=JUROS) if com_equip else {}
    r = simular(float(al), p, obra=OBRA, **kw)
    pb = r.payback_meses if np.isfinite(r.payback_meses) else 61
    fat_mad = p.faturamento(al, com_anuidade=True)
    return dict(alunos=al, fat_maduro=fat_mad, margem=r.margem_ebitda_pct, payback=min(pb, 61), viavel=bool(r.flag_viavel))


def main():
    f, d = ex.carregar()
    A = alav.atributos_ext(d)
    mid = pd.read_csv(UNI / "alavancas" / "master_id_cadastro.csv", sep=";", dtype=str)
    A["master_id"] = d.cod_cadastro.map(mid.assign(c=mid.cod_cadastro.str.zfill(2)).set_index("c").master_id).reindex(A.index)
    Y25, Y26 = ex.desfechos(f, "2025-01", "2025-12"), ex.desfechos(f, "2026-01", "2026-08")
    tr = A.join(Y25, how="inner").dropna(subset=["l_fat"] + BASE + ["frac_indep", "studios", "master_id"])
    amb = tr.index.intersection(Y26.index); cal = float(np.median(Y26.loc[amb, "l_fat"] - Y25.loc[amb, "l_fat"]))
    cont = tr.master_id.value_counts(); proprios = sorted(m for m, n in cont.items() if n >= 4 and m != "M1")
    for m in proprios:
        tr[f"mr_{m}"] = (tr.master_id == m).astype(float)
    tr["mr_outras"] = (~tr.master_id.isin(["M1"] + proprios)).astype(float)
    V2 = BASE + [f"mr_{m}" for m in proprios] + ["mr_outras", "studios"]
    b = np.linalg.lstsq(X_(tr, V2), tr.l_fat.to_numpy(float), rcond=None)[0]
    b0 = np.linalg.lstsq(X_(tr, BASE), tr.l_fat.to_numpy(float), rcond=None)[0]
    # residuos LOO do treino (faixa adotada no UNI-07)
    ev = pd.read_csv(UNI / "uni07" / "erros_fora_da_amostra.csv", sep=";", encoding="utf-8-sig", index_col=0)
    rtr = ev.loc[ev.grupo == "treino", "residuo"].to_numpy()
    ql, qm, qh = np.quantile(rtr, [0.10, 0.50, 0.90])

    # --- calibracao da aproximacao: circulo de raio 4,97 km x isocrona real, nas 39 de treino
    L = ["# Simulação — unidade em Manaus (pino NOVA CIDADE MANAUS), v2 de trabalho", "",
         "**Aproximação declarada:** a isócrona de 10 min de carro foi trocada por um círculo de área equivalente (o `osmium` não está no ambiente "
         "que funciona). Calibração abaixo.", ""]
    raz = []
    for u in tr.index:
        la, lo = d.lat.get(u), d.lng.get(u)
        if pd.isna(la):
            continue
        ctx = contexto(la, lo, margem=0.12)
        a = attrs_circulo(la, lo, 4.97, ctx)
        raz.append((u, a["pop"] / d.iso_pop__carro_10[u], a["renda_pc"] / d.iso_renda_pc__carro_10[u],
                    float(X_(pd.DataFrame({"l_m2": [tr.l_m2[u]], "l_renda": [np.log(a["renda_pc"])], "l_pop": [np.log(a["pop"])]}), BASE) @ b0) - float(X_(tr.loc[[u]], BASE) @ b0)))
    R = pd.DataFrame(raz, columns=["u", "pop", "renda", "dprev"]).set_index("u")
    L += [f"- Nas {len(R)} unidades de treino, o círculo de 5 km contra a isócrona real: população ×{R['pop'].median():.2f} (p10 ×{R['pop'].quantile(.1):.2f}, p90 ×{R['pop'].quantile(.9):.2f}); "
          f"renda ×{R.renda.median():.2f} (p10 ×{R.renda.quantile(.1):.2f}, p90 ×{R.renda.quantile(.9):.2f}); "
          f"efeito na previsão de faturamento do M0: mediana {100 * (np.exp(R.dprev.median()) - 1):+.0f}%, erro típico {100 * np.median(np.abs(np.exp(R.dprev) - 1)):.0f}%.", ""]

    # --- Manaus
    ctx = contexto(PIN["lat"], PIN["lng"])
    L += ["## Praça (área a ~10 min de carro, aproximada por círculo)", "", "| raio (área) | população | renda per capita | dentro da faixa da rede? |", "|---|---|---|---|"]
    praca = {}
    for rot, rk in (("4,2 km (isócrona pequena, p25)", 4.2), ("5,0 km (típica, p50)", 4.97), ("5,8 km (grande, p75)", 5.83)):
        a = attrs_circulo(PIN["lat"], PIN["lng"], rk, ctx)
        praca[rot] = a
        dentro = (d.iso_pop__carro_10.min() <= a["pop"] <= d.iso_pop__carro_10.max()) and (d.iso_renda_pc__carro_10.min() <= a["renda_pc"] <= d.iso_renda_pc__carro_10.max())
        L.append(f"| {rot} | {a['pop']:,.0f} | R$ {a['renda_pc']:,.0f} | {'sim' if dentro else 'NÃO (extrapolação)'} |")
    L += ["", f"Rede (isócrona real de 10 min): população mediana {d.iso_pop__carro_10.median():,.0f}, renda mediana R$ {d.iso_renda_pc__carro_10.median():,.0f}.", ""]

    # --- previsao v2 (estudio = 1; master desconhecida -> 'outras'; sensibilidade por master)
    L += ["## Previsão da v2 (faturamento maduro mensal, nível 2026)", "", "| praça | master | previsto | faixa p10 · p50 · p90 |", "|---|---|---|---|"]
    prev_central = None
    for rot, a in praca.items():
        for mrot, dm in (("desconhecida → 'outras'", {"mr_outras": 1.0}), ("como M1 (DF/GO)", {}), ("como M2 (matriz)", {"mr_M2": 1.0}), ("como M3", {"mr_M3": 1.0})):
            row = {"l_m2": np.log(M2), "l_renda": np.log(a["renda_pc"]), "l_pop": np.log(a["pop"]), "studios": 1.0, **{f"mr_{m}": 0.0 for m in proprios}, "mr_outras": 0.0}
            row.update(dm)
            p = float(X_(pd.DataFrame([row]), V2) @ b) + cal
            if rot.startswith("5,0") and mrot.startswith("desconhecida"):
                prev_central = p
            if rot.startswith("5,0") or mrot.startswith("desconhecida"):
                L.append(f"| {rot} | {mrot} | R$ {np.exp(p) / 1000:,.0f} mil | {np.exp(p + ql) / 1000:,.0f} · {np.exp(p + qm) / 1000:,.0f} · {np.exp(p + qh) / 1000:,.0f} mil |")
    fat_c = float(np.exp(prev_central))
    # --- viabilidade (simulador de producao)
    L += ["", "## Viabilidade (simulador de produção; praça típica, master desconhecida)", "",
          f"Premissas: aluguel R$ {ALUGUEL:,.0f}; obra R$ {OBRA:,.0f}; equipamentos R$ {EQUIP:,.0f} em {PRAZO}x a {100 * JUROS:.0f}% a.m.; estúdio (+R$ {cfg.SIM_CUSTO_STUDIO:,.0f}/mês); "
          f"balcão {cfg.SIM_SHARE_BALCAO:.0%}, agregador a {cfg.SIM_TICKET_AGREGADOR_FATOR:.0%} do ticket; rampa observada {c5.RAMPA_OBS}.", "",
          "| cenário | ticket | alunos maduros | faturamento maduro | margem EBITDA | payback (meses) | viável? |", "|---|---|---|---|---|---|---|"]
    for crot, fator in (("pessimista (p10)", np.exp(ql)), ("central (p50)", np.exp(qm)), ("otimista (p90)", np.exp(qh))):
        for tk, trot in ((137.0, "R$ 137 (média da rede, como o modelo aprendeu)"), (TICKET, "R$ 167 declarado (conta: mesma demanda)")):
            s = sim(fat_c * fator, tk)
            pbt = '>60' if s['payback'] >= 61 else f"{s['payback']:.0f}"
            L.append(f"| {crot} | {trot} | {s['alunos']:,.0f} | R$ {s['fat_maduro'] / 1000:,.0f} mil | {100 * s['margem']:.0f}% | {pbt} | {'sim' if s['viavel'] else 'não'} |")
    for tk in (137.0, TICKET):
        ch = np.mean([sim(fat_c * np.exp(e), tk)["viavel"] for e in rtr])
        L.append(f"")
        L.append(f"**Chance de ser viável com ticket R$ {tk:.0f}: {100 * ch:.0f}%** (39 erros do treino aplicados à previsão central).")
    # faturamento necessario para viabilidade
    lo_f, hi_f = 100e3, 1.5e6
    for _ in range(40):
        mid_ = (lo_f + hi_f) / 2
        if sim(mid_, TICKET)["viavel"]:
            hi_f = mid_
        else:
            lo_f = mid_
    L += ["", f"Para ser viável (margem ≥ 30% e payback ≤ 36) com esses custos e ticket R$ 167, a demanda precisa equivaler a ~R$ {hi_f / 1000:,.0f} mil/mês no nível que o modelo prevê "
          f"(~{c5.alunos_de(hi_f):,.0f} alunos maduros) — {100 * (hi_f / fat_c - 1):+.0f}% acima da previsão central.", ""]
    (AQUI / "resultado_manaus_nova_cidade.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
