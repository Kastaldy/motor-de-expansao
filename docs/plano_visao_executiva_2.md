# Visão Executiva 2.0 — de mapa com painel a dashboard acionável da rede

## Context

A aba **Visão Executiva** do piloto web (`web/src/screens/ExecutiveScreen.tsx` + `GET /api/executiva/{uf}`) nasceu como um **mapa deck.gl em tela cheia** com um painel lateral de 4 KPIs e uma lista ordenável. Ela responde bem a "onde estão as unidades", mas mal a "o que fazer com elas".

O pedido do Felipe (2026-08-04) é inverter a perspectiva: **o dado da rede vira o protagonista e o mapa vira apoio**, transformando a aba num relatório útil e acionável pelo time de campo. Decisões tomadas na abertura:

| decisão | escolha |
|---|---|
| Mapa | **card secundário**, ao lado da carteira — não mais o plano de fundo |
| Recorte | **rede toda com filtros** (UF, `master`, coorte) — hoje obriga escolher uma UF antes de ver qualquer coisa |
| Uso | **carteira priorizada → ficha da unidade** (dois níveis) |
| Export | **PDF da ficha + PDF da carteira + CSV/Excel** |

A matéria-prima é boa e está subaproveitada: `growth_api_historico.parquet` tem **102 unidades, 29 colunas, série diária desde abr/2022** (53 meses), atualizada todo dia às 06:30 pelo cron. A tela usa 7 dessas colunas.

**E há um alvo concreto.** O time de campo já construiu, com ajuda do Claude, um `analise_diariaconsultoria.html` (Chart.js, 8 telas, 15 gráficos) que eles alimentam **importando um `.xlsx` na mão todo dia**. Esta aba existe para **aposentar esse trabalho manual** — o critério de sucesso não é "um dashboard bonito", é *o consultor abrir a aba e já ter o que hoje ele monta à mão*. A §2 destrincha o que eles fazem, porque é a especificação real do produto.

> **Este plano NÃO altera o M1.** Nenhum artefato, pipeline, score ou peso é tocado. É leitura da camada paralela Growth, como a aba já é hoje.

---

## 1. O alicerce está torto — e isso vem primeiro

Medi a base de produção antes de desenhar qualquer tela. **Dois números que a aba mostra hoje estão errados**, e construir análise em cima deles propagaria o erro.

### 1.1 Ticket médio: 76% subestimado

`ticket_medio_pagantes` **não é snapshot** — é `faturamento_sem_agregador / pagantes` acumulado no mês (confirmado em **100% das linhas**). O backend a trata como snapshot (`app.py:2129-2130`), então no dia 2 do mês a tela mostra o ticket de dois dias:

```
Botafogo, jul/2026:  dia 1 → R$  7,75   dia 15 → R$ 90,92   (cresce o mês inteiro)
SP, dia 2 de junho:  exibido R$ 20,28  |  real ≈ R$ 163,67
```

**Atenção — correção a uma hipótese inicial:** eu havia suposto que o campo `ticket_medio` fosse o snapshot correto. **Não é.** Ele tem 26,5% de zeros no dia 1, correlação de apenas **0,313** com o ticket real, e nenhuma de 6 fórmulas candidatas explica mais que 11% dos seus valores — é outra grandeza (comportamento compatível com "ticket dos planos vendidos no mês", mas isso é hipótese não confirmada com a Growth).

**Conserto correto** — calcular a partir de primitivas que entendemos, com o `rolling30` que já existe (`app.py:2051`):

```python
receita_por_recorrente = rolling30(g, ano, mes, "faturamento_sem_agregador") / pagantes_snapshot
```

Validação: rolling-30 dá **R$ 163,67** e o mês fechado M-1 dá **R$ 162,47** — concordam em 0,7%.

**O rótulo NÃO pode ser "ticket médio"** — e isto ficou claro com o DAX oficial (§9). No PowerBI, `TICKET_MEDIO` é o **ticket da venda**: `SUM(FT_RELATORIO_VENDAS[VALOR_REAL]) / COUNTROWS(...)`, com piso de R$ 19,90, vindo de uma **tabela de vendas individuais que não existe na base Growth** (lá só há a contagem `vendas`). Medida a correlação entre as duas grandezas: **0,285** — são coisas diferentes (R$ 153 de mediana contra R$ 113).

Se chamarmos nosso número de "ticket médio", o time de campo vai compará-lo com o do PowerBI e concluir que um dos dois está errado. O rótulo é **"Receita por recorrente (sem agregador)"**, e fica registrado que `TICKET_MEDIO` é **irreproduzível** com os dados da API — só voltaria se a Growth expusesse a venda individual.

### 1.2 NPS inflado por sentinela

`999` é sentinela de "sem pesquisa no período" (**5,5% das linhas, 53 unidades**) e entra na média ponderada sem filtro. Em SP: **67,4 exibido vs 62,8 real**.

Filtro correto é a **faixa canônica** `-100 <= v <= 100`, não `v > 0`: **NPS negativo é legítimo** e não pode ser descartado. Servir junto `nps_cobertura_pct` — sem isso, "NPS 62,8" esconde que 6 unidades não responderam.

### 1.3 Três unidades têm a série histórica partida ao meio

Achado que **bloqueia o Nível 2**. A ingestão passou a gravar UTF-8 correto em 20/02/2026 e o `groupby("unidade")` enxerga duas unidades onde há uma:

```
'P?TIO BRASIL - DF'  158 linhas até 19/02/2026  ┐ mesma inauguração, datas disjuntas
'PATIO BRASIL - DF'  112 linhas desde 20/02/2026 ┘ → é a MESMA unidade, fundir
```

Idem `PIÇARRAS - SC` e `SÃO GONÇALO SHOPPING - RJ`. Sem resolver, a ficha da Pátio Brasil mostraria **3,5 meses** de histórico em vez de 12.

O caso oposto impede resolver ingenuamente por nome normalizado:

```
'AGUAS CLARAS'       1180 linhas, master=DF/GO, inaug 20/03/2023 ┐ datas SOBREPOSTAS,
'AGUAS CLARAS - DF'   601 linhas, master=ULTRA, inaug 19/10/2024 ┘ inaugurações diferentes
                                                    → são DUAS unidades reais
```

**Regra**: fundir dois nomes crus **sse** as faixas de data são disjuntas **E** a `inauguracao` é idêntica. Classifica corretamente os 4 casos existentes (3 fusões, 1 separação).

### 1.4 Demais correções do alicerce

| item | ação |
|---|---|
| `ANDRE DE BARROS - PR` com `inauguracao = 31/12/1969` (sentinela epoch → 677 meses) | gate `1990 <= ano <= ano_ref` → `coorte = "indefinida"` |
| `cancelados` **cai** dentro do mês em 36,7% dos unidade-mês (estornos) | usar sempre `last`, nunca `max` nem soma de diferenças |
| 150 de 2.132 unidade-mês têm **< 20 dias** de dado | marcar `fechado: false` e **excluir do peer set** da coorte |
| `_FAT_MIN_EXEC = 20000.0` é literal financeiro em `app.py:1827` | viola `dimensionamento/config.py:118-124` — migrar para constantes nomeadas |
| `inadimplente` (>100% dos pagantes em 10% dos fechamentos) e `treino_ativo` (>100 em 6 linhas) | **exibir com aviso, proibido em alerta** até validar com a Growth |

### 1.5 Lista de exclusão — corrigida (decidido por Felipe, 2026-08-04)

`_EXEC_EXCLUIR` casa por **chave normalizada**, e isso está **derrubando uma academia real em produção hoje**:

| nome cru | o que é | hoje | correto |
|---|---|---|---|
| `AGUAS CLARAS` (DF/GO, inaug 2023, **2.088 ativos**) | **academia** | ❌ excluída | ✅ **entra** |
| `AGUAS CLARAS - DF` (ULTRA, inaug 2024, 282 ativos, R$ 1,3 mil) | **studio** | ❌ excluída | ❌ excluída |
| `CHACARA STO ANTONIO - SP` | não é academia | ✅ aparece | ❌ **sai** |
| `BARRA FUNDA` | não é academia | ✅ aparece | ❌ **sai** |
| `NATAL - RN`, `BATEL - PR`, `BACACHERI - PR`, `ADMINISTRACAO` | fora da rede comparável | ❌ excluídas | ❌ excluídas |

**A exclusão passa a casar por nome CRU** (ou pelo `id` canônico), nunca por chave normalizada — é a única forma de separar `AGUAS CLARAS` de `AGUAS CLARAS - DF`. Impacto líquido medido em jul/2026: **+1 volta, −2 saem**.

---

## 2. O que o time de campo já faz — e que o produto tem de absorver

Analisei o HTML e o `.xlsx` que eles usam. Isto **é** a especificação.

### 2.1 O quarteto de contexto — o achado mais importante

Na planilha, **toda** métrica aparece com o mesmo quarteto de colunas:

```
MÊS  |  M - 1  |  Ranking N/89  |  % vs Média Rede
```

Eles nunca olham um número sozinho. E a leitura de desempenho não é por cor: o gestor lê *"estou 64% abaixo da média da rede e sou 79º de 89"*. **Esse trio de contexto é o semáforo deles** — e é mais informativo que um chip colorido, porque diz o tamanho e a posição do problema.

**Consequência para o desenho**: cada métrica da carteira e da ficha entrega os quatro valores. O motor de alertas do §4 **soma-se** a isso (eles não têm nada parecido, e é o que transforma a lista em fila de trabalho); não substitui.

### 2.2 As regras de ranking, que hoje só existem na cabeça de quem monta a planilha

Deduzidas numericamente, com validação exata em 89/89 unidades no faturamento:

| métrica | ranqueia por | direção |
|---|---|---|
| faturamento, recorrentes, ativos, visitas, novos alunos | valor | desc (1 = maior) |
| **churn** | **a taxa %**, não a quantidade | **asc** (1 = menor churn) |
| **em cobrança** | **o %**, não a quantidade | **asc** |
| **NPS** | **a nota**, não o volume de pesquisas | desc |
| **pesquisas não tratadas** | quantidade | **asc** (1 = menos pendências) |
| conversão, treinos ativos | % | desc |

Empates recebem a mesma posição (`RANK.EQ`), e o ranking é **segregado por marca** (89 posições `ULT`, 2 posições `ICON`).

**Um defeito a não herdar**: a média da rede deles é `total / 91` e inclui `ADMINISTRACAO` (R$ 218 de faturamento) e as duas `ICON` — o que **deprime artificialmente a média** contra a qual as 89 unidades são medidas. Nossa versão exclui as não-academias (§1.5), o que já corrige isso.

### 2.3 Dimensões e atributos que a API não tem

A aba `DADOS` do Excel **não é base de métricas — é o cadastro** (a dimensão) que a Growth não fornece. Cruzei com a base real:

- **O join fecha em 91 de 99 unidades vivas.** Das 8 órfãs, **6 são exatamente as não-academias que você mandou excluir** — confirmação independente da decisão do §1.5. Sobram dois casos reais a reconciliar: `CEILANDIA QNN32 - DF ` (espaço no fim) e `SAO GONCALO - CENTRO - RJ`.
- **Consultor cobre 100%** das que casam: MARISE 24 · JAILSON 23 · ANDERSON 21 · ISAMARA 18 · GUILHERME 5. A carteira por consultor é viável de imediato.
- **`master` da API e `MASTER FRANQUIA` do cadastro são dimensões DIFERENTES**, não rótulos do mesmo campo (12 células na tabela cruzada contra 7 se fosse 1:1): `ULTRA` da API se espalha por Franqueadora 24 / Dalmo Ribeiro 1 / Jefferson Pinheiro 1. Uma é **agrupamento regional-operacional**, a outra é **o dono**. Ambas úteis, ambas expostas como filtro.

Campos exclusivos do cadastro: `COD UNIDADE`, `CIDADE`, `DPTO` (Operações 86 / Implantação 18, derivado de a inauguração já ter passado), `MASTER FRANQUIA`, `FRANQUEADO`, `CONSULTOR`, `CONSULTOR 2` (só DF/GO), `CLI.OC ROD 01`, `LIFE TIME`, `LTV` (= life time × ticket), `GOLD` (preço do plano), modalidades (piscina/studios/bike/lutas/pilates) e tiers `WELLHUB`/`TOTALPASS`.

### 2.4 O que dá para entregar automático e hoje é colado à mão

| hoje, manual | com a API |
|---|---|
| Ranking e "% vs média" recalculados fora e colados (a aba `ANALISE DIARIA` **não tem uma única fórmula**) | calculados no backend |
| M-1 no mesmo recorte de dias (D1–D21) | o `mtd()` do piloto **já faz exatamente isso** |
| Bloco "Novos alunos diário", 31 colunas coladas | **derivável**: `novos_alunos` é cumulativa diária, basta o `diff` |
| Categoria de faturamento (<150k Crítico … ≥300k Excelente+) | adotar as faixas **deles**, não inventar novas |
| Somar parcelas de agregador na célula (`=35576.92+8008.72`) | a API já traz separado |

**O que NÃO dá para entregar** e precisa decisão: a decomposição de receita em `VENDAS UX + GYMPASS + TOTALPASS − TEM SAÚDE`. A API só tem dois desses quatro (`faturamento` e `faturamento_sem_agregador`). E há uma **quebra de série em set/2025**, quando `TEM SAÚDE` passou a ser deduzido para toda a rede — sem nenhuma marcação no arquivo.

### 2.5 Defeitos do que eles usam hoje (não herdar)

1. `rec_ant` e `ativos_ant` vêm **nulos em 85 de 85 unidades** — desalinhamento de coluna nunca corrigido; os cards mostram "M-1: —" há meses.
2. **Churn subindo 40% aparece com seta verde**: o delta usa a mesma direção para todas as métricas, sem inverter para churn e cobrança.
3. O semáforo é **relativo à média do conjunto filtrado** — se a rede inteira cair, tudo continua verde, e a mesma unidade muda de cor quando se mexe num filtro.
4. **Quatro definições diferentes de "Saúde"** no mesmo arquivo (3, 4, 4 e 5 indicadores; cortes 70/40 num lugar, ≥2/≥0 noutro). Unificar em uma.
5. A escala de cor do bloco diário está **congelada e dessincronizada dos valores** — a planilha mente visualmente hoje.
6. **19 de 104 unidades somem dos indicadores** por falha de join de nome-texto.
7. O "PDF" é `window.print()` num iframe, sem os gráficos.

---

## 3. Arquitetura

### 3.1 Backend — congelar o v1, criar `/api/rede/*`

`/api/executiva/{uf}` **permanece registrada e verde**, mas vira um **adaptador fino** sobre o núcleo novo. Isso entrega o conserto do §1 à tela atual sem esperar a repaginação.

A UF sai do path porque virou filtro entre outros:

| rota | papel |
|---|---|
| `GET /api/rede/filtros` | vocabulário de filtros + **réguas vigentes** + contadores de qualidade |
| `GET /api/rede/carteira` | Nível 1 — `?uf=&master=&coorte=&mes=&ordenar=&severidade=` |
| `GET /api/rede/unidade/{id}` | Nível 2 — série 12m, funil, coorte, recomendações |
| `GET /api/rede/carteira.{csv,xlsx,pdf}` | exports, mesmos query params |
| `GET /api/rede/unidade/{id}.pdf` | ficha em PDF |

**Peça central — `_fechamento_mensal()`**: uma linha por `(unidade_id, competência)` com o último dia **com dado** do mês, vetorizada. Substitui o loop Python por unidade. Medido: **2.132 linhas em 17 ms** para a rede inteira. Carteira, ficha, coorte, alertas e exports derivam todos dela — um único lugar onde a semântica cumulativa/snapshot vive.

**Onde o código mora** (importa para a governança): toda a lógica nasce em `src/motor_expansao/dashboard/` (**Média, loop-safe**) e `web/**` recebe só adaptador fino (**Alta, `aprovado-humano`, nunca loop-safe**). Módulos novos:

```
src/motor_expansao/dashboard/rede_metricas.py     # fechamento mensal, identidade, ticket, NPS
src/motor_expansao/dashboard/rede_diagnostico.py  # réguas, alertas, prioridade, narrativa
src/motor_expansao/dashboard/rede_coorte.py       # coortes, percentil, degradação
src/motor_expansao/dashboard/rede_export.py       # CSV/XLSX/PDF
src/motor_expansao/dashboard/pdf_base.py          # primitivas _UltraPDF compartilhadas
```

**Identificador estável**: verifiquei que o nome cru é único (102 nomes, uma UF e um `master` cada, zero linhas duplicadas), mas colide em 4 casos após normalização. O `id` é um slug ASCII derivado de `(chave_unidade, uf)` com a regra de fusão do §1.3.

**Payload**: linha da carteira ≈ 1,08 KB → **102 unidades ≈ 120 KB** (~25 KB com gzip), sem paginação. Série da ficha em **formato colunar** (`{meses: [...], faturamento: [...]}`), que custa **0,9 KB** contra 2,2 KB em array de objetos.

### 3.2 Frontend — um scroller, mapa fixo ao lado

O padrão é o da `ViabilityScreen`: pilha vertical de cards. Dado `body{overflow:hidden}` (`global.css:31`), **um único scroller** — nada de scroll aninhado:

```
┌ HEADER fixo — Rede Ultra │ UF ▾ │ Consultor ▾ │ Master ▾ │ Coorte ▾ │ Mês ▾ │ busca │ [↓] ┐
├ SCROLLER ▼ ────────────────────────────────────────────────────────────────────────────────┤
│ ┌ KPIs da rede — Faturamento · Ativos · Churn · Receita/recorrente · NPS · Em risco ──────┐ │
│ ┌ Semáforo da rede — barra segmentada + chips que FILTRAM a carteira ─────────────────────┐ │
│ ┌ CARTEIRA (flex 1 1 620px) ──────────────────┐ ┌ coluna dir. 360px, sticky ─────────────┐ │
│ │ ▓ cabeçalho sticky ▓                         │ │ ┌ MAPA (h 340, scrollZoom off) ─────┐ │ │
│ │  ● │Unidade      │Coorte│12m  │Fat.  │Δ│…   │ │ │ │ bolhas coloridas pelo semáforo   │ │ │
│ │  ● │Vicente Pires│12-24m│▁▂▃▅▆│R$412k│▼│    │ │ │ └───────────────────────────────────┘ │ │
│ │  ○ │Pátio Brasil │ 24m+ │▃▄▅▅▆│R$501k│▲│    │ │ │ ┌ Distribuição por coorte ─────────┐ │ │
│ └──────────────────────────────────────────────┘ └────────────────────────────────────────┘ │
│ ┌ Faturamento da rede (12 meses) ─────────┐ ┌ Churn por coorte ──────────────────────────┐ │
│ ┌ Notas metodológicas ────────────────────────────────────────────────────────────────────┐ │
└────────────────────────────────────────────────────────────────────────────────────────────┘
```

Abaixo de ~1010px de largura útil o `flexWrap` derruba o mapa para baixo da carteira, sem media query (não há folha de estilo para componentes — tudo é inline).

**Cada célula de métrica entrega o quarteto do §2.1** — valor, M-1, ranking e % vs média da rede. Na tabela, valor e Δ ficam visíveis e o ranking + % vs média entram no `title` da célula e na ficha; num painel de 8 colunas não cabe tudo em texto, mas o dado tem de estar lá porque é assim que eles lêem.

**Filtros**: UF, **consultor** (a carteira — dimensão principal do time de campo), **master franquia**, coorte de maturidade e competência. Chips de severidade filtram a carteira, como no HTML deles.

**Uma tela a mais que eu não tinha previsto**: o HTML tem "Por Consultor" com **drill-down inline da carteira**, e é assim que o gestor de campo trabalha. Na nossa aba isso não vira tela separada — é o filtro de consultor + um agrupamento opcional da carteira, mantendo uma superfície só.

**Carteira → ficha**: a ficha **substitui o corpo** da aba, com `history.pushState` (Voltar do browser + Esc funcionam) e restauração da posição de rolagem. Não modal (focus trap + scroller aninhado em 768px de altura), não router (evita a dep nova). Os filtros vivem **acima** do switch, então abrir e fechar a ficha **não refaz nenhum request**.

**Componentes.** O projeto **não tem biblioteca de gráficos nem componente de tabela** — tudo é SVG escrito à mão. Novos, com o que reaproveitam:

| componente | onde | deriva de |
|---|---|---|
| `Tabela<T>` genérica, `<table>` real com `aria-sort` e `<th>` sticky | `components/Tabela.tsx` | — (primeira do produto; `<table>` real para colar no Excel preservando colunas) |
| `Sparkline` | `primitives.tsx` | `RampaAlunos` (`ViabilityCharts.tsx:596-714`) |
| `Semaforo` | `primitives.tsx` | `Chip` (`primitives.tsx:18-37`) |
| `BarraMeta`, `BarraSegmentada` | `primitives.tsx` | `ReguaBreakEven` + o split de `ExecutiveScreen.tsx:245` |
| `Delta` **promovido** (hoje é local) | `primitives.tsx` | `ExecutiveScreen.tsx:361-396` |
| `BarrasPeriodo`, `ComparativoCoorte`, `FunilComercial` | `components/exec/ExecCharts.tsx` | `CascataDre` (`ViabilityCharts.tsx:263-552`) |
| `BannerRecomendacao` | `components/exec/` | `Veredito` (`ViabilityCharts.tsx:1233-1364`) |

**Regra para não repetir o erro atual** (`ExecutiveScreen` declara `Kpi`/`Delta`/`Legenda` locais homônimos e divergentes dos de `primitives.tsx`): zero declaração de componente dentro de `screens/`; a tela fica só com estado e composição, meta de **≤ 300 linhas** contra as 506 de hoje. Os três locais são **apagados**, não deixados coexistindo.

**Desacoplar a UF por completo** (decidido por Felipe): a Executiva **nunca** herda a UF do Mapa — nem na primeira montagem. Ela abre com **a rede do Brasil inteiro carregada** e o filtro de UF vive só dentro da aba. `ExecutiveScreen` deixa de receber `uf`/`onUf` (não recebe nem `ufInicial`); `ExecLanding` é deletada. Isso também elimina o efeito colateral atual, em que trocar a UF na Executiva dispara um refetch de `/api/uf/{uf}` no Mapa que pode passar de 15 s.

---

## 4. Diagnóstico — réguas absolutas, não quartis

Testei o corte por quartil no dado real: **76 de 89 unidades acendem algum alerta (85% da rede)**. Vira ruído. O `CLAUDE.md` §2 já dizia: *"quartis são apoio de ranking relativo; para decisão executiva, priorizar régua absoluta"*, e o precedente é `censo_report.py`, com metas absolutas nomeadas (`_META_POP_TOTAL_RAIO`) + helper puro `_cor_por_meta`.

Réguas **recalibradas com as definições oficiais do DAX** (§9) e as exclusões corretas (§1.5), medidas contra jul/2026 fechado, 88 unidades:

| régua | limiar | acende |
|---|---|---|
| churn mensal (**base do mês anterior**, como o DAX) | > 8% | 15 (17%) |
| conversão visita→convertido | < 40% | 14 (16%) |
| NPS | < 40 | 18 (20%) |
| dependência de agregador | > 70% | 6 (7%) |
| **`SALDO_OPERACIONAL` negativo 3 meses fechados seguidos** | `vendas − cancelados` < 0 | 12 (14%) |
| queda de faturamento | ≤ −10% vs média de 3 meses | 14 (16%) |

Três mecanismos empilhados evitam o ruído:

1. **Régua absoluta** em vez de quartil.
2. **Persistência** em vez de foto do mês — o saldo exige 3 meses fechados consecutivos, não um mês ruim.
3. **Severidade em dois níveis** (o mecanismo principal): `alta` se houver um alerta grave **ou** dois médios; `media` com um; `ok` sem nenhum.

Resultado medido: **36 unidades limpas (41%), 31 com um alerta (35%) e 21 com 2+ (24%)** — dentro da banda alvo do teste-guardião. Os motivos saem legíveis: *Berrini-SP → churn; conversão; NPS; dependência de agregador*.

**Meta ≠ alerta.** `NPS_IDEAL = 60` é a **meta oficial** da rede, e 38% das unidades estão abaixo dela — número certo para uma linha de referência no gráfico e semáforo de meta, e errado para uma fila de visita. A meta de 60 é **exibida**; o alerta dispara em 40.

**Adotar a categorização que eles já usam**, em vez de inventar outra: faturamento em `Crítico < 150k · Regular < 200k · Bom < 250k · Excelente < 300k · Excelente+ ≥ 300k`. É a linguagem do time e já está nos dois artefatos. (Registrar a ressalva: são faixas absolutas aplicadas indistintamente a unidade de bairro e a flagship, sem normalizar por porte ou idade — daí 31 de 104 caírem em "Crítico". O benchmark por coorte do §5 é o contrapeso honesto a isso.)

**Uma definição de Saúde, não quatro.** O HTML deles tem quatro fórmulas diferentes convivendo (§2.5). A nossa é uma só: a `severidade` do motor de diagnóstico, calculada no backend, servida no payload e impressa no PDF — um número, uma régua, um lugar.

**O alerta complementa o quarteto, não o substitui.** Eles hoje só têm posição relativa; nós acrescentamos a leitura absoluta ("churn de 8,4%, acima da régua de 8%") e a persistência ("3 meses seguidos"). As duas leituras convivem na mesma linha: o ranking diz *onde você está entre pares*, o alerta diz *se isso é aceitável*.

**Fora das réguas de propósito**: `inadimplente` e `treino_ativo` (§1.4) e `ticket` (só faz sentido comparado por coorte — uma unidade de 3 meses com ticket abaixo da rede é normal).

**Como o Felipe recalibra**: um único bloco `_REGUA_*` no topo de `rede_diagnostico.py`, com o p10/p50/p90 medido em comentário ao lado. As réguas vigentes são **servidas** em `/api/rede/filtros.reguas` e impressas no rodapé do PDF — impossível a tela mostrar uma régua e o motor aplicar outra. E um teste-guardião (`test_banda_alvo_da_fila_acionavel`) **falha o CI** se a fatia `alta` sair da banda 5–25%, avisando antes de a tela virar ruído.

---

## 5. Benchmark por coorte de maturidade

A **DEC-014** já decidiu isto: o eixo territorial de retenção deu **NO-GO**, e a parte previsível é a **maturidade (tempo de operação), não a geografia**. Comparar contra pares da mesma coorte de inauguração é o defensável.

Coortes por semântica operacional (não por quantil), com o n medido: `0_5` (9) · `6_11` (16) · `12_23` (26) · `24_47` (25) · `48_mais` (13) · `indefinida` (1).

Decisões que evitam armadilhas:

- A coorte é sempre calculada sobre a **rede toda**, jamais sobre o recorte filtrado. Filtrar "master = PR" (5 unidades) e comparar contra 2 pares seria ruído — e reintroduziria geografia pela porta dos fundos.
- **Peer set** exclui mês aberto, mês com < 25 dias de dado, unidades abaixo do piso de faturamento e coorte indefinida.
- **Escada de degradação explícita**: coorte própria (n≥8) → coorte vizinha → rede toda → sem dado. O campo `degradacao` é **servido no payload e impresso no PDF** — é a lição literal do `fonte_base_calibracao` (`app.py:1782`), onde a degradação silenciosa mudava o significado dos percentis sem sinal nenhum na tela.
- **Benchmark por m² fica fora**: só 54 das 102 unidades têm `metragem`. Meia rede é degradação demais para um dashboard que promete "a carteira toda".

---

## 6. Exports

| formato | como | por quê |
|---|---|---|
| CSV | `csv.writer` sobre `StringIO`, `sep=";"`, `utf-8-sig` | **Não** `df.to_csv` — o AST guardrail reprova o CI |
| XLSX | `openpyxl.Workbook()` → `BytesIO` | padrão de `/api/simulador/xlsx` |
| PDF | `pdf_base.py` novo + `fpdf2`, 16:9 | reusa as primitivas dos relatórios existentes |

**Sobre a duplicação de `_UltraPDF`**: ela é byte-idêntica entre `censo_report.py:360` e `relatorio_municipal.py:1576`. Extrair para `pdf_base.py` e fazer **só o módulo novo** importar de lá — **não** reapontar os dois legados neste epic (são geradores em produção com testes de regressão de bytes; refatorá-los é risco alto que não entrega nada ao usuário). Um teste `test_ultra_pdf_config_identica` impede a duplicação virar triplicação, e a de-duplicação vira bloco de follow-up.

**Armadilha do latin-1** (o `fpdf2` troca por `?` em silêncio): `≥`, `≤`, `—`, `•`, `→`, `…`, `−` (U+2212) e aspas curvas **falham**. O mesmo texto de alerta vai para o JSON (UTF-8, tudo passa) **e** para o PDF — então toda string gerada por `rede_diagnostico.py` nasce com pontuação ASCII, imposto por teste que varre a matriz de alertas e tenta `encode("latin-1", errors="strict")`.

**Estender o guardrail AST**: hoje ele parseia só `web/server/app.py`. Como a lógica nova vai para `src/`, um teste novo aplica a mesma análise a `rede_export.py` e `rede_diagnostico.py` — senão mover código para `src/` é mover código para fora do guardrail.

---

## 7. Faseamento

Cada bloco entrega valor sozinho. **`web/**` é classe GOVERNANÇA no `loop_guard.py`** → exige `aprovado-humano` e nunca é loop-safe; concentrar o volume de código em `src/` mantém a maior parte do trabalho no loop e reduz cada gate humano a revisar ~100 linhas de adaptador.

| bloco | escopo | `web/**`? | criticidade · autonomia |
|---|---|---|---|
| **BLK-EXEC-00** | **Cadastro de unidades (leitura)** — `cadastro_unidades.json` com as dimensões que a API não tem (consultor, master franquia, franqueado, dpto, cidade, cod, modalidades, tiers, gold, life time, LTV), semeado da aba `DADOS`, com reconciliação de chave e relatório de órfãs. **Bloqueia o filtro de consultor** | não | Média · **loop-safe** |
| **BLK-EXEC-00b** | **Cadastro editável (escrita)** — volume `:rw` no compose, repositório com interface estreita, `PUT` com lista branca de campos, concorrência otimista por versão, log de auditoria com `Remote-User`, e os ajustes de guardrail do §11.3. **Toca infra de produção** | sim | **Alta** · `aprovado-humano` |
| **BLK-EXEC-01** | Núcleo semântico: `_fechamento_mensal()` vetorizado, resolvedor de identidade (§1.3), **lista de exclusão por nome cru (§1.5)**, `nps_valido`, ticket rolling-30, gate de inauguração, migração do literal financeiro | não | Média · **loop-safe** |
| **BLK-EXEC-01b** | **Contexto comparativo**: ranking por métrica com a tabela de direção/base do §2.2, `% vs média da rede` e a série diária de novos alunos (derivada do cumulativo) | não | Média · **loop-safe** |
| **BLK-EXEC-02** | **Conserto do alicerce na tela atual** — `executiva()` vira adaptador; ticket e NPS corretos, loop por unidade morto. Contrato v1 intacto | sim | Alta · `aprovado-humano` |
| **BLK-EXEC-03** | Motor de diagnóstico puro: réguas, `Alerta`/`Diagnostico`, narrativa ASCII-safe, `prioridade` | não | Média · **loop-safe** |
| **BLK-EXEC-04** | Benchmark por coorte puro: percentil, escada de degradação, peer set | não | Média · **loop-safe** |
| **BLK-EXEC-05** | Fundação frontend pura: `lib/exec.ts`, `lib/sparkline.ts`, tipos v2, métodos em `api.ts`. **Zero mudança visual** | sim | Média · `aprovado-humano` |
| **BLK-EXEC-06** | Nível 1 backend: `/api/rede/filtros` + `/api/rede/carteira`, incluindo **SSS (base comparável ano a ano, §8)** ao lado do M-1 | sim | Alta · `aprovado-humano` |
| **BLK-EXEC-07** | Nível 1 frontend: scroller único, `Tabela`, mapa vira card, filtros, semáforo, UF desacoplada, `ExecLanding` deletada | sim | Alta · `aprovado-humano` + **`[GATE VISUAL — Felipe]`** |
| **BLK-EXEC-08** | Nível 2 backend: `/api/rede/unidade/{id}` — série colunar, funil, coorte, recomendações | sim | Alta · `aprovado-humano` |
| **BLK-EXEC-09** | Nível 2 frontend: navegação, ficha, gráficos, banner de recomendação | sim | Alta · `aprovado-humano` + **`[GATE VISUAL — Felipe]`** |
| **BLK-EXEC-10** | Export tabular (CSV/XLSX) — o time de campo ganha a planilha antes de qualquer PDF | sim | Alta · `aprovado-humano` |
| **BLK-EXEC-11** | Export PDF: `pdf_base.py` + carteira + ficha | sim | Alta · `aprovado-humano` |
| **BLK-EXEC-12** | Follow-up: de-duplicar `_UltraPDF` nos dois legados, com byte-comparação antes/depois | não | Média · **loop-safe** |

**Ordem**: 01 → (03 ∥ 04 ∥ 05) → 06 → 07 → 08 → 09 → (10 ∥ 11) → 12.
**02 é paralelo e independente a partir de 01** — de propósito: conserta um número **76% errado em produção** sem esperar a repaginação. **Se só uma coisa for feita esta semana, é 01 + 02.**

**Governança**: mudança de escopo de superfície tem precedente de exigir **DEC** (foi assim na DEC-020 e na DEC-022, ambas Estratégicas e READ-ONLY sobre o M1). Recomendo abrir uma **DEC-023** registrando a virada de produto da aba antes do BLK-EXEC-06, e criar os blocos em `tasks/backlog.md` no formato da casa (tabela Criticidade/Esteira/Status/Autonomia + Contexto/Objetivo/Guardrail/Aceite).

---

## 8. Verificação

**Testes por bloco** (padrão herdado: contrato + degradação sem parquet + AST de `test_piloto_web_endpoints.py`; lógica pura parametrizada de `test_exec_coordenadas.py`):

- **01** — `test_ticket_usa_faturamento_sem_agregador_rolling30` (regressão do R$ 20,28 vs R$ 163,67); `test_ticket_medio_da_api_nao_e_usado` (trava o conserto errado); `test_nps_999_vira_none` **e** `test_nps_negativo_e_preservado` (impede alguém "consertar" filtrando `v > 0`); `test_identidade_funde_serie_partida` e `test_identidade_nao_funde_unidades_distintas` (os dois lados da regra); `test_fechamento_usa_last_nao_max`; teto de tempo que impede a volta do loop por unidade.
- **02** — `test_executiva_sem_growth_levanta_404` continua passando; `test_executiva_contrato_v1_preservado` (todas as chaves de `ExecutivaPayload`); `json.dumps(allow_nan=False)`.
- **03** — matriz **régua × (abaixo, na régua, acima)**; `test_metricas_a_validar_nunca_alertam`; **`test_banda_alvo_da_fila_acionavel`**; `test_textos_sobrevivem_a_latin1`; `test_diagnosticar_e_pura`.
- **04** — `test_escada_de_degradacao`; `test_degradacao_e_sempre_servida`; `test_coorte_ignora_filtro_da_tela`; **`test_benchmark_nao_usa_geografia`** (AST: nenhuma referência a `lat`/`lng`/`uf`/`cidade` — DEC-014 em código).
- **06/08** — rotas novas em `test_todas_as_rotas_registradas`; `test_carteira_e_ficha_concordam` (análogo de `test_tela_e_pdf_leem_os_mesmos_kpis` — o defeito mais caro deste projeto é a mesma unidade com dois números); `test_payload_da_carteira_cabe_no_orcamento` (< 200 KB).
- **05/07/09 (frontend)** — não há teste de componente (sem `@testing-library/react`). Seguir o precedente de `lib/select-filter.ts`, **extraído de `Select.tsx` só para ser testável sem DOM**: `ordenarUnidades` (com nulos por último **nas duas direções** — o `?? -Infinity` de hoje só funciona em `desc`), `filtrarUnidades`, `lerDelta`, `formatarMetrica` (blinda o pega-ratão do churn em percentual aqui vs fração na Viabilidade), `caminhoSparkline` (série toda igual → sem divisão por zero). Propor RTL no bloco do `Tabela`, único com contrato interativo que vale travar.
- **10/11** — `test_csv_usa_ponto_e_virgula_e_utf8_sig`; `test_export_nao_escreve_em_disco`; `test_modulos_de_export_sao_read_only_por_ast`; `test_pdf_sem_caractere_fora_de_latin1`.

**Verificação end-to-end**, seguindo o que já validou o trabalho anterior nesta aba:

1. Local: `pytest tests/unit tests/contracts -q` e `cd web && npm run test && npm run build`.
2. Contra os dados reais, sem tocar o servidor: `scp` dos parquets de produção e execução do backend novo apontando para a cópia local — foi assim que medi 61% → 93% de cobertura na correção dos pins.
3. Em produção, após deploy manual por digest: `docker exec -i motor_expansao_web python -` com script via stdin, comparando `carteira` × `ficha` × CSV para a mesma unidade.
4. Gate visual com o Felipe antes de 07 e 09.

---

## 9. O PowerBI como fonte de vocabulário canônico

`Dashboard - Análise Diária - MVP.pbix` consome **a mesma base** (tabela `D_HISTORICO_DASH`, antes via view SQL, hoje via API). Extraí as **158 medidas** referenciadas nos visuais. O DAX em si está no `DataModel` comprimido (XPress9) e não é legível sem ferramenta, mas os nomes já resolvem duas coisas.

**Vocabulário a adotar na aba nova** — o time de campo já fala esta língua:

| termo do PowerBI | o que este plano chamava |
|---|---|
| **Recorrentes** | pagantes (balcão) |
| **Agregadores** | Gympass + Totalpass |
| `SALDO_OPERACIONAL` | saldo de alunos |
| `RECEITA_PERDIDA` | churn em R$ |
| `NPS_IDEAL` | **existe meta de NPS definida** — usar em vez da minha régua arbitrária |
| `Cor Faturamento M-1`, `Cor Churn M-1`, … | já há semaforização por variação vs M-1 |

**Uma métrica que eu não tinha previsto e que deveria entrar**: a família **`SSS - *` (Same Store Sales)** — `SSS - Faturamento Atual / AA / Var%`, idem Recorrentes, Agregadores e Ativos Totais, mais `SSS - Qtd Unidades`. É comparação **ano contra ano em base comparável** (só unidades presentes nos dois períodos), que é a leitura correta de crescimento numa rede que abriu 33 unidades em 2025. O plano previa apenas M-1; **acrescentar SSS ao Nível 1** e usar a lógica de "base comparável" que o `soma_metric` atual já esboça.

Outros achados: existe `COD_UNIDADE` no modelo (resolveria o ID estável de forma limpa) mas **ele não vem nas 29 colunas da API** — vale pedir à Growth; e há mix de planos (`VD_FREEPASS`, `VD_GOLD`, `VD_GOLDPRO`, `VD_ULTRA360`) e um bloco de conversão de agregadores que não existem no parquet atual.

### 9.1 As fórmulas oficiais (Felipe, 2026-08-04) e o que cada uma muda

```dax
CHURN_DIA         = [CANCELADOS_DIA] / [REC_MES_ANTERIOR]
SALDO_OPERACIONAL = [VENDAS_DIA] - [CANCELADOS_DIA]
NPS_IDEAL         = 60
TICKET_MEDIO      = DIVIDE( SUM(FT_RELATORIO_VENDAS[VALOR_REAL]),
                            COUNTROWS(FT_RELATORIO_VENDAS) )   -- filtrado a VALOR_REAL > 19,90
AgrTickMedioTotal = ([AgrTickMedioGympass] + [AgrTickMedioTotalpass]) / 2
```

| fórmula | o que o plano fazia | impacto medido |
|---|---|---|
| **`SALDO_OPERACIONAL = vendas − cancelados`** | eu usava `novos_alunos − cancelados` | **a correção mais relevante**: `vendas > novos_alunos` em 74% dos casos e **23 unidades trocam de sinal**. Negativos caem de 40 para 23. Adotar a oficial |
| **Churn com denominador `REC_MES_ANTERIOR`** | denominador era a base do dia | conceitualmente certo (saídas ÷ base inicial), custo zero: diferença mediana de **−0,03 pp**, só 8 de 86 unidades passam de 0,5 pp. Adotar por paridade com o PowerBI |
| **`NPS_IDEAL = 60`** | régua inventada | vira **meta exibida**, não alerta (§4) |
| **`TICKET_MEDIO`** | eu ia renomear o nosso de "ticket" | **irreproduzível** — depende de `FT_RELATORIO_VENDAS[VALOR_REAL]`, venda individual que a API não expõe. Nosso número vira "Receita por recorrente" (§1.1) |
| **`AgrTickMedioTotal`** = média **simples** das duas | — | mediana idêntica à ponderada (−R$ 0,02), mas diverge até R$ 72 em casos extremos. Adotar a simples por paridade, com nota de que é média não ponderada |

## 10. Decisões — resolvidas e pendentes

| # | questão | status |
|---|---|---|
| **D1** | Exclusões | ✅ **resolvida** — `AGUAS CLARAS - DF` é studio e sai; a academia `AGUAS CLARAS` entra; somam-se `CHACARA STO ANTONIO - SP` e `BARRA FUNDA`. Casar por nome cru (§1.5) |
| **D3** | Réguas de alerta | ✅ **resolvida** — usar as do §3 como ponto de partida; Felipe calibra com o time de campo em uso. **Reforça o requisito**: régua num único bloco, servida no payload e impressa no PDF, com o teste-guardião de banda |
| **D4** | Herança de UF | ✅ **resolvida** — a Executiva **nunca** herda; abre com o Brasil todo e filtra internamente |
| **D2a** | `ticket_medio` | ✅ **resolvida** (§9.1) — `TICKET_MEDIO` é ticket **da venda**, de tabela que a API não expõe. Nosso número passa a se chamar **"Receita por recorrente"**, e churn e saldo adotam as definições oficiais |
| **D2b** | `inadimplente` | ⏳ **pendente** — segue sem denominador conhecido (>100% dos pagantes em 10% dos fechamentos). Existe `TAXA_COBRANC_REDE` no PowerBI, cuja fórmula não veio. Permanece **fora de qualquer alerta**, exibido com aviso |
| **D5** | Vale pedir à Growth `COD_UNIDADE` e a venda individual (`VALOR_REAL`)? | ⏳ **pendente** — o primeiro daria o ID estável de graça; o segundo permitiria reproduzir o `TICKET_MEDIO` oficial e encerrar a divergência de vocabulário |
| **D6** | Cadastro de unidades | ✅ **resolvida** — semear com a aba `DADOS` e **permitir atribuir consultor / master franqueado pela própria aba** para quem ainda não tem. PostgreSQL com usuários e permissões fica para depois; o desenho do §11 já prepara a migração |
| **D7** | Decomposição de receita | ✅ **resolvida** — **não reproduzir**. Basta a proporção recorrentes × agregadores, que a API já dá. Isso remove a dependência de `VENDAS UX`/`TEM SAÚDE` e a quebra de série de set/2025 do escopo. **Consequência a comunicar**: o faturamento da aba **não vai bater** com o total da planilha deles, porque lá o `TEM SAÚDE` é deduzido |

## 11. Cadastro editável — a primeira escrita do piloto

Decisão D6: o cadastro é **semeado da aba `DADOS`** e passa a ser **editável pela própria aba**, para atribuir consultor e master franqueado a quem ainda não tem. Isso é uma mudança de natureza, e vale explicitar por quê.

### 11.1 O que isso quebra

**O backend do piloto é read-only por CI.** `test_backend_read_only_por_ast` parseia o `app.py` e falha se aparecer `to_parquet`/`to_csv`/`to_excel`/`unlink`/`rmtree`; `test_leituras_nao_mutam_artefatos` tira snapshot do filesystem e prova que nada é escrito fora de `cache/`. E **todos os volumes do container `web` são `:ro`**.

Esse guardrail existe para proteger **artefatos do M1**. Um cadastro operacional novo não é artefato do M1 — mas a regra, como está escrita, não distingue. A solução não é afrouxar o teste; é **separar fisicamente** o que pode ser escrito.

### 11.2 Desenho

1. **Diretório próprio, fora do `MOTOR_DATA_DIR`**: `/opt/motor-expansao/cadastro` montado `:rw` no compose (todos os demais seguem `:ro`). Nenhum artefato M1 fica sob um mount de escrita.
2. **JSON, não parquet** — `cadastro_unidades.json`. Some a tentação de `to_parquet` e o AST guardrail continua íntegro sem exceção nenhuma.
3. **Escrita atômica**: grava `.tmp` e `os.replace()` — que está deliberadamente **fora** da lista de proibidos (o comentário do teste diz que `replace`/`move` ficam de fora porque `.replace(` é pandas/str legítimo).
4. **Concorrência otimista**: o payload carrega uma `versao`; o `PUT` só aplica se a versão do cliente bater com a do disco, senão devolve `409` e a tela recarrega. Sem banco, é isso que evita dois consultores se sobrescrevendo.
5. **Auditoria de graça**: o Caddy **já repassa `Remote-User`, `Remote-Groups` e `Remote-Email`** ao piloto (confirmado no `Caddyfile`, bloco `piloto.ultra-expansao.tech`). Cada edição grava uma linha em `cadastro_log.jsonl` com quem, quando, unidade, campo, valor antigo → novo. Append-only.
6. **Repositório com interface estreita** — `ler_cadastro()`, `atribuir(unidade_id, campo, valor, autor)` — para que a migração para PostgreSQL troque **uma** implementação, não o código espalhado. É o que o Felipe já sinalizou como destino.

### 11.3 Ajustes de guardrail (explícitos, não silenciosos)

- `test_leituras_nao_mutam_artefatos` ganha `CADASTRO_DIR` na lista de exceções, ao lado de `cache/` — **e um teste novo prova que a escrita acontece SÓ ali**, nunca sob `DATA_DIR`.
- O AST guardrail fica **inalterado**: nada de `to_*` é introduzido.
- Um teste prova que o `PUT` **rejeita** campo fora da lista branca (só `consultor`, `consultor_2`, `master_franquia`) — o cadastro não vira porta de escrita para qualquer coisa.

### 11.4 Custo de infra

Mudar o `docker-compose.prod.yml` para adicionar um volume `:rw` é alteração de **infra de produção**: exige deploy manual por digest e cai no guardrail do §6 do `CLAUDE.md` (comando a comando). É o único item deste plano que toca o servidor além do deploy normal da imagem.

---

## 12. Riscos

1. **O conserto do ticket muda um número visível em produção há semanas** — SP salta de ~R$ 20 para ~R$ 164 (8×). Alguém vai achar que quebrou. Mitigação: BLK-EXEC-02 sai com o rótulo novo **e** nota de release explícita.
2. **As réguas vão desregular quando calibradas contra produção** (medi contra jul/2026; a rede cresce). O `test_banda_alvo` pega no CI, e o parâmetro "2 médios = 1 alto" reajusta a fila sem tocar em nenhum limiar.
3. **Densidade visual** — 102 linhas × 8 colunas em tema escuro vira parede cinza. Mitigações: `.num` com `tabular-nums` (já existe), **uma só cor de destaque por linha** (o semáforo), ordenação default por prioridade, máximo 8 colunas visíveis.
4. **deck.gl dentro de um scroller** — `scrollZoom:false` obrigatório, senão a roda do mouse dá zoom no mapa em vez de rolar a página; e o mapa **desmonta** (não `display:none`) quando a ficha abre, para não manter contexto WebGL ocioso.
5. **5 dos 12 blocos tocam `web/**`** → 5 gates humanos de merge. É o custo da governança da DEC-022, mitigado por manter o volume de código em `src/`.
6. **`vendas > convertidos`** em parte da base — o funil não fecha. Servir com texto honesto ("há venda sem visita registrada"), nunca clampar em 100%: clampar esconde um problema de coleta.
