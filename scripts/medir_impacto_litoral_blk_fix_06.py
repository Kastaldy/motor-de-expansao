"""
BLK-FIX-06 / FASE A (MEDICAO) — Impacto do criterio geometrico HIBRIDO no litoral.

NAO toca NENHUM artefato oficial do M1. TUDO em scratch:
  - base H3 scratch: data/staging/brasil_litoral_tmp/uf=XX/hexagonos.parquet (limiar piso 0.15)
  - vetor fracao_terra: data/staging/brasil_litoral_tmp/fracao_terra_descartados.parquet
  - delta caro (0.20 e 0.30): data/staging/brasil_estrutural.0NN.tmp.parquet etc.
  - relatorio: data/reports/base_h3_litoral_impacto.md (+ CSV auxiliar do leque)

Estrategia de eficiencia (plano v2):
  - interseccao poligono x poligono calculada UMA vez por hex hoje-descartado (piso 0.15);
  - o LEQUE {0.15, 0.20, 0.25, 0.30} e re-filtragem barata do vetor de fracao_terra;
  - o DELTA CARO (percentis nacionais + score_priorizacao + top-20%/UF) roda o enriquecimento
    estrutural+priorizacao em SCRATCH apenas para 0.20 e 0.30.

Uso:
    python scripts/medir_impacto_litoral_blk_fix_06.py
"""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd

from motor_expansao.config import settings
from motor_expansao.pipelines.m1.base_h3_brasil import (
    IBGE_MALHA_BRASIL_URL,
    IBGE_MALHAS_UF_URL,
    carregar_geojson,
    construir_geometria_brasil,
    gerar_hexagonos_validos_uf,
    montar_dataframe_hexagonos,
    salvar_particao_uf,
)
from motor_expansao.pipelines.m1.hex_enrichment import (
    enriquecer_hexagonos_uf_estrutural,
    rodar_camada_oportunidade_nacional,
    selecionar_areas_prioritarias,
)
from motor_expansao.pipelines.m1.ibge_censo import IBGECenso

# ── Caminhos de SCRATCH (jamais oficiais) ──────────────────────────────────────
SCRATCH_BASE_ROOT = Path("data/staging/brasil_litoral_tmp")
VEC_PATH = SCRATCH_BASE_ROOT / "fracao_terra_descartados.parquet"
REPORT_PATH = Path("data/reports/base_h3_litoral_impacto.md")
LEQUE_CSV_PATH = Path("data/reports/base_h3_litoral_leque.csv")

OFICIAL_BASE_ROOT = Path("data/staging/brasil")
OFICIAL_ESTRUTURAL = Path("data/staging/brasil_estrutural.parquet")
OFICIAL_PRIORIZADOS = Path("data/staging/brasil_priorizados.parquet")

PISO = 0.15  # menor limiar do leque -> superset de hexes recuperaveis
LEQUE = [0.15, 0.20, 0.25, 0.30]
DELTA_CARO = [0.20, 0.30]  # so estes rodam enriquecimento nacional em scratch

# Repro do litoral (hexes-alvo conhecidos hoje ausentes)
PRAIA_GRANDE_LATLNG = (-24.005, -46.41)
RJ_LITORAL_LATLNG = (-22.97, -43.18)  # orla do Rio de Janeiro (Copacabana approx)


def _t(msg: str, t0: float) -> None:
    print(f"[{time.time() - t0:7.1f}s] {msg}", flush=True)


def regenerar_base_scratch_e_vetor(t0: float) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    """Gera a base H3 scratch no PISO (0.15) e coleta o vetor de fracao_terra.

    Retorna:
      - dict uf -> DataFrame de hexes (centroide-in + recuperados>=0.15) gravado em scratch;
      - DataFrame do vetor (hex_id, uf, lat, lng, fracao_terra) de TODOS os hexes
        hoje-descartados que sobrepoem terra (fracao>0).
    """
    payload_uf = carregar_geojson(IBGE_MALHAS_UF_URL, Path("data/raw/ibge/malha_uf_brasil.geojson"), False)
    payload_br = carregar_geojson(IBGE_MALHA_BRASIL_URL, Path("data/raw/ibge/malha_brasil.geojson"), False)
    from motor_expansao.pipelines.m1.base_h3_brasil import normalizar_features_uf

    feats = normalizar_features_uf(payload_uf)
    brasil = construir_geometria_brasil(payload_br)

    bases_por_uf: dict[str, pd.DataFrame] = {}
    vec_rows: list[dict] = []
    for f in feats:
        uf = f["uf"]
        validos, removidos, recuperados, vec = gerar_hexagonos_validos_uf(
            feature_uf=f,
            brasil_geom=brasil,
            resolucao=settings.H3_RESOLUTION,
            land_fraction_min=PISO,
            coletar_fracao_terra=True,
        )
        df_uf = montar_dataframe_hexagonos(hex_ids=validos, uf=uf, regiao=f["regiao"])
        salvar_particao_uf(df=df_uf, output_root=SCRATCH_BASE_ROOT, uf=uf)
        bases_por_uf[uf] = df_uf
        for hex_id, frac in vec:
            import h3

            lat, lng = h3.cell_to_latlng(hex_id)
            vec_rows.append(
                {"hex_id": hex_id, "uf": uf, "lat": lat, "lng": lng, "fracao_terra": float(frac)}
            )
        _t(f"base scratch {uf}: validos={len(validos)} removidos(<{PISO})={removidos} recup(>= {PISO})={recuperados}", t0)

    vec_df = pd.DataFrame(vec_rows, columns=["hex_id", "uf", "lat", "lng", "fracao_terra"])
    VEC_PATH.parent.mkdir(parents=True, exist_ok=True)
    vec_df.to_parquet(VEC_PATH, index=False)
    _t(f"vetor fracao_terra salvo: {len(vec_df)} hexes em {VEC_PATH}", t0)
    return bases_por_uf, vec_df


def enriquecer_recuperados(vec_df: pd.DataFrame, t0: float) -> pd.DataFrame:
    """Enriquece estruturalmente APENAS os hexes recuperados (set pequeno).

    Anexa renda_per_capita / pop_total / populacao_proxy aos hexes do vetor para
    a massa demografica do leque (barato; nao roda enriquecimento nacional).
    """
    censo = IBGECenso()
    frames = []
    for uf, grp in vec_df.groupby("uf", sort=True):
        df_hex = grp[["hex_id", "uf", "lat", "lng"]].copy()
        df_hex["regiao"] = ""
        out = enriquecer_hexagonos_uf_estrutural(
            df_hex_uf=df_hex, uf=uf, censo=censo, refresh_demografia=False, refresh_malha=False
        )
        cols = ["hex_id", "renda_per_capita", "pop_total", "populacao_proxy"]
        cols = [c for c in cols if c in out.columns]
        frames.append(out[cols])
        _t(f"enriquecido recuperados {uf}: {len(out)} hexes", t0)
    enr = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
        columns=["hex_id", "renda_per_capita", "pop_total", "populacao_proxy"]
    )
    return vec_df.merge(enr, on="hex_id", how="left")


def montar_tabela_leque(vec_enr: pd.DataFrame) -> pd.DataFrame:
    """Tabela do leque: por limiar L, hexes que entram + massa demografica."""
    rows = []
    for L in LEQUE:
        entra = vec_enr[vec_enr["fracao_terra"] >= L]
        por_uf = entra.groupby("uf").size().to_dict()
        por_uf_str = ", ".join(f"{uf}:{n}" for uf, n in sorted(por_uf.items()))
        rows.append(
            {
                "limiar_L": L,
                "hexes_entram_total": int(len(entra)),
                "hexes_por_uf": por_uf_str,
                "soma_pop_total": round(float(entra["pop_total"].fillna(0).sum()), 1),
                "soma_populacao_proxy": round(float(entra["populacao_proxy"].fillna(0).sum()), 1),
                "renda_media_entram": round(float(entra["renda_per_capita"].fillna(0).mean()), 2)
                if len(entra)
                else 0.0,
            }
        )
    return pd.DataFrame(rows)


def _quartis_fracao(vec_enr: pd.DataFrame, L: float) -> dict:
    s = vec_enr[vec_enr["fracao_terra"] >= L]["fracao_terra"]
    if s.empty:
        return {}
    return {
        "n": int(len(s)),
        "min": round(float(s.min()), 4),
        "q25": round(float(s.quantile(0.25)), 4),
        "mediana": round(float(s.median()), 4),
        "q75": round(float(s.quantile(0.75)), 4),
        "max": round(float(s.max()), 4),
    }


def construir_base_scratch_para_limiar(vec_df: pd.DataFrame, limiar: float, t0: float) -> Path:
    """Materializa uma base H3 scratch para `limiar` derivando do PISO (0.15).

    base(L) = base_piso(0.15) MENOS os hexes recuperados com fracao_terra < L.
    Le as particoes scratch do piso, remove os hex_id a excluir, grava em novo root.
    """
    root_l = Path(f"data/staging/brasil_litoral_tmp_{int(round(limiar * 100)):03d}")
    excluir = set(vec_df[vec_df["fracao_terra"] < limiar]["hex_id"])
    for part in sorted(SCRATCH_BASE_ROOT.glob("uf=*/hexagonos.parquet")):
        uf = part.parent.name.split("=", 1)[1]
        df = pd.read_parquet(part)
        if excluir:
            df = df[~df["hex_id"].isin(excluir)].reset_index(drop=True)
        salvar_particao_uf(df=df, output_root=root_l, uf=uf)
    _t(f"base scratch limiar={limiar}: root={root_l} (excluidos {len(excluir)} hexes < {limiar})", t0)
    return root_l


def rodar_enriquecimento_scratch(input_root: Path, limiar: float, t0: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Roda estrutural + priorizacao em SCRATCH (sem BI exports, sem paths oficiais).

    Retorna (df_estrutural_scratch, df_priorizados_scratch).
    """
    tag = f"{int(round(limiar * 100)):03d}"
    out_estrutural = Path(f"data/staging/brasil_estrutural.{tag}.tmp.parquet")
    out_priorizados = Path(f"data/staging/brasil_priorizados.{tag}.tmp.parquet")
    out_oportunidades = Path(f"data/staging/hexagonos_brasil_oportunidades.{tag}.tmp.parquet")
    tmp_root = Path(f"data/staging/brasil_estrutural_tmp_{tag}")

    censo = IBGECenso()
    from motor_expansao.pipelines.m1.hex_enrichment import (
        _garantir_nomes_municipio,
        _listar_particoes_brasil,
        _salvar_particao_uf,
        calcular_hex_score_estrutural,
    )

    particoes = _listar_particoes_brasil(input_root)
    paths_tmp = []
    for uf, path in particoes:
        df_hex_uf = pd.read_parquet(path)
        df_estr = enriquecer_hexagonos_uf_estrutural(
            df_hex_uf=df_hex_uf, uf=uf, censo=censo, refresh_demografia=False, refresh_malha=False
        )
        paths_tmp.append(_salvar_particao_uf(df_estr, tmp_root, uf))
    df_total = pd.concat([pd.read_parquet(p) for p in paths_tmp], ignore_index=True)
    df_total = calcular_hex_score_estrutural(df_total)
    df_total = _garantir_nomes_municipio(df_total)
    df_total = df_total.sort_values("hex_score_estrutural", ascending=False).reset_index(drop=True)
    out_estrutural.parent.mkdir(parents=True, exist_ok=True)
    df_total.to_parquet(out_estrutural, index=False)
    _t(f"estrutural scratch limiar={limiar}: {len(df_total)} hexes -> {out_estrutural}", t0)

    df_prior, _ = selecionar_areas_prioritarias(
        df_estrutural=df_total, top_pct_por_uf=settings.M1_PRIORIZACAO_TOP_PCT_POR_UF
    )
    df_prior.to_parquet(out_priorizados, index=False)
    _t(f"priorizados scratch limiar={limiar}: {len(df_prior)} hexes -> {out_priorizados}", t0)

    # Camada de oportunidade em SCRATCH (percentis nacionais consistentes); todos paths .tmp
    rodar_camada_oportunidade_nacional(
        input_estrutural_path=out_estrutural,
        input_priorizados_path=out_priorizados,
        output_base_path=out_oportunidades,
        output_top_brasil_csv=Path(f"data/staging/top_hexagonos_brasil.{tag}.tmp.csv"),
        output_top_uf_csv=Path(f"data/staging/top_hexagonos_por_uf.{tag}.tmp.csv"),
        output_dashboard_path=Path(f"data/staging/hexagonos_brasil_dashboard_base.{tag}.tmp.parquet"),
        report_path=Path(f"data/reports/camada_oportunidade_fase1.{tag}.tmp.md"),
    )
    return df_total, df_prior


def calcular_delta(df_oficial: pd.DataFrame, df_novo: pd.DataFrame, limiar: float) -> dict:
    """Delta de percentis nacionais + score_priorizacao para os hexes EXISTENTES."""
    cols = [
        "hex_id",
        "renda_pct_nacional",
        "pop_pct_nacional",
        "score_priorizacao",
    ]
    a = df_oficial[[c for c in cols if c in df_oficial.columns]].copy()
    b = df_novo[[c for c in cols if c in df_novo.columns]].copy()
    m = a.merge(b, on="hex_id", how="inner", suffixes=("_old", "_new"))
    out = {"limiar": limiar, "hexes_existentes_comparados": int(len(m))}
    for c in ["renda_pct_nacional", "pop_pct_nacional", "score_priorizacao"]:
        if f"{c}_old" in m.columns and f"{c}_new" in m.columns:
            d = (m[f"{c}_new"] - m[f"{c}_old"]).abs()
            out[f"delta_{c}_min"] = round(float(d.min()), 4)
            out[f"delta_{c}_mediana"] = round(float(d.median()), 4)
            out[f"delta_{c}_max"] = round(float(d.max()), 4)
    if "score_priorizacao_old" in m.columns and "score_priorizacao_new" in m.columns:
        d = (m["score_priorizacao_new"] - m["score_priorizacao_old"]).abs()
        out["score_n_muda_alem_0p5"] = int((d > 0.5).sum())
        out["score_pct_muda_alem_0p5"] = round(float((d > 0.5).mean() * 100), 4)
        out["score_maior_deslocamento_abs"] = round(float(d.max()), 4)
    return out


def calcular_delta_top20(df_prior_oficial: pd.DataFrame, df_prior_novo: pd.DataFrame, limiar: float) -> dict:
    set_old = set(df_prior_oficial["hex_id"])
    set_new = set(df_prior_novo["hex_id"])
    return {
        "limiar": limiar,
        "top20_oficial": len(set_old),
        "top20_novo": len(set_new),
        "entram_no_recorte": len(set_new - set_old),
        "saem_do_recorte": len(set_old - set_new),
    }


def repro_litoral(vec_enr: pd.DataFrame) -> list[dict]:
    import h3

    alvos = {
        "Praia Grande (SP)": h3.latlng_to_cell(*PRAIA_GRANDE_LATLNG, settings.H3_RESOLUTION),
        "Litoral RJ (Rio)": h3.latlng_to_cell(*RJ_LITORAL_LATLNG, settings.H3_RESOLUTION),
    }
    out = []
    df_sp = set(pd.read_parquet(OFICIAL_BASE_ROOT / "uf=SP/hexagonos.parquet")["hex_id"])
    df_rj = set(pd.read_parquet(OFICIAL_BASE_ROOT / "uf=RJ/hexagonos.parquet")["hex_id"])
    oficiais = df_sp | df_rj
    vmap = dict(zip(vec_enr["hex_id"], vec_enr["fracao_terra"], strict=True))
    for nome, hid in alvos.items():
        # hex exato pode ja estar dentro; reportamos o melhor hex recuperado vizinho ausente
        candidatos = []
        for viz in h3.grid_disk(hid, 4):
            if viz in oficiais:
                continue
            if viz in vmap:
                candidatos.append((viz, vmap[viz]))
        candidatos.sort(key=lambda x: -x[1])
        if candidatos:
            best_hid, best_frac = candidatos[0]
            entra_a_partir = min(L for L in LEQUE if best_frac >= L) if best_frac >= min(LEQUE) else None
            out.append(
                {
                    "alvo": nome,
                    "hex_recuperado": best_hid,
                    "fracao_terra": round(float(best_frac), 4),
                    "ausente_hoje": True,
                    "reaparece_a_partir_de": entra_a_partir,
                    "n_vizinhos_recuperados": len(candidatos),
                }
            )
        else:
            out.append({"alvo": nome, "hex_recuperado": None, "fracao_terra": None, "ausente_hoje": False})
    return out


def _df_md(df: pd.DataFrame) -> str:
    if df.empty:
        return "_(vazio)_"
    cols = list(df.columns)
    linhas = ["| " + " | ".join(str(c) for c in cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, r in df.iterrows():
        linhas.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    return "\n".join(linhas)


def main() -> None:
    t0 = time.time()
    print("=== BLK-FIX-06 Fase A — medicao de impacto do litoral (SCRATCH) ===", flush=True)

    bases_por_uf, vec_df = regenerar_base_scratch_e_vetor(t0)
    total_oficial = int(sum(len(pd.read_parquet(p)) for p in sorted(OFICIAL_BASE_ROOT.glob("uf=*/hexagonos.parquet"))))
    total_piso = int(sum(len(df) for df in bases_por_uf.values()))
    _t(f"total hexes oficial(centroide)={total_oficial}  scratch(piso {PISO})={total_piso}  delta(+)={total_piso - total_oficial}", t0)

    vec_enr = enriquecer_recuperados(vec_df, t0)
    tabela_leque = montar_tabela_leque(vec_enr)
    _t("tabela do leque montada", t0)
    print(tabela_leque.to_string(index=False), flush=True)

    repro = repro_litoral(vec_enr)
    _t(f"repro litoral: {repro}", t0)

    # Totais por limiar (antes vs depois)
    totais_limiar = {}
    for L in LEQUE:
        n_entra = int((vec_enr["fracao_terra"] >= L).sum())
        totais_limiar[L] = {"total_apos": total_oficial + n_entra, "recuperados": n_entra}

    # Delta caro: 0.20 e 0.30
    df_oficial_estr = pd.read_parquet(OFICIAL_ESTRUTURAL, columns=[
        "hex_id", "renda_pct_nacional", "pop_pct_nacional", "score_priorizacao",
    ])
    df_oficial_prior = pd.read_parquet(OFICIAL_PRIORIZADOS, columns=["hex_id"])
    deltas, deltas_top20, quartis = [], [], {}
    for L in DELTA_CARO:
        root_l = construir_base_scratch_para_limiar(vec_df, L, t0)
        df_estr_l, df_prior_l = rodar_enriquecimento_scratch(root_l, L, t0)
        deltas.append(calcular_delta(df_oficial_estr, df_estr_l, L))
        deltas_top20.append(calcular_delta_top20(df_oficial_prior, df_prior_l, L))
        quartis[L] = _quartis_fracao(vec_enr, L)
        _t(f"delta caro limiar={L} concluido", t0)

    escrever_relatorio(tabela_leque, totais_limiar, vec_enr, repro, deltas, deltas_top20, quartis, total_oficial, t0)
    _t("RELATORIO ESCRITO. Fase A concluida.", t0)


def escrever_relatorio(
    tabela_leque, totais_limiar, vec_enr, repro, deltas, deltas_top20, quartis, total_oficial, t0
) -> None:
    # CSV auxiliar do leque
    LEQUE_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    tabela_leque.to_csv(LEQUE_CSV_PATH, sep=";", encoding="utf-8-sig", index=False)

    df_delta = pd.DataFrame(deltas)
    df_top20 = pd.DataFrame(deltas_top20)
    df_repro = pd.DataFrame(repro)
    quartis_geral = _quartis_fracao(vec_enr, PISO)

    linhas = [
        "# BLK-FIX-06 — Impacto do criterio HIBRIDO no litoral (Fase A, medicao em scratch)",
        "",
        f"- Data: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- Resolucao H3: {settings.H3_RESOLUTION}; criterio: centroide-dentro OU fracao_terra >= L",
        f"- Limiar default candidato (config): {settings.M1_HEX_LAND_FRACTION_MIN}",
        f"- Total de hexes OFICIAL (criterio centroide atual): {total_oficial}",
        "- Fracao de terra: razao de areas em graus (EPSG:4674), interseccao calculada 1x por hex hoje-descartado.",
        "- NENHUM artefato oficial foi escrito. Tudo em scratch (ver caminhos no fim).",
        "",
        "## Tabela do LEQUE de limiares {0.15, 0.20, 0.25, 0.30}",
        "",
        _df_md(tabela_leque),
        "",
        "## Total de hexes antes vs. depois",
        "",
        "| limiar L | total_apos | recuperados |",
        "|---|---|---|",
    ]
    for L, d in totais_limiar.items():
        linhas.append(f"| {L} | {d['total_apos']} | {d['recuperados']} |")
    linhas += [
        "",
        "## Distribuicao (quartis) de fracao_terra dos hexes que entram",
        "",
        f"- Geral (>= {PISO}): {quartis_geral}",
    ]
    for L in DELTA_CARO:
        linhas.append(f"- >= {L}: {quartis.get(L, {})}")
    linhas += [
        "",
        "## DELTA CARO — percentis nacionais e score_priorizacao dos hexes EXISTENTES (0.20 e 0.30)",
        "",
        _df_md(df_delta),
        "",
        "## DELTA CARO — recorte top-20%/UF (brasil_priorizados) (0.20 e 0.30)",
        "",
        _df_md(df_top20),
        "",
        "## Repro do litoral (hexes hoje ausentes que reaparecem)",
        "",
        _df_md(df_repro),
        "",
        "## Caminhos de SCRATCH gerados (prova de nao-escrita em oficiais)",
        "",
        f"- base scratch (piso {PISO}): {SCRATCH_BASE_ROOT}/uf=XX/hexagonos.parquet",
        f"- vetor fracao_terra: {VEC_PATH}",
        "- bases por limiar caro: data/staging/brasil_litoral_tmp_020/ , .../brasil_litoral_tmp_030/",
        "- estrutural/priorizados scratch: data/staging/brasil_estrutural.0NN.tmp.parquet , brasil_priorizados.0NN.tmp.parquet",
        f"- CSV auxiliar do leque: {LEQUE_CSV_PATH}",
        "",
        "## Nota de honestidade (delta caro)",
        "",
        "- Delta caro medido em 0.20 E 0.30 (enriquecimento estrutural+priorizacao+camada de oportunidade em scratch).",
        "- 0.15 e 0.25 reportados apenas com contagem/massa (leque), por design do plano v2.",
        "",
    ]
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(linhas) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
