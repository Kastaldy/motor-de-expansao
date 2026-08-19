# Motor de Expansao Ultra Academia - CLAUDE.md
> Fonte canonica curta do projeto. Ler antes de qualquer tarefa.
> Responsavel: Felipe Silva | Estrategia e Growth | Ultra Academia
> Versao: Maio 2026
> Regra de manutencao: manter curto; historico detalhado fica em `docs/`, `data/reports/` e `PRD.md`.

## 1. Norte
- O repo tem duas trilhas complementares:
  - `M1 oficial territorial`: decide onde expandir no nivel executivo.
  - `mercado por hexagono`: camada paralela para ler demanda, oferta mapeada, residual fitness e restricao da rede Ultra.
- Perguntas centrais: onde expandir, quem ja atua ali, qual mercado residual existe e como ocupar regioes com sequencia controlada.
- Posicionamento da Ultra: marca **low-cost / massa** (NAO e premium). Publico-alvo prioritario: 18-45 anos. Concorrente low-cost direto e comparavel de mesmo segmento: Smart Fit.
- `score_priorizacao` continua sendo o score oficial do M1 (camada executiva), nao o score operacional do dia a dia.
- Nenhuma trilha paralela pode alterar o M1 sem aprovacao explicita.
- Papeis das camadas:
  - M1 e a camada EXECUTIVA: decide municipios e ranking oficial de carteira no nivel executivo (uma camada entre varias, nao a primaria operacional).
  - Censitario (`score_setor_2022_calibrado`) e a camada PRIMARIA no uso operacional do dia a dia; hibrido refina leitura intraurbana.
  - Mercado/residual e Expansao de Dominio apoiam estrategia operacional, nao substituem o M1.

## 2. Regras operacionais
- Ler o repositorio real antes de editar; este arquivo resume contexto, nao substitui o codigo.
- Tratar `config.py`, este arquivo e `PRD.md` como fontes canonicas de parametros e guardrails.
- Staging sempre em Parquet; CSVs locais gerados pelo projeto usam `sep=";"` e `encoding="utf-8-sig"`.
- Excecao de legado: `data/ultra/Ultra.csv` usa `sep=";"`, `encoding="latin-1"` e 1 linha inicial de metadado.
- Bases de validacao de scores (concorrentes) ficam em `data/validacao/` (gitignored, dados reais): `Sky Fit dados.xlsx` e `academias_engenharia_do_corpo.xlsx` (alunos/m² + metragem). Insumo do BLK-SCORE-01; contrato em `data/validacao/README.md`. Read-only sobre o M1.
- Ao tocar em camadas paralelas, preservar 100% das linhas e colunas oficiais do M1.
- Pipelines e artefatos do M1 seguem offline (Parquet local); nao criar dependencia de API ao vivo NELES. O app de producao e o piloto web (`web/` — SPA + FastAPI, DEC-022), que serve esses Parquets read-only.
- Toda mudanca relevante entra com teste; nenhum PR deve subir com CI quebrado.
- Quartis sao apoio de ranking relativo; para sizing e decisao executiva, priorizar regua absoluta, residual, receita esperada e capacidade operacional.
- Pins/logos de concorrentes e Ultra no dashboard sao camada visual de apoio; nao alteram score, ranking, carteira nem artefatos oficiais.
- Variaveis IBGE Censo 2022 Basico: `v0001` = Total de pessoas; `v0002` = Total de Domicilios; `v0007` = Domicilios Particulares Ocupados; `v0005` = media de moradores.
- O guia operacional do ciclo ativo fica em `PRD.md`; contratos tecnicos detalhados ficam em `docs/`.
- **Acentuacao (regra permanente, vale para todo trabalho apos a epic BLK-ACENTO):** TODO texto voltado ao usuario — piloto web (labels, botoes, tooltips, legendas, mensagens do funil), bot Telegram e relatorios gerados (PDF/CSV) — deve ser escrito com **acentuacao correta do portugues**; nao regredir para texto sem acento ao criar/editar strings novas. **NUNCA acentuar IDENTIFICADORES:** chaves de payload/estado, seletores CSS, valores brutos de enum/categoria (ex.: `FAIXA_ORDEM` `"media"`/`"alta"`/`"prioridade_maxima"`, produzidos pelo pipeline core e comparados em `.isin`/dict de cores), nomes de coluna de DataFrame e slugs/nomes de arquivo — para exibir acentuado, usar uma **camada de LABEL de exibicao** (`{valor_bruto: "Texto Acentuado"}`), sem tocar o valor bruto. No PDF (`fpdf2` core font Helvetica, encoding `latin-1` via `_ascii()`), os acentos portugueses renderizam normalmente, mas caracteres **fora de latin-1** (travessao `—`/`–`, bullet `•`, seta `→`, reticencias `…`, aspas curvas, `©`) viram `"?"` silenciosamente — usar pontuacao ASCII (`-`, `"`, `(c)`, `...`). Execucao/detalhe: epic BLK-ACENTO no backlog.
Interpretação operacional da regra de criticidade para score (decidida em 2026-05-30):
- LEITURA/ANÁLISE de score sem escrita em artefato M1 → Alta (revisão humana antes do Builder)
- ALTERAÇÃO de fórmula, pesos, ou qualquer artefato M1 → Crítica (aprovação obrigatória + DEC)

**Regras operacionais rapidas (dia a dia):**
- **Grafo antes de varredura:** para "como X funciona", "o que chama Y", "onde vive Z", consultar o grafo PRIMEIRO — tool MCP `graphify` (`.mcp.json` na raiz) ou `python -m graphify query "<pergunta>"`. Grep/Read amplo so' depois que o grafo nao resolver. Instalacao (`pip install --group graph`), limites e armadilhas: §7 + `docs/grafo_conhecimento.md`.
- **Resposta ao Felipe:** recomendacao/decisao primeiro, em ate 2 linhas; evidencia/detalhe so sob demanda.
- **Nunca declarar incapacidade** (scp, mover arquivo, chamar API) sem UMA tentativa real. **VPS:** `scp` via `~/.ssh/id_ultra_mcp` = SIM; `ssh` remoto interativo = NAO; MCP `ssh-vps-ultra` read/edit = SIM.
- **Deploy:** desde 2026-08-14 o path-filter do `publish-api` cobre `dashboard/` e `dimensionamento/` (a imagem api/bot serve o PDF por eles) — o gotcha antigo ("mudanca so em dashboard/ nao rebuilda api/bot") ACABOU. Republish manual continua disponivel: `gh workflow run ci.yml --ref main -f publish_api=true` (`docs/deploy_api_bot.md`). Deploy sempre manual, por digest (§6).
- **Texto renderizado** (PNG/legenda de mapa/fonte core do fpdf2, fora de latin-1): aplicar a excecao de RENDER (ASCII) por padrao ANTES de acentuar.
- **Background longo** (deploy/suite/workflow): prometer avisar e notificar proativamente ao concluir.

## 3. Nucleo oficial M1

### Parametros canonicos
```python
H3_RESOLUTION = 7
DIST_MIN_ULTRA_KM = 1.0
RENDA_MIN = 4500.0
AREA_MIN_M2 = 1200.0
AREA_IDEAL_MIN_M2 = 1500.0
AREA_IDEAL_MAX_M2 = 2000.0
PE_DIREITO_MIN = 3.5
M1_SCORE_OFICIAL = "score_priorizacao"
M1_PRIORIZACAO_TOP_PCT_POR_UF = 0.20
M1_OSM_ENABLED = False
M1_SETOR_CENSITARIO_OBRIGATORIO = False
M1_POP_MINIMA_PROXY = 1
M1_HEX_LAND_FRACTION_MIN = 0.05
```
> `M1_HEX_LAND_FRACTION_MIN` faltava neste bloco ate 2026-07-27 e e' o parametro que define o
> UNIVERSO de hexes (criterio hibrido do litoral): 0.20 na DEC-002 -> **0.05** na DEC-003, o que
> levou a base de 1.537.950 para **1.542.531** hexes. Valor real em `config.py`; travado por
> `tests/contracts/test_parametros_canonicos.py`.

### Fluxo oficial
Implementacao em `src/motor_expansao/pipelines/m1/`; scripts da raiz continuam como wrappers legados:
1. `base_h3_brasil.py` -> `data/staging/brasil/uf=XX/hexagonos.parquet`
2. `hex_enrichment.py` -> `data/staging/brasil_estrutural.parquet`, `data/staging/brasil_priorizados.parquet`, `data/staging/hexagonos_brasil_oportunidades.parquet`
3. `fase1_bi_exports.py` -> artefatos executivos e BI estaveis

### Score oficial
```python
renda_pct_nacional = percentil_nacional(renda_per_capita)
pop_pct_nacional = percentil_nacional(populacao_proxy)
hex_score_estrutural = 100 * (0.40 * renda_pct_nacional + 0.60 * pop_pct_nacional)
score_priorizacao = clip(hex_score_estrutural + ajuste_executivo, 0, 100)
score_oficial = score_priorizacao
```
- Inputs oficiais: `renda_per_capita` e `populacao_proxy` (= `pop_total`; trava 18-45 removida em 2026-05-15).
- Pesos aprovados: `renda=0.40`, `pop=0.60`.
- Campos minimos: `renda_pct_nacional`, `pop_pct_nacional`, `hex_score_estrutural`, `ajuste_executivo`, `score_priorizacao`, `score_oficial`, `score_oficial_nome`, `score_percentil_nacional`.
- Artefatos oficiais: `brasil_estrutural.parquet`, `brasil_priorizados.parquet`, `hexagonos_brasil_oportunidades.parquet`, `hexagonos_brasil_dashboard.parquet`, `hexagonos_mapa_sample.parquet`, `top_oportunidades_resumo.csv`, `resumo_por_uf.csv`.

## 4. Camadas paralelas e estado atual
- `M1.1`, censitario, hibrido, mercado residual e Expansao de Dominio sao paralelos ao M1.
- Modelo hibrido: M1 aprova municipios; censitario ranqueia hexes dentro de municipios aprovados; `score_expansao_hibrido` e operacional.
- Dashboard separa papeis: mapa executivo/hibrido para leitura local, carteira por M1, residual como apoio de mercado.
- Camada de mercado por hexagono:
  - objetivo: combinar demanda, oferta mapeada e restricao da rede propria Ultra;
  - base principal: `data/staging/hexagonos_mercado_mapeado.parquet`;
  - outputs acionaveis: `carteira_expansao_acionavel.parquet` e `plano_expansao_curto_prazo.parquet`;
  - residual fitness: `oferta_efetiva_disponivel` e `score_oportunidade_residual`;
  - oferta consumida: concorrentes mapeados + Ultra propria;
  - capacidade default de concorrente/unidade proxy: 2500 alunos;
  - `pop_hex_base` usa `pop_total_setor_2022` quando disponivel e fallback `populacao_proxy / total_hex_municipio`.
- O piloto web funciona com Parquets locais em `data/outputs/` (montados `:ro` em producao); sem recalculo de score em runtime.
- Artefato derivado (NAO oficial M1): `fase1_bi_exports.py` tambem materializa `data/outputs/hexagonos_dashboard_enriquecido/uf=XX/parte-*.parquet` (resultado de `enrich_dashboard_data`, particionado por UF) para acelerar a carga do piloto; nao recalcula score nem altera artefatos oficiais. Detalhe em `docs/m1_outputs_oficiais.md`.
- Carga lazy por UF: o backend do piloto le so a particao `uf=XX` desse artefato (`read_enriched_uf_partition`/`list_partitioned_ufs` em `dashboard/data.py`) — a 1a leitura de uma UF carrega a particao inteira e demora; e' esperado.
- Render lazy das abas (Bloco 5): `main()` usa `render_tab_selector` (`st.segmented_control` + `session_state`) no lugar de `st.tabs`; so o `render_*` da aba ativa roda por rerun (UX de 4 abas preservada). `build_city_summary`/`build_uf_summary` so sao computados nas abas Visao Executiva/Mapa Territorial. Nao recalcula score nem altera artefatos.
- Fonte de mapa enxuta (Bloco 6): os builders de mapa fazem downsample antes do cap via `_downsample_map_index` (ordena/dedup/`head(MAP_POINT_LIMIT)` sobre projecao leve de chaves) e so materializam as colunas completas (`MAP_SOURCE_COLUMNS_M1`/`MAP_SOURCE_COLUMNS_HYBRID` em `constants.py`) para os ≤35k sobreviventes. Cap inalterado (mesmos top-N por prioridade); busca por hex fora do recorte lida do `df`. Nao usa `hexagonos_mapa_sample.parquet` (nacional, so 39 cols M1). Nao recalcula score nem altera artefatos.
- Relatorio Pontual Censitario (raio 1,0 km desde a DEC-021; 1,5 km ate 2026-07-29): ciclo concluido em 2026-05-22; base geo completa em 2026-05-25. Contrato em `docs/relatorio_pontual_censitario.md`; usa malha real IBGE 2022 em `data/outputs/setores_censitarios_2022_geo/uf=XX/cod_municipio=NNNNNNN/part-000.parquet`, com `geometry_wkb` em `EPSG:4674`, area/densidade em `EPSG:5880`, bbox e score setorial paralelo. Cobertura: 27 UFs, 5.571 municipios, 468.099 setores (~1,17 GB). Parquets `censo2022_setores_*.parquet` sao agregados H3 sem geometria e nao bastam para o motor setorial.
- Motor/UI censitario e Relatorio Pontual (mapas, camadas, slide-hero, PDF): contrato canonico em `docs/relatorio_pontual_censitario.md`; implementacao em `src/motor_expansao/dashboard/censo_map.py` e `censo_report.py`. Invariantes que valem sempre: o motor censitario (`setor_censitario_intersecao_area_1km`, `RAIO_CENSITARIO_DEFAULT_KM` = **1,0 km desde a DEC-021**, 2026-07-29, autorizada por Felipe; era 1,5 km) so muda por DEC explicita, e a camada e' READ-ONLY sobre o M1. O raio e' calculado em RUNTIME (`buffer` + `intersection` por setor), entao troca-lo NAO exige reprocessar o artefato geo — mas exige reescalar as metas ABSOLUTAS dos Big Numbers e revisar toda string de raio visivel.
- Resolucao de `cod_municipio`: o dataset M1 base nao tem essa coluna; ela flui do censo trace via `enrich_dashboard_data` (`censo_extra_cols` inclui `cod_municipio`). Fallback para parquets enriquecidos antigos: `resolve_cod_municipio_from_geo_dir` le uma linha por particao `uf=XX/cod_municipio=N/` para casar pelo `nome_municipio`. `render_mapa_territorial` e `render_relatorio_pontual_censitario` aceitam `censo_geo_dir: Path` para ativar esse fallback.
- Renda media domiciliar (READ-ONLY, visualizacao; formula corrigida em 2026-08-14): exibida no tooltip do hex, no grid 2x2 do Relatorio Pontual e no PDF da API/bot, sempre como `V06004_bruta x uplift x FATOR_TEMPORAL_RENDA` (per capita = dividir por moradores). A formula antiga (`renda_pc_calibrada x moradores x uplift x ...`) tinha DUPLA CONTAGEM: a calibrada carrega o `k` e o uplift ja converte a escala — NAO reintroduzir o `k` na renda exibida (o `k` so serve ao score). Formula, fontes de uplift e faixas em `docs/relatorio_pontual_censitario.md`.
- Camada paralela PLANEJADA `Motor de Dimensionamento e Viabilidade` (epic `BLK-DIM-00..04`, spec `docs/modelo_dimensionamento_expansao.md` do CEO; substitui o BLK-SCORE-05 — DEC-008): motor inverso de 4 camadas (Potencial via aderencia calibrada -> Captura/Huff -> Dimensionamento m2 pela curva de densidade -> Viabilidade financeira deterministica). READ-ONLY sobre o M1 (nao toca `score_priorizacao`/pesos/artefatos; DEC-001 intacta). Metodologia obrigatoria: LOO-CV vs baseline, sem R2 in-sample, com intervalos + flag de extrapolacao. Camadas 3-4 prototipaveis ja (BLK-DIM-03); 1-2 dependem de insumos a disponibilizar (serie diaria das maduras, datas de abertura, simulador `.xlsx`). Detalhe no backlog (epic BLK-DIM) e DEC-008.
- API/FastAPI, PostGIS, Prefect, pipelines pesados, M2/M3, pesquisas e Power BI continuam fora do deploy inicial.

## 5. Ciclos concluidos
- **Baseline pytest (2026-07-27): `2006 tests` coletados** (`pytest --collect-only -q`). Qualquer contagem citada em ciclo antigo (497, 509, 532, 656, 661...) e' HISTORICA do momento daquele ciclo — nao usar como tripwire de regressao. Regra: medir a baseline no momento, nao confiar nesta linha, que envelhece a cada ciclo (esta ficou 2 meses em `532` — ver §7, defeito de drift doc-vs-codigo).
- Historico detalhado dos ciclos concluidos: `tasks/completed.md` (fonte unica de conclusao) e `docs/`. Nao reproduzir aqui — este arquivo e' curto por regra de manutencao (ver topo).
- O app de producao e' o **piloto web** com **3 superficies**: `Mapa` (default), `Executiva` e `Viabilidade` (`web/src/App.tsx`; Dock mostra `Expansão de domínio` e `Carteira e plano` como fora do piloto — DEC-020). O dashboard Streamlit de 5 tabs foi aposentado pela DEC-022 (2026-08-03); historia das tabs em `tasks/completed.md`.
- Multi-Hex (Blocos 14-16.2): `agregar_cenario_multihex` retorna 25 campos; hex_id copiavel via `st.code()`; botao add/remove na Analise Pontual; `parse_hex_ids_from_text` aceita qualquer separador; `column_config TextColumn(width="large")` para hex_id integral.
- Dominio Hibrido (Bloco 17): `score_dominio_hibrido = clip(0.60*score_setor_2022_calibrado + 0.40*score_oportunidade_residual, 0, 100)` com fallback para componente unico; rastreabilidade via `motivo_dominio`.
- Consumo fitness (Bloco 18): `Consumo Conc. (est.)`, `Consumo Ultra (real)`, `Consumo Total Instalado` em tooltips, Analise Pontual e tabelas. `analisar_entorno_ponto` retorna `consumo_concorrentes_raio`/`consumo_ultra_raio`.
- Bloco 19 concluido em 2026-05-21: 497 testes passam, 1 skipped; docs atualizados; ciclo Blocos 14-19 completo.
- `Visao Executiva`: mapa Ultra-only (sem hexagonos), KPIs de rede, graficos de residual por UF/cidade.
- `Analise Pontual de Entorno`: raio 1.6 km, helper `analisar_entorno_ponto` em `data.py`; usa centroide de hex/ponto como aproximacao, nao muta inputs, retorna populacao/renda do raio e exibe pins de concorrentes/Ultra filtrados pelo raio.
- Hardening concluido (Bloco 13): 189 testes passam; ciclo completo em 2026-05-20.
- Padronizacao visual concluida (Bloco 9): todos os 4 modos quantitativos usam `score_band_to_color` (10 faixas via `RESIDUAL_SCORE_BANDS`); helper em `dashboard/utils.py`; legenda generica `render_score_bands_legend(mode_label)` em `components.py`.
- Clique exato — decisao tecnica concluida (Bloco 12): manter `st.pydeck_chart` com centroide do hex. `streamlit-folium` (+2 deps) e componente customizado (fora de escopo) descartados. Nota de centroide exibida no dashboard quando clique ativo.
- Captura por clique: `st.pydeck_chart(on_select="rerun")`; retorna centroide do hex selecionado; espaco vazio e botao direito nao suportados; fallback: campo lat,lng na sidebar.
- Regra visual canonica (Bloco 9 em diante): faixas de 10 pontos (0-10 a 90-100) via `RESIDUAL_SCORE_BANDS`; M1 colore por `score_priorizacao`, Censitario por `score_setor_2022_calibrado`, Hibrido por `score_expansao_hibrido`, Residual por `score_oportunidade_residual`.
- Area do raio 1.6 km = pi*1.6^2 = 8.04 km2 (corrige `~5 km2` que aparecia em docs anteriores); para ~5 km2 usar raio ~1.26 km com aprovacao explicita.
- Guardrail permanente: visualizacoes, analise radial e interacoes de mapa nao podem recalcular ou alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano dominio ou artefatos oficiais do M1 sem aprovacao explicita.

## 6. Guardrails de infraestrutura e VPS
- MCP configurado: `ssh-vps-ultra` conecta em `root@2.25.137.241` (Hostinger KVM4, producao).
- GUARDRAIL ABSOLUTO: nunca executar qualquer comando no servidor via MCP (ou qualquer tool SSH) sem confirmacao explicita do usuario para cada comando individual. Isso inclui git pull, docker compose, chmod, rm, e qualquer outro.
- Nao encadear multiplos comandos no servidor sem aprovacao intermediaria.
- Coleta de concorrentes (GymScraping) roda **semanal e autonoma na VPS** (cron `0 6 * * 0` = dom 03:00 BRT): scrape dos 90 coletores -> relatorio de crescimento por rede -> integracao ao motor (regen camada paralela mercado/residual, **READ-ONLY M1**) -> restart. Runbook em `docs/infra_producao.md`; decisao em DEC-013 (§8).
- Detalhes de manutencao e deploy em `docs/infra_producao.md`.

## 6.1 Loop autonomo (ralph) — BLK-LOOP-01
- Padrao "ralph" portado do Growth RPG: um laco roda `/run-cycle` 100% autonomo num **container Docker isolado** (`Dockerfile.loop`, non-root, repo como volume), auth pela assinatura Max (`CLAUDE_CODE_OAUTH_TOKEN`, NAO API key). Lancador de 1 clique: **`iniciar-loop.cmd`** -> `scripts/iniciar_loop.ps1` (le so o token do `.env`, MASCARA o `.env` no container, builda a imagem, cria branch `ciclo/loop-*`, roda). Runbook: `docs/loop_autonomo.md`.
- **REGRA CRITICA — opt-in por marcador:** o loop SO executa blocos que tenham a linha **`| **Autonomia** | loop-safe ... |`** na tabela do bloco em `tasks/backlog.md`. **Bloco SEM esse marcador e TOTALMENTE ignorado pelo loop.** Logo: para um backlog novo entrar no loop, ALGUEM (humano) precisa adicionar essa linha — e isso e a pre-aprovacao que substitui o gate humano interativo. Trabalho futuro/manual: nao marcar (ou `Autonomia: futuro`). O loop tambem respeita `Depende de` (so inicia bloco com dependencias ja em `completed.md`). **NAO confiar em lista de blocos escrita aqui — ela envelhece:** o perimetro real e' o que `python scripts/garimpeiro_select_block.py` devolve, lendo o marcador direto do `tasks/backlog.md` (`RE_LOOP_SAFE`). Em 2026-07-27 esta linha dizia `BLK-DIM-01/02/03/04`, blocos DELETADOS do backlog em 1a19d2a (2026-06-15, superseded) — o elegivel de fato era `BLK-FIX-LTV-01`. Para saber o perimetro, RODAR o seletor.
- **Criterio para um bloco PODER ser `loop-safe`:** READ-ONLY sobre o M1, NAO toca VPS/deploy/segredos, NAO persiste PII, consome `data/staging` (sem ingestao ao vivo). Blocos que tocam M1/score/pesos/artefatos/VPS NUNCA sao loop-safe.
- **Redes de seguranca que substituem o humano no loop:** (1) `run-ralph-loop.sh` aborta se houver credencial sensivel no ambiente (`VPS_/SSH_PRIVATE_KEY/CLICKUP_WRITE/DEPLOY_KEY/GROWTH_API_`); (2) `scripts/loop_guard.py` roda apos cada bloco e aborta + escreve `RELATORIO-BLOQUEIO.md` se o diff tocar `config.py`/`pipelines/m1`/`*scoring*`/artefatos M1/`deploy/`/`Dockerfile.*`/compose/Caddy/authelia/`.env`/`secrets/`/CI; (3) testes (ruff+pytest) como gate sem bypass; (4) container sem chave de VPS -> nao deploya. O loop **commita por path** no branch e **NUNCA** faz merge/push/deploy — revisao + merge sao passos humanos.
  - **Ressalva (DEC-016, 2026-07-13):** a parte "**NUNCA** faz merge/push" acima esta **SUPERSEDED PARCIALMENTE** — **somente** para blocos de criticidade **Baixa/Media** e **somente** com os **4 checks verdes** (`test` + `guard` + `claude-review` + `review-gate`), o merge passa a ocorrer por **auto-merge nativo do GitHub**, sem aprovacao humana. **Alta** exige a label `aprovado-humano` e **Critica** a label `critica-aprovada` do proprio Felipe -> nesses casos o merge **segue humano**. **DEPLOY CONTINUA NUNCA AUTOMATICO, EM NENHUM CASO:** auto-merge NAO deploya (push na main so publica a imagem no GHCR; subir a imagem na VPS e sempre passo manual do Felipe, por digest — §6). Detalhe e gatilho de suspensao em DEC-016 (§8).

## 7. Onde aprofundar
- **Grafo de conhecimento (graphify) — detalhe tecnico** (a NORMA de consultar antes de varrer esta na §2): `python -m graphify query "<pergunta>"`, `... path "A" "B"`, `... explain "<no>"`. **Sempre `python -m graphify`, NUNCA o `graphify` nu** — o pacote instala `graphify.exe` em `<python>/Scripts/`, normalmente fora do PATH (verificado 2026-07-27). Instalar: `python -m pip install --group graph` (grupo `graph` do `pyproject.toml`, PEP 735 — fora do `constraints.txt` DE PROPOSITO, ver comentario no bloco). **O pin `mcp>=1.28,<2` e' obrigatorio:** o `mcp` 2.0.0 removeu `AnyUrl` de `mcp.types` e quebra o servidor com o erro ENGANOSO `'mcp not installed'` (medido 2026-07-28). Cobre 421 arquivos (290 de codigo por AST + 131 docs/contratos/DECs) em 7.633 nos e 15.362 arestas; ~58x menos tokens por consulta que ler o corpus. Artefatos versionados: `graphify-out/graph.json` e `graphify-out/GRAPH_REPORT.md`. Runbook: `docs/grafo_conhecimento.md`.
- **Como o grafo se mantem atualizado (2 caminhos, NAO se substituem):**
  - **CODIGO — automatico.** Hook `post-commit` versionado em `.githooks/` dispara rebuild AST em segundo plano a cada commit (sem LLM, nao bloqueia o `git commit`; log em `~/.cache/graphify-rebuild.log`; pular com `GRAPHIFY_SKIP_HOOK=1`). **Nao viaja sozinho:** o git NAO aceita `core.hooksPath` vindo do repo — cada clone roda `git config core.hooksPath .githooks` uma vez (mesma pegadinha do `.mcp.json`, que pede aprovacao na 1a sessao para quem nao usa `enabledMcpjsonServers`). Equivalente manual: `python -m graphify update .`. Container do loop e CI nao tem o pacote — la o grafo nao atualiza.
  - **DOCS/DECs/backlog — MANUAL.** O hook ignora a camada semantica (precisa de LLM). Depois de mexer em `docs/`, `tasks/`, `CLAUDE.md` ou nas DECs, rodar **numa sessao Claude o SLASH-COMMAND** `/graphify . --update`. **`python -m graphify . --update` NAO faz isso** (verificado 2026-07-28): o CLI reescreve para `extract . --update`, o flag e' ignorado em silencio e vira uma extracao COMPLETA com LLM.
- **LIMITES do grafo, ler antes de confiar:** (a) entre um commit de doc e o `/graphify . --update` manual, a camada semantica esta DESATUALIZADA — se a resposta depender de doc recem-alterado, ler o arquivo; (b) a consulta trunca por orcamento de tokens (usar `--budget`); (c) `context/handoff/` (566 logs) e as imagens ficaram **fora** do corpus de proposito, mas o rebuild automatico NAO respeita esse recorte — por isso o `post-checkout` (rebuild total) ficou FORA do `.githooks/`; (d) e' INDICE de navegacao, **nao** fonte canonica — parametro, formula e guardrail valem pelo §3/§8 e pelos contratos em `docs/`.
- **Indice completo de docs:** `docs/README.md` (mapa tematico de todos os contratos/runbooks).
- `docs/estado_dos_modelos.md`: sintese de desempenho, arquitetura e uso dos modelos + roadmap de produto (2026-07-08). Ler para entender o que cada camada preve e como usar.
- `PRD.md`: guia operacional em blocos do ciclo ativo.
- `docs/modelo_mercado_hexagonos.md`: contrato tecnico de colunas e calculos de mercado/residual.
- `docs/m1_outputs_oficiais.md`: contrato curto dos outputs do M1.
- `docs/m1_1_arquitetura_enriquecimento.md`: design da camada M1.1.
- `docs/arquitetura_app_atual.md`: arquitetura e governanca do dashboard atual (5 abas).
- `data/reports/validacao_penetracao_ultra_hex.md`: aderencia e cautelas com dados reais das unidades Ultra.
- `data/reports/validacao_geofusion_vs_hex.md`: comparacao GeoFusion 1km vs H3.
- `docs/decisions/`: corpo completo das decisoes (DEC-0XX, com emendas); indice canonico (data/criticidade/status) no §8 abaixo.

Se um detalhe historico nao estiver aqui, procurar primeiro nesses docs antes de expandir novamente este arquivo.

## 8. Decisoes registradas (DEC)

> Indice das decisoes. O corpo completo de cada DEC (com suas emendas) vive em `docs/decisions/DEC-0XX.md`; aqui fica so 1 linha por DEC (indice canonico).
> **Regra (manter curto, ver topo):** nova DEC cria o arquivo em `docs/decisions/` e adiciona 1 linha nesta tabela — NAO colar o corpo aqui; emendas entram no arquivo da DEC, nao nesta tabela.
> **Invariantes vigentes** (sempre-verdadeiros; impostos por CODIGO em `scripts/loop_guard.py` + `.github/workflows/guard.yml`, nao so por prosa) — nova DEC nao precisa reafirma-los: M1 READ-ONLY (pesos `renda=0.40`/`pop=0.60`, `score_priorizacao`, `hex_score_estrutural` e artefatos oficiais so mudam com DEC — §1/§3/§5) · merge por criticidade + deploy manual por digest (§6/§6.1, DEC-016) · acentuacao correta em texto de usuario, nunca em identificadores (§2) · CSV `sep=";"` `utf-8-sig` (§2).

| DEC | Data | Criticidade | Decisao | Status |
|---|---|---|---|---|
| [DEC-001](docs/decisions/DEC-001.md) | 2026-05-31 | Crítica | Manter pesos/formula do score_priorizacao (M1) apos backtest BLK-SCORE-02 | APROVADA |
| [DEC-002](docs/decisions/DEC-002.md) | 2026-06-03 | Crítica | Criterio geometrico HIBRIDO no litoral (M1) e regeneracao dos artefatos oficiais (BLK-FIX-06) | APROVADA |
| [DEC-003](docs/decisions/DEC-003.md) | 2026-06-03 | Crítica | Geracao de candidatos por OVERLAP + limiar 0.05 (correcao do BLK-FIX-06; BLK-FIX-06-B) | APROVADA |
| [DEC-004](docs/decisions/DEC-004.md) | 2026-06-05 | Alta | Fundo de ruas por tiles online no Relatorio Pontual Censitario (BLK-CENSO-01) | APROVADA |
| [DEC-005](docs/decisions/DEC-005.md) | 2026-06-10 | Estratégica | Arquitetura e contrato da API GeoEspacial on-demand (BLK-API-01 / G1) | APROVADA |
| [DEC-006](docs/decisions/DEC-006.md) | 2026-06-10 | Alta | Redefinição do gate do SAM: Faixa M1 elegível AND população ≥ 5000 (BLK-SAM-01) | APROVADA |
| [DEC-007](docs/decisions/DEC-007.md) | 2026-06-10 | Alta | Afrouxar o gate do SAM: apenas Faixa M1 elegível AND população ≥ 5000 (reverte 2 sub-decisões da DEC-006; BLK-SAM-02) | APROVADA |
| [DEC-008](docs/decisions/DEC-008.md) | 2026-06-12 | Estratégica | Supersessão do BLK-SCORE-05 pela epic BLK-DIM (Motor de Dimensionamento e Viabilidade — camada paralela) | APROVADA |
| [DEC-009](docs/decisions/DEC-009.md) | 2026-06-15 | Estratégica | Pivô da epic BLK-DIM para "property-first" (viabilidade/break-even); previsão de demanda pela geografia encerrada | APROVADA |
| [DEC-010](docs/decisions/DEC-010.md) | 2026-06-17 | Alta | Resolução de endereço por fetch HTTP na barra de busca do dashboard (BLK-UI-08) | APROVADA |
| [DEC-011](docs/decisions/DEC-011.md) | 2026-06-22 | Alta | Fundo de ruas por tiles online no Relatório Municipal (BLK-RELMUN-01); e critério/rótulo dos hexágonos destacados | APROVADA |
| [DEC-012](docs/decisions/DEC-012.md) | 2026-06-24 | Estratégica | Adoção da camada paralela de Demanda Revelada (H3 res-7, sem PII; BLK-TP-01) | APROVADA |
| [DEC-013](docs/decisions/DEC-013.md) | 2026-06-26 | Alta | Coleta recorrente de concorrentes (GymScraping) automatizada na VPS + integração ao residual (READ-ONLY M1) | APROVADA |
| [DEC-014](docs/decisions/DEC-014.md) | 2026-07-01 | Estratégica | Score de retenção territorial (camada paralela M2 READ-ONLY sobre o M1; BLK-LTV-04) | APROVADA |
| DEC-015 | — | — | *(reservado — a numeracao pulou 014→016)* | — |
| [DEC-016](docs/decisions/DEC-016.md) | 2026-07-13 | Estratégica | Portão da `main` por CHECKS DE CI (0 aprovações) e auto-merge de blocos Baixa/Média | APROVADA |
| [DEC-017](docs/decisions/DEC-017.md) | 2026-07-15 | Estratégica | Normalização de EOL (Markdown de `tasks/`+`docs/` em LF) + enxugamento do CODEOWNERS (uma aprovação para governança de bookkeeping) | APROVADA |
| [DEC-018](docs/decisions/DEC-018.md) | 2026-07-22 | Alta | Vista aérea por tiles de satélite (Esri) no Relatório Pontual Censitário, via chave ArcGIS por env (BLK-SAT-01) | APROVADA |
| [DEC-019](docs/decisions/DEC-019.md) | 2026-07-23 | Estratégica | Segundo dono autorizado a liberar merge Crítico (`@VinhoAbencoado`); emenda a blindagem #3 da DEC-016 | APROVADA |
| [DEC-020](docs/decisions/DEC-020.md) | 2026-07-23 | Estratégica | Escopo do corte do Streamlit pelo piloto web: Domínio fora (coberto pela Fase 4 do Mapa), Carteira vira Oportunidades Imobiliárias (placeholder), paridade só de Mapa + Visão Executiva + Viabilidade (BLK-WEB-11); renumerada de DEC-019 na reconciliação — emendada pela DEC-022 (corte imediato) | APROVADA |
| [DEC-021](docs/decisions/DEC-021.md) | 2026-07-29 | Crítica | Raio do Relatório Pontual Censitário passa de 1,5 km para 1,0 km — análise, rótulo do método (`..._1km`, muda contrato da API); metas absolutas dos Big Numbers MANTIDAS por decisão de Felipe; emenda a decisão-chave 5 da DEC-005 e o invariante do §3 | APROVADA |
| [DEC-022](docs/decisions/DEC-022.md) | 2026-08-03 | Estratégica | Substituição total do Streamlit pelo piloto web: corte imediato com perdas aceitas (emenda a consequência iv da DEC-020), fila/lote como porte prioritário pós-corte, `dashboard.` vira host só de `/tiles/` + 301, fim da branch `piloto-web` e dos PRs gêmeos; guard ganha `^web/` | APROVADA |
| [DEC-023](docs/decisions/DEC-023.md) | 2026-08-04 | Estratégica | Visão Executiva 2.0: a aba vira dashboard acionável da rede (carteira priorizada -> ficha), mapa vira card, réguas absolutas e coorte de maturidade; primeira ESCRITA do piloto (cadastro editável em volume `:rw` próprio, guardrail READ-ONLY intacto); emenda a DEC-020 e a consequência (iii) da DEC-022; emendada pela DEC-027 | APROVADA |
| [DEC-024](docs/decisions/DEC-024.md) | 2026-08-04 | Alta | Extensão do escopo de coleta do GymScraping: nota in-app do WellHub (`partnerRating`) como agregado numérico, com schema de 2 colunas e estados distinguíveis (BLK-MA-08); fatia o gate conjunto MA-08/MA-09; emenda as partes 2 e 3 da DEC-013 | APROVADA |
| [DEC-025](docs/decisions/DEC-025.md) | 2026-08-07 | Alta | Critério de universo do coletor WellHub (vocabulário de musculação "V2", após a renomeação da taxonomia) + taxonomia (`atividades`/`modalidades`) sai do hash de staleness nas duas fontes, com bump `snapshots_concorrentes_v1` -> `v2` e quebra de comparabilidade declarada (BLK-MA-11); emenda a parte 3 da DEC-013 | APROVADA |
| [DEC-026](docs/decisions/DEC-026.md) | 2026-08-10 | Alta | Gate do BLK-MA-09 (D-B = opção 0): o rating do WellHub entra como **coluna-fato sem peso** (molde do G-D2), `SINAIS_INATIVOS` segue `("s2",)` e o bloco deixa de reativar o `v2`; D-A e D-C ficam sem objeto. Com peso, o `v2` INVERTE o ranking — `score_com = 0,75·score_sem + 25·v2` penaliza 99,97% das linhas com nota, e o alvo `sumiu_recente` cai 22 pontos. Snapshot vai a 12 colunas | APROVADA |
| [DEC-027](docs/decisions/DEC-027.md) | 2026-08-17 | Alta | Trilha de acesso do piloto web (quem fez o quê, retenção 90 dias): middleware com identidade Authelia + segundo volume `:rw` fora de `/app/data` + Caddy access log + Authelia `info`; emenda o "único mount de escrita" da DEC-023; bot/API fora do escopo | APROVADA (emendada: aba Acessos restrita por allowlist + rollup sem dado pessoal, 2026-08-19) |
| [DEC-028](docs/decisions/DEC-028.md) | 2026-08-14 | Alta | A camada de M&A entra no piloto como **OVERLAY de `pressão competitiva`** — nunca "vulnerabilidade": com `{s1,s6}` o `v1` é constante `0,5` e o score vira `30 + 40·v6`, então o que um ranking ordena hoje é pressão. É liga/desliga (molde da chave de raio), **não** um passo 6 do funil, que é a inversão do §2 e quebraria os contratos do funil. Emenda o G-D1 (`flag_score_provisorio` passa a `(~s3)&(~s4)&(~s6)`, senão o `ordenavel` nasce nulo em 19.329 de 19.329) e o §10 (overlay sai de "opcional/futuro"). Terceiro artefato `alvos_ma_hex.parquet`, com colapso de regimes explícito (BLK-MA-13). **OVERLAY REVERTIDO no mesmo dia** por redundância com a camada 3 do funil (Pearson `1,0000` contra o mesmo insumo): caíram a superfície e o artefato; **PERMANECE a emenda do G-D1**, que é sobre o score. O rótulo volta a valer no BLK-MA-15 — ver a emenda no arquivo da DEC | APROVADA (emendada) |
| [DEC-029](docs/decisions/DEC-029.md) | 2026-08-14 | Alta | Sinal 6 passa a ser medido **POR ACADEMIA** (da coordenada da unidade), não do centroide do hex: "independente espremida" é propriedade da academia, e no grão antigo todas as do mesmo hex EMPATAVAM (`0 de 6.753` com variação). Erro medido em SP: médio **7,82** pts, p90 22,15, **máx 65,97**; 33% mudariam de faixa; caso decisivo — hex mede `1,2` e a academia dentro dele, `67,2`. **Rota B: zero bump de série** (coordenada lida do feed, usada e descartada; rejeitada a rota que custaria 3 bumps em cascata). Os dois grãos coexistem com carimbo `pressao_grao`; a agregação do entregável deixa de ser `first` (vira média+máximo); score vai a 25 colunas, bump `v3`->`v4` (BLK-MA-14) | APROVADA |
| [DEC-030](docs/decisions/DEC-030.md) | 2026-08-14 | Alta | A Conclusão do Relatório Pontual passa a carimbar **DOIS selos** independentes — DEMOGRÁFICO (praça: E4 zona morta, E5, R4, R7, censo indisponível) e FINANCEIRO (imóvel e retorno: E1/R1, E2/R2, E3/R3, R5, R6) — e **deixa de emitir veredito único**: `_ConclusaoPonto` perde o campo `status`, porque um agregado sem consumidor de render seria lido como *o* veredito. Reverte a premissa fundadora da página (2026-08-06) sem reabrir nenhum corte: o golden do Recife decompõe em `1/2/2` no financeiro (a calibração de Vinicius, intacta) e `4/1/0` no demográfico. Zona morta é DEMOGRÁFICA (dispara por `pop<5000`/`renda<1600`); só-estudo desenha um selo (`financeiro is None`) e absorve a exceção de Juan por construção; invariante de coerência com a tela reendereçado ao eixo financeiro. Selo 240x196 -> 210x176 + gap 20, senão o 2º sairia por baixo do rodapé em silêncio (`auto_page_break` OFF). Só o PDF; tela intocada. **Emenda 1 (mesmo dia):** o gate **E5 passa a valer nos DOIS modos** — a régua da praça deixa de depender de por qual porta o relatório saiu; revoga o escopo só-bot fechado por Juan em 2026-08-12. Corte (4 de 6) inalterado e golden do Recife intacto (máx. 1 meta), medido antes de decidir | APROVADA (emendada) |
| [DEC-031](docs/decisions/DEC-031.md) | 2026-08-13 | Crítica | Régua do percentil de renda setorial: MANTER a referência do M1 (a troca por régua setorial foi medida e refutada — não faz SC/PR passarem e Curitiba piora), reclassificar o gate de spearman como indicador diagnóstico e abrir bloco próprio para a assimetria de granularidade entre os dois termos do score | PROPOSTA |
| [DEC-032](docs/decisions/DEC-032.md) | 2026-08-14 | Crítica | O `k` de calibração da renda setorial é NACIONAL e único (1,2334632197): correção do cálculo feito dentro do laço por UF, que dava um `k` por estado (0,7956 DF a 2,5505 MA) e fazia as 27 UFs pousarem na mesma mediana — apagando, e na cauda invertendo, a diferença de renda entre estados (correlação −0,456 com o IBGE). Ratifica a variante já aprovada no relatório de calibração de 2026-05-15; muda `score_setor_2022_calibrado` em 95,0% dos setores | PROPOSTA |
| [DEC-033](docs/decisions/DEC-033.md) | 2026-08-14 | Alta | Independentes entram na **oferta** do sinal 6 com **metade** do peso de uma unidade de rede (`0,5` contra `1,0`). O insumo de hoje (`concorrentes_mapeados`) tem 4.499 pontos, 104 redes e **zero independentes**, entao a pressao respondia "quanta CADEIA cerca" — **37,8% do universo marcava `0`, e 32,3% (6.238 academias) tinham sinal invisivel vindo so' de independentes**. Universo CONDICIONAL ao insumo (molde da DEC-036), carimbo `universo_oferta` obrigatorio, auto-exclusao por chave (sem ela, `+33,3` pts fantasma) e dedup entre fontes (hoje sem efeito: so' ha WellHub). A saturacao **nao embaralha o ranking** (`Spearman = 1,000000`); ela achata a leitura e desloca limiares absolutos. Score vai a 26 colunas, bumps `v4`->`v5` / `pressao_v1`->`v2` (BLK-MA-16; **renumerada de DEC-030 em 2026-08-15** — o numero colidia com uma DEC-030 ja' existente na `main`) | APROVADA (opcao A: e' o default) |
| [DEC-034](docs/decisions/DEC-034.md) | 2026-08-15 | Alta | As **unidades de REDE que o agregador lista** entram na oferta do sinal 6, com peso `1,0`. E' a outra metade da DEC-033: la' as independentes nao contavam como oferta, aqui **2.844 unidades de cadeia** listadas no WellHub tambem nao — e **1.171 delas** nao tem equivalente em `concorrentes_mapeados`, ou seja, sao academias reais que nao pressionavam ninguem (as outras 1.673 colapsam contra um ponto ja' mapeado). Dedup PROPRIA contra o insumo mapeado, `(rede igual E d <= 150 m) OU (d <= 50 m)`: casar a rede salva **37 concorrentes reais** que a distancia pura apagaria, e o piso recupera 8 enderecos iguais com slug divergente (o menor a `0,0` m). Auto-exclusao nos DOIS casos (sobrevivente e colapsada; sem ela, `+50` pts fantasma). **A ordem MUDA** — `Spearman 0,9911994` contra a regua anterior, **12 das 100 primeiras linhas do CSV trocam** — e tres reguas VISIVEIS no pin se movem (`pressao` em 7.237 academias, `n_conc` em 7.218, `dist_m` em 773). Contratos de pressao vao a 15/14 colunas e o nomeado a 24; **quatro bumps**: `pressao_v2`->`v3`, `score_v5`->`v6`, `alvos_ma_v2`->`v3`, `nomeados_v3`->`v4` (BLK-MA-17, metade 2) | APROVADA |
| [DEC-035](docs/decisions/DEC-035.md) | 2026-08-18 | Alta | **Metade 1 do BLK-MA-17**: as **2.844 unidades de REDE** do agregador ganham diagnóstico VISÍVEL, mas com **fato e sem score**. Recebem o **S6** (geográfico, não sabe se a academia é de rede) e os fatos sem peso (`nota_wellhub`, `qtd_avaliacoes_wellhub`, `status_churn`); **não** recebem `score_vulnerabilidade`. Razão medida: S1 e S3 medem OUTRA COISA numa rede — a negociação com o agregador é centralizada, e o S3 é correlacionado (top 5 = **48,4%** das unidades, máx **440** numa rede): quando a Panobianco sair do WellHub, 440 unidades viram `sumiu_recente` no mesmo dia e o score leria negociação como 440 alvos. Molde do G-D2/DEC-026 — o fato entra antes do peso. `_filtrar_universo_sinal_1` **intacto** (universo de exibição próprio) e a lista de alvos segue só de independentes. **Precedência de pin sai de graça da DEC-034**: as 1.171 sobreviventes da dedup são exatamente as sem pin desenhado. A auditoria do pin é corrigida na CAUSA — a revisão de 2026-08-17 mediu que a promessa "o operador conta os pins e o número fecha" **já falhava em 16,4% ANTES** da metade 2 (recorte municipal contra raio de 2 km, duas réguas de validade, dedup entre fontes) | APROVADA |
| [DEC-036](docs/decisions/DEC-036.md) | 2026-08-13 | Alta | Sinal 6 (pressão competitiva com decaimento por distância) entra em `Σ(wi·vi)` com `w6 = 0,10`, **ATIVO mas CONDICIONAL** — disponível sse o insumo de pressão vier na chamada. Pesos do D4 seguem CONGELADOS e a soma-alvo vai a `1,10` (inócuo: `renormalizar_pesos` divide pelos PRESENTES). Sem a condicionalidade, o S6 deslocaria os pesos efetivos de S1/S3/S4 e tornaria INALCANÇÁVEL a trava "ausência nunca é zero". Score vai a 24 colunas, bump `v2`->`v3` (BLK-MA-12) | APROVADA |
