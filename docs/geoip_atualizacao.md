# Atualizacao da base GeoIP do piloto (DEC-082)

> READ-ONLY sobre o M1. Pura infra de exibicao da aba Acessos. Aplicacao na VPS e' MANUAL,
> comando a comando, com confirmacao do dono (CLAUDE.md pargr. 6).

## O que e'

A aba Acessos (DEC-027 + DEC-082) carimba o PAIS do IP de quem acessa sem conta e marca
"fora do pais", em atipicos e rajadas. O pais vem de uma base MaxMind-mmdb lida em runtime
pela lib `maxminddb` (`acesso_analytics.pais_do_ip`). E' OPCIONAL: sem a env `MOTOR_GEOIP_DB`
(ou sem a lib, ou base ilegivel) o pais degrada para "n/d" e nada quebra.

Base: **DB-IP Country Lite**, licenca **CC BY** (atribuicao obrigatoria -- ver no fim),
atualizada MENSALMENTE, ~4 MB compactada. Um so' arquivo serve BR e AR (o `web_ar` monta o
mesmo diretorio `:ro`).

## Instalacao (uma vez, VPS, manual)

1. **Imagem com a lib.** Esta DEC adiciona `maxminddb` a imagem `web` (grupo `geoip` no
   `pyproject` + `Dockerfile.web`). Precisa de deploy da imagem `web` nova por digest, BR e AR
   (ver `docs/deploy_piloto_web.md`). Antes disso, GeoIP fica desligado (degrada) -- ok.
2. **Diretorio da base + mount.** `mkdir -p /opt/motor-expansao/data/geoip`. Os composes
   (`docker-compose.prod.yml` e `docker-compose.ar.yml`) ja' montam esse diretorio `:ro` em
   `/app/data/geoip` (kit de compose da VPS).
3. **Envs no `.env` da VPS:**
   ```
   MOTOR_GEOIP_DB=/app/data/geoip/dbip-country-lite.mmdb
   MOTOR_GEOIP_DB_AR=/app/data/geoip/dbip-country-lite.mmdb
   ```
4. **1a carga:** rodar `scripts/cron/run_geoip_update.sh` uma vez (como root). Ele baixa,
   valida DENTRO do container, publica por rename atomico e reinicia `web`+`web_ar`.
5. **Conferir:** abrir a aba Acessos e ver o pais nos atipicos/rajadas; ou
   `/opt/motor-monitoring/healthcheck_vps.sh geoip` (deve dar OK).

## Cron mensal

Instalar no crontab do root (DB-IP publica no inicio do mes; dia 3 da' folga):

```
0 4 3 * * /opt/.../run_geoip_update.sh
```

O script e' idempotente e seguro: falha em qualquer passo deixa a base viva intacta e sai
!= 0. Log em `/var/log/motor-snapshots/geoip_latest.log`.

## Monitor

`healthcheck_vps.sh geoip` -- idade da base, limiar `GEOIP_MAX_DIAS=45`. Base que NUNCA
existiu = FAIL (GeoIP ainda nao instalado). Agendar junto dos outros monitores.

## Reversao

Esvaziar `MOTOR_GEOIP_DB` / `MOTOR_GEOIP_DB_AR` no `.env` e reiniciar (ou remover a base):
a aba volta a `pais = n/d`, SEM rebuild. Nenhum artefato a regenerar.

## Privacidade

A base NAO tem PII -- e' um mapa publico faixa-de-IP -> pais. O IP segue so' como contagem
de distintos na aba (DEC-027); o pais e' derivado.

## Atribuicao (obrigatoria -- CC BY)

A DB-IP Country Lite e' distribuida sob **CC BY 4.0**. Manter o credito a **DB-IP**
(<https://db-ip.com>) onde a base for citada (este runbook cumpre a atribuicao no repo).
