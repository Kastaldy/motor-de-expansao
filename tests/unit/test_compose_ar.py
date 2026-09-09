"""Guardas do `docker-compose.ar.yml` — a stack ARGENTINA do piloto (Bloco E / BLK-INTL-08).

O teste analogo do BR (`test_piloto_web_rede.py::
test_compose_monta_somente_cadastro_e_trilha_como_volumes_de_escrita`) le o
`docker-compose.prod.yml` por caminho LITERAL, entao o compose AR nao era conferido
por NADA — exatamente a "segunda armadilha" do plano_multipais.md (BLK-INTL-08):
sem `MOTOR_CADASTRO_DIR` e sem override, `abas_do_usuario`
(`web/server/acesso.py:363-388`) devolve ABAS_VALIDAS inteira para todo autenticado.

Estes testes vivem num arquivo PROPRIO, e nao dentro de `test_piloto_web_rede.py`,
porque aquele importa `app as pilot` no topo — e `app.py` importa `h3`, que nao
carrega em toda maquina de dev (WinError 4551). Aqui e' so texto + YAML: roda puro.
"""

from __future__ import annotations

from pathlib import Path

import yaml

_REPO = Path(__file__).resolve().parents[2]
_AR = _REPO / "docker-compose.ar.yml"
_PROD = _REPO / "docker-compose.prod.yml"


def _compose_ar() -> dict:
    return yaml.safe_load(_AR.read_text(encoding="utf-8"))


def _web_ar() -> dict:
    return _compose_ar()["services"]["web_ar"]


def test_compose_ar_nao_e_fail_open_no_acesso() -> None:
    """A armadilha do plano: sem estas envs, TODO autenticado ganha TODAS as abas.

    As DUAS travas tem de estar presentes: `MOTOR_CADASTRO_DIR` liga o fail-closed
    por presenca (`acesso.py:352-354`) e aponta o `acesso_abas.json` da AR;
    `MOTOR_ACESSO_FAIL_CLOSED="1"` e' o override avaliado ANTES dela
    (`acesso.py:352-353`) — remover o cadastro no futuro nunca reabre em silencio.
    """
    env = _web_ar()["environment"]
    assert env["MOTOR_CADASTRO_DIR"] == "/app/cadastro"
    assert str(env["MOTOR_ACESSO_FAIL_CLOSED"]) == "1"


def test_compose_ar_monta_somente_cadastro_e_trilha_como_volumes_de_escrita() -> None:
    """Espelho do teste BR: lista EXATA de `:rw` — um terceiro so' entra com DEC propria."""
    montagens = [str(v) for v in _web_ar()["volumes"]]
    escritas = [m for m in montagens if m.endswith(":rw")]
    assert escritas == [
        "/opt/motor-expansao-ar/cadastro:/app/cadastro:rw",
        "/opt/motor-expansao-ar/logs/acesso:/app/logs/acesso:rw",
    ]
    assert all(m.endswith((":ro", ":rw")) for m in montagens), "montagem sem modo explicito"
    assert not any("/opt/motor-expansao-ar/data" in m for m in escritas), (
        "nenhum artefato de dados AR pode ficar sob mount de escrita"
    )


def test_compose_ar_com_ibge_e_sem_oportunidades() -> None:
    """A malha adm2 chegou (P7 fechada em 2026-09-03): o mount de ibge e' OBRIGATORIO
    e :ro, no mesmo commit em que o perfil virou malha_municipal_disponivel=true —
    compose sem o mount deixaria as rotas de ponto liberadas pelo gate estourarem 500
    na primeira coordenada. `oportunidades` segue fora de `perfil.superficies`."""
    montagens = "\n".join(str(v) for v in _web_ar()["volumes"])
    assert "/opt/motor-expansao-ar/data/ibge:/app/data/ibge:ro" in montagens
    assert "/opt/motor-expansao-ar/concorrentes:/app/concorrentes:ro" in montagens
    assert "oportunidades" not in montagens


def test_compose_ar_container_name_exato() -> None:
    """O Caddy do template e o healthcheck_vps.sh resolvem por ESTE nome — um typo
    aqui quebra o roteamento e a vigilancia ao mesmo tempo, em silencio."""
    assert _web_ar()["container_name"] == "motor_expansao_web_ar"


def test_compose_ar_sem_api_e_sem_bot() -> None:
    """Um servico so: api/bot/caddy/authelia sao da stack BR (compartilhados)."""
    assert set(_compose_ar()["services"]) == {"web_ar"}


def test_compose_ar_usa_a_mesma_imagem_do_prod() -> None:
    """DEC-047: UMA imagem, o pais vem do perfil — mesmo `${WEB_IMAGE:?...}` (forma
    identica, logo mesmo digest quando os dois composes leem o mesmo `.env`)."""
    prod = yaml.safe_load(_PROD.read_text(encoding="utf-8"))
    assert _web_ar()["image"] == prod["services"]["web"]["image"]
    assert _web_ar()["image"].startswith("${WEB_IMAGE:?")


def test_compose_ar_entra_na_rede_externa_do_edge() -> None:
    """Fail-closed de rede: `external` faz o `up` FALHAR se a rede nao existir, em
    vez de criar uma rede propria isolada do Caddy (instancia verde e inalcancavel)."""
    redes = _compose_ar()["networks"]
    assert set(redes) == {"app_net"}
    assert redes["app_net"]["external"] is True
    assert redes["app_net"]["name"] == "app_app_net"
    assert "driver" not in redes["app_net"], "rede externa nao declara driver"
    assert _web_ar()["networks"] == ["app_net"]


def test_compose_ar_tem_project_name_proprio() -> None:
    """Os dois composes rodam do MESMO diretorio (/opt/motor-expansao/app): sem
    `name:` proprio o project da AR colidiria com o da BR (`app`, do basename).

    A segunda metade pina a PREMISSA do nome de rede `app_app_net`: o compose BR
    NAO tem `name:` (project = basename do diretorio). Se um dia ele ganhar um, a
    rede runtime muda de nome e o `networks.app_net.name` do compose AR tem de
    acompanhar — este assert transforma essa deriva silenciosa em vermelho.
    """
    ar = _compose_ar()
    assert ar["name"] == "motor-expansao-ar"
    assert ar["name"] != "app"
    prod = yaml.safe_load(_PROD.read_text(encoding="utf-8"))
    assert "name" not in prod, (
        "docker-compose.prod.yml ganhou `name:` — a rede runtime deixa de ser "
        "`app_app_net`; ajuste `networks.app_net.name` no docker-compose.ar.yml junto"
    )


def test_compose_ar_espelha_o_hardening_do_prod() -> None:
    """O que a instancia BR tem de cinto, a AR tem tambem — mesma VPS, mesma exposicao."""
    web_ar = _web_ar()
    assert web_ar["restart"] == "unless-stopped"
    assert web_ar["expose"] == [8899] or web_ar["expose"] == ["8899"]
    assert "no-new-privileges:true" in web_ar["security_opt"]
    assert web_ar["cap_drop"] == ["ALL"]
    # Teto PROVISORIO (perfil.operacao.mem_limit_alvo, NAO MEDIDO) — mas presente:
    # sem teto, um pico da AR briga com os 8g do BR pela RAM do host.
    assert web_ar["mem_limit"] == "2g"
    assert web_ar["memswap_limit"] == "3g"
