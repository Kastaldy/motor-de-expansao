"""As duas paginas da praca no Relatorio Pontual: "Pressao concorrencial" e "Como a cidade esta indo".

Montagem UNICA para os dois geradores do pontual: o piloto web (`app._praca_para_pdf`) e a API
publica (`service._praca_do_ponto`, com `paginas_praca` no corpo). Cada lado so' CARREGA os
dados do seu jeito -- o piloto pelo `carregar_uf` (cache da tela), a API pelos parquets da
staging -- e entrega aqui o mesmo recorte: os hexagonos do municipio (com `cres_hex_*`), a linha
municipal da camada de crescimento e os pins. Daqui para frente as regras sao uma so': a frase,
as linhas da pagina, o hexagono do ponto contra a mediana da cidade e o mapa dos raios de 750 m.

Logica em `relatorio_praca.py`; PNG em `relatorio_praca_mapas.py`. Nenhum caminho daqui derruba
o PDF: mapa que falha vira fallback textual; municipio ou hexagono sem crescimento viram a frase
de "sem dado".
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from typing import Any

import pandas as pd

from motor_expansao.dashboard import relatorio_praca as rp
from motor_expansao.dashboard import relatorio_praca_mapas as rpm


def _tem_taxa(linha_hex: Mapping[str, Any] | None) -> bool:
    if linha_hex is None:
        return False
    taxa = pd.to_numeric(pd.Series([linha_hex.get(rp.COL_CRES_HEX_TAXA)]), errors="coerce").iloc[0]
    return not pd.isna(taxa)


def montar_praca_do_ponto(
    lat: float,
    lng: float,
    *,
    uf: str,
    nome_municipio: str | None,
    hexes_cidade: pd.DataFrame,
    linha_crescimento: Mapping[str, Any] | None,
    carregar_crescimento_hex: Callable[[], pd.DataFrame | None],
    comp_df: pd.DataFrame | None,
    ultra_df: pd.DataFrame | None,
    leitura: bool,
    rotulo_tendencia: Mapping[str, str],
    basemap: bool = True,
    log: logging.Logger | None = None,
) -> rp.PracaDoPonto:
    """A `PracaDoPonto` das duas paginas a partir do recorte ja' carregado.

    `hexes_cidade`: hexagonos do municipio (`relatorio_praca.filtrar_hexes_do_municipio`), com
    `cres_hex_taxa`/`cres_hex_classe` ja' juntados quando a camada existe. `linha_crescimento`:
    a linha municipal (chaves de `COLS_CRESCIMENTO_MUNICIPAL`; ausente -> None). `leitura=True`
    na instancia com a regua da recomendacao unica (DEC-077): sem o veredito "E' praca para
    entrar", nem na frase nem pelo fallback do `resumir_crescimento`.
    `carregar_crescimento_hex`: so' chamado quando o hexagono do ponto nao esta' na cidade (ponto
    na divisa) ou esta' sem taxa.
    """
    import h3

    log = log or logging.getLogger("motor_expansao.relatorio_praca")

    municipio = nome_municipio or (
        str(hexes_cidade["nome_municipio"].dropna().iloc[0])
        if "nome_municipio" in hexes_cidade.columns and hexes_cidade["nome_municipio"].notna().any()
        else ""
    )
    municipio = municipio.title() if municipio.isupper() else municipio

    # NaN -> None aqui: a linha lida do parquet (API) traz NaN onde a tendencia e' nula de
    # proposito, e `is not None` abaixo a contaria como dado. O piloto ja' chega sem NaN.
    linha = {c: rp._valor(linha_crescimento or {}, c) for c in rp.COLS_CRESCIMENTO_MUNICIPAL}
    linha_resumo = dict(linha)
    if leitura:
        linha_resumo.pop("v_frase", None)
        tem_cres = linha.get("cres_tendencia") is not None or bool(
            rp._texto_ou_none(linha.get("cres_dims")) or rp._texto_ou_none(linha.get("cres_series"))
        )
    else:
        tem_cres = linha.get("cres_tendencia") is not None or bool(linha.get("v_frase"))
    frase = (
        rp.narrativa_crescimento(
            linha, municipio, uf=str(uf).upper(), rotulo_tendencia=rotulo_tendencia, leitura=leitura
        )
        if tem_cres
        else None
    )
    crescimento = rp.resumir_crescimento(
        linha_resumo, uf=uf, frase=frase, rotulo_tendencia=rotulo_tendencia
    )

    # Hexagono do ponto: primeiro na propria cidade (ja com `cres_hex_*`); ponto na divisa cai num
    # hexagono de outro municipio, e ai' a leitura vem direto da camada por hexagono.
    hex_ponto = str(h3.latlng_to_cell(lat, lng, 7))
    linha_hex: dict[str, Any] | None = None
    if "hex_id" in hexes_cidade.columns:
        achados = hexes_cidade.loc[hexes_cidade["hex_id"].astype(str) == hex_ponto]
        if len(achados):
            linha_hex = achados.iloc[0].to_dict()
    if not _tem_taxa(linha_hex):
        chex = carregar_crescimento_hex()
        if chex is not None:
            achados = chex.loc[chex["hex_id"].astype(str) == hex_ponto]
            if len(achados):
                linha_hex = achados.iloc[0].to_dict()
    crescimento_hex = rp.crescimento_do_hexagono(linha_hex, hexes_cidade)

    mapas: dict[str, bytes] = {}
    for fundo in ((True, False) if basemap else (False,)):
        try:
            mapas["pressao_raios"] = rpm.render_pressao_raios(lat, lng, comp_df, ultra_df, basemap=fundo)
            break
        except Exception as exc:  # noqa: BLE001 - mapa que falha vira fallback textual
            log.warning("mapa pressao_raios (fundo=%s) falhou: %r", fundo, exc)

    log.info(
        "praca %s/%s: hexagono %s, crescimento=%s, obra nova=%s",
        municipio, uf, hex_ponto, crescimento.disponivel, crescimento_hex.disponivel,
    )
    return rp.PracaDoPonto(
        municipio=municipio,
        uf=uf,
        pressao=rp.pressao_sobre_ponto(lat, lng, comp_df, ultra_df),
        crescimento=crescimento,
        crescimento_hex=crescimento_hex,
        mapas=mapas,
    )
