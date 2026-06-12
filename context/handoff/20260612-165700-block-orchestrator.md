# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
**BLK-EST-01-FU1** — Marca d'água sutil no canto inferior-direito do PDF do Relatório Pontual Censitário

## Objetivo
Reposicionar e reduzir a marca d'água do PDF de uma faixa diagonal grande centralizada para um rodapé horizontal pequeno e discreto no canto inferior-direito, sem reverter a feature BLK-EST-01.

## Âncoras confirmadas (censo_report.py)

| Elemento | Localização atual |
|---|---|
| `_WATERMARK_BASE` | linha 82 |
| `_WATERMARK_RGB` | linha 83 |
| `_WATERMARK_ALPHA` | linha 84 — `0.16` |
| `_WATERMARK_ANGLE` | linha 85 — `45.0` (a zerar) |
| `_WATERMARK_FONT_PT` | linha 86 — `60` (reduzir para ~9) |
| `_draw_watermark(pdf, text)` | linhas 260–275 |
| Loop por-página | linhas 635–637 |

Estado atual de `_draw_watermark` (linhas 260–275):
- Fonte: `"Helvetica"`, `"B"`, `_WATERMARK_FONT_PT=60`
- Cor: `_WATERMARK_RGB=(120,120,120)`, `fill_opacity=_WATERMARK_ALPHA=0.16`
- Posição: `cx=_PAGE_W/2=480.0`, `cy=_PAGE_H/2=270.0` (centralizado)
- Rotação: `pdf.rotation(_WATERMARK_ANGLE=45.0, x=cx, y=cy)`
- `pdf.text(x0=cx-w/2, y0=cy, text)` — baseline no centro da página

Dimensões da página: `_PAGE_W=960.0`, `_PAGE_H=540.0` (16:9 widescreen, linhas 76–77).

## Escopo permitido
- `src/motor_expansao/dashboard/censo_report.py`:
  - Constantes `_WATERMARK_ANGLE`, `_WATERMARK_FONT_PT`, `_WATERMARK_ALPHA` — ajustar valores
  - Adicionar constante `_WATERMARK_MARGIN` (margem do canto, ex.: 18–22 pt)
  - Corpo de `_draw_watermark`: reposicionar para canto inferior-direito, remover rotação, reduzir fonte
- `tests/unit/test_relatorio_pontual_censitario_export.py` — SOMENTE se algum teste asserir ângulo/posição/tamanho (confirmado abaixo: NENHUM o faz; arquivo provavelmente inalterado)

## Decisão de produto (aprovada Felipe/Vini, 2026-06-12)
- **Posição**: rodapé inferior-direito com margem `_WATERMARK_MARGIN` (~18–22 pt das bordas direita e inferior)
  - `x = _PAGE_W - _WATERMARK_MARGIN - pdf.get_string_width(text)`
  - `y = _PAGE_H - _WATERMARK_MARGIN` (baseline via `pdf.text`)
- **Ângulo**: horizontal — `_WATERMARK_ANGLE = 0.0`; o `with pdf.rotation(...)` deve ser removido do corpo (mas o `with pdf.local_context(fill_opacity=...)` PERMANECE para restaurar opacidade)
- **Fonte**: reduzir `_WATERMARK_FONT_PT` de 60 → ~9 pt; peso pode passar de `"B"` para `""` (normal) para ser mais discreto — Planner decide valor exato 8–10 pt e peso
- **Opacidade**: `_WATERMARK_ALPHA=0.16` foi calibrada para fonte 60 pt; em 9 pt pode ficar invisível — Planner avalia ~0.30–0.45 e registra o valor escolhido no handoff
- **Preservar**: desenho em TODAS as 7 páginas via loop linhas 635–637 (inalterado), chamado DEPOIS do conteúdo, restauração de estado gráfico via `local_context`

## Confirmação dos testes (test_relatorio_pontual_censitario_export.py, linhas 206–244)

Os três testes de marca d'água APENAS verificam bytes de texto e contagem — NÃO asserem posição, ângulo ou tamanho:

- `test_pdf_marca_dagua_com_solicitante` (L206): assere `b"Ultra Academia" in pdf_bytes` e `b"Analista Teste" in pdf_bytes`
- `test_pdf_marca_dagua_sem_solicitante` (L221): assere `b"Ultra Academia" in pdf_bytes`
- `test_pdf_marca_dagua_em_todas_as_paginas` (L235): assere `pdf_bytes.count(b"Ultra Academia") >= 7`

Todos continuarão verdes após o fix (o texto permanece inalterado em todas as 7 páginas).

## Fora de escopo
- Recalcular qualquer score ou artefato M1
- Reverter a feature da marca d'água / alterar o texto ou o parâmetro `solicitante`
- Alterar template/conteúdo das 7 páginas, raio/interseção, geração de mapas
- Tocar componentes do dashboard (`pages.py`, `components.py`) — este ciclo é só do PDF
- `data/outputs/setores_censitarios_2022_geo/_metadata.json` e `data/reports/relatorio_pontual_censitario_base_geo.md` (paths pré-sujos, NÃO commitar)

## Arquivos que devem ser lidos
- `src/motor_expansao/dashboard/censo_report.py` (linhas 76–87 constantes; 260–276 `_draw_watermark`; 632–638 loop por-página)
- `tests/unit/test_relatorio_pontual_censitario_export.py` (linhas 206–244 — confirmar que nenhum teste assere posição/ângulo/tamanho)

## Arquivos que podem ser alterados
- `src/motor_expansao/dashboard/censo_report.py` — constantes `_WATERMARK_*` + corpo de `_draw_watermark`
- `tests/unit/test_relatorio_pontual_censitario_export.py` — APENAS se necessário (provavelmente inalterado)

## Critérios de aceite
1. PDF gerado com `solicitante="X"` contém `b"Ultra Academia"` e `b"X"` nos bytes crus (testes existentes continuam verdes).
2. `pdf_bytes.count(b"Ultra Academia") >= 7` continua verde (texto presente em todas as 7 páginas).
3. `b"/Count 7"` presente (7 páginas, ordem e estrutura intactas).
4. Marca d'água está no canto inferior-direito, horizontal (ângulo 0), fonte ≤10 pt — verificado por render visual: orquestrador gera PDF e lê a página via Read de PDF.
5. Nenhum arquivo de artefato M1 alterado; nenhum score recalculado.
6. Ruff + mypy limpos.
7. Suite completa `pytest -q` verde sem novas falhas (baseline atual: 696 passed, 1 skipped, 3 failed pré-existentes — as 3 falhas são pré-existentes e alheias a este ciclo).

## Criticidade classificada
Média

## Esteira recomendada
BO (concluído) → **Planner** → Builder → QA (sempre Opus 4.8)

## Tiering de modelo
- Planner: sonnet
- Builder: sonnet
- QA: opus 4.8 (sempre, sem exceção)

## Riscos identificados
- **Opacidade vs legibilidade**: `_WATERMARK_ALPHA=0.16` projetada para fonte 60 pt pode tornar a marca invisível em 9 pt — Planner deve escolher valor entre 0.30–0.45 e justificar no handoff.
- **`local_context` sem `rotation`**: ao remover `pdf.rotation(...)`, o `with pdf.local_context(fill_opacity=...)` permanece obrigatório para restaurar o estado gráfico de opacidade — não remover o `local_context`.
- **Testes de contagem (`>= 7`)**: o texto continua presente em todas as páginas; sem risco.
- **Render visual**: pytest não valida posição — verificação final obrigatória via leitura de PDF pelo orquestrador.
- **Paths pré-sujos**: `_metadata.json` e `relatorio_pontual_censitario_base_geo.md` aparecem no `git status`; NÃO devem entrar no commit deste ciclo.

## Guardrails ativos (CLAUDE.md §2/§4/§5)
- READ-ONLY sobre o M1: nenhuma visualização, análise ou interação de mapa pode recalcular ou alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano ou artefatos oficiais do M1.
- Anti-PII §4: `set_compression(False)` e `pdf_version="1.4"` INALTERADOS (auditabilidade); cartão de contato `image24.png` NUNCA embutido; texto da marca permanece "Ultra Academia" ou "Ultra Academia | {solicitante}".
- Método de interseção `setor_censitario_intersecao_area_1p5km` e raio 1,5 km INTOCADOS.
