# System Design de Referência — Novo App (Motor de Expansão)

> **Épico:** BLK-REV — Revisão do app (pesquisa e planejamento).
> **Origem:** tarefa ClickUp "Pesquisa/Análise de System Design de referência para o novo app" (86e28ewja).
> **Entregável:** benchmark de referências externas + recomendações aplicáveis ao nosso contexto.
> **Consumido por:** BLK-REV-10 (arquitetura de informação), BLK-REV-11 (design system); dialoga com
> BLK-REV-08 (spike client-side) e BLK-REV-12 (síntese/decisão de rumo). Tarefa independente.
> **Guardrail:** READ-ONLY sobre o M1 (§5) — pesquisa/planejamento, não implementa produção.
> **Data:** 2026-07-16

---

## 0. Sumário executivo — o que este documento conclui

O benchmark converge em uma tese central e cinco padrões que endereçam diretamente as cinco dores relatadas (lag no mapa, lag na troca de cor/heatmap, lag na seleção de hex, lag no PDF, app poluído para leigos):

1. **O gargalo de performance do mapa não é o volume de dados nem o deck.gl — é o ciclo rerun/reserialização do Streamlit + pydeck.** O deck.gl renderiza ~1M de itens a 60 FPS; 18–35k hexes H3 estão duas a três ordens de grandeza abaixo do limite de fluidez. A causa das dores #1–3 é que cada interação re-executa o script e reenvia todos os dados, forçando o deck.gl a regenerar todos os GPU buffers. **A solução é uma camada de mapa client-side persistente que muta só o atributo alterado — não reduzir dados.** (Confirma empiricamente a hipótese que o BLK-REV-08 vai medir.)

2. **Separar consumo de autoria** (modo Viewer limpo vs. modo Explorar/Construir) é o padrão universal de BI e o antídoto direto ao "poluído para leigos".

3. **Score único e humano (A–F / 0–100 + semáforo) como capa**, com sub-scores e variáveis atrás de progressive disclosure. Nunca abrir com uma tabela; abrir com uma nota.

4. **Layout mapa-dominante + painéis retráteis + brushing bidirecional**, com painel de propriedades oculto até a seleção. Abandonar o layout em colunas rígidas do Streamlit.

5. **H3 como eixo unificador de macro→micro** (triagem municipal em r5–6 ↔ viabilidade pontual em r8–9), com zoom semântico. É uma vantagem estrutural que os incumbentes fazem com pipelines separados.

As recomendações abaixo são organizadas por **dimensão de System Design** (layout, navegação, componentização, dataviz, progressive disclosure, fluxo/IA, relatórios) e cada uma amarra os padrões observados às nossas dores.

---

## 1. Produtos analisados

| Família | Produtos | Por que importam |
|---|---|---|
| **A. Geo / mapas dataviz** | deck.gl, kepler.gl, CARTO Builder, Foursquare Studio (ex-Unfolded), Mapbox Studio, Felt | Teto de performance do mapa client-side; renderização H3; separação dado↔estilo; UX de mapa para leigos |
| **B. BI / dashboards** | Tableau, Power BI, Looker, Metabase, Sigma, Superset | Densidade/clutter, progressive disclosure, cross-filtering, KPI tiles, relatórios paginados (PDF) |
| **C. Real estate / location intelligence** | SiteZeus (Atlas 2026), Esri ArcGIS Business Analyst, Placer.ai, Tango, Buxton, CARTO | Funil mercado→site, score humano, narrativa IA, catchment/canibalização, relatórios committee-ready |

---

## 2. Diagnóstico técnico: por que o mapa atual trava (dores #1–3)

Achado mais importante para o BLK-REV-08 e para a decisão de rumo do BLK-REV-12:

- **O volume não é o problema.** O deck.gl nativo renderiza ~1M de itens a 60 FPS durante pan/zoom em hardware de 2015 e só degrada perto de 10M de itens. Nossos 18–35k hexes estão muito abaixo do limite de fluidez.
- **A causa é o acoplamento Streamlit (rerun) + pydeck (reserialização).** No Streamlit, cada interação de widget re-executa o script inteiro; o pydeck reserializa todo o spec JSON e reenvia todos os dados de todos os hexágonos ao navegador, forçando o deck.gl a **regenerar todos os GPU buffers do zero** — a operação mais cara que uma camada faz, segundo a própria doc do deck.gl. Trocar o modo de cor dispara exatamente esse caminho.
- **Os produtos de referência evitam isso** mantendo uma instância deck.gl **persistente** no cliente e mutando apenas a propriedade que mudou via `updateTriggers` — nunca reenviando dados. É o modelo Mapbox de "dado ↔ estilo separados": vector tiles carregam geometria/atributos crus, e a estilização acontece em runtime, então trocar cor/estilo **não recarrega dados**.

**Implicação para o rumo (BLK-REV-12):** migrar a camada de mapa para um componente JS deck.gl persistente resolve as dores #1–3 sem tocar no volume de dados. Isso reforça a viabilidade do rebuild sobre a infra existente (SPA servida pelo Caddy + API FastAPI) mencionada na emenda do REV-12.

---

## 3. LAYOUT

**Padrões observados (convergentes nas três famílias):**

- **Mapa como fundo dominante em tela cheia**, com UI flutuando sobre ele (kepler.gl, Felt, Esri). Ninguém usa layout de colunas rígidas tipo Streamlit onde o mapa divide espaço fixo.
- **Sidebar esquerda retrátil = composição/controle** (camadas, filtros, critérios). **Painel direito = propriedades do objeto selecionado, oculto até haver seleção** (Felt, kepler.gl). Dock inferior colapsável para a tabela de dados.
- **BI impõe teto de densidade explícito:** Tableau recomenda 2–3 views por dashboard; Power BI, no máximo 3–4 KPI tiles no topo; grid de 8px com snap; whitespace de 16–24px entre cards. Hierarquia em Z (mensagem principal no topo-esquerda).
- **Atalho para esconder toda a UI** (Felt `Cmd/Ctrl+.`) para modo apresentação.

**Recomendações:**

Migrar do layout em colunas do Streamlit para **mapa full-bleed + painéis flutuantes retráteis** — isso sozinho já reduz a sensação de "poluído". Sidebar esquerda com abas (*Camadas | Cor/Visualização | Cenários*); **painel de propriedades do hexágono/cenário à direita, oculto por padrão**, abrindo só ao selecionar um hex (padrão Felt — não renderizar controles de propriedade quando não há seleção). Dock inferior colapsável para a tabela de hexes do cenário. Adotar **grid de 8px**, teto de densidade (no modo Viewer: 3–4 KPIs + mapa + 2–3 gráficos por tela; o resto vai para abas/seções), e whitespace de 16–24px. Incluir um **"modo apresentação"** que esconde a UI para mostrar a executivos.

---

## 4. NAVEGAÇÃO

**Padrões observados:**

- **Troca de modo de cor/heatmap = mudança de propriedade de estilo, nunca recarga de dados** (Mapbox data-driven styling; CARTO/Foursquare re-estilizam no cliente).
- **Separação explícita editor vs. viewer** (Felt `Shift+E`, abas Legend/List). Leigos entram no modo viewer limpo, "safe".
- **Cross-filtering** (Looker, Metabase, Power BI): clicar num elemento filtra/destaca todos os demais. Boas práticas: habilitar seletivamente, sinalizar visualmente o que é clicável e **sempre oferecer "Limpar/Resetar"** para o usuário não ficar "preso".
- **Zoom semântico** (Esri): o nível de zoom governa o detalhe — em resolução baixa rotula por estado/município, em alta por ZIP/ponto; transita macro↔micro num único gesto.
- **Breadcrumbs** para orientar o leigo (`Brasil > Estado > Município > Endereço`).

**Recomendações:**

Adotar **modelo de dois modos**: "Exploração" (viewer limpo, read-only, para gestores/leigos) e "Construção de cenário" (power user) — espelha o Legend/List do Felt. **A troca de modo de cor/heatmap deve ser puramente client-side** (`updateTriggers` para o atributo de cor; toggle `visible` para heatmap) e **nunca disparar rerun do backend**. Camadas ligadas/desligadas via prop `visible`, jamais recriadas. **Cross-filtering pelo mapa:** clicar num hexágono filtra os gráficos de demografia/concorrência, com botão "Limpar filtros" sempre visível. **Zoom semântico H3** para transitar triagem municipal ↔ viabilidade pontual. **Breadcrumb persistente** e navegação por abas/segmented control no topo (Pontual | Municipal | Comparar) em vez de re-rodar a página inteira.

---

## 5. COMPONENTIZAÇÃO

**Padrões observados:**

- **Controle de cor em dois níveis** (kepler.gl): nível 1 = "colorir por qual campo?"; nível 2 (atrás de "···") = tipo de escala (quantile/quantized), paleta, nº de steps, cores custom.
- **Escala quantile (por rank) vs. quantized (por valor)** exposta como escolha explícita — crítica para dados enviesados.
- **Legenda dinâmica** que remove categorias fora do viewport (Foursquare Dynamic Color) — ataca diretamente o "poluído".
- **KPI tile canônico** (Power BI/Metabase): valor grande + delta% + seta semântica + mini-sparkline + comparação com meta; sustenta a "compreensão em 5 segundos".
- **Painel de configuração recolhível** (popover/modal, estilo Sigma) tira parâmetros avançados da tela principal.
- **Interactions como painel separado** (kepler.gl): tooltip, brush, polygon-filter desacoplados do estilo.

**Recomendações:**

Criar um **design system de 5–6 componentes canônicos** (insumo direto para o BLK-REV-11) e compor toda tela a partir deles:

1. **KPI Tile** — score de aderência (grande) + delta vs. média do município/rede + meta + seta verde/vermelha com semântica de negócio (público-alvo↑ bom, canibalização↑ ruim) + mini-sparkline.
2. **Card de mapa** (deck.gl persistente).
3. **Card de gráfico** (barra/linha).
4. **Card de tabela** com formatação condicional.
5. **Text/section card** (títulos de seção, notas).
6. **Filtro global** + **seletor de cor em dois níveis**.

O **seletor de cor** deve mostrar ao leigo só "Colorir por: [métrica]" + 3–4 paletas nomeadas em linguagem de negócio ("Oportunidade", "Risco", "Densidade"); o power user expande para quantile vs. quantized e nº de bins. **Legenda que reflete só o viewport atual** (padrão Foursquare). Parâmetros avançados (pesos do modelo, raio, fonte de dados) atrás de um botão "Configurar" (popover), eliminando a sidebar poluída do Streamlit. Cada componente com **estado local**, sem trigger de recarga global.

---

## 6. DATAVIZ — mapa e gráficos

### 6.1 Núcleo: performance do mapa H3 (dores #1–3)

Técnicas verificáveis do deck.gl e da stack de tiles, ordenadas por impacto:

| Técnica | Aplicação | Dor |
|---|---|---|
| `H3HexagonLayer` persistente + `updateTriggers: { getFillColor }` | Trocar cor mutando só o buffer de cor, sem reenviar hexes | #2 |
| Toggle `visible` em vez de add/remove de camada | Heatmap on/off instantâneo | #2 |
| `highPrecision: false` (res uniforme, sem pentágonos) | Caminho rápido de instanced drawing p/ H3 | #1 |
| `useDevicePixels: false` | Desliga Retina, ~4× menos fragmentos — ganho grande e barato | #1 |
| `pickable: true` só na camada H3 interativa | Reduz custo de pan/hover (picking usa buffer off-screen) | #1, #3 |
| Picking GPU nativo (16M itens/camada) p/ clique; Polygon-filter (kepler) p/ seleção em massa | Seleção sem re-render por clique | #3 |
| Marcar hex selecionado mutando `getFillColor` via `updateTriggers` | Inclusão em cenário sem reprocessar o dataset | #3 |
| Dados como binary/TypedArray (Arrow), atributos pré-calculados | Bypass da geração de buffer na CPU (essencial ao sair do pydeck) | #1 |
| CARTO Dynamic Tiling binário + Spatial Index Tilesets (H3 = features do tile) | Escalar além de ~35k hexes / multi-cidade | escala |
| Agregação zoom-adaptativa de resolução H3 | Menos células em zoom baixo | #1, escala |

### 6.2 Gráficos e cor para leigos

**Padrões observados (BI):** usar o tipo de gráfico certo — às vezes uma tabela é mais clara que um gráfico; barras/colunas são imbatíveis para comparação. Paletas acessíveis: máximo 12 cores, ideal ≤6 categóricas; validar colorblind (ColorBrewer/Viz Palette) e WCAG; desenhar primeiro em grayscale. Cor semântica limitada a 3–5 significados. **Título como insight, não como métrica.** Formatação condicional, goal lines e trend arrows traduzem "isto é bom/na meta?".

**Recomendações:**

Forçar o caminho rápido do deck.gl (§6.1) — esse é o coração da solução das dores #1–3. Para gráficos: padronizar uma **paleta de marca de ≤6 cores + uma escala sequencial única** para os heatmaps, validada para daltonismo (mapas coropléticos são o ponto mais crítico de acessibilidade). **Números para leigos:** abreviar (12,5 mil / 1,2 mi / R$ 3,4 mi), % com 1 casa e **sempre com comparação** (vs. média do município, vs. meta). **Títulos-frase:** trocar "População 0-5km" por "Público-alvo no raio: 42 mil (acima da média da rede)". **Semântica de cor consistente** em KPIs, mapas e tabelas: verde = favorável, vermelho = risco/canibalização, cinza = neutro. Preferir barras/tabelas com condicional a gauges/pizzas decorativos.

### 6.3 Dataviz espacial específica de site selection

**Padrões observados (location intelligence):**

- **Catchment via origem real, não raio** (Placer "True Trade Area"): o trade area é o conjunto de áreas de onde a demanda realmente vem — muito mais preciso que um círculo de N km.
- **Classificação escolhível** (Esri): Quantile / Natural breaks / Equal interval; ramp sequencial + transparência.
- **Três tipos de influência de variável** (Esri): Positive (quanto maior, melhor), Inverse (quanto menor, melhor), **Ideal** (valor-alvo — quanto mais perto, melhor).
- **Canibalização como overlap** de trade areas com unidades existentes (Placer), com % de sobreposição.
- **Twin Areas / áreas gêmeas** (CARTO): dado um site bom, achar áreas com perfil similar.

**Recomendações:**

Calcular **catchment via H3** (conjunto de hexágonos de onde vem a demanda), não círculo — mais preciso e mais convincente visualmente. **Heatmap de potencial = H3 coroplético** com classificação escolhível (default **Natural breaks** para leigos, que evita distorção de outliers). Implementar os **três tipos de influência** no motor de score (o "Ideal" é poderoso para distância ótima a uma unidade existente — minimiza canibalização sem deixar whitespace). **Canibalização como interseção de células H3** com % de overlap (barato de calcular em H3). Camada de competição com **peso por tipo de concorrente** (direto vs. indireto). Considerar **Twin Areas** para a triagem municipal ("onde mais existe um mercado como o do meu melhor município?"). Filtro por score e por rank (top-N) direto no mapa e no ranking.

---

## 7. PROGRESSIVE DISCLOSURE (dor #5 — poluído/leigo)

**Padrões observados:**

- **Fundamento NN/g:** mostrar inicialmente só as poucas opções mais importantes; revelar o avançado sob demanda. Máximo **2 níveis** de disclosure. Deixar **óbvio como progredir** (botão visível com "information scent"). Wizards (staged disclosure) para tarefas lineares.
- **Painel de propriedades oculto até seleção** (Felt); controles avançados atrás de "···"/toggle (kepler.gl, Foursquare).
- **Modo viewer "safe" vs. modo editor** (Felt): leigo nunca vê ferramentas de edição.
- **Defaults inteligentes que dispensam configuração** (Foursquare Dynamic Color escolhe a escala ótima sozinho, sem metadados).
- **Query builder GUI em vez de SQL** (Metabase) dá ao leigo o poder sem código; tooltips/text cards explicam desvios e reduzem jargão.

**Recomendações:**

Adotar **dois níveis de UI por padrão** (não mais que dois): **"Simples"** (só métrica + paleta nomeada + toggle de heatmap + legenda dinâmica; painel de propriedades por seleção) e **"Avançado"** (quantile/quantized, bins, opacidade, custom palette, filtros, pesos do modelo). Leigos e executivos ficam no Simples; o operador entra no Avançado por um botão claro "Explorar dados" com "Voltar ao resumo". **Defaults automáticos:** ao abrir um dataset, escolher a escala de cor por viewport automaticamente (padrão Foursquare) — o leigo não configura nada e já vê bom contraste. **Nomear escalas em linguagem de negócio** e esconder o vocabulário GIS (quantile, resolução H3) no modo avançado. **Onboarding leve:** tour de 3–4 passos na primeira visita + tooltips contextuais em cada KPI/camada + glossário (i) para "isócrona", "canibalização", "índice de aderência". **Landing-resumo de 1 tela** ("Vale a pena? Sim/Não + 3 KPIs + mapa") como antídoto direto ao poluído.

---

## 8. FLUXO CORE + SCORE + NARRATIVA (específico de site selection)

Esta seção sintetiza o que os líderes de location intelligence fazem e que não aparece em BI/mapas genéricos — é o coração do valor do Motor de Expansão.

**Padrões observados:**

- **Funil de 2 estágios com gate explícito** (Buxton, SiteZeus, Tango): dimensionar o mercado → escolher o site vencedor. O macro é etapa-porteira do micro, mas é o **mesmo motor em escalas diferentes** (SiteZeus roda 30k+ ZIPs com o mesmo rigor de um single-site).
- **Múltiplos pontos de entrada** (SiteZeus): pergunta em linguagem natural, pin no mapa, ou endereço colado — todos convergem ao mesmo motor de score.
- **Score único e humano como capa** (SiteZeus A–F customizável; Esri 0–100; Tango dual-score Site + Demographic), com sub-scores atrás de progressive disclosure.
- **Narrativa gerada por IA em linguagem natural** (SiteZeus Zeus.ai Summary): explica o forecast em 2–3 frases — puxadores, variáveis que mais pesam, riscos. Deixa stakeholders "que nunca abriram a plataforma" se auto-servirem.
- **Explicabilidade obrigatória** (SiteZeus, Tango, Esri): comitês exigem "por que este score" (ranking das variáveis ponderadas) — sem isso não aprovam. *"If you can't explain how your software arrived at a prediction, you can't act on it."*
- **Comparação lado a lado** de 2–4 sites/municípios (SiteZeus drag-to-compare; Tango) — decisão de expansão é sempre comparativa.
- **Ranking top-N/bottom-N como resumo executivo** (Esri top-5/bottom-5), não uma tabela de milhares de linhas.

**Recomendações:**

Modelar explicitamente os **dois estágios como um gate visível** (Triagem Municipal → Viabilidade Pontual), com o usuário sempre sabendo em qual está e podendo descer (clicar num município) e subir (breadcrumb). Usar o **H3 como a unidade que unifica os dois níveis** (r5–6 para triagem/heatmap; r8–9 para catchment do site — a métrica de potencial é aditiva em H3). Permitir **múltiplos pontos de entrada**. Adotar **score único e humano (A–F ou 0–100 + semáforo) como a "capa"** de cada município e site; considerar o **dual-score** adaptado ("Score de Mercado" = potencial de demanda + "Score de Ponto" = viabilidade do endereço). **Gerar narrativa automática de 2–3 frases por site/município** (veredito + puxadores + riscos) — é a maior alavanca de clareza para leigos que a pesquisa revela. **Sempre mostrar o "porquê do score"** (ranking das variáveis ponderadas). **Comparação lado a lado** e **tela de ranking** (top-10 melhores / piores municípios) como entregas imediatas da triagem.

---

## 9. RELATÓRIOS / PDF (dor #4 — lag no PDF Pontual e Municipal)

**Padrões observados:**

- **PDF ≠ dashboard** (Power BI): relatórios paginados são otimizados para impressão — layout fixo, cabeçalho/rodapé repetidos, numeração de página, print-first (A4/Letter, margens, fontes ≥10pt). Não gerar o PDF como screenshot do dashboard interativo.
- **One-pager executivo na pág. 1** (Esri card, Buxton board-ready): score + veredito em uma frase + mapa + 3 puxadores + 2 riscos. Executivo decide sem virar a página.
- **Blocos reusáveis / template salvável** (SiteZeus chat-driven reporting): o PDF é composto pelos mesmos cards da tela; um template aprovado pelo comitê vira padrão da empresa.
- **Biblioteca de relatórios de site** (Placer): Trade Area Demographics, True Trade Area, Cannibalization, Void — branded e automáticos.
- **Cadência/subscription** (Metabase): enviar o PDF por email em cadência para quem não abre o app.

**Recomendações:**

Tratar **Pontual e Municipal como relatórios paginados print-first** (template A4 fixo, margens seguras, numeração), não como export do dashboard — isso também tende a reduzir o custo de geração (dor #4), pois evita renderizar o app inteiro. Estrutura sugerida:

- **Municipal (triagem):** capa com ranking dos municípios + heatmap H3 de potencial; para cada município top: score, demanda estimada, whitespace, saturação/competição, nº de unidades que o mercado suporta.
- **Pontual (viabilidade):** one-pager executivo na pág. 1 (score A–F + semáforo + narrativa IA + mapa do catchment H3), seguido de demografia do trade area, competição/canibalização, co-tenants/POIs e forecast com explicação das variáveis.

Compor o PDF a partir dos **mesmos componentes canônicos** da tela (§5) — um template committee-ready vira padrão. Incluir sempre a seção **"por que este score"** (defensabilidade em comitê) e a **narrativa em linguagem natural** impressa (leigo lê sem o app). Permitir **envio agendado** do Municipal ao comitê de expansão.

---

## 10. Matriz Persona × Dimensão

| Dimensão | Executivo | Operador | Leigo |
|---|---|---|---|
| **Layout** | 1 tela: veredito + 3–4 KPIs + mapa | + gráficos de apoio, abas de detalhe | igual ao exec + títulos-frase |
| **Navegação** | cenários/presets salvos | drill-down livre, cross-filter | botões guiados + breadcrumbs + reset |
| **Componentização** | KPI Tiles + veredito | tiles + tabelas condicionais | tiles com ícones/rótulos simples |
| **Dataviz** | números abreviados + comparação | gráficos densos, condicional | frases + semântica de cor |
| **Progressive disclosure** | landing-resumo | modo "Explorar" completo | onboarding + tooltips + glossário |
| **Score/narrativa** | score + narrativa 2–3 frases | score + variáveis ponderadas | score + semáforo + narrativa |
| **PDF** | 1–2 págs (veredito+KPIs), por email | PDF completo master-detail | PDF com glossário |

---

## 11. Recomendações priorizadas (ligação com as dores)

| # | Recomendação | Dor(es) | Diálogo com bloco |
|---|---|---|---|
| 1 | Camada de mapa **deck.gl persistente client-side**; trocar cor via `updateTriggers`, heatmap via `visible`; nunca reenviar dados | #1, #2 | BLK-REV-08 (mede), REV-12 (rumo) |
| 2 | **Seleção via picking GPU + polygon-filter**; marcar hex de cenário mutando atributo, sem reprocessar dataset | #3 | BLK-REV-08 |
| 3 | Layout **mapa full-bleed + painéis retráteis**; propriedades por seleção; grid 8px, whitespace 16–24px | #5 | BLK-REV-10 |
| 4 | **Dois modos (Viewer/Explorar)** + dois níveis de UI (Simples/Avançado); defaults automáticos | #5 | BLK-REV-09, REV-10 |
| 5 | **Score único humano (A–F/semáforo) + narrativa IA 2–3 frases + "porquê do score"** | #5 | BLK-REV-10 |
| 6 | **Design system de 5–6 componentes canônicos** (KPI tile, mapa, gráfico, tabela, texto, filtro/cor); paleta ≤6 cores validada p/ daltonismo; semântica de cor consistente | #5 | BLK-REV-11 |
| 7 | **H3 como eixo macro↔micro** com zoom semântico; catchment por origem real; canibalização como overlap de células | — | BLK-REV-10, REV-12 |
| 8 | **PDF paginado print-first** (Pontual/Municipal) com one-pager executivo e blocos reusáveis | #4 | BLK-REV-10/11 |

---

## 12. Handoff para os blocos seguintes

- **BLK-REV-10 (arquitetura de informação):** usar §3 (layout), §4 (navegação), §7 (progressive disclosure), §8 (fluxo mercado→site com H3) e a matriz persona (§10) como base dos wireframes de baixa fidelidade e do modelo de dois modos.
- **BLK-REV-11 (design system):** usar §5 (componentização), §6.2 (paletas/cor/dataviz) — os 5–6 componentes canônicos, tokens de cor semântica e a escala sequencial acessível são o ponto de partida.
- **BLK-REV-08 (spike client-side):** §2 e §6.1 são as hipóteses técnicas a validar empiricamente (FPS, latência de troca de cor/seleção; frames WebSocket; A/B Streamlit vs. client-side na VPS).
- **BLK-REV-12 (síntese/decisão):** §2 e a tabela §11 alimentam o critério de performance e o de custo de dev (a migração da camada de mapa para JS aproxima o rebuild sobre a infra existente).

---

## 13. Fontes

**Geo / mapas**

- deck.gl — Performance Optimization: https://deck.gl/docs/developer-guide/performance
- deck.gl — H3HexagonLayer: https://deck.gl/docs/api-reference/geo-layers/h3-hexagon-layer
- deck.gl — H3TileLayer (CARTO): https://deck.gl/docs/api-reference/carto/h3-tile-layer
- kepler.gl — H3 layer: https://docs.kepler.gl/docs/user-guides/c-types-of-layers/j-h3
- kepler.gl — Color Palettes: https://docs.kepler.gl/docs/user-guides/l-color-attributes
- kepler.gl — Interactions: https://docs.kepler.gl/docs/user-guides/g-interactions
- CARTO — How CARTO generates and serves map tiles: https://carto.com/blog/carto-tile-generation-cloud-native/
- CARTO — Spatial Indexes (H3): https://carto.com/solutions/spatial-indexes/
- Foursquare Studio — Visualize Big Data with Vector Tiles: https://foursquare.com/resources/blog/capabilities/visualize-big-data-with-vector-tiles-in-foursquare-studio/
- Foursquare Studio — Best Practices Visualizing Vector Tiles (Dynamic Color): https://docs.foursquare.com/analytics-products/docs/vector-tiles-visualize
- Mapbox — Vector tiles introduction: https://docs.mapbox.com/data/tilesets/guides/vector-tiles-introduction/
- Mapbox — Style layers (data-driven styling): https://docs.mapbox.com/mapbox-gl-js/guides/add-your-data/style-layers/
- Felt — Tour the interface: https://help.felt.com/getting-started/tour-the-interface

**BI / dashboards**

- Tableau — Best Practices for Effective Dashboards: https://help.tableau.com/current/pro/desktop/en-us/dashboards_best_practices.htm
- Tableau — Dashboard spacing/whitespace: https://www.tableau.com/blog/command-visual-best-practices-dashboard-spacing-tableau-104-73169
- Power BI — design best practices (grid 8pt, Z/F-pattern): https://lukasreese.com/2025/08/20/power-bi-dashboard-design-best-practices-guide/
- KPI card best practices (Tabular Editor): https://tabulareditor.com/blog/kpi-card-best-practices-dashboard-design
- Looker — Cross-filtering dashboards: https://cloud.google.com/looker/docs/cross-filtering-dashboards
- Looker — More powerful data drilling: https://cloud.google.com/looker/docs/best-practices/how-to-use-more-powerful-data-drilling
- Metabase — BI dashboard best practices: https://www.metabase.com/learn/metabase-basics/querying-and-dashboards/dashboards/bi-dashboard-best-practices
- Metabase — Which chart to use: https://www.metabase.com/learn/cheat-sheets/which-chart-to-use
- Sigma — Layout options (phData): https://www.phdata.io/blog/what-are-sigma-dashboard-layout-options/
- Atlassian — Data viz color selection: https://www.atlassian.com/data/charts/how-to-choose-colors-data-visualization
- NN/g — Progressive Disclosure: https://www.nngroup.com/articles/progressive-disclosure/
- Microsoft — When to use paginated reports: https://learn.microsoft.com/en-us/power-bi/guidance/report-paginated-or-power-bi
- Microsoft — Export Power BI reports to PDF: https://learn.microsoft.com/en-us/power-bi/collaborate-share/end-user-pdf

**Real estate / location intelligence**

- SiteZeus — Atlas release: https://insites.sitezeus.com/locate/introducing-atlas-release-sitezeus-locate
- SiteZeus — Ask Zeus (IA conversacional): https://insites.sitezeus.com/locate/ask-zeus-conversational-ai-site-selection
- SiteZeus — Zeus.ai Summary & Chat: https://support.sitezeus.com/en/zeus.ai
- SiteZeus — Chat-driven reporting: https://insites.sitezeus.com/locate/chat-driven-reporting-atlas-release
- Esri ArcGIS Business Analyst — Suitability analysis: https://doc.arcgis.com/en/business-analyst/web/suitability-analysis.htm
- Esri — Business Analyst overview: https://www.esri.com/en-us/arcgis/products/arcgis-business-analyst/overview
- Placer.ai — Site Selection: https://www.placer.ai/site-selection
- Placer.ai — Void Analysis: https://www.placer.ai/guides/void-analysis
- Tango — Predictive Analytics: https://tangoanalytics.com/products/tango-predictive-analytics/
- Tango — 10 Must-Have Capabilities: https://tangoanalytics.com/blog/site-selection-software-capabilities/
- Buxton/Audiense — Location Strategies & Store Performance: https://www.audiense.com/solutions/location-strategies-and-store-performance/
- CARTO — Site Selection: https://carto.com/solutions/site-selection/

---

*Documento de referência — pesquisa e planejamento (READ-ONLY M1). Não implementa produção; alimenta as decisões de BLK-REV-10, 11 e 12.*
