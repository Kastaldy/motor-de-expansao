# Piloto web — Motor de Expansão

Substituição faseada do Streamlit por um app web. Três telas: **Mapa Territorial**
(porta de entrada por estado → funil de 4 camadas → município), **Visão Executiva**
(a rede Ultra real por estado — Growth API) e **Viabilidade do ponto** (stress-test
de um imóvel real). Os relatórios em PDF saem do Mapa e da Viabilidade.

## Porta de entrada por UF e drill-down

O app abre numa **landing** com um seletor de estado bem visível. Ao escolher um
estado, o Mapa mostra a leitura territorial da **UF inteira** e o painel recomenda
**municípios**; clicar num município **filtra automático** para ele (drill-down).
"Todos os municípios" volta à visão da UF. Dois extras enxutos: **multi-hex**
(comparar vários hexes e somar residual/população/score) e um **filtro global**
"MELHORES" (mostra só os hexes de faixa M1 mais alta).

## Visão Executiva (rede real por estado)

Escolhido um estado, mostra as unidades Ultra num **bubble map** (tamanho ∝
faturamento) e os números REAIS da Growth API (`growth_api_historico.parquet`,
ingestão semanal — DEC-013): faturamento, alunos ativos, churn, NPS e a
**proporção pagantes × agregadores** (Gympass/TotalPass), com o **ranking de
unidades por faturamento**. Cada card traz a variação **vs M-1** (verde/vermelho).

Há um **seletor de PERÍODO** (competência) no topo — escolha o mês a analisar
(evita ficar preso ao mês corrente parcial); o **ranking de unidades** pode ser por
qualquer KPI (faturamento, alunos ativos, churn, NPS, ticket); e churn/NPS mostram a
variação em **pontos percentuais** (`pp`/`pts`), não em % relativo (menos confuso).

**ETL (atenção — a base tem peculiaridades, Felipe 2026-07-20):** os dados são
DIÁRIOS e `faturamento`/`churn`/`cancelados` **acumulam no mês (MTD) e resetam no
dia 1**. Por isso **faturamento e churn são rolling 30 dias** (reconstruídos do
cumulativo: mês + cauda do mês anterior — o MTD parcial mostra ~metade); o M-1
compara a janela equivalente do mês anterior (mesmo dia-do-mês); snapshots
(ativos/pagantes) comparam o mesmo dia. **Dado sujo filtrado**: entradas
administrativas/de teste (faturamento < R$ 20k ou churn > 100%) e unidades paradas
ficam fora; há também uma lista de exclusão explícita (`_EXEC_EXCLUIR`). Camada
PARALELA, sem PII, READ-ONLY sobre o M1.

> **READ-ONLY sobre o M1.** Nada aqui recalcula `score_priorizacao`, pesos ou
> `hex_score_estrutural`, e nenhum artefato oficial é escrito. A camada só lê
> parquet. Vale o guardrail permanente do CLAUDE.md §5.

## Subir

Na raiz do repositório:

```
iniciar-piloto-web.cmd
```

Sobe as duas peças e abre o browser:

| Peça | Porta | O que é |
|---|---|---|
| front | `5000` | Vite + React + deck.gl |
| back  | `8899` | FastAPI que embrulha as funções puras do motor |

Os parquets são gitignored e vivem no checkout da `main`. O `.cmd` aponta
`MOTOR_DATA_DIR` para lá; sobrescreva a variável se o seu caminho for outro.

Manual, se preferir:

```bash
cd web/server && MOTOR_DATA_DIR=<...>/data python -m uvicorn app:app --port 8899
cd web && npm run dev
```

## Como as telas se ligam

O **mapa** conta a história em quatro camadas, e cada uma declara de onde veio e o
que sobrou — no DF: `999 hexágonos → 99 hexágonos quentes → 38 com residual →
23 white spaces → 4 aberturas`. Os números saem do dado real, não são mock. O
passo 1 (Potencial) só conta regiões com **≥ 5.000 habitantes** (mesma régua
`POP_MIN_ACIONAVEL` do mapa, que pinta `<5k` em cinza); o corte propaga por todo o
funil.

No **4º passo** o botão da barra inferior deixa de ser "próxima camada" e passa a
gerar o **Relatório Municipal** (9 páginas).

O filtro de **UF e Município** é ordenado alfabeticamente e ganha um campo de
**busca** (insensível a acento) quando há muitas opções. O painel lateral mostra
até as **10 melhores** localidades da camada; como a lista já chega filtrada pelo
funil (quente + residual + white space), toda recomendação é viável — se houver
menos, a lista encurta sozinha.

Escolhendo um hexágono, "Testar viabilidade deste ponto" leva para a segunda tela
com a coordenada já carregada. Lá, os campos opcionais do imóvel (fotos, valor,
pé-direito, vagas, tipo, observações) alimentam o **Relatório Pontual completo**.

## Pins de concorrentes e Ultra

Cada concorrente aparece como uma **bandeira quadrada** com a logo da rede (fundo
branco + logo) ou, quando o PNG da logo não está disponível, um quadrado da cor da
marca com a sigla (ex.: `SF` Smart Fit, `BF` Bluefit). As unidades **Ultra** usam a
logo própria, um pouco maiores. São enxutos de propósito (o operador pediu "sem
encher a tela"), filtrados ao município e com tooltip (rede + unidade) no hover.

As logos das redes são `logo_<rede>.png` em `<repo>/concorrentes/` (gitignored;
sobrescreva com `MOTOR_COMPETITORS_LOGO_DIR`). Sem elas, o fallback de sigla mantém
o mapa legível. Os pontos vêm de `data/staging/concorrentes_mapeados.parquet` e
`unidades_ultra_performance_hex.parquet`. Camada visual — não altera score/ranking.

## Busca por coordenada

A lupa no cabeçalho aceita uma coordenada (`lat, lng`, com ponto ou vírgula
decimal), um link do Google Maps **ou um endereço livre**. Coordenada/link são
resolvidos offline (parser puro, bbox do Brasil); um endereço cai no **geocoding**
(`/api/geocode`, Nominatim — DEC-010: cache em disco, timeout, fallback gracioso).
Ao encontrar, o mapa voa até o ponto, **solta um pin**, **marca o hexágono** que o
contém (H3 res-7) e abre o atalho **"Estudo pontual →"**, que leva à Viabilidade
daquele ponto — funciona mesmo fora do município carregado (a viabilidade e o
Relatório Pontual são geográficos, resolvem o município no servidor).

## Guardrail da demanda

A demanda da Viabilidade é **premissa explícita do operador** — nunca prevista pela
geografia (DEC-009). A ferramenta testa o número que você assume; ela não adivinha
quantos alunos o ponto teria.

Ela **vem preenchida com o p50** da curva tamanho→densidade para a metragem
informada (dos comparáveis Ultra, depende só de `m²`) e **re-escala** quando você
muda a metragem — até você mexer no `±`, aí o valor manual prevalece (o link
"voltar ao p50" restaura). É um ponto de partida honesto, não uma previsão: o
badge diz "padrão · p50" ou "ajuste manual" conforme o caso.

A demanda também **dimensiona a folha** (ver a seção abaixo): é ela que define o
tamanho da equipe que a unidade contrata para abrir a porta.

## Motor único de viabilidade

Desde o ciclo **FIN-VIAB-01** existe **um** motor e **uma** série mensal. O backend
chama `simular()` (`dimensionamento/simulador.py`), que devolve um `ViabilidadeResult`
com **tudo já calculado**, e serve isso como `viabilidade_payload_v1`. **Tela, API e
PDF consomem exatamente o mesmo objeto e não recalculam nada** — se um número aparece
em dois lugares, é literalmente o mesmo campo.

Antes disso havia cinco séries mensais independentes e nove KPIs com implementação
dupla, e o mesmo cenário divergia entre tela e PDF (payback 35 no KPI e 33 no gráfico,
aluguel-teto R$ 55.535 na tela e R$ 105.813 no PDF). Toda premissa vive em
`dimensionamento/config.py` e está documentada em `PREMISSAS_VIABILIDADE.md` (default,
fonte, quem pode alterar). **Nenhuma fórmula financeira pode ser escrita fora do
simulador** — se der vontade, ela já existe lá.

A série é **uma linha do tempo de M-4 a M+60**: quatro meses de pré-abertura (obra,
parcelas da taxa de franquia, aluguel se já houver contrato) e sessenta de operação.
O CAPEX aparece **inteiro** nela, então o payback do gráfico e o payback do KPI são,
por construção, o mesmo número.

### Folha — custo FIXO desde o mês 1

A folha **não escala com a rampa de alunos**. Ela é dimensionada **uma vez**, por
`SIM_FOLHA_PCT` (17%) aplicado ao faturamento **MADURO** — o de regime pleno, a preços
do ano 1 —, e esse valor é pago **integralmente desde o mês 1**, reajustando
anualmente como os demais custos. No caso de referência: 17% × R$ 288.257,57 =
**R$ 49.003,79/mês**, do M1 ao M60.

Antes (até 2026-07-24) ela era `17% × faturamento DO MÊS`, então encolhia junto com a
rampa — custava R$ 15.678,87 no mês 1. Isso equivalia a supor que **se contrata gente
na medida em que o aluno entra**, e escondia duas coisas: a queima de caixa real dos
primeiros meses e o break-even verdadeiro. Decisão de Felipe (2026-07-24): **a equipe
existe antes dos alunos**.

Três consequências que aparecem na tela:

- **A folha é custo fixo, não percentual.** O fator receita → EBITDA (`k`) **não**
  subtrai mais a folha: passou de `0,628985` para **`0,798985`**. O bloco de custo
  fixo passou a incluí-la (sem aluguel: R$ 38.150 → **R$ 87.153,79**).
- **A alavancagem operacional aumentou.** Mais custo fixo e mais contribuição por
  aluno: cada aluno vale mais no topo, e a falta de alunos dói mais embaixo.
- **O mês 1 fica mais duro e o steady não muda.** O EBITDA do mês 1 vai de
  −R$ 10.139,56 para **−R$ 43.464,47**; o mês 12 (steady) fica **idêntico**, porque lá
  o faturamento já é o maduro. O que muda é a rampa e tudo que deriva dela —
  break-even, payback, TIR, VPL.

O **nível** (17%) segue pendente de gate da controladoria (o BLK-VIAB-11 apurou 25-26%
em 6 DREs reais); a **estrutura** (fixa) está decidida. Detalhe em
`PREMISSAS_VIABILIDADE.md` §4.1.

### Anuidade

A DRE tem uma linha de **anuidade** (a `Simulador!J10` da planilha, que o motor não
implementava até 2026-07-24): **R$ 99 uma vez por ano** por aluno de **balcão** que
completa 12 meses de casa. Quatro detalhes que mudam o número:

- **Agregador não paga.** O aluno de Gympass/TotalPass não tem contrato com a
  academia — o agregador remunera por acesso.
- **Nem todo aluno chega aos 12 meses.** A fatia elegível é **derivada do churn**
  (`(1 − churn)¹²` = `0,94¹²` = **47,59%**), não um número fixado à mão: mexer no
  churn ajusta a elegibilidade sozinho.
- **Reconhecimento pro-rata mensal** (`99 ÷ 12` a partir do mês 12), não um
  lançamento único — os aniversários se espalham pelo ano, e o lançamento único
  criaria um degrau falso no gráfico de caixa.
- **O steady-state passa a ser o mês 12**, não o mês da maturação (8): só aí o
  regime é pleno (alunos maduros *e* anuidade em cobrança). O motor serve esse mês
  em `premissas.mes_referencia_steady` — **tela, gráficos e PDF leem de lá e não
  recalculam**.

A linha aparece explícita no payload (`dre.receita_anuidade`), justamente para que o
faturamento não suba sem uma causa visível na tela. No caso de referência são
**R$ 6.241,94/mês**, 2,2% do faturamento. O valor e as quatro regras vivem em
`config.py` (`SIM_ANUIDADE_*`) e estão documentados em `PREMISSAS_VIABILIDADE.md`
§2.1 — mudar qualquer um deles é decisão do dono do produto, não de engenharia.

## Indicadores

**Break-even em alunos TOTAIS.** O número é diretamente comparável com a demanda que
você digita, porque o mix balcão/agregadores (69/31) escala junto. Antes o break-even
variava só o balcão, com os agregadores congelados na premissa, e era exibido como se
fosse total — dava 632 contra uma demanda de 2.304. Hoje, no caso de referência, são
**1.152,0 alunos totais** (margem de segurança de 2,0×). São dois: o de **EBITDA**
(cobre o custo operacional) e o de **caixa** (cobre também a PMT do financiamento —
1.542,4 alunos). Os dois são medidos em **regime pleno**, com a anuidade dentro da
receita por aluno — a mesma régua da DRE de steady-state, para não haver duas contas
do mesmo cenário.

A conta usa a **folha da demanda que você assumiu**, e é isso que a torna honesta: ela
responde "montei a casa para 2.304 alunos; com quantos eu empato?" — não "com quantos
eu empato se a equipe também encolher junto". Enquanto a folha era percentual, o
break-even saía otimista (840,6).

**TIR e VPL.** A TIR sai do fluxo de caixa real dos 64 meses; o VPL desconta o mesmo
fluxo a **12% a.a.** — taxa **provisória, pendente de aval do comitê** (muda o VPL, não
muda payback, EBITDA nem TIR). Quando o fluxo não troca de sinal não existe raiz real:
a TIR vem como `null` explícito, nunca como `NaN`.

**Retorno desalavancado** é o padrão (resultado antes da PMT ÷ investimento cheio). O
retorno de **equity** existe como visão secundária e nunca aparece no mesmo KPI.

**Aluguel-teto** é % do faturamento bruto de steady-state, em três faixas — ideal 15%,
teto 20% e exceção 30%. O exibido como "aluguel-teto" é o de **20% (o teto)**, porque o
card tem de mostrar o limite que a operação defende; 30% é caso de exceção, não
referência. As **três faixas viajam no payload e aparecem tanto na tela quanto no
PDF**: mostrar só o canônico esconde a régua que dá sentido a ele.

## CAPEX, carência e reajuste

A sidebar tem inputs opcionais de **investimento**: obra (parcelada, sem juros),
equipamentos (financiados no Price, com prazo e juros), **taxa de franquia** (agora
editável — o default é R$ 160.000) e **carência de aluguel**.

A **taxa de franquia é parcelada em 4× sem juros** (default), nos mesmos meses da
obra (M-4 a M-1) — antes ela saía inteira do caixa no M-4. A pré-abertura fica plana
em **R$ 190.000/mês** no caso de referência (obra 150.000 + franquia 40.000) em vez de
R$ 310.000 no primeiro mês. É **só timing de caixa**: EBITDA, margem, break-even,
payback e acumulado de 60 meses **não mudam**; só TIR (+0,33 pp) e VPL (+R$ 2.241,80),
que são sensíveis à data de cada real.

A **carência** é do motor, não pós-processamento: conta em `mes_contrato`, ou seja, a
partir de **M-4 (entrega da unidade)**, não da abertura — que é como o contrato de
locação costuma ser escrito.

O **reajuste anual** de 4% a.a. incide sobre ticket, aluguel e custos fixos (**a folha
inclusive**), como um degrau a partir do mês 13. A **PMT é nominal e não reajusta**.

CAPEX e carência entram no **payback** e no fluxo de caixa — **não na margem**, que é
operacional de steady-state.

## Fluxo de caixa acumulado

O gráfico de **FCF acumulado** plota a série mensal real (`serie_mensal` do payload,
M-4 a M+60): mergulha com o CAPEX na pré-abertura, sobe pela rampa de maturação e cruza
a linha do zero no **payback** — área vermelha abaixo, verde acima, com o marcador do
mês de virada. Reage a metragem, aluguel, demanda, CAPEX, carência e taxa de franquia.

Duas coisas que o gráfico agora mostra e antes ficavam escondidas pela média de
steady-state: o **EBITDA do mês 1 é bem negativo** (−R$ 43.464,47 no caso de
referência — a folha é integral desde a abertura, enquanto os alunos rampam por 8
meses; o mês 4 já vai a +R$ 21.522,79) e há um **mês declarado de virada do caixa
operacional** (`mes_caixa_operacional_positivo` — mês 6 no caso de referência).

## Estrutura

```
web/
  server/app.py         backend do piloto (não toca src/motor_expansao/api/)
  src/
    lib/                contrato de tipos, cliente HTTP, formatação pt-BR
    components/         dock, mapa deck.gl, painel narrativo, stepper, gráficos
    screens/            MapScreen, ViabilityScreen
    styles/tokens.css   paleta e escalas
```

## Cores dos hexágonos

Idênticas ao dashboard Streamlit (CLAUDE.md §5): faixas de 10 pontos via
`RESIDUAL_SCORE_BANDS` (vermelho→verde), corte de `<5k hab` em cinza e score NaN
com fill próprio — porte 1:1 de `dashboard/utils.score_band_to_color`. O score que
colore muda por passo, espelhando os modos do dashboard: passo 1 → censitário,
passos 2–3 → residual, passo 4 → M1. Os hexágonos **do passo atual ficam em
opacidade cheia e os de fora esmaecem** — um holofote no funil, sem contorno
colorido (as 10 aberturas do passo 4 precisam se destacar no meio do mapa). Só o
hex selecionado ganha um contorno claro.

## Tooltip do hexágono

Ao passar o mouse, o tooltip espelha o do dashboard Streamlit: **Município / UF**,
**Faixa M1**, os três scores (M1, censitário, residual — o que colore o mapa no
passo atual vem em destaque), **Habitantes**, **Renda per capita**, **Renda média
domiciliar**, **Residual Fitness** e concorrentes no raio. A renda domiciliar usa a
mesma fórmula do Streamlit (`renda per capita × moradores × uplift × fator
temporal`, todos municipais); sem os parquets municipais de uplift no `data/`, cai
no fallback nacional — igual ao Streamlit local.

O basemap é o **CARTO Dark Matter** (tiles online, precedente DEC-004/DEC-010),
com fallback gracioso ao gradiente do tema se a rede faltar — a interatividade do
mapa não depende de internet.

## Tipografia

O template de referência usa Manrope + JetBrains Mono. Aqui:

- **Instrument Serif** — voz narrativa (títulos de camada, veredito)
- **Instrument Sans** — interface
- **IBM Plex Mono** — todo número, com figuras tabulares

A separação serif/sans é o que faz a tela ler como um briefing e não como um
painel de métricas.

## O que ainda não é

Piloto. O corte do Streamlit foi decidido e executado pela DEC-022 (2026-08-03) — este app é o único de produção.
As outras três abas do dock aparecem desabilitadas de propósito, para deixar
explícito que isto é um recorte.

Custos conhecidos: a primeira leitura de uma UF carrega a partição inteira
(alguns segundos); o Relatório Pontual baixa tiles de rua e leva ~80 s em área
densa.
