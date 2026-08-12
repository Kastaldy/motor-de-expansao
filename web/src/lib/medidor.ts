/**
 * As contas por trás das leituras VISUAIS da ficha (barras, medidores, faixas).
 *
 * Vive aqui, e não no `.tsx`, porque desenho que mente é pior que tabela: onde a barra
 * começa, o que ela usa de teto e quando ela NÃO deve aparecer são decisões, e decisão
 * sem teste é decisão que muda sozinha no próximo ajuste de estilo.
 *
 * REGRA DE OURO DESTE ARQUIVO: nada de régua inventada. Só entram aqui grandezas que o
 * payload já publica (scores 0-100, que têm escala própria) ou razões entre dois números
 * publicados (o residual dentro do SAM). Não há corte de "residual bom" no produto, e
 * pintar uma barra de verde a partir de um limiar que ninguém aprovou seria afirmar
 * régua inexistente — na tela isso vira decisão de abertura.
 */

/** Escala dos scores do produto (censitário, residual, socioeconômico). */
export const SCORE_MAX = 100

/** Prende um valor entre 0 e 1. */
function preso01(v: number): number {
  return Math.max(0, Math.min(1, v))
}

/**
 * Fração que um score 0-100 ocupa no medidor. `null` quando não há score.
 *
 * `null` e não zero: zero é uma AFIRMAÇÃO ("o pior possível") e ausência não afirma —
 * o mesmo motivo pelo qual o chip some quando o dado falta, em vez de virar "Desfavorável".
 */
export function fracaoDoScore(valor: number | null | undefined): number | null {
  if (valor == null || !Number.isFinite(valor)) return null
  return preso01(valor / SCORE_MAX)
}

export interface ComposicaoMercado {
  /** Alunos já atendidos pela oferta instalada (SAM − residual). */
  atendido: number
  /** Alunos que sobram — o `residual` do payload, sem transformação. */
  disponivel: number
  /** Quanto do mercado sobra, de 0 a 1. */
  fracaoDisponivel: number
}

/**
 * Divide o mercado potencial entre o que já é atendido e o que sobra.
 *
 * É SUBTRAÇÃO entre dois números publicados (`sam` e `residual`), não um indicador novo:
 * a barra mostra a mesma informação que os dois KPIs ao lado, na forma que responde
 * "sobra muito ou sobra pouco?" — pergunta que dois números soltos não respondem sem o
 * operador fazer a conta de cabeça.
 *
 * `null` quando falta um dos lados ou quando o SAM é zero (não há mercado para repartir).
 * O residual é preso ao teto do SAM: por arredondamentos das duas fontes ele pode vir
 * marginalmente maior, e uma barra com 103% de "disponível" leria como defeito.
 */
export function composicaoMercado(
  sam: number | null | undefined,
  residual: number | null | undefined,
): ComposicaoMercado | null {
  if (sam == null || residual == null) return null
  if (!Number.isFinite(sam) || !Number.isFinite(residual)) return null
  if (sam <= 0) return null
  const disponivel = Math.max(0, Math.min(residual, sam))
  return {
    atendido: sam - disponivel,
    disponivel,
    fracaoDisponivel: disponivel / sam,
  }
}

export interface FaixaDistribuicao {
  /** Onde a mediana cai entre o mínimo e o máximo, de 0 a 1. */
  posicaoMediana: number
  min: number
  p50: number
  max: number
}

/**
 * A dispersão setor a setor, pronta para virar uma régua com a mediana marcada.
 *
 * POR QUE IMPORTA: a ficha mostra a MÉDIA do raio, e a média esconde o caso em que
 * metade dos setores é boa e a outra metade não — dois pontos com a mesma média podem
 * ser territórios completamente diferentes. O payload já traz min/p50/max; o que faltava
 * era mostrá-los.
 *
 * `null` quando falta qualquer extremo, quando há menos de 2 setores medidos (com um só,
 * "dispersão" não existe) ou quando min == max (a régua seria um ponto, e a marca da
 * mediana sugeriria variação onde não há).
 */
export function faixaDaDistribuicao(
  d: { min: number | null; p50: number | null; max: number | null; n: number } | null | undefined,
): FaixaDistribuicao | null {
  if (!d || d.min == null || d.p50 == null || d.max == null) return null
  if (d.n < 2 || d.max <= d.min) return null
  return {
    posicaoMediana: preso01((d.p50 - d.min) / (d.max - d.min)),
    min: d.min,
    p50: d.p50,
    max: d.max,
  }
}
