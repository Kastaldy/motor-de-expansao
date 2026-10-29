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
  referência visual que o plano explica, `Motor de Expansão - Referência (standalone).html`, segue na raiz.
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

Removidos em 29/10/2026, por já estarem cobertos por outro documento (o git guarda o texto; para ler,
`git log --all --full-history -- <caminho>`): `PRD.md`, `STATUS_ORQUESTRACAO.md`,
`docs/m1_1_arquitetura_enriquecimento.md`, `docs/uso_pratico_skills.md`, `docs/rev08_spike_perf_runbook.md`,
`docs/analise_pontual_entorno.md`, `docs/streamlit_dashboard_m1.md`, `docs/mapa_territorial_unificado.md`,
`openmaptiles-infra/HANDOFF_LIDER.md`, `docs/deploy_plan.md` e `docs/onboarding_colaborador_vini.md`.

Fonte de verdade atual: `CLAUDE.md` (regras) · `tasks/backlog.md` (roadmap) · `docs/README.md` (índice).
