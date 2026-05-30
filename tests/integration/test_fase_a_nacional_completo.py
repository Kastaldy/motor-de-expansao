from __future__ import annotations

import pandas as pd
import pytest

from jobs.pipelines.fase_a_nacional_completo import (
    _UFS_JA_COBERTAS,
    TARGET_UFS,
    calcular_qualidade_join_uf,
    carregar_k_global,
)
from jobs.pipelines.fase_a_piloto_expandido import (
    parse_k_global,
    resumir_metricas_uf,
)
from jobs.pipelines.validar_fase_a_censo2022 import UFS_BRASIL


def test_target_ufs_tem_21_ufs():
    assert len(TARGET_UFS) == 21


def test_target_ufs_nao_contem_ufs_ja_cobertas():
    assert not _UFS_JA_COBERTAS.intersection(TARGET_UFS)


def test_target_ufs_cobre_apenas_ufs_validas():
    invalidas = set(TARGET_UFS) - set(UFS_BRASIL)
    assert not invalidas, f"UFs invalidas em TARGET_UFS: {invalidas}"


def test_target_ufs_mais_ja_cobertas_cobre_brasil_completo():
    todas = set(TARGET_UFS) | _UFS_JA_COBERTAS
    assert todas == set(UFS_BRASIL)


def test_calcular_qualidade_join_uf_go_preserva_classe():
    summary = {"status_tecnico": "GO", "classe_join": "A"}
    assert calcular_qualidade_join_uf(summary) == "A"

    summary_b = {"status_tecnico": "GO", "classe_join": "B"}
    assert calcular_qualidade_join_uf(summary_b) == "B"


def test_calcular_qualidade_join_uf_nogo_retorna_c():
    summary = {"status_tecnico": "NO-GO", "classe_join": "A"}
    assert calcular_qualidade_join_uf(summary) == "C"

    summary_b = {"status_tecnico": "NO-GO", "classe_join": "B"}
    assert calcular_qualidade_join_uf(summary_b) == "C"


def test_resumir_metricas_uf_gate_nao_bloqueante():
    """UF com amplitude baixa resulta em status NO-GO mas nao lanca excecao."""
    df = pd.DataFrame(
        {
            "score_setor_2022_calibrado": [40.0, 42.0, 43.0, 44.0, 45.0],
            "score_priorizacao": [50.0, 51.0, 52.0, 53.0, 54.0],
        }
    )
    outlier_result = {"critical_outliers": 0, "threshold": 5.0, "avaliados": 5}
    result = resumir_metricas_uf(df, uf="AM", mismatch_pct=1.0, outlier_result=outlier_result)
    assert result["status_tecnico"] == "NO-GO"
    assert result["gate_amplitude"] is False
    qualidade = calcular_qualidade_join_uf(result)
    assert qualidade == "C"


def test_parse_k_global_consistente_com_formato_do_metodo():
    metodo = "multiplicativo_global_k=1.0213"
    k = parse_k_global(metodo)
    assert k == pytest.approx(1.0213)
    reconstruido = f"multiplicativo_global_k={k:.4f}"
    assert parse_k_global(reconstruido) == pytest.approx(k, rel=1e-4)


def test_carregar_k_global_falha_sem_parquet(tmp_path):
    caminho_inexistente = tmp_path / "nao_existe.parquet"
    with pytest.raises(FileNotFoundError):
        carregar_k_global(caminho_inexistente)
