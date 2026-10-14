# BLK-UNI-05B — Alavancas do operador (entradas da viabilidade v2)

Versão 1.0, 2026-09-29. Escrito antes de rodar e revisado por um revisor adversarial, também antes de rodar (§10).
Só análise; nada vai para produção.

## 1. Pergunta

A v2 prevê o faturamento maduro **da praça**, com o modelo de negócio típico da rede. O operador decide antes de abrir
algumas coisas que mudam esse número. Para cada uma: **quanto ela muda o faturamento maduro, e por onde (alunos ou
ticket), com a praça constante?** O resultado vira um multiplicador que a v2 aplica sobre a previsão da praça.

Alavancas (as que o Felipe listou em 2026-09-29):
1. **aceita agregador** (Wellhub/TotalPass);
2. **preço do plano** (Gold);
3. **estúdios e modalidades**;
4. **vagas de estacionamento** (comodidade).

## 2. O que já se sabe antes de rodar (e o que já foi visto)

**Olhando só o X, sem o desfecho:**
- **As 39 unidades de treino aceitam agregador.** Só Botafogo, entre as 18 de teste, não aceita. O "sim/não" **não se
  estima comparando unidades**.
- O **TotalPass entrou em datas diferentes** em unidades que já operavam (2022–2024). Isso permite medir o efeito de
  **passar a aceitar um agregador** dentro da mesma unidade, contra as outras unidades no mesmo mês (parte A).
- Preço, estúdios, modalidades e vagas só existem como **retrato do cadastro** (ago/2026). Para eles, a única medida
  possível é a comparação entre unidades, com a praça controlada (parte B).

**Já visto com o desfecho, em etapas anteriores** (declarado para não passar por teste cego):
- A anatomia dos erros (28/09) correlacionou, nestas mesmas 39 unidades, o **preço Gold** com o erro do M0: ρ +0,31 no
  faturamento e +0,47 nos alunos. Correlacionou também as **vagas por 1.000 m²** (ρ +0,03).
- A parte B é **exploratória para preço e vagas**.
- Botafogo (teste) motivou este estudo. A confirmação da parte C é reportada **com e sem Botafogo** e só vale se se
  sustentar nas duas.

## 3. Parte A — aceitar agregador (estudo de evento dentro da unidade)

**Datação:** pelo número de alunos TotalPass em **todos** os meses do Growth, não só nos válidos para faturamento.
- **Entrada:** 1º mês com `alunos_totalpass > 0`, depois de pelo menos um mês sem.
- **"Desde o início":** tem TotalPass já no 1º mês da série.
- Para conferência, grava-se:
  - o 1º mês com receita de TotalPass no Financeiro;
  - os alunos TotalPass nos meses −3 a +3.
- **Datação conferida com o Financeiro:** o evento sai se o Financeiro tem receita de TotalPass **2 meses ou mais
  antes** da entrada no Growth. É sinal de que a unidade já aceitava e a contagem do Growth começou depois.
  - Pelas datas, isso exclui Setor Oeste: R$ 8–15 mil/mês de TotalPass no Financeiro desde a abertura (2023-02) e
    zero aluno TotalPass no Growth até 2023-12.
- **Receita incompleta:** a linha de TotalPass do Financeiro só existe na rede a partir de **2023-10** (antes, em 1–2
  unidades).
  - Meses com alunos TotalPass e sem essa linha **não entram nos desfechos de receita** (faturamento, ticket): a
    receita do TotalPass pode não estar no total.
  - Os desfechos de alunos (Growth) usam todos os meses.

**Evento:** entrada com:
- `mes_vida` ≥ 6 no mês do evento (a entrada junto com a inauguração não conta: a rampa confundiria);
- **≥ 4 meses válidos antes, com `mes_vida` ≥ 6, na janela** (os que entram na regressão);
- **≥ 3 meses válidos depois, na janela**.

A unidade fica tratada daí em diante. Período de exploração: **até 2025-12**.

**Desenho empilhado** (um bloco por evento):
- janela de calendário de 12 meses antes a 12 meses depois do evento;
- **tratada:** a unidade do evento, nos meses válidos da janela com `mes_vida` ≥ 6;
- **meses de controle:** meses válidos de outras unidades, com `mes_vida` ≥ 6, em que a unidade:
  - nunca teve TotalPass;
  - ou **ainda não** recebeu o seu (só os meses anteriores à entrada dela);
  - ou já tinha TotalPass **mais de 12 meses antes do evento, comprovadamente**:
    - entrada datada antes de E − 12;
    - ou série começando antes de E − 12 já com TotalPass;
    - e com TotalPass em **todos** os meses da janela.
- Cada unidade de controle precisa de ≥ 3 meses antes e ≥ 3 a partir do mês do evento.
- **Um evento só entra na estimativa principal com ≥ 3 unidades de controle.** Olhando só as datas, isso deixa 3
  eventos: Santos (2022-10), Lago Sul (2023-10) e Jardim Botânico (2024-03).
  - Santos tem só 1 mês depois com receita completa. Na prática, **alunos e a conta de substituição vêm dos 3
    eventos; o faturamento, de Lago Sul e Jardim Botânico**.
  - O grupo de SP que entrou em 2023-01/02 tem 2 controles e entra só na sensibilidade 1.
- **Modelo:** `y = efeito unidade×bloco + efeito mês×bloco + faixa de maturidade + β·depois + erro`.
  - Faixas de `mes_vida`: 6–8, 9–11, 12–17, 18–23, 24+ (referência). Placeholder de inauguração conta como 24+.
  - Se a matriz perder posto (faixa colinear com o evento), o ajuste é refeito sem as faixas, e isso é marcado. Se
    ainda perder, sai "não identificado".

**Desfechos (mensais, meses válidos):**
- log do total de alunos (`ativos`), esperado **+**;
- log dos recorrentes (`pagantes`, balcão), esperado **−** ou 0 (canibalização);
- log do faturamento (Financeiro), **±**;
- log do ticket médio (faturamento ÷ ativos), esperado **−**;
- **em nível** (para a conta de substituição): `ativos`, `pagantes`, `agregadores`.

**Inferência:**
- IC 90% com erro-padrão agrupado por unidade (CR1, t com G − 1 graus de liberdade). Com 4 unidades tratadas, ele
  tende a sair **estreito demais**;
- por isso, também um **IC 90% por bootstrap** de unidades (2.000 reamostras, semente fixa). A reamostragem é
  estratificada: tratadas e controles em separado.

**Checagens:**
- **retirar cada evento:** o sinal de β se mantém? Retirada sem estimativa conta como falha;
- **placebo:** evento falso 6 meses antes do real, usando só os meses anteriores ao real.
  - Um evento só testa o placebo se tiver ≥ 2 meses antes de −6 e ≥ 2 entre −6 e −1.
  - Pelas datas, só Lago Sul e Jardim Botânico têm isso. Santos tem só os meses −4 a −1, ainda na rampa
    (`mes_vida` 6–9).
  - O placebo é "**testável**" com ≥ 3 eventos que o testam;
- **perfil no tempo:** β por faixa de meses em relação ao evento (−12 a −7, −6 a −4, −3 a −2; ref. −1; 0–2, 3–5,
  6–8, 9–12). Reporta-se se os IC das faixas anteriores ao evento cobrem zero.

**Sensibilidades:**
1. com o grupo de SP de 2023-01/02;
2. só meses com `mes_vida` ≥ 12, para tirar a rampa dos períodos anteriores;
3. controles só "nunca" e "ainda não" (sem os que já tinham TotalPass), nos eventos principais que ficam com ≥ 2
   controles;
4. sem as unidades com placeholder de inauguração como controle.

**Leitura do faturamento (fixada antes; vale a primeira que casar):**
1. **"efeito medido":**
   - o IC CR1 e o IC bootstrap excluem zero;
   - o sinal se mantém ao retirar cada evento;
   - o placebo é testável e cobre zero.
2. **"efeito provável, sem teste de tendência prévia":** as mesmas condições, mas o placebo não é testável e, onde é
   estimável, cobre zero.
3. **"sem efeito líquido relevante":**
   - o IC CR1, o IC bootstrap e todas as retiradas de evento ficam dentro de −10% a +10%;
   - ou seja, aceitar o agregador troca ticket por volume, com saldo neutro.
4. **"inconclusivo":** o resto.

**Conta de substituição** (como a v2 recebe "não aceita agregador"):
- s = −β(pagantes, nível) ÷ β(agregadores, nível): quantos recorrentes a unidade perde para cada aluno de agregador
  que ganha.
- Numa unidade sem agregador, supõe-se o mesmo **s** no sentido inverso. Ela perde a fatia típica de alunos de
  agregador da rede (**a**) e recupera s·a recorrentes por aluno.
- Com ρ = receita por aluno de agregador ÷ receita por recorrente (parte D), o multiplicador sobre a previsão da praça
  é `m = 1 + a·(s − ρ) / (1 − a + a·ρ)`.
- A faixa de m vem de um bootstrap conjunto de s (eventos), ρ (unidades da parte D) e a (as 39 de treino).
- **Declarado agora:** é extrapolação. O dado mede a entrada de **um** agregador (TotalPass) sobre o Wellhub já
  aceito, não a ausência dos dois.

**Confirmação de direção** (dado diferente, 2025–2026): saídas de agregador datadas nos meses do Growth.
- Condições da saída:
  - primeiro mês sem o agregador em 2025-01 ou depois;
  - agregador presente em ≥ 3 dos 4 meses anteriores;
  - média de ≥ 20 alunos dele nos 3 meses anteriores;
  - ≥ 4 meses válidos antes e ≥ 3 depois;
  - controles com status constante na janela.
- Mesmo estimador, com um tratado só: reporta-se só o sinal, sem IC. A receita do agregador no Financeiro antes e
  depois é mostrada para conferir.

## 4. Parte B — preço, estúdios, modalidades, vagas (comparação entre unidades)

**Amostra:** as 39 maduras de 2025 do UNI-02 (treino), mesmos desfechos do UNI-01 (`desfechos`, jan–dez/2025,
≥ 3 meses com `mes_vida` ≥ 12).

**Modelo:** base M0 (log m², log renda, log população da isócrona de 10 min de carro) + **uma** alavanca por vez.
Mesmo ajuste do UNI-01 (`ajustar`): MQO, IC 90% HC3, ΔR² LOO, retirada de cada metro e sensibilidades A (maturidade
ajustada) e B (jan–set/2025).

| id | alavanca | X | desfechos | sinal esperado no faturamento |
|---|---|---|---|---|
| L1 | preço do plano Gold | `cad_preco_gold` (R$) | faturamento, alunos, ticket | ± (preço sobe o ticket e pode tirar alunos) |
| L2 | tem estúdios | `cad_mod_studios` | faturamento, alunos, ticket | + |
| L3 | nº de modalidades | soma de piscina, estúdios, bike, lutas, pilates (0–5) | faturamento, alunos, ticket | + |
| L4 | vagas | log(1 + `tam_vagas`) | faturamento, alunos, ticket | + |

- **Classificação** pelas regras do UNI-01 (§6), aplicada ao **faturamento**: candidata, fraca, inconclusiva,
  descartada ou contrária. Alunos e ticket só decompõem, sem classe própria.
- Efeito reportado por 1 desvio-padrão e na unidade de negócio:
  - **por R$ 10** de preço;
  - **ter × não ter** estúdios;
  - **+1 modalidade**;
  - **dobrar as vagas** (≈ log 2 em log(1 + vagas); a aproximação vale para 20 vagas ou mais).
- Nas sensibilidades, a conversão usa o desvio-padrão da própria amostra.
- São 4 testes a 10%: espera-se ~0,4 falso positivo. Por isso existe a parte C.

## 5. Parte C — confirmação nas 18 unidades de teste (2026)

Para cada alavanca da parte B, ajusta-se M0 + alavanca no treino e prevê-se o teste, com o mesmo ajuste de calendário
e a mesma metragem do UNI-02. Compara-se com o M0 **nas mesmas unidades** (as que têm a alavanca preenchida):
- erro típico (mediana de |erro|) e ordenação (Spearman);
- diferença de erro com IC 90% por bootstrap pareado (2.000 reamostras).

Tudo é reportado **com e sem Botafogo**. A alavanca é "**consistente**" se, nas duas versões, o erro cai e a ordenação
não piora. Senão, "**não se repete**". Com menos de 5 unidades de teste, sai "sem amostra". Com 15–18 unidades, o IC
quase certamente cruza zero. Isso é declarado agora.

## 6. Parte D — premissa do simulador: quanto rende um aluno de agregador

Base: meses válidos de 2025 das unidades maduras (`mes_vida` ≥ 12). No Financeiro, faturamento = vendas + Wellhub +
TotalPass − Tem Saúde.
- **Receita de agregador:** Wellhub + TotalPass do Financeiro.
  - Componente ausente com 0 alunos daquele agregador conta como 0.
  - Componente ausente com alunos > 0 tira o mês.
- **Receita do recorrente:** faturamento − receita de agregador. O desconto do Tem Saúde fica todo no recorrente.
  Reporta-se também a versão bruta (sem o desconto).
- **Por aluno:**
  - `r_agr` = receita de agregador ÷ alunos de agregador;
  - `r_rec` = receita do recorrente ÷ recorrentes.

Reporta-se a mediana dos meses da razão **ρ = `r_agr / r_rec`**, no geral e por agregador, e a mediana por unidade.
**O simulador supõe 60%.**

## 7. Como o resultado vira entrada da v2 (proposta; a decisão é do Felipe)

Cada alavanca sai com um rótulo:
- **medida e consistente:** a v2 aplica o multiplicador medido;
- **medida, não confirmada:** o multiplicador é mostrado como faixa, sem entrar no número central;
- **sem efeito relevante:** a v2 não muda o número central;
- **sinal oposto ao esperado:** não entra sem decisão explícita;
- **não medida:** a v2 faz só a aritmética do simulador. Exemplo: preço × os mesmos alunos, com aviso de que o efeito
  sobre o volume não foi medido.

**Parte B → rótulo:**

| classe no faturamento | rótulo |
|---|---|
| candidata + parte C consistente | medida e consistente |
| candidata sem a parte C consistente, ou fraca | medida, não confirmada |
| descartada, **e** o IC na unidade de negócio entre −10% e +10% | sem efeito relevante |
| descartada, mas o IC na unidade de negócio passa de ±10% | não medida |
| contrária | sinal oposto ao esperado |
| inconclusiva | não medida |

**Parte A → rótulo:**
- **"aceita mais um agregador"** (governado por β do faturamento):
  - efeito medido e saídas consistentes → medida e consistente;
  - efeito medido sem saídas consistentes, ou efeito provável → medida, não confirmada;
  - sem efeito líquido relevante → sem efeito relevante;
  - inconclusivo → não medida.
  - "Saídas consistentes" quer dizer que, em todas as saídas analisáveis de 2025–2026, os efeitos no total de alunos
    e no faturamento têm o sinal **oposto** ao da entrada. Sem nenhuma saída analisável, não é consistente.
- **"não aceita agregador"** (governado por m): no máximo "medida, não confirmada", por ser extrapolação. Exige:
  - IC CR1 de β(agregadores, nível) excluindo zero;
  - o sinal de s se mantendo ao retirar cada evento.

  Senão, "não medida".

## 8. Limites (declarados antes)

- **Agregador:**
  - mede a entrada do TotalPass sobre o Wellhub, quase toda em SP e DF, em 2022–2024. "Nenhum agregador" é
    extrapolação pela conta de substituição;
  - dos 3 eventos principais, Santos tem o período anterior na rampa;
  - antes de 2023-10, o Financeiro não tinha a linha de TotalPass na maior parte da rede. Por isso a receita dos
    eventos de 2022–2023 é quase toda descartada;
  - as unidades de SP com placeholder de inauguração são tratadas como 24+, mas tinham ≥ 14–17 meses em 2022–23;
  - o Financeiro recebe Wellhub/TotalPass com atraso. Nos primeiros meses depois da entrada, a receita aparece menor e
    o ticket, mais baixo do que de fato.
- **Preço:**
  - retrato de ago/2026 contra desfecho de 2025;
  - o operador põe preço mais alto onde a demanda aguenta, e isso puxa a elasticidade medida para cima: o volume parece
    cair menos do que cairia de fato;
  - já foi olhado contra o erro do modelo (§2).
- **Vagas:** o dicionário do painel registra que vagas são colineares com o m². Com o m² no modelo, mede-se o efeito
  das vagas a mais para o mesmo tamanho. Já foi olhado (§2).
- **Estúdios e modalidades:** associação, não causa. Unidades com mais estrutura podem ter também operador melhor ou
  ponto melhor.
- **Amostra:**
  - N = 39 no corte transversal;
  - no agregador, 4 eventos principais, com poucos controles em 2022–2023, quando a rede tinha 14–23 unidades.
- **Para revisão futura:** o RJ começou a aceitar Wellhub em algumas unidades em set/2026, um experimento natural
  "não aceitar → aceitar". Em ~6 meses dá para medir direto.

## 9. Arquivos

`alavancas/01_alavancas.py` → `resultado_alavancas.md`, `eventos_agregador.csv`, `saidas_agregador.csv`,
`alavancas_corte.csv`, `confirmacao_alavancas.csv`. Cada parte grava o seu arquivo assim que termina.

O relatório inclui uma **ilustração** (não teste) de Botafogo com o multiplicador m. Congelamento em
`REGISTRO_CONGELAMENTO.txt` antes de rodar.

## 10. Revisão antes de rodar (2026-09-29)

Um revisor adversarial leu a primeira redação e o script sem rodar nada. O que mudou:
- declarados os pontos já vistos (§2);
- datação conferida com o Financeiro, e descarte dos meses de receita incompleta;
- placebo com testabilidade por evento e leitura "efeito provável" quando não é testável;
- bootstrap e retiradas de evento exigidos também para "sem efeito";
- controles que já tinham TotalPass precisam comprovar a data e manter o status;
- datação por todos os meses do Growth;
- filtros de saída;
- checagem de posto da matriz;
- fórmula de m pela razão ρ, com bootstrap conjunto;
- rótulo próprio para m;
- a faixa de irrelevância da parte B aplicada na unidade de negócio;
- parte D sem o substituto do Growth e com o Tem Saúde num lugar só;
- sensibilidades 2 a 4;
- confirmação com e sem Botafogo;
- gravação por parte.
