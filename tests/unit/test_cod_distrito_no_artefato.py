"""`cod_distrito` no artefato geo (F0.1) — a coluna que o DBF sempre teve.

O `CD_DIST` (9 digitos: municipio + distrito) esta no `BR_setores_CD2022.dbf` desde sempre, e
o pipeline nao o lia: o artefato saia com o NOME do distrito e sem o codigo. Isso obrigava a
agregar por distrito casando NOME + municipio + UF, e deixava o ETL das bases de referencia do
`banco-de-reservas` sem a chave que o proprio de-para dele pressupoe.

Estes testes olham o CONTRATO do pipeline, nao dados: rodar a materializacao exige a malha de
1,2 GB e nao cabe em teste unitario. O que garante o VALOR e' o
`scripts/comparar_artefato_geo.py`, que o operador roda entre o artefato antigo e o novo.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from motor_expansao.pipelines import materializar_setores_censitarios_geo as pipeline

FONTE = Path(pipeline.__file__).read_text(encoding="utf-8")


def test_cod_distrito_esta_no_contrato_do_artefato() -> None:
    assert "cod_distrito" in pipeline.COLUNAS_ARTEFATO


def test_cod_distrito_vem_logo_apos_nome_subdistrito() -> None:
    """A ordem das colunas e' o contrato lido por quem consome o parquet; agrupar o codigo
    junto do nome do distrito mantem a leitura obvia."""
    colunas = list(pipeline.COLUNAS_ARTEFATO)
    assert colunas.index("cod_distrito") == colunas.index("nome_distrito") - 1


def test_a_leitura_da_malha_pede_o_CD_DIST() -> None:
    """Sem o campo na lista de colunas lidas do shapefile, o resto e' inalcancavel."""
    assert '"CD_DIST"' in FONTE


def test_o_codigo_e_normalizado_com_9_digitos() -> None:
    """`CD_DIST` tem 9 posicoes (7 do municipio + 2 do distrito). Normalizar com outro
    tamanho produziria codigo truncado ou com zeros a mais — e o erro so' apareceria ao
    cruzar com a malha, muito depois."""
    assert re.search(r'gdf\["CD_DIST"\]\.map\(lambda value: _normalizar_codigo_ibge\(value, 9\)\)', FONTE)


def test_setor_sem_municipio_e_descartado() -> None:
    """A particao `uf=RS/cod_municipio=000None/` vinha de `str(None).zfill(7)`. Sao as duas
    lagoas costeiras do RS — pseudo-municipios do IBGE para massa d'agua — e era esse par que
    fazia o artefato reportar 5.571 municipios num pais de 5.570."""
    assert "sem_municipio = gdf[\"cod_municipio\"].isna()" in FONTE
    assert "gdf = gdf[~sem_municipio].copy()" in FONTE


def test_o_municipio_usa_o_normalizador_e_nao_zfill_cru() -> None:
    """A causa do `000None`: `astype(str).str.zfill(7)` transforma ausencia em texto. O
    normalizador devolve NA, que e' o que permite o descarte acima existir."""
    assert 'gdf["cod_municipio"] = gdf["CD_MUN"].map(' in FONTE
    assert 'gdf["cod_municipio"] = gdf["CD_MUN"].astype(str).str.zfill(7)' not in FONTE


@pytest.mark.parametrize("coluna", ["cod_bairro", "cod_distrito", "nome_distrito"])
def test_as_colunas_de_unidade_administrativa_toleram_ausencia(coluna: str) -> None:
    """Toda coluna vinda do DBF tem ramo `else: pd.NA`. Uma malha futura sem o campo faria o
    pipeline morrer em vez de degradar, e a materializacao inteira cairia por um atributo."""
    campo = {"cod_bairro": "CD_BAIRRO", "cod_distrito": "CD_DIST", "nome_distrito": "NM_DIST"}[coluna]
    assert f'if "{campo}" in gdf.columns:' in FONTE
    assert f'gdf["{coluna}"] = pd.NA' in FONTE
