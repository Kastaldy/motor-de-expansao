# Modelo Hibrido de Expansao

> Data: 2026-08-25
> Status: GO para uso pratico controlado como camada complementar ao M1

## Regra final do modelo

1. O municipio e aprovado primeiro pelo M1 via `score_priorizacao`.
2. O corte municipal usa top 20% de municipios por UF, com minimo operacional de 1 municipio por UF.
3. So depois disso o censitario entra para ranquear hexes dentro dos municipios aprovados.
4. O censitario so participa quando o hex passa nas regras de robustez: score disponivel, coverage >= 85%, join UF classe A/B, sem restricao de join e com no minimo 5.000 habitantes no hexagono (piso de PORTE, nao de densidade -- ver POP_MIN_HEX_HIBRIDO).
5. `score_expansao_hibrido` preserva o M1 como criterio principal e usa o censitario apenas como desempate/refino local.

## Cobertura operacional

- UFs com camada censitaria disponivel: AC, AL, AM, AP, BA, CE, DF, ES, GO, MA, MG, MS, MT, PA, PB, PE, PI, PR, RJ, RN, RO, RR, RS, SC, SE, SP, TO
- Hexes com score censitario disponivel: 1,302,296
- Hexes elegiveis no fluxo hibrido: 4,674
- Municipios top M1 com camada local utilizavel: 771
- Registros priorizados para monitoramento futuro: 3,442

## Como usar na pratica

- Primeiro leia `top_municipio` e `rank_municipio_uf` para decidir em quais cidades vale aprofundar a abertura.
- Depois use `rank_hex_intraurbano`, `top_hex_intraurbano` e `top_oportunidade_municipio` para montar shortlist de bairros/hex dentro dessas cidades.
- `top_oportunidade_brasil` e `top_oportunidade_uf` servem como carteira executiva de priorizacao imediata.
- `score_priorizacao` continua sendo o score oficial; `score_expansao_hibrido` existe para ordenar a fila operacional do modelo combinado.

## Municipios hibridos por UF

| UF | Municipios top M1 com camada local | Score medio municipal |
| --- | --- | --- |
| MG | 167 | 77.67 |
| SP | 129 | 95.75 |
| RS | 92 | 85.98 |
| BA | 79 | 69.18 |
| PR | 76 | 85.42 |
| SC | 56 | 89.35 |
| GO | 49 | 81.18 |
| MT | 27 | 86.24 |
| RN | 27 | 62.53 |
| RJ | 18 | 96.68 |
| TO | 18 | 59.70 |
| MS | 15 | 85.09 |
| ES | 13 | 91.52 |
| AC | 4 | 70.54 |
| DF | 1 | 100.00 |

## Top 20 oportunidades Brasil

| Rank Brasil | UF | Municipio | Hex | Score M1 | Score censitario | Score hibrido | Rank intraurbano |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | MT | Cuiabá | 878ba6506ffffff | 100.00 | 100.00 | 100.00100 | 1 |
| 2 | MT | Cuiabá | 878ba6531ffffff | 100.00 | 100.00 | 100.00100 | 2 |
| 3 | MT | Cuiabá | 878ba6535ffffff | 100.00 | 100.00 | 100.00100 | 3 |
| 4 | PR | Londrina | 87a80132affffff | 100.00 | 100.00 | 100.00100 | 1 |
| 5 | PR | Londrina | 87a801374ffffff | 100.00 | 100.00 | 100.00100 | 2 |
| 6 | PR | Londrina | 87a801adbffffff | 100.00 | 100.00 | 100.00100 | 3 |
| 7 | PR | Curitiba | 87a804d92ffffff | 100.00 | 100.00 | 100.00100 | 1 |
| 8 | SP | São Paulo | 87a810764ffffff | 100.00 | 100.00 | 100.00100 | 1 |
| 9 | SP | Campinas | 87a81148bffffff | 100.00 | 100.00 | 100.00100 | 1 |
| 10 | SP | Piracicaba | 87a811640ffffff | 100.00 | 100.00 | 100.00100 | 1 |
| 11 | SP | São José dos Campos | 87a812aa4ffffff | 100.00 | 100.00 | 100.00100 | 1 |
| 12 | SP | São Carlos | 87a81ea82ffffff | 100.00 | 100.00 | 100.00100 | 1 |
| 13 | SP | São Carlos | 87a81ea9effffff | 100.00 | 100.00 | 100.00100 | 2 |
| 14 | PR | Cascavel | 87a82c26dffffff | 100.00 | 100.00 | 100.00100 | 1 |
| 15 | PR | Cascavel | 87a82dc83ffffff | 100.00 | 100.00 | 100.00100 | 2 |
| 16 | PR | Cascavel | 87a82dc91ffffff | 100.00 | 100.00 | 100.00100 | 3 |
| 17 | PR | Cascavel | 87a82dc9affffff | 100.00 | 100.00 | 100.00100 | 4 |
| 18 | PR | Curitiba | 87a831361ffffff | 100.00 | 100.00 | 100.00100 | 2 |
| 19 | SC | Jaraguá do Sul | 87a835313ffffff | 100.00 | 100.00 | 100.00100 | 1 |
| 20 | SC | Jaraguá do Sul | 87a83531cffffff | 100.00 | 100.00 | 100.00100 | 2 |

## Monitoramento futuro (6-12 meses)

- Base criada em `data/outputs/monitoramento_expansao_hibrido_base.parquet`.
- Cada registro ja leva `score_censitario_ponto_monitoramento`, `score_m1_ponto_monitoramento` e `score_expansao_hibrido` do ponto recomendado.
- Quando uma nova unidade for aprovada, basta preencher `data_decisao_abertura`, `data_abertura_unidade` e as metricas de 6/12 meses para validar aderencia do modelo.

## Restricoes mantidas

- O M1 oficial nao foi alterado.
- `score_priorizacao` nao foi substituido.
- O censitario segue como camada complementar local, nao como score oficial nacional.
