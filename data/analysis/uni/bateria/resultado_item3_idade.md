# BLK-UNI-10, item 3 — % da população na faixa etária real dos alunos (protocolo da bateria §7 + §9.9 + §17.3 + §20 + §21, congelado antes de rodar)

Faixa pela regra pré-registrada (idade real dos alunos, Growth, 62 unidades com peso igual, sem o teste e a turma): **20-49 anos**, que reúne 66% dos alunos. F = população de 20-49 anos / população com faixa, na área de 10 min de carro (ou círculo), pelos setores do Censo 2022 (células de sigilo recuperadas pelo total do setor).

**Como ler (§21):** F sobe sobretudo onde há menos pessoas com 50 anos ou mais. Um positivo quer dizer "áreas com estrutura etária menos envelhecida têm mais alunos", e não "população na faixa dos alunos". A composição etária, sozinha, prevê só +3.7% de alunos por +5 p.p. de F (+0.9% por DP residual), muito abaixo do que o teste enxerga; **um nulo não refuta que a idade importe**.

## Laboratório Smart Fit (teste primário; unilateral, coef > 0)

- Funil: {'painel KPI (Siglas)': 961, 'nivel 2025 (idade >= 12 m, >= 6 meses)': 708, 'com coordenada (crosswalk nome + UF)': 652, 'isocrona compartilhada por 2 Siglas (vira circulo)': 0, 'isocrona real nao truncada': 394, 'circulo (sem isocrona, truncada ou compartilhada)': 258, 'raio do circulo (m)': 5061, 'com pop/domicilios/renda': 650, 'em area (metro ou municipio) com >= 2': 578}.
- No modelo: n = 578 em 48 áreas. Maior área com 31% do N. F: mediana 46.2% (p10 43.7%, p90 48.9%); DP residual 1.2 p.p.
- G* (mínimo entre ρ 0 e ρ 1): 10 km 7.5; 10s km 12.6; 15 km 5.9; 15s km 5.4; 20 km 6.1; 20s km 7.1; 30 km 3.4; 30s km 4.7. p primário = o maior entre as quadrículas com G* ≥ 10 (10s km; 's' = deslocada), que é o da 10s km (§17.3).
- Coeficiente de F: **+0.426** → **+2.2% de alunos por +5 p.p.** (+0.5% por DP residual); n = 578.
- **p de decisão (unilateral, coef > 0; wild cluster bootstrap restrito, Webb, B = 9999): 0.3099** (limiar efetivo do Holm 0.0083). Por quadrícula: 10s km p(coef > 0) 0.3099, p(coef < 0) 0.6902. R² LOO com efeito fixo: 0.212 → 0.210.
- Guardas (§21): sem a maior área -1.956 (NÃO resiste); com oferta e centralidade +0.422 (resiste); cluster por área p 0.4486, grade de 30 km p 0.4212.
- c1: **não significativo**.

## Sensibilidades do laboratório (descritivas; p da grade de 10 km, NÃO comparável ao p de decisão)

| versão | n | coef. | efeito por +5 p.p. | p (coef > 0) | p (coef < 0) | G* |
|---|---|---|---|---|---|---|
| sem a maior área (metro_0) — guarda | 398 | -1.956 | -9.3% | 0.9741 | 0.0260 | 16.1 |
| controles de oferta e centralidade (Smart Fit pelo site, Wellhub, filiais a ≤ 500 m) — guarda | 578 | +0.422 | +2.1% | 0.2930 | 0.7071 | 7.9 |
| cluster = área (metrô ou município) — guarda | 578 | +0.426 | +2.2% | 0.4486 | 0.5515 | 4.5 |
| cluster = quadrícula de 30 km — guarda | 578 | +0.426 | +2.2% | 0.4212 | 0.5789 | 3.4 |
| controle: log(moradores por domicílio) | 578 | +0.411 | +2.1% | 0.3191 | 0.6810 | 9.4 |
| só setores completos (sem recuperar células de sigilo) | 578 | +0.305 | +1.5% | 0.3664 | 0.6337 | 13.3 |
| faixa 15–49 (também a leitura por coorte: quem tinha 15–49 em 2022) | 578 | +0.420 | +2.1% | 0.3039 | 0.6962 | 11.6 |
| faixa 25–59 (a regra lida por nº de grupos) | 578 | -1.274 | -6.2% | 0.8265 | 0.1736 | 7.5 |
| faixa 20–59 | 578 | -0.378 | -1.9% | 0.6329 | 0.3672 | 8.0 |
| 20–49 entre quem tem 15 anos ou mais (interpretativa) | 578 | +0.251 | +1.3% | 0.3419 | 0.6582 | 14.8 |
| % com 60 anos ou mais (referência, direção esperada negativa) | 578 | +0.006 | +0.0% | 0.4956 | 0.5045 | 18.6 |
| % com 0 a 14 anos (referência) | 578 | +0.137 | +0.7% | 0.4500 | 0.5501 | 12.2 |
| só áreas com ≥ 90% da população com faixa (578) | 578 | +0.426 | +2.2% | 0.3144 | 0.6857 | 7.5 |
| cluster = quadrícula de 15 km (G* < 10) | 578 | +0.426 | +2.2% | 0.3805 | 0.6196 | 5.9 |
| cluster = quadrícula de 15 km deslocada (G* < 10) | 578 | +0.426 | +2.2% | 0.3216 | 0.6785 | 5.4 |
| cluster = quadrícula de 20 km (G* < 10) | 578 | +0.426 | +2.2% | 0.4159 | 0.5842 | 6.1 |
| cluster = quadrícula de 20 km deslocada (G* < 10) | 578 | +0.426 | +2.2% | 0.3268 | 0.6733 | 7.1 |
| cluster = quadrícula de 30 km deslocada (G* < 10) | 578 | +0.426 | +2.2% | 0.3604 | 0.6397 | 4.7 |
| só isócronas reais (sem círculos; também a leitura de menor erro de medida) | 381 | +0.552 | +2.8% | 0.2985 | 0.7016 | 6.9 |
| só dentro das áreas metropolitanas | 454 | +0.503 | +2.5% | 0.2890 | 0.7111 | 8.1 |
| controles de idade da unidade (12–23 meses) e franquia | 578 | +0.463 | +2.3% | 0.2989 | 0.7012 | 7.5 |

Tirando uma área com ≥ 20 unidades por vez (coeficiente): sem metro_0: -1.956, sem metro_5: +1.279, sem metro_1: +0.760, sem mun_2304400: +0.683, sem metro_4: +0.452. Mesmo sinal em 4 de 5.

## Ultra (57 unidades, pinos corrigidos)

- F: mediana 47.8% (p25 45.7%, p75 49.0%). Sem efeito fixo de área: o coeficiente mistura diferença entre cidades e regiões (parte absorvida pelas masters), outro estimando que o do laboratório.
- Efeito de F (empilhado, cluster por metrô; descritivo): -0.986 → -4.8% de faturamento por +5 p.p.; p (coef > 0) 0.6609, p (coef < 0) 0.3392; HC3 IC 90% -23.9% a +19.0%.
- c2/c3 (v2 contra v2 + F; só relatados, o laboratório não passou): coeficiente nas 39 -1.612 (IC 90% -7.364 a +4.139) — sinal diferente do laboratório; estúdios +0.227 → +0.239.
  LOO 23.5% → 24.4% (queda -0.8 pp; IC 90% -5.2 a +1.7); teste 22.1% → 22.1% (queda -0.0 pp; IC 90% -5.0 a +2.0; 9 de 18 melhoram; recentrado -2.0 pp); viés +0.3% → +2.9%; deslocamento -0.2%; queda com F acima da mediana +1.7 pp, abaixo +0.7 pp.

**Veredito do item 3: NÃO DEMONSTRADO no laboratório (não vai à Ultra); exclui efeitos de ~20% ou mais por +5 p.p., mas não refuta o efeito que a composição etária prevê (+3.7%).**

## Turma de 2026 congelada

`previsoes_turma_2026_v2_I.csv`: 16 unidades; γ̂ (Ultra) = -0.986. SHA-256 `fa40f8711aac6660e6ea43b801ede18eb90e81931573b2295aabaf7031c1182c`.
Conferência (§21): junto com o BLK-UNI-12, quando ≥ 10 das 16 tiverem 12 meses de vida e ≥ 3 meses válidos. Métrica: a inclinação do resíduo da v2 congelada sobre (F − média) dentro da turma, comparada a γ̂ (EP ≈ 0,19 por +5 p.p., detectável de ~+60%: confere quase só o nível); a `prev_v2dom_x_I` só conta se o erro típico dela vencer o da `prev_v2dom_mesmo_nivel`.

