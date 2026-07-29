"""BLK-MA-03: sinal 1 do score de vulnerabilidade — presença em agregador (TotalPass/WellHub).

Série de partições `semana=AAAA-SS` -> uma linha por `hex_id_res7`, com quantos dos 2 agregadores
cobrem o hex, quantas academias independentes cada agregador tem ali e os **dois relógios de
frescor por fonte**. Este módulo entrega o **insumo BRUTO**: `v1`, pesos, normalização,
`score_vulnerabilidade`, `n_sinais_disponiveis` e `flag_score_provisorio` são do **BLK-MA-04** —
`_assert_schema_presenca_agregador` FALHA se qualquer uma dessas colunas aparecer.

GRANULARIDADE É O HEX, NÃO A ACADEMIA (emenda BLK-MA-03 ao §8.1 do contrato do epic, ratificada
pelo gate humano em 2026-07-29):

  Com o universo NOMEADO (Opção B / D1-B) deferido, não existe identidade cross-provider: a chave
  do snapshot embute a `fonte` (`chave_do_slug`/`chave_hash_estavel` em `contrato.py`) e o nome do
  estabelecimento não é persistido (anti-PII, §11). Logo a MESMA academia em TotalPass e WellHub é
  sempre DUAS chaves distintas, e "quantos agregadores cobrem esta linha" seria constante `1` —
  um sinal sem variância. O hex é a única granularidade computável, e o sufixo `_no_hex` das
  colunas `n_agregadores_no_hex`/`fontes_presentes_no_hex` leva essa ressalva a todo consumidor.

  Viés registrado: num hex denso em que o TotalPass cobre a academia A e o WellHub cobre a B, o
  hex lê "2 agregadores" e ambas recebem a mesma leitura, embora cada uma esteja em um só. O erro
  é sistemático nos hexes densos (que são os hexes-alvo, pela INVERSÃO do §2), mas a sua direção é
  a segura para um funil de aquisição: **falso negativo** (alvo bom que não sobe no ranking),
  nunca falso alvo.

LIMITE ESTRUTURAL, DOCUMENTADO E NÃO É BUG — o ramo "0 agregadores" é inalcançável e VACUOSO:

  TotalPass e WellHub são fontes **só-positivas** (dizem quem ESTÁ presente, nunca quem está
  ausente), e não há no repositório registro externo do universo de academias independentes. Por
  isso `n_agregadores_no_hex` vive em `{1, 2}` e um hex sem observação alguma simplesmente **não
  emite linha**. Isso não custa alvo ao funil: um hex sem nenhuma academia independente observada
  não tem o que pontuar. O caso realmente informativo — "estava no agregador e saiu" — já é
  capturado pelo **sinal 3** (`status_churn == "sumiu_recente"`, peso efetivo ~= 0,467), com peso
  2,3x maior do que este sinal.

OS DOIS DEFEITOS QUE ESTE MÓDULO NEUTRALIZA POR DESENHO:

  **P1 — a redução para a observação mais recente ordena por `semana`, JAMAIS por
  `snapshot_date`.** Coletor que falha mantém o arquivo bruto da execução anterior
  (`docs/infra_producao.md:181-182`), então semanas consecutivas podem repetir — ou até fazer
  REGREDIR — o `snapshot_date`, enquanto a `semana` (derivada da data de EXECUÇÃO, P1 do
  BLK-MA-02) é monótona por construção e tem zero-padding, o que torna a ordem lexicográfica igual
  à cronológica. `snapshot_date` é **medidor de frescor**, nunca chave de ordenação.

  **P2 — REDUZIR primeiro, FILTRAR depois.** Uma chave classificada `independente` na semana 1 e
  como marca conhecida na semana 5 sobreviveria pela observação velha se o filtro viesse antes, e
  entraria como falso alvo de M&A. A classificação MAIS RECENTE vence.

GAP DE FEED (R3): a janela não é encurtada e observação velha não é descartada — uma fonte em gap
não apaga a cobertura que ela já provou. Em troca, o contrato carrega os dois relógios do §6 por
fonte: `semana_ultima_observacao_*` (relógio do PIPELINE) e `snapshot_date_ultimo_*` (relógio do
COLETOR), para o BLK-MA-06 distinguir "a fonte não roda há meses" de "a fonte rodou servindo um
arquivo congelado". A flag formal de staleness é do BLK-MA-06, não deste bloco.

GUARDRAILS: READ-ONLY sobre o M1; pacote DISJUNTO (nunca importa `pipelines/m1/`, `dashboard/`,
`api`, `censo_*`, `config.py` raiz, `normalizar_concorrentes.py` — nem `demanda_revelada`, cuja
categoria residual de rede está REPLICADA em `contrato.py`); anti-PII por construção (só lê
colunas já não-PII do snapshot e só emite agregados por hex); não escreve nada em disco; fixtures
100% sintéticas nos testes.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import h3
import pandas as pd

from .churn_staleness import _montar_serie_longa  # reuso deliberado (CA-11): a validacao e UMA so
from .contrato import (
    CATEGORIA_INDEPENDENTE,
    CONTRATO_COLUNAS_PRESENCA_AGREGADOR,
    FONTES_AGREGADORES,
    H3_RES_CONTRATO,
    RE_SEMANA,
    VERSAO_CONTRATO_PRESENCA_AGREGADOR,
)
from .snapshots import ler_snapshots

# Colunas que este bloco NÃO produz (BLK-MA-04; `v2` é BLK-MA-08). A trava é executável de
# propósito: um bloco futuro que "adiantar" o score aqui quebra o teste, em vez de vazar escopo em
# silêncio.
_COLUNAS_DE_SCORE_PROIBIDAS: frozenset[str] = frozenset(
    {"v1", "v2", "score_vulnerabilidade", "n_sinais_disponiveis", "flag_score_provisorio"}
)


def _frame_presenca_vazio() -> pd.DataFrame:
    return pd.DataFrame(
        {
            col: pd.Series(dtype=dtype)
            for col, dtype in CONTRATO_COLUNAS_PRESENCA_AGREGADOR.items()
        }
    )


def _reduzir_para_observacao_mais_recente(longo: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por `(fonte, chave_snapshot)`: a de **maior `semana`** (P1).

    A ordenação é por `semana` e nunca por `snapshot_date` — ver o bloco P1 no docstring do módulo.
    Não há empate possível: `(semana, fonte, chave_snapshot)` já foi validada como única em
    `_montar_serie_longa`, logo o máximo é uma única linha por grupo.

    A redução existe porque a série retida tem até `RETENCAO_SEMANAS` partições: sem ela a mesma
    academia seria contada uma vez por semana observada (inflando as contagens) e uma academia
    recolocada contaria nos DOIS hexes.
    """
    if longo.empty:
        return longo
    return (
        longo.sort_values(["fonte", "chave_snapshot", "semana"], kind="mergesort")
        .drop_duplicates(subset=["fonte", "chave_snapshot"], keep="last")
        .reset_index(drop=True)
    )


def _filtrar_universo_sinal_1(df: pd.DataFrame) -> pd.DataFrame:
    """Universo do sinal 1: `fonte in FONTES_AGREGADORES` **e** `rede == CATEGORIA_INDEPENDENTE`.

    Chamada **depois** da redução (P2). Exclui sempre a fonte `unidades` (feed de cadeias), mesmo
    que a `rede` venha forjada como independente, e exclui linhas de TP/WH cuja `rede` casou uma
    marca conhecida: "cadeia ausente do WellHub" não é independente frágil.
    """
    if df.empty:
        return df
    manter = df["fonte"].astype(str).isin(set(FONTES_AGREGADORES)) & (
        df["rede"].astype(str) == CATEGORIA_INDEPENDENTE
    )
    return df[manter].reset_index(drop=True)


def _agregar_por_hex(df: pd.DataFrame) -> pd.DataFrame:
    """Frame reduzido+filtrado -> as 10 colunas do contrato, uma linha por `hex_id_res7`."""
    if df.empty:
        return _frame_presenca_vazio()

    linhas: list[dict[str, object]] = []
    for hex_id, bloco in df.groupby("hex_id_res7", sort=True):
        contagem: dict[str, int] = {}
        semana_ultima: dict[str, object] = {}
        snapshot_ultimo: dict[str, object] = {}
        for fonte in FONTES_AGREGADORES:
            recorte = bloco[bloco["fonte"].astype(str) == fonte]
            # `nunique()` conta CHAVES, que é o que o contrato exige — e não depende de a redução
            # do passo anterior estar correta (após ela, equivale à contagem de linhas).
            contagem[fonte] = int(recorte["chave_snapshot"].nunique())
            if contagem[fonte] == 0:
                semana_ultima[fonte] = pd.NA
                snapshot_ultimo[fonte] = pd.NA
                continue
            semana = max(str(s) for s in recorte["semana"])
            semana_ultima[fonte] = semana
            na_semana = recorte[recorte["semana"].astype(str) == semana]
            # ISO compara lexicograficamente = cronologicamente.
            snapshot_ultimo[fonte] = max(str(d) for d in na_semana["snapshot_date"])

        presentes = [f for f in FONTES_AGREGADORES if contagem[f] > 0]
        linha: dict[str, object] = {
            "hex_id_res7": str(hex_id),
            "fontes_presentes_no_hex": ",".join(presentes),
            "n_agregadores_no_hex": int(len(presentes)),
            "versao_contrato": VERSAO_CONTRATO_PRESENCA_AGREGADOR,
        }
        for fonte in FONTES_AGREGADORES:
            linha[f"n_academias_independentes_{fonte}"] = int(contagem[fonte])
            linha[f"semana_ultima_observacao_{fonte}"] = semana_ultima[fonte]
            linha[f"snapshot_date_ultimo_{fonte}"] = snapshot_ultimo[fonte]
        linhas.append(linha)

    out = pd.DataFrame(linhas, columns=list(CONTRATO_COLUNAS_PRESENCA_AGREGADOR.keys()))
    for coluna, dtype in CONTRATO_COLUNAS_PRESENCA_AGREGADOR.items():
        out[coluna] = out[coluna].astype(dtype)
    return out.sort_values("hex_id_res7", kind="mergesort").reset_index(drop=True)


def _assert_schema_presenca_agregador(df: pd.DataFrame) -> None:
    """Falha alto se o frame não é exatamente o contrato `presenca_agregador_v1`."""
    esperado = list(CONTRATO_COLUNAS_PRESENCA_AGREGADOR.keys())
    score = sorted(set(df.columns) & _COLUNAS_DE_SCORE_PROIBIDAS)
    if score:
        raise ValueError(
            f"coluna de SCORE no extrator (escopo do BLK-MA-04, nao deste bloco): {score}"
        )
    extras = set(df.columns) - set(esperado)
    if extras:
        raise ValueError(f"colunas fora do contrato: {sorted(extras)}")
    faltando = set(esperado) - set(df.columns)
    if faltando:
        raise ValueError(f"colunas do contrato ausentes: {sorted(faltando)}")
    if list(df.columns) != esperado:
        raise ValueError(f"ordem de colunas fora do contrato: {list(df.columns)}")
    if df.empty:
        return

    invalidos: list[str] = []
    for hid in df["hex_id_res7"].astype(str).unique():
        if not h3.is_valid_cell(hid) or h3.get_resolution(hid) != H3_RES_CONTRATO:
            invalidos.append(hid)
            if len(invalidos) >= 5:
                break
    if invalidos:
        raise ValueError(f"hex_id_res7 fora de res-{H3_RES_CONTRATO}: amostra {invalidos}")

    dup = int(df.duplicated(subset=["hex_id_res7"]).sum())
    if dup > 0:
        raise ValueError(f"hex_id_res7 duplicado: {dup} linha(s)")

    n_agregadores = df["n_agregadores_no_hex"].astype("int64")
    fora = sorted(set(int(v) for v in n_agregadores) - {1, 2})
    if fora:
        raise ValueError(f"`n_agregadores_no_hex` fora do dominio {{1, 2}}: {fora}")

    contagens: dict[str, pd.Series] = {}
    for fonte in FONTES_AGREGADORES:
        coluna = f"n_academias_independentes_{fonte}"
        contagens[fonte] = df[coluna].astype("int64")
        if bool((contagens[fonte] < 0).any()):
            raise ValueError(f"`{coluna}` negativo no frame de presenca")

    # `fontes_presentes_no_hex` tem de ser EXATAMENTE as fontes com contagem > 0, na ordem
    # canônica, e `n_agregadores_no_hex` o seu comprimento.
    esperado_str = pd.Series(
        [
            ",".join(f for f in FONTES_AGREGADORES if int(contagens[f].iloc[i]) > 0)
            for i in range(len(df))
        ],
        index=df.index,
        dtype="string",
    )
    atual_str = df["fontes_presentes_no_hex"].astype("string").fillna("")
    ruins = int((esperado_str != atual_str).sum())
    if ruins > 0:
        raise ValueError(
            f"`fontes_presentes_no_hex` inconsistente com as contagens por fonte: {ruins} linha(s)"
        )
    n_esperado = esperado_str.map(lambda s: len(s.split(",")) if s else 0).astype("int64")
    if bool((n_esperado != n_agregadores).any()):
        raise ValueError(
            "`n_agregadores_no_hex` inconsistente com `fontes_presentes_no_hex`"
        )

    # Nulabilidade dos dois relógios: nulo SE E SOMENTE SE a contagem daquela fonte for 0.
    for fonte in FONTES_AGREGADORES:
        sem_observacao = contagens[fonte] == 0
        for coluna in (
            f"semana_ultima_observacao_{fonte}",
            f"snapshot_date_ultimo_{fonte}",
        ):
            if bool((df[coluna].isna() != sem_observacao).any()):
                raise ValueError(
                    f"`{coluna}` deve ser nulo se e somente se "
                    f"`n_academias_independentes_{fonte}` for 0"
                )

    versoes = sorted(set(df["versao_contrato"].astype(str)) - {VERSAO_CONTRATO_PRESENCA_AGREGADOR})
    if versoes:
        raise ValueError(f"versao_contrato inesperada: {versoes}")

    for fonte in FONTES_AGREGADORES:
        coluna = f"semana_ultima_observacao_{fonte}"
        ruins_semana = sorted(
            {str(s) for s in df[coluna].dropna() if not RE_SEMANA.match(str(s))}
        )
        if ruins_semana:
            raise ValueError(f"`{coluna}` fora do formato ISO AAAA-SS: {ruins_semana[:5]}")


def extrair_presenca_agregador(
    base_dir: Path | None = None,
    *,
    snapshots: Sequence[pd.DataFrame] | None = None,
) -> pd.DataFrame:
    """Série de snapshots -> frame `presenca_agregador_v1` (10 colunas), uma linha por hex.

    Exatamente UM entre `base_dir` (lê do disco, delegando a `ler_snapshots`) e `snapshots`
    (injetado) deve ser dado — mesmo molde de `extrair_churn_staleness`. Com `snapshots` injetado
    a função é **pura**: é assim que os testes rodam sem I/O.

    O algoritmo tem quatro passos, e a ORDEM dos dois primeiros é o núcleo da correção (P1/P2 no
    docstring do módulo):

    | # | passo | por quê |
    |---|---|---|
    | 1 | série longa validada | `semana` ISO, as 10 colunas do snapshot e unicidade da chave |
    | 2 | **reduzir** cada `(fonte, chave_snapshot)` à observação de maior `semana` | não contar a mesma academia uma vez por semana |
    | 3 | **filtrar** TP/WH x independente, DEPOIS da redução | a classificação mais recente vence |
    | 4 | agregar por `hex_id_res7` | a única granularidade com variância |

    Hex sem nenhuma observação no universo do sinal 1 **não emite linha**, e
    `n_agregadores_no_hex` nunca é `0` — limite estrutural documentado (não bug) no docstring do
    módulo.
    """
    if (base_dir is None) == (snapshots is None):
        raise ValueError("informe exatamente um entre `base_dir` e `snapshots`")

    if snapshots is None:
        serie = ler_snapshots(Path(base_dir))  # type: ignore[arg-type]
        frames: Sequence[pd.DataFrame] = [serie] if not serie.empty else []
    else:
        frames = snapshots

    longo = _montar_serie_longa(frames)
    if longo.empty:
        vazio = _frame_presenca_vazio()
        _assert_schema_presenca_agregador(vazio)
        return vazio

    # `_montar_serie_longa` coage `semana`/`fonte`/`rede`/chaves/`hex_id_res7`, mas nao o
    # `snapshot_date` — que aqui e comparado como texto ISO.
    longo = longo.copy()
    longo["snapshot_date"] = longo["snapshot_date"].astype(str)

    reduzido = _reduzir_para_observacao_mais_recente(longo)
    universo = _filtrar_universo_sinal_1(reduzido)
    if universo.empty:
        vazio = _frame_presenca_vazio()
        _assert_schema_presenca_agregador(vazio)
        return vazio

    out = _agregar_por_hex(universo)
    _assert_schema_presenca_agregador(out)
    return out


__all__ = [
    "extrair_presenca_agregador",
    "CONTRATO_COLUNAS_PRESENCA_AGREGADOR",
    "VERSAO_CONTRATO_PRESENCA_AGREGADOR",
    "FONTES_AGREGADORES",
    "CATEGORIA_INDEPENDENTE",
]
