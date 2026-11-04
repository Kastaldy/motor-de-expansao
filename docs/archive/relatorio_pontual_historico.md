# Relatório Pontual Censitário — histórico

> Registro: trechos de história tirados do `docs/relatorio_pontual_censitario.md` em 03/11/2026, palavra por
> palavra, na segunda rodada da leiguificação (proposta aprovada por Vinicius, responsável pela documentação). O
> que vale hoje está no documento principal; aqui fica como o relatório chegou lá. Este arquivo só recebe acréscimo.
> Os números de linha são os da versão anterior ao corte (main `fb98c989`).

## Cabeçalho

*Trecho da linha 9:*

> Este documento foi atualizado para o raio vigente.

*Linha 18:*

> Versao: 2026-08-12 (atualizada no BLK-CONC-ESTUDO; PDF de 7 paginas base, Conclusao CONDICIONAL — +1 pagina no caminho API/bot —, gerador UNIFICADO na estetica classica).

## Parquets censitarios atuais

*Trecho da linha 83:*

> (Era 1.532.645 ate a regeneracao oficial do litoral — DEC-002/DEC-003, criterio de centroide -> OVERLAP com `M1_HEX_LAND_FRACTION_MIN=0.05`; numero corrigido aqui em 2026-07-27.)

## 3. Saidas esperadas

*Trecho da linha 102:*

> (D1, reverte a fonte da faixa do BLK-RELPON-05)

## Implementacao do Bloco 2

*Trecho da linha 135:*

> : `jobs/pipelines/*` migrou para `src/` no BLK-ARCH-01a, 2026-05-30

*Linha 145:*

Validacao real executada no DF: 5.418 setores, 1 arquivo, 3,46 MB, ~35s, 97,16% de cobertura de renda/score. Relatorio em `data/reports/relatorio_pontual_censitario_base_geo.md`.

## 6. Mapa do relatorio (camadas combinadas + fundo de ruas)

*Trecho da linha 178:*

> Criado no ciclo BLK-CENSO-01 (DEC-004) e ampliado depois por BLK-CENSO-03/-FU5, BLK-RELPON-06, renda domiciliar (PR #126) e BLK-RELPON-10/-FU1 (`socioeconomia`/`residual`). A camada `entorno` (mapa de quadra do BLK-RELPON-11) foi REMOVIDA por completo no BLK-RELPON-14.

*Trecho da linha 182:*

> (único desde o BLK-RELPON-14)

*Trecho da linha 200:*

> — **NAO** mais uma pagina por camada (o BLK-RELPON-01 consolidou os choropleths)

*Trecho da linha 205:*

> `competitors._render_pin_tile` (balao teardrop 128x128) segue INTOCADO servindo `build_icon_atlas` (`anchorY=122`; o mapa interativo pydeck que o consumia saiu com o Streamlit — DEC-022, 2026-08-03).

*Trecho da linha 211:*

> Tamanho do titulo aumentado no BLK-RELPON-06 (ver abaixo).

*Trecho da linha 212:*

> `_map_box`/`legend_x`/largura da coluna foram REABERTOS e ampliados pelo BLK-RELPON-06 (ver abaixo) para acomodar as fontes maiores.

*Trecho da linha 217:*

> o texto dos mapas estava quebrado em producao (dashboard **e** PDF): `_font()` chamava `ImageFont.truetype("arial.ttf", size)` e caia em `ImageFont.load_default()` **sem** `size` no `OSError` -- em qualquer imagem sem `arial.ttf` (e a `python:3.11-slim` do dashboard, `Dockerfile.streamlit`, não tinha NENHUMA fonte TrueType instalada) isso significava um bitmap fixo ~10px que IGNORAVA o `size` pedido (`_font(20)` e `_font(60)` renderizavam IGUAL). Fix:

*Trecho da linha 217:*

> desde 2026-10-20 e pinava `12.3.0` quando o bloco entrou

*Trecho da linha 217:*

> , ao custo de mudar o visual local (Arial -> fonte embutida) e quebrar de proposito a byte-identidade dos PNGs vs. o estado anterior

*Trecho da linha 217:*

> ; em 2026-07-14 servia o dashboard Streamlit (tela e PDF, aposentado pela DEC-022) e a API -- o piloto web só nasceu em 2026-07-20

## 7. Export CSV e PDF

*Trecho da linha 237:*

> gate humano de Felipe em 2026-06-05 aprovou trocar o writer manual PDF-1.4 por `fpdf2`,

*Trecho da linha 237:*

> em vez de A4 retrato (a capa 16:9 do `.pptx` deixou de distorcer e o titulo foi para a zona limpa inferior-direita, sem colidir com o logo "GRUPO ULTRA" embutido)

*Trecho da linha 237:*

> no lugar do `score_oportunidade_residual`

*Trecho da linha 240:*

> **INALTERADO** neste ciclo.

*Trecho da linha 241:*

> ; **BLK-RELPON-01** consolidou os 3 choropleths em 1 slide; **BLK-RELPON-07** inseriu "Perfil do Bairro/Distrito"; **BLK-RELPON-10** inseriu o slide-hero "Socioeconomia e Residual Fitness"; **BLK-RELPON-11** inseriu "Imagem do Entorno" e **BLK-RELPON-14** a REMOVEU

*Trecho da linha 241:*

> — ja o default de producao no dashboard, na API e no bot — venceu e

*Trecho da linha 241:*

> As funcoes de pagina exclusivas do template "recente" (`_cover_page`, `_socioeconomia_residual_page`, `_mapas_calor_page`, `_competitors_page`, `_perfil_bairro_page`, `_credit_page` e `_entorno_page`) foram DELETADAS; as compartilhadas (`_big_numbers_page`, `_viabilidade_page`, `_fotos_imovel_page`, `_info_imovel_page`) permanecem:

*Trecho da linha 243:*

> ; **socioeconomia revista no BLK-RELPON-13, gate Vinicius 2026-07-23; representacao do raio revista no BLK-RELPON-14**

*Trecho da linha 244:*

> (BLK-RELPON-01 consolidou a tira 1x3; a 4a camada entrou com a renda media domiciliar, PR #126)

*Trecho da linha 244:*

> — restaurado COM legenda no BLK-CENSO-03-FU5 —

*Trecho da linha 248:*

> , no lugar da nota READ-ONLY desde 2026-08-19

*Trecho da linha 250:*

> , titulo renomeado em 2026-08-19

*Trecho da linha 262:*

> ; o `render_downloads_relatorio_censitario` saiu com o Streamlit, DEC-022

*Trecho da linha 263:*

> **Nota de escopo (historico do BLK-RELPON-07):** na epoca, `src/motor_expansao/api/service.py` (endpoint `POST /analisar` com `formato=pdf`, DEC-005) chamava `gerar_pdf_relatorio_pontual_classico` DIRETAMENTE, sem passar `perfil_bairro` -- FORA do escopo daquele bloco: o PDF da API ganhou a pagina nova automaticamente (contagem 5->6 tambem la), mas com os 4 cards em "n/d". **Isso ja nao vale:**

*Trecho da linha 263:*

> — era k=5, 91 hexes —

*Trecho da linha 263:*

> As diferencas de render acabaram:

*Trecho da linha 263:*

> ; o expander do Mapa Territorial e o outro caminho de download eram do Streamlit (DEC-022)

*Trecho da linha 264:*

> ; ate' entao eram a linha do hexagono res-7 do ponto (`_residual_do_ponto`) e o card de consumo mostrava so' a parcela de concorrentes, escondendo o termo da Ultra que o residual descontava

*Trecho da linha 264:*

> `score_setor_max` (antigo card "Score censitario maximo") SAIU do PDF a partir do BLK-RELPON-08 e `score_setor_medio` (antigo card "Score censitario medio") SAIU em 2026-07-17, cedendo o 4o card da linha 1 a renda media domiciliar -- os dois continuam calculados em `result` para auditoria em CSV, so nao aparecem mais como card.

*Trecho da linha 265:*

> o par `render_downloads_relatorio_censitario(...)`, que desenhava os botoes `st.download_button`, saiu com o Streamlit — DEC-022;

*Trecho da linha 265:*

> — quando havia chamador de producao (o Streamlit), ele usava `template="classico"`

*Trecho da linha 274:*

> adotar `fpdf2` exige rebuild da imagem Docker + redeploy por digest na VPS;

*Linha 276:*

**Consolidacao BLK-RELPON-01 (gate humano Vinicius 2026-07-01):** os 3 choropleths (Populacao/Renda/Score) — antes 1 pagina cada — foram consolidados em **UM slide "Mapas de calor"** (tira 1x3 lado a lado, sem sobreposicao, cada PNG embutido separadamente com sua legenda), levando o PDF de **7->5 paginas** (Capa->Mapas de calor->Concorrentes->Big Numbers->Realizacao), `/Count 7`->`/Count 5`, `PDF_SECTION_HEADERS` de 7->5 strings. Feito nas duas variantes (`censitario` e `classico`). READ-ONLY sobre o M1; metodo de intersecao/raio de entao (1,5 km)/score/artefatos oficiais INTOCADOS. Helpers `_map_page`/`_classico_map_page`/`_draw_map`/`_classico_draw_map` removidos (substituidos por `_mapas_calor_page`/`_classico_mapas_calor_page` + `_draw_maps_grid`/`_classico_draw_maps_grid` + `_map_grid_cells`).

*Linha 278:*

**Insercao BLK-RELPON-07 (2026-07-15):** a pagina "Perfil do Bairro/Distrito" foi inserida entre Concorrentes e Big Numbers, levando o PDF de **5->6 paginas** (Capa->Mapas de calor->Concorrentes->Perfil do Bairro/Distrito->Big Numbers->Realizacao), `/Count 5`->`/Count 6`, `PDF_SECTION_HEADERS` de 5->6 strings. Feito nas duas variantes. Consequencia aceita da alternancia de tema por ordinal (`_tema_bicolor`): a cor de destaque da pagina Big Numbers muda de turquesa para magenta (era o 3o slide de conteudo, passa a ser o 4o); a nova pagina Perfil do Bairro/Distrito herda o turquesa que antes era de Big Numbers. Ver secao dedicada acima (§7 topo) para o contrato completo da pagina nova.

*Linha 280:*

**Insercao BLK-RELPON-10 (gate Vinicius 2026-07-21):** o slide-hero "Socioeconomia e Residual Fitness" foi inserido ANTES de "Mapas de calor", levando o PDF de **6->7 paginas**, `/Count 6`->`/Count 7`, `PDF_SECTION_HEADERS` de 6->7 strings. Feito nas duas variantes. 2 mapas lado a lado via `_draw_maps_grid` generalizado com `cols`/`rows` KEYWORD-ONLY (default 2x2 preservado -> o caminho de "Mapas de calor" ficou byte-identico): `socioeconomia` = MESMO choropleth de `score_setor_2022_calibrado` no raio do relatorio (1,5 km a epoca) (o `score` PERMANECE no grid 2x2, S1=A do gate) e `residual` = `oferta_efetiva_disponivel` em ALUNOS por hexagono H3 res-7 no raio de EXIBICAO de 5 km (S2=B do gate; emenda a DEC-011, que limitava o residual a NUMERO nos Big Numbers). O slide usa `_tema_bicolor(0)` (magenta) e NAO inverte a cor das paginas ja existentes (ordinais decrescentes a partir de 0 para paginas inseridas antes das 4 paginas de conteudo historicas). **BLK-RELPON-10-FU1 (2026-07-22):** a camada Residual deixou de desenhar pins de concorrentes/Ultra e a legenda de pins (a 5 km a area e ~11x a do raio do relatorio e os logos tapavam o choropleth). Motor censitario (`setor_censitario_intersecao_area_1p5km`, raio 1,5 km a epoca) INTOCADO. **O BLK-RELPON-14 preservou o VALOR de 5 km** (`RAIO_RESIDUAL_DISPLAY_KM`, enquadramento) e removeu apenas a sua REPRESENTACAO — circulo e rotulo — ver abaixo.

*Linha 282:*

**Insercao BLK-RELPON-11 (caminho A1, gate Vinicius 2026-07-22) — REVERTIDA pelo BLK-RELPON-14:** a pagina "Imagem do Entorno" foi inserida entre a Capa e o slide-hero, levando o PDF de **7->8 paginas**, e saiu por completo em 2026-07-28 (ver abaixo). Enquanto existiu: grid 1x1 empacotado com a camada `entorno`, tema `_tema_bicolor(-1)` = turquesa (`-1 % 2 == 1` em Python), nas duas variantes (`_entorno_page`/`_classico_entorno_page`).

*Linhas 284–288:*

**Remocao + unificacao BLK-RELPON-14 (2026-07-28):**
- **Slide "Imagem do Entorno" REMOVIDO por completo** — pagina do PDF, camada PNG `entorno`, constantes orfas (`RAIO_ENTORNO_DISPLAY_KM`, `_ENTORNO_VALOR_LINHA`, o parametro `rotulo_escala` de `_render_camada` e o override local de `zoom_bump`) e a chave `entorno` de `CAMADAS_CENSITARIAS`/`MAP_LAYER_TITLES`. O PDF volta de **8->7 paginas** (Capa->Socioeconomia e Residual Fitness->Mapas de calor->Concorrentes->Perfil do Bairro/Distrito->Big Numbers->Realizacao), `/Count 8`->`/Count 7`, `PDF_SECTION_HEADERS` de 8->7 strings, e o teto com as opcionais cai de **12->11** (`/Count 11`). Os ordinais de `_tema_bicolor` sao ABSOLUTOS (nao um contador incremental), entao liberar o `-1` que so servia a essa pagina **nao desloca cor nenhuma**: hero=magenta, mapas=turquesa, concorrentes=magenta, perfil=turquesa, big numbers=magenta, exatamente como antes.
- **Gerador UNIFICADO na estetica classica** — `gerar_pdf_relatorio_pontual_classico` e a implementacao unica; `gerar_pdf_relatorio_pontual_censitario` vira wrapper fino com `DeprecationWarning`. As paginas duplicadas do template "recente" (`_cover_page`, `_socioeconomia_residual_page`, `_mapas_calor_page`, `_competitors_page`, `_perfil_bairro_page`, `_credit_page`, `_entorno_page`) foram DELETADAS; `_big_numbers_page`, `_viabilidade_page`, `_fotos_imovel_page` e `_info_imovel_page` (compartilhadas desde sempre) FICAM.
- **Representacao do raio nos paineis de 5 km** — `RAIO_RESIDUAL_DISPLAY_KM = 5.0` **NAO MUDA** (segue definindo o ENQUADRAMENTO dos dois paineis; encolher reintroduziria o mosaico chapado que a DEC-011 documenta). O que saiu foi a REPRESENTACAO: circulo azul e rotulo "Raio X km" removidos, e o hexagono H3 res-7 que CONTEM o ponto ganhou uma borda fina de destaque. Ver §6 e a emenda de 2026-07-28 na DEC-011.
- Motor censitario (`setor_censitario_intersecao_area_1p5km`, raio 1,5 km a epoca), score e artefatos oficiais do M1 INTOCADOS — e mudanca de RENDER/estrutura de relatorio (§5 guardrail permanente).

*Linha 290:*

**Correcao BLK-RELPON-13 (gate visual Vinicius 2026-07-23):** o painel `socioeconomia` do slide-hero deixou de ser o choropleth de setores a 1,5 km e passou a ser `score_setor_2022_calibrado` por **hexagono H3 res-7 num enquadramento de 5 km** (disco `h3.grid_disk` k=5, clip ao frame) — a MESMA metrica e a MESMA paleta (`score_band_to_color`, 0-100) do `score` do grid 2x2, mudando so a geometria/escala para casar com o `residual` ao lado. Implementado GENERALIZANDO o caminho do `residual` (`_render_camada_residual_hex`/`_hex_polygons_3857`/`_residual_hex_central` ganharam parametros keyword-only DEFAULT-PRESERVING para `value_col`/titulo/legenda/cor/valor central -> o `residual` fica byte-a-byte igual). Consequencia: `socioeconomia` virou **CONDICIONAL** como o `residual` (sem `hexes_df`/coluna/hex desenhavel -> chave ausente + fallback textual; SEM pins), e a faixa superior passou a usar `_legenda_valor_hex` ("Score no hexagono: NN"). As 2 imagens do slide sao reduzidas por `_HERO_MAP_SCALE` (constante de RENDER de `censo_report.py`, **0.85**, calibrada por Vinicius no gate visual de 2026-07-24 -- partiu de 0.92; so as paginas socioeconomia+residual a aplicam via `packed_scale` do `_draw_maps_grid`/`_map_grid_cells_packed`). `/Count 8`, as 8 chaves de `CAMADAS_CENSITARIAS` e as demais 7 camadas seguiam byte-identicas (numeros da epoca; hoje sao 7 paginas e 7 chaves — BLK-RELPON-14). Feito nas duas variantes. READ-ONLY sobre o M1: `score_setor_2022_calibrado` e apenas LIDO do `hexes_df`; motor censitario (`setor_censitario_intersecao_area_1km`; raio 1,5 km a epoca, hoje 1,0 km — DEC-021) INTOCADO.

*Trecho da linha 292:*

> (a contagem de paginas/ordem foi atualizada depois por BLK-RELPON-01, -07, -10, -11 e -14, acima; hoje sao 7 paginas)

*Trecho da linha 294:*

> ; era `y+88` no card de 156

*Trecho da linha 295:*

> ; baixado de 6.200 por Vinicius no gate visual de 2026-07-24

*Trecho da linha 295:*

> desde a remocao do "Score censitario medio" em 2026-07-17

*Trecho da linha 295:*

> era "Consumo instalado (conc. + Ultra)" ate 2026-10-16;

*Trecho da linha 295:*

> ; antes era "Consumo concorrentes (est.)", so a parcela dos concorrentes

*Trecho da linha 295:*

> ; os cards "Score censitario maximo" (BLK-RELPON-08) e "Score censitario medio" (2026-07-17) SAIRAM do PDF (campos `score_setor_max`/`score_setor_medio` continuam em `result`/CSV)

*Trecho da linha 297:*

> ; blocos de texto subidos. Nota READ-ONLY e atribuicao de tiles mantidas

*Trecho da linha 301:*

> A pagina nasceu em 2026-08-06 compondo num status UNICO os tres juizos dispersos que o repo tinha (semaforo por METRICA dos Big Numbers, veredito BINARIO `dre.flag_viavel`, parecer tri-estado de `rede_diagnostico` apontado para unidade MADURA). Esse status unico **acabou**:

*Trecho da linha 305:*

> **Ate' a DEC-042 (2026-08-28) este gate NUNCA disparava** no piloto: `_payload_viabilidade` chamava o motor sem `setores_df`, o catchment nao rodava e `flag_zona_morta` saia `None` em 100% das requisicoes. A mesma DEC derrubou o piso de renda de 1.600 para 500, porque no valor antigo o gate reprovava 46,3% da propria rede Ultra — 12 das vetadas operando ACIMA da mediana.

*Trecho da linha 305:*

> **R6** e' o unico item que mudou de casa por arrumacao, nao por semantica: saiu de `_avaliar_conclusao` para o fim de `_conclusao_eixo_financeiro`, que e' a mesma posicao relativa na ordem de leitura.

*Trecho da linha 306:*

> `PE_DIREITO_MIN` chegou a ser gate eliminatorio na primeira versao (era a estreia da constante, ate entao nunca comparada com nada) e foi RETIRADO:

*Trecho da linha 307:*

> — antes o status unico o carimbava REPROVADO e a leitura da praca sumia junto

*Trecho da linha 308:*

> , que reverteu a proposta original

*Linha 309:*

- **Primeira aplicacao real de `AREA_MIN_M2` / `AREA_IDEAL_MIN_M2` / `AREA_IDEAL_MAX_M2` / `PE_DIREITO_MIN`.** Eram canonicos declarados em `config.py` e travados em `tests/contracts/test_parametros_canonicos.py`, mas **nao comparados com nada em lugar nenhum** — o pe-direito era so um campo digitado e impresso. Sao os unicos parametros do `config.py` que a pagina le; nada do M1 e tocado.

*Trecho da linha 313:*

> , era 240

*Trecho da linha 313:*

> , era 622

*Trecho da linha 313:*

> — foi essa derivacao que absorveu, sozinha, o estreitamento da coluna direita

*Trecho da linha 313:*

> O que a direita perde, a esquerda ganha, e e' ela que precisa: passou a comportar DOIS titulos de bloco alem dos cards.

*Trecho da linha 313:*

> O card de status em largura total que existia antes SAIU, e com ele o dicionario `_CONCLUSAO_LABELS` ("Aprovado com ressalvas" etc.):

*Trecho da linha 315:*

> — antes tudo nascia colado no topo e sobrava um vazio grande embaixo em quase todo relatorio

*Trecho da linha 317:*

> Defeito encontrado na revisao visual do proprio bloco: preenchendo a coluna na ordem, um ponto ruim em tudo (10 apontamentos para ~6 vagas) a enchia inteira com o bloco demografico e o bloco financeiro **nao entrava — nem o titulo**. O selo financeiro ficava carimbado REPROVADO ao lado de uma coluna que nao trazia UMA linha sobre o financeiro: e' o "reprova, mas nunca em silencio" prometido desde 2026-08-06, quebrado pela unica via que a lista unica nao tinha, a truncagem.

*Trecho da linha 318:*

> : com uma altura so o teste passava mesmo com a correcao removida (para muitas alturas a reserva e' no-op),

*Trecho da linha 320:*

> e saia **"Aprovado"** com o texto de confirmacao AFIRMANDO que atendia "as metas censitarias do raio" — que nunca foram avaliadas

*Trecho da linha 322:*

> , entao o caso MAIS grave era o unico que nunca traduzia e saia `"pop<5000; renda<500"` cru no PDF

*Trecho da linha 323:*

> : um `flag_zona_morta` corrompido REPROVAVA o ponto, contra o invariante declarado no proprio cabecalho da secao

*Trecho da linha 325:*

> (era 240x196 quando havia um so)

*Trecho da linha 326:*

> unico acrescimo a anatomia de 2026-08-07, e obrigatorio:

*Trecho da linha 328:*

> Sairam `_CONCLUSAO_SELO_APOIO_OCULTO_NO_ESTUDO` e o ramo `0.55`/`0.62` do rotulo (todo estado tem apoio agora).

*Trecho da linha 329:*

> (a redacao anterior desta linha afirmava que as duas eram, e a revisao adversarial do bloco mostrou que nao)

*Trecho da linha 329:*

> (Registro, porque a justificativa anterior citava um numero errado: com a geometria antiga em 176 o simbolo **nao** termina a ~5 pt do rotulo — o gap real seria 18,85 pt no pior caso, o "!" do estado intermediario, e 28,16 pt no check.)

*Trecho da linha 333:*

> Ate 2026-08-12 valia so `if viabilidade:`, o que deixava a **API e o bot Telegram** (que então não mandavam `viabilidade`; ver `api/service.py`) sem parecer nenhum.

*Trecho da linha 333:*

> (escopo fechado por Juan em 2026-08-12)

*Trecho da linha 334:*

> Byte-a-byte o de antes.

*Trecho da linha 335:*

> -- do hexagono ate' a DEC-070 --

*Trecho da linha 336:*

> Ate aqui nenhum criterio da praca era eliminatorio, e o parecer da API/bot parava sempre em `com_ressalvas`. O E5 fecha isso:

*Trecho da linha 337:*

> Nasceu preso ao so-estudo (escopo fechado por Juan em 2026-08-12: "a mudanca e' do PDF do bot, e so dele"), e a divergencia que isso criava era declarada e ACEITA — um ponto com 4+ metas vermelhas e financeiro bom saia `reprovado` no PDF do bot e `com_ressalvas` no do piloto. **O que mudou nao foi o corte, foi o que a divergencia significa:** enquanto o parecer era um veredito unico, ela ficava diluida num status que misturava praca e financeiro; com o selo demografico proprio, o MESMO ponto passa a exibir um carimbo de cor diferente em dois documentos, e a leitura da praca nao pode depender de por qual porta o relatorio saiu. **Custo medido antes de estender:** os 5 pontos do golden do Recife falham no maximo **1** meta contra corte **4** — a calibracao de Vinicius nao se move (era exatamente o que `test_e5_nao_desloca_o_golden_do_recife` existia para garantir). O corte **nao foi remedido nem alterado**; so o escopo.

*Trecho da linha 340:*

> (nasceu como 2a linha de defesa, quando o E5 ainda era so do so-estudo)

*Trecho da linha 342:*

> — o golden original era, na pratica, um golden desse eixo: os 5 reprovam e ressalvam por metragem, aluguel e retorno

*Trecho da linha 342:*

> Ou seja, a DEC-030 **nao reabriu a calibracao** — mostrou de onde vinham os vereditos.

*Linha 345:*

Validacao minima: `tests/unit/test_relatorio_pontual_censitario_export.py` cobre bytes CSV/PDF, os **7** headers de secao, `/Count 7`, as imagens de mapa embutidas no PDF (**socioeconomia/residual + os 4 choropleths do grid 2x2 "Mapas de calor" + a de Concorrentes so-pins**, separadamente e nao pre-compostas, via `/Subtype /Image >= 5`), Big Numbers com/sem residual (sem ele, `TEXTO_SEM_DADO`, "Não disponível"; a sigla "n/d" saiu dos Big Numbers em 2026-07-31 e `test_pdf_nao_contem_a_sigla_nd_em_lugar_nenhum` impede que ela volte ao PDF de base — ele gera o PDF mínimo, sem as páginas opcionais), fallback offline sem assets, anti-PII, atribuicao de tiles, retrocompat de `bytes` unico e helper de download; os testes `test_pdf_concorrentes_contagem_total_e_mais_n_quando_excede_10` e `test_pdf_concorrentes_sem_contagem_quando_ate_10` cobrem o cabecalho/contagem D4=B do BLK-EST-02 (sem PII). **BLK-RELPON-01** adiciona `test_slide_unico_quatro_mapas_sem_sobreposicao` (bounding boxes das celulas do grid, recente + classico), o assert de `/Count` + titulo do slide "Mapas de calor" (o nome desse teste carrega a contagem vigente de paginas), `test_slide_unico_offline_safe_por_camada` e `test_slide_unico_quatro_imagens_embutidas`. **BLK-RELPON-05** nao muda logica em `censo_report.py` (a faixa ja vem "assada" nos PNGs recebidos como `mapas: dict[str, bytes]`); `test_pdf_estrutura_inalterada_com_faixa_valor_ponto_blk_relpon_05` reforca que a contagem de paginas, a de imagens e os headers permanecem identicos. **BLK-RELPON-07** adiciona `test_perfil_bairro_page_presente_com_4_metricas_recente`, `test_perfil_bairro_page_nd_quando_perfil_bairro_none` e `test_classico_perfil_bairro_page_presente_e_nd` (nova pagina "Perfil do Bairro/Distrito", com/sem `perfil_bairro`); em `tests/unit/test_relatorio_pontual_censitario_motor.py`, `test_lookup_bairro_ponto_quando_setor_tem_bairro`, `test_lookup_distrito_ponto_fallback_quando_bairro_ausente` e os testes de `agregar_perfil_bairro_distrito` (agregacao, fallback, exclusao simetrica de renda, "n/d" sem identificador/DataFrame vazio) cobrem o motor novo. **BLK-RELPON-10** adiciona o slide-hero (presenca, `offline-safe` sem a camada residual, `_tema_bicolor` ordinal 0 = magenta sem mexer nos existentes, `MAP_LAYER_TITLES` com as chaves novas e o grid aceitando 2x1/1x1 com default 2x2). **BLK-RELPON-11** adicionou a bateria da pagina "Imagem do Entorno", **REMOVIDA** no BLK-RELPON-14 junto com a pagina. **BLK-RELPON-14** atualiza os asserts de estrutura para `/Count 7` + 7 headers e a marca d'agua para `>= 7`, e cobre: a ausencia do header "Imagem do Entorno" e da chave `entorno` (descartada em silencio por `_normalize_mapas` quando alguem ainda a passa), a equivalencia entre o wrapper depreciado e a classica (mesmos bytes e mesmo numero de paginas + `DeprecationWarning` emitido) e os dois ramos de `template` produzindo o mesmo PDF. Com as opcionais que `tests/unit/test_relatorio_pontual_viabilidade.py` e `tests/unit/test_relatorio_pontual_orquestracao.py` montam — fotos, dados do imóvel, Viabilidade (números e gráficos) e Conclusão, sobre as 7 de base — o PDF tem **12 páginas** (era 11 antes da página de Conclusão), travado nos dois (`/Count 12`). O teto real é maior: as duas páginas da praça (desde 2026-09-17) e a vista aérea (BLK-SAT) ficam fora dessa conta, e com elas o PDF chega a **15** (medido em 2026-10-29), total que nenhum teste trava. A **pagina de Conclusao** tem bateria propria em `tests/unit/test_relatorio_pontual_conclusao.py` (**130 casos** em 2026-10-29; eram 125 logo após a DEC-030, em 2026-08-14): um por gate com as bordas inclusivas (`>=` meta, teto exato, faixa ideal), os invariantes "indecidivel nunca reprova" e "zero numero de faturamento" (por valores-sentinela), a insercao no PDF com a Realizacao permanecendo a ultima pagina e o golden dos 5 pontos do Recife. **DEC-030** nao mexeu em nenhum assert de estrutura (a pagina segue UMA, entao os `/Count` de todos os arquivos vizinhos ficaram intactos), mas cada teste de gate passou a assertar o status do EIXO que aquele gate alimenta — e' isso que prova a particao: um gate financeiro que sujasse o selo demografico (ou o contrario) quebra ali, mesmo que o apontamento saia escrito na pagina do mesmo jeito. Acrescentou: ausencia de status agregado, `financeiro is None` no so-estudo, zona morta reprovando a praca e nao o financeiro, os dois selos carimbando eixos independentes nos bytes (pelas linhas de apoio, unicas por eixo+estado), legendas e titulos de bloco no PDF, a truncagem repartida entre blocos (com o caso de 10 apontamentos que expos o defeito), a guarda de altura dos dois selos e a equivalencia da geometria interna na altura de referencia. Fechou tambem um **buraco de cobertura anterior**: `test_relatorio_acentuacao_regressao` gera os PDFs sem `viabilidade` e sem `conclusao_so_estudo`, entao a pagina de Conclusao nunca e' renderizada la, e o teste de latin-1 daqui so percorria eliminatorios/ressalvas — os **rotulos do selo nao eram auditados por ninguem**; agora sao (`test_textos_de_exibicao_do_selo_nao_usam_caractere_fora_de_latin1`).

*Linha 347:*

**Cinco testes da propria DEC-030 foram reescritos apos revisao adversarial**, por nao travarem o que a docstring prometia — e a correcao de cada um foi provada por MUTACAO (patch em runtime, repo intocado): o teste tem de derrubar a quebra que ele existe para pegar. Os casos, porque a classe de defeito se repete: (a) `test_legendas_identificam_os_dois_selos_no_pdf` era tautologico — `DEMOGRÁFICO`/`FINANCEIRO` tambem saem da NOTA metodologica na mesma pagina, entao apagar as duas legendas dos selos deixava a suite verde; passou a assertar CONTAGEM (2 de cada = selo + nota); (b) `_ConclusaoElemento.altura` nao era confrontada com o avanco que `_conclusao_page` faz por conta propria — devolver so `altura_card` orcava 62 pt a menos e a suite nao via; (c) `_conclusao_elementos` nao tinha teste, e `titulo_offset=0.0` apagava na pratica o `_CONCLUSAO_BLOCO_GAP`; (d) o rotulo principal do selo FINANCEIRO nao tinha cobertura, porque no PDF inteiro `APROVADO` ja vinha do selo demografico — virou golden LITERAL com o selo renderizado isolado (`_bytes_do_selo`), depois de a primeira correcao falhar pelo mesmo defeito que corrigia: ela lia o rotulo esperado do dicionario que a mutacao alterava; (e) `test_eixo_demografico_nao_herda_o_veredito_do_cenario` era um `> 0` que sobrevivia a reunificacao PARCIAL dos eixos (concatenar so os eliminatorios financeiros deixava 144 dos 384 cenarios ainda aprovados) — passou a exigir DISJUNCAO dos apontamentos nos 4.096 cenarios. `test_truncagem_reparte_o_espaco_entre_os_blocos` tambem so verificava o prefixo do 1o bloco, e agora verifica os dois. **BLK-CONC-ESTUDO** NAO mexeu em nenhum assert de estrutura dos testes existentes — o default do gerador ficou intocado, e por isso `/Count 7` e os 7 headers seguem valendo. Acrescentou: `test_sem_viabilidade_e_sem_flag_nao_ha_pagina_de_conclusao` (o caminho do piloto web, provando que 7 paginas continuam 7), `test_sem_viabilidade_com_flag_a_pagina_entra_em_modo_so_estudo` (o caminho API/bot), `test_flag_e_inerte_quando_ha_viabilidade` (bytes IDENTICOS com e sem o flag quando o payload existe) e a bateria do modo so-estudo: gates de imovel/retorno desligados em bloco, metas censitarias e mercado preservados, ausencia dos cards de aluguel, nota metodologica propria, selo sem "PARA COMITÊ" (contra `test_com_viabilidade_...`, que prova a manutencao no modo completo) e o gate **E5** (bordas 0/1/2/3 nao reprovam, 4 reprova, contagem sobre a lista crua, constante de total batendo com a funcao real, valendo nos DOIS modos desde a emenda de 2026-08-14 (`test_e5_vale_nos_dois_modos`, que inverteu o antigo `test_e5_nao_vale_no_modo_completo`) e o golden do Recife intocado).

## Mercado no raio (DEC-070, 2026-10-14)

*Linha 351:*

Caso que abriu a decisao (Santana/SP, `-23,48516 / -46,61771`, a 9 m da Ultra Santana): o PDF mostrava SAM 12.038 e consumo de concorrentes 9.170, e o residual saia **0**. Nao era erro de conta, era leitura: os tres numeros vinham do HEXAGONO res-7 do ponto (5,16 km2, centroide a 1.250 m), ao lado de uma populacao do RAIO; o residual do hexagono descontava ainda **5.000 da Ultra** que nao estavam na pagina; e esses 5.000 vinham do fallback `n_unidades_ultra_2km x 2.500` do pipeline, que conta inteira a Ultra Vila Guilherme -- que ja' desconta seus alunos reais no hexagono dela (dupla contagem).

*Linha 364:*

Santana recalculado (2026-10-14, staging local): pop do raio **36.413**, SAM_raio **6.418**, concorrentes **4.865** (8 unidades, 1,95 equivalentes), Ultra **2.486** (so' a Santana; proxy de 2.500 x 0,994), consumo **7.351**, residual **0** -- contra o hexagono (SAM 12.038, conc. 9.170, Ultra 5.000, residual 0). O zero se sustenta: o ponto e' a propria Ultra e a praca esta consumida; o que muda e' que a conta agora FECHA na pagina.

## Paginas da praca (piloto web, 2026-09-17)

*Trecho da linha 370:*

> Pedido do Felipe (2026-09-10): o relatorio saia generico, com pouco do que o motor sabe da cidade.

*Trecho da linha 372:*

> ; ate entao `RAIO_INFLUENCIA_M`, 1 km

## Implementacao do Bloco 6

*Linha 381:*

Na epoca (dashboard Streamlit, aposentado pela DEC-022), o fluxo visual foi integrado ao dashboard em `render_relatorio_pontual_censitario`, dentro do expander `Relatorio Pontual Censitario` na aba `Mapa Territorial`: reutilizava a coordenada ativa do clique no mapa ou da busca da sidebar, mantinha raio fixo `1.0 km`, exibia KPIs, as 4 imagens censitarias em grade 2x2 (densidade/renda/score/concorrentes) SEM seletor de metrica, tabela de setores e botoes de download CSV/PDF (o download usava `template="classico"`). Hoje o PDF sai pelo piloto web (`POST /api/relatorio/pontual`), pela API e pelo bot.

*Trecho da linha 383:*

> (na epoca havia tambem o wrapper cacheado `load_censo_geo_setores` no `streamlit_app.py`, que saiu com o Streamlit — DEC-022)

*Trecho da linha 385:*

> Ate' aqui lia-se UMA particao — a do municipio que CONTEM o ponto — e o mapa/analise paravam na divisa municipal, ainda que o raio a atravessasse.

*Linha 387:*

Baseline simples DF/Brasilia: `5.418` setores carregados, `34` setores intersectados, leitura `~0,04s`, analise `~0,16s`, pico Python via `tracemalloc` `~6,3 MB`.

## 9. Decisao operacional

*Linhas 401–405:*

Na epoca do ciclo, o relatorio nasceu dentro do dashboard Streamlit porque:
- o produto precisava conviver com a entrada por coordenada ja existente;
- o deploy inicial continuava offline com dados locais;
- o processamento pesado podia ser amortizado por artefato GeoParquet/WKB particionado e cache;
- API/worker separado so entraria no backlog se houvesse concorrencia de usuarios, fila de PDFs, historico por usuario ou deploy independente.

*Linhas 409–416:*

## 10. Validacao do Bloco 1

Comandos executados:
- `python -c "import geopandas, shapely, pandas; print('ok')"`: passou.
- Leitura da malha com `geopandas.read_file(..., rows=1)`: passou; CRS `EPSG:4674`.
- Inventario com `pyogrio.read_info`: 468.099 features.
- Leitura de cabecalho/amostra dos CSVs Basico e Renda: passou.
- Leitura de schemas dos Parquets com `pyarrow.parquet`: passou; nenhuma coluna `geometry` detectada nos Parquets censitarios atuais.
