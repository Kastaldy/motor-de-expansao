import { describe, expect, it } from 'vitest'
import {
  type AlvoMedicao,
  TOLERANCIA_TRAVA_PX,
  distanciaMetros,
  metrosPorPixel,
  travarNoAlvo,
} from './medicao'

const PAULISTA = { lat: -23.5614, lng: -46.6559 }

describe('distanciaMetros', () => {
  it('ponto contra ele mesmo e zero', () => {
    expect(distanciaMetros(PAULISTA, PAULISTA)).toBe(0)
  })

  it('1 grau de latitude vale ~111,2 km', () => {
    const d = distanciaMetros({ lat: 0, lng: 0 }, { lat: 1, lng: 0 })
    expect(d).toBeGreaterThan(111_000)
    expect(d).toBeLessThan(111_400)
  })

  it('confere contra uma distancia conhecida (Paulista -> Ibirapuera, ~2,7 km)', () => {
    const d = distanciaMetros(PAULISTA, { lat: -23.5874, lng: -46.6576 })
    expect(d).toBeGreaterThan(2_800)
    expect(d).toBeLessThan(3_000)
  })

  it('e simetrica', () => {
    const a = { lat: -23.55, lng: -46.63 }
    const b = { lat: -23.57, lng: -46.65 }
    expect(distanciaMetros(a, b)).toBeCloseTo(distanciaMetros(b, a), 6)
  })
})

describe('metrosPorPixel', () => {
  it('cai pela metade a cada zoom', () => {
    expect(metrosPorPixel(13, 0) / metrosPorPixel(14, 0)).toBeCloseTo(2, 6)
  })

  it('encolhe longe do equador (cos da latitude)', () => {
    expect(metrosPorPixel(14, -23.5)).toBeLessThan(metrosPorPixel(14, 0))
  })
})

const ALVOS: AlvoMedicao[] = [
  { lat: -23.5614, lng: -46.6559, rotulo: 'Smart Fit - Paulista', tipo: 'concorrente' },
  { lat: -23.5650, lng: -46.6600, rotulo: 'Ultra Academia', tipo: 'ultra' },
]

describe('travarNoAlvo', () => {
  const mpp = metrosPorPixel(15, -23.56)

  it('clique em cima do pin trava nele', () => {
    const alvo = travarNoAlvo({ lat: -23.56141, lng: -46.65591 }, ALVOS, mpp)
    expect(alvo?.rotulo).toBe('Smart Fit - Paulista')
  })

  it('clique longe de todos nao trava (medicao livre)', () => {
    expect(travarNoAlvo({ lat: -23.6, lng: -46.7 }, ALVOS, mpp)).toBeNull()
  })

  it('entre dois pins na tolerancia, trava no MAIS PROXIMO', () => {
    // Ponto deslocado na direcao do Ultra, com tolerancia larga (zoom de cidade).
    const largo = metrosPorPixel(11, -23.56)
    const alvo = travarNoAlvo({ lat: -23.5649, lng: -46.6599 }, ALVOS, largo)
    expect(alvo?.rotulo).toBe('Ultra Academia')
  })

  it('sem alvos nao trava', () => {
    expect(travarNoAlvo(PAULISTA, [], mpp)).toBeNull()
  })

  it('zoom mais fechado APERTA a trava: o mesmo clique deixa de imantar', () => {
    const clique = { lat: -23.5619, lng: -46.6564 }
    expect(travarNoAlvo(clique, ALVOS, metrosPorPixel(14, -23.56))?.rotulo).toBe(
      'Smart Fit - Paulista',
    )
    expect(travarNoAlvo(clique, ALVOS, metrosPorPixel(20, -23.56))).toBeNull()
  })

  it('metrosPorPixel invalido nao trava (nunca imanta por acidente)', () => {
    expect(travarNoAlvo(PAULISTA, ALVOS, 0)).toBeNull()
    expect(travarNoAlvo(PAULISTA, ALVOS, NaN)).toBeNull()
  })

  it('a tolerancia e declarada em pixels', () => {
    expect(TOLERANCIA_TRAVA_PX).toBeGreaterThan(0)
  })
})
