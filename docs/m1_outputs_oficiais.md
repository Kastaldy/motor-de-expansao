# Outputs oficiais do M1

Contrato curto e canonico dos artefatos do fechamento nacional do M1.

## Artefatos

| artefato | papel oficial | campo principal |
| --- | --- | --- |
| `data/staging/brasil_estrutural.parquet` | base estrutural auditavel do M1 | `hex_score_estrutural` |
| `data/staging/brasil_priorizados.parquet` | recorte oficial de priorizacao top 20% por UF | `score_priorizacao` |
| `data/staging/hexagonos_brasil_oportunidades.parquet` | camada canonica de oportunidade com ranking | `score_priorizacao` |
| `data/outputs/hexagonos_brasil_dashboard.parquet` | dataset oficial exportado para BI | `score_oficial` |
| `data/outputs/hexagonos_mapa_sample.parquet` | amostra oficial do dashboard para mapas no Streamlit | `score_oficial` |
| `data/outputs/top_oportunidades_resumo.csv` | resumo executivo das oportunidades viaveis | `score_oficial` |
| `data/outputs/resumo_por_uf.csv` | resumo agregado por UF | `score_oficial` |

## Dicionario de dados

| campo | definicao oficial |
| --- | --- |
| `hex_score_estrutural` | base estrutural do M1, calculada a partir dos percentis nacionais de renda e populacao proxy |
| `ajuste_executivo` | bonus ou penalidade de priorizacao aplicado sobre a base estrutural |
| `score_priorizacao` | score oficial do M1 para ranking executivo e priorizacao |
| `score_oficial` | replica estavel para consumo de BI, igual a `score_priorizacao` |
| `score_oficial_nome` | nome fixo do score oficial exportado, sempre `score_priorizacao` |
| `score_percentil_nacional` | percentil nacional do `score_priorizacao` |
| `faixa_oportunidade` | classificacao executiva do hexagono |
| `flag_viavel` | indica se o hexagono passa a leitura executiva minima |
| `flag_prioridade` | indica se o hexagono esta no recorte priorizado oficial |
| `rank_brasil`, `rank_uf`, `rank_cidade` | ranking executivo oficial nas tres granularidades |
| `osm_status` | status do uso de OSM; no fechamento nacional atual deve ser `nao_aplicado_mvp_nacional` |
| colunas de rastreabilidade IBGE | `fonte_demografica`, `fonte_renda`, `fonte_populacao`, `nivel_geografico_ibge`, `fallback_setor_censitario`, `motivo_fallback_setor`, `fonte_geometria_ibge`, `metodo_atribuicao_municipio`, `data_referencia_ibge` |
