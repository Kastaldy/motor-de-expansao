# Current Task

## Bloco atual

ID: BLK-ACENTO-01
Nome: Acentuação da UI do dashboard (Streamlit)
Status: APROVADO (QA 2026-07-07, re-verificação do follow-up) — ressalva anterior RESOLVIDA: build_faixa_comparison_figure agora exibe labels acentuados no eixo x/legenda via FAIXA_COLORS_POR_LABEL derivado, cor e ordem por faixa preservadas, valor bruto intocado. Suíte serial 1431 passed / 2 skipped / 1 falha pré-existente ambiental (M2 lifetime, gitignored). Pronto para fechamento (housekeeping move + commit por path pelo orquestrador).
Tipo: manutenção (correção ampla de texto de UI)
Criticidade: média
Esteira: Block Orchestrator → Planner → [confirmação humana — produto: D1 (label de exibição das faixas)] → Builder → QA
Skill atual: Fechamento (orquestrador) CONCLUÍDO
Skill anterior: QA (re-verificação — APROVADO em 2026-07-07)
Próxima Skill: revisão visual da UI + merge da branch ciclo/BLK-ACENTO-01 pelo humano (6.b). Sem dry-run (não tocou orquestração). Housekeeping move OK (--check verde) + commit por path feito.

## Gate humano (produto) — CONFIRMADO em 2026-07-07
- D1 = mapeamento FAIXA_LABELS proposto APROVADO (prioridade_maxima→"Prioridade máxima",
  alta→"Alta", media→"Média", baixa→"Baixa", descartado→"Descartado", inviavel→"Inviável").
  Criar em src/motor_expansao/dashboard/constants.py (correção do Planner; core/constants.py NÃO tocar).
- D1-bis = Opção A (label layer HYBRID_ELIGIBILITY_LABELS + format_func; valor bruto
  "Elegivel"/"Nao elegivel" INTOCADO; zero fixture de teste alterada).
- Fallback = trocar "Nao informado"→"Não informado" nas 5 ocorrências juntas.

## Objetivo
Acentuar corretamente TODO o texto voltado ao usuário na UI do dashboard Streamlit
(abas, labels, help=, st.caption/markdown/info/warning/success/error, st.metric,
column_config, legendas), preservando 100% dos identificadores (key=, .st-key-*, enums
brutos, nomes de coluna, slugs), READ-ONLY sobre o M1.

## Gate humano obrigatório
Apesar de criticidade Média, o bloco exige confirmação humana de PRODUTO na decisão D1
(camada de label de exibição das faixas: FAIXA_LABELS + format_func). Orquestrador PARA
após o Planner e aguarda aprovação explícita antes de spawnar o Builder.

## Tiering de modelo (Passo 4) — Média
- Block Orchestrator: sonnet
- Planner: sonnet
- Builder: opus (override +1: volume ~560 strings de UI + arquivo de teste de 6232 linhas + risco alto de acentuar identificador por engano — atipicamente complexo/arriscado para Média)
- QA: opus 4.8 (sempre)

## Branch do ciclo
ciclo/BLK-ACENTO-01 (criada a partir de main @ HEAD, working tree limpo).

## Paths do ciclo (commit por path — NUNCA git add -A)
- src/motor_expansao/dashboard/pages.py
- src/motor_expansao/dashboard/components.py
- src/motor_expansao/dashboard/data.py
- src/motor_expansao/core/constants.py (só onde string é EXIBIDA; D1 FAIXA_LABELS)
- streamlit_app.py
- tests/integration/test_streamlit_app.py, tests/unit/test_dashboard_format_utils.py
- tasks/current_task.md, tasks/completed.md, tasks/backlog.md (fechamento)
- context/handoff.md, context/handoff/

## Guardrails
- §5 READ-ONLY M1: zero recálculo/alteração de score/pesos/carteira/plano/artefatos oficiais.
- NUNCA acentuar identificadores: key=/st.session_state, .st-key-* CSS, valores brutos de
  enum/categoria (FAIXA_ORDEM etc.), nomes de coluna de DataFrame, slugs/nomes de arquivo.
- D1: label de exibição via {valor_bruto: "Texto Acentuado"} + format_func; valor bruto INTOCADO.
- Banir tipografia "esperta" na UI (hífen simples, aspas retas).
- Fora de escopo: relatórios PDF/CSV (BLK-ACENTO-02).
