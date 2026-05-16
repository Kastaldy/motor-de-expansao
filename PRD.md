# PRD - Guia Operacional para Agentes de IA
**Projeto:** Motor de expansao - Ultra Academia
**Ultima atualizacao:** 2026-05-15
**Ciclo ativo:** Penetracao, TAM/SAM e oferta efetiva por hexagono

## Instrucoes obrigatorias
1. Ler `CLAUDE.md` antes de qualquer acao.
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
- Ciclo de handoff/deploy e refatoracao segura concluido em 2026-05-14.
- M1 oficial recalculado em 2026-05-15 para refletir `populacao_proxy = pop_total`; pesos `renda=0.40` e `pop=0.60` seguem inalterados.
- Camada censitaria completa regenerada em 2026-05-15 com `v0001` corrigido; cadeia rematerializada: hibrido, carteira e plano.
- Estrutura atual: pacote interno em `src/motor_expansao/`; entrypoints legados preservados na raiz.
- Dashboard Streamlit roda offline com Parquets locais; busca por coordenada centraliza e destaca o hex corretamente.
- Busca por coordenada ja exibe tooltip completo no hex destacado, inclusive fora do recorte filtrado.
- `data/ultra/Ultra.csv` contem unidades Ultra com coordenadas e 1 linha inicial de metadado.
- `data/ultra/dados_academias.xlsx` contem dados de algumas unidades: populacao/densidade GeoFusion em raio de 1 km, faturamento, alunos pagantes/agregadores e alunos totais.
- A nova frente deve usar esses dados reais para calibrar penetracao, padroes de desempenho e potencial residual de mercado por hexagono.

## Inputs do ciclo ativo
| arquivo | uso |
| --- | --- |
| `data/ultra/Ultra.csv` | coordenadas das unidades Ultra |
| `data/ultra/dados_academias.xlsx` | performance real e dados GeoFusion das unidades |
| `data/staging/hexagonos_mercado_mapeado.parquet` | camada de mercado atual por hexagono |
| `data/outputs/oportunidades_expansao_hibrido.parquet` | base hibrida/censitaria para joins e contexto |
| `concorrentes/*.csv` | oferta mapeada de grandes redes concorrentes |

## Artefatos minimos do dashboard
Manter em `data/outputs/` no ambiente da equipe ou montados como volume na VPS:

| arquivo | uso |
| --- | --- |
| `hexagonos_brasil_dashboard.parquet` | base oficial M1, KPIs, ranking e mapa executivo |
| `oportunidades_expansao_hibrido.parquet` | enriquecimento hibrido/censitario e filtros combinados |
| `carteira_expansao_acionavel.parquet` | aba de carteira operacional |
| `plano_expansao_curto_prazo.parquet` | aba de plano curto prazo |

Validar com:

```bash
python scripts/check_artifacts.py
```

## Comandos de referencia

Setup local:
```bash
python -m pip install -e ".[dev]"
copy .env.example .env
python -m streamlit run streamlit_app.py
```

Suite rapida:
```bash
python -m pytest -q tests/integration/test_streamlit_app.py tests/integration/test_carteira_plano_nacional.py
python -c "import streamlit_app; print('ok')"
```

Suite mercado:
```bash
python -m pytest -q tests/integration/test_modelo_mercado_hexagonos.py
```

Suite completa:
```bash
python -m pytest -q
```

## Docs de referencia
- `README.md`: quickstart, testes, deploy e mapa de docs.
- `docs/handoff_repositorio.md`: contrato de handoff e checklist para a equipe.
- `docs/artefatos_dados.md`: manifesto de dados e politica de versionamento.
- `docs/deploy_vps_streamlit.md`: runbook Streamlit/Docker para VPS.
- `docs/streamlit_dashboard_m1.md`: governanca e uso do dashboard.
- `docs/modelo_mercado_hexagonos.md`: contrato tecnico da camada de mercado.

## Blocos pendentes

### Bloco 1 - Normalizar unidades Ultra com performance e coordenadas [x]
**Objetivo:** criar uma base auditavel que una coordenadas, alunos e faturamento das unidades Ultra.

**Escopo:**
- Ler `data/ultra/dados_academias.xlsx` e padronizar unidade, cidade/UF, populacao GeoFusion, densidade GeoFusion, faturamento, `ativos_pag`, agregadores e `alunos_total`.
- Ler `data/ultra/Ultra.csv` com `skiprows=1`, `sep=";"`, `encoding="latin-1"` e coordenadas com virgula decimal.
- Fazer match entre as duas bases por nome normalizado e UF/cidade, preservando linhas nao casadas com status explicito.
- Gerar `hex_id_res7` por coordenada valida.
- Materializar `data/staging/unidades_ultra_performance.parquet`.

**Colunas minimas esperadas:**
`unidade`, `uf`, `cidade`, `lat`, `lng`, `hex_id_res7`, `pop_geofusion_1km`, `densidade_geofusion_1km_km2`, `faturamento`, `ativos_pag`, `alunos_gympass`, `alunos_totalpass`, `agregadores`, `alunos_total`, `ticket_medio_aluno`, `status_match_coord`.

**Validacao minima:**
rodar testes novos ou smoke script que confirme leitura, coordenadas validas, taxa de match e ausencia de duplicidade critica por unidade.

**Observacoes:** Concluido em 2026-05-15. Pipeline `jobs/pipelines/normalizar_unidades_ultra.py` materializa `data/staging/unidades_ultra_performance.parquet` com 54 unidades da planilha de performance; 53 casaram coordenada/`hex_id_res7` e `CAMPO LIMPO - SP` ficou `sem_coord` por ausencia de ponto correspondente no CSV. Validado com `python jobs\pipelines\normalizar_unidades_ultra.py` e `python -m pytest -q tests\integration\test_normalizar_unidades_ultra.py tests\integration\test_modelo_mercado_hexagonos.py::test_ultra_loader_lida_com_metadado_e_encoding_legacy`.

### Bloco 2 - Calcular penetracao Ultra por hexagono [x]
**Objetivo:** medir a penetracao de mercado de cada unidade Ultra contra a populacao do hex onde ela esta localizada.

**Escopo:**
- Join de `unidades_ultra_performance.parquet` com a base de hexagonos por `hex_id_res7 = hex_id`.
- Usar populacao granular do hex quando disponivel (`pop_total_setor_2022` elegivel); fallback para `populacao_proxy`.
- Criar `pop_hex_base` e `fonte_pop_hex_base` para auditoria.
- Calcular `penetracao_ultra_alunos_total`, `penetracao_ultra_pagantes`, `receita_por_habitante_hex`, `ticket_medio_aluno`, `alunos_por_m2` quando `metragem` existir.
- Materializar `data/staging/unidades_ultra_performance_hex.parquet`.

**Validacao minima:**
testar divisao por zero/nulos, consistencia de fontes de populacao e ranking das unidades por penetracao.

**Observacoes:** Concluido em 2026-05-15. Pipeline `jobs/pipelines/calcular_penetracao_ultra_hex.py` materializa `data/staging/unidades_ultra_performance_hex.parquet` com 54 unidades preservadas; 49 casaram com `hex_id` da camada de mercado, 28 usam `censo_2022_hex`, 21 usam `m1_municipal_proxy`, 4 ficam `hex_nao_encontrado` e `CAMPO LIMPO - SP` fica `sem_hex_id_res7`. Colunas novas: `pop_hex_base`, `fonte_pop_hex_base`, penetracoes Ultra, receita por habitante, `alunos_por_m2` e rankings. Validado com `python jobs\pipelines\calcular_penetracao_ultra_hex.py` e `python -m pytest -q tests\integration\test_calcular_penetracao_ultra_hex.py`.

### Bloco 3 - Comparar GeoFusion 1km vs populacao do hex [x]
**Objetivo:** comparar a leitura GeoFusion de raio 1 km com a leitura H3 sem misturar areas diferentes.

**Escopo:**
- Tratar GeoFusion como raio de 1 km, area aproximada `3.14 km2`.
- Calcular `densidade_geofusion_1km_calc = pop_geofusion_1km / 3.14`.
- Calcular area real do H3 por `h3.cell_area(hex_id, unit="km^2")` e `densidade_hex_km2 = pop_hex_base / area_hex_km2`.
- Comparar principalmente densidade: `delta_densidade_hex_vs_geofusion`, `ratio_densidade_hex_geofusion`.
- Manter a diferenca bruta de populacao apenas como diagnostico secundario, nao como KPI principal.
- Gerar tabela/report em `data/reports/validacao_geofusion_vs_hex.md`.

**Validacao minima:**
reportar unidades sem GeoFusion, sem coordenada ou sem populacao de hex; garantir que as areas usadas estejam registradas no output.

**Observacoes:** Concluido em 2026-05-15. Pipeline `jobs/pipelines/comparar_geofusion_vs_hex.py` gera `data/reports/validacao_geofusion_vs_hex.md`. Base comparavel: 49/54 unidades (todas tem GeoFusion; 1 sem coord: CAMPO LIMPO SP; 4 sem pop hex: PRAIA GRANDE, POA BARRA SUL, CABO FRIO, GUARUJA). Achado principal: unidades com `censo_2022_hex` mostram ratios realistas (mediana 0.90, range 0.44-1.43); unidades com `m1_municipal_proxy` mostram ratios inflados (populacao municipal total dividida por area de um unico hex) — comportamento esperado e documentado. Areas registradas: GeoFusion=3.14 km2 (constante), H3 res7 min=4.4/max=5.8/mediana=5.5 km2. Validado com 12/12 testes em `tests/integration/test_comparar_geofusion_vs_hex.py`.

### Bloco 4 - Identificar padroes das melhores e piores unidades [x]
**Objetivo:** entender o que os hexes das unidades com melhor e pior resultado tem em comum.

**Escopo:**
- Classificar desempenho por mais de uma lente: alunos totais, faturamento, penetracao, receita por habitante, ticket medio e pagantes.
- Separar top/bottom por percentis ou tercis, com regra documentada.
- Rodar correlacoes Pearson/Spearman entre desempenho e variaveis de hex: populacao, densidade, renda, score M1, score hibrido, concorrentes, distancia de concorrentes, white space, densidade GeoFusion e diferenca GeoFusion vs hex.
- Alem das correlacoes, procurar padroes interpretaveis: faixas de densidade, renda, concorrencia, tamanho da unidade, agregadores, outliers e combinacoes recorrentes.
- Gerar `data/reports/validacao_penetracao_ultra_hex.md` com tabelas, achados e cautelas.

**Validacao minima:**
registrar tamanho da amostra, metricas com n valido, outliers tratados e conclusoes que nao podem ser inferidas por baixa amostra.

**Observacoes:** Concluido em 2026-05-15. Pipeline `jobs/pipelines/validar_penetracao_ultra_hex.py` gera `data/reports/validacao_penetracao_ultra_hex.md` com 54 unidades, classificacao top/bottom por tercis para 6 lentes de desempenho, 84 correlacoes Pearson/Spearman validas e 9 outliers IQR mantidos na analise. Cautelas registradas: amostra pequena, 21 unidades com populacao municipal proxy, e correlacoes de penetracao/receita por habitante com `pop_hex_base` lidas como diagnostico de denominador, nao causalidade. Validado com `python jobs\pipelines\validar_penetracao_ultra_hex.py`.

### Bloco 5 - Feature TAM/SAM e oferta efetiva residual nos hexagonos [x]
**Objetivo:** adicionar uma camada de potencial absoluto para mapear hexes com alta demanda fitness e mercado residual relevante.

**Escopo:**
- Implementar em `jobs/pipelines/calcular_colunas_mercado.py`, preservando as colunas atuais.
- Usar os estudos dos blocos 2 a 4 para calibrar uma taxa inicial de aderencia fitness/penetracao esperada.
- Criar `tam_populacao_hex = pop_hex_base` e `tam_fitness_potencial = pop_hex_base * taxa_fitness_calibrada`.
- Criar `sam_fitness_potencial` aplicando gates operacionais ja existentes: viabilidade, municipio priorizado, renda/densidade quando documentado e restricao de canibalizacao Ultra.
- Estimar consumo de mercado por grandes redes mapeadas: concorrentes grandes com capacidade default documentada (ex.: 2.500 alunos por unidade ate calibracao melhor) e unidades Ultra com alunos reais quando disponiveis.
- Criar `oferta_consumida_mercado_estimada`, `oferta_consumida_ultra_real`, `oferta_efetiva_disponivel = max(sam_fitness_potencial - oferta_consumida_mercado_estimada, 0)`.
- Criar metricas de leitura: `penetracao_fitness_mercado_estimada`, `share_ultra_estimado_hex`, `score_oportunidade_residual`.
- Atualizar `docs/modelo_mercado_hexagonos.md` com a semantica de TAM, SAM e oferta efetiva residual.

**Validacao minima:**
testes de contrato garantindo que o M1 oficial nao mudou, colunas novas existem, valores nao ficam negativos e exemplos manuais batem com a regra: `10k hab -> potencial -> consumo concorrente -> residual`.

**Observacoes:** Concluido e revisado em 2026-05-15. Logica corrigida em relacao a versao inicial: (1) `taxa_fitness_calibrada` nao e mais um valor fixo de `0.045` — e calibrada em runtime por `calibrar_taxa_fitness_mercado(df)` como mediana de `(n_total_academias_2km * 2000) / pop_hex_base` nos hexes com academias; resultado com 28 redes e **20%**; fallback `TAXA_FITNESS_MERCADO_FALLBACK = 0.10` quando base insuficiente para calibracao. (2) `oferta_efetiva_disponivel` agora desconta `oferta_consumida_total_estimada = oferta_consumida_mercado_estimada + oferta_consumida_ultra_estimada` — Ultra propria tambem entra no calculo de consumo (alunos reais quando disponivel, proxy `n_unidades_ultra_2km * 2500` caso contrario). (3) Cobertura de concorrentes expandida de 3 redes (1.684 unidades) para **28 redes** (3.179 unidades validas) via auto-discovery de todos os `unidades_*.csv` de `concorrentes/`. Novas colunas: `taxa_fitness_mercado_calibrada`, `oferta_consumida_ultra_estimada`, `oferta_consumida_total_estimada`. `penetracao_fitness_mercado_estimada` usa `oferta_consumida_total_estimada` como numerador. Parquet regenerado com 1.532.645 linhas; soma `oferta_efetiva_disponivel` pos-Bloco 8: 3.17M alunos (correto apos correcao de inflate de populacao).

### Bloco 6 - Tooltip completo para hex pesquisado por coordenada [x]
**Objetivo:** fazer o hover do hex destacado pela busca por coordenada exibir os mesmos dados de um hex normal.

**Escopo:**
- Ajustar `src/motor_expansao/dashboard/components.py`: `_build_search_hex_layer` deve receber os campos de tooltip do hex pesquisado quando eles existirem.
- Reaproveitar `_apply_hex_tooltip_fields` para montar o payload do destaque, mantendo o fallback atual apenas quando o `hex_id` nao estiver na base.
- Preservar destaque amarelo, centralizacao e exibicao mesmo fora dos filtros.
- Atualizar testes em `tests/integration/test_streamlit_app.py` e/ou `tests/unit/test_coord_search.py`.

**Validacao minima:**
teste deve confirmar que o layer de destaque possui `Habitantes`, `Renda per capita`, scores e demais linhas esperadas, nao apenas `Hex pesquisado`.

**Observacoes:** Concluido em 2026-05-15. `_build_search_hex_layer` agora recebe payload de tooltip gerado com `_apply_hex_tooltip_fields`; quando o `hex_id` existe na base, o destaque amarelo mostra o mesmo tooltip do hex normal, inclusive fora do recorte filtrado; fallback simples permanece para hex nao encontrado. Validado com `python -m pytest -q tests\integration\test_streamlit_app.py::test_build_map_figure_adiciona_layer_de_destaque_do_hex_pesquisado tests\integration\test_streamlit_app.py::test_build_map_figure_destaque_hex_aparece_mesmo_fora_dos_filtros tests\unit\test_coord_search.py` e `python -m pytest -q tests\integration\test_streamlit_app.py`.

### Bloco 8 - Corrigir base populacional do SAM/TAM e sinalizar proxy no dashboard [x]
**Objetivo:** corrigir o bug onde `populacao_proxy` (populacao total do municipio) era usada diretamente no sizing absoluto de TAM/SAM, inflando o SAM de cada hex pelo total do municipio inteiro.

**Contexto do bug diagnosticado em 2026-05-15:**
- `pop_hex_base` usava `populacao_proxy` (total municipal) como fallback para hexes sem `flag_censo_elegivel=True`, mesmo quando `pop_total_setor_2022` estava disponivel.
- Resultado: todos os hexes de um mesmo municipio recebiam SAM identico e inflado. Ex.: Rio de Janeiro (6,2M hab) -> SAM de 279k alunos por hex; Sao Paulo (11,4M) -> 515k por hex.
- O tooltip exibia `Habitantes` do censo (~30k) mas o SAM era calculado sobre o proxy municipal, criando contradicao visual direta.
- 1.816 hexes em RJ com `flag_sam=True` tinham esse conflito; 1,3M hexes no total com `pop_total_setor_2022` disponivel mas SAM usando proxy.

**Escopo — correcao do calculo (`calcular_colunas_mercado.py`):**
- Mudar a condicao de `pop_hex_base` de `flag_censo_elegivel=True AND pop_total_setor_2022.notna()` para `pop_total_setor_2022 > 0` (usar o dado censitario sempre que existir, independente do gate de densidade do modelo hibrido).
- Novo fallback quando censo nao estiver disponivel: `populacao_proxy / total_hex_municipio` (coluna `total_hex_municipio` ja existe no parquet) em vez do total bruto municipal.
- Atualizar `fonte_pop_hex_base` para refletir a nova logica: `censo_2022_setor` quando usar `pop_total_setor_2022`; `m1_municipal_proxy_per_hex` quando usar o fallback dividido.
- Apos recalcular o staging, rodar `enriquecer_outputs_residual_mercado.py` e `gerar_carteira_acionavel.py` para propagar os novos valores.

**Escopo — sinalizacao no dashboard (`components.py` e tooltip):**
- No tooltip dos hexes, exibir SAM/TAM com sufixo `(est. proxy)` quando `fonte_pop_hex_base` for `m1_municipal_proxy_per_hex`.
- Na aba Carteira, adicionar coluna ou badge visual indicando confiabilidade do sizing absoluto.

**Restricoes:**
- Nao alterar `score_priorizacao`, `hex_score_estrutural` nem rankings oficiais M1.
- `flag_censo_elegivel` segue intocado; mudanca e somente na condicao de `pop_hex_base` para sizing absoluto.
- Testes de contrato de schema devem continuar passando; valores numericos de SAM/TAM vao mudar — atualizar fixtures/expects nos testes afetados.

**Validacao minima:**
- Confirmar que nenhum hex tem `sam_fitness_potencial > populacao_proxy / total_hex_municipio * 0.05` para hexes proxy.
- Confirmar que hexes com `pop_total_setor_2022` disponivel usam esse valor como `pop_hex_base`.
- Smoke do dashboard: hex de RJ com censo disponivel deve mostrar SAM coerente com os `Habitantes` exibidos no tooltip.
- `python -m pytest -q tests/integration/test_modelo_mercado_hexagonos.py tests/integration/test_carteira_plano_nacional.py tests/integration/test_streamlit_app.py`

**Observacoes:** Concluido em 2026-05-15. `calcular_colunas_mercado.py` corrigido: `pop_hex_base` agora usa `pop_total_setor_2022` para 1.302.296 hexes (antes apenas 850 via `flag_censo_elegivel`); fallback `populacao_proxy / total_hex_municipio` para 230.349 hexes restantes; labels atualizados para `censo_2022_setor` e `m1_municipal_proxy_per_hex`. `oferta_efetiva_disponivel` total caiu de 1.27B para 3.17M alunos (correto — eliminado inflate por populacao municipal bruta). Dashboard sinaliza `(est. proxy)` no tooltip do SAM quando fonte e proxy. `fonte_pop_hex_base` adicionada as map_columns de ambos os mapas. Propagado via `enriquecer_outputs_residual_mercado.py` e `gerar_carteira_acionavel.py`. 270/270 testes passando.

## Backlog posterior
- Hardening operacional da VPS: HTTPS/proxy reverso, autenticacao ou VPN, monitoramento de uptime.
- Limpeza assistida dos diretorios temporarios antigos com permissao negada em `fixtures/`.
- Avaliar atualizacao da carteira/plano apos estabilizar a nova camada de TAM/SAM/oferta residual.
### Bloco 7 - Expor oferta residual nos parquets e dashboard [x]
**Objetivo:** propagar as colunas de TAM/SAM fitness e residual absoluto para os parquets principais e permitir ranquear os melhores hexes/ofertas no dashboard.

**Escopo:**
- Enriquecer `oportunidades_expansao_hibrido.parquet`, `carteira_expansao_acionavel.parquet` e `plano_expansao_curto_prazo.parquet` a partir de `data/staging/hexagonos_mercado_mapeado.parquet`, preservando `score_priorizacao` e rankings M1.
- Carregar no Streamlit `sam_fitness_potencial`, `oferta_efetiva_disponivel`, `score_oportunidade_residual`, `share_ultra_estimado_hex` e consumo estimado/Ultra real.
- Adicionar esses campos ao tooltip/legenda dos hexagonos e a filtros/ordenacao da aba de carteira para ranquear por oportunidade residual, com quartis apenas como apoio visual.

**Validacao minima:** testes de contrato dos parquets enriquecidos, smoke do dashboard/import Streamlit e teste garantindo que ranking oficial M1 segue preservado.

**Observacoes:** Concluido em 2026-05-15. Novo pipeline `jobs/pipelines/enriquecer_outputs_residual_mercado.py` propaga TAM/SAM fitness, consumo estimado, Ultra real, `oferta_efetiva_disponivel`, `score_oportunidade_residual`, `share_ultra_estimado_hex` e `quartil_oportunidade_residual` para `oportunidades_expansao_hibrido.parquet`, carteira e plano sem alterar `score_priorizacao` nem ranks oficiais. `gerar_carteira_acionavel.py` tambem anexa residual a partir do staging ao regenerar a carteira; o plano herda as colunas. Dashboard carrega os campos, mostra residual no tooltip dos mapas, legenda auxiliar, filtro de quartil e ordenacao opcional por oportunidade residual na aba Carteira; ordenacao padrao segue M1. Parquets materializados: hibrido 1.532.645 linhas, carteira 4.892, plano 267, todos com cobertura residual 100%. Validado com `python jobs\pipelines\enriquecer_outputs_residual_mercado.py`, `python jobs\pipelines\gerar_carteira_acionavel.py`, `python jobs\pipelines\gerar_plano_expansao_curto_prazo.py`, checagem de schema/somas dos 3 parquets e `python -m pytest -q tests\integration\test_carteira_plano_nacional.py tests\integration\test_streamlit_app.py tests\integration\test_modelo_mercado_hexagonos.py`.
