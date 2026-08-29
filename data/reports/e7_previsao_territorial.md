# E7 — Sobra sinal territorial em faturamento por m²? (2026-08-29)

> Protocolo pré-registrado em `e7_protocolo_pre_registrado.md`, escrito **antes** de medir
> qualquer relação. Este relatório é o resultado contra aquele critério — e inclui as duas
> correções que a verificação adversarial impôs, uma delas a um erro meu de agregação e
> outra a uma afirmação errada do meu próprio protocolo.

## Veredito

**NO-GO pelos critérios pré-registrados.** Nenhuma especificação produziu R² out-of-fold
positivo.

| modelo (LOO, N=45) | R² out-of-fold |
|---|---|
| B0 — só a média | −0,0460 |
| B1 — só metragem | −0,0489 |
| **território (ridge)** | **−0,1135** · IC95 [−0,2872, **−0,0514**] |
| território (GBM) | −0,5798 |
| território + metragem | −0,1499 |

Sob GroupKFold por UF, pior: território ridge = **−0,3426**.

Ganho sobre B1: **−0,0686**, IC95 [−0,1743, +0,0064].

- **Critério 1** (R² OOF > 0 com IC excluindo zero): **não atendido** — o IC está
  inteiramente *abaixo* de zero.
- **Critério 2** (ganho sobre metragem > 0 com IC excluindo zero): **não atendido**.

Que o GBM — o modelo mais flexível — seja o **pior** (−0,58) é evidência adicional: não há
estrutura para achar, só ruído para ajustar.

---

## Correção 1 — um erro meu, encontrado pela verificação adversarial

A coluna `faturamento` do painel diário é **acumulada mês-a-data**, não diária. A primeira
versão desta análise a **somou**, inflando o desfecho ~17×.

Verificado diretamente: **99,1%** dos 2.219 meses-unidade são monotônicos não-decrescentes
em `faturamento`, contra **2,2%** em `pagantes` (que é estoque de verdade). Numa unidade
qualquer a série sobe 4.558 → 10.515 → 16.754 → 20.467 ao longo do mês.

Efeito na leitura: o desfecho mediano publicado na v1 era **R$ 2.322/m²/mês**; o correto é
**R$ 121,3/m²/mês** — que, multiplicado por uma unidade de 1.500 m², dá ~R$ 182 mil/mês e
**bate com a mediana de faturamento de `base_calibracao_maduras`**, uma fonte independente.
A correção se valida contra outro dado.

Efeito no veredito: **nenhum**. O R² territorial vai de −0,081 para −0,114 — continua
negativo em todas as especificações.

### Outros defeitos corrigidos na mesma passagem

- **Colisão de nome real.** `AGUAS CLARAS` e `AGUAS CLARAS - DF` têm **653 dias
  sobrepostos** e inaugurações diferentes (2023-03-20 × 2024-10-19): são **duas unidades**,
  e fundi-las somava faturamento alheio. Já `PATIO BRASIL` × `PÁTIO BRASIL` tem **zero**
  sobreposição e a **mesma** inauguração — é a mesma unidade com duas grafias ao longo do
  tempo, e fundir está certo. A chave passou a ser **nome normalizado + inauguração**:
  uma unidade tem uma data de abertura.
- **`oferta_efetiva_disponivel` saiu do bloco territorial.** Ela é **endógena**: o residual
  desconta a oferta Ultra já instalada, e a unidade em análise está nesse desconto. Prever
  o desempenho de uma unidade com uma variável que a inclui não é previsão territorial.
- **Perdas por dado ausente declaradas** em vez de silenciosas: das 56 unidades com regime
  maduro, 6 não têm metragem, 7 não têm hexágono e 11 não têm score censitário → N=45.

---

## Correção 2 — o meu protocolo afirmava uma limitação que é FALSA

O protocolo pré-registrado declarava que a amostra sofreria **restrição de amplitude** (a
Ultra só abriu onde quis), o que **atenuaria** correlações e enviesaria o desenho a favor
do NO-GO. Medido, é o **contrário**:

| feature | SD na amostra (45) | SD no universo elegível do funil (2.149 hexes) | razão U/A |
|---|---|---|---|
| `score_setor_2022_calibrado` | 20,7 | 11,9 | **0,58** |
| `renda_per_capita_setor_2022_calibrada` | 1.379,0 | 595,3 | **0,43** |
| `pop_total_setor_2022` | 25.972 | 19.894 | **0,77** |

Todas as razões são **< 1**: a amostra é **mais** dispersa que o universo que o próprio
funil consideraria elegível. **Não há restrição de amplitude na direção que afirmei**, e a
defesa "o desenho era conservador" cai. O NO-GO não pode se escorar nela.

---

## O que este teste PODE e NÃO PODE afirmar

Análise de poder por simulação (sinal territorial conhecido injetado sobre a **matriz de
features real**, 300 réplicas por nível, mesmo procedimento e mesmo critério de parada):

| R² territorial verdadeiro | frequência com que este desenho declararia GO |
|---|---|
| 0,05 | 0,7% |
| 0,10 | 2,0% |
| 0,20 | 5,0% |
| 0,30 | 20,3% |
| 0,50 | 73,3% |

**Com N=45, este desenho só detecta sinal FORTE.** Um efeito territorial de R² = 0,20 —
comercialmente relevante — seria declarado NO-GO em **95% das vezes**.

Portanto:

- **PODE afirmar:** não há sinal territorial forte (R² ≳ 0,4) em faturamento/m² dentro do
  universo em que a Ultra opera. E o observado é *negativo*, não apenas nulo: usar
  território **piora** a previsão em relação a chutar a média, com IC inteiramente abaixo
  de zero.
- **NÃO PODE afirmar:** "a pergunta se fecha em definitivo". Essa consequência estava
  escrita no meu protocolo e **não decorre deste teste**. Fica retratada.

---

## Consequência (corrigida)

A pergunta se fecha **operacionalmente, não estatisticamente**.

O motor permanece **triagem territorial** — ranqueia praça, não prevê desempenho de
unidade. Isso agora é **decisão de produto sob evidência nula**, e não "está provado que
território não prevê". A diferença importa: a primeira é honesta, a segunda seria falsa.

**CNAE continua fora**, porque o gate para abri-lo era um GO que não veio.

**O que seria preciso para reabrir**, e é caro: N da ordem de **centenas** de unidades
maduras com metragem e faturamento, não 45. Nova rodada sobre o mesmo dado não muda nada —
o limitante é o N, não o método.

---

## A dívida do grão — VERIFICADA em 2026-08-29

O painel adversarial reportou que o score do hexágono res-7 e o do setor no ponto teriam
Spearman de apenas **+0,085**. **Medi na malha nacional (container de produção, N=48) e o
número do painel está errado:**

| comparação | Spearman | Pearson | erro absoluto médio |
|---|---|---|---|
| hexágono res-7 × **setor do ponto** | **+0,389** | +0,495 | **26,0 pts** |
| hexágono res-7 × **média no raio de 1 km** | **+0,508** | +0,605 | 24,5 pts |

A correlação é **moderada, não nula**. Mas a dívida é real por outro motivo, que os números
mostram melhor que a correlação:

- o erro absoluto médio é de **26 pontos numa escala de 0 a 100** (mediana 27, máximo 68);
- o hexágono lê **sistematicamente mais alto**: mediana 48,0 contra 33,4 do setor do ponto;
- casos extremos: **Paranoá Parque** mede 68,0 no hexágono e **0,0** no setor do ponto;
  Carapicuíba 47,5 × 0,0; Recanto das Emas 45,2 × 0,0.

Isso não é defeito de um dos dois — é que **medem coisas diferentes**. O hexágono cobre
~5 km² e faz média de muitos setores (é o bairro); o setor do ponto tem algumas centenas de
domicílios (é a quadra). Com a régua absoluta da DEC-040, um setor comercial ou de baixa
densidade residencial pontua perto de zero legitimamente, enquanto o bairro em volta pontua
48.

**Consequência prática:** análise feita no grão do hexágono **não é intercambiável** com o
que o Relatório Pontual serve ao operador. Quem comparar os dois lado a lado vai ver números
muito diferentes para o mesmo endereço — e os dois estão certos, para perguntas diferentes.

**Isto enfraquece o E7?** Em parte, e a parte é pequena: erro de medida no preditor atenua
relação e enviesaria o E7 para NO-GO. Mas o bloco de features do E7 **já continha os dois
grãos** — `pop_captacao` e `renda_per_capita_captacao` vêm do catchment de 1,5 km em torno
do **ponto**, não do hexágono. O grão fino estava no modelo e não mudou o veredito.

## Dívida que eu NÃO verifiquei

1. **Teste de maior potência disponível.** `base_calibracao_multirede` traz ~260 unidades
   de três redes em 23 UFs — poder muito maior. Mas o desfecho lá é `alunos_reais`, **não
   faturamento**: licenciaria "sem sinal territorial para DEMANDA", que é uma pergunta
   vizinha, não esta. Vale como evidência de apoio se for medido com o mesmo rigor.
