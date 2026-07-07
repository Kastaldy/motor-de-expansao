"""Módulo de validação e limpeza da base de imóveis candidatos (BLK-VIAB-01).

READ-ONLY sobre o M1: nao recalcula `score_priorizacao`, `hex_score_estrutural`,
pesos, carteira, plano nem artefatos oficiais do M1 (DEC-001/DEC-009).

Camada PARALELA de Viabilidade (epic BLK-VIAB). Materializa:
  - data/staging/imoveis_candidatos_limpos.parquet
  - data/analysis/imoveis_qualidade.md
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Constantes LOCAIS ao módulo — NÃO tocar config.py do M1 nem do dimensionamento
# ---------------------------------------------------------------------------

AREA_MIN_M2: float = 500.0
ALUGUEL_MIN: float = 10_000.0
ALUGUEL_MAX: float = 500_000.0
ALUGUEL_PLACEHOLDER: float = 11_111.11
PLACEHOLDER_TOLERANCIA: float = 0.01

COLUNAS_ESPERADAS: tuple[str, ...] = (
    "ID",
    "NOME",
    "ÁREA",
    "VAGAS",
    "ALUGUEL",
    "LOGRADOURO",
    "NÚMERO",
    "COMPLEMENTO",
    "BAIRRO",
    "CIDADE",
    "ESTADO",
    "CEP",
    "LATITUDE",
    "LONGITUDE",
    "DATA CADASTRO",
    "DATA ATUALIZAÇÃO",
    "STATUS",
    "ATIVO",
    "DESCRIÇÃO",
)


# ---------------------------------------------------------------------------
# Função 1 — leitura do xlsx
# ---------------------------------------------------------------------------


def ler_imoveis_xlsx(path: Path | str) -> pd.DataFrame:
    """Lê a aba 'Imóveis' do xlsx de candidatos e retorna o DataFrame bruto.

    O arquivo tem 2 linhas antes do cabeçalho real:
    - Linha 0: título do relatório
    - Linha 1: linha vazia
    - Linha 2: cabeçalhos das colunas  (header=2)

    Raises:
        ValueError: se alguma coluna de COLUNAS_ESPERADAS estiver ausente.
    """
    df = pd.read_excel(Path(path), sheet_name="Imóveis", header=2)
    faltantes = set(COLUNAS_ESPERADAS) - set(df.columns)
    if faltantes:
        raise ValueError(f"Colunas ausentes no xlsx: {sorted(faltantes)}")
    return df


# ---------------------------------------------------------------------------
# Função 2 — validação e limpeza
# ---------------------------------------------------------------------------


def validar_e_limpar(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Aplica 3 filtros sequenciais e adiciona flag_sem_coord.

    Filtros em sequência (cada um opera sobre o df residual):
    1. Descarta ÁREA < 500 m²  (erro de cadastro / sala comercial pequena).
    2. Descarta aluguel placeholder (abs(ALUGUEL - 11_111.11) < 0.01).
    3. Descarta aluguel fora do range [10.000, 500.000].

    Registros sem coordenada (LATITUDE ou LONGITUDE NaN) recebem
    flag_sem_coord=True mas são MANTIDOS no df_limpo.

    Returns:
        (df_limpo, resumo) — df com reset de índice + dict de contagens.
    """
    total_entrada = len(df)

    # Garantir tipos numéricos (coerce strings raras de locales)
    area = pd.to_numeric(df["ÁREA"], errors="coerce")
    aluguel = pd.to_numeric(df["ALUGUEL"], errors="coerce")

    # --- Filtro 1: área ---
    mask_area_ok = area >= AREA_MIN_M2
    descartados_area = int((~mask_area_ok).sum())
    df1 = df.loc[mask_area_ok].copy()
    aluguel1 = aluguel.loc[mask_area_ok]

    # --- Filtro 2: placeholder ---
    mask_placeholder = (aluguel1 - ALUGUEL_PLACEHOLDER).abs() < PLACEHOLDER_TOLERANCIA
    descartados_placeholder = int(mask_placeholder.sum())
    df2 = df1.loc[~mask_placeholder].copy()
    aluguel2 = aluguel1.loc[~mask_placeholder]

    # --- Filtro 3: aluguel fora de range ---
    mask_range_ok = aluguel2.between(ALUGUEL_MIN, ALUGUEL_MAX, inclusive="both")
    descartados_aluguel_fora_range = int((~mask_range_ok).sum())
    df_limpo = df2.loc[mask_range_ok].copy()

    # --- flag_sem_coord ---
    df_limpo["flag_sem_coord"] = pd.isna(df_limpo["LATITUDE"]) | pd.isna(
        df_limpo["LONGITUDE"]
    )
    df_limpo = df_limpo.reset_index(drop=True)

    sem_coord = int(df_limpo["flag_sem_coord"].sum())
    total_limpo = len(df_limpo)

    resumo: dict[str, int] = {
        "total_entrada": total_entrada,
        "descartados_area": descartados_area,
        "descartados_placeholder": descartados_placeholder,
        "descartados_aluguel_fora_range": descartados_aluguel_fora_range,
        "total_limpo": total_limpo,
        "sem_coord": sem_coord,
    }

    return df_limpo, resumo


# ---------------------------------------------------------------------------
# Função 3 — materialização
# ---------------------------------------------------------------------------


def materializar(
    df_limpo: pd.DataFrame,
    resumo: dict[str, int],
    staging_dir: Path | str,
    analysis_dir: Path | str,
) -> tuple[Path, Path]:
    """Grava parquet + relatório de qualidade e retorna os dois paths.

    Cria os diretórios se não existirem. Parquet sem índice (index=False).
    Relatório em UTF-8 (não utf-8-sig — é arquivo interno, não CSV de usuário).
    """
    staging_dir = Path(staging_dir)
    analysis_dir = Path(analysis_dir)
    staging_dir.mkdir(parents=True, exist_ok=True)
    analysis_dir.mkdir(parents=True, exist_ok=True)

    path_parquet = staging_dir / "imoveis_candidatos_limpos.parquet"
    df_limpo.to_parquet(path_parquet, index=False)

    # Cálculo de % sem coordenada (proteger divisão por zero)
    total_limpo = resumo["total_limpo"]
    pct_sem_coord = (
        100.0 * resumo["sem_coord"] / total_limpo if total_limpo > 0 else 0.0
    )

    relatorio = f"""# Relatório de Qualidade — Imóveis Candidatos

Gerado em: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Resumo por regra de limpeza

| Regra | Descartados |
|---|---|
| Área < 500 m² | {resumo["descartados_area"]} |
| Aluguel placeholder (11.111,11) | {resumo["descartados_placeholder"]} |
| Aluguel fora de [10.000, 500.000] | {resumo["descartados_aluguel_fora_range"]} |

## Totais

| Métrica | Valor |
|---|---|
| Total de entrada | {resumo["total_entrada"]} |
| Total limpo (sobreviventes) | {resumo["total_limpo"]} |
| Sem coordenada (flag_sem_coord=True) | {resumo["sem_coord"]} |
| % sem coordenada | {pct_sem_coord:.1f}% |

## Observação

Registros sem coordenada recebem `flag_sem_coord=True` e são MANTIDOS no parquet
limpo. O geocoding é passo humano separado (BLK-VIAB-03). Nenhum dado de
coordenada de pessoa física é processado — os imóveis são endereços comerciais.
"""

    path_relatorio = analysis_dir / "imoveis_qualidade.md"
    path_relatorio.write_text(relatorio, encoding="utf-8")

    return path_parquet, path_relatorio


# ---------------------------------------------------------------------------
# Função 4 — ponto de entrada (CLI / orquestrador)
# ---------------------------------------------------------------------------


def run(
    xlsx_path: Path | str,
    staging_dir: Path | str = Path("data/staging"),
    analysis_dir: Path | str = Path("data/analysis"),
) -> tuple[Path, Path]:
    """Orquestra leitura → limpeza → materialização.

    Ponto de entrada para uso via CLI ou script externo.

    Returns:
        (path_parquet, path_relatorio)
    """
    df_bruto = ler_imoveis_xlsx(xlsx_path)
    df_limpo, resumo = validar_e_limpar(df_bruto)
    return materializar(df_limpo, resumo, staging_dir, analysis_dir)


# ---------------------------------------------------------------------------
# Ponto de entrada CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    xlsx = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else Path("data/ultra/Imoveis_16-06-2026_150117.xlsx")
    )
    parquet_path, relatorio_path = run(xlsx)
    print(f"Parquet: {parquet_path}")
    print(f"Relatório: {relatorio_path}")
