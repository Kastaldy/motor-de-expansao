# Modelo Hibrido de Expansao

> Data: 2026-08-31
> Status: GO para uso pratico controlado como camada complementar ao M1

## Regra final do modelo

1. O municipio e aprovado primeiro pelo M1 via `score_priorizacao`.
2. O corte municipal usa top 20% de municipios por UF, com minimo operacional de 1 municipio por UF.
3. So depois disso o censitario entra para ranquear hexes dentro dos municipios aprovados.
4. O censitario so participa quando o hex passa nas regras de robustez: score disponivel, coverage >= 85%, join UF classe A/B, sem restricao de join e com densidade setorial minima de 5.000 hab/km2.
5. `score_expansao_hibrido` preserva o M1 como criterio principal e usa o censitario apenas como desempate/refino local.

## Cobertura operacional

- UFs com camada censitaria disponivel: AC, AL, AM, AP, BA, CE, DF, ES, GO, MA, MG, MS, MT, PA, PB, PE, PI, PR, RJ, RN, RO, RR, RS, SC, SE, SP, TO
- Hexes com score censitario disponivel: 1,303,414
- Hexes elegiveis no fluxo hibrido: 780
- Municipios top M1 com camada local utilizavel: 159
- Registros priorizados para monitoramento futuro: 550

## Como usar na pratica

- Primeiro leia `top_municipio` e `rank_municipio_uf` para decidir em quais cidades vale aprofundar a abertura.
- Depois use `rank_hex_intraurbano`, `top_hex_intraurbano` e `top_oportunidade_municipio` para montar shortlist de bairros/hex dentro dessas cidades.
- `top_oportunidade_brasil` e `top_oportunidade_uf` servem como carteira executiva de priorizacao imediata.
- `score_priorizacao` continua sendo o score oficial; `score_expansao_hibrido` existe para ordenar a fila operacional do modelo combinado.

## Municipios hibridos por UF

| UF | Municipios top M1 com camada local | Score medio municipal |
| --- | --- | --- |
| SP | 49 | 98.08 |
| MG | 31 | 94.92 |
| BA | 18 | 84.15 |
| RJ | 11 | 97.38 |
| RS | 10 | 98.45 |
| SC | 8 | 100.00 |
| GO | 8 | 90.74 |
| PR | 7 | 98.48 |
| ES | 6 | 95.93 |
| RN | 4 | 91.59 |
| MT | 3 | 99.23 |
| DF | 1 | 100.00 |
| MS | 1 | 100.00 |
| AC | 1 | 94.92 |
| TO | 1 | 94.35 |

## Top 20 oportunidades Brasil

| Rank Brasil | UF | Municipio | Hex | Score M1 | Score censitario | Score hibrido | Rank intraurbano |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | SP | São Paulo | 87a8100c4ffffff | 100.00 | 100.00 | 100.00100 | 1 |
| 2 | GO | Goiânia | 87a8c0ce0ffffff | 100.00 | 100.00 | 100.00100 | 1 |
| 3 | DF | Brasília | 87a8c2419ffffff | 100.00 | 100.00 | 100.00100 | 1 |
| 4 | SP | São Paulo | 87a8100ebffffff | 100.00 | 100.00 | 100.00100 | 2 |
| 5 | SP | São Paulo | 87a8100e1ffffff | 100.00 | 100.00 | 100.00100 | 3 |
| 6 | SP | São Paulo | 87a8100c1ffffff | 100.00 | 100.00 | 100.00100 | 4 |
| 7 | SP | São Paulo | 87a8100e5ffffff | 100.00 | 100.00 | 100.00100 | 5 |
| 8 | DF | Brasília | 87a8c241bffffff | 100.00 | 100.00 | 100.00100 | 2 |
| 9 | SP | São Paulo | 87a8100c5ffffff | 100.00 | 100.00 | 100.00100 | 6 |
| 10 | MG | Belo Horizonte | 87a88cdb0ffffff | 100.00 | 100.00 | 100.00100 | 1 |
| 11 | SP | São Paulo | 87a8100e2ffffff | 100.00 | 100.00 | 100.00100 | 7 |
| 12 | SP | São Paulo | 87a8100d9ffffff | 100.00 | 100.00 | 100.00100 | 8 |
| 13 | SP | São Paulo | 87a810055ffffff | 100.00 | 100.00 | 100.00100 | 9 |
| 14 | SP | São Paulo | 87a8100d0ffffff | 100.00 | 100.00 | 100.00100 | 10 |
| 15 | SP | São Paulo | 87a8100cdffffff | 100.00 | 100.00 | 100.00100 | 11 |
| 16 | SP | São Paulo | 87a8100ccffffff | 100.00 | 100.00 | 100.00100 | 12 |
| 17 | SP | São Paulo | 87a8100e6ffffff | 100.00 | 100.00 | 100.00100 | 13 |
| 18 | RJ | Rio de Janeiro | 87a8a0616ffffff | 100.00 | 100.00 | 100.00100 | 1 |
| 19 | SP | São Paulo | 87a8100eaffffff | 100.00 | 99.99 | 100.00100 | 14 |
| 20 | RS | Porto Alegre | 87a90128effffff | 100.00 | 99.77 | 100.00100 | 1 |

## Monitoramento futuro (6-12 meses)

- Base criada em `data/outputs/monitoramento_expansao_hibrido_base.parquet`.
- Cada registro ja leva `score_censitario_ponto_monitoramento`, `score_m1_ponto_monitoramento` e `score_expansao_hibrido` do ponto recomendado.
- Quando uma nova unidade for aprovada, basta preencher `data_decisao_abertura`, `data_abertura_unidade` e as metricas de 6/12 meses para validar aderencia do modelo.

## Restricoes mantidas

- O M1 oficial nao foi alterado.
- `score_priorizacao` nao foi substituido.
- O censitario segue como camada complementar local, nao como score oficial nacional.
