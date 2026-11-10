import { describe, expect, it } from 'vitest'

import { circuloGeoJson } from './alcance'
import { metrosPorPixel } from './captura-mapa'
import {
  ALTURA_PRINT_CSS,
  FOLGA_PIN_CSS,
  FOLGA_PRINT_CSS,
  ID_LAVOURA,
  ID_URBANO_ESPECIAL,
  LARGURA_PRINT_CSS,
  PALETA_PRINT,
  ZOOM_PRINT_MAX,
  alcanceDoPrint,
  caixaDoPrint,
  camadasDoAlcance,
  classeDaVia,
  escalaDoPrint,
  geojsonDoAlcance,
  limparRotuloDigitado,
  MAX_ROTULO_PRINT,
  nomeDoArquivoPrint,
  recorteDoArquivoPrint,
  primeiraCamadaDeRotulo,
  quadroDoPrint,
  realcarEstilo,
  rotuloDoPrint,
  type EstiloMapa,
} from './print-mapa'

/* Projeção de teste, independente do módulo: lng/lat -> px CSS no quadro do print. */
function projetar(lng: number, lat: number, centro: { lng: number; lat: number }, zoom: number) {
  const escala = 512 * 2 ** zoom
  const mx = (v: number) => ((v + 180) / 360) * escala
  const my = (v: number) => {
    const s = Math.sin((v * Math.PI) / 180)
    return (0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI)) * escala
  }
  return {
    x: LARGURA_PRINT_CSS / 2 + mx(lng) - mx(centro.lng),
    y: ALTURA_PRINT_CSS / 2 + my(lat) - my(centro.lat),
  }
}

const TERESOPOLIS = { lat: -22.4152, lng: -42.9706 }

describe('alcanceDoPrint', () => {
  it('usa o círculo do raio quando o item é um raio', () => {
    const p = alcanceDoPrint({ ...TERESOPOLIS, raio_km: 2 })
    expect(p).toHaveLength(1)
    expect(p[0][0]).toHaveLength(65)
  })

  it('usa o contorno do servidor (isócrona) quando ele vem', () => {
    const iso = { type: 'Polygon' as const, coordinates: [[[-43, -22.4], [-42.9, -22.4], [-42.9, -22.5], [-43, -22.4]]] as [number, number][][] }
    const p = alcanceDoPrint({ ...TERESOPOLIS, raio_km: null, recorte: { contorno: iso } })
    expect(p).toEqual([iso.coordinates])
  })

  it('sem contorno nenhum, cai no raio de 1 km — o print nunca sai sem recorte', () => {
    const p = alcanceDoPrint({ ...TERESOPOLIS, raio_km: null })
    expect(p).toEqual([circuloGeoJson(TERESOPOLIS.lat, TERESOPOLIS.lng, 1).coordinates])
  })
})

describe('caixaDoPrint', () => {
  it('cobre o anel externo e o ponto', () => {
    const anel: [number, number][] = [[-43, -22], [-42, -22], [-42, -23], [-43, -22]]
    expect(caixaDoPrint([[anel]], { lat: -24, lng: -41 })).toEqual([-43, -24, -41, -22])
  })

  it('ignora vértice inválido e devolve null sem nenhum válido', () => {
    const anel = [[NaN, 1], [Infinity, 2]] as [number, number][]
    expect(caixaDoPrint([[anel]])).toBeNull()
  })
})

describe('quadroDoPrint — o alcance aparece POR COMPLETO', () => {
  const casos = [
    { nome: 'raio de 1 km', km: 1 },
    { nome: 'raio de 2 km', km: 2 },
    { nome: 'isócrona larga (~7 km)', km: 7 },
  ]
  for (const caso of casos) {
    it(`${caso.nome}: todo vértice fica dentro do quadro, respeitando a folga`, () => {
      const poligonos = [circuloGeoJson(TERESOPOLIS.lat, TERESOPOLIS.lng, caso.km).coordinates]
      const caixa = caixaDoPrint(poligonos, TERESOPOLIS)!
      const q = quadroDoPrint(caixa)
      const pts = poligonos[0][0].map(([x, y]) => projetar(x, y, q.centro, q.zoom))
      const xs = pts.map((p) => p.x)
      const ys = pts.map((p) => p.y)
      expect(Math.min(...xs)).toBeGreaterThanOrEqual(FOLGA_PRINT_CSS - 0.5)
      expect(Math.max(...xs)).toBeLessThanOrEqual(LARGURA_PRINT_CSS - FOLGA_PRINT_CSS + 0.5)
      expect(Math.min(...ys)).toBeGreaterThanOrEqual(FOLGA_PRINT_CSS + FOLGA_PIN_CSS - 0.5)
      expect(Math.max(...ys)).toBeLessThanOrEqual(ALTURA_PRINT_CSS - FOLGA_PRINT_CSS + 0.5)
      // E o alcance ENCOSTA na folga em pelo menos um eixo: o print não sobra vazio.
      const encostaY = Math.abs(Math.max(...ys) - (ALTURA_PRINT_CSS - FOLGA_PRINT_CSS)) < 1
      const encostaX = Math.abs(Math.max(...xs) - (LARGURA_PRINT_CSS - FOLGA_PRINT_CSS)) < 1
      expect(encostaX || encostaY).toBe(true)
    })
  }

  it('o raio de 2 km sai exatamente um zoom abaixo do de 1 km', () => {
    const z = (km: number) => quadroDoPrint(caixaDoPrint([circuloGeoJson(TERESOPOLIS.lat, TERESOPOLIS.lng, km).coordinates])!).zoom
    expect(z(1) - z(2)).toBeCloseTo(1, 2)
  })

  it('não passa do zoom máximo num recorte minúsculo', () => {
    const q = quadroDoPrint([-42.97, -22.415, -42.9699, -22.4149])
    expect(q.zoom).toBe(ZOOM_PRINT_MAX)
  })
})

describe('escalaDoPrint', () => {
  it('escolhe distância redonda que cabe no máximo, com rótulo em pt-BR', () => {
    const e = escalaDoPrint(-22.4, 14)
    expect(e.px).toBeLessThanOrEqual(150)
    expect(e.px).toBeCloseTo(e.metros / metrosPorPixel(-22.4, 14), 6)
    expect([200, 250, 500]).toContain(e.metros)
  })

  it('usa km a partir de 1.000 m, com vírgula', () => {
    expect(escalaDoPrint(-22.4, 11).rotulo).toMatch(/^\d+(,\d)? km$/)
    expect(escalaDoPrint(-22.4, 9, 150).rotulo).toMatch(/ km$/)
  })
})

describe('rotuloDoPrint e nomeDoArquivoPrint', () => {
  it('junta bairro e cidade/UF', () => {
    expect(rotuloDoPrint('Várzea', 'Teresópolis', 'RJ')).toBe('Várzea · Teresópolis/RJ')
  })

  it('não repete a cidade quando o bairro tem o mesmo nome', () => {
    expect(rotuloDoPrint('Teresopolis', 'Teresópolis', 'RJ')).toBe('Teresópolis/RJ')
  })

  it('sem bairro (área desenhada), fica só a cidade', () => {
    expect(rotuloDoPrint(null, 'Teresópolis', 'RJ')).toBe('Teresópolis/RJ')
  })

  it('nome digitado: espaços e quebras viram um espaço, com teto de tamanho; vazio vale', () => {
    expect(limparRotuloDigitado('  Av. Lúcio Meira,\n 923   - Várzea ')).toBe('Av. Lúcio Meira, 923 - Várzea')
    expect(limparRotuloDigitado('x'.repeat(200))).toHaveLength(MAX_ROTULO_PRINT)
    expect(limparRotuloDigitado('   ')).toBe('')
  })

  it('o recorte no nome do arquivo é só o alcance: sem "sem trânsito" nem área', () => {
    expect(recorteDoArquivoPrint('carro_10min')).toBe('10 min de carro')
    expect(recorteDoArquivoPrint('carro_5min')).toBe('5 min de carro')
    expect(recorteDoArquivoPrint('raio_2km')).toBe('Raio de 2 km')
    expect(recorteDoArquivoPrint('poligono')).toBe('Área desenhada')
    expect(recorteDoArquivoPrint(null)).toBeNull()
    expect(nomeDoArquivoPrint('Várzea · Teresópolis/RJ', recorteDoArquivoPrint('carro_10min'))).toBe(
      'mapa-varzea-teresopolis-rj-10-min-de-carro.png',
    )
  })

  it('nome do arquivo sem acento, com o recorte', () => {
    expect(nomeDoArquivoPrint('Várzea · Teresópolis/RJ', 'raio de 1 km')).toBe('mapa-varzea-teresopolis-rj-raio-de-1-km.png')
    expect(nomeDoArquivoPrint('', null)).toBe('mapa.png')
  })
})

/* Recorte mínimo do Voyager do CARTO, com os ids REAIS (conferidos em 10/11/2026). */
function voyagerMinimo(): EstiloMapa {
  const nomeEn = ['coalesce', ['get', 'name:en'], ['get', 'name']]
  return {
    version: 8,
    sources: { protomaps: { type: 'vector', tiles: ['https://exemplo/{z}/{x}/{y}.mvt'] } },
    layers: [
      { id: 'background', type: 'background', paint: { 'background-color': '#fbf8f3' } },
      { id: 'landcover', type: 'fill', source: 'protomaps', 'source-layer': 'landuse', paint: {} },
      { id: 'landuse_residential', type: 'fill', source: 'protomaps', 'source-layer': 'landuse', minzoom: 6, paint: {} },
      { id: 'waterway', type: 'line', source: 'protomaps', 'source-layer': 'water', paint: {} },
      { id: 'water', type: 'fill', source: 'protomaps', 'source-layer': 'water', paint: {} },
      { id: 'water_shadow', type: 'fill', source: 'protomaps', 'source-layer': 'water', paint: {} },
      { id: 'road_minor_case', type: 'line', source: 'protomaps', 'source-layer': 'roads', minzoom: 13, paint: {} },
      { id: 'road_minor_fill', type: 'line', source: 'protomaps', 'source-layer': 'roads', minzoom: 15, paint: {} },
      { id: 'road_pri_fill_noramp', type: 'line', source: 'protomaps', 'source-layer': 'roads', paint: {} },
      { id: 'road_mot_fill_ramp', type: 'line', source: 'protomaps', 'source-layer': 'roads', paint: {} },
      { id: 'bridge_mot_case', type: 'line', source: 'protomaps', 'source-layer': 'roads', paint: {} },
      { id: 'road_trunk_fill_noramp', type: 'line', source: 'protomaps', 'source-layer': 'roads', paint: {} },
      { id: 'road_path', type: 'line', source: 'protomaps', 'source-layer': 'roads', paint: { 'line-color': '#d7d7d7' } },
      { id: 'building', type: 'fill', source: 'protomaps', 'source-layer': 'buildings', paint: {} },
      { id: 'building-top', type: 'fill', source: 'protomaps', 'source-layer': 'buildings', paint: {} },
      { id: 'waterway_label', type: 'symbol', source: 'protomaps', 'source-layer': 'water', layout: { 'text-field': nomeEn }, paint: {} },
      { id: 'place_suburbs', type: 'symbol', source: 'protomaps', 'source-layer': 'places', layout: { 'text-field': nomeEn }, paint: {} },
      { id: 'poi_park', type: 'symbol', source: 'protomaps', 'source-layer': 'pois', layout: { 'text-field': nomeEn }, paint: {} },
      { id: 'roadname_pri', type: 'symbol', source: 'protomaps', 'source-layer': 'roads', minzoom: 14, layout: { 'text-field': nomeEn }, paint: {} },
      { id: 'housenumber', type: 'symbol', source: 'protomaps', 'source-layer': 'buildings', layout: {}, paint: {} },
    ],
  }
}

describe('classeDaVia', () => {
  it('lê classe, parte e túnel do id do Voyager', () => {
    expect(classeDaVia('road_pri_case_noramp')).toEqual({ classe: 'pri', parte: 'case', tunel: false, alca: false })
    expect(classeDaVia('road_mot_fill_ramp')).toEqual({ classe: 'mot', parte: 'fill', tunel: false, alca: true })
    expect(classeDaVia('bridge_mot_fill')).toEqual({ classe: 'mot', parte: 'fill', tunel: false, alca: false })
    expect(classeDaVia('tunnel_minor_case')).toEqual({ classe: 'minor', parte: 'case', tunel: true, alca: false })
    expect(classeDaVia('road_path')).toBeNull()
    expect(classeDaVia('roadname_pri')).toBeNull()
  })
})

describe('realcarEstilo', () => {
  const base = voyagerMinimo()
  const r = realcarEstilo(base)
  const camada = (id: string) => r.layers.find((c) => c.id === id)
  const ids = r.layers.map((c) => c.id)

  it('não muta o estilo baixado', () => {
    expect(base.layers[0].paint).toEqual({ 'background-color': '#fbf8f3' })
    expect(base.layers.map((c) => c.id)).toContain('poi_park')
  })

  it('tira POIs, número de casa, topo 3D e sombra da água — o print não tem "dado"', () => {
    for (const fora of ['poi_park', 'housenumber', 'building-top', 'water_shadow']) expect(ids).not.toContain(fora)
  })

  it('rodovia em laranja, avenida em amarelo, rua branca com contorno cinza', () => {
    expect(camada('road_trunk_fill_noramp')?.paint?.['line-color']).toBe(PALETA_PRINT.rodovia)
    expect(camada('bridge_mot_case')?.paint?.['line-color']).toBe(PALETA_PRINT.rodoviaContorno)
    expect(camada('road_pri_fill_noramp')?.paint?.['line-color']).toBe(PALETA_PRINT.avenida)
    expect(camada('road_minor_fill')?.paint?.['line-color']).toBe(PALETA_PRINT.rua)
    expect(camada('road_minor_case')?.paint?.['line-color']).toBe(PALETA_PRINT.ruaContorno)
    // A rua local ganha miolo no mesmo zoom do contorno (no Voyager, só no 15).
    expect(camada('road_minor_fill')?.minzoom).toBe(12)
    expect(camada('road_minor_case')?.minzoom).toBe(12)
  })

  it('alça de rodovia: mesma cor, largura menor que a da pista', () => {
    const largura = (id: string) => (camada(id)?.paint?.['line-width'] as unknown[]).slice(3) as number[]
    expect(camada('road_mot_fill_ramp')?.paint?.['line-color']).toBe(PALETA_PRINT.rodovia)
    const pista = largura('road_trunk_fill_noramp')
    const alca = largura('road_mot_fill_ramp')
    for (let i = 1; i < pista.length; i += 2) expect(alca[i]).toBeLessThan(pista[i])
  })

  it('rio e água em azul', () => {
    expect(camada('water')?.paint?.['fill-color']).toBe(PALETA_PRINT.agua)
    expect(camada('waterway')?.paint?.['line-color']).toBe(PALETA_PRINT.rio)
    expect(camada('waterway_label')?.paint?.['text-color']).toBe(PALETA_PRINT.rotuloAgua)
  })

  it('chão: fundo -> lavoura -> urbano -> urbano especial -> vegetação (parque fica verde sobre o bairro)', () => {
    const ordem = ['background', ID_LAVOURA, 'landuse_residential', ID_URBANO_ESPECIAL, 'landcover']
    expect(ordem.map((id) => ids.indexOf(id))).toEqual([0, 1, 2, 3, 4])
    expect(camada('landuse_residential')?.paint?.['fill-color']).toBe(PALETA_PRINT.urbano)
    const cobertura = JSON.stringify(camada('landcover')?.paint?.['fill-color'])
    expect(cobertura).toContain(PALETA_PRINT.vegetacao)
    expect(cobertura).toContain(PALETA_PRINT.campo)
    const chaoNovo = JSON.stringify(camada(ID_LAVOURA)?.paint?.['fill-color'])
    for (const cor of [PALETA_PRINT.lavoura, PALETA_PRINT.rocha, PALETA_PRINT.alagado]) expect(chaoNovo).toContain(cor)
    expect(JSON.stringify(camada(ID_LAVOURA)?.filter)).toContain('farmland')
    expect(JSON.stringify(camada(ID_LAVOURA)?.filter)).toContain('bare_rock')
    expect(camada(ID_LAVOURA)?.source).toBe('protomaps')
    expect(camada('background')?.paint?.['background-color']).toBe(PALETA_PRINT.fundo)
  })

  it('rótulos no nome local/pt, nunca no name:en do Voyager', () => {
    for (const id of ['place_suburbs', 'waterway_label', 'roadname_pri']) {
      expect(JSON.stringify(camada(id)?.layout?.['text-field'])).not.toContain('name:en')
      expect(camada(id)?.layout?.['text-field']).toEqual(['coalesce', ['get', 'name:pt'], ['get', 'name']])
    }
    expect(camada('roadname_pri')?.minzoom).toBe(12.5)
  })

  it('camada que a regra não reconhece segue como veio', () => {
    expect(camada('road_path')?.paint?.['line-color']).toBe('#d7d7d7')
  })

  it('sem fonte vetorial, não inventa camada de chão (e não quebra)', () => {
    const semFonte: EstiloMapa = { version: 8, sources: {}, layers: [{ id: 'background', type: 'background', paint: {} }] }
    expect(realcarEstilo(semFonte).layers.map((c) => c.id)).toEqual(['background'])
  })
})

describe('alcance desenhado', () => {
  it('GeoJSON do alcance como MultiPolygon; vazio sem polígono', () => {
    const p = [circuloGeoJson(-22.4, -42.9, 1).coordinates]
    const g = geojsonDoAlcance(p)
    expect(g.features[0].geometry.type).toBe('MultiPolygon')
    expect(g.features[0].geometry.coordinates).toEqual(p)
    expect(geojsonDoAlcance([]).features).toEqual([])
  })

  it('linha azul por cima, com halo branco', () => {
    const c = camadasDoAlcance()
    expect(c.linha.paint?.['line-color']).toBe(PALETA_PRINT.alcance)
    expect(c.halo.paint?.['line-color']).toBe(PALETA_PRINT.halo)
  })

  it('o contorno entra no início do BLOCO FINAL de rótulos, nunca abaixo das ruas', () => {
    const base = voyagerMinimo()
    // Como no Voyager real: um nome de rio ANTES das ruas.
    base.layers.splice(4, 0, { id: 'rotulo_cedo', type: 'symbol', source: 'protomaps', 'source-layer': 'water', layout: {}, paint: {} })
    const estilo = realcarEstilo(base)
    const id = primeiraCamadaDeRotulo(estilo)
    expect(id).toBe('waterway_label')
    const i = estilo.layers.findIndex((c) => c.id === id)
    expect(estilo.layers.slice(i).every((c) => c.type === 'symbol')).toBe(true)
    expect(estilo.layers.slice(0, i).some((c) => c.id === 'road_pri_fill_noramp')).toBe(true)
  })

  it('sem rótulo no fim, a linha vai para o topo', () => {
    expect(primeiraCamadaDeRotulo({ version: 8, sources: {}, layers: [{ id: 'background', type: 'background' }] })).toBeUndefined()
  })
})
