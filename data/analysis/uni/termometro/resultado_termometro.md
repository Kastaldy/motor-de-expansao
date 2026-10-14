# Termômetro de praça pela Smart Fit (protocolo v1.0 + emenda v1.1)

Insumos: painel `KPIs_Smart_2025_02 (1).xlsx` (SHA `d74fda3ef0dc…`), base da VPS `concorrentes_mapeados_2026-09-27.parquet` (SHA `7923a2b74053…`).
Casamento nome + UF: 895 de 961 Smart Fit do painel (93%; 832 têm ≥ 6 meses em 2025). Smart Fit da base sem UF pelo hexágono: 7. Trava contra o TotalPass: 482 casadas nos dois, 0.8% a > 1 km (limite 2%).
Nível 2025 (meses com idade ≥ 12, ≥ 6 meses): 708 Smart Fit; mediana nacional = referência do termômetro relativo.

Cobertura T5: treino 32/39 ({'ok': 32, 'sem Smart Fit no raio': 4, 'cobertura < 50%': 3}); teste 15/18 ({'ok': 15, 'sem Smart Fit no raio': 2, 'cobertura < 50%': 1}). Coordenada de baixa confiança: treino 0, teste 0.

## Resultado principal (faturamento, v2 + T5 com indicador de ausência, nas 39 / 18)

Reprodução da v2: R² LOO 0.264, erro no teste 22.1% ✓.
- Coeficiente de T: **-0.688** (IC 90% t, gl 29: -1.750 a +0.373) — cada +10% de alunos na Smart Fit vizinha (relativo ao nacional) ≈ -6.4% no faturamento.
- Erro típico LOO: v2 23.5% → v2+T 21.6% (queda +1.9 pp; IC 90% bootstrap pareado -7.0 a +5.0 pp). R² LOO 0.264 → 0.240.
- Teste (18, T de antes da abertura): erro típico v2 22.1% → v2+T 25.6% (queda -3.4 pp); viés +0.3% → +2.5%; 5 de 18 com |erro| menor; Spearman +0.69 → +0.35.
- Leave-one-metro-out (relatado): 44.8% → 50.9%. Largura da faixa de 80% (LOO): 93 → 92 pontos percentuais.
- v2 nas unidades sem T: LOO 18.3% (n=7); teste 18.7% (n=3).
- Ativos (secundário): coeficiente -0.789; erro LOO 18.9% → 20.6%; teste 17.8% → 16.9%.

Critério: c1 não; c2 (≥ 2 pp no LOO) não; c3 (≥ 2 pp no teste) não. → **NÃO MELHORA**.

## Sensibilidades (descritivas; não mudam o veredito)

| versão | cobertura treino/teste | coef. T | erro LOO v2 → v2+T | erro teste v2 → v2+T |
|---|---|---|---|---|
| T10 | 33/15 | -0.194 | 23.5% → 23.0% | 22.1% → 21.1% |
| T3 | 33/15 | +0.240 | 23.5% → 23.6% | 22.1% → 27.9% |
| T5_pre (só Smart Fit anteriores à Ultra) | 17/15 | -0.990 | 23.5% → 23.8% | 22.1% → 24.8% |
| T5 sem a regra de cobertura | 32/15 | -0.688 | 23.5% → 21.6% | 22.1% → 25.6% |
| T5 + controle nº de Smart Fit a 5 km | 32/15 | -0.812 | 21.9% → 21.6% | 25.4% → 29.0% |
| só unidades com T (masters < 3 → outras: nenhuma) | 32/15 | -0.658 | 24.8% → 21.3% | 25.5% → 28.6% |

## Manaus (descritivo)

- T5 do pino (2025): +0.59 (1 Smart Fit; ok) = +81% de alunos contra a Smart Fit mediana do país; percentil no treino 100 — **acima do máximo do treino (extrapolação)**.
- Sem a leva de 2024 (só Smart Fit no painel até 2023-12): – (0 Smart Fit).
- Faturamento, M3: v2 R$ 241 mil → v2+T R$ 130 mil (nível 2025); com calendário 2026: R$ 236 mil → R$ 127 mil.
- Faturamento, master média: v2 R$ 259 mil → v2+T R$ 153 mil (nível 2025); com calendário 2026: R$ 254 mil → R$ 150 mil.
- Ativos, M3: v2 2,958 → v2+T 1,466 (nível 2025); com calendário 2026: 2,870 → 1,423.
- Ativos, master média: v2 2,532 → v2+T 1,394 (nível 2025); com calendário 2026: 2,457 → 1,353.

## Turma de 2026 congelada (teste limpo futuro)

`previsoes_turma_2026_v2T.csv`: 16 unidades, 12 com termômetro de antes da abertura; SHA-256 `9561c2bdb9cb8e9e290c3556a9a0c82d4373c0c647559e1298e3b5f9fea1acc1`.


## Adendo pós-verificação (2026-09-30)

A verificação adversarial (só leitura) **não achou bug**, e o veredito **NÃO MELHORA se mantém**. Ela corrige a leitura
em quatro pontos.

- **"Sem sinal útil" é o que se sustenta. O coeficiente negativo NÃO deve ser lido como disputa.**
  - O T do treino é o nível da Smart Fit em 2025, com a Ultra já aberta ao lado: uma Ultra forte tira aluno da
    vizinha (causalidade reversa).
  - O sinal também muda com o raio: T3 dá +0,24, e T10 dá −0,19.
- **O ganho de 1,9 pp no LOO é ruído.** O IC vai de −7 a +5 pp. O R² LOO cai, o leave-one-metro-out piora, e só 5 de 18
  unidades de teste melhoram.
- **Manaus está fora do suporte.** O T5 do pino vem de 1 Smart Fit só, acima do máximo do treino. Além disso, a regra
  de idade ≥ 12 meses exclui a leva de 2024, que era a fonte do prêmio medido no teste formal de Manaus. Por isso:
  - **não há base na rede para transferir o prêmio da Smart Fit de Manaus para a Ultra, nem para negá-lo**;
  - a queda para R$ 130 mil é extrapolação e **não deve ser usada**.
- **A previsão congelada da turma de 2026 com o termômetro (v2T)** muda os números em até ±50% e serve só como teste
  futuro.
