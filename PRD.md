# PRD - Guia Operacional para Agentes de IA
**Projeto:** Motor de expansao - Ultra Academia
**Ultima atualizacao:** 2026-05-25
**Ciclo ativo:** Nenhum bloco pendente. Proximo ciclo deve ser planejado a partir do backlog.

## Instrucoes obrigatorias
1. Ler `CLAUDE.md`, `README.md` e este PRD antes de qualquer acao.
2. Tratar `CLAUDE.md`, `config.py` e este PRD como fontes de verdade operacional.
3. Executar apenas o proximo bloco cujo cabecalho esteja com `[ ]`; se nao houver bloco pendente, nao iniciar backlog sem novo planejamento.
4. Antes de editar, ler os arquivos reais envolvidos e rodar `git status --short`.
5. Nao reverter nem sobrescrever mudancas existentes sem aprovacao explicita.
6. Atualizar `CLAUDE.md` e `PRD.md` se mudar regra, target, semantica de coluna, fluxo ou decisao relevante.
7. Se houver ambiguidade entre codigo e documentacao, corrigir primeiro a documentacao e depois o codigo.
8. Nao encerrar bloco sem editar arquivo, registrar observacoes e rodar validacao minima.
9. Tentar manter `CLAUDE.md` e `PRD.md` com no maximo `200` linhas.
10. Quando um ciclo fechar, consolidar o historico em `Estado atual` e substituir blocos antigos pelo backlog ativo.
11. Nenhum ciclo pode alterar `score_priorizacao`, `hex_score_estrutural` nem artefatos oficiais do M1 sem aprovacao explicita.
12. Multi-hex, consumo fitness, dominio hibrido e relatorio censitario sao camadas operacionais paralelas ao M1.
13. Prompt operacional padrao para outros agentes: `PROMPT_PRD.md`.

## Estado atual
- M1 oficial permanece como gate executivo; `score_priorizacao` e o score oficial.
- Dashboard com 4 abas: `Visao Executiva`, `Mapa Territorial`, `Expansao de Dominio`, `Carteira e Plano`.
- Performance: o app carrega so a particao `uf=XX` do dataset enriquecido materializado (`hexagonos_dashboard_enriquecido/`), renderiza so a aba ativa por rerun e usa fonte de mapa enxuta. Detalhe em `data/reports/perf_baseline_dashboard.md`.
- Analise Pontual H3: raio 1.6 km (~8.04 km2), populacao/renda no raio, pins de concorrentes/Ultra filtrados; clique retorna centroide do hex; fallback por `lat,lng` na sidebar.
- Relatorio Pontual Censitario 1.5 km: feature complementar no expander do `Mapa Territorial`, usando geometria real de setores IBGE 2022, intersecao setor x circulo, mapa PNG offline e export CSV/PDF em memoria.
- Base geo censitaria: `jobs/pipelines/materializar_setores_censitarios_geo.py` materializa `data/outputs/setores_censitarios_2022_geo/uf=XX/cod_municipio=NNNNNNN/part-000.parquet` com `geometry_wkb`, bbox, area metrificada, densidade e score setorial paralelo. **Cobertura atual: 27 UFs, 5.571 municipios, 468.099 setores (~1,17 GB).** RR tem menor cobertura de renda (65,8%) por supressao IBGE.
- Motor censitario: `analisar_ponto_censitario_setores` usa CRS metrico local, calcula `area_intersecao_m2`, `peso_area_setor`, populacao/renda/score ponderados e pins por distancia real. Metodo: `setor_censitario_intersecao_area_1p5km`.
- UI/export censitario: `render_relatorio_pontual_censitario`, `render_mapa_censitario_estatico_png` e `censo_report.py`; raio fixo 1.5 km, lazy load/cache por `uf` + `cod_municipio`, mensagem clara quando a base geo nao existe.
- Cenario Multi-Hex: selecao via clique/busca/lista; agregador retorna pop, renda ponderada, residual, SAM, consumo concorrentes/Ultra/total, concorrentes, presenca Ultra e scores medio/max.
- Dominio Hibrido: `score_dominio_hibrido = clip(0.60*score_setor_2022_calibrado + 0.40*score_oportunidade_residual, 0, 100)` com fallback para componente unico.
- Consumo fitness padronizado: `Consumo Conc. (est.)`, `Consumo Ultra (real)` e `Consumo Total Instalado` aparecem em tooltips, analises pontuais e tabelas quando as colunas existem.
- Regra visual: modos quantitativos usam `score_band_to_color` em faixas de 10 pontos via `RESIDUAL_SCORE_BANDS`.
- Limitacoes: selecao H3 por centroide, colunas opcionais exibem `-`, relatorio censitario com distribuicao intrassetor aproximada por area, RR com cobertura de renda reduzida (supressao IBGE).

## Historico consolidado
- Blocos 1-13 concluidos em 2026-05-20: Visao Executiva Ultra-only, Analise Pontual de Entorno, clique por centroide, mapa com pins, regua visual 10-em-10 e hardening.
- Blocos 14-19 concluidos em 2026-05-21: contrato multi-hex, agregador, UI multi-hex, dominio hibrido censitario-residual, consumo fitness padronizado e handoff.
- Ciclo `Performance e Refatoracao do Dashboard` concluido em 2026-05-22: baseline/harness, dataset enriquecido particionado por UF, carga lazy, render lazy, fonte de mapa enxuta e fechamento com 509 passed, 1 skipped.
- Ciclo `Relatorio Pontual Censitario 1.5 km` concluido em 2026-05-22: contrato tecnico, base geo otimizada, motor setor x circulo, mapa PNG offline, export CSV/PDF em memoria, UI Streamlit e governanca final.

## Ciclo concluido: Relatorio Pontual Censitario 1.5 km
Objetivo concluido: criar subsistema complementar ao H3 atual para analise local por coordenada usando geometria real de setores censitarios IBGE 2022, raio fixo de 1.5 km, intersecao geometrica, mapa censitario e export PDF/CSV.

Guardrails preservados:
- Nao altera `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano dominio ou artefatos oficiais do M1.
- Nao depende de API ao vivo no dashboard.
- Nao carrega shapefile nacional a cada clique; usa artefato otimizado por UF/municipio.
- Diferencia H3 area-weighted de setor censitario real.
- PDF exibe metodologia e limites; nao promete precisao de lote/rua.

Blocos concluidos:
- Bloco 1: contrato tecnico e inventario em `docs/relatorio_pontual_censitario.md`.
- Bloco 2: pipeline `jobs/pipelines/materializar_setores_censitarios_geo.py` e relatorio `data/reports/relatorio_pontual_censitario_base_geo.md`.
- Bloco 3: motor puro `src/motor_expansao/dashboard/censo_point.py`.
- Bloco 4: mapa PNG offline `src/motor_expansao/dashboard/censo_map.py`.
- Bloco 5: CSV/PDF em memoria `src/motor_expansao/dashboard/censo_report.py`.
- Bloco 6: UI no Streamlit com lazy load/cache e baseline simples DF/Brasilia.
- Bloco 7: fechamento, documentacao e governanca; `CLAUDE.md`, `README.md`, `docs/streamlit_dashboard_m1.md` e este PRD atualizados.

Observacoes do fechamento:
- Semantica final consolidada: relatorio censitario e paralelo ao M1 e complementa a Analise Pontual H3.
- Artefato geo municipal e opcional; quando ausente, a UI informa indisponibilidade e nao tenta carregar shapefile nacional.
- Dependencias diretas do ciclo: `geopandas` para materializacao/geo e `pillow` para mapa/PDF; ja registradas no `pyproject.toml`.
- Validacao do Bloco 7: suite minima censitaria + `test_streamlit_app.py` com 160 passed; import `streamlit_app` ok; suite completa com 526 passed, 1 skipped e 9 warnings conhecidos.

Correcao e expansao pos-fechamento (2026-05-25):
- Bug corrigido: `cod_municipio` ausente do dataset M1 impedia identificacao de UF/municipio. Correcao: adicionado a `censo_extra_cols`+`OPTIONAL_DATASET_COLUMNS`; nova funcao `resolve_cod_municipio_from_geo_dir` como fallback via diretorio geo; `censo_geo_dir: Path` propagado ate `_resolve_censo_context`. Dataset enriquecido (`hexagonos_dashboard_enriquecido/`) regravado com 1,53 M linhas incluindo `cod_municipio`.
- Base geo materializada para Brasil completo: 27 UFs via `materializar_setores_censitarios_geo.py --uf ALL` (468.099 setores, 5.571 municipios, ~1,17 GB). Relatorio Pontual Censitario agora funciona para qualquer coordenada urbana do Brasil.
- Validacao: 526 passed, 1 skipped (baseline mantido).

## Backlog posterior
- Refatoracao completa do repositorio (proxima etapa de planejamento).
- Limpar leftovers (`data/outputs/*.tmp.parquet`, diretorio `tmp_codex_runtime/`) com aprovacao explicita quando envolver remocao.
- Avaliar `hex_id` como `category` apenas com benchmark, pois e chave de join.
- Avaliar `st.fragment` dedicado para interacoes do mapa caso o render lazy de abas nao baste.
- Evolucao futura: extrair o relatorio pontual censitario para API/worker separado apenas se houver concorrencia de usuarios, fila de PDFs, historico por usuario ou deploy independente.
- Geocodificacao offline/online de endereco, caso aprovada dependencia externa ou base local.
- Relatorio semanal de movimentacao concorrencial com snapshots, deltas por rede/cidade e impacto nas oportunidades.
- Cenarios salvos por usuario, comentarios e historico de decisao, caso o dashboard evolua para produto web interno.
