# Template de referência — Relatório Municipal (BLK-RELMUN-01)

> Transcrição estruturada do template enviado por Vini em 2026-06-22.
> Original (NÃO versionado — anti-PII / convenção §5 de não versionar PDF/PPTX):
> `C:\Users\Vinicius Cruz\Downloads\Template_Relatorio_Municipo.pdf` (+ `.pptx`).
> Este `.md` é a fonte canônica de ESTRUTURA/SEÇÕES para o ciclo; o conteúdo real
> (números) sai do motor censitário/mercado/residual por município. Camada de
> visualização/relatório — **READ-ONLY sobre o M1** (§5 guardrail).

O Relatório Municipal **coexiste** com o Relatório Pontual Censitário (raio 1,0 km),
não o substitui. Unidade de análise = **município inteiro** (selecionado no dashboard);
gerável e baixável após a seleção do município. Estética = a mesma família visual do
template GeoFusion/Ultra (turquesa + magenta + laranja; capa escura com hexágonos).

## Estrutura (11 páginas/slides)

> `PDF_SECTION_HEADERS` lista as 11 do relatório. A página "Comparação das Regiões" **saiu em 2026-10-20**: as duas tabelas de "Onde crescer" (maior residual e maior socioeconômico) a substituem. A página "Bairros — Núcleo Urbano"
> (BLK-RELMUN-11) **saiu em 2026-10-20** (Juan): repetia o mapa de score da página seguinte. O
> recorte urbano (`bounds_nucleo_urbano`) continua enquadrando os mapas temáticos por bairro.
> Município grande ganha **uma página a mais por parte** dos Bairros Oficiais (Página 3):
> São Paulo sai com 6 partes.

> Fonte de verdade da contagem/ordem: `PDF_SECTION_HEADERS` em
> `src/motor_expansao/dashboard/relatorio_municipal.py` (10 entradas), travada por
> `tests/unit/test_relatorio_municipal.py` (asserts em `/Count 11`). Ao mudar a estrutura,
> atualizar ESTE doc no mesmo PR — a página 2 abaixo ficou 1 mês fora dele (BLK-RELMUN-01-FU1).

> **Ordem desde 2026-10-20 (Juan):** apresentação do município (Bairros Oficiais) → mapas do território (Score, Residual e, com a praça, Mapas de calor, Pressão
> concorrencial e Como a cidade está indo) → oportunidade (Visão Geral com os bairros aprovados,
> Resumo e a conta do espaço) → estratégia (Expansão de Domínio, Bairros por Zona e, com a praça,
> Onde crescer) → Síntese → Espaço e academias. As cores seguem o ordinal
> de `_tema_bicolor` de cada página, não a posição.

### Página 1 — Capa
- Eyebrow: "ANÁLISE DE EXPANSÃO".
- Título: **"Potencial de Entrada de Novas Unidades"**.
- Subtítulo: "Mapeamento competitivo por região — Ultra e espaço disponível para novas academias".
- Rótulo do município: **"Cidade - UF"** (preenchido com o município selecionado).
- Arte: capa escura (roxo/navy) com hexágonos de contorno (magenta/turquesa/laranja) e barras de acento.

### Página 2 — Bairros Oficiais
- Inserida pelo **BLK-RELMUN-06**, logo após a Visão Geral: ancora o território em nomes que o
  time reconhece ANTES de a leitura virar hexágono — mesma posição que o slide ocupa no material
  de referência do time de Expansão (estudo GeoFusion).
- Título da banda: **"Bairros Oficiais - Cidade - UF"**.
- **Mapa** do município INTEIRO com o **limite territorial de cada bairro** (contorno vermelho),
  a divisa do município (contorno preto) e um **número** dentro de cada bairro; o nome vai no
  índice ao lado (desde 2026-10-20: o mapa único de São Paulo cabia 29 de 96 nomes e a placa
  cruzava a divisa). A área **cinza** é a que não tem bairro na base — nunca sai como se fosse
  divisa oficial.
- **Em partes** (`dividir_bairros_em_partes`): quando os números não cabem num quadro, a página
  vira uma visão geral com as partes coloridas e numeradas + **uma página por parte** ("Parte k
  de K"), com zoom só nela, os vizinhos em cinza, mini-mapa de localização e o índice dos seus
  bairros. Corte pela mediana do eixo mais longo até ≤ 25 bairros e números a ≥ 36 px; um vazio
  grande (zona rural longe da cidade) vira corte; parte de até 3 bairros é numerada no mapa geral.
- **Só os 40 mais populosos são numerados** (`_BAIRROS_NUMERADOS_MAX`, Juan, 2026-10-21): com o
  CNEFE o município tem centenas de bairros (São José dos Campos: 331 contra as 35 regiões do
  IBGE) e numerar todos dava 40 partes. Os demais ficam no mapa em cinza, sem número; o título
  diz "40 de N bairros" e a nota repete o recorte. Em SJC: 5 partes.
- Fonte: o **bairro do CNEFE 2022** (DEC-076), o mais frequente em cada setor, com a malha do
  IBGE como reserva (`nome_bairro` → `nome_subdistrito` → `nome_distrito`). O limite é o dos
  setores censitários do **IBGE Censo 2022** (`geometry_wkb`) **dissolvidos** por esse bairro
  (`carregar_bairros_geo`). Sem o artefato do CNEFE no `staging/`, volta à malha do IBGE.
- Coluna da direita: índice **"BAIRROS (N)"** (município numa parte só) ou **"PARTES DO
  MUNICÍPIO"** (faixa de números e três bairros de exemplo por parte).
- **Cobertura medida (2026-08-18, varredura dos 5.571 municípios com a cascata REAL do
  código — `nome_bairro` → `nome_subdistrito` → `nome_distrito`):** desenham bairro
  **196 dos 319 municípios de 100 mil+ habitantes (61,4%)**, que somam **79,0% da população**
  desse recorte. No país todo, 955 municípios (17,1%) e 55,7% da população.
  Critério: ≥2 áreas distintas E ≥50% dos setores com localidade — abaixo disso o mapa não
  divide nada útil. **Não contar só `nome_bairro`:** Goiânia/GO tem 0% de `nome_bairro` mas 64
  U.T.P.s em `nome_subdistrito`, e uma medição que pule o nível do meio a classifica como "sem
  dado" por engano (erro cometido e corrigido em 2026-08-18). Maiores que NÃO desenham:
  Campinas (31% de cobertura), São Luís, Sorocaba, Aparecida de Goiânia, Ananindeua.
- **Cobertura é heterogênea** (ver D9): abaixo de 50% dos setores com bairro/distrito, a página
  troca o subtítulo pela cobertura real e explica que o restante exigiria a malha da prefeitura —
  o número nunca sai sozinho dando a entender que o município inteiro está mapeado.
- READ-ONLY sobre o M1. Implementação: `_bairros_mapa_page` + `_render_mapa_bairros`.

### Página 3 — Score Censitário (02)
- **BLK-RELMUN-09: o mapa desta página é por BAIRRO, não por hexágono.** É a única camada
  temática em que trocar a unidade não custa precisão: o score sai do **setor**, e o bairro é
  agregação exata de setores (~21 por bairro em Novo Hamburgo). Já o hexágono res-7 tem 5,16 km²
  e é **maior que 86% dos bairros** de lá (77% no Rio) — levar métrica de hexágono para o bairro
  seria repartir, não agregar. Por isso Resumo, Residual e Domínio **seguem em hexágono**: são
  camada de mercado, e o hexágono é a unidade real delas.
- Score do bairro = média dos setores **ponderada por população** (um setor de 10 moradores não
  pode pesar como um de 990). Bairro sem score fica **cinza neutro**, nunca na faixa mais baixa —
  "sem dado" e "medido e ruim" são afirmações diferentes.
- Régua de cor INALTERADA (`score_band_to_color`, regra visual canônica do §5): a mesma cor
  significa a mesma faixa no mapa por bairro e nos mapas por hexágono.
- **Fallback em 2 casos** (`bairro_representa_o_municipio`): município **sem bairro** na base, e
  município cujos bairros mapeados **não representam o território** (< 50% dos setores com
  localidade). Nos dois, os temáticos mantêm o choropleth de hexágono e a página de Bairros
  Oficiais segue mostrando o que existe, com o aviso. O limiar é o MESMO que dispara o aviso de
  cobertura — avisar "31%" numa página e agir como se fosse pleno na outra seria incoerente.
  Caso que motivou (Campinas/SP, decisão de Juan em 2026-08-18): 31% de cobertura e os 6
  distritos mapeados **todos periféricos**, deixando o miolo urbano cinza no mapa de score
  apesar de o dado existir (score médio 61,2, máx 100,0). Afeta 65 dos 319 municípios de
  100 mil+ (Campinas, Palmas, Anápolis, Montes Claros, Cotia...).
- Subtítulo: "Potencial socioeconômico por célula hexagonal H3".
- **Mapa choropleth** H3 (verde→amarelo→laranja→vermelho) com pins Ultra/concorrentes.
- Legenda (4 faixas): **Alto potencial** (verde), **Médio-alto** (amarelo/âmbar),
  **Médio** (laranja), **Baixo potencial** (vermelho). Desde 2026-10-20 cada faixa mostra a
  **renda per capita observada** (Censo 2022) dos bairros da cidade naquela faixa, do 1º ao 3º
  quartil (`renda_por_faixa_de_score`), com o score e o número de bairros embaixo. Não é regra:
  o score mistura renda (60%) e população (40%) — DEC-040.
- Rodapé: "Fonte: IBGE Censo 2022 · Agregação H3 resolução 7".

### Página 4 — Residual Fitness (03)
- Subtítulo: "Estimativa de mercado ainda não capturado pela concorrência".
- **Mapa** residual (verde/amarelo/vermelho) com pins.
- Painel **"MERCADO DISPONÍVEL"**:
  - Número grande (magenta): **XX.XXX pessoas**.
  - **Hab. totais** ~XXX mil
  - **Renda per capita** R$ X.XXX
  - **Penetração fitness** ~XX,X%
  - Nota de método: "Pop. elegível − alunos com academia cadastrada".

### Página 5 — Visão Geral do Município
- Inserida pelo **BLK-RELMUN-01-FU1** (2026-06-23), logo após a capa — é o slide que faltava
  neste doc até 2026-07-27.
- Título da banda: **"Visão Geral do Município - Cidade - UF"**.
- **Mapa** com zoom nos **aprovados** (bbox dos hexágonos verdes ou dos bairros aprovados, margem
  de 2% — Juan, 2026-10-20), **sem legenda e sem nomes**. Verde = aprovado com dado próprio;
  o aprovado por fallback municipal sai no **cinza** do reprovado.
- À direita, tabela **"BAIRROS APROVADOS (N)"** em ordem alfabética (bairro aprovado = maioria da
  população em hexágono aprovado). Acima de 60, entram **os 60 mais populosos** (ainda em ordem
  alfabética, em duas colunas) e "+ N outros"; o título segue com o total (São José dos Campos
  com o CNEFE: 168). Sem bairro na base, o bloco **"REGIÕES CONSIDERADAS"** de antes
  (`n_aprovados` / `n_hex_municipio` / `n_reprovados`).
- READ-ONLY sobre o M1. Implementação: `_visao_geral_page` em `relatorio_municipal.py`.

### Página 6 — Resumo da Região (01)
- Título "Cidade - UF" / subtítulo "Potencial de entrada de novas unidades".
- **Mapa** de hexágonos (estilo dashboard) com pins de Ultra e concorrentes; alguns hexágonos
  exibem o número de **vagas/consumo** (ex.: 4.451, 5.061, 4.259, 3.863, 4.371, 4.561, 5.876, 4.651).
  Hexágonos verdes = aprovados (espaço disponível), cinza = o resto. **Sem legenda** desde
  2026-10-21 (Juan): o aprovado por fallback municipal deixou de sair em amarelo e sai no mesmo
  verde, porque também conta no espaço.
- Painel lateral **"RESUMO DA REGIÃO"** — tabela `Indicador | Qtd.`, nesta ordem desde 2026-10-20:
  - **Espaço para academias** = XX
  - **Unidades Concorrentes** = XX
  - **Unidades Ultra** = XX
- Box **"Como calculamos o espaço"**:
  - "Soma dos hexágonos amarelos ÷ 2.500"
  - `XXXX + XXXX + XXXX + XXXX + XXXX = XXXX`
  - `÷ 2.500 → XX`
- Legenda: "● Ultra".

### Página 7 — Como chegamos ao Espaço para academias
- Inserida em 2026-10-20 (Juan), logo após o Resumo: no mapa do Resumo cada verde parecia UM
  espaço, e dentro de um verde cabem várias academias.
- **Mapa por hexágono** (camada `espaco`, nos dois modos): aprovados em verde, cada um com o número
  de academias de 2.500 alunos que cabem nele (`academias_por_hex`: residual ÷ 2.500 pelos maiores
  restos, para os números somarem exatamente o espaço do Resumo). Por hexágono de propósito: é o
  grão em que o espaço é calculado; repartir por bairro perdia academias nos hexágonos de borda.
- Ao lado: o total ("ESPAÇO PARA ACADEMIAS") e "ONDE CABEM MAIS" (hexágonos com mais academias, pelo
  bairro dominante). Mesma fórmula da DEC-011 parte 2; só display. Implementação:
  `_espaco_explicado_page`.

### Página 8 — Expansão de Domínio (04) — mapa + estratégia
- Subtítulo: "Sugestão de posicionamento para cercar e dominar a região".
- **Mapa** com hexágonos numerados por **zona** (1, 2, 3) e pins.
- Painel **"ESTRATÉGIA"** (3 movimentos; rótulos do template — atenção: no template os textos
  de "Cerco" e "Ancora central" aparecem trocados entre as duas páginas, o Planner deve
  normalizar a redação):
  - **1 Cerco** — bairros de alta renda no Centro / hexágonos mais afastados.
  - **2 Flancos laterais** — captura dos hexágonos residuais e consolidação.
  - **3 Ancora central** — hexágonos centrais / posicionamento.
- Rodapé: "Motor de Expansão Ultra · IBGE + OSM".

### Página 9 — Expansão de Domínio (04) — bairros por zona
- Cabeçalho do painel: "Bairros com os melhores números".
- Listas de **bairros agrupadas por zona** (1/2/3/4), ex. (Bauru-SP no template):
  - Zona 1: Parque Roosevelt, Parque Primavera, Jardim Petrópolis, Núcleo 9 de Julho,
    Parque Jaraguá, Jardim Vânia Maria, Jardim Andorfato, Parque Santa Edwirges.
  - Zona 2: Parque Viaduto, Residencial Jardim Jussara, Vila Nipônica, Jardim Ferraz, Jardim Vitória.
  - Zona 3: Jardim Rosa Branca, Vila Pacífico I/II, Vila Industrial, Vila Rocha, Vila São Manoel, Vila Alto Paraíso.
  - Zona 4: Núcleo Hab. Mary Dota, Núcleo Hab. Beija-Flor, Núcleo Hab. Isaura Pitta Garms, Jardim Silvestre II.
- Rodapé: "Motor de Expansão Ultra · IBGE + OSM".

### Página 10 — Síntese — Diagnóstico & Recomendação Estratégica
- **Desde 2026-10-20 os cards 1 e 2 leem o número da cidade** (`_texto_penetracao_sintese`, `_texto_residual_sintese`) contra a régua das cidades com 100 mil+ hab. (terços medidos na base: penetração 10,5% / 15,8% / 22,8%; residual por mil hab. 138 / 151 / 169). Antes diziam sempre "penetração baixa" e "residual significativo" — São Paulo (41,8%) saía como mercado com penetração baixa. Leitura de comparação, não previsão.
- 3 cards (acento magenta / turquesa / laranja):
  - **~XX,X% de penetração** → "Mercado com Oportunidade": penetração fitness atual baixa,
    grande espaço para crescimento.
  - **XX.XXX pessoas** → "Residual Significativo": elegíveis sem academia regular,
    concentradas nas bordas/periferia.
  - **3 zonas de atuação** → "Movimento Recomendado": posicionamento periférico (cercar o
    núcleo pelos flancos antes da concorrência; áreas centrais saturadas).
- Rodapé: "Estratégia e Growth · Ultra Academia · Motor de Expansão · 2026".

### Página 11 — Síntese — Espaço e academias
- Eyebrow "SÍNTESE" / título "Espaço e academias".
- 3 big numbers:
  - **XX** Unidades Ultra mapeadas.
  - **XX** Unidades concorrentes mapeadas.
  - **XX** Espaço total p/ novas academias.
- Breakdown de concorrentes por rede (lista "X Concorrente …" + logos: Smart Fit, BF, Allp Fit,
  Bio Ritmo/pin, SkyFit, RedFit, etc. — usar as redes realmente mapeadas no município).
- Método (rodapé): "contagem de pins dentro do território · Espaço = Σ hexágonos amarelos ÷ 2.500".

## Páginas da praça (pedido do Felipe, 2026-09-10)

> Posição desde 2026-10-20: Mapas de calor, Pressão concorrencial e Como a cidade está indo logo depois do Residual Fitness; Onde crescer logo depois de Bairros por Zona, com duas tabelas: top 5 por residual e top 5 por score socioeconômico (valor absoluto; empate pelo maior residual).

`service.montar_pdf_municipio` — o preparo único do motor e do bot (#373) — monta `praca=PracaDaCidade` (`service._praca_da_cidade`) e o PDF ganha **quatro páginas** (11 -> 15 no modo bairro). Sem `praca` o PDF sai o de antes; as páginas são condicionais e ficam fora de `PDF_SECTION_HEADERS`. Cores pelos ordinais 12..15 de `_tema_bicolor`, então nenhuma página existente troca de cor. Falha no preparo deixa o PDF sair sem as quatro; falha de um mapa vira "Mapa indisponível". Lógica pura em `dashboard/relatorio_praca.py`, PNGs em `dashboard/relatorio_praca_mapas.py`, testes em `tests/unit/test_relatorio_municipal_praca.py`.

- **Mapas de calor da cidade** (depois de Score Censitário): renda média domiciliar e densidade por hexágono, lado a lado. Renda pelo mesmo mapa da tabela de regiões (`carregar_renda_domiciliar_por_hex`); sem ele a coluna fica nula, nunca cai na per capita. Densidade = população de leitura (`COLS_POPULACAO`, a precedência do piloto) sobre a área da célula, e não `densidade_pop_setor_hab_km2`, que é do setor. Cores do slide "Mapas de calor" do pontual; cortes pelos quintis da própria cidade (`quebras_por_quantil`), porque a pergunta é "quais bairros desta praça".
- **Pressão concorrencial** (depois de Residual Fitness): um disco de `RAIO_INFLUENCIA_M` (1 km, DEC-051) por academia do município — o recorte do slide Concorrentes (`filtrar_pins_do_municipio`) — sobre a cidade inteira. Com mais de `LOGOS_MAX_CIDADE` (120) academias as logos viram pontos, senão escondem os discos. Painel: concorrentes, independentes, Ultra, % dos hexágonos com o centro sob algum raio, % com 3+ raios (`N_DISCOS_DISPUTA`), máximo num hexágono e as 5 redes com mais unidades (`pressao_na_cidade`).
- **Onde crescer** (depois de Expansão de Domínio): os 5 hexágonos de `selecionar_onde_crescer`, com o bairro dominante. **Não é o residual puro** (Spearman ~0,995 com população, DEC-041): elegível = residual > 0 **e** renda domiciliar >= mediana da cidade; ordem pelo `indice_praca` da DEC-041, desempate por renda e `hex_id`. O índice é calculado por `dashboard/praca_indice.py`, o MESMO módulo da camada 5 do funil — ele saiu de `web/server/` para `src/` porque o container da API não importa `web/server`, e `web/server/praca_indice.py` virou alias (`sys.modules`). Leitura só do PDF: funil, `/api/hexagonos` e índice não mudam.
- **Como a cidade está indo** (antes da Síntese): a linha do município em `crescimento_municipal.parquet` da staging (`linha_crescimento_municipal`, por `cod6` e, sem ele, por `UF|NOME`), lida pelo service para o bot e o motor terem a mesma página — a base do bot não traz as colunas `cres_*`. Frase = `v_frase`. Município sem linha (inclusive AR, que não tem a camada) mostra "Sem dado de crescimento para este município.".

A moeda dos mapas e da tabela vem do perfil (`simbolo_renda`, #374).

**Limpeza dos mapas temáticos (2026-09-17, pedido do Juan).** Duas regras, porque em capital o mapa ficava ilegível:
- **Nome de bairro só nos 5 hexágonos de "Onde crescer".** Antes ele saía em todo hexágono aprovado (São Paulo: 154 placas). `service.montar_pdf_municipio` calcula a praça ANTES dos mapas e passa `hexes_rotulados` a `render_mapas_municipio`; sem ele o comportamento antigo continua valendo.
- **Pins só da Ultra** (`TOP_REDES_NO_MAPA = 0`). O corte foi em dois passos no mesmo dia: primeiro as 5 maiores redes (`principais_redes`), que em São Paulo ainda davam 370 pins porque só a Smart Fit tem 171, e depois nenhuma — Resumo e Domínio respondem ONDE HÁ ESPAÇO, e a concorrência tem duas páginas próprias. O rodapé do PNG declara o recorte em segunda linha ("no mapa, só as unidades Ultra; as 491 concorrentes estão em Pressão concorrencial e Espaço e academias"), e as contagens cheias seguem nos painéis. Voltar a desenhar as N maiores redes é mudar a constante.

**Domínio com os 10 melhores e zoom na melhor área (2026-09-17).** A camada de Domínio pintava e numerava os 154 hexágonos aprovados de São Paulo; passa a numerar só os 10 melhores pela régua de "Onde crescer" (`service.TOP_HEXES_DOMINIO`, os 5 primeiros são os da página). O Domínio enquadra esses hexágonos (`_focus_bounds_mercator(hexes_foco=...)`); o Resumo enquadra os mesmos escolhidos com margem folgada (`_FOCUS_PAD_FRAC_RESUMO`) e **sem os pins no cálculo** — enquadrar todos os aprovados devolvia a cidade inteira, porque em São Paulo eles vão de norte a sul — uma unidade num hexágono afastado esticava o quadro e trazia junto a cauda cinza. O mapa do Resumo continua desenhando os hexágonos não aprovados, que são o contexto: o pedido era priorizar os verdes no ZOOM quando houvesse cinza nas pontas, e quem faz isso é o enquadramento, o mapa de "Onde crescer" fecha nos 5 escolhidos (`relatorio_praca_mapas.quadro_onde_crescer`), e os demais mapas ganharam uma aproximação leve (`_FOCUS_MIN_SPAN_M` 6.000 -> 5.000 m e `_FOCUS_PAD_FRAC` 0,16 -> 0,08).

**Mapa do Resumo sem o número em cada hexágono (2026-09-17).** O Residual de cada hexágono destacado saía numa plaquinha magenta sobre o mapa (São Paulo: 154 delas). A pedido do Juan o relatório passa a pedir o mapa sem elas (`rotular_valores=False`); os valores seguem na tabela "Comparação das Regiões" e o total, no box "Como calculamos o espaço", que ficou intacto. Quem chama `_render_mapa_municipio` direto continua com o default `True`, e é assim que `test_rotulo_de_valor_fica_acima_do_marcador_blk_relpon_09_fu1` segue travando a ordem rótulo-sobre-pin.

**Score Censitário e Residual Fitness sem pins (2026-09-17).** Na versão por hexágono os dois mapas levavam as logos de concorrentes e Ultra, e em capital elas cobriam os hexágonos (São Paulo: 491 academias). Agora seguem a regra da versão por bairro: pins só em Resumo e Domínio.

**Bases com join censitário ruim (medido em Manaus/AM, 2026-09-17).** Três defeitos que só aparecem lá:
- a **população do hexágono** vinha de `populacao_corte_hex`, que nessas bases repete os 2.063.689 habitantes do município em cada um dos 2.139 hexágonos (DEC-054/058). Na densidade isso virava "mesmo número ÷ área da célula" e o mapa saía em faixas verticais. A precedência de `relatorio_praca.COLS_POPULACAO` passa a começar por `pop_total_setor_2022` (cobertura medida: 99,9% em Manaus, 98,6% em São Paulo); sem dado de setor, `populacao_e_municipal` suprime o mapa de densidade e a legenda explica (`TEXTO_POP_MUNICIPAL`);
- a **legenda do mapa de calor** repetia faixas ("0 a 0") ou publicava faixa degenerada ("0,2 a 0,2") quando a floresta domina os quintis; faixas assim são fundidas, e abaixo de 10 o número sai com uma casa decimal.

## Decisões do gate humano (APROVADO por Vinicius, 2026-06-22 — DEC-011) — IMPLEMENTADO

Implementação em `src/motor_expansao/dashboard/relatorio_municipal.py` (módulo NOVO, disjunto;
helpers de layout reimplementados localmente — o Relatório Pontual fica BYTE-A-BYTE intocado).
Expander "Relatório Municipal" em `render_mapa_territorial` (pages.py), habilitado só com
EXATAMENTE 1 município selecionado. READ-ONLY sobre o M1.

- **D1 — hexágono DESTACADO ("amarelo"):** `sam_fitness_potencial >= 3000` **E**
  `oferta_efetiva_disponivel >= 2000` (ambas colunas reais, em alunos; presentes no slice
  enriquecido por UF). **Rótulo sobre cada hexágono destacado** = `oferta_efetiva_disponivel`.
  **"Espaço para academias"** (Páginas 2 e 11) = `round( Σ oferta_efetiva_disponivel dos
  destacados ÷ 2.500 )`. Limiares de DISPLAY locais ao módulo; NÃO mexem em `flag_sam`/DEC-006/
  DEC-007 nem no M1.
- **D2 — zonas (Páginas 8–9):** via `dominio_df` (`plano_expansao_dominio.parquet`) agrupado por
  `cluster_id` do município, ordenado por `residual_total_cluster` desc, cap em 3 zonas. Fallback
  gracioso (sem `dominio_df`/sem o município): Páginas 8–9 em modo simplificado, sem exceção.
- **D3 — mapas COM TILES ONLINE:** `contextily`/EPSG:3857, cache `data/cache/basemap_tiles/`,
  import lazy, fallback offline gracioso (canvas claro SEM ruas), default `basemap=False` em
  CI/teste, atribuição "© OpenStreetMap, © CARTO" no rodapé. (DEC-011 parte 1, estende a DEC-004.)
- **D4 — Mercado disponível / Residual:** `Σ oferta_efetiva_disponivel` do município (alunos).
- **D5 — faixas do Score Censitário:** Alto ≥70 / Médio-alto 50–70 / Médio 30–50 / Baixo <30
  (cores via `RESIDUAL_SCORE_BANDS`/`score_band_to_color`).
- **D6 — pins Ultra/concorrentes:** filtro geográfico por H3 res-7 (pin cai num `hex_id` do
  município; reusa `hex_id_res7` quando presente, senão deriva via `h3`). Anti-PII: só `rede`/contagem.
- **D7 — redação das zonas:** 1 Âncora central / 2 Flancos laterais / 3 Cerco.
- **D8 — Página 11:** breakdown só das redes de concorrentes realmente mapeadas + carimbo de versão
  do contrato no rodapé (`VERSAO_CONTRATO_MUNICIPAL`).
- **D9 — Página 9 (bairros) IMPLEMENTADA (BLK-RELMUN-02):** lista os bairros REAIS agrupados pelas
  3 zonas geométricas (Âncora central / Flancos laterais / Cerco), fonte **IBGE Censo 2022
  `NM_BAIRRO` do setor** (coluna `nome_bairro` agora materializada em
  `data/outputs/setores_censitarios_2022_geo/`). O relatório lê a partição geo do município
  on-demand (`_carregar_bairros_por_hex` → bairro dominante por `hex_id` res-7, por população do
  setor) e agrupa por zona (`_bairros_por_zona`), cap de ~10 bairros/zona + "... e mais N" ao
  truncar. **Cobertura de bairro é HETEROGÊNEA** entre municípios (capitais/grandes têm; muitos
  municípios pequenos e o DF não têm `NM_BAIRRO`). **Fallback gracioso mandatório:** município sem
  bairro mapeado cai nas zonas geométricas + descrição/tese, sem exceção e sem a nota "indisponível"
  como texto principal. READ-ONLY sobre o M1; camada de display (não altera score/artefatos/M1).

## Notas de mapeamento dados → motor (a confirmar pelo Planner)
- "Espaço para academias" = Σ (vagas/consumo dos hexágonos amarelos) ÷ **2.500** (capacidade
  default de unidade já documentada em CLAUDE.md §4: "capacidade default de concorrente/unidade
  proxy: 2500 alunos").
- "Score Censitário" = `score_setor_2022_calibrado` agregado em H3 res 7 (faixas de cor já
  existentes; mapear as 4 faixas do template sobre `RESIDUAL_SCORE_BANDS`/bandas existentes).
- "Residual Fitness / Mercado disponível" = camada residual já existente (`oferta_efetiva_disponivel`
  / `score_oportunidade_residual`; pop elegível − consumo instalado).
- "Expansão de Domínio / zonas / bairros" = camada de domínio híbrido + nomes de bairro/setor.
- "Unidades Ultra / Concorrentes" = contagem de pins (Ultra própria + concorrentes mapeados) dentro
  do território municipal.
- Reusar, onde fizer sentido, `censo_report.py` / `censo_map.py` / `pages.py` e a base geo
  `data/outputs/setores_censitarios_2022_geo/...`, **sem** alterar o Relatório Pontual existente.
