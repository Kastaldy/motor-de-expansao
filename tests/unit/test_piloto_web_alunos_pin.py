"""O numero de alunos REAIS no pino do mapa (BLK-ALUNOS-01).

**A lacuna que esta suite fecha.** O campo `alunos` nasceu no payload do pino, foi para o
balao e para o aro de destaque, e nao tinha UM teste: `tests/unit/test_alunos_reais.py`
cobre o CROSSWALK (o pipeline que casa planilha com coordenada) e para ali. A fronteira
entre o artefato e a tela ficou descoberta — e e' exatamente onde este repo ja' se
machucou varias vezes (DEC-038/045/050/054): a coluna existe, o valor e' legitimo, e
mesmo assim nao chega, sem erro nenhum.

O que se protege aqui:

  * o campo CHEGA ao pino quando ha crosswalk (a projecao de `_carregar_concorrentes`
    tem de mencionar `alunos` pelo nome, senao ele e lido do parquet e descartado na
    saida — foi assim que a `foto` se perdeu uma vez);
  * so' entra `confianca_match == "alta"`: a rota de CONTENCAO e' inferencia, e quem le
    "Vila Nova Cachoeirinha - 2.400 alunos" nao tem como auditar que a linha de origem
    dizia so' "Cachoeirinha";
  * `alunos_total <= 0` NAO vira `0` na tela — desenharia academia vazia onde ha unidade
    recem-aberta ou lacuna de coleta;
  * ausencia do artefato e' caminho NORMAL (ele nao e' versionado): o mapa abre igual,
    so' sem o numero.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from tests.unit.test_piloto_web_endpoints import (  # noqa: F401
    pilot,
    synth_data,
)

HEX_SP = "87a0d0000000ffff"


def _concorrentes() -> pd.DataFrame:
    """Quatro unidades da mesma rede, uma para cada desfecho possivel do crosswalk."""
    linhas = [
        ("c-alta", "Vila Granada"),
        ("c-media", "Cachoeirinha"),
        ("c-zero", "Recem Aberta"),
        ("c-sem", "Sem Planilha"),
    ]
    return pd.DataFrame(
        [
            {
                "concorrente_id": cid,
                "rede": "redfit",
                "nome_unidade": nome,
                "lat": -23.55 + 0.001 * i,
                "lng": -46.63,
                "hex_id_res7": HEX_SP,
                "flag_coord_valida": True,
                "status_registro": "valido",
            }
            for i, (cid, nome) in enumerate(linhas)
        ]
    )


def _crosswalk() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"concorrente_id": "c-alta", "alunos_total": 889.0, "confianca_match": "alta"},
            {"concorrente_id": "c-media", "alunos_total": 2400.0, "confianca_match": "media"},
            {"concorrente_id": "c-zero", "alunos_total": 0.0, "confianca_match": "alta"},
        ]
    )


@pytest.fixture
def com_alunos(synth_data: Path) -> Path:  # noqa: F811
    staging = synth_data / "staging"
    staging.mkdir(parents=True, exist_ok=True)
    _concorrentes().to_parquet(staging / "concorrentes_mapeados.parquet")
    _crosswalk().to_parquet(staging / "alunos_reais_por_unidade.parquet")
    pilot.limpar_caches()
    return synth_data


@pytest.fixture
def sem_crosswalk(synth_data: Path) -> Path:  # noqa: F811
    staging = synth_data / "staging"
    staging.mkdir(parents=True, exist_ok=True)
    _concorrentes().to_parquet(staging / "concorrentes_mapeados.parquet")
    pilot.limpar_caches()
    return synth_data


def _por_nome(df: pd.DataFrame) -> dict:
    return {str(r.nome_unidade): r for r in df.itertuples(index=False)}


# --------------------------------------------------------------------------- #
# O campo chega                                                                #
# --------------------------------------------------------------------------- #


def test_o_numero_chega_ao_pino(com_alunos: Path) -> None:
    """A projecao final tem de MENCIONAR `alunos`, senao ele e' lido e descartado."""
    conc = pilot._carregar_concorrentes()
    assert "alunos" in conc.columns, "a coluna sumiu na projecao de saida"
    assert _por_nome(conc)["Vila Granada"].alunos == 889.0


def test_confianca_media_nao_chega_a_tela(com_alunos: Path) -> None:
    """Contencao e' inferencia; o operador nao tem como auditar isso no balao."""
    assert pd.isna(_por_nome(pilot._carregar_concorrentes())["Cachoeirinha"].alunos)


def test_zero_nao_vira_numero_exibido(com_alunos: Path) -> None:
    """Desenhar "0 alunos" numa academia que existe afirma algo falso."""
    assert pd.isna(_por_nome(pilot._carregar_concorrentes())["Recem Aberta"].alunos)


def test_unidade_sem_planilha_fica_sem_numero(com_alunos: Path) -> None:
    """Ausencia e' "nao temos a planilha desta rede", nunca "academia vazia"."""
    assert pd.isna(_por_nome(pilot._carregar_concorrentes())["Sem Planilha"].alunos)


def test_lookup_so_traz_o_que_pode_ser_exibido(com_alunos: Path) -> None:
    assert pilot._alunos_reais_por_id() == {"c-alta": 889}


# --------------------------------------------------------------------------- #
# Degradacao                                                                   #
# --------------------------------------------------------------------------- #


def test_sem_o_crosswalk_o_mapa_abre_igual(sem_crosswalk: Path) -> None:
    """O parquet nao e' versionado: ausencia e' caminho normal, nao erro."""
    assert pilot._alunos_reais_por_id() == {}
    conc = pilot._carregar_concorrentes()
    assert len(conc) == 4, "os pinos continuam existindo sem o crosswalk"
    assert "alunos" not in conc.columns


# --------------------------------------------------------------------------- #
# Payload do pino                                                              #
# --------------------------------------------------------------------------- #


def test_a_chave_alunos_esta_no_pino_do_payload(com_alunos: Path) -> None:
    """E' por esta chave que a tela desenha o aro e monta a linha do balao.

    O teste olha o pino MONTADO, e nao so' o DataFrame: entre um e outro ha' o
    `_linha_conc`, que e' onde uma chave esquecida some sem deixar rastro.
    """
    dados = pilot.municipio("SP", "Sao Paulo")
    pinos = {str(p["nome"]): p for p in dados["pins"]["concorrentes"]}
    assert pinos, "o recorte sintetico precisa ter pino para este teste valer"
    assert "alunos" in pinos["Vila Granada"], "a chave sumiu do pino"
    assert pinos["Vila Granada"]["alunos"] == 889
    # E as outras tres continuam desenhaveis, so' que sem numero.
    for nome in ("Cachoeirinha", "Recem Aberta", "Sem Planilha"):
        assert pinos[nome]["alunos"] is None, f"{nome} nao deveria ter numero"
        assert pinos[nome]["lat"] and pinos[nome]["rede"], "o pino tem de seguir desenhavel"
