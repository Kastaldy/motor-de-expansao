# Infraestrutura de Produção — Motor de Expansão Ultra Academia

## Visão geral

| Componente | Valor |
|---|---|
| Provedor | Hostinger KVM4 |
| IP | 2.25.137.241 |
| Domínio | ultra-expansao.tech |
| Dashboard | https://dashboard.ultra-expansao.tech |
| Portal de login | https://auth.ultra-expansao.tech |
| SO | Ubuntu 22.04 LTS |
| Recursos | 4 vCPU, 16 GB RAM, 200 GB NVMe, 4 GB swap |

## Stack

- **Streamlit** — dashboard Python, container `motor_expansao_streamlit`
- **Caddy** — reverse proxy com TLS automático (Let's Encrypt), container `motor_expansao_caddy`
- **Authelia 4.38** — autenticação self-hosted (login + 2FA opcional), container `motor_expansao_authelia`

Todos os containers sobem com `docker compose -f docker-compose.prod.yml`.

## Acesso SSH

```bash
ssh -i ~/.ssh/id_ultra root@2.25.137.241
```

Chave privada local: `~/.ssh/id_ultra` (Windows: `C:\Users\Felipe Silva\.ssh\id_ultra`)

---

## Atualizar o dashboard (modo PULL, sem build)

> Modelo PULL: o VPS PUXA a imagem publicada no GHCR pelo job `publish` do workflow `CI`
> (`.github/workflows/ci.yml`). NAO se faz `--build` no servidor. Runbook canonico: `docs/deploy.md`.
> GUARDRAIL CLAUDE.md §6: execucao no VPS e SEMPRE passo humano, comando a comando.

```bash
cd /opt/motor-expansao/app

# 1. Pinar a imagem por DIGEST imutavel (recomendado p/ producao). Obter o digest:
#    - do output "Digest imutavel publicado:" do job publish no Actions, ou
#    - via: docker buildx imagetools inspect \
#        ghcr.io/kastaldy/motor-de-expansao/motor-expansao-streamlit:sha-<commit>
export STREAMLIT_IMAGE=ghcr.io/kastaldy/motor-de-expansao/motor-expansao-streamlit@sha256:<digest>

# 2. Pull + up -d SOMENTE do streamlit (SEM --build)
docker compose -f docker-compose.prod.yml pull streamlit
docker compose -f docker-compose.prod.yml up -d streamlit

# 3. Conferir saude
docker compose -f docker-compose.prod.yml ps
curl -fsS http://127.0.0.1:8501/_stcore/health
```

- Caddy e Authelia **nao** reiniciam.
- Dados em `/opt/motor-expansao/data/outputs/` sao preservados (bind mount read-only).
- Se o pacote GHCR for privado, autenticar antes: `docker login ghcr.io` com PAT `read:packages`
  (credencial de runtime do servidor; NUNCA no repo). Ver `docs/deploy.md`.

---

## Rollback (por digest imutavel, SEM rebuild)

Para voltar a imagem anterior conhecida sem reconstruir nada:

```bash
cd /opt/motor-expansao/app

# 1. Apontar para o DIGEST imutavel do deploy anterior (anote sempre o digest vigente
#    antes de atualizar; ou recupere via imagetools inspect da tag sha-<commit_anterior>)
export STREAMLIT_IMAGE=ghcr.io/kastaldy/motor-de-expansao/motor-expansao-streamlit@sha256:<digest_anterior>

# 2. Pull + up -d (SEM --build)
docker compose -f docker-compose.prod.yml pull streamlit
docker compose -f docker-compose.prod.yml up -d streamlit

# 3. Conferir
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs --tail=80 streamlit
```

- Digest imutavel (`@sha256:...`) garante reproducao byte-identica da imagem anterior; a tag
  `sha-<commit>` tambem e rastreavel, mas o digest e o pin canonico.
- Rollback NAO usa `--build` (nada e reconstruido no servidor).

---

## Atualizar parquets de dados

Os parquets não estão no git. Para atualizar no servidor após rodar o pipeline localmente:

### Arquivo específico

```powershell
scp -i "$env:USERPROFILE\.ssh\id_ultra" data/outputs/ARQUIVO.parquet root@2.25.137.241:/opt/motor-expansao/data/outputs/
```

### Diretório particionado (ex: enriquecido por UF)

```powershell
scp -i "$env:USERPROFILE\.ssh\id_ultra" -r data/outputs/hexagonos_dashboard_enriquecido root@2.25.137.241:/opt/motor-expansao/data/outputs/
```

### Todos os outputs de uma vez

```powershell
# Atenção: rodar de dentro do diretório do projeto
cd "C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao"
scp -i "$env:USERPROFILE\.ssh\id_ultra" data/outputs/brasil_estrutural.parquet root@2.25.137.241:/opt/motor-expansao/data/outputs/
scp -i "$env:USERPROFILE\.ssh\id_ultra" data/outputs/brasil_priorizados.parquet root@2.25.137.241:/opt/motor-expansao/data/outputs/
scp -i "$env:USERPROFILE\.ssh\id_ultra" data/outputs/hexagonos_brasil_dashboard.parquet root@2.25.137.241:/opt/motor-expansao/data/outputs/
scp -i "$env:USERPROFILE\.ssh\id_ultra" data/outputs/hexagonos_mapa_sample.parquet root@2.25.137.241:/opt/motor-expansao/data/outputs/
scp -i "$env:USERPROFILE\.ssh\id_ultra" -r data/outputs/hexagonos_dashboard_enriquecido root@2.25.137.241:/opt/motor-expansao/data/outputs/
```

O Streamlit lê do volume na próxima requisição — **não é necessário reiniciar o container**.

---

## Integração com gymscraping (repo separado)

> **Status (2026-06):** a coleta de concorrentes roda **automatizada e semanal na própria VPS**
> (a antiga "Opção B" foi implementada). É camada paralela mercado/residual, **READ-ONLY sobre o M1**
> (não recalcula `score_priorizacao`, `hex_score_estrutural` nem regenera artefatos M1 oficiais). Ver
> **DEC-013** em `CLAUDE.md` §8.

### Arquitetura (o que roda toda semana)

- **Repo do scraper:** `VinhoAbencoado/GymScraping` (privado; 90 coletores centrais + agregadores WellHub/TotalPass).
  Clonado em **`/opt/gymscraping`** via **deploy key read-only** (`/root/.ssh/gymscraping_deploy`, host SSH
  `github-gymscraping` em `/root/.ssh/config`). O `git pull` semanal traz coletores novos automaticamente.
- **Imagem:** `gymscraping:local` — `Dockerfile` no próprio repo do scraper (Chrome + webdriver-manager +
  Chromium do Playwright). Reconstruída a cada run (cache acelera).
- **Runner:** **`/opt/gymscraping-infra/run_weekly_90.sh`** (infra na VPS, fora do repo). Faz, em sequência:
  1. `git pull` + `docker build`;
  2. **Coleta** dos 90 (`executar_coletores.py --workers 3 --scheduler-policy weighted`, container `--user 0:0`);
  3. **Relatório de crescimento por rede** (`/opt/gymscraping-infra/relatorio_crescimento.py`): snapshot
     `contagem_atual.csv`, diff vs. `contagem_anterior.csv` (delta por rede), histórico `historico_contagem.csv`
     e `relatorio_crescimento_<data>.txt`;
  4. **Integração ao motor** (regen camada paralela, READ-ONLY M1 — ver abaixo);
  5. **Sync do diretório de concorrentes dos apps** (`sync_concorrentes_dashboard.py` — ver abaixo);
  6. **Restart** de `streamlit`/`api`/`telegram-bot`/`web`.
- **Cron:** `0 6 * * 0` (domingo **06:00 UTC = 03:00 BRT**; o servidor é UTC). `crontab -l` no root.
- **Logs:** `/var/log/gymscraping/weekly_<TS>.log` (+ symlink `weekly_latest.log`).

### Integração ao motor (regen mercado/residual — READ-ONLY M1)

A coleta atualiza só os CSVs `Unidades/unidades_<rede>.csv`. A propagação para o dashboard roda a cadeia
**paralela** via o checkout do motor em **`/opt/motor-expansao/app`** (imagem do `streamlit`, `PYTHONPATH=/app/src`,
`ROOT=/app`, dados em `/app/data`):

```
normalizar_concorrentes → calcular_colunas_mercado → gerar_carteira_acionavel →
gerar_plano_expansao_curto_prazo → gerar_plano_expansao_dominio →
enriquecer_outputs_residual_mercado → fase1_bi_exports.materialize_enriched_dashboard()
```

Usa-se **`materialize_enriched_dashboard()`** (só o artefato enriquecido derivado), **não** o `main()` do
`fase1_bi_exports` — assim **não recompõe** os artefatos oficiais do M1 (`hexagonos_brasil_dashboard.parquet`
permanece intocado). Insumos de staging M1/censitário necessários à cadeia foram enviados **uma vez** por `scp`
para `/opt/motor-expansao/data/staging/` (`censo2022_setores_calibrado` + variantes, `brasil_estrutural`,
`unidades_ultra_performance_hex`; ~68 MB).

**Gotcha de permissão:** os containers de coleta/regen rodam como **`--user 0:0` (root)** — os CSVs/parquets no
host são de root e o usuário não-root da imagem não consegue sobrescrevê-los; o Chrome já usa `--no-sandbox`.

### Sync do diretório de concorrentes dos apps (BLK-CONC-SYNC-01)

> **Por que existe:** o mount `$REPO/Unidades:/app/concorrentes:ro` do passo anterior vale **só dentro do
> container de regen** — ele alimenta o *parquet*. O diretório **`/opt/motor-expansao/concorrentes`**, que os
> serviços `streamlit`, `api` e `web` montam em `/app/concorrentes`, **não era tocado por ninguém**. Medido em
> 2026-07-29: estava congelado desde 2026-05-28 com 39 CSVs e 39 logos, enquanto o parquet já tinha 106 redes.
> Efeito visível: o Streamlit (que lê os CSVs, não o parquet) perdia **68 das 107 redes** no mapa, e os pins do
> piloto web e dos PDFs caíam no **fallback de sigla** por falta de `logo_<slug>.png`.

O passo roda `scripts/sync_concorrentes_dashboard.py` (cópia instalada em `/opt/gymscraping-infra/`) dentro da
imagem do `streamlit`, com `GymScraping` em `:ro` e o diretório dos apps como destino. Duas regras importam:

- **Normalização de nome:** o coletor guarda parte das artes fora do padrão (`AD3_logo.png`, `Malibu_logo.png`,
  `companhiafit_logo.png`). O canônico é sempre `logo_<slug>.png`, definido por `COMPETITOR_LOGO_FILES`; o
  casamento é por chave compacta, com desempate por prefixo. Rede sem arte fica sem logo **de propósito** (o pin
  cai na sigla) — hoje são 10 das 107.
- **Nunca reduzir:** por rede, vence a fonte com **mais** unidades válidas entre o destino atual e a coleta,
  contando com o mesmo parser do app. Uma coleta parcial (já houve domingo com 45/106 redes) não pode apagar o
  que estava visível em produção.

> **Custo conhecido da regra "nunca reduzir":** unidade que **fecha de verdade** não sai sozinha do diretório —
> a contagem do destino só sobe. O `relatorio_crescimento_<data>.txt` é quem mostra a queda real por rede; se
> ele acusar retração sustentada em alguma rede, forçar a coleta por cima com
> `cp /opt/gymscraping/Unidades/unidades_<slug>.csv /opt/motor-expansao/concorrentes/` e reiniciar os apps.
> Vale lembrar que isso é a camada **visual** (§2) — o `concorrentes_mapeados.parquet`, que alimenta o piloto
> web e os PDFs, é regerado do zero pelo `normalizar_concorrentes` toda semana e não herda esse acúmulo.

O `web` entra no restart porque o piloto carrega as logos em `@app.on_event("startup")` e cacheia o ícone por
rede em `lru_cache` — sem restart, logo nova não aparece nele. Rodar sob demanda (é idempotente):

```bash
IMG=$(docker inspect --format '{{.Image}}' motor_expansao_streamlit)
docker run --rm --user 0:0 -e PYTHONIOENCODING=utf-8 \
  -v /opt/gymscraping-infra/sync_concorrentes_dashboard.py:/tmp/sync.py:ro \
  -v /opt/gymscraping:/gymscraping:ro -v /opt/motor-expansao/concorrentes:/destino \
  "$IMG" python /tmp/sync.py --gymscraping /gymscraping --destino /destino   # --aplicar para escrever
```

> **Ao mexer no script versionado, reinstalar a cópia da VPS** (`scp` para `/opt/gymscraping-infra/`, com
> **LF**): o runner não faz `git pull` do checkout do motor, então `scripts/` do repo não chega lá sozinho.

### Operação manual / troubleshooting

```bash
# rodar o ciclo semanal sob demanda (cuidado: ~2h de coleta)
/opt/gymscraping-infra/run_weekly_90.sh

# acompanhar
tail -f /var/log/gymscraping/weekly_latest.log

# ver o crescimento por rede da última execução
cat /opt/gymscraping-infra/relatorio_crescimento_*.txt | tail -100
```

Falhas individuais de coletor **não** abortam o lote; redes que falham mantêm o CSV anterior e aparecem como
"defasadas" no relatório de crescimento. Se o regen falhar, o dashboard mantém os dados anteriores (sem restart).
**Nota:** o runner **não** faz `git pull` do checkout do motor (`/opt/motor-expansao/app`) para não conflitar
com o deploy; se os pipelines da cadeia mudarem, re-sincronizar o checkout manualmente.

> **Pendentes (futuro):** cron **mensal** dos agregadores WellHub/TotalPass (~20h, invocação separada);
> integração deles ao residual com remodelagem (Huff por tipo de rede + dedup) usando as bases `NAO_ABRA/`.

### Ingestão DIÁRIA da Growth API (Visão Executiva do piloto web)

A **Visão Executiva** do piloto web (`/api/executiva/{uf}`) lê `data/staging/growth_api_historico.parquet`
(rede Ultra real por UF — faturamento/ativos/pagantes/churn/NPS + split pagantes×agregadores). Os dados da
Growth **atualizam todo dia**, então a ingestão é **diária** (não semanal como o GymScraping).

- **Script canônico (repo):** `scripts/ingerir_growth_api.py` (ganhou `--out`/env `GROWTH_OUT_PARQUET` para
  escrever fora do staging read-only). **Wrapper de cron:** `scripts/cron/run_growth_daily.sh`.
- **Cron sugerido (root, servidor em UTC):** `30 6 * * *` (06:30 UTC = 03:30 BRT; fora da janela dom 06:00 do
  GymScraping). Logs em `/var/log/growth/daily_<TS>.log` (+ symlink `daily_latest.log`).
- **Fluxo do wrapper (one-shot, sem tocar na API viva):** (1) `docker run --rm` de um container **efêmero** com a
  **imagem da API** (que já tem o motor + `scripts/ingerir_growth_api.py`), `--env-file` com as credenciais e o
  **staging do host montado READ-WRITE** — ele lê o perf parquet e escreve `growth_api_historico.parquet` direto no
  staging (os containers de longa duração montam o staging `:ro`, por isso o one-shot); (2) `docker restart
  motor_expansao_web` (limpa o `lru_cache` de `_carregar_growth` e passa a servir o dado novo). Nenhum segredo mora
  no container da API/bot; a API não reinicia.
- **Detalhes do one-shot:** roda como **`--user 0:0` (root)** — a imagem roda como `appuser(1000)`, mas o staging e
  o cache do host são `root:root`, então sem root o `to_parquet` falha com `PermissionError`. Monta um **cache
  persistente** do host (`data/cache/growth_api`, = `config.CACHE_DIR`) para o **backfill de 52 meses não se repetir**:
  o run diário só re-busca o mês corrente (cache hit no resto) → rápido apesar do rate limit da Growth (10 req/5 min).
- **⚠️ PRÉ-REQUISITO (uma vez):** o arquivo de credenciais em `/opt/motor-expansao-infra/growth.env` (root-only,
  `chmod 600`) com `GROWTH_API_USUARIO=...` e `GROWTH_API_SENHA=...`. Sem ele a ingestão aborta com "Credenciais
  ausentes" e a Visão Executiva fica **404**. A chave **nunca** entra no repo/script.
- **READ-ONLY sobre o M1** (camada Growth paralela, sem PII — `assert_sem_pii` antes de persistir; DEC-013).

### Transferir data/ultra (base Ultra)

```powershell
scp -i "$env:USERPROFILE\.ssh\id_ultra" -r data/ultra/ root@2.25.137.241:/opt/motor-expansao/data/ultra/
```

---

## Gerenciar usuários do dashboard

### Adicionar usuário

1. Gerar hash da senha no servidor:
   ```bash
   docker run --rm authelia/authelia:4.38 authelia crypto hash generate argon2 --password 'SenhaNova'
   ```
2. Editar o arquivo de usuários:
   ```bash
   nano /opt/motor-expansao/app/authelia/users_database.yml
   ```
3. Adicionar bloco:
   ```yaml
   novousuario:
     displayname: "Nome Completo"
     password: "$argon2id$v=19$... (hash gerado)"
     email: email@ultraacademia.com.br
     groups:
       - ultra_team
   ```
4. Reiniciar Authelia:
   ```bash
   cd /opt/motor-expansao/app && docker compose -f docker-compose.prod.yml restart authelia
   ```

### Revogar usuário

1. Editar `authelia/users_database.yml` e remover o bloco do usuário
2. `docker compose -f docker-compose.prod.yml restart authelia`

### Trocar senha de usuário

1. Gerar novo hash (passo 1 acima)
2. Substituir o campo `password:` do usuário em `users_database.yml`
3. Reiniciar Authelia

---

## Hardening do servidor (BLK-SEC-03, aplicado 2026-07-13)

Estado após o hardening — cada item com seu rollback:

| Controle | Estado | Onde / rollback |
|---|---|---|
| Firewall | `ufw` ativo, só 22/80/443 (v4+v6) | já existia; `ufw status` |
| SSH sem senha | `PasswordAuthentication no` + `PermitRootLogin prohibit-password` | `/etc/ssh/sshd_config.d/00-hardening.conf` (prefixo `00-` vence os demais — sshd usa o PRIMEIRO valor). Rollback: remover o arquivo + `systemctl reload ssh` (pelo console web da Hostinger se preciso) |
| fail2ban | jail `sshd` ativa (ban 30 min / 5 tentativas / 10 min, backend systemd) | `/etc/fail2ban/jail.local`; `fail2ban-client status sshd` |
| Patches automáticos | `unattended-upgrades` diário (só security) | `/etc/apt/apt.conf.d/20auto-upgrades`; log em `/var/log/unattended-upgrades/` |
| Kernel | reboot aplicado em 2026-07-13 (5.15.0-177 → 185) | ver política abaixo |

**Acesso de emergência (porta dos fundos):** hPanel Hostinger → VPS → Gerenciar → **"Terminal do
navegador"** — login `root` + senha root (login de console, NÃO passa pelo sshd; continua aceitando
senha mesmo com o SSH endurecido). Senha root redefinível em VPS → Configurações. Validado em
2026-07-13. **Sempre validar esse acesso ANTES de mexer em SSH/firewall.**

**Chaves SSH autorizadas:** somente a chave `ed25519` da máquina do Felipe (`silva@Ultra-2025-032`).
Para dar acesso a alguém: adicionar a chave pública da pessoa em `/root/.ssh/authorized_keys`
(senha NÃO volta a ser opção). Offboarding: remover a linha da chave.

**Política de reboot (kernel):** o `unattended-upgrades` instala kernels de segurança mas NÃO
reinicia sozinho. Quando o banner/`/var/run/reboot-required` acusar, agendar reboot manual (~2 min de
indisponibilidade; containers voltam sozinhos — comprovado em 2026-07-13). O monitoramento
(BLK-SEC-05) alerta se algo não voltar.

**Pendente (follow-up BLK-SEC-03-FU1):** forçar 2FA no Authelia para o `ultra_team` + revisão de
acesso — exige o time presente para cadastrar TOTP; agendar com aviso prévio.

---

## Monitoramento e manutenção

### Ver status dos containers

```bash
cd /opt/motor-expansao/app && docker compose -f docker-compose.prod.yml ps
```

### Ver logs em tempo real

```bash
docker compose -f docker-compose.prod.yml logs -f streamlit
docker compose -f docker-compose.prod.yml logs -f caddy
docker compose -f docker-compose.prod.yml logs -f authelia
```

### Verificar uso de memória

```bash
docker stats --no-stream
free -h
```

### Reiniciar um serviço específico

```bash
docker compose -f docker-compose.prod.yml restart streamlit
docker compose -f docker-compose.prod.yml restart authelia
docker compose -f docker-compose.prod.yml restart caddy
```

### Reiniciar tudo

```bash
cd /opt/motor-expansao/app && docker compose -f docker-compose.prod.yml down && docker compose -f docker-compose.prod.yml up -d
```

### Verificar espaço em disco

```bash
df -h /
du -sh /opt/motor-expansao/data/outputs/
```

### Alertas automáticos (BLK-SEC-05)

Monitoramento leve por cron + bot Telegram (reusa o bot de produção; alertas vão para o
grupo de ops — `MONITOR_TELEGRAM_CHAT_ID` no `.env`). Script versionado no repo em
`scripts/healthcheck_vps.sh`, instalado em `/opt/motor-monitoring/healthcheck_vps.sh`.

O que é vigiado e a cadência (crontab do root):

```cron
*/5 * * * * /opt/motor-monitoring/healthcheck_vps.sh containers  # 5 containers + edge HTTPS
0 * * * *   /opt/motor-monitoring/healthcheck_vps.sh host        # disco >80% / memória <10%
0 11 * * *  /opt/motor-monitoring/healthcheck_vps.sh authelia    # resumo diário de falhas de login (08h BRT)
0 18 * * 0  /opt/motor-monitoring/healthcheck_vps.sh coleta      # domingo 15h BRT: resumo/falha da coleta semanal
```

Comportamento anti-spam: alerta na transição OK→FAIL, lembrete a cada 1h enquanto durar,
e aviso de recuperação no FAIL→OK (estado em `/var/lib/motor-monitoring/`). Logs em
`/var/log/motor-monitoring/healthcheck.log`. Teste manual: `healthcheck_vps.sh test`.

Segredos: o script lê `API_TELEGRAM_TOKEN` e `MONITOR_TELEGRAM_CHAT_ID` do `.env` em
runtime; token nunca aparece em log/alerta. A rotação de logs do Docker já é feita pelo
daemon (`/etc/docker/daemon.json`, json-file 10m×3) — não é papel deste script.

---

## Runbook de incidente

Proporcional a um dashboard interno — 3 cenários. Em todos: **quem aciona é quem viu o
alerta primeiro** (grupo de ops); Felipe é o dono da decisão de contenção.

**1. Indisponibilidade (dashboard/API/bot fora do ar).**
Diagnóstico: `docker compose -f docker-compose.prod.yml ps` + logs do serviço caído.
Ação: restart do serviço (seção acima). Se o restart não segurar (crash-loop), rollback
de imagem por digest (seção "Rollback"). Se o host estiver sem recurso (disco/memória do
alerta de host): liberar espaço (`docker system prune`, logs antigos) antes de reiniciar.

**2. Suspeita de comprometimento (login anômalo no Authelia, processo estranho, tráfego
inesperado).**
Contenção imediata: `ufw deny 80 && ufw deny 443` (derruba o edge, preserva SSH para
forense) — decisão de Felipe. Coletar evidência ANTES de reiniciar qualquer coisa:
`docker logs` dos containers, `last`, `journalctl -u ssh --since "-48h"`.
Se houver risco de credencial vazada: rotacionar segredos pelo runbook de DR do
BLK-OPS-01 (`docs/backup_restore.md`) — todos os segredos têm regeneração documentada.
Reinstalar/recriar containers só a partir de imagens do GHCR (pinadas por digest).

**3. Perda/corrupção de dados (parquets).**
Enquanto o BLK-SEC-04 não entrega o backup automatizado: restaurar por `scp` da cópia
local da máquina de dev (seção "Atualizar parquets de dados") ou regenerar pelos
pipelines. Sessões do bot (`bot_data`) são descartáveis (usuários apenas deslogam).

Ligações: DR de segredos = `docs/backup_restore.md` (BLK-OPS-01); backup de dados =
BLK-SEC-04 (pendente); hardening preventivo = BLK-SEC-03.

---

## Renovação de certificados TLS

Caddy renova os certificados Let's Encrypt automaticamente. Nenhuma ação manual necessária. Para verificar:

```bash
docker compose -f docker-compose.prod.yml logs caddy | grep -i "certificate\|tls"
```

---

## Estrutura de diretórios no servidor

```
/opt/motor-expansao/
├── app/                          # Código-fonte (git clone)
│   ├── docker-compose.prod.yml
│   ├── Dockerfile.streamlit
│   ├── Caddyfile                 # NÃO está no git
│   ├── .env                      # NÃO está no git
│   ├── authelia/
│   │   ├── configuration.yml     # NÃO está no git
│   │   ├── users_database.yml    # NÃO está no git
│   │   └── db.sqlite3            # banco de sessões Authelia
│   ├── streamlit_app.py
│   ├── src/
│   └── dashboard/
└── data/
    ├── outputs/                  # Parquets do M1 (~1,6 GB)
    │   ├── hexagonos_brasil_dashboard.parquet
    │   ├── hexagonos_dashboard_enriquecido/
    │   │   └── uf=XX/
    │   └── ...
    └── ultra/                    # Base Ultra (CSV legado)
```

### Arquivos que NÃO estão no git (existem apenas no servidor)

| Arquivo | Conteúdo |
|---|---|
| `app/Caddyfile` | Configuração do Caddy com domínio real |
| `app/.env` | Segredos Authelia |
| `app/authelia/configuration.yml` | Configuração Authelia com domínio real |
| `app/authelia/users_database.yml` | Usuários e hashes de senhas |
| `data/outputs/` | Todos os parquets (~1,6 GB) |
| `data/ultra/` | Base Ultra.csv |

**Importante:** antes de qualquer `git pull`, confirme que esses arquivos não foram sobrescritos.

---

## Cuidados e boas práticas

- **Nunca commitar** `.env`, `Caddyfile`, `authelia/users_database.yml` ou `authelia/configuration.yml` com dados reais
- **Backup dos parquets:** manter cópia local em `data/outputs/` na máquina de desenvolvimento
- **Scrapers M2/M3:** agendar em janela noturna 2h–5h BRT para não competir com usuários ativos
- **Memória:** limite de 10 GB no container Streamlit + 4 GB swap; monitorar com `docker stats` se houver lentidão
- **Atualizações de sistema:** rodar mensalmente `apt-get update && apt-get upgrade -y` no servidor
