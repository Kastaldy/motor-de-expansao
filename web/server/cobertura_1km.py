"""PROTOTIPO — o hexagono partido em LIVRE e COBERTO pelo raio de 1 km.

POR QUE EXISTE. Colorir o hexagono inteiro de uma cor so' esconde o que importa para o
estudo de ponto: um imovel pode estar sob o disco de uma concorrente por um lado e livre
por outro. O agregado ("este hexagono perde 1.477 alunos") nao diz em que direcao.

O QUE E' DEVOLVIDO. Duas pecas por hexagono (cada uma com o SEU score) mais UM contorno
do alcance total (fronteira da uniao dos discos, sem linhas internas):

    COBERTO = hexagono INTERSECAO (uniao dos discos de 1 km)   -> score pior
    LIVRE   = hexagono MENOS essa uniao                        -> score melhor

E por isso que a parte livre "melhora" no mapa: ali nenhuma concorrente alcanca, entao o
residual daquele pedaco nao leva desconto de concorrencia. O hexagono deixa de ter uma cor
media que mente sobre as duas metades.

POR QUE UNIAO, E NAO UMA PECA POR CONCORRENTE. A versao anterior emitia uma peca por
concorrente para que o alpha se acumulasse na sobreposicao. Em campo isso poluiu o mapa:
49 concorrentes recortando o mesmo hexagono viravam 49 poligonos empilhados, cada um com
borda. Agora a area coberta e' UMA regiao limpa, e a intensidade da disputa vem do
SCORE (que ja cai quanto mais concorrente consome) — nao de empilhar geometria.

COMO OS SCORES SAO DERIVADOS (so' colunas existentes; nao reimplementa o Bloco 5)
---------------------------------------------------------------------------------
Do Bloco 5: `oferta_efetiva_disponivel = max(sam - consumo_mercado - consumo_ultra, 0)`.
A parcela que NAO depende do raio das concorrentes e':

    disponivel_sem_conc = max(sam - consumo_ultra, 0)

Ela vem de `pressao_1km.disponivel_sem_concorrente`, uma fonte so' para os dois modulos.
NAO reconstruir aqui somando `oferta_efetiva_disponivel + oferta_consumida_mercado_...`:
aquela coluna ja nasce clipada em zero e, em hexagono saturado, a soma infla o residual
justamente onde a disputa e' maior. Hexagono cujo valor nao possa ser reproduzido sai da
leitura (NaN), em vez de entrar com numero errado.

Esse e' o residual que existiria se nao houvesse concorrente. Ele e' partido entre as
duas regioes pela area (`f` = fracao coberta), e o consumo cai PRIMEIRO na coberta; o que
sobrar do consumo transborda para a livre:

    demanda_coberta = disponivel_sem_conc * f
    demanda_livre   = disponivel_sem_conc * (1 - f)
    absorvido       = min(consumo_conc_1km, demanda_coberta)
    excedente       = consumo_conc_1km - absorvido        -> cobrado da parte LIVRE
    score_x         = 100 * disponivel_sem_conc / CAP  *  (demanda_x - gasto_x) / demanda_x

POR QUE O TRANSBORDO EXISTE. Sem ele o modelo misturava duas normalizacoes: o consumo da
concorrente e' rateado pela area do DISCO (2500 * A / 3,14 km2) enquanto a demanda da
fatia sai pela area do HEXAGONO (D * A / 5,20 km2). A razao entre as duas nao depende de
A — ela se cancela — e vale `4136 / D`. Ou seja: em TODO hexagono com demanda abaixo de
4.136 alunos, a concorrente "consumia mais do que existia" na fatia coberta, que zerava
por construcao. Medido em SP: 57% dos hexagonos alcancados. O efeito visivel era um
hexagono perdendo 20% do residual no total, mas com dois cantos pintados de aniquilacao
— e a parte livre artificialmente BOA, porque o excesso ficava preso nos cantos.
Uma concorrente do lado de fora nao puxa aluno so' da faixa exata que o disco toca: ela
puxa do entorno. O transbordo e' isso.

POR QUE MULTIPLICATIVO, E NAO SUBTRATIVO. A regua `100 * residual / 2500` SATURA: medido
em Sao Paulo, 65% dos hexagonos ja batem 100 no mapa padrao. Numa escala saturada,
subtrair o consumo so' podia produzir 0 ou 100 — foi o que apareceu em campo (desvio
45,6 entre hexagonos com UMA concorrente; um virava vermelho, o vizinho amarelo, sem
razao visivel). A retencao e' uma RAZAO: vive em [0,1] e nao satura.

INVARIANTE: (demanda_coberta - absorvido) + (demanda_livre - excedente)
            = disponivel_sem_conc - consumo_conc_1km = `oferta_efetiva_disponivel_1km`.
Os dois pedacos somam exatamente o residual do hexagono no modelo novo.

RESSALVA HONESTA: repartir por AREA assume aluno espalhado por igual dentro do hexagono.
Medido em SP, 28% dos discos cobrem hexagonos com >3x de diferenca de populacao. Isto e'
visualizacao de prototipo, nao base de decisao.

PROJECAO. Discos construidos em graus, com metros-por-grau da latitude de CADA
concorrente (mesma serie WGS84 do motor). Em ~1 km o erro e' invisivel na tela.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import h3
import pandas as pd
import pressao_1km  # regra unica do residual sem concorrente (evita a 2a copia do bug)
import shapely
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from motor_expansao.pipelines.calcular_colunas_mercado import (  # noqa: E402
    SCORE_RESIDUAL_CAPACIDADE_REFERENCIA,
)
from motor_expansao.pipelines.pressao_concorrencial_1km import (  # noqa: E402
    RAIO_INFLUENCIA_M,
    _metros_por_grau,
)

# 24 segmentos por disco (era 48). No zoom em que o operador trabalha o circulo continua
# liso, e a geometria cai pela metade — o custo aqui e' de REDE e de vertices no WebGL,
# nao de CPU. Medido: -1,8 MB no payload da UF de SP.
_SEGMENTOS = 24

# Teto de pecas. Cada hexagono rende no maximo 2 (livre + coberto), entao 6.000 cobre
# ~3.000 hexagonos. O corte e' DECLARADO no payload (`truncado`): corte silencioso num
# mapa mente sobre a extensao da cobertura.
LIMITE_PECAS = 6000

# Teto das sombras (uma por hexagono x concorrente). Num aglomerado isso cresce rapido —
# 49 concorrentes num hexagono geram 49 sombras. O corte entra no mesmo `truncado`.
LIMITE_SOMBRAS = 12000


def _disco(lat: float, lng: float, raio_m: float = RAIO_INFLUENCIA_M) -> Polygon:
    """Circulo de `raio_m` em torno de (lat, lng), em GRAUS."""
    m_lat, m_lng = _metros_por_grau(lat)
    # Buffer unitario escalado por eixo: um circulo em metros e' ELIPSE em graus (1 grau
    # de longitude e' mais curto que 1 de latitude fora do equador).
    base = Point(0.0, 0.0).buffer(1.0, quad_segs=_SEGMENTOS // 4)
    return Polygon(
        [(lng + x * raio_m / m_lng, lat + y * raio_m / m_lat) for x, y in base.exterior.coords]
    )


def _hex_poly(hex_id: str) -> Polygon:
    return Polygon([(p[1], p[0]) for p in h3.cell_to_boundary(hex_id)])


# Grade de arredondamento das coordenadas enviadas ao mapa: 1e-6 grau ~= 0,11 m.
# Suficiente para o desenho e ~40% menor no payload que a precisao cheia.
_GRADE = 1e-6


def _ring(coords: Any) -> list[list[float]]:
    return [[round(x, 6), round(y, 6)] for x, y in coords]


def _aneis(geom: Any) -> list[list[list[list[float]]]]:
    """Poligonos COM buracos: cada item e' [anel_externo, buraco1, buraco2, ...].

    Os buracos importam. Quando o disco de uma concorrente cai INTEIRO dentro do
    hexagono, a peca `livre` (hexagono menos disco) tem um furo no meio. Emitindo so' o
    anel externo, ela tapava o proprio furo — a area somava 108% do hexagono e a cor era
    pintada duas vezes exatamente ali, com o alpha somando. Medido: 22 dos 195 hexes de
    Sao Paulo. E' o formato "complex polygon" do deck.gl.
    """
    if geom is None or geom.is_empty:
        return []

    # SNAP NA GEOMETRIA, nao nas coordenadas soltas. Arredondar vertice a vertice na
    # saida criava AUTO-INTERSECAO onde o arco do disco corre quase tangente a aresta do
    # hexagono: dois vertices trocavam de ordem e o anel cruzava a si mesmo. O deck.gl
    # nao valida — ele triangula (earcut) e o resultado e' um TRIANGULO atravessando o
    # poligono inteiro. Medido em Bauru: 8 de 14 hexagonos afetados.
    # `set_precision` encaixa na grade E devolve geometria valida.
    try:
        geom = shapely.set_precision(geom, _GRADE)
    except Exception:  # pragma: no cover - versao antiga do shapely
        geom = geom.buffer(0)
    if geom.is_empty:
        return []
    if not geom.is_valid:
        geom = geom.buffer(0)
        if geom.is_empty:
            return []

    partes = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
    saida = []
    for parte in partes:
        if parte.is_empty or parte.area <= 0:
            continue
        saida.append([_ring(parte.exterior.coords)] + [_ring(i.coords) for i in parte.interiors])
    return saida


def _score(residual: float) -> float:
    """Mesma regua do motor: 100 * residual / capacidade de referencia, clip 0-100."""
    return max(0.0, min(100.0, 100.0 * residual / SCORE_RESIDUAL_CAPACIDADE_REFERENCIA))


def cobertura(
    df_visiveis: pd.DataFrame,
    caminho_conc: Path,
    *,
    com_sombras: bool = True,
    apenas_dentro: bool = False,
) -> dict[str, Any]:
    """Pecas LIVRE/COBERTO por hexagono, com o score de cada uma.

    So' processa hexes que alguma concorrente de fato alcanca (`conc1k > 0`): recortar os
    15.000 do mapa devolveria vazio na imensa maioria.

    `com_sombras=False` omite a camada de adensamento (uma peca por concorrente). Ela e' a
    parte mais cara do payload e, na visao de UF, ilegivel: o disco de 1 km tem ~5 px
    naquele zoom, entao o escurecimento por acumulo nao se le e custa ~1,8 MB.

    `apenas_dentro=True` restringe as concorrentes as que estao DENTRO da malha analisada
    (usado no drill-down de municipio, a pedido do Felipe). E' escolha de EXIBICAO, nao de
    modelo: uma concorrente do outro lado da divisa continua competindo de fato, e o
    motor (`shares_por_hex`) segue repartindo a capacidade dela normalmente. O que muda e'
    so' o que o mapa desenha quando o operador esta olhando um municipio.
    """
    vazio: dict[str, Any] = {
        "pecas": [],
        "sombras": [],
        "contorno": [],
        "n_discos": 0,
        "truncado": False,
    }
    if not Path(caminho_conc).exists() or df_visiveis.empty:
        return vazio
    if "n_concorrentes_influencia_1km" not in df_visiveis.columns:
        return vazio

    alvo = df_visiveis[
        pd.to_numeric(df_visiveis["n_concorrentes_influencia_1km"], errors="coerce").fillna(0) > 0
    ]
    if alvo.empty:
        return vazio

    lat_min, lat_max = float(df_visiveis["lat"].min()), float(df_visiveis["lat"].max())
    lng_min, lng_max = float(df_visiveis["lng"].min()), float(df_visiveis["lng"].max())

    colunas = ["lat", "lng", "status_registro"]
    if apenas_dentro:
        colunas.append("hex_id_res7")
    conc = pd.read_parquet(caminho_conc, columns=colunas)
    if "status_registro" in conc.columns:
        conc = conc[conc["status_registro"] == "valido"]

    if apenas_dentro:
        # So' as concorrentes cujo hexagono pertence a malha analisada. Sem folga de
        # bbox: e' exatamente "dentro do municipio".
        dentro = set(df_visiveis["hex_id"].astype(str))
        conc = conc[conc["hex_id_res7"].astype(str).isin(dentro)]
    else:
        # Folga de ~1 km em graus: concorrente FORA do bbox ainda cobre hex de dentro.
        # Sem ela apareceria uma faixa artificialmente livre na borda da tela.
        folga = 0.012
        conc = conc[
            conc["lat"].between(lat_min - folga, lat_max + folga)
            & conc["lng"].between(lng_min - folga, lng_max + folga)
        ]
    if conc.empty:
        return vazio

    discos = [
        _disco(float(la), float(ln)) for la, ln in zip(conc["lat"], conc["lng"], strict=True)
    ]
    # Indice espacial: sem ele seriam hexes x discos (961 x 1313 na UF de SP = 1,2 M
    # testes). Com a arvore, cada hexagono consulta so' os discos que tocam sua bbox.
    arvore = STRtree(discos)

    num = lambda s: pd.to_numeric(s, errors="coerce").fillna(0.0)  # noqa: E731
    # Residual sem concorrente pela MESMA regra do `pressao_1km` — nao somar a coluna
    # clipada aqui de novo. Foram duas copias da mesma inversao ingenua que fizeram o
    # bug aparecer nos dois lugares; agora ha uma fonte so'.
    sem_conc_s = pressao_1km.disponivel_sem_concorrente(alvo)
    sem_conc_por_hex = dict(zip(alvo["hex_id"].astype(str), sem_conc_s, strict=True))
    cons1k = dict(zip(alvo["hex_id"].astype(str), num(alvo.get("consumo_concorrentes_1km")), strict=True))

    # Contorno UNICO do alcance: fronteira da uniao de TODOS os discos da janela. E' a
    # linha que o mapa desenha no lugar dos circulos individuais — desenhar um circulo por
    # concorrente fazia as bordas se cruzarem uma sobre a outra e, num aglomerado, o mapa
    # virava um emaranhado de arcos. A uniao nao tem linha interna: so' o limite de ate
    # onde a concorrencia alcanca.
    try:
        contorno = _aneis(unary_union(discos))
    except Exception:  # pragma: no cover
        contorno = []

    # SOMBRAS: uma peca por (hexagono, concorrente), sem contorno. Empilhadas no mapa com
    # alpha baixo, elas escurecem a area proporcionalmente a QUANTAS concorrentes cobrem
    # aquele ponto — a leitura de adensamento que a uniao (peca unica) apaga por
    # construcao. Sao separadas das pecas livre/coberto de proposito: aquelas carregam o
    # SCORE (cor da faixa), estas carregam so' a densidade de disputa (tinta escura).
    sombras: list[list[list[float]]] = []
    pecas: list[dict[str, Any]] = []
    truncado = False
    for hid in sorted(alvo["hex_id"].astype(str).unique()):
        if len(pecas) >= LIMITE_PECAS:
            truncado = True
            break
        hexp = _hex_poly(hid)
        vizinhos = [discos[int(i)] for i in arvore.query(hexp)]
        if not vizinhos:
            continue
        try:
            coberto = hexp.intersection(unary_union(vizinhos))
            livre = hexp.difference(coberto)
        except Exception:  # pragma: no cover - geometria degenerada nao derruba a rota
            continue

        area_hex = hexp.area
        if area_hex <= 0:
            continue
        frac_cob = min(1.0, max(0.0, coberto.area / area_hex))

        # Residual que existiria SEM concorrente. NaN = nao foi possivel reproduzir o
        # consumo Ultra num hexagono saturado; o hexagono sai da leitura em vez de
        # entrar com numero inflado (ver `pressao_1km.disponivel_sem_concorrente`).
        sem_conc = float(sem_conc_por_hex.get(hid, 0.0))
        if sem_conc != sem_conc:  # NaN
            continue

        base = _score(sem_conc)
        f = min(max(frac_cob, 0.0), 1.0)
        demanda_coberta = sem_conc * f
        demanda_livre = sem_conc * (1.0 - f)

        consumo = float(cons1k.get(hid, 0.0))
        # O consumo cai PRIMEIRO na area coberta; o que ela nao comporta transborda para
        # a livre (ver docstring: sem isto 57% das fatias zeravam por construcao).
        absorvido = min(consumo, demanda_coberta)
        excedente = consumo - absorvido

        ret_cob = (demanda_coberta - absorvido) / demanda_coberta if demanda_coberta > 0 else 0.0
        ret_liv = (
            max(0.0, (demanda_livre - excedente) / demanda_livre) if demanda_livre > 0 else 0.0
        )
        s_coberto = base * ret_cob
        s_livre = base * ret_liv

        # Uma sombra por concorrente que toca este hexagono.
        if com_sombras and len(sombras) < LIMITE_SOMBRAS:
            for disco in vizinhos:
                try:
                    parte = hexp.intersection(disco)
                except Exception:  # pragma: no cover
                    continue
                for poli in _aneis(parte):
                    if len(sombras) >= LIMITE_SOMBRAS:
                        break
                    sombras.append(poli)

        for tipo, geom, score in (
            ("livre", livre, s_livre),
            ("coberto", coberto, s_coberto),
        ):
            for poli in _aneis(geom):
                pecas.append({"hex": hid, "tipo": tipo, "score": round(score, 1), "anel": poli})

    return {
        "pecas": pecas,
        "sombras": sombras,
        "contorno": contorno,
        "n_discos": int(len(conc)),
        "truncado": truncado,
    }
