import { describe, expect, it } from 'vitest'

import {
  ESTADO_MAPA_VAZIO,
  chaveContexto,
  fotoAplicavel,
  type EstadoMapa,
} from './mapa-estado'

function foto(over: Partial<EstadoMapa> = {}): EstadoMapa {
  return {
    ...ESTADO_MAPA_VAZIO,
    uf: 'SP',
    municipio: 'São Paulo',
    passoN: 4,
    selecionado: '87a8100c3ffffff',
    pin: { lat: -23.5505, lng: -46.6333, hexId: '87a8100c3ffffff' },
    busca: '-23.5505, -46.6333',
    camera: { longitude: -46.6333, latitude: -23.5505, zoom: 14.2, pitch: 0, bearing: 0 },
    ...over,
  }
}

describe('chaveContexto', () => {
  it('separa UF de municipio', () => {
    expect(chaveContexto('SP', 'São Paulo')).toBe('SP|São Paulo')
    expect(chaveContexto('SP', '')).toBe('SP|')
  })

  it('visao da UF e drill-down no municipio sao contextos diferentes', () => {
    expect(chaveContexto('SP', '')).not.toBe(chaveContexto('SP', 'São Paulo'))
  })
})

describe('fotoAplicavel', () => {
  it('devolve a foto quando o contexto e o MESMO — o caso da volta da Viabilidade', () => {
    const f = foto()
    const out = fotoAplicavel(f, 'SP', 'São Paulo')
    expect(out).toBe(f)
    // o que o operador espera reencontrar no mapa
    expect(out.passoN).toBe(4)
    expect(out.selecionado).toBe('87a8100c3ffffff')
    expect(out.pin).toEqual({ lat: -23.5505, lng: -46.6333, hexId: '87a8100c3ffffff' })
    expect(out.camera?.zoom).toBe(14.2)
    expect(out.busca).toBe('-23.5505, -46.6333')
  })

  it('descarta foto de OUTRO municipio (drill-down mudou)', () => {
    expect(fotoAplicavel(foto(), 'SP', 'Campinas')).toBe(ESTADO_MAPA_VAZIO)
  })

  it('descarta foto de OUTRA UF', () => {
    expect(fotoAplicavel(foto(), 'MG', 'São Paulo')).toBe(ESTADO_MAPA_VAZIO)
  })

  it('descarta foto da UF inteira quando ja se entrou num municipio', () => {
    expect(fotoAplicavel(foto({ municipio: '' }), 'SP', 'São Paulo')).toBe(ESTADO_MAPA_VAZIO)
  })

  it('descarta foto de municipio quando se voltou para a visao da UF', () => {
    expect(fotoAplicavel(foto(), 'SP', '')).toBe(ESTADO_MAPA_VAZIO)
  })

  it('descarta foto sem contexto (foto neutra ou de versao anterior)', () => {
    expect(fotoAplicavel(ESTADO_MAPA_VAZIO, 'SP', 'São Paulo')).toBe(ESTADO_MAPA_VAZIO)
    expect(fotoAplicavel(foto({ uf: '' }), 'SP', 'São Paulo')).toBe(ESTADO_MAPA_VAZIO)
  })

  it('tolera null/undefined', () => {
    expect(fotoAplicavel(null, 'SP', 'São Paulo')).toBe(ESTADO_MAPA_VAZIO)
    expect(fotoAplicavel(undefined, 'SP', 'São Paulo')).toBe(ESTADO_MAPA_VAZIO)
  })

  it('preserva o cenario multi-hex e o filtro de faixa', () => {
    const f = foto({ modoCenario: true, cenario: ['87a', '87b'], filtroFaixa: 'alta' })
    const out = fotoAplicavel(f, 'SP', 'São Paulo')
    expect(out.modoCenario).toBe(true)
    expect(out.cenario).toEqual(['87a', '87b'])
    expect(out.filtroFaixa).toBe('alta')
  })
})

describe('ESTADO_MAPA_VAZIO', () => {
  it('e o mapa como ele sempre comecou (passo 1, nada selecionado, camera padrao)', () => {
    expect(ESTADO_MAPA_VAZIO.passoN).toBe(1)
    expect(ESTADO_MAPA_VAZIO.selecionado).toBeNull()
    expect(ESTADO_MAPA_VAZIO.pin).toBeNull()
    expect(ESTADO_MAPA_VAZIO.camera).toBeNull()
    expect(ESTADO_MAPA_VAZIO.busca).toBe('')
    expect(ESTADO_MAPA_VAZIO.cenario).toEqual([])
  })
})
