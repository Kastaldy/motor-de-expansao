# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
BLK-RELPON-09 — Indicador de concorrente = logo quadrada nos PDFs (Relatório Pontual Censitário +
Relatório Municipal). Troca o marcador visual de concorrente/Ultra: sai o balão teardrop 128x128 com
a logo mascarada em círculo (~17-14 px efetivos de logo visível); entra a própria logo em formato
QUADRADO (~30 px), via função nova, sem tocar a função/atlas que hoje serve o mapa interativo pydeck.

## Objetivo
Criar `competitors._render_square_logo_tile(key, size)` (logo quadrada, sem balão, sem máscara
circular, borda branca ~2 px + sombra leve) e consumi-la só em `censo_map._paste_logo_pin` e
`relatorio_municipal._draw_pins`/`_draw_rede_logo`, mantendo `_render_pin_tile` e `build_icon_atlas`
intocados.

## Escopo permitido
- Adicionar `_render_square_logo_tile(key, size)` NOVA em
  `src/motor_expansao/dashboard/competitors.py` (perto de `_render_pin_tile`, ~linha 504-568).
  Pode reusar helpers existentes do módulo (`_extract_embedded_logo_png`, `_ICON_CACHE`,
  `ULTRA_BRAND`/`COMPETITOR_BRANDS`) — NÃO duplicar a lógica de extração de logo.
- Trocar `censo_map._paste_logo_pin` (`censo_map.py:327-343`) para chamar a função nova em vez de
  `_render_pin_tile`; ajustar âncora conforme a decisão do gate visual sobre S2b (default
  recomendado: centro do quadrado + ponto fino de 2 px no local exato).
- Trocar `relatorio_municipal._draw_pins` (`relatorio_municipal.py:1141-1176`, hoje 34 px) para
  usar a função nova.
- Simplificar `relatorio_municipal._draw_rede_logo` (`relatorio_municipal.py:1478-1494`) para
  reusar a função nova em vez do `tile.crop((37,20,91,74))` acoplado à geometria do balão antigo.
- Ajustar o tamanho-padrão do marcador para ~30 px nos dois PDFs (Pontual e Municipal), respeitando
  a decisão do gate sobre S2a (px do PNG fonte vs pt do PDF).
- Reescrever `tests/unit/test_relatorio_pontual_censitario_mapa.py:198-206` (teste de pixels
  avermelhados do pin Ultra) para a forma nova — o vermelho de hoje vem do balão `#C8001E`
  (`ULTRA_BRAND["bg"]`), não da logo; com o quadrado sem balão o teste de detecção precisa mudar de
  critério (ex.: presença de tile quadrado colado nas coordenadas esperadas, ou cor de borda/sombra),
  nunca ser removido ou silenciado.
- Ajustar/estender testes em `tests/unit/test_relatorio_municipal.py` e, se estritamente necessário,
  `tests/unit/test_ultra_pins.py` — só para cobrir a função NOVA; os testes que hoje validam
  `_render_pin_tile`/`build_icon_atlas` (geometria 128x128, `anchorY=122`) devem continuar passando
  SEM alteração de asserção, porque essas funções não mudam.
- Fechar as duas sub-decisões abertas (S2a, S2b) no gate visual do Vini antes ou durante a revisão
  do PDF gerado; a recomendação de cada uma (documentada abaixo) é o default caso o Planner precise
  avançar sem esperar o gate.

## Fora de escopo
- Alterar `competitors._render_pin_tile` (`competitors.py:504-568`) de qualquer forma.
- Alterar `competitors.build_icon_atlas` (`competitors.py:571-618`) ou o mapa interativo pydeck.
- BLK-RELPON-10 (slide novo "Socioeconomia + Residual Fitness") — bloco separado, não iniciar.
- BLK-RELPON-11 (página de satélite Esri World Imagery) — bloco separado, bloqueado por DEC-018,
  não iniciar.
- Qualquer recálculo de score, faixas, `flag_sam`, carteira, plano ou artefato oficial do M1.
- Qualquer mudança em `data/`, pipelines, `config.py` ou parâmetros canônicos do §3 do CLAUDE.md.
- Edição de `tasks/backlog.md` / `tasks/completed.md` (housekeeping fica para o fechamento do ciclo,
  não para este handoff).

## Arquivos que devem ser lidos
- `src/motor_expansao/dashboard/competitors.py` (completo; focar `_render_pin_tile` linhas 504-568,
  `build_icon_atlas` 571-618, `_extract_embedded_logo_png` 486-501, `ULTRA_BRAND`/`COMPETITOR_BRANDS`
  ~linha 388, `_ATLAS_CIRCLE_CX/CY/R`, `ATLAS_TILE`, `_ATLAS_ANCHOR_Y`)
- `src/motor_expansao/dashboard/censo_map.py` (focar `_paste_logo_pin` linhas 327-343 e o call-site
  em `render_mapas_censitarios_combinados`/`_render_camada`)
- `src/motor_expansao/dashboard/relatorio_municipal.py` (focar `_draw_pins` linhas 1141-1176 e
  `_draw_rede_logo` linhas 1478-1494)
- `tests/unit/test_ultra_pins.py` (focar linhas 260-312, testes de `build_icon_atlas` que dependem
  de `_render_pin_tile` inalterado: `width==128`, `height==128`, `anchorY==122`)
- `tests/unit/test_relatorio_pontual_censitario_mapa.py` (focar linhas 180-207, teste de pixels
  avermelhados a reescrever)
- `tests/unit/test_relatorio_municipal.py` (varredura geral por testes que tocam pins/logos de
  concorrente — busca atual não encontrou teste de pixel equivalente lá, mas confirmar)
- `tasks/backlog.md` linhas 103-185 (contexto completo do pedido + decisões D1-D4/S1/S2 + a íntegra
  do bloco BLK-RELPON-09)
- `CLAUDE.md` §5 (guardrail READ-ONLY sobre o M1) e regra de acentuação no §2

## Arquivos que podem ser alterados
- `src/motor_expansao/dashboard/competitors.py`
- `src/motor_expansao/dashboard/censo_map.py`
- `src/motor_expansao/dashboard/relatorio_municipal.py`
- `tests/unit/test_relatorio_pontual_censitario_mapa.py`
- `tests/unit/test_relatorio_municipal.py`
- `tests/unit/test_ultra_pins.py` (só se necessário para cobrir a função nova — não para alterar as
  asserções de `_render_pin_tile`/`build_icon_atlas`)

## Critérios de aceite
- `competitors._render_pin_tile` e `competitors.build_icon_atlas` permanecem byte-a-byte idênticos
  ao estado atual (nenhuma linha alterada); `test_ultra_pins.py` (testes de atlas, `width/height=128`,
  `anchorY=122`) segue verde sem alteração de asserção.
- Função nova `competitors._render_square_logo_tile(key, size)` existe, produz um tile RGBA quadrado
  (sem balão, sem máscara circular) com a logo real quando disponível em `_ICON_CACHE` e fallback de
  sigla quando não.
- `censo_map._paste_logo_pin` e `relatorio_municipal._draw_pins`/`_draw_rede_logo` passam a chamar a
  função nova; o marcador de concorrente/Ultra nos dois PDFs vira quadrado (~30 px) sem balão.
- `tests/unit/test_relatorio_pontual_censitario_mapa.py:198-206` é REESCRITO (não removido, não
  silenciado) para validar a forma nova — deve continuar provando de forma determinística que o pin
  Ultra aparece no mapa gerado.
- Nenhuma escrita/alteração em `score_priorizacao`, `hex_score_estrutural`, scores censitários,
  `flag_sam`, carteira, plano ou artefatos oficiais do M1 (§5 CLAUDE.md).
- Texto voltado ao usuário (labels/legendas/`help=`) com acentuação correta; identificadores
  (`key=`, nomes de coluna, slugs) nunca acentuados (regra de acentuação, CLAUDE.md §2).
- Suite de testes impactada (Builder) e suite FULL (QA) verdes; ruff/mypy limpos.
- Duas sub-decisões (S2a, S2b) explicitamente resolvidas e registradas no handoff do
  Planner/Builder, com a decisão tomada e o motivo — mesmo que sigam a recomendação por default.

## Criticidade classificada
Média — conforme já fixado em `tasks/backlog.md` (linha 153) e `tasks/current_task.md`: display
local nos dois PDFs, sem rede, sem dado novo, sem DEC, READ-ONLY sobre o M1. O tiering de modelo do
ciclo já eleva Planner/Builder para Opus (override +1) por causa da fronteira delicada com
`_render_pin_tile` (superfície compartilhada com o atlas pydeck e a paridade de BLK-WEB-02/07) e da
reescrita do teste de pixel — isso é override de modelo, não reclassificação de criticidade.

## Esteira recomendada
Block Orchestrator → Planner → Builder → QA → [GATE VISUAL do Vini — PDF gerado]. Autonomia
`manual` (critério de aceite é visual: legibilidade e colisão de marcadores sobre choropleth,
que a suíte automatizada não captura sozinha) — não marcar `loop-safe`.

## Riscos identificados
- Alterar `_render_pin_tile` por engano (mesmo que mínimo) quebra silenciosamente `build_icon_atlas`
  e a paridade futura de BLK-WEB-02/BLK-WEB-07 — é o risco central do bloco; a função precisa nascer
  100% separada.
- `test_relatorio_pontual_censitario_mapa.py:198-206` corre risco de ser "corrigido" reduzindo a
  força do teste (ex.: só checar que o PNG não é vazio) em vez de continuar provando presença real do
  pin Ultra — precisa de critério novo igualmente forte (não avermelhado, mas igualmente
  determinístico).
- `relatorio_municipal._draw_rede_logo` faz `tile.crop((37,20,91,74))` acoplado à geometria do balão
  128x128; ao trocar para a função nova, garantir que nenhum código residual continue recortando um
  tile que já não tem essa geometria.
- Tamanho pequeno (~30 px) com borda branca + sombra pode ficar ilegível sobre choropleth translúcido
  em zoom apertado — é exatamente o critério do gate visual manual; Builder deve gerar um PDF de
  amostra para conferência antes do QA, não só confiar na suíte automatizada.
- Ambiguidade S2a (px do PNG-fonte vs pt do PDF) e S2b (âncora centro+ponto fino vs base do quadrado)
  seguem abertas; se o Planner não registrar explicitamente qual foi adotada, o Builder pode divergir
  do que o Vini vai avaliar no gate.

## Guardrails ativos
- §5 CLAUDE.md (READ-ONLY sobre o M1, permanente): visualizações, relatórios e interações de mapa não
  podem recalcular ou alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto
  prazo, plano de domínio ou artefatos oficiais do M1 sem aprovação explícita. Este bloco é 100%
  display — nenhuma dessas peças é tocada.
- `_render_pin_tile` NÃO PODE ser alterado — é requisito, não recomendação (alimenta o atlas 128px/
  `anchorY=122` do pydeck e a paridade dos blocos pendentes BLK-WEB-02/BLK-WEB-07).
- Regra de acentuação (CLAUDE.md §2): texto voltado ao usuário acentuado corretamente; identificadores
  (`key=`, `session_state`, seletores CSS, valores brutos de enum, nomes de coluna, slugs/nomes de
  arquivo) NUNCA acentuados. No PDF (`fpdf2`/Helvetica/latin-1 via `_ascii()`), caracteres fora de
  latin-1 (travessão, bullet, seta, reticências, aspas curvas, ©) viram "?" silenciosamente — usar
  pontuação ASCII.
- Toda mudança relevante entra com teste; nenhum PR sobe com CI quebrado (§2 CLAUDE.md).
- `test_ultra_pins.py` linhas ~260-312 (faixa de testes de atlas dependentes de `_render_pin_tile`/
  `build_icon_atlas` inalterados: `width==128`, `height==128`, `anchorY==122`) só continua verde se
  essas duas funções não mudarem.
