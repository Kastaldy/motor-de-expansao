# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner (criticidade Alta + desvio de guardrail "sem API ao vivo" → Planner formaliza a DEC dos tiles e
leva ao gate humano ANTES do Builder).

## Bloco refinado
**BLK-CENSO-01 — Relatório Pontual Censitário: camadas combinadas + fundo de ruas + faixas GeoFusion + pins com logo.**

Repaginação da feature já existente (Relatório Pontual Censitário 1.5 km), READ-ONLY sobre M1.
Hoje o relatório (`render_relatorio_pontual_censitario`, `pages.py:2479`) gera 1 PDF, mas o mapa mostra
**só 1 métrica por vez** (selectbox pop/renda/score/peso), desenhado 100% offline com Pillow em
`render_mapa_censitario_estatico_png` (`censo_map.py:245`) **sem fundo de ruas**, com cores por **quartil**
(`_build_breaks`, `censo_map.py:75`) e símbolos genéricos (círculo laranja=concorrente, quadrado vermelho=
Ultra, círculo azul com cruz=ponto central) **sem logo**. O objetivo é entregar UMA exportação (UI e PDF)
com renda + população + concorrentes juntos, fundo de ruas branco/claro via tiles online só na geração
(cache + fallback offline), faixas de cor absolutas estilo GeoFusion e pins com logo.

> Decisões de produto JÁ aprovadas por Felipe em 2026-06-05 (ver bloco no `tasks/backlog.md`, linhas ~64-158).
> O que falta é o Planner formalizar a **DEC dos tiles online** e detalhar a engenharia.

## Objetivo
Entregar uma única geração do Relatório Pontual Censitário com renda + população + concorrentes juntos
(UI e PDF), fundo de ruas branco/claro por tiles online só na geração (cache + fallback offline gracioso),
faixas de cor absolutas fixas por camada (estilo GeoFusion) e pins com logo (Ultra + concorrentes), sem
tocar M1/score.

## Escopo permitido
- **Camadas combinadas:** uma geração apresenta (UI **e** PDF) Renda + População/Densidade + Concorrentes
  (pins) no raio 1.5 km, sem trocar dropdown nem baixar vários PDFs. O Planner decide a forma: 3 mapas
  (1 por camada) **ou** 1 mapa-base + variações de choropleth; critério = "uma exportação só resolve".
- **Fundo de ruas = tiles online SÓ na geração**, basemap claro/BRANCO (ex.: Carto Positron/Light "no
  labels", via `contextily`/provedor OSM/Carto), com **cache local** de tiles e **fallback offline
  gracioso** (sem internet/tiles → canvas branco sem ruas, sem quebrar). A dependência fica restrita ao
  caminho de geração do relatório, NÃO à carga do dashboard.
- **Faixas absolutas fixas por camada (não quartil), cores definidas, transparentes** o bastante para ver
  as ruas; cortes e cores canônicos centralizados em constantes; comparáveis entre pontos:
  - **População/Densidade:** rampa de vermelhos estilo GeoFusion por hab/km², cortes fixos de referência:
    até 1.000 / 1.001–5.000 / 5.001–10.000 / 10.001–25.000 / >25.000 hab/km².
  - **Renda:** rampa estilo GeoFusion **adaptada a renda PER CAPITA** (o Planner recalibra os cortes/classes
    para escala per capita — NÃO copiar os valores A/B/C do Geo, que são de renda domiciliar; só o estilo).
  - **Score censitário:** manter o padrão do projeto `RESIDUAL_SCORE_BANDS`/`score_band_to_color`
    (`dashboard/constants.py:302` e `dashboard/utils.py:35`).
- **Pins com logo:** substituir os círculos/quadrados pelos logos já existentes (Ultra + concorrentes),
  reaproveitando `preload_logos`/brand colors (`competitors.py:203`); embutir as imagens de logo no PNG
  Pillow (ponto central, concorrentes, Ultra distinguíveis).
- **Arquivos:** editar `censo_map.py` (tiles + faixas fixas + pins logo), `pages.py` (UI camadas combinadas),
  `censo_report.py` (embutir os mapas combinados no PDF). Adicionar dependência de basemap/tiles
  (ex.: `contextily`) em `pyproject`/extras + cache local de tiles.
- **Testes:** atualizar os 3 unit (`tests/unit/test_relatorio_pontual_censitario_{motor,mapa,export}.py` —
  10 testes hoje: 5+2+3) e `tests/integration/test_streamlit_app.py` para o novo visual; cobrir o
  **fallback offline** (sem tiles) e a presença das 3 camadas no PDF.
- **Docs:** atualizar `docs/relatorio_pontual_censitario.md` §6/§7 e a linha do relatório no `CLAUDE.md` §4
  (tiles + faixas + pins); **registrar a DEC dos tiles no CLAUDE.md §8**.

## Fora de escopo (invioláveis)
- Qualquer recálculo/escrita de M1 (`scoring.py`/`constants.py` M1/pesos/artefatos oficiais) — é visualização.
- Mudar o método de interseção `setor_censitario_intersecao_area_1p5km` (`censo_point.py:145`) ou o raio
  fixo de 1.5 km.
- Tornar o **dashboard interativo** dependente de internet — o desvio de tiles é **só no caminho de geração
  do relatório**.
- Template/diagramação final do PDF — isso é o **BLK-CENSO-02** (fase 2). Aqui só a função
  (camadas/mapas/faixas/pins), não o layout/branding/estrutura de slides do PDF.
- O PDF de referência real `data/referencias/Av. Wesley Dias Rodrigues, 1385 - Hortolândia, SP.pdf`
  (contém PII) é insumo do BLK-CENSO-02; **não usar/versionar aqui** (`data/referencias/` está untracked).

## Arquivos que devem ser lidos
- `CLAUDE.md` (§1 papéis das camadas; §2 guardrail "não criar dependência de API ao vivo no dashboard";
  §5 guardrail READ-ONLY M1; §8 DECs e modelo de DEC).
- `tasks/backlog.md` (bloco BLK-CENSO-01, linhas ~64-158 — decisões de produto aprovadas, escopo, aceite, risco).
- `docs/relatorio_pontual_censitario.md` (contrato atual §6 mapa, §7 export, §5 método de interseção).
- `src/motor_expansao/dashboard/pages.py:2479` (`render_relatorio_pontual_censitario`; selectbox de métrica
  ~2528-2540; chamada do PNG ~2550; downloads ~2585).
- `src/motor_expansao/dashboard/censo_map.py` (`render_mapa_censitario_estatico_png`:245; `_build_breaks`:75
  quartil; `_SECTOR_PALETTE`:31; `_color_for_value`:65; `_draw_legend`:141; pins desenhados ~354-364).
- `src/motor_expansao/dashboard/censo_point.py:145` (`analisar_ponto_censitario_setores` — já devolve
  `concorrentes_raio`/`ultra_raio`, renda, pop, densidade, setores; NÃO alterar o método nem o raio).
- `src/motor_expansao/dashboard/censo_report.py` (`gerar_csv_setores_censitarios`:62;
  `gerar_pdf_relatorio_pontual_censitario`:306, recebe `mapa_png_bytes`; `render_downloads_relatorio_censitario`:334).
- `src/motor_expansao/dashboard/competitors.py` (`preload_logos`:203; `_png_icon_data`:190;
  `COMPETITOR_BRANDS`:83; `COMPETITOR_SPECS`/logo files).
- `src/motor_expansao/dashboard/constants.py:302` (`RESIDUAL_SCORE_BANDS`) e `dashboard/utils.py:35`
  (`score_band_to_color`) — paleta canônica do score.
- `pyproject.toml` (dependências/`[project.optional-dependencies]`; `pillow` já presente em deps base).
- Logos reais: `concorrentes/logo_*.png` (ex.: `logo_live_academia.png`, `logo_bioritmo.png`,
  `logo_alphafitness.png`, etc.) e `data/ultra/logo_ultra.png`. (Ignorar as cópias em `tmp_codex_runtime/`.)

## Arquivos que podem ser alterados
- `src/motor_expansao/dashboard/censo_map.py`
- `src/motor_expansao/dashboard/pages.py` (apenas `render_relatorio_pontual_censitario` e helpers do relatório)
- `src/motor_expansao/dashboard/censo_report.py`
- `src/motor_expansao/dashboard/competitors.py` (apenas reúso/expor logos para o PNG; sem mudar bases)
- `src/motor_expansao/dashboard/constants.py` (apenas ADIÇÃO das constantes de faixas/cores das novas
  camadas pop/renda; não mexer em parâmetros M1)
- `pyproject.toml` (adicionar dependência de basemap/tiles + cache; preferir um extra dedicado para não
  pesar o deploy base)
- `tests/unit/test_relatorio_pontual_censitario_motor.py`
- `tests/unit/test_relatorio_pontual_censitario_mapa.py`
- `tests/unit/test_relatorio_pontual_censitario_export.py`
- `tests/integration/test_streamlit_app.py`
- `docs/relatorio_pontual_censitario.md`
- `CLAUDE.md` (§4 linha do relatório + nova DEC em §8)

## Critérios de aceite
- Uma única geração entrega **renda + população + concorrentes** (UI e PDF), sem múltiplos downloads.
- Mapas com **fundo de ruas branco/claro** quando há tiles; **fallback offline** gera mapa sobre canvas
  branco sem ruas, **sem quebrar** (testado explicitamente).
- Faixas de cor **absolutas fixas com paleta própria por camada** (pop = vermelhos estilo Geo; renda =
  estilo Geo adaptado a renda PER CAPITA; score = `RESIDUAL_SCORE_BANDS`), **transparentes** o bastante
  para ver as ruas; legenda condizente com cada camada.
- **Pins com logo** de Ultra e concorrentes (sem os círculos/quadrados antigos); ponto central distinguível.
- Suite verde (`pytest -n auto`), ruff+mypy limpos, smoke `import streamlit_app` ok.
- **DEC dos tiles registrada** no CLAUDE.md §8; docs (`relatorio_pontual_censitario.md` §6/§7 + CLAUDE.md §4)
  atualizados.
- **ZERO** mudança em `score_priorizacao`/`hex_score_estrutural`/carteira/plano/artefatos oficiais do M1.

## Criticidade classificada
**Alta.** Toca o guardrail "não criar dependência de API ao vivo no dashboard de produção" (tiles online na
geração) → exige DEC + gate humano. É READ-ONLY sobre M1/score. NÃO rebaixar abaixo de Alta. Se o Planner/
Builder encontrar qualquer toque em `score_priorizacao`/`hex_score_estrutural`/carteira/plano/artefatos M1,
**ELEVAR para Crítica** e alertar (não deveria ocorrer — é camada de visualização).

## Esteira recomendada
Block Orchestrator → **Planner** → `[REVISÃO HUMANA + DEC sobre tiles online]` → Builder → QA.

## ALERTA AO PLANNER — DEC obrigatória
O Planner **DEVE** formalizar a **DEC dos tiles online** (formato das DEC-001..003 do CLAUDE.md §8) para o
gate humano, ANTES do Builder. A DEC deve registrar: (a) que se desvia do guardrail "sem API ao vivo"
restrito ao caminho de geração do relatório; (b) provedor/licença de tiles escolhido (basemap claro/branco,
ex.: Carto Positron/Light "no labels"); (c) mitigações: cache local de tiles + fallback offline gracioso +
dependência fora da carga do dashboard; (d) que pesos/fórmula/artefatos do M1 ficam INALTERADOS. Sem essa
DEC aprovada por Felipe, o Builder não inicia.

## Riscos identificados
- **Tiles — rate-limit/licença:** provedor OSM/Carto tem limites de uso e termos de atribuição; escolher
  provedor de basemap claro com licença compatível e respeitar atribuição/limite (parte da DEC).
- **Reprojeção tiles × CRS métrico local:** o buffer de 1.5 km e os setores são desenhados num CRS métrico
  azimutal local centrado no ponto (`_local_metric_crs`, `censo_point.py`); tiles web vêm em Web Mercator
  (EPSG:3857). Casar a projeção/alinhamento tile↔polígonos sem distorcer o círculo de 1.5 km é o ponto
  técnico mais delicado; o Planner deve definir a estratégia (ex.: render via Mercator com reprojeção dos
  setores, ou warp dos tiles para o CRS local).
- **Peso do cache de tiles:** cache local pode crescer; definir diretório/limite/limpeza e não versionar.
- **Fallback offline:** CI e ambiente de teste rodam sem internet — o caminho sem tiles tem de ser o
  default seguro e estar coberto por teste, senão a suite quebra de forma intermitente.
- **Regressão dos 10 testes existentes:** todos referenciam paleta de quartil, símbolos atuais e mapa de
  1 métrica; serão reescritos — risco de perder cobertura de estados-vazios/sem-concorrentes se não migrar
  com cuidado.
- **Inchaço da dependência base:** `contextily` puxa árvore geoespacial; preferir extra dedicado para não
  pesar a imagem de produção do dashboard.
- **Performance da geração:** baixar/compor tiles + 3 camadas pode encarecer a geração do relatório; manter
  sob demanda e cacheado.

## Guardrails ativos (do CLAUDE.md)
- §2: "Não criar dependência de API ao vivo no dashboard de produção." → desvio permitido SÓ na geração do
  relatório, via DEC + gate humano, com cache + fallback offline.
- §5 (permanente): "visualizações, análise radial e interações de mapa não podem recalcular ou alterar
  `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano domínio ou artefatos
  oficiais do M1 sem aprovação explícita."
- §2 (criticidade de score): LEITURA/ANÁLISE de score sem escrita em artefato M1 → Alta. ALTERAÇÃO de
  fórmula/pesos/artefato M1 → Crítica + DEC. (Este bloco é visualização → Alta; não deve escrever score.)
- §1: M1 é camada EXECUTIVA; censitário (`score_setor_2022_calibrado`) é a camada operacional — este
  relatório é da camada censitária/visualização, paralelo ao M1.
- §6: nenhum comando no VPS sem confirmação individual (não há ação de VPS neste bloco).
