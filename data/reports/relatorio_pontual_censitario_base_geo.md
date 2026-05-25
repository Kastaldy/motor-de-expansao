# Relatorio - Base censitaria geografica otimizada

> Gerado em 2026-05-25 para o ciclo Relatorio Pontual Censitario 1.5 km.

## Resumo

- Artefato: `data/outputs/setores_censitarios_2022_geo`
- Formato: Parquet com `geometry_wkb`, particionado por `uf` e `cod_municipio`.
- Setores materializados: 468.099
- Arquivos parquet: 5.571
- Tamanho total: 1170.79 MB
- Guardrail: artefato derivado; nao altera M1 oficial, carteira ou plano.

## Performance por UF

| UF | Municipios | Setores | Arquivos | Tamanho MB | Tempo s | Renda % | Score % |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| AC | 22 | 2215 | 22 | 13.06 | 6.18 | 89.44 | 89.44 |
| AL | 102 | 6359 | 102 | 19.75 | 11.61 | 96.98 | 96.98 |
| AM | 62 | 10729 | 62 | 83.76 | 12.46 | 78.65 | 78.65 |
| AP | 16 | 1492 | 16 | 3.73 | 8.20 | 91.09 | 91.09 |
| BA | 417 | 30985 | 417 | 91.18 | 26.87 | 98.46 | 98.46 |
| CE | 184 | 20979 | 184 | 24.60 | 14.82 | 95.79 | 95.79 |
| DF | 1 | 5418 | 1 | 3.46 | 40.83 | 97.16 | 97.16 |
| ES | 78 | 8706 | 78 | 19.62 | 22.54 | 97.31 | 97.31 |
| GO | 246 | 12861 | 246 | 85.15 | 47.10 | 98.16 | 98.16 |
| MA | 217 | 16301 | 217 | 40.69 | 16.53 | 95.52 | 95.52 |
| MG | 853 | 51387 | 853 | 149.70 | 51.43 | 97.86 | 97.86 |
| MS | 79 | 6117 | 79 | 24.08 | 36.36 | 97.84 | 97.84 |
| MT | 141 | 9381 | 141 | 38.07 | 41.61 | 93.74 | 93.74 |
| PA | 144 | 16714 | 144 | 33.80 | 17.93 | 92.90 | 92.90 |
| PB | 223 | 9639 | 223 | 19.94 | 14.90 | 98.24 | 98.24 |
| PE | 185 | 19578 | 185 | 30.90 | 14.47 | 98.07 | 98.07 |
| PI | 224 | 7340 | 224 | 30.89 | 13.08 | 98.26 | 98.26 |
| PR | 399 | 23777 | 399 | 46.23 | 24.68 | 97.48 | 97.48 |
| RJ | 92 | 41700 | 92 | 46.37 | 33.20 | 95.45 | 95.45 |
| RN | 167 | 6095 | 167 | 7.41 | 18.01 | 97.70 | 97.70 |
| RO | 52 | 3456 | 52 | 6.84 | 8.10 | 90.71 | 90.71 |
| RR | 15 | 1783 | 15 | 5.43 | 7.26 | 65.79 | 65.79 |
| RS | 498 | 25569 | 498 | 47.90 | 27.53 | 97.27 | 97.27 |
| SC | 295 | 16736 | 295 | 98.83 | 51.01 | 96.43 | 96.43 |
| SE | 75 | 5346 | 75 | 8.42 | 12.78 | 97.25 | 97.25 |
| SP | 645 | 103319 | 645 | 124.88 | 84.42 | 96.04 | 96.04 |
| TO | 139 | 4117 | 139 | 66.10 | 11.08 | 94.66 | 94.66 |

## Schema

`cod_setor`, `uf`, `cod_uf`, `cod_municipio`, `nome_municipio`, `situacao_setor`, `area_setor_km2_ibge`, `area_setor_m2`, `geometry_wkb`, `crs_origem`, `pop_total_setor_2022`, `domicilios_particulares_ocupados_setor_2022`, `avg_moradores_domicilio_setor_2022`, `renda_responsavel_media_setor_2022`, `renda_per_capita_setor_2022`, `renda_per_capita_setor_2022_calibrada`, `densidade_pop_setor_hab_km2`, `renda_pct_nacional_calibrado`, `pop_pct_municipal`, `hex_score_estrutural_calibrado`, `ajuste_calibrado`, `score_setor_2022_calibrado`, `bbox_minx`, `bbox_miny`, `bbox_maxx`, `bbox_maxy`, `flag_renda_disponivel`, `flag_geometria_valida`, `flag_score_calibrado_disponivel`, `qualidade_join_uf`, `metodo_renda_setor_2022`, `metodo_score_setor_2022`, `data_materializacao`

## Observacoes

- A geometria permanece no CRS original `EPSG:4674`; areas sao calculadas em `EPSG:5880`.
- A renda setorial usa `V06004 / v0005` e calibracao multiplicativa global quando a referencia M1 esta disponivel.
- O score setorial e paralelo e operacional; nao substitui `score_priorizacao`.
- O CSV de renda possui menos linhas que a malha/Basico; o join de renda segue alinhamento posicional por UF e registra `qualidade_join_uf`.
