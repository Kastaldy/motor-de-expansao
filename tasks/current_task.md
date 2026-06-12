# Current Task

## Bloco atual

ID: BLK-EST-01-FU2
Nome: Marca d'água visível-porém-discreta + branca na capa (turquesa)
Status: aprovado
Tipo: feature (UX/UI — PDF, ajuste visual)
Criticidade: média
Esteira: Block Orchestrator → Planner → Builder → QA
Skill atual: QA (concluído — APROVADO)
Próxima Skill: Fechamento manual

## Objetivo
A marca d'água do FU1 (canto inferior-direito) ficou SUTIL DEMAIS (0.40/9pt cinza): no conteúdo passa
batida e na capa (fundo turquesa) some. Ajustar para DISCRETA-PORÉM-VISÍVEL e legível na capa.
READ-ONLY M1; só `censo_report.py`; texto/`solicitante` INALTERADOS.

## Diagnóstico (render real verificado pelo orquestrador)
- O código do FU1 está correto e desenha a marca no canto inferior-direito em TODAS as páginas (loop 635-637).
  NÃO é cache (não há @st.cache_data no caminho do relatório em pages.py).
- A 0.40/9pt/cinza ela é fraca demais: conteúdo (fundo branco) quase imperceptível; CAPA (fundo turquesa)
  praticamente invisível porque cinza sobre turquesa não contrasta.

## Decisões de produto aprovadas (Felipe/Vini, 2026-06-12)
1. **Visibilidade**: discreta porém visível → `_WATERMARK_ALPHA` 0.40 → **0.65**; `_WATERMARK_FONT_PT` 9 → **10**.
   Cor cinza `_WATERMARK_RGB=(120,120,120)` mantida no conteúdo.
2. **Capa**: texto **claro/branco** na capa (visível sobre o turquesa); cinza nas demais páginas. Cor
   condicional por página (página 1 = capa → branco; páginas 2-7 → cinza).

## Estado atual (censo_report.py)
- Constantes: `_WATERMARK_FONT_PT=9`, `_WATERMARK_ANGLE=0.0`, `_WATERMARK_ALPHA=0.40`, `_WATERMARK_RGB=(120,120,120)`,
  `_WATERMARK_MARGIN=20.0`, `_PAGE_W=960`, `_PAGE_H=540`.
- `_draw_watermark(pdf, text)` (canto inf-direito, horizontal) usa `_WATERMARK_RGB` fixo.
- Loop por-página (635-637): `for page_number in range(1, pdf.pages_count+1): pdf.page = page_number; _draw_watermark(pdf, wm_text)`.
  Página 1 = capa.

## Correção (a especificar pelo Planner com valores exatos)
- `_WATERMARK_ALPHA` 0.40 → 0.65; `_WATERMARK_FONT_PT` 9 → 10.
- Adicionar `_WATERMARK_RGB_COVER = (255, 255, 255)` (ou claro) para a capa.
- `_draw_watermark` passa a aceitar a COR por parâmetro (ex.: `rgb: tuple[int,int,int] = _WATERMARK_RGB`),
  mantendo posição/horizontal/`local_context`. O loop decide: `page_number == 1` → `_WATERMARK_RGB_COVER`,
  senão `_WATERMARK_RGB`.
- Posição/canto/horizontal e o desenho em todas as páginas: preservados. Texto/`solicitante`: inalterados.

## Atenção (testes)
- `test_pdf_marca_dagua_*` checam o TEXTO embutido (não cor/posição) → devem seguir verdes. Se algum
  asserir cor/alpha, ajustar com justificativa.

## Verificação (com render real)
- Orquestrador gera PDF de amostra e renderiza a CAPA (marca branca visível sobre turquesa) e uma página
  de conteúdo (cinza 0.65/10pt legível no canto) — além do pytest.

## Tiering de modelo (Passo 4) — Média
- Block Orchestrator: sonnet
- Planner: sonnet
- Builder: sonnet
- QA: opus 4.8 (sempre)

## Branch do ciclo
ciclo/BLK-EST-01-FU2 (a partir de ciclo/BLK-EST-01-FU1 @ HEAD; stack não mergeado)

## Escopo permitido
- src/motor_expansao/dashboard/censo_report.py — constantes `_WATERMARK_*`, `_draw_watermark`, o loop 635-637
- tests/unit/test_relatorio_pontual_censitario_export.py — só se algum teste asserir cor/alpha

## Fora de escopo (invioláveis)
- recalcular qualquer score ou artefato M1
- mexer no texto/`_watermark_text`/param `solicitante`
- alterar template/7 páginas/mapas/raio/interseção
- tocar dashboard (pages/components)

## Paths pré-sujos (NÃO commitar — alheios ao ciclo)
- data/outputs/setores_censitarios_2022_geo/_metadata.json
- data/reports/relatorio_pontual_censitario_base_geo.md

dry_run: false
