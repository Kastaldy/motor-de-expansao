# Infraestrutura de Produção — Motor de Expansão Ultra Academia

## Visão geral

| Componente | Valor |
|---|---|
| Provedor | Hostinger KVM4 |
| IP | 2.25.137.241 |
| Domínio | ultra-expansao.tech |
| Piloto (app de produção) | https://piloto.ultra-expansao.tech |
| Tiles (basemap self-host) | https://dashboard.ultra-expansao.tech/tiles/* |
| Portal de login | https://auth.ultra-expansao.tech |
| SO | Ubuntu 22.04 LTS |
| Recursos | 4 vCPU, 16 GB RAM, 200 GB NVMe, 4 GB swap |

> **DEC-022 (2026-08-03):** o dashboard Streamlit foi aposentado; o app de produção é o
> **piloto web** (`web/` — SPA React/Vite + FastAPI). O subdomínio
> `dashboard.ultra-expansao.tech` segue vivo **apenas** como host de `/tiles/*` (o
> tileserver que alimenta o basemap dos PDFs de api, web e bot; `publicUrl` e styles do
> openmaptiles INALTERADOS) — a raiz do subdomínio redireciona **301** para
> `piloto.ultra-expansao.tech`.

## Stack

- **web (SPA + FastAPI)** — piloto web (React/Vite + FastAPI num único container, porta interna `8899`), container `motor_expansao_web`
- **API GeoEspacial + bot Telegram** — containers `motor_expansao_api` e `motor_expansao_telegram_bot` (mesma imagem; ver `docs/deploy_api_bot.md`)
- **Caddy** — reverse proxy com TLS automático (Let's Encrypt), container `motor_expansao_caddy`
- **Authelia 4.38** — autenticação self-hosted (login + 2FA opcional), container `motor_expansao_authelia`

Todos os containers sobem com `docker compose -f docker-compose.prod.yml`.

## Acesso SSH

```bash
ssh -i ~/.ssh/id_ultra root@2.25.137.241
```

Chave privada local: `~/.ssh/id_ultra` (Windows: `C:\Users\Felipe Silva\.ssh\id_ultra`)

---

## Atualizar o web (modo PULL, sem build)

> Modelo PULL: o VPS PUXA a imagem publicada no GHCR pelo job `publish-web` do workflow `CI`
> (`.github/workflows/ci.yml` — roda no push da `main`, com path-filter). NAO se faz
> `--build` no servidor. Runbook canonico: `docs/deploy_piloto_web.md`.
> GUARDRAIL CLAUDE.md §6: execucao no VPS e SEMPRE passo humano, comando a comando.

```bash
cd /opt/motor-expansao/app

# 1. Pinar a imagem por DIGEST imutavel no .env (o compose EXIGE WEB_IMAGE — fail-closed).
#    Obter o digest:
#    - do output "WEB digest imutavel publicado:" do job publish-web no Actions, ou
#    - via: docker buildx imagetools inspect \
#        ghcr.io/kastaldy/motor-de-expansao/motor-expansao-web:sha-<commit>
#    No .env: WEB_IMAGE=ghcr.io/kastaldy/motor-de-expansao/motor-expansao-web@sha256:<digest>

# 2. Pull + up -d SOMENTE do web (SEM --build)
docker compose -f docker-compose.prod.yml pull web
docker compose -f docker-compose.prod.yml up -d web

# 3. Conferir saude (o web NAO expoe porta no host — checar de dentro do container)
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml exec web curl -fsS http://127.0.0.1:8899/api/health
```

- Caddy e Authelia **nao** reiniciam.
- API e bot seguem o mesmo modelo com `API_IMAGE` — ver `docs/deploy_api_bot.md`.
- Dados em `/opt/motor-expansao/data/outputs/` sao preservados (bind mount read-only).
- Se o pacote GHCR for privado, autenticar antes: `docker login ghcr.io` com PAT `read:packages`
  (credencial de runtime do servidor; NUNCA no repo). Ver `docs/deploy_piloto_web.md`.

---

## Rollback (por digest imutavel, SEM rebuild)

Para voltar a imagem anterior conhecida sem reconstruir nada:

```bash
cd /opt/motor-expansao/app

# 1. Apontar o .env para o DIGEST imutavel do deploy anterior (anote sempre o digest
#    vigente antes de atualizar; ou recupere via imagetools inspect da tag sha-<commit_anterior>)
#    No .env: WEB_IMAGE=ghcr.io/kastaldy/motor-de-expansao/motor-expansao-web@sha256:<digest_anterior>

# 2. Pull + up -d (SEM --build)
docker compose -f docker-compose.prod.yml pull web
docker compose -f docker-compose.prod.yml up -d web

# 3. Conferir
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs --tail=80 web
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

O web lê do volume na próxima requisição — em geral **não é necessário reiniciar o container**.
Exceção: dados que o backend cacheia em memória (`lru_cache` — ex.: Growth, logos de
concorrentes) só aparecem após `docker compose -f docker-compose.prod.yml restart web`.

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
  6. **Restart** de `api`/`telegram-bot`/`web` (o `streamlit` saiu da lista com a DEC-022).
- **Cron:** `0 6 * * 0` (domingo **06:00 UTC = 03:00 BRT**; o servidor é UTC). `crontab -l` no root.
- **Logs:** `/var/log/gymscraping/weekly_<TS>.log` (+ symlink `weekly_latest.log`).

### Integração ao motor (regen mercado/residual — READ-ONLY M1)

A coleta atualiza só os CSVs `Unidades/unidades_<rede>.csv`. A propagação para os apps roda a cadeia
**paralela** via o checkout do motor em **`/opt/motor-expansao/app`** (imagem da `api`, que carrega o motor
completo — desde a DEC-022; antes rodava na imagem do `streamlit` —, `PYTHONPATH=/app/src`,
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
> serviços `api` e `web` montam em `/app/concorrentes`, **não era tocado por ninguém**. Medido em
> 2026-07-29: estava congelado desde 2026-05-28 com 39 CSVs e 39 logos, enquanto o parquet já tinha 106 redes.
> Efeito visível: o Streamlit (que lê os CSVs, não o parquet) perdia **68 das 107 redes** no mapa, e os pins do
> piloto web e dos PDFs caíam no **fallback de sigla** por falta de `logo_<slug>.png`.

O passo roda `scripts/sync_concorrentes_dashboard.py` (cópia instalada em `/opt/gymscraping-infra/`) dentro da
imagem da `api`, com `GymScraping` em `:ro` e o diretório dos apps como destino. Duas regras importam:

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
IMG=$(docker inspect --format '{{.Image}}' motor_expansao_api)
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
"defasadas" no relatório de crescimento. Se o regen falhar, os apps mantêm os dados anteriores (sem restart).
**Nota:** o runner **não** faz `git pull` do checkout do motor (`/opt/motor-expansao/app`) para não conflitar
com o deploy; se os pipelines da cadeia mudarem, re-sincronizar o checkout manualmente.

> **Pendentes (futuro):** integração dos agregadores ao residual com remodelagem (Huff por tipo de
> rede + dedup) usando as bases `NAO_ABRA/`. *(O cron **semanal** dos agregadores saiu desta lista
> no BLK-MA-21 — tem script versionado e seção própria abaixo.)*

### Snapshot semanal de concorrentes (BLK-MA-06 — insumo de churn/staleness)

**Por que existe.** O runner **sobrescreve** os CSVs crus a cada coleta: toda semana não fotografada
está perdida **para sempre**. O snapshot é o produtor da série que os sinais **S3 (churn)** e
**S4 (staleness)** do score de vulnerabilidade consomem. READ-ONLY sobre o M1 — escreve só em
`data/staging/snapshots_concorrentes/semana=AAAA-SS/`.

**Script versionado:** `scripts/cron/run_snapshot_concorrentes.sh` (mesmo molde do
`run_growth_daily.sh`: container efêmero na imagem da `api`, `--user 0:0`, concorrentes montado
`:ro`). Instalação e a linha a inserir no `run_weekly_90.sh` estão no cabeçalho do próprio script.

**`--fontes unidades`, e isto NÃO é detalhe de configuração.** O runner de domingo recoleta só os 90
coletores, que atualizam `Unidades/unidades_<rede>.csv`; WellHub e TotalPass são recoletados pelo
cron **semanal dos agregadores**, na terça (seção própria abaixo). **Fotografar um feed que não foi recoletado é pior do que não
fotografar:** o `hash_campos_raspados` sai idêntico semana após semana, `semanas_sem_mudanca` cresce
sozinho e o **S4 marca o universo inteiro daquela fonte como "parado"** — que é exatamente o sinal de
vulnerabilidade que o funil de M&A procura. Falso positivo em massa, no sinal de segundo maior peso,
e silencioso. O cron dos agregadores **não** passa por este script: ele tem wrapper próprio
(`run_snapshot_agregadores.sh`), porque precisa da curadoria antes do snapshot. O recorte de cada
partição fica registrado em `fontes_lidas`, na auditoria.

**Instalação, uma vez.** Nada no repo cria `/opt/motor-expansao-infra/` — o `cp` dos wrappers de cron
o pressupõe. `install -d` é idempotente, então rodá-lo mesmo já existindo não custa nada:

```bash
install -d -m 0755 /opt/motor-expansao-infra
cp /opt/motor-expansao/app/scripts/cron/run_snapshot_concorrentes.sh /opt/motor-expansao-infra/
chmod +x /opt/motor-expansao-infra/run_snapshot_concorrentes.sh
```

> O checkout em `/opt/motor-expansao/app` **não é atualizado por ninguém automaticamente** (o runner
> semanal não faz `git pull` de propósito, para não conflitar com o deploy). Se o script não estiver
> lá, ou sincronize o checkout, ou envie o arquivo por `scp` da estação direto para
> `/opt/motor-expansao-infra/` — neste caso confira que ele foi com **LF**, não CRLF.

**Antes de agendar, rode o modo seco** — o layout dos CSVs na VPS não é versionado e o script não
tem como adivinhá-lo:

```bash
DRY_RUN=1 /opt/motor-expansao-infra/run_snapshot_concorrentes.sh
```

> **`HOST_CONCORRENTES` tem duas armadilhas, e uma delas é silenciosa.** O default do script é
> `/opt/gymscraping` — o clone do repo de coleta, que é onde existe `Unidades/unidades_<rede>.csv`,
> o padrão que o glob procura. O palpite natural, `/opt/motor-expansao/concorrentes`, **existe** mas
> guarda os CSVs **achatados** (o sync copia os arquivos direto para a raiz, sem o subdiretório):
> ali o glob não casa com nada e o dry-run devolve `linhas_snapshot = 0` **sem erro nenhum**, o que
> se lê como "não há dado" em vez de "caminho errado". Um caminho inexistente, ao contrário, aborta
> na hora. Se precisar sobrescrever: `HOST_CONCORRENTES=/outro/caminho DRY_RUN=1 ...`.

`--dry-run` roda a cadeia inteira **sem gravar e sem podar** (a poda de retenção,
`RETENCAO_SEMANAS = 26` desde a emenda de 2026-08-26 ao BLK-MA-21 / DEC-039 — o `78` foi comprado
pela premissa mensal, que morreu; a aritmética está na seção do cron dos agregadores, abaixo). Se
`linhas_snapshot` vier `0`, o caminho de `HOST_CONCORRENTES`
está errado; só agende depois de ver contagem plausível.

**Falha do snapshot não pode abortar o lote** — a linha sugerida termina em
`|| echo "snapshot falhou"`, no mesmo espírito de "falhas individuais de coletor não abortam o lote".

> **Maturidade da série — DECIDIDO em 2026-08-11 por Vinicius: `MIN_SEMANAS` fica em 8.** Cumpre a
> obrigação que o D2 do contrato delegou a este bloco ("revisitar com a cadência real medida"), e a
> revisão foi feita: mantém-se o valor. **Não reabrir sem dado novo.**
>
> A medição que sustentou a decisão. Os parâmetros contam **observações, não meses**, e são dois,
> com papéis distintos: `MIN_SEMANAS = 8` libera o sinal de churn (`s3`, via `flag_serie_imatura`),
> enquanto `STALE_SEMANAS = 12` é o **denominador** do componente de estagnação
> (`v4 = semanas_sem_mudanca / 12`, `score.py`). Baixar só o primeiro **desequilibra os dois**: o
> score viraria ordenável com 6 observações enquanto o `v4` ainda estaria confinado a `≤ 0,5` —
> metade da escala do sinal mais importante do ranking, inacessível justamente na largada.
>
> E o prazo vem da **cadência**: com as três fontes semanais, 8 observações são **~2 meses** para
> todas. Quando esta nota foi escrita, os agregadores ainda não tinham cron e valiam ~8 meses; o
> BLK-MA-21 deu cron próprio a eles, na terça, e a maturação caiu para ~8 **semanas** — que era
> justamente o caminho com retorno real, em vez de afrouxar o critério.
>
> Fica registrado, para quando houver dado: o parâmetro é **global**, e agora a cadência também é.
> A assimetria que sobra não é de cadência, é de **buraco**: a semana em que a curadoria recusa um
> feed velho ocupa slot de calendário sem render observação àquela fonte. Se isso incomodar, a
> pergunta certa é tornar o parâmetro por fonte — escopo novo, fora do BLK-MA-06.

### Coleta semanal dos agregadores (BLK-MA-21 / DEC-039 — o relógio dos independentes)

**Por que existe.** Os **independentes** — o universo-alvo do funil de M&A — vivem **só** no WellHub
e no TotalPass. O snapshot semanal acima fotografa `--fontes unidades`, que é o feed de **cadeias**.
Sem este cron, S3 (churn) e S4 (staleness) sobre independentes **nunca amadurecem**, e o score de
vulnerabilidade fica preso no regime `{s1,s6}` — em que o `v1` é constante e o que se ordena é
pressão competitiva renomeada, para sempre.

**Script versionado:** `scripts/cron/run_snapshot_agregadores.sh`. Ele faz os **três** passos numa
execução só (decisão D2 da DEC-039): coleta (~21h45) → curadoria → snapshot, com um `flock -n`
cobrindo a janela inteira. READ-ONLY sobre o M1. **O script nunca atualiza o clone do coletor, nunca
copia arquivo entre máquinas, nunca abre sessão remota e nunca faz deploy** — tudo isso é passo
manual, comando a comando (§6 do `CLAUDE.md`).

> **O cron dos agregadores NÃO usa o wrapper de domingo.** O cabeçalho de
> `run_snapshot_concorrentes.sh` mandava, até 2026-08-25, invocar "este mesmo script com
> `--fontes totalpass wellhub`" na cadência dos agregadores.
> Seguir aquilo pularia a curadoria inteira — a escolha do diretório do WellHub e a guarda de
> frescor, que são a razão deste bloco existir. Os dois wrappers são distintos e não se substituem.

**Passo 0 do wrapper: a rotação do consolidado, e por que `--no-resume` não bastava**
*(emenda de 2026-08-25)*. Nos dois coletores, `--no-resume` faz **apenas** `checkpoint.unlink()`. O
CSV consolidado (`Wellhub/unidades_wellhub.csv`, `TotalPass/unidades_totalpass.csv`) é escrito em
modo `"a"`, e `ensure_header` **retorna cedo** quando o arquivo já existe com conteúdo: **nada
trunca o consolidado**. Na segunda semana as duas safras coexistem no mesmo arquivo e `split_by_state`
(modo `"w"`) propaga as duas para os 27 CSVs por UF.

O estrago não é volume, é **inversão de sinal**. `montar_snapshot` desempata por
`sort_values(["fonte","chave_snapshot","hash_campos_raspados"])` + `drop_duplicates(keep="first")`,
ou seja, sobrevive o **menor hash** — arbitrário em relação à safra, porque `data_coleta` está em
`CAMPOS_NUNCA_HASHEADOS` e a safra nova não se distingue pelo hash. Academia que **mudou** tem
~metade de chance de sobreviver com a linha **velha**: `semanas_sem_mudanca` cresce sozinho e o
**S4 lê "parado" exatamente em quem se mexeu**. E mudança de **nome** gera chave nova sem a velha
sumir do feed, então `sumiu_recente` (S1, o de maior peso) nunca dispara e nasce **pin fantasma**.

O wrapper **rotaciona, não apaga**: o consolidado vira `<nome>.<AAAAMMDD-HHMMSS>.bak` ao lado do
original (sufixo sem `.csv`, para nenhum glob voltar a casá-lo), a coleta nasce limpa e o histórico
fica no disco para auditoria. Só roda quando a coleta vai rodar — com `DRY_RUN=1` ou
`PULAR_COLETA=1` rotacionar destruiria justamente o feed que se quer reaproveitar.

> **Os arquivos `.bak` acumulam um por SEMANA e ninguém os apaga — e não são ~200 KB.** Medido em
> 2026-08-26 no clone irmão: `unidades_wellhub.csv` = **11.707.221 B** (11,16 MiB) e
> `unidades_totalpass.csv` = **3.319.377 B** (3,17 MiB), ou seja **14,33 MiB por rotação**. Com 52
> rotações por ano são **~745 MiB/ano, sem teto e sem dono** — mais do que a série de snapshots
> inteira. A limpeza é do operador, e agora ela é mensal, não anual.

**E o TotalPass agora também roda `--no-resume`.** Sem ele, `TotalPass/pipeline.py` filtra
`pending = [s for s in slugs if not checkpoint.already_processed(s)]` e retorna cedo com
`if not pending` — com o checkpoint cheio (34.982 slugs medidos nesta estação: 15.986 completed +
50 failed + 18.946 filtered), **praticamente nada era recoletado**. E o `main()` **não parava ali**:
`split_by_state` rodava em seguida e reescrevia os 27 CSVs por UF em modo `"w"`, com conteúdo
idêntico e **mtime de agora**. O coletor saía com **sucesso**, então o `|| echo "coletor falhou"` do
wrapper nunca disparava.

**A curadoria não é `cp`.** Ela é um módulo Python versionado e testado
(`motor_expansao.vulnerabilidade.curadoria_agregadores`, que viaja **dentro da imagem** da API, logo
"está no ar" é verificável por digest), e decide duas coisas que, decididas errado, produzem um
**número maior em vez de um erro**:

| decisão | regra | por quê |
|---|---|---|
| qual diretório | `TotalPass/csvs`; WellHub prefere `Wellhub/csvs_musculacao` e cai em `Wellhub/csvs` se ele não existir | os dois universos do WellHub diferem por 2-3× (16.432 × 6.850 linhas medidas em SP). `csvs/` já sai filtrado no modo **default** do coletor; `csvs_musculacao/` só é gerado quando o filtro do pipeline está desligado |
| ambiguidade | `csvs_musculacao/` presente mas **mais antigo** que `csvs/` ⇒ **aborta** | significa que a última coleta rodou noutro modo. Escolher em silêncio é o modo de falha que este bloco existe para matar |
| frescor | recusa publicar agregador cuja **`data_coleta`** mais VELHA ainda no diretório passe de `MAX_IDADE_DIAS` (default **3**) | se um coletor morrer no meio da janela de 20h, os CSVs antigos ficam no disco. Fotografá-los faz `semanas_sem_mudanca` crescer sozinho e o **S4 marcar o universo inteiro daquela fonte como "parado"** — falso positivo em massa, no sinal de segundo maior peso, com `exit 0` |
| piso de volume | recusa volume abaixo de `--piso-relativo` (default **0,5**) do que já está publicado no destino | o teto pega universo que **infla**; sem piso, coleta que morreu na metade passa — CSVs frescos, metade das linhas, e as que faltam viram `sumiu_recente` em massa no **S1**. Inerte na 1ª execução (sem baseline); `0` desliga |

> **A idade sai da linha mais VELHA do feed (`min(data_coleta)`), não do `mtime` nem do máximo**
> *(emenda de 2026-08-25, régua ajustada para o mínimo em 2026-08-26)*. A guarda nasceu medindo
> `p.stat().st_mtime` e isso a tornava cega ao caso que ela existe para pegar. Medido no clone real:
> os 27 CSVs de `TotalPass/csvs/` tinham `mtime` de **hoje** e `data_coleta = 2026-06-01` em
> **15.982 de 15.986** linhas — **85 dias** reportados como `0`. O `mtime` mede quando o arquivo foi
> *tocado*; `data_coleta`, quando o dado foi *colhido*. Motivo independente: `mtime` **não sobrevive**
> a `scp`, `git clone`, `cp -r` nem a restore de volume, então a régua antiga protegia só a estação em
> que o arquivo nasceu — não a VPS. O `mtime` fica como **fallback declarado** (feed sem `data_coleta`
> legível) e continua sendo a régua da **ambiguidade** acima, onde a pergunta é outra ("qual diretório
> o coletor escreveu por último") e ele é a resposta certa. Qual régua decidiu cada agregador sai no
> relatório, em `regua_idade`, e no log — com o rótulo `data_coleta_min`, cujo sufixo existe para a
> procedência não ficar ambígua entre versões da imagem (a anterior agregava por **máximo**).
>
> **Por que o mínimo, e não o máximo** *(2026-08-26)*. `Wellhub/split_by_state.py` só reescreve as
> UFs presentes no consolidado e **nada apaga**: uma coleta que morre no meio deixa as demais UFs com
> a safra anterior no disco. Simulado com as proporções reais das 27 UFs (só SP recoletada hoje, 26
> UFs de 7 dias atrás), o **máximo** reportava `idade_dias = 0,0` e publicava **45.526 linhas das
> quais só 36,1% eram frescas** — e o piso relativo de volume não dispara, porque o total continua em
> 100% do baseline. Pelo mínimo o mesmo diretório mede 7 dias e é recusado. A troca custa zero hoje:
> o spread real medido é **0** em 83.685 linhas dos três diretórios do clone. **Direção de falha:
> fail-closed** — uma única linha com data corrompida no passado passa a recusar o feed inteiro, o
> wrapper sai com `exit 3` e chama o operador. `data_coleta` no **futuro** é descartada (não é dado,
> é corrupção): com o máximo, 1 linha corrompida em 10.000 dava `idade_do_feed = -1,0` e absolvia o
> feed inteiro.

Fonte recusada **sai do `--fontes`** do snapshot, e a partição registra o que foi *pedido* na coluna
`fontes_lidas` do parquet — que é como se distingue "o TotalPass não foi tentado" de "foi tentado e
recusado". Se **nenhuma** fonte for publicada, o wrapper sai com código `3`: nada fresco para
fotografar é falha, não sucesso silencioso.

A curadoria decide os **dois** agregadores antes de copiar qualquer byte *(emenda de 2026-08-25)*:
no laço único anterior, o `totalpass` (primeiro na ordem canônica) já tinha sido publicado quando a
ambiguidade do `wellhub` levantava, e o destino ficava com meia curadoria de uma semana nova enquanto
o wrapper abortava.

> **Ação humana pendente, e ela se repete toda SEMANA se não for resolvida.** O wrapper roda o WellHub
> no modo **default** (filtro do pipeline ligado), em que só `csvs/` é regenerado —
> `Wellhub/csvs_musculacao/` fica para trás e vira "estritamente mais antigo", que é exatamente o
> gatilho da linha *ambiguidade* acima. Nesta estação o clone já está nesse estado
> (`csvs/` de `2026-08-18` contra `csvs_musculacao/` de `2026-08-07`). **Antes da primeira execução
> agendada:** confirmar de que modo o coletor rodou e **apagar `Wellhub/csvs_musculacao/` à mão**. Com
> o filtro ligado, `csvs/` já É o subset de musculação e o diretório antigo não tem função.

**Retenção: `RETENCAO_SEMANAS` voltou de `78` para `26`, e o número decide o epic.**
`podar_snapshots` é keep-newest-N sobre diretórios `semana=`. Com as **três** fontes semanais, N
partições = N observações de **cada** fonte no caminho feliz — o divisor `4,345` do feed mensal não
existe mais. O piso é **13**, medido: `_semanas_sem_mudanca` conta observações estritamente **após**
a última mudança, logo vale `k-1` com hash constante, contra o denominador `STALE_SEMANAS = 12`.

| N | `semanas_sem_mudanca` | `v4` | |
|---|---|---|---|
| 8 | 7 | 0,5833 | |
| 12 | 11 | 0,9167 | **teto permanente: nunca satura** |
| 13 | 12 | 1,0000 | **piso duro — nunca descer abaixo daqui** |
| **26** | 25 | **1,0000** | 2× o piso: satura mesmo com 50% de buraco de folha |

`26` é o menor N que ainda satura o `v4` com uma fonte perdendo **metade** das semanas (26 semanas,
50% de falha → 13 observações → `semanas_sem_mudanca = 12` → `v4 = 1,0000`, exatamente no piso).
Custo em disco medido em 2026-08-26 (42.535 linhas/semana somando as três fontes, 151,7
bytes/linha): **160,0 MB** — não é restrição num NVMe de 200 GB. O que restringe é a **leitura**:
`ler_snapshots` carrega a série inteira em memória e o pico de RSS medido cresce ~70,5 MB por semana
retida (N=13 → 999 MB; N=26 → 1,9 GB). Numa KVM4 de 16 GB com 6 containers permanentes, 1,9 GB é
folgado; o `78` extrapolava para ~5,6 GB, que não é obviamente seguro.

**Ordem de aplicação — ela é a defesa contra o modo destrutivo.** A partição passou a ter **duas**
chaves (`semana=AAAA-SS/fonte=<fonte>/`), porque duas cadências escrevem na mesma semana ISO e, com
uma chave só, `delete_matching` fazia a segunda apagar a primeira.

1. **Publicar e aplicar a imagem da API com o BLK-MA-21** (`docs/deploy_api_bot.md`, deploy por
   digest) **antes de qualquer cron**. Uma imagem antiga escreve com **uma** chave e **apaga** a
   folha da outra cadência.
2. Se o snapshot **semanal** já tiver rodado com a imagem antiga, **copiar
   `snapshots_concorrentes/` inteiro** e só então migrar o layout **na imagem nova**:
   `python -m motor_expansao.vulnerabilidade.snapshots --migrar-layout --dry-run` e depois sem o
   `--dry-run`. A escrita **recusa** semana com arquivo legado solto — sem isso, legado + folha nova
   da mesma fonte na mesma semana devolve a linha **duas vezes** na leitura, e o erro só aparece
   dias depois, longe da causa.

   > **A cópia não é zelo, é a única defesa contra a janela residual** *(emenda de 2026-08-25)*. A
   > migração agora escreve as folhas num diretório temporário **irmão** de `snapshots_concorrentes/`
   > e as move por rename atômico — antes ela gravava direto no caminho final, e um crash no meio do
   > `write_dataset` deixava uma folha **parcial** ao lado do legado, que é exatamente o par que faz a
   > leitura duplicar linha (e que então travava a retentativa na guarda de estado ambíguo). Sobra uma
   > janela de alguns renames, entre a primeira folha movida e o `unlink` do legado; eliminá-la
   > exigiria rename atômico de diretório sobre diretório, que nem POSIX nem Windows oferecem.
   >
   > O `--dry-run` agora **DIAGNOSTICA** em vez de levantar: imprime
   > `{"migrar_layout": [...], "ambiguas": [...], "dry_run": True}` com **todas** as semanas ambíguas
   > de uma vez. Antes ele levantava na primeira, e com duas ambíguas a segunda só aparecia depois de
   > a primeira ser resolvida à mão — uma por execução. Se `ambiguas` não vier vazia, **não migre**:
   > resolva à mão primeiro.
3. Concluir os três passos pendentes do **BLK-MA-06** (cópia do wrapper semanal, `DRY_RUN=1`, linha
   no `run_weekly_90.sh`). É ele quem prova o caminho dos CSVs e o `API_IMAGE`.
4. Atualizar o clone `/opt/gymscraping` (traz o `GymScraping` #11 — a caixa exata de `TotalPass/`;
   sem ele o passo 1 do wrapper aborta com mensagem própria).
5. Instalar o wrapper e rodar o modo seco.
6. Só então: a linha de crontab e a linha do healthcheck.

**Instalação, uma vez.** Se o checkout `/opt/motor-expansao/app` estiver desatualizado, envie o
arquivo por `scp` da estação direto para `/opt/motor-expansao-infra/` — neste caso confira que ele
foi com **LF**, não CRLF.

```bash
install -d -m 0755 /opt/motor-expansao-infra          # idempotente
cp /opt/motor-expansao/app/scripts/cron/run_snapshot_agregadores.sh /opt/motor-expansao-infra/
chmod +x /opt/motor-expansao-infra/run_snapshot_agregadores.sh
```

**Modo seco — passo OBRIGATÓRIO antes de agendar** (pula a coleta; usa os CSVs já no clone):

```bash
DRY_RUN=1 /opt/motor-expansao-infra/run_snapshot_agregadores.sh
```

Confira na saída, nesta ordem:

| campo | o que significa se vier errado |
|---|---|
| `fontes_publicadas=` | vazio ⇒ os dois feeds estão velhos ou o caminho do clone está errado |
| `regua_idade` | por agregador: `data_coleta_min` é a régua boa; `mtime` é **fallback** (o feed não trouxe data legível) e vale bem menos — foi por medir mtime que 85 dias saíram como `0`. O rótulo sem o sufixo `_min` também denuncia imagem antiga |
| `linhas_snapshot` | `0` ⇒ o caminho dos CSVs curados está errado (o glob não casou com nada). **Exceção:** na **primeira instalação**, com o destino ainda vazio, `0` é o esperado *por construção* — a curadoria em `DRY_RUN` não copia nada, então não há o que o snapshot leia. Repita o modo seco **depois** da 1ª execução real para a leitura valer |
| `versao_contrato` | tem de ser `snapshots_concorrentes_v4`. **`v3` = imagem ANTIGA na VPS** — ela escreve com uma chave e apaga a folha da outra cadência. **Não agende**: aplique a imagem nova primeiro |
| `retencao_semanas` | tem de ser `26` (piso duro medido: **13**; nunca abaixo). O `78` é o valor da premissa **mensal**, que morreu — se o `DRY_RUN` mostrar `78`, a VPS está com imagem antiga |

> Os dois últimos campos entraram na auditoria **exatamente** para isto: são a única forma de o
> `DRY_RUN` provar **qual imagem está rodando** antes de agendar. A lição é do BLK-MA-19 — "código
> publicado ≠ camada no ar".

**Linha de crontab (D1 — TODA terça, 02:00 UTC = segunda 23:00 BRT):**

```cron
0 2 * * 2 /opt/motor-expansao-infra/run_snapshot_agregadores.sh
```

**Sem guarda de dia do mês** — ela existia só para emular "1ª terça", e com ela cai também o `%`
escapado (`\%`) que o crontab exigia. A janela sequencial mede ~21h45: começando 02:00 UTC de terça,
fecha ~23h45 de terça. Folga de **39h depois** do runner de domingo (06:00 UTC) e de **~102h antes**
do próximo — as duas janelas nunca se encostam, nem na banda alta de 31h medida para o WellHub.
Terça também deixa a retentativa caber na **mesma semana ISO**: falha na terça → `FAIL` do
healthcheck na quinta 12:00 → retentativa manual fecha sexta, e a observação da semana é salva.

> **Terça e domingo caem na MESMA semana ISO** (medido: `2026-08-25` e `2026-08-30` são ambos
> `2026-35`), então as três fontes colidem numa partição **por construção** — é para isso que a
> chave dupla `semana=/fonte=` existe. E `materializar` deriva a semana de `date.today()` no passo
> 3, nunca de `data_coleta`, então nem a banda alta de 31h atravessa a fronteira ISO.

**Alerta de idade** (a partir daqui a ausência do cron deixa de ser silenciosa):

```cron
0 12 * * 4 /opt/motor-monitoring/healthcheck_vps.sh agregadores   # quinta 09h BRT
```

O check olha a partição **por fonte** (`fonte=wellhub`, `fonte=totalpass`) e não a série inteira: o
cron de domingo escreve toda semana, então a série nunca *parece* velha e um cron de agregador morto
passaria despercebido para sempre. Limiar `MONITOR_AGREGADOR_MAX_DIAS` (default **9**). Partição que
**nunca existiu** também dispara `FAIL` — que é o estado real enquanto o cron não for agendado.

> **Por que quinta, e por que 9** *(2026-08-26)*. A régua deriva a idade da **segunda-feira da semana
> ISO** da partição, não do instante da coleta. Na quinta 12:00 UTC: com a rodada da própria terça a
> idade mede **3** dias; com uma rodada perdida, **10**. A faixa que separa os dois casos é `[3, 9]`
> inteira, e `9` é o **teto** dela — o mais tolerante a uma rodada que legitimamente escorregue
> dentro da semana. (Não é o *único* valor que separa; a justificativa de unicidade era falsa.) O
> `45` herdado da premissa mensal deixava passar **até 6 rodadas perdidas** antes do primeiro `FAIL`.
> Quinta alerta 2 dias depois da falha e deixa sexta livre para a retentativa dentro da semana ISO.

> **A idade sai da chave `semana=AAAA-SS`, não do mtime do diretório `fonte=`** *(emenda de
> 2026-08-25)*. O check media `stat -c %Y` da folha, e o **passo 2 obrigatório desta mesma ordem de
> aplicação** — `--migrar-layout` — **cria** a folha com mtime de agora. Medido sobre cópia da
> partição viva: dado de `2026-08-05` (20 dias) reportado como `0d`; com o limiar herdado de 45, o `FAIL`
> atrasaria ~20 dias, e a distância é arbitrária para qualquer `rsync`/restore do volume. A conversão
> ISO-week é feita à mão (`date -d` não parseia data ISO-week em nenhum coreutils): 4 de janeiro cai
> sempre na semana 1. A régua nova pode **adiantar** o alerta em até ~1 dia, nunca atrasá-lo — direção
> segura para um monitor. Chave ilegível cai no mtime e **diz** que caiu, no texto do alerta.

**Fronteira com o BLK-MA-20 (DEC-039, D9) — e ela é FAIL-CLOSED** *(emenda de 2026-08-25)*. A
partição do **TotalPass é gravada desde a primeira semana** (o cronômetro de `MIN_SEMANAS = 8` são 8
semanas na cadência real — cada semana de espera é irrecuperável), mas o **consumo** dela pelo score
espera o BLK-MA-20 decidir o grão do S1 e calibrar a dedup TP × WH, que hoje está *arbitrada*.

O recorte é imposto por código **na ausência de gesto**: `alvos_ma` sem `--fontes` aplica
`FONTES_ENTREGAVEL_DEFAULT = ("wellhub",)` e registra o recorte no log. A primeira implementação
tinha `default=None` e, com isso, a mesma propriedade que a DEC-039 rejeitou com a frase *"é prosa: a
cadeia roda com as duas fontes sem editar uma linha"* — só que o gesto que vazava passou a ser **não
digitar o flag**, e duas das três receitas canônicas do próprio repositório o omitiam. Para consumir
a série inteira quando o MA-20 fechar, o gesto é explícito: `--todas-as-fontes` (incompatível com
`--fontes`, e o log sai em `WARNING`).

### Entregável de M&A no piloto (BLK-MA-19 — os pins de academia no Mapa Territorial)

**Por que esta seção existe.** O snapshot acima produz a **série**; esta seção trata do **produto**
dela, que é outra coisa e tem outro ciclo de vida. Entre 2026-08-19 e 2026-08-24 o código dos pins
esteve publicado e funcionando em produção sem que **nenhum dos dois parquets** tivesse sido
enviado — a camada não existia para ninguém, e nada acusou. Não havia bloco de backlog, não havia
linha de runbook, e `scripts/check_artifacts.py` imprimia "OK".

**Os dois artefatos.** Ambos vivem em `data/staging/` (gitignored, carregam identidade — autorizado
pela emenda de 2026-08-14 à DEC-028) e são **opt-in**: sem a flag, nada nomeado é gravado.

| arquivo | o que desenha | contrato |
|---|---|---|
| `vulnerabilidade_ma_nomeadas.parquet` | pins das academias INDEPENDENTES, com score (BLK-MA-15) | `alvos_ma_nomeados_v5` |
| `vulnerabilidade_ma_redes.parquet` | pins das unidades de REDE do agregador, com pressão e **sem** score (DEC-035) | `redes_ma_nomeadas_v2` |

`vulnerabilidade_ma_academias.parquet` (variante sem identidade) **não vai a produção**: nenhuma
superfície de lá o lê.

**Gerar — na estação, nunca na VPS:**

```bash
python -m motor_expansao.vulnerabilidade.alvos_ma \
  --base-dir data/staging/snapshots_concorrentes \
  --saida-nomeadas data/staging/vulnerabilidade_ma_nomeadas.parquet \
  --saida-redes    data/staging/vulnerabilidade_ma_redes.parquet
```

> **Não falta `--fontes wellhub` aqui — o recorte é FAIL-CLOSED** *(DEC-039, D9; emenda de
> 2026-08-25)*. Omitir o flag aplica `FONTES_ENTREGAVEL_DEFAULT = ("wellhub",)`, e o log da execução
> diz qual recorte valeu. Até 2026-08-25 este mesmo bloco copiável rodava **sem recorte nenhum**,
> vinte e quatro linhas depois de a seção do cron dos agregadores prometer, em prosa, que "o entregável roda
> `--fontes wellhub`" — o gesto que vazava tinha deixado de ser "editar uma linha" e passado a ser
> "não digitar o flag". Para consumir a série inteira quando o BLK-MA-20 fechar, o gesto é
> explícito: `--todas-as-fontes`.

> **Por que NÃO gerar na VPS**, ainda que a imagem da `api` tenha o módulo:
> 1. `data/staging` e `data/outputs` são montados **`:ro`** nos containers de longa duração — o
>    `to_csv` do entregável aborta antes de chegar nos dois nomeados.
> 2. Num one-shot `docker run --rm`, os **defaults do módulo mentem**: o pacote é instalado
>    não-editável, então o `ROOT = parents[3]` resolve para dentro de `site-packages`, o
>    `mkdir(parents=True)` **cria o diretório e grava lá com exit code 0**, e o `--rm` apaga tudo.
>    Sai "sucesso" e não há arquivo.
> 3. Sem `snapshots_concorrentes/semana=*` no host, a cadeia devolve frames **vazios** de ponta a
>    ponta e grava artefatos vazios — aí o `/api/health` **para de acusar** e a camada fica
>    invisível **com sinal verde**, que é pior que o estado de hoje.
>
> Caminho canônico: gerar na estação, conferir, e **transportar por `scp`**.

**Antes do `scp`, confirmar que a imagem NO AR tem o código dos pins.** "Publicado no GHCR" não é
"rodando na VPS" — o deploy é manual por digest (§6 do `CLAUDE.md`), então a imagem em execução pode
ser anterior ao código que lê estes artefatos. Se for, o trabalho não é `scp` + `restart`: é deploy
de imagem (`docs/deploy_piloto_web.md`), e enviar o dado sozinho não acende nada.

```bash
docker inspect motor_expansao_web \
  --format '{{index .Config.Labels "org.opencontainers.image.revision"}}'
```
O commit precisa ser igual ou posterior ao merge de **#243 (2026-08-19)**, que é onde
`NOMEADAS_PATH`/`REDES_PATH` entraram. Se o label vier vazio, caia para
`docker inspect motor_expansao_web --format '{{.Image}}'` e compare com o `WEB_IMAGE` do `.env`.

**Transportar — `.tmp` + `md5sum` + rename atômico**, para não haver janela de arquivo truncado
sendo lido por um container de pé (mesmo molde da camada de crescimento):

```bash
scp -i ~/.ssh/id_ultra_mcp data/staging/vulnerabilidade_ma_nomeadas.parquet \
  root@2.25.137.241:/opt/motor-expansao/data/staging/vulnerabilidade_ma_nomeadas.parquet.tmp
```
```bash
scp -i ~/.ssh/id_ultra_mcp data/staging/vulnerabilidade_ma_redes.parquet \
  root@2.25.137.241:/opt/motor-expansao/data/staging/vulnerabilidade_ma_redes.parquet.tmp
```
Conferir na VPS (`md5sum` dos `.tmp` contra os da estação), depois `chmod 0644` e `mv -f` de cada um
sobre o nome final. **Não rodar `chown`** no staging: o diretório é compartilhado com a `api`.

**RESTARTAR o `web` — obrigatório, não higiene.** `carregar_independentes` e `carregar_redes` são
`@functools.lru_cache(maxsize=1)` e **memoizam a ausência**. Com o container de pé, o `/api/health`
fica **verde na hora** (ele faz `exists()` a cada chamada) e os pins seguem invisíveis:

```bash
docker restart motor_expansao_web
```

Use `docker restart`, **não** `up -d --force-recreate` — este recria a partir do `${WEB_IMAGE}` do
`.env` e trocaria a versão do piloto junto com o dado, dando duas causas na mesma janela.

**Provar que funcionou.** O `/api/health` é necessário e **insuficiente** (prova disco, não leitura).
A prova é a rota que serve a camada, num drill-down **municipal** — a visão de UF nunca traz M&A:

```bash
docker exec motor_expansao_web curl -fsS -H 'Remote-User: <usuario com a aba mapa>' \
  'http://127.0.0.1:8899/api/municipio/SP/S%C3%A3o%20Paulo'
```
Esperado: `independentes.disponivel = true` com `total > 0`, e **pelo menos um item de
`pins.concorrentes` com `"diag": true`** (as unidades de rede entram na mesma lista das bandeiras, e
o `diag` é o que acende o halo). Na tela, a pílula **"Ver academias independentes"** aparece no
drill-down.

> **`pins.redes_disponivel` não serve de aceite enquanto a imagem no ar for anterior ao BLK-MA-19.**
> O campo nasceu nesse bloco (`web/server/app.py`), então **ausente não é falha** — é uma imagem
> mais velha, e o deploy pode estar perfeito. Ele só passa a valer como sinal depois do merge **e**
> do próximo deploy de imagem, que é passo separado e manual (por digest, §6 do `CLAUDE.md`). Até
> lá, o aceite é a contagem de `diag`.

Dois erros de leitura a evitar no `403` e no `200`:

- **`403`** significa que o `Remote-User` escolhido não tem a aba `mapa` — **não** prova ausência de
  artefato. Use um usuário que exista no `acesso_abas.json` de produção.
- **`200` com um nome inventado não prova o gate.** Se o controle de abas estiver indisponível, o
  fail-closed devolve `ABAS_VALIDAS - ABAS_SENSIVEIS` (`acesso.py`), e `mapa` **não** é sensível —
  ou seja, qualquer nome passa. O `200` prova a camada, não a allowlist.

> **Contagem de pins não fecha com o total do artefato, e isso é correto.** Das 2.844 unidades de
> rede, só as **851** com `tem_pin_proprio = True` são desenhadas: as demais colapsaram contra um
> ponto de `concorrentes_mapeados` na dedup da DEC-034/FU4 e **já têm bandeira naquele endereço** —
> desenhá-las de novo daria duas bandeiras no mesmo lugar. Esperar 2.844 bandeiras é expectativa
> errada, não defeito.

**Rollback, em dois comandos:** `rm -f` dos dois parquets e `docker restart motor_expansao_web`. Os
dois leitores são opcionais e devolvem `None` — o piloto volta byte a byte ao comportamento anterior.

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

## Gerenciar usuários do login (Authelia)

> O login continua igual após a DEC-022: o Authelia protege `piloto.ultra-expansao.tech`
> e `/tiles/` em `dashboard.ultra-expansao.tech` com a mesma base de usuários.

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
docker compose -f docker-compose.prod.yml logs -f web
docker compose -f docker-compose.prod.yml logs -f api
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
docker compose -f docker-compose.prod.yml restart web
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

### Trilha de acesso do piloto (DEC-027)

Quem fez o quê no piloto: JSONL diário com usuário (Authelia), IP real, rota, status e
latência em `/opt/motor-expansao/logs/acesso/` (retenção 90 dias, podada pelo backend) +
access log do Caddy em `/opt/motor-expansao/logs/caddy/` + Authelia em `level: info`
(logins com sucesso e falha). Contrato, comandos de consulta e os passos manuais de
habilitação na VPS: **`docs/trilha_acesso_piloto.md`**.

### Alertas automáticos (BLK-SEC-05)

Monitoramento leve por cron + bot Telegram (reusa o bot de produção; alertas vão para o
grupo de ops — `MONITOR_TELEGRAM_CHAT_ID` no `.env`). Script versionado no repo em
`scripts/healthcheck_vps.sh`, instalado em `/opt/motor-monitoring/healthcheck_vps.sh`.

O que é vigiado e a cadência (crontab do root):

```cron
*/5 * * * * /opt/motor-monitoring/healthcheck_vps.sh containers  # 6 containers (web, api, bot, caddy, authelia, tileserver) + edge HTTPS
0 * * * *   /opt/motor-monitoring/healthcheck_vps.sh host        # disco >80% / memória <10%
0 11 * * *  /opt/motor-monitoring/healthcheck_vps.sh authelia    # resumo diário de falhas de login (08h BRT)
0 18 * * 0  /opt/motor-monitoring/healthcheck_vps.sh coleta      # domingo 15h BRT: resumo/falha da coleta semanal
0 12 * * 4  /opt/motor-monitoring/healthcheck_vps.sh agregadores # quinta 09h BRT: idade da partição de cada agregador (BLK-MA-21)
```

Comportamento anti-spam: alerta na transição OK→FAIL, lembrete a cada 1h enquanto durar,
e aviso de recuperação no FAIL→OK (estado em `/var/lib/motor-monitoring/`). Logs em
`/var/log/motor-monitoring/healthcheck.log`. Teste manual: `healthcheck_vps.sh test`.

Segredos: o script lê `API_TELEGRAM_TOKEN` e `MONITOR_TELEGRAM_CHAT_ID` do `.env` em
runtime; token nunca aparece em log/alerta. A rotação de logs do Docker já é feita pelo
daemon (`/etc/docker/daemon.json`, json-file 10m×3) — não é papel deste script.

---

## Runbook de incidente

Proporcional a um app interno — 3 cenários. Em todos: **quem aciona é quem viu o
alerta primeiro** (grupo de ops); Felipe é o dono da decisão de contenção.

**1. Indisponibilidade (piloto/API/bot fora do ar).**
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
│   ├── Dockerfile.web            # build fica no CI; produção puxa imagem do GHCR
│   ├── Dockerfile.api
│   ├── Caddyfile                 # NÃO está no git
│   ├── .env                      # NÃO está no git (WEB_IMAGE/API_IMAGE pinados por digest)
│   ├── authelia/
│   │   ├── configuration.yml     # NÃO está no git
│   │   ├── users_database.yml    # NÃO está no git
│   │   └── db.sqlite3            # banco de sessões Authelia
│   ├── web/                      # SPA + backend FastAPI do piloto
│   └── src/
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
- **Memória:** limite de 8 GB no container `web` (`memswap_limit` 10 GB; teto herdado da função do Streamlit — DEC-022); monitorar com `docker stats` se houver lentidão
- **Atualizações de sistema:** rodar mensalmente `apt-get update && apt-get upgrade -y` no servidor
