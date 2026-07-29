# Backlog

## Priorização atual (2026-07-19)

**Ciclo em curso (PR #134):** enxugamento do CLAUDE.md + higiene de docs/orquestração — split do §8 para `docs/decisions/`, skill `/registrar-decisao` + lint de teto, índice `docs/README.md`, arquivamento do sprawl da raiz, 4 skills novas (deploy, fechar-ciclo, clickup-sync, backlog-reconcile), `.claude/settings.json` versionado, e esta reconciliação de backlog/PRD. READ-ONLY sobre o M1.

**Bloco em curso (2026-07-28):** `BLK-RELPON-14` — unificação do gerador de PDF do Relatório Pontual, remoção do slide "Imagem do Entorno" (8 → 7 páginas), borda no hexágono central dos painéis de 5 km e cadastro de 68 redes de concorrentes. Gate humano pendente: emenda de 2026-07-28 à DEC-011.

**Próximo bloco:** derivar de `/backlog-reconcile` (cruza git × completed × backlog e calcula o próximo loop-safe desbloqueado). Blocos abertos = os headings `### BLK-` abaixo.

> O ponteiro anterior (BLK-PERF-01a, 2026-07-10) apontava para bloco já concluído — substituído.

**Trilha BLK-DIM — PONTO DE DECISÃO (2026-06-15):** a sub-trilha de "estressar o dado interno"
(DIM-07→08) está **concluída** e deu **três NO-GOs honestos** — a demanda/viabilidade NÃO é previsível
pela geografia de mercado que temos. O dimensionamento por m² (DIM-03R/06) é a parte que funciona, mas
consome demanda, não a produz. **Próximo passo = decisão de Felipe na bifurcação `BLK-DIM-10`**: Caminho A
(repaginar o motor para viabilidade/break-even, ROI imediato) e/ou Caminho B (BLK-DIM-DATA, a aposta de
buscar o sinal que falta). Recomendação: A agora + B como aposta. Ver BLK-DIM-10.

- **BLK-CENSO-01** (repaginação do relatório: camadas combinadas + fundo de ruas + faixas GeoFusion +
  pins com logo) — **concluído** em 2026-06-05 (FU1–FU5 deployados na VPS). Ver tasks/completed.md.
- Bugs de produção do dashboard (BLK-FIX-03..06) — todos **concluídos** em 2026-06-03.

> Blocos BLK-OPS-02/03/04, BLK-ARCH-01 e BLK-SCORE-01/02/03 originados do "Programa de
> Melhorias — Referência do Master Orchestrator" (PRD.md), migrados em 2026-05-29.
> Mapa de dependências e ordem recomendada do programa: ver §3 do PRD.md original.
> Ordem deste backlog: arquitetura (BLK-ARCH-01) à frente da trilha de score (BLK-SCORE-*).

---

## Bugs de produção do dashboard — TOPO DE PRIORIDADE (2026-06-01)

> Reportados por Felipe a partir do dashboard em produção (`dashboard.ultra-expansao.tech`).
> Cada bug é um bloco BLK-FIX próprio. Nenhum toca M1/score, **exceto BLK-FIX-06** (litoral),
> que altera a base de hexes do M1 e regenera artefatos oficiais → **Crítica + DEC**.
> Causas-raiz abaixo são **hipóteses** ancoradas no código (file:line) a confirmar pelo Planner.

- BLK-FIX-03 (concluído 2026-06-01) — ver tasks/completed.md

- BLK-FIX-03-FU1 (concluído 2026-06-01) — ver tasks/completed.md


---

- BLK-FIX-04 (concluído 2026-06-01) — ver tasks/completed.md


---

- BLK-FIX-05 (concluído 2026-06-01) — ver tasks/completed.md


---

- BLK-FIX-06 (concluído 2026-06-03) — ver tasks/completed.md

---

- BLK-FIX-06-C (concluído 2026-06-03) — ver tasks/completed.md



---

## Relatório Pontual Censitário — repaginação (2026-06-05, pedido de Felipe)

> Pedido de Felipe a partir do uso real do relatório (PDFs anexados: estudo GeoFusion de
> referência + exemplo do relatório atual com símbolos "esquisitos"). Objetivo: tornar o
> relatório pontual censitário **utilizável no dia a dia** — uma exportação só, com renda +
> população + concorrentes juntos, fundo de ruas, faixas de cor padronizadas e pins com logo.
> Execução **faseada**: BLK-CENSO-01 (função) e depois BLK-CENSO-02 (template/visual).
> Decisões de produto **já aprovadas por Felipe** em 2026-06-05 (ver cada bloco).
> READ-ONLY sobre M1: nenhuma das mudanças recalcula `score_priorizacao`, scores censitários,
> carteira, plano ou artefatos oficiais — é camada de visualização/relatório (§5 guardrail).

- BLK-CENSO-01 (concluído 2026-06-05) — ver tasks/completed.md


---

- BLK-CENSO-02 (concluído 2026-06-05) — ver tasks/completed.md


---

- BLK-CENSO-03 (concluído 2026-06-08) — ver tasks/completed.md


---

## Relatório Pontual Censitário — polimento de layout (2026-07-01, pedido de Vini)

> Pedido de Vinicius a partir do uso real do Relatório Pontual (variante **classico**, em produção
> via dashboard e API). Hoje os três mapas de calor censitários — **População/Densidade, Renda e
> Score** — ocupam **um slide cada** (páginas 2, 3 e 4 do PDF de 7 páginas). Objetivo: **consolidá-los
> em UM único slide**, lado a lado, **sem sobreposição** entre eles nem sobre o restante do conteúdo
> (faixa de título, rodapé, marca d'água). READ-ONLY sobre o M1 (§5 guardrail): nada recalcula score,
> intersecção de setores, raio de 1,5 km ou artefatos oficiais.

- BLK-RELPON-01 (concluído 2026-07-01) — ver tasks/completed.md


---

## Grafo de conhecimento do repositório — otimização de token (2026-07-27, pedido de Vinicius)

> Pedido ad-hoc (fora do `/run-cycle`): aplicar o **graphify** ao repositório para reduzir o contexto
> que cada sessão/sub-agente carrega. A branch `graph-01` foi criada para isso.

- BLK-GRAPH-01 (concluído 2026-07-27) — ver tasks/completed.md

- BLK-GRAPH-02 (concluído 2026-07-28) — ver tasks/completed.md


---

## Relatório Pontual Censitário — vista aérea de satélite (2026-07-21, pedido de Juan)

> Pedido de Juan a partir dos estudos prontos do time de UX (`UX/*.pptx`, slide "Fotos Do Imóvel"),
> que trazem uma **foto aérea do imóvel com pin**. Objetivo: gerar essa imagem automaticamente a
> partir da coordenada que o usuário já informa (o campo de busca resolve coordenada, link do Maps,
> Plus Code e **endereço livre** — `BLK-UI-08`/`DEC-010`), e inseri-la como página própria no PDF.

### BLK-SAT-01 — Vista aérea (satélite Esri) no PDF do Relatório Pontual

| Campo | Valor |
|---|---|
| **Criticidade** | Alta |
| **Status** | **Aprovado e mergeado (PR #138, 2026-07-23)** — [DEC-018](../docs/decisions/DEC-018.md) APROVADA por Felipe (label `critica-aprovada`). Validação visual com Juan segue em andamento (não bloqueia; página aditiva). |
| **ClickUp** | — |

> **Criticidade Alta, não Média** (corrigido 2026-07-22 após a revisão automática do PR #138): o
> precedente direto — DEC-004, tiles online no MESMO relatório — é Alta, pelo mesmo motivo (desvia do
> guardrail §2 "não criar dependência de API ao vivo"). Merge exige a label `aprovado-humano`.

**Escopo (aditivo, READ-ONLY sobre o M1):** `censo_map.render_foto_satelite_ponto()` monta um PNG
da vista aérea do ponto (Esri World Imagery + `Reference/World_Transportation` para rótulos — a mesma
composição do "World Imagery Hybrid" da Esri e do `sat-overlay` do `openmaptiles-infra`), com pin
vermelho no centro. `censo_report._foto_satelite_page()` insere a página logo após a capa.
**Nada recalcula** score, interseção de setores, raio de 1,5 km ou artefato oficial — os números do
relatório saem idênticos com e sem a página.

**Zoom:** sonda 1 tile e usa z19 se houver imagem no ponto, senão z18. Medido em 22 pontos do Brasil:
z17 existe em todo lugar, z18 em cidade média/grande, z19 só em capital.

**Tamanho da imagem na página:** `foto_satelite_grande=True` (API/bot e PDF do dashboard, onde a
vista aérea é a única imagem) ocupa a área de conteúdo; `False` (aba Viabilidade) usa a célula padrão
de `_fotos_cells`, para casar com a página de fotos do imóvel que o usuário sobe. Em **página própria**
nos dois casos: com `_FOTOS_MAX=2`, dividir a página descartaria em silêncio uma foto do usuário.

**Falha de rede → `None` → o PDF sai como hoje, sem a página** (mesmo fallback gracioso do
`_fetch_basemap`, DEC-004). Nenhum caminho novo pode derrubar a geração do relatório.

**BLOQUEANTE — [DEC-018](../docs/decisions/DEC-018.md), PROPOSTA e aguardando Felipe.** A revisão
automática do PR #138 reprovou (severidade ALTA) por dependência de rede nova não coberta por DEC: o
`REVIEW.md` (ALTA #5) só permite rede fora da carga do dashboard nas exceções DEC-004/010/011, e a
Esri é serviço novo. A DEC-018 foi redigida e traz o levantamento completo — inclusive a **licença**
(o `tou_summary.pdf` da Esri, 21/04/2025, exige assinatura do ArcGIS Online; o tile hoje é anônimo) e
o caminho de regularização (**ArcGIS Location Platform**, cadastro grátis, 2M tiles/mês, chave via
env). Duas perguntas abertas ao final da DEC esperam decisão.

**Hermeticidade da suíte (achado MÉDIA do mesmo review, corrigido):** `render_foto_satelite_ponto` é
chamada DENTRO de `gerar_pdf_ponto` e de `pages.py`, então testes que só mockavam a função final
passaram a fazer HTTP real. Corrigido na raiz com a fixture `autouse` `_sat_offline` no `conftest.py`,
em vez de remendar arquivo por arquivo.

**Testes:** `tests/unit/test_relatorio_pontual_foto_satelite.py` (15 casos, zero acesso a rede —
tile mockado por monkeypatch): matemática de tile, geometria pura da célula, fallback de rede,
tolerância a tile faltando, e inserção/ausência da página nos dois tamanhos.

---

## Relatório Pontual Censitário — satélite + mapas socioeconômico/residual + logo quadrada (2026-07-21, pedido de Vini)

> **Pedido de Vinicius (2026-07-21)**, a partir do uso real do Relatório Pontual em produção, em três
> partes: (1) **um slide novo ANTES do slide "Mapas de calor"**, com **dois mapas lado a lado** —
> socioeconomia da região e residual fitness; (2) uma **imagem de satélite** da região inserida **antes**
> desses mapas novos, com zoom aproximado para dar noção do que existe no ponto; (3) nos relatórios
> gerados pelo motor, o **indicador de concorrente** deixa de ser um pin-balão com a logo dentro e passa
> a ser a **própria logo em formato quadrado**. READ-ONLY sobre o M1 (§5 guardrail): nenhum dos três
> recalcula `score_priorizacao`, scores censitários, `setor_censitario_intersecao_area_1p5km`, raio de
> 1,5 km, carteira, plano ou artefatos oficiais — é camada de visualização/relatório.
>
> **Correção de premissa (medida no código em 2026-07-21).** O pedido descrevia o PDF como "5 páginas /
> tira 1x3". Está desatualizado — **e o CLAUDE.md §4 também**: hoje são **6 páginas base** (`/Count 6`) e
> o slide "Mapas de calor" já é um **grid 2x2 com 4 camadas** (`densidade`, `renda`, `score`,
> `renda_domiciliar`) — `censo_report.py:27-34,387,465`. A correção do §4 entra junto com o BLK-RELPON-10.
>
> **Ordem final de páginas alvo (8 base):** Capa → **Satélite (RELPON-11)** → **Socioeconomia + Residual
> (RELPON-10)** → Mapas de calor 2x2 → Concorrentes → Perfil do Bairro → Big Numbers → Realização. As
> páginas opcionais (Fotos, Info do imóvel, Viabilidade) permanecem onde estão.
>
> **Decisões de produto travadas com Vinicius em 2026-07-21 (gate deste ciclo):**
> - **D1 — "socioeconomia" = `score_setor_2022_calibrado`** (o composto socioeconômico do repo e camada
>   PRIMÁRIA operacional, §1). O termo "socioeconomia" não existia no repositório (0 matches em `tasks/`);
>   fica definido aqui.
> - **D2 — residual fitness em raio MAIOR (~5 km)**, rotulado explicitamente como escala diferente do mapa
>   ao lado. Motivo medido no dado real (Monte Carlo Voronoi, 200k pontos): no raio de 1,5 km cabem apenas
>   **3 a 5 hexágonos H3 res-7** e **68,9%** dos hexes valem exatamente 0 → sairia um mosaico chapado, não
>   um mapa de calor. Comparação no mesmo ponto (Av. Paulista): **639 setores censitários vs 5 hexes**.
> - **D3 — satélite = `Esri.WorldImagery`, largura 250–400 m** (não Google, não 100 m). Ver BLK-RELPON-11.
> - **D4 — logo quadrada vale no Pontual + Municipal**, via **função nova**, sem tocar `_render_pin_tile`
>   nem o atlas do pydeck. Ver BLK-RELPON-09.
>
> **Sub-decisões ABERTAS, a fechar no gate visual de cada bloco** (não bloqueiam o Planner):
> - **S1 (RELPON-10):** o `score` promovido ao slide novo **permanece** também no grid 2x2 (slide novo =
>   resumo/"hero"; 2x2 = detalhe técnico)? **Recomendação: SIM, permanece** — tirá-lo regride o
>   BLK-RELPON-01 e força o grid de 2x2 para 1x3, com churn extra e sem ganho claro.
> - **S2 (RELPON-09):** "30x30" é em **px do PNG fonte** (recomendado, comparável aos 40 px atuais) ou em
>   pt do PDF; e a âncora passa a ser o **centro** do quadrado + ponto fino de 2 px no local exato
>   (recomendado) ou a base do quadrado (preserva a semântica do pin atual).
>
> **Impacto cruzado a citar nos gates:** `BLK-WEB-05`/`BLK-WEB-08` (pendentes) exigem **paridade** com o
> "2x2 mapas" do Pontual e `BLK-WEB-02`/`BLK-WEB-07` exigem paridade com os **pins com logo** — os três
> blocos abaixo criam dívida de paridade para o piloto web.

---

- BLK-RELPON-09 (concluído 2026-07-22) — ver tasks/completed.md


---

- BLK-RELPON-10 (concluído 2026-07-22) — ver tasks/completed.md


---

- BLK-RELPON-11 (concluído 2026-07-22) — ver tasks/completed.md


---

- BLK-RELPON-12 (concluído 2026-07-22) — ver tasks/completed.md


---

- BLK-RELPON-13 (concluído 2026-07-24) — ver tasks/completed.md

### BLK-RELPON-07 — Mapas de calor legíveis (nomes de rua/bairro POR CIMA do choropleth)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (melhora a LEITURA do Relatório Pontual; READ-ONLY sobre M1) |
| **Esteira** | Block Orchestrator → Planner → `[GATE VISUAL — Felipe]` → Builder → QA |
| **Depende de** | — (aditivo sobre `censo_map`; OpenMapTiles self-host é passo posterior/opcional) |
| **Status** | Em revisão (PR aberto) |

**Contexto:** nos mapas de calor do Relatório Pontual (densidade/renda/score/renda domiciliar) o
choropleth **cobre as ruas e os nomes** — não dá para identificar QUAL área tem o número melhor/pior.
O realce `_STREET_*` recupera só as LINHAS de rua; os TEXTOS (nomes) continuam soterrados sob a cor.

**Objetivo:** ordem de camadas — o heat entra POR BAIXO e um tileset **só-rótulos** (transparente) é
composto POR CIMA, deixando "Av. X", "Bairro Y" legíveis sobre a cor (identificação da área).

**Escopo:** `_fetch_labels` (mosaico só-rótulos, lazy/best-effort via rede) + composição em
`_render_camada` alinhada ao extent do basemap; rótulos buscados **1x** e compartilhados pelas 4
camadas; flag `labels_overlay` (default on); a camada só-pins (concorrentes) não recebe overlay.
Fonte atual = CartoDB Voyager Only-Labels (keyless, mesma licença/atribuição do basemap Voyager).
Quando o OpenMapTiles self-host subir, trocar `_LABELS_TILE_URL` para o endpoint de rótulos do
tileserver (`openmaptiles-infra`, estilo `ultra-maptiler` já com a camada `transportation_name`).

**Fora de escopo (invioláveis):** score/pesos/intersecção de setores/raio/artefatos M1 (RENDER apenas);
subir a infra (passo posterior); dado de carteira/residual.

**Critérios de aceite:** nomes visíveis por cima do choropleth quando há basemap; **degradação graciosa**
(offline/sem rede → mapa sem nomes, byte-compatível com o anterior); testes cobrindo overlay
ligado/desligado; ruff + mypy + pytest verdes; **gate visual do Felipe**.

**Risco:** baixo (aditivo, gated por flag e por rede; caminho `basemap=False`/offline preservado).

---

### BLK-RELPON-14 — Unificação do gerador de PDF + remoção do slide "Imagem do Entorno" + borda no hex central + cadastro de 68 redes

| Campo | Valor |
|---|---|
| **Criticidade** | Alta |
| **Status** | **Em implementação** na branch `ciclo/BLK-RELPON-14-sync-piloto`. Emenda de 2026-07-28 à [DEC-011](../docs/decisions/DEC-011.md) **PENDENTE DE APROVAÇÃO por Vinicius** — merge exige a label `aprovado-humano`. |
| **ClickUp** | — |

> **Criticidade Alta porque emenda a DEC-011** (Alta): a representação do raio de 5 km nos painéis
> de Socioeconomia/Residual muda, e a emenda de 2026-07-22 daquela DEC dizia explicitamente "dois
> raios distintos, cada um **ROTULADO** no próprio mapa". Nada de M1: é camada de visualização/
> relatório (§5 guardrail permanente) — `setor_censitario_intersecao_area_1p5km`, raio de 1,5 km,
> `score_priorizacao`, carteira, plano e artefatos oficiais ficam INTOCADOS.

**Escopo (4 partes, decididas por Felipe):**

1. **Unificação do gerador de PDF — a estética CLÁSSICA vence.** Ela já era o default de produção
   no dashboard, na API e no bot; `gerar_pdf_relatorio_pontual_classico` passa a ser **A**
   implementação única. `gerar_pdf_relatorio_pontual_censitario` vira **wrapper fino** que só
   repassa os kwargs para a clássica, com `DeprecationWarning` — não quebra a branch piloto-web,
   que ainda a chama pelo nome. As funções de página duplicadas do template "recente"
   (`_cover_page`, `_socioeconomia_residual_page`, `_mapas_calor_page`, `_competitors_page`,
   `_perfil_bairro_page`, `_credit_page`, `_entorno_page`) são **DELETADAS**; as compartilhadas
   (`_big_numbers_page`, `_viabilidade_page`, `_fotos_imovel_page`, `_info_imovel_page`) **FICAM**.
2. **Slide "Imagem do Entorno" REMOVIDO por completo** — página do PDF, camada PNG `entorno`,
   constantes órfãs (`RAIO_ENTORNO_DISPLAY_KM`, `_ENTORNO_VALOR_LINHA`, o parâmetro `rotulo_escala`
   e o override local de `zoom_bump`) e a chave `entorno` em `CAMADAS_CENSITARIAS`/`MAP_LAYER_TITLES`.
   O PDF base cai de **8 → 7 páginas** (`/Count 7`, `PDF_SECTION_HEADERS` com 7 strings) e o teto com
   as opcionais de **12 → 11**. Os ordinais de `_tema_bicolor` são absolutos: liberar o `-1` que só
   servia a essa página **não desloca cor nenhuma**. Reverte o BLK-RELPON-11 (2026-07-22).
3. **Raio dos painéis Socioeconomia e Residual Fitness: o VALOR não muda, a REPRESENTAÇÃO sai.**
   `RAIO_RESIDUAL_DISPLAY_KM = 5.0` **PERMANECE** — continua definindo o ENQUADRAMENTO dos dois
   painéis; encolhê-lo reintroduziria o mosaico chapado de 3 a 5 hexágonos medido no gate de
   2026-07-21 (o motivo de existir do raio de exibição, DEC-011). O que sai é o desenho: **círculo
   azul removido** e **rótulo "Raio X km" removido** do rodapé e do título. No lugar, o **hexágono
   H3 res-7 que CONTÉM o ponto ganha uma borda fina de destaque** (`destaque_3857`,
   `_HEX_CENTRAL_EDGE_COLOR` = o mesmo azul do antigo círculo, `_HEX_CENTRAL_LINEWIDTH = 3`) — só a
   borda; o preenchimento continua vindo do `color_fn`, e sem hex central desenhável simplesmente
   não há borda. As camadas de 1,5 km seguem com círculo + rótulo, byte-a-byte idênticas.
4. **Cadastro de 68 redes** do coletor semanal (VinhoAbencoado/GymScraping, [DEC-013](../docs/decisions/DEC-013.md))
   em `dashboard/competitors.py`: as redes já tinham CSV em `concorrentes/Unidades/unidades_<slug>.csv`,
   mas caíam em `independente` porque `load_competitor_points` só itera `COMPETITOR_SPECS`. Entram nos
   três registros — `COMPETITOR_SPECS`, estilos de marca (`label`/`short` de 3 chars único/cores,
   reusando a paleta existente) e o registro de logos `logo_<slug>.png`. **10 redes ainda não têm PNG**
   no GymScraping: `preload_logos` ignora o arquivo ausente e o pin cai no fallback de sigla, que é o
   comportamento projetado. A normalização de nomes invertidos/slugs divergentes (`companhiafit`,
   `malibu`, `marrafit`, `matchfit`, `moinhosfit`) acontece na **cópia dos PNGs para a VPS**, não no
   registro.

**Gate humano:** aprovação da emenda de 2026-07-28 à DEC-011 por Vinicius (o único ponto que sai do
já decidido). As partes 1, 2 e 4 são estrutura de relatório/cadastro e não emendam DEC alguma.

**Testes:** contagem de páginas e headers para `/Count 7` (e `/Count 11` no teto com as opcionais,
em `test_relatorio_pontual_viabilidade.py`/`test_relatorio_pontual_orquestracao.py`); as 7 chaves de
`CAMADAS_CENSITARIAS`; a bateria da camada/página `entorno` **removida**; ausência de círculo e de
rótulo de raio nos dois painéis de 5 km; borda do hex central mudando pixels sem alterar a cor do
choropleth; equivalência do wrapper depreciado com a clássica (mesmo PDF + `DeprecationWarning`);
regressão de byte-identidade das camadas de 1,5 km.

**Impacto cruzado:** `BLK-WEB-*` (piloto web) importa `gerar_pdf_relatorio_pontual_censitario` pelo
nome — por isso o wrapper, e não a remoção do símbolo. Deploy: mudança em `dashboard/` **não**
dispara o rebuild da imagem da API — republicar manualmente e conferir o smoke de
`CAMADAS_CENSITARIAS` (7 chaves) em `docs/deploy_api_bot.md`.

**Docs atualizadas:** `docs/relatorio_pontual_censitario.md` (§3/§6/§7), `docs/decisions/DEC-011.md`
(emenda 2026-07-28, pendente), `docs/deploy_api_bot.md`, `docs/api_geoespacial_contrato.md`,
`docs/api_geoespacial_uso.md`, `docs/api_geoespacial_openapi.yaml`, `docs/arquitetura_app_atual.md`.

---

## Relatório Municipal — novo formato (2026-06-19, pedido de Vini)

> Novo formato de relatório que **coexiste** com o Relatório Pontual Censitário atual (que analisa
> uma região a partir do **raio de um ponto central**). O novo é um **relatório de município**:
> fica disponível para **geração e download após a seleção de um município** no dashboard. O escopo
> exato dos dados sai de um **template** que o Vini enviará e que será analisado como base, com
> ajustes ao longo do ciclo. Família do Relatório Censitário (malha real IBGE 2022), camada de
> visualização/relatório — **READ-ONLY sobre o M1** (§5 guardrail).

- BLK-RELMUN-01 (concluído 2026-06-22) — ver tasks/completed.md

- BLK-RELMUN-02 (concluído 2026-06-24) — ver tasks/completed.md

- BLK-RELMUN-03 (concluído 2026-07-02) — ver tasks/completed.md

- BLK-RELMUN-04 (concluído 2026-07-02) — ver tasks/completed.md



---

## Relatório Municipal — mapas com barra cinza (2026-07-01, pedido de Vini)

> Pedido de Vinicius a partir do uso real do Relatório Municipal: os mapas não preenchem todo o
> espaço disponível do painel, sobrando uma **barra cinza** (fundo do painel) acima/abaixo do mapa.
> Quer o mapa estendido para cobrir essa área cinza. Camada de visualização/relatório — **READ-ONLY
> sobre o M1** (§5 guardrail): nada recalcula score, gate do SAM, faixas ou artefatos oficiais.

- BLK-RELPON-03 (concluído 2026-07-01) — ver tasks/completed.md


---

## Trilha colaborador (Vini) — dashboard / PDF / UX (2026-06-09)

> Blocos derivados das tarefas pendentes do Vini (Vinícius, ClickUp id 101182135) na lista
> Motor de Expansão. Trilha de **visualização/relatório/UX**, executável em **paralelo** à trilha
> M1/infra/score do Felipe (arquivos quase disjuntos). Convenção: 1 bloco = 1 commit = 1 tarefa ClickUp.
> Fluxo: branch `ciclo/<ID>` → PR para `main` → CI verde → merge+deploy pelo Felipe
> (ver `docs/handoff_colaborador_run_cycle.md`).
> **READ-ONLY sobre o M1** em TODOS abaixo: nenhum recalcula `score_priorizacao`, pesos ou artefatos
> oficiais — é camada de visualização/relatório (§5 guardrail), **exceto BLK-FIX-08** (toca a camada
> PARALELA de mercado/residual, não o M1 oficial — ver o bloco).
> Causas-raiz são **hipóteses ancoradas no código** a confirmar pelo Planner.

- BLK-FIX-07 (concluído 2026-06-10) — ver tasks/completed.md


---

- BLK-FIX-08 (concluído 2026-06-10) — ver tasks/completed.md

- BLK-FIX-09 (concluído 2026-06-11) — ver tasks/completed.md


---

- BLK-FIX-10 (concluído 2026-06-12) — ver tasks/completed.md


---

- BLK-EST-03 (concluído 2026-06-15) — ver tasks/completed.md
- BLK-FIX-13 (concluído 2026-06-15) — ver tasks/completed.md
- BLK-EST-05 (concluído 2026-06-15) — ver tasks/completed.md


---

- BLK-FIX-07 (SUPERSEDED por BLK-FIX-13 em 2026-06-15) — o data-drift de `test_csvs_concorrentes_legiveis` foi resolvido pelo teste robusto a drift do BLK-FIX-13 (Vini); suíte verde confirmada no merge do PR #28 (3/3 passed). Ver tasks/completed.md (BLK-FIX-13).

---

- BLK-UI-01 (concluído 2026-06-16) — ver tasks/completed.md


---

- BLK-UI-07 (concluído 2026-06-19) — ver tasks/completed.md


---

- BLK-UI-09 (concluído 2026-06-19) — ver tasks/completed.md


---

## Novos blocos (2026-06-09, pedido de Felipe)

> Dois blocos derivados da análise de código com Felipe em 2026-06-09: (1) redefinição das condições
> do SAM (`BLK-SAM-01`) e (2) correção concreta dos overlays mortos do Mapa Territorial (`BLK-FIX-11`,
> Alternativa A). Ambos têm bloco "irmão" mais antigo/vago no backlog — ver a nota "Relacionado" em cada um.
> Causas-raiz abaixo estão **ancoradas no código** (file:line), confirmadas em leitura de 2026-06-09.

- BLK-SAM-01 (concluído 2026-06-10) — ver tasks/completed.md

- BLK-FIX-11 (concluído 2026-06-10) — ver tasks/completed.md

- BLK-SAM-02 (concluído 2026-06-10) — ver tasks/completed.md



---

## Projeto — API GeoEspacial (lista ClickUp `API GeoEspacial` / projeto `PROJETOS - DEG`)

> API complementar ao Motor de Expansão para integração com Telegram/WhatsApp, dando autonomia
> de estudos geoespaciais internos. Tarefa-pai ClickUp `86e1rtfcy`. Subtarefas: G1 (arquitetura/contrato,
> Felipe), G2 (backend/rotas, Juan), G3 (integração com o motor, Felipe+Juan), G4 (Telegram/WhatsApp, Juan).
> **Decisão de fonte (Felipe, 2026-06-09):** a API serve o relatório **on-demand a partir do motor**
> (importa `analisar_ponto_censitario_setores` + geradores de mapa/PDF e lê os Parquets locais de
> `data/outputs/setores_censitarios_2022_geo/`); **PostGIS fica como evolução futura, fora do MVP**.
> **Fronteira inegociável:** a API **importa, não edita** a camada `censo_*` (`censo_point.py`/`censo_map.py`/
> `censo_report.py`) — trata-os como interface estável, para não colidir com a trilha do Vini (dashboard/PDF).
> Código novo da API mora em `src/motor_expansao/api/` (pasta disjunta); dependências só no extra `[api]`
> do `pyproject.toml`, fora do deploy base do Streamlit. **READ-ONLY sobre o M1** (§5 guardrail): nada
> recalcula `score_priorizacao`, pesos, carteira, plano ou artefatos oficiais.

- BLK-API-01 (concluído 2026-06-10) — ver tasks/completed.md


- BLK-API-02 (concluído 2026-06-12) — ver tasks/completed.md


- BLK-API-03 (concluído 2026-06-12) — ver tasks/completed.md


- BLK-API-04 (concluído 2026-06-12) — ver tasks/completed.md


### BLK-API-05 — Endpoints estendidos M1/mercado (CONDICIONAL — roadmap pós-MVP)

| Campo | Valor |
|---|---|
| **Criticidade** | A definir (depende de reabrir a Decisão 3 para (b)) |
| **Status** | **Roadmap / condicional** — NÃO faz parte do MVP (Decisão 3 = (a)) |
| **ClickUp** | G3 (futuro) |

**Escopo (só se materializado):** `POST /lookup-hex` (lookup de hex M1) e/ou `GET /mercado/...` (camada
de mercado/residual), **READ-ONLY** (apenas leitura de artefatos; nada recalcula score/carteira/plano).
Permanece como roadmap até nova decisão de Felipe.

- BLK-API-06 (concluído 2026-06-12) — ver tasks/completed.md


- BLK-API-07 (concluído 2026-06-12) — ver tasks/completed.md


---

- BLK-API-08 (concluído 2026-06-12) — ver tasks/completed.md



---

- BLK-EST-04 (concluído 2026-06-12) — ver tasks/completed.md


---

## Tarefas pendentes

- BLK-OPS-06 (concluído 2026-05-29) — ver tasks/completed.md
- BLK-OPS-07 (concluído 2026-05-29) — ver tasks/completed.md
- BLK-PRD-01 (concluído 2026-05-29) — ver tasks/completed.md
- BLK-OPS-02 (concluído 2026-05-29) — ver tasks/completed.md
- BLK-OPS-02b (concluído 2026-05-29) — ver tasks/completed.md
- BLK-OPS-08 (concluído 2026-05-29) — ver tasks/completed.md

---

- BLK-OPS-12 (concluído 2026-07-13) — ver tasks/completed.md



---

### BLK-SCORE-05 — Viabilidade de proxy exógeno de demanda (pré-requisito de modelagem)

| Campo | Valor |
|---|---|
| **Status** | **SUPERSEDED por BLK-DIM-00..04 em 2026-06-12** |

**Supersessão (2026-06-12, decisão de Felipe).** O SCORE-05 era um diagnóstico read-only de
"existe proxy exógeno de demanda + maturação para tentar modelar?". Essa pergunta é exatamente a
**Camada 1 (aderência/penetração calibrada)** do novo `docs/modelo_dimensionamento_expansao.md` (CEO),
que a subsume e melhora: em vez de só diagnosticar, calibra com validação honesta (LOO-CV vs
baseline) e entrega um motor inverso de 4 camadas (Potencial → Captura → Dimensionamento m² →
Viabilidade financeira). A **disciplina de GO/NO-GO honesto** e os bloqueios estruturais
(viés de seleção, alvo pós-maturação, sinal exógeno ≈ nulo) do SCORE-05 foram DOBRADOS no
**BLK-DIM-01**. Camada paralela, **READ-ONLY sobre o M1** — DEC-001 (não recalibrar `score_priorizacao`)
permanece intacta. Detalhe e decomposição abaixo (epic BLK-DIM).

---

## Epic BLK-DIM — Motor de Dimensionamento e Viabilidade de Unidades (camada paralela)

> **Origem:** `docs/modelo_dimensionamento_expansao.md` (raiz do repo; spec/handoff do CEO, 2026-06-10),
> derivado dos testes do projeto externo `Análise Preditiva` (base de 54 academias). Substitui o
> BLK-SCORE-05.
>
> **Tese:** inverter a lógica — partir do potencial de mercado de cada região → dimensionar o imóvel
> ideal (m²/vagas) → fechar a conta financeira (faturamento, aluguel-teto, margem, payback, ROIC).
> 4 camadas: **1. Potencial** (hex → alunos potenciais via aderência calibrada) · **2. Captura**
> (market share via Huff/gravitacional) · **3. Dimensionamento** (alunos-alvo → m² pela curva de
> densidade) · **4. Unit economics** (determinística). As camadas 3-4 são prototipáveis JÁ; 1-2 são
> o coração e dependem de calibração nas unidades maduras.
>
> **Guardrail do epic (todos os blocos):** camada PARALELA, **READ-ONLY sobre o M1** — não toca
> `score_priorizacao`/`hex_score_estrutural`/pesos/artefatos oficiais (DEC-001 vigente). Não cria
> dependência de API ao vivo no dashboard de produção. Sem PII (`nome_unidade`) em relatórios.
>
> **Metodologia não-negociável (todos os blocos de modelagem — §7 do spec):** métrica oficial =
> **LOO-CV ou k-fold repetido SEMPRE contra baseline da média**; BANIR R² in-sample e
> `fit(X,y)→predict(X)`; começar simples (linear regularizado/GLM), só subir complexidade se ganhar
> honestamente sobre o baseline; toda saída com **intervalo de predição + flag de extrapolação**.
>
> **Sequenciamento recomendado:** **DIM-03 primeiro** (determinístico, usa só dados que já temos,
> valor imediato e desacoplado) → DIM-00 → DIM-01 (gate GO/NO-GO) → DIM-02 → DIM-04. Camadas 1-2 só
> avançam se as lacunas de dados fecharem em DIM-00.
>
> **Insumos — auditoria de 2026-06-12 (estado real do repo):**
> - ✅ EXISTE: 54 unidades Ultra com faturamento/pagantes/alunos/**metragem m²**/ticket/alunos-por-m²
>   (`data/staging/unidades_ultra_performance_hex.parquet`, 57 cols); concorrência OSM 3.296 unidades
>   ~35 redes com lat/lng (`data/staging/concorrentes_mapeados.parquet`); camada de mercado/residual
>   (`hexagonos_mercado_mapeado.parquet`, 135 cols); helper de catchment `analisar_entorno_ponto`
>   (1,5 km); backtest helpers (`analysis/score_backtest.py`, `feature_backtest_mercado.py`).
> - ❌ FALTA no repo (Felipe vai disponibilizar — 2026-06-12): **série diária das ~60 maduras**
>   (vendas/cancelamentos/churn/rampa de maturação); **datas de abertura por unidade**
>   (`maturacao_status` é constante `maturacao_indisponivel` em 100% hoje — gate G1 da DEC-001 segue
>   aberto); **`ULTRA padrão - Simulador Financeiro.xlsx`**; `modelo_demanda.py`/`teste_densidade.py`
>   (referência portável). m²/capacidade real de concorrentes (hoje só proxy 2.500 alunos).

---

- BLK-DIM-00 (concluído 2026-06-13) — ver tasks/completed.md


---

> **Spikes BLK-DIM-01..04** (1ª rodada do loop, 2026-06-13): **auditados e SUPERSEDED**, mantidos
> como referência nos branches `ciclo/BLK-DIM-01..04` (não mergeados — ver BLK-LOOP-02). Detalhe e
> motivo de cada um em `tasks/completed.md`.
>
> - BLK-DIM-01 → superseded por **BLK-DIM-01R** (R²=0.897 era artefato de fixture).
> - BLK-DIM-02 → superseded por **BLK-DIM-02R** (fallback previsor=alvo, vazamento).
> - BLK-DIM-03 → superseded por **BLK-DIM-03R** (números mágicos calibrados ao teste).
> - BLK-DIM-04 → superseded por **BLK-DIM-06** (backtest in-sample disfarçado).

---

- BLK-DIM-01R (concluído 2026-06-13) — ver tasks/completed.md


---

- BLK-DIM-05 (concluído 2026-06-13) — ver tasks/completed.md


---

- BLK-DIM-06 (concluído 2026-06-13) — ver tasks/completed.md



---

- BLK-DIM-07 (concluído 2026-06-15) — ver tasks/completed.md
- BLK-DIM-08 (concluído 2026-06-15) — ver tasks/completed.md
- BLK-DIM-02R (concluído 2026-06-15) — ver tasks/completed.md



---

### BLK-DIM-10 — Bifurcação estratégica da epic: demanda não é previsível pela geografia de mercado (decisão de Felipe)

| Campo | Valor |
|---|---|
| **Criticidade** | **Estratégica** (define o rumo da epic BLK-DIM; READ-ONLY sobre M1) |
| **Esteira** | `[DECISÃO HUMANA — Felipe]` — NÃO loop-safe (escolha de produto/rota) |
| **Status** | **RESOLVIDO pela evidência (2026-06-15)** — registro de decisão; não é mais trabalho aberto |
| **Origem** | síntese dos resultados DIM-01R / DIM-05 / DIM-08 / DIM-02R + spike de densidade (2026-06-15) |

> **RESOLUÇÃO (2026-06-15):** o spike de densidade (`data/analysis/densidade_contexto.md`) fechou a
> dúvida — a geografia **também** não prevê a densidade (alunos/m²) (4º NO-GO; R²_LOO −0,01), e o único
> sinal usável é a **curva tamanho→densidade** (metragem, R²_LOO +0,10). A base geográfica interna está
> **esgotada**. Decisão tomada: **Caminho A vira o rumo agora** → materializado no **BLK-DIM-11** (esteira
> property-first / viabilidade). **Caminho B (BLK-DIM-DATA) é REDEFINIDO**: só faz sentido atrás de
> **atributos de imóvel** (visibilidade, fluxo, esquina) — NÃO de mais dado demográfico, que 4 NO-GOs já
> provaram não carregar sinal. **Formalizado como DEC-009** (CLAUDE.md §8, aprovada por Felipe em
> 2026-06-15). Este bloco fica como **registro de decisão** (não loop-safe, não é tarefa); a execução
> é o BLK-DIM-11 (engine, concluído) + BLK-DIM-12 (UI).

**Onde chegamos (evidência):** depois de **estressar ao máximo o dado interno** (sub-trilha DIM-07→08 + spike de densidade),
temos **três NO-GOs honestos** convergindo: a demanda/viabilidade de um ponto **NÃO é previsível a partir
da geografia de mercado** que temos (pop, renda, concorrência, residual), em raio nenhum, com feature
nenhuma disponível.

| Camada | Veredito |
|---|---|
| 1 — Potencial (pop+renda, DIM-01R) | NO-GO (R²_LOO −0,01) |
| 1 — + features exógenas (DIM-05) | NO-GO |
| 1 — residual discrimina viabilidade? (DIM-08) | **NO-GO (AUC 0,48 ≈ acaso)** |
| 2 — Captura/Huff (DIM-02R) | GO técnico, mas não agrega (LOO −0,25) |
| 3+4 — Dimensionamento m² + DRE (DIM-03R/06) | **GO** (R²=+0,23, bate baseline) |

A metade que **funciona** é o dimensionamento por m² — mas ele **consome** demanda como entrada, não a
produz. O sinal que separa uma Carapicuíba (1.299) de uma vencedora (6.251) está provavelmente em
**execução/operação, micro-localização ou variáveis demográficas que faltam** (idade 18-45, vínculo CLT),
não na geografia agregada.

**A bifurcação (escolher o rumo):**

- **Caminho A — Repaginar o motor para VIABILIDADE / BREAK-EVEN (ROI imediato, usa o que funciona):**
  inverter a pergunta de *"quantos alunos este ponto terá?"* (sem resposta) para *"quantos alunos este
  imóvel **precisa** para ser viável, e isso é plausível aqui?"*. Usa o goal-seek que o DIM-03R já tem
  (alunos mínimos viáveis, aluguel-teto). A demanda entra como **premissa explícita** (input humano ou
  faixa de comparáveis), nunca como previsão cravada. Entregável sem dado novo. → viraria um bloco
  sucessor (ex.: BLK-DIM-11).
- **Caminho B — BLK-DIM-DATA (a aposta):** buscar o sinal que falta (microdados IBGE idade 18-45 / CLT, ou
  proxy Gympass/Wellhub) e re-rodar a calibração. É o único caminho que poderia **restaurar previsão de
  verdade** — mas pode dar NO-GO de novo (§5/DEC-001 avisaram que o sinal pode ser intrinsecamente fraco).
  Bloco já existe (BLK-DIM-DATA), manual/não loop-safe.

**Cautela registrada:** o método de **comparáveis/análogos** NÃO é um atalho — o DIM-08 mostrou que os
eixos atuais (pop/renda/concorrência) não separam viável de inviável, então "pontos parecidos" nesses
eixos teriam resultados igualmente dispersos. Só ajudaria com eixos novos (tipo de cidade, visibilidade,
imóvel) — o que recai na questão de dado (Caminho B).

**Recomendação (Claude):** fazer os dois em ordem — **A agora** (entrega valor sem dado novo e repaginia o
papel do motor de "prever alunos" para "stress-testar viabilidade") e **B como aposta** (o teste honesto de
"é dado ou é intrínseco?"). Se B vier NO-GO, encerra-se a questão com evidência e fica-se com o motor de
viabilidade — que já é valioso.

**Guardrail:** READ-ONLY sobre o M1 (DEC-001/DEC-008) em qualquer caminho; a priorização de **onde** olhar
segue com o M1/censitário (camada executiva, intacta) — o que se perde é só a contagem fina de alunos por
ponto, não a triagem regional. Após a escolha de Felipe, formalizar como **DEC-009** (CLAUDE.md §8).

---

- BLK-DIM-11 (concluído 2026-06-15) — ver tasks/completed.md


---

- BLK-DIM-12 (concluído 2026-06-15) — ver tasks/completed.md


---

- BLK-DIM-13 (concluído 2026-06-17) — ver tasks/completed.md


---

- BLK-DIM-14 (concluído 2026-06-17) — ver tasks/completed.md


---

- BLK-DIM-16 (concluído 2026-06-17) — ver tasks/completed.md


---

### BLK-DIM-09 — Crosswalk manual das unidades não-casadas (CONDICIONAL — só se o match do 07 deixar lacuna material)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (recupera N perdido no join; READ-ONLY sobre M1) |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA]` → Builder → QA |
| **Depende de** | **BLK-DIM-07** (lista de não-casadas + taxa de match) |
| **Status** | Pendente (condicional — só dispara se o match automático do 07 ficar abaixo do aceitável) |
| **Autonomia** | **manual (NÃO loop-safe)** — resolver nomes ambíguos (várias unidades por cidade, nome interno vs. cidade) exige julgamento humano; NÃO marcar loop-safe. |

**Contexto:** o geocoding online deixou de ser necessário — SkyFit (`concorrentes/Unidades/unidades_skyfit.csv`,
481 coords) e Engenharia (`.../unidades_engenharia_do_corpo.csv`, 62 coords) **já têm lat/lng locais**. O
problema real não é coordenada, é o **join por nome**: match exato normalizado = **0%** (convenções
divergentes — ver caveat do BLK-DIM-07). O 07 resolve o grosso por chave cidade+UF (SkyFit) e crosswalk
fuzzy (Engenharia); este bloco só existe para a **cauda de unidades ambíguas** que sobrar (ex.: várias
SkyFit na mesma cidade; nome interno da Engenharia sem cidade explícita).

**Objetivo:** se a taxa de match automático do 07 ficar abaixo do aceitável, construir um **crosswalk
revisado por humano** (`unidade_alunos ↔ unidade_coords`) para as não-casadas, anexar à base multi-rede e
**re-rodar o BLK-DIM-08** com N recuperado, reportando o ganho/perda honesto.

**Escopo permitido (só se acionado):** crosswalk manual auditável (CSV de-para versionável SEM PII —
só identificadores de unidade); reanexar à base; re-rodar discriminação/variância; reportar quantas
unidades foram recuperadas e o impacto no veredito.

**Fora de escopo (invioláveis):** geocoding online (desnecessário); persistir PII/endereço bruto;
score/pesos/artefatos M1; dependência de API ao vivo no dashboard; "casar por centroide de cidade" quando
há várias unidades na mesma cidade (ambiguidade tem que ser resolvida, não chutada).

**Critérios de aceite:** crosswalk revisado e auditável; nº de unidades recuperadas reportado;
BLK-DIM-08 re-rodado com veredito honesto de ganho/perda; ZERO PII em disco; ZERO M1.

**Risco:** baixo (trabalho manual pequeno). Pode concluir que a cauda não-casada é imaterial → a sub-trilha
encerra com o N do 07 (resultado válido).

---

### BLK-DIM-DATA — Aquisição de dado para destravar a Camada 1 (demanda) — o gargalo real

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (engenharia de dados pesada/aquisição externa; READ-ONLY sobre M1) |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA OBRIGATÓRIA]` → Builder → QA |
| **Depende de** | **BLK-DIM-01R** (estabeleceu o NO-GO e a estrutura de calibração) |
| **Status** | Pendente |
| **Autonomia** | **manual (NÃO loop-safe)** — downloads grandes/fontes externas; NÃO se limita a `data/staging`; exige gate humano. NÃO marcar loop-safe. |

**Contexto / por que existe:** o BLK-DIM-01R provou, com dado real (n=53, alvo `log(pagantes)` absoluto,
LOO honesto), que a demanda **NÃO é calibrável** com pop+renda (`R²_LOO=−0,013`, NO-GO) e o BLK-DIM-05
mostrou que as features disponíveis no Censo 2022 **Básico** não ajudam. As features que decidiriam a
demanda (**faixa etária 18-45**, vínculo formal/CLT, % ocupados) **não existem no Censo Básico por
setor** — exigem microdados/amostra do IBGE (~10 GB) ou um proxy exógeno. **O gargalo é DADO, não
algoritmo** (exatamente o que a DEC-001 e o §5 do spec avisaram). Este bloco ataca o gargalo.

**Objetivo:** avaliar (viabilidade/custo/legalidade) e, se viável, **materializar** ao menos um sinal
novo que possa virar a Camada 1 de NO-GO → GO, e **re-rodar a calibração do BLK-DIM-01R** com ele,
reportando honestamente se o `R²_LOO` melhora materialmente.

**Escopo permitido (candidatos — diagnosticar antes de baixar tudo):**
- **Microdados/amostra Censo 2022 IBGE**: faixa etária 18-45, vínculo formal, renda do trabalho por
  setor/área de ponderação. Avaliar cobertura, granularidade (área de ponderação ≠ setor), tamanho e
  licença antes de baixar. Materializar features por catchment (reuso do helper censitário).
- **Proxy exógeno de demanda**: penetração Wellhub/Gympass (já há `sinal_wellhub`/`n_parcerias_wellhub`
  no dataset de validação) — medir cobertura e se é exógeno ou colado a unidades existentes.
- **Reduzir viés de seleção**: a rede já tem ~88 unidades na Growth API (vs 53 maduras) — incorporar
  mais unidades (incl. em rampa, com `inauguracao`) para ampliar N e a variação de contexto.
- Re-rodar `aderencia.py` (BLK-DIM-01R) com a(s) feature(s) nova(s); LOO-CV vs baseline; veredito.

**Fora de escopo (invioláveis):** score/pesos/artefatos M1 (READ-ONLY; DEC-001); dependência de API ao
vivo no dashboard; persistir PII (microdados podem ter PII — agregar na borda, nunca em disco);
inventar feature sem fonte auditável; alterar o método/raio censitário.

**Critérios de aceite:** diagnóstico de disponibilidade/custo/legalidade das fontes; se houver fonte
viável, feature materializada por catchment + re-calibração honesta com veredito GO/NO-GO documentado
(IC/N/confounds); ZERO PII em disco; ZERO escrita em M1; reprodutível.

**Risco:** médio-alto de esforço (download/limpeza de microdados é pesado). O resultado pode seguir
NO-GO — e isso encerra honestamente a questão "dá para modelar demanda por hex hoje?". **Não loop-safe:
exige decisão humana sobre quais fontes baixar e validação de licença/LGPD.**

---

- BLK-DIM-17 (concluído 2026-06-22) — ver tasks/completed.md


---

- BLK-DIM-18 (concluído 2026-07-01) — ver tasks/completed.md



---

- BLK-SEC-03 (concluído 2026-07-13) — ver tasks/completed.md


---

### BLK-SEC-03-FU1 — Forçar 2FA no Authelia + revisão de acesso do dashboard (P4 do SEC-03)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (acesso ao dashboard; não toca M1/score) |
| **Prioridade** | Média |
| **Esteira** | interativa com gate humano (VPS §6) — **agendar com o TIME AVISADO** |
| **Status** | Pendente |
| **Origem** | P4 do BLK-SEC-03 (concluído 2026-07-13), adiado por decisão de Felipe para não trancar o time |
| **Autonomia** | **manual (NÃO loop-safe)** — VPS + coordenação de pessoas |

**Escopo:** (1) avaliar/forçar `two_factor` para o grupo `ultra_team` no Authelia
(`authelia/configuration.yml`), com prazo prévio para o time cadastrar TOTP e virada em horário
combinado com todos disponíveis; rollback = voltar a policy a `one_factor` (1 edit). (2) Revisão de
acesso em `authelia/users_database.yml`: remover usuários obsoletos, definir offboarding (revogar ao
sair) e periodicidade da revisão. Documentar em `docs/infra_producao.md`.

**Risco:** trancar o time fora do dashboard se virar sem aviso — mitigado por agendamento + rollback
de 1 edit.

---

- BLK-SEC-04 (concluído 2026-07-13) — ver tasks/completed.md




---

- BLK-ORQ-02 (concluído 2026-07-19) — ver tasks/completed.md




---

### BLK-PROD-01 — Refatoração completa do repositório

Status: pendente
Criticidade: estratégica
Prioridade: média
Tipo: refatoração
Skill recomendada: /run-cycle (fluxo estratégico)
Resumo: Migrado do PRD.md. Próxima etapa de planejamento estrutural do repositório.
Dependências: nenhuma bloqueadora
Observações: requer planejamento detalhado antes de execução. Não iniciar sem aprovação.

---

### BLK-PROD-05 — Geocodificação offline/online de endereço

Status: pendente
Criticidade: alta
Prioridade: baixa
Tipo: feature
Skill recomendada: /run-cycle
Resumo: Implementar geocodificação de endereço apenas se dependência externa for
aprovada ou base local viável identificada.
Dependências: aprovação de dependência externa ou base local.

---

- BLK-PROD-06 (concluído 2026-07-07) — ver tasks/completed.md


---

### BLK-PROD-07 — Cenários salvos por usuário e histórico de decisão

Status: pendente
Criticidade: alta
Prioridade: baixa
Tipo: feature
Skill recomendada: /run-cycle
Resumo: Apenas se o dashboard evoluir para produto web interno com múltiplos usuários.
Dependências: decisão de produto sobre evolução para web interno.

---

## Epic BLK-VIAB — Integração de Viabilidade de Imóvel Candidato (imóvel-first; camada paralela READ-ONLY sobre o M1)

> Continuidade da **DEC-009** (property-first) e do motor `dimensionamento/viabilidade_ponto.py` (BLK-DIM-11 concluído).
> Costura o produto completo: **imóvel real → curva m²→alunos → DRE → margem de segurança (aluguel-teto vs pedido)**,
> com a **demanda SEMPRE como premissa explícita** (NUNCA prevista pela geografia — DEC-009). A triagem demográfica
> entra só como CONTEXTO do catchment, não como pré-filtro.
> **READ-ONLY sobre o M1 em TODOS os blocos** (§5): nenhum recalcula `score_priorizacao`/pesos/carteira/plano/artefatos
> oficiais. Saídas em `data/staging/` (paralela, gitignored) + `data/analysis/` (gitignored).
> **Achado 2026-07-07 embutido nos guardrails:** o alvo de demanda honesto é **alunos_totais reais** (Ultra+Smart+Eng+Sky),
> NÃO `membros` (agregador corporativo, ~1/3 da demanda, e circular com o Huff). Ver memória
> `huff-membros-circularidade-teto-demanda`.
> **NÃO entram nesta epic loop-safe (blocos HUMANOS separados):** geocoding ao vivo dos endereços (rede — DEC-010),
> a tela do operador no dashboard (UI — lição do BLK-UI-10), e a materialização do ranking como artefato de comitê
> (DEC + gate, padrão BLK-ATR-05).

- BLK-VIAB-01 (concluído 2026-07-07) — ver tasks/completed.md


---

- BLK-VIAB-02 (concluído 2026-07-07) — ver tasks/completed.md


---

- BLK-VIAB-03 (concluído 2026-07-07) — ver tasks/completed.md


---

- BLK-VIAB-04 (concluído 2026-07-07) — ver tasks/completed.md


---

- BLK-VIAB-05 (concluído 2026-07-08) — ver tasks/completed.md

> **Roadmap de produto (síntese 2026-07-08, `docs/estado_dos_modelos.md`).** Os blocos abaixo
> operacionalizam o produto property-first. Ordem de valor: **VIAB-09 (UI end-to-end)** é o de maior
> impacto; VIAB-06/07 são loop-safe (guardrail + alavanca de precisão); VIAB-08/10 são humanos
> (rede/dado externo). READ-ONLY sobre o M1 em todos.

- BLK-VIAB-06 (concluído 2026-07-08) — ver tasks/completed.md


---

- BLK-VIAB-07 (concluído 2026-07-08) — ver tasks/completed.md


---

### BLK-VIAB-08 — Geocoding + catchment dos imóveis candidatos

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (rede ao vivo — precedente DEC-010; **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir (Felipe/Vini). |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA — rede/anti-PII]` → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | **BLK-VIAB-01** (candidatos limpos com `flag_sem_coord`). |
| **Autonomia** | **manual (NÃO loop-safe)** — geocoding é rede ao vivo (DEC-010/Nominatim); loop não faz ingestão ao vivo; exige gate humano. NÃO marcar loop-safe. |

**Contexto.** Os 23 candidatos limpos (BLK-VIAB-01) estão **100% sem coordenada**; o catchment do motor
(pop/renda do entorno, flag de zona-morta) só roda com `lat/lng` (hoje o batch VIAB-03 roda coordless).

**Objetivo.** Geocodificar os endereços (reusando `maps_geocoder`/Nominatim, DEC-010: cache local, fallback,
anti-PII) e ligar o `setores_df` (catchment) no batch de viabilidade, ativando pop/renda do entorno + zona-morta.

**Guardrail.** DEC-010 (cache `data/cache/geocode/`, fallback offline gracioso, timeout, anti-PII); §5 READ-ONLY M1.

---

### BLK-VIAB-09 — UI de Viabilidade de Imóvel no dashboard (produto end-to-end)

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (superfície do produto property-first; **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir (Felipe/Vini) — **maior impacto do roadmap**. |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA — UX/visual]` → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | **BLK-VIAB-03** (batch/ranking) + **BLK-VIAB-06** (guardrail de envelope). BLK-VIAB-08 (catchment) opcional/aditivo. |
| **Autonomia** | **manual (NÃO loop-safe)** — UI exige revisão visual humana (lição do BLK-UI-10: loop marca verde por teste, mas UX precisa de olho). NÃO marcar loop-safe. |

**Contexto.** Motor (`viabilidade_ponto`), batch e ranking por margem de segurança já existem e estão validados
(BLK-VIAB-03/04). Falta a **tela do operador** — o "produto completo" property-first da DEC-009.

**Objetivo.** Aba/seção no dashboard onde o operador traz um imóvel (m² + aluguel + endereço) — ou seleciona da
base — e recebe: faixa de alunos (p10/p50/p90), break-even, **aluguel-teto vs pedido (margem de segurança)**,
grade de sensibilidade demanda×aluguel, e o **aviso de envelope** (BLK-VIAB-06). Demanda SÓ como premissa (DEC-009).

**Guardrail.** §5 READ-ONLY M1 (visualização não recalcula score/carteira/plano/artefatos); usa faixas, não pontos.

> **RE-ESCOPO (2026-07-10, varredura de código — aprovado por Felipe):** a tela do operador **JÁ EXISTE**
> (`render_viabilidade_ponto`, `pages.py:3572`, aba "Viabilidade" — entregue nos BLK-DIM-12..16): faixa
> p10/p50/p90, break-even, aluguel-teto vs pedido, grade de sensibilidade, contexto de catchment/zona-morta,
> projeção 60 meses e export Excel já renderizam. **Escopo restante deste bloco:** (i) exibir o aviso de
> extrapolação quando `resultado.flag_fora_envelope` (BLK-VIAB-06 — hoje a UI NÃO lê a flag; zero matches
> de "envelope" em `dashboard/`); (ii) expor o param opcional `formato` (BLK-VIAB-07, GO −9,1 p.p. MAPE)
> na chamada de `pages.py:3750-3764` (selectbox opcional, default None = comportamento atual);
> (iii) OPCIONAL: seletor "carregar candidato da base" lendo `imoveis_candidatos_limpos.parquet`;
> (iv) testes de integração da tela (hoje zero). **Complexidade revista: Baixa** (Média só se incluir iii).

---

### BLK-VIAB-10 — Aquisição de metragem externa para ampliar a curva

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (destrava a melhoria da curva; **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir (Felipe/Vini). |
| **Esteira** | Block Orchestrator → Planner → `[GATE HUMANO — aquisição/licença de dado]` → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | — (relacionado a **BLK-DIM-DATA**; e ao NO-GO do **BLK-VIAB-05**). |
| **Autonomia** | **manual (NÃO loop-safe)** — aquisição de dado externo (fora de `data/staging`); exige gate humano. NÃO marcar loop-safe. |

**Contexto.** A curva de densidade só tem **112 unidades com metragem** (Ultra 54 + Eng Corpo 58). Smart Fit e
Sky Fit têm alunos totais mas **nenhuma coluna de metragem** — por isso o BLK-VIAB-05 bloqueou. O gargalo para
melhorar a curva é **metragem por unidade**, não alunos.

**Objetivo.** Adquirir metragem por unidade de mais redes low-cost (fonte externa a disponibilizar) para ampliar
a base de calibração DENTRO do formato Ultra, e revalidar a curva (reabre BLK-VIAB-05 sob DEC-008).

**Guardrail.** §5 READ-ONLY M1; procedência/licença do dado no gate humano.

---

### BLK-VIAB-11 — Recalibrar o custo de PESSOAL do simulador de viabilidade (fixo → % da receita)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (recalibra um coeficiente de custo da camada paralela de Dimensionamento/Viabilidade; muda a saída de go/no-go do simulador, mas **READ-ONLY sobre o M1** — não toca score/pesos/carteira/plano/artefatos oficiais). |
| **Prioridade** | A definir (Felipe/Vini) — pedido explícito de Felipe (2026-07-17). |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA — confirmar o ratio com a controladoria]` → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | **BLK-DIM-03R** (que fixou os coeficientes do DRE, incluindo `SIM_PESSOAL_MES`). Relacionado a **BLK-VIAB-04** (backtest N=112, para checar que a mudança não piora a validação). |
| **Autonomia** | **manual (NÃO loop-safe)** — muda a economia que a ferramenta recomenda; o **valor do ratio** (~25%) é decisão de produto/finanças que precisa de gate humano (N=6 nas DREs). Mecanicamente é simples, mas NÃO marcar loop-safe. |

> **ATENÇÃO — a ESTRUTURA deste bloco já foi implementada, e de forma DIFERENTE da escrita abaixo (FIN-VIAB-01,
> decisão de Felipe em 2026-07-24). Não executar o texto original ao pé da letra: ele reintroduziria o defeito que
> acabou de ser corrigido.** O que existe hoje no motor: `SIM_FOLHA_PCT` dimensiona a folha pelo **faturamento
> MADURO** (regime pleno, a preços do ano 1) e o valor resultante é **FIXO desde o mês 1**, reajustando só
> anualmente — a equipe é contratada **antes** dos alunos chegarem. Logo a folha é **custo FIXO**, saiu de
> `fator_receita_para_ebitda` (k: 0,628985 → 0,798985) e entrou em `Premissas.custo_fixo_total_mes()`. As frases
> "a folha deve acompanhar o faturamento de cada mês, inclusive menor na rampa" (Escopo) e "folha escala com a
> receita" (Aceite item 3) descrevem a regra **ANTIGA/DESCARTADA** — a folha percentual do mês diluía o custo na
> rampa, subestimava a queima de caixa do mês 1 em ~R$33,3 mil e deixava o break-even otimista (840,6 em vez de
> 1.152,0 alunos totais no caso de referência). **O que continua PENDENTE deste bloco é só o NÍVEL do percentual**
> (0,17 vigente x 0,25–0,26 apurados nas 6 DREs), com a controladoria; ver `PREMISSAS_VIABILIDADE.md` §4.1 e
> `docs/nota_impacto_fin_viab_01.md`.

**Contexto.** O simulador (`dimensionamento/simulador.py::viabilidade`) modela a folha como um **custo fixo absoluto**
`SIM_PESSOAL_MES = R$50.128,16` (`dimensionamento/config.py:103`), aplicado **igual a toda unidade**, independente de
receita, metragem ou região. Seis DREs gerenciais reais (Augusta, Bangu, Cabo Frio, Icaraí, Praia Grande, Vila
Guilherme; jun–jul/2026) mostram que **isso está errado nos extremos**: a folha real varia de **R$38k a R$99k/mês**,
e o R$50k fixo **subestima unidades de alto faturamento** (Praia Grande: folha real ≈ R$99k) → **infla o EBITDA em
~R$49k/mês** e **super-aprova unidades grandes**.

**Evidência (das 6 DREs).** A folha é **estável como % da RECEITA BRUTA — média 26%, CV 0,16** (baixa dispersão), e
**instável por m² — CV 0,34** (61→40 R$/m², cai com o tamanho = economia de escala). Ou seja, **pessoal acompanha
VOLUME/faturamento, não metragem.** SP vs RJ: pessoal% ~idêntico (25% em ambos) → **sem ajuste regional para folha**
(ao contrário de energia — fora deste bloco).

**Objetivo.** Trocar, **apenas para o custo de pessoal**, o valor fixo por um **percentual da receita bruta
(faturamento)**: `pessoal = SIM_PESSOAL_PCT × faturamento`, com `SIM_PESSOAL_PCT` default **0,25–0,26** (a confirmar
com a controladoria; parametrizado). Isso torna a folha auto-consistente com o design "demanda é premissa" (mais
alunos assumidos → mais folha, automático) e corrige a distorção nas caixas grandes.

**Escopo (ENXUTO — só pessoal).**
- **Incluído:** `dimensionamento/config.py` (nova constante `SIM_PESSOAL_PCT`); `simulador.py::viabilidade`,
  `gerar_serie_mensal` (rampa — a folha deve acompanhar o faturamento de cada mês, inclusive menor na rampa),
  o solver `aluguel_teto` e `grade_sensibilidade` (propagar a nova lógica); `viabilidade_ponto.py` se repassar `pessoal_mes`.
- **Backward-compat:** manter o parâmetro `pessoal_mes` como **override opcional** (se o chamador passar um absoluto,
  usa o absoluto; caso contrário, usa `SIM_PESSOAL_PCT × faturamento`). Nenhum chamador quebra.
- **FORA de escopo (follow-up, NÃO fazer agora):** água/luz/energia (que é mista: m² + região/clima + volume), IPTU
  (melhor virar input), multiplicador regional. Ficam como bloco sucessor **BLK-VIAB-12** (custos de ocupação).

**Aceite.**
1. `SIM_PESSOAL_PCT` adicionado em `dimensionamento/config.py`; folha calculada como `pct × faturamento` no
   `viabilidade()` e na série mensal (rampa).
2. **Sanity check:** no faturamento da unidade de referência (~R$193k, onde `50.128/193.000 ≈ 0,26`), o novo modelo
   reproduz ≈ R$50k → sem quebra de continuidade no ponto de calibração antigo.
3. **Teste unitário:** folha escala com a receita — uma unidade de faturamento alto (ex.: R$487k) recebe folha maior
   que uma de R$145k; o override `pessoal_mes` explícito continua vencendo.
4. **Backtest re-rodado (BLK-VIAB-04, N=112 / 54 Ultra):** MAPE e ranking por margem de segurança **não pioram**
   (esperado: melhora nas unidades grandes). Registrar o antes/depois.
5. **READ-ONLY M1:** zero escrita em score/pesos/`hex_score_estrutural`/carteira/plano/artefatos oficiais; suíte verde.

**Guardrail.** §5 permanente — camada paralela de Dimensionamento, READ-ONLY sobre o M1 (DEC-001 intacta). Não altera
`config.py` raiz do M1; só `dimensionamento/config.py` (constantes locais da camada, precedente BLK-DIM-00).

**Ressalva.** **N=6 DREs** (4 com metragem), viés RJ/SP, possível ramp-up. O **ratio ~25%** é direção robusta
(CV 0,16), mas o valor exato (25 vs 26%) deve ser **confirmado pela controladoria** e com mais DREs; por isso
`SIM_PESSOAL_PCT` fica **parametrizado**. O bug de receita +33% (BLK-DIM-13, split 69/31 balcão/agregador) **já está
corrigido** e é ortogonal a este bloco.

**Nota — FIN-VIAB-01 (2026-07-24): a ESTRUTURA já foi entregue; falta só o NÍVEL.** O ciclo FIN-VIAB-01
(reconciliação do simulador) **ativou a folha percentual** no núcleo: `SIM_FOLHA_PCT = 0,17` do **faturamento
bruto** (`dimensionamento/config.py`), consumido por `simulador.py` na série mensal completa — a folha passou a
**escalar com o volume**, com override absoluto (`pessoal_mes_override`) preservado para os chamadores históricos.
`SIM_PESSOAL_MES = R$50.128,16` vira **legado** (não alimenta mais a folha; segue só como default da assinatura de
`viabilidade()`/`gerar_serie_mensal()`). O **0,17** foi escolha de Felipe (2026-07-24) para ficar ~no status quo de
nível (R$50.128 / R$277.676 = 18,05% no caso de referência) e permitir atribuir o delta do ciclo à mudança de
ESTRUTURA, não de nível. **Este bloco segue pendente APENAS para calibrar o NÍVEL** — 17% (vigente) vs **25-26%**
(as 6 DREs) — **com a controladoria**. Impacto **re-medido no gate de fechamento, com a anuidade LIGADA** (caso
Boulevard Londrina): a 17% a folha é **R$49.003,79** e o EBITDA fecha em **R$113.159,69 (39,26%)**, break-even
**840,6** alunos totais e payback **28** meses; **a 26%** a folha vai a **R$74.946,97**, o EBITDA cai para
**R$87.216,50 (30,26%)**, o break-even sobe para **987,8** alunos totais e o **payback vai de 28 para 54 meses** —
ou seja, a unidade deixaria de atender o critério de payback de 36 meses. (Os números que esta nota trazia antes —
R$47.942,66 / R$109.233,60 / 38,73% / 859,6 / 29 → 58 — eram da rodada com a **anuidade desligada**, estado que
deixou de valer em 2026-07-24.) Premissas e conflito documentados em
`PREMISSAS_VIABILIDADE.md` (§4 e §9-a); impacto no comitê em `docs/nota_impacto_fin_viab_01.md`. **Status e
criticidade deste bloco permanecem inalterados.**

---

## Epic BLK-RELVIAB — Relatório de Viabilidade do Imóvel (PDF enriquecido) — CONCLUÍDA (2026-07-18)

> Epic **concluída e deployada em produção em 2026-07-18** (PR #130 = blocos 01–05; PR #132 = bloco 06 + polish
> visual aprovado por Felipe). A aba **Viabilidade** gera o **relatório completo em PDF** (fotos do imóvel + info +
> slides de viabilidade financeira). READ-ONLY sobre o M1 (camada de relatório/visualização; precedente DEC-004
> emenda 2026-07-18 para o caminho de tiles online). Detalhe de cada bloco em `tasks/completed.md`.

- BLK-RELVIAB-01 (concluído 2026-07-18) — ver tasks/completed.md
- BLK-RELVIAB-02 (concluído 2026-07-18) — ver tasks/completed.md
- BLK-RELVIAB-03 (concluído 2026-07-18) — ver tasks/completed.md
- BLK-RELVIAB-04 (concluído 2026-07-18) — ver tasks/completed.md
- BLK-RELVIAB-05 (concluído 2026-07-18) — ver tasks/completed.md
- BLK-RELVIAB-06 (concluído 2026-07-18) — ver tasks/completed.md

---

## Epic BLK-REV — Revisão séria do app: pesquisa e planejamento (Desempenho + Arquitetura + UX/UI)

> **Objetivo:** revisar a estrutura INTEIRA do app para achar pontos fortes/fracos e planejar o produto mais
> otimizado e completo possível — **incluindo avaliar refazer o app noutra stack web** (sair do Streamlit se a
> evidência justificar). **Épico 100% de PESQUISA e PLANEJAMENTO: nenhum bloco implementa produção.** Cada bloco
> entrega um RELATÓRIO/PROPOSTA (gitignored em `data/analysis/` ou em `docs/`). As DECISÕES (rebuild vs refactor,
> stack alvo, direção de UX) são **gate humano + DEC** no bloco de síntese (BLK-REV-12). **READ-ONLY sobre o M1**
> em todos os blocos.
>
> **Dores relatadas por Felipe (2026-07-08), que ancoram a pesquisa:** (1) lag ao **renderizar o mapa**; (2) lag
> na **troca de modos de cor/heat maps** (M1/Censitário/Residual…); (3) lag na **seleção de hexes + inclusão no
> cenário múltiplo**; (4) lag ao **gerar PDF Pontual e Municipal**; (5) app **poluído e pouco usual para leigos**.
>
> **Divisão de autonomia:** MEDIÇÃO/DIAGNÓSTICO/pesquisa de arquitetura (REV-01..07) é **loop-safe** (headless,
> determinística, READ-ONLY, entrega relatório). O que exige **ver o app renderizado, julgamento de design ou
> decisão** (spike visual, UX, síntese) é **humano** (lição BLK-UI-10: o loop não enxerga a UI). **Caveat honesto:**
> o loop mede o lado **Python/servidor** (data prep, serialização, recompute do rerun, geometria, tiles); a medição
> de **paint/interação no browser** é complemento **manual**, anotado no relatório.

- BLK-REV-01 (concluído 2026-07-08) — ver tasks/completed.md


---

- BLK-REV-02 (concluído 2026-07-08) — ver tasks/completed.md


---

- BLK-REV-03 (concluído 2026-07-08) — ver tasks/completed.md


---

- BLK-REV-04 (concluído 2026-07-08) — ver tasks/completed.md


---

- BLK-REV-05 (concluído 2026-07-08) — ver tasks/completed.md


---

- BLK-REV-06 (concluído 2026-07-10) — ver tasks/completed.md


---

- BLK-REV-07 (concluído 2026-07-10) — ver tasks/completed.md


---

- BLK-REV-08 (concluído 2026-07-16) — ver tasks/completed.md


---

### BLK-REV-09 — Avaliação heurística de UX + estudo de "clutter" para leigos

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (dor #5; **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir (Felipe/Vini). |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA — UX]` → Builder → QA. |
| **Status** | Pendente — **~2/3 já executado**, ver "Insumo pronto" abaixo. |
| **Depende de** | — (avaliação do app renderizado). |
| **Autonomia** | **manual (NÃO loop-safe)** — exige VER o app renderizado + julgamento humano de UX; o loop não enxerga a UI. NÃO marcar loop-safe. |

**Contexto.** Dor #5 — app "poluído e pouco usual para leigos".
**Objetivo.** Heuristic evaluation (Nielsen), inventário de poluição visual/densidade/jargão, e **jobs-to-be-done
por persona** (executivo, operador, leigo). Relatório de problemas priorizados por severidade × esforço.
**Guardrail.** §5 READ-ONLY M1.

> **INSUMO PRONTO (2026-07-13) — LER ANTES DE INICIAR O CICLO:**
> **`data/reports/rev09_passagem_heuristica_ux.md`** (evidência visual em `data/reports/rev09_telas/`;
> reprodução via `scripts/rev09_capturar_telas.py`).
>
> A **passagem heurística sobre o app RENDERIZADO já foi feita** (Playwright, 5 abas, commit `e4ec53c`):
> **19 achados catalogados** com heurística de Nielsen, severidade 0–4, evidência e matriz
> severidade × esforço. Destaques: (#1) **"oportunidade" significa coisas diferentes em abas
> diferentes** — 1.588 no Executivo vs 6 na Carteira, MESMO recorte; (#2) os cards "Onde expandir" e
> "Onde evitar expansão" mostram **texto idêntico**; (#3) o mapa **não enquadra a UF selecionada**
> (abre em escala continental); (#4) o mapa está **abaixo da dobra** (1.025 px = 1,02 telas).
>
> **O QUE FALTA (bloqueia o REV-10, só o humano fecha):** os **jobs-to-be-done por persona** — quem
> abre o app, com que frequência, e **quem é concretamente o "leigo"** da dor #5. Deliberadamente NÃO
> foi inventado: o REV-10 desenha wireframes *por persona* e o REV-12 herda a severidade numa DEC
> estratégica — persona fictícia se propaga. As 4 perguntas estão na §6 do relatório.
>
> **Achado que afeta o BLK-REV-12:** nenhum dos 19 itens é culpa do Streamlit — cards idênticos, coluna
> "Join" na tabela, mapa que não enquadra a seleção, guardrail de dev na tela. É dívida de **produto**,
> não de **stack**: **um rebuild não conserta nada disso de graça.**

---

### BLK-REV-10 — Arquitetura de informação e fluxos-alvo (proposta de redesign)

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (reduz complexidade sem perder poder; **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir (Felipe/Vini). |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA — design]` → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | **BLK-REV-09** (dores de UX priorizadas). |
| **Autonomia** | **manual (NÃO loop-safe)** — design/UX; exige julgamento humano. NÃO marcar loop-safe. |

**Contexto.** Reduzir a complexidade para leigos sem perder poder para power users.
Insumo de benchmark externo: `docs/system_design_referencia.md` (§3 layout, §4 navegação, §7 progressive
disclosure, §8 fluxo triagem→viabilidade com H3, §10 matriz persona).
**Objetivo.** Redesenhar a **arquitetura de informação** em torno dos fluxos core (triagem→viabilidade, per
`docs/estado_dos_modelos.md`); **progressive disclosure** (modo simples p/ leigo vs avançado); wireframes de baixa
fidelidade por persona. Usar o guia `frontend-design`.
**Guardrail.** §5 READ-ONLY M1.

---

### BLK-REV-11 — Sistema visual / design language (research)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (linguagem visual coerente; **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir (Felipe/Vini). |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA — design]` → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | — (pode ir em paralelo à trilha de UX). |
| **Autonomia** | **manual (NÃO loop-safe)** — design; exige julgamento visual humano. NÃO marcar loop-safe. |

**Contexto.** Consolidar a linguagem visual (a direção **turquesa Ultra + magenta concorrente** do BLK-UI-10;
tipografia; componentes) e o sistema de dataviz dos mapas/gráficos.
Insumo de benchmark externo: `docs/system_design_referencia.md` (§5 componentização — design system de 5-6
componentes canônicos; §6.2 paletas acessíveis e dataviz para leigos).
**Objetivo.** Proposta de **design system** (tokens, componentes, paletas acessíveis light/dark) reusando os guias
`frontend-design` e `dataviz`.
**Guardrail.** §5 READ-ONLY M1.

---

### BLK-REV-12 — Síntese executiva + decisão de rumo (rebuild vs refactor) + roadmap faseado (DEC + gate)

| Campo | Valor |
|---|---|
| **Criticidade** | **Estratégica** (decide o rumo do produto; **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir (Felipe/Vini). |
| **Esteira** | Block Orchestrator → Planner → `[GATE HUMANO + DEC]` → (implementação vira epic próprio). |
| **Status** | Pendente. |
| **Depende de** | **BLK-REV-01..11** (todos os relatórios de perf, arquitetura e UX). |
| **Autonomia** | **manual (NÃO loop-safe)** — decisão estratégica; gate humano obrigatório + DEC. NÃO marcar loop-safe. |

**Contexto.** Consolidar tudo numa recomendação acionável.
Insumo de referência: `docs/system_design_referencia.md` (§2 diagnóstico técnico do gargalo rerun/pydeck e
§11 recomendações priorizadas alimentam o critério de performance e o de custo de dev da matriz de decisão).
**Objetivo.** Relatório executivo que junta **perf** (REV-01..06), **arquitetura** (REV-07/08) e **UX** (REV-09..11)
numa **recomendação de rumo** (rebuild vs refactor incremental), **stack alvo**, direção de UX e **roadmap faseado**
(esforço × risco × valor por fase). Registrar **DEC** com a decisão. A implementação vira **epic próprio** (fora deste
épico de pesquisa).
**Guardrail.** §5 READ-ONLY M1; este bloco decide o PLANO, não implementa.

> **Emenda (2026-07-10, Felipe):** o critério 5 da matriz do BLK-REV-07 ("custo de dev por perfil de
> time") foi avaliado assumindo time **Python-only** — premissa INCORRETA: o time é **poliglota** (JS/TS
> inclusive; Vini fez os scrapers e o PoC HTML/Leaflet do BLK-UI-10, Juan mantém bot + API). Na decisão,
> **reponderar o "−" das opções (b)/(d) para "0/+"** nesse critério — o que aproxima o rebuild sobre a
> infra existente (SPA servida pelo Caddy + `api` FastAPI já em produção). Insumos adicionais exigidos
> para decidir: o teto empírico do client-side em escala real e a latência VPS↔cliente medida (ambos do
> BLK-REV-08 emendado). Os quick wins (epic BLK-PERF) NÃO conflitam com nenhum rumo: 01a é server-side
> permanente; 01b/c mantêm a produção usável durante a eventual migração e viram a régua de comparação da SPA.

---

## Epic BLK-PERF — Quick wins de performance do dashboard (implementação dos fixes diagnosticados no BLK-REV)

> **Origem (2026-07-10, aprovado por Felipe):** implementação dos fixes com causa-raiz isolada e ganho
> estimado pelos diagnósticos **BLK-REV-03/04/05/06** (concluídos; relatórios em `data/analysis/`,
> inventário em `docs/arquitetura_app_atual.md`). Diferente do épico BLK-REV (pesquisa-only), este epic
> **IMPLEMENTA** — mas SÓ na camada de display/render do dashboard e relatórios. **READ-ONLY sobre o M1
> em todos os blocos** (§5): nenhum recalcula `score_priorizacao`/`hex_score_estrutural`/pesos/carteira/
> plano/artefatos oficiais; raio 1,5 km e método de intersecção INTOCADOS.
>
> **Instrumento de aceite (todos os blocos):** re-rodar `scripts/perf_baseline_app.py` (harness do
> BLK-REV-01) ANTES/DEPOIS e registrar a comparação no PR — o ganho tem de aparecer no número, não na
> narrativa. Baseline de referência: `data/analysis/perf_baseline_app_2026.md`.
>
> **Relação com a trilha web (REV-07/08/12):** o BLK-PERF-01a é **permanente** (server-side; os PDFs
> continuam no backend em qualquer stack). O 01b/01c são específicos do Streamlit — o custo (dias) compra
> produção usável durante a trilha web e a régua honesta de comparação para a eventual SPA.
> **Estratégia de branch:** 1 bloco = 1 branch `ciclo/<ID>` = 1 PR — independentes entre si e da trilha
> web (superfícies disjuntas; a SPA viverá em diretório novo + extensões da `api/`).

---

- BLK-PERF-01a (concluído 2026-07-10) — ver tasks/completed.md


---

- BLK-PERF-01b (concluído 2026-07-10) — ver tasks/completed.md


---

- BLK-PERF-01c (concluído 2026-07-10) — ver tasks/completed.md


---

- BLK-PERF-01d (concluído 2026-07-10) — ver tasks/completed.md


---

## Epic BLK-TP — Camada de Demanda Revelada (camada paralela, READ-ONLY sobre o M1)

> Epic que incorpora ao Motor um **sinal externo, georreferenciado e anônimo de demanda paga por
> academia** (membros pagantes por região), agregado em H3. Motivação: a DEC-009 encerrou a previsão
> de *magnitude de demanda* pela geografia interna (renda/pop têm sinal nulo no M1 — DEC-001); faltava
> um sinal de **demanda observada**. Uma **análise exploratória interna (2026-06-24)** indicou que essa
> demanda paga por hex correlaciona forte com a nossa camada residual (Spearman **+0,52** vs.
> `score_oportunidade_residual`) e com alunos efetivamente capturados (**+0,75**) — primeira validação
> externa positiva forte de uma camada do Motor.
> **READ-ONLY sobre o M1 em TODOS os blocos:** nenhum recalcula `score_priorizacao`, pesos, carteira,
> plano ou artefatos oficiais (§5 guardrail). A **demanda entra como insumo observado, NUNCA como
> preditor geográfico de magnitude** (DEC-009 intacta).
> **Anti-PII por construção:** o insumo bruto tem PII na origem; a ingestão consome **apenas dados já
> agregados** e descarta qualquer identificador/coordenada individual na fronteira de entrada (§4).
> Sugere registrar **DEC-012** (adoção da camada) ao iniciar o BLK-TP-01.

- BLK-TP-01 (concluído 2026-06-24) — ver tasks/completed.md


---

- BLK-TP-02 (concluído 2026-06-25) — ver tasks/completed.md


---

- BLK-TP-03 (concluído 2026-07-02) — ver tasks/completed.md


---

- BLK-TP-03-FU1 (concluído 2026-07-15) — ver tasks/completed.md




---

### BLK-TP-09 — Integração do sinal de captura validado à camada de mercado/residual (agnóstico de mecanismo; DEC + gate)

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta/Crítica** (altera a **FÓRMULA de um score ATIVO** da camada paralela de mercado/residual e **regenera** os parquets que alimentam dashboard/API; **READ-ONLY sobre o M1 OFICIAL**). **Exige DEC registrada + gate humano obrigatório** antes do Builder. |
| **Prioridade** | A definir (Felipe/Vini). |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA OBRIGATÓRIA + DEC]` → Builder → QA. |
| **Status** | **Habilitado por um candidato vencedor (BLK-TP-07 = GO) — pendente de DEC + gate.** RE-ESCOPADO em 2026-07-04: era "aplicar a recalibração do residual do TP-06"; passou a ser **agnóstico de mecanismo — integrar o SINAL DE CAPTURA VALIDADO** à camada de mercado/residual. Motivo: a via original (mexer na *oferta consumida* do residual) foi **testada e esgotada** out-of-fold, honestamente (DEC-008), sem candidato material — **BLK-TP-06-FU1** Candidato A (somar as menores cru, dedup fino) = **NO-GO** (Δ −0,0427); **BLK-TP-06-FU2** Candidato C (capacidade de clube real `data/validacao/` + decay 2 km) = **C1 RUÍDO** (Δ +0,0019, idêntico ao baseline em 97,3% dos hexes) / **C2 NO-GO** (Δ −0,0312). O candidato que **venceu materialmente** veio por OUTRO mecanismo: **BLK-TP-07 (GO)** — Huff/gravitacional de captura por hexágono vs demanda observada `membros` (R²_oof_log +0,4391 IC95 [+0,4251,+0,4523], β=0,5, **supera o baseline geométrico +0,2922 ⇒ a distância AGREGA**; n_join 16.575, ~1% do universo, viés Sudeste). O TP-07 **validou o sinal, mas NÃO integrou nada**. Este bloco é essa **integração** — segue exigindo **DEC + gate humano** e medição de impacto/cobertura. |
| **Depende de** | **BLK-TP-07** (candidato vencedor = GO honesto out-of-fold, concluído 2026-07-03 — `demanda_revelada/huff_captura.py`). Histórico da via esgotada (contexto, não bloqueio): BLK-TP-06 (GO +0,3119), BLK-TP-06-FU1 (A NO-GO), BLK-TP-06-FU2 (C ruído/NO-GO). |
| **Autonomia** | **manual (NÃO loop-safe)** — muda um score em produção; NUNCA loop-safe. |

**Contexto.** A trilha de melhorar o `score_oportunidade_residual` **pela oferta consumida** (subtrair/recapacitar
concorrência no próprio residual) foi exaurida sem ganho material (TP-06-FU1/FU2, acima). O sinal que **venceu**
apareceu por um mecanismo diferente: tratar a concorrência como **captura gravitacional (Huff) no ponto/hex
candidato**, validada contra a demanda **observada** (`membros`) — o **BLK-TP-07** deu o **GO honesto** (out-of-fold,
supera o baseline geométrico ⇒ a geometria de distância agrega, não é só "contar concorrente perto"). O TP-07
implementou e validou o motor de captura (`demanda_revelada/huff_captura.py`, READ-ONLY, sem integrar), mas **não
tocou** `score_oportunidade_residual`/carteira/plano. Este bloco é a **aplicação/integração** desse sinal — e por
isso exige DEC + gate.

**Objetivo.** Integrar o sinal de captura Huff validado (TP-07) à **camada paralela de mercado/residual** — seja
como componente/ajuste de `score_oportunidade_residual`, seja como coluna acionável nova casada por `hex_id` (a
forma exata é decisão do Planner + gate/DEC) — em `src/motor_expansao/pipelines/calcular_colunas_mercado.py`,
**medindo o impacto** (antes/depois: quantos hexes mudam de faixa, deslocamento de distribuição) e **regenerando**
a camada pela **ordem canônica** (`híbrido → mercado → calcular_colunas_mercado → carteira → plano → domínio →
residual → fase1_bi_exports`). **READ-ONLY sobre o M1 OFICIAL**: `score_priorizacao`, `hex_score_estrutural`,
pesos (renda 0.40/pop 0.60), carteira/plano do M1 e os 4 artefatos oficiais permanecem **INTOCADOS** (mtime
inalterado) — muda-se apenas a camada paralela de mercado/residual.

**Critérios de aceite.** DEC registrada e aprovada ANTES do Builder (a DEC define a FORMA de integração e a
função exata); medição de impacto documentada (antes/depois, hexes que mudam de faixa); regeneração reprodutível
pela ordem canônica; **cobertura/viés do sinal (~1% metropolitano, viés Sudeste — herdado do TP-07/TP-06)
explicitamente tratado** — o GO é de ~1% do universo, então a integração **não pode piorar/enviesar os 99% sem
sinal** (ex.: aplicar só onde há cobertura, ou como camada acionável separada em vez de sobrescrever o residual
nacional); artefatos oficiais do M1 com **mtime inalterado**; suíte verde; `import streamlit_app` ok.
**Guardrail.** §5 (READ-ONLY M1 OFICIAL — só a camada paralela muda, e com DEC); DEC-008 (a integração tem de ser
justificada pela validação **out-of-fold** do TP-07, não por R² in-sample); DEC-009 (demanda `membros` é ALVO de
validação, NUNCA vira preditor geográfico de magnitude no artefato de produção); DEC-012 (anti-PII).

---

## Epic BLK-ATR — Funil de Atratividade de Hexágonos (gate de viabilidade + leitura multi-eixo; camada paralela READ-ONLY sobre o M1)

**Objetivo do epic.** Formalizar a decisão de "onde entrar" como um **funil de duas etapas**, paralelo e
READ-ONLY sobre o M1: **(1) um gate absoluto de viabilidade** (piso fixo de população e renda per capita —
abaixo dele nem entra na conversa) e **(2) uma leitura multi-eixo dentro do viável** que cruza os três eixos
ortogonais de atratividade — **sociodemografia** (renda/densidade), **tamanho de mercado** (residual/demanda
observada) e **disputa competitiva** (share de captura Huff do BLK-TP-07). Nenhuma camada bate o martelo
sozinha; todas informam. Motivação: o residual sozinho "desiste" de regiões ricas-mas-saturadas (competição
alta zera a demanda não atendida) e o Huff sozinho também penaliza saturação — falta o eixo de **atração**
sociodemográfica para contrabalançar as duas lentes de competição. Este epic testa, honestamente, se combinar
os eixos agrega valor preditivo real sobre a demanda observada, e só então materializa.
**READ-ONLY sobre o M1** (não recalibra `score_priorizacao`/`hex_score_estrutural`/pesos nem regenera
artefatos oficiais; DEC-001 intacta). Metodologia obrigatória DEC-008 (out-of-fold vs baseline, R² in-sample
banido, IC95, flag de extrapolação). DEC-009 (demanda observada é ALVO de validação, nunca preditor de
magnitude). DEC-012 aplica-se **só ao dado pessoal** da Demanda Revelada; o dado de **estabelecimento**
concorrente (nome/endereço/lat-long de academia — público, coletado por scraper) **não é PII pessoal** e é
usado normalmente, inclusive o nome para dedup por rede.

**Sequência:** BLK-ATR-01 (densifica o Huff) + BLK-ATR-02 (gate) → BLK-ATR-03 (testa a estrutura) →
BLK-ATR-04 (visualiza os resultados) → **[revisão humana]** → BLK-ATR-05 (materializa em produção; NÃO
loop-safe). Os quatro primeiros são de **análise/validação, 100% autônomos (loop-safe)**; o último toca
produção e exige DEC + gate humano.

---

- BLK-ATR-01 (concluído 2026-07-06) — ver tasks/completed.md



---

- BLK-ATR-03 (concluído 2026-07-06) — ver tasks/completed.md


---

- BLK-ATR-04 (concluído 2026-07-06) — ver tasks/completed.md


---

- BLK-ATR-01-FU1 (concluído 2026-07-07) — ver tasks/completed.md


---

- BLK-ATR-03-FU1 (concluído 2026-07-07) — ver tasks/completed.md


## Projeto — Score de vulnerabilidade de academias independentes (M&A)

> Trilha nova (pedido de Vinicius, 2026-07-06): transformar a base de concorrentes já coletada pelos
> scrapers (GymScraping, DEC-013) num **funil de M&A**. A cada academia INDEPENDENTE (não-rede/de
> bairro) mapeada, anexar sinais de "saúde do negócio" e derivar um **score de vulnerabilidade**;
> cruzar com os hexágonos quentes do Motor para produzir uma **lista priorizada de alvos de aquisição**
> para o time comercial. É **camada de ENRIQUECIMENTO** sobre os scrapers existentes — NÃO cria pipeline
> novo. **READ-ONLY sobre o M1** (§5): a vulnerabilidade é um score PARALELO, nunca toca
> `score_priorizacao`/pesos/artefatos oficiais.
>
> **Rota escolhida por Vinicius (2026-07-06): PLANO B — sem Google Places.** Os sinais vêm de fontes
> que o repo JÁ coleta: (a) presença + **rating in-app** do WellHub/TotalPass (DEC-013), e (b)
> **diff do histórico de snapshots semanais** dos próprios scrapers (churn e staleness). Isso elimina a
> dependência de API externa ao vivo (sem desvio do §2 → **sem DEC**), sem custo/ToS e **sem PII de
> reviewers**. Reputação pública externa (Google Places etc.) fica como **sucessor opcional com gate
> próprio** (BLK-MA-07), caso um dia se queira a nota do público geral.

### BLK-MA-01 — Contrato e decisões do enriquecimento de vulnerabilidade (design, Plano B)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (camada de enriquecimento paralela que reusa dados já coletados + diff de snapshots; **sem dependência externa nova** e **sem DEC** — a rota Google Places/§2 foi descartada no Plano B; gera um score paralelo e um entregável comercial. **READ-ONLY sobre o M1**). |
| **Prioridade** | A definir por Vinicius. |
| **Esteira** | Block Orchestrator → Planner → `[confirmação humana — produto: pesos/limiares do score + definição de hex quente]` → Builder → QA. |
| **Status** | Pendente. |
| **Depende de** | DEC-013 (WellHub/TotalPass já coletados + **cron semanal que acumula os snapshots** — insumo de churn/staleness); camada mercado/residual + Demanda Revelada (para "hexágono quente"); `concorrentes_mapeados.parquet`. |
| **Autonomia** | **manual (NÃO loop-safe)** — toca a trilha de scrapers/VPS (integração ao cron, DEC-013) e define um score/entregável comercial; precisa de confirmação humana de produto. NÃO marcar loop-safe. |

**Contexto (ancorado).** Os scrapers do Vini (`VinhoAbencoado/GymScraping`, DEC-013) já mapeiam a
oferta concorrente **e rodam semanalmente**; a base entra no Motor via
`normalizar_concorrentes → calcular_colunas_mercado` e alimenta o residual. Hoje esses registros têm
oferta/rede/geo, mas **nenhum sinal de fragilidade do negócio**. O insight do Plano B: a **variação
temporal** e a **última atualização** saem do **diff do próprio histórico de scraping** (nenhuma API
externa), e a **reputação** vem do **rating in-app WellHub/TotalPass** que já é coletado. O BLK-MA-01
**não escreve código de produção** — fixa o contrato dos sinais, a metodologia do score e as decisões
de produto; os sucessores implementam.

**Objetivo do epic.** Score de vulnerabilidade por academia independente + lista priorizada de M&A
(academias mais vulneráveis próximas a hexágonos quentes) para o time comercial.

**Sinais (Plano B — só fontes internas / já coletadas).**
1. **Presença/ausência em agregadores** (WellHub/TotalPass) — já interno (DEC-013). Tese: ausência do
   canal onde o público low-cost está → sinal de fragilidade.
2. **Rating in-app WellHub/TotalPass** (subconjunto listado) — substitui a "avaliação média" do Google;
   `n/d` para quem não está no agregador (ver D3). **[VERIFICAR no gate — checado por Claude em
   2026-07-23]** o único caminho de ingestão que existe hoje,
   `demanda_revelada/concorrentes_densos.py:_ler_csv_tp_wh` (linha 127), produz SÓ
   `hex_id_res7`/`rede_normalizada`/`fonte` (drop-PII na fronteira), **sem coluna de rating**.
   Confirmar que os CSVs BRUTOS TP/WH (que vivem na VPS, gitignored) carregam a nota ANTES que
   BLK-MA-03/04 dependam dela — senão este sinal também é aquisição, não reuso, e o rótulo "já
   coletado" cai. É a claim mais load-bearing do Plano B.
3. **Churn/permanência** via **diff dos snapshots semanais** — apareceu/sumiu/reapareceu na base dos
   scrapers → forte proxy de fechamento/venda. (Substitui a "variação de reviews".)
4. **Staleness** via **diff dos snapshots** — tempo desde a última mudança nos campos raspados
   (horário/preço/lista de unidades/endereço). (Substitui "tempo desde última atualização" — proxy mais
   confiável que o "last-updated" do Google, que nem é exposto.)
5. **(Opcional) Tendência de popularidade no agregador** — `membros`/`alunos_parceiras` da célula
   subindo/caindo, quando a série permitir.
6. **(Opcional, interno) Pressão competitiva** — proximidade a Smart Fit/rede Ultra + residual saturado
   (de `concorrentes_mapeados` + Ultra + mercado/residual): independente espremida = mais vulnerável.
   Colunas reais já materializadas por `hex_id` em `data/staging/hexagonos_mercado_mapeado.parquet`
   (verificadas em 2026-07-23): `pressao_concorrencial_score_2km`, `n_concorrentes_mapeados_2km`,
   `dist_concorrente_mais_proximo_m`, `n_unidades_ultra_2km`, `rede_dominante_2km`,
   `share_smart_fit_2km` — nenhum sinal de "pressão" precisa ser recomputado do zero.

**Mapa dos 4 sinais originais → Plano B:** avaliação média → (2) rating in-app; Δ reviews 3m → (3)
churn + (5) tendência; presença agregadores → (1) [já interno]; última atualização → (4) staleness.

**Decisões a resolver/confirmar (BLK-MA-01).**
- **D1 — Definição de "academia independente".** Critério de não-rede/bairro sobre `concorrentes_mapeados`
  (ex.: `rede` isolada / contagem de unidades da marca == 1) e o universo exato (os 28 scrapers citados
  vs. os 90 coletores da DEC-013 — quais entram).
- **D2 — Fonte/retenção dos snapshots semanais.** Onde vivem os snapshots dos scrapers (formato/retenção)
  para computar churn/staleness; janela de staleness (nº de semanas sem mudança = "stale"); tratamento do
  **ramp-up** (cron ativo desde 26/06 — ~1,5 mês hoje; a série cresce). Sem histórico → sinal marcado
  como imaturo, não penaliza.
- **D3 — Rating de agregador.** Usar como sinal só no subconjunto listado; como tratar `n/d` (não
  penalizar quem não tem rating; a ausência de agregador já é o sinal 1).
- **D4 — Fórmula/pesos do score.** Heurística transparente e auditável (composição ponderada normalizada
  dos sinais), com direção de cada um (ausência de agregador ↑vuln.; rating baixo ↑; churn/sumiço ↑;
  staleness alta ↑; popularidade caindo ↑; pressão competitiva alta ↑). NÃO é modelo preditivo treinado
  em desfecho — se um dia se quiser validar que prevê aquisição/fechamento, entra a disciplina DEC-008
  (out-of-fold vs baseline) em bloco próprio.
- **D5 — "Hexágono quente" + proximidade.** Qual métrica define quente (`score_oportunidade_residual`,
  SAM, demanda revelada) e o limiar de distância academia↔hex para entrar na lista de M&A.
  Âncora verificada (2026-07-23): o hotness por hex já está materializado em
  `data/outputs/carteira_expansao_acionavel.parquet` (4.899x62) — colunas `score_priorizacao`,
  `score_setor_2022_calibrado`, `score_expansao_hibrido`, `score_oportunidade_residual`,
  `oferta_efetiva_disponivel`, `tese_entrada` por `hex_id` — e casa direto com
  `concorrentes_mapeados.hex_id_res7`. Fazer o join READ-ONLY no padrão defensivo de
  `src/motor_expansao/pipelines/enriquecer_outputs_residual_mercado.py:68-82` (asserts de
  `score_priorizacao`/ranks/cardinalidade inalterados após o join). **Nota de tese de M&A:** comprar
  (não construir) quer demanda ALTA + residual BAIXO (mercado saturado); é a INVERSÃO do sinal de
  abrir unidade nova (residual alto). Registrar a inversão no cálculo.
- **D6 — Entregável.** Formato da lista priorizada (Parquet + CSV `sep=";"`/`utf-8-sig` para o comercial;
  e/ou overlay no dashboard) e onde materializar (`data/staging` / `data/outputs`).
- **D7 — Anti-PII.** Persistir **somente agregados** (rating médio, contagens, flags de churn/staleness);
  **nunca** texto/autor de review nem PII. Fonte real fora do versionamento; fixtures sintéticas (DEC-012).
- **D8 — Integração ao cron.** Rodar como passo do lote semanal da VPS (DEC-013) vs. cadência separada.

**Escopo permitido (READ-ONLY M1).** Camada de enriquecimento nova (módulo isolado, ex.:
`src/motor_expansao/vulnerabilidade/` ou extensão do pacote de mercado), consumindo o histórico de
snapshots dos scrapers + o ativo WellHub/TotalPass + `concorrentes_mapeados`; materializa um Parquet
paralelo com o score e a lista de M&A. NÃO altera artefatos oficiais do M1. **Sem dependência nova de
base** e **sem API externa ao vivo**.

**Fora de escopo.** `score_priorizacao`/`hex_score_estrutural`/pesos/carteira/plano/artefatos oficiais
do M1; `flag_sam`/gate do SAM (DEC-006/DEC-007); **Google Places / qualquer API externa de reputação**
(movido para o sucessor opcional BLK-MA-07, com gate/DEC próprios); persistir PII.

**Guardrails.** §5 (score paralelo, não recalcula M1); DEC-012/anti-PII (só agregados; fonte real não
versionada; fixtures sintéticas); DEC-013 (extensão do lote de scrapers, não pipeline novo). §2 NÃO é
desafiado no Plano B — não há API ao vivo; o dashboard segue offline sobre Parquets.

**Entregável.** Score de vulnerabilidade por academia independente + lista priorizada de alvos de M&A
(vulneráveis × proximidade a hexágonos quentes) para o time comercial.

**Decomposição sugerida (sucessores, a confirmar no BLK-MA-01).**
- **BLK-MA-02** — extrator de **churn + staleness** a partir do histórico de snapshots semanais dos
  scrapers (100% interno); flags de série imatura (ramp-up).
- **BLK-MA-03** — join do sinal de agregadores (**presença + rating in-app** WellHub/TotalPass) por
  dedup com `concorrentes_mapeados`; anti-PII por construção; fixtures sintéticas.
- **BLK-MA-04** — score de vulnerabilidade (fórmula/pesos do D4) + normalização + flags de qualidade.
- **BLK-MA-05** — lista priorizada de M&A (cruzamento com hexágonos quentes, D5) + entregável (D6).
- **BLK-MA-06** — integração ao cron semanal da VPS (D8) e runbook.
- **BLK-MA-07 (opcional/futuro, gate + DEC próprios)** — enriquecer com **reputação externa** (Google
  Places ou outra) SE se quiser a nota do público geral; só aqui reaparece o desvio do §2.

**Critério de aceite (BLK-MA-01).** Contrato dos sinais internos (1–4, + 5/6 opcionais) e do score
definido; D1–D8 resolvidas/confirmadas no gate de produto; decomposição BLK-MA-02+ confirmada;
guardrails §5/anti-PII/DEC-013 explicitados; **sem DEC de API externa** (rota Google descartada, movida
ao BLK-MA-07); ZERO código de produção neste bloco (só docs/contrato).

---

### BLK-ATR-05 — Materializar a estrutura escolhida (gate + matriz/composto) em produção (DEC + gate humano)

| Campo | Valor |
|---|---|
| **Criticidade** | **Crítica** (materializa o funil na camada de um score ATIVO e regenera parquets de dashboard/API; **READ-ONLY sobre o M1 OFICIAL**). **Exige DEC registrada + gate humano obrigatório** antes do Builder. |
| **Prioridade** | A definir (Felipe/Vini). |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA OBRIGATÓRIA + DEC]` → Builder → QA. |
| **Status** | Em espera (condicional ao veredito do BLK-ATR-03 + decisão humana). |
| **Depende de** | **BLK-ATR-03** (estrutura decidida: matriz ou composto GO) + **BLK-ATR-04** (visualização para a decisão). |
| **Autonomia** | **manual (NÃO loop-safe)** — muda a camada de um score em produção e exige gate humano; NUNCA loop-safe (o loop não tem gate). |

**Contexto.** Após BLK-ATR-03 decidir a estrutura e BLK-ATR-04 dar os números, este bloco a materializa na
camada paralela de mercado — o gate de viabilidade (BLK-ATR-02) + a leitura escolhida (matriz de eixos
normalizados na mesma régua **ou** score composto validado) — para consumo no dashboard/API.

**Objetivo.** Materializar o funil na camada de mercado (`calcular_colunas_mercado.py` ou módulo paralelo),
medindo impacto (antes/depois: hexes por faixa/quadrante) e regenerando a camada pela **ordem canônica**
(`híbrido → mercado → calcular_colunas_mercado → carteira → plano → domínio → residual → fase1_bi_exports`).
**READ-ONLY sobre o M1 OFICIAL**: `score_priorizacao`/`hex_score_estrutural`/pesos/carteira/plano/4 artefatos
oficiais **INTOCADOS** (mtime inalterado).

**Critérios de aceite.** DEC registrada e aprovada ANTES do Builder; medição de impacto documentada;
regeneração reprodutível pela ordem canônica; cobertura/viés ~1% metropolitano explicitamente tratado (não
enviesar os 99% sem sinal de disputa); artefatos oficiais do M1 com **mtime inalterado**; suíte verde;
`import streamlit_app` ok.
**Guardrail.** §5 (READ-ONLY M1 OFICIAL — só a camada paralela muda, e com DEC); DEC-008 (justificado pela
validação out-of-fold do BLK-ATR-03); DEC-009 (demanda não vira preditor de magnitude); DEC-012 (dado pessoal
protegido).

---

## Epic BLK-LTV — Integração Lifetime × Motor de Expansão (eixo retenção territorial, camada paralela READ-ONLY sobre o M1)

**Objetivo do epic.** Validar se o perfil do território prevê a retenção/LTV da carteira, para a
expansão passar a priorizar "onde a demanda **permanece**", não só "onde há demanda". Se validado,
compor um eixo de score paralelo (M2) que pondere captação + retenção/LTV territorial. **READ-ONLY
sobre o M1** (não recalibra `score_priorizacao`/`hex_score_estrutural`/pesos nem regenera artefatos
oficiais; DEC-001 intacta). Metodologia obrigatória DEC-008: Spearman + **bootstrap/IC** (N pequeno),
sem R² in-sample; controlar por maturidade quando houver dado.

**Insumo (Lifetime).** `data/ultra/unidade_para_motor.parquet` — 88 unidades com `PROB_CANCEL_90D_*`,
`LTV_PROSPECTIVO_12M_*`, `CONFIABILIDADE_UNIDADE`, `USAR_PROB_ABSOLUTA`, `USAR_RANKING`
(dicionário em `unidade_para_motor_DICIONARIO.md`). Chave lógica: `COD_UNIDADE`; chave de join real
disponível: **nome da unidade** (`UNIDADE`), pois nem o Lifetime nem as bases geo têm `COD_UNIDADE`.

**Fonte de geocodificação (confirmada no repo).** `data/ultra/Ultra.csv` (legado: `sep=";"`,
`encoding="latin-1"`, 1 linha de metadado) — 147 unidades com `UNIDADE`/`ESTADO`/`CIDADE`/`Latitude`/
`Longitude`. Complemento: `data/staging/unidades_ultra_performance_hex.parquet` (54 unidades já com
`hex_id`/features territoriais). Cobertura medida (2026-07-01): match exato de nome Lifetime↔Ultra.csv
= 34/88; fuzzy ≥0.8 recupera mais (≈43 contra o perf-hex) — fechar cobertura é trabalho do BLK-LTV-01.

**Regras (do pedido, canônicas para o epic).** Usar `LTV_PROSPECTIVO_12M_*` só no **agregado por
unidade** (validado); respeitar `USAR_PROB_ABSOLUTA` por unidade (unidades sem prob. absoluta confiável
entram só no eixo de ranking); aplicar **haircut ~20%** em volume absoluto; **N=88 exige bootstrap/IC**.

**Caveat estrutural (registrar, não bloqueia LTV-01/02).** `unidade_para_motor.parquet` **não tem data
de abertura / idade da unidade** (as métricas de tempo são tenure de aluno, não idade da unidade) → o
"controlar por maturidade" do BLK-LTV-03 esbarra no **mesmo gap do gate G1 da DEC-001**. Sem esse
controle, a correlação território×retenção fica confundida por maturidade; tratar como confound
declarado no relatório.

---

- BLK-LTV-01 (concluído 2026-07-01) — ver tasks/completed.md



---

- BLK-LTV-03 (concluído 2026-07-01) — ver tasks/completed.md


---

- BLK-LTV-04 (concluído 2026-07-01) — ver tasks/completed.md


---

### BLK-FIX-LTV-01 — Guarda de skip faltante em `test_run_readonly_m1_por_mtime` (só teste)

| Campo | Valor |
|---|---|
| **Criticidade** | **Baixa** — só arquivo de teste; zero código de produção, READ-ONLY sobre o M1. |
| **Prioridade** | Baixa — a falha é local-only e **não** afeta o portão da `main`. |
| **Esteira** | Block Orchestrator → Builder. |
| **Status** | Pendente. |
| **Depende de** | — |
| **Autonomia** | **loop-safe** — READ-ONLY M1, só teste, sem VPS/deploy/segredos/PII, consome `data/staging`. |

**Problema (achado pelo QA do BLK-RELPON-13, 2026-07-24).**
`tests/unit/test_score_retencao_territorial.py::test_run_readonly_m1_por_mtime` guarda com `pytest.skip`
os **artefatos M1** ausentes (linhas 260-261), mas **não guarda a própria ENTRADA** que `run()` carrega
logo depois (linha 263): `data/staging/unidade_territorio_retencao.parquet`. Numa máquina de dev onde
alguns dos artefatos M1 existem mas esse dataset **não** existe, o skip não dispara e o teste morre com
`FileNotFoundError` em vez de pular. Em CI limpo `data/staging/` é gitignored → nenhum artefato M1 → o
teste pula; por isso o portão da `main` **não** é afetado (falha é local-only, reproduzida em 2026-07-24).

**Correção.** Estender a guarda para cobrir também o dataset de entrada: se
`data/staging/unidade_territorio_retencao.parquet` não existir, `pytest.skip` com a mesma mensagem de
"ambiente sem os parquets". **Não** alterar a semântica do teste — o assert de mtime (READ-ONLY M1)
permanece exatamente como está.

**Critério de aceite.** Em máquina sem o parquet de entrada o teste **pula** (não falha); em máquina com o
parquet ele roda e mantém o assert de mtime; `pytest -q` deixa de reportar esse `FAILED`.

---

### BLK-QA-XDIST-01 — `pytest -n auto` quebrado nesta estação (INTERNALERROR do `execnet`)

| Campo | Valor |
|---|---|
| **Criticidade** | **Baixa** — ergonomia de gate local; **não** afeta o portão da `main` (o CI roda serial, `ci.yml:60`). READ-ONLY sobre o M1. |
| **Prioridade** | Média — hoje o gate do QA custa **23 min** em serial contra os poucos minutos que o `-n auto` custava. |
| **Esteira** | Block Orchestrator → Builder. |
| **Status** | Pendente. |
| **Depende de** | — |
| **Autonomia** | *(sem marcador — **NÃO** loop-safe: o diagnóstico exige rodar/instalar tooling na estação, fora do container)* |

**Problema (achado e MEDIDO pelo QA do BLK-GRAPH-02, 2026-07-28).**
`python -m pytest -n auto` aborta com `INTERNALERROR` antes de coletar qualquer teste, na criação dos
workers (`xdist/workermanage.py:setup_node` → `execnet/gateway.py:_rinfo`). Três assinaturas alternando
entre execuções: `EOFError: couldn't load message header, expected 9 bytes, got 0`,
`OSError: [WinError 6] Identificador inválido` e `OSError: [WinError 50] Não há suporte para o pedido`
(em `_winapi.DuplicateHandle`). `os.cpu_count()` = 12 → `-n auto` = 12 workers.
Versões: `pytest 8.4.2`, `pytest-xdist 3.8.0`, `execnet 2.1.2`, Python 3.14 (Windows).

**PROVADO PRÉ-EXISTENTE — não é regressão do BLK-GRAPH-02:**
1. Reproduzido **3/3** em `tests/unit/test_claude_md_size.py` (2 testes, sem subprocess), cujo blob é
   **idêntico** ao da `main`, com `conftest.py` e a seção `[tool.pytest.ini_options]` também idênticos.
2. Reproduzido **2/2** em um `git worktree` da **`main` pura** (zero mudanças do ciclo). Nesse mesmo
   worktree o `-n 2` também caiu (`WinError 50`).
3. Reproduzido com **`-n 4`** na suíte completa (mesmo `INTERNALERROR`).
4. Os pacotes instalados pelo grupo `graph` (`mcp`, `graphifyy`, `starlette`, `sse-starlette`,
   `httpx-sse`, `pyjwt`) **não registram** nenhum entry point `pytest11` — não são a causa.
5. Fora do repositório, num diretório temporário com um teste trivial, `-n auto` **passa** — ou seja, a
   quebra aparece com o `conftest.py`/site-packages deste projeto carregados em 12 workers, não com o
   xdist em si.

**Histórico.** O `-n auto` **funcionava** (ver `tasks/completed.md`: "672 passed" e "678 passed ...
idêntico em `-n auto` e serial"). Regrediu em algum ponto entre aqueles ciclos e 2026-07-28.

**Correção sugerida (a confirmar por medição, não presumir).** Investigar (a) limitar workers por
`addopts`/`-n logical` ou um teto explícito no `pyproject.toml`; (b) `--dist loadfile` (reduz canais);
(c) bump de `pytest-xdist`/`execnet`; (d) compatibilidade do `execnet 2.1.2` com Python 3.14 no Windows
(`DuplicateHandle`). **Não** mascarar com `-p no:xdist`.

**Critério de aceite.** `python -m pytest -n auto -q` completa a suíte com a **mesma contagem** do serial
(hoje: `2028 passed, 2 skipped` + o `FAILED` conhecido do BLK-FIX-LTV-01), em 3 execuções seguidas.
Documentar no `prompts/qa_analyzer.md` o modo de execução vigente se a conclusão for mudar de `-n auto`.

---

## Projeto — Repaginação visual do dashboard (UX/UI)

- BLK-UI-11 (concluído 2026-06-29) — ver tasks/completed.md


---

- BLK-UI-10 (concluído 2026-07-06) — ver tasks/completed.md


---

## Relatório Pontual Censitário — geração em lote (2026-07-06, pedido de Vini)

> Espelha o **BLK-RELMUN-04** (Relatório Municipal em lote), agora para o **Relatório Pontual
> Censitário** (raio 1,5 km). Diferença estrutural: o municipal itera sobre um *multiselect* de
> municípios já existente; o pontual é dirigido por **um endereço/coordenada pesquisado por vez** →
> o mecanismo de lote é **acumular os endereços pesquisados** numa fila antes de gerar. Camada de
> visualização/relatório — **READ-ONLY sobre o M1** (§5).

- BLK-RELPON-04 (concluído 2026-07-06) — ver tasks/completed.md


---

## Epic BLK-ACENTO — Correção de acentuação e escrita (plataforma + relatórios)

> Origem: tarefa ClickUp **"Resolver Problemas de Escrita e Acentuação no Motor"** (`86e26mtn5`,
> lista *Motor de Expansão*, prioridade **urgente**, criador Felipe Castaldi, responsável Vinicius).
> Descrição: *"Resolva todos os problemas de gramática e escrita no site e nos relatórios gerados
> pelo Motor de Expansão."* Esclarecimento de Vinicius (2026-07-06): o problema é a **acentuação de
> TUDO** — tanto a plataforma (dashboard Streamlit) quanto os relatórios gerados (PDF/CSV); **muitas
> palavras não contêm acento** (ex.: "Relatorio", "Analise", "Nao", "concluido", "endereco",
> "ultimo", "Populacao", "municipio", "regiao", "voce", "opcao").
>
> **Diagnóstico técnico (auditoria 2026-07-06, ancorado no código):** a ausência de acento é
> majoritariamente **estilo/hábito herdado**, NÃO uma exigência técnica. No PDF, o core font
> `Helvetica` do `fpdf2` codifica em **`latin-1`**, que **cobre integralmente** os acentos
> portugueses (á â ã à ç é ê í ó ô õ ú ü); o helper `_ascii()` (`censo_report.py:170-172`,
> `relatorio_municipal.py:211-213`) reduz a latin-1 com `errors="replace"` e seu comentário-fonte
> (`censo_report.py:16-17`) generalizou incorretamente para "ASCII sem acento". Logo, **acentuar o
> texto-fonte é seguro hoje, sem trocar fonte/biblioteca.** O CSV é `utf-8-sig`
> (`censo_report.py:148`) — acentos seguros. Estado atual JÁ é misto (ex.: `pages.py:551`
> "Expansão de Domínio" já acentuado), reforçando que é descuido, não regra.
>
> **A ARMADILHA REAL não é o acento** e sim a **tipografia "esperta"**: travessão `—`/`–`, bullet
> `•`, seta `→`, reticências `…`, aspas curvas `" " ' '` e `©` estão FORA de latin-1 e viram `"?"`
> **silenciosamente** via `errors="replace"` no PDF. Todo texto-fonte de PDF deve usar ASCII simples
> para pontuação (hífen `-`, aspas retas `"`, "(c)") mesmo tendo acento nas letras.
>
> **READ-ONLY sobre o M1 (§5):** esta epic corrige APENAS texto voltado ao usuário. NÃO toca
> `score_priorizacao`/`hex_score_estrutural`/pesos/carteira/plano/artefatos oficiais, nem a lógica.
> É um trabalho de **display**, com a disciplina crítica de **jamais acentuar identificadores**.
>
> **Guardrail permanente (não regredir depois):** a regra de acentuação foi promovida a **CLAUDE.md
> §2** (fonte canônica lida antes de qualquer tarefa, inclusive pelos sub-agentes do `/run-cycle`),
> para que TODO trabalho POSTERIOR a esta epic mantenha a acentuação correta em strings novas/editadas
> e respeite a lista de proibições (identificadores). Esta epic é a correção retroativa; a §2 é a
> prevenção contínua.

**NÃO ACENTUAR (quebra lógica) — lista canônica de proibições (todos os sub-blocos):**
- `key=` de widgets Streamlit e chaves de `st.session_state` (ex.: `coord_search_input`,
  `dashboard_active_tab`, `relpon_lote_fila`, `btn_gerar_pdf_topo`, `multihex_cenario`) —
  `pages.py:802,1592,2472-2660,3096-3368`.
- Seletores CSS `.st-key-*` em `inject_styles` (`pages.py:154,358-448`) — ecoam as `key=` acima.
- **Valores brutos de enum/categoria** comparados em lógica E produzidos pelo pipeline core:
  `FAIXA_ORDEM = ["prioridade_maxima","alta","media","baixa","descartado","inviavel"]`
  (`constants.py:90-97`), exibido CRU no `st.multiselect` (`pages.py:668-671`), usado em
  `.isin(selected_faixas)` (`data.py:499`, `components.py:1706`) e como chave do dict de cores
  (`constants.py:289-292`); origem em `src/motor_expansao/core/constants.py`,
  `pipelines/calcular_colunas_mercado.py`, `pipelines/m1/*`. Também `HYBRID_ELIGIBILITY_ORDER`,
  `COVERAGE_BUCKET_ORDER`, `JOIN_QUALITY_ORDER` (`constants.py:86-88`), `template="classico"`,
  `METODO_RELATORIO_*` (`censo_point.py:15`, `relatorio_municipal.py:58`). **Solução: camada de
  LABEL DE EXIBIÇÃO (`{valor_bruto: "Texto Acentuado"}`) — nunca tocar o literal usado na lógica.**
- Nomes de coluna de DataFrame (`score_priorizacao`, `nome_municipio`, `renda_per_capita`,
  `faixa_oportunidade`, `cod_municipio`, ...) — schema compartilhado com o M1/pipeline.
- Slugs/nomes de arquivo — JÁ protegidos por `_slug()`/`unicodedata` (`relatorio_municipal.py:216-221`)
  e `_relmun_key_slug` (`pages.py:3194`); não mexer.

**Decomposição (sequência recomendada):** BLK-ACENTO-01 (UI dashboard) -> BLK-ACENTO-02 (relatórios
PDF/CSV). Sub-blocos independentes (podem ir em PRs separados); cada um traz seus próprios testes.

---

- BLK-ACENTO-01 (concluído 2026-07-08) — ver tasks/completed.md


---

- BLK-ACENTO-02 (concluído 2026-07-08) — ver tasks/completed.md


---

- BLK-MAP-02 (concluído 2026-07-08) — ver tasks/completed.md


---

- BLK-RELMUN-05 (concluído 2026-07-08) — ver tasks/completed.md


---

- BLK-RELMUN-06 (concluído 2026-07-10) — ver tasks/completed.md


---

- BLK-RELPON-05 (concluído 2026-07-10) — ver tasks/completed.md


---

## Epic BLK-ORQ — Governança de merge por checks de CI (autonomia da esteira; **DEC-016**)

> **Origem (2026-07-13, aprovado por Felipe — DEC-016, §8):** o gate humano único em TODO merge é o
> gargalo dominante da esteira. A epic troca o portão "1 aprovação humana" por um portão de **checks de CI
> auditáveis** (`test` + `guard` + `claude-review` + `review-gate`), com **auto-merge nativo** para blocos
> **Baixa/Média** e label humana para **Alta** (`aprovado-humano`) / **Crítica** (`critica-aprovada`, aplicada
> pelo próprio Felipe, login `Kastaldy`). **READ-ONLY sobre o M1 em todos os blocos** (§5): nenhum toca
> `score_priorizacao`/`hex_score_estrutural`/pesos/`config.py`/`pipelines/m1/`/carteira/plano/artefatos oficiais.
> **Deploy continua NUNCA automático** — auto-merge não deploya (push na `main` só publica imagem no GHCR).
>
> **Ordem obrigatória:** BLK-ORQ-20 (checks existem e rodam) → **BLK-ORQ-21** (só então aplicar a proteção, com
> `require_code_owner_reviews: true` + teste anti-spoof N0) → BLK-ORQ-22 (Garimpeiro) / BLK-ORQ-23 (Auditor).
> Inverter 20↔21 **trava todos os PRs do repo** (ver ORQ-21). **BLK-ORQ-24** (separar housekeeping do backlog)
> depende só do 20 e deve entrar **antes de ligar o auto-merge do loop** — senão todo PR de ciclo cai em
> governança e nada mergeia sozinho.

---

- BLK-ORQ-20 (concluído 2026-07-14) — ver tasks/completed.md


---

- BLK-ORQ-21 (concluído 2026-07-14) — ver tasks/completed.md


---

- BLK-ORQ-22 (concluído 2026-07-15) — ver tasks/completed.md


---

- BLK-ORQ-23 (concluído 2026-07-15) — ver tasks/completed.md



---

- BLK-RELPON-08 (concluído 2026-07-15) — ver tasks/completed.md


---

## Epic BLK-WEB — Piloto Web App (React + deck.gl) das telas Mapa e Viabilidade (substituição faseada do Streamlit; READ-ONLY sobre o M1)

> **Origem (2026-07-19, pedido de Felipe):** construir o **piloto completo** de um web app dedicado que
> reproduz o Motor com UX/UI muito melhor, começando pelas **duas telas** do protótipo — **Mapa** e
> **Viabilidade** — **preservando 100% das funções que essas abas têm hoje** (seleção de hex, busca,
> entorno, cenário multi-hex, relatórios, etc.). Handoff de produto: **`PLANO_APP_WEB.md`** (raiz, ajustado
> nesta mesma entrega para refletir a realidade do repo). Referência visual: **`Motor de Expansão -
> Referência (standalone).html`** (raiz) — spec visual de alta fidelidade; **o mapa nela é FALSO** (hexágonos
> em CSS, dados mockados) → no app vira `H3HexagonLayer` deck.gl sobre dados reais.
>
> **Arquitetura alvo:** motor Python **INTOCADO** → **API FastAPI fina read-only** (estende a que já existe)
> → **frontend React + deck.gl + MapLibre**. Roda **EM PARALELO** ao Streamlit. **READ-ONLY sobre o M1 em
> TODOS os blocos** (§5): nenhum recalcula `score_priorizacao`/`hex_score_estrutural`/pesos/carteira/plano/
> artefatos oficiais; a API só **lê e serializa** os Parquets que o motor já gera; o guardrail "nada
> recalcula score" fica garantido por construção.
>
> **Realidade do repo que muda o custo (confirmada por varredura de código, 2026-07-19):**
> - **Motor desacoplado — CONFIRMADO:** a camada de compute é **100% st-free** (`data.py`, `competitors.py`,
>   `censo_point.py`, `censo_map.py`, `censo_report.py`, `relatorio_municipal.py`, `viabilidade_charts.py`,
>   `dimensionamento/*`, `constants.py`, `utils.py` = zero `import streamlit`). O acoplamento vive em
>   `streamlit_app.py` (704 LOC, 16 loaders cacheados), `pages.py` (4908 LOC, 539 `st.`) e `components.py`.
> - **API FastAPI production-grade JÁ EXISTE e está LIVE** (`api.ultra-expansao.tech`): `src/motor_expansao/api/`
>   (~2432 LOC) com factory, **auth Bearer token→consumidor**, CORS, modelo de erro `{detail,codigo}`, settings,
>   versionamento, `Dockerfile.api`, `docker-compose.prod.yml`, **publish por digest no GHCR** e bot Telegram.
>   **Fase 0 ESTENDE essa API, não cria do zero.** Hoje há 5 endpoints; `/ponto/censitario` **já existe** como
>   `POST /api/v1/analisar`; `/ufs` existe mas **aponta para a base de mercado** (repontar p/ partições enriquecidas).
> - **Basemap MapLibre JÁ self-hosted:** `tileserver-gl` (OpenMapTiles) roteado por Caddy em `/tiles/` same-origin
>   (`docker-compose.yml` + `caddy/tiles.Caddyfile`, montados localmente). A parte mais dura da infra de mapa está resolvida.
> - **Spike deck.gl prévio:** `src/motor_expansao/dashboard/ui_spike_deckgl.py` (810 LOC) — ativo de referência.
> - **Relatórios são server-side puros** (`censo_report.py`→bytes, `gerar_excel_viabilidade`→bytes,
>   `relatorio_municipal.py`, `montar_payload_viabilidade`) → viram **endpoint de download, não React**.
>
> **Ordem (dependência real):** Fase 0 backend (**01→02/03/04→05**) → Fase 1 mapa (**06→07 [spike, marca-passo]→08**)
> → Fase 2 viabilidade (**09**) → **10** (deploy paralelo) → **11** (paridade/aceite). O **mapa deck.gl (07)** e a
> **paridade byte-a-byte (11)** são os marca-passos; o resto é port de spec conhecida sobre back pronto.
>
> **Escopo do corte do Streamlit (DEC-019, decisões de produto de Felipe em 2026-07-23):** "substituir 100% o Streamlit"
> passa a significar **paridade de apenas 3 telas — Mapa + Visão Executiva + Viabilidade** (gate de aceite = **BLK-WEB-11**),
> **sem** portar Domínio nem Carteira/Plano como abas. **Três decisões fecham o escopo:**
> 1. **Expansão de Domínio NÃO vira aba** — a **Fase 4 (camada 4) do Mapa Territorial** (recomendação + ordem de expansão +
>    Relatório Municipal) já entrega essa análise; a parte de domínio prevista no **BLK-WEB-02** fica **CANCELADA**.
> 2. **A aba "Carteira e Plano" vira "Oportunidades Imobiliárias"** — nasce como **PLACEHOLDER**. As tabelas atuais de
>    **Carteira acionável + Plano curto prazo (T+0..T+9) são DROPADAS** (funil + Relatório Municipal já cobrem), e a parte
>    de carteira/plano prevista no **BLK-WEB-02** fica **CANCELADA**. A feature plena (mapear oportunidades de imóveis no
>    mapa + coletores imobiliários online) é uma **EPIC FUTURA própria** — nova fonte de dados de imóveis, que **merece DEC +
>    spec próprias**.
> 3. **Critério de corte redefinido:** aposentar o Streamlit = **paridade de Mapa + Visão Executiva + Viabilidade**,
>    validada em **BLK-WEB-11** — nada além dessas 3 telas. **Caveat:** a **Visão Executiva** depende de
>    `growth_api_historico.parquet`, **hoje AUSENTE em prod** (`GET /api/executiva/{uf}` → **HTTP 404**); gerar/deployar esse
>    parquet é pré-requisito da paridade da tela executiva.
> **Deploy SEMPRE manual, por digest, pelo Felipe (§6) — auto-merge não deploya.**
>
> **Governança loop-safe:** **nenhum bloco entra marcado `loop-safe`** — essa marcação é **pré-aprovação HUMANA**
> (§6.1: "ALGUÉM humano precisa adicionar essa linha"). Os blocos de **backend (01–05)** são **candidatos naturais**
> (mecânicos, READ-ONLY, verificados por teste de contrato, sem deploy, reusam o extra `[api_mvp]` sem dep nova);
> Felipe/Vini adicionam a linha `| **Autonomia** | loop-safe ... |` se quiserem a esteira autônoma. **Frontend
> (06–09) e deploy (10) NUNCA são loop-safe** (UX/visual exige olho humano — lição BLK-UI-10/BLK-VIAB-09;
> toolchain Node/Vite fora do container Python do loop; deploy toca VPS/CI).

---

### BLK-WEB-01 — API base: catálogo de UF + slice por UF com filtros server-side + fundação compartilhada

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (nova superfície read-only na API existente; **READ-ONLY sobre o M1** — só serializa artefatos, não altera nenhum score). |
| **Prioridade** | Alta (funda a Fase 0; tudo depende dela). |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA — contrato de resposta]` → Builder → QA. |
| **Status** | Concluído (em prod, rev 9b60761): os 3 endpoints existem e respondem — GET /api/ufs (catálogo), GET /api/uf/{uf} (slice + funil), GET /api/municipios/{uf} — sobre fundação compartilhada (`MOTOR_DATA_DIR`, `lru_cache` por UF, serialização). Ressalva: o slice usa funil narrativo + cap 15k em vez dos 8 filtros globais e da banda de cor server-side. |
| **Depende de** | — (primeiro bloco do epic). |
| **Autonomia** | **manual por padrão (candidato a loop-safe)** — mecânico, READ-ONLY M1, verificado por teste de contrato, não toca deploy/VPS/segredos, consome `data/outputs`/`data/staging`, sem dep nova (`[api_mvp]`). Qualifica p/ loop-safe, mas a marcação é pré-aprovação HUMANA (§6.1). |

**Contexto.** A API existente (`src/motor_expansao/api/`) é orientada a PDF de ponto/município; falta a superfície de
"dados de dashboard". As funções puras já existem: `list_partitioned_ufs` (`data.py:65`), `read_enriched_uf_partition`
(`data.py:82`), `apply_global_filters` (`data.py:477`), `list_censo_geo_municipios` (`data.py:130`). Os **paths estão
hardcoded** em `streamlit_app.py:187-214` e o cache é `@st.cache_*` (`streamlit_app.py:277-460`).

**Objetivo.** Endpoints: **`GET /ufs`** (catálogo — **repontar** de `_MERCADO_PARQUET` para `list_partitioned_ufs`
sobre `hexagonos_dashboard_enriquecido/`, `service.py:438`); **`GET /uf/{uf}`** (slice de hexes via
`read_enriched_uf_partition` + `apply_global_filters` server-side com os **8 params** — `municipios[]`, `faixas[]`,
`elegibilidade_hibrida[]`, `cobertura[]`, `qualidade[]`, `only_top_municipio`, `only_top_hex_intraurbano` — aplicar
`MAP_POINT_LIMIT`/`_LARGE` (`constants.py:117`) server-side, preservar **colunas oficiais** e já enviar a **banda de
cor** por `RESIDUAL_SCORE_BANDS` (`constants.py:328`); **`GET /uf/{uf}/municipios`** (`list_censo_geo_municipios`).
Criar a **fundação compartilhada**: módulo de config/paths (tira do `streamlit_app.py`), camada de serialização
(dicts com DataFrames aninhados → `to_dict("records")`), `functools.lru_cache` por UF (drop-in dos `@st.cache_*`).

**Preserva (paridade):** seleção de UF com carga lazy (S1), filtros globais (S2), régua de recorte "X hex | Y UF | Z cidades".

**Guardrail.** §5 READ-ONLY M1; a API **importa `data.py`/`constants.py`, NUNCA `pages.py`/`components.py`/`streamlit_app.py`**
(que arrastam Streamlit). Nomes/valores de coluna oficiais intactos. Teste de contrato: JSON == números do Streamlit.

---

### BLK-WEB-02 — API de overlays + tabelas operacionais (concorrentes, Ultra, atlas de ícones, domínio, carteira, plano)

| Campo | Valor |
|---|---|
| **Criticidade** | **Baixa** (wraps finos de função pura; **READ-ONLY sobre o M1**). |
| **Prioridade** | Média. |
| **Esteira** | Block Orchestrator → Planner → Builder → QA. |
| **Status** | Concluído (escopo reduzido pela DEC-019, em prod rev 9b60761): overlays de concorrentes/Ultra + atlas de ícones quadrados servidos via campo `pins` nas respostas de /api/municipio e /api/uf, consumidos no MapScreen. **Domínio, carteira, plano e vazios competitivos: CANCELADOS pela DEC-019.** |
| **Depende de** | **BLK-WEB-01** (fundação de config/serialização/cache). |
| **Autonomia** | **manual por padrão (candidato a loop-safe)** — mesmo perfil do 01 (mecânico, READ-ONLY, teste de contrato, sem deploy/dep nova). Marcação = pré-aprovação humana (§6.1). |

**Contexto.** Camadas visuais de apoio; funções puras prontas: `load_competitor_points` (`competitors.py:323`),
`load_ultra_points` (`competitors.py:397`), `build_icon_atlas` (`competitors.py:571`). Domínio/carteira/plano são
`pd.read_parquet` diretos dos artefatos (`plano_expansao_dominio.parquet`, `carteira_expansao_acionavel.parquet`,
`plano_expansao_curto_prazo.parquet`).

**Objetivo.** **`GET /overlays/concorrentes`** (filtro `uf`/`municipio`/`rede` + `COMPETITOR_PIN_LIMIT` 6000 + cluster
em escopo largo — `constants.py:128,133`), **`GET /overlays/ultra`**, servir o **atlas/sprite de ícones** (`build_icon_atlas`)
para o `IconLayer` do deck.gl, **`GET /dominio`**, **`GET /carteira`**, **`GET /plano`** (filtro `uf`/`municipio`), e o
overlay opcional `vazios_competitivos_lc` (`data/staging/vazios_competitivos_lc.parquet`).

**Preserva (paridade):** overlays Concorrentes/Ultra/Âncoras Domínio/Vazio LC (M3/M4/M16), filtro por rede (M5),
pins com logo + cluster (M7/M16).

**Guardrail.** §5 READ-ONLY M1; respeitar caps/amostragem determinística; pins são camada visual (não afetam score/ranking).

---

### BLK-WEB-03 — API de análises pontuais interativas (entorno 1.6 km, cenário multi-hex, ponto censitário 1.5 km)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (motor interativo das telas; **READ-ONLY sobre o M1**). |
| **Prioridade** | Alta (a interatividade do mapa depende dela). |
| **Esteira** | Block Orchestrator → Planner → Builder → QA. |
| **Status** | Concluído (parcial, em prod rev 9b60761): ponto censitário 1,5 km via POST /api/relatorio/pontual (`analisar_ponto_censitario_setores`); multi-hex agregado no cliente (MapScreen). Sem API /ponto/entorno nem /cenario/multihex — o estudo pontual roteia para a Viabilidade. |
| **Depende de** | **BLK-WEB-01**. |
| **Autonomia** | **manual por padrão (candidato a loop-safe)** — funções puras, READ-ONLY, teste de contrato; sem rede (o geocoding da busca fica no 06, humano). Marcação = pré-aprovação humana (§6.1). |

**Contexto.** Helpers puros já retornam dicts prontos: `analisar_entorno_ponto` (`data.py:726`, raio 1.6 km),
`agregar_cenario_multihex` (`data.py:863`, **25 campos**), `analisar_ponto_censitario_setores` (`censo_point.py:155`,
raio fixo **1.5 km** `censo_point.py:23`), `parse_hex_ids_from_text` (`data.py:1015`), `lookup_hex_by_coord`.

**Objetivo.** **`GET /ponto/entorno?lat=&lng=&raio_km=1.6`**; **`POST /cenario/multihex`** (lista de `hex_id` →
`agregar_cenario_multihex`, aceitar colar lista via `parse_hex_ids_from_text`, devolver os 25 campos +
`hexes_selecionados`); **`GET /ponto/censitario?lat=&lng=`** — **alinhar/reusar** o `POST /api/v1/analisar`
(`routes/analisar.py:31`) já existente (mesmo engine). Endpoint auxiliar `lookup_hex_by_coord` (busca → hex).

**Preserva (paridade):** click no hex → centroide res-7 → entorno (M6/M13), pins no raio via `filter_points_to_radius`,
cenário multi-hex com add/remove/colar/copiar e os 25 KPIs (M10/M11), disclaimer de centroide.

**Guardrail.** §5 READ-ONLY M1; centroide de hex como aproximação (documentar na UI); serializar DataFrames aninhados.

---

### BLK-WEB-04 — API de viabilidade (JSON + Excel + PDF)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (expõe o engine property-first; **READ-ONLY sobre o M1**; não altera o simulador). |
| **Prioridade** | Alta (Fase 2 depende dela). |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA — schema de request]` → Builder → QA. |
| **Status** | Concluído (parcial, em prod rev 9b60761): POST /api/viabilidade (JSON completo — break-even, aluguel-teto, p10/p50/p90, grade de sensibilidade, série 60m, DRE cascata) e PDF via /api/relatorio/pontual (viabilidade embutida). Falta o export Excel (`gerar_excel_viabilidade` não exposto). |
| **Depende de** | **BLK-WEB-01**. |
| **Autonomia** | **manual por padrão (candidato a loop-safe)** — engine já é função pura; wrap + serialização verificáveis por teste; sem deploy/dep nova. Marcação = pré-aprovação humana (§6.1). |

**Contexto.** O engine é **puro e desacoplado** (DEC-009): `analisar_viabilidade_ponto` (`dimensionamento/viabilidade_ponto.py:318`)
→ `ViabilidadePontoResult` (dataclass, `:74/:104`); a matemática vive em `dimensionamento/simulador.py` (`viabilidade`
`:89` — DRE em cascata; `aluguel_teto` `:436` e `alunos_minimos_viaveis` `:494` via `scipy.brentq`; `gerar_serie_mensal`
`:340` — rampa `SIM_MATURACAO_MESES` mês 8 + FCF 60m). `render_viabilidade_ponto` (`pages.py:3790`) é **só UI**.
Excel (`gerar_excel_viabilidade` `dimensionamento/excel_export.py:334`→bytes) e o payload de PDF (`montar_payload_viabilidade`
`viabilidade_charts.py:179`) **já são server-side**.

**Objetivo.** **`POST /viabilidade`** (schema de request: ponto, `m2`, `aluguel`, `demanda` premissa, `usar_p50`, params
avançados — ticket/margem/capex/financiamento; resposta: KPIs, break-even, aluguel-teto, faixa p10/p50/p90
(`faixa_alunos_por_densidade` `:125`), grade de sensibilidade, **série 60m** e **DRE cascata**; mapear `inf`→JSON-safe
como o Excel já faz); **`POST /viabilidade/excel`** (`gerar_excel_viabilidade`→bytes); **`POST /viabilidade/relatorio-pdf`**
(portar o assembly de `_render_relatorio_pdf_imovel` (`pages.py:3697`) + `_montar_insumos_censo_pdf` (`pages.py:3615`)
para a camada `api/service.py`; só o `st.spinner` é cosmético).

**Preserva (paridade):** todos os resultados da tela (V4–V9), a demanda **como premissa** (DEC-009, nunca prevista pela
geografia), split balcão ~69%/agregadores ~31%.

**Guardrail.** §5 READ-ONLY M1; não muta o simulador/coeficientes; PDF usa `[basemap]`/`contextily` já embutido (DEC-004/011)
com fallback offline; anti-PII (nada persistido).

---

### BLK-WEB-05 — API de relatórios do mapa (download): Relatório Pontual Censitário (PDF+CSV) + Relatório Municipal (PDF)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (expõe relatórios existentes como download; **READ-ONLY sobre o M1**). |
| **Prioridade** | Média. |
| **Esteira** | Block Orchestrator → Planner → Builder → QA. |
| **Status** | Concluído (parcial, em prod rev 9b60761): POST /api/relatorio/pontual (PDF, com fotos/imóvel/viabilidade) e POST /api/relatorio/municipal (PDF 9 págs), ambos ligados no front (ViabilityScreen/MapScreen). Falta: export CSV de setores do Pontual e suporte a fila/lote (i/N). |
| **Depende de** | **BLK-WEB-03** (contexto de ponto/censo). |
| **Autonomia** | **manual por padrão (candidato a loop-safe)** — geradores já são server-side puros (bytes); wrap de download + tiles online (DEC-004/011, cache+fallback). Marcação = pré-aprovação humana (§6.1). |

**Contexto.** Relatório Pontual Censitário e Relatório Municipal já geram **bytes** server-side
(`gerar_payloads_relatorio_pontual_para_pin` `pages.py:2975`; `relatorio_municipal.py` via `agregar_municipio` +
`render_mapas_municipio`, tiles online DEC-011). O PDF pontual já é servido pela API (`service.gerar_pdf_ponto`).

**Objetivo.** Endpoints de **download**: Relatório Pontual Censitário (PDF **e** CSV; reusar o caminho `/analisar` PDF +
o CSV de setores), Relatório Municipal (PDF 9 páginas), com suporte a **fila/lote** (i/N). Fundo de ruas por tiles
online sob as mitigações da **DEC-004/DEC-011** (cache `data/cache/basemap_tiles/`, fallback offline gracioso, import lazy).

**Preserva (paridade):** Relatório Pontual (M14) com fila + single + 2×2 mapas + PDF/CSV; Relatório Municipal (M15);
botões-topo compartilhados (S6).

**Guardrail.** §5 READ-ONLY M1; DEC-004/011 vigentes; anti-PII (`.pptx`/cartão de contato nunca embutidos).

---

### BLK-WEB-06 — Frontend scaffold (Vite + React + TS) + AppShell + Design System (tokens §7) + CommandBar + busca

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (funda o frontend; introduz toolchain Node; **READ-ONLY sobre o M1**). |
| **Prioridade** | Alta (Fase 1). |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA — UX/visual]` → Builder → QA. |
| **Status** | Concluído (em prod, rev 9b60761): scaffold Vite+React+TS, AppShell (Dock de 5 destinos, domínio/carteira desabilitados), design system (Glass/Chip/Kpi) e busca coord/link Maps + geocode Nominatim. Ressalva: `fetch` em vez de react-query; sem Plus Code/short-link no cliente. |
| **Depende de** | **BLK-WEB-01** (para `/ufs` + `/uf/{uf}`). |
| **Autonomia** | **manual (NÃO loop-safe)** — toolchain Node/Vite (fora do container Python do loop) + revisão visual humana + a busca por endereço usa **rede ao vivo** (DEC-010/Nominatim). NUNCA loop-safe. |

**Contexto.** Frontend novo em `web/` (ou similar): **React + TypeScript + Vite + @tanstack/react-query**, `deck.gl`,
`maplibre-gl`. Design system da **§7 do `PLANO_APP_WEB.md`** (cores, Manrope + JetBrains Mono, vidro/backdrop-blur,
raios, ícones line minimalistas).

**Objetivo.** `AppShell` (Dock lateral com 5 destinos + área de conteúdo por tela), `CommandBar` (título +
**busca** coordenada/endereço/link Maps/Plus Code + seletor de UF + pill "Modo guiado"), `GlassPanel` base,
`TagPill`, `Kpi`, wiring `react-query` a `GET /ufs` e `GET /uf/{uf}`. A busca reusa a **cascata de 4 passos** do
`render_coord_search_sidebar` (`pages.py:807`): `parse_coordinate_input` (offline) → link Maps (`extract_any_coord` +
`resolve_short_link`) → Plus Code → endereço `resolve_endereco_http` (Nominatim), com o card de resultado (S5) e o
link-fallback offline. Rede só neste sub-caminho (DEC-010: cache, timeout, fallback, anti-PII).

**Preserva (paridade):** chrome global S3/S4/S5 (nav, busca 4-passos, card do hex pesquisado).

**Guardrail.** §5 READ-ONLY M1; DEC-010 (rede só na resolução de endereço, cache/fallback/anti-PII); só cor a partir de
score no cliente — **nunca** cálculo de score.

---

### BLK-WEB-07 — MapCanvas: spike deck.gl + MapLibre (H3 real + pins + click-select + 4 modos + caps + perf) — MARCA-PASSO

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (o item de maior risco/incerteza do piloto; **READ-ONLY sobre o M1**). |
| **Prioridade** | Alta — **medir primeiro** (o marca-passo do calendário). |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA — visual/perf]` → Builder → QA. |
| **Status** | Concluído (em prod, rev 9b60761): HexMap.tsx com `H3HexagonLayer` (score→cor por faixa, <5k cinza, NaN fill), `IconLayer` de pins Ultra/concorrentes, click→select, tooltip de 7 linhas, hex buscado e multi-hex destacados. Spike aprovado (08/09 construídos por cima). Ressalva: basemap CARTO Dark Matter online (não o `/tiles/` self-hosted); modos = passos do funil (sem híbrido explícito). |
| **Depende de** | **BLK-WEB-06** + **BLK-WEB-01** + **BLK-WEB-02**. |
| **Autonomia** | **manual (NÃO loop-safe)** — WebGL/perf/visual exige olho humano; toolchain Node. NUNCA loop-safe. |

**Contexto.** O mapa da referência é **FALSO** (hexágonos CSS); o real é `H3HexagonLayer`. Ativo de referência:
`ui_spike_deckgl.py` (810 LOC). Basemap MapLibre **já self-hosted** em `/tiles/` (same-origin). O paralelo Streamlit é
`build_unified_map_figure_cached` (`components.py:80`) + `st.pydeck_chart(on_select="rerun")` (`pages.py:4386`).

**Objetivo (isolado, medível):** `MapCanvas` com `H3HexagonLayer` colorido por `RESIDUAL_SCORE_BANDS` nos modos
**censitário** (default visível), **residual** e **domínio** (M1/híbrido disponíveis nos dados, ocultos como hoje —
`MAPA_COLOR_MODES_OCULTOS`), basemap MapLibre `/tiles/`, pan/zoom, **`IconLayer`** de pins (Ultra `__ultra__` +
concorrentes por logo via atlas do BLK-WEB-02) + cluster em escopo largo, **click no hex → centroide res-7 → select**
(equivale ao `_extract_click_coord_from_selection` `pages.py:2815`), tooltip de 7 linhas (M8), descartados <5k cinza
(M9), hex pesquisado destacado, highlight laranja de multi-hex, caps `MAP_POINT_LIMIT`/`_LARGE`, e **medir performance
em UFs grandes** (SP/AM/PA/MG/BA) vs baseline. Entregável de spike: relatório curto de perf + "vai/não-vai" da abordagem.

**Preserva (paridade):** render do mapa + seleção por clique (M6), tooltips (M8), caps/sampling (M7), coloração de
descartados (M9), pins (M16).

**Guardrail.** §5 READ-ONLY M1; manter os caps (anti-OOM/WebGL); centroide como aproximação; só score→cor no cliente.

---

### BLK-WEB-08 — Tela Mapa completa: narrativa em 4 camadas + funil + seleção + entorno + multi-hex + filtros + relatórios

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (superfície principal do piloto; **READ-ONLY sobre o M1**). |
| **Prioridade** | Alta. |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA — UX/visual]` → Builder → QA. |
| **Status** | Concluído (parcial, em prod rev 9b60761): Mapa com narrativa em 4 camadas + funil real, filtros UF/município/melhores + busca/geocode, multi-hex (compara + copia IDs), tooltips com renda domiciliar, Relatório Municipal/Pontual. Ressalva: entorno 1,6 km dobrado na Viabilidade; multi-hex e conjunto de filtros simplificados vs spec (sem 25 KPIs, sem os 8 filtros). |
| **Depende de** | **BLK-WEB-07** + **BLK-WEB-03** + **BLK-WEB-02** + **BLK-WEB-05**. |
| **Autonomia** | **manual (NÃO loop-safe)** — UI exige revisão visual humana (lição BLK-UI-10/BLK-VIAB-09). NUNCA loop-safe. |

**Contexto.** Junta o MapCanvas (07) com a narrativa/§9 do plano e **todas as funções da aba Mapa** hoje
(`render_mapa_territorial` `pages.py:4775`). A narrativa em 4 camadas (`mstep` 1→4) é a **reorganização de UX** do
protótipo sobre os modos de cor reais.

**Objetivo.** `RecommendationPanel` + `NarrativeTimeline` (stepper 1→4 + funil com **números reais** derivados dos
endpoints, não fixos) + `RankedList`; filtros globais (8 filtros, S2) na UI; modos de cor + **legenda de 10 faixas**
(M1/M2); overlays multiselect + rede de concorrentes + vazio LC (M3/M4/M5); **click → Análise Pontual de Entorno**
1.6 km (single + multihex, M13) via `/ponto/entorno`; **Cenário Multi-Hex** (add/remove, colar lista, **copiar hex_id**,
25 KPIs, highlight laranja "Atualizar mapa", M10/M11) via `/cenario/multihex`; Detalhamento territorial (Análise +
Ranking, M12); **Relatório Pontual Censitário** (fila + single, PDF/CSV, 2×2 mapas, M14) e **Relatório Municipal** (M15)
via BLK-WEB-05; tooltips completos incl. renda média domiciliar (M8).

**Preserva (paridade):** **TODAS** as features M1–M16 da aba Mapa + chrome S1–S6.

**Guardrail.** §5 READ-ONLY M1; "camada visual · read-only M1" visível (princípio §8.6); só score→cor no cliente.

---

### BLK-WEB-09 — Tela Viabilidade completa: cenário (stress-test) + veredito + KPIs + régua break-even + DRE + rampa + FCF + relatório

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (segunda tela do piloto; **READ-ONLY sobre o M1**). |
| **Prioridade** | Alta. |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA — UX/visual]` → Builder → QA. |
| **Status** | Concluído (parcial, em prod rev 9b60761): ViabilityScreen sobre POST /api/viabilidade + /api/faixa-alunos + PDF via /api/relatorio/pontual (veredito, KPIs, régua break-even, faixas p10/p50/p90, rampa, FCF/FCO/DRE, fotos/dados do imóvel). Falta o export Excel (V9) e a grade de sensibilidade na UI (V7, já retornada pelo backend). |
| **Depende de** | **BLK-WEB-06** + **BLK-WEB-04**. |
| **Autonomia** | **manual (NÃO loop-safe)** — UI exige revisão visual humana. NUNCA loop-safe. |

**Contexto.** Espelha `render_viabilidade_ponto` (`pages.py:3790`) sobre `POST /viabilidade`. É **stress-test de um
imóvel real** (DEC-009): a demanda é **premissa do operador**, nunca prevista pela geografia. Todo cálculo no backend.

**Objetivo.** `ScenarioForm`: captura do ponto (coord/link Maps offline + **breadcrumb** "↩ vindo do mapa" do
`search_pin`, V1), inputs (metragem, aluguel, checkbox p50, demanda, params avançados: ticket/margem/capex/financiamento,
V2); resultados: **Verdict banner** + KPIs (break-even, aluguel-teto, margem EBITDA, payback, ROIC, faturamento, EBITDA,
viável — V4), faixa **p10/p50/p90** (V5), contexto de catchment + zona morta (V6), **régua de equilíbrio** (peça
principal, §10 do plano) + sensibilidade demanda×aluguel (V7), **4 gráficos** (rampa, faturamento/EBITDA, **FCF
acumulado**, **DRE em cascata** — V8), **Excel** (V9) e **Relatório completo (PDF)** com "Dados para o relatório"
(fotos até 2 + endereço/valor/pé-direito/vagas/tipo/obs, V11) via `/viabilidade/relatorio-pdf`.

**Preserva (paridade):** **TODAS** as features V1–V11 da aba Viabilidade.

**Guardrail.** §5 READ-ONLY M1 (não muta score/carteira/plano/artefatos); demanda como premissa; usa faixas, não pontos.

---

### BLK-WEB-10 — Deploy do piloto EM PARALELO ao Streamlit (serviço web nginx + rota Caddy + auth + CI por digest)

| Campo | Valor |
|---|---|
| **Criticidade** | **Crítica** (toca `deploy/`/`Dockerfile.*`/`docker-compose*`/Caddy/**CI** + VPS; exige **`critica-aprovada`** do Felipe — DEC-016). |
| **Prioridade** | Média (depois das duas telas prontas). |
| **Esteira** | Block Orchestrator → Planner → `[GATE HUMANO — deploy/VPS/auth/LGPD]` → Builder → QA. |
| **Status** | Concluído (em prod, rev 9b60761): `Dockerfile.web` (build Vite + FastAPI servindo SPA+API na 8899), job `publish-web` no CI por digest (WEB_IMAGE, Trivy bloqueante), serviço `web` no `docker-compose.prod.yml` ao lado do Streamlit, Caddy `reverse_proxy web:8899` atrás do Authelia; container `motor_expansao_web` vivo. (SPA via FastAPI StaticFiles, não nginx.) |
| **Depende de** | **BLK-WEB-08** + **BLK-WEB-09**. |
| **Autonomia** | **manual (NÃO loop-safe)** — o `loop_guard` aborta em `deploy/`/`Dockerfile.*`/compose/CI; deploy sempre manual por digest (§6). NUNCA loop-safe. |

**Contexto.** Prod atual = 5 serviços em `docker-compose.prod.yml` (streamlit, api, telegram-bot, caddy, authelia);
único ingress é o Caddy (80/443); a **API hoje não tem porta no host** (interna, só o bot consome) e `API_CORS_ORIGINS`
é curinga. Precedente de API pública com Bearer: `api.ultra-expansao.tech`.

**Objetivo.** Adição **aditiva**: `Dockerfile.web` (build Vite → nginx estático), job **`publish-web`** no CI +
`WEB_IMAGE` por digest (introduz toolchain Node/Vite no CI hoje só-Python), serviço `web` no compose, **rota Caddy**
(subdomínio dedicado **ou** `/app` + `/api/*` same-origin sob **Authelia**, reusando o truque do `/tiles/`),
`API_CORS_ORIGINS` **restrito**, expor a API ao browser. **DECISÃO de auth/LGPD no gate:** Authelia interno
(recomendado — dados de dashboard atrás de login) **vs** Bearer; a API pública NÃO deve ganhar endpoints de dados de
dashboard sem gate. Roda **AO LADO** do Streamlit (sem corte).

**Guardrail.** §6 (nenhum comando na VPS sem confirmação, comando a comando; deploy por digest, manual); §5 READ-ONLY M1.
**Não** aposenta o Streamlit (isso é decisão futura + DEC).

---

### BLK-WEB-11 — Paridade byte-a-byte + critérios de aceite do piloto (§15) + baseline de performance

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (porta de validação do piloto; **READ-ONLY sobre o M1**). |
| **Prioridade** | Média (fecha o piloto). |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA — aceite/UX]` → Builder → QA. |
| **Status** | **Pendente (gate do corte, mas AVANÇADO)** — o núcleo automatizável **já existe**: `tests/unit/test_piloto_web_endpoints.py` (24 testes: contrato de todos os endpoints + JSON-safe + **guardrail READ-ONLY estático (AST) e runtime** por snapshot do FS). **Baseline de performance MEDIDO em prod (2026-07-23, rev 9b60761):** `/api/uf/{uf}` em **0,6–1,2 s/UF** (SP 1,21 s cold / 0,98 s warm), resposta ~3 MB capada por `MAP_POINT_LIMIT`, **sem crash em SP/MG** — dentro do baseline do Streamlit. **Faltam (humano/medido):** paridade byte-a-byte formal vs Streamlit e o aceite de UX (analista jr. → recomendação < 60 s). |
| **Depende de** | **BLK-WEB-08** + **BLK-WEB-09**. |
| **Autonomia** | **manual (NÃO loop-safe)** — os critérios de aceite incluem UX ("<60s sem treino") e paridade visual que exigem olho humano; a parte de teste de contrato é automatizável, o veredito de aceite é humano. |

**Contexto.** Critérios da **§1/§15 do `PLANO_APP_WEB.md`**: paridade numérica byte-a-byte, performance por UF ≤
baseline (`data/reports/perf_baseline_dashboard.md`), zero recálculo de score, analista jr. → recomendação de UF < 60s.

**Objetivo.** **Testes de contrato** comparando o JSON de cada endpoint com a saída do Streamlit (mesmas funções puras,
mesmos Parquets) — byte-a-byte nos números; **teste de guardrail** (nenhum endpoint escreve em disco; `mtime` dos 4
artefatos oficiais inalterado; score/pesos intactos); medição de **carga por UF** vs baseline (incl. UFs grandes sem
crash); checklist da §15; validação humana de UX (<60s jr., "uma decisão por tela", read-only visível).

**Guardrail.** §5 READ-ONLY M1 (o próprio teste de guardrail prova isso); centralizar `RESIDUAL_SCORE_BANDS` no back
(evita divergência de cor/faixa).

---

## Epic BLK-WEB — Addendum (2026-07-20): piloto standalone construído + novas frentes (Felipe)

> **Reconciliação com a realidade (2026-07-20).** O piloto foi **construído nesta data** como app
> **STANDALONE**, divergindo da arquitetura planejada em WEB-01..11:
> - **Backend próprio** `web/server/app.py` (FastAPI, porta 8899) — **NÃO** estende `src/motor_expansao/api/`
>   de produção; embrulha as mesmas funções puras do motor. Basemap = **CARTO Dark Matter online** (não o
>   `tileserver-gl` self-hosted). Front em `web/` (Vite + React + TS + deck.gl), sobe com `iniciar-piloto-web.cmd`.
>   Branch `piloto-web`, commits até `12bd6e4`.
> - **Entregue e validado em sessão:** tela **Mapa** (funil 4 camadas, tooltip com paridade de campos —
>   Faixa M1/scores/Habitantes/Renda per capita/**Renda média domiciliar**/Residual, busca por coordenada,
>   holofote do passo por opacidade, filtro UF/Município alfabético + busca, top-10 recomendações viáveis,
>   Relatório Municipal PDF) e tela **Viabilidade** (p50 por m², CAPEX/carência, payback real, DRE/rampa/FCF,
>   Relatório Pontual PDF).
> - **Efeito nos blocos existentes:** WEB-01..05 (estender a API de produção) → **SUPERSEDED** pela abordagem
>   standalone (a decisão de unificar com a API prod fica no WEB-17). WEB-06..09 (frontend das 2 telas) →
>   substancialmente **ENTREGUES** na variante standalone (falta a paridade completa — WEB-12). WEB-10/11 →
>   seguem pendentes (redefinidos/absorvidos por WEB-16/17).
> - **Correção de dado pendente:** a renda média domiciliar do tooltip cai no **fallback nacional** localmente —
>   faltam 3 parquets municipais no `data/staging` do backend (memória `project-piloto-renda-domiciliar-fallback`);
>   endereçado no WEB-17.
>
> **Novas frentes pedidas por Felipe (2026-07-20) — escopo desta rodada:** paridade total do Mapa (WEB-12) com a
> única troca do pin de concorrente (WEB-13), geocoding (WEB-14), Visão Executiva por estado (WEB-15), suíte de
> testes E2E + CI/CD (WEB-16) e deploy lado a lado (WEB-17). **Expansão de Domínio e Carteira e Plano seguem FORA.**
> **Futuro (parking-lot):** nova aba **Carteira Imobiliária** — onde ficarão os **coletores de imóveis ativos**
> (conceito novo, NÃO a "Carteira e Plano" do Streamlit); planejar quando priorizado.
> **READ-ONLY sobre o M1 em todos.** **Nenhum bloco entra `loop-safe`** — frontend/rede/deploy exigem olho humano
> (lição BLK-UI-10/BLK-VIAB-09; §6.1).
>
> **Progresso (2026-07-20):** **WEB-13 ✅** (`ee77fb7`) e **WEB-12 ✅** (`2cd7964` + `57f0c67`) concluídos e validados
> no browser. **WEB-12 teve o ESCOPO REDUZIDO por Felipe (2026-07-20)** — "manter só o essencial": (a) **porta de
> entrada por UF** (seletor de estado + storytelling/CTA na landing; funil narrativo por UF; painel recomenda
> **municípios**; clique = drill-down automático; "Todos os municípios" volta à UF), (b) **multi-hex** (cenário que
> soma residual/pop/score no cliente), (c) **1 filtro global** ("MELHORES" por faixa M1). **FORA do WEB-12 agora**
> (não pedidos): modos de score selecionáveis, overlay de vazios competitivos, Análise Pontual de Entorno dedicada,
> régua de 8 filtros. **WEB-14 ✅ + WEB-15 ✅** (`b1996e7`): geocoding de endereço na busca do Mapa
> (Nominatim/DEC-010) e a **Visão Executiva por estado** (aba habilitada; `/api/executiva/{uf}` agrega
> `growth_api_historico.parquet` — faturamento/ativos/pagantes/churn/NPS + split pagantes×agregadores; bubble map
> deck.gl das unidades). Também trocado o **ícone do app pela logo Ultra** (Dock + favicon). Felipe vai avaliar a
> aba nova e dar feedback. Faltam **WEB-16** (testes+CI) e **WEB-17** (deploy). Nota de dado: logos de
> concorrentes ausentes no checkout → fallback quadrado cor+sigla.

---

## Epic BLK-WEB — Fecho do escopo do corte (2026-07-23, DEC-019)

> **Reconciliação com prod + decisões de escopo (Felipe, 2026-07-23).** Os Status dos blocos WEB-01..17 acima foram
> atualizados para o estado REAL, verificado **na VPS** (não no código local): a imagem em produção (`motor_expansao_web`)
> foi buildada do commit **`9b60761` = tip de `origin/piloto-web`** — **prod == este código**. O `/openapi.json` expõe
> **11 endpoints vivos** (mapa por UF, executiva, faixa-alunos, geocode, municípios, relatórios municipal/pontual,
> viabilidade + catálogos); **não existem** `/api/dominio`, `/api/carteira` nem `/api/plano`.
>
> **Decisões formalizadas na DEC-019:** (1) **Expansão de Domínio não vira aba** — a Fase 4 do Mapa já cobre;
> (2) **Carteira vira "Oportunidades Imobiliárias"** (placeholder; feature plena = epic futura de imóveis + coletores,
> com DEC + spec próprias) e as tabelas Carteira acionável + Plano curto prazo são **dropadas** — a parte de
> domínio/carteira/plano/vazios do **BLK-WEB-02 fica CANCELADA**; (3) **substituir 100% o Streamlit = paridade só de
> Mapa + Visão Executiva + Viabilidade**, gate = **BLK-WEB-11** (o único bloco que ainda falta).
>
> **Caveat aberto (pendência de DADO, não de código):** a Visão Executiva depende de `growth_api_historico.parquet`,
> **ausente na VPS** — `GET /api/executiva/SP` retorna **HTTP 404**; gerar/subir esse parquet (via `scp` para
> `/opt/motor-expansao/data/staging/`, como os uplifts em §5) é pré-requisito da paridade da tela executiva.

---

### BLK-WEB-12 — Paridade total do Mapa Territorial (standalone) vs Streamlit

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (superfície principal do piloto; **READ-ONLY sobre o M1**). |
| **Prioridade** | Alta (fecha a tela mais usada). |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA — UX/visual]` → Builder → QA. |
| **Status** | Concluído (em prod, rev 9b60761; commits 2cd7964+57f0c67): porta por UF + funil narrativo, cenário multi-hex (soma no cliente + copiar IDs) e filtro global "MELHORES" por faixa M1. Escopo reduzido por Felipe 2026-07-20 (modos de score, overlay de vazios e régua de 8 filtros ficaram FORA — cancelados, não pendentes). |
| **Depende de** | piloto standalone atual (Mapa entregue); herda a spec de paridade de **BLK-WEB-08** e os critérios de **BLK-WEB-11**. |
| **Autonomia** | **manual (NÃO loop-safe)** — UI/visual + WebGL; exige olho humano. |

**Contexto.** O Mapa standalone já entregou o funil narrativo em 4 camadas, o tooltip com paridade de campos, a
busca por coordenada, o Relatório Municipal e o top-10. Faltam features do `render_mapa_territorial`
(`pages.py:4775`) do Streamlit para a **paridade TOTAL** que o Felipe pediz — "única troca relevante" é o pin de
concorrente (WEB-13); todo o resto replica 1:1.

**Objetivo (checklist de gaps a fechar).** (a) **modos de score selecionáveis** (M1/censitário/híbrido/residual)
além do funil guiado, com legenda de 10 faixas por modo; (b) **pins de concorrentes** (via WEB-13) + **pins Ultra**
com tooltip/logo; (c) **Análise Pontual de Entorno** raio 1,6 km — single + **Cenário Multi-Hex** (add/remove, colar
lista, copiar `hex_id`, 25 KPIs); (d) **overlay de vazios competitivos** (paridade BLK-TP-03-FU1); (e) **filtros
globais** (8 filtros server-side, régua "X hex | Y UF | Z cidades"); (f) **caps** `MAP_POINT_LIMIT`/`_LARGE` +
**visão de UF inteira** (hoje é município); (g) **busca por endereço** (via WEB-14).

**Guardrail.** §5 READ-ONLY M1; só score→cor no cliente (nunca cálculo de score); manter os caps (anti-OOM/WebGL);
centroide de hex como aproximação (documentar na UI).

**Aceite.** Matriz feature-a-feature M1..M16 da aba Mapa do Streamlit marcada; números batem com o dashboard;
nenhum recálculo de score/artefato; UX preservada.

---

### BLK-WEB-13 — Pin de concorrente como bandeira (logo quadrado enxuto)

| Campo | Valor |
|---|---|
| **Criticidade** | **Baixa** (camada visual de apoio; **READ-ONLY sobre o M1**). |
| **Prioridade** | Média (a "única troca relevante" da paridade do mapa). |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA — visual]` → Builder → QA. |
| **Status** | Concluído (em prod, rev 9b60761): concorrentes como bandeira quadrada — backend `_montar_pins` (atlas por rede, fallback cor+sigla, cap COMPETITOR_PIN_LIMIT=6000, tooltip); front `IconLayer` conc-pins. Ultra em marcador próprio; escopo largo (UF) mostra só Ultra, concorrentes no drill-down do município (sem cluster explícito). |
| **Depende de** | **BLK-WEB-12** (superfície do mapa) — na prática vai junto. |
| **Autonomia** | **manual (NÃO loop-safe)** — decisão visual; exige olho humano. |

**Contexto.** Hoje o piloto mostra a Ultra como ponto vermelho e **não desenha os concorrentes**; o Streamlit usa
pins com logo por rede + cluster. Felipe (2026-07-20): o concorrente vira **apenas a bandeira com a logo em formato
QUADRADO**, enxuta, **sem preencher muito espaço** na tela.

**Objetivo.** `IconLayer` de concorrentes com **sprite quadrado da logo da rede** (atlas por `rede`, fallback de
sigla — reusar `competitors._render_pin_tile`/`build_icon_atlas`), tamanho pequeno e constante em pixels, **cluster**
em escopo largo (cap `COMPETITOR_PIN_LIMIT` = 6000, amostragem determinística), tooltip curto (rede/unidade). Pino da
Ultra segue seu próprio marcador.

**Guardrail.** §5 READ-ONLY M1; pins são camada visual (não alteram score/ranking/carteira); respeitar cap/amostragem.

**Aceite.** Concorrentes aparecem como bandeira quadrada enxuta; não poluem em zoom baixo (cluster); contagem em
paridade com o dashboard.

---

### BLK-WEB-14 — Geocoding: busca por endereço no piloto

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (rede ao vivo — precedente **DEC-010**; **READ-ONLY sobre o M1**). |
| **Prioridade** | Média. |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA — rede/anti-PII]` → Builder → QA. |
| **Status** | Concluído (em prod, rev 9b60761): GET /api/geocode (Nominatim, cache `data/cache/geocode/`, timeout 10s, fallback gracioso, anti-PII, restrito ao Brasil — DEC-010). A busca aceita endereço além de coordenada/link, com pin e mensagem de fallback offline. |
| **Depende de** | — (a busca do piloto já resolve `lat,lng` + link Maps offline). Relacionado a **BLK-PROD-05** (geral) e **BLK-VIAB-08** (imóveis). |
| **Autonomia** | **manual (NÃO loop-safe)** — geocoding é rede ao vivo (DEC-010/Nominatim); o loop não faz rede. NUNCA loop-safe. |

**Contexto.** A busca do piloto (`web/src/lib/coord.ts`) resolve só `lat,lng` e link do Google Maps. Falta a cascata
do Streamlit (`resolve_endereco_http`, `pages.py:807`) para **endereço livre** e **Plus Code** via Nominatim.

**Objetivo.** Endpoint no backend do piloto que resolve endereço/Plus Code → `lat/lng` (Nominatim, **DEC-010**: cache
`data/cache/geocode/`, timeout, **fallback offline gracioso**, anti-PII), e a barra de busca aceitando endereço além de
coordenada/link, com card de resultado + link-fallback quando a rede faltar.

**Guardrail.** DEC-010 (cache/timeout/fallback/anti-PII); §5 READ-ONLY M1; **nunca** colocar dado pessoal em query string.

**Aceite.** Digitar um endereço leva ao ponto com pin e habilita o estudo pontual; offline degrada com link-fallback;
nenhuma PII persistida.

---

### BLK-WEB-15 — Tela Visão Executiva por estado (métricas reais da Growth API)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (nova tela; **READ-ONLY sobre o M1**; consome a camada PARALELA Growth, **sem PII**). |
| **Prioridade** | Alta (frente pedida por Felipe). |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA — UX/visual + conferência dos números]` → Builder → QA. |
| **Status** | Código concluído; **sem paridade em prod (dado ausente)** (rev 9b60761): GET /api/executiva/{uf} agrega Growth por UF (faturamento, ativos/pagantes, churn 30d, split pagantes×agregadores, ticket, NPS, M-1) + ExecutiveScreen (pins Ultra, KPIs, seletor mês/estado). **Bloqueio operacional:** `growth_api_historico.parquet` ausente na VPS → HTTP 404 (não é bug de código; `scripts/ingerir_growth_api.py` está em prod mas não rodou). |
| **Depende de** | `growth_api_historico.parquet` no `data/staging` do backend (ingestão semanal já roda na VPS — **DEC-013**). |
| **Autonomia** | **manual (NÃO loop-safe)** — UI/visual + validação de números reais de negócio. |

**Contexto.** O dock tem "Visão executiva" desabilitada. Felipe (2026-07-20): agrupar **por ESTADO** e, dentro do
estado, mostrar **pins das Ultras + números REAIS**. Dado **confirmado** em `growth_api_historico.parquet` (93
unidades, 2023–2025, PII-free): `uf`, `faturamento` / `faturamento_sem_agregador`, `pagantes` / `ativos_total`,
`churn`, `alunos_gympass` + `alunos_totalpass` (agregadores), `ticket_medio_pagantes`, `NPS`, `inauguracao`.

**Objetivo.** Endpoint(s) que **agregam por UF** (competência mais recente ou janela): faturamento no estado, alunos
ativos/pagantes reais, churn, **proporção pagantes × agregadores** (Gympass + TotalPass), ticket médio, NPS; +
**join** das unidades às coordenadas dos pins Ultra por `normalizar_unidade` (trata o sufixo " - XX"). Front: mapa por
estado com **pins Ultra** + painel de KPIs do estado + gráficos (faturamento/churn por unidade) + seletor de estado.

**Guardrail.** §5 READ-ONLY M1; a camada Growth é **paralela e sem PII** (`assert_sem_pii`, `config.PII_COLUNAS_PROIBIDAS`);
a Visão Executiva **não** recalcula score/carteira/plano — só lê o histórico + pins Ultra.

**Aceite.** Por estado, os KPIs batem com o `growth_api_historico.parquet`; pins Ultra corretos; split pagantes ×
agregadores coerente; nenhum dado pessoal exibido ou persistido.

---

### BLK-WEB-16 — Suíte de testes E2E + CI/CD da nova versão

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (fundação de qualidade da nova versão; **READ-ONLY sobre o M1**). |
| **Prioridade** | Alta (bloqueia a substituição segura do Streamlit). |
| **Esteira** | Block Orchestrator → Planner → Builder → QA. |
| **Status** | Concluído (parcial, em prod rev 9b60761): CI job `web` (Node 20 + **Vitest 59 testes** + tsc/vite build) **e o pytest do backend** `tests/unit/test_piloto_web_endpoints.py` (24 testes: contrato de todos os endpoints + JSON-safe + **guardrail READ-ONLY AST e runtime**). Falta: **E2E Playwright**, eslint e mypy. |
| **Depende de** | telas do piloto razoavelmente estáveis (**BLK-WEB-12** + **BLK-WEB-15**). Absorve/estende **BLK-WEB-11**. |
| **Autonomia** | **manual por padrão** — introduz toolchain **Node no CI** (fora do container Python do loop); parte é automatizável, mas o pipeline novo pede gate humano. |

**Contexto.** O piloto (`web/server/app.py` + `web/`) hoje tem **zero testes**; o Streamlit tem 660+. Substituir com
segurança exige cobertura ponta a ponta e CI próprio.

**Objetivo (matriz de testes e validações).**
- **Backend (pytest):** contrato de cada endpoint (`/ufs`, `/municipios`, `/municipio`, `/faixa-alunos`, `/viabilidade`,
  relatórios, `/executiva/*`), JSON-safe (NaN/inf→None), **paridade numérica** vs as funções puras do motor, **teste de
  guardrail READ-ONLY** (`mtime` dos 4 artefatos oficiais + score/pesos intactos; nenhum write em disco), fallback do
  basemap/geocoding.
- **Frontend (Vitest):** unit dos libs (`colors.ts`, `coord.ts`, `format.ts`, `Select` — filtro/ordem) e componentes-chave.
- **E2E (Playwright):** fluxos reais — carregar UF/município, funil 1→4, tooltip, busca coordenada→estudo pontual,
  Relatório Municipal, Viabilidade (calcular + payback + FCF), Visão Executiva por estado.
- **CI/CD:** pipeline com **lint** (ruff + eslint), **typecheck** (mypy + tsc), **build Vite**, pytest + vitest +
  playwright headless; gate por checks (DEC-016); dispara em push da branch.

**Guardrail.** §5 READ-ONLY M1 (o teste de guardrail prova); **CI não deploya** (§6); sem segredos reais nos testes.

**Aceite.** Pipeline verde ponta a ponta; o teste de guardrail **falha** se algum endpoint escrever artefato oficial;
cobertura mínima acordada; roda no CI.

---

### BLK-WEB-17 — Deploy do piloto EM PARALELO ao Streamlit (standalone) + decisão de qual manter

| Campo | Valor |
|---|---|
| **Criticidade** | **Crítica** (toca `deploy/`/`Dockerfile.*`/`docker-compose*`/Caddy/**CI** + VPS; exige **`critica-aprovada`** do Felipe — DEC-016). |
| **Prioridade** | Média (após telas + testes). |
| **Esteira** | Block Orchestrator → Planner → `[GATE HUMANO — deploy/VPS/auth/LGPD/arquitetura]` → Builder → QA. |
| **Status** | Concluído (parcial, em prod rev 9b60761): piloto ao lado do Streamlit — `Dockerfile.web`, serviço `web`/`motor_expansao_web` no compose (`:ro`, sob Caddy+Authelia), job `publish-web` e os 3 parquets de renda domiciliar presentes na VPS. Falta: registrar a decisão de qual manter (agora coberta pela **DEC-019** + gate **BLK-WEB-11**). |
| **Depende de** | **BLK-WEB-12** + **BLK-WEB-15** + **BLK-WEB-16**. **Supersede/refina BLK-WEB-10** para a arquitetura standalone. |
| **Autonomia** | **manual (NÃO loop-safe)** — `loop_guard` aborta em `deploy/`/`Dockerfile.*`/compose/CI; deploy sempre manual, por digest (§6). NUNCA loop-safe. |

**Contexto.** Prod = `docker-compose.prod.yml` (streamlit, api, telegram-bot, caddy, authelia); ingress único = Caddy.
O piloto standalone tem **backend próprio** (`web/server`, uvicorn :8899) + front Vite. Objetivo: subir **ao lado** do
Streamlit para **teste real** e decidir qual manter — o **corte** do Streamlit é decisão futura + DEC.

**Objetivo.** Adição **aditiva**: `Dockerfile.web` (build Vite → nginx estático) + serviço do backend do piloto
(uvicorn) no compose; **decisão de arquitetura no gate** — manter o backend standalone `web/server` **ou** unificar com
a API de produção (reconciliar WEB-01..05); **rota Caddy** em subdomínio dedicado sob **Authelia**; `API_CORS_ORIGINS`
restrito; **shipping dos 3 parquets municipais de renda domiciliar** ao `data/staging` do serviço (corrige o fallback
nacional — memória `project-piloto-renda-domiciliar-fallback`); job **`publish-web`** por digest (Node no CI). Roda
**sem corte**; coletar uso real; **gate de decisão** Streamlit vs piloto (registrar DEC).

**Guardrail.** §6 (nenhum comando na VPS sem confirmação, comando a comando; deploy por digest, manual; **auto-merge
não deploya**); §5 READ-ONLY M1; DEC-016 (`critica-aprovada`). **Não** aposenta o Streamlit (decisão futura + DEC).

**Aceite.** Piloto acessível em prod atrás de login, ao lado do Streamlit, com os 3 parquets presentes (renda
domiciliar municipal correta); uso real coletado; decisão de qual manter registrada em DEC.

---

### BLK-BASEMAP-03 — Quita a dívida do overlay de rótulos + nomes de rua no Relatório Municipal

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (RENDER; **READ-ONLY sobre o M1**) |
| **Esteira** | Builder → QA |
| **Depende de** | BLK-RELPON-07 (#154), BLK-BASEMAP-01 (#155), BLK-BASEMAP-02 (#156) — todos em `main` |
| **Status** | Em revisão (PR aberto) |
| **Autonomia** | **manual (NÃO loop-safe)** — toca DECs e o caminho de geração dos dois relatórios |

**Contexto.** O #154 entrou por bypass com dois achados aceitos (ALTA: `_fetch_labels` sem o cache
que a mitigação (a) da DEC-004 exige; MÉDIA: a matemática de zoom/tile/extent sem teste direto).
E o #156 trouxe uma regressão não prevista: como o estilo `ultra-maptiler` não tem
`transportation_name` e o Municipal não tinha overlay de rótulos, o mapa municipal passou a sair
com as ruas desenhadas e **sem nome** — o Voyager trazia os nomes embutidos no raster.

**Entregue.** (1) cache em disco por tile em `data/cache/label_tiles/`, escrita atômica;
(2) `_labels_grid`/`_labels_extent` extraídos e testáveis sem rede, com 12 casos novos;
(3) `_fetch_labels` devolve `None` quando **nenhum** tile entra (antes devolvia canvas
transparente, contrariando o próprio docstring); (4) timeout por tile 20 s → 8 s;
(5) overlay de rótulos também no Relatório Municipal, com o crédito do CARTO de volta ao rodapé.

**Guardrail.** §5 READ-ONLY M1: nenhuma mudança em score/pesos/carteira/plano/artefatos.
Emendas em DEC-004 e DEC-011.

---

### BLK-BASEMAP-04 — Custo do mosaico de rótulos: `@2x` desperdiçado e orçamento de tempo

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (custo/latência de RENDER; **READ-ONLY sobre o M1**) |
| **Esteira** | Block Orchestrator → Planner → `[GATE VISUAL — Vinicius]` → Builder → QA |
| **Depende de** | BLK-BASEMAP-03 |
| **Status** | Pendente |
| **Autonomia** | **manual (NÃO loop-safe)** — muda resolução de render, exige gate visual |

**Contexto (medido no frame canônico do Pontual: raio 1,5 km, canvas 1000x760, lat −23,55).**
O mosaico de rótulos busca **624 tiles** por relatório contra 169 do basemap, e aloca um canvas de
`13312x12288` RGBA ≈ **654 MB por chamada**. O `@2x` é **100% desperdiçado**: o mosaico sai a
3,349 px/m contra 0,1548 px/m do frame — downsample de **21,6x** no render. O cache do
BLK-BASEMAP-03 corta a repetição, **não o pico**: no cache frio os 624 tiles e os 654 MB continuam.

**Objetivo.** (a) avaliar dropar o `@2x` e/ou baixar `_LABELS_ZOOM_BUMP` de 1 para 0 (corta os
tiles ~4x) — **precisa de gate visual**, porque a nitidez dos nomes foi aprovada por Vinicius no
gate do BLK-RELPON-11; (b) orçamento de tempo (wall-clock) para o mosaico inteiro, em vez de só
timeout por tile: hoje o pior caso contra um CDN em blackhole ainda é ~10 min segurando o PDF;
(c) avaliar servir os rótulos do **próprio tileserver** (camada `transportation_name` no estilo
`ultra-maptiler`), o que elimina o CARTO e deixa o rodapé honestamente só `(c) OpenStreetMap`.

**Guardrail.** §5 READ-ONLY M1. Qualquer mudança de resolução passa por gate visual antes do merge.

---

### BLK-BASEMAP-05 — Fontes do estilo (100% dos tiles PNG davam 500), pin do tileserver por digest e o piloto no healthcheck

| Campo | Valor |
|---|---|
| **Criticidade** | **Crítica** (toca deploy/VPS e o monitoramento de produção; corrige degradação silenciosa já no ar) |
| **Esteira** | Block Orchestrator → Builder → QA |
| **Depende de** | BLK-BASEMAP-01 (#155), BLK-BASEMAP-02 (#156), BLK-BASEMAP-03 (#157) — todos em `main` |
| **Status** | **Em revisão** no PR #159 |
| **Autonomia** | **manual (NÃO loop-safe)** — mexe em deploy/VPS e no healthcheck de produção |

> Criticidade **Crítica** porque o bloco toca `openmaptiles-infra/docker-compose.yml`,
> `scripts/healthcheck_vps.sh` e a configuração do tileserver que serve produção — caminhos de
> deploy/VPS pelo `loop_guard`. Nada de M1: não toca score, pesos, pipelines nem artefatos
> oficiais (READ-ONLY, §5).

**Problema (medido na subida real de 2026-07-28).** O tileserver subiu servindo `brazil.json` com
HTTP 200 e **100% dos tiles PNG com HTTP 500**. O `ultra-maptiler/style.json` pedia
`Open Sans Semibold`/`Open Sans Italic`, fontes que não existem nem na stack (que não versiona
nenhum `.pbf`) nem na imagem (que só traz `Noto Sans Regular`), e o `data/config.json` não
declarava `paths.fonts` — então o tileserver procurava em `/data/<fontstack>/<range>.pbf`, não
achava e o rasterizador falhava o tile INTEIRO (`Font load error`).

**Por que é perigoso e não só chato:** o `_fetch_basemap` do motor **engole a falha em silêncio**
e o PDF sai sem fundo de ruas — e, como o overlay de rótulos é guardado por `basemap_tiles is not
None`, sai **sem os nomes de rua também**. O deploy passa em todos os checks e a degradação só
aparece quando alguém abre um relatório.

**Escopo (3 partes):**

1. **Fontes** — `data/config.json` ganha `paths.fonts` apontando para dentro da imagem
   (`/usr/src/app/node_modules/tileserver-gl-styles/fonts`) e as duas camadas de símbolo do
   estilo (`water-name`, `place-labels`) passam a usar `Noto Sans Regular`.
2. **Pin por digest** — `maptiler/tileserver-gl:latest` → `@sha256:3a9ccdb2…`. O caminho das
   fontes é INTERNO à imagem: um `:latest` que mude de layout quebra a rasterização sem aviso.
3. **Monitoramento** — `scripts/healthcheck_vps.sh` passa de 5 para **7** containers: entram o
   `motor_expansao_tileserver` (BLK-BASEMAP-01) e o `motor_expansao_web`, o piloto, que **estava
   rodando em produção sem nenhuma vigilância** — nem este script nem a versão do BLK-BASEMAP-01
   o listavam, porque a `main` não descrevia o piloto (ele subiu da branch `piloto-web` com o
   compose do servidor editado à mão).

**Critérios de aceite:**
- `…/tiles/styles/ultra-maptiler/{z}/{x}/{y}@2x.png` devolve 200 (logado), não 500.
- Um PDF gerado com `API_BASEMAP_TILES_URL` apontando para o tileserver sai **com** nomes de rua.
- `healthcheck_vps.sh` acusa 7 containers e alerta se o `motor_expansao_web` cair.

**Guardrail.** §5 READ-ONLY M1. Nenhuma mudança em código de render, score ou pipeline.

---

### BLK-BASEMAP-06 — Nomes de rua/avenida legíveis por cima do choropleth, servidos pelo tileserver próprio (CARTO sai)

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (muda a REPRESENTAÇÃO dos mapas de calor e a atribuição de licença; READ-ONLY sobre o M1) |
| **Esteira** | Block Orchestrator → Builder → `[GATE VISUAL — Vinicius]` → QA |
| **Depende de** | BLK-RELPON-07 (#154), BLK-BASEMAP-02 (#156), BLK-BASEMAP-03 (#157), BLK-BASEMAP-05 (#159) |
| **Status** | **Em implementação** |
| **Autonomia** | **manual (NÃO loop-safe)** — muda render aprovado em gate visual e toca a stack do tileserver |

**Problema (medido em produção, 2026-07-29).** Os mapas de calor do Relatório Pontual saíam
**sem nome de rua nenhum**, e o rodapé creditava `(c) CARTO`. Duas causas independentes:

1. **Os rótulos eram sub-pixel.** `_labels_grid` somava `_BASEMAP_ZOOM_BUMP + _LABELS_ZOOM_BUMP`
   fixos e **ignorava o bump que o chamador usou no fundo**. O piloto busca o fundo com
   `zoom_bump=0`, então os rótulos saíam DOIS níveis acima. Medição no ponto do relatório:
   mosaico a **3,349 px/m** contra **0,1636 px/m** do frame → redução de **20,5x**; um texto de
   ~11 px chegava ao PNG final com **0,54 px**. O `_fetch_labels` devolvia um mosaico VÁLIDO —
   só que ilegível —, então nada falhava e ninguém via erro. É o mesmo desperdício que o
   BLK-BASEMAP-04 registrou como problema de CUSTO (`@2x` + 624 tiles); ninguém tinha ligado as
   duas coisas.
2. **O `ultra-maptiler` não tem `transportation_name`.** O basemap próprio desenha as vias mas
   não os nomes delas — o que o BLK-BASEMAP-03 já havia constatado no Relatório Municipal e
   contornado trazendo o overlay do CARTO de volta.

**Escopo (3 partes):**

1. **Estilo `ultra-labels` no tileserver** (`openmaptiles-infra/data/styles/ultra-labels/`):
   só símbolos, fundo transparente, com `transportation_name` (vias principais e secundárias),
   `place` (bairro/distrito) e `water_name`. `text-size` deliberadamente maior que o de um
   basemap de tela, porque o PNG ainda é reduzido ao entrar no PDF. O `brazil.mbtiles` já
   continha `transportation_name` — só faltava o estilo consumi-lo.
2. **Rótulos no mesmo zoom do frame.** `_labels_grid` e `_fetch_labels` passam a aceitar
   `zoom_bump` e o chamador repassa o mesmo do fundo; `_LABELS_ZOOM_BUMP` vai de `1` para `0`.
   O tamanho do texto passa a ser governado pelo `text-size` do estilo — onde dá para controlar.
3. **CARTO sai do caminho.** `_LABELS_TILE_URL` (hardcode do Voyager Only-Labels) vira
   `API_BASEMAP_LABELS_URL`, **sem default**: sem a env var não há overlay. A atribuição passa a
   ser resolvida em runtime — `(c) OpenStreetMap - OpenMapTiles` no self-host,
   `(c) OpenStreetMap, (c) CARTO` no fallback Voyager — e o Municipal **delega** a mesma função,
   para os dois relatórios não divergirem de rodapé (foi o que aconteceu entre o -02 e o -03).

**Critérios de aceite:**
- Nome de rua/avenida legível por cima do choropleth nos 4 mapas de calor. `[GATE VISUAL]`
- Rodapé sem `CARTO` quando `API_BASEMAP_TILES_URL` está definida.
- Teste numérico travando a densidade do mosaico em ≤ 3x a do frame (piso do `@2x`).
- Nenhum tile de terceiro requisitado em produção.

**Fora de escopo (segue aberto):** os painéis Socioeconomia e Residual Fitness (5 km) continuam
sem overlay — eles passam por `_render_camada_residual_hex`, que nunca recebeu `labels`. É o
limite conhecido registrado no BLK-RELPON-07 e não muda aqui.

**Guardrail.** §5 READ-ONLY M1: só RENDER. Não toca score, pesos, interseção censitária, raio de
análise, carteira, plano nem artefatos oficiais.

---
