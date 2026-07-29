"""Contrato canônico da camada paralela de Vulnerabilidade para M&A (snapshots + churn).

Fonte única de verdade do schema dos snapshots semanais
(`data/staging/snapshots_concorrentes/semana=AAAA-SS/parte-*.parquet`, gitignored) e do frame de
churn/staleness derivado dele. **SEM I/O e SEM pandas** — só stdlib (BLK-MA-02 / DEC-012).

Diferença consciente em relação ao molde `demanda_revelada/contrato.py` (só constantes): aqui as
**primitivas de derivação também SÃO o contrato**. Alterar `normalizar_texto`, os campos da chave ou
a resolução do hex **re-chaveia a série inteira** e produz churn artificial em massa — por isso elas
ficam no mesmo arquivo que carrega `VERSAO_CONTRATO_SNAPSHOT`, e qualquer mudança **exige bump**
dessa versão (o BLK-MA-04 deve tratar o bump como descontinuidade de série).

GUARDRAILS (CLAUDE.md §1/§2/§5; contrato `docs/vulnerabilidade_ma_contrato.md` §11/§14):
  - READ-ONLY sobre o M1: nada aqui recalcula `score_priorizacao`, `hex_score_estrutural`, os pesos
    `renda=0.40`/`pop=0.60`, carteira, plano ou artefato oficial. `H3_RES_CONTRATO = 7` é **cópia
    local read-only** do parâmetro canônico (molde `demanda_revelada/contrato.py:16`), nunca um
    import de `config.py`.
  - Anti-PII (DEC-012): as colunas de PII/ruído textual morrem na fronteira do materializador; esta
    lista (`COLUNAS_PII_PROIBIDAS`) é a rede de segurança automatizada.
  - Acentuação (§2): prosa acentuada; identificadores, nomes de coluna e valores de enum em ASCII.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Mapping
from datetime import date

# --------------------------------------------------------------------------- #
# Carimbos de reprodutibilidade e parâmetros do contrato
# --------------------------------------------------------------------------- #
VERSAO_CONTRATO_SNAPSHOT = "snapshots_concorrentes_v1"
VERSAO_CONTRATO_CHURN = "churn_staleness_v1"
VERSAO_CONTRATO_PRESENCA_AGREGADOR = "presenca_agregador_v1"

# Resolução H3 da chave de join com o Motor (mesma do M1: H3_RESOLUTION=7) - cópia read-only.
H3_RES_CONTRATO = 7

# Maturidade/retenção do contrato §6 (gate de produto 2026-07-23). NÃO alterar sem novo gate:
# contam semanas OBSERVADAS, não semanas de calendário (ver §6/§12 do contrato).
MIN_SEMANAS = 8
STALE_SEMANAS = 12
RETENCAO_SEMANAS = 26

# ARBITRADO, nao medido (sem serie real; revisitar no BLK-MA-06). O valor importa menos que o
# DESENHO: o rebaixamento GLOBAL da chave só ocorre se o chamador INJETAR a taxa medida (default
# `None` em `derivar_chave`/`materializar`), senão uma reavaliação automática re-chavearia o
# universo inteiro no instante em que a taxa cruzasse o limiar.
LIMIAR_SLUG_ESTAVEL = 0.90

# Folga (~55 km) sobre o bbox da UF, para não descartar academia legítima junto a divisa.
TOLERANCIA_BBOX_UF_GRAUS = 0.5

# Coluna de partição hive do snapshot (não é coluna do arquivo: vive no caminho).
COLUNA_PARTICAO = "semana"

RE_SEMANA = re.compile(r"^\d{4}-\d{2}$")
RE_UUID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE
)

FONTES_VALIDAS: frozenset[str] = frozenset({"totalpass", "wellhub", "unidades"})
CHAVE_ORIGEM_VALIDAS: frozenset[str] = frozenset({"slug", "hash_estavel"})
STATUS_CHURN_VALIDOS: tuple[str, ...] = ("novo", "estavel", "piscando", "sumiu_recente")

# ORDEM CANÔNICA do `fontes_presentes_no_hex` (molde de domínio-tupla: `STATUS_CHURN_VALIDOS`) —
# a string do sinal 1 é montada iterando ESTA tupla, nunca um `set`, para ser determinística.
# Subconjunto PRÓPRIO de `FONTES_VALIDAS`: a fonte `unidades` é o feed de CADEIAS e nunca entra no
# universo do sinal 1 (BLK-MA-03).
FONTES_AGREGADORES: tuple[str, ...] = ("totalpass", "wellhub")

# REPLICADA de `demanda_revelada/classificacao_rede_menor.py:58`, NUNCA importada: aquele pacote é
# reexportado inteiro pelo seu `__init__`, e importá-lo daqui criaria uma SEGUNDA aresta para o
# vazamento transitivo que o `BLK-MA-02-FU1` (Item 2) vai fechar removendo UMA dependência. Não é
# ganho de tempo de import (o `__init__` deste pacote já paga o custo via `snapshots.py`): é não
# multiplicar o débito. Travada contra drift por teste, não por confiança.
CATEGORIA_INDEPENDENTE = "independente"

# (lat_min, lat_max, lng_min, lng_max) - MESMOS valores de `normalizar_concorrentes.py:24-25`,
# REPLICADOS de propósito (aquele arquivo é `_DENY_CRITICO` do loop_guard: molde de leitura,
# nunca import).
ENVELOPE_BRASIL: tuple[float, float, float, float] = (-34.0, 6.0, -75.0, -28.0)

# Retângulos por UF (lat_min, lat_max, lng_min, lng_max), com folga deliberada nas bordas.
# São grosseiros DE PROPÓSITO: a regra é fail-open e serve só para matar coordenada
# grosseiramente inconsistente com a `uf` declarada (contrato §6). Travados por teste que
# cruza as 27 capitais, digitadas de forma independente no arquivo de teste.
BBOX_UF: dict[str, tuple[float, float, float, float]] = {
    "AC": (-11.15, -7.11, -73.99, -66.62),
    "AL": (-10.50, -8.81, -38.24, -35.15),
    "AM": (-9.82, 2.25, -73.80, -56.10),
    "AP": (-1.24, 4.44, -54.88, -49.87),
    "BA": (-18.35, -8.53, -46.62, -37.34),
    "CE": (-7.86, -2.78, -41.42, -37.25),
    "DF": (-16.05, -15.50, -48.29, -47.31),
    "ES": (-21.30, -17.89, -41.88, -39.66),
    "GO": (-19.50, -12.40, -53.25, -45.90),
    "MA": (-10.27, -1.04, -48.76, -41.79),
    "MG": (-22.93, -14.23, -51.05, -39.86),
    "MS": (-24.07, -17.16, -58.17, -50.92),
    "MT": (-18.05, -7.35, -61.65, -50.22),
    # PE inclui Fernando de Noronha (~-3.85, -32.42): o retângulo é alongado de propósito.
    "PA": (-9.84, 2.60, -58.90, -46.06),
    "PB": (-8.31, -6.03, -38.77, -34.79),
    "PE": (-9.49, -3.80, -41.36, -32.38),
    "PI": (-10.93, -2.74, -45.99, -40.37),
    "PR": (-26.72, -22.52, -54.62, -48.02),
    "RJ": (-23.37, -20.76, -44.89, -40.96),
    "RN": (-6.99, -4.83, -38.59, -34.97),
    "RO": (-13.69, -7.97, -66.81, -59.77),
    "RR": (-1.58, 5.27, -64.83, -58.89),
    "RS": (-33.75, -27.08, -57.65, -49.69),
    "SC": (-29.36, -25.95, -53.84, -48.35),
    "SE": (-11.57, -9.51, -38.25, -36.39),
    "SP": (-25.31, -19.78, -53.11, -44.16),
    "TO": (-13.47, -5.17, -50.75, -45.70),
}

# --------------------------------------------------------------------------- #
# Limpeza de ruído (contrato §6): motivos e padrões
# --------------------------------------------------------------------------- #
# ORDEM FIXA de avaliação; a PRIMEIRA regra que casar decide o motivo (singular, para a contagem
# de auditoria fechar com `linhas_lidas - linhas_mantidas`).
MOTIVOS_DESCARTE: tuple[str, ...] = (
    "data_coleta_invalida",
    "coord_zero_zero",
    "coord_fora_envelope_brasil",
    "coord_fora_bbox_uf",
    "rotulo_de_teste",
    "entrada_tecnologia_totalpass",
)

PADROES_RUIDO_ROTULO_TESTE: tuple[str, ...] = (
    r"\bteste\b",
    r"\btest\b",
    r"\bdemo\b",
    r"\bhomologacao\b",
    r"\bsandbox\b",
)

PADROES_RUIDO_TECNOLOGIA_TOTALPASS: tuple[str, ...] = (
    r"\bzon tecnologia\b",
    r"\bsagaz sistemas\b",
    r"\btsitech\b",
    r"\bdatafitness\b",
    r"\bbatatao jeans\b",
    r"\bfornecedor\b",
)

_RE_RUIDO_ROTULO_TESTE = [re.compile(p) for p in PADROES_RUIDO_ROTULO_TESTE]
_RE_RUIDO_TECNOLOGIA_TOTALPASS = [re.compile(p) for p in PADROES_RUIDO_TECNOLOGIA_TOTALPASS]

# --------------------------------------------------------------------------- #
# Impressão digital dos campos raspados (sinal 4 / staleness)
# --------------------------------------------------------------------------- #
# Conjunto FIXO por fonte. `data_coleta` NUNCA entra (senão `semanas_sem_mudanca` jamais sairia de
# 0 e a staleness morreria); `slug` NUNCA entra (rotação de UUID no slug não é mudança de negócio).
CAMPOS_HASH_POR_FONTE: dict[str, tuple[str, ...]] = {
    "totalpass": (
        "nome",
        "latitude",
        "longitude",
        "cidade",
        "uf",
        "cep",
        "endereco_formatado",
        "modalidades",
    ),
    "wellhub": (
        "nome",
        "latitude",
        "longitude",
        "cidade",
        "uf",
        "cep",
        "endereco_formatado",
        "atividades",
    ),
    "unidades": ("nome_unidade", "latitude", "longitude"),
}
CAMPOS_NUNCA_HASHEADOS: frozenset[str] = frozenset({"data_coleta", "slug"})
CAMPOS_LISTA: frozenset[str] = frozenset({"modalidades", "atividades"})
CAMPOS_NUMERICOS: frozenset[str] = frozenset({"latitude", "longitude"})

# --------------------------------------------------------------------------- #
# Schemas canônicos
# --------------------------------------------------------------------------- #
# Snapshot semanal: 10 colunas, nesta ORDEM. `semana` NÃO é coluna do arquivo — é chave de
# partição hive (igual ao `uf` do enriquecido em `fase1_bi_exports.py`), materializada na leitura.
CONTRATO_COLUNAS_SNAPSHOT: dict[str, str] = {
    "snapshot_date": "string",         # `data_coleta` POR LINHA (ISO) -> medidor de frescor
    "slug": "string",                  # ID nativo do provedor (nulável: `unidades` não emite)
    "concorrente_id": "string",        # sha1 de produção replicado (rastreabilidade)
    "chave_snapshot": "string",        # A CHAVE DE CHURN (sha1 hex 40)
    "chave_origem": "string",          # slug | hash_estavel (rebaixamento auditável)
    "hex_id_res7": "string",           # geometria anti-PII (DEC-012) e chave de join
    "rede": "string",                  # categoria de rede; metade do escopo de observabilidade
    "fonte": "string",                 # totalpass | wellhub | unidades (sinal 1 do contrato §4)
    "hash_campos_raspados": "string",  # impressão digital dos campos raspados (sinal 4)
    "versao_contrato": "string",       # carimbo; mudança = descontinuidade de série
}

# Extrator de churn/staleness: 17 colunas, nesta ORDEM. `v3`/`v4`/`score_vulnerabilidade`/
# `n_sinais_disponiveis`/`flag_score_provisorio` estão AUSENTES DE PROPÓSITO — são BLK-MA-04.
CONTRATO_COLUNAS_CHURN: dict[str, str] = {
    "chave_snapshot": "string",
    "fonte": "string",
    "rede": "string",
    "hex_id_res7": "string",
    "chave_origem": "string",
    "status_churn": "string",
    "n_semanas_serie": "int64",
    "n_semanas_presente": "int64",
    "n_desaparecimentos": "int64",
    "semanas_sem_mudanca": "int64",
    "semana_primeira_observacao": "string",
    "semana_ultima_observacao": "string",
    "snapshot_date_ultimo": "string",
    "flag_serie_imatura": "bool",
    "flag_staleness_interpretavel": "bool",
    "flag_troca_chave_na_serie": "bool",
    "versao_contrato": "string",
}

# Sinal 1 (presença em agregador), hex-level: 10 colunas, nesta ORDEM. Uma linha por
# `hex_id_res7`. `v1`/`v2`/`score_vulnerabilidade`/`n_sinais_disponiveis`/`flag_score_provisorio`
# estão AUSENTES DE PROPÓSITO — são BLK-MA-04 (e o `v2`, BLK-MA-08).
#
# GRANULARIDADE (emenda BLK-MA-03 ao §8.1 do contrato do epic, ratificada em 2026-07-29): o §8.1
# descrevia `v1` POR ACADEMIA, mas a chave do snapshot embute a `fonte` (`chave_do_slug` e
# `chave_hash_estavel`), logo a mesma academia em TotalPass e WellHub é sempre DUAS chaves e
# "quantos agregadores cobrem esta linha" seria constante `1` — sinal sem variância. O sufixo
# `_no_hex` das colunas 2 e 3 é deliberado: ele carrega essa ressalva até todo consumidor futuro,
# depois do join `many_to_one` do BLK-MA-04.
CONTRATO_COLUNAS_PRESENCA_AGREGADOR: dict[str, str] = {
    "hex_id_res7": "string",                          # a chave (anti-PII, DEC-012) e o join
    "fontes_presentes_no_hex": "string",              # subconjunto de FONTES_AGREGADORES, `,`
    "n_agregadores_no_hex": "int64",                  # {1, 2} — nunca 0 (ver docstring do módulo)
    "n_academias_independentes_totalpass": "int64",   # chaves distintas de TP no hex
    "n_academias_independentes_wellhub": "int64",     # chaves distintas de WH no hex
    "semana_ultima_observacao_totalpass": "string",   # relógio do PIPELINE (nulo sse contagem 0)
    "semana_ultima_observacao_wellhub": "string",     # idem, WellHub
    "snapshot_date_ultimo_totalpass": "string",       # relógio do COLETOR (nulo sse contagem 0)
    "snapshot_date_ultimo_wellhub": "string",         # idem, WellHub
    "versao_contrato": "string",                      # carimbo; mudança = descontinuidade de série
}

# Colunas PROIBIDAS nos artefatos desta camada (rede de segurança do teste anti-PII: a limpeza é
# por construção, projetando só as 10 colunas do contrato).
COLUNAS_PII_PROIBIDAS: frozenset[str] = frozenset(
    {
        "nome",
        "nome_unidade",
        "latitude",
        "longitude",
        "lat",
        "lng",
        "cidade",
        "uf",
        "cep",
        "endereco_formatado",
        "modalidades",
        "atividades",
        "email",
        "telefone",
        "cpf",
        "cnpj",
        "endereco",
        "bairro",
        "logradouro",
    }
)

# --------------------------------------------------------------------------- #
# Primitivas CONGELADAS (mudança aqui re-chaveia a série -> bump obrigatório da versão)
# --------------------------------------------------------------------------- #
_RE_PONTUACAO = re.compile(r"[^a-z0-9\s]")
_RE_ESPACOS = re.compile(r"\s+")
_RE_SEPARADOR_LISTA = re.compile(r"[,;|/]")
_RE_CORTE_DATA = re.compile(r"[T ]")


def normalizar_texto(valor: object) -> str:
    """NFKD + remoção de acentos + minúsculas + pontuação -> espaço + colapso de espaços.

    `None`, `NaN` e a string `"nan"` viram `""`. **CONGELADA**: a chave de churn depende dela.
    """
    if valor is None:
        return ""
    texto = str(valor).strip()
    if not texto or texto.lower() == "nan":
        return ""
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.lower()
    texto = _RE_PONTUACAO.sub(" ", texto)
    return _RE_ESPACOS.sub(" ", texto).strip()


def normalizar_lista(valor: object) -> str:
    """Campo multivalorado -> tokens normalizados, sem vazios, **ORDENADOS**, juntos por `","`.

    A ordenação é o que torna o `hash_campos_raspados` insensível a reordenação de modalidades
    pelo provedor (que não é mudança de negócio e viraria falsa "atualização de cadastro").
    """
    if valor is None:
        return ""
    texto = str(valor)
    if not texto.strip() or texto.strip().lower() == "nan":
        return ""
    tokens = [normalizar_texto(t) for t in _RE_SEPARADOR_LISTA.split(texto)]
    return ",".join(sorted(t for t in tokens if t))


def normalizar_numero(valor: object) -> str:
    """Número -> `"{:.5f}"` (~1 m). Não-numérico/NaN/infinito -> `""` (sentinela fixa)."""
    try:
        numero = float(valor)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return ""
    if numero != numero or numero in (float("inf"), float("-inf")):
        return ""
    return f"{numero:.5f}"


def derivar_semana_iso(d: date) -> str:
    """`date` -> `AAAA-SS` pela semana ISO, via `isocalendar()`.

    Usa o **`iso_year`**, JAMAIS `d.year`: `2027-01-01` pertence à semana ISO `2026-53` e
    `2025-12-29` à `2026-01`. Zero-padding sempre (`2026-05`, nunca `2026-5`).
    """
    iso = d.isocalendar()
    return f"{int(iso[0]):04d}-{int(iso[1]):02d}"


def parse_data_coleta(valor: object, *, coluna: str = "data_coleta", fonte: str = "") -> date:
    """`AAAA-MM-DD` (ou `AAAA-MM-DDThh:mm:ss`, truncado) -> `date`. Falha alto em qualquer outro.

    Anti-PII no log: a mensagem de erro carrega o **nome da coluna e a `fonte`**, NUNCA o valor
    ofensor. A linha ofensora não derruba o lote: `limpar_ruido` a descarta individualmente e a
    conta em `descartes["data_coleta_invalida"]`.
    """
    texto = "" if valor is None else str(valor).strip()
    if texto and texto.lower() != "nan":
        cabeca = _RE_CORTE_DATA.split(texto, maxsplit=1)[0]
        partes = cabeca.split("-")
        if len(partes) == 3:
            try:
                return date(int(partes[0]), int(partes[1]), int(partes[2]))
            except (TypeError, ValueError):
                pass
    raise ValueError(
        f"coluna `{coluna}` fora do formato ISO aceito (AAAA-MM-DD); "
        f"fonte={fonte or 'n/d'} (valor omitido do log por anti-PII)"
    )


def coord_no_envelope(lat: object, lng: object) -> bool:
    """`True` se a coordenada cai no envelope do Brasil. `NaN`/não-numérico -> `False`."""
    try:
        la = float(lat)  # type: ignore[arg-type]
        ln = float(lng)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False
    if la != la or ln != ln:
        return False
    lat_min, lat_max, lng_min, lng_max = ENVELOPE_BRASIL
    return lat_min <= la <= lat_max and lng_min <= ln <= lng_max


def coord_no_bbox_uf(lat: object, lng: object, uf: object) -> bool:
    """`True` se a coordenada cai no bbox da `uf` (± tolerância). **Fail-open**.

    `uf` ausente, vazia ou fora de `BBOX_UF` -> `True` (a linha não é descartada por esta regra;
    só o envelope do Brasil vale). A coluna `uf` só existe no feed TP/WH: no feed `unidades` esta
    regra nunca dispara.
    """
    chave = "" if uf is None else str(uf).strip().upper()
    bbox = BBOX_UF.get(chave)
    if bbox is None:
        return True
    try:
        la = float(lat)  # type: ignore[arg-type]
        ln = float(lng)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False
    if la != la or ln != ln:
        return False
    lat_min, lat_max, lng_min, lng_max = bbox
    tol = TOLERANCIA_BBOX_UF_GRAUS
    return (lat_min - tol) <= la <= (lat_max + tol) and (lng_min - tol) <= ln <= (lng_max + tol)


def rotulo_de_teste(nome: object) -> bool:
    """`True` se o nome normalizado casa algum padrão de rótulo de teste/homologação."""
    norm = normalizar_texto(nome)
    return any(rgx.search(norm) for rgx in _RE_RUIDO_ROTULO_TESTE)


def entrada_tecnologia_totalpass(nome: object) -> bool:
    """`True` se o nome normalizado casa alguma entrada de tecnologia/onboarding do TotalPass."""
    norm = normalizar_texto(nome)
    return any(rgx.search(norm) for rgx in _RE_RUIDO_TECNOLOGIA_TOTALPASS)


def hash_campos_raspados(campos: Mapping[str, object], fonte: str) -> str:
    """Impressão digital sha1 dos campos raspados da linha (sinal 4 / staleness).

    Payload = `"{fonte}|{campo}={valor_norm}|..."` na ordem de `CAMPOS_HASH_POR_FONTE[fonte]`.
    Campo ausente entra como `""`. `fonte` fora do contrato levanta `ValueError`.
    """
    chave_fonte = str(fonte)
    campos_da_fonte = CAMPOS_HASH_POR_FONTE.get(chave_fonte)
    if campos_da_fonte is None:
        raise ValueError(f"fonte fora do contrato; aceitas: {sorted(CAMPOS_HASH_POR_FONTE)}")
    partes: list[str] = []
    for campo in campos_da_fonte:
        bruto = campos.get(campo, "")
        if campo in CAMPOS_LISTA:
            valor = normalizar_lista(bruto)
        elif campo in CAMPOS_NUMERICOS:
            valor = normalizar_numero(bruto)
        else:
            valor = normalizar_texto(bruto)
        partes.append(f"{campo}={valor}")
    payload = chave_fonte + "|" + "|".join(partes)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def chave_hash_estavel(fonte: object, rede: object, nome: object, hex_id_res7: object) -> str:
    """Chave de churn de fallback: sha1 estável a jitter de coordenada dentro do hex res-7.

    Divergimos do `concorrente_id` de produção de propósito (gate 2026-07-29): lá a coordenada
    entra com `:.6f` (~11 cm), então qualquer re-geocodificação produziria 1 falso
    `sumiu_recente` + 1 falso `novo` no sinal de MAIOR peso (S3 ~= 0,467).
    """
    payload = f"hash_estavel|{fonte}|{rede}|{normalizar_texto(nome)}|{hex_id_res7}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def chave_do_slug(fonte: object, slug: object) -> str:
    """Chave de churn pelo `slug` nativo do provedor, também como sha1 hex de 40 caracteres.

    Uniformizar o dtype/largura das duas variantes torna a chave opaca e simplifica os joins do
    BLK-MA-04/05; o `slug` cru permanece em coluna própria (artefato gitignored).
    """
    payload = f"slug|{fonte}|{normalizar_texto(slug)}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def concorrente_id_producao(rede: object, nome: object, lat: object, lng: object) -> str:
    """Réplica EXATA da fórmula de `concorrente_id` de produção (`sha1(rede|nome|lat|lng)`).

    A fórmula é **replicada, nunca importada**: `pipelines/normalizar_concorrentes.py` é
    `_DENY_CRITICO` do `loop_guard`. **Limite honesto:** este id só casa de fato com
    `concorrentes_mapeados.parquet` quando `fonte == "unidades"` (onde a `rede` também vem do nome
    do arquivo). Para TotalPass/WellHub é identificador best-effort — aqueles feeds nunca passaram
    pelo `normalizar_concorrentes`. Não prometer join universal.
    """
    try:
        la = float(lat)  # type: ignore[arg-type]
        ln = float(lng)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return ""
    if la != la or ln != ln:
        return ""
    return hashlib.sha1(f"{rede}|{nome}|{la:.6f}|{ln:.6f}".encode()).hexdigest()


__all__ = [
    "VERSAO_CONTRATO_SNAPSHOT",
    "VERSAO_CONTRATO_CHURN",
    "VERSAO_CONTRATO_PRESENCA_AGREGADOR",
    "H3_RES_CONTRATO",
    "MIN_SEMANAS",
    "STALE_SEMANAS",
    "RETENCAO_SEMANAS",
    "LIMIAR_SLUG_ESTAVEL",
    "TOLERANCIA_BBOX_UF_GRAUS",
    "COLUNA_PARTICAO",
    "RE_SEMANA",
    "RE_UUID",
    "FONTES_VALIDAS",
    "FONTES_AGREGADORES",
    "CATEGORIA_INDEPENDENTE",
    "CHAVE_ORIGEM_VALIDAS",
    "STATUS_CHURN_VALIDOS",
    "ENVELOPE_BRASIL",
    "BBOX_UF",
    "MOTIVOS_DESCARTE",
    "PADROES_RUIDO_ROTULO_TESTE",
    "PADROES_RUIDO_TECNOLOGIA_TOTALPASS",
    "CAMPOS_HASH_POR_FONTE",
    "CAMPOS_NUNCA_HASHEADOS",
    "CAMPOS_LISTA",
    "CAMPOS_NUMERICOS",
    "CONTRATO_COLUNAS_SNAPSHOT",
    "CONTRATO_COLUNAS_CHURN",
    "CONTRATO_COLUNAS_PRESENCA_AGREGADOR",
    "COLUNAS_PII_PROIBIDAS",
    "normalizar_texto",
    "normalizar_lista",
    "normalizar_numero",
    "derivar_semana_iso",
    "parse_data_coleta",
    "coord_no_envelope",
    "coord_no_bbox_uf",
    "rotulo_de_teste",
    "entrada_tecnologia_totalpass",
    "hash_campos_raspados",
    "chave_hash_estavel",
    "chave_do_slug",
    "concorrente_id_producao",
]
