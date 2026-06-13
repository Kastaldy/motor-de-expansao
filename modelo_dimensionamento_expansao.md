# Modelo de Dimensionamento e Viabilidade de Unidades — Especificação e Handoff

> Documento de transferência para implementação no repositório do **Motor de Expansão**
> (dados completos: hexágonos H3 r7 / setores censitários de todo o Brasil, 100+ unidades,
> dados diários de 60 unidades maduras com vendas, cancelamentos e churn).
>
> Origem: testes e validações feitos no projeto `Análise Preditiva` (base de 54 academias).
> Data: 2026-06-10.

---

## 0. Resumo executivo

A ideia do CEO — **inverter a lógica**: partir do potencial de mercado de cada região →
dimensionar o imóvel ideal (m²/vagas) → fechar a conta financeira (faturamento, aluguel-teto,
margem, payback, ROIC) — **é viável e é o framework correto** de site selection + sizing usado
por redes de varejo/fitness.

A viabilidade, porém, **não é uniforme**. A cadeia tem 4 camadas:

| Camada | Construível hoje? | Dificuldade real |
|---|:---:|---|
| 1. Potencial de mercado (hex → alunos potenciais) | Só no projeto real | **Alta** — depende de aderência calibrada |
| 2. Captura / market share (potencial → alunos da unidade) | Só no projeto real | **Altíssima** — não-linear, satura |
| 3. Dimensionamento (alunos-alvo → m²/vagas) | **Sim** | Baixa — curva de densidade já medida |
| 4. Unit economics (alunos → margem/payback/ROIC) | **Sim** | Baixa — aritmética determinística |

**Toda a precisão do sistema repousa nas camadas 1 e 2.** As camadas 3 e 4 são sólidas e
podem ser prototipadas imediatamente. O erro fatal a evitar é tratar a camada 1 como
"população × 20%" fixo — isso transforma todo o resto em ficção.

---

## 1. Contexto: de onde viemos (o que a base de 54 academias ensinou)

### 1.1 Os modelos antigos não generalizavam
Três modelos Random Forest (`alunos_previsao.py`, `recorrentes_previsao.py`,
`agregadores_previsao.py`) reportavam R² ~0,85, mas isso era **100% overfitting**
(`min_samples_leaf=1`, n≈43 de treino). Sob validação honesta (Leave-One-Out CV):

| Modelo | R² reportado (in-sample) | R² honesto (LOO-CV) | vs. prever a média |
|--------|:---:|:---:|:---:|
| Alunos total | 0,855 | **−0,118** | pior que a média |
| Recorrentes (ATIVOS_PAG) | 0,826 | **−0,307** | pior que a média |
| Agregadores | 0,886 | **+0,119** | só +15% |

**Lição #1 para o projeto real:** com n pequeno, métrica oficial = **LOO-CV (ou k-fold
repetido) contra baseline da média**. Nunca aceitar R² in-sample nem o padrão
`fit(X,y)→predict(X)` (que vazava no script de recorrentes).

### 1.2 Modelo direto honesto (P1, já implementado)
Substituídos por Ridge regularizado (`modelo_demanda.py`), com `alpha` por LOO interno:

| Modelo | Features | R² honesto | MAPE |
|--------|----------|:---:|:---:|
| Alunos | Metragem, Renda | +0,150 | 26% |
| Recorrentes | Metragem, Renda, População | +0,010 | 34% |
| Agregadores | Metragem, População | +0,051 | 58% |

Restrições adotadas (decisão de negócio): **não usar `PEA Dia`** (correlação ~0 com
alunos/recorrentes) nem **`Densidade demográfica`** (usar **População total**).

**Lição #2:** R² modesto é o **teto honesto de 54 unidades com renda municipal grosseira**.
Subir disso exige mais dados + features de ponto granulares — exatamente o que o Motor tem.

---

## 2. O teste da densidade (alunos/m²) — sugestão inicial do CEO

Comparação honesta (LOO-CV) de 4 formas de prever o total de alunos (`teste_densidade.py`):

| Abordagem | R² honesto | MAE |
|---|:---:|:---:|
| [C] **Ratio fixo (~1,67 alunos/m²) × metragem** | **+0,180** 🏆 | 652 |
| [A] Modelo direto Metragem + Renda | +0,150 | 609 |
| [B] Modelar densidade do local → × metragem | +0,066 | 688 |
| [D] Baseline (média do total) | 0,000 | 699 |

**Três conclusões que viajam para o projeto real:**

1. **Ratio fixo de alunos/m² já bate o modelo direto** para alunos total. Demanda bruta
   escala com m² — "número fixo por unidade" está errado, o CEO está certo.
2. **A versão rica [B] (densidade ~ local) não paga AQUI** porque a densidade (alunos/m²)
   **varia de verdade (CV=0,35) mas não é explicada pela renda municipal** (R²_densidade =
   **−0,12**). Falta granularidade. *É justamente o que muda no projeto real.*
3. **Para ATIVOS_PAG (pagantes), escalar por m² não funciona** (todas as variantes perdem
   para o baseline). Reter pagante depende de mais que área. **A conta financeira tem que
   rodar sobre pagantes, não alunos brutos.**

> Nota técnica: normalizar por **m²** funciona; por **vaga** é lixo (coluna `Vagas` instável,
> CV=0,77, R² catastrófico). Dimensionar por m², usar vagas só como restrição operacional.

---

## 3. Dois achados empíricos que mudam a modelagem

### 3.1 A penetração está incalculável na base atual (e por quê)
`penetração = alunos / população`: **CV=2,92**, com máximo de **598%** (mais alunos que a
"população" do registro). Isso prova que a coluna `População` da base de 54 **não é a área de
captação real** da unidade.

→ **Implicação direta para o projeto real:** o primeiro entregável tem que ser uma
**definição rigorosa de catchment** (raio/isócrona por hex H3 ou agregação de setores) e a
**penetração real calibrada** = alunos reais / população do catchment, por unidade madura.

### 3.2 Retornos decrescentes de tamanho (curva de densidade)
Densidade alunos/m² por faixa de metragem (base de 54):

| Faixa de metragem | Metragem média | Densidade (alunos/m²) | Alunos médios |
|---|:---:|:---:|:---:|
| 750–1.300 m² | 1.071 | **2,06** | 2.213 |
| 1.300–1.500 m² | 1.448 | 1,56 | 2.262 |
| 1.500–1.667 m² | 1.557 | 1,63 | 2.531 |
| 1.667–2.800 m² | 1.986 | **1,45** | 2.922 |

`corr(densidade, metragem) = −0,26` → **densidade cai com o tamanho**.

→ **Implicação:** o dimensionamento (camada 3) precisa de uma **curva densidade×tamanho**,
não de uma constante. E existe uma **faixa ótima de tamanho** — "quanto maior" não é "melhor".

---

## 4. Arquitetura proposta: motor inverso em 4 camadas

```
  [Camada 1]                [Camada 2]               [Camada 3]              [Camada 4]
  POTENCIAL          -->    CAPTURA          -->     DIMENSIONAMENTO  -->    VIABILIDADE
  do hex H3                 (market share)           (m² / vagas)            (financeiro)

  pop_captação      x       f_share(concorrência,    alunos_alvo /          faturamento,
  x aderência_cal           distância, saturação)    curva_densidade(m²)    aluguel-teto,
  x ajuste_renda            x atratividade_unidade    -> m² e vagas ideais   margem, payback,
  = alunos_potenciais       = alunos_capturáveis      (faixa ótima)          ROIC
```

### Camada 1 — Potencial de mercado
`alunos_potenciais(hex) = pop_captação(hex) × aderência_calibrada(hex) × ajuste_renda(hex)`

- **pop_captação:** somar população dos hexágonos H3 dentro do raio/isócrona de captação
  (ex.: 1–2 km ou 10 min de carro). Não usar população de um único hex.
- **aderência_calibrada:** NÃO é constante (não usar 20% fixo). Estimar a função de aderência
  a partir das 60 unidades maduras: `penetração_real = alunos_maduros / pop_captação`,
  regredida contra renda per capita, densidade urbana, perfil etário do hex. Benchmark de
  sanidade: penetração fitness no Brasil ~5% nacional, muito variável por renda.
- **ajuste_renda:** renda per capita do setor/hex (não municipal) modula ticket e aderência.

### Camada 2 — Captura / market share (o elo mais crítico)
`alunos_capturáveis = alunos_potenciais × share_local`

- **share NÃO é linear nem fixo.** Usar modelo gravitacional (**Huff**): a probabilidade de
  um morador escolher a unidade ∝ atratividade_unidade / Σ atratividade_concorrentes,
  com decaimento por distância. Atratividade ≈ f(tamanho, marca, preço, equipamentos).
- **Saturação:** capturável é limitado pela própria capacidade (vagas, horários de pico) e
  pela base de concorrência. Evitar que "hex de 6k potencial" gere demanda impossível.
- **Canibalização:** descontar share captado por outras unidades próprias no catchment.

### Camada 3 — Dimensionamento (problema inverso)
Dado `alunos_alvo` (da camada 2) e a **curva de densidade** da seção 3.2:

- `m²_ideal = alunos_alvo / densidade_esperada(m²)` — resolver com a curva (não constante),
  porque densidade depende do próprio tamanho. Há uma **faixa ótima**, encontrada otimizando
  contra a margem (camada 4), não maximizando tamanho.
- `vagas` como **restrição operacional** (capacidade de pico), não como driver de demanda.

### Camada 4 — Unit economics (determinística — construível já)
```
faturamento_mês   = pagantes_steady × ticket_médio × (1 − inadimplência)
pagantes_steady   = alunos_capturáveis × (1 − churn_steady)        # rodar sobre PAGANTES
margem            = faturamento − aluguel − folha − contas/impostos
aluguel_teto      = faturamento − folha − contas − margem_alvo     # resolver p/ margem-alvo
payback           = capex / fluxo_mensal, ajustado pela CURVA DE MATURAÇÃO (rampa)
ROIC              = NOPAT / capital investido
```
- Rodar sobre **pagantes líquidos de churn e inadimplência**, não alunos brutos.
- **Curva de maturação:** unidade nova não enche no dia 1 — usar a rampa observada nos dados
  diários das 60 unidades maduras para o payback ser realista.

---

## 5. Os 5 riscos que decidem ciência vs. ficção

1. **Aderência assumida ("pop × 20%") é a armadilha fatal.** Tem que ser calibrada da
   penetração real por hex; senão todo o downstream é lixo. *Maior risco do projeto.*
2. **Captura é saturante, não proporcional.** Sem modelo de share (Huff/gravitacional), hex
   grande gera demanda irreal.
3. **Retornos decrescentes de tamanho** (comprovado, corr −0,26): curva de densidade
   obrigatória; existe faixa ótima.
4. **Pagante ≠ aluno total.** Demanda paga não escala limpa com m² (seção 2). Financeiro
   sobre steady-state de recorrentes, líquido de churn/inadimplência.
5. **Curva de maturação.** Payback sem a rampa de enchimento superestima o retorno.

---

## 6. Roteiro de implementação no Motor de Expansão

**Fase 0 — Fundação de dados (pré-requisito de tudo)**
- [ ] Definir catchment por unidade (raio/isócrona sobre hexágonos H3 r7).
- [ ] Calcular `pop_captação` e `renda_per_capita_captação` por unidade existente e por hex
      candidato.
- [ ] Montar base de calibração das 60 unidades maduras: alunos pagantes steady-state,
      churn, inadimplência, ticket, curva de maturação (dos dados diários).

**Fase 1 — Calibrar Camada 1 (aderência)**
- [ ] `penetração_real = pagantes_steady / pop_captação` por unidade madura.
- [ ] Regredir penetração contra renda per capita, densidade urbana, perfil etário (LOO-CV,
      baseline da média). Validar com `teste_densidade.py` adaptado — número-chave:
      **R²_densidade/penetração** ficar positivo e material.

**Fase 2 — Camada 2 (share/captura)**
- [ ] Implementar Huff com concorrência OSM (já mapeada no Motor) ponderada por distância.
- [ ] Validar prevendo alunos das unidades maduras a partir do potencial × share.

**Fase 3 — Camadas 3+4 (dimensionamento + financeiro) — PROTOTIPÁVEL JÁ**
- [ ] Curva de densidade×tamanho (começar com a da seção 3.2, recalibrar com dados reais).
- [ ] Calculadora determinística: `(alunos_alvo, ticket, churn, custos) → (m², vagas,
      aluguel-teto, margem, payback, ROIC)`. Pode ser construída e testada com inputs manuais
      antes das camadas 1-2 entrarem.

**Fase 4 — Integração e backtesting**
- [ ] Encadear as 4 camadas: hex candidato → potencial → captura → tamanho ideal → viabilidade.
- [ ] Backtesting: rodar o motor "às cegas" nas 60 unidades maduras e comparar tamanho/alunos/
      faturamento previstos vs. reais. Reportar erro honesto.

---

## 7. Metodologia de validação (não negociável)

- **Métrica oficial:** LOO-CV ou k-fold repetido, sempre contra **baseline da média**.
- **Banir:** R² in-sample e `fit(X,y)→predict(X)`.
- **Modelos:** começar simples (linear regularizado / GLM). Só subir complexidade se ganhar
  honestamente sobre o baseline. Com features granulares e 100+ unidades, RF/GBM passam a ser
  defensáveis — mas validados do mesmo jeito.
- **Incerteza obrigatória:** toda saída com intervalo de predição + flag de extrapolação
  (ponto fora do envelope observado). Já implementado em `prever()` de `modelo_demanda.py`.
- **Backtesting prospectivo:** registrar previsto vs. real quando novas unidades abrirem.

---

## 8. O Simulador Financeiro real (Bloco C+D já existente)

> Análise do arquivo `ULTRA padrão - Simulador Financeiro.xlsx` (9 abas, DRE mensal de 60
> meses). **Descoberta principal: o Bloco D — toda a parte financeira — já está pronto e é
> robusto.** O que falta é só o acoplamento com a demanda (camadas 1–2) e com o tamanho (m²).

### 8.0 Princípio de implementação — SIMPLES e DINÂMICO (restrição do negócio)
A integração **não pode reconstruir o DRE** nem virar um monstro de engenharia. Tem que ser
dinâmica (rodar para qualquer hex em tempo real). Regra de ouro:

> Tratar o simulador como uma **função de poucos drivers**. A camada nova é só um punhado de
> **coeficientes paramétricos** (R$/m², ratios) + **uma inversão (goal-seek)**. Nada além disso.

Reconstruir as 9 abas em código = caminho errado. O certo é parametrizar ~6 drivers e resolver
1 equação.

### 8.1 O que o simulador já faz bem (não refazer)
- **Curva de maturação + churn já embutidos:** alunos vão de `inicial 500 → maturidade 938` em
  8 meses, com churn 6%/mês (`ativos_EOP = BOP + novos − saindo`). Resolve 2 riscos da seção 5.
- **Agregadores como linha de receita separada** (651 alunos, ticket próprio menor) — alinhado
  com o achado de que agregador ≠ pagante cheio.
- **DRE completo:** receita (mensalidade, anuidade, personal, agregadores) → deduções → custos
  → resultado financeiro → impostos → Lucro Líquido → EBITDA → FCF → ROIC → payback → valuation.

### 8.2 Drivers (inputs) e premissas atuais — aba `Simulador`
| Driver | Célula | Valor padrão | Natureza |
|---|---|---|---|
| # alunos inicial | E9 | 500 | **demanda (hoje manual)** |
| # alunos balcão maturidade | E10 | 938 | **demanda (hoje manual)** |
| # alunos agregadores maturidade | E11 | 651 | **demanda (hoje manual)** |
| Churn | E12 | 6% | premissa |
| Maturação (meses) | E13 | 8 | premissa |
| Mensalidade | J9 | R$137 (por cenário) | premissa |
| Anuidade / Manutenção | J10 | R$99 | premissa |
| Aluguel R$/mês | N9 | 20.000 | **físico (hoje manual)** |
| Royalties | N11 | 8% | contrato |
| Capex total | R9 | R$2,34M | **físico (hoje manual)** |
| Taxa de franquia | R10 | R$140k | contrato |
| Múltiplo (valuation) | R11 | 1,5× receita | premissa |

Custos em % (DRE): Marketing 6% rec. líquida · Manutenção 1% rec. bruta · Cartão 1,05% ·
Devoluções 0,5% · IR 8% efetivo + CSLL 2,88% (presumido). Capex = Obras 800k + Musculação 600k +
Cardio 600k + Acessórios 200k + Tech 40k + Mkt 100k. Saída padrão: ROIC ~10,7%/ano, margem
EBITDA ~23% (ano 2+), ano 1 negativo pela rampa.

### 8.3 O gap único: a metragem é invisível
Busca em todo o workbook → **zero referências a m²/área/vagas** (os "M2…M29" são cabeçalhos de
*Mês*). Capex, aluguel, água/luz e pessoal são **valores absolutos digitados**, não derivados do
tamanho. E a demanda (alunos) é **input manual**, não vem do local. O simulador é puramente
**forward**: dá-se alunos + aluguel + capex, ele devolve a margem.

### 8.4 Integração mínima (os 3 pontos — e só esses)
1. **Demanda para dentro:** camadas 1–2 produzem `alunos_capturáveis_maturidade` do hex →
   preenchem `E10` (balcão) e `E11` (agregadores). Fim da digitação manual.
2. **Elo tamanho↔custo (Bloco C) — paramétrico e enxuto.** Em vez de digitar capex/aluguel,
   derivá-los de m² com **poucos coeficientes**:

   | Driver físico | Vira | Coeficiente a calibrar |
   |---|---|---|
   | `m²` | `alunos_alvo / densidade(m²)` | curva de densidade (2,06→1,45) |
   | Capex obras | `R$/m² × m²` | custo de obra por m² |
   | Aluguel | `R$/m²/mês × m²` | aluguel por m² (varia por hex!) |
   | Água/Luz, IPTU, limpeza | `R$/m² × m²` | custo de ocupação por m² |
   | Equipamentos | `f(m²) ou f(capacidade)` | densidade de equipamentos |
   | Pessoal | `f(alunos/capacidade)` | ratio de staff por aluno |

   São ~6 coeficientes, calibrados uma vez nas 60 unidades maduras. **Não é refazer o DRE.**
3. **A inversão (goal-seek) — uma equação.** O "aluguel-teto" é literalmente **Atingir Meta em
   `N9` (Aluguel) com alvo na Margem/ROIC**. O modelo já calcula a margem para um aluguel dado;
   inverter para "aluguel máximo a uma margem-alvo" (ou "alunos mínimos viáveis", ou "m² ótimo")
   é resolver 1 variável. Em Python: `scipy.optimize.brentq` sobre a função do simulador.

### 8.5 Caminho de implementação recomendado (dinâmico, baixo atrito)
- **Opção A (mais simples, recomendada):** replicar **só a linha de resultado** do DRE numa
  função Python enxuta `viabilidade(alunos, m², aluguel, ticket, churn, ...) → (margem, ROIC,
  payback)` — são ~15 fórmulas, não 9 abas. Aí o goal-seek e o loop por hex ficam triviais e
  rodam em tempo real para o Brasil todo.
- **Opção B:** manter o Excel como fonte de verdade e dirigi-lo via `xlwings`/`openpyxl` com
  goal-seek externo. Mais fiel, porém mais lento e frágil para rodar em escala/dinâmico.
- Recomendação: **A** para o motor de expansão (escala + dinamismo); usar o Excel só como
  referência de calibração e validação cruzada das fórmulas.

---

## 9. Artefatos de referência (projeto `Análise Preditiva`)

| Arquivo | O que é |
|---|---|
| `diagnostico_modelos_demanda.md` | Diagnóstico completo dos modelos antigos + roadmap P0–P5 |
| `Código - Random Forest/modelo_demanda.py` | Modelo direto honesto (Ridge + LOO + intervalos), referência de metodologia |
| `Código - Random Forest/teste_densidade.py` | Comparador de abordagens de densidade — **portável**: função `comparar(d, target, metragem_col, location_features)`, basta apontar para o parquet do Motor e passar features granulares |

**Veredito final:** o modelo é **viável e é a arquitetura certa**. Camadas 3–4 são fáceis e
prototipáveis já. Camadas 1–2 são o coração e só ganham vida com a geografia fina + calibração
nas 60 unidades maduras. Construir de baixo (dados/catchment) para cima, validando cada elo
honestamente, e o número que decide tudo é a **aderência/penetração calibrada por hex** — não
assumida.
