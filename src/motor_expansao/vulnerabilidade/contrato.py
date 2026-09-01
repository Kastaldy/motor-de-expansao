"""Contrato canônico da camada paralela de Vulnerabilidade para M&A (snapshots + churn).

Fonte única de verdade do schema dos snapshots semanais
(`data/staging/snapshots_concorrentes/semana=AAAA-SS/fonte=<fonte>/parte-*.parquet`, gitignored) e
do frame de churn/staleness derivado dele. **SEM I/O e SEM pandas** — só stdlib (BLK-MA-02/DEC-012).

Diferença consciente em relação ao molde `demanda_revelada/contrato.py` (só constantes): aqui as
**primitivas de derivação também SÃO o contrato**. Alterar `normalizar_texto`, os campos da chave,
o conjunto de `CAMPOS_HASH_POR_FONTE` ou a resolução do hex **re-chaveia a série inteira** e produz
churn artificial em massa — por isso elas ficam no mesmo arquivo que carrega
`VERSAO_CONTRATO_SNAPSHOT`, e qualquer mudança **exige bump** dessa versão (o BLK-MA-04 deve tratar
o bump como descontinuidade de série). Histórico de bumps do snapshot: `v1` (BLK-MA-02) -> `v2`
(BLK-MA-11 / DEC-025, saída da taxonomia do hash) -> `v3` (BLK-MA-09 / DEC-026, entrada das duas
colunas-fato de rating) -> `v4` (BLK-MA-21 / DEC-039, entrada de `fontes_lidas` e da segunda chave
de partição `fonte=`). Os TRÊS primeiros foram feitos com a série ainda VAZIA, logo sem migração.

**A janela grátis de bump FECHOU, e o `v4` é o primeiro bump COM série no disco.** Existe partição
viva (medida em 2026-08-25: `semana=2026-33`, 22.173 linhas, só `wellhub`, `v3`), e ela é o insumo
de artefatos que estão em produção. Política de convivência, que vale a partir daqui: **a partição
antiga permanece legível** — `ler_snapshots` declara `schema=` por arquivo (DEC-026), então o
pyarrow preenche o que falta partição a partição — e sai com `fontes_lidas` **nula**, que se lê como
"gravada antes do `v4`", nunca como "nenhuma fonte foi lida". O `v3` levou junto o bump de
`VERSAO_CONTRATO_CHURN` e de `VERSAO_CONTRATO_SCORE`, porque os dois schemas também mudaram; o `v4`
**não** os leva, porque nenhum dos dois derivados ganhou coluna.

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
from collections.abc import Mapping, Sequence
from datetime import date

# --------------------------------------------------------------------------- #
# Carimbos de reprodutibilidade e parâmetros do contrato
# --------------------------------------------------------------------------- #
VERSAO_CONTRATO_SNAPSHOT = "snapshots_concorrentes_v4"
VERSAO_CONTRATO_CHURN = "churn_staleness_v2"
VERSAO_CONTRATO_PRESENCA_AGREGADOR = "presenca_agregador_v1"
VERSAO_CONTRATO_SCORE = "score_vulnerabilidade_v7"

# Resolução H3 da chave de join com o Motor (mesma do M1: H3_RESOLUTION=7) - cópia read-only.
H3_RES_CONTRATO = 7

# Maturidade/retenção do contrato §6 (gate de produto 2026-07-23). NÃO alterar sem novo gate:
# contam semanas OBSERVADAS, não semanas de calendário (ver §6/§12 do contrato).
MIN_SEMANAS = 8
STALE_SEMANAS = 12

# `RETENCAO_SEMANAS` é a ÚNICA das três que conta semanas de CALENDÁRIO, e é essa assimetria que
# torna o valor um parâmetro de produto, não de disco
# `[BLK-MA-21 / DEC-039, emenda de 2026-08-26 — cadência SEMANAL]`.
#
# A cadência é UNIFORME: as três fontes rodam toda semana ISO (`unidades` no domingo, os dois
# agregadores na terça). `podar_snapshots` é keep-newest-N sobre diretórios `semana=`, então reter N
# partições retém, NO CAMINHO FELIZ, N observações de CADA fonte. Fora dele não: a fonte que perde a
# folha da semana (a curadoria recusa feed velho, o coletor cai) perde a observação, mas a semana
# continua ocupando um slot — é essa a folga que o número tem de comprar.
#
# O piso é **13**, MEDIDO (`extrair_churn_staleness` com séries sintéticas de hash constante):
# `_semanas_sem_mudanca` conta observações ESTRITAMENTE após a última mudança, logo com k semanas
# presentes vale `k-1`, contra o denominador `STALE_SEMANAS = 12` do `v4`.
#
#   | N  | semanas_sem_mudanca | v4     |                                            |
#   |----|---------------------|--------|--------------------------------------------|
#   |  8 |  7                  | 0,5833 |                                            |
#   | 12 | 11                  | 0,9167 | <- teto permanente: NUNCA satura           |
#   | 13 | 12                  | 1,0000 | <- PISO DURO; nunca descer abaixo daqui    |
#   | 26 | 25                  | 1,0000 | <- 2x o piso: satura mesmo com 50% de buraco |
#
# `26` é o menor N que ainda satura o `v4` com uma fonte perdendo METADE das semanas (26 semanas,
# 50% de falha -> 13 observações -> `semanas_sem_mudanca` = 12 -> `v4` = 1,0000, exatamente no piso).
# Disco medido em 2026-08-26 (42.535 linhas/semana somando as três fontes, 151,7 bytes/linha):
# **160,0 MB**. Não é restrição. O que restringe é a LEITURA — `ler_snapshots` carrega a série
# INTEIRA em memória (`ds.dataset(...).to_table().to_pandas()`) e o pico de RSS medido cresce
# ~70,5 MB por semana retida: N=13 -> 999 MB, N=26 -> 1,9 GB numa KVM4 de 16 GB com 6 containers.
#
# Poda POR FONTE dentro da partição (que garantiria N observações por fonte mesmo com buraco de
# folha) fica em bloco próprio: ela mexe na única função do pacote que apaga arquivo, e a margem que
# compraria já vem de graça no 26 = 2x o piso.
RETENCAO_SEMANAS = 26

# ARBITRADO, nao medido (sem serie real; revisitar no BLK-MA-06). O valor importa menos que o
# DESENHO: o rebaixamento GLOBAL da chave só ocorre se o chamador INJETAR a taxa medida (default
# `None` em `derivar_chave`/`materializar`), senão uma reavaliação automática re-chavearia o
# universo inteiro no instante em que a taxa cruzasse o limiar.
LIMIAR_SLUG_ESTAVEL = 0.90

# Folga (~55 km) sobre o bbox da UF, para não descartar academia legítima junto a divisa.
TOLERANCIA_BBOX_UF_GRAUS = 0.5

# Chaves de partição hive do snapshot (não são colunas do arquivo: vivem no caminho). A ORDEM é a
# ordem das chaves hive no caminho — `semana=AAAA-SS/fonte=<fonte>/parte-*.parquet`.
#
# Era escalar (`COLUNA_PARTICAO = "semana"`) até o BLK-MA-21 / DEC-039. A segunda chave existe
# porque duas execuções escrevem na MESMA semana ISO (a terça dos agregadores e o domingo do
# `unidades` caem na mesma semana ISO — medido): com uma chave só, `delete_matching` fazia a
# execução dos agregadores apagar a partição inteira que a do `unidades` tinha acabado de gravar
# (e vice-versa).
# Com `fonte=` a idempotência passa a ser por FOLHA — ver `escrever_particao_semana`.
COLUNAS_PARTICAO: tuple[str, ...] = ("semana", "fonte")

RE_SEMANA = re.compile(r"^\d{4}-\d{2}$")
RE_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE)

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
# 0 e a staleness morreria); `slug` NUNCA entra (rotação de UUID no slug não é mudança de negócio);
# a TAXONOMIA de atividades (`atividades`/`modalidades`) NUNCA entra `[emenda BLK-MA-11, DEC-025]`
# — ela é vocabulário da FONTE, não cadastro da academia. Medido em 2026-08-07: o WellHub renomeou
# "Musculação" para "Treino de força"/"Fisiculturismo"/"Treino Híbrido" entre maio e agosto, e o
# campo mudou em 12.314 dos 12.420 slugs comuns (**99,1%**) sem que uma única academia mudasse de
# fato. Com a taxonomia dentro do hash, a renomeação seria lida como "cadastro atualizado agora"
# para a base inteira e o sinal 4 morreria — o mesmo modo de falha que `data_coleta` já causava.
CAMPOS_HASH_POR_FONTE: dict[str, tuple[str, ...]] = {
    "totalpass": (
        "nome",
        "latitude",
        "longitude",
        "cidade",
        "uf",
        "cep",
        "endereco_formatado",
    ),
    "wellhub": (
        "nome",
        "latitude",
        "longitude",
        "cidade",
        "uf",
        "cep",
        "endereco_formatado",
    ),
    "unidades": ("nome_unidade", "latitude", "longitude"),
}
# Rede de segurança EXECUTÁVEL da regra acima: `test_campos_hash_por_fonte_exclui_os_proibidos`
# falha se qualquer um destes voltar para uma tupla de `CAMPOS_HASH_POR_FONTE`.
CAMPOS_NUNCA_HASHEADOS: frozenset[str] = frozenset(
    {"data_coleta", "slug", "modalidades", "atividades"}
)
# Declaração de TIPO dos campos de lista (ordena + normaliza tokens antes de comparar). Hoje
# nenhum campo hasheado é de lista — os dois saíram do hash pela emenda BLK-MA-11 —, então o ramo
# correspondente em `hash_campos_raspados` é caminho RESERVADO, não código morto por descuido: ele
# volta a valer se uma fonte futura hashear um campo multivalorado que NÃO seja taxonomia.
CAMPOS_LISTA: frozenset[str] = frozenset({"modalidades", "atividades"})
CAMPOS_NUMERICOS: frozenset[str] = frozenset({"latitude", "longitude"})

# --------------------------------------------------------------------------- #
# Schemas canônicos
# --------------------------------------------------------------------------- #
# Snapshot semanal: 13 colunas, nesta ORDEM. `semana` NÃO é coluna do arquivo — é chave de
# partição hive (igual ao `uf` do enriquecido em `fase1_bi_exports.py`), materializada na leitura.
#
# `fonte` é caso HÍBRIDO desde o BLK-MA-21: ela está aqui (é coluna LÓGICA do contrato, exigida pelo
# `_assert_schema_snapshot` e devolvida por `ler_snapshots`), mas virou a SEGUNDA chave de partição
# — e o pyarrow remove do arquivo toda coluna que promove a chave. Consequência medida (pyarrow
# 23.0.1): o parquet físico tem 12 colunas, não 13, e um `pd.read_parquet` de UMA folha não vê
# `fonte`. Quem lê a série pela função de produção continua vendo as 13.
CONTRATO_COLUNAS_SNAPSHOT: dict[str, str] = {
    "snapshot_date": "string",  # `data_coleta` POR LINHA (ISO) -> medidor de frescor
    "slug": "string",  # ID nativo do provedor (nulável: `unidades` não emite)
    "concorrente_id": "string",  # sha1 de produção replicado (rastreabilidade)
    "chave_snapshot": "string",  # A CHAVE DE CHURN (sha1 hex 40)
    "chave_origem": "string",  # slug | hash_estavel (rebaixamento auditável)
    "hex_id_res7": "string",  # geometria anti-PII (DEC-012) e chave de join
    "rede": "string",  # categoria de rede; metade do escopo de observabilidade
    "fonte": "string",  # totalpass | wellhub | unidades (sinal 1 do contrato §4)
    "hash_campos_raspados": "string",  # impressão digital dos campos raspados (sinal 4)
    # FATOS sem peso `[BLK-MA-09 / DEC-026]` — NÃO são componentes do score. Só o WellHub emite;
    # no TotalPass são nulos por construção e para sempre (BLK-MA-10: a nota não existe no
    # produto). Os TRÊS estados da DEC-024 sobrevivem no par: `4.81`/`105` = tem nota;
    # `NA`/`0` = existe e não tem avaliação; `NA`/`NA` = o parser não leu (scraper quebrado).
    # Ficam FORA de `CAMPOS_HASH_POR_FONTE` — a nota muda a cada avaliação e mataria o S4.
    "nota_wellhub": "Float64",  # [NOTA_WELLHUB_MIN, NOTA_WELLHUB_MAX]; nulável
    "qtd_avaliacoes_wellhub": "Int64",  # >= 0; nulável
    # `[BLK-MA-21 / DEC-039]` O recorte que a EXECUÇÃO PEDIU (`--fontes`), como CSV ordenado —
    # ex.: `"totalpass,wellhub"`. NÃO é o que a partição contém, e a diferença é o motivo de a
    # coluna existir: com a guarda de frescor da curadoria, o TotalPass pode ter sido **tentado e
    # recusado** (feed velho), e nesse caso a folha `fonte=totalpass` simplesmente não existe.
    # Inferir o recorte das folhas presentes responderia "que fontes esta PARTIÇÃO tem", que é
    # outra pergunta, e leria "tentado e recusado" como "nunca tentado".
    # Constante por execução, e redundante por linha de propósito: é o único lugar onde o
    # consumidor da série a encontra sem um segundo artefato (o custo em disco é ~0 por dictionary
    # encoding). Fora de `CAMPOS_HASH_POR_FONTE` — mudar o recorte não é o cadastro mudar.
    "fontes_lidas": "string",
    "versao_contrato": "string",  # carimbo; mudança = descontinuidade de série
}

# Domínio da nota. O piso é `1.0`, NÃO `0.0`: a nota é média de avaliações de 1 a 5 estrelas, logo
# `0.0` é aritmeticamente inalcançável — "sem avaliação" tem forma própria (`NA`/`0`). Medido na
# DEC-026 sobre 34.035 independentes com nota: `min = 1,0`, `max = 5,0`.
#
# Por que o piso importa mais que o teto: `0.0` é o retorno NATURAL de um extrator quebrado (default
# numérico de um parser que não achou o campo). Um piso em `0.0` aceitaria em silêncio justamente o
# valor mais provável de um bug, e a nota falsa entraria na série como observação legítima. O teto
# pega o modo simétrico — `481` é `4.81` sem o separador decimal.
NOTA_WELLHUB_MIN: float = 1.0
NOTA_WELLHUB_MAX: float = 5.0

# Colunas do snapshot que PODEM ser nulas. `slug` porque o feed `unidades` não o emite; as duas de
# rating porque só o WellHub as tem. O `_assert_schema_snapshot` exige não-nulo em todo o resto.
COLUNAS_SNAPSHOT_NULAVEIS: frozenset[str] = frozenset(
    {"slug", "nota_wellhub", "qtd_avaliacoes_wellhub"}
)

# Extrator de churn/staleness: 19 colunas, nesta ORDEM. `v3`/`v4`/`score_vulnerabilidade`/
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
    "nota_wellhub": "Float64",  # FATO sem peso, da ULTIMA observacao (DEC-026)
    "qtd_avaliacoes_wellhub": "Int64",  # FATO sem peso, da ULTIMA observacao (DEC-026)
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
    "hex_id_res7": "string",  # a chave (anti-PII, DEC-012) e o join
    "fontes_presentes_no_hex": "string",  # subconjunto de FONTES_AGREGADORES, `,`
    "n_agregadores_no_hex": "int64",  # {1, 2} — nunca 0 (ver docstring do módulo)
    # COLUNAS 4/5 — leia-as como TETO, nunca como número exato `[ressalva BLK-MA-03-FU1]`: elas
    # contam CHAVES distintas, e a chave muda quando `chave_origem` é rebaixado de `slug` para
    # `hash_estavel`, então a MESMA academia observada nos dois regimes sai como 2 (medido em
    # 2026-08-12). Não é caso raro: em `derivar_chave` o rebaixamento POR LINHA (slug ausente ou
    # duplicado no snapshot) é SEMPRE ativo e depende só da qualidade do feed.
    # `n_agregadores_no_hex` — e portanto o `v1` — NÃO é afetado. Quem exibir estas duas como
    # "densidade do alvo" deve cruzar com `flag_troca_chave_na_serie` do churn.
    "n_academias_independentes_totalpass": "int64",  # chaves distintas de TP no hex (TETO)
    "n_academias_independentes_wellhub": "int64",  # chaves distintas de WH no hex (TETO)
    "semana_ultima_observacao_totalpass": "string",  # relógio do PIPELINE (nulo sse contagem 0)
    "semana_ultima_observacao_wellhub": "string",  # idem, WellHub
    "snapshot_date_ultimo_totalpass": "string",  # relógio do COLETOR (nulo sse contagem 0)
    "snapshot_date_ultimo_wellhub": "string",  # idem, WellHub
    "versao_contrato": "string",  # carimbo; mudança = descontinuidade de série
}

# --------------------------------------------------------------------------- #
# Score de vulnerabilidade (D4) — BLK-MA-04
# --------------------------------------------------------------------------- #
# ORDEM CANÔNICA do `sinais_disponiveis` (molde de domínio-tupla: `STATUS_CHURN_VALIDOS`).
# A string é montada iterando ESTA tupla, nunca um `set` nem as chaves de um dict.
SINAIS_ORDEM: tuple[str, ...] = ("s1", "s2", "s3", "s4", "s6")

# Pesos-alvo. S1..S4 são os do D4 (gate de produto de 2026-07-23) e seguem **CONGELADOS e
# INTOCADOS** — este bloco os lê, nunca os altera. S6 entra POR CIMA (BLK-MA-12), e a soma-alvo
# passa de 1,00 para 1,10.
#
# **A soma deixar de ser 1,00 é inócua, e isso é uma propriedade de `renormalizar_pesos`, não uma
# licença:** ela divide pela soma dos sinais PRESENTES, nunca pelo total do dicionário. Logo o peso
# efetivo de qualquer regime que não contenha `s6` é **exatamente o mesmo de antes** — o Plano B
# segue `0,20 / 0,4667 / 0,3333`, travado por teste. Foi essa a razão de acrescentar S6 em vez de
# adotar o conjunto ilustrativo de 6 sinais do §8.3 (`S1=0,12 · S3=0,28 · S4=0,20 · S6=0,10`):
# aquele conjunto REPESA S1..S4, o que exigiria reabrir o gate de 2026-07-23 e deslocaria o ranking
# de todas as linhas, inclusive as que não têm pressão medida.
#
# `s6` NÃO está em `SINAIS_INATIVOS`: diferente do `s2` (que não tem dado nenhum), o S6 é
# calculável hoje. O que decide a disponibilidade dele é a presença do INSUMO na chamada — ver
# `_regra_de_disponibilidade` em `score.py`.
PESOS_ALVO_SINAIS: dict[str, float] = {
    "s1": 0.15,
    "s2": 0.25,
    "s3": 0.35,
    "s4": 0.25,
    "s6": 0.10,
}

# Pesos do D4 isolados, para o teste provar que o S6 não os tocou.
PESOS_ALVO_D4: dict[str, float] = {"s1": 0.15, "s2": 0.25, "s3": 0.35, "s4": 0.25}

# S2 (rating in-app) é `n/d` PERMANENTE no Plano B (contrato §7 / D3) até o BLK-MA-08 ajustar o
# coletor. Reativar o sinal 2 é remover UMA entrada desta tupla — a fórmula do score não muda.
SINAIS_INATIVOS: tuple[str, ...] = ("s2",)

# `novo` mapeia para `None` (= AUSENTE), NUNCA para `0.0`: ler "série curta demais para julgar"
# como "estável" inverteria o sinal em silêncio. As chaves são EXATAMENTE `STATUS_CHURN_VALIDOS`
# — um 5º estado futuro quebra o teste do contrato em vez de cair num default silencioso.
V3_POR_STATUS_CHURN: dict[str, float | None] = {
    "novo": None,
    "estavel": 0.0,
    "piscando": 0.7,
    "sumiu_recente": 1.0,
}

# Score de vulnerabilidade (D4): 26 colunas, nesta ORDEM. Uma linha por ACADEMIA, isto é, por
# `(fonte, chave_snapshot)` do universo de M&A (TotalPass/WellHub x independente).
#
# `v2` está AUSENTE DE PROPÓSITO (S2 é `n/d` permanente, D3 — BLK-MA-08); `hex_quente`,
# `sam_fitness_potencial` e a lista comercial são BLK-MA-05.
#
# `n_agregadores_no_hex` é `Int64` (NULÁVEL) e é a única coluna de inteiro nulável do contrato:
# a linha cujo hex não casa no join com o sinal 1 fica com `v1` AUSENTE (renormalizado para
# fora), e o `int64` nativo não carrega nulo — no miss o pandas promoveria a `float64` + `NaN`.
CONTRATO_COLUNAS_SCORE: dict[str, str] = {
    "chave_snapshot": "string",  # a chave opaca (anti-PII); metade do grão
    "fonte": "string",  # totalpass | wellhub — NUNCA `unidades`
    "rede": "string",  # sempre `independente` (universo de M&A)
    "hex_id_res7": "string",  # join com o sinal 1 e, no BLK-MA-05, hotness
    "status_churn": "string",  # FATO propagado, sem peso (G-D2)
    "nota_wellhub": "Float64",  # FATO propagado, sem peso (DEC-026)
    "qtd_avaliacoes_wellhub": "Int64",  # FATO propagado, sem peso (DEC-026)
    "v1": "float64",  # componente do S1; {0.0, 0.5} ou nulo
    "v3": "float64",  # componente do S3; {0.0, 0.7, 1.0} ou nulo
    "v4": "float64",  # componente do S4; [0, 1] ou nulo
    "v6": "float64",  # componente do S6; [0, 1) ou nulo se o insumo nao veio (BLK-MA-12)
    # AUDITORIA do v6; nulo sse `v6` nulo. O nome perdeu o sufixo `_no_hex` no BLK-MA-14: a
    # pressao passou a ter DOIS graos possiveis, e cravar um deles no nome da coluna faria o
    # contrato mentir metade das vezes. Quem diz de onde o numero veio e' `pressao_grao`.
    "pressao_competitiva": "Float64",
    # Carimbo do GRAO: `academia` (medido da coordenada da unidade) ou `hex` (do centroide).
    # Nulo exatamente quando `pressao_competitiva` e' nula. Viaja ate' o consumidor de proposito —
    # duas linhas com graos diferentes NAO estao na mesma regua, e sem o carimbo isso e' invisivel.
    "pressao_grao": "string",
    # Carimbo do UNIVERSO DE OFERTA (BLK-MA-16): `cadeias` ou `cadeias_e_independentes`. Mesma
    # regra de nulidade e mesma razao de existir do `pressao_grao`, para o OUTRO eixo — a mesma
    # academia mede 39 num universo e 65 no outro (medido em SP), e sem o carimbo as duas
    # respostas parecem a mesma grandeza.
    "universo_oferta": "string",
    "sinais_disponiveis": "string",  # subconjunto de SINAIS_ORDEM, unido por `,`
    # 0..4: o S2 nunca conta (DEC-026), mas o S6 conta QUANDO o insumo de pressao e' fornecido
    # (BLK-MA-12). Sem o insumo, o dominio volta a 0..3 e nada muda em relacao ao v2.
    "n_sinais_disponiveis": "int64",
    "score_vulnerabilidade": "float64",  # [0, 100]; nulo sse nenhum sinal disponível
    "score_vulnerabilidade_ordenavel": "float64",  # nulo enquanto `flag_score_provisorio` (G-D1)
    "flag_serie_imatura": "bool",  # propagada do churn
    "flag_staleness_interpretavel": "bool",  # propagada do churn; condiciona o S4
    "flag_score_provisorio": "bool",  # S3 E S4 indisponíveis (contrato §8.4)
    "n_agregadores_no_hex": "Int64",  # auditoria do v1; NULÁVEL (ver acima)
    "fontes_presentes_no_hex": "string",  # auditoria do v1; nulo sse a de cima for nula
    "semana_ultima_observacao": "string",  # relógio do PIPELINE (vem do churn)
    "snapshot_date_ultimo": "string",  # relógio do COLETOR (vem do churn)
    "versao_contrato": "string",  # carimbo; mudança = descontinuidade de série
}

# --------------------------------------------------------------------------- #
# Sinal 6 — pressão competitiva com decaimento por distância (BLK-MA-12)
# --------------------------------------------------------------------------- #
VERSAO_CONTRATO_PRESSAO = "pressao_competitiva_v4"

# Raio de TRUNCAMENTO, não de alcance: quem define o alcance efetivo é a forma do kernel. 2.000 m
# é o mesmo do `pressao_concorrencial_score_2km` da camada de mercado — manter o número igual é o
# que torna os dois comparáveis.
PRESSAO_RAIO_M = 2000.0

# `linear` é o kernel do contrato de mercado (triangular, zero na borda). `potencia` é o molde do
# Huff, disponível para sensibilidade mas NÃO default: o `beta` do Huff é re-calibrado a cada
# rodada contra desfecho observado (1,845 no dimensionamento vs 0,5 na demanda revelada), e o score
# de vulnerabilidade não tem desfecho contra o qual calibrar (§8: heurística, não modelo).
KERNEIS_PRESSAO: tuple[str, ...] = ("linear", "potencia")
PRESSAO_KERNEL_DEFAULT = "linear"
PRESSAO_BETA_POTENCIA = 1.5
PRESSAO_DIST_MIN_M = 50.0  # piso anti-divisão-por-zero do kernel de potência

# GRÃOS possíveis da pressão (BLK-MA-14). `academia` é o default do pipeline desde então; `hex`
# continua calculável e é o que a camada de mercado usa, mas NÃO é mais o grão do componente `v6`.
PRESSAO_GRAO_ACADEMIA = "academia"
PRESSAO_GRAO_HEX = "hex"
PRESSAO_GRAOS: tuple[str, ...] = (PRESSAO_GRAO_ACADEMIA, PRESSAO_GRAO_HEX)

# --------------------------------------------------------------------------- #
# UNIVERSO DE OFERTA do sinal 6 (BLK-MA-16)
# --------------------------------------------------------------------------- #
# O `pressao_grao` responde "de ONDE se mediu"; estas constantes respondem "QUEM conta como
# concorrência". São eixos independentes, e por isso dois carimbos e não um: o grão errado dá um
# número preciso do lugar errado, o universo errado dá um número honesto de um mundo menor.
#
# `cadeias` é o universo HISTÓRICO (BLK-MA-12 a BLK-MA-15) e segue sendo o default. Não é escolha
# de desenho: é o que `concorrentes_mapeados.parquet` contém — 4.499 pontos em 104 redes e **zero
# independentes**, porque ele nasce dos coletores `unidades_*.csv`, que são feeds de CADEIA. A
# consequência foi medida em SP (2026-08-14): **29,2% das independentes marcam pressão `0`**, e a
# leitura de "território livre" ali é artefato do insumo, não do território. Uma independente
# espremida entre oito independentes tem zero cadeia por perto e muita concorrência.
#
# ASSIMETRIA DECLARADA `[emenda BLK-MA-17 / DEC-034]`: o enum classifica a CATEGORIA que conta
# (cadeia / independente), **não a procedência** dos pontos. Desde o BLK-MA-17 o bloco de cadeias
# soma dois insumos — `concorrentes_mapeados.parquet` (feed de rede, o histórico) **e** as unidades
# de REDE que o agregador lista e que `_filtrar_universo_sinal_1` corta antes do score. A categoria
# não mudou, então o rótulo não muda; o que mudou foi a COBERTURA dela, e quem distingue as duas
# rodadas é a VERSÃO (`pressao_competitiva_v2` -> `v3`), não um terceiro valor aqui.
#
# Por que não um terceiro valor: ele tocaria todos os asserts, a CLI e a leitura de todo parquet já
# gravado, para exprimir uma distinção que a versão já carrega. Quem precisar do detalhe tem as duas
# colunas de decomposição (`oferta_cadeias_do_feed`, `n_cadeias_do_feed_no_raio`), que dizem
# exatamente quanto da oferta veio do agregador — o mesmo molde do G-D2: fato auditável ao lado do
# número, antes de qualquer uso com peso.
UNIVERSO_OFERTA_CADEIAS = "cadeias"
UNIVERSO_OFERTA_COM_INDEPENDENTES = "cadeias_e_independentes"
UNIVERSOS_OFERTA: tuple[str, ...] = (UNIVERSO_OFERTA_CADEIAS, UNIVERSO_OFERTA_COM_INDEPENDENTES)

# Peso de uma unidade na oferta, por tipo. `0,5` para a independente é **decisão de produto de
# Vinicius (2026-08-14)**, não estimativa: uma independente pressiona metade do que pressiona uma
# unidade de rede. Ele age no NUMERADOR da oferta, antes da saturação.
#
# **O que este número NÃO controla:** a compressão do topo. Medida em SP, a amplitude entre os 200
# mais pressionados cai de 7,74 para 4,19 pontos quando as independentes entram — e a causa é a
# saturação `1 - 1/(1 + oferta)`, que empurra todo mundo ao teto quando a oferta cresce. Baixar
# este peso alivia e não resolve; quem resolveria é trocar a saturação, que é justamente o que
# torna o número comparável com `pressao_concorrencial_score_2km`. Registrado aqui para quem for
# mexer no `0,5` esperando corrigir aquilo.
PESO_OFERTA_CADEIA = 1.0
PESO_OFERTA_INDEPENDENTE = 0.5

# DEDUP entre fontes: a mesma academia listada em TotalPass e WellHub são DUAS chaves por
# construção (§8.1, emenda BLK-MA-03) e contariam duas vezes na oferta.
#
# **NÃO CALIBRADO CONTRA DADO REAL, e isso é declarado de propósito:** em 2026-08-14 o feed do
# TotalPass não existe nesta estação (`concorrentes/totalpass/csvs` vazio) e o snapshot tem só
# WellHub, então não há par TP x WH para medir. O critério abaixo é ARBITRADO e travado por
# fixtures; recalibrar na primeira coleta com as duas fontes é trabalho do BLK-MA-06.
#
# Por que distância pura, sem casar nome: o custo de errar é ASSIMÉTRICO. Não deduplicar dobra a
# oferta de toda academia listada nas duas fontes — erro sistemático, em massa, invisível.
# Deduplicar um par que na verdade eram dois vizinhos distintos subtrai `0,5` de oferta de um
# ponto — erro local e pequeno. E casar por nome erraria para o outro lado: a MESMA academia sai
# como "Academia X" num feed e "X Fitness" no outro.
DEDUP_INDEPENDENTES_M = 50.0

# Resolução H3 do bucket espacial da dedup (aresta ~29 m). Serve só para não comparar todos os
# pares (19.329² = 373 M): o candidato é buscado na própria célula + um `grid_disk` de raio
# DERIVADO do limiar, e a distância real decide. É detalhe de PERFORMANCE, não de contrato —
# mudá-la não muda resultado, e é isso que o teste de equivalência contra a varredura completa
# prova.
DEDUP_H3_RES = 11

# Anéis EXTRAS de folga sobre o `k` calculado. O `k` mínimo é derivado da aresta média da
# resolução, e as células do H3 não são hexágonos regulares idênticos: a folga cobre a variação
# real de tamanho sem depender de um literal. Custa vizinhos a mais na busca (barato) e evita o
# modo de falha mais perigoso da dedup — deixar de deduplicar **em silêncio**, sem levantar nada.
DEDUP_K_MARGEM_ANEIS = 1

# --------------------------------------------------------------------------- #
# DEDUP entre o feed do AGREGADOR e o parquet de cadeias `[BLK-MA-17 / DEC-034]`
# --------------------------------------------------------------------------- #
# As unidades de REDE que o WellHub lista (2.844 na semana `2026-33`, em 83 redes) são concorrência
# REAL e hoje não pressionam ninguém: elas saem do universo do score por `_filtrar_universo_sinal_1`
# e nunca foram insumo de oferta. Parte delas já está desenhada em `concorrentes_mapeados.parquet`
# pelo feed do próprio site da rede — contá-las de novo dobraria a oferta daquele ponto. Daí a
# dedup, e daí ela ter critério e limiar PRÓPRIOS.
#
# **Por que não reusar `DEDUP_INDEPENDENTES_M = 50`:** aquele limiar foi arbitrado para o par
# TotalPass x WellHub, que compartilham a mesma geocodificação. Aqui o par é "site da rede" x "app
# do WellHub" — duas geocodificações independentes do mesmo endereço, com desvio maior.
#
# **O CRITÉRIO é conjunção-disjunção, e não distância pura, porque o custo de errar é assimétrico
# NOS DOIS SENTIDOS.** Unidades de rede que ENTRAM na oferta, por critério (medido em 2026-08-15
# sobre o feed real, 2.844 unidades contra 4.366 pontos válidos):
#
# | limiar | dedup por distância PURA | dedup por (rede, d) | **ADOTADO** (rede OU piso 50 m) |
# |---|---|---|---|
# | 30 m | 1.629 entram | 1.637 | 1.418 |
# | 50 m | 1.418 | 1.433 | 1.418 |
# | 100 m | 1.239 | 1.268 | 1.257 |
# | **150 m** | **1.134** | **1.179** | **1.171** |
# | 200 m | 1.046 | 1.121 | 1.113 |
# | 300 m | 834 | 946 | 938 |
#
#   - **Casar a `rede` salva 37 concorrentes REAIS** que a distância pura apagaria: unidades cujo
#     único vizinho a menos de 150 m é pin de OUTRA rede. Apagar concorrente real é a direção exata
#     do falso zero que a DEC-033 existe para matar. (São 45 as que têm só pin de outra rede por
#     perto; 8 delas estão a menos de 50 m e o piso colapsa de qualquer forma -> líquido de 37.)
#   - **O PISO de 50 m recupera 8 casos** de "mesmo endereço com slug de rede divergente" — o menor
#     deles a **0,0 m**, inequivocamente o mesmo estabelecimento. Sem ele, contariam em dobro.
#
# O critério final — `(rede igual E d <= 150 m) OU (d <= 50 m)` — é estritamente mais conservador
# que qualquer das duas variantes isoladas: a escolha NÃO é cosmética, e a coluna do meio da tabela
# (a variante SEM o piso) é a que o handoff do Planner citou como `1.179`.
DEDUP_CADEIA_FEED_M = 150.0
DEDUP_CADEIA_FEED_PISO_M = 50.0

# Frame de pressão POR ACADEMIA: 15 colunas, nesta ORDEM. É o insumo do `v6` desde o BLK-MA-14.
#
# POR QUE A CHAVE É `(fonte, chave_snapshot)` E NÃO SÓ A CHAVE: é o mesmo par que o score usa como
# chave primária. `chave_snapshot` sozinha não é única — ela é derivada por fonte, e a mesma
# academia listada em TotalPass e WellHub são duas linhas por construção (§8.1, emenda BLK-MA-03).
#
# **NÃO HÁ COORDENADA AQUI, e essa ausência é o contrato.** A latitude/longitude da academia entra
# no CÁLCULO (é dela que a distância é medida) e morre na função: o que sai é o agregado. A
# distinção entre CALCULAR e PERSISTIR é o que torna o grão de academia compatível com o §11 —
# antes do BLK-MA-14 o docstring do módulo confundia as duas e dava a mudança como impossível.
CONTRATO_COLUNAS_PRESSAO_ACADEMIA: dict[str, str] = {
    "fonte": "string",
    "chave_snapshot": "string",
    "pressao_competitiva": "float64",  # [0, 100); mesma régua e mesma fórmula do grão hex
    "v6": "float64",  # pressao/100 — o componente do §8.1
    "oferta_ponderada": "float64",  # soma dos pesos, TOTAL; auditoria do decaimento
    "n_concorrentes_no_raio": "int64",  # contagem CRUA, para comparar com a ponderada
    "dist_concorrente_mais_proximo_m": "float64",
    # DECOMPOSIÇÃO da oferta por tipo (BLK-MA-16). Zeradas no universo `cadeias`, onde não há
    # independente para contar. Elas respondem a pergunta que o total esconde e que muda a tese de
    # M&A: uma independente cercada de independentes é alvo diferente de uma cercada de Smart Fits.
    "oferta_independentes": "float64",  # parte de `oferta_ponderada` vinda de independente
    "n_independentes_no_raio": "int64",  # contagem CRUA das independentes (subconjunto da acima)
    # DECOMPOSIÇÃO por PROCEDÊNCIA `[BLK-MA-17 / DEC-034]`, simétrica à de cima. Elas contam a parte
    # da oferta de CADEIA que veio do agregador em vez do `concorrentes_mapeados.parquet` — a parte
    # que, até este bloco, não existia no cálculo. É o que torna o carimbo `universo_oferta`
    # auditável apesar de o rótulo dele não mencionar procedência (ver o comentário do enum).
    "oferta_cadeias_do_feed": "float64",  # parte de `oferta_ponderada` vinda de rede do agregador
    "n_cadeias_do_feed_no_raio": "int64",  # contagem CRUA delas (subconjunto de `n_concorrentes`)
    "kernel_pressao": "string",  # carimbo: qual decaimento produziu o número
    "raio_pressao_m": "float64",
    "universo_oferta": "string",  # carimbo: QUEM contou como concorrência (UNIVERSOS_OFERTA)
    "versao_contrato": "string",
}

# Frame de pressão por hex: 14 colunas, nesta ORDEM. O sufixo `_no_hex` das colunas 2-4 é
# deliberado, no molde do `presenca_agregador`: a pressão é grandeza do TERRITÓRIO, e todas as
# academias do mesmo hex herdam o mesmo valor pelo join.
#
# **ESTE FRAME DEIXOU DE SER O INSUMO DO `v6` no BLK-MA-14** — ele mede o território, e o §8.1
# passou a exigir a unidade. Continua vivo e calculável: é a grandeza comparável com o
# `pressao_concorrencial_score_2km` da camada de mercado, e é a única que faz sentido pintar num
# mapa (uma cor cobre o hexágono inteiro). Quem o injetar em `calcular_score_vulnerabilidade`
# recebe o score no grão antigo, com `pressao_grao = "hex"` carimbado na saída.
CONTRATO_COLUNAS_PRESSAO: dict[str, str] = {
    "hex_id_res7": "string",
    "pressao_competitiva_no_hex": "float64",  # [0, 100); mesma régua do mercado
    "v6_no_hex": "float64",  # pressao/100 — o componente do §8.1
    "oferta_ponderada_no_hex": "float64",  # soma dos pesos, TOTAL; auditoria do decaimento
    "n_concorrentes_no_raio": "int64",  # contagem CRUA, para comparar com a ponderada
    "dist_concorrente_mais_proximo_m": "float64",
    # Decomposição por tipo (BLK-MA-16), simétrica à do grão academia. A simetria é deliberada:
    # os dois grãos compartilham `_oferta_por_origem`, e um schema que divergisse tornaria a
    # comparação entre eles — que é a razão de o grão hex continuar vivo — silenciosamente falsa.
    "oferta_independentes_no_hex": "float64",
    "n_independentes_no_raio": "int64",
    # Procedência da oferta de CADEIA `[BLK-MA-17 / DEC-034]`, simétrica à do grão academia — pela
    # mesma razão de sempre: os dois grãos compartilham `_oferta_por_origem`, e um schema divergente
    # tornaria silenciosamente falsa a comparação entre eles.
    "oferta_cadeias_do_feed_no_hex": "float64",
    "n_cadeias_do_feed_no_raio": "int64",
    "kernel_pressao": "string",  # carimbo: qual decaimento produziu o número
    "raio_pressao_m": "float64",
    "universo_oferta": "string",  # carimbo: QUEM contou como concorrência (UNIVERSOS_OFERTA)
    "versao_contrato": "string",
}

# --------------------------------------------------------------------------- #
# Lista priorizada de alvos de M&A (D5/D6) — BLK-MA-05
# --------------------------------------------------------------------------- #
VERSAO_CONTRATO_ALVOS_MA = "alvos_ma_v4"

# Gate D5 (ratificado em 2026-07-23; reabrir exige DEC). A INVERSÃO do §2 mora aqui: comprar quer
# demanda ALTA + residual BAIXO, o OPOSTO de `abrir_agora`.
QUANTIL_SAM_QUENTE = 0.75
LIMIAR_RESIDUAL_SATURADO = 25.0
ADJACENCIA_HEX_QUENTE_K = 1

# Colunas do M1/mercado que a camada de M&A LÊ da carteira e nunca reescreve. As 5 primeiras são as
# que o §9 manda verificar; as 5 últimas são as invariantes do molde
# `enriquecer_dataframe_com_residual` — se o join mexer numa delas, o assert derruba.
COLUNAS_HOTNESS_CARTEIRA: tuple[str, ...] = (
    "uf",
    "sam_fitness_potencial",
    "score_oportunidade_residual",
    "oferta_efetiva_disponivel",
    "tese_entrada",
)
COLUNAS_M1_INVARIANTES: tuple[str, ...] = (
    "score_priorizacao",
    "rank_brasil",
    "rank_uf",
    "rank_carteira_brasil",
    "rank_carteira_uf",
)

# Camada scored (D6), grão ACADEMIA: as do score + hotness + as invariantes do M1, propagadas
# para auditoria. `hex_quente` é o nome que o §10 usa e que `score.py` reserva em
# `_COLUNAS_PROIBIDAS_MA05` — é aqui, e só aqui, que ele passa a existir.
CONTRATO_COLUNAS_ACADEMIAS_MA: dict[str, str] = {
    "chave_snapshot": "string",
    "fonte": "string",
    "hex_id_res7": "string",
    "status_churn": "string",
    "nota_wellhub": "Float64",
    "qtd_avaliacoes_wellhub": "Int64",
    "sinais_disponiveis": "string",
    "n_sinais_disponiveis": "int64",
    "score_vulnerabilidade": "float64",
    "score_vulnerabilidade_ordenavel": "float64",
    "flag_serie_imatura": "bool",
    "flag_score_provisorio": "bool",
    "hex_quente": "bool",  # o hex da academia satisfaz a conjunção do D5
    "hex_quente_vizinho": "bool",  # algum vizinho `grid_disk(k=1)` e' quente
    "proximo_de_hex_quente": "bool",  # a disjuncao do §9: o proprio OU um vizinho
    # SINAL 6 (BLK-MA-12) — PROPAGADO do score, onde ele é componente com peso desde que o insumo
    # de pressão seja fornecido. Esta camada não recalcula nada: só carrega para o entregável.
    # Nulo quando o score foi calculado sem `pressao=` — ausência de cálculo, não pressão zero.
    "pressao_competitiva": "Float64",
    "pressao_grao": "string",
    "universo_oferta": "string",  # carimbo do BLK-MA-16, propagado junto com o grao
    "v6": "float64",
    "uf": "string",
    "sam_fitness_potencial": "float64",
    "score_oportunidade_residual": "float64",
    "oferta_efetiva_disponivel": "float64",
    "tese_entrada": "string",
    "score_priorizacao": "float64",  # PROPAGADO do M1, nunca recalculado
    "versao_contrato": "string",
}

# Lista curada (D6), grão (HEX x REGIME). O §10 traz um cabeçalho de EXEMPLO, não normativo; duas
# diferenças deliberadas em relação a ele, ambas exigidas pela emenda BLK-MA-04-FU1:
#   1. `sinais_disponiveis` entra ao lado de `n_sinais_disponiveis`. Segmentar só pelo CONTADOR
#      ainda mistura réguas: `{s1,s3}` e `{s3,s4}` têm ambos `n = 2` e renormalizações diferentes.
#      A composição é a chave estrita; o contador fica por legibilidade e ordenação.
#   2. A linha é (hex, regime), não (hex). Uma média que atravessa regimes mistura réguas ANTES de
#      qualquer `sort` — a obrigação do FU1 vale para a AGREGAÇÃO, não só para a ordenação.
CONTRATO_COLUNAS_ALVOS_MA: dict[str, str] = {
    "hex_id_res7": "string",
    "uf": "string",
    "sinais_disponiveis": "string",
    "n_sinais_disponiveis": "int64",
    "n_independentes_vulneraveis": "int64",
    "score_vulnerabilidade_medio": "float64",
    "score_vulnerabilidade_max": "float64",
    "sam_fitness_potencial": "float64",
    "score_oportunidade_residual": "float64",
    "hex_quente": "bool",
    "proximo_de_hex_quente": "bool",
    "flag_serie_imatura": "bool",
    "n_com_nota_wellhub": "int64",  # FATO sem peso (DEC-026): a nota anda com a contagem
    "nota_wellhub_mediana": "Float64",
    # AGREGADOS do grao ACADEMIA (BLK-MA-14): a media e o maximo da pressao entre as academias
    # do hex. Deixou de ser `first`, e a mudanca e' obrigatoria, nao estetica — com pressao por
    # unidade a variancia DENTRO do hex passa a existir (amplitude media medida: 14,9 pontos), e
    # `first` devolveria a linha que o `groupby` viu primeiro como se fosse o hex inteiro.
    "pressao_competitiva_media": "Float64",
    "pressao_competitiva_max": "Float64",
    "v6_medio": "Float64",
    "versao_contrato": "string",
}

# --------------------------------------------------------------------------- #
# Variante NOMEADA (D1-B) — BLK-MA-15
# --------------------------------------------------------------------------- #
VERSAO_CONTRATO_ALVOS_NOMEADOS = "alvos_ma_nomeados_v5"

# O UNICO contrato desta camada que carrega IDENTIDADE e COORDENADA, autorizado pela emenda de
# 2026-08-14 a DEC-028 (decidida por Vinicius). Grao: uma linha por academia.
#
# O ARTEFATO NASCE GITIGNORED (`data/staging/`), como o D1 exige desde o inicio — e
# `_assert_destino_gitignored` transforma isso em codigo, porque `data/outputs/` e' apenas
# PARCIALMENTE versionado e um caminho errado ali poria 19 mil estabelecimentos no historico do
# git, onde um `git rm` depois nao os apaga.
#
# `lat`/`lng` sao NULAVEIS de proposito: academia com score e sem coordenada ENTRA no artefato, so'
# nao e' desenhavel. Descarta-la esconderia um alvo por acidente de coleta.
CONTRATO_COLUNAS_ALVOS_NOMEADOS: dict[str, str] = {
    "fonte": "string",
    "chave_snapshot": "string",
    "nome": "string",  # IDENTIDADE — o ponto do artefato (emenda DEC-028)
    "lat": "Float64",  # nulavel: sem coordenada a academia existe, so' nao tem pin
    "lng": "Float64",
    "hex_id_res7": "string",
    "status_churn": "string",
    "nota_wellhub": "Float64",  # FATO sem peso (DEC-026); anda SEMPRE com a contagem ao lado
    "qtd_avaliacoes_wellhub": "Int64",
    "v6": "float64",
    "pressao_competitiva": "Float64",
    "pressao_grao": "string",  # `academia` desde a DEC-029
    "universo_oferta": "string",  # `cadeias_e_independentes` desde a DEC-033
    # AUDITORIA DA PRESSAO NA TELA (BLK-MA-18). Elas nao entram em conta nenhuma: existem porque a
    # pressao SOZINHA nao e' legivel. A saturacao `100(1-1/(1+o))` gasta METADE da escala numa
    # unica unidade equivalente, entao `40,4` significa "0,68 concorrentes efetivos" e nao "40% de
    # pressao" — leitura que um numero de 0 a 100 num pin praticamente convida a fazer.
    # Com a contagem ao lado, o operador confere no mapa: conta os pins e o numero fecha.
    "n_concorrentes_no_raio": "Int64",  # contagem CRUA no raio (nulavel: sem pressao, sem contagem)
    "n_independentes_no_raio": "Int64",  # quantos daqueles sao independentes (o resto e' cadeia)
    # `[BLK-MA-17 / DEC-034]` Quantos dos `n_concorrentes_no_raio` sao unidades de REDE vindas do
    # agregador. Ela existe porque o tooltip promete conferencia visual ("conta os pins e o numero
    # fecha") e essas unidades **nao tem pin desenhado** no piloto: o mapa so' desenha os pins de
    # cadeia do funil e as independentes nomeadas. A coluna DECLARA o tamanho da lacuna em vez de
    # deixar a contagem nao bater sem explicacao. `Int64` (nulavel), como as duas contagens acima —
    # ausencia de medicao e' nula, nunca zero.
    "n_cadeias_do_feed_no_raio": "Int64",
    "oferta_ponderada": "Float64",  # concorrentes EFETIVOS (ja' com o decaimento)
    "dist_concorrente_mais_proximo_m": "Float64",  # responde "quao perto", que a soma esconde
    "sinais_disponiveis": "string",
    "n_sinais_disponiveis": "int64",
    "score_vulnerabilidade": "float64",
    "score_vulnerabilidade_ordenavel": "float64",
    "flag_score_provisorio": "bool",
    "versao_contrato": "string",
}

# `[BLK-MA-17 metade 1 / DEC-035]` Artefato NOMEADO das unidades de REDE do agregador.
#
# Ele existe porque as 2.844 unidades de rede que o WellHub lista entram na OFERTA do sinal 6 desde
# a DEC-034 e nao aparecem em lugar nenhum da tela — `_filtrar_universo_sinal_1` as corta antes do
# score, e a camada de exibicao herdou esse corte sem ter a mesma razao para te-lo: o que nao serve
# para rede e' a REGUA DE SCORE, nao a leitura.
#
# **FATO SIM, SCORE NAO.** Nao ha `score_vulnerabilidade` nem `score_vulnerabilidade_ordenavel`
# aqui, e a ausencia e' a decisao, nao um esquecimento: S1 e S3 medem outra coisa numa rede. A
# negociacao com o agregador e' CENTRALIZADA, e o S3 e' correlacionado — top 5 = 48,4% das unidades,
# maximo 440 numa rede so'. Quando a Panobianco sair do WellHub, 440 unidades viram `sumiu_recente`
# no mesmo dia e o score leria um evento de negociacao como 440 alvos. O S6 nao tem esse defeito: e'
# geografico e nao sabe se a academia e' de rede. Molde do G-D2 e da DEC-026 — o fato entra antes do
# peso.
VERSAO_CONTRATO_REDES_NOMEADAS = "redes_ma_nomeadas_v2"

CONTRATO_COLUNAS_REDES_NOMEADAS: dict[str, str] = {
    "fonte": "string",
    "chave_snapshot": "string",
    "nome": "string",  # IDENTIDADE — mesmo regime do nomeado de independentes (emenda DEC-028)
    "rede": "string",  # o que distingue este artefato do outro; nunca `independente`
    "lat": "Float64",
    "lng": "Float64",
    "hex_id_res7": "string",
    # FATOS SEM PESO, os mesmos tres que a DEC-035 autoriza propagar.
    "status_churn": "string",
    "nota_wellhub": "Float64",
    "qtd_avaliacoes_wellhub": "Int64",
    # O SINAL 6 e a auditoria dele. `v6` fica DE FORA de proposito: ele e' o componente normalizado
    # que alimenta um score que este artefato nao emite, e sozinho seria `pressao/100` — redundante
    # e sugerindo um composto que nao existe aqui.
    "pressao_competitiva": "Float64",
    "pressao_grao": "string",
    "universo_oferta": "string",
    "n_concorrentes_no_raio": "Int64",
    "n_independentes_no_raio": "Int64",
    "n_cadeias_do_feed_no_raio": "Int64",
    "oferta_ponderada": "Float64",
    "dist_concorrente_mais_proximo_m": "Float64",
    # PRECEDENCIA DE PIN, herdada de graca da dedup da DEC-034 e por isso nao e' regra nova: as
    # sobreviventes sao, POR CONSTRUCAO, exatamente as unidades sem ponto equivalente em
    # `concorrentes_mapeados` — logo as unicas sem pin ja' desenhado no funil. `True` = desenhar pin
    # proprio; `False` = o pin do funil ja' cobre aquele endereco, e desenhar outro criaria dois
    # pins no mesmo lugar.
    "tem_pin_proprio": "boolean",
    "versao_contrato": "string",
}

# `[BLK-MA-17-FU4 / emenda DEC-034]` Resolucao do bucket da passagem por NOME.
#
# A dedup por distancia usa `DEDUP_H3_RES = 11` (aresta 28,66 m), que e' certa para limiares de
# dezenas de metros. Para os 1.200 m do casamento por nome ela custaria `grid_disk(k=31)` -- 2.977
# celulas por ponto. Na resolucao 8 (aresta 531 m) o mesmo alcance sai com `k=4`, 61 celulas: 49x
# menos varredura para a MESMA cobertura.
DEDUP_NOME_H3_RES = 8

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

    `CAMPOS_NUNCA_HASHEADOS` e' imposto AQUI, em runtime (BLK-MA-02-FU1, m3). Antes era so' prosa:
    injetar `data_coleta` em `CAMPOS_HASH_POR_FONTE` nao levantava nada, e o efeito seria mudo e
    fatal — todo cadastro pareceria "alterado" a cada coleta, `semanas_sem_mudanca` nunca cresceria
    e o S4 morreria. E' o mesmo modo de falha que motivou manter a nota fora do hash (DEC-026).
    """
    chave_fonte = str(fonte)
    campos_da_fonte = CAMPOS_HASH_POR_FONTE.get(chave_fonte)
    if campos_da_fonte is None:
        raise ValueError(f"fonte fora do contrato; aceitas: {sorted(CAMPOS_HASH_POR_FONTE)}")
    proibidos = sorted(set(campos_da_fonte) & CAMPOS_NUNCA_HASHEADOS)
    if proibidos:
        raise ValueError(
            f"campo(s) de `CAMPOS_NUNCA_HASHEADOS` em CAMPOS_HASH_POR_FONTE[{chave_fonte!r}]: "
            f"{proibidos} — hashea-los mataria o S4 (staleness)"
        )
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


# --------------------------------------------------------------------------- #
# Primitiva do score de vulnerabilidade (D4) — mora ao lado dos pesos de propósito
# --------------------------------------------------------------------------- #
def renormalizar_pesos(disponiveis: Sequence[str]) -> dict[str, float]:
    """Pesos-alvo do D4 restritos a `disponiveis`, reescalados para somar `1,0`.

    É a implementação GENÉRICA da regra do §8.4 do contrato do epic ("dropar o peso do sinal
    ausente/imaturo e reescalar os restantes"). Os pesos efetivos do Plano B saem daqui como
    CONSEQUÊNCIA — `renormalizar_pesos(["s1", "s3", "s4"])` devolve `~0,20 / ~0,467 / ~0,333` —,
    e por isso esses três números **nunca** são digitados no código: reativar o S2 (BLK-MA-08) é
    remover uma entrada de `SINAIS_INATIVOS`, sem tocar em fórmula alguma.

    Devolve `{}` quando `disponiveis` é vazio — o chamador trata isso como score AUSENTE, nunca
    como `0` (zero é uma afirmação de solidez; ausência é ausência). Itera `SINAIS_ORDEM` para o
    dicionário sair determinístico, e duplicatas na entrada colapsam. Sinal fora de
    `SINAIS_ORDEM` levanta `ValueError`.

    **Esta primitiva NÃO conhece `SINAIS_INATIVOS`** e aceita `"s2"` de bom grado, porque ele está
    em `SINAIS_ORDEM` `[registro BLK-MA-04-FU1]`. Não é defeito: a função é sobre PESOS, e quem
    decide disponibilidade é `_disponibilidade_efetiva` em `score.py`, que força `s2` a `False`
    enquanto ele estiver naquela tupla. Registrado aqui para quem for reativar o sinal 2 não
    procurar o gate no lugar errado.
    """
    pedidos = {str(s) for s in disponiveis}
    desconhecidos = sorted(pedidos - set(SINAIS_ORDEM))
    if desconhecidos:
        raise ValueError(f"sinal fora de SINAIS_ORDEM {list(SINAIS_ORDEM)}: {desconhecidos}")
    presentes = [s for s in SINAIS_ORDEM if s in pedidos]
    if not presentes:
        return {}
    soma = sum(PESOS_ALVO_SINAIS[s] for s in presentes)
    return {s: PESOS_ALVO_SINAIS[s] / soma for s in presentes}


__all__ = [
    "VERSAO_CONTRATO_SNAPSHOT",
    "VERSAO_CONTRATO_CHURN",
    "VERSAO_CONTRATO_PRESENCA_AGREGADOR",
    "VERSAO_CONTRATO_SCORE",
    "H3_RES_CONTRATO",
    "MIN_SEMANAS",
    "STALE_SEMANAS",
    "RETENCAO_SEMANAS",
    "LIMIAR_SLUG_ESTAVEL",
    "TOLERANCIA_BBOX_UF_GRAUS",
    "COLUNAS_PARTICAO",
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
    "COLUNAS_SNAPSHOT_NULAVEIS",
    "CAMPOS_LISTA",
    "CAMPOS_NUMERICOS",
    "CONTRATO_COLUNAS_SNAPSHOT",
    "CONTRATO_COLUNAS_CHURN",
    "CONTRATO_COLUNAS_PRESENCA_AGREGADOR",
    "CONTRATO_COLUNAS_SCORE",
    "SINAIS_ORDEM",
    "SINAIS_INATIVOS",
    "PESOS_ALVO_SINAIS",
    "V3_POR_STATUS_CHURN",
    "VERSAO_CONTRATO_PRESSAO",
    "PRESSAO_RAIO_M",
    "PRESSAO_KERNEL_DEFAULT",
    "PRESSAO_BETA_POTENCIA",
    "PRESSAO_DIST_MIN_M",
    "KERNEIS_PRESSAO",
    "CONTRATO_COLUNAS_PRESSAO",
    "CONTRATO_COLUNAS_PRESSAO_ACADEMIA",
    "PRESSAO_GRAOS",
    "PRESSAO_GRAO_ACADEMIA",
    "PRESSAO_GRAO_HEX",
    "UNIVERSOS_OFERTA",
    "UNIVERSO_OFERTA_CADEIAS",
    "UNIVERSO_OFERTA_COM_INDEPENDENTES",
    "PESO_OFERTA_CADEIA",
    "PESO_OFERTA_INDEPENDENTE",
    "DEDUP_INDEPENDENTES_M",
    "DEDUP_H3_RES",
    "DEDUP_NOME_H3_RES",
    "DEDUP_K_MARGEM_ANEIS",
    "DEDUP_CADEIA_FEED_M",
    "DEDUP_CADEIA_FEED_PISO_M",
    "VERSAO_CONTRATO_ALVOS_MA",
    "QUANTIL_SAM_QUENTE",
    "LIMIAR_RESIDUAL_SATURADO",
    "ADJACENCIA_HEX_QUENTE_K",
    "COLUNAS_HOTNESS_CARTEIRA",
    "COLUNAS_M1_INVARIANTES",
    "CONTRATO_COLUNAS_ACADEMIAS_MA",
    "CONTRATO_COLUNAS_ALVOS_MA",
    "CONTRATO_COLUNAS_ALVOS_NOMEADOS",
    "VERSAO_CONTRATO_ALVOS_NOMEADOS",
    "CONTRATO_COLUNAS_REDES_NOMEADAS",
    "VERSAO_CONTRATO_REDES_NOMEADAS",
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
    "renormalizar_pesos",
]
