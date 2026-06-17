# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner → [APROVAÇÃO HUMANA (gate obrigatório — ver Risco 1 abaixo)] → Builder → QA

## Bloco refinado
BLK-UI-08 — Refinos de UX/UI do dashboard (paleta Renda Média, tab selector sticky, busca por endereço)

## Objetivo
Aplicar três melhorias de interface no dashboard sem regressão funcional nem impacto no M1: (1) nova paleta de 5 faixas absolutas para o mapa de Renda Média, (2) tab selector fixo no topo ao rolar a página, (3) barra de pesquisa que aceita endereço livre além de coordenada numérica.

## Escopo permitido
- `src/motor_expansao/dashboard/constants.py` — substituir `RENDA_PER_CAPITA_BANDS` (linhas 335–341) pelas 5 novas faixas absolutas com as cores fornecidas pelo usuário.
- `src/motor_expansao/dashboard/pages.py` — (a) adicionar CSS de `position: sticky; top: 0` ao bloco `div[data-testid="stSegmentedControl"]` dentro de `inject_styles` (linhas 318–329); (b) ampliar `render_coord_search_sidebar` (linha 586) para aceitar texto livre de endereço além de lat/lng, **somente conforme decisão do gate humano** (ver Risco 1).
- `src/motor_expansao/api/maps_geocoder.py` — apenas LEITURA; `extract_any_coord` (linha 69) e `build_search_url` (linha 80) são helpers puros reutilizáveis sem abrir rede.
- `streamlit_app.py` — apenas LEITURA de referência; sem alteração esperada.
- `tests/integration/test_streamlit_app.py` — atualizar ou adicionar testes para as 3 mudanças.

## Fora de escopo
- `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano de domínio, artefatos M1 oficiais — READ-ONLY absoluto.
- `DENSIDADE_POP_BANDS` (paleta de Densidade) e `RESIDUAL_SCORE_BANDS` — NÃO alterar.
- `censo_map.py` — NÃO alterar; apenas consome `RENDA_PER_CAPITA_BANDS` via import; mudança em `constants.py` se propaga automaticamente.
- Carga lazy por UF (Bloco 4), render lazy de abas (Bloco 5), fonte de mapa enxuta (Bloco 6) — preservar integralmente.
- `MapsGeocoder` (instância Selenium) — NÃO instanciar no dashboard; proibido por guardrail §2 e §6.
- Geocoding ao vivo/Nominatim/qualquer HTTP externo chamado de dentro do dashboard — proibido sem DEC aprovada.
- Frentes herdadas F2-E (hero header contextual com UF) e F2-G (limpeza CSS legado sidebar) — fora deste ciclo.

## Arquivos que devem ser lidos

### Mudança 1 — Paleta Renda Média
- `src/motor_expansao/dashboard/constants.py` linhas 327–341 — definição atual de `RENDA_PER_CAPITA_BANDS` (5 faixas + RGBA). Aqui está a única alteração necessária.
- `src/motor_expansao/dashboard/censo_map.py` linhas 26–27, 178–182, 767–810 — consumidores de `RENDA_PER_CAPITA_BANDS` (coloring, choropleth, legenda do relatório censitário). A troca em `constants.py` se propaga; confirmar que não há override local de cor de renda.
- `src/motor_expansao/dashboard/censo_report.py` linhas 13 — importa `build_search_url` de `maps_geocoder`; não consome `RENDA_PER_CAPITA_BANDS` diretamente. Verificar se há alguma referência inline de cor de renda.

### Mudança 2 — Tab selector sticky
- `src/motor_expansao/dashboard/pages.py` linhas 140–460 — função `inject_styles` completa; bloco CSS do `stSegmentedControl` nas linhas 318–355. É onde entra o `position: sticky; top: 0; z-index: ...`.
- `streamlit_app.py` linhas 510–535 — ordem de chamada: `render_coord_search_sidebar` (linha 515) → `render_tab_selector` (linha 524). O sticky deve cobrir apenas o seletor de abas.
- Limitação técnica a avaliar no Planner: `.block-container` do Streamlit pode ter `overflow: hidden` nos ancestrais do `stSegmentedControl`, impedindo `position: sticky`. Planner deve confirmar seletor CSS correto e se é necessário injetar `overflow: visible` nos ancestrais. Fallback possível: `position: fixed` com padding-top compensatório no conteúdo abaixo.

### Mudança 3 — Busca por endereço (DEPENDE DO GATE HUMANO)
- `src/motor_expansao/dashboard/pages.py` linhas 586–609 — `render_coord_search_sidebar`: widget de texto, `parse_coordinate_input`, mensagem de erro. Assinatura `-> tuple[float, float] | None` deve ser preservada.
- `src/motor_expansao/dashboard/data.py` linhas 600+ — `parse_coordinate_input` (parser numérico offline); primeiro caminho de parsing, preservar.
- `src/motor_expansao/api/maps_geocoder.py` linhas 69–83 — `extract_any_coord` (extrai lat/lng de URL Maps via regex, sem rede) e `build_search_url` (monta URL de busca; equivale à `endereco_para_link_maps` do usuário). O código fornecido pelo usuário é alternativo; Builder pode usar o existente `build_search_url` ou o novo, a decidir no Planner.
- `streamlit_app.py` linha 515 — ponto de chamada; assinatura e contrato de retorno inalterados.

## Decisões pendentes de gate humano

### D1 — Fluxo endereço → coordenada (obrigatória antes de codar a mudança 3)
O campo atual aceita apenas lat/lng numérico. Para aceitar endereço livre, o fluxo de resolução tem duas alternativas:

**Alternativa A (100% offline — sem DEC):**
O campo aceita endereço, monta o link de busca com `build_search_url` (ou `endereco_para_link_maps` fornecida), exibe o link como botão clicável para o usuário abrir no browser e copiar a coordenada de volta. Não resolve automaticamente — requer ação manual do usuário. NÃO tensiona o guardrail §2.

**Alternativa B (fetch leve com HTTP puro — exige DEC):**
O dashboard faz uma requisição HTTP à URL de busca do Maps, lê a URL final redirecionada e extrai a coordenada via `extract_any_coord`. Sem Selenium; usa `urllib.request`. Resolve automaticamente, mas **tensiona guardrail §2** ("não criar dependência de API ao vivo no dashboard de produção"). Requer nova DEC com a mesma estrutura da DEC-004, restringindo o fetch ao caminho de resolução de endereço (não à carga/interatividade do mapa). O gate humano deve decidir qual alternativa adotar antes de qualquer implementação.

## Arquivos que podem ser alterados
- `src/motor_expansao/dashboard/constants.py` — mudança 1 (RENDA_PER_CAPITA_BANDS)
- `src/motor_expansao/dashboard/pages.py` — mudanças 2 e 3 (inject_styles + render_coord_search_sidebar)
- `tests/integration/test_streamlit_app.py` — novos/atualizados testes para as 3 mudanças
- `context/handoff.md` e `context/handoff/<timestamp>-*.md` — housekeeping de ciclo (não commitar com os pré-sujos)
- `tasks/current_task.md`, `tasks/backlog.md`, `tasks/completed.md` — housekeeping de bloco

## Critérios de aceite
1. `RENDA_PER_CAPITA_BANDS` em `constants.py` contém exatamente 5 faixas com as novas cores (hex→RGBA): `#00CC00` (R=0,G=204,B=0) para >5000; `#A8FFA8` (R=168,G=255,B=168) para 3500–5000; `#FFD21C` (R=255,G=210,B=28) para 2000–3500; `#FFFF00` (R=255,G=255,B=0) para 1000–2000; `#F7F48B` (R=247,G=244,B=139) para ≤1000. Alpha preservado em 150 (padrão dos outros bands). `DENSIDADE_POP_BANDS` e `RESIDUAL_SCORE_BANDS` intocados.
2. Ao rolar a página, o `stSegmentedControl` permanece visível no topo da área de conteúdo. CSS não quebra elementos existentes (botões, cards, sidebar). Verificável manualmente.
3. O campo `coord_search_input` (key preservada) aceita endereço livre e produz `(lat, lng)` ou exibe mensagem clara de fallback. Fluxo numérico lat/lng existente continua funcionando. Assinatura de `render_coord_search_sidebar` retorna `tuple[float, float] | None` — inalterada.
4. Suite completa verde (`pytest -q`); novos testes cobrem: (a) `RENDA_PER_CAPITA_BANDS` com as 5 novas cores; (b) CSS sticky presente no output de `inject_styles`; (c) `render_coord_search_sidebar` com entrada de endereço livre (mock do geocoder se houver chamada de rede).
5. `ruff` e `mypy` limpos. READ-ONLY M1: nenhum artefato oficial tocado.

## Criticidade classificada
Alta

## Esteira recomendada
Block Orchestrator (concluído) → Planner (opus) → [APROVAÇÃO HUMANA — obrigatória; decisão D1 sobre busca por endereço antes de codar] → Builder (opus) → QA (opus 4.8)

## Riscos identificados

### Risco 1 — PRINCIPAL: busca por endereço tensiona guardrail §2
O guardrail §2 do CLAUDE.md proíbe "criar dependência de API ao vivo no dashboard de produção". Converter endereço→coordenada em tempo real exige chamada HTTP ao Google Maps. O precedente DEC-004 liberou tiles online apenas no caminho de geração do relatório censitário, não na interatividade do dashboard. Qualquer fluxo de resolução automática de endereço no dashboard exige nova DEC com aprovação humana. **Não implementar sem o gate respondido.**

### Risco 2 — CSS sticky pode não funcionar no layout do Streamlit
O `.block-container` pode ter `overflow: auto` ou `overflow: hidden` nos ancestrais do `stSegmentedControl`, impedindo que `position: sticky` funcione. Planner deve avaliar e planejar fallback (`position: fixed` + padding-top compensatório) caso necessário.

### Risco 3 — Alpha das novas cores de Renda
As cores fornecidas são hex sólidos (sem alpha). O padrão dos outros `BANDS` usa alpha=150 (transparência para ruas do basemap). Builder deve converter para RGBA com alpha=150 e registrar a escolha em comentário, a não ser que o usuário indique diferente.

### Risco 4 — Branch contém commits do BLK-FIX-14 não mergeado
Paths pré-sujos (`data/outputs/setores_censitarios_2022_geo/_metadata.json` e `data/reports/relatorio_pontual_censitario_base_geo.md`) não devem ser commitados. Builder deve usar `git add` por path específico.

## Guardrails ativos
- §2 CLAUDE.md: "Não criar dependência de API ao vivo no dashboard de produção." — afeta diretamente a mudança 3.
- §5 CLAUDE.md (guardrail permanente): visualizações e interações de mapa não podem recalcular ou alterar artefatos M1.
- Blocos 4–6 (carga lazy por UF, render lazy de abas, fonte de mapa enxuta): contratos de performance intocados.
- DEC-001 (pesos/fórmula M1) e DEC-004 (tiles online restritos ao relatório): vigentes; não reabrir.
