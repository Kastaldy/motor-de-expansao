"""
Bloco 2 - Normalizacao das unidades Ultra.

Transforma Ultra.csv (1 linha de metadado + cabecalho + dados) em base
georreferenciada para uso como restricao de canibalizacao.
Saida: data/staging/unidades_ultra_mapeadas.parquet

Nao altera nenhum artefato oficial do M1.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

ULTRA_CSV = ROOT / "data" / "ultra" / "Ultra.csv"
OUT_PATH = ROOT / "data" / "staging" / "unidades_ultra_mapeadas.parquet"

LAT_MIN, LAT_MAX = -34.0, 6.0
LNG_MIN, LNG_MAX = -75.0, -28.0


def _sha1_id(unidade: str, lat: float, lng: float) -> str:
    raw = f"ultra|{unidade}|{lat:.6f}|{lng:.6f}"
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


def carregar_ultra(path: Path) -> pd.DataFrame:
    # Linha 0 e metadado; cabecalho real esta na linha 1 (skiprows=1)
    df = pd.read_csv(path, sep=";", skiprows=1, dtype=str, encoding="latin-1")
    df.columns = [c.strip().strip('"') for c in df.columns]
    df.columns = [c.lower() for c in df.columns]
    # Renomear para nomes canonicos
    df = df.rename(columns={
        "unidade": "unidade",
        "estado": "uf",
        "cidade": "cidade",
        "latitude": "lat_raw",
        "longitude": "lng_raw",
    })
    df["unidade"] = df["unidade"].str.strip().str.strip('"')
    df["uf"] = df["uf"].str.strip().str.strip('"')
    df["cidade"] = df["cidade"].str.strip().str.strip('"')
    # Corrigir UF corrompida: extrair sigla do nome da unidade ("Nome / UF")
    mask_uf_invalida = ~df["uf"].str.match(r"^[A-Z]{2}$", na=False)
    if mask_uf_invalida.any():
        uf_from_nome = df.loc[mask_uf_invalida, "unidade"].str.extract(r"/\s*([A-Z]{2})\s*$")[0]
        df.loc[mask_uf_invalida, "uf"] = uf_from_nome.fillna("DESCONHECIDO")
    # Converter virgula decimal para ponto
    df["lat"] = pd.to_numeric(
        df["lat_raw"].str.replace(",", ".", regex=False), errors="coerce"
    )
    df["lng"] = pd.to_numeric(
        df["lng_raw"].str.replace(",", ".", regex=False), errors="coerce"
    )
    return df


def normalizar(df: pd.DataFrame) -> pd.DataFrame:
    df["flag_coord_valida"] = df.apply(
        lambda r: _coord_valida(r["lat"], r["lng"]), axis=1
    )

    try:
        import h3

        def _hex(row):
            if row["flag_coord_valida"]:
                return h3.latlng_to_cell(float(row["lat"]), float(row["lng"]), 7)
            return None

        df["hex_id_res7"] = df.apply(_hex, axis=1)
    except ImportError:
        df["hex_id_res7"] = None

    def _id(row):
        if row["flag_coord_valida"]:
            return _sha1_id(row["unidade"], float(row["lat"]), float(row["lng"]))
        return None

    df["ultra_id"] = df.apply(_id, axis=1)

    cols = ["ultra_id", "unidade", "uf", "cidade", "lat", "lng",
            "flag_coord_valida", "hex_id_res7"]
    return df[cols]


def validar(df: pd.DataFrame) -> None:
    print("\n=== Validacao: unidades_ultra_mapeadas ===")
    print(f"Total de linhas: {len(df)}")
    validas = df["flag_coord_valida"].sum()
    invalidas = (~df["flag_coord_valida"]).sum()
    print(f"Coordenadas validas: {validas}")
    print(f"Coordenadas invalidas (descartadas): {invalidas}")
    if invalidas > 0:
        print(df[~df["flag_coord_valida"]][["unidade", "uf", "lat", "lng"]])
    print(f"\nColunas: {list(df.columns)}")
    required = {"ultra_id", "unidade", "uf", "cidade", "lat", "lng",
                "flag_coord_valida", "hex_id_res7"}
    assert set(df.columns) >= required, f"Schema incompleto: faltam {required - set(df.columns)}"
    print("\nSchema OK")
    print(f"\nPor UF:")
    print(df[df["flag_coord_valida"]].groupby("uf").size().sort_values(ascending=False).to_string())


def main():
    if not ULTRA_CSV.exists():
        print(f"ERRO: arquivo nao encontrado: {ULTRA_CSV}")
        sys.exit(1)

    df_raw = carregar_ultra(ULTRA_CSV)
    print(f"Lido Ultra.csv: {len(df_raw)} linhas apos ignorar metadado")

    df_final = normalizar(df_raw)
    validar(df_final)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df_final.to_parquet(OUT_PATH, index=False)
    print(f"\nSalvo: {OUT_PATH}")


if __name__ == "__main__":
    main()
