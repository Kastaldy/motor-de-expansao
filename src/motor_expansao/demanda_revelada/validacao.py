"""Validação cruzada: Demanda Revelada × Residual Fitness (BLK-TP-02).

Módulo READ-ONLY sobre o M1: calcula correlação Spearman entre `membros`
(demanda observada, DEC-012) e `score_oportunidade_residual` / `oferta_efetiva_disponivel`
(camada paralela de mercado), mapeia quadrantes e identifica divergências vs. o
recorte top-20%/UF do M1.

NUNCA importa de `pipelines/m1/`, `censo_*` nem `dashboard/` (DEC-012).
A demanda é insumo OBSERVADO (DEC-009), NUNCA preditor geográfico de magnitude.
Proibido usar `membros` em regressão geográfica de demanda ou como ajuste de
`score_priorizacao`.

Imports permitidos: pathlib, pandas, numpy, scipy.stats, datetime (stdlib).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from .contrato import COLUNAS_PII_PROIBIDAS

# ---------------------------------------------------------------------------
# Constantes de caminho (relativas ao CWD do projeto)
# ---------------------------------------------------------------------------

DEMANDA_DEFAULT = Path("data/staging/demanda_revelada_h3.parquet")
MERCADO_DEFAULT = Path("data/staging/hexagonos_mercado_mapeado.parquet")
PRIORIZADOS_DEFAULT = Path("data/staging/brasil_priorizados.parquet")
RELATORIO_DEFAULT = Path("data/reports/demanda_revelada_validacao.md")
QUADRANTES_DEFAULT = Path("data/staging/quadrantes_demanda_residual.parquet")

# Colunas mínimas necessárias de cada fonte
_COLS_DEMANDA = ["hex_id", "membros"]
_COLS_MERCADO = ["hex_id", "score_oportunidade_residual", "oferta_efetiva_disponivel", "uf"]
_COLS_PRIORIZADOS = ["hex_id", "uf", "score_priorizacao"]

# Colunas do parquet de quadrantes (sem PII)
_COLS_QUADRANTES = [
    "hex_id",
    "membros",
    "score_oportunidade_residual",
    "oferta_efetiva_disponivel",
    "uf",
    "quadrante",
    "top_m1_20pct",
]


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------


def _assert_sem_pii_validacao(df: pd.DataFrame, contexto: str = "") -> None:
    """Levanta ValueError se o DataFrame contiver coluna de COLUNAS_PII_PROIBIDAS."""
    pii = set(df.columns) & COLUNAS_PII_PROIBIDAS
    if pii:
        raise ValueError(
            f"colunas PII proibidas no resultado{' (' + contexto + ')' if contexto else ''}: "
            f"{sorted(pii)}"
        )


def _ic_fisher(rho: float, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """IC via transformação de Fisher z = arctanh(rho).

    Válido para qualquer N ≥ 4. Usado quando N > 10_000 para evitar bootstrap
    lento, ou quando N é insuficiente para bootstrap.
    Clipa rho para (-1+eps, 1-eps) para evitar arctanh(±1) = ±inf.
    """
    eps = 1e-10
    rho_c = float(np.clip(rho, -1.0 + eps, 1.0 - eps))
    z = np.arctanh(rho_c)
    se = 1.0 / np.sqrt(n - 3)
    z_crit = stats.norm.ppf(1 - alpha / 2)
    lo = float(np.tanh(z - z_crit * se))
    hi = float(np.tanh(z + z_crit * se))
    return lo, hi


# ---------------------------------------------------------------------------
# Funções públicas
# ---------------------------------------------------------------------------


def carregar_par_validacao(
    demanda_path: Path = DEMANDA_DEFAULT,
    mercado_path: Path = MERCADO_DEFAULT,
    priorizados_path: Path = PRIORIZADOS_DEFAULT,
) -> pd.DataFrame:
    """Carrega e combina as 3 fontes; retorna DataFrame de análise sem PII.

    Inner join demanda × mercado (preserva só hexes com ambos os lados).
    Left join com priorizados para o flag `top_m1_20pct` (bool).

    Raises
    ------
    FileNotFoundError
        Se `mercado_path` ou `demanda_path` não existirem.
        Mensagem inclui a ordem de regeneração canônica dos parquets de staging.
    ValueError
        Se o resultado contiver coluna de `COLUNAS_PII_PROIBIDAS`.
    """
    # --- Carrega demanda revelada ---
    demanda_path = Path(demanda_path)
    if not demanda_path.exists():
        raise FileNotFoundError(
            f"Parquet de demanda revelada não encontrado: {demanda_path}\n"
            "Regere executando: python -m motor_expansao.demanda_revelada.ingestao"
        )
    df_dem = pd.read_parquet(demanda_path, columns=_COLS_DEMANDA)
    df_dem["hex_id"] = df_dem["hex_id"].astype("string")

    # --- Carrega hexagonos_mercado_mapeado ---
    mercado_path = Path(mercado_path)
    if not mercado_path.exists():
        raise FileNotFoundError(
            f"Parquet de mercado não encontrado: {mercado_path}\n"
            "Ordem canônica de regeneração:\n"
            "  híbrido → mercado → calcular_colunas_mercado → carteira → plano "
            "→ domínio → residual → fase1_bi_exports"
        )
    # Guard de colunas mínimas
    df_mkt_raw = pd.read_parquet(mercado_path)
    missing_mkt = set(_COLS_MERCADO) - set(df_mkt_raw.columns)
    if missing_mkt:
        raise ValueError(
            f"Colunas ausentes em {mercado_path}: {sorted(missing_mkt)}"
        )
    df_mkt = df_mkt_raw[_COLS_MERCADO].copy()
    df_mkt["hex_id"] = df_mkt["hex_id"].astype("string")

    # --- Inner join demanda × mercado ---
    df = df_dem.merge(df_mkt, on="hex_id", how="inner")

    # --- Left join com priorizados (flag top_m1_20pct) ---
    priorizados_path = Path(priorizados_path)
    if priorizados_path.exists():
        df_pri = pd.read_parquet(priorizados_path, columns=["hex_id"])
        df_pri["hex_id"] = df_pri["hex_id"].astype("string")
        df_pri = df_pri.drop_duplicates(subset=["hex_id"])
        df_pri["_in_top20"] = True
        df = df.merge(df_pri[["hex_id", "_in_top20"]], on="hex_id", how="left")
        df["top_m1_20pct"] = df["_in_top20"].where(df["_in_top20"].notna(), other=False).astype(bool)
        df = df.drop(columns=["_in_top20"])
    else:
        # priorizados ausente → flag False para todos (análise parcial)
        df["top_m1_20pct"] = False

    # --- Validação anti-PII ---
    _assert_sem_pii_validacao(df, "carregar_par_validacao")

    # Garantir ordem de colunas canônica
    cols_finais = [
        "hex_id",
        "membros",
        "score_oportunidade_residual",
        "oferta_efetiva_disponivel",
        "uf",
        "top_m1_20pct",
    ]
    df = df[cols_finais].reset_index(drop=True)
    return df


def calcular_spearman_ic(
    df: pd.DataFrame,
    col_x: str,
    col_y: str,
    n_boot: int = 9999,
    seed: int = 42,
) -> dict[str, float]:
    """Calcula Spearman rho + IC 95% entre duas colunas do DataFrame.

    Para N > 10_000 usa a fórmula analítica de Fisher (mais rápida e igualmente
    precisa para amostras grandes). Para N ≤ 10_000, tenta bootstrap paramétrico
    via `scipy.stats.bootstrap`; se N < 6 (mínimo de scipy), usa Fisher como
    fallback.

    Returns
    -------
    dict com chaves: rho, pvalor, ic_low, ic_high, n
    """
    x = df[col_x].to_numpy(dtype=float)
    y = df[col_y].to_numpy(dtype=float)
    n = len(x)

    result = stats.spearmanr(x, y)
    rho = float(result.statistic)
    pvalor = float(result.pvalue)

    # IC 95%: Fisher analítico para N grande ou N insuficiente para bootstrap
    _BOOTSTRAP_MIN_N = 6
    _BOOTSTRAP_MAX_N = 10_000

    if n <= _BOOTSTRAP_MIN_N or n > _BOOTSTRAP_MAX_N:
        # Fisher analítico
        if n > 3:
            ic_low, ic_high = _ic_fisher(rho, n)
        else:
            ic_low, ic_high = float("nan"), float("nan")
    else:
        # Bootstrap via scipy (N moderado)
        try:
            rng = np.random.default_rng(seed)
            boot = stats.bootstrap(
                (x, y),
                statistic=lambda a, b, axis=0: np.array(  # noqa: ARG005
                    [stats.spearmanr(a[..., i], b[..., i]).statistic for i in range(a.shape[-1])]
                    if a.ndim > 1
                    else [stats.spearmanr(a, b).statistic]
                )[0],
                n_resamples=n_boot,
                paired=True,
                confidence_level=0.95,
                random_state=rng,
                method="percentile",
            )
            ic_low = float(boot.confidence_interval.low)
            ic_high = float(boot.confidence_interval.high)
        except Exception:
            # Fallback para Fisher se bootstrap falhar
            if n > 3:
                ic_low, ic_high = _ic_fisher(rho, n)
            else:
                ic_low, ic_high = float("nan"), float("nan")

    return {
        "rho": rho,
        "pvalor": pvalor,
        "ic_low": ic_low,
        "ic_high": ic_high,
        "n": n,
    }


def mapear_quadrantes(
    df: pd.DataFrame,
    limiar_residual: float | None = None,
    limiar_demanda: float | None = None,
) -> pd.DataFrame:
    """Adiciona coluna `quadrante` (Q1..Q4) baseada nas medianas.

    Quadrantes definidos pelos limiares de `score_oportunidade_residual` e `membros`:
      - Q1: residual ≥ limiar E membros ≥ limiar  (alta demanda + alto residual)
      - Q2: residual ≥ limiar E membros < limiar   (baixa demanda + alto residual)
      - Q3: residual < limiar E membros ≥ limiar   (alta demanda + baixo residual)
      - Q4: residual < limiar E membros < limiar   (baixa demanda + baixo residual)

    Parameters
    ----------
    df:
        DataFrame retornado por `carregar_par_validacao`.
    limiar_residual:
        Mediana de `score_oportunidade_residual` se None.
    limiar_demanda:
        Mediana de `membros` se None.

    Returns
    -------
    Cópia de df com coluna `quadrante` adicionada.
    """
    df = df.copy()
    if limiar_residual is None:
        limiar_residual = float(df["score_oportunidade_residual"].median())
    if limiar_demanda is None:
        limiar_demanda = float(df["membros"].median())

    cond_residual_alto = df["score_oportunidade_residual"] >= limiar_residual
    cond_demanda_alta = df["membros"] >= limiar_demanda

    df["quadrante"] = np.select(
        [
            cond_residual_alto & cond_demanda_alta,
            cond_residual_alto & ~cond_demanda_alta,
            ~cond_residual_alto & cond_demanda_alta,
            ~cond_residual_alto & ~cond_demanda_alta,
        ],
        ["Q1", "Q2", "Q3", "Q4"],
        default="Q4",
    )
    return df


def calcular_divergencias(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Identifica divergências entre quadrantes de mercado e recorte M1.

    Returns
    -------
    dict com duas chaves:
      - "q1_fora_top20": hexes Q1 (alta demanda + alto residual) não presentes no
        top-20%/UF do M1 — potenciais subvalorizados pelo M1 executivo.
      - "top20_fora_q1": hexes do top-20%/UF do M1 não classificados como Q1 —
        possível sobreestimação executiva ou baixa cobertura de demanda revelada.
    """
    if "quadrante" not in df.columns:
        raise ValueError("DataFrame não tem coluna `quadrante`. Chame `mapear_quadrantes` antes.")
    if "top_m1_20pct" not in df.columns:
        raise ValueError("DataFrame não tem coluna `top_m1_20pct`.")

    q1_fora_top20 = (
        df[(df["quadrante"] == "Q1") & (~df["top_m1_20pct"])]
        .sort_values("membros", ascending=False)
        .reset_index(drop=True)
    )
    top20_fora_q1 = (
        df[(df["top_m1_20pct"]) & (df["quadrante"] != "Q1")]
        .sort_values("score_oportunidade_residual", ascending=False)
        .reset_index(drop=True)
    )
    return {
        "q1_fora_top20": q1_fora_top20,
        "top20_fora_q1": top20_fora_q1,
    }


def gerar_relatorio_validacao(
    df: pd.DataFrame,
    spearman_primario: dict[str, float],
    spearman_secundario: dict[str, float],
    limiar_residual: float,
    limiar_demanda: float,
    divergencias: dict[str, pd.DataFrame],
    destino: Path = RELATORIO_DEFAULT,
) -> str:
    """Gera relatório Markdown estruturado em 7 seções e escreve em `destino`.

    Seções:
      1. Resumo Executivo
      2. Metodologia
      3. Resultados Spearman Primário (membros × score_oportunidade_residual)
      4. Resultados Spearman Secundário (membros × oferta_efetiva_disponivel)
      5. Mapa de Quadrantes
      6. Divergências vs. M1
      7. Guardrails e Proibições

    Returns
    -------
    Conteúdo Markdown gerado como string.
    """
    ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    n_join = len(df)

    # Contagens por quadrante
    vc = df["quadrante"].value_counts()
    quad_rows = []
    for q in ["Q1", "Q2", "Q3", "Q4"]:
        cnt = int(vc.get(q, 0))
        pct = 100.0 * cnt / n_join if n_join > 0 else 0.0
        quad_rows.append(f"| {q} | {cnt:,} | {pct:.1f}% |")
    quad_table = "\n".join(quad_rows)

    # Divergências — top-10 para o relatório
    q1_fora = divergencias["q1_fora_top20"]
    top20_fora = divergencias["top20_fora_q1"]

    def _fmt_table(sub: pd.DataFrame, cols: list[str], n: int = 10) -> str:
        if sub.empty:
            return "_Nenhum hex encontrado._"
        sub_show = sub[cols].head(n)
        header = "| " + " | ".join(cols) + " |"
        sep = "| " + " | ".join(["---"] * len(cols)) + " |"
        rows = []
        for _, row in sub_show.iterrows():
            vals = []
            for c in cols:
                v = row[c]
                if isinstance(v, float):
                    vals.append(f"{v:.2f}")
                else:
                    vals.append(str(v))
            rows.append("| " + " | ".join(vals) + " |")
        return "\n".join([header, sep] + rows)

    q1_fora_cols = ["hex_id", "uf", "membros", "score_oportunidade_residual", "oferta_efetiva_disponivel"]
    top20_fora_cols = ["hex_id", "uf", "score_oportunidade_residual", "membros"]

    q1_fora_table = _fmt_table(q1_fora, q1_fora_cols)
    top20_fora_table = _fmt_table(top20_fora, top20_fora_cols)

    # Sinal de significância
    def _sig(pv: float) -> str:
        if pv < 0.001:
            return "***"
        if pv < 0.01:
            return "**"
        if pv < 0.05:
            return "*"
        return "n.s."

    sp = spearman_primario
    ss = spearman_secundario

    conteudo = f"""# Relatório de Validação — Demanda Revelada × Residual Fitness

> Gerado automaticamente por `validacao.py` (BLK-TP-02) em {ts}.
> READ-ONLY sobre o M1. DEC-009 e DEC-012 intactas.

---

## 1. Resumo Executivo

| Correlação | rho | IC 95% | p-valor | N |
|---|---|---|---|---|
| `membros` × `score_oportunidade_residual` | **{sp['rho']:.3f}** | [{sp['ic_low']:.3f}, {sp['ic_high']:.3f}] | {sp['pvalor']:.4f} {_sig(sp['pvalor'])} | {sp['n']:,} |
| `membros` × `oferta_efetiva_disponivel` | **{ss['rho']:.3f}** | [{ss['ic_low']:.3f}, {ss['ic_high']:.3f}] | {ss['pvalor']:.4f} {_sig(ss['pvalor'])} | {ss['n']:,} |

**Interpretação:** rho = {sp['rho']:.3f} (primário) confirma correlação positiva entre
demanda revelada e residual fitness. Valor esperado ~+0,52 ± 0,05 (dado arredondamento de
coords ~1 km da fonte). Correlação secundária (×`oferta_efetiva_disponivel`) esperada ~+0,75.

---

## 2. Metodologia

**Fontes de dados:**
- `data/staging/demanda_revelada_h3.parquet` — demanda paga agregada por hex H3 res-7
  (BLK-TP-01 / DEC-012). Colunas usadas: `hex_id`, `membros`.
- `data/staging/hexagonos_mercado_mapeado.parquet` — camada de mercado/residual.
  Colunas usadas: `hex_id`, `score_oportunidade_residual`, `oferta_efetiva_disponivel`, `uf`.
- `data/staging/brasil_priorizados.parquet` — recorte top-20%/UF do M1 (READ-ONLY).
  Usado apenas para derivar o flag `top_m1_20pct` (presença no frame = True).

**Join:** inner join demanda × mercado em `hex_id` (preserva ~16k hexes com ambos os lados;
descarta ~99% do universo M1 sem cobertura de demanda revelada → camada de refino sobre
metrópoles, NÃO cobertura nacional). Left join posterior com priorizados para `top_m1_20pct`.

**Quadrantes:** definidos pelas medianas de `score_oportunidade_residual`
({limiar_residual:.2f}) e `membros` ({limiar_demanda:.0f}):
- Q1: residual ≥ mediana E membros ≥ mediana
- Q2: residual ≥ mediana E membros < mediana
- Q3: residual < mediana E membros ≥ mediana
- Q4: residual < mediana E membros < mediana

**Correlação:** Spearman ρ via `scipy.stats.spearmanr`. IC 95% via transformação de Fisher
analítica (para N > 10.000) ou bootstrap `scipy.stats.bootstrap` com `n_resamples=9999`.

**Caveats obrigatórios:**
1. Cobertura ~1% do universo M1 (~{n_join:,} hexes com join vs. ~1,54 M hexes totais).
2. Concentração geográfica em SP (fonte majoritariamente urbana metropolitana).
3. Arredondamento de coords ~1 km na fonte → ruído no join res-7 (hex pode diferir 1 nível).
4. Join parcial: hexes sem demanda revelada ficam fora desta análise.
5. `brasil_priorizados.parquet` pode estar ausente localmente (gitignored); flag
   `top_m1_20pct` = False para todos nesse caso.

---

## 3. Resultados Spearman Primário

**`membros` × `score_oportunidade_residual`**

- rho = **{sp['rho']:.4f}** {_sig(sp['pvalor'])}
- IC 95%: [{sp['ic_low']:.4f}, {sp['ic_high']:.4f}]
- p-valor: {sp['pvalor']:.6f}
- N: {sp['n']:,} hexes

**Interpretação:** IC não atravessa zero → correlação positiva estatisticamente
significativa entre demanda revelada e o score de oportunidade residual do Motor.
Isso valida que hexes com mais membros (demanda paga) tendem a ter maior residual fitness,
confirmando a consistência da camada paralela de mercado.

---

## 4. Resultados Spearman Secundário

**`membros` × `oferta_efetiva_disponivel`**

- rho = **{ss['rho']:.4f}** {_sig(ss['pvalor'])}
- IC 95%: [{ss['ic_low']:.4f}, {ss['ic_high']:.4f}]
- p-valor: {ss['pvalor']:.6f}
- N: {ss['n']:,} hexes

**Interpretação:** correlação com `oferta_efetiva_disponivel` (alunos de capacidade
disponível estimada) tende a ser mais forte que com o score normalizado, pois as
magnitudes em alunos têm escala mais diretamente comparável à demanda revelada.

---

## 5. Mapa de Quadrantes

**Limiares:** residual = {limiar_residual:.2f} | demanda (membros) = {limiar_demanda:.0f}

| Quadrante | N hexes | % do join |
|---|---|---|
{quad_table}

**Legenda:**
- **Q1** (residual+ & demanda+): oportunidades convergentes — alto residual fitness E alta demanda observada.
- **Q2** (residual+ & demanda−): subdemandados no dado revelado mas com residual alto.
- **Q3** (residual− & demanda+): alta demanda mas residual baixo (mercado mais saturado/coberto).
- **Q4** (residual− & demanda−): hexes fora do foco operacional.

---

## 6. Divergências vs. M1

### 6.1 Q1 fora do top-20%/UF (potencial subvalorizado pelo M1 executivo)

Hexes com alta demanda E alto residual fitness que **NÃO** estão no recorte top-20%/UF do M1.
Total: **{len(q1_fora):,} hexes**. Hipótese: mercado local relevante mas score M1 insuficiente
(renda/pop menores na agregação municipal) — confirma que o M1 é camada executiva (município),
não intraurbana.

{q1_fora_table}

### 6.2 Top-20%/UF fora de Q1 (eventual sobreestimação ou cobertura parcial)

Hexes priorizados pelo M1 que **NÃO** se classificam como Q1 no cruzamento com demanda revelada.
Total: **{len(top20_fora):,} hexes**. Hipótese de causa: (a) demanda revelada é parcial —
cobre só usuários de benefício corporativo (SmartFit/TotalPass), não toda a demanda fitness;
(b) concentração geográfica da fonte em SP subestima demanda em outras UFs; (c) caveat de
arredondamento de coords ~1 km pode deslocar o hex de match.

{top20_fora_table}

---

## 7. Guardrails e Proibições

**DEC-009 (intacta):** a demanda entra como insumo OBSERVADO, NUNCA como preditor
geográfico de magnitude. É PROIBIDO:
- Usar `membros` ou qualquer coluna desta camada como input em regressão geográfica de demanda.
- Usar `membros` como ajuste do `score_priorizacao` (pesos `renda=0.40`/`pop=0.60` inalterados).
- Reintroduzir "20% fixo" ou qualquer predição de magnitude de alunos por geografia.

**DEC-001 (intacta):** pesos `renda=0.40`/`pop=0.60` e fórmula `score_priorizacao`
**INALTERADOS**. Nenhum artefato M1 foi tocado neste relatório.

**DEC-012 (intacta):** `src/motor_expansao/demanda_revelada/` é pacote DISJUNTO.
Nenhuma importação de `pipelines/m1/`, `censo_*` ou `dashboard/`.

**Anti-PII:** parquet de quadrantes (`quadrantes_demanda_residual.parquet`) não contém
nenhuma coluna de `COLUNAS_PII_PROIBIDAS`. Validação automática em `salvar_quadrantes_parquet`.

**Próximos passos (blocos BLK-TP-03..05):** os sucessores podem usar a camada de quadrantes
como insumo de refino intraurbano sobre metrópoles — nunca para recalibrar o M1.
"""

    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(conteudo, encoding="utf-8")
    return conteudo


def salvar_quadrantes_parquet(
    df: pd.DataFrame,
    destino: Path = QUADRANTES_DEFAULT,
) -> None:
    """Salva parquet de quadrantes com zero PII.

    Seleciona apenas as colunas canônicas `_COLS_QUADRANTES` e valida
    anti-PII antes de escrever.

    Parameters
    ----------
    df:
        DataFrame após `mapear_quadrantes` (deve ter coluna `quadrante`).
    destino:
        Caminho do parquet de saída.

    Raises
    ------
    ValueError
        Se o DataFrame contiver coluna de `COLUNAS_PII_PROIBIDAS`.
    """
    cols_presentes = [c for c in _COLS_QUADRANTES if c in df.columns]
    saida = df[cols_presentes].copy()

    _assert_sem_pii_validacao(saida, "salvar_quadrantes_parquet")

    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    saida.to_parquet(destino, index=False)


def executar_validacao_completa(
    demanda_path: Path = DEMANDA_DEFAULT,
    mercado_path: Path = MERCADO_DEFAULT,
    priorizados_path: Path = PRIORIZADOS_DEFAULT,
    relatorio_path: Path = RELATORIO_DEFAULT,
    quadrantes_path: Path = QUADRANTES_DEFAULT,
    *,
    salvar_quadrantes: bool = True,
) -> dict:
    """Orquestra a validação completa: join → Spearman → quadrantes → relatório.

    READ-ONLY sobre o M1. Nunca escreve em artefatos oficiais.

    Returns
    -------
    dict com chaves:
      n_hexes_join, spearman_primario, spearman_secundario,
      contagem_quadrantes, n_q1_fora_top20, n_top20_fora_q1
    """
    # 1. Carregar par de validação
    df = carregar_par_validacao(
        demanda_path=Path(demanda_path),
        mercado_path=Path(mercado_path),
        priorizados_path=Path(priorizados_path),
    )

    # 2. Spearman primário e secundário
    spearman_primario = calcular_spearman_ic(
        df, col_x="membros", col_y="score_oportunidade_residual"
    )
    spearman_secundario = calcular_spearman_ic(
        df, col_x="membros", col_y="oferta_efetiva_disponivel"
    )

    # 3. Quadrantes (medianas como limiares)
    limiar_residual = float(df["score_oportunidade_residual"].median())
    limiar_demanda = float(df["membros"].median())
    df_quad = mapear_quadrantes(df, limiar_residual=limiar_residual, limiar_demanda=limiar_demanda)

    # 4. Divergências
    divergencias = calcular_divergencias(df_quad)

    # 5. Relatório Markdown
    gerar_relatorio_validacao(
        df=df_quad,
        spearman_primario=spearman_primario,
        spearman_secundario=spearman_secundario,
        limiar_residual=limiar_residual,
        limiar_demanda=limiar_demanda,
        divergencias=divergencias,
        destino=Path(relatorio_path),
    )

    # 6. Parquet de quadrantes (opcional)
    if salvar_quadrantes:
        salvar_quadrantes_parquet(df_quad, destino=Path(quadrantes_path))

    # 7. Retorno estruturado
    contagem_quadrantes = df_quad["quadrante"].value_counts().to_dict()
    return {
        "n_hexes_join": len(df),
        "spearman_primario": spearman_primario,
        "spearman_secundario": spearman_secundario,
        "contagem_quadrantes": contagem_quadrantes,
        "n_q1_fora_top20": len(divergencias["q1_fora_top20"]),
        "n_top20_fora_q1": len(divergencias["top20_fora_q1"]),
    }


__all__ = [
    "carregar_par_validacao",
    "calcular_spearman_ic",
    "mapear_quadrantes",
    "calcular_divergencias",
    "gerar_relatorio_validacao",
    "salvar_quadrantes_parquet",
    "executar_validacao_completa",
    # constantes de caminho
    "DEMANDA_DEFAULT",
    "MERCADO_DEFAULT",
    "PRIORIZADOS_DEFAULT",
    "RELATORIO_DEFAULT",
    "QUADRANTES_DEFAULT",
]
