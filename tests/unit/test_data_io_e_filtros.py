"""Reancoragem BLK-WEB-19 (DEC-022): I/O particionado e filtros globais sem Streamlit.

A cobertura destes helpers de `dashboard/data.py` vivia nos testes da UI Streamlit
(que serao deletados no corte do Streamlit): leitores de parquet particionado
(`uf=XX` e `uf=XX/cod_municipio=N`), catalogos leves de particao para a sidebar,
`apply_global_filters` (o coracao da filtragem de todas as abas) e os delegates
finos para `pipelines/pop_corte.py`. Estes testes reancoram os mesmos contratos
direto nas funcoes puras, com parquets SINTETICOS em tmp_path — nada aqui le os
artefatos oficiais nem recalcula score (CLAUDE.md §2).
"""

from __future__ import annotations

from pathlib import Path

import h3
import numpy as np
import pandas as pd
import pytest

from motor_expansao.dashboard.constants import OPTIONAL_DATASET_COLUMNS
from motor_expansao.dashboard.data import (
    _has_censo_signal,
    _normalized_join_quality,
    _read_optional_parquet_subset,
    _read_parquet_subset,
    apply_global_filters,
    list_censo_geo_municipios,
    list_partitioned_ufs,
    read_censo_geo_partition,
    read_enriched_uf_partition,
)

# Celulas H3 REAIS (res 7): `read_enriched_uf_partition` valida o frame via
# `validate_dashboard_frame`, que rejeita hex_id que nao seja celula H3 valida.
_HEX_BSB = h3.latlng_to_cell(-15.79, -47.88, 7)
_HEX_SP = h3.latlng_to_cell(-23.55, -46.63, 7)


# ---------------------------------------------------------------------------
# _read_parquet_subset — subset de colunas + opcionais do dataset oficial
# ---------------------------------------------------------------------------


def _gravar_parquet(path: Path, frame: pd.DataFrame) -> None:
    frame.to_parquet(path, index=False)


def test_read_parquet_subset_anexa_opcionais_presentes_no_arquivo(tmp_path: Path) -> None:
    """Alem das colunas pedidas, o leitor anexa as OPTIONAL_DATASET_COLUMNS que
    existirem no arquivo — e NAO carrega colunas extras nao pedidas (projecao)."""
    path = tmp_path / "oficial.parquet"
    _gravar_parquet(
        path,
        pd.DataFrame(
            {
                "hex_id": ["a", "b"],
                "uf": ["DF", "SP"],
                "confianca_geografica": ["granular", "municipal"],
                "cod_municipio": ["5300108", "3550308"],
                "coluna_pesada_nao_pedida": [1.0, 2.0],
            }
        ),
    )

    frame = _read_parquet_subset(path, ["hex_id", "uf"])

    assert frame.columns.tolist() == ["hex_id", "uf", *OPTIONAL_DATASET_COLUMNS]
    assert frame["confianca_geografica"].tolist() == ["granular", "municipal"]


def test_read_parquet_subset_nao_duplica_opcional_ja_pedida(tmp_path: Path) -> None:
    """Opcional pedida explicitamente entra uma unica vez (o filtro `not in columns`
    evita coluna duplicada, que quebraria o frame a jusante)."""
    path = tmp_path / "oficial.parquet"
    _gravar_parquet(
        path,
        pd.DataFrame(
            {
                "hex_id": ["a"],
                "confianca_geografica": ["granular"],
                "cod_municipio": ["5300108"],
            }
        ),
    )

    frame = _read_parquet_subset(path, ["hex_id", "confianca_geografica"])

    assert frame.columns.tolist() == ["hex_id", "confianca_geografica", "cod_municipio"]


def test_read_parquet_subset_sem_opcionais_no_arquivo(tmp_path: Path) -> None:
    """Parquet legado sem as opcionais: retorna exatamente o subset pedido."""
    path = tmp_path / "legado.parquet"
    _gravar_parquet(path, pd.DataFrame({"hex_id": ["a"], "uf": ["DF"], "lat": [-15.0]}))

    frame = _read_parquet_subset(path, ["hex_id", "uf"])

    assert frame.columns.tolist() == ["hex_id", "uf"]


def test_read_parquet_subset_coluna_obrigatoria_ausente_levanta_valueerror(tmp_path: Path) -> None:
    """Coluna obrigatoria ausente e erro de CONTRATO do dataset oficial (fail-fast
    com o nome da coluna na mensagem), nunca um frame parcial silencioso."""
    path = tmp_path / "incompleto.parquet"
    _gravar_parquet(path, pd.DataFrame({"hex_id": ["a"]}))

    with pytest.raises(ValueError, match="score_priorizacao"):
        _read_parquet_subset(path, ["hex_id", "score_priorizacao"])


# ---------------------------------------------------------------------------
# _read_optional_parquet_subset — camadas opcionais degradam para vazio
# ---------------------------------------------------------------------------


def test_read_optional_parquet_arquivo_ausente_retorna_vazio(tmp_path: Path) -> None:
    """Camada opcional inexistente NAO e erro: o dashboard degrada sem a camada."""
    frame = _read_optional_parquet_subset(tmp_path / "nao_existe.parquet", ["hex_id"])
    assert frame.empty


def test_read_optional_parquet_sem_intersecao_de_colunas_retorna_vazio(tmp_path: Path) -> None:
    """Arquivo existe mas nenhuma coluna pedida esta nele: vazio, sem levantar
    (parquet de versao antiga da camada nao pode derrubar o load)."""
    path = tmp_path / "camada.parquet"
    _gravar_parquet(path, pd.DataFrame({"outra_coluna": [1]}))

    frame = _read_optional_parquet_subset(path, ["hex_id", "score_setor_2022_calibrado"])

    assert frame.empty


def test_read_optional_parquet_le_apenas_a_intersecao(tmp_path: Path) -> None:
    """Le so as colunas pedidas que existem (subset gracioso, sem KeyError)."""
    path = tmp_path / "camada.parquet"
    _gravar_parquet(path, pd.DataFrame({"hex_id": ["a"], "extra": [9], "score": [1.5]}))

    frame = _read_optional_parquet_subset(path, ["hex_id", "coluna_futura"])

    assert frame.columns.tolist() == ["hex_id"]
    assert frame["hex_id"].tolist() == ["a"]


# ---------------------------------------------------------------------------
# list_partitioned_ufs / list_censo_geo_municipios — catalogos leves de particao
# ---------------------------------------------------------------------------


def test_list_partitioned_ufs_ordena_e_ignora_entradas_estranhas(tmp_path: Path) -> None:
    """O catalogo da sidebar inspeciona so os nomes de diretorio `uf=XX`: arquivos
    soltos, diretorios sem o prefixo e `uf=` com valor vazio sao ignorados, e a
    saida e ordenada (ordem estavel do seletor de UF)."""
    (tmp_path / "uf=SP").mkdir()
    (tmp_path / "uf=DF").mkdir()
    (tmp_path / "uf=MG").mkdir()
    (tmp_path / "uf=").mkdir()  # valor vazio: filtrado
    (tmp_path / "_staging").mkdir()  # prefixo errado: ignorado
    (tmp_path / "uf=RJ").write_text("nao sou particao")  # ARQUIVO com prefixo certo: ignorado

    assert list_partitioned_ufs(tmp_path) == ["DF", "MG", "SP"]


def test_list_partitioned_ufs_base_inexistente_retorna_vazio(tmp_path: Path) -> None:
    """Dataset enriquecido ainda nao materializado: lista vazia, sem levantar."""
    assert list_partitioned_ufs(tmp_path / "nao_existe") == []


def test_list_censo_geo_municipios_ordena_ignora_estranhos_e_normaliza_uf(tmp_path: Path) -> None:
    """Mesmo contrato do catalogo de UFs no nivel `cod_municipio=N`, com a UF de
    entrada normalizada para maiuscula (a sidebar pode passar 'sp')."""
    uf_dir = tmp_path / "uf=SP"
    (uf_dir / "cod_municipio=3550308").mkdir(parents=True)
    (uf_dir / "cod_municipio=3509502").mkdir()
    (uf_dir / "cod_municipio=").mkdir()  # valor vazio: filtrado
    (uf_dir / "_tmp").mkdir()  # prefixo errado: ignorado
    (uf_dir / "manifest.txt").write_text("nao sou particao")  # arquivo: ignorado

    assert list_censo_geo_municipios(tmp_path, "sp") == ["3509502", "3550308"]


def test_list_censo_geo_municipios_uf_inexistente_retorna_vazio(tmp_path: Path) -> None:
    assert list_censo_geo_municipios(tmp_path, "AC") == []


# ---------------------------------------------------------------------------
# read_enriched_uf_partition — leitura hive `uf=XX` + _prepare_dataframe
# ---------------------------------------------------------------------------


def _linha_enriquecida(hex_id: str, **overrides) -> dict:
    """Linha minima valida do artefato enriquecido particionado.

    Sem `uf` (a particao hive carrega o valor) e sem `nome_municipio` — a ausencia
    e proposital para exercer o fallback `nome_municipio = cidade` de
    `_prepare_dataframe` (branch que o enrich nunca atinge, pois ele sempre cria a
    coluna antes)."""
    row = {
        "hex_id": hex_id,
        "lat": -15.79,
        "lng": -47.88,
        "cidade": "Brasilia",
        "regiao": "Centro-Oeste",
        "score_priorizacao": 90.0,
        "hex_score_estrutural": 85.0,
        "ajuste_executivo": 5.0,
        "faixa_oportunidade": "alta",
        "flag_viavel": True,
        "flag_prioridade": True,
        "rank_brasil": 1.0,
        "rank_uf": 1.0,
        "rank_cidade": 1.0,
        "renda_per_capita": 6000.0,
        "populacao_proxy": 18000.0,
    }
    row.update(overrides)
    return row


def _gravar_particao_enriquecida(base: Path, uf: str, rows: list[dict]) -> None:
    part_dir = base / f"uf={uf}"
    part_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(part_dir / "part-0.parquet", index=False)


def test_read_enriched_uf_partition_le_so_a_uf_e_prepara_o_frame(tmp_path: Path) -> None:
    """Le APENAS a particao pedida e restaura o contrato de runtime: `uf` volta da
    particao hive, floats viram Float32, a ordenacao do mapa (prioridade > viavel >
    score desc) e aplicada e as colunas de exibicao (UF, nome_municipio fallback
    cidade, score_exibicao) nascem — igualando o frame do enrich em runtime."""
    base = tmp_path / "enriquecido"
    _gravar_particao_enriquecida(
        base,
        "DF",
        [
            _linha_enriquecida(
                _HEX_BSB,
                score_priorizacao=99.0,
                flag_prioridade=False,
                flag_viavel=False,
                rank_brasil=3.0,
            ),
            _linha_enriquecida(_HEX_SP, score_priorizacao=70.0, rank_brasil=1.0),
        ],
    )
    # Segunda UF no MESMO dataset: nao pode vazar para a leitura de DF.
    _gravar_particao_enriquecida(
        base, "SP", [_linha_enriquecida(_HEX_SP, cidade="Sao Paulo", rank_brasil=2.0)]
    )

    frame = read_enriched_uf_partition(base, "DF")

    assert len(frame) == 2  # so a particao DF; a de SP nao vaza
    assert frame["uf"].astype(str).tolist() == ["DF", "DF"]
    # Ordenacao do mapa: o hex priorizado vem antes mesmo com score menor.
    assert frame["hex_id"].tolist() == [_HEX_SP, _HEX_BSB]
    assert str(frame["score_priorizacao"].dtype) == "Float32"
    assert frame["UF"].astype(str).tolist() == ["DF", "DF"]
    # Fallback do _prepare_dataframe: sem nome_municipio no parquet, usa cidade.
    assert frame["nome_municipio"].tolist() == ["Brasilia", "Brasilia"]
    assert frame["score_exibicao"].tolist() == frame["score_priorizacao"].tolist()


def test_read_enriched_uf_partition_base_inexistente_retorna_vazio(tmp_path: Path) -> None:
    """Dataset nao materializado: DataFrame vazio, sem levantar (o piloto degrada)."""
    assert read_enriched_uf_partition(tmp_path / "nao_existe", "DF").empty


def test_read_enriched_uf_partition_uf_sem_particao_retorna_vazio(tmp_path: Path) -> None:
    """UF sem particao no dataset: o filtro hive devolve tabela vazia e a funcao
    retorna ANTES de validar/preparar (validacao de schema nao roda em vazio)."""
    base = tmp_path / "enriquecido"
    _gravar_particao_enriquecida(base, "DF", [_linha_enriquecida(_HEX_BSB)])

    assert read_enriched_uf_partition(base, "MG").empty


# ---------------------------------------------------------------------------
# read_censo_geo_partition — recorte `uf=XX/cod_municipio=N` do artefato geo
# ---------------------------------------------------------------------------


def _gravar_particao_geo(base: Path, uf: str, cod_municipio: str, rows: list[dict]) -> None:
    part_dir = base / f"uf={uf}" / f"cod_municipio={cod_municipio}"
    part_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(part_dir / "part-0.parquet", index=False)


def test_read_censo_geo_partition_municipio_restaura_colunas_de_particao(tmp_path: Path) -> None:
    """Leitura por municipio: o parquet fisico NAO tem `uf`/`cod_municipio` (vivem
    no caminho hive) — a funcao precisa restaura-las no frame para o relatorio
    pontual saber o recorte. UF minuscula e normalizada."""
    base = tmp_path / "setores_geo"
    _gravar_particao_geo(
        base,
        "SP",
        "3550308",
        [
            {"cod_setor": "355030800000001", "score_setor_2022_calibrado": 80.0},
            {"cod_setor": "355030800000002", "score_setor_2022_calibrado": 55.0},
        ],
    )

    frame = read_censo_geo_partition(base, "sp", "3550308")

    assert len(frame) == 2
    assert frame["uf"].unique().tolist() == ["SP"]
    assert frame["cod_municipio"].unique().tolist() == ["3550308"]
    assert frame.index.tolist() == [0, 1]  # reset_index: indice denso p/ iloc a jusante


def test_read_censo_geo_partition_municipio_inexistente_retorna_vazio(tmp_path: Path) -> None:
    """Municipio nao materializado na UF: vazio, sem levantar."""
    base = tmp_path / "setores_geo"
    _gravar_particao_geo(base, "SP", "3550308", [{"cod_setor": "1"}])

    assert read_censo_geo_partition(base, "SP", "9999999").empty


def test_read_censo_geo_partition_uf_inteira_agrega_municipios(tmp_path: Path) -> None:
    """Sem cod_municipio, o recorte e a UF inteira via dataset hive: agrega todos
    os municipios materializados e restaura `uf` do caminho de particao."""
    base = tmp_path / "setores_geo"
    _gravar_particao_geo(base, "SP", "3550308", [{"cod_setor": "1"}, {"cod_setor": "2"}])
    _gravar_particao_geo(base, "SP", "3509502", [{"cod_setor": "3"}])

    frame = read_censo_geo_partition(base, "SP")

    assert len(frame) == 3
    assert frame["uf"].astype(str).unique().tolist() == ["SP"]
    assert sorted(frame["cod_municipio"].astype(str).unique()) == ["3509502", "3550308"]


def test_read_censo_geo_partition_base_ou_uf_inexistente_retorna_vazio(tmp_path: Path) -> None:
    """Artefato inteiro ausente OU UF nao materializada: ambos degradam p/ vazio."""
    assert read_censo_geo_partition(tmp_path / "nao_existe", "SP").empty

    base = tmp_path / "setores_geo"
    _gravar_particao_geo(base, "SP", "3550308", [{"cod_setor": "1"}])
    assert read_censo_geo_partition(base, "MG").empty


# ---------------------------------------------------------------------------
# apply_global_filters — cada eixo de filtro e as combinacoes
# ---------------------------------------------------------------------------


def _frame_filtros() -> pd.DataFrame:
    """3 hexes cobrindo os eixos de filtro; NaN nos flags top_* de proposito
    (a semantica `.eq(True)` precisa EXCLUIR NaN, nao propagar)."""
    return pd.DataFrame(
        {
            "hex_id": ["h1", "h2", "h3"],
            "uf": ["SP", "SP", "DF"],
            "cidade": ["Sao Paulo", "Campinas", "Brasilia"],
            "nome_municipio": ["Sao Paulo", "Campinas", "Brasilia"],
            "faixa_oportunidade": ["alta", "media", "prioridade_maxima"],
            "elegibilidade_hibrida": ["Elegivel", "Nao elegivel", "Sem camada"],
            "cobertura_censitaria_bucket": ["100%", "95-99,9%", "Sem camada"],
            "qualidade_camada": ["A", "B", "Sem camada"],
            "top_municipio": [True, False, np.nan],
            "top_hex_intraurbano": [True, np.nan, False],
        }
    )


def _filtrar(df: pd.DataFrame, **kwargs) -> pd.DataFrame:
    """Atalho: os tres eixos obrigatorios da assinatura default para 'sem filtro'."""
    base = {"selected_ufs": [], "selected_cities": [], "selected_faixas": []}
    base.update(kwargs)
    return apply_global_filters(df, **base)


def test_filtros_sem_selecao_retornam_o_frame_inteiro() -> None:
    """Listas vazias = 'sem filtro' (mascara toda True), inclusive para os eixos
    opcionais que entram como None e viram [] no corpo da funcao."""
    df = _frame_filtros()
    assert _filtrar(df)["hex_id"].tolist() == ["h1", "h2", "h3"]


def test_filtro_por_uf() -> None:
    df = _frame_filtros()
    assert _filtrar(df, selected_ufs=["DF"])["hex_id"].tolist() == ["h3"]


def test_filtro_de_cidade_usa_nome_municipio_quando_existe() -> None:
    """Com `nome_municipio` no frame, e ele (nome oficial IBGE) que filtra — nao a
    coluna legada `cidade`."""
    df = _frame_filtros()
    assert _filtrar(df, selected_cities=["Campinas"])["hex_id"].tolist() == ["h2"]


def test_filtro_de_cidade_cai_para_cidade_sem_nome_municipio() -> None:
    """Frame legado sem `nome_municipio`: o filtro precisa cair para `cidade` em
    vez de levantar KeyError."""
    df = _frame_filtros().drop(columns=["nome_municipio"])
    assert _filtrar(df, selected_cities=["Brasilia"])["hex_id"].tolist() == ["h3"]


def test_filtro_por_faixa_de_oportunidade() -> None:
    df = _frame_filtros()
    filtrado = _filtrar(df, selected_faixas=["alta", "prioridade_maxima"])
    assert filtrado["hex_id"].tolist() == ["h1", "h3"]


def test_filtro_por_elegibilidade_hibrida() -> None:
    df = _frame_filtros()
    filtrado = _filtrar(df, selected_hybrid_eligibility=["Elegivel"])
    assert filtrado["hex_id"].tolist() == ["h1"]


def test_filtro_de_elegibilidade_e_ignorado_sem_a_coluna() -> None:
    """Frame M1 puro (sem camada hibrida): o filtro selecionado NAO pode zerar o
    resultado nem levantar — e simplesmente ignorado."""
    df = _frame_filtros().drop(columns=["elegibilidade_hibrida"])
    filtrado = _filtrar(df, selected_hybrid_eligibility=["Elegivel"])
    assert filtrado["hex_id"].tolist() == ["h1", "h2", "h3"]


def test_filtro_por_bucket_de_cobertura() -> None:
    df = _frame_filtros()
    filtrado = _filtrar(df, selected_coverage_buckets=["95-99,9%"])
    assert filtrado["hex_id"].tolist() == ["h2"]


def test_filtro_por_qualidade_do_join() -> None:
    df = _frame_filtros()
    filtrado = _filtrar(df, selected_join_quality=["A", "B"])
    assert filtrado["hex_id"].tolist() == ["h1", "h2"]


def test_only_top_municipio_exclui_false_e_nan() -> None:
    """`.eq(True)` (e nao `== True` puro) mantem a semantica pandas: NaN conta
    como fora do top, nunca propaga para a mascara."""
    df = _frame_filtros()
    assert _filtrar(df, only_top_municipio=True)["hex_id"].tolist() == ["h1"]


def test_only_top_hex_intraurbano_exclui_false_e_nan() -> None:
    df = _frame_filtros()
    assert _filtrar(df, only_top_hex_intraurbano=True)["hex_id"].tolist() == ["h1"]


def test_only_top_ignorado_sem_as_colunas() -> None:
    """Toggles de top ligados num frame sem as colunas: no-op, sem KeyError."""
    df = _frame_filtros().drop(columns=["top_municipio", "top_hex_intraurbano"])
    filtrado = _filtrar(df, only_top_municipio=True, only_top_hex_intraurbano=True)
    assert filtrado["hex_id"].tolist() == ["h1", "h2", "h3"]


def test_combinacao_de_filtros_aplica_intersecao() -> None:
    """Os eixos compoem por E logico (intersecao), como na sidebar real."""
    df = _frame_filtros()
    filtrado = _filtrar(
        df,
        selected_ufs=["SP"],
        selected_faixas=["alta", "media"],
        selected_join_quality=["A"],
        only_top_municipio=True,
    )
    assert filtrado["hex_id"].tolist() == ["h1"]


# ---------------------------------------------------------------------------
# Delegates finos para pipelines/pop_corte.py (fonte unica da regua)
# ---------------------------------------------------------------------------


def test_normalized_join_quality_delegacao_normaliza_nulo_e_caixa() -> None:
    """O wrapper do dashboard delega ao helper compartilhado: nulo vira "" e a
    caixa e normalizada p/ maiuscula (contrato usado pela regua granular A/B)."""
    df = pd.DataFrame({"qualidade_join_uf": ["a", None, "B"]})
    assert _normalized_join_quality(df).tolist() == ["A", "", "B"]
    # Sem a coluna: serie vazia de "", nunca KeyError.
    assert _normalized_join_quality(pd.DataFrame(index=[0, 1])).tolist() == ["", ""]


def test_has_censo_signal_delegacao_combina_flag_e_score() -> None:
    """Sinal de censo = flag disponivel OU score calibrado presente (OR logico);
    nulo em ambos = sem sinal."""
    df = pd.DataFrame(
        {
            "flag_censo_disponivel": [True, False, None],
            "score_setor_2022_calibrado": [None, 5.0, None],
        }
    )
    assert _has_censo_signal(df).tolist() == [True, True, False]
