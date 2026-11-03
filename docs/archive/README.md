# `docs/archive/` — histórico preservado

Documentos **já implementados ou superados** que saíram do caminho de leitura primária, mas são
preservados para auditoria (o git também preserva o histórico). **Não** são fonte de verdade; cada um
aponta para o que o substituiu.

- `orquestracao_agentes.md` · `orquestracao_claude.md` — planos originais da esteira de agentes
  (maio/2026). A esteira descrita **já existe**: `.claude/commands/run-cycle.md`, `prompts/`,
  `.github/workflows/` (guard/claude-review), `REVIEW.md`. Orquestração viva = **/run-cycle + DEC-016**.
- `PLANO_ORQUESTRACAO_V2.md` — rascunho do plano ORQ (BLK-ORQ-10…18), **implementado** sob os IDs
  ORQ-20…27 e formalizado na **DEC-016** (`docs/decisions/DEC-016.md`). Mantido como registro.
- `PROMPT_PRD.md` — prompt do fluxo single-agent antigo ("execute o próximo bloco do PRD"), substituído
  pela esteira `/run-cycle` que lê `tasks/backlog.md`.
- `relatorio_analise_mercado.md` — snapshot analítico de maio/2026.
- `plano_multipais.md` — plano da Argentina (31/08/2026), executado nos Blocos A a E. As decisões do dono
  que valem estão na DEC-047 (seção «Decisões de subida do dono»); o estado da AR e as pendências de
  plataforma, em `docs/expansao-latam/00-baseline-argentina.md`. Arquivado palavra por palavra porque o
  anexo `fase0-b-receita-argentina.md` e a `spec_portal_selecao_pais.md` o citam por número de linha.
- `PLANO_APP_WEB.md` — plano do piloto web (jul/2026), executado (DEC-020, DEC-022); saiu da raiz do
  repositório em 29/10/2026. O app de hoje está em `web/README.md` e `docs/arquitetura_app_atual.md`; a
  referência visual que o plano explica é o HTML do item seguinte.
- `referencia_visual_piloto_standalone.html` — protótipo visual do piloto web, num HTML só que abre no
  navegador: a referência de alta fidelidade do `PLANO_APP_WEB.md` (§17); o mapa nele é falso (hexágonos
  desenhados em CSS, dados inventados). Saiu da raiz em 31/10/2026. Nome antigo, ainda citado no plano,
  num teste do guard e em comentários do `web/`:
  `Motor de Expansão - Referência (standalone).html`.
- `plano_visao_executiva_2.md` — plano da Visão Executiva 2.0, executado em 04/08/2026 (DEC-023). As regras
  vigentes estão na DEC-023, no `web/README.md` e comentadas em `rede_metricas.py`, `rede_diagnostico.py`
  e `rede_cadastro.py`.
- `modelo_dimensionamento_expansao.md` — spec do CEO (jun/2026) que originou a epic BLK-DIM (DEC-008). As
  camadas 3 e 4 viraram o simulador e as camadas 1 e 2 foram substituídas pelo modelo de praça da DEC-078;
  o que vale hoje está no `PREMISSAS_VIABILIDADE.md` e na DEC-078.
- `nota_impacto_fin_viab_01.md` — nota ao Comitê sobre a 3ª rodada do FIN-VIAB-01 (24/07/2026), com
  números que a 4ª rodada superou; o caso de referência vigente está no `PREMISSAS_VIABILIDADE.md` §15.
- `system_design_referencia.md` — pesquisa de jul/2026 com referências externas que embasou o redesenho
  do app; a conclusão que importa está em `docs/arquitetura_app_atual.md` A.3.
- `spec_bloco_a_perfil.md` — spec executável do Bloco A do perfil de país, executada em 02/09/2026. O
  schema vigente é o do loader `src/motor_expansao/perfil.py` com a tabela do `data/perfis/LEIA-ME.md`
  §3.2; a operação do `perfil.json` está em `docs/deploy_piloto_web.md`.
- `premissas_viabilidade_historico.md` — trechos de história tirados do `PREMISSAS_VIABILIDADE.md` em
  03/11/2026, palavra por palavra: regras antigas, rodadas de cálculo superadas e emendas. O que vale hoje
  está no documento principal.
- `relatorio_pontual_historico.md` — trechos de história tirados do `docs/relatorio_pontual_censitario.md` em
  03/11/2026, palavra por palavra: a cronologia das páginas do PDF, as validações de maio e junho, a época do
  Streamlit e os defeitos já consertados. O que vale hoje está no documento principal.
- `repasse_corte_p19.md` — roteiro do corte do P19, que levou o login próprio do Motor ao piloto do Brasil
  (DEC-067); executado na produção em 27/10/2026. O texto descreve o estado de 24/10/2026, antes do corte.
  O que vale hoje está no `docs/autenticacao_propria_p19.md`, no `docs/banco_deploy.md` e na DEC-067; a
  seção «Se precisar voltar atrás» continua citada pelo `infra_producao.md` e pelo `banco_deploy.md` como o
  caminho de volta.
- `repasse_migracoes_p19.md` — pacote para aplicar as migrations 018, 019 e 020 do P19 num banco que já
  existia. Na produção ele não se aplicou: o banco nasceu do zero em 17/10/2026, já com as 21 migrations,
  pelo `docs/banco_deploy.md`.
- `repasse_logout_2h.md` — troca manual da inatividade do Authelia de 30 min para 2 h na VPS (emenda D2 da
  DEC-067, de 14/10/2026), executada em 17/10/2026. Desde o corte do P19, no Brasil o logout por
  inatividade vem da sessão própria do Motor (`INATIVIDADE_MIN = 120` em `src/motor_expansao/db/sessoes.py`).
- `infra_producao_historico.md` — trechos de história tirados do `docs/infra_producao.md` em 03/11/2026,
  palavra por palavra: carimbos de data, a época do Streamlit, o "como era antes", incidentes já consertados,
  passos de instalação já feitos e o login do Brasil antes do corte do P19. O que vale hoje está no documento
  principal.

Removidos em 29/10/2026, por já estarem cobertos por outro documento (o git guarda o texto; para ler,
`git log --all --full-history -- <caminho>`): `PRD.md`, `STATUS_ORQUESTRACAO.md`,
`docs/m1_1_arquitetura_enriquecimento.md`, `docs/uso_pratico_skills.md`, `docs/rev08_spike_perf_runbook.md`,
`docs/analise_pontual_entorno.md`, `docs/streamlit_dashboard_m1.md`, `docs/mapa_territorial_unificado.md`,
`openmaptiles-infra/HANDOFF_LIDER.md`, `docs/deploy_plan.md` e `docs/onboarding_colaborador_vini.md`.

Fonte de verdade atual: `CLAUDE.md` (regras) · `tasks/backlog.md` (roadmap) · `docs/README.md` (índice).
