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
# A AR TAMBEM corta (DEC-081): o acoplamento AR->Authelia foi DESFEITO
# --------------------------------------------------------------------------------------
#
# Ate' 2026-10-29 este par de testes TRAVAVA o estado antigo: enquanto o `web_ar` nao tivesse
# `MOTOR_DATABASE_URL`, o bloco Caddy do AR tinha de apontar para `authelia:9091` -- os dois
# fatos so' podiam mudar JUNTOS (a DEC-067 limitara o corte do P19 ao BR, porque a AR nao tinha
# banco). A DEC-081 da' banco a' AR (o MESMO Postgres do BR, cadastro unico, pais por pessoa) e
# move os DOIS fatos no mesmo PR: o template AR passa a apontar para o nosso `/api/verify`, e o
# compose ganha `MOTOR_DATABASE_URL`/`MOTOR_AUTENTICACAO_PROPRIA` (vars AR-especificas).
#
# Os testes abaixo travam o estado NOVO -- o par continua existindo porque o acoplamento segue
# real na EXECUCAO: a aplicacao na VPS e' fail-closed e manual (Estagio 2, CLAUDE.md §6), e
# ligar o `forward_auth` para o `web_ar` antes de o banco existir derruba a AR. Mudou o alvo,
# nao a disciplina.

_TEMPLATE_AR = _REPO / "deploy" / "caddy" / "piloto-ar.Caddyfile.template"
_TEMPLATE_BR = _REPO / "deploy" / "caddy" / "piloto-br.Caddyfile.template"
_TEMPLATE_APEX = _REPO / "deploy" / "caddy" / "apex.Caddyfile.template"


def test_o_bloco_do_AR_aponta_para_o_proprio_web_ar() -> None:
    """DEC-081: o `forward_auth` do AR passou de `authelia:9091` para o nosso `web_ar`,
    espelhando o BR. Se este teste voltar a vermelho apontando ao Authelia, o corte da AR
    regrediu -- e o par (`test_o_AR_tem_banco_e_login_proprio`) regride junto."""
    texto = _TEMPLATE_AR.read_text(encoding="utf-8")
    assert "forward_auth authelia:9091" not in texto, (
        "o `forward_auth` do AR voltou a apontar para o Authelia. A DEC-081 cortou a AR para o "
        "login proprio; reverter e' reverter os DOIS fatos juntos (template + compose). (A "
        "palavra `authelia:9091` ainda aparece no COMENTARIO historico do template -- por isso "
        "o assert e' sobre a DIRETIVA `forward_auth authelia:9091`, nao a palavra solta.)"
    )
    assert "forward_auth @protegido motor_expansao_web_ar:8899" in texto, (
        "o `forward_auth` do AR deixou de perguntar ao proprio `web_ar` com o matcher "
        "`@protegido` (molde do BR). (`split('forward_auth')` nao serve: a palavra aparece nos "
        "comentarios ANTES da diretiva.)"
    )
    # Igualdade de LINHA, nao substring: `"uri /api/verify" in texto` casaria tambem
    # `uri /api/verify-sessao` (o endpoint PAIS-NEUTRO do apex). O AR e' host de PAIS -- gateia
    # por pais com `/api/verify`, nunca com o neutro.
    linhas_uri = {ln.strip() for ln in texto.splitlines() if ln.strip().startswith("uri ")}
    assert "uri /api/verify" in linhas_uri and "uri /api/verify-sessao" not in linhas_uri, (
        "o `forward_auth` do AR tem de usar `/api/verify` (gateado por pais), e NAO o "
        "`/api/verify-sessao` pais-neutro do apex."
    )


def test_o_AR_tem_banco_e_login_proprio() -> None:
    """A outra metade do acoplamento: o `web_ar` ganhou `MOTOR_DATABASE_URL` +
    `MOTOR_AUTENTICACAO_PROPRIA` (vars AR-especificas, DEC-081) -- o pre-requisito que destravou
    o corte da AR. Default VAZIO no compose: quem LIGA de verdade e' o `.env` da VPS (Estagio 2).
    """
    env = _web_ar().get("environment") or {}
    assert env.get("MOTOR_DATABASE_URL") == "${MOTOR_DATABASE_URL_AR:-}", (
        "o `web_ar` tem de declarar `MOTOR_DATABASE_URL` como var AR-especifica "
        "(`${MOTOR_DATABASE_URL_AR:-}`): reusar a do BR herdaria o alias `postgres`, que nao "
        "cruza projects compose."
    )
    assert env.get("MOTOR_AUTENTICACAO_PROPRIA") == "${MOTOR_AUTENTICACAO_PROPRIA_AR:-}", (
        "o `web_ar` tem de declarar `MOTOR_AUTENTICACAO_PROPRIA` (var AR-especifica), para "
        "ligar/desligar o login proprio da AR sem tocar o BR."
    )


def test_o_bloco_do_BR_existe_versionado_e_aponta_para_o_nosso_verify() -> None:
    """O BR precisava de um bloco versionado, e a falta dele foi a CAUSA do erro acima.

    O `Caddyfile` real e' gitignored e vive so' na VPS. Sem um template do BR, quem fosse
    aplicar o D4 nao tinha onde escreve-lo — e escreveu no do AR. Este arquivo e' o lugar
    certo, revisavel em PR e copiavel na janela de manutencao.
    """
    texto = _TEMPLATE_BR.read_text(encoding="utf-8")
    assert "forward_auth @protegido web:8899" in texto
    linhas_uri = {ln.strip() for ln in texto.splitlines() if ln.strip().startswith("uri ")}
    assert "uri /api/verify" in linhas_uri and "uri /api/verify-sessao" not in linhas_uri, (
        "o `forward_auth` do BR tem de usar `/api/verify` (gateado por pais), nao o neutro."
    )
    # O matcher NAO e' refinamento: sem ele a tela de entrar (`entrar.html`, estatico
    # deste mesmo host) ficaria atras da autenticacao que ela existe para obter.
    assert "@protegido" in texto and "not path /api/login" in texto, (
        "o bloco do BR perdeu o matcher: o `forward_auth` cobriria os estaticos e a tela "
        "de login ficaria inalcancavel — 401 em tela branca, sem formulario e sem saida."
    )


def test_o_bloco_do_apex_e_pais_neutro_e_serve_o_portal_react() -> None:
    """O apex (`ultra-expansao.tech`) ganhou bloco VERSIONADO proprio (DEC-081). Sem este teste,
    so' o `aceite_portal_paises.sh` MANUAL (na VPS, contra o Caddyfile real) o guardaria -- e os
    comentarios do template dao a entender a mesma rede de protecao de CI do BR/AR. As diretivas
    criticas, lidas do TEMPLATE versionado:

    - `uri /api/verify-sessao` (PAIS-NEUTRO) e NAO `/api/verify` (gateado): o apex e' o seletor,
      tem de admitir quem so' tem OUTRO pais;
    - `rewrite ... /portal.html`: a raiz vira a tela React (senao `/` cai no `index.html` da SPA BR);
    - `reverse_proxy web:8899`: servido pelo backend, nao de `/srv/portal` (o template Go foi aposentado);
    - as rotas publicas (incl. `/api/verify-sessao`) ficam FORA do `@protegido`.

    E nenhum vestigio do modelo Authelia nas LINHAS DE CODIGO (os comentarios citam `authelia`/
    `templates`/`/srv/portal` de proposito, ao explicar o que SAIU -- por isso o filtro de `#`).
    """
    texto = _TEMPLATE_APEX.read_text(encoding="utf-8")
    linhas = [ln.strip() for ln in texto.splitlines() if not ln.strip().startswith("#")]
    uri = {ln for ln in linhas if ln.startswith("uri ")}
    assert "uri /api/verify-sessao" in uri and "uri /api/verify" not in uri, (
        "o apex tem de usar o `/api/verify-sessao` PAIS-NEUTRO (nao o `/api/verify` gateado): e' "
        "o seletor de paises e admite quem so' tem outro pais."
    )
    assert any("rewrite" in ln and "/portal.html" in ln for ln in linhas), (
        "o apex tem de reescrever a raiz para `/portal.html` (a tela React); senao `/` cai na SPA do BR."
    )
    assert any(ln.startswith("reverse_proxy web:8899") for ln in linhas), (
        "o apex tem de servir pelo `web` (reverse_proxy web:8899), nao de `/srv/portal`."
    )
    assert any("not path" in ln and "/api/verify-sessao" in ln for ln in linhas), (
        "o matcher `@protegido` do apex tem de deixar as rotas publicas (incl. /api/verify-sessao) de fora."
    )
    corpo = "\n".join(linhas)
    for vestigio in ("authelia", "/srv/portal", "templates", "@so_"):
        assert vestigio not in corpo, (
            f"vestigio do modelo Authelia nas diretivas do apex: {vestigio!r} (DEC-081 Opcao F o removeu)."
        )
