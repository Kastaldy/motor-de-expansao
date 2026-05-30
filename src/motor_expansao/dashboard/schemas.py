from __future__ import annotations

import h3
import pandas as pd

from motor_expansao.dashboard.constants import REQUIRED_COLUMNS

# Colunas de score com faixa canonica [0,100] (M1 §3, clip 0-100).
# Subconjunto de REQUIRED_COLUMNS (sempre presentes no frame M1/enriquecido cru).
_SCORE_RANGE_REQUIRED = ("score_priorizacao", "hex_score_estrutural")
# Scores presentes apenas no enriquecido/hibrido — checados so se a coluna existe.
_SCORE_RANGE_OPTIONAL = (
    "score_setor_2022_calibrado",
    "score_expansao_hibrido",
    "score_oportunidade_residual",
    "score_dominio_hibrido",
)
# Chaves que nao podem ser nulas no frame de load.
_KEY_COLUMNS = ("hex_id", "uf")


class SchemaValidationError(ValueError):
    """Levantada quando um frame de load do dashboard viola uma invariante de schema.

    Herda de ValueError para ser compativel com o `raise ValueError` que
    `_read_parquet_subset` ja usa no load (app/CI ja lidam com ValueError ali).
    """


def validate_dashboard_frame(df: pd.DataFrame, *, source: str) -> None:
    """Valida invariantes read-only de um frame de load M1/enriquecido.

    NAO muta `df`: toda coercao numerica vive em variavel local e jamais e
    gravada de volta. Levanta `SchemaValidationError` com `source` (arquivo ou
    particao), nome da coluna e a invariante violada ao falhar. Frame vazio
    (`df is None or df.empty`) e no-op — particao inexistente ja e tratada a
    montante.

    Invariantes (nesta ordem):
      b. colunas obrigatorias presentes (REQUIRED_COLUMNS);
      c. chaves `hex_id`/`uf` nao-nulas;
      d. `hex_id` com celulas H3 validas (h3.is_valid_cell sobre os unicos);
      e. colunas de score conversiveis a numerico e dentro de [0,100].
    """
    if df is None or df.empty:
        return

    # b. Colunas obrigatorias presentes.
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise SchemaValidationError(
            f"[{source}] colunas obrigatorias ausentes: {', '.join(missing)}"
        )

    # c. Chaves nao-nulas.
    for col in _KEY_COLUMNS:
        n_null = int(df[col].isna().sum())
        if n_null > 0:
            raise SchemaValidationError(
                f"[{source}] coluna '{col}' tem {n_null} valores nulos "
                "(chave nao pode ser nula)"
            )

    # d. hex_id com celulas H3 validas (so os unicos; O(1) por celula em C).
    uniques = df["hex_id"].dropna().astype(str).unique()
    invalidos = [c for c in uniques if not h3.is_valid_cell(c)]
    if invalidos:
        amostra = ", ".join(invalidos[:5])
        raise SchemaValidationError(
            f"[{source}] coluna 'hex_id' tem {len(invalidos)} celulas H3 "
            f"invalidas (ex.: {amostra})"
        )

    # e. Scores conversiveis a numerico + faixa [0,100].
    score_cols = list(_SCORE_RANGE_REQUIRED) + [
        c for c in _SCORE_RANGE_OPTIONAL if c in df.columns
    ]
    for col in score_cols:
        original = df[col]
        numeric = pd.to_numeric(original, errors="coerce")  # local, nunca reatribuido
        # dtype: coluna nao-numerica cuja coercao criou NaN onde havia valor -> lixo de tipo.
        if not pd.api.types.is_numeric_dtype(original):
            if bool((original.notna() & numeric.isna()).any()):
                raise SchemaValidationError(
                    f"[{source}] coluna de score '{col}' nao e conversivel a numerico"
                )
        # range: NaN e tolerado; rejeita so valores fora de [0,100].
        mask = numeric.notna()
        if bool(mask.any()) and not bool(numeric[mask].between(0, 100).all()):
            vmin = float(numeric[mask].min())
            vmax = float(numeric[mask].max())
            raise SchemaValidationError(
                f"[{source}] coluna 'score' '{col}' viola faixa [0,100]: "
                f"min={vmin}, max={vmax}"
            )
