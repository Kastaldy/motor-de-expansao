# PRD - Guia Operacional para Agentes de IA
**Projeto:** Motor de expansao - Ultra Academia
**Ultima atualizacao:** 2026-05-18
**Ciclo ativo:** Expansao de Dominio

## Instrucoes obrigatorias
1. Ler `CLAUDE.md`, `README.md` e este PRD antes de qualquer acao.
2. Tratar `CLAUDE.md`, `config.py` e este PRD como fontes de verdade operacional.
3. Executar apenas o proximo bloco cujo cabecalho esteja com `[ ]`.
4. Antes de editar, ler os arquivos reais envolvidos e rodar `git status --short`.
5. Nao reverter nem sobrescrever mudancas existentes sem aprovacao explicita.
6. Atualizar `CLAUDE.md` e `PRD.md` se mudar regra, target, semantica de coluna, fluxo ou decisao relevante.
7. Se houver ambiguidade entre codigo e documentacao, corrigir primeiro a documentacao e depois o codigo.
8. Nao encerrar bloco sem editar arquivo, registrar observacoes e rodar validacao minima.
9. Tentar manter `CLAUDE.md` e `PRD.md` com no maximo `200` linhas.
10. Quando um ciclo fechar, consolidar o historico em `Estado atual` e substituir blocos antigos pelo backlog ativo.
11. Este ciclo nao pode alterar `score_priorizacao`, `hex_score_estrutural` nem os artefatos oficiais do M1 sem aprovacao explicita.

## Estado atual
- M1 oficial permanece como gate executivo de prioridade territorial; `score_priorizacao` e o score oficial.
- Camada de mercado por hexagono esta materializada em `data/staging/hexagonos_mercado_mapeado.parquet`.
- Residual fitness ja existe: `oferta_efetiva_disponivel` e `score_oportunidade_residual`.
- Concorrentes e Ultra ja entram no modelo espacial com raio de 1 km/2 km e decaimento linear.
- Carteira e plano curto prazo atuais ranqueiam oportunidades, mas ainda nao desenham ocupacao coordenada por clusters.
- Nova frente: transformar ranking de hexes em plano sequencial de dominio territorial por cidade/regiao.
- Dashboard e deploy continuam offline, com Parquets locais, sem API ao vivo e sem PostGIS obrigatorio.

## Objetivo do ciclo
Criar a feature **Expansao de Dominio**: algoritmo que seleciona clusters e hexes ancora dentro de cidades/regioes para expandir a Ultra de forma escalavel, controlada e protetiva, priorizando residual fitness, cobertura espacial, fortalecimento de marca e baixa canibalizacao.

## Inputs do ciclo ativo
| arquivo | uso |
| --- | --- |
| `data/staging/hexagonos_mercado_mapeado.parquet` | base completa para candidatos, coordenadas, residual, concorrencia e Ultra |
| `data/outputs/oportunidades_expansao_hibrido.parquet` | apoio para dashboard e contexto hibrido |
| `data/outputs/carteira_expansao_acionavel.parquet` | referencia da carteira M1 atual |
| `data/outputs/plano_expansao_curto_prazo.parquet` | referencia do plano executivo atual |
| `concorrentes/*.csv` | origem da oferta mapeada de grandes redes |
| `data/ultra/Ultra.csv` | pins/unidades Ultra para contexto visual |

## Artefatos esperados
| arquivo | uso |
| --- | --- |
| `docs/expansao_dominio.md` | contrato tecnico e regra executiva da feature |
| `data/outputs/plano_expansao_dominio.parquet` | output principal para consumo analitico/dashboard |
| `data/outputs/plano_expansao_dominio.csv` | leitura operacional em planilha |
| `data/reports/expansao_dominio.md` | resumo executivo por cidade/cluster |

## Blocos pendentes

### Bloco 1 - Contrato tecnico da Expansao de Dominio [x]
**Objetivo:** documentar o desenho da feature antes de codar o algoritmo.

**Escopo:**
- Criar `docs/expansao_dominio.md`.
- Definir semantica de cidade/regiao, cluster, hex ancora, residual capturado, sobreposicao, protecao de marca e fase de abertura.
- Definir parametros iniciais: H3 res7, raio de captura 2 km, distancia minima entre novas unidades, distancia minima de Ultra existente, maximo de ancoras por cidade e gates de elegibilidade.
- Definir schema esperado de `plano_expansao_dominio.parquet`.
- Registrar que a feature nao substitui M1, carteira nem plano curto prazo; ela e uma camada paralela de ocupacao espacial.
- Atualizar `CLAUDE.md` apenas com o resumo canonico do novo ciclo.

**Validacao minima:**
```bash
python -c "import pyarrow.parquet as pq; cols=set(pq.read_schema('data/staging/hexagonos_mercado_mapeado.parquet').names); req={'hex_id','uf','nome_municipio','cod_municipio','lat','lng','score_oportunidade_residual','oferta_efetiva_disponivel','sam_fitness_potencial','dist_ultra_mais_proxima_m','flag_canibalizacao_ultra_1km'}; assert req <= cols, req-cols; print('ok')"
```

**Observacoes:** Contrato criado em `docs/expansao_dominio.md`. Todos os campos obrigatorios confirmados no parquet de mercado. CLAUDE.md ja continha secao 5 alinhada; mantida sem alteracao. Validacao minima: OK.

### Bloco 2 - Nucleo de candidatos e clusters [x]
**Objetivo:** criar a base de candidatos elegiveis e agrupar hexes bons em clusters intraurbanos.

**Escopo:**
- Criar `jobs/pipelines/gerar_plano_expansao_dominio.py`.
- Ler somente colunas necessarias de `hexagonos_mercado_mapeado.parquet`.
- Filtrar candidatos por `flag_sam_fitness=True`, `oferta_efetiva_disponivel > 0`, score residual minimo configuravel, coordenadas validas e sem canibalizacao Ultra <1 km.
- Implementar clusters por adjacencia H3 dentro do mesmo `cod_municipio`, usando vizinhos H3 res7.
- Calcular metricas por cluster: `cluster_id`, `n_hex_cluster`, `residual_total_cluster`, `score_residual_max`, `score_residual_medio`, `sam_total_cluster`, `pressao_concorrencial_media`, `dist_ultra_min_cluster`.
- Criar testes unitarios com DataFrame sintetico pequeno.

**Validacao minima:**
```bash
python -m pytest -q tests/unit/test_expansao_dominio.py
python jobs/pipelines/gerar_plano_expansao_dominio.py --dry-run --cidade "Sao Paulo" --uf SP
```

**Observacoes:** Pipeline criado com funcoes `filtrar_candidatos`, `construir_clusters` (union-find H3 res7), `calcular_metricas_cluster`. 25 testes unitarios PASS. Dry-run SP: 179 candidatos em 2 clusters. Busca por cidade usa normalizacao NFKD/ASCII para lidar com acentos no parquet (ex: "São Paulo" casa com "Sao Paulo"). h3-py 4.x retorna lista em `grid_disk` — convertido para set internamente.

### Bloco 3 - Algoritmo greedy de hexes ancora [x]
**Objetivo:** selecionar uma sequencia de aberturas por cidade/cluster evitando sobreposicao e canibalizacao.

**Escopo:**
- Implementar funcao de captura residual com decaimento linear ate 2 km, alinhada ao modelo atual de concorrentes.
- Implementar selecao greedy: a cada passo escolher o hex que maximiza residual incremental capturado, qualidade do score e valor estrategico, penalizando sobreposicao com ancoras ja escolhidas.
- Aplicar distancia minima entre novas ancoras, default inicial `1.5 km`.
- Classificar `tese_dominio`: `dominar_white_space`, `abrir_com_disputa`, `proteger_corredor_ultra`, `adensar_cluster`, `monitorar`, `bloqueado_canibalizacao`.
- Gerar colunas de auditoria: `ordem_expansao_cidade`, `residual_incremental_capturado`, `residual_cluster_pos_acao`, `dist_nova_ancora_mais_proxima_m`.
- Cobrir casos de empate e cidade sem candidatos.

**Validacao minima:**
```bash
python -m pytest -q tests/unit/test_expansao_dominio.py
python jobs/pipelines/gerar_plano_expansao_dominio.py --dry-run --cidade "Sao Paulo" --uf SP --max-ancoras-cidade 5
```

**Observacoes:** Algoritmo greedy implementado com decaimento linear (2 km), distancia minima entre ancoras (default 1.5 km), desempate por score_oportunidade_residual e classificacao de tese. Funcoes: `_haversine_m`, `_haversine_array`, `classificar_tese_dominio`, `selecionar_ancoras_greedy`, `gerar_plano_dominio`. H3 res7 tem distancia ~2.5 km entre centros adjacentes (ajuste de limiar documentado nos testes). 55 testes PASS. Dry-run SP --max-ancoras-cidade 5: 179 candidatos → 5 ancoras, residual capturado ~94k.

### Bloco 4 - Materializacao nacional do plano [x]
**Objetivo:** gerar o output oficial da feature para todas as cidades elegiveis.

**Escopo:**
- Adicionar CLI ao pipeline: filtros por UF/cidade, `--top-cidades`, `--max-ancoras-cidade`, `--min-score-residual`, `--min-dist-novas-ultras-km`.
- Materializar `data/outputs/plano_expansao_dominio.parquet` e `.csv`.
- Preservar cardinalidade de candidatos durante joins auxiliares e garantir 0 duplicatas em `hex_id` recomendado por execucao.
- Criar ranking nacional e ranking por UF/cidade: `rank_dominio_brasil`, `rank_dominio_uf`, `rank_dominio_cidade`.
- Criar teste de integracao com fixtures pequenas e/ou execucao amostrada.

**Validacao minima:**
```bash
python jobs/pipelines/gerar_plano_expansao_dominio.py --top-cidades 30
python -m pytest -q tests/integration/test_expansao_dominio.py
```

**Observacoes:** Funcoes `_top_cidades_por_residual`, `adicionar_rankings` e `materializar` adicionadas ao pipeline. Rankings por residual_incremental_capturado (method=first, ascending=False). Filtro top-cidades aplica-se apenas quando `--cidade` nao e especificado. CSV com sep=";" e encoding="utf-8-sig". Validacao de hex_id duplicado/nulo antes de salvar. Execucao --top-cidades 30: 300 ancoras em 30 cidades. 19 testes de integracao PASS, 55 unitarios PASS.

### Bloco 5 - Relatorio executivo por cidade e cluster [x]
**Objetivo:** transformar o output em uma leitura executiva clara para Growth/Expansao.

**Escopo:**
- Criar `jobs/pipelines/gerar_relatorio_expansao_dominio.py`.
- Gerar `data/reports/expansao_dominio.md`.
- Reportar top cidades por residual capturado, top clusters, quantidade sugerida de ancoras, tese dominante e cautelas.
- Comparar a nova lista com `carteira_expansao_acionavel.parquet` e `plano_expansao_curto_prazo.parquet` sem alterar esses artefatos.
- Registrar limitações: concorrentes grandes mapeados, ausencia de independentes, capacidade proxy de 2500 alunos e qualidade da populacao por fonte.

**Validacao minima:**
```bash
python jobs/pipelines/gerar_relatorio_expansao_dominio.py
python -c "from pathlib import Path; p=Path('data/reports/expansao_dominio.md'); assert p.exists() and p.stat().st_size > 1000; print('ok')"
```

**Observacoes:** Script criado em `jobs/pipelines/gerar_relatorio_expansao_dominio.py`. Relatorio gerado em `data/reports/expansao_dominio.md` (5.3 kb). Secoes: sumario executivo, top 15 cidades, top 10 clusters, resumo por UF, comparativo com M1 (todas as 30 cidades do dominio ja estao na carteira; 27 no plano CP), parametros e cautelas. Nenhum artefato M1 foi alterado. Validacao minima: OK.

### Bloco 6 - Expor Expansao de Dominio no dashboard [x]
**Objetivo:** permitir explorar o plano novo no Streamlit sem recalcular nada em producao.

**Escopo:**
- Adicionar loader opcional para `plano_expansao_dominio.parquet`.
- Criar aba/subaba "Expansao de Dominio" com tabela operacional, filtros por UF/cidade/tese e KPIs de residual capturado.
- Exibir colunas essenciais: ordem, cidade, cluster, hex ancora, score residual, residual capturado, distancia Ultra, tese e ranking.
- Manter o dashboard funcional quando o parquet nao existir.
- Nao alterar mapas M1/hibrido existentes.

**Validacao minima:**
```bash
python -c "import streamlit_app; print('ok')"
python -m pytest -q tests/integration/test_streamlit_app.py
```

**Observacoes:** `load_plano_dominio` adicionado com `@st.cache_data`; retorna DataFrame vazio graciosamente quando parquet ausente. Nova aba "Expansao de Dominio" (tabs[7]) com KPIs (ancoras, cidades, UFs, residual capturado), filtros por UF/cidade/tese e tabela operacional ordenada por `rank_dominio_brasil`. `render_expansao_dominio` adicionada a `pages.py` seguindo padrao das outras paginas. 4 novos testes de integracao adicionados (mock colunas com `side_effect` em vez de `return_value` fixo para suportar chamadas com n variavel). Validacao: `import streamlit_app` OK, 33 testes de integracao PASS (31 anteriores + 4 novos, sendo 2 que existiam). Mapas M1/hibrido intactos.

### Bloco 7 - Mapa de dominio e narrativa visual [x]
**Objetivo:** visualizar as ancoras e clusters recomendados sobre os mapas existentes.

**Escopo:**
- Adicionar camada visual opcional de ancoras da Expansao de Dominio.
- Diferenciar ordem de expansao por cor/tamanho e tese por tooltip.
- Destacar cluster recomendado e residual no entorno sem alterar score nem ranking.
- Reutilizar pins Ultra e concorrentes ja existentes.
- Adicionar legenda enxuta e testes de construcao da figura.

**Validacao minima:**
```bash
python -m pytest -q tests/integration/test_streamlit_app.py
python -c "import streamlit_app; print('ok')"
```

**Observacoes:** `build_dominio_map_figure` e `render_dominio_tese_legend` adicionadas a `components.py`. Fill-color por `ordem_expansao_cidade` (cyan brilhante=1, azul=posterior); line-color por `tese_dominio` (6 cores distintas). `render_expansao_dominio` em `pages.py` ganhou secao de mapa antes da tabela, com legenda de teses, caption de contexto e suporte a `competitors_df`/`ultra_df`. `streamlit_app.py` exporta as novas funcoes e repassa os DataFrames de contexto. 2 novos testes de integracao adicionados. Total: 35 testes de integracao PASS. `import streamlit_app` OK. Mapas M1/hibrido intactos.

### Bloco 8 - Calibracao e hardening operacional [x]
**Objetivo:** estabilizar parametros para uso recorrente pela equipe.

**Escopo:**
- Centralizar parametros da feature em constantes documentadas.
- Adicionar smoke de schema para `plano_expansao_dominio.parquet`.
- Validar que nenhum output da feature altera `score_priorizacao`, `hex_score_estrutural`, carteira ou plano curto prazo.
- Testar cenarios: cidade sem candidatos, todos bloqueados por Ultra, multiplos clusters, empate de score residual, limite de ancoras por cidade.
- Atualizar `docs/expansao_dominio.md`, `CLAUDE.md` e este PRD com observacoes finais do ciclo.

**Validacao minima:**
```bash
python -m pytest -q tests/unit/test_expansao_dominio.py tests/integration/test_expansao_dominio.py tests/integration/test_streamlit_app.py
python -c "import pandas as pd; df=pd.read_parquet('data/outputs/plano_expansao_dominio.parquet'); assert df['hex_id'].notna().all(); assert not df['hex_id'].duplicated().any(); print(len(df))"
```

**Observacoes:** `DOMINIO_SCHEMA_MINIMO` e `DOMINIO_TESES_VALIDAS` centralizados em `dashboard/constants.py`; `SCHEMA_DOMINIO_OBRIGATORIO` no pipeline espelha o mesmo conjunto (validado por teste unitario). `validate_dominio_schema()` adicionada ao pipeline e chamada dentro de `materializar()`. Novos testes unitarios (8): smoke de schema, schema vs. constants, todos-bloqueados-por-Ultra, multiplos-clusters, limite-ancoras-por-cidade, guardrail de paths M1. Novos testes de integracao (3 condicionais): carteira contem score_priorizacao, plano_cp contem score_priorizacao, plano dominio nao altera scores M1. Corrigido conflito de nomes pytest (`tests/unit/test_expansao_dominio.py` x `tests/integration/test_expansao_dominio.py`) com `__init__.py` nos subdirs. Total final: 63 unitarios PASS + 84 expansao-dominio PASS + 35 streamlit PASS. `docs/expansao_dominio.md` atualizado com secao 9 (hardening).

## Backlog posterior
- Calibrar capacidade por formato de unidade Ultra e por rede concorrente quando houver dado confiavel.
- Incluir imoveis disponiveis e funil real de implantacao como restricao do plano.
- Criar cenario de budget trimestral: maximo de aberturas por UF/cidade e simulacao de cobertura.
