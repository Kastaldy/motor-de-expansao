"""Ingestao OFFLINE/manual da Growth API -> data/staging/growth_api_historico.parquet.

Roda com rede real e `.env` presente. NAO entra no CI (so as funcoes puras em
`motor_expansao.dimensionamento.ingestao` sao testadas com mock).

Fluxo:
  1. VERIFICACAO DE ESCOPO MASTER (1o fetch curto): audita `set(unidade)` vs as 54
     unidades do performance parquet. Se vier 1 so unidade -> ABORTA (login nao e
     master de dados, contradicao doc §10.1) e nao inventa dados.
  2. Janelamento mensal de `--data-inicio` ate `--data-fim` em `/historico-dash-view`
     (decisao D7, superset). Cache idempotente por janela.
  3. `assert_sem_pii` antes do `to_parquet`.
  4. Auditoria final (nº unidades, range de datas, nº linhas, % inauguracao real).

ZERO PII em disco; READ-ONLY sobre o M1.
"""

from __future__ import annotations

import datetime as dt
import os
from pathlib import Path

import click
import pandas as pd

from motor_expansao.dimensionamento import config
from motor_expansao.dimensionamento.growth_api_client import (
    GrowthAPIClient,
    assert_sem_pii,
    normalizar_unidade,
    to_dataframe,
)
from motor_expansao.dimensionamento.ingestao import (
    auditar_historico,
    concatenar_e_dedup,
    gerar_janelas_mensais,
    iter_janelas,
    unidades_ausentes_do_view,
)

PERF_PARQUET = Path("data/staging/unidades_ultra_performance_hex.parquet")
OUT_PARQUET = config.STAGING_DIR / "growth_api_historico.parquet"


def verificar_escopo_master(cliente: GrowthAPIClient, perf_df: pd.DataFrame) -> dict:
    """1o fetch curto (ultimo mes) -> auditoria de escopo master."""
    hoje = dt.date.today()
    primeiro_dia = hoje.replace(day=1)
    di, dfim = primeiro_dia.isoformat(), hoje.isoformat()
    reg = cliente.get_historico_dash_view(di, dfim)
    df = to_dataframe(reg)
    perf_uns = set(perf_df["unidade"].dropna().astype(str).map(normalizar_unidade))
    view_uns = (
        set(df["unidade"].dropna().astype(str).map(normalizar_unidade))
        if "unidade" in df.columns
        else set()
    )
    match = view_uns & perf_uns
    info = {
        "janela": (di, dfim),
        "n_linhas": int(len(df)),
        "n_unidades_view": len(view_uns),
        "n_unidades_perf": len(perf_uns),
        "n_match": len(match),
        "pct_match_perf": round(100.0 * len(match) / max(1, len(perf_uns)), 1),
        "colunas": sorted(df.columns.tolist()),
        "tem_inauguracao": "inauguracao" in df.columns,
        "so_no_perf": sorted(perf_uns - view_uns),
    }
    return info


@click.command()
@click.option("--data-inicio", default=config.DATA_INICIO_HISTORICO, show_default=True)
@click.option("--data-fim", default=None, help="default = hoje")
@click.option("--force-refresh", is_flag=True, default=False)
@click.option(
    "--so-verificar-escopo",
    is_flag=True,
    default=False,
    help="Roda so a verificacao de escopo master e sai.",
)
@click.option(
    "--out",
    default=None,
    help=(
        "Caminho de saida do parquet. Default: env GROWTH_OUT_PARQUET ou "
        "data/staging/growth_api_historico.parquet. Necessario no deploy porque o "
        "staging e montado READ-ONLY nos containers: rode com --out /tmp/... e copie "
        "para o staging do host (ver scripts/cron/run_growth_daily.sh)."
    ),
)
def main(
    data_inicio: str,
    data_fim: str | None,
    force_refresh: bool,
    so_verificar_escopo: bool,
    out: str | None,
) -> None:
    data_fim = data_fim or dt.date.today().isoformat()
    if not PERF_PARQUET.is_file():
        raise click.ClickException(f"Performance parquet ausente: {PERF_PARQUET}")
    perf_df = pd.read_parquet(PERF_PARQUET, columns=["unidade"])

    cliente = GrowthAPIClient()
    cliente.login()

    # --- PASSO 2: verificacao de escopo master (obrigatoria) ----------------
    esc = verificar_escopo_master(cliente, perf_df)
    click.echo("=== VERIFICACAO DE ESCOPO MASTER ===")
    click.echo(f"janela: {esc['janela']}")
    click.echo(f"linhas: {esc['n_linhas']}")
    click.echo(
        f"unidades view={esc['n_unidades_view']} perf={esc['n_unidades_perf']} "
        f"match={esc['n_match']} ({esc['pct_match_perf']}%)"
    )
    click.echo(f"tem_inauguracao: {esc['tem_inauguracao']}")
    if esc["so_no_perf"]:
        click.echo(f"unidades do perf nao casadas: {esc['so_no_perf']}")

    if esc["n_unidades_view"] <= 1:
        raise click.ClickException(
            "ESCOPO MASTER FALHOU: a API retornou <=1 unidade. O login NAO e "
            "master de dados (contradicao doc §10.1 vs pre-ciclo). NAO inventar "
            "dados — escalar a Felipe."
        )
    if so_verificar_escopo:
        return

    # --- Ingestao da serie historica mensal ---------------------------------
    janelas = gerar_janelas_mensais(data_inicio, data_fim)
    click.echo(f"\n=== INGESTAO: {len(janelas)} janelas mensais ===")
    blocos: list[list[dict]] = []
    with click.progressbar(
        iter_janelas(cliente, janelas, force_refresh=force_refresh),
        length=len(janelas),
        label="historico-dash-view",
    ) as barra:
        for bloco in barra:
            blocos.append(bloco)

    df = concatenar_e_dedup(blocos)
    if df.empty:
        raise click.ClickException("Ingestao retornou DataFrame vazio.")

    # --- Completar o UNIVERSO pelo /historico-dash --------------------------
    # O `view` foi adotado como fonte unica sob a premissa de ser "superset de
    # /historico-dash" (config.py, decisao D7). A premissa vale para COLUNAS e nao para
    # UNIDADES: medido ao vivo em 2026-09-09, dash=103 e view=99, e tres das quatro
    # diferencas eram academias reais faturando ~R$ 593 mil/mes que nunca entraram na
    # base -- e por isso nunca apareceram na Visao Executiva. A auditoria abaixo passa a
    # ser gritada em toda execucao: se um dia o view voltar a cobrir tudo, o numero cai a
    # zero sozinho e o passo fica inerte.
    blocos_dash: list[list[dict]] = []
    with click.progressbar(
        iter_janelas(cliente, janelas, force_refresh=force_refresh, endpoint="dash"),
        length=len(janelas),
        label="historico-dash",
    ) as barra:
        for bloco in barra:
            blocos_dash.append(bloco)
    dash = concatenar_e_dedup(blocos_dash)

    click.echo("")
    click.echo("=== UNIVERSO: view x dash ===")
    n_view = int(df["unidade"].nunique())
    n_dash = int(dash["unidade"].nunique()) if len(dash) else 0
    click.echo(f"unidades view={n_view} dash={n_dash}")
    adotadas = unidades_ausentes_do_view(df, dash) if len(dash) else pd.DataFrame()
    if len(adotadas):
        # So' as colunas que o view ja' tem: o dash traz `acrescimo_dias` a mais, e deixar
        # a coluna entrar mudaria o schema do parquet por efeito colateral deste passo.
        adotadas = adotadas.reindex(columns=df.columns)
        nomes = sorted(adotadas["unidade"].unique())
        click.echo(f"ADOTADAS do /historico-dash ({len(nomes)}): {nomes}")
        df = concatenar_e_dedup([df.to_dict("records"), adotadas.to_dict("records")])
    else:
        click.echo("nenhuma unidade a adotar (o view ja cobre o universo do dash)")
    if n_dash > n_view and not len(adotadas):
        click.echo(
            f"AVISO: o dash tem {n_dash - n_view} unidade(s) que o view nao tem, e "
            "nenhuma passou no criterio de operacao recente. Conferir se e' unidade "
            "encerrada (esperado) ou dado faltando (nao esperado)."
        )

    # Anti-PII OBRIGATORIO antes de persistir.
    assert_sem_pii(df)
    out_path = Path(out or os.environ.get("GROWTH_OUT_PARQUET") or OUT_PARQUET)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)

    aud = auditar_historico(df)
    click.echo("\n=== AUDITORIA growth_api_historico.parquet ===")
    click.echo(f"arquivo: {out_path}")
    click.echo(f"linhas: {aud['n_linhas']}")
    click.echo(f"unidades: {aud['n_unidades']}")
    click.echo(f"range datas: {aud['data_min']} -> {aud['data_max']}")
    click.echo(f"colunas minimas presentes: {aud['colunas_minimas_presentes']}")
    click.echo(f"colunas minimas ausentes: {aud['colunas_minimas_ausentes']}")
    click.echo(f"% unidades com inauguracao real: {aud['tem_pct_inauguracao']}%")


if __name__ == "__main__":
    main()
