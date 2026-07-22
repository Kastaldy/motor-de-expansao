"""Matriz de contrato + guardrails do backend do piloto web (web/server/app.py).

WEB-16 (READ-ONLY sobre o M1). Estende o smoke de `test_piloto_web_api.py` para a
matriz completa do backend — a rede de seguranca que autoriza aposentar o Streamlit:

  - **JSON-safe:** `_num`/`_numf` transformam NaN/inf/None em None; nenhum payload
    carrega valor que quebre `json.dumps(..., allow_nan=False)`.
  - **Contrato de TODOS os endpoints em degradacao graciosa** (SEM os parquets — o
    cenario do CI): cada rota responde ou levanta `HTTPException` coerente.
  - **Guardrail READ-ONLY ESTATICO (AST):** o backend nao chama nenhum escritor de
    artefato (`to_parquet`/`to_csv`/...) nem operacao destrutiva de FS. Analise por
    AST — nao pode ser enganada por string/comentario como o grep textual antigo.
  - **Guardrail READ-ONLY em RUNTIME:** com um dataset SINTETICO minimo, exercita os
    endpoints de leitura e prova, por snapshot do filesystem, que nada foi escrito
    fora do `cache/` — a prova de que a leitura nao muta artefato do M1.

Chama as funcoes de rota DIRETO (sem TestClient/httpx), como o smoke existente.
"""

from __future__ import annotations

import ast
import asyncio
import json
import sys
from pathlib import Path

import pandas as pd
import pytest
from fastapi import HTTPException

_REPO = Path(__file__).resolve().parents[2]  # tests/unit/ -> raiz do worktree
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import app as pilot  # noqa: E402  (backend do piloto; web/server no sys.path acima)

# ---------------------------------------------------------------------------
# Retargeting: aponta os globais de caminho do app para um data_dir de teste e
# limpa TODOS os lru_caches (as cargas do app sao lazy + cacheadas por processo).
# ---------------------------------------------------------------------------

_CACHED = [
    "carregar_uf",
    "carregar_uf_completo",
    "listar_ufs",
    "_fator_temporal_renda",
    "_faixa_labels",
    "_icone_rede",
    "_icone_ultra",
    "_carregar_concorrentes",
    "_carregar_ultra_pontos",
    "bairros_por_hex",
    "_base_calibracao",
    "_carregar_growth",
    "_ultra_coord_map",
]


def _clear_caches() -> None:
    for nome in _CACHED:
        fn = getattr(pilot, nome, None)
        if fn is not None and hasattr(fn, "cache_clear"):
            fn.cache_clear()


def _point_app_at(monkeypatch: pytest.MonkeyPatch, data_dir: Path) -> None:
    """Reaponta os globais de caminho do app (restaurados pelo monkeypatch) e limpa caches."""
    data_dir = Path(data_dir)
    outputs = data_dir / "outputs"
    staging = data_dir / "staging"
    monkeypatch.setattr(pilot, "DATA_DIR", data_dir)
    monkeypatch.setattr(pilot, "OUTPUTS_DIR", outputs)
    monkeypatch.setattr(pilot, "STAGING_DIR", staging)
    monkeypatch.setattr(pilot, "IBGE_DIR", data_dir / "ibge")
    monkeypatch.setattr(pilot, "ULTRA_DIR", data_dir / "ultra")
    monkeypatch.setattr(pilot, "CENSO_GEO_DIR", outputs / "setores_censitarios_2022_geo")
    monkeypatch.setattr(pilot, "ENRICHED_DIR", outputs / "hexagonos_dashboard_enriquecido")
    monkeypatch.setattr(pilot, "CONCORRENTES_PARQUET", staging / "concorrentes_mapeados.parquet")
    monkeypatch.setattr(pilot, "ULTRA_PERF_PARQUET", staging / "unidades_ultra_performance_hex.parquet")
    monkeypatch.setattr(pilot, "GROWTH_PARQUET", staging / "growth_api_historico.parquet")
    monkeypatch.setattr(pilot, "GEOCODE_CACHE_DIR", data_dir / "cache" / "geocode")
    _clear_caches()


@pytest.fixture
def empty_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """App apontado para um data_dir VAZIO (sem parquets) — reproduz o CI."""
    _point_app_at(monkeypatch, tmp_path)
    yield tmp_path
    _clear_caches()


def _synthetic_enriched() -> pd.DataFrame:
    """Dataset minimo: 2 municipios em SP, valores que acendem o funil de 4 passos."""
    rows: list[dict[str, object]] = []
    munis = [("Sao Paulo", "3550308"), ("Campinas", "3509502")]
    for mi, (nome, cod) in enumerate(munis):
        for h in range(4):
            rows.append(
                {
                    "hex_id": f"87a{mi}{h}0000000ffff",
                    "lat": -23.55 + 0.01 * mi + 0.001 * h,
                    "lng": -46.63 + 0.01 * mi + 0.001 * h,
                    "nome_municipio": nome,
                    "cod_municipio": cod,
                    "score_priorizacao": 80.0 + h,
                    "score_setor_2022_calibrado": 75.0 + h,  # >=70 acende o passo 1
                    "score_expansao_hibrido": 70.0 + h,
                    "score_oportunidade_residual": 5000.0 + 100 * h,
                    "oferta_efetiva_disponivel": 3000.0 + 500 * h,  # >=2000 acende o passo 2
                    "oferta_consumida_mercado_estimada": 2500.0 * h,  # h=0 -> white space
                    "sam_fitness_potencial": 4000.0 + h,
                    "populacao_corte_hex": 8000.0 + 100 * h,  # >=5000
                    "pop_total": 8000.0 + 100 * h,
                    "pop_total_setor_2022": 8000.0 + 100 * h,
                    "renda_per_capita": 2500.0 + 10 * h,
                    "renda_per_capita_setor_2022_calibrada": 2600.0 + 10 * h,
                    "faixa_oportunidade": "alta",
                    "n_unidades_ultra_performance_hex": h % 2,
                    "capacidade_default_concorrente_alunos": 2500.0,
                    "densidade_pop_setor_hab_km2": 5000.0,
                }
            )
    return pd.DataFrame(rows)


@pytest.fixture
def synth_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """App apontado para um data_dir com um enriquecido SINTETICO (UF=SP)."""
    part = tmp_path / "outputs" / "hexagonos_dashboard_enriquecido" / "uf=SP"
    part.mkdir(parents=True)
    _synthetic_enriched().to_parquet(part / "part-0.parquet")  # escrita do TESTE, nao do app
    _point_app_at(monkeypatch, tmp_path)
    yield tmp_path
    _clear_caches()


# ===========================================================================
# 1) JSON-safe: NaN/inf/None -> None (o payload nunca quebra json.dumps)
# ===========================================================================


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), None, "abc", object()])
def test_num_e_numf_sao_json_safe(bad: object) -> None:
    assert pilot._num(bad) is None
    assert pilot._numf(bad) is None


def test_num_arredonda_e_numf_preserva() -> None:
    assert pilot._num(3.14159, 2) == pytest.approx(3.14)
    assert pilot._num(3.6) == 4
    assert pilot._numf(3.14159) == pytest.approx(3.14159)


# ===========================================================================
# 2) Catalogo de rotas — nenhuma rota some por acidente
# ===========================================================================


def test_todas_as_rotas_registradas() -> None:
    paths = {getattr(r, "path", None) for r in pilot.app.routes}
    esperadas = {
        "/api/health",
        "/api/ufs",
        "/api/geocode",
        "/api/municipios/{uf}",
        "/api/uf/{uf}",
        "/api/municipio/{uf}/{municipio}",
        "/api/faixa-alunos",
        "/api/viabilidade",
        "/api/executiva/{uf}",
        "/api/relatorio/municipal",
        "/api/relatorio/pontual",
    }
    assert esperadas <= paths


# ===========================================================================
# 3) Contrato de cada endpoint em degradacao graciosa (SEM parquets = CI)
# ===========================================================================


def test_health_contrato(empty_data: Path) -> None:
    h = pilot.health()
    assert h["status"] == "ok"
    assert h["data_ok"] is False
    assert h["data_dir"] == str(empty_data)


def test_ufs_sem_base_levanta_500(empty_data: Path) -> None:
    with pytest.raises(HTTPException) as e:
        pilot.ufs()
    assert e.value.status_code == 500


@pytest.mark.parametrize(
    "chamada",
    [
        lambda: pilot.municipios("SP"),
        lambda: pilot.uf_view("SP"),
        lambda: pilot.municipio("SP", "Qualquer"),
    ],
)
def test_rotas_uf_sem_particao_levantam_404(empty_data: Path, chamada) -> None:
    with pytest.raises(HTTPException) as e:
        chamada()
    assert e.value.status_code == 404


@pytest.mark.parametrize("q", ["", "ab"])
def test_geocode_curto_nao_bate_na_rede(empty_data: Path, q: str) -> None:
    # termos < 3 chars retornam sem tocar a rede (Nominatim) — seguro no CI.
    assert pilot.geocode(q) == {"found": False}


def test_faixa_alunos_sem_base_degrada(empty_data: Path) -> None:
    assert pilot.faixa_alunos(m2=1500) == {"p10": None, "p50": None, "p90": None, "n_comparaveis": 0}


def test_executiva_sem_growth_levanta_404(empty_data: Path) -> None:
    with pytest.raises(HTTPException) as e:
        pilot.executiva("SP")
    assert e.value.status_code == 404


def test_relatorio_municipal_sem_dados_levanta_httpexception(empty_data: Path) -> None:
    with pytest.raises(HTTPException):
        pilot.relatorio_municipal(pilot.RelatorioMunicipalIn(uf="SP", municipio="X"))


def test_relatorio_pontual_sem_geo_levanta_404(empty_data: Path) -> None:
    with pytest.raises(HTTPException) as e:
        asyncio.run(pilot.relatorio_pontual(lat=-23.5, lng=-46.6))
    assert e.value.status_code == 404


def test_viabilidade_contrato_e_json_safe(empty_data: Path) -> None:
    # A viabilidade roda pela calibracao INTERNA do motor (base=None): sem parquets.
    body = pilot.viabilidade(
        pilot.ViabilidadeIn(
            lat=-23.5,
            lng=-46.6,
            m2=1500,
            aluguel=30000,
            demanda=1600,
            ticket=177,
            obra=800_000,
            equipamentos=700_000,
        )
    )
    assert {"dre", "fcf_serie", "fco_serie", "aluguel_teto", "grade", "faixa_alunos"} <= set(body)
    # JSON-safe de ponta a ponta: o payload inteiro serializa SEM NaN/inf.
    json.dumps(body, allow_nan=False)

    dre = body["dre"]
    assert {"faturamento", "ebitda", "lucro_liquido", "payback", "roic", "margem"} <= set(dre)
    # Cascata coerente: faturamento - deducoes - impostos - custos == ebitda.
    if all(dre.get(k) is not None for k in ("faturamento", "deducoes", "impostos", "custos", "ebitda")):
        recomposto = dre["faturamento"] - dre["deducoes"] - dre["impostos"] - dre["custos"]
        assert recomposto == pytest.approx(dre["ebitda"], abs=0.05)
    # fcf_serie (payback) parte NEGATIVO (-(investimento)); fco_serie comeca no mes 1.
    assert body["fcf_serie"] and body["fcf_serie"][0]["fcf"] < 0
    assert body["fco_serie"] and body["fco_serie"][0]["mes"] == 1


# ===========================================================================
# 4) Guardrail READ-ONLY ESTATICO (AST) — nenhum escritor de artefato/destruicao
# ===========================================================================

# Escritores de DataFrame para DISCO (o vetor de escrita de artefato M1). `to_json`
# NAO entra: o backend o usa para gerar STRING (grade.to_json()), sem tocar o disco.
_ESCRITORES_ARTEFATO = {
    "to_parquet",
    "to_csv",
    "to_feather",
    "to_excel",
    "to_hdf",
    "to_pickle",
    "to_sql",
    "to_stata",
    "to_orc",
}
# Operacoes destrutivas de filesystem (nenhuma e usada legitimamente pelo backend).
# `replace`/`move` ficam de fora: `.replace(` e pandas/str legitimo no app.
_FS_DESTRUTIVO = {"rmtree", "rmdir", "unlink", "remove"}


def test_backend_read_only_por_ast() -> None:
    """Prova estrutural (AST) de que o backend nao escreve artefato nem destroi FS."""
    tree = ast.parse((_SERVER / "app.py").read_text(encoding="utf-8"))
    ofensas: list[tuple[str, int]] = []
    proibidos = _ESCRITORES_ARTEFATO | _FS_DESTRUTIVO
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in proibidos:
                ofensas.append((node.func.attr, node.lineno))
    assert not ofensas, f"backend deve ser READ-ONLY sobre o M1; escrita/destruicao encontrada: {ofensas}"


# ===========================================================================
# 5) Guardrail READ-ONLY em RUNTIME — leituras nao mutam nada fora do cache
# ===========================================================================


def _snapshot(root: Path) -> dict[str, tuple[int, int]]:
    """(caminho relativo -> mtime_ns, size) de cada arquivo, ignorando `cache/`."""
    snap: dict[str, tuple[int, int]] = {}
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if "cache" in rel.parts:  # geocode/basemap sao caches legitimos
            continue
        st = p.stat()
        snap[str(rel)] = (st.st_mtime_ns, st.st_size)
    return snap


def test_leituras_nao_mutam_artefatos(synth_data: Path) -> None:
    """Exercita os endpoints de leitura sobre dado real e prova, por snapshot do FS,
    que nenhum artefato foi escrito/alterado — a rede de seguranca do M1."""
    antes = _snapshot(synth_data)

    assert pilot.ufs()["ufs"] == ["SP"]
    munis = pilot.municipios("SP")
    assert munis["uf"] == "SP"
    assert len(munis["municipios"]) == 2

    uf = pilot.uf_view("SP")
    assert uf["nivel"] == "uf"
    assert uf["hexes"]  # dado real fluiu (o guardrail nao e no-op)

    m = pilot.municipio("SP", "Sao Paulo")
    assert m["nivel"] == "municipio"
    assert m["hexes"]
    assert m["passos"][0]["itens"]  # funil acendeu com o dado sintetico

    # Todos os payloads sao JSON-safe de ponta a ponta.
    for payload in (munis, uf, m):
        json.dumps(payload, allow_nan=False)

    depois = _snapshot(synth_data)
    assert antes == depois, "backend escreveu/alterou artefato fora do cache durante leituras"
