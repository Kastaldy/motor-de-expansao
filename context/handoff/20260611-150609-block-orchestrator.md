# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
BLK-EST-02 — Melhorar visual e template dos estudos automatizados

Evolução visual/template do Relatório Pontual Censitário (PDF 7 páginas, fpdf2, 16:9), sem alterar
conteúdo, scores, raio ou método de interseção. É continuação direta de BLK-CENSO-02 (template
estabelecido) e BLK-CENSO-03 (mapas refinados). As decisões visuais precisam de gate humano de
Felipe antes de qualquer implementação.

## Objetivo
Refinar o template visual do PDF do Relatório Pontual Censitário para um nível mais profissional,
com decisões visuais aprovadas por Felipe em gate, mantendo integralmente as 7 páginas, o conteúdo
Big Numbers READ-ONLY e todos os contratos de score/M1.

## Escopo permitido
- `src/motor_expansao/dashboard/censo_report.py` — template fpdf2: paleta, tipografia, layout de
  páginas, espaçamentos, faixas de acento, grid Big Numbers, página de Realização
- `src/motor_expansao/dashboard/censo_map.py` — composição dos 4 mapas PNG (knobs visuais:
  cores, bordas, legendas, escala, títulos dos mapas)
- Assets de branding em `data/ultra/` (gitignored): `relatorio_capa_bg.png`,
  `relatorio_conteudo_bg.png`, `logo_ultra.png` — substituição/ajuste, nunca versionados
- Testes correspondentes em `tests/unit/test_relatorio_pontual_censitario_export.py` e
  `tests/unit/test_relatorio_pontual_censitario_mapa.py`
- Docs: `docs/relatorio_pontual_censitario.md` e `CLAUDE.md §4` se necessário

## Fora de escopo
- Qualquer recálculo ou escrita de score: `score_priorizacao`, `hex_score_estrutural`,
  `score_setor_2022_calibrado`, residual, SAM, carteira, plano, artefatos oficiais do M1
- Método de interseção `setor_censitario_intersecao_area_1p5km` e raio 1.5 km (INTOCADOS)
- Estrutura das 7 páginas: ordem (Capa→Pop→Renda→Score→Concorrentes→Big Numbers→Realização)
  e conteúdo das páginas são CONTRATOS — não remover nem reordenar páginas sem aprovação explícita
- Grid 4×2 de 8 métricas do Big Numbers (READ-ONLY): nenhuma métrica alterada, removida ou
  adicionada sem aprovação; formatação pode mudar mas campos não
- Dependência de API ao vivo no dashboard interativo (DEC-004: tiles só na geração do relatório)
- Anti-PII §4: `.pptx`/PDF nunca versionados; `image24.png` NUNCA embutido; compressão de stream OFF
- `pages.py` — a UI do Streamlit que chama o relatório (fora do escopo visual do PDF/mapas)
- `censo_point.py` — motor de interseção (intocado)

## Arquivos que devem ser lidos
- `src/motor_expansao/dashboard/censo_report.py` — estado atual do template (já lido pelo BO)
- `src/motor_expansao/dashboard/censo_map.py` — estado atual dos 4 mapas (já lido pelo BO)
- `docs/relatorio_pontual_censitario.md` §6/§7/§8 — contrato técnico
- `src/motor_expansao/dashboard/constants.py` — paletas `DENSIDADE_POP_BANDS`,
  `RENDA_PER_CAPITA_BANDS`, `RESIDUAL_SCORE_BANDS` (usadas nos mapas e no Big Numbers)
- `tasks/completed.md` (BLK-CENSO-02 e BLK-CENSO-03) — histórico de decisões visuais já tomadas
- `CLAUDE.md §4` — estado atual do relatório e DEC-004

## Arquivos que podem ser alterados
- `src/motor_expansao/dashboard/censo_report.py`
- `src/motor_expansao/dashboard/censo_map.py`
- `tests/unit/test_relatorio_pontual_censitario_export.py`
- `tests/unit/test_relatorio_pontual_censitario_mapa.py`
- `docs/relatorio_pontual_censitario.md` (atualização de contrato após decisões aprovadas)
- `CLAUDE.md §4` (registro de mudanças visuais relevantes)

## Critérios de aceite
- Visual aprovado por Felipe em gate humano (obrigatório antes do Builder)
- 7 páginas e Big Numbers READ-ONLY preservados (estrutura de `PDF_SECTION_HEADERS` intacta,
  `gerar_pdf_relatorio_pontual_censitario` retorna PDF com `/Count 7`)
- Suite verde: `pytest -n auto` sem falhas; ruff+mypy limpos
- READ-ONLY M1 confirmado: zero mudança em pipelines/scoring/config/artefatos oficiais
- Geração offline-safe: `basemap=False` funciona sem internet (fallback gracioso preservado)
- Anti-PII: bytes crus do PDF sem PII de pessoas; `image24` não referenciada
- Deploy registrado (rebuild de imagem + redeploy por digest na VPS após aprovação, passo de OPS
  gated pelo guardrail §6 — fora deste ciclo de código)

## Criticidade classificada
Média

## Esteira recomendada
Block Orchestrator (concluído) → Planner → [REVISÃO HUMANA das decisões visuais — Felipe]
→ Builder → QA

## Decisões visuais que EXIGEM gate humano (para o Planner enumerar com opções concretas)

O Planner deve apresentar cada decisão abaixo com 2–3 opções concretas (mockup textual ou
amostra de valores de knob) para Felipe escolher. O Builder só executa após aprovação do gate.

### D1 — Tipografia e hierarquia de títulos (censo_report.py)
Estado atual (`_draw_title_band`): Helvetica Bold 20 pt na faixa de título (linha 224–227).
Capa: Helvetica Bold 26 pt para título principal (linha 308), Helvetica 13 pt para subtítulo
(linhas 312–318). Realização: Bold 30 pt + Bold 16 pt + 12 pt (linhas 494–513).
Decisões abertas:
- Tamanho do título principal da Capa (26 pt atual — grande o suficiente? muito pequeno?).
- Tamanho da faixa de título nas páginas de conteúdo (20 pt atual).
- Tipografia da página de Realização (30 pt/16 pt/12 pt — muito espaçada?).
- Usar fonte diferente de Helvetica (fpdf2 suporta TTF via `add_font`) — acrescentaria dep de asset.

### D2 — Paleta de acento e cores de texto (censo_report.py)
Estado atual (linhas 58–63):
  `ULTRA_TURQUESA = (0, 167, 157)` — faixas de título e acento dos Big Numbers (cards ímpares)
  `ULTRA_MAGENTA = (194, 60, 142)` — acento dos Big Numbers (cards pares) e título da lista
    de redes na página de Concorrentes
  `_CINZA_TEXTO = (60, 60, 60)` — texto corrido
  `_BRANCO = (255, 255, 255)` e `_BRANCO_GELO = (248, 248, 248)` — fundo de conteúdo
Decisões abertas:
- Proporção turquesa×magenta nos cards do Big Numbers (alternância atual: 1×1).
- Cor do texto de rótulo dos cards (cinza 60 atual — mais escuro/claro?).
- Cor do valor grande no card (acento atual — legível sobre fundo branco?).
- Cor de fundo do card branco (`_BRANCO`) vs branco-gelo — diferenciação do fundo da página.

### D3 — Layout e dimensionamento dos cards de Big Numbers (censo_report.py)
Estado atual (`_big_numbers_page`, linhas 342–413):
  grid 4×2, `card_w ≈ 213 pt`, `card_h = 150 pt`, `gap = 14 pt`, `margin_x = 36 pt`,
  `top = 70 pt`. Barra de acento de 8 pt no topo de cada card. Rótulo Helvetica 11 pt,
  valor Helvetica Bold 24 pt.
Decisões abertas:
- Altura dos cards (150 pt — suficiente para o valor de 24 pt + rótulo de 11 pt + margem?).
- Espessura da barra de acento (8 pt atual).
- Tamanho do valor (24 pt atual — destaque adequado?).
- Espaçamento `gap` entre cards (14 pt) e margem lateral (36 pt).
- Sombra/borda nos cards (nenhuma atualmente).

### D4 — Layout da página de Concorrentes (censo_report.py)
Estado atual (`_competitors_page`, linhas 432–480):
  Mapa à esquerda (max 560×430 pt), lista de redes à direita (a partir de x=620 pt, largura ≈304 pt).
  Título "Redes no raio de 1.5 km" em Magenta Bold 14 pt. Cada linha de rede em Cinza 10 pt.
  Limite de 10 entradas (`points.head(10)`).
Decisões abertas:
- Proporção mapa×lista (60/40 atual — mais espaço para o mapa ou para a lista?).
- Limite de entradas na lista (10 atual — suficiente?).
- Adicionar ícone/bullet colorido por tipo (Ultra vs concorrente) na lista.
- Mostrar contagem total de concorrentes no cabeçalho da lista quando houver mais de 10.

### D5 — Página de Realização/Crédito (censo_report.py)
Estado atual (`_credit_page`, linhas 483–527):
  Fundo turquesa sólido (não usa asset de capa), texto branco centralizado.
  Linha 1: "Realização" Bold 30 pt (y=150 pt).
  Linha 2: crédito Ultra Bold 16 pt (y=210 pt).
  Linha 3: descrição do método Regular 12 pt (y=260 pt, largura 640 pt, align=C).
  Linha 4: nota READ-ONLY Regular 12 pt (y=320 pt).
  Linha 5: atribuição de tiles Regular 9 pt (y=_PAGE_H-40, centralizado).
Decisões abertas:
- Usar o asset de capa (`relatorio_capa_bg.png`) em vez de turquesa sólido para mais consistência.
- Simplificar o texto de método (muito técnico para uma página de encerramento?).
- Posicionamento vertical do bloco de texto (hoje começa em y=150 pt, ~28% da página).
- Adicionar logo Ultra na página de Realização.

### D6 — Títulos internos dos mapas PNG (censo_map.py)
Estado atual (`_render_camada`, linha 479–481):
  Título grande: `_font(20)` no canto superior-esquerdo (x=28, y=22).
  Subtítulo: `_font(12)` com coordenada+raio+n_setores (x=28, y=52), cor cinza-slate `(71,85,105)`.
  Títulos atuais passados pela orquestradora (linhas 751–783): longos, ex.:
  "Relatorio Pontual Censitario - Densidade populacional".
Decisões abertas:
- Reduzir/reformular os títulos dos mapas (ex.: só "Densidade Populacional" sem o prefixo).
- Tamanho/estilo da fonte do título do mapa (20 pt atual — coerente com o PDF?).
- Suprimir o subtítulo técnico (coordenada/raio/setores) nos mapas do PDF (mantê-lo no PNG da UI).

### D7 — Legenda dos mapas PNG (censo_map.py)
Estado atual (`_draw_legend_camada`, linhas 265–288):
  Posição fixa `legend_x = width - 252` (linha 485). Título "Legenda" em `_font(14)`, nome da
  camada em `_font(11)`. Cada entrada: retângulo 22×16 px + texto. Pins de referência ao final.
  Cor das bordas das amostras: `(148, 163, 184)` (cinza-azulado).
Decisões abertas:
- Largura da coluna de legenda (252 px atual — tira espaço do mapa?).
- Estilo das amostras de cor (retângulo atual — arredondado? circular?).
- Separação visual entre a legenda de faixas e a legenda de pins.
- Exibir o valor de corte de cada faixa ao lado do rótulo textual.

### D8 — Barra de escala e rodapé dos mapas PNG (censo_map.py)
Estado atual (`_draw_scale_bar`, linhas 227–243; rodapé em linhas 601–609):
  Escala no canto inferior-esquerdo da área de mapa, cor `_DARK_MAP_INK = (31, 41, 55)`.
  Rodapé de metodologia em `_font(11)`, cor cinza-slate, y=`height - 34`, comprimento total.
Decisões abertas:
- Cor/espessura da barra de escala (tinta escura `(31,41,55)` atual).
- Texto do rodapé: muito longo (inclui método + atribuição) — simplificar?
- Posicionar a atribuição de tiles apenas no PDF (já presente no rodapé do PDF) e remover do PNG.

## Riscos identificados
- Rebuild de imagem Docker + redeploy por digest na VPS necessários após cada iteração visual
  (precedente BLK-CENSO-02/03; guardrail §6 SSH gated). O ciclo de feedback visual é lento.
- Assets de branding em `data/ultra/` são gitignored: qualquer mudança de asset exige cópia
  manual ao volume do VPS. Planner deve verificar se novos assets são necessários.
- `_font()` usa `arial.ttf` com fallback para `load_default()` (linha 116–123 do censo_map.py);
  em Linux/Docker a fonte Arial pode não estar disponível, afetando métricas de texto.
  Trocar tipografia exigiria asset de fonte no repo ou no volume.
- `fpdf2` core font Helvetica é subconjunto latin-1; caracteres fora do latin-1 passam por
  `_ascii()` (linha 138–139) com `errors="replace"`. Nomes de cidades/redes com acentos já
  são tratados; o Planner deve confirmar que nenhuma mudança de texto quebra essa codificação.
- Regressão de testes de anti-PII: `test_pdf_sem_pii_de_pessoas` verifica bytes crus do PDF;
  qualquer texto novo deve ser revisado para não incluir PII.
- Compressão de stream está OFF (`set_compression(False)`, linha 198 do censo_report.py);
  PDFs maiores/mais ricos podem crescer significativamente em bytes.

## Guardrails ativos
- READ-ONLY sobre M1 (§2, §5): zero escrita em score_priorizacao, hex_score_estrutural,
  score_setor_2022_calibrado, residual, SAM, carteira, plano, artefatos oficiais.
- Anti-PII §4: .pptx/PDF nunca versionados; image24.png NUNCA embutido; compressão OFF.
- DEC-004: basemap online APENAS no caminho de geração do relatório; dashboard interativo
  NÃO depende de internet; fallback offline gracioso obrigatório.
- Método `setor_censitario_intersecao_area_1p5km` e raio 1.5 km INTOCADOS.
- 7 páginas e Big Numbers grid 4×2 de 8 métricas READ-ONLY são CONTRATOS invioláveis.
- Guardrail §6 SSH: nenhum comando no VPS sem confirmação explícita do usuário.
- Gate humano obrigatório APÓS o Planner e ANTES do Builder (esteira definida no backlog).
