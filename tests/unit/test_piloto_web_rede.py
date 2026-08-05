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
    """O cliente nao pagina: o payload inteiro tem de caber num carregamento."""
    bruto = json.dumps(pilot.rede_carteira(), ensure_ascii=False).encode("utf-8")
    por_unidade = len(bruto) / max(pilot.rede_carteira()["totais"]["no_recorte"], 1)
    # ~2,3 KB/unidade x 102 unidades da rede real = ~235 KB (gzip: ~40 KB).
    assert por_unidade < 3_000, f"{por_unidade:.0f} bytes por unidade e' pesado demais"


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


def test_compose_monta_o_cadastro_como_unico_volume_de_escrita() -> None:
    """Infra: todo volume do `web` e' `:ro`, menos o cadastro."""
    compose = (_REPO / "docker-compose.prod.yml").read_text(encoding="utf-8")
    bloco = compose.split("motor_expansao_web", 1)[1].split("caddy:", 1)[0]
    montagens = [
        linha.strip().lstrip("- ").split("#")[0].strip()
        for linha in bloco.splitlines()
        if linha.strip().startswith("- /opt/motor-expansao")
    ]
    escritas = [m for m in montagens if m.endswith(":rw")]
    assert escritas == ["/opt/motor-expansao/cadastro:/app/cadastro:rw"]
    assert all(m.endswith((":ro", ":rw")) for m in montagens), "montagem sem modo explicito"
    assert 'MOTOR_CADASTRO_DIR: "/app/cadastro"' in compose
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
