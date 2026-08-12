import { describe, expect, it } from 'vitest'

import {
  DIMENSOES,
  MAX_DIMENSOES_NA_FRASE,
  compararComFrase,
  compararHexes,
} from './comparacao'
import type { Hex } from './types'

/** Hexagono neutro; cada teste muda só o que precisa. Valores da ordem de grandeza
 *  do payload real de GO (oferta ~8.694, pop ~42.222, renda ~1.273). */
function hex(over: Partial<Hex> = {}): Hex {
  return {
    id: '87a8c0cc6ffffff',
    lat: -16.68, lng: -49.26,
    m1: 70, censo: 60, hib: 70, res: 100,
    oferta: 5000, sam: 9000, pop: 20000,
    renda: 1500, renda_dom: 4500,
    faixa: 'Alta', conc: 2, ultra: 0,
    mun: 'Goiânia',
    cres_hex_taxa: 10, cres_hex_classe: 'Estável',
    ...over,
  } as Hex
}

describe('DIMENSOES', () => {
  it('segue a ordem de prioridade combinada', () => {
    expect(DIMENSOES.map((d) => d.chave)).toEqual([
      'oferta', 'pop', 'conc', 'renda', 'cres',
    ])
  })

  it('le residual do BRUTO (oferta), nunca do score clipado', () => {
    // `res` empata em 100 para todo hex acima de 2.500 alunos — comparar por ele
    // apagaria a diferenca no topo, que e onde estao os candidatos.
    const dim = DIMENSOES.find((d) => d.chave === 'oferta')!
    const a = hex({ oferta: 8694, res: 100 })
    const b = hex({ oferta: 3000, res: 100 })
    expect(dim.ler(a)).toBe(8694)
    expect(dim.ler(b)).toBe(3000)
    expect(dim.ler(a)).not.toBe(a.res)
  })

  it('concorrentes e a UNICA dimensao onde menor ganha', () => {
    const invertidas = DIMENSOES.filter((d) => !d.maiorEhMelhor).map((d) => d.chave)
    expect(invertidas).toEqual(['conc'])
  })
})

describe('compararHexes', () => {
  it('quem tem mais residual leva a dimensao', () => {
    const d = compararHexes(hex({ oferta: 9000 }), hex({ oferta: 3000 }))
      .find((x) => x.dimensao.chave === 'oferta')!
    expect(d.vencedor).toBe('a')
    expect(d.diferenca).toBe(6000)
    expect(d.desvioRelativo).toBeCloseTo(6000 / 9000, 5)
    expect(d.relevante).toBe(true)
  })

  it('quem tem MENOS concorrente leva a dimensao de concorrencia', () => {
    const d = compararHexes(hex({ conc: 1 }), hex({ conc: 6 }))
      .find((x) => x.dimensao.chave === 'conc')!
    expect(d.vencedor).toBe('a') // 1 < 6
    expect(d.relevante).toBe(true)
  })

  it('dimensao ausente num dos lados nao vira diferenca inventada', () => {
    const d = compararHexes(hex({ cres_hex_taxa: null }), hex({ cres_hex_taxa: 30 }))
      .find((x) => x.dimensao.chave === 'cres')!
    expect(d.diferenca).toBeNull()
    expect(d.relevante).toBe(false)
    expect(d.vencedor).toBe('empate')
  })

  it('zero contra zero e empate, nao NaN', () => {
    const d = compararHexes(hex({ conc: 0 }), hex({ conc: 0 }))
      .find((x) => x.dimensao.chave === 'conc')!
    expect(d.desvioRelativo).toBe(0)
    expect(Number.isNaN(d.desvioRelativo as number)).toBe(false)
    expect(d.vencedor).toBe('empate')
  })
})

describe('limiares — nao afirmar diferenca que e ruido', () => {
  it('2% de diferenca em populacao NAO entra', () => {
    const d = compararHexes(hex({ pop: 20000 }), hex({ pop: 19600 }))
      .find((x) => x.dimensao.chave === 'pop')!
    expect(d.desvioRelativo).toBeLessThan(0.1)
    expect(d.relevante).toBe(false)
  })

  it('1 concorrente contra 2 nao sustenta frase, apesar de ser +100% relativo', () => {
    const d = compararHexes(hex({ conc: 2 }), hex({ conc: 1 }))
      .find((x) => x.dimensao.chave === 'conc')!
    expect(d.desvioRelativo).toBeGreaterThanOrEqual(0.1) // passa no relativo...
    expect(d.relevante).toBe(false) // ...e barra no absoluto (limiar = 1)
  })

  it('precisa passar nos DOIS limiares', () => {
    // 30% relativo, mas 60 alunos de diferenca (limiar absoluto = 100).
    const d = compararHexes(hex({ oferta: 200 }), hex({ oferta: 140 }))
      .find((x) => x.dimensao.chave === 'oferta')!
    expect(d.desvioRelativo).toBeGreaterThan(0.1)
    expect(d.relevante).toBe(false)
  })
})

describe('compararComFrase', () => {
  it('empate total devolve a frase de equivalencia, sem inventar diferenca', () => {
    const c = compararComFrase(hex(), hex())
    expect(c.destaques).toHaveLength(0)
    expect(c.vencedor).toBe('empate')
    expect(c.frase).toBe('Os dois pontos são equivalentes nas leituras disponíveis.')
  })

  it('usa no maximo 3 dimensoes mesmo quando 5 sao relevantes', () => {
    const a = hex({ oferta: 9000, pop: 40000, conc: 0, renda: 3000, cres_hex_taxa: 40 })
    const b = hex({ oferta: 1000, pop: 5000, conc: 8, renda: 900, cres_hex_taxa: 2 })
    const c = compararComFrase(a, b)
    expect(c.deltas.filter((d) => d.relevante).length).toBe(5)
    expect(c.destaques).toHaveLength(MAX_DIMENSOES_NA_FRASE)
    /* A de maior PRIORIDADE entra sempre (residual e' a pergunta do produto); as
       outras duas vagas vao para as de maior DESVIO — aqui concorrentes (0 contra 8,
       desvio 1,0) e crescimento (40 contra 2, desvio 0,95), que separam mais do que
       populacao (0,875). A apresentacao volta a ordem de prioridade. */
    expect(c.destaques.map((d) => d.dimensao.chave)).toEqual(['oferta', 'conc', 'cres'])
  })

  it('monta a frase na voz de A, com "mais" e "menos" corretos', () => {
    const a = hex({ oferta: 9000, conc: 0, pop: 20000 })
    const b = hex({ oferta: 2000, conc: 7, pop: 20000 })
    const c = compararComFrase(a, b, 'O hexágono A', 'o hexágono B')
    expect(c.frase).toContain('mais residual disponível')
    expect(c.frase).toContain('menos concorrentes')
    expect(c.frase).toContain('O hexágono A leva a comparação.')
    // Populacao identica nao pode aparecer.
    expect(c.frase).not.toContain('população')
  })

  it('separa vantagem de desvantagem com "porém" — menos concorrente e GANHO', () => {
    // Par real de GO (Goiatuba x Anapolis) que expos o defeito: enfileirar
    // "menos populacao, menos concorrentes e menos renda" fazia as tres lerem como
    // deficit, quando "menos concorrentes" era a unica vitoria de A.
    const a = hex({ pop: 2138, conc: 0, renda: 1035, oferta: 440, cres_hex_taxa: 10 })
    const b = hex({ pop: 20345, conc: 6, renda: 1709, oferta: 427, cres_hex_taxa: 10 })
    const c = compararComFrase(a, b, 'Goiatuba', 'Anápolis')

    expect(c.frase).toContain('menos concorrentes, porém')
    expect(c.frase).toContain('Anápolis leva a comparação.')
    // O ganho de A vem ANTES do "porém"; os deficits, depois.
    const [antes, depois] = c.frase.split('porém')
    expect(antes).toContain('concorrentes')
    expect(depois).toContain('população')
    expect(depois).toContain('renda per capita')
  })

  it('so vantagens: nao aparece "porém"', () => {
    const c = compararComFrase(hex({ oferta: 9000 }), hex({ oferta: 1000 }), 'A', 'B')
    expect(c.frase).not.toContain('porém')
  })

  it('quando cada lado ganha uma dimensao, declara equilibrio em vez de escolher', () => {
    const a = hex({ oferta: 9000, conc: 8, pop: 20000, renda: 1500, cres_hex_taxa: 10 })
    const b = hex({ oferta: 1000, conc: 0, pop: 20000, renda: 1500, cres_hex_taxa: 10 })
    const c = compararComFrase(a, b)
    expect(c.destaques).toHaveLength(2)
    expect(c.vencedor).toBe('empate')
    expect(c.frase).toContain('se equilibram')
  })

  it('B melhor devolve B como vencedor', () => {
    const c = compararComFrase(hex({ oferta: 1000 }), hex({ oferta: 9000 }), 'A', 'B')
    expect(c.vencedor).toBe('b')
    expect(c.frase).toContain('B leva a comparação.')
    expect(c.frase).toContain('menos residual disponível')
  })

  it('a dimensao de maior prioridade relevante nunca fica de fora', () => {
    // Mesmo quando outras 4 dimensoes tem desvio maior, o residual entra.
    const a = hex({ oferta: 5200, pop: 40000, conc: 0, renda: 3000, cres_hex_taxa: 40 })
    const b = hex({ oferta: 4000, pop: 5000, conc: 9, renda: 800, cres_hex_taxa: 1 })
    const c = compararComFrase(a, b)
    expect(c.destaques[0].dimensao.chave).toBe('oferta')
  })

  it('a frase e DETERMINISTICA: mesma entrada, mesma saida', () => {
    const a = hex({ oferta: 9000, pop: 40000, conc: 1 })
    const b = hex({ oferta: 2000, pop: 10000, conc: 6 })
    expect(compararComFrase(a, b).frase).toBe(compararComFrase(a, b).frase)
  })
})
