# Índice de `docs/`

Mapa de navegação dos contratos e runbooks do Motor de Expansão. Legenda de status:
**[canônico]** fonte atual · **[histórico]** descreve um estado antigo (ver o canônico apontado).

> A fonte de verdade curta do projeto é o `CLAUDE.md` (raiz); o roadmap por bloco é `tasks/backlog.md`;
> as decisões (DEC) ficam em [`docs/decisions/`](decisions/README.md).

## 1. Modelo, scores e relatórios
- [estado_dos_modelos.md](estado_dos_modelos.md) — **[canônico]** síntese de desempenho/arquitetura dos modelos + roadmap de produto.
- [m1_outputs_oficiais.md](m1_outputs_oficiais.md) — **[canônico]** contrato curto dos outputs oficiais do M1.
- [m1_1_arquitetura_enriquecimento.md](m1_1_arquitetura_enriquecimento.md) — design da camada M1.1.
- [modelo_mercado_hexagonos.md](modelo_mercado_hexagonos.md) — **[canônico]** contrato de colunas/cálculos de mercado/residual.
- [camada_crescimento_municipal.md](camada_crescimento_municipal.md) — **[canônico]** contrato + runbook de publicação da camada de crescimento (passo 4 do piloto): join `cod6`, domínios fechados, validação HTTP pós-deploy e rollback.
- [vulnerabilidade_ma_contrato.md](vulnerabilidade_ma_contrato.md) — **[canônico]** contrato dos sinais de vulnerabilidade de academias independentes (funil de M&A, Plano B, READ-ONLY M1).
- [relatorio_pontual_censitario.md](relatorio_pontual_censitario.md) — **[canônico]** contrato do Relatório Pontual Censitário (1,0 km).
- [relatorio_municipal_template.md](relatorio_municipal_template.md) — template do Relatório Municipal.
- [artefatos_dados.md](artefatos_dados.md) · [fontes_dados_gratuitas.md](fontes_dados_gratuitas.md) — insumos e fontes de dados.
- [analise_pontual_entorno.md](analise_pontual_entorno.md) · [expansao_dominio.md](expansao_dominio.md) · [mapa_territorial_unificado.md](mapa_territorial_unificado.md) — **[histórico]** contratos de ciclos de maio/2026.

## 2. App e Dashboard
- [arquitetura_app_atual.md](arquitetura_app_atual.md) — **[canônico]** arquitetura do app atual (piloto web: 3 superfícies + motor compartilhado; Parte B preserva a história do Streamlit).
- [contrato_api_metodologia.md](contrato_api_metodologia.md) — **[canônico]** contrato do `GET /api/metodologia` (painel de metodologia do Mapa): payload, escopo das faixas e por que elas são DERIVADAS de `constants.FAIXAS_MAPA_*`.
- [streamlit_dashboard_m1.md](streamlit_dashboard_m1.md) — **[histórico]** governança do dashboard Streamlit de 4 abas — app aposentado pela DEC-022 (2026-08-03); o app de produção é o piloto web (`deploy_piloto_web.md`).

## 3. API GeoEspacial
- [api_geoespacial_contrato.md](api_geoespacial_contrato.md) — **[canônico]** contrato da API on-demand.
- [api_geoespacial_uso.md](api_geoespacial_uso.md) — guia de uso (hub cross-linkado).
- [api_geoespacial_deploy.md](api_geoespacial_deploy.md) · [api_geoespacial_openapi.yaml](api_geoespacial_openapi.yaml) — deploy e OpenAPI.

## 4. Deploy, Infra e Ops
- [infra_producao.md](infra_producao.md) — **[canônico]** manutenção e deploy da VPS (fonte única de infra).
- [deploy.md](deploy.md) — runbook curto de deploy (modo PULL do GHCR).
- [deploy_api_bot.md](deploy_api_bot.md) — containerização/deploy da API + bot Telegram.
- [backup_restore.md](backup_restore.md) — **[canônico]** backup e regeneração (DR) de segredos e dados.
- [deploy_piloto_web.md](deploy_piloto_web.md) — **[canônico]** runbook completo de deploy do piloto web (imagem `motor-expansao-web` por digest).
- [deploy_plan.md](deploy_plan.md) · [archive/deploy_vps_streamlit.md](archive/deploy_vps_streamlit.md) — **[histórico]** planos/runbooks antigos de deploy (ver `infra_producao.md`).

## 5. Orquestração, Loop e Governança
- [portao_merge_orq21.md](portao_merge_orq21.md) — **[canônico]** runbook do portão de merge (DEC-016/BLK-ORQ-21).
- [loop_autonomo.md](loop_autonomo.md) — runbook do loop "ralph".
- [garimpeiro.md](garimpeiro.md) — routine autônoma de execução de blocos loop-safe.
- [grafo_conhecimento.md](grafo_conhecimento.md) — **[canônico]** grafo de conhecimento (graphify): instalação (`--group graph`), consulta via MCP/CLI, `.mcp.json`, hooks em `.githooks/` e as duas limitações de instalação por clone.
- [decisions/](decisions/README.md) — **[canônico]** corpo completo das DECs (índice no `CLAUDE.md` §8).
- [system_design_referencia.md](system_design_referencia.md) — referência de design de sistema.
- [uso_pratico_skills.md](uso_pratico_skills.md) — **[histórico]** guia de fases da esteira (superado pela DEC-016; ver `portao_merge_orq21.md` + `.claude/commands/run-cycle.md`).

## 6. Onboarding e Handoff
- [onboarding_colaborador_vini.md](onboarding_colaborador_vini.md) — onboarding de colaborador.
- [handoff_colaborador_run_cycle.md](handoff_colaborador_run_cycle.md) — handoff do /run-cycle.
- [handoff_repositorio.md](handoff_repositorio.md) — **[histórico]** handoff de repositório (maio/2026).

## 7. Histórico e arquivo
- [archive/](archive/README.md) — planos e prompts já implementados/superados, preservados para auditoria.
- [rev08_spike_perf_runbook.md](rev08_spike_perf_runbook.md) — **[histórico]** medição descartável do BLK-REV-08 (os scripts do spike saíram do repo com a DEC-022).
