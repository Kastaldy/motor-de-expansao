"""Rotas `/api/rede/*` da Visao Executiva 2.0 (BLK-EXEC-02/05..11, DEC-023).

Cobre o que o backend do piloto sempre exigiu -- contrato, degradacao sem parquet e
JSON-safe -- mais tres coisas proprias deste epic:

* **carteira e ficha tem de concordar.** O defeito mais caro deste projeto e' a mesma
  unidade com dois numeros em duas superficies; aqui isso e' teste.
* **o contrato v1 continua intacto.** `/api/executiva/{uf}` virou adaptador, e a tela
  antiga nao pode notar.
* **a unica escrita do piloto acontece so no diretorio do cadastro**, com lista branca,
  concorrencia otimista e degradacao clara quando o volume nao esta montado.

Chama as funcoes de rota DIRETO (sem TestClient), como o resto da suite do piloto.
"""

from __future__ import annotations

import ast
import csv
import io
import json
import re
import sys
from pathlib import Path

import pandas as pd
import pytest
from fastapi import HTTPException

_REPO = Path(__file__).resolve().parents[2]
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import app as pilot  # noqa: E402

from motor_expansao.dashboard import rede_cadastro, rede_diagnostico, rede_export  # noqa: E402
from tests.unit.rede_fixtures import mes as mes_sintetico  # noqa: E402


@pytest.fixture(autouse=True)
def _exports_da_rede_ligados(monkeypatch: pytest.MonkeyPatch) -> None:
    """B7: em producao os exports da rede nascem DESLIGADOS (403). Esta suite foi escrita
    quando as 4 rotas respondiam 200, entao liga a chave para todos os testes do modulo;
    `test_exports_desligados_recusam_no_servidor` a desliga de novo para provar o 403."""
    monkeypatch.setattr(pilot, "EXPORTS_REDE_ATIVOS", True)


_CACHES = (
    "_carregar_growth",
    "_carregar_ultra_pontos",
    "_carregar_ultra_mapeadas",
    "_ultra_coord_map",
    "_icone_ultra",
    "_rede_base",
    "_rede_fechamento",
    "_rede_cadastro",
    "_rede_mes",
)


def _limpar_caches() -> None:
    pilot.limpar_caches()


def _base_sintetica() -> pd.DataFrame:
    """Rede pequena, com o bastante para acender ranking, coorte e alertas."""
    perfis = [
        ("BOTAFOGO - RJ", "RJ", "RJ/SP 01", "01/01/2021", 400_000.0, 40.0, 80.0),
        ("ICARAI - RJ", "RJ", "RJ/SP 01", "01/06/2024", 220_000.0, 30.0, 55.0),
        ("BANGU - RJ", "RJ", "RJ/SP 01", "01/03/2026", 90_000.0, 120.0, 10.0),
        ("AUGUSTA", "SP", "ULTRA", "02/01/2021", 310_000.0, 25.0, 70.0),
        ("BERRINI - SP", "SP", "SP 03", "01/02/2023", 150_000.0, 95.0, 15.0),
    ]
    linhas: list[dict[str, object]] = []
    for nome, uf, master, inauguracao, faturamento, cancelados, nps in perfis:
        for ano, numero_mes in ((2026, 4), (2026, 5), (2026, 6), (2026, 7)):
            linhas += mes_sintetico(
                nome,
                ano,
                numero_mes,
                uf=uf,
                master=master,
                inauguracao=inauguracao,
                cumulativas={
                    "faturamento": faturamento,
                    "faturamento_sem_agregador": faturamento * 0.9,
                    "cancelados": cancelados,
                    "visitas": 200.0,
                    "convertidos": 100.0,
                    "novos_alunos": 90.0,
                    "vendas": 100.0,
                },
                snapshots={
                    "pagantes": 1_200.0,
                    "ativos_total": 1_500.0,
                    "alunos_gympass": 150.0,
                    "alunos_totalpass": 150.0,
                    "NPS": nps,
                    "em_cobranca": 90.0,
                    "inadimplente": 70.0,
                    "treino_ativo": 50.0,
                },
            )
    return pd.DataFrame(linhas)


@pytest.fixture
def rede(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """App apontado para uma base Growth sintetica e um cadastro proprio."""
    staging = tmp_path / "staging"
    staging.mkdir(parents=True)
    _base_sintetica().to_parquet(staging / "growth_api_historico.parquet")

    cadastro_dir = tmp_path / "cadastro"
    cadastro_dir.mkdir()
    rede_cadastro.gravar_cadastro(
        rede_cadastro.Cadastro(
            versao=1,
            atualizado_em="2026-08-04T00:00:00+00:00",
            unidades={
                "botafogo-rj": {
                    "consultor": "MARISE",
                    "cidade": "Rio de Janeiro",
                    "master_franquia": "Fernando Nero",
                },
                "icarai-rj": {
                    "consultor": "JAILSON",
                    "cidade": "Niteroi",
                    "master_franquia": "Dalmo Ribeiro",
                },
            },
        ),
        cadastro_dir,
    )

    monkeypatch.setattr(pilot, "STAGING_DIR", staging)
    monkeypatch.setattr(pilot, "GROWTH_PARQUET", staging / "growth_api_historico.parquet")
    monkeypatch.setattr(pilot, "ULTRA_PERF_PARQUET", staging / "nao_existe.parquet")
    monkeypatch.setattr(pilot, "ULTRA_MAPEADAS_PARQUET", staging / "tambem_nao.parquet")
    # A planilha financeira TAMBEM precisa ser declarada ausente, como as duas acima:
    # `FATURAMENTO_FINANCEIRO_PARQUET` e constante de MODULO, resolvida no import a partir
    # do `STAGING_DIR` de ENTAO — repontar `STAGING_DIR` aqui em cima nao a move. Sem esta
    # linha, quem tiver `data/staging/faturamento_financeiro.parquet` no worktree le a
    # planilha REAL. Passava por acidente ate 2026-09-02, quando `STAGING_DIR` derivava do
    # `_DEFAULT_DATA` cravado no Downloads de UMA maquina: com a raiz quebrada, nenhum
    # arquivo existia. O Bloco A (DEC-047) trocou a raiz pelo `data/` do repo.
    monkeypatch.setattr(
        pilot, "FATURAMENTO_FINANCEIRO_PARQUET", staging / "sem_planilha.parquet"
    )
    monkeypatch.setattr(pilot, "CADASTRO_DIR", cadastro_dir)
    _limpar_caches()
    yield tmp_path
    _limpar_caches()


@pytest.fixture
def sem_dados(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Cenario do CI: nenhum parquet, nenhum cadastro."""
    monkeypatch.setattr(pilot, "GROWTH_PARQUET", tmp_path / "nao_existe.parquet")
    monkeypatch.setattr(pilot, "CADASTRO_DIR", tmp_path / "sem_cadastro")
    _limpar_caches()
    yield tmp_path
    _limpar_caches()


# ---------------------------------------------------------------------------
# Registro e degradacao
# ---------------------------------------------------------------------------

_ROTAS_NOVAS = {
    "/api/rede/filtros",
    "/api/rede/carteira",
    "/api/rede/carteira.csv",
    "/api/rede/carteira.xlsx",
    "/api/rede/carteira.pdf",
    "/api/rede/unidade/{unidade_id}",
    "/api/rede/unidade/{unidade_id}.pdf",
    "/api/rede/cadastro/{unidade_id}",
}


def test_todas_as_rotas_registradas() -> None:
    registradas = {getattr(r, "path", None) for r in pilot.app.routes}
    assert _ROTAS_NOVAS <= registradas
    assert "/api/executiva/{uf}" in registradas, "o contrato v1 nao pode sumir"


@pytest.mark.parametrize(
    "chamada",
    [
        lambda: pilot.rede_filtros(),
        lambda: pilot.rede_carteira(),
        lambda: pilot.rede_unidade("botafogo-rj"),
        lambda: pilot.executiva("RJ"),
    ],
)
def test_sem_base_levanta_404(sem_dados: Path, chamada) -> None:
    """Degradacao graciosa: sem o parquet, 404 coerente -- nunca 500."""
    with pytest.raises(HTTPException) as erro:
        chamada()
    assert erro.value.status_code == 404


# ---------------------------------------------------------------------------
# Carteira
# ---------------------------------------------------------------------------


def test_carteira_traz_o_quarteto_de_contexto(rede: Path) -> None:
    payload = pilot.rede_carteira(mes="2026-07")
    assert payload["totais"]["rede"] == 5
    botafogo = next(u for u in payload["unidades"] if u["id"] == "botafogo-rj")
    faturamento = botafogo["metricas"]["faturamento"]
    assert set(faturamento) == {"atual", "m1", "delta_pct", "rank", "rank_total", "vs_media_pct"}
    assert faturamento["rank"] == 1, "maior faturamento e' o 1o lugar"
    assert faturamento["vs_media_pct"] is not None
    assert botafogo["consultor"] == "MARISE"
    assert botafogo["coorte_rotulo"]


def test_carteira_e_ficha_concordam(rede: Path) -> None:
    """A mesma unidade, dois endpoints, o MESMO numero. Um por um, sem tolerancia."""
    carteira = pilot.rede_carteira(mes="2026-07")
    for unidade in carteira["unidades"]:
        ficha = pilot.rede_unidade(unidade["id"], mes="2026-07")
        for chave, valores in unidade["metricas"].items():
            assert ficha["metricas"][chave] == valores, f"{unidade['id']}.{chave} divergiu"
        assert ficha["diagnostico"]["severidade"] == unidade["severidade"]
        assert ficha["unidade"]["coorte"] == unidade["coorte"]


def test_carteira_e_json_safe(rede: Path) -> None:
    for payload in (pilot.rede_filtros(), pilot.rede_carteira(), pilot.rede_unidade("augusta-sp")):
        json.dumps(payload, allow_nan=False)


def test_payload_da_carteira_cabe_no_orcamento(rede: Path) -> None:
    """O cliente nao pagina: o payload inteiro tem de caber num carregamento.

    Mede a INCLINACAO (custo marginal por unidade) e a CONSTANTE separadamente, e nao o
    total dividido pela contagem. O painel do panorama trouxe um bloco fixo -- series de
    12 meses para 10 metricas, SSS mes a mes, faixas e coortes -- que nao cresce com a
    rede; numa base sintetica de 5 unidades ele sozinho desloca a media em ~1 KB por
    unidade e reprovaria um payload que na rede real esta folgado. Medido na base de
    producao em 2026-08-10: 92 unidades, 235 KB no total, 21,7 KB de bloco fixo e 2,3 KB
    marginais por unidade.
    """
    tudo = json.dumps(pilot.rede_carteira(), ensure_ascii=False).encode("utf-8")
    # `busca` corta a carteira para UMA unidade sem mexer no bloco fixo.
    uma = json.dumps(pilot.rede_carteira(busca="BOTAFOGO"), ensure_ascii=False).encode("utf-8")
    no_recorte = pilot.rede_carteira()["totais"]["no_recorte"]

    marginal = (len(tudo) - len(uma)) / max(no_recorte - 1, 1)
    assert marginal < 3_000, f"{marginal:.0f} bytes por unidade e' pesado demais"
    # O bloco fixo viaja em TODA requisicao, inclusive na de um consultor com 5 unidades.
    assert len(uma) < 40_000, f"bloco fixo de {len(uma)} bytes"


def test_filtros_nao_mudam_ranking_nem_media(rede: Path) -> None:
    """Ranking e "% vs media" saem da REDE, nao do recorte.

    E' o defeito do semaforo relativo que o HTML do time tem hoje: a mesma unidade muda
    de cor quando se mexe num filtro.
    """
    completa = pilot.rede_carteira(mes="2026-07")
    filtrada = pilot.rede_carteira(mes="2026-07", uf="RJ")
    de_todas = next(u for u in completa["unidades"] if u["id"] == "botafogo-rj")
    do_recorte = next(u for u in filtrada["unidades"] if u["id"] == "botafogo-rj")
    assert de_todas["metricas"] == do_recorte["metricas"]
    assert filtrada["totais"]["no_recorte"] < completa["totais"]["no_recorte"]


def test_busca_e_filtros_de_severidade(rede: Path) -> None:
    assert pilot.rede_carteira(busca="botafogo")["totais"]["no_recorte"] == 1
    assert pilot.rede_carteira(consultor="MARISE")["totais"]["no_recorte"] == 1
    alta = pilot.rede_carteira(severidade="alta")
    assert all(u["severidade"] == "alta" for u in alta["unidades"])


def _com_franqueados() -> None:
    """Dono por unidade (18/11/2026): duas do mesmo franqueado, uma de outro, o resto sem."""
    for uid, nome in (
        ("botafogo-rj", "Fernando / Franklin"),
        ("icarai-rj", "Fernando / Franklin"),
        ("augusta-sp", "Humberto Monday"),
    ):
        rede_cadastro.atribuir(uid, {"franqueado": nome}, base=pilot.CADASTRO_DIR)
    _limpar_caches()


def test_filtro_por_franqueado(rede: Path) -> None:
    """Recorte pelo DONO da unidade (`franqueado` do cadastro), no molde do consultor."""
    _com_franqueados()
    assert pilot.rede_filtros()["franqueados"] == ["Fernando / Franklin", "Humberto Monday"]

    completa = pilot.rede_carteira(mes="2026-07")
    dele = pilot.rede_carteira(mes="2026-07", franqueado="Fernando / Franklin")
    assert {u["id"] for u in dele["unidades"]} == {"botafogo-rj", "icarai-rj"}
    assert {u["franqueado"] for u in dele["unidades"]} == {"Fernando / Franklin"}
    # Ranking e "% vs media" seguem os da REDE, como em todo outro filtro.
    de_todas = next(u for u in completa["unidades"] if u["id"] == "botafogo-rj")
    assert next(u for u in dele["unidades"] if u["id"] == "botafogo-rj")["metricas"] == de_todas["metricas"]
    # Soma com os outros filtros (estreita), e nome desconhecido da' vazio, nunca a rede.
    assert pilot.rede_carteira(
        mes="2026-07", franqueado="Fernando / Franklin", consultor="MARISE"
    )["totais"]["no_recorte"] == 1
    assert pilot.rede_carteira(mes="2026-07", franqueado="Ninguem")["totais"]["no_recorte"] == 0

    inteligencia = pilot.rede_inteligencia_recorte(mes="2026-07", franqueado="Humberto Monday")
    assert inteligencia["retencao"]["no_recorte"] == 1

    linhas = list(csv.reader(io.StringIO(
        pilot.rede_carteira_csv(mes="2026-07", franqueado="Humberto Monday").body.decode("utf-8-sig")
    ), delimiter=";"))
    assert sum("AUGUSTA" in ";".join(linha) for linha in linhas) == 1
    assert not any("BOTAFOGO" in ";".join(linha) for linha in linhas)


def test_ordenacao_poe_nulos_por_ultimo_nas_duas_direcoes(rede: Path) -> None:
    """O `?? -Infinity` da v1 so funcionava em `desc`.

    Em `asc`, quem nao tinha o numero subia para o topo da lista de trabalho -- o pior
    lugar possivel para um dado ausente.
    """
    base = pilot.rede_carteira(mes="2026-07")
    unidades = [dict(u) for u in base["unidades"]]
    unidades[0]["metricas"] = {**unidades[0]["metricas"], "nps": {"atual": None}}
    for direcao in ("asc", "desc"):
        ordenadas = pilot._rede_ordenar(unidades, "nps", direcao)
        assert ordenadas[-1]["metricas"]["nps"]["atual"] is None, (
            f"nulo deveria ficar no fim tambem em {direcao}"
        )
        valores = [u["metricas"]["nps"]["atual"] for u in ordenadas[:-1]]
        assert valores == sorted(valores, reverse=direcao == "desc")


def test_empate_desempata_por_nome_na_mesma_ordem_das_duas_direcoes(rede: Path) -> None:
    """A tela e o CSV nao podem discordar sobre a ordem de duas unidades empatadas.

    Com `reverse=True`, o desempate por nome inverteria junto e as mesmas duas linhas
    sairiam trocadas entre uma superficie e outra.
    """
    empatadas = [
        {"nome": "ZULU", "prioridade": 1.0, "metricas": {"nps": {"atual": 50}}},
        {"nome": "ALFA", "prioridade": 1.0, "metricas": {"nps": {"atual": 50}}},
    ]
    for direcao in ("asc", "desc"):
        ordenadas = pilot._rede_ordenar(list(empatadas), "nps", direcao)
        assert [u["nome"] for u in ordenadas] == ["ALFA", "ZULU"], (
            f"empate deveria sair em ordem alfabetica tambem em {direcao}"
        )


def test_diagnostico_nunca_sai_de_mes_aberto(rede: Path) -> None:
    """No dia 2 do mes, o acumulado de dois dias acenderia queda na rede inteira."""
    payload = pilot.rede_carteira(mes="2026-07")
    assert payload["competencia_diagnostico"] <= payload["mes"]
    assert any("Diagn" in nota or "diagn" in nota for nota in payload["notas"]) or (
        payload["competencia_diagnostico"] == payload["mes"]
    )


def test_reguas_vigentes_sao_servidas(rede: Path) -> None:
    """A tela nao repete a regua: ela recebe a que o motor aplicou."""
    filtros = pilot.rede_filtros()
    assert filtros["reguas"]["churn"]["limiar"] == pytest.approx(8.0)
    assert filtros["meta_nps"] == 60.0
    assert set(filtros["metricas_a_validar"]) == {"inadimplente", "treino_ativo"}
    assert pilot.rede_carteira()["reguas"] == filtros["reguas"]


# ---------------------------------------------------------------------------
# Ficha
# ---------------------------------------------------------------------------


def test_ficha_traz_serie_colunar_e_coorte(rede: Path) -> None:
    ficha = pilot.rede_unidade("botafogo-rj", mes="2026-07")
    assert ficha["serie"]["meses"], "serie de 12 meses vazia"
    assert len(ficha["serie"]["faturamento"]) == len(ficha["serie"]["meses"])
    assert ficha["coorte"]["degradacao"] in {"coorte", "coorte_vizinha", "rede", "sem_dado"}
    assert ficha["coorte"]["base_rotulo"], "a degradacao tem de ser SEMPRE dita"
    assert ficha["serie_diaria"]["datas"]


def test_ficha_de_unidade_inexistente_e_404(rede: Path) -> None:
    with pytest.raises(HTTPException) as erro:
        pilot.rede_unidade("nao-existe-xx")
    assert erro.value.status_code == 404


def test_funil_nao_e_clampado(rede: Path) -> None:
    """`vendas > convertidos` em 75% das linhas da base real.

    Clampar em 100% esconderia um problema de coleta em vez de mostra-lo.
    """
    ficha = pilot.rede_unidade("botafogo-rj", mes="2026-07")
    assert "aviso" in ficha["funil"]
    assert ficha["funil"]["conversao_pct"] is not None


# ---------------------------------------------------------------------------
# Contrato v1
# ---------------------------------------------------------------------------


def test_executiva_contrato_v1_preservado(rede: Path) -> None:
    payload = pilot.executiva("RJ")
    assert set(payload) == {
        "uf", "mes", "meses", "referencia", "referencia_m1", "centro", "ultra_icon",
        "totais", "unidades",
    }
    assert set(payload["totais"]) == {
        "unidades", "com_coordenada", "faturamento", "ativos", "pagantes", "agregadores",
        "churn", "ticket", "nps", "pct_pagantes", "pct_agregadores",
    }
    assert set(payload["unidades"][0]) == {
        "nome", "lat", "lng", "faturamento", "ativos", "pagantes", "agregadores",
        "churn", "ticket", "nps", "inauguracao",
    }
    for chave in ("faturamento", "ativos", "churn", "ticket", "nps"):
        assert set(payload["totais"][chave]) == {"atual", "m1", "delta_pct"}
    json.dumps(payload, allow_nan=False)


def test_executiva_ordena_por_faturamento(rede: Path) -> None:
    faturamentos = [u["faturamento"] for u in pilot.executiva("RJ")["unidades"]]
    assert faturamentos == sorted(faturamentos, reverse=True)


def test_executiva_uf_inexistente_e_404(rede: Path) -> None:
    with pytest.raises(HTTPException) as erro:
        pilot.executiva("AC")
    assert erro.value.status_code == 404


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------


def test_csv_usa_ponto_e_virgula_e_utf8_sig(rede: Path) -> None:
    resposta = pilot.rede_carteira_csv(mes="2026-07")
    corpo = resposta.body
    assert corpo.startswith(b"\xef\xbb\xbf"), "sem BOM, o Excel pt-BR abre tudo numa coluna"
    cabecalho = corpo[3:].split(b"\r\n")[0].decode("utf-8")
    assert cabecalho.count(";") > 10 and "," not in cabecalho.split(";")[0]
    assert "attachment" in resposta.headers["Content-Disposition"]


def test_xlsx_e_pdf_saem_validos(rede: Path) -> None:
    assert pilot.rede_carteira_xlsx(mes="2026-07").body[:2] == b"PK"
    assert pilot.rede_carteira_pdf(mes="2026-07").body[:5] == b"%PDF-"
    assert pilot.rede_unidade_pdf("botafogo-rj", mes="2026-07").body[:5] == b"%PDF-"


def test_pdf_sem_caractere_fora_de_latin1(rede: Path) -> None:
    """O fpdf2 troca por "?" em silencio; o PDF sai sem compressao, entao da para olhar."""
    for pdf in (
        pilot.rede_carteira_pdf(mes="2026-07").body,
        pilot.rede_unidade_pdf("botafogo-rj", mes="2026-07").body,
    ):
        assert b"?" not in pdf, "caractere fora de latin-1 virou '?' no PDF"


def test_export_nao_escreve_em_disco(rede: Path) -> None:
    """Todo gerador devolve bytes; nada toca o filesystem."""
    antes = {p: p.stat().st_mtime_ns for p in rede.rglob("*") if p.is_file()}
    pilot.rede_carteira_csv(mes="2026-07")
    pilot.rede_carteira_xlsx(mes="2026-07")
    pilot.rede_carteira_pdf(mes="2026-07")
    pilot.rede_unidade_pdf("botafogo-rj", mes="2026-07")
    depois = {p: p.stat().st_mtime_ns for p in rede.rglob("*") if p.is_file()}
    assert antes == depois


def test_export_le_o_mesmo_payload_da_tela(rede: Path) -> None:
    """Uma unica fonte de verdade: o CSV sai do payload, nao de um segundo calculo."""
    payload = pilot.rede_carteira(mes="2026-07")
    linhas = rede_export.carteira_csv(payload).decode("utf-8-sig").splitlines()
    assert len(linhas) == len(payload["unidades"]) + 1
    assert payload["unidades"][0]["nome"] in linhas[1]


def test_modulos_de_export_sao_read_only_por_ast() -> None:
    proibidos = {
        "to_parquet", "to_csv", "to_feather", "to_excel", "to_hdf", "to_pickle", "to_sql",
        "rmtree", "rmdir", "unlink", "remove",
    }
    arvore = ast.parse(Path(rede_export.__file__).read_text(encoding="utf-8"))
    ofensas = [
        (no.func.attr, no.lineno)
        for no in ast.walk(arvore)
        if isinstance(no, ast.Call)
        and isinstance(no.func, ast.Attribute)
        and no.func.attr in proibidos
    ]
    assert not ofensas, f"o export deve devolver bytes, nunca escrever: {ofensas}"


# ---------------------------------------------------------------------------
# Cadastro — a unica escrita do piloto
# ---------------------------------------------------------------------------


def test_cadastro_atribui_consultor(rede: Path) -> None:
    resposta = pilot.rede_cadastro_atribuir(
        "augusta-sp",
        pilot.CadastroIn(versao=1, campos={"consultor": "ISAMARA"}),
        remote_user="felipe",
    )
    assert resposta["valores"]["consultor"] == "ISAMARA"
    assert resposta["versao"] == 2
    # ...e a carteira ja enxerga a mudanca (o cache do cadastro foi invalidado).
    carteira = pilot.rede_carteira(mes="2026-07")
    augusta = next(u for u in carteira["unidades"] if u["id"] == "augusta-sp")
    assert augusta["consultor"] == "ISAMARA"


def test_cadastro_rejeita_campo_fora_da_lista_branca(rede: Path) -> None:
    with pytest.raises(HTTPException) as erro:
        pilot.rede_cadastro_atribuir(
            "augusta-sp", pilot.CadastroIn(versao=1, campos={"faturamento": "999"})
        )
    assert erro.value.status_code == 422


def test_cadastro_conflito_de_versao_devolve_409(rede: Path) -> None:
    pilot.rede_cadastro_atribuir("augusta-sp", pilot.CadastroIn(versao=1, campos={"consultor": "A"}))
    with pytest.raises(HTTPException) as erro:
        pilot.rede_cadastro_atribuir(
            "augusta-sp", pilot.CadastroIn(versao=1, campos={"consultor": "B"})
        )
    assert erro.value.status_code == 409


def test_cadastro_sem_volume_devolve_503(sem_dados: Path) -> None:
    with pytest.raises(HTTPException) as erro:
        pilot.rede_cadastro_atribuir(
            "augusta-sp", pilot.CadastroIn(versao=None, campos={"consultor": "A"})
        )
    assert erro.value.status_code == 503


def test_cadastro_unidade_desconhecida_devolve_404(rede: Path) -> None:
    """Pentest Onda B #9: id fora da rede E fora do cadastro -> 404, sem unidade-fantasma."""
    with pytest.raises(HTTPException) as erro:
        pilot.rede_cadastro_atribuir(
            "unidade-fantasma-zz",
            pilot.CadastroIn(versao=1, campos={"consultor": "A"}),
            remote_user="felipe",
        )
    assert erro.value.status_code == 404
    # A chave-fantasma nao pode ter sido gravada.
    assert "unidade-fantasma-zz" not in rede_cadastro.ler_cadastro(pilot.CADASTRO_DIR).unidades


def test_escrita_do_cadastro_nao_toca_o_data_dir(rede: Path) -> None:
    """A prova que autoriza o mount `:rw`: a escrita nao sai do diretorio do cadastro."""
    fora = {
        p: p.stat().st_mtime_ns
        for p in rede.rglob("*")
        if p.is_file() and pilot.CADASTRO_DIR not in p.parents
    }
    pilot.rede_cadastro_atribuir(
        "augusta-sp", pilot.CadastroIn(versao=1, campos={"consultor": "ANDERSON"})
    )
    assert {p: p.stat().st_mtime_ns for p in fora} == fora


def test_compose_monta_somente_cadastro_e_trilha_como_volumes_de_escrita() -> None:
    """Infra: todo volume do `web` e' `:ro`, menos cadastro (DEC-023) e trilha (DEC-027).

    A lista de escritas e' EXATA de proposito: um terceiro `:rw` so entra aqui com
    DEC propria, como aconteceu com a trilha de acesso.
    """
    compose = (_REPO / "docker-compose.prod.yml").read_text(encoding="utf-8")
    bloco = compose.split("motor_expansao_web", 1)[1].split("caddy:", 1)[0]
    montagens = [
        linha.strip().lstrip("- ").split("#")[0].strip()
        for linha in bloco.splitlines()
        if linha.strip().startswith("- /opt/motor-expansao")
    ]
    escritas = [m for m in montagens if m.endswith(":rw")]
    assert escritas == [
        "/opt/motor-expansao/cadastro:/app/cadastro:rw",
        "/opt/motor-expansao/logs/acesso:/app/logs/acesso:rw",
    ]
    assert all(m.endswith((":ro", ":rw")) for m in montagens), "montagem sem modo explicito"
    assert 'MOTOR_CADASTRO_DIR: "/app/cadastro"' in compose
    assert 'MOTOR_ACESSO_LOG_DIR: "/app/logs/acesso"' in compose
    assert "/opt/motor-expansao/data" not in "".join(escritas), (
        "nenhum artefato do M1 pode ficar sob mount de escrita"
    )


# ---------------------------------------------------------------------------
# Regressoes achadas na revisao adversarial (2026-08-04)
# ---------------------------------------------------------------------------


def test_pdf_da_ficha_nao_e_engolido_pela_rota_json() -> None:
    """`{unidade_id}` casa "botafogo-rj.pdf" -- quem for declarado PRIMEIRO vence.

    Com a rota JSON antes, o pedido do PDF caia nela, a unidade "botafogo-rj.pdf" nao
    existia e o usuario recebia 404 dizendo que a unidade nao tinha dado. O PDF da ficha
    nao saia para unidade nenhuma, em producao.
    """
    escopo = {"type": "http", "method": "GET", "path": "/api/rede/unidade/botafogo-rj.pdf"}
    casadas = [
        r
        for r in pilot.app.router.routes
        if getattr(r, "matches", None) and r.matches(escopo)[0].value >= 2
    ]
    assert casadas, "nenhuma rota casa o caminho do PDF"
    assert casadas[0].endpoint is pilot.rede_unidade_pdf, (
        f"quem atende o .pdf e' {casadas[0].endpoint.__name__} -- a rota JSON esta na frente"
    )


def test_pdf_da_ficha_sai_de_verdade(rede: Path) -> None:
    assert pilot.rede_unidade_pdf("botafogo-rj", mes="2026-07").body[:5] == b"%PDF-"


def test_mes_em_curso_nao_conta_como_fechado(rede: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Do dia 25 ao fim do mes, o piso de dias sozinho declarava fechado o mes EM CURSO.

    O diagnostico entao comparava um acumulado parcial contra a media de 3 meses inteiros
    e acendia "queda de faturamento" na rede toda, todo fim de mes, em unidades cujo
    faturamento diario nao variou.
    """
    base = _base_sintetica()
    # julho para no dia 26: 26 dias de dado, mas o mes NAO acabou.
    base = base[~((base["data"].str.endswith("/07/2026")) & (base["data"].str[:2].astype(int) > 26))]
    staging = rede / "staging"
    base.to_parquet(staging / "growth_api_historico.parquet")
    _limpar_caches()

    fech = pilot._rede_fechamento()
    julho = fech[fech["competencia"] == "2026-07"]
    assert int(julho["dias_com_dado"].max()) == 26
    assert not bool(julho["mes_completo"].any()), "mes em curso nao pode ser 'completo'"
    assert rede_diagnostico.competencia_base(fech, "2026-07") == "2026-06"

    payload = pilot.rede_carteira(mes="2026-07")
    assert payload["mes_completo"] is False
    assert payload["competencia_diagnostico"] == "2026-06"
    assert any("junho" in n or "2026-06" in n for n in payload["notas"]), (
        "a tela tem de DIZER que o diagnostico vem de outro mes"
    )


def test_kpi_de_mes_fechado_bate_com_a_serie(rede: Path) -> None:
    """Em mes fechado, o numero grande e o ultimo ponto do grafico sao o MESMO numero.

    Aplicar a janela de 30 dias num mes fechado puxava cauda do mes anterior (em
    fevereiro, 3 dias de janeiro) e a receita por recorrente da tela saia ~11% acima do
    fechamento que o grafico mostrava logo abaixo.
    """
    carteira = pilot.rede_carteira(mes="2026-07")
    assert carteira["mes_completo"] is True
    ficha = pilot.rede_unidade("botafogo-rj", mes="2026-07")
    ultimo = ficha["serie"]["meses"][-1]
    assert ultimo == "2026-07"
    for chave in ("receita_por_recorrente", "churn_pct", "faturamento"):
        assert ficha["metricas"][chave]["atual"] == pytest.approx(
            ficha["serie"][chave][-1], rel=1e-6
        ), f"{chave}: o KPI diverge do ultimo ponto da serie"


def test_serie_meses_vem_do_servidor_e_termina_no_ultimo_fechado(rede: Path) -> None:
    """O cliente NAO consegue derivar os rotulos: com a competencia aberta, a serie
    termina no mes anterior, e contar para tras a partir de `mes` desloca o grafico
    inteiro em um mes."""
    for mes, ultimo in (("2026-07", "2026-07"), ("2026-08", "2026-07")):
        payload = pilot.rede_carteira(mes=mes)
        assert payload["serie_meses"], "serie_meses vazia"
        assert payload["serie_meses"][-1] == ultimo
        assert payload["serie_meses"] == sorted(payload["serie_meses"])
        tamanho = max(len(u["sparkline"]) for u in payload["unidades"])
        assert tamanho == len(payload["serie_meses"])


def test_delta_de_media_ponderada_usa_a_mesma_cesta(rede: Path) -> None:
    """Comparar a media com as unidades novas dentro contra a de M-1 sem elas mostrava o
    NPS da rede despencando num mes de inauguracao sem que nada tivesse caido."""
    payload = pilot.rede_carteira(mes="2026-07")
    nps = payload["kpis"]["nps"]
    assert nps["atual"] is not None and nps["m1"] is not None
    # BANGU inaugurou em 03/2026 e entra nos dois meses; o delta tem de ser modesto.
    assert abs(nps["delta_pct"] or 0) < 5.0


def test_csv_neutraliza_formula(rede: Path) -> None:
    """O cadastro e' editavel pela tela: um `consultor` que comece com "=" viraria formula
    viva ao abrir o CSV (HYPERLINK/WEBSERVICE exfiltram, DDE executa)."""
    payload = pilot.rede_carteira(mes="2026-07")
    payload = {**payload, "unidades": [{**payload["unidades"][0], "consultor": '=HYPERLINK("http://x")'}]}
    linha = rede_export.carteira_csv(payload).decode("utf-8-sig").splitlines()[1]
    assert "'=HYPERLINK" in linha
    assert ";=HYPERLINK" not in linha


def test_serie_da_rede_vem_pronta_e_bate_com_as_unidades(rede: Path) -> None:
    """Tela, CSV e PDF desenham a MESMA série porque só existe uma conta, no servidor."""
    payload = pilot.rede_carteira(mes="2026-07")
    assert len(payload["serie_rede"]) == len(payload["serie_meses"])
    # o último mês da série é a soma do faturamento fechado das unidades do recorte
    esperado = sum(
        u["sparkline"][-1] for u in payload["unidades"] if u["sparkline"] and u["sparkline"][-1]
    )
    assert payload["serie_rede"][-1] == pytest.approx(esperado, rel=1e-6)
    # o recorte filtrado tem série menor que a rede inteira
    so_rj = pilot.rede_carteira(mes="2026-07", uf="RJ")
    assert so_rj["serie_rede"][-1] < payload["serie_rede"][-1]


def test_pdf_traz_os_graficos_do_dashboard(rede: Path) -> None:
    """O PDF circula sem a tela ao lado: os mesmos cards têm de estar nele."""
    carteira = pilot.rede_carteira_pdf(mes="2026-07").body
    for marcador in (
        b"Faturamento da rede no recorte",
        b"Fila de trabalho",
        b"Recorrentes x agregadores",
    ):
        assert marcador in carteira, f"{marcador!r} ausente do PDF da carteira"

    ficha = pilot.rede_unidade_pdf("botafogo-rj", mes="2026-07").body
    for marcador in (
        b"Faturamento nos 13 meses fechados",
        b"Alunos ativos",
        b"Funil comercial",
        b"NPS contra a meta",
        b"mesma maturidade",
    ):
        assert marcador in ficha, f"{marcador!r} ausente do PDF da ficha"
    assert b"?" not in carteira and b"?" not in ficha


def test_percentil_de_metrica_invertida_diz_a_direcao(rede: Path) -> None:
    """"Churn - percentil 92" lê como elogio e é o oposto: 92% dos pares têm churn menor."""
    ficha = pilot.rede_unidade_pdf("botafogo-rj", mes="2026-07").body
    assert b"Churn (menor \xe9 melhor)" in ficha or b"menor \xe9 melhor" in ficha


# ---------------------------------------------------------------------------
# Panorama do recorte — SSS filtrado, series, funil, faixas e coortes
# ---------------------------------------------------------------------------


def _base_anual() -> pd.DataFrame:
    """Base com os DOIS anos, que a `_base_sintetica` nao tem.

    A base sintetica das outras suites vive so em 2026, entao o SSS nasce indisponivel
    nela — e' por isso que o SSS ignorando o filtro passou meses sem teste. Aqui ha tres
    unidades:

    * ANTIGA A (MARISE)  - nos dois anos, 100k -> 150k  (+50%)
    * ANTIGA B (JAILSON) - nos dois anos, 200k -> 180k  (-10%)
    * NOVA C   (MARISE)  - so em 2026, inaugurada em 01/03/2026 (fora da base comparavel)

    Logo a rede inteira cresce (150+180)/(100+200) = +10%, que nao e' nem o numero de
    MARISE nem o de JAILSON. Com o filtro ignorado, os tres davam +10%.
    """
    perfis = [
        ("ANTIGA A", "01/01/2020", 100_000.0, 150_000.0, 100.0, 50.0, (2025, 2026)),
        ("ANTIGA B", "01/01/2020", 200_000.0, 180_000.0, 900.0, 90.0, (2025, 2026)),
        ("NOVA C", "01/03/2026", 0.0, 90_000.0, 50.0, 25.0, (2026,)),
    ]
    linhas: list[dict[str, object]] = []
    for nome, inauguracao, fat_2025, fat_2026, visitas, convertidos, anos in perfis:
        for ano in anos:
            # Agosto entra com TRES dias de propria: e' a competencia em curso, que prova
            # que as faixas absolutas nao podem sair dela.
            for numero_mes, dias in ((6, None), (7, None), (8, 3)):
                faturamento = fat_2025 if ano == 2025 else fat_2026
                linhas += mes_sintetico(
                    nome,
                    ano,
                    numero_mes,
                    uf="SP",
                    master="ULTRA",
                    inauguracao=inauguracao,
                    dias=dias,
                    cumulativas={
                        "faturamento": faturamento,
                        "faturamento_sem_agregador": faturamento,
                        "cancelados": 30.0,
                        "visitas": visitas,
                        "convertidos": convertidos,
                        "novos_alunos": 40.0,
                        "vendas": 45.0,
                    },
                    snapshots={
                        "pagantes": 1_000.0,
                        "ativos_total": 1_200.0,
                        "alunos_gympass": 100.0,
                        "alunos_totalpass": 100.0,
                        "NPS": 60.0,
                        "em_cobranca": 50.0,
                        "inadimplente": 40.0,
                        "treino_ativo": 50.0,
                    },
                )
    return pd.DataFrame(linhas)


@pytest.fixture
def rede_anual(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """App apontado para a base de dois anos, com consultor em todas as unidades."""
    staging = tmp_path / "staging"
    staging.mkdir(parents=True)
    _base_anual().to_parquet(staging / "growth_api_historico.parquet")

    cadastro_dir = tmp_path / "cadastro"
    cadastro_dir.mkdir()
    rede_cadastro.gravar_cadastro(
        rede_cadastro.Cadastro(
            versao=1,
            atualizado_em="2026-08-04T00:00:00+00:00",
            unidades={
                "antiga-a-sp": {"consultor": "MARISE"},
                "antiga-b-sp": {"consultor": "JAILSON"},
                "nova-c-sp": {"consultor": "MARISE"},
            },
        ),
        cadastro_dir,
    )

    monkeypatch.setattr(pilot, "STAGING_DIR", staging)
    monkeypatch.setattr(pilot, "GROWTH_PARQUET", staging / "growth_api_historico.parquet")
    monkeypatch.setattr(pilot, "ULTRA_PERF_PARQUET", staging / "nao_existe.parquet")
    monkeypatch.setattr(pilot, "ULTRA_MAPEADAS_PARQUET", staging / "tambem_nao.parquet")
    # A planilha financeira TAMBEM precisa ser declarada ausente, como as duas acima:
    # `FATURAMENTO_FINANCEIRO_PARQUET` e constante de MODULO, resolvida no import a partir
    # do `STAGING_DIR` de ENTAO — repontar `STAGING_DIR` aqui em cima nao a move. Sem esta
    # linha, quem tiver `data/staging/faturamento_financeiro.parquet` no worktree le a
    # planilha REAL. Passava por acidente ate 2026-09-02, quando `STAGING_DIR` derivava do
    # `_DEFAULT_DATA` cravado no Downloads de UMA maquina: com a raiz quebrada, nenhum
    # arquivo existia. O Bloco A (DEC-047) trocou a raiz pelo `data/` do repo.
    monkeypatch.setattr(
        pilot, "FATURAMENTO_FINANCEIRO_PARQUET", staging / "sem_planilha.parquet"
    )
    monkeypatch.setattr(pilot, "CADASTRO_DIR", cadastro_dir)
    _limpar_caches()
    yield tmp_path
    _limpar_caches()


def test_sss_segue_o_filtro_do_recorte(rede_anual: Path) -> None:
    """O defeito: a carteira de um consultor exibia o SSS da rede inteira.

    `_rede_sss` nascia dentro de `_rede_mes`, que tem cache por MES e nenhuma nocao de
    filtro. Medido na base de producao em 2026-08-10, MARISE (24 unidades), GUILHERME (5)
    e a rede (92) devolviam os TRES o mesmo `+6,2%` sobre `60 unidades`.
    """
    rede = pilot._rede_carteira_payload(mes="2026-07")
    marise = pilot._rede_carteira_payload(mes="2026-07", consultor="MARISE")
    jailson = pilot._rede_carteira_payload(mes="2026-07", consultor="JAILSON")

    assert rede["sss"]["metricas"]["faturamento"]["var_pct"] == pytest.approx(10.0)
    assert marise["sss"]["metricas"]["faturamento"]["var_pct"] == pytest.approx(50.0)
    assert jailson["sss"]["metricas"]["faturamento"]["var_pct"] == pytest.approx(-10.0)

    # A cesta comparavel de MARISE e' UMA unidade: a NOVA C nao existia ha um ano.
    assert marise["sss"]["unidades"] == 1
    assert marise["sss"]["unidades_recorte"] == 2
    assert marise["sss"]["unidades_fora"] == 1
    assert rede["sss"]["unidades"] == 2
    assert rede["sss"]["unidades_fora"] == 1


def test_sss_nunca_conta_mais_unidades_do_que_o_recorte(rede_anual: Path) -> None:
    """Invariante barata que denuncia a volta do vazamento: comparavel <= recorte."""
    for filtro in ({}, {"consultor": "MARISE"}, {"consultor": "JAILSON"}, {"uf": "SP"}):
        payload = pilot._rede_carteira_payload(mes="2026-07", **filtro)
        # Sem esta linha o teste passaria com o filtro DEVOLVENDO VAZIO (0 <= 0).
        assert payload["totais"]["no_recorte"] > 0, filtro
        assert payload["sss"]["unidades"] <= payload["totais"]["no_recorte"]
        assert payload["sss"]["unidades_recorte"] == payload["totais"]["no_recorte"]


def test_sss_serie_recalcula_a_base_mes_a_mes(rede_anual: Path) -> None:
    """Cada ponto tem a SUA base comparavel; sem o ano anterior, o ponto fica vazio."""
    payload = pilot._rede_carteira_payload(mes="2026-07")
    serie = payload["sss"]["serie"]
    assert serie["meses"] == payload["serie_meses"]

    por_mes = dict(zip(serie["meses"], serie["var_pct"], strict=True))
    tamanho = dict(zip(serie["meses"], serie["unidades"], strict=True))
    # 2026-07 contra 2025-07: as duas antigas, +10%.
    assert por_mes["2026-07"] == pytest.approx(10.0)
    assert tamanho["2026-07"] == 2
    # 2025-06 nao tem 2024-06 na base: buraco honesto, nao zero.
    assert por_mes["2025-06"] is None
    assert tamanho["2025-06"] == 0


def test_series_do_painel_sao_a_mesma_conta_da_serie_da_rede(rede_anual: Path) -> None:
    """`serie_rede` (que o CSV e o PDF leem) tem de ser LITERALMENTE series.faturamento."""
    payload = pilot._rede_carteira_payload(mes="2026-07")
    assert payload["series"]["faturamento"] == payload["serie_rede"]
    for chave, valores in payload["series"].items():
        assert len(valores) == len(payload["serie_meses"]), chave


def test_series_de_taxa_sao_ponderadas_nunca_somadas(rede_anual: Path) -> None:
    """Somar churn de N unidades nao significa nada; a media SIMPLES deforma por tamanho.

    ANTIGA A converte 50% (50/100) e ANTIGA B converte 10% (90/900). A media simples da
    30%; a ponderada por visitas da 14%, que e' a conversao real do recorte.
    """
    payload = pilot._rede_carteira_payload(mes="2026-07", consultor=None, uf="SP")
    indice = payload["serie_meses"].index("2026-07")
    conversao = payload["series"]["conversao_pct"][indice]
    assert conversao == pytest.approx(15.71, abs=0.1)  # (50+90+25) / (100+900+50)

    so_antigas = pilot._rede_carteira_payload(mes="2026-07", busca="ANTIGA")
    indice = so_antigas["serie_meses"].index("2026-07")
    assert so_antigas["series"]["conversao_pct"][indice] == pytest.approx(14.0, abs=0.1)


def test_funil_do_recorte_soma_etapas_e_reusa_a_conversao_do_kpi(rede_anual: Path) -> None:
    """Duas contas para o mesmo percentual e' como a mesma unidade ganha dois numeros."""
    payload = pilot._rede_carteira_payload(mes="2026-07")
    funil = payload["funil"]
    assert funil["visitas"] == 1_050  # 100 + 900 + 50
    assert funil["convertidos"] == 165  # 50 + 90 + 25
    assert funil["conversao_pct"] == payload["kpis"]["conversao_pct"]["atual"]
    # `vendas` (135) e' menor que `convertidos` (165): o funil fecha, nao ha aviso.
    assert funil["aviso"] is None


def test_faixas_saem_do_ultimo_mes_fechado_mesmo_com_a_competencia_em_curso(
    rede_anual: Path,
) -> None:
    """As faixas sao limiares de MES INTEIRO.

    Em 2026-08 a base tem tres dias; aplicar `Critico <150k` ao acumulado de tres dias
    jogaria a rede inteira em Critico. E' a mesma razao pela qual o diagnostico nao roda
    sobre mes aberto.
    """
    aberto = pilot._rede_carteira_payload(mes="2026-08")
    assert aberto["mes_completo"] is False
    assert aberto["faixas"]["competencia"] == "2026-07"

    contagem = {f["chave"]: f["n"] for f in aberto["faixas"]["faixas"]}
    assert contagem["critico"] == 1  # NOVA C, 90k
    assert contagem["regular"] == 2  # ANTIGA A (150k) e ANTIGA B (180k)
    assert sum(contagem.values()) == aberto["totais"]["no_recorte"]


def test_faixas_e_coortes_fecham_com_o_total_do_recorte(rede_anual: Path) -> None:
    """Barra que nao fecha com o total mente por omissao."""
    for filtro in ({}, {"consultor": "MARISE"}):
        payload = pilot._rede_carteira_payload(mes="2026-07", **filtro)
        total = payload["totais"]["no_recorte"]
        assert sum(f["n"] for f in payload["faixas"]["faixas"]) == total
        assert sum(c["n"] for c in payload["coortes"]) == total


def test_churn_do_mes_em_curso_comeca_zerado_e_escala(rede_anual: Path) -> None:
    """O churn ACUMULA dentro do mes; nao e' uma janela movel de 30 dias.

    Ate 2026-08-10 o mes em curso reconstruia uma janela de ~30 dias, entao no dia 1o o
    churn ja nascia em ~5,7% arrastando a cauda do mes anterior -- e nao batia com a
    contagem de cancelamentos ao lado (BERRINI aparecia com "7,8% (0)"). A definicao do
    negocio e' `cancelados no mes / recorrentes no INICIO do mes`, a mesma do mes fechado.
    """
    aberto = pilot._rede_carteira_payload(mes="2026-08")
    assert aberto["mes_completo"] is False

    # 3 dias de agosto: 30 cancelados por unidade sobre 1.000 recorrentes com que o mes
    # comecou (o fechamento de julho), e nao sobre a foto do mesmo dia-do-mes.
    for unidade in aberto["unidades"]:
        metricas = unidade["metricas"]
        cancelados = metricas["cancelados"]["atual"]
        churn = metricas["churn_pct"]["atual"]
        assert cancelados == 30
        assert churn == pytest.approx(3.0, abs=0.05), unidade["nome"]

    # E o percentual do KPI fecha com a contagem do proprio KPI: sem isso, o numero entre
    # parenteses na tela contradiz o percentual ao lado dele.
    kpis = aberto["kpis"]
    esperado = 100.0 * kpis["cancelados"]["atual"] / kpis["pagantes"]["atual"]
    assert kpis["churn_pct"]["atual"] == pytest.approx(esperado, rel=0.02)


def test_churn_de_mes_fechado_nao_mudou(rede_anual: Path) -> None:
    """A mudanca do mes em curso nao pode mexer no mes fechado, que ja estava certo."""
    fechado = pilot._rede_carteira_payload(mes="2026-07")
    for unidade in fechado["unidades"]:
        metricas = unidade["metricas"]
        assert metricas["cancelados"]["atual"] == 30
        # 30 cancelados sobre os 1.000 recorrentes do fechamento de junho.
        assert metricas["churn_pct"]["atual"] == pytest.approx(3.0, abs=0.05), unidade["nome"]


def test_faturamento_viaja_com_centavo(rede_anual: Path) -> None:
    """Arredondar no servidor e' irreversivel: o centavo nao se recupera no cliente.

    O time de campo confere o faturamento contra o extrato, entao `R$ 18.470` e
    `R$ 18.470,37` sao a MESMA linha do payload e precisam ser numeros diferentes.
    """
    payload = pilot._rede_carteira_payload(mes="2026-07")
    assert pilot._rede_casas("faturamento") == 2
    assert pilot._rede_casas("receita_por_recorrente") == 2
    assert pilot._rede_casas("ativos") == 0, "contagem de gente nao tem centavo"

    unidade = payload["unidades"][0]
    bruto = pilot._rede_mes("2026-07")["atual"].set_index("unidade_id")
    esperado = float(bruto.loc[unidade["id"], "faturamento"])
    assert unidade["metricas"]["faturamento"]["atual"] == pytest.approx(esperado, abs=0.005)


def test_sss_por_unidade_soma_o_sss_do_recorte(rede_anual: Path) -> None:
    """A lista unidade a unidade tem de fechar com o agregado; senao uma das duas mente."""
    payload = pilot._rede_carteira_payload(mes="2026-07")
    comparaveis = [u for u in payload["unidades"] if (u.get("sss") or {}).get("var_pct") is not None]
    assert len(comparaveis) == payload["sss"]["unidades"]

    soma_atual = sum(u["sss"]["faturamento"] for u in comparaveis)
    soma_antes = sum(u["sss"]["ano_anterior"] for u in comparaveis)
    assert soma_atual == pytest.approx(payload["sss"]["metricas"]["faturamento"]["atual"], abs=0.05)
    assert soma_antes == pytest.approx(
        payload["sss"]["metricas"]["faturamento"]["ano_anterior"], abs=0.05
    )

    # A unidade sem base comparavel continua na lista, com var_pct nulo em vez de sumir.
    nova = next(u for u in payload["unidades"] if u["id"] == "nova-c-sp")
    assert nova["sss"] is not None
    assert nova["sss"]["var_pct"] is None


def test_periodo_anterior_preserva_a_ancora(rede_anual: Path) -> None:
    """Contra o que o "vs anterior" compara, nos tres casos.

    O caso 2 e' o que custou caro: sem ele, o acumulado do mes em curso (1 a 03/08, que e'
    o padrao da tela) comparava com 29 a 31/07 e o faturamento da rede abria a tela com
    +190,3%. Nao e' crescimento -- a mensalidade e' cobrada no comeco do mes, entao os tres
    primeiros dias valem varias vezes os tres ultimos.
    """
    inteiro = pilot._rede_carteira_payload(mes="2026-07")
    assert inteiro["periodo"] == {
        "inicio": "2026-07-01",
        "fim": "2026-07-31",
        "dias": 31,
        "mes_inteiro": True,
        # julho já fechou na base (que vai até 03/08): o churn é o Churn Médio (DEC-088).
        "churn_medio": True,
    }
    assert inteiro["periodo_anterior"] == {"inicio": "2026-06-01", "fim": "2026-06-30"}

    # Ancorado no dia 1o, mas sem fechar o mes: mesmo intervalo de dias do mes anterior.
    mtd = pilot._rede_carteira_payload(mes="2026-08")
    assert mtd["periodo"]["inicio"] == "2026-08-01"
    assert mtd["periodo"]["mes_inteiro"] is False
    assert mtd["periodo_anterior"] == {"inicio": "2026-07-01", "fim": "2026-07-03"}

    # Janela solta: a imediatamente anterior, de mesmo tamanho.
    solta = pilot._rede_carteira_payload(inicio="2026-07-15", fim="2026-07-24")
    assert solta["periodo"]["dias"] == 10
    assert solta["periodo_anterior"] == {"inicio": "2026-07-05", "fim": "2026-07-14"}


def test_periodo_grampeia_no_que_a_base_cobre(rede_anual: Path) -> None:
    """Arrastar o calendario para fora da base pede "desde o comeco", nao um erro."""
    payload = pilot._rede_carteira_payload(inicio="1999-01-01", fim="2099-12-31")
    limites = payload["limites"]
    assert payload["periodo"]["inicio"] == limites["min"]
    assert payload["periodo"]["fim"] == limites["max"]

    with pytest.raises(HTTPException) as erro:
        pilot._rede_carteira_payload(inicio="2026-07-31", fim="2026-07-01")
    assert erro.value.status_code == 400


def test_periodo_de_mes_inteiro_reproduz_a_competencia(rede_anual: Path) -> None:
    """O calendario nao pode mudar numero nenhum de quem escolhe um mes fechado.

    E' a invariante que protege o contrato v1 e os links antigos: `mes=2026-07` e
    `inicio=2026-07-01&fim=2026-07-31` sao a MESMA pergunta.
    """
    por_competencia = pilot._rede_carteira_payload(mes="2026-07")
    por_intervalo = pilot._rede_carteira_payload(inicio="2026-07-01", fim="2026-07-31")
    assert por_competencia["kpis"] == por_intervalo["kpis"]
    assert por_competencia["sss"] == por_intervalo["sss"]
    assert por_competencia["funil"] == por_intervalo["funil"]
    assert [u["metricas"] for u in por_competencia["unidades"]] == [
        u["metricas"] for u in por_intervalo["unidades"]
    ]


def test_panorama_e_json_safe(rede_anual: Path) -> None:
    """NaN/inf no payload quebram o `JSON.parse` do navegador com erro ilegivel."""
    payload = pilot._rede_carteira_payload(mes="2026-07", consultor="MARISE")
    texto = json.dumps(payload, allow_nan=False)
    assert "NaN" not in texto
    assert "Infinity" not in texto


def test_notas_cabem_no_pdf(rede_anual: Path) -> None:
    """Nota com tipografia fora de latin-1 chega ao franqueado como "?".

    O core font do fpdf2 e' latin-1 e `pdf_base.ascii_seguro` troca o que nao couber por
    "?" DE PROPOSITO, para o autor consertar o texto-fonte. So' que isso nao falha em lugar
    nenhum: o PDF sai valido, com um "?" no meio da frase, e so' quem OLHA o arquivo
    percebe. Aconteceu com um travessao numa nota de fonte do faturamento, e a suite
    inteira passou verde. Este teste fecha o buraco.
    """
    fora_de_latin1: list[tuple[str, str]] = []
    for janela in ({"mes": "2026-07"}, {"inicio": "2026-07-01", "fim": "2026-07-10"}):
        payload = pilot._rede_carteira_payload(**janela)
        for nota in payload["notas"]:
            ruins = sorted({c for c in nota if c.encode("latin-1", "replace") == b"?" and c != "?"})
            if ruins:
                fora_de_latin1.append((str(ruins), nota))
    assert not fora_de_latin1, f"tipografia que vira '?' no PDF: {fora_de_latin1}"


def test_todas_as_frases_de_fonte_cabem_no_pdf() -> None:
    """Mesma trava, direto no catalogo: as tres frases de origem do faturamento."""
    for frase in pilot._NOTA_DO_PERIODO.values():
        assert frase.encode("latin-1", "replace").decode("latin-1") == frase, frase


# ---------------------------------------------------------------------------
# Procedencia do faturamento: o que a tela e o PDF DIZEM sobre a fonte
# ---------------------------------------------------------------------------


def _com_financeiro(mp: pytest.MonkeyPatch, competencias: tuple[str, ...]) -> None:
    """Planilha do Financeiro sintetica, cobrindo so' as competencias pedidas.

    E' o que permite exercitar `financeiro`/`ux`/`misto` sem parquet real: a fixture da
    rede nao tem planilha, entao sem isto todo teste veria so' o caminho `ux`.
    """
    linhas = [
        {
            "cod_unidade": "01", "unidade_planilha": nome, "unidade_ux": nome,
            "tem_depara": True, "competencia": mes, "faturamento": 999_000.0,
            "vendas_ux": 800_000.0, "gympass": 199_000.0, "totalpass": 0.0, "tem_saude": 0.0,
        }
        for nome in ("ANTIGA A", "ANTIGA B", "NOVA C")
        for mes in competencias
    ]
    mp.setattr(pilot, "_rede_faturamento_financeiro", lambda: pd.DataFrame(linhas))
    _limpar_caches()


def test_fonte_do_faturamento_sem_planilha_e_toda_ux(rede_anual: Path) -> None:
    """Sem planilha, a aba segue inteira na Growth — e o payload diz isso."""
    payload = pilot._rede_carteira_payload(mes="2026-07")
    fonte = payload["fonte_faturamento"]
    assert fonte["periodo"] == "ux"
    assert set(fonte["por_mes"].values()) == {"ux"}
    assert fonte["unidades_sem_par"] == []
    assert any("TEM SAÚDE é deduzido" in n for n in payload["notas"])


def test_fonte_do_faturamento_com_planilha_no_mes_fechado(
    rede_anual: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mes fechado coberto: periodo E serie saem `financeiro`, e a nota muda junto."""
    COBERTOS = ("2026-06", "2026-07")
    _com_financeiro(monkeypatch, COBERTOS)

    payload = pilot._rede_carteira_payload(mes="2026-07")
    fonte = payload["fonte_faturamento"]

    assert fonte["periodo"] == "financeiro"
    # Mes que a planilha NAO cobre continua na Growth, e o payload nao mente sobre isso.
    fora = {m for m in fonte["por_mes"] if m not in COBERTOS}
    assert fora, "a serie tem de ter mes fora da cobertura, senao o teste nao prova nada"
    assert {fonte["por_mes"][m] for m in COBERTOS} == {"financeiro"}
    assert {fonte["por_mes"][m] for m in fora} == {"ux"}
    assert any("planilha do Financeiro" in n for n in payload["notas"])
    assert any("mês(es) da série ainda sem cobertura" in n for n in payload["notas"])
    assert not any("TEM SAÚDE é deduzido" in n for n in payload["notas"])


def test_periodo_parcial_avisa_que_o_topo_e_da_growth(
    rede_anual: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A planilha e' MENSAL: numa janela parcial o quarteto do topo nao pode se dizer dela."""
    _com_financeiro(monkeypatch, ("2026-06", "2026-07"))

    payload = pilot._rede_carteira_payload(inicio="2026-07-01", fim="2026-07-10")

    assert payload["fonte_faturamento"]["periodo"] == "ux"
    assert pilot._NOTA_DO_PERIODO["ux"] in payload["notas"]


def test_origem_dominante_denuncia_recorte_misturado() -> None:
    """Recorte em que as unidades discordam sai `misto`, nunca uma das duas pontas."""
    assert pilot._origem_dominante(pd.DataFrame()) == "ux"
    so_uma = pd.DataFrame({"origem_faturamento": ["financeiro", "financeiro"]})
    assert pilot._origem_dominante(so_uma) == "financeiro"
    discordam = pd.DataFrame({"origem_faturamento": ["financeiro", "ux"]})
    assert pilot._origem_dominante(discordam) == "misto"


def test_filtro_de_master_casa_pelo_nome_do_franqueado_e_nao_pela_sigla(rede: Path) -> None:
    """O recorte de master responde "as unidades de QUEM", nao "de que regiao".

    Ate 2026-09-09 o filtro lia a coluna `master` da Growth, que e' sigla de REGIAO --
    e uma regiao tem varios franqueados (medido na base real: `DF/GO` cobre 2 masters,
    `RJ/SP 01` cobre 3, `ULTRA` cobre 3). Na fixture, BOTAFOGO e ICARAI dividem a mesma
    sigla `RJ/SP 01` e tem masters DIFERENTES: e' exatamente o par que a regua antiga
    nao conseguia separar, e por isso ele esta aqui.
    """
    filtros = pilot.rede_filtros()
    assert "Fernando Nero" in filtros["masters"]
    assert "Dalmo Ribeiro" in filtros["masters"]
    # A sigla nao pode mais aparecer no vocabulario do filtro...
    assert "RJ/SP 01" not in filtros["masters"]
    # ...mas segue servida a parte, para quem precisar do recorte por regiao.
    assert "RJ/SP 01" in filtros["masters_regiao"]

    carteira = pilot.rede_carteira(master="Fernando Nero")
    nomes = {u["nome"] for u in carteira["unidades"]}
    assert nomes == {"BOTAFOGO - RJ"}, nomes

    # Mesma sigla, outro master: a regua antiga devolveria as duas juntas.
    outra = pilot.rede_carteira(master="Dalmo Ribeiro")
    assert {u["nome"] for u in outra["unidades"]} == {"ICARAI - RJ"}


def test_filtro_de_master_desconhecido_nao_derruba_a_rota(rede: Path) -> None:
    """Master sem nenhuma unidade devolve carteira VAZIA, nunca a rede inteira.

    Um filtro que nao casa com nada e' o caso em que um `if` mal escrito silenciosamente
    NAO filtra -- e a tela mostraria a rede toda sob o nome de um franqueado.
    """
    carteira = pilot.rede_carteira(master="Quem Nao Existe")
    assert carteira["unidades"] == []


def test_linha_da_rede_inteira_media_e_total(rede: Path) -> None:
    """A linha da rede no topo da Carteira (pedido do Vinicius, 2026-10-20).

    `media` e' a referencia do "% vs media" de cada celula -- recalculada aqui a mao das
    unidades comparaveis --, `total` e' o mesmo numero dos KPIs, e as duas IGNORAM o filtro.
    """
    completa = pilot.rede_carteira(mes="2026-07")
    filtrada = pilot.rede_carteira(mes="2026-07", uf="RJ")
    linha = completa["rede_inteira"]
    assert linha == filtrada["rede_inteira"]
    assert set(linha["media"]) == set(linha["total"]) == {"faturamento", "ativos", "churn_pct", "cancelados", "nps"}

    comparaveis = [u for u in completa["unidades"] if u["comparavel"]]
    assert linha["n_comparaveis"] == len(comparaveis)
    assert linha["n_unidades"] == completa["totais"]["rede"]
    for chave in ("faturamento", "ativos", "churn_pct", "nps"):
        valores = [u["metricas"][chave]["atual"] for u in comparaveis if u["metricas"][chave]["atual"] is not None]
        # Tolerancia de arredondamento: a celula sai com 1 casa nas taxas, a media vem do bruto.
        assert linha["media"][chave]["atual"] == pytest.approx(sum(valores) / len(valores), abs=0.06)

    # Uma unidade com o valor da media le ~0% no "% vs media" da propria celula.
    u = comparaveis[0]
    m = u["metricas"]["faturamento"]
    esperado = 100.0 * (m["atual"] - linha["media"]["faturamento"]["atual"]) / linha["media"]["faturamento"]["atual"]
    assert m["vs_media_pct"] == pytest.approx(esperado, abs=0.1)

    # Total = KPI do topo sem filtro (soma para volume, taxa ponderada para churn e NPS).
    for chave in linha["total"]:
        assert linha["total"][chave] == completa["kpis"][chave]


# ---------------------------------------------------------------------------
# Churn Médio (DEC-088): período com mês FECHADO não acumula o churn
# ---------------------------------------------------------------------------

#: out/2025 (a base de novembro) a out/2026 inteiros + 17 dias de novembro/2026 (em curso).
_MESES_UM_ANO: tuple[tuple[int, int], ...] = (
    (2025, 10),
    (2025, 11),
    (2025, 12),
    *((2026, m) for m in range(1, 12)),
)
_DOZE_MESES = ["2025-11", "2025-12"] + [f"2026-{m:02d}" for m in range(1, 11)]


def _base_um_ano() -> pd.DataFrame:
    """Três unidades, com recorrentes e cancelados que mudam mês a mês.

    * ANTIGA X e ANTIGA Y operam a série inteira (inauguradas em 2020 e 2021).
    * NOVA Z inaugura em 15/03/2026 e só tem dado a partir daí: março é o mês de abertura
      (sem base de churn) e, olhado de abril, o período anterior NÃO foi inteiro.
    """
    perfis = [
        ("ANTIGA X", "01/01/2020", None, 1_000.0, 25.0, 40.0, 7.0, 4),
        ("ANTIGA Y", "01/01/2021", None, 500.0, 10.0, 30.0, 5.0, 3),
        ("NOVA Z", "15/03/2026", (2026, 3), 300.0, 20.0, 10.0, 2.0, 5),
    ]
    linhas: list[dict[str, object]] = []
    for nome, inauguracao, desde, pag0, pag_passo, canc0, canc_passo, ciclo in perfis:
        for ordem, (ano, numero_mes) in enumerate(_MESES_UM_ANO):
            if desde is not None and (ano, numero_mes) < desde:
                continue
            dias = mes_sintetico(
                nome,
                ano,
                numero_mes,
                uf="SP",
                master="ULTRA",
                inauguracao=inauguracao,
                dias=17 if (ano, numero_mes) == (2026, 11) else None,
                cumulativas={
                    "faturamento": 200_000.0 + 1_000.0 * ordem,
                    "faturamento_sem_agregador": 180_000.0,
                    "cancelados": canc0 + canc_passo * (ordem % ciclo),
                    "visitas": 200.0,
                    "convertidos": 100.0,
                    "novos_alunos": 60.0,
                    "vendas": 70.0,
                },
                snapshots={
                    "pagantes": pag0 + pag_passo * ordem,
                    "ativos_total": pag0 + pag_passo * ordem + 200.0,
                    "alunos_gympass": 100.0,
                    "alunos_totalpass": 100.0,
                    "NPS": 60.0 + ordem,
                    "em_cobranca": 50.0,
                    "inadimplente": 40.0,
                    "treino_ativo": 50.0,
                },
            )
            if (ano, numero_mes) == (2026, 3) and desde == (2026, 3):
                # Abriu no dia 15: nada antes disso.
                dias = [d for d in dias if int(str(d["data"])[:2]) >= 15]
            linhas += dias
    return pd.DataFrame(linhas)


@pytest.fixture
def rede_um_ano(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """App apontado para a base de um ano (até 17/11/2026), sem planilha do Financeiro."""
    staging = tmp_path / "staging"
    staging.mkdir(parents=True)
    _base_um_ano().to_parquet(staging / "growth_api_historico.parquet")
    cadastro_dir = tmp_path / "cadastro"
    cadastro_dir.mkdir()
    rede_cadastro.gravar_cadastro(
        rede_cadastro.Cadastro(versao=1, atualizado_em="2026-11-17T00:00:00+00:00", unidades={}),
        cadastro_dir,
    )
    monkeypatch.setattr(pilot, "STAGING_DIR", staging)
    monkeypatch.setattr(pilot, "GROWTH_PARQUET", staging / "growth_api_historico.parquet")
    monkeypatch.setattr(pilot, "ULTRA_PERF_PARQUET", staging / "nao_existe.parquet")
    monkeypatch.setattr(pilot, "ULTRA_MAPEADAS_PARQUET", staging / "tambem_nao.parquet")
    monkeypatch.setattr(pilot, "FATURAMENTO_FINANCEIRO_PARQUET", staging / "sem_planilha.parquet")
    monkeypatch.setattr(pilot, "CADASTRO_DIR", cadastro_dir)
    _limpar_caches()
    yield tmp_path
    _limpar_caches()


def _churn_mensal_da_unidade(unidade_id: str, meses: list[str]) -> list[float]:
    """O churn de cada mês pelo fechamento MENSAL da tela (o dos pontos da série)."""
    cheio = pilot._rede_fechamento()
    linhas = cheio[(cheio["unidade_id"] == unidade_id) & cheio["competencia"].isin(meses)]
    return [float(v) for v in pd.to_numeric(linhas["churn_pct"], errors="coerce").dropna()]


def test_churn_medio_de_doze_meses_e_a_media_dos_pontos_do_grafico(rede_um_ano: Path) -> None:
    """O defeito: 12 meses davam ~70% de churn na rede real (cancelados de um ano sobre a
    base de um mês). O KPI passa a ser a MÉDIA dos 12 pontos do gráfico logo abaixo, e a
    célula de cada unidade, a média do churn de cada mês fechado dela."""
    payload = pilot._rede_carteira_payload(inicio="2025-11-01", fim="2026-10-31")
    assert payload["periodo"]["churn_medio"] is True

    indices = [payload["serie_meses"].index(m) for m in _DOZE_MESES]
    pontos = [payload["series"]["churn_pct"][i] for i in indices]
    assert None not in pontos, "a série tem de ter os 12 pontos, senão o teste não prova nada"
    kpi = payload["kpis"]["churn_pct"]["atual"]
    assert kpi == pytest.approx(sum(pontos) / 12, abs=0.006)
    assert kpi < 10.0, "a conta antiga, acumulada, dava várias vezes isto"
    # A linha da rede (total) é o mesmo KPI, sem filtro.
    assert payload["rede_inteira"]["total"]["churn_pct"] == payload["kpis"]["churn_pct"]

    cheio = pilot._rede_fechamento()
    for unidade in payload["unidades"]:
        mensais = _churn_mensal_da_unidade(unidade["id"], _DOZE_MESES)
        assert unidade["metricas"]["churn_pct"]["atual"] == pytest.approx(
            sum(mensais) / len(mensais), abs=0.051
        ), unidade["nome"]
        # `cancelados` segue sendo o TOTAL do período (o número entre parênteses).
        do_ano = cheio[(cheio["unidade_id"] == unidade["id"]) & cheio["competencia"].isin(_DOZE_MESES)]
        assert unidade["metricas"]["cancelados"]["atual"] == pytest.approx(
            float(pd.to_numeric(do_ano["cancelados"]).sum()), abs=0.5
        )


def test_churn_medio_compara_com_a_mesma_conta_na_janela_anterior(rede_um_ano: Path) -> None:
    """jul-out/2026 contra a janela anterior de mesmo tamanho (28/02 a 30/06): dos dois
    lados, a média dos pontos mensais dos meses fechados (mar-jun contra jul-out).

    O `atual` é a rede inteira (os pontos do gráfico). A comparação é na cesta que operou o
    anterior INTEIRO: NOVA Z abriu em 15/03, depois do início dele, e fica fora dos dois
    lados dela -- a mesma regra da seta de cada unidade.
    """
    payload = pilot._rede_carteira_payload(inicio="2026-07-01", fim="2026-10-31")
    assert payload["periodo_anterior"] == {"inicio": "2026-02-28", "fim": "2026-06-30"}

    serie = dict(zip(payload["serie_meses"], payload["series"]["churn_pct"], strict=True))
    agora = [serie[f"2026-{m:02d}"] for m in (7, 8, 9, 10)]
    kpi = payload["kpis"]["churn_pct"]
    assert kpi["atual"] == pytest.approx(sum(agora) / 4, abs=0.006)

    cheio = pilot._rede_fechamento()
    antigas = ["antiga-x-sp", "antiga-y-sp"]
    cesta_agora = pilot._rede_churn_medio(cheio, antigas, [f"2026-{m:02d}" for m in (7, 8, 9, 10)])
    cesta_antes = pilot._rede_churn_medio(cheio, antigas, [f"2026-{m:02d}" for m in (3, 4, 5, 6)])
    assert kpi["m1"] == pytest.approx(cesta_antes, abs=0.006)
    assert kpi["delta_pct"] == pytest.approx(
        100.0 * (cesta_agora - cesta_antes) / cesta_antes, abs=0.15
    )
    assert kpi["delta_pontos"] == pytest.approx(cesta_agora - cesta_antes, abs=0.011)


def test_janela_que_atravessa_a_virada_sem_mes_fechado_segue_a_conta_de_hoje(
    rede_um_ano: Path,
) -> None:
    """17/10 a 16/11 não contém mês inteiro: churn = cancelados / base do início, como antes,
    e a tela rotula só "Churn" (sem a nota do Churn Médio)."""
    payload = pilot._rede_carteira_payload(inicio="2026-10-17", fim="2026-11-16")
    assert payload["periodo"]["churn_medio"] is False
    assert pilot._NOTA_CHURN_MEDIO not in payload["notas"]

    bruto = pilot._rede_periodo("2026-10-17", "2026-11-16")["atual"].set_index("unidade_id")
    for unidade in payload["unidades"]:
        linha = bruto.loc[unidade["id"]]
        esperado = 100.0 * float(linha["cancelados"]) / float(linha["pagantes_inicio"])
        assert unidade["metricas"]["churn_pct"]["atual"] == pytest.approx(esperado, abs=0.051)
    assert payload["kpis"]["churn_pct"]["atual"] == pilot._num(
        pilot._wavg(bruto["churn_pct"], bruto["pagantes"]), 2
    )


def test_mes_civil_fechado_sai_identico_a_conta_de_hoje(rede_um_ano: Path) -> None:
    """Outubro inteiro: média de UM mês = o churn do mês, na unidade e no KPI."""
    payload = pilot._rede_carteira_payload(mes="2026-10")
    assert payload["periodo"]["churn_medio"] is True
    bruto = pilot._rede_mes("2026-10")["atual"].set_index("unidade_id")
    for unidade in payload["unidades"]:
        linha = bruto.loc[unidade["id"]]
        conta_de_hoje = 100.0 * float(linha["cancelados"]) / float(linha["pagantes_inicio"])
        assert unidade["metricas"]["churn_pct"]["atual"] == pytest.approx(conta_de_hoje, abs=0.051)
        assert float(linha["churn_meses"]) == 1.0
    # O KPI antigo: média ponderada por recorrentes do quadro do mês.
    antigo = 100.0 * (bruto["churn_pct"] / 100.0 * bruto["pagantes"]).sum() / bruto["pagantes"].sum()
    assert payload["kpis"]["churn_pct"]["atual"] == pytest.approx(antigo, abs=0.006)


def test_unidade_inaugurada_na_janela_fica_fora_do_ranking_e_da_media(rede_um_ano: Path) -> None:
    """NOVA Z abriu em 15/03/2026, dentro dos doze meses: o churn dela é a média só dos
    meses COM base (abril a outubro, 7), e ela não entra no ranking nem na média da rede."""
    payload = pilot._rede_carteira_payload(inicio="2025-11-01", fim="2026-10-31")
    por_id = {u["id"]: u for u in payload["unidades"]}
    nova = por_id["nova-z-sp"]
    assert nova["comparavel"] is False
    churn = nova["metricas"]["churn_pct"]
    assert churn["rank"] is None and churn["vs_media_pct"] is None

    bruto = pilot._rede_periodo("2025-11-01", "2026-10-31")["atual"].set_index("unidade_id")
    assert float(bruto.loc["nova-z-sp", "churn_meses"]) == 7.0
    mensais = _churn_mensal_da_unidade("nova-z-sp", _DOZE_MESES)
    assert len(mensais) == 7
    assert churn["atual"] == pytest.approx(sum(mensais) / 7, abs=0.051)

    for antiga in ("antiga-x-sp", "antiga-y-sp"):
        assert por_id[antiga]["metricas"]["churn_pct"]["rank_total"] == 2
    linha = payload["rede_inteira"]
    assert linha["n_comparaveis"] == 2
    media_antigas = (
        float(bruto.loc["antiga-x-sp", "churn_pct"]) + float(bruto.loc["antiga-y-sp", "churn_pct"])
    ) / 2
    assert linha["media"]["churn_pct"]["atual"] == pytest.approx(media_antigas, abs=0.051)


def test_seta_some_quando_a_unidade_nao_operou_o_periodo_anterior_inteiro(
    rede_um_ano: Path,
) -> None:
    """Abril contra março: NOVA Z abriu em 15/03 e a seta mediria a rampa de abertura. O M-1
    fica (é real), o delta some e `m1_parcial` avisa a tela, que lê churn e NPS em pontos."""
    abril = {u["id"]: u for u in pilot._rede_carteira_payload(mes="2026-04")["unidades"]}
    nova = abril["nova-z-sp"]["metricas"]
    assert nova["faturamento"]["m1"] is not None, "o M-1 continua no quarteto"
    for chave, quarteto in nova.items():
        assert quarteto["delta_pct"] is None, chave
        assert quarteto.get("m1_parcial") is True, chave
    antiga = abril["antiga-x-sp"]["metricas"]
    assert all("m1_parcial" not in q for q in antiga.values())
    assert antiga["churn_pct"]["delta_pct"] is not None

    # Maio contra abril: abril ela operou inteiro, a seta volta.
    maio = {u["id"]: u for u in pilot._rede_carteira_payload(mes="2026-05")["unidades"]}
    assert "m1_parcial" not in maio["nova-z-sp"]["metricas"]["churn_pct"]
    assert maio["nova-z-sp"]["metricas"]["faturamento"]["delta_pct"] is not None


_ANTIGAS = ["antiga-x-sp", "antiga-y-sp"]


def _nova_z_com_nps_baixo(raiz: Path) -> None:
    """A base de um ano com NOVA Z em NPS 20 (as antigas seguem em 60 + mês): sem a
    diferença, a cesta não muda o NPS e o teste não provaria nada."""
    base = _base_um_ano()
    base.loc[base["unidade"] == "NOVA Z", "NPS"] = 20.0
    base.to_parquet(raiz / "staging" / "growth_api_historico.parquet")
    _limpar_caches()


def test_kpi_em_pontos_compara_na_mesma_cesta_com_inauguracao_na_janela(
    rede_um_ano: Path,
) -> None:
    """Achado A da revisão da DEC-088: churn e NPS variam em PONTOS na tela, e a tela
    contava `atual - m1` -- `atual` com a unidade inaugurada em março, `m1` sem ela. O NPS da
    rede "caía" 9 pontos num mês em que as mesmas lojas SUBIRAM 1. O servidor manda a
    variação pronta, na mesma cesta (`delta_pontos`)."""
    _nova_z_com_nps_baixo(rede_um_ano)
    marco = pilot._rede_carteira_payload(mes="2026-03")
    nps = marco["kpis"]["nps"]
    # Antigas: 64 em fevereiro, 65 em março.
    assert nps["m1"] == pytest.approx(64.0)
    assert nps["delta_pontos"] == pytest.approx(1.0, abs=0.011)
    assert nps["atual"] - nps["m1"] < -1.0, "sem a unidade nova no atual o teste não prova nada"

    churn = marco["kpis"]["churn_pct"]
    cheio = pilot._rede_fechamento()
    esperado = pilot._rede_churn_medio(cheio, _ANTIGAS, ["2026-03"]) - pilot._rede_churn_medio(
        cheio, _ANTIGAS, ["2026-02"]
    )
    assert churn["delta_pontos"] == pytest.approx(esperado, abs=0.011)


def test_cesta_do_agregado_exige_o_periodo_anterior_inteiro(rede_um_ano: Path) -> None:
    """Achado B: a cesta dos KPIs e da linha da rede era só "presente nos dois períodos".
    Em abril, NOVA Z está nos dois, mas abriu em 15/03 -- e a seta da rede media a rampa
    dela contra uma janela em que mal existia. Agora vale o mesmo gate da seta por unidade."""
    _nova_z_com_nps_baixo(rede_um_ano)
    payload = pilot._rede_carteira_payload(mes="2026-04")
    contexto = pilot._rede_mes("2026-04")
    m1 = contexto["m1"]
    assert "nova-z-sp" in m1.index, "premissa: ela tem dado no anterior"
    indexado = contexto["atual"].set_index("unidade_id")
    assert sorted(pilot._rede_cesta_do_anterior(indexado, m1)) == _ANTIGAS

    kpis = payload["kpis"]
    # NPS: só as antigas no M-1 (65), e a mesma cesta dos dois lados (66 - 65).
    assert kpis["nps"]["m1"] == pytest.approx(65.0)
    assert kpis["nps"]["delta_pontos"] == pytest.approx(1.0, abs=0.011)
    # Churn Médio: abril contra março, só nas antigas.
    cheio = pilot._rede_fechamento()
    antes = pilot._rede_churn_medio(cheio, _ANTIGAS, ["2026-03"])
    agora = pilot._rede_churn_medio(cheio, _ANTIGAS, ["2026-04"])
    assert kpis["churn_pct"]["m1"] == pytest.approx(antes, abs=0.006)
    assert kpis["churn_pct"]["delta_pontos"] == pytest.approx(agora - antes, abs=0.011)
    # Volume: o M-1 é a soma da cesta, sem o meio mês de NOVA Z.
    soma_antigas = float(pd.to_numeric(m1.loc[_ANTIGAS, "faturamento"]).sum())
    assert kpis["faturamento"]["m1"] == pytest.approx(soma_antigas, abs=0.01)

    # Linha da rede (média por unidade): NOVA Z é comparável em abril, mas fica fora da cesta.
    media = payload["rede_inteira"]["media"]["nps"]
    assert payload["rede_inteira"]["n_comparaveis"] == 3
    assert media["m1"] == pytest.approx(65.0)
    assert media["delta_pontos"] == pytest.approx(1.0, abs=0.011)
    # O total da linha segue sendo o KPI.
    assert payload["rede_inteira"]["total"]["nps"] == kpis["nps"]


def test_janela_sem_mes_fechado_compara_com_a_conta_da_janela_anterior(rede_um_ano: Path) -> None:
    """Achado C: "05/10 a 17/11" não tem mês fechado (conta da janela), mas a anterior,
    "22/08 a 04/10", contém setembro inteiro -- e lia o Churn Médio de setembro. A seta
    comparava duas contas. A anterior segue o modo da atual."""
    payload = pilot._rede_carteira_payload(inicio="2026-10-05", fim="2026-11-17")
    assert payload["periodo"]["churn_medio"] is False
    assert payload["periodo_anterior"] == {"inicio": "2026-08-22", "fim": "2026-10-04"}

    contexto = pilot._rede_periodo("2026-10-05", "2026-11-17")
    assert contexto["meses_churn_anterior"] == []
    m1 = contexto["m1"]
    assert m1["churn_meses"].isna().all(), "a anterior não pode ter virado Churn Médio"
    for unidade in payload["unidades"]:
        linha = m1.loc[unidade["id"]]
        conta_da_janela = 100.0 * float(linha["cancelados"]) / float(linha["pagantes_inicio"])
        assert float(linha["churn_pct"]) == pytest.approx(conta_da_janela)
        assert unidade["metricas"]["churn_pct"]["m1"] == pytest.approx(conta_da_janela, abs=0.051)
        # E a conta da janela não é o churn de setembro (senão o teste não provaria nada).
        setembro = _churn_mensal_da_unidade(unidade["id"], ["2026-09"])[0]
        assert abs(conta_da_janela - setembro) > 0.5, unidade["nome"]


def test_mes_fechado_contra_anterior_sem_mes_fechado_fica_sem_m1_de_churn(
    rede_um_ano: Path,
) -> None:
    """O inverso de C: "30/09 a 31/10" tem outubro fechado, e a anterior, "29/08 a 29/09",
    nenhum mês inteiro. Não existe Churn Médio do lado de lá: M-1 e seta do churn somem no
    KPI, na linha da rede e em cada unidade (o CSV herda). As outras métricas comparam."""
    payload = pilot._rede_carteira_payload(inicio="2026-09-30", fim="2026-10-31")
    assert payload["periodo"]["churn_medio"] is True
    assert payload["periodo_anterior"] == {"inicio": "2026-08-29", "fim": "2026-09-29"}

    kpi = payload["kpis"]["churn_pct"]
    assert kpi["atual"] is not None
    assert kpi["m1"] is None and kpi["delta_pct"] is None and kpi["delta_pontos"] is None
    media = payload["rede_inteira"]["media"]["churn_pct"]
    assert media["m1"] is None and media["delta_pontos"] is None
    assert payload["kpis"]["cancelados"]["m1"] is not None

    for unidade in payload["unidades"]:
        churn = unidade["metricas"]["churn_pct"]
        assert churn["atual"] is not None
        assert churn["m1"] is None and churn["delta_pct"] is None, unidade["nome"]
        assert unidade["metricas"]["faturamento"]["m1"] is not None

    texto = rede_export.carteira_csv(payload).decode("utf-8-sig")
    cabecalho, *linhas = list(csv.reader(io.StringIO(texto), delimiter=";"))
    coluna = cabecalho.index("Churn Médio % (M-1)")
    assert linhas and all(linha[coluna] == "" for linha in linhas)


def test_rotulos_e_nota_do_churn_medio_na_tela_e_nos_exports(rede_um_ano: Path) -> None:
    """"Churn Médio" com mês fechado, "Churn" no mês em curso -- nunca "mensal"."""
    ano = pilot._rede_carteira_payload(inicio="2025-11-01", fim="2026-10-31")
    assert pilot._NOTA_CHURN_MEDIO in ano["notas"]
    cabecalho = rede_export.carteira_csv(ano).decode("utf-8-sig").splitlines()[0]
    assert "Churn Médio %" in cabecalho.split(";")
    pdf = rede_export.carteira_pdf(ano)
    assert b"Churn M\xe9dio" in pdf
    assert b"m\xe9dia dos meses fechados" in pdf

    em_curso = pilot._rede_carteira_payload(inicio="2026-11-01", fim="2026-11-17")
    assert em_curso["periodo"]["churn_medio"] is False
    assert pilot._NOTA_CHURN_MEDIO not in em_curso["notas"]
    cabecalho = rede_export.carteira_csv(em_curso).decode("utf-8-sig").splitlines()[0]
    assert "Churn %" in cabecalho.split(";")
    assert "Churn Médio" not in cabecalho
    pdf = rede_export.carteira_pdf(em_curso)
    assert b"Churn M\xe9dio" not in pdf
    assert b"m\xe9dia ponderada" in pdf

    # A ficha é sempre um mês e não rotula Churn Médio: a nota não vai para ela.
    ficha = pilot.rede_unidade("antiga-x-sp", mes="2026-10")
    assert pilot._NOTA_CHURN_MEDIO not in ficha["notas"]
    assert pilot._NOTA_CHURN_MEDIO.encode("latin-1", "replace").decode("latin-1") == pilot._NOTA_CHURN_MEDIO


# --- B7: exportacao desligada vale no SERVIDOR, nao so' na tela -----------------------------

_ROTAS_DE_EXPORT = (
    pytest.param(lambda: pilot.rede_carteira_csv(mes="2026-07"), id="carteira.csv"),
    pytest.param(lambda: pilot.rede_carteira_xlsx(mes="2026-07"), id="carteira.xlsx"),
    pytest.param(lambda: pilot.rede_carteira_pdf(mes="2026-07"), id="carteira.pdf"),
    pytest.param(lambda: pilot.rede_unidade_pdf("botafogo-rj", mes="2026-07"), id="ficha.pdf"),
)


@pytest.mark.parametrize("chamar", _ROTAS_DE_EXPORT)
def test_exports_desligados_recusam_no_servidor(chamar, monkeypatch: pytest.MonkeyPatch) -> None:
    # Desliga a chave (sobrepondo o autouse): as 4 rotas tem de dar 403 ANTES de qualquer dado,
    # provando que a tela nao e' a unica barreira (B7). Sem banco, `_exigir_rede_inteira` ja'
    # passa, entao o 403 so' pode vir do `_exigir_exports_da_rede_ligados`.
    monkeypatch.setattr(pilot, "EXPORTS_REDE_ATIVOS", False)
    with pytest.raises(HTTPException) as erro:
        chamar()
    assert erro.value.status_code == 403
    assert erro.value.detail == pilot._MOTIVO_EXPORTS_DESLIGADOS


def test_chave_de_exports_casa_com_a_tela() -> None:
    # Religar exige trocar a chave no front E no backend; reprova se so' um mudar.
    api_ts = (_REPO / "web" / "src" / "lib" / "api.ts").read_text(encoding="utf-8")
    app_py = (_REPO / "web" / "server" / "app.py").read_text(encoding="utf-8")
    front = re.search(r"EXPORTS_REDE_ATIVOS\s*=\s*(true|false)", api_ts)
    back = re.search(r"EXPORTS_REDE_ATIVOS\s*=\s*(True|False)", app_py)
    assert front is not None and back is not None
    assert (front.group(1) == "true") == (back.group(1) == "True")
