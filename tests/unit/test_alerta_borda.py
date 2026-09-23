"""Contrato do alerta de borda (`motor_expansao.api.alerta_borda`).

O que estes testes protegem, em ordem de importância:

1. que a regra de ASSINATURA não passe a casar rota nossa (seria alarme diário);
2. que uma sondagem ATENDIDA (2xx) seja notável sozinha, sem limiar;
3. que o ruído de fundo medido em produção continue FORA do envio.
"""

from __future__ import annotations

import gzip
import json
from datetime import UTC, date, datetime, timedelta

import pytest

from motor_expansao.api import alerta_borda as ab


def _evento(uri: str, *, ip: str = "1.2.3.4", status: int = 404,
            dia: str = "2026-09-20", hora: int = 12, host: str = "piloto.ultra-expansao.tech",
            agente: str = "curl/8") -> str:
    """Uma linha de access log do Caddy, no dia BRT pedido."""
    # BRT = UTC-3: para cair no dia BRT `dia` às `hora`, o UTC é hora+3.
    quando = datetime.fromisoformat(f"{dia}T{hora:02d}:00:00").replace(tzinfo=UTC) + timedelta(hours=3)
    return json.dumps({
        "ts": quando.timestamp(),
        "status": status,
        "request": {
            "client_ip": ip,
            "method": "GET",
            "host": host,
            "uri": uri,
            "headers": {"User-Agent": [agente]},
        },
    })


# ---------------------------------------------------------------- assinaturas


@pytest.mark.parametrize("uri", [
    "/.env",
    "/app/.env.production",
    "/.git/config",
    "/wp-login.php",
    "/xmlrpc.php",
    "/phpmyadmin/",
    "/.ssh/id_rsa",
    "/backup.sql",
    "/?rest_route=/wp/v2/users",
])
def test_sondagem_conhecida_dispara(uri: str) -> None:
    assert ab.assinaturas_da_uri(uri), f"{uri} deveria disparar alguma assinatura"


@pytest.mark.parametrize("uri", [
    "/",
    "/entrar.html",
    "/entrar-assets/entrar-abc123.js",
    "/assets/index-abc.js",
    "/api/me",
    "/api/ufs",
    "/api/relatorio/pontual?lat=-23.5&lng=-46.6",
    "/api/municipio/3550308",
    "/tiles/12/2000/3000.pbf",
    "/favicon.ico",
    "/robots.txt",
    "/logo-ultra.avif",
])
def test_rota_nossa_nunca_dispara(uri: str) -> None:
    """A regressão mais cara possível aqui: casar rota legítima.

    Uma assinatura que pegue `/api/...` transformaria o alerta num aviso diário
    sobre o uso normal do produto — e, pior, ensinaria a ignorá-lo.
    """
    assert ab.assinaturas_da_uri(uri) == [], f"{uri} NAO pode ser tratada como sondagem"


def test_maiuscula_nao_escapa() -> None:
    # Varredor que pede `/.ENV` não deve passar por baixo da regra.
    assert ab.assinaturas_da_uri("/.ENV")
    assert ab.assinaturas_da_uri("/WP-LOGIN.PHP")


# ---------------------------------------------------------------- agregação


def test_agrega_por_ip_e_filtra_o_dia_brt() -> None:
    linhas = [
        _evento("/.env", ip="9.9.9.9", dia="2026-09-20", hora=3),
        _evento("/.git/config", ip="9.9.9.9", dia="2026-09-20", hora=5),
        _evento("/wp-login.php", ip="8.8.8.8", dia="2026-09-20", hora=7),
        _evento("/.env", ip="7.7.7.7", dia="2026-09-19", hora=12),  # outro dia
        _evento("/api/me", ip="6.6.6.6", dia="2026-09-20", hora=9),  # sem assinatura
    ]
    por_ip = ab.agregar_sondagens(linhas, date(2026, 9, 20))
    assert set(por_ip) == {"9.9.9.9", "8.8.8.8"}
    assert por_ip["9.9.9.9"]["total"] == 2
    assert por_ip["9.9.9.9"]["assinaturas"] == {"arquivo .env", "repositório .git"}
    assert por_ip["9.9.9.9"]["ini"] == "03:00"
    assert por_ip["9.9.9.9"]["fim"] == "05:00"


def test_hora_sai_em_brt_e_nao_em_utc() -> None:
    """Regra permanente do repo: nada de UTC em texto que o Felipe lê."""
    # 23:00 BRT do dia 20 é 02:00 UTC do dia 21 — o evento tem de cair no dia 20.
    por_ip = ab.agregar_sondagens([_evento("/.env", dia="2026-09-20", hora=23)], date(2026, 9, 20))
    assert por_ip["1.2.3.4"]["ini"] == "23:00"


def test_linha_corrompida_nao_derruba_a_leitura() -> None:
    linhas = ["", "nao é json", "{quebrado", _evento("/.env")]
    assert len(ab.agregar_sondagens(linhas, date(2026, 9, 20))) == 1


# ---------------------------------------------------------------- notabilidade


def test_uma_sondagem_atendida_e_notavel_sozinha() -> None:
    """Sem limiar: 2xx é a única coisa aqui que mudou o estado do sistema."""
    por_ip = ab.agregar_sondagens([_evento("/.env", status=200)], date(2026, 9, 20))
    assert por_ip["1.2.3.4"]["atendidas"] == 1
    assert ab.notavel(por_ip) is True


def test_ruido_de_fundo_nao_e_notavel() -> None:
    """O fundo medido em produção: um IP pedindo `.env` uma ou duas vezes.

    23 dos 36 dias do log são assim. Se isto virasse mensagem, o alerta falaria
    em 2 de cada 3 dias e deixaria de ser lido.
    """
    linhas = [_evento("/.env", hora=2), _evento("/.env", hora=3)]
    assert ab.notavel(ab.agregar_sondagens(linhas, date(2026, 9, 20))) is False


def test_fan_out_de_ips_e_notavel() -> None:
    # A janela de 19–26/08 (6 a 13 IPs por dia) é o caso que este limiar pega.
    linhas = [_evento("/.env", ip=f"10.0.0.{n}") for n in range(ab.MINIMO_IPS_NOTAVEL)]
    assert ab.notavel(ab.agregar_sondagens(linhas, date(2026, 9, 20))) is True


def test_volume_de_um_ip_so_e_notavel() -> None:
    # Os estouros de 20 e 21/09 (255 e 251 requisições) caem aqui.
    linhas = [_evento("/.env", hora=h % 24) for h in range(ab.MINIMO_REQS_NOTAVEL)]
    assert ab.notavel(ab.agregar_sondagens(linhas, date(2026, 9, 20))) is True


def test_dia_sem_sondagem_nao_e_notavel() -> None:
    assert ab.notavel({}) is False


# ---------------------------------------------------------------- leitura e texto


def test_le_rotacao_gz(tmp_path) -> None:
    """A rotação do Caddy é por TAMANHO: metade do dia pode estar no .gz."""
    (tmp_path / "piloto-access.log").write_text(_evento("/.env", ip="1.1.1.1") + "\n",
                                                encoding="utf-8")
    with gzip.open(tmp_path / "piloto-access-2026-09-20T00-00-00.000-size.log.gz",
                   "wt", encoding="utf-8") as fh:
        fh.write(_evento("/.git/config", ip="2.2.2.2") + "\n")
    por_ip = ab.agregar_sondagens(ab.ler_linhas(tmp_path), date(2026, 9, 20))
    assert set(por_ip) == {"1.1.1.1", "2.2.2.2"}


def test_texto_diz_barrada_quando_nao_houve_2xx() -> None:
    texto = ab.montar_texto(date(2026, 9, 20),
                            ab.agregar_sondagens([_evento("/.env")], date(2026, 9, 20)))
    assert "20/09/2026" in texto
    assert "Todas barradas" in texto
    assert "ATENDIDA" not in texto


def test_texto_grita_quando_houve_2xx() -> None:
    texto = ab.montar_texto(date(2026, 9, 20),
                            ab.agregar_sondagens([_evento("/.env", status=200)],
                                                 date(2026, 9, 20)))
    assert "ATENÇÃO" in texto
    assert "[ATENDIDA]" in texto


def test_texto_vazio_e_reconhecivel() -> None:
    texto = ab.montar_texto(date(2026, 9, 20), {})
    assert ab.alerta_vazio(texto)


def test_teto_de_ips_resume_em_vez_de_virar_parede() -> None:
    linhas = [_evento("/.env", ip=f"10.1.{n // 256}.{n % 256}")
              for n in range(ab.TETO_IPS_NO_TEXTO + 7)]
    texto = ab.montar_texto(date(2026, 9, 20), ab.agregar_sondagens(linhas, date(2026, 9, 20)))
    assert "+7 IPs não listados" in texto


def test_ip_atendido_vai_para_o_topo_da_lista() -> None:
    """Quem passou tem de ser a PRIMEIRA linha, não a mais volumosa."""
    linhas = [_evento("/.env", ip="barrado", hora=h % 24) for h in range(30)]
    linhas.append(_evento("/.env", ip="passou", status=200))
    texto = ab.montar_texto(date(2026, 9, 20), ab.agregar_sondagens(linhas, date(2026, 9, 20)))
    assert texto.index("• passou") < texto.index("• barrado")
