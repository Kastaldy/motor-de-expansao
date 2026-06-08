# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner (criticidade Média; gate humano de decisões visuais já resolvido upfront em tasks/current_task.md)

## Bloco refinado
**BLK-CENSO-03** — Relatório censitário: trocar a base ESCURA (Dark Matter) por base CLARA (CartoDB Voyager COM labels) mantendo ruas/nomes nítidos por inversão do overlay de pixels nativos do tile; substituir a camada "Concorrentes" (que hoje tem choropleth de score de contexto) por uma versão SÓ-concorrentes (basemap + pins, sem choropleth); preservar o frame retangular já implementado no FU3.

## Objetivo
Inverter a lógica de overlay de pixels do FU3 (pixels claros → pixels escuros) para fazer ruas/nomes nativos do Voyager aparecerem sobre o choropleth translúcido, e substituir o choropleth de score da camada Concorrentes por um mapa de pins puro — tudo READ-ONLY sobre o M1.

## Escopo permitido
- `src/motor_expansao/dashboard/censo_map.py`: trocar `_BASEMAP_PROVIDER_ATTR` de `"DarkMatter"` para `"Voyager"` (ou variante COM labels); inverter a lógica de `_STREET_*` (luminância < cutoff para pixels escuros); retunar `_BASEMAP_CONTRAST`, `_CHOROPLETH_ALPHA`, `_CIRCLE_RGBA`, `_DARK_MAP_INK`; mudar a camada "concorrentes" para render sem choropleth (passar `sector_records_3857=[]` ou criar branch `_render_camada_pins`); ajustar fallback offline para canvas claro (hoje é escuro `(34,38,49)`)
- `src/motor_expansao/dashboard/constants.py`: retunar `DENSIDADE_POP_BANDS`, `RENDA_PER_CAPITA_BANDS` e `RESIDUAL_SCORE_BANDS` SOMENTE se saturação/contraste precisar ajuste para não conflitar com o verde do Voyager — sem troca de paleta (decisão do gate: manter rampas atuais)
- `src/motor_expansao/dashboard/pages.py`: ajuste de UI se necessário para refletir nova semântica da camada "concorrentes"
- `src/motor_expansao/dashboard/censo_report.py`: atualizar footer/atribuição do tile (de "Dark Matter" para "Voyager"); ajustar referências explícitas ao tema escuro
- `tests/unit/test_censo_map.py` (e demais testes correspondentes): atualizar/adicionar testes para novo basemap, overlay de pixels escuros, camada pins-pura, fallback canvas claro
- `tests/integration/test_relatorio_pontual_censitario_export.py`: atualizar/adicionar testes
- `tests/integration/test_streamlit_app.py`: ajustar smoke tests se necessário
- `docs/relatorio_pontual_censitario.md`: atualizar seções de basemap/camadas para refletir Voyager + pins-pura
- `CLAUDE.md §4`: atualizar descrição do FU3/estado atual do basemap para refletir FU4 (base clara)
- `DEC-004`: atualizar provedor de tile (Dark Matter → Voyager COM labels); mesmo guardrail, novo provedor

## Fora de escopo
- Qualquer recálculo ou escrita em artefatos do M1 (score_priorizacao, hex_score_estrutural, carteira, plano curto prazo, plano de domínio, artefatos oficiais)
- Mudar o método de interseção `setor_censitario_intersecao_area_1p5km` ou o raio fixo de 1.5 km (a análise/KPIs continuam circulares e intocadas)
- Tornar o dashboard interativo dependente de internet (tiles apenas na geração do relatório — DEC-004)
- Reusar edge-detection (ImageFilter.FIND_EDGES) — DESCARTADO por Felipe nos FU1/FU2; NUNCA reaplicar
- Trocar paleta de renda/score (gate decidiu MANTER rampas atuais; eventual ajuste é follow-up com nova aprovação de Felipe)
- Tornar o relatório em 4 mapas (gate decidiu SUBSTITUIR a camada Concorrentes, não adicionar 4ª)
- Template/branding final do PDF — isso é o BLK-CENSO-02, já concluído
- Modificar `pyproject.toml` ou `Dockerfile.streamlit` para nova dependência (o extra `[basemap]` com contextily já está instalado na imagem — DEC-004 FU1 atualizada; sem nova lib)

## Arquivos que devem ser lidos
- `src/motor_expansao/dashboard/censo_map.py` — estado FU3 vigente (Dark Matter + pixels claros); lógica de `_render_camada`, `_STREET_*`, `_fetch_basemap`, `render_mapas_censitarios_combinados`
- `src/motor_expansao/dashboard/constants.py` — rampas DENSIDADE_POP_BANDS / RENDA_PER_CAPITA_BANDS / RESIDUAL_SCORE_BANDS
- `src/motor_expansao/dashboard/pages.py` — UI do relatório censitário (`render_relatorio_pontual_censitario`)
- `src/motor_expansao/dashboard/censo_report.py` — PDF (`gerar_pdf_relatorio_pontual_censitario`), footer do tile, páginas de mapa
- `tests/unit/test_censo_map.py` — testes existentes do render (para não quebrar)
- `tests/integration/test_relatorio_pontual_censitario_export.py` — testes de export existentes
- `tests/integration/test_streamlit_app.py` — smoke tests do app
- `docs/relatorio_pontual_censitario.md` — contrato técnico atual; seções de basemap/camadas
- `CLAUDE.md §4` — descrição do FU3 vigente e DEC-004
- `tasks/current_task.md` — decisões do gate visual já resolvidas upfront

## Arquivos que podem ser alterados
- `src/motor_expansao/dashboard/censo_map.py` — mudanças principais
- `src/motor_expansao/dashboard/constants.py` — apenas retunar, se necessário
- `src/motor_expansao/dashboard/pages.py` — ajuste UI se necessário
- `src/motor_expansao/dashboard/censo_report.py` — footer/atribuição do tile
- `tests/unit/test_censo_map.py`
- `tests/integration/test_relatorio_pontual_censitario_export.py`
- `tests/integration/test_streamlit_app.py`
- `docs/relatorio_pontual_censitario.md`
- `CLAUDE.md §4` + `DEC-004` (seção dentro do CLAUDE.md)

## Critérios de aceite
1. `_BASEMAP_PROVIDER_ATTR` aponta para CartoDB Voyager COM labels (não Dark Matter)
2. Overlay de ruas invertido: pixels com luminância < cutoff (escuros) recolocados por cima do choropleth; NUNCA FIND_EDGES; ruas/nomes do Voyager visíveis e nítidos sobre a cor
3. Tema claro coerente: `_DARK_MAP_INK` atualizado para tinta escura; fallback offline = canvas branco/claro (não escuro `(34,38,49)`)
4. Camada "concorrentes" SEM choropleth de score: exibe apenas basemap + pins de concorrentes/Ultra + ponto central + legenda de pins
5. Frame retangular (paisagem) preservado na UI e no PDF — não regredir o FU3
6. READ-ONLY sobre M1: zero mudança em score/carteira/plano/artefatos; raio 1.5 km e `setor_censitario_intersecao_area_1p5km` intocados
7. Suite verde: `pytest -n auto` sem falhas; `ruff check` + `mypy` limpos; smoke `import streamlit_app` ok
8. Atribuição correta no footer/PDF: "(c) OpenStreetMap, (c) CARTO" com menção a Voyager
9. DEC-004 atualizada: registrar mudança de provedor Dark Matter → Voyager COM labels
10. CLAUDE.md §4 atualizado: refletir FU4 (base clara Voyager) como estado vigente
11. Validação visual obrigatória antes de propor deploy: Builder/QA validam com basemap real (contextily) no ponto de referência RJ `-22.87650,-43.34582`; aprovação de Felipe antes de rebuild de imagem + redeploy por digest na VPS

## Criticidade classificada
**Média** (visualização/apresentação; READ-ONLY sobre M1/score; tiles já cobertos pela DEC-004; sem novo desvio de guardrail)

## Esteira recomendada
Block Orchestrator (este) → **Planner** → Builder (opus, override +1 aprovado em current_task.md) → QA (opus 4.8)

Nota: gate humano de decisões visuais RESOLVIDO upfront (ver tasks/current_task.md). Planner planeja diretamente com as decisões já registradas; não precisa convocar novo gate.

## Riscos identificados
- **Tuning de overlay em base clara**: `_STREET_FLOOR`/`_STREET_GAIN`/`_STREET_CAP` foram calibrados para Dark Matter (pixels claros). Para Voyager (ruas são pixels escuros sobre fundo claro) os valores precisam recalibração cuidadosa; risco de ruas invisíveis ou excessivamente pesadas. Builder deve testar com imagem real antes de fixar valores.
- **Conflito verde Voyager × rampas**: Voyager carrega verde de vegetação que pode se confundir com verde de renda alta / score alto. Gate decidiu MANTER rampas — Builder/QA validam visualmente; se reprovar, abre follow-up (sem trocar paleta neste ciclo).
- **Alpha do choropleth em fundo claro**: `_CHOROPLETH_ALPHA=95` foi calibrado para Dark Matter; em fundo claro pode ficar opaco demais ou claro demais. Retunar é parte do escopo.
- **Camada pins-pura**: garantir que a legenda da camada Concorrentes reflita corretamente "só pins" (sem faixas de score), e que o título do mapa seja atualizado para não mencionar "choropleth" ou "score de contexto".
- **Fallback offline**: hoje é canvas escuro `(34,38,49)`; deve virar canvas claro. Garantir que CI (que usa `basemap=False`) continue passando com o novo fallback claro.
- **Rebuild de imagem obrigatório para deploy**: cada iteração visual exige rebuild + redeploy por digest na VPS (memória de deploy). QA não executa deploy — apenas valida; deploy exige aprovação de Felipe.

## Guardrails ativos
- **ABSOLUTO**: zero escrita em `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano de domínio ou qualquer artefato oficial do M1.
- **DEC-004**: tiles permitidos APENAS no caminho de geração do relatório; cache local em `data/cache/basemap_tiles/`; fallback offline gracioso obrigatório; dashboard interativo NÃO pode depender de internet. Provedor muda (Dark Matter → Voyager COM labels) mas o guardrail é idêntico.
- **NUNCA edge-detection**: FU1/FU2 foram descartados por Felipe; overlay usa pixels nativos do tile (pixels escuros do Voyager), NUNCA FIND_EDGES.
- **Interseção `setor_censitario_intersecao_area_1p5km` e raio 1.5 km**: INTOCADOS. Mudança é 100% de render.
- **Sem nova dependência de biblioteca**: extra `[basemap]` (contextily) já está na imagem; não adicionar nova lib sem aprovação.
- **Guardrail VPS (§6 CLAUDE.md)**: NUNCA executar comandos no servidor via MCP sem confirmação explícita de Felipe para cada comando individual.
