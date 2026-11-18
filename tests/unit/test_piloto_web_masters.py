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

import asyncio
import dataclasses
import io
import json
import os
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


# ---------------------------------------------------------------------------
# O relatório em PDF (BLK-MASTERS-04)
# ---------------------------------------------------------------------------

CONFIG_MASTERS = {
    "masters": [
        {
            "id": "rjsp",
            "nome_planilha": "RJ/SP 01 — Fulano",
            "nome_exibicao": "RJ/SP 01",
            "regioes": [
                {"id": "rj", "nome": "Rio de Janeiro", "ufs": ["RJ"]},
                {"id": "sp", "nome": "São Paulo", "ufs": ["SP"]},
            ],
        },
        {
            "id": "sp03",
            "nome_planilha": "SP 03 — Beltrano",
            "nome_exibicao": "SP 03",
            "regioes": [{"id": "sp", "nome": "São Paulo", "ufs": ["SP"]}],
        },
    ]
}
FONTES_DO_RELATORIO = (
    ("UNI_DIM_PARQUET", "dim_unidade.parquet"),
    ("UNI_FATO_PARQUET", "fato_unidade_mes.parquet"),
    ("MERCADO_PARQUET", "hexagonos_mercado_mapeado.parquet"),
    ("CONCORRENTES_PARQUET", "concorrentes_mapeados.parquet"),
    ("ULTRA_MAPEADAS_PARQUET", "unidades_ultra_mapeadas.parquet"),
)


@pytest.fixture
def relatorio(masters: Path, monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """O piloto com tudo o que o relatório pede na staging e o GERADOR trocado por um falso: aqui
    se confere a rota (área, cache, 404, gate); o PDF em si tem os testes dele."""
    from motor_expansao.masters import gerar as G

    territorios = masters / ingestao.ARQ_TERRITORIOS
    territorios.write_text(json.dumps(CONFIG_MASTERS, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(pilot, "MASTERS_TERRITORIOS", territorios)
    for constante, nome in FONTES_DO_RELATORIO:
        (masters / nome).write_bytes(b"x")
        monkeypatch.setattr(pilot, constante, masters / nome)
    chamadas: list[dict[str, Any]] = []

    def falso(e: Any, master: Any, gerado_em: Any, regiao_id: Any = None, planilha: Any = None):
        chamadas.append(
            {"master": master.id, "regiao": regiao_id, "dia": gerado_em, "planilha": planilha}
        )
        return b"%PDF-falso", f"relatorio_master_{master.id}_{regiao_id}.pdf"

    monkeypatch.setattr(G, "pdf_do_master", falso)
    pilot.limpar_caches()
    yield chamadas
    pilot.limpar_caches()


def _pedir(master_id: str, regiao: str | None = None) -> Any:
    return asyncio.run(pilot.api_master_relatorio(master_id, regiao=regiao, remote_user=None))


def test_relatorio_de_uma_area_do_master(relatorio: list[dict[str, Any]]) -> None:
    r = _pedir("rjsp", "sp")
    assert r.media_type == "application/pdf" and r.body == b"%PDF-falso"
    assert r.headers["content-disposition"] == 'attachment; filename="relatorio_master_rjsp_sp.pdf"'
    (c,) = relatorio
    assert (c["master"], c["regiao"], c["dia"]) == ("rjsp", "sp", HOJE)
    # A planilha chega ao gerador pelo nome que ela usa, remontada da ingestão.
    inaug, pipe = c["planilha"]
    assert set(inaug["master_secao"]) == {"RJ/SP 01 — Fulano", "SP 03 — Beltrano"}
    assert set(pipe["master"]) == {"RJ/SP 01 — Fulano"}


def test_relatorio_fica_em_cache_ate_uma_fonte_mudar(relatorio: list[dict[str, Any]]) -> None:
    _pedir("rjsp", "rj")
    _pedir("rjsp", "rj")
    assert len(relatorio) == 1
    # Painel de unidades novo na staging (a cópia do mês): gera de novo.
    dim = pilot.UNI_DIM_PARQUET
    os.utime(dim, ns=(dim.stat().st_atime_ns, dim.stat().st_mtime_ns + 10**9))
    _pedir("rjsp", "rj")
    assert len(relatorio) == 2


def test_relatorio_responde_404_dizendo_o_que_falta(relatorio: list[dict[str, Any]]) -> None:
    assert _status(lambda: _pedir("zeta")) == (404, "Master não encontrado.")
    assert _status(lambda: _pedir("sp03", "rj")) == (404, "Área não encontrada para este master.")
    pilot.UNI_FATO_PARQUET.unlink()
    status, detalhe = _status(lambda: _pedir("rjsp", "sp"))
    assert status == 404 and "fato_unidade_mes.parquet" in detalhe
    assert relatorio == []


def test_relatorio_tem_o_gate_da_tela(monkeypatch: pytest.MonkeyPatch) -> None:
    caminho = "/api/masters/relatorio/rjsp"
    assert acesso.capacidade_necessaria(caminho, "GET") == "masters.ver"
    _identidade(monkeypatch, {"rede.ver"})
    assert acesso.motivo_bloqueio_por_banco(caminho, "GET", "alguem") is not None


def test_botao_unico_entrega_um_pdf_por_area_num_zip(relatorio: list[dict[str, Any]]) -> None:
    """Sem `regiao` (o botão único da tela): master com duas ou mais áreas recebe um .zip com um
    PDF por área; com uma área só, o PDF dela (18/11/2026, Juan: "deixe apenas um botão só")."""
    import zipfile

    r = _pedir("rjsp")
    assert r.media_type == "application/zip"
    assert (
        r.headers["content-disposition"]
        == 'attachment; filename="relatorios_master_rjsp_2026T4_novo.zip"'
    )
    with zipfile.ZipFile(io.BytesIO(r.body)) as zf:
        assert zf.namelist() == ["relatorio_master_rjsp_rj.pdf", "relatorio_master_rjsp_sp.pdf"]
        assert zf.read("relatorio_master_rjsp_sp.pdf") == b"%PDF-falso"
    assert [c["regiao"] for c in relatorio] == ["rj", "sp"]

    um = _pedir("sp03")
    assert um.media_type == "application/pdf"
    assert relatorio[-1]["regiao"] is None


# ---------------------------------------------------------------------------
# O mapa do território no painel (BLK-MASTERS-04; 18/11/2026, Juan: "o mapa, assim como está na
# carteira, com a área e a opção de ligar a renda e a densidade")
# ---------------------------------------------------------------------------


def _hex(lat: float, lng: float) -> str:
    import h3

    return str(h3.latlng_to_cell(lat, lng, 7))


RIO, SAMPA, INTERIOR, VAZIO = (
    _hex(-22.90, -43.20),
    _hex(-23.55, -46.63),
    _hex(-22.90, -47.06),
    _hex(-21.20, -47.80),
)


@pytest.fixture
def mapa(masters: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, list[str]]:
    """Territórios, mercado e Ultra mínimos na staging; a partição da UF e a renda do hexágono
    trocadas por falsas (a conta da renda tem os testes dela; aqui se confere a rota)."""
    territorios = masters / ingestao.ARQ_TERRITORIOS
    territorios.write_text(json.dumps(CONFIG_MASTERS, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(pilot, "MASTERS_TERRITORIOS", territorios)
    mercado = masters / "hexagonos_mercado_mapeado.parquet"
    pd.DataFrame(
        {
            "uf": ["RJ", "SP", "SP", "SP", "MG"],
            "nome_municipio": ["Rio de Janeiro", "São Paulo", "Campinas", "Ribeirão Preto", "BH"],
            "hex_id": [RIO, SAMPA, INTERIOR, VAZIO, _hex(-19.9, -43.9)],
            "lat": [-22.90, -23.55, -22.90, -21.20, -19.9],
            "lng": [-43.20, -46.63, -47.06, -47.80, -43.9],
            # Hexágono sem gente fica fora, como no mapa do relatório em PDF.
            "pop_hex_base": [9000.0, 12000.0, 3000.0, 0.0, 5000.0],
            "outra_coluna": [1, 2, 3, 4, 5],
        }
    ).to_parquet(mercado)
    monkeypatch.setattr(pilot, "MERCADO_PARQUET", mercado)
    ultra = masters / "unidades_ultra_mapeadas.parquet"
    pd.DataFrame(
        {
            "ultra_id": ["u1", "u2", "u3"],
            "unidade": ["Tijuca", "Paulista", "Savassi"],
            "uf": ["RJ", "SP", "MG"],
            "lat": [-22.90, -23.55, -19.9],
            "lng": [-43.20, -46.63, -43.9],
            "hex_id_res7": [RIO, SAMPA, _hex(-19.9, -43.9)],
            "flag_coord_valida": [True, True, True],
        }
    ).to_parquet(ultra)
    monkeypatch.setattr(pilot, "ULTRA_MAPEADAS_PARQUET", ultra)
    monkeypatch.setattr(pilot, "_icone_ultra", lambda: "data:image/png;base64,eA==")
    lidas: list[str] = []

    def carregar_uf(uf: str) -> pd.DataFrame:
        lidas.append(uf)
        if uf == "RJ":
            raise HTTPException(404, "Partição da UF RJ não encontrada.")
        return pd.DataFrame(
            {
                "hex_id": [SAMPA, INTERIOR, VAZIO],
                "renda_teste": [6100.4, None, 2000.0],
                "densidade_pop_setor_hab_km2": [8123.46, 310.0, 2.0],
            }
        )

    monkeypatch.setattr(pilot, "carregar_uf", carregar_uf)
    monkeypatch.setattr(pilot, "_renda_domiciliar_hex", lambda r: r.get("renda_teste"))
    pilot.limpar_caches()
    yield {"lidas": lidas}
    pilot.limpar_caches()


def _json(resposta: Any) -> Any:
    return json.loads(resposta.body)


def test_mapa_mostra_o_territorio_por_regiao_com_a_cor_do_pdf(mapa: dict[str, Any]) -> None:
    from motor_expansao.masters.mapa import CORES_REGIAO

    d = _json(pilot.api_master_mapa("rjsp"))
    assert d["regioes"] == [
        {"id": "rj", "nome": "Rio de Janeiro", "cor": CORES_REGIAO[0]},
        {"id": "sp", "nome": "São Paulo", "cor": CORES_REGIAO[1]},
    ]
    # Só os povoados das UFs do master, cada um com o índice da região dele.
    assert sorted(d["hexes"]) == sorted([[RIO, 0], [SAMPA, 1], [INTERIOR, 1]])
    # Só as Ultra dentro do território, com o nome para a dica.
    assert sorted(u[2] for u in d["ultra"]) == ["Paulista", "Tijuca"]
    assert d["bbox"] == [-47.06, -23.55, -43.2, -22.9]
    assert d["icone_ultra"].startswith("data:image/png")
    # O master de uma área só vê a dele.
    assert sorted(h for h, _ in _json(pilot.api_master_mapa("sp03"))["hexes"]) == sorted(
        [SAMPA, INTERIOR]
    )


def test_camadas_usam_a_renda_e_a_densidade_do_mapa_do_motor(mapa: dict[str, Any]) -> None:
    d = _json(pilot.api_master_mapa_camadas("rjsp"))
    assert d["disponivel"] is True
    # A renda arredondada a reais e a densidade a uma casa; sem leitura vai None (cinza na tela).
    # O hexágono sem gente não entra, e a UF sem partição (RJ) fica sem leitura, sem derrubar.
    assert sorted(d["hexes"]) == sorted([[SAMPA, 6100.0, 8123.5], [INTERIOR, None, 310.0]])
    assert sorted(mapa["lidas"]) == ["RJ", "SP"]
    # As faixas são as da ficha da carteira (a régua do núcleo).
    from motor_expansao.dashboard import constants as C

    assert d["faixas"] == {
        "renda_domiciliar": pilot._faixas_camada(C.RENDA_MEDIA_DOMICILIAR_BANDS),
        "densidade": pilot._faixas_camada(C.DENSIDADE_POP_BANDS),
    }


def test_mapa_fica_em_cache_ate_uma_fonte_mudar(mapa: dict[str, Any]) -> None:
    pilot.api_master_mapa_camadas("rjsp")
    pilot.api_master_mapa_camadas("rjsp")
    assert len(mapa["lidas"]) == 2  # RJ e SP, uma vez
    m = pilot.MERCADO_PARQUET
    os.utime(m, ns=(m.stat().st_atime_ns, m.stat().st_mtime_ns + 10**9))
    pilot.api_master_mapa_camadas("rjsp")
    assert len(mapa["lidas"]) == 4


def test_mapa_responde_404_dizendo_o_que_falta(mapa: dict[str, Any]) -> None:
    assert _status(lambda: pilot.api_master_mapa("zeta")) == (404, "Master não encontrado.")
    pilot.MASTERS_TERRITORIOS.unlink()
    status, detalhe = _status(lambda: pilot.api_master_mapa("rjsp"))
    assert status == 404 and "masters_territorios.json" in detalhe
    status, detalhe = _status(lambda: pilot.api_master_mapa_camadas("rjsp"))
    assert status == 404 and "masters_territorios.json" in detalhe


@pytest.mark.parametrize("caminho", ["/api/masters/rjsp/mapa", "/api/masters/rjsp/mapa/camadas"])
def test_mapa_tem_o_gate_da_tela(monkeypatch: pytest.MonkeyPatch, caminho: str) -> None:
    assert acesso.capacidade_necessaria(caminho, "GET") == "masters.ver"
    assert acesso.abas_necessarias(caminho) == frozenset({"masters"})
    _identidade(monkeypatch, {"rede.ver"})
    assert acesso.motivo_bloqueio_por_banco(caminho, "GET", "alguem") is not None
