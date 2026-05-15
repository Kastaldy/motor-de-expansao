# Fase A — Censo 2022 por Setor Censitario (Piloto GO + SP + RJ)

> Data de execucao: 2026-05-15
> Fonte: IBGE Censo Demografico 2022 — Agregados por Setores Censitarios

## 1. Setores processados por UF

### GO
- Setores no Basico: 12861
- Setores no DomicilioRenda (linhas totais): 12816
- Setores no DomicilioRenda (renda valida): 12625
- Setores com match (apos join): 12861
- Setores descartados (pop invalida): 0
- Setores descartados (renda invalida): 191
- Mismatch estrutural do join (%): 0.35

### SP
- Setores no Basico: 103319
- Setores no DomicilioRenda (linhas totais): 100928
- Setores no DomicilioRenda (renda valida): 99223
- Setores com match (apos join): 103319
- Setores descartados (pop invalida): 0
- Setores descartados (renda invalida): 1705
- Mismatch estrutural do join (%): 2.31

### RJ
- Setores no Basico: 41700
- Setores no DomicilioRenda (linhas totais): 40519
- Setores no DomicilioRenda (renda valida): 39804
- Setores com match (apos join): 41700
- Setores descartados (pop invalida): 0
- Setores descartados (renda invalida): 715
- Mismatch estrutural do join (%): 2.83

## 2. Cobertura espacial por UF

| UF | Hex total | Hex com match | Cobertura % | Ref 2010 % | Gate (>=85%) |
| --- | --- | --- | --- | --- | --- |
| GO | 59952 | 59878 | 99.88 | 100.0 | PASS |
| SP | 47139 | 46670 | 99.01 | 100.0 | PASS |
| RJ | 7895 | 7841 | 99.32 | 97.88 | PASS |

## 3. Amplitude intraurbana (score_setor_2022_exp)

| UF | Amplitude p95-p05 | Ref 2010 | Std | Distintos | Gate (>50) |
| --- | --- | --- | --- | --- | --- |
| GO | 54.06 | 71.47 | 14.73 | 2613 | PASS |
| SP | 59.59 | 69.06 | 17.42 | 3998 | PASS |
| RJ | 59.85 | 74.31 | 18.67 | 2315 | PASS |

## 4. Rastreabilidade

| UF | % nulos rastreio | Gate (<=2%) |
| --- | --- | --- |
| GO | 0.00 | PASS |
| SP | 0.00 | PASS |
| RJ | 0.00 | PASS |

## 5. Comparacao com experimento 2010

| UF | Cobertura 2022 | Cobertura 2010 | Ampl. 2022 | Ampl. 2010 |
| --- | --- | --- | --- | --- |
| GO | 99.88% | 100.0% | 54.06 | 71.47 |
| SP | 99.01% | 100.0% | 59.59 | 69.06 |
| RJ | 99.32% | 97.88% | 59.85 | 74.31 |

## 6. Distribuicao do score experimental

- count: 114024
- min: 0.0
- max: 96.17
- media: 29.59
- mediana: 29.21
- std: 16.32
- p90: 55.15

## 7. Status do gate de qualidade

| UF | Cobertura | Amplitude | Rastreio | Status |
| --- | --- | --- | --- | --- |
| GO | PASS | PASS | PASS | **GO** |
| SP | PASS | PASS | PASS | **GO** |
| RJ | PASS | PASS | PASS | **GO** |

## 8. Recomendacao

**GO** — Todas as UFs piloto passaram nos gates de qualidade.
Recomendacao: avancar para escala nacional.

## 9. Observacoes

- `score_setor_2022_exp` e experimental — NAO substitui `score_priorizacao` oficial.
- Nenhum artefato do M1 oficial foi alterado.
- Percentis ancorados na distribuicao nacional do M1 via `_percentil_em_distribuicao_referencia()`.
- Hexagonos com cobertura < 10% foram marcados como fallback e nao receberam score.
- `domicilios_setor_2022` nao disponivel nesta versao (coluna nula).
