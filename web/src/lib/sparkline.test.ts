import { describe, expect, it } from 'vitest'

import { caminhoSparkline, escalaDeBarras } from './sparkline'

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
