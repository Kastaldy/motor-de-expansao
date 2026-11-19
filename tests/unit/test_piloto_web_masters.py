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


def test_camadas_por_hexagono_sao_espaco_livre_e_concorrentes(mapa: dict[str, Any]) -> None:
    d = _json(pilot.api_master_mapa_camadas("rjsp"))
    assert d["disponivel"] is True
    # [hex, espaço livre, concorrentes]: os mapas do relatório que ele desenha por hexágono. O
    # hexágono sem gente não entra. Renda e densidade são sempre do Censo (19/11/2026, Juan:
    # "deixe o padrão sempre censitário"), e não leem mais a partição da UF.
    assert sorted(d["hexes"]) == sorted(
        [[RIO, 600.0, 2.0], [SAMPA, 1000.0, 5.0], [INTERIOR, 500.0, 0.0]]
    )
    assert mapa["lidas"] == []
    # As faixas são as do núcleo e as do relatório; concorrentes começa em "nenhuma".
    from motor_expansao.dashboard import constants as C
    from motor_expansao.masters.relatorio_pdf import CONC_1KM_BANDS

    assert d["faixas"]["renda_domiciliar"] == pilot._faixas_camada(C.RENDA_MEDIA_DOMICILIAR_BANDS)
    assert d["faixas"]["densidade"] == pilot._faixas_camada(C.DENSIDADE_POP_BANDS)
    assert d["faixas"]["espaco_livre"] == pilot._faixas_camada(C.OFERTA_DISPONIVEL_ALUNOS_BANDS)
    assert d["faixas"]["concorrentes"][0]["rotulo"] == "nenhuma"
    assert d["faixas"]["concorrentes"][1:] == pilot._faixas_camada(CONC_1KM_BANDS)


def test_mapa_fica_em_cache_ate_uma_fonte_mudar(
    mapa: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    lidos: list[tuple[str, str]] = []

    def pontos(uf: str, cod: str) -> tuple[tuple[Any, ...], ...]:
        lidos.append((uf, cod))
        return ()

    monkeypatch.setattr(pilot, "_setores_pontos", pontos)
    pilot.api_master_setores_pontos("rjsp")
    pilot.api_master_setores_pontos("rjsp")
    assert len(lidos) == 4  # os quatro municípios do território, uma vez
    m = pilot.MERCADO_PARQUET
    os.utime(m, ns=(m.stat().st_atime_ns, m.stat().st_mtime_ns + 10**9))
    pilot.api_master_setores_pontos("rjsp")
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


def test_setores_do_censo_so_dos_municipios_do_territorio(
    mapa: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """De perto, renda e densidade passam aos setores do Censo (19/11/2026, Juan: "o censitário"),
    um município por vez, pela mesma leitura do mapa de calor do município."""
    pedidos: list[tuple[str, str]] = []

    def setores(uf: str, cod: str) -> list[dict[str, Any]]:
        pedidos.append((uf, cod))
        return [{"setor": "1", "anel": [[0, 0]], "densidade": 10.0, "renda_domiciliar": 5000.0}]

    monkeypatch.setattr(pilot, "_setores_heatmap_features", setores)
    d = _json(pilot.api_master_setores("rjsp", "sp", "3550308"))
    assert d["setores"][0]["renda_domiciliar"] == 5000.0
    assert pedidos == [("SP", "3550308")]
    # Município fora do território (BH, de outro estado): 404, sem ler nada.
    assert _status(lambda: pilot.api_master_setores("rjsp", "MG", "3106200")) == (
        404,
        "Município fora do território do master.",
    )
    # E o master de uma área não lê os setores da outra.
    assert _status(lambda: pilot.api_master_setores("sp03", "RJ", "3304557"))[0] == 404
    assert pedidos == [("SP", "3550308")]


def test_renda_e_densidade_sao_sempre_do_censo_um_ponto_por_setor(
    mapa: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """19/11/2026, Juan: "deixe o padrão sempre censitário". De longe, um ponto por setor do
    território inteiro (os mapas de calor do relatório); de perto, os polígonos."""
    por_municipio = {
        ("RJ", "3304557"): ((-43.2, -22.9, 9000.0, 12000.0),),
        ("SP", "3550308"): ((-46.63, -23.55, 6100.0, 8123.5), (-46.6, -23.5, None, 900.0)),
    }
    monkeypatch.setattr(pilot, "_setores_pontos", lambda uf, cod: por_municipio.get((uf, cod), ()))
    d = _json(pilot.api_master_setores_pontos("rjsp"))
    assert d["setores"] == [
        [-43.2, -22.9, 9000.0, 12000.0],
        [-46.63, -23.55, 6100.0, 8123.5],
        [-46.6, -23.5, None, 900.0],
    ]
    # O master de uma área só lê os setores da dele.
    assert len(_json(pilot.api_master_setores_pontos("sp03"))["setores"]) == 2


def test_o_ponto_do_setor_e_o_centro_da_caixa_sem_arredondar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O centro de cada setor sai da caixa dele com a precisão da coordenada (um arredondamento a
    inteiro punha todos os setores de Brasília no mesmo ponto), e a renda e a densidade são as
    do mapa de calor do município."""
    pasta = tmp_path / "geo" / "uf=DF" / "cod_municipio=5300108"
    pasta.mkdir(parents=True)
    pd.DataFrame(
        {
            "cod_setor": ["530010805000001", "530010805000002"],
            "bbox_minx": [-47.90, -47.80],
            "bbox_miny": [-15.80, -15.70],
            "bbox_maxx": [-47.88, -47.78],
            "bbox_maxy": [-15.78, -15.68],
            "densidade_pop_setor_hab_km2": [12345.67, None],
            "renda_responsavel_media_setor_2022": [5000.0, 3000.0],
            "renda_per_capita_setor_2022": [2000.0, 1000.0],
            "avg_moradores_domicilio_setor_2022": [2.5, 3.0],
        }
    ).to_parquet(pasta / "part-000.parquet")
    monkeypatch.setattr(pilot, "CENSO_GEO_DIR", tmp_path / "geo")
    monkeypatch.setattr(
        pilot._renda_setor,
        "renda_domiciliar_da_linha",
        lambda r, uf, cod: r["renda_responsavel_media_setor_2022"] * 1.1,
    )
    pilot._setores_pontos.cache_clear()
    pontos = pilot._setores_pontos("DF", "5300108")
    assert pontos == (
        (-47.89, -15.79, 5500.0, 12345.7),
        (-47.79, -15.69, 3300.0, None),
    )
