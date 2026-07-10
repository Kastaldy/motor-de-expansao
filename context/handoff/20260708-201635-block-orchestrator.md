# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Proxima Skill recomendada
Planner

## Bloco
BLK-REV-01

## Criticidade confirmada
Alta

## Escopo confirmado (READ-ONLY M1)
NÃO será tocado:
- `src/` (nenhum arquivo de producao alterado)
- `config.py` e qualquer parametro de score (pesos `renda=0.40`/`pop=0.60`, formula, artefatos oficiais)
- `data/outputs/` e `data/staging/` (leitura apenas)
- VPS, rede de producao, deploy
- `streamlit_app.py` (importado mas nao modificado)

O ciclo escreve SOMENTE em `data/analysis/perf_baseline_app_2026.md` (gitignored) e cria `scripts/perf_baseline_app.py`.

## Caminhos a medir (6 benchmarks)

| # | Caminho | Funcao principal | Inputs realistas | Medicao frio/quente |
|---|---|---|---|---|
| 1 | Carga inicial por UF (load_uf_slice + enrich lazy) | `read_enriched_uf_partition(base_dir, uf)` de `data.py`; wrapper `load_uf_slice(uf)` em `streamlit_app.py` | RO (46k hexes, 8 MB — pequena), SC (20k, 6.6 MB — media), AM (294k, 23 MB — grande) | Frio: primeira chamada no processo limpo. Quente: segunda chamada no mesmo processo (sem cache @st — headless) |
| 2 | Troca de UF / municipio (filtro pos-carga) | `apply_global_filters(df, selected_ufs=[uf], selected_cities=[cidade], ...)` de `data.py` | Mesmo df da UF; cidades: Florianopolis/SC, Manaus/AM, Porto Velho/RO | Frio: primeiro apply no df frio. Quente: apply repetido no df ja em memoria |
| 3 | Render do mapa — lado Python (build M1, Hibrido, Residual) | `build_map_figure(df, selected_ufs=[uf], ...)` e `build_hybrid_map_figure(hdf, ...)` de `components.py` | df por UF (RO/SC/AM); competidores e Ultra carregados de `data/staging/concorrentes_mapeados.parquet` e `data/ultra/Ultra.csv` | Frio: primeira montagem do pydeck.Deck. Quente: segunda chamada com mesmo df (sem @st.cache — headless) |
| 4 | Troca de modo de cor (recompute heat-map / color mapping) | `score_band_to_color` via `build_map_figure(color_col=...)` ou `build_hybrid_map_figure(color_col=...)` com trocar coluna de cor entre: `score_priorizacao`, `score_setor_2022_calibrado`, `score_oportunidade_residual`, `score_expansao_hibrido` | Mesmo df de AM (caso saturado, cap MAP_POINT_LIMIT_LARGE=18k) | Frio: primeira troca apos carga. Quente: troca subsequente (df ja quente) |
| 5 | Selecao / cenario multiplo (agregar_cenario_multihex) | `agregar_cenario_multihex(df, hex_ids)` de `data.py` | 1 hex, 5 hexes e 20 hexes amostrados do df de SC (covers range tipico de uso) | Frio: primeira agregacao no df frio. Quente: agregacoes subsequentes |
| 6 | Geracao de PDF (Pontual Censitario e Municipal) | `gerar_pdf_relatorio_pontual_censitario(result, mapas=None)` de `censo_report.py`; `gerar_pdf_relatorio_municipal(municipio_result, mapas=None)` de `relatorio_municipal.py` | Para o Pontual: resultado de `analisar_ponto_censitario_setores(-27.59, -48.55, setores_df_floripa)`. Para Municipal: resultado de `agregar_municipio(df_sc, nome_municipio="Florianopolis", uf="SC")`. `mapas=None` (sem PNG, caminhos puramente offline/fpdf2). | Frio: primeira chamada fpdf2. Quente: segunda chamada consecutiva |

## Artefatos disponíveis em data/

Artefatos relevantes confirmados em disco:

**data/outputs/**
- `hexagonos_brasil_dashboard.parquet` — M1 base (sem enriquecimento)
- `hexagonos_dashboard_enriquecido/uf=XX/parte-0.parquet` — particionado por UF (27 UFs presentes: AC..TO)
  - RO: 46.455 hexes / 8.3 MB; SC: 20.373 hexes / 6.6 MB; AM: 293.991 hexes / 23 MB; SP: 47.389 hexes / 12 MB
- `oportunidades_expansao_hibrido.parquet` — dados hibridos (score_setor/hibrido/residual)
- `setores_censitarios_2022_geo/uf=SC/cod_municipio=4205407/part-000.parquet` — Florianopolis confirmado
- `setores_censitarios_2022_geo/uf=AM/cod_municipio=*/` — 62 municipios AM presentes
- `carteira_expansao_acionavel.parquet`, `plano_expansao_curto_prazo.parquet`, `plano_expansao_dominio.parquet`

**data/staging/**
- `brasil_estrutural.parquet`, `brasil_priorizados.parquet`
- `concorrentes_mapeados.parquet` (3.296 unidades concorrentes)
- `hexagonos_mercado_mapeado.parquet` (dados de residual/mercado)

**data/ultra/Ultra.csv** — unidades Ultra (encoding latin-1, sep=";", 1 linha de metadado)

**Constantes relevantes:**
- `MAP_POINT_LIMIT = 35.000` (cap normal); `MAP_POINT_LIMIT_LARGE = 18.000` (cap UF grande — AM cai neste)
- AM com 293k hexes ativa o cap reduzido automaticamente em `build_map_figure`

## Estrategia de instrumentacao headless

O harness importa as funcoes Python diretamente, **sem Streamlit rodando e sem browser**:

```python
# Configurar PYTHONPATH antes de importar
import sys, logging
sys.path.insert(0, "/repo")
sys.path.insert(0, "/repo/src")
# Suprimir warnings de ScriptRunContext (esperados fora do runtime)
logging.getLogger("streamlit").setLevel(logging.ERROR)

# Importar loaders do streamlit_app (os @st.cache_* viram no-ops sem runtime)
# OU importar diretamente as funcoes puras de data.py / components.py
from motor_expansao.dashboard.data import read_enriched_uf_partition, apply_global_filters, agregar_cenario_multihex
from motor_expansao.dashboard.components import build_map_figure, build_hybrid_map_figure
from motor_expansao.dashboard.censo_report import gerar_pdf_relatorio_pontual_censitario
from motor_expansao.dashboard.relatorio_municipal import gerar_pdf_relatorio_municipal, agregar_municipio
from motor_expansao.dashboard.censo_point import analisar_ponto_censitario_setores
```

**Cuidados de headless:**
1. `@st.cache_data` / `@st.cache_resource` em `streamlit_app.py` funcionam como identity function fora do runtime — preferir chamar as funcoes puras em `data.py` / `components.py` diretamente para medir sem overhead de cache.
2. `build_map_figure` e `build_hybrid_map_figure` retornam um `pdk.Deck` — o custo medido e a montagem Python (tooltip, color-map, downsample, layer); **nao inclui render WebGL** (essa parte e browser-side, complemento manual anotado no relatorio).
3. `pydeck` pode tentar buscar tiles de MapboxToken — usar `map_style=None` ou verificar se pdk.Deck() e instanciavel offline (em geral e: o objeto e serializado, nao renderizado em Python).
4. `gerar_pdf_relatorio_*` usam `fpdf2` (offline, sem rede). `mapas=None` pula a composicao matplotlib/contextily — mede so o backbone fpdf2.
5. Medicao de memoria: usar `psutil.Process().memory_info().rss` quando disponivel; fallback `tracemalloc`.
6. **Frio vs quente** no harness headless: frio = primeira chamada apos `gc.collect()` + carregamento do arquivo (sem cache Python); quente = segunda chamada no mesmo processo (sem re-ler disco).

## Arquivos do ciclo

- **Criar:** `scripts/perf_baseline_app.py` — harness de medicao (todos os 6 benchmarks, frio/quente, 3 UFs, relatorio Markdown)
- **Criar:** `data/analysis/perf_baseline_app_2026.md` — relatorio de resultados (gitignored; pasta `data/analysis/` ja consta no `.gitignore` como `data/analysis/`)
- **NAO alterar:** `src/`, `streamlit_app.py`, qualquer artefato oficial do M1, `config.py`

## Riscos / alertas

1. **AM com 293k hexes:** carga fria pode ser lenta (~5-15s estimado); build_map_figure usa cap de 18k. O harness deve ter timeout ou nota quando AM excede limite esperado.
2. **pydeck offline:** confirmar que `pdk.Deck(...)` nao tenta fetch de tiles durante construcao do objeto Python. Se falhar, medir ate `_deck_layer_frame(map_df)` (montagem do payload serializado) e anotar como "custo Python pre-pydeck".
3. **mapas=None no PDF:** caminho offline limpo (sem contextily/matplotlib). Se o Builder quiser medir o caminho COM mapas (PNG mockado), precisaria gerar um PNG sintetico de teste — anotar como variante opcional.
4. **Setores Florianopolis:** confirmados em `uf=SC/cod_municipio=4205407/part-000.parquet`. O Builder deve usar lat/lng dentro do perimetro de Florianopolis (ex.: -27.5954, -48.5480 — centro da ilha).
5. **profile_dashboard.py existente** em `scripts/`: este script mede SOMENTE a carga nacional full (`load_data`, `load_hybrid_data` etc.) — o BLK-REV-01 mede os 6 caminhos com granularidade por UF. NAO sobrescrever o script existente; criar `perf_baseline_app.py` como arquivo novo.
6. **data/analysis/ gitignored:** verificar se `.gitignore` ja cobre essa pasta; se nao, adicionar explicitamente no script para evitar commit acidental do relatorio.
7. **Troca de modo de cor (caminho 4):** `score_band_to_color` e uma funcao pura de `utils.py`; o custo real do "rerun por troca de cor" no Streamlit inclui re-chamar todo `build_map_figure`. O harness mede esse custo integral, que e o mais honesto para o Felipe.
