import { describe, expect, it } from 'vitest'

import { ehAreaDesenhada, rotuloDaAreaDesenhada, rotuloDoRaio } from './recorte'
import type { PontoPayload } from './types'

describe('rotuloDoRaio — a ÚNICA escrita do raio na tela', () => {
  it('raio inteiro sai sem ",0" e em km (nunca "1.000 m" num lugar e "1,0 km" no outro)', () => {
    expect(rotuloDoRaio(1)).toBe('raio de 1 km')
    expect(rotuloDoRaio(2)).toBe('raio de 2 km')
  })

  it('raio fracionário com vírgula e uma casa', () => {
    expect(rotuloDoRaio(1.5)).toBe('raio de 1,5 km')
    expect(rotuloDoRaio(1.04)).toBe('raio de 1 km')
  })

  it('sem raio no payload vale o raio padrão do produto', () => {
    expect(rotuloDoRaio(null)).toBe('raio de 1 km')
    expect(rotuloDoRaio(undefined)).toBe('raio de 1 km')
  })
})

describe('rotuloDaAreaDesenhada — a área desenhada continua dizendo a área', () => {
  it('duas casas abaixo de 10 km², uma acima', () => {
    expect(rotuloDaAreaDesenhada(2.4)).toBe('área desenhada de 2,40 km²')
    expect(rotuloDaAreaDesenhada(25.36)).toBe('área desenhada de 25,4 km²')
  })

  it('sem área conhecida não inventa número', () => {
    expect(rotuloDaAreaDesenhada(null)).toBe('área desenhada')
    expect(rotuloDaAreaDesenhada(Number.NaN)).toBe('área desenhada')
  })
})

describe('ehAreaDesenhada — uma definição só', () => {
  const anel = [[[-46.6, -23.5], [-46.5, -23.5], [-46.5, -23.4], [-46.6, -23.5]]]

  it('pela geometria, mesmo com o mercado falho (sem `grao`)', () => {
    const p = { geometria: anel, mercado: { disponivel: false } } as unknown as PontoPayload
    expect(ehAreaDesenhada(p)).toBe(true)
  })

  it('pelo `grao` do mercado quando a geometria não veio', () => {
    expect(ehAreaDesenhada({ mercado: { grao: 'geometria' } } as unknown as PontoPayload)).toBe(true)
  })

  it('ponto com raio, payload antigo e ausência: não é área', () => {
    expect(ehAreaDesenhada({ geometria: null, mercado: { grao: 'raio' } } as unknown as PontoPayload)).toBe(false)
    expect(ehAreaDesenhada({ mercado: {} } as unknown as PontoPayload)).toBe(false)
    expect(ehAreaDesenhada(null)).toBe(false)
    expect(ehAreaDesenhada(undefined)).toBe(false)
  })
})
