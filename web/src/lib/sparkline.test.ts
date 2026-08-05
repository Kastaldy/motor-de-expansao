import { describe, expect, it } from 'vitest'

import { caminhoSparkline, escalaDeBarras, fatiasDeRosca, percentualDaFatia } from './sparkline'

describe('caminhoSparkline', () => {
  it('desenha a série e marca o último ponto', () => {
    const s = caminhoSparkline([1, 2, 3, 4], 100, 20)
    expect(s.linha.startsWith('M')).toBe(true)
    expect(s.linha.split('L')).toHaveLength(4)
    expect(s.ultimo).not.toBeNull()
    expect(s.minimo).toBe(1)
    expect(s.maximo).toBe(4)
  })

  it('série toda igual não divide por zero', () => {
    // Uma unidade estável desenharia NaN no caminho e sumiria da tela sem erro nenhum.
    const s = caminhoSparkline([500, 500, 500], 100, 20)
    expect(s.linha).not.toContain('NaN')
    expect(s.linha).toContain('10.00') // reta no meio da caixa
  })

  it('um ponto só não estoura', () => {
    const s = caminhoSparkline([42], 100, 20)
    expect(s.linha).not.toContain('NaN')
    expect(s.area).toBe('')
  })

  it('série vazia devolve caminho vazio', () => {
    expect(caminhoSparkline([], 100, 20)).toMatchObject({ linha: '', area: '', ultimo: null })
    expect(caminhoSparkline([null, null], 100, 20).linha).toBe('')
  })

  it('buraco no meio não vira NaN nem quebra a linha', () => {
    const s = caminhoSparkline([10, null, 30], 100, 20)
    expect(s.linha).not.toContain('NaN')
    expect(s.linha.split('L')).toHaveLength(2)
  })

  it('maior valor fica no topo da caixa', () => {
    const s = caminhoSparkline([0, 100], 100, 20, 0)
    expect(s.ultimo?.y).toBeCloseTo(0)
  })
})

describe('escalaDeBarras', () => {
  it('escala pela maior barra, com base em ZERO', () => {
    // Base no mínimo faria uma variação de 2% parecer queda pela metade — é o
    // defeito da escala congelada do bloco diário da planilha do time.
    expect(escalaDeBarras([50, 100])).toEqual([0.5, 1])
  })

  it('série toda zero não divide por zero', () => {
    expect(escalaDeBarras([0, 0])).toEqual([0, 0])
  })

  it('negativo mantém o sinal e escala pelo módulo', () => {
    expect(escalaDeBarras([-100, 50])).toEqual([-1, 0.5])
  })

  it('buraco vira zero, não NaN', () => {
    expect(escalaDeBarras([null, 10, undefined])).toEqual([0, 1, 0])
  })
})

describe('fatiasDeRosca', () => {
  const cores = { a: '#0a7', b: '#c39' }

  it('duas fatias somam a volta inteira', () => {
    const { fatias, total, perimetro } = fatiasDeRosca(
      [
        { rotulo: 'Recorrentes', valor: 906, cor: cores.a },
        { rotulo: 'Agregadores', valor: 713, cor: cores.b },
      ],
      50,
    )
    expect(total).toBe(1619)
    expect(fatias[0].fracao + fatias[1].fracao).toBeCloseTo(1)
    // a segunda fatia começa exatamente onde a primeira termina
    expect(fatias[1].deslocamento).toBeCloseTo(-perimetro * fatias[0].fracao)
  })

  it('fatia de 100% fecha a volta', () => {
    // Foi o caso que a versão em Python errou: uma unidade sem NENHUM agregador
    // desenhava 100% como um setor mordido.
    const { fatias, perimetro } = fatiasDeRosca(
      [
        { rotulo: 'Recorrentes', valor: 3870, cor: cores.a },
        { rotulo: 'Agregadores', valor: 0, cor: cores.b },
      ],
      50,
    )
    expect(fatias[0].fracao).toBe(1)
    expect(fatias[0].traco).toBe(`${perimetro} 0`)
    expect(fatias[1].fracao).toBe(0)
  })

  it('fatia vazia não desloca a seguinte', () => {
    const { fatias } = fatiasDeRosca(
      [
        { rotulo: 'vazia', valor: 0, cor: cores.a },
        { rotulo: 'cheia', valor: 10, cor: cores.b },
      ],
      50,
    )
    expect(fatias[1].deslocamento).toBe(-0)
  })

  it('total zero não divide por zero', () => {
    const { fatias, total } = fatiasDeRosca(
      [
        { rotulo: 'a', valor: 0, cor: cores.a },
        { rotulo: 'b', valor: 0, cor: cores.b },
      ],
      50,
    )
    expect(total).toBe(0)
    expect(fatias.every((f) => f.fracao === 0 && !Number.isNaN(f.deslocamento))).toBe(true)
    expect(fatias.every((f) => !f.traco.includes('NaN'))).toBe(true)
  })

  it('valor negativo não vira fatia', () => {
    const { fatias, total } = fatiasDeRosca(
      [
        { rotulo: 'a', valor: -5, cor: cores.a },
        { rotulo: 'b', valor: 10, cor: cores.b },
      ],
      50,
    )
    expect(total).toBe(10)
    expect(fatias[0].fracao).toBe(0)
    expect(fatias[1].fracao).toBe(1)
  })

  it('percentualDaFatia devolve null sem base', () => {
    expect(percentualDaFatia(5, 20)).toBe(25)
    expect(percentualDaFatia(0, 0)).toBeNull()
  })
})
