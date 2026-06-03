"""
BLK-FIX-06-B (MEDICAO) — Impacto da geracao de candidatos por OVERLAP no litoral.

Corrige o defeito do BLK-FIX-06: a geracao de candidatos usava `h3.geo_to_cells`
(containment por CENTRO), que nunca produzia os hexes da orla com centroide no mar.
Agora `_gerar_candidatos_uf` usa containment OVERLAP, e o filtro de fracao-de-terra
(limiar DEC-002 = 0.20) recupera a orla povoada de verdade.

NAO toca NENHUM artefato oficial. TUDO em scratch:
  - base H3 scratch:        data/staging/brasil_litoral06b_tmp/uf=XX/hexagonos.parquet
  - estrutural/priorizados: data/staging/*.06b.tmp.parquet
  - relatorio:              data/reports/base_h3_litoral_impacto_06b.md

Uso:
    python scripts/medir_impacto_litoral_blk_fix_06b.py
"""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd

from motor_expansao.config import settings
from motor_expansao.pipelines.m1.base_h3_brasil import executar_base_h3_brasil
from motor_expansao.pipelines.m1.hex_enrichment import (
    _garantir_nomes_municipio,
    _listar_particoes_brasil,
    _salvar_particao_uf,
    calcular_hex_score_estrutural,
    enriquecer_hexagonos_uf_estrutural,
    rodar_camada_oportunidade_nacional,
    selecionar_areas_prioritarias,
)
from motor_expansao.pipelines.m1.ibge_censo import IBGECenso

SCRATCH_BASE_ROOT = Path("data/staging/brasil_litoral06b_tmp")
SCRATCH_REPORT = Path("data/reports/base_h3_brasil_06b.tmp.md")
REPORT_PATH = Path("data/reports/base_h3_litoral_impacto_06b.md")

OFICIAL_BASE_ROOT = Path("data/staging/brasil")
OFICIAL_ESTRUTURAL = Path("data/staging/brasil_estrutural.parquet")
OFICIAL_PRIORIZADOS = Path("data/staging/brasil_priorizados.parquet")

# Hexes que o usuario apontou como ausentes na orla (BLK-FIX-06-B).
REPRO_HEXES = {
    "Orla Mongagua (SP)": "87a810998ffffff",
    "Orla PG-Mongagua (SP)": "87a810d4cffffff",
    "Orla Itanhaem (SP)": "87a810903ffffff",
    "Orla Praia Grande recuperada (06)": "87a810c02ffffff",
}


def _t(msg: str, t0: float) -> None:
    print(f"[{time.time() - t0:7.1f}s] {msg}", flush=True)


def _hexset(root: Path) -> set[str]:
    out: set[str] = set()
    for p in sorted(root.glob("uf=*/hexagonos.parquet")):
        out |= set(pd.read_parquet(p, columns=["hex_id"])["hex_id"])
    return out


def rodar_enriquecimento_scratch(input_root: Path, t0: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    out_estrutural = Path("data/staging/brasil_estrutural.06b.tmp.parquet")
    out_priorizados = Path("data/staging/brasil_priorizados.06b.tmp.parquet")
    out_oportunidades = Path("data/staging/hexagonos_brasil_oportunidades.06b.tmp.parquet")
    tmp_root = Path("data/staging/brasil_estrutural_tmp_06b")

    censo = IBGECenso()
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
    _t(f"estrutural scratch: {len(df_total)} hexes -> {out_estrutural}", t0)

    df_prior, _ = selecionar_areas_prioritarias(
        df_estrutural=df_total, top_pct_por_uf=settings.M1_PRIORIZACAO_TOP_PCT_POR_UF
    )
    df_prior.to_parquet(out_priorizados, index=False)
    _t(f"priorizados scratch: {len(df_prior)} hexes -> {out_priorizados}", t0)

    rodar_camada_oportunidade_nacional(
        input_estrutural_path=out_estrutural,
        input_priorizados_path=out_priorizados,
        output_base_path=out_oportunidades,
        output_top_brasil_csv=Path("data/staging/top_hexagonos_brasil.06b.tmp.csv"),
        output_top_uf_csv=Path("data/staging/top_hexagonos_por_uf.06b.tmp.csv"),
        output_dashboard_path=Path("data/staging/hexagonos_brasil_dashboard_base.06b.tmp.parquet"),
        report_path=Path("data/reports/camada_oportunidade_fase1.06b.tmp.md"),
    )
    return df_total, df_prior


def calcular_delta(df_oficial: pd.DataFrame, df_novo: pd.DataFrame) -> dict:
    cols = ["hex_id", "renda_pct_nacional", "pop_pct_nacional", "score_priorizacao"]
    a = df_oficial[[c for c in cols if c in df_oficial.columns]].copy()
    b = df_novo[[c for c in cols if c in df_novo.columns]].copy()
    m = a.merge(b, on="hex_id", how="inner", suffixes=("_old", "_new"))
    out: dict = {"hexes_existentes_comparados": int(len(m))}
    for c in ["renda_pct_nacional", "pop_pct_nacional", "score_priorizacao"]:
        if f"{c}_old" in m.columns and f"{c}_new" in m.columns:
            d = (m[f"{c}_new"] - m[f"{c}_old"]).abs()
            out[f"delta_{c}_mediana"] = round(float(d.median()), 4)
            out[f"delta_{c}_max"] = round(float(d.max()), 4)
    if "score_priorizacao_old" in m.columns and "score_priorizacao_new" in m.columns:
        d = (m["score_priorizacao_new"] - m["score_priorizacao_old"]).abs()
        out["score_n_muda_alem_0p5"] = int((d > 0.5).sum())
        out["score_maior_deslocamento_abs"] = round(float(d.max()), 4)
    return out


def main() -> None:
    t0 = time.time()
    print("=== BLK-FIX-06-B — medicao do litoral (candidatos OVERLAP, limiar 0.20) ===", flush=True)
    print(f"limiar M1_HEX_LAND_FRACTION_MIN = {settings.M1_HEX_LAND_FRACTION_MIN}", flush=True)

    # 1. Regenera a base em scratch com o criterio corrigido (overlap).
    res = executar_base_h3_brasil(
        output_root=SCRATCH_BASE_ROOT, report_path=SCRATCH_REPORT, refresh_malha=False
    )
    _t(f"base scratch: total={res['total_hexagonos']} removidos={res['total_removidos']}", t0)

    novo = _hexset(SCRATCH_BASE_ROOT)
    oficial = _hexset(OFICIAL_BASE_ROOT)
    recuperados = novo - oficial
    perdidos = oficial - novo
    # recuperados por UF (via particoes scratch)
    rec_por_uf: dict[str, int] = {}
    for p in sorted(SCRATCH_BASE_ROOT.glob("uf=*/hexagonos.parquet")):
        uf = p.parent.name.split("=", 1)[1]
        s = set(pd.read_parquet(p, columns=["hex_id"])["hex_id"])
        rec_por_uf[uf] = len(s & recuperados)
    rec_por_uf = {k: v for k, v in sorted(rec_por_uf.items()) if v > 0}
    _t(
        f"total oficial={len(oficial)} novo={len(novo)} recuperados=+{len(recuperados)} perdidos=-{len(perdidos)}",
        t0,
    )
    print("recuperados por UF:", rec_por_uf, flush=True)

    # 2. Enriquecimento scratch -> delta de percentis/score nos hexes existentes.
    df_estr_novo, df_prior_novo = rodar_enriquecimento_scratch(SCRATCH_BASE_ROOT, t0)
    df_oficial_estr = pd.read_parquet(
        OFICIAL_ESTRUTURAL, columns=["hex_id", "renda_pct_nacional", "pop_pct_nacional", "score_priorizacao"]
    )
    delta = calcular_delta(df_oficial_estr, df_estr_novo)
    _t(f"delta nos hexes existentes: {delta}", t0)

    set_prior_old = set(pd.read_parquet(OFICIAL_PRIORIZADOS, columns=["hex_id"])["hex_id"])
    set_prior_new = set(df_prior_novo["hex_id"])
    top20 = {
        "top20_oficial": len(set_prior_old),
        "top20_novo": len(set_prior_new),
        "entram": len(set_prior_new - set_prior_old),
        "saem": len(set_prior_old - set_prior_new),
    }
    _t(f"top-20%/UF: {top20}", t0)

    # 3. Repro dos hexes da orla apontados pelo usuario.
    repro_rows = []
    for nome, hx in REPRO_HEXES.items():
        repro_rows.append(
            {
                "alvo": nome,
                "hex_id": hx,
                "no_oficial_atual": hx in oficial,
                "no_novo_06b": hx in novo,
                "recuperado_por_06b": (hx in recuperados),
            }
        )
    df_repro = pd.DataFrame(repro_rows)
    print(df_repro.to_string(index=False), flush=True)

    escrever_relatorio(len(oficial), len(novo), recuperados, perdidos, rec_por_uf, delta, top20, df_repro)
    _t("RELATORIO ESCRITO. Medicao 06-B concluida.", t0)


def _df_md(df: pd.DataFrame) -> str:
    if df.empty:
        return "_(vazio)_"
    cols = list(df.columns)
    linhas = ["| " + " | ".join(str(c) for c in cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, r in df.iterrows():
        linhas.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    return "\n".join(linhas)


def escrever_relatorio(
    total_oficial, total_novo, recuperados, perdidos, rec_por_uf, delta, top20, df_repro
) -> None:
    rec_uf_str = ", ".join(f"{uf}:{n}" for uf, n in rec_por_uf.items())
    linhas = [
        "# BLK-FIX-06-B — Impacto da geracao de candidatos por OVERLAP (medicao, scratch)",
        "",
        f"- Data: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- Limiar M1_HEX_LAND_FRACTION_MIN (DEC-002, inalterado): {settings.M1_HEX_LAND_FRACTION_MIN}",
        "- Fix: candidatos por containment OVERLAP (antes: centro). Filtro de fracao-de-terra inalterado.",
        "- NENHUM artefato oficial escrito. Tudo em scratch.",
        "",
        "## Universo de hexes",
        "",
        f"- Oficial atual (BLK-FIX-06, +474): **{total_oficial}**",
        f"- Novo (06-B, overlap): **{total_novo}**",
        f"- Recuperados pelo 06-B: **+{len(recuperados)}**  | perdidos: -{len(perdidos)}",
        f"- Recuperados por UF: {rec_uf_str}",
        "",
        "## Delta nos hexes EXISTENTES (percentis nacionais + score_priorizacao)",
        "",
        f"- {delta}",
        "",
        "## Recorte top-20%/UF (brasil_priorizados)",
        "",
        f"- {top20}",
        "",
        "## Repro dos hexes da orla (apontados pelo usuario)",
        "",
        _df_md(df_repro),
        "",
        "## Scratch gerado (prova de nao-escrita em oficiais)",
        "",
        f"- base: {SCRATCH_BASE_ROOT}/uf=XX/hexagonos.parquet",
        "- estrutural/priorizados: data/staging/*.06b.tmp.parquet",
        "",
    ]
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(linhas) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
