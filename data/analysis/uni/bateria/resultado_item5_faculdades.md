# BLK-UNI-10, item 5 — faculdade muito próxima (protocolo da bateria §9.9 + §15 + §16 + §17, congelado antes de rodar)

D500 = 1 se há pelo menos um CNPJ ativo com CNAE principal de ensino superior (8531-7, 8532-5, 8533-3), com endereço exato ou por CEP, a até 500 m do pino da unidade, com início antes da data de decisão (01/01/2025 no laboratório e no treino; a inauguração no teste e na turma). Receita Federal, set/2026: só CNPJ ativo hoje.

## Laboratório Smart Fit (teste primário; bilateral)

- Funil: {'painel KPI (Siglas)': 961, 'nivel 2025 (idade >= 12 m, >= 6 meses)': 708, 'com coordenada (crosswalk nome + UF)': 652, 'isocrona compartilhada por 2 Siglas (vira circulo)': 0, 'isocrona real nao truncada': 394, 'circulo (sem isocrona, truncada ou compartilhada)': 258, 'raio do circulo (m)': 5061, 'com pop/domicilios/renda': 650, 'em area (metro ou municipio) com >= 2': 578}.
- Áreas de comparação: 48 (454 unidades em metrô, 124 em município); isócrona real 385, círculo 193. Maior área com 31% do N.
- Com faculdade a ≤ 500 m: 55% das unidades (318 de 578); indeterminadas (sem faculdade precisa a ≤ 500 m, mas com faculdade imprecisa a ≤ 1,5 km): 51.
- G* (mínimo entre ρ 0 e ρ 1): 10 km 13.3; 10s km 21.9; 15 km 5.2; 15s km 17.9; 20 km 4.6; 20s km 5.3; 30 km 5.0; 30s km 3.0. p primário = o maior entre as quadrículas com G* ≥ 10 (10, 10s, 15s km; 's' = deslocada), que é o da 10 km (§17).
- Coeficiente de D500: **-0.029** → **-2.8% de alunos** com faculdade a ≤ 500 m, contra sem; n = 578.
- **p de decisão (bilateral; wild cluster bootstrap restrito, Webb, B = 9999): 0.1918.** Por quadrícula: 10 km p(coef > 0) 0.9042, p(coef < 0) 0.0959; 10s km p(coef > 0) 0.9059, p(coef < 0) 0.0942; 15s km p(coef > 0) 0.9440, p(coef < 0) 0.0561. R² LOO com efeito fixo: 0.212 → 0.212.
- Robustez (§16.5): sem a maior área -0.025 (resiste); com log(1 + filiais a ≤ 500 m) -0.020 (resiste).
- c1: **não significativo**.

## Sensibilidades do laboratório (descritivas; cluster 10 km)

| versão | n | com | coef. | efeito | p (coef > 0) | p (coef < 0) | G* |
|---|---|---|---|---|---|---|---|
| sem a maior área (metro_0) — obrigatória | 398 | 57% | -0.025 | -2.5% | 0.8639 | 0.1362 | 17.1 |
| controle: log(1 + filiais de CNPJ a ≤ 500 m, sem ensino superior e sem academia) — obrigatória | 578 | 55% | -0.020 | -1.9% | 0.7784 | 0.2217 | 30.6 |
| sem as indeterminadas (51) | 523 | 60% | -0.023 | -2.3% | 0.8333 | 0.1668 | 15.5 |
| CNPJ ou universidade do OSM a ≤ 500 m (união) | 578 | 58% | -0.022 | -2.2% | 0.8270 | 0.1731 | 12.5 |
| a ≤ 300 m | 578 | 38% | -0.030 | -2.9% | 0.9420 | 0.0581 | 22.1 |
| a ≤ 1 km | 578 | 80% | -0.044 | -4.3% | 0.9637 | 0.0364 | 19.8 |
| distância contínua: log(3 km / distância), piso 50 m (por +1) | 578 | — | -0.022 | — | 0.9730 | 0.0271 | 23.6 |
| só endereço exato (CEP + número) | 578 | 42% | -0.029 | -2.9% | 0.9456 | 0.0545 | 14.6 |
| todo nível com coordenada | 578 | 56% | -0.018 | -1.8% | 0.7982 | 0.2019 | 14.2 |
| só graduação (8531 + 8532) | 578 | 51% | -0.027 | -2.7% | 0.8839 | 0.1162 | 14.1 |
| universidade mapeada no OSM (foto set/2026, sem data) | 578 | 22% | -0.031 | -3.1% | 0.9423 | 0.0578 | 8.8 |
| referência: contagem na isócrona de 10 min, log(1 + n) (medida original, G* < 10) | 578 | — | +0.009 | — | 0.3127 | 0.6874 | 6.6 |
| cluster = quadrícula de 15 km (G* < 10) | 578 | 55% | -0.029 | -2.8% | 0.9230 | 0.0771 | 5.2 |
| cluster = quadrícula de 20 km (G* < 10) | 578 | 55% | -0.029 | -2.8% | 0.9505 | 0.0496 | 4.6 |
| cluster = quadrícula de 20 km deslocada (G* < 10) | 578 | 55% | -0.029 | -2.8% | 0.9113 | 0.0888 | 5.3 |
| cluster = quadrícula de 30 km (G* < 10) | 578 | 55% | -0.029 | -2.8% | 0.9161 | 0.0840 | 5.0 |
| cluster = quadrícula de 30 km deslocada (G* < 10) | 578 | 55% | -0.029 | -2.8% | 0.9598 | 0.0403 | 3.0 |
| cluster = área (metrô ou município) | 578 | 55% | -0.029 | -2.8% | 0.9149 | 0.0852 | 6.8 |
| só isócronas reais (sem círculos) | 381 | 56% | -0.037 | -3.6% | 0.8943 | 0.1058 | 10.3 |
| só dentro das áreas metropolitanas | 454 | 56% | -0.025 | -2.5% | 0.8394 | 0.1607 | 11.6 |
| controles de idade (12–23 meses) e franquia | 578 | 55% | -0.030 | -3.0% | 0.9154 | 0.0847 | 13.3 |

Tirando uma área com ≥ 20 unidades por vez (coeficiente): sem metro_0: -0.025, sem metro_5: -0.025, sem metro_1: -0.039, sem mun_2304400: -0.027, sem metro_4: -0.029. Mesmo sinal em 5 de 5.

## Ultra (57 unidades, pinos corrigidos)

- Com faculdade a ≤ 500 m: treino 18 de 39, teste 11 de 18; indeterminadas 7.
- Efeito de D500 (empilhado, cluster por metrô; descritivo): +0.130 → +13.9% de faturamento; p (coef > 0) 0.1968, p (coef < 0) 0.8033; HC3 IC 90% -2.7% a +33.4%.
- Pinos de confiança baixa ou nenhuma nas 57: 0 (a sensibilidade sem eles coincide com o principal).
- c2/c3 (v2 contra v2 + D500; só relatados, o laboratório não passou): coeficiente nas 39 +0.164 (IC 90% -0.017 a +0.345) — sinal diferente do laboratório; estúdios +0.227 → +0.249.
  LOO 23.5% → 25.4% (queda -1.9 pp; IC 90% -7.6 a +3.0); teste 22.1% → 27.1% (queda -5.0 pp; IC 90% -8.2 a +8.6; 7 de 18 melhoram; recentrado -8.1 pp); viés +0.3% → +6.1%; deslocamento +3.0%; queda nas mais perto de faculdade -6.7 pp, nas mais longe +4.0 pp.

**Veredito do item 5: NÃO DEMONSTRADO no laboratório (não vai à Ultra).**

## Turma de 2026 congelada

`previsoes_turma_2026_v2_F.csv`: 16 unidades, 8 com faculdade a ≤ 500 m; γ̂ (Ultra) = +0.130. SHA-256 `57f04169fc0af0842393016fb9d6a466f4250d696b24c3acd88690baa15b68da`.
Conferência (§17): junto com o BLK-UNI-12, quando ≥ 10 das 16 tiverem 12 meses de vida e ≥ 3 meses válidos. Métrica: a diferença média do resíduo da v2 congelada entre quem tem e quem não tem faculdade a ≤ 500 m, comparada a γ̂ (o sinal bate? o IC 90% do contraste cobre γ̂?); a `prev_v2dom_x_F` só conta se o erro típico dela vencer o da `prev_v2dom_mesmo_nivel`.

