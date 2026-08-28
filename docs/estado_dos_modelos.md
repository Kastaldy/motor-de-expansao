# Estado dos Modelos — Desempenho, Arquitetura e Uso

> Síntese consolidada em 2026-07-08. Fonte de fácil acesso ao time sobre **o que os modelos do
> Motor realmente preveem, como usá-los e o roadmap de implementação**. Complementa (não substitui)
> o `CLAUDE.md` (§1–§8) e as decisões registradas (DEC-001 a DEC-014).

## TL;DR

- O Motor **não é um modelo**; é uma **pilha de camadas paralelas**, cada uma respondendo uma pergunta
  diferente. A arquitetura correta de uso é um **funil**: triagem macro → mercado → **imóvel real** → viabilidade.
- Os modelos são bons **triadores** (ordem relativa — "onde olhar") e **fracos preditores de número
  absoluto** (quantos alunos). Isso é a DEC-009, agora quantificada.
- A **demanda entra como PREMISSA explícita, nunca como predição pela geografia**.
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
| Geografia → **magnitude de demanda** | ❌ Não | M1 `rho ≈ 0`; renda/pop com sinal nulo (DEC-001, backtest BLK-SCORE-02) |
| Demanda revelada (`membros`) | ⚠️ Só a fatia corporativa | R²_oof **+0,57 inflado** por circularidade Huff↔`membros` + viés corporativo; contra **alunos totais reais** cai para **~+0,08 a +0,16** |
| Curva viabilidade (m²→densidade) | ✅ Ordem de grandeza | **MAPE ~30–32%**, R² ~0,19 (N=112: Ultra 54 + Eng Corpo 58); Ultra-só 26,8% |
| Ranquear / triar (ordem relativa) | ✅ Sim | é o que a pilha faz bem |

### Achados-chave da validação (2026-07-07/08)

- **`membros` é a fatia do benefício corporativo (~1/3 dos alunos reais).** Nas 54 unidades Ultra, o agregador
  (Gympass+TotalPass) é só **35,6%** do total. O eixo `disputa = 1 − share_huff` foi calibrado no próprio
  `membros`, então o R²_oof +0,57 é **parcialmente circular**. Contra um alvo independente (alunos totais),
  o poder cai para ~+0,08 (limpo) / ~+0,16 (com Huff). Detalhe: memória `huff-membros-circularidade-teto-demanda`.
- **A curva de viabilidade generaliza entre redes** (MAPE Eng Corpo 30,3% ≈ Ultra 35,3% no pool de 112), **mas
  misturar portes diferentes na curva PIORA a rede menor** (Ultra: 26,8% base-54 → 35,3% base-112) e **extrapolar
  fora do envelope (> 2.800 m²) é ruim (MAPE 85%)**.
- **Afinar a curva por tamanho NÃO melhora a precisão** — o motor já usa janela ±20% de metragem, que está no
  ótimo; o pool global (densidade constante) é o pior. A precisão trava em **~30% MAPE**, o piso honesto do dado.
- **A única alavanca de precisão restante é a homogeneidade de FORMATO/rede** (comparáveis do mesmo formato dão
  ~−1,7 p.p. de MAPE) — mas isso exige saber o **formato pretendido** do imóvel, não só o tamanho.

### O que os modelos NÃO fazem

- Não preveem quantos alunos um ponto novo terá (DEC-009).
- Não substituem análise humana do imóvel (visibilidade, fluxo, esquina, negociação).
- Fora do envelope de metragem calibrado (~600–3.000 m²), a viabilidade não é confiável.

---

## 3. Como usar — a doutrina operacional

1. **Triagem decide ONDE olhar, não QUANTOS alunos.** M1/censitário/residual estreitam o mapa para regiões
   promissoras. Não os leia como oráculo de magnitude.
2. **Demanda entra como PREMISSA, nunca como predição geográfica** (DEC-009). O operador ou os comparáveis
   trazem a faixa de demanda; o software faz a conta de viabilidade.
3. **A decisão é property-first:** o operador traz um imóvel real (m² + aluguel) → o motor devolve faixa de
   alunos, break-even, aluguel-teto, **margem de segurança** e sensibilidade. Use **faixas (p10–p90)**, nunca o
   número pontual.
4. **Respeite o envelope calibrado (~600–3.000 m²).** Fora dele, sinalize extrapolação.
5. **Nenhuma camada decide sozinha.** A decisão vem da **triangulação**: triagem + viabilidade + preço + olho
   humano no imóvel. E cuidado com falsa confiança: residual/Huff/censitário são correlacionados — não os
   conte como confirmações independentes.

---

## 4. Roadmap de implementação

O que **já existe e funciona:** M1/censitário/dashboard (produção); `viabilidade_ponto.py` (motor);
BLK-VIAB-01/02/03 (base de imóveis → ranking por margem de segurança); BLK-VIAB-04/FU (backtest validado, N=112).

Blocos para operacionalizar o produto (ver `tasks/backlog.md`, epic BLK-VIAB):

| # | Bloco | Passo | Autonomia |
|---|---|---|---|
| 1 | **BLK-VIAB-09** — UI de Viabilidade de Imóvel no dashboard | Produto end-to-end (maior impacto) | Humano (UX) |
| 2 | **BLK-VIAB-06** — Guardrail de envelope de metragem | Impede extrapolação ruim | **loop-safe** |
| 3 | **BLK-VIAB-07** — Curva por formato (rótulo opcional) | Única alavanca de precisão restante | **loop-safe** |
| 4 | **BLK-VIAB-08** — Geocoding + catchment dos candidatos | Liga pop/renda do entorno | Humano (rede/DEC-010) |
| 5 | **BLK-VIAB-10** — Aquisição de metragem externa | Destrava melhorar a curva (gargalo VIAB-05) | Humano (dado externo) |

**Recomendação:** o maior valor está em **ligar o produto end-to-end (BLK-VIAB-09)** — transforma o motor
validado numa ferramenta que o time usa. Os blocos **VIAB-06/07 são loop-safe** (guardrail + precisão) e podem
rodar autônomos; VIAB-08/09/10 são humanos (rede, UI e dado externo).

**O que parar de fazer:** tentar prever demanda pela geografia; afinar a curva por tamanho (retornos decrescentes).

---

## 5. Referências

- **Decisões:** DEC-001 (não recalibrar M1), DEC-008 (metodologia out-of-fold), DEC-009 (pivô property-first).
- **Relatórios (gitignored, `data/analysis/`):** `viabilidade_candidatos.md`, `viabilidade_backtest_ultra.md`,
  `viabilidade_backtest_multirede.md`, `atr_alvo_alunos_totais.md`.
- **Código:** `src/motor_expansao/dimensionamento/viabilidade_ponto.py` (motor), `backtest_viabilidade.py`
  (validação), `demanda_revelada/` (camada de demanda revelada).
- **Contexto de mercado/residual:** `docs/modelo_mercado_hexagonos.md`.
