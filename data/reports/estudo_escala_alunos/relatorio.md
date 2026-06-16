# Estudo estatístico — Escala de alunos por m² e modelo de viabilidade/risco

> **Objetivo:** decidir, com evidência defensável, como um produto de dados deve estimar/usar a
> escala de alunos de um imóvel para **classificar risco e ranquear oportunidades** de expansão —
> e o que precisa ser corrigido antes de subir o modelo para produção.
>
> **Escopo:** camada paralela BLK-DIM (property-first, DEC-009). **READ-ONLY sobre o M1** — não toca
> `score_priorizacao`/pesos/artefatos oficiais. Sem PII (só agregados).
>
> **Data:** 2026-06-16 · **Reprodutível:** `python data/analysis/estudo_escala_alunos/gerar_estudo.py`

---

## 0. Sumário executivo (a decisão)

1. **A demanda de um ponto NÃO é previsível pela geografia** (4 NO-GOs anteriores, DEC-009). O único
   sinal físico usável é a **metragem** (curva tamanho→densidade). Confirmado aqui.
2. **A métrica que vai na frente do usuário deve mudar:** de *"quantos alunos este ponto terá"*
   (impreciso, assusta) para **classificação de RISCO** = break-even determinístico + **P(viável)**
   (probabilidade honesta de cobrir a conta) + ranking por margem de segurança.
3. **A faixa p10–p90 é HONESTA (calibrada):** contém ~76–78% das unidades reais (alvo 80%), PIT médio
   0,50. Pode-se confiar nela para derivar P(viável). A dispersão larga **é a realidade**, não erro.
4. **`vagas` não entra como preditor:** é colinear com m² (proxy de escala mais ruidoso) e não adiciona
   sinal robusto. Usar só como restrição de capacidade.
5. **Bug de produção encontrado:** o wiring atual da aba **superestima a receita em ~33%** (trata o p50
   de alunos *totais* como 100% balcão a ticket cheio e ainda soma agregadores fixos). **Corrigir antes
   de subir.**

---

## 1. Metodologia (por que dá para confiar)

- **Métrica oficial:** R²_LOO (leave-one-out, *out-of-sample*) vs **baseline da média**. **R² in-sample é
  banido** (§7 do spec / disciplina das DEC-001/008/009).
- **Anti-geográfico:** nenhum preditor de demanda usa lat/lng. A faixa depende só de m² + comparáveis.
- **Dados reais (sem PII):**
  - Ultra: `data/staging/unidades_ultra_performance_hex.parquet` (54 un.) + fonte `data/ultra/dados_academias.xlsx` (metragem, vagas, ATIVOS_PAG, ALUNOS_TOTAL).
  - Engenharia do Corpo: `data/validacao/academias_engenharia_do_corpo.xlsx` (~58 un.: metragem, vagas, alunos totais/ativos).
  - Base multi-rede: `data/staging/base_calibracao_multirede.parquet` (112 válidas com m²: 54 Ultra + 58 Eng).
- **SkyFit fica de fora:** tem alunos (EVO/Gympass/TotalPass) e coordenadas, mas **zero metragem** em todas
  as fontes (xlsx, CSV, parquet) → não entra no modelo baseado em m². Para incluir (≈300 un.), é preciso
  obter a metragem por unidade.
- **Limite estrutural:** N pequeno (54/58). As tendências são claras; a precisão dos números tem incerteza
  (ver intervalos por bootstrap onde aplicável).

---

## 2. A metragem escala alunos — mas com retornos decrescentes  · `G1`, `G2`

A densidade **cai** conforme a metragem cresce. Elasticidade ajustada (Ultra): **`alunos ∝ m²^0,62`**
(b<1). Logo `densidade = alunos/m² ∝ m²^(−0,38)` — quanto maior o imóvel, menos alunos por m².

- Dobrar a metragem rende só **~1,54×** alunos (não 2×).
- Densidade mediana por faixa (base multi-rede): pico **~2,5 alunos/m² em 800–1.300 m²**, caindo para
  **~1,3–1,7 acima de 1.500 m²**. Existe **faixa ótima de densidade** (a de alunos absolutos segue subindo).
- Densidade mediana por marca: **Ultra 1,57** (p25 1,17 / p75 1,92) · **Engenharia 2,31** (p25 1,89 / p75 2,91).

> **Implicação:** um "número fixo de alunos/m²" está errado — é preciso uma **curva** (retornos decrescentes).

---

## 3. Qual ESTRUTURA usar? Curva + formato vence; número fixo e região falham  · `G3`

Comparação honesta (LOO, alunos totais, base multi-rede n=112) — tabela em `tabelas/t_estrutura_r2loo.csv`:

| Estrutura | R²_LOO |
|---|---|
| baseline (média) | −0,018 |
| **número fixo único** (1 ratio × m²) | +0,004 |
| **ratio fixo por marca** | −0,031 |
| **ratio fixo por região** (cluster geográfico) | **−0,118** |
| curva log-log (retornos decrescentes) | +0,174 |
| **curva + marca/formato** | **+0,307** 🏆 |

- **Número fixo (único ou por marca): falha** — ignora os retornos decrescentes.
- **Cluster por região: pior que o baseline (−0,118)** — geografia não carrega sinal (5º NO-GO). A analogia
  com o "raio variável" não transfere: aquele estabilizou **medição**, não **previsão**.
- **Vence: curva (b<1) + intercepto por formato/marca** (Ultra ≠ Engenharia). Quase dobra a curva pura.

> **Implicação:** o "cluster" certo é **formato/marca**, não região; e é **curva**, não número fixo.

---

## 4. Vagas: colinear com m², não adiciona sinal robusto  · `G4`

`vagas` correlaciona com m² (corr log-log **+0,40 Eng / +0,54 Ultra**) — é um **proxy de escala**. Por isso
**não adiciona** poder preditivo além do m² (LOO, `tabelas/t_vagas_r2loo.csv`):

| Rede | ~m² | ~vagas | ~m²+vagas | Δ(m²+vagas − m²) |
|---|---|---|---|---|
| Ultra | +0,18 | +0,04 | +0,10 | **−0,09** (piora) |
| Engenharia | +0,21 | +0,29 | +0,35 | +0,14 (aparente) |

- O "ganho" da Engenharia **não é robusto:** bootstrap **IC95% cruza zero** [−0,02; +0,72] e **colapsa para
  o nível do m²** ao remover 1–2 unidades de maior vaga (uma mega-unidade de 5.863 m²/400 vagas domina).
- Consistente com o spec do CEO ("por vaga é lixo, CV alto, R² catastrófico").

> **Implicação:** vagas **não entra como feature**. Usar só como **restrição de capacidade de pico**.

---

## 5. Composição: balcão × agregadores — só o total escala  · `G5`

`alunos_total = balcão (ativos_pag) + agregadores` (Gympass/TotalPass/etc.). Ultra:
**balcão ~69%** (mensalidade, ticket cheio) · **agregadores ~31%** (repasse por check-in, ~60% do ticket).

LOO ~ m² por componente (`tabelas/t_composicao.csv`):

| Componente | R²_LOO ~ m² |
|---|---|
| alunos_total | +0,144 |
| **balcão (ativos_pag)** | **−0,007** (não escala) |
| agregadores | +0,062 (fraco) |

- **Só o total escala com m².** O **balcão — o segmento de maior receita — NÃO escala com a área**: depende
  de vendas/retenção, não de tamanho. Por isso o balcão deve ser tratado como **premissa de negócio**, não
  como algo previsto pela metragem.

> **Implicação (financeira):** a receita tem que rodar com **dois tickets** (balcão cheio + agregador ~60%)
> sobre a composição — nunca um ticket médio único sobre alunos totais (ver §8).

---

## 6. A faixa é honesta (calibrada)  · `G6`

Teste de calibração (LOO, distribuição preditiva = comparáveis × m²; `tabelas/t_calibracao.csv`):

| Rede | Cobertura p10–p90 (alvo ~80%) | PIT médio (alvo 0,50) |
|---|---|---|
| Ultra | **76%** | 0,50 |
| Engenharia | **78%** | 0,50 |

A faixa p10–p90 contém ~76–78% das unidades reais, sem viés (PIT 0,50). **A faixa é larga porque a realidade
é dispersa — mas é confiável.** Isso é o que permite transformar a dispersão em **probabilidade honesta**.

---

## 7. O produto: classificação de RISCO + ranking por P(viável)  · `G7`

Em vez de cravar alunos, o produto entrega **decisão + 1 número comparável**:

- **Break-even** (determinístico, exato): quantos alunos o imóvel precisa p/ pagar a conta (m²+aluguel+custos).
- **P(viável)** = fração dos comparáveis (× m², por formato) que superam o break-even → probabilidade honesta.
- **Classe** 🟢 GO (P≥70%) · 🟡 ATENÇÃO (40–70%) · 🔴 NÃO (<40%).

Exemplo (imóvel 1.500 m², mesma faixa 1.632–3.853, alugueis diferentes → break-evens diferentes):

| Imóvel | break-even | P(viável) | classe |
|---|---|---|---|
| A (aluguel baixo) | 1.100 | 98% | 🟢 |
| B (mediano) | 2.100 | 65% | 🟡 |
| C (aluguel alto) | 3.200 | 19% | 🔴 |

**Discriminação (ranqueia bom de ruim?)** — AUC do P(viável) vs superar a mediana:
Engenharia **0,68** (terço top 74% vs base 37%), Ultra **0,60**. *No produto real o ranking é melhor*, porque
o break-even (exato, varia com aluguel) adiciona separação determinística que este teste mantém fixa.

> **Resposta à insegurança do p10/p90:** o usuário não encara dois números distantes — vê **uma decisão +
> uma probabilidade**, com a faixa demovida a **contexto** (nuvem de comparáveis + linha do break-even).

---

## 8. Auditoria de receita — bug de superestimação (corrigir antes de produção)  · `G9`

- **O motor de DRE (`simulador.py`) está correto:** já separa balcão (R$137) + agregadores (R$82 ≈ **60%**)
  + personal. ✅
- **O wiring da aba está errado:** o toggle "usar p50" preenche o campo *"alunos balcão"* com o
  **p50 de alunos TOTAIS** (balcão+agregadores); o engine cobra **tudo a ticket cheio** e **ainda soma 651
  agregadores fixos** por cima → **double-count**.
- **Impacto (p50=2.350, 1.500 m²):** atual ≈ **R$ 375k/mês** vs correto (split 69/31) ≈ **R$ 282k/mês** →
  **+33% de receita fantasma**.

> **Correção exigida:** dividir a demanda-premissa em **balcão (~69%) + agregadores (~31%)** com seus tickets,
> e escalar agregadores junto da premissa (não constante fixa). Ver §9.

---

## 9. Recomendações para produção

1. **Métrica de demanda = curva tamanho→densidade por formato** (não número fixo, não região). Saída como
   **faixa proporcional p10/p50/p90** (≈±40%), nunca banda fixa de 200 (que dá falsa precisão — `G8`).
2. **Headline de risco:** classe 🟢🟡🔴 + **P(viável)** + ranking por margem de segurança. Faixa = contexto.
3. **Corrigir o wiring de receita** (§8): split balcão/agregador com dois tickets; agregadores escalando com
   a premissa. **Bloqueante para produção.**
4. **Balcão = premissa de negócio** (meta de vendas/retenção), exibida e editável; agregadores derivados da
   composição. Demanda nunca derivada da geografia (DEC-009).
5. **Vagas:** só restrição de capacidade; **não** como preditor.
6. **Carimbar incerteza e N:** mostrar n_comparáveis, faixa e a natureza "premissa, não previsão".

---

## 10. Limites e honestidade (o que o modelo NÃO promete)

- **Não prevê** quantos alunos um ponto terá (4–5 NO-GOs); promete **break-even exato + risco calibrado**.
- **N pequeno** (54/58): AUC/coeficientes têm incerteza; a direção é robusta, a casa decimal não.
- **SkyFit fora** por falta de metragem (≈300 un. disponíveis se a metragem for obtida → validação em 3ª rede).
- **Discriminação da demanda é modesta** (AUC 0,60 Ultra) — a força do ranking vem sobretudo do break-even
  determinístico, não da previsão de demanda.

---

## 11. Reprodutibilidade

- Gerar tudo: `python data/reports/estudo_escala_alunos/gerar_estudo.py`
- Figuras: `graficos/g1..g9_*.png` · Tabelas: `tabelas/t_*.csv`
- Estudos de apoio (gitignored): `data/analysis/{densidade_m2,vagas,composicao,estrutura,faixas200,valida_risco}_*.txt`
- **Versionado** em `data/reports/` (tracked) com **apenas agregados** (sem PII, sem dado por unidade).
  As fontes reais (`data/validacao/`, `data/ultra/`, `data/staging/*.parquet`) seguem gitignored; o
  `gerar_estudo.py` as lê localmente para regenerar os agregados.
- Blocos sucessores: **BLK-DIM-13** (correção do split de ticket) e **BLK-DIM-14** (engine de risco +
  ranking dormente). Ver `tasks/backlog.md`.
