"""Nucleo PURO da recomendacao unica: Top 10 = 5 Mata Virgem + 5 Premium, por hexagono H3 res-7.

Puro de proposito: sem I/O, sem env, sem relogio, sem aleatoriedade, sem perfil, e nunca muta a
entrada. Tudo o que depende de ambiente (a regua vigente, o k da malha, a renda do card) entra
por argumento -- quem le e `montar.py`. Assim a mesma tabela + a mesma regua + a mesma
procedencia de renda dao SEMPRE o mesmo Top 10, em qualquer ordem de linhas, na web, na API, no
bot e no PDF (Fase 4).

A regra (fechada pelo usuario nos GATES 1 e 2; DEC-077) -- numeros na regua, nunca aqui:

    Mata Virgem: renda domiciliar >= R  E  residual >= S  E  residual MEDIDO
                 ordem: residual desc, populacao desc, hex_id asc
    Premium:     NAO e Mata Virgem (PROVADAMENTE)  E  score censitario >= P  E  populacao >= Pm
                 ordem: populacao desc, score desc, hex_id asc

- Limites inclusivos no valor CHEIO (float64 exato; Float32 de origem e convertido sem
  arredondar). Empate e resolvido pela chave seguinte -- "vence o maior numero absoluto" -- e o
  `hex_id` fecha a ordem total. Nunca `nlargest` (que nao garante a ordem dos empatados).
- Segmentos exclusivos, e um NUNCA completa o outro: faltando candidato, a vaga sai VAZIA com
  motivo. Vizinhos do mesmo bairro podem ocupar varias vagas (sem dedup geografico).
- Fora da conta, de proposito: concorrencia, viabilidade, aluguel, score_priorizacao (M1),
  Ultra e distancia. NAO existe regra de proximidade/1 km aqui.
- "Nao vamos mostrar estimado": residual cuja populacao veio da media da cidade
  (`fonte_pop_hex_base` fora de `FONTES_MEDIDAS`) nunca e Mata Virgem (com a regua BR v1) e o
  NUMERO estimado nunca sai: `residual=None`, `residual_medido=False`.

Logica de tres valores (nada e imputado). "Nao e Mata Virgem" precisa de PROVA: um hexagono sem
renda e com residual alto pode ser Mata Virgem -- nao se sabe --, e por isso NUNCA vira Premium
(senao uma falha de dado empurraria para o Premium justamente o hexagono que talvez seja o
melhor Mata Virgem do recorte).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
import pandas as pd

from motor_expansao.recomendacao.carregador import Regra

# --------------------------------------------------------------------------------
# Contrato de colunas (particao enriquecida `hexagonos_dashboard_enriquecido/uf=XX`)
# --------------------------------------------------------------------------------

COL_HEX = "hex_id"
#: Residual fitness em ALUNOS (Float32 no artefato -> float64 exato aqui).
COL_RESIDUAL = "oferta_efetiva_disponivel"
#: Score censitario absoluto 0-100 (DEC-040). NAO e o `score_priorizacao` do M1.
COL_SCORE = "score_setor_2022_calibrado"
#: Populacao do Censo 2022 no hexagono. NUNCA `populacao_corte_hex` (repete o total da cidade).
COL_POPULACAO = "pop_total_setor_2022"
#: De onde saiu a populacao-base do residual: so `FONTES_MEDIDAS` contam como medido.
COL_FONTE_POP = "fonte_pop_hex_base"
FONTE_MEDIDA = "censo_2022_setor"
#: Populacao do Censo pela MALHA (fracao de area dos setores): o hexagono de orla e de beira
#: de rio, onde nenhum centroide de setor cai dentro (emenda da DEC-077).
FONTE_MEDIDA_MALHA = "censo_2022_malha"
FONTES_MEDIDAS: tuple[str, ...] = (FONTE_MEDIDA, FONTE_MEDIDA_MALHA)
#: Renda domiciliar do card (R$/mes), calculada por `montar.py` com o k da malha. NAO vem do
#: artefato: o nucleo nao faz conta de renda (ponto unico da renda, DEC-072).
COL_RENDA = "renda_domiciliar"
#: Origem de cada renda (`serie_renda`): nome da coluna de leitura. Opcional.
COL_RENDA_ORIGEM = "renda_origem"
#: Origem que marca renda MUNICIPAL (SIDRA, o mesmo numero na cidade inteira).
ORIGEM_MUNICIPAL = "renda_per_capita"

COLUNAS_OBRIGATORIAS: tuple[str, ...] = (
    COL_HEX,
    COL_RESIDUAL,
    COL_SCORE,
    COL_POPULACAO,
    COL_FONTE_POP,
)
#: So repassadas ao item quando vierem no frame.
COLUNAS_REPASSADAS: tuple[str, ...] = ("uf", "cod_municipio", "nome_municipio", "lat", "lng")

# --------------------------------------------------------------------------------
# Identificadores (sem acento) e a camada de ROTULO de exibicao (com acento)
# --------------------------------------------------------------------------------

Segmento = Literal["mata_virgem", "premium"]
SEGMENTOS: tuple[Segmento, Segmento] = ("mata_virgem", "premium")

STATUS_COMPLETO = "completo"
STATUS_INCOMPLETO = "incompleto"
STATUS_INDISPONIVEL = "indisponivel"

MOTIVO_RENDA_INDISPONIVEL = "renda_indisponivel"
MOTIVO_CANDIDATOS_INSUFICIENTES = "candidatos_insuficientes"

#: Contadores "ficou de fora por falta de dado" de cada segmento -- chaves FIXAS, sempre todas
#: presentes (zero explicito). Definicao exata em `_contadores`.
CHAVES_SEM_DADO: dict[str, tuple[str, ...]] = {
    "mata_virgem": (
        "abaixo_da_populacao_minima",
        "residual_estimado",
        "sem_populacao",
        "sem_renda",
        "sem_residual",
    ),
    "premium": (
        "abaixo_da_populacao_minima",
        "indeterminado_mv",
        "residual_estimado",
        "sem_populacao",
        "sem_score",
    ),
}

ROTULO_SEGMENTO: dict[str, str] = {"mata_virgem": "Mata Virgem", "premium": "Premium"}
ROTULO_STATUS: dict[str, str] = {
    STATUS_COMPLETO: "Completo",
    STATUS_INCOMPLETO: "Incompleto",
    STATUS_INDISPONIVEL: "Indisponível",
}
ROTULO_MOTIVO: dict[str, str] = {
    MOTIVO_RENDA_INDISPONIVEL: "Renda indisponível: recomendação suspensa até a base ser corrigida",
    MOTIVO_CANDIDATOS_INSUFICIENTES: "Não há outra região que atenda à régua neste recorte",
}
ROTULO_SEM_DADO: dict[str, str] = {
    "sem_renda": "Sem renda domiciliar",
    "sem_residual": "Sem residual",
    "residual_estimado": "Residual estimado (não medido)",
    "sem_populacao": "Sem população do Censo",
    "sem_score": "Sem score censitário",
    "abaixo_da_populacao_minima": "Abaixo da população mínima",
    "indeterminado_mv": "Sem dado para descartar Mata Virgem",
}

VERSAO_PAYLOAD = 1

_NIVEIS_RECORTE = ("brasil", "uf", "municipio")


# --------------------------------------------------------------------------------
# Tipos
# --------------------------------------------------------------------------------


@dataclass(frozen=True)
class Recorte:
    """O recorte ja selecionado na tela. So CARIMBA o resultado -- quem recorta e o chamador."""

    nivel: str
    uf: str | None = None
    cod_municipio: str | None = None
    nome: str | None = None

    def __post_init__(self) -> None:
        if self.nivel not in _NIVEIS_RECORTE:
            raise ValueError(f"nivel de recorte invalido: {self.nivel!r} (um de {_NIVEIS_RECORTE})")


@dataclass(frozen=True)
class ProcedenciaRenda:
    """De onde saiu a renda que decidiu a lista: k da malha, carimbo, versao dos fatores, pais."""

    k: float
    carimbo: str
    fatores_versao: str
    pais: str


@dataclass(frozen=True)
class ItemRecomendado:
    """Uma vaga preenchida. `residual` e None quando estimado (o numero estimado nunca sai)."""

    segmento: str
    posicao: int
    hex_id: str
    renda_domiciliar: float | None
    renda_municipal: bool
    populacao: float
    residual: float | None
    residual_medido: bool
    score_censitario: float | None
    uf: str | None = None
    cod_municipio: str | None = None
    nome_municipio: str | None = None
    lat: float | None = None
    lng: float | None = None


@dataclass(frozen=True)
class VagaVazia:
    """Uma vaga sem regiao, com o motivo (identificador; o rotulo esta em `ROTULO_MOTIVO`)."""

    segmento: str
    posicao: int
    motivo: str


Vaga = ItemRecomendado | VagaVazia


@dataclass(frozen=True)
class ResultadoSegmento:
    """Resultado de um segmento: `vagas` tem SEMPRE `vagas_por_segmento` posicoes."""

    segmento: str
    status: str
    vagas: tuple[Vaga, ...]
    n_elegiveis: int
    sem_dado: tuple[tuple[str, int], ...] = field(default=())


@dataclass(frozen=True)
class Recomendacao:
    """O Top 10 de um recorte, com a regua e a procedencia da renda que o decidiram."""

    regra: Regra
    recorte: Recorte
    n_hexes_recorte: int
    renda: ProcedenciaRenda | None
    mata_virgem: ResultadoSegmento
    premium: ResultadoSegmento

    @property
    def top10(self) -> tuple[Vaga, ...]:
        """As vagas na ordem de exibicao: Mata Virgem 1..N, depois Premium 1..N (vazias inclusas)."""
        return self.mata_virgem.vagas + self.premium.vagas

    @property
    def hex_ids(self) -> tuple[str, ...]:
        """Os hexagonos recomendados, na ordem de `top10` (sem as vagas vazias)."""
        return tuple(v.hex_id for v in self.top10 if isinstance(v, ItemRecomendado))

    def segmento_do_hex(self, hex_id: object) -> str | None:
        """Segmento em que `hex_id` foi recomendado, ou None se ele nao esta no Top 10."""
        alvo = str(hex_id)
        for v in self.top10:
            if isinstance(v, ItemRecomendado) and v.hex_id == alvo:
                return v.segmento
        return None

    def para_payload(self, *, nomes: dict[str, str] | None = None) -> dict[str, Any]:
        """Dicionario JSON-safe, chaves e ordem fixas, floats CRUS (sem arredondar), NaN -> None.

        `nomes` (opcional) = `hex_id -> rotulo da regiao` (`nomes.rotulos_das_regioes`); vira o
        campo `nome_regiao` de cada vaga (None quando ausente: o chamador mostra o municipio).
        """
        nomes = nomes or {}
        return {
            "versao_payload": VERSAO_PAYLOAD,
            "regra": _regra_payload(self.regra),
            "recorte": {
                "nivel": self.recorte.nivel,
                "uf": self.recorte.uf,
                "cod_municipio": self.recorte.cod_municipio,
                "nome": self.recorte.nome,
            },
            "n_hexes_recorte": int(self.n_hexes_recorte),
            "renda": _renda_payload(self.renda),
            "mata_virgem": _segmento_payload(self.mata_virgem, nomes),
            "premium": _segmento_payload(self.premium, nomes),
            "rotulos": {
                "segmento": dict(ROTULO_SEGMENTO),
                "status": dict(ROTULO_STATUS),
                "motivo": dict(ROTULO_MOTIVO),
                "sem_dado": dict(ROTULO_SEM_DADO),
            },
        }


# --------------------------------------------------------------------------------
# Normalizacao da entrada (sem imputar nada)
# --------------------------------------------------------------------------------


def _float64(s: pd.Series) -> pd.Series:
    """Numero em float64 EXATO (Float32 -> float64 nao arredonda), NaN onde nao ha valor.

    Categorico e nullable (`Float32` com `pd.NA`) passam por object/`Float64` antes: comparar
    um `pd.NA` levantaria, e um categorico numerico nao aceita `>=` contra escalar.
    +-inf vira AUSENTE: passaria em `notna` e em `>=` (um residual infinito seria o Mata Virgem
    no 1 com `residual=None` na tela), enquanto a exibicao (`_float_ou_none`) ja o trata como
    sem numero -- classificacao e exibicao tem de concordar sobre o que e "valor conhecido".
    """
    if isinstance(s.dtype, pd.CategoricalDtype):
        s = s.astype(object)
    num = pd.to_numeric(s, errors="coerce")
    valores = num.astype("Float64").to_numpy(dtype="float64", na_value=np.nan)
    valores = np.where(np.isfinite(valores), valores, np.nan)
    return pd.Series(valores, index=s.index, dtype="float64")


#: Nulos que chegam ESCRITOS como texto (`astype(str)` de uma coluna com nulos).
_NULOS_TEXTO = frozenset({"nan", "none", "<na>", "nat", "null"})


def _texto(v: object) -> str | None:
    """Texto de uma celula: None/NaN (inclusive `np.float32`)/vazio/nulo escrito -> None."""
    if v is None or v is pd.NA or v is pd.NaT:
        return None
    if isinstance(v, (float, np.floating)) and math.isnan(v):
        return None
    s = str(v).strip()
    if not s or s.casefold() in _NULOS_TEXTO:
        return None
    return s


def _cod_municipio(v: object) -> str | None:
    """Codigo IBGE como texto, mesmo vindo float/categorico (`3550308.0`); nulo -> None."""
    if isinstance(v, (float, np.floating)) and not math.isnan(v) and float(v).is_integer():
        return str(int(v))
    s = _texto(v)
    return None if s is None else s.removesuffix(".0")


def _serie_texto(s: pd.Series) -> pd.Series:
    return pd.Series([_texto(v) for v in s.astype(object)], index=s.index, dtype="object")


@dataclass(frozen=True)
class _Entrada:
    hex_id: pd.Series
    renda: pd.Series
    origem: pd.Series
    residual: pd.Series
    score: pd.Series
    populacao: pd.Series
    medido: pd.Series


def validar_colunas(hexes: pd.DataFrame, *, renda_disponivel: bool) -> None:
    """Fail-closed: coluna obrigatoria ausente -> `ValueError` nomeando TODAS as que faltam."""
    if not isinstance(hexes, pd.DataFrame):
        raise TypeError(f"esperado pandas.DataFrame, veio {type(hexes).__name__}")
    exigidas = COLUNAS_OBRIGATORIAS + ((COL_RENDA,) if renda_disponivel else ())
    faltando = [c for c in exigidas if c not in hexes.columns]
    if faltando:
        raise ValueError(
            f"recomendacao: coluna(s) obrigatoria(s) ausente(s): {', '.join(faltando)}"
        )


def _entrada(hexes: pd.DataFrame, *, renda_disponivel: bool) -> _Entrada:
    validar_colunas(hexes, renda_disponivel=renda_disponivel)
    idx = hexes.index
    if renda_disponivel:
        renda = _float64(hexes[COL_RENDA])
    else:
        renda = pd.Series(np.nan, index=idx, dtype="float64")
    if COL_RENDA_ORIGEM in hexes.columns:
        origem = _serie_texto(hexes[COL_RENDA_ORIGEM])
    else:
        origem = pd.Series([None] * len(hexes), index=idx, dtype="object")
    fonte = _serie_texto(hexes[COL_FONTE_POP])
    return _Entrada(
        hex_id=_serie_texto(hexes[COL_HEX]),
        renda=renda,
        origem=origem,
        residual=_float64(hexes[COL_RESIDUAL]),
        score=_float64(hexes[COL_SCORE]),
        populacao=_float64(hexes[COL_POPULACAO]),
        medido=fonte.isin(FONTES_MEDIDAS).astype(bool),
    )


# --------------------------------------------------------------------------------
# Classificacao (tres valores)
# --------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Mascaras:
    renda_ok: pd.Series
    res_ok: pd.Series
    pop_ok: pd.Series
    score_ok: pd.Series
    mv_elegivel: pd.Series
    prova_nao_mv: pd.Series
    mv_indeterminado: pd.Series
    premium_elegivel: pd.Series
    mv_recomendavel: pd.Series
    premium_recomendavel: pd.Series
    falha_valor_mv: pd.Series
    pop_mv_falha: pd.Series
    premium_candidato_por_valor: pd.Series


def _mascaras(e: _Entrada, regra: Regra, *, renda_disponivel: bool) -> _Mascaras:
    mv, pr = regra.mata_virgem, regra.premium
    r_min, s_min, p_min = mv.renda_domiciliar_min, mv.residual_min, pr.score_min
    falso = pd.Series(False, index=e.renda.index, dtype=bool)

    renda_ok = e.renda.notna() if renda_disponivel else falso
    res_ok = e.residual.notna()
    pop_ok = e.populacao.notna()
    score_ok = e.score.notna()
    # `NaN >= x` e False no numpy: as comparacoes abaixo ja tratam o ausente como "nao passou",
    # e o `_ok` explicito so documenta (e protege de um dtype nullable que propagasse NA).
    renda_alta = renda_ok & (e.renda >= r_min)
    res_alto = res_ok & (e.residual >= s_min)
    estimado_barrado_mv = ~e.medido if mv.exige_residual_medido else falso
    if mv.populacao_min is None:
        pop_mv_passa = pd.Series(True, index=e.renda.index, dtype=bool)
        pop_mv_falha = falso
    else:
        pop_mv_passa = pop_ok & (e.populacao >= mv.populacao_min)
        pop_mv_falha = pop_ok & (e.populacao < mv.populacao_min)

    mv_elegivel = renda_alta & res_alto & ~estimado_barrado_mv & pop_mv_passa
    # Prova de "nao e Mata Virgem" EXATAMENTE como no pseudo-codigo aprovado (spec da Fase 2,
    # "nao reinterpretar"): renda < R, residual < S, ou residual estimado com a regua exigindo
    # medido. O piso de populacao do MV (`mata_virgem.populacao_min`, null na BR v1) barra o MV
    # mas NAO e prova: um hexagono de renda e residual altos abaixo desse piso fica
    # INDETERMINADO e nunca vira Premium. Ler o piso como prova (o hexagono iria para o Premium)
    # seria outra regra -- so com decisao do usuario e emenda da DEC-077.
    falha_valor_mv = (renda_ok & (e.renda < r_min)) | (res_ok & (e.residual < s_min))
    prova_nao_mv = falha_valor_mv | estimado_barrado_mv
    mv_indeterminado = ~mv_elegivel & ~prova_nao_mv

    if pr.populacao_min is None:
        pop_pr_passa = pop_ok
    else:
        pop_pr_passa = pop_ok & (e.populacao >= pr.populacao_min)
    estimado_barrado_pr = ~e.medido if pr.exige_residual_medido else falso
    # Passaria no Premium pelos proprios numeros (sem olhar a exclusividade com o Mata Virgem).
    premium_candidato_por_valor = (
        score_ok & (e.score >= p_min) & pop_pr_passa & ~estimado_barrado_pr
    )
    premium_elegivel = prova_nao_mv & premium_candidato_por_valor

    return _Mascaras(
        renda_ok=renda_ok,
        res_ok=res_ok,
        pop_ok=pop_ok,
        score_ok=score_ok,
        mv_elegivel=mv_elegivel,
        prova_nao_mv=prova_nao_mv,
        mv_indeterminado=mv_indeterminado,
        premium_elegivel=premium_elegivel,
        mv_recomendavel=mv_elegivel & pop_ok,
        premium_recomendavel=premium_elegivel,
        falha_valor_mv=falha_valor_mv,
        pop_mv_falha=pop_mv_falha,
        premium_candidato_por_valor=premium_candidato_por_valor,
    )


def classificar(hexes: pd.DataFrame, regra: Regra, *, renda_disponivel: bool) -> pd.DataFrame:
    """COPIA de `hexes` com as colunas booleanas da classificacao (a entrada nao e tocada).

    `mv_elegivel`, `mv_indeterminado`, `premium_elegivel`, `mv_recomendavel`,
    `premium_recomendavel` e `residual_medido`. Com `renda_disponivel=False` nenhum hexagono
    e Mata Virgem elegivel (sem renda nao ha prova de renda alta); a recomendacao, nesse caso,
    nem chega a usar a classificacao -- o Top 10 inteiro fica indisponivel.
    """
    e = _entrada(hexes, renda_disponivel=renda_disponivel)
    m = _mascaras(e, regra, renda_disponivel=renda_disponivel)
    out = hexes.copy()
    out["mv_elegivel"] = m.mv_elegivel.to_numpy(dtype=bool)
    out["mv_indeterminado"] = m.mv_indeterminado.to_numpy(dtype=bool)
    out["premium_elegivel"] = m.premium_elegivel.to_numpy(dtype=bool)
    out["mv_recomendavel"] = m.mv_recomendavel.to_numpy(dtype=bool)
    out["premium_recomendavel"] = m.premium_recomendavel.to_numpy(dtype=bool)
    out["residual_medido"] = e.medido.to_numpy(dtype=bool)
    return out


def linhas_que_precisam_de_renda(hexes: pd.DataFrame, regra: Regra) -> pd.Series:
    """Mascara das linhas em que a renda pode DECIDIR alguma coisa (o resto nao precisa dela).

    Residual nulo ou >= S (pode ser Mata Virgem, ou so a renda prova que nao e), ou score >= P
    com populacao >= minimo do Premium. No Brasil inteiro sao ~3,5 mil linhas (snapshot de
    outubro/2026): a renda do card e uma conta por linha, e calcula-la para 1,5 milhao de
    hexagonos seria trabalho jogado fora.
    """
    validar_colunas(hexes, renda_disponivel=False)
    residual = _float64(hexes[COL_RESIDUAL])
    score = _float64(hexes[COL_SCORE])
    populacao = _float64(hexes[COL_POPULACAO])
    pr = regra.premium
    pop_pr = populacao.notna()
    if pr.populacao_min is not None:
        pop_pr = pop_pr & (populacao >= pr.populacao_min)
    mv_possivel = residual.isna() | (residual >= regra.mata_virgem.residual_min)
    premium_possivel = score.notna() & (score >= pr.score_min) & pop_pr
    return (mv_possivel | premium_possivel).astype(bool)


def _contadores(e: _Entrada, m: _Mascaras, regra: Regra) -> dict[str, dict[str, int]]:
    """Quantos ficaram de fora de cada segmento POR FALTA DE DADO, e por que (disjuntos).

    Quem nao passa por VALOR conhecido (renda, residual ou score abaixo do corte) nao entra em
    contador nenhum: "nao se qualifica" nao e "faltou dado". A excecao declarada e
    `abaixo_da_populacao_minima`, que o usuario le ao lado dos outros. Cada hexagono cai em no
    maximo um contador por segmento.

    Mata Virgem (entre os que nao falham por valor):
      - `residual_estimado`: renda >= R e residual >= S, mas o residual e ESTIMADO (regua exige
        medido). Renda ausente com residual estimado NAO conta aqui nem em `sem_renda`: o
        hexagono ja esta fora pela estimativa, qualquer que fosse a renda;
      - `sem_renda`: sem renda, e nada mais o descarta;
      - `sem_residual`: com renda, sem residual, e nada mais o descarta;
      - `sem_populacao`: renda >= R e residual >= S (medido quando exigido), mas sem
        `pop_total_setor_2022` (dado minimo);
      - `abaixo_da_populacao_minima`: so quando a regua declara piso para o segmento (BR v1 nao).
        Esse hexagono NAO e provadamente nao-MV (ver `_mascaras`): fica indeterminado.
    Premium (entre os que passariam pelos proprios numeros, salvo o contador):
      - `indeterminado_mv`: passaria no Premium, mas falta dado para provar que nao e Mata Virgem;
      - `sem_score`: provadamente nao-Mata-Virgem, com populacao no piso do Premium, sem score.
        Quem nao tem score NEM populacao (fora da malha censitaria: ~234 mil hexagonos no
        Brasil, todos sem `pop_total_setor_2022`) nao conta -- seria terra vazia exibida como
        "faltou o score";
      - `sem_populacao` / `abaixo_da_populacao_minima`: provadamente nao-MV, score >= P, sem
        populacao / abaixo do piso;
      - `residual_estimado`: provadamente nao-MV, score e populacao ok, residual estimado e a
        regua do Premium exige medido (BR v1 exige).
    """
    mv, pr = regra.mata_virgem, regra.premium
    falso = pd.Series(False, index=e.renda.index, dtype=bool)
    estimado = ~e.medido
    livre = ~m.falha_valor_mv
    estimado_barrado_mv = estimado if mv.exige_residual_medido else falso
    renda_alta = m.renda_ok & (e.renda >= mv.renda_domiciliar_min)
    res_alto = m.res_ok & (e.residual >= mv.residual_min)

    mv_res_estimado = renda_alta & res_alto & estimado_barrado_mv & livre
    mv_sem_renda = livre & ~m.renda_ok & ~estimado_barrado_mv
    mv_sem_residual = livre & m.renda_ok & ~m.res_ok & ~estimado_barrado_mv
    # Nao derivado de `mv_elegivel`: com piso de populacao declarado, `mv_elegivel` ja exige a
    # populacao, e o hexagono sem ela sumiria de todos os contadores.
    mv_sem_pop = renda_alta & res_alto & ~estimado_barrado_mv & ~m.pop_ok
    mv_abaixo = renda_alta & res_alto & ~estimado_barrado_mv & m.pop_mv_falha

    score_alto = m.score_ok & (e.score >= pr.score_min)
    estimado_barrado_pr = estimado if pr.exige_residual_medido else falso
    if pr.populacao_min is None:
        pop_pr_passa = m.pop_ok
        pop_pr_falha = falso
    else:
        pop_pr_passa = m.pop_ok & (e.populacao >= pr.populacao_min)
        pop_pr_falha = m.pop_ok & (e.populacao < pr.populacao_min)
    prova = m.prova_nao_mv

    contagem = {
        "mata_virgem": {
            "abaixo_da_populacao_minima": mv_abaixo,
            "residual_estimado": mv_res_estimado,
            "sem_populacao": mv_sem_pop,
            "sem_renda": mv_sem_renda,
            "sem_residual": mv_sem_residual,
        },
        "premium": {
            "abaixo_da_populacao_minima": prova & score_alto & pop_pr_falha,
            "indeterminado_mv": m.mv_indeterminado & m.premium_candidato_por_valor,
            "residual_estimado": prova & score_alto & pop_pr_passa & estimado_barrado_pr,
            "sem_populacao": prova & score_alto & ~m.pop_ok,
            "sem_score": prova & ~m.score_ok & pop_pr_passa,
        },
    }
    return {
        seg: {chave: int(mascara.sum()) for chave, mascara in por_chave.items()}
        for seg, por_chave in contagem.items()
    }


# --------------------------------------------------------------------------------
# Ordenacao e montagem das vagas
# --------------------------------------------------------------------------------


def _ordem(e: _Entrada, mascara: pd.Series, segmento: str) -> list[int]:
    """Posicoes (iloc) dos candidatos de `segmento`, na ordem total da regra.

    Ordenacao estavel (`mergesort`) pelas 3 chaves no valor cheio; o `hex_id` (unico entre os
    candidatos -- conferido antes) fecha a ordem, entao a permutacao das linhas nao muda nada.
    """
    sel = np.flatnonzero(mascara.to_numpy(dtype=bool))
    quadro = pd.DataFrame(
        {
            "_pos": sel,
            "hex_id": e.hex_id.to_numpy(dtype=object)[sel],
            "residual": e.residual.to_numpy(dtype="float64")[sel],
            "populacao": e.populacao.to_numpy(dtype="float64")[sel],
            "score": e.score.to_numpy(dtype="float64")[sel],
        }
    )
    if segmento == "mata_virgem":
        chaves = ["residual", "populacao", "hex_id"]
    else:
        chaves = ["populacao", "score", "hex_id"]
    quadro = quadro.sort_values(chaves, ascending=[False, False, True], kind="mergesort")
    return [int(p) for p in quadro["_pos"]]


def _float_ou_none(v: object) -> float | None:
    if v is None or v is pd.NA:
        return None
    try:
        f = float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _item(
    hexes: pd.DataFrame, e: _Entrada, pos: int, segmento: str, posicao: int
) -> ItemRecomendado:
    medido = bool(e.medido.iat[pos])
    renda = _float_ou_none(e.renda.iat[pos])
    origem = e.origem.iat[pos]
    populacao = _float_ou_none(e.populacao.iat[pos])
    if populacao is None:  # inalcancavel: candidato sempre tem populacao (dado minimo)
        raise ValueError(f"recomendacao: candidato {e.hex_id.iat[pos]!r} sem {COL_POPULACAO}")

    def repassada(coluna: str) -> object:
        return hexes[coluna].iat[pos] if coluna in hexes.columns else None

    return ItemRecomendado(
        segmento=segmento,
        posicao=posicao,
        hex_id=str(e.hex_id.iat[pos]),
        renda_domiciliar=renda,
        renda_municipal=bool(renda is not None and origem == ORIGEM_MUNICIPAL),
        populacao=populacao,
        # "Nao vamos mostrar estimado": o numero so sai quando medido.
        residual=_float_ou_none(e.residual.iat[pos]) if medido else None,
        residual_medido=medido,
        score_censitario=_float_ou_none(e.score.iat[pos]),
        uf=_texto(repassada("uf")),
        cod_municipio=_cod_municipio(repassada("cod_municipio")),
        nome_municipio=_texto(repassada("nome_municipio")),
        lat=_float_ou_none(repassada("lat")),
        lng=_float_ou_none(repassada("lng")),
    )


def _resultado(
    hexes: pd.DataFrame,
    e: _Entrada,
    mascara: pd.Series,
    segmento: str,
    vagas: int,
    sem_dado: dict[str, int],
) -> ResultadoSegmento:
    ordem = _ordem(e, mascara, segmento)
    preenchidas: list[Vaga] = [
        _item(hexes, e, pos, segmento, i + 1) for i, pos in enumerate(ordem[:vagas])
    ]
    vazias: list[Vaga] = [
        VagaVazia(segmento=segmento, posicao=i + 1, motivo=MOTIVO_CANDIDATOS_INSUFICIENTES)
        for i in range(len(preenchidas), vagas)
    ]
    return ResultadoSegmento(
        segmento=segmento,
        status=STATUS_COMPLETO if len(ordem) >= vagas else STATUS_INCOMPLETO,
        vagas=tuple(preenchidas + vazias),
        n_elegiveis=len(ordem),
        sem_dado=tuple(sorted(sem_dado.items())),
    )


def _indisponivel(segmento: str, vagas: int) -> ResultadoSegmento:
    """Segmento sem renda confiavel: todas as vagas vazias, contadores zerados (nada foi medido)."""
    return ResultadoSegmento(
        segmento=segmento,
        status=STATUS_INDISPONIVEL,
        vagas=tuple(
            VagaVazia(segmento=segmento, posicao=i + 1, motivo=MOTIVO_RENDA_INDISPONIVEL)
            for i in range(vagas)
        ),
        n_elegiveis=0,
        sem_dado=tuple((chave, 0) for chave in sorted(CHAVES_SEM_DADO[segmento])),
    )


def _conferir_hex_ids(e: _Entrada, candidatos: pd.Series) -> None:
    ids = e.hex_id[candidatos.to_numpy(dtype=bool)]
    if ids.isna().any():
        raise ValueError(f"recomendacao: {int(ids.isna().sum())} candidato(s) sem hex_id")
    repetidos = sorted(set(ids[ids.duplicated()]))
    if repetidos:
        amostra = ", ".join(repetidos[:5])
        raise ValueError(
            f"recomendacao: hex_id repetido entre candidatos ({len(repetidos)}): {amostra}"
        )


def candidatos_ordenados(
    hexes: pd.DataFrame, regra: Regra, segmento: str, *, renda_disponivel: bool
) -> pd.DataFrame:
    """TODOS os candidatos recomendaveis de `segmento`, na ordem da regra (linhas de `hexes`).

    E a lista de onde o Top saem as `vagas_por_segmento` primeiras -- serve para conferir a
    invariancia de recorte (o Top do Brasil filtrado por UF = o Top da UF). As linhas sao as de
    `hexes`, com UMA protecao de "nao vamos mostrar estimado": `oferta_efetiva_disponivel` vira
    NaN onde o residual nao e medido, e a coluna `residual_medido` diz qual e qual. Ainda assim
    NAO e uma saida de exibicao (as demais colunas vao cruas): uma tela que listar mais que o Top
    deve montar os itens pelo mesmo caminho de `recomendar` (`ItemRecomendado`).
    """
    if segmento not in SEGMENTOS:
        raise ValueError(f"segmento invalido: {segmento!r} (um de {SEGMENTOS})")
    e = _entrada(hexes, renda_disponivel=renda_disponivel)
    m = _mascaras(e, regra, renda_disponivel=renda_disponivel)
    _conferir_hex_ids(e, m.mv_recomendavel | m.premium_recomendavel)
    mascara = m.mv_recomendavel if segmento == "mata_virgem" else m.premium_recomendavel
    ordem = _ordem(e, mascara, segmento)
    out = hexes.iloc[ordem].copy()
    medido = e.medido.to_numpy(dtype=bool)[ordem]
    residual = e.residual.to_numpy(dtype="float64")[ordem]
    out[COL_RESIDUAL] = np.where(medido, residual, np.nan)
    out["residual_medido"] = medido
    return out


def recomendar(
    hexes: pd.DataFrame,
    regra: Regra,
    *,
    renda: ProcedenciaRenda | None,
    recorte: Recorte,
) -> Recomendacao:
    """O Top 10 de `hexes` (o recorte JA selecionado) pela `regra`.

    `renda=None` = sem o carimbo k da malha: a renda nao e confiavel, e o Top 10 INTEIRO sai
    indisponivel (os dois segmentos, todas as vagas vazias com `renda_indisponivel`). Nunca sai
    lista com a renda calculada de outro jeito. Com `renda`, `hexes` tem de trazer a coluna
    `renda_domiciliar` (e, opcional, `renda_origem`), calculadas por `montar.py`.
    """
    if not isinstance(recorte, Recorte):
        raise TypeError(f"recorte deveria ser Recorte, veio {type(recorte).__name__}")
    renda_disponivel = renda is not None
    e = _entrada(hexes, renda_disponivel=renda_disponivel)
    vagas = regra.vagas_por_segmento
    if not renda_disponivel:
        mv = _indisponivel("mata_virgem", vagas)
        pr = _indisponivel("premium", vagas)
    else:
        m = _mascaras(e, regra, renda_disponivel=True)
        _conferir_hex_ids(e, m.mv_recomendavel | m.premium_recomendavel)
        contadores = _contadores(e, m, regra)
        mv = _resultado(
            hexes, e, m.mv_recomendavel, "mata_virgem", vagas, contadores["mata_virgem"]
        )
        pr = _resultado(hexes, e, m.premium_recomendavel, "premium", vagas, contadores["premium"])
    return Recomendacao(
        regra=regra,
        recorte=recorte,
        n_hexes_recorte=len(hexes),
        renda=renda,
        mata_virgem=mv,
        premium=pr,
    )


# --------------------------------------------------------------------------------
# Payload
# --------------------------------------------------------------------------------


def _json_float(v: float | None) -> float | None:
    return v if v is not None and math.isfinite(v) else None


def _regra_payload(regra: Regra) -> dict[str, Any]:
    mv, pr = regra.mata_virgem, regra.premium
    return {
        "versao": regra.versao,
        "pais": regra.pais,
        "dec": regra.dec,
        "aprovado_por": regra.aprovado_por,
        "fixada_por_env": bool(regra.fixada_por_env),
        "vagas_por_segmento": int(regra.vagas_por_segmento),
        "mata_virgem": {
            "renda_domiciliar_min": mv.renda_domiciliar_min,
            "residual_min": mv.residual_min,
            "populacao_min": mv.populacao_min,
            "exige_residual_medido": mv.exige_residual_medido,
        },
        "premium": {
            "score_min": pr.score_min,
            "populacao_min": pr.populacao_min,
            "exige_residual_medido": pr.exige_residual_medido,
        },
    }


def _renda_payload(renda: ProcedenciaRenda | None) -> dict[str, Any]:
    if renda is None:
        return {
            "disponivel": False,
            "k": None,
            "carimbo": None,
            "fatores_versao": None,
            "pais": None,
        }
    return {
        "disponivel": True,
        "k": _json_float(renda.k),
        "carimbo": renda.carimbo,
        "fatores_versao": renda.fatores_versao,
        "pais": renda.pais,
    }


def _vaga_payload(v: Vaga, nomes: dict[str, str]) -> dict[str, Any]:
    """Mesmo conjunto de chaves para vaga preenchida e vazia (o consumidor nao ramifica no schema)."""
    if isinstance(v, ItemRecomendado):
        return {
            "segmento": v.segmento,
            "posicao": v.posicao,
            "vazia": False,
            "motivo": None,
            "rotulo_motivo": None,
            "hex_id": v.hex_id,
            "nome_regiao": nomes.get(v.hex_id),
            "renda_domiciliar": _json_float(v.renda_domiciliar),
            "renda_municipal": v.renda_municipal,
            "populacao": _json_float(v.populacao),
            "residual": _json_float(v.residual),
            "residual_medido": v.residual_medido,
            "score_censitario": _json_float(v.score_censitario),
            "uf": v.uf,
            "cod_municipio": v.cod_municipio,
            "nome_municipio": v.nome_municipio,
            "lat": _json_float(v.lat),
            "lng": _json_float(v.lng),
        }
    return {
        "segmento": v.segmento,
        "posicao": v.posicao,
        "vazia": True,
        "motivo": v.motivo,
        "rotulo_motivo": ROTULO_MOTIVO.get(v.motivo, v.motivo),
        "hex_id": None,
        "nome_regiao": None,
        "renda_domiciliar": None,
        "renda_municipal": False,
        "populacao": None,
        "residual": None,
        "residual_medido": False,
        "score_censitario": None,
        "uf": None,
        "cod_municipio": None,
        "nome_municipio": None,
        "lat": None,
        "lng": None,
    }


def _segmento_payload(r: ResultadoSegmento, nomes: dict[str, str]) -> dict[str, Any]:
    sem_dado = dict(r.sem_dado)
    return {
        "segmento": r.segmento,
        "rotulo": ROTULO_SEGMENTO.get(r.segmento, r.segmento),
        "status": r.status,
        "rotulo_status": ROTULO_STATUS.get(r.status, r.status),
        "n_elegiveis": int(r.n_elegiveis),
        "sem_dado": {chave: int(sem_dado.get(chave, 0)) for chave in CHAVES_SEM_DADO[r.segmento]},
        "vagas": [_vaga_payload(v, nomes) for v in r.vagas],
    }
