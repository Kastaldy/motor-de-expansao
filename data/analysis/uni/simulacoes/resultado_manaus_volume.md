# Manaus — o volume de alunos, olhado direto (EXPLORATÓRIO, 2026-09-30)

Base: as 39 unidades maduras de treino (2025), médias mensais. 'Ativos' = alunos ativos no mês (balcão + agregador).

## 1. Quanto cada aluno ativo fatura de verdade

- Rede (2025): mediana **R$ 108** por ativo/mês (p25 R$ 96, p75 R$ 118); agregador mediano 41% dos ativos.
- Simulador (plano R$ 137, 69% balcão): R$ 115 por aluno. A conversão faturamento → alunos usada até aqui divide por esse número; se o real é R$ 108, ela conta **6% alunos a menos**.

## 2. Quantos ativos a rede tem

- Mediana 2,338; p25 1,952; p75 2,855; p90 3,716; máximo 5,900.

| unidade | m² | estúdio | ativos | faturamento/mês | R$ por ativo | agregador |
|---|---|---|---|---|---|---|
| **≥ 1.800 m²** (n=7, mediana 3,175 ativos) | | | | | | |
| PRAIA GRANDE | 2,500 | sim | 5,900 | R$ 497 mil | R$ 84 | 77% |
| SERRA | 2,200 | sim | 3,912 | R$ 385 mil | R$ 98 | 54% |
| SANTOS | 2,000 | sim | 3,706 | R$ 524 mil | R$ 141 | 43% |
| POA BARRA SUL | 2,800 | sim | 3,175 | R$ 329 mil | R$ 104 | 57% |
| LAGO NORTE | 1,800 | sim | 3,007 | R$ 412 mil | R$ 137 | 30% |
| LAGO SUL | 2,000 | não | 2,633 | R$ 294 mil | R$ 112 | 41% |
| JUNDIAI | 1,920 | não | 2,054 | R$ 184 mil | R$ 90 | 56% |
| **comparáveis de renda baixa com estúdio** (n=2, mediana 3,265 ativos) | | | | | | |
| SANTA MARIA | 1,400 | sim | 2,776 | R$ 314 mil | R$ 113 | 30% |
| SUZANO | 1,350 | sim | 3,755 | R$ 326 mil | R$ 87 | 63% |

## 3. A v2 ajustada direto em ATIVOS

R² LOO 0.074; erro típico LOO 19%.

| variável | coeficiente | Manaus | típica | contribuição |
|---|---|---|---|---|
| l_m2 | +0.529 | 2,000 | 1,500 | +16% |
| l_renda_dom | +0.218 | 3,511 | 6,080 | -11% |
| l_pop | -0.113 | 525,532 | 397,853 | -3% |
| mr_M2 | +0.280 | 0.00 | 0.26 | -7% |
| mr_M3 | +0.315 | 1.00 | 0.13 | +32% |
| mr_outras | +0.263 | 0.00 | 0.18 | -5% |
| studios | +0.161 | 1.00 | 0.59 | +7% |

**Manaus, master de RJ/SP (M3): 2,884 ativos** (faixa 80%: 1,918 a 4,517).

**Manaus, master 'outras': 2,739 ativos** (faixa 80%: 1,822 a 4,289).

Ativos medianos na rede: com estúdio 2,739, sem estúdio 2,012.

## 4. Faturamento e payback a R$ 167 (premissas corrigidas + plano de estúdio a R$ 272 em 5%)

| volume | ativos | faturamento maduro (simulador) | payback |
|---|---|---|---|
| v2 em ativos, M3 | 2,884 | R$ 421 mil | 54 |
| v2 em ativos, M3, p90 da faixa | 4,517 | R$ 656 mil | 20 |
| mediana das comparáveis | 3,265 | R$ 476 mil | 38 |
| p90 da rede | 3,716 | R$ 541 mil | 28 |

O simulador fatura R$ 139 por aluno a R$ 167 (69% de balcão); a rede real fatura R$ 108 por ativo com os preços de hoje e 41% de agregador.

