# Fase A - Pipeline Nacional Completo (Bloco 7)

> Data: 2026-05-15
> UFs: AC, AL, AM, AP, BA, CE, ES, MA, MS, MT, PA, PB, PE, PI, PR, RN, RO, RR, SC, SE, TO
> k_global fixo da calibracao validada: 1.0239

## 1. Validacao tecnica por UF

| UF | Coverage % | Amp p95-p05 | Std | Mismatch % | Classe join | qualidade_join_uf | Status tecnico |
| --- | --- | --- | --- | --- | --- | --- | --- |
| AC | 85.29 | 53.24 | 15.86 | 3.97 | B | B | GO |
| AL | 100.00 | 48.07 | 16.05 | 1.45 | A | C | NO-GO |
| AM | 55.87 | 49.73 | 14.54 | 10.50 | C | C | NO-GO |
| AP | 61.62 | 57.87 | 17.46 | 3.49 | B | C | NO-GO |
| BA | 98.10 | 58.77 | 17.90 | 0.79 | A | A | GO |
| CE | 99.84 | 49.38 | 16.27 | 2.20 | B | C | NO-GO |
| ES | 99.85 | 69.90 | 20.77 | 1.59 | A | A | GO |
| MA | 97.64 | 46.66 | 15.62 | 1.66 | A | C | NO-GO |
| MS | 99.45 | 71.79 | 21.20 | 0.87 | A | A | GO |
| MT | 93.32 | 83.31 | 23.90 | 2.06 | B | B | GO |
| PA | 78.66 | 61.26 | 17.68 | 3.88 | B | C | NO-GO |
| PB | 99.99 | 46.82 | 15.79 | 0.79 | A | C | NO-GO |
| PE | 99.83 | 47.99 | 15.93 | 0.82 | A | C | NO-GO |
| PI | 97.30 | 49.82 | 15.98 | 0.84 | A | C | NO-GO |
| PR | 98.11 | 71.89 | 21.27 | 1.44 | A | A | GO |
| RN | 99.99 | 54.88 | 17.17 | 1.35 | A | A | GO |
| RO | 81.62 | 74.31 | 21.94 | 4.40 | B | C | NO-GO |
| RR | 65.56 | 43.48 | 13.36 | 9.59 | C | C | NO-GO |
| SC | 99.20 | 65.46 | 19.87 | 1.80 | A | A | GO |
| SE | 100.00 | 46.71 | 15.41 | 1.91 | A | C | NO-GO |
| TO | 98.25 | 68.89 | 20.84 | 2.14 | B | B | GO |

## 2. Resumo de cobertura

- UFs com gates aprovados (qualidade A/B): 9 — AC, BA, ES, MS, MT, PR, RN, SC, TO
- UFs com gate degradado (qualidade C): 12 — AL, AM, AP, CE, MA, PA, PB, PE, PI, RO, RR, SE
- Nota: gates sao informacionais. Todas as UFs foram incluidas no parquet de saida.

## 3. Decisao consolidada

**GO** para uso controlado como camada complementar.
Nenhuma UF bloqueia a geracao do parquet; UFs com qualidade C ficam marcadas e
sao filtradas automaticamente pelo modelo hibrido.

- Output final: `data\staging\censo2022_setores_calibrado_nacional_completo.parquet`
- M1 oficial permaneceu intocado durante toda a execucao.
