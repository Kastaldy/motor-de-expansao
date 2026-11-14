import { describe, expect, it } from 'vitest'

import {
  COR_TIPO,
  COR_TIPO_FALLBACK,
  avisoDaProjecao,
  classeAluguelFat,
  corTipo,
  corTipoRgb,
  custoOcup,
  faixaDoModelo,
  faixaDoModeloCurta,
  labelFaixa,
  labelTipo,
  modeloCortouAArea,
  pctAluguelFat,
  projecaoPeloModelo,
  rsM2,
} from './imovel'
import type { Oportunidade } from './types'
import { AVISO_EXTRAPOLACAO_V2 } from './viabilidade-demanda-v2'

function op(extra: Partial<Oportunidade> = {}): Oportunidade {
  return {
    id: 'im_teste',
    titulo: 'Galpão de teste',
    tipo: 'galpao',
    operacao: null,
    uf: 'GO',
    municipio: 'Goiânia',
    bairro: null,
    area: null,
    aluguel: null,
    iptu: null,
    condominio: null,
    rs_m2: null,
    hex_id: '87a8c0ce3ffffff',
    residual: null,
    residual_total: null,
    score: null,
    censo_score: null,
    faixa: null,
    pop: null,
    renda_pc: null,
    sam: null,
    n_ultra: null,
    first_seen: null,
    lat: null,
    lng: null,
    url: null,
    ...extra,
  }
}

describe('corTipo', () => {
  it('devolve a cor do tipo conhecido', () => {
    expect(corTipo('galpao')).toBe(COR_TIPO.galpao)
    expect(corTipo('terreno')).toBe(COR_TIPO.terreno)
  })

  it('loja e comercial dividem a mesma matiz (grupo Comercial/Loja)', () => {
    expect(corTipo('loja')).toBe(corTipo('comercial'))
  })

  it('tipo desconhecido cai no cinza neutro, nunca em undefined', () => {
    expect(corTipo('fazenda')).toBe(COR_TIPO_FALLBACK)
    expect(corTipo('')).toBe(COR_TIPO_FALLBACK)
  })
})

describe('corTipoRgb', () => {
  it('converte o hex do tipo para RGB 0-255 (accessor do deck.gl)', () => {
    expect(corTipoRgb('galpao')).toEqual([0xf2, 0x59, 0x7f])
    expect(corTipoRgb('terreno')).toEqual([0xf2, 0x91, 0x3a])
  })

  it('o fallback tambem converte', () => {
    expect(corTipoRgb('desconhecido')).toEqual([0x8b, 0x97, 0xa5])
  })
})

describe('labelTipo', () => {
  it('exibe o rotulo acentuado do enum bruto', () => {
    expect(labelTipo('galpao')).toBe('Galpão')
    expect(labelTipo('comercial')).toBe('Comercial')
  })

  it('tipo novo capitaliza em vez de sumir; vazio vira Imóvel', () => {
    expect(labelTipo('kitnet')).toBe('Kitnet')
    expect(labelTipo('')).toBe('Imóvel')
  })

  it('o default bruto do backend ("Imovel") ganha o acento na exibição', () => {
    expect(labelTipo('Imovel')).toBe('Imóvel')
    expect(labelTipo('imovel')).toBe('Imóvel')
  })
})

describe('custoOcup', () => {
  it('soma aluguel + IPTU + condominio', () => {
    expect(custoOcup(op({ aluguel: 10_000, iptu: 1_200, condominio: 800 }))).toBe(12_000)
  })

  it('componente ausente conta como 0, nao como NaN', () => {
    expect(custoOcup(op({ aluguel: 10_000 }))).toBe(10_000)
    expect(custoOcup(op())).toBe(0)
  })
})

describe('labelFaixa', () => {
  it('traduz o valor cru da faixa para o rotulo acentuado', () => {
    expect(labelFaixa('prioridade_maxima')).toBe('Prioridade máxima')
    expect(labelFaixa('media')).toBe('Média')
  })

  it('faixa nova capitaliza; null passa adiante', () => {
    expect(labelFaixa('promissora')).toBe('Promissora')
    expect(labelFaixa(null)).toBeNull()
  })
})

describe('regua aluguel/faturamento (15/20/30 do modelo de viabilidade)', () => {
  it('pctAluguelFat deriva a fracao e exige as duas pontas', () => {
    expect(pctAluguelFat(op({ aluguel: 30_000, fat_proj: 200_000 }))).toBe(15)
    expect(pctAluguelFat(op({ aluguel: 30_000 }))).toBeNull()
    expect(pctAluguelFat(op({ fat_proj: 200_000 }))).toBeNull()
    expect(pctAluguelFat(op({ aluguel: 30_000, fat_proj: 0 }))).toBeNull()
  })

  it('classifica nos mesmos clusters e rotulos da Viabilidade', () => {
    expect(classeAluguelFat(12)?.rotulo).toBe('dentro do ideal')
    expect(classeAluguelFat(15)?.rotulo).toBe('dentro do ideal')
    expect(classeAluguelFat(18)?.rotulo).toBe('no teto')
    expect(classeAluguelFat(25)?.rotulo).toBe('exceção')
    expect(classeAluguelFat(31)?.rotulo).toBe('acima do máximo')
    expect(classeAluguelFat(null)).toBeNull()
  })
})

describe('rsM2', () => {
  it('prefere o rs_m2 servido pelo backend', () => {
    expect(rsM2(op({ rs_m2: 21.5, aluguel: 99, area: 1 }))).toBe(21.5)
  })

  it('deriva aluguel/area quando o backend nao mandou', () => {
    expect(rsM2(op({ aluguel: 30_000, area: 1_500 }))).toBe(20)
  })

  it('sem area (ou area 0) nao inventa numero', () => {
    expect(rsM2(op({ aluguel: 30_000 }))).toBeNull()
    expect(rsM2(op({ aluguel: 30_000, area: 0 }))).toBeNull()
  })
})

describe('projeção de faturamento: modelo de praça ou curva (DEC-086)', () => {
  const praca = (extra: Partial<Oportunidade> = {}) =>
    op({ fat_fonte: 'praca', fat_proj: 300_000, fat_p10: 203_000, fat_p90: 483_000, ...extra })

  it('a fonte é a do servidor; sem campo (servidor antigo) é a curva', () => {
    expect(projecaoPeloModelo(praca())).toBe(true)
    expect(projecaoPeloModelo(op({ fat_fonte: 'densidade' }))).toBe(false)
    expect(projecaoPeloModelo(op())).toBe(false)
  })

  it('a faixa do modelo usa o rótulo do simulador e some fora do modelo', () => {
    expect(faixaDoModelo(praca())).toMatch(/^Faixa do modelo: R\$ 203 mil–R\$ 483 mil$/)
    expect(faixaDoModelo(op({ fat_fonte: 'densidade', fat_proj: 200_000 }))).toBeNull()
    expect(faixaDoModelo(praca({ fat_p90: null }))).toBeNull()
  })

  it('a faixa curta da lista não repete o símbolo da moeda', () => {
    expect(faixaDoModeloCurta(praca())).toMatch(/^R\$ 203k–483k$/)
    expect(faixaDoModeloCurta(op())).toBeNull()
  })

  it('o aviso de extrapolação é o MESMO texto do simulador, só no modelo', () => {
    expect(avisoDaProjecao(praca({ fat_extrapolacao: true }))).toBe(AVISO_EXTRAPOLACAO_V2)
    expect(avisoDaProjecao(praca({ fat_extrapolacao: false }))).toBeNull()
    expect(avisoDaProjecao(op({ fat_fonte: 'densidade', fat_extrapolacao: true }))).toBeNull()
  })

  it('o teto do modelo só é dito quando cortou a área do anúncio', () => {
    expect(modeloCortouAArea(praca({ area: 3000, m2_modelo: 2800 }))).toBe(true)
    expect(modeloCortouAArea(praca({ area: 1500, m2_modelo: 1500 }))).toBe(false)
    expect(modeloCortouAArea(op({ fat_fonte: 'densidade', area: 3000 }))).toBe(false)
  })

  it('a régua do aluguel segue o número servido, venha de onde vier', () => {
    expect(pctAluguelFat(praca({ aluguel: 30_000 }))).toBe(10)
  })
})
