/**
 * A geometria da janela flutuante da ficha: onde ela está, que tamanho tem, e o que o
 * arrasto pode fazer com isso.
 *
 * Vive aqui, e não no `.tsx`, porque é DECISÃO e não pintura: quanto da janela pode sair
 * da tela, qual o tamanho mínimo utilizável, o que acontece quando a tela encolhe. O
 * componente só aplica o resultado. É o padrão da casa — o vitest roda em ambiente node e
 * só casa `src/**\/*.test.ts`, então regra em `.tsx` é regra sem teste.
 */

export interface Geometria {
  x: number
  y: number
  largura: number
  altura: number
}

export interface Area {
  largura: number
  altura: number
}

/** 520px cabe a grade de KPI em 2 colunas e a comparação A x B em 3, sem espremer. */
export const LARGURA_PADRAO = 520
/** Abaixo disto os KPIs quebram em 1 coluna e a janela deixa de valer a pena. */
export const LARGURA_MINIMA = 320
/** Duas seções e o cabeçalho. Menos que isso vira uma fresta que não se lê. */
export const ALTURA_MINIMA = 220
/** Folga das bordas na posição inicial. */
export const MARGEM = 16
/** Altura do cabeçalho da janela — é o que sobra quando ela é recolhida. */
export const ALTURA_CABECALHO = 56

/**
 * Quanto da janela precisa continuar dentro da área, em cada eixo.
 *
 * Sem isto o operador arrasta a janela para fora e não tem como trazê-la de volta: some
 * a barra de título, que é a única alça. 120px garantem um pedaço do título e o × ao
 * alcance; no eixo Y a trava é a própria barra, que nunca passa do pé da área.
 */
export const VISIVEL_MINIMO = 120

/**
 * Onde a janela nasce: encostada à direita, abaixo do cabeçalho do mapa e acima do
 * stepper. Mesma posição que ela tinha quando era fixa — quem não arrastar nada não vê
 * diferença nenhuma.
 */
export function geometriaPadrao(area: Area, topo: number, recuoInferior: number): Geometria {
  const largura = Math.min(LARGURA_PADRAO, Math.max(LARGURA_MINIMA, area.largura - 2 * MARGEM))
  const altura = Math.max(ALTURA_MINIMA, area.altura - topo - recuoInferior)
  return { x: Math.max(MARGEM, area.largura - largura - MARGEM), y: topo, largura, altura }
}

/** Prende um valor entre dois limites. `max < min` devolve `min` — área minúscula não inverte a trava. */
function preso(valor: number, min: number, max: number): number {
  return Math.max(min, Math.min(valor, Math.max(min, max)))
}

/**
 * Move a janela, mantendo-a alcançável.
 *
 * O X pode ficar NEGATIVO de propósito: encostar a janela meio para fora à esquerda é
 * legítimo (libera o mapa) desde que sobre alça para trazê-la de volta. Já o Y nunca é
 * negativo — barra de título acima do topo é barra de título perdida.
 */
export function mover(geo: Geometria, dx: number, dy: number, area: Area): Geometria {
  return {
    ...geo,
    x: preso(geo.x + dx, VISIVEL_MINIMO - geo.largura, area.largura - VISIVEL_MINIMO),
    y: preso(geo.y + dy, 0, Math.max(0, area.altura - ALTURA_CABECALHO)),
  }
}

/**
 * Redimensiona pelo canto inferior direito: `x`/`y` ficam parados e a janela cresce para
 * baixo e para a direita, que é o gesto que o canto promete.
 *
 * O teto é a borda da área a partir da posição atual — sem ele, arrastar rápido para fora
 * da tela deixaria a janela maior que o espaço e o canto sairia do alcance do mouse, o
 * que trava o redimensionamento para sempre.
 */
export function redimensionar(geo: Geometria, dx: number, dy: number, area: Area): Geometria {
  return {
    ...geo,
    largura: preso(geo.largura + dx, LARGURA_MINIMA, Math.max(LARGURA_MINIMA, area.largura - geo.x)),
    altura: preso(geo.altura + dy, ALTURA_MINIMA, Math.max(ALTURA_MINIMA, area.altura - geo.y)),
  }
}

/**
 * Reprende uma geometria já existente numa área NOVA (a janela do navegador mudou de
 * tamanho, ou o painel lateral apareceu).
 *
 * Sem isto, encolher a janela do navegador deixa a ficha inteira fora da tela e sem volta
 * — o estado dela é absoluto, não relativo.
 */
export function reajustar(geo: Geometria, area: Area): Geometria {
  const largura = preso(geo.largura, LARGURA_MINIMA, Math.max(LARGURA_MINIMA, area.largura))
  const altura = preso(geo.altura, ALTURA_MINIMA, Math.max(ALTURA_MINIMA, area.altura))
  return mover({ ...geo, largura, altura }, 0, 0, area)
}
