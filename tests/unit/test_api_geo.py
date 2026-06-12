"""Testes da limpeza de endereco (geo.py) — parte PURA, sem rede."""

from __future__ import annotations

from motor_expansao.api import geo


def test_link_maps_basico() -> None:
    link = geo.endereco_para_link_maps("Aguas da Prata, SP")
    assert link.startswith("https://www.google.com/maps/search/?api=1&query=")
    assert "Brasil" in geo.endereco_limpo("Aguas da Prata, SP")


def test_remove_cep() -> None:
    limpo = geo.endereco_limpo("Rua A, 10, Altinopolis - SP, CEP 14350-000")
    assert "cep" not in limpo.lower()
    assert "14350" not in limpo


def test_ancora_pais() -> None:
    assert geo.endereco_limpo("Rua A, 10, Altinopolis").endswith("Brasil")


def test_vazio() -> None:
    assert geo.endereco_para_link_maps("") == ""
    assert geo.endereco_limpo("   ") == ""


def test_percent_encoding_acentos() -> None:
    # 'ã' (U+00E3) em UTF-8 = 0xC3 0xA3 -> %C3%A3
    link = geo.endereco_para_link_maps("Endereco ã")
    assert "%C3%A3" in link.upper()
    # virgula (reservado) vira %2C
    assert "%2C" in geo.endereco_para_link_maps("Rua A, 10").upper()
