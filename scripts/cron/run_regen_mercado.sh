#!/usr/bin/env bash
# ============================================================================
# Regeneracao SEMANAL da camada paralela de mercado/residual (DEC-059)
#     rascunho -> cadeia -> validacao -> publicacao atomica -> restart
#     -> aviso no chat de ops do Telegram, nos DOIS desfechos.
#
# Este script ASSUME A ETAPA 4 INTEIRA do `run_weekly_90.sh` (a "Integracao ao
# motor"), e muda DUAS coisas em relacao ao que ela fazia:
#
#   1. LIGA O BLOCO 3. A etapa 4 de hoje NAO roda
#      `enriquecimento_espacial_hexagonos` -- ela comeca no
#      `calcular_colunas_mercado`. Ou seja: a academia coletada no domingo entra no
#      `concorrentes_mapeados.parquet` e NAO PRESSIONA NINGUEM, porque a oferta
#      espacial de 1 km (`oferta_efetiva_1km_area`, `n_concorrentes_influencia_1km`,
#      `consumo_concorrentes_1km_area`) e as contagens de 2 km continuam as da ultima
#      vez que alguem rodou o Bloco 3 a mao. Custo historico MEDIDO (DEC-048):
#      atualizar o cadastro de 11/06 para 13/08 -- nove domingos que o cron coletou e
#      nao propagou -- moveu 5.105 hexagonos (60,46%) e tirou o white space de 808.
#      Foi MAIOR que o efeito da propria DEC-048. Com a DEC-056 piorou: rede de
#      ESTUDIO nova tambem nao seria excluida do universo de oferta.
#
#   2. TROCA O REGIME DE ESCRITA. A etapa 4 de hoje escreve DIRETO no staging vivo,
#      com `||` TOLERANTE entre os passos: um passo que falha no meio deixa a camada
#      em estado MISTO (mercado novo + carteira velha, ou pior) e o lote segue com
#      `exit 0`. Ligar o Bloco 3 -- que reescreve a oferta de 1,5 milhao de hexes --
#      nesse regime seria irresponsavel. Aqui a cadeia roda num RASCUNHO, os passos
#      sao encadeados com `&&` (a falha de um PARA a cadeia), e o staging vivo so' e'
#      tocado depois que a validacao passa, por rename atomico. Reprovou: NADA
#      publicado, staging vivo intacto, aviso de falha, exit != 0.
#
# READ-ONLY sobre o M1 (CLAUDE.md §1/§3): nao recalcula `score_priorizacao` nem
# `hex_score_estrutural`, nao escreve nenhum dos 7 artefatos oficiais. Usa
# `materialize_enriched_dashboard()` -- so' o artefato DERIVADO --, nunca o `main()`
# do `fase1_bi_exports`, que recomporia os artefatos oficiais.
#
# GUARDRAIL DESTE SCRIPT (mesmo dos outros wrappers de cron do repo): ele NUNCA copia
# nada entre maquinas, NUNCA abre sessao remota e NUNCA faz deploy de imagem.
# Instalar e agendar sao passos MANUAIS do dono, comando a comando (CLAUDE.md §6).
#
# ---------------------------------------------------------------------------
# O RASCUNHO E' POR MOUNT, NAO POR `MOTOR_DATA_DIR`
#
# Isto foi MEDIDO e e' a chave do desenho: nenhum pipeline da cadeia de mercado le
# `MOTOR_DATA_DIR` (o unico `grep` em `src/motor_expansao/pipelines/` cai em
# `exportar_piloto_ar.py`, que nao esta na cadeia). Todos derivam
# `ROOT = Path(__file__).resolve().parents[3]` e montam `ROOT/data/staging` fixo.
# Como a imagem faz `COPY . .` para `/app` e este job roda com `PYTHONPATH=/app/src`
# (que tem precedencia sobre o pacote instalado em site-packages), `ROOT` e' SEMPRE
# `/app` -- entao montar o rascunho do host em `/app/data` faz a cadeia inteira
# escrever no rascunho SEM UMA LINHA de Python mudar.
#
# Isso tambem e' o que mantem ZERO diff em `enriquecimento_espacial_hexagonos.py`,
# que e' CRITICO no `scripts/loop_guard.py` desde a DEC-048 (o furo em que ele saia
# LIMPO). Nada deste bloco toca `src/`.
#
# `MOTOR_DATA_DIR=/app/data` ainda vai no ambiente, mas por OUTRO motivo: o perfil de
# pais (DEC-047) e' fail-closed quando a variavel esta setada, e queremos que o job
# leia o MESMO `perfil.json` do deploy -- por isso ele e' espelhado no rascunho e
# checado no passo 1.
#
# ---------------------------------------------------------------------------
# A MALHA DE SETORES ENTRA POR BIND `:ro`, E ISSO NAO E' OTIMIZACAO
#
# `data/outputs/setores_censitarios_2022_geo/` (468.099 setores, ~1,17 GB, 5.571
# particoes) e insumo de DOIS passos da cadeia: `calcular_colunas_mercado` chama
# `calcular_notas_municipio(CENSO_GEO_ROOT)` (nota de join municipal, DEC-054 -- que
# alimenta `flag_pop_min_5k` e portanto o GATE do SAM) e
# `fase1_bi_exports.build_enriched_dashboard_frame` faz o mesmo para o artefato
# servido ao piloto. E o contrato dessa funcao e': **artefato ausente devolve frame
# vazio e a promocao vira no-op** -- sem erro, sem log, sem teste vermelho.
#
# Ou seja: esquecer a malha no rascunho REGREDIRIA em silencio os 13.147 hexagonos
# que a DEC-054 promoveu (Manaus 2.038/2.139, Boa Vista 1.110/1.191) de volta ao
# fallback municipal, e o unico sintoma seria a populacao errada na tela. E' a
# familia de defeito da DEC-038/042/045: valor legitimo (frame vazio) no lugar
# errado apaga uma camada inteira. Por isso ela e' montada `:ro` por DENTRO do
# rascunho (bind aninhado, que o Docker resolve por profundidade de caminho) e a
# existencia dela e' PRE-CHECAGEM que aborta -- nao se espelha 468 mil arquivos por
# hardlink so' para dar a eles um caminho.
#
# ---------------------------------------------------------------------------
# ANTES DE AGENDAR: rode o modo seco (passo obrigatorio, como nos outros crons):
#     DRY_RUN=1 /opt/motor-expansao-infra/run_regen_mercado.sh
#   DRY_RUN monta o rascunho, roda a cadeia inteira e VALIDA, mas NAO publica, NAO
#   reinicia container e NAO manda Telegram -- imprime no stdout o aviso que mandaria.
#   E' a unica forma de ver os numeros do "antes->depois" sem tocar producao.
#
# INSTALACAO (uma vez) e a linha do `run_weekly_90.sh`: docs/infra_producao.md,
# secao "Regeneracao semanal da camada de mercado". Resumo:
#     install -d -m 0755 /opt/motor-expansao-infra
#     cp /opt/motor-expansao/app/scripts/cron/run_regen_mercado.sh /opt/motor-expansao-infra/
#     chmod +x /opt/motor-expansao-infra/run_regen_mercado.sh
#   e, no `/opt/gymscraping-infra/run_weekly_90.sh`, a etapa 4 inteira vira UMA linha:
#     /opt/motor-expansao-infra/run_regen_mercado.sh || echo "regen falhou (nada publicado; ver log)"
#
# O `||` AQUI, na fronteira, e' deliberado e NAO e' o `||` que este bloco veio matar:
# uma falha do regen nao pode abortar a coleta nem os passos 5/6 do lote. O que
# acabou foi o `||` ENTRE os passos da cadeia, que publicava estado misto.
# ============================================================================
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/motor-expansao/app}"
HOST_DATA="${HOST_DATA:-/opt/motor-expansao/data}"
HOST_STAGING="${HOST_STAGING:-${HOST_DATA}/staging}"
HOST_OUTPUTS="${HOST_OUTPUTS:-${HOST_DATA}/outputs}"
# Clone do repo de coleta. `Unidades/` e' o diretorio que `normalizar_concorrentes`
# varre (`ROOT/concorrentes/unidades_*.csv`, glob PLANO -- ver a armadilha do
# `/opt/motor-expansao/concorrentes` no cabecalho do run_snapshot_concorrentes.sh).
HOST_CONCORRENTES="${HOST_CONCORRENTES:-/opt/gymscraping/Unidades}"
RUN_DIR="${RUN_DIR:-/opt/motor-expansao/regen_run}"
LOG_DIR="${LOG_DIR:-/var/log/motor-snapshots}"
LOCK_FILE="${LOCK_FILE:-/var/lock/motor-regen-mercado.lock}"
DRY_RUN="${DRY_RUN:-0}"
MEMORIA="${MEMORIA:-6g}"
COMPOSE_FILE="${COMPOSE_FILE:-${APP_DIR}/docker-compose.prod.yml}"
SERVICOS_RESTART="${SERVICOS_RESTART:-web api telegram-bot}"
# Guarda de absurdo da oferta: quanto a massa de oferta de 1 km pode variar contra o
# publicado sem reprovar. A barra e' FROUXA de proposito -- ja' houve domingo com
# 45/106 redes coletadas, e uma coleta parcial legitima move a oferta bem mais que
# uma semana normal. Ela pega catastrofe (feed vazio, universo trocado), nao deriva.
TOLERANCIA_OFERTA_PCT="${TOLERANCIA_OFERTA_PCT:-15}"

RASCUNHO_DATA="${RUN_DIR}/data"
GEO_DIR="${HOST_OUTPUTS}/setores_censitarios_2022_geo"

# LOG ANTES DO LOCK (molde dos agregadores, emenda de 2026-08-26 a DEC-039): com o
# `tee` depois do `flock`, uma rodada TRAVADA faria as seguintes sairem `exit 0` e
# SEM NENHUM arquivo de log -- colisao silenciosa, e o `_latest` apontando para a
# ultima rodada COMPLETA.
TS="$(date -u +%Y%m%d-%H%M%S)"
mkdir -p "$LOG_DIR" "$RUN_DIR"
LOG="${LOG_DIR}/regen_mercado_${TS}.log"
exec > >(tee -a "$LOG") 2>&1
ln -sfn "$LOG" "${LOG_DIR}/regen_mercado_latest.log"

exec 9>"$LOCK_FILE"
flock -n 9 || { echo ">> ja rodando (lock $LOCK_FILE); saindo"; exit 0; }

echo ">> [$(date -u +%FT%TZ)] regen da camada de mercado - inicio (dry_run=${DRY_RUN})"

# Le VAR=valor do .env do compose (mesmo espirito do get_env_var do healthcheck).
#
# `tr -d '\r'` NAO e' paranoia: o `.env` da VPS chegou por rsync de uma maquina
# Windows, entao pode ter CRLF. Sem isso o `\r` final entra no nome da imagem e o
# `docker run` morre com "invalid reference format" -- mensagem que aponta para o
# lugar errado (parece digest torto).
_env_do_compose() {
  local valor
  valor="$(grep -E "^${1}=" "${APP_DIR}/.env" | head -1 | cut -d= -f2- | tr -d '\r' || true)"
  valor="${valor%\"}"; valor="${valor#\"}"
  valor="${valor%\'}"; valor="${valor#\'}"
  printf '%s' "$valor"
}

API_IMAGE="$(_env_do_compose API_IMAGE)"
[ -n "$API_IMAGE" ] || { echo "!! API_IMAGE nao encontrado em ${APP_DIR}/.env"; exit 1; }
echo ">> API_IMAGE=${API_IMAGE}"

API_TELEGRAM_TOKEN="$(_env_do_compose API_TELEGRAM_TOKEN)"
MONITOR_TELEGRAM_CHAT_ID="$(_env_do_compose MONITOR_TELEGRAM_CHAT_ID)"
export API_TELEGRAM_TOKEN MONITOR_TELEGRAM_CHAT_ID
# Credencial ausente NAO aborta a rodada (o dado vale mais que o aviso), mas fica
# GRITADO no log: sem isso os avisos morreriam engolidos pelo `|| true` e ninguem
# saberia que ops ficou surdo.
if [ "$DRY_RUN" != "1" ] && { [ -z "$API_TELEGRAM_TOKEN" ] || [ -z "$MONITOR_TELEGRAM_CHAT_ID" ]; }; then
  echo "!! AVISO: API_TELEGRAM_TOKEN/MONITOR_TELEGRAM_CHAT_ID ausentes no .env — a rodada segue, mas NENHUM aviso chegara ao chat de ops"
fi

# Envia texto ao chat de ops REUSANDO o sender ja' testado da imagem
# (`crescimento.aviso.enviar`): ele le token/chat do AMBIENTE, particiona abaixo do
# teto de 4096 do Telegram e, em falha, relanca so' a classe da excecao -- o
# `HTTPError`/`ConnectionError` do requests embute a URL COM O TOKEN, e stderr de
# cron vai para log em disco. O texto entra por STDIN, nao por argv.
#
# Token e chat vao por `-e NOME` SEM valor: `docker run ... -e API_TELEGRAM_TOKEN`
# herda do ambiente e nao aparece em `ps`.
_avisar() {
  if [ "$DRY_RUN" = "1" ]; then
    echo ">> DRY-RUN: aviso que SERIA enviado ao chat de ops:"
    cat
    return 0
  fi
  docker run --rm -i -e API_TELEGRAM_TOKEN -e MONITOR_TELEGRAM_CHAT_ID "$API_IMAGE" \
    python -c 'import sys; from motor_expansao.crescimento.aviso import enviar; enviar(sys.stdin.read())' \
    || echo "!! aviso nao foi enviado ao chat de ops"
}

_avisar_falha() {
  local etapa="$1"
  _avisar <<EOF
🔴 [Motor] Regeneração semanal da camada de mercado FALHOU.
Etapa: ${etapa}
NADA foi publicado — o staging vivo está intacto e os apps seguem servindo a camada anterior.
Log: ${LOG}
EOF
}

# --------------------------------------------------------------------------
# Passo 1 - PRE-CHECAGENS que ABORTAM (nao avisam)
#
# Vem ANTES de montar o rascunho de proposito: nao se copia ~550 MB para descobrir
# depois que falta insumo. Cada um destes, ausente, faz a cadeia rodar VERDE e
# publicar numero errado -- e' por isso que sao abort, e nao warning.
# --------------------------------------------------------------------------
echo ">> [$(date -u +%FT%TZ)] passo 1 - pre-checagens"

for d in "$APP_DIR" "$HOST_STAGING" "$HOST_OUTPUTS" "$HOST_CONCORRENTES"; do
  [ -d "$d" ] || { echo "!! diretorio ausente: $d"; exit 1; }
done

# Perfil de pais (DEC-047): com MOTOR_DATA_DIR setado o loader e' FAIL-CLOSED.
[ -f "${HOST_DATA}/perfil.json" ] || { echo "!! ${HOST_DATA}/perfil.json ausente (DEC-047: o pais e' propriedade do deploy)"; exit 1; }

# Insumos OPCIONAIS do Bloco 3 -- e e' exatamente por serem opcionais que precisam
# ser exigidos AQUI. Ausentes, `enriquecimento_espacial_hexagonos` cai em ramos de
# `print` e segue com sucesso, publicando:
#   * vulnerabilidade_ma_redes    -> oferta de cadeia 26,7% SUBESTIMADA (DEC-048)
#   * alunos_reais_por_unidade    -> 1.202 academias voltam ao proxy de 2.500 (DEC-057)
#   * unidades_ultra_mapeadas     -> canibalizacao/gap da rede propria zerados
# Verde, silencioso, e servido na tela.
for f in vulnerabilidade_ma_redes.parquet alunos_reais_por_unidade.parquet unidades_ultra_mapeadas.parquet; do
  [ -f "${HOST_STAGING}/${f}" ] || {
    echo "!! insumo ausente: ${HOST_STAGING}/${f} — o Bloco 3 sairia VERDE com oferta subestimada; abortando"
    exit 1
  }
done

# Malha de setores: sem ela a promocao da DEC-054 vira no-op EM SILENCIO (ver o
# cabecalho). `uf=` no primeiro nivel e' o layout do artefato.
[ -d "$GEO_DIR" ] && [ -n "$(find "$GEO_DIR" -mindepth 1 -maxdepth 1 -type d -name 'uf=*' -print -quit 2>/dev/null)" ] || {
  echo "!! malha de setores ausente ou vazia: ${GEO_DIR} — a nota de join municipal (DEC-054) viraria no-op sem erro; abortando"
  exit 1
}

# CSVs de concorrentes: glob PLANO `unidades_*.csv`.
[ -n "$(find "$HOST_CONCORRENTES" -maxdepth 1 -name 'unidades_*.csv' -print -quit 2>/dev/null)" ] || {
  echo "!! nenhum unidades_*.csv em ${HOST_CONCORRENTES} -- normalizar_concorrentes produziria um cadastro vazio"
  exit 1
}

docker image inspect "$API_IMAGE" >/dev/null 2>&1 || { echo "!! imagem ${API_IMAGE} ausente"; exit 1; }
# Imagem antiga (anterior a DEC-048/056/057) nao tem o modulo do Bloco 3 -- ou tem
# uma versao que nao conhece capacidade real nem estudio boutique. O import prova o
# minimo: que o modulo existe nesta imagem.
docker run --rm "$API_IMAGE" python -c "import motor_expansao.pipelines.enriquecimento_espacial_hexagonos" 2>/dev/null \
  || { echo "!! a imagem nao tem motor_expansao.pipelines.enriquecimento_espacial_hexagonos — aplique a imagem nova antes de agendar"; exit 1; }

# --------------------------------------------------------------------------
# Passo 2 - MONTAR O RASCUNHO
#
# `cp -al` (hardlink) para tudo que a cadeia so' LE: custo ~0 em tempo e em disco.
# `cp -p` DE VERDADE para o que ela SOBRESCREVE -- hardlink NAO serve ali, porque
# `to_parquet` abre o destino em modo binario de escrita e TRUNCA O INODE: com o
# inode compartilhado, escrever no rascunho vazaria para o arquivo VIVO, que e'
# exatamente o que este desenho existe para impedir.
# --------------------------------------------------------------------------
echo ">> [$(date -u +%FT%TZ)] passo 2 - montando o rascunho em ${RASCUNHO_DATA}"

# Artefatos que a cadeia REESCREVE (caminho relativo a `data/`). Ordem irrelevante;
# a lista e' a mesma usada na publicacao do passo 5.
ARTEFATOS_ESCRITOS=(
  "staging/concorrentes_mapeados.parquet"
  "staging/hexagonos_mercado_mapeado.parquet"
  "outputs/oportunidades_expansao_hibrido.parquet"
  "outputs/carteira_expansao_acionavel.parquet"
  "outputs/carteira_expansao_acionavel.csv"
  "outputs/plano_expansao_curto_prazo.parquet"
  "outputs/plano_expansao_curto_prazo.csv"
  "outputs/plano_expansao_dominio.parquet"
  "outputs/plano_expansao_dominio.csv"
)
#: Diretorio (nao arquivo) que a cadeia reescreve; publicado por rename de DIRETORIO.
DIR_ENRIQUECIDO="outputs/hexagonos_dashboard_enriquecido"

# `rm -rf` no rascunho da rodada anterior e' seguro: o que esta la' sao HARDLINKS, e
# apagar um hardlink so' decrementa o contador de links -- o arquivo vivo continua
# inteiro no lugar dele.
rm -rf "$RASCUNHO_DATA"
install -d -m 0755 "$RASCUNHO_DATA" "${RASCUNHO_DATA}/staging" "${RASCUNHO_DATA}/outputs"
cp -p "${HOST_DATA}/perfil.json" "${RASCUNHO_DATA}/perfil.json"

for entrada in "${HOST_STAGING}"/*; do
  [ -e "$entrada" ] || continue
  cp -al "$entrada" "${RASCUNHO_DATA}/staging/"
done
for entrada in "${HOST_OUTPUTS}"/*; do
  [ -e "$entrada" ] || continue
  # A malha entra por bind `:ro` no passo 3 -- espelhar 468 mil arquivos por
  # hardlink so' para dar a eles um caminho seria minutos de I/O por nada.
  [ "$(basename "$entrada")" = "setores_censitarios_2022_geo" ] && continue
  # O enriquecido NAO e' espelhado: nenhum passo da cadeia o LE (o
  # `materialize_enriched_dashboard` monta o frame do zero, do dashboard M1 + hibrido
  # + censo, e so' ESCREVE). Nao espelhar dispensa uma suposicao sobre as entranhas do
  # `ds.write_dataset` -- se algum dia ele abrisse `parte-0.parquet` em cima em vez de
  # apagar e recriar, o hardlink levaria a escrita direto para o diretorio VIVO.
  # DIFERENCA DECLARADA: no regime antigo, uma UF ausente do frame mantinha a particao
  # velha; aqui ela sumiria. O validador conta as particoes por isso.
  [ "$(basename "$entrada")" = "$(basename "$DIR_ENRIQUECIDO")" ] && continue
  cp -al "$entrada" "${RASCUNHO_DATA}/outputs/"
done

# Desfaz o hardlink dos alvos de escrita, trocando por copia REAL.
for rel in "${ARTEFATOS_ESCRITOS[@]}"; do
  rm -f "${RASCUNHO_DATA}/${rel}"
  if [ -f "${HOST_DATA}/${rel}" ]; then
    cp -p "${HOST_DATA}/${rel}" "${RASCUNHO_DATA}/${rel}"
  fi
done

echo ">> rascunho montado: $(du -sh "$RASCUNHO_DATA" 2>/dev/null | cut -f1) (o hardlink nao ocupa disco novo)"

# --------------------------------------------------------------------------
# Passo 3 - CADEIA, em container efemero, TODA com `&&`
#
# ORDEM NOVA: o Bloco 3 entra entre `normalizar_concorrentes` e
# `calcular_colunas_mercado` -- e' a mudanca que faz a coleta de domingo chegar a
# oferta espacial. O resto da ordem e' a da etapa 4 de hoje.
#
# `&&` e nao `||`: a falha de QUALQUER passo para a cadeia aqui mesmo, com o
# rascunho pela metade e o staging vivo intocado.
# --------------------------------------------------------------------------
echo ">> [$(date -u +%FT%TZ)] passo 3 - cadeia no rascunho"
set +e
docker run --rm --user 0:0 -w /app \
  -e PYTHONPATH=/app/src \
  -e MOTOR_DATA_DIR=/app/data \
  -e PYTHONIOENCODING=utf-8 \
  --memory "$MEMORIA" \
  -v "${RASCUNHO_DATA}:/app/data" \
  -v "${GEO_DIR}:/app/data/outputs/setores_censitarios_2022_geo:ro" \
  -v "${HOST_CONCORRENTES}:/app/concorrentes:ro" \
  "$API_IMAGE" \
  bash -c '
    set -e
    python -m motor_expansao.pipelines.normalizar_concorrentes &&
    python -m motor_expansao.pipelines.enriquecimento_espacial_hexagonos &&
    python -m motor_expansao.pipelines.calcular_colunas_mercado &&
    python -m motor_expansao.pipelines.gerar_carteira_acionavel &&
    python -m motor_expansao.pipelines.gerar_plano_expansao_curto_prazo &&
    python -m motor_expansao.pipelines.gerar_plano_expansao_dominio &&
    python -m motor_expansao.pipelines.enriquecer_outputs_residual_mercado &&
    python -c "from motor_expansao.pipelines.m1.fase1_bi_exports import materialize_enriched_dashboard as m; print(len(m()), \"linhas no enriquecido\")"
  '
CADEIA_RC=$?
set -e
if [ "$CADEIA_RC" -ne 0 ]; then
  _avisar_falha "cadeia de mercado (rc=${CADEIA_RC}) — rodou no rascunho, nada publicado"
  exit 3
fi

# --------------------------------------------------------------------------
# Passo 4 - VALIDACAO DE PUBLICACAO, sobre o rascunho x o publicado
#
# O validador e' escrito AQUI, no wrapper, e nao em `src/`: o wrapper viaja para a
# VPS por copia manual e este PR nao toca `src/motor_expansao/` (ver o cabecalho --
# `enriquecimento_espacial_hexagonos.py` e' CRITICO no guard e tem de ficar com ZERO
# diff). Ele roda DENTRO da imagem, que ja' tem pandas/pyarrow.
# --------------------------------------------------------------------------
echo ">> [$(date -u +%FT%TZ)] passo 4 - validacao de publicacao"
# Sobras da rodada anterior saem ANTES: se o validador morresse sem escrever, o aviso
# de falha citaria o motivo da SEMANA PASSADA como se fosse o desta rodada.
rm -f "${RUN_DIR}/falhas.txt" "${RUN_DIR}/aviso.txt" "${RUN_DIR}/resumo.json"
cat > "${RUN_DIR}/validar_publicacao.py" <<'PY'
"""Valida o rascunho da camada de mercado ANTES de publicar (DEC-059).

Reprovar aqui significa: nada publicado, staging vivo intacto, exit != 0. Escrito
pelo wrapper em runtime; roda dentro da imagem da API.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

RASCUNHO = Path("/saida/data")
VIVO = Path("/vivo")
TOLERANCIA_PCT = float(sys.argv[1]) if len(sys.argv) > 1 else 15.0

MERCADO = "staging/hexagonos_mercado_mapeado.parquet"
CONCORRENTES = "staging/concorrentes_mapeados.parquet"

#: Colunas do Bloco 3 + as de 1 km. Sao a razao de este cron existir: se elas nao
#: estiverem la', o que se publicaria e' a camada velha com data nova.
COLUNAS_EXIGIDAS = [
    "n_concorrentes_mapeados_1km",
    "n_concorrentes_mapeados_2km",
    "dist_concorrente_mais_proximo_m",
    "n_unidades_ultra_1km",
    "n_unidades_ultra_2km",
    "dist_ultra_mais_proxima_m",
    "flag_canibalizacao_ultra_1km",
    "flag_white_space_2km",
    "oferta_efetiva_1km_area",
    "gap_competitivo_1km_area",
    "consumo_concorrentes_1km_area",
    "n_concorrentes_influencia_1km",
    "n_redes_mapeadas",
]

falhas: list[str] = []
resumo: dict[str, object] = {}


def _validos(df: pd.DataFrame) -> pd.DataFrame:
    """Concorrentes DESENHAVEIS: status valido E coordenada presente.

    As duas condicoes deveriam ser a mesma coisa (`status_registro` DERIVA da
    validade da coordenada em `normalizar_concorrentes`), e e' justamente por isso
    que a coordenada e' checada de novo: a guarda de 2026-08-30 falhou por confiar
    numa propriedade que "obviamente" valia.
    """
    ok = df["status_registro"].astype(str) == "valido"
    ok &= pd.to_numeric(df["lat"], errors="coerce").notna()
    ok &= pd.to_numeric(df["lng"], errors="coerce").notna()
    return df.loc[ok]


novo = pd.read_parquet(RASCUNHO / MERCADO)
conc_bruto_novo = pd.read_parquet(RASCUNHO / CONCORRENTES)
conc_novo = _validos(conc_bruto_novo)

# (a) CARDINALIDADE preservada.
#
# A regua e' o PUBLICADO, nao um numero cravado no script. Cravar `1_542_531` aqui
# transformaria a base H3 num literal duplicado fora do `config.py` -- e o repo ja'
# pagou por constante-que-ja-foi-verdade mais de uma vez. O invariante que importa e'
# "a cadeia nao pode PERDER hexagono", e ele se mede contra o que esta no ar.
vivo_mercado = VIVO / MERCADO
if vivo_mercado.exists():
    n_vivo = len(pd.read_parquet(vivo_mercado, columns=["hex_id"]))
    if len(novo) != n_vivo:
        falhas.append(f"cardinalidade mudou: rascunho {len(novo):,} x publicado {n_vivo:,}")
    resumo["hexes_publicado"] = n_vivo
else:
    print(">> primeira publicacao: nao ha' artefato vivo para comparar cardinalidade")
resumo["hexes"] = len(novo)

# (b) COLUNAS do Bloco 3 e de 1 km presentes e sem nulo.
faltam = [c for c in COLUNAS_EXIGIDAS if c not in novo.columns]
if faltam:
    falhas.append(f"colunas ausentes no rascunho: {faltam}")
for col in [c for c in COLUNAS_EXIGIDAS if c in novo.columns]:
    n_nulos = int(novo[col].isna().sum())
    if n_nulos:
        falhas.append(f"{col} tem {n_nulos:,} nulos")

# (c) GUARDA DE ABSURDO da oferta de 1 km.
#
# `oferta_efetiva_1km_area` conserva massa por construcao: cada concorrente reparte
# 1,0 entre os hexagonos que o disco de 1 km alcanca, e o share e' renormalizado
# sobre a base valida. Logo a SOMA e' o numero de academias que efetivamente caiu na
# base -- ela e' a grandeza comparavel, e nao ha' o que dividir por 2.500 (esse
# divisor pertence a `consumo_concorrentes_1km_area`, que soma share x CAPACIDADE e,
# desde a DEC-057, nem usa 2.500 para 1.202 das unidades).
soma_nova = float(pd.to_numeric(novo["oferta_efetiva_1km_area"], errors="coerce").fillna(0).sum())
resumo["oferta_equivalente"] = round(soma_nova, 1)
if vivo_mercado.exists():
    soma_viva = float(
        pd.to_numeric(
            pd.read_parquet(vivo_mercado, columns=["oferta_efetiva_1km_area"])["oferta_efetiva_1km_area"],
            errors="coerce",
        ).fillna(0).sum()
    )
    resumo["oferta_equivalente_publicada"] = round(soma_viva, 1)
    if soma_viva > 0:
        var = 100.0 * (soma_nova - soma_viva) / soma_viva
        resumo["oferta_var_pct"] = round(var, 2)
        if abs(var) > TOLERANCIA_PCT:
            falhas.append(
                f"oferta de 1 km variou {var:+.1f}% (limite +-{TOLERANCIA_PCT:.0f}%): "
                f"{soma_viva:,.0f} -> {soma_nova:,.0f} academias-equivalentes"
            )

# (b2) PARTICOES do enriquecido: o rascunho nao herda o diretorio vivo (ele nasce so'
# do frame desta rodada), entao uma UF que sumisse do frame sumiria da tela. No regime
# antigo ela sobreviveria por inercia -- e essa inercia era o que escondia o problema.
ENRIQUECIDO = "outputs/hexagonos_dashboard_enriquecido"
ufs_novas = {p.name for p in (RASCUNHO / ENRIQUECIDO).glob("uf=*")} if (RASCUNHO / ENRIQUECIDO).is_dir() else set()
resumo["ufs_enriquecido"] = len(ufs_novas)
if not ufs_novas:
    falhas.append("o diretorio enriquecido do rascunho nao tem nenhuma particao uf=")
elif (VIVO / ENRIQUECIDO).is_dir():
    ufs_vivas = {p.name for p in (VIVO / ENRIQUECIDO).glob("uf=*")}
    perdidas = sorted(ufs_vivas - ufs_novas)
    if perdidas:
        falhas.append(f"particoes de UF que sumiriam do enriquecido: {perdidas}")

# (d) GUARDA DE DESENHABILIDADE.
#
# Licao do incidente de 2026-08-30, em que o refresh semanal APAGOU os pins do mapa:
# a guarda da epoca olhava BYTES, e um artefato gordo e sem coordenada passou. Aqui
# a regua e' a contagem de concorrentes DESENHAVEIS, e ela nao pode CAIR.
resumo["concorrentes_desenhaveis"] = len(conc_novo)
resumo["redes"] = int(conc_novo["rede"].nunique())
vivo_conc = VIVO / CONCORRENTES
if vivo_conc.exists():
    conc_vivo = _validos(pd.read_parquet(vivo_conc))
    resumo["concorrentes_desenhaveis_publicado"] = len(conc_vivo)
    resumo["redes_publicado"] = int(conc_vivo["rede"].nunique())
    if len(conc_novo) < len(conc_vivo):
        falhas.append(
            "concorrentes DESENHAVEIS cairam: "
            f"{len(conc_vivo):,} -> {len(conc_novo):,} (coleta parcial? pins sumiriam do mapa)"
        )

# (e) COERENCIA da auditoria: o carimbo do mercado bate com o cadastro que o gerou.
#
# A regua e' a MESMA de `calcular_colunas_mercado._contar_redes_mapeadas` (so'
# `status_registro == "valido"`, sem olhar coordenada), senao a checagem poderia
# reprovar por uma diferenca de DEFINICAO em vez de por uma incoerencia real.
redes_status = int(
    conc_bruto_novo.loc[conc_bruto_novo["status_registro"].astype(str) == "valido", "rede"].nunique()
)
n_redes_carimbado = (
    int(pd.to_numeric(novo["n_redes_mapeadas"], errors="coerce").dropna().iloc[0])
    if "n_redes_mapeadas" in novo.columns and len(novo)
    else -1
)
if n_redes_carimbado != redes_status:
    falhas.append(
        f"n_redes_mapeadas carimbado ({n_redes_carimbado}) != redes no cadastro ({redes_status}): "
        "o mercado nao foi gerado a partir deste concorrentes_mapeados"
    )
resumo["n_redes_mapeadas"] = n_redes_carimbado

# Honestidade de conteudo para o aviso: quantas academias ficaram no proxy de 2.500
# por falta de capacidade real (DEC-057). `alunos_total` e' a coluna do contrato
# `alunos_reais_v1`; ausencia dela NAO reprova a rodada -- e' linha de aviso, nao
# gate.
try:
    alunos = pd.read_parquet(RASCUNHO / "staging/alunos_reais_por_unidade.parquet")
    resumo["unidades_com_capacidade_real"] = int(
        pd.to_numeric(alunos["alunos_total"], errors="coerce").gt(0).sum()
    )
except (OSError, ValueError, KeyError) as exc:
    print(f">> capacidade real nao lida ({type(exc).__name__}); o aviso sai sem essa linha")
    resumo["unidades_com_capacidade_real"] = None
if resumo.get("unidades_com_capacidade_real") is not None:
    resumo["unidades_no_proxy_2500"] = max(
        0, resumo["concorrentes_desenhaveis"] - int(resumo["unidades_com_capacidade_real"])
    )

# Antes->depois de white space e de score, para o aviso (nao reprova).
if vivo_mercado.exists():
    try:
        antes = pd.read_parquet(
            vivo_mercado, columns=["hex_id", "flag_white_space_2km", "score_oportunidade_residual"]
        )
        depois = novo[["hex_id", "flag_white_space_2km", "score_oportunidade_residual"]]
        j = antes.merge(depois, on="hex_id", how="inner", suffixes=("_antes", "_depois"))
        resumo["perderam_white_space"] = int(
            (j["flag_white_space_2km_antes"].fillna(False) & ~j["flag_white_space_2km_depois"].fillna(False)).sum()
        )
        resumo["ganharam_white_space"] = int(
            (~j["flag_white_space_2km_antes"].fillna(False) & j["flag_white_space_2km_depois"].fillna(False)).sum()
        )
        delta = (
            pd.to_numeric(j["score_oportunidade_residual_depois"], errors="coerce")
            - pd.to_numeric(j["score_oportunidade_residual_antes"], errors="coerce")
        ).abs()
        resumo["hexes_com_score_alterado"] = int((delta > 0.01).sum())
    except (OSError, KeyError, ValueError) as exc:
        print(f">> antes->depois indisponivel ({type(exc).__name__}); segue sem ele")

Path("/saida/resumo.json").write_text(json.dumps(resumo, indent=2, ensure_ascii=False), encoding="utf-8")

print("\n=== Validacao de publicacao ===")
for chave, valor in resumo.items():
    print(f"  {chave}: {valor}")

if falhas:
    print("\n!! REPROVADO — nada sera publicado:")
    for f in falhas:
        print(f"   - {f}")
    Path("/saida/falhas.txt").write_text("\n".join(falhas), encoding="utf-8")
    raise SystemExit(4)

# Texto do aviso de sucesso (acentuado: e' texto de usuario, CLAUDE.md §2). Emoji e'
# seguro AQUI -- o destino e' o Telegram, nao o PDF de fonte core (latin-1).


def _num(valor: float, casas: int = 0, sinal: bool = False) -> str:
    """Numero em pt-BR: milhar com ponto, decimal com virgula.

    O `f"{x:,}"` do Python e' separador INGLES, e a mensagem e' portuguesa -- "1,542"
    lido por um operador brasileiro e' mil e meio, nao mil e quinhentos.
    """
    bruto = f"{valor:{'+' if sinal else ''},.{casas}f}"
    return bruto.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


linhas = [
    "🟢 [Motor] Camada de mercado/residual regenerada (oferta espacial de 1 km incluída).",
    f"Cadastro: {_num(resumo['concorrentes_desenhaveis'])} academias desenháveis em "
    f"{resumo['redes']} redes"
    + (
        f" (era {_num(resumo['concorrentes_desenhaveis_publicado'])} em {resumo['redes_publicado']})."
        if "concorrentes_desenhaveis_publicado" in resumo
        else "."
    ),
]
if "concorrentes_desenhaveis_publicado" in resumo:
    delta_ac = resumo["concorrentes_desenhaveis"] - resumo["concorrentes_desenhaveis_publicado"]
    linhas.append(f"Entraram/saíram no líquido: {_num(delta_ac, sinal=True)} academias.")
if "oferta_var_pct" in resumo:
    linhas.append(
        f"Oferta instalada de 1 km: {_num(resumo['oferta_equivalente_publicada'])} -> "
        f"{_num(resumo['oferta_equivalente'])} academias-equivalentes "
        f"({_num(resumo['oferta_var_pct'], casas=1, sinal=True)}%)."
    )
if "hexes_com_score_alterado" in resumo:
    linhas.append(
        f"Hexágonos com score residual alterado: {_num(resumo['hexes_com_score_alterado'])} "
        f"de {_num(resumo['hexes'])}."
    )
if "perderam_white_space" in resumo:
    linhas.append(
        f"White space: {_num(resumo['perderam_white_space'])} hexágonos perderam e "
        f"{_num(resumo['ganharam_white_space'])} ganharam."
    )
if resumo.get("unidades_no_proxy_2500") is not None:
    linhas.append(
        f"Capacidade real conhecida em {_num(resumo['unidades_com_capacidade_real'])} unidades; "
        f"as demais {_num(resumo['unidades_no_proxy_2500'])} seguem no proxy de 2.500 alunos (DEC-057)."
    )
linhas.append("READ-ONLY sobre o M1: nenhum artefato oficial foi tocado.")
Path("/saida/aviso.txt").write_text("\n".join(linhas), encoding="utf-8")
print("\nValidacao OK")
PY

set +e
docker run --rm --user 0:0 -w /app \
  -e PYTHONIOENCODING=utf-8 \
  -v "${RUN_DIR}:/saida" \
  -v "${HOST_DATA}:/vivo:ro" \
  "$API_IMAGE" \
  python /saida/validar_publicacao.py "$TOLERANCIA_OFERTA_PCT"
VALID_RC=$?
set -e
if [ "$VALID_RC" -ne 0 ]; then
  _avisar_falha "validacao de publicacao reprovou (rc=${VALID_RC}) — $(head -c 400 "${RUN_DIR}/falhas.txt" 2>/dev/null || echo 'ver o log')"
  exit 4
fi

if [ "$DRY_RUN" = "1" ]; then
  echo ">> DRY-RUN: nada publicado, sem restart, sem Telegram."
  _avisar < "${RUN_DIR}/aviso.txt"
  echo ">> [$(date -u +%FT%TZ)] regen da camada de mercado (dry-run) - OK"
  exit 0
fi

# --------------------------------------------------------------------------
# Passo 5 - PUBLICAR por `.tmp` + rename atomico
#
# Molde do `crescimento/atualizar.py:publicar`: em DUAS fases de proposito. Primeiro
# TODAS as copias (a parte lenta e falivel -- disco cheio, I/O), depois os renames
# (rapidos). Uma falha na fase de copia deixa o vivo 100% intacto; a janela de estado
# parcial e' a distancia entre os renames, nao a duracao das copias.
#
# `chmod 0644` ANTES do rename: o job roda como root e os containers leem como
# usuario non-root -- um umask restritivo aqui apagaria a camada da tela sem erro
# nenhum no job. O artefato ja' nasce legivel no instante em que aparece.
# --------------------------------------------------------------------------
echo ">> [$(date -u +%FT%TZ)] passo 5 - publicando"
PRONTOS=()
for rel in "${ARTEFATOS_ESCRITOS[@]}"; do
  origem="${RASCUNHO_DATA}/${rel}"
  [ -f "$origem" ] || { echo "   (pulado, nao gerado: ${rel})"; continue; }
  destino="${HOST_DATA}/${rel}"
  tmp="${destino}.tmp-$$"
  cp -p "$origem" "$tmp"
  chmod 0644 "$tmp"
  PRONTOS+=("${tmp}|${destino}")
done
for par in "${PRONTOS[@]}"; do
  mv -f "${par%%|*}" "${par##*|}"
  echo "   publicado ${par##*|}"
done

# Diretorio enriquecido: nao existe swap atomico de DIRETORIO em POSIX, entao a
# sequencia e' preparar ao lado -> tirar o antigo -> por o novo. A janela e' de dois
# renames seguidos (microssegundos) e o antigo fica como `.old-<TS>` para rollback
# manual ate' a rodada seguinte.
if [ -d "${RASCUNHO_DATA}/${DIR_ENRIQUECIDO}" ]; then
  novo_dir="${HOST_DATA}/${DIR_ENRIQUECIDO}.tmp-$$"
  velho_dir="${HOST_DATA}/${DIR_ENRIQUECIDO}.old-${TS}"
  rm -rf "$novo_dir"
  cp -rp "${RASCUNHO_DATA}/${DIR_ENRIQUECIDO}" "$novo_dir"
  chmod -R a+rX "$novo_dir"
  if [ -d "${HOST_DATA}/${DIR_ENRIQUECIDO}" ]; then
    mv -f "${HOST_DATA}/${DIR_ENRIQUECIDO}" "$velho_dir"
  fi
  mv -f "$novo_dir" "${HOST_DATA}/${DIR_ENRIQUECIDO}"
  echo "   publicado ${HOST_DATA}/${DIR_ENRIQUECIDO} (anterior em ${velho_dir})"
  # Guarda so' a geracao anterior; as mais velhas saem. O `|| true` e' deliberado:
  # isto roda DEPOIS da publicacao, e uma falha de faxina nao pode transformar uma
  # rodada bem-sucedida em alarme de falha (o `pipefail` faria exatamente isso).
  antigos="$(find "${HOST_DATA}/outputs" -maxdepth 1 -type d -name "$(basename "$DIR_ENRIQUECIDO").old-*" | sort | head -n -1 || true)"
  if [ -n "$antigos" ]; then
    while read -r antigo; do
      [ -n "$antigo" ] && rm -rf "$antigo"
    done <<< "$antigos"
  fi
fi

# --------------------------------------------------------------------------
# Passo 6 - RESTART + AVISO
#
# O restart e' OBRIGATORIO, nao higiene: `web/server/app.py` cacheia o parquet de
# mercado com `lru_cache(maxsize=1)` (MERCADO_PARQUET), e a api/bot cacheiam os seus.
# Sem restart, publicar nao muda a tela nem o PDF.
#
# `restart` e NUNCA `up -d --force-recreate`: o segundo reaplicaria o compose inteiro
# e poderia trocar a VERSAO do piloto junto com o dado.
# --------------------------------------------------------------------------
echo ">> [$(date -u +%FT%TZ)] passo 6 - restart de ${SERVICOS_RESTART}"
# shellcheck disable=SC2086 -- a lista de servicos e' intencionalmente separada por espaco
if ! docker compose -f "$COMPOSE_FILE" restart $SERVICOS_RESTART; then
  _avisar_falha "restart dos containers (dado NOVO publicado, apps ainda no cache antigo — reinicie a mao)"
  exit 5
fi

_avisar < "${RUN_DIR}/aviso.txt"
echo ">> [$(date -u +%FT%TZ)] regen da camada de mercado - OK"
