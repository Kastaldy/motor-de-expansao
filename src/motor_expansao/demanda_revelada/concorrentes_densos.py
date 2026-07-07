"""BLK-ATR-01: base DENSA de concorrentes do Huff (TotalPass/WellHub/Unidades) + re-validacao.

Ingere os ~93 CSVs LOCAIS de concorrentes (`concorrentes/totalpass/csvs`,
`concorrentes/wellhub/csvs`, `concorrentes/Unidades`), deriva `hex_id_res7` na FRONTEIRA,
classifica a rede por token (reuso de `classificacao_rede_menor.classificar_rede`), DESCARTA a
PII textual (slug/nome/cidade/CEP/endereco/coords brutas) logo apos derivar hex+rede, deduplica
por `(hex_id_res7, rede_normalizada)` em 2 niveis (intra-fonte + inter-fonte com precedencia
`unidades > totalpass > wellhub`) e contra `concorrentes_mapeados.parquet` (base atual), e
materializa `data/staging/concorrentes_densos.parquet` (gitignored, NAO oficial do M1).

Depois recomputa o share Huff sobre a base densa e RE-VALIDA o GO do BLK-TP-07 out-of-fold
(mesmo harness k-fold 5x5 seed=42/IC95/BETA_GRID de `huff_captura.calibrar_huff_captura`, sem
alterar `huff_captura.py`), comparando ANTES (base original ~3,3k) x DEPOIS (base densa) e
gravando `data/analysis/relatorio_huff_densa.md` (gitignored). NO-GO e resultado VALIDO (DEC-008).

GUARDRAILS (DEC-001/DEC-008/DEC-009/DEC-012/DEC-013; CLAUDE.md §5):
  - READ-ONLY sobre o M1: nenhuma escrita em score/pesos/carteira/plano/artefatos oficiais; a base
    densa e parquet SEPARADO (`concorrentes_mapeados.parquet` e apenas LIDO, nunca sobrescrito).
  - Pacote DISJUNTO (DEC-012): este modulo NUNCA importa de `pipelines/m1/`, `censo_*`,
    `dashboard/`, `api` nem `config.py` raiz. Imports so de stdlib, `h3`/`pandas`/`numpy` e de
    DENTRO do proprio pacote `demanda_revelada` (que ja re-exporta o nucleo puro do Huff).
  - DEC-009: `membros` e ALVO OBSERVADO; a base densa e o PREDITOR geometrico (share puro), NUNCA
    preditor geografico de magnitude. Este bloco VALIDA -- NAO integra ao residual/carteira/plano
    (integracao = BLK-TP-09, DEC-013 §3, sob gate humano).
  - DEC-012: dado de ESTABELECIMENTO concorrente (nome/coords) e PUBLICO -- PODE ser usado para
    derivar hex + classificar rede; a PII textual e dropada na fronteira e o parquet final so tem
    o centroide do hex (via `h3.cell_to_latlng`), nunca a coord GPS bruta. `NAO_ABRA/` nunca
    versionado; testes so com fixtures sinteticas.

API h3 = v4 (`latlng_to_cell`/`cell_to_latlng`/`get_resolution`/`is_valid_cell`).
"""

from __future__ import annotations

import logging
from pathlib import Path

import h3
import numpy as np
import pandas as pd

from .classificacao_rede_menor import classificar_rede
from .contrato import H3_RES_CONTRATO
from .huff_captura import (
    _assert_sem_pii_no_relatorio,
    _preparar_join_real,
    calcular_share_por_hex,
    calibrar_huff_captura,
)

_logger = logging.getLogger(__name__)

# Carimbo de reprodutibilidade do contrato (gravado em todas as linhas do parquet).
VERSAO_CONTRATO_CONCORRENTES_DENSOS = "concorrentes_densos_v1"

# Caminhos default (CSVs locais em concorrentes/; parquets/relatorio gitignored).
DIR_TOTALPASS_DEFAULT = Path("concorrentes/totalpass/csvs")
DIR_WELLHUB_DEFAULT = Path("concorrentes/wellhub/csvs")
DIR_UNIDADES_DEFAULT = Path("concorrentes/Unidades")
CONCORRENTES_MAPEADOS_DEFAULT = Path("data/staging/concorrentes_mapeados.parquet")
DEMANDA_DEFAULT = Path("data/staging/demanda_revelada_h3.parquet")
MERCADO_DEFAULT = Path("data/staging/hexagonos_mercado_mapeado.parquet")
DESTINO_PARQUET_DEFAULT = Path("data/staging/concorrentes_densos.parquet")
RELATORIO_HUFF_DEFAULT = Path("data/analysis/relatorio_huff_densa.md")

# Prefixo dos arquivos de `Unidades/`: `unidades_<rede>.csv` -> rede = stem sem esse prefixo.
_PREFIXO_UNIDADES = "unidades_"

# Precedencia estavel para escolher a linha sobrevivente no dedup inter-fonte.
_PRECEDENCIA_FONTE: dict[str, int] = {"unidades": 0, "totalpass": 1, "wellhub": 2}

# Colunas textuais de entrada dos CSVs descartadas na FRONTEIRA (PII/ruido; nao vao ao parquet).
_COLUNAS_DROP_FRONTEIRA = (
    "slug",
    "nome",
    "nome_unidade",
    "cidade",
    "uf",
    "cep",
    "endereco_formatado",
    "modalidades",
    "atividades",
    "data_coleta",
    "latitude",
    "longitude",
)

# Ordem e dtypes canonicos do parquet de saida (contrato `concorrentes_densos_v1`).
CONTRATO_COLUNAS_CONCORRENTES_DENSOS: dict[str, str] = {
    "hex_id_res7": "string",        # H3 res-7 (chave de join)
    "lat": "float64",               # centroide via h3.cell_to_latlng (NAO coord GPS bruta)
    "lng": "float64",               # idem
    "rede_normalizada": "string",   # categoria de rede (token; `independente` residual)
    "fonte": "string",              # totalpass | wellhub | unidades | base_atual
    "flag_da_base_atual": "bool",   # True se veio de concorrentes_mapeados.parquet
    "n_unidades_no_hex": "int64",   # nº de linhas brutas colapsadas (auditoria de densidade)
    "versao_contrato": "string",    # carimbo de reprodutibilidade
}


# --------------------------------------------------------------------------- #
# Geometria (fronteira -> hex; hex -> centroide anti-PII)
# --------------------------------------------------------------------------- #
def _to_cell(lat: object, lng: object) -> str | None:
    """Converte (lat,lng) bruta -> hex res-7 (h3 v4); None se invalido."""
    try:
        return h3.latlng_to_cell(float(lat), float(lng), H3_RES_CONTRATO)  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return None


def _centroide_hex(hex_id: object) -> tuple[float, float]:
    """Centroide (lat,lng) do hex via `h3.cell_to_latlng`. `(nan,nan)` se invalido.

    Anti-PII (DEC-012): a geometria do parquet vem do PROPRIO `hex_id`, NUNCA da coord GPS bruta.
    """
    try:
        lat, lng = h3.cell_to_latlng(str(hex_id))
        return float(lat), float(lng)
    except (ValueError, TypeError, KeyError):
        return (float("nan"), float("nan"))


# --------------------------------------------------------------------------- #
# Leitura por fonte (drop-PII na fronteira)
# --------------------------------------------------------------------------- #
def _ler_csv_tp_wh(caminho: Path, fonte: str) -> pd.DataFrame:
    """Le um CSV TotalPass/WellHub -> `hex_id_res7`, `rede_normalizada`, `fonte` (drop-PII).

    Colunas de entrada: `nome`/`latitude`/`longitude` (+ ruido textual dropado). A rede e
    classificada pelo `nome` cru (so em memoria); o nome/coords sao descartados imediatamente.
    """
    df = pd.read_csv(caminho, sep=";", encoding="utf-8-sig")
    hex_ids = [
        _to_cell(lat, lng)
        for lat, lng in zip(df.get("latitude"), df.get("longitude"), strict=False)
    ]
    redes = [classificar_rede(n) for n in df.get("nome", pd.Series(dtype="object"))]
    out = pd.DataFrame({"hex_id_res7": hex_ids, "rede_normalizada": redes})
    out["fonte"] = fonte
    return out.dropna(subset=["hex_id_res7"]).reset_index(drop=True)


def _ler_csv_unidades(caminho: Path) -> pd.DataFrame:
    """Le um CSV de `Unidades/` -> `hex_id_res7`, `rede_normalizada`, `fonte="unidades"`.

    A rede canonica = nome do arquivo sem o prefixo `unidades_` e sem extensao
    (`unidades_smart_fit.csv` -> `smart_fit`). Colunas de entrada: `nome_unidade`/`latitude`/
    `longitude`/`data_coleta` (dropadas apos derivar o hex).
    """
    df = pd.read_csv(caminho, sep=";", encoding="utf-8-sig")
    stem = caminho.stem
    rede = stem[len(_PREFIXO_UNIDADES):] if stem.startswith(_PREFIXO_UNIDADES) else stem
    hex_ids = [
        _to_cell(lat, lng)
        for lat, lng in zip(df.get("latitude"), df.get("longitude"), strict=False)
    ]
    out = pd.DataFrame({"hex_id_res7": hex_ids})
    out["rede_normalizada"] = rede
    out["fonte"] = "unidades"
    return out.dropna(subset=["hex_id_res7"]).reset_index(drop=True)


def ingerir_csvs_concorrentes(
    dir_totalpass: Path = DIR_TOTALPASS_DEFAULT,
    dir_wellhub: Path = DIR_WELLHUB_DEFAULT,
    dir_unidades: Path = DIR_UNIDADES_DEFAULT,
) -> pd.DataFrame:
    """Le as 3 pastas de CSVs -> frame LONGO consolidado + Nivel 1 (dedup intra-fonte).

    Concatena TotalPass/WellHub (via `_ler_csv_tp_wh`) e Unidades (via `_ler_csv_unidades`);
    aplica o Nivel 1 do dedup: colapsa cada `(hex_id_res7, rede_normalizada, fonte)` para 1 linha,
    contando as brutas em `n_unidades_no_hex`. NAO faz dedup inter-fonte (isso e `deduplicar`).
    NAO escreve -- e a etapa de ingestao pura (o sanity de volume mede aqui).
    """
    partes: list[pd.DataFrame] = []
    for caminho in sorted(Path(dir_totalpass).glob("*.csv")):
        partes.append(_ler_csv_tp_wh(caminho, "totalpass"))
    for caminho in sorted(Path(dir_wellhub).glob("*.csv")):
        partes.append(_ler_csv_tp_wh(caminho, "wellhub"))
    for caminho in sorted(Path(dir_unidades).glob("*.csv")):
        partes.append(_ler_csv_unidades(caminho))

    if not partes:
        return pd.DataFrame(
            columns=["hex_id_res7", "rede_normalizada", "fonte", "n_unidades_no_hex"]
        )

    bruto = pd.concat(partes, ignore_index=True)
    bruto["hex_id_res7"] = bruto["hex_id_res7"].astype(str)
    bruto["rede_normalizada"] = bruto["rede_normalizada"].astype(str)
    bruto["fonte"] = bruto["fonte"].astype(str)

    # Nivel 1: colapsa duplicatas intra-fonte, preservando a contagem bruta.
    consolidado = (
        bruto.groupby(["hex_id_res7", "rede_normalizada", "fonte"], as_index=False)
        .size()
        .rename(columns={"size": "n_unidades_no_hex"})
    )
    consolidado["n_unidades_no_hex"] = consolidado["n_unidades_no_hex"].astype("int64")
    return consolidado.reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Base atual (concorrentes_mapeados.parquet) -- so LIDA
# --------------------------------------------------------------------------- #
def _ler_base_atual(concorrentes_path: Path) -> pd.DataFrame:
    """Le `(hex_id_res7, rede)` unicos da base atual -> frame `base_atual` (so leitura).

    Retorna frame com `hex_id_res7`, `rede_normalizada` (= `rede` da base, mesmos 28 slugs),
    `fonte="base_atual"`, `flag_da_base_atual=True`, `n_unidades_no_hex=1`. Frame vazio se ausente.
    """
    if not Path(concorrentes_path).exists():
        return pd.DataFrame(
            columns=[
                "hex_id_res7",
                "rede_normalizada",
                "fonte",
                "flag_da_base_atual",
                "n_unidades_no_hex",
            ]
        )
    df = pd.read_parquet(concorrentes_path, columns=["hex_id_res7", "rede"])
    df = df.dropna(subset=["hex_id_res7", "rede"])
    df = df.rename(columns={"rede": "rede_normalizada"})
    df["hex_id_res7"] = df["hex_id_res7"].astype(str)
    df["rede_normalizada"] = df["rede_normalizada"].astype(str)
    df = df.drop_duplicates(subset=["hex_id_res7", "rede_normalizada"]).reset_index(drop=True)
    df["fonte"] = "base_atual"
    df["flag_da_base_atual"] = True
    df["n_unidades_no_hex"] = 1
    return df


def deduplicar(
    df_consolidado: pd.DataFrame,
    concorrentes_path: Path = CONCORRENTES_MAPEADOS_DEFAULT,
    *,
    incluir_base_atual: bool = True,
) -> pd.DataFrame:
    """Nivel 2: dedup inter-fonte + contra a base atual. Chave = `(hex_id_res7, rede_normalizada)`.

    - Inter-fonte: precedencia `unidades > totalpass > wellhub`; a linha sobrevivente mantem o seu
      proprio `n_unidades_no_hex` (a densidade fina nao afeta o Huff, que usa 1 coord por hex).
    - Contra base atual: pares `(hex, rede)` ja presentes em `concorrentes_mapeados` sao removidos
      das 3 fontes novas (nao duplicar); a base atual inteira e anexada como `fonte="base_atual"`.
    - `flag_da_base_atual=False` para as 3 fontes novas.

    Retorna frame com `(hex_id_res7, rede_normalizada)` ÚNICA no total.
    """
    df = df_consolidado.copy()
    if df.empty:
        df = pd.DataFrame(
            columns=["hex_id_res7", "rede_normalizada", "fonte", "n_unidades_no_hex"]
        )

    # Dedup inter-fonte (determinista por precedencia de fonte + hex + rede).
    df["_prec"] = df["fonte"].map(_PRECEDENCIA_FONTE).fillna(99).astype(int)
    df = df.sort_values(["hex_id_res7", "rede_normalizada", "_prec"], kind="mergesort")
    df = df.drop_duplicates(subset=["hex_id_res7", "rede_normalizada"], keep="first")
    df = df.drop(columns=["_prec"]).reset_index(drop=True)
    df["flag_da_base_atual"] = False

    base_atual = (
        _ler_base_atual(concorrentes_path)
        if incluir_base_atual
        else pd.DataFrame(
            columns=[
                "hex_id_res7",
                "rede_normalizada",
                "fonte",
                "flag_da_base_atual",
                "n_unidades_no_hex",
            ]
        )
    )

    # Remove das 3 fontes novas os pares (hex, rede) ja mapeados na base atual.
    if not base_atual.empty:
        pares_base = set(
            zip(
                base_atual["hex_id_res7"].astype(str),
                base_atual["rede_normalizada"].astype(str),
                strict=False,
            )
        )
        if not df.empty:
            chaves = list(
                zip(
                    df["hex_id_res7"].astype(str),
                    df["rede_normalizada"].astype(str),
                    strict=False,
                )
            )
            manter = pd.Series([k not in pares_base for k in chaves], index=df.index)
            df = df.loc[manter].reset_index(drop=True)

    cols = ["hex_id_res7", "rede_normalizada", "fonte", "flag_da_base_atual", "n_unidades_no_hex"]
    frames = [f[cols] for f in (df, base_atual) if not f.empty]
    if not frames:
        return pd.DataFrame(columns=cols)
    out = pd.concat(frames, ignore_index=True)
    return out.reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Finalizacao do schema + validacoes
# --------------------------------------------------------------------------- #
def _finalizar_schema(df: pd.DataFrame) -> pd.DataFrame:
    """Materializa `lat`/`lng` (centroide do hex), carimba versao, coage dtypes, ordena."""
    out = df.copy()
    centroides = [_centroide_hex(h) for h in out["hex_id_res7"]]
    out["lat"] = [c[0] for c in centroides]
    out["lng"] = [c[1] for c in centroides]
    out["versao_contrato"] = VERSAO_CONTRATO_CONCORRENTES_DENSOS

    for col, dtype in CONTRATO_COLUNAS_CONCORRENTES_DENSOS.items():
        if dtype in ("string", "bool", "float64", "int64"):
            out[col] = out[col].astype(dtype)

    out = out[list(CONTRATO_COLUNAS_CONCORRENTES_DENSOS.keys())]
    out = out.sort_values(["hex_id_res7", "rede_normalizada"]).reset_index(drop=True)
    return out


def _assert_schema(df: pd.DataFrame) -> None:
    """Falha se: coluna fora do contrato; NaN/vazio em chave; hex nao res-7; chave duplicada."""
    extras = set(df.columns) - set(CONTRATO_COLUNAS_CONCORRENTES_DENSOS)
    if extras:
        raise ValueError(f"colunas fora do contrato: {sorted(extras)}")
    faltando = set(CONTRATO_COLUNAS_CONCORRENTES_DENSOS) - set(df.columns)
    if faltando:
        raise ValueError(f"colunas do contrato ausentes: {sorted(faltando)}")
    if df.empty:
        return
    for chave in ("hex_id_res7", "rede_normalizada"):
        vazio = df[chave].isna() | (df[chave].astype(str).str.len() == 0)
        if bool(vazio.any()):
            raise ValueError(f"`{chave}` com NaN/vazio no parquet denso")
    invalidos: list[str] = []
    for hid in df["hex_id_res7"].astype(str).unique():
        if not h3.is_valid_cell(hid) or h3.get_resolution(hid) != H3_RES_CONTRATO:
            invalidos.append(hid)
            if len(invalidos) >= 5:
                break
    if invalidos:
        raise ValueError(f"hex_id_res7 fora de res-{H3_RES_CONTRATO}: amostra {invalidos}")
    dup = df.duplicated(subset=["hex_id_res7", "rede_normalizada"]).sum()
    if int(dup) > 0:
        raise ValueError(f"chave (hex_id_res7, rede_normalizada) duplicada: {int(dup)} linha(s)")


def materializar(
    dir_totalpass: Path = DIR_TOTALPASS_DEFAULT,
    dir_wellhub: Path = DIR_WELLHUB_DEFAULT,
    dir_unidades: Path = DIR_UNIDADES_DEFAULT,
    destino: Path = DESTINO_PARQUET_DEFAULT,
    concorrentes_path: Path = CONCORRENTES_MAPEADOS_DEFAULT,
    *,
    escrever: bool = True,
    incluir_base_atual: bool = True,
) -> pd.DataFrame:
    """Orquestra ingestao -> dedup -> schema -> validacao -> (opcional) grava o parquet denso.

    Testes chamam com `escrever=False` e fixtures sinteticas (nunca CSVs reais). READ-ONLY sobre
    o M1: `concorrentes_mapeados.parquet` e apenas LIDO; o destino e parquet SEPARADO.
    """
    consolidado = ingerir_csvs_concorrentes(dir_totalpass, dir_wellhub, dir_unidades)
    dedup = deduplicar(consolidado, concorrentes_path, incluir_base_atual=incluir_base_atual)
    final = _finalizar_schema(dedup)
    _assert_schema(final)
    if escrever:
        destino = Path(destino)
        destino.parent.mkdir(parents=True, exist_ok=True)
        final.to_parquet(destino, index=False)
        _logger.info("concorrentes_densos.parquet escrito: %s (%d linhas)", destino, len(final))
    return final


# --------------------------------------------------------------------------- #
# Re-validacao Huff com a base densa
# --------------------------------------------------------------------------- #
def _coords_densas(df_denso: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Extrai `(conc_lat, conc_lng)` finitos do parquet denso (ja sao centroides de hex)."""
    lat = pd.to_numeric(df_denso.get("lat"), errors="coerce").to_numpy(dtype=float)
    lng = pd.to_numeric(df_denso.get("lng"), errors="coerce").to_numpy(dtype=float)
    ok = np.isfinite(lat) & np.isfinite(lng)
    return lat[ok], lng[ok]


def _preparar_join_demanda(
    dem_path: Path = DEMANDA_DEFAULT, mkt_path: Path = MERCADO_DEFAULT
) -> pd.DataFrame:
    """Le a demanda revelada (+ uf/ultra do mercado) e monta o join via `_preparar_join_real`."""
    dem = pd.read_parquet(dem_path)
    mkt = None
    mkt_p = Path(mkt_path)
    if mkt_p.exists():
        try:
            mkt = pd.read_parquet(
                mkt_p,
                columns=["hex_id", "uf", "n_unidades_ultra_1km", "dist_ultra_mais_proxima_m"],
            )
        except Exception as exc:  # pragma: no cover - mercado sem essas colunas
            _logger.info("mercado sem colunas uf/ultra (%s); segue sem elas", exc)
            mkt = None
    return _preparar_join_real(dem, mkt)


def _cobertura_share(
    df_join: pd.DataFrame, conc_lat: np.ndarray, conc_lng: np.ndarray, beta: float
) -> dict[str, float]:
    """Recomputa o share do beta e mede cobertura util (hexes com share < 1.0 = competitivos)."""
    hexes = df_join["hex_id"].astype(str).tolist()
    share = calcular_share_por_hex(hexes, conc_lat, conc_lng, beta)
    finito = np.isfinite(share)
    n_val = int(finito.sum())
    n_lt1 = int((finito & (share < 1.0)).sum())
    pct = float(100.0 * n_lt1 / n_val) if n_val else float("nan")
    return {
        "n_concorrentes": float(len(conc_lat)),
        "n_hex_share_lt_1": float(n_lt1),
        "pct_hex_competitivo": pct,
    }


def revalidar_huff_densa(
    df_denso: pd.DataFrame,
    dem_path: Path = DEMANDA_DEFAULT,
    mkt_path: Path = MERCADO_DEFAULT,
    *,
    df_join: pd.DataFrame | None = None,
):
    """Recomputa o share Huff sobre a base DENSA e re-valida o GO out-of-fold (BLK-TP-07).

    `df_join` injetavel em teste (evita I/O). Retorna `(result, cobertura)` onde `result` e um
    `HuffCapturaResult` e `cobertura` e o dict de cobertura util do beta selecionado. Alvo
    `membros` INTOCADO; harness k-fold 5x5 seed=42 de `calibrar_huff_captura` (nao alterado).
    """
    join = df_join if df_join is not None else _preparar_join_demanda(dem_path, mkt_path)
    conc_lat, conc_lng = _coords_densas(df_denso)
    result = calibrar_huff_captura(join, conc_lat, conc_lng)
    cobertura = _cobertura_share(join, conc_lat, conc_lng, result.beta_selecionado)
    return result, cobertura


# --------------------------------------------------------------------------- #
# Relatorio ANTES x DEPOIS (gitignored, sem PII)
# --------------------------------------------------------------------------- #
def _bloco_dedup(
    consolidado: pd.DataFrame, dedup: pd.DataFrame, base_atual: pd.DataFrame
) -> list[str]:
    """Linhas markdown do bloco de DEDUP (bruto por fonte, colapsos, liquido final)."""
    por_fonte = (
        consolidado.groupby("fonte")["n_unidades_no_hex"].sum().to_dict()
        if not consolidado.empty
        else {}
    )
    pares_intra = int(len(consolidado))  # ja colapsado intra-fonte -> pares (hex,rede,fonte)
    novas = dedup[~dedup["flag_da_base_atual"]] if not dedup.empty else dedup
    n_novas = int(len(novas))
    n_base = int(len(base_atual))
    L: list[str] = []
    L.append("## DEDUP (bruto por fonte -> liquido final)")
    L.append("")
    L.append("| etapa | valor |")
    L.append("| --- | ---: |")
    for fonte in ("totalpass", "wellhub", "unidades"):
        L.append(f"| unidades brutas `{fonte}` (Σ n_unidades_no_hex) | {int(por_fonte.get(fonte, 0))} |")
    L.append(f"| pares (hex, rede, fonte) apos dedup intra-fonte | {pares_intra} |")
    L.append(f"| pares (hex, rede) novos apos dedup inter-fonte + vs base atual | {n_novas} |")
    L.append(f"| pares (hex, rede) da base atual anexados | {n_base} |")
    L.append(f"| total liquido final (chave unica) | {n_novas + n_base} |")
    L.append("")
    L.append(
        "Precedencia de fonte no dedup inter-fonte: `unidades > totalpass > wellhub` "
        "(linha sobrevivente mantem o proprio `n_unidades_no_hex`)."
    )
    L.append("")
    return L


def _linha_result_md(rotulo: str, r, cob: dict[str, float]) -> list[str]:
    """Linhas de uma coluna ANTES/DEPOIS da tabela de metricas."""
    return [
        f"| {rotulo} | n_conc={cob.get('n_concorrentes', float('nan')):.0f}; "
        f"beta={r.beta_selecionado:g}; "
        f"R2_oof_log={r.r2_oof_log:+.4f} IC95[{r.ic95_r2_oof[0]:+.4f},{r.ic95_r2_oof[1]:+.4f}]; "
        f"rho_oof={r.rho_oof:+.4f} IC95[{r.ic95_rho_oof[0]:+.4f},{r.ic95_rho_oof[1]:+.4f}]; "
        f"R2_base_geo={r.r2_oof_baseline_geometrico:+.4f}; "
        f"n_hex_share_lt_1={cob.get('n_hex_share_lt_1', float('nan')):.0f}; "
        f"pct_competitivo={cob.get('pct_hex_competitivo', float('nan')):.1f}%; "
        f"veredito={r.veredito}{('(' + r.tipo_go + ')') if r.tipo_go else ''} |"
    ]


def gerar_relatorio_huff_densa(
    result_densa,
    result_original,
    cobertura_densa: dict[str, float],
    cobertura_original: dict[str, float],
    consolidado: pd.DataFrame,
    dedup: pd.DataFrame,
    base_atual: pd.DataFrame,
    destino: Path = RELATORIO_HUFF_DEFAULT,
    *,
    escrever: bool = True,
) -> str:
    """Markdown (PT, sem PII) com dedup + tabela ANTES (base original) x DEPOIS (base densa).

    ANTES/DEPOIS recomputados no MESMO runtime (reprodutiveis, nao copiados do doc). Veredito
    honesto GO/NO-GO copiado de `result_densa.nota_honesta`. Rede de seguranca anti-PII antes de
    gravar. Escreve em `data/analysis/relatorio_huff_densa.md` (gitignored).
    """
    L: list[str] = []
    L.append("# Re-validacao do Huff com base DENSA de concorrentes -- BLK-ATR-01")
    L.append("")
    L.append(
        "READ-ONLY sobre o M1 (DEC-001/DEC-008/DEC-009/DEC-013). Pacote disjunto (DEC-012). "
        "Sem PII (so contagens/metricas; centroide via `h3.cell_to_latlng`, nunca coord GPS bruta). "
        "Base densa = TotalPass + WellHub + Unidades + `concorrentes_mapeados` (base atual), "
        "deduplicada por `(hex_id_res7, rede_normalizada)`. Este bloco VALIDA -- NAO integra a "
        "captura ao residual/carteira/plano (isso e BLK-TP-09 / DEC-013 §3, sob gate humano)."
    )
    L.append("")
    L.extend(_bloco_dedup(consolidado, dedup, base_atual))
    L.append("## Metricas honestas ANTES x DEPOIS (mesmo harness k-fold 5x5 seed=42)")
    L.append("")
    L.append("| base | metricas out-of-fold |")
    L.append("| --- | --- |")
    L.extend(_linha_result_md("ANTES (concorrentes_mapeados)", result_original, cobertura_original))
    L.extend(_linha_result_md("DEPOIS (base densa)", result_densa, cobertura_densa))
    L.append("")
    L.append(
        "Baseline BLK-TP-07 declarado (referencia): R2_oof_log ~= +0,4391, "
        "IC95 [+0,4251, +0,4523], beta=0,5. Os numeros ANTES/DEPOIS acima sao recomputados no "
        "mesmo runtime (nao copiados)."
    )
    L.append("")
    L.append("## Veredito honesto (DEC-008 -- NO-GO e resultado VALIDO)")
    L.append("")
    L.append("```")
    L.append(result_densa.nota_honesta.rstrip("\n"))
    L.append("```")
    L.append("")
    texto = "\n".join(L)
    _assert_sem_pii_no_relatorio(texto)
    if escrever:
        destino = Path(destino)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(texto, encoding="utf-8")
        _logger.info("relatorio BLK-ATR-01 escrito: %s", destino)
    return texto


# --------------------------------------------------------------------------- #
# Orquestrador real (caminho de disco -- NAO chamado em teste)
# --------------------------------------------------------------------------- #
def executar(
    dir_totalpass: Path = DIR_TOTALPASS_DEFAULT,
    dir_wellhub: Path = DIR_WELLHUB_DEFAULT,
    dir_unidades: Path = DIR_UNIDADES_DEFAULT,
    destino_parquet: Path = DESTINO_PARQUET_DEFAULT,
    concorrentes_path: Path = CONCORRENTES_MAPEADOS_DEFAULT,
    dem_path: Path = DEMANDA_DEFAULT,
    mkt_path: Path = MERCADO_DEFAULT,
    relatorio: Path = RELATORIO_HUFF_DEFAULT,
    *,
    incluir_base_atual: bool = True,
):  # pragma: no cover - caminho de disco, nao chamado em teste
    """Materializa a base densa, re-valida o Huff (ANTES x DEPOIS) e grava o relatorio.

    Operacao CARA (share sobre ~32k concorrentes x ~16k hexes) e gitignored. NAO rodar no
    building; o QA pode rodar se necessario. Retorna `(df_denso, result_densa)`.
    """
    # 1. Materializa a base densa (+ instrumenta o dedup para o relatorio).
    consolidado = ingerir_csvs_concorrentes(dir_totalpass, dir_wellhub, dir_unidades)
    dedup = deduplicar(consolidado, concorrentes_path, incluir_base_atual=incluir_base_atual)
    base_atual = (
        _ler_base_atual(concorrentes_path)
        if incluir_base_atual
        else pd.DataFrame(columns=["hex_id_res7", "rede_normalizada"])
    )
    df_denso = _finalizar_schema(dedup)
    _assert_schema(df_denso)
    destino_parquet = Path(destino_parquet)
    destino_parquet.parent.mkdir(parents=True, exist_ok=True)
    df_denso.to_parquet(destino_parquet, index=False)

    # 2. Join da demanda (reuso do preparo do BLK-TP-07).
    df_join = _preparar_join_demanda(dem_path, mkt_path)

    # 3. DEPOIS (base densa) + ANTES (base original) no MESMO runtime.
    result_densa, cobertura_densa = revalidar_huff_densa(df_denso, df_join=df_join)

    from motor_expansao.dimensionamento.huff import _carregar_concorrentes

    conc_lat0, conc_lng0 = _carregar_concorrentes(Path(concorrentes_path))
    result_original = calibrar_huff_captura(df_join, conc_lat0, conc_lng0)
    cobertura_original = _cobertura_share(
        df_join, conc_lat0, conc_lng0, result_original.beta_selecionado
    )

    # 4. Relatorio ANTES x DEPOIS (gitignored).
    gerar_relatorio_huff_densa(
        result_densa,
        result_original,
        cobertura_densa,
        cobertura_original,
        consolidado,
        dedup,
        base_atual,
        destino=relatorio,
    )
    return df_denso, result_densa


__all__ = [
    "materializar",
    "ingerir_csvs_concorrentes",
    "deduplicar",
    "revalidar_huff_densa",
    "gerar_relatorio_huff_densa",
    "executar",
    "CONTRATO_COLUNAS_CONCORRENTES_DENSOS",
    "VERSAO_CONTRATO_CONCORRENTES_DENSOS",
    "DESTINO_PARQUET_DEFAULT",
    "RELATORIO_HUFF_DEFAULT",
]


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    _df, _res = executar()
    print("linhas base densa:", len(_df))
    print("veredito:", _res.veredito, _res.tipo_go)
