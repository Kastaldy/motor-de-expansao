# Plano — Piloto Web App do Motor de Expansão (substituição do Streamlit)

> Documento de handoff para desenvolvimento. Objetivo: construir um piloto web app que
> reorganiza a plataforma em torno da **narrativa analítica** (potencial → residual →
> concorrência → recomendação) e, se validado, substitui o dashboard Streamlit atual.
>
> Referência visual: `Motor de Expansão - Referência (standalone).html` (raiz do repo; telas Mapa e
> Viabilidade em HTML/CSS/JS puro, interativas — abra no navegador e inspecione o CSS real). **Atenção:**
> é uma **spec visual**, não um app funcional — o mapa ali é FALSO (hexágonos em CSS, dados mockados,
> zero fetch); no app vira `H3HexagonLayer` deck.gl sobre dados reais.
>
> Este documento é **subordinado ao `CLAUDE.md`** do repo. Em qualquer conflito de
> parâmetros/guardrails, o `CLAUDE.md` prevalece. Nada aqui altera score, pesos ou artefatos M1.

---

## 0. Estado real do repositório (reality check — varredura de código 2026-07-19)

> Adicionada para alinhar o plano ao que **já existe** no repo. Onde o texto original divergiu de
> nomes/fatos reais, o correto está aqui e **vale sobre o resto do documento**. Backlog operacional
> desta migração: **epic BLK-WEB** em `tasks/backlog.md` (11 blocos, 01–11).

**A premissa central está confirmada:** o motor está desacoplado — a camada de compute é **100% livre de
Streamlit** (`data.py`, `competitors.py`, `censo_point.py`, `censo_map.py`, `censo_report.py`,
`relatorio_municipal.py`, `viabilidade_charts.py`, `dimensionamento/*`, `constants.py`, `utils.py`). O
acoplamento a `st.*` vive só em `streamlit_app.py` (704 LOC), `pages.py` (4908 LOC) e `components.py`. A
migração é de **apresentação**, não de sistema — risco de M1 = zero (tudo read-only).

**O que muda o custo (a favor):**
1. **Já existe uma API FastAPI production-grade E LIVE** — `src/motor_expansao/api/` (~2432 LOC), no ar em
   `api.ultra-expansao.tech`. Tem factory, **auth Bearer token→consumidor**, CORS, erro `{detail,codigo}`,
   settings, versionamento, `Dockerfile.api`, `docker-compose.prod.yml`, **publish por digest no GHCR** e bot
   Telegram. **A "Fase 0" NÃO é greenfield — ela ESTENDE essa API.** Hoje há 5 endpoints; **`/ponto/censitario`
   já existe** como `POST /api/v1/analisar`; **`/ufs` já existe** (mas aponta para a base de mercado — repontar).
   Dos 14 endpoints do §6, ~10 são **wrap fino de função pura** já existente; só 2 têm trabalho real:
   **`GET /uf/{uf}`** (serializar slice + filtros + caps) e **`POST /viabilidade`** (schema + série + DRE).
2. **O basemap MapLibre já está self-hosted** — `tileserver-gl` (OpenMapTiles) roteado por Caddy em `/tiles/`
   same-origin (`docker-compose.yml` + `caddy/tiles.Caddyfile`). A parte mais dura de um SPA de mapa está
   resolvida; o "CARTO dark" do §5 pode virar este basemap próprio.
3. **Já houve um spike deck.gl** — `src/motor_expansao/dashboard/ui_spike_deckgl.py` (810 LOC). Ativo de referência.
4. **Os relatórios já são server-side puros** (`censo_report.py`→bytes, `gerar_excel_viabilidade`→bytes,
   `relatorio_municipal.py`, `montar_payload_viabilidade`) → viram **endpoint de download, NÃO componente React**.

**O que exige decisão (contra a suposição do plano):**
- **Auth.** O §3 assume "Authelia (já existe)" na frente. A API LIVE hoje usa **Bearer token por consumidor**,
  sem Authelia, e **sem porta no host** (inalcançável pelo browser); `API_CORS_ORIGINS` é curinga. Para o web
  app interno o caminho limpo é **Authelia same-origin** (como o `/tiles/`) + CORS restrito. **A API pública não
  deve ganhar endpoints de dados de dashboard sem gate (LGPD).** — decidido no **BLK-WEB-10**.

**Nomenclatura (plano → repo real):** vários loaders citados abaixo (`load_uf_catalog`, `load_uf_slice`,
`load_carteira`, `load_plano`, `load_plano_dominio`, `load_base_calibracao`) são **wrappers `@st.cache_*` em
`streamlit_app.py`**; os equivalentes puros que a API deve importar são `list_partitioned_ufs` /
`read_enriched_uf_partition` (`data.py:65,82`), `carregar_base_calibracao`, `analisar_viabilidade_ponto`
(`dimensionamento/viabilidade_ponto.py:318`) e `pd.read_parquet` direto dos artefatos (carteira/plano/domínio).
As tabelas do §6 abaixo já foram corrigidas para os nomes reais.

**Estimativa (recalibrada para o modo de trabalho real — Felipe + Claude, agêntico, portando spec conhecida
sobre back pronto):** o piloto é **semanas, não meses**. O back é barato (fundação e engine prontos, wraps
mecânicos); o custo real é o **frontend React**, e nele os dois **marca-passos** são (a) o **mapa deck.gl**
(`H3HexagonLayer` + interações + perf de ~35k hexes) e (b) a **paridade byte-a-byte** (correção iterativa, não
geração). O resto das telas é port do mesmo padrão.

**Realidade de LOC:** dashboard 19.105 LOC (mas ~4,3k são geradores de PDF que viram backend); API 2.432 LOC;
engine de viabilidade 470 LOC.

---

## 1. Objetivo e critério de sucesso do piloto

**Problema atual:** o dashboard Streamlit empilha tudo num scroll vertical único (banner →
filtros → 5 abas). Fica poluído e difícil para o analista júnior e para o executivo se
localizarem.

**Meta do piloto:** provar que um web app dedicado entrega a mesma inteligência com muito
menos atrito, organizado por **perguntas do usuário** e não por recursos.

**Critérios de sucesso (validar antes de aposentar o Streamlit):**
1. Um analista júnior chega à recomendação de expansão de uma UF em < 60s, sem treino.
2. As telas Mapa e Viabilidade cobrem 100% dos dados que as abas equivalentes mostram hoje.
3. Paridade numérica: todo número exibido bate byte-a-byte com o Streamlit (mesmos Parquets).
4. Performance de carga por UF ≤ a do Streamlit atual (baseline em `data/reports/perf_baseline_dashboard.md`).
5. Zero recálculo de score no front/back (guardrail permanente preservado).

---

## 2. Por que sair do Streamlit (resumo)

Streamlit renderiza widgets num fluxo vertical — é a causa estrutural da poluição. O layout
do protótipo (mapa full-bleed, painéis de vidro flutuantes, stepper de narrativa, régua de
equilíbrio, uma decisão por tela) **não é alcançável** em Streamlit puro sem lutar contra o
framework. A migração é de **camada de apresentação**, não de sistema — o motor já está
desacoplado (ver §3).

---

## 3. Arquitetura alvo

```
┌─────────────────────────────────────────────────────────────────┐
│  MOTOR PYTHON (INTOCADO)                                          │
│  src/motor_expansao/  →  scoring M1, hibrido, censo, residual,   │
│  dominio, viabilidade  →  escreve Parquets em data/outputs/      │
└───────────────────────────┬─────────────────────────────────────┘
                            │  (read-only)
┌───────────────────────────▼─────────────────────────────────────┐
│  API FastAPI (NOVA, fina, read-only)                             │
│  embrulha os loaders/funções puras já existentes em endpoints    │
│  JSON. Cache por UF. Sem lógica de negócio nova.                 │
└───────────────────────────┬─────────────────────────────────────┘
                            │  HTTP/JSON
┌───────────────────────────▼─────────────────────────────────────┐
│  FRONTEND (NOVO)  React + deck.gl (mapa H3) + MapLibre basemap   │
│  As 5 áreas viram telas; layout do protótipo.                    │
└──────────────────────────────────────────────────────────────────┘
Auth: DECISAO do BLK-WEB-10 (a API LIVE hoje usa Bearer/consumidor, sem Authelia; para o web app
interno -> Authelia same-origin como o /tiles/ + CORS restrito). Deploy: Docker/VPS (ja existe).
Basemap: tileserver-gl proprio em /tiles/ (ja self-hosted). Roda EM PARALELO ao Streamlit.
```

**Princípio-chave:** o pipeline de dados/scoring não muda. A API só lê os Parquets que o
motor já gera. O guardrail "nada recalcula o score" fica garantido por construção — a API é
read-only.

---

## 4. Escopo do piloto (incremental, em paralelo)

| Fase | Entrega | Depende de | Roda ao lado do Streamlit? |
| --- | --- | --- | --- |
| **0** | API FastAPI: catálogo de UFs + slice por UF + overlays (concorrentes/Ultra) | Parquets existentes | sim |
| **1** | Tela **Mapa** (3a): narrativa em 4 camadas + deck.gl | Fase 0 | sim |
| **2** | Tela **Viabilidade** (4a): régua de equilíbrio + DRE + relatório | Fase 0 + endpoint de viabilidade | sim |
| **3** | Telas Executivo, Expansão de Domínio, Carteira e Plano | Fases 0–2 | sim |
| **4** | Corte: substitui o Streamlit quando os critérios da §1 baterem | Fase 3 | — |

Comece por **Fase 0 + Fase 1**. Se o Mapa convencer, o resto é repetição do mesmo padrão.

---

## 5. Stack recomendada

**Backend**
- FastAPI + Uvicorn.
- pandas / pyarrow (já no projeto) para ler Parquets. Reaproveitar `data.py` e os loaders.
- Cache: `functools.lru_cache` por UF (espelha os `@st.cache_resource`/`@st.cache_data` atuais).
- Geração de PDF/Excel: manter as funções server-side existentes, expor como endpoint de download.

**Frontend**
- **React** + **TypeScript** + **Vite**.
- **deck.gl** (`@deck.gl/react`, `@deck.gl/geo-layers` → `H3HexagonLayer`, `IconLayer`) — porta direta do pydeck atual.
- **MapLibre GL** como basemap escuro (equivale ao CARTO dark que vocês já usam).
- **@tanstack/react-query** para fetch/cache dos endpoints.
- Estado de UI local (camada ativa, demanda) com `useState`/`zustand` — sem Redux.
- Zero framework de CSS pesado; **inline styles / CSS Modules** com os tokens da §7.
- Charts (Viabilidade): `visx` ou SVG puro (a régua e o DRE do protótipo são SVG/flex simples).

**Infra:** Docker (frontend estático servido por nginx + API atrás do Authelia). Deploy git-pull na VPS como hoje.

---

## 6. Contrato de dados por tela (endpoint ↔ função atual ↔ Parquet)

> Regra geral: cada endpoint apenas **lê e serializa** o que os loaders/funções já produzem.
> Nomes de colunas e semântica são os do `docs/streamlit_dashboard_m1.md` e `CLAUDE.md §3`.

### 6.1 Base / filtros
| Endpoint | Reaproveita | Fonte |
| --- | --- | --- |
| `GET /ufs` | `list_partitioned_ufs` (`data.py:65`) | partições `uf=XX` de `hexagonos_dashboard_enriquecido/` (hoje `/ufs` existe apontando p/ base de mercado — **repontar**) |
| `GET /uf/{uf}` (slice de hexes + filtros server-side) | `read_enriched_uf_partition` (`data.py:82`) + `apply_global_filters` (`data.py:477`) | `hexagonos_dashboard_enriquecido/uf=XX/` (fallback M1) |
| `GET /uf/{uf}/municipios` | `list_censo_geo_municipios` (`data.py:130`) | `setores_censitarios_2022_geo/uf=XX/` |

Query params de `/uf/{uf}`: `municipios[]`, `faixas[]`, `elegibilidade_hibrida[]`,
`cobertura[]`, `qualidade[]`, `only_top_municipio`, `only_top_hex_intraurbano`
(mesma assinatura de `apply_global_filters`).

Resposta: hexes com `hex_id`, centróide (lat/lng), e os scores por modo de cor:
`score_priorizacao` (M1), `score_setor_2022_calibrado` (censitário),
`score_expansao_hibrido` (híbrido), `score_oportunidade_residual` (residual),
`faixa_oportunidade`, `pop_total_setor_2022`/`populacao_proxy`, flags (`flag_baixa_pop_setor` etc).
Aplicar `MAP_POINT_LIMIT` / `MAP_POINT_LIMIT_LARGE` server-side (igual hoje).

### 6.2 Overlays (camada visual — não altera score)
| Endpoint | Reaproveita | Fonte |
| --- | --- | --- |
| `GET /overlays/concorrentes?uf=&municipio=` | `load_competitor_points` | `concorrentes/*.csv` |
| `GET /overlays/ultra?uf=&municipio=` | `load_ultra_points` | `data/ultra/Ultra.csv` |

Respeitar `COMPETITOR_PIN_LIMIT`/`ULTRA_PIN_LIMIT` (6000) e amostragem determinística.
Logos: servir o atlas de ícones (`build_icon_atlas`) como sprite pro `IconLayer` do deck.gl.

### 6.3 Análises pontuais / cenário
| Endpoint | Reaproveita |
| --- | --- |
| `GET /ponto/entorno?lat=&lng=&raio_km=1.6` | `analisar_entorno_ponto` (H3) |
| `POST /cenario/multihex` (lista de hex_id) | `agregar_cenario_multihex` |
| `GET /ponto/censitario?lat=&lng=` (raio 1.0 km) | `analisar_ponto_censitario_setores` + `load_censo_geo_setores` |

### 6.4 Camadas operacionais
| Endpoint | Reaproveita | Fonte |
| --- | --- | --- |
| `GET /dominio?uf=&municipio=` (âncoras + ordem) | `pd.read_parquet` (sem loader puro — corpo inline `@st.cache_data` em `streamlit_app.py`; extrair a coerção de colunas) | `plano_expansao_dominio.parquet` |
| `GET /carteira?uf=&municipio=` | `pd.read_parquet` (idem — extrair coerção) | `carteira_expansao_acionavel.parquet` |
| `GET /plano?uf=&municipio=` | `pd.read_parquet` (idem, forma igual à carteira) | `plano_expansao_curto_prazo.parquet` |

### 6.5 Viabilidade (tela 4a)
| Endpoint | Reaproveita |
| --- | --- |
| `POST /viabilidade` (payload: ponto, metragem, aluguel, demanda, params) | `analisar_viabilidade_ponto` (`dimensionamento/viabilidade_ponto.py:318`, engine PURO) + `gerar_serie_mensal` (`simulador.py:340`) + `carregar_base_calibracao`. **NÃO** `render_viabilidade_ponto` (isso é só UI). |
| `POST /viabilidade/relatorio-pdf` | assembly de `_render_relatorio_pdf_imovel`/`_montar_insumos_censo_pdf` (`pages.py`) portado p/ `api/service.py` + `montar_payload_viabilidade` (`viabilidade_charts.py:179`) |
| `POST /viabilidade/excel` | `gerar_excel_viabilidade` (`dimensionamento/excel_export.py:334`, retorna bytes) |

Resposta de `/viabilidade`: margem EBITDA no cenário, **ponto de equilíbrio (alunos)**,
faturamento steady-state, FCF 60m, série da rampa de alunos, série do FCF, e o **DRE
steady-state** (fat. bruto, deduções, impostos, custos op., EBITDA). Split balcão ~69% /
agregadores ~31% aplicado pelo engine (não pelo front).

---

## 7. Design System (tokens)

### 7.1 Cores
```
/* Base escura (mapa protagonista) */
--bg-app        #080b10   /* fundo do app */
--bg-panel      rgba(14,21,30,.80)   /* painéis de vidro (backdrop-blur 14–18px) */
--bg-panel-2    rgba(16,24,34,.82)   /* barras de comando / docks */
--border        rgba(255,255,255,.09)
--surface-soft  rgba(255,255,255,.04)  /* campos, cards internos */

/* Texto */
--text          #eef3f8
--text-2        #cdd8e2
--text-muted    #8b97a5
--text-faint    #6f7b89

/* Acento primário (dados/ação) — CYAN */
--accent        #35c9d6
--accent-hi     #4fd3df
--accent-ink    #06232a   /* texto sobre botão cyan */

/* Marca / rede própria — Ultra */
--ultra         #C8001E

/* Semânticos (data viz) */
--pos           #2ec86e   /* positivo / viável / white space */
--pos-hi        #4fe08a
--neg           #ff7a8a   /* negativo / abaixo do equilíbrio */
--warn          #d9a441   /* atenção / disputa / nicho */
--info          #2f6bed   /* concorrente / info */

/* Rampas de camada do mapa (por modo de cor) */
censitário  : #2a2358 → #3a2f86 → #5344b4 → #7161da → #9789ee → #c1baff (indigo)
residual    : #123f26 → #19613a → #237f4c → #39a063 → #5cbf83 → #8ad9a5 (verde)
competitivo : base cinza rgba(70,80,96,.5); white space verde #39a063/#5cbf83
recomendação: base azul-escuro rgba(40,58,84,.55); topo #2f6bed com halo
descartado <5k hab: rgba(120,120,140,.28) cinza
```
> **Regra de cor canônica:** todos os modos quantitativos usam faixas de 10 pontos via
> `RESIDUAL_SCORE_BANDS` (ver `docs/streamlit_dashboard_m1.md`). O front só mapeia score→cor;
> nunca deriva score. `POP_MIN_ACIONAVEL = 5.000` → hex cinza.

### 7.2 Tipografia
- **UI / títulos:** `Manrope` (400/500/600/700/800). Títulos 800, letter-spacing −0.01em.
- **Números / dados / coordenadas / scores:** `JetBrains Mono` (500/600/700). **Todo dado
  numérico é mono** — é a assinatura séria do produto.
- Escalas: título de tela 15–19px/800; título de painel 16–19px/800; corpo 12.5–13px;
  labels 10–11px uppercase mono muted; KPI number 22–24px mono 800.

### 7.3 Forma e profundidade
```
--radius-lg  16px  (painéis, cards grandes)
--radius-md  11–14px (cards internos, botões)
--radius-sm  7–9px (chips, campos)
gap padrão   14–18px; padding painel 16–20px
sombra card  0 24px 60px -20px rgba(0,0,0,.7)
vidro        background rgba(14,21,30,.8) + backdrop-filter: blur(14–18px) + border 1px rgba(255,255,255,.09)
pin (mapa)   teardrop: border-radius:50% 50% 50% 0; transform:rotate(-45deg); border 2px #fff
```

### 7.4 Ícones
Line-icons minimalistas (stroke 1.6, `currentColor`), 19–20px, compostos só de
formas básicas (rect/circle/line/path simples). Um por destino: Mapa (pin), Executivo
(barras), Domínio (círculos concêntricos), Carteira (linhas), Viabilidade (linha de tendência).
**Sem emoji.**

---

## 8. Princípios de UX (o que faz a refatoração funcionar)

1. **Organizar por perguntas, não por abas.** A pergunta do usuário ("onde abrir, qual
   bairro, em que ordem") guia a navegação — não a lista de features.
2. **Narrativa em funil.** A análise avança em camadas que **estreitam** o território:
   `999 hexágonos → 12 setores quentes → 5 regiões com residual → 3 white spaces → fila de 4`.
   Cada camada recolore o mapa e escreve uma frase que se apoia na anterior. É o coração do produto.
3. **Uma decisão por tela.** Nada de scroll infinito. O que importa aparece sem rolar; o
   detalhe fica em progressive disclosure (expanders, "ver detalhes").
4. **Mapa protagonista.** Full-bleed escuro; o chrome (busca, filtros, painéis) **flutua** por cima.
5. **Guiado por padrão, poder sob demanda.** "Modo guiado" leva o júnior pela mão (botão
   *Próxima camada*); o analista sênior pode pular direto entre camadas e abrir parâmetros avançados.
6. **Read-only é uma promessa visível.** Toda camada visual (pins, overlays, cenário) exibe
   "não altera o score M1". Reforça confiança e o guardrail.
7. **Números sempre em mono, com contexto.** Todo KPI traz um rótulo curto do que é e "de onde vem".

---

## 9. Especificação — Tela **Mapa** (ref. 3a)

**Objetivo:** conduzir da leitura territorial bruta até a fila de expansão, em 4 camadas.

**Layout (full-bleed, fundo `--bg-app`):**
- **Dock lateral esquerdo** (vidro): logo Ultra + 5 ícones de destino. Ativo = cyan.
- **Barra de comando (topo-esq, vidro):** logo, título "Inteligência de Expansão", busca
  (coordenada/endereço/Plus Code), seletor de UF, pill "Modo guiado".
- **Mapa (deck.gl):** `H3HexagonLayer` colorido pelo modo da camada ativa + `IconLayer`
  (Ultra vermelho, concorrentes por logo/cor). Zoom flutuante.
- **Painel de recomendação (direita, slide-over de vidro):**
  - eyebrow `Camada X de 4 · {modo}`
  - título da camada + **frase narrativa** (o texto muda por camada)
  - **destaque do funil:** número grande + unidade + "filtrados de {camada anterior}"
  - lista rankeada (4 itens): rank, nome, tese curta, métrica (mono) + tag de tom
  - rodapé: "Camada visual · read-only M1"
- **Linha do tempo da narrativa (rodapé, vidro):** 4 etapas com nº/✓, label e o número do
  funil (12 setores / 5 regiões / 3 white space / 4 aberturas) + botão primário *Próxima camada* /
  *Gerar plano de expansão*.

**As 4 camadas (estado `mstep` 1→4):**
| Camada | Modo de cor | Mapa | Painel |
| --- | --- | --- | --- |
| 1 Potencial socioeconômico | `censitário` (`score_setor_2022_calibrado`) | rampa indigo por densidade | top setores por score censitário |
| 2 Residual fitness | `residual` (`score_oportunidade_residual`) | rampa verde | top regiões por residual (alunos) |
| 3 Concorrência | `competitivo` | hexes esmaecidos + white space verde + pins de concorrentes em destaque | white space vs disputa (conc. 2km) |
| 4 Recomendação | `dominio` (`tese_dominio` + `ordem_expansao_cidade`) | topo em azul com halo + pins numerados 1–4 | fila operacional (ordem T+0…T+9) |

**Interações:** clicar etapa → troca camada; *Próxima camada* → avança; clicar hex →
Análise Pontual de Entorno (`/ponto/entorno`); busca por coordenada → destaca hex + card.
**Dados:** `/uf/{uf}`, `/overlays/*`, `/dominio`. Cores por `RESIDUAL_SCORE_BANDS`.

**Números do funil:** derivados dos dados reais da UF filtrada (contagens de setores acima
do corte, regiões com residual > 0, white spaces com conc.=0 no raio, âncoras do plano de domínio).
No protótipo estão fixos (DF) para ilustrar — no app, calcular a partir dos endpoints.

---

## 10. Especificação — Tela **Viabilidade** (ref. 4a)

**Objetivo:** do ponto no mapa ao veredito financeiro, uma decisão por tela. É um
**stress-test** de um imóvel real (não muta M1, carteira nem artefatos).

**Layout:** barra de comando (título + breadcrumb "↩ vindo do mapa · {bairro}" + coordenada).
Corpo em 2 colunas:

**Coluna esquerda — painel de cenário (rolável):**
- Seção **Cenário:** Metragem, Aluguel, e **Demanda do modelo** (valor estimado pelos
  modelos Ultra; ± é só *ajuste fino* para stress-test — o operador não "inventa" a demanda).
  Nota do split balcão ~69% / agregadores ~31%. "Parâmetros avançados" (colapsado).
- Seção **Dados para o relatório (opcional):** dropzone de **fotos** (até 2), nome/endereço,
  valor de venda, pé-direito, vagas, tipo do imóvel, observações.
- Rodapé fixo: *Recalcular viabilidade* (primário) + *Exportar Excel* / *Relatório PDF*.

**Coluna direita — resultados:**
1. **Veredito** (banner com barra de acento): título + frase (ex.: "Com 800 alunos, margem
   EBITDA −34,6%, abaixo do equilíbrio ~1.150") + pill de status ("Requer revisão de premissas"
   / "Aprovado para comitê"). Tom pela cor: `--neg` / `--pos` / `--warn`.
2. **4 KPIs:** Margem EBITDA · Ponto de equilíbrio (alunos) · Faturamento bruto/mês · FCF 60m.
3. **Régua de equilíbrio (peça principal, no lugar do heatmap):** barra horizontal
   vermelho→verde numa escala de alunos (0…1.400); marcador da **demanda do modelo** + linha
   do **ponto de equilíbrio (1.150)**. Bate o olho e entende se está viável. Substitui a
   matriz de sensibilidade porque a demanda é **saída do modelo**, não um sweep do operador.
4. **Três gráficos intuitivos:** Rampa de alunos (linha, maturação mês 8) · **DRE em cascata**
   (fat. bruto → deduções → impostos → custos op. → EBITDA) · FCF acumulado (área).

**Interação (stress-test):** ± na demanda → recomputa via `/viabilidade`; o marcador da
régua desliza e cruza o equilíbrio, o DRE/EBITDA e o FCF acompanham, e o veredito troca de
tom. **Todo o cálculo é do backend** (engine atual); o front só renderiza a resposta.

**Números do protótipo:** matriz/valores de exemplo do DF (fat. bruto R$95k @800 alunos,
equilíbrio ~1.150). No app, tudo vem de `/viabilidade`.

---

## 11. Componentes reutilizáveis do front

- `AppShell` (dock + área de conteúdo por tela).
- `CommandBar` (busca + UF + pills).
- `GlassPanel` (base de vidro; usada em slide-over, dock, barras).
- `MapCanvas` (deck.gl + MapLibre; recebe hexes + overlays + modo de cor).
- `RecommendationPanel` (eyebrow, título, narrativa, funil, lista rankeada).
- `NarrativeTimeline` (stepper com funil + CTA).
- `RankedList` / `RankedItem` (rank, título, tese, métrica mono, tag de tom).
- `Kpi` (label, valor mono, tom).
- `BreakEvenGauge` (régua vermelho→verde com marcadores).
- `WaterfallDRE` (barras de cascata).
- `LineChart` / `AreaChart` (SVG simples).
- `TagPill` (tons: blue/green/amber/red/gray — ver `tag()` no HTML de referência).
- `ScenarioForm` (inputs de viabilidade + relatório).

---

## 12. Estado e dados no front

- **Servidor:** react-query por endpoint, chaveado por UF + filtros. Cache e revalidação.
- **UI local:** `{ uf, filtros, mstep (camada), pontoSelecionado, demanda }`.
- **Derivações no cliente:** só cor a partir de score (bandas), formatação e layout.
  **Nunca** cálculo de score, residual, DRE ou ordem — isso é do backend.

---

## 13. Guardrails e não-objetivos (do `CLAUDE.md`)

- **API read-only.** Não escreve Parquets, não recalcula `score_priorizacao`,
  `hex_score_estrutural`, carteira, plano, plano de domínio nem artefatos M1.
- Pins/logos de concorrentes e Ultra são **camada visual** — não afetam score/ranking/carteira.
- Análises pontuais e multi-hex usam centróide de hex como aproximação (documentar na UI).
- **Fora do piloto:** PostGIS, Prefect, pipelines pesados ao vivo, M2/M3, pesquisas, Power BI.
- Preservar 100% das linhas/colunas oficiais do M1 ao servir dados.
- **Segurança/VPS:** nenhum comando no servidor sem confirmação explícita, comando a comando.

---

## 14. Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| Render de ~35k hexes no cliente (OOM/WebGL) | manter caps (`MAP_POINT_LIMIT`/`_LARGE`), simplificar layer em recortes grandes (já feito no Streamlit) |
| Paridade numérica com o Streamlit | endpoints reusam as MESMAS funções; teste de contrato comparando JSON vs saída atual |
| Divergência de cor/faixa | centralizar `RESIDUAL_SCORE_BANDS` no back e enviar já a banda, ou replicar tabela única no front |
| Peso dos logos de concorrentes | servir atlas/sprite único (`build_icon_atlas`), não data-URI por pin |
| Escopo inflar | piloto = só Mapa + Viabilidade; resto só depois de validar |

---

## 15. Critérios de aceite do piloto (checklist)

- [ ] `/ufs`, `/uf/{uf}`, `/overlays/*` retornam JSON idêntico em números ao Streamlit.
- [ ] Tela Mapa: 4 camadas trocam cor + narrativa + funil; clique no hex abre entorno.
- [ ] Tela Viabilidade: ± demanda recomputa veredito/régua/DRE/FCF via `/viabilidade`.
- [ ] Relatório PDF e Excel geram e baixam.
- [ ] Carga por UF ≤ baseline; sem crash em UFs grandes (SP/AM/PA/MT/MG/BA).
- [ ] Nenhum endpoint escreve em disco; score/artefatos inalterados (teste de guardrail).
- [ ] Auth Authelia na frente; deploy Docker na VPS, ao lado do Streamlit.

---

## 16. Roadmap (ordem e dependências, sem cravar datas)

1. **Fase 0 — API base:** `/ufs`, `/uf/{uf}` (+ filtros), `/overlays/*`. Testes de contrato.
2. **Fase 1 — Tela Mapa:** AppShell + MapCanvas (deck.gl) + narrativa/funil + endpoints acima.
3. **Fase 2 — Tela Viabilidade:** `/viabilidade` + `/viabilidade/relatorio-pdf`/`excel` + UI 4a.
4. **Validação:** rodar em paralelo, medir contra §1/§15.
5. **Fase 3 — Demais telas:** Executivo, Domínio, Carteira e Plano (mesmo padrão).
6. **Fase 4 — Corte:** aposentar o Streamlit.

---

## 17. Como usar `Motor de Expansão - Referência (standalone).html`

- Abra no navegador (arquivo na raiz do repo). Contém as telas **Mapa (3a)** e **Viabilidade (4a)** em
  HTML/CSS/JS puro, **interativas** (stepper de camadas; ± da demanda) — mas com **dados mockados** (4
  snapshots + tabela de lookup; **zero fetch**) e **mapa FALSO** (hexágonos em CSS). É **spec visual**, não app.
- É a **fonte de verdade visual**: inspecione o CSS real (cores, espaçamento, vidro, pins,
  a régua e o DRE em cascata) e copie os valores exatos para os componentes React.
- O mapa ali usa **hexágonos desenhados em CSS** apenas para ilustrar — no app, troque por
  `H3HexagonLayer` do deck.gl sobre os dados reais. Todo o resto (layout, painéis, tipografia,
  interações) é para reproduzir fielmente.
- Dados nas telas são exemplos do DF; no app vêm dos endpoints da §6.
```
```
