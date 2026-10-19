"""Renda media domiciliar por HEXAGONO: UMA redacao para o card do REP e o Relatorio Municipal.

Ate 2026-10-16 as duas superficies tinham formulas proprias sobre o mesmo Censo 2022. O card
(`web/server/app.py`, `_hex_dict`) le a coluna do hexagono, agregada da malha setorial por area;
o PDF municipal jogava o setor INTEIRO no hexagono do centro do bbox dele
(`relatorio_municipal.carregar_renda_domiciliar_por_hex`). Em Sao Roque/SP o 87a810361ffffff
saia R$ 13.261 no PDF e R$ 4.924 no card. Esta e' a formula do card, que passa a valer para os
dois -- `app.py` delega para ca, e o preparo do PDF (`service.montar_pdf_municipio`) tambem.

    renda_domiciliar = base x moradores_muni x uplift_muni x fator_temporal

onde a base desfaz a escala da coluna de origem (ver `base_renda_domiciliar`).
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Sequence
from pathlib import Path

import pandas as pd

_LOG_RENDA = logging.getLogger("piloto.renda")

#: Precedencia da renda do hexagono: setor (granular) primeiro, municipio (SIDRA, o MESMO
#: numero repetido em toda a cidade) como fallback.
COLS_RENDA_LEITURA: tuple[str, ...] = (
    "renda_per_capita_setor_2022_calibrada",
    "renda_per_capita",
)

# k do STAGING HEX (censo2022_setores_calibrado.parquet, safra 2026-05) — NAO confundir com o
# k do artefato GEO setorial (1,2335 na safra 2026-08-12): sao calibracoes independentes.
K_CALIBRACAO_FALLBACK = 1.0239
CENSO_HEX_STAGING_PARQUET = "censo2022_setores_calibrado.parquet"
# Artefato da MALHA (agregado dos setores). Quando existe, e ELE quem carrega o k da
# coluna servida — ver `k_calibracao_renda`.
CENSO_MALHA_PARQUET = "censo2022_hex_da_malha.parquet"
_RE_K_CARIMBO = re.compile(r"k=([0-9]+(?:\.[0-9]+)?)")


def serie_renda(
    df: pd.DataFrame, precedencia: Sequence[str] = COLS_RENDA_LEITURA
) -> tuple[pd.Series, pd.Series]:
    """Renda de leitura POR LINHA, mais a origem de CADA valor.

    A escolha e' por LINHA e nao por COLUNA. A redacao anterior parava na primeira coluna
    PRESENTE e usava so' ela para o frame inteiro, o que produzia dois defeitos de uma vez:

      1. `renda_origem` saia ESCALAR. Como o artefato nacional tem a coluna de setor no
         schema, a origem era `renda_per_capita_setor_2022_calibrada` em 1.542.531 de
         1.542.531 hexagonos -- e o aviso `renda_municipal` do payload, criado justamente
         para dizer ao operador quando o numero e' da cidade inteira, nascia constante
         `False`. Quatro ramos de rotulo do front ficavam inalcancaveis.
      2. 234.147 hexagonos (15,18%) tem a coluna de setor PRESENTE e NULA naquela linha,
         com a municipal disponivel -- AM 129.823, PA 45.941, RR 15.562, MT 11.091. Eles
         nao exibiam renda NENHUMA, tendo um numero legitimo (ainda que municipal) ao lado.

    E' a mesma familia da DEC-038: a precedencia por COLUNA trata "a coluna existe" como
    "o valor existe". Aqui a coluna existe e o valor, naquela linha, nao.

    Devolve `(valor, origem)`; `origem` e' o NOME DA COLUNA de onde cada valor veio (`None`
    onde nenhuma tinha valor) -- identificador, nao rotulo: quem exibe traduz.
    """
    valor = pd.Series(float("nan"), index=df.index, dtype="float64")
    # `[None] * n` e nao o escalar `None`: com o escalar o pandas materializa NaN, e o
    # consumidor teria de distinguir "sem origem" de "origem NaN" -- duas grafias da mesma
    # ausencia, que e' como ausencia vira ramo esquecido.
    origem = pd.Series([None] * len(df), index=df.index, dtype="object")
    for coluna in precedencia:
        if coluna not in df.columns:
            continue
        candidato = pd.to_numeric(df[coluna], errors="coerce")
        # So' preenche o que ainda esta' vazio: a precedencia se mantem, agora por linha.
        preencher = valor.isna() & candidato.notna()
        if not preencher.any():
            continue
        valor = valor.where(~preencher, candidato)
        origem = origem.where(~preencher, coluna)
    return valor, origem


def k_calibracao_renda(staging_dir: Path) -> float:
    """O `k` com que a coluna calibrada DO HEX foi gerada, lido do carimbo do staging hex.

    `renda_per_capita_setor_2022_calibrada` do enriquecido nasce do STAGING HEX
    (`censo2022_setores_calibrado.parquet`), nao do artefato geo setorial — e cada um carrega
    seu proprio k (staging 1,0239; geo 1,2335 na safra de 2026-08-12). Ate 2026-08-14 este
    helper lia o `_metadata.json` do GEO: desfazia um k que a coluna nunca teve, a base saia
    0,83x a correta e a renda do tooltip ~17% abaixo do IBGE. A fonte certa e o carimbo
    `metodo_calibracao_renda` ("multiplicativo_global_k=X") gravado no proprio staging hex.

    Guarda de plausibilidade [0,5; 3,0] e fallback para a constante da safra conhecida, sempre
    com log — NUNCA cair em 1,0 em silencio: reintroduziria a dupla contagem sem pista.
    """
    # Desde 2026-08-31 a coluna calibrada SERVIDA e' agregada da MALHA setorial
    # (`sobrepor_renda_da_malha`), com o k da malha — nao mais o k do staging hex. A fonte
    # do carimbo tem de acompanhar a fonte do VALOR: ler o carimbo antigo aqui desfaria um
    # k que a coluna nao tem mais e erraria a renda domiciliar em 20,47%, que e' o mesmo
    # defeito de 2026-08-14 com o sinal trocado. Ordem = precedencia: malha primeiro.
    staging_dir = Path(staging_dir)
    fontes = (
        (staging_dir / CENSO_MALHA_PARQUET, "metodo_calibracao_renda_malha"),
        (staging_dir / CENSO_HEX_STAGING_PARQUET, "metodo_calibracao_renda"),
    )
    try:
        disponiveis = [(caminho, coluna) for caminho, coluna in fontes if caminho.exists()]
        if not disponiveis:
            raise FileNotFoundError(f"nenhum de {[str(p) for p, _ in fontes]}")
        caminho, coluna = disponiveis[0]
        serie = pd.read_parquet(caminho, columns=[coluna])[coluna].dropna()
        carimbo = str(serie.mode().iloc[0])
        k = float(_RE_K_CARIMBO.search(carimbo).group(1))  # type: ignore[union-attr]
    except Exception as exc:  # noqa: BLE001 — staging ausente/carimbo ilegivel: constante conhecida
        _LOG_RENDA.warning(
            "k de calibracao do hex: carimbo ilegivel em %s (%s); usando fallback %s",
            [str(p) for p, _ in fontes], exc, K_CALIBRACAO_FALLBACK,
        )
        return K_CALIBRACAO_FALLBACK
    if not 0.5 <= k <= 3.0:
        _LOG_RENDA.warning(
            "k de calibracao do hex fora da faixa plausivel (%s); usando fallback %s",
            k, K_CALIBRACAO_FALLBACK,
        )
        return K_CALIBRACAO_FALLBACK
    if serie.nunique() > 1:
        _LOG_RENDA.warning(
            "staging hex com %d carimbos de calibracao distintos; usando o modal %r",
            serie.nunique(), carimbo,
        )
    _LOG_RENDA.info("k de calibracao do hex = %s (carimbo %r)", k, carimbo)
    return k


def fator_domiciliar(
    uf: str | None, cod_municipio: str | None, fator_temporal: float
) -> float | None:
    """Fator renda per capita -> renda media domiciliar do municipio.

    = moradores_por_domicilio x uplift_renda_domiciliar x FATOR_TEMPORAL_RENDA
    (todos MUNICIPAIS, como no tooltip do Streamlit — um hex res-7 cobre varios
    setores, entao o uplift setorial nao se aplica ao hex). Um hex pertence a UM
    municipio, entao o fator e um escalar por chamada.
    """
    from motor_expansao.dashboard.constants import (
        moradores_por_domicilio,
        uplift_renda_domiciliar,
    )

    try:
        return (
            moradores_por_domicilio(uf, cod_municipio)
            * uplift_renda_domiciliar(uf, cod_municipio)
            * fator_temporal
        )
    except Exception:  # noqa: BLE001 — enriquecimento opcional, degrada gracioso
        return None


def base_renda_domiciliar(
    valor: object, origem: object, uf: str | None, cod: str | None, k: Callable[[], float]
) -> float | None:
    """Base da renda domiciliar do hex, na escala da renda do RESPONSAVEL per capita.

    `fator_domiciliar` multiplica por `moradores x uplift x fator_temporal`; para o resultado
    ser a renda do domicilio, a base tem de ser V06004/moradores — nem mais, nem menos. As duas
    colunas de origem estao em escalas diferentes e precisam de tratamento distinto:

      - `renda_per_capita_setor_2022_calibrada` = V06004/moradores x k  -> dividir pelo k.
        Ate 2026-08-13 usava-se ela crua, e o k sobrava: +23,35% na renda exibida.
      - `renda_per_capita` (SIDRA t.10295 v.13431) JA e renda domiciliar per capita -> dividir
        pelo uplift do municipio, senao o `fator_domiciliar` aplica o uplift uma segunda vez.
        Esse ramo estava +54,4% errado, e COM dispersao (o uplift varia de 1,42 a 1,86 entre
        municipios), entao distorcia tambem a comparacao entre cidades.

    `k` e' chamavel: so' o ramo da calibrada le o carimbo.
    """
    if valor is None or pd.isna(valor):  # type: ignore[call-overload]
        return None
    if origem == "renda_per_capita_setor_2022_calibrada":
        return float(valor) / k()  # type: ignore[arg-type]
    if origem == "renda_per_capita":
        from motor_expansao.dashboard.constants import uplift_renda_domiciliar

        uplift = uplift_renda_domiciliar(uf, cod)
        return float(valor) / uplift if uplift else None  # type: ignore[arg-type]
    return float(valor)  # type: ignore[arg-type]


def renda_domiciliar_por_hex(
    df: pd.DataFrame,
    *,
    uf: str | None,
    cod_municipio: str | None,
    staging_dir: Path,
    fator_temporal: float | None = None,
) -> dict[str, float]:
    """`hex_id` -> renda media domiciliar (R$/mes) dos hexagonos de UM municipio.

    O mesmo numero que o card do REP mostra em "Renda domiciliar". `fator_temporal` ausente ->
    `constants.FATOR_TEMPORAL_RENDA` lido na hora (o web reaponta o modulo no boot). Hexagono
    sem renda em nenhuma coluna fica fora do mapa (a coluna sai "n/d"), nunca zero.
    """
    if df is None or df.empty or "hex_id" not in df.columns or not cod_municipio:
        return {}
    if fator_temporal is None:
        from motor_expansao.dashboard import constants as _const

        fator_temporal = float(_const.FATOR_TEMPORAL_RENDA)
    fator = fator_domiciliar(uf, cod_municipio, fator_temporal)
    if fator is None:
        return {}
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
            out[hex_id] = base * fator
    return out
