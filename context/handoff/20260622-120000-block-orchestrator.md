# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
**BLK-RELMUN-01 — Relatório Municipal (novo formato, por município selecionado)**

Novo relatório em PDF de 8 páginas, gerável e baixável após a seleção de um município no
dashboard (aba Mapa Territorial), seguindo o template GeoFusion/Ultra enviado por Vini em
2026-06-22. Coexiste com o Relatório Pontual Censitário (raio 1,5 km) — os dois relatórios
NÃO se sobrepõem em unidade de análise nem em código compartilhado (o Pontual usa
`analisar_ponto_censitario_setores` com coordenada; o Municipal usa os dados H3 do município
inteiro já no DataFrame carregado). READ-ONLY sobre o M1.

## Objetivo
Implementar `gerar_pdf_relatorio_municipal(municipio, df, ...)` em novo módulo
`src/motor_expansao/dashboard/relatorio_municipal.py` (e exposição de botão de download
em `pages.py`), gerando as 8 páginas do template sem alterar o Relatório Pontual nem
qualquer artefato/score/peso do M1.

## Escopo permitido
- Criar novo módulo `src/motor_expansao/dashboard/relatorio_municipal.py` com a função de
  geração do PDF municipal (reusa `fpdf2`, já dependência base).
- Criar novos testes em `tests/unit/test_relatorio_municipal.py` (equivalente ao padrão
  de `test_relatorio_pontual_censitario_export.py`).
- Adicionar botão de download do relatório municipal em `pages.py` (função
  `render_mapa_territorial` ou auxiliar nova), disparado após seleção de município.
- Reusar dados já carregados em `df` (slice da UF ativa, colunas `HYBRID_LOAD_COLS` e
  `RESIDUAL_MERCADO_COLS`) — SEM carga nova de parquet.
- Reusar `competitors_df` e `ultra_df` já em escopo em `pages.py` para contagem de pins
  no município.
- Reusar `NM_BAIRRO` da malha geo `data/outputs/setores_censitarios_2022_geo/...` para
  listas de bairros (Página 6) — carregada APENAS SE a base geo municipal já estiver
  disponível (mesmo fallback gracioso do Pontual).
- Reusar constantes de cor/faixa já em `constants.py` (ULTRA_TURQUESA, ULTRA_MAGENTA,
  RESIDUAL_SCORE_BANDS, etc.).
- Reusar `_render_pin_tile` de `competitors.py` para logos na Página 8 (se factível via
  fpdf2; fallback texto).
- Ajustar `tasks/backlog.md` e `tasks/current_task.md` (atualização de estado do bloco).
- Atualizar `docs/relatorio_municipal_template.md` se necessário após o gate (anotações
  de decisão do Planner/Builder).

## Fora de escopo
- Alterar `censo_report.py`, `censo_map.py`, `censo_point.py` além de importações
  passivas (coexistência estrita — o Relatório Pontual segue 100% intocado).
- Alterar `score_priorizacao`, `hex_score_estrutural`, `carteira`, `plano curto prazo`,
  `plano domínio` ou qualquer artefato oficial M1.
- Criar dependência de API ao vivo não aprovada (sem DEC pendente para isso).
- Gerar mapas choropleth com tiles online (DEC-004 cobre apenas o Pontual); o relatório
  municipal usa imagens offline baseadas em `df` filtrado — A CONFIRMAR no gate se tiles
  serão requeridos (se sim, nova DEC será necessária).
- Quebrar os contratos de performance do dashboard: carga lazy por UF (Bloco 4), render
  lazy de abas (Bloco 5), fonte de mapa enxuta (Bloco 6).
- Implementar mapas interativos via pydeck/folium no PDF (imagens estáticas offline via
  Pillow, sem tiles, é o caminho seguro sem nova DEC).
- Versionar o PDF de saída nem o template `.pptx`/`.pdf` original (anti-PII).
- Adicionar nova dependência fora das já disponíveis (`fpdf2`, `Pillow`, `pyproj`,
  `shapely`, `contextily [basemap]`).
- Criar nova tabela/artefato parquet; todo dado vem do `df` já em memória.

## Mapeamento das 8 páginas → fontes de dados (âncoras a confirmar pelo Planner)

| Página | Seção | Fonte principal | Coluna-chave |
|--------|-------|----------------|--------------|
| 1 | Capa | `nome_municipio` + `uf` do filtro ativo | `nome_municipio`, `uf` |
| 2 | Resumo da Região | `df` filtrado por município + `competitors_df` + `ultra_df` | `oferta_efetiva_disponivel`, `faixa_oportunidade` |
| 2 | Espaço (Σ hex amarelos ÷ 2.500) | hexes com `faixa_oportunidade in {alta, prioridade_maxima}` como proxy de "amarelos" — A CONFIRMAR no gate (ambiguidade A1) | `faixa_oportunidade`, `oferta_efetiva_disponivel` |
| 2 | Mapa de hexágonos + pins | imagem offline a partir do `df` filtrado (sem tiles, sem DEC nova) | `lat`, `lng`, `score_setor_2022_calibrado` |
| 3 | Score Censitário (4 faixas) | `score_setor_2022_calibrado` (faixas `RESIDUAL_SCORE_BANDS` já em `constants.py`) | `score_setor_2022_calibrado` |
| 4 | Residual Fitness / Mercado disponível | `oferta_efetiva_disponivel` (soma), `pop_hex_base` (soma), `renda_per_capita` (média), `penetracao_fitness_mercado_estimada` (média) | `oferta_efetiva_disponivel`, `pop_hex_base`, `penetracao_fitness_mercado_estimada` |
| 5 | Expansão de Domínio — mapa + zonas | `score_dominio_hibrido` / clusters H3 adjacentes — A CONFIRMAR se dados de domínio estão em `dominio_df` já em escopo (ambiguidade A3) | `score_dominio_hibrido`, `cluster_id` |
| 6 | Bairros por zona | `NM_BAIRRO` da base geo `setores_censitarios_2022_geo` — A CONFIRMAR disponibilidade (ambiguidade A4) | `NM_BAIRRO` da malha IBGE |
| 7 | Síntese (3 cards) | penetração fitness média, total residual (alunos), número de zonas/clusters | agregados do `df` filtrado |
| 8 | Espaço e academias (logos) | contagem Ultra + breakdown de concorrentes por rede no município | `competitors_df` filtrado por `nome_municipio`, `ultra_df` |

## Ambiguidades para o gate humano (DECISÕES OBRIGATÓRIAS antes de codar)

**A1 — "Hexágonos amarelos" (Página 2):**
O template mostra hexágonos amarelos = "espaço disponível". No sistema, nenhuma coluna
se chama literalmente "amarelo". Hipóteses:
- (a) `faixa_oportunidade in {'alta', 'prioridade_maxima'}` — hexes de alta oportunidade
  segundo a faixa M1 (coluna disponível no `df`).
- (b) `flag_sam == True` — SAM gate (pipeline de mercado).
- (c) `oferta_efetiva_disponivel > 0` — residual positivo.
Humano DEVE escolher uma antes do Builder codificar.

**A2 — Mapa visual nas páginas 2–5:**
O template usa mapas choropleth/hexagonais de alta qualidade (estilo dashboard). Opções:
- (a) Imagem Pillow offline (hexágonos como polígonos raster, sem tiles, sem rede)
  — seguro, sem nova DEC, simples de implementar.
- (b) Tiles CartoDB (mesma abordagem do Pontual via `contextily`) — requer nova DEC ou
  emenda à DEC-004 estendendo cobertura ao relatório municipal.
Humano DEVE escolher antes do Builder. Se (b), o Planner deve incluir a DEC no plano.

**A3 — Zonas de Expansão de Domínio (Páginas 5–6):**
O template usa zonas numeradas (1, 2, 3) com bairros por zona. O pipeline
`gerar_plano_expansao_dominio.py` produz `cluster_id` (clusters H3 adjacentes), mas:
- O `df` do dashboard (`oportunidades_expansao_hibrido.parquet`) NÃO inclui `cluster_id`
  nem `score_dominio_hibrido` diretamente (essas colunas estão em `plano_expansao_dominio.parquet`).
- `dominio_df` (`plano_expansao_dominio.parquet`) é carregado separadamente em `pages.py`.
Humano DEVE decidir: (a) usar `dominio_df` já em escopo para extrair zonas do município;
ou (b) derivar zonas on-demand a partir do `df` principal com lógica equivalente.

**A4 — Bairros por zona (Página 6):**
`NM_BAIRRO` existe na malha SHP (coluna confirmada no contrato), mas NÃO está garantida
nos parquets `setores_censitarios_2022_geo` (o pipeline `materializar_setores_censitarios_geo.py`
materializa colunas mínimas — verificar se `NM_BAIRRO` foi incluído). Se ausente, precisaria
de nova materialização (OPS). Humano DEVE confirmar: (a) aceitar simplificação da Página 6
caso `NM_BAIRRO` não exista nos parquets; ou (b) exigir `NM_BAIRRO` (pode travar até OPS).

**A5 — Ponto de entrada do botão de download no dashboard:**
Onde exatamente fica o botão "Gerar Relatório Municipal"?
- (a) Dentro de `render_mapa_territorial`, abaixo dos filtros de município existentes.
- (b) Novo expander dedicado em `render_mapa_territorial`.
- (c) Aba `Visão Executiva` (onde `build_city_summary` é computado).
Humano DEVE escolher o local UI antes do Builder.

**A6 — Seleção de município no dashboard (hoje):**
Hoje o município é selecionado via multiselect em `render_filter_bar` (coluna `nome_municipio`
de `df`), mas o filtro pode ter zero, um ou mais municípios. O relatório exige EXATAMENTE
um município selecionado. Humano DEVE decidir: (a) o botão só aparece quando exatamente
1 município está selecionado no filtro existente; (b) adicionar seletor dedicado de
município para o relatório (separado do filtro do mapa).

**A7 — Redação das zonas "Cerco" / "Âncora central" (Página 5):**
O template tem os textos trocados entre as duas páginas (anotado em
`docs/relatorio_municipal_template.md` §Página 5). Humano DEVE confirmar a redação
canônica antes de o Builder hardcodar os strings.

**A8 — Redes de concorrentes com logos (Página 8):**
O template lista: Smart Fit, BF, Allp Fit, Bio Ritmo, SkyFit, RedFit. Os logos disponíveis
dependem do `_ICON_CACHE` preloadado no `streamlit_app.py`. Humano DEVE confirmar:
(a) usar apenas as redes realmente mapeadas no município (coluna `rede` de `competitors_df`
filtrado), com fallback para sigla textual quando logo ausente; ou (b) listar apenas as
redes com logo disponível. Opção (a) é o comportamento atual do Pontual e o mais robusto.

## Arquivos que devem ser lidos

- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\docs\relatorio_municipal_template.md`
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\docs\relatorio_pontual_censitario.md`
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\src\motor_expansao\dashboard\censo_report.py`
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\src\motor_expansao\dashboard\censo_map.py`
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\src\motor_expansao\dashboard\censo_point.py`
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\src\motor_expansao\dashboard\pages.py`
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\src\motor_expansao\dashboard\constants.py`
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\src\motor_expansao\dashboard\data.py`
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\src\motor_expansao\dashboard\competitors.py`
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\src\motor_expansao\pipelines\gerar_plano_expansao_dominio.py`
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\jobs\pipelines\materializar_setores_censitarios_geo.py`
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\tasks\backlog.md`
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\tests\unit\test_relatorio_pontual_censitario_export.py`
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\streamlit_app.py`

## Arquivos que podem ser alterados

**Novos (a criar):**
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\src\motor_expansao\dashboard\relatorio_municipal.py`
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\tests\unit\test_relatorio_municipal.py`

**Existentes (toques pontuais mínimos):**
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\src\motor_expansao\dashboard\pages.py`
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\tasks\backlog.md`
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\tasks\current_task.md`

**INTOCADOS (guardrail absoluto):**
- `src/motor_expansao/dashboard/censo_report.py`
- `src/motor_expansao/dashboard/censo_map.py`
- `src/motor_expansao/dashboard/censo_point.py`
- `src/motor_expansao/pipelines/m1/` (qualquer arquivo)
- `config.py`
- Artefatos M1 oficiais em `data/staging/brasil_*.parquet`, `data/outputs/hexagonos_*.parquet`

## Critérios de aceite

- CA1: PDF municipal gerado com as 8 seções do template, baixável como `.pdf`.
- CA2: Relatório Pontual Censitário segue 100% intocado: `render_relatorio_pontual_censitario` funciona exatamente como antes; `censo_report.py`/`censo_map.py`/`censo_point.py` sem nenhuma alteração.
- CA3: Nenhum recálculo de `score_priorizacao`, `hex_score_estrutural`, carteira, plano ou artefato M1 (READ-ONLY estrito).
- CA4: Suite `pytest -q` verde após as alterações (sem regressão em nenhum teste existente).
- CA5: Botão de download só aparece quando o contexto municipal está definido (município único selecionado — conforme decisão da ambiguidade A6).
- CA6: Fallback gracioso sem a base geo municipal: PDF gerado sem listagem de bairros (Página 6 simplificada ou omitida), sem exceção.
- CA7: Anti-PII: o PDF gerado não embute `image24.png` nem qualquer dado pessoal.
- CA8: Fallback sem assets de branding (`relatorio_capa_bg.png` ausente): cores sólidas Ultra sem exceção.
- CA9: Ambiguidades A1–A8 respondidas pelo humano no gate antes do Builder codificar.
- CA10: `ruff` e `mypy` passando sem erros novos.

## Criticidade classificada
**Alta**

Justificativa: novo relatório no dashboard de produção (adiciona arquivo novo + toque pontual
em `pages.py`), READ-ONLY sobre o M1 — não toca `score_priorizacao`, pesos, carteira, plano
ou artefatos oficiais. Não há nova camada de score nem escrita em parquets.

## Esteira recomendada
Block Orchestrator (concluído) → **Planner** → [REVISÃO HUMANA — gate obrigatório: resolver
ambiguidades A1–A8 antes de qualquer código] → Builder → QA

## Riscos identificados

- R1: **"Hexágonos amarelos" mal definidos (A1)** — proxy errada distorce o número central da Página 2; gate obrigatório.
- R2: **Mapas sem tiles (A2)** — mapas Pillow offline serão menos ricos que o template; se tiles exigidos, nova DEC obrigatória antes de codar.
- R3: **`NM_BAIRRO` ausente nos parquets geo (A4)** — Página 6 pode ficar sem dados de bairro; exigiria OPS ou simplificação.
- R4: **Zonas de Domínio dependem de `dominio_df` (A3)** — se `dominio_df` não estiver carregado para o município, Páginas 5–6 ficam sem dado de zona.
- R5: **Performance** — filtrar por município e gerar PDF em `df` de até ~60k hexes (SP) deve ficar abaixo de ~5 s; Planner deve confirmar.
- R6: **Acoplamento com internals do Pontual** — importar funções com `_` prefixado de `censo_report.py` cria fragilidade; novo módulo deve reimplementar ou usar só a API pública.
- R7: **Logos de concorrentes** — `_ICON_CACHE` vazio em testes unitários; testes devem mockar ou usar fallback de sigla.

## Guardrails ativos

- §2 (CLAUDE.md): tiles online no relatório municipal exigem nova DEC antes de codificar.
- §5 (CLAUDE.md): visualizações/relatórios NÃO podem recalcular ou alterar artefatos M1.
- §3 (CLAUDE.md): parâmetros canônicos M1 INALTERADOS.
- Blocos 4–6 de performance do dashboard: PRESERVADOS integralmente.
- Anti-PII: `image24.png` nunca embutida; PDF de saída nunca versionado.
