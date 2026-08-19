# Trilha de Acesso do Piloto Web (DEC-027)

> Contrato canônico da trilha "quem fez o quê" do Motor de Expansão.
> Decisão: DEC-027. Escopo: **piloto web** (SPA + FastAPI). O bot Telegram e a API
> GeoEspacial ficam **fora** deste ciclo por decisão explícita de Felipe (2026-08-17).

## O problema que ela resolve

Diagnóstico de 2026-08-17: o Caddy injeta `Remote-User`/`Remote-Email` em **toda**
requisição do piloto (atrás do Authelia), mas nada gravava essa identidade — o access
log default do uvicorn registrava só o IP interno do Caddy, sem usuário; o Authelia em
`level: warn` não registrava login bem-sucedido; e a retenção era um acidente da rotação
do Docker (json-file 10m×3). Era impossível responder "quem abriu qual relatório, quando
e de onde".

## As três camadas da trilha

| Camada | O que registra | Onde persiste | Retenção |
|---|---|---|---|
| **1. App (backend do piloto)** | usuário real, IP de origem, método, rota+query, status, latência, user-agent, bytes | `/opt/motor-expansao/logs/acesso/acesso-AAAA-MM-DD.jsonl` (volume `:rw` próprio) | 90 dias, podada pelo próprio backend (`MOTOR_ACESSO_RETENCAO_DIAS`) |
| **2. Caddy (edge)** | access log HTTP completo do host `piloto.` em JSON (IP real, TLS, user-agent, latência) | `/opt/motor-expansao/logs/caddy/piloto-access.log` | rotação do próprio Caddy: 20 MiB × 10 arquivos, máx. 2160h (90 dias) |
| **3. Authelia (login)** | tentativas de login com usuário + IP — **sucesso e falha** (`level: info`) | stdout do container (rotação do daemon Docker) | ~semanas (10 MB × 3) |

A camada 1 é a fonte primária de auditoria de uso; a 2 é o registro bruto de edge
(cobre também o que o app filtra); a 3 responde "quem entrou e quando".

## Camada 1 — contrato do gravador

- **Módulo:** `src/motor_expansao/dashboard/acesso_log.py` (gravador, filtro, poda).
  **Middleware:** `_trilha_acesso` em `web/server/app.py` (logo após o CORS).
- **Uma linha JSON por requisição relevante**, chaves (identificadores, sem acento):
  `quando` (UTC, ISO, segundos), `usuario` (`Remote-User` → fallback `Remote-Email` →
  `"desconhecido"`; teto 120), `ip` (primeiro salto do `X-Forwarded-For`; fallback IP do
  socket), `metodo`, `rota` (teto 300), `query` (teto 2000; omitida se vazia), `status`,
  `duracao_ms`, `agente` (user-agent, teto 200; omitido se vazio), `bytes`
  (content-length da resposta; omitido se ausente).
- **Filtro "sem inflar"** (`relevante()`): ficam FORA os assets estáticos do SPA
  (`/assets/*` e extensões `.js/.css/.woff2/.png/...`) e o `/api/health` (healthcheck do
  compose a cada 30 s). Todo o resto entra — inclusive `/` e deep-links do SPA (sinal de
  navegação) e todos os `/api/*` (a query do Relatório Pontual carrega lat/lng e inputs
  de viabilidade: é exatamente o "o quê" da auditoria).
- **Arquivo por dia UTC** (`acesso-AAAA-MM-DD.jsonl`), append-only. Na primeira escrita
  de cada dia o gravador **poda** arquivos do padrão próprio (e somente dele) mais
  antigos que a retenção.
- **Rastro, não transação:** qualquer falha de escrita é engolida (1 aviso por processo
  no stderr) — a trilha **nunca** derruba uma requisição. Sem o volume montado, o app
  sobe e funciona normalmente.
- **Config:** `MOTOR_ACESSO_LOG_DIR` (default dev: `<repo>/data/acesso_log`, gitignored;
  produção: `/app/logs/acesso` via compose) e `MOTOR_ACESSO_RETENCAO_DIAS` (default 90).

### Guardrails

- **READ-ONLY sobre o M1 intacto:** o diretório da trilha mora **fora** de
  `MOTOR_DATA_DIR`, como o cadastro (DEC-023). O compose mantém a lista **exata** de
  mounts `:rw` do `web` travada por teste
  (`test_compose_monta_somente_cadastro_e_trilha_como_volumes_de_escrita`); o `app.py`
  continua sem escritor de filesystem (guardrail AST `test_backend_read_only_por_ast` —
  a escrita vive no módulo `acesso_log`).
- **Sem segredo, sem excesso:** a trilha não grava headers de autenticação, cookies nem
  corpo de requisição. O Caddy (camada 2) redige `Authorization`/`Cookie` por default
  (>= 2.5). Usuários são logins internos do Authelia; IPs são dado operacional de
  auditoria com retenção definida (90 dias) — postura LGPD da DEC-005 mantida.
- **Limite de confiança da identidade:** `Remote-User`/`X-Forwarded-For` são headers, e o
  backend `web:8899` não tem autenticação própria — a camada 1 só é **confiável para
  tráfego que passou pelo Caddy** (que sobrescreve `Remote-User` com o valor do Authelia
  e ignora XFF de cliente não confiável). Uma requisição feita direto ao container (outro
  processo na `app_net`, dev local) pode forjar usuário/IP na linha. Para perícia, cruzar
  com a camada 2: linha na trilha do app **sem par no access log do Caddy** = tráfego que
  não veio da borda. Mesmo limite já valia para o autor do cadastro (DEC-023).
- **Permissões:** o gravador cria o diretório com modo `0700` e os `.jsonl` com `0600`
  (dono `appuser` uid 1000); no host, criar o diretório com
  `install -d -m 0700 -o 1000 -g 1000` — a trilha é dado pessoal e não deve ser legível
  por qualquer conta local futura.

## Como consultar (read-only, na VPS)

```bash
# o que fulano fez ontem
grep '"usuario": "fulano' /opt/motor-expansao/logs/acesso/acesso-2026-08-16.jsonl

# quem gerou Relatorio Pontual na semana
grep '"rota": "/api/relatorio/pontual"' /opt/motor-expansao/logs/acesso/acesso-2026-08-1*.jsonl

# logins (sucesso e falha) com usuario + IP
docker logs motor_expansao_authelia 2>&1 | grep -iE "authentication attempt"

# edge bruto do piloto
tail -50 /opt/motor-expansao/logs/caddy/piloto-access.log
```

## Habilitação na VPS (passos manuais do Felipe — guardrail §6 do CLAUDE.md)

O merge + deploy da imagem `web` ativa a camada 1 **somente depois** destes passos
(cada comando é executado pelo humano, um a um):

1. **Diretórios no host** (dono = `appuser` uid 1000 da imagem web; o Caddy roda root;
   `-m 0700` porque o conteúdo é dado pessoal):
   ```bash
   install -d -m 0700 -o 1000 -g 1000 /opt/motor-expansao/logs/acesso
   install -d -m 0700 /opt/motor-expansao/logs/caddy
   ```
2. **Compose novo no servidor** (os volumes/env chegam pelo `git pull` do checkout em
   `/opt/motor-expansao/app` — conferir antes que `.env`/`Caddyfile`/`authelia/` locais
   não sejam sobrescritos, como manda o runbook).
3. **Caddyfile do servidor:** adicionar o bloco `log { ... }` no host
   `piloto.ultra-expansao.tech` (o arquivo local do repo já tem a versão de referência;
   o do servidor é editado à mão). Depois: `docker compose -f docker-compose.prod.yml
   restart caddy`. **Atualizar também o backup `secrets/Caddyfile.enc` (SOPS).**
4. **Authelia do servidor:** `log.level: info` em `authelia/configuration.yml` +
   `docker compose -f docker-compose.prod.yml restart authelia`.
5. **Subir o `web` novo** por digest (runbook `docs/deploy_piloto_web.md`) e conferir:
   navegar no piloto logado e `tail /opt/motor-expansao/logs/acesso/acesso-$(date -u
   +%F).jsonl` deve mostrar linhas com o seu usuário.

## Aba Acessos — painel restrito sobre a trilha (emenda DEC-027, 2026-08-19)

A trilha ganhou um consumidor visual: a aba `Acessos` do piloto
(`web/src/screens/AcessosScreen.tsx` + rotas `/api/acessos/*` servidas por
`src/motor_expansao/dashboard/acesso_analytics.py`). Contrato:

- **Autorização própria, mais forte que a das abas**: allowlist na env
  `MOTOR_ACESSOS_ADMIN_USUARIOS` (usuários Authelia separados por vírgula,
  case-insensitive), checada no middleware contra o `Remote-User`. FORA do
  `acesso_abas.json`: sem curinga, sem fail-open; `acessos` está fora de
  `ABAS_VALIDAS`, então concedê-la pelo JSON é permissão fantasma impossível.
  Quem está fora vê **404** (existência não anunciada). Env vazia/ausente =
  painel desligado para todos, em dev e em produção.
- **O que mostra**: agregados (série diária, heatmap hora×dia BRT, uso por aba,
  saúde 4xx/5xx + p95) e, por usuário (redesign de 2026-08-19): sessões (pausa
  > 30 min abre outra), linha do tempo das últimas 80 ações por FEATURE com hora
  e flag de erro, heatmap de horários, distribuição por aba, contagem de erros,
  sparkline de 14 dias na tabela e nº de IPs distintos. **O que nunca mostra**:
  rota, query/conteúdo (endereço pesquisado, parâmetros) e o IP em si — isso
  segue só na trilha bruta (o corte da emenda vale em toda a tela).
- **Rollup `uso-diario.json`** (mesmo diretório da trilha): consolidação
  write-once por dia BRT fechado com `{acoes, usuarios, por_aba}` — contagens,
  sem nome/IP/rota — e SEM poda: é o que dá tendência além dos 90 dias. Roda no
  startup do `web`, a cada abertura da aba **e na virada de dia da trilha**
  (hook em `acesso_log.registrar`, ANTES da poda — app meses de pé sem abertura
  da aba não perde dia). O nome não casa com o padrão `acesso-*.jsonl` da poda
  de propósito. Dia consolidado nunca é recalculado (o histórico fica estável
  mesmo depois de a trilha ser podada); um dia só consolida quando o SEU arquivo
  UTC existe e está legível (nunca congela subcontagem). Rollup com conteúdo
  inválido vai para quarentena (`uso-diario.json.corrompido`, bytes preservados)
  e NUNCA é sobrescrito às cegas; falha de IO transitória só adia a rodada.
- **Auto-observação fora das métricas**: `/api/acessos/*` entra na trilha
  (auditoria de quem olhou o painel) mas é excluído das contagens na aba E no
  relatório 3/3h do Telegram, pelo mesmo filtro (`evento_valido` +
  `ROTAS_FORA_DA_METRICA` em `relatorio_acessos.py`).
- Habilitação: adicionar `MOTOR_ACESSOS_ADMIN_USUARIOS=<usuario>` ao `.env` da
  VPS (o compose repassa ao serviço `web`) e recriar o `web`. Testes:
  `tests/unit/test_acesso_analytics.py` + seção "Aba Acessos" de
  `tests/unit/test_piloto_web_acesso.py`.

## O que continua fora (dívidas conhecidas)

- **Bot Telegram e API GeoEspacial**: log próprio anônimo/efêmero; sessões do bot sem
  expurgo. Fora deste ciclo por decisão de Felipe — retomar quando o bot voltar à pauta.
- **Correlação entre camadas** (request-id único app↔Caddy): não há; o timestamp + rota
  resolve na prática para o volume atual (~1 req/s de pico).
- **`/tiles/*`** (host `dashboard.`): sem access log de propósito — volume alto de
  requisições de tile com valor de auditoria baixo.
- **Envio dos logs para fora da VPS** (backup/central): pendente com o BLK-SEC-04
  (backup automatizado).
- **A poda de retenção é melhor-esforço**: ela roda dentro do `registrar()` (primeira
  escrita relevante de cada dia) — app parado ou sem tráfego = poda não roda. E o
  diretório é bind mount: **descomissionar o piloto exige apagar
  `/opt/motor-expansao/logs/acesso/` e `/opt/motor-expansao/logs/caddy/` à mão**, senão
  a trilha nominal fica órfã no host além do prazo declarado.
