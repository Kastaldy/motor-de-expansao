# PRD - Guia Operacional para Agentes de IA
**Projeto:** Motor de expansao - Ultra Academia
**Ultima atualizacao:** 2026-05-20 (Bloco 13 concluido)
**Ciclo ativo:** Hardening da Analise Pontual e Padronizacao Visual de Scores (CONCLUIDO)

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
- M1 oficial permanece como gate executivo; `score_priorizacao` e o score oficial.
- Dois ciclos completos: Blocos 1-7 (Visao Executiva e Analise Pontual) e Blocos 8-13 (Hardening e Padronizacao Visual), ambos fechados em 2026-05-20.
- Dashboard com 4 abas estabilizadas: `Visao Executiva` (Ultra-only, sem hexagonos), `Mapa Territorial` (modos M1/Hibrido/Censitario/Residual/Dominio + Analise Pontual), `Expansao de Dominio`, `Carteira e Plano`.
- Analise Pontual: raio 1.6 km (~8.04 km2), populacao/renda no raio, pins de concorrentes/Ultra filtrados, tabela de hexes.
- Regra visual: todos os 4 modos quantitativos usam `score_band_to_color` (10 faixas via `RESIDUAL_SCORE_BANDS`); legenda generica `render_score_bands_legend`.
- Clique: `st.pydeck_chart` retorna centroide do hex; nota visual exibida; fallback por `lat,lng` na sidebar.
- Limitacoes registradas: centroide vs geometria real; botao direito nao suportado; cobertura censitaria parcial (UFs A/B).
- Suite de testes: 189 testes passam (1 skip).

## Historico do ciclo (todos os blocos concluidos)

| bloco | entrega |
| --- | --- |
| 1 | `docs/analise_pontual_entorno.md` criado; contrato de Visao Executiva e raio 1.6 km |
| 2 | `build_ultra_presence_map`; Visao Executiva Ultra-only sem hexagonos |
| 3 | 6 KPIs de rede/mercado e 3 graficos executivos na Visao Executiva |
| 4 | `analisar_entorno_ponto` com haversine vetorizado; retorna metricas de raio sem mutar inputs |
| 5 | UI Analise Pontual com expander, mapa 3 camadas (hexes, circulo, ponto), KPIs e coordenada copiavel |
| 6 | `st.pydeck_chart(on_select="rerun")`; `_extract_click_coord_from_selection`; `effective_pin` = clique ou busca |
| 7 | Hardening ciclo 1-7; `docs/streamlit_dashboard_m1.md` reescrito; 170 testes |
| 8 | Contrato de area 8.04 km2; regra visual 10-em-10 definida em docs |
| 9 | `score_band_to_color` e `render_score_bands_legend`; M1/Hibrido/Censitario/Residual padronizados |
| 10 | `pop_total_raio` e `renda_per_capita_media_raio` com fallback por fonte; ponderacao por pop |
| 11 | `build_analise_pontual_map` com `IconLayer` de concorrentes/Ultra filtrados por raio |
| 12 | Decisao tecnica: pydeck com centroide mantido; folium/componente descartados; nota visual |
| 13 | Hardening final; docs atualizados; 189 testes passam (1 skip) |


## Backlog posterior
- Selecao multi-ponto ou multi-hex para montar cenarios de expansao.
- Exportacao da analise pontual para CSV/PDF.
- Geocodificacao offline/online de endereco, caso aprovada dependencia externa ou base local.
- Relatorio semanal de movimentacao concorrencial com snapshots, deltas por rede/cidade e impacto nas oportunidades.
- Cenarios salvos por usuario, comentarios e historico de decisao, caso o dashboard evolua para produto web interno.
