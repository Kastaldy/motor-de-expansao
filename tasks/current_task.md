# Current Task

## Bloco atual

ID: BLK-RELMUN-01
Nome: Relatório Municipal (novo formato, por município selecionado)
Status: aprovado (QA — 2026-06-22; suíte completa 1055 passed / 1 skipped / 0 failed)
Tipo: feature (novo relatório no dashboard; READ-ONLY sobre M1)
Criticidade: Alta (confirmada — Block Orchestrator 2026-06-22)
Esteira: Block Orchestrator → Planner → [REVISÃO HUMANA — gate obrigatório] → Builder → QA (CONCLUÍDO)
Skill atual: QA/Quality Analyzer (CONCLUÍDO — 2026-06-22; VEREDITO APROVADO)
Próxima Skill: Fechamento manual / orquestrador (Passo 6.0 housekeeping_move_block BLK-RELMUN-01 + commit por path)

## Gate humano (APROVADO — Vinicius, 2026-06-22) — decisões D1–D9 TRAVADAS
- **D1 (hexágonos destacados/"amarelos") — AJUSTE DO HUMANO:** hex destacado ⇔
  `sam_fitness_potencial >= 3000` **E** `oferta_efetiva_disponivel >= 2000` (ambas em alunos).
  **Rótulo sobre o hexágono** = `oferta_efetiva_disponivel` (Residual Fitness do hex).
  **Espaço para academias** = `round( Σ oferta_efetiva_disponivel dos hexes destacados ÷ 2500 )`.
  (substitui a recomendação original do Planner para D1.) Registrado em DEC-011 (parte 2).
- **D2:** zonas via `dominio_df` agrupado por `cluster_id` do município; fallback gracioso se vazio.
- **D3 (tiles) — AJUSTE DO HUMANO:** **TILES ONLINE** (fiel ao template), NÃO Pillow puro.
  → registrado em **DEC-011** (parte 1): estende a DEC-004 ao Relatório Municipal, com TODAS as
  mitigações (cache `data/cache/basemap_tiles/`, fallback offline gracioso/canvas claro, import
  lazy de `contextily`, EPSG:3857, atribuição © OSM/© CARTO, default `basemap=False` em CI/teste).
- **D4:** "Mercado disponível"/Residual = `Σ oferta_efetiva_disponivel` do município (alunos).
- **D5:** faixas do Score Censitário: Alto ≥70 / Médio-alto 50–70 / Médio 30–50 / Baixo <30
  (via `RESIDUAL_SCORE_BANDS`).
- **D6:** contagem de pins Ultra/concorrentes por filtro geográfico H3 res-7.
- **D7:** redação normalizada das zonas: 1 Âncora central / 2 Flancos laterais / 3 Cerco.
- **D8:** Página 8 só com as redes de concorrentes realmente mapeadas + carimbo de versão no rodapé.
- **D9:** Página 6 (bairros) SIMPLIFICADA temporariamente (por zona/cluster + nota "bairros
  indisponíveis na base atual"); Vini resolverá a fonte de `NM_BAIRRO` depois.
- DEC criada neste gate: **DEC-011** (CLAUDE.md §8).

## Objetivo
Entregar um relatório consolidado por município (gerável e baixável após selecionar um
município no dashboard), seguindo o template enviado por Vini (8 seções), reaproveitando o
motor censitário/mercado/residual/domínio e a malha real IBGE 2022, sem regressão do
Relatório Pontual Censitário (coexistência) nem do M1.

## Template de referência (recebido 2026-06-22)
- Transcrição canônica: `docs/relatorio_municipal_template.md`.
- Original NÃO versionado (anti-PII): `C:\Users\Vinicius Cruz\Downloads\Template_Relatorio_Municipo.{pdf,pptx}`.
- 8 páginas: (1) Capa "Potencial de Entrada de Novas Unidades" → (2) Resumo da Região
  (Ultra/Concorrentes/Espaço = Σ hex amarelos ÷ 2.500) → (3) Score Censitário (H3 res 7,
  4 faixas) → (4) Residual Fitness (mercado disponível) → (5) Expansão de Domínio (zonas +
  estratégia) → (6) Bairros por zona → (7) Síntese (3 cards) → (8) Espaço e academias (logos).

## Tiering de modelo (Passo 4) — Alta
- Block Orchestrator: sonnet
- Planner: opus
- Builder: opus
- QA: opus 4.8 (sempre)

## Branch do ciclo
ciclo/BLK-RELMUN-01 (criada a partir de main @ a65381f).

## Paths pré-sujos (NÃO commitar — alheios ao ciclo)
- data/outputs/setores_censitarios_2022_geo/_metadata.json
- data/reports/relatorio_pontual_censitario_base_geo.md
- tasks/backlog.md (estado anterior; o ciclo regrava conforme necessário)

## Fora de escopo
- score/pesos/artefatos M1; alterar o Relatório Pontual Censitário existente (coexistência);
  dependência de API ao vivo não aprovada; quebrar contratos de performance do dashboard
  (carga lazy por UF, render lazy de abas, fonte de mapa enxuta — Blocos 4–6).
