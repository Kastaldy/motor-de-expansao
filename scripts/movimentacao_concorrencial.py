"""Relatório de movimentação concorrencial — snapshot único (READ-ONLY sobre o M1).

Lê dados de staging (concorrentes_mapeados, concorrentes_densos,
hexagonos_mercado_mapeado) e gera data/analysis/movimentacao_concorrencial.md.

Guardrails:
- READ-ONLY sobre o M1: não toca config.py, pipelines/m1, artefatos oficiais.
- Não importa nenhum módulo de src/motor_expansao/.
- TotalPass/Wellhub: reportados SEPARADAMENTE (não somados ao residual do M1).
- Escrita apenas em data/analysis/ (gitignored).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
STAGING_DIR = ROOT / "data" / "staging"
ANALYSIS_DIR = ROOT / "data" / "analysis"

# Colunas lidas do mercado (evita OOM: 139 cols × 1,5 M linhas)
COLS_MERCADO = [
    "hex_id",
    "uf",
    "nome_municipio",
    "oferta_consumida_mercado_estimada",
    "oferta_efetiva_disponivel",
    "rede_dominante_2km",
]

SNAP_CONC = "concorrentes_mapeados.parquet"
SNAP_DENSO = "concorrentes_densos.parquet"
SNAP_MKT = "hexagonos_mercado_mapeado.parquet"

# Datas dos snapshots (metadados documentados no backlog)
DATA_COLETA_CONC = "2026-04-22 a 2026-05-04"
DATA_SNAPSHOT_MKT = "2026-06-11"

# Fontes da base complementar densa (TotalPass/Wellhub — anti-dupla contagem)
FONTES_AGREGADORAS = {"totalpass", "wellhub"}


# ---------------------------------------------------------------------------
# Passo 1 — Carregamento
# ---------------------------------------------------------------------------


def carregar_dados(
    staging_dir: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Carrega os três parquets do diretório de staging.

    Retorna ``(df_conc, df_denso, df_mkt)`` onde ``df_mkt`` carrega
    apenas as 6 colunas em ``COLS_MERCADO``.
    """
    df_conc = pd.read_parquet(staging_dir / SNAP_CONC)
    df_denso = pd.read_parquet(staging_dir / SNAP_DENSO)
    df_mkt = pd.read_parquet(staging_dir / SNAP_MKT, columns=COLS_MERCADO)
    return df_conc, df_denso, df_mkt


# ---------------------------------------------------------------------------
# Passo 2 — Join UF / cidade
# ---------------------------------------------------------------------------


def join_uf_cidade(
    df_conc: pd.DataFrame, df_mkt: pd.DataFrame
) -> pd.DataFrame:
    """Filtra válidos e enriquece com UF/cidade via hex_id_res7.

    Retorna apenas as linhas com ``status_registro == "valido"``
    enriquecidas com ``uf`` e ``nome_municipio`` do mercado mapeado.
    Linhas sem match ficam com ``uf=NaN`` (merge LEFT preserva todas).
    """
    df_validos = df_conc[df_conc["status_registro"] == "valido"].copy()
    df_geo = df_mkt[["hex_id", "uf", "nome_municipio"]].drop_duplicates("hex_id")
    joined = df_validos.merge(
        df_geo,
        left_on="hex_id_res7",
        right_on="hex_id",
        how="left",
    )
    sem_uf = int(joined["uf"].isna().sum())
    print(f"  join_uf_cidade: {sem_uf} unidades sem UF após join (hex não encontrado no mercado)")
    return joined


# ---------------------------------------------------------------------------
# Helper — top municípios (seção 4)
# ---------------------------------------------------------------------------


def top_municipios(df_geo: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """Retorna os N municípios com maior número de unidades concorrentes."""
    return (
        df_geo.groupby(["nome_municipio", "uf"])
        .size()
        .reset_index(name="n_unidades")
        .sort_values("n_unidades", ascending=False)
        .head(n)
    )


# ---------------------------------------------------------------------------
# Passo 3 — Resumo por rede
# ---------------------------------------------------------------------------


def resumo_por_rede(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega por rede: n_unidades e top 3 cidades.

    Entrada: ``df_validos_geo`` (resultado de :func:`join_uf_cidade`).
    Retorna DataFrame ``[rede, n_unidades, top3_cidades]`` ordenado por
    ``n_unidades`` decrescente.
    """

    def _top3(grp: pd.DataFrame) -> str:
        cidades = (
            grp["nome_municipio"]
            .dropna()
            .value_counts()
            .head(3)
            .index.tolist()
        )
        return ", ".join(cidades) if cidades else "—"

    contagem = df.groupby("rede").size().reset_index(name="n_unidades")
    top3 = (
        df.groupby("rede", group_keys=False)
        .apply(_top3, include_groups=False)
        .reset_index()
    )
    top3.columns = ["rede", "top3_cidades"]
    resultado = contagem.merge(top3, on="rede").sort_values(
        "n_unidades", ascending=False
    )
    return resultado.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Passo 4 — Resumo por UF
# ---------------------------------------------------------------------------


def resumo_por_uf(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega por UF: n_unidades e n_redes distintas.

    Entrada: ``df_validos_geo``.
    Retorna DataFrame ``[uf, n_unidades, n_redes]`` ordenado por
    ``n_unidades`` decrescente. Linhas sem UF são excluídas.
    """
    df_com_uf = df.dropna(subset=["uf"])
    resultado = (
        df_com_uf.groupby("uf")
        .agg(n_unidades=("rede", "size"), n_redes=("rede", "nunique"))
        .reset_index()
        .sort_values("n_unidades", ascending=False)
    )
    return resultado.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Passo 5 — Rede dominante por UF
# ---------------------------------------------------------------------------


def rede_dominante_por_uf(df_mkt: pd.DataFrame) -> pd.DataFrame:
    """Identifica a rede dominante por UF com base em ``rede_dominante_2km``.

    Filtra hexes com ``rede_dominante_2km`` não nula, conta hexes por
    ``(uf, rede_dominante_2km)`` e retorna a rede com mais hexes por UF.
    Retorna DataFrame ``[uf, rede_dominante, n_hexes]``.
    """
    df_dom = df_mkt.dropna(subset=["rede_dominante_2km"])
    if df_dom.empty:
        return pd.DataFrame(columns=["uf", "rede_dominante", "n_hexes"])

    contagem = (
        df_dom.groupby(["uf", "rede_dominante_2km"])
        .size()
        .reset_index(name="n_hexes")
    )
    idx_max = contagem.groupby("uf")["n_hexes"].idxmax()
    resultado = contagem.loc[idx_max].rename(
        columns={"rede_dominante_2km": "rede_dominante"}
    )
    return resultado.sort_values("n_hexes", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Passo 6 — Impacto residual
# ---------------------------------------------------------------------------


def impacto_residual(df_mkt: pd.DataFrame) -> dict:
    """Calcula oferta consumida e disponível total e por UF.

    Retorna dict com:
    - ``oferta_consumida_total`` (float)
    - ``oferta_disponivel_total`` (float)
    - ``por_uf`` (DataFrame: uf | oferta_consumida | oferta_disponivel | n_hexes)
    """
    oferta_consumida_total = float(
        df_mkt["oferta_consumida_mercado_estimada"].sum()
    )
    oferta_disponivel_total = float(df_mkt["oferta_efetiva_disponivel"].sum())
    por_uf = (
        df_mkt.groupby("uf")
        .agg(
            oferta_consumida=("oferta_consumida_mercado_estimada", "sum"),
            oferta_disponivel=("oferta_efetiva_disponivel", "sum"),
            n_hexes=("hex_id", "count"),
        )
        .reset_index()
        .sort_values("oferta_consumida", ascending=False)
    )
    return {
        "oferta_consumida_total": oferta_consumida_total,
        "oferta_disponivel_total": oferta_disponivel_total,
        "por_uf": por_uf,
    }


# ---------------------------------------------------------------------------
# Passo 7 — Resumo densos (TotalPass/Wellhub separados)
# ---------------------------------------------------------------------------


def resumo_densos(df_denso: pd.DataFrame) -> dict:
    """Sumariza a base complementar de concorrentes densos.

    TotalPass/Wellhub são reportados separadamente — NÃO somados ao
    ``oferta_consumida_mercado_estimada`` do M1 (risco de dupla contagem).

    Retorna dict com:
    - ``total_linhas`` (int)
    - ``por_fonte`` (dict fonte → contagem)
    - ``totalpass_wellhub`` (int: linhas das fontes agregadoras)
    - ``redes_adicionais`` (list: redes de TotalPass/Wellhub != "independente")
    """
    total_linhas = len(df_denso)
    por_fonte = df_denso.groupby("fonte").size().to_dict()
    mask_agr = df_denso["fonte"].isin(FONTES_AGREGADORAS)
    totalpass_wellhub = int(mask_agr.sum())
    redes_adicionais = sorted(
        df_denso.loc[mask_agr & (df_denso["rede_normalizada"] != "independente"), "rede_normalizada"]
        .dropna()
        .unique()
        .tolist()
    )
    return {
        "total_linhas": total_linhas,
        "por_fonte": por_fonte,
        "totalpass_wellhub": totalpass_wellhub,
        "redes_adicionais": redes_adicionais,
    }


# ---------------------------------------------------------------------------
# Helpers de formatação
# ---------------------------------------------------------------------------


def _fmt_int(v: float | int) -> str:
    """Formata número inteiro com separador de milhar (ponto)."""
    return f"{int(round(v)):,}".replace(",", ".")


def _tabela_md(df: pd.DataFrame, cols: list[str] | None = None) -> str:
    """Converte DataFrame em tabela Markdown simples."""
    if cols is not None:
        df = df[cols]
    header = "| " + " | ".join(str(c) for c in df.columns) + " |"
    sep = "| " + " | ".join(["---"] * len(df.columns)) + " |"
    rows = []
    for _, row in df.iterrows():
        cells = " | ".join(str(v) for v in row)
        rows.append(f"| {cells} |")
    return "\n".join([header, sep] + rows)


# ---------------------------------------------------------------------------
# Passo 8 — Geração do relatório Markdown
# ---------------------------------------------------------------------------


def gerar_relatorio(resultados: dict, output_path: Path) -> str:
    """Monta o relatório em Markdown e escreve em output_path.

    Retorna o conteúdo como str.
    """
    por_rede: pd.DataFrame = resultados["por_rede"]
    por_uf: pd.DataFrame = resultados["por_uf"]
    dom_uf: pd.DataFrame = resultados["dom_uf"]
    residual: dict = resultados["residual"]
    densos: dict = resultados["densos"]
    df_geo: pd.DataFrame = resultados["df_geo"]

    n_validos = len(df_geo)
    n_redes = df_geo["rede"].nunique()
    n_ufs = df_geo["uf"].dropna().nunique()
    sem_uf = int(df_geo["uf"].isna().sum())

    # Seção 1 — Resumo executivo
    sec1 = f"""## 1. Resumo executivo

- **Unidades válidas mapeadas:** {_fmt_int(n_validos)}
- **Redes identificadas:** {n_redes}
- **UFs com presença mapeada:** {n_ufs}
- **Unidades sem UF (hex não encontrado no mercado):** {sem_uf}
- **Período de coleta (concorrentes_mapeados):** {DATA_COLETA_CONC}
- **Data do snapshot de mercado (hexagonos_mercado_mapeado):** {DATA_SNAPSHOT_MKT}
"""

    # Seção 2 — Por rede
    df_rede_fmt = por_rede.copy()
    sec2 = f"""## 2. Contagem por rede (base mapeada)

{_tabela_md(df_rede_fmt, ["rede", "n_unidades", "top3_cidades"])}
"""

    # Seção 3 — Por UF
    sec3 = f"""## 3. Distribuição por UF

{_tabela_md(por_uf, ["uf", "n_unidades", "n_redes"])}
"""

    # Seção 4 — Top 10 municípios
    top10 = top_municipios(df_geo, n=10)
    sec4 = f"""## 4. Top 10 municípios por número de unidades concorrentes

{_tabela_md(top10, ["nome_municipio", "uf", "n_unidades"])}
"""

    # Seção 5 — Oferta consumida e residual por UF (top 15)
    uf_res = residual["por_uf"].head(15).copy()
    uf_res["oferta_consumida"] = uf_res["oferta_consumida"].map(
        lambda v: _fmt_int(v)
    )
    uf_res["oferta_disponivel"] = uf_res["oferta_disponivel"].map(
        lambda v: _fmt_int(v)
    )
    oferta_consumida_total = _fmt_int(residual["oferta_consumida_total"])
    oferta_disponivel_total = _fmt_int(residual["oferta_disponivel_total"])
    sec5 = f"""## 5. Oferta consumida e residual por UF (top 15 por oferta consumida)

> Valores em alunos estimados. Oferta consumida = concorrentes + Ultra na camada de mercado.
> Oferta disponível = mercado residual (Residual Fitness).

{_tabela_md(uf_res, ["uf", "oferta_consumida", "oferta_disponivel", "n_hexes"])}

**Total nacional:** consumida = {oferta_consumida_total} alunos | disponível = {oferta_disponivel_total} alunos
"""

    # Seção 6 — Rede dominante por UF
    n_hexes_dom = int(dom_uf["n_hexes"].sum()) if not dom_uf.empty else 0
    sec6 = f"""## 6. Rede dominante por UF

> Baseado em `rede_dominante_2km` dos hexágonos do mercado (hexes com concorrente no raio de 2 km).
> Total de hexes com rede dominante identificada: {_fmt_int(n_hexes_dom)}.

{_tabela_md(dom_uf, ["uf", "rede_dominante", "n_hexes"])}
"""

    # Seção 7 — Base complementar (densos)
    por_fonte_str = "\n".join(
        f"  - `{fonte}`: {_fmt_int(cnt)} registros"
        for fonte, cnt in sorted(densos["por_fonte"].items(), key=lambda x: -x[1])
    )
    redes_adic = (
        ", ".join(densos["redes_adicionais"])
        if densos["redes_adicionais"]
        else "nenhuma identificada"
    )
    sec7 = f"""## 7. Base complementar (concorrentes_densos — TotalPass/Wellhub)

> **ATENÇÃO — risco de dupla contagem:** as linhas de fonte `totalpass` e `wellhub`
> incluem academias que já podem estar em `concorrentes_mapeados`. Por isso, esses dados
> são reportados SEPARADAMENTE e **NÃO são somados** ao `oferta_consumida_mercado_estimada`
> do Motor nem ao total de unidades mapeadas (§4 / DEC-013).

- **Total de linhas na base densa:** {_fmt_int(densos["total_linhas"])}
- **Por fonte:**
{por_fonte_str}
- **TotalPass + Wellhub (fontes agregadoras):** {_fmt_int(densos["totalpass_wellhub"])} registros
- **Redes adicionais identificadas (TotalPass/Wellhub, excl. "independente"):** {redes_adic}
"""

    # Seção 8 — Notas metodológicas
    sec8 = f"""## 8. Notas metodológicas e limitações

- **Snapshot único:** este relatório representa um retrato pontual do período de coleta.
  Deltas temporais (crescimento/fechamento de unidades) não estão disponíveis neste snapshot.
  Com a coleta semanal automatizada na VPS (DEC-013), novas execuções deste script
  gerarão retratos atualizados.
- **Join via hex_id_res7:** o enriquecimento de UF/cidade usa `hex_id_res7`
  (H3 resolução 7) como chave de junção com `hexagonos_mercado_mapeado.parquet`.
  Unidades sem correspondência no mercado ({sem_uf} casos) ficam sem UF/cidade.
- **READ-ONLY sobre o M1:** este script não altera `score_priorizacao`,
  `hex_score_estrutural`, carteira, plano ou quaisquer artefatos oficiais do M1.
  Escreve apenas em `data/analysis/` (gitignored).
- **TotalPass/Wellhub:** reportados somente na Seção 7 para evitar dupla contagem
  com a oferta já consumida na camada de mercado do Motor.
- **Fontes:** `concorrentes_mapeados.parquet` ({DATA_COLETA_CONC}),
  `hexagonos_mercado_mapeado.parquet` (snapshot {DATA_SNAPSHOT_MKT}).
"""

    conteudo = f"""# Relatório de Movimentação Concorrencial

> **Fonte:** dados de staging (`data/staging/`). Snapshot único — sem série histórica.
> Retrato da concorrência referente ao período de coleta {DATA_COLETA_CONC}
> (concorrentes_mapeados) e ao snapshot de mercado {DATA_SNAPSHOT_MKT} (hexagonos_mercado_mapeado).
> **Limitação:** este relatório é um retrato pontual; deltas temporais não estão disponíveis.
> Quando novos snapshots forem coletados (coleta semanal VPS, DEC-013), o script pode ser
> re-executado para gerar um relatório atualizado.

{sec1}
{sec2}
{sec3}
{sec4}
{sec5}
{sec6}
{sec7}
{sec8}"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(conteudo, encoding="utf-8")
    return conteudo


# ---------------------------------------------------------------------------
# Passo 9 — Orquestrador principal
# ---------------------------------------------------------------------------


def run(
    staging_dir: Path | None = None,
    analysis_dir: Path | None = None,
) -> Path:
    """Orquestra todos os passos e retorna o caminho do relatório gerado."""
    staging_dir = staging_dir or STAGING_DIR
    analysis_dir = analysis_dir or ANALYSIS_DIR

    print("=== Relatório de Movimentação Concorrencial ===")

    print("  [1/7] Carregando dados...")
    df_conc, df_denso, df_mkt = carregar_dados(staging_dir)
    print(f"        concorrentes_mapeados: {len(df_conc):,} linhas")
    print(f"        concorrentes_densos:   {len(df_denso):,} linhas")
    print(f"        hexagonos_mercado:     {len(df_mkt):,} linhas")

    print("  [2/7] Enriquecendo com UF/cidade...")
    df_geo = join_uf_cidade(df_conc, df_mkt)
    print(f"        {len(df_geo):,} unidades válidas")

    print("  [3/7] Resumo por rede...")
    por_rede = resumo_por_rede(df_geo)
    print(f"        {len(por_rede)} redes identificadas")

    print("  [4/7] Resumo por UF...")
    por_uf = resumo_por_uf(df_geo)

    print("  [5/7] Rede dominante por UF...")
    dom_uf = rede_dominante_por_uf(df_mkt)

    print("  [6/7] Impacto no residual...")
    residual = impacto_residual(df_mkt)

    print("  [7/7] Base complementar (densos)...")
    densos = resumo_densos(df_denso)

    resultados = {
        "por_rede": por_rede,
        "por_uf": por_uf,
        "dom_uf": dom_uf,
        "residual": residual,
        "densos": densos,
        "df_geo": df_geo,
    }

    output_path = analysis_dir / "movimentacao_concorrencial.md"
    print(f"  Gerando relatório em {output_path}...")
    gerar_relatorio(resultados, output_path)
    print(f"  Relatório gerado: {output_path}")

    return output_path


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    path = run()
    print(f"\nConcluído: {path}")
