"""Testes das rotas do MODO DE PONTO do piloto web: `/api/ponto` e `/api/resolver-ponto`.

Cobre o CONTRATO (chaves e tipos JSON-serializaveis), a degradacao POR BLOCO quando
`data/staging` nao esta montado, e a separacao dos codigos de erro.

Nao ha rede aqui: os casos de `/api/resolver-ponto` exercitados sao os que o parser puro
resolve (coordenada crua e link LONGO). O caminho de link curto depende de seguir um
redirect e fica fora do teste de unidade de proposito.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]  # tests/unit/ -> raiz do worktree
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import app as pilot  # noqa: E402  (backend do piloto; web/server no sys.path acima)
from fastapi import HTTPException  # noqa: E402

# Av. Paulista 1000, Sao Paulo/SP — dentro da malha censitaria materializada.
LAT_SP, LNG_SP = -23.5613, -46.6565
# Lisboa: bounding box do Brasil recusa antes de qualquer leitura de disco.
LAT_LIS, LNG_LIS = 38.7223, -9.1393
# Atlantico, a mais de 2 km da costa: passa no bounding box, falha no ponto-em-poligono.
LAT_MAR, LNG_MAR = -25.0, -40.0


def _tem_malha() -> bool:
    """A malha censitaria e a malha municipal sao artefatos externos (gitignored)."""
    return (pilot.CENSO_GEO_DIR / "uf=SP").is_dir() and any(
        pilot.IBGE_DIR.glob("municipios_*.geojson")
    )


requer_malha = pytest.mark.skipif(
    not _tem_malha(), reason="malha censitaria/municipal nao materializada neste worktree"
)


# --------------------------------------------------------------------------- #
# /api/ponto — contrato                                                        #
# --------------------------------------------------------------------------- #
@requer_malha
def test_ponto_devolve_o_contrato_completo() -> None:
    body = pilot.ponto(lat=LAT_SP, lng=LNG_SP)

    assert set(body) >= {
        "lat", "lng", "raio_km", "hex_id", "local", "censo",
        "concorrencia", "mercado", "vizinhos",
    }
    # Raio canonico do Relatorio Pontual (DEC-021): a tela e o PDF contam a mesma coisa.
    assert body["raio_km"] == 1.0
    # H3 res-7, a resolucao do M1.
    assert isinstance(body["hex_id"], str) and len(body["hex_id"]) == 15


@requer_malha
def test_ponto_resolve_municipio_e_uf_pela_malha() -> None:
    local = pilot.ponto(lat=LAT_SP, lng=LNG_SP)["local"]
    assert local["uf"] == "SP"
    assert local["municipio"] == "São Paulo"
    # `unidade_tipo` e IDENTIFICADOR cru: nunca acentuado (CLAUDE.md §2).
    assert local["unidade_tipo"] in {"bairro", "distrito", None}
    if local["unidade_tipo"] is not None:
        assert local["unidade_tipo"] == local["unidade_tipo"].lower()
        assert local["unidade_tipo"].isascii()


@requer_malha
def test_ponto_traz_censo_real_e_plausivel() -> None:
    censo = pilot.ponto(lat=LAT_SP, lng=LNG_SP)["censo"]

    assert censo["disponivel"] is True
    assert censo["motivo"] is None
    # A malha IBGE 2022 nao depende de `data/staging`: estes numeros TEM de existir.
    for chave in ("populacao", "domicilios", "renda_per_capita", "densidade_hab_km2"):
        assert censo[chave] is not None, chave
        assert censo[chave] > 0, chave
    # Regiao central e densa de Sao Paulo: nao e' um valor de zona rural.
    assert censo["densidade_hab_km2"] > 5_000
    assert 0 <= censo["score_socioeconomico"] <= 100


# --------------------------------------------------------------------------- #
# Degradacao POR BLOCO — o ponto do exercicio                                  #
# --------------------------------------------------------------------------- #
@requer_malha
def test_bloco_sem_dado_diz_o_motivo_em_vez_de_sumir() -> None:
    """Sem `data/staging`, concorrencia e mercado ficam indisponiveis COM motivo.

    A cadeia degrada em silencio por desenho (`_competitors_ultra` devolve (None, None)
    e `_residual_do_ponto` devolve so' None). Se a rota apenas omitisse os campos, a tela
    mostraria card em branco e o operador leria como defeito.
    """
    body = pilot.ponto(lat=LAT_SP, lng=LNG_SP)

    for nome in ("concorrencia", "mercado"):
        bloco = body[nome]
        assert "disponivel" in bloco and "motivo" in bloco, nome
        if not bloco["disponivel"]:
            assert bloco["motivo"], f"{nome} indisponivel PRECISA de motivo por extenso"
            assert len(bloco["motivo"]) > 20, nome


@requer_malha
def test_payload_e_json_serializavel() -> None:
    """`analisar_ponto_censitario_setores` devolve 3 DataFrames (`concorrentes_raio`,
    `ultra_raio`, `setores_intersectados`). Devolver o dict cru quebraria o cliente."""
    import json

    texto = json.dumps(pilot.ponto(lat=LAT_SP, lng=LNG_SP))
    assert "NaN" not in texto  # NaN nao e JSON valido e quebra o JSON.parse do browser


# --------------------------------------------------------------------------- #
# Erros — 400 do operador x 404 de implantacao                                 #
# --------------------------------------------------------------------------- #
def test_coordenada_fora_do_brasil_para_no_bounding_box() -> None:
    with pytest.raises(HTTPException) as exc:
        pilot.ponto(lat=LAT_LIS, lng=LNG_LIS)
    assert exc.value.status_code == 400
    assert "fora do Brasil" in exc.value.detail


@requer_malha
def test_ponto_no_mar_aberto_vira_400_com_a_mensagem_da_malha() -> None:
    with pytest.raises(HTTPException) as exc:
        pilot.ponto(lat=LAT_MAR, lng=LNG_MAR)
    assert exc.value.status_code == 400
    # A mensagem vem do APIError de `_resolver_e_carregar`, propagada em vez de virar 500:
    # o piloto NAO registra handler de APIError.
    assert "malha municipal" in exc.value.detail


# --------------------------------------------------------------------------- #
# /api/resolver-ponto — sem rede                                               #
# --------------------------------------------------------------------------- #
def test_resolver_coordenada_crua() -> None:
    r = pilot.resolver_ponto(q=f"{LAT_SP}, {LNG_SP}")
    assert r["found"] is True
    assert r["via"] == "coordenada"
    assert r["lat"] == pytest.approx(LAT_SP)
    assert r["lng"] == pytest.approx(LNG_SP)


def test_resolver_link_longo_do_maps() -> None:
    r = pilot.resolver_ponto(
        q=f"https://www.google.com/maps/place/Av.+Paulista/@{LAT_SP},{LNG_SP},17z"
    )
    assert r["found"] is True
    assert r["via"] == "coordenada"  # o parse puro resolveu: nenhuma ida a rede
    assert r["lat"] == pytest.approx(LAT_SP)


def test_resolver_fora_do_brasil_tem_motivo_proprio() -> None:
    """Nao pode cair no generico "nao encontrei": a coordenada FOI lida, so' nao e' Brasil."""
    r = pilot.resolver_ponto(q=f"{LAT_LIS}, {LNG_LIS}")
    assert r["found"] is False
    assert "fora do Brasil" in r["motivo"]


def test_resolver_vazio_nao_vai_a_rede() -> None:
    r = pilot.resolver_ponto(q="   ")
    assert r["found"] is False
    assert r["motivo"]


# --------------------------------------------------------------------------- #
# Crescimento do ESTADO — bloco proprio, fora do funil                        #
# --------------------------------------------------------------------------- #
def _tem_enriquecido() -> bool:
    return pilot.ENRICHED_DIR.is_dir() and any(pilot.ENRICHED_DIR.glob("uf=*"))


requer_enriquecido = pytest.mark.skipif(
    not _tem_enriquecido(), reason="particao enriquecida nao materializada neste worktree"
)


@requer_enriquecido
def test_crescimento_estado_olha_a_uf_INTEIRA_nao_o_white_space() -> None:
    """O passo 4 descreve so' quem sobreviveu aos filtros; este bloco, o estado todo.

    Confundir os dois e' o erro facil: numa UF onde quase tudo tem concorrente, o
    passo 4 lista meia duzia de cidades e some com o resto.
    """
    body = pilot.uf_view("GO")
    bloco = body.get("crescimento_estado")
    assert bloco is not None, "a visao de UF precisa trazer o bloco"

    assert set(bloco) >= {
        "mediana_uf", "n_municipios_com_medicao", "n_municipios_uf",
        "pop_minima", "n_fora_do_piso", "itens",
    }
    # O universo do bloco e' MAIOR que o do passo 4 (que so' ve white space).
    passo4 = next(p for p in body["passos"] if p["n"] == 4)
    assert bloco["n_municipios_com_medicao"] > len(passo4["itens"])


@requer_enriquecido
def test_crescimento_estado_declara_o_piso_em_vez_de_cortar_em_silencio() -> None:
    """Sem piso, o topo e' municipio minusculo com variacao percentual enorme sobre
    base de poucas centenas de empregos. O corte existe, e o payload diz quanto cortou."""
    bloco = pilot.uf_view("GO")["crescimento_estado"]
    assert bloco["pop_minima"] == pilot.POP_MIN_ACIONAVEL
    assert isinstance(bloco["n_fora_do_piso"], int)
    assert bloco["n_fora_do_piso"] >= 0


@requer_enriquecido
def test_crescimento_estado_traz_a_mediana_da_propria_uf() -> None:
    """O CAGED so' vale contra margem estadual: sem a mediana no payload a tela nao
    teria contra o que dizer que a cidade cresce muito ou pouco."""
    bloco = pilot.uf_view("GO")["crescimento_estado"]
    assert bloco["mediana_uf"] is not None
    for it in bloco["itens"]:
        # A etiqueta e' RELATIVA a mediana, nunca um julgamento absoluto.
        assert it.get("tag"), "cada item precisa da etiqueta contra a mediana"


# --------------------------------------------------------------------------- #
# /api/estados — a unica rota que compara UFs                                 #
# --------------------------------------------------------------------------- #
@requer_enriquecido
def test_estados_ranqueia_as_ufs_pelo_residual_em_white_space() -> None:
    """A pergunta "por qual estado comecar?" nao tinha rota: o piloto le UMA particao
    por vez. Aqui as 27 sao lidas com projecao de colunas."""
    body = pilot.estados()
    assert set(body) >= {"reguas", "estados"}
    estados = body["estados"]
    assert len(estados) >= 20, "esperado o pais quase todo"

    # Ordenado por residual em white space, DECRESCENTE, e com rank coerente.
    valores = [e["residual_white_space"] or 0 for e in estados]
    assert valores == sorted(valores, reverse=True)
    assert [e["rank"] for e in estados] == list(range(1, len(estados) + 1))


@requer_enriquecido
def test_estados_usa_as_reguas_do_funil_e_nao_um_criterio_novo() -> None:
    reguas = pilot.estados()["reguas"]
    assert reguas["score_minimo"] == pilot.SCORE_CORTE_QUENTE
    assert reguas["pop_minima"] == pilot.POP_MIN_ACIONAVEL
    assert reguas["capacidade_concorrente"] == pilot.CAPACIDADE_CONCORRENTE_PADRAO


@requer_enriquecido
def test_estados_elegivel_nunca_passa_do_total() -> None:
    """O white space e' um SUBCONJUNTO do estado: se passar do total, o filtro inverteu."""
    for e in pilot.estados()["estados"]:
        assert e["hexes_elegiveis"] <= e["hexes_total"], e["uf"]
        if e["residual_white_space"] is not None and e["residual_total"] is not None:
            assert e["residual_white_space"] <= e["residual_total"] + 1, e["uf"]
