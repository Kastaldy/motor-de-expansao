/**
 * Comparar N itens (2 a 5) e dizer qual e' o melhor e qual e' o pior.
 *
 * NAO SOMA AS DIMENSOES NUM SCORE. Um Borda count (somar posicoes) parece inocente e
 * nao e': ele assume que uma posicao em "residual" vale o mesmo que uma posicao em
 * "renda", o que e' um PESO — e peso entre camadas do M1 e' decisao que exige DEC. O
 * que se faz aqui e' CONTAR: em quantas dimensoes cada item e' o melhor, e em quantas
 * e' o pior. Contagem o operador confere a olho na propria tabela.
 *
 * DIMENSAO SEM SEPARACAO NAO DA PONTO. Se o melhor e o pior de uma dimensao estao
 * dentro do limiar (o mesmo par relativo+absoluto que a comparacao A x B usa), aquela
 * dimensao nao elege ninguem — declarar vencedor por 2% de diferenca seria transformar
 * ruido em argumento.
 *
 * O EMPATE E' UMA RESPOSTA. Quando dois itens tem a mesma contagem de vitorias, nao ha
 * "melhor": a funcao diz isso em vez de desempatar por um criterio inventado.
 */

import type { Dimensao } from './comparacao'

/** Teto de itens numa comparacao. Acima disto a tabela deixa de caber e de ser lida. */
export const MAX_COMPARADOS = 5

export interface PosicaoNaDimensao {
  chave: string
  rotulo: string
  unidade: string
  valor: number | null
  /** 1 = melhor desta dimensao. `null` quando o item nao tem o dado. */
  posicao: number | null
  melhor: boolean
  pior: boolean
}

export interface ItemRanqueado {
  indice: number
  rotulo: string
  /** Dimensoes em que este item e' o melhor (so' as que separam). */
  vitorias: number
  /** Dimensoes em que e' o pior. */
  derrotas: number
  porDimensao: PosicaoNaDimensao[]
}

export interface RankingComparacao {
  itens: ItemRanqueado[]
  /** `null` quando ha empate no topo — nao se inventa desempate. */
  melhor: ItemRanqueado | null
  pior: ItemRanqueado | null
  /** Dimensoes que efetivamente separaram alguem. */
  dimensoesDecisivas: string[]
  frase: string
}

/**
 * Ranqueia `itens` nas `dims` dadas.
 *
 * Generico pelo mesmo motivo do resto: hexagono, municipio e ponto usam as MESMAS
 * dimensoes e os MESMOS limiares que a comparacao de dois ja usa.
 */
export function ranquear<T>(
  dims: readonly Dimensao<T>[],
  itens: readonly T[],
  rotulos: readonly string[],
): RankingComparacao {
  const base: ItemRanqueado[] = itens.map((_, i) => ({
    indice: i,
    rotulo: rotulos[i] ?? `Item ${i + 1}`,
    vitorias: 0,
    derrotas: 0,
    porDimensao: [],
  }))

  const decisivas: string[] = []

  for (const dim of dims) {
    const valores = itens.map((it) => dim.ler(it))
    const comDado = valores
      .map((v, i) => ({ v, i }))
      .filter((x): x is { v: number; i: number } => x.v != null)

    // Ordena do MELHOR para o pior, ja considerando `maiorEhMelhor`.
    const ordenados = [...comDado].sort((x, y) =>
      dim.maiorEhMelhor ? y.v - x.v : x.v - y.v,
    )

    /* A dimensao SEPARA? Mede-se pelo par melhor x pior, com os mesmos dois limiares
       da comparacao A x B. Sem isso, cinco itens praticamente iguais elegeriam um
       "melhor" por diferenca que nao sustenta decisao. */
    let separa = false
    if (ordenados.length >= 2) {
      const vMelhor = ordenados[0].v
      const vPior = ordenados[ordenados.length - 1].v
      const diff = Math.abs(vMelhor - vPior)
      const escala = Math.max(Math.abs(vMelhor), Math.abs(vPior))
      const relativo = escala === 0 ? 0 : diff / escala
      separa = relativo >= dim.limiarRelativo && diff >= dim.limiarAbsoluto
    }
    if (separa) decisivas.push(dim.chave)

    // Empate no topo (ou na base) NAO elege ninguem naquela ponta.
    const topoUnico =
      ordenados.length >= 2 && ordenados[0].v !== ordenados[1].v
    const baseUnica =
      ordenados.length >= 2 &&
      ordenados[ordenados.length - 1].v !== ordenados[ordenados.length - 2].v

    itens.forEach((_, i) => {
      const v = valores[i]
      const pos = v == null ? null : ordenados.findIndex((o) => o.i === i) + 1
      const ehMelhor = separa && topoUnico && pos === 1
      const ehPior = separa && baseUnica && pos === ordenados.length && pos !== 1
      if (ehMelhor) base[i].vitorias += 1
      if (ehPior) base[i].derrotas += 1
      base[i].porDimensao.push({
        chave: dim.chave,
        rotulo: dim.rotulo,
        unidade: dim.unidade,
        valor: v,
        posicao: pos,
        melhor: ehMelhor,
        pior: ehPior,
      })
    })
  }

  // Ordena por vitorias desc, depois por MENOS derrotas. Nao ha terceiro criterio de
  // proposito: se ainda empata, e' empate mesmo.
  const ordenado = [...base].sort(
    (a, b) => b.vitorias - a.vitorias || a.derrotas - b.derrotas,
  )

  const topoEmpatado =
    ordenado.length >= 2 &&
    ordenado[0].vitorias === ordenado[1].vitorias &&
    ordenado[0].derrotas === ordenado[1].derrotas
  const baseEmpatada =
    ordenado.length >= 2 &&
    ordenado[ordenado.length - 1].vitorias === ordenado[ordenado.length - 2].vitorias &&
    ordenado[ordenado.length - 1].derrotas === ordenado[ordenado.length - 2].derrotas

  const melhor = decisivas.length && !topoEmpatado ? ordenado[0] : null
  const pior =
    decisivas.length && !baseEmpatada ? ordenado[ordenado.length - 1] : null

  return {
    itens: ordenado,
    melhor,
    pior,
    dimensoesDecisivas: decisivas,
    frase: montarFrase(ordenado, melhor, pior, decisivas.length),
  }
}

function montarFrase(
  ordenado: ItemRanqueado[],
  melhor: ItemRanqueado | null,
  pior: ItemRanqueado | null,
  nDecisivas: number,
): string {
  if (!nDecisivas) {
    return 'Os itens comparados são equivalentes nas leituras disponíveis — nenhuma diferença passa do limiar.'
  }
  if (!melhor) {
    return `Não há um melhor: ${ordenado[0].rotulo} e ${ordenado[1].rotulo} vencem o mesmo número de leituras.`
  }

  const venceEm = melhor.porDimensao
    .filter((d) => d.melhor)
    .map((d) => d.rotulo.toLowerCase())
  const lista =
    venceEm.length === 1
      ? venceEm[0]
      : `${venceEm.slice(0, -1).join(', ')} e ${venceEm[venceEm.length - 1]}`

  const base = `${melhor.rotulo} é o melhor: lidera em ${lista}.`

  if (!pior || pior.indice === melhor.indice) return base

  const perdeEm = pior.porDimensao.filter((d) => d.pior).map((d) => d.rotulo.toLowerCase())
  const listaPior =
    perdeEm.length === 1
      ? perdeEm[0]
      : `${perdeEm.slice(0, -1).join(', ')} e ${perdeEm[perdeEm.length - 1]}`

  return `${base} ${pior.rotulo} é o pior: fica atrás em ${listaPior}.`
}
