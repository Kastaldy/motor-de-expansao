"""BLK-MA-02: materializador dos snapshots semanais de concorrentes (insumo de S3/S4).

CSV cru dos coletores -> limpeza de ruído auditável -> chave estável -> `hash_campos_raspados` ->
`data/staging/snapshots_concorrentes/semana=AAAA-SS/fonte=<fonte>/parte-*.parquet` (**gitignored**,
NÃO oficial do M1). É o produtor que faltava: o `run_weekly_90.sh` **sobrescreve** os CSVs a cada
coleta, então toda semana não fotografada é perdida para sempre (`docs/infra_producao.md:136-149`).

**Duas execuções escrevem na MESMA semana ISO `[BLK-MA-21 / DEC-039]`:** o cron de DOMINGO
fotografa `--fontes unidades` (o feed de cadeias) e o cron dos AGREGADORES, na TERÇA, fotografa
`--fontes totalpass wellhub`. As duas cadências são SEMANAIS e terça e domingo caem na mesma
semana ISO (medido), então elas colidem numa partição POR CONSTRUÇÃO. Por isso a partição tem
DUAS chaves: com uma só, a segunda execução da semana apagava a primeira via `delete_matching`.
Ver `escrever_particao_semana`.

Fronteira desta camada: aqui nasce UMA partição de UMA semana. A leitura da série e a derivação de
churn/staleness são de `churn_staleness.py` — o materializador **nunca** olha semanas anteriores
(exceto a poda de retenção e o diagnóstico opcional de estabilidade do `slug`).

DECISÕES DE ENGENHARIA RATIFICADAS NO GATE (2026-07-29) que NÃO podem ser "simplificadas":

  * **A `semana` da partição sai da `data_referencia` da EXECUÇÃO, nunca do `data_coleta` da
    linha.** Coletor que falha mantém o CSV anterior (`docs/infra_producao.md:181-182`); com a
    partição vindo da linha, uma execução de hoje reescreveria uma semana passada e, com
    `existing_data_behavior="delete_matching"`, **APAGARIA** aquele histórico. `snapshot_date`
    continua por linha e vira o medidor de frescor.
  * **A chave de churn é própria** (`chave_hash_estavel`/`chave_do_slug` do `contrato`), não o
    `concorrente_id` de produção — cuja coordenada `:.6f` (~11 cm) produziria falso churn no sinal
    de maior peso. Colisões de chave são **COLAPSADAS**, nunca desambiguadas por ordinal.

GUARDRAILS (CLAUDE.md §1/§2/§5; DEC-012; DEC-013):
  - READ-ONLY sobre o M1: nada aqui lê ou escreve `score_priorizacao`, `hex_score_estrutural`,
    pesos, carteira, plano ou artefato oficial. `concorrentes_mapeados.parquet` sequer é aberto.
  - Pacote DISJUNTO: NUNCA importa `pipelines/m1/`, `dashboard/`, `api`, `censo_*`, `config.py`
    raiz nem `pipelines/normalizar_concorrentes.py` (`_DENY_CRITICO` do loop_guard — molde de
    leitura apenas; a fórmula do `concorrente_id` foi REPLICADA em `contrato.py`).
  - Anti-PII (DEC-012 / contrato §11): `nome`/coordenadas/endereço/CEP existem **só em memória**;
    o Parquet leva apenas as 13 colunas do contrato. A auditoria da limpeza carrega **só
    contagens**, jamais o texto ofensor. Testes com fixtures 100% sintéticas.
  - CSV do projeto: `sep=";"`, `encoding="utf-8-sig"`. Staging sempre em Parquet.

API h3 = v4 (`latlng_to_cell`).
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import shutil
import tempfile
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import TypedDict

import h3
import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds

from motor_expansao.demanda_revelada.classificacao_rede_menor import classificar_rede

from .contrato import (
    CHAVE_ORIGEM_VALIDAS,
    COLUNAS_PARTICAO,
    COLUNAS_PII_PROIBIDAS,
    COLUNAS_SNAPSHOT_NULAVEIS,
    CONTRATO_COLUNAS_PONTE,
    CONTRATO_COLUNAS_SNAPSHOT,
    FONTES_VALIDAS,
    H3_RES_CONTRATO,
    LIMIAR_SLUG_ESTAVEL,
    MIN_UNIDADES_GUARDA_REDE,
    MIN_UNIDADES_GUARDA_TOTAL,
    MOTIVOS_DESCARTE,
    NOTA_WELLHUB_MAX,
    NOTA_WELLHUB_MIN,
    RE_SEMANA,
    RE_UUID,
    RETENCAO_SEMANAS,
    RETENCAO_TUDO,
    TOLERANCIA_QUEDA_REDE_PCT,
    TOLERANCIA_QUEDA_TOTAL_PCT,
    VERSAO_CONTRATO_SNAPSHOT,
    VERSAO_CONTRATO_SNAPSHOT_V4,
    chave_do_slug,
    chave_hash_estavel,
    chave_hash_estavel_v4,
    concorrente_id_producao,
    coord_no_bbox_uf,
    coord_no_envelope,
    derivar_semana_iso,
    entrada_tecnologia_totalpass,
    hash_campos_raspados,
    normalizar_texto,
    parse_data_coleta,
    rotulo_de_teste,
)

_logger = logging.getLogger(__name__)

# Caminhos default IGUAIS aos de `demanda_revelada/concorrentes_densos.py:57-59` (nunca hardcodar
# noutro lugar: os diretórios são sempre parâmetro).
DIR_TOTALPASS_DEFAULT = Path("concorrentes/totalpass/csvs")
DIR_WELLHUB_DEFAULT = Path("concorrentes/wellhub/csvs")
DIR_UNIDADES_DEFAULT = Path("concorrentes/Unidades")
SNAPSHOTS_DIR_DEFAULT = Path("data/staging/snapshots_concorrentes")
# Ponte de identidade (DEC-064, D3). Árvore IRMÃ da série, nunca dentro dela: `ler_snapshots` varre
# `SNAPSHOTS_DIR_DEFAULT` inteiro com o schema do snapshot, e um parquet de outro schema lá dentro
# quebraria a leitura da série — que é o insumo de S3/S4.
PONTE_DIR_DEFAULT = Path("data/staging/ponte_identidade_concorrentes")

# Prefixo dos arquivos de `Unidades/`: `unidades_<rede>.csv` -> rede = stem sem esse prefixo.
_PREFIXO_UNIDADES = "unidades_"

# Superconjunto de colunas do frame de TRABALHO (em memória; carrega PII que morre na fronteira
# do `montar_snapshot`). `nome_unidade` entra porque é o campo hasheado do feed `unidades`.
_COLUNAS_TRABALHO: tuple[str, ...] = (
    "fonte",
    "rede",
    "slug",
    "nome",
    "nome_unidade",
    "latitude",
    "longitude",
    "cidade",
    "uf",
    "cep",
    "endereco_formatado",
    "modalidades",
    "atividades",
    # Rating do WellHub (BLK-MA-08). NAO e PII (DEC-024) e, ao contrario das duas de cima,
    # SOBREVIVE a fronteira: vira coluna-fato do snapshot (DEC-026). Ausente no feed TotalPass
    # e no `unidades` -> `montar_snapshot` preenche com NA.
    "nota_wellhub",
    "qtd_avaliacoes_wellhub",
    "data_coleta",
)

_POLITICAS_CHAVE: frozenset[str] = frozenset({"auto", "hash_estavel"})
_RE_DIR_SEMANA = re.compile(r"^semana=(\d{4}-\d{2})$")
_RE_DIR_FONTE = re.compile(r"^fonte=(.+)$")


# --------------------------------------------------------------------------- #
# 1. Leitura dos feeds (I/O; PII só em memória)
# --------------------------------------------------------------------------- #
def _ler_csv_bruto(caminho: Path) -> pd.DataFrame:
    """Lê um CSV do projeto (`sep=";"`, `utf-8-sig`) inteiramente como texto.

    `dtype=str` + `keep_default_na=False` deixam a normalização 100% nas mãos do `contrato`
    (célula vazia vira `""`, nunca `NaN`), o que torna o hash determinístico.
    """
    try:
        return pd.read_csv(caminho, sep=";", encoding="utf-8-sig", dtype=str, keep_default_na=False)
    except pd.errors.EmptyDataError:  # pragma: no cover - CSV totalmente vazio
        return pd.DataFrame()


def _frame_trabalho_vazio() -> pd.DataFrame:
    return pd.DataFrame({col: pd.Series(dtype="object") for col in _COLUNAS_TRABALHO})


def _preparar_parte(df: pd.DataFrame, fonte: str, rede_do_arquivo: str | None) -> pd.DataFrame:
    """Reindexa um CSV lido para o superconjunto de trabalho e resolve a coluna `rede`."""
    out = df.copy()
    if fonte == "unidades":
        # O feed de cadeias emite `nome_unidade`; espelhamos em `nome` para a chave/classificação.
        if "nome_unidade" not in out.columns:
            out["nome_unidade"] = ""
        out["nome"] = out["nome_unidade"]
        out["rede"] = rede_do_arquivo or ""
    else:
        if "nome" not in out.columns:
            out["nome"] = ""
        out["nome_unidade"] = ""
        out["rede"] = [classificar_rede(n) for n in out["nome"]]
    out["fonte"] = fonte
    for col in _COLUNAS_TRABALHO:
        if col not in out.columns:
            out[col] = ""
    return out[list(_COLUNAS_TRABALHO)].astype(object)


def ler_feeds(
    dir_totalpass: Path = DIR_TOTALPASS_DEFAULT,
    dir_wellhub: Path = DIR_WELLHUB_DEFAULT,
    dir_unidades: Path = DIR_UNIDADES_DEFAULT,
    *,
    fontes: Sequence[str] | None = None,
) -> pd.DataFrame:
    """Lê as 3 pastas de CSVs -> frame LONGO de trabalho (PII **só em memória**, nada persistido).

    `rede` = stem sem o prefixo `unidades_` para o feed de cadeias; `classificar_rede(nome)` para
    TotalPass/WellHub (espelha `concorrentes_densos.py:138`/`:153`). Colunas ausentes no arquivo
    entram como `""`. Diretório inexistente contribui 0 linhas e **nunca** levanta.

    `fontes` restringe QUAIS feeds entram (default: todos). Existe por causa de um descasamento de
    JANELA, não de gosto (BLK-MA-06): o runner de domingo recoleta só o feed `unidades`; WellHub e
    TotalPass são recoletados pelo cron dos agregadores, na TERÇA
    (`docs/infra_producao.md`, "Coleta semanal dos agregadores"). Fotografar um feed que não foi
    recoletado produz
    `hash_campos_raspados` idêntico semana após semana -> `semanas_sem_mudanca` cresce sozinho ->
    o **S4 marcaria o universo inteiro de agregador como "parado"**, que é justamente o sinal de
    vulnerabilidade. Passar `fontes` explicitamente deixa esse recorte auditável no log e na
    auditoria, em vez de escondido num diretório apontado para lugar nenhum.
    """
    ativas = FONTES_VALIDAS if fontes is None else frozenset(str(f) for f in fontes)
    desconhecidas = sorted(ativas - FONTES_VALIDAS)
    if desconhecidas:
        raise ValueError(
            f"fonte fora do contrato: {desconhecidas}; aceitas: {sorted(FONTES_VALIDAS)}"
        )
    if not ativas:
        raise ValueError("`fontes` vazio: nao ha o que ler")
    partes: list[pd.DataFrame] = []
    if "totalpass" in ativas:
        for caminho in sorted(Path(dir_totalpass).glob("*.csv")):
            partes.append(_preparar_parte(_ler_csv_bruto(caminho), "totalpass", None))
    if "wellhub" in ativas:
        for caminho in sorted(Path(dir_wellhub).glob("*.csv")):
            partes.append(_preparar_parte(_ler_csv_bruto(caminho), "wellhub", None))
    if "unidades" in ativas:
        for caminho in sorted(Path(dir_unidades).glob("*.csv")):
            stem = caminho.stem
            rede = stem[len(_PREFIXO_UNIDADES) :] if stem.startswith(_PREFIXO_UNIDADES) else stem
            partes.append(_preparar_parte(_ler_csv_bruto(caminho), "unidades", rede))

    partes = [p for p in partes if not p.empty]
    if not partes:
        return _frame_trabalho_vazio()
    return pd.concat(partes, ignore_index=True)


# --------------------------------------------------------------------------- #
# 2. Limpeza de ruído (PURA; auditoria só com contagens)
# --------------------------------------------------------------------------- #
def _motivo_descarte(
    fonte: object, nome: object, lat: object, lng: object, uf: object, data_coleta: object
) -> str | None:
    """Motivo de descarte da linha, ou `None` se ela sobrevive.

    **Determinística no conteúdo da LINHA, jamais do lote.** Se dependesse do lote (percentil,
    mediana, contagem), uma linha limpa numa semana e descartada na outra viraria falso churn.
    Ordem FIXA: a primeira regra que casar decide (motivo singular).
    """
    try:
        parse_data_coleta(data_coleta, fonte=str(fonte))
    except ValueError:
        return "data_coleta_invalida"

    try:
        la = float(lat)  # type: ignore[arg-type]
        ln = float(lng)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        la = ln = float("nan")
    if la == 0.0 and ln == 0.0:
        return "coord_zero_zero"
    if not coord_no_envelope(lat, lng):
        return "coord_fora_envelope_brasil"
    if not coord_no_bbox_uf(lat, lng, uf):
        return "coord_fora_bbox_uf"
    if rotulo_de_teste(nome):
        return "rotulo_de_teste"
    if str(fonte) in ("totalpass", "wellhub") and entrada_tecnologia_totalpass(nome):
        return "entrada_tecnologia_totalpass"
    return None


def limpar_ruido(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object]]:
    """Remove as linhas que não são academias reais e devolve a auditoria **só com contagens**.

    Contrato §6: coords `0;0`, coords fora do Brasil ou grosseiramente inconsistentes com a `uf`,
    rótulos de teste e entradas de tecnologia/onboarding do TotalPass distorceriam churn e
    universo. `data_coleta` inválido ganha o seu próprio balde em vez de derrubar o lote.

    Anti-PII: a auditoria devolve **apenas inteiros** — nunca o nome/endereço ofensor.
    """
    auditoria: dict[str, object] = {
        "linhas_lidas": int(len(df)),
        "linhas_mantidas": 0,
        "descartes": {motivo: 0 for motivo in MOTIVOS_DESCARTE},
    }
    if df.empty:
        return df.copy(), auditoria

    descartes: dict[str, int] = auditoria["descartes"]  # type: ignore[assignment]
    manter: list[bool] = []
    for fonte, nome, lat, lng, uf, data_coleta in zip(
        df["fonte"],
        df["nome"],
        df["latitude"],
        df["longitude"],
        df["uf"],
        df["data_coleta"],
        strict=False,
    ):
        motivo = _motivo_descarte(fonte, nome, lat, lng, uf, data_coleta)
        if motivo is None:
            manter.append(True)
        else:
            manter.append(False)
            descartes[motivo] += 1

    limpo = df.loc[pd.Series(manter, index=df.index)].reset_index(drop=True)
    auditoria["linhas_mantidas"] = int(len(limpo))
    return limpo, auditoria


# --------------------------------------------------------------------------- #
# 3. Impressão digital dos campos raspados (PURA)
# --------------------------------------------------------------------------- #
def calcular_hash_campos_raspados(df: pd.DataFrame) -> pd.DataFrame:
    """Acrescenta `hash_campos_raspados` por linha, com o conjunto de campos da própria `fonte`.

    `data_coleta`, `slug` e a taxonomia (`atividades`/`modalidades`) **jamais** entram no hash
    (`CAMPOS_NUNCA_HASHEADOS`): com a data dentro, `semanas_sem_mudanca` nunca sairia de 0 e a
    staleness morreria; com o slug dentro, a rotação de UUID viraria falsa mudança de negócio; com
    a taxonomia dentro, uma renomeação de rótulo pela FONTE viraria "cadastro alterado" para o
    universo inteiro (medido no WellHub em 2026-08-07: 99,1% — emenda BLK-MA-11 / DEC-025).
    """
    out = df.copy()
    valores = [
        hash_campos_raspados(registro, str(registro.get("fonte", "")))
        for registro in out.to_dict("records")
    ]
    out["hash_campos_raspados"] = pd.Series(valores, index=out.index, dtype="object")
    return out


# --------------------------------------------------------------------------- #
# 4. Chave do snapshot (PURA)
# --------------------------------------------------------------------------- #
def _to_cell(lat: object, lng: object) -> str:
    """`(lat,lng)` -> hex res-7 (h3 v4); `""` se inválida (o `_assert_schema` falha alto depois)."""
    try:
        return h3.latlng_to_cell(float(lat), float(lng), H3_RES_CONTRATO)  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return ""


def derivar_chave(
    df: pd.DataFrame,
    *,
    taxa_slug_persistente: float | None = None,
    limiar: float = LIMIAR_SLUG_ESTAVEL,
    politica: str = "auto",
) -> pd.DataFrame:
    """Deriva `hex_id_res7`, `chave_snapshot`, `chave_origem` e `concorrente_id`.

    Rebaixamento do `slug` para `hash_estavel` em duas camadas:

    * **por linha** (sempre ativo, só informação local da semana): slug ausente, ou slug duplicado
      dentro do próprio snapshot;
    * **global** (opcional): só quando o chamador **injeta** `taxa_slug_persistente`. Com o default
      `None` o materializador **nunca** lê semanas anteriores — se ele recalculasse a persistência
      a cada semana, a chave mudaria no instante em que a taxa cruzasse o limiar e re-chavearia o
      universo inteiro, produzindo churn sintético em massa.

    `taxa_slug_persistente = NaN` (menos de 2 semanas observadas) **não** rebaixa.
    """
    if politica not in _POLITICAS_CHAVE:
        raise ValueError(f"politica de chave invalida; aceitas: {sorted(_POLITICAS_CHAVE)}")

    out = df.copy()
    if out.empty:
        for col in ("hex_id_res7", "chave_snapshot", "chave_origem", "concorrente_id"):
            out[col] = pd.Series(dtype="object")
        return out

    out["hex_id_res7"] = [
        _to_cell(la, ln) for la, ln in zip(out["latitude"], out["longitude"], strict=False)
    ]
    if "slug" not in out.columns:
        out["slug"] = ""
    slug_norm = [normalizar_texto(s) for s in out["slug"]]
    out["_slug_norm"] = slug_norm

    forcar_hash = politica == "hash_estavel"
    if not forcar_hash and taxa_slug_persistente is not None:
        taxa = float(taxa_slug_persistente)
        forcar_hash = taxa == taxa and taxa < float(limiar)

    dup = out.duplicated(subset=["fonte", "_slug_norm"], keep=False)
    chaves: list[str] = []
    origens: list[str] = []
    for i, (fonte, rede, nome, hex_id, sl) in enumerate(
        zip(out["fonte"], out["rede"], out["nome"], out["hex_id_res7"], slug_norm, strict=False)
    ):
        usa_slug = (not forcar_hash) and bool(sl) and not bool(dup.iloc[i])
        if usa_slug:
            chaves.append(chave_do_slug(fonte, sl))
            origens.append("slug")
        else:
            chaves.append(chave_hash_estavel(fonte, rede, nome, hex_id))
            origens.append("hash_estavel")
    out["chave_snapshot"] = chaves
    out["chave_origem"] = origens
    out["concorrente_id"] = [
        concorrente_id_producao(rede, nome, la, ln)
        for rede, nome, la, ln in zip(
            out["rede"], out["nome"], out["latitude"], out["longitude"], strict=False
        )
    ]
    return out.drop(columns=["_slug_norm"])


def avaliar_estabilidade_slug(snapshots: Sequence[pd.DataFrame]) -> dict[str, float]:
    """Diagnóstico PURO da estabilidade do `slug` entre semanas (contrato §6, caveat do UUID).

    **Não decide nada sozinha**: quem injeta `taxa_slug_persistente` em `derivar_chave` é o
    chamador. Retorna 6 métricas:

    * `taxa_slug_presente` — fração das linhas com `slug` não vazio;
    * `taxa_slug_unico_no_snapshot` — entre as linhas com slug, fração NÃO duplicada em
      `(semana, fonte, slug)`;
    * `taxa_slug_persistente` — micro-média `Σ|slugs(w_i) ∩ slugs(w_i+1)| / Σ|slugs(w_i)|` sobre
      pares de semanas **consecutivas OBSERVADAS da mesma fonte** (nunca semanas de calendário);
    * `taxa_slug_com_uuid` — entre as linhas com slug, fração cujo slug carrega UUID;
    * `n_semanas_avaliadas`, `n_pares_consecutivos` — auditoria.

    Sem par consecutivo algum, `taxa_slug_persistente` é `NaN` (e NÃO rebaixa chave nenhuma).
    """
    frames = [f for f in snapshots if f is not None and not f.empty]
    vazio = {
        "taxa_slug_presente": float("nan"),
        "taxa_slug_unico_no_snapshot": float("nan"),
        "taxa_slug_persistente": float("nan"),
        "taxa_slug_com_uuid": float("nan"),
        "n_semanas_avaliadas": 0.0,
        "n_pares_consecutivos": 0.0,
    }
    if not frames:
        return vazio

    longo = pd.concat(frames, ignore_index=True)
    if "semana" not in longo.columns:
        raise ValueError("avaliar_estabilidade_slug exige a coluna de particao `semana`")
    if "slug" not in longo.columns:
        longo["slug"] = ""
    longo["_slug_norm"] = [normalizar_texto(s) for s in longo["slug"]]
    longo["semana"] = longo["semana"].astype(str)
    longo["fonte"] = longo["fonte"].astype(str)

    n_total = int(len(longo))
    com_slug = longo[longo["_slug_norm"] != ""]
    n_slug = int(len(com_slug))

    taxa_presente = float(n_slug / n_total) if n_total else float("nan")
    if n_slug:
        dup = com_slug.duplicated(subset=["semana", "fonte", "_slug_norm"], keep=False)
        taxa_unico = float((~dup).sum() / n_slug)
        # O UUID é procurado no slug CRU: `normalizar_texto` troca `-` por espaço e destruiria o
        # formato canônico do UUID, zerando a métrica em silêncio.
        taxa_uuid = float(sum(1 for s in com_slug["slug"] if RE_UUID.search(str(s))) / n_slug)
    else:
        taxa_unico = float("nan")
        taxa_uuid = float("nan")

    numerador = 0
    denominador = 0
    n_pares = 0
    for _fonte, bloco in com_slug.groupby("fonte", sort=True):
        semanas = sorted(set(bloco["semana"]))
        conjuntos = {w: set(bloco.loc[bloco["semana"] == w, "_slug_norm"]) for w in semanas}
        for anterior, seguinte in zip(semanas, semanas[1:], strict=False):
            n_pares += 1
            numerador += len(conjuntos[anterior] & conjuntos[seguinte])
            denominador += len(conjuntos[anterior])
    taxa_persistente = float(numerador / denominador) if denominador else float("nan")

    return {
        "taxa_slug_presente": taxa_presente,
        "taxa_slug_unico_no_snapshot": taxa_unico,
        "taxa_slug_persistente": taxa_persistente,
        "taxa_slug_com_uuid": taxa_uuid,
        "n_semanas_avaliadas": float(len(set(longo["semana"]))),
        "n_pares_consecutivos": float(n_pares),
    }


# --------------------------------------------------------------------------- #
# 5. Montagem do snapshot (PURA) — aqui a PII morre
# --------------------------------------------------------------------------- #
def _coagir_rating(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Coage as duas colunas-fato de rating. **NUNCA levanta** — devolve quantas ficaram ilegíveis.

    Por que não pode levantar: `montar_snapshot` roda ANTES de `escrever_particao_semana`, e o
    `run_weekly_90.sh` sobrescreve os CSVs a cada coleta. Uma exceção aqui não perde uma linha:
    perde a **semana inteira**, para sempre, por causa de uma célula. Direção segura é degradar a
    célula para "não lido" — que é um dos três estados do contrato — e **contar**, para que a
    degradação apareça na auditoria em vez de virar silêncio.

    Dois modos de falha, os dois medidos como reais:

    1. **Contagem não-inteira.** `pd.to_numeric("1.262")` devolve `1.262` (float), e o
       `.astype("Int64")` seguinte levanta `TypeError: cannot safely cast non-equivalent`. É a
       forma que a contagem assume se o WellHub trocar o locale da UI para pt-BR — e contagem de
       4 dígitos existe no universo (a DEC-024 cita "4,73 com 1.262"). Medido em 2026-08-10: o
       consolidado atual traz as 45.527 contagens como inteiro puro, então isto é **latente**,
       não ativo.
    2. **Valor fora do domínio.** Nota fora de `[NOTA_WELLHUB_MIN, NOTA_WELLHUB_MAX]` ou contagem
       negativa. `481` é `4.81` sem o separador decimal; `0.0` é o default de um parser que não
       achou o campo. Antes estes valores só eram vistos pelo `_assert_schema_snapshot`, que
       LEVANTA — mesma consequência do item 1, e pelo mesmo caminho.
    3. **Par fora dos três estados.** A DEC-024 (D-3) define TRÊS: `4.81`/`105` (tem nota), `NA`/`0`
       (sem avaliações) e `NA`/`NA` (parser quebrou). Qualquer outro par — `NA`/`105` (nota
       ilegível com contagem boa), `4.81`/`0` (nota sem avaliação que a sustente), `4.81`/`NA` —
       é normalizado para `NA`/`NA`, porque "não lido" é o que de fato aconteceu. Deixar passar
       faria uma quebra de parser entrar no funil disfarçada de academia sem avaliação.

    A ordem importa: o domínio primeiro, o par depois. É ela que faz `0.0`/`0` — extrator quebrado
    sobre uma unidade sem avaliações — cair no estado CERTO (`NA`/`0`, "sem avaliações") em vez de
    virar "não lido".
    """
    nota = pd.to_numeric(df["nota_wellhub"], errors="coerce")
    qtd = pd.to_numeric(df["qtd_avaliacoes_wellhub"], errors="coerce")

    # (1) Domínio, por coluna. Um valor impossível é um valor NÃO LIDO — não um motivo para abortar.
    fora_dominio = nota.notna() & ((nota < NOTA_WELLHUB_MIN) | (nota > NOTA_WELLHUB_MAX))
    nota = nota.where(~fora_dominio)

    # `Int64` só aceita valor integral; não-integral vira "não lido" em vez de abortar a semana.
    nao_inteiro = qtd.notna() & (qtd != qtd.round())
    negativa = qtd.notna() & (qtd < 0)
    qtd = qtd.where(~(nao_inteiro | negativa))

    # (2) Par: os três estados da DEC-024 são os ÚNICOS válidos; todo o resto vira "não lido".
    tem_nota = nota.notna() & qtd.notna() & (qtd > 0)
    sem_avaliacoes = nota.isna() & qtd.notna() & (qtd == 0)
    nao_lido = nota.isna() & qtd.isna()
    par_invalido = ~(tem_nota | sem_avaliacoes | nao_lido)
    nota = nota.where(~par_invalido)
    qtd = qtd.where(~par_invalido)

    out = df.copy()
    out["nota_wellhub"] = nota.astype("Float64")
    out["qtd_avaliacoes_wellhub"] = qtd.round().astype("Int64")
    # Conta LINHAS degradadas, não ocorrências: uma nota `9.9` com contagem boa aciona o domínio e
    # o par, e vale 1 — senão a auditoria inflaria e ninguém saberia quantas células se perderam.
    degradadas = fora_dominio | nao_inteiro | negativa | par_invalido
    return out, int(degradadas.sum())


def coordenadas_por_chave(
    dir_totalpass: Path = DIR_TOTALPASS_DEFAULT,
    dir_wellhub: Path = DIR_WELLHUB_DEFAULT,
    dir_unidades: Path = DIR_UNIDADES_DEFAULT,
    *,
    fontes: Sequence[str] | None = None,
) -> pd.DataFrame:
    """Feed cru -> `(fonte, chave_snapshot, nome, lat, lng, rede)`, **em memória, sem tocar disco**.

    É a ponte que o BLK-MA-14 (DEC-029, rota B) abriu para o `v6` por academia: a pressão precisa da
    coordenada da unidade, e ela existe AQUI, antes de `montar_snapshot` projetar as 12 colunas e
    matar a PII. Nada é gravado; quem chama passa o resultado direto para
    `calcular_pressao_por_academia`, que devolve só o agregado.

    **Por que isto NÃO fura o anti-PII (§11/DEC-012).** A regra é sobre o que a camada PERSISTE e
    sobre o que cruza a fronteira de saída — não sobre o que ela lê. Este módulo já lia essas
    coordenadas (é delas que sai o `hex_id_res7`); a função só as expõe ao chamador dentro do
    processo. A trava de saída continua onde sempre esteve: no schema do frame de pressão.

    **A chave bate com a do snapshot persistido** porque `derivar_chave` é determinística e, no
    default (`taxa_slug_persistente=None`), **não lê semanas anteriores** — o mesmo feed produz a
    mesma chave, hoje e na semana que vem. É essa propriedade que dispensa o bump de série que a
    rota A exigiria.

    Ressalva herdada: a leitura é do feed ATUAL, não da série. Uma academia que sumiu do CSV desde a
    última coleta não aparece aqui e fica sem pressão — o que é correto (não há de onde medir) e é a
    mesma premissa que o parquet de pontos de concorrentes já carrega.
    """
    bruto = ler_feeds(dir_totalpass, dir_wellhub, dir_unidades, fontes=fontes)
    if bruto.empty:
        return pd.DataFrame(
            {
                "fonte": pd.Series(dtype="string"),
                "chave_snapshot": pd.Series(dtype="string"),
                "nome": pd.Series(dtype="string"),
                "lat": pd.Series(dtype="float64"),
                "lng": pd.Series(dtype="float64"),
                "rede": pd.Series(dtype="string"),
            }
        )
    limpo, _auditoria = limpar_ruido(bruto)
    com_chave = derivar_chave(limpo)
    out = pd.DataFrame(
        {
            "fonte": com_chave["fonte"].astype("string"),
            "chave_snapshot": com_chave["chave_snapshot"].astype("string"),
            # O NOME viaja desde o BLK-MA-15: e' o que o pin do mapa exibe. Continua sem tocar
            # disco por esta funcao — quem persiste identidade e' o `alvos_nomeados`, e so' sob
            # `data/staging/` (gitignored), com guard proprio.
            "nome": com_chave["nome"].astype("string"),
            "lat": pd.to_numeric(com_chave["latitude"], errors="coerce").astype("float64"),
            "lng": pd.to_numeric(com_chave["longitude"], errors="coerce").astype("float64"),
            # A REDE viaja desde o BLK-MA-16, e não é PII: é a mesma categoria que o snapshot já
            # persiste em coluna própria. Ela existe aqui para o chamador separar independente de
            # cadeia SEM uma segunda leitura do feed — duas leituras custariam o dobro e abririam
            # a chance de os dois lados verem feeds diferentes (a mesma razão que fez o `main` do
            # `alvos_ma` ler o feed uma vez só).
            "rede": com_chave["rede"].astype("string"),
        }
    )
    # MESMO colapso de `montar_snapshot`: `(fonte, chave_snapshot)` é a chave primária do score, e
    # duplicata aqui faria o join da pressão levantar. Colapsar mantém os dois lados coerentes.
    return out.drop_duplicates(subset=["fonte", "chave_snapshot"], keep="first").reset_index(
        drop=True
    )


def montar_snapshot(
    df: pd.DataFrame, *, fontes_lidas: str
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Projeta as **13 colunas do contrato**, coage dtypes, colapsa colisões e valida o schema.

    `fontes_lidas` é kwarg **obrigatório e sem default** `[BLK-MA-21 / DEC-039]`: é o recorte que a
    EXECUÇÃO pediu (CSV ordenado, ex. `"totalpass,wellhub"`), e um default o tornaria adivinhável —
    exatamente o que a coluna existe para impedir. Ela distingue "o TotalPass não foi tentado" de
    "foi tentado e a curadoria o recusou por feed velho": no segundo caso a folha `fonte=totalpass`
    não existe, e olhar as folhas presentes leria os dois casos como o mesmo.

    **Não recebe `data_referencia`** (removido no BLK-MA-02-FU1, m2). O parâmetro existia, nunca era
    lido, e sugeria exatamente a coisa errada: que o `snapshot_date` saísse dele. Não sai — ele é
    derivado POR LINHA de `parse_data_coleta(data_coleta, fonte)`, e é isso que o torna medidor de
    frescor ("o CSV é o da semana passada?"). Quem usa a data da execução é a `semana` da partição,
    decidida em `materializar`.

    A PII morre neste passo (molde `_COLUNAS_DROP_FRONTEIRA`, `concorrentes_densos.py:73-86`):
    `nome`/coords/cidade/CEP/endereço/modalidades simplesmente não são projetados.

    Colisões de `(fonte, chave_snapshot)` são **COLAPSADAS** para uma linha (contadas em
    `chaves_colapsadas`). Desambiguar por ordinal seria pior: o ordinal depende da ordem de leitura
    do CSV, os dois trocariam de chave entre semanas e gerariam churn sintético toda semana.
    Colapsar produz falso NEGATIVO — direção segura para um sinal de peso ~0,467.
    """
    entrada = int(len(df))
    out = df.copy()
    if out.empty:
        vazio = _frame_snapshot_vazio(com_semana=False)
        _assert_schema_snapshot(vazio)
        return vazio, {
            "linhas_entrada": 0,
            "linhas_snapshot": 0,
            "chaves_colapsadas": 0,
            "rating_ilegivel": 0,
        }

    out["snapshot_date"] = [
        parse_data_coleta(valor, fonte=str(fonte)).isoformat()
        for valor, fonte in zip(out["data_coleta"], out["fonte"], strict=False)
    ]
    out["versao_contrato"] = VERSAO_CONTRATO_SNAPSHOT
    out["fontes_lidas"] = str(fontes_lidas)
    # As colunas-fato de rating só existem no feed do WellHub; TotalPass e `unidades` chegam sem
    # elas e ficam nulas por construção (DEC-026). Sem este preenchimento a projeção abaixo levanta
    # `KeyError` para essas duas fontes.
    for coluna in ("nota_wellhub", "qtd_avaliacoes_wellhub"):
        if coluna not in out.columns:
            out[coluna] = pd.NA
    out = out[list(CONTRATO_COLUNAS_SNAPSHOT.keys())]

    for coluna in CONTRATO_COLUNAS_SNAPSHOT:
        if CONTRATO_COLUNAS_SNAPSHOT[coluna] == "string":
            out[coluna] = out[coluna].astype("string")
    out, rating_ilegivel = _coagir_rating(out)
    out["slug"] = out["slug"].where(out["slug"].fillna("").str.len() > 0, pd.NA)

    out = out.sort_values(
        ["fonte", "chave_snapshot", "hash_campos_raspados"], kind="mergesort"
    ).reset_index(drop=True)
    antes = int(len(out))
    out = out.drop_duplicates(subset=["fonte", "chave_snapshot"], keep="first").reset_index(
        drop=True
    )
    colapsadas = antes - int(len(out))

    _assert_schema_snapshot(out)
    return out, {
        "linhas_entrada": entrada,
        "linhas_snapshot": int(len(out)),
        "chaves_colapsadas": int(colapsadas),
        # Degradações de rating desta semana. Zero é o normal; qualquer número > 0 é sinal de que
        # o formato do coletor mudou e vale investigar ANTES de a série herdar o buraco.
        "rating_ilegivel": int(rating_ilegivel),
    }


def _assert_schema_snapshot(df: pd.DataFrame) -> None:
    """Falha alto se o frame não é exatamente o contrato `VERSAO_CONTRATO_SNAPSHOT`.

    A versão vive na constante, não neste texto: cravá-la aqui já ficou stale uma vez, no bump
    `v1` -> `v2` da emenda BLK-MA-11.
    """
    esperado = list(CONTRATO_COLUNAS_SNAPSHOT.keys())
    pii = sorted(set(df.columns) & COLUNAS_PII_PROIBIDAS)
    if pii:
        raise ValueError(f"coluna de PII no snapshot (anti-PII DEC-012): {pii}")
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

    obrigatorias = [c for c in esperado if c not in COLUNAS_SNAPSHOT_NULAVEIS]
    for coluna in obrigatorias:
        serie = df[coluna]
        vazio = serie.isna() | (serie.astype(str).str.len() == 0)
        if bool(vazio.any()):
            raise ValueError(f"`{coluna}` com NaN/vazio no snapshot")

    invalidos: list[str] = []
    for hid in df["hex_id_res7"].astype(str).unique():
        if not h3.is_valid_cell(hid) or h3.get_resolution(hid) != H3_RES_CONTRATO:
            invalidos.append(hid)
            if len(invalidos) >= 5:
                break
    if invalidos:
        raise ValueError(f"hex_id_res7 fora de res-{H3_RES_CONTRATO}: amostra {invalidos}")

    fontes_ruins = sorted(set(df["fonte"].astype(str)) - FONTES_VALIDAS)
    if fontes_ruins:
        raise ValueError(f"fonte fora do contrato: {fontes_ruins}")
    origens_ruins = sorted(set(df["chave_origem"].astype(str)) - CHAVE_ORIGEM_VALIDAS)
    if origens_ruins:
        raise ValueError(f"chave_origem fora do contrato: {origens_ruins}")
    versoes_ruins = sorted(set(df["versao_contrato"].astype(str)) - {VERSAO_CONTRATO_SNAPSHOT})
    if versoes_ruins:
        raise ValueError(f"versao_contrato inesperada: {versoes_ruins}")

    dup = int(df.duplicated(subset=["fonte", "chave_snapshot"]).sum())
    if dup > 0:
        raise ValueError(f"chave (fonte, chave_snapshot) duplicada: {dup} linha(s)")

    # Rating (DEC-026). O caminho público normaliza TODOS estes casos em `_coagir_rating` — nenhum
    # deles pode chegar aqui vindo de `montar_snapshot`, e é de propósito: levantar sobre dado do
    # coletor custaria a semana inteira (ver a docstring de `_coagir_rating`). Estas checagens são
    # a rede para frames montados à MÃO — que é como metade dos testes desta camada constrói o
    # insumo, e como um bloco futuro provavelmente vai construir também.
    nota = df["nota_wellhub"]
    qtd = df["qtd_avaliacoes_wellhub"]
    fora = nota.dropna()
    if len(fora) and (
        bool((fora < NOTA_WELLHUB_MIN).any()) or bool((fora > NOTA_WELLHUB_MAX).any())
    ):
        raise ValueError(
            f"nota_wellhub fora de [{NOTA_WELLHUB_MIN}, {NOTA_WELLHUB_MAX}]: "
            f"amostra {sorted(set(fora))[:5]}"
        )
    negativas = qtd.dropna()
    if len(negativas) and bool((negativas < 0).any()):
        raise ValueError("qtd_avaliacoes_wellhub negativa")
    # O PAR tem de ser um dos TRÊS estados da DEC-024 (D-3): "tem nota" (`4.81`/`105`), "sem
    # avaliações" (`NA`/`0`) ou "não lido" (`NA`/`NA`). Os outros três pares possíveis — `NA`/`105`,
    # `4.81`/`0` e `4.81`/`NA` — não existem no contrato. Deixá-los passar faria uma quebra de
    # parser entrar no funil disfarçada de academia sem avaliação.
    tem_nota = nota.notna() & qtd.notna() & (qtd > 0)
    sem_avaliacoes = nota.isna() & qtd.notna() & (qtd == 0)
    nao_lido = nota.isna() & qtd.isna()
    incoerentes = int((~(tem_nota | sem_avaliacoes | nao_lido)).sum())
    if incoerentes:
        raise ValueError(
            f"rating incoerente em {incoerentes} linha(s): estado fora dos tres da DEC-024"
        )


# --------------------------------------------------------------------------- #
# 6. Escrita/leitura particionada (I/O) — pyarrow hive, molde fase1_bi_exports.py:588-608
# --------------------------------------------------------------------------- #
def _particionamento_hive() -> ds.Partitioning:
    """Particionamento hive das DUAS chaves do contrato, na ordem de `COLUNAS_PARTICAO`.

    Função ÚNICA de propósito: escrita e leitura têm de declarar exatamente as mesmas chaves. Se
    divergirem, o modo de falha é silencioso — um leitor de UMA chave sobre a árvore de duas
    devolve `fonte` nula para 100% das linhas, sem erro e sem log (medido). Como
    `(fonte, chave_snapshot)` é a chave primária composta de todo o pacote, isso envenenaria churn,
    presença e score de uma vez. `test_nenhum_leitor_do_pacote_usa_particionamento_de_uma_chave`
    trava a regressão por AST.
    """
    return ds.partitioning(
        pa.schema([(chave, pa.string()) for chave in COLUNAS_PARTICAO]), flavor="hive"
    )


def _arquivos_legados_da_semana(base_dir: Path, semana: str) -> list[Path]:
    """`parte-*.parquet` SOLTOS dentro de `semana=AAAA-SS/` (layout antigo, de 1 chave).

    Profundidade 1 de propósito: o layout novo põe os arquivos em `semana=X/fonte=Y/`, então
    qualquer `parte-*.parquet` filho DIRETO do diretório da semana é resíduo do layout de 1 chave.
    """
    diretorio = Path(base_dir) / f"semana={semana}"
    if not diretorio.is_dir():
        return []
    return sorted(p for p in diretorio.glob("parte-*.parquet") if p.is_file())


def escrever_particao_semana(
    df: pd.DataFrame, base_dir: Path = SNAPSHOTS_DIR_DEFAULT, *, semana: str
) -> Path:
    """Grava `base_dir/semana=AAAA-SS/fonte=<fonte>/parte-*.parquet` (partição hive de 2 chaves).

    **A idempotência é por FOLHA, não por partição `[BLK-MA-21 / DEC-039]`.** Com uma chave só,
    `existing_data_behavior="delete_matching"` casava a SEMANA inteira: a execução dos
    agregadores (terça) apagava o que a do `unidades` (domingo) tinha acabado de gravar na mesma
    semana ISO, e vice-versa — ~21h de coleta perdidas com `exit 0`. Com `fonte=` como segunda
    chave, reescrever uma semana substitui **só as folhas das fontes presentes no frame**, e a
    folha de uma fonte AUSENTE do frame **sobrevive** (medido em pyarrow 23.0.1). Onde antes se
    lia "a semana encolheu", leia-se agora "a folha encolheu": chamar com um frame parcial encolhe
    exatamente as folhas daquele frame. A exigência de **exatamente uma** semana ISO por chamada
    (CA-17/R7) continua, porque a `semana` ainda vem da data de referência da execução.

    O `fonte` **sai de dentro do arquivo** quando vira chave de partição — o pyarrow o move para o
    caminho. O parquet físico tem 12 colunas; as 13 do contrato voltam em `ler_snapshots`, que
    declara as duas chaves. Um leitor que declare só `semana` devolve `fonte` **nula para 100% das
    linhas, sem erro e sem log** (ver `ler_snapshots`).

    **EXCEÇÃO, e ela é deliberada (BLK-MA-02-FU1, m1):** frame **vazio** NÃO apaga a partição
    existente e NÃO cria diretório — a função sai cedo, avisando em WARNING, e o caminho devolvido
    **pode não existir**. A idempotência do parágrafo acima vale para "a folha encolheu", não para
    "a semana sumiu". Motivo: zero linha quase sempre é **coleta que falhou**, não universo
    realmente vazio; apagar aqui trocaria uma falha transitória por perda permanente de série, o
    mesmo modo de falha que o `_coagir_rating` evita do lado do dado. Para zerar uma semana de
    propósito, apague a partição à mão.

    **Recusa semana com layout LEGADO (D8).** Se a semana já tiver `parte-*.parquet` solto (layout
    de 1 chave), a função levanta em vez de gravar: o `delete_matching` de 2 chaves **não** apaga o
    arquivo legado, e o resultado medido é a linha voltando **duas vezes** na leitura — dias depois
    e longe da causa, como `chave (semana, fonte, chave_snapshot) duplicada`. A migração é um ato
    explícito (`migrar_layout_particoes` / `--migrar-layout`), nunca um efeito colateral da escrita.
    """
    if not isinstance(semana, str) or not RE_SEMANA.match(semana):
        raise ValueError("escrever_particao_semana exige `semana` no formato ISO AAAA-SS")
    legados = _arquivos_legados_da_semana(Path(base_dir), semana)
    if legados:
        raise ValueError(
            f"particao legada de 1 chave em semana={semana} "
            f"({len(legados)} arquivo(s) solto(s)); rode --migrar-layout antes de gravar"
        )
    if df.empty:
        _logger.warning(
            "frame vazio para semana=%s: nada gravado e particao existente PRESERVADA "
            "(zero linha e' sintoma de coleta falha, nao de universo vazio)",
            semana,
        )
        return Path(base_dir) / f"semana={semana}"
    frame = df.copy()
    if "semana" in frame.columns and not frame.empty:
        semanas_no_frame = {str(v) for v in frame["semana"]}
        if len(semanas_no_frame) != 1 or next(iter(semanas_no_frame)) != semana:
            raise ValueError(
                "escrever_particao_semana aceita exatamente 1 semana ISO por chamada "
                f"(recebeu {len(semanas_no_frame)} distinta(s))"
            )
        frame = frame.drop(columns=["semana"])

    _assert_schema_snapshot(frame)
    base_dir = Path(base_dir)
    base_dir.mkdir(parents=True, exist_ok=True)
    # `str`, NUNCA `categorical`: o pyarrow não particiona por coluna dictionary
    # (armadilha comentada em `fase1_bi_exports.py:596-598`).
    frame["semana"] = str(semana)
    frame["semana"] = frame["semana"].astype(str)
    # `schema=` explícito na ESCRITA pelo mesmo motivo que na leitura: garante que o arquivo nasça
    # com os tipos do contrato em vez dos que o pandas inferir. Sem isso, uma partição em que
    # `nota_wellhub` fosse toda nula sairia como `null` em vez de `double`, e a leitura seguinte
    # teria de conciliar tipos incompatíveis entre semanas.
    tabela = pa.Table.from_pandas(frame, preserve_index=False, schema=_schema_arrow_snapshot())
    ds.write_dataset(
        tabela,
        base_dir=str(base_dir),
        format="parquet",
        partitioning=_particionamento_hive(),
        basename_template="parte-{i}.parquet",
        existing_data_behavior="delete_matching",
    )
    return base_dir / f"semana={semana}"


def ponte_dir_de(base_dir: Path, ponte_dir: Path | None = None) -> Path:
    """Onde a ponte mora, dado onde a série mora. `ponte_dir` explícito vence.

    DERIVADA do `base_dir`, e não uma constante absoluta, por um motivo que um default fixo
    esconderia: todo chamador que aponta a série para outro lugar — cada teste com `tmp_path`, um
    `--base-dir` de rascunho, o regen em diretório provisório — passaria a espalhar ponte em
    `data/staging/` do processo, longe da série que ela descreve. Derivando, a ponte acompanha a
    série por construção, e em produção cai exatamente em `PONTE_DIR_DEFAULT`.
    """
    if ponte_dir is not None:
        return Path(ponte_dir)
    return Path(base_dir).parent / PONTE_DIR_DEFAULT.name


def montar_ponte_identidade(df: pd.DataFrame) -> pd.DataFrame:
    """Frame de TRABALHO -> `(fonte, chave_snapshot, nome, lat, lng)`, uma linha por chave.

    Recebe o frame que já passou por `derivar_chave` — o mesmo de que `montar_snapshot` parte — e
    projeta as colunas que a projeção do contrato mata. É por isso que a ponte nasce **antes** da
    fronteira anti-PII e não depois: depois, a informação já não existe.

    O colapso é o MESMO de `montar_snapshot` — e "mesmo" inclui o **desempate**: a ordenação por
    `["fonte", "chave_snapshot", "hash_campos_raspados"]` (estável) ANTES do
    `drop_duplicates(keep="first")`. Sem ela, as duas funções colapsariam o mesmo par para linhas
    DIFERENTES, cada uma pela ordem em que o CSV foi lido: a ponte responderia "quem é esta chave"
    descrevendo a linha que o snapshot descartou, e a ficha exibiria o nome e a coordenada errados
    no evento. Travado por `test_ponte_colapsa_colisao_pela_MESMA_linha_do_snapshot` — o defeito foi
    achado pela revisão automática no PR #386, com a docstring já afirmando a equivalência que o
    código não cumpria.
    """
    if df.empty:
        return pd.DataFrame(
            {col: pd.Series(dtype=dtype) for col, dtype in CONTRATO_COLUNAS_PONTE.items()}
        )
    ordenado = df.sort_values(
        ["fonte", "chave_snapshot", "hash_campos_raspados"], kind="mergesort"
    )
    out = pd.DataFrame(
        {
            "fonte": ordenado["fonte"].astype("string"),
            "chave_snapshot": ordenado["chave_snapshot"].astype("string"),
            "nome": ordenado["nome"].astype("string"),
            "lat": pd.to_numeric(ordenado["latitude"], errors="coerce").astype("Float64"),
            "lng": pd.to_numeric(ordenado["longitude"], errors="coerce").astype("Float64"),
        }
    )
    return out.drop_duplicates(subset=["fonte", "chave_snapshot"], keep="first").reset_index(
        drop=True
    )


def escrever_ponte_identidade(
    df: pd.DataFrame, ponte_dir: Path = PONTE_DIR_DEFAULT, *, semana: str
) -> Path:
    """Grava `ponte_dir/semana=AAAA-SS/fonte=<fonte>/parte-*.parquet` (DEC-064, D3).

    Mesmas duas chaves de partição e mesma idempotência POR FOLHA da série, pela mesma razão: duas
    cadências escrevem na mesma semana ISO, e com uma chave só a segunda apagaria a primeira.

    Frame vazio **não apaga** a folha existente, também pelo mesmo motivo do snapshot: zero linha é
    quase sempre coleta que falhou, não universo vazio.
    """
    if not isinstance(semana, str) or not RE_SEMANA.match(semana):
        raise ValueError("escrever_ponte_identidade exige `semana` no formato ISO AAAA-SS")
    destino = Path(ponte_dir) / f"semana={semana}"
    if df.empty:
        _logger.warning("ponte de identidade vazia para semana=%s: nada gravado", semana)
        return destino
    faltando = [c for c in CONTRATO_COLUNAS_PONTE if c not in df.columns]
    if faltando:
        raise ValueError(f"ponte de identidade fora do contrato; colunas ausentes: {faltando}")
    frame = df[list(CONTRATO_COLUNAS_PONTE.keys())].copy()
    base = Path(ponte_dir)
    base.mkdir(parents=True, exist_ok=True)
    frame["semana"] = str(semana)
    tabela = pa.Table.from_pandas(frame, preserve_index=False, schema=_schema_arrow_ponte())
    ds.write_dataset(
        tabela,
        base_dir=str(base),
        format="parquet",
        partitioning=_particionamento_hive(),
        basename_template="parte-{i}.parquet",
        existing_data_behavior="delete_matching",
    )
    return destino


def ler_ponte_identidade(
    ponte_dir: Path = PONTE_DIR_DEFAULT,
    *,
    semanas: Sequence[str] | None = None,
    fontes: Sequence[str] | None = None,
) -> pd.DataFrame:
    """Lê a ponte -> 5 colunas do contrato + `semana`. Recortada na varredura, como a série."""
    base = Path(ponte_dir)
    colunas = list(CONTRATO_COLUNAS_PONTE.keys()) + ["semana"]
    vazio = pd.DataFrame(
        {
            **{c: pd.Series(dtype=dt) for c, dt in CONTRATO_COLUNAS_PONTE.items()},
            "semana": pd.Series(dtype="string"),
        }
    )
    if not base.exists() or not any(_RE_DIR_SEMANA.match(p.name) for p in base.iterdir()):
        return vazio
    dataset = ds.dataset(
        str(base),
        format="parquet",
        schema=_schema_arrow_ponte(),
        partitioning=_particionamento_hive(),
    )
    tabela = dataset.to_table(filter=_filtro_de_particao(semanas=semanas, fontes=fontes))
    df = tabela.to_pandas(types_mapper=_TIPO_PANDAS_POR_ARROW.get)
    out = df[colunas].reset_index(drop=True)
    for coluna, dtype in CONTRATO_COLUNAS_PONTE.items():
        out[coluna] = out[coluna].astype(dtype)
    return out


# Tradução dtype do contrato -> tipo Arrow, e a volta. Uma tabela só, para que a ida e a volta
# não possam divergir (o `types_mapper` do `to_pandas` é a inversa desta).
_TIPO_ARROW_POR_DTYPE: dict[str, pa.DataType] = {
    "string": pa.string(),
    "Float64": pa.float64(),
    "Int64": pa.int64(),
}
_TIPO_PANDAS_POR_ARROW: dict[pa.DataType, object] = {
    pa.string(): pd.StringDtype(),
    pa.float64(): pd.Float64Dtype(),
    pa.int64(): pd.Int64Dtype(),
}


def _schema_arrow_ponte() -> pa.Schema:
    """Schema Arrow da ponte de identidade + a coluna de partição `semana`."""
    campos = [(col, _TIPO_ARROW_POR_DTYPE[dtype]) for col, dtype in CONTRATO_COLUNAS_PONTE.items()]
    return pa.schema([*campos, ("semana", pa.string())])


def _schema_arrow_snapshot() -> pa.Schema:
    """Schema Arrow do contrato de snapshot + a coluna de partição `semana`."""
    campos = [
        (col, _TIPO_ARROW_POR_DTYPE[dtype]) for col, dtype in CONTRATO_COLUNAS_SNAPSHOT.items()
    ]
    return pa.schema([*campos, ("semana", pa.string())])


def _frame_snapshot_vazio(com_semana: bool = True) -> pd.DataFrame:
    """Frame vazio COM os dtypes do contrato — `nota_wellhub`/`qtd_avaliacoes_wellhub` sao
    numericos nulaveis, nao `string`, e um frame vazio mal tipado quebraria o `concat` da serie.
    """
    dados = {col: pd.Series(dtype=dt) for col, dt in CONTRATO_COLUNAS_SNAPSHOT.items()}
    if com_semana:
        dados["semana"] = pd.Series(dtype="string")
    return pd.DataFrame(dados)


def _filtro_de_particao(
    *, semanas: Sequence[str] | None, fontes: Sequence[str] | None
) -> ds.Expression | None:
    """Recorte de `semanas`/`fontes` como expressão de PARTIÇÃO (`None` = ler tudo).

    Existe separada para que o filtro seja escrito UMA vez: a leitura recortada é o que sustenta a
    retenção integral da DEC-064, e um segundo lugar que recortasse em pandas reintroduziria o pico
    de memória sem que nenhum teste ficasse vermelho.
    """
    partes: list[ds.Expression] = []
    if semanas is not None:
        partes.append(ds.field("semana").isin(sorted({str(s) for s in semanas})))
    if fontes is not None:
        partes.append(ds.field("fonte").isin(sorted({str(f) for f in fontes})))
    if not partes:
        return None
    filtro = partes[0]
    for parte in partes[1:]:
        filtro = filtro & parte
    return filtro


def listar_particoes(base_dir: Path = SNAPSHOTS_DIR_DEFAULT) -> dict[str, list[str]]:
    """`{fonte: [semanas ISO ordenadas]}` pela LISTAGEM de diretórios — **não abre um parquet**.

    É a leitura de METADADO que a DEC-064 (D5) exige para a estreia e para a observabilidade. Com
    a leitura da série recortada, "a primeira semana desta fonte" **não pode** sair do frame lido:
    sairia a borda da janela, e o defeito corrigido no PR #383 voltaria por outro caminho — lá, a
    estreia por SÉRIE em vez de por FONTE fez 22.877 chaves do WellHub passarem por recém-chegadas,
    contra 327 reais.

    **Partição LEGADA (1 chave) é invisível aqui**, e é uma consequência declarada, não um
    descuido: no layout antigo a `fonte` vive DENTRO do arquivo, então nomear a fonte exigiria
    abrir o parquet — exatamente o que esta função existe para não fazer. Quem enxerga o legado é
    `diagnosticar_layout_particoes`, e `escrever_particao_semana` já recusa gravar por cima dele.
    """
    base = Path(base_dir)
    if not base.exists():
        return {}
    por_fonte: dict[str, list[str]] = {}
    for filho in sorted(base.iterdir()):
        casa = _RE_DIR_SEMANA.match(filho.name)
        if not casa or not filho.is_dir():
            continue
        semana = casa.group(1)
        for neto in sorted(filho.iterdir()):
            casa_fonte = _RE_DIR_FONTE.match(neto.name)
            if not casa_fonte or not neto.is_dir():
                continue
            por_fonte.setdefault(casa_fonte.group(1), []).append(semana)
    return {fonte: sorted(set(semanas)) for fonte, semanas in sorted(por_fonte.items())}


def primeira_semana_por_fonte(base_dir: Path = SNAPSHOTS_DIR_DEFAULT) -> dict[str, str]:
    """`{fonte: primeira semana ISO da fonte}` — a ESTREIA, pela listagem (DEC-064, D5).

    Derivada de `listar_particoes` e não do frame lido: ver lá por que a distinção importa.
    """
    return {fonte: semanas[0] for fonte, semanas in listar_particoes(base_dir).items() if semanas}


def ler_snapshots(
    base_dir: Path = SNAPSHOTS_DIR_DEFAULT,
    *,
    semanas: Sequence[str] | None = None,
    fontes: Sequence[str] | None = None,
) -> pd.DataFrame:
    """Lê a série de partições -> 13 colunas do contrato + `semana` (string, vinda do caminho).

    O `partitioning` é explícito também na LEITURA para o pyarrow não inferir tipo e devolver
    `semana`/`fonte` como algo diferente de string. Base inexistente/vazia -> frame vazio
    bem-formado.

    **Declarar as DUAS chaves não é simetria estética — é correção `[BLK-MA-21 / DEC-039]`.** Sobre
    a árvore de duas chaves, um leitor que declare só `semana` devolve **`fonte = None` para 100%
    das linhas, sem exceção, sem erro e sem log** (medido em pyarrow 23.0.1). Como
    `(fonte, chave_snapshot)` é a chave primária composta de todo o pacote — churn, presença, score
    e o universo do sinal 1 —, o resultado seria o colapso de todas as fontes numa só, em silêncio.
    A trava contra um leitor futuro nascer com esse defeito é o teste de AST
    `test_nenhum_leitor_do_pacote_usa_particionamento_de_uma_chave`, e o defeito em si é
    caracterizado por `test_leitor_de_uma_chave_devolve_fonte_nula_em_silencio`.

    Séries MISTAS (partição legada de 1 chave, com `fonte` dentro do arquivo, ao lado de folhas
    novas) são lidas corretamente: medido, `fonte` volta certa e com zero nulos. O que NÃO pode
    coexistir é arquivo legado e folha nova **da mesma fonte na mesma semana** — aí a linha volta
    duas vezes. Por isso `escrever_particao_semana` recusa semana com layout legado.

    **O `schema=` explícito não é otimização — é correção `[BLK-MA-09 / DEC-026]`.** Sem ele o
    pyarrow infere o schema do PRIMEIRO arquivo do dataset. Numa série com partições de contratos
    diferentes (pré e pós-bump, que é exatamente o que um bump produz), se a primeira lida for uma
    partição antiga, as colunas novas são **descartadas de todas as outras**; o laço de
    preenchimento abaixo então as recria como `pd.NA`, e o resultado é uma coluna **nula para o
    universo inteiro, sem erro e sem log** — inclusive para as linhas que tinham valor. Com o
    schema declarado, o pyarrow preenche o que falta **por arquivo**, que é a semântica certa. É
    por ele que uma partição `v3` (sem `fontes_lidas`) segue legível, saindo com a coluna nula.

    **O recorte é aplicado na VARREDURA, não depois dela `[DEC-064]`.** `semanas=`/`fontes=` viram
    filtro de PARTIÇÃO (`ds.field(...).isin(...)` passado ao `to_table`), então o pyarrow só abre
    as folhas pedidas. Antes o filtro era em pandas DEPOIS do `to_pandas`, ou seja, a série inteira
    subia para a memória para ser jogada fora em seguida — os ~70,5 MB de RSS por semana retida
    medidos no D5 da DEC-039, que são exatamente o custo que fazia a retenção precisar de teto. O
    resultado é idêntico; o que muda é o pico de memória, e é ele que sustenta o D1.

    `fontes` recorta a série pelas fontes pedidas, no mesmo molde de `semanas`. Existe para impor
    POR CÓDIGO a fronteira com o BLK-MA-20 (DEC-039, D9): a
    partição do `totalpass` passa a ser GRAVADA desde a primeira semana — para o cronômetro de
    `MIN_SEMANAS` começar a correr —, mas o consumo dela pelo score espera a calibração da dedup
    TP x WH, que hoje está arbitrada. Prosa não impediria: a cadeia inteira roda com as duas fontes
    sem editar uma linha. Nome fora de `FONTES_VALIDAS` **levanta**, e levanta ANTES da saída
    antecipada por base vazia — ver o comentário no corpo.
    """
    # A validação vem ANTES da saída antecipada `[emenda de 2026-08-25 à DEC-039]`. Ela estava
    # depois, e o efeito era o oposto do prometido: sobre base inexistente ou sem partição — que é
    # exatamente o estado da VPS hoje, zero partições — `fontes=["wellub"]` devolvia frame VAZIO em
    # vez de levantar. Um erro de digitação na fronteira do D9 sairia como "não há dado", que é a
    # leitura errada e a única que não faz ninguém procurar a causa.
    if fontes is not None:
        pedidas = {str(f) for f in fontes}
        desconhecidas = sorted(pedidas - FONTES_VALIDAS)
        if desconhecidas:
            raise ValueError(
                f"fonte fora do contrato: {desconhecidas}; aceitas: {sorted(FONTES_VALIDAS)}"
            )
        if not pedidas:
            raise ValueError("`fontes` vazio: nao ha o que ler")
    base = Path(base_dir)
    if not base.exists() or not any(_RE_DIR_SEMANA.match(p.name) for p in base.iterdir()):
        return _frame_snapshot_vazio()
    dataset = ds.dataset(
        str(base),
        format="parquet",
        schema=_schema_arrow_snapshot(),
        partitioning=_particionamento_hive(),
    )
    tabela = dataset.to_table(filter=_filtro_de_particao(semanas=semanas, fontes=fontes))
    df = tabela.to_pandas(types_mapper=_TIPO_PANDAS_POR_ARROW.get)
    colunas = list(CONTRATO_COLUNAS_SNAPSHOT.keys()) + ["semana"]
    for coluna in colunas:
        if coluna not in df.columns:
            df[coluna] = pd.NA
    out = df[colunas].reset_index(drop=True)
    for coluna, dtype in CONTRATO_COLUNAS_SNAPSHOT.items():
        out[coluna] = out[coluna].astype(dtype)
    return out


def podar_snapshots(
    base_dir: Path = SNAPSHOTS_DIR_DEFAULT,
    retencao_semanas: int = RETENCAO_SEMANAS,
    *,
    dry_run: bool = False,
) -> list[str]:
    """Retenção rolante **keep-newest-N** (contrato §6; default `RETENCAO_SEMANAS`). Devolve as
    semanas removidas.

    A unidade é o DIRETÓRIO `semana=`, e a folha `fonte=` **não** é olhada: podar remove a semana
    inteira, com todas as fontes que ela tiver. É essa granularidade que faz `RETENCAO_SEMANAS`
    contar semanas de CALENDÁRIO e não observações — a aritmética está no comentário da
    constante, em `contrato.py`.

    Poda por FONTE dentro da partição fica em bloco próprio (DEC-039, D5). Sob cadência uniforme
    as duas unidades coincidem NO CAMINHO FELIZ, mas divergem assim que uma fonte perde a folha
    da semana (a curadoria recusa feed velho, o coletor cai): a semana continua ocupando um slot
    e a fonte perde a observação. Medido: 20 semanas com `wellhub` só nas pares, poda em N=13 ->
    `unidades` fica com 13 observações e `wellhub` com 7, abaixo de `MIN_SEMANAS = 8`. A margem
    que a poda por fonte compraria já vem de graça no `RETENCAO_SEMANAS = 26` (2x o piso 13).

    Semântica sem `date.today()` de propósito (determinística e testável). **APAGA DIRETÓRIOS EM
    DISCO**, e por isso é conservadora: só olha filhos DIRETOS de `base_dir` cujo nome casa
    `^semana=\\d{4}-\\d{2}$` — um irmão fora do padrão (`backup/`, `semana_antiga/`, um arquivo
    solto) é **invisível** para a poda. Chamada SÓ por `executar()`; `materializar(escrever=False)`
    nunca a alcança.
    """
    if int(retencao_semanas) < 1:
        raise ValueError("retencao_semanas deve ser >= 1")
    base = Path(base_dir)
    if not base.exists():
        return []
    candidatos: list[tuple[str, Path]] = []
    for filho in base.iterdir():
        if not filho.is_dir():
            continue
        casa = _RE_DIR_SEMANA.match(filho.name)
        if casa:
            candidatos.append((casa.group(1), filho))
    # Zero-padding torna a ordem lexicográfica == ordem cronológica ISO.
    candidatos.sort(key=lambda par: par[0])
    a_remover = candidatos[: max(0, len(candidatos) - int(retencao_semanas))]
    removidas: list[str] = []
    for semana, caminho in a_remover:
        if not dry_run:
            shutil.rmtree(caminho)
        removidas.append(semana)
    return sorted(removidas)


def _fontes_do_legado(
    base: Path, semana: str, legados: Sequence[Path]
) -> tuple[pd.DataFrame, list[str]]:
    """`(frame concatenado do legado, fontes distintas)`. Levanta se o legado não tiver `fonte`."""
    antigo = pd.concat([pd.read_parquet(arquivo) for arquivo in legados], ignore_index=True)
    if "fonte" not in antigo.columns:
        raise ValueError(
            f"particao legada em semana={semana} sem a coluna `fonte`: "
            "nao da' para decidir a folha de destino"
        )
    return antigo, sorted({str(v) for v in antigo["fonte"]})


def diagnosticar_layout_particoes(base_dir: Path = SNAPSHOTS_DIR_DEFAULT) -> dict[str, list[str]]:
    """`{"migraveis": [...], "ambiguas": [...]}` — **nunca levanta por ambiguidade, nunca toca disco**.

    Existe para que o operador possa OLHAR antes de agir `[emenda de 2026-08-25 à DEC-039]`. O
    `--dry-run` da migração levantava no primeiro estado ambíguo e não dizia mais nada: com duas
    semanas ambíguas, a segunda só aparecia depois de a primeira ser resolvida à mão, uma por
    execução. Diagnóstico que aborta no primeiro achado não é diagnóstico.

    A migração de verdade (`dry_run=False`) **continua levantando** — ali adivinhar custa dado.
    """
    base = Path(base_dir)
    diagnostico: dict[str, list[str]] = {"migraveis": [], "ambiguas": []}
    if not base.exists():
        return diagnostico
    for filho in sorted(base.iterdir()):
        if not filho.is_dir():
            continue
        casa = _RE_DIR_SEMANA.match(filho.name)
        if not casa:
            continue
        semana = casa.group(1)
        legados = _arquivos_legados_da_semana(base, semana)
        if not legados:
            continue
        _antigo, fontes_no_legado = _fontes_do_legado(base, semana, legados)
        ja_existem = [f for f in fontes_no_legado if (filho / f"fonte={f}").is_dir()]
        if ja_existem:
            diagnostico["ambiguas"].append(semana)
            _logger.error(
                "estado ambiguo em semana=%s: arquivo legado e folha `fonte=` da(s) mesma(s) "
                "fonte(s) %s coexistem; resolva a mao antes de migrar",
                semana,
                ja_existem,
            )
        else:
            diagnostico["migraveis"].append(semana)
    return diagnostico


def migrar_layout_particoes(
    base_dir: Path = SNAPSHOTS_DIR_DEFAULT, *, dry_run: bool = False
) -> list[str]:
    """Converte partições do layout LEGADO (1 chave) para o de 2 chaves. Devolve as semanas tocadas.

    `semana=AAAA-SS/parte-*.parquet` -> `semana=AAAA-SS/fonte=<fonte>/parte-0.parquet`. É a
    **segunda** função do módulo que apaga arquivo, e por isso vive colada à poda: o agrupamento
    torna visível quantos caminhos destrutivos existem. Ela é EXPLÍCITA de propósito (DEC-039, D8)
    — auto-migrar dentro de `escrever_particao_semana` poria leitura, reescrita e apagamento no
    caminho onde uma exceção custa a semana inteira de coleta.

    O que ela resolve, medido: arquivo legado e folha nova **da mesma fonte, na mesma semana** fazem
    a leitura devolver a linha DUAS vezes (o `delete_matching` de 2 chaves casa folhas, não o
    diretório da semana). Downstream isso aparece como `chave (semana, fonte, chave_snapshot)
    duplicada`, dias depois e longe da causa.

    **Ordem segura: escreve FORA da série e só então move `[emenda de 2026-08-25 à DEC-039]`.** A
    versão anterior gravava com `write_dataset` direto no caminho final e só depois apagava o
    legado — e o docstring prometia que "se a escrita falhar, o legado continua lá e a série segue
    legível pelo caminho misto", o que era FALSO: um crash no meio do `write_dataset` deixa uma
    folha PARCIAL ao lado do legado, e é exatamente esse par (legado + folha da mesma fonte) que
    faz a leitura devolver linha duplicada. Pior: a retentativa então bate na guarda de estado
    ambíguo e a migração fica travada até alguém apagar arquivo à mão.

    Agora: as folhas nascem num diretório temporário IRMÃO de `base_dir` (mesmo sistema de
    arquivos, logo o `os.replace` é rename e não cópia), e cada folha `fonte=Y` é movida para o
    lugar por um rename atômico. Irmão, e não filho, de propósito: um filho com parquets dentro
    entraria no `ds.dataset(base)` de `ler_snapshots` com profundidade errada de chaves.

    **Janela residual, declarada.** Entre o rename da primeira folha e o `unlink` do legado ainda
    há um instante em que os dois coexistem — mas agora ele mede alguns renames, não a escrita
    inteira. Se um crash pegar exatamente ali, o estado é o legado mais N folhas já movidas;
    `diagnosticar_layout_particoes` o reporta como ambíguo e o conserto é apagar as folhas movidas
    e repetir. Para eliminar a janela por completo seria preciso rename atômico de um diretório
    sobre outro, que nem POSIX nem Windows oferecem para diretório não vazio — por isso o passo 2
    do runbook pede CÓPIA da partição antes de migrar.

    **Estado ambíguo levanta** (em `dry_run=False`). Se a semana já tiver folha `fonte=Y` da MESMA
    fonte que o arquivo legado carrega, não há como saber qual das duas é a boa — e adivinhar aqui
    é escolher entre perder dado e duplicá-lo. Resolva à mão.

    `dry_run=True` **não toca disco** e **não levanta**: devolve as semanas migráveis e reporta as
    ambíguas em ERROR, via `diagnosticar_layout_particoes` — o operador precisa ver TODAS antes de
    agir, não uma por execução.
    """
    base = Path(base_dir)
    if not base.exists():
        return []
    if dry_run:
        return diagnosticar_layout_particoes(base)["migraveis"]
    migradas: list[str] = []
    for filho in sorted(base.iterdir()):
        if not filho.is_dir():
            continue
        casa = _RE_DIR_SEMANA.match(filho.name)
        if not casa:
            continue
        semana = casa.group(1)
        legados = _arquivos_legados_da_semana(base, semana)
        if not legados:
            continue

        antigo, fontes_no_legado = _fontes_do_legado(base, semana, legados)
        ja_existem = [f for f in fontes_no_legado if (filho / f"fonte={f}").is_dir()]
        if ja_existem:
            raise ValueError(
                f"estado ambiguo em semana={semana}: arquivo legado e folha `fonte=` da(s) "
                f"mesma(s) fonte(s) {ja_existem} coexistem; resolva a mao antes de migrar"
            )

        # `reindex` (e nao projecao direta): a particao legada pode ser de um contrato ANTERIOR e
        # nao ter as colunas novas. Preencher com nulo e' a mesma semantica do `schema=` por
        # arquivo do `ler_snapshots` — "gravada antes do bump", nunca "sem valor por engano".
        frame = antigo.reindex(columns=list(CONTRATO_COLUNAS_SNAPSHOT.keys()))
        for coluna, dtype in CONTRATO_COLUNAS_SNAPSHOT.items():
            frame[coluna] = frame[coluna].astype(dtype)
        frame["semana"] = str(semana)
        tabela = pa.Table.from_pandas(frame, preserve_index=False, schema=_schema_arrow_snapshot())
        # Diretorio IRMAO de `base` (`data/staging/`): mesmo sistema de arquivos que o destino,
        # logo `os.replace` e' rename. Dentro de `base` ele seria varrido pelo `ds.dataset`.
        temporario = Path(tempfile.mkdtemp(dir=str(base.parent), prefix=".migracao-"))
        try:
            ds.write_dataset(
                tabela,
                base_dir=str(temporario),
                format="parquet",
                partitioning=_particionamento_hive(),
                basename_template="parte-{i}.parquet",
                existing_data_behavior="delete_matching",
            )
            for fonte in fontes_no_legado:
                origem_folha = temporario / f"semana={semana}" / f"fonte={fonte}"
                if not origem_folha.is_dir():  # pragma: no cover - o write acabou de cria-la
                    raise ValueError(
                        f"folha `fonte={fonte}` nao foi escrita em {temporario}: migracao abortada"
                    )
                os.replace(origem_folha, filho / f"fonte={fonte}")
            for arquivo in legados:
                arquivo.unlink()
        finally:
            shutil.rmtree(temporario, ignore_errors=True)
        migradas.append(semana)
        _logger.info(
            "layout migrado: semana=%s -> %d folha(s) fonte= (%d linha(s))",
            semana,
            len(fontes_no_legado),
            len(frame),
        )
    return migradas


def migrar_chave_churn(
    base_dir: Path = SNAPSHOTS_DIR_DEFAULT,
    *,
    semana: str,
    dir_unidades: Path = DIR_UNIDADES_DEFAULT,
    dry_run: bool = False,
) -> dict[str, object]:
    """Re-chaveia a folha `semana=<S>/fonte=unidades` do `v4` para o `v5` `[DEC-063]`.

    **Por que uma migração, e não simplesmente deixar a chave nova entrar na próxima semana.** A
    chave é a identidade da academia na série: trocá-la sem migrar dá chave NOVA a todas as
    unidades de cadeia, e `concorrentes_novos` (`web/server/rede_inteligencia.py`) define "nova"
    como *primeira semana da chave != primeira semana da série*. Como a primeira semana das chaves
    novas seria a da troca, **toda academia de cadeia do país apareceria como "concorrente novo"**
    no pin da Visão Executiva, por `SEMANAS_CONCORRENTE_NOVO = 8` semanas. O relógio de maturidade
    (`MIN_SEMANAS`, contado POR CHAVE) também reiniciaria.

    **O preimage existe porque o feed guarda o que o snapshot não guarda.** O snapshot não persiste
    `nome` (anti-PII, DEC-012), então a chave `v4` de uma partição gravada não é recomputável a
    partir dela mesma. É recomputável a partir do CSV que a gerou: esta função refaz
    `ler_feeds -> limpar_ruido -> derivar_chave` (o mesmo caminho de `coordenadas_por_chave`, nunca
    uma segunda redação dele), obtém a chave `v5` e calcula a `v4` com `chave_hash_estavel_v4`
    sobre as MESMAS linhas sobreviventes. Medido antes de escrever uma linha: a `v4` recomputada
    reproduz **4.495 de 4.495** chaves em `2026-31` e **4.610 de 4.610** em `2026-36`, com zero
    órfãs dos dois lados.

    **FALHA FECHADO.** Se qualquer chave da partição não casar com o feed — ou vice-versa —, nada é
    gravado. Um mapa parcial é pior que nenhum: as linhas não mapeadas ficariam com a chave antiga
    ao lado das novas, que é o defeito de identidade em massa que a migração existe para evitar.
    Partição que já está em `v5` é **no-op** (idempotente); versão desconhecida **aborta**.

    Só a folha `fonte=unidades` é tocada. As outras fontes usam `chave_do_slug`, que a DEC-063 não
    muda, e `escrever_particao_semana` substitui apenas as folhas presentes no frame.

    `dry_run=True` não toca o disco: devolve as contagens do cruzamento para conferência.
    """
    if not isinstance(semana, str) or not RE_SEMANA.match(semana):
        raise ValueError("migrar_chave_churn exige `semana` no formato ISO AAAA-SS")

    persistido = ler_snapshots(base_dir, semanas=[semana], fontes=["unidades"])
    if persistido.empty:
        _logger.warning("semana=%s nao tem folha `fonte=unidades`: nada a migrar", semana)
        return {"semana": semana, "linhas": 0, "migradas": 0, "dry_run": bool(dry_run)}

    versoes = sorted({str(v) for v in persistido["versao_contrato"]})
    if versoes == [VERSAO_CONTRATO_SNAPSHOT]:
        _logger.info("semana=%s ja' esta em %s: no-op", semana, VERSAO_CONTRATO_SNAPSHOT)
        return {
            "semana": semana,
            "linhas": int(len(persistido)),
            "migradas": 0,
            "ja_migrada": True,
            "dry_run": bool(dry_run),
        }
    if versoes != [VERSAO_CONTRATO_SNAPSHOT_V4]:
        raise ValueError(
            f"semana={semana} tem versao_contrato {versoes}; esta migracao so' converte "
            f"{VERSAO_CONTRATO_SNAPSHOT_V4} -> {VERSAO_CONTRATO_SNAPSHOT}"
        )

    # O MESMO caminho de `coordenadas_por_chave`: ler -> limpar -> derivar. Reusar (em vez de
    # reimplementar) e' o que garante que as linhas sobreviventes aqui sejam as mesmas que
    # `materializar` gravou — qualquer divergencia de filtro apareceria como orfa no cruzamento
    # abaixo, e a guarda de fail-closed a transformaria em recusa, nunca em mapa parcial.
    bruto = ler_feeds(dir_unidades=dir_unidades, fontes=["unidades"])
    if bruto.empty:
        raise ValueError(
            f"o feed em {dir_unidades} nao tem linha nenhuma: sem ele nao ha como recomputar a "
            "chave v4 (o snapshot nao guarda `nome`)"
        )
    limpo, _auditoria = limpar_ruido(bruto)
    com_chave = derivar_chave(limpo)

    de_para: dict[str, str] = {}
    for fonte, rede, nome, hex7, nova in zip(
        com_chave["fonte"],
        com_chave["rede"],
        com_chave["nome"],
        com_chave["hex_id_res7"],
        com_chave["chave_snapshot"],
        strict=False,
    ):
        de_para[chave_hash_estavel_v4(fonte, rede, nome, hex7)] = str(nova)

    no_disco = {str(k) for k in persistido["chave_snapshot"]}
    sem_origem = sorted(no_disco - set(de_para))
    if sem_origem:
        raise ValueError(
            f"semana={semana}: {len(sem_origem)} chave(s) do disco NAO foram reproduzidas pelo "
            f"feed em {dir_unidades} (amostra: {sem_origem[:5]}). O feed nao e' o que gerou esta "
            "particao; nada foi gravado (um mapa parcial deixaria chaves antigas e novas lado a "
            "lado, que e' o dano que esta migracao existe para evitar)"
        )

    destinos = [de_para[str(k)] for k in persistido["chave_snapshot"]]
    if len(set(destinos)) != len(destinos):
        raise ValueError(
            f"semana={semana}: a chave v5 COLAPSARIA linhas distintas desta particao "
            f"({len(destinos) - len(set(destinos))} colisao(oes)); nada foi gravado"
        )

    resultado: dict[str, object] = {
        "semana": semana,
        "linhas": int(len(persistido)),
        "migradas": int(len(destinos)),
        "chaves_no_feed": int(len(de_para)),
        "dry_run": bool(dry_run),
    }
    if dry_run:
        _logger.info("DRY-RUN da migracao de chave: %s", resultado)
        return resultado

    novo = persistido.copy()
    novo["chave_snapshot"] = pd.Series(destinos, index=novo.index, dtype="string")
    novo["versao_contrato"] = pd.Series(
        [VERSAO_CONTRATO_SNAPSHOT] * len(novo), index=novo.index, dtype="string"
    )
    escrever_particao_semana(novo, base_dir, semana=semana)
    _logger.info("chave migrada v4 -> v5: %s", resultado)
    return resultado


# --------------------------------------------------------------------------- #
# 6.1 Guarda de coleta PARCIAL (fronteira de publicação)
# --------------------------------------------------------------------------- #
class LaudoColetaParcial(TypedDict):
    """Laudo da guarda. TIPADO de proposito: como `dict[str, object]`, `laudo["motivos"]` sai como
    `object` e nem iterar sobre ele o mypy aceita — e o consumidor acabaria fazendo `cast`, que é
    justamente onde um erro de chave passa despercebido."""

    aprovado: bool
    motivos: list[str]
    por_fonte: dict[str, object]
    erro_leitura_serie: str | None


def avaliar_coleta_parcial(
    snapshot: pd.DataFrame,
    base_dir: Path = SNAPSHOTS_DIR_DEFAULT,
    *,
    semana: str,
    tolerancia_rede_pct: float = TOLERANCIA_QUEDA_REDE_PCT,
    tolerancia_total_pct: float = TOLERANCIA_QUEDA_TOTAL_PCT,
) -> LaudoColetaParcial:
    """A semana candidata veio de uma coleta COMPLETA? Compara com a última semana da MESMA fonte.

    **O incidente (2026-09-13).** Um coletor travou, o tratador de timeout do repo irmão quebrou e o
    lote morreu no #28 de 90. O `run_weekly_90.sh` abre com `git checkout -- Unidades/`, então as 56
    redes que não rodaram ficaram com o CSV commitado no repositório: a Selfit caiu de 231 para 119.
    O regen de mercado REPROVOU (guarda de desenhabilidade, DEC-059) e não publicou nada — mas o
    snapshot não tinha guarda nenhuma e gravou a foto quebrada. Como a série é o insumo de S3/S4, as
    112 unidades "sumidas" virariam `sumiu_recente`: falso positivo em massa no sinal de maior peso.

    **Por REDE, não no total** (ver `TOLERANCIA_QUEDA_REDE_PCT`): naquele domingo o total caiu só
    2,5% e a Selfit, 48,5%. O colapso por rede é a assinatura; o total é rede de segurança para a
    queda difusa.

    **Compara fonte com ela mesma.** `unidades` (domingo) e os agregadores (sábado/terça) têm
    cadências próprias e universos de tamanho diferente; cruzar fontes inventaria queda onde só há
    calendário. Fonte que estreia não tem referência e **passa** — a guarda mede queda, não tamanho.

    **Lê UMA semana, não a série `[DEC-064]`.** A referência sai de `listar_particoes` (metadado,
    sem abrir parquet) e só a folha `(ref, fonte)` é carregada. Antes a guarda chamava
    `ler_snapshots(base_dir)` inteiro para usar uma única semana de cada fonte — sob retenção
    integral seria ELA o gargalo de memória do pacote, como a própria DEC-064 declarou.

    É a ÚNICA leitura de semanas anteriores fora da poda, e ela é deliberada: a fronteira declarada
    no topo do módulo ("o materializador nunca olha semanas anteriores") existia para o CÁLCULO do
    snapshot, que segue intacto — aqui não se deriva nada, só se decide publicar.

    Devolve sempre o laudo (nunca levanta): quem decide gravar é `materializar`.
    """
    # A guarda NUNCA pode ser o motivo de a semana não ser gravada por um problema de LEITURA: parte
    # corrompida, layout legado ou arquivo estranho na árvore fariam `ler_snapshots` levantar, e o
    # snapshot inteiro morreria — o oposto do que esta função existe para proteger. Sem referência
    # legível ela APROVA e carimba o erro, que é a direção segura: perder a checagem de uma semana
    # custa menos que perder a semana.
    try:
        semanas_por_fonte = listar_particoes(base_dir)
        erro_leitura: str | None = None
    except Exception as exc:  # noqa: BLE001 — qualquer falha de leitura degrada, nunca bloqueia
        semanas_por_fonte = {}
        erro_leitura = f"{type(exc).__name__}: {exc}"
        _logger.error("guarda de coleta parcial sem referencia (serie ilegivel): %s", erro_leitura)

    por_fonte: dict[str, object] = {}
    motivos: list[str] = []

    for fonte in sorted(set(snapshot["fonte"].astype(str))) if not snapshot.empty else []:
        atual = snapshot[snapshot["fonte"].astype(str) == fonte]
        anteriores = [s for s in semanas_por_fonte.get(fonte, []) if s < semana]
        if not anteriores:
            por_fonte[fonte] = {"semana_anterior": None, "unidades_antes": None,
                                "unidades_agora": int(len(atual)), "queda_pct": None, "redes_que_desabaram": []}
            continue

        ref = anteriores[-1]
        try:
            antes = ler_snapshots(base_dir, semanas=[ref], fontes=[fonte])
        except Exception as exc:  # noqa: BLE001 — mesma degradacao do bloco acima, por fonte
            erro_leitura = f"{type(exc).__name__}: {exc}"
            _logger.error(
                "guarda sem referencia para fonte=%s (semana %s ilegivel): %s",
                fonte,
                ref,
                erro_leitura,
            )
            por_fonte[fonte] = {
                "semana_anterior": None,
                "unidades_antes": None,
                "unidades_agora": int(len(atual)),
                "queda_pct": None,
                "redes_que_desabaram": [],
            }
            continue
        n_antes, n_agora = int(len(antes)), int(len(atual))
        queda_pct = 100.0 * (n_antes - n_agora) / n_antes if n_antes else 0.0

        c_antes = antes["rede"].astype(str).value_counts()
        c_agora = atual["rede"].astype(str).value_counts()
        desabaram = []
        for rede, qtd_antes in c_antes.items():
            if int(qtd_antes) < MIN_UNIDADES_GUARDA_REDE:
                continue
            qtd_agora = int(c_agora.get(rede, 0))
            perda = 100.0 * (int(qtd_antes) - qtd_agora) / int(qtd_antes)
            if perda > tolerancia_rede_pct:
                desabaram.append({"rede": str(rede), "antes": int(qtd_antes), "agora": qtd_agora,
                                  "queda_pct": round(perda, 1)})

        por_fonte[fonte] = {"semana_anterior": ref, "unidades_antes": n_antes, "unidades_agora": n_agora,
                            "queda_pct": round(queda_pct, 2), "redes_que_desabaram": desabaram}
        for d in desabaram:
            motivos.append(
                f"fonte={fonte}: rede {d['rede']} caiu {d['antes']} -> {d['agora']} "
                f"({d['queda_pct']:.1f}%) contra a semana {ref} — coleta parcial?"
            )
        if n_antes >= MIN_UNIDADES_GUARDA_TOTAL and queda_pct > tolerancia_total_pct:
            motivos.append(
                f"fonte={fonte}: total caiu {n_antes} -> {n_agora} ({queda_pct:.1f}%) "
                f"contra a semana {ref}, acima do limite de {tolerancia_total_pct:.0f}%"
            )

    return LaudoColetaParcial(
        aprovado=not motivos,
        motivos=motivos,
        por_fonte=por_fonte,
        erro_leitura_serie=erro_leitura,
    )


# --------------------------------------------------------------------------- #
# 7. Orquestração
# --------------------------------------------------------------------------- #
def materializar(
    dir_totalpass: Path = DIR_TOTALPASS_DEFAULT,
    dir_wellhub: Path = DIR_WELLHUB_DEFAULT,
    dir_unidades: Path = DIR_UNIDADES_DEFAULT,
    base_dir: Path = SNAPSHOTS_DIR_DEFAULT,
    data_referencia: date | None = None,
    *,
    escrever: bool = True,
    ponte_dir: Path | None = None,
    taxa_slug_persistente: float | None = None,
    politica_chave: str = "auto",
    fontes: Sequence[str] | None = None,
    forcar: bool = False,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """CSV cru -> limpeza -> hash -> chave -> snapshot da semana (e, opcionalmente, a partição).

    `data_referencia=None` usa `date.today()`. A `semana` da partição sai **dessa data de
    referência**, NUNCA do `data_coleta` da linha — um coletor que falha mantém o CSV anterior, e
    derivar a partição da linha faria uma execução de hoje reescrever (e, com `delete_matching`,
    APAGAR) uma semana passada.

    **NUNCA** chama `podar_snapshots` — a poda é exclusiva de `executar()`.
    """
    referencia = data_referencia or date.today()
    semana = derivar_semana_iso(referencia)

    bruto = ler_feeds(dir_totalpass, dir_wellhub, dir_unidades, fontes=fontes)
    limpo, auditoria_limpeza = limpar_ruido(bruto)
    com_hash = calcular_hash_campos_raspados(limpo)
    com_chave = derivar_chave(
        com_hash, taxa_slug_persistente=taxa_slug_persistente, politica=politica_chave
    )
    # Quais feeds ESTA execução PEDIU. Calculado UMA vez e usado nos dois lugares — a coluna do
    # parquet e a auditoria impressa —, para que a auditoria espelhe exatamente o que foi gravado
    # em vez de recalcular a mesma coisa por outro caminho (dois caminhos podem divergir; um não).
    # A resposta muda com a cadência (BLK-MA-06): quem ler a série semanas depois precisa saber que
    # as semanas antigas só tinham `unidades`, sob pena de ler ausência de agregador como churn.
    fontes_lidas = ",".join(sorted(FONTES_VALIDAS if fontes is None else {str(f) for f in fontes}))
    snapshot, auditoria_snapshot = montar_snapshot(com_chave, fontes_lidas=fontes_lidas)

    auditoria: dict[str, object] = {
        "semana": semana,
        "fontes_lidas": fontes_lidas,
        **auditoria_limpeza,
        **auditoria_snapshot,
    }
    # Guarda de coleta PARCIAL (DEC-061). Avaliada TAMBEM em dry-run: o modo seco da VPS existe
    # para antecipar o domingo, e um laudo que so' aparecesse na hora de gravar nao anteciparia nada.
    guarda = avaliar_coleta_parcial(snapshot, base_dir, semana=semana)
    auditoria["coleta_parcial"] = guarda
    auditoria["forcado"] = bool(forcar)

    if not guarda["aprovado"]:
        for motivo in guarda["motivos"]:
            _logger.error("coleta parcial: %s", motivo)

    publicar = escrever and (guarda["aprovado"] or forcar)
    if escrever and not publicar:
        _logger.error(
            "REPROVADO — semana %s NAO sera gravada (coleta parcial). A serie anterior fica "
            "intacta. Se a queda for real, repita com --forcar.",
            semana,
        )
    auditoria["publicado"] = bool(publicar)
    if publicar:
        destino = escrever_particao_semana(snapshot, base_dir, semana=semana)
        _logger.info("snapshot semanal escrito: %s (%d linhas)", destino, len(snapshot))
        # Ponte de identidade (DEC-064, D3), do frame de TRABALHO — `com_chave`, não `snapshot`:
        # aqui `nome`/`latitude`/`longitude` ainda existem. Gravada sob a MESMA condição do
        # snapshot (`publicar`), para que as duas árvores nunca discordem sobre quais semanas
        # existem: uma ponte de uma semana que a guarda de coleta parcial REPROVOU descreveria
        # chaves que a série não tem.
        ponte = montar_ponte_identidade(com_chave)
        destino_ponte = escrever_ponte_identidade(
            ponte, ponte_dir_de(base_dir, ponte_dir), semana=semana
        )
        auditoria["linhas_ponte"] = int(len(ponte))
        _logger.info("ponte de identidade escrita: %s (%d linhas)", destino_ponte, len(ponte))
    return snapshot, auditoria


def executar(
    dir_totalpass: Path = DIR_TOTALPASS_DEFAULT,
    dir_wellhub: Path = DIR_WELLHUB_DEFAULT,
    dir_unidades: Path = DIR_UNIDADES_DEFAULT,
    base_dir: Path = SNAPSHOTS_DIR_DEFAULT,
    data_referencia: date | None = None,
    retencao_semanas: int = RETENCAO_TUDO,
    dry_run: bool = False,
    ponte_dir: Path | None = None,
    fontes: Sequence[str] | None = None,
    forcar: bool = False,
) -> dict[str, object]:
    """Orquestrador de disco: materializa a semana corrente e aplica a retenção rolante.

    É o ponto que o BLK-MA-06 plugará no `run_weekly_90.sh` (decisão de produto do gate
    2026-07-29), **depois** do passo de coleta — o snapshot tem de ser tirado DENTRO da execução do
    runner porque os CSVs crus são sobrescritos a cada coleta. **Único** lugar que poda.

    **A poda NÃO roda em regime desde a DEC-064 (D1).** O default de `retencao_semanas` é
    `RETENCAO_TUDO`, e sob ela `podar_snapshots` nem é consultada — a série inteira fica, que é o
    que torna `--reprocessar` possível. Passar qualquer valor `>= 1` reativa a poda keep-newest-N;
    é assim que ela segue disponível como ato MANUAL, com a invariante `>= 1` intacta do outro lado.

    `dry_run=True` roda o caminho inteiro e **não toca disco**: nada é gravado e **nada é podado**.
    Existe porque este é o unico ponto do pacote que APAGA arquivo, e um cron novo precisa poder ser
    validado antes de rodar para valer (BLK-MA-02-FU1, m6).

    A auditoria carrega `retencao_semanas` e `versao_contrato` `[BLK-MA-21]`. Não é cosmético: é a
    única forma de um `DRY_RUN` na VPS provar **qual imagem está rodando** antes de agendar. Uma
    imagem antiga escreve com UMA chave de partição e APAGA a folha da outra cadência; e a lição de
    "código publicado != camada no ar" veio de exatamente esse tipo de suposição não verificada.
    Nenhum dos dois campos toca o parquet, logo nenhum exige bump.
    """
    _snapshot, auditoria = materializar(
        dir_totalpass,
        dir_wellhub,
        dir_unidades,
        base_dir,
        data_referencia,
        escrever=not dry_run,
        ponte_dir=ponte_dir,
        fontes=fontes,
        forcar=forcar,
    )
    auditoria["retencao_semanas"] = int(retencao_semanas)
    auditoria["versao_contrato"] = VERSAO_CONTRATO_SNAPSHOT
    if dry_run:
        # A poda e' irreversivel; em modo seco ela nem e' consultada, so' anunciada.
        auditoria["dry_run"] = True
        auditoria["semanas_removidas"] = 0
        _logger.info("dry-run: nada gravado, nenhuma semana podada")
        return auditoria
    auditoria["dry_run"] = False
    if not auditoria.get("publicado", True):
        # Nada foi gravado: podar aqui encurtaria a serie BOA por causa de uma semana que nem entrou.
        auditoria["semanas_removidas"] = 0
        _logger.error("nada publicado (coleta parcial): retencao NAO aplicada")
        return auditoria
    if int(retencao_semanas) <= RETENCAO_TUDO:
        # Regime normal desde a DEC-064 (D1): a serie inteira fica. A poda NAO e' consultada, e a
        # invariante `>= 1` de `podar_snapshots` segue intacta porque a sentinela nunca chega la'.
        auditoria["semanas_removidas"] = 0
        _logger.info("retencao integral (DEC-064): nenhuma semana podada")
        return auditoria
    removidas = podar_snapshots(base_dir, retencao_semanas)
    auditoria["semanas_removidas"] = len(removidas)
    _logger.info("retencao aplicada: %d semana(s) removida(s)", len(removidas))
    return auditoria


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """CLI do materializador. Sem ela, `python -m ...snapshots` gravava e PODAVA sem argumento."""
    p = argparse.ArgumentParser(
        prog="python -m motor_expansao.vulnerabilidade.snapshots",
        description=(
            "Materializa o snapshot semanal de concorrentes e aplica a retencao rolante. "
            "E' o passo que o cron da VPS invoca (BLK-MA-06). READ-ONLY sobre o M1."
        ),
    )
    p.add_argument("--dir-totalpass", type=Path, default=DIR_TOTALPASS_DEFAULT)
    p.add_argument("--dir-wellhub", type=Path, default=DIR_WELLHUB_DEFAULT)
    p.add_argument("--dir-unidades", type=Path, default=DIR_UNIDADES_DEFAULT)
    p.add_argument(
        "--base-dir",
        type=Path,
        default=SNAPSHOTS_DIR_DEFAULT,
        help="raiz das particoes `semana=AAAA-SS` (grava E poda aqui)",
    )
    p.add_argument(
        "--ponte-dir",
        type=Path,
        default=None,
        help=(
            "raiz da ponte de identidade `chave -> nome/lat/lng` (DEC-064). Artefato NOMEADO e "
            "gitignored, arvore IRMA da serie -- nunca dentro dela. Default: derivado do "
            f"`--base-dir` (irmao de nome `{PONTE_DIR_DEFAULT.name}`), para a ponte acompanhar "
            "a serie mesmo quando ela nao esta' no caminho de producao"
        ),
    )
    p.add_argument(
        "--data-referencia",
        type=date.fromisoformat,
        default=None,
        help="AAAA-MM-DD; default = hoje. Decide a particao `semana=` de destino.",
    )
    p.add_argument(
        "--retencao-semanas",
        type=int,
        default=RETENCAO_TUDO,
        help=(
            f"semanas mantidas em disco. Default {RETENCAO_TUDO} = RETER TUDO, sem podar "
            f"(DEC-064). Qualquer valor >= 1 reativa a poda keep-newest-N; o piso medido e' "
            f"{RETENCAO_SEMANAS}, nunca abaixo dele"
        ),
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="roda tudo sem gravar e SEM PODAR; use antes de ligar o cron",
    )
    p.add_argument(
        "--migrar-layout",
        action="store_true",
        help=(
            "converte particoes do layout legado (`semana=X/parte-*.parquet`) para o de 2 chaves "
            "(`semana=X/fonte=Y/`) e SAI, sem materializar nada. Com `--dry-run` DIAGNOSTICA: "
            "lista as migraveis e TODAS as ambiguas, sem levantar e sem tocar o disco"
        ),
    )
    p.add_argument(
        "--migrar-chave-v5",
        action="store_true",
        help=(
            "re-chaveia a folha `fonte=unidades` de UMA semana do contrato v4 para o v5 (DEC-063) "
            "e SAI, sem materializar nada. Exige `--semana` e um `--dir-unidades` que seja o feed "
            "QUE GEROU aquela semana. Falha FECHADO: chave do disco que o feed nao reproduza "
            "aborta a migracao sem gravar. Com `--dry-run`, so' cruza e reporta"
        ),
    )
    p.add_argument(
        "--semana",
        default=None,
        help="semana ISO AAAA-SS alvo de `--migrar-chave-v5` (uma por execucao)",
    )
    p.add_argument(
        "--forcar",
        action="store_true",
        help=(
            "grava mesmo com a guarda de coleta parcial REPROVANDO. So' para queda REAL de mercado, "
            "conferida a mao: a auditoria sai com `forcado: true`"
        ),
    )
    p.add_argument(
        "--fontes",
        nargs="+",
        choices=sorted(FONTES_VALIDAS),
        default=None,
        help=(
            "feeds a fotografar (default: todos). O cron SEMANAL deve passar `--fontes unidades`: "
            "so' esse feed e' recoletado toda semana, e fotografar um feed estagnado faria o S4 "
            "marcar o universo inteiro daquela fonte como parado (BLK-MA-06)"
        ),
    )
    return p.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Entrada do `python -m`. Devolve 0 em sucesso — codigo de saida importa para o cron."""
    args = _parse_args(argv)
    logging.basicConfig(level=logging.INFO)
    if args.migrar_layout:
        # ANTES de `executar()`, e sem materializar nada: a migração é um ato próprio, e misturá-la
        # a uma coleta faria a operação destrutiva viajar de carona numa execução de rotina.
        if args.dry_run:
            # Modo seco DIAGNOSTICA: reporta TODAS as semanas ambíguas de uma vez, em vez de
            # levantar na primeira. O operador precisa da lista inteira antes de mexer à mão.
            diagnostico = diagnosticar_layout_particoes(args.base_dir)
            print(
                {
                    "migrar_layout": diagnostico["migraveis"],
                    "ambiguas": diagnostico["ambiguas"],
                    "dry_run": True,
                }
            )
            return 0
        migradas = migrar_layout_particoes(args.base_dir)
        print({"migrar_layout": migradas, "ambiguas": [], "dry_run": False})
        return 0
    if args.migrar_chave_v5:
        # Mesmo princípio do `--migrar-layout`: ANTES de `executar()` e sem materializar nada. A
        # migração é um ato próprio; misturá-la a uma coleta faria a reescrita da série viajar de
        # carona numa execução de rotina.
        if not args.semana:
            print({"erro": "--migrar-chave-v5 exige --semana AAAA-SS"})
            return 2
        resultado = migrar_chave_churn(
            args.base_dir,
            semana=args.semana,
            dir_unidades=args.dir_unidades,
            dry_run=bool(args.dry_run),
        )
        print(resultado)
        return 0
    auditoria = executar(
        dir_totalpass=args.dir_totalpass,
        dir_wellhub=args.dir_wellhub,
        dir_unidades=args.dir_unidades,
        base_dir=args.base_dir,
        ponte_dir=args.ponte_dir,
        data_referencia=args.data_referencia,
        retencao_semanas=args.retencao_semanas,
        dry_run=args.dry_run,
        fontes=args.fontes,
        forcar=args.forcar,
    )
    print(auditoria)
    # O wrapper da VPS roda com `|| echo` (falha no snapshot nao aborta o lote): sem codigo de saida
    # proprio, uma semana RECUSADA sairia no log como sucesso, que e' a leitura oposta da verdade.
    # 4 e' o mesmo codigo que o regen usa para "validacao de publicacao reprovou" (DEC-059).
    laudo = auditoria.get("coleta_parcial")
    reprovou = isinstance(laudo, dict) and not laudo.get("aprovado", True)
    if reprovou and not auditoria.get("forcado"):
        return 4
    return 0


__all__ = [
    "DIR_TOTALPASS_DEFAULT",
    "DIR_WELLHUB_DEFAULT",
    "DIR_UNIDADES_DEFAULT",
    "SNAPSHOTS_DIR_DEFAULT",
    "ler_feeds",
    "limpar_ruido",
    "calcular_hash_campos_raspados",
    "derivar_chave",
    "avaliar_estabilidade_slug",
    "montar_snapshot",
    "avaliar_coleta_parcial",
    "escrever_particao_semana",
    "ler_snapshots",
    "listar_particoes",
    "primeira_semana_por_fonte",
    "montar_ponte_identidade",
    "escrever_ponte_identidade",
    "ler_ponte_identidade",
    "ponte_dir_de",
    "PONTE_DIR_DEFAULT",
    "podar_snapshots",
    "diagnosticar_layout_particoes",
    "migrar_layout_particoes",
    "materializar",
    "executar",
    "main",
]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
