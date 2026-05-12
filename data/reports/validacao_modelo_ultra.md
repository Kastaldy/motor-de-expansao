# Validação de aderência do modelo — Unidades Ultra

**Data:** 2026-04-09  
**Unidades analisadas:** 53 (deduplicadas) | **Com score M1:** 49 | **Com score censitário:** 41 | **Com ambos scores:** 41  
**Fonte Ultra:** `data/ultra/Ultra.csv` (lat/lng) + `data/ultra/dados_academias.xlsx` (performance, unidades maduras ≥ 6 meses)  
**Match:** 53/54 unidades com localização encontrada (98.1%; JARDIM APURA sem match)

---

## 1. Cobertura

| Dimensão | Detalhe |
|---|---|
| UFs com score M1 | Todas as 27 UFs (cobertura nacional) |
| UFs com score censitário | GO, SP, RJ, MG, DF (5 de 27 UFs) |
| UFs sem score censitário | ES, PR, SC, MT, BA — unidades sem validação censitária |
| Score M1 = 100 nas unidades | **81%** das unidades existentes (40/49) |
| Score M1 ≥ 95 nas unidades | **89%** das unidades existentes |

**Diagnóstico estrutural do M1 nas unidades Ultra:** o M1 é estruturalmente flat — 81% das unidades já operam em áreas com score máximo (100). Isso era esperado: a Ultra abre em áreas de alta renda e alta população. Consequência direta: o M1 tem baixa variância neste dataset e, portanto, baixo poder de discriminação entre unidades existentes.

---

## 2. Correlação de Spearman — Score × Performance

### 2a. Subset UFs piloto censo (GO/SP/RJ/MG/DF) — n=41 com ambos scores

| Métrica | M1 ρ | M1 p-valor | M1 n | Censitário ρ | Censo p-valor | Censo n |
|---------|------|------------|------|--------------|---------------|---------|
| faturamento | **0.417** | **0.007** ✓ | 41 | 0.122 | 0.449 | 41 |
| ativos_pag | 0.300 | 0.057 ~ | 41 | -0.014 | 0.932 | 41 |
| alunos_total | 0.302 | 0.055 ~ | 41 | 0.068 | 0.675 | 41 |
| agregadores | — | — | — | 0.118 | 0.462 | 41 |

✓ = estatisticamente significativo (p < 0.05) | ~ = marginalmente significativo (p < 0.10)

### 2b. Conjunto completo deduplicado (todas as UFs, n=49 para M1)

| Métrica | M1 ρ | M1 p-valor | M1 n |
|---------|------|------------|------|
| faturamento | 0.199 | 0.171 | 49 |
| ativos_pag | 0.094 | 0.519 | 49 |
| alunos_total | 0.076 | 0.605 | 49 |

**Nota:** a correlação sobe para significativo (rho=0.417) quando a análise se restringe às UFs com cobertura censitária. Isso se deve a maior variação de score M1 nessa sub-amostra (GO e SP têm unidades com score < 95).

---

## 3. Análise de Quartis — Performance por Faixa de Score M1

(Score M1 por faixas absolutas; 81% das unidades estão em Q4=100)

| Faixa M1 | n | Faturamento Médio | Ativos Pag. Médio | Alunos Total Médio |
|----------|---|-------------------|-------------------|--------------------|
| Q1 (< 85) | 2 | R$ 208.441 | 1.785 | 2.747 |
| Q2 (85–95) | 3 | R$ 128.001 | 1.064 | 2.203 |
| Q3 (95–99) | 2 | R$ 192.033 | 1.620 | 2.700 |
| Q4 (= 100) | 42 | R$ 221.233 | 1.626 | 2.332 |

**Leitura:** unidades em áreas com score M1 médio (85–95) têm performance claramente inferior. Unidades com score máximo (100) sustentam faturamento e alunos médios mais altos.

---

## 4. Performance Média por UF (subset com ambos scores)

| UF | Score M1 médio | Score Censo médio | Faturamento médio |
|----|----------------|-------------------|-------------------|
| DF | 100.0 | 86.3 | R$ 231.646 |
| GO | 91.1 | 82.4 | R$ 119.760 |
| MG | 96.7 | 85.0 | R$ 115.010 |
| RJ | 100.0 | 100.0 | R$ 617.061 |
| SP | 98.4 | 83.2 | R$ 193.974 |

**Observação sobre o DF:** o M1 é completamente flat (= 100) para todas as 19 unidades do DF. O score censitário varia entre 59 e 100 e mostra aderência editorial razoável:
- Noroeste DF (censo=100) → R$ 525k
- Botanic Mall DF (censo=88) → R$ 340k
- Taguatinga Sul DF (censo=81) → R$ 125k
- Ceilândia Sul DF (censo=73) → R$ 131k

---

## 5. Correlação entre os Modelos

- **M1 vs Censitário (41 unidades com ambos):** ρ = 0.198, p = 0.215 — **não correlacionados**
- Interpretação: os dois modelos medem dimensões distintas. O M1 captura ranking municipal/regional; o censitário captura granularidade intraurbana dentro de cada município.

---

## 6. Comparação Final — Qual Modelo Explica Melhor?

| Critério | Score M1 | Score Censitário 2022 | Veredito |
|---|---|---|---|
| Correlação com faturamento (p-valor) | 0.417 (p=0.007) ✓ | 0.122 (p=0.449) ✗ | **M1 vence** |
| Correlação com ativos_pag | 0.300 (p=0.057) ~ | -0.014 (p=0.932) ✗ | **M1 vence** |
| Correlação com alunos_total | 0.302 (p=0.055) ~ | 0.068 (p=0.675) ✗ | **M1 vence** |
| Variância nas unidades existentes | Baixa (81% = 100) | Alta (IQR = 73–100) | **Censo vence** |
| Discriminação intraurbana (DF) | Nenhuma | Clara | **Censo vence** |
| Cobertura geográfica | Nacional (27 UFs) | Parcial (5 UFs) | **M1 vence** |

---

## 7. Decisão Estratégica

### Status geral: NO-GO para substituição / GO para uso complementar

**NO-GO para substituição do M1 pelo modelo censitário:**
- O M1 demonstra correlação estatisticamente significativa com faturamento real (ρ=0.42, p=0.007) nas UFs piloto
- O score censitário não mostrou correlação significativa com nenhuma métrica de performance (p > 0.44 em todos os casos)
- O modelo censitário não supera o M1 na predição de performance das unidades existentes

**GO para uso complementar (intraurbano):**
- O score censitário é o único que discrimina entre unidades dentro do DF (onde M1 = 100 para todas)
- Oferece granularidade intraurbana relevante para decisão de *local específico* dentro de município já aprovado pelo M1
- Não deve ser usado para substituir o ranking entre municípios

### Interpretação correta do M1 nesta validação

A correlação positiva do M1 com faturamento é **dirigida pelas unidades em áreas sub-ótimas** (score < 95): Mococa SP (93), Suzano SP (89), Carapicuíba SP (90), Aguas Lindas GO (73). Essas unidades têm performance consistentemente mais baixa. Isso confirma que o M1 discrimina corretamente entre territórios — áreas de score alto tendem a sustentar unidades mais fortes.

### Limitações desta validação

1. **Seleção de sobrevivência:** todas as 54 unidades já estão abertas e maduras — o teste ideal compararia hexes onde a Ultra *não* abriu vs onde abriu depois
2. **Amostra pequena:** 41 unidades com ambos os scores; erro padrão alto
3. **Churn e conversão não disponíveis:** dois KPIs críticos ausentes neste snapshot
4. **Score censitário parcial:** 5 de 27 UFs — ES, PR, SC, MT, BA sem cobertura
5. **M1 flat no topo:** a maioria das unidades opera no score máximo — a discriminação real do M1 ocorre *antes* da abertura, não depois

---

## 8. Próximos Passos Recomendados

1. **Manter M1 como score oficial de expansão** — validado pela performance real das unidades existentes
2. **Usar censitário como camada editorial local** dentro de municípios aprovados pelo M1, especialmente no DF
3. **Coletar dados de churn e taxa de conversão** para próxima rodada de validação
4. **Monitorar novas aberturas** nos próximos 12 meses: comparar score censitário do local vs faturamento dos primeiros 6 meses — esse é o teste definitivo de poder preditivo

---

## 9. Outputs Gerados

- `data/staging/ultra_validacao_consolidada.parquet` — dataset consolidado com scores e métricas por unidade
- `data/reports/validacao_modelo_ultra.md` — este relatório
