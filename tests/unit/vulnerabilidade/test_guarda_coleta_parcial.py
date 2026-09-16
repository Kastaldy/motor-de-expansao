"""Guarda de coleta PARCIAL no snapshot semanal (DEC-061).

**O incidente que estes testes impedem de voltar.** Em 2026-09-13 um coletor travou, o tratador de
timeout do repo irmão quebrou e o lote morreu no coletor #28 de 90 — 56 coletores nunca rodaram. O
wrapper de domingo começa com `git checkout -- Unidades/`, que devolve os CSVs ao baseline
commitado, então as redes não recoletadas ficaram com a foto do repositório: a **Selfit caiu de 231
para 119 unidades**. O regen de mercado REPROVOU pela guarda de desenhabilidade (DEC-059) e não
publicou nada — mas o **snapshot não tem guarda nenhuma** e fotografou a coleta quebrada, gravando
`semana=2026-37/fonte=unidades` com 4.494 linhas contra 4.610 da semana anterior.

Isso é pior que perder uma semana: a série é o insumo de S3 (churn) e S4 (staleness), então as 112
Selfits que "sumiram" viram `sumiu_recente` — falso positivo em massa no sinal de maior peso
(~0,467), exatamente o modo de falha que o `--fontes unidades` do BLK-MA-06 existe para evitar.

Os testes são de COMPORTAMENTO na fronteira de publicação, não de valor: o que não pode voltar é
**gravar semana com coleta parcial em silêncio**.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from motor_expansao.vulnerabilidade import snapshots as m

REF_1 = date(2026, 7, 29)  # semana ISO 2026-31
REF_2 = date(2026, 8, 5)  # semana ISO 2026-32
SEMANA_1 = "2026-31"
SEMANA_2 = "2026-32"


def _escrever_rede(dir_unidades: Path, rede: str, n: int, *, data_coleta: str) -> None:
    """CSV sintético de uma rede, no schema real do feed `unidades` (4 colunas)."""
    dir_unidades.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "nome_unidade": [f"{rede} unidade {i}" for i in range(n)],
            # Coordenadas distintas e dentro do Brasil: nomes/células iguais colapsariam a chave.
            "latitude": [-23.55 - i * 0.01 for i in range(n)],
            "longitude": [-46.63 - i * 0.01 for i in range(n)],
            "data_coleta": [data_coleta] * n,
        }
    ).to_csv(dir_unidades / f"unidades_{rede}.csv", sep=";", encoding="utf-8-sig", index=False)


@pytest.fixture
def base_com_semana_1(tmp_path: Path) -> tuple[Path, Path]:
    """Semana 1 publicada: `alfa` com 20 unidades e `beta` com 20."""
    un, base = tmp_path / "un", tmp_path / "snapshots"
    _escrever_rede(un, "alfa", 20, data_coleta="2026-07-27")
    _escrever_rede(un, "beta", 20, data_coleta="2026-07-27")
    _, auditoria = m.materializar(
        tmp_path / "tp", tmp_path / "wh", un, base_dir=base, data_referencia=REF_1, fontes=["unidades"]
    )
    assert auditoria["publicado"] is True
    return un, base


# --------------------------------------------------------------------------- #
# A guarda                                                                     #
# --------------------------------------------------------------------------- #
def test_primeira_semana_publica_sem_referencia(tmp_path: Path) -> None:
    """Sem semana anterior não há queda que medir — a guarda não pode travar o começo da série."""
    un, base = tmp_path / "un", tmp_path / "snapshots"
    _escrever_rede(un, "alfa", 20, data_coleta="2026-07-27")
    _, auditoria = m.materializar(
        tmp_path / "tp", tmp_path / "wh", un, base_dir=base, data_referencia=REF_1, fontes=["unidades"]
    )
    assert auditoria["publicado"] is True
    guarda = auditoria["coleta_parcial"]
    assert guarda["aprovado"] is True
    assert guarda["motivos"] == []
    assert (base / f"semana={SEMANA_1}" / "fonte=unidades").is_dir()


def test_rede_que_desaba_reprova_e_NADA_e_gravado(base_com_semana_1: tuple[Path, Path]) -> None:
    """O caso 13/09: `beta` volta ao baseline do repo (20 -> 6) e a semana não pode ser gravada."""
    un, base = base_com_semana_1
    _escrever_rede(un, "beta", 6, data_coleta="2026-05-26")  # data velha: nao foi recoletada
    _, auditoria = m.materializar(
        un.parent / "tp", un.parent / "wh", un, base_dir=base, data_referencia=REF_2, fontes=["unidades"]
    )
    assert auditoria["publicado"] is False, "gravou uma coleta parcial"
    guarda = auditoria["coleta_parcial"]
    assert guarda["aprovado"] is False
    assert any("beta" in str(motivo) for motivo in guarda["motivos"])
    assert not (base / f"semana={SEMANA_2}").exists(), "a particao da semana reprovada nasceu"


def test_semana_reprovada_nao_corrompe_a_anterior(base_com_semana_1: tuple[Path, Path]) -> None:
    """`delete_matching` casa a folha; uma reprovação não pode ter apagado a série já boa."""
    un, base = base_com_semana_1
    antes = len(m.ler_snapshots(base, semanas=[SEMANA_1]))
    _escrever_rede(un, "beta", 6, data_coleta="2026-05-26")
    m.materializar(un.parent / "tp", un.parent / "wh", un, base_dir=base, data_referencia=REF_2, fontes=["unidades"])
    assert len(m.ler_snapshots(base, semanas=[SEMANA_1])) == antes


def test_queda_pequena_passa(base_com_semana_1: tuple[Path, Path]) -> None:
    """Fechamento real é ruído pequeno: uma unidade a menos publica normalmente."""
    un, base = base_com_semana_1
    _escrever_rede(un, "beta", 19, data_coleta="2026-08-03")
    _, auditoria = m.materializar(
        un.parent / "tp", un.parent / "wh", un, base_dir=base, data_referencia=REF_2, fontes=["unidades"]
    )
    assert auditoria["publicado"] is True
    assert auditoria["coleta_parcial"]["aprovado"] is True


def test_rede_nova_nao_reprova(base_com_semana_1: tuple[Path, Path]) -> None:
    """Coletor novo ADICIONA rede; a guarda mede queda, nunca crescimento."""
    un, base = base_com_semana_1
    _escrever_rede(un, "gama", 30, data_coleta="2026-08-03")
    _, auditoria = m.materializar(
        un.parent / "tp", un.parent / "wh", un, base_dir=base, data_referencia=REF_2, fontes=["unidades"]
    )
    assert auditoria["publicado"] is True


def test_forcar_publica_a_reprovada_e_carimba(base_com_semana_1: tuple[Path, Path]) -> None:
    """A saída de emergência existe, mas deixa rastro — queda real de mercado é decisão humana."""
    un, base = base_com_semana_1
    _escrever_rede(un, "beta", 6, data_coleta="2026-05-26")
    _, auditoria = m.materializar(
        un.parent / "tp", un.parent / "wh", un, base_dir=base, data_referencia=REF_2,
        fontes=["unidades"], forcar=True,
    )
    assert auditoria["publicado"] is True
    assert auditoria["coleta_parcial"]["aprovado"] is False
    assert auditoria["forcado"] is True
    assert (base / f"semana={SEMANA_2}" / "fonte=unidades").is_dir()


def test_a_guarda_compara_a_MESMA_fonte(base_com_semana_1: tuple[Path, Path]) -> None:
    """`unidades` e `wellhub` têm cadências diferentes: comparar entre fontes inventaria queda."""
    un, base = base_com_semana_1
    wh = un.parent / "wh"
    wh.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "slug": ["academia-alfa"],
            "nome": ["Academia Alfa"],
            "latitude": [-23.55],
            "longitude": [-46.63],
            "cidade": ["Sao Paulo"],
            "uf": ["SP"],
            "cep": ["01000-000"],
            "endereco_formatado": ["Rua A, 100"],
            "atividades": ["Musculacao"],
            "data_coleta": ["2026-08-03"],
        }
    ).to_csv(wh / "unidades_wellhub_sp.csv", sep=";", encoding="utf-8-sig", index=False)
    _, auditoria = m.materializar(
        un.parent / "tp", wh, un, base_dir=base, data_referencia=REF_2, fontes=["unidades", "wellhub"]
    )
    # O wellhub estreia com 1 linha; se a guarda comparasse o TOTAL entre fontes, leria desabamento.
    assert auditoria["publicado"] is True
    por_fonte = auditoria["coleta_parcial"]["por_fonte"]
    assert por_fonte["wellhub"]["semana_anterior"] is None
    assert por_fonte["unidades"]["semana_anterior"] == SEMANA_1


# --------------------------------------------------------------------------- #
# Fronteira do cron: codigo de saida                                           #
# --------------------------------------------------------------------------- #
def test_main_sai_diferente_de_zero_quando_reprova(base_com_semana_1: tuple[Path, Path]) -> None:
    """O wrapper roda com `|| echo`: sem exit != 0 a reprovacao passaria como sucesso no log."""
    un, base = base_com_semana_1
    _escrever_rede(un, "beta", 6, data_coleta="2026-05-26")
    rc = m.main([
        "--dir-totalpass", str(un.parent / "tp"),
        "--dir-wellhub", str(un.parent / "wh"),
        "--dir-unidades", str(un),
        "--base-dir", str(base),
        "--data-referencia", REF_2.isoformat(),
        "--fontes", "unidades",
    ])
    assert rc == 4, "cron leria coleta parcial como sucesso"
    assert not (base / f"semana={SEMANA_2}").exists()


def test_main_zero_quando_aprova(base_com_semana_1: tuple[Path, Path]) -> None:
    un, base = base_com_semana_1
    _escrever_rede(un, "beta", 21, data_coleta="2026-08-03")
    rc = m.main([
        "--dir-totalpass", str(un.parent / "tp"),
        "--dir-wellhub", str(un.parent / "wh"),
        "--dir-unidades", str(un),
        "--base-dir", str(base),
        "--data-referencia", REF_2.isoformat(),
        "--fontes", "unidades",
    ])
    assert rc == 0
    assert (base / f"semana={SEMANA_2}" / "fonte=unidades").is_dir()


def test_serie_ilegivel_APROVA_e_carimba_o_erro(base_com_semana_1: tuple[Path, Path]) -> None:
    """A guarda não pode virar o motivo de a semana se perder.

    Parte corrompida, layout legado ou arquivo estranho na árvore fazem `ler_snapshots` levantar.
    Antes desta degradação, isso derrubava o snapshot INTEIRO — a guarda passaria a causar
    exatamente o dano que existe para evitar. Sem referência legível ela aprova e registra.
    """
    un, base = base_com_semana_1
    (base / "semana=2020-01").mkdir(parents=True, exist_ok=True)
    (base / "semana=2020-01" / "parte-0.parquet").write_bytes(b"nao e' parquet")
    _escrever_rede(un, "beta", 6, data_coleta="2026-05-26")  # desabaria, se houvesse referencia

    _, auditoria = m.materializar(
        un.parent / "tp", un.parent / "wh", un, base_dir=base, data_referencia=REF_2, fontes=["unidades"]
    )
    guarda = auditoria["coleta_parcial"]
    assert guarda["aprovado"] is True
    assert guarda["erro_leitura_serie"] is not None
    assert auditoria["publicado"] is True


def test_piso_absoluto_do_total_nao_reprova_base_minuscula(tmp_path: Path) -> None:
    """Percentual sobre N pequeno não mede coleta parcial: 2 unidades e uma fecha já é -50%.

    O feed real tem ~4.600 linhas, então o piso é inócuo em produção — mas sem ele a guarda
    reprovaria qualquer série pequena (fixture, UF isolada, primeira semana de um país novo).
    """
    un, base = tmp_path / "un", tmp_path / "snapshots"
    _escrever_rede(un, "alfa", 2, data_coleta="2026-07-27")
    m.materializar(tmp_path / "tp", tmp_path / "wh", un, base_dir=base, data_referencia=REF_1, fontes=["unidades"])
    _escrever_rede(un, "alfa", 1, data_coleta="2026-08-03")  # -50% no total, mas sao 2 unidades

    _, auditoria = m.materializar(
        tmp_path / "tp", tmp_path / "wh", un, base_dir=base, data_referencia=REF_2, fontes=["unidades"]
    )
    assert auditoria["publicado"] is True
    assert auditoria["coleta_parcial"]["aprovado"] is True


def test_queda_difusa_grande_reprova_pelo_total(tmp_path: Path) -> None:
    """A rede de segurança: muitas redes perdendo POUCO passa na régua por rede e some no total."""
    un, base = tmp_path / "un", tmp_path / "snapshots"
    for rede in ("alfa", "beta", "gama", "delta"):
        _escrever_rede(un, rede, 20, data_coleta="2026-07-27")
    m.materializar(tmp_path / "tp", tmp_path / "wh", un, base_dir=base, data_referencia=REF_1, fontes=["unidades"])
    for rede in ("alfa", "beta", "gama", "delta"):  # -25% cada: abaixo do limite POR REDE (30%)
        _escrever_rede(un, rede, 15, data_coleta="2026-08-03")

    _, auditoria = m.materializar(
        tmp_path / "tp", tmp_path / "wh", un, base_dir=base, data_referencia=REF_2, fontes=["unidades"]
    )
    guarda = auditoria["coleta_parcial"]
    assert guarda["aprovado"] is False
    assert any("total caiu" in motivo for motivo in guarda["motivos"])
    assert auditoria["publicado"] is False


def test_dry_run_avalia_mas_nao_grava(base_com_semana_1: tuple[Path, Path]) -> None:
    """O modo seco da VPS precisa ANTECIPAR a reprovacao, senao so' se descobre no domingo."""
    un, base = base_com_semana_1
    _escrever_rede(un, "beta", 6, data_coleta="2026-05-26")
    auditoria = m.executar(
        un.parent / "tp", un.parent / "wh", un, base_dir=base, data_referencia=REF_2,
        dry_run=True, fontes=["unidades"],
    )
    assert auditoria["coleta_parcial"]["aprovado"] is False
    assert auditoria["publicado"] is False
    assert not (base / f"semana={SEMANA_2}").exists()
