# Base H3 Brasil

- Data de execucao: 2026-06-03 09:59:32
- Resolucao H3: 7
- Total de hexagonos: 1538424
- Tempo de execucao: 50.0s
- Fonte malha UFs IBGE: https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR?formato=application/vnd.geo+json&intrarregiao=UF&qualidade=maxima
- Cache malha UFs: data\raw\ibge\malha_uf_brasil.geojson
- Fonte malha Brasil IBGE: https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR?formato=application/vnd.geo+json&qualidade=maxima
- Cache malha Brasil: data\raw\ibge\malha_brasil.geojson

## Distribuicao por UF

| UF | Regiao | Hexagonos | Removidos | Recuperados costeiros | Tempo (s) |
|----|--------|-----------|-----------|-----------------------|-----------|
| AC | N | 28745 | 5 | 24 | 0.7 |
| AL | NE | 4595 | 0 | 1 | 0.1 |
| AM | N | 293488 | 15 | 57 | 11.2 |
| AP | N | 24479 | 3 | 14 | 0.5 |
| BA | NE | 94127 | 1 | 10 | 3.8 |
| CE | NE | 24109 | 0 | 13 | 0.5 |
| DF | CO | 999 | 0 | 0 | 0.0 |
| ES | SE | 8241 | 2 | 2 | 0.2 |
| GO | CO | 59954 | 0 | 1 | 1.6 |
| MA | NE | 53520 | 34 | 33 | 2.1 |
| MG | SE | 104078 | 0 | 0 | 3.8 |
| MS | CO | 69686 | 6 | 31 | 1.7 |
| MT | CO | 165241 | 3 | 11 | 5.0 |
| PA | N | 214431 | 25 | 43 | 7.8 |
| PB | NE | 9251 | 4 | 1 | 0.5 |
| PE | NE | 16054 | 1 | 4 | 0.6 |
| PI | NE | 40883 | 0 | 1 | 1.1 |
| PR | S | 40383 | 5 | 10 | 1.0 |
| RJ | SE | 8112 | 28 | 23 | 0.2 |
| RN | NE | 8638 | 0 | 6 | 0.2 |
| RO | N | 46264 | 17 | 35 | 1.2 |
| RR | N | 43931 | 16 | 49 | 1.4 |
| RS | S | 61745 | 30 | 73 | 2.1 |
| SC | S | 20255 | 13 | 16 | 0.5 |
| SE | NE | 3627 | 0 | 2 | 0.1 |
| SP | SE | 47286 | 10 | 14 | 1.2 |
| TO | N | 46302 | 0 | 0 | 1.1 |

## Problemas encontrados

- 474 hexagonos costeiros recuperados (centroide fora mas fracao de terra >= 0.2) em 24 UFs.
- 218 hexagonos sem centroide no Brasil removidos (centroide em mar/fronteira, fracao de terra < 0.2) em 18 UFs.
