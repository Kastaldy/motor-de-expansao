# Modelo Hibrido de Expansao

> Data: 2026-08-26
> Status: GO para uso pratico controlado como camada complementar ao M1

## Regra final do modelo

1. O municipio e aprovado primeiro pelo M1 via `score_priorizacao`.
2. O corte municipal usa top 20% de municipios por UF, com minimo operacional de 1 municipio por UF.
3. So depois disso o censitario entra para ranquear hexes dentro dos municipios aprovados.
4. O censitario so participa quando o hex passa nas regras de robustez: score disponivel, coverage >= 85%, join UF classe A/B, sem restricao de join e com densidade setorial minima de 5.000 hab/km2.
5. `score_expansao_hibrido` preserva o M1 como criterio principal e usa o censitario apenas como desempate/refino local.

## Cobertura operacional

- UFs com camada censitaria disponivel: AC, AL, AM, AP, BA, CE, DF, ES, GO, MA, MG, MS, MT, PA, PB, PE, PI, PR, RJ, RN, RO, RR, RS, SC, SE, SP, TO
- Hexes com score censitario disponivel: 1,302,296
- Hexes elegiveis no fluxo hibrido: 780
- Municipios top M1 com camada local utilizavel: 159
- Registros priorizados para monitoramento futuro: 565

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
| 1 | DF | Brasília | 87a8c241bffffff | 100.00 | 100.00 | 100.00100 | 1 |
| 2 | SP | São Paulo | 87a8100c5ffffff | 100.00 | 100.00 | 100.00100 | 1 |
| 3 | SP | São Paulo | 87a8100dbffffff | 100.00 | 100.00 | 100.00100 | 2 |
| 4 | MG | Belo Horizonte | 87a88cdb0ffffff | 100.00 | 100.00 | 100.00100 | 1 |
| 5 | SP | São Paulo | 87a810770ffffff | 100.00 | 100.00 | 100.00100 | 3 |
| 6 | SP | São Paulo | 87a8100d9ffffff | 100.00 | 100.00 | 100.00100 | 4 |
| 7 | SP | São Paulo | 87a810700ffffff | 100.00 | 100.00 | 100.00100 | 5 |
| 8 | RJ | Rio de Janeiro | 87a8a06a5ffffff | 100.00 | 100.00 | 100.00100 | 1 |
| 9 | SP | São Paulo | 87a810773ffffff | 100.00 | 99.95 | 100.00100 | 6 |
| 10 | RJ | Rio de Janeiro | 87a8a078bffffff | 100.00 | 99.90 | 100.00100 | 2 |
| 11 | SP | São Paulo | 87a810775ffffff | 100.00 | 99.29 | 100.00099 | 7 |
| 12 | SP | São Paulo | 87a810766ffffff | 100.00 | 99.11 | 100.00099 | 8 |
| 13 | PR | Curitiba | 87a83136effffff | 100.00 | 98.57 | 100.00099 | 1 |
| 14 | SP | São Paulo | 87a810774ffffff | 100.00 | 98.06 | 100.00098 | 9 |
| 15 | SP | São Paulo | 87a8103b1ffffff | 100.00 | 97.87 | 100.00098 | 10 |
| 16 | DF | Brasília | 87a8d1b26ffffff | 100.00 | 97.22 | 100.00097 | 2 |
| 17 | GO | Goiânia | 87a8c0ce2ffffff | 100.00 | 97.09 | 100.00097 | 1 |
| 18 | GO | Goiânia | 87a8c0ce3ffffff | 100.00 | 96.99 | 100.00097 | 2 |
| 19 | RS | Porto Alegre | 87a901299ffffff | 100.00 | 95.65 | 100.00096 | 1 |
| 20 | PR | Curitiba | 87a831345ffffff | 100.00 | 95.64 | 100.00096 | 2 |

## Monitoramento futuro (6-12 meses)

- Base criada em `data/outputs/monitoramento_expansao_hibrido_base.parquet`.
- Cada registro ja leva `score_censitario_ponto_monitoramento`, `score_m1_ponto_monitoramento` e `score_expansao_hibrido` do ponto recomendado.
- Quando uma nova unidade for aprovada, basta preencher `data_decisao_abertura`, `data_abertura_unidade` e as metricas de 6/12 meses para validar aderencia do modelo.

## Restricoes mantidas

- O M1 oficial nao foi alterado.
- `score_priorizacao` nao foi substituido.
- O censitario segue como camada complementar local, nao como score oficial nacional.
