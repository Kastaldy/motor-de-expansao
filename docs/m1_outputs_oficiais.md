# Outputs oficiais do M1

Contrato curto e canonico dos artefatos do fechamento nacional do M1.

## Artefatos

| artefato | papel oficial | campo principal |
| --- | --- | --- |
| `data/staging/brasil_estrutural.parquet` | base estrutural auditavel do M1 | `hex_score_estrutural` |
| `data/staging/brasil_priorizados.parquet` | recorte oficial de priorizacao top 20% por UF | `score_priorizacao` |
| `data/staging/hexagonos_brasil_oportunidades.parquet` | camada canonica de oportunidade com ranking | `score_priorizacao` |
| `data/outputs/hexagonos_brasil_dashboard.parquet` | dataset oficial exportado para BI | `score_oficial` |
| `data/outputs/hexagonos_mapa_sample.parquet` | amostra oficial do dashboard para mapas (o consumidor Streamlit foi aposentado pela DEC-022; o artefato segue gerado) | `score_oficial` |
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

## Artefato derivado (NAO oficial M1)

`data/outputs/hexagonos_dashboard_enriquecido/uf=XX/parte-*.parquet` materializa offline o merge que o dashboard montava a frio em runtime (M1 + hibrido censitario + censo + `pop_total` estrutural). E um dataset pyarrow particionado por `uf`, gerado por `fase1_bi_exports.materialize_enriched_dashboard()` a partir de `enrich_dashboard_data`, sem recalcular `score_priorizacao`, `hex_score_estrutural`, carteira, plano nem os artefatos oficiais acima.

- Papel: acelerar a carga do dashboard (Bloco 4 le apenas a particao da UF selecionada); nao substitui nem altera o M1 oficial.
- Insumos: `hexagonos_brasil_dashboard.parquet` (oficial), `oportunidades_expansao_hibrido.parquet`, `censo2022_setores_calibrado*.parquet`, `censo2022_setores_validado_v2.parquet`, `brasil_estrutural.parquet`.
- Conteudo: mesmas colunas e linhas de `enrich_dashboard_data` (`uf` reconstruida da particao na leitura); regenera-se com `python fase1_bi_exports.py` quando o insumo hibrido existe.
