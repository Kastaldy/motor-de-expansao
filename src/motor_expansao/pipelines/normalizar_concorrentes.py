"""
Bloco 1 - Normalização dos concorrentes mapeados.

Consolida Smart Fit, Bluefit e Panobianco em um snapshot auditavel.
Saida: data/staging/concorrentes_mapeados.parquet

Nao altera nenhum artefato oficial do M1.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]

CONCORRENTES_DIR = ROOT / "concorrentes"
OUT_PATH = ROOT / "data" / "staging" / "concorrentes_mapeados.parquet"

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


def _detectar_sep(arquivo: Path) -> str:
    amostra = arquivo.read_text(encoding="utf-8", errors="replace")[:500]
    return ";" if amostra.count(";") >= amostra.count(",") else ","


def carregar_csv(arquivo: Path, rede: str) -> pd.DataFrame:
    sep = _detectar_sep(arquivo)
    df = pd.read_csv(arquivo, sep=sep, dtype=str)
    df.columns = [c.strip().lower() for c in df.columns]
    df["nome_unidade"] = df["nome_unidade"].str.strip()
    df["lat"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["lng"] = pd.to_numeric(df["longitude"], errors="coerce")
    df["rede"] = rede
    df["arquivo_origem"] = arquivo.name
    df = df.drop(columns=["latitude", "longitude"], errors="ignore")
    return df


# Origem da coordenada de cada linha (coluna de auditoria `coord_origem`).
COORD_DA_COLETA = "coleta"
COORD_DA_SEMANA_ANTERIOR = "semana_anterior"
COORD_AUSENTE = "sem_coordenada"


def _chave_unidade(rede: pd.Series, nome: pd.Series) -> pd.Series:
    """Chave `rede|nome` tolerante a caixa e espaco (o coletor alterna `POWER FIT X` / `Power Fit X`)."""
    nome_norm = nome.fillna("").astype(str).str.strip().str.casefold().str.replace(r"\s+", " ", regex=True)
    return rede.astype(str) + "|" + nome_norm


def herdar_coordenadas_da_semana_anterior(
    df: pd.DataFrame, anterior: pd.DataFrame | None
) -> pd.DataFrame:
    """Academia que veio SEM coordenada nesta coleta herda a da semana anterior.

    A busca de localizacao do coletor falha de forma intermitente: em 2026-11-01, 10 academias
    que continuavam no site da rede (26fit Capao da Canoa, Live Franceses, Cristal Guarulhos...)
    vieram com latitude/longitude vazias, sairam do mapa e derrubaram a contagem de pins
    desenhaveis -- o regen reprovou e o mercado da semana nao foi publicado.

    A academia so' herda se continua LISTADA nesta coleta (fechou -> sai do CSV e nao volta) e
    se a chave `rede|nome` aponta para UMA coordenada valida na semana anterior e UMA linha
    nesta. Chave ambigua nao herda: escolher uma das coordenadas seria inventar endereco.
    Coordenada que veio na coleta nunca e' sobrescrita (a academia pode ter mudado de lugar).

    `anterior` e' o `concorrentes_mapeados.parquet` publicado; sem ele nada muda. Funcao pura.
    """
    out = df.copy()
    valida = out.apply(lambda r: _coord_valida(r["lat"], r["lng"]), axis=1).astype(bool)
    out["coord_origem"] = COORD_DA_COLETA
    out.loc[~valida, "coord_origem"] = COORD_AUSENTE
    if anterior is None or anterior.empty or valida.all():
        return out
    if not {"rede", "nome_unidade", "lat", "lng"} <= set(anterior.columns):
        return out

    ant = anterior[["rede", "nome_unidade", "lat", "lng"]].copy()
    ant = ant[ant.apply(lambda r: _coord_valida(r["lat"], r["lng"]), axis=1).astype(bool)]
    ant["_chave"] = _chave_unidade(ant["rede"], ant["nome_unidade"])
    ant = ant.drop_duplicates(subset=["_chave", "lat", "lng"])
    ant = ant[~ant["_chave"].duplicated(keep=False)].set_index("_chave")

    chave = _chave_unidade(out["rede"], out["nome_unidade"])
    unica_agora = ~chave.duplicated(keep=False)
    herda = ~valida & unica_agora & chave.isin(ant.index)
    if herda.any():
        out.loc[herda, "lat"] = chave[herda].map(ant["lat"]).to_numpy(dtype="float64")
        out.loc[herda, "lng"] = chave[herda].map(ant["lng"]).to_numpy(dtype="float64")
        out.loc[herda, "coord_origem"] = COORD_DA_SEMANA_ANTERIOR
    return out


def normalizar(dfs: list[pd.DataFrame], anterior: pd.DataFrame | None = None) -> pd.DataFrame:
    df = pd.concat(dfs, ignore_index=True)
    df = herdar_coordenadas_da_semana_anterior(df, anterior)

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
        "status_registro", "hex_id_res7", "coord_origem",
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
    if "coord_origem" in df.columns:
        herdadas = df["coord_origem"] == COORD_DA_SEMANA_ANTERIOR
        print(f"Coordenada herdada da semana anterior: {int(herdadas.sum())}")
        for _, r in df.loc[herdadas, ["rede", "nome_unidade"]].iterrows():
            print(f"  herdada: {r['rede']} | {r['nome_unidade']}")
    print(f"\nColunas: {list(df.columns)}")
    assert set(df.columns) >= {
        "concorrente_id", "rede", "nome_unidade", "lat", "lng",
        "data_coleta", "arquivo_origem", "flag_coord_valida",
        "flag_duplicado_rede_coord", "status_registro", "hex_id_res7",
    }, "Schema incompleto"
    print("\nSchema OK")


def descobrir_csvs(concorrentes_dir: Path) -> dict[str, str]:
    """Descobre todos os unidades_*.csv e deriva o nome da rede pelo nome do arquivo."""
    return {
        p.name: p.stem.removeprefix("unidades_")
        for p in sorted(concorrentes_dir.glob("unidades_*.csv"))
    }


def main():
    rede_map = descobrir_csvs(CONCORRENTES_DIR)
    print(f"CSVs encontrados: {len(rede_map)}")

    dfs = []
    for fname, rede in rede_map.items():
        path = CONCORRENTES_DIR / fname
        df = carregar_csv(path, rede)
        dfs.append(df)
        print(f"  {rede:<30} {len(df):>5} unidades")

    if not dfs:
        print("Nenhum arquivo encontrado. Abortando.")
        sys.exit(1)

    # O parquet que esta' em OUT_PATH e' o da rodada anterior (no regen da DEC-059, a copia
    # REAL do publicado): e' dele que sai a coordenada de quem veio sem nesta coleta.
    anterior = None
    if OUT_PATH.exists():
        try:
            anterior = pd.read_parquet(OUT_PATH, columns=["rede", "nome_unidade", "lat", "lng"])
        except Exception as exc:  # noqa: BLE001 - sem a semana anterior, segue sem herdar
            print(f"AVISO: semana anterior ilegivel ({type(exc).__name__}: {exc}); nenhuma coordenada herdada")
    else:
        print("AVISO: sem semana anterior em OUT_PATH; nenhuma coordenada herdada")

    df_final = normalizar(dfs, anterior=anterior)
    validar(df_final)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df_final.to_parquet(OUT_PATH, index=False)
    print(f"\nSalvo: {OUT_PATH}")


if __name__ == "__main__":
    main()
