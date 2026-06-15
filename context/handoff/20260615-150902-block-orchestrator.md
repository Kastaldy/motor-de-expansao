# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
**BLK-EST-05 — PDF "Apresentação Clássica Ultra" (template GeoFusion) do Relatório Pontual Censitário**

Implementar em produção a variante "Apresentação Clássica Ultra" do PDF do Relatório Pontual
Censitário — estrutura/dados do motor novo (motor censitário) + estética GeoFusion antiga — como
variante em `censo_report.py`, sem alterar o template recente e sem tocar o M1.

## Objetivo
Adicionar `gerar_pdf_relatorio_pontual_classico(...)` (ou equivalente com param `template="classico"`)
em `censo_report.py`, reutilizando o motor real e os helpers existentes, com novo visual de 7 páginas
aprovado por Vini em 2026-06-15, sem alterar `gerar_pdf_relatorio_pontual_censitario` (template recente).

## Escopo permitido

- Adicionar função/classe de variante em `src/motor_expansao/dashboard/censo_report.py`
  (nome sugerido: `gerar_pdf_relatorio_pontual_classico`; alternativa: param `template="classico"`
  em `gerar_pdf_relatorio_pontual_censitario` com rota interna — Planner decide; contanto que
  o caminho `template=None`/padrão seja byte-a-byte inalterado).
- Reutilizar TODOS os helpers existentes: `_UltraPDF`, `_draw_watermark`, `_load_branding_assets`,
  `_ascii`, `_format_number`, `_parece_coordenada`, `_point_rows`, `_safe_len`,
  `_competitors_page` (ou análogo), `_big_numbers_page` (grid READ-ONLY inalterado),
  `_credit_page` (Realização recente, com adição do bloco de link clicável — ver abaixo),
  `_normalize_mapas`/`_normalize_mapas_by_key`. NÃO duplicar lógica já existente.
- Reutilizar motor real: `analisar_ponto_censitario_setores` (censo_point.py — INTOCADO),
  `render_mapas_censitarios_combinados` (censo_map.py — INTOCADO), lookup residual.
- Reutilizar `extract_any_coord` de `src/motor_expansao/api/maps_geocoder.py` (regex pura,
  sem Selenium) para resolver link do Maps → coordenada na capa/Realização.
- Adicionar asset `icone_ultra.png` ao carregamento de branding em `_load_branding_assets`
  (chave `"icone"`; fallback gracioso — None quando ausente).
- Adicionar testes da nova variante (fixtures sintéticas sem PII; nome fictício, sem endereço real).
- `gerar_payloads_download_relatorio_censitario` e `render_downloads_relatorio_censitario` podem
  receber param opcional `template=` para rotear para a variante clássica — Planner decide se
  encapsula ou expõe função separada.

## Fora de escopo

- Alterar `gerar_pdf_relatorio_pontual_censitario` (comportamento recente preservado byte-a-byte
  quando chamado sem o novo param).
- Alterar `analisar_ponto_censitario_setores`, raio 1,5 km, método de interseção (INTOCADOS).
- Alterar `render_mapas_censitarios_combinados` (INTOCADO — a nova variante consome o mesmo dict
  de camadas que o template recente).
- score/pesos/artefatos M1 (READ-ONLY; DEC-001).
- Versionar PDF real ou PII (LGPD; anti-PII §2).
- Dependência de API ao vivo no dashboard de produção (DEC-004; contextily já é lazy+cache).
- Selenium/webdriver no caminho de render do PDF (extract_any_coord é regex pura).
- Selo GO/NO-GO (território BLK-DIM).
- Fotos de imóvel, GeoFusion fluxo/verticalização, POIs OSM.

## Contrato visual das 7 páginas (INALTERÁVEL sem novo gate humano)

Fonte canônica: memória `template-pdf-apresentacao` + backlog BLK-EST-05.

### Parâmetros base
- Formato: 16:9, 960×540 pt; `pdf_version="1.4"`; `set_compression(False)`.
- Cores: turquesa `(0,159,160)` OU asset `(0,167,157)` (Planner decide se usa a constante
  existente `ULTRA_TURQUESA=(0,167,157)` ou define nova — a spec da memória usa `(0,159,160)`;
  delta visual mínimo; Planner deve levantar ao gate humano).
- Magenta `(199,32,120)`, laranja `(237,125,49)`, branco, cinza-texto `(45,45,45)`.

### Assets em `data/ultra/` (gitignored; fallback gracioso obrigatório em todos)
- `relatorio_capa_bg.png` — já existe no carregamento atual (chave `"capa"`).
- `relatorio_conteudo_bg.png` — já existe (chave `"conteudo"`).
- `logo_ultra.png` — já existe (chave `"logo"`); no clássico usa-se SÓ sobre fundo colorido.
- **`icone_ultra.png`** — NOVO; marca ▶ BRANCA, transparente; chave `"icone"` a adicionar em
  `_load_branding_assets`; usado nas bandas turquesa à direita. Fallback: omitir ícone (sem erro).

### Bandas turquesa (cabeçalho das páginas de mapa — páginas 2, 3, 4, 5)
- Margem de **20 px de TODAS as bordas** do slide (NÃO flush como o template recente).
- **TODOS os cantos arredondados**, raio ~16 pt (fpdf2: `pdf.set_line_width(0)` +
  `pdf.rect(..., round_corners=True, corner_radius=16)` ou equivalente).
- Altura ~58 pt.
- Conteúdo: endereço/nome do ponto (branco, esquerda) + ícone Ultra branco (direita, fallback gracioso).
- Título da seção posicionado ABAIXO da banda (não dentro).

### Banda magenta (rodapé de dados — página 6 Big Numbers)
- Full-width, flush com a base; porém com offset de ~13 px para cima (NÃO cobrir marca d'água).
- Diferente das bandas turquesa: sem margem lateral, sem cantos arredondados.

### Marca d'água
- Reusa `_draw_watermark` do template recente BYTE-A-BYTE.
- Capa: cor branca (`_WATERMARK_RGB_COVER`); demais: cinza `_WATERMARK_RGB`.
- Texto: `"Ultra Academia"` ou `"Ultra Academia | {solicitante}"` via `_watermark_text`.

### Estrutura de 7 páginas (ordem canônica)
1. **Capa** — fundo `relatorio_capa_bg.png` (fallback turquesa sólido).
   - Texto branco na zona limpa inferior-direita (x≥478).
   - **Endereço ACIMA** do subtítulo (ordem invertida vs template recente).
   - Linha branca horizontal sólida do asset em ~y 460; texto fica **ACIMA** dela com
     **base do bloco ~5 px acima da linha** (base ≈ y 455).
   - Posicionar por baseline (`pdf.text`), NÃO `cell`.
   - Subtítulo: "Relatorio Pontual Censitario - Raio 1,5 km | {mês/ano}".

2. **População/Densidade** (mapa) — banda turquesa + título abaixo + mapa.

3. **Renda** (mapa) — idem.

4. **Score Censitário** (mapa choropleth com legenda) — idem.

5. **Concorrentes** — mapa à ESQUERDA + LISTA à direita.
   - Lista: nome + distância ao pin, ordenada por distância crescente.
   - "... e mais N" ao truncar (já implementado em `_competitors_page`/`_point_rows`).
   - Ultra listado também.
   - Banda turquesa no topo (com margem/raio do clássico, não a faixa flush do recente).

6. **Big Numbers** — grid 4×2 READ-ONLY (reusa `_big_numbers_page` do template recente).
   - Banda magenta no rodapé (full-width flush-baixo com offset ~13 px).
   - SEM selo de aprovação.
   - As 8 métricas são IDÊNTICAS ao template recente (pop, renda, score médio, score max,
     SAM Fitness, Residual Fitness, concorrentes, consumo concorrentes).

7. **Realização** — reusa `_credit_page` do template recente COM extensão:
   - Adicionar bloco **"Link para localizacao do ponto:"** com o **endereço como link clicável**
     (`pdf.set_link` + `pdf.cell(..., link=url)` onde `url = build_search_url(endereco)`).
   - Data da geração (ex.: "15 de junho de 2026").
   - Atribuição CARTO no rodapé (já existe).
   - SEM logo, SEM cartão de contato (anti-PII).

### Precisão de coordenada / link
- `extract_any_coord(url)` em `src/motor_expansao/api/maps_geocoder.py` — regex pura, sem
  Selenium — extrai lat/lng do link do Maps quando disponível (pino resolvido > centro câmera).
- O LINK da Realização usa `build_search_url(endereco)` com o texto do endereço.
- Os DADOS são calculados na coordenada fornecida (fluxo inalterado do motor).

## Arquivos que devem ser lidos

- `src/motor_expansao/dashboard/censo_report.py` — template recente (LEITURA COMPLETA obrigatória antes de qualquer edição)
- `src/motor_expansao/dashboard/censo_map.py` — `render_mapas_censitarios_combinados` (interface estável)
- `src/motor_expansao/dashboard/censo_point.py` — `analisar_ponto_censitario_setores`, `RAIO_CENSITARIO_DEFAULT_KM` (INTOCADOS)
- `src/motor_expansao/api/maps_geocoder.py` — `extract_any_coord`, `build_search_url` (regex pura)
- `docs/relatorio_pontual_censitario.md` — contrato técnico do relatório
- `tasks/backlog.md` — spec completa do BLK-EST-05 (linhas ~122–188)
- Memória `template-pdf-apresentacao` (já consolidada neste handoff)
- `data/outputs/SIMULACAO_relatorio_caiubi_classico.pdf` (NÃO commitar; referência visual local para o Builder/gate humano)

## Arquivos que podem ser alterados

- `src/motor_expansao/dashboard/censo_report.py` — ÚNICA alteração de produção permitida:
  adicionar nova função/variante e a adição de chave `"icone"` em `_load_branding_assets`.
  O restante do arquivo (incluindo `gerar_pdf_relatorio_pontual_censitario`) deve ser
  preservado byte-a-byte.
- `tests/` — adicionar testes da nova variante (fixtures sintéticas, sem PII).
- Nenhum outro arquivo de produção pode ser alterado.

## Critérios de aceite

1. **Template recente inalterado:** `gerar_pdf_relatorio_pontual_censitario` chamado sem o
   novo param produz byte-a-byte o mesmo PDF. Testes existentes do template recente VERDES.
2. **Nova variante reproduz o contrato visual:** bandas turquesa com margem 20 px e cantos
   arredondados; ícone branco à direita (ou ausência graciosa); capa com endereço acima do
   subtítulo e texto acima da linha branca; concorrentes com mapa+lista de distâncias; Big
   Numbers sem selo; Realização com link clicável no endereço.
3. **Fallback gracioso:** PDF gerado sem erro quando qualquer asset em `data/ultra/` estiver
   ausente (capa turquesa sólida; banda sem ícone; Realização sem logo).
4. **Fixtures sem PII:** nome fictício, coordenada sintética, sem endereço real.
5. **ruff + mypy limpos** (sem novos erros; ruff per-file-ignores existentes preservados).
6. **READ-ONLY M1:** nenhuma escrita em score, carteira, plano ou artefatos oficiais.
7. **Suite full verde:** `pytest -q` sem regressão (baseline atual: 884 passed, 1 skipped).

## Criticidade classificada
**Alta**

Justificativa: caminho de geração do PDF de produção; branding/LGPD; gate visual humano
(Felipe+Vini) obrigatório antes do Builder. READ-ONLY sobre o M1 (não envolve score,
pesos, carteira, plano ou artefatos oficiais — portanto NÃO é Crítica pelo guardrail do BO).

Alerta de guardrail aplicável: "LEITURA/ANÁLISE de score sem escrita em artefato M1 → Alta
(revisão humana antes do Builder)" — interpretação operacional de 2026-05-30 no CLAUDE.md §2.

## Esteira recomendada
Block Orchestrator (este handoff) → **Planner** → `[PARAR: gate visual humano Felipe+Vini]` → Builder (Opus) → QA (Opus)

## Riscos identificados

- **Cor turquesa divergente:** memória usa `(0,159,160)`, constante existente é `(0,167,157)`.
  Delta visual mínimo mas deve ser levantado ao gate humano para decisão explícita (não resolver
  silenciosamente).
- **`_credit_page` compartilhada:** a Realização clássica adiciona o bloco de link clicável;
  o Builder deve criar uma variante (`_credit_page_classico` ou param opcional) sem alterar
  `_credit_page` (usada pelo template recente).
- **Cantos arredondados no fpdf2:** checar a versão disponível do fpdf2 no pyproject.toml
  antes de assumir `round_corners=True`; pode exigir composição manual (rect + arcs).
- **Banda magenta e marca d'água:** offset de ~13 px na banda magenta é estimativa da memória;
  Builder deve calibrar vendo o PDF de simulação local antes de commitar.
- **`icone_ultra.png` não existe no repo:** asset novo; se Felipe/Vini não fornecerem o PNG
  antes do Builder rodar, o fallback gracioso deve ser testado explicitamente.
- **Paths pré-sujos (NÃO commitar):** `data/outputs/setores_censitarios_2022_geo/_metadata.json`,
  `data/reports/relatorio_pontual_censitario_base_geo.md` (alheios) e
  `data/outputs/SIMULACAO_relatorio_caiubi_classico.pdf` (simulação descartável).

## Guardrails ativos

- §2 CLAUDE.md: "anti-PII — .pptx/PDF nunca versionados; cartão de contato image24.png NUNCA
  embutido"; fixtures de teste com nome fictício e coordenada sintética.
- §2 CLAUDE.md: "nao criar dependencia de API ao vivo no dashboard de producao" — a variante
  usa contextily já autorizado por DEC-004 (lazy + cache + fallback offline gracioso).
  `extract_any_coord` é regex pura, sem Selenium — sem dependência de API ao vivo.
- §4/§5 CLAUDE.md guardrail permanente: "visualizacoes, analise radial e interacoes de mapa
  nao podem recalcular ou alterar score_priorizacao, hex_score_estrutural, carteira, plano
  curto prazo, plano dominio ou artefatos oficiais do M1 sem aprovacao explicita."
- DEC-001: pesos/formula/artefatos M1 INALTERADOS.
- DEC-004: basemap tiles autorizados só no caminho de geração do relatório (não na carga do
  dashboard); contextily com cache + fallback offline gracioso.
- BLK-EST-03/FU1: marca d'água reusa `_draw_watermark` e `_watermark_text` exatos do template
  recente (solicitante via param; FU1 para nome real permanece pendente).
