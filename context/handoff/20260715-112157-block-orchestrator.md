# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
BLK-RELPON-07 — Slide de perfil do Bairro/Distrito no Relatório Pontual Censitário
(estilo GeoFusion "Microárea").

## Objetivo
Adicionar ao Relatório Pontual Censitário (PDF) uma nova página "Perfil do
Bairro/Distrito" — nas duas variantes `censitario` e `classico`, inserida entre
Concorrentes e Big Numbers — com 4 blocos de dado fiel (título+unidade, população,
densidade demográfica, domicílios, renda média) agregados sobre TODO o bairro
(fallback distrito) que contém o pin pesquisado, independente do raio de 1,5 km.

## Decisões de produto já fechadas (NÃO reabrir — Vinicius, 2026-07-15)
- **D1 — unidade geográfica:** BAIRRO (`nome_bairro`/`cod_bairro`) com fallback para
  DISTRITO (`nome_distrito`) quando `nome_bairro` é nulo (~39% dos setores
  nacionais). `subdistrito` é descartado (não usar `nome_subdistrito` neste bloco,
  mesmo que exista no artefato geo). O rótulo do slide deve indicar qual unidade
  está sendo mostrada (ex.: subtítulo "bairro de {município}" ou "distrito de
  {município}").
- **D2 — escopo:** agregar TODOS os setores cujo `cod_bairro` (ou, no fallback,
  `nome_distrito`) é igual ao do setor que CONTÉM o ponto — o bairro/distrito
  inteiro, não o raio de 1,5 km. Base para o lookup do "setor do ponto": reusar a
  lógica já existente do BLK-RELPON-05 (`cod_setor_ponto`/`contains_ponto` em
  `analisar_ponto_censitario_setores`, `src/motor_expansao/dashboard/censo_point.py`
  linhas ~254-304). Os setores da unidade já estão disponíveis: `setores_df` (a
  partição municipal completa carregada por `censo_geo_loader`/
  `read_censo_geo_partition`) é o mesmo DataFrame já passado a
  `analisar_ponto_censitario_setores` e a `render_mapas_censitarios_combinados`
  em `src/motor_expansao/dashboard/pages.py` (ver linhas ~3419-3435) — não requer
  nova carga de dado.
- **D3 — só 4 blocos com dado fiel** (confirmado que os campos-fonte existem no
  artefato geo, ver "Viabilidade medida" no backlog):
  1. Título — nome do bairro (fallback distrito) + contexto do município.
  2. População — `Σ pop_total_setor_2022` dos setores da unidade.
  3. Densidade Demográfica — `população / (Σ area_setor_m2 / 1e6)` em hab/km².
  4. Domicílios — `Σ domicilios_particulares_ocupados_setor_2022`.
  5. Renda Média — **método de ponderação A DEFINIR pelo Planner**: preferir renda
     média domiciliar ponderada por domicílios (leitura GeoFusion "Renda Média");
     alternativa é `renda_per_capita_setor_2022_calibrada` ponderada por população.
     Documentar a escolha no handoff do Planner para ficar auditável (não confundir
     com a renda do raio do BLK-RELPON-06 nem com o setor do pin do BLK-RELPON-05).
     Formatar em R$, padrão ASCII do PDF (`_ascii()`, latin-1 — sem travessão/
     bullet/aspas curvas fora de latin-1).
  Faixa etária, faixa de renda ABEP e PEA **NÃO entram** (sem dado — não reabrir).
- **Ordem final do PDF (as duas variantes):** Capa → Mapas de calor → Concorrentes →
  **Perfil do Bairro/Distrito** → Big Numbers → Realização/Crédito.
- **Contagem de páginas: 5→6** nas duas variantes (`censitario` e `classico`) —
  mudança INTENCIONAL deste bloco.

## Esteira — divergência a resolver e decisão tomada
`tasks/backlog.md` registra a esteira como `Block Orchestrator → Planner →
[REVISÃO HUMANA — visual do PDF] → Builder → QA` (gate ANTES do Builder).
`tasks/current_task.md` e a instrução do orquestrador para este ciclo dizem
`Block Orchestrator → Planner → Builder → QA → [revisão visual humana do PDF,
pós-QA] → merge`. **Como D1/D2/D3 já foram respondidas por Vinicius e não há
decisão de produto pendente para o Planner levantar**, este handoff adota a
esteira do `current_task.md`/instrução do ciclo: **revisão humana do PDF ocorre
DEPOIS do QA, antes do merge** (gate visual final, não gate de decisão). Se o
Planner identificar alguma ambiguidade residual de produto ao detalhar D3.5
(método de renda) ou D1 (formato do rótulo), deve levantar isso explicitamente
no handoff para gate humano ANTES do Builder — não presumir.

## Escopo permitido
- `src/motor_expansao/dashboard/censo_point.py`:
  - Expor no `result` de `analisar_ponto_censitario_setores` os campos de
    identificação do bairro/distrito do pin (ex.: `cod_bairro_ponto`,
    `nome_bairro_ponto`, `nome_distrito_ponto`, `unidade_ponto_rotulo` já com o
    fallback resolvido) — reusando o mesmo `ponto_row` (setor que contém o ponto,
    linhas ~292-304) já calculado para os 5 campos `*_setor_ponto` do
    BLK-RELPON-05. SÓ LEITURA de `nome_bairro`/`cod_bairro`/`nome_distrito` do
    setor do ponto; não tocar interseção/raio/circle_metric.
  - Novo helper de AGREGAÇÃO por bairro/distrito (pode viver em `censo_point.py`
    ou módulo próprio dentro de `dashboard/`) que recebe `setores_df` (partição
    municipal completa) + o identificador da unidade (cod_bairro ou
    nome_distrito) resolvido acima, filtra os setores da unidade e calcula
    população, densidade, domicílios e renda média ponderada. "n/d" gracioso
    quando o pin cai fora de qualquer setor da malha OU a unidade não tem dado
    suficiente (não lançar exceção).
- `src/motor_expansao/dashboard/censo_report.py`:
  - Nova página "Perfil do Bairro/Distrito" nas DUAS variantes (recente/
    `_UltraPDF` via `gerar_pdf_relatorio_pontual_censitario` E `classico` via
    `gerar_pdf_relatorio_pontual_classico`), inserida entre `_competitors_page`/
    `_classico_competitors_page` e `_big_numbers_page`.
  - Atualizar `PDF_SECTION_HEADERS` (linha 24-30): inserir o rótulo da nova seção
    entre `"Concorrentes"` e `"Big Numbers"` (5 strings → 6).
  - Atualizar os temas bicolor (`_tema_bicolor`, hoje só 3 páginas de conteúdo —
    ver comentários "3 paginas de conteudo" nas linhas ~1092-1095/1164-1168) para
    4 páginas de conteúdo.
  - Marca d'água (`_draw_watermark`, laço `for page_number in range(1,
    pdf.pages_count + 1)`) deve continuar cobrindo TODAS as páginas incluindo a
    nova — isso já é automático por iterar `pdf.pages_count`, mas o Builder deve
    confirmar/testar explicitamente.
  - Se o Planner decidir que a nova página precisa de mapa (não é claramente
    exigido por D3 — os 4 blocos são numéricos/texto, sem mapa), documentar a
    decisão; caso contrário, página é texto/números apenas (mais simples, sem
    nova geração de PNG).
- Testes novos/atualizados:
  - Agregação por bairro (com e sem fallback para distrito; "n/d" quando o pin
    cai fora da malha ou fora de qualquer setor).
  - Presença e conteúdo da nova página no PDF, nas duas variantes.
  - Atualização dos testes de contagem de páginas/`/Count`/headers que HOJE
    esperam 5 (não relaxar — atualizar para 6). Ver lista de testes afetados
    abaixo em "Riscos".
- `docs/relatorio_pontual_censitario.md`: atualizar §7 (estrutura de páginas,
  `PDF_SECTION_HEADERS`, contagem) e, se aplicável, §4/§5.1 se algum campo novo
  do artefato geo for consumido de forma diferente da já documentada.
- `tasks/completed.md`: entrada de fechamento do ciclo (passo do Builder/QA, não
  deste Orchestrator).

## Fora de escopo
- Método de interseção `setor_censitario_intersecao_area_1p5km`, raio 1,5 km,
  `RAIO_CENSITARIO_DEFAULT_KM`.
- Mapas de calor/choropleth, faixa "no raio" (BLK-RELPON-06), grid de Big Numbers
  4x2, marca d'água anti-PII (só CONSUMIR o laço existente, não redesenhar).
- `score_priorizacao`/pesos/`hex_score_estrutural`/carteira/plano/artefatos
  oficiais do M1.
- Faixa etária, faixa de renda ABEP e PEA (sem dado — não entram, D3).
- `subdistrito`/`nome_subdistrito` como unidade geográfica (descartado por D1;
  mesmo que exista no artefato, não usar).
- Relatório Municipal (`relatorio_municipal.py`) e UI interativa do dashboard
  fora do Relatório Pontual (este bloco só toca o PDF do Relatório Pontual).
- Qualquer dependência de rede nova (tiles, geocoding).
- `set_compression(False)`, `pdf_version="1.4"`.
- Reabrir D1/D2/D3 ou a esteira de gate humano.

## Arquivos que devem ser lidos
- CLAUDE.md (completo)
- tasks/current_task.md
- tasks/backlog.md (bloco BLK-RELPON-07, linhas 1623-1711)
- docs/relatorio_pontual_censitario.md (especialmente §4 "Colunas canônicas",
  §5 "Método de interseção" com a nota BLK-RELPON-05, §7 "Export CSV e PDF")
- src/motor_expansao/dashboard/censo_point.py (função
  `analisar_ponto_censitario_setores`, linhas ~145-310; ver campos
  `cod_setor_ponto`/`contains_ponto` do BLK-RELPON-05 como precedente direto)
- src/motor_expansao/dashboard/censo_report.py (`PDF_SECTION_HEADERS` linhas
  24-30; `_mapas_calor_page`/`_classico_mapas_calor_page`; `_competitors_page`/
  `_classico_competitors_page`; `_big_numbers_page`;
  `gerar_pdf_relatorio_pontual_censitario` linhas ~1137-1187;
  `gerar_pdf_relatorio_pontual_classico`, ~1090-1116; `_tema_bicolor`)
- src/motor_expansao/dashboard/pages.py (linhas ~3415-3475, chamada de
  `analisar_ponto_censitario_setores`/`render_mapas_censitarios_combinados`/
  `render_downloads_relatorio_censitario` com `setores_df` já carregado)
- src/motor_expansao/pipelines/materializar_setores_censitarios_geo.py (linhas
  ~90-93, 158-280, 372-375 — confirma que `cod_bairro`/`nome_bairro`/
  `nome_subdistrito`/`nome_distrito` já existem no artefato geo particionado)
- tests/unit/test_relatorio_pontual_censitario_export.py (testes de estrutura/
  contagem hoje esperando 5 páginas — a atualizar)

## Arquivos que podem ser alterados
- src/motor_expansao/dashboard/censo_point.py
- src/motor_expansao/dashboard/censo_report.py
- tests/unit/test_relatorio_pontual_censitario_*.py
- docs/relatorio_pontual_censitario.md
- tasks/completed.md
- context/handoff.md e context/handoff/*.md (append-only)
- tasks/current_task.md

## Critérios de aceite
- Relatório Pontual (PDF) passa a ter a página "Perfil do Bairro/Distrito" nas
  duas variantes (`censitario` e `classico`), com os 4 blocos (título+unidade,
  população, densidade, domicílios, renda média) agregados sobre o bairro (ou
  distrito, no fallback) que contém o pin — não o raio de 1,5 km.
- Município sem bairro (ex.: fora de SP) exercita o fallback para distrito sem
  slide vazio; ponto fora de qualquer setor da malha mostra "n/d" gracioso sem
  exceção.
- Contagem de páginas, `/Count` e `PDF_SECTION_HEADERS` atualizados de 5→6 nas
  duas variantes; testes de estrutura ATUALIZADOS (não relaxados) para refletir
  6 páginas e a nova seção na posição correta (entre Concorrentes e Big
  Numbers).
- Marca d'água (BLK-EST-01) cobre a página nova, testado explicitamente.
- Interseção `setor_censitario_intersecao_area_1p5km`, raio 1,5 km, marca
  d'água anti-PII e M1 (score/pesos/artefatos oficiais) INTOCADOS.
- `ruff`/`mypy` limpos; suíte unit relevante e suíte full verdes.
- Revisão visual humana do PDF aprovada (pós-QA, antes do merge — ver seção
  "Esteira" acima).

## Criticidade classificada
Média — confirmado. Não envolve `score_priorizacao`/`hex_score_estrutural`/
carteira/plano/artefatos oficiais do M1 (não é Crítica); é mudança estrutural
intencional e testada do PDF do Relatório Pontual, com decisões de produto já
fechadas (não é Alta por decisão pendente).

## Esteira recomendada
Block Orchestrator → Planner → Builder → QA → [revisão visual humana do PDF,
pós-QA] → merge. QA sempre em Opus (tiering já fixado em
`tasks/current_task.md`: BO=sonnet, Planner=sonnet, Builder=sonnet, QA=opus).

## Riscos identificados
- **Contagem de páginas muda de propósito** — quebra testes de estrutura hoje
  fixados em 5 páginas/`/Count 5`/5 headers (ex.:
  `tests/unit/test_relatorio_pontual_censitario_export.py`:
  `test_slide_unico_count_5_e_titulo_mapas_de_calor`,
  `test_pdf_estrutura_inalterada_com_faixa_valor_ponto_blk_relpon_05`, e
  quaisquer asserts de `/Count 5`/5 headers/contagem de imagens). Devem ser
  ATUALIZADOS para 6, não relaxados nem removidos.
- **Bairro ausente em ~39% dos setores nacionais** — fallback para distrito
  precisa ser exercitado por teste com um município sem bairro (fora de SP;
  `nome_bairro` nulo na malha) para garantir que o slide não fica vazio nem
  quebra.
- **Ponto fora de qualquer setor (água/orla)** — `flag_setor_ponto_encontrado =
  False` já existe (BLK-RELPON-05); o novo bloco de agregação por bairro deve
  herdar esse "n/d" gracioso sem exceção quando não há setor do ponto.
- **Renda média — método de ponderação (D3.5)** — decisão técnica do Planner,
  não reabertura de D1-D3; documentar claramente o campo/peso escolhido (renda
  domiciliar por domicílios vs. per capita por população) para o número não ser
  confundido com a renda do raio (BLK-RELPON-06) nem com a renda do setor do
  pin (BLK-RELPON-05). Se ambíguo, levantar para gate humano ANTES do Builder.
- **Tema bicolor / helpers de layout hoje hardcoded para 3 páginas de
  conteúdo** (`_tema_bicolor(1)`/`(2)`/`(3)` nas duas funções `gerar_pdf_*`) —
  precisam virar 4 sem quebrar a alternância turquesa/magenta existente das
  páginas já testadas.
- **Consistência semântica no slide** — deixar explícito no texto do PDF que é
  o bairro/distrito INTEIRO (não o raio de 1,5 km nem o setor do ponto), para
  não conflitar com os outros números do relatório (Big Numbers, mapas de
  calor).

## Guardrails ativos
- READ-ONLY sobre o M1: nenhuma alteração em `score_priorizacao`,
  `hex_score_estrutural`, pesos (`renda=0.40`/`pop=0.60`), carteira, plano curto
  prazo, plano de domínio ou artefatos oficiais do M1 (CLAUDE.md §5).
- Método de interseção `setor_censitario_intersecao_area_1p5km`, raio de 1,5 km
  e `RAIO_CENSITARIO_DEFAULT_KM` são INTOCÁVEIS (CLAUDE.md §4, contrato
  `docs/relatorio_pontual_censitario.md` §5).
- Toda mudança relevante entra com teste; nenhum PR sobe com CI quebrado
  (CLAUDE.md §2).
- Acentuação correta do português em todo texto voltado ao usuário no PDF; usar
  pontuação ASCII (sem travessão/bullet/seta/reticências/aspas curvas/©) porque
  o writer usa Helvetica core font em latin-1 via `_ascii()` (CLAUDE.md §2,
  regra de acentuação).
- Anti-PII: PDFs nunca versionados; nenhum dado de pessoa física (nome/telefone/
  e-mail) pode aparecer no novo slide — só agregados estatísticos do Censo por
  bairro/distrito.
- `set_compression(False)`/`pdf_version="1.4"` (auditabilidade anti-PII) devem
  permanecer inalterados ao adicionar a nova página.
