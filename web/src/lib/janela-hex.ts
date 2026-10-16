/**
 * Quando a janela da ficha do HEXÁGONO abre no mapa.
 *
 * O MESMO hexágono pode ficar selecionado por dois caminhos que pedem leituras diferentes
 * (decisão do dono, 2026-10-14, valendo para "Explorar uma região" e "Analisar um ponto"):
 *  - BUSCA de coordenada (lupa) ou "Selecionar ponto": a pergunta é sobre o PONTO, e a
 *    resposta é a ficha de ponto (raio de 1 km). Abrir também a ficha do hexágono por
 *    baixo dela dava duas leituras concorrentes da mesma coordenada.
 *  - CLIQUE DIRETO num hexágono: a pergunta é sobre o hexágono — abre a ficha dele, nas
 *    duas entradas.
 *
 * POR QUE UM FLAG E NÃO SÓ A COMPARAÇÃO DE hexId. Comparar `selecionado === hexDaBusca`
 * não distingue o caso em que o operador busca um ponto e DEPOIS clica no próprio hexágono
 * dele querendo a ficha do hex: o id é o mesmo nos dois momentos. Quem sabe de onde veio
 * a seleção é `selecaoDaBusca`, que a tela liga na busca e desliga no clique.
 *
 * Em `modoCenario` ("Comparar hexes") nunca abre: ali o clique soma o hexágono ao cenário
 * e quem ocupa a janela é o comparativo.
 *
 * Função PURA, para o vitest (node, só `.test.ts`) cobrir a regra sem montar a tela.
 */

export interface EstadoJanelaHex {
  /** O hexágono selecionado no mapa, ou null. */
  selecionado: string | null
  /** O hexágono do último ponto buscado/selecionado, ou null. */
  hexDaBusca: string | null
  /** A seleção atual veio da busca/"Selecionar ponto" (true) ou de um clique no hex (false)? */
  selecaoDaBusca: boolean
  /** "Comparar hexes" ligado. */
  modoCenario: boolean
}

export function janelaDoHexVisivel({
  selecionado,
  hexDaBusca,
  selecaoDaBusca,
  modoCenario,
}: EstadoJanelaHex): boolean {
  if (selecionado == null || modoCenario) return false
  // Só suprime quando a seleção É a da busca. Se o flag ficou ligado mas o hexágono
  // selecionado já é outro, a seleção não veio da busca — mostrar a ficha é o certo.
  if (selecaoDaBusca && hexDaBusca != null && selecionado === hexDaBusca) return false
  return true
}

/**
 * Em que DEGRAU nascem as janelas do mapa que vivem à ESQUERDA (a ficha do hexágono e a do
 * comparativo de hexágonos), dado quantos itens há na análise de pontos.
 *
 * Com pontos na lista a ficha de PONTO ocupa a esquerda, nas duas entradas do mapa. Mandar
 * a do hexágono para a DIREITA (a primeira correção) a punha exatamente em cima da do
 * imóvel e da unidade, que nascem lá — e por cima do painel de ranking. Em degrau ela fica
 * do lado de sempre, sem cobrir a barra de título da ficha de ponto.
 */
export function degrauSobreFichaDePonto(nPontos: number): number {
  return nPontos > 0 ? 1 : 0
}

/**
 * O ponto ativo deve (re)selecionar o hexágono dele AGORA?
 *
 * Quase sempre sim — é o que amarra o ponto ao contorno no mapa. A exceção é a REMONTAGEM
 * do mapa (volta da Viabilidade): a foto devolve a seleção que o operador tinha, e se ela
 * era de OUTRO hexágono (ele clicou num hexágono depois de analisar o ponto e foi simular
 * aquele), o efeito do ponto rodando na montagem a trocava pelo hexágono do ponto — e a
 * ficha do hexágono que ele tinha aberto sumia na volta.
 *
 * `pinDaMontagem` = o pin do ponto é o MESMO objeto que existia quando a tela montou (o
 * mesmo critério de identidade do voo no `HexMap`): um ponto NOVO depois da montagem
 * sempre seleciona.
 */
export function pontoSeleciona({
  pinDaMontagem,
  selecaoRestaurada,
  hexDoPonto,
}: {
  pinDaMontagem: boolean
  selecaoRestaurada: string | null
  hexDoPonto: string
}): boolean {
  if (!pinDaMontagem) return true
  return selecaoRestaurada == null || selecaoRestaurada === hexDoPonto
}
