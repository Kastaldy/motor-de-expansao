# Template de referência — Relatório Municipal (BLK-RELMUN-01)

> **Em poucas palavras**
> - **Do que trata:** O relatório em PDF de uma cidade: cada página, sua ordem e a origem dos números, dos mapas de bairro e de mercado ainda livre à lista de onde expandir.
> - **Quando ler:** Para entender uma página ou um número do PDF de uma cidade, ou antes de pedir mudança na estrutura dele.
> - **Atenção:** No Brasil, várias páginas saem ou mudam para dar uma lista única de onde expandir. Leia antes a tabela do Brasil: ela prevalece sobre a descrição de cada página.

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
> Município grande ganha **uma página a mais por parte** dos Bairros Oficiais (Página 2):
> São Paulo sai com 6 partes.

> Fonte de verdade da contagem/ordem: `PDF_SECTION_HEADERS` em
> `src/motor_expansao/dashboard/relatorio_municipal.py` (11 entradas), travada por
> `tests/unit/test_relatorio_municipal.py` (asserts em `/Count 11`). Ao mudar a estrutura,
> atualizar ESTE doc no mesmo PR — a página 2 abaixo ficou 1 mês fora dele (BLK-RELMUN-01-FU1).

> **Ordem desde 2026-10-20 (Juan):** apresentação do município (Bairros Oficiais) → mapas do território (Score, Residual e, com a praça, Mapas de calor, Pressão
> concorrencial e Como a cidade está indo) → oportunidade (Visão Geral com os bairros aprovados,
> Resumo e a conta do espaço) → estratégia (Expansão de Domínio, Bairros por Zona e, com a praça,
> Onde crescer) → Síntese → Espaço e academias. As cores seguem o ordinal
> de `_tema_bicolor` de cada página, não a posição.

### No Brasil: resposta única de "onde expandir" (DEC-077, desde 2026-10-22)

Onde o país tem régua de recomendação (hoje só o BR), o preparo liga
`resultado["resposta_unica"]` (`CHAVE_RESPOSTA_UNICA`) e o relatório mostra **uma** lista de
onde expandir: a do "Onde crescer", que é o Top 10 do módulo único
(`motor_expansao.recomendacao.montar_recomendacao`, a mesma lista da tela). Sem régua
(Argentina), tudo fica como descrito nas páginas abaixo.

| Página | No Brasil |
|---|---|
| Capa | Subtítulo "Mapeamento competitivo por região - Ultra, concorrência e capacidade não atendida" (sem "espaço disponível para novas academias"). |
| Bairros Oficiais | Município sem bairro na base: a nota não promete mais "as zonas geométricas" das páginas seguintes, que saíram. |
| Visão Geral do Município | **Fora** (Juan, 22/10/2026). Sem o verde de aprovado e sem a tabela "BAIRROS APROVADOS" ela ficou neutra e repetia o mapa do Resumo; o mapa `cobertura` nem é desenhado no Brasil. |
| Resumo da Região | Mapa neutro só com as unidades Ultra (`TOP_REDES_NO_MAPA = 0` desde 2026-09-18; o rodapé do PNG remete as concorrentes a Pressão concorrencial e Espaço e academias), no enquadramento de Score e Residual (sem foco em escolhidos). Painel com os números da cidade; "Como calculamos o espaço" fala em "regiões com 2.000 ou mais". |
| Como chegamos ao Espaço | Fica, com os números por hexágono em laranja (não no verde do aprovado) e sem o quadro "ONDE CABEM MAIS" (Felipe, 22/10); o texto diz "regiões com residual a partir de 2.000 alunos (capacidade não atendida)" em vez de "aprovadas". |
| Expansão de Domínio e Bairros por Zona | Fora, até chegarem os dados do gestor. |
| Como a cidade está indo | Sem a frase de veredito ("É praça para entrar", `v_frase`): a caixa do topo fica só com o nome da cidade. Os outros números continuam; "Sem dado" só quando não sobra nenhum. |
| Onde crescer | Tabela **Mata Virgem** (5, em ordem de residual) e tabela **Premium** (5, em ordem de população), colunas #, Região, Residual, População e Renda domiciliar. Vaga sem candidato: "Vaga vazia: …" com o motivo do módulo; sem o carimbo k da malha, ou com a base recusada pelo módulo, uma linha "… indisponível …" por segmento, sem número. Nome = bairro de mais moradores (`rotulos_das_regioes`); o "A / B" que não cabe vai em duas linhas; sem bairro, o município, e a nota avisa. Mapa: verde = Mata Virgem, azul = Premium, subtítulo com as vagas preenchidas e o teto da régua; sem nenhuma região, a cidade em cinza ("Nenhuma regiao da cidade atende a regua", sem acento como todo texto dos mapas da praça). Nota com os números e os critérios da régua. |
| Síntese | Título "Síntese - Diagnóstico". Dois cards (penetração e residual); o de zonas sai. O residual diz quanto dele está "nas regiões com residual a partir de 2.000 alunos". |
| Espaço e academias | O número sai como "Espaço para academias: capacidade não atendida nas regiões com residual a partir de 2.000 alunos". |

Base: o bot/API lê a partição enriquecida da UF (a da tela), com a coluna `uf`; sem ela, recusa
(503, `base_da_tela_ausente`). A subida da API confere a régua e o carimbo k da malha
(`recomendacao.validar_na_subida`). Carimbo: `BLK-RELMUN | contrato v3`.

### Página 1 — Capa
- Eyebrow: "ANÁLISE DE EXPANSÃO".
- Título: **"Potencial de Entrada de Novas Unidades"**.
- Subtítulo: "Mapeamento competitivo por região — Ultra e espaço disponível para novas academias".
- Rótulo do município: **"Cidade - UF"** (preenchido com o município selecionado).
- Arte: capa escura (roxo/navy) com hexágonos de contorno (magenta/turquesa/laranja) e barras de acento.

### Página 2 — Bairros Oficiais
- Inserida pelo **BLK-RELMUN-06**; vem logo após a Capa: ancora o território em nomes que o
  time reconhece ANTES de a leitura virar hexágono — mesma posição que o slide ocupa no material
  de referência do time de Expansão (estudo GeoFusion).
- Título da banda: **"Bairros Oficiais - Cidade - UF"**.
- **Mapa** do município INTEIRO com o **limite territorial de cada bairro** (contorno vermelho),
  a divisa do município (contorno preto) e um **número** dentro de cada bairro; o nome vai no
  índice ao lado (com o nome no mapa, o de São Paulo cabia 29 de 96 nomes e a placa
  cruzava a divisa). A área **sem bairro na base** sai **sem cor, só com contorno cinza** — nunca
  como se fosse divisa oficial — e sem preenchimento: é quase
  sempre mata, parque ou zona rural, e o fundo de ruas (OpenMapTiles) mostra isso; um cinza por cima tapa o verde. Vale para todos os mapas por bairro.
- **Em partes** (`dividir_bairros_em_partes`): quando os números não cabem num quadro, a página
  vira uma visão geral com as partes coloridas e numeradas + **uma página por parte** ("Parte k
  de K"), com zoom só nela, os vizinhos em cinza, mini-mapa de localização e o índice dos seus
  bairros. Corte pela mediana do eixo mais longo até ≤ 25 bairros e números a ≥ 36 px; um vazio
  grande (zona rural longe da cidade) vira corte; parte de até 3 bairros é numerada no mapa geral.
- **Só os 40 mais populosos são numerados** (`_BAIRROS_NUMERADOS_MAX`, Juan, 2026-10-21): com o
  CNEFE o município tem centenas de bairros (São José dos Campos: 331 contra as 35 regiões do
  IBGE) e numerar todos dava 40 partes. O título diz "40 de N bairros" e a nota repete o recorte.
  Em SJC: 5 partes.
- **O município inteiro nas cores das partes** (Juan, 2026-10-22): cada bairro sem número vai
  para a parte do numerado mais próximo (`parte_de`) e sai no **tom claro** da cor dela; os
  numerados, no tom cheio. Antes os sem número saíam em cinza — em SJC, 84% da área e metade da
  população —, e as partes, com alpha baixo e composição que escurecia a cor, saíam bege. O índice
  diz "Parte k - n de N bairros". Nas **páginas das partes** o bairro sai só com **contorno forte
  na cor da parte, sem preenchimento** (`so_contorno`, Juan, 2026-10-22): ali o que se lê é o
  limite do bairro, e a cor cheia fazia a página parecer mais um mapa temático. Traço grosso nos
  numerados, fino nos demais da parte; os das outras partes, em cinza. Nenhum bairro falta: em SJC os 331 bairros
  e a área sem bairro (160 km², 3,3 mil habitantes) cobrem o município (~1 km² sem polígono, de
  arredondamento).
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
  seria repartir, não agregar. Resumo, Residual, Domínio e a Visão Geral **também** saem por bairro no modo bairro desde o
  BLK-RELMUN-10 (decisão de 2026-08-14), mas por REPARTIÇÃO do hexágono por população — estimativa,
  não medição, e o rodapé de cada mapa declara a procedência.
- Score do bairro = média dos setores **ponderada por população** (um setor de 10 moradores não
  pode pesar como um de 990). Bairro sem score fica **cinza neutro**, nunca na faixa mais baixa —
  "sem dado" e "medido e ruim" são afirmações diferentes.
- Régua de cor INALTERADA (`score_band_to_color`, regra visual canônica do §5): a mesma cor
  significa a mesma faixa no mapa por bairro e nos mapas por hexágono.
- **Fallback em 1 caso** (`tem_bairro_real`): só o município **sem bairro** na base mantém o
  choropleth de hexágono. O segundo caso — bairros que **não representam o território** (< 50% dos
  setores com localidade; Campinas/SP, decisão de Juan em 2026-08-18, 65 dos 319 municípios de
  100 mil+) — foi REVERTIDO em 2026-08-19, também a pedido de Juan (Sinop/MT): hoje eles saem por
  bairro, presos ao recorte do núcleo urbano, e só a página de Bairros Oficiais declara a cobertura
  real. Em Campinas o miolo urbano aparece sem cor, com contorno cinza ("sem bairro na base").
- Subtítulo: "Potencial socioeconômico por célula hexagonal H3".
- **Mapa choropleth** por bairro (H3 no modo hexágono e no fallback), verde→amarelo→laranja→vermelho, **sem pins** desde 2026-09-17.
- Legenda (4 faixas): **Alto potencial** (verde), **Médio-alto** (amarelo/âmbar),
  **Médio** (laranja), **Baixo potencial** (vermelho). Desde 2026-10-20 cada faixa mostra a
  **renda domiciliar observada** (a do card do mapa; sem ela, a per capita do Censo 2022) e a **densidade** dos bairros da cidade naquela faixa, do 1º ao 3º
  quartil (`renda_por_faixa_de_score`), com o score e o número de bairros embaixo. Não é regra:
  o score mistura renda (60%) e população (40%) — DEC-040.
- Rodapé: "Fonte: IBGE Censo 2022 · Agregação H3 resolução 7".

### Página 4 — Residual Fitness (03)
- Subtítulo: "Estimativa de mercado ainda não capturado pela concorrência".
- **Mapa** residual (verde/amarelo/vermelho), **sem pins** desde 2026-09-17.
- Painel **"MERCADO DISPONÍVEL"**:
  - Número grande (magenta): **XX.XXX pessoas**.
  - **Hab. totais** ~XXX mil
  - **Renda per capita** R$ X.XXX
  - **Penetração fitness** ~XX,X%
  - Nota de método: "Pop. elegível − alunos com academia cadastrada".

### Página 5 — Visão Geral do Município
- **Só fora do Brasil desde 2026-10-22** (Juan): no PDF com a resposta única (DEC-077) a página
  não sai — ver a tabela "No Brasil" acima.

- Título da banda: **"Visão Geral do Município - Cidade - UF"**.
- **Mapa** com zoom nos **aprovados** (bbox dos hexágonos verdes ou dos bairros aprovados, margem
  de 2% — Juan, 2026-10-20), **sem legenda e sem nomes**. Verde = aprovado com dado próprio;
  o aprovado por fallback municipal sai no **cinza** do reprovado.
- À direita, tabela **"BAIRROS APROVADOS (N)"** em ordem alfabética (bairro aprovado = maioria da
  população em hexágono aprovado). Acima de 60, entram **os 60 mais populosos** (ainda em ordem
  alfabética, em duas colunas) e "+ N outros"; o título segue com o total (São José dos Campos
  com o CNEFE: 168). Sem bairro na base, o bloco **"REGIÕES CONSIDERADAS"** de antes
  (`n_aprovados` / `n_hex_municipio` / `n_reprovados`).
- READ-ONLY sobre o M1. Implementação: `_cobertura_page` em `relatorio_municipal.py`.

### Página 6 — Resumo da Região (01)
- Título "Cidade - UF" / subtítulo "Potencial de entrada de novas unidades".
- **Mapa** (por bairro no modo bairro; de hexágonos no modo hexágono e no fallback) só com os pins da Ultra
  (`TOP_REDES_NO_MAPA = 0`) e sem o número de **vagas/consumo** em cada hexágono (`rotular_valores=False`).
  Hexágonos verdes = aprovados (espaço disponível), cinza = o resto. **Sem legenda** (Juan): o aprovado por fallback municipal sai no mesmo
  verde, porque também conta no espaço.
- Painel lateral **"RESUMO DA REGIÃO"** — tabela `Indicador | Qtd.`, nesta ordem desde 2026-10-20:
  - **Espaço para academias** = XX
  - **Unidades Concorrentes** = XX
  - **Unidades Ultra** = XX
- Box **"Como calculamos o espaço"**:
  - "Soma dos hexágonos destacados / 2.500" (no Brasil, "Residual das regiões com 2.000 ou mais / 2.500")
  - `XXXX + XXXX + XXXX + XXXX + XXXX = XXXX`
  - `÷ 2.500 → XX`
- Sem legenda (2026-10-21); o rodapé do PNG declara o recorte de academias desenhado.

### Página 7 — Como chegamos ao Espaço para academias
- Inserida em 2026-10-20 (Juan), logo após o Resumo: no mapa do Resumo cada verde parecia UM
  espaço, e dentro de um verde cabem várias academias.
- **Mapa por hexágono** (camada `espaco`, nos dois modos): aprovados em verde, cada um com o número
  de academias de 2.500 alunos que cabem nele (`academias_por_hex`: residual ÷ 2.500 pelos maiores
  restos, para os números somarem exatamente o espaço do Resumo). Por hexágono de propósito: é o
  grão em que o espaço é calculado; repartir por bairro perdia academias nos hexágonos de borda.
  O número sai como texto do PDF dentro de um **círculo grafite com borda branca** (2026-10-22):
  em branco direto no hexágono ele sumia sob as ruas e os nomes do fundo de ruas, que vêm por cima
  dos hexágonos.
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
- **Os cards 1 e 2 leem o número da cidade** (`_texto_penetracao_sintese`, `_texto_residual_sintese`) contra a régua das cidades com 100 mil+ hab. (terços — p33 / mediana / p67 — medidos na base local em 2026-10-20: penetração 10,5% / 15,8% / 22,8%; residual por mil hab. 138 / 151 / 169; DEC-011, emenda de 2026-10-21, item 6, aprovada em 2026-10-29). Antes de 2026-10-20 diziam sempre "penetração baixa" e "residual significativo" — São Paulo (41,8% naquela base) saía como mercado com penetração baixa. Leitura de comparação, não previsão.
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

> Posição desde 2026-10-20: Mapas de calor, Pressão concorrencial e Como a cidade está indo logo depois do Residual Fitness; Onde crescer logo depois de Bairros por Zona, com duas tabelas: top 5 por residual e top 5 por score socioeconômico (valor absoluto; no teto de 100 o empate sai pela mesma mistura renda + população sem o teto, `com_socio_sem_teto`; no Brasil as duas tabelas são Mata Virgem e Premium, DEC-077).

`service.montar_pdf_municipio` — o preparo único do motor e do bot (#373) — monta `praca=PracaDaCidade` (`service._praca_da_cidade`) e o PDF ganha **quatro páginas** (11 -> 15; no Brasil, com a resposta única da DEC-077, 8 -> 12). Sem `praca` o PDF sai o de antes; as páginas são condicionais e ficam fora de `PDF_SECTION_HEADERS`. Cores pelos ordinais 12..15 de `_tema_bicolor`, então nenhuma página existente troca de cor. Falha no preparo deixa o PDF sair sem as quatro; falha de um mapa vira "Mapa indisponível". Lógica pura em `dashboard/relatorio_praca.py`, PNGs em `dashboard/relatorio_praca_mapas.py`, testes em `tests/unit/test_relatorio_municipal_praca.py`.

- **Mapas de calor da cidade** (depois de Residual Fitness): renda média domiciliar e densidade por hexágono, lado a lado. Renda pelo mesmo mapa por hexágono do card do mapa (`motor_expansao.renda.renda_domiciliar_por_hex`, desde o #460; a tabela de regiões saiu em 2026-10-20); sem ele a coluna fica nula, nunca cai na per capita. Densidade = população de leitura (`COLS_POPULACAO`, que começa pelo dado de setor — de propósito, diferente da precedência do funil; ver Manaus abaixo) sobre a área da célula, e não `densidade_pop_setor_hab_km2`, que é do setor. Cores do slide "Mapas de calor" do pontual; cortes pelos quintis da própria cidade (`quebras_por_quantil`), porque a pergunta é "quais bairros desta praça".
- **Pressão concorrencial** (depois de Residual Fitness): um disco de `RAIO_INFLUENCIA_M` (1 km, DEC-051) por academia do município — o recorte do slide Concorrentes (`filtrar_pins_do_municipio`) — sobre a cidade inteira. Com mais de `LOGOS_MAX_CIDADE` (120) academias as logos viram pontos, senão escondem os discos. **O raio é a leitura, não o ponto exato** (Juan): os discos saem por tipo — independente por baixo, rede no meio, Ultra por cima — com a borda de rede e Ultra mais forte (`_DISCO_REALCE`), para o raio de rede não sumir sob o âmbar das independentes (SJC: 139 de 166); pontos de 7/9/11 px (independente/rede/Ultra) e logos de rede/Ultra em 40 px; quadro fechado em 2,5%–97,5% das academias a partir de 60 (folga de meio raio), com as que ficam fora contadas no subtítulo. Isso vale só para o Municipal: a pressão do Relatório Pontual tem regra própria. Painel: concorrentes, independentes, Ultra, % dos hexágonos com o centro sob algum raio, % com 3+ raios (`N_DISCOS_DISPUTA`), máximo num hexágono e as 5 redes com mais unidades (`pressao_na_cidade`).
- **Onde crescer** (depois de Bairros por Zona; no Brasil, depois de Como chegamos ao Espaço): duas tabelas de 5 hexágonos pelo valor absoluto — maior residual e maior score socioeconômico (`relatorio_praca.top_por_coluna`) —; no Brasil, Mata Virgem e Premium da recomendação única (DEC-077). `selecionar_onde_crescer` (elegível = residual > 0 **e** renda domiciliar >= mediana da cidade; ordem pelo `indice_praca` da DEC-041, desempate por renda e `hex_id`), só numera o Top 10 do Domínio, fora do Brasil. O índice é calculado por `dashboard/praca_indice.py`, o MESMO módulo da camada 5 do funil — fica em `src/` porque o container da API não importa `web/server`, e `web/server/praca_indice.py` é alias (`sys.modules`). Leitura só do PDF: funil, `/api/hexagonos` e índice não mudam.
- **Como a cidade está indo** (depois de Pressão concorrencial): a linha do município em `crescimento_municipal.parquet` da staging (`linha_crescimento_municipal`, por `cod6` e, sem ele, por `UF|NOME`), lida pelo service para o bot e o motor terem a mesma página — a base do bot não traz as colunas `cres_*`. Frase = `v_frase`. Município sem linha (inclusive AR, que não tem a camada) mostra "Sem dado de crescimento para este município.".

A moeda dos mapas e da tabela vem do perfil (`simbolo_renda`, #374).

**Limpeza dos mapas temáticos (2026-09-17, pedido do Juan).** Duas regras, porque em capital o mapa ficava ilegível:
- **Nome de bairro fora dos hexágonos.** Desde 2026-10-20 nenhum hexágono leva nome de bairro — `render_mapas_municipio` ainda aceita `hexes_rotulados`, mas `_render_mapa_municipio` não o lê mais (no Brasil o service passa `None`). Antes disso, em 2026-09-17, o nome tinha ficado só nos 5 hexágonos de "Onde crescer" (até então saía em todo hexágono aprovado; São Paulo, naquela data: 154 placas).
- **Pins só da Ultra** (`TOP_REDES_NO_MAPA = 0`). O corte foi em dois passos no mesmo dia: primeiro as 5 maiores redes (`principais_redes`), que em São Paulo ainda davam 370 pins porque só a Smart Fit tinha 171 naquela data, e depois nenhuma — Resumo e Domínio respondem ONDE HÁ ESPAÇO, e a concorrência tem duas páginas próprias. O rodapé do PNG declara o recorte em segunda linha ("no mapa, só as unidades Ultra; as 491 concorrentes estão em Pressão concorrencial e Espaço e academias", em São Paulo naquela data), e as contagens cheias seguem nos painéis. Voltar a desenhar as N maiores redes é mudar a constante.

**Domínio com os 10 melhores e zoom na melhor área.** A camada de Domínio numera só os 10 melhores pela régua de "Onde crescer" (`service.TOP_HEXES_DOMINIO`, por `selecionar_onde_crescer`; a página "Onde crescer" mostra outras listas, e no Brasil a página de Domínio não sai — DEC-077). O Domínio enquadra esses hexágonos (`_focus_bounds_mercator(hexes_foco=...)`); o Resumo enquadra os mesmos escolhidos com margem folgada (`_FOCUS_PAD_FRAC_RESUMO`) e **sem os pins no cálculo** — enquadrar todos os aprovados devolvia a cidade inteira, porque em São Paulo eles vão de norte a sul — uma unidade num hexágono afastado esticava o quadro e trazia junto a cauda cinza. O mapa do Resumo desenha também os hexágonos não aprovados, que são o contexto: quem prioriza os verdes no ZOOM é o enquadramento. O mapa de "Onde crescer" fecha nos até 10 hexágonos das duas listas (`relatorio_praca_mapas.render_onde_crescer_duas_listas`), e os demais mapas têm uma aproximação leve (`_FOCUS_MIN_SPAN_M` = 5.000 m e `_FOCUS_PAD_FRAC` = 0,08).

**Mapa do Resumo sem o número em cada hexágono (2026-09-17).** O Residual de cada hexágono destacado saía numa plaquinha magenta sobre o mapa (São Paulo, naquela data: 154 delas). A pedido do Juan, o relatório pede o mapa sem elas (`rotular_valores=False`); os valores seguiam na tabela "Comparação das Regiões" (que saiu em 2026-10-20), e o total segue no box "Como calculamos o espaço", que ficou intacto naquela mudança. Quem chama `_render_mapa_municipio` direto continua com o default `True`; `test_rotulo_de_valor_fica_acima_do_marcador_blk_relpon_09_fu1` chama o render direto, com `rotular_valores=True` explícito, e assim segue travando a ordem rótulo-sobre-pin.

**Score Censitário e Residual Fitness sem pins (2026-09-17).** Na versão por hexágono os dois mapas levavam as logos de concorrentes e Ultra, e em capital elas cobriam os hexágonos (São Paulo, naquela data: 491 academias). Agora seguem a regra da versão por bairro: pins só em Resumo e Domínio.

**Bases com join censitário ruim (medido em Manaus/AM, 2026-09-17).** Três defeitos que só aparecem lá:
- a **população do hexágono** vinha de `populacao_corte_hex`, que nessas bases repete os 2.063.689 habitantes do município em cada um dos 2.139 hexágonos (DEC-054/058). Na densidade isso virava "mesmo número ÷ área da célula" e o mapa saía em faixas verticais. A precedência de `relatorio_praca.COLS_POPULACAO` passa a começar por `pop_total_setor_2022` (cobertura medida: 99,9% em Manaus, 98,6% em São Paulo); sem dado de setor, `populacao_e_municipal` suprime o mapa de densidade e a legenda explica (`TEXTO_POP_MUNICIPAL`);
- a **legenda do mapa de calor** repetia faixas ("0 a 0") ou publicava faixa degenerada ("0,2 a 0,2") quando a floresta domina os quintis; faixas assim são fundidas, e abaixo de 10 o número sai com uma casa decimal.

## Decisões do gate humano (APROVADO por Vinicius, 2026-06-22 — DEC-011) — IMPLEMENTADO

Implementação em `src/motor_expansao/dashboard/relatorio_municipal.py` (módulo disjunto;
helpers de layout reimplementados localmente — o Relatório Pontual fica BYTE-A-BYTE intocado).
O PDF sai pelo piloto web (`POST /api/relatorio/municipal`) e pela API/bot (`POST /api/v1/analisar-municipio`), pelo mesmo preparo `service.montar_pdf_municipio`. READ-ONLY sobre o M1.

- **D1 — hexágono DESTACADO ("amarelo"):** `oferta_efetiva_disponivel >= 2000` (`OFERTA_DESTAQUE_MIN`; o termo
  `sam_fitness_potencial >= 3000` saiu na emenda do BLK-RELMUN-03, e o rótulo do residual sobre cada
  hexágono destacado saiu em 2026-09-17, `rotular_valores=False`).
  **"Espaço para academias"** (Páginas 6 e 11) = `round( Σ oferta_efetiva_disponivel dos
  destacados ÷ 2.500 )`. Limiares de DISPLAY locais ao módulo; NÃO mexem em `flag_sam`/DEC-006/
  DEC-007 nem no M1.
- **D2 — zonas (Páginas 8–9):** via `dominio_df` (`plano_expansao_dominio.parquet`) agrupado por
  `cluster_id` do município, ordenado por `residual_total_cluster` desc, cap em 3 zonas. Fallback
  gracioso (sem `dominio_df`/sem o município): Páginas 8–9 em modo simplificado, sem exceção.
- **D3 — mapas COM TILES ONLINE:** `contextily`/EPSG:3857, cache `data/cache/basemap_tiles/`,
  import lazy, fallback offline gracioso (canvas claro SEM ruas), default `basemap=False` em
  CI/teste (DEC-011 parte 1, estende a DEC-004). Com `API_BASEMAP_TILES_URL` o fundo vem do tileserver OpenMapTiles próprio (a mesma env do Pontual) e o crédito no rodapé é "(c) OpenStreetMap - OpenMapTiles"; sem ela, o CARTO Voyager, com "(c) OpenStreetMap, (c) CARTO" (BLK-BASEMAP-02/06).
- **D4 — Mercado disponível / Residual:** `Σ oferta_efetiva_disponivel` do município (alunos).
- **D5 — faixas do Score Censitário:** Alto ≥70 / Médio-alto 50–70 / Médio 30–50 / Baixo <30
  (cores via `RESIDUAL_SCORE_BANDS`/`score_band_to_color`).
- **D6 — pins Ultra/concorrentes:** recorte pela divisa REAL do município (malha IBGE,
  `carregar_poligono_municipio`, BLK-RELMUN-05) e, sem ela, por H3 res-7 (pin cai num `hex_id` do município; reusa `hex_id_res7` quando presente, senão deriva via `h3`) — `filtrar_pins_do_municipio`. Anti-PII: só `rede`/contagem.
- **D7 — redação das zonas:** 1 Âncora central / 2 Flancos laterais / 3 Cerco.
- **D8 — Página 11:** breakdown só das redes de concorrentes realmente mapeadas + carimbo de versão
  do contrato (`VERSAO_CONTRATO_MUNICIPAL`) no `/Info` do PDF, não no rodapé (emenda da DEC-005).
- **D9 — Página 9 (bairros) IMPLEMENTADA (BLK-RELMUN-02):** lista os bairros REAIS agrupados pelas
  3 zonas geométricas (Âncora central / Flancos laterais / Cerco), fonte **bairro do CNEFE 2022 por setor** (DEC-076), com o IBGE Censo 2022
  `NM_BAIRRO` → subdistrito → distrito como reserva (coluna `nome_bairro` agora materializada em
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
