import { describe, expect, it } from 'vitest'

import {
  aluguelDeReferencia,
  diferencaPct,
  ROTULO_TIPO_IMOVEL,
  textoDaBase,
  textoDaDiferenca,
  TIPO_IMOVEL_PADRAO,
  type AluguelReferencia,
} from './aluguel-referencia'

const ref = (over: Partial<AluguelReferencia> = {}): AluguelReferencia => ({
  tipo: 'comercial',
  rs_m2: 22.5,
  n_anuncios: 7,
  nivel: 'municipio',
  uf: 'ES',
  municipio: 'Vitória',
  ...over,
})

describe('régua de aluguel (DEC-080)', () => {
  it('o seletor abre em Comercial (valor bruto loja)', () => {
    expect(TIPO_IMOVEL_PADRAO).toBe('loja')
    expect(ROTULO_TIPO_IMOVEL.loja).toBe('Comercial')
    expect(ROTULO_TIPO_IMOVEL.comercial).toBe('Laje Corporativa')
  })

  it('aluguel de referência = metragem × R$/m², na centena', () => {
    expect(aluguelDeReferencia(ref(), 1500)).toBe(33800)
    expect(aluguelDeReferencia(null, 1500)).toBeNull()
    expect(aluguelDeReferencia(ref(), 0)).toBeNull()
  })

  it('a base é fato neutro, sem fonte, data nem selo de confiança', () => {
    const textos = [
      textoDaBase(ref()),
      textoDaBase(ref({ nivel: 'uf', municipio: null, tipo: 'galpao', n_anuncios: 74, uf: 'GO' })),
      textoDaBase(ref({ nivel: 'brasil', municipio: null, uf: null, tipo: 'loja', n_anuncios: 752 })),
    ]
    expect(textos).toEqual([
      'Base: 7 anúncios de laje corporativa em Vitória/ES',
      'Base: 74 anúncios de galpão no estado (GO)',
      'Base: 752 anúncios de comercial no Brasil',
    ])
    for (const t of textos) expect(t).not.toMatch(/confian|OLX|baixa|\d{4}/i)
  })

  it('diferença em % contra a referência', () => {
    expect(diferencaPct(32000, 25000)).toBe(28)
    expect(diferencaPct(20000, 25000)).toBe(-20)
    expect(diferencaPct(undefined, 25000)).toBeNull()
    expect(textoDaDiferenca(28)).toBe('28% acima da referência')
    expect(textoDaDiferenca(-20)).toBe('20% abaixo da referência')
    expect(textoDaDiferenca(0)).toBe('igual à referência')
  })
})
