"""Funcoes puras de ingestao da Growth API (janelamento/concat/dedup/auditoria).

Separadas do CLI (`scripts/ingerir_growth_api.py`) para serem testaveis com
mock do cliente, sem rede (CI-safe). READ-ONLY sobre o M1; ZERO PII em disco
(o guard `assert_sem_pii` e aplicado no script antes do `to_parquet`).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime, timedelta

import pandas as pd

# Colunas minimas exigidas pelos criterios de aceite (#1).
COLUNAS_MINIMAS_HISTORICO = (
    "unidade",
    "data",
    "faturamento",
    "pagantes",
    "ticket_medio",
    "cancelados",
    "churn",
    "ativos_total",
    "inadimplente",
    "uf",
    "inauguracao",
)


def _parse_data(value: str | date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def gerar_janelas_mensais(
    data_inicio: str | date,
    data_fim: str | date,
) -> list[tuple[str, str]]:
    """Gera janelas mensais `[(inicio, fim), ...]` em `YYYY-MM-DD` inclusivas.

    Cada janela cobre um mes-calendario; a ultima e truncada em `data_fim`.
    """
    inicio = _parse_data(data_inicio)
    fim = _parse_data(data_fim)
    if inicio > fim:
        return []
    janelas: list[tuple[str, str]] = []
    cursor = date(inicio.year, inicio.month, 1)
    while cursor <= fim:
        if cursor.month == 12:
            prox = date(cursor.year + 1, 1, 1)
        else:
            prox = date(cursor.year, cursor.month + 1, 1)
        # primeiro inicio respeita o dia de data_inicio; demais sao dia 1.
        ini = inicio if not janelas else cursor
        ultimo_dia_mes = prox - timedelta(days=1)
        fim_janela = min(ultimo_dia_mes, fim)
        janelas.append((ini.isoformat(), fim_janela.isoformat()))
        cursor = prox
    return janelas


def iter_janelas(
    cliente,
    janelas: list[tuple[str, str]],
    force_refresh: bool = False,
) -> Iterator[list[dict]]:
    """Itera as janelas chamando `get_historico_dash_view` (decisao D7)."""
    for di, dfim in janelas:
        yield cliente.get_historico_dash_view(di, dfim, force_refresh=force_refresh)


def concatenar_e_dedup(blocos: list[list[dict]]) -> pd.DataFrame:
    """Concatena blocos de registros e remove duplicatas por (unidade, data).

    Mantem a ultima ocorrencia (janelas mais recentes/refrescadas sobrescrevem).
    """
    registros: list[dict] = []
    for bloco in blocos:
        if bloco:
            registros.extend(bloco)
    if not registros:
        return pd.DataFrame()
    df = pd.DataFrame(registros)
    subset = [c for c in ("unidade", "data") if c in df.columns]
    if subset:
        df = df.drop_duplicates(subset=subset, keep="last")
    return df.reset_index(drop=True)


def auditar_historico(df: pd.DataFrame) -> dict:
    """Auditoria do parquet ingerido: nº unidades, range de datas, nº linhas."""
    out: dict = {
        "n_linhas": int(len(df)),
        "n_unidades": int(df["unidade"].nunique()) if "unidade" in df.columns else 0,
        "data_min": None,
        "data_max": None,
        "colunas_minimas_presentes": [],
        "colunas_minimas_ausentes": [],
        "tem_pct_inauguracao": None,
    }
    if "data" in df.columns and not df.empty:
        datas = pd.to_datetime(df["data"], errors="coerce", dayfirst=True)
        if datas.notna().any():
            out["data_min"] = str(datas.min().date())
            out["data_max"] = str(datas.max().date())
    presentes = [c for c in COLUNAS_MINIMAS_HISTORICO if c in df.columns]
    out["colunas_minimas_presentes"] = presentes
    out["colunas_minimas_ausentes"] = [
        c for c in COLUNAS_MINIMAS_HISTORICO if c not in df.columns
    ]
    if "inauguracao" in df.columns and "unidade" in df.columns and not df.empty:
        por_unidade = df.groupby("unidade")["inauguracao"].first()
        com_inaug = por_unidade.notna() & (por_unidade.astype(str).str.strip() != "")
        out["tem_pct_inauguracao"] = round(
            100.0 * float(com_inaug.sum()) / max(1, len(por_unidade)), 1
        )
    return out
