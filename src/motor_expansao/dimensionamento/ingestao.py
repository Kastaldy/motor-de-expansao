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
    endpoint: str = "view",
) -> Iterator[list[dict]]:
    """Itera as janelas de um dos dois endpoints do historico.

    `endpoint="view"` e' `/historico-dash-view` (o default, e a base da ingestao);
    `endpoint="dash"` e' `/historico-dash`, usado so' para COMPLETAR o universo -- ver
    `unidades_ausentes_do_view`.
    """
    if endpoint not in ("view", "dash"):
        raise ValueError(f"endpoint desconhecido: {endpoint!r} (use 'view' ou 'dash')")
    puxar = (
        cliente.get_historico_dash_view if endpoint == "view" else cliente.get_historico_dash
    )
    for di, dfim in janelas:
        yield puxar(di, dfim, force_refresh=force_refresh)


# Janela, em dias contados do fim da base, em que a unidade precisa ter dado algum sinal de
# operacao para ser adotada do `/historico-dash`. Nao se olha o ULTIMO dia isolado (a coleta
# perde dias com frequencia) nem a serie INTEIRA -- a serie inteira adotaria unidade que
# operou um dia em 2025 e esta zerada desde entao, que e' exatamente o caso `BELA CINTRA`
# (medido 2026-09-09: pagantes>0 em 25/02/2025, e 0 pagantes / 0 ativos / 0 faturamento em
# 08/09/2026, ausente da planilha do Financeiro).
DIAS_JANELA_OPERACAO = 30


def _uf_do_sufixo(nome: object) -> str:
    """UF a partir do sufixo ` - XX` do nome da unidade. Vazio quando nao ha sufixo.

    O `/historico-dash` nao traz `uf`, `master` nem `inauguracao` -- sao justamente as
    colunas de CADASTRO, e a hipotese e' que as unidades ausentes do `view` sejam as de
    cadastro incompleto la' na origem. O sufixo do nome e' a unica fonte de UF que viaja
    no proprio registro.
    """
    texto = " ".join(str(nome or "").split())
    marca = texto[-5:].upper()
    if len(texto) >= 5 and marca[:3] in (" - ",) and marca[3:].isalpha():
        return marca[3:]
    return ""


def unidades_ausentes_do_view(
    view: pd.DataFrame, dash: pd.DataFrame, *, dias_operacao: int = DIAS_JANELA_OPERACAO
) -> pd.DataFrame:
    """Linhas do `/historico-dash` cujas unidades o `/historico-dash-view` nao tem.

    O `view` foi adotado como fonte unica em BLK-DIM-00 sob a premissa de que era
    "superset de `/historico-dash`". A premissa vale para COLUNAS e **nao** para
    UNIDADES: medido ao vivo em 2026-09-09, o `dash` devolve 103 unidades e o `view`
    99, e as 4 diferencas incluiam tres academias reais faturando ~R$ 593 mil/mes
    (`JARDIM DAS AMERICAS - MT`, `SAO CARLOS - CENTRO - SP`, `VILA IZABEL - PR`), que
    nunca entraram na base e por isso nunca apareceram na Visao Executiva.

    So' entra unidade com sinal de operacao nos ultimos `dias_operacao` dias da base --
    ver `DIAS_JANELA_OPERACAO`. As colunas de cadastro que o `dash` nao traz sao
    preenchidas assim:

    * `uf`: do sufixo do nome (unica fonte no proprio registro);
    * `inauguracao`: a PRIMEIRA data da serie da unidade, e so' quando ela e' posterior
      ao inicio da base -- se a serie comeca junto com a base, ela foi truncada pelo
      recorte e nao diz nada sobre a abertura. Verificado nas tres: a primeira data e'
      exatamente o primeiro dia com pagantes, e em Jardim das Americas (25/02/2026) bate
      com o inicio do faturamento na planilha do Financeiro;
    * `master`: fica VAZIO de proposito. A coluna `master` da Growth e' sigla de regiao,
      e quem responde "de quem e' a unidade" e' o `master_franquia` do cadastro, que e'
      editavel pela propria tela.
    """
    if not len(dash) or "unidade" not in dash.columns:
        return dash.iloc[0:0] if len(dash.columns) else pd.DataFrame()

    from motor_expansao.dimensionamento.growth_api_client import normalizar_unidade

    no_view = (
        {normalizar_unidade(u) for u in view["unidade"].dropna()}
        if len(view) and "unidade" in view.columns
        else set()
    )
    fora = dash[~dash["unidade"].map(normalizar_unidade).isin(no_view)].copy()
    if not len(fora):
        return fora

    fora["_data"] = pd.to_datetime(fora["data"], format="%d/%m/%Y", errors="coerce")
    fora = fora.dropna(subset=["_data"])
    if not len(fora):
        return fora

    # Sinal de operacao: pagantes > 0 em algum dia da janela final da BASE (nao da
    # unidade -- serie que morreu ha um ano nao pode se qualificar pelo proprio fim).
    fim = pd.to_datetime(dash["data"], format="%d/%m/%Y", errors="coerce").max()
    recente = fora[fora["_data"] >= fim - pd.Timedelta(days=dias_operacao)]
    pagantes = pd.to_numeric(recente.get("pagantes"), errors="coerce").fillna(0)
    vivas = set(recente.loc[pagantes > 0, "unidade"])
    fora = fora[fora["unidade"].isin(vivas)]
    if not len(fora):
        return fora.drop(columns=["_data"])

    inicio_base = pd.to_datetime(dash["data"], format="%d/%m/%Y", errors="coerce").min()
    primeira = fora.groupby("unidade")["_data"].min()

    fora["uf"] = fora["unidade"].map(_uf_do_sufixo)
    fora["master"] = ""
    fora["inauguracao"] = fora["unidade"].map(
        lambda u: primeira[u].strftime("%d/%m/%Y") if primeira[u] > inicio_base else ""
    )
    return fora.drop(columns=["_data"])


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
