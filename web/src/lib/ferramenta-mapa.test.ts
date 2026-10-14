import { describe, expect, it } from 'vitest'

import {
  alternarFerramenta,
  cliqueSelecionaHex,
  cursorDaFerramenta,
  type FerramentaMapa,
} from './ferramenta-mapa'

const TODAS: FerramentaMapa[] = ['nenhuma', 'ponto', 'regua', 'geometria']

describe('alternarFerramenta', () => {
  it('liga a ferramenta tocada quando nada está ligado', () => {
    expect(alternarFerramenta('nenhuma', 'ponto')).toBe('ponto')
    expect(alternarFerramenta('nenhuma', 'regua')).toBe('regua')
    expect(alternarFerramenta('nenhuma', 'geometria')).toBe('geometria')
  })

  it('tocar na mesma desliga', () => {
    expect(alternarFerramenta('ponto', 'ponto')).toBe('nenhuma')
    expect(alternarFerramenta('regua', 'regua')).toBe('nenhuma')
    expect(alternarFerramenta('geometria', 'geometria')).toBe('nenhuma')
  })

  it('exclusão mútua: ligar uma troca a outra, nunca soma', () => {
    expect(alternarFerramenta('regua', 'ponto')).toBe('ponto')
    expect(alternarFerramenta('ponto', 'regua')).toBe('regua')
    expect(alternarFerramenta('ponto', 'geometria')).toBe('geometria')
    expect(alternarFerramenta('geometria', 'regua')).toBe('regua')
  })

  it("'nenhuma' como alvo sempre desliga", () => {
    for (const f of TODAS) expect(alternarFerramenta(f, 'nenhuma')).toBe('nenhuma')
  })
})

describe('cliqueSelecionaHex', () => {
  it('só sem ferramenta o clique abre o hexágono', () => {
    expect(cliqueSelecionaHex('nenhuma')).toBe(true)
    expect(cliqueSelecionaHex('ponto')).toBe(false)
    expect(cliqueSelecionaHex('regua')).toBe(false)
    expect(cliqueSelecionaHex('geometria')).toBe(false)
  })
})

describe('cursorDaFerramenta', () => {
  it('mira com qualquer ferramenta ligada, esteja ou não sobre algo', () => {
    for (const f of ['ponto', 'regua', 'geometria'] as FerramentaMapa[]) {
      expect(cursorDaFerramenta(f, true)).toBe('crosshair')
      expect(cursorDaFerramenta(f, false)).toBe('crosshair')
    }
  })

  it('sem ferramenta, o cursor de sempre', () => {
    expect(cursorDaFerramenta('nenhuma', true)).toBe('pointer')
    expect(cursorDaFerramenta('nenhuma', false)).toBe('grab')
  })
})
