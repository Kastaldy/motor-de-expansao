# BLK-REV-09 — Passagem heurística de UX sobre o app RENDERIZADO

> **Status: INSUMO PRONTO, bloco NÃO fechado.** Este documento adianta ~2/3 do BLK-REV-09.
> Falta a parte que exige input humano (§6). Ler antes de rodar `/run-cycle BLK-REV-09`.
>
> Data da passagem: **2026-07-13** | Executor: Claude (sessão interativa)
> Commit do app avaliado: `e4ec53c` (main, após BLK-RELPON-05 / BLK-PERF-01d / BLK-SEC-05)
> READ-ONLY sobre o M1: nenhum score, peso, carteira ou artefato oficial foi tocado.

---

## 1. Por que este registro existe

O BLK-REV-09 pede: heuristic evaluation (Nielsen), inventário de poluição visual / densidade / jargão,
**jobs-to-be-done por persona** e uma matriz de problemas priorizados por **severidade × esforço**.

A parte que **não depende de input humano** — percorrer o app renderizado e catalogar as violações com
evidência visual — foi executada e está aqui. A parte que **depende de você** (personas / JTBD) está
declarada em aberto na §6, **de propósito**: inventar personas produziria ficção plausível, e o
BLK-REV-10 desenha wireframes *por persona* em cima disso, e o BLK-REV-12 herda a severidade numa DEC
estratégica. Ficção não fica contida — ela se propaga.

## 2. Método

- App subido localmente (`streamlit run streamlit_app.py`, porta 8501) no commit acima.
- Navegação e captura via **Playwright/Chromium** (viewport 1600x1000), percorrendo as 5 abas reais:
  `Mapa`, `Executivo`, `Expansão de Domínio`, `Carteira e Plano`, `Viabilidade`.
- Medições de layout via JS no DOM (posição do mapa, contagem de expanders/captions).
- Script de reprodução: **`scripts/rev09_capturar_telas.py`** (versionado junto).
- Evidência visual: **`data/reports/rev09_telas/`** (5 JPGs).

**Acaso relevante:** o seletor caiu em **AC (Acre)** — UF onde a Ultra **não opera** e a densidade é baixa.
Isso expôs o comportamento do app em condições que ninguém testa (rede vazia, hexes abaixo do corte de
5k hab). Vários dos achados mais graves **só aparecem nesse cenário** — recomendo manter AC como caso de
teste permanente de UX.

## 3. Achados (severidade Nielsen 0–4)

### Severidade 4 — catastrófico

**#1 — "Oportunidade" significa coisas diferentes em abas diferentes.**
Mesmo recorte (AC, 29.004 hexágonos), sem mudar filtro:
- aba **Executivo**: `Oportunidades viáveis: 1.588`
- aba **Carteira**: `Oportunidades no recorte: 6`

Diferença de **264×** para o mesmo substantivo e o mesmo filtro, sem nenhuma tela explicando que são
universos distintos. A reação natural do usuário não é "são métricas diferentes", é *"o sistema está
errado"* — o que contamina a confiança em todos os outros números.
`[H4 consistência + H2 mundo real]` · evidência: `executivo_cards_identicos.jpg`, `carteira_coluna_join.jpg`

**#2 — Os cards "Onde expandir" e "Onde evitar expansão" mostram TEXTO IDÊNTICO.**
Ambos exibem literalmente `AC: 1.588 viáveis | score médio 41.95`. Dois cards que respondem perguntas
**opostas**, na aba mais visível para quem decide, dizem a mesma coisa. É defeito de nível bug.
`[H2]` · evidência: `executivo_cards_identicos.jpg` · código: `pages.py:1016-1023` (`render_answer_card`)

**#3 — O mapa não enquadra a UF selecionada.**
Selecionando AC, o mapa abre em **escala continental** (Peru, Bolívia, Paraguai, Chile, Argentina) com o
Acre como uma mancha **cinza** (quase todos os hexes caem no corte "<5k hab" → `_DISCARDED_FILL`). O
usuário escolhe um estado e vê um mapa aparentemente vazio de um continente. Não há auto-fit ao recorte.
`[H1 visibilidade do estado do sistema]` · evidência: `mapa_legenda_40_chips.jpg`

### Severidade 3 — grave

**#4 — O mapa está abaixo da dobra.** Medido no DOM: o canvas começa a **1.025 px do topo = 1,02 telas**
de rolagem (viewport 1000 px). O produto é o mapa e ele não aparece na primeira tela — antes vêm hero,
filtros globais, seletor de abas, título, 2 captions e 2 expanders. Na aba Mapa contei **10 expanders** e
**15 captions**. `[H8 minimalismo]` · evidência: `mapa_acima_da_dobra.jpg`

**#5 — A legenda é opcional e, aberta, vira poluição.** Está **colapsada por padrão** (a chave de leitura
do mapa é um clique escondido) e, ao abrir, despeja **~40 chips de marcas** de concorrentes, empurrando o
mapa ainda mais para baixo. `[H6 reconhecimento vs memorização + H8]` · evidência: `mapa_legenda_40_chips.jpg`

**#6 — Instrução falsa na tela.** O caption diz *"selecione um município **no filtro lateral**"* — **não
existe filtro lateral**. Não há `st.sidebar`; o BLK-UI-07 moveu todos os filtros para o corpo. O texto de
ajuda aponta para uma UI que não existe mais. `[H2 + H10]`

**#7 — Estado normal apresentado como erro.** Em AC: *"Dados de unidades Ultra não disponíveis ou sem
unidades no recorte selecionado. **Verifique `data/ultra/Ultra.csv`**."* A Ultra simplesmente não opera no
Acre — estado **esperado**. A mensagem funde "não há unidades aqui" com "o arquivo está quebrado", e manda
o usuário conferir um caminho de arquivo que ele não pode consertar. `[H9 mensagens de erro]`

**#8 — Guardrails internos vazando para a tela do usuário.** *"As camadas visuais não alteram score,
ranking, carteira nem artefatos do M1"*; *"Não altera M1, carteira, plano ou artefatos oficiais"*;
*"Proveniência dos outputs (read-only)"*. Isso é a **§5 do CLAUDE.md** — regra escrita para
DESENVOLVEDORES — impressa no produto. `[H2 + H8]` · evidência: `viabilidade_guardrail_na_ui.jpg`

**#9 — Nomes internos exibidos como dados de negócio.** Coluna literalmente chamada **"Join"** (valor `B`);
`Modo Hex = granular_censitario` (enum cru, snake_case); aviso citando `populacao_corte_hex < 5.000`;
`Hex ID = 878b5131efffff` como identificador. `[H2]` · evidência: `carteira_coluna_join.jpg`

### Severidade 2 — menor

**#10 — O hero promete o que a UI não entrega.** As 3 pills anunciam *"Onde expandir (M1)"*, *"Qual bairro
(Censitário)"*, *"Fila operacional (Híbrido)"* — mas o seletor "Modo de cor" **esconde M1 e Híbrido**
(`MAPA_COLOR_MODES_OCULTOS`). O usuário procura o que foi prometido e não acha. `[H4]`

**#11 — Jargão sem definição no ponto de uso:** *Overlays, SAM Fitness, Oferta Residual, Quartil Residual,
Rank Intraurbano, Âncoras de domínio, fallback municipal/M1, camada granular*. Nenhum tem tooltip. Para o
"leigo" da dor #5, a tela é opaca. `[H2 + H10]`

**#12 — Dois campos de coordenada simultâneos** na aba Viabilidade: a busca global (topo) e "Ponto do
imóvel". Mesmo propósito aparente, dois lugares. `[H4]`

### Severidade 1 — cosmético

**#13** `"1 UFs"` (plural incorreto). **#14** `"Choose options"` — placeholder padrão do Streamlit em
inglês, convivendo com "Selecione municípios". **#15** Precisão inconsistente na mesma tela: *Score médio
M1 **42.0*** vs *score médio **41.95***.

### Achados adicionais (leitura de código, mesma sessão)

**#16 — A cor não distingue o que está sendo medido.** Os 4 modos quantitativos (M1, Censitário, Híbrido,
Residual) usam a **mesma rampa** de 10 faixas vermelho→verde (`utils.py:37`, `score_band_to_color`). Só o
rótulo da legenda muda — e a legenda está colapsada (#5). Um print do mapa é ambíguo: não dá para saber
qual score está pintado.

**#17 — Residual é volume, mas está codificado como taxa.** Choropleth comunica taxa/intensidade; magnitude
pede símbolo proporcional. O número que o operador decide (`oferta_efetiva_disponivel`, em **alunos**) só
aparece no tooltip/tabela. Sugestão: bivariado (cor = score, **tamanho = alunos**) — o padrão já existe em
`components.py:873` (bolha por `sqrt(contagem)` no cluster de concorrentes).

**#18 — Tooltip gasta 1 das 6 linhas repetindo.** No modo censitário, a linha 2 (score do modo ativo) e a
linha 3 ("Score Censitário") mostram o mesmo número (`components.py:520`, reconhecido no código).

**#19 — Dois cinzas, dois significados, um sem legenda.** `[150,150,170]` = descartado por pop <5k;
`[110,116,140]` = score ausente (NaN). Perceptualmente próximos, semanticamente opostos. Só o primeiro tem
entrada de legenda; o NaN não tem nenhuma. E a precedência faz o corte de 5k **sobrescrever** a cor de
score (um hex de score alto pode renderizar cinza).

## 4. Matriz severidade × esforço

| | **Esforço baixo** | **Esforço médio** | **Esforço alto** |
|---|---|---|---|
| **Sev. 4** | #2 cards idênticos | #1 desambiguar "oportunidade" · #3 auto-fit do mapa na UF | — |
| **Sev. 3** | #6 instrução falsa · #7 msg de erro · #8 guardrail na UI · #5 legenda visível por padrão | #9 nomes internos · #4 mapa acima da dobra | — |
| **Sev. 2** | #10 hero · #12 coordenada dupla | #11 glossário no ponto de uso | — |
| **Sev. 1** | #13 #14 #15 | — | — |
| **(código)** | #18 dedup do tooltip · #19 legenda do NaN | #16 cor por modo | #17 bivariado no residual |

**Quadrante que importa: superior-esquerdo.** Os achados **#2, #5, #6, #7, #8** são severidade 3–4 com
esforço **baixo** — texto, um `expanded=True` e uma correção de card. São horas, não semanas.

## 5. Conclusão que afeta o BLK-REV-12

**Nada do que foi encontrado é culpa do Streamlit.** Cards idênticos, coluna "Join", mapa que não enquadra
a seleção, guardrail de desenvolvedor na tela, "oportunidade" com dois significados — **tudo isso
reapareceria igual numa SPA**. Isso é dívida de **produto**, não de **stack**.

Consequência direta para a decisão *rebuild vs refactor* (BLK-REV-12): **um rebuild não conserta nenhum
destes 19 itens de graça.** Se a decisão for rebuild, estes achados precisam ser tratados como requisito
explícito do novo app — senão são reconstruídos fielmente.

## 6. O QUE FALTA (só você pode fechar) — bloqueia o REV-10

O bloco pede **jobs-to-be-done por persona**. Isso não sai do código. Perguntas a responder:

1. **Quem de fato abre o dashboard hoje?** (Felipe? Vini? Juan? operações?) Com que frequência?
2. **Quem é concretamente o "leigo" da dor #5** (Felipe, 2026-07-08: *"app poluído e pouco usual para
   leigos"*)? Franqueado? Regional? Comitê de expansão? Consultor externo? **A resposta muda o redesign
   inteiro.**
3. **Qual pergunta cada persona chega querendo responder**, e **o que precisa levar embora** (um município?
   um imóvel? um PDF para reunião?).
4. **Um episódio real de alguém travando no app** — vale mais que dez heurísticas.

Com isso, a coluna de *severidade* da §4 deixa de ser a leitura do avaliador e passa a ser a do usuário
real, e o REV-10 ganha base para os wireframes por persona.

## 7. Como reproduzir

```bash
# 1. subir o app
PYTHONPATH=src python -m streamlit run streamlit_app.py --server.port 8501 --server.headless true

# 2. capturar as telas (playwright ja esta no extra [scraping])
python scripts/rev09_capturar_telas.py <dir_de_saida>
```

O script seleciona a **primeira UF** da lista (= AC) de propósito, percorre as 5 abas, mede a posição do
mapa no DOM e captura as telas. Para reavaliar depois de mudanças, rodar de novo e comparar.

## 8. Referências

- Bloco: `tasks/backlog.md` → **BLK-REV-09**
- Épico: BLK-REV (dores de Felipe, 2026-07-08); sucessores **REV-10** (arquitetura de informação),
  **REV-11** (design system), **REV-12** (síntese + DEC rebuild vs refactor)
- Guardrail: CLAUDE.md §5 (visualização não recalcula M1) — respeitado integralmente
- Evidência: `data/reports/rev09_telas/`
- Script: `scripts/rev09_capturar_telas.py`
