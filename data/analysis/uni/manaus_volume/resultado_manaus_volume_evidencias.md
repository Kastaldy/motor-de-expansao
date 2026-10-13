# Manaus — o volume de ~2.900 alunos: evidências (protocolo v1.1, congelado antes de rodar)

## Passo 0 — número central

Treino: 39 unidades. Reprodução do número congelado (M3, círculo): 2,884 ✓.
Isócrona real (10 min de carro): área 55.3 km², população 388,488, renda per capita R$ 1,039, renda domiciliar (proxy da v2) R$ 3,373, truncada: não → substitui o círculo no central.

| master | círculo 5 km | isócrona real | faixa 80% (central) |
|---|---|---|---|
| M3 (master de RJ/SP) | 2,884 | 2,958 | 1,968 a 4,633 |
| outras | 2,739 | 2,809 | 1,869 a 4,400 |
| M1 (referência DF/GO) | 2,105 | 2,159 | 1,436 a 3,382 |
| média da rede | 2,469 | 2,532 | 1,685 a 3,966 |

**Central direto (M3): 2,958 ativos.**

## Passo 0c — central por componentes (balcão ÷ (1 − mix))

v2 em log(balcão), 39 unidades: coeficiente de M3 -0.466 (em ativos: +0.315). Agregador mediano nas unidades M3: 61% (rede 41%).
Balcão previsto para Manaus: **968** (M3); 1,413 (master média).
Central por componentes: mix 30% → 1,383; **mix 43% (padrão 'outros') → 1,698**; mix 55% → 2,151 ativos.

## Passo 1 — ativos ajustados ao porte (2.000 m²)

Universo: 60 maduras (2025-01 a 2026-08); com metragem oficial e renda: 54. Ajuste: ativos × (2.000/m²)^0.529. Pré-checagem |ativos − (balcão + agregador)| / ativos: mediana 1.2%.
Ativos ajustados no universo: mediana 2,622; p75 3,378; p90 3,999; máximo 5,378; ≥ 3,500: 13 de 54.
Renda baixa = domiciliar ≤ R$ 4,088 (Manaus R$ 3,373), n = 18: ≥ 3,500 ajustado: 4 → maior. Controle negativo (terço superior, n = 18): 7 → maior. **Veredito: MAIOR.**
Sensibilidade com renda per capita: maior.

| praça de renda baixa | UF | m² | renda dom. | ativos | ativos ajust. 2.000 m² | balcão | agregador |
|---|---|---|---|---|---|---|---|
| SUZANO | SP | 1,350 | R$ 3,426 | 3,573 | 4,400 | 1,174 | 2,444 |
| GUARUJA | SP | 943 | R$ 3,856 | 2,809 | 4,182 | 1,237 | 1,584 |
| CARIACICA | ES | 1,300 | R$ 2,953 | 3,187 | 4,003 | 1,776 | 1,451 |
| SERRA | ES | 2,200 | R$ 3,918 | 3,835 | 3,647 | 1,676 | 2,166 |
| SANTA MARIA | DF | 1,400 | R$ 3,769 | 2,676 | 3,232 | 1,818 | 879 |
| CAMPO LARGO | PR | 1,500 | R$ 4,039 | 2,402 | 2,797 | 1,961 | 444 |
| VALPARAISO | GO | 1,800 | R$ 3,365 | 2,645 | 2,797 | 1,808 | 872 |
| ARAPOANGA PLANALTINA | DF | 1,500 | R$ 3,316 | 2,349 | 2,735 | 1,743 | 615 |
| COTIA | SP | 750 | R$ 4,054 | 1,614 | 2,713 | 838 | 778 |
| UNAI | MG | 800 | R$ 3,899 | 1,574 | 2,557 | 1,022 | 509 |
| PARANOA PARQUE | DF | 2,000 | R$ 2,969 | 2,464 | 2,464 | 1,895 | 610 |
| CEILANDIA | DF | 1,500 | R$ 3,758 | 1,733 | 2,018 | 1,254 | 498 |
| MOCOCA | SP | 1,311 | R$ 3,615 | 1,561 | 1,952 | 573 | 929 |
| JARDIM APURA | SP | 1,200 | R$ 2,985 | 1,459 | 1,912 | 549 | 916 |
| BRASILANDIA | SP | 1,400 | R$ 3,836 | 1,576 | 1,904 | 650 | 898 |
| AGUAS LINDAS | GO | 1,500 | R$ 2,471 | 1,449 | 1,687 | 1,200 | 244 |
| CARAPICUIBA | SP | 1,100 | R$ 3,320 | 1,198 | 1,645 | 668 | 533 |
| CAMPO LIMPO | SP | 1,220 | R$ 3,469 | 1,212 | 1,574 | 483 | 723 |

10 maiores em ativos ajustados ao porte (universo todo):

| unidade | UF | m² | renda dom. | ativos | ajust. | balcão | agregador |
|---|---|---|---|---|---|---|---|
| PRAIA GRANDE | SP | 2,500 | R$ 4,693 | 6,052 | 5,378 | 1,382 | 4,756 |
| BOTAFOGO | RJ | 1,230 | R$ 11,393 | 4,064 | 5,257 | 4,001 | 0 |
| VILA MARIANA | SP | 1,500 | R$ 13,611 | 4,320 | 5,030 | 2,067 | 2,324 |
| SUZANO | SP | 1,350 | R$ 3,426 | 3,573 | 4,400 | 1,174 | 2,444 |
| GUARUJA | SP | 943 | R$ 3,856 | 2,809 | 4,182 | 1,237 | 1,584 |
| CARIACICA | ES | 1,300 | R$ 2,953 | 3,187 | 4,003 | 1,776 | 1,451 |
| NOROESTE | DF | 2,000 | R$ 15,109 | 3,990 | 3,990 | 2,629 | 1,540 |
| ASA NORTE | DF | 1,700 | R$ 15,769 | 3,479 | 3,792 | 2,168 | 1,433 |
| AUGUSTA | SP | 1,100 | R$ 13,425 | 2,757 | 3,783 | 536 | 2,237 |
| JARDIM BOTANICO | DF | 1,000 | R$ 13,589 | 2,582 | 3,726 | 2,100 | 567 |

Balcão (descritivo): mediana 1,271; p90 2,085; máximo 4,001.

## Passo 2 — efeito praça pela Smart Fit

Amostra: 410 Smart Fit maduras, com isócrona não truncada e ≥ 6 meses com valor em 2025. Manaus (caixa de ±12 km do pino, metrô 44): 0 antes do filtro de truncamento → **0** depois. Metrôs Ultra cobertos: 9 (95% das 39 de treino).
Alunos Smart Fit, mediana 2025: Manaus nan; metrôs das Ultra 2,732; todas 2,817. Controles (ii): log_renda_dom, log_pop, franquia, idade_12_23.

Portão (≥ 5 em Manaus): 0 → **INCONCLUSIVO**.

## Passo 3 — mercado de agregador na praça (só indica o cenário de mix)

Wellhub (musculação, sem Ultra e estúdios) por mil hab. na isócrona de 10 min: Manaus **0.033** (13 academias); rede p25 0.121 · mediana 0.175 · p75 0.204 (percentil de Manaus ≈ 0). → cenário de mix mais plausível: **30%** → 1,383 ativos pelo central por componentes.
TotalPass (à parte): Manaus 0.039 (15); rede mediana 0.122; percentil ≈ 0.
Faturamento maduro a R$ 167 + plano de estúdio: central direto 2,958 ativos, mix 43% → R$ 410 mil; componentes 1,698 ativos, mix 43% → R$ 238 mil; componentes/cenário 1,383 ativos, mix 30% → R$ 205 mil.

## Passo 4 — hipótese do diretor (só sensibilidade)

Fração de independentes: Manaus 0.60 (12 de 20); treino p10–p90 0.44–0.77.
Dentro da faixa. v2 + hipótese do diretor (M3): **2,836 ativos** (ao lado do central 2,958; não substitui).

## Passo 5 — compromisso depois de abrir

Esperado com o central 2,958: mês 1 ~2,017 (só alerta: cobertura 59%); mês 3 ~2,484; mês 6 ~2,721.
Gatilho do mês 3: revisar para CIMA se fechar com ≥ 3,105 ativos (projeção ≥ 3,698); para BAIXO se ≤ 2,012 (projeção ≤ 2,396).

## Síntese (regra do §11, fixada antes)

Passo 1: maior; Passo 2: inconclusivo. → **OS DADOS SUSTENTAM NÚMERO MAIOR**.

Ressalva: nas unidades novas com estúdio, o teto da faixa furou em 4 de 18 (BLK-UNI-08); o risco de subestimar existe e não é previsível antes de abrir.


## Adendo pós-verificação (2026-09-30)

Três lentes adversariais, só leitura, revisaram o resultado. Elas mudam a **leitura**; os números acima continuam
valendo.

### 1. O "maior" do Passo 1 não discrimina

- Na rede, 13 de 54 unidades passam de 3.500 quando ajustadas a 2.000 m². Com essa taxa-base, a regra dá "maior" em
  ~95% de qualquer terço de renda (baixo 4, médio 2, alto 7).
- O resultado mostra que 3.500 é uma **cauda possível**, coisa que a faixa de 80% já dizia. **Não** mostra que Manaus
  deve passar do central.
- As 4 unidades de renda baixa que passam têm 45–68% de agregador e balcão ≤ 1.776. Duas delas só passam pelo ajuste de
  porte: Guarujá (×1,49) e Cariacica (×1,26). Suzano caiu 52% em 2026.
- **Nenhuma praça de renda baixa com agregador ≤ 33% passa de 3.232 ajustado** (máximo em Santa Maria). A mediana
  dessas é ~2.650.
- A emenda v1.1 empurrou o rótulo para "maior". Pela v1.0, que usava balcão e a porta do Passo 3, o resultado seria
  "mantém o central".

### 2. O central direto (2.958, com a master M3) carrega a composição de agregador de SP

- As unidades da M3 no treino são todas de SP, com ~67% de agregador. No balcão, a M3 sai com −0,466.
- Com a master média da rede, o central é de **2.532**. Por componentes, a faixa coerente é de **~2.150 a 2.550**. O
  valor de 2.958 fica como teto de cenário.
- Os R$ 410 mil do Passo 3 (2.958 com 43% de agregador) combinam um total e uma divisão incompatíveis e não devem ser
  usados.

### 3. Smart Fit em Manaus (exploratório, fora do protocolo)

Mediana mensal de "Alunos Totais SF" em 2025, com 12 meses:

| unidade | entrada no painel | alunos 2025 |
|---|---|---|
| Amazonas Shopping | 2023-01 ou antes | 2.827 |
| Jardim Amazonas | 2023-01 ou antes | 2.688 |
| Flores | 2024-05 | 4.957 |
| Ponta Negra | 2024-05 | 4.822 |
| Assaí Grande Circular | 2024-06 | 4.123 |
| Shopping ViaNorte (Zona Norte) | 2024-10 | 4.493 |
| Av. Torquato Tapajós | 2024-10 | 3.129 |
| Cachoeirinha | 2024-12 | 5.118 |
| Alvorada | 2024-12 | 3.568 |
| Cidade Nova (Zona Norte) | 2024-12 | 3.408 |

- **Leitura:** a mediana das 10 é ~3.850, contra 2.717 das Smart Fit maduras do Brasil (~+40%). 8 de 10 estão acima da
  mediana nacional. As 5 que entraram no fim de 2024 estavam no **1º ano** em 2025.
- **Ressalvas:**
  - não há metragem nem controle de renda;
  - o total inclui agregador, e o TotalPass é do grupo Smart Fit. Com poucos parceiros de agregador em Manaus, esses
    usuários podem se concentrar na Smart Fit;
  - o estimador pré-registrado (efeito fixo + controles) não rodou, porque o recorte do metrô 44 (caixa de ±12 km de
    um pino, recuo de 6 km) e o crosswalk não pegam Manaus.
  - Uma conta de bolso sobre as 5 maduras dá "neutro" (alternativo ~3.480, com limite inferior ~2.860).
- **O que falta para medir direito:**
  - reconstruir a caixa do metrô 44 para cobrir a mancha urbana, com a mesma regra para os metrôs 43 e 45;
  - pré-registrar a v1.2 declarando que esta checagem já foi vista;
  - checar a cobertura do feed pelo CNAE 9313.

### 4. Leitura final

- **Pela rede Ultra:** ~2.500–3.000, com 2.958 já no topo do cenário. Em praça de renda baixa e com pouco agregador,
  a rede nunca passou de ~3.200.
- **Pela praça de Manaus (Smart Fit):** há sinal de volume por academia bem acima do nacional, mas ainda sem teste
  formal.
