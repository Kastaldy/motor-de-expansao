"""A régua de aluguel da API pública (DEC-080, Emenda 1) no compose de produção.

O que só se descobre quebrado na VPS:

1. `API_OPORTUNIDADES_PATH` fora do `environment:` do `api`. O compose de produção não tem
   `env_file`; sem a linha, `GET /api/v1/aluguel-referencia` responde 503 para sempre.
2. A variável apontando para um caminho que nenhum volume monta, ou um volume gravável. A
   API só LÊ a base do coletor.
3. O `api` lendo uma pasta de anúncios diferente da do `web`. As duas rotas têm de devolver
   o mesmo número para o mesmo município e tipo; isso começa pelo mesmo arquivo.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

import pytest

yaml = pytest.importorskip("yaml", reason="pyyaml nao instalado neste ambiente")

COMPOSE_PROD = Path(__file__).resolve().parents[2] / "docker-compose.prod.yml"


def _servicos() -> dict:
    return yaml.safe_load(COMPOSE_PROD.read_text(encoding="utf-8"))["services"]


def _mounts(servico: dict) -> list[tuple[str, str, str]]:
    """(host, container, modo) de cada bind curto `host:container[:modo]`."""
    saida = []
    for vol in servico.get("volumes") or []:
        if not isinstance(vol, str) or not vol.startswith("/"):
            continue
        partes = vol.split(":")
        saida.append((partes[0], partes[1], partes[2] if len(partes) > 2 else "rw"))
    return saida


def _mount_que_contem(servico: dict, caminho: str) -> tuple[str, str, str] | None:
    alvo = PurePosixPath(caminho)
    for host, dentro, modo in _mounts(servico):
        if alvo == PurePosixPath(dentro) or PurePosixPath(dentro) in alvo.parents:
            return host, dentro, modo
    return None


def test_api_recebe_o_caminho_da_base_de_anuncios() -> None:
    env = _servicos()["api"].get("environment") or {}
    assert env.get("API_OPORTUNIDADES_PATH") == "/app/data/oportunidades/viaveis.parquet", (
        "o `api` perdeu `API_OPORTUNIDADES_PATH` no `environment:` — sem `env_file`, a rota "
        "de aluguel de referência responderia 503 em produção"
    )


def test_api_monta_a_base_so_para_leitura_e_da_mesma_pasta_do_web() -> None:
    servicos = _servicos()
    caminho = servicos["api"]["environment"]["API_OPORTUNIDADES_PATH"]
    no_api = _mount_que_contem(servicos["api"], caminho)
    assert no_api is not None, f"nenhum volume do `api` monta {caminho}"
    assert no_api[2] == "ro", "a base de anúncios entra no `api` só para leitura (:ro)"

    no_web = _mount_que_contem(
        servicos["web"], servicos["web"]["environment"]["MOTOR_OPORTUNIDADES_PATH"]
    )
    assert no_web is not None
    assert no_api[0] == no_web[0], (
        f"`api` lê anúncios de {no_api[0]} e `web` de {no_web[0]}: as duas rotas da régua "
        "dariam números diferentes para o mesmo município"
    )
