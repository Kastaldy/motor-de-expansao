# Fase A - Piloto expandido calibrado

> Data: 2026-04-09
> UFs: MG, DF, RS
> k_global fixo da calibracao validada: 1.0213

## 1. Validacao tecnica por UF

| UF | Coverage % | Amp p95-p05 | Std | Distintos | Mismatch % | Classe join | Outliers criticos | Status espacial | Status tecnico |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MG | 99.86 | 76.65 | 22.70 | 98645 | 0.89 | A | 344 | REVIEW | GO |
| DF | 98.60 | 92.78 | 25.94 | 925 | 1.40 | A | 4 | REVIEW | GO |
| RS | 99.86 | 76.60 | 22.26 | 58976 | 1.05 | A | 209 | REVIEW | GO |

## 2. Comparativo tecnico com o M1

| UF | Amp calibrado | Amp M1 | Ganho amp | Std calibrado | Std M1 | Ganho std | Spearman calibrado vs M1 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MG | 76.65 | 72.52 | 4.13 | 22.70 | 22.13 | 0.57 | 0.07 |
| DF | 92.78 | 0.00 | 92.78 | 25.94 | 0.00 | 25.94 | N/D |
| RS | 76.60 | 58.60 | 18.00 | 22.26 | 18.64 | 3.62 | -0.02 |

## 3. Dados reais Ultra

- Status: `SNAPSHOT_NAO_ENCONTRADO`
- Fonte: `nao encontrada`
- Observacao: Snapshot real de unidades Ultra nao encontrado no workspace; correlacao de negocio e ganho vs M1 permanecem pendentes.

- Correlacoes com metricas reais: N/D.
- Comparacao de explicacao de performance vs M1: pendente pelo mesmo motivo.

## 4. Decisao consolidada

**NO-GO** para escala nacional imediata.

Motivos principais:
- validacao com dados reais da Ultra nao foi concluida

- Output final: `data\staging\censo2022_setores_calibrado_piloto_expandido.parquet`
- M1 oficial permaneceu intocado durante toda a execucao.
