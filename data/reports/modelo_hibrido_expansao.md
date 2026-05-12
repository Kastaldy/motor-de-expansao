# Modelo Hibrido de Expansao

> Data: 2026-04-24
> Status: GO para uso pratico controlado como camada complementar ao M1

## Regra final do modelo

1. O municipio e aprovado primeiro pelo M1 via `score_priorizacao`.
2. O corte municipal usa top 20% de municipios por UF, com minimo operacional de 1 municipio por UF.
3. So depois disso o censitario entra para ranquear hexes dentro dos municipios aprovados.
4. O censitario so participa quando o hex passa nas regras de robustez: score disponivel, coverage >= 85%, join UF classe A/B, sem restricao de join e com densidade setorial minima de 5.000 hab/km2.
5. `score_expansao_hibrido` preserva o M1 como criterio principal e usa o censitario apenas como desempate/refino local.

## Cobertura operacional

- UFs com camada censitaria disponivel: AC, AL, AM, AP, BA, CE, DF, ES, GO, MA, MG, MS, MT, PA, PB, PE, PI, PR, RJ, RN, RO, RR, RS, SC, SE, SP, TO
- Hexes com score censitario disponivel: 1,331,239
- Hexes elegiveis no fluxo hibrido: 186
- Municipios top M1 com camada local utilizavel: 26
- Registros priorizados para monitoramento futuro: 141

## Como usar na pratica

- Primeiro leia `top_municipio` e `rank_municipio_uf` para decidir em quais cidades vale aprofundar a abertura.
- Depois use `rank_hex_intraurbano`, `top_hex_intraurbano` e `top_oportunidade_municipio` para montar shortlist de bairros/hex dentro dessas cidades.
- `top_oportunidade_brasil` e `top_oportunidade_uf` servem como carteira executiva de priorizacao imediata.
- `score_priorizacao` continua sendo o score oficial; `score_expansao_hibrido` existe para ordenar a fila operacional do modelo combinado.

## Municipios hibridos por UF

| UF | Municipios top M1 com camada local | Score medio municipal |
| --- | --- | --- |
| SP | 16 | 96.97 |
| MG | 3 | 100.00 |
| BA | 1 | 100.00 |
| DF | 1 | 100.00 |
| ES | 1 | 100.00 |
| GO | 1 | 100.00 |
| PR | 1 | 100.00 |
| RJ | 1 | 100.00 |
| RS | 1 | 100.00 |

## Top 20 oportunidades Brasil

| Rank Brasil | UF | Municipio | Hex | Score M1 | Score censitario | Score hibrido | Rank intraurbano |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | SP | São Paulo | 87a8100e1ffffff | 100.00 | 100.00 | 100.00100 | 1 |
| 2 | SP | São Paulo | 87a8100eaffffff | 100.00 | 100.00 | 100.00100 | 2 |
| 3 | SP | São Paulo | 87a810764ffffff | 100.00 | 100.00 | 100.00100 | 3 |
| 4 | GO | Goiânia | 87a8c0ce0ffffff | 100.00 | 100.00 | 100.00100 | 1 |
| 5 | DF | Brasília | 87a8c2419ffffff | 100.00 | 100.00 | 100.00100 | 1 |
| 6 | RS | Porto Alegre | 87a901283ffffff | 100.00 | 100.00 | 100.00100 | 1 |
| 7 | RS | Porto Alegre | 87a90128effffff | 100.00 | 100.00 | 100.00100 | 2 |
| 8 | RS | Porto Alegre | 87a90129dffffff | 100.00 | 100.00 | 100.00100 | 3 |
| 9 | BA | Salvador | 878116b1dffffff | 100.00 | 100.00 | 100.00100 | 1 |
| 10 | SP | Campinas | 87a813b22ffffff | 100.00 | 100.00 | 100.00100 | 1 |
| 11 | MG | Juiz de Fora | 87a8a3656ffffff | 100.00 | 100.00 | 100.00100 | 1 |
| 12 | MG | Belo Horizonte | 87a88cdb5ffffff | 100.00 | 100.00 | 100.00100 | 1 |
| 13 | SP | São Paulo | 87a8100c1ffffff | 100.00 | 100.00 | 100.00100 | 4 |
| 14 | SP | São Paulo | 87a8100c5ffffff | 100.00 | 100.00 | 100.00100 | 5 |
| 15 | MG | Belo Horizonte | 87a88cd94ffffff | 100.00 | 100.00 | 100.00100 | 2 |
| 16 | SP | Guarulhos | 87a810709ffffff | 100.00 | 100.00 | 100.00100 | 1 |
| 17 | DF | Brasília | 87a8c241bffffff | 100.00 | 100.00 | 100.00100 | 2 |
| 18 | SP | São Paulo | 87a810088ffffff | 100.00 | 100.00 | 100.00100 | 6 |
| 19 | SP | São Paulo | 87a810075ffffff | 100.00 | 100.00 | 100.00100 | 7 |
| 20 | SP | São Paulo | 87a8100e2ffffff | 100.00 | 100.00 | 100.00100 | 8 |

## Monitoramento futuro (6-12 meses)

- Base criada em `data/outputs/monitoramento_expansao_hibrido_base.parquet`.
- Cada registro ja leva `score_censitario_ponto_monitoramento`, `score_m1_ponto_monitoramento` e `score_expansao_hibrido` do ponto recomendado.
- Quando uma nova unidade for aprovada, basta preencher `data_decisao_abertura`, `data_abertura_unidade` e as metricas de 6/12 meses para validar aderencia do modelo.

## Restricoes mantidas

- O M1 oficial nao foi alterado.
- `score_priorizacao` nao foi substituido.
- O censitario segue como camada complementar local, nao como score oficial nacional.
