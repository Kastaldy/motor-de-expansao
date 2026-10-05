"""PDF da janela da unidade no mapa: a unidade, a região e o que cada concorrente oferece.

O PDF repete o que a ficha em janela mostra (`FichaUnidadeNoMapa.tsx`) e tem de preservar os
mesmos três estados das comodidades: base ausente, academia não coletada e item declarado.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

from motor_expansao.dashboard import rede_export
from tests.unit.rede_fixtures import payload_ficha_sintetico
from tests.unit.test_pdf_base import _SEMPRE_ACENTUADAS, _texto_cru_do_pdf

SERVER = Path(__file__).resolve().parents[2] / "web" / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))


def _canal(fonte: str, itens: dict[str, bool], lista: list[str], atividades: list[str]) -> dict[str, object]:
    return {
        "fonte": fonte,
        "nome": "Academia",
        "itens": {chave: (True if valor else None) for chave, valor in itens.items()},
        "lista": lista,
        "atividades": atividades,
        "data_coleta": "2026-09-29",
    }


def _concorrente(nome: str, **campos: object) -> dict[str, object]:
    return {
        "lat": -22.95,
        "lng": -43.18,
        "nome": nome,
        "rede": "bluefit",
        "classe": "cadeia",
        "distancia_m": 320.0,
        "comodidades": None,
        "agregadores": {"wellhub": None, "totalpass": None},
        **campos,
    }


def _inteligencia(concorrentes: list[dict[str, object]]) -> dict[str, object]:
    return {
        "agregadores": {"wellhub": 150, "totalpass": 90},
        "mapa": {"raio_m": 2000, "concorrentes": concorrentes},
    }


def _ficha() -> dict[str, object]:
    ficha = payload_ficha_sintetico()
    ficha["metricas"] = {
        **ficha["metricas"],  # type: ignore[dict-item]
        "ativos": {"atual": 1_400.0},
        "pagantes": {"atual": 1_100.0},
        "agregadores": {"atual": 300.0},
    }
    return ficha


PONTO = {
    "raio_km": 1.0,
    "censo": {
        "disponivel": True,
        "renda_media_domiciliar": 8_500.0,
        "renda_per_capita": 3_200.0,
        "densidade_hab_km2": 14_000.0,
        "populacao": 43_000.0,
    },
}


def test_pdf_traz_a_unidade_a_regiao_e_o_que_cada_concorrente_oferece() -> None:
    completo = _concorrente(
        "Bluefit Botafogo",
        agregadores={"wellhub": {"plano": "Silver", "preco": 149.99, "casado_por": "ponto"}, "totalpass": None},
        comodidades={
            "recorrente": _canal("site", {"musculacao": True, "luta": True}, ["Lutas", "Ar-condicionado"], []),
            "agregador": _canal("wellhub", {"chuveiro": True}, ["Chuveiro"], ["Muay Thai", "Yoga", "muay thai", " "]),
        },
    )
    pdf = rede_export.concorrencia_pdf(_ficha(), _inteligencia([completo]), PONTO)
    assert pdf.startswith(b"%PDF-1.4")
    cru = _texto_cru_do_pdf(pdf)
    for esperado in (
        "botafogo",
        "bluefit botafogo",
        "320 m",
        "wellhub: silver",
        "149,99",
        "no site da rede",
        "no agregador \(wellhub\)",  # o PDF escapa os parênteses no texto cru
        "chuveiro",
        "lutas",
        "modalidades: muay thai, yoga",
        "1.400",  # ativos
        "43.000",  # população do raio
    ):
        assert esperado in cru, esperado


def test_pdf_distingue_base_ausente_de_academia_nao_coletada() -> None:
    sem_base = _concorrente("Academia Sem Base", comodidades=None)
    nao_coletada = _concorrente("Academia Fora da Coleta", comodidades={"recorrente": None, "agregador": None})

    cru = _texto_cru_do_pdf(rede_export.concorrencia_pdf(_ficha(), _inteligencia([sem_base]), None))
    assert "comodidades indispon" in cru and "o coletadas" not in cru

    cru = _texto_cru_do_pdf(rede_export.concorrencia_pdf(_ficha(), _inteligencia([nao_coletada]), None))
    assert "comodidades n\xe3o coletadas" in cru
    assert "sem plano de wellhub ou totalpass identificado" in cru
    # sem o censo do ponto a página não inventa número: diz que não leu
    assert "censo do entorno indispon" in cru


def test_pdf_sem_mapa_e_sem_concorrente_nao_quebra() -> None:
    sem_mapa = rede_export.concorrencia_pdf(_ficha(), {"mapa": None}, None)
    assert "sem coordenada" in _texto_cru_do_pdf(sem_mapa)
    vazio = rede_export.concorrencia_pdf(_ficha(), _inteligencia([]), PONTO)
    assert "nenhuma academia mapeada" in _texto_cru_do_pdf(vazio)


def test_pdf_pagina_quando_a_praca_e_densa_e_nao_perde_concorrente() -> None:
    muitos = [
        _concorrente(
            f"Academia Numero {i:02d}",
            comodidades={
                "recorrente": None,
                "agregador": _canal("totalpass", {"musculacao": True}, ["Musculação"], ["Funcional"] * 12),
            },
        )
        for i in range(40)
    ]
    pdf = rede_export.concorrencia_pdf(_ficha(), _inteligencia(muitos), PONTO)
    cru = _texto_cru_do_pdf(pdf)
    assert all(f"academia numero {i:02d}" in cru for i in range(40))
    assert len(re.findall(rb"/Type /Page\b", pdf)) > 2


def test_pdf_nao_imprime_interrogacao_nem_texto_sem_acento() -> None:
    # travessão e seta estão fora de latin-1: o texto da FONTE não pode virar "?" calado
    esquisito = _concorrente(
        "Studio Corpo — Unidade → Sul",
        comodidades={
            "recorrente": None,
            "agregador": _canal("wellhub", {"vestiario": True}, ["Vesti\xe1rio"], ["Dan\xe7a – ritmos"]),
        },
    )
    cru = _texto_cru_do_pdf(rede_export.concorrencia_pdf(_ficha(), _inteligencia([esquisito]), PONTO))
    assert "studio corpo - unidade -> sul" in cru
    assert "dan\xe7a - ritmos" in cru
    ofensas = sorted(set(re.findall(r"\b(?:" + "|".join(_SEMPRE_ACENTUADAS) + r")\b", cru)))
    assert not ofensas, f"PDF imprime texto sem acento (CLAUDE.md \xa72): {ofensas}"


def test_rota_do_pdf_existe_e_fica_atras_da_aba_executiva() -> None:
    import acesso
    import app as pilot

    rota = "/api/rede/unidade/{unidade_id}/concorrencia.pdf"
    assert rota in {r.path for r in pilot.app.routes}
    assert any(
        rota.startswith(prefixo) and abas == frozenset({"executiva"})
        for prefixo, abas in acesso.REGRAS_DE_ACESSO
    )


def test_rota_do_pdf_devolve_404_para_unidade_desconhecida(rede) -> None:  # noqa: F811
    import app as pilot
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as erro:
        pilot.rede_unidade_concorrencia_pdf("nao-existe")
    assert erro.value.status_code == 404


from tests.unit.test_piloto_web_rede import rede  # noqa: E402,F401  (fixture)
