# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
BLK-RELPON-03 — Eliminar a barra cinza (letterbox) dos mapas do Relatório Municipal.

Os mapas gerados para o Relatório Municipal (PDF de 9 páginas — `/Count 9` confirmado nos
testes; note que o texto do bloco no backlog fala em "template de 8 páginas" mas o PDF real
atual do `relatorio_municipal.py` já materializa 9 — o Planner deve tratar isso como fato
observado no código, não recontar páginas) não preenchem inteiramente o painel arredondado
(`_rounded_panel`) onde são desenhados. Sobra uma barra cinza (na verdade é o fundo BRANCO do
próprio painel — `_BRANCO`/`fill` de `_rounded_panel` — visível como "barra" acima/abaixo do
mapa) no topo e na base do quadro, porque o PNG do mapa é gerado numa proporção mais larga
que o painel e `_draw_map` encaixa por **contain** (letterbox), não por **cover**.

## Objetivo
Os mapas do Relatório Municipal passam a preencher o painel sem a barra vazia (letterbox
top/base), casando a proporção do mapa ao painel, sem distorção grosseira nem sobreposição de
moldura/título/rodapé. Ajuste de RENDER, isolado em `relatorio_municipal.py`. READ-ONLY sobre
o M1.

## Causa-raiz confirmada no código (não é hipótese — linha e valor lidos)
- `_render_mapa_municipio` (relatorio_municipal.py:853) e `render_mapas_municipio`
  (relatorio_municipal.py:1158) geram o PNG do mapa com `width: int = 1000, height: int = 620`
  → aspect = 1000/620 = **1,6129**.
- `_draw_map` (relatorio_municipal.py:1296-1316): `scale = min(max_w/img_w, max_h/img_h)` —
  isto é **contain**: a imagem é encolhida até caber inteira dentro de `(max_w, max_h)`,
  centralizada com `x = x_anchor + (max_w-draw_w)/2`, `y = y_anchor + (max_h-draw_h)/2`. Como o
  aspect do PNG (1,613/1,474) é sempre MAIOR que o aspect do painel (1,421/1,474 — ver abaixo),
  o fator que domina é `max_w/img_w`, a imagem fica mais "baixa" que o painel, e sobra espaço
  vertical (top/base) — a "barra".
- `_draw_framed_map` (relatorio_municipal.py:1410-1421) é o wrapper usado nas 4 páginas de
  conteúdo com mapa; ele desenha `_rounded_panel` (fundo branco + borda colorida) e DEPOIS
  chama `_draw_map` por cima com os MESMOS `max_w/max_h` do painel (sem a margem `pad=10.0`
  do próprio painel arredondado, ou seja `_draw_map` já recebe o `max_w`/`max_h` "internos").
  Logo: a barra vazia = fundo branco do painel aparecendo nas faixas onde o mapa (contido) não
  chega.
- Chamadas reais de `_draw_framed_map` (todas com `x_anchor=34.0, y_anchor=100.0`):
  - linha 1528 (Página "Visão Geral do Município" / cobertura): `max_w=540.0, max_h=380.0` → aspect painel = 1,4211.
  - linha 1586 (Página "Resumo da Região"): `max_w=540.0, max_h=380.0` → aspect = 1,4211.
  - linha 1643 (Página "Score Censitário"): `max_w=560.0, max_h=380.0` → aspect = **1,4737** (o "outlier" dos 2 aspects citados no backlog).
  - linha 1693 (Página "Residual Fitness"): `max_w=540.0, max_h=380.0` → aspect = 1,4211.
  - linha 1755 (Página "Expansão de Domínio"): `max_w=540.0, max_h=380.0` → aspect = 1,4211.
  - Total: **5 chamadas de `_draw_framed_map` na base atual** (o handoff anterior do BO
    apontava "5 linhas" no CLAUDE.md-side prompt, todas confirmadas acima).
- `_draw_map` (função de baixo nível) tem defaults próprios (`max_w=600.0, max_h=430.0`, aspect
  1,3953) não usados por nenhuma chamada real hoje (todas passam `max_w/max_h` explícitos via
  `_draw_framed_map`) — o Planner deve decidir se atualiza os defaults também, por consistência,
  ou deixa como estão (nunca exercitados).
- Math do letterbox no caso mais comum (540×380, PNG 1000×620): `scale = min(540/1000, 380/620)
  = min(0.54, 0.6129) = 0.54` (a largura domina) → `draw_h = 620*0.54 = 334.8` → sobra
  `380 - 334.8 = 45.2` pontos verticais totais, ou seja **~22,6pt em cima e ~22,6pt embaixo**
  (confere com o valor citado no backlog/current_task, expresso lá em "px" mas na verdade são
  pontos PDF — fpdf2 trabalha em pt, não px; o Planner deve usar "pt" na nomenclatura do plano).
- No caso do painel 560×380: `scale = min(560/1000, 380/620) = min(0.56, 0.6129) = 0.56` →
  `draw_h = 620*0.56 = 347.2` → sobra `380-347.2 = 32.8` pt (~16,4pt em cima e embaixo) — MENOR
  que no caso 540×380, mas ainda existe. Confirma que os DOIS aspects (540×380 e 560×380)
  sofrem do mesmo problema em graus diferentes.

## Escopo permitido
- Ajustar a geração do PNG do mapa (`width`/`height` de `_render_mapa_municipio` e
  `render_mapas_municipio`, e/ou o cálculo de `map_box`/viewport/bbox interno) para que o
  aspect do PNG resultante se aproxime do aspect do painel de destino — ATENÇÃO: hoje um único
  PNG por camada é reusado pela MESMA chamada de página (não há um PNG por painel/aspect); se o
  Planner optar por esta via, decidir explicitamente se: (i) padroniza TODOS os painéis para um
  único aspect (eliminando a divergência 540×380 vs 560×380), ou (ii) gera PNGs diferentes por
  aspect de destino (mais mudança de assinatura/plumbing entre `render_mapas_municipio` e as
  páginas), ou (iii) mantém 1 PNG e resolve só no `_draw_map` (ver próxima opção).
- Alterar `_draw_map` para preencher o painel por **cover** (escala pelo `max`, não pelo `min`,
  recortando o excedente com clipping) em vez de **contain** — elimina a barra sem tocar a
  geração do PNG nem a assinatura de `render_mapas_municipio`; introduz recorte lateral do mapa
  (perde-se conteúdo nas bordas esquerda/direita, já que o PNG é mais largo que o painel).
- Pintar o fundo do painel (`_rounded_panel`/área não coberta pelo mapa dentro de
  `_draw_framed_map`) com uma cor derivada do próprio mapa (ex.: cor média dos pixels de borda,
  ou um preenchimento sólido não-branco) em vez de eliminar o letterbox — mitiga o efeito visual
  da "barra" sem mudar proporção/recorte; tecnicamente mais simples, mas é só cosmético (a barra
  continua existindo, só fica menos contrastante).
- Combinações das três acima (ex.: reduzir o aspect do PNG parcialmente + cover com recorte leve
  residual) são permitidas se o Planner justificar o tradeoff.
- Novo(s) parâmetro(s) opcional(is) de render (ex.: um modo `fit: Literal["contain","cover"]` em
  `_draw_map`/`_draw_framed_map`, ou `width`/`height` diferentes por camada) seguindo o
  precedente da emenda DEC-005 (2026-06-12): parâmetro NOVO e OPCIONAL, default = comportamento
  atual seria uma opção conservadora, mas como o objetivo do bloco É MUDAR o comportamento
  padrão (eliminar a barra sempre), o Planner deve decidir se o novo comportamento passa a ser o
  default do caminho de produção (provavelmente sim, já que não há caminho legado a preservar
  aqui — diferente da DEC-005 original, que estendia `censo_map.py`/`censo_report.py` mantendo o
  dashboard intocado). Registrar essa distinção explicitamente no plano.
- Testes novos/ajustados em `tests/unit/test_relatorio_municipal.py` que fixem a AUSÊNCIA de
  letterbox (ex.: medir a área do painel efetivamente coberta pelo mapa desenhado, ou testar a
  função de encaixe isoladamente com dimensões sintéticas) — hoje NENHUM teste existente trava
  ou mede o encaixe/aspect do mapa dentro do painel (confirmado por leitura completa de
  `test_relatorio_municipal.py`); os testes atuais só verificam presença de PNG
  (`startswith(b"\x89PNG")`, `len(png) > 1000`), contagem de páginas (`/Count 9`), headers de
  seção, ausência de PII e byte-identity do Relatório Pontual (não afetado por este bloco, pois
  vive em `censo_map.py`/`censo_report.py`, módulos disjuntos). Logo, há liberdade total para
  escolher a abordagem sem quebrar trava existente — mas o Planner DEVE especificar o novo teste
  de trava como critério de aceite (ver abaixo), senão o bloco fecha sem cobertura do próprio bug
  que resolve.

## Fora de escopo
- Gate do SAM / `flag_sam` (DEC-006/DEC-007) — não tocar `calcular_colunas_mercado.py` nem
  qualquer lógica de elegibilidade.
- `score_priorizacao`, `hex_score_estrutural`, pesos, carteira, plano curto prazo, plano de
  domínio, artefatos oficiais do M1 — nenhum recálculo, nenhuma leitura que os altere.
- Relatório Pontual Censitário (`censo_map.py`, `censo_point.py`, `censo_report.py`) — módulos
  disjuntos, intocados; o teste `test_coexistencia_relatorio_pontual_intocado` já trava
  byte-identity e deve continuar passando sem qualquer edição nesses arquivos.
- Método de intersecção geométrica setor×círculo (`setor_censitario_intersecao_area_1p5km`) e
  raio de 1,5 km — não pertencem a este módulo e não devem ser tocados.
- Estrutura de páginas (contagem, ordem, headers `PDF_SECTION_HEADERS`), marca d'água,
  `set_compression(False)`, moldura Ultra Clean (`_rounded_panel`, ciclo de cores
  `_ciclo_cor`/`_tema_bicolor`), título/rodapé — preservar tudo; a mudança é estritamente no
  encaixe do PNG dentro do painel já existente.
- Dependência de rede nova — DEC-011 (tiles online via `contextily`) permanece como está; este
  bloco não introduz nem remove chamadas de rede.
- Qualquer outro relatório/módulo fora de `relatorio_municipal.py` e seus testes.

## Arquivos que devem ser lidos
- `CLAUDE.md` (completo — §2, §4 Relatório Municipal, §5 guardrail READ-ONLY M1, DEC-011,
  DEC-005 emenda 2026-06-12)
- `tasks/current_task.md`
- `tasks/backlog.md` (bloco "Relatório Municipal — mapas com barra cinza" / `BLK-RELPON-03`,
  linhas ~112-155)
- `src/motor_expansao/dashboard/relatorio_municipal.py` (arquivo completo recomendado; mínimo:
  `_render_mapa_municipio` ~853-1157, `render_mapas_municipio` ~1158-1230ish, `_draw_map`
  ~1296-1316, `_draw_framed_map` ~1410-1421, `_rounded_panel` ~1371-1396, e as 5 chamadas de
  `_draw_framed_map` nas páginas ~1528, ~1586, ~1643, ~1693, ~1755, incluindo o contexto de cada
  página — `pdf.add_page()` até o próximo `pdf.add_page()` — para não sobrepor título/painel
  lateral)
- `tests/unit/test_relatorio_municipal.py` (completo — já lido pelo BO; nenhuma trava de
  aspect/encaixe hoje)
- `docs/relatorio_municipal_template.md` (referência de layout/estética esperada pelo template
  original, citado no DEC-011 como fonte da exigência visual)

## Arquivos que podem ser alterados
- `src/motor_expansao/dashboard/relatorio_municipal.py`
- `tests/unit/test_relatorio_municipal.py` (e qualquer teste unitário impactado no mesmo
  diretório, se novos helpers forem extraídos)
- `tasks/current_task.md`, `tasks/backlog.md` (bloco BLK-RELPON-03), `tasks/completed.md`
  (passos de fechamento do ciclo, não do Planner/Builder)
- `context/handoff.md`, `context/handoff/` (handoffs versionados)

## Critérios de aceite
- Nos 5 pontos de chamada reais (`_draw_framed_map` nas linhas ~1528/1586/1643/1693/1755), o
  mapa cobre o painel inteiro (ou a diferença residual é ínfima/imperceptível — o Planner deve
  definir um limiar numérico verificável, ex. "sobra vertical/horizontal ≤ N pt", e um teste que
  meça isso, seja via a função de encaixe testada isoladamente com dimensões sintéticas, seja via
  inspeção do PNG final desenhado).
- Nenhuma distorção grosseira do mapa perceptível (se a abordagem escolhida distorcer o aspect —
  ex.: opção (a) squeeze sem recorte — o Planner deve justificar o grau aceitável e como isso é
  verificado/aprovado no gate humano).
- Nenhuma sobreposição do mapa sobre título (`_draw_title_band`), painel lateral
  (`_info_panel`/legendas), rodapé (`_draw_footer`) ou marca d'água (`_draw_watermark`) nas 5
  páginas afetadas.
- Moldura Ultra Clean (`_rounded_panel` com borda colorida ciclando
  turquesa/magenta/laranja via `_ciclo_cor`/`_tema_bicolor`) preservada.
- `/Count 9`, `PDF_SECTION_HEADERS`, `set_compression(False)`, `pdf_version="1.4"`, marca
  d'água anti-PII e o carimbo de versão no rodapé (`BLK-RELMUN-01`, atribuição
  "OpenStreetMap"/"CARTO") continuam presentes nos bytes do PDF — sem regressão dos testes
  existentes.
- `test_coexistencia_relatorio_pontual_intocado` continua passando (byte-identity do Relatório
  Pontual preservada — módulos disjuntos, não deveria ser afetado, mas é o teste que PROVA
  isolamento).
- Pelo menos 1 teste NOVO que trave a ausência (ou o limiar aceito) de letterbox — este bloco
  NASCEU de um defeito visual sem cobertura; fechar sem essa trava reabre a regressão no futuro.
- Suíte completa (`pytest -q` ou `-n auto`) verde; `ruff` + `mypy` limpos no escopo do arquivo
  tocado.
- Revisão visual humana do PDF gerado (olho humano no gate — ver Esteira) aprovada antes do
  Builder implementar em definitivo (a esteira do backlog exige `[REVISÃO HUMANA —
  produto/visual]` entre Planner e Builder, além da aprovação padrão de bloco Alta).

## Criticidade classificada
**Alta.** Confirmado — não envolve `score_priorizacao`, `hex_score_estrutural`, pesos, carteira,
plano curto prazo, plano de domínio nem qualquer artefato oficial do M1 (guardrail de
"Crítica obrigatória" do prompt do BO não se aplica: nenhum termo-gatilho tocado). É mudança de
RENDER num template de PDF já gated por decisão registrada (DEC-011), o que por si justifica
Alta (não Média) — decisão visual/de produto (como encaixar o mapa) precisa de revisão humana
antes do Builder implementar em definitivo, e o próprio bloco no backlog já fixa
`Autonomia: manual (NÃO loop-safe)`. READ-ONLY sobre o M1 mantido.

## Esteira recomendada
Block Orchestrator → Planner → **[REVISÃO HUMANA — produto/visual, decisão sobre a abordagem de
encaixe e o grau de recorte/distorção aceitável]** → Builder → QA.

(Tiering de modelo, já fixado em `tasks/current_task.md`: Planner=opus, Builder=opus, QA=opus
sempre — nível Alta.)

## Riscos identificados
- **Ambiguidade de abordagem sem decisão de produto:** as 3 abordagens candidatas (regenerar PNG
  no aspect do painel / cover com recorte / cor de fundo) têm tradeoffs de natureza distinta
  (perda de área visível do mapa nas bordas vs. distorção de forma vs. solução puramente
  cosmética que não elimina o "problema" tecnicamente, só o disfarça). O Planner deve PROPOR,
  não decidir sozinho — o gate humano intermediário existe exatamente para isso.
- **Dois aspects de painel divergentes (540×380 e 560×380):** se a solução escolhida for
  "regenerar o PNG no aspect do painel", surge a pergunta de qual aspect usar como alvo único
  (ou se gerar 2 PNGs por camada/página). Ignorar essa divergência e resolver só para um dos
  aspects deixaria a página "Score Censitário" (linha 1643, `max_w=560.0`) com um resíduo de
  letterbox diferente das outras 4 — o Planner deve tratar EXPLICITAMENTE os dois casos.
  Alternativa (Planner) para o Builder: padronizar por decisão humana no gate ambos os painéis
  no mesmo `max_w/max_h` (eliminando a divergência na origem) — mas isso é mudança de layout, não
  só de encaixe; anotar como opção adicional se o Planner achar pertinente propor.
- **Cover com recorte pode cortar conteúdo relevante do mapa** (hexágonos de borda, pins de
  concorrentes/Ultra próximos da margem) se o recorte lateral for grande — o Planner deve
  estimar/quantificar o recorte esperado (largura perdida em % do PNG) para a decisão humana
  julgar se é aceitável.
- **Regenerar o PNG no aspect do painel muda o "zoom"/enquadramento do mapa** (o viewport de foco
  `focus_bounds_mercator` já é compartilhado entre as 4 camadas de foco — resumo/score/
  residual/dominio — para ficarem comparáveis; mudar dimensões de captura pode exigir recalcular
  esse bbox compartilhado com cuidado para não descompassar as camadas entre si).
- **`_draw_map` tem defaults (`max_w=600.0, max_h=430.0`) não exercitados por nenhuma chamada
  real hoje** — se o Planner atualizar só as chamadas explícitas e esquecer os defaults, fica
  uma inconsistência dormente (sem teste que a cubra hoje) para o futuro.
- **Ausência de cobertura de teste hoje para o próprio bug:** sem um teste novo de trava, o
  Builder pode "resolver visualmente" mas a suíte fecha verde mesmo se a barra persistir
  parcialmente — reforça o critério de aceite de teste novo obrigatório.

## Guardrails ativos
- §5 (CLAUDE.md) — guardrail permanente: "visualizações, análise radial e interações de mapa não
  podem recalcular ou alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto
  prazo, plano domínio ou artefatos oficiais do M1 sem aprovação explícita." Este bloco é
  estritamente visualização/render de um relatório PDF — nenhuma leitura/escrita de artefato M1.
- §2 (CLAUDE.md) — "não criar dependência de API ao vivo no dashboard de produção": não se aplica
  a mudanças novas aqui (DEC-011 já cobre os tiles existentes do Relatório Municipal; este bloco
  não adiciona nem remove chamadas de rede).
- DEC-011 (fundo de ruas por tiles online no Relatório Municipal): tiles/cache/fallback offline
  inalterados; este bloco não toca `_fetch_basemap_municipio` nem a lógica de basemap — só o
  encaixe do PNG resultante (com ou sem basemap) dentro do painel.
- DEC-005 emenda 2026-06-12 (precedente de parâmetro opcional de render, default=comportamento
  atual): citada no backlog como padrão a seguir "quando aplicável" — mas, diferente do caso
  original (API estendendo `censo_map.py` mantendo o dashboard intocado por trás de um default
  `None`), aqui não há dois consumidores a proteger (só existe o caminho de produção do
  Relatório Municipal); o Planner deve avaliar se faz sentido manter um "modo antigo" opcional
  ou apenas corrigir o comportamento padrão, e justificar a escolha.
- Guardrail do BO (prompt canônico): não implementar, não expandir escopo, não resolver múltiplos
  blocos — este handoff delimita SÓ o BLK-RELPON-03.
