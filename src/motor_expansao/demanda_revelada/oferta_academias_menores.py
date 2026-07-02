"""Ingestão anti-PII da OFERTA de academias menores (WellHub/TotalPass) — H3 res-7.

Pipeline: lê `NAO_ABRA/03_Competidores.xlsx` (24.045 academias menores agregadoras)
→ deriva `hex_id` res-7 de `Latitude`/`Longitude` na FRONTEIRA e IMEDIATAMENTE dropa
`Latitude`/`Longitude`/`Nome_Academia`/`Cluster_ID` → agrega por `hex_id`
→ valida anti-PII + res-7 → grava `data/staging/oferta_academias_menores_h3.parquet`.

Anti-PII por construção (BLK-TP-08 / DEC-012):
- `Latitude`/`Longitude`/`Nome_Academia`/`Cluster_ID` são dropadas logo após derivar
  `hex_id`; nunca são persistidas nem logadas;
- `Total_Alunos_Cluster` NUNCA é somado nem vira coluna (soma por cluster → dupla
  contagem); entra na lista de proibidas (`_COLUNAS_PII_LOCAIS`) como blindagem;
- o artefato não contém nenhuma coluna de `_COLUNAS_PII_LOCAIS` (validado por
  `_assert_sem_pii` e pelo teste `test_zero_pii`);
- a fonte real (`NAO_ABRA/`) nunca é versionada; testes usam fixture sintética.

DEC-013 (parte 3): agregadores coletados/armazenados como oferta com DEDUP medido no
relatório ANTES de qualquer integração ao residual. Este módulo só INGERE + gera
relatório de qualidade/DEDUP; NÃO recompõe `score_oportunidade_residual`/
`oferta_efetiva_disponivel` nem regenera parquets de mercado (follow-up sob gate).

READ-ONLY sobre o M1: pacote DISJUNTO — nunca importa de `pipelines/m1/`, `censo_*`,
`dashboard/` nem `api`; não escreve em nenhum artefato oficial do M1. A oferta é
insumo OBSERVADO (DEC-009), NUNCA preditor geográfico de magnitude.

API h3 = v4 (`latlng_to_cell`/`get_resolution`/`is_valid_cell`).
"""

from __future__ import annotations

from pathlib import Path

import h3
import pandas as pd

from .contrato import COLUNAS_PII_PROIBIDAS, H3_RES_CONTRATO

# Carimbo de reprodutibilidade do contrato (gravado em todas as linhas do parquet).
VERSAO_CONTRATO_OFERTA_MENORES = "oferta_menores_v1"

# Caminhos default (fonte gitignored em NAO_ABRA/; parquet gitignored em staging).
FONTE_DEFAULT = Path("NAO_ABRA/03_Competidores.xlsx")
DESTINO_DEFAULT = Path("data/staging/oferta_academias_menores_h3.parquet")
CONCORRENTES_DEFAULT = Path("data/staging/concorrentes_mapeados.parquet")
UNIVERSO_DEFAULT = Path("data/outputs/hexagonos_brasil_dashboard.parquet")
RELATORIO_DEFAULT = Path("data/reports/scratch/oferta_academias_menores_qualidade.md")

# Colunas de entrada da planilha (PII na origem) descartadas na fronteira.
_COLUNAS_DROP_FRONTEIRA = ("Latitude", "Longitude", "Nome_Academia", "Cluster_ID")

# Categorias de `Plano` conhecidas (11); vira `n_plano_<plano>` no contrato.
_PLANOS_CANONICOS = (
    "tp0",
    "tp1",
    "tp1_plus",
    "tp2",
    "tp2_plus",
    "tp3",
    "tp4",
    "tp5",
    "tp5_plus",
    "tp6",
    "tp7",
)
_COLUNAS_PLANO = tuple(f"n_plano_{p}" for p in _PLANOS_CANONICOS)

# Ordem e dtypes canônicos do parquet de saída (contrato `oferta_menores_v1`).
CONTRATO_COLUNAS_OFERTA_MENORES: dict[str, str] = {
    "hex_id": "string",                    # H3 res-7 (chave de join com o Motor)
    "n_academias_menores": "int64",        # nº academias menores no hex
    "alunos_academias_menores": "int64",   # Σ `Alunos_Academia` (NUNCA Total_Alunos_Cluster)
    **{c: "int64" for c in _COLUNAS_PLANO},  # distribuição por `Plano` (D3)
    "versao_contrato": "string",           # carimbo de reprodutibilidade
}

# Colunas PROIBIDAS no artefato/relatório. Estende `COLUNAS_PII_PROIBIDAS` do contrato
# base com as PII locais da planilha (nomes normalizados p/ minúsculas) e o
# `total_alunos_cluster` (blindagem contra dupla-contagem por cluster).
_COLUNAS_PII_LOCAIS: frozenset[str] = COLUNAS_PII_PROIBIDAS | frozenset(
    {
        "latitude",
        "longitude",
        "nome_academia",
        "cluster_id",
        "total_alunos_cluster",
    }
)


def _to_cell(lat: object, lng: object) -> str | None:
    """Converte (lat,lng) → hex res-7 (h3 v4); None se inválido."""
    try:
        return h3.latlng_to_cell(float(lat), float(lng), H3_RES_CONTRATO)  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return None


def _ler_e_derivar_hex(fonte: Path) -> pd.DataFrame:
    """Lê o xlsx, deriva `hex_id` na FRONTEIRA e dropa PII imediatamente.

    Retorna frame SEM PII com colunas `hex_id`, `Plano`, `Alunos_Academia`. Nunca
    persiste/loga `Latitude`/`Longitude`/`Nome_Academia`/`Cluster_ID`.
    """
    df = pd.read_excel(Path(fonte), sheet_name=0)

    # Deriva o hex ANTES de qualquer outra operação, direto das coords brutas.
    hex_ids = [
        _to_cell(lat, lng)
        for lat, lng in zip(df.get("Latitude"), df.get("Longitude"), strict=False)
    ]

    # DROP-PII na fronteira: descarta coords/nome/cluster imediatamente.
    df = df.drop(columns=[c for c in _COLUNAS_DROP_FRONTEIRA if c in df.columns])
    df["hex_id"] = hex_ids
    df = df.dropna(subset=["hex_id"])

    # Normaliza `Plano`; só as colunas não-PII seguem adiante.
    plano = df.get("Plano", pd.Series(dtype="object")).astype("string").str.strip()
    alunos = pd.to_numeric(df.get("Alunos_Academia"), errors="coerce").fillna(0)
    return pd.DataFrame(
        {"hex_id": df["hex_id"].to_numpy(), "Plano": plano.to_numpy(), "Alunos_Academia": alunos.to_numpy()}
    )


def _agregar_h3(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega por `hex_id` (res-7): contagem, Σ alunos e distribuição por `Plano`.

    `Total_Alunos_Cluster` NUNCA é somado (não está no frame). Só `Alunos_Academia`.
    """
    g = df.groupby("hex_id")
    out = pd.DataFrame(
        {
            "n_academias_menores": g.size(),
            "alunos_academias_menores": g["Alunos_Academia"].sum(),
        }
    ).reset_index()

    # Distribuição por `Plano` (D3): pivô de contagens, uma coluna por plano canônico.
    pivot = (
        df.assign(_um=1)
        .pivot_table(index="hex_id", columns="Plano", values="_um", aggfunc="sum", fill_value=0)
    )
    for plano, col in zip(_PLANOS_CANONICOS, _COLUNAS_PLANO, strict=True):
        out[col] = out["hex_id"].map(pivot.get(plano, pd.Series(dtype="int64"))).fillna(0)

    # Coerção de dtypes conforme o contrato (int64 sem NaN; hex_id/versao string).
    for col, dtype in CONTRATO_COLUNAS_OFERTA_MENORES.items():
        if col in ("hex_id", "versao_contrato"):
            continue
        if dtype == "int64":
            out[col] = out[col].round().astype("int64")

    out["hex_id"] = out["hex_id"].astype("string")
    out["versao_contrato"] = VERSAO_CONTRATO_OFERTA_MENORES
    out["versao_contrato"] = out["versao_contrato"].astype("string")

    # Ordem canônica de colunas + ordenação por hex_id (determinismo/reprodutibilidade).
    out = out[list(CONTRATO_COLUNAS_OFERTA_MENORES.keys())]
    out = out.sort_values("hex_id").reset_index(drop=True)
    return out


def _assert_sem_pii(df: pd.DataFrame) -> None:
    """Falha se o frame tiver coluna fora do contrato ou alguma coluna PII local."""
    extras = set(df.columns) - set(CONTRATO_COLUNAS_OFERTA_MENORES)
    if extras:
        raise ValueError(f"colunas fora do contrato no parquet de saída: {sorted(extras)}")
    pii = {c for c in df.columns if c.lower() in _COLUNAS_PII_LOCAIS}
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


def ingerir_oferta_academias_menores(
    fonte: Path = FONTE_DEFAULT,
    destino: Path = DESTINO_DEFAULT,
    *,
    escrever: bool = True,
) -> pd.DataFrame:
    """Ingere o xlsx → deriva hex + drop-PII → agrega res-7 → valida → grava parquet.

    Parametrizável por ``fonte`` (testes usam fixture sintética, nunca o dump real).
    Retorna o DataFrame agregado (ordenado por ``hex_id``). READ-ONLY sobre o M1.
    """
    df = _ler_e_derivar_hex(Path(fonte))
    agg = _agregar_h3(df)
    _assert_sem_pii(agg)
    _assert_res7(agg)
    if escrever:
        destino = Path(destino)
        destino.parent.mkdir(parents=True, exist_ok=True)
        agg.to_parquet(destino, index=False)
    return agg


def _ler_hexes_concorrentes(concorrentes_path: Path) -> set[str]:
    """Lê os hexes res-7 únicos de `concorrentes_mapeados.parquet` (chave `hex_id_res7`)."""
    if not Path(concorrentes_path).exists():
        return set()
    df = pd.read_parquet(concorrentes_path, columns=["hex_id_res7"])
    return set(df["hex_id_res7"].dropna().astype(str))


def _ler_hexes_universo(universo_path: Path) -> set[str]:
    """Lê os hexes do universo do Motor (`hexagonos_brasil_dashboard.parquet`, `hex_id`)."""
    if not Path(universo_path).exists():
        return set()
    df = pd.read_parquet(universo_path, columns=["hex_id"])
    return set(df["hex_id"].dropna().astype(str))


def gerar_relatorio_qualidade(
    df_oferta: pd.DataFrame,
    concorrentes_path: Path = CONCORRENTES_DEFAULT,
    universo_path: Path = UNIVERSO_DEFAULT,
    destino_md: Path = RELATORIO_DEFAULT,
    *,
    escrever: bool = True,
) -> str:
    """Gera o markdown de qualidade + DEDUP (só agregados, ZERO PII).

    DEDUP = medição de RELATÓRIO por `hex_id` (overlap) vs `concorrentes_mapeados`
    (D1); NÃO subtrai oferta nem flag no parquet. Nunca lê/grava `Nome_Academia`.
    """
    n_hexes = len(df_oferta)
    n_academias = int(df_oferta["n_academias_menores"].sum())
    n_alunos = int(df_oferta["alunos_academias_menores"].sum())

    hexes_oferta = set(df_oferta["hex_id"].astype(str))
    hexes_conc = _ler_hexes_concorrentes(concorrentes_path)
    hexes_univ = _ler_hexes_universo(universo_path)

    overlap = hexes_oferta & hexes_conc
    n_overlap = len(overlap)
    if hexes_conc:
        mask_overlap = df_oferta["hex_id"].astype(str).isin(overlap)
        acad_cobertas = int(df_oferta.loc[mask_overlap, "n_academias_menores"].sum())
        alunos_cobertos = int(df_oferta.loc[mask_overlap, "alunos_academias_menores"].sum())
        pct_acad = 100.0 * acad_cobertas / n_academias if n_academias else 0.0
        pct_alunos = 100.0 * alunos_cobertos / n_alunos if n_alunos else 0.0
    else:
        acad_cobertas = alunos_cobertos = 0
        pct_acad = pct_alunos = 0.0

    if hexes_univ:
        n_casados = len(hexes_oferta & hexes_univ)
        pct_casado = 100.0 * n_casados / n_hexes if n_hexes else 0.0
        universo_str = (
            f"- Hexes que casam com o universo do Motor "
            f"(`hexagonos_brasil_dashboard.parquet`): **{n_casados:,}** de {n_hexes:,} "
            f"(**{pct_casado:.1f}%**)."
        )
    else:
        universo_str = "- Universo do Motor **indisponível** em runtime → cobertura não medida."

    # Distribuição por `Plano` (só agregados).
    linhas_plano = "\n".join(
        f"  - `{plano}`: {int(df_oferta[col].sum()):,}"
        for plano, col in zip(_PLANOS_CANONICOS, _COLUNAS_PLANO, strict=True)
    )

    md = f"""# Oferta de academias menores (WellHub/TotalPass) — qualidade & DEDUP

> Camada PARALELA de OFERTA (BLK-TP-08 / DEC-012 / DEC-013 parte 3). Contrato
> `{VERSAO_CONTRATO_OFERTA_MENORES}`. Artefato: `data/staging/oferta_academias_menores_h3.parquet`
> (gitignored, NÃO oficial do M1). **READ-ONLY sobre o M1** — não recompõe
> `score_oportunidade_residual`/`oferta_efetiva_disponivel`. **ZERO PII** (só agregados).

## Cobertura
- Academias menores agregadas: **{n_academias:,}**.
- Alunos agregados (Σ `Alunos_Academia`): **{n_alunos:,}**.
- Hexes res-7 distintos: **{n_hexes:,}**.
{universo_str}

## DEDUP por `hex_id` vs `concorrentes_mapeados.parquet` (D1 — só RELATÓRIO)
> Medição de sobreposição de OFERTA por `hex_id` (overlap). **NÃO subtrai oferta**
> nem marca flag no parquet — a dupla-contagem é apenas QUANTIFICADA aqui (a
> subtração/integração fina é follow-up sob gate, BLK-TP-09 / DEC-013 parte 3).
- Hexes de concorrentes mapeados (únicos): **{len(hexes_conc):,}**.
- Hexes em SOBREPOSIÇÃO (academia menor + concorrente mapeado): **{n_overlap:,}**.
- Academias menores em hex já coberto: **{acad_cobertas:,}** (**{pct_acad:.1f}%** do total).
- Alunos em hex já coberto: **{alunos_cobertos:,}** (**{pct_alunos:.1f}%** do total).
- **Estratégia de DEDUP candidata (registrada, não aplicada):** dedup por `hex_id`
  (overlap) como cross-check primário; subtração de oferta e capacidade por tipo/Huff
  são epic futura (BLK-TP-09) sob gate próprio.

## Caveat de coordenadas (~1 km) — D2
- As coordenadas da fonte têm ~2 casas decimais (~1,1 km de precisão): academias
  distintas podem colapsar no mesmo hex res-7 e a borda do hex é incerta. O ruído é
  ACEITO e documentado (mesmo caveat do BLK-TP-01) — esta camada é **refino**, não
  verdade fina; sem arredondamento extra (a derivação res-7 já absorve as ~2 casas).

## Distribuição por `Plano` (D3 — proxy de tipo/capacidade)
{linhas_plano}

> `Total_Alunos_Cluster` NUNCA é somado nem vira coluna (soma por cluster →
> dupla-contagem); blindado na lista de proibidas do módulo.
"""
    if escrever:
        destino_md = Path(destino_md)
        destino_md.parent.mkdir(parents=True, exist_ok=True)
        destino_md.write_text(md, encoding="utf-8")
    return md


__all__ = [
    "ingerir_oferta_academias_menores",
    "gerar_relatorio_qualidade",
    "CONTRATO_COLUNAS_OFERTA_MENORES",
    "VERSAO_CONTRATO_OFERTA_MENORES",
    "FONTE_DEFAULT",
    "DESTINO_DEFAULT",
]
