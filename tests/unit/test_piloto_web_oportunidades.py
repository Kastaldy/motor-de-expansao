"""Contrato da rota `/api/oportunidades` (camada imobiliária do piloto web).

Esta rota não tinha teste NENHUM até 2026-08-24, e foi assim que dois defeitos
chegaram a produção juntos:

  1. A tela pedia sem `limite` (default 500 no servidor) e montava o seletor de
     estados a partir dos ITENS recebidos. Como `m1_residual_fitness` **satura** em
     100,0 para 44% do universo, o corte dos 500 caía DENTRO do empate e três UFs
     inteiras (RJ, PR, SC) não apareciam — nem no seletor, nem em lugar nenhum da aba.
  2. Sem desempate secundário e com `sort_values` em quicksort (instável), QUAIS
     linhas entravam no top-N era arbitrário — não reproduzível entre execuções.

Os testes abaixo travam as duas correções e o contrato das três contagens
(`total`, `total_recorte`, `len(itens)`), que é o que permite a tela dizer um
denominador honesto.

Chama as funções de rota DIRETO (sem TestClient), no padrão de
`test_piloto_web_api.py`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

_REPO = Path(__file__).resolve().parents[2]
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import app as pilot_app  # noqa: E402


def _linha(
    imovel_id: str,
    uf: str,
    fitness: float,
    total_residual: float,
    *,
    status: str = "ativo",
    area: float = 1500.0,
) -> dict[str, object]:
    """Uma linha do `viaveis.parquet` com o mínimo que a rota projeta."""
    return {
        "imovel_id": imovel_id,
        "fonte_listing_id": f"lst-{imovel_id}",
        "titulo": f"Imovel {imovel_id}",
        "tipo": "galpao",
        "operacao": "aluguel",
        "uf": uf,
        "municipio": f"Cidade {uf}",
        "bairro": "Centro",
        "area_relevante_m2": area,
        "preco_aluguel": 30000.0,
        "hex_id": f"87{imovel_id}ffffff",
        "m1_residual_fitness": fitness,
        "m1_residual_total": total_residual,
        "status": status,
        "latitude": -23.5,
        "longitude": -46.6,
        "url": f"https://exemplo/{imovel_id}",
    }


@pytest.fixture
def apontar(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Escreve um parquet de teste e aponta a rota para ele, zerando o cache global.

    `_OPORTUNIDADES_CACHE` é um global que NUNCA invalida (por desenho: em produção o
    artefato só muda por deploy). Sem zerar aqui, o primeiro teste contaminaria todos
    os outros — e o cache também guarda lista vazia, então a ordem importaria.
    """

    def _apontar(linhas: list[dict[str, object]]) -> None:
        caminho = tmp_path / "viaveis.parquet"
        pd.DataFrame(linhas).to_parquet(caminho)
        monkeypatch.setattr(pilot_app, "OPORTUNIDADES_PATH", caminho)
        monkeypatch.setattr(pilot_app, "_OPORTUNIDADES_CACHE", None)
        # Sem dossiê no tmp: o índice varre um diretório que não existe -> {}.
        monkeypatch.setattr(pilot_app, "DOSSIES_DIR", tmp_path / "sem-dossies")

    yield _apontar
    # Não deixa o cache do teste vazar para a suíte (o monkeypatch restaura o global,
    # mas quem já leu o valor antigo dentro da função não é afetado — reforço explícito).
    pilot_app._OPORTUNIDADES_CACHE = None


# --- as três contagens ------------------------------------------------------------


def test_tres_contagens_no_recorte_nacional(apontar) -> None:
    """`total` e `total_recorte` coincidem sem `uf`; `itens` respeita o `limite`."""
    apontar([_linha(f"a{i:03d}", "SP", 50.0, 1000.0 - i) for i in range(10)])
    r = pilot_app.api_oportunidades(limite=4)
    assert r["total"] == 10
    assert r["total_recorte"] == 10
    assert len(r["itens"]) == 4


def test_total_recorte_e_o_denominador_da_uf(apontar) -> None:
    """Filtrar por UF muda `total_recorte`, NUNCA `total`.

    É a diferença que a tela usa para dizer "N de M deste recorte". Com só `total`,
    escolher SP comparava os itens de SP contra o universo nacional.
    """
    apontar(
        [_linha(f"sp{i}", "SP", 50.0, 100.0 - i) for i in range(7)]
        + [_linha(f"rj{i}", "RJ", 50.0, 100.0 - i) for i in range(3)]
    )
    nacional = pilot_app.api_oportunidades()
    assert (nacional["total"], nacional["total_recorte"]) == (10, 10)

    sp = pilot_app.api_oportunidades(uf="SP")
    assert sp["total"] == 10, "o universo nao encolhe ao filtrar"
    assert sp["total_recorte"] == 7
    assert {o["uf"] for o in sp["itens"]} == {"SP"}


def test_filtro_de_uf_e_case_insensitive(apontar) -> None:
    apontar([_linha("sp1", "SP", 50.0, 10.0), _linha("rj1", "RJ", 50.0, 10.0)])
    assert len(pilot_app.api_oportunidades(uf="sp")["itens"]) == 1


# --- o seletor de estados (defeito nº 1) ------------------------------------------


def test_ufs_e_o_universo_e_nao_as_ufs_dos_itens(apontar) -> None:
    """REGRESSÃO do seletor de 3 estados.

    Com o `limite` cortando dentro do empate de residual, os `itens` podem não conter
    nenhuma linha de UFs que EXISTEM no universo. `ufs` tem de listar todas de todo
    jeito — é dele que o seletor da tela se alimenta.
    """
    apontar(
        # SP domina o topo por residual_total; RJ e PR ficam fora de um limite=2.
        [_linha("sp1", "SP", 100.0, 900.0), _linha("sp2", "SP", 100.0, 800.0)]
        + [_linha("rj1", "RJ", 100.0, 10.0), _linha("pr1", "PR", 100.0, 5.0)]
    )
    r = pilot_app.api_oportunidades(limite=2)
    assert {o["uf"] for o in r["itens"]} == {"SP"}, "o cap cortou RJ e PR dos itens"
    assert r["ufs"] == ["PR", "RJ", "SP"], "mas o seletor precisa ver as tres"


def test_ufs_nao_encolhe_ao_filtrar_por_uf(apontar) -> None:
    """Com `ufs` derivado dos itens, escolher SP deixava o seletor com um único item —
    e não havia como voltar para outro estado."""
    apontar([_linha("sp1", "SP", 50.0, 10.0), _linha("rj1", "RJ", 50.0, 10.0)])
    assert pilot_app.api_oportunidades(uf="SP")["ufs"] == ["RJ", "SP"]


# --- a ordem (defeito nº 2) -------------------------------------------------------


def test_residual_total_desempata_o_fitness_saturado(apontar) -> None:
    """Todas com `fitness` 100,0 (o caso real: 44% do universo). A ordem tem de sair
    do `m1_residual_total`, que não satura, e não da ordem do arquivo."""
    apontar(
        [
            _linha("baixo", "SP", 100.0, 10.0),
            _linha("alto", "SP", 100.0, 9000.0),
            _linha("medio", "SP", 100.0, 500.0),
        ]
    )
    ids = [o["id"] for o in pilot_app.api_oportunidades()["itens"]]
    assert ids == ["alto", "medio", "baixo"]


def test_fitness_continua_sendo_o_criterio_principal(apontar) -> None:
    """O desempate NÃO pode virar régua: um fitness maior vence um total maior."""
    apontar(
        [
            _linha("total_gigante", "SP", 40.0, 9_999.0),
            _linha("fitness_maior", "SP", 90.0, 1.0),
        ]
    )
    ids = [o["id"] for o in pilot_app.api_oportunidades()["itens"]]
    assert ids == ["fitness_maior", "total_gigante"]


def test_ordem_e_deterministica_no_empate_duplo(apontar) -> None:
    """Empate nos DOIS critérios cai na ordem do arquivo (`kind="stable"`), não na
    sorte do quicksort. Duas leituras seguidas devolvem a mesma sequência."""
    apontar([_linha(f"x{i}", "SP", 100.0, 100.0) for i in range(12)])
    primeira = [o["id"] for o in pilot_app.api_oportunidades(limite=5)["itens"]]
    pilot_app._OPORTUNIDADES_CACHE = None
    segunda = [o["id"] for o in pilot_app.api_oportunidades(limite=5)["itens"]]
    assert primeira == segunda == ["x0", "x1", "x2", "x3", "x4"]


def test_ordena_sem_a_coluna_de_desempate(apontar) -> None:
    """Parquet antigo, sem `m1_residual_total`: ordena só por fitness, sem explodir."""
    linhas = [_linha("a", "SP", 10.0, 1.0), _linha("b", "SP", 90.0, 1.0)]
    for linha in linhas:
        del linha["m1_residual_total"]
    apontar(linhas)
    assert [o["id"] for o in pilot_app.api_oportunidades()["itens"]] == ["b", "a"]


# --- guardas de contrato ----------------------------------------------------------


def test_removido_sai_do_universo(apontar) -> None:
    apontar(
        [
            _linha("vivo", "SP", 50.0, 10.0),
            _linha("morto", "SP", 99.0, 999.0, status="removido"),
        ]
    )
    r = pilot_app.api_oportunidades()
    assert r["total"] == 1
    assert [o["id"] for o in r["itens"]] == ["vivo"]


def test_limite_e_capado_em_3000_e_tem_piso_de_1(apontar) -> None:
    """O cap protege o payload (3.000 itens ≈ 2,3 MB); o piso evita `itens` vazio por
    um `limite=0` vindo da query."""
    apontar([_linha(f"x{i}", "SP", 50.0, float(i)) for i in range(5)])
    assert len(pilot_app.api_oportunidades(limite=99_999)["itens"]) == 5
    assert len(pilot_app.api_oportunidades(limite=0)["itens"]) == 1


def test_sem_pii_de_corretor_no_payload(apontar) -> None:
    """A lista é liberada também pela aba `mapa` (DEC-037): contato de corretor não
    pode sair daqui em NENHUMA circunstância — ele vive só no PDF do dossiê."""
    linha = _linha("sp1", "SP", 50.0, 10.0)
    linha.update(
        {
            "corretor_nome": "Fulano de Tal",
            "corretor_telefone_e164": "+5511999999999",
            "corretor_creci": "12345",
            "corretor_conta_id": "conta-1",
        }
    )
    apontar([linha])
    item = pilot_app.api_oportunidades()["itens"][0]
    serializado = repr(item).lower()
    for proibido in ("corretor", "fulano", "5511999999999", "creci"):
        assert proibido not in serializado, f"PII no payload: {proibido}"


def test_sem_o_parquet_devolve_vazio_e_nao_500(monkeypatch, tmp_path) -> None:
    """A aba degrada para lista vazia — é por isso que o artefato entrou no
    `/api/health` (a tela não distingue "sem dado" de "filtro não casou")."""
    monkeypatch.setattr(pilot_app, "OPORTUNIDADES_PATH", tmp_path / "nao-existe.parquet")
    monkeypatch.setattr(pilot_app, "_OPORTUNIDADES_CACHE", None)
    r = pilot_app.api_oportunidades()
    assert (r["total"], r["total_recorte"], r["itens"], r["ufs"]) == (0, 0, [], [])
    pilot_app._OPORTUNIDADES_CACHE = None
