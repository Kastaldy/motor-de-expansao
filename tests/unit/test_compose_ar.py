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


def test_compose_ar_liga_painel_de_acessos_por_allowlist_propria() -> None:
    """A trilha da AR ja' grava (MOTOR_ACESSO_LOG_DIR + mount :rw), mas sem a allowlist
    `pode_ver_acessos` (`web/server/acesso.py:243-275`) e' falso para todos: a aba
    some do /api/me e /api/acessos/* responde 404.

    A lista e' PROPRIA da AR (`MOTOR_ACESSOS_ADMIN_USUARIOS_AR`): os dois composes leem o
    mesmo .env da VPS, e reusar a variavel do BR prenderia quem ve o painel de um pais
    a quem ve o do outro. Vazia = painel desligado, igual ao BR.
    """
    env = _web_ar()["environment"]
    valor = str(env["MOTOR_ACESSOS_ADMIN_USUARIOS"])
    assert valor == "${MOTOR_ACESSOS_ADMIN_USUARIOS_AR:-}"
    assert "MOTOR_ACESSOS_ADMIN_USUARIOS}" not in valor
    assert "MOTOR_ACESSOS_ADMIN_USUARIOS:-}" not in valor
    assert env["MOTOR_ACESSO_LOG_DIR"] == "/app/logs/acesso"


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


# --------------------------------------------------------------------------------------
# A AR fica no Authelia (decisao de Vinicius, 25/09/2026)
# --------------------------------------------------------------------------------------
#
# O corte do P19 (DEC-067, D4) troca o alvo do `forward_auth` do Authelia para o nosso
# `/api/verify` — SO' NO BR. A AR fica onde esta', e o motivo e' de DEPENDENCIA, nao de
# preferencia: a sessao propria vive em TABELA (D1/migration 018) e o `web_ar` nao tem
# banco. Sem banco nao ha' tabela de sessao, logo o motor nao autentica ninguem la'.
#
# ESTE PAR DE TESTES EXISTE POR UM ERRO REAL, cometido em 25/09/2026. O unico Caddyfile
# VERSIONADO era o do AR (o do BR e' gitignored e vive so' na VPS), entao a mudanca do D4
# caiu nele — no host errado, porque era o unico lugar que parecia ser o lugar. Aplicada,
# ela derrubaria a AR INTEIRA: `/api/verify` responderia 404 (chave desligada) ou 503 (sem
# banco), e o Caddy nega tudo que nao for 2xx, inclusive para quem ja' estava dentro.
#
# A guarda e' de ACOPLAMENTO: enquanto o `web_ar` nao tiver `MOTOR_DATABASE_URL`, o bloco
# dele tem de apontar para o Authelia. Os dois fatos so' podem mudar JUNTOS.

_TEMPLATE_AR = _REPO / "deploy" / "caddy" / "piloto-ar.Caddyfile.template"
_TEMPLATE_BR = _REPO / "deploy" / "caddy" / "piloto-br.Caddyfile.template"


def test_o_bloco_do_AR_continua_apontando_para_o_authelia() -> None:
    """Mover este `forward_auth` sem dar banco a' AR e' derrubar a instancia."""
    texto = _TEMPLATE_AR.read_text(encoding="utf-8")
    assert "forward_auth authelia:9091" in texto, (
        "o bloco do AR deixou de apontar para o Authelia. A AR nao tem banco, entao ela "
        "NAO pode ir para o `/api/verify`: a rota responderia 404 ou 503 e o Caddy negaria "
        "a instancia inteira. Se a AR ganhou banco, mude os dois fatos no mesmo PR — este "
        "teste e' o par do `test_o_AR_continua_sem_banco` logo abaixo."
    )
    assert "web_ar:8899" not in texto.split("forward_auth")[1].split("}")[0], (
        "o `forward_auth` do AR passou a perguntar ao proprio `web_ar` — ver acima."
    )


def test_o_AR_continua_sem_banco_e_por_isso_fica_no_authelia() -> None:
    """A outra metade do acoplamento, e a razao de o teste de cima existir.

    Se alguem der `MOTOR_DATABASE_URL` ao `web_ar` e este teste ficar vermelho, a leitura
    NAO e' "apague a asercao": e' que o pre-requisito do corte da AR passou a existir, e
    a decisao de 25/09 pode ser reaberta — com DEC, porque ela foi tomada pelo dono.
    """
    env = _web_ar().get("environment") or {}
    assert "MOTOR_DATABASE_URL" not in env, (
        "o `web_ar` ganhou banco. Isso NAO e' erro — e' o pre-requisito para a AR "
        "acompanhar o corte do P19. Reabra a decisao de 25/09/2026 (a AR ficar no "
        "Authelia) em vez de so' apagar este teste."
    )


def test_o_bloco_do_BR_existe_versionado_e_aponta_para_o_nosso_verify() -> None:
    """O BR precisava de um bloco versionado, e a falta dele foi a CAUSA do erro acima.

    O `Caddyfile` real e' gitignored e vive so' na VPS. Sem um template do BR, quem fosse
    aplicar o D4 nao tinha onde escreve-lo — e escreveu no do AR. Este arquivo e' o lugar
    certo, revisavel em PR e copiavel na janela de manutencao.
    """
    texto = _TEMPLATE_BR.read_text(encoding="utf-8")
    assert "forward_auth @protegido web:8899" in texto
    assert "uri /api/verify" in texto
    # O matcher NAO e' refinamento: sem ele a tela de entrar (`entrar.html`, estatico
    # deste mesmo host) ficaria atras da autenticacao que ela existe para obter.
    assert "@protegido" in texto and "not path /api/login" in texto, (
        "o bloco do BR perdeu o matcher: o `forward_auth` cobriria os estaticos e a tela "
        "de login ficaria inalcancavel — 401 em tela branca, sem formulario e sem saida."
    )
