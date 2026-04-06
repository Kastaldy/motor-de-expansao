from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

try:
    from jobs.pipelines.ibge_censo import carregar_lookup_municipios_ibge
except ModuleNotFoundError:
    from ibge_censo import carregar_lookup_municipios_ibge

SOURCE_PATH = Path("data/staging/hexagonos_brasil_oportunidades.parquet")
MUNICIPIOS_LOOKUP_PATH = Path("data/ibge/municipios_nomes_ibge.parquet")
DASHBOARD_PATH = Path("data/outputs/hexagonos_brasil_dashboard.parquet")
TOP_OPORTUNIDADES_PATH = Path("data/outputs/top_oportunidades_resumo.csv")
RESUMO_UF_PATH = Path("data/outputs/resumo_por_uf.csv")
MAPA_SAMPLE_PATH = Path("data/outputs/hexagonos_mapa_sample.parquet")
RESUMO_EXECUTIVO_PATH = Path("data/reports/resumo_executivo_fase1.md")

FAIXAS_OPORTUNIDADE = [
    "prioridade_maxima",
    "alta",
    "media",
    "baixa",
    "descartado",
]

DASHBOARD_COLUMNS = [
    "hex_id",
    "lat",
    "lng",
    "uf",
    "cidade",
    "regiao",
    "hex_score_estrutural",
    "score_oficial",
    "score_oficial_nome",
    "score_percentil_nacional",
    "faixa_oportunidade",
    "flag_viavel",
    "flag_prioridade",
    "rank_brasil",
    "rank_uf",
    "rank_cidade",
    "renda_per_capita",
    "renda_target_proxy",
    "populacao_proxy",
    "proxy_populacao",
    "renda_pct_nacional",
    "pop_pct_nacional",
    "ajuste_executivo",
    "score_priorizacao",
    "criterio_prioridade",
    "threshold_prioridade_uf",
    "osm_status",
    "fonte_demografica",
    "fonte_renda",
    "fonte_populacao",
    "nivel_geografico_ibge",
    "fallback_setor_censitario",
    "motivo_fallback_setor",
    "fonte_geometria_ibge",
    "metodo_atribuicao_municipio",
    "data_referencia_ibge",
    "motivo_priorizacao",
    "motivo_alerta",
    "observacao_estrategica",
]

SOURCE_COLUMNS = [
    "hex_id",
    "lat",
    "lng",
    "uf",
    "regiao",
    "cod_municipio",
    "municipio_label",
    "nome_municipio",
    "populacao_proxy",
    "pop_18_45",
    "renda_pct_nacional",
    "pop_pct_nacional",
    "hex_score_estrutural",
    "ajuste_executivo",
    "score_priorizacao",
    "score_oficial",
    "score_oficial_nome",
    "score_percentil_nacional",
    "faixa_oportunidade",
    "flag_viavel",
    "flag_prioridade",
    "rank_brasil",
    "rank_uf",
    "rank_cidade",
    "renda_per_capita",
    "renda_target_proxy",
    "criterio_prioridade",
    "threshold_prioridade_uf",
    "osm_status",
    "fonte_demografica",
    "fonte_renda",
    "fonte_populacao",
    "nivel_geografico_ibge",
    "fallback_setor_censitario",
    "motivo_fallback_setor",
    "fonte_geometria_ibge",
    "metodo_atribuicao_municipio",
    "data_referencia_ibge",
    "motivo_priorizacao",
    "motivo_alerta",
    "observacao_estrategica",
]


def _pick_first_existing(df: pd.DataFrame, columns: list[str], default: str = "") -> pd.Series:
    for column in columns:
        if column in df.columns:
            return df[column]
    return pd.Series([default] * len(df), index=df.index, dtype="string")


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _to_markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_sem dados_"

    data = df.copy()
    for column in data.columns:
        if pd.api.types.is_float_dtype(data[column]):
            data[column] = data[column].map(lambda value: f"{value:.2f}")

    headers = [str(column) for column in data.columns]
    align = ["---"] * len(headers)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(align) + " |",
    ]
    for row in data.itertuples(index=False, name=None):
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def load_oportunidades_source(path: Path | str = SOURCE_PATH) -> pd.DataFrame:
    path = Path(path)
    available_columns = pq.read_schema(path).names
    columns = [column for column in SOURCE_COLUMNS if column in available_columns]
    return pd.read_parquet(path, columns=columns)


def load_municipios_lookup(path: Path | str = MUNICIPIOS_LOOKUP_PATH) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        return carregar_lookup_municipios_ibge(path=path)
    df_lookup = pd.read_parquet(path, columns=["cod_municipio", "nome_municipio"]).copy()
    df_lookup["cod_municipio"] = df_lookup["cod_municipio"].astype("string").str.extract(r"(\d{7})")[0]
    df_lookup["nome_municipio"] = df_lookup["nome_municipio"].astype("string").str.strip()
    return df_lookup.dropna(subset=["cod_municipio"]).drop_duplicates(subset=["cod_municipio"])


def build_dashboard_dataset(
    df_source: pd.DataFrame,
    df_municipios_lookup: pd.DataFrame | None = None,
) -> pd.DataFrame:
    cod_municipio = _pick_first_existing(df_source, ["cod_municipio"]).astype("string").str.extract(r"(\d{7})")[0]
    cidade = (
        _pick_first_existing(df_source, ["municipio_label", "nome_municipio", "cidade"])
        .fillna("")
        .astype("string")
        .str.strip()
    )
    if df_municipios_lookup is not None and not df_municipios_lookup.empty:
        mapping = (
            df_municipios_lookup.set_index("cod_municipio")["nome_municipio"]
            .astype("string")
        )
        cidade_lookup = cod_municipio.map(mapping)
        cidade = cidade.where(~cidade.str.fullmatch(r"\d{7}"), cidade_lookup)
        cidade = cidade.where(cidade.fillna("").str.strip().ne(""), cidade_lookup)

    proxy_populacao = pd.to_numeric(
        _pick_first_existing(df_source, ["populacao_proxy", "pop_18_45", "proxy_populacao"]),
        errors="coerce",
    )

    dashboard = pd.DataFrame(
        {
            "hex_id": _pick_first_existing(df_source, ["hex_id"]).astype("string").str.strip(),
            "lat": pd.to_numeric(_pick_first_existing(df_source, ["lat"]), errors="coerce"),
            "lng": pd.to_numeric(_pick_first_existing(df_source, ["lng"]), errors="coerce"),
            "uf": _pick_first_existing(df_source, ["uf"]).astype("string").str.upper().str.strip(),
            "cidade": cidade,
            "regiao": _pick_first_existing(df_source, ["regiao"]).astype("string").str.upper().str.strip(),
            "hex_score_estrutural": pd.to_numeric(
                _pick_first_existing(df_source, ["hex_score_estrutural"]),
                errors="coerce",
            ).round(2),
            "ajuste_executivo": pd.to_numeric(
                _pick_first_existing(df_source, ["ajuste_executivo"]),
                errors="coerce",
            ).round(2),
            "score_priorizacao": pd.to_numeric(
                _pick_first_existing(df_source, ["score_priorizacao", "score_oficial", "hex_score_estrutural"]),
                errors="coerce",
            ).round(2),
            "score_oficial": pd.to_numeric(
                _pick_first_existing(df_source, ["score_oficial", "score_priorizacao", "hex_score_estrutural"]),
                errors="coerce",
            ).round(2),
            "score_oficial_nome": _pick_first_existing(
                df_source,
                ["score_oficial_nome"],
                default="score_priorizacao",
            ).astype("string"),
            "score_percentil_nacional": pd.to_numeric(
                _pick_first_existing(df_source, ["score_percentil_nacional"]),
                errors="coerce",
            ).round(2),
            "faixa_oportunidade": pd.Categorical(
                _pick_first_existing(df_source, ["faixa_oportunidade"]).astype("string"),
                categories=FAIXAS_OPORTUNIDADE,
                ordered=True,
            ),
            "flag_viavel": _pick_first_existing(df_source, ["flag_viavel"]).fillna(False).astype(bool),
            "flag_prioridade": _pick_first_existing(df_source, ["flag_prioridade"]).fillna(False).astype(bool),
            "rank_brasil": pd.to_numeric(_pick_first_existing(df_source, ["rank_brasil"]), errors="coerce").astype("int64"),
            "rank_uf": pd.to_numeric(_pick_first_existing(df_source, ["rank_uf"]), errors="coerce").astype("int64"),
            "rank_cidade": pd.to_numeric(_pick_first_existing(df_source, ["rank_cidade"]), errors="coerce").astype("int64"),
            "renda_per_capita": pd.to_numeric(
                _pick_first_existing(df_source, ["renda_per_capita"]),
                errors="coerce",
            ).round(2),
            "renda_target_proxy": pd.to_numeric(
                _pick_first_existing(df_source, ["renda_target_proxy"]),
                errors="coerce",
            ).round(2),
            "populacao_proxy": proxy_populacao,
            "proxy_populacao": proxy_populacao,
            "renda_pct_nacional": pd.to_numeric(
                _pick_first_existing(df_source, ["renda_pct_nacional"]),
                errors="coerce",
            ).round(6),
            "pop_pct_nacional": pd.to_numeric(
                _pick_first_existing(df_source, ["pop_pct_nacional"]),
                errors="coerce",
            ).round(6),
            "criterio_prioridade": _pick_first_existing(df_source, ["criterio_prioridade"]).astype("string"),
            "threshold_prioridade_uf": pd.to_numeric(
                _pick_first_existing(df_source, ["threshold_prioridade_uf"]),
                errors="coerce",
            ).round(2),
            "osm_status": _pick_first_existing(
                df_source,
                ["osm_status"],
                default="nao_aplicado_mvp_nacional",
            ).astype("string"),
            "fonte_demografica": _pick_first_existing(df_source, ["fonte_demografica"]).astype("string"),
            "fonte_renda": _pick_first_existing(df_source, ["fonte_renda"]).astype("string"),
            "fonte_populacao": _pick_first_existing(df_source, ["fonte_populacao"]).astype("string"),
            "nivel_geografico_ibge": _pick_first_existing(df_source, ["nivel_geografico_ibge"]).astype("string"),
            "fallback_setor_censitario": _pick_first_existing(
                df_source,
                ["fallback_setor_censitario"],
            ).fillna(True).astype(bool),
            "motivo_fallback_setor": _pick_first_existing(df_source, ["motivo_fallback_setor"]).astype("string"),
            "fonte_geometria_ibge": _pick_first_existing(df_source, ["fonte_geometria_ibge"]).astype("string"),
            "metodo_atribuicao_municipio": _pick_first_existing(
                df_source,
                ["metodo_atribuicao_municipio"],
            ).astype("string"),
            "data_referencia_ibge": _pick_first_existing(
                df_source,
                ["data_referencia_ibge"],
                default="censo_2022",
            ).astype("string"),
            "motivo_priorizacao": _pick_first_existing(df_source, ["motivo_priorizacao"]).astype("string"),
            "motivo_alerta": _pick_first_existing(df_source, ["motivo_alerta"]).astype("string"),
            "observacao_estrategica": _pick_first_existing(df_source, ["observacao_estrategica"]).astype("string"),
        }
    )

    dashboard = dashboard.sort_values("rank_brasil", kind="stable").reset_index(drop=True)
    validate_dashboard_dataset(dashboard)
    return dashboard[DASHBOARD_COLUMNS].copy()


def validate_dashboard_dataset(df_dashboard: pd.DataFrame) -> None:
    missing = [column for column in DASHBOARD_COLUMNS if column not in df_dashboard.columns]
    if missing:
        raise ValueError(f"Colunas obrigatorias ausentes no dashboard: {missing}")

    if df_dashboard["hex_id"].duplicated().any():
        duplicated = int(df_dashboard["hex_id"].duplicated().sum())
        raise ValueError(f"Dashboard possui {duplicated} hexagonos duplicados")

    if df_dashboard["lat"].isna().any() or df_dashboard["lng"].isna().any():
        raise ValueError("Dashboard possui coordenadas nulas")

    if df_dashboard["cidade"].fillna("").str.strip().eq("").any():
        raise ValueError("Dashboard possui cidade vazia")

    if df_dashboard["populacao_proxy"].isna().any():
        raise ValueError("Dashboard possui populacao_proxy nula")

    if df_dashboard["rank_brasil"].duplicated().any():
        duplicated = int(df_dashboard["rank_brasil"].duplicated().sum())
        raise ValueError(f"Dashboard possui {duplicated} ranks Brasil duplicados")


def build_top_oportunidades_resumo(df_dashboard: pd.DataFrame, top_n: int = 500) -> pd.DataFrame:
    resumo = (
        df_dashboard[df_dashboard["flag_viavel"]]
        .sort_values("rank_brasil", kind="stable")
        .head(top_n)[
            [
                "rank_brasil",
                "uf",
                "cidade",
                "score_oficial",
                "score_oficial_nome",
                "score_priorizacao",
                "ajuste_executivo",
                "hex_score_estrutural",
                "faixa_oportunidade",
                "motivo_priorizacao",
                "observacao_estrategica",
            ]
        ]
        .copy()
    )
    resumo["faixa_oportunidade"] = resumo["faixa_oportunidade"].astype("string")
    return resumo


def build_resumo_por_uf(df_dashboard: pd.DataFrame) -> pd.DataFrame:
    grouped = df_dashboard.groupby("uf", sort=True)
    resumo = grouped.agg(
        total_hexagonos=("hex_id", "size"),
        total_viaveis=("flag_viavel", "sum"),
        score_medio=("score_oficial", "mean"),
        qtd_prioridade_maxima=("faixa_oportunidade", lambda values: int((values == "prioridade_maxima").sum())),
        qtd_alta=("faixa_oportunidade", lambda values: int((values == "alta").sum())),
    )
    score_p90 = grouped["score_oficial"].quantile(0.90).rename("score_p90")
    resumo = resumo.join(score_p90).reset_index()
    resumo["pct_viaveis"] = (resumo["total_viaveis"] / resumo["total_hexagonos"] * 100).round(2)
    resumo["score_medio"] = resumo["score_medio"].round(2)
    resumo["score_p90"] = resumo["score_p90"].round(2)
    resumo = resumo[
        [
            "uf",
            "total_hexagonos",
            "total_viaveis",
            "pct_viaveis",
            "score_medio",
            "score_p90",
            "qtd_prioridade_maxima",
            "qtd_alta",
        ]
    ]
    return resumo.sort_values(
        ["score_medio", "pct_viaveis", "total_viaveis", "uf"],
        ascending=[False, False, False, True],
        kind="stable",
    ).reset_index(drop=True)


def build_hexagonos_mapa_sample(df_dashboard: pd.DataFrame, top_pct: float = 0.30) -> pd.DataFrame:
    sample_size = max(1, math.ceil(len(df_dashboard) * top_pct))
    sample = (
        df_dashboard.sort_values("rank_brasil", kind="stable")
        .head(sample_size)
        .copy()
    )
    validate_dashboard_dataset(sample)
    return sample


def build_resumo_executivo(
    df_dashboard: pd.DataFrame,
    resumo_por_uf: pd.DataFrame,
    mapa_sample: pd.DataFrame,
) -> str:
    total_hexagonos = len(df_dashboard)
    total_viaveis = int(df_dashboard["flag_viavel"].sum())
    pct_viaveis = round(total_viaveis / total_hexagonos * 100, 2) if total_hexagonos else 0.0

    top_cidades = (
        df_dashboard[df_dashboard["flag_viavel"]]
        .groupby(["uf", "cidade"], sort=False)
        .agg(
            oportunidades_viaveis=("hex_id", "size"),
            score_medio=("score_oficial", "mean"),
            melhor_rank_brasil=("rank_brasil", "min"),
        )
        .reset_index()
        .sort_values(
            ["oportunidades_viaveis", "score_medio", "melhor_rank_brasil", "uf", "cidade"],
            ascending=[False, False, True, True, True],
            kind="stable",
        )
        .head(10)
    )
    top_cidades["score_medio"] = top_cidades["score_medio"].round(2)

    top_ufs = (
        resumo_por_uf[
            ["uf", "total_viaveis", "pct_viaveis", "score_medio", "qtd_prioridade_maxima"]
        ]
        .head(10)
        .copy()
    )

    distribuicao = (
        df_dashboard["faixa_oportunidade"]
        .value_counts(dropna=False)
        .reindex(FAIXAS_OPORTUNIDADE, fill_value=0)
        .rename_axis("faixa_oportunidade")
        .reset_index(name="hexagonos")
    )
    distribuicao["pct_hexagonos"] = (distribuicao["hexagonos"] / total_hexagonos * 100).round(2)
    distribuicao["faixa_oportunidade"] = distribuicao["faixa_oportunidade"].astype("string")

    lines = [
        "# Resumo Executivo Fase 1",
        "",
        "Metricas, ranking e faixas derivados de `data/staging/hexagonos_brasil_oportunidades.parquet`, sem recalculo de score ou alteracao de regras de negocio.",
        "Score oficial de priorizacao executiva do M1 nacional: `score_priorizacao` (replicado em `score_oficial`).",
        "Base estrutural oficial preservada em `hex_score_estrutural`; ajuste executivo auditavel exposto em `ajuste_executivo`.",
        "OSM permanece `nao_aplicado_mvp_nacional` no fechamento oficial da Fase 1 e nao participa do ranking executivo.",
        "Rotulos de municipio enriquecidos apenas para exibicao via lookup oficial do IBGE em `data/ibge/municipios_nomes_ibge.parquet`.",
        "",
        "## Indicadores-chave",
        "",
        f"- total_hexagonos: {total_hexagonos:,}".replace(",", "."),
        f"- total_viaveis: {total_viaveis:,}".replace(",", "."),
        f"- pct_viaveis: {pct_viaveis:.2f}%",
        f"- amostra_mapa_top_30_pct: {len(mapa_sample):,} hexagonos".replace(",", "."),
        "",
        "## Top 10 cidades com mais oportunidades viaveis",
        "",
        _to_markdown_table(top_cidades),
        "",
        "## Top 10 UFs",
        "",
        _to_markdown_table(top_ufs),
        "",
        "## Distribuicao por faixa_oportunidade",
        "",
        _to_markdown_table(distribuicao),
        "",
    ]
    return "\n".join(lines)


def write_outputs(
    df_dashboard: pd.DataFrame,
    top_oportunidades: pd.DataFrame,
    resumo_por_uf: pd.DataFrame,
    mapa_sample: pd.DataFrame,
    resumo_executivo: str,
) -> None:
    for path in [
        DASHBOARD_PATH,
        TOP_OPORTUNIDADES_PATH,
        RESUMO_UF_PATH,
        MAPA_SAMPLE_PATH,
        RESUMO_EXECUTIVO_PATH,
    ]:
        _ensure_parent(path)

    df_dashboard.to_parquet(DASHBOARD_PATH, index=False)
    top_oportunidades.to_csv(TOP_OPORTUNIDADES_PATH, sep=";", encoding="utf-8-sig", index=False)
    resumo_por_uf.to_csv(RESUMO_UF_PATH, sep=";", encoding="utf-8-sig", index=False)
    mapa_sample.to_parquet(MAPA_SAMPLE_PATH, index=False)
    RESUMO_EXECUTIVO_PATH.write_text(resumo_executivo + "\n", encoding="utf-8")


def generate_fase1_bi_artifacts(source_path: Path | str = SOURCE_PATH) -> dict[str, pd.DataFrame | str]:
    df_source = load_oportunidades_source(source_path)
    df_municipios_lookup = load_municipios_lookup()
    df_dashboard = build_dashboard_dataset(df_source, df_municipios_lookup=df_municipios_lookup)
    top_oportunidades = build_top_oportunidades_resumo(df_dashboard)
    resumo_por_uf = build_resumo_por_uf(df_dashboard)
    mapa_sample = build_hexagonos_mapa_sample(df_dashboard)
    resumo_executivo = build_resumo_executivo(df_dashboard, resumo_por_uf, mapa_sample)
    write_outputs(df_dashboard, top_oportunidades, resumo_por_uf, mapa_sample, resumo_executivo)
    return {
        "dashboard": df_dashboard,
        "top_oportunidades": top_oportunidades,
        "resumo_por_uf": resumo_por_uf,
        "mapa_sample": mapa_sample,
        "resumo_executivo": resumo_executivo,
    }


def main() -> None:
    artifacts = generate_fase1_bi_artifacts()
    dashboard = artifacts["dashboard"]
    resumo_por_uf = artifacts["resumo_por_uf"]
    mapa_sample = artifacts["mapa_sample"]

    print("Artefatos BI gerados com sucesso.")
    print(f"Dashboard: {len(dashboard)} hexagonos")
    print(f"UFs: {len(resumo_por_uf)}")
    print(f"Mapa sample: {len(mapa_sample)} hexagonos")


if __name__ == "__main__":
    main()
