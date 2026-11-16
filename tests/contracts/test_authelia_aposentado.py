"""O Authelia foi aposentado no Estágio 3 da DEC-081 (16/11/2026) e não pode voltar por descuido.

O kit do Estágio 3 tirou o serviço do compose da VPS; este teste trava o mesmo no repositório,
senão o próximo deploy que levasse o compose da main recriaria o container (e o `:?` das
`AUTHELIA_*` passaria a exigir segredos de um serviço morto). Vale também para o monitor, que
alertaria a cada 5 minutos por um container que não existe mais, e para os textos da aba Acessos,
que mandavam cadastrar cada pessoa nova no `users_database.yml`.

Só as LINHAS DE CÓDIGO contam: os comentários contam a história e citam o Authelia de propósito.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[2]


def _linhas_de_codigo(caminho: Path, comentario: str) -> list[str]:
    linhas = []
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        if linha.strip().startswith(comentario):
            continue
        linhas.append(linha.split(f" {comentario}", 1)[0])
    return linhas


def test_compose_de_producao_sem_o_servico_authelia() -> None:
    compose = yaml.safe_load((RAIZ / "docker-compose.prod.yml").read_text(encoding="utf-8"))
    assert "authelia" not in compose["services"]
    assert "authelia" not in (compose["services"]["caddy"].get("depends_on") or [])
    codigo = _linhas_de_codigo(RAIZ / "docker-compose.prod.yml", "#")
    assert not [linha for linha in codigo if re.search("authelia", linha, re.IGNORECASE)]


def test_env_example_sem_segredos_do_authelia() -> None:
    codigo = _linhas_de_codigo(RAIZ / ".env.example", "#")
    assert not [linha for linha in codigo if linha.startswith("AUTHELIA_")]


def test_monitor_da_vps_nao_vigia_o_authelia() -> None:
    codigo = _linhas_de_codigo(RAIZ / "scripts" / "healthcheck_vps.sh", "#")
    assert not [linha for linha in codigo if re.search("authelia", linha, re.IGNORECASE)]


def test_aba_acessos_nao_manda_cadastrar_no_authelia() -> None:
    for relativo in ("web/src/lib/painel-usuarios.ts", "web/src/lib/confirmacao-admin.ts"):
        codigo = _linhas_de_codigo(RAIZ / relativo, "//")
        sem_bloco = re.sub(r"/\*.*?\*/", "", "\n".join(codigo), flags=re.DOTALL)
        assert not re.search("authelia|users_database", sem_bloco, re.IGNORECASE), relativo
