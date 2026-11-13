import { describe, expect, it } from 'vitest'

import {
  FORMULARIO_VAZIO,
  avisoDoPrazo,
  coordenadaTexto,
  coordenadasSuperadas,
  distanciaTexto,
  formularioDaPrevia,
  formularioDaUnidade,
  lerFormulario,
  pinsComUnidadesDoSite,
  prazoTexto,
  rotuloMaisPerto,
  unidadesNoPrazo,
} from './inclusao-unidade'
import { parseCoordinate } from './coord'
import type { Pins, PreviaUnidadeSite, UnidadeSite } from './types'

const PREVIA: PreviaUnidadeSite = {
  unidade: 'Teresópolis',
  uf: 'RJ',
  cidade: 'Teresópolis',
  lat: -22.407291,
  lng: -42.96576,
  hex_id_res7: '87a8a0c6dffffff',
  mais_perto: { unidade: 'Maricá / RJ', cidade: 'Maricá', uf: 'RJ', distancia_m: 64_321 },
  prazo_horas: 24,
}

function unidade(extra: Partial<UnidadeSite> = {}): UnidadeSite {
  return {
    id: 1,
    ultra_id: 'site-1',
    id_no_mapa: 'cadastro-site-1',
    unidade: 'Teresópolis',
    uf: 'RJ',
    cidade: 'Teresópolis',
    lat: -22.407291,
    lng: -42.96576,
    criada_em: '2026-11-13T18:32:00+00:00',
    prazo_ate: '2026-11-14T18:32:00+00:00',
    no_prazo: true,
    incluida_por: 'Pessoa Growth',
    ...extra,
  }
}

describe('lerFormulario', () => {
  it('só nome e coordenada: UF e cidade vêm do ponto, no servidor', () => {
    expect(FORMULARIO_VAZIO).toEqual({ unidade: '', coordenadas: '' })
    const r = lerFormulario({ unidade: '  Teresópolis ', coordenadas: '-22.407291, -42.965760' })
    expect(r).toEqual({ ok: true, campos: { unidade: 'Teresópolis', lat: -22.407291, lng: -42.96576 } })
  })

  it('aceita o link do mapa e a vírgula decimal', () => {
    const link = lerFormulario({ ...FORMULARIO_VAZIO, unidade: 'X1', coordenadas: 'https://www.google.com/maps/@-22.4073,-42.9658,17z' })
    expect(link.ok && [link.campos.lat, link.campos.lng]).toEqual([-22.4073, -42.9658])
    const virgula = lerFormulario({ ...FORMULARIO_VAZIO, unidade: 'X1', coordenadas: '-22,4073; -42,9658' })
    expect(virgula.ok && [virgula.campos.lat, virgula.campos.lng]).toEqual([-22.4073, -42.9658])
  })

  it('sem nome, sem coordenada ou com coordenada fora do país não pede revisão', () => {
    expect(lerFormulario({ ...FORMULARIO_VAZIO, coordenadas: '-22.4, -42.9' })).toEqual({
      ok: false,
      erro: 'Preencha o nome da unidade.',
    })
    const sem = lerFormulario({ ...FORMULARIO_VAZIO, unidade: 'Teresópolis' })
    expect(sem.ok).toBe(false)
    expect(!sem.ok && sem.erro).toContain('Cole as coordenadas')
    // latitude e longitude trocadas caem fora do Brasil
    const trocada = lerFormulario({ ...FORMULARIO_VAZIO, unidade: 'Teresópolis', coordenadas: '-42.965760, -22.407291' })
    expect(!trocada.ok && trocada.erro).toContain('fora do país')
  })
})

describe('Corrigir e Alterar devolvem o formulário preenchido', () => {
  it('a revisão volta com o nome e a coordenada revisados', () => {
    expect(formularioDaPrevia(PREVIA)).toEqual({ unidade: 'Teresópolis', coordenadas: '-22.407291, -42.965760' })
    expect(formularioDaUnidade(unidade())).toEqual({ unidade: 'Teresópolis', coordenadas: '-22.407291, -42.965760' })
  })

  it('a coordenada do formulário relida dá o mesmo ponto', () => {
    expect(parseCoordinate(coordenadaTexto(-22.407291, -42.96576))).toEqual({ lat: -22.407291, lng: -42.96576 })
    expect(formularioDaUnidade(unidade()).coordenadas).toBe('-22.407291, -42.965760')
  })
})

describe('textos da revisão e da lista', () => {
  it('distância em metros até 1 km e em km depois', () => {
    expect(distanciaTexto(350)).toBe('350 m')
    expect(distanciaTexto(64_321)).toBe('64,3 km')
  })

  it('a unidade mais perto não repete a cidade que o nome já traz', () => {
    expect(rotuloMaisPerto(PREVIA.mais_perto!)).toBe('Maricá / RJ, a 64,3 km')
    expect(rotuloMaisPerto({ unidade: 'Santana', cidade: 'São Paulo', uf: 'SP', distancia_m: 850 })).toBe(
      'Santana (São Paulo/SP), a 850 m',
    )
    expect(rotuloMaisPerto({ unidade: 'Capim Macio', cidade: '', uf: 'RN', distancia_m: 1200 })).toBe(
      'Capim Macio, a 1,2 km',
    )
  })

  it('o prazo sai no fuso de quem olha', () => {
    expect(prazoTexto('2026-11-14T18:32:00+00:00', 'America/Sao_Paulo')).toBe('até 14/11 às 15:32')
  })

  it('o aviso diz o prazo, quem corrige depois dele e quando entra no mercado', () => {
    const aviso = avisoDoPrazo(24)
    expect(aviso).toContain('1 dia para alterar ou remover')
    expect(aviso).toContain('time de tecnologia')
    expect(aviso).toContain('domingo')
  })

  it('a lista do painel mostra com Alterar e Remover só as que ainda estão no prazo', () => {
    const lista = [unidade(), unidade({ id: 2, no_prazo: false })]
    expect(unidadesNoPrazo(lista).map((u) => u.id)).toEqual([1])
  })
})

describe('o pino da unidade incluída, com a logo, no mapa já carregado', () => {
  const PINS: Pins = {
    concorrentes: [],
    ultra: [{ lat: -22.922484, lng: -42.817391, nome: 'Maricá / RJ' }],
    icones: { __ultra__: 'data:image/png;base64,LOGO' },
  }

  it('soma a unidade nova aos pinos do recorte, com o nome dela', () => {
    const r = pinsComUnidadesDoSite(PINS, [unidade()], new Set(), 'data:image/png;base64,OUTRO')
    expect(r?.ultra.map((p) => p.nome)).toEqual(['Maricá / RJ', 'Teresópolis'])
    // o ícone que o recorte já tinha fica
    expect(r?.icones.__ultra__).toBe('data:image/png;base64,LOGO')
  })

  it('não duplica a unidade que o servidor já mandou no payload', () => {
    const comElas: Pins = { ...PINS, ultra: [...PINS.ultra, { lat: -22.407291, lng: -42.96576, nome: 'Teresópolis' }] }
    expect(pinsComUnidadesDoSite(comElas, [unidade()], new Set(), null)).toBe(comElas)
  })

  it('num recorte sem Ultra, o pino ganha o ícone da logo', () => {
    const vazio: Pins = { concorrentes: [], ultra: [], icones: {} }
    const r = pinsComUnidadesDoSite(vazio, [unidade()], new Set(), 'data:image/png;base64,LOGO')
    expect(r?.ultra).toHaveLength(1)
    expect(r?.icones.__ultra__).toBe('data:image/png;base64,LOGO')
  })

  it('a removida e o ponto antigo da alterada saem do mapa já carregado', () => {
    const antes = [unidade(), unidade({ id: 2, unidade: 'Copacabana', lat: -22.9711, lng: -43.1863 })]
    const movida = unidade({ lat: -22.41, lng: -42.97 })
    const superadas = new Set(coordenadasSuperadas(antes, [movida]))
    expect(superadas.size).toBe(2)
    const doPayload: Pins = {
      ...PINS,
      ultra: [...PINS.ultra, { lat: -22.407291, lng: -42.96576, nome: 'Teresópolis' }, { lat: -22.9711, lng: -43.1863, nome: 'Copacabana' }],
    }
    const r = pinsComUnidadesDoSite(doPayload, [movida], superadas, null)
    expect(r?.ultra.map((p) => [p.nome, p.lat])).toEqual([
      ['Maricá / RJ', -22.922484],
      ['Teresópolis', -22.41],
    ])
  })

  it('sem payload ainda, nada é inventado', () => {
    expect(pinsComUnidadesDoSite(undefined, [unidade()], new Set(), 'x')).toBeUndefined()
  })
})
