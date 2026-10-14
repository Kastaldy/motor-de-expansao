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
