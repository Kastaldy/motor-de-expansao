# Current Task

## Bloco atual

ID: BLK-EST-01-FU1
Nome: Marca d'água sutil no canto (rodapé inferior-direito, horizontal) do Relatório Pontual
Status: aprovado
Tipo: feature (UX/UI — PDF, ajuste visual)
Criticidade: média
Esteira: Block Orchestrator → Planner → Builder → QA
Skill atual: QA (concluído — APROVADO)
Próxima Skill: Fechamento manual

## Objetivo
Tornar a marca d'água do PDF do Relatório Pontual Censitário MAIS SUTIL e no CANTO, em vez da faixa
diagonal grande centralizada de hoje. Decisão de produto (Felipe/Vini, 2026-06-12): **rodapé
inferior-direito, horizontal, pequena e discreta**. NÃO reverter o BLK-EST-01 — só reposicionar/reduzir.
READ-ONLY M1; só `censo_report.py` (render da marca); o texto e o `solicitante` permanecem iguais.

## Estado atual (censo_report.py)
- `_draw_watermark(pdf, text)` (linhas 260-275): desenha CENTRALIZADO (`cx=_PAGE_W/2`, `cy=_PAGE_H/2`),
  rotacionado `_WATERMARK_ANGLE=45.0`, fonte `_WATERMARK_FONT_PT=60`, `_WATERMARK_ALPHA=0.16`,
  cor `_WATERMARK_RGB=(120,120,120)`. Página 16:9: `_PAGE_W=960.0`, `_PAGE_H=540.0`.
- Desenhada em TODAS as páginas: loop `for page_number in range(1, pdf.pages_count+1): _draw_watermark(...)`
  (linhas 635-637). Comportamento por-página DEVE ser preservado (continua em todas as páginas).
- O texto vem de `_watermark_text(solicitante)` — INALTERADO (continua "Ultra Academia" ou
  "Ultra Academia | {solicitante}"). A feature do BLK-EST-01 NÃO é revertida.

## Correção (decisão aprovada)
- Reposicionar para o **canto inferior-direito**, com pequena margem (ex.: ~18-22 pt das bordas):
  `x = _PAGE_W - margem - get_string_width(text)`, `y = _PAGE_H - margem` (baseline via `pdf.text`).
- **Horizontal** (sem rotação): remover/zerar o `pdf.rotation(_WATERMARK_ANGLE...)` (ou `_WATERMARK_ANGLE=0`).
- **Pequena**: reduzir `_WATERMARK_FONT_PT` de 60 → ~9 (peso pode passar de "B" para normal para ficar discreto;
  Planner decide o valor exato 8-10pt).
- **Sutil**: manter cor cinza; ajustar opacidade para discreta-porém-legível em fonte pequena
  (Planner decide: 0.16 pode ficar fraco demais num corpo pequeno — avaliar ~0.30-0.40). Registrar o valor.
- Manter o desenho em TODAS as páginas, POR CIMA do conteúdo (chamado depois do conteúdo), e a restauração
  de estado gráfico (`local_context`).

## Atenção (testes)
- `tests/unit/test_relatorio_pontual_censitario_export.py`: `test_pdf_marca_dagua_com_solicitante` e
  `_sem_solicitante` verificam que o TEXTO da marca está embutido no stream (compressão OFF). NÃO devem
  asserir posição/ângulo — confirmar que seguem verdes (o texto continua presente). Se algum asserir
  ângulo/tamanho, ajustar com justificativa.

## Verificação (com render real)
- Após o Builder, o ORQUESTRADOR gera um PDF de amostra e LÊ a página (Read de PDF) para confirmar
  visualmente que a marca está no canto inferior-direito, pequena e sutil — além do pytest.

## Tiering de modelo (Passo 4) — Média
- Block Orchestrator: sonnet
- Planner: sonnet
- Builder: sonnet
- QA: opus 4.8 (sempre)

## Branch do ciclo
ciclo/BLK-EST-01-FU1 (a partir de ciclo/BLK-UI-06 @ HEAD; stack ainda não mergeado)

## Escopo permitido
- src/motor_expansao/dashboard/censo_report.py — `_draw_watermark` + constantes `_WATERMARK_*`
- tests/unit/test_relatorio_pontual_censitario_export.py — só se algum teste asserir posição/ângulo

## Fora de escopo (invioláveis)
- recalcular qualquer score ou artefato M1
- reverter a feature da marca d'água / mexer no texto ou no param `solicitante`
- alterar o template/conteúdo das 7 páginas, raio/interseção, geração de mapas
- tocar componentes do dashboard (pages/components) — este ciclo é só do PDF

## Paths pré-sujos (NÃO commitar — alheios ao ciclo)
- data/outputs/setores_censitarios_2022_geo/_metadata.json
- data/reports/relatorio_pontual_censitario_base_geo.md

dry_run: false
