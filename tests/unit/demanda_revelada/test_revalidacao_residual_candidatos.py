"""BLK-TP-06-FU1: testes offline (seed-fixo, sem I/O real) da re-validacao do residual.

Fixtures SINTETICAS (nunca a fonte real NAO_ABRA/ nem data/staging): join demanda x mercado com
colunas agregadas + oferta de academias menores por rede + pares de concorrentes. Cobre:
  - dedup FINO correto por par (hex, rede): rede conhecida JA mapeada NAO soma; rede nao mapeada
    soma; `independente` sempre soma;
  - residual do Candidato A CAI onde soma; fica em [0,100]; oferta efetiva nunca negativa;
  - baseline == `score_oportunidade_residual` do parquet (reproduz o BLK-TP-06);
  - R2 in-sample BANIDO do veredito (nao ha campo in-sample no fluxo de veredito);
  - Delta pareado determinista (seed) e usa os MESMOS indices nos 2 vetores (cand==base => ~0);
  - isolamento de import (AST: sem m1/dashboard/censo/api/config/pipelines.calcular/enriquecimento);
  - anti-PII no relatorio/frames; NO-GO/NAO_APLICAR e resultado valido sem excecao.
"""

from __future__ import annotations

import ast
import inspect
import re

import numpy as np
import pandas as pd
import pytest

from motor_expansao.demanda_revelada import revalidacao_residual_candidatos as m
from motor_expansao.demanda_revelada.contrato import COLUNAS_PII_PROIBIDAS
from motor_expansao.demanda_revelada.revalidacao_residual_candidatos import (
    CAP_REF,
    alunos_menores_add_por_hex,
    comparar_pareado,
    construir_pares_concorrentes,
    construir_residuais_candidatos,
    relatorio_revalidacao,
    revalidar_candidatos,
    validar_candidato,
)


# --------------------------------------------------------------------------- #
# Fixtures sinteticas
# --------------------------------------------------------------------------- #
def _hexes(n: int) -> list[str]:
    return [f"87a{i:012x}ffff" for i in range(n)]


@pytest.fixture
def join_sintetico() -> pd.DataFrame:
    """Join demanda x mercado com sinal monotonico membros ~ residual (para o harness rodar)."""
    rng = np.random.default_rng(11)
    n = 400
    score = rng.uniform(0.0, 100.0, n)
    log_mem = 0.06 * score + rng.normal(0.0, 0.3, n)
    membros = np.expm1(np.clip(log_mem, 0.0, None)).round().astype(int)
    sam = rng.uniform(0.0, 6000.0, n)
    consumida = rng.uniform(0.0, 3000.0, n)
    uf = np.where(np.arange(n) % 3 == 0, "SP", np.where(np.arange(n) % 3 == 1, "MG", "BA"))
    return pd.DataFrame(
        {
            "hex_id": _hexes(n),
            "membros": membros,
            "uf": uf,
            "score_oportunidade_residual": score,
            "sam_fitness_potencial": sam,
            "oferta_consumida_total_estimada": consumida,
        }
    )


@pytest.fixture
def of_menores() -> pd.DataFrame:
    """Oferta de academias menores por (hex, rede): 3 casos-chave nos hexes 0,1,2."""
    hx = _hexes(3)
    return pd.DataFrame(
        {
            "hex_id": [hx[0], hx[1], hx[2]],
            "rede_menor": ["panobianco", "independente", "velocity"],
            "n_academias_menores": [1, 1, 1],
            "alunos_academias_menores": [500, 300, 200],
            "versao_contrato": ["oferta_menores_rede_v1"] * 3,
        }
    )


@pytest.fixture
def pares_conc() -> set[tuple[str, str]]:
    """Concorrentes mapeados: hex0/panobianco JA existe (deve dedupar); velocity NAO existe."""
    hx = _hexes(3)
    return {(hx[0], "panobianco")}


# --------------------------------------------------------------------------- #
# Dedup FINO por par (hex, rede)
# --------------------------------------------------------------------------- #
def test_dedup_fino_rede_ja_mapeada_nao_soma(of_menores, pares_conc):
    """Par (hex, rede_conhecida) que JA existe em concorrentes NAO soma."""
    hx = _hexes(3)
    add = alunos_menores_add_por_hex(of_menores, pares_conc)
    # hex0/panobianco esta nos pares -> dedupado -> NAO entra na soma.
    assert hx[0] not in add.index or add.get(hx[0], 0.0) == 0.0


def test_dedup_fino_independente_sempre_soma(of_menores, pares_conc):
    """`independente` sempre soma integral (rede distinta, oferta que o Motor ignora)."""
    hx = _hexes(3)
    add = alunos_menores_add_por_hex(of_menores, pares_conc)
    assert add.get(hx[1], 0.0) == 300.0


def test_dedup_fino_rede_nao_mapeada_soma(of_menores, pares_conc):
    """Rede conhecida NAO mapeada em concorrentes soma integral."""
    hx = _hexes(3)
    add = alunos_menores_add_por_hex(of_menores, pares_conc)
    assert add.get(hx[2], 0.0) == 200.0


def test_dedup_independente_soma_mesmo_com_concorrente_no_hex(pares_conc):
    """Mesmo com um concorrente de OUTRA rede no hex, o `independente` continua somando."""
    hx = _hexes(1)
    of = pd.DataFrame(
        {
            "hex_id": [hx[0], hx[0]],
            "rede_menor": ["independente", "panobianco"],
            "alunos_academias_menores": [400, 500],
        }
    )
    # hex0/panobianco esta nos pares -> so o independente (400) soma.
    add = alunos_menores_add_por_hex(of, {(hx[0], "panobianco")})
    assert add.get(hx[0], 0.0) == 400.0


def test_construir_pares_filtra_status_valido():
    """`construir_pares_concorrentes` filtra status_registro=='valido' e usa hex_id_res7."""
    conc = pd.DataFrame(
        {
            "hex_id_res7": ["h1", "h2"],
            "rede": ["smart_fit", "selfit"],
            "status_registro": ["valido", "invalido"],
        }
    )
    pares = construir_pares_concorrentes(conc)
    assert ("h1", "smart_fit") in pares
    assert ("h2", "selfit") not in pares


# --------------------------------------------------------------------------- #
# Residual do Candidato A
# --------------------------------------------------------------------------- #
def test_residual_A_cai_onde_soma(join_sintetico, of_menores, pares_conc):
    """O residual do Candidato A e <= baseline onde ha oferta menor somada (satura mais)."""
    df = construir_residuais_candidatos(join_sintetico, of_menores, pares_conc)
    hx = _hexes(3)
    somados = df["hex_id"].isin([hx[1], hx[2]])  # independente + velocity somam
    # onde soma, oferta consumida sobe => oferta efetiva cai => residual cai (ou igual se ja 0).
    assert (df.loc[somados, "residual_cand_A"] <= df.loc[somados, "residual_baseline"] + 1e-9).all()


def test_residual_A_em_faixa_e_nao_negativo(join_sintetico, of_menores, pares_conc):
    """residual_cand_A em [0,100] e oferta efetiva nunca negativa (clip)."""
    df = construir_residuais_candidatos(join_sintetico, of_menores, pares_conc)
    assert (df["residual_cand_A"] >= 0.0).all()
    assert (df["residual_cand_A"] <= 100.0).all()


def test_baseline_igual_score_do_parquet(join_sintetico, of_menores, pares_conc):
    """residual_baseline == score_oportunidade_residual (reproduz o BLK-TP-06)."""
    df = construir_residuais_candidatos(join_sintetico, of_menores, pares_conc)
    pd.testing.assert_series_equal(
        df["residual_baseline"],
        df["score_oportunidade_residual"].astype(float),
        check_names=False,
    )


def test_flag_metropolitano(join_sintetico, of_menores, pares_conc):
    """flag_metropolitano True so para SP/MG/RJ."""
    df = construir_residuais_candidatos(join_sintetico, of_menores, pares_conc)
    assert (df.loc[df["uf"].isin(["SP", "MG"]), "flag_metropolitano"]).all()
    assert not (df.loc[df["uf"] == "BA", "flag_metropolitano"]).any()


# --------------------------------------------------------------------------- #
# Validacao out-of-fold + veredito honesto
# --------------------------------------------------------------------------- #
def test_r2_insample_banido_do_veredito(join_sintetico, of_menores, pares_conc):
    """Nenhum campo/atributo de R2 in-sample vaza para o resultado do candidato (DEC-008)."""
    res = revalidar_candidatos(join_sintetico, of_menores, pares_conc)
    cand = res.recortes[m.RECORTE_COMPLETO].candidatos["cand_A"]
    for campo in vars(cand):
        assert "insample" not in campo.lower()
        assert "in_sample" not in campo.lower()


def test_ic_determinista_seed(join_sintetico):
    """IC95 do candidato e determinista (seed=42): duas chamadas dao o mesmo resultado."""
    df = join_sintetico.assign(residual_baseline=join_sintetico["score_oportunidade_residual"])
    a = validar_candidato(df, "residual_baseline", nome="b")
    b = validar_candidato(df, "residual_baseline", nome="b")
    assert a.r2_oof_log == pytest.approx(b.r2_oof_log)
    assert a.ic95_r2_oof == pytest.approx(b.ic95_r2_oof)
    assert a.rho_oof == pytest.approx(b.rho_oof)


def test_bootstrap_pareado_mesmos_indices(join_sintetico):
    """cand==baseline => Delta pareado ~0 e IC95 cobre zero (mesmos indices nos 2 vetores)."""
    df = join_sintetico.assign(residual_baseline=join_sintetico["score_oportunidade_residual"])
    r = validar_candidato(df, "residual_baseline", nome="b")
    delta, ic = comparar_pareado(r.y_oof, r.y_pred_oof, r.y_pred_oof)
    assert delta == pytest.approx(0.0, abs=1e-12)
    assert ic[0] <= 0.0 <= ic[1]


def test_bootstrap_pareado_determinista(join_sintetico):
    """Delta pareado e reproduzivel com a mesma seed."""
    df = join_sintetico.assign(residual_baseline=join_sintetico["score_oportunidade_residual"])
    r = validar_candidato(df, "residual_baseline", nome="b")
    rng_score = df["score_oportunidade_residual"].to_numpy(float)
    # perturba o candidato para um delta nao-trivial mas determinista
    cand_pred = r.y_pred_oof + 0.01 * (rng_score[: len(r.y_pred_oof)] - 50.0)
    d1, ic1 = comparar_pareado(r.y_oof, r.y_pred_oof, cand_pred)
    d2, ic2 = comparar_pareado(r.y_oof, r.y_pred_oof, cand_pred)
    assert d1 == pytest.approx(d2)
    assert ic1 == pytest.approx(ic2)


def test_no_go_e_resultado_valido(join_sintetico, of_menores, pares_conc):
    """NAO_APLICAR/APLICAR_A e resultado valido sem excecao; veredito coerente com o Delta."""
    res = revalidar_candidatos(join_sintetico, of_menores, pares_conc)
    assert res.veredito in ("APLICAR_A", "NAO_APLICAR")
    # veredito casa com a propriedade de vitoria (completo E fora)
    esperado = "APLICAR_A" if res.vence_candidato_a else "NAO_APLICAR"
    assert res.veredito == esperado


def test_vence_exige_completo_e_fora(join_sintetico, of_menores, pares_conc):
    """`vence_candidato_a` exige vitoria no completo E fora de SP/MG/RJ."""
    res = revalidar_candidatos(join_sintetico, of_menores, pares_conc)
    comp_c = res.recortes[m.RECORTE_COMPLETO].comparacoes["cand_A"].vence
    comp_f = res.recortes[m.RECORTE_FORA].comparacoes["cand_A"].vence
    assert res.vence_candidato_a == (comp_c and comp_f)


# --------------------------------------------------------------------------- #
# Anti-PII + isolamento de import
# --------------------------------------------------------------------------- #
def test_anti_pii_relatorio(join_sintetico, of_menores, pares_conc):
    """Nenhuma coluna de COLUNAS_PII_PROIBIDAS como TOKEN isolado no relatorio."""
    res = revalidar_candidatos(join_sintetico, of_menores, pares_conc)
    texto = relatorio_revalidacao(res).lower()
    for col in COLUNAS_PII_PROIBIDAS:
        assert re.search(rf"\b{re.escape(col.lower())}\b", texto) is None, (
            f"PII '{col}' vazou no relatorio"
        )


def test_isolamento_import():
    """AST: o modulo NUNCA importa de m1/dashboard/censo/api/config/pipelines pesados (DEC-012)."""
    src = inspect.getsource(m)
    proibidos = (
        "motor_expansao.pipelines.m1",
        "motor_expansao.dashboard",
        "motor_expansao.censo",
        "motor_expansao.api",
        "motor_expansao.pipelines.calcular_colunas_mercado",
        "motor_expansao.pipelines.enriquecimento_espacial_hexagonos",
    )
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert not any(mod.startswith(p) for p in proibidos), f"import proibido: {mod}"
            assert mod != "config", "nao importar config.py raiz"
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not any(alias.name.startswith(p) for p in proibidos)


def test_cap_ref_constante():
    """CAP_REF = 2500 (denominador do clip INTOCADO)."""
    assert CAP_REF == 2500.0
