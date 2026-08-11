"""BLK-MA-02: materializador dos snapshots semanais de concorrentes (insumo de S3/S4).

CSV cru dos coletores -> limpeza de ruído auditável -> chave estável -> `hash_campos_raspados` ->
`data/staging/snapshots_concorrentes/semana=AAAA-SS/parte-*.parquet` (**gitignored**, NÃO oficial
do M1). É o produtor que faltava: o `run_weekly_90.sh` **sobrescreve** os CSVs a cada coleta, então
toda semana não fotografada é perdida para sempre (`docs/infra_producao.md:136-149`).

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
    o Parquet leva apenas as 12 colunas do contrato. A auditoria da limpeza carrega **só
    contagens**, jamais o texto ofensor. Testes com fixtures 100% sintéticas.
  - CSV do projeto: `sep=";"`, `encoding="utf-8-sig"`. Staging sempre em Parquet.

API h3 = v4 (`latlng_to_cell`).
"""

from __future__ import annotations

import argparse
import logging
import re
import shutil
from collections.abc import Sequence
from datetime import date
from pathlib import Path

import h3
import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds

from motor_expansao.demanda_revelada.classificacao_rede_menor import classificar_rede

from .contrato import (
    CHAVE_ORIGEM_VALIDAS,
    COLUNAS_PII_PROIBIDAS,
    COLUNAS_SNAPSHOT_NULAVEIS,
    CONTRATO_COLUNAS_SNAPSHOT,
    FONTES_VALIDAS,
    H3_RES_CONTRATO,
    LIMIAR_SLUG_ESTAVEL,
    MOTIVOS_DESCARTE,
    NOTA_WELLHUB_MAX,
    NOTA_WELLHUB_MIN,
    RE_SEMANA,
    RE_UUID,
    RETENCAO_SEMANAS,
    VERSAO_CONTRATO_SNAPSHOT,
    chave_do_slug,
    chave_hash_estavel,
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
    CADÊNCIA, não de gosto (BLK-MA-06): o cron semanal recoleta só o feed `unidades`; WellHub e
    TotalPass dependem de um cron mensal que ainda **não existe**
    (`docs/infra_producao.md`, "Pendentes"). Fotografar um feed que não foi recoletado produz
    `hash_campos_raspados` idêntico semana após semana -> `semanas_sem_mudanca` cresce sozinho ->
    o **S4 marcaria o universo inteiro de agregador como "parado"**, que é justamente o sinal de
    vulnerabilidade. Passar `fontes` explicitamente deixa esse recorte auditável no log e na
    auditoria, em vez de escondido num diretório apontado para lugar nenhum.
    """
    ativas = FONTES_VALIDAS if fontes is None else frozenset(str(f) for f in fontes)
    desconhecidas = sorted(ativas - FONTES_VALIDAS)
    if desconhecidas:
        raise ValueError(f"fonte fora do contrato: {desconhecidas}; aceitas: {sorted(FONTES_VALIDAS)}")
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


def montar_snapshot(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object]]:
    """Projeta as **12 colunas do contrato**, coage dtypes, colapsa colisões e valida o schema.

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
def escrever_particao_semana(
    df: pd.DataFrame, base_dir: Path = SNAPSHOTS_DIR_DEFAULT, *, semana: str
) -> Path:
    """Grava `base_dir/semana=AAAA-SS/parte-*.parquet` (dataset pyarrow, partição hive).

    `existing_data_behavior="delete_matching"` dá idempotência VERDADEIRA de partição: reescrever a
    mesma semana apaga e regrava a partição inteira, então a idempotência vale mesmo quando a
    semana **encolhe**. O preço é que um frame PARCIAL apagaria o resto daquela semana — por isso a
    primeira coisa aqui é exigir **exatamente uma** semana ISO por chamada (CA-17/R7).

    **EXCEÇÃO, e ela é deliberada (BLK-MA-02-FU1, m1):** frame **vazio** NÃO apaga a partição
    existente e NÃO cria diretório — a função sai cedo, avisando em WARNING, e o caminho devolvido
    **pode não existir**. A idempotência do parágrafo acima vale para "a semana encolheu", não para
    "a semana sumiu". Motivo: zero linha quase sempre é **coleta que falhou**, não universo
    realmente vazio; apagar aqui trocaria uma falha transitória por perda permanente de série, o
    mesmo modo de falha que o `_coagir_rating` evita do lado do dado. Para zerar uma semana de
    propósito, apague a partição à mão.
    """
    if not isinstance(semana, str) or not RE_SEMANA.match(semana):
        raise ValueError("escrever_particao_semana exige `semana` no formato ISO AAAA-SS")
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
        partitioning=ds.partitioning(pa.schema([("semana", pa.string())]), flavor="hive"),
        basename_template="parte-{i}.parquet",
        existing_data_behavior="delete_matching",
    )
    return base_dir / f"semana={semana}"


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


def ler_snapshots(
    base_dir: Path = SNAPSHOTS_DIR_DEFAULT, *, semanas: Sequence[str] | None = None
) -> pd.DataFrame:
    """Lê a série de partições -> 12 colunas do contrato + `semana` (string, vinda do caminho).

    O `partitioning` é explícito também na LEITURA para o pyarrow não inferir tipo e devolver
    `semana` como algo diferente de string. Base inexistente/vazia -> frame vazio bem-formado.

    **O `schema=` explícito não é otimização — é correção `[BLK-MA-09 / DEC-026]`.** Sem ele o
    pyarrow infere o schema do PRIMEIRO arquivo do dataset. Numa série com partições de contratos
    diferentes (pré e pós-bump, que é exatamente o que um bump produz), se a primeira lida for uma
    partição antiga, as colunas novas são **descartadas de todas as outras**; o laço de
    preenchimento abaixo então as recria como `pd.NA`, e o resultado é uma coluna **nula para o
    universo inteiro, sem erro e sem log** — inclusive para as linhas que tinham valor. Com o
    schema declarado, o pyarrow preenche o que falta **por arquivo**, que é a semântica certa.
    """
    base = Path(base_dir)
    if not base.exists() or not any(_RE_DIR_SEMANA.match(p.name) for p in base.iterdir()):
        return _frame_snapshot_vazio()
    dataset = ds.dataset(
        str(base),
        format="parquet",
        schema=_schema_arrow_snapshot(),
        partitioning=ds.partitioning(pa.schema([("semana", pa.string())]), flavor="hive"),
    )
    tabela = dataset.to_table()
    df = tabela.to_pandas(types_mapper=_TIPO_PANDAS_POR_ARROW.get)
    if semanas is not None:
        alvo = {str(s) for s in semanas}
        df = df[df["semana"].astype(str).isin(alvo)]
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
    """Retenção rolante **keep-newest-N** (contrato §6: 26 semanas). Retorna as semanas removidas.

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
    taxa_slug_persistente: float | None = None,
    politica_chave: str = "auto",
    fontes: Sequence[str] | None = None,
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
    snapshot, auditoria_snapshot = montar_snapshot(com_chave)

    auditoria: dict[str, object] = {
        "semana": semana,
        # Quais feeds ESTA partição fotografou. Fica no snapshot porque a resposta muda com a
        # cadência (BLK-MA-06): quem ler a série meses depois precisa saber que as semanas antigas
        # só tinham `unidades`, sob pena de ler ausência de agregador como churn.
        "fontes_lidas": sorted(FONTES_VALIDAS if fontes is None else {str(f) for f in fontes}),
        **auditoria_limpeza,
        **auditoria_snapshot,
    }
    if escrever:
        destino = escrever_particao_semana(snapshot, base_dir, semana=semana)
        _logger.info("snapshot semanal escrito: %s (%d linhas)", destino, len(snapshot))
    return snapshot, auditoria


def executar(
    dir_totalpass: Path = DIR_TOTALPASS_DEFAULT,
    dir_wellhub: Path = DIR_WELLHUB_DEFAULT,
    dir_unidades: Path = DIR_UNIDADES_DEFAULT,
    base_dir: Path = SNAPSHOTS_DIR_DEFAULT,
    data_referencia: date | None = None,
    retencao_semanas: int = RETENCAO_SEMANAS,
    dry_run: bool = False,
    fontes: Sequence[str] | None = None,
) -> dict[str, object]:
    """Orquestrador de disco: materializa a semana corrente e aplica a retenção rolante.

    É o ponto que o BLK-MA-06 plugará no `run_weekly_90.sh` (decisão de produto do gate
    2026-07-29), **depois** do passo de coleta — o snapshot tem de ser tirado DENTRO da execução do
    runner porque os CSVs crus são sobrescritos a cada coleta. **Único** lugar que poda.

    `dry_run=True` roda o caminho inteiro e **não toca disco**: nada é gravado e **nada é podado**.
    Existe porque este é o unico ponto do pacote que APAGA arquivo, e um cron novo precisa poder ser
    validado antes de rodar para valer (BLK-MA-02-FU1, m6).
    """
    _snapshot, auditoria = materializar(
        dir_totalpass,
        dir_wellhub,
        dir_unidades,
        base_dir,
        data_referencia,
        escrever=not dry_run,
        fontes=fontes,
    )
    if dry_run:
        # A poda e' irreversivel; em modo seco ela nem e' consultada, so' anunciada.
        auditoria["dry_run"] = True
        auditoria["semanas_removidas"] = 0
        _logger.info("dry-run: nada gravado, nenhuma semana podada")
        return auditoria
    auditoria["dry_run"] = False
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
        "--data-referencia",
        type=date.fromisoformat,
        default=None,
        help="AAAA-MM-DD; default = hoje. Decide a particao `semana=` de destino.",
    )
    p.add_argument(
        "--retencao-semanas",
        type=int,
        default=RETENCAO_SEMANAS,
        help=f"semanas mantidas em disco (default {RETENCAO_SEMANAS})",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="roda tudo sem gravar e SEM PODAR; use antes de ligar o cron",
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
    auditoria = executar(
        dir_totalpass=args.dir_totalpass,
        dir_wellhub=args.dir_wellhub,
        dir_unidades=args.dir_unidades,
        base_dir=args.base_dir,
        data_referencia=args.data_referencia,
        retencao_semanas=args.retencao_semanas,
        dry_run=args.dry_run,
        fontes=args.fontes,
    )
    print(auditoria)
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
    "escrever_particao_semana",
    "ler_snapshots",
    "podar_snapshots",
    "materializar",
    "executar",
    "main",
]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
