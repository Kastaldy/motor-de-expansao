"""O padrão do pico por estado chegando à Viabilidade (emenda de 2026-10-29 da DEC-078).

O que tem de valer:
- sem o arquivo mensal, nada muda: 10 meses e as mesmas premissas de antes (o campo novo
  `pico_padrao` só diz `padrao`);
- com o arquivo, o ponto num estado com padrão próprio abre no padrão dele, e a conta é a MESMA
  de o operador ter escolhido esse pico no contador;
- a escolha do operador vence o padrão, e o payload continua dizendo qual era o padrão;
- o PDF recebe o mesmo estado.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from motor_expansao.dashboard.censo_report import _viab_linha_rampa, _viab_normalizado
from motor_expansao.dimensionamento import pico_por_uf as p
from motor_expansao.dimensionamento.payload_viabilidade import (
    ViabilidadeIn,
    montar_payload_para_pdf,
    montar_payload_viabilidade,
    premissas_do_body,
)

from .test_rampa_pico_maturacao import GOLDEN_BODY


@pytest.fixture(autouse=True)
def _cache_limpo():
    p.limpar_cache()
    yield
    p.limpar_cache()


def _staging_com_sp_11(staging: Path) -> Path:
    medicao = p.Medicao(
        33, 10, 60, 8, {"SP": (17, 10), "DF": (19, 8), "MG": (5, 6)}, "2026-09", (1.0,) * 12
    )
    p.gravar_atomico(
        staging / p.ARQUIVO,
        p.montar_artefato(medicao, {"SP": 11, "DF": 10, "MG": 9}, {"SP": 11, "DF": 10, "MG": 9}),
    )
    return staging


def _premissas(staging: Path, uf: str | None, **extra) -> dict:
    body = ViabilidadeIn(**GOLDEN_BODY, **extra)
    return montar_payload_viabilidade(body, staging_dir=staging, setores_df=None, uf=uf)[
        "premissas"
    ]


def test_sem_arquivo_as_premissas_sao_as_de_antes(tmp_path: Path) -> None:
    com_uf = _premissas(tmp_path, "SP")
    sem_uf = _premissas(tmp_path, None)
    assert com_uf == sem_uf
    assert com_uf["mes_pico_rampa"] == 10
    assert com_uf["pico_padrao"] == {
        "meses": 10,
        "origem": p.ORIGEM_PADRAO,
        "uf": None,
        "unidades_maduras": None,
        "competencia_corte": None,
    }


def test_com_arquivo_o_ponto_abre_no_padrao_do_estado(tmp_path: Path) -> None:
    staging = _staging_com_sp_11(tmp_path)
    padrao = _premissas(staging, "SP")
    escolhido = _premissas(staging, "SP", mes_pico_rampa=11)
    assert padrao["mes_pico_rampa"] == 11
    assert padrao["curva_rampa"] == escolhido["curva_rampa"]  # a mesma curva do contador em 11
    assert padrao["pico_padrao"] == {
        "meses": 11,
        "origem": p.ORIGEM_ESTADO,
        "uf": "SP",
        "unidades_maduras": 17,
        "competencia_corte": "2026-09",
    }


def test_a_conta_do_padrao_e_a_da_escolha(tmp_path: Path) -> None:
    """Pico 11 pelo padrão de SP e pico 11 escolhido no contador dão o MESMO resultado."""
    staging = _staging_com_sp_11(tmp_path)
    body = ViabilidadeIn(**GOLDEN_BODY)
    pelo_padrao = montar_payload_viabilidade(body, staging_dir=staging, setores_df=None, uf="SP")
    pela_escolha = montar_payload_viabilidade(
        ViabilidadeIn(**GOLDEN_BODY, mes_pico_rampa=11),
        staging_dir=tmp_path / "vazio",
        setores_df=None,
    )
    # Tudo igual, menos o campo que diz de onde veio o padrão (SP x sem medição).
    assert pelo_padrao["premissas"].pop("pico_padrao")["origem"] == p.ORIGEM_ESTADO
    assert pela_escolha["premissas"].pop("pico_padrao")["origem"] == p.ORIGEM_PADRAO
    assert pelo_padrao == pela_escolha


def test_escolha_do_operador_vence_o_padrao(tmp_path: Path) -> None:
    staging = _staging_com_sp_11(tmp_path)
    pr = _premissas(staging, "SP", mes_pico_rampa=10)
    assert pr["mes_pico_rampa"] == 10
    assert pr["pico_padrao"]["meses"] == 11  # o payload segue dizendo qual era o padrão


def test_estado_sem_padrao_proprio_fica_nos_10(tmp_path: Path) -> None:
    staging = _staging_com_sp_11(tmp_path)
    pr = _premissas(staging, "GO")
    assert pr["mes_pico_rampa"] == 10
    assert (pr["pico_padrao"]["origem"], pr["pico_padrao"]["uf"]) == (p.ORIGEM_REDE, "GO")


def test_padrao_abaixo_dos_10(tmp_path: Path) -> None:
    staging = _staging_com_sp_11(tmp_path)
    assert _premissas(staging, "MG")["mes_pico_rampa"] == 9


def test_na_reta_o_padrao_nao_entra(tmp_path: Path) -> None:
    staging = _staging_com_sp_11(tmp_path)
    pr = _premissas(staging, "SP", forma_rampa="reta")
    assert pr["mes_pico_rampa"] is None
    assert pr["pico_padrao"] is None


def test_pdf_recebe_o_mesmo_estado(tmp_path: Path) -> None:
    staging = _staging_com_sp_11(tmp_path)
    saida = montar_payload_para_pdf(ViabilidadeIn(**GOLDEN_BODY), staging_dir=staging, uf="SP")
    assert saida is not None
    assert saida["premissas"]["mes_pico_rampa"] == 11
    assert saida["premissas"]["pico_padrao"]["origem"] == p.ORIGEM_ESTADO


def test_premissas_com_padrao_sao_as_da_escolha() -> None:
    """A planilha usa `premissas_do_body(body, pico_padrao=...)`: tem de ser igual à escolha."""
    assert premissas_do_body(ViabilidadeIn(**GOLDEN_BODY), pico_padrao=11) == premissas_do_body(
        ViabilidadeIn(**GOLDEN_BODY, mes_pico_rampa=11)
    )
    assert premissas_do_body(ViabilidadeIn(**GOLDEN_BODY, mes_pico_rampa=10), pico_padrao=11) == (
        premissas_do_body(ViabilidadeIn(**GOLDEN_BODY))
    )


# ------------------------------------------------------------------ a linha da rampa no PDF

_SP = {"meses": 11, "origem": "estado", "uf": "SP", "unidades_maduras": 17}
_GO = {"meses": 10, "origem": "rede", "uf": "GO", "unidades_maduras": 0}


@pytest.mark.parametrize(
    ("padrao", "mes", "esperado"),
    [
        (None, 10, "Rampa: curva observada, pico de maturação no mês 10."),
        (
            {"meses": 10, "origem": "padrao"},
            10,
            "Rampa: curva observada, pico de maturação no mês 10.",
        ),
        (
            _SP,
            11,
            "Rampa: curva observada, pico de maturação no mês 11 (padrão de SP, de 17 unidades maduras).",
        ),
        (
            _SP,
            10,
            "Rampa: curva observada, pico de maturação no mês 10 (escolhido no estudo; o padrão de SP é 11).",
        ),
        (_GO, 10, "Rampa: curva observada, pico de maturação no mês 10 (padrão da rede)."),
        (
            _GO,
            12,
            "Rampa: curva observada, pico de maturação no mês 12 (escolhido no estudo; o padrão da rede é 10).",
        ),
    ],
)
def test_linha_da_rampa_no_pdf_diz_de_onde_veio(
    padrao: dict | None, mes: int, esperado: str
) -> None:
    """Sem medição publicada a linha é a de sempre; com ela, diz a origem. Latin-1, como o PDF."""
    linha = _viab_linha_rampa({"mes_pico_rampa": mes, "pico_padrao": padrao})
    assert linha == esperado
    linha.encode("latin-1")


def test_o_pdf_le_a_origem_do_payload(tmp_path: Path) -> None:
    """Caminho inteiro: payload com SP em 11 -> dados do slide -> linha do rodapé."""
    staging = _staging_com_sp_11(tmp_path)
    payload = montar_payload_viabilidade(ViabilidadeIn(**GOLDEN_BODY), staging_dir=staging, uf="SP")
    assert _viab_linha_rampa(_viab_normalizado(payload)) == (
        "Rampa: curva observada, pico de maturação no mês 11 (padrão de SP, de 17 unidades maduras)."
    )


def test_numeros_da_emenda_de_29_10_no_golden() -> None:
    """Os números que a emenda cita: no caso de referência (Londrina, a curva do produto), pico
    11 leva o retorno de 25 para 26 meses, e 9 não o muda. Se a conta do motor mudar, a emenda
    tem de mudar junto."""
    from motor_expansao.dimensionamento.simulador import simular

    from .test_rampa_pico_maturacao import DEMANDA, INVEST, _premissas_pico

    payback = {k: simular(DEMANDA, _premissas_pico(k), **INVEST).payback_meses for k in (9, 10, 11)}
    assert payback == {9: 25.0, 10: 25.0, 11: 26.0}
