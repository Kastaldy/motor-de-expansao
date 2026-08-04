/**
 * Caminho SVG de uma sparkline. Puro, sem React — testável sem DOM.
 *
 * Deriva de `RampaAlunos` (`ViabilityCharts.tsx`), que já desenha série mensal à mão: o
 * projeto não tem biblioteca de gráficos, e não vai ganhar uma por causa de 12 pontos.
 */

export interface Sparkline {
  /** `d` da polilinha */
  linha: string
  /** `d` da área sob a linha (fecha na base) */
  area: string
  /** ponto final, para o marcador */
  ultimo: { x: number; y: number } | null
  minimo: number
  maximo: number
}

/**
 * Constrói o caminho de uma série, ignorando buracos.
 *
 * Série toda igual (ou de um ponto só) NÃO pode virar divisão por zero: nesse caso a
 * linha sai reta no meio da caixa, que é a leitura honesta de "não variou".
 */
export function caminhoSparkline(
  valores: (number | null | undefined)[],
  largura: number,
  altura: number,
  padding = 1.5,
): Sparkline {
  const pontos = valores
    .map((v, i) => ({ i, v: typeof v === 'number' && Number.isFinite(v) ? v : null }))
    .filter((p): p is { i: number; v: number } => p.v !== null)

  const vazio: Sparkline = { linha: '', area: '', ultimo: null, minimo: 0, maximo: 0 }
  if (pontos.length === 0) return vazio

  const minimo = Math.min(...pontos.map((p) => p.v))
  const maximo = Math.max(...pontos.map((p) => p.v))
  const amplitude = maximo - minimo
  const passo = valores.length > 1 ? (largura - 2 * padding) / (valores.length - 1) : 0
  const alturaUtil = altura - 2 * padding

  const xy = pontos.map((p) => ({
    x: padding + p.i * passo,
    y: amplitude === 0 ? altura / 2 : padding + alturaUtil * (1 - (p.v - minimo) / amplitude),
  }))

  const linha = xy.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(2)},${p.y.toFixed(2)}`).join(' ')
  const primeiro = xy[0]
  const ultimo = xy[xy.length - 1]
  const area =
    xy.length > 1
      ? `${linha} L${ultimo.x.toFixed(2)},${altura} L${primeiro.x.toFixed(2)},${altura} Z`
      : ''
  return { linha, area, ultimo, minimo, maximo }
}

/**
 * Escala de barras: cada valor vira a fração da maior barra (0..1).
 *
 * Base sempre em ZERO, nunca no mínimo da série: começar no mínimo faz uma variação de
 * 2% parecer uma queda pela metade. É o mesmo defeito da escala congelada do bloco
 * diário da planilha do time.
 */
export function escalaDeBarras(valores: (number | null | undefined)[]): number[] {
  const finitos = valores.filter((v): v is number => typeof v === 'number' && Number.isFinite(v))
  const maximo = finitos.length ? Math.max(...finitos.map(Math.abs)) : 0
  if (maximo === 0) return valores.map(() => 0)
  return valores.map((v) => (typeof v === 'number' && Number.isFinite(v) ? v / maximo : 0))
}
