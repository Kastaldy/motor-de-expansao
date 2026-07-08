# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
BLK-ACENTO-02 — Acentuação dos relatórios gerados (PDF/CSV): Relatório Pontual Censitário 1,5 km
(`censo_report.py`) e Relatório Municipal (`relatorio_municipal.py`). Segundo sub-bloco da epic
BLK-ACENTO (BLK-ACENTO-01, UI do dashboard, já concluído em 2026-07-07); independente, mesma
branch compartilhada `ciclo/BLK-ACENTO-01` por decisão explícita de Vinicius (um único PR para os
dois blocos).

## Objetivo
Acentuar corretamente o texto-fonte dos dois relatórios PDF/CSV (renderiza via latin-1 no core
font Helvetica do fpdf2, que cobre integralmente os acentos portugueses), banindo em troca toda
tipografia fora de latin-1 (travessão, bullet, seta, reticências unicode, aspas curvas, ©) que hoje
vira `"?"` silenciosamente via `_ascii(..., errors="replace")` — sem tocar núcleo funcional, fonte,
biblioteca ou estrutura de páginas.

## Escopo permitido
- Reescrever com acento correto as strings-fonte voltadas ao usuário em
  `src/motor_expansao/dashboard/censo_report.py` (~50 chamadas `_ascii(...)`, incluindo
  `PDF_SECTION_HEADERS` em `censo_report.py:21-27`) e
  `src/motor_expansao/dashboard/relatorio_municipal.py` (~142 ocorrências / ~55 pares
  `set_font`+`_ascii`, incluindo `PDF_SECTION_HEADERS` em `relatorio_municipal.py:62-71`): títulos,
  rótulos de Big Numbers, legendas de mapas, rodapé, textos de zona/síntese.
- Manter as funções `_ascii()` (`censo_report.py:170-172`, `relatorio_municipal.py:211-213`)
  INTOCADAS na lógica — seguem como salvaguarda de encoding; só o texto que passa por elas muda.
- Corrigir os comentários-fonte enganosos que dizem "ASCII, sem acento": `censo_report.py:16`
  ("Cabecalhos canonicos das 5 paginas do template Ultra (ASCII, sem acento problematico)") e
  `relatorio_municipal.py:60-61` ("Cabecalhos canonicos das 9 paginas (ASCII; ...)") — reescrever
  para refletir que latin-1 cobre acentuação e que o que se proíbe é tipografia fora de latin-1.
- Banir tipografia "esperta" em todo texto de PDF: substituir `—`/`–` por `-`, `•` por `-` ou
  marcador ASCII equivalente, `→` por `->` (padrão já usado alhures no código), `…` por `...`,
  aspas curvas por aspas retas `"`, `©` por `(c)`.
- Adicionar teste(s) de regressão anti-`"?"`: gerar os PDFs (pontual + municipal) e assertar que
  nenhum byte `b"?"` inesperado aparece nos bytes crus (aproveita `set_compression(False)` que já
  expõe o texto sem compressão — `censo_report.py:228-236` e equivalente em
  `relatorio_municipal.py`); alternativa/complemento: rodar `_ascii` em modo auditoria com
  `errors="strict"` para pegar caractere fora de latin-1 antes de virar `"?"`.
- Atualizar os asserts de bytes existentes para as novas strings acentuadas (em `latin-1`, ex.
  `b"Visao"` -> `"Visão".encode("latin-1")`):
  - `tests/unit/test_relatorio_municipal.py` — 26 ocorrências de `assert b"..."` confirmadas
    (grep), próximo das linhas citadas no backlog (354-368, 467-472, 498, 558-583).
  - `tests/unit/test_relatorio_pontual_censitario_export.py` — 40 ocorrências de `assert b"..."`
    confirmadas (grep), próximo das linhas citadas no backlog (125-126, 268-269, 311-326, 382-416,
    554-556).
  - O laço que itera `PDF_SECTION_HEADERS` e faz `assert header.encode("latin-1") in pdf_bytes` lê
    a constante (não precisa mudar por si só), mas os asserts de string literal isolados precisam
    ser atualizados um a um.
- Fechamento de ciclo: `tasks/current_task.md`, `tasks/completed.md`, `tasks/backlog.md`,
  `context/handoff.md` e `context/handoff/`.

## Fora de escopo
- Núcleo funcional `censo_*`: `setor_censitario_intersecao_area_1p5km`, raio 1,5 km,
  `RAIO_CENSITARIO_DEFAULT_KM`, contagem/ordem/estrutura das páginas dos dois relatórios, grid de
  Big Numbers, marca d'água anti-PII (BLK-EST-03), `set_compression(False)`, `pdf_version`. Só as
  STRINGS de texto mudam — nenhuma lógica, nenhum cálculo, nenhuma coordenada de layout.
- UI do dashboard (Streamlit) — já coberta pelo BLK-ACENTO-01 (concluído).
- Qualquer coluna/valor bruto de enum, `key=` de widget, seletor CSS, nome de coluna de DataFrame
  ou slug/nome de arquivo — lista de proibições fixada no cabeçalho da epic BLK-ACENTO
  (`tasks/backlog.md` ~1223-1240) e em CLAUDE.md §2 (regra permanente).
- `score_priorizacao`/M1/artefatos oficiais — READ-ONLY total (§5).
- Trocar o core font Helvetica por TTF Unicode — não necessário; latin-1 basta para os acentos
  portugueses.
- Qualquer outro bloco da epic ou do backlog além de BLK-ACENTO-02.

## Arquivos que devem ser lidos
- `CLAUDE.md` (completo, com atenção à §2 e §4 — já lido pelo Block Orchestrator).
- `tasks/backlog.md` (cabeçalho da epic BLK-ACENTO ~1188-1244 e bloco BLK-ACENTO-02 ~1252-1303).
- `tasks/current_task.md` (branch compartilhada, tiering de modelo, paths do ciclo).
- `src/motor_expansao/dashboard/censo_report.py` (completo — texto-fonte, `_ascii`,
  `PDF_SECTION_HEADERS`, comentário-fonte a corrigir).
- `src/motor_expansao/dashboard/relatorio_municipal.py` (completo — mesma finalidade).
- `tests/unit/test_relatorio_municipal.py` (completo).
- `tests/unit/test_relatorio_pontual_censitario_export.py` (completo).
- `docs/relatorio_pontual_censitario.md` e `docs/relatorio_municipal_template.md` (contrato de
  estrutura/páginas, para confirmar que nada estrutural será tocado).

## Arquivos que podem ser alterados
- `src/motor_expansao/dashboard/censo_report.py` (só strings + comentário-fonte).
- `src/motor_expansao/dashboard/relatorio_municipal.py` (só strings + comentário-fonte).
- `tests/unit/test_relatorio_municipal.py`
- `tests/unit/test_relatorio_pontual_censitario_export.py`
- `tasks/current_task.md`, `tasks/completed.md`, `tasks/backlog.md` (fechamento de ciclo).
- `context/handoff.md`, `context/handoff/` (novos snapshots).

## Critérios de aceite
- Todo texto voltado ao usuário nos dois relatórios usa acentuação correta em português (títulos,
  `PDF_SECTION_HEADERS`, Big Numbers, legendas, rodapé).
- Zero caractere de tipografia "esperta" (`—`, `–`, `•`, `→`, `…`, aspas curvas, `©`) no texto-fonte
  de PDF; tudo em ASCII de pontuação (`-`, `"`, "(c)", "...").
- Comentários enganosos ("ASCII, sem acento") corrigidos em `censo_report.py:16` e
  `relatorio_municipal.py:60-61`.
- `_ascii()` preservada como salvaguarda em ambos os módulos, sem mudança de assinatura/lógica.
- Novo teste de regressão anti-`"?"` verde: PDFs gerados (pontual + municipal) sem byte `b"?"`
  inesperado nos bytes crus.
- Todos os `assert b"..."` dos dois arquivos de teste atualizados e verdes (26 + 40).
- Núcleo `censo_*` (interseção, raio, `RAIO_CENSITARIO_DEFAULT_KM`, contagem/ordem/estrutura de
  páginas, grid de Big Numbers, marca d'água BLK-EST-03, `set_compression(False)`, `pdf_version`)
  byte-a-byte equivalente em comportamento — só o conteúdo textual muda.
- Suíte completa verde (`pytest -q`), ruff e mypy limpos.
- Revisão visual humana do PDF (pontual + municipal) aprovada antes do fechamento (sem gate
  humano formal na esteira, mas o critério de aceite exige essa checagem visual).
- `score_priorizacao`/pesos/artefatos oficiais do M1: mtime e conteúdo inalterados.

## Criticidade classificada
Média

## Esteira recomendada
Block Orchestrator (concluído) → Planner → Builder (Opus, override +1) → QA (Opus 4.8) — sem gate
humano formal na esteira (revisão visual do PDF é critério de aceite, não gate de aprovação de
decisão de produto).

## Riscos identificados
- Introduzir, ao acentuar, algum caractere fora de latin-1 (aspas curvas copiadas de fonte externa,
  travessão de editor, reticências unicode) que vira `"?"` silenciosamente via
  `errors="replace"` — mitigado pelo teste anti-`"?"` obrigatório.
- Tocar por engano estrutura/núcleo fora de escopo: método de interseção, raio de 1,5 km, contagem/
  ordem de páginas, grid de Big Numbers, marca d'água anti-PII, `set_compression`, `pdf_version`.
- Acentuar por engano um identificador da lista canônica de proibições (enum bruto, `key=`, coluna
  de DataFrame, slug) em vez de só o texto de exibição — risco herdado da epic, relevante mesmo
  neste sub-bloco de relatório (ex.: `template="classico"`, `METODO_RELATORIO_*` NÃO são texto de
  exibição e não devem ser acentuados).
- Volume alto de ocorrências (~50 em censo_report.py, ~142 em relatorio_municipal.py, 66 asserts de
  teste) cria risco de inconsistência (algumas strings acentuadas, outras esquecidas) — mitigado
  por revisão completa arquivo-a-arquivo e pelo teste de regressão cobrindo os bytes crus inteiros.
- Falso-negativo do teste anti-`"?"`: se o PDF já tiver algum `"?"` legítimo pré-existente (parte do
  texto, não erro de encoding), o teste precisa diferenciar — Planner deve especificar a estratégia
  exata (whitelist de `"?"` esperado vs. comparação de contagem antes/depois, ou `errors="strict"`
  em modo auditoria que falha explicitamente no encode).

## Guardrails ativos
- CLAUDE.md §2 (regra permanente de acentuação, promovida por esta epic): todo texto voltado ao
  usuário em dashboard e relatórios gerados deve usar acentuação correta; NUNCA acentuar
  identificadores (`key=`, `session_state`, seletores CSS, valores brutos de enum/categoria, nomes
  de coluna, slugs/nomes de arquivo) — usar camada de LABEL de exibição quando necessário. No PDF
  (fpdf2 core font Helvetica, latin-1 via `_ascii()`), acentos portugueses renderizam normalmente,
  mas caracteres fora de latin-1 (travessão, bullet, seta, reticências, aspas curvas, ©) viram `"?"`
  silenciosamente — usar pontuação ASCII.
- CLAUDE.md §5 (guardrail permanente): visualizações e relatórios não podem recalcular ou alterar
  `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano de domínio ou
  artefatos oficiais do M1 sem aprovação explícita — este bloco é puramente de display/texto.
- Anti-PII inalterado: compressão de stream OFF (`set_compression(False)`) mantida para
  auditabilidade; marca d'água do solicitante (BLK-EST-03) intocada; `.pptx`/PDF nunca versionados;
  `image24.png` nunca embutido.
- Lista canônica de proibições de identificadores (`tasks/backlog.md` ~1223-1240): não acentuar
  `FAIXA_ORDEM`, `HYBRID_ELIGIBILITY_ORDER`, `COVERAGE_BUCKET_ORDER`, `JOIN_QUALITY_ORDER`,
  `template="classico"`, `METODO_RELATORIO_*`, nomes de coluna de DataFrame, slugs/nomes de arquivo.
- Sem dependência de rede nova; nenhuma DEC necessária (criticidade Média, sem alteração de
  fórmula/pesos/artefato M1).
