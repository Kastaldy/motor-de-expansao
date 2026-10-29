# Estado dos Modelos — Desempenho, Arquitetura e Uso

> Fonte de fácil acesso ao time sobre **o que os modelos do Motor realmente preveem, com que erro e como
> usá-los na decisão**. Complementa (não substitui) o `CLAUDE.md` (§1–§8) e as decisões registradas em
> `docs/decisions/`; o andamento dos blocos de produto (epic BLK-VIAB) fica em `tasks/backlog.md`.

## TL;DR

- O Motor **não é um modelo**; é uma **pilha de camadas paralelas**, cada uma respondendo uma pergunta
  diferente. A arquitetura correta de uso é um **funil**: triagem macro → mercado → **imóvel real** → viabilidade.
- Os modelos são bons **triadores** (ordem relativa — "onde olhar") e **fracos preditores de número
  absoluto** (quantos alunos).
- A **demanda entra como PREMISSA editável**; o valor pode vir **sugerido por um modelo de praça** que usa a geografia (isócrona de 10 min, DEC-078), só na Viabilidade de um imóvel dado.
- A ferramenta de viabilidade é de **ordem de grandeza** (MAPE ~30%): use as **faixas p10–p90 e o ranking
  relativo**, não o número pontual.

---

## 1. Arquitetura — as camadas

| Camada | Pergunta que responde | Papel | Artefato canônico |
|---|---|---|---|
| **M1 territorial** | Onde expandir (município/UF)? | Executivo — triagem macro | `score_priorizacao` (renda 0,40 + pop 0,60) |
| **Censitário** | Qual praça (hexágono) tem melhor renda e população? | Operacional — régua **absoluta**, comparável entre cidades (DEC-040) | `score_setor_2022_calibrado` |
| **Mercado / Residual** | Onde há oferta consumida vs. demanda? | Oportunidade de mercado | `score_oportunidade_residual` |
| **Demanda Revelada + Huff** | Onde há demanda paga observada? | Leitura de demanda (corporativa) | `membros`, `share_captura_huff` |
| **Viabilidade de Imóvel** | Este imóvel fecha a conta? | Property-first — decisão econômica | `viabilidade_ponto.py` |

Todas as camadas paralelas são **READ-ONLY sobre o M1** (§5): nenhuma recalcula `score_priorizacao`, pesos,
carteira, plano ou artefatos oficiais.

---

## 2. Desempenho — o retrato honesto

| Modelo | Prevê bem? | Número honesto (out-of-fold onde aplicável) |
|---|---|---|
| Score territorial do M1 → **magnitude de demanda** | ❌ Não | M1 `rho ≈ 0`; renda/pop com sinal nulo (DEC-001, backtest BLK-SCORE-02) |
| Demanda revelada (`membros`) | ⚠️ Só a fatia corporativa | R²_oof **+0,57 inflado** por circularidade Huff↔`membros` + viés corporativo; contra **alunos totais reais** cai para **~+0,08 a +0,16** |
| Curva viabilidade (m²→densidade) | ✅ Ordem de grandeza | **MAPE ~30–32%**, R² ~0,19 (N=112: Ultra 54 + Eng Corpo 58); Ultra-só 26,8% |
| Modelo de praça (Viabilidade, DEC-078: m², renda domiciliar e população da isócrona de 10 min de carro e estúdio → faturamento maduro, convertido em alunos) | ✅ Ordem de grandeza, só como **sugestão editável** para um imóvel dado | erro típico do faturamento **18,6%** deixando cada unidade de fora (39 de treino) e **20,6%** no teste (15 unidades, onde fica ~9,8% abaixo do real); R² 0,369 deixando cada uma de fora; faixa p10–p90 = p50 × 0,677 a 1,611, **provisória** (vem dos resíduos do próprio teste); fora do envelope do treino (ex.: m² de 940 a 2.800) sai com `flag_extrapolacao` |
| Ranquear / triar (ordem relativa) | ✅ Sim | é o que a pilha faz bem |

### Achados-chave da validação (2026-07-07/08)

- **`membros` é a fatia do benefício corporativo (~1/3 dos alunos reais).** Nas 54 unidades Ultra, o agregador
  (Gympass+TotalPass) é só **35,6%** do total. O eixo `disputa = 1 − share_huff` foi calibrado no próprio
  `membros`, então o R²_oof +0,57 é **parcialmente circular**. Contra um alvo independente (alunos totais),
  o poder cai para ~+0,08 (limpo) / ~+0,16 (com Huff). Fonte versionada: o achado (2026-07-07) virou regra nas "Decisões PRÉ-FIXADAS" do BLK-VIAB-02 em `tasks/completed.md` (alvo = alunos totais reais, nunca `membros`/agregador); a medição dos +0,08/+0,16 é a do `scripts/_scratch_atr_alvo_alunos_totais.py` (relatório em `data/analysis/atr_alvo_alunos_totais.md`).
- **A curva de viabilidade generaliza entre redes** (MAPE Eng Corpo 30,3% ≈ Ultra 35,3% no pool de 112), **mas
  misturar portes diferentes na curva PIORA a rede menor** (Ultra: 26,8% base-54 → 35,3% base-112) e **extrapolar
  fora do envelope (> 2.800 m²) é ruim (MAPE 85%)**. Este achado e os dois seguintes vêm do backtest BLK-VIAB-04-FU, resumido no "Contexto" dos BLK-VIAB-06 e BLK-VIAB-07 em `tasks/completed.md`.
- **Afinar a curva por tamanho NÃO melhora a precisão** — o motor já usa janela ±20% de metragem, que está no
  ótimo; o pool global (densidade constante) é o pior. A precisão trava em **~30% MAPE**, o piso honesto do dado.
- **A única alavanca de precisão restante é a homogeneidade de FORMATO/rede** (comparáveis do mesmo formato dão
  ~−1,7 p.p. de MAPE) — mas isso exige saber o **formato pretendido** do imóvel, não só o tamanho.

### O que os modelos NÃO fazem

- Fora da Viabilidade (modelo de praça da DEC-078, que só SUGERE a demanda, editável), não preveem quantos alunos um ponto novo terá.
- Não substituem análise humana do imóvel (visibilidade, fluxo, esquina, negociação).
- Fora do envelope de metragem calibrado (~600–3.000 m²), a viabilidade não é confiável.

---

## 3. Como usar — a doutrina operacional

1. **Triagem decide ONDE olhar, não QUANTOS alunos.** M1/censitário/residual estreitam o mapa para regiões
   promissoras. Não os leia como oráculo de magnitude.
2. **Demanda entra como PREMISSA editável** (DEC-078). O operador, os comparáveis ou,
   na Viabilidade, a sugestão do modelo de praça trazem a demanda; o software faz a conta de viabilidade.
3. **A decisão é property-first:** o operador traz um imóvel real (m² + aluguel) → o motor devolve faixa de
   alunos, break-even, aluguel-teto, **margem de segurança** e sensibilidade. Use **faixas (p10–p90)**, nunca o
   número pontual.
4. **Respeite o envelope calibrado (~600–3.000 m²).** Fora dele, sinalize extrapolação.
5. **Nenhuma camada decide sozinha.** A decisão vem da **triangulação**: triagem + viabilidade + preço + olho
   humano no imóvel. E cuidado com falsa confiança: residual/Huff/censitário são correlacionados — não os
   conte como confirmações independentes.

---

## 4. Referências

- **Decisões:** DEC-001 (não recalibrar M1), DEC-008 (metodologia out-of-fold), DEC-009 (pivô property-first; revogada pela DEC-078), DEC-078 (Viabilidade v2: demanda sugerida pelo modelo de praça e curva de rampa).
- **Relatórios (gitignored, `data/analysis/`):** `viabilidade_candidatos.md`, `viabilidade_backtest_ultra.md`,
  `viabilidade_backtest_multirede.md`, `atr_alvo_alunos_totais.md`.
- **Código:** `src/motor_expansao/dimensionamento/viabilidade_ponto.py` (motor), `backtest_viabilidade.py`
  (validação), `demanda_v2.py` e `v2_coeficientes.json` (modelo de praça), `demanda_revelada/` (camada de demanda revelada).
- **Contexto de mercado/residual:** `docs/modelo_mercado_hexagonos.md`.
