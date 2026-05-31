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
- Publico-alvo prioritario: 18-45 anos.
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
- Nao criar dependencia de API ao vivo no dashboard de producao.
- Toda mudanca relevante entra com teste; nenhum PR deve subir com CI quebrado.
- Quartis sao apoio de ranking relativo; para sizing e decisao executiva, priorizar regua absoluta, residual, receita esperada e capacidade operacional.
- Pins/logos de concorrentes e Ultra no dashboard sao camada visual de apoio; nao alteram score, ranking, carteira nem artefatos oficiais.
- Variaveis IBGE Censo 2022 Basico: `v0001` = Total de pessoas; `v0002` = Total de Domicilios; `v0007` = Domicilios Particulares Ocupados; `v0005` = media de moradores.
- O guia operacional do ciclo ativo fica em `PRD.md`; contratos tecnicos detalhados ficam em `docs/`.
Interpretação operacional da regra de criticidade para score (decidida em 2026-05-30):
- LEITURA/ANÁLISE de score sem escrita em artefato M1 → Alta (revisão humana antes do Builder)
- ALTERAÇÃO de fórmula, pesos, ou qualquer artefato M1 → Crítica (aprovação obrigatória + DEC)

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
```

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
- Dashboard funciona offline com Parquets locais em `data/outputs/`.
- Artefato derivado (NAO oficial M1): `fase1_bi_exports.py` tambem materializa `data/outputs/hexagonos_dashboard_enriquecido/uf=XX/parte-*.parquet` (resultado de `enrich_dashboard_data`, particionado por UF) para acelerar a carga do dashboard; nao recalcula score nem altera artefatos oficiais. Detalhe em `docs/m1_outputs_oficiais.md`.
- Carga lazy por UF (Bloco 4): o dashboard le so a particao `uf=XX` desse artefato (`load_uf_slice`/`read_enriched_uf_partition`), com catalogo leve via diretorios de particao (`load_uf_catalog`/`list_partitioned_ufs`) e fallback para `build_dashboard_dataset()` filtrado quando a particao nao existe. Consequencia: a busca por coordenada resolve dentro da UF carregada.
- Render lazy das abas (Bloco 5): `main()` usa `render_tab_selector` (`st.segmented_control` + `session_state`) no lugar de `st.tabs`; so o `render_*` da aba ativa roda por rerun (UX de 4 abas preservada). `build_city_summary`/`build_uf_summary` so sao computados nas abas Visao Executiva/Mapa Territorial. Nao recalcula score nem altera artefatos.
- Fonte de mapa enxuta (Bloco 6): os builders de mapa fazem downsample antes do cap via `_downsample_map_index` (ordena/dedup/`head(MAP_POINT_LIMIT)` sobre projecao leve de chaves) e so materializam as colunas completas (`MAP_SOURCE_COLUMNS_M1`/`MAP_SOURCE_COLUMNS_HYBRID` em `constants.py`) para os ≤35k sobreviventes. Cap inalterado (mesmos top-N por prioridade); busca por hex fora do recorte lida do `df`. Nao usa `hexagonos_mapa_sample.parquet` (nacional, so 39 cols M1). Nao recalcula score nem altera artefatos.
- Relatorio Pontual Censitario 1.5 km: ciclo concluido em 2026-05-22; base geo completa em 2026-05-25. Contrato em `docs/relatorio_pontual_censitario.md`; usa malha real IBGE 2022 em `data/outputs/setores_censitarios_2022_geo/uf=XX/cod_municipio=NNNNNNN/part-000.parquet`, com `geometry_wkb` em `EPSG:4674`, area/densidade em `EPSG:5880`, bbox e score setorial paralelo. Cobertura: 27 UFs, 5.571 municipios, 468.099 setores (~1,17 GB). Parquets `censo2022_setores_*.parquet` sao agregados H3 sem geometria e nao bastam para o motor setorial.
- Motor/UI censitario: `analisar_ponto_censitario_setores` cruza setor real x circulo 1.5 km em CRS metrico local; metodo `setor_censitario_intersecao_area_1p5km`. `render_mapa_censitario_estatico_png` gera PNG offline via Pillow; `censo_report.py` gera CSV/PDF em memoria; `render_relatorio_pontual_censitario` roda no expander do Mapa Territorial, com lazy load/cache por `uf` + `cod_municipio` e mensagem clara quando a base geo nao existe. Nao recalcula score nem altera artefatos.
- Resolucao de `cod_municipio`: o dataset M1 base nao tem essa coluna; ela flui do censo trace via `enrich_dashboard_data` (`censo_extra_cols` inclui `cod_municipio`). Fallback para parquets enriquecidos antigos: `resolve_cod_municipio_from_geo_dir` le uma linha por particao `uf=XX/cod_municipio=N/` para casar pelo `nome_municipio`. `render_mapa_territorial` e `render_relatorio_pontual_censitario` aceitam `censo_geo_dir: Path` para ativar esse fallback.
- API/FastAPI, PostGIS, Prefect, pipelines pesados, M2/M3, pesquisas e Power BI continuam fora do deploy inicial.

## 5. Ciclos concluidos
- **Baseline pytest atual (2026-05-28): `532 passed, 1 skipped, 9 warnings`** via `pytest -q`. Os numeros menores citados nos ciclos abaixo (497, 509 etc.) sao contagens historicas de cada ciclo no momento em que foi concluido — nao comparar com o estado atual.
- Ciclo `BLK-OPS-01 — Backup encriptado de segredos e plano de regeneracao` (tooling) concluido em 2026-05-28: tooling SOPS+age, runbook `docs/backup_restore.md` com 16 secoes + 7-bis (Plano B), scripts `setup_secrets_vps.sh` + `secrets_roundtrip_test.{sh,ps1}`. FU1 (stage do `.ps1`) e FU2 (execucao do roundtrip + gitleaks com correcoes do tooling + criacao de `.gitleaks.toml`/`.gitleaksignore`) concluidos no mesmo dia.
- Ciclo `BLK-OPS-01 — Fechamento real (backup real + restore validado)` concluido em 2026-05-29: chave age real gerada via Plano B (recipient `age1lau0w4xg...` commitado, privada em KeePassXC + papel), 5 segredos reais encriptados in-place no VPS (chave privada nunca tocou o VPS), 5 `.enc.*` commitados em `secrets/`, restore real validado em pasta limpa (binarios byte-identicos, textos semanticamente identicos via PyYAML). Defeitos 3-5 do tooling original descobertos e corrigidos durante o fechamento: path_regex sem `/` em SOPS 3.8.1, sufixo `env.enc.env` para regra dotenv casar, `.gitattributes` com `binary` para `.enc.*` (evita CRLF conversion em checkouts Windows). Risco de DR eliminado. Detalhes em `tasks/completed.md`. Nenhum segredo real exposto a Claude; M1, dashboard e artefatos oficiais inalterados.
- Ciclo `Relatorio Pontual Censitario 1.5 km` concluido em 2026-05-22 (7 blocos): feature paralela no Streamlit usando geometria real de setores IBGE 2022, raio fixo 1.5 km, intersecao geometrica, mapa censitario offline e export PDF/CSV em memoria. Validacao de fechamento: suite censitaria + `test_streamlit_app.py` verdes e import do app ok. Nao substitui Analise Pontual H3 nem altera M1.
- Ciclo `Performance e Refatoracao do Dashboard` concluido em 2026-05-22 (7 blocos): carga lazy por UF (le so a particao do enriquecido), render lazy de abas, fonte de mapa enxuta e dataset enriquecido particionado; 509 testes passam, 1 skipped. Detalhe em `data/reports/perf_baseline_dashboard.md`. Sem recalculo de score/carteira/plano/artefatos M1.
- Ciclo `Cenarios Multi-Hex e Dominio Hibrido Censitario-Residual` concluido em 2026-05-21 (Blocos 14-19 do PRD).
- Ciclo `Hardening da Analise Pontual e Padronizacao Visual de Scores` concluido em 2026-05-20 (Blocos 8-13 do PRD).
- Ciclo `Visao Executiva Ultra e Analise Pontual` concluido em 2026-05-20 (Blocos 1-7 do PRD).
- Dashboard tem 4 tabs: `Visao Executiva`, `Mapa Territorial`, `Expansao de Dominio`, `Carteira e Plano`.
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
- Detalhes de manutencao e deploy em `docs/infra_producao.md`.

## 7. Onde aprofundar
- `PRD.md`: guia operacional em blocos do ciclo ativo.
- `docs/modelo_mercado_hexagonos.md`: contrato tecnico de colunas e calculos de mercado/residual.
- `docs/m1_outputs_oficiais.md`: contrato curto dos outputs do M1.
- `docs/m1_1_arquitetura_enriquecimento.md`: design da camada M1.1.
- `docs/streamlit_dashboard_m1.md`: governanca e uso do dashboard.
- `data/reports/validacao_penetracao_ultra_hex.md`: aderencia e cautelas com dados reais das unidades Ultra.
- `data/reports/validacao_geofusion_vs_hex.md`: comparacao GeoFusion 1km vs H3.

Se um detalhe historico nao estiver aqui, procurar primeiro nesses docs antes de expandir novamente este arquivo.

## 8. Decisoes registradas (DEC)

### DEC-001 — Manter pesos/formula do score_priorizacao (M1) apos backtest BLK-SCORE-02
- ID: DEC-001 | Data: 2026-05-31 | Criticidade: critica (decisao sobre pesos M1)
- Status: APROVADA por Felipe Silva em 2026-05-31.
- Decisao: NAO recalibrar. Manter `renda=0.40` / `pop=0.60` (`PESOS_HEX_SCORE_ESTRUTURAL`) e a formula de `score_priorizacao` INALTERADAS; nenhum artefato M1 regerado. O M1 e a camada EXECUTIVA (municipios/ranking de carteira), nao o score operacional primario do dia a dia (esse papel e da camada censitaria).
- Evidencia-chave (de `data/analysis/relatorio_backtest.md`, BLK-SCORE-02, read-only, gitignored):
  - `score_priorizacao` (AGG): Spearman rho ≈ -0.004, IC95% [-0.104, +0.094] (atravessa zero) -> poder preditivo nulo, sem direcao a corrigir.
  - Componentes nao-significativos: `renda_pct_nacional` +0.067 (n.s.) e `pop_pct_nacional` +0.095 (n.s.); diferenca dentro do ruido e o peso atual ja favorece pop (0.60>0.40). Recalibrar seria sobreajuste a ruido.
  - Sem feature nova usavel DENTRO do M1: `n_domicilios` e `densidade_dom` em `brasil_estrutural.parquet` EXISTEM mas estao 100% ZERADAS (placeholders, nunique=1, min=max=0.0); correlacao indefinida. As unicas features reais do M1 sao `renda_per_capita` e `pop_total`.
  - Censitario (`score_setor_2022_calibrado`, camada PRIMARIA operacional) e o unico preditor positivo significativo: rho +0.148, IC [+0.052, +0.251].
- Pesos antigos -> novos: `renda_per_capita` 0.40 -> 0.40 (INALTERADO); `populacao_proxy` 0.60 -> 0.60 (INALTERADO); formula INALTERADA.
- Plano de reabertura (novo bloco CRITICO; Planner -> gate humano -> Builder): so se TODOS satisfeitos —
  - PRE-REQUISITO de engenharia de dados: popular `n_domicilios`/`densidade_dom` (hoje 100% zeradas); sem isso nao existe M1 multivariado a calibrar.
  - G1: `maturacao_status` deixar de ser constante unica (data de abertura por unidade) para controlar maturacao.
  - G2: desfecho homogeneo e auditavel entre redes (sem estimativa para EngCorpo).
  - G3: N adequado por celula e hex com precisao de unidade na maioria das linhas.
  - G4: sob esses controles e/ou com sinal significativo vindo do BLK-SCORE-04, um componente/feature com correlacao significativa (p<0.05, IC sem cruzar zero) e materialmente diferente do peso atual.
- Referencias: `data/analysis/relatorio_backtest.md` (BLK-SCORE-02); `context/handoff.md` (BLK-SCORE-03); BLK-SCORE-04 (proposta no backlog).
