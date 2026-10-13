import { afterEach, describe, expect, it } from 'vitest'

import { brl, brlCurto, definirExibicaoMonetaria } from './format'
import {
  _resetarMoedaParaTeste,
  definirMoedaDeViabilidade,
  fracaoDoPercentual,
  moedaDeViabilidade,
  paraReais,
  reaisPorUnidade,
  trocarDeMoeda,
} from './viabilidade-moeda'

const AR = {
  codigo: 'ARS',
  simbolo: '$',
  local_por_usd: 1397.71,
  brl_por_usd: 4.9837,
  base: '2026-05',
}

describe('reaisPorUnidade', () => {
  it('um dolar vale o cambio do real', () => {
    expect(reaisPorUnidade(AR, 'usd')).toBe(4.9837)
  })

  it('a moeda do pais passa pelo dolar', () => {
    expect(reaisPorUnidade(AR, 'local')).toBeCloseTo(4.9837 / 1397.71, 12)
  })
})

describe('paraReais', () => {
  it('dolares e pesos equivalentes chegam ao MESMO valor em reais', () => {
    // US$ 25 e os pesos que compram US$ 25 sao o mesmo ticket.
    const emDolar = paraReais(25, reaisPorUnidade(AR, 'usd'))
    const emPesos = paraReais(25 * 1397.71, reaisPorUnidade(AR, 'local'))
    expect(emDolar).toBe(124.59)
    expect(emPesos).toBe(124.59)
  })

  it('sai arredondado ao centavo: e o numero que vai ao motor', () => {
    const r = paraReais(35000, reaisPorUnidade(AR, 'local'))!
    expect(r).toBe(Math.round(r * 100) / 100)
    expect(r).toBeCloseTo(124.8, 1)
  })

  it('campo vazio continua vazio; zero e valor legitimo', () => {
    expect(paraReais(undefined, 4.9837)).toBeUndefined()
    expect(paraReais(0, 4.9837)).toBe(0)
  })

  it('negativo, NaN ou cambio invalido nao viram numero', () => {
    expect(paraReais(-1, 4.9837)).toBeUndefined()
    expect(paraReais(Number.NaN, 4.9837)).toBeUndefined()
    expect(paraReais(25, 0)).toBeUndefined()
    expect(paraReais(25, Number.POSITIVE_INFINITY)).toBeUndefined()
  })

  it('com fator 1 (instancia em reais) o valor atravessa intacto', () => {
    expect(paraReais(20000, 1)).toBe(20000)
    expect(paraReais(147, 1)).toBe(147)
  })
})

describe('trocarDeMoeda', () => {
  it('trocar o seletor preserva o cenario, nao o numero', () => {
    const usd = reaisPorUnidade(AR, 'usd')
    const local = reaisPorUnidade(AR, 'local')
    expect(trocarDeMoeda(25, usd, local, 0)).toBe(34943) // 25 x 1397,71
    expect(trocarDeMoeda(34943, local, usd, 2)).toBe(25)
  })

  it('vazio continua vazio', () => {
    expect(trocarDeMoeda(undefined, 1, 2)).toBeUndefined()
  })
})

describe('exibicao monetaria: o resultado em reais lido na moeda escolhida', () => {
  afterEach(() => {
    definirExibicaoMonetaria(null)
  })

  it('sem exibicao definida, brl() fica como sempre foi', () => {
    expect(brl(1000)).toBe('R$ 1.000')
  })

  it('com exibicao em dolares, o valor em reais e convertido e o simbolo troca', () => {
    definirExibicaoMonetaria({ simbolo: 'US$', porReal: 1 / reaisPorUnidade(AR, 'usd') })
    expect(brl(498.37)).toBe('US$ 100')
    expect(brl(124.59, false, 2)).toBe('US$ 25,00')
    expect(brlCurto(4983700)).toBe('US$ 1,0M')
  })

  it('exibicao invalida e ignorada: nunca divide por zero nem imprime Infinity', () => {
    definirExibicaoMonetaria({ simbolo: 'US$', porReal: 0 })
    expect(brl(1000)).toBe('R$ 1.000')
    definirExibicaoMonetaria({ simbolo: '', porReal: 2 })
    expect(brl(1000)).toBe('R$ 1.000')
  })
})

describe('fracaoDoPercentual', () => {
  it('69 (%) vira 0,69 — o contrato do payload e fracao', () => {
    expect(fracaoDoPercentual(69)).toBeCloseTo(0.69, 10)
    expect(fracaoDoPercentual(100)).toBe(1)
    expect(fracaoDoPercentual(0)).toBe(0)
  })

  it('vazio atravessa como undefined, para a chave sumir do JSON', () => {
    expect(fracaoDoPercentual(undefined)).toBeUndefined()
  })

  it('fora de 0–100 nao vira fracao', () => {
    expect(fracaoDoPercentual(-1)).toBeUndefined()
    expect(fracaoDoPercentual(101)).toBeUndefined()
    expect(fracaoDoPercentual(Number.NaN)).toBeUndefined()
  })
})

describe('moeda da viabilidade vinda do perfil', () => {
  afterEach(() => {
    _resetarMoedaParaTeste()
  })

  it('nasce ausente: no Brasil tudo e digitado e lido em reais', () => {
    expect(moedaDeViabilidade()).toBeNull()
  })

  it('instala o que o /api/me serve', () => {
    definirMoedaDeViabilidade(AR)
    expect(moedaDeViabilidade()).toEqual(AR)
  })

  it('payload ausente, incompleto ou com cambio invalido nao instala nada', () => {
    for (const ruim of [
      undefined,
      null,
      'x',
      {},
      { ...AR, local_por_usd: 0 },
      { ...AR, brl_por_usd: -1 },
      { ...AR, brl_por_usd: '4.98' },
      { ...AR, simbolo: '' },
    ]) {
      definirMoedaDeViabilidade(ruim)
      expect(moedaDeViabilidade()).toBeNull()
    }
  })
})
