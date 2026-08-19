"""BLK-MA-17-FU1: o bucket H3 da `dedup_independentes` passa a cobrir o limiar de fato.

Até 2026-08-18 a função buscava o candidato em `h3.grid_disk(celulas[i], 1)` — `k` **cravado** —
com `DEDUP_INDEPENDENTES_M = 50 m`. Na `DEDUP_H3_RES = 11` a aresta média medida é **28,66 m**, e
`grid_disk(k=1)` alcança apenas células cujo centro está a ~1,5 arestas: **não** há garantia
nenhuma de cobrir 50 m. A fórmula que o BLK-MA-17 introduziu no mesmo arquivo dá
`_k_do_bucket(50) = 4`.

**Por que isso não levantava.** A função só colapsa entre `fonte` DIFERENTES e o snapshot `2026-33`
só tem WellHub: `0 de 19.329` colapsos. O modo de falha de uma dedup sub-coberta é
**indistinguível** do caso correto — ela devolve "nenhum colapso", que é exatamente o que uma dedup
correta devolve quando não há duplicata. Só uma comparação contra varredura completa separa os dois.

**O custo quando o TotalPass entrar.** A duplicata que não colapsa vira duas linhas na oferta; a
gêmea a ~0 m soma `peso(0) x PESO_OFERTA_INDEPENDENTE` -> até **+33,3 pontos** de pressão fantasma
— o mesmo fantasma que a DEC-033 criou a dedup para matar.

**Nota sobre a densidade das fixtures.** A fixture de equivalência é ESPARSA de propósito: com
pontos densos cada um tem vários candidatos, então perder o que está no anel 2 não muda quem
colapsa, e o teste passa mesmo com `k = 1`. Medido: numa nuvem de 80 pontos em ~200 m havia 219
pares qualificados e o `k` cravado não alterava o resultado. Pares ISOLADOS são o que exercita o
bucket.

READ-ONLY sobre o M1.
"""

from __future__ import annotations

import math

import h3
import numpy as np
import pandas as pd
import pytest

from motor_expansao.vulnerabilidade import contrato as c
from motor_expansao.vulnerabilidade.pressao_competitiva import (
    _haversine_m,
    _k_do_bucket,
    dedup_cadeias_do_feed,
    dedup_independentes,
)

_LAT, _LNG = -23.5500, -46.6300
_GRAU_LAT_M = 111_320.0


def _distancia(lat_a: float, lng_a: float, lat_b: float, lng_b: float) -> float:
    return float(
        _haversine_m(
            np.array([lat_a]), np.array([lng_a]), np.array([lat_b]), np.array([lng_b])
        )[0]
    )


def _par_fora_do_anel_1(lat_base: float, lng_base: float) -> tuple[float, float] | None:
    """Ponto a <= 50 m da base cuja célula está FORA de `grid_disk(k=1)`, ou `None`.

    Busca por AZIMUTE em vez de cravar coordenada: a célula em que um ponto cai depende de onde ele
    pousa dentro da grade H3, e um par que hoje está no anel 2 poderia deixar de estar com outra
    versão do `h3` — o teste passaria a verde sem provar nada.

    Devolve `None` quando a base cai perto do CENTRO da sua célula: dali o anel 1 alcança ~71 m em
    todas as direções, e nenhum ponto dentro dos 50 m escapa dele. Só bases próximas da BORDA
    produzem o caso que o `k` cravado perdia — por isso `_cluster_que_exercita_o_bucket` varre a
    base, em vez de assumir que qualquer uma serve.
    """
    celula_base = h3.latlng_to_cell(lat_base, lng_base, c.DEDUP_H3_RES)
    vizinhas = set(h3.grid_disk(celula_base, 1))
    for graus in range(0, 360, 5):
        radianos = math.radians(graus)
        distancia = 49.0
        lat = lat_base + (distancia * math.cos(radianos)) / _GRAU_LAT_M
        lng = lng_base + (distancia * math.sin(radianos)) / (
            _GRAU_LAT_M * math.cos(math.radians(lat_base))
        )
        if h3.latlng_to_cell(lat, lng, c.DEDUP_H3_RES) in vizinhas:
            continue
        if _distancia(lat_base, lng_base, lat, lng) <= c.DEDUP_INDEPENDENTES_M:
            return lat, lng
    return None


def _cluster_que_exercita_o_bucket(lat_inicial: float) -> tuple[float, float, float]:
    """`(lat_base, lat_par, lng_par)` do primeiro cluster, a partir de `lat_inicial`, com par
    qualificado FORA do anel 1. Desloca a base ~2 m por passo até achar uma perto da borda."""
    for passo in range(300):
        lat_base = lat_inicial + passo * 0.00002
        achado = _par_fora_do_anel_1(lat_base, _LNG)
        if achado is not None:
            return lat_base, achado[0], achado[1]
    raise AssertionError(
        f"nenhuma base a partir de {lat_inicial} produziu par fora do anel 1 — revisar a fixture"
    )


def _independentes(linhas: list[tuple[str, str, float, float]]) -> pd.DataFrame:
    """`(fonte, chave_snapshot, lat, lng)` — o frame mínimo que a dedup exige."""
    return pd.DataFrame(
        {
            "fonte": [f for f, _, _, _ in linhas],
            "chave_snapshot": [k for _, k, _, _ in linhas],
            "lat": [la for _, _, la, _ in linhas],
            "lng": [ln for _, _, _, ln in linhas],
        }
    )


def test_o_k_derivado_do_limiar_de_independentes_e_maior_que_1() -> None:
    """A guarda que impede a regressão para o literal, no molde do `test_13` do BLK-MA-17."""
    assert _k_do_bucket(c.DEDUP_INDEPENDENTES_M) > 1, (
        "k=1 nao cobre 50 m na resolucao 11 — o `k` tem de sair do limiar"
    )
    aresta = float(h3.average_hexagon_edge_length(c.DEDUP_H3_RES, unit="m"))
    assert 28.0 < aresta < 29.0, f"aresta media mudou ({aresta:.2f} m); revisar o comentario"


def test_par_a_49m_em_fontes_distintas_colapsa_apesar_de_cair_fora_do_anel_1() -> None:
    """O caso concreto que o `k = 1` perdia.

    Com o `k` cravado em 1 a busca nem chegava ao candidato, e a função devolvia "nenhum colapso" —
    silenciosamente somando a mesma academia duas vezes na oferta.
    """
    lat_a, lat_b, lng_b = _cluster_que_exercita_o_bucket(_LAT)

    # `totalpass` < `wellhub` na ordem estável, então a primeira sobrevive e a segunda colapsa.
    frame = _independentes([("totalpass", "a", lat_a, _LNG), ("wellhub", "b", lat_b, lng_b)])
    pontos, mapa = dedup_independentes(frame)

    assert len(pontos) == 1, "a duplicata entre fontes tinha de colapsar"
    assert mapa[("totalpass", "a")] == 0
    assert mapa[("wellhub", "b")] == 0, "a colapsada aponta para o representante"


def test_a_guarda_de_fonte_sobrevive_ao_k_maior() -> None:
    """Ampliar o `k` amplia o conjunto de candidatos — a guarda de MESMA fonte não pode ceder.

    Duas linhas da mesma fonte a 40 m são duas academias, por decisão registrada (a chave já é
    única por fonte). Se o `k` maior passasse a colapsá-las, o bloco apagaria concorrente real —
    exatamente o custo assimétrico que a DEC-034 mediu do outro lado.
    """
    lat_b = _LAT + 40.0 / _GRAU_LAT_M
    frame = _independentes([("wellhub", "a", _LAT, _LNG), ("wellhub", "b", lat_b, _LNG)])
    pontos, mapa = dedup_independentes(frame)

    assert len(pontos) == 2, "mesma fonte NUNCA colapsa, por mais que o bucket cresca"
    assert mapa[("wellhub", "a")] == 0
    assert mapa[("wellhub", "b")] == 1


def test_equivalencia_contra_varredura_completa() -> None:
    """A única prova de que o bucket não mudou resultado. Molde do `test_14b` do BLK-MA-17.

    Compara-se o CONJUNTO de chaves colapsadas, não o representante de cada uma: diferente da
    `dedup_cadeias_do_feed` (que escolhe o ponto qualificado MAIS PRÓXIMO, com desempate por menor
    índice), esta função para no PRIMEIRO candidato que encontrar, e a ordem em que o `grid_disk`
    devolve as células não é a ordem dos índices. Quem colapsa é determinístico; qual representante
    absorve, quando há mais de um candidato, não é. O invariante forte — "não perder colapso" — é o
    que este teste trava, e é o que o `k` cravado violava.
    """
    linhas: list[tuple[str, str, float, float]] = []
    esperado_fora_do_anel_1 = 0

    # Clusters ISOLADOS entre si (~400 m), cada um com um par de fontes distintas. Metade dos pares
    # cai fora do anel 1 (só o `k` derivado os alcança); a outra metade fica perto, e serve de
    # controle — ela tem de colapsar nos dois regimes.
    for indice in range(6):
        base_lat, lat_b, lng_b = _cluster_que_exercita_o_bucket(_LAT + indice * 0.0036)
        linhas.append(("totalpass", f"longe{indice}a", base_lat, _LNG))
        linhas.append(("wellhub", f"longe{indice}b", lat_b, lng_b))
        esperado_fora_do_anel_1 += 1

    for indice in range(4):
        base_lat = _LAT + 0.03 + indice * 0.0036
        linhas.append(("totalpass", f"perto{indice}a", base_lat, _LNG))
        linhas.append(("wellhub", f"perto{indice}b", base_lat + 15.0 / _GRAU_LAT_M, _LNG))

    # Solitários: nenhum candidato a qualquer distância, para o teste também provar o não-colapso.
    for indice in range(5):
        linhas.append(("wellhub", f"solo{indice}", _LAT + 0.06 + indice * 0.0036, _LNG))

    assert esperado_fora_do_anel_1 >= 1, "a fixture nao exercita o bucket: o teste nao provaria nada"

    frame = _independentes(linhas)
    pontos, mapa = dedup_independentes(frame)

    # VARREDURA COMPLETA, sem bucket nenhum: a referência contra a qual a otimização se prova.
    ordenado = frame.sort_values(["fonte", "chave_snapshot"], kind="stable").reset_index(drop=True)
    f_ord = ordenado["fonte"].astype(str).to_numpy()
    k_ord = ordenado["chave_snapshot"].astype(str).to_numpy()
    la_ord = ordenado["lat"].to_numpy(dtype="float64")
    ln_ord = ordenado["lng"].to_numpy(dtype="float64")

    mantidos_ref: list[int] = []
    colapsadas_ref: set[str] = set()
    for i in range(len(ordenado)):
        achou = any(
            f_ord[j] != f_ord[i]
            and _distancia(la_ord[i], ln_ord[i], la_ord[j], ln_ord[j])
            <= c.DEDUP_INDEPENDENTES_M
            for j in mantidos_ref
        )
        if achou:
            colapsadas_ref.add(k_ord[i])
        else:
            mantidos_ref.append(i)

    assert len(colapsadas_ref) == 10, (
        f"a fixture deveria produzir 10 colapsos (6 longe + 4 perto), produziu "
        f"{len(colapsadas_ref)}"
    )

    sobreviventes = set(pontos["chave_snapshot"].astype(str))
    colapsadas_obtidas = set(k_ord) - sobreviventes

    assert colapsadas_obtidas == colapsadas_ref
    assert len(pontos) == len(mantidos_ref)

    # E o representante de toda colapsada é mesmo um ponto QUALIFICADO — invariante bem definido
    # mesmo quando há empate de candidatos.
    lat_s = pontos["lat"].to_numpy(dtype="float64")
    lng_s = pontos["lng"].to_numpy(dtype="float64")
    f_s = pontos["fonte"].astype(str).to_numpy()
    for i in range(len(ordenado)):
        if k_ord[i] not in colapsadas_obtidas:
            continue
        pos = mapa[(f_ord[i], k_ord[i])]
        distancia = _distancia(la_ord[i], ln_ord[i], lat_s[pos], lng_s[pos])
        assert distancia <= c.DEDUP_INDEPENDENTES_M, (
            f"representante de {k_ord[i]} esta a {distancia:.1f} m"
        )
        assert f_s[pos] != f_ord[i], "o representante tem de ser de outra fonte"


def test_fonte_unica_continua_com_zero_colapso() -> None:
    """O efeito sobre o dado de HOJE é exatamente nulo — o snapshot `2026-33` só tem WellHub.

    Trava a afirmação que torna este bloco seguro de mergear: o `k` maior não muda nenhum número
    enquanto houver uma fonte só, por mais próximas que as academias estejam.
    """
    rng = np.random.default_rng(20260818)
    n = 60
    lat = _LAT + rng.uniform(-0.0005, 0.0005, n)
    lng = _LNG + rng.uniform(-0.0005, 0.0005, n)
    frame = _independentes(
        [("wellhub", f"k{i}", float(lat[i]), float(lng[i])) for i in range(n)]
    )

    pontos, mapa = dedup_independentes(frame)

    assert len(pontos) == n, "com fonte unica NENHUMA linha pode colapsar"
    assert sorted(mapa.values()) == list(range(n))


# --------------------------------------------------------------------------- #
# Chave duplicada — a exclusão silenciosa do ponto errado                      #
# --------------------------------------------------------------------------- #
def test_chave_duplicada_levanta_nas_duas_dedups() -> None:
    """`posicao_por_chave` é um `dict`: com `(fonte, chave)` repetido, a segunda linha sobrescreve
    a primeira e a auto-exclusão da perdida passa a apontar para o índice de OUTRA academia.

    O pipeline não produz isso hoje — `coordenadas_por_chave` faz
    `drop_duplicates(subset=["fonte","chave_snapshot"])` —, mas as duas funções são públicas e o
    modo de falha é silencioso: nenhum erro, só um ponto excluído no lugar errado.
    """
    repetido = _independentes(
        [
            ("wellhub", "mesma", _LAT, _LNG),
            ("wellhub", "mesma", _LAT + 100.0 / _GRAU_LAT_M, _LNG),
        ]
    )
    with pytest.raises(ValueError, match="duplicado"):
        dedup_independentes(repetido)

    feed = repetido.assign(rede="bluefit")
    mapeados = pd.DataFrame({"lat": [_LAT + 0.05], "lng": [_LNG], "rede": ["smart_fit"]})
    with pytest.raises(ValueError, match="duplicado"):
        dedup_cadeias_do_feed(feed, mapeados)
