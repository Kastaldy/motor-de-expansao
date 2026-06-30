# Relatório de Validação — Demanda Revelada × Residual Fitness

> Gerado automaticamente por `validacao.py` (BLK-TP-02) em 2026-06-25 02:59 UTC.
> READ-ONLY sobre o M1. DEC-009 e DEC-012 intactas.

---

## 1. Resumo Executivo

| Correlação | rho | IC 95% | p-valor | N |
|---|---|---|---|---|
| `membros` × `score_oportunidade_residual` | **0.517** | [0.506, 0.529] | 0.0000 *** | 16,411 |
| `membros` × `oferta_efetiva_disponivel` | **0.525** | [0.513, 0.536] | 0.0000 *** | 16,411 |

**Interpretação:** rho = 0.517 (primário) confirma correlação positiva entre
demanda revelada e residual fitness. Valor esperado ~+0,52 ± 0,05 (dado arredondamento de
coords ~1 km da fonte). Correlação secundária (×`oferta_efetiva_disponivel`) esperada ~+0,75.

---

## 2. Metodologia

**Fontes de dados:**
- `data/staging/demanda_revelada_h3.parquet` — demanda paga agregada por hex H3 res-7
  (BLK-TP-01 / DEC-012). Colunas usadas: `hex_id`, `membros`.
- `data/staging/hexagonos_mercado_mapeado.parquet` — camada de mercado/residual.
  Colunas usadas: `hex_id`, `score_oportunidade_residual`, `oferta_efetiva_disponivel`, `uf`.
- `data/staging/brasil_priorizados.parquet` — recorte top-20%/UF do M1 (READ-ONLY).
  Usado apenas para derivar o flag `top_m1_20pct` (presença no frame = True).

**Join:** inner join demanda × mercado em `hex_id` (preserva ~16k hexes com ambos os lados;
descarta ~99% do universo M1 sem cobertura de demanda revelada → camada de refino sobre
metrópoles, NÃO cobertura nacional). Left join posterior com priorizados para `top_m1_20pct`.

**Quadrantes:** definidos pelas medianas de `score_oportunidade_residual`
(0.00) e `membros` (7):
- Q1: residual ≥ mediana E membros ≥ mediana
- Q2: residual ≥ mediana E membros < mediana
- Q3: residual < mediana E membros ≥ mediana
- Q4: residual < mediana E membros < mediana

**Correlação:** Spearman ρ via `scipy.stats.spearmanr`. IC 95% via transformação de Fisher
analítica (para N > 10.000) ou bootstrap `scipy.stats.bootstrap` com `n_resamples=9999`.

**Caveats obrigatórios:**
1. Cobertura ~1% do universo M1 (~16,411 hexes com join vs. ~1,54 M hexes totais).
2. Concentração geográfica em SP (fonte majoritariamente urbana metropolitana).
3. Arredondamento de coords ~1 km na fonte → ruído no join res-7 (hex pode diferir 1 nível).
4. Join parcial: hexes sem demanda revelada ficam fora desta análise.
5. `brasil_priorizados.parquet` pode estar ausente localmente (gitignored); flag
   `top_m1_20pct` = False para todos nesse caso.

---

## 3. Resultados Spearman Primário

**`membros` × `score_oportunidade_residual`**

- rho = **0.5174** ***
- IC 95%: [0.5061, 0.5285]
- p-valor: 0.000000
- N: 16,411 hexes

**Interpretação:** IC não atravessa zero → correlação positiva estatisticamente
significativa entre demanda revelada e o score de oportunidade residual do Motor.
Isso valida que hexes com mais membros (demanda paga) tendem a ter maior residual fitness,
confirmando a consistência da camada paralela de mercado.

---

## 4. Resultados Spearman Secundário

**`membros` × `oferta_efetiva_disponivel`**

- rho = **0.5245** ***
- IC 95%: [0.5133, 0.5355]
- p-valor: 0.000000
- N: 16,411 hexes

**Interpretação:** correlação com `oferta_efetiva_disponivel` (alunos de capacidade
disponível estimada) tende a ser mais forte que com o score normalizado, pois as
magnitudes em alunos têm escala mais diretamente comparável à demanda revelada.

---

## 5. Mapa de Quadrantes

**Limiares:** residual = 0.00 | demanda (membros) = 7

| Quadrante | N hexes | % do join |
|---|---|---|
| Q1 | 8,352 | 50.9% |
| Q2 | 8,059 | 49.1% |
| Q3 | 0 | 0.0% |
| Q4 | 0 | 0.0% |

**Legenda:**
- **Q1** (residual+ & demanda+): oportunidades convergentes — alto residual fitness E alta demanda observada.
- **Q2** (residual+ & demanda−): subdemandados no dado revelado mas com residual alto.
- **Q3** (residual− & demanda+): alta demanda mas residual baixo (mercado mais saturado/coberto).
- **Q4** (residual− & demanda−): hexes fora do foco operacional.

---

## 6. Divergências vs. M1

### 6.1 Q1 fora do top-20%/UF (potencial subvalorizado pelo M1 executivo)

Hexes com alta demanda E alto residual fitness que **NÃO** estão no recorte top-20%/UF do M1.
Total: **1,997 hexes**. Hipótese: mercado local relevante mas score M1 insuficiente
(renda/pop menores na agregação municipal) — confirma que o M1 é camada executiva (município),
não intraurbana.

| hex_id | uf | membros | score_oportunidade_residual | oferta_efetiva_disponivel |
| --- | --- | --- | --- | --- |
| 87a810063ffffff | SP | 3610 | 100.00 | 13391.70 |
| 87a8a06c4ffffff | RJ | 3578 | 100.00 | 7705.21 |
| 87a81044dffffff | SP | 3149 | 100.00 | 10851.04 |
| 87a8a39b5ffffff | RJ | 2921 | 100.00 | 9960.12 |
| 87a810060ffffff | SP | 2786 | 100.00 | 7444.92 |
| 87a8a39a6ffffff | RJ | 2655 | 0.00 | 0.00 |
| 87a8a0651ffffff | RJ | 2533 | 100.00 | 12405.10 |
| 87a8a2a60ffffff | RJ | 2497 | 100.00 | 6714.76 |
| 87a8a0690ffffff | RJ | 2458 | 100.00 | 3692.83 |
| 87a8a065affffff | RJ | 2391 | 100.00 | 6746.64 |

### 6.2 Top-20%/UF fora de Q1 (eventual sobreestimação ou cobertura parcial)

Hexes priorizados pelo M1 que **NÃO** se classificam como Q1 no cruzamento com demanda revelada.
Total: **3,500 hexes**. Hipótese de causa: (a) demanda revelada é parcial —
cobre só usuários de benefício corporativo (SmartFit/TotalPass), não toda a demanda fitness;
(b) concentração geográfica da fonte em SP subestima demanda em outras UFs; (c) caveat de
arredondamento de coords ~1 km pode deslocar o hex de match.

| hex_id | uf | score_oportunidade_residual | membros |
| --- | --- | --- | --- |
| 87806a76effffff | AP | 100.00 | 5 |
| 87806a76cffffff | AP | 100.00 | 1 |
| 8781851a5ffffff | AL | 100.00 | 1 |
| 878005555ffffff | PI | 100.00 | 5 |
| 878183d6bffffff | PE | 100.00 | 3 |
| 878183b32ffffff | PE | 100.00 | 4 |
| 878000716ffffff | PI | 100.00 | 1 |
| 87806a762ffffff | AP | 100.00 | 3 |
| 8780008e2ffffff | PI | 100.00 | 1 |
| 8781858b4ffffff | AL | 100.00 | 4 |

---

## 7. Guardrails e Proibições

**DEC-009 (intacta):** a demanda entra como insumo OBSERVADO, NUNCA como preditor
geográfico de magnitude. É PROIBIDO:
- Usar `membros` ou qualquer coluna desta camada como input em regressão geográfica de demanda.
- Usar `membros` como ajuste do `score_priorizacao` (pesos `renda=0.40`/`pop=0.60` inalterados).
- Reintroduzir "20% fixo" ou qualquer predição de magnitude de alunos por geografia.

**DEC-001 (intacta):** pesos `renda=0.40`/`pop=0.60` e fórmula `score_priorizacao`
**INALTERADOS**. Nenhum artefato M1 foi tocado neste relatório.

**DEC-012 (intacta):** `src/motor_expansao/demanda_revelada/` é pacote DISJUNTO.
Nenhuma importação de `pipelines/m1/`, `censo_*` ou `dashboard/`.

**Anti-PII:** parquet de quadrantes (`quadrantes_demanda_residual.parquet`) não contém
nenhuma coluna de `COLUNAS_PII_PROIBIDAS`. Validação automática em `salvar_quadrantes_parquet`.

**Próximos passos (blocos BLK-TP-03..05):** os sucessores podem usar a camada de quadrantes
como insumo de refino intraurbano sobre metrópoles — nunca para recalibrar o M1.
