"""BLK-TP-04: testes offline (seed-fixo, sem I/O de rede) da validacao da curva.

Fixtures SINTETICAS (nunca a fonte real NAO_ABRA/): base com m2 real (marca +
metragem + alunos_reais) e uma tabela de demanda (parceiras) para o sanity-check.
Cobre: anti-PII, LOO honesto sem R2 in-sample, intervalos presentes/ordenados,
`alunos_parceiras` NUNCA preditor, isolamento de import, IC bootstrap
determinista, criterio GO/NO-GO e materializacao do relatorio.
"""

from __future__ import annotations

import inspect

import numpy as np
import pandas as pd
import pytest

from motor_expansao.demanda_revelada import calibracao_curva as m
from motor_expansao.demanda_revelada.calibracao_curva import (
    CurvaValidacaoResult,
    _relatorio_markdown,
    escrever_relatorio,
    flag_extrapolacao_m2,
    sanity_check_parceiras,
    validar_curva_densidade,
)


# --------------------------------------------------------------------------- #
# Fixtures sinteticas
# --------------------------------------------------------------------------- #
@pytest.fixture
def base_curva_ruido() -> pd.DataFrame:
    """Base com m2 real (2 marcas) onde alunos_por_m2 NAO depende de metragem (ruido).

    Densidade sorteada independente do tamanho -> a curva log(metragem) nao deve
    generalizar out-of-fold (esperado NO-GO / IC cruzando zero).
    """
    rng = np.random.default_rng(42)
    n = 60
    metragem = rng.uniform(800.0, 2600.0, n)
    apm = rng.uniform(1.0, 3.0, n)  # densidade independente da metragem
    marca = np.where(np.arange(n) % 2 == 0, "engenharia_do_corpo", "ultra")
    return pd.DataFrame(
        {
            "marca": marca,
            "metragem": metragem,
            "alunos_reais": apm * metragem,
            "alunos_por_m2": apm,
            "flag_qualidade_match": ["direto"] * n,
            "coorte": ["multirede"] * n,
        }
    )


@pytest.fixture
def base_curva_forte() -> pd.DataFrame:
    """Base com m2 onde alunos_por_m2 CAI linearmente com log(metragem) + ruido pequeno.

    Sinal forte e estavel -> a curva deve generalizar out-of-fold (esperado GO).
    """
    rng = np.random.default_rng(7)
    n = 80
    metragem = np.geomspace(800.0, 3000.0, n)
    apm = 6.0 - 0.55 * np.log(metragem) + rng.normal(0.0, 0.02, n)
    apm = np.clip(apm, 0.2, None)
    marca = np.where(np.arange(n) % 2 == 0, "engenharia_do_corpo", "ultra")
    return pd.DataFrame(
        {
            "marca": marca,
            "metragem": metragem,
            "alunos_reais": apm * metragem,
            "alunos_por_m2": apm,
            "flag_qualidade_match": ["fuzzy"] * n,
            "coorte": ["multirede"] * n,
        }
    )


@pytest.fixture
def demanda_parceiras() -> pd.DataFrame:
    """Camada de Demanda Revelada sintetica (so colunas agregadas do contrato)."""
    rng = np.random.default_rng(3)
    n = 400
    n_acad = rng.integers(1, 30, n)
    alunos = (n_acad * rng.uniform(2.0, 40.0, n)).round().astype(int)
    return pd.DataFrame(
        {
            "hex_id": [f"87a{i:012x}ffff" for i in range(n)],
            "membros": rng.integers(0, 5000, n),
            "n_acad_parceiras": n_acad,
            "alunos_parceiras": alunos,
            "n_concorrente_lc": rng.integers(0, 5, n),
            "versao_contrato": ["demanda_revelada_v1"] * n,
        }
    )


# --------------------------------------------------------------------------- #
# Testes
# --------------------------------------------------------------------------- #
def test_anti_pii(base_curva_forte, demanda_parceiras):
    """Nenhuma coluna de COLUNAS_PII_PROIBIDAS como TOKEN isolado no relatorio/result."""
    import re

    from motor_expansao.demanda_revelada.contrato import COLUNAS_PII_PROIBIDAS

    res = validar_curva_densidade(base_curva_forte)
    sanity = sanity_check_parceiras(demanda_parceiras)
    # _relatorio_markdown ja roda o guard _assert_sem_pii internamente (por token/word-boundary);
    # aqui reforcamos a checagem por token isolado (nao substring de palavras PT legitimas).
    texto = _relatorio_markdown(res, sanity).lower()
    for col in COLUNAS_PII_PROIBIDAS:
        assert re.search(rf"\b{re.escape(col.lower())}\b", texto) is None, (
            f"PII '{col}' vazou no relatorio"
        )
    # o result nao carrega campo com nome de coluna proibida
    for campo in vars(res):
        assert campo not in COLUNAS_PII_PROIBIDAS


def test_loo_honesto_sem_r2_insample(base_curva_forte, demanda_parceiras):
    """R2 in-sample NUNCA aparece como campo/valor no result nem no relatorio (DEC-008)."""
    res = validar_curva_densidade(base_curva_forte)
    # nenhum campo do dataclass expoe r2 in-sample
    for campo in vars(res):
        assert "insample" not in campo.lower()
        assert "in_sample" not in campo.lower()
    sanity = sanity_check_parceiras(demanda_parceiras)
    texto = _relatorio_markdown(res, sanity).lower()
    # nenhum valor numerico rotulado como r2_insample pode existir no corpo
    assert "r2_insample =" not in texto
    assert "r2_insample=" not in texto
    assert "r2_in_sample" not in texto
    # a mencao explicativa de que o R2 in-sample e BANIDO deve estar presente (transparencia)
    assert "in-sample e banido" in texto or "banido" in texto


def test_intervalos_presentes(base_curva_forte):
    """p10/p50/p90 presentes e ordenados; flag_extrapolacao bool coerente."""
    res = validar_curva_densidade(base_curva_forte)
    assert set(res.intervalos_m2) == {"m2_p25", "m2_p50", "m2_p75"}
    for iv in res.intervalos_m2.values():
        assert iv["p10"] <= iv["p50"] <= iv["p90"]
        assert iv["n"] >= 1
    lo, hi = res.envelope_m2
    assert lo < hi
    # dentro do envelope -> False; muito fora -> True
    assert flag_extrapolacao_m2((lo + hi) / 2.0, base_curva_forte) is False
    assert flag_extrapolacao_m2(hi * 100.0, base_curva_forte) is True
    assert flag_extrapolacao_m2(-1.0, base_curva_forte) is True


def test_alunos_parceiras_nunca_preditor(base_curva_forte, demanda_parceiras):
    """sanity_check retorna usado_na_curva=False; X da curva so tem metragem/marca."""
    sanity = sanity_check_parceiras(demanda_parceiras)
    assert sanity["usado_na_curva"] is False
    assert "incompar" in sanity["motivo"].lower()
    assert sanity["faixa_referencia"]["n"] >= 1
    # a validacao da curva NAO le alunos_parceiras: uma base sem essa coluna valida igual
    assert "alunos_parceiras" not in base_curva_forte.columns
    res = validar_curva_densidade(base_curva_forte)
    assert isinstance(res, CurvaValidacaoResult)
    # o codigo-fonte da validacao nao referencia colunas de demanda como feature
    src = inspect.getsource(validar_curva_densidade)
    assert "alunos_parceiras" not in src
    assert "membros" not in src


def test_isolamento_import():
    """O modulo nao importa de pipelines.m1/dashboard/censo_/motor_expansao.api (DEC-012)."""
    src = inspect.getsource(m)
    for proibido in ("pipelines.m1", "dashboard", "censo_", "motor_expansao.api"):
        assert proibido not in src, f"import proibido '{proibido}' no modulo"


def test_ic_bootstrap_deterministico(base_curva_forte):
    """Mesma seed -> mesmo IC95 (reprodutibilidade DEC-008)."""
    r1 = validar_curva_densidade(base_curva_forte)
    r2 = validar_curva_densidade(base_curva_forte)
    assert r1.r2_oof_ic95 == pytest.approx(r2.r2_oof_ic95)
    assert r1.rho_oof_ic95 == pytest.approx(r2.rho_oof_ic95)
    assert r1.r2_oof == pytest.approx(r2.r2_oof)


def test_go_nogo_criterio(base_curva_forte, base_curva_ruido):
    """Sinal forte -> go=True; ruido -> go=False (IC cruza zero)."""
    forte = validar_curva_densidade(base_curva_forte)
    ruido = validar_curva_densidade(base_curva_ruido)
    assert forte.go is True
    assert forte.veredito == "GO"
    assert forte.r2_oof > 0.0
    assert forte.r2_oof_ic95[0] > 0.0
    assert ruido.go is False
    assert ruido.veredito == "NO-GO"
    # criterio D7: NO-GO quando R2_oof <= 0 OU IC95 inferior <= 0
    assert (ruido.r2_oof <= 0.0) or (ruido.r2_oof_ic95[0] <= 0.0)


def test_relatorio_cria_arquivo(base_curva_forte, demanda_parceiras, tmp_path):
    """escrever_relatorio grava .md nao-vazio."""
    res = validar_curva_densidade(base_curva_forte)
    sanity = sanity_check_parceiras(demanda_parceiras)
    p = tmp_path / "calibracao_curva_densidade.md"
    escrever_relatorio(res, sanity, path=p)
    assert p.exists()
    conteudo = p.read_text(encoding="utf-8")
    assert conteudo.strip()
    assert "BLK-TP-04" in conteudo
    assert res.veredito in conteudo
