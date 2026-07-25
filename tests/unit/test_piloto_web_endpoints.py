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
    # A viabilidade roda pelas premissas INTERNAS do motor (base=None): sem parquets.
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
    assert body["versao"] == pilot.VIABILIDADE_PAYLOAD_VERSAO
    assert {
        "premissas", "dre", "investimento", "retorno", "break_even",
        "aluguel_teto", "grade", "faixa_alunos", "serie_mensal",
    } <= set(body)
    # JSON-safe de ponta a ponta: o payload inteiro serializa SEM NaN/inf. E o guardrail
    # do `json.dumps(..., allow_nan=False)` do Starlette — payback infinito e TIR
    # inexistente tem que sair como null, nunca como Infinity/NaN.
    json.dumps(body, allow_nan=False)

    dre = body["dre"]
    assert {"faturamento", "ebitda", "custos_op", "margem", "ir_csll"} <= set(dre)
    # Cascata coerente: faturamento - deducoes - impostos - custos_op == ebitda.
    recomposto = dre["faturamento"] - dre["deducoes"] - dre["impostos"] - dre["custos_op"]
    assert recomposto == pytest.approx(dre["ebitda"], abs=0.05)
    # Serie UNICA (M-4..M60) com o CAPEX dentro: o acumulado parte negativo.
    serie = body["serie_mensal"]
    assert [linha["mes"] for linha in serie[:4]] == [-4, -3, -2, -1]
    assert serie[0]["fcf_acumulado"] < 0
    # Sem base de comparaveis, a fonte da faixa e EXPLICITA (degradacao nao-silenciosa).
    assert body["premissas"]["fonte_base_calibracao"] == pilot.FONTE_BASE_INDISPONIVEL
    assert body["faixa_alunos"]["p50"] is None


def test_viabilidade_payback_infinito_vira_null(empty_data: Path) -> None:
    """Cenario que nunca se paga: `payback`/`tir_anual` saem como null explicito.

    O motor devolve `inf`/`None`; se algum deles vazasse, o Starlette (que serializa
    com allow_nan=False) derrubaria a resposta inteira com um 500 opaco.
    """
    body = pilot.viabilidade(
        pilot.ViabilidadeIn(
            lat=-23.5, lng=-46.6, m2=1500, aluguel=120_000, demanda=200, ticket=100
        )
    )
    assert body["retorno"]["payback"] is None
    assert body["retorno"]["tir_anual"] is None
    json.dumps(body, allow_nan=False)


def _viab(empty: bool = True, **extra) -> dict:
    base = dict(
        lat=-23.5, lng=-46.6, m2=1500, aluguel=30000, demanda=1600, ticket=177,
        obra=600_000, equipamentos=1_400_000, prazo_equipamentos=60,
        juros_equipamentos_am=0.018,
    )
    return pilot.viabilidade(pilot.ViabilidadeIn(**{**base, **extra}))


def test_n_studios_custa_no_dre(empty_data: Path) -> None:
    """Cada studio soma SIM_CUSTO_STUDIO ao custo fixo.

    Ate o FIN-VIAB-01 o campo era aceito e DESCARTADO: o studio elevava o ticket no
    front e nao custava nada no DRE (receita fantasma) — uma unidade com 3 studios
    rodava com o custo fixo de uma sem nenhum.
    """
    from motor_expansao.dimensionamento.config import SIM_CUSTO_STUDIO

    sem = _viab(n_studios=0)["dre"]
    com = _viab(n_studios=2)["dre"]
    assert com["custos_fixos"] - sem["custos_fixos"] == pytest.approx(2 * SIM_CUSTO_STUDIO, abs=0.05)
    assert com["ebitda"] < sem["ebitda"]


def test_taxa_franquia_editavel_pelo_operador(empty_data: Path) -> None:
    """A taxa de franquia era constante invisivel; agora e premissa explicita."""
    from motor_expansao.dimensionamento.config import SIM_TAXA_FRANQUIA

    padrao = _viab()["investimento"]
    assert padrao["taxa_franquia"] == pytest.approx(SIM_TAXA_FRANQUIA)

    ajustada = _viab(taxa_franquia=140_000)["investimento"]
    assert ajustada["taxa_franquia"] == pytest.approx(140_000)
    assert ajustada["investimento_total"] == pytest.approx(padrao["investimento_total"] - 20_000)


def test_tela_e_pdf_leem_os_mesmos_kpis(empty_data: Path) -> None:
    """COERENCIA ENTRE CAMADAS: tela e PDF entregam o MESMO numero (tolerancia R$0,01).

    E a regressao do defeito central do FIN-VIAB-01 — o mesmo cenario saindo com payback
    35 no card e 33 no grafico, aluguel-teto R$55,5 mil na tela e R$105,8 mil no PDF.
    Compara o `viabilidade_payload_v1` que a rota devolve com o dict que o slide do PDF
    de fato imprime, ja normalizado por `censo_report._viab_normalizado`.
    """
    from motor_expansao.dashboard.censo_report import _viab_normalizado

    entrada = pilot.ViabilidadeIn(
        lat=-23.5, lng=-46.6, m2=1500, aluguel=30000, demanda=1600, ticket=177,
        obra=600_000, equipamentos=1_400_000, prazo_equipamentos=60,
        juros_equipamentos_am=0.018,
    )
    tela = pilot.viabilidade(entrada)
    pdf = _viab_normalizado(pilot._viabilidade_pdf_payload(entrada))

    for caminho, chave_pdf in (
        (("dre", "faturamento"), "faturamento_mensal"),
        (("dre", "ebitda"), "ebitda_mensal"),
        (("dre", "margem"), "margem_ebitda_pct"),
        (("retorno", "payback"), "payback_meses"),
        (("retorno", "retorno_anual_desalavancado"), "retorno_anual"),
        (("retorno", "tir_anual"), "tir_anual"),
        (("retorno", "vpl"), "vpl"),
        (("break_even", "ebitda"), "alunos_breakeven"),
        (("break_even", "caixa"), "breakeven_caixa"),
        (("investimento", "pmt"), "pmt_mensal"),
        (("investimento", "juros_totais"), "juros_totais"),
        (("investimento", "investimento_total"), "investimento_total"),
        (("aluguel_teto", "canonico"), "aluguel_teto"),
        (("acumulado_mes_final",), "acumulado_mes_final"),
    ):
        esperado: object = tela
        for parte in caminho:
            esperado = esperado[parte]  # type: ignore[index]
        obtido = pdf[chave_pdf]
        if esperado is None:
            assert obtido is None, f"{chave_pdf}: tela=None mas PDF={obtido!r}"
        else:
            assert obtido == pytest.approx(esperado, abs=0.01), (
                f"{chave_pdf}: tela={esperado!r} x PDF={obtido!r}"
            )

    # As 3 FAIXAS do aluguel-teto tem que chegar ao PDF. A chave PLANA `aluguel_teto`
    # (float) e homonima da secao v1 (dict): sem preservar as faixas a parte, o slide
    # perdia a linha "ideal | teto | excecao" e imprimia so o canonico.
    faixas = pdf["aluguel_teto_faixas"]
    for nome in ("ideal", "teto", "excecao"):
        assert faixas[nome] == pytest.approx(tela["aluguel_teto"][nome], abs=0.01)


def test_dre_do_payload_e_a_linha_de_steady_da_serie(empty_data: Path) -> None:
    """O DRE de topo tem que ser EXATAMENTE uma linha da serie unica, nao outro mes.

    O waterfall do PDF ja reencontrou a "linha de steady" por `maturacao_meses` em vez de
    ler o `dre`; bastou o nucleo mover o steady para grafico e card do MESMO slide saírem
    de meses diferentes. Este teste trava a identidade dre == serie[mes de referencia].

    O mes de referencia e SERVIDO em `premissas.mes_referencia_steady` e vale
    max(maturacao, inicio da anuidade) — com a anuidade ligada ele NAO e mais
    `maturacao_meses`. Reencontrar a linha por `maturacao_meses` aqui era o proprio
    anti-padrao que este ciclo elimina: o teste passava a comparar o DRE de regime
    pleno (mes 12) com a linha do mes 8.
    """
    corpo = _viab()
    ref = corpo["premissas"]["mes_referencia_steady"]
    # Com a anuidade ligada o regime pleno so comeca depois da maturacao.
    assert ref >= corpo["premissas"]["maturacao_meses"]
    linha = next(r for r in corpo["serie_mensal"] if r["mes"] == ref)
    assert corpo["dre"]["faturamento"] == pytest.approx(linha["faturamento_mensal"], abs=0.01)
    assert corpo["dre"]["ebitda"] == pytest.approx(linha["ebitda_mensal"], abs=0.01)
    # Os degraus intermediarios do DRE tambem sao a MESMA linha (nao subtracoes).
    assert corpo["dre"]["deducoes"] == pytest.approx(linha["deducoes"], abs=0.01)
    assert corpo["dre"]["impostos"] == pytest.approx(linha["impostos"], abs=0.01)
    assert corpo["dre"]["receita_liquida"] == pytest.approx(linha["receita_liquida"], abs=0.01)
    assert corpo["dre"]["receita_anuidade"] == pytest.approx(linha["receita_anuidade"], abs=0.01)


def test_premissas_opcionais_sobrescrevem_o_config(empty_data: Path) -> None:
    """As premissas que viraram campo do schema chegam MESMO ao motor (nao sao ignoradas)."""
    body = _viab(
        deducoes_pct=0.01,
        reajuste_ticket_aa=0.0,
        taxa_desconto_aa=0.15,
        custo_pre_operacional_mes=5_000,
        carencia_aluguel_meses=6,
    )
    p = body["premissas"]
    assert p["deducoes_pct"] == pytest.approx(0.01)
    assert p["reajuste_ticket_aa"] == pytest.approx(0.0)
    assert p["taxa_desconto_aa"] == pytest.approx(0.15)
    assert p["custo_pre_operacional_mes"] == pytest.approx(5_000)
    # Carencia contada da ENTREGA (M-4): 6 meses de contrato -> aluguel comeca em M3.
    assert p["carencia_aluguel_meses"] == 6
    assert p["mes_inicio_aluguel"] == 3
    assert body["serie_mensal"][0]["aluguel"] == 0.0
    assert body["serie_mensal"][0]["custo_pre_operacional"] == pytest.approx(5_000)


# ===========================================================================
# 3b) FIN-VIAB-01 (2026-07-24) — folha FIXA desde o mes 1 e franquia parcelada 4x
# ===========================================================================


def test_payload_serve_folha_fixa_desde_o_mes_1(empty_data: Path) -> None:
    """A `folha` da serie servida NAO escala com a rampa (era o defeito reportado).

    Decisao de Felipe (2026-07-24): a folha e dimensionada UMA vez pelo faturamento
    MADURO e paga integralmente desde o mes 1 -- a equipe existe antes dos alunos.
    Consequencias visiveis no payload: `dre.folha` == folha de QUALQUER mes do ano 1,
    e o EBITDA do mes 1 fica bem mais negativo do que com a folha escalonada.
    """
    corpo = _viab()
    operacao = [linha for linha in corpo["serie_mensal"] if linha["fase"] == "operacao"]
    ano1 = operacao[:12]
    assert [linha["mes"] for linha in ano1] == list(range(1, 13))

    # UM unico valor de folha no ano 1 -- e ele e o `dre.folha` do topo do payload.
    assert len({linha["folha"] for linha in ano1}) == 1
    assert ano1[0]["folha"] == pytest.approx(corpo["dre"]["folha"], abs=0.01)
    # ...mesmo com os alunos MAIS QUE DOBRANDO no intervalo (637,5 -> 1.600).
    assert ano1[-1]["alunos_total"] > 2.0 * ano1[0]["alunos_total"]
    # Reajuste anual e o UNICO degrau: aparece no mes 13, nunca antes.
    assert operacao[12]["mes"] == 13
    assert operacao[12]["folha"] > ano1[0]["folha"]

    # A folha do mes 1 e MAIOR que folha_pct x faturamento do mes 1 (a regra antiga).
    folha_pct = corpo["premissas"]["folha_pct"]
    assert ano1[0]["folha"] > folha_pct * ano1[0]["faturamento_mensal"]
    # E o mes 1 nasce no vermelho por causa disso.
    assert ano1[0]["ebitda_mensal"] < 0

    # A cascata do DRE continua fechando com a folha como parcela propria.
    dre = corpo["dre"]
    assert dre["custos_op"] == pytest.approx(
        dre["custos_variaveis"] + dre["folha"] + dre["custos_fixos"], abs=0.05
    )


def test_payload_folha_e_breakeven_dependem_da_demanda_assumida(empty_data: Path) -> None:
    """Demanda assumida menor -> folha menor -> break-even menor.

    A folha virou custo FIXO dimensionado pela demanda, entao `break_even_alunos` e
    `alunos_para_margem` passaram a receber a demanda. Isto prova que o backend serve
    essa dependencia (antes o break-even nao se movia com a demanda).
    """
    baixa = _viab(demanda=900)
    alta = _viab(demanda=2400)
    assert baixa["dre"]["folha"] < alta["dre"]["folha"]
    assert baixa["break_even"]["ebitda"] < alta["break_even"]["ebitda"]
    assert baixa["break_even"]["caixa"] < alta["break_even"]["caixa"]
    # O de caixa cobre a PMT, entao continua >= o de EBITDA nos dois cenarios.
    for corpo in (baixa, alta):
        assert corpo["break_even"]["caixa"] >= corpo["break_even"]["ebitda"]


def test_payload_serve_a_franquia_em_parcelas_iguais(empty_data: Path) -> None:
    """4 parcelas iguais nos meses de contrato 1..4 (M-4..M-1), junto da obra.

    Antes a taxa saia INTEIRA do caixa no M-4. O payload tem de servir o cronograma
    (nao so o total) para o operador ver quando o dinheiro sai.
    """
    from motor_expansao.dimensionamento.config import SIM_PARCELAS_FRANQUIA_DEFAULT

    # Obra e equipamentos ZERADOS: a linha `investimento` da serie e SO a franquia.
    corpo = _viab(obra=0, equipamentos=0, prazo_equipamentos=1)
    inv = corpo["investimento"]
    assert inv["parcelas_franquia"] == SIM_PARCELAS_FRANQUIA_DEFAULT == 4
    assert inv["franquia_parcela"] == pytest.approx(inv["taxa_franquia"] / 4, abs=0.01)

    pre = [linha for linha in corpo["serie_mensal"] if linha["fase"] == "pre_operacional"]
    assert [linha["mes"] for linha in pre] == [-4, -3, -2, -1]
    for linha in pre:
        assert linha["investimento"] == pytest.approx(inv["franquia_parcela"], abs=0.01)
    # A SOMA das parcelas e a taxa de franquia (nada se perde no cronograma).
    assert sum(linha["investimento"] for linha in corpo["serie_mensal"]) == pytest.approx(
        inv["taxa_franquia"], abs=0.01
    )


def test_payload_parcelas_franquia_1_reproduz_o_a_vista_sem_mexer_no_resultado(
    empty_data: Path,
) -> None:
    """`parcelas_franquia=1` = regra antiga (tudo no M-4). E parcelar NAO muda resultado.

    Parcelamento e timing de CAIXA: EBITDA, margem e break-even ficam identicos; so
    TIR e VPL melhoram. Payback nao muda porque as 4 parcelas cabem na pre-abertura.
    """
    parcelado = _viab()
    vista = _viab(parcelas_franquia=1)

    assert vista["investimento"]["parcelas_franquia"] == 1
    pre_p = [x for x in parcelado["serie_mensal"] if x["fase"] == "pre_operacional"]
    pre_v = [x for x in vista["serie_mensal"] if x["fase"] == "pre_operacional"]
    # A vista o M-4 carrega a taxa inteira a mais que os demais meses.
    assert pre_v[0]["investimento"] - pre_v[1]["investimento"] == pytest.approx(
        parcelado["investimento"]["taxa_franquia"], abs=0.01
    )
    assert len({x["investimento"] for x in pre_p}) == 1  # parcelado: 4 meses iguais

    # Resultado IDENTICO.
    for secao, chave in (
        ("dre", "ebitda"), ("dre", "margem"), ("dre", "folha"), ("dre", "custos_op"),
        ("break_even", "ebitda"), ("break_even", "caixa"),
        ("retorno", "payback"), ("retorno", "retorno_anual_desalavancado"),
    ):
        assert parcelado[secao][chave] == pytest.approx(vista[secao][chave], abs=0.01), (
            f"{secao}.{chave} mudou com o parcelamento (deveria ser so timing de caixa)"
        )
    assert parcelado["acumulado_mes_final"] == pytest.approx(
        vista["acumulado_mes_final"], abs=0.01
    )
    assert parcelado["investimento"]["investimento_total"] == pytest.approx(
        vista["investimento"]["investimento_total"], abs=0.01
    )

    # ...e o que melhora e o valor do dinheiro no tempo.
    assert parcelado["retorno"]["tir_anual"] > vista["retorno"]["tir_anual"]
    assert parcelado["retorno"]["vpl"] > vista["retorno"]["vpl"]


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


def test_municipios_ignora_categorias_fantasma(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regressao (bug de prod 2026-07-22): `nome_municipio` vem como Categorical com
    o dicionario NACIONAL de municipios (parquet dict-encoded -> a particao uf=SP
    carrega ~5,3k categorias, mas so 645 presentes). O groupby default
    (observed=False) gera 1 grupo por CATEGORIA — inclusive municipios de OUTRAS UFs,
    com 0 hexes -> ~4,6k municipios FANTASMA vazavam no seletor. O endpoint deve
    devolver SO os municipios presentes na particao."""
    part = tmp_path / "outputs" / "hexagonos_dashboard_enriquecido" / "uf=SP"
    part.mkdir(parents=True)
    df = _synthetic_enriched()
    presentes = list(dict.fromkeys(df["nome_municipio"]))  # distintos, ordem estavel
    fantasmas = [f"Fantasma {i}" for i in range(50)]  # municipios de outras UFs, sem hex
    df["nome_municipio"] = pd.Categorical(df["nome_municipio"], categories=presentes + fantasmas)
    df.to_parquet(part / "part-0.parquet")
    _point_app_at(monkeypatch, tmp_path)
    try:
        # sanity: o parquet PRESERVOU as categorias fantasma (senao o teste seria vacuo)
        check = pd.read_parquet(part / "part-0.parquet", columns=["nome_municipio"])
        assert str(check["nome_municipio"].dtype) == "category"
        assert len(check["nome_municipio"].cat.categories) == len(presentes) + len(fantasmas)

        nomes = [m["nome"] for m in pilot.municipios("SP")["municipios"]]
        assert len(nomes) == len(presentes), (
            f"esperava {len(presentes)} municipios reais, veio {len(nomes)} "
            "(categoria sem hex vazando = regressao do observed=False)"
        )
        assert not any(str(n).startswith("Fantasma") for n in nomes)
    finally:
        _clear_caches()


def test_relatorio_municipal_renderiza_e_passa_os_mapas(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regressao (bug 'relatorio municipal nao gera'): o endpoint DEVE renderizar as
    camadas de mapa e PASSA-LAS ao gerador. Antes chamava o gerador com mapas=None e o
    PDF saia com 'Mapa indisponivel' em toda pagina. Patcha os colaboradores nas
    fronteiras (o endpoint importa tudo de forma lazy do modulo relatorio_municipal)."""
    import motor_expansao.dashboard.relatorio_municipal as relmun
    from motor_expansao.api import service as api_service

    df = pd.DataFrame(
        {"nome_municipio": ["X"], "uf": ["DF"], "hex_id": ["8a"], "lat": [0.0], "lng": [0.0]}
    )
    monkeypatch.setattr(pilot, "carregar_uf_completo", lambda uf: df)
    monkeypatch.setattr(
        relmun, "_municipio_mask", lambda d, nome: pd.Series([True] * len(d), index=d.index)
    )
    monkeypatch.setattr(
        relmun,
        "agregar_municipio",
        lambda *a, **k: {"uf": "DF", "nome_municipio": "X", "n_hex_total": 1},
    )
    monkeypatch.setattr(api_service, "_competitors_ultra", lambda cfg: (None, None))

    chamada: dict[str, object] = {}

    def _fake_render(df_muni, result, *, competitors_df=None, ultra_df=None, basemap=False):
        chamada["render"] = True
        chamada["basemap"] = basemap
        return {c: b"PNG" for c in ("cobertura", "resumo", "score", "residual", "dominio")}

    monkeypatch.setattr(relmun, "render_mapas_municipio", _fake_render)

    capturado: dict[str, object] = {}

    def _fake_payloads(result, mapas=None, **k):
        capturado["mapas"] = mapas

        class _P:
            pdf_bytes = b"%PDF-1.4"
            pdf_filename = "r.pdf"

        return _P()

    monkeypatch.setattr(
        relmun, "gerar_payloads_download_relatorio_municipal", _fake_payloads
    )

    resp = pilot.relatorio_municipal(pilot.RelatorioMunicipalIn(uf="DF", municipio="X"))
    assert resp.media_type == "application/pdf"
    assert chamada.get("render") is True, "o endpoint nao chamou render_mapas_municipio"
    mapas = capturado.get("mapas")
    assert mapas is not None, "regressao: o gerador recebeu mapas=None (PDF sem mapas)"
    assert set(mapas) >= {"cobertura", "resumo", "score", "residual", "dominio"}


def test_rotas_http_apontam_para_o_handler_certo():
    """Regressao: cada rota HTTP tem que apontar para o SEU handler, nao um helper vizinho.

    Bug real (2026-07-24): `_residual_hexes_do_ponto` foi inserido ENTRE o
    `@app.post("/api/relatorio/pontual")` e `async def relatorio_pontual`, entao o decorator
    registrou o HELPER como rota -> o param `staging_dir: Path` (sem default) virou query
    obrigatoria -> 422 "missing staging_dir" em TODOS os relatorios pontuais. Os demais
    testes chamam as funcoes de rota DIRETO (sem HTTP), entao SO um teste de REGISTRO
    de rota pega esse tipo de erro de decorator.
    """
    esperado = {
        "/api/relatorio/pontual": "relatorio_pontual",
        "/api/relatorio/municipal": "relatorio_municipal",
        "/api/viabilidade": "viabilidade",
        "/api/executiva/{uf}": "executiva",
        "/api/health": "health",
    }
    registrado = {
        r.path: r.endpoint.__name__
        for r in pilot.app.routes
        if getattr(r, "path", "") in esperado
    }
    assert registrado == esperado


def test_relatorio_pontual_nao_bloqueia_o_event_loop():
    """Regressao de producao (2026-07-24): "o relatorio da aba Viabilidade carrega para
    sempre".

    A rota era `async def` com corpo 100% SINCRONO e pesado (interseccao de setores,
    tiles de basemap/satelite, matplotlib, fpdf). Num `async def`, esse corpo roda NO
    event loop do unico worker do uvicorn -> enquanto um PDF era gerado, toda outra
    requisicao ficava presa na fila. Medido em producao: 3 relatorios simultaneos
    serializaram em 12/21/31 s e um `/api/health` (trivial) levou 29 s.

    O contrato que impede a volta do defeito: a rota continua `async` (precisa do
    `await` dos uploads), mas o trabalho pesado vive numa funcao SINCRONA separada,
    despachada ao threadpool. Se alguem transformar o helper em `async def` de novo,
    ou reinserir o corpo pesado na rota, este teste quebra.
    """
    import inspect

    # A rota segue assincrona (le o corpo multipart das fotos com await).
    assert inspect.iscoroutinefunction(pilot.relatorio_pontual)

    # ...mas o gerador e SINCRONO -> `run_in_threadpool` o tira do event loop.
    assert not inspect.iscoroutinefunction(pilot._gerar_relatorio_pontual_pdf)

    # E a rota realmente delega (nao ficou com uma copia do corpo pesado).
    fonte = inspect.getsource(pilot.relatorio_pontual)
    assert "run_in_threadpool" in fonte
    assert "_gerar_relatorio_pontual_pdf" in fonte
    # O corpo pesado NAO pode estar na rota: nenhuma dessas chamadas ali dentro.
    for pesado in ("render_mapas_censitarios_combinados", "gerar_pdf_relatorio_pontual"):
        assert pesado not in fonte, f"corpo pesado ({pesado}) voltou para o event loop"

    # Teto de concorrencia: sem ele, N pedidos simultaneos disputariam as 4 CPUs da VPS.
    assert 1 <= pilot._PDF_CONCORRENCIA_MAX <= 4


def test_relatorio_municipal_tambem_fora_do_event_loop():
    """O Relatorio Municipal e igualmente pesado; como e `def` (nao `async def`), o
    proprio FastAPI ja o roda no threadpool. Trava esse invariante junto."""
    import inspect

    assert not inspect.iscoroutinefunction(pilot.relatorio_municipal)
