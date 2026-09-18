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
# `[DEC-064]` Fixtures MULTI-FONTE, para a coluna `fontes_da_academia`.
#
# O `_coordenadas` acima crava `fonte="totalpass"` e poe tudo na MESMA coordenada — com isso todo
# par sairia a 0 m e o raio de 100 m nunca seria exercitado. Estes irmaos existem por isso; alterar
# o compartilhado perturbaria os testes que ja' dependem da forma dele.
# --------------------------------------------------------------------------- #
_LAT_BASE, _LNG_BASE = -23.55, -46.63
_DELTA_PERTO = 0.0005   # ~55 m: DENTRO do raio
_DELTA_LONGE = 0.0015   # ~167 m: FORA do raio


def _score_multi(pares: list[tuple[str, str]]) -> pd.DataFrame:
    """Score com linhas de fontes DIFERENTES. `pares` = `[(chave, fonte)]`."""
    return calcular_score_vulnerabilidade(
        churn=_churn(
            [
                _linha_churn(k, fonte=f, hex_id=HEX_A, n_semanas_serie=13, interpretavel=True)
                for k, f in pares
            ]
        ),
        presenca=_presenca([_linha_presenca(HEX_A)]),
    )


def _coord_multi(linhas: list[tuple[str, str, str, float | None]]) -> pd.DataFrame:
    """`linhas` = `[(fonte, chave, nome, delta_lat)]`. `delta_lat=None` -> sem coordenada."""
    return pd.DataFrame(
        [
            {
                "fonte": fonte,
                "chave_snapshot": chave,
                "nome": nome,
                "lat": None if delta is None else _LAT_BASE + delta,
                "lng": None if delta is None else _LNG_BASE,
            }
            for fonte, chave, nome, delta in linhas
        ],
        columns=["fonte", "chave_snapshot", "nome", "lat", "lng"],
    )


def _fontes_de(df: pd.DataFrame, chave: str) -> object:
    recorte = df[df["chave_snapshot"] == chave]
    assert len(recorte) == 1, f"a chave {chave} deveria ter exatamente 1 linha"
    return recorte.iloc[0]["fontes_da_academia"]


def test_par_entre_apps_perto_e_com_nome_que_casa_vira_ambos() -> None:
    """A promessa da coluna: as DUAS linhas passam a declarar as duas fontes."""
    out = m.montar_alvos_nomeados(
        _score_multi([("k_tp", "totalpass"), ("k_wh", "wellhub")]),
        _coord_multi([
            ("totalpass", "k_tp", "Academia Alfa", 0.0),
            ("wellhub", "k_wh", "Academia Alfa", _DELTA_PERTO),
        ]),
    )
    assert str(_fontes_de(out, "k_tp")) == "totalpass,wellhub"
    assert str(_fontes_de(out, "k_wh")) == "totalpass,wellhub"


def test_par_perto_com_nome_que_NAO_casa_fica_cada_um_na_sua_fonte() -> None:
    """A regua escolhida e' `100 m E nome`, nao `OU`: perto sem nome nao basta."""
    out = m.montar_alvos_nomeados(
        _score_multi([("k_tp", "totalpass"), ("k_wh", "wellhub")]),
        _coord_multi([
            ("totalpass", "k_tp", "Academia Alfa", 0.0),
            ("wellhub", "k_wh", "Studio Beta Pilates", _DELTA_PERTO),
        ]),
    )
    assert str(_fontes_de(out, "k_tp")) == "totalpass"
    assert str(_fontes_de(out, "k_wh")) == "wellhub"


def test_par_com_nome_que_casa_mas_LONGE_nao_vira_ambos() -> None:
    """O raio MORDE — e este teste e' o que protege o bucket H3.

    Um `k` sub-dimensionado nao levanta erro: ele devolve "nenhum casamento", que e' exatamente o
    que um raio correto devolve quando nao ha' par. O defeito so' aparece com um caso que DEVERIA
    casar por nome e nao deve casar por distancia.
    """
    out = m.montar_alvos_nomeados(
        _score_multi([("k_tp", "totalpass"), ("k_wh", "wellhub")]),
        _coord_multi([
            ("totalpass", "k_tp", "Academia Alfa", 0.0),
            ("wellhub", "k_wh", "Academia Alfa", _DELTA_LONGE),
        ]),
    )
    assert str(_fontes_de(out, "k_tp")) == "totalpass"
    assert str(_fontes_de(out, "k_wh")) == "wellhub"


def test_com_uma_fonte_so_cada_linha_sai_com_a_propria_fonte() -> None:
    """O degrade de `--fontes wellhub`, que sai DE GRACA — e de graca e' onde ninguem olha.

    `coordenadas_por_chave(fontes=...)` ja' recortou a montante, entao nao existe par entre fontes
    e nenhum caso especial e' preciso. Sem este teste, quebrar isso passaria em silencio.
    """
    out = m.montar_alvos_nomeados(
        _score_multi([("k1", "wellhub"), ("k2", "wellhub")]),
        _coord_multi([
            ("wellhub", "k1", "Academia Alfa", 0.0),
            ("wellhub", "k2", "Academia Alfa", _DELTA_PERTO),
        ]),
    )
    assert str(_fontes_de(out, "k1")) == "wellhub"
    assert str(_fontes_de(out, "k2")) == "wellhub"


def test_academia_sem_coordenada_sai_com_fontes_NULA() -> None:
    """Nulo, nao a propria fonte: a linha existe e NAO e' casavel.

    Carimbar `"totalpass"` sozinho afirmaria exclusividade que nao foi medida — mesma regra da
    auditoria da pressao, onde ausencia de medicao e' nula e nunca zero.
    """
    out = m.montar_alvos_nomeados(
        _score_multi([("k_sem", "totalpass")]),
        _coord_multi([("totalpass", "k_sem", "Academia Alfa", None)]),
    )
    assert pd.isna(_fontes_de(out, "k_sem")), "sem coordenada -> nulo, nunca a propria fonte"


def test_contrato_carrega_a_coluna_e_a_versao_subiu() -> None:
    assert "fontes_da_academia" in c.CONTRATO_COLUNAS_ALVOS_NOMEADOS
    assert c.VERSAO_CONTRATO_ALVOS_NOMEADOS == "alvos_ma_nomeados_v8"
    assert c.RAIO_MESMA_ACADEMIA_ENTRE_APPS_M == 100.0


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
