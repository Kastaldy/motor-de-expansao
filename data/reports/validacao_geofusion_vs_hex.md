# Validacao GeoFusion 1km vs Populacao do Hex

**Data:** 2026-05-15  
**Unidades analisadas:** 54

## Coberturas

| Indicador | n |
| --- | --- |
| Com dado GeoFusion | 54 |
| Com hex_id_res7 valido | 53 |
| Com pop_hex_base valida | 49 |
| Base comparavel (ambos) | 49 |

## Contexto metodologico

As areas cobertas sao intrinsecamente distintas — nao e esperado que populacao GeoFusion
e populacao do hex sejam iguais. O KPI de comparacao e a densidade (hab/km2).

| Fonte | Area coberta |
| --- | --- |
| GeoFusion raio 1 km | pi x 1^2 = 3.14 km2 (constante) |
| H3 resolucao 7 | ~5.16 km2 (varia por hex; calculado via h3.cell_area) |

Interpretacao do ratio `densidade_hex / densidade_geofusion`:
- Ratio > 1: hex mais denso que raio 1 km GeoFusion (hex captura area menos densa ao redor).
- Ratio < 1: nucleo urbano de 1 km GeoFusion mais denso que o hex como um todo.

## Comparacao de densidades — base comparavel

| Unidade | UF | Fonte pop hex | Area hex km2 | Dens GeoFusion (hab/km2) | Dens hex (hab/km2) | Delta | Ratio |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ACLIMACAO | SP | censo_2022_hex | 5.210 | 17,149.0 | 14,303.7 | -2,845.3 | 0.83 |
| AGUAS CLARAS | DF | censo_2022_hex | 5.777 | 23,388.4 | 12,422.0 | -10,966.3 | 0.53 |
| AGUAS LINDAS | GO | censo_2022_hex | 5.775 | 6,066.4 | 4,663.7 | -1,402.7 | 0.77 |
| ALEXANDRINA | GO | censo_2022_hex | 5.719 | 3,916.8 | 4,553.6 | 636.9 | 1.16 |
| ARAPOANGA PLANALTINA | DF | censo_2022_hex | 5.802 | 5,634.0 | 5,037.5 | -596.5 | 0.89 |
| ASA NORTE | DF | censo_2022_hex | 5.786 | 6,340.1 | 5,735.5 | -604.6 | 0.90 |
| AUGUSTA | SP | censo_2022_hex | 5.211 | 22,072.6 | 10,772.1 | -11,300.5 | 0.49 |
| BOTAFOGO | RJ | m1_municipal_proxy | 5.315 | 20,110.8 | 1,168,693.7 | 1,148,582.9 | 58.11 |
| BOTANIC MALL | DF | m1_municipal_proxy | 5.784 | 1,154.7 | 487,078.1 | 485,923.5 | 421.84 |
| BRASILANDIA | SP | censo_2022_hex | 5.218 | 17,948.3 | 16,137.7 | -1,810.5 | 0.90 |
| CAMBUI CAMPINAS | SP | censo_2022_hex | 5.263 | 12,363.5 | 9,947.7 | -2,415.7 | 0.80 |
| CAMPO LARGO | PR | m1_municipal_proxy | 4.950 | 3,045.5 | 27,541.2 | 24,495.7 | 9.04 |
| CARAPICUIBA | SP | censo_2022_hex | 5.208 | 12,560.3 | 17,991.9 | 5,431.6 | 1.43 |
| CARIACICA | ES | censo_2022_hex | 5.541 | 5,732.9 | 8,021.2 | 2,288.3 | 1.40 |
| CEILANDIA | DF | censo_2022_hex | 5.776 | 12,463.5 | 11,294.0 | -1,169.5 | 0.91 |
| CEILANDIA SUL | DF | censo_2022_hex | 5.776 | 8,917.9 | 9,263.2 | 345.3 | 1.04 |
| CENTRO COMENDADOR | PR | censo_2022_hex | 4.960 | 17,487.6 | 9,614.1 | -7,873.6 | 0.55 |
| COTIA | SP | censo_2022_hex | 5.201 | 4,847.3 | 6,009.0 | 1,161.7 | 1.24 |
| CPA | MT | m1_municipal_proxy | 5.387 | 4,448.3 | 120,821.3 | 116,373.0 | 27.16 |
| CRUZEIRO | DF | censo_2022_hex | 5.784 | 7,544.1 | 6,521.7 | -1,022.4 | 0.86 |
| JARDIM APURA | SP | m1_municipal_proxy | 5.197 | 5,997.7 | 2,203,786.0 | 2,197,788.3 | 367.44 |
| JARDIM BOTANICO | DF | m1_municipal_proxy | 5.782 | 735.6 | 487,305.5 | 486,569.9 | 662.44 |
| JUNDIAI | SP | m1_municipal_proxy | 5.239 | 7,047.3 | 84,606.7 | 77,559.5 | 12.01 |
| LAGO NORTE | DF | m1_municipal_proxy | 5.789 | 4,034.0 | 486,681.3 | 482,647.3 | 120.65 |
| LAGO SUL | DF | m1_municipal_proxy | 5.783 | 119.1 | 487,164.8 | 487,045.6 | 4,088.90 |
| MOCOCA | SP | m1_municipal_proxy | 5.391 | 2,874.6 | 12,553.3 | 9,678.7 | 4.37 |
| MOOCA | SP | censo_2022_hex | 5.213 | 12,127.1 | 12,934.2 | 807.1 | 1.07 |
| NOROESTE | DF | m1_municipal_proxy | 5.786 | 1,814.6 | 486,907.5 | 485,092.9 | 268.33 |
| PARANOA PARQUE | DF | censo_2022_hex | 5.790 | 2,373.3 | 7,715.6 | 5,342.2 | 3.25 |
| PLAZA SUL | SP | censo_2022_hex | 5.208 | 13,711.2 | 16,719.5 | 3,008.3 | 1.22 |
| RECANTO DAS EMAS | DF | censo_2022_hex | 5.773 | 7,674.0 | 4,553.3 | -3,120.7 | 0.59 |
| SAMAMBAIA | DF | censo_2022_hex | 5.774 | 7,418.1 | 8,410.7 | 992.6 | 1.13 |
| SANTA MARIA | DF | m1_municipal_proxy | 5.770 | 5,077.9 | 488,311.2 | 483,233.3 | 96.16 |
| SANTOS | SP | m1_municipal_proxy | 5.180 | 19,395.8 | 80,819.9 | 61,424.0 | 4.17 |
| SERRA | ES | m1_municipal_proxy | 5.551 | 2,241.2 | 93,787.5 | 91,546.3 | 41.85 |
| SETOR OESTE | GO | censo_2022_hex | 5.683 | 7,954.5 | 6,999.1 | -955.3 | 0.88 |
| SOBRADINHO | DF | m1_municipal_proxy | 5.795 | 4,411.4 | 486,134.1 | 481,722.7 | 110.20 |
| SORRISO | MT | m1_municipal_proxy | 5.553 | 2,449.3 | 19,924.3 | 17,474.9 | 8.13 |
| SUZANO | SP | censo_2022_hex | 5.220 | 6,364.6 | 5,853.7 | -511.0 | 0.92 |
| TAGUATINGA | DF | censo_2022_hex | 5.779 | 7,420.9 | 5,518.0 | -1,902.9 | 0.74 |
| TAGUATINGA SUL | DF | m1_municipal_proxy | 5.776 | 3,650.9 | 487,801.0 | 484,150.1 | 133.61 |
| TAUBATE | SP | m1_municipal_proxy | 5.282 | 4,004.7 | 58,828.4 | 54,823.8 | 14.69 |
| UNAI | MG | censo_2022_hex | 5.777 | 6,473.0 | 5,682.9 | -790.0 | 0.88 |
| VALPARAISO | GO | m1_municipal_proxy | 5.764 | 4,458.8 | 34,501.0 | 30,042.2 | 7.74 |
| VICENTE PIRES | DF | m1_municipal_proxy | 5.781 | 2,542.5 | 487,343.2 | 484,800.7 | 191.68 |
| VILA GUANABARA | SC | m1_municipal_proxy | 4.885 | 4,524.8 | 126,162.5 | 121,637.6 | 27.88 |
| VILA GUILHERME | SP | censo_2022_hex | 5.219 | 14,810.4 | 14,510.8 | -299.6 | 0.98 |
| VILA MARIANA | SP | censo_2022_hex | 5.209 | 16,120.4 | 7,089.2 | -9,031.2 | 0.44 |
| VILA MATILDE | SP | censo_2022_hex | 5.217 | 12,637.0 | 11,624.2 | -1,012.8 | 0.92 |

## Estatisticas do ratio

| Estatistica | Valor |
| --- | --- |
| Mediana | 1.24 |
| Media | 136.82 |
| Min | 0.44 |
| Max | 4,088.90 |
| P25 | 0.89 |
| P75 | 27.88 |

## Diagnostico secundario — diferenca bruta de populacao

Registrado apenas para rastreabilidade. Nao usar como KPI de comparacao pois as areas sao distintas.

- Mediana delta pop: 29,345.2 hab
- Media delta pop: 951,763.2 hab

## Unidades sem coordenada (sem hex_id_res7)

- **CAMPO LIMPO** (SP): `sem_hex_id_res7`

## Unidades com coordenada mas sem populacao de hex

Coordenada existe mas hex nao foi encontrado na camada de mercado.

- **PRAIA GRANDE** (SP): `hex_nao_encontrado`
- **POA BARRA SUL** (RS): `hex_nao_encontrado`
- **CABO FRIO** (RJ): `hex_nao_encontrado`
- **GUARUJA** (SP): `hex_nao_encontrado`

## Areas registradas no output

- `area_geofusion_km2`: 3.14 km2 (constante; pi x r^2 com r=1km)
- `area_hex_km2`: min=4.405, max=5.802, mediana=5.541 km2

_Gerado por `jobs/pipelines/comparar_geofusion_vs_hex.py`_