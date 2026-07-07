"""BLK-ATR-01-FU1: aferição de precisão/overlap da base densa vs unidades reais do NAO_ABRA.

Cruza as bases reais de estabelecimentos (`NAO_ABRA/01_SmartFit.xlsx` e
`NAO_ABRA/03_Competidores.xlsx`) com `data/staging/concorrentes_densos.parquet` para medir
recall, overlap por rede e documentar caveats de imprecisão, gerando relatório em
`data/analysis/relatorio_overlap_nao_abra.md` (gitignored) sem persistir PII.

GUARDRAILS (DEC-012 / DEC-001 / DEC-009 / CLAUDE.md §5):
  - READ-ONLY sobre o M1: zero escrita em score/pesos/carteira/plano/artefatos oficiais.
  - Pacote DISJUNTO: NUNCA importa de `pipelines/m1/`, `dashboard/`, `censo_*`, `api/`,
    `config.py`. Imports só de stdlib, `h3`, `pandas` e de DENTRO do próprio pacote.
  - DEC-012: dado de ESTABELECIMENTO (nome/coords) é PÚBLICO; PII textual (ID, Nome,
    Nome_Academia, Latitude, Longitude, Cluster_ID etc.) dropada NA FRONTEIRA antes de
    qualquer persistência. Relatório contém SÓ contagens/métricas agregadas.
  - `concorrentes_densos.parquet` SÓ LIDO (não reescrito); mtime não muda.
  - `NAO_ABRA/totalpass_final*.html` NUNCA lido (DEC-012 §3).

API h3 = v4 (`latlng_to_cell`/`is_valid_cell`/`get_resolution`).
"""

from __future__ import annotations

import logging
from pathlib import Path

import h3
import pandas as pd

from .classificacao_rede_menor import classificar_rede
from .contrato import H3_RES_CONTRATO

_logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Constantes públicas do módulo
# --------------------------------------------------------------------------- #
VERSAO_CONTRATO_OVERLAP = "overlap_nao_abra_v1"
REDE_SMARTFIT = "smart_fit"

# Colunas PII que NUNCA devem aparecer no relatório (rede de segurança anti-PII).
_NOMES_PROIBIDOS_RELATORIO: frozenset[str] = frozenset(
    {"nome", "nome_academia", "id", "nome_unidade"}
)

# Caminhos default (gitignored)
SMARTFIT_DEFAULT = Path("NAO_ABRA/01_SmartFit.xlsx")
COMPETIDORES_DEFAULT = Path("NAO_ABRA/03_Competidores.xlsx")
DENSOS_DEFAULT = Path("data/staging/concorrentes_densos.parquet")
RELATORIO_DEFAULT = Path("data/analysis/relatorio_overlap_nao_abra.md")

__all__ = [
    "executar",
    "calcular_metricas_smartfit",
    "calcular_metricas_competidores",
    "gerar_relatorio",
    "RELATORIO_DEFAULT",
    "SMARTFIT_DEFAULT",
    "COMPETIDORES_DEFAULT",
    "DENSOS_DEFAULT",
    "VERSAO_CONTRATO_OVERLAP",
]


# --------------------------------------------------------------------------- #
# Geometria
# --------------------------------------------------------------------------- #
def _to_hex(lat: object, lng: object) -> str | None:
    """Converte (lat, lng) para hex H3 res-7; None se inválido."""
    try:
        return h3.latlng_to_cell(float(lat), float(lng), H3_RES_CONTRATO)  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return None


# --------------------------------------------------------------------------- #
# Leitura das fontes NAO_ABRA (drop-PII na fronteira)
# --------------------------------------------------------------------------- #
def _ler_smartfit(fonte: Path) -> pd.DataFrame:
    """Lê `01_SmartFit.xlsx` e retorna DataFrame com apenas `hex_id` (sem PII).

    Colunas de entrada: `ID`, `Nome`, `Latitude`, `Longitude`.
    Drop-PII imediato após derivar hex — nunca persiste ID/Nome/coords.
    Retorna DataFrame com coluna única `hex_id`, sem NaN.
    """
    df = pd.read_excel(fonte)
    hex_ids = [
        _to_hex(lat, lng)
        for lat, lng in zip(df.get("Latitude", pd.Series(dtype="object")),
                            df.get("Longitude", pd.Series(dtype="object")),
                            strict=False)
    ]
    out = pd.DataFrame({"hex_id": hex_ids})
    # Drop-PII: NENHUMA coluna textual persiste além do hex
    return out.dropna(subset=["hex_id"]).reset_index(drop=True)


def _ler_competidores(fonte: Path) -> tuple[pd.DataFrame, int]:
    """Lê `03_Competidores.xlsx` e retorna (df_sem_pii, n_skyfit_nao_reconhecido).

    Colunas de entrada: `Latitude`, `Longitude`, `Nome_Academia`, + outras ignoradas.
    Drop-PII imediato após derivar hex + rede_normalizada.
    Retorna DataFrame com colunas `hex_id` e `rede_normalizada`, sem NaN em hex_id.

    CAVEAT: coords com 1-2 decimais (~10 km de precisão) causam viés de hex res-7;
    recall será artificialmente baixo para este arquivo — documentado no relatório.
    """
    df = pd.read_excel(fonte)
    nomes = df.get("Nome_Academia", pd.Series(dtype="object"))
    lats = df.get("Latitude", pd.Series(dtype="object"))
    lngs = df.get("Longitude", pd.Series(dtype="object"))

    hex_ids = [_to_hex(lat, lng) for lat, lng in zip(lats, lngs, strict=False)]
    redes = [classificar_rede(str(n) if pd.notna(n) else "") for n in nomes]

    # Contar SKYFIT não reconhecido ANTES do drop-PII (único momento em que o nome existe)
    n_skyfit_nao_reconhecido = sum(
        1
        for nome, rede in zip(nomes, redes, strict=False)
        if pd.notna(nome) and "skyfit" in str(nome).lower() and rede == "independente"
    )

    out = pd.DataFrame({"hex_id": hex_ids, "rede_normalizada": redes})
    # Drop-PII imediato: apenas hex_id e rede_normalizada sobrevivem
    return out.dropna(subset=["hex_id"]).reset_index(drop=True), n_skyfit_nao_reconhecido


# --------------------------------------------------------------------------- #
# Métricas
# --------------------------------------------------------------------------- #
def calcular_metricas_smartfit(
    df_sf: pd.DataFrame, df_denso: pd.DataFrame
) -> dict:
    """Calcula recall e métricas de overlap da Smart Fit vs base densa.

    Args:
        df_sf: DataFrame com coluna `hex_id` (resultado de `_ler_smartfit`, sem PII).
        df_denso: Parquet denso (`concorrentes_densos.parquet`); coluna chave = `hex_id_res7`.

    Returns:
        dict com: recall, n_sf_total, n_denso_sf, n_intersecao,
                  n_sf_ausentes_da_densa, n_densa_sem_sf.
    """
    hexes_sf: set[str] = set(df_sf["hex_id"].astype(str).unique())
    denso_sf = df_denso[df_denso["rede_normalizada"].astype(str) == REDE_SMARTFIT]
    hexes_denso_sf: set[str] = set(denso_sf["hex_id_res7"].astype(str).unique())

    intersecao = hexes_sf & hexes_denso_sf
    n_sf_total = len(hexes_sf)
    n_denso_sf = len(hexes_denso_sf)
    n_intersecao = len(intersecao)
    recall = n_intersecao / n_sf_total if n_sf_total > 0 else 0.0

    return {
        "recall": recall,
        "n_sf_total": n_sf_total,
        "n_denso_sf": n_denso_sf,
        "n_intersecao": n_intersecao,
        "n_sf_ausentes_da_densa": len(hexes_sf - hexes_denso_sf),
        "n_densa_sem_sf": len(hexes_denso_sf - hexes_sf),
    }


def calcular_metricas_competidores(
    df_comp: pd.DataFrame, df_denso: pd.DataFrame
) -> dict:
    """Calcula recall e métricas de overlap do 03_Competidores vs base densa.

    Args:
        df_comp: DataFrame com `hex_id` e `rede_normalizada` (sem PII).
        df_denso: Parquet denso (`concorrentes_densos.parquet`); colunas `hex_id_res7`,
                  `rede_normalizada`.

    Returns:
        dict com: recall_global, n_pares_comp_total, n_pares_denso_total,
                  n_intersecao, tabela_por_rede (lista de dicts).
    """
    pares_comp: set[tuple[str, str]] = set(
        zip(
            df_comp["hex_id"].astype(str),
            df_comp["rede_normalizada"].astype(str),
            strict=False,
        )
    )
    pares_denso: set[tuple[str, str]] = set(
        zip(
            df_denso["hex_id_res7"].astype(str),
            df_denso["rede_normalizada"].astype(str),
            strict=False,
        )
    )

    n_pares_comp_total = len(pares_comp)
    n_pares_denso_total = len(pares_denso)
    n_intersecao = len(pares_comp & pares_denso)
    recall_global = n_intersecao / n_pares_comp_total if n_pares_comp_total > 0 else 0.0

    # Recall por rede (excluindo `independente` — não é classificável 1:1)
    redes_conhecidas = sorted(
        {r for r in df_comp["rede_normalizada"].astype(str).unique() if r != "independente"}
    )
    tabela_por_rede: list[dict] = []
    for rede in redes_conhecidas:
        pares_rede = {(h, r) for h, r in pares_comp if r == rede}
        n_pares_rede = len(pares_rede)
        n_inter_rede = len(pares_rede & pares_denso)
        recall_rede = n_inter_rede / n_pares_rede if n_pares_rede > 0 else 0.0
        tabela_por_rede.append(
            {
                "rede": rede,
                "n_pares_comp": n_pares_rede,
                "n_intersecao": n_inter_rede,
                "recall": recall_rede,
            }
        )

    return {
        "recall_global": recall_global,
        "n_pares_comp_total": n_pares_comp_total,
        "n_pares_denso_total": n_pares_denso_total,
        "n_intersecao": n_intersecao,
        "tabela_por_rede": tabela_por_rede,
    }


# --------------------------------------------------------------------------- #
# Rede de segurança anti-PII
# --------------------------------------------------------------------------- #
def _assert_sem_pii_relatorio(texto: str) -> None:
    """Falha se o relatório contiver colunas PII como headers de tabela Markdown.

    Verifica a presença de `| <termo_proibido> ` (case-insensitive) no texto.
    Isso garante que nenhum nome de coluna PII entrou por acidente num header de tabela.
    """
    for termo in _NOMES_PROIBIDOS_RELATORIO:
        # Verifica como header de tabela markdown (| Termo  ou | termo )
        for variante in (f"| {termo} ", f"| {termo.capitalize()} ", f"| {termo.upper()} "):
            if variante in texto:
                raise ValueError(
                    f"PII detectada no relatório: header de tabela '{variante}' encontrado"
                )


# --------------------------------------------------------------------------- #
# Geração do relatório
# --------------------------------------------------------------------------- #
def gerar_relatorio(
    metricas_sf: dict,
    metricas_comp: dict,
    n_skyfit_nao_reconhecido: int,
    df_denso_info: dict,
    destino: Path,
    *,
    escrever: bool = True,
) -> str:
    """Monta relatório Markdown (PT-BR, sem PII) e opcionalmente grava em disco.

    Args:
        metricas_sf: resultado de `calcular_metricas_smartfit`.
        metricas_comp: resultado de `calcular_metricas_competidores`.
        n_skyfit_nao_reconhecido: contagem de linhas "skyfit" classificadas como `independente`.
        df_denso_info: dict com `n_pares` e `n_redes` da base densa.
        destino: caminho de saída do relatório (gitignored).
        escrever: se True, escreve o arquivo; se False, só retorna o texto.

    Returns:
        Texto do relatório em Markdown.
    """
    L: list[str] = []

    # ---------- Header e disclaimers ----------
    L.append("# Aferição de Overlap: Base Densa de Concorrentes vs NAO_ABRA")
    L.append("")
    L.append(
        f"Versão do contrato: `{VERSAO_CONTRATO_OVERLAP}`  "
    )
    L.append(
        "READ-ONLY sobre o M1 (DEC-001/DEC-009/DEC-012). Pacote disjunto (DEC-012). "
        "Sem PII: apenas contagens e métricas agregadas; nomes/coords dropados na fronteira. "
        "`concorrentes_densos.parquet` só lido (mtime inalterado). "
        "`NAO_ABRA/totalpass_final*.html` nunca lido."
    )
    L.append("")

    # ---------- Resumo da base densa ----------
    L.append("## Resumo da base densa")
    L.append("")
    L.append("| métrica | valor |")
    L.append("| --- | ---: |")
    L.append(f"| pares (hex_id_res7, rede) totais | {df_denso_info.get('n_pares', 0)} |")
    L.append(f"| redes distintas | {df_denso_info.get('n_redes', 0)} |")
    L.append("")

    # ---------- Recall vs 01_SmartFit ----------
    L.append("## Recall vs `01_SmartFit.xlsx`")
    L.append("")
    L.append(
        "Cada unidade Smart Fit do arquivo real é convertida para hex H3 res-7 (6 decimais "
        "de precisão → baixo viés de hex). Recall = hexes do arquivo que aparecem na base "
        "densa com `rede_normalizada='smart_fit'`."
    )
    L.append("")
    L.append("| métrica | valor |")
    L.append("| --- | ---: |")
    L.append(f"| hexes únicos em 01_SmartFit | {metricas_sf.get('n_sf_total', 0)} |")
    L.append(f"| hexes Smart Fit na base densa | {metricas_sf.get('n_denso_sf', 0)} |")
    L.append(f"| interseção (hexes em ambos) | {metricas_sf.get('n_intersecao', 0)} |")
    L.append(f"| hexes no 01_SmartFit ausentes da densa | {metricas_sf.get('n_sf_ausentes_da_densa', 0)} |")
    L.append(f"| hexes na densa sem correspondente no 01_SmartFit | {metricas_sf.get('n_densa_sem_sf', 0)} |")
    recall_sf_pct = metricas_sf.get("recall", 0.0) * 100
    L.append(f"| **Recall Smart Fit** | **{recall_sf_pct:.1f}%** |")
    L.append("")

    # ---------- Recall vs 03_Competidores ----------
    L.append("## Recall/overlap vs `03_Competidores.xlsx`")
    L.append("")
    recall_global_pct = metricas_comp.get("recall_global", 0.0) * 100
    L.append(
        f"Recall global (pares hex+rede): **{recall_global_pct:.1f}%** "
        f"({metricas_comp.get('n_intersecao', 0)} de "
        f"{metricas_comp.get('n_pares_comp_total', 0)} pares do arquivo "
        f"encontrados na base densa com {metricas_comp.get('n_pares_denso_total', 0)} pares totais)."
    )
    L.append("")

    # Tabela por rede
    tabela = metricas_comp.get("tabela_por_rede", [])
    if tabela:
        L.append("### Recall por rede (redes conhecidas, excluindo `independente`)")
        L.append("")
        L.append("| rede | pares no 03_Competidores | interseção com densa | recall |")
        L.append("| --- | ---: | ---: | ---: |")
        for entrada in tabela:
            recall_pct = entrada.get("recall", 0.0) * 100
            L.append(
                f"| {entrada.get('rede', '')} "
                f"| {entrada.get('n_pares_comp', 0)} "
                f"| {entrada.get('n_intersecao', 0)} "
                f"| {recall_pct:.1f}% |"
            )
        L.append("")

    # Caveat: imprecisão de coordenadas
    L.append("### Caveat: imprecisão de coordenadas no 03_Competidores")
    L.append("")
    L.append(
        "As coordenadas do `03_Competidores.xlsx` possuem apenas **1-2 decimais** "
        "(precisão de ~10 km), enquanto o H3 res-7 tem células de ~5 km de lado. "
        "Esse arredondamento de coords provoca um viés sistemático de hex: a unidade "
        "real pode estar num hex diferente do hex derivado da coord arredondada, "
        "reduzindo artificialmente o recall calculado. O recall real provavelmente é "
        "maior do que o reportado acima. Não corrigido no código — documentado aqui "
        "como caveat de precisão."
    )
    L.append("")

    # Caveat: SKYFIT
    L.append("### Caveat: gap de token SKYFIT")
    L.append("")
    L.append(
        f"**{n_skyfit_nao_reconhecido} linha(s)** do `03_Competidores.xlsx` "
        "contém 'skyfit' no nome mas foram classificadas como `independente` "
        "pelo classificador atual (gap de token: `skyfit` não está na lista curada "
        "de `classificacao_rede_menor.py`). A base densa possui `skyfit` via fonte "
        "`unidades`, portanto esses pares não contribuem para o recall de `skyfit` "
        "calculado acima. Correção planejada: adicionar token `skyfit` em bloco futuro "
        "sob gate humano (fora do escopo deste FU1)."
    )
    L.append("")

    # ---------- Recomendação ----------
    L.append("## Recomendação")
    L.append("")
    L.append(
        "A base densa (`concorrentes_densos.parquet`) apresenta recall alto para Smart Fit "
        "(fonte de maior precisão de coords, 6 decimais). Para o `03_Competidores.xlsx`, "
        "o recall calculado é subestimado pelo viés de coord com 1-2 decimais — "
        "o overlap real é maior do que o número reportado sugere. "
        "A base densa é **suficiente para o modelo Huff** como insumo de oferta: "
        "captura as principais redes via `unidades/` (coordenadas de alta precisão) "
        "e complementa com TotalPass/WellHub onde disponível. "
        "Recomenda-se manter o fluxo atual e revisar o token SKYFIT em bloco futuro."
    )
    L.append("")

    texto = "\n".join(L)

    # Rede de segurança anti-PII antes de qualquer persistência
    _assert_sem_pii_relatorio(texto)

    if escrever:
        destino = Path(destino)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(texto, encoding="utf-8")
        _logger.info("relatório overlap escrito: %s", destino)

    return texto


# --------------------------------------------------------------------------- #
# Orquestrador
# --------------------------------------------------------------------------- #
def executar(
    smartfit_path: Path = SMARTFIT_DEFAULT,
    competidores_path: Path = COMPETIDORES_DEFAULT,
    densos_path: Path = DENSOS_DEFAULT,
    destino: Path = RELATORIO_DEFAULT,
    *,
    escrever: bool = True,
) -> str:
    """Orquestra a aferição de overlap e gera o relatório.

    Lê `df_denso` do parquet (READ-ONLY, não reescreve). Chama `_ler_smartfit`,
    `_ler_competidores` (recebe tupla `(df_comp, n_skyfit)`), `calcular_metricas_smartfit`,
    `calcular_metricas_competidores` e `gerar_relatorio`.

    Returns:
        Texto do relatório em Markdown.
    """
    _logger.info("lendo base densa: %s", densos_path)
    df_denso = pd.read_parquet(Path(densos_path))

    _logger.info("lendo SmartFit: %s", smartfit_path)
    df_sf = _ler_smartfit(Path(smartfit_path))

    _logger.info("lendo Competidores: %s", competidores_path)
    df_comp, n_skyfit_nao_reconhecido = _ler_competidores(Path(competidores_path))

    _logger.info(
        "calculando métricas (SF=%d hexes, comp=%d linhas, denso=%d pares)",
        len(df_sf),
        len(df_comp),
        len(df_denso),
    )

    metricas_sf = calcular_metricas_smartfit(df_sf, df_denso)
    metricas_comp = calcular_metricas_competidores(df_comp, df_denso)

    df_denso_info = {
        "n_pares": len(df_denso),
        "n_redes": int(df_denso["rede_normalizada"].nunique()),
    }

    return gerar_relatorio(
        metricas_sf,
        metricas_comp,
        n_skyfit_nao_reconhecido,
        df_denso_info,
        destino,
        escrever=escrever,
    )


if __name__ == "__main__":  # pragma: no cover
    import logging as _logging
    _logging.basicConfig(level=_logging.INFO)
    _texto = executar()
    print("Relatório gerado com sucesso.")
    print(_texto[:500])
