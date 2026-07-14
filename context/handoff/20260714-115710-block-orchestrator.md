# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner (com etapa obrigatória de `[REVISÃO HUMANA — visual do PDF]` antes do fechamento pelo QA, conforme esteira do bloco)

## Bloco refinado
BLK-RELPON-06 — Legibilidade dos mapas no PDF (slides 2 e 3) + linha de dado por RAIO (densidade sobre área válida) no Relatório Pontual Censitário.

## Objetivo
Tornar título/linha de dado/legenda dos mapas legíveis só no PDF (fontes + resolução maiores, via parâmetro opcional) e trocar a fonte da faixa de "setor do pin" para os agregados do RAIO, com densidade = população do raio ÷ área de interseção válida (exclui água/vazio).

## Escopo permitido
- `src/motor_expansao/dashboard/censo_point.py` — `analisar_ponto_censitario_setores`: adicionar campo NOVO de densidade sobre área válida derivado de `pop_total_raio` (já calculado, ~linha 302-305) e `area_intersecao_total_m2` (já calculado, ~linha 265). `None`/"n/d" quando `area_intersecao_total_m2 == 0` ou não há setores no raio (guarda contra divisão por zero). Os 5 campos `*_setor_ponto` do BLK-RELPON-05 (linhas 190-196, 267-300) NÃO são removidos, apenas deixam de alimentar a faixa.
- `src/motor_expansao/dashboard/censo_map.py`:
  - (a) parâmetro(s) OPCIONAL(is) novo(s) — default `None` — de escala de texto e/ou canvas, aplicados a título (`title_font`, hoje `_font(20)`, linha 528), linha de dado (hoje `_font(17)`, linha 537) e legenda (`_draw_legend_camada`, corpo/rótulos hoje `_font(13)`/`_font(11)`, ~linha 302+). Seguir o padrão da emenda 2026-06-12 da DEC-005: default `None` = render idêntico ao atual.
  - (b) trocar a fonte dos 3 valores da faixa (`_legenda_valor_ponto` linha 232-234, `_format_valor_ponto_*` linhas 211-230, chamadas em `render_mapas_censitarios_combinados` linhas 857-864) de `*_setor_ponto` para os agregados do raio (D1: densidade NOVA, `renda_per_capita_media_raio` já existe, `score_setor_medio` já existe) e o texto fixo "no ponto" (linha 234) para "no raio".
  - `render_mapas_censitarios_combinados` (assinatura linha 684-701) e `_render_camada` (assinatura linha 490-515) já aceitam outros parâmetros opcionais (`street_ceil`/`street_gain`/`street_cap`/`choropleth_alpha`) com o mesmo padrão default-`None` — seguir o precedente.
- `src/motor_expansao/dashboard/censo_report.py` — passar a escala/resolução nova no caminho do PDF (`_mapas_calor_page` linha 375, `_competitors_page` linha 608, via `_draw_maps_grid`/`_map_grid_cells` linhas 313-374), restrito à geração do relatório.
- Testes: `tests/unit/test_relatorio_pontual_censitario_motor.py`, `tests/unit/test_relatorio_pontual_censitario_mapa.py`, `tests/unit/test_relatorio_pontual_censitario_export.py`.
- `docs/relatorio_pontual_censitario.md` — atualizar contrato (novo campo, rótulo "no raio", reversão do D3 do BLK-RELPON-05).
- `tasks/backlog.md` / `tasks/completed.md` — fechamento do ciclo, registrando explicitamente a reversão do D3 do BLK-RELPON-05.

## Fora de escopo
- `setor_censitario_intersecao_area_1p5km`, raio 1,5 km, `RAIO_CENSITARIO_DEFAULT_KM` — método de interseção INTOCADO.
- O choropleth (cor por setor/faixa) — só a FAIXA DE TEXTO muda; cores por setor permanecem exatamente como estão.
- Contagem/ordem/estrutura das 5 páginas do PDF, grid de Big Numbers 4x2, marca d'água anti-PII, `set_compression(False)`, `pdf_version`.
- `score_priorizacao`, `hex_score_estrutural`, pesos (`renda=0.40`/`pop=0.60`), carteira, plano curto prazo, plano de domínio, artefatos oficiais do M1 — READ-ONLY (§5 CLAUDE.md).
- Remoção dos 5 campos `*_setor_ponto` do BLK-RELPON-05 do `result` — permanecem para CSV/auditoria, só deixam de alimentar a faixa do mapa.
- Alterar o caminho do dashboard/API quando os novos parâmetros não são passados (deve permanecer byte-a-byte idêntico).
- Reabrir D1 ou D2 (já decididas por Vinicius em 2026-07-13; ver `tasks/current_task.md` e o corpo do bloco em `tasks/backlog.md`).

## Arquivos que devem ser lidos
- `CLAUDE.md` (§2, §4, §5, DEC-005 emenda 2026-06-12)
- `tasks/backlog.md` (bloco BLK-RELPON-06, linhas 1752-1839, contexto/diagnóstico/D1/D2/critério de aceite completos)
- `tasks/current_task.md`
- `src/motor_expansao/dashboard/censo_point.py` (função `analisar_ponto_censitario_setores`, linhas 145-319)
- `src/motor_expansao/dashboard/censo_map.py` (`_render_camada` linhas 490-620+, `_draw_legend_camada` linha 302+, `render_mapas_censitarios_combinados` linhas 684-900+, helpers `_format_valor_ponto_*`/`_legenda_valor_ponto` linhas 205-234, `_font` linha 118)
- `src/motor_expansao/dashboard/censo_report.py` (`_PAGE_W`/`_PAGE_H`, `_map_grid_cells` linha 313, `_mapas_calor_page` linha 375, `_competitors_page` linha 608, `MAP_LAYER_TITLES` linha 42)
- `docs/relatorio_pontual_censitario.md`

## Arquivos que podem ser alterados
- `src/motor_expansao/dashboard/censo_point.py`
- `src/motor_expansao/dashboard/censo_map.py`
- `src/motor_expansao/dashboard/censo_report.py`
- `tests/unit/test_relatorio_pontual_censitario_motor.py`
- `tests/unit/test_relatorio_pontual_censitario_mapa.py`
- `tests/unit/test_relatorio_pontual_censitario_export.py`
- `docs/relatorio_pontual_censitario.md`
- `tasks/backlog.md`
- `tasks/completed.md`
- `context/handoff.md` / `context/handoff/`

## Critérios de aceite
- Slides 2 e 3 do PDF: título, linha de dado e legenda legíveis e nítidos — texto efetivo alvo ≥ ~9-10 pt no slide, sem borrão de reamostragem — aprovado por REVISÃO VISUAL HUMANA (obrigatória antes do fechamento, não é automatizável pelo QA).
- Faixa superior dos mapas de densidade/renda/score passa a exibir os agregados do RAIO (`densidade` = campo novo `pop_total_raio / (area_intersecao_total_m2 / 1e6)`, `renda_per_capita_media_raio`, `score_setor_medio`), com rótulo "no raio" (não mais "no ponto").
- "n/d" (sem exceção) quando `area_intersecao_total_m2 == 0` ou não há setores intersectados no raio — cobrir com teste explícito de divisão por zero.
- Densidade nova verificada no caso Rio Branco/AC (`-9.95796, -67.81461`): deve ser MAIOR que a densidade antiga (`densidade_pop_raio_hab_km2`, hoje dividida por `π·raio²` fixo incluindo água), pois o denominador novo (área de interseção válida) é menor ou igual à área do círculo.
- Dashboard e API: render byte-a-byte idêntico ao atual quando os novos parâmetros de escala/canvas não são passados (default `None`).
- Choropleth (cor por setor) inalterado — só a faixa de texto muda.
- Interseção/raio/estrutura das 5 páginas/grid de Big Numbers/marca d'água: intocados; zero alteração em `score_priorizacao`/pesos/artefatos oficiais do M1.
- Os 5 campos `*_setor_ponto` do BLK-RELPON-05 continuam presentes no `result` (CSV/auditoria).
- Consistência de rótulos entre a faixa (agora "no raio") e os Big Numbers da página 4 (que já usam médias do raio) — sem contradição textual.
- Acentuação correta em texto de usuário (labels/legenda); identificadores sem acento; PDF com pontuação ASCII (sem travessão/bullet/seta/reticências/aspas curvas fora de latin-1).
- Testes cobrindo: novo campo de densidade (incl. área válida = 0 → "n/d"), rótulo "no raio", escala de texto/canvas (default `None` preserva render atual vs. valor explícito muda), reversão do D3 do BLK-RELPON-05 registrada em `completed.md`. `ruff`/`mypy` limpos; suíte verde.

## Criticidade classificada
Média

## Esteira recomendada
Block Orchestrator → Planner → [REVISÃO HUMANA — visual do PDF] → Builder → QA (Opus, conforme `tasks/current_task.md`)

## Riscos identificados
- Os números da faixa VÃO MUDAR em relatórios já gerados: a nova densidade é sempre ≥ à atual (denominador menor, exclui água/vazio) — esperado, mas comunicar a quem já usou PDFs antigos.
- Divisão por zero se a área de interseção válida for 0 — precisa cair em "n/d" sem exceção.
- O render (`censo_map.py`) é compartilhado com a API (BLK-API-01, DEC-005 emenda 2026-06-12) — os novos parâmetros precisam seguir o padrão default `None` já usado por `street_ceil`/`street_gain`/`street_cap`/`choropleth_alpha`, sob pena de quebrar o caminho da API silenciosamente.
- Risco de inconsistência textual entre a nova faixa "no raio" e os Big Numbers da página 4 (que já mostram médias do raio) se a formatação/arredondamento divergir.
- Fontes maiores + canvas maior no PDF podem estourar o layout da célula de ~299 pt na tira 1x3 (`_map_grid_cells`) se a escala escolhida for excessiva — validar visualmente antes do fechamento.
- Reversão do D3 do BLK-RELPON-05 precisa ficar rastreável no `completed.md` (histórico de decisões revertidas, conforme padrão de outras DECs revogadas explicitamente, ex. DEC-016 sobre DEC-005).

## Guardrails ativos
- READ-ONLY M1: NÃO tocar `score_priorizacao`/`hex_score_estrutural`/pesos (`renda=0.40`/`pop=0.60`)/carteira/plano/artefatos oficiais (§5 CLAUDE.md).
- NÃO tocar `setor_censitario_intersecao_area_1p5km`, raio 1,5 km, `RAIO_CENSITARIO_DEFAULT_KM`, estrutura/contagem das 5 páginas, grid de Big Numbers 4x2, marca d'água anti-PII, `set_compression(False)`.
- Parâmetros novos em `censo_*` seguem o padrão da emenda 2026-06-12 da DEC-005: opcionais, default `None` = comportamento idêntico ao dashboard; extensão da interface, não alteração do núcleo.
- Acentuação correta em todo texto de usuário (dashboard/PDF); identificadores (`key=`, `session_state`, colunas de DataFrame, enums) SEM acento; PDF (fpdf2/latin-1) usa só pontuação ASCII — travessão/bullet/seta/reticências/aspas curvas viram "?" silenciosamente.
- Toda mudança relevante entra com teste; nenhum PR sobe com CI quebrado.
- Autonomia do bloco = manual (NÃO loop-safe) — exige revisão visual humana do PDF, que o loop não enxerga.
