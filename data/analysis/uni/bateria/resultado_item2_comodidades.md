# BLK-UNI-10, item 2 — qualidade da concorrência (protocolo da bateria §9.9 + §13 + §14 + §15, congelado antes de rodar)

Q = fração das academias **listadas no Wellhub** na isócrona de 10 min de carro (ou círculo de raio equivalente) com vestiário, chuveiro e armário, entre as que declararam comodidades; sem a própria rede. Foto da planilha: 29/09/2026 (SHA `07abe5684bf8…`).

## Laboratório Smart Fit (teste primário; direção esperada: negativa)

- Funil: {'painel KPI (Siglas)': 961, 'nivel 2025 (idade >= 12 m, >= 6 meses)': 708, 'com coordenada (crosswalk nome + UF)': 652, 'isocrona compartilhada por 2 Siglas (vira circulo)': 0, 'isocrona real nao truncada': 394, 'circulo (sem isocrona, truncada ou compartilhada)': 258, 'raio do circulo (m)': 5061, 'com pop/domicilios/renda': 650, 'em area (metro ou municipio) com >= 2': 578}.
- Áreas de comparação: 48 (454 unidades em metrô, 124 em município); isócrona real 385, círculo 193. Maior área com 31% do N.
- G* (mínimo entre ρ 0 e ρ 1) por quadrícula: 10 km 15.3; 15 km 14.4; 20 km 8.5; 30 km 3.8. Usado: cluster = quadrícula de 15 km dentro da área (§15).
- Coeficiente de Q: **-0.040** em log de alunos por +1 de Q → **-0.4% de alunos por +10 p.p.** de concorrência completa; n = 574, 0 sem Q.
- **p unilateral (coef < 0; wild cluster bootstrap restrito, Webb, B = 9999): 0.3002.** p CR1 (gl G − 1) 0.3045; lado oposto (descritivo) 0.6999. R² LOO com efeito fixo: 0.220 → 0.217.
- Robustez (§15): sem a maior área +0.049 (NÃO resiste); com log(1 + nº de academias Wellhub) -0.066 (resiste).
- c1: **não significativo**.

## Sensibilidades do laboratório (descritivas)

| versão | n | coef. | p (coef < 0) | G* |
|---|---|---|---|---|
| sem a maior área (metro_0) — obrigatória | 394 | +0.049 | 0.7053 | 10.3 |
| controle: log(1 + nº de academias Wellhub na isócrona) — obrigatória | 574 | -0.066 | 0.2131 | 15.9 |
| cluster = quadrícula de 10 km | 574 | -0.040 | 0.3367 | 15.3 |
| cluster = quadrícula de 10 km deslocada | 574 | -0.040 | 0.3247 | 27.1 |
| cluster = quadrícula de 15 km deslocada | 574 | -0.040 | 0.3331 | 7.6 |
| cluster = quadrícula de 20 km | 574 | -0.040 | 0.3447 | 8.5 |
| cluster = quadrícula de 20 km deslocada | 574 | -0.040 | 0.3305 | 5.6 |
| cluster = quadrícula de 30 km | 574 | -0.040 | 0.3571 | 3.8 |
| cluster = quadrícula de 30 km deslocada | 574 | -0.040 | 0.3342 | 7.4 |
| cluster = área (metrô ou município) | 574 | -0.040 | 0.3948 | 3.7 |
| só isócronas reais (sem círculos) | 378 | -0.075 | 0.2066 | 11.2 |
| só dentro das áreas metropolitanas | 452 | -0.063 | 0.2359 | 12.1 |
| controle: log(1 + nº de Smart Fit na isócrona, pelo site da rede) | 574 | -0.040 | 0.2971 | 14.5 |
| controle: fração de vizinhas vindas do TotalPass | 574 | -0.045 | 0.2835 | 14.4 |
| controles de idade (12–23 meses) e franquia | 574 | -0.057 | 0.2322 | 14.1 |

Tirando uma área com ≥ 20 unidades por vez (coeficiente): sem metro_0: +0.049, sem metro_5: -0.137, sem metro_1: -0.042, sem mun_2304400: -0.068, sem metro_4: -0.036. Mesmo sinal em 4 de 5.

## Ultra (57 unidades, pinos corrigidos)

- Efeito principal de Q (empilhado, cluster por metrô; descritivo): -0.449 → -4.4% por +10 p.p.; p (coef < 0) 0.0268.
- **Hipótese do diretor (interação m² × Q, descritiva, fora do Holm):** -0.071; p (coef < 0) 0.4626; p (coef > 0) 0.5375. Negativo = o tamanho rende menos onde a concorrência é completa. Diferença de elasticidade do m² entre Q no p25 e no p75: -0.01.
- c2/c3 (v2 contra v2 + Q; só relatados, o laboratório não passou): coeficiente nas 39 -0.476 (IC 90% -1.255 a +0.303); estúdios +0.227 → +0.222.
  LOO 23.5% → 22.3% (queda +1.2 pp; IC 90% -4.8 a +4.1); teste 22.1% → 26.4% (queda -4.3 pp; IC 90% -8.9 a +7.3; 11 de 18 melhoram; recentrado -6.1 pp); viés +0.3% → +2.9%; deslocamento +5.3%; queda com Q acima da mediana +0.2 pp, abaixo -3.4 pp.

**Veredito do item 2: NÃO DEMONSTRADO no laboratório (não vai à Ultra).**

## Turma de 2026 congelada

`previsoes_turma_2026_v2_Q.csv`: 16 unidades, 15 com Q; γ̂ (Ultra) = -0.449. SHA-256 `1159b1b639a3691acbc69d74208a36f2159b5cb22df7c7c8fe87b3915d9dea8a`.
Conferência: a inclinação do resíduo da v2 congelada sobre (Q − média) dentro da turma, comparada a γ̂; a `prev_v2dom_x_Q` só conta se vencer a `prev_v2dom_mesmo_nivel`.

