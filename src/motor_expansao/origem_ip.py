"""A CHAVE de origem dos limites por IP: o IPv4 inteiro, ou o PREFIXO /56 do IPv6.

Da revisao de seguranca de 06/11/2026. Dentro do bloco IPv6 que um provedor entrega a UM
cliente, o endereco gira a vontade. Chaveado pelo endereco inteiro, cada tentativa abria balde novo -- no
rate-limit do login, na trava por (conta, IP) e no rate-limit da API --, e uma maquina so'
chegava ao teto da CONTA (50) e trancava a dona.

POR QUE /56 E NAO /64. A primeira versao agregava no /64, e a segunda revisao mediu o furo: a
delegacao tipica de banda larga e de VPS e' /56 (256 redes /64; RIPE-690), entao um assinante
sozinho tinha 256 chaves -- 12 bastavam para os 50 da conta. /56 devolve a ele o custo de UMA
origem. O preco: quem tem so' /64 (celular, alguns provedores) passa a dividir a chave com quem
mais estiver no mesmo /56 do provedor -- o limite de taxa (20/60 s) e o par (5 por conta) ficam
por grupo. Aceito: e' o mesmo efeito de um NAT de IPv4, que ja' e' o caso hoje.

REDACAO UNICA, usada pelo piloto web (`web/server/rate_limit_login.py`) e pela API
(`api/main.py`): duas regras para a mesma chave desencontrariam em silencio (DEC-044).

So' para CHAVE de limite. O IP gravado na sessao (migration 020) e na trilha segue inteiro.
"""

from __future__ import annotations

import ipaddress

#: Tamanho do bloco IPv6 que conta como UMA origem. Ver o docstring do modulo.
PREFIXO_IPV6 = 56


def chave_de_origem(ip: str) -> str:
    """`ip` como chave de limite: IPv4 intacto, IPv6 reduzido ao /56, texto nao-IP intacto.

    IPv6 mapeado de IPv4 (`::ffff:1.2.3.4`) vira o proprio IPv4, senao o mesmo cliente teria
    duas chaves conforme a pilha que o atendeu. Texto que nao e' IP (o "desconhecido" do
    teste, um peer estranho) volta como veio -- nunca levanta.
    """
    try:
        endereco = ipaddress.ip_address(ip.strip())
    except ValueError:
        return ip
    if isinstance(endereco, ipaddress.IPv6Address):
        if endereco.ipv4_mapped is not None:
            return str(endereco.ipv4_mapped)
        return str(ipaddress.IPv6Network(f"{endereco}/{PREFIXO_IPV6}", strict=False))
    return str(endereco)
