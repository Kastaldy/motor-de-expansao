# Base H3 Brasil

- Data de execucao: 2026-05-26 09:32:57
- Resolucao H3: 7
- Total de hexagonos: 1537950
- Tempo de execucao: 48.2s
- Fonte malha UFs IBGE: https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR?formato=application/vnd.geo+json&intrarregiao=UF&qualidade=maxima
- Cache malha UFs: data\raw\ibge\malha_uf_brasil.geojson
- Fonte malha Brasil IBGE: https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR?formato=application/vnd.geo+json&qualidade=maxima
- Cache malha Brasil: data\raw\ibge\malha_brasil.geojson

## Distribuicao por UF

| UF | Regiao | Hexagonos | Removidos | Tempo (s) |
|----|--------|-----------|-----------|-----------|
| AC | N | 28721 | 29 | 1.1 |
| AL | NE | 4594 | 1 | 0.1 |
| AM | N | 293431 | 72 | 11.6 |
| AP | N | 24465 | 17 | 0.7 |
| BA | NE | 94117 | 11 | 2.8 |
| CE | NE | 24096 | 13 | 0.6 |
| DF | CO | 999 | 0 | 0.0 |
| ES | SE | 8239 | 4 | 0.2 |
| GO | CO | 59953 | 1 | 1.7 |
| MA | NE | 53487 | 67 | 1.5 |
| MG | SE | 104078 | 0 | 3.5 |
| MS | CO | 69655 | 37 | 1.7 |
| MT | CO | 165230 | 14 | 4.7 |
| PA | N | 214388 | 68 | 7.1 |
| PB | NE | 9250 | 5 | 0.2 |
| PE | NE | 16050 | 5 | 0.4 |
| PI | NE | 40882 | 1 | 1.2 |
| PR | S | 40373 | 15 | 1.3 |
| RJ | SE | 8089 | 51 | 0.2 |
| RN | NE | 8632 | 6 | 0.2 |
| RO | N | 46229 | 52 | 1.2 |
| RR | N | 43882 | 65 | 1.1 |
| RS | S | 61672 | 103 | 1.9 |
| SC | S | 20239 | 29 | 0.6 |
| SE | NE | 3625 | 2 | 0.1 |
| SP | SE | 47272 | 24 | 1.2 |
| TO | N | 46302 | 0 | 1.1 |

## Problemas encontrados

- 692 hexagonos sem centroide no Brasil removidos (centroide em mar/fronteira) em 24 UFs.
