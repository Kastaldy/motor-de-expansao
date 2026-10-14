# Passo 2 formal — efeito praça de Manaus pela Smart Fit (protocolo §12 + emenda v1.3 §13)

Base Ultra: v2 em ativos com master média na isócrona real = **2,532** (faixa 80% 1,685–3,966); central M3 (teto de cenário) = 2,958. Inclinações da v2: renda domiciliar +0.218, população -0.113. Pesos por `iso_metro` (39 unidades; divergências contra a regra da caixa: 0).

## Casamento

Smart Fit com desfecho (≥ 6 meses em 2025, no painel até 2024-12): 789. Casadas: 329 (42%); coordenada inválida (limite por cidade = máx(40 km, p95)): 2 {'AM': 1, 'SP': 1}; válidas: 327; válidas em cidade com 1 parceiro só: 2. Diagnóstico: das 460 não casadas, 1 casariam com as palavras ordenadas.
AM por situação: Jardim Amazonas = não casada; Amazonas Shopping = não casada; Ponta Negra = válida; Flores = válida; Assaí Manaus Grande Circular = coordenada inválida; Avenida Torquato Tapajós = válida; Shopping Manaus ViaNorte = válida; Alvorada = válida; Cidade Nova = válida; Cachoeirinha = válida.

Círculo de 4.97 km: 375 arquivos, 204,138 setores (0 pontos inválidos fora); com atributos: 327 (quedas por grupo: nenhuma).
Manaus casadas (n=7): população mediana 481,825 (DP do log 0.16); renda domiciliar mediana R$ 4,359 (DP do log 0.25). Demais: 414,556 e R$ 4,859. Imputação das não casadas: médias das casadas.

## Efeito praça (r) e número alternativo = 2,532 × r

| versão | n | Manaus | peso Ultra coberto | r (IC90 bootstrap; IC90 t-HC3) | alt (IC mais largo) | inclinações Smart Fit | reamostras válidas/descartadas | categoria |
|---|---|---|---|---|---|---|---|---|
| (i-todas) sem controles | 330 | 10 | 95% | r 1.42 (boot 1.25–1.60; t 1.21–1.65) | **3,588** (3,076–4,185) | – | 2000/0 | A |
| (i-casadas) sem controles | 327 | 7 | 95% | r 1.54 (boot 1.35–1.72; t 1.30–1.82) | **3,894** (3,288–4,611) | – | 2000/0 | A |
| **(ii-casadas)** | 327 | 7 | 95% | r 1.54 (boot 1.34–1.74; t 1.28–1.84) | **3,892** (3,250–4,662) | renda_dom +0.019, pop +0.080 | 2000/0 | A |
| **(ii-todas-imputada)** | 330 | 10 | 95% | r 1.38 (boot 1.19–1.58; t 1.15–1.64) | **3,483** (2,914–4,165) | renda_dom +0.019, pop +0.075 | 2000/0 | B |
| **(ii-offset, casadas)** | 327 | 7 | 95% | r 1.74 (boot 1.53–1.96; t 1.47–2.06) | **4,409** (3,718–5,229) | – | 2000/0 | A |
| **(ii-offset, todas-imputada)** | 330 | 10 | 95% | r 1.58 (boot 1.39–1.79; t 1.35–1.86) | **4,006** (3,410–4,707) | – | 2000/0 | A |
| (ii-casadas) sem as com < 12 meses | 246 | 2 | 87% | r 1.71 (boot 1.53–1.88; t 1.08–2.71) | **4,324** (2,727–6,856) | renda_dom -0.026, pop +0.056 | 2000/0 | B |
*(sensibilidade sem as com < 12 meses: Manaus abaixo do portão de 5 — não interpretar.)*

Inclinações da v2 para comparar: renda domiciliar +0.218, população -0.113.
**Veredito do Passo 2 (o menos favorável das 4 versões principais): B — acima do modelo (média), sem chegar ao teto de cenário.** Na síntese do §11, o Passo 2 conta como: **neutro**.

## Idade: Manaus por dentro × coeficientes nacionais

Manaus (log médio por faixa, n): id_le8 8.28 (n=3); id_9_11 8.23 (n=2); id_12_17 8.44 (n=3); referência 7.92 (n=2).
Coeficientes nacionais (ii-todas-imputada): id_le8 -0.11; id_9_11 -0.00; id_12_17 -0.00; id_18_23 -0.11.

## Descritivos

- Cidade Nova: 2025-01 3,441; 2025-04 4,213; 2025-07 3,374; 2025-10 3,266; 2025-11 3,310; 2025-12 3,215; 2026-01 3,137.
- Amazonas Shopping: 2023-01 2,853; 2023-04 3,016; 2023-07 2,959; 2023-10 2,763; 2024-01 2,859; 2024-04 3,153; 2024-07 3,210; 2024-10 3,371; 2025-01 3,156; 2025-04 3,175; 2025-07 2,774; 2025-10 2,569; 2025-11 2,645; 2025-12 2,555; 2026-01 2,719.
- Jardim Amazonas: 2023-01 2,325; 2023-04 2,353; 2023-07 2,419; 2023-10 2,279; 2024-01 2,357; 2024-04 2,422; 2024-07 2,494; 2024-10 2,617; 2025-01 2,717; 2025-04 2,719; 2025-07 2,704; 2025-10 2,520; 2025-11 2,525; 2025-12 2,390; 2026-01 2,485.
- Isócrona de 10 min do pino: base de concorrentes {'live': 7, 'bluefit': 1}; Smart Fit válidas do painel dentro: 3.
- Distância do pino (km): Alvorada 6.4; Ponta Negra 10.1; Avenida Torquato Tapajós 2.9; Cidade Nova 0.4; Shopping Manaus ViaNorte 3.9; Flores 3.1; Cachoeirinha 10.2.


## Adendo pós-verificação (2026-09-30)

Duas lentes adversariais, só leitura, revisaram o resultado. Depois delas veio uma checagem exploratória, pós-hoc.

**Conta:** o resultado bate com o código. O veredito B ("acima do modelo, sem chegar a 3.000 com 90%") e o "neutro" no
§11 estão corretos.

**Desvio de método:** a Assaí, que tem coordenada inválida, foi imputada também na (ii-todas-imputada), contra o
§13.1. O r mexe ~0,01 e continua B.

**Declarações que faltavam:**
- a alavancagem 1 zerada no HC3 e no bootstrap (grupos com 1 unidade não variam);
- a faixa de 80% da v2 × r: somando o erro da v2, a faixa da unidade fica em ~2.200 a 5.500.

**Leitura (muda):**
- **O prêmio vem das 8 Smart Fit abertas em 2024** (~4.100 alunos cada). As 2 antigas (Amazonas Shopping e Jardim
  Amazonas) ficam no nível nacional desde 2023 (r ≈ 1,0).
- Portanto, praça e "leva de entrada da Smart Fit em Manaus" não se separam. O mais provável é demanda reprimida,
  absorvida pela expansão de 2 para 15 unidades entre 2024 e 2026.
- **O total da Smart Fit inclui o TotalPass** (mesmo grupo). Aplicando o r só ao balcão, a unidade daria ~2.800 a
  3.400.
- **A concorrência perto do pino é mais densa que a média da cidade:**
  - 7 unidades da Live, 1 da Bluefit e 3 Smart Fit do painel na isócrona de 10 min;
  - a Cidade Nova a 0,4 km;
  - a Cidade Manoa, a 0,8 km, desde dez/2025.

**Checagem exploratória da queda no fim de 2025** (razão entre nov/25–jan/26 e a mediana de 2025):
- Brasil: 0,911 (antigas 0,904; abertas no fim de 2024, 0,999);
- **Manaus: 0,940**.
- A queda do fim de 2025 é **sazonal nacional**, e Manaus caiu menos.
- No nível recente (nov/25–jan/26), Manaus tem 3.690 alunos por unidade contra 2.457 no Brasil (razão 1,50).
- A objeção "a janela de 2025 é a mais favorável" **não se confirma**.

**Número de trabalho proposto:** ~3.000, com faixa de trabalho de 2.500 a 3.500.
- 3.500 é o cenário otimista: supõe que a Ultra capture o prêmio inteiro da praça.
- 2.500 é o cenário em que o prêmio é só efeito da leva de entrada da Smart Fit.
- O mês 3 decide: revisar para cima se fechar com 3.105 ativos ou mais.
