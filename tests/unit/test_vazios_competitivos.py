"""Testes do modulo de vazios competitivos do concorrente low-cost (BLK-TP-03).

Usa SEMPRE fixture SINTETICA construida em codigo (NUNCA o parquet/HTML real).
Cobre: casos-limite do filtro, reproducibilidade/determinismo, contrato de colunas/dtypes,
zero PII, join de enriquecimento, colunas ausentes, e isolamento de importacao.

READ-ONLY sobre o M1 (DEC-001/DEC-009/DEC-012 / CLAUDE.md §5).
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from motor_expansao.demanda_revelada.contrato import COLUNAS_PII_PROIBIDAS
from motor_expansao.demanda_revelada.vazios_competitivos import (
    CONTRATO_COLUNAS_VAZIOS,
    LIMIAR_MEMBROS_GT5KM,
    VERSAO_CONTRATO_VAZIOS,
    _assert_sem_pii_vazios,
    _coagir_ao_contrato,
    enriquecer_vazios,
    flag_vazio_competitivo,
    gerar_vazios_competitivos,
)

# ---------------------------------------------------------------------------
# Helpers de fixture sintetica
# ---------------------------------------------------------------------------

def _row(
    *,
    hex_id: str = "87a800000ffffff",
    membros: int = 500,
    membros_gt5km: int = 300,
    dist: float | None = 10_000.0,
    n_conc: int = 0,
    n_celulas: int = 3,
    n_acad: int = 2,
    alunos: int = 100,
    versao: str = "demanda_revelada_v1",
) -> dict:
    """Cria uma linha do contrato demanda_revelada_v1 como dict."""
    return {
        "hex_id": hex_id,
        "membros": membros,
        "membros_gt5km_concorrente_lc": membros_gt5km,
        "dist_concorrente_lc_min_m": dist,
        "n_celulas_agregadas": n_celulas,
        "n_acad_parceiras": n_acad,
        "alunos_parceiras": alunos,
        "n_concorrente_lc": n_conc,
        "versao_contrato": versao,
    }


def _df_from_rows(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def _df_enriquecimento(n: int = 3) -> pd.DataFrame:
    """Frame sintetico de enriquecimento (subset de hexagonos_mercado_mapeado.parquet)."""
    return pd.DataFrame({
        "hex_id": [f"87a{i:012x}" for i in range(n)],
        "uf": [f"UF{i}" for i in range(n)],
        "nome_municipio": [f"Municipio{i}" for i in range(n)],
        "score_priorizacao": [float(i * 10) for i in range(n)],
        "oferta_efetiva_disponivel": [float(i * 500) for i in range(n)],
    })


# ---------------------------------------------------------------------------
# test_flag_casos_limite
# ---------------------------------------------------------------------------

class TestFlagCasosLimite:
    """Casos-limite da funcao flag_vazio_competitivo."""

    def test_n_concorrente_lc_maior_zero_eh_false(self) -> None:
        """Se n_concorrente_lc > 0, nunca e vazio (concorrente presente no hex)."""
        df = _df_from_rows([_row(n_conc=1, dist=10_000.0, membros_gt5km=300)])
        resultado = flag_vazio_competitivo(df)
        assert resultado.iloc[0] is np.bool_(False)

    def test_n_concorrente_lc_zero_dist_exatamente_5000_eh_false(self) -> None:
        """dist == 5000.0 exatamente: condicao e ESTRITA (> 5000), entao False."""
        df = _df_from_rows([_row(n_conc=0, dist=5_000.0, membros_gt5km=300)])
        resultado = flag_vazio_competitivo(df)
        assert resultado.iloc[0] is np.bool_(False)

    def test_n_concorrente_lc_zero_dist_5000_ponto_01_pode_ser_true(self) -> None:
        """dist == 5000.01: ultrapassa o limiar estrito -> True se membros ok."""
        df = _df_from_rows([_row(n_conc=0, dist=5_000.01, membros_gt5km=LIMIAR_MEMBROS_GT5KM)])
        resultado = flag_vazio_competitivo(df)
        assert resultado.iloc[0] is np.bool_(True)

    def test_dist_nan_tratado_como_muito_longe_true(self) -> None:
        """dist NaN = 'muito longe' (Decisao 1 Planner) -> incluido se demais condicoes ok."""
        df = _df_from_rows([_row(n_conc=0, dist=None, membros_gt5km=LIMIAR_MEMBROS_GT5KM)])
        resultado = flag_vazio_competitivo(df)
        assert resultado.iloc[0] is np.bool_(True)

    def test_membros_gt5km_abaixo_do_limiar_eh_false(self) -> None:
        """membros_gt5km == LIMIAR - 1 -> False (nao atinge limiar inclusivo)."""
        df = _df_from_rows([_row(n_conc=0, dist=10_000.0, membros_gt5km=LIMIAR_MEMBROS_GT5KM - 1)])
        resultado = flag_vazio_competitivo(df)
        assert resultado.iloc[0] is np.bool_(False)

    def test_membros_gt5km_igual_ao_limiar_eh_true(self) -> None:
        """membros_gt5km == LIMIAR -> True (fronteira inclusiva >=)."""
        df = _df_from_rows([_row(n_conc=0, dist=10_000.0, membros_gt5km=LIMIAR_MEMBROS_GT5KM)])
        resultado = flag_vazio_competitivo(df)
        assert resultado.iloc[0] is np.bool_(True)

    def test_membros_gt5km_zero_eh_false(self) -> None:
        """membros_gt5km == 0 -> False (sem demanda a >5km)."""
        df = _df_from_rows([_row(n_conc=0, dist=10_000.0, membros_gt5km=0)])
        resultado = flag_vazio_competitivo(df)
        assert resultado.iloc[0] is np.bool_(False)

    def test_todas_condicoes_satisfeitas_eh_true(self) -> None:
        """Caso canonico: n_conc=0, dist>5km, membros_gt5km>=limiar -> True."""
        df = _df_from_rows([_row(n_conc=0, dist=15_000.0, membros_gt5km=250)])
        resultado = flag_vazio_competitivo(df)
        assert resultado.iloc[0] is np.bool_(True)

    def test_limiar_parametrizavel(self) -> None:
        """Limiar customizado funciona corretamente."""
        df = _df_from_rows([
            _row(hex_id="87a000000000000", n_conc=0, dist=10_000.0, membros_gt5km=50),
            _row(hex_id="87a000000000001", n_conc=0, dist=10_000.0, membros_gt5km=100),
        ])
        # Com limiar=50: ambos True
        resultado50 = flag_vazio_competitivo(df, limiar_membros_gt5km=50)
        assert resultado50.iloc[0] is np.bool_(True)
        assert resultado50.iloc[1] is np.bool_(True)
        # Com limiar=100: apenas o segundo True
        resultado100 = flag_vazio_competitivo(df, limiar_membros_gt5km=100)
        assert resultado100.iloc[0] is np.bool_(False)
        assert resultado100.iloc[1] is np.bool_(True)


# ---------------------------------------------------------------------------
# test_reproducibilidade_determinismo
# ---------------------------------------------------------------------------

def test_reproducibilidade_determinismo() -> None:
    """Mesmo input -> mesmo output byte-a-byte (ordenacao por hex_id)."""
    rows = [
        _row(hex_id=f"87a{i:012x}", n_conc=0, dist=float(6000 + i * 100), membros_gt5km=200 + i)
        for i in range(5)
    ]
    df = _df_from_rows(rows)
    enrich = _df_enriquecimento(5)

    # Primeira execucao
    mask1 = flag_vazio_competitivo(df)
    df_vazios1 = df[mask1].copy()
    df_vazios1["flag_vazio_competitivo"] = True
    df_enr1 = enriquecer_vazios(df_vazios1, enrich)
    df_enr1["versao_contrato"] = VERSAO_CONTRATO_VAZIOS
    df_final1 = _coagir_ao_contrato(df_enr1).sort_values("hex_id").reset_index(drop=True)

    # Segunda execucao (mesmo input)
    mask2 = flag_vazio_competitivo(df)
    df_vazios2 = df[mask2].copy()
    df_vazios2["flag_vazio_competitivo"] = True
    df_enr2 = enriquecer_vazios(df_vazios2, enrich)
    df_enr2["versao_contrato"] = VERSAO_CONTRATO_VAZIOS
    df_final2 = _coagir_ao_contrato(df_enr2).sort_values("hex_id").reset_index(drop=True)

    assert df_final1.equals(df_final2), "Saida nao e deterministica!"


# ---------------------------------------------------------------------------
# test_contrato_colunas_e_dtypes
# ---------------------------------------------------------------------------

def test_contrato_colunas_e_dtypes() -> None:
    """Saida tem EXATAMENTE as colunas de CONTRATO_COLUNAS_VAZIOS na ordem correta."""
    rows = [_row(n_conc=0, dist=10_000.0, membros_gt5km=250)]
    df = _df_from_rows(rows)
    df["flag_vazio_competitivo"] = True
    df["versao_contrato"] = VERSAO_CONTRATO_VAZIOS
    enrich = _df_enriquecimento(1)
    enrich["hex_id"] = "87a800000ffffff"

    df_enr = enriquecer_vazios(df, enrich)
    df_enr["versao_contrato"] = VERSAO_CONTRATO_VAZIOS
    df_final = _coagir_ao_contrato(df_enr).sort_values("hex_id").reset_index(drop=True)

    # Colunas exatas e na ordem
    assert list(df_final.columns) == list(CONTRATO_COLUNAS_VAZIOS.keys()), (
        f"Colunas divergem. Esperado: {list(CONTRATO_COLUNAS_VAZIOS.keys())}\n"
        f"Obtido:   {list(df_final.columns)}"
    )

    # versao_contrato correta em todas as linhas
    assert (df_final["versao_contrato"] == VERSAO_CONTRATO_VAZIOS).all()

    # Dtypes basicos (bool, string, numerico)
    assert df_final["flag_vazio_competitivo"].dtype == bool or str(df_final["flag_vazio_competitivo"].dtype) in ("bool", "boolean")
    assert str(df_final["hex_id"].dtype) == "string"
    assert str(df_final["versao_contrato"].dtype) == "string"


# ---------------------------------------------------------------------------
# test_zero_pii
# ---------------------------------------------------------------------------

def test_zero_pii() -> None:
    """set(out.columns) & COLUNAS_PII_PROIBIDAS == set() (rede anti-PII por NOME).

    Garante que hex_lat/hex_lng NAO colidem com lat/lng/latitude/longitude.
    """
    rows = [_row(n_conc=0, dist=10_000.0, membros_gt5km=300)]
    df = _df_from_rows(rows)
    df["flag_vazio_competitivo"] = True
    df["versao_contrato"] = VERSAO_CONTRATO_VAZIOS
    enrich = _df_enriquecimento(1)
    enrich["hex_id"] = "87a800000ffffff"

    df_enr = enriquecer_vazios(df, enrich)
    df_enr["versao_contrato"] = VERSAO_CONTRATO_VAZIOS
    df_final = _coagir_ao_contrato(df_enr)

    colisao = set(df_final.columns) & COLUNAS_PII_PROIBIDAS
    assert colisao == set(), f"PII detectada nas colunas do artefato: {sorted(colisao)}"

    # Garante que hex_lat/hex_lng existem mas lat/lng nao
    assert "hex_lat" in df_final.columns
    assert "hex_lng" in df_final.columns
    assert "lat" not in df_final.columns
    assert "lng" not in df_final.columns

    # Roda o guard automatizado
    _assert_sem_pii_vazios(df_final)


def test_assert_pii_levanta_se_coluna_proibida() -> None:
    """_assert_sem_pii_vazios levanta AssertionError se 'lat' estiver presente."""
    df_ruim = pd.DataFrame({"lat": [1.0], "hex_id": ["87a800000ffffff"]})
    with pytest.raises(AssertionError, match="PII"):
        _assert_sem_pii_vazios(df_ruim)


# ---------------------------------------------------------------------------
# test_enriquecimento_join_readonly
# ---------------------------------------------------------------------------

def test_enriquecimento_join_readonly() -> None:
    """Join traz uf/nome_municipio/score_priorizacao/oferta_efetiva_disponivel; hex sem match -> NA."""
    rows = [
        _row(hex_id="87a000000000000", n_conc=0, dist=10_000.0, membros_gt5km=300),
        _row(hex_id="87a000000000001", n_conc=0, dist=10_000.0, membros_gt5km=300),
        _row(hex_id="87a999999999999", n_conc=0, dist=10_000.0, membros_gt5km=300),  # sem match
    ]
    df = _df_from_rows(rows)
    df["flag_vazio_competitivo"] = True

    enrich = pd.DataFrame({
        "hex_id": ["87a000000000000", "87a000000000001"],
        "uf": ["SP", "RJ"],
        "nome_municipio": ["Cidade A", "Cidade B"],
        "score_priorizacao": [75.0, 60.0],
        "oferta_efetiva_disponivel": [3000.0, 2000.0],
    })

    resultado = enriquecer_vazios(df, enrich)

    # Hexes com match recebem os valores
    row_sp = resultado[resultado["hex_id"] == "87a000000000000"].iloc[0]
    assert row_sp["uf"] == "SP"
    assert row_sp["nome_municipio"] == "Cidade A"
    assert float(row_sp["score_priorizacao"]) == pytest.approx(75.0)
    assert float(row_sp["oferta_efetiva_disponivel"]) == pytest.approx(3000.0)

    # Hex sem match recebe NA (sem quebrar)
    row_sem_match = resultado[resultado["hex_id"] == "87a999999999999"].iloc[0]
    assert pd.isna(row_sem_match["uf"]) or row_sem_match["uf"] is pd.NA

    # score_priorizacao nao foi recalculado (READ-ONLY: apenas copiado)
    assert float(resultado[resultado["hex_id"] == "87a000000000001"].iloc[0]["score_priorizacao"]) == pytest.approx(60.0)

    # Nenhuma coluna PII presente
    assert set(resultado.columns) & COLUNAS_PII_PROIBIDAS == set()


# ---------------------------------------------------------------------------
# test_enriquecimento_colunas_ausentes
# ---------------------------------------------------------------------------

def test_enriquecimento_colunas_ausentes() -> None:
    """Enriquecimento sem score_priorizacao/oferta_efetiva_disponivel: nao levanta, preenche NA."""
    rows = [_row(hex_id="87a800000ffffff", n_conc=0, dist=10_000.0, membros_gt5km=300)]
    df = _df_from_rows(rows)
    df["flag_vazio_competitivo"] = True

    # Enriquecimento sem as colunas opcionais
    enrich_parcial = pd.DataFrame({
        "hex_id": ["87a800000ffffff"],
        "uf": ["SP"],
        "nome_municipio": ["Cidade X"],
        # score_priorizacao e oferta_efetiva_disponivel AUSENTES
    })

    resultado = enriquecer_vazios(df, enrich_parcial)

    assert "uf" in resultado.columns
    assert resultado["uf"].iloc[0] == "SP"
    # Colunas ausentes devem existir mas ser NA
    assert "score_priorizacao" in resultado.columns
    assert "oferta_efetiva_disponivel" in resultado.columns
    assert pd.isna(resultado["score_priorizacao"].iloc[0])
    assert pd.isna(resultado["oferta_efetiva_disponivel"].iloc[0])


def test_enriquecimento_frame_vazio() -> None:
    """Enriquecimento com DataFrame vazio: nao levanta; colunas de enriquecimento sao NA."""
    rows = [_row(n_conc=0, dist=10_000.0, membros_gt5km=300)]
    df = _df_from_rows(rows)
    df["flag_vazio_competitivo"] = True

    enrich_vazio = pd.DataFrame(columns=["hex_id"])
    resultado = enriquecer_vazios(df, enrich_vazio)

    for col in ["uf", "nome_municipio", "score_priorizacao", "oferta_efetiva_disponivel"]:
        assert col in resultado.columns


# ---------------------------------------------------------------------------
# test_isolamento_import
# ---------------------------------------------------------------------------

def test_isolamento_import() -> None:
    """Verifica estaticamente que vazios_competitivos.py NAO importa de pipelines.m1,
    censo nem dashboard (DEC-012: pacote disjunto).

    Inspecciona o texto-fonte via regex de importacao (espelha criterio de aceite 5).
    """
    modulo_path = (
        Path(__file__).resolve().parent.parent.parent
        / "src" / "motor_expansao" / "demanda_revelada" / "vazios_competitivos.py"
    )
    assert modulo_path.exists(), f"Arquivo nao encontrado: {modulo_path}"

    texto = modulo_path.read_text(encoding="utf-8")

    # Padroes proibidos de importacao
    proibidos = [
        r"from\s+motor_expansao\.pipelines\.m1",
        r"import\s+motor_expansao\.pipelines\.m1",
        r"from\s+motor_expansao\.censo",
        r"import\s+motor_expansao\.censo",
        r"from\s+motor_expansao\.dashboard",
        r"import\s+motor_expansao\.dashboard",
        r"from\s+config\b",   # config.py raiz
        r"import\s+config\b",
    ]

    violacoes: list[str] = []
    for padrao in proibidos:
        if re.search(padrao, texto):
            violacoes.append(padrao)

    assert not violacoes, (
        f"vazios_competitivos.py importa de modulos proibidos (DEC-012): {violacoes}"
    )


# ---------------------------------------------------------------------------
# test_gerar_vazios_competitivos_sem_escrever (integracao sintetica)
# ---------------------------------------------------------------------------

def test_gerar_vazios_escrever_false(tmp_path: Path) -> None:
    """gerar_vazios_competitivos com fontes sinteticas e escrever=False nao grava arquivo."""
    # Criar parquets sinteticos temporarios
    demanda = pd.DataFrame([
        _row(hex_id="87a000000000000", n_conc=0, dist=10_000.0, membros_gt5km=300),
        _row(hex_id="87a000000000001", n_conc=1, dist=10_000.0, membros_gt5km=300),  # excluido
        _row(hex_id="87a000000000002", n_conc=0, dist=4_000.0, membros_gt5km=300),   # excluido (dist<5km)
        _row(hex_id="87a000000000003", n_conc=0, dist=10_000.0, membros_gt5km=50),   # excluido (membros<200)
    ])
    demanda_path = tmp_path / "demanda.parquet"
    demanda.to_parquet(demanda_path)

    enrich = pd.DataFrame({
        "hex_id": ["87a000000000000"],
        "uf": ["SP"],
        "nome_municipio": ["Sao Paulo"],
        "score_priorizacao": [88.0],
        "oferta_efetiva_disponivel": [5000.0],
    })
    enrich_path = tmp_path / "enrich.parquet"
    enrich.to_parquet(enrich_path)

    destino_path = tmp_path / "vazios.parquet"

    resultado = gerar_vazios_competitivos(
        fonte=demanda_path,
        enriquecimento=enrich_path,
        destino=destino_path,
        escrever=False,
    )

    # Apenas 1 hex deve passar os 3 filtros
    assert len(resultado) == 1
    assert resultado.iloc[0]["hex_id"] == "87a000000000000"
    assert resultado.iloc[0]["versao_contrato"] == VERSAO_CONTRATO_VAZIOS

    # Com escrever=False, o arquivo NAO deve existir
    assert not destino_path.exists()

    # Anti-PII
    assert set(resultado.columns) & COLUNAS_PII_PROIBIDAS == set()


def test_gerar_vazios_escrever_true(tmp_path: Path) -> None:
    """gerar_vazios_competitivos com escrever=True grava o parquet corretamente."""
    demanda = pd.DataFrame([
        _row(hex_id="87a000000000000", n_conc=0, dist=10_000.0, membros_gt5km=300),
    ])
    demanda_path = tmp_path / "demanda.parquet"
    demanda.to_parquet(demanda_path)

    enrich = pd.DataFrame({"hex_id": pd.Series([], dtype=str)})
    enrich_path = tmp_path / "enrich.parquet"
    enrich.to_parquet(enrich_path)

    destino_path = tmp_path / "vazios.parquet"

    resultado = gerar_vazios_competitivos(
        fonte=demanda_path,
        enriquecimento=enrich_path,
        destino=destino_path,
        escrever=True,
    )

    assert destino_path.exists()
    df_lido = pd.read_parquet(destino_path)
    assert len(df_lido) == len(resultado)
    assert list(df_lido.columns) == list(CONTRATO_COLUNAS_VAZIOS.keys())
