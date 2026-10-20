import { describe, expect, it } from 'vitest'

import {
  ehAreaDesenhada,
  minutosDoRecorte,
  rotuloDaAreaDesenhada,
  rotuloDaIsocrona,
  rotuloDoRaio,
  tipoDoRecorte,
} from './recorte'
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

/* ---------------- Alcance (DEC-074) ---------------- */
describe('tipoDoRecorte e a isócrona', () => {
  const mercado = { disponivel: true, sam: 1, residual: 1, score_residual: 1 }

  it('o tipo do servidor manda', () => {
    for (const tipo of ['raio_1km', 'raio_2km', 'carro_5min', 'carro_10min', 'poligono'] as const) {
      expect(tipoDoRecorte({ recorte: { tipo, area_km2: 1, metodo: 'x' } })).toBe(tipo)
    }
  })

  it('payload anterior à chave: área pelo desenho, senão o raio pelo `raio_km`', () => {
    expect(tipoDoRecorte({ raio_km: 1, mercado } as PontoPayload)).toBe('raio_1km')
    expect(tipoDoRecorte({ raio_km: 2, mercado } as PontoPayload)).toBe('raio_2km')
    expect(tipoDoRecorte({ raio_km: null, mercado: { ...mercado, grao: 'geometria' } } as PontoPayload)).toBe(
      'poligono',
    )
  })

  it('a isócrona tem mercado de GEOMETRIA no servidor, mas NÃO é área desenhada', () => {
    const iso = {
      mercado: { ...mercado, grao: 'geometria' },
      recorte: { tipo: 'carro_10min', area_km2: 38.2, metodo: 'x' },
    } as PontoPayload
    expect(ehAreaDesenhada(iso)).toBe(false)
    // O desenho à mão continua área, com ou sem o tipo no payload.
    expect(ehAreaDesenhada({ ...iso, recorte: { tipo: 'poligono', area_km2: 1, metodo: 'x' } })).toBe(true)
  })

  it('"10 min de carro, sem trânsito", com a área quando ela vem', () => {
    expect(rotuloDaIsocrona(38.21)).toBe('10 min de carro, sem trânsito · 38,2 km²')
    expect(rotuloDaIsocrona(7.5)).toBe('10 min de carro, sem trânsito · 7,50 km²')
    expect(rotuloDaIsocrona(null)).toBe('10 min de carro, sem trânsito')
  })

  it('5 min de carro (Emenda 1 da DEC-074): o mesmo rótulo com o tempo dela', () => {
    expect(rotuloDaIsocrona(3.17, 5)).toBe('5 min de carro, sem trânsito · 3,17 km²')
    expect(rotuloDaIsocrona(null, 5)).toBe('5 min de carro, sem trânsito')
    expect(minutosDoRecorte('carro_5min')).toBe(5)
    expect(minutosDoRecorte('carro_10min')).toBe(10)
    expect(minutosDoRecorte('raio_2km')).toBeNull()
    expect(minutosDoRecorte('poligono')).toBeNull()
    const cinco = {
      mercado: { ...mercado, grao: 'geometria' },
      recorte: { tipo: 'carro_5min', area_km2: 3.2, metodo: 'x' },
    } as PontoPayload
    expect(ehAreaDesenhada(cinco)).toBe(false)
  })
})
