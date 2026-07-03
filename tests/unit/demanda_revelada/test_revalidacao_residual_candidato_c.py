"""BLK-TP-06-FU2: testes offline (seed-fixo, sem I/O real) do Candidato C (C1 + C2).

Fixtures SINTETICAS (nunca a fonte real `data/validacao/` nem `data/staging/`):
  - leitor anti-PII de capacidade de clube: xlsx sintetico em tmp_path (openpyxl) -> retorno so
    `{rede: float}`, ZERO PII; capacidade real vs fallback por rede;
  - decay point-level dos concorrentes (dist~0 => peso~1; 2 km => 0; 1 km => 0,5) ponderado por
    capacidade por rede;
  - k-ring de bairro k=1 ponderado (1,0/0,5) NORMALIZADO Σ=4,0 -> conserva massa (NAO infla ~4x);
  - residual C1/C2 em [0,100], oferta efetiva >= 0, CAP_REF=2500 intocado;
  - R2 in-sample BANIDO do resultado dos candidatos C (DEC-008);
  - Δ pareado determinista (seed) + veredito por sub-candidato sem excecao;
  - isolamento de import (AST) dos DOIS modulos (sem m1/dashboard/censo/api/config/pipelines).
"""

from __future__ import annotations

import ast
import inspect

import numpy as np
import pandas as pd
import pytest
from openpyxl import Workbook

from motor_expansao.demanda_revelada import capacidade_clube_validacao as capmod
from motor_expansao.demanda_revelada import revalidacao_residual_candidatos as m
from motor_expansao.demanda_revelada.capacidade_clube_validacao import (
    FALLBACK_CAPACIDADE,
    capacidade_por_rede_com_fallback,
    ler_capacidade_clube_por_rede,
)
from motor_expansao.demanda_revelada.contrato import COLUNAS_PII_PROIBIDAS
from motor_expansao.demanda_revelada.revalidacao_residual_candidatos import (
    CAP_REF,
    construir_residuais_candidatos,
    oferta_bairro_decaida_kring_por_hex,
    oferta_concorrentes_recapacitada_por_hex,
    relatorio_revalidacao_candidato_c,
    revalidar_candidatos,
)


# --------------------------------------------------------------------------- #
# Fixtures sinteticas
# --------------------------------------------------------------------------- #
def _hex(lat: float, lng: float) -> str:
    import h3

    return h3.latlng_to_cell(lat, lng, 7)


@pytest.fixture
def join_geo() -> pd.DataFrame:
    """Join demanda x mercado com lat/lng + Ultra, sinal monotonico membros ~ residual."""
    rng = np.random.default_rng(7)
    n = 400
    lat = -23.5 + rng.uniform(-0.5, 0.5, n)
    lng = -46.6 + rng.uniform(-0.5, 0.5, n)
    hexes = [_hex(a, b) for a, b in zip(lat, lng, strict=True)]
    score = rng.uniform(0.0, 100.0, n)
    log_mem = 0.06 * score + rng.normal(0.0, 0.3, n)
    membros = np.expm1(np.clip(log_mem, 0.0, None)).round().astype(int)
    uf = np.where(np.arange(n) % 3 == 0, "SP", np.where(np.arange(n) % 3 == 1, "MG", "BA"))
    return pd.DataFrame(
        {
            "hex_id": hexes,
            "membros": membros,
            "uf": uf,
            "lat": lat,
            "lng": lng,
            "score_oportunidade_residual": score,
            "sam_fitness_potencial": rng.uniform(0.0, 6000.0, n),
            "oferta_consumida_total_estimada": rng.uniform(0.0, 3000.0, n),
            "oferta_consumida_ultra_estimada": rng.uniform(0.0, 500.0, n),
        }
    )


@pytest.fixture
def of_menores() -> pd.DataFrame:
    hx = ["87abc00000ffff", "87abc00001ffff"]
    return pd.DataFrame(
        {
            "hex_id": hx,
            "rede_menor": ["independente", "velocity"],
            "n_academias_menores": [1, 1],
            "alunos_academias_menores": [300, 200],
        }
    )


@pytest.fixture
def conc_geo(join_geo) -> pd.DataFrame:
    """Concorrentes point-level com lat/lng, 2 redes (smart_fit real, velocity fallback)."""
    row = join_geo.iloc[0]
    return pd.DataFrame(
        {
            "rede": ["smart_fit", "velocity"],
            "lat": [row["lat"], row["lat"]],
            "lng": [row["lng"], row["lng"]],
            "status_registro": ["valido", "valido"],
        }
    )


# --------------------------------------------------------------------------- #
# Leitor anti-PII de capacidade de clube
# --------------------------------------------------------------------------- #
def _escrever_xlsx_smart(path, alunos: list[float]) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Base"
    ws.append(["Data_Ref", "Sigla", "Nome", "Alunos Totais SF"])
    for i, a in enumerate(alunos):
        ws.append(["2025-02-01", f"U{i}", f"UNIDADE PII {i}", a])
    wb.save(path)


def _escrever_xlsx_eng(path, alunos: list[float]) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Academias"
    ws.append(["ID", "Unidade", "Alunos Totais"])
    for i, a in enumerate(alunos):
        ws.append([i, f"ACADEMIA PII {i}", a])
    wb.save(path)


def test_leitor_capacidade_retorna_so_dict_float(tmp_path, monkeypatch):
    """Retorno e SO `{rede: float}`; nenhum nome/PII atravessa a fronteira."""
    _escrever_xlsx_smart(tmp_path / "KPIs_Smart_2025_02 (1).xlsx", [2000, 2400, 2600])
    _escrever_xlsx_eng(tmp_path / "academias_engenharia_do_corpo.xlsx", [3000, 3200])
    cap = ler_capacidade_clube_por_rede(tmp_path)
    assert set(cap) == {"smart_fit", "engenharia_do_corpo"}
    for k, v in cap.items():
        assert isinstance(k, str) and isinstance(v, float)
    # mediana das 3 unidades Smart = 2400; Engenharia = 3100
    assert cap["smart_fit"] == pytest.approx(2400.0)
    assert cap["engenharia_do_corpo"] == pytest.approx(3100.0)


def test_leitor_capacidade_zero_pii(tmp_path):
    """Nenhuma coluna de COLUNAS_PII_PROIBIDAS vira chave; valores sao floats (sem PII)."""
    _escrever_xlsx_smart(tmp_path / "KPIs_Smart_2025_02 (1).xlsx", [2200])
    cap = ler_capacidade_clube_por_rede(tmp_path)
    for chave in cap:
        assert chave.lower() not in {c.lower() for c in COLUNAS_PII_PROIBIDAS}
    # o dict inteiro nao contem nenhum token PII como chave
    assert all(isinstance(v, float) for v in cap.values())


def test_capacidade_fallback_para_rede_sem_arquivo(tmp_path):
    """Rede sem arquivo cai no fallback 2.500; dict COMPLETO cobre todas as redes-alvo."""
    _escrever_xlsx_smart(tmp_path / "KPIs_Smart_2025_02 (1).xlsx", [2400])
    cap_reais = ler_capacidade_clube_por_rede(tmp_path)  # so smart_fit
    redes = ["smart_fit", "velocity", "selfit", "engenharia_do_corpo"]
    cap = capacidade_por_rede_com_fallback(redes, cap_reais)
    assert set(cap) == set(redes)
    assert cap["smart_fit"] == pytest.approx(2400.0)
    assert cap["velocity"] == FALLBACK_CAPACIDADE
    assert cap["selfit"] == FALLBACK_CAPACIDADE
    # engenharia sem arquivo -> fallback (nao foi lido)
    assert cap["engenharia_do_corpo"] == FALLBACK_CAPACIDADE


def test_capacidade_real_vs_fallback_por_rede(tmp_path):
    """Redes lidas usam capacidade real; nao-lidas usam fallback (distinguiveis)."""
    _escrever_xlsx_smart(tmp_path / "KPIs_Smart_2025_02 (1).xlsx", [2350])
    _escrever_xlsx_eng(tmp_path / "academias_engenharia_do_corpo.xlsx", [3100])
    cap_reais = ler_capacidade_clube_por_rede(tmp_path)
    cap = capacidade_por_rede_com_fallback(["smart_fit", "engenharia_do_corpo", "bluefit"], cap_reais)
    assert cap["smart_fit"] == pytest.approx(2350.0)
    assert cap["engenharia_do_corpo"] == pytest.approx(3100.0)
    assert cap["bluefit"] == FALLBACK_CAPACIDADE


def test_capacidade_arquivo_ausente_retorna_vazio(tmp_path):
    """Sem nenhum xlsx, o leitor retorna {} (sem excecao); fallback cobre tudo depois."""
    assert ler_capacidade_clube_por_rede(tmp_path) == {}


# --------------------------------------------------------------------------- #
# Decay point-level dos concorrentes (C1)
# --------------------------------------------------------------------------- #
def test_decay_pointlevel_dist_zero_peso_um():
    """Concorrente sobre o hex (dist~0) => peso~1 => oferta ~= cap da rede."""
    h = _hex(-23.5, -46.6)
    conc = pd.DataFrame(
        {"rede": ["a"], "lat": [-23.5], "lng": [-46.6], "status_registro": ["valido"]}
    )
    o = oferta_concorrentes_recapacitada_por_hex(
        pd.Series([h]), pd.Series([-23.5]), pd.Series([-46.6]), conc, {"a": 2000.0}
    )
    assert o.iloc[0] == pytest.approx(2000.0, rel=1e-3)


def test_decay_pointlevel_2km_peso_zero():
    """Concorrente a 2 km => peso 0 => oferta 0."""
    lat2 = -23.5 + (2000.0 / 6_371_000.0) * (180.0 / np.pi)
    conc = pd.DataFrame(
        {"rede": ["a"], "lat": [lat2], "lng": [-46.6], "status_registro": ["valido"]}
    )
    o = oferta_concorrentes_recapacitada_por_hex(
        pd.Series([_hex(-23.5, -46.6)]), pd.Series([-23.5]), pd.Series([-46.6]), conc, {"a": 2000.0}
    )
    assert o.iloc[0] == pytest.approx(0.0, abs=1.0)


def test_decay_pointlevel_1km_peso_meio():
    """Concorrente a ~1 km => peso ~0,5 => oferta ~= 0,5*cap."""
    lat1 = -23.5 + (1000.0 / 6_371_000.0) * (180.0 / np.pi)
    conc = pd.DataFrame(
        {"rede": ["a"], "lat": [lat1], "lng": [-46.6], "status_registro": ["valido"]}
    )
    o = oferta_concorrentes_recapacitada_por_hex(
        pd.Series([_hex(-23.5, -46.6)]), pd.Series([-23.5]), pd.Series([-46.6]), conc, {"a": 2000.0}
    )
    assert o.iloc[0] == pytest.approx(1000.0, rel=0.02)


def test_decay_pointlevel_capacidade_por_rede():
    """Redes distintas aplicam capacidades distintas (peso~1 cada)."""
    conc = pd.DataFrame(
        {
            "rede": ["a", "b"],
            "lat": [-23.5, -23.5],
            "lng": [-46.6, -46.6],
            "status_registro": ["valido", "valido"],
        }
    )
    o = oferta_concorrentes_recapacitada_por_hex(
        pd.Series([_hex(-23.5, -46.6)]),
        pd.Series([-23.5]),
        pd.Series([-46.6]),
        conc,
        {"a": 2000.0, "b": 3000.0},
    )
    assert o.iloc[0] == pytest.approx(5000.0, rel=1e-3)


def test_decay_pointlevel_fallback_rede_ausente():
    """Rede sem capacidade no dict usa cap_fallback (default CAP_REF=2500)."""
    conc = pd.DataFrame(
        {"rede": ["desconhecida"], "lat": [-23.5], "lng": [-46.6], "status_registro": ["valido"]}
    )
    o = oferta_concorrentes_recapacitada_por_hex(
        pd.Series([_hex(-23.5, -46.6)]), pd.Series([-23.5]), pd.Series([-46.6]), conc, {}
    )
    assert o.iloc[0] == pytest.approx(CAP_REF, rel=1e-3)


# --------------------------------------------------------------------------- #
# k-ring de bairro (C2) -- conserva massa (NAO infla ~4x)
# --------------------------------------------------------------------------- #
def test_kring_ponderado_conserva_massa():
    """k=1 ponderado (1,0/0,5) NORMALIZADO => Σ contribuicoes == add original (nao infla 4x)."""
    import h3

    hf = _hex(-23.5, -46.6)
    alvo = {hf} | set(h3.grid_ring(hf, 1))
    s = oferta_bairro_decaida_kring_por_hex(pd.Series({hf: 1000.0}), alvo, k=1, pesos_anel=(1.0, 0.5))
    assert s.sum() == pytest.approx(1000.0)
    # central = 1000*1.0/4.0 = 250; cada vizinho = 1000*0.5/4.0 = 125 (6 => 750)
    assert s[hf] == pytest.approx(250.0)
    vizinhos = [h for h in s.index if h != hf]
    assert all(s[h] == pytest.approx(125.0) for h in vizinhos)


def test_kring_nao_infla_quadruplo():
    """Prova explicita: sem normalizacao o total seria 4000; com normalizacao fica 1000."""
    import h3

    hf = _hex(-23.5, -46.6)
    alvo = {hf} | set(h3.grid_ring(hf, 1))
    s = oferta_bairro_decaida_kring_por_hex(pd.Series({hf: 1000.0}), alvo, k=1, pesos_anel=(1.0, 0.5))
    soma_pesos_bruta = 1.0 + 6 * 0.5  # = 4.0
    assert s.sum() == pytest.approx(1000.0)
    assert s.sum() != pytest.approx(1000.0 * soma_pesos_bruta)  # nao infla 4x


def test_kring_k0_mantem_no_hex():
    """k=0 (peso 1.0) mantem todo o valor no proprio hex-fonte."""
    hf = _hex(-23.5, -46.6)
    s = oferta_bairro_decaida_kring_por_hex(pd.Series({hf: 800.0}), {hf}, k=0, pesos_anel=(1.0,))
    assert s.sum() == pytest.approx(800.0)
    assert s[hf] == pytest.approx(800.0)


def test_kring_flat_difere_do_ponderado():
    """k=1 flat (1,1) distribui uniforme (central==vizinho); ponderado nao."""
    import h3

    hf = _hex(-23.5, -46.6)
    alvo = {hf} | set(h3.grid_ring(hf, 1))
    flat = oferta_bairro_decaida_kring_por_hex(
        pd.Series({hf: 700.0}), alvo, k=1, pesos_anel=(1.0, 1.0)
    )
    # flat: Σ pesos = 7; central = 700/7 = 100; conserva massa
    assert flat.sum() == pytest.approx(700.0)
    assert flat[hf] == pytest.approx(100.0)


# --------------------------------------------------------------------------- #
# residual C1/C2 -- faixa, nao-negativo, CAP_REF intocado
# --------------------------------------------------------------------------- #
def test_residual_c1_c2_em_faixa(join_geo, of_menores, conc_geo):
    """residual_cand_C1/C2 em [0,100]; oferta efetiva nunca negativa (clip)."""
    cap = {"smart_fit": 2400.0}  # velocity cai no fallback
    df = construir_residuais_candidatos(
        join_geo, of_menores, {("h", "smart_fit")}, capacidade_por_rede=cap, conc_df=conc_geo
    )
    for col in ("residual_cand_C1", "residual_cand_C2"):
        assert (df[col] >= 0.0).all()
        assert (df[col] <= 100.0).all()


def test_c2_menor_igual_c1(join_geo, of_menores, conc_geo):
    """C2 adiciona oferta consumida (bairro) => residual C2 <= C1 (satura mais)."""
    cap = {"smart_fit": 2400.0}
    df = construir_residuais_candidatos(
        join_geo, of_menores, set(), capacidade_por_rede=cap, conc_df=conc_geo
    )
    assert (df["residual_cand_C2"] <= df["residual_cand_C1"] + 1e-9).all()


def test_cap_ref_intocado():
    """CAP_REF = 2500 (denominador do clip do residual INTOCADO)."""
    assert CAP_REF == 2500.0


def test_c_ausente_preserva_fu1(join_geo, of_menores):
    """Sem capacidade_por_rede/conc_df, NAO cria colunas C (comportamento FU1)."""
    df = construir_residuais_candidatos(join_geo, of_menores, set())
    assert "residual_cand_C1" not in df.columns
    assert "residual_cand_C2" not in df.columns
    assert "residual_cand_A" in df.columns


# --------------------------------------------------------------------------- #
# Validacao out-of-fold + veredito por sub-candidato
# --------------------------------------------------------------------------- #
def test_r2_insample_banido_c(join_geo, of_menores, conc_geo):
    """Nenhum campo in-sample no resultado dos candidatos C1/C2 (DEC-008)."""
    cap = {"smart_fit": 2400.0}
    res = revalidar_candidatos(
        join_geo, of_menores, set(), capacidade_por_rede=cap, conc_df=conc_geo
    )
    for chave in ("cand_C1", "cand_C2"):
        cand = res.recortes[m.RECORTE_COMPLETO].candidatos[chave]
        for campo in vars(cand):
            assert "insample" not in campo.lower()
            assert "in_sample" not in campo.lower()


def test_veredito_por_sub_candidato(join_geo, of_menores, conc_geo):
    """Veredito consolidado inclui APLICAR/NAO_APLICAR de A, C1 e C2 sem excecao."""
    cap = {"smart_fit": 2400.0}
    res = revalidar_candidatos(
        join_geo, of_menores, set(), capacidade_por_rede=cap, conc_df=conc_geo
    )
    partes = {p.strip() for p in res.veredito.split(";")}
    for rot in ("A", "C1", "C2"):
        assert (f"APLICAR_{rot}" in partes) or (f"NAO_APLICAR_{rot}" in partes)
    # casa com as propriedades de vitoria (token EXATO, nao substring)
    assert ("APLICAR_C1" in partes) == res.vence_candidato_c1
    assert ("APLICAR_C2" in partes) == res.vence_candidato_c2


def test_vence_c_exige_completo_e_fora(join_geo, of_menores, conc_geo):
    """`vence_candidato_c1/c2` exige vitoria no completo E fora de SP/MG/RJ (decisao (D))."""
    cap = {"smart_fit": 2400.0}
    res = revalidar_candidatos(
        join_geo, of_menores, set(), capacidade_por_rede=cap, conc_df=conc_geo
    )
    for chave, prop in (("cand_C1", res.vence_candidato_c1), ("cand_C2", res.vence_candidato_c2)):
        comp_c = res.recortes[m.RECORTE_COMPLETO].comparacoes[chave].vence
        comp_f = res.recortes[m.RECORTE_FORA].comparacoes[chave].vence
        assert prop == (comp_c and comp_f)


def test_delta_pareado_determinista_c(join_geo, of_menores, conc_geo):
    """Duas execucoes (seed=42) dao o mesmo Δ pareado de C1/C2 (reprodutivel)."""
    cap = {"smart_fit": 2400.0}
    r1 = revalidar_candidatos(join_geo, of_menores, set(), capacidade_por_rede=cap, conc_df=conc_geo)
    r2 = revalidar_candidatos(join_geo, of_menores, set(), capacidade_por_rede=cap, conc_df=conc_geo)
    for chave in ("cand_C1", "cand_C2"):
        d1 = r1.recortes[m.RECORTE_COMPLETO].comparacoes[chave]
        d2 = r2.recortes[m.RECORTE_COMPLETO].comparacoes[chave]
        assert d1.delta_medio == pytest.approx(d2.delta_medio)
        assert d1.ic95_delta == pytest.approx(d2.ic95_delta)


def test_c1_capacidade_uniforme_neutro(join_geo, of_menores):
    """Capacidade uniforme=2500 p/ toda rede => C1 e uma re-derivacao consistente (sem excecao)."""
    conc = pd.DataFrame(
        {
            "rede": ["r1", "r2"],
            "lat": list(join_geo["lat"].iloc[:2]),
            "lng": list(join_geo["lng"].iloc[:2]),
            "status_registro": ["valido", "valido"],
        }
    )
    cap = {}  # tudo cai no fallback 2500
    df = construir_residuais_candidatos(
        join_geo, of_menores, set(), capacidade_por_rede=cap, conc_df=conc, cap_ref=CAP_REF
    )
    assert (df["residual_cand_C1"] >= 0.0).all()
    assert (df["residual_cand_C1"] <= 100.0).all()


# --------------------------------------------------------------------------- #
# Anti-PII no relatorio C + isolamento de import (AST) dos 2 modulos
# --------------------------------------------------------------------------- #
def test_anti_pii_relatorio_c(join_geo, of_menores, conc_geo):
    """Nenhuma coluna PII como token isolado no relatorio do Candidato C."""
    import re

    cap = {"smart_fit": 2400.0, "velocity": 2500.0}
    res = revalidar_candidatos(
        join_geo, of_menores, set(), capacidade_por_rede=cap, conc_df=conc_geo
    )
    texto = relatorio_revalidacao_candidato_c(
        res, capacidades=cap, ancora_sky=2191.0, n_redes_alvo=2, n_redes_reais=1
    ).lower()
    for col in COLUNAS_PII_PROIBIDAS:
        assert re.search(rf"\b{re.escape(col.lower())}\b", texto) is None, f"PII '{col}' vazou"


def _proibidos_ast(mod) -> None:
    src = inspect.getsource(mod)
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
            modn = node.module or ""
            assert not any(modn.startswith(p) for p in proibidos), f"import proibido: {modn}"
            assert modn != "config", "nao importar config.py raiz"
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not any(alias.name.startswith(p) for p in proibidos)


def test_isolamento_import_revalidacao():
    """AST: revalidacao_residual_candidatos nao importa de m1/dashboard/censo/api/config/pipelines."""
    _proibidos_ast(m)


def test_isolamento_import_capacidade():
    """AST: capacidade_clube_validacao nao importa de m1/dashboard/censo/api/config/pipelines."""
    _proibidos_ast(capmod)
