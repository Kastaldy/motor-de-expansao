# Fase A - Piloto expandido calibrado

> Data: 2026-05-15
> UFs: MG, DF, RS
> k_global fixo da calibracao validada: 1.0239

## 1. Validacao tecnica por UF

| UF | Coverage % | Amp p95-p05 | Std | Distintos | Mismatch % | Classe join | Outliers criticos | Status espacial | Status tecnico |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MG | 99.78 | 75.32 | 22.47 | 98852 | 0.89 | A | 344 | REVIEW | GO |
| DF | 98.30 | 92.19 | 25.86 | 917 | 1.40 | A | 4 | REVIEW | GO |
| RS | 99.85 | 74.98 | 22.01 | 58978 | 1.05 | A | 204 | REVIEW | GO |

## 2. Comparativo tecnico com o M1

| UF | Amp calibrado | Amp M1 | Ganho amp | Std calibrado | Std M1 | Ganho std | Spearman calibrado vs M1 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MG | 75.32 | 78.65 | -3.33 | 22.47 | 24.92 | -2.45 | 0.06 |
| DF | 92.19 | 0.00 | 92.19 | 25.86 | 0.00 | 25.86 | N/D |
| RS | 74.98 | 69.15 | 5.83 | 22.01 | 24.20 | -2.19 | -0.02 |

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
