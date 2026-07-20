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
ingestão semanal — DEC-013): faturamento/mês, alunos ativos, churn, NPS e a
**proporção pagantes × agregadores** (Gympass/TotalPass), além do ranking de
unidades por faturamento. Camada PARALELA, sem PII, READ-ONLY sobre o M1.

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
que sobrou — no DF: `999 hexágonos → 99 setores quentes → 38 com residual →
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

## CAPEX e carência de aluguel

A sidebar tem inputs opcionais de **investimento**: CAPEX total (R$), % financiado,
parcelas e **carência de aluguel** (meses iniciais sem pagar aluguel). Vazios, o
motor usa o padrão (R$ 2,34 mi, sem carência). CAPEX e carência entram no **payback**
e no fluxo de caixa — **não na margem** (que é operacional de steady-state). O
readout na sidebar e o **KPI Payback** (na fileira principal, para bater o olho)
mostram o resultado.

A carência é aplicada como pós-processamento da série canônica do simulador
(`gerar_serie_mensal`): devolve o aluguel nos primeiros N meses, antecipando o
payback. Não altera o motor.

## Fluxo de caixa acumulado

O gráfico de **FCF acumulado** plota a série mensal REAL dos 60 meses (do
`gerar_serie_mensal`): mergulha com o CAPEX, sobe pela rampa de maturação e cruza a
linha do zero no **payback** — área vermelha abaixo, verde acima, com o marcador do
mês de virada. Reage a metragem, aluguel, demanda, CAPEX e carência.

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

Piloto. O corte do Streamlit está fora de escopo e depende de decisão + DEC.
As outras três abas do dock aparecem desabilitadas de propósito, para deixar
explícito que isto é um recorte.

Custos conhecidos: a primeira leitura de uma UF carrega a partição inteira
(alguns segundos); o Relatório Pontual baixa tiles de rua e leva ~80 s em área
densa.
