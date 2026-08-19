# Deploy do Piloto Web (produção)

Runbook do serviço **`web`** do `docker-compose.prod.yml` — o piloto (frontend Vite +
backend FastAPI num único container, servindo o SPA e a API na porta interna `8899`),
publicado em `piloto.ultra-expansao.tech`, atrás do Caddy + Authelia. Desde a **DEC-022
(2026-08-03)** o piloto é **O app de produção** — o dashboard Streamlit foi aposentado, não
há mais app paralelo.

> **Guardrails.** Execução no VPS é **sempre passo humano, comando a comando** (CLAUDE.md §6).
> Deploy é **por digest imutável**, nunca `:latest` cego. O piloto é **READ-ONLY sobre o M1**
> (só lê os parquets montados `:ro`). **Rótulo "preliminar":** os números da aba Viabilidade
> ainda estão em calibração vs a planilha oficial (folha via Fopag, balcão/agregadores
> separados e alavancagem pendentes — 2º passo) e a UI já avisa isso.

Arquitetura: **um container** serve tudo. O `web/server/app.py` monta o `dist/` (build do
Vite) na raiz via `StaticFiles` e expõe a API em `/api/*` na mesma porta `8899`. O Caddy só
faz `reverse_proxy web:8899`. Nada de porta no host. O subdomínio `dashboard.ultra-expansao.tech`
ficou vivo **só** para `/tiles/*` (tileserver do basemap dos PDFs; `publicUrl` e styles
inalterados), com **301 da raiz para o piloto** — DEC-022.

---

## 0. Pré-requisitos (uma vez)

- **DNS**: criar registro **A** `piloto.ultra-expansao.tech` → `2.25.137.241` (Hostinger).
- **Dados no VPS** (montados `:ro`; ver §2). Os parquets são gitignored.
- **`.env`** na VPS (`/opt/motor-expansao/app/.env`) com `WEB_IMAGE` pinado (§4).

---

## 1. Publicar a imagem (CI → GHCR, por digest)

O job **`publish-web`** (`.github/workflows/ci.yml`) builda `Dockerfile.web` (estágio Node
para o Vite + estágio Python para o backend) e publica `ghcr.io/kastaldy/motor-de-expansao/
motor-expansao-web` no GHCR, com **Trivy bloqueante** (HIGH/CRITICAL).

- **Automático**: o job roda em **todo push na `main`** (DEC-022 — a imagem `motor-expansao-web`
  é a imagem principal de UI) e publica quando o path-filter acusa mudança em `web/**`,
  `Dockerfile.web`, `src/motor_expansao/(dashboard|dimensionamento|api)/**` ou `pyproject.toml`.
- **Manual / bootstrap** (ex.: mudança que o filtro não pega):
  ```bash
  gh workflow run ci.yml --ref main -f publish_web=true
  ```
- Pegar o **digest** no fim do job (step "WEB digest imutavel publicado: sha256:...") ou:
  ```bash
  docker buildx imagetools inspect ghcr.io/kastaldy/motor-de-expansao/motor-expansao-web:sha-<commit>
  ```

> Se o Trivy travar numa CVE sem fix viável, adicionar ao `.trivyignore` (raiz) com
> justificativa — o piloto é exposto publicamente, então o gate é intencional.

---

## 2. Dados no VPS (montados `:ro`)

O serviço `web` monta os mesmos diretórios da `api`:
`/opt/motor-expansao/data/{outputs,staging,ibge,ultra}` e `/opt/motor-expansao/concorrentes`.
O backend deriva tudo de `MOTOR_DATA_DIR=/app/data`.

Confira o que o piloto precisa (senão a feature degrada em silêncio):
- `data/outputs/hexagonos_dashboard_enriquecido/` — **obrigatório** (Mapa Territorial, carga por UF).
- `data/outputs/setores_censitarios_2022_geo/` — Relatório Pontual (malha real IBGE).
- `data/staging/base_calibracao_maduras.parquet` — semente p50/faixa da Viabilidade.
- `data/staging/{uplift_renda_domiciliar_municipio,uplift_composicao_setor}.parquet` +
  `fator_temporal_renda.json` — **renda domiciliar municipal**; sem eles, o tooltip cai no
  fallback NACIONAL (~4,55×). Enviar por scp (ver [[project_deploy_pin_digest_prod]] / memória).
- `data/staging/{crescimento_municipal,crescimento_hex}.parquet` — passo 4 do funil
  ("Como a cidade está indo"). **OPCIONAIS**: sem eles o passo sobe, avisa que não há
  leitura e o resto do piloto segue igual — mas a feature fica morta. Gerados por
  `data/reports/crescimento/` (ordem obrigatória no README de lá).
- `data/staging/{growth_api_historico,concorrentes_mapeados,unidades_ultra_performance_hex}.parquet`
  — Visão Executiva + pins.
- `concorrentes/logo_<rede>.png` — **logos das bandeiras** (pendente; sem eles, fallback sigla+cor).

Enviar arquivos que faltarem (scp permitido; ssh remoto não — §6 do CLAUDE.md):
```bash
scp -i ~/.ssh/id_ultra_mcp <arquivo> root@2.25.137.241:/opt/motor-expansao/data/staging/
# validar na VPS: md5sum
```

---

## 2.1 Cadastro operacional (volume `:rw`) — DEC-023

A Visão Executiva 2.0 lê as dimensões que a API Growth não tem (consultor, master
franquia, franqueado, cidade, Gold, LTV, modalidades) de um **cadastro próprio**, e a
partir dela o time pode **atribuir consultor** pela própria aba. É a primeira escrita do
piloto.

Ela mora **fora** do `MOTOR_DATA_DIR` de propósito: assim nenhum artefato do M1 fica sob
um mount de escrita e o guardrail READ-ONLY do backend continua valendo sem exceção.

> **DEC-027 (2026-08-17):** o cadastro deixou de ser o único `:rw` — o `web` ganhou um
> **segundo** mount de escrita, `/opt/motor-expansao/logs/acesso:/app/logs/acesso:rw`
> (trilha de acesso), também fora do `MOTOR_DATA_DIR`. A lista exata dos DOIS é travada
> por `test_compose_monta_somente_cadastro_e_trilha_como_volumes_de_escrita`. Preparo do
> host e contrato: `docs/trilha_acesso_piloto.md` (em resumo:
> `install -d -m 0700 -o 1000 -g 1000 /opt/motor-expansao/logs/acesso` — sem isso a
> trilha degrada em silêncio, o app sobe igual).

```bash
# 1) criar o diretório no host (uma vez) E DAR O DONO CERTO.
#    O container roda como `appuser`, UID 1000 (fixo no Dockerfile.web). Criado como
#    root, o diretório fica legível — a aba sobe, os filtros de consultor aparecem, o
#    checklist passa 100% — mas o primeiro PUT devolve 500. O `chown` é o passo que
#    separa "parece que funcionou" de "funcionou".
mkdir -p /opt/motor-expansao/cadastro
chown -R 1000:1000 /opt/motor-expansao/cadastro

# 2) enviar a semeadura (gerada localmente da planilha do time de campo)
scp -i ~/.ssh/id_ultra_mcp cadastro_unidades.json     root@2.25.137.241:/opt/motor-expansao/cadastro/
```

Gerar a semeadura localmente:
```bash
python scripts/semear_cadastro_unidades.py     --planilha "ANALISE DIARIA DASHBOARD.xlsx"     --growth data/staging/growth_api_historico.parquet     --saida data/cadastro
```

O compose já monta `/opt/motor-expansao/cadastro:/app/cadastro:rw` (e, desde a DEC-027,
`/opt/motor-expansao/logs/acesso:/app/logs/acesso:rw` com
`MOTOR_ACESSO_LOG_DIR=/app/logs/acesso`) e passa `MOTOR_CADASTRO_DIR=/app/cadastro`.
**Sem o diretório o piloto sobe igual** — a aba degrada: os filtros de consultor ficam
vazios e o `PUT` devolve 503 com mensagem clara.

Dois arquivos vivem ali: `cadastro_unidades.json` (estado, gravado de forma atômica por
`os.replace`) e `cadastro_log.jsonl` (auditoria append-only: quem, quando, campo, de →
para). O autor sai do header `Remote-User`, que o Caddy já repassa ao piloto.

> **Não versionar o JSON.** Depois da semeadura, a fonte de verdade é o arquivo do
> servidor — rodar o seeder de novo NÃO sobrescreve o que foi editado na tela (campos já
> preenchidos vencem os da planilha, a menos que se passe `--forcar-planilha`).

---

## 2.2 Controle temporário de acesso por aba (2026-08-13)

O Authelia autentica; **quem autoriza por aba é o backend do piloto**
(`web/server/acesso.py`), pelo header `Remote-User` e por um mapa
`usuário -> [abas]` num JSON **no mesmo volume `:rw` do cadastro**:

```
/opt/motor-expansao/cadastro/acesso_abas.json
```

Formato (abas válidas: `mapa`, `oportunidades`, `executiva`, `viabilidade`;
`"*"` é o default para usuário fora da lista; chave começando com `_` é comentário):

```json
{
  "_comentario": "editar e salvar — vale na requisição seguinte, sem restart",
  "felipe_castaldi": ["mapa", "oportunidades", "executiva", "viabilidade"],
  "fulano_da_silva": ["executiva"],
  "*": []
}
```

Regras de operação:

- **Editar o arquivo basta** — o backend relê por mtime; não precisa de restart.
- **Validar o JSON antes de salvar** (`python -m json.tool acesso_abas.json`): arquivo
  ilegível ou JSON inválido **desliga o controle** (fail-open, com warning no log) —
  um typo devolve acesso cheio a todos, nunca um piloto morto.
- **Sem o arquivo** (dev local, mount ausente) o controle fica desligado — todos veem
  tudo, comportamento igual ao de antes da feature.
- A SPA esconde as abas via `GET /api/me`; o bloqueio real é o middleware (403 nas
  rotas da aba vetada). Rota nova sem regra reprova em
  `tests/unit/test_piloto_web_acesso.py` (cobertura obrigatória).
- Solução **temporária** até o banco de identidade (plano de 2026-08-07).

---

## 3. Caddy — bloco do subdomínio (editar na VPS)

O `Caddyfile` **não está no git** (gitignored, backup cifrado em `secrets/Caddyfile.enc`);
vive em `/opt/motor-expansao/app/Caddyfile`. O bloco do piloto (o bloco de `dashboard.` hoje só
serve `/tiles/*` e redireciona a raiz 301 para cá — DEC-022):

```caddyfile
piloto.ultra-expansao.tech {
    forward_auth authelia:9091 {
        uri /api/verify?rd=https://auth.ultra-expansao.tech
        copy_headers Remote-User Remote-Groups Remote-Name Remote-Email
    }
    reverse_proxy web:8899
}
```

Recarregar sem downtime:
```bash
cd /opt/motor-expansao/app
docker compose -f docker-compose.prod.yml exec caddy caddy reload --config /etc/caddy/Caddyfile
```
(Atualizar também o backup: `sops secrets/Caddyfile.enc` no repo local, se for versionar o cifrado.)

---

## 4. Authelia — proteger o subdomínio (editar na VPS)

Config **não versionada** (backup cifrado `secrets/authelia.configuration.enc.yaml`); vive em
`/opt/motor-expansao/app/authelia/configuration.yml`. Adicionar a regra:

```yaml
access_control:
  rules:
    # ... regras existentes ...
    - domain: piloto.ultra-expansao.tech
      policy: one_factor          # ou two_factor, se o ultra_team já usa 2FA
      subject:
        - "group:ultra_team"
```
Garanta que o subdomínio está coberto pela config de sessão/cookie (mesmo `session.domain`
base `ultra-expansao.tech` já cobre os subdomínios). Reiniciar:
```bash
docker compose -f docker-compose.prod.yml restart authelia
```
Usuários novos: `authelia/users_database.yml` (argon2id, grupo `ultra_team`) — ver
`docs/infra_producao.md`.

---

## 5. Subir o serviço (por digest)

No `.env` da VPS (`/opt/motor-expansao/app/.env`), pinar:
```
WEB_IMAGE=ghcr.io/kastaldy/motor-de-expansao/motor-expansao-web@sha256:<digest-do-passo-1>
```
Depois:
```bash
cd /opt/motor-expansao/app
docker compose -f docker-compose.prod.yml pull web
docker compose -f docker-compose.prod.yml up -d web
# Caddy pega a nova rota (se editou o Caddyfile, recarregue — §3)
docker compose -f docker-compose.prod.yml up -d caddy

# conferir saúde
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml exec web curl -fsS http://127.0.0.1:8899/api/health
```
Abrir `https://piloto.ultra-expansao.tech` → login Authelia → piloto.

**Rollback**: apontar `WEB_IMAGE` para o digest anterior e repetir `pull` + `up -d web`.

---

## 6. Checklist de verificação pós-deploy

- [ ] `GET /api/health` responde `{"status":"ok"}` no container.
- [ ] **`artefatos_faltando` do `/api/health` vem vazio.** É o item que faltava aqui: os
      parquets de crescimento (`crescimento_municipal`, `crescimento_hex`) não vêm no
      git nem na imagem — chegam só pelo bind mount `/opt/motor-expansao/data/staging`.
      Sem eles o piloto sobe normal e o **passo 4 sai vazio e sem cor, em silêncio**,
      então nenhum outro item deste checklist acusa a falta. Se aparecer algum nome ali,
      copiar o arquivo para o staging do VPS (juntos têm ~2,4 MB) e repetir o `up -d`.
- [ ] `https://piloto.ultra-expansao.tech` exige login (Authelia) e abre o SPA depois.
- [ ] Mapa Territorial carrega uma UF (a 1ª leitura carrega a partição inteira, demora).
- [ ] Viabilidade calcula um ponto e mostra o **banner "preliminar"**.
- [ ] Relatório Pontual (PDF) gera sem erro (basemap/contextily presentes).
- [ ] Tooltip de renda domiciliar mostra valor **municipal** (não o fallback nacional) —
      se cair no nacional, faltam os 3 parquets de renda domiciliar (§2).
- [ ] **Visão Executiva** abre com a rede do Brasil inteiro (sem pedir UF) e a carteira
      lista as unidades com semáforo. `GET /api/rede/carteira` deve responder em < 1 s.
- [ ] Filtro de **consultor** tem nomes (se estiver vazio, falta o `cadastro_unidades.json` — §2.1).
- [ ] A **receita por recorrente** está na casa de R$ 130–180, não de R$ 20 (o número da v1
      era 76% subestimado; ver DEC-023).
- [ ] Abrir uma unidade (ficha) e voltar com o **Voltar do browser**.
- [ ] Baixar o **CSV da carteira** e conferir que abre no Excel em colunas.
- [ ] **Atribuir um consultor** numa unidade e recarregar: se voltar 503/500, o dono de
      `/opt/motor-expansao/cadastro` não é o UID 1000 (§2.1).
- [ ] Baixar a **ficha em PDF** de uma unidade (a rota `.pdf` tem de vir antes da JSON).

---

## 7. Gotchas

- **Imagem stale**: mudança só em `src/motor_expansao/dashboard|dimensionamento/**` (que o
  backend importa) **dispara** o `publish-web` (o path-filter cobre). Mas se editar algo fora
  do filtro que afete o runtime, republique manual (§1).
- **CORS**: em produção o SPA e a API são a **mesma origem** (mesmo container atrás do Caddy),
  então CORS é irrelevante; as origens `localhost:5000` no `app.py` são só para o dev.
- **Base path**: o Vite builda com `base: "/"` (raiz). Como o piloto tem subdomínio próprio
  (não subpath), está correto. Se um dia for servido em `/piloto`, setar `base` no `vite.config.ts`.
- **Node só no build**: a imagem final é `python:3.11-slim` (sem Node) — o Vite roda só no
  estágio 1 do `Dockerfile.web`.
