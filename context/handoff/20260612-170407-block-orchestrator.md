# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
BLK-EST-01-FU2 — Marca d'água discreta-porém-visível + branca na capa (fundo turquesa)

## Objetivo
Ajustar `_draw_watermark` em `censo_report.py` para que a marca fique visível no conteúdo (alpha 0.65, 10 pt, cinza) e legível na capa turquesa (branca, mesmos alpha/tamanho), sem alterar texto, template, mapas ou qualquer artefato M1.

## Âncoras confirmadas (file:line)

| Item | Linha(s) | Detalhe |
|---|---|---|
| `_WATERMARK_BASE` | 82 | `"Ultra Academia"` |
| `_WATERMARK_RGB` | 83 | `(120, 120, 120)` |
| `_WATERMARK_ALPHA` | 84 | `0.40` |
| `_WATERMARK_ANGLE` | 85 | `0.0` |
| `_WATERMARK_FONT_PT` | 86 | `9` |
| `_WATERMARK_MARGIN` | 87 | `20.0` |
| `_draw_watermark(pdf, text)` | 261–275 | usa `_WATERMARK_RGB` fixo via `set_text_color`; `local_context(fill_opacity=_WATERMARK_ALPHA)` |
| Loop por-página | 635–637 | `for page_number in range(1, pdf.pages_count + 1): pdf.page = page_number; _draw_watermark(pdf, wm_text)` |
| Página 1 = capa | — | primeiro índice do loop; fundo turquesa (asset ou sólido) |

## Escopo permitido
- `src/motor_expansao/dashboard/censo_report.py`:
  - Alterar `_WATERMARK_ALPHA`: `0.40` → `0.65`
  - Alterar `_WATERMARK_FONT_PT`: `9` → `10`
  - Adicionar constante `_WATERMARK_RGB_COVER = (255, 255, 255)` (branca para a capa)
  - Adicionar parâmetro `rgb: tuple[int, int, int] = _WATERMARK_RGB` em `_draw_watermark`; usar `rgb` no `set_text_color` em vez do global fixo
  - Loop (linhas 635–637): passar `rgb=_WATERMARK_RGB_COVER` quando `page_number == 1`, caso contrário `rgb=_WATERMARK_RGB`
- `tests/unit/test_relatorio_pontual_censitario_export.py`: SOMENTE se algum teste asserir cor ou alpha — nenhum dos 3 `test_pdf_marca_dagua_*` faz isso (asserem apenas texto no stream e `/Count 7`), então o arquivo de testes provavelmente NÃO precisa ser tocado

## Fora de escopo
- Qualquer score, artefato ou parâmetro M1 (score_priorizacao, hex_score_estrutural, carteira, plano, parquets oficiais)
- Texto da marca d'água (`_WATERMARK_BASE`, `_watermark_text`, parâmetro `solicitante`) — INALTERADOS
- Template (7 páginas, ordem, `/Count 7`, `set_compression(False)`, `pdf_version="1.4"`)
- Mapas / raio 1.5 km / método de interseção
- Dashboard (`pages.py`, `components.py`)
- Posição (canto inferior-direito), orientação (horizontal), `local_context`, desenho em todas as páginas — PRESERVADOS

## Arquivos que devem ser lidos
- `src/motor_expansao/dashboard/censo_report.py` — linhas 79–87 (constantes), 261–275 (`_draw_watermark`), 632–637 (loop por-página)
- `tests/unit/test_relatorio_pontual_censitario_export.py` — linhas 206–244 (os 3 testes de marca d'água; confirmar que não assertam cor/alpha)

## Arquivos que podem ser alterados
- `src/motor_expansao/dashboard/censo_report.py` (único arquivo de produção a tocar)
- `tests/unit/test_relatorio_pontual_censitario_export.py` — apenas se necessário (expectativa: não precisa)

## Critérios de aceite
1. `_WATERMARK_ALPHA == 0.65` e `_WATERMARK_FONT_PT == 10` no código após a mudança
2. `_WATERMARK_RGB_COVER = (255, 255, 255)` adicionada junto às demais constantes `_WATERMARK_*`
3. `_draw_watermark` aceita parâmetro `rgb` (default `_WATERMARK_RGB`) e o usa em `set_text_color`
4. Loop: página 1 → `rgb=_WATERMARK_RGB_COVER`; páginas 2-7 → `rgb=_WATERMARK_RGB`
5. Posição, horizontal e desenho em todas as 7 páginas: preservados
6. `pytest -q tests/unit/test_relatorio_pontual_censitario_export.py -k "marca_dagua"` → 3 passed (sem novas falhas)
7. Suíte FULL sem regressão (baseline: `696 passed, 1 skipped, 3 failed pré-existentes`)
8. `ruff check` e `mypy` limpos em `censo_report.py`
9. Verificação final por render: orquestrador gera PDF de amostra e confirma capa (marca branca visível sobre turquesa) e página de conteúdo (cinza, 0.65, 10 pt, legível no canto inferior-direito)
10. Paths pré-sujos (`data/outputs/setores_censitarios_2022_geo/_metadata.json`, `data/reports/relatorio_pontual_censitario_base_geo.md`) NÃO commitados

## Criticidade classificada
Média

## Esteira recomendada
Block Orchestrator (este handoff) → Planner → Builder → QA

## Riscos identificados
- Os 3 testes `test_pdf_marca_dagua_*` assertam apenas presença de texto no stream e `/Count 7` — NÃO cor ou alpha — portanto devem seguir verdes sem alteração. Se o Builder encontrar qualquer teste que asserte `_WATERMARK_RGB` ou `_WATERMARK_ALPHA` como valor literal, deve ajustar esse teste com justificativa.
- A assinatura de `_draw_watermark` ganha um parâmetro novo com default; qualquer chamada existente (apenas o loop em 635-637) segue compatível.
- Verificação final é POR RENDER (pytest não cobre cor); o orquestrador valida o efeito visual ao fechar o ciclo.
- Anti-PII §4 não é afetado: `set_compression(False)` e `pdf_version="1.4"` não são tocados; o texto da marca não muda.

## Guardrails ativos
- READ-ONLY sobre o M1: não recalcular score nem alterar artefatos oficiais.
- Guardrail permanente (CLAUDE.md §4): visualizações e o relatório não podem alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano ou artefatos oficiais do M1 sem aprovação explícita.
- Anti-PII §4: `.pptx`/PDF nunca versionados; cartão de contato `image24.png` nunca embutido. `set_compression(False)` preservado para auditabilidade.
- Paths pré-sujos alheios ao ciclo não devem ser commitados.
