"""BLK-MA-15: a variante NOMEADA (D1-B) — score com identidade e coordenada.

Este é o ÚNICO módulo do pacote que junta identidade e score, e por isso os testes aqui são
majoritariamente sobre fronteira, não sobre aritmética. O que eles protegem:

  * **`test_destino_fora_de_staging_levanta`** — o artefato tem de nascer gitignored. A pasta de
    saída (a irmã de `staging`) é só PARCIALMENTE versionada, e um caminho errado ali poria nome e
    coordenada de 19 mil estabelecimentos no histórico do git, onde `git rm` não os apaga.
  * **`test_academia_sem_coordenada_entra_sem_pin`** — ela tem score; sumir com ela esconderia um
    alvo por acidente de coleta.
  * **`test_cadeia_do_feed_nao_entra`** — o universo de M&A exclui cadeias, e o join tem de
    preservar isso: sem essa garantia a Smart Fit ganharia pin de "alvo de aquisição".

Fixtures 100% sintéticas: nomes e coordenadas são inventados, nenhum teste lê `data/`.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from motor_expansao.vulnerabilidade import alvos_nomeados as m
from motor_expansao.vulnerabilidade import contrato as c
from motor_expansao.vulnerabilidade.score import calcular_score_vulnerabilidade

from .test_score import (
    HEX_A,
    _churn,
    _linha_churn,
    _linha_presenca,
    _presenca,
)


def _score(chaves: list[str]) -> pd.DataFrame:
    return calcular_score_vulnerabilidade(
        churn=_churn(
            [
                _linha_churn(k, hex_id=HEX_A, n_semanas_serie=13, interpretavel=True)
                for k in chaves
            ]
        ),
        presenca=_presenca([_linha_presenca(HEX_A)]),
    )


def _coordenadas(nomes: dict[str, str], *, sem_coord: tuple[str, ...] = ()) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "fonte": "totalpass",
                "chave_snapshot": chave,
                "nome": nome,
                "lat": None if chave in sem_coord else -23.55,
                "lng": None if chave in sem_coord else -46.63,
            }
            for chave, nome in nomes.items()
        ],
        # Colunas declaradas mesmo na lista vazia: `DataFrame([])` sai SEM coluna nenhuma, o que
        # nao e' o frame que `coordenadas_por_chave` produz.
        columns=["fonte", "chave_snapshot", "nome", "lat", "lng"],
    )


# --------------------------------------------------------------------------- #
# O join
# --------------------------------------------------------------------------- #
def test_identidade_e_score_chegam_na_mesma_linha() -> None:
    """O ponto do módulo: o nome de uma ponta, o score da outra."""
    out = m.montar_alvos_nomeados(_score(["k1"]), _coordenadas({"k1": "Academia do Bairro"}))
    assert len(out) == 1
    linha = out.iloc[0]
    assert str(linha["nome"]) == "Academia do Bairro"
    assert not pd.isna(linha["score_vulnerabilidade"]), "o score existe (pode ser 0,0)"
    assert float(linha["lat"]) == pytest.approx(-23.55)


def test_academia_sem_coordenada_entra_sem_pin() -> None:
    """Ela TEM score. Sumir com ela esconderia um alvo por acidente de coleta."""
    out = m.montar_alvos_nomeados(
        _score(["k1", "k2"]),
        _coordenadas({"k1": "Com Pin", "k2": "Sem Pin"}, sem_coord=("k2",)),
    )
    assert len(out) == 2
    sem = out[out["nome"] == "Sem Pin"].iloc[0]
    assert pd.isna(sem["lat"]) and pd.isna(sem["lng"])
    assert not pd.isna(sem["score_vulnerabilidade"]), "sem pin, mas COM score"


def test_academia_do_feed_fora_do_score_nao_entra() -> None:
    """O SCORE é o lado que sobrevive ao join.

    Uma linha no feed sem par no score é, tipicamente, uma CADEIA — que o universo de M&A exclui de
    propósito. Deixá-la entrar daria pin de "alvo de aquisição" para a Smart Fit, que é o erro mais
    caro do epic.
    """
    coord = _coordenadas({"k1": "Independente", "k_cadeia": "Smart Fit Paulista"})
    out = m.montar_alvos_nomeados(_score(["k1"]), coord)
    assert set(out["nome"]) == {"Independente"}


def test_coordenada_duplicada_no_feed_nao_duplica_a_academia() -> None:
    """O join é `1:1`; duplicata à direita multiplicaria a linha do score."""
    coord = pd.concat([_coordenadas({"k1": "A"}), _coordenadas({"k1": "A"})], ignore_index=True)
    out = m.montar_alvos_nomeados(_score(["k1"]), coord)
    assert len(out) == 1


def test_score_vazio_produz_saida_vazia_bem_formada() -> None:
    vazio = m.montar_alvos_nomeados(_score([]).head(0), _coordenadas({}))
    assert list(vazio.columns) == list(c.CONTRATO_COLUNAS_ALVOS_NOMEADOS)
    assert vazio.empty


# --------------------------------------------------------------------------- #
# Fronteira: onde o artefato pode nascer, e o que ele não pode carregar
# --------------------------------------------------------------------------- #
def test_destino_fora_de_staging_levanta(tmp_path: Path) -> None:
    """A pasta de saída é PARCIALMENTE versionada — identidade não pode ir para lá."""
    fora = tmp_path / "outputs" / "nomeadas.parquet"
    with pytest.raises(ValueError, match="staging"):
        m.materializar_alvos_nomeados(
            _score(["k1"]), _coordenadas({"k1": "A"}), saida=fora
        )
    assert not fora.exists(), "nada pode ter sido gravado antes do guard"


def test_grava_sob_staging_e_sobrevive_a_releitura(tmp_path: Path) -> None:
    destino = tmp_path / "staging" / "nomeadas.parquet"
    auditoria = m.materializar_alvos_nomeados(
        _score(["k1", "k2"]),
        _coordenadas({"k1": "A", "k2": "B"}, sem_coord=("k2",)),
        saida=destino,
    )
    lido = pd.read_parquet(destino)
    assert list(lido.columns) == list(c.CONTRATO_COLUNAS_ALVOS_NOMEADOS)
    assert int(auditoria["academias_nomeadas"]) == 2
    assert int(auditoria["com_coordenada"]) == 1
    assert int(auditoria["sem_coordenada"]) == 1


def test_campo_vedado_pelo_paragrafo_11_levanta() -> None:
    """Autorizar identidade de ESTABELECIMENTO não abre a porta para dado de PESSOA."""
    out = m.montar_alvos_nomeados(_score(["k1"]), _coordenadas({"k1": "A"}))
    ruim = out.copy()
    ruim["autor_review"] = "fulano"
    with pytest.raises(AssertionError, match="§11|vedado"):
        m._assert_schema_nomeados(ruim)


def test_dry_run_nao_grava(tmp_path: Path) -> None:
    destino = tmp_path / "staging" / "nomeadas.parquet"
    m.materializar_alvos_nomeados(
        _score(["k1"]), _coordenadas({"k1": "A"}), saida=destino, dry_run=True
    )
    assert not destino.exists()


def test_frame_de_coordenadas_sem_nome_levanta() -> None:
    coord = _coordenadas({"k1": "A"}).drop(columns=["nome"])
    with pytest.raises(AssertionError, match="nome"):
        m.montar_alvos_nomeados(_score(["k1"]), coord)


def test_modulo_nao_importa_demanda_revelada() -> None:
    from .._ast_imports import nomes_importados

    for n in nomes_importados(m):
        assert "demanda_revelada" not in n, n
