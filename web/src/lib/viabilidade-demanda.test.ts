import { afterEach, describe, expect, it } from 'vitest'

import {
  _resetarAvisoParaTeste,
  avisoDeViabilidade,
  definirAvisoDeViabilidade,
  sementeDaDemanda,
} from './viabilidade-demanda'

describe('sementeDaDemanda', () => {
  it('sem p50 e sem demanda anterior NAO inventa numero', () => {
    // Era aqui que o 800 fixo entrava: instancia sem base de comparaveis (a AR)
    // devolve p50 null, e a tela calculava sozinha com 800 alunos.
    expect(sementeDaDemanda(null, null)).toBeNull()
    expect(sementeDaDemanda(undefined, null)).toBeNull()
  })

  it('com p50, semeia no p50 arredondado', () => {
    expect(sementeDaDemanda(2385.4, null)).toBe(2385)
    expect(sementeDaDemanda(2385.6, 1200)).toBe(2386)
  })

  it('sem p50, preserva a demanda que o operador ja tinha', () => {
    expect(sementeDaDemanda(null, 1500)).toBe(1500)
  })

  it('p50 invalido (NaN, zero, negativo) conta como ausente', () => {
    expect(sementeDaDemanda(Number.NaN, null)).toBeNull()
    expect(sementeDaDemanda(0, null)).toBeNull()
    expect(sementeDaDemanda(-10, 900)).toBe(900)
  })
})

describe('aviso de viabilidade do perfil', () => {
  afterEach(() => {
    _resetarAvisoParaTeste()
  })

  it('nasce ausente: o Brasil nao declara aviso', () => {
    expect(avisoDeViabilidade()).toBeNull()
  })

  it('instala titulo e texto vindos do /api/me', () => {
    definirAvisoDeViabilidade({ titulo: 'Simulacao provisoria', texto: 'Conta em reais.' })
    expect(avisoDeViabilidade()).toEqual({
      titulo: 'Simulacao provisoria',
      texto: 'Conta em reais.',
    })
  })

  it('payload ausente ou malformado nao instala nada nem derruba o app', () => {
    for (const ruim of [undefined, null, 'x', {}, { titulo: 'so titulo' }, { titulo: '', texto: '' }]) {
      definirAvisoDeViabilidade(ruim)
      expect(avisoDeViabilidade()).toBeNull()
    }
  })
})
