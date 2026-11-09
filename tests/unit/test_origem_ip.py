"""`chave_de_origem`: a chave dos limites por IP (revisao de seguranca de 06/11/2026)."""

from __future__ import annotations

import pytest

from motor_expansao.origem_ip import chave_de_origem


@pytest.mark.parametrize(
    ("ip", "esperado"),
    [
        ("203.0.113.9", "203.0.113.9"),
        ("2001:db8:1:2::1", "2001:db8:1::/56"),
        ("2001:db8:1:ff:ffff:ffff:ffff:ffff", "2001:db8:1::/56"),
        ("::ffff:203.0.113.9", "203.0.113.9"),
        ("desconhecido", "desconhecido"),
        ("", ""),
    ],
)
def test_chave_de_origem(ip: str, esperado: str) -> None:
    assert chave_de_origem(ip) == esperado


def test_o_assinante_de_um_56_e_UMA_origem() -> None:
    """2a revisao (09/11/2026): no /64, um assinante com /56 tinha 256 chaves -- 12 chegavam ao
    teto da conta. As 256 redes /64 dele precisam virar uma chave so'."""
    chaves = {chave_de_origem(f"2001:db8:aa:{i:x}::1") for i in range(256)}
    assert len(chaves) == 1


def test_dois_56_diferentes_sao_origens_diferentes() -> None:
    """Agregar nao pode juntar assinantes de blocos distintos num balde so'."""
    assert chave_de_origem("2001:db8:1:2::1") != chave_de_origem("2001:db8:1:102::1")
