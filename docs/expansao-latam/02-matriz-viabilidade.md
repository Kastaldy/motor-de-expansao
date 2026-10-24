# 02 — Matriz de viabilidade e ordem de entrada

- **Data:** 2026-10-16 · **Status:** ANÁLISE. A ordem recomendada é a **proposta DEC-073/D10**, e quem decide é o dono.
- **Insumos:** `00-baseline-argentina.md` (esforço), `01-consolidacao-auditoria.md` (valores canônicos e veredito por camada), dossiês e anexos.

---

## 1. Matriz país × critério

### 1.1 Disponibilidade de dados por camada

| Camada | CO | MX | PE | PY |
|---|---|---|---|---|
| Identidade | Completa | Completa | Completa | Completa |
| 1 Potencial | Parcial (pop 2018 reescalada; renda por estrato) | **Pop Completa** / renda Parcial (calibrada no município) | Parcial (forma 2017, nível 2025) | Parcial fraca (distrito; Asunción por barrio) |
| 2 Residual | Parcial | Parcial | Parcial | Parcial fraca |
| 3 Pressão | Parcial (agregadores locais Fitpass/Fitpal) | **Completa** (DENUE + WellHub + TotalPass) | Parcial (sem agregador) | Parcial fraca |
| 4 Momentum | Parcial (municipal) | Parcial | Parcial (intercensal real) | Parcial fraca (só demografia) |
| 5 Fila | Parcial | Parcial | Parcial | Parcial fraca |
| Relatório Pontual | **Geometria fina** (manzana) | Geometria boa (AGEB) | Geometria sem download | Pseudossetor fora de Asunción |
| Viabilidade | Parcial | Parcial (COF) | Parcial | Parcial |
| Imobiliário | Inviável | Inviável | Inviável | Parcial |

### 1.2 Os cinco critérios (nota 1 = pior, 5 = melhor)

| Critério (peso) | CO | MX | PE | PY | O que sustenta a nota |
|---|---|---|---|---|---|
| **Dados por camada** (30 %) | 3,5 | **4,5** | 3,0 | 2,0 | Tabela 1.1. MX tem população medida até manzana, renda medida no município e concorrência oficial georreferenciada. PY para no distrito e perdeu o único proxy fino (RWI é NC) |
| **Atratividade de mercado** (25 %) | 3,5 | **4,0** | 3,5 | 1,5 | População: MX 130,9 M · CO 53,4 M · PE 34,2 M · PY 6,1 M. Penetração de 5,6–6,9 % nos três maiores (espaço de crescimento contra o "potencial de 15 %" citado pela própria Smart Fit no PE). **Smart Fit por milhão: PE 2,8 (menos saturado) · PY 3,1 · MX 3,7 · CO 4,3 (mais saturado).** O MX desconta pela concorrência HVLP (Planet Fitness 50, Anytime 110+). PY: teto estimado de **3–8 unidades Ultra** em 3–5 anos |
| **Esforço técnico** (20 %; 5 = menor) | 3,0 | 2,0 | 2,5 | **4,5** | Fatores contra a AR: MX 1,2–1,4 · PE 1,1–1,3 · CO 0,9–1,1 · PY 0,5–0,7 (`04-roadmap.md` §0.1). MX e PE exigem `mascara.ts` (R8); PE exige obter a geometria de manzana |
| **Risco regulatório** (10 %; 5 = menor) | 3,5 | 2,5 | **4,0** | 3,0 | MX: COF transforma a viabilidade em informação pré-contratual com responsabilidade; LFDA contra contornar anti-bot. CO: retenção de 20 % + IVA sobre royalty sem tratado vigente; RUES com dado pessoal. PE: tratado em vigor, sem lei de franquia. PY: Lei 194/93 sem parecer e sem tratado |
| **Dependência de proxies** (15 %; 5 = menor) | 3,0 | **3,5** | 3,0 | 2,0 | Renda é modelada nos 4 (nenhum censo pergunta renda). MX calibra em renda medida; CO usa estrato observado; PE é validável pelos Planos Estratificados; PY depende de prédios validados em 67 barrios. Penetração: série única HFA/Mercado Fitness em CO, MX e PE; **decisão** no PY |
| **Nota ponderada** | **3,33** | **3,53** | **3,13** | **2,48** | — |

### 1.3 Sensibilidade da nota aos pesos (autoauditoria)

A matriz é uma régua de discussão, não um resultado. A ordem entre MX e CO **depende do peso do esforço**:

| Cenário de pesos (dados/atrat./esforço/reg./proxies) | MX | CO | PE | PY | 1º lugar |
|---|---|---|---|---|---|
| Base (30/25/20/10/15) | **3,53** | 3,33 | 3,13 | 2,48 | MX |
| Prazo primeiro (25/20/35/10/10) | 3,23 | **3,28** | 3,03 | 2,88 | **CO** (empate técnico) |
| Mercado primeiro (25/40/15/10/10) | **3,63** | 3,38 | 3,23 | 2,28 | MX |
| Risco primeiro (25/20/15/25/15) | **3,38** | 3,35 | 3,28 | 2,53 | MX (empate técnico com CO e PE) |

**Leitura honesta:**
- O **PY é o último em qualquer peso**.
- MX, CO e PE ficam a ±0,2 entre si na maioria dos cenários, ou seja, a nota não os separa com folga. Quem decide a ordem entre eles é o **objetivo do programa**:
  - maior prêmio e melhor dado → MX;
  - primeiro país novo no ar mais rápido → CO;
  - menor risco jurídico → empate dos três, com o PE subindo.

---

## 2. Esforço técnico estimado (baseline AR)

| | CO | MX | PE | PY |
|---|---|---|---|---|
| Pipeline do país (MVP) | 5–7 sem | 8–10 sem | 6–8 sem | 3–5 sem |
| Subida (DNS, compose, perfil, medição) | 1 sem | 1 sem | 1 sem | 1 sem |
| Cauda de correções | 2–3 sem | 2–3 sem | 2–3 sem | 1–2 sem |
| Completo (camada 4, viabilidade local, coleta recorrente) | +3–5 sem | +4–6 sem | +3–5 sem | +2–3 sem |
| Hex servidos / acionáveis (gate por captação) | ~13,3 mil / ~7,4 mil | ~41,4 mil / ~22,5 mil | ~11,8 mil / ~4,9 mil | ~2,5 mil / ~1,0 mil |
| Prereqs de plataforma além do núcleo | — | R8 (máscara), COF/DEC-073/D6 para a viabilidade | R8, geometria INEI | — |

Mais a plataforma uma vez (F0 + F1 + F1b + F1c, ~5 semanas de calendário em paralelo) e a viabilidade multi-regime (3–5 semanas de engenharia + 3–6 semanas humanas por país). Tudo é **estimativa** sobre o baseline AR, com o defeito conhecido de a AR ter usado spec executável e IA e de **não** ter orçado a cauda.

---

## 3. Atratividade de mercado: números de apoio

| | CO | MX | PE | PY |
|---|---|---|---|---|
| População (2025–2026) | 53,4 M (projeção) | 130,9 M (EIC 2025) | 34,2 M (Censo 2025) | 6,1 M (Censo 2022) |
| Penetração | 6,9 % (3 % em sensibilidade) | 5,6 % | 6 % | 3–5 % (decisão) |
| Sócios estimados | ~3,6 M | ~7,2 M | ~2,1 M | ? |
| Smart Fit (abertas / pipeline) | 232 / 245 | 488 / 526 | 95 / 101 | 19 / 19 |
| Smart Fit por milhão | 4,3 | 3,7 | **2,8** | 3,1 |
| Outros low-cost/HVLP relevantes | Bodytech/Athletic (~90, 2022), Spinning Center 18, Stark 7 | Planet Fitness 50, Anytime 110+, Sports World 49 (premium) | b2 8–9, Sportlife 3–7, Bodytech **saiu** em 2024 | BIGG ≥4, EXEN ≥4, Premier 2 |
| Ticket Smart Fit básico | ~US$ 28 / Int$ 54 | ~US$ 22 / Int$ 35 | ~US$ 27 / Int$ 47 | ~US$ 29–40 |
| Receita líquida / preço | 84,0 % | 86,2 % | 84,7 % | 90,9 % |
| Juro de política | **12,25 %** (subindo) | 6,50 % | 4,25 % | 5,50 % |

---

## 4. Recomendação de ordem de entrada (proposta DEC-073/D10)

### **1º México → 2º Colômbia → 3º Peru → 4º Paraguai (sob demanda, só metros)**

**Por que o México primeiro:**
1. **É o maior prêmio e tem o melhor dado.**
   - População medida até manzana, mais a Intercensal 2025.
   - Renda modelada sobre renda **medida** no município.
   - Concorrência **oficial e georreferenciada** (DENUE: 30.242 academias com lat/lng e porte).
   - WellHub e TotalPass presentes, o que deixa reaproveitar a cadeia brasileira de agregadores e M&A.
   - Num país só, o motor tem as camadas 1 e 3 mais fortes dos quatro.
2. **O MX é o melhor país para validar o kit de pipeline**, porque tem dado limpo. Um defeito encontrado ali é do kit, não do dado. O inverso (estrear o kit no PY) confundiria as duas coisas.
3. **Os riscos do MX não estão no MVP.** A COF e a premissa fiscal mordem só a `viabilidade`, que no MX não liga sem premissas assinadas (DEC-073/D6). O MVP é `mapa` + camadas 1–3.
4. **A Smart Fit tem 488 unidades lá**, o que dá o teste de falso-veto com mais poder estatístico (§5).

**Por que a Colômbia em segundo:**
- Tem a **melhor geometria** (manzana com estrato observado) e o tamanho da AR.
- Usa a mesma gramática numérica do BR, então **não depende do R8**.
- Os agregadores locais (Fitpass, Fitpal) melhoram a camada 3, ainda sujeitos aos termos.
- Contras:
  - censo de 2018;
  - **país mais saturado de Smart Fit** (4,3 por milhão);
  - IVA de 19 % e o juro mais alto (12,25 %) apertam o payback;
  - royalty sem tratado vigente.
- **Alternativa legítima:** se o objetivo do dono for *ter o primeiro país novo no ar o quanto antes*, a CO vem **antes** do MX (empate técnico no cenário "prazo primeiro"). Com duas pessoas de pipeline, MX e CO rodam **em paralelo** e a pergunta some.

**Por que o Peru em terceiro:**
- O **menos saturado** de Smart Fit (2,8 por milhão; Bodytech saiu).
- Tratado com o Brasil em vigor, menor risco jurídico.
- UBIGEO casa nativamente.
- **Entrar depois tem valor:** dá tempo para o INEI publicar a manzana e os microdados do Censo 2025, e para obter a geometria de manzana por pedido formal (iniciar o pedido **já** na F1).
- Contras: sem agregador e com gramática decimal invertida.

**Por que o Paraguai por último, e sob demanda:**
- O mercado comporta ~17–26 unidades low-cost no país inteiro, e a Smart Fit já tem 19. A folga estimada é de 3–8 unidades Ultra em 3–5 anos.
- O dado intraurbano é o mais fraco e o único proxy fino é proibido para uso comercial.
- **O motor completo pode custar mais que a decisão que ele informa.**
- Recomendação: **instância só se o time de Expansão confirmar apetite**, e então só Gran Asunción, CDE metropolitana e Encarnación (3–5 partições). Antes disso, um **estudo de mesa** sobre o mesmo dado (sem instância) pode responder a pergunta.
- Ponto a favor que não aparece na nota: proximidade operacional com o Brasil (fronteiras CDE–Foz e PJC–Ponta Porã, reais circulando). A demanda de brasileiros em CDE e PJC **não é medida** por fonte alguma.

---

## 5. Como validar o modelo em país sem unidade Ultra (proposta DEC-073/D9)

**Princípio (DEC-041; a DEC-043 foi revogada pela DEC-078 em 21/10/2026):** o funil é **triagem**, não previsão. Nenhum país novo é "validado" por acerto de faturamento. A validação mede só o que a triagem promete:
- **não vetar praça boa** (falso-veto);
- **ordenar de forma estável**;
- **não ter defeito de dado grosseiro.**

Cinco gates, pré-registrados **antes** de medir (molde do E6/E7):

| # | Gate | Como | Critério de aprovação (proposta; o valor é decisão do dono antes da medição) |
|---|---|---|---|
| 1 | **Validador semântico** | `validar_pacote_pais.py` (DEC-073/D1) | Verde nos 3 níveis |
| 2 | **Sensibilidade de âncoras** | 4 conjuntos de âncoras candidatas, como na AR | Top-30 compartilhado ≥ 25/30 e Spearman ≥ 0,95. Se falhar, a âncora vira decisão explícita do dono |
| 3 | **Falso-veto com a Smart Fit** | Localizar as unidades abertas (MX 488, CO 232, PE 95, PY 19) pelo site/sitemap e medir a fração que cai em hexágono "frio" (score < corte **ou** captação < 5.000) | Fração ≤ teto declarado antes da medição. **Calibrar o teto no Brasil primeiro:** rodar o mesmo teste no BR, onde existem 1.025 Smart Fit **e** a rede Ultra, para saber que taxa de falso-veto um motor "bom" produz |
| 4 | **Teste prospectivo e de ordenação** | (a) Backtest: aberturas da Smart Fit 2021–2025 (série do RI: MX 403 → 488 em 12 meses) contra a fila calculada com dado do ano-base. (b) **Prospectivo:** as unidades em **pré-venda** hoje (CO +13, MX +38, PE +6) são registradas como previsão **antes** de abrirem, e daqui a 6–12 meses se mede onde caíram | Fração das aberturas no terço superior da fila acima do acaso, com IC declarado. Leitura de ordenação, não de desempenho |
| 5 | **Ranking cego com o time local** | 20–30 praças em 2 cidades por país, ranqueadas por quem conhece a praça **antes** de ver o mapa | Spearman como **diagnóstico**. Toda divergência grande vira revisão de dado caso a caso (o tipo "Bariloche com renda alta e ninguém morando") |

**Outras validações complementares:**
- **Redes de mesmo segmento como segundo teste de falso-veto:**
  - MX: Planet Fitness (50), Anytime (110+);
  - CO: Bodytech/Athletic, Spinning Center;
  - PE: b2.
- **Verdade de chão de renda, onde existe:**
  - PE: Planos Estratificados por manzana (245 distritos);
  - PY: SAE nos 67 barrios de Asunción;
  - MX: IMU CONAPO por AGEB e NSE AMAI (validação interna);
  - CO: estrato observado.

  Mede-se **o acerto do estrato previsto**, que é a parte que a AR não pôde medir.
- **Camada financeira:** priors derivados da rede BR + preços públicos locais, saída em faixa (P10–P90) e tornado de sensibilidade, **nunca ponto**. Carimbo "não calibrado" no PDF e no XLSX (decisão 0.7).

**Ressalvas que viajam junto, por escrito:**
1. A amostra Smart Fit é **condicionada no desfecho** (ela só abriu onde decidiu), então prova falso-veto e **não** prova acerto ao rejeitar (DEC-042).
2. **Circularidade:** a Smart Fit escolhe ponto com lógica parecida com a do motor; concordar com ela não é independência.
3. O PY, com 19 pontos, tem **poder estatístico baixo** no gate 3; lá o gate 5 pesa mais.
4. Nenhum gate aqui autoriza falar em previsão de desempenho (o funil é política declarada, DEC-041; a DEC-043 foi revogada pela DEC-078, cuja sugestão de faturamento é calibrada em unidades Ultra).

---

## 6. Premissas frágeis desta matriz

| # | Premissa | Por que é frágil |
|---|---|---|
| M1 | As notas 1–5 | São julgamento sobre evidência, não medida. A sensibilidade (§1.3) mostra que MX, CO e PE não se separam com folga |
| M2 | Fatores de esforço por país | Extrapolados de **um** caso (AR), feito por **uma** pessoa. O 1º país novo recalibra |
| M3 | Penetração "comparável" entre CO, MX e PE | A série HFA/Mercado Fitness é uma só, mas a regra de contagem de instalações por país **não foi lida** (relatório pago) |
| M4 | Teto do PY (3–8 unidades) | Benchmark de 4–6 low-cost por milhão de urbanos sobre penetração e capacidade **não verificadas** |
| M5 | "Os riscos do MX não estão no MVP" | Vale só se a `viabilidade` MX ficar **desligada** até as premissas assinadas. Se alguém ligar com carimbo provisório (como na AR), o risco vira legal |
| M6 | Atratividade ≠ estratégia | A matriz não sabe da estratégia comercial da Ultra (parceiros master-franqueados, capital, time local). Um parceiro local pronto num país muda a ordem mais que qualquer nota |
