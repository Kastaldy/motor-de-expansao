# BLK-UNI-10, item 4 — visibilidade objetiva do ponto (protocolo da bateria §7 + §9.9 + §17.3 + §18 + §19, congelado antes de rodar)

A30 = 1 se o pino da unidade fica a até 30 m do eixo de uma via arterial do OSM (primária, secundária ou expressa trunk; acessos *_link não entram). OpenStreetMap de set/2026, grafo do pipeline de isócronas.

## Laboratório Smart Fit (teste primário; unilateral, coef > 0)

- Funil: {'painel KPI (Siglas)': 961, 'nivel 2025 (idade >= 12 m, >= 6 meses)': 708, 'com coordenada (crosswalk nome + UF)': 652, 'isocrona compartilhada por 2 Siglas (vira circulo)': 0, 'isocrona real nao truncada': 394, 'circulo (sem isocrona, truncada ou compartilhada)': 258, 'raio do circulo (m)': 5061, 'com pop/domicilios/renda': 650, 'em area (metro ou municipio) com >= 2': 578, 'com >= 1 km de margem no grafo viario': 514}.
- No modelo: n = 513 em 39 áreas (453 unidades em metrô, 60 em município); isócrona real 385, círculo 128. Maior área com 35% do N.
- De frente para arterial (≤ 30 m): 40% das unidades (205 de 513); em shopping (≤ 50 m do polígono) 113.
- G* (mínimo entre ρ 0 e ρ 1): 10 km 32.3; 10s km 19.6; 15 km 23.2; 15s km 12.8; 20 km 17.0; 20s km 15.0; 30 km 8.0; 30s km 4.3. p primário = o maior entre as quadrículas com G* ≥ 10 (10, 10s, 15, 15s, 20, 20s km; 's' = deslocada), que é o da 15 km (§17.3).
- Coeficiente de A30: **-0.009** → **-0.9% de alunos** de frente para arterial, contra não; n = 513.
- **p de decisão (unilateral, coef > 0; wild cluster bootstrap restrito, Webb, B = 9999): 0.7206.** Por quadrícula: 10 km p(coef > 0) 0.6775, p(coef < 0) 0.3226; 10s km p(coef > 0) 0.6928, p(coef < 0) 0.3073; 15 km p(coef > 0) 0.7206, p(coef < 0) 0.2795; 15s km p(coef > 0) 0.6793, p(coef < 0) 0.3208; 20 km p(coef > 0) 0.6672, p(coef < 0) 0.3329; 20s km p(coef > 0) 0.6529, p(coef < 0) 0.3472. R² LOO com efeito fixo: 0.202 → 0.198.
- Robustez (§18.4 + §19): sem a maior área +0.002 (NÃO resiste); com log(1 + filiais a ≤ 500 m) -0.010 (resiste); com o controle de shopping -0.001 (NÃO resiste). O controle de shopping tende a subir o coeficiente por construção (§19), então resistir a ele não é corroboração.
- c1: **não significativo**.

## Sensibilidades do laboratório (descritivas; p da grade de 20 km, NÃO comparável ao p de decisão)

| versão | n | com | coef. | efeito | p (coef > 0) | p (coef < 0) | G* |
|---|---|---|---|---|---|---|---|
| sem a maior área (metro_0) — obrigatória | 333 | 41% | +0.002 | +0.2% | 0.4544 | 0.5457 | 14.5 |
| controle: log(1 + filiais de CNPJ a ≤ 500 m) — obrigatória | 513 | 40% | -0.010 | -1.0% | 0.6877 | 0.3124 | 16.6 |
| controle: em shopping (≤ 50 m do polígono) — obrigatória | 513 | 40% | -0.001 | -0.1% | 0.5079 | 0.4922 | 18.4 |
| sem as unidades em shopping (113) | 392 | 44% | +0.010 | +1.0% | 0.3728 | 0.6273 | 15.5 |
| controle: shopping a ≤ 150 m (regra do POI) | 513 | 40% | -0.001 | -0.1% | 0.5140 | 0.4861 | 18.6 |
| só pinos concordantes (site × TotalPass ≤ 50 m; 144) | 133 | 41% | -0.010 | -1.0% | 0.5757 | 0.4244 | 9.0 |
| a ≤ 15 m | 513 | 14% | -0.031 | -3.0% | 0.8203 | 0.1798 | 10.6 |
| a ≤ 50 m | 513 | 55% | -0.014 | -1.4% | 0.7290 | 0.2711 | 13.5 |
| a ≤ 100 m | 513 | 71% | +0.015 | +1.5% | 0.3045 | 0.6956 | 13.5 |
| distância contínua: log(300 m / distância), piso 10 m (por +1) | 513 | — | -0.009 | — | 0.8098 | 0.1903 | 10.7 |
| com os acessos (*_link) | 513 | 41% | -0.012 | -1.2% | 0.7225 | 0.2776 | 16.4 |
| com as terciárias | 513 | 53% | +0.001 | +0.1% | 0.4737 | 0.5264 | 8.8 |
| esquina (≥ 3 segmentos de via de quadra de ≥ 2 vias, a ≤ 30 m) | 513 | 20% | -0.009 | -0.9% | 0.6184 | 0.3817 | 16.6 |
| arterial E esquina | 513 | 13% | -0.028 | -2.7% | 0.8617 | 0.1384 | 9.5 |
| margem ≥ 5 km no grafo viário (502) | 502 | 40% | -0.009 | -0.9% | 0.6714 | 0.3287 | 16.7 |
| cluster = quadrícula de 30 km (G* < 10) | 513 | 40% | -0.009 | -0.9% | 0.7054 | 0.2947 | 8.0 |
| cluster = quadrícula de 30 km deslocada (G* < 10) | 513 | 40% | -0.009 | -0.9% | 0.6966 | 0.3035 | 4.3 |
| cluster = área (metrô ou município) | 513 | 40% | -0.009 | -0.9% | 0.6978 | 0.3023 | 5.2 |
| só isócronas reais (sem círculos) | 381 | 41% | -0.013 | -1.3% | 0.6985 | 0.3016 | 10.2 |
| só dentro das áreas metropolitanas | 453 | 41% | -0.009 | -0.9% | 0.6581 | 0.3420 | 15.3 |
| controles de idade (12–23 meses) e franquia | 513 | 40% | -0.011 | -1.1% | 0.7086 | 0.2915 | 16.5 |

Tirando uma área com ≥ 20 unidades por vez (coeficiente): sem metro_0: +0.002, sem metro_5: -0.020, sem metro_1: -0.005, sem metro_4: -0.007. Mesmo sinal em 3 de 4.

## Ultra (57 unidades, pinos corrigidos)

- De frente para arterial (≤ 30 m): treino 13 de 39, teste 4 de 18; em shopping 8.
- Efeito de A30 (empilhado, cluster por metrô; descritivo): -0.010 → -1.0% de faturamento; p (coef > 0) 0.5305, p (coef < 0) 0.4696; HC3 IC 90% -18.1% a +19.6%.
- Só pinos de confiança alta (53 de 57): -0.002 → -0.2%; p (coef > 0) 0.5083.
- c2/c3 (v2 contra v2 + A30; só relatados, o laboratório não passou): coeficiente nas 39 +0.039 (IC 90% -0.202 a +0.281) — sinal diferente do laboratório; estúdios +0.227 → +0.215.
  LOO 23.5% → 22.6% (queda +0.9 pp; IC 90% -2.9 a +1.2); teste 22.1% → 21.8% (queda +0.3 pp; IC 90% -1.7 a +1.2; 7 de 18 melhoram; recentrado +0.3 pp); viés +0.3% → +0.4%; deslocamento -0.1%; queda nas mais perto de arterial -1.6 pp, nas mais longe -0.0 pp.

**Veredito do item 4: NÃO DEMONSTRADO no laboratório (não vai à Ultra).**

## Turma de 2026 congelada

`previsoes_turma_2026_v2_V.csv`: 16 unidades, 5 de frente para arterial; γ̂ (Ultra) = -0.010. SHA-256 `b07e528ad4f13aa79075650098c91ee4bef7fb9e8385eee14b73a86b7bab805c`.
Conferência (§19): junto com o BLK-UNI-12, quando ≥ 10 das 16 tiverem 12 meses de vida e ≥ 3 meses válidos. Métrica: a diferença média do resíduo da v2 congelada entre quem está e quem não está de frente para arterial (5 contra 11; EP ≈ 0,16, detectável de ~+50%: confere quase só o nível), comparada a γ̂, também sem o pino de confiança baixa; a `prev_v2dom_x_V` só conta se o erro típico dela vencer o da `prev_v2dom_mesmo_nivel`.

