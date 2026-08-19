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

describe('empate dentro do parametro', () => {
  it('divide a posicao em vez de ordenar por quem foi colado antes', () => {
    // Dois residuais IDENTICOS (0) e um terceiro bem acima: a dimensao separa, mas os
    // dois de baixo empatam. Antes saiam como 2o e 3o, decididos pela ordem da lista.
    const alvos: Alvo[] = [
      { residual: 0, pop: 10000, conc: 3 },
      { residual: 5000, pop: 20000, conc: 3 },
      { residual: 0, pop: 30000, conc: 3 },
    ]
    const r = ranquear(DIMS, alvos, rot(3))
    const posicao = (rotulo: string) =>
      r.itens.find((it) => it.rotulo === rotulo)!.porDimensao.find((d) => d.chave === 'residual')!
        .posicao
    expect(posicao('H2')).toBe(1)
    expect(posicao('H1')).toBe(2)
    expect(posicao('H3')).toBe(2)
  })

  it('nao muda a posicao quando a ordem de entrada muda', () => {
    const a: Alvo = { residual: 0, pop: 10000, conc: 3 }
    const b: Alvo = { residual: 5000, pop: 20000, conc: 3 }
    const c: Alvo = { residual: 0, pop: 30000, conc: 3 }
    const residual = (r: ReturnType<typeof ranquear>, i: number) =>
      r.itens.find((it) => it.indice === i)!.porDimensao.find((d) => d.chave === 'residual')!.posicao
    const direta = ranquear(DIMS, [a, b, c], rot(3))
    const trocada = ranquear(DIMS, [c, b, a], rot(3))
    // O primeiro colado e o ultimo colado tem o MESMO residual: nenhum dos dois pode
    // ficar atras do outro so' por ter sido digitado depois.
    expect(residual(direta, 0)).toBe(residual(trocada, 2))
    expect(residual(direta, 2)).toBe(residual(trocada, 0))
  })

  it('o pior segue marcado quando a base NAO empata', () => {
    const r = ranquear(
      DIMS,
      [
        { residual: 9000, pop: 50000, conc: 1 },
        { residual: 9000, pop: 20000, conc: 1 },
        { residual: 1000, pop: 8000, conc: 9 },
      ],
      rot(3),
    )
    const dim = (rotulo: string) =>
      r.itens.find((it) => it.rotulo === rotulo)!.porDimensao.find((d) => d.chave === 'residual')!
    expect(dim('H3').posicao).toBe(3)
    expect(dim('H3').pior).toBe(true)
    // Topo empatado: a dimensao separa, mas nao elege ninguem.
    expect(dim('H1').melhor).toBe(false)
    expect(dim('H2').melhor).toBe(false)
  })
})

describe('o denominador do "lidera em X/N" e fixo', () => {
  /** O que a tela e o deck usam de denominador: o conjunto de parametros comparados. */
  const denominador = (r: ReturnType<typeof ranquear>) => r.itens[0].porDimensao.length

  it('nao muda ao acrescentar itens a comparacao', () => {
    // O MESMO alvo, comparado contra dois, tres e quatro outros.
    const foco: Alvo = { residual: 9000, pop: 50000, conc: 1 }
    const outros: Alvo[] = [
      { residual: 3000, pop: 20000, conc: 1 },
      { residual: 1000, pop: 8000, conc: 9 },
      { residual: 500, pop: 4000, conc: 12 },
    ]
    const vistos = new Set<number>()
    for (let n = 1; n <= outros.length; n++) {
      const r = ranquear(DIMS, [foco, ...outros.slice(0, n)], rot(n + 1))
      vistos.add(denominador(r))
    }
    expect(vistos).toEqual(new Set([DIMS.length]))
  })

  it('as vitorias somadas podem NAO fechar o total — o resto e "ninguem lidera"', () => {
    const r = ranquear(
      DIMS,
      [
        // `conc` 1, 1 e 9: separa, mas o topo empata e ninguem leva este parametro.
        { residual: 9000, pop: 50000, conc: 1 },
        { residual: 3000, pop: 20000, conc: 1 },
        { residual: 1000, pop: 8000, conc: 9 },
      ],
      rot(3),
    )
    const soma = r.itens.reduce((s, it) => s + it.vitorias, 0)
    expect(denominador(r)).toBe(3)
    expect(soma).toBe(2)
    // E o parametro sem lider continua declarado como decisivo, para a tabela nao
    // apagar a linha: ele separou o pior, so' nao elegeu um primeiro.
    expect(r.dimensoesDecisivas).toContain('conc')
    expect(r.itens.every((it) => !it.porDimensao.find((d) => d.chave === 'conc')!.melhor)).toBe(
      true,
    )
  })
})

describe('empate e a contagem de vitorias, so ela', () => {
  it('nao desempata por menos derrotas', () => {
    // H1 lidera residual e pop; H2 lidera conc; H3 nao lidera nada e perde em tudo.
    // Antes, quem tivesse menos derrotas com as MESMAS vitorias virava "o melhor".
    const r = ranquear(
      DIMS,
      [
        { residual: 9000, pop: 50000, conc: 8 },
        { residual: 1000, pop: 8000, conc: 0 },
      ],
      rot(2),
    )
    // Um lidera duas dimensoes e o outro uma: NAO ha empate aqui, e deve haver melhor.
    expect(r.melhor?.rotulo).toBe('H1')
  })

  it('mesma contagem de vitorias = sem melhor, ainda que as derrotas diferem', () => {
    const r = ranquear(
      DIMS,
      [
        // H1 lidera residual; H2 lidera pop; H3 lidera conc. Um cada.
        { residual: 9000, pop: 8000, conc: 5 },
        { residual: 1000, pop: 50000, conc: 5 },
        { residual: 3000, pop: 20000, conc: 0 },
      ],
      rot(3),
    )
    const vitorias = r.itens.map((it) => it.vitorias)
    expect(new Set(vitorias).size).toBe(1)
    expect(r.melhor).toBeNull()
    expect(r.frase).toContain('Não há um melhor')
  })

  it('a BASE empata por derrotas, nao por vitorias', () => {
    const r = ranquear(
      DIMS,
      [
        { residual: 9000, pop: 50000, conc: 0 },
        // Os dois de baixo sao IDENTICOS: em cada dimensao eles dividem o fundo, entao
        // nenhum acumula derrota e nenhum pode ser apontado como o pior.
        { residual: 1000, pop: 8000, conc: 9 },
        { residual: 1000, pop: 8000, conc: 9 },
      ],
      rot(3),
    )
    const ultimos = r.itens.slice(-2)
    expect(ultimos[0].derrotas).toBe(ultimos[1].derrotas)
    expect(r.pior).toBeNull()
  })

  it('sem vitoria nenhuma, ainda ha pior — quem fica atras em mais dimensoes', () => {
    /* O caso que mostra por que a base NAO pode medir vitorias: H1 leva as tres, H2 e H3
       ficam com zero vitoria cada, mas so' H3 fica atras em tudo. Medir por vitorias
       empataria os dois e o deck deixaria de nomear o pior. */
    const r = ranquear(
      DIMS,
      [
        { residual: 9000, pop: 50000, conc: 0 },
        { residual: 3000, pop: 20000, conc: 6 },
        { residual: 1000, pop: 8000, conc: 9 },
      ],
      rot(3),
    )
    expect(r.itens.map((it) => it.vitorias).filter((v) => v === 0)).toHaveLength(2)
    expect(r.pior?.rotulo).toBe('H3')
  })
})

describe('portao do estudo — so fala no empate', () => {
  /** Alvo com um "passa em tudo" acoplado, para exercitar `opcoes.aprovado`. */
  type ComEstudo = Alvo & { ok: boolean | null }
  const aprovado = (x: ComEstudo) => x.ok

  it('desempata o topo quando um passa em tudo e o outro nao', () => {
    const r = ranquear(
      DIMS,
      [
        // Um lidera residual; o outro lidera pop. Empate em vitorias.
        { residual: 9000, pop: 8000, conc: 5, ok: true },
        { residual: 1000, pop: 50000, conc: 5, ok: false },
      ] as ComEstudo[],
      rot(2),
      { aprovado },
    )
    expect(r.itens[0].vitorias).toBe(r.itens[1].vitorias)
    expect(r.melhor?.rotulo).toBe('H1')
    expect(r.itens[0].posicao).toBe(1)
    expect(r.itens[1].posicao).toBe(2)
    expect(r.frase).toContain('lideram o mesmo número de parâmetros')
    expect(r.frase).toContain('passa em todos os critérios do estudo')
  })

  it('NAO fala quando a contagem de parametros ja separa', () => {
    const r = ranquear(
      DIMS,
      [
        // H1 lidera as tres, e mesmo reprovando no estudo continua o melhor: o portao
        // nao inverte o que a comparacao decidiu, so' desempata o que ela nao decidiu.
        { residual: 9000, pop: 50000, conc: 0, ok: false },
        { residual: 1000, pop: 8000, conc: 9, ok: true },
      ] as ComEstudo[],
      rot(2),
      { aprovado },
    )
    expect(r.melhor?.rotulo).toBe('H1')
    expect(r.frase).not.toContain('critérios do estudo')
  })

  it('segue empatado quando os dois passam, ou os dois reprovam', () => {
    const par = (ok: boolean): ComEstudo[] => [
      { residual: 9000, pop: 8000, conc: 5, ok },
      { residual: 1000, pop: 50000, conc: 5, ok },
    ]
    for (const ok of [true, false]) {
      const r = ranquear(DIMS, par(ok), rot(2), { aprovado })
      expect(r.melhor).toBeNull()
      expect(r.itens[0].posicao).toBe(1)
      expect(r.itens[1].posicao).toBe(1)
    }
  })

  it('sem criterio avaliado o portao se cala — empate continua empate', () => {
    const r = ranquear(
      DIMS,
      [
        { residual: 9000, pop: 8000, conc: 5, ok: null },
        { residual: 1000, pop: 50000, conc: 5, ok: false },
      ] as ComEstudo[],
      rot(2),
      { aprovado },
    )
    expect(r.melhor).toBeNull()
  })

  it('sem `aprovado` nada muda — e o caso dos hexagonos', () => {
    const alvos: Alvo[] = [
      { residual: 9000, pop: 8000, conc: 5 },
      { residual: 1000, pop: 50000, conc: 5 },
    ]
    const r = ranquear(DIMS, alvos, rot(2))
    expect(r.melhor).toBeNull()
    expect(r.itens.map((it) => it.posicao)).toEqual([1, 1])
  })
})

describe('posicao publicada no item', () => {
  it('compartilha no empate e pula a seguinte (1, 1, 3)', () => {
    const r = ranquear(
      DIMS,
      [
        { residual: 9000, pop: 8000, conc: 5 },
        { residual: 1000, pop: 50000, conc: 5 },
        { residual: 1200, pop: 8500, conc: 5 },
      ],
      rot(3),
    )
    const posicoes = r.itens.map((it) => it.posicao)
    expect(posicoes[0]).toBe(1)
    expect(posicoes[1]).toBe(1)
    expect(posicoes[2]).toBe(3)
  })
})

describe('regressoes da revisao de 19/08', () => {
  type ComEstudo = Alvo & { ok: boolean | null }
  const aprovado = (x: ComEstudo) => x.ok

  it('o portao NAO reordena o fundo da lista', () => {
    /* O caso do revisor: B fica no MEIO de todos os parametros e nao perde nenhum; C
       perde os tres. O portao reprovava B e aprovava C, e com ele valendo como criterio
       global de ordenacao o B saia em ultimo e era chamado de "o pior". */
    const r = ranquear(
      DIMS,
      [
        { residual: 9000, pop: 50000, conc: 0, ok: true },
        { residual: 3000, pop: 20000, conc: 6, ok: false },
        { residual: 1000, pop: 8000, conc: 9, ok: true },
      ] as ComEstudo[],
      rot(3),
      { aprovado },
    )
    const porRotulo = (n: string) => r.itens.find((it) => it.rotulo === n)!
    expect(porRotulo('H2').derrotas).toBe(0)
    expect(porRotulo('H3').derrotas).toBe(3)
    /* Os dois lideram ZERO parametros, entao dividem a posicao — o portao nao fala aqui,
       e a posicao ranqueia lideranca. O que os separa e' a outra leitura: quem perdeu em
       todas as dimensoes e' o pior, e quem nao perdeu nenhuma nao pode ser. */
    expect(porRotulo('H2').posicao).toBe(porRotulo('H3').posicao)
    expect(r.pior?.rotulo).toBe('H3')
    // E a lista poe embaixo quem perdeu mais, nao quem o portao reprovou.
    expect(r.itens[r.itens.length - 1].rotulo).toBe('H3')
  })

  it('o pior sai da METRICA, e nao da ultima linha da lista', () => {
    // O ultimo da lista tem ZERO derrotas; quem perdeu foi o do meio.
    const r = ranquear(
      DIMS,
      [
        { residual: 9000, pop: 50000, conc: 0 },
        { residual: 1000, pop: 8000, conc: 9 },
        { residual: 3000, pop: 20000, conc: 6 },
      ],
      rot(3),
    )
    const maxDerrotas = Math.max(...r.itens.map((it) => it.derrotas))
    expect(r.pior?.derrotas).toBe(maxDerrotas)
    expect(maxDerrotas).toBeGreaterThan(0)
  })

  it('a frase nunca sai com "e undefined"', () => {
    /* Antes: `pior` com zero derrotas caia no ramo de lista vazia e a frase — que vai
       inteira para o PDF do locador — imprimia "fica atras em  e undefined". */
    const casos: Alvo[][] = [
      [
        { residual: 9000, pop: 50000, conc: 0 },
        { residual: 3000, pop: 20000, conc: 6 },
        { residual: 1000, pop: 8000, conc: 9 },
      ],
      [
        { residual: 9000, pop: 50000, conc: 0 },
        { residual: 8900, pop: 49000, conc: 1 },
      ],
      [
        { residual: 0, pop: 10000, conc: 3 },
        { residual: 5000, pop: 20000, conc: 3 },
        { residual: 0, pop: 30000, conc: 3 },
      ],
    ]
    for (const alvos of casos) {
      const r = ranquear(DIMS, alvos, rot(alvos.length))
      expect(r.frase).not.toContain('undefined')
      expect(r.frase).not.toMatch(/em\s{2,}/)
      expect(r.frase.trim().endsWith('.')).toBe(true)
    }
  })

  it('o portao continua desempatando o TOPO', () => {
    const r = ranquear(
      DIMS,
      [
        { residual: 9000, pop: 8000, conc: 5, ok: true },
        { residual: 1000, pop: 50000, conc: 5, ok: false },
      ] as ComEstudo[],
      rot(2),
      { aprovado },
    )
    expect(r.melhor?.rotulo).toBe('H1')
    expect(r.itens[0].posicao).toBe(1)
    expect(r.itens[1].posicao).toBe(2)
  })
})
