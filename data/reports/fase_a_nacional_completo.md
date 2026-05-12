# Fase A - Pipeline Nacional Completo (Bloco 7)

> Data: 2026-04-23
> UFs: AC, AL, AM, AP, BA, CE, ES, MA, MS, MT, PA, PB, PE, PI, PR, RN, RO, RR, SC, SE, TO
> k_global fixo da calibracao validada: 1.0213

## 1. Validacao tecnica por UF

| UF | Coverage % | Amp p95-p05 | Std | Mismatch % | Classe join | qualidade_join_uf | Status tecnico |
| --- | --- | --- | --- | --- | --- | --- | --- |
| AC | 85.58 | 54.11 | 16.06 | 3.97 | B | B | GO |
| AL | 100.00 | 47.98 | 16.03 | 1.45 | A | C | NO-GO |
| AM | 60.59 | 56.00 | 16.92 | 10.50 | C | C | NO-GO |
| AP | 62.14 | 59.18 | 18.64 | 3.49 | B | C | NO-GO |
| BA | 99.31 | 59.77 | 18.30 | 0.79 | A | A | GO |
| CE | 99.89 | 49.36 | 16.29 | 2.20 | B | C | NO-GO |
| ES | 99.88 | 70.11 | 20.84 | 1.59 | A | A | GO |
| MA | 97.90 | 48.12 | 15.96 | 1.66 | A | C | NO-GO |
| MS | 99.49 | 72.62 | 21.63 | 0.87 | A | A | GO |
| MT | 95.68 | 83.70 | 24.31 | 2.06 | B | B | GO |
| PA | 80.96 | 63.56 | 18.88 | 3.88 | B | C | NO-GO |
| PB | 100.00 | 47.25 | 15.90 | 0.79 | A | C | NO-GO |
| PE | 99.86 | 47.92 | 16.00 | 0.82 | A | C | NO-GO |
| PI | 98.39 | 50.43 | 16.22 | 0.84 | A | A | GO |
| PR | 98.57 | 72.53 | 21.41 | 1.44 | A | A | GO |
| RN | 99.99 | 54.83 | 17.36 | 1.35 | A | A | GO |
| RO | 84.76 | 78.33 | 22.62 | 4.40 | B | C | NO-GO |
| RR | 69.86 | 48.68 | 15.29 | 9.59 | C | C | NO-GO |
| SC | 99.36 | 67.02 | 20.10 | 1.80 | A | A | GO |
| SE | 100.00 | 46.74 | 15.59 | 1.91 | A | C | NO-GO |
| TO | 99.17 | 68.99 | 20.92 | 2.14 | B | B | GO |

## 2. Resumo de cobertura

- UFs com gates aprovados (qualidade A/B): 10 — AC, BA, ES, MS, MT, PI, PR, RN, SC, TO
- UFs com gate degradado (qualidade C): 11 — AL, AM, AP, CE, MA, PA, PB, PE, RO, RR, SE
- Nota: gates sao informacionais. Todas as UFs foram incluidas no parquet de saida.

## 3. Decisao consolidada

**GO** para uso controlado como camada complementar.
Nenhuma UF bloqueia a geracao do parquet; UFs com qualidade C ficam marcadas e
sao filtradas automaticamente pelo modelo hibrido.

- Output final: `data\staging\censo2022_setores_calibrado_nacional_completo.parquet`
- M1 oficial permaneceu intocado durante toda a execucao.
