#!/usr/bin/env bash
# Coleta semanal dos 90 coletores + relatorio de crescimento + integracao ao motor
# (regen camada paralela mercado/residual; READ-ONLY sobre o M1). 100% autonomo.
#
# ---------------------------------------------------------------------------
# ESTE ARQUIVO E' A FONTE VERSIONADA DO LOTE DE DOMINGO.
# ---------------------------------------------------------------------------
# Ate' 2026-09-17 ele existia SO' em `/opt/gymscraping-infra/run_weekly_90.sh`, sem copia no
# repositorio -- o unico wrapper de producao sem versionamento, enquanto os outros cinco ja'
# viviam em `scripts/cron/`. O custo disso foi medido, nao suposto: a DEC-059 tirou o mount do
# checkout velho da etapa de REGEN em 2026-09-12 e deixou o passo 4.5 (pins M&A) para tras,
# porque nao havia diff para ninguem revisar. O passo ficou montando `$MOTOR/app:/app` -- um
# checkout congelado em 19/08 -- por cima da imagem, e o `alvos_ma` de la', que declara
# `snapshots_concorrentes_v3`, lia a serie `v4` de duas chaves devolvendo `fonte` NULA e gravava
# artefato VAZIO com `exit 0`. Os pins ficaram congelados de 2026-08-30 a 2026-09-17, salvos
# apenas pela guarda de desenhabilidade (`DRAW >= 100`), que recusou promover o vazio.
#
# INSTALACAO (manual, do Felipe -- CLAUDE.md §6):
#   cp /opt/motor-expansao/app/scripts/cron/run_weekly_90.sh /opt/gymscraping-infra/
#   chmod +x /opt/gymscraping-infra/run_weekly_90.sh
#   bash -n /opt/gymscraping-infra/run_weekly_90.sh   # sintaxe antes de esperar o domingo
# Cron ja' instalado: `0 6 * * 0` (domingo 06:00 UTC = 03:00 BRT).
#
# POR QUE ESTE WRAPPER PODE O QUE OS OUTROS NAO PODEM.
# `tests/unit/test_wrappers_cron_regen_mercado.py` proibe `git pull` e `docker compose` em
# wrapper de cron, e a proibicao esta certa LA': aqueles rodam a partir da estacao/CI e um
# comando desses tocaria a VPS de fora (§6). Este aqui e' o oposto -- ele E' o processo que roda
# DENTRO da VPS, disparado pelo cron do root. O `git pull` atualiza o clone do coletor e o
# `docker compose restart` recarrega os caches `lru_cache` dos apps depois do regen. Sao a razao
# de o arquivo existir, e por isso o teste proprio (`test_wrapper_cron_weekly_90.py`) EXIGE os
# dois em vez de proibi-los.
#
# DIVIDA DECLARADA, NAO CORRIGIDA AQUI (seria mudanca de comportamento num PR de
# versionamento): a linha 2 faz `git checkout -- Unidades/` e a 3 engole a falha do pull com
# `|| echo`. Juntas, elas tornam DESTRUTIVA uma falha de coletor -- o CSV raspado e' descartado
# e a rede volta ao baseline do repositorio -- e deixam um pull que falha passar em silencio.
# Foi assim que o checkout ficou 8 commits atras sem ninguem ver, ate' 2026-09-17.
set -uo pipefail
REPO=/opt/gymscraping
INFRA=/opt/gymscraping-infra
MOTOR=/opt/motor-expansao
LOGDIR=/var/log/gymscraping
mkdir -p "$LOGDIR"
TS=$(date -u +%Y%m%d-%H%M%S)
LOG="$LOGDIR/weekly_${TS}.log"
{
  echo "[$(date -u)] === run_weekly_90 INICIO ==="
  cd "$REPO" || { echo "ERRO: sem $REPO"; exit 1; }
  [ -f "$INFRA/contagem_atual.csv" ] && cp -f "$INFRA/contagem_atual.csv" "$INFRA/contagem_anterior.csv"
  git checkout -- Unidades/ 2>/dev/null || true   # auto-cura: descarta CSVs raspados p/ o pull dar fast-forward
  git pull --ff-only || echo "AVISO: git pull falhou; segue com a copia local"
  docker build -t gymscraping:local . || { echo "ERRO: build falhou"; exit 1; }

  # 1) Coleta dos 90 (root: sobrescreve CSVs; Chrome usa --no-sandbox)
  docker rm -f gym_batch_90 >/dev/null 2>&1 || true
  docker run --rm --user 0:0 -v "$REPO/Unidades:/app/Unidades" --name gym_batch_90 \
    gymscraping:local python -B executar_coletores.py --workers 3 --scheduler-policy weighted --timing

  # 1.5) Snapshot semanal (BLK-MA-06): fotografa unidades (recem-coletado aqui) + wellhub
  #      (coletado no sabado) para a serie do S3/churn e S4/staleness. UMA chamada com as
  #      DUAS fontes de proposito: o snapshot grava com delete_matching por ISO-week, entao
  #      snapshotar sabado e domingo em chamadas separadas apagaria uma a outra. || echo:
  #      falha aqui NAO aborta o lote. A guarda de coleta PARCIAL (DEC-061) vive dentro do
  #      materializador e sai `rc=4` quando reprova -- sem ela, a coleta quebrada de
  #      2026-09-13 (`selfit 231 -> 119`) teria sido fotografada com `exit 0`.
  FONTES="unidades wellhub" /opt/motor-expansao-infra/run_snapshot_concorrentes.sh || echo "snapshot semanal falhou (nao aborta o lote)"

  # 2) Relatorio de crescimento por rede (snapshot + diff + historico)
  docker run --rm --user 0:0 -v "$REPO/Unidades:/app/Unidades:ro" -v "$INFRA:/infra" \
    gymscraping:local python -B /infra/relatorio_crescimento.py

  # 3) Integracao ao motor: regen camada paralela mercado/residual (READ-ONLY M1).
  #    Roda o codigo da IMAGEM da api (DEC-022: o streamlit foi aposentado; a imagem da api tem
  #    superset das deps). A imagem ja' traz `/app/src` pelo `COPY . .` do Dockerfile, entao
  #    `PYTHONPATH=/app/src` faz `ROOT` ser `/app` SEM montar checkout nenhum.
  echo "[$(date -u)] regen mercado/residual..."
  IMG=$(docker inspect --format '{{.Image}}' motor_expansao_api 2>/dev/null)
  if [ -n "$IMG" ]; then
    docker rm -f motor_regen_weekly >/dev/null 2>&1 || true
    # DEC-059: a cadeia deixa de rodar aqui em cima do staging VIVO e passa pelo wrapper
    # versionado: rascunho -> cadeia com && -> validacao -> rename atomico -> restart ->
    # aviso no Telegram nos dois desfechos. Duas mudancas juntas, e a 2a e' pre-requisito da 1a:
    #   1) o BLOCO 3 (enriquecimento_espacial_hexagonos) entra na cadeia -- ele NAO estava
    #      aqui, entao academia coletada no domingo nao pressionava ninguem ate' alguem
    #      regenerar a mao. Custo medido (DEC-048): nove domingos sem propagar moveram
    #      5.105 hexagonos (60,46%).
    #   2) o regime de escrita muda. O bloco antigo escrevia DIRETO no staging vivo; um
    #      passo que morresse no meio deixava mercado novo + carteira velha, com exit 0.
    # O wrapper tambem roda o codigo da IMAGEM. O bloco antigo montava `$MOTOR/app:/app`
    # por cima e executava um CHECKOUT que ninguem atualiza -- em 2026-09-12 ele estava
    # velho o bastante para nao ter o proprio wrapper, e teria rodado a calibracao anterior
    # a DEC-060 (28,52%) por cima da corrigida (17,35%), toda semana, em silencio.
    if /opt/motor-expansao-infra/run_regen_mercado.sh; then
      # 4) Sync do diretorio de concorrentes que os APPS leem (BLK-CONC-SYNC-01).
      #    O mount de $REPO/Unidades acima vale SO dentro do container de regen: ele
      #    alimenta o parquet, nao o diretorio $MOTOR/concorrentes que streamlit/api/web
      #    montam em /app/concorrentes. Sem este passo o diretorio congela (ficou parado
      #    de 2026-05-28 a 2026-07-29): o Streamlit le os CSVs e perdia 68 das 107 redes
      #    no mapa, e os pins do piloto web/PDFs caiam no fallback de sigla por falta de
      #    logo_<slug>.png. O script normaliza o nome das logos do coletor e NUNCA reduz a
      #    contagem de uma rede -- coleta parcial nao apaga o que ja estava visivel.
      echo "[$(date -u)] sync do diretorio de concorrentes dos apps..."
      docker run --rm --user 0:0 -e PYTHONIOENCODING=utf-8 \
        -v "$INFRA/sync_concorrentes_dashboard.py:/tmp/sync.py:ro" \
        -v "$REPO:/gymscraping:ro" -v "$MOTOR/concorrentes:/destino" "$IMG" \
        python /tmp/sync.py --gymscraping /gymscraping --destino /destino --aplicar \
        || echo "AVISO: sync falhou; os apps seguem com os arquivos anteriores"

      # 4.5) Pins de vulnerabilidade M&A (BLK-MA-05/15/17): materializa do snapshot + carteira +
      #      concorrentes (regenerados acima). GUARDA DE VAZIO: grava em *_novo e so' PROMOVE se
      #      vier substancial. O materializador grava artefato VAZIO quando falta insumo (LEIA-ME do
      #      Vini + medido 2026-08-25), e isso NUNCA pode sobrescrever os pins bons.
      echo "[$(date -u)] materializando pins M&A..."
      SD="$MOTOR/data/staging"; OD="$MOTOR/data/outputs"
      docker rm -f motor_ma_weekly >/dev/null 2>&1 || true
      # FEEDS CRUS montados (decisao 2026-09-02): a COORDENADA dos pins e o SINAL 6 vem de
      # `coordenadas_por_chave()`/`ler_concorrentes()`, que leem os CSVs crus, NAO o snapshot.
      # O csvs/ do WellHub agora e' 100% MUSCULACAO (o coletor filtra internamente e o
      # run_wellhub_semanal.sh rotaciona o consolidado + --no-resume desde 2026-08-31, corrigindo
      # a contaminacao de 49% que empilhava a safra velha). Montar o feed produz o universo CERTO
      # (~19,6k independentes musculacao, medido em 2026-09-02), NAO os 42.862 do feed contaminado.
      # `csvs_musculacao` nunca existira: nesse modo o proprio csvs/ E' o feed de musculacao.
      # A GUARDA DE DESENHABILIDADE abaixo segue como rede: se o feed sumir, ela bloqueia a promocao.
      #
      # NAO MONTAR `$MOTOR/app:/app` AQUI. Foi o que este passo fez ate' 2026-09-17, e o mount
      # SUBSTITUI o `/app` da imagem pelo checkout congelado em 19/08 -- saida VAZIA com `exit 0`.
      # `PYTHONPATH=/app/src` e `-w /app` FICAM: o caminho da carteira e' resolvido pela
      # localizacao do PACOTE (`ROOT` derivado de `__file__`), nao pelo CWD, entao rodar de
      # `site-packages` quebra com `FileNotFoundError: /usr/local/lib/python3.11/data/outputs/...`.
      if docker run --rm --user 0:0 -e PYTHONPATH=/app/src -w /app \
           -v "$MOTOR/data:/app/data" \
           -v "$REPO/Unidades:/app/concorrentes/Unidades:ro" \
           -v "$REPO/Wellhub/csvs:/app/concorrentes/wellhub/csvs:ro" \
           --name motor_ma_weekly "$IMG" \
           python -m motor_expansao.vulnerabilidade.alvos_ma \
             --base-dir /app/data/staging/snapshots_concorrentes \
             --concorrentes /app/data/staging/concorrentes_mapeados.parquet \
             --saida-academias /app/data/staging/vulnerabilidade_ma_academias_novo.parquet \
             --saida-csv /app/data/outputs/alvos_ma_priorizados_novo.csv \
             --saida-nomeadas /app/data/staging/vulnerabilidade_ma_nomeadas_novo.parquet \
             --saida-redes /app/data/staging/vulnerabilidade_ma_redes_novo.parquet; then
        # GUARDA DE DESENHABILIDADE (incidente 2026-08-30): TAMANHO NAO BASTA. A camada com score
        # fica grande (~2 MB) mesmo com 0 pin desenhavel -- foi exatamente o que sobrescreveu os
        # pins bons em 30/08 (42.862 linhas, todas SEM coordenada). A guarda antiga so' via bytes
        # e PROMOVEU o lixo. Agora conta os pins com coordenada de fato antes de promover.
        # Em 2026-09-17 provou-se de novo: com o checkout velho montado, ela barrou 3 semanas de
        # artefato vazio (0 desenhaveis) e preservou os pins de 30/08.
        DRAW=$(docker run --rm --user 0:0 -e PYTHONPATH=/app/src \
                 -w /app -v "$MOTOR/data:/app/data" "$IMG" \
                 python -c 'import pandas as pd
try:
    d = pd.read_parquet("/app/data/staging/vulnerabilidade_ma_nomeadas_novo.parquet")
    print(int(d["lat"].notna().sum()))
except Exception:
    print(0)' 2>/dev/null | tail -1)
        echo "[$(date -u)] pins novos com coordenada (desenhaveis): ${DRAW:-0}"
        if [ -f "$SD/vulnerabilidade_ma_nomeadas_novo.parquet" ] \
           && [ "$(stat -c%s "$SD/vulnerabilidade_ma_nomeadas_novo.parquet")" -gt 500000 ] \
           && [ -f "$SD/vulnerabilidade_ma_redes_novo.parquet" ] \
           && [ "$(stat -c%s "$SD/vulnerabilidade_ma_redes_novo.parquet")" -gt 50000 ] \
           && [ "${DRAW:-0}" -ge 100 ]; then
          mv -f "$SD/vulnerabilidade_ma_nomeadas_novo.parquet" "$SD/vulnerabilidade_ma_nomeadas.parquet"
          mv -f "$SD/vulnerabilidade_ma_redes_novo.parquet"    "$SD/vulnerabilidade_ma_redes.parquet"
          mv -f "$SD/vulnerabilidade_ma_academias_novo.parquet" "$SD/vulnerabilidade_ma_academias.parquet" 2>/dev/null || true
          mv -f "$OD/alvos_ma_priorizados_novo.csv" "$OD/alvos_ma_priorizados.csv" 2>/dev/null || true
          echo "[$(date -u)] pins M&A promovidos (${DRAW} desenhaveis)"
        else
          echo "[$(date -u)] AVISO: pins M&A vazios/pequenos/sem coordenada (desenhaveis=${DRAW:-0}); mantendo os anteriores"
          rm -f "$SD"/vulnerabilidade_ma_*_novo.parquet "$OD/alvos_ma_priorizados_novo.csv"
        fi
      else
        echo "[$(date -u)] AVISO: materializador M&A falhou; mantendo pins anteriores"
        rm -f "$SD"/vulnerabilidade_ma_*_novo.parquet "$OD/alvos_ma_priorizados_novo.csv"
      fi

      # `web` entra no restart porque o piloto carrega as logos em @app.on_event("startup")
      # e cacheia o icone por rede em lru_cache: sem restart, logo nova nao aparece nele.
      echo "[$(date -u)] regen OK; restart api/bot/web"
      ( cd "$MOTOR/app" && docker compose -f docker-compose.prod.yml restart api telegram-bot web )
    else
      echo "ERRO: regen falhou; dashboard mantem os dados anteriores (sem restart)"
    fi
  else
    echo "ERRO: imagem da api nao encontrada; regen pulado"
  fi
  echo "[$(date -u)] === run_weekly_90 FIM ==="
} >>"$LOG" 2>&1
ln -sf "$LOG" "$LOGDIR/weekly_latest.log"
