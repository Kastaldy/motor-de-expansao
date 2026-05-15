# PRD - Guia Operacional para Agentes de IA
**Projeto:** Motor de expansao - Ultra Academia
**Ultima atualizacao:** 2026-05-14
**Ciclo ativo:** Handoff, refatoracao segura e preparacao VPS fechados

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

## Estado atual
- Ciclo de handoff/deploy e refatoracao segura concluido em 2026-05-14.
- Repositorio preparado para equipe: Streamlit offline, Docker de producao e docs de VPS mantidos.
- M1 oficial preservado: `score_priorizacao`, `hex_score_estrutural`, pesos `renda=0.40` e `pop=0.60` nao foram alterados.
- Artefatos oficiais recalculados em 2026-05-12 seguem como base vigente; validacao final desta fase rodou contra os arquivos locais existentes.
- Branch historico `codex-dashboard-m1-streamlit` permanece apenas como historico; mudancas anteriores foram promovidas para `main` em 2026-05-14.
- Estrutura nova: pacote interno em `src/motor_expansao/` com `dashboard`, `core`, `data` e `pipelines/m1`.
- Entrypoints legados preservados na raiz: `streamlit_app.py`, `base_h3_brasil.py`, `hex_enrichment.py`, `fase1_bi_exports.py`.
- Arquivos fora do deploy inicial foram concentrados em `fora_primeira_fase/`: API/PostGIS, M2/M3, pesquisas, Power BI e testes associados.
- Testes reorganizados em `tests/unit/`, `tests/integration/` e `tests/contracts/`; coleta oficial em `pyproject.toml`.
- CI rapido aponta para os novos caminhos de testes.
- Diretorios temporarios antigos em `fixtures/` seguem com alguns avisos de permissao no `git status`; nao foram removidos sem aprovacao.

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

Suite M1:
```bash
python -m pytest -q tests/integration/test_base_h3_brasil.py tests/integration/test_hex_enrichment_brasil.py tests/integration/test_fase1_bi_exports.py tests/contracts/test_fontes_gratuitas.py
```

Suite completa:
```bash
python -m pytest -q
```

Deploy VPS:
```bash
python scripts/check_artifacts.py
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
curl -fsS http://127.0.0.1:8501/_stcore/health
```

Recalculo analitico M1, fora do deploy Streamlit inicial:
```bash
python base_h3_brasil.py
python hex_enrichment.py --brasil
python fase1_bi_exports.py
```

## Docs de referencia
- `README.md`: quickstart, testes, deploy e mapa de docs.
- `docs/handoff_repositorio.md`: contrato de handoff e checklist para a equipe.
- `docs/artefatos_dados.md`: manifesto de dados e politica de versionamento.
- `docs/deploy_vps_streamlit.md`: runbook Streamlit/Docker para VPS.
- `docs/streamlit_dashboard_m1.md`: governanca e uso do dashboard.
- `docs/modelo_mercado_hexagonos.md`: contrato tecnico da camada de mercado.

## Blocos concluidos

### Ciclo anterior - Handoff, refatoracao segura e preparacao VPS [x]
**Concluido:** 2026-05-14
- Blocos 1 a 6 fechados: diagnostico, higiene segura, pacote interno, extracao do dashboard, isolamento do M1, pipelines/testes e handoff.
- Validacao final registrada: `scripts/check_artifacts.py`, suite completa com `215 passed, 4 warnings` e import smoke dos entrypoints.
- Historico operacional consolidado em `Estado atual`; detalhes tecnicos permanecem no git e nos docs de referencia.

## Blocos pendentes

### Bloco 1 - Regua populacional 5k para mercado/dashboard [x]
**Concluido:** 2026-05-14

**Observacoes:**
- `POP_MIN_ACIONAVEL = 5_000` em `dashboard/constants.py`.
- `derive_pop_cut_columns` e `build_pop_cut_lookup` em `src/motor_expansao/dashboard/data.py`; chamadas dentro de `enrich_dashboard_data`.
- Fonte preferencial: `pop_total_setor_2022` (quando `confianca_geografica=granular`); fallback: `populacao_proxy`; ausente: `flag_pop_min_5k=False`.
- Corte aplicado nas abas Carteira e Plano via join por `hex_id` em `render_carteira_expansao`/`render_plano_expansao`; mapa M1 principal nao filtrado (guardrail preservado).
- Ajuste visual pendente: hex abaixo de `5.000` habitantes nao pode continuar verde/como oportunidade no mapa; tratar no proximo bloco.
- `pop_total_setor_2022` adicionado ao merge do hybrid em `enrich_dashboard_data` para que dado censitario chegue ao lookup.
- Bug corrigido em `components.py`: `pd.Series(dtype=float)` como default causava UFuncTypeError ao concatenar strings; corrigido com `pd.Series(pd.NA, index=map_df.index, dtype="Float64")`.
- Suite: `28 passed` em `tests/unit/test_pop_cut.py` + `tests/integration/test_streamlit_app.py`; smoke test `import streamlit_app` ok.

### Bloco 2 - Busca direta por coordenada/pin [x]
**Concluido:** 2026-05-14

**Observacoes:**
- `parse_coordinate_input` e `lookup_hex_by_coord` em `src/motor_expansao/dashboard/data.py`; bbox Brasil hardcoded.
- `render_coord_search_sidebar` e `render_hex_search_result` em `src/motor_expansao/dashboard/pages.py`; widget na sidebar, card de detalhe acima das abas.
- `_build_search_pin_layer` em `components.py`; `build_map_figure` e `build_hybrid_map_figure` aceitam `search_pin: tuple[float, float] | None` e centralizam o mapa no pin com `zoom=10.0`.
- Quando hex nao encontrado na base: mensagem clara. Quando fora do recorte de filtros ou descartado pela regua de 5k hab: aviso com motivo. Quando visivel: badge de sucesso.
- Ajuste visual pendente: a busca precisa desenhar/destacar o hex pesquisado no mapa, nao apenas mostrar card numerico; tratar no proximo bloco.
- Testes: `tests/unit/test_coord_search.py` (21 cases) + 3 novos em `test_streamlit_app.py`; 53 passed, 0 failed.

### Bloco 3 - Correcoes visuais da regua 5k e busca por coordenada [x]
**Concluido:** 2026-05-14

**Observacoes:**
- `_apply_pop_cut_colors` em `components.py`: aplica `fill_color=[120,120,140,70]` e `line_color=[120,120,140,180]` para hexes com `flag_pop_min_5k=False`; nao altera `score_priorizacao` nem artefatos M1.
- `render_pop_cut_legend` em `components.py`: chip visual cinza na legenda dos mapas principal e hibrido.
- `_build_search_hex_layer` em `components.py`: `H3HexagonLayer` amarelo destacado (fill semi-transparente, borda solida) renderizado acima de todas as camadas; aparece mesmo se o hex nao estiver nos filtros nem na base.
- `_apply_hex_tooltip_fields` atualizado: titulo do tooltip recebe sufixo " — Descartado <5k hab" quando `flag_pop_min_5k=False`.
- `build_map_figure` e `build_hybrid_map_figure`: aceitam `search_hex_id: str | None = None`; `flag_pop_min_5k` incluido nos `map_columns`.
- `render_visao_executiva` e `render_modelo_hibrido_v2` em `pages.py`: aceitam `search_hex_id` e chamam `render_pop_cut_legend`.
- `streamlit_app.py`: `search_hex_id` derivado de `lookup_hex_by_coord` e repassado a ambas as funcoes de render.
- Suite: `56 passed` em `test_pop_cut.py` + `test_coord_search.py` + `test_streamlit_app.py`; smoke test `import streamlit_app` ok.
- 3 novos testes: `test_build_map_figure_pinta_hex_descartado_por_pop_com_cor_neutra`, `test_build_map_figure_adiciona_layer_de_destaque_do_hex_pesquisado`, `test_build_map_figure_destaque_hex_aparece_mesmo_fora_dos_filtros`.

### Bloco 4 - Pins das unidades Ultra [x]
**Concluido:** 2026-05-14

**Observacoes:**
- `load_ultra_points(ultra_path)` em `competitors.py`: le `data/ultra/Ultra.csv` com `skiprows=1` (metadado), `sep=";"`, fallback de encoding `latin-1 -> utf-8-sig -> utf-8`; retorna `pd.DataFrame` vazio se arquivo ausente ou sem colunas obrigatorias.
- `ultra_icon_data()` e `ultra_legend_entry()` em `competitors.py`: pin vermelho `#C8001E` com sigla `UA`; SVG base64 identico ao padrao dos concorrentes.
- `_build_ultra_icon_layer(ultra_df, reference_df)` em `components.py`: filtra pelo bounding box do recorte atual (mesma logica de concorrentes); tamanho de icone ligeiramente maior (38px) para distinção visual.
- `render_ultra_legend(ultra_df)` em `components.py`: chip na legenda somente quando `ultra_df` nao estiver vazio; chamado apos `render_competitor_legend` em ambos os mapas.
- `build_map_figure` e `build_hybrid_map_figure` aceitam `ultra_df: pd.DataFrame | None = None`; layer Ultra e empilhado apos concorrentes.
- `render_visao_executiva` e `render_modelo_hibrido_v2` em `pages.py` aceitam `ultra_df`.
- `streamlit_app.py`: `ULTRA_PATH`, `load_ultra()` com `@st.cache_data`; `ultra_df` passado a ambas as abas de mapa.
- Guardrail preservado: `score_priorizacao`, artefatos M1 e carteira intocados.
- Suite: `88 passed` em `tests/unit` + `test_streamlit_app.py`; smoke test `import streamlit_app` ok.
- 17 novos testes em `tests/unit/test_ultra_pins.py`.

### Bloco 5 - Documentacao e fechamento do ciclo [x]
**Concluido:** 2026-05-14

**Observacoes:**
- `CLAUDE.md` atualizado: linha sobre pins Ultra (Bloco 4) adicionada na secao 5; arquivo ficou em 131 linhas (abaixo do limite 200).
- `README.md` atualizado: novas subsecoes "Pins das unidades Ultra no mapa", "Busca por coordenada" e "Regua visual de populacao minima (5k hab)".
- `docs/streamlit_dashboard_m1.md` atualizado: secoes correspondentes adicionadas antes de "Performance e limites locais".
- Suite rapida: `26 passed` em `test_streamlit_app.py` + `test_carteira_plano_nacional.py`; smoke test `import streamlit_app` ok.
- Ciclo de blocos 1-5 encerrado; nenhuma alteracao em `score_priorizacao`, artefatos M1 ou estrutura de dados.

### Bloco 6 - Atualizacao de concorrentes, logos e legenda [x]
**Concluido:** 2026-05-14

**Observacoes:**
- `COMPETITOR_SPECS` expandido de 4 para 27 redes (SkyFit removida); todas as novas planilhas seguem schema `nome_unidade;latitude;longitude;data_coleta`; `bio_ritmo` e `phd_sports` usam `,` — detectado automaticamente em `_read_csv` (tenta `;`, se 1 coluna, tenta `,`).
- `COMPETITOR_BRANDS` atualizado com entradas para todas as 27 redes; fallback SVG preservado para quando logo PNG estiver ausente.
- `COMPETITOR_LOGO_FILES` mapeando rede → filename PNG em `concorrentes/`; `ULTRA_LOGO_FILE = "logo_ultra.png"` em `data/ultra/`.
- `_ICON_CACHE` (dict global), `_png_icon_data` e `preload_logos(competitors_dir, ultra_dir)` adicionados; `competitor_icon_data`/`ultra_icon_data` checam o cache primeiro, fallback ao SVG com `@cache`.
- `preload_logos(CONCORRENTES_DIR, ultra_dir=ULTRA_PATH.parent)` chamado no nivel de modulo de `streamlit_app.py`; logos carregadas antes de qualquer render.
- Legenda de concorrentes removida dos 3 pontos em `pages.py` (visao executiva, modelo hibrido legado, modelo hibrido v2); import `render_competitor_legend` removido de `pages.py`; funcao permanece em `components.py` e importada em `streamlit_app.py` (retro-compat).
- Guardrails preservados: `score_priorizacao`, artefatos M1, carteira e plano intocados; app funciona sem arquivos de logo (fallback SVG) e sem arquivos de CSV (retorna DataFrame vazio).
- Suite: `43 passed` em `test_ultra_pins.py` + `test_streamlit_app.py`; smoke test `import streamlit_app` ok.
- Novos testes: `test_skyfit_nao_esta_no_competitor_specs`, `test_load_competitors_ignora_skyfit`, `test_load_competitors_carrega_multiplas_planilhas`, `test_preload_logos_*` (3 casos: PNG ultra, PNG concorrente, sem arquivos).

## Backlog posterior
- Hardening operacional da VPS: HTTPS/proxy reverso, autenticacao ou VPN, monitoramento de uptime.
- Limpeza assistida dos diretorios temporarios antigos com permissao negada em `fixtures/`.
- Avaliar regeneracao nacional da camada de mercado apos estabilizar a regua de `5.000` habitantes.
