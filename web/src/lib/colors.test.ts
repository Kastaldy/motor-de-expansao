import { describe, expect, it } from 'vitest'
import {
  NA_FILL,
  POP_MIN_ACIONAVEL,
  SCORE_BANDS_HEX,
  bandSolid,
  scoreBandToColor,
} from './colors'

describe('scoreBandToColor', () => {
  it('score 0 -> primeira faixa (vermelho 941212) com alpha default 170', () => {
    expect(scoreBandToColor(0)).toEqual([148, 18, 18, 170])
  })
  it('score 100 -> ultima faixa (verde 0A8226); clampa idx em 9', () => {
    expect(scoreBandToColor(100)).toEqual([10, 130, 38, 170])
  })
  it('score 95 cai na faixa 9 (floor(9.5))', () => {
    expect(scoreBandToColor(95)).toEqual([10, 130, 38, 170])
  })
  it('score 55 cai na faixa 5 (EEC828)', () => {
    expect(scoreBandToColor(55)).toEqual([238, 200, 40, 170])
  })
  it('score negativo clampa na faixa 0', () => {
    expect(scoreBandToColor(-5)).toEqual([148, 18, 18, 170])
  })
  it('alpha customizavel', () => {
    expect(scoreBandToColor(50, 100)).toEqual([238, 200, 40, 100])
  })
  it.each([null, undefined, NaN])('sem score -> NA_FILL', (v) => {
    expect(scoreBandToColor(v)).toEqual([120, 120, 140, 70])
  })
  it('devolve COPIA de NA_FILL (mutar o retorno nao corrompe a constante)', () => {
    const c = scoreBandToColor(null)
    c[0] = 999
    expect(NA_FILL[0]).toBe(120)
  })
})

describe('bandSolid / constantes', () => {
  it('sao 10 faixas de 10 pontos', () => {
    expect(SCORE_BANDS_HEX).toHaveLength(10)
  })
  it('bandSolid devolve o hex solido da faixa', () => {
    expect(bandSolid(0)).toBe('#941212')
    expect(bandSolid(9)).toBe('#0A8226')
  })
  it('POP_MIN_ACIONAVEL espelha a regua do dashboard', () => {
    expect(POP_MIN_ACIONAVEL).toBe(5000)
  })
})
