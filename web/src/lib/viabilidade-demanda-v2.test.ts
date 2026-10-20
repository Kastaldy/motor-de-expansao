import { describe, expect, it } from 'vitest'

import type { DemandaV2Out } from './types'
import {
  avisosV2,
  camposDeV2,
  corpoSugestaoV2,
  motivoV2,
  sementeDaDemandaV2,
  sugestaoValePara,
  v2Disponivel,
} from './viabilidade-demanda-v2'

function sug(parcial: Partial<DemandaV2Out> = {}): DemandaV2Out {
  return {
    faturamento: { p10: 189000, p50: 300000, p90: 474000 },
    alunos: { p10: 1450.4, p50: 2303.6, p90: 3640.2 },
    conversao: { fixo: 5000, r_aluno: 128.1 },
    entradas: {
      m2: 1500,
      studios: 0,
      pop_c10: 300000,
      dom_c10: 100000,
      renda_pc_c10: 1800,
      renda_dom_c10: 5400,
    },
    flag_extrapolacao: false,
    fora_do_envelope: [],
    faixa_provisoria: true,
    coeficientes: { versao: 't', sha256: 'a'.repeat(64), data: '2026-10-20' },
    token: 'v2-abc',
    ...parcial,
  }
}

describe('disponibilidade decidida pelo SERVIDOR', () => {
  it('só com disponivel === true', () => {
    expect(v2Disponivel(null)).toBe(false)
    expect(v2Disponivel(undefined)).toBe(false)
    expect(
      v2Disponivel({ disponivel: false, motivo: 'desligada', versao: null, sha256: null }),
    ).toBe(false)
    expect(v2Disponivel({ disponivel: true, motivo: null, versao: 'x', sha256: 'y' })).toBe(true)
  })

  it('o motivo do servidor vence; sem estado, o erro da sugestão', () => {
    const fora = { disponivel: false, motivo: 'A Viabilidade v2 está desligada.', versao: null, sha256: null }
    expect(motivoV2(fora, null)).toBe('A Viabilidade v2 está desligada.')
    expect(motivoV2(null, 'Falhou')).toBe('Falhou')
    expect(motivoV2({ disponivel: true, motivo: null, versao: 'x', sha256: 'y' }, null)).toBeNull()
  })
})

describe('semente pelo p50 da v2', () => {
  it('arredonda o p50 em alunos', () => {
    expect(sementeDaDemandaV2(sug())).toBe(2304)
  })
  it('sem sugestão ou p50 inválido não inventa número', () => {
    expect(sementeDaDemandaV2(null)).toBeNull()
    expect(sementeDaDemandaV2(sug({ alunos: { p10: null, p50: null, p90: null } }))).toBeNull()
    expect(sementeDaDemandaV2(sug({ alunos: { p10: 1, p50: 0, p90: 2 } }))).toBeNull()
  })
})

describe('o pedido só carimba v2 com sugestão válida para o cenário', () => {
  it('mesma metragem e mesma presença de estúdio -> v2 + token + entradas', () => {
    expect(camposDeV2(sug(), 1500, 0)).toEqual({
      modelo_demanda: 'v2',
      demanda_v2: { token: 'v2-abc', pop_c10: 300000, dom_c10: 100000, renda_pc_c10: 1800 },
    })
  })
  it('metragem mudou -> sugestão velha, pedido no modo densidade (sem chaves)', () => {
    expect(camposDeV2(sug(), 1600, 0)).toEqual({})
  })
  it('estúdio é binário: 1 -> 2 estúdios mantém a sugestão; 0 -> 1 a invalida', () => {
    const com = sug({ entradas: { ...sug().entradas, studios: 1 } })
    expect(sugestaoValePara(com, 1500, 1)).toBe(true)
    expect(sugestaoValePara(com, 1500, 2)).toBe(true)
    expect(sugestaoValePara(sug(), 1500, 1)).toBe(false)
  })
  it('sem sugestão (v2 indisponível) -> nada muda no pedido', () => {
    expect(camposDeV2(null, 1500, 0)).toEqual({})
  })
})

describe('corpo da sugestão', () => {
  it('leva a metragem, o ticket, o mix e os tickets dos estúdios ativos', () => {
    expect(
      corpoSugestaoV2({ lat: -23, lng: -51, m2: 1500, ticket: 147, ticketsStudios: [210, 190] }),
    ).toEqual({
      lat: -23,
      lng: -51,
      m2: 1500,
      ticket: 147,
      share_balcao: undefined,
      n_studios: 2,
      tickets_studios: [210, 190],
    })
  })
})

describe('avisos', () => {
  it('a faixa provisória aparece sempre que o servidor a marca', () => {
    expect(avisosV2(sug())).toEqual([
      'Faixa provisória: no teste fora da amostra ela cobriu 72% das unidades.',
    ])
  })
  it('extrapolação e reta forçada sem agregador', () => {
    const a = avisosV2(
      sug({ faixa_provisoria: false, flag_extrapolacao: true, rampa_reta_forcada_sem_agregador: true }),
    )
    expect(a).toHaveLength(2)
    expect(a[0]).toContain('extrapolação')
    expect(a[1]).toBe('Sem agregador: a rampa usada é a reta.')
  })
})
