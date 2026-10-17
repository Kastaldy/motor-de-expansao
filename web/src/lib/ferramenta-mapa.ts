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

/**
 * A ferramenta ligada, a partir das três chaves que o `HexMap` recebe (`medindo`,
 * `selecionandoPonto`, `desenhando`). O `MapScreen` só liga uma por vez (`alternarFerramenta`),
 * mas o mapa recebe booleanos — é aqui que eles voltam a ser o estado único que as regras
 * acima esperam, em vez de cada regra ser refeita à mão sobre os booleanos.
 */
export function ferramentaDasChaves(c: {
  medindo: boolean
  selecionandoPonto: boolean
  desenhando: boolean
}): FerramentaMapa {
  if (c.medindo) return 'regua'
  if (c.selecionandoPonto) return 'ponto'
  if (c.desenhando) return 'geometria'
  return 'nenhuma'
}

/**
 * O clique num PIN COLORIDO da comparação abre a análise daquele ponto?
 *
 * Sem ferramenta, sim. Com "Selecionar ponto" ligado, TAMBÉM: o pin tem raio de 10-13 px e
 * o clique quase nunca cai na mesma chave de ~1 m da coordenada dele, então repassá-lo ao
 * mapa criava um SEGUNDO ponto a poucos metros do primeiro — um quase duplicado ocupando
 * uma das cinco vagas. Quem clica em cima de um ponto já marcado quer aquele ponto.
 * Com a régua ou o desenho, não: ali o pin é só um lugar do mapa (a régua imanta nele).
 */
export function pinDaComparacaoAbre(f: FerramentaMapa): boolean {
  return f === 'nenhuma' || f === 'ponto'
}
