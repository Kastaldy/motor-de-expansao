from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq

from motor_expansao.dashboard.constants import (
    CENSO_TRACE_LOAD_COLS,
    HYBRID_LOAD_COLS,
    REQUIRED_COLUMNS,
)
from motor_expansao.dashboard.data import (
    _coalesce_columns,
    _prepare_censo_trace,
    _prepare_dataframe,
    _read_optional_parquet_subset,
    _read_parquet_subset,
    enrich_dashboard_data,
)
from motor_expansao.pipelines.agregar_censo_hex_da_malha import (
    DEFAULT_OUTPUT_PATH as MALHA_CENSO_PATH,
)
from motor_expansao.pipelines.agregar_censo_hex_da_malha import sobrepor_renda_da_malha
from motor_expansao.pipelines.m1.ibge_censo import carregar_lookup_municipios_ibge
from motor_expansao.pipelines.m1.provenance import write_manifest

SOURCE_PATH = Path("data/staging/hexagonos_brasil_oportunidades.parquet")
MUNICIPIOS_LOOKUP_PATH = Path("data/ibge/municipios_nomes_ibge.parquet")
DASHBOARD_PATH = Path("data/outputs/hexagonos_brasil_dashboard.parquet")
TOP_OPORTUNIDADES_PATH = Path("data/outputs/top_oportunidades_resumo.csv")
RESUMO_UF_PATH = Path("data/outputs/resumo_por_uf.csv")
MAPA_SAMPLE_PATH = Path("data/outputs/hexagonos_mapa_sample.parquet")
RESUMO_EXECUTIVO_PATH = Path("data/reports/resumo_executivo_fase1.md")

# Insumos do dataset enriquecido (derivado, NAO oficial M1). Espelham os caminhos
# lidos pelo dashboard em streamlit_app, para materializar offline o merge que hoje
# roda a frio em runtime via enrich_dashboard_data.
HYBRID_PATH = Path("data/outputs/oportunidades_expansao_hibrido.parquet")
CENSO_CORE_PATH = Path("data/staging/censo2022_setores_calibrado.parquet")
CENSO_EXPANDED_PATH = Path("data/staging/censo2022_setores_calibrado_piloto_expandido.parquet")
CENSO_NACIONAL_PATH = Path("data/staging/censo2022_setores_calibrado_nacional_completo.parquet")
CENSO_VALIDATED_PATH = Path("data/staging/censo2022_setores_validado_v2.parquet")
ESTRUTURAL_PATH = Path("data/staging/brasil_estrutural.parquet")
ENRIQUECIDO_DIR = Path("data/outputs/hexagonos_dashboard_enriquecido")

FAIXAS_OPORTUNIDADE = [
    "prioridade_maxima",
    "alta",
    "media",
    "baixa",
    "descartado",
    "inviavel",
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
        _pick_first_existing(df_source, ["populacao_proxy", "proxy_populacao"]),
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


# ---------------------------------------------------------------------------
# Dataset enriquecido particionado por UF (artefato derivado, NAO oficial M1)
# ---------------------------------------------------------------------------
# Materializa offline o resultado de enrich_dashboard_data (M1 + hibrido + censo +
# pop estrutural). Os readers replicam o caminho de carga de streamlit_app, mas
# importam apenas a camada de dados (sem streamlit), mantendo o pipeline leve.


def _read_m1_dashboard_frame(path: Path | str = DASHBOARD_PATH) -> pd.DataFrame:
    return _prepare_dataframe(_read_parquet_subset(Path(path), REQUIRED_COLUMNS))


def _read_hybrid_frame(path: Path | str = HYBRID_PATH) -> pd.DataFrame:
    return _prepare_dataframe(_read_optional_parquet_subset(Path(path), HYBRID_LOAD_COLS))


def _read_censo_trace_frame(malha_path: Path = MALHA_CENSO_PATH) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    # Ordem = precedencia da deduplicacao (drop_duplicates keep="first"), a mesma de
    # modelo_hibrido_expansao._load_censo: core > expandido > nacional. O nacional
    # (21 UFs) faltava aqui, e por isso o dataset enriquecido -- que o piloto web le --
    # so tinha censo nas 6 UFs de core+expandido.
    for path in [CENSO_CORE_PATH, CENSO_EXPANDED_PATH, CENSO_NACIONAL_PATH]:
        frame = _prepare_censo_trace(_read_optional_parquet_subset(path, CENSO_TRACE_LOAD_COLS))
        if not frame.empty:
            frames.append(frame)

    if not frames:
        return pd.DataFrame()

    censo = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["hex_id"], keep="first")
    # Mesma sobreposicao de `modelo_hibrido_expansao._load_censo`: renda e score do censo
    # no grao do hexagono vem da MALHA de setores. As DUAS leituras precisam chamar a
    # MESMA funcao — duas redacoes da mesma regra nao dao erro, desencontram em silencio
    # (a licao da DEC-044).
    censo = sobrepor_renda_da_malha(censo, malha_path=malha_path)
    validated = _prepare_censo_trace(_read_optional_parquet_subset(CENSO_VALIDATED_PATH, CENSO_TRACE_LOAD_COLS))
    if validated.empty:
        return censo

    overlay_columns = [
        "qualidade_join_uf",
        "flag_join_uf_restrito",
        "flag_baixa_pop_setor",
        "flag_outlier_espacial",
        "causa_outlier_espacial",
        "delta_vs_vizinhos",
        "metodo_join_setor_2022",
        "motivo_fallback_setor_2022",
    ]
    validated = validated[[column for column in ["hex_id"] + overlay_columns if column in validated.columns]]
    censo = censo.merge(validated, on="hex_id", how="left", suffixes=("", "_validado"))

    for column in overlay_columns:
        censo = _coalesce_columns(censo, column, f"{column}_validado")

    return censo


def _read_estrutural_pop_frame(path: Path | str = ESTRUTURAL_PATH) -> pd.DataFrame:
    return _read_optional_parquet_subset(Path(path), ["hex_id", "pop_total"])


def build_enriched_dashboard_frame(dashboard_path: Path | str = DASHBOARD_PATH) -> pd.DataFrame:
    """Reproduz offline o frame que streamlit_app monta em runtime via enrich_dashboard_data."""
    return enrich_dashboard_data(
        _read_m1_dashboard_frame(dashboard_path),
        _read_hybrid_frame(),
        _read_censo_trace_frame(),
        estrutural_pop_df=_read_estrutural_pop_frame(),
    )


def write_enriched_dashboard_partitioned(
    df_enriched: pd.DataFrame,
    base_dir: Path | str = ENRIQUECIDO_DIR,
) -> Path:
    """Grava o frame enriquecido como dataset pyarrow particionado em uf=XX/parte-*.parquet."""
    base_dir = Path(base_dir)
    base_dir.mkdir(parents=True, exist_ok=True)
    frame = df_enriched.copy()
    # uf vem como categorical do _prepare_dataframe; pyarrow nao particiona por
    # coluna dictionary, entao normalizamos para string antes de escrever.
    frame["uf"] = frame["uf"].astype("string").astype(str)
    table = pa.Table.from_pandas(frame, preserve_index=False)
    ds.write_dataset(
        table,
        base_dir=str(base_dir),
        format="parquet",
        partitioning=ds.partitioning(pa.schema([("uf", pa.string())]), flavor="hive"),
        basename_template="parte-{i}.parquet",
        existing_data_behavior="delete_matching",
    )
    return base_dir


def read_enriched_dashboard(
    base_dir: Path | str = ENRIQUECIDO_DIR,
    uf: str | None = None,
) -> pd.DataFrame:
    """Le o dataset enriquecido particionado; opcionalmente apenas a particao da UF."""
    dataset = ds.dataset(str(Path(base_dir)), format="parquet", partitioning="hive")
    if uf is None:
        return dataset.to_table().to_pandas()
    return dataset.to_table(filter=ds.field("uf") == str(uf)).to_pandas()


#: Colunas sem as quais o artefato enriquecido sobe MUTILADO e o piloto degrada em
#: SILENCIO -- nao com erro, apenas parando de responder. Cada uma sustenta uma
#: superficie inteira:
#:   `oferta_efetiva_disponivel`          -> camadas 2, 3 e 5 do funil (a recomendacao)
#:   `score_setor_2022_calibrado`         -> camada 1 e a paleta do mapa censitario
#:   `oferta_consumida_mercado_estimada`  -> `n_concorrentes_est`, a leitura de pressao
#:   `populacao_corte_hex`                -> `pop_leitura`, o gate de populacao do funil
#:   `renda_per_capita_setor_2022_calibrada` -> renda intraurbana (DEC-038)
#:
#: POR QUE ISTO EXISTE: em 2026-08-28 uma rematerializacao rodou SEM o passo anterior
#: (`enriquecer_outputs_residual_mercado`, que devolve as colunas de mercado ao hibrido)
#: e produziu 65 colunas em vez de 82. O artefato existia, era legivel e tinha todas as
#: linhas -- so' faltava a coluna. `montar_funil` a le' de forma defensiva
#: (`if "oferta_efetiva_disponivel" in quentes.columns`), entao as camadas 2, 3 e 5
#: simplesmente ficaram VAZIAS em producao, sem log, sem 500, sem teste vermelho.
#: E' a mesma classe de falha da DEC-038 ("invisivel porque a coluna existe"), com o
#: agravante de que aqui a coluna nem existia e ainda assim nada gritou.
#: A materializacao agora RECUSA escrever um frame sem elas.
COLUNAS_CRITICAS_ENRIQUECIDO = (
    "hex_id",
    "score_setor_2022_calibrado",
    "oferta_efetiva_disponivel",
    "oferta_consumida_mercado_estimada",
    "populacao_corte_hex",
    "renda_per_capita_setor_2022_calibrada",
)


def verificar_colunas_criticas(df: pd.DataFrame) -> None:
    """Levanta se o frame enriquecido nao carrega o minimo que o piloto consome.

    Falha ALTO e cedo: o custo de um artefato mutilado nao e' um erro, e' um piloto que
    para de recomendar em silencio ate' alguem reparar.
    """
    faltam = [c for c in COLUNAS_CRITICAS_ENRIQUECIDO if c not in df.columns]
    if not faltam:
        return
    dica = ""
    if any(c.startswith("oferta_") or c == "sam_fitness_potencial" for c in faltam):
        dica = (
            " As colunas de mercado chegam ao hibrido pelo passo "
            "`python -m motor_expansao.pipelines.enriquecer_outputs_residual_mercado`, "
            "que precisa rodar ANTES desta materializacao."
        )
    raise ValueError(
        "Frame enriquecido sem colunas criticas: "
        f"{faltam}. Escrever assim deixaria o piloto degradado em silencio.{dica}"
    )


def materialize_enriched_dashboard(
    dashboard_path: Path | str = DASHBOARD_PATH,
    base_dir: Path | str = ENRIQUECIDO_DIR,
) -> pd.DataFrame:
    df_enriched = build_enriched_dashboard_frame(dashboard_path)
    verificar_colunas_criticas(df_enriched)
    write_enriched_dashboard_partitioned(df_enriched, base_dir)
    return df_enriched


def main() -> None:
    artifacts = generate_fase1_bi_artifacts()
    dashboard = artifacts["dashboard"]
    resumo_por_uf = artifacts["resumo_por_uf"]
    mapa_sample = artifacts["mapa_sample"]

    print("Artefatos BI gerados com sucesso.")
    print(f"Dashboard: {len(dashboard)} hexagonos")
    print(f"UFs: {len(resumo_por_uf)}")
    print(f"Mapa sample: {len(mapa_sample)} hexagonos")

    # Artefato derivado (nao oficial M1): so materializa quando o insumo hibrido
    # ja existe, mantendo o export oficial independente das camadas paralelas.
    if HYBRID_PATH.exists():
        enriched = materialize_enriched_dashboard()
        print(f"Enriquecido particionado: {len(enriched)} linhas em {ENRIQUECIDO_DIR}/uf=*/")
    else:
        print(f"Enriquecido pulado: insumo ausente ({HYBRID_PATH})")

    # Passo FINAL isolado (BLK-OPS-03): manifesto de proveniencia AO LADO dos
    # artefatos ja materializados. So LE parametros/sha e escreve _manifest.json;
    # nao recalcula score nem reescreve qualquer artefato M1.
    manifest_path = write_manifest()
    print(f"Manifesto de proveniencia gerado: {manifest_path}")


if __name__ == "__main__":
    main()
