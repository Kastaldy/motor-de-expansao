"""Renda por HEXAGONO: UMA redacao para o card do REP, o tooltip, a ficha e o Relatorio Municipal.

Movido de `dashboard/renda_hex.py` (E0; DEC-072). Ate 2026-10-16 o card e o PDF municipal
tinham formulas proprias sobre o mesmo Censo 2022 (Sao Roque/SP, 87a810361ffffff: R$ 13.261
no PDF contra R$ 4.924 no card). Esta e a formula do card, que vale para os dois:

    fator_hex(uf, cod, tipo) = (moradores_muni x uplift_muni) x F_tipo(uf)
    renda_domiciliar_hex     = base x fator_hex(..., "domiciliar")
    renda_per_capita_hex     = round(base x fator_hex(..., "per_capita")) / moradores_muni

onde a base desfaz a escala da coluna de origem (ver `base_renda_domiciliar`). Um hexagono
res-7 cobre varios setores, entao uplift e moradores sao MUNICIPAIS: um escalar por municipio.
"""

from __future__ import annotations

import logging
import math
import os
import re
from collections.abc import Callable, Sequence
from pathlib import Path

import pandas as pd

from motor_expansao.renda.formula import fator
from motor_expansao.renda.insumos import moradores_por_domicilio, staging_dir, uplift_municipio

_LOG_RENDA = logging.getLogger("piloto.renda")

#: Precedencia da renda do hexagono: setor (granular) primeiro, municipio (SIDRA, o MESMO
#: numero repetido em toda a cidade) como fallback.
COLS_RENDA_LEITURA: tuple[str, ...] = (
    "renda_per_capita_setor_2022_calibrada",
    "renda_per_capita",
)

# k do STAGING HEX (censo2022_setores_calibrado.parquet, safra 2026-05) -- NAO confundir com o
# k do artefato GEO setorial (1,2335 na safra 2026-08-12): sao calibracoes independentes.
K_CALIBRACAO_FALLBACK = 1.0239
CENSO_HEX_STAGING_PARQUET = "censo2022_setores_calibrado.parquet"
# Artefato da MALHA (agregado dos setores). Quando existe, e ELE quem carrega o k da
# coluna servida -- ver `k_calibracao_renda`.
CENSO_MALHA_PARQUET = "censo2022_hex_da_malha.parquet"
_RE_K_CARIMBO = re.compile(r"k=([0-9]+(?:\.[0-9]+)?)")
FAIXA_K = (0.5, 3.0)


class InsumoRendaInvalido(RuntimeError):
    """Insumo de staging da renda ausente ou ilegivel numa instancia de producao."""


def serie_renda(
    df: pd.DataFrame, precedencia: Sequence[str] = COLS_RENDA_LEITURA
) -> tuple[pd.Series, pd.Series]:
    """Renda de leitura POR LINHA, mais a origem de CADA valor.

    A escolha e por LINHA e nao por COLUNA. A redacao anterior parava na primeira coluna
    PRESENTE e usava so ela para o frame inteiro: `renda_origem` saia ESCALAR (o aviso
    `renda_municipal` nascia constante `False`) e 234.147 hexagonos (15,18%) com a coluna
    de setor PRESENTE e NULA nao exibiam renda nenhuma, tendo a municipal ao lado. Mesma
    familia da DEC-038: "a coluna existe" tratado como "o valor existe".

    Devolve `(valor, origem)`; `origem` e o NOME DA COLUNA de onde cada valor veio (`None`
    onde nenhuma tinha valor) -- identificador, nao rotulo: quem exibe traduz.
    """
    valor = pd.Series(float("nan"), index=df.index, dtype="float64")
    # `[None] * n` e nao o escalar `None`: com o escalar o pandas materializa NaN, e o
    # consumidor teria de distinguir "sem origem" de "origem NaN".
    origem = pd.Series([None] * len(df), index=df.index, dtype="object")
    for coluna in precedencia:
        if coluna not in df.columns:
            continue
        candidato = pd.to_numeric(df[coluna], errors="coerce")
        # So preenche o que ainda esta vazio: a precedencia se mantem, agora por linha.
        preencher = valor.isna() & candidato.notna()
        if not preencher.any():
            continue
        valor = valor.where(~preencher, candidato)
        origem = origem.where(~preencher, coluna)
    return valor, origem


def _k_obrigatorio() -> bool:
    """Instancia de producao (`MOTOR_DATA_DIR`) cuja versao de fatores exige o carimbo k."""
    if not os.environ.get("MOTOR_DATA_DIR"):
        return False
    from motor_expansao.renda.carregador import carregar_fatores

    return carregar_fatores().artefato_k_obrigatorio


def k_calibracao_renda(staging: Path | str | None = None) -> float:
    """O `k` com que a coluna calibrada DO HEX foi gerada, lido do carimbo no staging.

    Desde 2026-08-31 a coluna calibrada SERVIDA e agregada da MALHA setorial, com o k da
    malha -- a fonte do carimbo acompanha a fonte do valor (ler o carimbo antigo erraria a
    renda domiciliar em 20,47%). Ordem = precedencia: malha primeiro, staging hex depois.

    Carimbo ilegivel ou fora de [0,5; 3,0]:
      - em producao (`MOTOR_DATA_DIR` setado) com versao de fatores que exige o k ->
        `InsumoRendaInvalido`;
      - em dev/teste (ou pais sem k) -> fallback 1,0239 com WARNING, como antes. NUNCA 1,0
        em silencio: reintroduziria a dupla contagem sem pista.
    """
    base = Path(staging) if staging is not None else staging_dir()
    fontes = (
        (base / CENSO_MALHA_PARQUET, "metodo_calibracao_renda_malha"),
        (base / CENSO_HEX_STAGING_PARQUET, "metodo_calibracao_renda"),
    )
    nomes = [str(p) for p, _ in fontes]
    problema: str | None = None
    k = math.nan
    serie = None
    carimbo = ""
    try:
        disponiveis = [(caminho, coluna) for caminho, coluna in fontes if caminho.exists()]
        if not disponiveis:
            raise FileNotFoundError(f"nenhum de {nomes}")
        caminho, coluna = disponiveis[0]
        serie = pd.read_parquet(caminho, columns=[coluna])[coluna].dropna()
        carimbo = str(serie.mode().iloc[0])
        k = float(_RE_K_CARIMBO.search(carimbo).group(1))  # type: ignore[union-attr]
    except Exception as exc:  # noqa: BLE001 -- staging ausente/carimbo ilegivel
        problema = f"carimbo ilegivel em {nomes} ({exc})"
    else:
        lo, hi = FAIXA_K
        if not lo <= k <= hi:
            problema = f"k fora da faixa plausivel [{lo}, {hi}] ({k})"

    if problema is not None:
        if _k_obrigatorio():
            raise InsumoRendaInvalido(f"k de calibracao do hex: {problema}")
        _LOG_RENDA.warning(
            "k de calibracao do hex: %s; usando fallback %s", problema, K_CALIBRACAO_FALLBACK
        )
        return K_CALIBRACAO_FALLBACK
    assert serie is not None
    if serie.nunique() > 1:
        _LOG_RENDA.warning(
            "staging hex com %d carimbos de calibracao distintos; usando o modal %r",
            serie.nunique(), carimbo,
        )
    _LOG_RENDA.info("k de calibracao do hex = %s (carimbo %r)", k, carimbo)
    return k


def fator_hex(uf: str | None, cod_municipio: str | None, tipo: str) -> float:
    """(moradores_muni x uplift_muni) x F_tipo(uf): base do hex -> renda do tipo pedido.

    Sem o `except Exception: return None` da redacao antiga: insumo quebrado aparece como
    erro, nao como card vazio sem log.
    """
    return (
        moradores_por_domicilio(uf, cod_municipio) * uplift_municipio(uf, cod_municipio)
    ) * fator(uf, tipo)


def base_renda_domiciliar(
    valor: object, origem: object, uf: str | None, cod: str | None, k: Callable[[], float]
) -> float | None:
    """Base da renda do hex, na escala da renda do RESPONSAVEL per capita (V06004/moradores).

      - `renda_per_capita_setor_2022_calibrada` = V06004/moradores x k  -> dividir pelo k.
      - `renda_per_capita` (SIDRA t.10295 v.13431) JA e renda domiciliar per capita -> dividir
        pelo uplift do municipio, senao o fator do hex aplica o uplift uma segunda vez.

    `k` e chamavel: so o ramo da calibrada le o carimbo.
    """
    if valor is None or pd.isna(valor):  # type: ignore[call-overload]
        return None
    if origem == "renda_per_capita_setor_2022_calibrada":
        return float(valor) / k()  # type: ignore[arg-type]
    if origem == "renda_per_capita":
        uplift = uplift_municipio(uf, cod)
        return float(valor) / uplift if uplift else None  # type: ignore[arg-type]
    return float(valor)  # type: ignore[arg-type]


def renda_domiciliar_hex(base: float | None, uf: str | None, cod: str | None) -> float | None:
    """Renda media domiciliar do hex = base x fator_hex(..., "domiciliar"). Sem arredondar."""
    if base is None:
        return None
    return base * fator_hex(uf, cod, "domiciliar")


def renda_per_capita_hex(base: float | None, uf: str | None, cod: str | None) -> float | None:
    """Renda domiciliar per capita do hex = round(base x fator_hex(..., "per_capita")) / moradores.

    Com o PROPRIO fator, nunca a domiciliar dividida. O `round` intermediario e um
    arredondamento de EXIBICAO herdado: reproduz bit a bit o `_num(dom) / moradores` do
    `app.py` de antes da E0 (que dividia a domiciliar ja arredondada a reais). A revisar na E3,
    quando a per capita do hex passar a vir das colunas da malha.
    """
    if base is None:
        return None
    bruto = base * fator_hex(uf, cod, "per_capita")
    if not math.isfinite(bruto):
        return None
    moradores = moradores_por_domicilio(uf, cod)
    return round(bruto) / moradores if moradores else None


def renda_domiciliar_por_hex(
    df: pd.DataFrame,
    *,
    uf: str | None,
    cod_municipio: str | None,
    staging_dir: Path,
) -> dict[str, float]:
    """`hex_id` -> renda media domiciliar (R$/mes) dos hexagonos de UM municipio.

    O mesmo numero que o card do REP mostra em "Renda domiciliar". Hexagono sem renda em
    nenhuma coluna fica fora do mapa (a coluna sai "n/d"), nunca zero.
    """
    if df is None or df.empty or "hex_id" not in df.columns or not cod_municipio:
        return {}
    fator_dom = fator_hex(uf, cod_municipio, "domiciliar")
    k_lido: list[float] = []

    def _k() -> float:
        if not k_lido:
            k_lido.append(k_calibracao_renda(staging_dir))
        return k_lido[0]

    valor, origem = serie_renda(df)
    out: dict[str, float] = {}
    for hex_id, v, o in zip(df["hex_id"].astype(str), valor, origem, strict=True):
        base = base_renda_domiciliar(v, o, uf, cod_municipio, _k)
        if base is not None:
            out[hex_id] = base * fator_dom
    return out
