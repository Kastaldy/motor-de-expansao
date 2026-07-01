# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
BLK-RELPON-01 — Três mapas de calor (população/renda/score) num único slide do Relatório Pontual.
Hoje as 3 camadas de choropleth censitário (Densidade/População, Renda, Score censitário) ocupam
1 slide cada (páginas 2, 3 e 4 do PDF de 7 páginas), em ambas as variantes do Relatório Pontual
Censitário — `gerar_pdf_relatorio_pontual_censitario` (template recente) e
`gerar_pdf_relatorio_pontual_classico` (template GeoFusion). O bloco consolida os 3 mapas num
único slide "Mapas de calor", lado a lado, legíveis e sem sobreposição, levando o PDF de 7 para
5 páginas nas duas variantes.

## Objetivo
Substituir as 3 páginas individuais de choropleth (Densidade/Renda/Score) por 1 único slide com
os 3 mapas lado a lado, em ambas as variantes do Relatório Pontual, mantendo `/Count` consistente,
estética/guardrails atuais e zero impacto no M1.

## Escopo permitido
- Novo montador de página único (ex.: `_mapas_calor_page` para o template recente e
  `_classico_mapas_calor_page` para o template clássico) que recebe os 3 PNGs
  (`layers["densidade"]`, `layers["renda"]`, `layers["score"]`) e os posiciona lado a lado numa
  grade dentro da área de conteúdo (abaixo da faixa de título/banda, acima do rodapé), sem
  sobrepor faixa de título, rodapé ou marca d'água. Substitui as 3 chamadas atuais de
  `_map_page`/`_classico_map_page` para densidade/renda/score por 1 chamada ao novo montador,
  nas duas orquestrações (`gerar_pdf_relatorio_pontual_censitario` e
  `gerar_pdf_relatorio_pontual_classico`, em `src/motor_expansao/dashboard/censo_report.py`,
  atualmente nas linhas ~1033-1044 e ~1117-1119 respectivamente).
- Reuso das funções de desenho de imagem já existentes como base (`_draw_map`/`_classico_draw_map`,
  linhas ~295-336, desenham 1 PNG grande cada; o novo código precisa de uma variante que desenhe
  3 PNGs menores lado a lado dentro da mesma área) — decidir se cria helper novo de "3 PNGs numa
  grade" reaproveitando a lógica de escala/proporção (`_png_dimensions`, cálculo de
  `scale = min(max_w/img_w, max_h/img_h)`) já usada nas duas funções de desenho existentes.
- Atualizar `PDF_SECTION_HEADERS` em `tests/unit/test_relatorio_pontual_censitario_export.py`
  (linhas 20-28; hoje tupla de 7 strings: "Relatorio Pontual Censitario", "Populacao", "Renda",
  "Score censitario", "Concorrentes", "Big Numbers", "Realizacao" — cada uma é um assert literal
  contra os bytes crus do PDF) para refletir o novo título único do slide consolidado (decisão do
  Planner/gate: qual literal substitui "Populacao"/"Renda"/"Score censitario" — provavelmente
  "Mapas de calor" ou título equivalente que precisa aparecer nos bytes do PDF).
- Atualizar todos os 7 asserts `b"/Count 7" in pdf_bytes` no arquivo de teste (linhas 139, 191,
  218, 232, 323, 391, 423 — confirmado por grep) para `b"/Count 5"`.
- Revisar `_count_layer_titles` (linhas 116-124; hoje conta 3 títulos de página:
  `b"Populacao - Densidade"`, `b"Renda per capita"`, `b"Score censitario"`, usado em
  `test_export_pdf_executivo_gera_bytes_com_secoes_obrigatorias_e_mapa` e
  `test_pdf_embute_tres_camadas`) — com os 3 mapas no mesmo slide, decidir se os mini-títulos por
  mapa continuam existindo como texto (mantendo a contagem == 3) ou se o teste precisa de nova
  lógica de verificação (ex.: contar `/Subtype /Image` em vez de título de página).
- Revisar `assert pdf_bytes.count(b"/Subtype /Image") >= 4` (linhas 143 e 395) — a composição de
  3 PNGs numa página só + 1 na página de Concorrentes ainda deve somar >= 4 imagens; confirmar que
  a extração/posicionamento dos 3 PNGs no novo montador não reduz esse número por engano (ex.: se
  o Planner optar por pré-compor os 3 num único PNG combinado antes de embutir, a contagem cai
  para 1 imagem nessa página — decisão a expor no handoff do Planner, pois muda o critério de teste).
- Testes novos exigidos pelo backlog: slide único contém os 3 mapas sem sobreposição (checagem de
  bounding boxes no montador novo), `/Count` novo (5), geração offline-safe por camada (fallback
  "mapa indisponível" quando uma camada faltar — reusar o padrão já usado em `_map_page`/
  `_classico_map_page` quando `png_bytes` é `None`, linhas ~445-451 e ~825-831).
- Se a legibilidade em 960×540 exigir, parâmetro OPCIONAL novo em `render_mapas_censitarios_combinados`
  (`src/motor_expansao/dashboard/censo_map.py`, assinatura atual nas linhas 643-660, já com
  `street_ceil`/`street_gain`/`street_cap`/`choropleth_alpha` opcionais) para render
  compacto/sem legenda individual + legenda compartilhada no slide — só se necessário; default
  `None` = comportamento atual, preservando o caminho de chamada do dashboard byte-a-byte
  (precedente: emenda 2026-06-12 da DEC-005, que já permite parâmetros opcionais de RENDER em
  `censo_map.py`/`censo_report.py`, default `None` = comportamento idêntico ao atual).

## Fora de escopo
- Slides/páginas de Concorrentes (`_competitors_page`/`_classico_competitors_page`) e Big Numbers
  (`_big_numbers_page`) — permanecem como páginas próprias, inalteradas.
- Método `setor_censitario_intersecao_area_1p5km`, raio de 1,5 km, `analisar_ponto_censitario_setores`,
  score censitário, M1 (`score_priorizacao`, `hex_score_estrutural`, pesos, carteira, plano,
  artefatos oficiais) — todos INTOCADOS. Nada neste bloco recalcula ou altera esses artefatos.
- Relatório Municipal (`src/motor_expansao/dashboard/relatorio_municipal.py`) — outro
  template/módulo, fora de escopo.
- Qualquer dependência de rede NOVA (DEC-004/DEC-005/DEC-011 permanecem como estão; tiles/basemap
  seguem como hoje, sem mudança de provedor ou de caminho de fetch).
- Alteração da superfície pública da API (`src/motor_expansao/api/`) — se a assinatura pública de
  `gerar_pdf_relatorio_pontual_classico`/`_censitario` não mudar (só o corpo/orquestração
  interna), a API não precisa de alteração; confirmar isso no Planner antes do Builder tocar em
  `api/service.py` (não listado como arquivo alterável neste bloco).

## Arquivos que devem ser lidos
- src/motor_expansao/dashboard/censo_report.py (funções: `gerar_pdf_relatorio_pontual_classico`,
  `gerar_pdf_relatorio_pontual_censitario`, `_map_page`, `_classico_map_page`, `_draw_map`,
  `_classico_draw_map`, `_normalize_mapas`, `_normalize_mapas_by_key`, `MAP_LAYER_TITLES`,
  `_tema_bicolor`, `_draw_title_band`/`_classico_title_band`, `_draw_footer`, `_draw_watermark`)
- src/motor_expansao/dashboard/censo_map.py (função `render_mapas_censitarios_combinados`,
  dict de retorno `{"densidade","renda","score","concorrentes"}`, parâmetros opcionais já
  existentes `street_ceil`/`street_gain`/`street_cap`/`choropleth_alpha` como precedente de
  extensão)
- tests/unit/test_relatorio_pontual_censitario_export.py (constantes `PDF_SECTION_HEADERS`,
  `MAP_LAYER_TITLES`; helper `_count_layer_titles`; todos os testes que fazem assert de
  `b"/Count 7"`, de `PDF_SECTION_HEADERS`, de `_count_layer_titles(...) == 3`, e de
  `pdf_bytes.count(b"/Subtype /Image") >= 4`)
- docs/relatorio_pontual_censitario.md (contrato técnico da feature, se existir referência à
  estrutura de 7 páginas a atualizar)
- CLAUDE.md §4 (parágrafo "Motor/UI censitario" — descreve a estrutura de 7 páginas hoje vigente,
  que este bloco altera para 5; precisa de atualização textual pelo Builder/QA ao final, fora do
  escopo de código mas dentro do escopo de documentação do ciclo)
- tasks/backlog.md (bloco BLK-RELPON-01 completo, linhas 105–168, para as 5 perguntas do gate
  humano)

## Arquivos que podem ser alterados
- src/motor_expansao/dashboard/censo_report.py
- src/motor_expansao/dashboard/censo_map.py (só se o Planner/gate confirmar a necessidade do
  parâmetro opcional de render compacto/legenda compartilhada)
- tests/unit/test_relatorio_pontual_censitario_export.py
- docs/relatorio_pontual_censitario.md (se existir e descrever a estrutura de 7 páginas)
- tasks/backlog.md (bloco BLK-RELPON-01 já presente — pré-sujo, parte do ciclo)
- tasks/current_task.md, tasks/completed.md, context/handoff.md, context/handoff/ (governança
  do ciclo)
- CLAUDE.md §4 (atualização textual da contagem/estrutura de páginas, ao final do ciclo, se o
  Planner confirmar que é parte do fechamento)

## Critérios de aceite
- PDF do Relatório Pontual (variantes `classico` e `censitario`) passa de 7 para 5 páginas:
  Capa → Mapas de calor (Densidade+Renda+Score) → Concorrentes → Big Numbers → Realização.
- Os 3 choropleths aparecem no mesmo slide, lado a lado, legíveis, sem sobreposição entre si nem
  com faixa de título, rodapé ou marca d'água (verificável por teste de bounding boxes no
  montador).
- Todos os asserts `b"/Count 7"` atualizados para `b"/Count 5"` (7 ocorrências no arquivo de
  teste, ambas variantes).
- `PDF_SECTION_HEADERS` atualizado para refletir o novo header único do slide consolidado; todos
  os headers da tupla continuam batendo literalmente contra os bytes crus do PDF (compressão
  desativada).
- `_count_layer_titles`/contagem de imagens revisados e consistentes com a nova estrutura (decisão
  do Planner sobre se os 3 mini-títulos seguem existindo como texto ou se o critério de teste
  muda para outra verificação).
- `%PDF-1.4`, `set_compression(False)`, marca d'água em todas as páginas (agora 5, `>= 5`
  ocorrências onde hoje é `>= 7`), atribuição de tiles no rodapé, e o caminho de chamada do
  dashboard sem os parâmetros novos preservados byte-a-byte (se `censo_map.py` for tocado).
- Suíte `tests/unit/test_relatorio_pontual_censitario_export.py` 100% verde; ruff+mypy limpos;
  smoke import do dashboard ok.
- Revisão visual humana do PDF gerado aprovada no gate (layout, legendas, mini-títulos, tom
  bicolor do slide consolidado — ver "Pendências de decisão de produto" abaixo).
- Zero alteração em `score_priorizacao`, `hex_score_estrutural`, pesos, carteira, plano, ou
  qualquer artefato oficial do M1. Método de intersecção e raio de 1,5 km INTOCADOS.

## Pendências de decisão de produto (Planner PROPÕE, humano APROVA no gate — Block Orchestrator
não decide produto, só lista as perguntas)
1. **Consolidação vs. adição:** consolidar os 3 mapas num slide único (7→5 páginas, muda
   `/Count`) — leitura direta do pedido "num único slide" — **ou** manter os 3 slides individuais
   e ADICIONAR um slide-resumo (cresceria o `/Count` para 8)? O backlog já recomenda consolidar;
   o Planner deve propor formalmente e obter aprovação explícita antes do Builder.
2. **Layout da grade:** 3 mapas lado a lado em tira horizontal · 2 em cima + 1 embaixo · 1 linha
   de 3 com legenda compartilhada abaixo. Trade-off tamanho×legibilidade dentro da página
   960×540 (área de conteúdo é ainda menor, descontando banda de título e rodapé).
3. **Legendas:** manter a legenda embutida em cada um dos 3 mapas (mais denso/poluído, mas sem
   tocar `render_mapas_censitarios_combinados`) **ou** uma legenda única compartilhada para os 3
   (exige o parâmetro novo de render compacto em `censo_map.py`, com todos os cuidados de
   compatibilidade byte-a-byte do caminho do dashboard).
4. **Mini-títulos por mapa** (População / Renda / Score) — existem ou não como texto no novo
   slide, e em que posição (acima de cada mapa, faixa inferior, etc.). Decide diretamente o
   critério de teste (`_count_layer_titles`).
5. **Tom bicolor do slide consolidado:** hoje cada página de conteúdo alterna turquesa/magenta
   via `_tema_bicolor(ordinal)`; a fusão de 3 páginas (ordinais 2, 3, 4) em 1 página nova desloca
   os ordinais subsequentes (Concorrentes, Big Numbers, Realização) — o Planner precisa definir
   qual tom o slide consolidado usa e como isso reflui nos ordinais/tons das páginas seguintes
   (evitar que Concorrentes e Big Numbers troquem de tom sem intenção).

## Criticidade classificada
Alta — altera a ESTRUTURA de um template de PDF já aprovado em gate anterior (BLK-EST-02), muda
`/Count` de 7 para 5 e mexe em asserts de teste travados nas duas variantes (`classico` e
`censitario`). NÃO é Crítica: não toca `score_priorizacao`, pesos, `hex_score_estrutural`,
carteira, plano ou qualquer artefato oficial do M1 — é 100% READ-ONLY sobre o M1 (camada de
visualização/relatório, §5 guardrail permanente). É Alta (não Média/Baixa) porque é feature nova
de visualização/relatório que reestrutura um artefato de produto gated com testes travados e
exige revisão visual humana antes do merge.

## Esteira recomendada
Block Orchestrator → Planner → [aprovação humana — decisões de produto/visual listadas acima] →
Builder → QA. Tiering de modelo (já fixado em `tasks/current_task.md`): Planner=opus, Builder=opus,
QA=opus 4.8 (sempre).

## Riscos identificados
- Alterar `PDF_SECTION_HEADERS` sem atualizar TODOS os 7 asserts de `/Count 7` no mesmo commit
  quebra a suíte inteira do arquivo (os testes são interdependentes na mesma constante).
- Se o layout dos 3 mapas ficar pequeno demais (960×540 dividido em 3 colunas com margens),
  legibilidade pode cair abaixo do aceitável — risco central que motiva o gate humano visual antes
  do merge (não só suíte verde).
- Mudar o parâmetro opcional em `render_mapas_censitarios_combinados` (se necessário) sem manter
  `None` como default quebraria o caminho de chamada do dashboard (`pages.py`) e da API
  (`api/service.py`), que não fazem parte deste ciclo — risco de regressão silenciosa fora do
  escopo de teste deste bloco se o Builder não confirmar retrocompatibilidade byte-a-byte.
- Deslocamento dos ordinais de `_tema_bicolor` ao remover 2 páginas pode mudar sem intenção o tom
  das páginas de Concorrentes/Big Numbers/Realização — precisa de verificação explícita no QA
  visual, não só teste automatizado de cor.
- `_count_layer_titles` e a contagem de `/Subtype /Image >= 4` são âncoras de teste que dependem
  diretamente das decisões de produto (mini-títulos, pré-composição em 1 PNG vs. 3 PNGs
  separados) — se o Planner não fixar isso antes do Builder, o Builder pode escolher uma
  implementação que quebra a intenção original do teste sem quebrar a suíte (falso positivo).

## Guardrails ativos
- §2: tratar `config.py`, CLAUDE.md e `PRD.md` como fontes canônicas; toda mudança relevante entra
  com teste; nenhum PR sobe com CI quebrado.
- §5 (guardrail permanente): visualizações, análise radial e interações de mapa/relatório NÃO
  podem recalcular ou alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto
  prazo, plano de domínio ou artefatos oficiais do M1 sem aprovação explícita. Este bloco é
  estritamente READ-ONLY sobre o M1.
- DEC-004 e sua vigência: tiles online restritos ao caminho de geração do Relatório Pontual (e,
  por DEC-011, também ao Relatório Municipal) — este bloco NÃO estende nem modifica esse
  caminho de rede; nenhuma dependência de rede nova é introduzida.
- DEC-005 (emenda 2026-06-12): parâmetros opcionais de RENDER em `censo_map.py`/`censo_report.py`
  são permitidos como EXTENSÃO da interface (default `None` = comportamento idêntico ao atual);
  é o precedente direto que autoriza (se necessário) o parâmetro novo de render compacto/legenda
  compartilhada neste bloco, sem alterar `setor_censitario_intersecao_area_1p5km`, raio 1,5 km,
  score, M1 ou o caminho de chamada do dashboard sem os novos parâmetros.
- Marca d'água anti-PII (BLK-EST-01/BLK-EST-02) e `set_compression(False)` + `pdf_version="1.4"`
  (BLK-EST-02) permanecem obrigatórios em todas as páginas (agora 5).
