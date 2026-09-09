"""Nota de cobertura censitaria por MUNICIPIO (BLK-JOINUF-01).

POR QUE ESTE MODULO EXISTE. A nota que decide se um hexagono le dado de setor
(`qualidade_join_uf`) e' UM UNICO VALOR POR ESTADO: `fase_a_nacional_completo.py:322-325`
grava um escalar em `df_uf` inteiro. Pior, esse escalar vem de
`mismatch_renda_total_pct = abs(len(basico_uf) - len(renda_uf)) / len(basico_uf) * 100`
(`validar_fase_a_censo2022.py:215-217`) -- uma diferenca de CONTAGEM DE LINHAS entre dois
CSVs do IBGE, que nunca casa um codigo de setor com outro. O proprio repo ja' chamou essa
comparacao de obsoleta em `materializar_setores_censitarios_geo.py:638-639` ("nada dizia
sobre o acerto do join").

Consequencia medida contra o artefato de producao: AM (10,50% de deficit de linhas) e RR
(9,59%) sao as duas unicas UFs classe C do pais, e por isso 100% dos seus hexagonos leem
populacao municipal. Manaus perdia 2.038 dos 2.139 -- exibindo os 2.063.689 habitantes do
municipio inteiro repetidos em cada hexagono -- embora 97,50% dos seus 3.281 setores
tenham renda publicada.

O QUE A NOTA MEDE, COM PRECISAO. E' a fracao de setores do municipio com renda publicada
(`flag_renda_disponivel = renda_per_capita_setor_2022.notna()`,
`materializar_setores_censitarios_geo.py:637`). Isso e' COBERTURA, nao CORRECAO de join:
ela responde "o IBGE publicou renda para os setores deste municipio?" e NAO "a renda foi
colada no setor certo?" -- distincao que este repo pagou caro para aprender na DEC-045
(cobertura cheia com a renda no setor errado). A chave `cod_setor` do artefato GEO, alem
disso, e' recuperada POSICIONALMENTE de um agregado irmao
(`materializar_setores_censitarios_geo.py:196-300`), entao nem a cobertura e' imune ao
mesmo modo de falha.

Por que ela ainda serve, apesar disso: o que ela LIBERA e' a leitura de POPULACAO do setor
(`pop_total_setor_2022`), que vem do Basico com contagem validada exata e mede Pearson
>= 0,99954 contra a malha por chave -- com AM e RR entre as MAIS fieis do pais. A RENDA
exibida nao passa por este gate: desde a DEC-045 ela vem da malha, agregada por chave.

O QUE ELE NAO FAZ. Nao rebaixa ninguem. A nota entra como DISJUNCAO em
`pop_corte.derive_confianca_geografica` -- ver a nota la'. Substituir a nota de UF pela
municipal (em vez de somar) seria regressao liquida de 231.891 hexagonos.

READ-ONLY sobre o M1: nao toca `score_priorizacao`, `hex_score_estrutural` nem nenhum dos
7 artefatos oficiais do §3.
"""

from __future__ import annotations

import glob
import logging
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

#: Mesmos cortes de `materializar_setores_censitarios_geo.py:641`, de proposito: a regua
#: fina nao inventa criterio novo, so' aplica num grao mais fino o que o repo ja' usa.
CORTE_CLASSE_A = 0.95
CORTE_CLASSE_B = 0.90

#: Carimbo de procedencia. Sem ele, "nota ausente" e "nota calculada como C" ficariam
#: indistinguiveis a jusante -- exatamente a familia de defeito do "valor legitimo no
#: lugar errado" que ja' custou a DEC-038 e a DEC-045 a este repo.
FONTE_CALCULADA = "geo_setor_cobertura"
FONTE_AUSENTE = "ausente"
FONTE_PRESERVADA = "preservada"

#: Contrato de `calcular_notas`. `anexar_nota_municipal` trata frame sem estas colunas
#: como ausencia, em vez de estourar KeyError no meio de um pipeline de 4 horas.
COLUNAS_NOTA = (
    "cod_municipio",
    "classe_join_municipio",
    "taxa_match_municipio",
    "n_setores_municipio",
)


def _normalizar_cod_municipio(serie: pd.Series) -> pd.Series:
    """Extrai os 7 digitos do codigo IBGE, a convencao ja usada no repo.

    Sem isso, um `cod_municipio` que chegue como float (`1302603.0`), com espaco ou como
    int casaria ZERO linhas e a promocao viraria no-op SILENCIOSO -- o mesmo modo de falha
    que este bloco existe para consertar. `ibge_censo.py:709` usa este mesmo extract.
    """
    return serie.astype(str).str.extract(r"(\d{7})")[0]


def classificar_taxa(taxa: float) -> str:
    """Taxa de cobertura de renda por setor -> classe {A,B,C}."""
    if taxa >= CORTE_CLASSE_A:
        return "A"
    if taxa >= CORTE_CLASSE_B:
        return "B"
    return "C"


def _frame_vazio() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "cod_municipio": pd.Series(dtype="object"),
            "classe_join_municipio": pd.Series(dtype="object"),
            "taxa_match_municipio": pd.Series(dtype="float64"),
            "n_setores_municipio": pd.Series(dtype="int64"),
        }
    )


def calcular_notas(geo_root: Path) -> pd.DataFrame:
    """Le o artefato GEO e devolve a nota por municipio.

    Colunas: ver `COLUNAS_NOTA`. Devolve frame VAZIO quando o artefato nao esta' no disco
    -- e' o caso do CI e de qualquer maquina sem o 1,17 GB da malha. Frame vazio faz a
    promocao virar no-op, nunca um rebaixamento.
    """
    if not Path(geo_root).exists():
        return _frame_vazio()

    arquivos = glob.glob(str(Path(geo_root) / "uf=*" / "cod_municipio=*" / "*.parquet"))
    if not arquivos:
        return _frame_vazio()

    partes = []
    ilegiveis = 0
    for caminho in arquivos:
        try:
            partes.append(
                pd.read_parquet(caminho, columns=["cod_municipio", "flag_renda_disponivel"])
            )
        except Exception:
            # Particao corrompida/sem a coluna nao pode derrubar a nota do pais inteiro --
            # o custo de pular e' so' nao promover aquele municipio. Mas CONTA, porque
            # pular 5.000 em silencio e pular 1 sao problemas diferentes.
            ilegiveis += 1
    if ilegiveis:
        log.warning(
            "classe_join_municipio: %d de %d particoes ilegiveis, ignoradas",
            ilegiveis,
            len(arquivos),
        )
    if not partes:
        return _frame_vazio()

    setores = pd.concat(partes, ignore_index=True)
    setores["flag_renda_disponivel"] = setores["flag_renda_disponivel"].fillna(False).astype(bool)
    setores["cod_municipio"] = _normalizar_cod_municipio(setores["cod_municipio"])
    setores = setores[setores["cod_municipio"].notna()]
    if setores.empty:
        return _frame_vazio()

    notas = (
        setores.groupby("cod_municipio")["flag_renda_disponivel"]
        .agg(taxa_match_municipio="mean", n_setores_municipio="size")
        .reset_index()
    )
    notas["classe_join_municipio"] = notas["taxa_match_municipio"].map(classificar_taxa)
    return notas[list(COLUNAS_NOTA)]


def _notas_utilizaveis(notas: pd.DataFrame | None) -> bool:
    return (
        notas is not None
        and not notas.empty
        and all(coluna in notas.columns for coluna in COLUNAS_NOTA)
    )


def anexar_nota_municipal(df: pd.DataFrame, notas: pd.DataFrame) -> pd.DataFrame:
    """Anexa `classe_join_municipio` (+ taxa e procedencia) ao frame de hexagonos.

    PRESERVA o que ja' existe quando nao ha nota nova. Isso importa porque
    `calcular_colunas_mercado` LE O PROPRIO OUTPUT (`MERCADO_PATH == OUT_PATH`): uma
    re-execucao numa maquina sem a malha sobrescreveria a nota ja' gravada com NA e
    deixaria o artefato com hexagono `granular` sem nenhuma coluna explicando por que --
    granular por causa do termo `base` de `derive_confianca_geografica`, e inexplicavel
    para quem auditasse depois.
    """
    out = df.copy()
    tem_nota_previa = "classe_join_municipio" in out.columns

    if "cod_municipio" not in out.columns or not _notas_utilizaveis(notas):
        if tem_nota_previa:
            # Preserva; so' carimba a procedencia para o leitor saber que esta rodada nao
            # recalculou nada.
            out["fonte_classe_join_municipio"] = FONTE_PRESERVADA
            return out
        out["classe_join_municipio"] = pd.Series(pd.NA, index=out.index, dtype="object")
        out["taxa_match_municipio"] = pd.Series(pd.NA, index=out.index, dtype="Float64")
        out["fonte_classe_join_municipio"] = FONTE_AUSENTE
        return out

    chave = _normalizar_cod_municipio(out["cod_municipio"])
    notas_indexadas = notas.drop_duplicates(subset=["cod_municipio"]).set_index("cod_municipio")
    out["classe_join_municipio"] = chave.map(notas_indexadas["classe_join_municipio"]).astype(
        "object"
    )
    out["taxa_match_municipio"] = pd.to_numeric(
        chave.map(notas_indexadas["taxa_match_municipio"]), errors="coerce"
    ).astype("Float64")
    out["fonte_classe_join_municipio"] = out["classe_join_municipio"].notna().map(
        {True: FONTE_CALCULADA, False: FONTE_AUSENTE}
    )

    # TRIPWIRE: nota disponivel e casamento ZERO e' drift de formato de chave, nao dado
    # legitimo -- e sem este aviso viraria um no-op silencioso, que e' o defeito que o
    # bloco inteiro existe para consertar.
    casados = int(out["classe_join_municipio"].notna().sum())
    if casados == 0 and len(out):
        log.warning(
            "classe_join_municipio: %d notas disponiveis mas ZERO hexagonos casaram -- "
            "provavel divergencia de formato em cod_municipio",
            len(notas),
        )
    return out
