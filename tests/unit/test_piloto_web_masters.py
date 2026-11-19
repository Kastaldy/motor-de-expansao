"""Tela Masters do piloto (DEC-089): `GET /api/masters` e `GET /api/masters/{id}`.

Trava, do lado do servidor:

* a lista e o painel saem dos parquets da ingestão (`scripts/ingerir_masters.py`) com as datas
  de inauguração da base do Growth, casadas pela chave do próprio piloto (`_chave_unidade`);
* sem ingestão (ou com o esquema de outra versão) a rota responde 404 dizendo o que falta;
* o gate: só `masters.ver` (growth e lideres, migration 026) entra; a capacidade e a aba são
  sensíveis (fail-closed e curinga não as dão); o perfil `master` e a Consultoria ficam de fora;
  a superfície só existe no perfil BR.

Chama as rotas DIRETO (sem TestClient), como o resto da suíte do piloto.
"""

from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from fastapi import HTTPException

_REPO = Path(__file__).resolve().parents[2]
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import acesso  # noqa: E402
import app as pilot  # noqa: E402

from motor_expansao.db import rbac  # noqa: E402
from motor_expansao.masters import ingestao  # noqa: E402
from tests.unit.test_piloto_web_rede import _base_sintetica  # noqa: E402

HOJE = pd.Timestamp("2026-11-18")


def _tabelas(esquema: int = ingestao.ESQUEMA) -> ingestao.Tabelas:
    contratos = pd.DataFrame(
        [
            {
                "master_id": "rjsp",
                "nome": "Master Um",
                "territorio": "RJ/SP 01",
                "tipo_area": "A definir",
                "regioes": ["Rio de Janeiro"],
                "regioes_tipos": ["A definir"],
                "nota": None,
                "meta_quantidade": None,
                "meta_por_ano": 4,
                "meta_prazo": "2027-01-31",
                "conta_tambem": [],
                "ordem": 0,
            },
            {
                "master_id": "sp03",
                "nome": "Master Dois",
                "territorio": "SP 03",
                "tipo_area": "Exclusividade",
                "regioes": ["São Paulo"],
                "regioes_tipos": ["Exclusividade"],
                "nota": None,
                "meta_quantidade": 3,
                "meta_por_ano": None,
                "meta_prazo": None,
                "conta_tambem": [],
                "ordem": 1,
            },
        ]
    )
    contratos["meta_quantidade"] = contratos["meta_quantidade"].astype("Int64")
    contratos["meta_por_ano"] = contratos["meta_por_ano"].astype("Int64")
    inauguradas = pd.DataFrame(
        [
            ("rjsp", "Botafogo", "RJ", "rjsp", "rjsp"),
            ("rjsp", "Icaraí", "RJ", "rjsp", "rjsp"),
            ("rjsp", "Bangu", "RJ", "rjsp", "rjsp"),
            ("rjsp", "Rocinha", "RJ", "rjsp", "rjsp"),  # sem par na base do Growth
            ("sp03", "Berrini", "SP", "sp03", "sp03"),
        ],
        columns=list(ingestao.COLUNAS_INAUGURADAS),
    )
    pipeline = pd.DataFrame(
        [
            ("rjsp", "Tijuca", None, "RJ", "Pré Venda", None),
            ("rjsp", "Catete", "Rio de Janeiro", "RJ", "Obras", True),
        ],
        columns=list(ingestao.COLUNAS_PIPELINE),
    )
    manifesto = {
        "esquema": esquema,
        "gerado_em": "2026-11-18T12:00:00+00:00",
        "planilha": {"arquivo": "masters.xlsx", "sha256": "0" * 64, "modificada_em": "2026-11-13"},
        "territorios": {"arquivo": "territorios.json", "sha256": "0" * 64, "versao": "x"},
        "contagens": {"masters": 2, "inauguradas": 5, "pipeline": 2},
    }
    return ingestao.Tabelas(contratos, inauguradas, pipeline, manifesto)


def _apontar(monkeypatch: pytest.MonkeyPatch, staging: Path) -> None:
    monkeypatch.setattr(pilot, "GROWTH_PARQUET", staging / "growth_api_historico.parquet")
    monkeypatch.setattr(pilot, "FATURAMENTO_FINANCEIRO_PARQUET", staging / "sem_planilha.parquet")
    monkeypatch.setattr(pilot, "MASTERS_CONTRATOS_PARQUET", staging / ingestao.ARQ_CONTRATOS)
    monkeypatch.setattr(pilot, "MASTERS_INAUGURADAS_PARQUET", staging / ingestao.ARQ_INAUGURADAS)
    monkeypatch.setattr(pilot, "MASTERS_PIPELINE_PARQUET", staging / ingestao.ARQ_PIPELINE)
    monkeypatch.setattr(pilot, "MASTERS_MANIFESTO", staging / ingestao.ARQ_MANIFESTO)
    monkeypatch.setattr(pilot, "_masters_hoje", lambda: HOJE)


@pytest.fixture
def masters(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    staging = tmp_path / "staging"
    staging.mkdir()
    _base_sintetica().to_parquet(staging / "growth_api_historico.parquet")
    ingestao.gravar(_tabelas(), staging)
    _apontar(monkeypatch, staging)
    pilot.limpar_caches()
    yield staging
    pilot.limpar_caches()


def _status(chamada: Any) -> tuple[int, Any]:
    with pytest.raises(HTTPException) as erro:
        chamada()
    return erro.value.status_code, erro.value.detail


# ---------------------------------------------------------------------------
# As rotas
# ---------------------------------------------------------------------------


def test_lista_um_card_por_master(masters: Path) -> None:
    r = pilot.api_masters()
    json.dumps(r)  # JSON-safe: sem NaN, Timestamp ou numpy
    assert [c["id"] for c in r["masters"]] == ["rjsp", "sp03"]
    rjsp = r["masters"][0]
    assert (rjsp["nome"], rjsp["territorio"]) == ("Master Um", "RJ/SP 01")
    assert rjsp["tipo_area"] == "A definir"
    # Em operação: Botafogo, Icaraí e Bangu (datas do Growth) e Rocinha (sem par).
    assert rjsp["resumo"] == {
        "em_operacao": 4,
        "em_inauguracao": 1,
        "assinados": 1,
        "ano": 2026,
        "abertas_no_ano": 1,
    }
    assert rjsp["meta"]["por_ano"] == 4 and rjsp["meta"]["prazo"] == "2027-01-31"
    assert r["hoje"] == "2026-11-18"
    assert r["fontes"]["planilha_de"] == "2026-11-13"
    assert str(r["fontes"]["growth_ate"]).startswith("2026-07")


def test_painel_do_master_com_as_datas_do_growth(masters: Path) -> None:
    p = pilot.api_master("rjsp")
    json.dumps(p)
    datas = {u["unidade"]: u["inauguracao"] for u in p["em_operacao"]}
    # "ICARAI - RJ" no Growth casa com "Icaraí" da planilha (acento, caixa e sufixo de UF).
    assert datas == {
        "Bangu": "2026-03-01",
        "Icaraí": "2024-06-01",
        "Botafogo": "2021-01-01",
        "Rocinha": None,
    }
    assert [u["unidade"] for u in p["em_operacao"]] == ["Bangu", "Icaraí", "Botafogo", "Rocinha"]
    assert p["em_inauguracao"][0]["unidade"] == "Tijuca"
    assert p["em_inauguracao"][0]["fase"] == "Pré Venda"
    assert p["assinados"] == [
        {
            "fase": "Obras",
            "unidades": [
                {
                    "unidade": "Catete",
                    "cidade": "Rio de Janeiro",
                    "uf": "RJ",
                    "dentro_territorio": True,
                }
            ],
        }
    ]
    meta = p["meta"]
    assert [t["acumulado"] for t in meta["trimestres"]] == [1, 1, 1, 1]
    assert meta["trimestres"][0]["pct"] == 0.25 and meta["pct_ano"] == 0.25
    assert meta["n_contam"] == 4 and meta["sem_data"] == ["Rocinha"]
    assert meta["meses_ate_prazo"] == 2

    sp = pilot.api_master("sp03")
    assert sp["meta"]["pct_contrato"] == pytest.approx(1 / 3)


def test_master_que_nao_existe_e_404(masters: Path) -> None:
    assert _status(lambda: pilot.api_master("zeta")) == (404, "Master não encontrado.")


def test_sem_ingestao_responde_404_dizendo_o_que_falta(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _apontar(monkeypatch, tmp_path)  # pasta vazia
    pilot.limpar_caches()
    status, detalhe = _status(pilot.api_masters)
    assert status == 404 and "ingerir_masters" in detalhe
    assert _status(lambda: pilot.api_master("rjsp"))[0] == 404
    pilot.limpar_caches()


def test_ingestao_de_outro_esquema_nao_e_lida(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ingestao.gravar(_tabelas(esquema=ingestao.ESQUEMA + 1), tmp_path)
    _apontar(monkeypatch, tmp_path)
    pilot.limpar_caches()
    assert _status(pilot.api_masters)[0] == 404
    pilot.limpar_caches()


# ---------------------------------------------------------------------------
# O gate
# ---------------------------------------------------------------------------


def _identidade(monkeypatch: pytest.MonkeyPatch, permissoes: set[str] | None) -> None:
    def falsa(_remote_user: object) -> rbac.Identidade | None:
        if permissoes is None:
            return None
        return rbac.Identidade(
            id_usuario=1,
            login="alguem",
            perfil="teste",
            permissoes=frozenset(permissoes),
            paises=frozenset({"BR"}),
        )

    monkeypatch.setattr(rbac, "identidade", falsa)


@pytest.mark.parametrize("caminho", ["/api/masters", "/api/masters/rjsp"])
def test_so_masters_ver_abre_a_tela(monkeypatch: pytest.MonkeyPatch, caminho: str) -> None:
    assert acesso.capacidade_necessaria(caminho, "GET") == "masters.ver"
    assert acesso.abas_necessarias(caminho) == frozenset({"masters"})
    _identidade(monkeypatch, {"masters.ver"})
    assert acesso.motivo_bloqueio_por_banco(caminho, "GET", "alguem") is None
    # A Visão Executiva inteira (Consultoria) e a do master (025) não abrem a tela Masters.
    for outra in ({"rede.ver", "rede.cadastro_editar"}, {"rede.ver_propria"}):
        _identidade(monkeypatch, outra)
        assert acesso.motivo_bloqueio_por_banco(caminho, "GET", "alguem") is not None


def test_a_tela_e_sensivel(monkeypatch: pytest.MonkeyPatch) -> None:
    assert "masters.ver" in acesso.CAPACIDADES_SENSIVEIS
    assert "masters" in acesso.ABAS_SENSIVEIS
    assert acesso.CAPACIDADE_QUE_SUSTENTA_A_ABA["masters"] == "masters.ver"
    _identidade(monkeypatch, {"masters.ver"})
    assert acesso.abas_do_usuario_por_banco("alguem") == frozenset({"masters"})


def test_a_superficie_so_existe_no_brasil() -> None:
    assert "masters" in pilot.PERFIL.superficies
    assert acesso.motivo_bloqueio_pais("/api/masters", pilot.PERFIL) is None
    sem = dataclasses.replace(pilot.PERFIL, superficies=frozenset({"mapa", "viabilidade"}))
    assert acesso.motivo_bloqueio_pais("/api/masters/rjsp", sem) is not None


def test_a_migration_026_da_a_capacidade_so_a_growth_e_lideres() -> None:
    sql = (_REPO / "src/motor_expansao/db/migracoes/026-permissao-masters.sql").read_text(
        encoding="utf-8"
    )
    assert "('masters.ver'," in sql
    assert "('growth', 'masters.ver')" in sql and "('lideres', 'masters.ver')" in sql
    for fora in ("consultoria", "expansao", "'master'"):
        assert fora not in sql.split("INSERT INTO perfil_permissoes")[1]
