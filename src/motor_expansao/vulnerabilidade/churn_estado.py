"""DEC-064 (D2): churn/staleness como ESTADO materializado e incremental.

**A decisão é do dono**, e a pergunta dele foi a que reorientou tudo: *"não é melhor ter um arquivo
resumo unificando tudo?"*. Era. `extrair_churn_staleness` já produzia esse resumo — 19 colunas, uma
linha por chave, ordem de 2 MB — e **jogava fora toda semana**, recalculando-o do zero a partir da
série inteira. O que restringia a retenção nunca foi disco (2,6 MB por semana), e sim essa leitura:
~70,5 MB de pico de RSS por semana retida, medidos no D5 da DEC-039.

Este módulo é o terceiro caminho de leitura do churn, e os outros DOIS continuam vivos de propósito:

  1. `extrair_churn_staleness(base_dir=...)` — varredura completa do disco.
  2. `extrair_churn_staleness(snapshots=[...])` — PURA, com a série injetada. É a que `alvos_ma.py`
     usa nos dois ramos com recorte por fonte (DEC-039, D9). Substituí-la por estado tornaria o
     recorte decorativo, porque o estado não sabe de que recorte nasceu.
  3. **este** — `estado anterior + semana nova`, sem reler a série.

**A propriedade que se perde, e como ela é reposta.** Varredura é consistente por construção;
incremental acumula erro se um passo for perdido ou se a regra mudar. Por isso `reprocessar` é parte
da decisão, e ele **só existe porque o D1 retém a série inteira** — as duas metades se sustentam
mutuamente: reter tudo sem incremental custa RAM, incremental sem reter tudo é irreversível.

A trava executável dessa reposição é o teste de EQUIVALÊNCIA: aplicar as semanas uma a uma tem de
dar exatamente o mesmo frame que varrer todas de uma vez. Sem ele, "incremental" seria uma promessa.

GUARDRAILS: READ-ONLY sobre o M1; anti-PII por construção (o estado deriva das 13 colunas do
snapshot, que já não têm nome nem coordenada — quem carrega identidade é a ponte do D3, artefato
NOMEADO e gitignored); escreve só em `data/staging/`.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from .contrato import (
    CONTRATO_COLUNAS_CHURN,
    CONTRATO_COLUNAS_CHURN_ESTADO,
    CONTRATO_COLUNAS_OBSERVABILIDADE,
    MIN_SEMANAS,
    RE_SEMANA,
    STALE_SEMANAS,
    VERSAO_CONTRATO_CHURN,
    VERSAO_CONTRATO_CHURN_ESTADO,
    VERSAO_CONTRATO_OBSERVABILIDADE,
)
from .snapshots import SNAPSHOTS_DIR_DEFAULT, ler_snapshots, listar_particoes

_logger = logging.getLogger(__name__)

#: Raiz dos dois artefatos de estado. Árvore IRMÃ da série, pela mesma razão da ponte do D3: a
#: leitura da série declara UM schema e varre a raiz inteira, então parquet de outro schema lá
#: dentro quebraria `ler_snapshots` — que é o insumo de S3/S4, longe da causa.
ESTADO_DIR_DEFAULT = Path("data/staging/churn_estado_concorrentes")
_ARQUIVO_ESTADO = "estado.parquet"
_ARQUIVO_OBSERVABILIDADE = "observabilidade.parquet"


def estado_dir_de(base_dir: Path, estado_dir: Path | None = None) -> Path:
    """Onde o estado mora, dado onde a série mora. `estado_dir` explícito vence.

    DERIVADO do `base_dir` pela lição que a ponte do D3 já custou neste mesmo bloco: com uma
    constante absoluta, todo chamador que aponta a série para outro lugar — cada teste com
    `tmp_path`, um `--base-dir` de rascunho — passaria a escrever em `data/staging/` do processo,
    longe da série que o estado descreve. E o estrago é invisível no `git status`, porque o caminho
    é gitignored.
    """
    if estado_dir is not None:
        return Path(estado_dir)
    return Path(base_dir).parent / ESTADO_DIR_DEFAULT.name


def _inteiro(valor: object) -> int:
    """`to_dict("records")` tipa tudo como `object`; o contrato garante que estes são inteiros.

    Existe para não espalhar `cast`/`type: ignore` pelos acumuladores — o lugar onde um deles
    silenciaria um erro de coluna trocada.
    """
    return int(str(valor))


def _frame_vazio(contrato: dict[str, str]) -> pd.DataFrame:
    return pd.DataFrame({col: pd.Series(dtype=dtype) for col, dtype in contrato.items()})


def estado_vazio() -> pd.DataFrame:
    """Estado sem nenhuma chave — o ponto de partida de uma série que ainda não começou."""
    return _frame_vazio(CONTRATO_COLUNAS_CHURN_ESTADO)


def observabilidade_vazia() -> pd.DataFrame:
    return _frame_vazio(CONTRATO_COLUNAS_OBSERVABILIDADE)


def _coagir(df: pd.DataFrame, contrato: dict[str, str]) -> pd.DataFrame:
    out = df[list(contrato.keys())].reset_index(drop=True)
    for coluna, dtype in contrato.items():
        out[coluna] = out[coluna].astype(dtype)
    return out


def _assert_schema_estado(estado: pd.DataFrame, observabilidade: pd.DataFrame) -> None:
    """Falha alto se um dos dois frames saiu do contrato.

    As versões vivem nas constantes, não neste texto: cravá-las aqui já ficou stale no pacote (o
    comentário de `_assert_schema_churn` registra o caso do bump `v1` -> `v2`).
    """
    for frame, contrato, rotulo in (
        (estado, CONTRATO_COLUNAS_CHURN_ESTADO, "estado"),
        (observabilidade, CONTRATO_COLUNAS_OBSERVABILIDADE, "observabilidade"),
    ):
        esperado = list(contrato.keys())
        if list(frame.columns) != esperado:
            raise ValueError(
                f"{rotulo} fora do contrato: esperado {esperado}, veio {list(frame.columns)}"
            )
    if not estado.empty:
        dup = int(estado.duplicated(subset=["fonte", "chave_snapshot"]).sum())
        if dup:
            raise ValueError(f"estado com chave (fonte, chave_snapshot) duplicada: {dup} linha(s)")
        if bool((estado["n_semanas_presente"].astype("int64") < 1).any()):
            raise ValueError("estado com `n_semanas_presente` < 1: chave sem observacao alguma")
        ruins = sorted({s for s in estado["semana_ultima_observacao"] if not RE_SEMANA.match(str(s))})
        if ruins:
            raise ValueError(f"semana fora do formato ISO AAAA-SS no estado: {ruins[:5]}")
    if not observabilidade.empty:
        dup = int(observabilidade.duplicated(subset=["fonte", "rede", "semana"]).sum())
        if dup:
            raise ValueError(f"observabilidade com (fonte, rede, semana) duplicado: {dup} linha(s)")


def aplicar_semana(
    estado: pd.DataFrame,
    observabilidade: pd.DataFrame,
    snapshot: pd.DataFrame,
    *,
    semana: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """`(estado, observabilidade)` + a semana nova -> os dois frames atualizados. **Função PURA.**

    `snapshot` é o frame de UMA semana (as 13 colunas do contrato; a coluna `semana`, se vier, é
    ignorada em favor do argumento — a semana de destino é decisão da execução, nunca do dado, mesma
    regra do materializador).

    **Idempotente por semana:** reaplicar uma semana já presente na observabilidade daquele escopo é
    no-op. Sem isso, um cron que rodasse duas vezes no mesmo domingo somaria `n_semanas_presente` e
    envelheceria `semanas_sem_mudanca` sem que nada tivesse acontecido no mundo.

    Só avança o relógio POR ESCOPO OBSERVADO. Uma chave cujo escopo `(fonte, rede)` não apareceu
    nesta semana não é tocada — nem `n_desaparecimentos`, nem `semanas_sem_mudanca`. É a mesma
    defesa do `_observabilidade` da varredura, e é o que impede gap de feed de virar churn.
    """
    if not isinstance(semana, str) or not RE_SEMANA.match(semana):
        raise ValueError("aplicar_semana exige `semana` no formato ISO AAAA-SS")

    faltando = [c for c in CONTRATO_COLUNAS_CHURN if c in ("fonte", "rede") and c not in snapshot]
    if faltando:
        raise ValueError(f"snapshot da semana sem colunas de escopo: {faltando}")

    est = estado.copy() if not estado.empty else estado_vazio()
    obs = observabilidade.copy() if not observabilidade.empty else observabilidade_vazia()

    escopos_novos = (
        {(str(f), str(r)) for f, r in zip(snapshot["fonte"], snapshot["rede"], strict=False)}
        if not snapshot.empty
        else set()
    )
    pares_desta_semana = (
        {
            (str(f), str(r))
            for f, r, s in zip(obs["fonte"], obs["rede"], obs["semana"], strict=False)
            if str(s) == semana
        }
        if not obs.empty
        else set()
    )
    escopos_a_aplicar = escopos_novos - pares_desta_semana
    if escopos_novos and not escopos_a_aplicar:
        _logger.info("semana %s ja' aplicada para todos os escopos: no-op", semana)
        return _coagir(est, CONTRATO_COLUNAS_CHURN_ESTADO), _coagir(
            obs, CONTRATO_COLUNAS_OBSERVABILIDADE
        )

    # ---------------- observabilidade: o EIXO ganha a semana nova ----------------
    # `origens` viaja AQUI, no grao do escopo `[achado do claude-review no PR #387]`. Ela e'
    # propriedade do ESCOPO ao longo do tempo, e a varredura compara semanas consecutivas do escopo
    # mesmo nas semanas em que uma dada chave esta' AUSENTE. Guardada por chave, como estava, o
    # incremental so' enxergaria a ultima semana em que aquela chave foi vista, e divergiria da
    # varredura sempre que gap de presenca coincidisse com troca de origem.
    origens_agora: dict[tuple[str, str], set[str]] = {}
    if not snapshot.empty:
        for fonte, rede, origem in zip(
            snapshot["fonte"], snapshot["rede"], snapshot["chave_origem"], strict=False
        ):
            par = (str(fonte), str(rede))
            if par in escopos_a_aplicar:
                origens_agora.setdefault(par, set()).add(str(origem))

    linhas_obs = [
        {
            "fonte": fonte,
            "rede": rede,
            "semana": semana,
            "origens": ",".join(sorted(origens_agora.get((fonte, rede), set()))),
            "versao_contrato": VERSAO_CONTRATO_OBSERVABILIDADE,
        }
        for fonte, rede in sorted(escopos_a_aplicar)
    ]
    if linhas_obs:
        obs = pd.concat(
            [obs, pd.DataFrame(linhas_obs, columns=list(CONTRATO_COLUNAS_OBSERVABILIDADE))],
            ignore_index=True,
        )
    obs = _coagir(obs, CONTRATO_COLUNAS_OBSERVABILIDADE)

    # ---------------- estado: uma linha por (fonte, chave_snapshot) ----------------
    por_chave = {
        (str(f), str(k)): i
        for i, (f, k) in enumerate(zip(est["fonte"], est["chave_snapshot"], strict=False))
    }
    registros: list[dict[str, object]] = est.to_dict("records") if not est.empty else []

    vistas_agora: set[tuple[str, str]] = set()
    if not snapshot.empty:
        for linha in snapshot.to_dict("records"):
            fonte, rede = str(linha["fonte"]), str(linha["rede"])
            if (fonte, rede) not in escopos_a_aplicar:
                continue
            chave = str(linha["chave_snapshot"])
            vistas_agora.add((fonte, chave))
            idx = por_chave.get((fonte, chave))
            if idx is None:
                registros.append(
                    {
                        "fonte": fonte,
                        "chave_snapshot": chave,
                        "rede": rede,
                        "hex_id_res7": str(linha["hex_id_res7"]),
                        "chave_origem": str(linha["chave_origem"]),
                        "semana_primeira_observacao": semana,
                        "semana_ultima_observacao": semana,
                        "snapshot_date_ultimo": str(linha["snapshot_date"]),
                        "hash_ultimo": str(linha["hash_campos_raspados"]),
                        "n_semanas_presente": 1,
                        "n_desaparecimentos": 0,
                        # Reset na PROPRIA semana da mudanca, e a 1a observacao e' a referencia:
                        # mesma semantica de `_semanas_sem_mudanca` na varredura.
                        "semanas_sem_mudanca": 0,
                        "presente_na_ultima_semana_do_eixo": True,
                        "nota_wellhub": linha["nota_wellhub"],
                        "qtd_avaliacoes_wellhub": linha["qtd_avaliacoes_wellhub"],
                        "versao_contrato": VERSAO_CONTRATO_CHURN_ESTADO,
                    }
                )
                continue

            atual = registros[idx]
            hash_novo = str(linha["hash_campos_raspados"])
            mudou = hash_novo != str(atual["hash_ultimo"])
            reapareceu = not bool(atual["presente_na_ultima_semana_do_eixo"])
            atual.update(
                {
                    "rede": rede,
                    "hex_id_res7": str(linha["hex_id_res7"]),
                    "chave_origem": str(linha["chave_origem"]),
                    "semana_ultima_observacao": semana,
                    "snapshot_date_ultimo": str(linha["snapshot_date"]),
                    "hash_ultimo": hash_novo,
                    "n_semanas_presente": _inteiro(atual["n_semanas_presente"]) + 1,
                    "semanas_sem_mudanca": 0 if mudou else _inteiro(atual["semanas_sem_mudanca"]) + 1,
                    "presente_na_ultima_semana_do_eixo": True,
                    "nota_wellhub": linha["nota_wellhub"],
                    "qtd_avaliacoes_wellhub": linha["qtd_avaliacoes_wellhub"],
                    "versao_contrato": VERSAO_CONTRATO_CHURN_ESTADO,
                }
            )
            if reapareceu:
                # Voltou depois de sumir: o desaparecimento ja' foi contado quando ele ocorreu.
                _logger.debug("chave %s reapareceu na semana %s", chave, semana)

    # AUSENTES: só as chaves cujo escopo FOI observado nesta semana entram no eixo.
    for registro in registros:
        par = (str(registro["fonte"]), str(registro["rede"]))
        par_chave = (str(registro["fonte"]), str(registro["chave_snapshot"]))
        if par not in escopos_a_aplicar or par_chave in vistas_agora:
            continue
        if bool(registro["presente_na_ultima_semana_do_eixo"]):
            registro["n_desaparecimentos"] = _inteiro(registro["n_desaparecimentos"]) + 1
        registro["presente_na_ultima_semana_do_eixo"] = False

    est = pd.DataFrame(registros, columns=list(CONTRATO_COLUNAS_CHURN_ESTADO))
    est = _coagir(est, CONTRATO_COLUNAS_CHURN_ESTADO)
    est = est.sort_values(["fonte", "chave_snapshot"], kind="mergesort").reset_index(drop=True)
    _assert_schema_estado(est, obs)
    return est, obs


def churn_do_estado(
    estado: pd.DataFrame,
    observabilidade: pd.DataFrame,
    *,
    min_semanas: int = MIN_SEMANAS,
    stale_semanas: int = STALE_SEMANAS,
) -> pd.DataFrame:
    """Estado + eixo -> o frame `churn_staleness_v2` de 19 colunas. **Função PURA.**

    O schema de saída é o MESMO da varredura, e isso é a exigência central do D2: o consumidor
    (`score.py`, `alvos_ma.py`) não pode saber por qual caminho o churn chegou. `status_churn` é
    reavaliado aqui, de cima para baixo, na ordem do contrato — nunca persistido, porque depende de
    `min_semanas`/`stale_semanas`, que são parâmetro de quem lê.
    """
    if estado.empty:
        vazio = _frame_vazio(CONTRATO_COLUNAS_CHURN)
        return vazio

    eixo: dict[tuple[str, str], list[str]] = {}
    origens_por_escopo: dict[tuple[str, str], dict[str, str]] = {}
    if not observabilidade.empty:
        for fonte, rede, semana, origens in zip(
            observabilidade["fonte"],
            observabilidade["rede"],
            observabilidade["semana"],
            observabilidade["origens"],
            strict=False,
        ):
            par = (str(fonte), str(rede))
            eixo.setdefault(par, []).append(str(semana))
            origens_por_escopo.setdefault(par, {})[str(semana)] = str(origens)

    def _trocou_de_chave(par: tuple[str, str]) -> bool:
        """O conjunto de `chave_origem` do ESCOPO mudou entre semanas consecutivas?

        Mesma pergunta — e mesmas duas exclusões — de `_houve_troca_de_chave` na varredura: uma
        única semana observada não caracteriza troca, e mistura ESTÁVEL (o mesmo conjunto em todas
        as semanas) é o estado NORMAL do feed TP/WH, não um evento. O que a flag sinaliza é
        variação TEMPORAL.
        """
        por_semana = origens_por_escopo.get(par, {})
        if len(por_semana) < 2:
            return False
        conjuntos = [por_semana[s] for s in sorted(por_semana)]
        return any(a != b for a, b in zip(conjuntos, conjuntos[1:], strict=False))

    linhas: list[dict[str, object]] = []
    for registro in estado.to_dict("records"):
        fonte = str(registro["fonte"])
        rede = str(registro["rede"])
        primeira = str(registro["semana_primeira_observacao"])
        # Antes da 1a aparicao nao ha evidencia sobre esta chave -> fora do eixo ATIVO.
        ativo = sorted(w for w in eixo.get((fonte, rede), []) if w >= primeira)
        n_semanas_serie = len(ativo) or int(registro["n_semanas_presente"])
        presente = bool(registro["presente_na_ultima_semana_do_eixo"])
        n_desaparecimentos = int(registro["n_desaparecimentos"])

        if not presente:
            status = "sumiu_recente"
        elif n_desaparecimentos >= 1:
            status = "piscando"
        elif n_semanas_serie < int(min_semanas):
            status = "novo"
        else:
            status = "estavel"

        linhas.append(
            {
                "chave_snapshot": str(registro["chave_snapshot"]),
                "fonte": fonte,
                "rede": rede,
                "hex_id_res7": str(registro["hex_id_res7"]),
                "chave_origem": str(registro["chave_origem"]),
                "status_churn": status,
                "n_semanas_serie": int(n_semanas_serie),
                "n_semanas_presente": int(registro["n_semanas_presente"]),
                "n_desaparecimentos": n_desaparecimentos,
                "semanas_sem_mudanca": int(registro["semanas_sem_mudanca"]),
                "semana_primeira_observacao": primeira,
                "semana_ultima_observacao": str(registro["semana_ultima_observacao"]),
                "snapshot_date_ultimo": str(registro["snapshot_date_ultimo"]),
                "nota_wellhub": registro["nota_wellhub"],
                "qtd_avaliacoes_wellhub": registro["qtd_avaliacoes_wellhub"],
                "flag_serie_imatura": bool(n_semanas_serie < int(min_semanas)),
                "flag_staleness_interpretavel": bool(n_semanas_serie >= int(stale_semanas)),
                "flag_troca_chave_na_serie": _trocou_de_chave((fonte, rede)),
                "versao_contrato": VERSAO_CONTRATO_CHURN,
            }
        )

    out = pd.DataFrame(linhas, columns=list(CONTRATO_COLUNAS_CHURN))
    for coluna, dtype in CONTRATO_COLUNAS_CHURN.items():
        out[coluna] = out[coluna].astype(dtype)
    return out.sort_values(["fonte", "chave_snapshot"], kind="mergesort").reset_index(drop=True)


# --------------------------------------------------------------------------- #
# I/O
# --------------------------------------------------------------------------- #
def ler_estado(estado_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """`(estado, observabilidade)` do disco. Ausência devolve os dois VAZIOS, não erro.

    Ausência é o estado legítimo da primeira execução — e, sob `reprocessar`, do resultado de uma
    reconstrução que ainda não foi gravada.
    """
    raiz = Path(estado_dir)
    caminho_estado = raiz / _ARQUIVO_ESTADO
    caminho_obs = raiz / _ARQUIVO_OBSERVABILIDADE
    if not caminho_estado.is_file() or not caminho_obs.is_file():
        return estado_vazio(), observabilidade_vazia()
    estado = _coagir(pd.read_parquet(caminho_estado), CONTRATO_COLUNAS_CHURN_ESTADO)
    obs = _coagir(pd.read_parquet(caminho_obs), CONTRATO_COLUNAS_OBSERVABILIDADE)
    return estado, obs


def escrever_estado(
    estado: pd.DataFrame, observabilidade: pd.DataFrame, estado_dir: Path
) -> tuple[Path, Path]:
    """Grava os dois parquets. Valida o schema ANTES de tocar disco."""
    _assert_schema_estado(estado, observabilidade)
    raiz = Path(estado_dir)
    raiz.mkdir(parents=True, exist_ok=True)
    caminho_estado = raiz / _ARQUIVO_ESTADO
    caminho_obs = raiz / _ARQUIVO_OBSERVABILIDADE
    estado.to_parquet(caminho_estado, index=False)
    observabilidade.to_parquet(caminho_obs, index=False)
    return caminho_estado, caminho_obs


def reprocessar(
    base_dir: Path = SNAPSHOTS_DIR_DEFAULT,
    *,
    fontes: Sequence[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Reconstrói `(estado, observabilidade)` do zero, semana a semana, a partir da série retida.

    **É o caminho de reposição da consistência**, e só existe porque o D1 (retenção integral)
    mantém a série inteira: incremental acumula erro se um passo for perdido ou se a regra mudar, e
    sem série não haveria de onde reconstruir.

    Lê **uma semana por vez** (recorte de partição), não a série toda — reconstruir carregando tudo
    devolveria exatamente o pico de RSS que a DEC-064 existe para eliminar, na única função em que
    ninguém notaria, porque ela roda raramente.

    A ORDEM é cronológica e vem da LISTAGEM de diretórios (D5), nunca dos dados lidos.
    """
    semanas_por_fonte = listar_particoes(base_dir)
    if fontes is not None:
        pedidas = {str(f) for f in fontes}
        semanas_por_fonte = {f: s for f, s in semanas_por_fonte.items() if f in pedidas}
    todas = sorted({semana for semanas in semanas_por_fonte.values() for semana in semanas})

    estado, obs = estado_vazio(), observabilidade_vazia()
    for semana in todas:
        alvo = sorted(f for f, semanas in semanas_por_fonte.items() if semana in semanas)
        snapshot = ler_snapshots(base_dir, semanas=[semana], fontes=alvo)
        estado, obs = aplicar_semana(estado, obs, snapshot, semana=semana)
    _logger.info(
        "reprocessamento completo: %d semana(s), %d chave(s) no estado", len(todas), len(estado)
    )
    return estado, obs


def atualizar(
    snapshot: pd.DataFrame,
    base_dir: Path = SNAPSHOTS_DIR_DEFAULT,
    *,
    semana: str,
    estado_dir: Path | None = None,
    reprocessar_tudo: bool = False,
) -> dict[str, object]:
    """Ponto de entrada de disco: lê o estado, aplica a semana (ou reconstrói) e grava.

    `reprocessar_tudo=True` IGNORA o estado em disco e reconstrói da série — inclusive a semana
    passada em `snapshot`, se ela já estiver gravada. É deliberado: o reprocessamento tem de ser
    função da SÉRIE, não da série mais um frame em memória, senão ele deixaria de ser reproduzível.
    """
    destino = estado_dir_de(base_dir, estado_dir)
    if reprocessar_tudo:
        estado, obs = reprocessar(base_dir)
        modo = "reprocessado"
    else:
        estado, obs = ler_estado(destino)
        estado, obs = aplicar_semana(estado, obs, snapshot, semana=semana)
        modo = "incremental"
    caminho_estado, _caminho_obs = escrever_estado(estado, obs, destino)
    auditoria: dict[str, object] = {
        "modo": modo,
        "semana": semana,
        "chaves_no_estado": int(len(estado)),
        "linhas_observabilidade": int(len(obs)),
        "destino": str(caminho_estado.parent),
        "versao_contrato": VERSAO_CONTRATO_CHURN_ESTADO,
    }
    _logger.info("estado de churn atualizado: %s", auditoria)
    return auditoria


__all__ = [
    "ESTADO_DIR_DEFAULT",
    "estado_dir_de",
    "estado_vazio",
    "observabilidade_vazia",
    "aplicar_semana",
    "churn_do_estado",
    "ler_estado",
    "escrever_estado",
    "reprocessar",
    "atualizar",
    "CONTRATO_COLUNAS_CHURN_ESTADO",
    "CONTRATO_COLUNAS_OBSERVABILIDADE",
]
