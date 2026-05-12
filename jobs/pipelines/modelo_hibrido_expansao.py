"""Modelo hibrido de expansao: M1 para selecao municipal + censitario para selecao intraurbana.

Objetivo:
- preservar `score_priorizacao` como score oficial do M1
- operacionalizar uma regra pratica em 2 etapas
- gerar um dataset pronto para decisao de abertura e uma base inicial de monitoramento

Regras:
1. Etapa municipal: selecionar municipios via `score_priorizacao` (top 20% por UF).
2. Etapa intraurbana: dentro dos municipios selecionados, ranquear hexes via
   `score_setor_2022_calibrado`, respeitando as regras de robustez da Fase A.
3. `score_expansao_hibrido` funciona como chave de ordenacao lexicografica:
   o M1 continua sendo o criterio principal e o score censitario atua apenas
   como desempate/refino local dentro do municipio aprovado.

Artefatos:
- data/outputs/oportunidades_expansao_hibrido.parquet
- data/reports/modelo_hibrido_expansao.md
- data/outputs/monitoramento_expansao_hibrido_base.parquet
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import h3
import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"

DEFAULT_DASHBOARD_PATH = DATA_DIR / "outputs" / "hexagonos_brasil_dashboard.parquet"
DEFAULT_M1_STRUCTURAL_PATH = DATA_DIR / "staging" / "brasil_estrutural.parquet"
DEFAULT_CENSO_CORE_PATH = DATA_DIR / "staging" / "censo2022_setores_calibrado.parquet"
DEFAULT_CENSO_EXPANDED_PATH = (
    DATA_DIR / "staging" / "censo2022_setores_calibrado_piloto_expandido.parquet"
)
DEFAULT_CENSO_NACIONAL_PATH = (
    DATA_DIR / "staging" / "censo2022_setores_calibrado_nacional_completo.parquet"
)
DEFAULT_OUTPUT_PATH = DATA_DIR / "outputs" / "oportunidades_expansao_hibrido.parquet"
DEFAULT_REPORT_PATH = DATA_DIR / "reports" / "modelo_hibrido_expansao.md"
DEFAULT_MONITORING_PATH = DATA_DIR / "outputs" / "monitoramento_expansao_hibrido_base.parquet"

TOP_MUNICIPIO_PCT = 0.20
TOP_HEX_INTRAURBANO_PCT = 0.10
TOP_OPORTUNIDADES_BRASIL = 100
TOP_OPORTUNIDADES_POR_UF = 20
TOP_OPORTUNIDADES_POR_MUNICIPIO = 10
COVERAGE_MIN_SETOR = 85.0
JOIN_CLASSES_ELEGIVEIS = {"A", "B"}
LOCAL_BONUS_DIVISOR = 100_000.0
DENSIDADE_MIN_HAB_KM2 = 5_000.0
H3_RESOLUTION_PADRAO = 7


def calcular_corte_top(total: int, pct: float, *, minimo: int = 1) -> int:
    """Replica a filosofia de corte deterministico do M1 com minimo operacional."""
    if total <= 0:
        return 0
    return max(minimo, int(np.floor(total * pct)))


def calcular_densidade_pop_setor_hab_km2(
    hex_id: pd.Series,
    pop_total_setor_2022: pd.Series,
) -> pd.Series:
    """Estima densidade usando a area media da resolucao H3 do snapshot."""
    pop = pd.to_numeric(pop_total_setor_2022, errors="coerce")
    densidade = pd.Series(np.nan, index=pop.index, dtype="float64")

    hex_validos = hex_id.astype("string").fillna("").str.strip()
    mask = pop.notna() & hex_validos.ne("")
    if not mask.any():
        return densidade

    try:
        resolucao = h3.get_resolution(hex_validos.loc[mask].iloc[0])
    except (TypeError, ValueError):
        resolucao = H3_RESOLUTION_PADRAO
    area_km2 = float(h3.average_hexagon_area(resolucao, unit="km^2"))
    densidade.loc[mask] = pop.loc[mask] / area_km2
    return densidade


def classificar_motivo_nao_elegivel(
    *,
    score_setor_2022_calibrado: float | None,
    coverage_pct_setor_2022: float | None,
    qualidade_join_uf: str | None,
    flag_join_uf_restrito: bool,
    flag_baixa_pop_setor: bool,
    densidade_pop_setor_hab_km2: float | None,
    score_priorizacao: float,
) -> str:
    """Explica por que um hex nao pode usar a camada censitaria no fluxo hibrido."""
    if pd.isna(score_setor_2022_calibrado):
        return "sem_score_censitario"
    if pd.isna(coverage_pct_setor_2022) or float(coverage_pct_setor_2022) < COVERAGE_MIN_SETOR:
        return "coverage_baixa"
    if str(qualidade_join_uf) not in JOIN_CLASSES_ELEGIVEIS:
        return "join_uf_fora_regra"
    if bool(flag_join_uf_restrito):
        return "join_uf_restrito"
    if pd.isna(densidade_pop_setor_hab_km2):
        return "densidade_indisponivel"
    if bool(flag_baixa_pop_setor) or float(densidade_pop_setor_hab_km2) < DENSIDADE_MIN_HAB_KM2:
        return "densidade_abaixo_piso"
    return "elegivel"


def calcular_score_expansao_hibrido(
    score_priorizacao: pd.Series,
    score_setor_2022_calibrado: pd.Series,
    flag_hex_hibrido_elegivel: pd.Series,
) -> pd.Series:
    """Mantem M1 como camada primaria e usa o censitario so como desempate local."""
    bonus_local = np.where(
        flag_hex_hibrido_elegivel.fillna(False),
        pd.to_numeric(score_setor_2022_calibrado, errors="coerce").fillna(0.0) / LOCAL_BONUS_DIVISOR,
        0.0,
    )
    return pd.to_numeric(score_priorizacao, errors="coerce").fillna(0.0) + bonus_local


def _load_m1_dashboard(dashboard_path: Path, structural_path: Path) -> pd.DataFrame:
    dashboard_cols = [
        "hex_id",
        "uf",
        "cidade",
        "score_priorizacao",
        "score_oficial",
        "rank_brasil",
        "rank_uf",
        "rank_cidade",
        "hex_score_estrutural",
        "renda_per_capita",
        "populacao_proxy",
        "faixa_oportunidade",
        "flag_viavel",
        "flag_prioridade",
    ]
    structural_cols = ["hex_id", "cod_municipio", "nome_municipio"]
    dashboard = pd.read_parquet(dashboard_path, columns=dashboard_cols)
    structural = pd.read_parquet(structural_path, columns=structural_cols)
    df = dashboard.merge(structural, on="hex_id", how="left")
    nome_limpo = df["nome_municipio"].fillna("").astype(str).str.strip()
    df["nome_municipio"] = np.where(nome_limpo.ne(""), nome_limpo, df["cidade"])
    return df


def _padronizar_censo(df: pd.DataFrame, *, fonte: str) -> pd.DataFrame:
    available = set(df.columns)
    rename_map = {}
    if "classe_join_uf" in available and "qualidade_join_uf" not in available:
        rename_map["classe_join_uf"] = "qualidade_join_uf"
    if "status_espacial_piloto_expandido_uf" in available and "status_espacial_uf" not in available:
        rename_map["status_espacial_piloto_expandido_uf"] = "status_espacial_uf"
    if rename_map:
        df = df.rename(columns=rename_map)

    keep_cols = [
        "hex_id",
        "uf",
        "cod_municipio",
        "nome_municipio",
        "pop_total_setor_2022",
        "score_setor_2022_calibrado",
        "coverage_pct_setor_2022",
        "qualidade_join_uf",
        "flag_join_uf_restrito",
        "flag_baixa_pop_setor",
        "flag_outlier_espacial",
        "status_espacial_uf",
    ]
    cols = [col for col in keep_cols if col in df.columns]
    out = df[cols].copy()
    for col, default in {
        "pop_total_setor_2022": np.nan,
        "flag_join_uf_restrito": False,
        "flag_baixa_pop_setor": False,
        "flag_outlier_espacial": False,
        "status_espacial_uf": pd.NA,
    }.items():
        if col not in out.columns:
            out[col] = default
    out["fonte_camada_censitaria"] = fonte
    return out


def _load_censo(
    censo_core_path: Path,
    censo_expanded_path: Path,
    censo_nacional_path: Path | None = None,
) -> pd.DataFrame:
    partes = [
        _padronizar_censo(pd.read_parquet(censo_core_path), fonte="fase_a_calibrada"),
        _padronizar_censo(
            pd.read_parquet(censo_expanded_path),
            fonte="fase_a_calibrada_piloto_expandido",
        ),
    ]
    if censo_nacional_path is not None and censo_nacional_path.exists():
        partes.append(
            _padronizar_censo(
                pd.read_parquet(censo_nacional_path),
                fonte="fase_a_calibrada_nacional",
            )
        )
    # Ordem de prioridade na deduplicacao: core > expandido > nacional
    censo = pd.concat(partes, ignore_index=True)
    censo = censo.drop_duplicates(subset=["hex_id"], keep="first")
    return censo


def _rank_desc(df: pd.DataFrame, sort_cols: list[str], group_cols: list[str] | None = None) -> pd.Series:
    """Retorna rank denso via ordenacao deterministica e cumcount."""
    work = df.reset_index().copy()
    ascending = [False if col != "hex_id" else True for col in sort_cols]
    ordered = work.sort_values(sort_cols, ascending=ascending, kind="mergesort")
    if group_cols:
        ranks = ordered.groupby(group_cols, dropna=False).cumcount() + 1
    else:
        ranks = pd.Series(np.arange(1, len(ordered) + 1), index=ordered.index)
    return ranks.reindex(work.index).set_axis(work["index"]).sort_index()


def _build_municipio_summary(df: pd.DataFrame) -> pd.DataFrame:
    municipio = (
        df.groupby(["uf", "cod_municipio", "nome_municipio"], dropna=False)
        .agg(
            score_priorizacao_municipio=("score_priorizacao", "max"),
            hex_score_estrutural_municipio=("hex_score_estrutural", "max"),
            renda_per_capita_municipio=("renda_per_capita", "max"),
            populacao_proxy_municipio=("populacao_proxy", "max"),
            total_hex_municipio=("hex_id", "size"),
            total_hex_censo_elegivel=("flag_censo_elegivel", "sum"),
        )
        .reset_index()
    )

    sort_cols = [
        "score_priorizacao_municipio",
        "renda_per_capita_municipio",
        "populacao_proxy_municipio",
        "cod_municipio",
    ]
    municipio["rank_municipio_uf"] = _rank_desc(municipio, sort_cols, group_cols=["uf"]).astype(int)
    municipio["rank_municipio_brasil"] = _rank_desc(municipio, sort_cols).astype(int)
    municipio["total_municipios_uf"] = municipio.groupby("uf")["cod_municipio"].transform("size")
    municipio["corte_top_municipio_uf"] = municipio["total_municipios_uf"].apply(
        lambda total: calcular_corte_top(int(total), TOP_MUNICIPIO_PCT)
    )
    municipio["top_municipio"] = municipio["rank_municipio_uf"] <= municipio["corte_top_municipio_uf"]
    municipio["municipio_censo_disponivel"] = municipio["total_hex_censo_elegivel"] > 0
    municipio["top_municipio_hibrido"] = municipio["top_municipio"] & municipio["municipio_censo_disponivel"]
    return municipio


def _aplicar_ranking_hex(df: pd.DataFrame) -> pd.DataFrame:
    eligible = df["flag_hex_hibrido_elegivel"].fillna(False)
    df["total_hex_hibrido_municipio"] = df.groupby("cod_municipio")["flag_hex_hibrido_elegivel"].transform("sum")
    df["corte_top_hex_intraurbano"] = df["total_hex_hibrido_municipio"].apply(
        lambda total: calcular_corte_top(int(total), TOP_HEX_INTRAURBANO_PCT)
    )
    df["rank_hex_intraurbano"] = pd.NA

    subset = df.loc[eligible].copy()
    if not subset.empty:
        subset["rank_hex_intraurbano"] = _rank_desc(
            subset,
            [
                "score_setor_2022_calibrado",
                "coverage_pct_setor_2022",
                "score_priorizacao",
                "hex_id",
            ],
            group_cols=["cod_municipio"],
        ).astype(int)
        df.loc[subset.index, "rank_hex_intraurbano"] = subset["rank_hex_intraurbano"]

    df["top_hex_intraurbano"] = (
        eligible
        & pd.to_numeric(df["rank_hex_intraurbano"], errors="coerce").le(df["corte_top_hex_intraurbano"])
    )
    return df


def _aplicar_recomendacoes(df: pd.DataFrame) -> pd.DataFrame:
    eligible = df["flag_hex_hibrido_elegivel"].fillna(False)
    df["rank_hibrido_brasil"] = pd.NA
    df["rank_hibrido_uf"] = pd.NA

    subset = df.loc[eligible].copy()
    if not subset.empty:
        sort_cols = [
            "score_expansao_hibrido",
            "score_setor_2022_calibrado",
            "score_priorizacao",
            "coverage_pct_setor_2022",
            "hex_id",
        ]
        subset["rank_hibrido_brasil"] = _rank_desc(subset, sort_cols).astype(int)
        subset["rank_hibrido_uf"] = _rank_desc(subset, sort_cols, group_cols=["uf"]).astype(int)
        df.loc[subset.index, "rank_hibrido_brasil"] = subset["rank_hibrido_brasil"]
        df.loc[subset.index, "rank_hibrido_uf"] = subset["rank_hibrido_uf"]

    rank_hex = pd.to_numeric(df["rank_hex_intraurbano"], errors="coerce")
    rank_brasil = pd.to_numeric(df["rank_hibrido_brasil"], errors="coerce")
    rank_uf = pd.to_numeric(df["rank_hibrido_uf"], errors="coerce")

    df["top_oportunidade_brasil"] = eligible & rank_brasil.le(TOP_OPORTUNIDADES_BRASIL)
    df["top_oportunidade_uf"] = eligible & rank_uf.le(TOP_OPORTUNIDADES_POR_UF)
    df["top_oportunidade_municipio"] = eligible & rank_hex.le(TOP_OPORTUNIDADES_POR_MUNICIPIO)
    df["flag_monitoramento_prioritario"] = (
        df["top_oportunidade_brasil"] | df["top_oportunidade_uf"] | df["top_oportunidade_municipio"]
    )
    return df


def construir_dataset_hibrido(
    *,
    dashboard_path: Path = DEFAULT_DASHBOARD_PATH,
    structural_path: Path = DEFAULT_M1_STRUCTURAL_PATH,
    censo_core_path: Path = DEFAULT_CENSO_CORE_PATH,
    censo_expanded_path: Path = DEFAULT_CENSO_EXPANDED_PATH,
    censo_nacional_path: Path | None = DEFAULT_CENSO_NACIONAL_PATH,
) -> pd.DataFrame:
    """Constroi dataset hex-level pronto para decisao do modelo hibrido."""
    m1 = _load_m1_dashboard(dashboard_path, structural_path)
    censo = _load_censo(censo_core_path, censo_expanded_path, censo_nacional_path)
    df = m1.merge(censo, on="hex_id", how="left", suffixes=("", "_censo"))

    if "cod_municipio_censo" in df.columns:
        df["cod_municipio"] = df["cod_municipio"].fillna(df["cod_municipio_censo"])
    if "nome_municipio_censo" in df.columns:
        nome_base = df["nome_municipio"].fillna("").astype(str).str.strip()
        nome_censo = df["nome_municipio_censo"].fillna("").astype(str).str.strip()
        df["nome_municipio"] = np.where(nome_base.ne(""), nome_base, nome_censo)

    for col, default in {
        "qualidade_join_uf": pd.NA,
        "pop_total_setor_2022": np.nan,
        "densidade_pop_setor_hab_km2": np.nan,
        "flag_join_uf_restrito": False,
        "flag_baixa_pop_setor": False,
        "flag_outlier_espacial": False,
        "status_espacial_uf": pd.NA,
    }.items():
        if col not in df.columns:
            df[col] = default
    df["densidade_pop_setor_hab_km2"] = pd.to_numeric(
        df["densidade_pop_setor_hab_km2"],
        errors="coerce",
    )
    densidade_calculada = calcular_densidade_pop_setor_hab_km2(
        df["hex_id"],
        df["pop_total_setor_2022"],
    )
    df["densidade_pop_setor_hab_km2"] = df["densidade_pop_setor_hab_km2"].where(
        df["densidade_pop_setor_hab_km2"].notna(),
        densidade_calculada,
    )
    flag_baixa_legado = pd.Series(df["flag_baixa_pop_setor"], dtype="boolean").fillna(False).astype(bool)
    piso_densidade = df["densidade_pop_setor_hab_km2"].lt(DENSIDADE_MIN_HAB_KM2).fillna(False)
    df["flag_baixa_pop_setor"] = (flag_baixa_legado | piso_densidade).astype(bool)

    df["motivo_nao_elegivel_censo"] = df.apply(
        lambda row: classificar_motivo_nao_elegivel(
            score_setor_2022_calibrado=row.get("score_setor_2022_calibrado"),
            coverage_pct_setor_2022=row.get("coverage_pct_setor_2022"),
            qualidade_join_uf=row.get("qualidade_join_uf"),
            flag_join_uf_restrito=bool(row.get("flag_join_uf_restrito", False)),
            flag_baixa_pop_setor=bool(row.get("flag_baixa_pop_setor", False)),
            densidade_pop_setor_hab_km2=row.get("densidade_pop_setor_hab_km2"),
            score_priorizacao=float(row["score_priorizacao"]),
        ),
        axis=1,
    )
    df["flag_censo_disponivel"] = df["score_setor_2022_calibrado"].notna()
    df["flag_censo_elegivel"] = df["motivo_nao_elegivel_censo"].eq("elegivel")

    municipio = _build_municipio_summary(df)
    df = df.merge(
        municipio[
            [
                "uf",
                "cod_municipio",
                "nome_municipio",
                "score_priorizacao_municipio",
                "hex_score_estrutural_municipio",
                "renda_per_capita_municipio",
                "populacao_proxy_municipio",
                "total_hex_municipio",
                "total_hex_censo_elegivel",
                "rank_municipio_uf",
                "rank_municipio_brasil",
                "total_municipios_uf",
                "corte_top_municipio_uf",
                "top_municipio",
                "municipio_censo_disponivel",
                "top_municipio_hibrido",
            ]
        ],
        on=["uf", "cod_municipio", "nome_municipio"],
        how="left",
    )

    df["flag_hex_hibrido_elegivel"] = df["top_municipio"].fillna(False) & df["flag_censo_elegivel"]
    df["score_expansao_hibrido"] = calcular_score_expansao_hibrido(
        df["score_priorizacao"],
        df["score_setor_2022_calibrado"],
        df["flag_hex_hibrido_elegivel"],
    )
    df["criterio_score_expansao_hibrido"] = (
        "M1_primario_com_desempate_local_censitario"
    )
    df["camada_modelo_hibrido"] = np.where(
        df["flag_hex_hibrido_elegivel"],
        "municipio_m1_mais_hex_censitario",
        "somente_m1_ou_fora_escopo_censitario",
    )
    df["data_snapshot_hibrido"] = date.today().isoformat()

    df = _aplicar_ranking_hex(df)
    df = _aplicar_recomendacoes(df)

    df["score_censitario_ponto_monitoramento"] = df["score_setor_2022_calibrado"]
    df["score_m1_ponto_monitoramento"] = df["score_priorizacao"]
    df["janela_validacao_monitoramento_meses"] = "6-12"
    return df


def construir_base_monitoramento(df: pd.DataFrame) -> pd.DataFrame:
    """Cria base pronta para registrar novas aberturas e validar o modelo depois."""
    monitoring = df[df["flag_monitoramento_prioritario"]].copy()
    if monitoring.empty:
        return monitoring

    monitoring = monitoring.sort_values(
        ["top_oportunidade_brasil", "top_oportunidade_uf", "top_oportunidade_municipio", "score_expansao_hibrido"],
        ascending=[False, False, False, False],
        kind="mergesort",
    ).reset_index(drop=True)

    monitoring["monitoramento_id"] = (
        monitoring["uf"].astype(str)
        + "_"
        + monitoring["cod_municipio"].astype(str)
        + "_"
        + monitoring["hex_id"].astype(str)
    )
    monitoring["status_monitoramento"] = "pronto_para_registro"
    monitoring["data_registro_modelo"] = date.today().isoformat()
    monitoring["data_decisao_abertura"] = pd.NA
    monitoring["data_assinatura_ponto"] = pd.NA
    monitoring["data_abertura_unidade"] = pd.NA
    monitoring["unidade_id"] = pd.NA
    monitoring["faturamento_6m"] = pd.NA
    monitoring["faturamento_12m"] = pd.NA
    monitoring["ativos_pag_6m"] = pd.NA
    monitoring["alunos_total_6m"] = pd.NA
    monitoring["churn_6m"] = pd.NA
    monitoring["conversao_6m"] = pd.NA
    monitoring["validacao_6m_status"] = pd.NA
    monitoring["validacao_12m_status"] = pd.NA
    monitoring["observacao_validacao"] = pd.NA
    return monitoring


def gerar_relatorio(df: pd.DataFrame, monitoring: pd.DataFrame) -> str:
    eligible = df[df["flag_hex_hibrido_elegivel"]].copy()
    covered_ufs = sorted(df.loc[df["flag_censo_disponivel"], "uf"].dropna().unique().tolist())

    municipio_summary = (
        df[df["top_municipio_hibrido"]]
        .drop_duplicates(subset=["uf", "cod_municipio"])
        .groupby("uf", dropna=False)
        .agg(
            municipios_hibridos=("cod_municipio", "size"),
            score_medio_municipio=("score_priorizacao_municipio", "mean"),
        )
        .reset_index()
        .sort_values(["municipios_hibridos", "score_medio_municipio"], ascending=[False, False])
    )

    top_brasil = (
        eligible[eligible["top_oportunidade_brasil"]]
        .sort_values(["rank_hibrido_brasil", "hex_id"], ascending=[True, True], kind="mergesort")
        .head(20)
    )

    linhas = [
        "# Modelo Hibrido de Expansao",
        "",
        f"> Data: {date.today().isoformat()}",
        "> Status: GO para uso pratico controlado como camada complementar ao M1",
        "",
        "## Regra final do modelo",
        "",
        "1. O municipio e aprovado primeiro pelo M1 via `score_priorizacao`.",
        f"2. O corte municipal usa top {int(TOP_MUNICIPIO_PCT * 100)}% de municipios por UF, com minimo operacional de 1 municipio por UF.",
        "3. So depois disso o censitario entra para ranquear hexes dentro dos municipios aprovados.",
        "4. O censitario so participa quando o hex passa nas regras de robustez: score disponivel, coverage >= 85%, join UF classe A/B, sem restricao de join e com densidade setorial minima de 5.000 hab/km2.",
        "5. `score_expansao_hibrido` preserva o M1 como criterio principal e usa o censitario apenas como desempate/refino local.",
        "",
        "## Cobertura operacional",
        "",
        f"- UFs com camada censitaria disponivel: {', '.join(covered_ufs)}",
        f"- Hexes com score censitario disponivel: {int(df['flag_censo_disponivel'].sum()):,}",
        f"- Hexes elegiveis no fluxo hibrido: {int(df['flag_hex_hibrido_elegivel'].sum()):,}",
        f"- Municipios top M1 com camada local utilizavel: {int(df[['uf', 'cod_municipio', 'top_municipio_hibrido']].drop_duplicates()['top_municipio_hibrido'].sum()):,}",
        f"- Registros priorizados para monitoramento futuro: {len(monitoring):,}",
        "",
        "## Como usar na pratica",
        "",
        "- Primeiro leia `top_municipio` e `rank_municipio_uf` para decidir em quais cidades vale aprofundar a abertura.",
        "- Depois use `rank_hex_intraurbano`, `top_hex_intraurbano` e `top_oportunidade_municipio` para montar shortlist de bairros/hex dentro dessas cidades.",
        "- `top_oportunidade_brasil` e `top_oportunidade_uf` servem como carteira executiva de priorizacao imediata.",
        "- `score_priorizacao` continua sendo o score oficial; `score_expansao_hibrido` existe para ordenar a fila operacional do modelo combinado.",
        "",
        "## Municipios hibridos por UF",
        "",
        "| UF | Municipios top M1 com camada local | Score medio municipal |",
        "| --- | --- | --- |",
    ]

    for row in municipio_summary.itertuples(index=False):
        linhas.append(
            f"| {row.uf} | {int(row.municipios_hibridos)} | {float(row.score_medio_municipio):.2f} |"
        )

    linhas += [
        "",
        "## Top 20 oportunidades Brasil",
        "",
        "| Rank Brasil | UF | Municipio | Hex | Score M1 | Score censitario | Score hibrido | Rank intraurbano |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]

    for row in top_brasil.itertuples(index=False):
        linhas.append(
            f"| {int(row.rank_hibrido_brasil)} | {row.uf} | {row.nome_municipio} | {row.hex_id} | "
            f"{float(row.score_priorizacao):.2f} | {float(row.score_setor_2022_calibrado):.2f} | "
            f"{float(row.score_expansao_hibrido):.5f} | {int(row.rank_hex_intraurbano)} |"
        )

    linhas += [
        "",
        "## Monitoramento futuro (6-12 meses)",
        "",
        "- Base criada em `data/outputs/monitoramento_expansao_hibrido_base.parquet`.",
        "- Cada registro ja leva `score_censitario_ponto_monitoramento`, `score_m1_ponto_monitoramento` e `score_expansao_hibrido` do ponto recomendado.",
        "- Quando uma nova unidade for aprovada, basta preencher `data_decisao_abertura`, `data_abertura_unidade` e as metricas de 6/12 meses para validar aderencia do modelo.",
        "",
        "## Restricoes mantidas",
        "",
        "- O M1 oficial nao foi alterado.",
        "- `score_priorizacao` nao foi substituido.",
        "- O censitario segue como camada complementar local, nao como score oficial nacional.",
        "",
    ]
    return "\n".join(linhas)


def executar_pipeline(
    *,
    dashboard_path: Path = DEFAULT_DASHBOARD_PATH,
    structural_path: Path = DEFAULT_M1_STRUCTURAL_PATH,
    censo_core_path: Path = DEFAULT_CENSO_CORE_PATH,
    censo_expanded_path: Path = DEFAULT_CENSO_EXPANDED_PATH,
    censo_nacional_path: Path | None = DEFAULT_CENSO_NACIONAL_PATH,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    report_path: Path = DEFAULT_REPORT_PATH,
    monitoring_path: Path = DEFAULT_MONITORING_PATH,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = construir_dataset_hibrido(
        dashboard_path=dashboard_path,
        structural_path=structural_path,
        censo_core_path=censo_core_path,
        censo_expanded_path=censo_expanded_path,
        censo_nacional_path=censo_nacional_path,
    )
    monitoring = construir_base_monitoramento(df)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    monitoring_path.parent.mkdir(parents=True, exist_ok=True)

    df.to_parquet(output_path, index=False)
    monitoring.to_parquet(monitoring_path, index=False)
    report_path.write_text(gerar_relatorio(df, monitoring), encoding="utf-8")
    return df, monitoring


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera o modelo hibrido de expansao")
    parser.add_argument("--dashboard", type=Path, default=DEFAULT_DASHBOARD_PATH)
    parser.add_argument("--m1-structural", type=Path, default=DEFAULT_M1_STRUCTURAL_PATH)
    parser.add_argument("--censo-core", type=Path, default=DEFAULT_CENSO_CORE_PATH)
    parser.add_argument("--censo-expanded", type=Path, default=DEFAULT_CENSO_EXPANDED_PATH)
    parser.add_argument("--censo-nacional", type=Path, default=DEFAULT_CENSO_NACIONAL_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--monitoring", type=Path, default=DEFAULT_MONITORING_PATH)
    args = parser.parse_args()

    df, monitoring = executar_pipeline(
        dashboard_path=args.dashboard,
        structural_path=args.m1_structural,
        censo_core_path=args.censo_core,
        censo_expanded_path=args.censo_expanded,
        censo_nacional_path=args.censo_nacional,
        output_path=args.output,
        report_path=args.report,
        monitoring_path=args.monitoring,
    )

    print("=" * 60)
    print("Modelo hibrido de expansao gerado")
    print("=" * 60)
    print(f"Hexes totais: {len(df):,}")
    print(f"Hexes elegiveis no hibrido: {int(df['flag_hex_hibrido_elegivel'].sum()):,}")
    print(f"Registros de monitoramento: {len(monitoring):,}")
    print(f"Output: {args.output}")
    print(f"Relatorio: {args.report}")
    print(f"Monitoramento: {args.monitoring}")


if __name__ == "__main__":
    main()
