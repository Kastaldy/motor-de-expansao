"""Classificação anti-PII das academias menores por CATEGORIA DE REDE (BLK-TP-08-FU).

Estende a ingestão anti-PII do TP-08 (`oferta_academias_menores.py`) com um passo de
CLASSIFICAÇÃO na FRONTEIRA: cada academia recebe uma categoria `rede_menor` derivada do
`Nome_Academia` cru (só em memória) por matching de TOKEN com word-boundary contra uma
lista CURADA das 107 redes de `concorrentes_mapeados` (39 do registro histórico + as 68
com coletor no GymScraping — VinhoAbencoado/GymScraping, DEC-013); o nome/coords/cluster
são DROPADOS imediatamente. Produz dois artefatos gitignored/NÃO oficiais:

  (a) `data/staging/oferta_academias_menores_rede_h3.parquet` — oferta por `hex_id × rede_menor`
      (formato LONGO), habilitando o dedup FINO por rede vs `concorrentes_mapeados`.
  (b) `data/staging/capacidade_media_por_rede.parquet` — média/mediana de alunos por rede.

Gate humano (APROVADO por Felipe Silva em 2026-07-02):
  (A) matching por TOKEN com word-boundary `\\b…\\b` + lista curada; precisão > recall
      (tokens curtos ambíguos `live`/`race`/`jab`/`phd`/`kore`/`evoque`/`gavioes` curados);
  (B) rede com N < 3 filiais no dump → colapsa em `independente` (anti-reidentificação);
  (C) artefato de oferta em formato LONGO (`hex_id × rede_menor`);
  (D) capacidade reporta média+mediana, valor recomendado = MEDIANA, `flag_confiavel` N≥10.

Anti-PII por construção (DEC-012): `Nome_Academia`/`Latitude`/`Longitude`/`Cluster_ID` são
descartados logo após derivar `hex_id` + `rede_menor`; nunca persistidos/logados;
`Total_Alunos_Cluster` NUNCA é somado; `rede_menor` é sempre CATEGORIA (nunca o nome) e,
por (B), não singulariza um estabelecimento. Fonte real (`NAO_ABRA/`) nunca versionada;
testes usam fixtures sintéticas.

READ-ONLY sobre o M1: pacote DISJUNTO — nunca importa de `pipelines/m1/`, `censo_*`,
`dashboard/` nem `api`; não recompõe `score_oportunidade_residual` nem regenera parquets
de mercado (isso é BLK-TP-06-FU1 / BLK-TP-09, sob gate próprio). A oferta é insumo
OBSERVADO (DEC-009), NUNCA preditor geográfico de magnitude.

API h3 = v4 (`latlng_to_cell`/`get_resolution`/`is_valid_cell`).
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import h3
import pandas as pd

from .contrato import H3_RES_CONTRATO
from .oferta_academias_menores import (
    _COLUNAS_DROP_FRONTEIRA,
    _COLUNAS_PII_LOCAIS,
    CONCORRENTES_DEFAULT,
    FONTE_DEFAULT,
    _to_cell,
)

# Carimbos de reprodutibilidade dos 2 contratos (gravados em todas as linhas).
VERSAO_CONTRATO_OFERTA_MENORES_REDE = "oferta_menores_rede_v1"
VERSAO_CONTRATO_CAP_REDE = "capacidade_media_rede_v1"

# Categoria para academias não-classificáveis ou colapsadas por anti-reidentificação.
CATEGORIA_INDEPENDENTE = "independente"

# Gate (B): rede com N_filiais no dump < este limiar colapsa em `independente`.
N_MINIMO_ANTI_REIDENTIFICACAO = 3
# Gate (D): rede com N_filiais >= este limiar recebe `flag_confiavel=True`.
N_MINIMO_CONFIABILIDADE = 10

# Caminhos default (fonte gitignored em NAO_ABRA/; parquets gitignored em staging).
DESTINO_REDE_DEFAULT = Path("data/staging/oferta_academias_menores_rede_h3.parquet")
DESTINO_CAP_DEFAULT = Path("data/staging/capacidade_media_por_rede.parquet")
RELATORIO_REDE_DEFAULT = Path("data/reports/scratch/rede_menor_classificacao_qualidade.md")

# --------------------------------------------------------------------------------------
# Vocabulário CURADO (gate A). Cada `rede_menor` (categoria canônica = valor da coluna
# `rede` de `concorrentes_mapeados`) mapeia para uma tupla de TOKENS de matching. Ordem do
# dict = precedência de first-match (redes mais específicas/compostas primeiro). Todos os
# tokens são casados por word-boundary `\b…\b` (nunca substring). Tokens multi-palavra
# viram `\btoken1\s+token2\b`. Tokens curtos/ambíguos (`live`/`race`/`jab`/`phd`/`kore`/
# `evoque`/`gavioes`) foram CURADOS: só entram via marca COMPOSTA (2 palavras) — nome sem o
# contexto composto cai em `independente` (precisão > recall).
# --------------------------------------------------------------------------------------
VOCABULARIO_REDES: dict[str, tuple[str, ...]] = {
    "smart_fit": ("smart fit", "smartfit"),
    "panobianco": ("panobianco",),
    "bluefit": ("bluefit", "blue fit"),
    "selfit": ("selfit",),
    "pratique": ("pratique",),
    "bodytech": ("bodytech", "body tech"),
    # `phd` sozinho é ambíguo → só a marca composta.
    "phd_sports": ("phd sports", "phd sport"),
    "velocity": ("velocity",),
    "allp_fit": ("allp fit", "allp"),
    "26fit": ("26fit", "26 fit"),
    "engenharia_do_corpo": ("engenharia do corpo",),
    "vidya_studio": ("vidya",),
    "contorno_do_corpo": ("contorno do corpo",),
    # `evoque` mantido como token único (marca distintiva de baixa colisão).
    "evoque": ("evoque",),
    "tonus_gym": ("tonus gym", "tonus"),
    "bio_ritmo": ("bio ritmo", "bioritmo"),
    "aera_pilates": ("aera pilates",),
    "alpha_fitness": ("alpha fitness", "alpha fit"),
    "greenlife": ("greenlife", "green life"),
    "xprime": ("xprime", "x prime"),
    # `kore` sozinho é ambíguo (casa "korean"/"score" não, mas colide com nomes próprios) →
    # só a marca composta com contexto de academia.
    "kore": ("kore fit", "kore gym"),
    "cia_athletica": ("cia athletica", "cia atletica"),
    "world_gym": ("world gym",),
    "red_fitness": ("red fitness",),
    # Tokens curtos ambíguos (gate A) — SÓ a marca composta da rede-mãe:
    "live": ("live academia", "live fit"),
    "race_bootcamp": ("race bootcamp",),
    "jab_house": ("jab house",),
    # `gavioes` é nome próprio comum (torcida/bairro) → exige contexto de academia.
    "gavioes": ("gavioes academia", "gavioes fit"),
    # ── Redes do registro do dashboard que faltavam aqui (11) ─────────────────────────
    # `COMPETITOR_SPECS`/`COMPETITOR_BRANDS` já traziam 39 redes; este vocabulário cobria
    # só 28 — as 11 abaixo caíam em `independente` mesmo tendo concorrente mapeado.
    "a_fitness": ("a fitness",),
    "biohit": ("biohit",),
    # `evolve` mantido como token único (marca distintiva, mesmo critério de `evoque`).
    "evolve": ("evolve",),
    "feira_fitness": ("feira fitness",),
    # `formula` sozinho é genérico (fórmula 1 / fórmula magistral) → só a marca composta.
    "formula": ("formula academia", "academia formula"),
    "motion_fit": ("motion fit", "motionfit"),
    "my_box": ("my box",),
    "pacer": ("pacer",),
    "pro3": ("pro3", "pro 3"),
    # `red fit` NÃO casa "red fitness" (word-boundary); `red_fitness` já vem antes.
    "redfit": ("redfit", "red fit"),
    "skyfit": ("skyfit", "sky fit"),
    # ── 68 redes com coletor no GymScraping (VinhoAbencoado/GymScraping, DEC-013) ─────
    # Mesmo critério do gate A: marca distintiva → token único; palavra genérica
    # (`one`, `hi`, `premium`, `universal`, `wave`, `america`, `cristal`…) → SÓ marca
    # COMPOSTA com contexto de academia. Ordem = precedência: `force_one` vem antes de
    # `one` para que "Force One Academia" não caia em `one`.
    "a_melhor_academia": ("a melhor academia",),
    "academia_do_parque": ("academia do parque",),
    "acuas_fitness": ("acuas fitness", "acuas"),
    "ad3": ("ad3",),
    "ajuste": ("ajuste academia", "academia ajuste", "ajuste fitness"),
    "america": ("america academia", "academia america", "america fitness"),
    "bg_fitness": ("bg fitness",),
    "biofisic": ("biofisic",),
    "body_shop": ("body shop",),
    "bulkfit": ("bulkfit", "bulk fit"),
    "burnfit": ("burnfit", "burn fit"),
    "caixa_magica": ("caixa magica",),
    "california": ("california academia", "academia california", "california fitness"),
    "ciafit": ("ciafit", "cia fit"),
    "companhia_fit": ("companhia fit", "companhiafit"),
    "competition": ("competition academia", "competition fitness", "competition gym"),
    "corpo_e_saude": ("corpo e saude",),
    "cristal": ("cristal academia", "academia cristal", "cristal fitness"),
    "ctrc": ("ctrc",),
    "dffit": ("dffit", "df fit"),
    "domofit": ("domofit", "domo fit"),
    "flexfitness": ("flexfitness", "flex fitness"),
    "force_one": ("force one",),
    "gofit": ("gofit", "go fit"),
    "grecoforma": ("grecoforma", "greco forma"),
    "gymflix": ("gymflix",),
    "hammer": ("hammer academia", "academia hammer", "hammer fitness"),
    # `hi` sozinho é ruído puro (2 letras) → só a marca composta.
    "hi": ("hi academia", "academia hi"),
    "inova": ("inova academia", "academia inova", "inova fitness"),
    "ironberg": ("ironberg", "iron berg"),
    "korpus": ("korpus",),
    "malibu_fitness": ("malibu fitness", "malibu academia", "malibu"),
    "mansao_maromba": ("mansao maromba",),
    "marra_fit": ("marra fit", "marrafit"),
    "match_fit": ("match fit", "matchfit"),
    "moinhos_fitness": ("moinhos fitness", "moinhos fit", "moinhosfit"),
    "monstrao": ("monstrao academia", "academia monstrao", "monstrao fitness"),
    "nadarte": ("nadarte",),
    "nation_ct": ("nation ct", "nation academia"),
    "novafit": ("novafit", "nova fit"),
    "one": ("one academia", "academia one", "one fitness"),
    "paulo_bedeu": ("paulo bedeu", "bedeu"),
    "performance": ("performance academia", "academia performance", "performance fitness"),
    "power_fit": ("power fit", "powerfit"),
    "premium": ("premium academia", "academia premium", "premium fitness"),
    "profit": ("profit academia", "profit fitness", "profit gym"),
    "rede_lifefit": ("lifefit", "life fit"),
    "reebok_sports_club": ("reebok sports club", "reebok sports", "reebok"),
    # `romero` sozinho é sobrenome comum → só a marca composta.
    "romero_training": ("romero training",),
    "rtesser": ("rtesser", "r tesser", "tesser"),
    "runner": ("runner academia", "academia runner", "runner fitness"),
    "simplifit": ("simplifit", "simpli fit"),
    "sportdata": ("sportdata", "sport data"),
    "summit_fitness": ("summit fitness", "summit academia"),
    "target_gym": ("target gym", "target academia", "target fitness"),
    "tem_esportes": ("tem esportes",),
    "the_simple_gym": ("the simple gym", "simple gym"),
    "tntfit": ("tntfit", "tnt fit"),
    "topfit": ("topfit", "top fit"),
    "ufit": ("ufit", "u fit"),
    "universal": ("universal academia", "academia universal", "universal fitness"),
    "uplay": ("uplay", "u play"),
    "usina_do_corpo": ("usina do corpo",),
    "vasco_neto": ("vasco neto",),
    "voi_fit": ("voi fit", "voifit"),
    "wave": ("wave academia", "academia wave", "wave fitness"),
    "wellness_club": ("wellness club",),
    "ymca": ("ymca",),
}

# Regexes pré-compilados por rede (ordem estável = precedência first-match).
_TOKEN_REGEXES: dict[str, tuple[re.Pattern[str], ...]] = {
    rede: tuple(
        re.compile(r"\b" + r"\s+".join(re.escape(p) for p in tok.split()) + r"\b")
        for tok in tokens
    )
    for rede, tokens in VOCABULARIO_REDES.items()
}

_PONTUACAO_RE = re.compile(r"[^\w\s]", flags=re.UNICODE)
_ESPACOS_RE = re.compile(r"\s+")


def _normalizar_nome(nome: object) -> str:
    """Normaliza o nome: lower + sem acento + sem pontuação + espaços colapsados.

    Puro/stdlib (`unicodedata` + `re`). Retorna string normalizada tokenizável. O nome
    cru só transita em memória; nunca é persistido/logado.
    """
    if nome is None:
        return ""
    texto = str(nome)
    if not texto or texto.lower() == "nan":
        return ""
    # NFKD + strip de combining marks (remove acentos sem dep nova).
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.lower()
    texto = _PONTUACAO_RE.sub(" ", texto)
    texto = _ESPACOS_RE.sub(" ", texto).strip()
    return texto


def classificar_rede(nome: object) -> str:
    """Classifica um nome cru numa categoria `rede_menor` por token com word-boundary.

    Normaliza e testa cada token (word-boundary `\\b…\\b`, nunca substring) na ordem
    determinística de `VOCABULARIO_REDES` (first-match vence); sem match → `independente`.
    Nunca retorna/loga o nome cru.
    """
    norm = _normalizar_nome(nome)
    if not norm:
        return CATEGORIA_INDEPENDENTE
    for rede, regexes in _TOKEN_REGEXES.items():
        for rgx in regexes:
            if rgx.search(norm):
                return rede
    return CATEGORIA_INDEPENDENTE


def _colapsar_baixa_cardinalidade(
    rede_por_academia: pd.Series, n_min: int = N_MINIMO_ANTI_REIDENTIFICACAO
) -> pd.Series:
    """Colapsa em `independente` toda rede com N_filiais < ``n_min`` (anti-reidentificação).

    Conta filiais classificadas por `rede_menor` no dump inteiro; qualquer rede rara
    (baixíssima cardinalidade) é reescrita ANTES de qualquer agregação/persistência.
    `independente` nunca é colapsada (é o próprio bucket residual).
    """
    contagem = rede_por_academia.value_counts()
    raras = {
        rede
        for rede, n in contagem.items()
        if rede != CATEGORIA_INDEPENDENTE and int(n) < n_min
    }
    if not raras:
        return rede_por_academia
    return rede_por_academia.where(~rede_por_academia.isin(raras), CATEGORIA_INDEPENDENTE)


# Ordem e dtypes canônicos do parquet de oferta (contrato `oferta_menores_rede_v1`).
CONTRATO_COLUNAS_OFERTA_MENORES_REDE: dict[str, str] = {
    "hex_id": "string",                    # H3 res-7 (chave de join)
    "rede_menor": "string",                # categoria (nunca o nome); `independente` residual
    "n_academias_menores": "int64",        # nº academias no par hex×rede
    "alunos_academias_menores": "int64",   # Σ `Alunos_Academia` (NUNCA Total_Alunos_Cluster)
    "versao_contrato": "string",           # carimbo de reprodutibilidade
}

# Ordem e dtypes canônicos do parquet de capacidade (contrato `capacidade_media_rede_v1`).
CONTRATO_COLUNAS_CAP_REDE: dict[str, str] = {
    "rede_menor": "string",
    "media_alunos": "float64",
    "mediana_alunos": "float64",
    "n_filiais": "int64",
    "flag_confiavel": "bool",
    "versao_contrato": "string",
}


def _ler_e_derivar_hex_rede(
    fonte: Path, *, n_min_anti_reid: int = N_MINIMO_ANTI_REIDENTIFICACAO
) -> pd.DataFrame:
    """Lê o xlsx, deriva `hex_id` + `rede_menor` na FRONTEIRA e dropa PII imediatamente.

    Retorna frame SEM PII com colunas `hex_id`, `rede_menor`, `Alunos_Academia`. Nunca
    persiste/loga `Latitude`/`Longitude`/`Nome_Academia`/`Cluster_ID`. O colapso de baixa
    cardinalidade (gate B) é aplicado AQUI, antes de qualquer agregação/persistência.
    """
    df = pd.read_excel(Path(fonte), sheet_name=0)

    # Deriva o hex direto das coords brutas (fronteira).
    hex_ids = [
        _to_cell(lat, lng)
        for lat, lng in zip(df.get("Latitude"), df.get("Longitude"), strict=False)
    ]
    # Classifica a rede a partir do nome cru — SÓ em memória, aqui.
    redes = [classificar_rede(n) for n in df.get("Nome_Academia", pd.Series(dtype="object"))]

    # DROP-PII na fronteira: descarta coords/nome/cluster imediatamente.
    df = df.drop(columns=[c for c in _COLUNAS_DROP_FRONTEIRA if c in df.columns])
    df["hex_id"] = hex_ids
    df["rede_menor"] = redes
    df = df.dropna(subset=["hex_id"])

    alunos = pd.to_numeric(df.get("Alunos_Academia"), errors="coerce").fillna(0)
    out = pd.DataFrame(
        {
            "hex_id": df["hex_id"].to_numpy(),
            "rede_menor": pd.Series(df["rede_menor"].to_numpy(), dtype="object"),
            "Alunos_Academia": alunos.to_numpy(),
        }
    )
    # Anti-reidentificação (gate B): colapsa redes raras em `independente`.
    out["rede_menor"] = _colapsar_baixa_cardinalidade(
        out["rede_menor"], n_min=n_min_anti_reid
    )
    return out


def _agregar_h3_rede(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega por `(hex_id, rede_menor)` (formato LONGO): contagem e Σ alunos.

    `Total_Alunos_Cluster` NUNCA é somado (não está no frame). Só `Alunos_Academia`.
    """
    g = df.groupby(["hex_id", "rede_menor"], dropna=False)
    out = pd.DataFrame(
        {
            "n_academias_menores": g.size(),
            "alunos_academias_menores": g["Alunos_Academia"].sum(),
        }
    ).reset_index()

    out["n_academias_menores"] = out["n_academias_menores"].round().astype("int64")
    out["alunos_academias_menores"] = out["alunos_academias_menores"].round().astype("int64")
    out["hex_id"] = out["hex_id"].astype("string")
    out["rede_menor"] = out["rede_menor"].astype("string")
    out["versao_contrato"] = pd.Series(
        [VERSAO_CONTRATO_OFERTA_MENORES_REDE] * len(out), dtype="string"
    )

    out = out[list(CONTRATO_COLUNAS_OFERTA_MENORES_REDE.keys())]
    out = out.sort_values(["hex_id", "rede_menor"]).reset_index(drop=True)
    return out


def capacidade_media_por_rede(df_fronteira: pd.DataFrame) -> pd.DataFrame:
    """Agrega `Alunos_Academia` por `rede_menor` → média/mediana/N filiais + `flag_confiavel`.

    EXCLUI a linha `independente` (média de rede heterogênea não é capacidade de rede).
    Ordena por `n_filiais` desc. Valor recomendado ao consumo = MEDIANA (gate D).
    """
    df = df_fronteira[df_fronteira["rede_menor"] != CATEGORIA_INDEPENDENTE]
    g = df.groupby("rede_menor")
    out = pd.DataFrame(
        {
            "media_alunos": g["Alunos_Academia"].mean(),
            "mediana_alunos": g["Alunos_Academia"].median(),
            "n_filiais": g.size(),
        }
    ).reset_index()

    out["media_alunos"] = out["media_alunos"].astype("float64")
    out["mediana_alunos"] = out["mediana_alunos"].astype("float64")
    out["n_filiais"] = out["n_filiais"].round().astype("int64")
    out["flag_confiavel"] = out["n_filiais"] >= N_MINIMO_CONFIABILIDADE
    out["rede_menor"] = out["rede_menor"].astype("string")
    out["versao_contrato"] = pd.Series(
        [VERSAO_CONTRATO_CAP_REDE] * len(out), dtype="string"
    )

    out = out[list(CONTRATO_COLUNAS_CAP_REDE.keys())]
    out = out.sort_values(
        ["n_filiais", "rede_menor"], ascending=[False, True]
    ).reset_index(drop=True)
    return out


def _assert_sem_pii_rede(df: pd.DataFrame, contrato: dict[str, str]) -> None:
    """Falha se o frame tiver coluna fora do contrato ou alguma coluna PII local."""
    extras = set(df.columns) - set(contrato)
    if extras:
        raise ValueError(f"colunas fora do contrato no parquet de saída: {sorted(extras)}")
    pii = {c for c in df.columns if c.lower() in _COLUNAS_PII_LOCAIS}
    if pii:
        raise ValueError(f"colunas PII proibidas no parquet de saída: {sorted(pii)}")


def _assert_res7(df: pd.DataFrame) -> None:
    """Falha se algum hex_id não for H3 res-7 válido."""
    invalidos: list[str] = []
    for hid in df["hex_id"]:
        h = str(hid)
        if not h3.is_valid_cell(h) or h3.get_resolution(h) != H3_RES_CONTRATO:
            invalidos.append(h)
            if len(invalidos) >= 5:
                break
    if invalidos:
        raise ValueError(f"hex_id fora de res-{H3_RES_CONTRATO}: amostra {invalidos}")


def ingerir_oferta_menores_por_rede(
    fonte: Path = FONTE_DEFAULT,
    destino: Path = DESTINO_REDE_DEFAULT,
    *,
    n_min_anti_reid: int = N_MINIMO_ANTI_REIDENTIFICACAO,
    escrever: bool = True,
) -> pd.DataFrame:
    """Ingere o xlsx → deriva hex + rede + drop-PII → agrega hex×rede → valida → grava.

    Formato LONGO (gate C). Parametrizável por ``fonte`` (testes usam fixture sintética).
    Retorna o DataFrame agregado. READ-ONLY sobre o M1.
    """
    df = _ler_e_derivar_hex_rede(Path(fonte), n_min_anti_reid=n_min_anti_reid)
    agg = _agregar_h3_rede(df)
    _assert_sem_pii_rede(agg, CONTRATO_COLUNAS_OFERTA_MENORES_REDE)
    _assert_res7(agg)
    if escrever:
        destino = Path(destino)
        destino.parent.mkdir(parents=True, exist_ok=True)
        agg.to_parquet(destino, index=False)
    return agg


def gerar_capacidade_media_por_rede(
    fonte: Path = FONTE_DEFAULT,
    destino: Path = DESTINO_CAP_DEFAULT,
    *,
    n_min_anti_reid: int = N_MINIMO_ANTI_REIDENTIFICACAO,
    escrever: bool = True,
) -> pd.DataFrame:
    """Ingere o xlsx → deriva rede + drop-PII → capacidade média/mediana por rede → grava.

    Valor recomendado ao consumo = MEDIANA (robusta a outliers); a média fica na tabela
    como referência (gate D). Parametrizável por ``fonte``. READ-ONLY sobre o M1.
    """
    df = _ler_e_derivar_hex_rede(Path(fonte), n_min_anti_reid=n_min_anti_reid)
    cap = capacidade_media_por_rede(df)
    _assert_sem_pii_rede(cap, CONTRATO_COLUNAS_CAP_REDE)
    if escrever:
        destino = Path(destino)
        destino.parent.mkdir(parents=True, exist_ok=True)
        cap.to_parquet(destino, index=False)
    return cap


def _ler_pares_concorrentes(concorrentes_path: Path) -> set[tuple[str, str]]:
    """Lê os pares `(hex_id_res7, rede)` únicos de `concorrentes_mapeados.parquet`."""
    if not Path(concorrentes_path).exists():
        return set()
    df = pd.read_parquet(concorrentes_path, columns=["hex_id_res7", "rede"])
    df = df.dropna(subset=["hex_id_res7", "rede"])
    return set(zip(df["hex_id_res7"].astype(str), df["rede"].astype(str), strict=False))


def _ler_hexes_concorrentes(concorrentes_path: Path) -> set[str]:
    """Lê os hexes res-7 únicos de `concorrentes_mapeados.parquet` (dedup grosseiro)."""
    if not Path(concorrentes_path).exists():
        return set()
    df = pd.read_parquet(concorrentes_path, columns=["hex_id_res7"])
    return set(df["hex_id_res7"].dropna().astype(str))


def gerar_relatorio_classificacao(
    df_fronteira: pd.DataFrame,
    df_oferta_rede: pd.DataFrame,
    df_cap: pd.DataFrame,
    concorrentes_path: Path = CONCORRENTES_DEFAULT,
    destino_md: Path = RELATORIO_REDE_DEFAULT,
    *,
    escrever: bool = True,
) -> str:
    """Gera o markdown de qualidade da classificação + dedup FINO (só agregados, ZERO PII).

    Compara o dedup FINO por `(hex_id, rede_menor)` (só conta duplicado quando a MESMA
    rede aparece no MESMO hex) contra o dedup GROSSEIRO por `hex_id` (overlap) do TP-08.
    Nunca lê/grava `Nome_Academia`.
    """
    n_total = len(df_fronteira)
    n_indep = int((df_fronteira["rede_menor"] == CATEGORIA_INDEPENDENTE).sum())
    n_conhecida = n_total - n_indep
    pct_indep = 100.0 * n_indep / n_total if n_total else 0.0
    pct_conhecida = 100.0 * n_conhecida / n_total if n_total else 0.0

    n_redes_conhecidas = int((df_cap["rede_menor"] != CATEGORIA_INDEPENDENTE).nunique()) if len(
        df_cap
    ) else 0
    n_redes_confiaveis = int(df_cap["flag_confiavel"].sum()) if len(df_cap) else 0

    # Tabela de N por rede (só conhecidas após colapso) + capacidade + flag.
    linhas_rede = "\n".join(
        f"| `{r.rede_menor}` | {int(r.n_filiais):,} | {r.media_alunos:.1f} | "
        f"{r.mediana_alunos:.1f} | {'sim' if r.flag_confiavel else 'não'} |"
        for r in df_cap.itertuples(index=False)
    )

    # --- Dedup FINO por (hex, rede) vs dedup GROSSEIRO por hex ---
    pares_conc = _ler_pares_concorrentes(concorrentes_path)
    hexes_conc = _ler_hexes_concorrentes(concorrentes_path)

    n_academias = int(df_oferta_rede["n_academias_menores"].sum())
    n_alunos = int(df_oferta_rede["alunos_academias_menores"].sum())

    # Dedup GROSSEIRO (TP-08): qualquer academia menor cujo hex tem ALGUM concorrente mapeado.
    if hexes_conc:
        mask_grosso = df_oferta_rede["hex_id"].astype(str).isin(hexes_conc)
        alunos_grosso = int(df_oferta_rede.loc[mask_grosso, "alunos_academias_menores"].sum())
        pct_grosso = 100.0 * alunos_grosso / n_alunos if n_alunos else 0.0
    else:
        alunos_grosso = 0
        pct_grosso = 0.0

    # Dedup FINO (este FU): só quando a MESMA rede aparece no MESMO hex.
    if pares_conc:
        chaves = list(
            zip(
                df_oferta_rede["hex_id"].astype(str),
                df_oferta_rede["rede_menor"].astype(str),
                strict=False,
            )
        )
        mask_fino = pd.Series([k in pares_conc for k in chaves], index=df_oferta_rede.index)
        # `independente` nunca casa uma rede específica → nunca é dedupada no fino.
        mask_fino &= df_oferta_rede["rede_menor"].astype(str) != CATEGORIA_INDEPENDENTE
        alunos_fino = int(df_oferta_rede.loc[mask_fino, "alunos_academias_menores"].sum())
        pares_fino = int(mask_fino.sum())
        pct_fino = 100.0 * alunos_fino / n_alunos if n_alunos else 0.0
    else:
        alunos_fino = pares_fino = 0
        pct_fino = 0.0

    md = f"""# Classificação de rede das academias menores — qualidade & dedup FINO

> Camada PARALELA (BLK-TP-08-FU / DEC-012 / DEC-013 parte 3). Contratos
> `{VERSAO_CONTRATO_OFERTA_MENORES_REDE}` e `{VERSAO_CONTRATO_CAP_REDE}`. Artefatos:
> `data/staging/oferta_academias_menores_rede_h3.parquet` e
> `data/staging/capacidade_media_por_rede.parquet` (gitignored, NÃO oficiais do M1).
> **READ-ONLY sobre o M1** — não recompõe `score_oportunidade_residual`. **ZERO PII**
> (só agregados; `rede_menor` é CATEGORIA, nunca o nome). Gate humano APROVADO por
> Felipe Silva em 2026-07-02 (A token word-boundary + lista curada; B N<3→independente;
> C formato longo; D capacidade=mediana, flag_confiavel N≥10).

## Cobertura da classificação
- Academias classificadas: **{n_total:,}**.
- Rede **conhecida**: **{n_conhecida:,}** (**{pct_conhecida:.1f}%**).
- **`independente`** (não-classificável + redes colapsadas por N<{N_MINIMO_ANTI_REIDENTIFICACAO}):
  **{n_indep:,}** (**{pct_indep:.1f}%**).
- Redes conhecidas após colapso (gate B): **{n_redes_conhecidas}**.
- Redes com capacidade **confiável** (N≥{N_MINIMO_CONFIABILIDADE}): **{n_redes_confiaveis}**.

## Capacidade média/mediana por rede (gate D — valor recomendado = MEDIANA)
| rede_menor | n_filiais | média alunos | mediana alunos | confiável (N≥{N_MINIMO_CONFIABILIDADE}) |
| --- | ---: | ---: | ---: | :---: |
{linhas_rede}

> `independente` está EXCLUÍDA desta tabela (média de rede heterogênea não é capacidade
> de rede). `Total_Alunos_Cluster` NUNCA somado.

## Dedup FINO por `(hex_id, rede_menor)` vs dedup GROSSEIRO por `hex_id` (TP-08)
> O TP-08 media dedup por `hex_id` (overlap): conta como duplicado QUALQUER academia menor
> num hex que tenha ALGUM concorrente mapeado — super-dedução (uma Smart Fit e uma academia
> de bairro no mesmo hex viram "ambas duplicadas"). O dedup FINO só conta como duplicado
> quando a MESMA rede aparece no MESMO hex (`(hex, rede)` casando `concorrentes_mapeados`).
- Academias menores totais: **{n_academias:,}** | alunos: **{n_alunos:,}**.
- Pares `(hex, rede)` de concorrentes mapeados: **{len(pares_conc):,}**.
- **Dedup GROSSEIRO** (TP-08, por hex): alunos em hex com concorrente = **{alunos_grosso:,}**
  (**{pct_grosso:.1f}%**).
- **Dedup FINO** (este FU, por hex×rede): pares hex×rede duplicados = **{pares_fino:,}**;
  alunos realmente duplicados = **{alunos_fino:,}** (**{pct_fino:.1f}%**).
- **Correção do dedup fino:** o fino reduz a dedução de **{pct_grosso:.1f}% → {pct_fino:.1f}%**
  dos alunos — a maior parte da oferta menor num hex de concorrente é rede DISTINTA
  (adição legítima à saturação), não a mesma rede recontada.

## Caveats
- ~97% `independente` (esperado): academias de bairro/independentes dominam a agregação
  WellHub/TotalPass; a capacidade por rede só é útil para as ~{n_redes_confiaveis} redes N≥{N_MINIMO_CONFIABILIDADE}.
- Coords ~1 km (mesmo caveat do TP-08/TP-01): ruído no join res-7 — camada de refino, não
  verdade fina. NÃO substitui M1/censitário.
- Dedup fino ainda NÃO subtrai oferta (só QUANTIFICA); a subtração/integração ao residual é
  BLK-TP-06-FU1 / BLK-TP-09 sob gate próprio.
"""
    if escrever:
        destino_md = Path(destino_md)
        destino_md.parent.mkdir(parents=True, exist_ok=True)
        destino_md.write_text(md, encoding="utf-8")
    return md


__all__ = [
    "classificar_rede",
    "ingerir_oferta_menores_por_rede",
    "gerar_capacidade_media_por_rede",
    "capacidade_media_por_rede",
    "gerar_relatorio_classificacao",
    "CONTRATO_COLUNAS_OFERTA_MENORES_REDE",
    "CONTRATO_COLUNAS_CAP_REDE",
    "VERSAO_CONTRATO_OFERTA_MENORES_REDE",
    "VERSAO_CONTRATO_CAP_REDE",
    "VOCABULARIO_REDES",
    "CATEGORIA_INDEPENDENTE",
    "N_MINIMO_ANTI_REIDENTIFICACAO",
    "N_MINIMO_CONFIABILIDADE",
    "DESTINO_REDE_DEFAULT",
    "DESTINO_CAP_DEFAULT",
]
