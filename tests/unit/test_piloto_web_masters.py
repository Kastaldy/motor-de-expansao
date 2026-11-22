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


def test_o_master_do_relatorio_unico_recebe_um_pdf_so_com_todas_as_areas(
    relatorio: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """19/11/2026, Juan: "df pode deixar Goiás e DF tudo no mesmo relatório". O master da lista
    recebe o PDF do master inteiro (sem área), mesmo com duas áreas; o painel avisa a tela."""
    assert pilot.MASTERS_RELATORIO_UNICO == frozenset({"dfgo"})
    assert pilot.api_master("rjsp")["relatorio_por_area"] is True
    monkeypatch.setattr(pilot, "MASTERS_RELATORIO_UNICO", frozenset({"rjsp"}))
    r = _pedir("rjsp")
    assert r.media_type == "application/pdf" and r.body == b"%PDF-falso"
    assert [c["regiao"] for c in relatorio] == [None]
    assert pilot.api_master("rjsp")["relatorio_por_area"] is False
    # Uma área só nunca é "por área".
    assert pilot.api_master("sp03")["relatorio_por_area"] is False


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
            "cod_municipio": ["3304557", "3550308", "3509502", "3543402", "3106200"],
            "nome_municipio": ["Rio de Janeiro", "São Paulo", "Campinas", "Ribeirão Preto", "BH"],
            "hex_id": [RIO, SAMPA, INTERIOR, VAZIO, _hex(-19.9, -43.9)],
            "lat": [-22.90, -23.55, -22.90, -21.20, -19.9],
            "lng": [-43.20, -46.63, -47.06, -47.80, -43.9],
            # Hexágono sem gente fica fora, como no mapa do relatório em PDF.
            "pop_hex_base": [9000.0, 12000.0, 3000.0, 0.0, 5000.0],
            # O mercado de cada hexágono (alunos): potencial, consumo de redes e Ultra, livre.
            "sam_fitness_potencial": [1000.0, 2000.0, 600.0, 0.0, 900.0],
            "oferta_consumida_mercado_estimada": [300.0, 900.0, 100.0, 0.0, 100.0],
            "oferta_consumida_ultra_estimada": [100.0, 100.0, 0.0, 0.0, 0.0],
            "oferta_efetiva_disponivel": [600.0, 1000.0, 500.0, 0.0, 800.0],
            # Academias que alcançam o hexágono a 1 km (a camada "concorrentes" do relatório).
            "n_concorrentes_influencia_1km": [2, 5, 0, 0, 1],
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
    # O território vai DEMARCADO (19/11/2026, Juan): um contorno por região, a união dos
    # hexágonos dela (todos, e não só os povoados), com anéis fechados em [lng, lat].
    assert sorted(c["regiao"] for c in d["contornos"]) == [0, 1]
    for c in d["contornos"]:
        for poligono in c["poligonos"]:
            anel = poligono[0]
            assert len(anel) >= 6 and anel[0] == anel[-1]
            assert all(-48 < lng < -43 and -24 < lat < -21 for lng, lat in anel)
    # Os municípios do território (com a caixa de cada um), para os setores ao aproximar.
    assert [m[:3] for m in d["municipios"]] == [
        ["RJ", "3304557", "Rio de Janeiro"],
        ["SP", "3509502", "Campinas"],
        ["SP", "3543402", "Ribeirão Preto"],
        ["SP", "3550308", "São Paulo"],
    ]
    assert d["n_hexes"] == 3  # os povoados
    # Só as Ultra dentro do território, com o nome para a dica.
    assert sorted(u[2] for u in d["ultra"]) == ["Paulista", "Tijuca"]
    assert d["bbox"] == [-47.8, -23.55, -43.2, -21.2]
    assert d["icone_ultra"].startswith("data:image/png")
    # O master de uma área só vê a dele.
    assert [c["regiao"] for c in _json(pilot.api_master_mapa("sp03"))["contornos"]] == [0]


def test_as_camadas_sao_so_renda_e_densidade_do_censo(mapa: dict[str, Any]) -> None:
    """Renda e densidade, sempre do Censo (19/11/2026, Juan: "deixe o padrão sempre censitário"),
    com as faixas do núcleo; espaço livre e concorrentes saíram ("a camada de espaço livre e
    academias concorrentes não precisa ter"). Nada lê a partição da UF."""
    from motor_expansao.dashboard import constants as C

    d = _json(pilot.api_master_mapa_camadas("rjsp"))
    assert d == {
        "faixas": {
            "renda_domiciliar": pilot._faixas_camada(C.RENDA_MEDIA_DOMICILIAR_BANDS),
            "densidade": pilot._faixas_camada(C.DENSIDADE_POP_BANDS),
        }
    }
    assert mapa["lidas"] == []


def test_mapa_fica_em_cache_ate_uma_fonte_mudar(
    mapa: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    lidos: list[tuple[str, str]] = []

    def setores(uf: str, cod: str) -> list[tuple[Any, Any, Any]]:
        lidos.append((uf, cod))
        return []

    monkeypatch.setattr(pilot, "_setores_do_municipio_no_territorio", setores)
    pilot.api_master_setores("rjsp")
    pilot.api_master_setores("rjsp")
    assert len(lidos) == 4  # os quatro municípios do território, uma vez
    m = pilot.MERCADO_PARQUET
    os.utime(m, ns=(m.stat().st_atime_ns, m.stat().st_mtime_ns + 10**9))
    pilot.api_master_setores("rjsp")
    assert len(lidos) == 8


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


# ---------------------------------------------------------------------------
# O "Onde expandir" da aba Expansão (BLK-MASTERS-04; 18/11/2026, Juan: "a recomendação, igual
# está no relatório, para onde expandir")
# ---------------------------------------------------------------------------

ESTUDO_FALSO = {
    "analise": [{"cor": "magenta", "titulo": "Ocupação do mercado", "texto": "..."}],
}


@pytest.fixture
def estudo(relatorio: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """O piloto com o que o relatório pede e o estudo trocado por um falso (as regras dele são as
    do PDF e têm os testes de lá); aqui se confere a rota."""
    from motor_expansao.masters import gerar as G

    chamadas: list[str] = []

    def falso(e: Any, master: Any, gerado_em: Any, planilha: Any = None) -> dict[str, Any]:
        chamadas.append(master.id)
        assert planilha is not None  # a planilha chega remontada da ingestão, nunca a crua
        return ESTUDO_FALSO

    monkeypatch.setattr(G, "estudo_do_master", falso)
    return chamadas


def _estudo(master_id: str) -> Any:
    return asyncio.run(pilot.api_master_estudo(master_id))


def test_estudo_da_aba_expansao_vem_do_gerador_do_relatorio(estudo: list[str]) -> None:
    assert _json(_estudo("rjsp")) == ESTUDO_FALSO
    _estudo("rjsp")
    assert estudo == ["rjsp"]  # em cache até uma fonte mudar
    m = pilot.MERCADO_PARQUET
    os.utime(m, ns=(m.stat().st_atime_ns, m.stat().st_mtime_ns + 10**9))
    _estudo("rjsp")
    assert estudo == ["rjsp", "rjsp"]


def test_estudo_responde_404_dizendo_o_que_falta(estudo: list[str]) -> None:
    assert _status(lambda: _estudo("zeta")) == (404, "Master não encontrado.")
    pilot.UNI_DIM_PARQUET.unlink()
    status, detalhe = _status(lambda: _estudo("rjsp"))
    assert status == 404 and "dim_unidade.parquet" in detalhe
    assert estudo == []


def test_estudo_tem_o_gate_da_tela(monkeypatch: pytest.MonkeyPatch) -> None:
    caminho = "/api/masters/rjsp/estudo"
    assert acesso.capacidade_necessaria(caminho, "GET") == "masters.ver"
    _identidade(monkeypatch, {"rede.ver"})
    assert acesso.motivo_bloqueio_por_banco(caminho, "GET", "alguem") is not None


# ---------------------------------------------------------------------------
# Top 5 pela régua do motor e o crescimento (18/11/2026, Juan: "no top 5, mudar para o padrão do
# motor, que é Mata Virgem e Premium, e embaixo a opção de mostrar o top 20"; "a primeira linha,
# troque por quanto ele pode crescer na região, mostrando o residual, espaços para academias")
# ---------------------------------------------------------------------------


def test_recomendacao_e_a_do_motor_no_territorio_com_20_vagas(
    mapa: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    chamadas: list[dict[str, Any]] = []

    def bloco(df: pd.DataFrame, recorte: Any, *, regra: Any) -> dict[str, Any]:
        chamadas.append({"hexes": sorted(df["hex_id"]), "recorte": recorte, "regra": regra})
        return {"mata_virgem": {"vagas": []}, "premium": {"vagas": []}}

    monkeypatch.setattr(pilot, "_bloco_recomendacao", bloco)
    d = _json(pilot.api_master_recomendacao("rjsp"))
    assert d == {"recomendacao": {"mata_virgem": {"vagas": []}, "premium": {"vagas": []}}}
    (c,) = chamadas
    # Só os hexágonos do território (a UF sem partição, RJ, fica fora; o sem gente também).
    assert c["hexes"] == sorted([SAMPA, INTERIOR])
    # A régua vigente do país, só com 20 vagas por segmento (a tela mostra 5 e abre as 20).
    vigente = pilot._regra_recomendacao()
    assert c["regra"].vagas_por_segmento == 20
    assert c["regra"].versao == vigente.versao and c["regra"].premium == vigente.premium
    # O território atravessa UFs: vai como recorte "brasil" já filtrado (a régua não usa o nível).
    assert c["recorte"].nivel == "brasil" and "RJ/SP 01" in c["recorte"].nome
    pilot.api_master_recomendacao("rjsp")
    assert len(chamadas) == 1  # em cache até uma fonte mudar


def test_crescimento_soma_o_mercado_do_territorio_por_regiao(mapa: dict[str, Any]) -> None:
    d = _json(pilot.api_master_crescimento("rjsp"))
    assert d["capacidade_por_academia"] == 2500.0
    # Só os hexágonos das UFs do master (o de MG fica fora); RJ e SP por região.
    assert d["total"] == {
        "mercado_alunos": 3600.0,
        "atendido_alunos": 1500.0,
        "pct_atendido": round(1500 / 3600, 4),
        "espaco_livre_alunos": 2100.0,
        "academias_que_cabem": 0,
    }
    por_regiao = {r["id"]: r for r in d["regioes"]}
    assert por_regiao["rj"]["espaco_livre_alunos"] == 600.0
    assert por_regiao["sp"]["espaco_livre_alunos"] == 1500.0
    assert por_regiao["sp"]["pct_atendido"] == round(
        1100 / 2600, 4
    )  # 900 + 100 de redes, 100 Ultra


@pytest.mark.parametrize(
    "caminho", ["/api/masters/rjsp/recomendacao", "/api/masters/rjsp/crescimento"]
)
def test_recomendacao_e_crescimento_tem_o_gate_da_tela(
    monkeypatch: pytest.MonkeyPatch, caminho: str
) -> None:
    assert acesso.capacidade_necessaria(caminho, "GET") == "masters.ver"
    _identidade(monkeypatch, {"rede.ver"})
    assert acesso.motivo_bloqueio_por_banco(caminho, "GET", "alguem") is not None


def test_renda_e_densidade_sao_os_setores_do_territorio_inteiro_em_qualquer_zoom(
    mapa: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """19/11/2026, Juan: "deixe a densidade e a renda (quando ativadas) aparecendo sem limite de
    zoom". Os POLÍGONOS dos setores de todos os municípios do território, numa resposta só
    (antes, de longe, ia um ponto por setor, e os polígonos só no zoom de cidade): uma linha
    `[renda, densidade, anéis]` por peça, com o buraco do setor e as coordenadas em 5 casas."""
    from shapely.geometry import Polygon, box

    furado = Polygon(
        [(-46.7, -23.6), (-46.6, -23.6), (-46.6, -23.5), (-46.7, -23.5)],
        holes=[[(-46.68, -23.58), (-46.62, -23.58), (-46.62, -23.52), (-46.68, -23.52)]],
    )
    por_municipio = {
        ("RJ", "3304557"): [(box(-43.2, -22.9, -43.1, -22.8), 9000.0, 12000.0)],
        ("SP", "3550308"): [
            (furado, 6101.0, 8123.5),
            (box(-46.6, -23.6, -46.5000012, -23.5), None, 900.0),
        ],
    }
    lidos: list[tuple[str, str]] = []

    def setores(uf: str, cod: str) -> list[tuple[Any, Any, Any]]:
        lidos.append((uf, cod))
        return por_municipio.get((uf, cod), [])

    monkeypatch.setattr(pilot, "_setores_do_municipio_no_territorio", setores)
    d = _json(pilot.api_master_setores("rjsp"))
    assert [(renda, densidade) for renda, densidade, _ in d["setores"]] == [
        (9000.0, 12000.0),
        (6101.0, 8123.5),
        (None, 900.0),
    ]
    assert [len(aneis) for _, _, aneis in d["setores"]] == [1, 2, 1]  # o buraco fica
    coords = [c for _, _, aneis in d["setores"] for a in aneis for p in a for c in p]
    assert all(c == round(c, 5) for c in coords)
    # Os quatro municípios do território, e só eles: BH (de outro estado) não é lido.
    assert sorted(lidos) == [
        ("RJ", "3304557"),
        ("SP", "3509502"),
        ("SP", "3543402"),
        ("SP", "3550308"),
    ]
    # O master de uma área só lê os setores da dele.
    assert len(_json(pilot.api_master_setores("sp03"))["setores"]) == 2
    assert _status(lambda: pilot.api_master_setores("zeta")) == (404, "Master não encontrado.")


def test_os_setores_do_territorio_seguem_encaixados_depois_de_simplificar() -> None:
    """Simplificar setor a setor abria frestas entre vizinhos (prévia de 19/11/2026; no DF/GO,
    36.688 buracos na união dos setores). Como COBERTURA, a borda comum sai igual nos dois: o
    rio entre dois setores rurais grandes some dos dois de uma vez, o dente de 22 m do setor
    urbano pequeno fica, e a divisa do rural com o urbano não se mexe."""
    import shapely
    from shapely.geometry import Polygon

    # Dois rurais de 11 km de lado; a divisa entre eles faz uma curva de 5 m (some na 2ª passada).
    rural_a = Polygon(
        [(-48.0, -16.0), (-47.9, -16.0), (-47.89995, -15.95), (-47.9, -15.9), (-48.0, -15.9)]
    )
    rural_b = Polygon(
        [
            (-47.9, -16.0),
            (-47.8, -16.0),
            (-47.8, -15.951),
            (-47.8, -15.949),
            (-47.8, -15.9),
            (-47.9, -15.9),
            (-47.89995, -15.95),
        ]
    )
    # Urbano de 220 m encostado no rural B, com um dente de 22 m na borda de cima (fica).
    urbano = Polygon(
        [(-47.8, -15.951), (-47.798, -15.951), (-47.798, -15.949), (-47.799, -15.9492), (-47.8, -15.949)]
    )  # fmt: skip
    antes = [rural_a, rural_b, urbano]
    assert shapely.coverage_is_valid(antes)
    depois = pilot._simplificar_cobertura_do_territorio(antes)
    assert shapely.coverage_is_valid(depois)
    uniao = shapely.union_all(depois)
    assert uniao.geom_type == "Polygon" and not list(uniao.interiors)  # nenhuma fresta
    assert uniao.area == pytest.approx(sum(g.area for g in depois))  # nem sobreposição
    assert shapely.get_num_coordinates(depois[0]) == 5  # A sem a curva: o retângulo
    assert shapely.get_num_coordinates(depois[2]) == 6  # o urbano com o dente
    # A divisa do rural B com o urbano segue nos mesmos pontos.
    assert {(-47.8, -15.951), (-47.8, -15.949)} <= set(depois[1].exterior.coords)
    assert len(pilot._simplificar_cobertura_do_territorio([])) == 0


def test_os_setores_do_municipio_trazem_a_renda_e_a_densidade_do_mapa_de_calor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A renda e a densidade de cada setor são as do mapa de calor do município, e o setor sem
    geometria fica de fora."""
    from shapely.geometry import box

    pasta = tmp_path / "geo" / "uf=DF" / "cod_municipio=5300108"
    pasta.mkdir(parents=True)
    pd.DataFrame(
        {
            "cod_setor": ["530010805000001", "530010805000002", "530010805000003"],
            "geometry_wkb": [box(-47.9, -15.8, -47.89, -15.79).wkb, box(-48, -16, -47.9, -15.9).wkb, None],
            "densidade_pop_setor_hab_km2": [12345.67, 3.04, 10.0],
            "renda_responsavel_media_setor_2022": [5000.0, 3000.0, 1000.0],
        }
    ).to_parquet(pasta / "part-000.parquet")  # fmt: skip
    monkeypatch.setattr(pilot, "CENSO_GEO_DIR", tmp_path / "geo")
    monkeypatch.setattr(
        pilot._renda_setor,
        "renda_domiciliar_da_linha",
        lambda r, uf, cod: r["renda_responsavel_media_setor_2022"] * 1.1,
    )
    setores = pilot._setores_do_municipio_no_territorio("DF", "5300108")
    assert [(renda, densidade) for _, renda, densidade in setores] == [
        (5500.0, 12345.7),
        (3300.0, 3.0),
    ]
    assert pilot._setores_do_municipio_no_territorio("DF", "9999999") == []


# ---------------------------------------------------------------------------
# O master com login próprio (027, emenda 2 da DEC-089; 19/11/2026, Juan: "os masters vão ter seus
# próprios logins; quando clicarem em Masters, já abrir no nome dele")
# ---------------------------------------------------------------------------


def _login(monkeypatch: pytest.MonkeyPatch, nome: Any, permissoes: set[str]) -> None:
    """Banco no comando, a identidade e o nome do usuário dublados."""
    monkeypatch.setattr(acesso, "banco_no_comando", lambda: True)
    _identidade(monkeypatch, permissoes)

    def nome_do_usuario(_id: int) -> Any:
        if isinstance(nome, Exception):
            raise nome
        return nome

    monkeypatch.setattr(rbac, "nome_do_usuario", nome_do_usuario)


def test_o_master_com_login_ve_so_o_proprio_painel(
    masters: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _login(monkeypatch, "MASTER  um", {"masters.ver_proprio"})
    lista = pilot.api_masters(remote_user="alguem")
    assert [c["id"] for c in lista["masters"]] == ["rjsp"]
    assert lista["proprio"] is True  # a tela abre direto nele
    assert pilot.api_master("rjsp", remote_user="alguem")["id"] == "rjsp"
    # O de outro master responde como um master que não existe (404, e não 403).
    assert _status(lambda: pilot.api_master("sp03", remote_user="alguem")) == (
        404,
        "Master não encontrado.",
    )


def test_login_cujo_nome_nao_e_de_master_nao_ve_nenhum(
    masters: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for nome in ("Outra Pessoa", None):
        _login(monkeypatch, nome, {"masters.ver_proprio"})
        lista = pilot.api_masters(remote_user="alguem")
        assert lista["masters"] == [] and lista["proprio"] is True
        assert _status(lambda: pilot.api_master("rjsp", remote_user="alguem"))[0] == 404


def test_growth_e_lideres_seguem_vendo_todos(
    masters: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _login(monkeypatch, "Master Um", {"masters.ver"})
    lista = pilot.api_masters(remote_user="alguem")
    assert [c["id"] for c in lista["masters"]] == ["rjsp", "sp03"]
    assert lista["proprio"] is False


def test_banco_fora_ao_ler_o_nome_vira_503_e_nunca_todos(
    masters: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from motor_expansao import db

    _login(monkeypatch, db.BancoIndisponivel("fora"), {"masters.ver_proprio"})
    assert _status(lambda: pilot.api_masters(remote_user="alguem"))[0] == 503


@pytest.mark.parametrize(
    "rota",
    [
        "api_master_mapa",
        "api_master_mapa_camadas",
        "api_master_recomendacao",
        "api_master_crescimento",
        "api_master_setores",
    ],
)
def test_as_leituras_do_painel_barram_o_master_de_outro(
    mapa: dict[str, Any], monkeypatch: pytest.MonkeyPatch, rota: str
) -> None:
    _login(monkeypatch, "Master Um", {"masters.ver_proprio"})
    # A conta da recomendação e a dos setores têm os testes delas; aqui só importa quem chega.
    monkeypatch.setattr(pilot, "_bloco_recomendacao", lambda *_a, **_k: {})
    monkeypatch.setattr(pilot, "_setores_do_municipio_no_territorio", lambda *_a: [])
    funcao = getattr(pilot, rota)
    assert _status(lambda: funcao("sp03", remote_user="alguem")) == (404, "Master não encontrado.")
    funcao("rjsp", remote_user="alguem")  # o próprio passa


def test_o_estudo_e_o_relatorio_barram_o_master_de_outro(
    relatorio: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    _login(monkeypatch, "Master Um", {"masters.ver_proprio"})
    outro = (404, "Master não encontrado.")
    assert _status(lambda: asyncio.run(pilot.api_master_estudo("sp03", remote_user="x"))) == outro
    assert (
        _status(
            lambda: asyncio.run(pilot.api_master_relatorio("sp03", regiao=None, remote_user="x"))
        )
        == outro
    )
    # O próprio gera o relatório (Juan: "sim, ele, os líderes e o growth").
    r = asyncio.run(pilot.api_master_relatorio("rjsp", regiao="rj", remote_user="x"))
    assert r.media_type == "application/pdf"
    assert relatorio[-1]["master"] == "rjsp"


def test_o_perfil_master_ve_a_aba_masters(monkeypatch: pytest.MonkeyPatch) -> None:
    assert "masters.ver_proprio" in acesso.CAPACIDADES_SENSIVEIS
    _identidade(monkeypatch, {"rede.ver_propria", "masters.ver_proprio"})
    assert acesso.abas_do_usuario_por_banco("alguem") == frozenset({"executiva", "masters"})
    # Só a capacidade da Executiva não dá a tela Masters.
    _identidade(monkeypatch, {"rede.ver_propria"})
    assert acesso.abas_do_usuario_por_banco("alguem") == frozenset({"executiva"})


def test_a_migration_027_da_o_proprio_painel_so_ao_perfil_master() -> None:
    sql = (_REPO / "src/motor_expansao/db/migracoes/027-permissao-masters-proprio.sql").read_text(
        encoding="utf-8"
    )
    assert "('masters.ver_proprio'," in sql
    concessoes = sql.split("INSERT INTO perfil_permissoes")[1]
    assert "('master', 'masters.ver_proprio')" in concessoes
    for fora in ("growth", "lideres", "consultoria", "expansao"):
        assert f"('{fora}'," not in concessoes


# ---------------------------------------------------------------------------
# O Início do master (emenda 2 da DEC-089; 19/11/2026, Juan): o pedido de imóvel e o estudo de um
# ponto por coordenadas, com o aviso "Estudo fora da sua área de atuação" fora do território.
# ---------------------------------------------------------------------------


def test_o_master_pede_um_imovel_numa_regiao(
    masters: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from motor_expansao.db import eventos as db_eventos

    _login(monkeypatch, "Master Um", {"masters.ver_proprio"})
    gravados: list[dict[str, Any]] = []
    monkeypatch.setattr(db_eventos, "registrar_imovel_solicitado", lambda **kw: gravados.append(kw))
    r = pilot.api_master_solicitar_imovel(
        pilot.PedidoDeImovelIn(regiao="  Asa Sul,   perto do   Parkshopping "), remote_user="x"
    )
    assert r == {"ok": True, "registrado": True}
    assert gravados == [
        {"autor": 1, "masters": ["rjsp"], "regiao": "Asa Sul, perto do Parkshopping"}
    ]
    # Região em branco não vira pedido.
    vazio = (400, "Diga a região em que você gostaria de um imóvel.")
    assert (
        _status(
            lambda: pilot.api_master_solicitar_imovel(
                pilot.PedidoDeImovelIn(regiao="   "), remote_user="x"
            )
        )
        == vazio
    )


def test_o_pedido_de_imovel_nao_cai_quando_a_trilha_falha(
    masters: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from motor_expansao.db import eventos as db_eventos

    _login(monkeypatch, "Master Um", {"masters.ver_proprio"})

    def quebra(**_kw: Any) -> None:
        raise RuntimeError("banco caiu no meio")

    monkeypatch.setattr(db_eventos, "registrar_imovel_solicitado", quebra)
    r = pilot.api_master_solicitar_imovel(pilot.PedidoDeImovelIn(regiao="Centro"), remote_user="x")
    assert r == {"ok": True, "registrado": False}


@pytest.fixture
def estudo_do_ponto(mapa: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> dict[str, list[Any]]:
    """O gerador do PDF e os registros dublados: aqui se confere a rota (área, aviso, trilha). O
    lugar do ponto também é dublado (lê a malha municipal e o Censo, que têm os testes deles)."""
    from motor_expansao.db import eventos as db_eventos

    pdfs: list[dict[str, Any]] = []
    estudos: list[dict[str, Any]] = []

    def gerar(lat: float, lng: float, *args: Any, **kw: Any) -> Any:
        pdfs.append({"lat": lat, "lng": lng, **kw})
        return pilot.Response(content=b"%PDF-estudo", media_type="application/pdf")

    async def registrar(*_a: Any, **_k: Any) -> str:
        return "rid-1"

    monkeypatch.setattr(pilot, "_gerar_relatorio_pontual_pdf", gerar)
    monkeypatch.setattr(pilot, "_registrar_relatorio_gerado_fora_do_loop", registrar)
    monkeypatch.setattr(db_eventos, "registrar_estudo_solicitado", lambda **kw: estudos.append(kw))
    monkeypatch.setattr(pilot, "_lugar_do_ponto", lambda lat, lng: f"Lugar {lat}, {lng}")
    return {"pdfs": pdfs, "estudos": estudos}


def _estudo_do_ponto(lat: float, lng: float) -> Any:
    return asyncio.run(pilot.api_master_estudo_do_ponto(lat, lng, remote_user="x"))


def test_estudo_dentro_do_territorio_sai_sem_aviso(
    estudo_do_ponto: dict[str, list[Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    _login(monkeypatch, "Master Um", {"masters.ver_proprio"})
    r = _estudo_do_ponto(-23.55, -46.63)  # São Paulo, do território do RJ/SP 01
    assert r.body == b"%PDF-estudo"
    (pdf,) = estudo_do_ponto["pdfs"]
    assert pdf["so_estudo"] is True and pdf["aviso_fora_da_area"] is False
    assert pdf["report_id"] == "rid-1"
    # Todo estudo do master vira o aviso do Growth (DEC-090), dentro da área também.
    assert estudo_do_ponto["estudos"] == [
        {
            "autor": 1,
            "masters": ["rjsp"],
            "lat": -23.55,
            "lng": -46.63,
            "fora_da_area": False,
            "lugar": "Lugar -23.55, -46.63",
            "report_id": "rid-1",
        }
    ]
    # Um terreno vazio dentro do território (Ribeirão Preto, sem gente) ainda é do território.
    _estudo_do_ponto(-21.20, -47.80)
    assert estudo_do_ponto["pdfs"][-1]["aviso_fora_da_area"] is False


def test_estudo_fora_do_territorio_sai_com_o_aviso_e_fica_na_trilha(
    estudo_do_ponto: dict[str, list[Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    _login(monkeypatch, "Master Um", {"masters.ver_proprio"})
    _estudo_do_ponto(-19.90, -43.90)  # Belo Horizonte: fora do RJ/SP 01
    assert estudo_do_ponto["pdfs"][-1]["aviso_fora_da_area"] is True
    assert estudo_do_ponto["estudos"] == [
        {
            "autor": 1,
            "masters": ["rjsp"],
            "lat": -19.9,
            "lng": -43.9,
            "fora_da_area": True,
            "lugar": "Lugar -19.9, -43.9",
            "report_id": "rid-1",
        }
    ]


def test_growth_estuda_qualquer_ponto_sem_aviso(
    estudo_do_ponto: dict[str, list[Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    _login(monkeypatch, "Fulano", {"masters.ver"})
    _estudo_do_ponto(-19.90, -43.90)
    assert estudo_do_ponto["pdfs"][-1]["aviso_fora_da_area"] is False
    # Quem vê todos os masters (Growth, Líderes) não é master: o estudo dele não vira aviso.
    assert estudo_do_ponto["estudos"] == []


def test_estudo_fora_do_pais_e_recusado(
    estudo_do_ponto: dict[str, list[Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    _login(monkeypatch, "Master Um", {"masters.ver_proprio"})
    assert _status(lambda: _estudo_do_ponto(40.7, -74.0)) == (
        400,
        "Coordenada fora do país desta instância.",
    )
    assert estudo_do_ponto["pdfs"] == []


@pytest.mark.parametrize("caminho", ["/api/masters/estudo", "/api/masters/solicitar-imovel"])
def test_os_gestos_do_inicio_tem_o_gate_da_tela(
    monkeypatch: pytest.MonkeyPatch, caminho: str
) -> None:
    assert acesso.capacidade_necessaria(caminho, "POST") == "masters.ver"
    _identidade(monkeypatch, {"masters.ver_proprio"})
    assert acesso.motivo_bloqueio_por_banco(caminho, "POST", "alguem") is None
    _identidade(monkeypatch, {"rede.ver_propria"})
    assert acesso.motivo_bloqueio_por_banco(caminho, "POST", "alguem") is not None


def test_o_api_me_diz_quando_o_inicio_e_o_do_master(monkeypatch: pytest.MonkeyPatch) -> None:
    """O Início do master (emenda 2 da DEC-089) só aparece com `masters_proprio`: o master com
    login próprio o recebe; Growth e Líderes, que também têm a aba Masters, não."""
    _login(monkeypatch, "Master Um", {"rede.ver_propria", "masters.ver_proprio"})
    r = pilot.me(remote_user="alguem")
    assert set(r["abas"]) == {"executiva", "masters"}
    assert r["masters_proprio"] is True
    _login(monkeypatch, "Fulano", {"masters.ver", "rede.ver"})
    assert pilot.me(remote_user="alguem")["masters_proprio"] is False


def test_o_api_me_diz_os_avisos_que_chegam_a_pessoa(monkeypatch: pytest.MonkeyPatch) -> None:
    """O sino da barra lateral (DEC-090) so' aparece com a chave `avisos`: o Growth recebe o de
    estudo pelo perfil; quem tem o de imovel marcado na aba Acessos, esse; o master, nenhum."""
    from motor_expansao.db import avisos as db_avisos

    marcados: set[str] = set()
    monkeypatch.setattr(db_avisos, "avisos_da_pessoa", lambda _id: frozenset(marcados))
    _login(monkeypatch, "Fulano", {"masters.ver", "rede.ver", "avisos.estudos_masters"})
    assert pilot.me(remote_user="alguem")["avisos"] == ["estudo_master"]
    marcados.add("imovel_master")
    _login(monkeypatch, "Priscila", {"rede.ver"})
    assert pilot.me(remote_user="alguem")["avisos"] == ["imovel_master"]
    marcados.clear()
    _login(monkeypatch, "Master Um", {"rede.ver_propria", "masters.ver_proprio"})
    assert "avisos" not in pilot.me(remote_user="alguem")
