"""
validar_modelo_ultra.py
Validação de aderência do score censitário (score_setor_2022_calibrado)
e do M1 (score_priorizacao) com performance real das unidades Ultra.

Uso:
    python -m jobs.pipelines.validar_modelo_ultra

Saídas:
    data/staging/ultra_validacao_consolidada.parquet
    data/reports/validacao_modelo_ultra.md
"""

import re
import unicodedata
import warnings
from pathlib import Path

import h3
import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings("ignore")

BASE = Path(__file__).resolve().parents[2]
DATA = BASE / "data"

# ---------------------------------------------------------------------------
# 1. Carregamento de dados brutos
# ---------------------------------------------------------------------------

def _load_ultra_localizacao() -> pd.DataFrame:
    """Lê Ultra.csv com lat/lng das unidades."""
    df = pd.read_csv(
        DATA / "ultra" / "Ultra.csv",
        sep=";",
        encoding="latin-1",
        skiprows=1,
        header=0,
    )
    df.columns = ["unidade", "estado", "cidade", "lat_raw", "lng_raw"]
    # Limpar coordenadas (vírgula decimal, possíveis espaços)
    df["lat"] = (
        df["lat_raw"]
        .astype(str)
        .str.strip()
        .str.replace(",", ".", regex=False)
        .pipe(pd.to_numeric, errors="coerce")
    )
    df["lng"] = (
        df["lng_raw"]
        .astype(str)
        .str.strip()
        .str.replace(",", ".", regex=False)
        .pipe(pd.to_numeric, errors="coerce")
    )
    # Remover registros sem coordenadas válidas
    df = df.dropna(subset=["lat", "lng"]).reset_index(drop=True)
    return df[["unidade", "estado", "cidade", "lat", "lng"]]


def _load_ultra_performance() -> pd.DataFrame:
    """Lê dados_academias.xlsx com métricas de performance."""
    df = pd.read_excel(DATA / "ultra" / "dados_academias.xlsx")
    cols_keep = ["LOCALIZACAO", "FATURAMENTO", "ATIVOS_PAG", "AGREGADORES", "ALUNOS_TOTAL"]
    # ALUNOS_GYMPASS e ALUNOS_TOTALPASS são subconjunto de AGREGADORES
    df = df[cols_keep].copy()
    df.columns = ["localizacao", "faturamento", "ativos_pag", "agregadores", "alunos_total"]
    return df


# ---------------------------------------------------------------------------
# 2. Matching de nomes entre os dois arquivos
# ---------------------------------------------------------------------------

def _normalizar(texto: str) -> str:
    """Remove acentos, coloca minúsculas, remove sufixos de estado."""
    texto = unicodedata.normalize("NFD", str(texto))
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = texto.lower()
    # Remove sufixos comuns: " - SP", " / SP", " SP", " DF", etc.
    texto = re.sub(r"\s*[/\-]\s*(sp|rj|df|go|mg|rs|pr|sc|mt|es|ba|pe|al|rn|ma|to)\b", "", texto)
    texto = re.sub(r"\s+(sp|rj|df|go|mg|rs|pr|sc|mt|es|ba|pe|al|rn|ma|to)\b", "", texto)
    texto = re.sub(r"[^a-z0-9\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


# Mapeamento manual para casos ambíguos
MANUAL_MAP = {
    # localizacao_normalizada -> unidade_normalizada
    "poa barra sul": "porto alegre",
    "botanic mall": "jd botanico",
    "cpa": "jardim das americas",
    "campo limpo": "campo limpo paulista",  # não está no CSV, vai ficar sem match
    "santos": "santos",
    "aguas claras": "aguas claras",
    "aclimacao": "aclimaçao",
    "augusta": "augusta",
    "asa norte": "asa norte",
    "paranoa parque": "paranoa",
    "samambaia": "samambaia norte",
    "valparaiso": "valparaiso de goias",
    "sobradinho": "sobradinho",
    "taguatinga sul": "taguatinga sul",
    "jardim botanico": "jd botanico",
    "plaza sul": "plaza sul",
    "cambui campinas": "cambui",
}


def _match_unidades(loc_df: pd.DataFrame, perf_df: pd.DataFrame) -> pd.DataFrame:
    """
    Faz join entre localização e performance por normalização de nome.
    Retorna DataFrame com todas as unidades da performance que tiveram match.
    """
    loc_df = loc_df.copy()
    perf_df = perf_df.copy()

    loc_df["key"] = loc_df["unidade"].apply(_normalizar)
    perf_df["key"] = perf_df["localizacao"].apply(_normalizar)

    # Aplicar mapeamento manual nas chaves do perf
    perf_df["key_mapped"] = perf_df["key"].apply(
        lambda k: MANUAL_MAP.get(k, k)
    )
    # Aplicar mapeamento manual nas chaves do loc também
    loc_df["key_mapped"] = loc_df["key"].apply(
        lambda k: MANUAL_MAP.get(k, k)
    )

    # Tentar match exato primeiro
    merged = perf_df.merge(
        loc_df[["key_mapped", "unidade", "estado", "cidade", "lat", "lng"]],
        on="key_mapped",
        how="left",
    )

    # Para os que não deram match, tentar substring
    no_match = merged[merged["lat"].isna()].index
    for idx in no_match:
        k = merged.loc[idx, "key_mapped"]
        # buscar chave de loc que contenha k ou k contenha chave de loc
        for _, row_loc in loc_df.iterrows():
            kl = row_loc["key_mapped"]
            if k in kl or kl in k:
                merged.loc[idx, "unidade"] = row_loc["unidade"]
                merged.loc[idx, "estado"] = row_loc["estado"]
                merged.loc[idx, "cidade"] = row_loc["cidade"]
                merged.loc[idx, "lat"] = row_loc["lat"]
                merged.loc[idx, "lng"] = row_loc["lng"]
                break

    n_matched = merged["lat"].notna().sum()
    n_total = len(merged)
    print(f"  Match: {n_matched}/{n_total} unidades ({100*n_matched/n_total:.1f}%)")

    unmatched = merged[merged["lat"].isna()]["localizacao"].tolist()
    if unmatched:
        print(f"  Sem match ({len(unmatched)}): {unmatched}")

    return merged


# ---------------------------------------------------------------------------
# 3. H3 encoding
# ---------------------------------------------------------------------------

def _to_h3(df: pd.DataFrame, resolution: int = 7) -> pd.DataFrame:
    df = df.copy()
    df["hex_id"] = df.apply(
        lambda r: h3.latlng_to_cell(r["lat"], r["lng"], resolution)
        if pd.notna(r["lat"]) and pd.notna(r["lng"])
        else None,
        axis=1,
    )
    return df


# ---------------------------------------------------------------------------
# 4. Join com scores M1 e Censitário 2022
# ---------------------------------------------------------------------------

def _load_scores() -> pd.DataFrame:
    """
    Carrega scores M1 e censitário 2022, une em um único DataFrame por hex_id.
    """
    # M1: dashboard
    m1 = pd.read_parquet(DATA / "outputs" / "hexagonos_brasil_dashboard.parquet")
    m1_cols = ["hex_id", "uf", "cidade", "score_oficial", "hex_score_estrutural",
               "renda_per_capita", "populacao_proxy", "faixa_oportunidade"]
    m1 = m1[m1_cols].rename(columns={
        "score_oficial": "score_priorizacao_m1",
        "cidade": "nome_municipio_m1",
    })

    # Censitário: piloto GO/SP/RJ
    c1_cols = ["hex_id", "uf", "score_setor_2022_calibrado", "renda_per_capita_setor_2022_calibrada",
               "coverage_pct_setor_2022", "flag_outlier_espacial", "qualidade_join_uf"]
    c1 = pd.read_parquet(DATA / "staging" / "censo2022_setores_calibrado.parquet")[c1_cols]

    # Censitário: piloto expandido MG/DF/RS
    c2_raw = pd.read_parquet(DATA / "staging" / "censo2022_setores_calibrado_piloto_expandido.parquet")
    c2_cols = [col for col in c1_cols if col in c2_raw.columns]
    c2 = c2_raw[c2_cols]

    censo = pd.concat([c1, c2], ignore_index=True)
    censo = censo.rename(columns={"uf": "uf_censo"})

    # Join
    scores = m1.merge(censo[["hex_id", "score_setor_2022_calibrado",
                               "renda_per_capita_setor_2022_calibrada",
                               "coverage_pct_setor_2022", "flag_outlier_espacial",
                               "qualidade_join_uf"]],
                      on="hex_id", how="left")
    return scores


# ---------------------------------------------------------------------------
# 5. Dataset consolidado
# ---------------------------------------------------------------------------

def _build_dataset() -> pd.DataFrame:
    print("\n[1/5] Carregando dados das unidades Ultra...")
    loc = _load_ultra_localizacao()
    perf = _load_ultra_performance()

    print("[2/5] Fazendo match entre localização e performance...")
    units = _match_unidades(loc, perf)
    units = units[units["lat"].notna()].reset_index(drop=True)

    print("[3/5] Convertendo para H3 (resolução 7)...")
    units = _to_h3(units)

    print("[4/5] Carregando scores M1 e Censitário...")
    scores = _load_scores()

    print("[5/5] Joining scores com unidades Ultra...")
    df = units.merge(scores, on="hex_id", how="left")

    # Flag de disponibilidade de score censitário
    df["tem_score_censo"] = df["score_setor_2022_calibrado"].notna()

    print(f"\n  Total de unidades com performance: {len(df)}")
    print(f"  Com score M1: {df['score_priorizacao_m1'].notna().sum()}")
    print(f"  Com score censitário: {df['tem_score_censo'].sum()}")
    print(f"  UFs cobertas pelo censo: {sorted(df.loc[df['tem_score_censo'], 'uf'].dropna().unique().tolist())}")

    return df


# ---------------------------------------------------------------------------
# 6. Análise de correlação
# ---------------------------------------------------------------------------

def _correlacao(df: pd.DataFrame) -> dict:
    """Calcula Spearman entre scores e métricas de performance."""
    metricas = ["faturamento", "ativos_pag", "agregadores", "alunos_total"]
    scores = {
        "score_priorizacao_m1": df[df["score_priorizacao_m1"].notna()],
        "score_setor_2022_calibrado": df[df["score_setor_2022_calibrado"].notna()],
    }

    resultados = {}
    for score_name, sub in scores.items():
        resultados[score_name] = {}
        for metrica in metricas:
            valid = sub[[score_name, metrica]].dropna()
            if len(valid) < 5:
                resultados[score_name][metrica] = {"rho": None, "p": None, "n": len(valid)}
                continue
            rho, p = stats.spearmanr(valid[score_name], valid[metrica])
            resultados[score_name][metrica] = {"rho": round(rho, 4), "p": round(p, 4), "n": len(valid)}

    return resultados


# ---------------------------------------------------------------------------
# 7. Análise de quartis (ranking)
# ---------------------------------------------------------------------------

def _analise_quartis(df: pd.DataFrame) -> dict:
    """Compara performance média nos quartis superior e inferior de cada score."""
    metricas = ["faturamento", "ativos_pag", "alunos_total"]
    resultado = {}

    for score_name in ["score_priorizacao_m1", "score_setor_2022_calibrado"]:
        sub = df[df[score_name].notna()].copy()
        if len(sub) < 8:
            resultado[score_name] = None
            continue

        try:
            sub["quartil"] = pd.qcut(sub[score_name], 4, labels=["Q1", "Q2", "Q3", "Q4"])
        except ValueError:
            # Fallback com duplicates="drop" quando há valores repetidos (ex: DF flat=100)
            try:
                sub["quartil"] = pd.qcut(sub[score_name], 4, labels=False, duplicates="drop")
                sub["quartil"] = sub["quartil"].map({0: "Q1", 1: "Q2", 2: "Q3", 3: "Q4"})
            except Exception:
                sub["quartil"] = pd.cut(sub[score_name], 4, labels=["Q1", "Q2", "Q3", "Q4"])
        stats_q = sub.groupby("quartil", observed=True)[metricas].mean().round(0)
        resultado[score_name] = stats_q.to_dict()

    return resultado


# ---------------------------------------------------------------------------
# 8. Análise de divergência
# ---------------------------------------------------------------------------

def _analise_divergencia(df: pd.DataFrame) -> pd.DataFrame:
    """Identifica unidades onde os modelos divergem muito na predição."""
    sub = df[df["score_priorizacao_m1"].notna() & df["score_setor_2022_calibrado"].notna()].copy()
    if len(sub) < 4:
        return pd.DataFrame()

    sub["rank_m1"] = sub["score_priorizacao_m1"].rank(ascending=False)
    sub["rank_censo"] = sub["score_setor_2022_calibrado"].rank(ascending=False)
    sub["delta_rank"] = (sub["rank_m1"] - sub["rank_censo"]).abs()

    # Unidades no top quartil de score_censo mas bottom quartil de M1
    p75_censo = sub["score_setor_2022_calibrado"].quantile(0.75)
    p25_m1 = sub["score_priorizacao_m1"].quantile(0.25)
    p25_censo = sub["score_setor_2022_calibrado"].quantile(0.25)
    p75_m1 = sub["score_priorizacao_m1"].quantile(0.75)

    sub["tipo_divergencia"] = "alinhado"
    mask_censo_wins = (sub["score_setor_2022_calibrado"] >= p75_censo) & (sub["score_priorizacao_m1"] <= p25_m1)
    mask_m1_wins = (sub["score_priorizacao_m1"] >= p75_m1) & (sub["score_setor_2022_calibrado"] <= p25_censo)
    sub.loc[mask_censo_wins, "tipo_divergencia"] = "censo_alto_m1_baixo"
    sub.loc[mask_m1_wins, "tipo_divergencia"] = "m1_alto_censo_baixo"

    divergentes = sub[sub["tipo_divergencia"] != "alinhado"].copy()
    return divergentes[["localizacao", "uf", "score_priorizacao_m1", "score_setor_2022_calibrado",
                          "faturamento", "ativos_pag", "alunos_total", "tipo_divergencia", "delta_rank"]]


# ---------------------------------------------------------------------------
# 9. Comparação final: qual modelo explica melhor?
# ---------------------------------------------------------------------------

def _comparar_modelos(corr: dict) -> dict:
    metricas = ["faturamento", "ativos_pag", "alunos_total"]
    m1_rhos = [abs(corr["score_priorizacao_m1"][m]["rho"] or 0) for m in metricas]
    censo_rhos = [abs(corr["score_setor_2022_calibrado"][m]["rho"] or 0) for m in metricas]

    m1_media = np.mean(m1_rhos)
    censo_media = np.mean(censo_rhos)

    if censo_media > m1_media * 1.1:
        vencedor = "censitario"
    elif m1_media > censo_media * 1.1:
        vencedor = "m1"
    else:
        vencedor = "empate"

    return {
        "m1_media_abs_rho": round(m1_media, 4),
        "censo_media_abs_rho": round(censo_media, 4),
        "vencedor": vencedor,
    }


# ---------------------------------------------------------------------------
# 10. Geração do relatório Markdown
# ---------------------------------------------------------------------------

def _gerar_relatorio(df: pd.DataFrame, corr: dict, quartis: dict,
                     divergentes: pd.DataFrame, comparacao: dict) -> str:
    metricas = ["faturamento", "ativos_pag", "agregadores", "alunos_total"]

    linhas = [
        "# Validação de aderência do modelo — Unidades Ultra",
        "",
        f"**Data:** 2026-04-09  |  **Unidades analisadas:** {len(df)}  |  "
        f"**Com score M1:** {df['score_priorizacao_m1'].notna().sum()}  |  "
        f"**Com score censitário:** {df['score_setor_2022_calibrado'].notna().sum()}",
        "",
    ]

    # UFs cobertas
    ufs_censo = sorted(df.loc[df["tem_score_censo"], "uf"].dropna().unique().tolist())
    linhas += [
        "## 1. Cobertura",
        f"- UFs com score censitário disponível: {', '.join(ufs_censo)}",
        f"- UFs com score M1: todas as 27 UFs (cobertura nacional)",
        "",
    ]

    # Correlação
    linhas += [
        "## 2. Correlação de Spearman — Score × Performance",
        "",
        "| Métrica | M1 ρ | M1 p | M1 n | Censitário ρ | Censitário p | Censo n |",
        "|---------|------|------|------|--------------|--------------|---------|",
    ]
    for m in metricas:
        r_m1 = corr["score_priorizacao_m1"][m]
        r_c = corr["score_setor_2022_calibrado"][m]
        rho_m1 = f"{r_m1['rho']:.3f}" if r_m1["rho"] is not None else "N/A"
        rho_c = f"{r_c['rho']:.3f}" if r_c["rho"] is not None else "N/A"
        p_m1 = f"{r_m1['p']:.3f}" if r_m1["p"] is not None else "N/A"
        p_c = f"{r_c['p']:.3f}" if r_c["p"] is not None else "N/A"
        linhas.append(
            f"| {m} | {rho_m1} | {p_m1} | {r_m1['n']} | {rho_c} | {p_c} | {r_c['n']} |"
        )
    linhas.append("")

    # Quartis
    linhas += ["## 3. Análise de Quartis — Performance por Faixa de Score", ""]
    for score_name, stats_q in quartis.items():
        if stats_q is None:
            linhas.append(f"**{score_name}**: dados insuficientes.")
            continue
        linhas.append(f"### {score_name}")
        linhas.append("")
        linhas.append("| Quartil | Faturamento Médio | Ativos Pag. Médio | Alunos Total Médio |")
        linhas.append("|---------|-------------------|-------------------|--------------------|")
        for q in ["Q1", "Q2", "Q3", "Q4"]:
            fat = f"R$ {stats_q.get('faturamento', {}).get(q, 'N/A'):,.0f}" if isinstance(stats_q.get('faturamento', {}).get(q), float) else "N/A"
            atv = f"{stats_q.get('ativos_pag', {}).get(q, 'N/A'):,.0f}" if isinstance(stats_q.get('ativos_pag', {}).get(q), float) else "N/A"
            alu = f"{stats_q.get('alunos_total', {}).get(q, 'N/A'):,.0f}" if isinstance(stats_q.get('alunos_total', {}).get(q), float) else "N/A"
            linhas.append(f"| {q} | {fat} | {atv} | {alu} |")
        linhas.append("")

    # Divergentes
    linhas += ["## 4. Análise de Divergência entre Modelos", ""]
    if len(divergentes) > 0:
        linhas.append("| Unidade | UF | Score M1 | Score Censo | Faturamento | Tipo |")
        linhas.append("|---------|-----|----------|-------------|-------------|------|")
        for _, r in divergentes.iterrows():
            fat = f"R$ {r['faturamento']:,.0f}" if pd.notna(r["faturamento"]) else "N/A"
            linhas.append(
                f"| {r['localizacao']} | {r['uf']} | {r['score_priorizacao_m1']:.1f} | "
                f"{r['score_setor_2022_calibrado']:.1f} | {fat} | {r['tipo_divergencia']} |"
            )
    else:
        linhas.append("Nenhuma divergência expressiva identificada com a amostra disponível.")
    linhas.append("")

    # Comparação final
    linhas += [
        "## 5. Comparação Final — Qual Modelo Explica Melhor?",
        "",
        f"- **M1 (score_priorizacao):** |ρ| médio = {comparacao['m1_media_abs_rho']:.3f}",
        f"- **Censitário 2022 (score_setor_2022_calibrado):** |ρ| médio = {comparacao['censo_media_abs_rho']:.3f}",
        f"- **Modelo com maior correlação média:** `{comparacao['vencedor']}`",
        "",
    ]

    # Decisão GO/NO-GO
    v = comparacao["vencedor"]
    if v == "censitario":
        decisao = "**GO condicional**: modelo censitário demonstra correlação superior com performance real."
        orientacao = "Recomenda-se piloto controlado expandido antes de promoção ao ranking executivo."
    elif v == "m1":
        decisao = "**NO-GO para substituição**: M1 explica melhor a performance atual das unidades Ultra."
        orientacao = "Censitário tem valor como camada complementar para granularidade intraurbana, mas não supera M1 na validação de negócio."
    else:
        decisao = "**Empate técnico**: modelos têm aderência equivalente."
        orientacao = "Considerar uso combinado ou aguardar amostra maior para discriminação."

    linhas += [
        "## 6. Decisão Estratégica",
        "",
        decisao,
        "",
        orientacao,
        "",
        "### Limitações desta validação",
        "- Amostra limitada (54 unidades maduras); unidades sem dados de performance excluídas do scoring.",
        "- Score censitário disponível apenas para GO, SP, RJ, MG, DF, RS — amostra nacional incompleta.",
        "- Dados de churn e conversão não disponíveis neste snapshot.",
        "- GeoFusion demographics no dataset foram desconsideradas (fora do escopo desta validação).",
        "",
    ]

    return "\n".join(linhas)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("Validação de aderência — Modelo Ultra")
    print("=" * 60)

    df = _build_dataset()

    print("\n[6] Calculando correlações de Spearman...")
    corr = _correlacao(df)

    print("[7] Análise de quartis...")
    quartis = _analise_quartis(df)

    print("[8] Análise de divergência...")
    divergentes = _analise_divergencia(df)

    print("[9] Comparando modelos...")
    comparacao = _comparar_modelos(corr)

    print(f"\n  Resultado: M1 |rho| medio = {comparacao['m1_media_abs_rho']:.3f} | "
          f"Censitario |rho| medio = {comparacao['censo_media_abs_rho']:.3f} | "
          f"Vencedor: {comparacao['vencedor']}")

    print("\n[10] Salvando outputs...")
    out_parquet = DATA / "staging" / "ultra_validacao_consolidada.parquet"
    df.to_parquet(out_parquet, index=False)
    print(f"  Parquet: {out_parquet}")

    relatorio = _gerar_relatorio(df, corr, quartis, divergentes, comparacao)
    out_md = DATA / "reports" / "validacao_modelo_ultra.md"
    out_md.write_text(relatorio, encoding="utf-8")
    print(f"  Relatório: {out_md}")

    # Print resumo final
    print("\n" + "=" * 60)
    print("RESUMO FINAL")
    print("=" * 60)
    for score_name in ["score_priorizacao_m1", "score_setor_2022_calibrado"]:
        print(f"\n{score_name}:")
        for m in ["faturamento", "ativos_pag", "alunos_total"]:
            r = corr[score_name][m]
            rho = f"{r['rho']:.3f}" if r["rho"] is not None else "N/A"
            p = f"{r['p']:.3f}" if r["p"] is not None else "N/A"
            print(f"  {m}: rho={rho}, p={p}, n={r['n']}")

    print(f"\nModelo vencedor: {comparacao['vencedor']}")

    return df, corr, quartis, divergentes, comparacao


if __name__ == "__main__":
    main()
