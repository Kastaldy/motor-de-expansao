"""BLK-MAPA-CHIP-01 — a etiqueta do ranking tem de VARIAR quando o dado varia.

Todos os testes aqui passam por `montar_funil` / `montar_funil_uf`. Nenhum chama
`_etiqueta`, `_etiqueta_muni`, `_faixa_para_chip` ou os `_chip_*` direto — esse atalho e'
exatamente o que deixou o contrato anterior verde sobre um vocabulario que a tela nunca
mostrava (validava com `n_concorrentes_est` = 2 e 99 numa camada cujo corte e' n == 0).

Tres deles sao CONTROLES NEGATIVOS: falham hoje e falhariam tambem numa correcao ingenua
que acertasse o numero pelo motivo errado.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd
import pytest

_SERVER = Path(__file__).resolve().parents[2] / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import app as pilot  # noqa: E402  (backend do piloto; web/server no sys.path acima)

# Os 8 municipios do cenario que o proprio bloco mediu: residual de 2.000 a 40.000 alunos,
# 20x de amplitude, TODOS acima do corte de OFERTA_DESTAQUE_MIN. Antes do fix os oito
# saiam com o chip `Livre` — zero variacao sobre uma ordem de grandeza e meia de dado.
_CENARIO_BACKLOG = [2_000, 2_400, 3_000, 5_000, 9_000, 15_000, 25_000, 40_000]


def _hexes(
    residuais: list[float],
    *,
    fonte_pop: str = "setor_2022",
    concorrentes: list[int] | None = None,
    pops: list[float] | None = None,
    cres: list[float] | None = None,
    municipios: list[str] | None = None,
) -> pd.DataFrame:
    """Um enriquecido sintetico com AMPLITUDE, passado pelo `_derivar` de producao.

    Passar pelo `_derivar` real e' deliberado: `n_concorrentes_est` e `pop_granular` sao
    colunas DERIVADAS, e uma fixture que as plantasse a mao poderia divergir da derivacao
    que o endpoint entrega ao funil — o teste ficaria verde sobre um caminho que producao
    nao percorre.
    """
    n = len(residuais)
    concorrentes = concorrentes if concorrentes is not None else [0] * n
    pops = pops if pops is not None else [5_100.0 + 1_000 * i for i in range(n)]
    municipios = municipios if municipios is not None else ["Cidade A"] * n
    linhas = []
    for i in range(n):
        linhas.append(
            {
                "hex_id": f"87a{i:04d}0000000ffff",
                "lat": -23.5 + 0.001 * i,
                "lng": -46.6 + 0.001 * i,
                "nome_municipio": municipios[i],
                "cod_municipio": f"35{i:05d}",
                "score_priorizacao": 85.0,
                # >= SCORE_CORTE_QUENTE, e variando dentro da faixa alcancavel (70-100).
                "score_setor_2022_calibrado": 71.0 + (i * 29.0 / max(1, n - 1)),
                "score_expansao_hibrido": 70.0,
                "score_oportunidade_residual": 90.0,
                "oferta_efetiva_disponivel": float(residuais[i]),
                "oferta_consumida_mercado_estimada": 2_500.0 * concorrentes[i],
                "capacidade_default_concorrente_alunos": 2_500.0,
                "sam_fitness_potencial": float(residuais[i]) + 1_000.0,
                "populacao_corte_hex": pops[i],
                "fonte_populacao_corte": fonte_pop,
                "pop_total": pops[i],
                "pop_total_setor_2022": pops[i],
                "renda_per_capita": 3_000.0,
                "renda_per_capita_setor_2022_calibrada": 3_100.0,
                # CONSTANTE de proposito: e' a faixa saturada que o chip antigo publicava.
                # Se o chip novo variar com ela cravada, a variacao veio de outro lugar.
                "faixa_oportunidade": "prioridade_maxima",
                "n_unidades_ultra_performance_hex": 0,
                "densidade_pop_setor_hab_km2": 5_000.0,
                **({"cres_emp_pct": cres[i]} if cres is not None else {}),
                **({"cres_uf_mediana": 5.0} if cres is not None else {}),
            }
        )
    return pilot._derivar(pd.DataFrame(linhas))


def _bairros(df: pd.DataFrame) -> dict[str, str]:
    """Um bairro por hex: sem isso `_rank_items` deduplica por nome de municipio e o
    ranking inteiro colapsa em UM item — nao haveria variacao a medir."""
    return {hid: f"Bairro {i}" for i, hid in enumerate(df["hex_id"])}


def _tags(passo: dict) -> list[str]:
    return [i["tag"] for i in passo["itens"]]


def _numero(chip: str) -> float:
    """O numero de dentro do chip, em pt-BR (milhar com ponto, decimal com virgula)."""
    achado = re.search(r"[\d.]+(?:,\d+)?", chip)
    assert achado, f"chip sem numero: {chip!r}"
    return float(achado.group().replace(".", "").replace(",", "."))


# ============================================================================
# Criterio de aceite 1 — a camada 2 varia com a amplitude medida
# ============================================================================


def test_camada_2_varia_no_cenario_medido_do_backlog() -> None:
    """O cenario exato do bloco: 8 municipios de 2.000 a 40.000 alunos residuais.

    Medicao registrada no backlog: os oito saiam `Livre`. Amplitude de 20x no dado, zero
    variacao na etiqueta.
    """
    df = _hexes(
        _CENARIO_BACKLOG,
        municipios=[f"Cidade {i}" for i in range(len(_CENARIO_BACKLOG))],
    )
    passo2 = pilot.montar_funil_uf(df, "SP")[1]
    tags = _tags(passo2)

    assert len(tags) == len(_CENARIO_BACKLOG)
    assert len(set(tags)) == len(_CENARIO_BACKLOG), (
        f"a camada 2 voltou a colapsar: {tags}. Com 2.000 a 40.000 alunos os oito itens "
        "tem de sair com etiquetas distintas."
    )
    # E o chip cresce junto com o dado, na ordem — nao e' so' "diferente", e' MONOTONO.
    numeros = [_numero(t) for t in tags]
    assert numeros == sorted(numeros, reverse=True), (
        f"o ranking desce por residual mas o chip nao acompanha: {tags}"
    )


def test_camada_2_no_municipio_varia_entre_bairros() -> None:
    df = _hexes([6_118, 5_564, 4_157, 2_328])
    passos = pilot.montar_funil(df, "Cidade A", _bairros(df))
    tags = _tags(passos[1])
    assert len(set(tags)) == len(tags), f"camada 2 municipal constante: {tags}"


# ============================================================================
# CONTROLE NEGATIVO 1 — o chip da camada 2 e' a conversao do PROPRIO valor do item
# ============================================================================


@pytest.mark.parametrize("escopo", ["municipio", "uf"])
def test_chip_de_academias_reconstroi_o_valor_exibido(escopo: str) -> None:
    """Falha se o chip vier de qualquer outro agregado que nao o numero do proprio item.

    E' o controle negativo do descolamento de escala que existia: na visao de UF o chip
    saia da faixa de UM hexagono (clipada em 2.500 alunos) enquanto o valor exibido era a
    SOMA do municipio (938.487 em Sao Paulo). Os dois numeros conviviam a 40 px de
    distancia dizendo coisas incompativeis.

    Reconstroi pelos DOIS ramos do formatador — uma casa decimal abaixo de 10 academias,
    inteiro com separador de milhar acima. Uma versao do teste que so' cobrisse um ramo
    passaria verde sobre a troca de precisao.
    """
    residuais = [42_000, 25_000, 9_000, 2_400]
    if escopo == "uf":
        df = _hexes(residuais, municipios=[f"Cidade {i}" for i in range(len(residuais))])
        passo = pilot.montar_funil_uf(df, "SP")[1]
    else:
        df = _hexes(residuais)
        passo = pilot.montar_funil(df, "Cidade A", _bairros(df))[1]

    assert passo["itens"], "fixture nao acendeu a camada 2"
    for item in passo["itens"]:
        esperado = item["valor"] / 2_500
        obtido = _numero(item["tag"])
        casas = 0 if round(esperado, 1) >= 10 else 1
        assert obtido == pytest.approx(round(esperado, casas), abs=0.05), (
            f"{escopo}: item vale {item['valor']} alunos (= {esperado:.2f} academias) mas o "
            f"chip diz {item['tag']!r}. O chip deixou de ser a conversao do proprio valor."
        )


# ============================================================================
# CONTROLE NEGATIVO 2 — a camada 1 nao inventa populacao quando a fonte e' municipal
# ============================================================================


def test_camada_1_cala_quando_a_populacao_e_do_municipio_inteiro() -> None:
    """Dois dataframes IDENTICOS, exceto `fonte_populacao_corte`.

    `populacao_corte_hex` tem fallback para o total do municipio repetido em cada hexagono
    (`total_municipal`): 802.007 hexes no pais, 100% das linhas em 12 UFs. Sem a guarda, o
    chip imprimiria "1,5 mi hab." dentro de um hexagono de ~5 km2 do Recife.

    Este teste falha HOJE (a camada 1 emitia `Excelente` nos dois casos) e falha tambem
    numa correcao ingenua que lesse `pop_leitura` sem checar a fonte — que e' o ponto de
    um controle negativo.
    """
    residuais = [6_000.0, 5_000.0, 4_000.0]
    pops = [1_488_920.0, 900_000.0, 500_000.0]

    granular = _hexes(residuais, fonte_pop="setor_2022", pops=pops)
    municipal = _hexes(residuais, fonte_pop="total_municipal", pops=pops)

    tags_g = _tags(pilot.montar_funil(granular, "Cidade A", _bairros(granular))[0])
    tags_m = _tags(pilot.montar_funil(municipal, "Cidade A", _bairros(municipal))[0])

    assert all(tags_g), f"com censo granular a camada 1 tem de rotular: {tags_g}"
    assert len(set(tags_g)) == len(tags_g), f"camada 1 constante: {tags_g}"
    assert tags_m == [""] * len(tags_m), (
        f"com a populacao vinda do total do municipio a camada 1 tem de CALAR, e saiu "
        f"{tags_m}. Um desses numeros seria a populacao da cidade inteira dentro de um "
        "hexagono."
    )


def test_chip_da_camada_1_e_a_populacao_do_proprio_hexagono() -> None:
    """CONTROLE NEGATIVO: o numero do chip tem de ser a populacao DAQUELE hexagono.

    O teste irmao (`test_camada_1_cala_quando_...`) so' checa vazio contra nao-vazio: ele
    passaria se o chip mostrasse a populacao de OUTRO hexagono, ou uma soma, contanto que
    variasse entre itens. Aqui o valor e' reconstruido a partir de `populacao_corte_hex`,
    nos dois ramos do formatador — milhares e milhoes.

    As populacoes sao distintas por hexagono E diferentes de qualquer soma parcial, entao
    um chip que agregasse por engano cairia fora da tolerancia de arredondamento.
    """
    pops = [12_400.0, 26_660.0, 1_450_000.0, 7_800.0]
    df = _hexes([6_000, 5_000, 4_000, 3_000], pops=pops)
    itens = pilot.montar_funil(df, "Cidade A", _bairros(df))[0]["itens"]
    assert len(itens) == len(pops), f"a camada 1 devolveu {len(itens)} itens"

    por_hex = dict(zip(df["hex_id"], pops, strict=True))
    for item in itens:
        pop = por_hex[item["hex_id"]]
        esperado = (
            f"{pop / 1e6:.1f} mi hab.".replace(".", ",", 1)
            if pop >= 1_000_000
            else f"{round(pop / 1000):.0f} mil hab."
        )
        assert item["tag"] == esperado, (
            f"hexagono com {pop:.0f} habitantes saiu com o chip {item['tag']!r}; esperado "
            f"{esperado!r}. O chip deixou de ler a populacao do proprio hexagono."
        )


def test_sem_a_coluna_de_fonte_da_populacao_o_chip_cala() -> None:
    """A guarda promete "coluna ausente -> chip vazio, nunca numero errado". Aqui ela roda.

    Nenhuma outra fixture omite `fonte_populacao_corte`, entao este ramo de `_derivar` (o
    `else False`) ficava sem cobertura — e e' justamente ele que protege um artefato
    antigo, sem a coluna, de virar "1,5 mi hab." dentro de um hexagono.
    """
    df = _hexes([6_000, 5_000, 4_000], pops=[12_000.0, 30_000.0, 900_000.0])
    sem_coluna = pilot._derivar(df.drop(columns=["fonte_populacao_corte"]))
    assert not sem_coluna["pop_granular"].any(), "a guarda de `_derivar` deixou de valer"

    tags = _tags(pilot.montar_funil(sem_coluna, "Cidade A", _bairros(sem_coluna))[0])
    assert tags == [""] * len(tags), (
        f"sem `fonte_populacao_corte` a camada 1 tem de calar, e saiu {tags}"
    )


# ============================================================================
# CONTROLE NEGATIVO 3 — a camada 3 usa o residual TOTAL como denominador
# ============================================================================


def test_camada_3_uf_divide_pelo_residual_total_do_municipio() -> None:
    """Mesmo white space, residuais totais diferentes -> etiquetas diferentes.

    So' passa se o denominador for mesmo a soma do conjunto da camada 2. Um chip que
    dividisse pelo proprio white (sempre 100%) ou que ordenasse por coincidencia falharia
    aqui: as duas cidades tem o MESMO numerador, entao qualquer leitura que ignore o
    denominador as empata.
    """
    df = _hexes(
        # Cidade A: 10.000 livres de um total de 10.000  -> 100%
        # Cidade B: 10.000 livres de um total de 40.000  -> 25%
        [10_000, 10_000, 30_000],
        concorrentes=[0, 0, 3],
        municipios=["Cidade A", "Cidade B", "Cidade B"],
    )
    passo3 = pilot.montar_funil_uf(df, "SP")[2]
    por_cidade = {i["municipio"]: i["tag"] for i in passo3["itens"]}

    assert por_cidade["Cidade A"] == "100% sem disputa", por_cidade
    assert por_cidade["Cidade B"] == "25% sem disputa", por_cidade
    assert por_cidade["Cidade A"] != por_cidade["Cidade B"], (
        "as duas cidades tem o mesmo white space e residuais totais diferentes; se as "
        "etiquetas empatam, o denominador nao esta sendo lido"
    )


def test_camada_3_nunca_passa_de_cem_por_cento() -> None:
    """O clamp existe porque numerador e denominador vem de recortes distintos."""
    df = _hexes([9_000, 3_000], municipios=["Cidade A", "Cidade B"])
    for item in pilot.montar_funil_uf(df, "SP")[2]["itens"]:
        assert _numero(item["tag"]) <= 100, item


# ============================================================================
# Camadas que nao emitem chip, e o painel que declara o porque
# ============================================================================


def test_camadas_saturadas_saem_sem_chip() -> None:
    """Camada 1/UF, camada 3/municipio e camada 5/municipio: sem etiqueta, `tag_cor` nulo.

    Nas tres, todo item e' igual na dimensao da camada por construcao do corte. Rotulo
    constante nao informa — e, na camada 5, a faixa `prioridade_maxima` esta cravada na
    fixture justamente para provar que o chip nao voltou a sair dela.
    """
    df = _hexes(
        _CENARIO_BACKLOG, municipios=[f"Cidade {i}" for i in range(len(_CENARIO_BACKLOG))]
    )
    uf = pilot.montar_funil_uf(df, "SP")
    assert _tags(uf[0]) == [""] * len(uf[0]["itens"]), _tags(uf[0])
    assert all(i["tag_cor"] is None for i in uf[0]["itens"])

    dm = _hexes([6_118, 4_157, 2_788, 2_328])
    mun = pilot.montar_funil(dm, "Cidade A", _bairros(dm))
    for n in (2, 4):  # indices 2 e 4 = camadas 3 e 5
        assert _tags(mun[n]) == [""] * len(mun[n]["itens"]), (n, _tags(mun[n]))
        assert all(i["tag_cor"] is None for i in mun[n]["itens"])


def test_camada_5_nao_emite_chip_em_nenhum_escopo() -> None:
    """A camada 5 nao rotula — e' proposital, e o motivo e' colisao de reguas.

    Um chip de crescimento chegou a existir aqui. Foi removido: o `NarrativePanel` ja
    renderiza `<EtiquetaCrescimento>` em TODO item do passo 5, e as duas leituras
    classificam os mesmos dois numeros por reguas diferentes — o front por DELTA em pontos
    percentuais (`lerCrescimento`, margem de 0,5 p.p.) e o servidor por RAZAO
    (`_etiqueta_crescimento`, cortes 0,8/1,2/2,0). Medido em Sao Jose do Rio Preto (10,0
    contra mediana 9,0 da UF): razao 1,11 daria "na mediana" no chip enquanto a linha de
    baixo dizia "Cresce acima da mediana (+1,0 p.p.)". Duas afirmacoes opostas no mesmo item.

    Com `cres_emp_pct` presente OU ausente o resultado e' o mesmo: sem chip.
    """
    munis = [f"Cidade {i}" for i in range(4)]
    for cres in ([5.0, 12.0, 1.0, 7.0], None):
        df = _hexes([40_000, 25_000, 9_000, 3_000], municipios=munis, cres=cres)
        tags = _tags(pilot.montar_funil_uf(df, "SP")[4])
        assert tags == [""] * len(tags), (
            f"camada 5 voltou a emitir chip (cres={'sim' if cres else 'nao'}): {tags}. Se for "
            "leitura de crescimento, ela contradiz a EtiquetaCrescimento do mesmo item."
        )

    dm = _hexes([6_118, 4_157, 2_788, 2_328])
    tags_mun = _tags(pilot.montar_funil(dm, "Cidade A", _bairros(dm))[4])
    assert tags_mun == [""] * len(tags_mun), tags_mun


def test_camada_4_nao_muda_uma_letra() -> None:
    """A unica camada que ja discriminava fica byte a byte igual.

    `CrescimentoDoEstado.tsx` renderiza esta mesma string como `<span>` cru, e o refactor
    que extraiu `_chip_crescimento_curto` chama `_etiqueta_crescimento` por dentro — se
    alguem inverter a dependencia, a camada 4 herda o texto curto sem ninguem notar.
    """
    munis = [f"Cidade {i}" for i in range(4)]
    df = _hexes([40_000, 25_000, 9_000, 3_000], municipios=munis, cres=[10.0, 12.0, 1.0, 7.0])
    tags = _tags(pilot.montar_funil_uf(df, "SP")[3])
    assert tags, "camada 4 sem itens: a fixture nao acendeu o crescimento"
    assert all(t.endswith("do estado") for t in tags), (
        f"a camada 4 perdeu o sufixo 'do estado' — texto curto da camada 5 vazou: {tags}"
    )


def test_chip_cabe_no_espaco_do_item() -> None:
    """O chip e' 10px uppercase com `nowrap` num item de 394 px que ja carrega rank,
    titulo e valor. Rotulo longo empurra o layout.

    A camada 4 fica FORA: ela nao foi tocada pelo bloco e ja emite 26 caracteres
    ("3x a mediana do estado" e variantes). Incluir a faria nascer vermelha.
    """
    df = _hexes(
        _CENARIO_BACKLOG,
        municipios=[f"Cidade {i}" for i in range(len(_CENARIO_BACKLOG))],
        cres=[1.0 + i for i in range(len(_CENARIO_BACKLOG))],
    )
    dm = _hexes([6_118, 4_157, 2_788, 2_328])
    passos = [
        *(p for p in pilot.montar_funil_uf(df, "SP") if p["n"] != 4),
        *(p for p in pilot.montar_funil(dm, "Cidade A", _bairros(dm)) if p["n"] != 4),
    ]
    for passo in passos:
        for item in passo["itens"]:
            assert len(item["tag"]) <= 20, (
                f"camada {passo['n']}: chip {item['tag']!r} tem {len(item['tag'])} "
                "caracteres e estoura o item do ranking"
            )
