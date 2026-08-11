/**
 * Geometria de gráfico — sparkline e rosca. Puro, sem React: testável sem DOM.
 *
 * Deriva de `RampaAlunos` (`ViabilityCharts.tsx`), que já desenha série mensal à mão: o
 * projeto não tem biblioteca de gráficos, e não vai ganhar uma por causa de 12 pontos.
 *
 * A conta da rosca mora aqui pelo mesmo motivo que a da sparkline: ela existe DUAS vezes
 * no produto — nesta tela e no gerador de PDF, em Python — e as duas precisam concordar
 * sobre o que é 100%, o que é fatia vazia e o que acontece quando o total é zero.
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
  /**
   * x de CADA índice da série, buracos inclusive.
   *
   * Existe para quem desenha por cima da linha (o rótulo de valor de cada mês) não ter
   * de refazer a conta do passo: duas fórmulas para a mesma abscissa divergem no dia em
   * que uma das duas mudar, e o rótulo passa a apontar para o ponto do vizinho.
   */
  xs: number[]
  /**
   * y de cada índice — `null` onde não há valor. Mesma razão de `xs`: o rótulo precisa
   * pousar na altura EXATA do seu ponto, e refazer a conta lá fora obriga a repetir o
   * padding e a amplitude, que são justamente o que muda quando se dá folga ao desenho.
   */
  ys: (number | null)[]
}

/**
 * Como os pontos se espalham na largura disponível.
 *
 * `pontas` — primeiro ponto na borda esquerda, último na direita. É o que uma sparkline
 * sem eixo quer: aproveita cada pixel dos 76 px da célula da tabela.
 *
 * `faixas` — cada ponto no CENTRO da sua fatia de largura, exatamente onde
 * `BarrasPeriodo` põe a barra do mesmo mês. É o que um gráfico COM eixo de meses quer:
 * em `pontas`, o ponto de "ago" cai no x=6 enquanto o rótulo "ago" (um `div` em flex,
 * que divide a largura em N fatias iguais) fica centrado em x=39 — um terço de fatia de
 * erro, crescendo para as pontas. Alinhar também faz o mesmo mês não pular de lugar
 * quando o painel alterna entre a métrica de barra e a de linha.
 */
export type DistribuicaoSparkline = 'pontas' | 'faixas'

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
  distribuicao: DistribuicaoSparkline = 'pontas',
): Sparkline {
  const pontos = valores
    .map((v, i) => ({ i, v: typeof v === 'number' && Number.isFinite(v) ? v : null }))
    .filter((p): p is { i: number; v: number } => p.v !== null)

  const passo =
    distribuicao === 'faixas'
      ? largura / Math.max(valores.length, 1)
      : valores.length > 1
        ? (largura - 2 * padding) / (valores.length - 1)
        : 0
  const xDe = (i: number): number =>
    distribuicao === 'faixas' ? (i + 0.5) * passo : padding + i * passo
  const xs = valores.map((_, i) => xDe(i))

  if (pontos.length === 0) {
    return { linha: '', area: '', ultimo: null, minimo: 0, maximo: 0, xs, ys: valores.map(() => null) }
  }

  const minimo = Math.min(...pontos.map((p) => p.v))
  const maximo = Math.max(...pontos.map((p) => p.v))
  const amplitude = maximo - minimo
  const alturaUtil = altura - 2 * padding
  const yDe = (v: number): number =>
    amplitude === 0 ? altura / 2 : padding + alturaUtil * (1 - (v - minimo) / amplitude)

  const xy = pontos.map((p) => ({ x: xDe(p.i), y: yDe(p.v) }))
  const ys = valores.map((v) => (typeof v === 'number' && Number.isFinite(v) ? yDe(v) : null))

  const linha = xy.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(2)},${p.y.toFixed(2)}`).join(' ')
  const primeiro = xy[0]
  const ultimo = xy[xy.length - 1]
  const area =
    xy.length > 1
      ? `${linha} L${ultimo.x.toFixed(2)},${altura} L${primeiro.x.toFixed(2)},${altura} Z`
      : ''
  return { linha, area, ultimo, minimo, maximo, xs, ys }
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

export interface FatiaDeRosca {
  rotulo: string
  valor: number
  cor: string
  /** fração do total, 0..1 */
  fracao: number
  /** `stroke-dasharray` do arco */
  traco: string
  /** `stroke-dashoffset` acumulado das fatias anteriores */
  deslocamento: number
}

/**
 * Fatias de uma rosca desenhada com `stroke-dasharray` num círculo.
 *
 * Três casos que a versão em Python errou e custaram um render para descobrir:
 * total zero (não pode dividir), fatia de 100% (tem de fechar a volta inteira) e fatia
 * de valor zero (não pode ocupar espaço nem deslocar as seguintes).
 */
export function fatiasDeRosca(
  partes: { rotulo: string; valor: number; cor: string }[],
  raio: number,
): { fatias: FatiaDeRosca[]; total: number; perimetro: number } {
  const perimetro = 2 * Math.PI * raio
  const total = partes.reduce((s, p) => s + Math.max(p.valor, 0), 0)
  if (total <= 0) {
    return {
      fatias: partes.map((p) => ({ ...p, fracao: 0, traco: `0 ${perimetro}`, deslocamento: 0 })),
      total: 0,
      perimetro,
    }
  }
  let percorrido = 0
  const fatias = partes.map((p) => {
    const fracao = Math.max(p.valor, 0) / total
    const fatia: FatiaDeRosca = {
      ...p,
      fracao,
      traco: `${perimetro * fracao} ${perimetro * (1 - fracao)}`,
      deslocamento: -perimetro * percorrido,
    }
    percorrido += fracao
    return fatia
  })
  return { fatias, total, perimetro }
}

/** Percentual de uma fatia, para o rótulo. `null` quando não há base. */
export function percentualDaFatia(valor: number, total: number): number | null {
  return total > 0 ? (100 * valor) / total : null
}

/** Onde escrever o valor de um ponto sem que a própria linha passe por cima dele. */
export type LadoDoRotulo = 'acima' | 'abaixo' | 'acima-esquerda' | 'acima-direita'

/**
 * De que lado do ponto o rótulo de valor cabe.
 *
 * Um número escrito sobre uma série se espalha para os DOIS lados do seu ponto, umas
 * três vezes mais na horizontal do que na vertical. Colocá-lo sempre acima funciona no
 * pico e falha em todo o resto: no churn da rede, "5,3%" (fevereiro, um vale) saía
 * riscado pelas duas pernas do "V", e na receita por recorrente "R$ 140" (novembro, meio
 * de uma subida) saía riscado pela perna que sobe. A regra sai da forma local:
 *
 *   vale   (os dois vizinhos acima)  -> ABAIXO. Acima está o miolo do "V"; abaixo é a
 *                                       área preenchida, que não tem traço nenhum.
 *   pico   (os dois vizinhos abaixo) -> ACIMA, centrado. É o caso fácil.
 *   subida (esquerda < ponto < dir.) -> ACIMA e à ESQUERDA: a perna da direita sobe e
 *                                       ocupa aquele espaço; a da esquerda desce e libera.
 *   descida                          -> ACIMA e à DIREITA, pelo espelho do anterior.
 *
 * Ponta da série decide com o único vizinho que tem. Empate (trecho plano) vai para
 * `acima`: sem inclinação, nada cruza o texto.
 */
export function ladoDoRotulo(valores: (number | null | undefined)[], i: number): LadoDoRotulo {
  const numero = (v: number | null | undefined): number | null =>
    typeof v === 'number' && Number.isFinite(v) ? v : null
  const v = numero(valores[i])
  if (v === null) return 'acima'
  const esq = numero(valores[i - 1])
  const dir = numero(valores[i + 1])
  const vizinhos = [esq, dir].filter((n): n is number => n !== null)
  if (!vizinhos.length) return 'acima'
  if (vizinhos.every((n) => n >= v) && vizinhos.some((n) => n > v)) return 'abaixo'
  if (vizinhos.every((n) => n <= v)) return 'acima'
  // Sobrou a rampa: um vizinho de cada lado do valor. O rótulo foge da perna que sobe.
  return dir !== null && dir > v ? 'acima-esquerda' : 'acima-direita'
}

/** Quanto o rótulo se afasta do ponto, em px. */
const RECUO_LATERAL = 4
const DESCIDA_DO_ROTULO = 10
const SUBIDA_DO_ROTULO = 6
/** Teto de segurança do topo: acima disto o texto sai pela borda de cima do quadro. */
const TETO_DO_ROTULO = 9

export interface PosicaoDoRotulo {
  x: number
  y: number
  textAnchor: 'start' | 'middle' | 'end'
}

/**
 * Traduz `ladoDoRotulo` em coordenadas, mantendo a CAIXA do texto dentro do quadro.
 *
 * `meiaCaixa` é metade da largura do texto — quem chama sabe a fonte, esta função não.
 * O grampo é por caixa, e não pelo x do ponto: grampeando só o x, "1.808,0" começava em
 * −2 px na ficha da unidade e o número aparecia como ".808,0", que não é um rótulo feio,
 * é um valor errado na tela.
 *
 * O recuo lateral entra ANTES do grampo. Na ordem inversa, grampear e depois deslocar
 * devolveria o texto para fora exatamente na ponta em que o grampo tinha acabado de agir.
 */
export function ancoraDoRotulo(
  lado: LadoDoRotulo,
  x: number,
  y: number,
  meiaCaixa: number,
  largura: number,
): PosicaoDoRotulo {
  // `Math.max(max, min)` protege o caso em que o texto é mais largo que o quadro: sem
  // isso o grampo inverteria os limites e devolveria NaN em vez de encostar na borda.
  const grampo = (valor: number, min: number, max: number): number =>
    Math.min(Math.max(valor, min), Math.max(max, min))
  const acima = Math.max(y - SUBIDA_DO_ROTULO, TETO_DO_ROTULO)
  switch (lado) {
    case 'abaixo':
      return {
        x: grampo(x, meiaCaixa, largura - meiaCaixa),
        y: y + DESCIDA_DO_ROTULO,
        textAnchor: 'middle',
      }
    // `end`: o texto TERMINA em x, então ele cabe quando x >= a largura inteira do texto.
    case 'acima-esquerda':
      return { x: grampo(x - RECUO_LATERAL, 2 * meiaCaixa, largura), y: acima, textAnchor: 'end' }
    // `start`: o texto COMEÇA em x e se estende para a direita.
    case 'acima-direita':
      return {
        x: grampo(x + RECUO_LATERAL, 0, largura - 2 * meiaCaixa),
        y: acima,
        textAnchor: 'start',
      }
    default:
      return { x: grampo(x, meiaCaixa, largura - meiaCaixa), y: acima, textAnchor: 'middle' }
  }
}
