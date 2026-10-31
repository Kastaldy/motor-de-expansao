# Índice de `docs/`

## Comece por aqui

**O que é o Motor de Expansão.** É o sistema da Ultra Academia (rede de academias low-cost, para o público de
massa) que ajuda a decidir onde abrir unidades novas. Ele divide o país em hexágonos de uns 5 km² e cruza, em
cada um, a população e a renda do Censo 2022 do IBGE, as academias concorrentes e as unidades da própria rede.
O resultado chega por um site, por relatórios em PDF (de um endereço ou de uma cidade), por um robô no Telegram
e por um serviço que gera relatórios para outros sistemas. Hoje há duas instâncias no ar: Brasil e Argentina.

Ele responde a quatro perguntas: onde expandir; quem já atua ali; quanto mercado ainda está livre; e, para um
imóvel concreto, se a unidade se paga. A primeira tem um ranking oficial (o M1), que só muda por decisão
registrada; as outras são análises complementares, que não mexem nele.

**Por onde ler, conforme o que você faz:**

- **Gestão e negócio:** o [glossário](glossario.md) → [estado_dos_modelos.md](estado_dos_modelos.md) (o que
  cada análise prevê, com que erro e como usar) → [relatorio_pontual_censitario.md](relatorio_pontual_censitario.md)
  (o PDF de um endereço) → o [`PREMISSAS_VIABILIDADE.md`](../PREMISSAS_VIABILIDADE.md) (as premissas da
  simulação financeira) → as decisões, em [decisions/](decisions/README.md).
- **Desenvolvimento:** o `CLAUDE.md` da raiz (as regras do projeto) →
  [arquitetura_app_atual.md](arquitetura_app_atual.md) → [m1_outputs_oficiais.md](m1_outputs_oficiais.md) e
  [modelo_mercado_hexagonos.md](modelo_mercado_hexagonos.md) → o `web/README.md` →
  [grafo_conhecimento.md](grafo_conhecimento.md) → o `tasks/backlog.md`.
- **Operação (servidor e publicação):** [infra_producao.md](infra_producao.md) →
  [deploy_piloto_web.md](deploy_piloto_web.md) → [deploy_api_bot.md](deploy_api_bot.md) →
  [banco_deploy.md](banco_deploy.md) → [backup_restore.md](backup_restore.md).

Os documentos principais abrem com um quadro "Em poucas palavras"; o texto abaixo dele segue técnico.

## Onde fica cada coisa

As pastas do topo do repositório e o que vai em cada uma. Antes de criar um arquivo, procure aqui a pasta
dele; se nenhuma serve, o arquivo provavelmente não é do projeto (rascunho, saída de comando) e fica fora
do git.

| Pasta | O que tem |
|---|---|
| `src/motor_expansao/` | O código Python do produto: os pipelines do M1 (`pipelines/m1/`), a API e o robô do Telegram (`api/`), os relatórios em PDF (`dashboard/`, nome que sobrou do Streamlit), a Viabilidade (`dimensionamento/`), o banco (`db/`) e as camadas paralelas. |
| `web/` | O site (piloto web): as telas em React (`web/src/`) e o servidor FastAPI (`web/server/`). |
| `tests/` | Os testes: `unit/`, `contracts/` (regras que não podem quebrar), `integration/` e `fixtures/` (dados sintéticos). |
| `data/` | Os dados. Quase tudo fica fora do git (`raw/`, `staging/`, `outputs/`, `ultra/`); no git ficam as malhas municipais (`ibge/`), os perfis de país (`perfis/`), o cache do OSM (`osm_cache/`, ver [artefatos_dados.md](artefatos_dados.md) §6), os estudos (`analysis/`) e os relatórios (`reports/`). |
| `docs/` | A documentação: este índice, as decisões (`decisions/`), o plano da América Latina (`expansao-latam/`) e o arquivo (`archive/`). |
| `tasks/` | O `backlog.md` (o que falta fazer) e o `completed.md` (o que já foi feito). |
| `scripts/` | Os scripts avulsos: ingestão, operação, governança da esteira e medições; os da rotina do servidor ficam em `scripts/cron/`. |
| `deploy/`, `openmaptiles-infra/`, `valhalla-infra/`, `secrets/` | A infraestrutura do servidor: o Caddy, o servidor de mapas, o de rotas e os segredos cifrados. |
| `.github/`, `.githooks/` | A automação: os testes e as checagens de cada PR e o gancho que atualiza o grafo a cada commit. |
| `.claude/`, `.codex/`, `prompts/` | A configuração dos agentes: comandos, skills e prompts da esteira. |
| `context/handoff/` | O registro das passagens de bastão entre sessões de agentes. |
| `graphify-out/` | O grafo de conhecimento do repositório, gerado por ferramenta ([grafo_conhecimento.md](grafo_conhecimento.md)). |
| `analysis/` | Os backtests antigos dos scores, que três testes ainda importam. |
| `fora_primeira_fase/` | O que ficou fora da primeira fase: o protótipo da API com PostGIS, o M2/M3 imobiliário, o Power BI e pesquisas. |

Na raiz ficam só os pontos de entrada e a configuração das ferramentas: `CLAUDE.md`, `README.md`,
`REVIEW.md`, `PREMISSAS_VIABILIDADE.md`, os `Dockerfile.*`, os `docker-compose.*.yml`, `pyproject.toml`,
`constraints.txt`, `conftest.py`, os lançadores (`iniciar-*.cmd`, `run-ralph-loop.sh`) e os arquivos de
configuração que começam com ponto.

**Para não voltar a bagunçar:**

- Documento novo vai para `docs/`, script novo para `scripts/` e código do produto para `src/motor_expansao/`
  ou `web/`. A raiz não recebe arquivo novo sem motivo.
- Estudo ou medição avulsa: o script em `data/analysis/` e o resultado que vale guardar em `data/reports/`.
  Código que a produção roda não vai para `data/` (a cadeia de `data/reports/crescimento/`, rodada pelo
  `src/motor_expansao/crescimento/atualizar.py`, é exceção herdada).
- Temporário fica fora do git: na pasta temporária do sistema ou numa `tmp/` ou `tmp_*/` da raiz, que o
  `.gitignore` ignora. Apague ao terminar.
- Antes de mover ou renomear um arquivo, veja se o guard (`scripts/loop_guard.py`) o protege pelo caminho
  (infraestrutura, banco, CI, prompts). Se protege, a regra do guard muda no mesmo PR; senão o arquivo fica
  sem proteção no lugar novo.
- Registro não se reescreve, só recebe acréscimo ou correção de caminho: `context/handoff/`, `docs/archive/`
  e `tasks/completed.md` (neste, o acréscimo vai no fim). Documento que saiu de uso vai para `docs/archive/`,
  com uma linha no README de lá.
- Cada sessão de agente trabalha numa worktree em `.claude/worktrees/`, que não vai para o git; quando o PR
  entra, a worktree sai (`git worktree remove <caminho>`).

## Índice dos documentos

Mapa de navegação dos contratos e runbooks do Motor de Expansão. Legenda de status:
**[canônico]** fonte atual · **[histórico]** descreve um estado antigo (ver o canônico apontado).

> A fonte de verdade curta do projeto é o `CLAUDE.md` (raiz); o roadmap por bloco é `tasks/backlog.md`;
> as decisões (DEC) ficam em [`docs/decisions/`](decisions/README.md).

## 1. Modelo, scores e relatórios
- [estado_dos_modelos.md](estado_dos_modelos.md) — **[canônico]** o que cada camada prevê, com que erro e como usar na decisão (inclui o modelo de praça da DEC-078).
- [m1_outputs_oficiais.md](m1_outputs_oficiais.md) — **[canônico]** contrato curto dos outputs oficiais do M1.
- [modelo_mercado_hexagonos.md](modelo_mercado_hexagonos.md) — **[canônico]** contrato de colunas/cálculos de mercado/residual.
- [camada_crescimento_municipal.md](camada_crescimento_municipal.md) — **[canônico]** contrato + runbook de publicação da camada de crescimento (passo 4 do piloto): join `cod6`, domínios fechados, validação HTTP pós-deploy e rollback.
- [repasse_migracoes_p19.md](repasse_migracoes_p19.md) — pacote de repasse das migrations 018/019/020 (sessão, senha temporária, origem): passo a passo auto-contido para quem NÃO conhece a epic executar na VPS, com o que esperar de cada comando, o passo do `GRANT` que se esquece (ensaiado, com o erro real reproduzido) e o caminho de volta.
- [repasse_logout_2h.md](repasse_logout_2h.md) — troca manual de `inactivity: 30m -> 2h` no Authelia da VPS (emenda D2 da DEC-067, 14/10/2026): backup, `sed`, conferência, restart que desloga BR + AR + `dashboard.`, e recifragem do backup SOPS, um comando por confirmação. Sem ele o merge do código não muda o logout de ninguém.
- [repasse_cron_crescimento.md](repasse_cron_crescimento.md) — pacote de repasse da atualização trimestral da camada de crescimento (DEC-052): insumos, instalação, modo seco, crontab e rollback, comando a comando para o dono executar na VPS.
- [runbook_atualizacao_renda.md](runbook_atualizacao_renda.md) — **[canônico]** atualização anual dos fatores de renda exibida (`motor_expansao.renda`): `atualizar_fatores` pela PNAD Contínua (a SIDRA 7531 só confere o nível, nunca gera crescimento), regra de exceção por UF (candidatas; inclusão é decisão humana), arquivos imutáveis + `VIGENTE`, rollback por PR ou `MOTOR_FATORES_RENDA_VERSAO` e conferência do `/api/health`.
- [vulnerabilidade_ma_contrato.md](vulnerabilidade_ma_contrato.md) — **[canônico]** contrato dos sinais de vulnerabilidade de academias independentes (funil de M&A, Plano B, READ-ONLY M1).
- [relatorio_pontual_censitario.md](relatorio_pontual_censitario.md) — **[canônico]** contrato do Relatório Pontual Censitário (1,0 km).
- [relatorio_municipal_template.md](relatorio_municipal_template.md) — template do Relatório Municipal.
- [artefatos_dados.md](artefatos_dados.md) · [fontes_dados_gratuitas.md](fontes_dados_gratuitas.md) — insumos e fontes de dados.
- [expansao_dominio.md](expansao_dominio.md) — **[canônico]** contrato do plano de expansão de domínio (âncoras por cidade, teses e gates), refeito toda semana.

## 2. App e Dashboard
- [arquitetura_app_atual.md](arquitetura_app_atual.md) — **[canônico]** arquitetura do app atual (piloto web: Início + telas de Mapa, Oportunidades, Ponto, Viabilidade, Executiva, Oportunidades imobiliárias e Acessos, sobre o motor compartilhado; Parte B preserva a história do Streamlit).
- [contrato_api_metodologia.md](contrato_api_metodologia.md) — **[canônico]** contrato do `GET /api/metodologia` (painel de metodologia do Mapa): payload, escopo das faixas e por que elas são DERIVADAS de `constants.FAIXAS_MAPA_*`.

## 3. API GeoEspacial
- [api_geoespacial_contrato.md](api_geoespacial_contrato.md) — **[canônico]** contrato da API on-demand.
- [api_geoespacial_uso.md](api_geoespacial_uso.md) — guia de uso (hub cross-linkado).
- [api_geoespacial_deploy.md](api_geoespacial_deploy.md) · [api_geoespacial_openapi.yaml](api_geoespacial_openapi.yaml) — deploy e OpenAPI.

## 4. Deploy, Infra e Ops
- [infra_producao.md](infra_producao.md) — **[canônico]** manutenção e deploy da VPS (fonte única de infra).
- [deploy.md](deploy.md) — runbook curto de deploy (modo PULL do GHCR).
- [deploy_api_bot.md](deploy_api_bot.md) — containerização/deploy da API + bot Telegram.
- [backup_restore.md](backup_restore.md) — **[canônico]** backup e regeneração (DR) de segredos e dados.
- [trilha_acesso_piloto.md](trilha_acesso_piloto.md) — **[canônico]** trilha de acesso do piloto (DEC-027): quem fez o quê, retenção e habilitação na VPS.
- [autenticacao_propria_p19.md](autenticacao_propria_p19.md) — escopo da epic do **P19** (o motor passa a autenticar e o Authelia sai): o que já existe no front e no backend, o ponto único de inserção da sessão no middleware, as duas rotas para ninguém ficar trancado no corte, as armadilhas medidas e as cinco decisões, fechadas em 25/09/2026 (execução em `repasse_corte_p19.md`). **Não é canônico de propósito** — a decisão mora no P19 (`banco-de-reservas/decisoes-pendentes.md`); aqui está o terreno dela.
- [deploy_piloto_web.md](deploy_piloto_web.md) — **[canônico]** runbook completo de deploy do piloto web (imagem `motor-expansao-web` por digest).
- [acesso_deploy_colaborador.md](acesso_deploy_colaborador.md) — **[canônico]** acesso SSH de deploy por pessoa (usuário `deploy`): onboarding, limites e revogação.
- [archive/deploy_vps_streamlit.md](archive/deploy_vps_streamlit.md) — **[histórico]** runbook antigo de deploy do Streamlit (ver `infra_producao.md`).
- [banco_conexao.md](banco_conexao.md) — **[canônico]** conexão com o banco PostgreSQL/PostGIS (`MOTOR_DATABASE_URL`): os três estados, leitura `READ ONLY` × escrita com `app.id_usuario`, e por que o diagnóstico não fica no `/api/health`.
- [banco_deploy.md](banco_deploy.md) — **[canônico]** runbook do banco: o **ensaio local** que precede qualquer
  subida, a ordem que evita trancar todo mundo para fora, provisionamento dos papéis do D20, backup/restore
  e o interruptor de rollback.
- [eventos_contrato.md](eventos_contrato.md) — **[canônico]** o que a tabela `eventos` registra: vocabulário fechado de `tipo`, de-para para `entidade`/`metadados`, e a fronteira entre AÇÃO (vai para o banco) e telemetria de requisição (segue em JSONL, DEC-027).

## 5. Orquestração, Loop e Governança
- [portao_merge_orq21.md](portao_merge_orq21.md) — **[canônico]** runbook do portão de merge (DEC-016/BLK-ORQ-21).
- [loop_autonomo.md](loop_autonomo.md) — runbook do loop "ralph".
- [garimpeiro.md](garimpeiro.md) — routine autônoma de execução de blocos loop-safe.
- [grafo_conhecimento.md](grafo_conhecimento.md) — **[canônico]** grafo de conhecimento (graphify): instalação (`--group graph`), consulta via MCP/CLI, `.mcp.json`, hooks em `.githooks/` e as duas limitações de instalação por clone.
- [decisions/](decisions/README.md) — **[canônico]** corpo completo das DECs (índice no `CLAUDE.md` §8).

## 6. Onboarding e Handoff
- [handoff_colaborador_run_cycle.md](handoff_colaborador_run_cycle.md) — handoff do /run-cycle.
- [handoff_repositorio.md](handoff_repositorio.md) — checklist para compartilhar o repositório com a equipe e operar o deploy do piloto web.

## 7. Planos, specs e notas
- [spec_portal_selecao_pais.md](spec_portal_selecao_pais.md) — **[canônico]** portal de seleção de país da raiz (DEC-047).
- [expansao-latam/](expansao-latam/README.md) — plano CO/MX/PE/PY (DEC-073, PROPOSTA).
- [runbook_deploy_renda_hex_e3.md](runbook_deploy_renda_hex_e3.md) · [renda/2026-10_pnad2025_v1.md](renda/2026-10_pnad2025_v1.md) — renda do hexágono (E3) e relatório da versão de fatores.
- [fontes_bases_poi.md](fontes_bases_poi.md) — base única de POI (BLK-UNI).
- [refatoracao/review.md](refatoracao/review.md) — review de refatoração.

## 8. Histórico e arquivo
- [archive/](archive/README.md) — planos e prompts já implementados/superados, preservados para auditoria.
