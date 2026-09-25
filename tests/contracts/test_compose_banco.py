"""Invariantes do servico `postgres` no compose de producao (fase 2 do banco).

Tres coisas que so' se descobre quebradas na VPS, e sempre no pior momento:

1. Um `${VAR:?}` novo no compose que ninguem documentou no `.env.example`. O
   `docker compose up` ABORTA com a mensagem do `:?` -- que e' boa -- mas quem esta'
   deployando tem de adivinhar o VALOR sozinho, no meio de um deploy parado.
2. O Postgres publicando porta no host. Sem `ports:`, so' quem esta' na `app_net`
   alcanca o banco; com ele, a superficie passa a ser a internet e a unica defesa
   vira a senha.
3. O `web` esperando o banco ficar saudavel para subir. O piloto foi desenhado para
   servir SEM banco (leitura de parquet nao passa por ele) -- com `service_healthy`,
   um Postgres doente derrubaria o app inteiro junto, que e' exatamente o acoplamento
   que o healthcheck do container evita de proposito.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="pyyaml nao instalado neste ambiente")

RAIZ = Path(__file__).resolve().parents[2]
COMPOSE = RAIZ / "docker-compose.prod.yml"
ENV_EXEMPLO = RAIZ / ".env.example"

#: `${VAR:?mensagem}` = fail-closed: sem o valor, o compose aborta em vez de subir
#: com segredo vazio. Sao esses que TEM de estar documentados. Os `${VAR:-}` sao
#: opcionais por construcao e o deploy sobe sem eles.
PADRAO_OBRIGATORIA = re.compile(r"\$\{([A-Z0-9_]+):\?")
#: Pega tambem as linhas comentadas (`#   VAR=exemplo`): documentar sem preencher e'
#: legitimo para credencial que nao vai no compose, como a do runner de migration.
PADRAO_DECLARADA = re.compile(r"^\s*#?\s*([A-Z0-9_]+)=", re.MULTILINE)


@pytest.fixture(scope="module")
def compose() -> dict:
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


def test_toda_variavel_fail_closed_esta_no_env_exemplo() -> None:
    obrigatorias = set(PADRAO_OBRIGATORIA.findall(COMPOSE.read_text(encoding="utf-8")))
    declaradas = set(PADRAO_DECLARADA.findall(ENV_EXEMPLO.read_text(encoding="utf-8")))
    faltando = sorted(obrigatorias - declaradas)
    assert not faltando, (
        f"variaveis que ABORTAM o `docker compose up` sem estar no .env.example: {faltando}. "
        "Quem deploya so' descobre o nome pela mensagem de erro, e o valor por ninguem."
    )


def test_postgres_nao_publica_porta_no_host(compose: dict) -> None:
    servico = compose["services"]["postgres"]
    assert "ports" not in servico, (
        "o servico `postgres` ganhou `ports:` — isso o expoe fora da app_net. "
        "Use `expose:` (rede interna) ou um tunel SSH para acesso pontual."
    )
    assert servico.get("expose") == ["5432"]


def test_web_nao_fica_refem_da_saude_do_banco(compose: dict) -> None:
    depende = compose["services"]["web"].get("depends_on") or {}
    assert "postgres" in depende, "o `web` perdeu a ordem de subida em relacao ao banco"
    condicao = depende["postgres"]["condition"]
    assert condicao == "service_started", (
        f"`web.depends_on.postgres.condition` virou {condicao!r}. Com `service_healthy` um "
        "Postgres doente impede o piloto inteiro de subir — e ele serve sem banco de proposito."
    )


def test_postgres_e_o_volume_que_nenhum_pipeline_regenera(compose: dict) -> None:
    assert "postgres_data" in compose["volumes"], (
        "o volume nomeado `postgres_data` sumiu — sem ele o banco vive na camada de escrita do "
        "container e some no proximo `docker compose down`."
    )
    montagens = compose["services"]["postgres"].get("volumes") or []
    assert any(m.startswith("postgres_data:") for m in montagens)


# --------------------------------------------------------------------------------------
# O que o container NAO recebe: a lacuna de 25/09/2026
# --------------------------------------------------------------------------------------
#
# `MOTOR_AUTENTICACAO_PROPRIA` e' a chave que liga a autenticacao propria (epic do P19,
# DEC-067). Em 25/09/2026 ela existia no CODIGO, no `.env.example` de ninguem, no runbook
# de repasse e em quatro documentos -- e NAO existia aqui. Consequencia medida: por o
# valor no `.env` da VPS nao teria efeito nenhum, porque este compose nao tem `env_file`
# e o container so' recebe o que o bloco `environment:` lista.
#
# A falha seria MUDA. Nada quebra, o piloto sobe igual, e o operador -- que acabou de
# aplicar tres migrations e publicar uma imagem -- conclui que a epic nao funciona. E' a
# familia de defeito que este repositorio ja' catalogou (DEC-038, DEC-042, DEC-050): um
# valor legitimo que, no lugar errado, apaga uma superficie inteira em silencio.


def test_a_chave_do_P19_chega_ao_container(compose: dict) -> None:
    """Sem esta linha, virar a chave na VPS e' impossivel -- e o sintoma e' "nao acontece nada"."""
    env = compose["services"]["web"]["environment"]
    assert "MOTOR_AUTENTICACAO_PROPRIA" in env, (
        "a chave do P19 sumiu do bloco `environment:` do servico `web`. Sem ela o container "
        "nao a recebe, por o valor no `.env` da VPS vira no-op, e o corte do P19 fica "
        "impossivel de ligar sem editar o compose no meio da janela de manutencao."
    )
    # `:-` e nao `:?`: ausente, o piloto SOBE com o Authelia autenticando, que e' o estado
    # de producao. Um `:?` aqui faria a epic dormente virar pre-requisito de deploy.
    assert env["MOTOR_AUTENTICACAO_PROPRIA"] == "${MOTOR_AUTENTICACAO_PROPRIA:-}", (
        "a chave tem de ter default VAZIO. Com `:?` o compose passaria a ABORTAR sem ela, "
        "transformando uma funcionalidade dormente em pre-requisito para o piloto subir."
    )


def test_o_web_continua_SEM_env_file(compose: dict) -> None:
    """A premissa do teste acima, escrita como guarda.

    Todo o argumento -- "a variavel PRECISA estar no `environment:`" -- vale porque o
    servico nao carrega um `.env` inteiro. Se alguem acrescentar `env_file` um dia, a
    conclusao muda: as variaveis passariam a chegar sozinhas, e o bloco `environment:`
    deixaria de ser a lista completa do que o container ve'. Sem esta guarda, o teste de
    cima continuaria verde enquanto o motivo dele deixou de existir -- e a proxima
    variavel seria adicionada em dois lugares por uma razao que ja' nao vale.
    """
    assert "env_file" not in compose["services"]["web"], (
        "o servico `web` ganhou `env_file`. Isso NAO e' erro, mas muda a premissa do "
        "`test_a_chave_do_P19_chega_ao_container`: revise os dois juntos e reescreva o "
        "raciocinio, em vez de so' apagar a asercao que ficou vermelha."
    )
