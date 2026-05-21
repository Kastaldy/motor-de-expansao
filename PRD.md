# PRD - Guia Operacional para Agentes de IA
**Projeto:** Motor de expansao - Ultra Academia
**Ultima atualizacao:** 2026-05-21
**Ciclo ativo:** Backlog posterior (proximo ciclo a definir)

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
12. Multi-hex, consumo fitness e dominio hibrido sao camadas operacionais paralelas ao M1.

## Estado atual
- M1 oficial permanece como gate executivo; `score_priorizacao` e o score oficial.
- Tres ciclos completos: Blocos 1-7 (Visao Executiva), 8-13 (Hardening Visual), 14-19 (Multi-Hex e Dominio Hibrido), todos fechados em 2026-05-21.
- Dashboard com 4 abas: `Visao Executiva` (Ultra-only, sem hexagonos), `Mapa Territorial` (modos M1/Hibrido/Censitario/Residual/Dominio + Analise Pontual + cenario multi-hex), `Expansao de Dominio`, `Carteira e Plano`.
- Analise Pontual: raio 1.6 km (~8.04 km2), populacao/renda no raio, pins de concorrentes/Ultra filtrados; clique retorna centroide do hex; fallback por `lat,lng` na sidebar.
- Cenario Multi-Hex: selecao via clique/busca/colar lista; hex_id copiavel via `st.code()`; botao add/remove na Analise Pontual; `parse_hex_ids_from_text` aceita qualquer separador; feedback de duplicados; `column_config TextColumn(width="large")` para hex_id integral nas tabelas.
- Dominio Hibrido: `score_dominio_hibrido = clip(0.60*score_setor_2022_calibrado + 0.40*score_oportunidade_residual, 0, 100)` com fallback para componente unico; rastreabilidade via `motivo_dominio`; `filtrar_candidatos` e `selecionar_ancoras_greedy` usam `score_dominio_hibrido`.
- Consumo fitness padronizado: `Consumo Conc. (est.)` = `oferta_consumida_mercado_estimada`; `Consumo Ultra (real)` = `oferta_consumida_ultra_real`; `Consumo Total Instalado` = soma; presentes em tooltips, Analise Pontual single/multi-hex, tabelas de Dominio e Carteira.
- Agregador `agregar_cenario_multihex` (em `data.py`): retorna 25 campos — pop, renda ponderada, residual, SAM, consumo concorrentes/Ultra/total, n_concorrentes, presenca Ultra, scores medio/max para M1/censo/residual/hibrido.
- `analisar_entorno_ponto` retorna `consumo_concorrentes_raio` e `consumo_ultra_raio` agregados dos hexes no raio.
- Regra visual: 4 modos quantitativos usam `score_band_to_color` (10 faixas via `RESIDUAL_SCORE_BANDS`); legenda `render_score_bands_legend`.
- Suite de testes: 497 passed, 1 skipped no fechamento do ciclo.
- Limitacoes registradas: selecao multi-hex por centroide (nao geometria real); colunas opcionais por artefato (exibem `-`); cobertura censitaria parcial (UFs com `qualidade_join_uf=C` filtradas automaticamente).

## Historico consolidado
- Blocos 1-13 concluidos em 2026-05-20: Visao Executiva Ultra-only, Analise Pontual de Entorno, clique por centroide (`st.pydeck_chart`), mapa com pins de concorrentes/Ultra, regua visual 10-em-10 (`RESIDUAL_SCORE_BANDS`), hardening.
- Blocos 14-19 concluidos em 2026-05-21: contrato multi-hex (docs), agregador `agregar_cenario_multihex`, UI de selecao multi-hex, Analise Pontual multi-hex unificada, UX hex_id copiavel (`parse_hex_ids_from_text`), dominio hibrido censitario-residual (`score_dominio_hibrido`), consumo fitness padronizado em todo o app, hardening e handoff.

## Backlog posterior
- Exportacao da analise pontual para CSV/PDF.
- Geocodificacao offline/online de endereco, caso aprovada dependencia externa ou base local.
- Relatorio semanal de movimentacao concorrencial com snapshots, deltas por rede/cidade e impacto nas oportunidades.
- Cenarios salvos por usuario, comentarios e historico de decisao, caso o dashboard evolua para produto web interno.
