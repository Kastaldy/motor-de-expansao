import { describe, expect, it } from 'vitest'

import { classificarEntrada, linkGoogleMaps } from './entrada-ponto'

/** Av. Paulista, 1000 — o ponto de referencia dos testes. */
const LAT = -23.5613
const LNG = -46.6565

describe('classificarEntrada — vazio', () => {
  it('trata vazio e so-espacos como vazio, sem aviso', () => {
    for (const t of ['', '   ', '\t\n']) {
      const r = classificarEntrada(t)
      expect(r.tipo).toBe('vazio')
      expect(r.coord).toBeNull()
      expect(r.precisaServidor).toBe(false)
      expect(r.aviso).toBe('')
    }
  })
})

describe('classificarEntrada — coordenada resolvida no front', () => {
  it('par com ponto decimal', () => {
    const r = classificarEntrada(`${LAT}, ${LNG}`)
    expect(r.tipo).toBe('coordenada')
    expect(r.coord).toEqual({ lat: LAT, lng: LNG })
    expect(r.precisaServidor).toBe(false)
  })

  it('par pt-BR com virgula decimal', () => {
    const r = classificarEntrada('-23,5613; -46,6565')
    expect(r.tipo).toBe('coordenada')
    expect(r.coord?.lat).toBeCloseTo(LAT, 4)
    expect(r.coord?.lng).toBeCloseTo(LNG, 4)
  })

  it('link LONGO do Maps com @lat,lng nao precisa de servidor', () => {
    const r = classificarEntrada(
      `https://www.google.com/maps/place/Av.+Paulista/@${LAT},${LNG},17z/data=!3m1`,
    )
    expect(r.tipo).toBe('coordenada')
    expect(r.coord).toEqual({ lat: LAT, lng: LNG })
    expect(r.precisaServidor).toBe(false)
  })

  it('link LONGO no formato !3d..!4d tambem resolve aqui', () => {
    const r = classificarEntrada(
      `https://www.google.com/maps/place/X/data=!4m6!3m5!1s0x0!8m2!3d${LAT}!4d${LNG}`,
    )
    expect(r.tipo).toBe('coordenada')
    expect(r.coord).toEqual({ lat: LAT, lng: LNG })
  })
})

describe('classificarEntrada — link curto (o do celular)', () => {
  // Este e' o caso que hoje falha em silencio: sem coordenada na URL, o texto ia
  // inteiro para o geocode e voltava "nao encontrei esse endereco".
  it('reconhece maps.app.goo.gl e manda resolver no servidor', () => {
    const r = classificarEntrada('https://maps.app.goo.gl/aBcDeFgHiJkL')
    expect(r.tipo).toBe('link-curto')
    expect(r.coord).toBeNull()
    expect(r.precisaServidor).toBe(true)
    expect(r.aviso).not.toBe('')
  })

  it('reconhece o goo.gl/maps antigo', () => {
    expect(classificarEntrada('https://goo.gl/maps/XyZ123').tipo).toBe('link-curto')
  })

  it('nao se importa com maiuscula/minuscula nem com texto em volta', () => {
    const r = classificarEntrada('  olha aqui: HTTPS://MAPS.APP.GOO.GL/aBcD  ')
    expect(r.tipo).toBe('link-curto')
  })
})

describe('classificarEntrada — link do Maps sem coordenada', () => {
  it('/maps/place sem @ vai para o servidor', () => {
    const r = classificarEntrada(
      'https://www.google.com/maps/place/Ultra+Academia+Goiania',
    )
    expect(r.tipo).toBe('link-maps')
    expect(r.precisaServidor).toBe(true)
  })

  it('maps.google.com tambem conta', () => {
    expect(classificarEntrada('https://maps.google.com/?cid=123').tipo).toBe('link-maps')
  })
})

describe('classificarEntrada — fora do Brasil', () => {
  // parseCoordinate devolve `null` tanto para "nao e coordenada" quanto para "fora do
  // Brasil". Separar os dois e o ponto deste bloco: a mensagem muda.
  it('coordenada de Lisboa vira aviso proprio, nao "endereco"', () => {
    const r = classificarEntrada('38.7223, -9.1393')
    expect(r.tipo).toBe('fora-do-brasil')
    expect(r.coord).toBeNull()
    expect(r.precisaServidor).toBe(false)
    expect(r.aviso).toMatch(/fora do Brasil/i)
  })

  it('lat/lng trocadas (o erro comum) caem no mesmo aviso', () => {
    // -46.65, -23.56 e' o par invertido: longitude no lugar da latitude.
    const r = classificarEntrada('-46.6565, -23.5613')
    expect(r.tipo).toBe('fora-do-brasil')
  })

  it('coordenada valida do Brasil NAO cai aqui', () => {
    expect(classificarEntrada(`${LAT}, ${LNG}`).tipo).toBe('coordenada')
  })
})

describe('classificarEntrada — endereco', () => {
  it('texto livre vira endereco e vai ao servidor', () => {
    const r = classificarEntrada('Avenida Paulista 1000, Sao Paulo')
    expect(r.tipo).toBe('endereco')
    expect(r.coord).toBeNull()
    expect(r.precisaServidor).toBe(true)
    expect(r.aviso).toBe('')
  })

  it('nome de lugar sem numero tambem', () => {
    expect(classificarEntrada('Setor Marista, Goiania').tipo).toBe('endereco')
  })
})

describe('linkGoogleMaps', () => {
  it('usa ?q= para soltar PINO na coordenada, nao @ que so centraliza', () => {
    expect(linkGoogleMaps(LAT, LNG)).toBe(
      `https://www.google.com/maps?q=${LAT},${LNG}`,
    )
  })

  it('mantem PONTO decimal — virgula pt-BR quebraria a URL', () => {
    const url = linkGoogleMaps(-23.5613, -46.6565)
    expect(url).toContain('-23.5613')
    expect(url).not.toContain('-23,5613')
  })

  it('o proprio link volta a ser lido por classificarEntrada (ida e volta)', () => {
    const r = classificarEntrada(linkGoogleMaps(LAT, LNG))
    expect(r.tipo).toBe('coordenada')
    expect(r.coord?.lat).toBeCloseTo(LAT, 4)
    expect(r.coord?.lng).toBeCloseTo(LNG, 4)
  })
})
