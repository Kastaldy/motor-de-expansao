"""Ingestão e agregação H3 (res-7) da camada de Demanda Revelada — SEM PII.

Pipeline: parser do dump (vars JS `CELLS`/`GYMS_PTS`/`SF`/`BANDS`, já agregadas)
→ agregação H3 res-7 → drop-PII na fronteira → parquet (`demanda_revelada_h3.parquet`).

Anti-PII por construção (BLK-TP-01 / DEC-012):
- só desserializa as 4 estruturas JÁ agregadas; qualquer outra `var` do HTML é ignorada;
- identificadores/coordenadas individuais nunca são lidos para o staging nem persistidos;
- a agregação para H3 ocorre na ENTRADA; o artefato não contém nenhuma coluna de
  `COLUNAS_PII_PROIBIDAS` (validado por teste e por `_assert_sem_pii`).

READ-ONLY sobre o M1: nunca importa de `pipelines/m1/`, `censo_*` nem `dashboard/`;
não escreve em nenhum artefato oficial (só `demanda_revelada_h3.parquet`).
A demanda é insumo OBSERVADO (DEC-009), NUNCA preditor geográfico de magnitude.

API h3 = v4 (`latlng_to_cell`/`get_resolution`/`is_valid_cell`).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import h3
import pandas as pd

from .contrato import (
    COLUNAS_PII_PROIBIDAS,
    CONTRATO_COLUNAS,
    H3_RES_CONTRATO,
    VERSAO_CONTRATO,
)

# Caminho default do dump externo (gitignored, em NAO_ABRA/). Parametrizável: o
# parser NUNCA depende desse arquivo nos testes (a fixture sintética é o contrato).
FONTE_DEFAULT = Path("NAO_ABRA/totalpass_final (72) (1).html")
DESTINO_DEFAULT = Path("data/staging/demanda_revelada_h3.parquet")

# Banda de distância ">5km" do concorrente low-cost (índice 5 em BANDS).
_BANDA_GT5KM = 5


def _grab(txt: str, name: str) -> list | dict:
    """Extrai a estrutura JSON da var JS ``var NAME = [...]``/``{...}``.

    Varredura de chaves/colchetes balanceada com escape de strings (reuso da lógica
    do protótipo). Levanta ``ValueError`` se a var não existir ou estiver malformada.
    """
    m = re.search(r"var\s+" + re.escape(name) + r"\s*=\s*", txt)
    if m is None:
        raise ValueError(f"variável '{name}' não encontrada na fonte")
    i = m.end()
    op = txt[i]
    if op not in "[{":
        raise ValueError(f"variável '{name}' não inicia em '['/'{{' (achou '{op}')")
    cl = {"[": "]", "{": "}"}[op]
    depth = 0
    ins = False
    esc = False
    start = i
    while i < len(txt):
        c = txt[i]
        if ins:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                ins = False
        else:
            if c == '"':
                ins = True
            elif c == op:
                depth += 1
            elif c == cl:
                depth -= 1
                if depth == 0:
                    return json.loads(txt[start : i + 1])
        i += 1
    raise ValueError(f"bloco da variável '{name}' não foi fechado")


def _parse_fonte_html(fonte: Path) -> tuple[list, list, list, list]:
    """Lê o dump e desserializa SOMENTE `CELLS`, `GYMS_PTS`, `SF`, `BANDS`.

    Drop-PII na fronteira: nenhuma outra `var` do HTML é lida. Cada `CELLS[i]` é
    uma célula AGREGADA (não-individual) por construção da fonte.
    """
    txt = Path(fonte).read_text(encoding="utf-8")
    cells = _grab(txt, "CELLS")
    gyms = _grab(txt, "GYMS_PTS")
    sf = _grab(txt, "SF")
    bands = _grab(txt, "BANDS")
    return cells, gyms, sf, bands  # type: ignore[return-value]


def _to_cell(lat: object, lng: object) -> str | None:
    """Converte (lat,lng) → hex res-7 (h3 v4); None se inválido."""
    try:
        return h3.latlng_to_cell(float(lat), float(lng), H3_RES_CONTRATO)  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return None


def _agregar_h3(cells: list, gyms: list, sf: list) -> pd.DataFrame:
    """Agrega as células/academias/unidades em hexes res-7 (contrato de 9 colunas).

    Espelha a lógica do protótipo com os nomes GENÉRICOS do contrato.
    """
    cells_df = pd.DataFrame(
        cells, columns=["lat", "lng", "membros", "faixa_idx", "dist_sf_m", "sf_nome"]
    )
    cells_df["membros"] = pd.to_numeric(cells_df["membros"], errors="coerce").fillna(0)
    cells_df["dist_sf_m"] = pd.to_numeric(cells_df["dist_sf_m"], errors="coerce")
    cells_df["faixa_idx"] = pd.to_numeric(cells_df["faixa_idx"], errors="coerce").fillna(-1)
    cells_df["gt5km"] = cells_df["faixa_idx"] >= _BANDA_GT5KM
    cells_df["hex_id"] = [_to_cell(a, o) for a, o in zip(cells_df["lat"], cells_df["lng"], strict=False)]
    cells_df = cells_df.dropna(subset=["hex_id"])

    g = cells_df.groupby("hex_id")
    dem = pd.DataFrame(
        {
            "membros": g["membros"].sum(),
            "membros_gt5km_concorrente_lc": g.apply(
                lambda x: x.loc[x["gt5km"], "membros"].sum(), include_groups=False
            ),
            "dist_concorrente_lc_min_m": g["dist_sf_m"].min(),
            "n_celulas_agregadas": g.size(),
        }
    ).reset_index()

    # Academias parceiras (excluir as próprias unidades do concorrente, p=='sf').
    gyms_df = pd.DataFrame(gyms)
    if not gyms_df.empty:
        gyms_df["q"] = pd.to_numeric(gyms_df.get("q", 0), errors="coerce").fillna(0)
        parceiras = gyms_df[gyms_df.get("p", "") != "sf"].copy()
    else:
        parceiras = pd.DataFrame(columns=["lat", "lng", "p", "q"])
    if not parceiras.empty:
        parceiras["hex_id"] = [_to_cell(a, o) for a, o in zip(parceiras["lat"], parceiras["lng"], strict=False)]
        parceiras = parceiras.dropna(subset=["hex_id"])
        gp = parceiras.groupby("hex_id")
        acad = pd.DataFrame(
            {"n_acad_parceiras": gp.size(), "alunos_parceiras": gp["q"].sum()}
        ).reset_index()
    else:
        acad = pd.DataFrame(columns=["hex_id", "n_acad_parceiras", "alunos_parceiras"])

    # Unidades do concorrente low-cost de referência (SF).
    sf_df = pd.DataFrame(sf)
    if not sf_df.empty:
        sf_df = sf_df.rename(columns={"a": "lat", "o": "lng"})
        sf_df["hex_id"] = [_to_cell(a, o) for a, o in zip(sf_df["lat"], sf_df["lng"], strict=False)]
        sf_df = sf_df.dropna(subset=["hex_id"])
        conc = sf_df.groupby("hex_id").size().rename("n_concorrente_lc").reset_index()
    else:
        conc = pd.DataFrame(columns=["hex_id", "n_concorrente_lc"])

    out = dem.merge(acad, on="hex_id", how="left").merge(conc, on="hex_id", how="left")

    # Coerção aos dtypes do contrato (int64 sem NaN; float64 na distância).
    out["membros_gt5km_concorrente_lc"] = out["membros_gt5km_concorrente_lc"].fillna(0)
    for col in ("n_acad_parceiras", "alunos_parceiras", "n_concorrente_lc"):
        out[col] = out[col].fillna(0)
    for col, dtype in CONTRATO_COLUNAS.items():
        if col in ("hex_id", "versao_contrato"):
            continue
        if dtype == "int64":
            out[col] = out[col].round().astype("int64")
        elif dtype == "float64":
            out[col] = out[col].astype("float64")

    out["hex_id"] = out["hex_id"].astype("string")
    out["versao_contrato"] = VERSAO_CONTRATO
    out["versao_contrato"] = out["versao_contrato"].astype("string")

    # Ordem canônica de colunas + ordenação por hex_id (determinismo/reprodutibilidade).
    out = out[list(CONTRATO_COLUNAS.keys())]
    out = out.sort_values("hex_id").reset_index(drop=True)
    return out


def _assert_sem_pii(df: pd.DataFrame) -> None:
    """Falha se o frame tiver coluna fora do contrato ou alguma coluna PII."""
    extras = set(df.columns) - set(CONTRATO_COLUNAS)
    if extras:
        raise ValueError(f"colunas fora do contrato no parquet de saída: {sorted(extras)}")
    pii = set(df.columns) & COLUNAS_PII_PROIBIDAS
    if pii:
        raise ValueError(f"colunas PII proibidas no parquet de saída: {sorted(pii)}")


def _assert_res7(df: pd.DataFrame) -> None:
    """Falha se algum hex_id não for H3 res-7 válido."""
    invalidos: list[str] = []
    for hid in df["hex_id"]:
        h = str(hid)
        if not h3.is_valid_cell(h) or h3.get_resolution(h) != H3_RES_CONTRATO:
            invalidos.append(h)
            if len(invalidos) >= 5:
                break
    if invalidos:
        raise ValueError(f"hex_id fora de res-{H3_RES_CONTRATO}: amostra {invalidos}")


def ingerir_demanda_revelada(
    fonte: Path = FONTE_DEFAULT,
    destino: Path = DESTINO_DEFAULT,
    *,
    escrever: bool = True,
) -> pd.DataFrame:
    """Ingere o dump → agrega H3 res-7 → valida anti-PII/res-7 → grava parquet.

    Parametrizável por ``fonte`` (testes usam fixture sintética, nunca o dump real).
    Retorna o DataFrame agregado (ordenado por ``hex_id``). READ-ONLY sobre o M1.
    """
    cells, gyms, sf, _bands = _parse_fonte_html(Path(fonte))
    df = _agregar_h3(cells, gyms, sf)
    _assert_sem_pii(df)
    _assert_res7(df)
    if escrever:
        destino = Path(destino)
        destino.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(destino, index=False)
    return df


__all__ = ["ingerir_demanda_revelada", "FONTE_DEFAULT", "DESTINO_DEFAULT"]
