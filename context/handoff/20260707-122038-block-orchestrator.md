# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
BLK-ACENTO-01 — Acentuação da UI do dashboard (Streamlit). Corrigir a acentuação de TODO texto
voltado ao usuário na plataforma (abas, labels, botões, `help=`, `st.caption/markdown/info/
warning/success/error`, `st.metric`, `column_config`, legendas), preservando 100% dos
identificadores usados em lógica/CSS/schema. Inclui a decisão de produto D1: criar uma camada de
label de exibição (`FAIXA_LABELS`) para as faixas de `FAIXA_ORDEM`, usada via `format_func`, sem
tocar o valor bruto usado em `.isin`/dict de cores.

## Objetivo
Acentuar corretamente o texto de exibição do dashboard Streamlit sem alterar nenhum identificador,
valor de enum, nome de coluna, `key=`, seletor CSS ou slug — puro trabalho de display, READ-ONLY
sobre o M1.

## Escopo permitido
- Acentuar strings de EXIBIÇÃO em `src/motor_expansao/dashboard/pages.py` (~359 ocorrências) e
  `src/motor_expansao/dashboard/components.py` (~161 ocorrências) — concentram ~90% da massa de
  texto do bloco.
- Acentuar strings de exibição em `streamlit_app.py` (~38 ocorrências).
- Acentuar labels/mensagens de exibição em `src/motor_expansao/dashboard/data.py` — NÃO os valores
  de categoria salvos/comparados, exceto via camada de label (ver D1 abaixo para o caso específico
  do fallback "Nao informado").
- Acentuar em `src/motor_expansao/core/constants.py` SOMENTE onde a string é efetivamente EXIBIDA e
  não é usada como chave/valor lógico (ex.: rótulos, textos de legenda). NÃO tocar os valores brutos
  de `FAIXA_ORDEM`, `HYBRID_ELIGIBILITY_ORDER`, `COVERAGE_BUCKET_ORDER`, `JOIN_QUALITY_ORDER`.
- **D1 (decisão de produto — requer confirmação humana explícita antes do Builder):** criar
  `FAIXA_LABELS = {"prioridade_maxima": "Prioridade máxima", "alta": "Alta", "media": "Média",
  "baixa": "Baixa", "descartado": "Descartado", "inviavel": "Inviável"}` em `constants.py` e usar
  `format_func=` no `st.multiselect` de `pages.py:668-671` e em legendas/tabelas que exibem essas
  faixas — o VALOR bruto (`FAIXA_ORDEM`) usado no filtro/`.isin`/dict de cores fica INTOCADO. Avaliar
  se o mesmo padrão se aplica a `HYBRID_ELIGIBILITY_ORDER`/`COVERAGE_BUCKET_ORDER`/
  `JOIN_QUALITY_ORDER` (o Planner decide se há exibição bruta desses enums que precise de label
  equivalente).
- O fallback literal `"Nao informado"` (`data.py:211,219,223`; `components.py:572,589`) PODE virar
  "Não informado" DESDE QUE trocado em TODAS as ocorrências simultaneamente (é literal repetido, não
  comparado a dado externo/coluna) — validar que segue casando corretamente com
  `pd.Categorical(...)` onde for usado como categoria.
- Banir tipografia "esperta" na UI por consistência (hífen simples `-`, aspas retas `"`, sem
  travessão/bullet/seta/reticências tipográficas/aspas curvas).
- Atualizar os testes que travam strings de UI: `tests/integration/test_streamlit_app.py` (6232
  linhas; dezenas de asserts de string — ex.: linhas 334, 338, 762, 1112-1117, 1355-1357, 3199,
  3238-3239, 3664-3666, 4650-4653) e `tests/unit/test_dashboard_format_utils.py`.

## Fora de escopo
- Relatórios PDF/CSV (Relatório Pontual Censitário, Relatório Municipal) — isso é BLK-ACENTO-02,
  bloco separado e independente. NÃO tocar `censo_report.py`, `relatorio_municipal.py`,
  `censo_point.py`, `censo_map.py` neste bloco.
- Qualquer valor bruto de enum/categoria comparado em lógica: `FAIXA_ORDEM`,
  `HYBRID_ELIGIBILITY_ORDER`, `COVERAGE_BUCKET_ORDER`, `JOIN_QUALITY_ORDER`, `template="classico"`,
  `METODO_RELATORIO_*`.
- `key=` de widgets Streamlit e chaves de `st.session_state` (ex.: `coord_search_input`,
  `dashboard_active_tab`, `relpon_lote_fila`, `btn_gerar_pdf_topo`, `multihex_cenario`).
- Seletores CSS `.st-key-*` em `inject_styles` (`pages.py:154, 358-448`).
- Nomes de coluna de DataFrame (`score_priorizacao`, `nome_municipio`, `renda_per_capita`,
  `faixa_oportunidade`, `cod_municipio`, etc.) — schema compartilhado com M1/pipeline.
- Slugs/nomes de arquivo — já protegidos por `_slug()`/`unicodedata` (`relatorio_municipal.py:
  216-221`) e `_relmun_key_slug` (`pages.py:3194`); não mexer.
- `score_priorizacao`, `hex_score_estrutural`, pesos, carteira, plano curto prazo, plano de
  domínio, qualquer artefato oficial do M1 — zero recálculo, zero alteração.
- Qualquer dependência de rede nova.
- Resolver mais de um bloco: BLK-ACENTO-02 NÃO entra nesta execução.

## Arquivos que devem ser lidos
- `c:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\CLAUDE.md` (completo, §2 e lista de
  proibições de identificadores)
- `c:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\tasks\backlog.md` (linhas ~1188-1289:
  cabeçalho da epic BLK-ACENTO + bloco BLK-ACENTO-01 completo, incluindo a lista canônica de
  proibições da epic, linhas 1223-1240)
- `c:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\tasks\current_task.md`
- `c:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\src\motor_expansao\dashboard\pages.py`
- `c:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\src\motor_expansao\dashboard\components.py`
- `c:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\src\motor_expansao\dashboard\data.py`
- `c:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\src\motor_expansao\core\constants.py`
- `c:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\streamlit_app.py`
- `c:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\tests\integration\test_streamlit_app.py`
- `c:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\tests\unit\test_dashboard_format_utils.py`

## Arquivos que podem ser alterados
- `src/motor_expansao/dashboard/pages.py`
- `src/motor_expansao/dashboard/components.py`
- `src/motor_expansao/dashboard/data.py`
- `src/motor_expansao/core/constants.py` (só strings exibidas; adição de `FAIXA_LABELS` do D1)
- `streamlit_app.py`
- `tests/integration/test_streamlit_app.py`
- `tests/unit/test_dashboard_format_utils.py`
- `tasks/current_task.md`, `tasks/completed.md`, `tasks/backlog.md` (fechamento do ciclo)
- `context/handoff.md`, `context/handoff/` (novos snapshots)

## Critérios de aceite
- Varredura por amostra de palavras comuns sem acento (ex.: "Relatorio", "Analise", "Nao",
  "concluido", "endereco", "ultimo", "Populacao", "municipio", "regiao", "voce", "opcao") em texto
  de exibição de `pages.py`/`components.py`/`streamlit_app.py`/`data.py` retorna ~0 ocorrências fora
  de identificadores/comentários de código.
- Faixas de `FAIXA_ORDEM` exibidas com label acentuado (via `FAIXA_LABELS`/`format_func`), mas o
  comportamento de filtro (`.isin(selected_faixas)`) permanece idêntico ao valor bruto anterior —
  nenhuma regressão funcional no multiselect nem no dict de cores.
- Nenhum `key=`, `.st-key-*`, nome de coluna de DataFrame, valor bruto de enum (`FAIXA_ORDEM`,
  `HYBRID_ELIGIBILITY_ORDER`, `COVERAGE_BUCKET_ORDER`, `JOIN_QUALITY_ORDER`, `template="classico"`,
  `METODO_RELATORIO_*`) ou slug foi alterado.
- Nenhuma tipografia "esperta" (travessão, bullet, seta, reticências, aspas curvas, `©`) introduzida
  na UI — usar hífen simples e aspas retas.
- Suíte completa verde (`pytest -q`), incluindo os testes atualizados de
  `tests/integration/test_streamlit_app.py` e `tests/unit/test_dashboard_format_utils.py`.
- `ruff` e `mypy` limpos.
- Revisão visual humana da UI aprovada (screenshot/rodada manual do dashboard).
- Zero alteração em `score_priorizacao`/`hex_score_estrutural`/pesos/carteira/plano/artefatos
  oficiais do M1 (mtime dos parquets oficiais inalterado).

## Criticidade classificada
Média — confirmado. Não envolve `score_priorizacao`, `hex_score_estrutural`, pesos, carteira, plano
curto prazo, plano de domínio nem qualquer artefato oficial do M1 (guardrail de escalonamento
automático para Crítica do prompt canônico do Block Orchestrator NÃO se aplica aqui — é correção
ampla de texto de UI, puro display). Ainda assim, o bloco carrega uma decisão de produto (D1) que
exige confirmação humana explícita antes do Builder, conforme já registrado em
`tasks/current_task.md` e no backlog.

## Esteira recomendada
Block Orchestrator → Planner → **[gate humano obrigatório — confirmação de produto sobre D1:
`FAIXA_LABELS` + `format_func`, e sobre a troca do fallback "Nao informado"]** → Builder (override de
modelo: Opus, por volume ~560 strings de UI + arquivo de teste de 6232 linhas + risco de acentuar
identificador por engano) → QA (Opus 4.8, sempre).

## Riscos identificados
- Acentuar por engano um identificador de lógica: `key=`/`st.session_state`, seletor CSS
  `.st-key-*`, valor bruto de enum (`FAIXA_ORDEM` e demais `*_ORDER`), nome de coluna de DataFrame,
  ou slug/nome de arquivo — quebraria filtro, CSS, `.isin`, dict de cores ou geração de arquivo.
  Mitigação: lista canônica de proibições da epic (backlog linhas 1223-1240) + camada de label
  (D1) em vez de editar o valor bruto.
- Trocar o fallback "Nao informado" em algumas ocorrências e não em outras, quebrando a comparação
  com `pd.Categorical(...)` que depende do literal exato.
- Introduzir tipografia "esperta" (travessão, aspas curvas etc.) ao "melhorar" o texto — não é
  proibida tecnicamente na UI (diferente do PDF `latin-1`), mas o bloco bane por consistência com
  BLK-ACENTO-02.
- Volume alto (~560 ocorrências em `pages.py`+`components.py`) e teste de integração de 6232 linhas
  aumentam risco de dessincronia entre string alterada e assert de teste correspondente não
  atualizado — mitigado pelo tiering de modelo (Builder em Opus) e pela suíte completa como gate.
- Confundir este bloco com o BLK-ACENTO-02 (relatórios PDF/CSV) e tocar `censo_report.py`/
  `relatorio_municipal.py` por engano — fora de escopo explícito.

## Guardrails ativos
- §2 (CLAUDE.md) — regra permanente de acentuação: todo texto voltado ao usuário deve ter
  acentuação correta do português; NUNCA acentuar identificadores (`key=`/`st.session_state`,
  seletores CSS `.st-key-*`, valores brutos de enum/categoria, nomes de coluna de DataFrame,
  slugs/nomes de arquivo); usar camada de LABEL de exibição para exibir acentuado sem tocar o valor
  bruto.
- §5 (CLAUDE.md) — guardrail permanente: visualizações/UI não podem recalcular ou alterar
  `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano de domínio ou
  artefatos oficiais do M1 sem aprovação explícita. Este bloco é puro display.
- Lista canônica de proibições da epic BLK-ACENTO (`tasks/backlog.md:1223-1240`) — reproduzida
  acima em "Fora de escopo" e "Riscos identificados".
- Autonomia do bloco: **manual (NÃO loop-safe)** — não marcar para o loop autônomo (`ralph`);
  exige revisão humana.
