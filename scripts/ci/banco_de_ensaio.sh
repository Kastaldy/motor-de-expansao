#!/usr/bin/env bash
# ============================================================================
# Banco de ensaio do CI -- o MESMO PostGIS de producao, migrado do zero a cada
# execucao do job `test`, com o teste de integracao do banco rodando SEM PULAR.
#
# POR QUE EXISTE
# Ate' 24/10/2026 o CI nao tinha Postgres. As migrations passavam so' pelo
# parser (`pglast`, tests/unit/test_migracoes.py), o login inteiro por dubles,
# e tests/integration/test_login_ponta_a_ponta.py PULAVA no CI sempre. Uma
# migration com SQL que o PostGIS 18 recusa so' apareceria no `db aplicar` ja'
# na VPS -- o passo que o runbook declara sem volta. Sintaxe certa e
# comportamento certo sao coisas diferentes; este script mede a distancia.
#
# O QUE O `verificar` PROVA, em ordem (qualquer falha reprova o job):
#   1. `db aplicar` num banco VAZIO aplica a cadeia inteira (000 -> a ultima);
#   2. `db estado` fecha: manifesto == registradas, sem pendencia nem alerta
#      (o `estado` sai 0 mesmo com pendencia -- por isso a conferencia e' aqui);
#   3. `db aplicar` de novo e' no-op ("nada a aplicar.");
#   4. o teste de integracao roda inteiro e NENHUM teste pula. Duas travas, de
#      proposito: MOTOR_BANCO_DE_ENSAIO_OBRIGATORIO=1 faz o PROPRIO teste
#      transformar "ambiente ausente" em FALHA, e o junit e' conferido no fim
#      (zero pulados, ao menos um teste), o que pega tambem o pulo que nao vem
#      de ambiente. Sem isso o passo ficaria verde sem ter testado nada.
#
# O QUE FICA DE FORA, e por que: o D20 (papeis `app`/`auditoria`/`etl`,
# GRANTs, REVOKEs, `ENABLE ALWAYS TRIGGER`). Ele vive no `banco-de-reservas`
# (`sql/papeis-e-privilegios.md`), e um D20 recriado aqui provaria o recriado,
# nao o real. O teste de integracao roda os dois instrumentos do operador
# assim mesmo, cobrando o que da' para cobrar sem ele:
#   - `db conferir` reprova POR CONSTRUCAO nas duas triggers de auditoria em
#     'O' (o fail-closed do #447) -- e esses tem de ser os UNICOS problemas;
#   - `db privilegios` nao tem `app` para conectar: roda como DONO, e a
#     reprovacao tem de ser EXATAMENTE a que o dono e a falta do D20 explicam.
#     O VEREDITO de verdade, conectado como `app`, segue manual: ensaio do
#     runbook (docs/banco_deploy.md, secao 1.2) e VPS.
#
# PARIDADE COM PRODUCAO: imagem, `shm_size`, `POSTGRES_INITDB_ARGS` e o
# `tmpfs` sobre o initdb da imagem sao LIDOS do servico `postgres` do
# docker-compose.prod.yml -- nao ha' copia para envelhecer. Sem o `tmpfs`, o
# `10_postgis.sh` da imagem instalaria topology/tiger, fixaria `search_path`
# e o `privilegios` acusaria o que o D20 nao governa (2o defeito do ensaio de
# 13/10/2026). A TAG e' resolvida a cada execucao, como num `docker compose
# pull`; o digest que de fato rodou fica no log. O dono se chama
# `reservas_owner`, como la'; o banco ganha o sufixo `_ensaio` porque a trava
# de destino do teste exige `ensaio`/`test` no nome.
#
# USO (o CI chama exatamente isto):
#   bash scripts/ci/banco_de_ensaio.sh pre-baixar  # opcional: pull em 2o plano
#   bash scripts/ci/banco_de_ensaio.sh verificar   # sobe, migra e testa
#   bash scripts/ci/banco_de_ensaio.sh derrubar    # remove container e volume
#
#   CI_BANCO_NOME    nome do container (default `ci_banco_ensaio`). TEM de
#                    comecar com `ci_banco_`: a trava impede o `derrubar` de
#                    apagar container alheio (o laboratorio de simulacro,
#                    `motor_expansao_*`, roda na mesma maquina de quem testa).
#   CI_BANCO_PORTA   porta no host, so' em 127.0.0.1 (default 55432 -- longe
#                    da 5432, para nenhum outro teste achar este banco)
#   CI_BANCO_DIR     log do pull e junit (default $RUNNER_TEMP/ci_banco_ensaio)
#   CI_BANCO_IMAGEM  SO' fora do CI: outra imagem no lugar da do compose (ex.:
#                    o digest exato da VPS, antes de um upgrade). Com
#                    GITHUB_ACTIONS=true ela e' RECUSADA -- no CI a imagem e'
#                    a do compose, sempre.
#   MOTOR_DATABASE_URL  IGNORADA (o `verificar` a apaga do proprio ambiente): e'
#                    por ela que a aplicacao escreve, e uma que tivesse sobrado no
#                    terminal levaria as escritas do teste para OUTRO banco.
#
# Na maquina (Git Bash, raiz desta arvore), com o pacote DESTA arvore no caminho:
#   PYTHONPATH="$PWD/src" CI_BANCO_NOME=ci_banco_ensaio_local \
#     bash scripts/ci/banco_de_ensaio.sh verificar
#   CI_BANCO_NOME=ci_banco_ensaio_local bash scripts/ci/banco_de_ensaio.sh derrubar
#
# A senha do dono e' ALEATORIA por execucao, mascarada no log do Actions e
# nunca gravada em arquivo: nao ha' credencial no fonte, nem default que vire
# credencial de verdade depois (o espirito do test_sem_credencial_morta.py).
# ============================================================================
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$RAIZ"

NOME="${CI_BANCO_NOME:-ci_banco_ensaio}"
PORTA="${CI_BANCO_PORTA:-55432}"
DIR="${CI_BANCO_DIR:-${RUNNER_TEMP:-${TMPDIR:-/tmp}}/ci_banco_ensaio}"
DONO="reservas_owner"
BANCO="banco_de_reservas_ensaio"
COMPOSE="docker-compose.prod.yml"
TESTE="tests/integration/test_login_ponta_a_ponta.py"

no_actions() { [ "${GITHUB_ACTIONS:-}" = "true" ]; }

# Sempre no stderr, inclusive o `::error::` do Actions (o runner le os dois fluxos): dentro
# de um `$(...)` o stdout e' capturado, e o motivo da falha sumiria junto com a captura.
erro() {
  if no_actions; then echo "::error title=Banco de ensaio::$*" >&2; else echo "ERRO: $*" >&2; fi
}

grupo() {
  if no_actions; then echo "::group::$*"; else printf '\n== %s ==\n' "$*"; fi
}

fim_grupo() {
  if no_actions; then echo "::endgroup::"; fi
}

# `docker` sem a conversao de caminho do Git Bash: no Windows, `--tmpfs
# /docker-entrypoint-initdb.d` viraria `C:/Program Files/Git/...` em silencio
# e o initdb da imagem voltaria a rodar. No Linux as duas variaveis sao inertes.
docker_() { MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*' docker "$@"; }

agora_ms() { echo $(($(date +%s%N) / 1000000)); }

case "$NOME" in
  ci_banco_*) ;;
  *)
    erro "CI_BANCO_NOME='$NOME' recusado: o nome tem de começar com 'ci_banco_'. A trava impede o 'derrubar' de apagar um container alheio."
    exit 2
    ;;
esac
case "$PORTA" in
  '' | *[!0-9]*)
    erro "CI_BANCO_PORTA='$PORTA' não é um número de porta."
    exit 2
    ;;
esac

# Um campo do servico `postgres` do compose de producao. Recusa valor com `$`:
# interpolacao e' trabalho do `docker compose`, e um `${...}` cru no
# `docker run` daria erro longe da causa.
campo_do_compose() {
  python - "$COMPOSE" "$1" <<'PY'
import sys

import yaml

with open(sys.argv[1], encoding="utf-8") as arquivo:
    servico = yaml.safe_load(arquivo)["services"]["postgres"]
campo = sys.argv[2]
if campo == "imagem":
    valor = servico["image"]
elif campo == "shm":
    valor = servico.get("shm_size") or ""
elif campo == "initdb":
    valor = (servico.get("environment") or {}).get("POSTGRES_INITDB_ARGS") or ""
elif campo == "tmpfs":
    tmpfs = servico.get("tmpfs") or []
    valor = " ".join([tmpfs] if isinstance(tmpfs, str) else tmpfs)
else:
    raise SystemExit(f"campo desconhecido: {campo}")
valor = str(valor)
if "$" in valor:
    raise SystemExit(
        f"o campo {campo} do serviço postgres usa interpolação ({valor!r}); o CI não a resolve"
    )
print(valor)
PY
}

imagem_do_banco() {
  if [ -z "${CI_BANCO_IMAGEM:-}" ]; then
    campo_do_compose imagem
    return
  fi
  if no_actions; then
    erro "CI_BANCO_IMAGEM é só para ensaio local: no CI a imagem é a do docker-compose.prod.yml, sempre."
    return 2
  fi
  echo "AVISO: CI_BANCO_IMAGEM=$CI_BANCO_IMAGEM no lugar da imagem do compose (só para ensaio local)." >&2
  echo "$CI_BANCO_IMAGEM"
}

# Pronto = aceita conexao TCP DE DENTRO do container. Por TCP, e nao pelo
# socket: durante o initdb a imagem sobe um servidor TEMPORARIO so' no socket
# (listen_addresses=''), e um `pg_isready` pelo socket diria "pronto" para o
# servidor que vai ser derrubado no segundo seguinte.
esperar_pronto() {
  local limite=$((SECONDS + 120))
  until docker_ exec "$NOME" pg_isready -q -h 127.0.0.1 -p 5432 -U "$DONO" -d "$BANCO" >/dev/null 2>&1; do
    if [ "$(docker_ container inspect -f '{{.State.Running}}' "$NOME" 2>/dev/null)" != "true" ]; then
      erro "o container $NOME parou durante a subida (initdb recusado?); o log dele vem a seguir."
      return 1
    fi
    if [ "$SECONDS" -ge "$limite" ]; then
      erro "o Postgres não aceitou conexão TCP em 120 s."
      return 1
    fi
    sleep 1
  done
}

# Na saida do `verificar` com erro: o log do container (initdb recusado, SQL que
# o servidor rejeitou) e o do pull, e sai com o MESMO codigo. Trap de EXIT, e
# nao de ERR: pega tambem a falha dentro de funcao e de `$(...)`, uma vez so'.
ao_sair() {
  local rc=$?
  if [ "$rc" -eq 0 ]; then
    return 0
  fi
  fim_grupo
  if docker_ container inspect "$NOME" >/dev/null 2>&1; then
    grupo "docker logs $NOME (últimas 200 linhas)"
    docker_ logs --tail 200 "$NOME" 2>&1 || true
    fim_grupo
  fi
  if [ -s "$DIR/pull.log" ]; then
    grupo "log do pull em segundo plano (últimas 30 linhas)"
    tail -n 30 "$DIR/pull.log" || true
    fim_grupo
  fi
  erro "o banco de ensaio reprovou (código $rc); o motivo está nas linhas acima deste aviso."
  exit "$rc"
}

pre_baixar() {
  mkdir -p "$DIR"
  local imagem
  imagem="$(imagem_do_banco)"
  nohup env MSYS_NO_PATHCONV=1 docker pull "$imagem" </dev/null >"$DIR/pull.log" 2>&1 &
  echo "baixando $imagem em segundo plano (log: $DIR/pull.log)."
  echo "O 'verificar' não depende disto para ficar certo, só para ficar rápido: se o pull ainda não tiver terminado, o 'docker run' espera; se tiver falhado, baixa de novo."
}

verificar() {
  mkdir -p "$DIR"
  local inicio fase imagem shm initdb tmpfs caminho senha estado no_manifesto registradas de_novo
  inicio="$(agora_ms)"

  if docker_ container inspect "$NOME" >/dev/null 2>&1; then
    erro "já existe um container chamado $NOME. Rode 'bash scripts/ci/banco_de_ensaio.sh derrubar' antes; de propósito, este script não apaga nada sozinho."
    exit 2
  fi
  trap ao_sair EXIT

  imagem="$(imagem_do_banco)"
  shm="$(campo_do_compose shm)"
  initdb="$(campo_do_compose initdb)"
  tmpfs="$(campo_do_compose tmpfs)"

  # Senha nova a cada execucao, so' em memoria. O `::add-mask::` vem ANTES de
  # qualquer linha que pudesse ecoa-la.
  senha="$(python -c 'import secrets; print(secrets.token_hex(16))')"
  if no_actions; then echo "::add-mask::$senha"; fi

  local args=(run -d --name "$NOME"
    -e "POSTGRES_DB=$BANCO" -e "POSTGRES_USER=$DONO" -e POSTGRES_PASSWORD
    -p "127.0.0.1:$PORTA:5432" --security-opt no-new-privileges:true)
  if [ -n "$initdb" ]; then args+=(-e "POSTGRES_INITDB_ARGS=$initdb"); fi
  if [ -n "$shm" ]; then args+=(--shm-size "$shm"); fi
  # shellcheck disable=SC2086 # um caminho por palavra, de proposito
  for caminho in $tmpfs; do args+=(--tmpfs "$caminho"); done

  grupo "subir $imagem como $NOME (127.0.0.1:$PORTA)"
  fase="$(agora_ms)"
  echo "+ docker ${args[*]} $imagem"
  # A senha vai pelo AMBIENTE do processo (`-e POSTGRES_PASSWORD` sem valor), e
  # nao pela linha de comando, que o `echo` acima mostra e o `ps` tambem.
  POSTGRES_PASSWORD="$senha" MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*' \
    docker "${args[@]}" "$imagem" >/dev/null
  esperar_pronto
  echo "imagem resolvida: $(docker_ image inspect -f '{{join .RepoDigests ", "}}' "$imagem")"
  docker_ exec "$NOME" psql -U "$DONO" -d "$BANCO" -Atc 'SELECT version()'
  echo "(pronto em $(($(agora_ms) - fase)) ms)"
  fim_grupo

  # Python sem buffer. Com a saida num pipe (o log do Actions), o `print` do `db aplicar`
  # ficava retido e o traceback, que vai direto para o stderr, saia ANTES das linhas
  # "aplicada ..." -- o log de uma migration recusada lia-se fora de ordem. Medido em
  # 24/10/2026 com uma 021 que o servidor recusa e o `pglast` aceita.
  export PYTHONUNBUFFERED=1
  # A `MOTOR_DATABASE_URL` de quem reproduz este passo na maquina NAO entra. A aplicacao
  # (e o `privilegios`) escreve por ela, e o teste so' a preenche quando esta' vazia: uma
  # que tivesse sobrado no terminal apontando para outro banco levaria as escritas do
  # teste -- senha redefinida, linha em `eventos`, que e' append-only -- para la'.
  # Medido em 24/10/2026. Sem ela, o teste a preenche com a URL do banco que este script
  # acabou de subir. O teste tambem recusa a divergencia, para quem roda sem o script.
  if [ -n "${MOTOR_DATABASE_URL:-}" ]; then
    echo "AVISO: a MOTOR_DATABASE_URL deste terminal foi ignorada; o passo usa só o banco que ele mesmo subiu." >&2
  fi
  unset MOTOR_DATABASE_URL
  export MOTOR_DATABASE_URL_ADMIN="postgresql://$DONO:$senha@127.0.0.1:$PORTA/$BANCO"

  grupo "db aplicar (banco vazio: a cadeia inteira)"
  fase="$(agora_ms)"
  echo "+ python -m motor_expansao.db aplicar"
  python -m motor_expansao.db aplicar
  docker_ exec "$NOME" psql -U "$DONO" -d "$BANCO" -Atc \
    "SELECT string_agg(extname || ' ' || extversion, ', ' ORDER BY extname) FROM pg_extension"
  echo "($(($(agora_ms) - fase)) ms)"
  fim_grupo

  grupo "db estado (sem pendência)"
  echo "+ python -m motor_expansao.db estado"
  estado="$(python -m motor_expansao.db estado)"
  printf '%s\n' "$estado"
  no_manifesto="$(sed -n 's/^migrations no manifesto: *//p' <<<"$estado")"
  registradas="$(sed -n 's/^registradas no banco: *//p' <<<"$estado")"
  if [ -z "$no_manifesto" ] || [ "$no_manifesto" != "$registradas" ] \
    || grep -qE '^(pendentes:|ATENCAO)' <<<"$estado"; then
    erro "o 'db estado' não fechou: manifesto=${no_manifesto:-?}, registradas=${registradas:-?}, ou há pendência/alerta acima."
    false
  fi
  fim_grupo

  grupo "db aplicar de novo (tem de ser no-op)"
  echo "+ python -m motor_expansao.db aplicar"
  de_novo="$(python -m motor_expansao.db aplicar)"
  printf '%s\n' "$de_novo"
  if [ "$de_novo" != "nada a aplicar." ]; then
    erro "o segundo 'db aplicar' não foi no-op: o registro de migrations não fecha com o banco."
    false
  fi
  fim_grupo

  grupo "pytest $TESTE (aqui, pular é falhar)"
  fase="$(agora_ms)"
  export MOTOR_BANCO_DE_ENSAIO_OBRIGATORIO=1
  rm -f "$DIR/integracao.xml"
  echo "+ python -m pytest $TESTE -v -rs --junitxml=$DIR/integracao.xml"
  python -m pytest "$TESTE" -v -rs --junitxml="$DIR/integracao.xml"
  if ! python - "$DIR/integracao.xml" <<'PY'
import sys
import xml.etree.ElementTree as ET

raiz = ET.parse(sys.argv[1]).getroot()
suites = [raiz] if raiz.tag == "testsuite" else raiz.findall("testsuite")


def soma(campo: str) -> int:
    return sum(int(suite.get(campo, "0")) for suite in suites)


testes, pulados = soma("tests"), soma("skipped")
print(
    f"junit: {testes} teste(s), {pulados} pulado(s), "
    f"{soma('failures')} falha(s), {soma('errors')} erro(s)"
)
if testes == 0:
    raise SystemExit("nenhum teste rodou: o passo não provou nada")
if pulados:
    raise SystemExit(f"{pulados} teste(s) PULARAM com o banco no ar; os motivos estão no -rs acima")
PY
  then
    erro "o teste de integração não rodou inteiro: pular, aqui, é falhar."
    false
  fi
  echo "($(($(agora_ms) - fase)) ms)"
  fim_grupo

  echo
  echo "banco de ensaio: tudo verde em $((($(agora_ms) - inicio) / 1000)) s. O container $NOME segue no ar para inspeção; 'derrubar' o remove."
}

derrubar() {
  if docker_ container inspect "$NOME" >/dev/null 2>&1; then
    # `-v`: a imagem declara VOLUME para os dados, e sem ele cada ensaio
    # deixaria um volume anonimo para tras.
    docker_ rm -f -v "$NOME" >/dev/null
    echo "container $NOME removido, com o volume anônimo dos dados."
  else
    echo "nenhum container chamado $NOME: nada a remover."
  fi
}

case "${1:-}" in
  pre-baixar) pre_baixar ;;
  verificar) verificar ;;
  derrubar) derrubar ;;
  *)
    echo "uso: bash scripts/ci/banco_de_ensaio.sh {pre-baixar|verificar|derrubar}" >&2
    exit 2
    ;;
esac
