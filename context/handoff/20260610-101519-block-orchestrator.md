# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner — (criticidade Estratégica; a esteira inclui GATE HUMANO obrigatório
das 6 decisões-chave de contrato ANTES do Builder).

## Bloco refinado
**BLK-API-01 — Definir arquitetura e contrato da API (G1)**
Bloco de DESIGN/DECISÃO, **sem código de produção**. Produz o contrato técnico
da API GeoEspacial (camada complementar de consumo do motor, alvo Telegram/WhatsApp),
o esboço OpenAPI dos endpoints do MVP, um ADR (nova DEC estilo CLAUDE.md §8) com as
decisões-chave resolvidas, e a decomposição de G2+ em blocos `BLK-API-02..0N`.
ClickUp `86e1rtfe3` (subtarefa de `86e1rtfcy`). G1 é pré-requisito de G2 (backend, Juan),
G3 (integração, Felipe+Juan) e G4 (Telegram/WhatsApp, Juan).

Premissas canônicas já fixadas (do backlog, decisão de Felipe 2026-06-09) que o
contrato deve registrar e NÃO reabrir:
- **Fonte on-demand a partir do motor**: a API importa `analisar_ponto_censitario_setores`
  + geradores de mapa/PDF e lê os Parquets locais de `data/outputs/setores_censitarios_2022_geo/`.
  **PostGIS fica como evolução futura, FORA do MVP.**
- **Fronteira inegociável "importa, não edita"**: a API trata a camada `censo_*`
  (`censo_point.py` / `censo_map.py` / `censo_report.py`) como interface estável —
  importa, nunca edita — para não colidir com a trilha do Vini (dashboard/PDF).
- Código novo da API mora em `src/motor_expansao/api/` (pasta disjunta); dependências
  só no extra `[api]` do `pyproject.toml`, fora do deploy base do Streamlit.

## Objetivo
Entregar um contrato de API aprovado por Felipe (contrato + OpenAPI + ADR + decomposição
de G2+), suficiente para o Juan implementar G2 sem re-discussão de arquitetura, com ZERO
código de produção e READ-ONLY sobre o M1.

## Escopo permitido
- Escrever `docs/api_geoespacial_contrato.md` — contrato técnico: layout do pacote
  `src/motor_expansao/api/`, fronteira "importa-não-edita `censo_*`", lista de endpoints,
  schemas request/response, auth, erros, versionamento e a decomposição `BLK-API-02..0N`.
- Escrever o esboço **OpenAPI** do MVP (`docs/api_geoespacial_openapi.yaml` OU bloco no contrato).
- Escrever o **ADR** (nova DEC estilo CLAUDE.md §8) registrando as 6 decisões-chave resolvidas
  no gate, com a opção escolhida por decisão.
- Atualização mínima de README.md / PRD.md: ponteiro para o contrato, SEM implementar a API.
- Atualizar `tasks/backlog.md` (decomposição BLK-API-02..0N), `tasks/current_task.md`,
  `tasks/completed.md`.
- `context/handoff.md` + snapshot em `context/handoff/`.
- **ÚNICA exceção possível de `src/`, SOMENTE se decidida no gate**: criar a pasta
  `src/motor_expansao/api/` **vazia** com `__init__.py` como marcação de layout — **sem lógica**.

## Fora de escopo
- Qualquer código de produção em `src/motor_expansao/` (rotas, handlers, schemas executáveis,
  config) — exceto a pasta `api/` vazia com `__init__.py`, se aprovada no gate.
- Implementar/expor a API, subir container, PostGIS (fica fora do MVP), integração
  Telegram/WhatsApp (G4).
- Editar a camada `censo_*` (`censo_point.py` / `censo_map.py` / `censo_report.py`) —
  é interface importada, nunca tocada (trilha do Vini).
- Recalcular ou alterar M1: `score_priorizacao`, `hex_score_estrutural`, pesos, carteira,
  plano curto prazo, plano de domínio, artefatos oficiais (§5).
- API ao vivo no dashboard de produção (§2/§4) — não é introduzida por este bloco.
- Resolver as 6 decisões-chave fora do gate humano; expandir para outros blocos da fase API.

## Arquivos que devem ser lidos
- `CLAUDE.md` (§2 fontes canônicas, §4 camadas paralelas, §5 READ-ONLY M1, §8 DECs)
- `tasks/backlog.md` (bloco BLK-API-01 ~linha 444 e cabeçalho do projeto "API GeoEspacial" ~linha 430)
- `tasks/current_task.md`
- `config.py` (parâmetros canônicos; só leitura)
- `PRD.md` (apenas trecho relevante para o ponteiro do README/PRD)
- `pyproject.toml` (extra `[api]` já presente: fastapi, uvicorn, pydantic, pydantic-settings,
  e — não necessárias ao MVP on-demand — psycopg2/alembic/geoalchemy2/prefect; G1 decide o subset)
- Scaffold legado (SÓ leitura, para registrar o que aproveitar):
  `fora_primeira_fase/api_postgis/main.py`, `database.py`, `models.py`, `001_initial_schema.py`,
  `Dockerfile.api`, `docker-compose.yml`
- Interface estável a importar (SÓ leitura): `src/motor_expansao/dashboard/censo_point.py`
  (`analisar_ponto_censitario_setores`), `censo_report.py`
  (`gerar_pdf_relatorio_pontual_censitario`), `censo_map.py`

## Arquivos que podem ser alterados
- `docs/api_geoespacial_contrato.md` (novo)
- `docs/api_geoespacial_openapi.yaml` (novo, ou bloco no contrato)
- `docs/` — destino do ADR a confirmar pelo Planner (DEC nova; pode ir em CLAUDE.md §8 ou doc dedicado)
- `tasks/backlog.md`, `tasks/current_task.md`, `tasks/completed.md`
- `README.md`, `PRD.md` (ponteiro mínimo, sem implementar)
- `context/handoff.md` + `context/handoff/AAAAMMDD-HHMMSS-<slug>.md`
- (Condicional, só se aprovado no gate) `src/motor_expansao/api/__init__.py` vazio

## Decisões que EXIGEM gate humano (NÃO resolver aqui — Planner apresenta opção+recomendação; Felipe decide no Passo 5)
1. **Formato de saída** — (a) JSON KPIs / (b) PDF binário inline / (c) [recomendado] ambos por
   negociação (`/analisar` JSON default + `?formato=pdf` ou `Accept: application/pdf`) / (d) JSON + link p/ PDF.
2. **Autenticação** — (a) API key estática `X-API-Key` / (b) [recomendado] token por consumidor/bot
   (rastreia quem pediu; casa com BLK-EST-01 marca d'água+solicitante/logs LGPD) / (c) reuso Authelia/JWT.
3. **Superfície de endpoints do MVP** — (a) [recomendado] mínimo `GET /health` + `POST /analisar`
   (censitário 1.5 km) / (b) acrescentar lookup hex M1 / camada mercado. (Alimenta a decomposição BLK-API-02..0N.)
4. **Entrada de coordenada** — (a) só `{lat,lng}` / (b) [recomendado] `{lat,lng}` + link Google Maps (parser).
5. **Raio de análise no MVP** — (a) [recomendado] fixo 1.5 km (motor intocado) / (b) parametrizável (revalidar interseção).
6. **Carimbo de versão/reprodutibilidade** — [recomendado] incluir versão do contrato/score no JSON e no rodapé do PDF.

> O Block Orchestrator NÃO resolve nenhuma destas. O Planner deve apresentá-las com opções +
> recomendação; a decomposição de `BLK-API-02..0N` depende sobretudo das decisões 1 e 3.

## Critérios de aceite
- `docs/api_geoespacial_contrato.md` + esboço OpenAPI + ADR escritos e coerentes entre si.
- As 6 decisões-chave RESOLVIDAS no gate e registradas no ADR com a opção escolhida.
- Decomposição de G2+ em blocos `BLK-API-02..0N` explícita, com escopo de cada um.
- Registradas no contrato: fronteira "importa-não-edita `censo_*`" e "on-demand, PostGIS fora do MVP".
- **ZERO código de produção** — git scope só em `docs/`, `tasks/`, `README.md`/`PRD.md`
  (+ no máximo `src/motor_expansao/api/__init__.py` vazio, se aprovado no gate).
- Suíte + ruff + mypy verdes (bloco de docs não pode quebrar nada).
- READ-ONLY M1 comprovado: sem escrita em `pipelines/`, `config.py`, scoring, carteira, plano, artefatos oficiais.

## Criticidade classificada
**Estratégica** — nova fase: stand-up de uma API e redesenho da superfície de consumo do motor.
Decisão arquitetural de plataforma, com gate humano obrigatório das 6 decisões-chave antes do Builder.
(Não é Crítica no sentido §M1: o bloco é READ-ONLY sobre o M1 e não toca score/pesos/artefatos —
mas a esteira exige aprovação humana pela natureza estratégica/contratual.)

## Esteira recomendada
Block Orchestrator → Planner → **[REVISÃO HUMANA — 6 decisões-chave de contrato]** → Builder → QA
(Tiering Passo 4: BO=opus, Planner=opus, Builder=opus, QA=opus 4.8 sempre.)

## Riscos identificados
- **Vazamento de escopo para código**: tentação de implementar rotas/handlers. Mitigar: gate de
  git scope só em `docs/`/`tasks/`/`README`/`PRD` (+ `api/__init__.py` vazio condicional).
- **Resolver decisões sem gate**: Planner/Builder não podem fixar as 6 decisões antes de Felipe.
- **Reabrir premissas fechadas**: PostGIS no MVP ou editar `censo_*` violam decisões já tomadas (2026-06-09).
- **Colisão com a trilha do Vini**: qualquer edição em `censo_point/map/report.py` quebra a fronteira "importa-não-edita".
- **Acoplar deploy do Streamlit ao extra `[api]`**: deps da API devem ficar fora do deploy base.
- **Arrasto do worktree pré-sujo** (deleções de `data/raw/ibge/*.geojson` não relacionadas):
  commitar SÓ paths do ciclo por path; nunca `git add -A`.
- **Scaffold legado desatualizado** (`fora_primeira_fase/api_postgis/` assume PostGIS/Sentry/structlog):
  G1 decide o que aproveitar; não importar o desenho PostGIS por inércia.

## Guardrails ativos
- **§2 (fontes canônicas)**: `config.py`, `CLAUDE.md`, `PRD.md` são fontes de parâmetros/guardrails;
  ler o repositório real antes de editar; toda mudança relevante entra com teste; nenhum PR com CI quebrado.
- **§5 (READ-ONLY M1 / guardrail permanente)**: visualizações e camadas paralelas NÃO podem recalcular
  nem alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano de domínio
  ou artefatos oficiais do M1 sem aprovação explícita. A API é camada paralela de consumo — READ-ONLY.
- **§4 (camadas paralelas)**: preservar 100% das linhas/colunas oficiais do M1; não criar dependência
  de API ao vivo no dashboard de produção.
- **§6 (deploy/VPS é humano)**: não se aplica diretamente (G1 não faz deploy); registrado para a fase API.
- **Fronteira "importa-não-edita `censo_*`"** e **"on-demand, PostGIS fora do MVP"** (Felipe, 2026-06-09): invioláveis.
- Um bloco por vez; não expandir escopo; não implementar; não resolver as 6 decisões.
