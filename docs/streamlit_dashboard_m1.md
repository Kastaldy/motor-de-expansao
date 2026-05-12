# Dashboard Executivo M1 + Hibrido no Streamlit

## Estrutura atual do app

- `Visao Executiva`: KPIs principais do M1, mapa do recorte atual, top cidades por score medio e top UFs por oportunidades viaveis.
- `Analise Territorial`: dispersao entre `renda_per_capita` e `populacao_proxy`, distribuicao de `score_priorizacao`, comparativo por `faixa_oportunidade` e indicadores medios.
- `Ranking e Priorizacao`: tabela executiva ordenada por `rank_brasil` com as colunas oficiais do M1.
- `Comparacao por UF`: oportunidades viaveis por UF, score medio por UF e comparativo entre top e bottom UFs.
- `Modelo Hibrido`: quatro subtabs executivas para `Oportunidades Hibridas`, `Ranking Intraurbano`, `M1 vs Censitario` e `Municipios + Melhores Hexes`.

## Fontes e governanca

- Base oficial preservada: `data/outputs/hexagonos_brasil_dashboard.parquet`
- Camada hibrida operacional: `data/outputs/oportunidades_expansao_hibrido.parquet`
- Camadas censitarias de apoio e rastreabilidade:
  - `data/staging/censo2022_setores_calibrado.parquet`
  - `data/staging/censo2022_setores_calibrado_piloto_expandido.parquet`
  - `data/staging/censo2022_setores_validado_v2.parquet`
- O app carrega a base oficial do M1 primeiro e depois faz apenas enriquecimento local com as colunas censitarias/hibridas.
- `score_priorizacao` continua sendo o score oficial de expansao.

## Como interpretar os modelos

- `M1 = decisao municipal`: usar `score_priorizacao`, `rank_municipio_uf` e `top_municipio` para decidir quais mercados entram na fila.
- `Censitario = decisao intraurbana`: usar `score_setor_2022_calibrado`, `rank_hex_intraurbano` e `top_hex_intraurbano` para escolher bairros e hexes dentro de municipios aprovados.
- `Hibrido = uso combinado`: usar `score_expansao_hibrido` e `top_oportunidade_municipio` para ordenar a carteira operacional sem substituir o M1.

## Filtros globais

- `UF`
- `Municipio`
- `Faixa de oportunidade`
- `Elegibilidade hibrida`
- `Cobertura censitaria`
- `Qualidade da camada`
- `Apenas top_municipio`
- `Apenas top_hex_intraurbano`

## KPIs executivos adicionais

- Municipios elegiveis no hibrido
- Hexes elegiveis
- Municipios cobertos pela camada censitaria
- Registros prontos para monitoramento
- Comparativo entre oportunidades M1 e oportunidades hibridas

## Rastreabilidade visual

- Hover do mapa intraurbano com `qualidade_join_uf`, `flag_join_uf_restrito`, `flag_baixa_pop_setor`, `flag_outlier_espacial`, `causa_outlier_espacial` e `coverage_pct_setor_2022`.
- Tabelas executivas com flags de join restrito, baixa populacao e outlier espacial.
- Regra editorial: dado restrito ou de baixa confianca nao deve ser interpretado como evidencia forte isolada.

## Performance e limites locais

- O app continua offline e usa apenas arquivos locais.
- O mapa limita a renderizacao aos hexes mais relevantes do recorte para manter fluidez.
- As tabelas continuam limitadas a `1.000` linhas por visao.

## Como rodar localmente

1. Instale as dependencias do projeto, se necessario: `python -m pip install -e .`
2. Garanta a presenca do dataset oficial do M1: `data/outputs/hexagonos_brasil_dashboard.parquet`
3. Garanta a presenca das camadas opcionais censitarias/hibridas, se quiser a visao completa
4. Execute: `streamlit run streamlit_app.py`

Sem as camadas censitarias/hibridas, as abas oficiais do M1 continuam funcionando.
