"""Renda por HEXAGONO: UMA redacao para o card do REP, o tooltip, a ficha e o Relatorio Municipal.

Movido de `dashboard/renda_hex.py` (E0; DEC-072). Ate 2026-10-16 o card e o PDF municipal
tinham formulas proprias sobre o mesmo Censo 2022 (Sao Roque/SP, 87a810361ffffff: R$ 13.261
no PDF contra R$ 4.924 no card). Esta e a formula do card, que vale para os dois:

    fator_hex(uf, cod, tipo) = (moradores_muni x uplift_muni) x F_tipo(uf)
    renda_domiciliar_hex     = base x fator_hex(..., "domiciliar")
    renda_per_capita_hex     = round(base x fator_hex(..., "per_capita")) / moradores_muni

onde a base desfaz a escala da coluna de origem (ver `base_renda_domiciliar`). Um hexagono
res-7 cobre varios setores, entao uplift e moradores sao MUNICIPAIS: um escalar por municipio.

E3 (frente c do plano): quando a linha do hexagono traz as colunas da MALHA
(`renda_domiciliar_2022_malha` / `renda_per_capita_domiciliar_2022_malha`, agregadas dos
setores com o uplift e os moradores DO SETOR), a renda do hexagono passa a ser

    renda_domiciliar_hex <- renda_domiciliar_2022_malha            x F_dom(uf)
    renda_per_capita_hex <- renda_per_capita_domiciliar_2022_malha x F_pc(uf)

-- so o fator temporal, uma vez; nada de moradores, uplift ou k de novo, que ja estao dentro
das colunas. Sem as colunas (artefato antigo) ou sem valor para o hexagono (hexagono sem setor
com renda, origem municipal), a formula de cima vale LINHA A LINHA, bit a bit como antes.
"""

from __future__ import annotations

import logging
import math
import os
import re
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

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
#: Colunas da MALHA (E3): renda de 2022 do hexagono agregada dos setores, SEM fator temporal.
#: A domiciliar e ponderada pelos domicilios dos pedacos de setor; a per capita, pela populacao.
COL_RENDA_DOM_MALHA = "renda_domiciliar_2022_malha"
COL_RENDA_PC_MALHA = "renda_per_capita_domiciliar_2022_malha"
COLS_RENDA_MALHA: tuple[str, ...] = (COL_RENDA_DOM_MALHA, COL_RENDA_PC_MALHA)
_COL_MALHA_POR_TIPO = {"domiciliar": COL_RENDA_DOM_MALHA, "per_capita": COL_RENDA_PC_MALHA}
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


def renda_2022_da_malha(
    linha: Mapping[str, Any] | None, origem: object, tipo: str
) -> float | None:
    """Renda de 2022 do hexagono pela MALHA (coluna do `tipo` pedido), ou None.

    So vale quando a leitura do hexagono e a SETORIAL (`origem` = a coluna calibrada): a malha
    refina a mesma grandeza com moradores e uplift do setor. Origem municipal (SIDRA), linha
    sem a coluna (artefato antigo) ou valor ausente/nao positivo -> None, e o chamador cai na
    formula municipal de antes.
    """
    if linha is None or origem != COLS_RENDA_LEITURA[0]:
        return None
    try:
        valor = float(linha.get(_COL_MALHA_POR_TIPO[tipo]))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return valor if math.isfinite(valor) and valor > 0 else None


def renda_domiciliar_hex(
    base: float | None,
    uf: str | None,
    cod: str | None,
    *,
    linha: Mapping[str, Any] | None = None,
    origem: object = None,
) -> float | None:
    """Renda media domiciliar do hex. Sem arredondar.

      - com a malha na `linha` (E3): `renda_domiciliar_2022_malha x F_dom(uf)`;
      - senao: `base x fator_hex(..., "domiciliar")` (moradores e uplift do municipio).
    """
    malha = renda_2022_da_malha(linha, origem, "domiciliar")
    if malha is not None:
        return malha * fator(uf, "domiciliar")
    if base is None:
        return None
    return base * fator_hex(uf, cod, "domiciliar")


def renda_per_capita_hex(
    base: float | None,
    uf: str | None,
    cod: str | None,
    *,
    linha: Mapping[str, Any] | None = None,
    origem: object = None,
) -> float | None:
    """Renda domiciliar per capita do hex, com o PROPRIO fator -- nunca a domiciliar dividida.

      - com a malha na `linha` (E3): `renda_per_capita_domiciliar_2022_malha x F_pc(uf)`, sem
        arredondamento intermediario (a per capita ja vem pronta da malha);
      - senao: `round(base x fator_hex(..., "per_capita")) / moradores_muni`. O `round`
        intermediario e um arredondamento de EXIBICAO herdado: reproduz bit a bit o
        `_num(dom) / moradores` do `app.py` de antes da E0.
    """
    malha = renda_2022_da_malha(linha, origem, "per_capita")
    if malha is not None:
        return malha * fator(uf, "per_capita")
    if base is None:
        return None
    bruto = base * fator_hex(uf, cod, "per_capita")
    if not math.isfinite(bruto):
        return None
    moradores = moradores_por_domicilio(uf, cod)
    return round(bruto) / moradores if moradores else None


def colunas_malha_por_hex(
    hex_ids: Sequence[str], staging: Path | str | None = None
) -> pd.DataFrame:
    """As colunas da malha (E3) dos `hex_ids`, lidas do artefato da malha no staging.

    Para superficies que leem o hexagono de um artefato que NAO carrega as colunas (a ficha
    da rede le `hexagonos_mercado_mapeado.parquet`): sem elas a ficha cairia na formula
    municipal e mostraria outro numero que o tooltip para o mesmo hexagono. Indexado por
    `hex_id`. Artefato ausente ou sem as colunas (malha anterior a E3) -> frame vazio, e a
    linha cai sozinha na formula de antes.
    """
    caminho = (Path(staging) if staging is not None else staging_dir()) / CENSO_MALHA_PARQUET
    vazio = pd.DataFrame(columns=list(COLS_RENDA_MALHA), index=pd.Index([], name="hex_id"))
    ids = sorted({str(h) for h in hex_ids if h is not None})
    if not ids or not caminho.is_file():
        return vazio
    import pyarrow.compute as pc
    import pyarrow.dataset as ds

    conjunto = ds.dataset(str(caminho))
    if not set(COLS_RENDA_MALHA) <= set(conjunto.schema.names):
        return vazio
    return (
        conjunto.to_table(
            filter=pc.field("hex_id").isin(ids), columns=["hex_id", *COLS_RENDA_MALHA]
        )
        .to_pandas()
        .drop_duplicates("hex_id")
        .set_index("hex_id")
    )


def _com_colunas_malha(df: pd.DataFrame, staging: Path | str | None) -> pd.DataFrame:
    """`df` com as colunas da malha; anexadas do staging quando o frame nao as traz.

    O Relatorio Municipal do BOT recorta o artefato de MERCADO (sem as colunas) e o do piloto
    recorta o ENRIQUECIDO (com elas): sem este passo o mesmo municipio sairia com dois numeros
    conforme a porta. Frame que ja tem as colunas passa intacto (o artefato manda).
    """
    faltam = [c for c in COLS_RENDA_MALHA if c not in df.columns]
    if not faltam or "hex_id" not in df.columns:
        return df
    malha = colunas_malha_por_hex(df["hex_id"].astype(str).tolist(), staging)
    if malha.empty:
        return df
    out = df.copy()
    ids = out["hex_id"].astype(str)
    for coluna in faltam:
        out[coluna] = ids.map(malha[coluna]).to_numpy()
    return out


def _serie_malha(df: pd.DataFrame, tipo: str) -> pd.Series:
    """A coluna da malha do `tipo` (NaN onde o artefato nao a tem)."""
    coluna = _COL_MALHA_POR_TIPO[tipo]
    if coluna not in df.columns:
        return pd.Series(float("nan"), index=df.index, dtype="float64")
    return pd.to_numeric(df[coluna], errors="coerce")


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
    df = _com_colunas_malha(df, staging_dir)
    k_lido: list[float] = []

    def _k() -> float:
        if not k_lido:
            k_lido.append(k_calibracao_renda(staging_dir))
        return k_lido[0]

    valor, origem = serie_renda(df)
    malha = _serie_malha(df, "domiciliar")
    out: dict[str, float] = {}
    for hex_id, v, o, m in zip(df["hex_id"].astype(str), valor, origem, malha, strict=True):
        dom_malha = renda_2022_da_malha({COL_RENDA_DOM_MALHA: m}, o, "domiciliar")
        if dom_malha is not None:
            out[hex_id] = dom_malha * fator(uf, "domiciliar")
            continue
        base = base_renda_domiciliar(v, o, uf, cod_municipio, _k)
        if base is not None:
            out[hex_id] = base * fator_dom
    return out


def renda_per_capita_por_linha(
    df: pd.DataFrame,
    *,
    precedencia: Sequence[str] = COLS_RENDA_LEITURA,
    uf: str | None = None,
    cod_municipio: str | None = None,
    staging_dir: Path | str | None = None,
) -> pd.Series:
    """Renda domiciliar per capita CANONICA de cada hexagono de `df` (float64, NaN sem leitura).

    A mesma cadeia do card (`serie_renda` -> `base_renda_domiciliar` -> `renda_per_capita_hex`),
    para superficies que ate a E1 exibiam a coluna de origem CRUA (a calibrada na escala do
    score, ou a SIDRA municipal sem fator). `precedencia` restringe as colunas lidas -- o
    painel per capita municipal, por exemplo, le so a SIDRA (`("renda_per_capita",)`).

    UF e municipio da cascata: os da PROPRIA linha (`uf`/`cod_municipio`) quando existem;
    senao, os argumentos. Sem municipio a cascata cai na mediana da UF (nao em branco): quem
    exige o municipio, como o tooltip, filtra antes de chamar.
    """
    if df is None or df.empty:
        return pd.Series(dtype="float64")
    if COLS_RENDA_LEITURA[0] in precedencia:  # a malha so refina a leitura SETORIAL
        df = _com_colunas_malha(df, staging_dir)
    valor, origem = serie_renda(df, precedencia)
    k_lido: list[float] = []

    def _k() -> float:
        if not k_lido:
            k_lido.append(k_calibracao_renda(staging_dir))
        return k_lido[0]

    def _txt(v: object) -> str | None:
        if v is None or v is pd.NA or (isinstance(v, float) and math.isnan(v)):
            return None
        s = str(v).strip().removesuffix(".0")
        return s or None

    ufs = df["uf"] if "uf" in df.columns else pd.Series([None] * len(df), index=df.index)
    cods = (
        df["cod_municipio"]
        if "cod_municipio" in df.columns
        else pd.Series([None] * len(df), index=df.index)
    )
    malha = _serie_malha(df, "per_capita")
    saida: list[float] = []
    for v, o, uf_l, cod_l, m in zip(valor, origem, ufs, cods, malha, strict=True):
        uf_x = _txt(uf_l) or uf
        cod_x = _txt(cod_l) or cod_municipio
        base = base_renda_domiciliar(v, o, uf_x, cod_x, _k)
        pc = renda_per_capita_hex(base, uf_x, cod_x, linha={COL_RENDA_PC_MALHA: m}, origem=o)
        saida.append(float("nan") if pc is None else float(pc))
    return pd.Series(saida, index=df.index, dtype="float64")
