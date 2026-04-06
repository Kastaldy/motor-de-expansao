# Base H3 Brasil

- Data de execucao: 2026-04-05 16:28:37
- Resolucao H3: 7
- Total de hexagonos: 1532645
- Tempo de execucao: 153.5s
- Fonte malha UFs IBGE: https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR?formato=application/vnd.geo+json&intrarregiao=UF&qualidade=maxima
- Cache malha UFs: data\raw\ibge\malha_uf_brasil.geojson
- Fonte malha Brasil IBGE: https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR?formato=application/vnd.geo+json&qualidade=maxima
- Cache malha Brasil: data\raw\ibge\malha_brasil.geojson

## Distribuicao por UF

| UF | Regiao | Hexagonos | Removidos | Tempo (s) |
|----|--------|-----------|-----------|-----------|
| AC | N | 28370 | 380 | 3.2 |
| AL | NE | 4544 | 51 | 0.5 |
| AM | N | 292793 | 710 | 30.7 |
| AP | N | 24162 | 320 | 2.3 |
| BA | NE | 93918 | 210 | 9.9 |
| CE | NE | 23975 | 134 | 2.4 |
| DF | CO | 999 | 0 | 0.1 |
| ES | SE | 8158 | 85 | 0.8 |
| GO | CO | 59952 | 2 | 5.8 |
| MA | NE | 53180 | 374 | 5.3 |
| MG | SE | 104078 | 0 | 10.5 |
| MS | CO | 69344 | 348 | 6.7 |
| MT | CO | 165033 | 211 | 16.1 |
| PA | N | 213997 | 459 | 21.2 |
| PB | NE | 9223 | 32 | 1.0 |
| PE | NE | 16013 | 42 | 1.5 |
| PI | NE | 40869 | 14 | 3.9 |
| PR | S | 40261 | 127 | 3.9 |
| RJ | SE | 7895 | 245 | 0.8 |
| RN | NE | 8555 | 83 | 0.8 |
| RO | N | 45962 | 319 | 4.4 |
| RR | N | 43424 | 523 | 4.2 |
| RS | S | 60811 | 964 | 6.1 |
| SC | S | 20100 | 168 | 2.0 |
| SE | NE | 3588 | 39 | 0.3 |
| SP | SE | 47139 | 157 | 4.6 |
| TO | N | 46302 | 0 | 4.5 |

## Problemas encontrados

- 5997 hexagonos de borda foram removidos intencionalmente por extrapolar mar/fronteira em 24 UFs.
