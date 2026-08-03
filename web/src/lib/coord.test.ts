import { describe, expect, it } from 'vitest'
import { coordenadaDoEstudo, parseCoordinate } from './coord'

describe('parseCoordinate', () => {
  it('par decimal com ponto', () => {
    expect(parseCoordinate('-15.79, -47.88')).toEqual({ lat: -15.79, lng: -47.88 })
  })
  it('par pt-BR (virgula decimal) separado por ponto-e-virgula', () => {
    expect(parseCoordinate('-23,55; -46,63')).toEqual({ lat: -23.55, lng: -46.63 })
  })
  it('link do Google Maps (@lat,lng)', () => {
    expect(parseCoordinate('https://www.google.com/maps/@-15.7942,-47.8822,15z')).toEqual({
      lat: -15.7942,
      lng: -47.8822,
    })
  })
  it('link do Google Maps (!3d..!4d)', () => {
    expect(parseCoordinate('...!3d-15.79!4d-47.88...')).toEqual({ lat: -15.79, lng: -47.88 })
  })
  it('dois numeros soltos como ultimo recurso', () => {
    expect(parseCoordinate('-15 -47')).toEqual({ lat: -15, lng: -47 })
  })
  it('faz trim de espacos ao redor', () => {
    expect(parseCoordinate('  -15.79, -47.88  ')).toEqual({ lat: -15.79, lng: -47.88 })
  })
  it.each(['', 'abc', 'sem coordenada aqui'])('texto sem coordenada -> null', (s) => {
    expect(parseCoordinate(s)).toBeNull()
  })
  it('coordenada FORA do bounding box do Brasil -> null', () => {
    // Nova York (lat 40.7 > 5.5) — reconhecivel, porem fora do Brasil.
    expect(parseCoordinate('40.7128, -50.0')).toBeNull()
  })
  it('longitude fora do Brasil -> null', () => {
    expect(parseCoordinate('-15.79, 10.0')).toBeNull()
  })
})

describe('coordenadaDoEstudo', () => {
  // Centroide real do hex res-7 que contem o ponto do usuario em Janga/Paulista-PE.
  // O caso que quebrou em producao (2026-07-24): o front mandava o centroide, que cai
  // no mar -> a malha municipal do IBGE nao resolve -> HTTP 400 "fora do Brasil".
  const hex = { lat: -7.942426, lng: -34.821732 }

  it('usa a coordenada EXATA quando o ponto veio da busca', () => {
    const alvo = coordenadaDoEstudo({ hex, lat: -7.93908, lng: -34.82566 })
    expect(alvo).toEqual({ lat: -7.93908, lng: -34.82566 })
    // Nao pode vazar o centroide.
    expect(alvo.lat).not.toBe(hex.lat)
    expect(alvo.lng).not.toBe(hex.lng)
  })

  it('cai no centroide do hexagono quando nao ha coordenada exata (clique no ranking)', () => {
    expect(coordenadaDoEstudo({ hex })).toEqual(hex)
  })

  it('nao aceita coordenada exata pela metade', () => {
    expect(coordenadaDoEstudo({ hex, lat: -7.93908 })).toEqual(hex)
    expect(coordenadaDoEstudo({ hex, lng: -34.82566 })).toEqual(hex)
  })

  it('preserva lat/lng = 0 (falsy, mas coordenada valida)', () => {
    expect(coordenadaDoEstudo({ hex, lat: 0, lng: 0 })).toEqual({ lat: 0, lng: 0 })
  })
})
