import { describe, expect, it } from 'vitest'

import {
  aluguelDeReferencia,
  diferencaDaFaixaPct,
  diferencaDaMedianaPct,
  faixaDoAluguel,
  ROTULO_TIPO_IMOVEL,
  textoDaBase,
  textoDaDiferenca,
  textoDaDiferencaMediana,
  tomDaComparacao,
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
  rs_m2_p25: 18.4,
  rs_m2_p75: 29.1,
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

  it('faixa do mês = p25 e p75 × metragem, na centena', () => {
    expect(faixaDoAluguel(ref(), 1500)).toEqual({ min: 27600, max: 43700 })
    expect(faixaDoAluguel(null, 1500)).toBeNull()
    expect(faixaDoAluguel(ref(), 0)).toBeNull()
  })

  it('comparação contra a ponta mais próxima da faixa', () => {
    const faixa = { min: 27600, max: 43700 }
    expect(diferencaDaFaixaPct(48000, faixa)).toBe(10)
    expect(diferencaDaFaixaPct(22000, faixa)).toBe(-20)
    expect(diferencaDaFaixaPct(30000, faixa)).toBe(0)
    expect(diferencaDaFaixaPct(43700, faixa)).toBe(0)
    // Fora da faixa nunca arredonda para "dentro".
    expect(diferencaDaFaixaPct(43800, faixa)).toBe(1)
    expect(diferencaDaFaixaPct(27500, faixa)).toBe(-1)
    expect(diferencaDaFaixaPct(undefined, faixa)).toBeNull()
    expect(textoDaDiferenca(10)).toBe('10% acima da faixa')
    expect(textoDaDiferenca(-20)).toBe('20% abaixo da faixa')
    expect(textoDaDiferenca(0)).toBe('dentro da faixa')
  })

  it('comparação contra a mediana (espelho do PDF)', () => {
    expect(diferencaDaMedianaPct(48000, 33800)).toBe(42)
    expect(diferencaDaMedianaPct(30000, 33800)).toBe(-11)
    expect(diferencaDaMedianaPct(33800, 33800)).toBe(0)
    expect(diferencaDaMedianaPct(48000, null)).toBeNull()
    expect(diferencaDaMedianaPct(undefined, 33800)).toBeNull()
    expect(textoDaDiferencaMediana(42)).toBe('42% acima da mediana')
    expect(textoDaDiferencaMediana(-11)).toBe('11% abaixo da mediana')
    expect(textoDaDiferencaMediana(0)).toBe('na mediana')
  })

  it('cor: vermelho acima da faixa, amarelo acima da mediana, verde no resto', () => {
    expect(tomDaComparacao(10, 42)).toBe('faixa')
    expect(tomDaComparacao(0, 18)).toBe('mediana')
    expect(tomDaComparacao(0, 0)).toBe('ok')
    expect(tomDaComparacao(0, -11)).toBe('ok')
    expect(tomDaComparacao(-9, -26)).toBe('ok')
    expect(tomDaComparacao(0, null)).toBe('ok')
  })
})
