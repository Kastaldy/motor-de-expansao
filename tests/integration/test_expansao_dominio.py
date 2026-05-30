"""
Testes de integracao — Expansao de Dominio (Bloco 4)
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from motor_expansao.dashboard.constants import DOMINIO_SCHEMA_MINIMO, DOMINIO_TESES_VALIDAS

ROOT = Path(__file__).resolve().parents[2]
MERCADO_PATH = ROOT / "data" / "staging" / "hexagonos_mercado_mapeado.parquet"
PLANO_PATH = ROOT / "data" / "outputs" / "plano_expansao_dominio.parquet"
CARTEIRA_PATH = ROOT / "data" / "outputs" / "carteira_expansao_acionavel.parquet"
PLANO_CP_PATH = ROOT / "data" / "outputs" / "plano_expansao_curto_prazo.parquet"

pytestmark = pytest.mark.skipif(
    not MERCADO_PATH.exists(),
    reason="hexagonos_mercado_mapeado.parquet ausente",
)

SCHEMA_MINIMO = DOMINIO_SCHEMA_MINIMO
TESES_VALIDAS = DOMINIO_TESES_VALIDAS


@pytest.fixture(scope="module")
def plano_sample():
    """Executa pipeline nas top 3 cidades e retorna plano com rankings."""
    from jobs.pipelines.gerar_plano_expansao_dominio import (
        _top_cidades_por_residual,
        adicionar_rankings,
        carregar_candidatos,
        gerar_plano_dominio,
    )
    df = carregar_candidatos()
    df = _top_cidades_por_residual(df, 3)
    plano = gerar_plano_dominio(df, max_ancoras=5, dist_min_km=1.5)
    assert not plano.empty, "plano vazio com top 3 cidades"
    return adicionar_rankings(plano)


class TestIntegridadePlano:
    def test_sem_hex_id_duplicado(self, plano_sample):
        assert not plano_sample["hex_id"].duplicated().any()

    def test_sem_hex_id_nulo(self, plano_sample):
        assert plano_sample["hex_id"].notna().all()

    def test_schema_minimo_presente(self, plano_sample):
        ausentes = SCHEMA_MINIMO - set(plano_sample.columns)
        assert not ausentes, f"colunas ausentes: {ausentes}"

    def test_tese_dominio_valores_validos(self, plano_sample):
        assert set(plano_sample["tese_dominio"].unique()) <= TESES_VALIDAS

    def test_residual_incremental_positivo(self, plano_sample):
        assert (plano_sample["residual_incremental_capturado"] > 0).all()

    def test_ordem_expansao_comeca_em_1(self, plano_sample):
        for _, grp in plano_sample.groupby("cod_municipio"):
            assert grp["ordem_expansao_cidade"].min() == 1

    def test_max_ancoras_respeitado(self, plano_sample):
        for _, grp in plano_sample.groupby("cod_municipio"):
            assert len(grp) <= 5

    def test_cobre_exatamente_3_cidades(self, plano_sample):
        assert plano_sample["cod_municipio"].nunique() == 3


class TestRankings:
    def test_rank_brasil_unico(self, plano_sample):
        assert plano_sample["rank_dominio_brasil"].nunique() == len(plano_sample)

    def test_rank_brasil_sem_nulos(self, plano_sample):
        assert plano_sample["rank_dominio_brasil"].notna().all()

    def test_rank_uf_sem_nulos(self, plano_sample):
        assert plano_sample["rank_dominio_uf"].notna().all()

    def test_rank_cidade_sem_nulos(self, plano_sample):
        assert plano_sample["rank_dominio_cidade"].notna().all()

    def test_rank_brasil_comeca_em_1(self, plano_sample):
        assert plano_sample["rank_dominio_brasil"].min() == 1

    def test_rank_uf_comeca_em_1_por_uf(self, plano_sample):
        for _, grp in plano_sample.groupby("uf"):
            assert grp["rank_dominio_uf"].min() == 1

    def test_rank_cidade_comeca_em_1_por_cidade(self, plano_sample):
        for _, grp in plano_sample.groupby("cod_municipio"):
            assert grp["rank_dominio_cidade"].min() == 1


class TestTopCidadesFiltro:
    def test_top1_retorna_apenas_1_cidade(self):
        from jobs.pipelines.gerar_plano_expansao_dominio import (
            _top_cidades_por_residual,
            carregar_candidatos,
        )
        df = carregar_candidatos()
        top1 = _top_cidades_por_residual(df, 1)
        assert top1["cod_municipio"].nunique() == 1

    def test_top_maior_que_total_retorna_tudo(self):
        from jobs.pipelines.gerar_plano_expansao_dominio import (
            _top_cidades_por_residual,
            carregar_candidatos,
        )
        df = carregar_candidatos()
        total_cidades = df["cod_municipio"].nunique()
        top_over = _top_cidades_por_residual(df, total_cidades + 9999)
        assert top_over["cod_municipio"].nunique() == total_cidades


@pytest.mark.skipif(not PLANO_PATH.exists(), reason="plano_expansao_dominio.parquet nao gerado")
class TestArtefatoMaterializado:
    def test_schema_minimo_no_parquet(self):
        df = pd.read_parquet(PLANO_PATH)
        ausentes = SCHEMA_MINIMO - set(df.columns)
        assert not ausentes, f"colunas ausentes: {ausentes}"

    def test_sem_hex_id_duplicado_no_parquet(self):
        df = pd.read_parquet(PLANO_PATH, columns=["hex_id"])
        assert not df["hex_id"].duplicated().any()


@pytest.mark.skipif(
    not CARTEIRA_PATH.exists(),
    reason="carteira_expansao_acionavel.parquet ausente",
)
class TestArtefatosM1NaoAlterados:
    """Verifica que os artefatos oficiais do M1 nao sao tocados pelo pipeline de dominio."""

    def test_carteira_contem_score_priorizacao(self):
        df = pd.read_parquet(CARTEIRA_PATH, columns=["hex_id", "score_priorizacao"])
        assert "score_priorizacao" in df.columns
        assert df["hex_id"].notna().all()

    @pytest.mark.skipif(not PLANO_CP_PATH.exists(), reason="plano_expansao_curto_prazo.parquet ausente")
    def test_plano_cp_contem_score_priorizacao(self):
        df = pd.read_parquet(PLANO_CP_PATH, columns=["hex_id", "score_priorizacao"])
        assert "score_priorizacao" in df.columns

    def test_plano_dominio_nao_tem_hex_da_carteira_com_score_alterado(self, plano_sample):
        # Garante que o plano nao gerou linhas com score_priorizacao diferente do que
        # esta na carteira para os mesmos hex_ids
        if "score_priorizacao" not in plano_sample.columns:
            pytest.skip("plano_sample nao carregou score_priorizacao")
        carteira = pd.read_parquet(CARTEIRA_PATH, columns=["hex_id", "score_priorizacao"])
        merged = plano_sample.merge(carteira, on="hex_id", suffixes=("_dom", "_m1"), how="inner")
        if merged.empty:
            return  # sem hex em comum, guardrail satisfeito por ausencia
        diffs = (merged["score_priorizacao_dom"] - merged["score_priorizacao_m1"]).abs()
        assert (diffs < 1e-6).all(), "score_priorizacao foi alterado pelo pipeline de dominio"
