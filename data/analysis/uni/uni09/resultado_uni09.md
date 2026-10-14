# BLK-UNI-09 — faturamento em duas partes: balcão + agregador (pré-registro uni09/protocolo_uni09.md v1.1, congelado antes de rodar)

Treino: 39 maduras de 2025; teste: 18 unidades de 2026 (UNI-02); turma: 16. s_TP = 0.371; k = +0.0151; calibração 2025→2026: balcão -0.062, agregador +0.117 (total da v2 -0.020).

## Resultado principal (faturamento total)

- **v2:** R² LOO 0.264; erro típico LOO 23.5%; teste 22.1%.
- **Duas partes:** erro típico LOO 22.2% (queda +1.3 pp; IC 90% -3.9 a +3.7); teste 22.9% (queda -0.8 pp; IC 90% -9.8 a +2.9; recentrado -0.4 pp, IC 90% -7.0 a +4.6; 11 de 18 melhoram); viés no teste +0.3% → +0.9%. (IC condicionais aos ajustes: descritivos, não decidem.)
- R² LOO de cada parte: balcão 0.412; agregador 0.317.

**Veredito do UNI-09: NÃO MELHORA — na decomposição; o aceite quase não varia nas 39/18 e é testado na turma.**

### Teste por grupo de aceite (descritivo)

| grupo | n | erro v2 | erro duas partes |
|---|---|---|---|
| aceita os dois | 15 | 19.0% | 19.6% |
| não aceita algum (cadastro) | 3 | 68.0% | 82.5% |

## Diagnóstico: coeficientes por parte (log; IC 90% HC3)

| variável | v2 (total) | balcão | agregador | balcão em volume (pagantes) | agregador em volume (contagem) |
|---|---|---|---|---|---|
| l_m2 | +0.578 [-0.02; +1.17] | +0.512 [+0.00; +1.02] | +0.970 [+0.04; +1.90] | +0.353 [-0.13; +0.83] | +0.857 [+0.07; +1.64] |
| l_renda_dom | +0.317 [+0.14; +0.50] | +0.252 [+0.09; +0.42] | +0.548 [+0.25; +0.84] | +0.144 [-0.01; +0.30] | +0.344 [+0.09; +0.60] |
| l_pop | -0.149 [-0.27; -0.02] | -0.178 [-0.28; -0.08] | -0.061 [-0.33; +0.21] | -0.154 [-0.25; -0.06] | -0.006 [-0.24; +0.23] |
| mr_M2 | +0.244 [-0.03; +0.52] | +0.088 [-0.17; +0.35] | +0.762 [+0.30; +1.23] | +0.006 [-0.24; +0.25] | +0.729 [+0.36; +1.10] |
| mr_M3 | +0.022 [-0.40; +0.45] | -0.394 [-0.66; -0.13] | +0.982 [+0.32; +1.64] | -0.466 [-0.71; -0.22] | +1.122 [+0.47; +1.77] |
| mr_outras | +0.154 [-0.15; +0.46] | -0.100 [-0.43; +0.23] | +0.866 [+0.41; +1.32] | -0.164 [-0.45; +0.12] | +0.834 [+0.37; +1.30] |
| studios | +0.227 [-0.01; +0.47] | +0.233 [+0.01; +0.46] | +0.226 [-0.13; +0.58] | +0.145 [-0.06; +0.34] | +0.168 [-0.13; +0.47] |

Leitura: sinais opostos de uma master entre balcão e agregador indicam que o efeito dela no total é composição de mix. O mr_M3 do treino vem só das unidades de SP (todas aceitam agregador).

## Sensibilidades (descritivas)

| versão | n | erro LOO v2 → duas partes | queda LOO | erro teste v2 → duas partes | queda teste | queda recentrada |
|---|---|---|---|---|---|---|
| previsão sem o fator de aceite (mesmo ajuste, fator 1) | 39/18 | 23.5% → 20.0% | +3.5 pp | 22.1% → 23.0% | -0.9 pp | -0.4 pp |
| treino sem normalizar o agregador das 2 sem TotalPass | 39/18 | 23.5% → 21.8% | +1.7 pp | 22.1% → 22.1% | +0.0 pp | +0.2 pp |
| calendário único (o do total) nas duas partes | 39/18 | 23.5% → 22.2% | +1.3 pp | 22.1% → 23.8% | -1.6 pp | -1.2 pp |
| s_TP fora de SP para quem não aceita TotalPass | 39/18 | 23.5% → 21.3% | +2.2 pp | 22.1% → 22.7% | -0.6 pp | -0.2 pp |
| Tem Saúde descontado do agregador | 39/18 | 23.5% → 22.2% | +1.3 pp | 22.1% → 22.9% | -0.8 pp | -0.4 pp |
| agregador + escritórios a pé (poi_F1; só unidades com o dado) | 38/18 | 22.6% → 23.9% | -1.3 pp | 23.1% → 24.1% | -1.0 pp | -0.5 pp |
| agregador + parceiros Wellhub e TotalPass na isócrona (foto set/2026: associação) | 39/18 | 23.5% → 23.3% | +0.2 pp | 22.1% → 20.3% | +1.8 pp | +1.0 pp |
| agregador + tier Wellhub (ordinal do cadastro, foto ago/2026) | 39/17 | 23.5% → 20.8% | +2.7 pp | 21.1% → 19.0% | +2.1 pp | -1.0 pp |

## Turma de 2026 congelada (as peças, para recombinar na conferência)

`previsoes_turma_2026_duas_partes.csv`: 16 unidades (14 com covariáveis); pelo cadastro de ago/2026, 9 sem agregador, 2 com um só. SHA-256 `38593c1d2a1a1845da6d7bf62657e5f5d17e7e3f183862242b1858a0d694cf59`.
Conferência (protocolo §11): o fator usa o aceite OBSERVADO na receita da janela; o calendário é o do ano conferido, por parte. A foto do cadastro é leitura secundária.

