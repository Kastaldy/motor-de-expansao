/**
 * O alcance do ponto (DEC-074): a lista que o servidor oferece, o contorno que o mapa
 * desenha e o fator das réguas de totais.
 */
import { afterEach, describe, expect, it } from 'vitest'

import {
  ALCANCES,
  ROTULO_ALCANCE,
  _resetarAlcancesParaTeste,
  alcanceDoItem,
  alcancesDisponiveis,
  circuloGeoJson,
  contornosDoItem,
  definirAlcances,
  fatorReguaDoItem,
  hexSubstituidoPeloAlcance,
  notaDaReguaEscalada,
  poligonosDoContorno,
  selecaoMarcadaNoMapa,
} from './alcance'
import { latLngToCell } from 'h3-js'
import { distanciaMetros } from './medicao'
import type { PontoPayload } from './types'

afterEach(() => _resetarAlcancesParaTeste())

/**
 * Área de um anel `[lng, lat]` em km², numa projeção local equiretangular sobre a MESMA
 * esfera do gerador (basta para 2 km; constantes de elipsoide aqui mediriam a diferença
 * entre os dois modelos da Terra, não o círculo).
 */
function areaKm2(anel: [number, number][], lat0: number): number {
  const kmPorGrau = (6371.0088 * Math.PI) / 180
  const kx = kmPorGrau * Math.cos((lat0 * Math.PI) / 180)
  const ky = kmPorGrau
  let s = 0
  for (let i = 0; i < anel.length - 1; i++) {
    const [x1, y1] = anel[i]
    const [x2, y2] = anel[i + 1]
    s += x1 * kx * (y2 * ky) - x2 * kx * (y1 * ky)
  }
  return Math.abs(s) / 2
}

describe('alcances do perfil (`/api/me`)', () => {
  it('sem a chave (backend anterior): só o raio de 1 km — o seletor nem aparece', () => {
    definirAlcances(undefined)
    expect(alcancesDisponiveis()).toEqual(['raio_1km'])
  })

  it('payload malformado não instala nada nem derruba', () => {
    for (const ruim of [null, 'raio_2km', 42, { raio_2km: true }]) {
      definirAlcances(ruim)
      expect(alcancesDisponiveis()).toEqual(['raio_1km'])
    }
  })

  it('sem o serviço de rotas, "10 min de carro" SOME (não aparece apagado)', () => {
    definirAlcances(['raio_1km', 'raio_2km'])
    expect(alcancesDisponiveis()).toEqual(['raio_1km', 'raio_2km'])
    expect(alcancesDisponiveis()).not.toContain('carro_10min')
  })

  it('com o serviço de rotas, as três opções, na ordem do seletor', () => {
    definirAlcances(['carro_10min', 'raio_2km', 'raio_1km'])
    expect(alcancesDisponiveis()).toEqual(['raio_1km', 'raio_2km', 'carro_10min'])
  })

  it('o raio de 1 km entra SEMPRE (é para onde o seletor volta), e o desconhecido é ignorado', () => {
    definirAlcances(['raio_2km', 'bicicleta_15min'])
    expect(alcancesDisponiveis()).toEqual(['raio_1km', 'raio_2km'])
  })

  it('rótulos de exibição acentuados; os valores crus não mudam', () => {
    expect(ALCANCES).toEqual(['raio_1km', 'raio_2km', 'carro_10min'])
    expect(ROTULO_ALCANCE).toEqual({
      raio_1km: 'Raio de 1 km',
      raio_2km: 'Raio de 2 km',
      carro_10min: '10 min de carro',
    })
  })
})

describe('alcanceDoItem', () => {
  const base = { mercado: { disponivel: true, sam: 1, residual: 1, score_residual: 1 } } as Pick<
    PontoPayload,
    'mercado'
  >

  it('ponto de sempre (sem `recorte`): raio de 1 km', () => {
    expect(alcanceDoItem({ ...base, raio_km: 1 } as PontoPayload)).toBe('raio_1km')
  })

  it('pelo `recorte.tipo` do servidor', () => {
    const r2 = { ...base, raio_km: 2, recorte: { tipo: 'raio_2km', area_km2: 12.57, metodo: 'x' } }
    const iso = {
      ...base,
      raio_km: null,
      mercado: { ...base.mercado, grao: 'geometria' },
      recorte: { tipo: 'carro_10min', area_km2: 38.2, metodo: 'x' },
    }
    expect(alcanceDoItem(r2 as PontoPayload)).toBe('raio_2km')
    expect(alcanceDoItem(iso as PontoPayload)).toBe('carro_10min')
  })

  it('área desenhada não tem alcance', () => {
    const area = { ...base, raio_km: null, geometria: [[[0, 0], [1, 0], [1, 1], [0, 0]]] }
    expect(alcanceDoItem(area as PontoPayload)).toBeNull()
  })
})

describe('circuloGeoJson', () => {
  it('anel fechado, todos os vértices a exatamente r do centro', () => {
    const c = circuloGeoJson(-23.55, -46.63, 2)
    const anel = c.coordinates[0]
    expect(c.type).toBe('Polygon')
    expect(anel).toHaveLength(65)
    expect(anel[0]).toEqual(anel[64])
    for (const [lng, lat] of anel) {
      expect(distanciaMetros({ lat: -23.55, lng: -46.63 }, { lat, lng })).toBeCloseTo(2000, 0)
    }
  })

  it('área a menos de 0,3% de π·r² (geodésico, não elipse em graus — Porto Alegre também)', () => {
    for (const [lat, r] of [[-23.55, 1], [-30.03, 2], [-3.73, 2]] as const) {
      const anel = circuloGeoJson(lat, -46.63, r).coordinates[0]
      expect(Math.abs(areaKm2(anel, lat) / (Math.PI * r * r) - 1)).toBeLessThan(0.003)
    }
  })
})

describe('contornosDoItem — o que o mapa desenha de cada item', () => {
  const sq: [number, number][] = [[-46.63, -23.55], [-46.62, -23.55], [-46.62, -23.54], [-46.63, -23.55]]

  it('o raio de 1 km também é desenhado (antes não era)', () => {
    const c = contornosDoItem({ lat: -23.55, lng: -46.63, raio_km: 1 })
    expect(c).toHaveLength(1)
    expect(distanciaMetros({ lat: -23.55, lng: -46.63 }, { lat: c[0][0][0][1], lng: c[0][0][0][0] })).toBeCloseTo(1000, 0)
  })

  it('o raio de 2 km sai do `raio_km` (o servidor manda `contorno: null` no raio)', () => {
    const c = contornosDoItem({ lat: -23.55, lng: -46.63, raio_km: 2, recorte: { contorno: null } })
    expect(distanciaMetros({ lat: -23.55, lng: -46.63 }, { lat: c[0][0][0][1], lng: c[0][0][0][0] })).toBeCloseTo(2000, 0)
  })

  it('a isócrona vem pronta, Polygon ou MultiPolygon (com buraco)', () => {
    const buraco: [number, number][] = [[-46.628, -23.548], [-46.627, -23.548], [-46.627, -23.547], [-46.628, -23.548]]
    expect(
      contornosDoItem({ lat: 0, lng: 0, raio_km: null, recorte: { contorno: { type: 'Polygon', coordinates: [sq] } } }),
    ).toEqual([[sq]])
    const multi = contornosDoItem({
      lat: 0,
      lng: 0,
      raio_km: null,
      recorte: { contorno: { type: 'MultiPolygon', coordinates: [[sq, buraco], [sq]] } },
    })
    expect(multi).toHaveLength(2)
    expect(multi[0]).toHaveLength(2)
  })

  it('a área desenhada usa os vértices do operador', () => {
    expect(contornosDoItem({ lat: 0, lng: 0, geometria: [sq] })).toEqual([[sq]])
  })

  it('pendente de ponto (sem raio) não tem contorno; contorno malformado também não', () => {
    expect(contornosDoItem({ lat: 0, lng: 0 })).toEqual([])
    expect(
      poligonosDoContorno({ type: 'Polygon', coordinates: [[[0, 0], [1, 1]]] } as never),
    ).toEqual([])
  })
})

describe('fator das réguas', () => {
  const mercado = { disponivel: true, sam: 1, residual: 1, score_residual: 1 } as PontoPayload['mercado']

  it('raio de 1 km: EXATAMENTE 1, e nenhuma nota (regressão do bit atual)', () => {
    const p = { raio_km: 1, mercado } as PontoPayload
    expect(fatorReguaDoItem(p)).toBe(1)
    expect(notaDaReguaEscalada(p)).toBeNull()
  })

  it('o fator do servidor vence; sem ele, raio²', () => {
    expect(fatorReguaDoItem({ raio_km: 2, mercado } as PontoPayload)).toBe(4)
    const p = {
      raio_km: null,
      mercado,
      recorte: { tipo: 'carro_10min', area_km2: 38.2, metodo: 'x', fator_regua: 12.159 },
    } as PontoPayload
    expect(fatorReguaDoItem(p)).toBe(12.159)
  })

  it('a nota DECLARA a escala, com vírgula decimal', () => {
    const p = {
      raio_km: 2,
      mercado,
      recorte: { tipo: 'raio_2km', area_km2: 12.57, metodo: 'x', fator_regua: 4 },
    } as PontoPayload
    expect(notaDaReguaEscalada(p)).toBe('Réguas de totais escaladas ×4,0 pela área do recorte')
  })

  it('área desenhada sem fator do servidor: área / π', () => {
    const p = {
      raio_km: null,
      geometria: [[[0, 0], [1, 0], [1, 1], [0, 0]]],
      mercado,
      recorte: { tipo: 'poligono', area_km2: Math.PI * 3, metodo: 'x' },
    } as unknown as PontoPayload
    expect(fatorReguaDoItem(p)).toBeCloseTo(3, 9)
  })
})

/* ---------- O alcance substitui a marca do hexágono (pedido de 20/10/2026) ---------- */
describe('hexágono do ponto com alcance desenhado não é marcado', () => {
  const HEX = '87a8100c9ffffff'
  const OUTRO = '87a8100c8ffffff'
  const circulo1km = contornosDoItem({ lat: -23.55, lng: -46.63, raio_km: 1 })
  const pinComAlcance = { hexId: HEX, contornos: circulo1km }
  const pinPendente = { hexId: HEX, contornos: [] }

  it('o raio de 1 km também é alcance: o pin dele tem contorno', () => {
    expect(circulo1km.length).toBe(1)
    expect(hexSubstituidoPeloAlcance(pinComAlcance)).toBe(HEX)
  })

  it('sem contorno (pendente) ou sem pin, o hexágono segue marcado', () => {
    expect(hexSubstituidoPeloAlcance(pinPendente)).toBeNull()
    expect(hexSubstituidoPeloAlcance({ hexId: null, contornos: circulo1km })).toBeNull()
    expect(hexSubstituidoPeloAlcance(null)).toBeNull()
  })

  it('pendente de ÁREA DESENHADA (sem hex_id, com contorno): o hexágono da coordenada', () => {
    const lat = -23.55
    const lng = -46.63
    const hexDoPonto = latLngToCell(lat, lng, 7)
    const area = contornosDoItem({
      lat,
      lng,
      raio_km: null,
      geometria: [[[-46.64, -23.56], [-46.62, -23.56], [-46.62, -23.54], [-46.64, -23.56]]],
    })
    const pendenteDeArea = { hexId: null, contornos: area, lat, lng }
    expect(area.length).toBe(1)
    expect(hexSubstituidoPeloAlcance(pendenteDeArea)).toBe(hexDoPonto)
    /* A seleção da busca (o hexágono da coordenada) some; a de outro hexágono, não. */
    expect(selecaoMarcadaNoMapa(hexDoPonto, true, pendenteDeArea)).toBeNull()
    expect(selecaoMarcadaNoMapa(OUTRO, true, pendenteDeArea)).toBe(OUTRO)
    /* Clique direto no hexágono do ponto continua marcado. */
    expect(selecaoMarcadaNoMapa(hexDoPonto, false, pendenteDeArea)).toBe(hexDoPonto)
    /* Sem contorno, a coordenada não basta: o pendente de raio segue marcado. */
    expect(hexSubstituidoPeloAlcance({ hexId: null, contornos: [], lat, lng })).toBeNull()
  })

  it('a seleção que veio do ponto com alcance não é contornada no mapa', () => {
    expect(selecaoMarcadaNoMapa(HEX, true, pinComAlcance)).toBeNull()
  })

  it('hexágono comum (clique direto, sem ponto) continua marcado', () => {
    expect(selecaoMarcadaNoMapa(HEX, false, null)).toBe(HEX)
    expect(selecaoMarcadaNoMapa(OUTRO, false, null)).toBe(OUTRO)
  })

  it('clique direto no hexágono do próprio ponto continua marcado', () => {
    expect(selecaoMarcadaNoMapa(HEX, false, pinComAlcance)).toBe(HEX)
  })

  it('a seleção do ponto sem alcance ainda (pendente) continua marcada', () => {
    expect(selecaoMarcadaNoMapa(HEX, true, pinPendente)).toBe(HEX)
  })

  it('seleção de OUTRO hexágono não é apagada pelo alcance do ponto', () => {
    expect(selecaoMarcadaNoMapa(OUTRO, true, pinComAlcance)).toBe(OUTRO)
    expect(selecaoMarcadaNoMapa(null, true, pinComAlcance)).toBeNull()
  })
})
