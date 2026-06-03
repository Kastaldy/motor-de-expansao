# Base H3 Brasil

- Data de execucao: 2026-06-03 12:46:12
- Resolucao H3: 7
- Total de hexagonos: 1542531
- Tempo de execucao: 105.8s
- Fonte malha UFs IBGE: https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR?formato=application/vnd.geo+json&intrarregiao=UF&qualidade=maxima
- Cache malha UFs: data\raw\ibge\malha_uf_brasil.geojson
- Fonte malha Brasil IBGE: https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR?formato=application/vnd.geo+json&qualidade=maxima
- Cache malha Brasil: data\raw\ibge\malha_brasil.geojson

## Distribuicao por UF

| UF | Regiao | Hexagonos | Removidos | Recuperados costeiros | Tempo (s) |
|----|--------|-----------|-----------|-----------------------|-----------|
| AC | N | 29004 | 109 | 254 | 1.5 |
| AL | NE | 4635 | 14 | 40 | 0.2 |
| AM | N | 293991 | 245 | 488 | 18.6 |
| AP | N | 24686 | 92 | 204 | 2.0 |
| BA | NE | 94279 | 55 | 151 | 5.5 |
| CE | NE | 24192 | 28 | 83 | 1.1 |
| DF | CO | 999 | 0 | 0 | 0.4 |
| ES | SE | 8324 | 30 | 81 | 0.6 |
| GO | CO | 59954 | 0 | 0 | 3.7 |
| MA | NE | 53796 | 158 | 242 | 4.8 |
| MG | SE | 104078 | 0 | 0 | 7.5 |
| MS | CO | 69924 | 106 | 232 | 4.1 |
| MT | CO | 165383 | 57 | 141 | 9.1 |
| PA | N | 214734 | 165 | 280 | 14.9 |
| PB | NE | 9278 | 13 | 23 | 1.2 |
| PE | NE | 16085 | 20 | 31 | 1.4 |
| PI | NE | 40892 | 4 | 9 | 3.2 |
| PR | S | 40481 | 40 | 93 | 2.4 |
| RJ | SE | 8286 | 132 | 146 | 1.3 |
| RN | NE | 8708 | 19 | 70 | 1.4 |
| RO | N | 46455 | 100 | 174 | 3.3 |
| RR | N | 44243 | 187 | 297 | 3.2 |
| RS | S | 62410 | 344 | 635 | 4.8 |
| SC | S | 20373 | 70 | 107 | 2.0 |
| SE | NE | 3650 | 4 | 23 | 1.1 |
| SP | SE | 47389 | 70 | 96 | 3.5 |
| TO | N | 46302 | 0 | 0 | 3.0 |

## Problemas encontrados

- 11 hexagonos de mar duplicados entre UFs costeiras removidos pelo dedup nacional (cada hex fica na 1a UF processada).
- 3900 hexagonos costeiros recuperados (centroide fora mas fracao de terra >= 0.05) em 23 UFs.
- 2062 hexagonos sem centroide no Brasil removidos (centroide em mar/fronteira, fracao de terra < 0.05) em 23 UFs.
