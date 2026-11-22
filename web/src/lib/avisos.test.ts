import { describe, expect, it } from 'vitest'

import {
  avisosDoPayload,
  quandoDoAviso,
  rotuloDoContador,
  textoDoAviso,
  type ItemDeAviso,
} from './avisos'

const item = (extra: Partial<ItemDeAviso>): ItemDeAviso => ({
  id: 1,
  aviso: 'estudo_master',
  quando: null,
  quem: 'Dalmo Dias Ribeiro',
  dados: {},
  masters: ['DF/GO'],
  lido: false,
  ...extra,
})

describe('o sino dos pedidos dos masters (DEC-090)', () => {
  it('o estudo diz quem pediu, de onde (o lugar e a coordenada) e se foi fora da área', () => {
    const dentro = item({ dados: { lat: -15.8234, lng: -48.1104, lugar: 'Ceilândia, Brasília/DF', fora_da_area: false } })
    expect(textoDoAviso(dentro)).toEqual({
      titulo: 'Estudo pedido · DF/GO',
      linha: 'Dalmo Dias Ribeiro pediu o estudo de Ceilândia, Brasília/DF (-15,82, -48,11).',
      destaque: null,
    })
    const fora = item({ dados: { lat: -23.5505, lng: -46.6333, lugar: null, fora_da_area: true } })
    expect(textoDoAviso(fora)).toEqual({
      titulo: 'Estudo pedido · DF/GO',
      linha: 'Dalmo Dias Ribeiro pediu o estudo de (-23,55, -46,63).',
      destaque: 'Fora da área',
    })
  })

  it('o imóvel diz quem pediu e a região que ele escreveu', () => {
    const imovel = item({ aviso: 'imovel_master', dados: { regiao: ' Águas Claras, perto do metrô ' } })
    expect(textoDoAviso(imovel)).toEqual({
      titulo: 'Imóvel pedido · DF/GO',
      linha: 'Dalmo Dias Ribeiro pediu um imóvel em: Águas Claras, perto do metrô',
      destaque: null,
    })
    // Sem nome de quem pediu e sem master: o aviso ainda se lê.
    expect(textoDoAviso(item({ aviso: 'imovel_master', quem: null, masters: [], dados: {} })).linha).toBe(
      'Um master pediu um imóvel.',
    )
  })

  it('a hora na hora local, e vazio sem data', () => {
    const iso = new Date(2026, 10, 19, 14, 32).toISOString()
    expect(quandoDoAviso(iso)).toBe('19/11 14:32')
    expect(quandoDoAviso(null)).toBe('')
    expect(quandoDoAviso('não é data')).toBe('')
  })

  it('o sino só aparece com aviso conhecido no /api/me', () => {
    expect(avisosDoPayload({ avisos: ['imovel_master', 'outro', 'estudo_master'] })).toEqual([
      'estudo_master',
      'imovel_master',
    ])
    expect(avisosDoPayload({})).toEqual([])
    expect(avisosDoPayload(null)).toEqual([])
  })

  it('o contador vai até 9 e depois "9+"', () => {
    expect(rotuloDoContador(0)).toBe('0')
    expect(rotuloDoContador(9)).toBe('9')
    expect(rotuloDoContador(12)).toBe('9+')
  })
})
