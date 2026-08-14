"""BLK-MA-16: as independentes entram na oferta do S6 com metade do peso de uma unidade de rede.

O bloco corrige um defeito de INSUMO, não de fórmula: `concorrentes_mapeados.parquet` tem 4.499
pontos em 104 redes e **zero independentes** (ele nasce dos coletores `unidades_*.csv`, que são
feeds de cadeia), então a pressão de hoje responde "quanta CADEIA cerca este ponto". Medido em SP:
**29,2%** das independentes marcam `0`, e aquele zero é o insumo respondendo a pergunta errada.

O que estes testes protegem, em ordem de gravidade do modo de falha:

  1. **Auto-pressão** — a academia está no próprio conjunto de pontos. Sem excluí-la, cada uma
     recebe `sat(0,5) = 33,3` pontos de si mesma, e o erro é MAIOR justamente em quem não tem
     ninguém por perto: a isolada deixa de ser distinguível.
  2. **Dedup entre fontes** — a mesma academia em TP e WH são duas chaves (§8.1). Somar as duas
     dobra a oferta de toda academia listada nos dois apps. Hoje é latente (só há WellHub) e entra
     em massa junto com a primeira coleta que trouxer as duas fontes.
  3. **Carimbo** — a mesma academia mede 39 num universo e 65 no outro. Sem `universo_oferta`, as
     duas respostas parecem a mesma grandeza.
  4. **Default intacto** — sem o insumo, o número é byte a byte o de antes do bloco.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from motor_expansao.vulnerabilidade import contrato as c
from motor_expansao.vulnerabilidade.pressao_competitiva import (
    calcular_pressao_por_academia,
    calcular_pressao_por_hex,
    dedup_independentes,
)

# Duas academias a ~15 m uma da outra, e uma terceira longe (fora do raio das outras duas).
_LAT_A, _LNG_A = -23.5500, -46.6300
_LAT_B, _LNG_B = -23.5501, -46.6301
_LAT_LONGE, _LNG_LONGE = -23.6500, -46.7500


def _academias() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "fonte": ["wellhub"] * 3,
            "chave_snapshot": ["a", "b", "longe"],
            "lat": [_LAT_A, _LAT_B, _LAT_LONGE],
            "lng": [_LNG_A, _LNG_B, _LNG_LONGE],
        }
    )


def _cadeia_perto_de_a() -> pd.DataFrame:
    return pd.DataFrame(
        {"lat": [-23.5505], "lng": [-46.6305], "status_registro": ["valido"]}
    )


def _sem_cadeias() -> pd.DataFrame:
    return pd.DataFrame({"lat": [], "lng": [], "status_registro": []})


# --------------------------------------------------------------------------- #
# 1. Auto-pressão
# --------------------------------------------------------------------------- #
def test_academia_nao_pressiona_a_si_mesma() -> None:
    """O modo de falha mais perigoso do bloco, porque ele é MAIOR onde o sinal mais importa.

    `peso(d = 0) = 1,0` no kernel linear, então sem exclusão cada academia somaria `0,5` de oferta
    de si mesma — `sat(0,5) = 33,3` pontos. A academia ISOLADA, que deveria marcar zero, passaria a
    marcar 33,3 e ficaria indistinguível de uma com concorrência real por perto.
    """
    out = calcular_pressao_por_academia(
        _academias(), _sem_cadeias(), independentes=_academias()
    )
    longe = out[out["chave_snapshot"] == "longe"].iloc[0]
    assert float(longe["pressao_competitiva"]) == 0.0
    assert float(longe["oferta_independentes"]) == 0.0
    assert int(longe["n_independentes_no_raio"]) == 0


def test_auto_exclusao_sobrevive_ao_colapso_da_dedup() -> None:
    """O caso que uma exclusão ingênua por índice erraria.

    Se a PRÓPRIA academia foi a linha ABSORVIDA no colapso, quem a representa na oferta é a
    sobrevivente do grupo — a poucos metros dali. Excluir "a posição dela" não bastaria: a posição
    dela não existe mais, e ela se auto-pressionaria através da gêmea.
    """
    # `totalpass/x` e `wellhub/y` são a MESMA academia (a ~4 m). A ordem de dedup mantém a de
    # `fonte` menor (`totalpass`), então `wellhub/y` é a absorvida.
    duas_fontes = pd.DataFrame(
        {
            "fonte": ["totalpass", "wellhub"],
            "chave_snapshot": ["x", "y"],
            "lat": [_LAT_A, _LAT_A + 0.00003],
            "lng": [_LNG_A, _LNG_A + 0.00003],
        }
    )
    out = calcular_pressao_por_academia(
        duas_fontes, _sem_cadeias(), independentes=duas_fontes
    )
    assert (out["oferta_independentes"] == 0.0).all(), (
        "a academia absorvida se auto-pressionou atraves da propria gemea"
    )
    assert (out["pressao_competitiva"] == 0.0).all()


# --------------------------------------------------------------------------- #
# 2. Dedup entre fontes
# --------------------------------------------------------------------------- #
def test_mesma_academia_em_duas_fontes_conta_uma_vez() -> None:
    """O defeito LATENTE: hoje só há WellHub, e ele entra em massa na primeira coleta com as duas."""
    duas_fontes = pd.DataFrame(
        {
            "fonte": ["totalpass", "wellhub"],
            "chave_snapshot": ["x", "y"],
            "lat": [_LAT_A, _LAT_A],
            "lng": [_LNG_A, _LNG_A],
        }
    )
    alvo = pd.DataFrame(
        {"fonte": ["wellhub"], "chave_snapshot": ["obs"], "lat": [_LAT_B], "lng": [_LNG_B]}
    )
    com_dup = calcular_pressao_por_academia(alvo, _sem_cadeias(), independentes=duas_fontes)
    so_uma = calcular_pressao_por_academia(
        alvo, _sem_cadeias(), independentes=duas_fontes.iloc[[0]]
    )
    assert float(com_dup["oferta_independentes"].iloc[0]) == pytest.approx(
        float(so_uma["oferta_independentes"].iloc[0])
    )
    assert int(com_dup["n_independentes_no_raio"].iloc[0]) == 1


def test_duas_academias_da_MESMA_fonte_nao_colapsam() -> None:
    """A dedup é entre fontes, e essa restrição é o que a impede de apagar concorrência real.

    Duas linhas da mesma fonte a 15 m são duas academias — a chave já é única por fonte. Colapsá-las
    subtrairia oferta que existe.
    """
    mesma_fonte = pd.DataFrame(
        {
            "fonte": ["wellhub", "wellhub"],
            "chave_snapshot": ["a", "b"],
            "lat": [_LAT_A, _LAT_B],
            "lng": [_LNG_A, _LNG_B],
        }
    )
    pontos, mapa = dedup_independentes(mesma_fonte)
    assert len(pontos) == 2
    assert len(set(mapa.values())) == 2


def test_dedup_e_deterministica_na_ordem_de_entrada() -> None:
    """Mesma entrada embaralhada -> mesmo sobrevivente. Sem isso o artefato varia por máquina."""
    duas = pd.DataFrame(
        {
            "fonte": ["wellhub", "totalpass"],
            "chave_snapshot": ["z", "a"],
            "lat": [_LAT_A, _LAT_A],
            "lng": [_LNG_A, _LNG_A],
        }
    )
    direto, _ = dedup_independentes(duas)
    invertido, _ = dedup_independentes(duas.iloc[::-1].reset_index(drop=True))
    assert direto["fonte"].tolist() == invertido["fonte"].tolist()
    assert direto["chave_snapshot"].tolist() == invertido["chave_snapshot"].tolist()
    # O sobrevivente é o primeiro em ordem `(fonte, chave_snapshot)`.
    assert direto["fonte"].iloc[0] == "totalpass"


def test_dedup_respeita_a_distancia_do_contrato() -> None:
    """Ponto além de `DEDUP_INDEPENDENTES_M` é outra academia, mesmo vindo de outra fonte."""
    # ~111 m em latitude: acima dos 50 m do contrato.
    longe_o_bastante = pd.DataFrame(
        {
            "fonte": ["totalpass", "wellhub"],
            "chave_snapshot": ["x", "y"],
            "lat": [_LAT_A, _LAT_A + 0.001],
            "lng": [_LNG_A, _LNG_A],
        }
    )
    pontos, _ = dedup_independentes(longe_o_bastante)
    assert len(pontos) == 2


# --------------------------------------------------------------------------- #
# 3. Carimbo e decomposição
# --------------------------------------------------------------------------- #
def test_carimbo_declara_quem_contou() -> None:
    sem = calcular_pressao_por_academia(_academias(), _cadeia_perto_de_a())
    com = calcular_pressao_por_academia(
        _academias(), _cadeia_perto_de_a(), independentes=_academias()
    )
    assert (sem["universo_oferta"] == c.UNIVERSO_OFERTA_CADEIAS).all()
    assert (com["universo_oferta"] == c.UNIVERSO_OFERTA_COM_INDEPENDENTES).all()


def test_no_universo_cadeias_a_parte_de_independentes_e_zero() -> None:
    """Resíduo ali significaria que independentes entraram numa rodada que se declara sem elas."""
    sem = calcular_pressao_por_academia(_academias(), _cadeia_perto_de_a())
    assert (sem["oferta_independentes"] == 0.0).all()
    assert (sem["n_independentes_no_raio"] == 0).all()


def test_decomposicao_soma_no_total() -> None:
    """A parte não pode exceder o todo — e a diferença é a oferta vinda de cadeia."""
    com = calcular_pressao_por_academia(
        _academias(), _cadeia_perto_de_a(), independentes=_academias()
    )
    assert (com["oferta_independentes"] <= com["oferta_ponderada"] + 1e-9).all()
    assert (com["n_independentes_no_raio"] <= com["n_concorrentes_no_raio"]).all()
    perto = com[com["chave_snapshot"] == "a"].iloc[0]
    assert float(perto["oferta_independentes"]) > 0.0
    assert float(perto["oferta_ponderada"]) > float(perto["oferta_independentes"])


# --------------------------------------------------------------------------- #
# 4. O peso, e o que ele NÃO controla
# --------------------------------------------------------------------------- #
def test_independente_pesa_METADE_de_uma_unidade_de_rede() -> None:
    """A decisão de produto, medida contra a mesma geometria: a razão é exatamente 0,5."""
    alvo = pd.DataFrame(
        {"fonte": ["wellhub"], "chave_snapshot": ["obs"], "lat": [_LAT_A], "lng": [_LNG_A]}
    )
    vizinha = pd.DataFrame(
        {"fonte": ["wellhub"], "chave_snapshot": ["viz"], "lat": [_LAT_B], "lng": [_LNG_B]}
    )
    como_cadeia = calcular_pressao_por_academia(
        alvo,
        pd.DataFrame({"lat": [_LAT_B], "lng": [_LNG_B], "status_registro": ["valido"]}),
    )
    como_independente = calcular_pressao_por_academia(
        alvo, _sem_cadeias(), independentes=vizinha
    )
    razao = float(como_independente["oferta_ponderada"].iloc[0]) / float(
        como_cadeia["oferta_ponderada"].iloc[0]
    )
    assert razao == pytest.approx(c.PESO_OFERTA_INDEPENDENTE)


def test_peso_acima_do_de_uma_rede_e_recusado() -> None:
    """Uma independente pressionando MAIS que uma unidade de rede inverteria a premissa do bloco."""
    with pytest.raises(ValueError, match="peso_independente"):
        calcular_pressao_por_academia(
            _academias(), _sem_cadeias(), independentes=_academias(), peso_independente=1.5
        )


# --------------------------------------------------------------------------- #
# 5. O default não se mexe
# --------------------------------------------------------------------------- #
def test_sem_o_insumo_o_numero_e_identico_ao_de_antes_do_bloco() -> None:
    """A garantia que torna o bloco seguro de mergear antes do gate.

    O universo novo é CONDICIONAL ao insumo (molde da DEC-027): sem `independentes`, a aritmética é
    a mesma de antes, não uma aproximação dela.
    """
    academias = _academias()
    cadeias = _cadeia_perto_de_a()
    out = calcular_pressao_por_academia(academias, cadeias)

    # Recalculado à mão, pela fórmula do contrato: oferta = Σ peso(d), pressao = 100·(1 - 1/(1+o)).
    from motor_expansao.vulnerabilidade.pressao_competitiva import (
        _haversine_m,
        peso_por_distancia,
    )

    esperado = []
    for lat, lng in zip(academias["lat"], academias["lng"], strict=True):
        d = _haversine_m(
            np.array([lat]), np.array([lng]),
            cadeias["lat"].to_numpy(float), cadeias["lng"].to_numpy(float),
        )
        oferta = float(peso_por_distancia(d, raio_m=c.PRESSAO_RAIO_M).sum())
        esperado.append(100.0 * (1.0 - 1.0 / (1.0 + oferta)))
    assert out["pressao_competitiva"].tolist() == pytest.approx(esperado)


def test_grao_hex_aceita_o_mesmo_universo_e_nao_tem_auto_exclusao() -> None:
    """A ÚNICA diferença de tratamento entre os grãos, e ela é justificada.

    A origem do grão hex é o centroide do território — não há "si mesma" para excluir. Manter a
    exclusão ali removeria arbitrariamente uma academia real da oferta do hexágono.
    """
    import h3

    hex_id = h3.latlng_to_cell(_LAT_A, _LNG_A, c.H3_RES_CONTRATO)
    dentro = pd.DataFrame(
        {
            "fonte": ["wellhub"],
            "chave_snapshot": ["dentro"],
            "lat": [_LAT_A],
            "lng": [_LNG_A],
        }
    )
    out = calcular_pressao_por_hex([hex_id], _sem_cadeias(), independentes=dentro)
    assert float(out["oferta_independentes_no_hex"].iloc[0]) > 0.0
    assert out["universo_oferta"].iloc[0] == c.UNIVERSO_OFERTA_COM_INDEPENDENTES


# --------------------------------------------------------------------------- #
# 6. O score não infere o universo
# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# 7. O default do PIPELINE, virado pela DEC-030
# --------------------------------------------------------------------------- #
def test_o_default_do_pipeline_e_o_universo_com_independentes() -> None:
    """A DEC-030 virou o default; sem esta trava, reverter seria mudo.

    O ponto de decisão NÃO é a função pura (`calcular_pressao_por_academia` exige o frame
    explicitamente, e assim deve continuar — ela não adivinha). É o wrapper da CLI, que decide se
    filtra e passa as independentes. Este teste ancora a decisão onde ela mora.
    """
    import inspect

    from motor_expansao.vulnerabilidade.alvos_ma import _pressao_por_academia

    padrao = inspect.signature(_pressao_por_academia).parameters["com_independentes"].default
    assert padrao is True, (
        "o default do pipeline voltou a `cadeias` — se a reversao for intencional, ela precisa de "
        "emenda a DEC-030, porque 37,8% do universo volta a marcar pressao zero"
    )


def test_a_flag_da_cli_permite_reproduzir_o_numero_historico() -> None:
    """A régua antiga não pode sumir: ela é a comparável com a camada de mercado (só cadeia)."""
    from motor_expansao.vulnerabilidade.alvos_ma import _parse_args

    assert _parse_args(["--base-dir", "x"]).oferta_so_cadeias is False
    assert _parse_args(["--base-dir", "x", "--oferta-so-cadeias"]).oferta_so_cadeias is True


def test_score_recusa_frame_de_pressao_sem_o_carimbo() -> None:
    """Assumir `cadeias` no silêncio carimbaria a linha com algo que ninguém declarou.

    E seria o pior default: `cadeias` é o universo que produz o número MENOR, então o erro sairia
    na direção otimista — a mesma direção do falso zero que o bloco existe para corrigir.
    """
    from motor_expansao.vulnerabilidade.score import _juntar_pressao

    universo = pd.DataFrame(
        {"fonte": ["wellhub"], "chave_snapshot": ["a"], "hex_id_res7": ["8a2a1072b59ffff"]}
    )
    sem_carimbo = pd.DataFrame(
        {"fonte": ["wellhub"], "chave_snapshot": ["a"], "pressao_competitiva": [50.0]}
    )
    with pytest.raises(ValueError, match="universo_oferta"):
        _juntar_pressao(universo, sem_carimbo)
