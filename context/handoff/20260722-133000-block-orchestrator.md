# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner (gate de "qual caminho" já pago por Vinicius em 2026-07-22 — caminho A1, Voyager z19. Sem
nova pausa de aprovação de plano antes do Planner. O gate que resta é VISUAL, depois do QA.)

## Bloco refinado
BLK-RELPON-11 — Imagem do entorno do ponto: página nova "Imagem do Entorno", mapa de quadra
CartoDB Voyager z19 (~300 m de largura, zoom bump = 0), inserida no Relatório Pontual Censitário
(dashboard + bot Telegram, nas duas variantes `censitario` e `classico`).

## Objetivo
Dar ao operador noção de morfologia urbana (quadra, ruas, números de porta) no entorno imediato do
ponto, numa página nova entre a Capa e o slide "Socioeconomia e Residual Fitness" — sem provedor
novo, sem DEC, sem dependência de rede no dashboard interativo.

## Escopo permitido
- Nova camada de mapa "entorno" em `censo_map.py`, gerada por uma função dedicada (padrão
  `_render_camada_residual_hex`), reusando `_render_camada` em modo `pins_only=True`
  (sem choropleth, sem faixas, sem `valor_ponto`) e um frame métrico próprio (padrão
  `_frame_box_metric`) com raio de EXIBIÇÃO pequeno — ver seção "Parâmetro de render" abaixo.
- Override LOCAL de `zoom_bump` em `_fetch_basemap` (parâmetro novo opcional, default `None` ->
  cai na constante do módulo `_BASEMAP_ZOOM_BUMP` inalterada) — a nova camada passa `zoom_bump=0`.
  Os 2 call-sites existentes de `_fetch_basemap` (linhas ~989 e ~1196) continuam sem passar o
  parâmetro -> comportamento idêntico, zero regressão.
- Nova chave `"entorno"` em `CAMADAS_CENSITARIAS` (censo_map.py) — INCONDICIONAL (ao contrário de
  `"residual"`): não depende de `hexes_df`, só de `lat`/`lng` (sempre disponíveis). Vai no set
  `_CAMADAS_SEM_HEXES` dos testes, não no `| {"residual"}`.
- Nova entrada em `MAP_LAYER_TITLES` (censo_report.py) — **obrigatória**: sem ela
  `_normalize_mapas_by_key` descarta o PNG em silêncio (mesma armadilha documentada no teste
  `test_map_layer_titles_inclui_as_chaves_novas_senao_os_pngs_sumiriam`, que precisa de uma
  assert nova `"entorno" in chaves`). `densidade` continua no índice 0 (contrato existente).
- `PDF_SECTION_HEADERS` (censo_report.py): 7 -> 8 strings, nova entrada na posição 2 (logo após
  "Relatório Pontual Censitário", antes de "Socioeconomia e Residual Fitness"). ASCII/latin-1-safe
  (sem travessão/bullet/reticências/aspas curvas).
- Duas novas funções de página em `censo_report.py`: `_entorno_page` (template recente) e
  `_classico_entorno_page` (template clássico), espelhando exatamente o par
  `_socioeconomia_residual_page`/`_classico_socioeconomia_residual_page`, mas com
  `_draw_maps_grid(..., cols=1, rows=1, pack=True)` (1 mapa, não 2) — reusa o fallback textual
  gracioso já existente em `_draw_maps_grid` em vez de escrever posicionamento bespoke.
- Inserir a chamada nas DUAS funções de montagem (`gerar_pdf_relatorio_pontual_censitario` e
  `gerar_pdf_relatorio_pontual_classico`) na posição exata — ver "Ordem final de páginas" abaixo.
- Computar `p_entorno, _s_entorno = _tema_bicolor(-1)` (== turquesa/magenta) nas duas funções de
  montagem, ao lado de `p0..p4` já existentes. **Este ordinal -1 já está contratado e testado
  hoje** (ver "Evidência de código" abaixo) — não é uma escolha nova do Planner, é um contrato que
  o BLK-RELPON-10 já deixou pronto para este bloco.
- Atualizar os 6 arquivos de teste de `/Count`/`PDF_SECTION_HEADERS` herdados do BLK-RELPON-10 (ver
  lista exata abaixo) + o arquivo adicional `test_relatorio_pontual_censitario_mapa.py` (ver nota
  de churn extra abaixo — **não estava nos "6" do current_task.md, é achado novo desta análise**).
- Reusar `_ATRIBUICAO_TILES` já existente em `censo_map.py`/`censo_report.py` (mesma string, mesmo
  provedor Voyager/CARTO já aprovado pela DEC-004/DEC-011) — **nenhuma constante nova**, o rodapé
  de atribuição já sai de graça ao reusar `_render_camada`.
- Título/rótulo da página e do PNG descrevendo morfologia urbana (quadra/ruas/números de porta),
  nunca "imagem de satélite" nem prometendo POI comercial. Acentuação correta (§2) no PDF e nos
  identificadores em ASCII (`"entorno"`, sem acento).
- Housekeeping: `CLAUDE.md` §4 (parágrafo do Relatório Pontual) — trocar "7 páginas" por "8
  páginas" e incluir a nova página na lista da ordem, mesmo padrão que o BLK-RELPON-10 fez para o
  parágrafo do BLK-CENSO-02/RELPON-01.

## Fora de escopo
- **DEC-018 — não abrir.** Nenhum provedor novo (Esri, ortofoto municipal, OpenAerialMap,
  Sentinel/CBERS/INPE, Google). Decisão já paga por Vinicius em 2026-07-22.
- **Caminho A4 (upload de print pelo operador)** e os "3 consertos obrigatórios" do relatório de
  alternativas (§5: letterbox em vez de cover-crop, bug de rerun em `_render_relatorio_pdf_imovel`,
  ligar `st.file_uploader` ao Mapa Territorial) — fora deste bloco. Se valerem a pena por si só,
  registrar como bloco novo no handoff de fechamento, não puxar para dentro deste ciclo.
- **Alterar a constante global `_BASEMAP_ZOOM_BUMP = 1`** — serve os mapas de 1,5 km e 5 km já em
  produção; a solução é o parâmetro `zoom_bump` local, não mudar o default do módulo.
- **`relatorio_municipal.py`** — não faz parte do escopo de código deste bloco (é escopo do
  BLK-RELPON-09, que entra no mesmo PR final por empacotamento, não por este bloco reabrir texto
  nele). Ver nota de guard por path abaixo.
- **Motor censitário** (`analisar_ponto_censitario_setores`, `setor_censitario_intersecao_area_1p5km`,
  `RAIO_CENSITARIO_DEFAULT_KM`) — INTOCADO. Esta é uma camada de RENDER nova, não uma mudança do
  raio/método de análise de 1,5 km.
- **Abrir PR.** Decisão de Vinicius (2026-07-21): RELPON-09/10/11 entram num PR único no fechamento
  do ciclo. Este bloco termina em commit no branch `ciclo/BLK-RELPON-11` (já criado, empilhado
  sobre `ciclo/BLK-RELPON-10` @ `a491069`; branch atual está limpo, sem PR aberto).
- `tasks/backlog.md`/`tasks/completed.md` — housekeeping de fechamento é passo do fechamento em
  lote dos 3 blocos, não deste ciclo isolado (mesmo padrão que o QA do RELPON-10 registrou).
- Pins de concorrentes/Ultra na nova camada: RECOMENDAÇÃO desta análise é **sem pins**
  (`pins=[], ultra_pins=[], mostrar_legenda_pins=False` — mesmo padrão do BLK-RELPON-10-FU1 para a
  camada residual), porque "quem está instalado" já é coberto pela página "Concorrentes" e o
  objetivo declarado é morfologia física, não densidade de concorrência. Não é um contrato travado
  por teste como o ordinal -1 — é uma recomendação; se o Planner decidir diferente, registrar a
  razão no handoff dele, não é preciso voltar ao gate humano por isso.

## Ordem final de páginas (mandatório, sem opcionais) — 7 -> 8

1. Capa
2. **Imagem do Entorno** (NOVA — ordinal -1, turquesa)
3. Socioeconomia e Residual Fitness (ordinal 0, magenta)
4. Mapas de calor (ordinal 1, turquesa)
5. Concorrentes (ordinal 2, magenta)
6. Perfil do Bairro/Distrito (ordinal 3, turquesa)
7. Big Numbers (ordinal 4, magenta)
8. Realização

Com os opcionais (fotos do imóvel, informações do imóvel, viabilidade), a posição da página nova
**não muda**: eles continuam entre Capa e a página nova, exatamente como já entram hoje entre Capa
e "Socioeconomia e Residual Fitness" (usam cores emprestadas `p1`/`p2`, não têm ordinal próprio):

Capa -> [Fotos do Imóvel] -> [Informações do Imóvel] -> **Imagem do Entorno** -> Socioeconomia e
Residual Fitness -> Mapas de calor -> Concorrentes -> Perfil do Bairro/Distrito -> Big Numbers ->
[Viabilidade - Números] -> [Viabilidade - Projeção financeira] -> Realização.

Teto de páginas com TODOS os opcionais: 11 -> **12** (mesmo padrão incremental que o BLK-RELPON-10
já registrou como precedente "10->12").

### Evidência de código (não é inferência — já está escrito e testado)

`censo_report.py:332-337`, docstring de `_tema_bicolor` (escrita pelo próprio BLK-RELPON-10,
antecipando este bloco):
> "BLK-RELPON-10 (DT-4): ... paginas INSERIDAS ANTES da primeira delas tomam ordinais
> DECRESCENTES a partir de 0 ... Uma pagina anterior a essa deve tomar o ordinal -1 pela mesma
> regra de paridade (-1 % 2 == 1 em Python -> turquesa)."

`tests/unit/test_relatorio_pontual_censitario_export.py:759-760`, já commitado e passando hoje:
```python
# Contrato do sucessor (BLK-RELPON-11): pagina inserida ANTES desta toma o ordinal -1.
assert _tema_bicolor(-1) == (ULTRA_TURQUESA, ULTRA_MAGENTA)
```
Isso resolve, com evidência dura (não julgamento do BO), tanto a COR da página nova (turquesa
primária, magenta secundária) quanto a sua ADJACÊNCIA exata: ela é a página imediatamente anterior
ao ordinal 0 (Socioeconomia), não uma posição solta "em algum lugar depois da capa". Como fotos/
info do imóvel não participam da cadeia de ordinais (usam `p1`/`p2` emprestados, sem ordinal
próprio), a leitura mais consistente com o próprio código é: eles continuam onde estão hoje, e a
página nova fecha a cadeia -1,0,1,2,3,4 logo antes de "Socioeconomia e Residual Fitness".

## Parâmetro de render (mapa de quadra)

- Largura-alvo do frame: **~300 m** (janela viável 250-400 m). Constante de RENDER nova em
  `censo_map.py` (fora de `config.py`/§3, mesmo padrão de `RAIO_RESIDUAL_DISPLAY_KM`), sugestão de
  nome `RAIO_ENTORNO_DISPLAY_KM` — valor de partida ~0,14 km (o lado curto do frame sai em
  `raio_km * 1000 * (1 + _MAP_FRAME_MARGIN)` **x2**; com `_MAP_FRAME_MARGIN=0.08` isso dá ~300 m
  de lado curto para `raio_km≈0.14`). **Builder deve confirmar empiricamente** contra tiles reais
  do Voyager (o valor exato de zoom/target_px que fecha a janela 250-400 m foi medido na pesquisa
  de alternativas para z19/z18/z17 por REGIÃO, não para este frame específico).
- `z19` é o teto: `z20` perde rótulos no Voyager. Passar `zoom_bump=0` (não usar o `+1` global).
- Canvas do PNG: reusar `width=1000, height=760` (mesmo default de
  `render_mapas_censitarios_combinados`) por consistência — a nitidez vem do zoom escolhido, não
  do tamanho do canvas.
- Sem choropleth, sem faixas de cor, sem `valor_ponto` (não há métrica contínua nesta camada) —
  `pins_only=True`, `legenda_entries=[]`.
- Fallback offline: **incondicional/gracioso**, igual às 4 camadas de setor já existentes
  (densidade/renda/score/renda_domiciliar) — NUNCA a chave "ausente" do dict como a `residual`
  (que só falta por depender de `hexes_df` opcional). Sem tiles: canvas claro `(245,245,245)`,
  sem exceção, footer troca para "fundo de ruas offline" (mecanismo já existe em `_render_camada`,
  nada novo a escrever). `basemap=False` (default de teste/CI) cai direto nesse caminho.

## Arquivos que devem ser lidos
- `CLAUDE.md` (completo)
- `tasks/current_task.md`
- `tasks/backlog.md` — blocos `BLK-RELPON-11` (~L230-311) e `BLK-RELPON-10` (~L188-227)
- `data/reports/imagem_entorno_alternativas.md` (NÃO refazer esta pesquisa)
- `context/handoff/20260722-095101-qa.md` (handoff de QA do BLK-RELPON-10)
- `src/motor_expansao/dashboard/censo_map.py` (completo, 1393 linhas — em especial
  `_BASEMAP_ZOOM_BUMP`, `_ATRIBUICAO_TILES`, `_fetch_basemap`, `_zoom_for_bounds`, `_render_camada`,
  `_render_camada_residual_hex` como padrão a espelhar, `_frame_box_metric`, `CAMADAS_CENSITARIAS`,
  `render_mapas_censitarios_combinados`)
- `src/motor_expansao/dashboard/censo_report.py` (completo, 2235 linhas — em especial
  `PDF_SECTION_HEADERS`, `MAP_LAYER_TITLES`, `_tema_bicolor`, `_ascii`, `_draw_maps_grid`,
  `_socioeconomia_residual_page`/`_classico_socioeconomia_residual_page` como padrão a espelhar,
  `gerar_pdf_relatorio_pontual_censitario`, `gerar_pdf_relatorio_pontual_classico`)
- `tests/unit/test_relatorio_pontual_censitario_export.py` (linhas 648-869 cobrem exatamente o
  padrão de teste do slide-hero anterior — usar como molde)
- `tests/unit/test_relatorio_pontual_censitario_mapa.py` (linhas 1-36, 277-310, 720-810 — sets
  `_CAMADAS_SEM_HEXES`/`_CAMADAS`, testes de `_fetch_basemap`/offline)
- `tests/unit/test_relatorio_pontual_fotos.py`, `test_relatorio_pontual_info_imovel.py`,
  `test_relatorio_pontual_orquestracao.py`, `test_relatorio_pontual_ui_relviab06.py`,
  `test_relatorio_pontual_viabilidade.py` (asserções de `/Count N`)
- `src/motor_expansao/api/service.py` (linhas ~300-380 — confirma que o bot Telegram chama
  `render_mapas_censitarios_combinados`/`gerar_pdf_relatorio_pontual_classico` sem precisar de
  mudança própria; a camada nova chega "de graça" por ser incondicional)
- `scripts/loop_guard.py` (linhas 64-188 — classificação de path)

## Arquivos que podem ser alterados
- `src/motor_expansao/dashboard/censo_map.py`
- `src/motor_expansao/dashboard/censo_report.py`
- `tests/unit/test_relatorio_pontual_censitario_export.py`
- `tests/unit/test_relatorio_pontual_censitario_mapa.py` (arquivo ADICIONAL — não estava na lista
  herdada de "6 arquivos" do current_task.md; necessário por causa de `CAMADAS_CENSITARIAS`/
  `_CAMADAS_SEM_HEXES`)
- `tests/unit/test_relatorio_pontual_fotos.py`
- `tests/unit/test_relatorio_pontual_info_imovel.py`
- `tests/unit/test_relatorio_pontual_orquestracao.py`
- `tests/unit/test_relatorio_pontual_ui_relviab06.py`
- `tests/unit/test_relatorio_pontual_viabilidade.py`
- `CLAUDE.md` (§4, só o parágrafo do Relatório Pontual Censitário — mesmo escopo de housekeeping
  que o BLK-RELPON-10 aplicou)
- `context/handoff.md` + snapshot novo em `context/handoff/`
- `tasks/current_task.md`

Explicitamente FORA desta lista (não tocar): `config.py`, `src/motor_expansao/pipelines/`,
`data/staging/*`, `data/outputs/*`, artefatos M1, `relatorio_municipal.py`,
`tests/unit/test_relatorio_municipal.py` (constante `PDF_SECTION_HEADERS` própria, import
independente — confirmado por leitura, zero risco de contaminação cruzada), `tasks/backlog.md`,
`tasks/completed.md`, `docs/relatorio_pontual_censitario.md` (já estava stale antes deste bloco;
se o Planner quiser resolver a dívida, é decisão dele registrar no escopo, não obrigação herdada).

## Critérios de aceite
- PDF vai de 7 -> 8 páginas nas DUAS variantes (`censitario`/`classico`), sem opcionais; com
  fotos/info/viabilidade a contagem sobe proporcionalmente (+1 cada, teto 12, viabilidade com
  gráficos soma +2).
  A nova página aparece na ordem exata (ver "Ordem final de páginas").
- `_tema_bicolor(-1) == (ULTRA_TURQUESA, ULTRA_MAGENTA)` (já verdadeiro hoje) é o par de cor usado
  pela página nova nas duas funções de montagem.
- `PDF_SECTION_HEADERS`: 8 strings, nova entrada ASCII/latin-1-safe na posição correta.
- `MAP_LAYER_TITLES` inclui `"entorno"` (senão o PNG some em silêncio — regressão já documentada
  em teste existente para as chaves anteriores).
- `CAMADAS_CENSITARIAS`: 8 chaves; `"entorno"` SEMPRE presente (incondicional), diferente de
  `"residual"` (condicional a `hexes_df`).
- `_fetch_basemap` aceita `zoom_bump` opcional sem quebrar os 2 call-sites existentes
  (`_BASEMAP_ZOOM_BUMP` global permanece `= 1`, inalterado).
- Mapa de entorno usa `zoom_bump=0`, frame no intervalo 250-400 m de lado curto, teto z19.
- Atribuição reusa `_ATRIBUICAO_TILES` existente — nenhuma constante nova.
- `basemap=False` (default de teste) produz PNG válido sem exceção (canvas claro, footer
  "fundo de ruas offline").
- Rótulo/título não promete satélite nem POI comercial; descreve morfologia urbana.
- §5 READ-ONLY M1: `git diff` não toca `config.py`, `pipelines/`, `score_priorizacao`,
  `hex_score_estrutural`, pesos, artefatos oficiais (mtime/tamanho idênticos antes/depois).
  Motor censitário (raio 1,5 km, `setor_censitario_intersecao_area_1p5km`) INTOCADO.
- §2 acentuação: identificadores novos sem acento (`"entorno"`, `RAIO_ENTORNO_DISPLAY_KM` ou nome
  equivalente); texto do PNG 100% ASCII; texto do PDF latin-1-safe (`_ascii`).
- `test_relatorio_municipal.py` continua verde e intocado (módulo isolado).
- Suíte completa roda (serial, `pytest -q`, sem `-n auto` neste Windows/Python 3.14 — ~18-26 min).
  Os 7 arquivos de teste listados (6 herdados + `..._mapa.py`) atualizados e verdes.
- `CLAUDE.md` §4 atualizado (7 -> 8 páginas), como housekeeping obrigatório do bloco (mesmo padrão
  que o BLK-RELPON-10 aplicou).
- Nenhum PR aberto; commit no branch `ciclo/BLK-RELPON-11`.

## Criticidade classificada
**Média.** Já reclassificada por Vinicius em 2026-07-22 (o backlog só condicionava "Alta" ao
caminho de provedor novo; A1/Voyager já é provedor aprovado, sem DEC). Override de tiering de
modelo continua justificado pela complexidade REAL da churn (2 variantes de PDF, `/Count`,
`PDF_SECTION_HEADERS`, `_tema_bicolor`, 7 arquivos de teste — 1 a mais do que o herdado) — manter
Planner=opus, Builder=opus, QA=opus (regra dura), conforme já registrado em `tasks/current_task.md`.

## Esteira recomendada
Block Orchestrator (concluído) -> Planner -> Builder -> QA -> **GATE VISUAL do Vini** (sobre o PDF
gerado, nas duas variantes). Sem pausa de aprovação de plano entre BO e Planner (gate de caminho já
pago). Depois do gate visual: fechamento em lote junto com RELPON-09/10 (PR único, sem PR agora).

## Riscos identificados
- **Fotos/informações do imóvel entre Capa e a página nova**: a posição relativa foi resolvida com
  evidência de código (ordinal -1, ver acima), mas o Planner deve confirmar visualmente no gate que
  a leitura narrativa (Capa -> Entorno -> [fotos do imóvel] -> [dados do imóvel] -> Socioeconomia)
  não soa estranha quando AMBOS os opcionais estão presentes — é um julgamento de UX que só o PDF
  real revela, não um bloqueio estrutural.
- **Zoom/target_px exatos para a janela 250-400 m** não foram medidos para ESTE frame específico
  na pesquisa de alternativas (que testou sondagem HTTP por região, não por tamanho de frame) —
  Builder precisa validar contra tiles reais (cache local) antes de fechar o valor de
  `RAIO_ENTORNO_DISPLAY_KM`.
- **Chapecó/SC teve amostra esparsa** no Voyager fora de capital (relatório de alternativas, §6:
  "4 números de porta, muito bege vazio", amostra pequena) — esperar isso em cidades menores/
  interior; não é defeito do código, é limitação de cobertura do provedor. Levar ao gate visual
  como nota, não travar o bloco por isso.
- **`docker-compose.prod.yml` não monta `data/cache/basemap_tiles/` como volume** (achado
  independente do relatório de alternativas, §5) — o cache de tiles é efêmero por container em
  produção. Não é regressão deste bloco (já é assim para as camadas de 1,5 km/5 km), mas cada
  camada nova aumenta o custo de fetch a frio; registrar como possível bloco de ops futuro, fora
  de escopo aqui.
- **PR final agrega `relatorio_municipal.py`** (escopo do BLK-RELPON-09), que É classificado
  CRÍTICO por path em `scripts/loop_guard.py:87` (DEC-011). Isso não muda a criticidade DESTE
  bloco (Média), mas o PR combinado herdará a exigência de label mais alta dos 3 blocos somados —
  relevante para quem fechar o PR único, não para o Planner/Builder deste bloco.

## Guardrails ativos
- §5 READ-ONLY sobre o M1: nada aqui recalcula `score_priorizacao`, `hex_score_estrutural`, pesos,
  carteira, plano ou artefatos oficiais. Motor censitário (`setor_censitario_intersecao_area_1p5km`,
  `RAIO_CENSITARIO_DEFAULT_KM=1.5`) INTOCADO — a nova camada é raio de EXIBIÇÃO, não de análise.
- §2 acentuação: texto de usuário (dashboard, PDF) com acentuação correta; identificadores
  (`key=`, colunas, enums, slugs, nomes de constante Python) NUNCA acentuados. No PDF (fpdf2 core
  font Helvetica, latin-1 via `_ascii()`) evitar travessão `—`/`–`, bullet `•`, seta `→`,
  reticências `…`, aspas curvas, `©` — viram `"?"` silenciosamente. No PNG da legenda/mapa vale a
  exceção de RENDER (ASCII), como já ocorre em `RESIDUAL_SCORE_BANDS`/`OFERTA_DISPONIVEL_ALUNOS_BANDS`.
- Não criar dependência de API ao vivo no dashboard de produção — `basemap=False` continua sendo o
  default seguro em CI/teste; `import contextily` continua lazy.
- DEC-004/DEC-011: nenhum provedor novo; nenhuma DEC nova (DEC-018 permanece não aberta).
- Toda mudança relevante entra com teste; suíte completa sem quebra antes do QA.
- Merge por criticidade (DEC-016): Média com os 4 checks verdes qualificaria para auto-merge, MAS
  a entrega deste ciclo é commit no branch, sem PR — a decisão de merge/label fica para o
  fechamento em lote dos 3 blocos.
