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

import type { FaixaNomeada } from './faixas'

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

/**
 * Em que faixa NOMEADA um score cai — e, com ela, a cor e o veredito.
 *
 * É a régua PUBLICADA (`lib/faixas.ts`, espelho de `constants.py`), a mesma que pinta o
 * hexágono no mapa. Por isso o medidor pode colorir sem inventar corte: "Promissor" na
 * ficha é exatamente o "Promissor" que o operador vê no mapa e na legenda, na mesma cor.
 * Um gradiente escolhido no olho seria outra coisa — afirmaria bom e ruim por conta
 * própria, e na tela isso vira decisão de abertura.
 */
export function faixaDoValor(
  valor: number | null | undefined,
  faixas: readonly FaixaNomeada[],
): FaixaNomeada | null {
  if (valor == null || !Number.isFinite(valor)) return null
  // O último bloco fecha em 100 (intervalo superior INCLUSIVO): sem isto, score 100 —
  // uma unidade cheia na camada 2 — ficaria sem faixa e sem cor.
  return (
    faixas.find((f, i) => valor >= f.de && (valor < f.ate || i === faixas.length - 1)) ?? null
  )
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

/* A régua de dispersão (mínimo / mediana / máximo por setor) FOI REMOVIDA em 2026-08-12:
   "não faz sentido o usuário ver isso" (Juan). Era leitura de analista — quem escolhe
   imóvel quer o número da região e o setor em que o imóvel caiu, não a estatística
   descritiva do raio. O `/api/ponto` continua publicando `distribuicao`; se um dia ela
   voltar, volta com um consumidor que a justifique. */
