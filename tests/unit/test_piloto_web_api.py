"""Smoke de contrato + guardrail READ-ONLY do backend do piloto web (web/server/app.py).

Roda no CI (job `test`) SEM os parquets: o backend degrada gracioso sem os dados
(base_calibracao=None -> faixa=None; setores_df=None -> sem catchment), entao os
endpoints respondem mesmo assim. Chama as funcoes de rota DIRETO (sem TestClient/httpx)
— testa a logica sem depender de httpx nem subir servidor.

Guardrail: o backend do piloto e READ-ONLY sobre o M1 (nao escreve artefato oficial).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]  # tests/unit/ -> raiz do worktree
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import app as pilot_app  # noqa: E402  (backend do piloto; web/server no sys.path acima)


def _apontar(monkeypatch: pytest.MonkeyPatch, data_dir: Path) -> None:
    """Repointa os globais de caminho que o `/api/health` observa.

    Espelha o `_point_app_at` de `test_piloto_web_endpoints.py` no subconjunto que
    interessa aqui. Mexe nos GLOBAIS de proposito — e' a unica forma de provar que o
    health resolve os caminhos na chamada e nao no import.
    """
    outputs = data_dir / "outputs"
    staging = data_dir / "staging"
    monkeypatch.setattr(pilot_app, "DATA_DIR", data_dir)
    monkeypatch.setattr(pilot_app, "ENRICHED_DIR", outputs / "hexagonos_dashboard_enriquecido")
    monkeypatch.setattr(pilot_app, "CRESCIMENTO_PATH", staging / "crescimento_municipal.parquet")
    monkeypatch.setattr(pilot_app, "CRESCIMENTO_HEX_PATH", staging / "crescimento_hex.parquet")
    monkeypatch.setattr(
        pilot_app, "NOMEADAS_PATH", staging / "vulnerabilidade_ma_nomeadas.parquet"
    )
    monkeypatch.setattr(pilot_app, "REDES_PATH", staging / "vulnerabilidade_ma_redes.parquet")
    # Camada imobiliaria: NAO fica sob `outputs/` nem `staging/` — e' artefato de outro
    # repo (o coletor), com mount proprio em producao. O global tambem e' derivado do
    # DATA_DIR no import, entao precisa ser repontado aqui como os demais.
    monkeypatch.setattr(
        pilot_app, "OPORTUNIDADES_PATH", data_dir / "oportunidades" / "viaveis.parquet"
    )


def test_health_ok() -> None:
    # /api/health: liveness PUBLICO e mudo; basta o status ok.
    assert pilot_app.health().get("status") == "ok"


def test_health_publico_nao_vaza_caminhos() -> None:
    """Pentest Onda B #8: o /api/health publico devolve EXATAMENTE {"status":"ok"}.

    O inventario (data_dir + caminhos absolutos + descricao de cada parquet) vazava o
    layout do FS e a camada de M&A a qualquer autenticado, ja' que a rota e' livre.
    Trava contra readicao silenciosa desses campos no payload publico.
    """
    assert pilot_app.health() == {"status": "ok"}


def test_health_reporta_os_artefatos_que_a_tela_depende() -> None:
    """O inventario diagnostico tem de ACUSAR artefato ausente — era o unico jeito de
    ver isso no ar. Migrou do /api/health publico para `_inventario_artefatos()`, servido
    pela rota admin `/api/acessos/saude-artefatos` (pentest Onda B #8).

    Os parquets de crescimento nao vem do git (`.gitignore`: `data/staging/*`) nem da
    imagem (`.dockerignore` corta `data/`): so' chegam pelo bind mount do compose. Sem
    eles `carregar_crescimento*()` devolve None e o passo 4 sai vazio EM SILENCIO —
    nenhum erro, nenhum log, e `scripts/check_artifacts.py` so' enxerga disco local.
    """
    h = pilot_app._inventario_artefatos()

    # Contrato do inventario: data_dir + data_ok para o operador auditar o ar.
    assert {"status", "data_dir", "data_ok"} <= set(h)

    artefatos = h["artefatos"]
    assert set(artefatos) == {
        "enriquecido",
        "crescimento_municipal",
        "crescimento_hex",
        # Pins das independentes (BLK-MA-15): mesma classe dos de crescimento — nao vem do git nem
        # da imagem, so' pelo bind mount, e sem ele a camada some EM SILENCIO.
        "independentes_nomeadas",
        # Pins das unidades de REDE do agregador (BLK-MA-17 metade 1 / DEC-035). Mesma classe, e
        # com um agravante proprio: sem este artefato as 1.171 unidades que a DEC-034 poe na
        # oferta continuam contando na pressao sem aparecer no mapa.
        "redes_nomeadas",
        # Camada imobiliaria (2026-08-24). Mesma classe, e a mais fragil de todas: nao vem do
        # git NEM de outro pipeline deste repo — e' artefato de OUTRO repositorio (o coletor),
        # copiado por scp com cadencia propria. Sem ele a rota responde 200 com lista vazia e a
        # tela diz "Nada no recorte", que e' o que ela diz tambem quando o filtro nao casou.
        "oportunidades_imobiliarias",
    }
    for nome, a in artefatos.items():
        assert isinstance(a["ok"], bool), nome
        # `para_que` e' o que transforma "faltou um arquivo" em "o passo 4 vai sair
        # vazio". Sem ele o operador le um caminho e nao sabe o que perdeu.
        assert a["para_que"] and a["caminho"], nome

    # A lista resumida tem de bater com o dict — ela existe para o operador nao
    # precisar abrir os tres blocos, e divergir dela seria pior que nao ter.
    assert h["artefatos_faltando"] == sorted(
        n for n, a in artefatos.items() if not a["ok"]
    )
    assert h["data_ok"] == artefatos["enriquecido"]["ok"]


def test_health_nao_estoura_com_data_dir_inexistente(monkeypatch) -> None:
    """Mount caido nao pode virar 500: `curl -fsS` falharia e o container reiniciaria.

    Este e' o cenario REAL do defeito — o `data/` que o app aponta nao existe naquela
    maquina. O health precisa responder 200 dizendo o que falta, e nao morrer junto.
    """
    fantasma = Path("Z:/mount/que/nao/existe/data")
    _apontar(monkeypatch, fantasma)

    h = pilot_app._inventario_artefatos()
    assert h["status"] == "ok"
    assert h["data_ok"] is False
    assert h["data_dir"] == str(fantasma)
    assert h["artefatos_faltando"] == [
        "crescimento_hex",
        "crescimento_municipal",
        "enriquecido",
        "independentes_nomeadas",
        "oportunidades_imobiliarias",
        "redes_nomeadas",
    ]
    # Os caminhos reportados tem de sair do data_dir REPONTADO. Se a lista de artefatos
    # for montada no import, ela congela os `Path` originais e o health passa a falar do
    # disco de quem roda — verde nesta maquina (onde o caminho do autor tambem nao
    # existe) e mentiroso em qualquer outra.
    for a in h["artefatos"].values():
        assert str(fantasma) in a["caminho"], a


def test_health_sobrevive_a_stat_que_levanta(monkeypatch) -> None:
    """Cobre o ramo `except OSError`, que o teste do caminho inexistente NAO alcanca.

    No Windows, `Path("Z:/nao/existe").exists()` devolve False em vez de levantar — o
    caminho fantasma exercita o `ok=False` normal, nunca o `except`. Mas em producao o
    mount e' de rede e READ-ONLY: quando ele cai, o `exists()` levanta `OSError`, e sem
    a protecao o health viraria 500. Ai o `curl -fsS` do healthcheck falha e o Docker
    REINICIA o container por causa de um arquivo de dado ausente — justamente o
    contrario do que este endpoint existe para fazer.
    """

    class _CaminhoQueCai:
        def __init__(self, rotulo: str) -> None:
            self._rotulo = rotulo

        def exists(self) -> bool:
            raise OSError(f"mount caiu: {self._rotulo}")

        def __str__(self) -> str:
            return self._rotulo

    for glob in (
        "ENRICHED_DIR",
        "CRESCIMENTO_PATH",
        "CRESCIMENTO_HEX_PATH",
        "NOMEADAS_PATH",
        "REDES_PATH",
        "OPORTUNIDADES_PATH",
    ):
        monkeypatch.setattr(pilot_app, glob, _CaminhoQueCai(f"/app/data/{glob}"))

    h = pilot_app._inventario_artefatos()
    assert h["status"] == "ok", "o inventario NAO pode cair junto com o mount"
    assert h["data_ok"] is False
    # O motivo tem de chegar ao operador: sem `erro`, "ok=False" nao distingue
    # "arquivo nunca foi copiado" de "o mount de rede caiu agora".
    for nome, a in h["artefatos"].items():
        assert a["ok"] is False, nome
        assert "mount caiu" in a["erro"], nome


def test_faixa_alunos_contrato() -> None:
    body = pilot_app.faixa_alunos(m2=1500)
    assert set(body) >= {"p10", "p50", "p90", "n_comparaveis"}


def test_viabilidade_contrato_e_coerencia() -> None:
    """Contrato `viabilidade_payload_v1` (FIN-VIAB-01).

    O payload antigo tinha DUAS series (`fcf_serie` acumulada e `fco_serie` mensal),
    montadas no backend, mais `dre.payback`/`dre.roic` que SOBRESCREVIAM os do motor —
    a duplicacao que fazia o card dizer 35 e o grafico 33. Agora existe UMA serie
    (`serie_mensal`, do nucleo) e o payback/retorno sao os do motor, sem override.
    """
    body = pilot_app.viabilidade(
        pilot_app.ViabilidadeIn(
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
    assert body["versao"] == pilot_app.VIABILIDADE_PAYLOAD_VERSAO
    assert set(body) >= {
        "premissas",
        "dre",
        "investimento",
        "retorno",
        "break_even",
        "aluguel_teto",
        "faixa_alunos",
        "serie_mensal",
        "split",
        "grade",
    }
    # As series duplicadas do backend NAO existem mais.
    assert "fcf_serie" not in body and "fco_serie" not in body

    dre = body["dre"]
    assert set(dre) >= {
        "faturamento", "deducoes", "impostos", "custos_op", "custos_variaveis",
        "folha", "custos_fixos", "ebitda", "margem", "ir_csll", "resultado_apos_ir",
    }
    # Cascata coerente: as PARCELAS do custo vem do motor, nao por diferenca.
    assert dre["custos_op"] == pytest.approx(
        dre["custos_variaveis"] + dre["folha"] + dre["custos_fixos"], abs=0.05
    )
    assert dre["faturamento"] - dre["deducoes"] - dre["impostos"] - dre["custos_op"] == (
        pytest.approx(dre["ebitda"], abs=0.05)
    )
    # margem em FRACAO (0,3873 = 38,73%), como todo percentual do payload.
    assert 0.0 <= dre["margem"] <= 1.0

    # Aluguel-teto = % do faturamento bruto steady (unica definicao do sistema).
    teto = body["aluguel_teto"]
    assert teto["base"] == "faturamento_bruto"
    assert teto["ideal"] < teto["teto"] < teto["excecao"]
    # Card grande usa o TETO (20%), nao a excecao (decisao de Felipe 2026-07-24).
    assert teto["canonico"] == pytest.approx(teto["teto"])
    assert teto["teto"] == pytest.approx(0.20 * dre["faturamento"], rel=1e-4)

    # Retorno DESALAVANCADO = (EBITDA - IR) x12 / investimento total (capex + franquia).
    inv = body["investimento"]
    assert inv["investimento_total"] == pytest.approx(800_000 + 700_000 + 160_000)
    assert body["retorno"]["otica"] == "desalavancada"
    assert body["retorno"]["retorno_anual_desalavancado"] == pytest.approx(
        (dre["resultado_apos_ir"] * 12) / inv["investimento_total"], abs=1e-3
    )

    # Break-even em alunos TOTAIS (comparavel com a demanda digitada); o de caixa
    # (que cobre a PMT) e sempre >= o de EBITDA.
    be = body["break_even"]
    assert be["unidade"] == "alunos_totais"
    assert be["caixa"] >= be["ebitda"]

    # A UNICA serie: M-4..M-1 de pre-abertura + M1..M60 de operacao, com o CAPEX dentro.
    serie = body["serie_mensal"]
    assert [linha["mes"] for linha in serie[:4]] == [-4, -3, -2, -1]
    assert all(linha["fase"] == "pre_operacional" for linha in serie[:4])
    assert serie[0]["fcf_acumulado"] < 0  # o acumulado parte do desembolso
    assert serie[-1]["mes"] == body["premissas"]["horizonte_meses"]
    assert body["acumulado_mes_final"] == pytest.approx(serie[-1]["fcf_acumulado"])

    # FOLHA FIXA desde o mes 1 (decisao de Felipe, 2026-07-24): a folha da serie NAO
    # acompanha a rampa de alunos -- ela e dimensionada pelo faturamento MADURO e paga
    # inteira desde o mes 1. O `dre.folha` do topo e a folha de QUALQUER mes do ano 1.
    operacao = [linha for linha in serie if linha["fase"] == "operacao"]
    ano1 = operacao[:12]
    assert len({linha["folha"] for linha in ano1}) == 1, "a folha voltou a escalar"
    assert ano1[0]["folha"] == pytest.approx(dre["folha"], abs=0.01)
    assert ano1[0]["ebitda_mensal"] < 0  # o mes 1 nasce no vermelho por causa dela
    assert operacao[12]["folha"] > ano1[0]["folha"]  # reajuste anual so no mes 13

    # TAXA DE FRANQUIA PARCELADA (mesma decisao): N parcelas iguais nos meses de
    # contrato 1..N, e a SOMA das parcelas == taxa_franquia.
    n_parcelas = inv["parcelas_franquia"]
    assert n_parcelas >= 1
    assert inv["franquia_parcela"] == pytest.approx(inv["taxa_franquia"] / n_parcelas, abs=0.01)
    parcelas = [linha for linha in serie if linha["mes_contrato"] <= n_parcelas]
    assert [linha["mes_contrato"] for linha in parcelas] == list(range(1, n_parcelas + 1))


def test_backend_e_read_only() -> None:
    """Guardrail: o backend do piloto NAO escreve artefato (READ-ONLY sobre o M1)."""
    src = (_SERVER / "app.py").read_text(encoding="utf-8")
    proibidos = [".to_parquet(", ".to_csv(", ".to_feather(", "shutil.rmtree("]
    achados = [p for p in proibidos if p in src]
    assert not achados, f"backend do piloto deve ser READ-ONLY; escrita encontrada: {achados}"


def test_disco_de_hexes_traz_a_coluna_da_socioeconomia(tmp_path: Path) -> None:
    """DEFEITO (Felipe, 2026-07-29): o PDF do piloto saia SEM o painel de Socioeconomia.

    `_residual_hexes_do_ponto` lia so `oferta_efetiva_disponivel`. O painel de Socioeconomia
    (BLK-RELPON-13) le `score_setor_2022_calibrado` do MESMO disco de hexes; sem a coluna,
    `_render_camada_residual_hex` devolve lista vazia, a chave `socioeconomia` nao entra no dict
    de mapas e o PDF cai no fallback textual. Nada falhava: chave ausente e' caminho legitimo
    (ponto sem hex desenhavel), entao o defeito era SILENCIOSO. So o Residual aparecia.
    """
    import h3
    import pandas as pd

    lat, lng = -23.55, -46.63
    centro = h3.latlng_to_cell(lat, lng, 7)
    vizinhos = list(h3.grid_disk(centro, 1))
    pd.DataFrame(
        {
            "hex_id": vizinhos,
            "oferta_efetiva_disponivel": [1000.0] * len(vizinhos),
            "score_setor_2022_calibrado": [55.0] * len(vizinhos),
            "coluna_irrelevante": ["x"] * len(vizinhos),
        }
    ).to_parquet(tmp_path / "hexagonos_mercado_mapeado.parquet", index=False)

    df = pilot_app._residual_hexes_do_ponto(lat, lng, tmp_path)

    assert df is not None and not df.empty
    assert "score_setor_2022_calibrado" in df.columns, (
        "sem esta coluna o painel de Socioeconomia some do PDF, em silencio"
    )
    assert "oferta_efetiva_disponivel" in df.columns
    # Projecao continua enxuta: nao carrega o parquet inteiro so por causa disso.
    assert "coluna_irrelevante" not in df.columns


def test_disco_de_hexes_tolera_parquet_sem_a_coluna_de_score(tmp_path: Path) -> None:
    """Parquet antigo (pre-BLK-RELPON-13) nao pode derrubar o Residual junto."""
    import h3
    import pandas as pd

    lat, lng = -23.55, -46.63
    vizinhos = list(h3.grid_disk(h3.latlng_to_cell(lat, lng, 7), 1))
    pd.DataFrame(
        {"hex_id": vizinhos, "oferta_efetiva_disponivel": [900.0] * len(vizinhos)}
    ).to_parquet(tmp_path / "hexagonos_mercado_mapeado.parquet", index=False)

    df = pilot_app._residual_hexes_do_ponto(lat, lng, tmp_path)

    assert df is not None and "oferta_efetiva_disponivel" in df.columns
    assert "score_setor_2022_calibrado" not in df.columns


def test_piloto_e_api_renderizam_o_mapa_com_os_MESMOS_parametros() -> None:
    """DEC-021 — trava anti-deriva entre as duas superficies que geram o Relatorio Pontual.

    Historico que justifica o teste: o piloto e a API divergiram em producao por HORAS sem
    ninguem notar — alpha 255 aqui contra 110 la, e raio de display 1,0 contra analise 1,5 —
    porque cada call site passava seus proprios kwargs. A divergencia so aparecia comparando
    dois PDFs lado a lado. Agora ambos OMITEM o alpha (vale o default do modulo) e usam o
    MESMO raio canonico; este teste falha se alguem reintroduzir um override em qualquer lado.
    """
    import inspect

    from motor_expansao.api import service
    from motor_expansao.dashboard.censo_point import RAIO_CENSITARIO_DEFAULT_KM

    # 1. Nenhuma das duas superficies pode voltar a fixar o alpha do choropleth.
    for modulo, nome in ((pilot_app, "piloto web"), (service, "API/bot")):
        fonte = inspect.getsource(modulo)
        assert "choropleth_alpha=" not in fonte, (
            f"{nome} voltou a sobrescrever o alpha; o valor unico vive em censo_map."
        )

    # 2. O piloto nao pode ter raio de display proprio (a analise E o raio do mapa).
    assert not hasattr(pilot_app, "RAIO_MAPAS_DISPLAY_KM"), (
        "raio de display separado ressuscitou: o PDF volta a desenhar um raio e contar outro"
    )

    # 3. O raio canonico e o da DEC-021.
    assert RAIO_CENSITARIO_DEFAULT_KM == 1.0


def test_rotulo_do_metodo_acompanha_o_raio() -> None:
    """DEC-021: o `metodo` e' contrato publico da API e nao pode mentir sobre o raio."""
    from motor_expansao.dashboard.censo_point import (
        METODO_RELATORIO_PONTUAL_CENSITARIO,
        RAIO_CENSITARIO_DEFAULT_KM,
    )

    assert METODO_RELATORIO_PONTUAL_CENSITARIO == "setor_censitario_intersecao_area_1km"
    assert "1p5km" not in METODO_RELATORIO_PONTUAL_CENSITARIO
    assert RAIO_CENSITARIO_DEFAULT_KM == 1.0


def test_distribuicao_de_renda_le_a_coluna_corrigida() -> None:
    """`detalhe.distribuicao.renda_per_capita` tem de sair da coluna DOMICILIAR per capita.

    Contrato sobre o fonte, no mesmo molde de `test_backend_e_read_only`: montar o payload
    inteiro num teste exigiria a malha IBGE real em disco (`ponto()` falha antes de chegar no
    analisador), e o `_dist` e' uma closure dentro do endpoint — nao da' para chama-lo isolado.

    O payload de `/ponto` expoe renda per capita em TRES campos irmaos: o agregado do raio,
    o setor do ponto e esta distribuicao min/mediana/max. A correcao de escala de 2026-08-13
    pegou os dois primeiros e deixou este lendo `renda_per_capita_setor_2022_calibrada` — a
    coluna com o `k` —, o que punha ~24% de diferenca dentro do MESMO documento. Achado pela
    revisao automatica do PR #237, nao pela suite: nenhum teste olhava a coluna que o alimenta.

    A escala do VALOR esta travada em
    `test_os_tres_campos_de_renda_per_capita_do_payload_na_MESMA_escala`
    (tests/unit/test_relatorio_pontual_censitario_motor.py); aqui trava-se a LIGACAO.
    """
    src = (_SERVER / "app.py").read_text(encoding="utf-8")

    assert '"renda_per_capita": _dist("renda_per_capita_domiciliar_setor")' in src, (
        "a distribuicao de renda do payload precisa ler `renda_per_capita_domiciliar_setor`"
    )
    # Nenhuma distribuicao pode sair da coluna calibrada. Note que a calibrada CONTINUA valida
    # em `_base_renda_domiciliar`, que a converte dividindo pelo `k` — por isso o alvo aqui e'
    # o `_dist(...)`, e nao a mera presenca do nome da coluna no arquivo.
    assert '_dist("renda_per_capita_setor_2022_calibrada")' not in src, (
        "distribuicao saindo da coluna calibrada reintroduz o `k` na renda exibida"
    )


# --- Pentest Onda B #11: floats nao-finitos em /api/viabilidade ----------------
# Estes casos vivem na camada de validacao/serializacao (o corpo cru com NaN/Infinity),
# invisivel chamando a funcao de rota direto — precisam de TestClient. Mesmo padrao
# "pula se httpx ausente" de test_api_skeleton.py; httpx esta no constraints (roda no CI).

_CORPO_VIAB_OK = (
    '{"lat": -23.5, "lng": -46.6, "m2": 1500, "aluguel": 30000, "demanda": 1600}'
)


def _client_viab():
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    return TestClient(pilot_app.app, raise_server_exceptions=False)


def _post_viab_cru(corpo: str):
    # `content=` manda o JSON CRU: o `json=` do httpx recusa NaN/Infinity no cliente,
    # e e' justamente o corpo nao-finito que precisamos entregar ao servidor.
    return _client_viab().post(
        "/api/viabilidade", content=corpo, headers={"content-type": "application/json"}
    )


@pytest.mark.parametrize(
    "corpo",
    [
        '{"lat": -23.5, "lng": -46.6, "m2": NaN, "aluguel": 30000, "demanda": 1600}',
        '{"lat": -23.5, "lng": -46.6, "m2": Infinity, "aluguel": 30000, "demanda": 1600}',
        '{"lat": -23.5, "lng": -46.6, "m2": 1500, "aluguel": Infinity, "demanda": 1600}',
        '{"lat": NaN, "lng": -46.6, "m2": 1500, "aluguel": 30000, "demanda": 1600}',
    ],
)
def test_viabilidade_nao_finito_e_422_nao_500(corpo: str) -> None:
    """NaN/Infinity no corpo -> 422 limpo (nao 500 opaco, nem 200 com DRE-lixo)."""
    resp = _post_viab_cru(corpo)
    assert resp.status_code == 422, resp.text
    # O 422 tem de ser parseavel: o handler saneia o input nao-finito para string ANTES
    # de serializar (senao o json.dumps do Starlette com allow_nan=False estouraria = 500).
    assert isinstance(resp.json().get("detail"), list)


@pytest.mark.parametrize(
    "corpo",
    [
        '{"lat": 999, "lng": -46.6, "m2": 1500, "aluguel": 30000, "demanda": 1600}',
        '{"lat": -23.5, "lng": -999, "m2": 1500, "aluguel": 30000, "demanda": 1600}',
    ],
)
def test_viabilidade_latlng_fora_do_bound_e_422(corpo: str) -> None:
    """lat/lng fora de [-90,90]/[-180,180] -> 422 (antes passava com 200)."""
    assert _post_viab_cru(corpo).status_code == 422


def test_viabilidade_corpo_valido_segue_200() -> None:
    """Baseline: o fix nao pode quebrar o caminho feliz."""
    assert _post_viab_cru(_CORPO_VIAB_OK).status_code == 200
