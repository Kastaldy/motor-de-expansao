import { describe, expect, it } from 'vitest'

import {
  ALTURA_CABECALHO,
  ALTURA_MINIMA,
  LARGURA_MINIMA,
  LARGURA_PADRAO,
  MARGEM,
  VISIVEL_MINIMO,
  geometriaPadrao,
  mover,
  reajustar,
  redimensionar,
  type Geometria,
} from './janela'

const AREA = { largura: 1200, altura: 800 }
const TOPO = 88
const RECUO = 96

describe('geometriaPadrao', () => {
  it('nasce encostada à direita, entre o cabeçalho e o stepper', () => {
    const g = geometriaPadrao(AREA, TOPO, RECUO)
    expect(g.largura).toBe(LARGURA_PADRAO)
    expect(g.x + g.largura).toBe(AREA.largura - MARGEM)
    expect(g.y).toBe(TOPO)
    // O pé da janela para exatamente onde o stepper começa.
    expect(g.y + g.altura).toBe(AREA.altura - RECUO)
  })

  it('em área estreita encolhe em vez de vazar', () => {
    const g = geometriaPadrao({ largura: 400, altura: 800 }, TOPO, RECUO)
    expect(g.largura).toBeLessThanOrEqual(400 - 2 * MARGEM)
    expect(g.x).toBeGreaterThanOrEqual(0)
  })

  it('respeita a altura mínima mesmo sem espaço vertical', () => {
    const g = geometriaPadrao({ largura: 1200, altura: 150 }, TOPO, RECUO)
    expect(g.altura).toBe(ALTURA_MINIMA)
  })

  it('ancorada à esquerda nasce na margem oposta, sem tocar no tamanho', () => {
    const esq = geometriaPadrao(AREA, TOPO, RECUO, 'esquerda')
    const dir = geometriaPadrao(AREA, TOPO, RECUO, 'direita')
    expect(esq.x).toBe(MARGEM)
    expect(esq.largura).toBe(dir.largura)
    expect(esq.altura).toBe(dir.altura)
    // Duas janelas na mesma tela não podem nascer uma sobre a outra.
    expect(esq.x).not.toBe(dir.x)
  })
})

describe('mover', () => {
  const base: Geometria = { x: 600, y: 100, largura: 520, altura: 400 }

  it('move pelo delta quando há espaço', () => {
    expect(mover(base, -50, 30, AREA)).toMatchObject({ x: 550, y: 130 })
  })

  it('deixa sair pela esquerda, mas guarda alça para o retorno', () => {
    const g = mover(base, -5000, 0, AREA)
    expect(g.x).toBe(VISIVEL_MINIMO - base.largura)
    // O que sobra visível é exatamente a alça mínima.
    expect(g.x + g.largura).toBe(VISIVEL_MINIMO)
  })

  it('nunca some pela direita', () => {
    const g = mover(base, 5000, 0, AREA)
    expect(g.x).toBe(AREA.largura - VISIVEL_MINIMO)
  })

  it('não deixa a barra de título subir acima do topo', () => {
    expect(mover(base, 0, -5000, AREA).y).toBe(0)
  })

  it('não deixa a barra de título afundar abaixo do pé', () => {
    expect(mover(base, 0, 5000, AREA).y).toBe(AREA.altura - ALTURA_CABECALHO)
  })

  it('não altera o tamanho', () => {
    const g = mover(base, 40, 40, AREA)
    expect(g.largura).toBe(base.largura)
    expect(g.altura).toBe(base.altura)
  })
})

describe('redimensionar', () => {
  const base: Geometria = { x: 200, y: 100, largura: 520, altura: 400 }

  it('cresce pelo canto sem mexer na posição', () => {
    const g = redimensionar(base, 80, 60, AREA)
    expect(g).toMatchObject({ x: 200, y: 100, largura: 600, altura: 460 })
  })

  it('para nos mínimos utilizáveis', () => {
    const g = redimensionar(base, -5000, -5000, AREA)
    expect(g.largura).toBe(LARGURA_MINIMA)
    expect(g.altura).toBe(ALTURA_MINIMA)
  })

  it('não cresce além da borda a partir da posição atual', () => {
    const g = redimensionar(base, 5000, 5000, AREA)
    expect(g.largura).toBe(AREA.largura - base.x)
    expect(g.altura).toBe(AREA.altura - base.y)
  })
})

describe('reajustar', () => {
  it('traz de volta a janela que ficou fora depois de a tela encolher', () => {
    const g = reajustar({ x: 1100, y: 700, largura: 520, altura: 400 }, { largura: 700, altura: 500 })
    expect(g.x).toBeLessThanOrEqual(700 - VISIVEL_MINIMO)
    expect(g.y).toBeLessThanOrEqual(500 - ALTURA_CABECALHO)
    expect(g.largura).toBeLessThanOrEqual(700)
  })

  it('não mexe em quem já cabe', () => {
    const dentro: Geometria = { x: 100, y: 100, largura: 520, altura: 400 }
    expect(reajustar(dentro, AREA)).toEqual(dentro)
  })

  it('sobrevive a uma área menor que os próprios mínimos', () => {
    const g = reajustar({ x: 10, y: 10, largura: 520, altura: 400 }, { largura: 100, altura: 80 })
    expect(g.largura).toBe(LARGURA_MINIMA)
    expect(g.altura).toBe(ALTURA_MINIMA)
    expect(Number.isFinite(g.x)).toBe(true)
    expect(Number.isFinite(g.y)).toBe(true)
  })
})
