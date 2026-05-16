"""
Bloco 4 - Padroes das melhores e piores unidades Ultra.

Analisa a base de performance por hexagono criada nos Blocos 2 e 3 para
classificar top/bottom por tercis, calcular correlacoes Pearson/Spearman e
registrar padroes interpretaveis.

Saida: data/reports/validacao_penetracao_ultra_hex.md

Nao altera nenhum artefato oficial do M1.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from jobs.pipelines import comparar_geofusion_vs_hex  # noqa: E402

PERF_HEX_PATH = ROOT / "data" / "staging" / "unidades_ultra_performance_hex.parquet"
REPORT_PATH = ROOT / "data" / "reports" / "validacao_penetracao_ultra_hex.md"
REPORT_DATE = "2026-05-15"

PERFORMANCE_METRICS = {
    "alunos_total": "Alunos totais",
    "faturamento": "Faturamento",
    "penetracao_ultra_alunos_total": "Penetracao alunos totais",
    "receita_por_habitante_hex": "Receita por habitante",
    "ticket_medio_aluno": "Ticket medio por aluno",
    "ativos_pag": "Pagantes",
}

CONTEXT_VARIABLES = {
    "pop_hex_base": "Populacao do hex",
    "densidade_hex_km2": "Densidade do hex",
    "renda_per_capita": "Renda per capita M1",
    "renda_per_capita_setor_2022_calibrada": "Renda per capita setor 2022",
    "score_priorizacao": "Score M1",
    "score_expansao_hibrido": "Score hibrido",
    "n_concorrentes_mapeados_1km": "Concorrentes 1km",
    "n_concorrentes_mapeados_2km": "Concorrentes 2km",
    "dist_concorrente_mais_proximo_m": "Distancia concorrente mais proximo",
    "flag_white_space_2km_num": "White space 2km",
    "flag_canibalizacao_ultra_1km_num": "Canibalizacao Ultra 1km",
    "densidade_geofusion_1km_calc": "Densidade GeoFusion 1km",
    "delta_densidade_hex_vs_geofusion": "Delta densidade hex vs GeoFusion",
    "ratio_densidade_hex_geofusion": "Ratio densidade hex/GeoFusion",
}

SUMMARY_VARIABLES = {
    **CONTEXT_VARIABLES,
    "metragem": "Metragem",
    "agregadores": "Alunos agregadores",
    "alunos_por_m2": "Alunos por m2",
}

REQUIRED_INPUT_COLS = {
    "unidade",
    "uf",
    "hex_id_res7",
    "pop_geofusion_1km",
    "pop_hex_base",
    "fonte_pop_hex_base",
    *PERFORMANCE_METRICS.keys(),
}


@dataclass
class AnalisePenetracao:
    base: pd.DataFrame
    metricas: pd.DataFrame
    regras_tercis: pd.DataFrame
    correlacoes: pd.DataFrame
    resumo_top_bottom: pd.DataFrame
    outliers: pd.DataFrame
    achados: list[str]


def _to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _bool_to_numeric(series: pd.Series | None, index: pd.Index) -> pd.Series:
    if series is None:
        return pd.Series(np.nan, index=index, dtype="float64")

    def convert(value: object) -> float:
        if pd.isna(value):
            return np.nan
        if isinstance(value, str):
            lower = value.strip().lower()
            if lower in {"true", "1", "sim", "yes"}:
                return 1.0
            if lower in {"false", "0", "nao", "no"}:
                return 0.0
            return np.nan
        return 1.0 if bool(value) else 0.0

    return series.reindex(index).map(convert).astype("float64")


def _fmt(value: object, decimals: int = 1) -> str:
    if pd.isna(value):
        return "-"
    return f"{float(value):,.{decimals}f}"


def _fmt_corr(value: object) -> str:
    if pd.isna(value):
        return "-"
    return f"{float(value):.3f}"


def _fmt_metric_value(metric: str, value: object) -> str:
    if pd.isna(value):
        return "-"
    if metric == "penetracao_ultra_alunos_total":
        return f"{float(value) * 100:.2f}%"
    if metric in {"receita_por_habitante_hex", "ticket_medio_aluno"}:
        return _fmt(value, 2)
    return _fmt(value, 0)


def _fmt_variable_value(variable: str, value: object) -> str:
    if pd.isna(value):
        return "-"
    if variable in {"ratio_densidade_hex_geofusion"}:
        return _fmt(value, 2)
    if variable in {"flag_white_space_2km_num", "flag_canibalizacao_ultra_1km_num"}:
        return _fmt(value, 2)
    return _fmt(value, 1)


def preparar_base(df: pd.DataFrame) -> pd.DataFrame:
    faltam = REQUIRED_INPUT_COLS - set(df.columns)
    if faltam:
        raise AssertionError(f"Colunas obrigatorias ausentes: {sorted(faltam)}")

    out = comparar_geofusion_vs_hex.calcular_comparacao(df)
    out["flag_white_space_2km_num"] = _bool_to_numeric(out.get("flag_white_space_2km"), out.index)
    out["flag_canibalizacao_ultra_1km_num"] = _bool_to_numeric(
        out.get("flag_canibalizacao_ultra_1km"),
        out.index,
    )
    return out


def calcular_metricas_amostra(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for col, label in PERFORMANCE_METRICS.items():
        values = _to_numeric(df[col])
        valid = values.dropna()
        rows.append(
            {
                "metrica": col,
                "label": label,
                "n_valido": int(valid.size),
                "n_nulo": int(values.isna().sum()),
                "min": valid.min() if not valid.empty else np.nan,
                "p25": valid.quantile(0.25) if not valid.empty else np.nan,
                "mediana": valid.median() if not valid.empty else np.nan,
                "p75": valid.quantile(0.75) if not valid.empty else np.nan,
                "max": valid.max() if not valid.empty else np.nan,
            }
        )
    return pd.DataFrame(rows)


def classificar_desempenho(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    out = df.copy()
    regras = []

    for col, label in PERFORMANCE_METRICS.items():
        values = _to_numeric(out[col])
        valid = values.dropna()
        faixa_col = f"faixa_desempenho_{col}"
        out[faixa_col] = pd.NA

        if valid.empty:
            regras.append(
                {
                    "metrica": col,
                    "label": label,
                    "n_valido": 0,
                    "q33": np.nan,
                    "q67": np.nan,
                    "top_n": 0,
                    "bottom_n": 0,
                }
            )
            continue

        q33 = float(valid.quantile(1 / 3))
        q67 = float(valid.quantile(2 / 3))
        out.loc[values <= q33, faixa_col] = "bottom_tercil"
        out.loc[(values > q33) & (values < q67), faixa_col] = "intermediario"
        out.loc[values >= q67, faixa_col] = "top_tercil"

        regras.append(
            {
                "metrica": col,
                "label": label,
                "n_valido": int(valid.size),
                "q33": q33,
                "q67": q67,
                "top_n": int(out[faixa_col].eq("top_tercil").sum()),
                "bottom_n": int(out[faixa_col].eq("bottom_tercil").sum()),
            }
        )

    return out, pd.DataFrame(regras)


def calcular_correlacoes(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for metric, metric_label in PERFORMANCE_METRICS.items():
        metric_values = _to_numeric(df[metric])
        for variable, variable_label in CONTEXT_VARIABLES.items():
            if variable not in df.columns:
                continue
            variable_values = _to_numeric(df[variable])
            pair = pd.DataFrame({"metric": metric_values, "variable": variable_values}).dropna()
            n = int(len(pair))

            if n < 5:
                status = "n_insuficiente"
                pearson = np.nan
                spearman = np.nan
            elif pair["metric"].nunique() < 2 or pair["variable"].nunique() < 2:
                status = "sem_variacao"
                pearson = np.nan
                spearman = np.nan
            else:
                status = "ok"
                pearson = float(pair["metric"].corr(pair["variable"], method="pearson"))
                spearman = float(pair["metric"].corr(pair["variable"], method="spearman"))

            rows.append(
                {
                    "metrica": metric,
                    "label_metrica": metric_label,
                    "variavel": variable,
                    "label_variavel": variable_label,
                    "n_valido": n,
                    "pearson": pearson,
                    "spearman": spearman,
                    "status": status,
                    "abs_spearman": abs(spearman) if pd.notna(spearman) else np.nan,
                }
            )

    return pd.DataFrame(rows)


def resumir_top_bottom(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for metric, metric_label in PERFORMANCE_METRICS.items():
        faixa_col = f"faixa_desempenho_{metric}"
        if faixa_col not in df.columns:
            continue

        top = df[df[faixa_col].eq("top_tercil")]
        bottom = df[df[faixa_col].eq("bottom_tercil")]
        for variable, variable_label in SUMMARY_VARIABLES.items():
            if variable not in df.columns:
                continue

            top_values = _to_numeric(top[variable]).dropna()
            bottom_values = _to_numeric(bottom[variable]).dropna()
            top_med = top_values.median() if not top_values.empty else np.nan
            bottom_med = bottom_values.median() if not bottom_values.empty else np.nan
            delta_abs = top_med - bottom_med if pd.notna(top_med) and pd.notna(bottom_med) else np.nan
            delta_pct = (
                delta_abs / abs(bottom_med)
                if pd.notna(delta_abs) and pd.notna(bottom_med) and bottom_med != 0
                else np.nan
            )

            rows.append(
                {
                    "metrica": metric,
                    "label_metrica": metric_label,
                    "variavel": variable,
                    "label_variavel": variable_label,
                    "top_n": int(top_values.size),
                    "bottom_n": int(bottom_values.size),
                    "top_mediana": top_med,
                    "bottom_mediana": bottom_med,
                    "delta_abs": delta_abs,
                    "delta_pct": delta_pct,
                }
            )

    return pd.DataFrame(rows)


def detectar_outliers(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for metric, metric_label in PERFORMANCE_METRICS.items():
        values = _to_numeric(df[metric])
        valid = values.dropna()
        if valid.size < 8:
            continue

        q1 = valid.quantile(0.25)
        q3 = valid.quantile(0.75)
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr

        mask = values.lt(lower) | values.gt(upper)
        for _, row in df.loc[mask].iterrows():
            value = values.loc[row.name]
            rows.append(
                {
                    "metrica": metric,
                    "label_metrica": metric_label,
                    "unidade": row.get("unidade"),
                    "uf": row.get("uf"),
                    "valor": value,
                    "tipo": "alto" if value > upper else "baixo",
                    "limite_inferior": lower,
                    "limite_superior": upper,
                    "fonte_pop_hex_base": row.get("fonte_pop_hex_base"),
                }
            )

    cols = [
        "metrica",
        "label_metrica",
        "unidade",
        "uf",
        "valor",
        "tipo",
        "limite_inferior",
        "limite_superior",
        "fonte_pop_hex_base",
    ]
    return pd.DataFrame(rows, columns=cols)


def gerar_achados(analise: AnalisePenetracao) -> list[str]:
    df = analise.base
    corr = analise.correlacoes
    resumo = analise.resumo_top_bottom
    achados: list[str] = []

    n_total = len(df)
    n_pop = int(_to_numeric(df["pop_hex_base"]).gt(0).sum())
    achados.append(
        f"Amostra pequena: {n_total} unidades no total, {n_pop} com populacao de hex valida; "
        "os resultados indicam hipoteses operacionais, nao causalidade."
    )

    fontes = df["fonte_pop_hex_base"].value_counts(dropna=False).to_dict()
    if fontes.get("m1_municipal_proxy", 0):
        achados.append(
            "Parte da amostra usa populacao municipal proxy; densidade e penetracao nesses casos "
            "devem ser lidas com cautela e nao comparadas como se fossem setor censitario real."
        )
    achados.append(
        "Penetracao e receita por habitante usam `pop_hex_base` no denominador; correlacoes fortes "
        "com populacao ou densidade do hex sao diagnostico da formula, nao evidencia causal."
    )

    corr_ok = corr[corr["status"].eq("ok")].copy()
    for metric in [
        "alunos_total",
        "faturamento",
        "penetracao_ultra_alunos_total",
        "receita_por_habitante_hex",
    ]:
        sub = corr_ok[corr_ok["metrica"].eq(metric)].copy()
        if metric in {"penetracao_ultra_alunos_total", "receita_por_habitante_hex"}:
            sub = sub[
                ~sub["variavel"].isin(
                    {
                        "pop_hex_base",
                        "densidade_hex_km2",
                        "delta_densidade_hex_vs_geofusion",
                        "ratio_densidade_hex_geofusion",
                    }
                )
            ]
        sub = sub.sort_values("abs_spearman", ascending=False)
        if sub.empty:
            continue
        row = sub.iloc[0]
        prefix = (
            "Maior associacao nao derivada diretamente de pop_hex"
            if metric in {"penetracao_ultra_alunos_total", "receita_por_habitante_hex"}
            else "Maior associacao monotona observada"
        )
        achados.append(
            f"{prefix} para {row['label_metrica']}: "
            f"{row['label_variavel']} (Spearman={_fmt_corr(row['spearman'])}, n={int(row['n_valido'])})."
        )

    foco = resumo[
        resumo["metrica"].eq("penetracao_ultra_alunos_total")
        & resumo["variavel"].isin(
            [
                "densidade_geofusion_1km_calc",
                "renda_per_capita",
                "n_concorrentes_mapeados_1km",
                "dist_concorrente_mais_proximo_m",
            ]
        )
    ].copy()
    foco = foco.dropna(subset=["top_mediana", "bottom_mediana"]).sort_values(
        "delta_pct",
        key=lambda s: s.abs(),
        ascending=False,
    )
    if not foco.empty:
        row = foco.iloc[0]
        achados.append(
            f"No corte por penetracao, o maior contraste entre top e bottom tercil aparece em "
            f"{row['label_variavel']}: mediana top={_fmt_variable_value(row['variavel'], row['top_mediana'])}, "
            f"bottom={_fmt_variable_value(row['variavel'], row['bottom_mediana'])}."
        )

    if not analise.outliers.empty:
        achados.append(
            f"Foram encontrados {len(analise.outliers)} outliers por regra IQR; eles foram mantidos "
            "na analise e listados para leitura individual."
        )
    else:
        achados.append("Nenhum outlier IQR foi removido; todos os registros validos permaneceram na analise.")

    achados.append(
        "Nao e possivel inferir churn, conversao, causalidade de concorrencia ou capacidade ideal por "
        "hex apenas com esta amostra; o Bloco 5 deve tratar TAM/SAM como calibracao inicial conservadora."
    )
    return achados


def gerar_analise(path: Path = PERF_HEX_PATH) -> AnalisePenetracao:
    raw = pd.read_parquet(path)
    base = preparar_base(raw)
    classificada, regras = classificar_desempenho(base)
    metricas = calcular_metricas_amostra(classificada)
    correlacoes = calcular_correlacoes(classificada)
    resumo = resumir_top_bottom(classificada)
    outliers = detectar_outliers(classificada)
    analise = AnalisePenetracao(
        base=classificada,
        metricas=metricas,
        regras_tercis=regras,
        correlacoes=correlacoes,
        resumo_top_bottom=resumo,
        outliers=outliers,
        achados=[],
    )
    analise.achados = gerar_achados(analise)
    return analise


def _metric_table(metricas: pd.DataFrame) -> list[str]:
    lines = [
        "| Metrica | n valido | n nulo | Min | P25 | Mediana | P75 | Max |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for _, row in metricas.iterrows():
        lines.append(
            f"| {row['label']} | {int(row['n_valido'])} | {int(row['n_nulo'])} "
            f"| {_fmt_metric_value(row['metrica'], row['min'])} "
            f"| {_fmt_metric_value(row['metrica'], row['p25'])} "
            f"| {_fmt_metric_value(row['metrica'], row['mediana'])} "
            f"| {_fmt_metric_value(row['metrica'], row['p75'])} "
            f"| {_fmt_metric_value(row['metrica'], row['max'])} |"
        )
    return lines


def _rules_table(regras: pd.DataFrame) -> list[str]:
    lines = [
        "| Metrica | n valido | Bottom <= P33 | Top >= P67 | Top n | Bottom n |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for _, row in regras.iterrows():
        lines.append(
            f"| {row['label']} | {int(row['n_valido'])} "
            f"| {_fmt_metric_value(row['metrica'], row['q33'])} "
            f"| {_fmt_metric_value(row['metrica'], row['q67'])} "
            f"| {int(row['top_n'])} | {int(row['bottom_n'])} |"
        )
    return lines


def _correlation_table(correlacoes: pd.DataFrame, limit: int = 36) -> list[str]:
    corr_ok = correlacoes[correlacoes["status"].eq("ok")].copy()
    corr_ok = corr_ok.sort_values("abs_spearman", ascending=False).head(limit)
    lines = [
        "| Metrica | Variavel | n | Pearson | Spearman |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for _, row in corr_ok.iterrows():
        lines.append(
            f"| {row['label_metrica']} | {row['label_variavel']} | {int(row['n_valido'])} "
            f"| {_fmt_corr(row['pearson'])} | {_fmt_corr(row['spearman'])} |"
        )
    return lines


def _top_bottom_table(resumo: pd.DataFrame) -> list[str]:
    wanted_metrics = {
        "alunos_total",
        "faturamento",
        "penetracao_ultra_alunos_total",
        "receita_por_habitante_hex",
    }
    wanted_vars = {
        "pop_hex_base",
        "densidade_geofusion_1km_calc",
        "densidade_hex_km2",
        "renda_per_capita",
        "score_priorizacao",
        "score_expansao_hibrido",
        "n_concorrentes_mapeados_1km",
        "dist_concorrente_mais_proximo_m",
        "metragem",
        "agregadores",
    }
    sub = resumo[resumo["metrica"].isin(wanted_metrics) & resumo["variavel"].isin(wanted_vars)]
    sub = sub.dropna(subset=["top_mediana", "bottom_mediana"])

    lines = [
        "| Corte de desempenho | Variavel | Top mediana | Bottom mediana | Delta |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for _, row in sub.iterrows():
        lines.append(
            f"| {row['label_metrica']} | {row['label_variavel']} "
            f"| {_fmt_variable_value(row['variavel'], row['top_mediana'])} "
            f"| {_fmt_variable_value(row['variavel'], row['bottom_mediana'])} "
            f"| {_fmt_variable_value(row['variavel'], row['delta_abs'])} |"
        )
    return lines


def _outlier_table(outliers: pd.DataFrame, limit: int = 30) -> list[str]:
    if outliers.empty:
        return ["Nenhum outlier IQR identificado nas metricas de desempenho."]

    sub = outliers.sort_values(["metrica", "tipo", "valor"], ascending=[True, True, False]).head(limit)
    lines = [
        "| Metrica | Unidade | UF | Tipo | Valor | Fonte pop |",
        "| --- | --- | --- | --- | ---: | --- |",
    ]
    for _, row in sub.iterrows():
        lines.append(
            f"| {row['label_metrica']} | {row['unidade']} | {row['uf']} | {row['tipo']} "
            f"| {_fmt_metric_value(row['metrica'], row['valor'])} | {row['fonte_pop_hex_base']} |"
        )
    return lines


def escrever_relatorio(analise: AnalisePenetracao, path: Path = REPORT_PATH) -> None:
    df = analise.base
    lines: list[str] = []
    a = lines.append

    a("# Validacao Penetracao Ultra por Hex")
    a("")
    a(f"**Data:** {REPORT_DATE}  ")
    a(f"**Unidades analisadas:** {len(df)}  ")
    a("**Regra top/bottom:** tercis por metrica; maior valor = melhor desempenho.")
    a("")
    a("## Amostra")
    a("")
    a("| Fonte de populacao do hex | n |")
    a("| --- | ---: |")
    for fonte, n in df["fonte_pop_hex_base"].value_counts(dropna=False).items():
        a(f"| {fonte} | {int(n)} |")
    a("")
    lines.extend(_metric_table(analise.metricas))
    a("")
    a("## Regra de Classificacao")
    a("")
    a(
        "Top e bottom sao definidos separadamente para cada lente de desempenho: alunos totais, "
        "faturamento, penetracao, receita por habitante, ticket medio e pagantes."
    )
    a("")
    lines.extend(_rules_table(analise.regras_tercis))
    a("")
    a("## Correlacoes")
    a("")
    a(
        "Tabela ordenada por maior associacao absoluta de Spearman. Pearson e Spearman usam apenas "
        "pares validos; pares com n<5 ou sem variacao ficam fora desta tabela."
    )
    a("")
    a(
        "Nota: penetracao e receita por habitante usam `pop_hex_base` como denominador; associacoes "
        "com populacao, densidade do hex, delta e ratio de densidade sao diagnosticas e nao causais."
    )
    a("")
    lines.extend(_correlation_table(analise.correlacoes))
    a("")
    a("## Padroes Top vs Bottom")
    a("")
    a(
        "Medianas dos top tercis contra bottom tercis. Esta leitura destaca contrastes operacionais, "
        "mas nao substitui analise causal."
    )
    a("")
    lines.extend(_top_bottom_table(analise.resumo_top_bottom))
    a("")
    a("## Outliers")
    a("")
    a("Outliers foram detectados por IQR e mantidos na analise.")
    a("")
    lines.extend(_outlier_table(analise.outliers))
    a("")
    a("## Achados e Cautelas")
    a("")
    for achado in analise.achados:
        a(f"- {achado}")
    a("")
    a("_Gerado por `jobs/pipelines/validar_penetracao_ultra_hex.py`_")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Relatorio salvo: {path}")


def validar(analise: AnalisePenetracao) -> None:
    print("\n=== Validacao: penetracao Ultra por hex ===")
    print(f"Total de linhas: {len(analise.base)}")

    assert len(analise.base) > 0, "Base vazia"
    assert set(PERFORMANCE_METRICS) <= set(analise.base.columns), "Metricas de desempenho ausentes"
    assert {"pearson", "spearman", "n_valido", "status"} <= set(analise.correlacoes.columns)
    assert {"top_tercil", "bottom_tercil"} <= set(
        pd.concat(
            [
                analise.base[f"faixa_desempenho_{metric}"].dropna()
                for metric in PERFORMANCE_METRICS
            ]
        ).unique()
    )

    metricas_sem_n = analise.metricas[analise.metricas["n_valido"].eq(0)]
    assert metricas_sem_n.empty, f"Metricas sem amostra valida: {metricas_sem_n['metrica'].tolist()}"

    corr_ok = analise.correlacoes[analise.correlacoes["status"].eq("ok")]
    assert not corr_ok.empty, "Nenhuma correlacao valida calculada"
    assert corr_ok["n_valido"].ge(5).all(), "Correlacao valida com n<5"

    assert not analise.resumo_top_bottom.empty, "Resumo top/bottom vazio"
    assert analise.achados, "Achados interpretaveis ausentes"
    print(f"Correlacoes validas: {len(corr_ok)}")
    print(f"Outliers IQR: {len(analise.outliers)}")
    print("Validacao OK")


def main() -> None:
    print("Bloco 4 - Padroes das melhores e piores unidades")
    print("=" * 60)
    analise = gerar_analise(PERF_HEX_PATH)
    validar(analise)
    escrever_relatorio(analise, REPORT_PATH)
    print("Bloco 4 concluido.")


if __name__ == "__main__":
    main()
