"""BLK-MA-03: testes do sinal 1 (presença em agregador TotalPass/WellHub), hex-level.

Todas as fixtures são SINTÉTICAS e injetadas por `snapshots=[...]` — zero I/O, salvo o round-trip
explícito que grava e relê partições em `tmp_path`. Nenhum teste lê a fonte real (ela é gitignored,
vive na VPS e carrega PII na origem, DEC-012).

Os testes que mais importam são os dois pares que travam a ORDEM do algoritmo:

  * **P1** — a redução para a observação mais recente ordena por `semana`, JAMAIS por
    `snapshot_date`. Coletor que falha mantém o arquivo bruto anterior, então o `snapshot_date`
    congela ou até REGRIDE enquanto a `semana` avança; ordenar por ele escolheria a observação
    errada (aqui, o hex antigo de uma academia recolocada).
  * **P2** — reduzir ANTES de filtrar. Uma chave classificada como independente na semana 1 e como
    marca conhecida na semana 3 sobreviveria pela observação velha se o filtro viesse primeiro, e
    entraria como falso alvo de M&A.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import h3
import pandas as pd
import pytest

from motor_expansao.vulnerabilidade import churn_staleness as mchurn
from motor_expansao.vulnerabilidade import contrato as c
from motor_expansao.vulnerabilidade import presenca_agregador as m
from motor_expansao.vulnerabilidade import snapshots as msnap
from motor_expansao.vulnerabilidade.presenca_agregador import extrair_presenca_agregador

HEX_A = h3.latlng_to_cell(-23.5500, -46.6300, 7)  # São Paulo
HEX_B = h3.latlng_to_cell(-22.9100, -43.1800, 7)  # Rio de Janeiro


# --------------------------------------------------------------------------- #
# Helpers de fixture sintética
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
        # `[BLK-MA-21]` O recorte que a execucao pediu. Constante nas fixtures: o que
        # varia nos testes desta camada e a serie, nao o recorte.
        "fontes_lidas": "totalpass,wellhub",
        "versao_contrato": c.VERSAO_CONTRATO_SNAPSHOT,
    }


def _snapshot(semana: str, linhas: list[dict[str, object]]) -> pd.DataFrame:
    df = pd.DataFrame(linhas, columns=list(c.CONTRATO_COLUNAS_SNAPSHOT.keys()))
    df["semana"] = semana
    return df


def _semana(i: int) -> str:
    return f"2026-{i:02d}"


def _hex_de(df: pd.DataFrame, hex_id: str) -> pd.Series:
    recorte = df[df["hex_id_res7"] == hex_id]
    assert len(recorte) == 1, f"o hex {hex_id} deveria ter exatamente 1 linha"
    return recorte.iloc[0]


# --------------------------------------------------------------------------- #
# Fixtures multi-semana / multi-fonte
# --------------------------------------------------------------------------- #
@pytest.fixture
def universo_misturado() -> list[pd.DataFrame]:
    """1 semana com uma linha por CLASSE: só o par TP+WH independente em `HEX_A` conta."""
    return [
        _snapshot(
            _semana(1),
            [
                # (a) feed de CADEIAS com a `rede` forjada como independente -> fora do universo
                _linha("k_un", fonte="unidades", rede="independente", hex_id=HEX_B),
                # (b) marca conhecida DENTRO do TotalPass -> fora do universo
                _linha("k_marca", fonte="totalpass", rede="smart_fit", hex_id=HEX_B),
                # (c) + (d) genuinamente independentes, nos dois agregadores
                _linha("k_tp", fonte="totalpass", hex_id=HEX_A),
                _linha("k_wh", fonte="wellhub", hex_id=HEX_A),
            ],
        )
    ]


@pytest.fixture
def serie_3_semanas_duas_fontes() -> list[pd.DataFrame]:
    """3 semanas; a mesma chave TP e a mesma chave WH em `HEX_A` nas três."""
    return [
        _snapshot(
            _semana(i),
            [
                _linha("k_tp", fonte="totalpass", snapshot_date=f"2026-01-{5 + 7 * (i - 1):02d}"),
                _linha("k_wh", fonte="wellhub", snapshot_date=f"2026-01-{5 + 7 * (i - 1):02d}"),
            ],
        )
        for i in range(1, 4)
    ]


@pytest.fixture
def recolocacao() -> list[pd.DataFrame]:
    """3 semanas; a chave TP muda de `HEX_A` (semanas 1-2) para `HEX_B` (semana 3)."""
    return [
        _snapshot(_semana(i), [_linha("k_tp", hex_id=HEX_A if i < 3 else HEX_B)])
        for i in range(1, 4)
    ]


@pytest.fixture
def snapshot_date_congelado() -> list[pd.DataFrame]:
    """P1: o coletor serviu o MESMO arquivo nas 3 semanas -> `snapshot_date` idêntico."""
    return [
        _snapshot(
            _semana(i),
            [_linha("k_tp", hex_id=HEX_A if i < 3 else HEX_B, snapshot_date="2026-01-05")],
        )
        for i in range(1, 4)
    ]


@pytest.fixture
def snapshot_date_regressivo() -> list[pd.DataFrame]:
    """P1 (caso pior): a `semana` avança enquanto o `snapshot_date` REGRIDE."""
    datas = ["2026-01-20", "2026-01-27", "2026-01-06"]
    return [
        _snapshot(
            _semana(i),
            [
                _linha(
                    "k_tp",
                    hex_id=HEX_A if i < 3 else HEX_B,
                    snapshot_date=datas[i - 1],
                )
            ],
        )
        for i in range(1, 4)
    ]


@pytest.fixture
def reclassificacao_de_rede() -> list[pd.DataFrame]:
    """P2: independente nas semanas 1-2, marca conhecida na semana 3."""
    return [
        _snapshot(_semana(i), [_linha("k_tp", rede="independente" if i < 3 else "smart_fit")])
        for i in range(1, 4)
    ]


@pytest.fixture
def reclassificacao_espelhada() -> list[pd.DataFrame]:
    """P2 (espelho): marca conhecida nas semanas 1-2, independente na semana 3."""
    return [
        _snapshot(_semana(i), [_linha("k_tp", rede="smart_fit" if i < 3 else "independente")])
        for i in range(1, 4)
    ]


@pytest.fixture
def gap_de_fonte() -> list[pd.DataFrame]:
    """R3: o TotalPass só foi observado na semana 1; o WellHub, nas três. Mesmo hex."""
    snaps: list[pd.DataFrame] = []
    for i in range(1, 4):
        linhas = [_linha("k_wh", fonte="wellhub", snapshot_date=f"2026-01-{5 + 7 * (i - 1):02d}")]
        if i == 1:
            linhas.append(_linha("k_tp", fonte="totalpass", snapshot_date="2026-01-05"))
        snaps.append(_snapshot(_semana(i), linhas))
    return snaps


def _saida_valida() -> pd.DataFrame:
    """Frame de saída bem-formado (1 hex, 2 agregadores), base dos testes de `_assert_schema`."""
    snaps = [
        _snapshot(
            _semana(i),
            [_linha("k_tp", fonte="totalpass"), _linha("k_wh", fonte="wellhub")],
        )
        for i in range(1, 4)
    ]
    return extrair_presenca_agregador(snapshots=snaps)


# --------------------------------------------------------------------------- #
# CA-1 — universo do sinal 1 (TP/WH x independente)
# --------------------------------------------------------------------------- #
def test_universo_exclui_unidades_mesmo_com_rede_forjada(
    universo_misturado: list[pd.DataFrame],
) -> None:
    """A fonte `unidades` é o feed de CADEIAS: nunca entra, nem com a `rede` forjada."""
    out = extrair_presenca_agregador(snapshots=universo_misturado)
    assert HEX_B not in set(out["hex_id_res7"])
    assert len(out) == 1


def test_universo_exclui_tp_wh_com_marca_conhecida(
    universo_misturado: list[pd.DataFrame],
) -> None:
    """Uma marca conhecida listada dentro do TotalPass não é independente frágil."""
    out = extrair_presenca_agregador(snapshots=universo_misturado)
    linha = _hex_de(out, HEX_A)
    assert int(linha["n_academias_independentes_totalpass"]) == 1
    assert int(linha["n_academias_independentes_wellhub"]) == 1
    assert int(linha["n_agregadores_no_hex"]) == 2


def test_hex_so_com_linhas_excluidas_nao_emite_linha(
    universo_misturado: list[pd.DataFrame],
) -> None:
    out = extrair_presenca_agregador(snapshots=universo_misturado)
    assert set(out["hex_id_res7"]) == {HEX_A}


# --------------------------------------------------------------------------- #
# CA-2 — contagem de CHAVES distintas, nunca de linhas
# --------------------------------------------------------------------------- #
def test_conta_chaves_distintas_nao_linhas(
    serie_3_semanas_duas_fontes: list[pd.DataFrame],
) -> None:
    """A mesma chave observada em 3 semanas é UMA academia, não três."""
    out = extrair_presenca_agregador(snapshots=serie_3_semanas_duas_fontes)
    linha = _hex_de(out, HEX_A)
    assert int(linha["n_academias_independentes_totalpass"]) == 1
    assert int(linha["n_academias_independentes_wellhub"]) == 1


def test_duas_chaves_no_mesmo_hex_contam_duas() -> None:
    snaps = [
        _snapshot(
            _semana(1),
            [
                _linha("k_tp_1", fonte="totalpass"),
                _linha("k_tp_2", fonte="totalpass"),
            ],
        )
    ]
    out = extrair_presenca_agregador(snapshots=snaps)
    linha = _hex_de(out, HEX_A)
    assert int(linha["n_academias_independentes_totalpass"]) == 2
    assert int(linha["n_agregadores_no_hex"]) == 1
    assert linha["fontes_presentes_no_hex"] == "totalpass"


# --------------------------------------------------------------------------- #
# CA-3 / CA-3b — redução para a observação mais recente, ordenada por `semana`
# --------------------------------------------------------------------------- #
def test_recolocacao_conta_so_no_hex_mais_recente(recolocacao: list[pd.DataFrame]) -> None:
    """Academia recolocada não pode contar nos DOIS hexes; o hex antigo some da saída."""
    out = extrair_presenca_agregador(snapshots=recolocacao)
    assert set(out["hex_id_res7"]) == {HEX_B}
    assert int(_hex_de(out, HEX_B)["n_academias_independentes_totalpass"]) == 1


def test_reducao_ordena_por_semana_com_snapshot_date_congelado(
    snapshot_date_congelado: list[pd.DataFrame],
) -> None:
    """Com o `snapshot_date` idêntico nas 3 semanas, só a `semana` desempata."""
    out = extrair_presenca_agregador(snapshots=snapshot_date_congelado)
    assert set(out["hex_id_res7"]) == {HEX_B}
    linha = _hex_de(out, HEX_B)
    assert linha["semana_ultima_observacao_totalpass"] == "2026-03"
    assert linha["snapshot_date_ultimo_totalpass"] == "2026-01-05"


def test_reducao_ordena_por_semana_com_snapshot_date_regressivo(
    snapshot_date_regressivo: list[pd.DataFrame],
) -> None:
    """Ordenar por `snapshot_date` escolheria a semana 2 (data maior) e o hex ERRADO."""
    out = extrair_presenca_agregador(snapshots=snapshot_date_regressivo)
    assert set(out["hex_id_res7"]) == {HEX_B}
    linha = _hex_de(out, HEX_B)
    assert linha["semana_ultima_observacao_totalpass"] == "2026-03"
    assert linha["snapshot_date_ultimo_totalpass"] == "2026-01-06"


# --------------------------------------------------------------------------- #
# CA-3c — reduzir ANTES de filtrar
# --------------------------------------------------------------------------- #
def test_reclassificacao_para_marca_conhecida_exclui_a_chave(
    reclassificacao_de_rede: list[pd.DataFrame],
) -> None:
    """A classificação MAIS RECENTE vence: filtrar antes manteria um falso alvo de M&A."""
    out = extrair_presenca_agregador(snapshots=reclassificacao_de_rede)
    assert out.empty
    assert list(out.columns) == list(c.CONTRATO_COLUNAS_PRESENCA_AGREGADOR.keys())


def test_reclassificacao_para_independente_inclui_a_chave(
    reclassificacao_espelhada: list[pd.DataFrame],
) -> None:
    out = extrair_presenca_agregador(snapshots=reclassificacao_espelhada)
    assert int(_hex_de(out, HEX_A)["n_academias_independentes_totalpass"]) == 1


# --------------------------------------------------------------------------- #
# CA-4 — contrato de 10 colunas travado
# --------------------------------------------------------------------------- #
def test_schema_10_colunas_em_ordem_e_dtypes(
    serie_3_semanas_duas_fontes: list[pd.DataFrame],
) -> None:
    out = extrair_presenca_agregador(snapshots=serie_3_semanas_duas_fontes)
    assert list(out.columns) == list(c.CONTRATO_COLUNAS_PRESENCA_AGREGADOR.keys())
    assert len(list(out.columns)) == 10
    assert (out["versao_contrato"] == c.VERSAO_CONTRATO_PRESENCA_AGREGADOR).all()
    assert out["n_agregadores_no_hex"].dtype == "int64"
    assert out["n_academias_independentes_totalpass"].dtype == "int64"
    assert out["hex_id_res7"].dtype == "string"
    assert out["semana_ultima_observacao_wellhub"].dtype == "string"


def test_assert_schema_rejeita_coluna_extra() -> None:
    ruim = _saida_valida().copy()
    ruim["extra"] = "x"
    with pytest.raises(ValueError, match="fora do contrato"):
        m._assert_schema_presenca_agregador(ruim)


def test_assert_schema_rejeita_ordem_trocada() -> None:
    out = _saida_valida()
    ruim = out[list(reversed(list(out.columns)))]
    with pytest.raises(ValueError, match="ordem de colunas"):
        m._assert_schema_presenca_agregador(ruim)


def test_assert_schema_rejeita_coluna_faltante() -> None:
    ruim = _saida_valida().drop(columns=["versao_contrato"])
    with pytest.raises(ValueError, match="ausentes"):
        m._assert_schema_presenca_agregador(ruim)


def test_assert_schema_rejeita_hex_fora_res7() -> None:
    ruim = _saida_valida().copy()
    ruim.loc[0, "hex_id_res7"] = h3.latlng_to_cell(-23.55, -46.63, 8)
    with pytest.raises(ValueError, match="res-7"):
        m._assert_schema_presenca_agregador(ruim)


def test_assert_schema_rejeita_hex_duplicado() -> None:
    out = _saida_valida()
    ruim = pd.concat([out, out.head(1)], ignore_index=True)
    with pytest.raises(ValueError, match="duplicado"):
        m._assert_schema_presenca_agregador(ruim)


def test_assert_schema_rejeita_n_agregadores_fora_do_dominio() -> None:
    ruim = _saida_valida().copy()
    ruim.loc[0, "n_agregadores_no_hex"] = 3
    with pytest.raises(ValueError, match="dominio"):
        m._assert_schema_presenca_agregador(ruim)


def test_assert_schema_rejeita_fontes_presentes_inconsistente_com_a_contagem() -> None:
    ruim = _saida_valida().copy()
    ruim.loc[0, "fontes_presentes_no_hex"] = "wellhub"  # a contagem diz que o TP também está lá
    with pytest.raises(ValueError, match="inconsistente"):
        m._assert_schema_presenca_agregador(ruim)


def test_assert_schema_rejeita_fontes_presentes_nula() -> None:
    """O `fillna("")` da comparação é o que impede o `pd.NA` de passar em SILÊNCIO.

    Sem ele a comparação mascarada do pandas devolve `0` divergências para uma linha cujo
    `fontes_presentes_no_hex` é nulo — ou seja, a checagem inteira passaria com a coluna vazia. O
    teste irmão acima usa `"wellhub"` (um valor PRESENTE e errado) e não cobre este caminho:
    medido em 2026-08-12, `(esperado != atual).sum()` dá `0` sem o `fillna` e `1` com ele.
    """
    ruim = _saida_valida().copy()
    ruim.loc[0, "fontes_presentes_no_hex"] = pd.NA
    assert pd.isna(ruim.loc[0, "fontes_presentes_no_hex"]), "a fixture precisa mesmo ficar nula"
    with pytest.raises(ValueError, match="inconsistente"):
        m._assert_schema_presenca_agregador(ruim)


def test_assert_schema_rejeita_nulabilidade_inconsistente() -> None:
    """Os dois relógios são nulos SE E SOMENTE SE a contagem daquela fonte for 0."""
    ruim = _saida_valida().copy()
    ruim.loc[0, "semana_ultima_observacao_wellhub"] = pd.NA
    with pytest.raises(ValueError, match="se e somente se"):
        m._assert_schema_presenca_agregador(ruim)


def test_assert_schema_rejeita_versao_inesperada() -> None:
    ruim = _saida_valida().copy()
    ruim.loc[0, "versao_contrato"] = "presenca_agregador_v9"
    with pytest.raises(ValueError, match="versao_contrato"):
        m._assert_schema_presenca_agregador(ruim)


def test_assert_schema_rejeita_semana_fora_do_formato_iso() -> None:
    ruim = _saida_valida().copy()
    ruim.loc[0, "semana_ultima_observacao_totalpass"] = "2026-1"
    with pytest.raises(ValueError, match="ISO"):
        m._assert_schema_presenca_agregador(ruim)


# --------------------------------------------------------------------------- #
# CA-5 — trava executável contra score adiantado (BLK-MA-04 / BLK-MA-08)
# --------------------------------------------------------------------------- #
def test_extrator_nao_produz_score(serie_3_semanas_duas_fontes: list[pd.DataFrame]) -> None:
    out = extrair_presenca_agregador(snapshots=serie_3_semanas_duas_fontes)
    proibidas = {
        "v1",
        "v2",
        "score_vulnerabilidade",
        "n_sinais_disponiveis",
        "flag_score_provisorio",
    }
    assert not (set(out.columns) & proibidas)


@pytest.mark.parametrize(
    "coluna",
    ["v1", "v2", "score_vulnerabilidade", "n_sinais_disponiveis", "flag_score_provisorio"],
)
def test_assert_schema_falha_se_alguem_adiantar_o_score(coluna: str) -> None:
    ruim = _saida_valida().copy()
    ruim[coluna] = 0.5
    with pytest.raises(ValueError, match="SCORE"):
        m._assert_schema_presenca_agregador(ruim)


# --------------------------------------------------------------------------- #
# CA-6 — limite estrutural do "0 agregadores": documentado, não é bug
# --------------------------------------------------------------------------- #
def test_n_agregadores_no_hex_nunca_e_zero(universo_misturado: list[pd.DataFrame]) -> None:
    out = extrair_presenca_agregador(snapshots=universo_misturado)
    assert set(int(v) for v in out["n_agregadores_no_hex"]) <= {1, 2}
    assert not bool((out["n_agregadores_no_hex"] == 0).any())


def test_hex_sem_observacao_nao_emite_linha(universo_misturado: list[pd.DataFrame]) -> None:
    """Fontes só-positivas: hex sem alvo observado não tem o que pontuar."""
    out = extrair_presenca_agregador(snapshots=universo_misturado)
    assert HEX_B not in set(out["hex_id_res7"])


def test_docstring_registra_o_limite_do_zero_agregadores() -> None:
    doc = m.__doc__ or ""
    assert "0 agregadores" in doc
    assert "sinal 3" in doc, "o docstring precisa apontar onde o caso informativo vive"


# --------------------------------------------------------------------------- #
# CA-6b — segundo limite: as colunas 4/5 super-contam sob rotação de chave
# --------------------------------------------------------------------------- #
def test_rotacao_de_chave_super_conta_as_colunas_4_5() -> None:
    """UMA academia, duas encarnações de chave -> `n_academias_independentes_totalpass = 2`.

    Congela o limite do `BLK-MA-03-FU1` (Item 1). A redução dedupla por
    `(fonte, chave_snapshot)`, e o rebaixamento de `chave_origem` (`slug` -> `hash_estavel`)
    TROCA a chave: as duas encarnações sobrevivem como duas linhas e a contagem infla.

    As duas asserções que importam são de sinais opostos, e é essa combinação que define o
    limite: a contagem INFLA (é TETO, não número exato) enquanto `n_agregadores_no_hex` — o
    insumo real do `v1` — fica INTACTO em `1`, e por isso o score do BLK-MA-04 não é afetado.
    Se um bloco futuro deduplicar por academia, este teste quebra e a decisão fica explícita.
    """
    serie = [
        _snapshot(_semana(1), [_linha("k_slug", chave_origem="slug")]),
        _snapshot(_semana(2), [_linha("k_slug", chave_origem="slug")]),
        # A MESMA academia, agora sob a chave de fallback (rebaixamento auditável do contrato).
        _snapshot(_semana(3), [_linha("k_hash", chave_origem="hash_estavel")]),
        _snapshot(_semana(4), [_linha("k_hash", chave_origem="hash_estavel")]),
    ]
    linha = _hex_de(extrair_presenca_agregador(snapshots=serie), HEX_A)

    assert int(linha["n_academias_independentes_totalpass"]) == 2, "o limite: super-contagem"
    assert int(linha["n_agregadores_no_hex"]) == 1, "o `v1` NÃO pode ser contaminado"
    assert str(linha["fontes_presentes_no_hex"]) == "totalpass"


def test_docstring_registra_o_limite_da_rotacao_de_chave() -> None:
    """O limite acima só é aceitável enquanto estiver ESCRITO onde o consumidor lê."""
    doc = m.__doc__ or ""
    assert "SUPER-CONTAM" in doc
    assert "TETO" in doc, "o docstring precisa dizer como LER as colunas 4/5"
    assert "flag_troca_chave_na_serie" in doc, "e apontar o detector do modo de falha"
    comentario = inspect.getsource(c)
    assert "TETO" in comentario, "o comentário das colunas 4/5 em `contrato.py` também carrega"


# --------------------------------------------------------------------------- #
# CA-9 — constante replicada, sem import de `demanda_revelada`
# --------------------------------------------------------------------------- #
def test_modulo_nao_importa_demanda_revelada() -> None:
    """A tupla compartilhada de `test_isolamento_imports` NÃO proíbe isto — e não poderia."""
    from .._ast_imports import nomes_importados

    for n in nomes_importados(m):
        assert "demanda_revelada" not in n, n


def test_categoria_independente_replicada_bate_com_a_origem() -> None:
    """Só o TESTE importa a origem; o módulo replica o valor e é travado contra drift aqui."""
    from motor_expansao.demanda_revelada.classificacao_rede_menor import (
        CATEGORIA_INDEPENDENTE as origem,
    )

    assert c.CATEGORIA_INDEPENDENTE == origem


# --------------------------------------------------------------------------- #
# CA-8 — zero PII / zero releitura de arquivo bruto
# --------------------------------------------------------------------------- #
def test_saida_sem_coluna_de_pii(serie_3_semanas_duas_fontes: list[pd.DataFrame]) -> None:
    out = extrair_presenca_agregador(snapshots=serie_3_semanas_duas_fontes)
    assert not (set(out.columns) & c.COLUNAS_PII_PROIBIDAS)
    assert set(out.columns) == set(c.CONTRATO_COLUNAS_PRESENCA_AGREGADOR.keys())


def test_modulo_nao_le_csv_cru() -> None:
    """O módulo consome só a série já materializada — nunca o feed bruto nem o classificador."""
    fonte = inspect.getsource(m)
    for proibido in (
        "ler_" + "feeds",
        "_ler_" + "csv_bruto",
        "read_" + "csv",
        "classificar_" + "rede",
        "grid_" + "disk",
    ):
        assert proibido not in fonte, proibido


# --------------------------------------------------------------------------- #
# CA-11 — delegação de I/O e reuso, não reimplementação
# --------------------------------------------------------------------------- #
def test_extrator_exige_base_dir_xor_snapshots(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="exatamente um"):
        extrair_presenca_agregador()
    with pytest.raises(ValueError, match="exatamente um"):
        extrair_presenca_agregador(base_dir=tmp_path, snapshots=[])


def test_reusa_montar_serie_longa_do_churn() -> None:
    """A validação da série é UMA só: duplicá-la criaria dois lugares para divergir."""
    assert m._montar_serie_longa is mchurn._montar_serie_longa


def test_base_vazia_frame_vazio_bem_formado(tmp_path: Path) -> None:
    out = extrair_presenca_agregador(base_dir=tmp_path / "nao_existe")
    assert out.empty
    assert list(out.columns) == list(c.CONTRATO_COLUNAS_PRESENCA_AGREGADOR.keys())
    assert extrair_presenca_agregador(snapshots=[]).empty


def test_roundtrip_particoes_no_disco(tmp_path: Path) -> None:
    """Grava 3 semanas em `tmp_path` e lê por `base_dir=`: prova a delegação do I/O."""
    base = tmp_path / "snapshots_sinteticos"
    for i in range(1, 4):
        snap = _snapshot(
            _semana(i),
            [_linha("k_tp", fonte="totalpass"), _linha("k_wh", fonte="wellhub")],
        )
        msnap.escrever_particao_semana(snap, base, semana=_semana(i))

    out = extrair_presenca_agregador(base_dir=base)
    linha = _hex_de(out, HEX_A)
    assert int(linha["n_agregadores_no_hex"]) == 2
    assert linha["fontes_presentes_no_hex"] == "totalpass,wellhub"
    assert linha["semana_ultima_observacao_totalpass"] == "2026-03"


# --------------------------------------------------------------------------- #
# CA-12 — os dois relógios de frescor por fonte (gap de feed, R3)
# --------------------------------------------------------------------------- #
def test_gap_de_fonte_nao_apaga_cobertura(gap_de_fonte: list[pd.DataFrame]) -> None:
    """A janela não é encurtada: a fonte em gap não perde a cobertura que já provou."""
    out = extrair_presenca_agregador(snapshots=gap_de_fonte)
    linha = _hex_de(out, HEX_A)
    assert int(linha["n_agregadores_no_hex"]) == 2
    assert linha["semana_ultima_observacao_totalpass"] == "2026-01"
    assert linha["semana_ultima_observacao_wellhub"] == "2026-03"
    assert linha["snapshot_date_ultimo_totalpass"] == "2026-01-05"
    assert linha["snapshot_date_ultimo_wellhub"] == "2026-01-19"


def test_frescor_nulo_sse_contagem_zero() -> None:
    """Hex coberto só pelo WellHub: os relógios do TotalPass saem nulos, e só eles."""
    snaps = [_snapshot(_semana(1), [_linha("k_wh", fonte="wellhub")])]
    out = extrair_presenca_agregador(snapshots=snaps)
    linha = _hex_de(out, HEX_A)
    assert int(linha["n_academias_independentes_totalpass"]) == 0
    assert pd.isna(linha["semana_ultima_observacao_totalpass"])
    assert pd.isna(linha["snapshot_date_ultimo_totalpass"])
    assert not pd.isna(linha["semana_ultima_observacao_wellhub"])
    assert not pd.isna(linha["snapshot_date_ultimo_wellhub"])
    assert linha["fontes_presentes_no_hex"] == "wellhub"


def test_snapshot_date_ultimo_e_o_da_ultima_semana_da_fonte() -> None:
    """O relógio do COLETOR sai da ÚLTIMA semana observada, não do máximo da série toda."""
    snaps = [
        _snapshot(
            _semana(1),
            [
                _linha("k_tp_1", fonte="totalpass", snapshot_date="2026-01-30"),
                _linha("k_tp_2", fonte="totalpass", snapshot_date="2026-01-05"),
            ],
        ),
        _snapshot(_semana(2), [_linha("k_tp_2", fonte="totalpass", snapshot_date="2026-01-12")]),
    ]
    out = extrair_presenca_agregador(snapshots=snaps)
    linha = _hex_de(out, HEX_A)
    assert int(linha["n_academias_independentes_totalpass"]) == 2
    assert linha["semana_ultima_observacao_totalpass"] == "2026-02"
    assert linha["snapshot_date_ultimo_totalpass"] == "2026-01-12"


# --------------------------------------------------------------------------- #
# Ordem canônica da string e bordas herdadas da série
# --------------------------------------------------------------------------- #
def test_fontes_presentes_em_ordem_canonica() -> None:
    """A string itera `FONTES_AGREGADORES`, nunca um `set`: a ordem é determinística."""
    snaps = [
        _snapshot(
            _semana(1),
            [_linha("k_wh", fonte="wellhub"), _linha("k_tp", fonte="totalpass")],
        )
    ]
    out = extrair_presenca_agregador(snapshots=snaps)
    assert _hex_de(out, HEX_A)["fontes_presentes_no_hex"] == "totalpass,wellhub"


def test_serie_exige_semana_iso_e_chave_unica() -> None:
    """Bordas herdadas de `_montar_serie_longa` — a validação da série é reusada, não recriada."""
    sem_semana = _snapshot(_semana(1), [_linha("k_tp")]).drop(columns=["semana"])
    with pytest.raises(ValueError, match="semana"):
        extrair_presenca_agregador(snapshots=[sem_semana])

    fora_do_iso = _snapshot("2026-1", [_linha("k_tp")])
    with pytest.raises(ValueError, match="ISO"):
        extrair_presenca_agregador(snapshots=[fora_do_iso])

    duplicada = _snapshot(_semana(1), [_linha("k_tp"), _linha("k_tp")])
    with pytest.raises(ValueError, match="duplicada"):
        extrair_presenca_agregador(snapshots=[duplicada])
