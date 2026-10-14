import { describe, expect, it } from 'vitest'

import {
  AREA_MAX_KM2,
  MAX_VERTICES,
  TOLERANCIA_FECHAR_PX,
  adicionarVertice,
  areaKm2,
  avaliarDesenho,
  desfazerVertice,
  formatarKm2,
  interpretarClique,
  paraGeoJson,
  pontoInterno,
  segmentosSeCruzam,
  temAutointersecao,
} from './geometria-desenho'
import { metrosPorPixel, type Coord } from './medicao'

const LAT = -23.55
const LNG = -46.63
const M_POR_GRAU_LAT = 111_195
const mPorGrauLng = (lat: number) => M_POR_GRAU_LAT * Math.cos((lat * Math.PI) / 180)

/** Ponto a (dx, dy) METROS do centro. */
const em = (dx: number, dy: number): Coord => ({
  lat: LAT + dy / M_POR_GRAU_LAT,
  lng: LNG + dx / mPorGrauLng(LAT),
})

/** Quadrado de `lado` metros centrado. */
const quadrado = (lado: number): Coord[] => [
  em(-lado / 2, -lado / 2),
  em(lado / 2, -lado / 2),
  em(lado / 2, lado / 2),
  em(-lado / 2, lado / 2),
]

describe('área', () => {
  it('quadrado de 1 km dá 1 km²', () => {
    expect(areaKm2(quadrado(1000))).toBeCloseTo(1, 2)
  })

  it('independe do sentido do desenho', () => {
    expect(areaKm2([...quadrado(1000)].reverse())).toBeCloseTo(1, 2)
  })

  it('menos de 3 vértices não tem área', () => {
    expect(areaKm2(quadrado(1000).slice(0, 2))).toBe(0)
  })

  it('formata com vírgula e km²', () => {
    expect(formatarKm2(2.4)).toBe('2,40 km²')
    expect(formatarKm2(12.34)).toBe('12,3 km²')
  })
})

describe('autointerseção', () => {
  it('um "oito" cruza; o quadrado não', () => {
    const [a, b, c, d] = quadrado(1000)
    expect(temAutointersecao([a, b, c, d])).toBe(false)
    expect(temAutointersecao([a, c, b, d])).toBe(true)
  })

  it('arestas vizinhas tocando no vértice comum NÃO contam como cruzamento', () => {
    expect(temAutointersecao(quadrado(500))).toBe(false)
  })

  it('segmentos colineares sobrepostos se tocam', () => {
    expect(segmentosSeCruzam({ x: 0, y: 0 }, { x: 2, y: 0 }, { x: 1, y: 0 }, { x: 3, y: 0 })).toBe(true)
    expect(segmentosSeCruzam({ x: 0, y: 0 }, { x: 1, y: 0 }, { x: 2, y: 0 }, { x: 3, y: 0 })).toBe(false)
  })
})

describe('clique: fechar, acrescentar, teto', () => {
  const mpp = metrosPorPixel(15, LAT) // ~2,2 m/px

  it('perto do 1º vértice (em pixels) fecha, com 3+ vértices', () => {
    const vs = quadrado(1000).slice(0, 3)
    const perto = em(-500 + (TOLERANCIA_FECHAR_PX - 2) * mpp * 0.7, -500)
    expect(interpretarClique(vs, perto, mpp)).toEqual({ tipo: 'fechar' })
  })

  it('longe do 1º vértice acrescenta', () => {
    const vs = quadrado(1000).slice(0, 3)
    expect(interpretarClique(vs, em(-500, 500), mpp)).toEqual({ tipo: 'adicionar' })
  })

  it('com 2 vértices o clique no 1º NÃO fecha (não há área)', () => {
    const vs = quadrado(1000).slice(0, 2)
    expect(interpretarClique(vs, vs[0], mpp)).toEqual({ tipo: 'adicionar' })
  })

  it('a tolerância é de TELA: no zoom de cidade a mesma distância em metros fecha', () => {
    const vs = quadrado(1000).slice(0, 3)
    const a40m = em(-500 + 40, -500)
    expect(interpretarClique(vs, a40m, metrosPorPixel(17, LAT))).toEqual({ tipo: 'adicionar' })
    expect(interpretarClique(vs, a40m, metrosPorPixel(12, LAT))).toEqual({ tipo: 'fechar' })
  })

  it('no teto de vértices o clique é recusado, não engolido', () => {
    const vs = Array.from({ length: MAX_VERTICES }, (_, i) =>
      em(1000 * Math.cos((2 * Math.PI * i) / MAX_VERTICES), 1000 * Math.sin((2 * Math.PI * i) / MAX_VERTICES)),
    )
    expect(interpretarClique(vs, em(5000, 5000), mpp)).toEqual({ tipo: 'cheio' })
    expect(adicionarVertice(vs, em(5000, 5000))).toHaveLength(MAX_VERTICES)
  })
})

describe('acrescentar e desfazer', () => {
  it('acrescenta sem mutar a lista de entrada', () => {
    const vs = quadrado(1000).slice(0, 2)
    const novo = adicionarVertice(vs, em(0, 900))
    expect(novo).toHaveLength(3)
    expect(vs).toHaveLength(2)
  })

  it('clique repetido no mesmo lugar não vira vértice', () => {
    const vs = quadrado(1000).slice(0, 2)
    expect(adicionarVertice(vs, vs[1])).toHaveLength(2)
  })

  it('desfaz o último', () => {
    const vs = quadrado(1000)
    expect(desfazerVertice(vs)).toEqual(vs.slice(0, 3))
    expect(desfazerVertice([])).toEqual([])
  })
})

describe('avaliação (o que a barra mostra)', () => {
  it('pede mais vértices antes de 3', () => {
    const a = avaliarDesenho(quadrado(1000).slice(0, 1))
    expect(a.podeConcluir).toBe(false)
    expect(a.motivo).toMatch(/mais 2 vértices/)
    expect(a.areaKm2).toBeNull()
  })

  it('quadrado de 1 km pode ser concluído', () => {
    const a = avaliarDesenho(quadrado(1000))
    expect(a).toMatchObject({ podeConcluir: true, motivo: null, nVertices: 4 })
    expect(a.areaKm2).toBeCloseTo(1, 2)
  })

  it('recusa abaixo de 0,1 km² e acima de 25 km², dizendo o limite', () => {
    const pequeno = avaliarDesenho(quadrado(200))
    expect(pequeno.podeConcluir).toBe(false)
    expect(pequeno.motivo).toMatch(/mínimo é 0,1 km²/)
    const grande = avaliarDesenho(quadrado(Math.sqrt(AREA_MAX_KM2 * 1.2) * 1000))
    expect(grande.podeConcluir).toBe(false)
    expect(grande.motivo).toMatch(/máximo é 25 km²/)
  })

  it('recusa autointerseção', () => {
    const [a, b, c, d] = quadrado(1000)
    const r = avaliarDesenho([a, c, b, d])
    expect(r.podeConcluir).toBe(false)
    expect(r.motivo).toMatch(/cruza a si mesma/)
  })
})

describe('GeoJSON', () => {
  it('anel FECHADO, em [lng, lat]', () => {
    const vs = quadrado(1000)
    const g = paraGeoJson(vs)
    expect(g.type).toBe('Polygon')
    const anel = g.coordinates[0]
    expect(anel).toHaveLength(5)
    expect(anel[0]).toEqual([vs[0].lng, vs[0].lat])
    expect(anel[4]).toEqual(anel[0])
  })
})

describe('ponto interno (pin provisório)', () => {
  it('no convexo é o centroide', () => {
    const p = pontoInterno(paraGeoJson(quadrado(1000)).coordinates[0])
    expect(p.lat).toBeCloseTo(LAT, 6)
    expect(p.lng).toBeCloseTo(LNG, 6)
  })

  it('num "U" cai DENTRO de um braço, e não no vão onde fica o centroide', () => {
    const u = [em(-1000, -1000), em(1000, -1000), em(1000, 1000), em(300, 1000), em(300, -800),
      em(-300, -800), em(-300, 1000), em(-1000, 1000)]
    const p = pontoInterno(paraGeoJson(u).coordinates[0])
    // Fora do vão central (|x| < 300 m acima de -800 m).
    const dx = (p.lng - LNG) * mPorGrauLng(LAT)
    const dy = (p.lat - LAT) * M_POR_GRAU_LAT
    expect(Math.abs(dx) > 300 || dy < -800).toBe(true)
    expect(Math.abs(dx)).toBeLessThan(1000)
  })
})
