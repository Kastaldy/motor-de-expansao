"""BLK-MA-04: testes do score de vulnerabilidade (D4) — composição de S1/S3/S4.

Todas as fixtures são SINTÉTICAS e injetadas: séries de snapshots por `snapshots=[...]` e frames de
churn/presença forjados campo a campo. **Zero I/O** — este módulo não persiste nada, e nenhum teste
lê a fonte real (ela é gitignored, vive na VPS e carrega PII na origem, DEC-012).

Os testes que mais importam:

  * **universo** — o frame de churn é genérico e traz o feed de CADEIAS e marcas conhecidas
    listadas dentro do TotalPass. `test_cadeia_nunca_entra_no_score` falharia se o filtro saísse do
    lugar, e é o que impede a Smart Fit de aparecer como alvo de aquisição.
  * **renormalização genérica** — os pesos efetivos do Plano B (~0,20 / ~0,467 / ~0,333) são
    CALCULADOS no teste a partir de `PESOS_ALVO_SINAIS`, jamais digitados: reativar o S2 não pode
    exigir reescrever fórmula nem teste.
  * **ausência nunca é zero** — linha sem sinal algum tem score NULO. `0` afirmaria solidez.
  * **`v4` é razão absoluta** — `test_v4_nao_depende_do_universo` trava o G-D3 contra a
    reintrodução de uma normalização relativa, que tornaria o score não monotônico.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import h3
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from motor_expansao.vulnerabilidade import contrato as c
from motor_expansao.vulnerabilidade import presenca_agregador as mpresenca
from motor_expansao.vulnerabilidade import score as m
from motor_expansao.vulnerabilidade.churn_staleness import extrair_churn_staleness
from motor_expansao.vulnerabilidade.presenca_agregador import extrair_presenca_agregador
from motor_expansao.vulnerabilidade.score import (
    _assert_schema_score,
    calcular_score_vulnerabilidade,
)

HEX_A = h3.latlng_to_cell(-23.5500, -46.6300, 7)  # São Paulo
HEX_B = h3.latlng_to_cell(-22.9100, -43.1800, 7)  # Rio de Janeiro


# --------------------------------------------------------------------------- #
# Helpers de fixture sintética — série de snapshots
# --------------------------------------------------------------------------- #
def _linha(
    chave: str,
    *,
    fonte: str = "totalpass",
    rede: str = "independente",
    hex_id: str = HEX_A,
    snapshot_date: str = "2026-01-05",
    hash_: str = "h0",
    chave_origem: str = "slug",
    slug: str = "academia-sintetica",
) -> dict[str, object]:
    """Uma linha no contrato de 10 colunas do snapshot (`CONTRATO_COLUNAS_SNAPSHOT`)."""
    return {
        "snapshot_date": snapshot_date,
        "slug": slug,
        "concorrente_id": "0" * 40,
        "chave_snapshot": chave,
        "chave_origem": chave_origem,
        "hex_id_res7": hex_id,
        "rede": rede,
        "fonte": fonte,
        "hash_campos_raspados": hash_,
        "versao_contrato": c.VERSAO_CONTRATO_SNAPSHOT,
    }


def _snapshot(semana: str, linhas: list[dict[str, object]]) -> pd.DataFrame:
    df = pd.DataFrame(linhas, columns=list(c.CONTRATO_COLUNAS_SNAPSHOT.keys()))
    df["semana"] = semana
    return df


def _semana(i: int) -> str:
    return f"2026-{i:02d}"


def _serie(n: int) -> list[pd.DataFrame]:
    """`n` semanas: `HEX_A` coberto pelos DOIS agregadores, `HEX_B` só pelo TotalPass."""
    return [
        _snapshot(
            _semana(i),
            [
                _linha("k_tp", fonte="totalpass", hex_id=HEX_A),
                _linha("k_wh", fonte="wellhub", hex_id=HEX_A),
                _linha("k_tp_b", fonte="totalpass", hex_id=HEX_B),
            ],
        )
        for i in range(1, n + 1)
    ]


def _insumos(
    serie: list[pd.DataFrame],
    *,
    min_semanas: int = c.MIN_SEMANAS,
    stale_semanas: int = c.STALE_SEMANAS,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Os DOIS insumos derivados da MESMA série — o contrato de uso do modo injetado."""
    churn = extrair_churn_staleness(
        snapshots=serie, min_semanas=min_semanas, stale_semanas=stale_semanas
    )
    presenca = extrair_presenca_agregador(snapshots=serie)
    return churn, presenca


# --------------------------------------------------------------------------- #
# Helpers de fixture sintética — frames de insumo forjados campo a campo
# --------------------------------------------------------------------------- #
def _linha_churn(
    chave: str,
    *,
    fonte: str = "totalpass",
    rede: str = "independente",
    hex_id: str = HEX_A,
    chave_origem: str = "slug",
    status: str = "estavel",
    n_semanas_serie: int = 9,
    n_semanas_presente: int = 9,
    n_desaparecimentos: int = 0,
    semanas_sem_mudanca: int = 0,
    imatura: bool = False,
    interpretavel: bool = False,
) -> dict[str, object]:
    """Uma linha no contrato de churn vigente, com os campos do score parametrizáveis."""
    return {
        "chave_snapshot": chave,
        "fonte": fonte,
        "rede": rede,
        "hex_id_res7": hex_id,
        "chave_origem": chave_origem,
        "status_churn": status,
        "n_semanas_serie": n_semanas_serie,
        "n_semanas_presente": n_semanas_presente,
        "n_desaparecimentos": n_desaparecimentos,
        "semanas_sem_mudanca": semanas_sem_mudanca,
        "semana_primeira_observacao": "2026-01",
        "semana_ultima_observacao": "2026-09",
        "snapshot_date_ultimo": "2026-03-02",
        "flag_serie_imatura": imatura,
        "flag_staleness_interpretavel": interpretavel,
        "flag_troca_chave_na_serie": False,
        "versao_contrato": c.VERSAO_CONTRATO_CHURN,
    }


def _churn(linhas: list[dict[str, object]]) -> pd.DataFrame:
    df = pd.DataFrame(linhas, columns=list(c.CONTRATO_COLUNAS_CHURN.keys()))
    for coluna, dtype in c.CONTRATO_COLUNAS_CHURN.items():
        df[coluna] = df[coluna].astype(dtype)
    return df


def _linha_presenca(
    hex_id: str = HEX_A, *, fontes: tuple[str, ...] = c.FONTES_AGREGADORES
) -> dict[str, object]:
    """Uma linha no contrato `presenca_agregador_v1`, coerente com a regra dos dois relógios."""
    linha: dict[str, object] = {
        "hex_id_res7": hex_id,
        "fontes_presentes_no_hex": ",".join(f for f in c.FONTES_AGREGADORES if f in fontes),
        "n_agregadores_no_hex": len(fontes),
        "versao_contrato": c.VERSAO_CONTRATO_PRESENCA_AGREGADOR,
    }
    for fonte in c.FONTES_AGREGADORES:
        presente = fonte in fontes
        linha[f"n_academias_independentes_{fonte}"] = 1 if presente else 0
        linha[f"semana_ultima_observacao_{fonte}"] = "2026-09" if presente else pd.NA
        linha[f"snapshot_date_ultimo_{fonte}"] = "2026-03-02" if presente else pd.NA
    return linha


def _presenca(linhas: list[dict[str, object]]) -> pd.DataFrame:
    df = pd.DataFrame(linhas, columns=list(c.CONTRATO_COLUNAS_PRESENCA_AGREGADOR.keys()))
    for coluna, dtype in c.CONTRATO_COLUNAS_PRESENCA_AGREGADOR.items():
        df[coluna] = df[coluna].astype(dtype)
    return df


def _linha_de(df: pd.DataFrame, chave: str) -> pd.Series:
    recorte = df[df["chave_snapshot"] == chave]
    assert len(recorte) == 1, f"a chave {chave} deveria ter exatamente 1 linha"
    return recorte.iloc[0]


def _idx(df: pd.DataFrame, chave: str) -> int:
    return int(df.index[df["chave_snapshot"] == chave][0])


def _tokens(linha: pd.Series) -> list[str]:
    return [t for t in str(linha["sinais_disponiveis"]).split(",") if t]


def _saida_valida() -> pd.DataFrame:
    """Saída bem-formada com os TRÊS regimes que interessam, base dos testes de `_assert_schema`.

    `k_full` cobre `{s1, s3, s4}`; `k_so_s1` cobre o ramp-up; `k_sem_sinal` vive num hex sem par no
    sinal 1 e sem maturidade alguma — é a única forma consistente de ter uma linha com zero sinais.
    """
    churn = _churn(
        [
            _linha_churn(
                "k_full",
                status="sumiu_recente",
                semanas_sem_mudanca=6,
                interpretavel=True,
                n_semanas_serie=13,
            ),
            _linha_churn("k_so_s1", status="novo", imatura=True, n_semanas_serie=3),
            _linha_churn(
                "k_sem_sinal", hex_id=HEX_B, status="novo", imatura=True, n_semanas_serie=3
            ),
        ]
    )
    return calcular_score_vulnerabilidade(churn=churn, presenca=_presenca([_linha_presenca()]))


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture
def serie_rampup() -> list[pd.DataFrame]:
    """3 semanas: tudo imaturo, S3/S4 renormalizados para fora — regime `{S1}`."""
    return _serie(3)


@pytest.fixture
def serie_madura_s3() -> list[pd.DataFrame]:
    """9 semanas: madura para o S3 (>= `MIN_SEMANAS`), ainda opaca para o S4 (< `STALE_SEMANAS`)."""
    return _serie(9)


@pytest.fixture
def serie_madura_s3_s4() -> list[pd.DataFrame]:
    """13 semanas: os três sinais do Plano B disponíveis — regime `{S1, S3, S4}`."""
    return _serie(13)


@pytest.fixture
def serie_universo_misturado() -> list[pd.DataFrame]:
    """Uma linha por CLASSE: cadeia com a `rede` forjada, marca conhecida no TP e 2 legítimas."""
    return [
        _snapshot(
            _semana(i),
            [
                _linha("k_un", fonte="unidades", rede="independente", hex_id=HEX_B),
                _linha("k_marca", fonte="totalpass", rede="smart_fit", hex_id=HEX_B),
                _linha("k_tp", fonte="totalpass", hex_id=HEX_A),
                _linha("k_wh", fonte="wellhub", hex_id=HEX_A),
            ],
        )
        for i in range(1, 4)
    ]


# --------------------------------------------------------------------------- #
# CA-1 — pesos-alvo do D4 e renormalização GENÉRICA
# --------------------------------------------------------------------------- #
def test_pesos_do_d4_seguem_congelados_e_somam_um() -> None:
    """O gate de 2026-07-23 continua valendo: o S6 entrou POR CIMA, sem repesar S1..S4.

    Este é o teste que impede a entrada de um sinal novo de virar repesagem por tabela. Se alguém
    adotar o conjunto ilustrativo de 6 sinais do §8.3 (que muda `s1` de 0,15 para 0,12), ele
    quebra — e tem de quebrar, porque isso é reabrir o gate.
    """
    assert c.PESOS_ALVO_D4 == {"s1": 0.15, "s2": 0.25, "s3": 0.35, "s4": 0.25}
    assert abs(sum(c.PESOS_ALVO_D4.values()) - 1.0) < 1e-9
    for sinal, peso in c.PESOS_ALVO_D4.items():
        assert c.PESOS_ALVO_SINAIS[sinal] == peso, f"o S6 nao pode ter mexido em `{sinal}`"
    assert c.SINAIS_INATIVOS == ("s2",)


def test_soma_alvo_maior_que_um_e_inocua_por_construcao() -> None:
    """Com o S6, `PESOS_ALVO_SINAIS` soma 1,10 — e isso não altera peso efetivo algum.

    `renormalizar_pesos` divide pela soma dos PRESENTES, nunca pelo total do dicionário. A soma do
    dicionário é, portanto, um número sem consumidor: o que vale é sempre a razão dentro do regime.
    """
    assert abs(sum(c.PESOS_ALVO_SINAIS.values()) - 1.10) < 1e-9
    assert tuple(c.PESOS_ALVO_SINAIS) == c.SINAIS_ORDEM
    for subconjunto in (["s1"], ["s1", "s3"], ["s1", "s3", "s4"], ["s3", "s4"]):
        assert abs(sum(c.renormalizar_pesos(subconjunto).values()) - 1.0) < 1e-9


def _pressao(pares: list[tuple[str, float]]) -> pd.DataFrame:
    """Frame mínimo de pressão: `hex_id_res7` + `pressao_competitiva_no_hex` em [0, 100)."""
    return pd.DataFrame(
        {
            "hex_id_res7": pd.Series([h for h, _ in pares], dtype="string"),
            "pressao_competitiva_no_hex": pd.Series([p for _, p in pares], dtype="float64"),
        }
    )


# --------------------------------------------------------------------------- #
# BLK-MA-12 — o S6 como COMPONENTE (não mais fato sem peso)
# --------------------------------------------------------------------------- #
def test_s6_entra_no_regime_quando_o_insumo_vem(serie_madura_s3_s4: list[pd.DataFrame]) -> None:
    churn, presenca = _insumos(serie_madura_s3_s4)
    out = calcular_score_vulnerabilidade(
        churn=churn, presenca=presenca, pressao=_pressao([(HEX_A, 60.0), (HEX_B, 0.0)])
    )
    linha = _linha_de(out, "k_tp")
    assert "s6" in _tokens(linha)
    assert float(linha["v6"]) == pytest.approx(0.60)
    assert int(linha["n_sinais_disponiveis"]) == 4


def test_v6_e_razao_absoluta_nao_percentil_do_lote() -> None:
    """G-D3 aplicado ao S6: o valor de uma linha não pode depender de quem mais está no lote.

    Percentil por universo tornaria o score não-monotônico — acrescentar uma academia muito
    pressionada baixaria o `v6` de todas as outras. É o mesmo defeito que tirou o `v4` do percentil.
    """
    linhas = [
        _linha_churn("k_a", hex_id=HEX_A, n_semanas_serie=13, interpretavel=True),
        _linha_churn("k_b", hex_id=HEX_B, n_semanas_serie=13, interpretavel=True),
    ]
    pressao = _pressao([(HEX_A, 40.0), (HEX_B, 90.0)])
    dupla = calcular_score_vulnerabilidade(
        churn=_churn(linhas), presenca=_presenca([_linha_presenca(HEX_A), _linha_presenca(HEX_B)]),
        pressao=pressao,
    )
    sozinha = calcular_score_vulnerabilidade(
        churn=_churn(linhas[:1]), presenca=_presenca([_linha_presenca(HEX_A)]), pressao=pressao
    )
    assert float(_linha_de(dupla, "k_a")["v6"]) == float(_linha_de(sozinha, "k_a")["v6"])
    assert float(_linha_de(dupla, "k_a")["score_vulnerabilidade"]) == pytest.approx(
        float(_linha_de(sozinha, "k_a")["score_vulnerabilidade"])
    )


def test_pressao_zero_e_medicao_e_entra_no_score() -> None:
    """`0` medido NÃO é ausência: o sinal está disponível e contribui com `v6 = 0`."""
    churn = _churn([_linha_churn("k", hex_id=HEX_A, n_semanas_serie=13, interpretavel=True)])
    out = calcular_score_vulnerabilidade(
        churn=churn, presenca=_presenca([_linha_presenca()]), pressao=_pressao([(HEX_A, 0.0)])
    )
    linha = out.iloc[0]
    assert "s6" in _tokens(linha)
    assert float(linha["v6"]) == 0.0
    assert not pd.isna(linha["score_vulnerabilidade"])


def test_hex_sem_par_na_pressao_fica_com_s6_fora() -> None:
    """Miss no join = sinal indisponível, exatamente como no `s1`. Nunca imputa zero."""
    churn = _churn([_linha_churn("k", hex_id=HEX_B, n_semanas_serie=13, interpretavel=True)])
    out = calcular_score_vulnerabilidade(
        churn=churn,
        presenca=_presenca([_linha_presenca(HEX_B)]),
        pressao=_pressao([(HEX_A, 80.0)]),
    )
    linha = out.iloc[0]
    assert "s6" not in _tokens(linha)
    assert pd.isna(linha["v6"])


def test_zero_sinais_continua_alcancavel_com_o_s6_no_contrato() -> None:
    """A invariante mais antiga da camada NÃO pode virar inalcançável.

    Um S6 "sempre disponível" extinguiria o regime `n_sinais_disponiveis == 0` e, com ele, a trava
    "ausência nunca é zero" — que passaria a nunca disparar. Condicionar o S6 ao insumo é o que
    mantém o regime alcançável.
    """
    churn = _churn(
        [_linha_churn("k", hex_id=HEX_B, status="novo", n_semanas_serie=3, imatura=True)]
    )
    out = calcular_score_vulnerabilidade(
        churn=churn, presenca=_presenca([_linha_presenca()]), pressao=_pressao([(HEX_A, 50.0)])
    )
    linha = out.iloc[0]
    assert int(linha["n_sinais_disponiveis"]) == 0
    assert pd.isna(linha["score_vulnerabilidade"]), "ausencia nunca e' zero"


def test_frame_de_pressao_com_hex_duplicado_levanta() -> None:
    churn = _churn([_linha_churn("k", n_semanas_serie=13, interpretavel=True)])
    with pytest.raises(ValueError, match="duplicado"):
        calcular_score_vulnerabilidade(
            churn=churn,
            presenca=_presenca([_linha_presenca()]),
            pressao=_pressao([(HEX_A, 10.0), (HEX_A, 20.0)]),
        )


def test_renormalizar_pesos_reescala_para_somar_um() -> None:
    """Qualquer subconjunto soma `1,0`, sai na ordem canônica e ignora duplicatas."""
    for subconjunto in (["s1"], ["s3", "s4"], ["s1", "s3"], ["s1", "s2", "s3", "s4"]):
        pesos = c.renormalizar_pesos(subconjunto)
        assert set(pesos) == set(subconjunto)
        assert abs(sum(pesos.values()) - 1.0) < 1e-9
        assert list(pesos) == [s for s in c.SINAIS_ORDEM if s in set(subconjunto)]
    assert c.renormalizar_pesos(["s3", "s1", "s1"]) == c.renormalizar_pesos(["s1", "s3"])
    assert c.renormalizar_pesos(["s1"]) == {"s1": 1.0}


def test_pesos_efetivos_do_plano_b_sao_calculados_nao_digitados() -> None:
    """Os `~0,20 / ~0,467 / ~0,333` são CONSEQUÊNCIA da renormalização, nunca constante.

    O Plano B é o REGIME `{s1, s3, s4}` — a linha sem insumo de pressão, que é o caso geral. Não é
    mais "todos os sinais não-inativos": com o S6 passou a existir a categoria **ativo mas
    condicional** (existe no contrato, disponível só quando o insumo vem). É por isso que o regime
    é enumerado aqui em vez de derivado de `SINAIS_INATIVOS`.
    """
    plano_b = ["s1", "s3", "s4"]
    pesos = c.renormalizar_pesos(plano_b)
    soma_alvo = sum(c.PESOS_ALVO_SINAIS[s] for s in plano_b)
    for sinal in plano_b:
        assert pesos[sinal] == pytest.approx(c.PESOS_ALVO_SINAIS[sinal] / soma_alvo)
    assert pesos["s1"] == pytest.approx(0.2, abs=1e-3)
    assert pesos["s3"] == pytest.approx(0.4667, abs=1e-3)
    assert pesos["s4"] == pytest.approx(0.3333, abs=1e-3)


def test_s6_nao_desloca_os_pesos_de_quem_nao_tem_pressao() -> None:
    """A garantia central do desenho: sem insumo de pressão, o score é bit a bit o de antes.

    Se o S6 fosse "sempre disponível", os pesos efetivos de S1/S3/S4 cairiam para
    `0,176 / 0,412 / 0,294` e TODA linha mudaria de valor — inclusive as que não têm pressão
    medida. Este teste é o que impede essa regressão.
    """
    for regime in (["s1"], ["s1", "s3"], ["s1", "s3", "s4"], ["s3", "s4"], ["s3"]):
        sem_s6 = c.renormalizar_pesos(regime)
        esperado = {s: c.PESOS_ALVO_D4[s] / sum(c.PESOS_ALVO_D4[x] for x in regime) for s in regime}
        for sinal in regime:
            assert sem_s6[sinal] == pytest.approx(esperado[sinal]), (regime, sinal)


def test_renormalizar_pesos_vazio_devolve_dict_vazio() -> None:
    """Sem sinal algum não há divisão por zero nem "pesos iguais" — há AUSÊNCIA."""
    assert c.renormalizar_pesos([]) == {}


def test_renormalizar_pesos_rejeita_sinal_desconhecido() -> None:
    with pytest.raises(ValueError, match="SINAIS_ORDEM"):
        c.renormalizar_pesos(["s1", "s9"])


# --------------------------------------------------------------------------- #
# CA-2 — os regimes de disponibilidade e os seus pesos efetivos
# --------------------------------------------------------------------------- #
def test_regime_so_s1(serie_rampup: list[pd.DataFrame]) -> None:
    """Ramp-up: S3/S4 renormalizados para fora, S1 com peso `1,00`."""
    churn, presenca = _insumos(serie_rampup)
    out = calcular_score_vulnerabilidade(churn=churn, presenca=presenca)
    linha = _linha_de(out, "k_tp_b")
    assert _tokens(linha) == ["s1"]
    assert int(linha["n_sinais_disponiveis"]) == 1
    assert float(linha["v1"]) == 0.5
    assert float(linha["score_vulnerabilidade"]) == pytest.approx(
        100.0 * c.renormalizar_pesos(["s1"])["s1"] * 0.5
    )


def test_regime_s1_s3(serie_madura_s3: list[pd.DataFrame]) -> None:
    """9 semanas: o S3 amadurece (`>= MIN_SEMANAS`) e o S4 continua fora (`< STALE_SEMANAS`)."""
    churn, presenca = _insumos(serie_madura_s3)
    out = calcular_score_vulnerabilidade(churn=churn, presenca=presenca)
    linha = _linha_de(out, "k_tp_b")
    assert _tokens(linha) == ["s1", "s3"]
    assert int(linha["n_sinais_disponiveis"]) == 2
    pesos = c.renormalizar_pesos(["s1", "s3"])
    esperado = 100.0 * (pesos["s1"] * float(linha["v1"]) + pesos["s3"] * float(linha["v3"]))
    assert float(linha["score_vulnerabilidade"]) == pytest.approx(esperado)
    assert bool(linha["flag_score_provisorio"]) is False


def test_regime_s1_s3_s4(serie_madura_s3_s4: list[pd.DataFrame]) -> None:
    """13 semanas: os três sinais do Plano B entram, com os pesos efetivos renormalizados."""
    churn, presenca = _insumos(serie_madura_s3_s4)
    out = calcular_score_vulnerabilidade(churn=churn, presenca=presenca)
    linha = _linha_de(out, "k_tp_b")
    assert _tokens(linha) == ["s1", "s3", "s4"]
    assert int(linha["n_sinais_disponiveis"]) == 3
    pesos = c.renormalizar_pesos(["s1", "s3", "s4"])
    esperado = 100.0 * sum(
        pesos[s] * float(linha[v]) for s, v in (("s1", "v1"), ("s3", "v3"), ("s4", "v4"))
    )
    assert float(linha["score_vulnerabilidade"]) == pytest.approx(esperado)
    assert float(linha["score_vulnerabilidade_ordenavel"]) == pytest.approx(esperado)


def test_regime_so_s3() -> None:
    """Regime de UM sinal em que a coluna ordenável NASCE PREENCHIDA — e isso é escolha, não bug.

    O `flag_score_provisorio` do §8.4 é a conjunção "S3 **e** S4 indisponíveis": com o S3 maduro
    ela desliga, mesmo que ele seja o ÚNICO sinal da linha. O peso renormaliza para `1,00`, e um
    `sumiu_recente` (`v3 = 1.0`) sai com `score = 100,0` e `score_vulnerabilidade_ordenavel = 100,0`
    — no topo de qualquer ordenação, ao lado de linhas `{s1,s3,s4}` que estão em OUTRA régua.

    É fiel ao §8.4 ratificado (S3 maduro é sinal maduro), mas significa que o guardrail criado pelo
    G-D1 **não cobre** este regime. Inalcançável pelo caminho `base_dir` — `extrair_presenca_agregador`
    e `extrair_churn_staleness` saem da MESMA série, então todo hex do churn tem par no sinal 1 —,
    porém alcançável por frames injetados, que é justamente o modo que o BLK-MA-05 pode usar.

    Daí a obrigação registrada no §8.5 do contrato: **segmentar por `n_sinais_disponiveis` antes de
    ordenar.** Este teste existe para que o comportamento seja descoberto aqui, e não pelo MA-05.
    """
    # `HEX_B` não tem par no frame de presença (só `HEX_A`) -> `v1` ausente, S1 fora.
    # Série madura (9 >= MIN_SEMANAS) -> S3 dentro. Staleness não interpretável -> S4 fora.
    churn = _churn(
        [
            _linha_churn(
                "k",
                hex_id=HEX_B,
                status="sumiu_recente",
                n_semanas_serie=9,
                imatura=False,
                interpretavel=False,
            )
        ]
    )
    linha = _linha_de(
        calcular_score_vulnerabilidade(churn=churn, presenca=_presenca([_linha_presenca()])), "k"
    )

    assert _tokens(linha) == ["s3"]
    assert int(linha["n_sinais_disponiveis"]) == 1
    assert c.renormalizar_pesos(["s3"]) == {"s3": 1.0}, "peso efetivo do sinal único"
    assert float(linha["v3"]) == c.V3_POR_STATUS_CHURN["sumiu_recente"]
    assert float(linha["score_vulnerabilidade"]) == pytest.approx(100.0)

    # O ponto do teste: a flag desliga e a ordenável NÃO protege este regime de 1 sinal.
    assert bool(linha["flag_score_provisorio"]) is False
    assert not pd.isna(linha["score_vulnerabilidade_ordenavel"])
    assert float(linha["score_vulnerabilidade_ordenavel"]) == pytest.approx(100.0)


def test_ordenavel_nao_separa_regimes_de_tamanho_diferente() -> None:
    """A consequência do teste acima, dita em números: as duas réguas se misturam num `sort`.

    Uma linha `{s3}` com `sumiu_recente` (100,0) fica ACIMA de uma linha `{s1,s3,s4}` completa,
    com os três sinais medidos. `score_vulnerabilidade_ordenavel` não distingue as duas — quem
    ordena precisa de `n_sinais_disponiveis`, que existe na saída exatamente para isso (§8.5).
    """
    churn = _churn(
        [
            _linha_churn(
                "k_so_s3", hex_id=HEX_B, status="sumiu_recente", n_semanas_serie=9
            ),
            _linha_churn(
                "k_completa",
                status="sumiu_recente",
                semanas_sem_mudanca=6,
                interpretavel=True,
                n_semanas_serie=13,
            ),
        ]
    )
    out = calcular_score_vulnerabilidade(churn=churn, presenca=_presenca([_linha_presenca()]))

    assert _tokens(_linha_de(out, "k_so_s3")) == ["s3"]
    assert _tokens(_linha_de(out, "k_completa")) == ["s1", "s3", "s4"]

    ordenado = out.sort_values("score_vulnerabilidade_ordenavel", ascending=False)
    assert str(ordenado.iloc[0]["chave_snapshot"]) == "k_so_s3", "1 sinal lidera 3 sinais"
    assert not bool(ordenado["score_vulnerabilidade_ordenavel"].isna().any()), (
        "nenhuma das duas é filtrada pela ordenável: a segmentação tem de ser explícita"
    )
    assert set(int(v) for v in ordenado["n_sinais_disponiveis"]) == {1, 3}


def test_s4_disponivel_implica_s3_disponivel() -> None:
    """Consequência de `STALE_SEMANAS > MIN_SEMANAS` — travada por teste, nunca por `assert`."""
    assert c.STALE_SEMANAS > c.MIN_SEMANAS
    for n in (3, 9, 13, 20):
        churn, presenca = _insumos(_serie(n))
        out = calcular_score_vulnerabilidade(churn=churn, presenca=presenca)
        for _, linha in out.iterrows():
            tokens = _tokens(linha)
            if "s4" in tokens:
                assert "s3" in tokens, (n, tokens)


def test_regime_s4_sozinho_e_inalcancavel() -> None:
    """Nenhuma série produzida pelo extrator é imatura E interpretável ao mesmo tempo."""
    padroes: set[str] = set()
    for n in (3, 9, 13, 20):
        churn, presenca = _insumos(_serie(n))
        assert not bool(
            (churn["flag_serie_imatura"] & churn["flag_staleness_interpretavel"]).any()
        )
        out = calcular_score_vulnerabilidade(churn=churn, presenca=presenca)
        padroes |= set(out["sinais_disponiveis"].astype(str))
    assert "s4" not in padroes
    assert "s1,s4" not in padroes


# --------------------------------------------------------------------------- #
# CA-3 — `v1` é CATEGÓRICO (emenda G1), nunca uma posição relativa
# --------------------------------------------------------------------------- #
def test_v1_por_mapa_categorico() -> None:
    """`2 agregadores -> 0.0`, `1 agregador -> 0.5`. O ramo `0 -> 1.0` é inalcançável."""
    churn = _churn(
        [_linha_churn("k_a", hex_id=HEX_A, imatura=True), _linha_churn("k_b", hex_id=HEX_B, imatura=True)]
    )
    presenca = _presenca(
        [_linha_presenca(HEX_A), _linha_presenca(HEX_B, fontes=("totalpass",))]
    )
    out = calcular_score_vulnerabilidade(churn=churn, presenca=presenca)
    assert float(_linha_de(out, "k_a")["v1"]) == 0.0
    assert float(_linha_de(out, "k_b")["v1"]) == 0.5
    assert int(_linha_de(out, "k_a")["n_agregadores_no_hex"]) == 2
    assert int(_linha_de(out, "k_b")["n_agregadores_no_hex"]) == 1


def test_nenhum_percentil_toca_v1_nem_v3() -> None:
    """Prova operacional: engordar o universo com linhas idênticas não move `v1` nem `v3`."""
    base = _linha_churn("k_alvo", status="piscando", semanas_sem_mudanca=4, interpretavel=True)
    presenca = _presenca([_linha_presenca(HEX_A, fontes=("totalpass",))])

    sozinha = calcular_score_vulnerabilidade(churn=_churn([base]), presenca=presenca)
    acompanhadas = [base] + [
        _linha_churn(f"k_{i}", status="sumiu_recente", semanas_sem_mudanca=i, interpretavel=True)
        for i in range(40)
    ]
    multidao = calcular_score_vulnerabilidade(churn=_churn(acompanhadas), presenca=presenca)

    alvo_sozinha = _linha_de(sozinha, "k_alvo")
    alvo_multidao = _linha_de(multidao, "k_alvo")
    assert float(alvo_sozinha["v1"]) == float(alvo_multidao["v1"])
    assert float(alvo_sozinha["v3"]) == float(alvo_multidao["v3"])
    assert float(alvo_sozinha["score_vulnerabilidade"]) == pytest.approx(
        float(alvo_multidao["score_vulnerabilidade"])
    )


def test_modulo_nao_usa_funcao_de_percentil() -> None:
    """Nenhuma normalização relativa ao universo no módulo — o G-D3 vira trava de fonte.

    **HEURÍSTICA por substring da fonte, defesa SECUNDÁRIA** `[precisão BLK-MA-04-FU1]`: não pega
    `scipy.stats.rankdata`, `np.percentile` sob alias, nem qualquer forma que não contenha o texto
    literal. A defesa PRIMÁRIA é `test_v4_nao_depende_do_universo`, que mede o comportamento em
    vez de ler o código. Esta aqui é barata e pega o caso comum; não é prova.
    """
    fonte = inspect.getsource(m)
    for proibido in ("rank" + "(", "quantile" + "(", "percen" + "tile"):
        assert proibido not in fonte, proibido


# --------------------------------------------------------------------------- #
# CA-4 — `v3` pelos QUATRO status de churn, com `novo` -> ausente
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("status", "esperado"),
    [("sumiu_recente", 1.0), ("piscando", 0.7), ("estavel", 0.0), ("novo", None)],
)
def test_v3_cobre_os_quatro_status(status: str, esperado: float | None) -> None:
    imatura = status == "novo"
    churn = _churn([_linha_churn("k", status=status, imatura=imatura)])
    out = calcular_score_vulnerabilidade(churn=churn, presenca=_presenca([_linha_presenca()]))
    linha = _linha_de(out, "k")
    assert linha["status_churn"] == status
    if esperado is None:
        assert pd.isna(linha["v3"])
        assert "s3" not in _tokens(linha)
    else:
        assert float(linha["v3"]) == pytest.approx(esperado)
        assert "s3" in _tokens(linha)


def test_v3_de_novo_e_ausente_nunca_zero() -> None:
    """Ler "série curta demais para julgar" como "estável" inverteria o sinal em silêncio.

    Vale inclusive na combinação inconsistente (`novo` com a série marcada madura), que o extrator
    nunca produz mas um frame forjado pode: o sinal sai do regime em vez de virar `0.0`.
    """
    assert c.V3_POR_STATUS_CHURN["novo"] is None
    for imatura in (True, False):
        churn = _churn([_linha_churn("k", status="novo", imatura=imatura)])
        out = calcular_score_vulnerabilidade(churn=churn, presenca=_presenca([_linha_presenca()]))
        linha = _linha_de(out, "k")
        assert pd.isna(linha["v3"]), imatura
        assert "s3" not in _tokens(linha), imatura


def test_v3_map_tem_exatamente_os_status_do_contrato() -> None:
    """Um 5º estado de churn no futuro quebra AQUI, em vez de cair num default silencioso."""
    assert set(c.V3_POR_STATUS_CHURN) == set(c.STATUS_CHURN_VALIDOS)
    assert len(c.STATUS_CHURN_VALIDOS) == 4


# --------------------------------------------------------------------------- #
# CA-5 — `v4` é RAZÃO ABSOLUTA (G-D3), com clip em 1
# --------------------------------------------------------------------------- #
def test_v4_e_razao_absoluta_com_clip_em_um() -> None:
    esperado = {0: 0.0, 6: 0.5, 12: 1.0, 30: 1.0}
    churn = _churn(
        [
            _linha_churn(f"k_{n}", semanas_sem_mudanca=n, interpretavel=True)
            for n in esperado
        ]
    )
    out = calcular_score_vulnerabilidade(churn=churn, presenca=_presenca([_linha_presenca()]))
    for n, valor in esperado.items():
        assert float(_linha_de(out, f"k_{n}")["v4"]) == pytest.approx(valor), n
        assert float(_linha_de(out, f"k_{n}")["v4"]) == pytest.approx(
            min(n / c.STALE_SEMANAS, 1.0)
        )


def test_v4_so_entra_quando_staleness_interpretavel() -> None:
    churn = _churn(
        [
            _linha_churn("k_opaca", semanas_sem_mudanca=6, interpretavel=False),
            _linha_churn("k_legivel", semanas_sem_mudanca=6, interpretavel=True),
        ]
    )
    out = calcular_score_vulnerabilidade(churn=churn, presenca=_presenca([_linha_presenca()]))
    opaca = _linha_de(out, "k_opaca")
    legivel = _linha_de(out, "k_legivel")
    assert pd.isna(opaca["v4"]) and "s4" not in _tokens(opaca)
    assert float(legivel["v4"]) == pytest.approx(0.5) and "s4" in _tokens(legivel)


def test_v4_nao_depende_do_universo() -> None:
    """Trava do G-D3: uma academia muito parada não pode baixar o `v4` de terceiros."""
    alvo = _linha_churn("k_alvo", semanas_sem_mudanca=3, interpretavel=True)
    presenca = _presenca([_linha_presenca()])
    sozinha = calcular_score_vulnerabilidade(churn=_churn([alvo]), presenca=presenca)
    vizinhos = [alvo] + [
        _linha_churn(f"k_{i}", semanas_sem_mudanca=50 + i, interpretavel=True) for i in range(50)
    ]
    multidao = calcular_score_vulnerabilidade(churn=_churn(vizinhos), presenca=presenca)
    assert float(_linha_de(sozinha, "k_alvo")["v4"]) == pytest.approx(
        float(_linha_de(multidao, "k_alvo")["v4"])
    )
    assert float(_linha_de(sozinha, "k_alvo")["score_vulnerabilidade"]) == pytest.approx(
        float(_linha_de(multidao, "k_alvo")["score_vulnerabilidade"])
    )


# --------------------------------------------------------------------------- #
# CA-6 — o regime `{S1}` produz `{0, 50}`: a evidência que o gate releu
# --------------------------------------------------------------------------- #
def test_rampup_score_assume_apenas_zero_e_cinquenta(serie_rampup: list[pd.DataFrame]) -> None:
    churn, presenca = _insumos(serie_rampup)
    out = calcular_score_vulnerabilidade(churn=churn, presenca=presenca)
    assert set(float(v) for v in out["score_vulnerabilidade"]) <= {0.0, 50.0}
    assert len(out) == 3


def test_rampup_flag_score_provisorio_em_todas_as_linhas(
    serie_rampup: list[pd.DataFrame],
) -> None:
    churn, presenca = _insumos(serie_rampup)
    out = calcular_score_vulnerabilidade(churn=churn, presenca=presenca)
    assert bool(out["flag_score_provisorio"].all())
    assert bool(out["flag_serie_imatura"].all())


def test_rampup_coluna_ordenavel_e_toda_nula(serie_rampup: list[pd.DataFrame]) -> None:
    """G-D1: ordenar um frame provisório devolve NADA, não devolve lixo."""
    churn, presenca = _insumos(serie_rampup)
    out = calcular_score_vulnerabilidade(churn=churn, presenca=presenca)
    assert bool(out["score_vulnerabilidade_ordenavel"].isna().all())
    assert not bool(out["score_vulnerabilidade"].isna().any())
    ordenado = out.sort_values("score_vulnerabilidade_ordenavel", ascending=False)
    assert bool(ordenado["score_vulnerabilidade_ordenavel"].isna().all())


def test_score_zero_no_rampup_nao_significa_nao_vulneravel(
    serie_rampup: list[pd.DataFrame],
) -> None:
    """O `0` do ramp-up diz "o hex tem os 2 agregadores", não "esta academia é sólida"."""
    churn, presenca = _insumos(serie_rampup)
    out = calcular_score_vulnerabilidade(churn=churn, presenca=presenca)
    linha = _linha_de(out, "k_tp")
    assert float(linha["score_vulnerabilidade"]) == 0.0
    assert int(linha["n_agregadores_no_hex"]) == 2
    assert _tokens(linha) == ["s1"]
    assert bool(linha["flag_score_provisorio"]) is True
    assert pd.isna(linha["score_vulnerabilidade_ordenavel"])


# --------------------------------------------------------------------------- #
# CA-7 — bordas de ausência: ausência NUNCA é zero
# --------------------------------------------------------------------------- #
def test_zero_sinais_disponiveis_produz_score_nulo_nunca_zero() -> None:
    churn = _churn([_linha_churn("k", hex_id=HEX_B, status="novo", imatura=True)])
    out = calcular_score_vulnerabilidade(churn=churn, presenca=_presenca([_linha_presenca()]))
    linha = _linha_de(out, "k")
    assert int(linha["n_sinais_disponiveis"]) == 0
    assert str(linha["sinais_disponiveis"]) == ""
    assert pd.isna(linha["score_vulnerabilidade"])
    assert pd.isna(linha["score_vulnerabilidade_ordenavel"])
    # A versão anterior desta linha era `float(score or 1.0) != 0.0` — asserção MORTA: `NaN` e
    # `0.0` passavam os dois (`0.0 or 1.0` é `1.0`, e `NaN or 1.0` é `NaN`, que != 0.0). A forma
    # abaixo é sobre o frame inteiro e falha de verdade se alguém imputar `0` para ausência.
    assert not bool(
        (out["n_sinais_disponiveis"].eq(0) & out["score_vulnerabilidade"].eq(0.0)).any()
    )


def test_v1_ausente_nao_e_imputado() -> None:
    """Imputar `0.0` leria "2 agregadores" (falso negativo injetado); `0.5` ou `1.0`, pior ainda."""
    churn = _churn([_linha_churn("k", hex_id=HEX_B, imatura=True)])
    out = calcular_score_vulnerabilidade(churn=churn, presenca=_presenca([_linha_presenca()]))
    linha = _linha_de(out, "k")
    assert pd.isna(linha["v1"])
    assert pd.isna(linha["n_agregadores_no_hex"])
    assert pd.isna(linha["fontes_presentes_no_hex"])
    assert "s1" not in _tokens(linha)


def test_presenca_bem_formada_porem_vazia_com_churn_cheio() -> None:
    """Sinal 1 sem NENHUMA linha não zera o score: renormaliza o S1 para fora, como o `v1` ausente.

    É o caso do lote em que o feed de agregador falhou por inteiro (ou do primeiro lote, antes de
    haver hex algum). O frame de presença é VÁLIDO — só vazio —, e o `left join` deixa todas as
    linhas sem par. A direção é a segura: o universo continua pontuando pelo que sobrou, em vez de
    sumir ou receber `v1` imputado.
    """
    churn = _churn([_linha_churn("k", status="sumiu_recente", n_semanas_serie=9)])
    presenca_vazia = pd.DataFrame(
        {
            col: pd.Series(dtype=dtype)
            for col, dtype in c.CONTRATO_COLUNAS_PRESENCA_AGREGADOR.items()
        }
    )
    assert presenca_vazia.empty

    out = calcular_score_vulnerabilidade(churn=churn, presenca=presenca_vazia)
    assert len(out) == 1, "a linha do churn NÃO pode ser descartada pelo join"
    assert list(out.columns) == list(c.CONTRATO_COLUNAS_SCORE), "o contrato sai íntegro"

    linha = _linha_de(out, "k")
    assert pd.isna(linha["v1"])
    assert pd.isna(linha["n_agregadores_no_hex"])
    assert "s1" not in _tokens(linha)
    assert not pd.isna(linha["score_vulnerabilidade"]), "o que sobrou ainda pontua"


def test_churn_vazio_retorna_antes_de_validar_a_presenca() -> None:
    """A ORDEM de validação dos insumos, travada: `churn` vazio -> retorno ANTES do schema da presença.

    Medido em 2026-08-12: com `churn.empty`, uma presença malformada (coluna fora do contrato)
    passa SEM ser validada, porque o retorno antecipado vem primeiro. A direção é segura — a saída
    é vazia e ela própria validada —, mas era comportamento não declarado e sem teste; a
    contraprova abaixo mostra que o mesmo frame ruim levanta assim que o churn tem linha.

    Se um bloco futuro mover a validação da presença para antes do retorno antecipado, este teste
    quebra e a mudança de ordem vira decisão explícita, não efeito colateral.
    """
    churn_vazio = pd.DataFrame(
        {col: pd.Series(dtype=dtype) for col, dtype in c.CONTRATO_COLUNAS_CHURN.items()}
    )
    presenca_malformada = pd.DataFrame(
        {
            col: pd.Series(dtype=dtype)
            for col, dtype in c.CONTRATO_COLUNAS_PRESENCA_AGREGADOR.items()
        }
    ).assign(coluna_intrusa=pd.Series(dtype="string"))

    out = calcular_score_vulnerabilidade(churn=churn_vazio, presenca=presenca_malformada)
    assert out.empty
    assert list(out.columns) == list(c.CONTRATO_COLUNAS_SCORE), "a SAÍDA vazia é validada"

    # Contraprova: a mesma presença malformada É rejeitada quando o churn não é vazio.
    with pytest.raises(ValueError, match="fora do contrato"):
        calcular_score_vulnerabilidade(
            churn=_churn([_linha_churn("k")]), presenca=presenca_malformada
        )


def test_v1_ausente_renormaliza_s1_para_fora_e_score_ainda_sai() -> None:
    """Hex sem par no sinal 1 continua pontuando pelo que sobrou — regime `{s3, s4}`."""
    churn = _churn(
        [
            _linha_churn(
                "k",
                hex_id=HEX_B,
                status="sumiu_recente",
                semanas_sem_mudanca=6,
                interpretavel=True,
                n_semanas_serie=13,
            )
        ]
    )
    out = calcular_score_vulnerabilidade(churn=churn, presenca=_presenca([_linha_presenca()]))
    linha = _linha_de(out, "k")
    assert _tokens(linha) == ["s3", "s4"]
    pesos = c.renormalizar_pesos(["s3", "s4"])
    esperado = 100.0 * (pesos["s3"] * 1.0 + pesos["s4"] * 0.5)
    assert float(linha["score_vulnerabilidade"]) == pytest.approx(esperado)
    assert float(linha["score_vulnerabilidade_ordenavel"]) == pytest.approx(esperado)


# --------------------------------------------------------------------------- #
# CA-8 — UNIVERSO: o teste que impede o falso alvo (achado A3)
# --------------------------------------------------------------------------- #
def test_cadeia_nunca_entra_no_score(serie_universo_misturado: list[pd.DataFrame]) -> None:
    """A fonte `unidades` é o feed de CADEIAS: nunca entra, nem com a `rede` forjada."""
    churn, presenca = _insumos(serie_universo_misturado)
    assert "unidades" in set(churn["fonte"].astype(str)), "o insumo PRECISA trazer a cadeia"
    out = calcular_score_vulnerabilidade(churn=churn, presenca=presenca)
    assert "k_un" not in set(out["chave_snapshot"].astype(str))
    assert set(out["fonte"].astype(str)) <= set(c.FONTES_AGREGADORES)
    assert set(out["rede"].astype(str)) == {c.CATEGORIA_INDEPENDENTE}


def test_marca_conhecida_no_totalpass_nunca_entra(
    serie_universo_misturado: list[pd.DataFrame],
) -> None:
    """Uma marca conhecida listada dentro do TotalPass não é independente frágil."""
    churn, presenca = _insumos(serie_universo_misturado)
    assert "k_marca" in set(churn["chave_snapshot"].astype(str))
    out = calcular_score_vulnerabilidade(churn=churn, presenca=presenca)
    assert "k_marca" not in set(out["chave_snapshot"].astype(str))
    assert set(out["chave_snapshot"].astype(str)) == {"k_tp", "k_wh"}


def test_assert_schema_rejeita_fonte_fora_do_universo() -> None:
    ruim = _saida_valida().copy()
    ruim.loc[_idx(ruim, "k_full"), "fonte"] = "unidades"
    with pytest.raises(ValueError, match="universo"):
        _assert_schema_score(ruim)


def test_assert_schema_rejeita_rede_fora_do_universo() -> None:
    ruim = _saida_valida().copy()
    ruim.loc[_idx(ruim, "k_full"), "rede"] = "smart_fit"
    with pytest.raises(ValueError, match="universo"):
        _assert_schema_score(ruim)


def test_reusa_filtro_de_universo_do_sinal_1() -> None:
    """O universo do sinal 1 e o universo de M&A são o MESMO conjunto: um predicado só."""
    assert m._filtrar_universo_sinal_1 is mpresenca._filtrar_universo_sinal_1


# --------------------------------------------------------------------------- #
# CA-9 — join entre granularidades e cardinalidade
# --------------------------------------------------------------------------- #
def test_join_many_to_one_preserva_cardinalidade(serie_madura_s3_s4: list[pd.DataFrame]) -> None:
    """Muitas academias por hex, um hex por linha de presença: o `len` não muda."""
    churn, presenca = _insumos(serie_madura_s3_s4)
    universo = m._preparar_universo(churn)
    out = calcular_score_vulnerabilidade(churn=churn, presenca=presenca)
    assert len(out) == len(universo) == 3
    assert len(presenca) == 2


def test_join_da_mesma_serie_nao_tem_left_only(serie_madura_s3_s4: list[pd.DataFrame]) -> None:
    """Invariância do INSUMO (não do tipo): os dois frames vindos da MESMA série sempre casam."""
    churn, presenca = _insumos(serie_madura_s3_s4)
    out = calcular_score_vulnerabilidade(churn=churn, presenca=presenca)
    assert not bool(out["n_agregadores_no_hex"].isna().any())
    assert not bool(out["v1"].isna().any())


def test_hex_sem_par_em_s1_produz_v1_nulo_e_score_calculado() -> None:
    """Frames de séries DIFERENTES: o miss não levanta, vira ausência auditável."""
    churn, _ = _insumos(_serie(13))
    _, presenca_outra = _insumos(
        [_snapshot(_semana(i), [_linha("k_outra", hex_id=HEX_A)]) for i in range(1, 4)]
    )
    out = calcular_score_vulnerabilidade(churn=churn, presenca=presenca_outra)
    sem_par = _linha_de(out, "k_tp_b")
    assert pd.isna(sem_par["v1"])
    assert "s1" not in _tokens(sem_par)
    assert not pd.isna(sem_par["score_vulnerabilidade"])


def test_join_rejeita_presenca_com_hex_duplicado() -> None:
    """O `validate="many_to_one"` levanta: dois hexes iguais no sinal 1 duplicariam academias."""
    churn = _churn([_linha_churn("k")])
    presenca = _presenca([_linha_presenca(), _linha_presenca()])
    universo = m._preparar_universo(churn)
    with pytest.raises(ValueError):
        m._juntar_presenca(universo, presenca)


# --------------------------------------------------------------------------- #
# CA-10 — não-propagação das colunas ressalvadas nos FU1 (achado A7)
# --------------------------------------------------------------------------- #
def test_saida_nao_tem_colunas_ressalvadas(serie_madura_s3_s4: list[pd.DataFrame]) -> None:
    churn, presenca = _insumos(serie_madura_s3_s4)
    assert "flag_troca_chave_na_serie" in set(churn.columns), "o insumo TEM a coluna"
    out = calcular_score_vulnerabilidade(churn=churn, presenca=presenca)
    assert not (set(out.columns) & m._COLUNAS_PROIBIDAS_RESSALVADAS)


@pytest.mark.parametrize(
    "coluna",
    [
        "flag_troca_chave_na_serie",
        "n_academias_independentes_totalpass",
        "n_academias_independentes_wellhub",
    ],
)
def test_assert_schema_rejeita_colunas_ressalvadas(coluna: str) -> None:
    """Se um bloco futuro quiser exibi-las, o teste quebra e os FU1 voltam a bloquear em voz alta."""
    ruim = _saida_valida().copy()
    ruim[coluna] = 1
    with pytest.raises(ValueError, match="ressalva"):
        _assert_schema_score(ruim)


def test_docstring_registra_por_que_as_colunas_ressalvadas_ficam_fora() -> None:
    doc = m.__doc__ or ""
    assert "flag_troca_chave_na_serie" in doc
    assert "n_academias_independentes" in doc
    assert "BLK-MA-02-FU1" in doc and "BLK-MA-03-FU1" in doc


# --------------------------------------------------------------------------- #
# CA-11 — contrato de 20 colunas e `_assert_schema_score`
# --------------------------------------------------------------------------- #
def test_schema_24_colunas_em_ordem_e_dtypes(serie_madura_s3_s4: list[pd.DataFrame]) -> None:
    churn, presenca = _insumos(serie_madura_s3_s4)
    out = calcular_score_vulnerabilidade(churn=churn, presenca=presenca)
    assert list(out.columns) == list(c.CONTRATO_COLUNAS_SCORE.keys())
    # 20 -> 22 no BLK-MA-09 / DEC-026 (dois FATOS de rating); 22 -> 24 no BLK-MA-12 (`v6` e a
    # pressao que o audita). Sem insumo de pressao, `v6` sai NULO e `n_sinais_disponiveis`
    # continua limitado a 3 — a chamada acima nao passa `pressao=`.
    assert len(list(out.columns)) == 24
    assert "v2" not in out.columns
    assert out["nota_wellhub"].dtype == "Float64"
    assert out["qtd_avaliacoes_wellhub"].dtype == "Int64"
    assert out["v6"].isna().all(), "sem insumo de pressao, o S6 nao existe na linha"
    assert int(out["n_sinais_disponiveis"].max()) <= 3
    assert (out["versao_contrato"] == c.VERSAO_CONTRATO_SCORE).all()
    # `Int64` NULÁVEL, não `int64`: a linha sem par no sinal 1 precisa carregar nulo.
    assert out["n_agregadores_no_hex"].dtype == "Int64"
    assert out["v1"].dtype == "float64"
    assert out["score_vulnerabilidade"].dtype == "float64"
    assert out["n_sinais_disponiveis"].dtype == "int64"
    assert out["flag_score_provisorio"].dtype == "bool"
    assert out["sinais_disponiveis"].dtype == "string"
    assert out["status_churn"].dtype == "string"


def test_frame_vazio_bem_formado_e_valido() -> None:
    vazio = m._frame_score_vazio()
    assert vazio.empty
    assert list(vazio.columns) == list(c.CONTRATO_COLUNAS_SCORE.keys())
    assert vazio["n_agregadores_no_hex"].dtype == "Int64"
    _assert_schema_score(vazio)


def test_assert_schema_rejeita_coluna_extra() -> None:
    ruim = _saida_valida().copy()
    ruim["extra"] = "x"
    with pytest.raises(ValueError, match="fora do contrato"):
        _assert_schema_score(ruim)


def test_assert_schema_rejeita_ordem_trocada() -> None:
    out = _saida_valida()
    ruim = out[list(reversed(list(out.columns)))]
    with pytest.raises(ValueError, match="ordem de colunas"):
        _assert_schema_score(ruim)


def test_assert_schema_rejeita_coluna_faltante() -> None:
    ruim = _saida_valida().drop(columns=["versao_contrato"])
    with pytest.raises(ValueError, match="ausentes"):
        _assert_schema_score(ruim)


def test_assert_schema_rejeita_identidade_invalida() -> None:
    """Hex fora de res-7, chave duplicada e `status_churn` fora do domínio."""
    fora_res7 = _saida_valida().copy()
    fora_res7.loc[0, "hex_id_res7"] = h3.latlng_to_cell(-23.55, -46.63, 8)
    with pytest.raises(ValueError, match="res-7"):
        _assert_schema_score(fora_res7)

    out = _saida_valida()
    duplicada = pd.concat([out, out.head(1)], ignore_index=True)
    with pytest.raises(ValueError, match="duplicada"):
        _assert_schema_score(duplicada)

    status_ruim = _saida_valida().copy()
    status_ruim.loc[0, "status_churn"] = "sumiu_ha_muito"
    with pytest.raises(ValueError, match="status_churn"):
        _assert_schema_score(status_ruim)


@pytest.mark.parametrize(
    ("coluna", "valor"),
    [("v1", 0.3), ("v3", 0.4), ("v4", 1.5), ("score_vulnerabilidade", 140.0)],
)
def test_assert_schema_rejeita_componente_fora_do_dominio(coluna: str, valor: float) -> None:
    ruim = _saida_valida().copy()
    ruim.loc[_idx(ruim, "k_full"), coluna] = valor
    with pytest.raises(ValueError, match="dominio"):
        _assert_schema_score(ruim)


def test_assert_schema_rejeita_sinais_disponiveis_malformado() -> None:
    """Token desconhecido, fora da ordem canônica, repetido ou de um sinal INATIVO."""
    for valor, padrao in (
        ("s1,s9", "desconhecido"),
        ("s3,s1", "ordem canonica"),
        ("s1,s1,s3", "repetido"),
        ("s1,s2,s3", "INATIVO"),
    ):
        ruim = _saida_valida().copy()
        ruim.loc[_idx(ruim, "k_full"), "sinais_disponiveis"] = valor
        with pytest.raises(ValueError, match=padrao):
            _assert_schema_score(ruim)


def test_assert_schema_rejeita_n_sinais_incoerente() -> None:
    ruim = _saida_valida().copy()
    ruim.loc[_idx(ruim, "k_full"), "n_sinais_disponiveis"] = 2
    with pytest.raises(ValueError, match="incoerente"):
        _assert_schema_score(ruim)


def test_assert_schema_rejeita_biconditional_sinal_componente() -> None:
    """Sinal listado como disponível com o componente nulo (ou o contrário) é incoerência."""
    ruim = _saida_valida().copy()
    ruim.loc[_idx(ruim, "k_full"), "v4"] = float("nan")
    with pytest.raises(ValueError, match="biconditional"):
        _assert_schema_score(ruim)


def test_assert_schema_rejeita_biconditional_do_join() -> None:
    ruim = _saida_valida().copy()
    ruim.loc[_idx(ruim, "k_full"), "n_agregadores_no_hex"] = pd.NA
    with pytest.raises(ValueError, match="biconditional do join"):
        _assert_schema_score(ruim)

    outro = _saida_valida().copy()
    outro.loc[_idx(outro, "k_sem_sinal"), "fontes_presentes_no_hex"] = "totalpass"
    with pytest.raises(ValueError, match="biconditional do join"):
        _assert_schema_score(outro)


def test_assert_schema_rejeita_score_zero_com_zero_sinais() -> None:
    """`0` afirma solidez; a linha sem sinal algum não afirmou nada."""
    ruim = _saida_valida().copy()
    ruim.loc[_idx(ruim, "k_sem_sinal"), "score_vulnerabilidade"] = 0.0
    with pytest.raises(ValueError, match="ausencia nunca e zero"):
        _assert_schema_score(ruim)

    outro = _saida_valida().copy()
    outro.loc[_idx(outro, "k_sem_sinal"), "score_vulnerabilidade"] = 42.0
    with pytest.raises(ValueError, match="NULO"):
        _assert_schema_score(outro)


def test_assert_schema_rejeita_flag_provisorio_incoerente() -> None:
    ruim = _saida_valida().copy()
    ruim.loc[_idx(ruim, "k_so_s1"), "flag_score_provisorio"] = False
    with pytest.raises(ValueError, match="flag_score_provisorio"):
        _assert_schema_score(ruim)


def test_assert_schema_rejeita_ordenavel_incoerente() -> None:
    """G-D1 executável: a coluna de ordenação é NULA exatamente no regime provisório."""
    ruim = _saida_valida().copy()
    ruim.loc[_idx(ruim, "k_so_s1"), "score_vulnerabilidade_ordenavel"] = 50.0
    with pytest.raises(ValueError, match="ordenavel"):
        _assert_schema_score(ruim)

    outro = _saida_valida().copy()
    outro.loc[_idx(outro, "k_full"), "score_vulnerabilidade_ordenavel"] = 1.0
    with pytest.raises(ValueError, match="ordenavel"):
        _assert_schema_score(outro)


def test_assert_schema_rejeita_versao_inesperada() -> None:
    ruim = _saida_valida().copy()
    ruim.loc[0, "versao_contrato"] = "score_vulnerabilidade_v9"
    with pytest.raises(ValueError, match="versao_contrato"):
        _assert_schema_score(ruim)


@pytest.mark.parametrize(
    "coluna",
    [
        "score_priorizacao",
        "hex_score_estrutural",
        "score_oficial",
        "renda_pct_nacional",
        "pop_pct_nacional",
    ],
)
def test_assert_schema_rejeita_coluna_do_m1(coluna: str) -> None:
    """READ-ONLY sobre o M1 tornado EXECUTÁVEL: o score é PARALELO, não é do M1."""
    ruim = _saida_valida().copy()
    ruim[coluna] = 1.0
    with pytest.raises(ValueError, match="M1"):
        _assert_schema_score(ruim)


@pytest.mark.parametrize(
    "coluna",
    [
        "sam_fitness_potencial",
        "score_oportunidade_residual",
        "hex_quente",
        "tese_entrada",
        "oferta_efetiva_disponivel",
    ],
)
def test_assert_schema_rejeita_coluna_do_bloco_seguinte(coluna: str) -> None:
    """Anti-vazamento de escopo: hotness e lista comercial são do bloco seguinte."""
    ruim = _saida_valida().copy()
    ruim[coluna] = 1.0
    with pytest.raises(ValueError, match="BLK-MA-05"):
        _assert_schema_score(ruim)


# --------------------------------------------------------------------------- #
# G-D2 — `status_churn` é FATO propagado, sem peso e fora do somatório
# --------------------------------------------------------------------------- #
def test_status_churn_e_fato_propagado_sem_peso() -> None:
    """Duas linhas com os MESMOS sinais disponíveis e status diferentes têm o mesmo score."""
    churn = _churn(
        [
            _linha_churn("k_novo", status="novo", imatura=True),
            _linha_churn("k_sumiu", status="sumiu_recente", imatura=True),
        ]
    )
    out = calcular_score_vulnerabilidade(churn=churn, presenca=_presenca([_linha_presenca()]))
    novo = _linha_de(out, "k_novo")
    sumiu = _linha_de(out, "k_sumiu")
    assert novo["status_churn"] == "novo" and sumiu["status_churn"] == "sumiu_recente"
    assert _tokens(novo) == _tokens(sumiu) == ["s1"]
    assert float(novo["score_vulnerabilidade"]) == float(sumiu["score_vulnerabilidade"])
    assert pd.isna(novo["v3"]) and pd.isna(sumiu["v3"])


# --------------------------------------------------------------------------- #
# CA-12 — pureza, zero I/O e independência de ordem
# --------------------------------------------------------------------------- #
def test_modulo_nao_escreve_em_disco() -> None:
    """Mesma classe do teste de percentil: **heurística por substring**, defesa secundária.

    Não pegaria `Path.write_text` nem um handle obtido por outro nome `[precisão BLK-MA-04-FU1]`.
    Prova que o módulo não ESCREVE pelas formas usuais — não prova que ele é livre de I/O: pelo
    modo `base_dir=` ele LÊ disco transitivamente, via extratores (ver docstring de `score.py`).
    """
    fonte = inspect.getsource(m)
    for proibido in ("to_" + "parquet", "to_" + "csv", "op" + "en(", "mk" + "dir", "escrever_"):
        assert proibido not in fonte, proibido


def test_funcao_nao_muta_os_frames_de_entrada(serie_madura_s3_s4: list[pd.DataFrame]) -> None:
    churn, presenca = _insumos(serie_madura_s3_s4)
    churn_antes = churn.copy(deep=True)
    presenca_antes = presenca.copy(deep=True)
    calcular_score_vulnerabilidade(churn=churn, presenca=presenca)
    assert_frame_equal(churn, churn_antes)
    assert_frame_equal(presenca, presenca_antes)


def test_resultado_independe_da_ordem_das_linhas_de_entrada(
    serie_madura_s3_s4: list[pd.DataFrame],
) -> None:
    churn, presenca = _insumos(serie_madura_s3_s4)
    direto = calcular_score_vulnerabilidade(churn=churn, presenca=presenca)
    embaralhado = calcular_score_vulnerabilidade(
        churn=churn.iloc[::-1].reset_index(drop=True),
        presenca=presenca.iloc[::-1].reset_index(drop=True),
    )
    assert_frame_equal(direto, embaralhado)


def test_exige_base_dir_ou_o_par_de_frames(tmp_path: Path) -> None:
    """Três formas inválidas de chamar, uma mensagem só."""
    churn = _churn([_linha_churn("k")])
    presenca = _presenca([_linha_presenca()])
    with pytest.raises(ValueError, match="base_dir"):
        calcular_score_vulnerabilidade()
    with pytest.raises(ValueError, match="base_dir"):
        calcular_score_vulnerabilidade(churn=churn)
    with pytest.raises(ValueError, match="base_dir"):
        calcular_score_vulnerabilidade(tmp_path, churn=churn, presenca=presenca)


def test_insumo_vazio_devolve_frame_vazio_bem_formado() -> None:
    vazio_churn = _churn([])
    out = calcular_score_vulnerabilidade(churn=vazio_churn, presenca=_presenca([]))
    assert out.empty
    assert list(out.columns) == list(c.CONTRATO_COLUNAS_SCORE.keys())

    so_cadeia = _churn([_linha_churn("k_un", fonte="unidades", rede="smart_fit")])
    fora = calcular_score_vulnerabilidade(churn=so_cadeia, presenca=_presenca([]))
    assert fora.empty
    assert list(fora.columns) == list(c.CONTRATO_COLUNAS_SCORE.keys())


# --------------------------------------------------------------------------- #
# CA-13 — isolamento de import (a tupla compartilhada NÃO proíbe `demanda_revelada`)
# --------------------------------------------------------------------------- #
def test_modulo_nao_importa_demanda_revelada() -> None:
    from .._ast_imports import nomes_importados

    for n in nomes_importados(m):
        assert "demanda_revelada" not in n, n


# --------------------------------------------------------------------------- #
# CA-14 — anti-PII (DEC-012)
# --------------------------------------------------------------------------- #
def test_saida_sem_coluna_de_pii(serie_madura_s3_s4: list[pd.DataFrame]) -> None:
    churn, presenca = _insumos(serie_madura_s3_s4)
    out = calcular_score_vulnerabilidade(churn=churn, presenca=presenca)
    assert not (set(out.columns) & c.COLUNAS_PII_PROIBIDAS)
    assert set(out.columns) == set(c.CONTRATO_COLUNAS_SCORE.keys())


# --------------------------------------------------------------------------- #
# BLK-MA-09 / DEC-026 — o rating é FATO, não sinal
# --------------------------------------------------------------------------- #
def test_rating_chega_ao_score_com_valor_e_sem_virar_sinal(
    serie_madura_s3_s4: list[pd.DataFrame],
) -> None:
    """Prova de ponta a ponta: snapshot -> churn -> score, com o valor intacto e SEM peso.

    O ponto do bloco inteiro. Se o rating aparecesse em `sinais_disponiveis`, ele entraria em
    `Σ(wi · vi)` e o score mudaria — que é exatamente o que a DEC-026 recusou, porque
    `score_com_s2 = 0,75 · score_sem_s2 + 25 · v2` penalizaria 99,97% das linhas com nota.
    """
    serie = [s.copy() for s in serie_madura_s3_s4]
    for semana in serie:
        wh = semana["fonte"] == "wellhub"
        semana.loc[wh, "nota_wellhub"] = 4.25
        semana.loc[wh, "qtd_avaliacoes_wellhub"] = 88

    churn, presenca = _insumos(serie)
    out = calcular_score_vulnerabilidade(churn=churn, presenca=presenca)
    wh = out[out["fonte"] == "wellhub"]
    assert not wh.empty, "fixture sem linha de wellhub — o teste não provaria nada"

    # 1. O valor CHEGOU (e não apenas a coluna).
    assert wh["nota_wellhub"].notna().all()
    assert (wh["nota_wellhub"] == 4.25).all()
    # `notna()` primeiro, pelo mesmo motivo da linha acima: `.all()` de serie toda-NA da True.
    assert wh["qtd_avaliacoes_wellhub"].notna().all()
    assert (wh["qtd_avaliacoes_wellhub"] == 88).all()

    # 2. E NÃO virou sinal.
    assert all("s2" not in str(s).split(",") for s in out["sinais_disponiveis"])
    assert int(out["n_sinais_disponiveis"].max()) <= 3
    assert c.SINAIS_INATIVOS == ("s2",)


def test_rating_nao_altera_o_score(serie_madura_s3_s4: list[pd.DataFrame]) -> None:
    """O score tem de ser BIT A BIT o mesmo com e sem nota — é o que "sem peso" significa.

    Sem esta trava, uma futura entrada acidental do rating em `Σ(wi · vi)` passaria despercebida:
    as colunas continuariam lá, os schemas continuariam válidos, e só o ranking mudaria.
    """
    sem_nota = [s.copy() for s in serie_madura_s3_s4]
    com_nota = [s.copy() for s in serie_madura_s3_s4]
    for semana in com_nota:
        wh = semana["fonte"] == "wellhub"
        semana.loc[wh, "nota_wellhub"] = 1.0  # pior nota possível: máximo estrago se tivesse peso
        semana.loc[wh, "qtd_avaliacoes_wellhub"] = 4200

    churn_a, presenca_a = _insumos(sem_nota)
    churn_b, presenca_b = _insumos(com_nota)
    a = calcular_score_vulnerabilidade(churn=churn_a, presenca=presenca_a)
    b = calcular_score_vulnerabilidade(churn=churn_b, presenca=presenca_b)
    pd.testing.assert_series_equal(
        a["score_vulnerabilidade"], b["score_vulnerabilidade"], check_names=False
    )
    pd.testing.assert_series_equal(
        a["sinais_disponiveis"], b["sinais_disponiveis"], check_names=False
    )
