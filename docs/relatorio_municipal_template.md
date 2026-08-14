# Template de referência — Relatório Municipal (BLK-RELMUN-01)

> Transcrição estruturada do template enviado por Vini em 2026-06-22.
> Original (NÃO versionado — anti-PII / convenção §5 de não versionar PDF/PPTX):
> `C:\Users\Vinicius Cruz\Downloads\Template_Relatorio_Municipo.pdf` (+ `.pptx`).
> Este `.md` é a fonte canônica de ESTRUTURA/SEÇÕES para o ciclo; o conteúdo real
> (números) sai do motor censitário/mercado/residual por município. Camada de
> visualização/relatório — **READ-ONLY sobre o M1** (§5 guardrail).

O Relatório Municipal **coexiste** com o Relatório Pontual Censitário (raio 1,0 km),
não o substitui. Unidade de análise = **município inteiro** (selecionado no dashboard);
gerável e baixável após a seleção do município. Estética = a mesma família visual do
template GeoFusion/Ultra (turquesa + magenta + laranja; capa escura com hexágonos).

## Estrutura (10 páginas/slides)

> Fonte de verdade da contagem/ordem: `PDF_SECTION_HEADERS` em
> `src/motor_expansao/dashboard/relatorio_municipal.py` (10 entradas), travada por
> `tests/unit/test_relatorio_municipal.py` (asserts em `/Count 10`). Ao mudar a estrutura,
> atualizar ESTE doc no mesmo PR — a página 2 abaixo ficou 1 mês fora dele (BLK-RELMUN-01-FU1).

### Página 1 — Capa
- Eyebrow: "ANÁLISE DE EXPANSÃO".
- Título: **"Potencial de Entrada de Novas Unidades"**.
- Subtítulo: "Mapeamento competitivo por região — Ultra e espaço disponível para novas academias".
- Rótulo do município: **"Cidade - UF"** (preenchido com o município selecionado).
- Arte: capa escura (roxo/navy) com hexágonos de contorno (magenta/turquesa/laranja) e barras de acento.

### Página 2 — Visão Geral do Município
- Inserida pelo **BLK-RELMUN-01-FU1** (2026-06-23), logo após a capa — é o slide que faltava
  neste doc até 2026-07-27.
- Título da banda: **"Visão Geral do Município - Cidade - UF"**.
- **Mapa** do município INTEIRO (não o recorte das páginas seguintes), distinguindo hexágonos
  **aprovados**, **reprovados** e **fora do município**.
- Bloco **"REGIÕES CONSIDERADAS"**: quantas regiões entram nas páginas seguintes e quantas
  ficaram de fora (`n_aprovados` / `n_hex_municipio` / `n_reprovados`).
- READ-ONLY sobre o M1. Implementação: `_visao_geral_page` em `relatorio_municipal.py`.

### Página 3 — Bairros Oficiais
- Inserida pelo **BLK-RELMUN-06**, logo após a Visão Geral: ancora o território em nomes que o
  time reconhece ANTES de a leitura virar hexágono — mesma posição que o slide ocupa no material
  de referência do time de Expansão (estudo GeoFusion).
- Título da banda: **"Bairros Oficiais - Cidade - UF"**.
- **Mapa** do município INTEIRO com o **limite territorial de cada bairro** (contorno vermelho),
  a divisa do município (contorno preto) e o nome do bairro em placa branca. A área **cinza** é
  a que não tem bairro na base — nunca sai como se fosse divisa oficial.
- Fonte da geometria: setores censitários do **IBGE Censo 2022** (`geometry_wkb`) **dissolvidos**
  por localidade, na mesma cascata `nome_bairro` → `nome_subdistrito` → `nome_distrito` da Página
  7 (`carregar_bairros_geo`). Não depende de dado externo nem de rede.
- Bloco **"BAIRROS IDENTIFICADOS"** (contagem) + painel **"MAIS POPULOSOS (hab.)"** com os 5
  maiores por população do Censo 2022.
- **Cobertura é heterogênea** (ver D9): abaixo de 50% dos setores com bairro/distrito, a página
  troca o subtítulo pela cobertura real e explica que o restante exigiria a malha da prefeitura —
  o número nunca sai sozinho dando a entender que o município inteiro está mapeado.
- READ-ONLY sobre o M1. Implementação: `_bairros_mapa_page` + `_render_mapa_bairros`.

### Página 4 — Resumo da Região (01)
- Título "Cidade - UF" / subtítulo "Potencial de entrada de novas unidades".
- **Mapa** de hexágonos (estilo dashboard) com pins de Ultra e concorrentes; alguns hexágonos
  exibem o número de **vagas/consumo** (ex.: 4.451, 5.061, 4.259, 3.863, 4.371, 4.561, 5.876, 4.651).
  Hexágonos amarelos = espaço disponível.
- Painel lateral **"RESUMO DA REGIÃO"** — tabela `Indicador | Qtd.`:
  - **Unidades Ultra** = XX
  - **Unidades Concorrentes** = XX
  - **Espaço para academias** = XX
- Box **"Como calculamos o espaço"**:
  - "Soma dos hexágonos amarelos ÷ 2.500"
  - `XXXX + XXXX + XXXX + XXXX + XXXX = XXXX`
  - `÷ 2.500 → XX`
- Legenda: "● Ultra".

### Página 5 — Score Censitário (02)
- Subtítulo: "Potencial socioeconômico por célula hexagonal H3".
- **Mapa choropleth** H3 (verde→amarelo→laranja→vermelho) com pins Ultra/concorrentes.
- Legenda (4 faixas): **Alto potencial** (verde), **Médio-alto** (amarelo/âmbar),
  **Médio** (laranja), **Baixo potencial** (vermelho).
- Rodapé: "Fonte: IBGE Censo 2022 · Agregação H3 resolução 7".

### Página 6 — Residual Fitness (03)
- Subtítulo: "Estimativa de mercado ainda não capturado pela concorrência".
- **Mapa** residual (verde/amarelo/vermelho) com pins.
- Painel **"MERCADO DISPONÍVEL"**:
  - Número grande (magenta): **XX.XXX pessoas**.
  - **Hab. totais** ~XXX mil
  - **Renda per capita** R$ X.XXX
  - **Penetração fitness** ~XX,X%
  - Nota de método: "Pop. elegível − alunos com academia cadastrada".

### Página 7 — Expansão de Domínio (04) — mapa + estratégia
- Subtítulo: "Sugestão de posicionamento para cercar e dominar a região".
- **Mapa** com hexágonos numerados por **zona** (1, 2, 3) e pins.
- Painel **"ESTRATÉGIA"** (3 movimentos; rótulos do template — atenção: no template os textos
  de "Cerco" e "Ancora central" aparecem trocados entre as duas páginas, o Planner deve
  normalizar a redação):
  - **1 Cerco** — bairros de alta renda no Centro / hexágonos mais afastados.
  - **2 Flancos laterais** — captura dos hexágonos residuais e consolidação.
  - **3 Ancora central** — hexágonos centrais / posicionamento.
- Rodapé: "Motor de Expansão Ultra · IBGE + OSM".

### Página 8 — Expansão de Domínio (04) — bairros por zona
- Cabeçalho do painel: "Bairros com os melhores números".
- Listas de **bairros agrupadas por zona** (1/2/3/4), ex. (Bauru-SP no template):
  - Zona 1: Parque Roosevelt, Parque Primavera, Jardim Petrópolis, Núcleo 9 de Julho,
    Parque Jaraguá, Jardim Vânia Maria, Jardim Andorfato, Parque Santa Edwirges.
  - Zona 2: Parque Viaduto, Residencial Jardim Jussara, Vila Nipônica, Jardim Ferraz, Jardim Vitória.
  - Zona 3: Jardim Rosa Branca, Vila Pacífico I/II, Vila Industrial, Vila Rocha, Vila São Manoel, Vila Alto Paraíso.
  - Zona 4: Núcleo Hab. Mary Dota, Núcleo Hab. Beija-Flor, Núcleo Hab. Isaura Pitta Garms, Jardim Silvestre II.
- Rodapé: "Motor de Expansão Ultra · IBGE + OSM".

### Página 9 — Síntese — Diagnóstico & Recomendação Estratégica
- 3 cards (acento magenta / turquesa / laranja):
  - **~XX,X% de penetração** → "Mercado com Oportunidade": penetração fitness atual baixa,
    grande espaço para crescimento.
  - **XX.XXX pessoas** → "Residual Significativo": elegíveis sem academia regular,
    concentradas nas bordas/periferia.
  - **3 zonas de atuação** → "Movimento Recomendado": posicionamento periférico (cercar o
    núcleo pelos flancos antes da concorrência; áreas centrais saturadas).
- Rodapé: "Estratégia e Growth · Ultra Academia · Motor de Expansão · 2026".

### Página 10 — Síntese — Espaço e academias
- Eyebrow "SÍNTESE" / título "Espaço e academias".
- 3 big numbers:
  - **XX** Unidades Ultra mapeadas.
  - **XX** Unidades concorrentes mapeadas.
  - **XX** Espaço total p/ novas academias.
- Breakdown de concorrentes por rede (lista "X Concorrente …" + logos: Smart Fit, BF, Allp Fit,
  Bio Ritmo/pin, SkyFit, RedFit, etc. — usar as redes realmente mapeadas no município).
- Método (rodapé): "contagem de pins dentro do território · Espaço = Σ hexágonos amarelos ÷ 2.500".

## Decisões do gate humano (APROVADO por Vinicius, 2026-06-22 — DEC-011) — IMPLEMENTADO

Implementação em `src/motor_expansao/dashboard/relatorio_municipal.py` (módulo NOVO, disjunto;
helpers de layout reimplementados localmente — o Relatório Pontual fica BYTE-A-BYTE intocado).
Expander "Relatório Municipal" em `render_mapa_territorial` (pages.py), habilitado só com
EXATAMENTE 1 município selecionado. READ-ONLY sobre o M1.

- **D1 — hexágono DESTACADO ("amarelo"):** `sam_fitness_potencial >= 3000` **E**
  `oferta_efetiva_disponivel >= 2000` (ambas colunas reais, em alunos; presentes no slice
  enriquecido por UF). **Rótulo sobre cada hexágono destacado** = `oferta_efetiva_disponivel`.
  **"Espaço para academias"** (Páginas 2 e 9) = `round( Σ oferta_efetiva_disponivel dos
  destacados ÷ 2.500 )`. Limiares de DISPLAY locais ao módulo; NÃO mexem em `flag_sam`/DEC-006/
  DEC-007 nem no M1.
- **D2 — zonas (Páginas 6–7):** via `dominio_df` (`plano_expansao_dominio.parquet`) agrupado por
  `cluster_id` do município, ordenado por `residual_total_cluster` desc, cap em 3 zonas. Fallback
  gracioso (sem `dominio_df`/sem o município): Páginas 6–7 em modo simplificado, sem exceção.
- **D3 — mapas COM TILES ONLINE:** `contextily`/EPSG:3857, cache `data/cache/basemap_tiles/`,
  import lazy, fallback offline gracioso (canvas claro SEM ruas), default `basemap=False` em
  CI/teste, atribuição "© OpenStreetMap, © CARTO" no rodapé. (DEC-011 parte 1, estende a DEC-004.)
- **D4 — Mercado disponível / Residual:** `Σ oferta_efetiva_disponivel` do município (alunos).
- **D5 — faixas do Score Censitário:** Alto ≥70 / Médio-alto 50–70 / Médio 30–50 / Baixo <30
  (cores via `RESIDUAL_SCORE_BANDS`/`score_band_to_color`).
- **D6 — pins Ultra/concorrentes:** filtro geográfico por H3 res-7 (pin cai num `hex_id` do
  município; reusa `hex_id_res7` quando presente, senão deriva via `h3`). Anti-PII: só `rede`/contagem.
- **D7 — redação das zonas:** 1 Âncora central / 2 Flancos laterais / 3 Cerco.
- **D8 — Página 9:** breakdown só das redes de concorrentes realmente mapeadas + carimbo de versão
  do contrato no rodapé (`VERSAO_CONTRATO_MUNICIPAL`).
- **D9 — Página 7 (bairros) IMPLEMENTADA (BLK-RELMUN-02):** lista os bairros REAIS agrupados pelas
  3 zonas geométricas (Âncora central / Flancos laterais / Cerco), fonte **IBGE Censo 2022
  `NM_BAIRRO` do setor** (coluna `nome_bairro` agora materializada em
  `data/outputs/setores_censitarios_2022_geo/`). O relatório lê a partição geo do município
  on-demand (`_carregar_bairros_por_hex` → bairro dominante por `hex_id` res-7, por população do
  setor) e agrupa por zona (`_bairros_por_zona`), cap de ~10 bairros/zona + "... e mais N" ao
  truncar. **Cobertura de bairro é HETEROGÊNEA** entre municípios (capitais/grandes têm; muitos
  municípios pequenos e o DF não têm `NM_BAIRRO`). **Fallback gracioso mandatório:** município sem
  bairro mapeado cai nas zonas geométricas + descrição/tese, sem exceção e sem a nota "indisponível"
  como texto principal. READ-ONLY sobre o M1; camada de display (não altera score/artefatos/M1).

## Notas de mapeamento dados → motor (a confirmar pelo Planner)
- "Espaço para academias" = Σ (vagas/consumo dos hexágonos amarelos) ÷ **2.500** (capacidade
  default de unidade já documentada em CLAUDE.md §4: "capacidade default de concorrente/unidade
  proxy: 2500 alunos").
- "Score Censitário" = `score_setor_2022_calibrado` agregado em H3 res 7 (faixas de cor já
  existentes; mapear as 4 faixas do template sobre `RESIDUAL_SCORE_BANDS`/bandas existentes).
- "Residual Fitness / Mercado disponível" = camada residual já existente (`oferta_efetiva_disponivel`
  / `score_oportunidade_residual`; pop elegível − consumo instalado).
- "Expansão de Domínio / zonas / bairros" = camada de domínio híbrido + nomes de bairro/setor.
- "Unidades Ultra / Concorrentes" = contagem de pins (Ultra própria + concorrentes mapeados) dentro
  do território municipal.
- Reusar, onde fizer sentido, `censo_report.py` / `censo_map.py` / `pages.py` e a base geo
  `data/outputs/setores_censitarios_2022_geo/...`, **sem** alterar o Relatório Pontual existente.
