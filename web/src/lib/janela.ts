/**
 * A geometria da janela flutuante da ficha: onde ela está, que tamanho tem, e o que o
 * arrasto pode fazer com isso.
 *
 * Vive aqui, e não no `.tsx`, porque é DECISÃO e não pintura: quanto da janela pode sair
 * da tela, qual o tamanho mínimo utilizável, o que acontece quando a tela encolhe. O
 * componente só aplica o resultado. É o padrão da casa — o vitest roda em ambiente node e
 * só casa `src/**\/*.test.ts`, então regra em `.tsx` é regra sem teste.
 */

import { FOLGA_ABAIXO_DO_CABECALHO } from './botao-ver-ficha'

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

/**
 * De que lado a janela nasce.
 *
 * Existe porque agora há mais de uma na mesma tela: sem lados distintos, a segunda
 * abriria exatamente em cima da primeira e pareceria que só uma existe. Não trava nada —
 * arrastar continua levando qualquer uma para qualquer canto.
 */
export type Ancora = 'direita' | 'esquerda'

/** 520px cabe a grade de KPI em 2 colunas e a comparação A x B em 3, sem espremer. */
export const LARGURA_PADRAO = 520
/**
 * A ficha de PONTO nasce mais estreita (pedido do Vinicius, 20/10/2026: "no meu
 * dispositivo, 480px se mostraram menor sem perder muito conteúdo horizontal"). Ela é a
 * janela que divide a tela com o mapa do ponto — o contorno do alcance que se quer ver ao
 * lado. Só a NASCENÇA: redimensionar continua livre, até `LARGURA_MINIMA`, que fica abaixo.
 */
export const LARGURA_FICHA_PONTO = 480
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
 * Quanto um DEGRAU desloca a janela que nasce sobre outra do mesmo lado: a barra de título
 * inteira na vertical (a de baixo continua com título e × à vista) e um recuo na horizontal
 * (a borda de baixo continua visível). É a cascata clássica de janelas.
 */
export const DEGRAU_Y = ALTURA_CABECALHO
export const DEGRAU_X = 24

/**
 * Onde a janela nasce: encostada à direita, abaixo do cabeçalho do mapa e acima do
 * stepper. Mesma posição que ela tinha quando era fixa — quem não arrastar nada não vê
 * diferença nenhuma.
 *
 * `degrau` (0 = a posição de sempre) existe porque dois lados não bastam mais: com a
 * análise de pontos nas duas entradas do mapa, a ficha de ponto ocupa a esquerda, e a do
 * hexágono e a do comparativo de hexágonos nasciam EXATAMENTE em cima dela (ou, mandadas
 * para a direita, em cima da do imóvel e da unidade). Em degrau, a de cima nasce deslocada
 * para dentro da tela e a de baixo segue com a barra de título à vista.
 */
export function geometriaPadrao(
  area: Area,
  topo: number,
  recuoInferior: number,
  ancora: Ancora = 'direita',
  degrau = 0,
  larguraInicial = LARGURA_PADRAO,
): Geometria {
  const d = Math.max(0, Math.floor(degrau))
  /* A largura pedida nunca fica abaixo do mínimo: um valor menor viraria uma janela que o
     próprio `redimensionar` já não aceitaria. */
  const pedida = Math.max(LARGURA_MINIMA, larguraInicial)
  const largura = Math.min(pedida, Math.max(LARGURA_MINIMA, area.largura - 2 * MARGEM))
  const y = topo + d * DEGRAU_Y
  const altura = Math.max(ALTURA_MINIMA, area.altura - y - recuoInferior)
  const dx = d * DEGRAU_X
  const x =
    ancora === 'esquerda'
      ? MARGEM + dx
      : Math.max(MARGEM, area.largura - largura - MARGEM - dx)
  return { x, y, largura, altura }
}

/**
 * O TOPO MINIMO da janela: a borda de baixo do cabecalho do mapa, mais a folga de sempre.
 *
 * Existe desde que o cabecalho passou a ficar ACIMA das janelas (`Z_CABECALHO_MAPA`, pedido
 * do Vinicius, 21/10/2026: as janelas cobriam os seletores de UF e municipio). Por cima, o
 * cabecalho esconderia a barra de titulo de uma janela arrastada ate' o topo -- e a barra e'
 * a UNICA alca, entao a janela ficaria sem volta. O cabecalho e' `flex-wrap` e ocupa a
 * largura inteira: nao ha' por onde pegar a barra por baixo dele. Por isso a janela nunca
 * sobe alem desta linha, nem ao nascer, nem ao arrastar, nem quando o cabecalho quebra em
 * duas linhas com ela ja' aberta.
 *
 * Mesma regua do botao "Ver a ficha" (`lib/botao-ver-ficha`): os retangulos medidos estao
 * em px de TELA e o `top` em px de LAYOUT -- o `#root` e' encolhido por `--escala-app`.
 * Sem cabecalho medido (ou medida invalida) devolve 0: a trava antiga, so' o topo da area.
 */
export function topoMinimoSobCabecalho(
  fundoCabecalho: number | null,
  topoContainer: number | null,
  escala = 1,
): number {
  if (fundoCabecalho == null || topoContainer == null) return 0
  if (!Number.isFinite(fundoCabecalho) || !Number.isFinite(topoContainer)) return 0
  const e = Number.isFinite(escala) && escala > 0 ? escala : 1
  return Math.max(0, Math.round((fundoCabecalho - topoContainer) / e + FOLGA_ABAIXO_DO_CABECALHO))
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
export function mover(
  geo: Geometria,
  dx: number,
  dy: number,
  area: Area,
  /** a borda de baixo do cabecalho do mapa (`topoMinimoSobCabecalho`); 0 = sem cabecalho */
  topoMinimo = 0,
): Geometria {
  const piso = Math.max(0, topoMinimo)
  return {
    ...geo,
    x: preso(geo.x + dx, VISIVEL_MINIMO - geo.largura, area.largura - VISIVEL_MINIMO),
    y: preso(geo.y + dy, piso, Math.max(piso, area.altura - ALTURA_CABECALHO)),
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
export function reajustar(geo: Geometria, area: Area, topoMinimo = 0): Geometria {
  const largura = preso(geo.largura, LARGURA_MINIMA, Math.max(LARGURA_MINIMA, area.largura))
  const altura = preso(geo.altura, ALTURA_MINIMA, Math.max(ALTURA_MINIMA, area.altura))
  return mover({ ...geo, largura, altura }, 0, 0, area, topoMinimo)
}
