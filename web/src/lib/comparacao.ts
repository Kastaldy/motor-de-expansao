/**
 * Comparacao entre hexagonos — a regra, PURA e testavel.
 *
 * POR QUE NAO E' O "CENARIO MULTI-HEX". O botao que ja existe no mapa SOMA: junta
 * N hexes num bloco unico (residual somado, populacao somada, concorrentes somados,
 * media simples do score censitario). Isso responde "quanto vale este pedaco de
 * cidade junto". Comparar responde outra pergunta — "qual destes dois e' melhor, e
 * por que" — e as duas continuam existindo lado a lado.
 *
 * ORDENAR PELO BRUTO, NUNCA PELO SCORE. `score_oportunidade_residual` (`hex.res`) e'
 * `clip(100 * oferta / 2500, 0, 100)`: todo hexagono com mais de 2.500 alunos de
 * residual empata em 100. Medido no payload real de GO: `res: 100.0` com
 * `oferta: 8694`. Comparar por `res` apagaria justamente a diferenca no topo, que e'
 * onde estao os candidatos. Por isso a dimensao de residual le `oferta`, em alunos.
 *
 * TEXTO POR REGRA, NAO POR MODELO. O produto nao usa LLM em lugar nenhum (zero SDK,
 * zero chave); todo texto automatico daqui e' cadeia de regra deterministica, como
 * `_narrativa_concorrencia` no backend. A frase comparativa segue o mesmo padrao:
 * mesma entrada, mesma saida, auditavel e testavel.
 */

import type { Hex } from './types'

/** Uma dimensao comparavel: de onde ler, como chamar, e o que significa "melhor". */
export interface Dimensao {
  chave: string
  /** Rotulo de exibicao (acentuado — texto de usuario). */
  rotulo: string
  /** Le o valor do hexagono. `null` = dimensao ausente neste hex. */
  ler: (h: Hex) => number | null
  unidade: string
  /** `true` = numero maior e' melhor. Concorrentes e' o unico onde menor ganha. */
  maiorEhMelhor: boolean
  /**
   * Diferenca minima para a dimensao ENTRAR na frase.
   * `relativa` = fracao (0.1 = 10%); `absoluta` = unidades, para contagem pequena,
   * onde 1 concorrente contra 2 e' +100% e nao significa quase nada.
   */
  limiarRelativo: number
  limiarAbsoluto: number
}

/**
 * Ordem de PRIORIDADE, nao de exibicao: quando mais de 3 dimensoes passam do
 * limiar, a frase fica com as 3 primeiras desta lista. Residual vem antes de tudo
 * porque e' a pergunta do produto ("cabe quanta gente ainda?"); crescimento vem por
 * ultimo porque e' contexto municipal, nao atributo do hexagono.
 */
export const DIMENSOES: readonly Dimensao[] = Object.freeze([
  Object.freeze({
    chave: 'oferta',
    rotulo: 'Residual disponível',
    ler: (h: Hex) => h.oferta,
    unidade: 'alunos',
    maiorEhMelhor: true,
    limiarRelativo: 0.1,
    limiarAbsoluto: 100,
  }),
  Object.freeze({
    chave: 'pop',
    rotulo: 'População',
    ler: (h: Hex) => h.pop,
    unidade: 'pessoas',
    maiorEhMelhor: true,
    limiarRelativo: 0.1,
    limiarAbsoluto: 500,
  }),
  Object.freeze({
    chave: 'conc',
    rotulo: 'Concorrentes',
    ler: (h: Hex) => h.conc,
    unidade: '',
    // Unica dimensao invertida: menos concorrente e' melhor.
    maiorEhMelhor: false,
    limiarRelativo: 0.1,
    /**
     * Precisa de 2 concorrentes de diferenca, nao 1.
     *
     * O numero que chega aqui (`hex.conc`) NAO e' contagem: e'
     * `round(oferta_consumida_ponderada_por_distancia / 2500)`. Um concorrente a
     * 1,9 km entra valendo ~0,05 e some no arredondamento, entao +-1 e' ruido do
     * proprio estimador. Dizer "tem menos concorrentes" para 2 contra 1 seria
     * afirmar sobre a precisao que este campo nao tem.
     */
    limiarAbsoluto: 2,
  }),
  Object.freeze({
    chave: 'renda',
    rotulo: 'Renda per capita',
    ler: (h: Hex) => h.renda,
    unidade: 'R$',
    maiorEhMelhor: true,
    limiarRelativo: 0.1,
    limiarAbsoluto: 100,
  }),
  Object.freeze({
    chave: 'cres',
    rotulo: 'Crescimento',
    ler: (h: Hex) => h.cres_hex_taxa ?? null,
    unidade: '%',
    maiorEhMelhor: true,
    limiarRelativo: 0.1,
    limiarAbsoluto: 2,
  }),
])

export interface Delta {
  dimensao: Dimensao
  a: number | null
  b: number | null
  /** Diferenca absoluta (a - b). `null` se algum lado nao tem o dado. */
  diferenca: number | null
  /** |a-b| / max(|a|,|b|). `null` quando nao da para calcular. */
  desvioRelativo: number | null
  /** Passou dos DOIS limiares (relativo E absoluto)? */
  relevante: boolean
  /** Quem leva esta dimensao, ja considerando `maiorEhMelhor`. */
  vencedor: 'a' | 'b' | 'empate'
}

/** Compara A e B em todas as dimensoes, na ordem de prioridade. */
export function compararHexes(a: Hex, b: Hex): Delta[] {
  return DIMENSOES.map((dim) => {
    const va = dim.ler(a)
    const vb = dim.ler(b)

    if (va == null || vb == null) {
      return {
        dimensao: dim, a: va, b: vb,
        diferenca: null, desvioRelativo: null,
        relevante: false, vencedor: 'empate' as const,
      }
    }

    const diferenca = va - vb
    const escala = Math.max(Math.abs(va), Math.abs(vb))
    // Ambos zero: nao ha diferenca nem desvio definido — desvio 0, nao NaN.
    const desvioRelativo = escala === 0 ? 0 : Math.abs(diferenca) / escala

    const relevante =
      desvioRelativo >= dim.limiarRelativo &&
      Math.abs(diferenca) >= dim.limiarAbsoluto

    let vencedor: 'a' | 'b' | 'empate' = 'empate'
    if (diferenca !== 0) {
      const aGanha = dim.maiorEhMelhor ? diferenca > 0 : diferenca < 0
      vencedor = aGanha ? 'a' : 'b'
    }

    return { dimensao: dim, a: va, b: vb, diferenca, desvioRelativo, relevante, vencedor }
  })
}

/** Quantas dimensoes cabem numa frase antes de ela virar tabela em prosa. */
export const MAX_DIMENSOES_NA_FRASE = 3

export interface Comparacao {
  deltas: Delta[]
  /** As que entram na frase: relevantes, na ordem de prioridade, no maximo 3. */
  destaques: Delta[]
  /** Quem leva mais dimensoes relevantes. `empate` quando nenhuma passa do limiar. */
  vencedor: 'a' | 'b' | 'empate'
  frase: string
}

/**
 * Frase comparativa DETERMINISTICA.
 *
 * Regra de ouro: nunca afirmar diferenca que nao passou do limiar. Sem isso a frase
 * diria "tem mais populacao" para 2% de diferenca, que e' ruido do dado, e o
 * operador tomaria decisao em cima de nada.
 */
export function compararComFrase(
  a: Hex,
  b: Hex,
  rotuloA = 'O primeiro',
  rotuloB = 'o segundo',
): Comparacao {
  const deltas = compararHexes(a, b)
  const destaques = deltas.filter((d) => d.relevante).slice(0, MAX_DIMENSOES_NA_FRASE)

  if (!destaques.length) {
    return {
      deltas,
      destaques,
      vencedor: 'empate',
      frase: 'Os dois pontos são equivalentes nas leituras disponíveis.',
    }
  }

  const pontosA = destaques.filter((d) => d.vencedor === 'a').length
  const pontosB = destaques.filter((d) => d.vencedor === 'b').length
  const vencedor: 'a' | 'b' | 'empate' =
    pontosA === pontosB ? 'empate' : pontosA > pontosB ? 'a' : 'b'

  // Cada destaque vira um trecho na voz de A ("mais X", "menos Y").
  const trecho = (d: Delta) =>
    `${(d.diferenca ?? 0) > 0 ? 'mais' : 'menos'} ${d.dimensao.rotulo.toLowerCase()}`

  /**
   * Separa por QUEM GANHA, e nao pela direcao do numero.
   *
   * Sem isto a frase enfileira "menos população, menos concorrentes e menos renda"
   * como se as tres fossem deficits — mas menos concorrente e' VANTAGEM. Medido num
   * par real de GO (Goiatuba x Anapolis), a frase corrida dava a entender que
   * Goiatuba perdia em tudo, inclusive naquilo em que ganhava. O "porém" e' o que
   * devolve a direcao a leitura.
   */
  const vantagens = destaques.filter((d) => d.vencedor === 'a').map(trecho)
  const desvantagens = destaques.filter((d) => d.vencedor === 'b').map(trecho)

  const juntar = (xs: string[]) =>
    xs.length === 1 ? xs[0] : `${xs.slice(0, -1).join(', ')} e ${xs[xs.length - 1]}`

  const corpo =
    vantagens.length && desvantagens.length
      ? `${juntar(vantagens)}, porém ${juntar(desvantagens)}`
      : `${juntar(vantagens.length ? vantagens : desvantagens)}`

  const veredito =
    vencedor === 'empate'
      ? 'os dois se equilibram: cada um ganha em uma leitura diferente.'
      : vencedor === 'a'
        ? `${rotuloA} leva a comparação.`
        : `${rotuloB} leva a comparação.`

  return {
    deltas,
    destaques,
    vencedor,
    frase: `${rotuloA} tem ${corpo} que ${rotuloB} — ${veredito}`,
  }
}
