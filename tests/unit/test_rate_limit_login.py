"""Rate-limit por IP de /api/login (solidificacao do pentest, item 2 do achado #1).

Puro: importa so' o modulo irmao `rate_limit_login` (web/server no sys.path), sem app nem
banco. Cobre o teto por IP, o isolamento entre IPs, a janela deslizante e -- o ponto de
seguranca -- que a chave sai do ULTIMO elemento do X-Forwarded-For, nao do primeiro (que o
cliente forja).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_WEB_SERVER = Path(__file__).resolve().parents[2] / "web" / "server"
if str(_WEB_SERVER) not in sys.path:
    sys.path.insert(0, str(_WEB_SERVER))

import rate_limit_login as rl  # noqa: E402


@pytest.fixture(autouse=True)
def _limpa() -> None:
    rl._resetar_para_teste()
    yield
    rl._resetar_para_teste()


# --- chave: o IP que a BORDA observou (ultimo XFF), nunca o que o cliente dita ---------


def test_ip_sai_do_ULTIMO_elemento_do_xff_nao_do_primeiro() -> None:
    # Cliente injeta '1.2.3.4' na frente; o Caddy anexa o peer real no fim.
    assert rl.ip_observado_pelo_edge("1.2.3.4, 203.0.113.9", "10.0.0.1") == "203.0.113.9"


def test_xff_forjado_NAO_cria_balde_novo(monkeypatch: pytest.MonkeyPatch) -> None:
    """O coracao da defesa: variar o prefixo do XFF nao evade o teto, porque a chave e'
    o ultimo elemento (o peer real que o Caddy anexa) -- sempre o mesmo para um atacante."""
    monkeypatch.setattr(rl, "MAX_TENTATIVAS", 3)
    real = "198.51.100.7"
    bloqueado = False
    for i in range(10):
        xff = f"{i}.{i}.{i}.{i}, {real}"  # prefixo diferente a cada volta
        ip = rl.ip_observado_pelo_edge(xff, None)
        if rl.sob_limite(ip, agora=1000.0):
            bloqueado = True
            break
    assert bloqueado, "rotacionar o 1o XFF nao pode evadir o teto por IP"


def test_sem_xff_cai_no_fallback_e_sem_nada_vira_desconhecido() -> None:
    assert rl.ip_observado_pelo_edge(None, "10.0.0.1") == "10.0.0.1"
    assert rl.ip_observado_pelo_edge("", None) == "desconhecido"
    assert rl.ip_observado_pelo_edge("  ,  ", None) == "desconhecido"


# --- teto, isolamento entre IPs e janela deslizante ------------------------------------


def test_abaixo_do_teto_passa_e_no_teto_barra(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rl, "MAX_TENTATIVAS", 3)
    # As 3 primeiras passam (False); a 4a barra (True).
    assert rl.sob_limite("ip-a", agora=100.0) is False
    assert rl.sob_limite("ip-a", agora=100.1) is False
    assert rl.sob_limite("ip-a", agora=100.2) is False
    assert rl.sob_limite("ip-a", agora=100.3) is True


def test_ips_diferentes_sao_independentes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rl, "MAX_TENTATIVAS", 2)
    assert rl.sob_limite("ip-a", agora=10.0) is False
    assert rl.sob_limite("ip-a", agora=10.1) is False
    assert rl.sob_limite("ip-a", agora=10.2) is True
    # ip-b comeca do zero
    assert rl.sob_limite("ip-b", agora=10.2) is False


def test_janela_desliza_libera_depois_do_prazo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rl, "MAX_TENTATIVAS", 2)
    monkeypatch.setattr(rl, "JANELA_S", 60)
    assert rl.sob_limite("ip-a", agora=0.0) is False
    assert rl.sob_limite("ip-a", agora=1.0) is False
    assert rl.sob_limite("ip-a", agora=2.0) is True  # dentro da janela, barrado
    # 61 s depois do 1o: as marcas velhas sairam, volta a passar
    assert rl.sob_limite("ip-a", agora=61.5) is False


def test_tentativa_barrada_NAO_prolonga_a_janela(monkeypatch: pytest.MonkeyPatch) -> None:
    """Barrado nao registra marca nova -- senao o bloqueio nunca drenaria (como a trava
    por conta do app.py)."""
    monkeypatch.setattr(rl, "MAX_TENTATIVAS", 1)
    monkeypatch.setattr(rl, "JANELA_S", 30)
    assert rl.sob_limite("ip-a", agora=0.0) is False  # marca em t=0
    assert rl.sob_limite("ip-a", agora=10.0) is True  # barrado (nao registra t=10)
    assert rl.sob_limite("ip-a", agora=20.0) is True  # ainda dentro dos 30 s do t=0
    assert rl.sob_limite("ip-a", agora=31.0) is False  # 30 s apos t=0 (unica marca): drenou


def test_dict_podado_no_teto_de_ips(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rl, "_MAX_IPS", 5)
    for i in range(20):
        rl.sob_limite(f"ip-{i}", agora=float(i))
    assert len(rl._marcas) <= 5, "o dict tem de ser podado para nao crescer sem teto"
