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

// O caso da revisão de 2026-10-20: sugestão tirada em Londrina, ponto trocado para Manaus.
const LONDRINA = { lat: -23.33, lng: -51.16 }
const MANAUS = { lat: -3.0, lng: -60.0 }
const cen = (m2: number, nStudios: number, ponto = LONDRINA) => ({ ...ponto, m2, nStudios })

function sug(parcial: Partial<DemandaV2Out> = {}): DemandaV2Out {
  return {
    faturamento: { p10: 189000, p50: 300000, p90: 474000 },
    alunos: { p10: 1450.4, p50: 2303.6, p90: 3640.2 },
    conversao: { fixo: 5000, r_aluno: 128.1 },
    ponto: { lat: LONDRINA.lat, lng: LONDRINA.lng },
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
    const fora = { disponivel: false, motivo: 'O modelo está desligado.', versao: null, sha256: null }
    expect(motivoV2(fora, null)).toBe('O modelo está desligado.')
    // sem motivo do servidor, o texto padrão fala do modelo de praça, nunca de versão
    const semMotivo = { disponivel: false, motivo: null, versao: null, sha256: null }
    expect(motivoV2(semMotivo, null)).toBe(
      'A sugestão de demanda pelo modelo de praça está indisponível.',
    )
    expect(motivoV2(semMotivo, null)).not.toMatch(/\bv2\b/i)
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
    expect(camposDeV2(sug(), cen(1500, 0))).toEqual({
      modelo_demanda: 'v2',
      demanda_v2: { token: 'v2-abc', pop_c10: 300000, dom_c10: 100000, renda_pc_c10: 1800 },
    })
  })
  it('metragem mudou -> sugestão velha, pedido no modo densidade (sem chaves)', () => {
    expect(camposDeV2(sug(), cen(1600, 0))).toEqual({})
  })
  it('ponto mudou (Londrina -> Manaus) -> sugestão velha, pedido sem token', () => {
    expect(sugestaoValePara(sug(), cen(1500, 0, MANAUS))).toBe(false)
    expect(camposDeV2(sug(), cen(1500, 0, MANAUS))).toEqual({})
    // ~1 m de diferença (5ª casa) ainda é o mesmo ponto; sem ponto na tela, não vale.
    expect(sugestaoValePara(sug(), cen(1500, 0, { lat: -23.330004, lng: -51.16 }))).toBe(true)
    expect(sugestaoValePara(sug(), cen(1500, 0, { lat: -23.3301, lng: -51.16 }))).toBe(false)
    expect(sugestaoValePara(sug(), { lat: undefined, lng: undefined, m2: 1500, nStudios: 0 })).toBe(
      false,
    )
  })
  it('estúdio é binário: 1 -> 2 estúdios mantém a sugestão; 0 -> 1 a invalida', () => {
    const com = sug({ entradas: { ...sug().entradas, studios: 1 } })
    expect(sugestaoValePara(com, cen(1500, 1))).toBe(true)
    expect(sugestaoValePara(com, cen(1500, 2))).toBe(true)
    expect(sugestaoValePara(sug(), cen(1500, 1))).toBe(false)
  })
  it('sem sugestão (v2 indisponível) -> nada muda no pedido', () => {
    expect(camposDeV2(null, cen(1500, 0))).toEqual({})
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

describe('avisos (emenda de 21/10/2026: sem aviso de faixa provisória)', () => {
  it('a faixa marcada provisória pelo servidor NÃO vira aviso na tela', () => {
    expect(avisosV2(sug())).toEqual([])
  })
  it('só a extrapolação vira aviso; "reta forçada" não existe mais', () => {
    const a = avisosV2(
      sug({ faixa_provisoria: true, flag_extrapolacao: true, rampa_reta_forcada_sem_agregador: true }),
    )
    expect(a).toEqual([
      'Este ponto está fora do intervalo das unidades usadas no ajuste (extrapolação).',
    ])
    expect(a.join(' ')).not.toMatch(/provis|reta|\bv2\b/i)
  })
})

describe('mesmoPonto arredonda como o servidor (5 casas)', () => {
  it('dois pontos dos dois lados da fronteira de arredondamento não são o mesmo', async () => {
    const { mesmoPonto } = await import('./viabilidade-demanda-v2')
    expect(mesmoPonto(-23.330004, -23.330006)).toBe(false)
    expect(mesmoPonto(-23.330001, -23.330004)).toBe(true)
    expect(mesmoPonto(-23.33, -23.3301)).toBe(false)
    expect(mesmoPonto(null, -23.33)).toBe(false)
  })
})

describe('a chave da sugestão v2 inclui o ponto exato', () => {
  it('trocar de endereço no mesmo hexágono pede sugestão nova', async () => {
    const { readFileSync } = await import('node:fs')
    const { fileURLToPath } = await import('node:url')
    const fonte = readFileSync(fileURLToPath(new URL('../screens/ViabilityScreen.tsx', import.meta.url)), 'utf-8')
    const i = fonte.indexOf('const chaveSugestaoV2 = [')
    expect(fonte.slice(i, i + 120)).toMatch(/alvoLat,\s+alvoLng,/)
  })
})
