# Current Task

## Bloco atual

ID: BLK-UI-09
Nome: Busca por link do Google Maps na barra de pesquisa (3 opções: coordenada, endereço, link)
Status: aprovado
Tipo: feature (UX/UI; READ-ONLY sobre M1)
Criticidade: alta (confirmada pelo Block Orchestrator em 2026-06-19)
Esteira: Block Orchestrator → Planner → [REVISÃO HUMANA — gate obrigatório] → Builder → QA
Skill atual: QA (CONCLUÍDO — APROVADO)
Próxima Skill: Fechamento manual (orquestrador: housekeeping Passo 6.0 + merge humano)

## QA (CONCLUÍDO 2026-06-19) — VEREDITO: APROVADO
- Suíte FULL SERIAL (gate): **1030 passed, 1 skipped, 0 failed** (`-n auto` abortou com
  INTERNALERROR de execnet no Python 3.14 — contorno de ambiente autorizado, NÃO bypass).
- Subset impactado: **252 passed, 0 failed**. import streamlit_app **ok**. ruff **All checks
  passed**. mypy **Success: no issues found in 2 source files**.
- NO-BYPASS de rede confirmado: todos os `urlopen` nos testes são monkeypatched; `extract_any_coord`
  é regex pura. Nenhum teste bate na rede real.
- READ-ONLY M1: `git diff src/` toca só `api/maps_geocoder.py` + `dashboard/pages.py`; config.py
  intocado (H3=7, DIST_MIN=1.0, RENDA_MIN=4500.0, renda=0.40/pop=0.60). Caminhos numérico e de
  endereço preservados byte-a-byte; bbox Brasil aplicado a link longo e curto; cascata link antes de
  endereço. Blocos 4–6/basemap intocados. Escopo respeitado (3 arquivos + handoffs).
- Housekeeping `--check` = pré-move (exit 1, esperado); move é responsabilidade do orquestrador.
- Handoff: `context/handoff.md` (+ cópia `context/handoff/20260619-123106-qa.md`).

## Builder (CONCLUÍDO 2026-06-19) — Opção B implementada
- `maps_geocoder.py`: novo helper `resolve_short_link` (urllib puro, segue redirect de link
  curto → URL longa; None em qualquer falha; importável sem rede).
- `pages.py`: helpers `_parece_link`/`_e_link_curto_maps` (módulo, puros) + ramo de link na
  cascata de `render_coord_search_sidebar` (numérico INTOCADO → link Maps NOVO → endereço
  INTOCADO); URL longa offline via `extract_any_coord`, link curto via `resolve_short_link`,
  ambos + `_validate_brazil_bbox`; fallback gracioso por `st.warning`. Título/caption/label/
  placeholder mencionam os 3 formatos; `key="coord_search_input"` preservada.
- `tests/unit/test_coord_search.py`: nova seção (extract_any_coord regex pura, helpers de
  roteamento, resolve_short_link com urllib MOCKADO). Nenhum teste bate na rede real.
- Validações: pytest SERIAL (subconjunto + integração) **252 passed, 0 failed, 0 skipped**
  (xdist `-n auto` abortou com INTERNALERROR de execnet no Python 3.14 — fallback serial
  autorizado, não é bypass); import streamlit_app **ok**; ruff **OK**; mypy **OK**.
- READ-ONLY M1: score/pesos/artefatos/carteira/plano INALTERADOS. Blocos 4–6 intocados.
- Handoff: `context/handoff.md` (+ cópia `context/handoff/20260619-122528-builder.md`).

## Gate humano (2026-06-19) — APROVADO por Vinicius
Plano técnico do Planner APROVADO. Decisão de links curtos = **Opção B** (seguir redirect HTTP
de `maps.app.goo.gl`/`goo.gl/maps` via rede). Emenda à DEC-010 (2026-06-19) JÁ REGISTRADA em
CLAUDE.md §8 antes do Builder. Consequência: `maps_geocoder.py` fica editável (novo helper
`resolve_short_link`). URL longa segue offline (regex). READ-ONLY M1 em ambas as opções.

## Plano técnico do Planner (2026-06-19)
- Handoff completo: `context/handoff.md` (cópia append-only: `context/handoff/20260619-121937-planner.md`).
- Cascata em `render_coord_search_sidebar`: 1) numérico (intocado) → 2) link Maps NOVO (offline,
  `_parece_link` http/https → `extract_any_coord` + `_validate_brazil_bbox`; link curto cai em
  `_e_link_curto_maps` com mensagem clara) → 3) endereço Nominatim (intocado).
- DECISÃO DE GATE pendente: **Opção A** (só URL longa offline, recomendada, sem nova DEC) vs
  **Opção B** (seguir redirect de link curto → exige emenda à DEC-010 + edição de `maps_geocoder.py`).
  O Builder só implementa a opção que o humano aprovar.
- Escopo de edição: `pages.py` (`render_coord_search_sidebar` + 2 helpers + caption) e
  `tests/unit/test_coord_search.py`. READ-ONLY M1; Blocos 4–6 intocados.

## Objetivo
Permitir que a barra de busca principal do dashboard aceite TRÊS formatos de entrada —
(1) coordenada lat,lng, (2) endereço livre e (3) link do Google Maps — resolvendo cada
um para coordenada, sem regressão funcional nem do M1.

## Escopo citado pelo usuário (Vini, 2026-06-19)
> "Eu quero que a opção de busca permita 3 opções de busca: coordenada; endereço; link do maps.
> Coordenada e endereço já são possíveis, mas o link ainda precisa ser incluído."

Foco: adicionar o caminho **link do Maps → coordenada** à busca principal. Coordenada e
endereço já funcionam (BLK-UI-08 / DEC-010) e devem ficar INTOCADOS.

## Pré-investigação do orquestrador (pinagem de arquivos)
- Busca principal: `render_coord_search_sidebar` em `src/motor_expansao/dashboard/pages.py:701`
  (campo `key="coord_search_input"`). Hoje: (1) `parse_coordinate_input` (numérico, intacto);
  (2) `resolve_endereco_http` (endereço → Nominatim, DEC-010). NÃO trata link do Maps.
- Building block JÁ EXISTE: `extract_any_coord(url)` / `extract_place_pin(url)` em
  `src/motor_expansao/api/maps_geocoder.py:71` (regex sobre URL do Maps → coordenada, sem rede).
- Precedente NO PRÓPRIO REPO: a Análise Pontual já usa esse padrão em
  `src/motor_expansao/dashboard/pages.py:3054-3060` (`parse_coordinate_input` → `extract_any_coord`).
- Ponto sensível p/ o Planner: links curtos (`maps.app.goo.gl`, `goo.gl/maps`) NÃO contêm a
  coordenada na própria string → exigem seguir o redirect HTTP para obter a URL final com `!3d/!4d`.
  Isso tensiona o §2 (API ao vivo) — pode reutilizar a cobertura da DEC-010 ou exigir emenda/DEC nova.

## Classificação (Passo 2)
Alta — mexe no dashboard de produção; READ-ONLY sobre M1. A confirmar no Block Orchestrator.

## Tiering de modelo (Passo 4) — Alta
- Block Orchestrator: sonnet
- Planner: opus
- Builder: opus
- QA: opus 4.8 (sempre)

## Branch do ciclo
ciclo/BLK-UI-09 (criada a partir de main @ b0f846e). Inclui commit 571681f (housekeeping
BLK-UI-07 → completed, pedido do Vini antes de iniciar o ciclo).

## Paths pré-sujos (NÃO commitar — alheios ao ciclo)
- data/outputs/setores_censitarios_2022_geo/_metadata.json
- data/reports/relatorio_pontual_censitario_base_geo.md

## Fora de escopo
- score/pesos/artefatos M1; quebrar contratos de performance (carga lazy por UF, render lazy
  de abas, fonte de mapa enxuta — Blocos 4–6); alterar o caminho de coordenada/endereço existente.
