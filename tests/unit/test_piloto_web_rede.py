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
import json
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
                "botafogo-rj": {"consultor": "MARISE", "cidade": "Rio de Janeiro"},
                "icarai-rj": {"consultor": "JAILSON", "cidade": "Niteroi"},
            },
        ),
        cadastro_dir,
    )

    monkeypatch.setattr(pilot, "STAGING_DIR", staging)
    monkeypatch.setattr(pilot, "GROWTH_PARQUET", staging / "growth_api_historico.parquet")
    monkeypatch.setattr(pilot, "ULTRA_PERF_PARQUET", staging / "nao_existe.parquet")
    monkeypatch.setattr(pilot, "ULTRA_MAPEADAS_PARQUET", staging / "tambem_nao.parquet")
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
        b"Faturamento nos 12 meses fechados",
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

