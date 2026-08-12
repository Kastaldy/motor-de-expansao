import { describe, expect, it } from 'vitest'

import { MAX_COMPARADOS, ranquear } from './ranking-comparacao'
import type { Dimensao } from './comparacao'

interface Alvo {
  residual: number | null
  pop: number | null
  conc: number | null
}

/** Dimensões no mesmo formato das reais: dois limiares, uma invertida. */
const DIMS: readonly Dimensao<Alvo>[] = [
  {
    chave: 'residual', rotulo: 'Residual', ler: (a) => a.residual, unidade: 'alunos',
    maiorEhMelhor: true, limiarRelativo: 0.1, limiarAbsoluto: 100,
  },
  {
    chave: 'pop', rotulo: 'População', ler: (a) => a.pop, unidade: 'pessoas',
    maiorEhMelhor: true, limiarRelativo: 0.1, limiarAbsoluto: 500,
  },
  {
    chave: 'conc', rotulo: 'Concorrentes', ler: (a) => a.conc, unidade: '',
    maiorEhMelhor: false, limiarRelativo: 0.1, limiarAbsoluto: 2,
  },
]

const rot = (n: number) => Array.from({ length: n }, (_, i) => `H${i + 1}`)

describe('ranquear — conta vitorias, nao soma posicoes', () => {
  it('elege o melhor por numero de dimensoes lideradas', () => {
    const r = ranquear(
      DIMS,
      [
        { residual: 9000, pop: 50000, conc: 0 }, // lidera as 3
        { residual: 3000, pop: 20000, conc: 6 },
        { residual: 1000, pop: 8000, conc: 9 },
      ],
      rot(3),
    )
    expect(r.melhor?.rotulo).toBe('H1')
    expect(r.melhor?.vitorias).toBe(3)
    expect(r.pior?.rotulo).toBe('H3')
    expect(r.frase).toContain('H1 é o melhor')
    expect(r.frase).toContain('H3 é o pior')
  })

  it('cada dimensao vale UM ponto — a de maior amplitude nao pesa mais', () => {
    // H1 ganha residual por MUITO; H2 ganha populacao e concorrentes por pouco.
    const r = ranquear(
      DIMS,
      [
        { residual: 90000, pop: 10000, conc: 9 },
        { residual: 1000, pop: 30000, conc: 0 },
      ],
      rot(2),
    )
    expect(r.melhor?.rotulo).toBe('H2')
    expect(r.melhor?.vitorias).toBe(2)
  })

  it('dimensao invertida: menos concorrente e vitoria', () => {
    const r = ranquear(DIMS, [{ residual: null, pop: null, conc: 0 }, { residual: null, pop: null, conc: 8 }], rot(2))
    expect(r.melhor?.rotulo).toBe('H1')
  })
})

describe('limiares — ruido nao elege ninguem', () => {
  it('diferenca abaixo do limiar nao da ponto', () => {
    const r = ranquear(
      DIMS,
      [{ residual: 5000, pop: 20000, conc: 3 }, { residual: 5050, pop: 20100, conc: 3 }],
      rot(2),
    )
    expect(r.dimensoesDecisivas).toHaveLength(0)
    expect(r.melhor).toBeNull()
    expect(r.pior).toBeNull()
    expect(r.frase).toContain('equivalentes')
  })

  it('so a dimensao que separa entra em dimensoesDecisivas', () => {
    const r = ranquear(
      DIMS,
      [{ residual: 9000, pop: 20000, conc: 3 }, { residual: 1000, pop: 20050, conc: 3 }],
      rot(2),
    )
    expect(r.dimensoesDecisivas).toEqual(['residual'])
  })
})

describe('empates sao resposta, nao problema a resolver', () => {
  it('empate no topo devolve melhor = null', () => {
    // H1 ganha residual; H2 ganha populacao. Um a um.
    const r = ranquear(
      DIMS,
      [{ residual: 9000, pop: 8000, conc: 3 }, { residual: 1000, pop: 40000, conc: 3 }],
      rot(2),
    )
    expect(r.melhor).toBeNull()
    expect(r.frase).toContain('Não há um melhor')
  })

  it('valores IGUAIS numa dimensao nao elegem ninguem nela', () => {
    const r = ranquear(
      DIMS,
      [{ residual: 9000, pop: 9000, conc: 0 }, { residual: 9000, pop: 1000, conc: 0 }],
      rot(2),
    )
    const d = r.itens[0].porDimensao.find((x) => x.chave === 'residual')!
    expect(d.melhor).toBe(false)
  })
})

describe('dado ausente', () => {
  it('item sem o dado nao vence nem perde aquela dimensao', () => {
    const r = ranquear(
      DIMS,
      [{ residual: null, pop: 50000, conc: 0 }, { residual: 5000, pop: 1000, conc: 9 }],
      rot(2),
    )
    const semDado = r.itens.find((i) => i.indice === 0)!
    const d = semDado.porDimensao.find((x) => x.chave === 'residual')!
    expect(d.posicao).toBeNull()
    expect(d.melhor).toBe(false)
    expect(d.pior).toBe(false)
  })
})

describe('ate 5 itens', () => {
  it('ranqueia cinco e marca melhor e pior', () => {
    const itens: Alvo[] = [
      { residual: 1000, pop: 10000, conc: 8 },
      { residual: 9000, pop: 50000, conc: 0 },
      { residual: 5000, pop: 30000, conc: 4 },
      { residual: 3000, pop: 20000, conc: 6 },
      { residual: 7000, pop: 40000, conc: 2 },
    ]
    const r = ranquear(DIMS, itens, rot(5))
    expect(r.itens).toHaveLength(5)
    expect(r.melhor?.rotulo).toBe('H2')
    expect(r.pior?.rotulo).toBe('H1')
    // Cada item conhece a propria posicao em cada dimensao.
    for (const i of r.itens) expect(i.porDimensao).toHaveLength(DIMS.length)
  })

  it('o teto e 5', () => {
    expect(MAX_COMPARADOS).toBe(5)
  })
})
