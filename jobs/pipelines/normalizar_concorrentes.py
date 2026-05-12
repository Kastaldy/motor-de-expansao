"""
Bloco 1 - Normalização dos concorrentes mapeados.

Consolida Smart Fit, Bluefit e Panobianco em um snapshot auditavel.
Saida: data/staging/concorrentes_mapeados.parquet

Nao altera nenhum artefato oficial do M1.
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

CONCORRENTES_DIR = ROOT / "concorrentes"
OUT_PATH = ROOT / "data" / "staging" / "concorrentes_mapeados.parquet"

REDE_MAP = {
    "unidades_smart_fit.csv": "smart_fit",
    "unidades_bluefit.csv": "bluefit",
    "unidades_panobianco.csv": "panobianco",
}

# Envelope geografico do Brasil
LAT_MIN, LAT_MAX = -34.0, 6.0
LNG_MIN, LNG_MAX = -75.0, -28.0


def _sha1_id(rede: str, nome: str, lat: float, lng: float) -> str:
    raw = f"{rede}|{nome}|{lat:.6f}|{lng:.6f}"
    return hashlib.sha1(raw.encode()).hexdigest()


def _coord_valida(lat, lng) -> bool:
    try:
        return (
            pd.notna(lat)
            and pd.notna(lng)
            and LAT_MIN <= float(lat) <= LAT_MAX
            and LNG_MIN <= float(lng) <= LNG_MAX
        )
    except (TypeError, ValueError):
        return False


def carregar_csv(arquivo: Path, rede: str) -> pd.DataFrame:
    df = pd.read_csv(arquivo, sep=";", dtype=str)
    df.columns = [c.strip().lower() for c in df.columns]
    df["nome_unidade"] = df["nome_unidade"].str.strip()
    df["lat"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["lng"] = pd.to_numeric(df["longitude"], errors="coerce")
    df["rede"] = rede
    df["arquivo_origem"] = arquivo.name
    df = df.drop(columns=["latitude", "longitude"], errors="ignore")
    return df


def normalizar(dfs: list[pd.DataFrame]) -> pd.DataFrame:
    df = pd.concat(dfs, ignore_index=True)

    df["flag_coord_valida"] = df.apply(
        lambda r: _coord_valida(r["lat"], r["lng"]), axis=1
    )

    # Marca duplicatas por rede + coord (mantém primeira ocorrência)
    df["flag_duplicado_rede_coord"] = df.duplicated(
        subset=["rede", "lat", "lng"], keep="first"
    )

    def _status(row):
        if not row["flag_coord_valida"]:
            return "descartado_coord"
        if row["flag_duplicado_rede_coord"]:
            return "descartado_duplicado"
        return "valido"

    df["status_registro"] = df.apply(_status, axis=1)

    # hex_id_res7 apenas para registros validos
    try:
        import h3

        def _hex(row):
            if row["status_registro"] == "valido":
                return h3.latlng_to_cell(float(row["lat"]), float(row["lng"]), 7)
            return None

        df["hex_id_res7"] = df.apply(_hex, axis=1)
    except ImportError:
        df["hex_id_res7"] = None

    # concorrente_id apenas para registros validos
    def _id(row):
        if row["status_registro"] == "valido":
            return _sha1_id(row["rede"], row["nome_unidade"], float(row["lat"]), float(row["lng"]))
        return None

    df["concorrente_id"] = df.apply(_id, axis=1)

    # Ordem de colunas conforme contrato tecnico
    cols = [
        "concorrente_id", "rede", "nome_unidade", "lat", "lng",
        "data_coleta", "arquivo_origem",
        "flag_coord_valida", "flag_duplicado_rede_coord",
        "status_registro", "hex_id_res7",
    ]
    return df[cols]


def validar(df: pd.DataFrame) -> None:
    print("\n=== Validacao: concorrentes_mapeados ===")
    print(f"Total de linhas: {len(df)}")
    print("\nContagem por rede:")
    print(df.groupby("rede")["status_registro"].value_counts().to_string())
    print(f"\nDescartados coord invalida: {(df['status_registro'] == 'descartado_coord').sum()}")
    print(f"Descartados duplicado: {(df['status_registro'] == 'descartado_duplicado').sum()}")
    print(f"Registros validos: {(df['status_registro'] == 'valido').sum()}")
    print(f"\nColunas: {list(df.columns)}")
    assert set(df.columns) >= {
        "concorrente_id", "rede", "nome_unidade", "lat", "lng",
        "data_coleta", "arquivo_origem", "flag_coord_valida",
        "flag_duplicado_rede_coord", "status_registro", "hex_id_res7",
    }, "Schema incompleto"
    print("\nSchema OK")


def main():
    dfs = []
    for fname, rede in REDE_MAP.items():
        path = CONCORRENTES_DIR / fname
        if not path.exists():
            print(f"AVISO: arquivo nao encontrado: {path}")
            continue
        df = carregar_csv(path, rede)
        dfs.append(df)
        print(f"Lido {fname}: {len(df)} linhas")

    if not dfs:
        print("Nenhum arquivo encontrado. Abortando.")
        sys.exit(1)

    df_final = normalizar(dfs)
    validar(df_final)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df_final.to_parquet(OUT_PATH, index=False)
    print(f"\nSalvo: {OUT_PATH}")


if __name__ == "__main__":
    main()
