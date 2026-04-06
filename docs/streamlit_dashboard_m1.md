# Dashboard Executivo M1 no Streamlit

## Estrutura final do app

- `Visao Executiva`: KPIs principais, mapa do recorte atual, top cidades por score medio e top UFs por oportunidades viaveis.
- `Analise Territorial`: dispersao entre `renda_per_capita` e `populacao_proxy`, distribuicao de `score_priorizacao`, comparativo por `faixa_oportunidade` e indicadores medios.
- `Ranking e Priorizacao`: tabela executiva ordenada por `rank_brasil` com as colunas oficiais do M1 e destaque visual para score e faixa.
- `Comparacao por UF`: oportunidades viaveis por UF, score medio por UF e comparativo entre top e bottom UFs.

## Principais ajustes visuais

- Paleta alinhada ao pacote executivo M1 ja salvo em `powerbi/m1_dashboard_executivo/`.
- Layout limpo e sobrio com hero inicial, cards de KPI, filtros globais na sidebar e foco em leitura de ate 30 segundos.
- Reducao de ruido visual com limite de linhas na tabela e limite de pontos no mapa para manter fluidez local.

## Dependencias necessarias

- `streamlit`
- `pandas`
- `pyarrow`
- `plotly`

O projeto ja declara essas dependencias no `pyproject.toml`.

## Como rodar localmente

1. Instale as dependencias do projeto, se necessario: `python -m pip install -e .`
2. Garanta a presenca do arquivo oficial: `data/outputs/hexagonos_brasil_dashboard.parquet`
3. Execute: `streamlit run streamlit_app.py`

O app abre localmente e usa apenas o parquet oficial do M1.
