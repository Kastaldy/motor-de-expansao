"""BLK-MA-17 (metade 2): as unidades de REDE do agregador entram na oferta do sinal 6.

É o mesmo defeito que a DEC-033 corrigiu, do outro lado do universo. Lá as INDEPENDENTES não
contavam como concorrência; aqui parte das CADEIAS também não conta — e pela mesma razão, que é
cobertura do insumo e não desenho da fórmula. O snapshot `2026-33` tem **2.844 unidades de rede** em
83 redes que `_filtrar_universo_sinal_1` corta antes do score, e **1.171 delas** sobrevivem à dedup
contra `concorrentes_mapeados.parquet`: academias reais que hoje não pressionam ninguém.

O que estes testes protegem, em ordem de gravidade do modo de falha:

  1. **Auto-pressão de 50 pontos** — a unidade de rede está no próprio conjunto de pontos, e com
     `PESO_OFERTA_CADEIA = 1,0` ela somaria `sat(1,0) = 50,0` de si mesma. É o DOBRO do erro que a
     DEC-033 fechou do lado das independentes, e tem DOIS casos: a sobrevivente da dedup e a
     colapsada (que se auto-pressionaria através do próprio pin do funil).
  2. **Bucket H3 mal dimensionado** — `DEDUP_H3_RES = 11` tem aresta ~29 m, então `grid_disk(k=1)`
     cobre ~50 m e **não** cobre 150 m. É o erro silencioso mais provável do bloco: ele não levanta,
     só deixa de deduplicar. Travado por equivalência contra a varredura completa.
  3. **Critério de dedup** — distância pura apagaria 37 concorrentes REAIS (só têm pin de OUTRA rede
     por perto); sem o piso de 50 m, 8 endereços iguais com slug divergente contariam em dobro.
  4. **Dedup contra os pontos VÁLIDOS** — um `descartado_duplicado` não entra na oferta, então
     deixá-lo absorver uma unidade do feed apagaria concorrência com base em ponto que ninguém conta.
  5. **Default intacto** — sem o insumo, o número é byte a byte o de antes do bloco.
"""

from __future__ import annotations

import h3
import numpy as np
import pandas as pd
import pytest

from motor_expansao.vulnerabilidade import contrato as c
from motor_expansao.vulnerabilidade.pressao_competitiva import (
    _haversine_m,
    _k_do_bucket,
    _pontos_validos_frame,
    calcular_pressao_por_academia,
    calcular_pressao_por_hex,
    dedup_cadeias_do_feed,
    peso_por_distancia,
)

# Observador no centro; os pontos de teste orbitam em torno dele.
_LAT, _LNG = -23.5500, -46.6300
_GRAU_LAT_M = 111_320.0


def _norte(metros: float) -> float:
    """Latitude a `metros` ao norte de `_LAT` — a conversão exata o bastante para o kernel."""
    return _LAT + metros / _GRAU_LAT_M


def _observador(chave: str = "obs", *, metros: float = 0.0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "fonte": ["wellhub"],
            "chave_snapshot": [chave],
            "lat": [_norte(metros)],
            "lng": [_LNG],
        }
    )


def _mapeados(pontos: list[tuple[str, float]], *, status: str = "valido") -> pd.DataFrame:
    """Pontos de `concorrentes_mapeados`: `(rede, metros ao norte do observador)`."""
    return pd.DataFrame(
        {
            "rede": [rede for rede, _ in pontos],
            "lat": [_norte(m) for _, m in pontos],
            "lng": [_LNG] * len(pontos),
            "status_registro": [status] * len(pontos),
        }
    )


def _feed(pontos: list[tuple[str, str, float]]) -> pd.DataFrame:
    """Unidades de rede do agregador: `(chave, rede, metros ao norte do observador)`."""
    return pd.DataFrame(
        {
            "fonte": ["wellhub"] * len(pontos),
            "chave_snapshot": [chave for chave, _, _ in pontos],
            "lat": [_norte(m) for _, _, m in pontos],
            "lng": [_LNG] * len(pontos),
            "rede": [rede for _, rede, _ in pontos],
        }
    )


def _sem_cadeias() -> pd.DataFrame:
    return pd.DataFrame({"rede": [], "lat": [], "lng": [], "status_registro": []})


# --------------------------------------------------------------------------- #
# 1-4. O critério de dedup, nos quatro sentidos que a medição de 2026-08-15 expôs
# --------------------------------------------------------------------------- #
def test_1_unidade_de_rede_longe_de_qualquer_pin_ENTRA_na_oferta() -> None:
    """As 1.171 do bloco: academia de rede real que hoje não pressiona ninguém."""
    mapeados = _mapeados([("smart_fit", 1500.0)])
    nova = _feed([("r1", "bluefit", 800.0)])
    sem = calcular_pressao_por_academia(_observador(), mapeados)
    com = calcular_pressao_por_academia(_observador(), mapeados, cadeias_do_feed=nova)
    # A distância é a GEODÉSICA real (o `_GRAU_LAT_M` do helper é aproximação de posicionamento,
    # não de medição), e o peso é o do kernel do contrato vezes `PESO_OFERTA_CADEIA = 1,0`.
    dist = _haversine_m(
        np.array([_LAT]),
        np.array([_LNG]),
        nova["lat"].to_numpy(float),
        nova["lng"].to_numpy(float),
    )
    esperado = float(peso_por_distancia(dist, raio_m=c.PRESSAO_RAIO_M)[0] * c.PESO_OFERTA_CADEIA)
    delta = float(com["oferta_ponderada"].iloc[0]) - float(sem["oferta_ponderada"].iloc[0])
    assert delta == pytest.approx(esperado)
    assert float(com["oferta_cadeias_do_feed"].iloc[0]) == pytest.approx(esperado)
    assert int(com["n_cadeias_do_feed_no_raio"].iloc[0]) == 1


def test_2_unidade_a_menos_de_150m_de_pin_da_MESMA_rede_NAO_dobra_a_oferta() -> None:
    """O outro lado do custo: 1.673 das 2.844 já estão desenhadas pelo feed do site da rede."""
    mapeados = _mapeados([("bluefit", 800.0)])
    sem = calcular_pressao_por_academia(_observador(), mapeados)
    com = calcular_pressao_por_academia(
        _observador(),
        mapeados,
        # 100 m acima do pin: dentro dos 150 m, mesma rede.
        cadeias_do_feed=_feed([("r1", "bluefit", 900.0)]),
    )
    assert float(com["oferta_ponderada"].iloc[0]) == pytest.approx(
        float(sem["oferta_ponderada"].iloc[0])
    )
    assert int(com["n_cadeias_do_feed_no_raio"].iloc[0]) == 0
    assert float(com["oferta_cadeias_do_feed"].iloc[0]) == 0.0


def test_3_unidade_a_menos_de_150m_de_pin_de_OUTRA_rede_CONTINUA_contando() -> None:
    """Os 37 casos que a dedup por distância pura apagaria — concorrente REAL virando zero.

    É a direção exata do falso zero que a DEC-033 existe para matar, e por isso o casamento exige
    `rede` igual em vez de só distância.
    """
    mapeados = _mapeados([("smart_fit", 800.0)])
    com = calcular_pressao_por_academia(
        _observador(), mapeados, cadeias_do_feed=_feed([("r1", "bluefit", 900.0)])
    )
    assert int(com["n_cadeias_do_feed_no_raio"].iloc[0]) == 1
    assert float(com["oferta_cadeias_do_feed"].iloc[0]) > 0.0


def test_4_piso_de_50m_colapsa_mesmo_com_rede_diferente() -> None:
    """Os 8 casos de slug divergente, o menor deles a `0,0 m` — o mesmo estabelecimento.

    A menos de 50 m com nome de rede diferente é, quase sempre, o MESMO estabelecimento visto por
    duas geocodificações — não dois prédios.
    """
    mapeados = _mapeados([("smart_fit", 800.0)])
    com = calcular_pressao_por_academia(
        _observador(), mapeados, cadeias_do_feed=_feed([("r1", "bluefit", 830.0)])
    )
    assert int(com["n_cadeias_do_feed_no_raio"].iloc[0]) == 0, (
        "30 m e' menos que o piso de 50 m: e' o mesmo endereco com slug divergente"
    )


# --------------------------------------------------------------------------- #
# 5-6. Auto-pressão: o modo de falha mais caro, e ele tem DOIS casos
# --------------------------------------------------------------------------- #
def test_5_unidade_de_rede_SOBREVIVENTE_nao_pressiona_a_si_mesma() -> None:
    """`peso(d = 0) x 1,0` daria `sat(1,0) = 50,0` pontos de pressão fantasma.

    E o erro seria MAIOR exatamente onde o sinal mais importa: a unidade isolada, que deveria marcar
    zero, apareceria com meia escala de pressão.
    """
    unidade = pd.DataFrame(
        {
            "fonte": ["wellhub"],
            "chave_snapshot": ["r1"],
            "lat": [_LAT],
            "lng": [_LNG],
            "rede": ["bluefit"],
        }
    )
    out = calcular_pressao_por_academia(
        _observador("r1"), _sem_cadeias(), cadeias_do_feed=unidade
    )
    assert float(out["pressao_competitiva"].iloc[0]) == 0.0
    assert float(out["oferta_cadeias_do_feed"].iloc[0]) == 0.0
    assert int(out["n_cadeias_do_feed_no_raio"].iloc[0]) == 0
    assert pd.isna(out["dist_concorrente_mais_proximo_m"].iloc[0])


def test_6_unidade_de_rede_COLAPSADA_tambem_nao_se_auto_pressiona() -> None:
    """O caso que uma exclusão ingênua erraria — e que o Block Orchestrator não viu.

    Se a própria unidade colapsou contra um pin do funil, quem a representa na oferta é aquele pin,
    a poucos metros dali. Zerar "a posição dela" não bastaria: ela não tem posição própria, e se
    auto-pressionaria através do próprio pin — `peso(~0) x 1,0`, os mesmos 50 pontos.
    """
    unidade = pd.DataFrame(
        {
            "fonte": ["wellhub"],
            "chave_snapshot": ["r1"],
            "lat": [_norte(20.0)],
            "lng": [_LNG],
            "rede": ["bluefit"],
        }
    )
    out = calcular_pressao_por_academia(
        _observador("r1"), _mapeados([("bluefit", 0.0)]), cadeias_do_feed=unidade
    )
    assert float(out["oferta_ponderada"].iloc[0]) == 0.0, (
        "a unidade absorvida se auto-pressionou atraves do proprio pin do funil"
    )
    assert float(out["pressao_competitiva"].iloc[0]) == 0.0
    assert int(out["n_concorrentes_no_raio"].iloc[0]) == 0


# --------------------------------------------------------------------------- #
# 7. A dedup casa contra os pontos VÁLIDOS, nunca contra o parquet cru
# --------------------------------------------------------------------------- #
def test_7_ponto_descartado_nao_absorve_unidade_do_feed() -> None:
    """Um `descartado_duplicado` não entra na oferta; deixá-lo colapsar apagaria oferta real."""
    descartado = _mapeados([("bluefit", 810.0)], status="descartado_duplicado")
    com = calcular_pressao_por_academia(
        _observador(), descartado, cadeias_do_feed=_feed([("r1", "bluefit", 800.0)])
    )
    assert int(com["n_cadeias_do_feed_no_raio"].iloc[0]) == 1, (
        "a unidade colapsou contra um ponto que nem esta sendo contado na oferta"
    )
    # E o frame que a dedup enxerga é o filtrado, não o cru.
    assert len(_pontos_validos_frame(descartado)) == 0


# --------------------------------------------------------------------------- #
# 8-9. Decomposição e carimbo
# --------------------------------------------------------------------------- #
def test_8_decomposicao_soma_no_total() -> None:
    """As duas partes são recortes DISJUNTOS do total — nenhuma é subconjunto da outra."""
    independentes = pd.DataFrame(
        {
            "fonte": ["wellhub"],
            "chave_snapshot": ["i1"],
            "lat": [_norte(400.0)],
            "lng": [_LNG],
        }
    )
    out = calcular_pressao_por_academia(
        _observador(),
        _mapeados([("smart_fit", 1500.0)]),
        independentes=independentes,
        cadeias_do_feed=_feed([("r1", "bluefit", 900.0)]),
    )
    linha = out.iloc[0]
    soma = float(linha["oferta_independentes"]) + float(linha["oferta_cadeias_do_feed"])
    assert soma <= float(linha["oferta_ponderada"]) + 1e-9
    assert float(linha["oferta_independentes"]) > 0.0
    assert float(linha["oferta_cadeias_do_feed"]) > 0.0
    assert int(linha["n_independentes_no_raio"]) + int(linha["n_cadeias_do_feed_no_raio"]) <= int(
        linha["n_concorrentes_no_raio"]
    )


def test_9_no_universo_cadeias_as_duas_partes_e_as_duas_contagens_sao_zero() -> None:
    """Resíduo ali significaria que o carimbo está mentindo sobre quem contou."""
    out = calcular_pressao_por_academia(_observador(), _mapeados([("smart_fit", 800.0)]))
    assert (out["universo_oferta"] == c.UNIVERSO_OFERTA_CADEIAS).all()
    for coluna in ("oferta_independentes", "oferta_cadeias_do_feed"):
        assert (out[coluna] == 0.0).all()
    for coluna in ("n_independentes_no_raio", "n_cadeias_do_feed_no_raio"):
        assert (out[coluna] == 0).all()


# --------------------------------------------------------------------------- #
# 10-11. O default e a régua histórica
# --------------------------------------------------------------------------- #
def test_10_sem_nenhum_dos_dois_frames_o_numero_e_identico_ao_de_antes_do_bloco() -> None:
    """A garantia que torna o bloco seguro: o universo novo é CONDICIONAL ao insumo (DEC-036)."""
    mapeados = _mapeados([("smart_fit", 700.0), ("bluefit", 1500.0)])
    obs = _observador()
    out = calcular_pressao_por_academia(obs, mapeados)

    d = _haversine_m(
        np.full(2, _LAT),
        np.full(2, _LNG),
        mapeados["lat"].to_numpy(float),
        mapeados["lng"].to_numpy(float),
    )
    oferta = float(peso_por_distancia(d, raio_m=c.PRESSAO_RAIO_M).sum())
    assert float(out["pressao_competitiva"].iloc[0]) == pytest.approx(
        100.0 * (1.0 - 1.0 / (1.0 + oferta))
    )


def test_11_o_default_do_pipeline_liga_as_cadeias_do_feed_e_a_flag_reproduz_o_historico() -> None:
    """O ponto de decisão é o wrapper da CLI, e a régua antiga não pode sumir.

    Ela é a única comparável com `pressao_concorrencial_score_2km` da camada de mercado, que conta
    só cadeia MAPEADA — e some se ninguém a preservar.
    """
    import inspect

    from motor_expansao.vulnerabilidade.alvos_ma import _parse_args, _pressao_por_academia

    parametros = inspect.signature(_pressao_por_academia).parameters
    assert parametros["com_oferta_do_feed"].default is True
    assert "com_independentes" not in parametros, (
        "o nome antigo mentia: a mesma chave passou a ligar TAMBEM as unidades de rede do feed"
    )
    # Uma flag só desliga as duas metades juntas — sem knob novo (a matriz de teste dobraria).
    assert _parse_args(["--base-dir", "x"]).oferta_so_cadeias is False
    assert _parse_args(["--base-dir", "x", "--oferta-so-cadeias"]).oferta_so_cadeias is True


# --------------------------------------------------------------------------- #
# 12. O grão hex
# --------------------------------------------------------------------------- #
def test_12_grao_hex_aceita_o_mesmo_universo_e_NAO_tem_auto_exclusao() -> None:
    """A origem do grão hex é o centroide do território: não há "si mesma" para excluir."""
    hex_id = h3.latlng_to_cell(_LAT, _LNG, c.H3_RES_CONTRATO)
    lat, lng = h3.cell_to_latlng(hex_id)
    dentro = pd.DataFrame(
        {
            "fonte": ["wellhub"],
            "chave_snapshot": ["r1"],
            "lat": [lat],
            "lng": [lng],
            "rede": ["bluefit"],
        }
    )
    out = calcular_pressao_por_hex([hex_id], _sem_cadeias(), cadeias_do_feed=dentro)
    assert float(out["oferta_cadeias_do_feed_no_hex"].iloc[0]) > 0.0
    assert int(out["n_cadeias_do_feed_no_raio"].iloc[0]) == 1
    assert out["universo_oferta"].iloc[0] == c.UNIVERSO_OFERTA_COM_INDEPENDENTES


# --------------------------------------------------------------------------- #
# 13-14. Limiares do contrato, determinismo e o bucket H3
# --------------------------------------------------------------------------- #
def test_13_os_limiares_vem_do_contrato_e_nao_do_corpo_da_funcao() -> None:
    """Nenhum literal de metro dentro da função — trocar o critério é mexer no contrato."""
    import inspect

    from motor_expansao.vulnerabilidade import pressao_competitiva as m

    assert c.DEDUP_CADEIA_FEED_M == 150.0
    assert c.DEDUP_CADEIA_FEED_PISO_M == 50.0
    parametros = inspect.signature(m.dedup_cadeias_do_feed).parameters
    assert parametros["distancia_m"].default == c.DEDUP_CADEIA_FEED_M
    assert parametros["piso_m"].default == c.DEDUP_CADEIA_FEED_PISO_M
    # E o limiar da dedup de independentes NÃO foi reusado: ele foi arbitrado para TP x WH.
    assert c.DEDUP_CADEIA_FEED_M != c.DEDUP_INDEPENDENTES_M


def test_14_a_dedup_e_deterministica_na_ordem_de_entrada() -> None:
    """Mesma entrada embaralhada -> mesmo sobrevivente. Sem isso o artefato varia por máquina."""
    feed = _feed([("z", "bluefit", 900.0), ("a", "bluefit", 905.0), ("m", "one", 2000.0)])
    mapeados = _mapeados([("bluefit", 902.0)])
    direto, mapa_direto = dedup_cadeias_do_feed(feed, _pontos_validos_frame(mapeados))
    invertido, mapa_invertido = dedup_cadeias_do_feed(
        feed.iloc[::-1].reset_index(drop=True), _pontos_validos_frame(mapeados)
    )
    assert direto["chave_snapshot"].tolist() == invertido["chave_snapshot"].tolist()
    assert mapa_direto == mapa_invertido


def test_14b_o_bucket_h3_cobre_o_limiar_e_e_equivalente_a_varredura_completa() -> None:
    """O erro silencioso mais provável do bloco: a dedup deixar de deduplicar sem levantar nada.

    `DEDUP_H3_RES = 11` tem aresta ~29 m, então `grid_disk(k=1)` cobre ~50 m e **não** cobre 150 m.
    Um `k` cravado faria a busca não achar o vizinho, e o resultado seria "nenhum colapso" — que é
    exatamente o que uma dedup correta devolve quando não há duplicata. Indistinguível sem este
    teste.
    """
    assert _k_do_bucket(c.DEDUP_CADEIA_FEED_M) > 1, (
        "k=1 nao cobre 150 m na resolucao 11 — o `k` tem de sair do limiar"
    )

    rng = np.random.default_rng(20260815)
    n_map, n_feed = 60, 40
    redes = ["bluefit", "smart_fit", "one"]
    mapeados = pd.DataFrame(
        {
            "rede": rng.choice(redes, n_map),
            # Espalhados em ~600 m, para produzir pares dentro e fora dos dois limiares.
            "lat": _LAT + rng.uniform(-0.003, 0.003, n_map),
            "lng": _LNG + rng.uniform(-0.003, 0.003, n_map),
            "status_registro": ["valido"] * n_map,
        }
    )
    feed = pd.DataFrame(
        {
            "fonte": ["wellhub"] * n_feed,
            "chave_snapshot": [f"k{i}" for i in range(n_feed)],
            "lat": _LAT + rng.uniform(-0.003, 0.003, n_feed),
            "lng": _LNG + rng.uniform(-0.003, 0.003, n_feed),
            "rede": rng.choice(redes, n_feed),
        }
    )
    pontos = _pontos_validos_frame(mapeados)
    sobreviventes, mapa = dedup_cadeias_do_feed(feed, pontos)

    # VARREDURA COMPLETA, sem bucket nenhum: a referência contra a qual a otimização se prova.
    lat_m = pontos["lat"].to_numpy(float)
    lng_m = pontos["lng"].to_numpy(float)
    rede_m = pontos["rede"].astype(str).to_numpy()
    ordenado = feed.sort_values(["fonte", "chave_snapshot"], kind="stable").reset_index(drop=True)
    esperado_colapsos: dict[str, int] = {}
    for i in range(len(ordenado)):
        d = _haversine_m(
            np.full(len(lat_m), float(ordenado.loc[i, "lat"])),
            np.full(len(lng_m), float(ordenado.loc[i, "lng"])),
            lat_m,
            lng_m,
        )
        qualifica = ((rede_m == str(ordenado.loc[i, "rede"])) & (d <= c.DEDUP_CADEIA_FEED_M)) | (
            d <= c.DEDUP_CADEIA_FEED_PISO_M
        )
        if qualifica.any():
            candidatos = np.flatnonzero(qualifica)
            esperado_colapsos[str(ordenado.loc[i, "chave_snapshot"])] = int(
                candidatos[np.argmin(d[candidatos])]
            )

    assert esperado_colapsos, "a fixture nao produziu colapso nenhum: o teste nao provaria nada"
    offset = len(pontos)
    obtidos = {
        chave: pos for (_fonte, chave), pos in mapa.items() if pos < offset
    }
    assert obtidos == esperado_colapsos
    assert len(sobreviventes) == len(feed) - len(esperado_colapsos)


# --------------------------------------------------------------------------- #
# 15. Contratos e carimbos
# --------------------------------------------------------------------------- #
def test_15_contratos_e_as_quatro_versoes_bumpadas() -> None:
    """Os QUATRO carimbos, não dois: `VERSAO_CONTRATO_PRESSAO` não chega a disco.

    Quem carimba os artefatos que MUDAM DE VALOR é `score_vulnerabilidade`, `alvos_ma` e
    `alvos_ma_nomeados`. Bumpar só a pressão deixaria `alvos_ma_priorizados.csv` e
    `vulnerabilidade_ma_nomeadas.parquet` com o mesmo carimbo e números diferentes — o defeito exato
    que o carimbo existe para impedir.
    """
    assert len(c.CONTRATO_COLUNAS_PRESSAO_ACADEMIA) == 15
    assert len(c.CONTRATO_COLUNAS_PRESSAO) == 14
    assert len(c.CONTRATO_COLUNAS_ALVOS_NOMEADOS) == 24
    # Estes NÃO mudam de schema: o molde do BLK-MA-18 manda a auditoria para o nomeado.
    assert len(c.CONTRATO_COLUNAS_SCORE) == 26
    assert len(c.CONTRATO_COLUNAS_ALVOS_MA) == 18
    assert len(c.CONTRATO_COLUNAS_ACADEMIAS_MA) == 26

    assert c.VERSAO_CONTRATO_PRESSAO == "pressao_competitiva_v4"
    assert c.VERSAO_CONTRATO_SCORE == "score_vulnerabilidade_v7"
    assert c.VERSAO_CONTRATO_ALVOS_MA == "alvos_ma_v4"
    assert c.VERSAO_CONTRATO_ALVOS_NOMEADOS == "alvos_ma_nomeados_v5"

    # Sem terceiro valor de enum: o rótulo classifica CATEGORIA, e a categoria não mudou.
    assert c.UNIVERSOS_OFERTA == (
        c.UNIVERSO_OFERTA_CADEIAS,
        c.UNIVERSO_OFERTA_COM_INDEPENDENTES,
    )


def test_15b_a_posicao_das_colunas_novas_mantem_os_carimbos_no_fim() -> None:
    """Os carimbos (`kernel`, `raio`, `universo`, `versao`) fecham os dois contratos de pressão."""
    academia = list(c.CONTRATO_COLUNAS_PRESSAO_ACADEMIA)
    assert academia[academia.index("n_independentes_no_raio") + 1] == "oferta_cadeias_do_feed"
    assert academia[-4:] == [
        "kernel_pressao",
        "raio_pressao_m",
        "universo_oferta",
        "versao_contrato",
    ]
    hexes = list(c.CONTRATO_COLUNAS_PRESSAO)
    assert hexes[hexes.index("n_independentes_no_raio") + 1] == "oferta_cadeias_do_feed_no_hex"
    assert hexes[-4:] == [
        "kernel_pressao",
        "raio_pressao_m",
        "universo_oferta",
        "versao_contrato",
    ]


# --------------------------------------------------------------------------- #
# Guardrails que este bloco NÃO pode ter afrouxado
# --------------------------------------------------------------------------- #
def test_o_universo_do_SCORE_continua_intocado() -> None:
    """A metade 2 é sobre OFERTA, não sobre quem é avaliado. Nenhuma unidade de rede no score.

    `_filtrar_universo_sinal_1` é o filtro compartilhado com o sinal 1: afrouxá-lo faria
    `n_academias_independentes_totalpass`/`_wellhub` contarem redes com o nome dizendo o contrário.
    """
    from motor_expansao.vulnerabilidade.presenca_agregador import _filtrar_universo_sinal_1

    frame = pd.DataFrame(
        {
            "fonte": ["wellhub", "wellhub", "unidades"],
            "rede": [c.CATEGORIA_INDEPENDENTE, "bluefit", "smart_fit"],
            "chave_snapshot": ["i1", "r1", "u1"],
            "hex_id_res7": ["87a8100acffffff"] * 3,
        }
    )
    filtrado = _filtrar_universo_sinal_1(frame)
    assert filtrado["rede"].astype(str).unique().tolist() == [c.CATEGORIA_INDEPENDENTE]
    assert len(filtrado) == 1


def test_a_saida_da_pressao_continua_sem_coordenada() -> None:
    """A terceira lista de pontos traz coordenada de rede para dentro — e ela não pode sair."""
    out = calcular_pressao_por_academia(
        _observador(),
        _mapeados([("smart_fit", 800.0)]),
        cadeias_do_feed=_feed([("r1", "bluefit", 900.0)]),
    )
    for proibida in ("lat", "lng", "latitude", "longitude", "nome", "rede", "concorrente_id"):
        assert proibida not in out.columns


def test_frame_de_cadeias_do_feed_sem_coluna_obrigatoria_levanta() -> None:
    """`rede` é obrigatória: sem ela o casamento por rede não existe e a dedup viraria outra regra."""
    with pytest.raises(ValueError, match="obrigatoria"):
        dedup_cadeias_do_feed(
            _feed([("r1", "bluefit", 900.0)]).drop(columns=["rede"]),
            _pontos_validos_frame(_mapeados([("bluefit", 900.0)])),
        )


def test_feed_vazio_nao_quebra_e_nao_muda_nada() -> None:
    """Caso degenerado: nenhuma unidade de rede no feed (recorte de UF sem cadeia no agregador)."""
    vazio = _feed([]).astype(
        {"fonte": "object", "chave_snapshot": "object", "rede": "object"}
    )
    mapeados = _mapeados([("smart_fit", 800.0)])
    com = calcular_pressao_por_academia(_observador(), mapeados, cadeias_do_feed=vazio)
    sem = calcular_pressao_por_academia(_observador(), mapeados)
    assert float(com["oferta_ponderada"].iloc[0]) == pytest.approx(
        float(sem["oferta_ponderada"].iloc[0])
    )
    # O carimbo, porém, muda: o chamador DECLAROU o universo ampliado ao passar o frame.
    assert com["universo_oferta"].iloc[0] == c.UNIVERSO_OFERTA_COM_INDEPENDENTES
