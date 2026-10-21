/**
 * Ordem de empilhamento do Mapa Territorial (z-index), num lugar so' para ser testada.
 *
 *   corpo 10 < janelas 26/27 < pecas soltas do ponto 28 < CABECALHO 29
 *     < Metodologia 30 (e tooltips do mapa 30/31) < hero da tela vazia 40 < modais 100
 *
 * O cabecalho e o corpo (painel da camada + rodape) sao irmaos `position: relative`. Com o
 * MESMO z-index, o que vem depois no HTML -- o corpo -- pinta por cima de TUDO que esta'
 * dentro do cabecalho, inclusive a lista aberta de um seletor (o `zIndex: 40` dela fica
 * preso no contexto do cabecalho, que o `backdropFilter` e o proprio z criam). Em tela
 * estreita o painel "Potencial socioeconomico" comeca embaixo do seletor UNIDADES e cobria
 * a lista (Juan, 14/10).
 */
export const Z_CORPO_MAPA = 10
/**
 * O CABECALHO (UF, municipio, busca, UNIDADES) fica ACIMA das janelas e das pecas soltas do
 * ponto (pedido do Vinicius, 21/10/2026: "as outras abas acabam ficando por cima dele,
 * dificultando pra trocar estado / municipio"). Ate' entao ele era o z 11, um degrau acima
 * do corpo e ABAIXO das janelas: uma ficha arrastada para o topo cobria os seletores, e a
 * lista aberta de um deles -- presa no contexto do cabecalho -- descia por baixo da ficha.
 * Com 29, tudo o que esta' dentro dele, a lista aberta inclusive, pinta por cima de
 * qualquer janela.
 *
 * E ABAIXO de 30, de proposito:
 *  - a gaveta da Metodologia (`Z_GAVETA_METODOLOGIA`) existe para cobrir o chrome do mapa
 *    pela direita, cabecalho incluido; ela tem o proprio x e fecha no Esc;
 *  - os tooltips do `HexMap` (30/31) sao transitorios, nao recebem o mouse e seguem o
 *    cursor -- um tooltip de hexagono perto do topo continua legivel por cima da barra.
 *
 * A janela nao sobe alem da borda de baixo do cabecalho (`topoMinimoSobCabecalho` em
 * `lib/janela`): por cima dela, a barra de titulo -- a unica alca -- ficaria sem volta.
 */
export const Z_CABECALHO_MAPA = 29
/** as janelas de ficha (unidade, hexagono, comparacao, imovel E ponto) -- `JanelaFicha` */
export const Z_JANELA_FICHA = 26
/** a janela no TOPO da pilha (a aberta ou clicada por ultimo) sobe um degrau */
export const Z_JANELA_FICHA_TOPO = 27
/**
 * As pecas SOLTAS do modo de ponto (caixa de colar, espera e erro da leitura, botao "Ver a
 * ficha"): acima de qualquer janela, abaixo do cabecalho do mapa (29) e das camadas de 30+
 * (Metodologia, tooltips do mapa). Abaixo do cabecalho porque nascem logo abaixo dele e
 * nunca deveriam cobri-lo: a caixa de colar e o botao medem a borda de baixo dele.
 * Precisam de z proprio porque o conteiner do ponto deixou de ter um (ver `PontoScreen`):
 * sem ele cairiam sob o corpo do mapa.
 */
export const Z_FLUTUANTE_PONTO = 28
/** A gaveta da Metodologia (`MethodologyPanel`): cobre o chrome do mapa, cabecalho incluido. */
export const Z_GAVETA_METODOLOGIA = 30
