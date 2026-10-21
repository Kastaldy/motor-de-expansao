/**
 * Ordem de empilhamento do Mapa Territorial (z-index), num lugar so' para ser testada.
 *
 * O cabecalho e o corpo (painel da camada + rodape) sao irmaos `position: relative`. Com o
 * MESMO z-index, o que vem depois no HTML -- o corpo -- pinta por cima de TUDO que esta'
 * dentro do cabecalho, inclusive a lista aberta de um seletor (o `zIndex: 40` dela fica
 * preso no contexto do cabecalho). Em tela estreita o painel "Potencial socioeconomico"
 * comeca embaixo do seletor UNIDADES e cobria a lista (Juan, 14/10). Por isso o cabecalho
 * fica UM degrau acima do corpo e abaixo das janelas flutuantes.
 */
export const Z_CORPO_MAPA = 10
export const Z_CABECALHO_MAPA = 11
/** as janelas de ficha (unidade, hexagono, comparacao, imovel E ponto) -- `JanelaFicha` */
export const Z_JANELA_FICHA = 26
/** a janela no TOPO da pilha (a aberta ou clicada por ultimo) sobe um degrau */
export const Z_JANELA_FICHA_TOPO = 27
/**
 * As pecas SOLTAS do modo de ponto (caixa de colar, espera e erro da leitura, botao "Ver a
 * ficha"): acima de qualquer janela, abaixo das camadas de 30+ (Metodologia, tooltips do
 * mapa). Precisam de z proprio porque o conteiner do ponto deixou de ter um (ver
 * `PontoScreen`): sem ele cairiam sob o corpo do mapa.
 */
export const Z_FLUTUANTE_PONTO = 28
