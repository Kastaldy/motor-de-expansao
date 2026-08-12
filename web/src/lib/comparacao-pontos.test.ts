import { describe, expect, it } from 'vitest'

import {
  DIMENSOES_PONTO,
  MAX_PONTOS,
  compararPontos,
  indiceDoMesmoPonto,
  rotuloDoPonto,
  rotulosDosPontos,
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

describe('indiceDoMesmoPonto', () => {
  const p1 = ponto({ lat: -16.6869, lng: -49.2648 })
  const p2 = ponto({ lat: -16.706, lng: -49.24 })

  it('acha a coordenada repetida — o Enter dado duas vezes', () => {
    expect(indiceDoMesmoPonto([p1, p2], -16.6869, -49.2648)).toBe(0)
    expect(indiceDoMesmoPonto([p1, p2], -16.706, -49.24)).toBe(1)
  })

  it('devolve -1 para coordenada nova', () => {
    expect(indiceDoMesmoPonto([p1, p2], -23.5613, -46.6565)).toBe(-1)
  })

  it('trata como o MESMO ponto uma diferença abaixo do metro', () => {
    // 1e-7 de grau ≈ 1 cm: o mesmo imóvel, devolvido por caminhos diferentes.
    expect(indiceDoMesmoPonto([p1], -16.6869001, -49.2648001)).toBe(0)
  })

  it('trata como pontos DIFERENTES uma diferença acima do metro', () => {
    // 1e-4 de grau ≈ 11 m.
    expect(indiceDoMesmoPonto([p1], -16.6870, -49.2648)).toBe(-1)
  })

  it('lista vazia devolve -1 em vez de quebrar', () => {
    expect(indiceDoMesmoPonto([], -16.6869, -49.2648)).toBe(-1)
  })
})

describe('rotulosDosPontos', () => {
  it('nao numera quando os nomes ja se distinguem', () => {
    const r = rotulosDosPontos([ponto({ bairro: 'Bueno' }), ponto({ bairro: 'Marista' })])
    expect(r).toEqual(['Bueno', 'Marista'])
  })

  it('numera os EMPATADOS — o caso de dois endereços da mesma cidade sem bairro', () => {
    const r = rotulosDosPontos([
      ponto({ bairro: null }),
      ponto({ bairro: null }),
      ponto({ bairro: null }),
    ])
    expect(r).toEqual(['1 · São Paulo', '2 · São Paulo', '3 · São Paulo'])
  })

  it('numera SÓ quem empata, preservando o nome de quem é único', () => {
    const r = rotulosDosPontos([
      ponto({ bairro: null }),
      ponto({ bairro: 'Bela Vista' }),
      ponto({ bairro: null }),
    ])
    expect(r).toEqual(['1 · São Paulo', 'Bela Vista', '3 · São Paulo'])
  })

  it('o número é a POSIÇÃO na lista, não a ordem do empate', () => {
    // O 3º ponto continua sendo "3", senão o rótulo não casaria com a aba nem com o mapa.
    const r = rotulosDosPontos([ponto({ bairro: 'X' }), ponto({ bairro: null }), ponto({ bairro: null })])
    expect(r[1]).toBe('2 · São Paulo')
    expect(r[2]).toBe('3 · São Paulo')
  })

  it('resultado nunca tem duas entradas iguais', () => {
    const r = rotulosDosPontos([ponto({ bairro: null }), ponto({ bairro: null })])
    expect(new Set(r).size).toBe(r.length)
  })

  it('lista vazia e lista de um sobrevivem', () => {
    expect(rotulosDosPontos([])).toEqual([])
    expect(rotulosDosPontos([ponto()])).toEqual(['Bela Vista'])
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
