import { describe, expect, it } from 'vitest'

import {
  clampNStudios,
  definirTicketStudio,
  STUDIOS_MAX,
  TICKETS_STUDIO_PADRAO,
  ticketsAtivos,
} from './studios'

describe('studios da Viabilidade', () => {
  it('escada padrão espelha o config (157/167/177) e cabe no teto', () => {
    expect(TICKETS_STUDIO_PADRAO).toEqual([157, 167, 177])
    expect(TICKETS_STUDIO_PADRAO.length).toBe(STUDIOS_MAX)
  })

  it('n = 2 manda exatamente 2 tickets, na ordem', () => {
    expect(ticketsAtivos(TICKETS_STUDIO_PADRAO, 2)).toEqual([157, 167])
  })

  it('n = 0 manda lista vazia', () => {
    expect(ticketsAtivos(TICKETS_STUDIO_PADRAO, 0)).toEqual([])
  })

  it('baixar de 3 para 1 e voltar preserva o que foi digitado', () => {
    let tickets = definirTicketStudio(TICKETS_STUDIO_PADRAO, 0, 150)
    tickets = definirTicketStudio(tickets, 1, 199)
    tickets = definirTicketStudio(tickets, 2, 210)
    expect(ticketsAtivos(tickets, 3)).toEqual([150, 199, 210])
    // o estado guarda as três posições; só o recorte muda
    expect(ticketsAtivos(tickets, 1)).toEqual([150])
    expect(ticketsAtivos(tickets, 3)).toEqual([150, 199, 210])
  })

  it('trocar um ticket não mexe nos outros nem no padrão', () => {
    const t = definirTicketStudio(TICKETS_STUDIO_PADRAO, 1, 180)
    expect(t).toEqual([157, 180, 177])
    expect(TICKETS_STUDIO_PADRAO).toEqual([157, 167, 177])
    expect(definirTicketStudio(t, 5, 999)).toEqual(t)
  })

  it('posição ausente cai no padrão; valor digitado (mesmo 0) segue como está', () => {
    expect(ticketsAtivos([Number.NaN], 3)).toEqual([157, 167, 177])
    expect(ticketsAtivos([0, 160], 2)).toEqual([0, 160])
  })

  it('clamp do número de studios em 0..3', () => {
    expect(clampNStudios(-1)).toBe(0)
    expect(clampNStudios(0)).toBe(0)
    expect(clampNStudios(2)).toBe(2)
    expect(clampNStudios(2.6)).toBe(3)
    expect(clampNStudios(7)).toBe(3)
    expect(clampNStudios('')).toBe(0)
    expect(clampNStudios('abc')).toBe(0)
    expect(ticketsAtivos(TICKETS_STUDIO_PADRAO, 9)).toEqual([157, 167, 177])
  })
})
