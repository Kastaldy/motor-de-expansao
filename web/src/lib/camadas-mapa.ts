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
/** as janelas de ficha (unidade, hexagono, comparacao) -- `JanelaFicha` */
export const Z_JANELA_FICHA = 26
