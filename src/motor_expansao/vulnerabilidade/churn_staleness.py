"""BLK-MA-02: extrator de churn (sinal 3) e staleness (sinal 4) sobre a série de snapshots.

Série de partições `semana=AAAA-SS` -> `status_churn`, `semanas_sem_mudanca`, contadores de
auditoria e flags de maturidade. **O extrator PARA aqui**: `v3`, `v4`, normalização percentil,
pesos, `score_vulnerabilidade`, `n_sinais_disponiveis` e `flag_score_provisorio` são do
**BLK-MA-04** — `_assert_schema_churn` FALHA se qualquer uma dessas colunas aparecer.

O DEFEITO MAIS PROVÁVEL DESTA CAMADA, e como ele é neutralizado:

  **Gap de feed não pode virar churn.** O feed dos independentes (TotalPass/WellHub) é SEMANAL
  (cron da terça, `docs/infra_producao.md`, "Coleta semanal dos agregadores"), e o feed
  `unidades` é **um CSV por rede** — se o
  coletor de uma rede falhar, a fonte continua tendo linhas das outras redes. Por isso o escopo de
  observabilidade é o par **`(fonte, rede)`**, e não a `fonte`: uma semana em que o escopo não foi
  observado simplesmente **não entra no eixo** daquela chave, logo não pode gerar transição
  presente->ausente. A regra vive numa única função (`_observabilidade`) para não haver dois
  lugares para errar.

  Consequência aceita conscientemente: se uma `rede` inteira desaparecer de verdade, lemos "gap" e
  **não** sinalizamos churn. **Falso negativo é preferível a falso positivo** num sinal de peso
  ~0,467 (contrato §8.3).

LIMITAÇÃO REGISTRADA (tratamento é BLK-MA-04): coletor que falha mantém o CSV anterior
(`docs/infra_producao.md:181-182`) -> presença normal (sem falso churn), mas **hash congelado**, e
`semanas_sem_mudanca` sobe sem que o negócio tenha ficado parado. `snapshot_date_ultimo` é o
detector desse modo de falha — sem ela, staleness e coletor quebrado ficam indistinguíveis.

MATURIDADE: `MIN_SEMANAS`/`STALE_SEMANAS` contam **semanas OBSERVADAS**, não de calendário. Na
cadência real, que é SEMANAL para as três fontes, 8 observações são ~8 SEMANAS no caminho
feliz — e mais do que isso na medida em que a curadoria recuse feeds velhos, porque a semana
recusada ocupa slot de calendário sem render observação. Ver
`docs/vulnerabilidade_ma_contrato.md` §6/§12.

GUARDRAILS: READ-ONLY sobre o M1; pacote DISJUNTO (nunca importa `pipelines/m1/`, `dashboard/`,
`api`, `censo_*`, `config.py` raiz ou `normalizar_concorrentes.py`); anti-PII por construção (só
lê as 12 colunas do snapshot, que já não têm PII); fixtures 100% sintéticas nos testes.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from .contrato import (
    CONTRATO_COLUNAS_CHURN,
    CONTRATO_COLUNAS_SNAPSHOT,
    MIN_SEMANAS,
    RE_SEMANA,
    STALE_SEMANAS,
    STATUS_CHURN_VALIDOS,
    VERSAO_CONTRATO_CHURN,
)
from .snapshots import ler_snapshots

# Colunas que este bloco NÃO produz (BLK-MA-04). A trava é executável de propósito: um bloco
# futuro que "adiantar" o score aqui quebra o teste, em vez de vazar escopo em silêncio.
_COLUNAS_DE_SCORE_PROIBIDAS: frozenset[str] = frozenset(
    {"v3", "v4", "score_vulnerabilidade", "n_sinais_disponiveis", "flag_score_provisorio"}
)

_CONTADORES = (
    "n_semanas_serie",
    "n_semanas_presente",
    "n_desaparecimentos",
    "semanas_sem_mudanca",
)


def _frame_churn_vazio() -> pd.DataFrame:
    return pd.DataFrame(
        {col: pd.Series(dtype=dtype) for col, dtype in CONTRATO_COLUNAS_CHURN.items()}
    )


def _montar_serie_longa(snapshots: Sequence[pd.DataFrame]) -> pd.DataFrame:
    """Concatena os snapshots, exige a coluna `semana` ISO e valida a unicidade da chave."""
    frames = [f for f in snapshots if f is not None and not f.empty]
    colunas = list(CONTRATO_COLUNAS_SNAPSHOT.keys()) + ["semana"]
    if not frames:
        return pd.DataFrame({col: pd.Series(dtype="string") for col in colunas})

    longo = pd.concat(frames, ignore_index=True)
    if "semana" not in longo.columns:
        raise ValueError("a serie de snapshots exige a coluna de particao `semana`")
    faltando = [c for c in CONTRATO_COLUNAS_SNAPSHOT if c not in longo.columns]
    if faltando:
        raise ValueError(f"snapshot fora do contrato; colunas ausentes: {faltando}")

    longo = longo[colunas].copy()
    for coluna in ("semana", "fonte", "rede", "chave_snapshot", "chave_origem", "hex_id_res7"):
        longo[coluna] = longo[coluna].astype(str)
    ruins = sorted({s for s in longo["semana"] if not RE_SEMANA.match(s)})
    if ruins:
        raise ValueError(f"semana fora do formato ISO AAAA-SS: {ruins[:5]}")
    dup = int(longo.duplicated(subset=["semana", "fonte", "chave_snapshot"]).sum())
    if dup > 0:
        raise ValueError(f"chave (semana, fonte, chave_snapshot) duplicada: {dup} linha(s)")
    return longo


def _observabilidade(longo: pd.DataFrame) -> dict[tuple[str, str], set[str]]:
    """`{(fonte, rede): {semanas com >= 1 linha}}` — o coração da defesa contra gap virar churn.

    O escopo é o par `(fonte, rede)`, NÃO a `fonte`: o feed `unidades` é um CSV por rede, então o
    sumiço do arquivo de uma rede deixaria a fonte "observada" e marcaria a rede inteira como
    `sumiu_recente` (falso churn em massa no sinal de maior peso).
    """
    obs: dict[tuple[str, str], set[str]] = {}
    if longo.empty:
        return obs
    for (fonte, rede), bloco in longo.groupby(["fonte", "rede"], sort=True):
        obs[(str(fonte), str(rede))] = set(bloco["semana"].astype(str))
    return obs


def _semanas_sem_mudanca(presentes: list[str], hashes: dict[str, str]) -> int:
    """Nº de observações desde a última mudança do `hash_campos_raspados`.

    Conta **observações**, não semanas de calendário, e **reseta para 0** na própria semana da
    mudança. Sem mudança alguma, a referência é a primeira observação.
    """
    semana_mudanca = presentes[0]
    for anterior, atual in zip(presentes, presentes[1:], strict=False):
        if hashes[atual] != hashes[anterior]:
            semana_mudanca = atual
    return sum(1 for w in presentes if w > semana_mudanca)


def _houve_troca_de_chave(por_semana: dict[str, set[str]]) -> bool:
    """O conjunto de `chave_origem` do escopo MUDOU entre semanas consecutivas?

    Duas coisas que deliberadamente **não** caracterizam troca:

    - **uma única semana observada** — sem duas semanas não há "ao longo da série";
    - **mistura estável** — o mesmo conjunto de origens em todas as semanas. O feed TP/WH
      rebaixa a chave POR LINHA, então `{slug, hash_estavel}` na mesma semana é o estado
      NORMAL do escopo, não um evento.

    O que a flag sinaliza ao consumidor é que a identidade da chave pode ter se partido ao
    longo da série — e isso exige variação TEMPORAL.
    """
    if len(por_semana) < 2:
        return False
    conjuntos = [por_semana[semana] for semana in sorted(por_semana)]
    return any(a != b for a, b in zip(conjuntos, conjuntos[1:], strict=False))


def _estado_por_chave(
    longo: pd.DataFrame,
    obs: dict[tuple[str, str], set[str]],
    min_semanas: int,
    stale_semanas: int,
) -> pd.DataFrame:
    """Aplica o algoritmo de churn/staleness por chave `(fonte, chave_snapshot)`."""
    if longo.empty:
        return _frame_churn_vazio()

    # Escopo -> {semana: conjunto de `chave_origem` observados NAQUELA semana}.
    #
    # A formula anterior era `|{chave_origem do escopo}| > 1`, que responde "o escopo tem
    # origens MISTAS" -- pergunta diferente de "a chave TROCOU de politica ao longo da
    # serie", que e' o que o nome da flag promete e o que o consumidor le. No feed TP/WH o
    # rebaixamento de chave ocorre POR LINHA e convive com o `slug` na MESMA semana, entao
    # a versao antiga nascia `True` para todo o universo, toda semana -- um sinal morto.
    # Sonda do QA do BLK-MA-02: 4 semanas, mesmo escopo, uma chave sempre `slug` e outra
    # sempre `hash_estavel`, ZERO troca temporal, e a flag saia `True` para as duas.
    origens_por_semana: dict[tuple[str, str], dict[str, set[str]]] = {}
    for (fonte, rede), bloco in longo.groupby(["fonte", "rede"], sort=True):
        origens_por_semana[(str(fonte), str(rede))] = {
            str(semana): set(sub["chave_origem"].astype(str))
            for semana, sub in bloco.groupby("semana", sort=True)
        }

    linhas: list[dict[str, object]] = []
    for (fonte, chave), bloco in longo.groupby(["fonte", "chave_snapshot"], sort=True):
        fonte = str(fonte)
        chave = str(chave)
        presentes = sorted(set(bloco["semana"].astype(str)))
        redes = {str(r) for r in bloco["rede"]}

        eixo: set[str] = set()
        for rede in redes:
            eixo |= obs.get((fonte, rede), set())
        primeira = presentes[0]
        # Antes da 1a aparicao nao ha evidencia sobre esta chave -> fora do eixo ativo.
        ativo = sorted(w for w in eixo if w >= primeira)
        if not ativo:  # pragma: no cover - `presentes` sempre esta em `eixo` por construcao
            ativo = list(presentes)
        ultima_observada = ativo[-1]

        presentes_set = set(presentes)
        n_desaparecimentos = sum(
            1
            for i in range(1, len(ativo))
            if ativo[i] not in presentes_set and ativo[i - 1] in presentes_set
        )
        n_semanas_serie = len(ativo)

        if ultima_observada not in presentes_set:
            status = "sumiu_recente"
        elif n_desaparecimentos >= 1:
            status = "piscando"
        elif n_semanas_serie < int(min_semanas):
            status = "novo"
        else:
            status = "estavel"

        hashes = {
            str(w): str(h)
            for w, h in zip(
                bloco["semana"].astype(str), bloco["hash_campos_raspados"].astype(str), strict=False
            )
        }
        ultima = bloco[bloco["semana"].astype(str) == presentes[-1]].iloc[0]
        rede_ultima = str(ultima["rede"])

        linhas.append(
            {
                "chave_snapshot": chave,
                "fonte": fonte,
                "rede": rede_ultima,
                "hex_id_res7": str(ultima["hex_id_res7"]),
                "chave_origem": str(ultima["chave_origem"]),
                "status_churn": status,
                "n_semanas_serie": int(n_semanas_serie),
                "n_semanas_presente": int(len(presentes)),
                "n_desaparecimentos": int(n_desaparecimentos),
                "semanas_sem_mudanca": int(_semanas_sem_mudanca(presentes, hashes)),
                "semana_primeira_observacao": primeira,
                "semana_ultima_observacao": presentes[-1],
                "snapshot_date_ultimo": str(ultima["snapshot_date"]),
                # FATOS sem peso (DEC-026), da ÚLTIMA observação — mesmo critério de `rede_ultima`
                # e `snapshot_date_ultimo`. A nota muda entre coletas, então "a última que vimos"
                # é a única leitura defensável; NÃO se agrega a série (média/tendência seria
                # sinal derivado, e sinal derivado precisa de peso e de gate).
                "nota_wellhub": ultima["nota_wellhub"],
                "qtd_avaliacoes_wellhub": ultima["qtd_avaliacoes_wellhub"],
                "flag_serie_imatura": bool(n_semanas_serie < int(min_semanas)),
                "flag_staleness_interpretavel": bool(n_semanas_serie >= int(stale_semanas)),
                "flag_troca_chave_na_serie": _houve_troca_de_chave(
                    origens_por_semana.get((fonte, rede_ultima), {})
                ),
                "versao_contrato": VERSAO_CONTRATO_CHURN,
            }
        )

    out = pd.DataFrame(linhas, columns=list(CONTRATO_COLUNAS_CHURN.keys()))
    for coluna, dtype in CONTRATO_COLUNAS_CHURN.items():
        out[coluna] = out[coluna].astype(dtype)
    return out.sort_values(["fonte", "chave_snapshot"], kind="mergesort").reset_index(drop=True)


def _assert_schema_churn(df: pd.DataFrame) -> None:
    """Falha alto se o frame não é exatamente o contrato `VERSAO_CONTRATO_CHURN`.

    A versão vive na constante: cravada aqui ela já ficou stale no bump `v1` -> `v2`.
    """
    esperado = list(CONTRATO_COLUNAS_CHURN.keys())
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

    ruins = sorted(set(df["status_churn"].astype(str)) - set(STATUS_CHURN_VALIDOS))
    if ruins:
        raise ValueError(f"status_churn fora do contrato: {ruins}")
    for coluna in _CONTADORES:
        if bool((df[coluna].astype("int64") < 0).any()):
            raise ValueError(f"`{coluna}` negativo no frame de churn")
    if bool((df["n_semanas_presente"].astype("int64") < 1).any()):
        raise ValueError("`n_semanas_presente` < 1: chave sem observacao alguma")
    dup = int(df.duplicated(subset=["fonte", "chave_snapshot"]).sum())
    if dup > 0:
        raise ValueError(f"chave (fonte, chave_snapshot) duplicada: {dup} linha(s)")
    versoes = sorted(set(df["versao_contrato"].astype(str)) - {VERSAO_CONTRATO_CHURN})
    if versoes:
        raise ValueError(f"versao_contrato inesperada: {versoes}")


def extrair_churn_staleness(
    base_dir: Path | None = None,
    *,
    snapshots: Sequence[pd.DataFrame] | None = None,
    min_semanas: int = MIN_SEMANAS,
    stale_semanas: int = STALE_SEMANAS,
) -> pd.DataFrame:
    """Série de snapshots -> frame `churn_staleness_v2` (19 colunas), uma linha por chave.

    Exatamente UM entre `base_dir` (lê do disco) e `snapshots` (injetado; molde de
    `revalidar_huff_densa(..., df_join=...)`, `concorrentes_densos.py:427-444`) deve ser dado. Com
    `snapshots` injetado a função é **pura** — é assim que os testes rodam sem I/O.

    `status_churn` é avaliado de cima para baixo, primeiro que casar vence:

    | ordem | estado | condição |
    |---|---|---|
    | 1 | `sumiu_recente` | ausente na última semana OBSERVADA DO ESCOPO |
    | 2 | `piscando` | presente nela, com >= 1 desaparecimento anterior |
    | 3 | `novo` | presente, 0 desaparecimentos e série ainda imatura |
    | 4 | `estavel` | presente, 0 desaparecimentos, série madura |

    `novo` reusa `MIN_SEMANAS` de propósito ("ainda não há evidência suficiente sobre esta
    chave"), o que o torna equivalente a `presente & 0 sumicos & flag_serie_imatura` — sem
    constante mágica nova.
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
        vazio = _frame_churn_vazio()
        _assert_schema_churn(vazio)
        return vazio

    obs = _observabilidade(longo)
    out = _estado_por_chave(longo, obs, int(min_semanas), int(stale_semanas))
    _assert_schema_churn(out)
    return out


__all__ = [
    "extrair_churn_staleness",
    "CONTRATO_COLUNAS_CHURN",
    "VERSAO_CONTRATO_CHURN",
]
