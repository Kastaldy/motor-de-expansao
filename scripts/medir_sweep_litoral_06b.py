"""
BLK-FIX-06-B (LEQUE) — Recuperacao costeira por limiar de fracao-de-terra.

Com a geracao de candidatos por OVERLAP ja corrigida, mede quantos hexes da orla
entram em cada limiar candidato, para decidir o valor final ANTES de regenerar.

A interseccao poligono x poligono (fracao de terra) e calculada UMA vez por hex de
mar que sobrepoe terra; o leque e re-filtragem barata do vetor. NAO toca oficiais.

Uso:
    python scripts/medir_sweep_litoral_06b.py
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
    normalizar_features_uf,
)

REPORT_PATH = Path("data/reports/base_h3_litoral_sweep_06b.md")
SWEEP = [0.05, 0.10, 0.15, 0.20, 0.25]
# Hexes da orla apontados pelo usuario (fracao de terra conhecida).
THIN = {
    "Orla Mongagua (SP)": "87a810998ffffff",
    "Orla PG-Mongagua (SP)": "87a810d4cffffff",
    "Orla Itanhaem (SP)": "87a810903ffffff",
}


def _t(msg: str, t0: float) -> None:
    print(f"[{time.time() - t0:7.1f}s] {msg}", flush=True)


def _quartis(s: pd.Series) -> dict:
    if s.empty:
        return {}
    return {
        "n": int(len(s)),
        "min": round(float(s.min()), 3),
        "q25": round(float(s.quantile(0.25)), 3),
        "mediana": round(float(s.median()), 3),
        "q75": round(float(s.quantile(0.75)), 3),
        "max": round(float(s.max()), 3),
    }


def main() -> None:
    t0 = time.time()
    print("=== BLK-FIX-06-B — leque de limiares (candidatos OVERLAP) ===", flush=True)
    payload_uf = carregar_geojson(IBGE_MALHAS_UF_URL, Path("data/raw/ibge/malha_uf_brasil.geojson"), False)
    payload_br = carregar_geojson(IBGE_MALHA_BRASIL_URL, Path("data/raw/ibge/malha_brasil.geojson"), False)
    feats = normalizar_features_uf(payload_uf)
    brasil = construir_geometria_brasil(payload_br)

    # Vetor de fracao-de-terra de TODOS os hexes de mar que sobrepoem terra.
    vec_rows: list[dict] = []
    for f in feats:
        _, _, _, vec = gerar_hexagonos_validos_uf(
            feature_uf=f,
            brasil_geom=brasil,
            resolucao=settings.H3_RESOLUTION,
            land_fraction_min=0.20,  # nao afeta o vetor (coletar pega fracao>0)
            coletar_fracao_terra=True,
        )
        for hid, frac in vec:
            vec_rows.append({"hex_id": hid, "uf": f["uf"], "fracao": float(frac)})
        _t(f"vetor {f['uf']}: {len(vec)} hexes de mar com terra>0", t0)

    vec_df = pd.DataFrame(vec_rows, columns=["hex_id", "uf", "fracao"])
    # dedup: hex de mar pode aparecer em >1 UF costeira (fica a 1a, fracao igual)
    vec_df = vec_df.drop_duplicates("hex_id").reset_index(drop=True)
    _t(f"vetor total (dedup): {len(vec_df)} hexes de mar com terra>0", t0)

    # Tabela do leque
    rows = []
    for L in SWEEP:
        e = vec_df[vec_df["fracao"] >= L]
        por_uf = e.groupby("uf").size().sort_index()
        por_uf_str = ", ".join(f"{uf}:{n}" for uf, n in por_uf.items())
        rows.append(
            {
                "limiar_L": L,
                "recuperados_total": int(len(e)),
                "quartis_fracao": _quartis(e["fracao"]),
                "por_uf": por_uf_str,
            }
        )
    tabela = pd.DataFrame(rows)
    for _, r in tabela.iterrows():
        print(f"L={r['limiar_L']}: +{r['recuperados_total']} hexes | quartis={r['quartis_fracao']}", flush=True)

    # Repro: fracao de cada hex da orla + a partir de qual limiar entra
    fmap = dict(zip(vec_df["hex_id"], vec_df["fracao"], strict=True))
    repro_rows = []
    for nome, hid in THIN.items():
        frac = fmap.get(hid)
        # maior limiar do leque em que o hex AINDA e recuperado (L <= fracao):
        recuperado_ate = max([L for L in SWEEP if frac is not None and L <= frac], default=None)
        repro_rows.append(
            {"alvo": nome, "hex_id": hid, "fracao_terra": round(frac, 3) if frac is not None else None,
             "recuperado_ate_limiar": recuperado_ate}
        )
    df_repro = pd.DataFrame(repro_rows)
    print(df_repro.to_string(index=False), flush=True)

    escrever_relatorio(tabela, df_repro, vec_df)
    _t("RELATORIO DE LEQUE ESCRITO.", t0)


def _df_md(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    linhas = ["| " + " | ".join(str(c) for c in cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, r in df.iterrows():
        linhas.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    return "\n".join(linhas)


def escrever_relatorio(tabela: pd.DataFrame, df_repro: pd.DataFrame, vec_df: pd.DataFrame) -> None:
    linhas = [
        "# BLK-FIX-06-B — Leque de limiares de recuperacao costeira (medicao, scratch)",
        "",
        f"- Data: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "- Geracao de candidatos por OVERLAP (corrigida). Vetor de fracao-de-terra dos hexes de mar.",
        f"- Universo oficial atual: 1.538.424 (limiar 0.20 = +{int((vec_df['fracao'] >= 0.20).sum())} sobre os candidatos overlap).",
        "- NENHUM artefato oficial tocado.",
        "",
        "## Recuperados por limiar (re-filtragem do vetor)",
        "",
        _df_md(tabela),
        "",
        "## Repro dos hexes da orla apontados pelo usuario",
        "",
        _df_md(df_repro),
        "",
        "## Leitura",
        "",
        "- Limiar MENOR => mais orla fina entra, mas tambem mais hex majoritariamente oceanico",
        "  (baixa pop; no mapa cairia no corte cinza <5k, mas passa a EXISTIR em vez de ausente).",
        "- Impacto no score dos hexes existentes ja medido ~nulo em 0.20 (+2.446); limiares menores",
        "  adicionam hexes de pop ainda menor => impacto esperado igualmente desprezivel.",
        "",
    ]
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(linhas) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
