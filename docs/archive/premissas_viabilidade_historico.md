# Premissas da Viabilidade — histórico

> Registro: trechos de história tirados do `PREMISSAS_VIABILIDADE.md` em 03/11/2026, palavra por palavra, na
> segunda rodada da leiguificação (lista aprovada por Vinicius, responsável pela documentação). O que vale hoje
> está no documento principal; aqui fica como as regras chegaram lá. Este arquivo só recebe acréscimo.
> Os números de linha são os da versão anterior ao corte (main `61caf4e3`).

## Cabeçalho

*Linha 13:*

> Ciclo: **FIN-VIAB-01** (reconciliação do simulador) · Atualizado em **2026-07-25**, com acréscimos de **2026-10-05** (studios com ticket próprio, DEC-068), **2026-10-21/22** (demanda do modelo de praça e curva de rampa, DEC-078) e **2026-10-28** (padrão do investimento por campo, DEC-079)

## 2. Receita e demanda

*Trecho da linha 50:*

> (estava **hardcoded em dois lugares** antes do FIN-VIAB-01)

## 2.1 Regra da anuidade (decidida por Felipe em 2026-07-24 — não rediscutir)

*Trecho da linha 81:*

> A anuidade é a linha `Simulador!J10` da planilha, que o motor nunca tinha implementado. Ela foi
> **ligada** neste ciclo por decisão explícita do dono do produto, que confirmou também a
> periodicidade.

## 2.2 Forma da rampa de alunos (DEC-078, PROPOSTA; emenda de 21/10/2026)

*Trecho da linha 115:*

> ; eram −127 antes do mês 0

## 4. Custos operacionais

*Trecho da linha 152:*

> (era o `le=3` do schema)

## 4.1 Regra da folha — FIXA desde o mês 1 (decisão de Felipe, 2026-07-24 — não rediscutir)

*Linhas 162–166:*

**O que era:** `folha = folha_pct × faturamento DO MÊS`. Como o faturamento rampa por 8 meses, a
folha rampava junto — no caso de referência ela entrava com **R$ 15.678,87 no mês 1** e só chegava
aos ~R$ 49 mil na maturidade. Isso equivale a supor que **se contrata gente na medida em que o
aluno entra**, o que não é como a unidade abre. Foi exatamente o defeito reportado: *"a folha está
escalando junto com a unidade"*.

*Linhas 195–199:*

**Efeito no caso de referência:** o mês de *steady* **não muda** (lá o faturamento já é o maduro,
então a folha percentual e a folha fixa coincidem: R$ 49.003,79 nos dois modelos). O que muda são
os meses de rampa e tudo que deriva deles — EBITDA do mês 1 de **−R$ 10.139,56 para −R$ 43.464,47**,
break-even de **840,6 para 1.152,0** alunos totais, payback de **28 para 31 meses**. Números
completos em §15.

## 6. Investimento, financiamento, linha do tempo e retorno

*Trecho da linha 248:*

> (era literal em `simulador.py`)

*Trecho da linha 258:*

> O ROIC anterior misturava as duas (numerador antes do financiamento sobre
> denominador de capex cheio), e o modelo se beneficiava do financiamento duas vezes.

## 6.2 Como ler retorno — as duas óticas (decisão de Felipe, 2026-07-25)

*Linhas 275–282:*

Até a 3ª rodada existia **um** par TIR/VPL, e ele era o do **sócio** descontado a **12% a.a.** Uma
revisão externa apontou o furo: o sócio é **subordinado ao banco**, e o banco cobra **23,87% a.a.**
nesta operação. Descontar o fluxo do sócio a 12% é afirmar que ele aceita **metade** do retorno do
credor para correr **todo** o risco residual. O número não estava "conservador" — estava errado de
sinal conceitual, e inflava o VPL.

A correção não foi trocar 12 por 25 num campo. Foram **duas óticas separadas**, cada uma com o seu
fluxo e a sua taxa:

*Trecho da linha 302:*

> Não é mais "provisório pendente de aval" — foi decidido
> (§10).

## 6.4 Margem mínima de viabilidade: 10% → 30% (decisão de Felipe, 2026-07-25)

*Linhas 391–393:*

- **Cenários entre 10% e 30% viram NÃO-viável.** Quem comparar com material antigo tem de saber
  disso: um cenário que aparecia como "viável, margem 22%" agora reprova — e não porque a economia
  mudou, mas porque a régua era frouxa.

*Trecho da linha 398:*

> (contra 1.322,6 para os 10% antigos)

## `SIM_STUDIOS_DEFAULT = 0` (e `SIM_CUSTO_STUDIO`, que **deixou de ser órfã**)

*Trecho da linha 468:*

> O histórico abaixo fica como registro.

*Linhas 469–477:*

- **`SIM_CUSTO_STUDIO = 6 000,00` foi LIGADA neste ciclo.** `web/server/app.py::_premissas_do_body`
  soma `n_studios × SIM_CUSTO_STUDIO` a `outros_fixos_mes` (com `n_studios = 2`, o custo fixo vai de
  R$ 68.150,00 para R$ 80.150,00, ou seja −R$ 12.000 no EBITDA). Antes, a tela **tinha** um seletor
  de studios (0..3) que só afetava o **ticket** (via `TICKET_POR_STUDIO` no frontend) e nunca o
  custo: uma unidade com 3 studios rodava com o mesmo custo fixo de uma sem nenhum. A **fonte**
  ("fopag adicional por studio extra") continua sem célula da planilha nem linha de DRE — calibrar o
  valor é da controladoria. Nota: o studio entra em `outros_fixos_mes`, **não** na folha dimensionada
  por `SIM_FOLHA_PCT` (§4.1) — se o quadro de pessoal do studio já estivesse dentro dos 17%, isso
  seria dupla contagem, e é uma pergunta aberta para a controladoria.

## (a) FOLHA — a nota tem DUAS dimensões: a ESTRUTURA e o NÍVEL, as duas decididas

*Trecho da linha 492:*

> As tabelas abaixo registram o conflito como foi
> > levantado e como ele fechou.

*Linhas 502–512:*

**Sobre o nível:**

| | |
|---|---|
| **O que o código faz hoje** | `SIM_FOLHA_PCT = 0,17`, aplicado **uma vez** sobre o faturamento **maduro** → R$ 49.003,79/mês fixos. |
| **O que a evidência diz** | O **BLK-VIAB-11** apurou **25-26%** em **6 DREs gerenciais reais** (Augusta, Bangu, Cabo Frio, Icaraí, Praia Grande, Vila Guilherme; jun-jul/2026). Folha real de **R$ 38 mil a R$ 99 mil/mês**, **estável como % da receita bruta (CV 0,16)** e instável por m² (CV 0,34). SP e RJ praticamente idênticos → sem ajuste regional. |
| **Por que 17% mesmo assim** | 17% mantém o **nível** próximo do status quo (R$ 50.128 fixos ÷ R$ 277.676 = 18,05% no caso antigo). A 3ª rodada mexeu na **estrutura**, não no nível — e trocar as duas coisas ao mesmo tempo tornaria impossível atribuir o delta. Note a ironia útil: com a folha fixa, o nível de 17% reproduz quase exatamente o R$ 50.128 absoluto do modelo original, agora dimensionado por uma régua rastreável em vez de um número herdado. |
| **Impacto do nível (re-medido na 4ª rodada, 2026-07-25 — nas duas óticas e na régua de 30%)** | A **17%**: folha **R$ 49.003,79**, EBITDA **R$ 113.159,69 (39,26%)**, break-even **1.152,0**, payback **31**, **do negócio** TIR **31,74%** / VPL **R$ 312.177,18**, **do sócio** TIR **38,98%** / VPL **R$ 276.103,24**, cheque total **R$ 1.142.112,62** (mês 5), M60 **R$ 1.645.454,56**, `flag_viavel` **True**. **A 26%: folha R$ 74.946,97, EBITDA R$ 87.216,50 (30,26%), break-even 1.416,1, EBITDA do mês 1 de −R$ 69.407,65, cheque total R$ 1.297.571,83 (mês 7) e o payback NÃO OCORRE dentro dos 60 meses** (`inf`) — **do negócio** TIR **11,20%** / VPL **−R$ 623.616,27**, **do sócio** TIR **−1,05%** / VPL **−R$ 623.473,26**, acumulado de M60 **−R$ 40.745,08**, `flag_viavel` **False**. |
| **O que a régua nova de 30% revela aqui** | A 26% a margem fica em **30,26%** — passa o mínimo de 30% **por 26 pontos-base**. Quem reprova o cenário é o **payback infinito**, não a margem. Ou seja: no nível de folha que 6 DREs reais apuraram, o critério de margem fica **na casa dos centavos** do limite. Isso é informação de decisão, não curiosidade: a folga de margem que o caso de referência parece ter (39,26% contra 30%) é **quase toda** dependente do nível de folha estar em 17%. |
| **Atenção ao comparar com material anterior** | Duas revisões atrás esta linha dizia "payback 28 → 54 meses" e "VPL −R$ 174.670,13" (folha **percentual**, que diluía o custo na rampa). A revisão de 2026-07-24 já corrigiu para "não se paga no horizonte", mas citava **VPL −R$ 384.910,19 @ 12% a.a.** — taxa que **não existe mais**. Na régua de hoje o VPL a 26% é **−R$ 623 mil nas duas óticas**: quanto mais alta a taxa, mais pesado o desconto de um fluxo que só melhora no fim. |
| **Status** | **DECIDIDO em 2026-09-30 (Felipe): 17% permanece.** Enquanto esteve pendente, era a decisão de maior impacto do ciclo: sozinha, ela invertia a conclusão de go/no-go do Boulevard. |

## (b) TAXA DE FRANQUIA — R$ 160.000 (código) × R$ 140.000 (planilha e spec)

*Trecho da linha 521:*

> — efeito que a régua de 12% a.a. era incapaz de mostrar

## (c) TICKET DE MUSCULAÇÃO — R$ 137 (backend/planilha) × R$ 147 (tela)

*Trecho da linha 529:*

> As linhas abaixo são o registro histórico da medição.

*Linha 533:*

| **Frontend (histórico, até 2026-10-05)** | `web/src/screens/ViabilityScreen.tsx:34` → `TICKET_POR_STUDIO = [147, 157, 167, 177]` (0 → 147, 1 → 157, 2 → 167, 3 → 177). |

*Trecho da linha 535:*

> A tela cobra **um degrau a mais** em todos os cenários de studio.

*Trecho da linha 536:*

> Com a taxa antiga de 12% a.a. o mesmo cenário exibia **VPL +R$ 416.749,97** e parecia um projeto folgado.

## 10. A taxa SAIU desta seção — foi decidida (2026-07-25)

*Linhas 543–549:*

**Esta seção era "Pendente de aval" e tinha um único item: a taxa de desconto do VPL
(`SIM_TAXA_DESCONTO_AA = 0,12` a.a.). O item foi RESOLVIDO e a constante NÃO EXISTE MAIS.**

| O que era | O que é |
|---|---|
| `SIM_TAXA_DESCONTO_AA = 0,12` — "default provisório, escolhido para destravar a entrega de TIR/VPL", sem custo de capital formalizado. Todo VPL vinha com a ressalva "taxa provisória, pendente de aval do comitê". | **`SIM_TAXA_MINIMA_NEGOCIO_AA = 0,25`** (25% a.a. nominal), **decidida por Felipe** em 2026-07-25, com justificativa registrada: **piso do custo da dívida (23,87% a.a.) + *build-up* sobre a Selic de 14,25%**. **Quem pode alterar: o dono do produto.** |
| Uma taxa só, aplicada a um fluxo **de sócio** | **Duas óticas**, cada uma com a sua taxa — e a **do sócio é derivada** (§6.2), não configurável |

*Linhas 556–559:*

**Efeito honesto da decisão:** o VPL anunciado **caiu**. Era **R$ 849.484,15 a 12% a.a.**; hoje são
**R$ 312.177,18 do negócio a 25%** e **R$ 276.103,24 do sócio a 27,08%**. Isso **não é uma piora do
negócio** — é o mesmo fluxo de caixa medido contra a régua certa. A TIR não se moveu um centavo (é
raiz do fluxo, independe da taxa): o que se moveu foi a **exigência**.

## 12. Linhas da planilha ainda ausentes do motor

*Trecho da linha 593:*

> A **anuidade saiu desta lista** em 2026-07-24: foi decidida por Felipe, implementada, exposta no
> `viabilidade_payload_v1` e está ligada por default (`SIM_ANUIDADE_VALOR = 99.0`). Regra e
> justificativa em **§2.1**.

## 15. Caso de referência verificado

*Linha 685:*

| *(referência)* alunos para margem de 10% | *1.322,6 alunos totais — régua antiga, ver §6.4* |

*Linhas 713–748:*

**Steady-state não mudou na 3ª rodada.** Faturamento, EBITDA, margem, folha do mês 12, IR/CSLL e
aluguel-teto são idênticos aos da rodada anterior — no mês 12 o faturamento já é o maduro, então
folha percentual e folha fixa dão o mesmo R$ 49.003,79. Tudo o que mudou está na **rampa** e no que
deriva dela (break-even, payback, TIR, VPL, acumulado).

**O que a 4ª rodada mudou no caso de referência.** Nada na operação: faturamento, EBITDA, margem,
folha, IR/CSLL, break-even, payback, aluguel-teto e acumulado de M60 estão **idênticos** aos da 3ª
rodada — a 4ª rodada não tocou em nenhuma linha da DRE. O que mudou é a **régua de retorno** e o que
o motor **expõe**:

| item | 3ª rodada | 4ª rodada |
|---|---|---|
| Taxa | uma só: 12% a.a. (provisória) | **negócio 25,00%** (premissa) + **sócio 27,08%** (derivada) |
| TIR | uma só: 38,98% a.a. (era, sem rótulo, a do sócio) | **negócio 31,74%** · **sócio 38,98%** (o número antigo **era** o do sócio — não mudou, ganhou nome) |
| VPL | **R$ 849.484,15** @ 12% | **negócio R$ 312.177,18** @ 25% · **sócio R$ 276.103,24** @ 27,08% |
| Cheque total | **não existia** | **R$ 1.142.112,62** no mês 5 (**1,50×** o aporte de R$ 760 mil) |
| Margem mínima | 10% | **30%** (o caso segue viável: 39,26%) |
| Guardas | nenhuma | **duas identidades** aferidas + `alerta_divida_acima_da_taxa_negocio` + `vpl_identidade_residuo` |

**A queda do VPL é a correção, não um efeito colateral.** R$ 849 mil vinha de descontar um fluxo de
**sócio** a **12%** quando o **banco** cobra **23,87%**. Ver §6.2 e §10.

**Isolamento das duas mudanças da 3ª rodada** (medido em 2026-07-24, uma por vez; os VPLs desta
tabela são **históricos, @ 12% a.a.**, e ficam só para rastrear o efeito de cada mudança **entre si**
— não são o VPL de hoje):

| mudança | efeito |
|---|---|
| **Franquia parcelada 4×** — só timing de caixa | TIR **+0,33 pp** · VPL **+R$ 2.241,80** · payback, acumulado de M60, EBITDA, margem e break-even **idênticos** |
| **Folha fixa desde o mês 1** — responde por todo o resto | break-even **840,6 → 1.152,0** · payback **28 → 31** · TIR **45,48% → 38,65%** (antes de somar a franquia) · VPL **R$ 986.172,80 → R$ 847.242,35** · M60 **R$ 1.795.729,88 → R$ 1.645.454,56** · EBITDA do mês 1 **−R$ 10.139,56 → −R$ 43.464,47** |

**Referência com a anuidade desligada** (`anuidade_valor = 0`), re-medida na 4ª rodada, para quem
precisar comparar com material anterior: steady no **mês 8** · faturamento R$ 282.015,62 · folha
R$ 47.942,66 · EBITDA R$ 109.233,60 (38,73%) · break-even **1.166,9** · payback **32** · **do
negócio** TIR 30,34% / VPL R$ 244.664,58 · **do sócio** TIR 36,40% / VPL R$ 212.103,28 · cheque
total R$ 1.136.806,97 (mês 5) · acumulado M60 R$ 1.503.326,98 · aluguel-teto canônico R$ 56.403,12.

## 16. Funções deprecated

*Linhas 764–776:*

**Assinaturas que mudaram na 3ª rodada** (a folha fixa é dimensionada pela demanda assumida, então
as duas funções passaram a **receber** a demanda — chamada sem ela agora é `TypeError`, não um
número errado silencioso):

```python
break_even_alunos(p, demanda_total, *, incluir_pmt=0.0)     # antes: (p, *, incluir_pmt=0.0)
alunos_para_margem(p, margem_alvo, demanda_total)           # antes: (p, margem_alvo)
gerar_serie_mensal_completa(..., parcelas_franquia=4)       # argumento novo
simular(..., parcelas_franquia=4)                          # argumento novo
```

A propriedade `Premissas.custo_fixo_base_mes` **não existe mais**: foi substituída pelo método
`custo_fixo_total_mes(demanda_total)`, que inclui a folha.

*Linhas 778–789:*

**O que a 4ª rodada REMOVEU** (nenhuma assinatura de função mudou, mas um campo saiu):

```python
# NÃO EXISTE MAIS — TypeError no construtor, AttributeError no acesso:
Premissas(..., taxa_desconto_aa=0.12)   # TypeError: unexpected keyword argument
p.taxa_desconto_aa                      # AttributeError
SIM_TAXA_DESCONTO_AA                    # ImportError

# O substituto:
Premissas(..., taxa_minima_negocio_aa=0.25)   # SIM_TAXA_MINIMA_NEGOCIO_AA
# e a taxa do sócio NÃO tem parâmetro: sai derivada em `simular()` (§6.2)
```
