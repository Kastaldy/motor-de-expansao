/**
 * A ferramenta ativa do trilho inferior esquerdo do mapa: UM estado só.
 *
 * POR QUE UM ESTADO SÓ. O trilho ganhou "Selecionar ponto" e "Analisar geometria" ao lado
 * da régua (decisão do dono, 2026-10-14), e as três disputam o MESMO clique no mapa: com a
 * régua ligada o clique mede, com o ponto ligado ele marca um ponto, com a geometria ele
 * põe um vértice. Três booleanos independentes deixariam ligar duas ao mesmo tempo — e
 * aí um clique faria duas coisas. Com um estado só, a exclusão mútua sai de graça.
 *
 * Funções PURAS, sem deck.gl e sem React, para o teste não precisar montar mapa (o vitest
 * roda em node e só casa `.test.ts`).
 */

export type FerramentaMapa = 'nenhuma' | 'ponto' | 'regua' | 'geometria'

/**
 * O estado depois de tocar no botão de `alvo`.
 *
 * Tocar na ferramenta que já está ligada DESLIGA (volta a 'nenhuma'); tocar em outra troca
 * — ligar a régua desliga o ponto, e vice-versa. Tocar em 'nenhuma' é sempre desligar.
 */
export function alternarFerramenta(atual: FerramentaMapa, alvo: FerramentaMapa): FerramentaMapa {
  if (alvo === 'nenhuma') return 'nenhuma'
  return atual === alvo ? 'nenhuma' : alvo
}

/**
 * O clique no mapa seleciona o hexágono?
 *
 * Só sem ferramenta. Com qualquer uma ligada, o clique é dela — inclusive em cima de um
 * hexágono, de um pin de imóvel ou de uma Ultra: quem ligou "Selecionar ponto" quer o
 * ponto ONDE clicou, e não a ficha do que estava embaixo.
 */
export function cliqueSelecionaHex(f: FerramentaMapa): boolean {
  return f === 'nenhuma'
}

/**
 * O cursor do mapa: mira enquanto uma ferramenta espera o clique; sem ferramenta, a mão
 * de sempre (`pointer` sobre algo clicável, `grab` no vazio).
 */
export function cursorDaFerramenta(f: FerramentaMapa, hovering: boolean): string {
  if (f !== 'nenhuma') return 'crosshair'
  return hovering ? 'pointer' : 'grab'
}
