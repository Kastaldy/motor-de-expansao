import { describe, expect, it } from 'vitest'

import { FAIXAS_DEMANDA, FAIXAS_POTENCIAL } from './faixas'
import {
  composicaoMercado,
  faixaDoValor,
  fracaoDoScore,
  leituraDeSaturacao,
} from './medidor'

describe('leituraDeSaturacao', () => {
  it('sobra que comporta uma unidade cheia nao vira alerta', () => {
    const l = leituraDeSaturacao(10_000, 3_000)
    expect(l?.tom).toBe('folga')
    expect(l?.frase).toContain('2.500')
  })

  it('no limite exato dos 2.500 ainda e folga', () => {
    expect(leituraDeSaturacao(10_000, 2_500)?.tom).toBe('folga')
  })

  it('sobra menor que uma unidade diz que encher exige tirar aluno', () => {
    const l = leituraDeSaturacao(10_000, 900)
    expect(l?.tom).toBe('disputa')
    expect(l?.frase).toBe(
      'Sobram 900 alunos, menos que os 2.500 de uma unidade cheia: dá para entrar, mas encher a casa exige tirar aluno de concorrente.',
    )
  })

  it('area saturada declara que cada aluno vem de um concorrente', () => {
    const l = leituraDeSaturacao(10_000, 0)
    expect(l?.tom).toBe('saturado')
    expect(l?.frase).toContain('disputa direta')
  })

  it('residual negativo (arredondamento das duas fontes) le como saturado, nao como sobra', () => {
    expect(leituraDeSaturacao(10_000, -50)?.tom).toBe('saturado')
  })

  it('sem dado nao inventa veredito', () => {
    expect(leituraDeSaturacao(null, 900)).toBeNull()
    expect(leituraDeSaturacao(10_000, null)).toBeNull()
    expect(leituraDeSaturacao(0, 0)).toBeNull()
  })
})

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

describe('faixaDoValor', () => {
  it('devolve a faixa nomeada e a cor da rampa publicada', () => {
    expect(faixaDoValor(85, FAIXAS_POTENCIAL)?.nome).toBe('Excelente')
    expect(faixaDoValor(45, FAIXAS_POTENCIAL)?.nome).toBe('Promissor')
    expect(faixaDoValor(5, FAIXAS_POTENCIAL)?.nome).toBe('Desfavorável')
  })

  it('o limite inferior pertence à faixa de cima', () => {
    expect(faixaDoValor(60, FAIXAS_POTENCIAL)?.nome).toBe('Forte')
    expect(faixaDoValor(59.9, FAIXAS_POTENCIAL)?.nome).toBe('Promissor')
  })

  it('score 100 — uma unidade cheia — tem faixa; o topo é inclusivo', () => {
    expect(faixaDoValor(100, FAIXAS_DEMANDA)).not.toBeNull()
  })

  it('sem score, sem faixa — e portanto sem cor inventada', () => {
    expect(faixaDoValor(null, FAIXAS_POTENCIAL)).toBeNull()
    expect(faixaDoValor(undefined, FAIXAS_POTENCIAL)).toBeNull()
  })
})
