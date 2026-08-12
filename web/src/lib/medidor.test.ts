import { describe, expect, it } from 'vitest'

import { composicaoMercado, faixaDaDistribuicao, fracaoDoScore } from './medidor'

describe('fracaoDoScore', () => {
  it('mapeia 0-100 para 0-1', () => {
    expect(fracaoDoScore(0)).toBe(0)
    expect(fracaoDoScore(50)).toBe(0.5)
    expect(fracaoDoScore(100)).toBe(1)
  })

  it('score ausente NÃO vira zero — some', () => {
    expect(fracaoDoScore(null)).toBeNull()
    expect(fracaoDoScore(undefined)).toBeNull()
  })

  it('prende fora da escala em vez de vazar a barra', () => {
    expect(fracaoDoScore(140)).toBe(1)
    expect(fracaoDoScore(-10)).toBe(0)
  })
})

describe('composicaoMercado', () => {
  it('reparte o SAM entre atendido e disponível', () => {
    expect(composicaoMercado(10_000, 4_000)).toEqual({
      atendido: 6_000,
      disponivel: 4_000,
      fracaoDisponivel: 0.4,
    })
  })

  it('mercado todo disponível', () => {
    const c = composicaoMercado(2_000, 2_000)
    expect(c).toMatchObject({ atendido: 0, disponivel: 2_000, fracaoDisponivel: 1 })
  })

  it('mercado saturado: residual zero', () => {
    expect(composicaoMercado(5_000, 0)).toMatchObject({ disponivel: 0, fracaoDisponivel: 0 })
  })

  it('residual acima do SAM (arredondamento das duas fontes) é preso ao teto', () => {
    const c = composicaoMercado(1_000, 1_030)
    expect(c).toMatchObject({ atendido: 0, disponivel: 1_000, fracaoDisponivel: 1 })
  })

  it('residual negativo — oferta maior que o mercado — não inverte a barra', () => {
    expect(composicaoMercado(1_000, -200)).toMatchObject({ disponivel: 0, atendido: 1_000 })
  })

  it('sem dado, ou sem mercado para repartir, não desenha nada', () => {
    expect(composicaoMercado(null, 100)).toBeNull()
    expect(composicaoMercado(100, null)).toBeNull()
    expect(composicaoMercado(0, 0)).toBeNull()
  })
})

describe('faixaDaDistribuicao', () => {
  it('posiciona a mediana entre os extremos', () => {
    const f = faixaDaDistribuicao({ min: 0, p50: 25, max: 100, n: 8 })
    expect(f?.posicaoMediana).toBe(0.25)
  })

  it('mediana colada no mínimo e no máximo', () => {
    expect(faixaDaDistribuicao({ min: 10, p50: 10, max: 50, n: 4 })?.posicaoMediana).toBe(0)
    expect(faixaDaDistribuicao({ min: 10, p50: 50, max: 50, n: 4 })?.posicaoMediana).toBe(1)
  })

  it('um setor só não tem dispersão', () => {
    expect(faixaDaDistribuicao({ min: 10, p50: 10, max: 10, n: 1 })).toBeNull()
  })

  it('todos os setores iguais: régua de um ponto não vira barra', () => {
    expect(faixaDaDistribuicao({ min: 30, p50: 30, max: 30, n: 9 })).toBeNull()
  })

  it('extremo ausente derruba a faixa inteira', () => {
    expect(faixaDaDistribuicao({ min: null, p50: 5, max: 9, n: 5 })).toBeNull()
    expect(faixaDaDistribuicao(null)).toBeNull()
  })
})
