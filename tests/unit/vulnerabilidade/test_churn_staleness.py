"""BLK-MA-02: testes do extrator de churn (sinal 3) e staleness (sinal 4).

Todas as fixtures são SINTÉTICAS e injetadas por `snapshots=[...]` -- zero I/O, salvo o
round-trip explicito que grava e rele partições em `tmp_path`.

Os dois testes que mais importam são os de GAP: se uma semana em que o feed não rodou virasse
"desaparecimento", o sinal de maior peso do score (S3 ~= 0,467) encheria de falso churn. O escopo
de observabilidade e o par `(fonte, rede)` -- e não só a `fonte` -- porque o feed de cadeias e um
arquivo por rede.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import h3
import pandas as pd
import pytest

from motor_expansao.vulnerabilidade import contrato as c
from motor_expansao.vulnerabilidade import snapshots as m
from motor_expansao.vulnerabilidade.churn_staleness import extrair_churn_staleness

HEX = h3.latlng_to_cell(-23.5500, -46.6300, 7)


# --------------------------------------------------------------------------- #
# Helpers de fixture sintetica
# --------------------------------------------------------------------------- #
def _linha(
    chave: str,
    *,
    fonte: str = "unidades",
    rede: str = "smart_fit",
    hex_id: str = HEX,
    hash_: str = "h0",
    chave_origem: str = "hash_estavel",
    snapshot_date: str = "2026-01-05",
    nota: float | None = None,
    qtd: int | None = None,
) -> dict[str, object]:
    return {
        "snapshot_date": snapshot_date,
        "slug": None,
        "concorrente_id": "0" * 40,
        "chave_snapshot": chave,
        "chave_origem": chave_origem,
        "hex_id_res7": hex_id,
        "rede": rede,
        "fonte": fonte,
        "hash_campos_raspados": hash_,
        # Colunas-fato do rating (DEC-026). Default `None` -> o estado "não lido", que e o
        # correto para as fontes que não são WellHub.
        "nota_wellhub": nota,
        "qtd_avaliacoes_wellhub": qtd,
        "versao_contrato": c.VERSAO_CONTRATO_SNAPSHOT,
    }


def _snapshot(semana: str, linhas: list[dict[str, object]]) -> pd.DataFrame:
    df = pd.DataFrame(linhas, columns=list(c.CONTRATO_COLUNAS_SNAPSHOT.keys()))
    df["semana"] = semana
    return df


def _semana(i: int) -> str:
    return f"2026-{i:02d}"


def _linha_de(df: pd.DataFrame, chave: str) -> pd.Series:
    recorte = df[df["chave_snapshot"] == chave]
    assert len(recorte) == 1, f"chave {chave} deveria ter exatamente 1 linha"
    return recorte.iloc[0]


# --------------------------------------------------------------------------- #
# Fixtures multi-semana
# --------------------------------------------------------------------------- #
@pytest.fixture
def serie_10_semanas() -> list[pd.DataFrame]:
    """10 semanas, 1 escopo. 4 chaves cobrindo os 4 estados de churn."""
    snaps: list[pd.DataFrame] = []
    for i in range(1, 11):
        linhas = [_linha("k_estavel")]
        if i != 4:
            linhas.append(_linha("k_piscando"))
        if i != 10:
            linhas.append(_linha("k_sumiu"))
        if i >= 9:
            linhas.append(_linha("k_novo"))
        snaps.append(_snapshot(_semana(i), linhas))
    return snaps


@pytest.fixture
def gap_de_fonte() -> list[pd.DataFrame]:
    """4 semanas: a fonte `totalpass` não foi observada na semana 3 (o coletor não rodou)."""
    snaps: list[pd.DataFrame] = []
    for i in range(1, 5):
        linhas = [_linha("k_un", fonte="unidades", rede="smart_fit")]
        if i != 3:
            linhas.append(_linha("k_tp", fonte="totalpass", rede="independente"))
        snaps.append(_snapshot(_semana(i), linhas))
    return snaps


@pytest.fixture
def gap_de_rede() -> list[pd.DataFrame]:
    """4 semanas, tudo na fonte `unidades`: só o CSV da rede `selfit` faltou na semana 3."""
    snaps: list[pd.DataFrame] = []
    for i in range(1, 5):
        linhas = [_linha("k_sf", rede="smart_fit")]
        if i != 3:
            linhas.append(_linha("k_selfit", rede="selfit"))
        snaps.append(_snapshot(_semana(i), linhas))
    return snaps


@pytest.fixture
def reset_de_hash() -> list[pd.DataFrame]:
    """10 semanas, 1 chave: o cadastro mudou na semana 6."""
    return [
        _snapshot(_semana(i), [_linha("k", hash_="hA" if i <= 5 else "hB")])
        for i in range(1, 11)
    ]


@pytest.fixture
def regimes_maturidade() -> list[pd.DataFrame]:
    """3 escopos independentes com series de 4, 9 e 13 semanas observadas."""
    snaps: list[pd.DataFrame] = []
    for i in range(1, 14):
        linhas: list[dict[str, object]] = []
        if i <= 4:
            linhas.append(_linha("k_4", rede="rede_a"))
        if i <= 9:
            linhas.append(_linha("k_9", rede="rede_b"))
        linhas.append(_linha("k_13", rede="rede_c"))
        snaps.append(_snapshot(_semana(i), linhas))
    return snaps


@pytest.fixture
def troca_de_chave() -> list[pd.DataFrame]:
    """6 semanas no MESMO escopo: a politica de chave virou de `slug` para `hash_estavel`."""
    snaps: list[pd.DataFrame] = []
    for i in range(1, 7):
        if i <= 3:
            linhas = [_linha("k_antiga", chave_origem="slug")]
        else:
            linhas = [_linha("k_nova", chave_origem="hash_estavel")]
        snaps.append(_snapshot(_semana(i), linhas))
    return snaps


# --------------------------------------------------------------------------- #
# CA-8 — os 4 estados de churn
# --------------------------------------------------------------------------- #
def test_quatro_estados_de_churn(serie_10_semanas: list[pd.DataFrame]) -> None:
    out = extrair_churn_staleness(snapshots=serie_10_semanas)
    assert len(out) == 4

    estavel = _linha_de(out, "k_estavel")
    assert estavel["status_churn"] == "estavel"
    assert int(estavel["n_semanas_serie"]) == 10
    assert int(estavel["n_desaparecimentos"]) == 0
    assert bool(estavel["flag_serie_imatura"]) is False

    piscando = _linha_de(out, "k_piscando")
    assert piscando["status_churn"] == "piscando"
    assert int(piscando["n_desaparecimentos"]) >= 1
    assert int(piscando["n_semanas_presente"]) == 9

    sumiu = _linha_de(out, "k_sumiu")
    assert sumiu["status_churn"] == "sumiu_recente"
    assert sumiu["semana_ultima_observacao"] == "2026-09"

    novo = _linha_de(out, "k_novo")
    assert novo["status_churn"] == "novo"
    assert int(novo["n_semanas_serie"]) == 2
    assert bool(novo["flag_serie_imatura"]) is True
    assert novo["semana_primeira_observacao"] == "2026-09"


def test_novo_equivale_a_presente_sem_sumico_com_serie_imatura(
    serie_10_semanas: list[pd.DataFrame],
) -> None:
    """`novo` reusa MIN_SEMANAS: e consistente por construcao, sem constante magica nova."""
    out = extrair_churn_staleness(snapshots=serie_10_semanas)
    for _, linha in out.iterrows():
        if linha["status_churn"] == "novo":
            assert int(linha["n_desaparecimentos"]) == 0
            assert bool(linha["flag_serie_imatura"]) is True


# --------------------------------------------------------------------------- #
# CA-9 / CA-9b — gap de feed NÃO vira churn
# --------------------------------------------------------------------------- #
def test_gap_de_fonte_nao_vira_churn(gap_de_fonte: list[pd.DataFrame]) -> None:
    """A semana em que a fonte não foi observada não entra no eixo -> não gera transicao."""
    out = extrair_churn_staleness(snapshots=gap_de_fonte)
    tp = _linha_de(out, "k_tp")
    assert tp["status_churn"] != "sumiu_recente"
    assert int(tp["n_desaparecimentos"]) == 0
    assert int(tp["n_semanas_serie"]) == 3
    assert int(tp["n_semanas_presente"]) == 3


def test_gap_de_rede_dentro_da_fonte_nao_vira_churn(gap_de_rede: list[pd.DataFrame]) -> None:
    """P2: o feed de cadeias e um CSV por REDE -- gap por `(fonte, rede)`, não só por `fonte`."""
    out = extrair_churn_staleness(snapshots=gap_de_rede)
    selfit = _linha_de(out, "k_selfit")
    assert int(selfit["n_desaparecimentos"]) == 0, (
        "a fonte `unidades` tinha linhas na semana 3 (da outra rede), mas o escopo da selfit nao"
    )
    assert selfit["status_churn"] != "sumiu_recente"
    assert int(selfit["n_semanas_serie"]) == 3
    # A rede que foi observada nas 4 semanas mantém a série completa.
    assert int(_linha_de(out, "k_sf")["n_semanas_serie"]) == 4


def test_fonte_ausente_na_ultima_semana_da_base_nao_e_sumiu_recente() -> None:
    """`w_last` e a última semana observada DO ESCOPO, nunca a última semana da base."""
    snaps = [
        _snapshot(_semana(1), [_linha("k_tp", fonte="totalpass"), _linha("k_un")]),
        _snapshot(_semana(2), [_linha("k_tp", fonte="totalpass"), _linha("k_un")]),
        _snapshot(_semana(3), [_linha("k_un")]),  # `totalpass` em gap na ULTIMA semana da base
    ]
    out = extrair_churn_staleness(snapshots=snaps)
    tp = _linha_de(out, "k_tp")
    assert tp["status_churn"] != "sumiu_recente"
    assert int(tp["n_semanas_serie"]) == 2
    assert tp["semana_ultima_observacao"] == "2026-02"


# --------------------------------------------------------------------------- #
# CA-10 — staleness
# --------------------------------------------------------------------------- #
def test_semanas_sem_mudanca_reseta_no_meio(reset_de_hash: list[pd.DataFrame]) -> None:
    out = extrair_churn_staleness(snapshots=reset_de_hash)
    assert int(_linha_de(out, "k")["semanas_sem_mudanca"]) == 4


def test_semanas_sem_mudanca_sem_alteracao(serie_10_semanas: list[pd.DataFrame]) -> None:
    out = extrair_churn_staleness(snapshots=serie_10_semanas)
    assert int(_linha_de(out, "k_estavel")["semanas_sem_mudanca"]) == 9


def test_semanas_sem_mudanca_conta_observacoes_nao_calendario(
    gap_de_fonte: list[pd.DataFrame],
) -> None:
    """3 observações com hash fixo (semanas 1, 2 e 4) -> 2, não 3."""
    out = extrair_churn_staleness(snapshots=gap_de_fonte)
    assert int(_linha_de(out, "k_tp")["semanas_sem_mudanca"]) == 2


def test_flags_maturidade_tres_regimes(regimes_maturidade: list[pd.DataFrame]) -> None:
    out = extrair_churn_staleness(snapshots=regimes_maturidade)
    esperado = {"k_4": (4, True, False), "k_9": (9, False, False), "k_13": (13, False, True)}
    for chave, (n, imatura, interpretavel) in esperado.items():
        linha = _linha_de(out, chave)
        assert int(linha["n_semanas_serie"]) == n, chave
        assert bool(linha["flag_serie_imatura"]) is imatura, chave
        assert bool(linha["flag_staleness_interpretavel"]) is interpretavel, chave


def test_snapshot_date_ultimo_detecta_csv_estagnado() -> None:
    """R10: coletor falho mantém o CSV antigo -> presenca normal, mas `snapshot_date` congelado."""
    snaps = [
        _snapshot(_semana(i), [_linha("k", snapshot_date="2026-01-02")]) for i in range(1, 4)
    ]
    out = extrair_churn_staleness(snapshots=snaps)
    linha = _linha_de(out, "k")
    assert linha["snapshot_date_ultimo"] == "2026-01-02"
    assert linha["semana_ultima_observacao"] == "2026-03"


# --------------------------------------------------------------------------- #
# D7 — troca de politica de chave na série
# --------------------------------------------------------------------------- #
def test_flag_troca_chave_na_serie(troca_de_chave: list[pd.DataFrame]) -> None:
    """O extrator DETECTA e sinaliza; o reparo (se houver) e BLK-MA-04."""
    out = extrair_churn_staleness(snapshots=troca_de_chave)
    assert bool(out["flag_troca_chave_na_serie"].all())
    assert _linha_de(out, "k_antiga")["status_churn"] == "sumiu_recente"
    assert _linha_de(out, "k_nova")["status_churn"] == "novo"


def test_sem_troca_de_chave_a_flag_fica_falsa(serie_10_semanas: list[pd.DataFrame]) -> None:
    out = extrair_churn_staleness(snapshots=serie_10_semanas)
    assert not bool(out["flag_troca_chave_na_serie"].any())


def test_flag_troca_nao_liga_com_mistura_estavel_de_origens() -> None:
    """Sonda do QA do BLK-MA-02, reproduzida: mistura ESTÁVEL não é troca.

    Quatro semanas, mesmo escopo `(fonte, rede)`, uma chave sempre `slug` e outra sempre
    `hash_estavel` — **zero** troca temporal. A fórmula antiga (`|{chave_origem do escopo}|
    > 1`) marcava as duas como `True`.

    Por que isso importa: no feed TP/WH o rebaixamento de chave ocorre **por linha** e
    convive com o `slug` na mesma semana, então a flag antiga valeria `True` para todo o
    universo, todo mês — um sinal morto entregue ao consumidor do score.
    """
    snaps = [
        _snapshot(
            _semana(i),
            [
                _linha("k_slug", chave_origem="slug"),
                _linha("k_hash", chave_origem="hash_estavel"),
            ],
        )
        for i in range(1, 5)
    ]
    out = extrair_churn_staleness(snapshots=snaps)
    assert not bool(out["flag_troca_chave_na_serie"].any()), out[
        ["chave_snapshot", "chave_origem", "flag_troca_chave_na_serie"]
    ]


def test_flag_troca_liga_quando_a_politica_muda_entre_semanas() -> None:
    """O contraponto do teste acima: variação TEMPORAL do escopo liga a flag.

    Mesma chave, mesmo escopo, mas o escopo inteiro migra de `slug` (semanas 1-2) para
    `hash_estavel` (semanas 3-4). É este o evento que a flag promete sinalizar.
    """
    snaps = [
        _snapshot(
            _semana(i),
            [_linha("k_unica", chave_origem="slug" if i <= 2 else "hash_estavel")],
        )
        for i in range(1, 5)
    ]
    out = extrair_churn_staleness(snapshots=snaps)
    assert bool(out["flag_troca_chave_na_serie"].all())


# --------------------------------------------------------------------------- #
# CA-18 — o extrator NÃO pontua
# --------------------------------------------------------------------------- #
def test_extrator_nao_produz_score(serie_10_semanas: list[pd.DataFrame]) -> None:
    out = extrair_churn_staleness(snapshots=serie_10_semanas)
    proibidas = {"v3", "v4", "score_vulnerabilidade", "n_sinais_disponiveis", "flag_score_provisorio"}
    assert not (set(out.columns) & proibidas)


def test_assert_schema_churn_falha_se_alguem_adiantar_o_score(
    serie_10_semanas: list[pd.DataFrame],
) -> None:
    from motor_expansao.vulnerabilidade.churn_staleness import _assert_schema_churn

    out = extrair_churn_staleness(snapshots=serie_10_semanas)
    ruim = out.copy()
    ruim["score_vulnerabilidade"] = 50.0
    with pytest.raises(ValueError, match="SCORE"):
        _assert_schema_churn(ruim)


# --------------------------------------------------------------------------- #
# Contrato / bordas
# --------------------------------------------------------------------------- #
def test_schema_churn_19_colunas_em_ordem(serie_10_semanas: list[pd.DataFrame]) -> None:
    out = extrair_churn_staleness(snapshots=serie_10_semanas)
    assert list(out.columns) == list(c.CONTRATO_COLUNAS_CHURN.keys())
    # 17 -> 19 no BLK-MA-09 / DEC-026: os dois fatos de rating, da ULTIMA observacao.
    assert len(list(out.columns)) == 19
    assert (out["versao_contrato"] == c.VERSAO_CONTRATO_CHURN).all()
    assert set(out["status_churn"]) <= set(c.STATUS_CHURN_VALIDOS)
    assert out["n_semanas_serie"].dtype == "int64"
    assert out["flag_serie_imatura"].dtype == "bool"


def test_extrator_exige_base_dir_xor_snapshots(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="exatamente um"):
        extrair_churn_staleness()
    with pytest.raises(ValueError, match="exatamente um"):
        extrair_churn_staleness(base_dir=tmp_path, snapshots=[])


def test_extrator_base_vazia_frame_vazio_bem_formado(tmp_path: Path) -> None:
    out = extrair_churn_staleness(base_dir=tmp_path / "nao_existe")
    assert out.empty
    assert list(out.columns) == list(c.CONTRATO_COLUNAS_CHURN.keys())
    assert extrair_churn_staleness(snapshots=[]).empty


def test_serie_exige_semana_iso_e_chave_unica() -> None:
    sem_semana = _snapshot(_semana(1), [_linha("k")]).drop(columns=["semana"])
    with pytest.raises(ValueError, match="semana"):
        extrair_churn_staleness(snapshots=[sem_semana])

    ruim = _snapshot("2026-1", [_linha("k")])
    with pytest.raises(ValueError, match="ISO"):
        extrair_churn_staleness(snapshots=[ruim])

    duplicada = _snapshot(_semana(1), [_linha("k"), _linha("k")])
    with pytest.raises(ValueError, match="duplicada"):
        extrair_churn_staleness(snapshots=[duplicada])


def test_mesma_academia_em_duas_fontes_sao_duas_linhas() -> None:
    """A `fonte` faz parte da chave: sair de um agregador e ficar no outro E o sinal 1."""
    snaps = [
        _snapshot(
            _semana(i),
            [
                _linha("k", fonte="totalpass", rede="independente"),
                _linha("k", fonte="wellhub", rede="independente"),
            ],
        )
        for i in range(1, 4)
    ]
    out = extrair_churn_staleness(snapshots=snaps)
    assert len(out) == 2
    assert set(out["fonte"]) == {"totalpass", "wellhub"}


def test_min_semanas_e_stale_semanas_sao_parametros_injetaveis(
    serie_10_semanas: list[pd.DataFrame],
) -> None:
    """Os defaults vem do contrato (gate 2026-07-23) e NÃO são alterados por este bloco."""
    assert c.MIN_SEMANAS == 8
    assert c.STALE_SEMANAS == 12
    assert c.RETENCAO_SEMANAS == 26
    out = extrair_churn_staleness(snapshots=serie_10_semanas, min_semanas=3, stale_semanas=5)
    assert bool(_linha_de(out, "k_novo")["flag_serie_imatura"]) is True  # 2 < 3
    assert bool(_linha_de(out, "k_estavel")["flag_staleness_interpretavel"]) is True  # 10 >= 5


# --------------------------------------------------------------------------- #
# Round-trip real: materializar -> partição no disco -> extrair
# --------------------------------------------------------------------------- #
def test_roundtrip_materializar_e_extrair(tmp_path: Path) -> None:
    """Prova o hive read e que `semana` volta como string, ponta a ponta."""
    un = tmp_path / "un"
    un.mkdir(parents=True, exist_ok=True)
    vazio = tmp_path / "vazio"
    vazio.mkdir()
    base = tmp_path / "snapshots"
    referencias = [date(2026, 1, 5), date(2026, 1, 12), date(2026, 1, 19)]
    for i, ref in enumerate(referencias):
        nomes = ["Alfa", "Beta"] if i < 2 else ["Alfa"]  # a Beta some na 3a semana
        pd.DataFrame(
            {
                "nome_unidade": nomes,
                "latitude": [-23.5500, -23.9000][: len(nomes)],
                "longitude": [-46.6300, -46.9000][: len(nomes)],
                "data_coleta": [ref.isoformat()] * len(nomes),
            }
        ).to_csv(un / "unidades_selfit.csv", sep=";", encoding="utf-8-sig", index=False)
        m.materializar(vazio, vazio, un, base_dir=base, data_referencia=ref)

    serie = m.ler_snapshots(base)
    assert set(serie["semana"]) == {"2026-02", "2026-03", "2026-04"}
    assert serie["semana"].map(type).eq(str).all()

    out = extrair_churn_staleness(base_dir=base)
    assert len(out) == 2
    assert set(out["status_churn"]) == {"novo", "sumiu_recente"}
    assert (out["rede"] == "selfit").all()


def test_rating_vem_da_ULTIMA_observacao_presente() -> None:
    """A única decisão de design do rating neste módulo, e ela não tinha teste.

    Sonda de mutação provou o buraco: trocar `última[...]` por `bloco.iloc[0][...]` (a PRIMEIRA
    observação, o oposto exato do que o comentário promete) deixava a suíte inteira verde, porque
    as fixtures repetem a mesma nota em todas as semanas.

    "Última PRESENTE" e não "última da série": a academia some na semana 3 e volta na 4 com nota
    nova. É o cenário real — no smoke do BLK-MA-08 uma unidade saiu de `4,81`/`105` para
    `4,76`/`97` entre coletas.
    """
    notas = [3.0, 3.5, None, 4.9]  # semana 3: ausente
    frames = []
    for i, nota in enumerate(notas, start=1):
        if nota is None:
            # Semana observada para o escopo, mas SEM está chave -> ausência real, não gap.
            frames.append(_snapshot(f"2026-0{i}", [_linha("outra", nota=1.0, qtd=1)]))
            continue
        frames.append(
            _snapshot(
                f"2026-0{i}",
                [
                    _linha("alvo", nota=nota, qtd=int(nota * 10)),
                    _linha("outra", nota=1.0, qtd=1),
                ],
            )
        )

    out = extrair_churn_staleness(snapshots=frames)
    alvo = out[out["chave_snapshot"] == "alvo"].iloc[0]

    assert alvo["nota_wellhub"] == 4.9, "pegou uma observação que não é a última presente"
    assert alvo["qtd_avaliacoes_wellhub"] == 49
    assert alvo["semana_ultima_observacao"] == "2026-04"
