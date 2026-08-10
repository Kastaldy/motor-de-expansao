import { describe, expect, it } from 'vitest'

import {
  DIMENSOES_PONTO,
  MAX_PONTOS,
  compararPontos,
  rotuloDoPonto,
} from './comparacao-pontos'
import type { PontoPayload } from './types'

/** Ponto com a forma real do `/api/ponto` (valores da Av. Paulista). */
function ponto(over: Record<string, unknown> = {}): PontoPayload {
  const o = over as {
    bairro?: string | null
    municipio?: string | null
    residual?: number | null
    populacao?: number | null
    conc?: number | null
    renda?: number | null
    score?: number | null
    dens?: number | null
    lat?: number
    lng?: number
  }
  return {
    lat: o.lat ?? -23.5613,
    lng: o.lng ?? -46.6565,
    raio_km: 1,
    hex_id: '87a8100c5ffffff',
    local: {
      uf: 'SP',
      // `?? default` engoliria o `null` EXPLICITO que o teste do fallback precisa.
      municipio: o.municipio === undefined ? 'São Paulo' : o.municipio,
      bairro: o.bairro === undefined ? 'Bela Vista' : o.bairro,
      unidade_tipo: 'distrito',
    },
    censo: {
      disponivel: true,
      motivo: null,
      populacao: o.populacao ?? 66113,
      domicilios: 33609,
      renda_per_capita: 5838,
      renda_media_domiciliar: o.renda ?? 11452,
      densidade_hab_km2: o.dens ?? 21047,
      score_socioeconomico: o.score ?? 66.8,
      n_setores: 333,
    },
    concorrencia: {
      disponivel: true,
      motivo: null,
      n_concorrentes: o.conc ?? 17,
      n_ultra: 1,
    },
    mercado: {
      disponivel: true,
      motivo: null,
      sam: 19215,
      residual: o.residual ?? 0,
      score_residual: 0,
    },
    vizinhos: [],
    reguas: null,
    criterios: [],
  } as unknown as PontoPayload
}

describe('DIMENSOES_PONTO', () => {
  it('residual vem primeiro na prioridade', () => {
    expect(DIMENSOES_PONTO[0].chave).toBe('residual')
  })

  it('concorrentes e a unica invertida', () => {
    expect(DIMENSOES_PONTO.filter((d) => !d.maiorEhMelhor).map((d) => d.chave)).toEqual([
      'concorrentes',
    ])
  })

  it('limiar de concorrente e 1, nao 2 como nos hexagonos', () => {
    /* No ponto o numero e CONTAGEM REAL de pins em 1,0 km, nao a oferta ponderada por
       distancia que o mapa estima — um concorrente a mais e um concorrente a mais. */
    const dim = DIMENSOES_PONTO.find((d) => d.chave === 'concorrentes')!
    expect(dim.limiarAbsoluto).toBe(1)
  })

  it('NAO compara viabilidade', () => {
    // Dois imoveis com a mesma metragem e o mesmo aluguel produzem DRE identico
    // (DEC-009: demanda e premissa digitada) — duas colunas iguais leriam como bug.
    const chaves = DIMENSOES_PONTO.map((d) => d.chave)
    for (const proibida of ['margem', 'payback', 'aluguel', 'break_even', 'tir']) {
      expect(chaves).not.toContain(proibida)
    }
  })

  it('le do payload sem quebrar quando o bloco nao veio', () => {
    const vazio = { censo: {}, mercado: {}, concorrencia: {} } as unknown as PontoPayload
    for (const d of DIMENSOES_PONTO) expect(d.ler(vazio)).toBeNull()
  })
})

describe('rotuloDoPonto', () => {
  it('prefere o bairro', () => {
    expect(rotuloDoPonto(ponto())).toBe('Bela Vista')
  })

  it('cai no municipio quando nao ha bairro', () => {
    expect(rotuloDoPonto(ponto({ bairro: null }))).toBe('São Paulo')
  })

  it('cai na coordenada quando nao ha nem municipio', () => {
    expect(rotuloDoPonto(ponto({ bairro: null, municipio: null }))).toBe('-23.5613, -46.6565')
  })
})

describe('compararPontos', () => {
  it('usa o mesmo nucleo: frase com "porem" quando ha vantagem e desvantagem', () => {
    const a = ponto({ bairro: 'A', residual: 9000, conc: 1, populacao: 20000 })
    const b = ponto({ bairro: 'B', residual: 500, conc: 12, populacao: 60000 })
    const c = compararPontos(a, b)
    expect(c.frase).toContain('mais residual disponível')
    expect(c.frase).toContain('menos concorrentes')
    expect(c.frase).toContain('porém')
    expect(c.frase).toContain('menos população no raio')
  })

  it('respeita o teto de 3 dimensoes na frase', () => {
    const a = ponto({ bairro: 'A', residual: 9000, populacao: 60000, conc: 0, renda: 20000, score: 90, dens: 30000 })
    const b = ponto({ bairro: 'B', residual: 100, populacao: 5000, conc: 15, renda: 2000, score: 20, dens: 2000 })
    expect(compararPontos(a, b).destaques.length).toBeLessThanOrEqual(3)
  })

  it('pontos equivalentes nao inventam diferenca', () => {
    const c = compararPontos(ponto({ bairro: 'A' }), ponto({ bairro: 'B' }))
    expect(c.vencedor).toBe('empate')
    expect(c.frase).toContain('equivalentes')
  })

  it('usa o rotulo de cada ponto na frase', () => {
    const c = compararPontos(
      ponto({ bairro: 'Bela Vista', residual: 9000 }),
      ponto({ bairro: 'Taboão', residual: 100 }),
    )
    expect(c.frase).toContain('Bela Vista')
    expect(c.frase).toContain('Taboão')
  })
})

describe('MAX_PONTOS', () => {
  it('teto de 4 — a tabela e de duas colunas', () => {
    expect(MAX_PONTOS).toBe(4)
  })
})
