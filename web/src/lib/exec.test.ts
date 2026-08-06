import { describe, expect, it } from 'vitest'

import {
  enquadrar,
  filtrarUnidades,
  formatarMetrica,
  lerDelta,
  normalizar,
  ordenarUnidades,
  queryDaCarteira,
  rotuloMesCompetencia,
  rotuloRanking,
  rotuloVsMedia,
  tituloDaCelula,
} from './exec'
import type { RedeMetrica, RedeUnidade } from './types'

function metrica(p: Partial<RedeMetrica> = {}): RedeMetrica {
  return { atual: null, m1: null, delta_pct: null, rank: null, rank_total: null, vs_media_pct: null, ...p }
}

function unidade(nome: string, p: Partial<RedeUnidade> = {}): RedeUnidade {
  return {
    id: nome.toLowerCase(),
    nome,
    uf: 'SP',
    master: 'ULTRA',
    cidade: null,
    consultor: null,
    consultor_2: null,
    master_franquia: null,
    franqueado: null,
    coorte: '24_47',
    coorte_rotulo: '2 a 4 anos',
    meses_operacao: 30,
    inauguracao: '01/01/2020',
    lat: null,
    lng: null,
    comparavel: true,
    severidade: 'ok',
    severidade_rotulo: 'Sem alerta',
    prioridade: 0,
    resumo: '',
    faixa_faturamento: 'bom',
    faixa_faturamento_rotulo: 'Bom',
    alertas: [],
    metricas: {},
    sparkline: [],
    ...p,
  }
}

describe('formatarMetrica', () => {
  it('mostra churn em PERCENTUAL, não em fração', () => {
    // A armadilha: nesta API a taxa vem em %, e na Viabilidade vem em fração.
    // Um `pctFrac` aqui mostraria "0,1%" de churn e ninguém desconfiaria.
    expect(formatarMetrica(5.93, 'pct')).toBe('5,9%')
  })

  it('usa centavos só quando o centavo importa', () => {
    expect(formatarMetrica(156.68, 'brl')).toBe('R$ 156,68')
    expect(formatarMetrica(412_000, 'brl')).toBe('R$ 412.000')
  })

  it('nulo vira travessão, nunca zero', () => {
    expect(formatarMetrica(null, 'brl')).toBe('—')
    expect(formatarMetrica(undefined, 'int')).toBe('—')
    expect(formatarMetrica(NaN, 'pct')).toBe('—')
  })

  it('NPS negativo é valor legítimo', () => {
    expect(formatarMetrica(-16.7, 'nota')).toBe('-17')
  })
})

describe('quarteto de contexto', () => {
  it('diz a posição e a distância da média em texto', () => {
    const m = metrica({ atual: 100, m1: 90, rank: 79, rank_total: 89, vs_media_pct: -64.2 })
    expect(rotuloRanking(m)).toBe('79º de 89')
    expect(rotuloVsMedia(m)).toBe('64,2% abaixo da média da rede')
    expect(tituloDaCelula('Faturamento', m, 'int')).toContain('79º de 89')
  })

  it('unidade nova não recebe posição inventada', () => {
    const m = metrica({ atual: 8000 })
    expect(rotuloRanking(m)).toBe('sem posição (unidade nova)')
    expect(rotuloVsMedia(m)).toBe('sem comparação com a rede')
  })

  it('na média não vira "0,0% acima"', () => {
    expect(rotuloVsMedia(metrica({ vs_media_pct: 0.01 }))).toBe('na média da rede')
  })
})

describe('lerDelta', () => {
  it('churn subindo é RUIM (o defeito da seta verde)', () => {
    const d = lerDelta(metrica({ atual: 9, m1: 6, delta_pct: 50 }), false, true)
    expect(d).toMatchObject({ subiu: true, bom: false, modo: 'pontos' })
    expect(d?.valor).toBeCloseTo(3)
  })

  it('faturamento subindo é BOM', () => {
    expect(lerDelta(metrica({ delta_pct: 12 }), true)).toMatchObject({ subiu: true, bom: true })
  })

  it('faturamento caindo é ruim', () => {
    expect(lerDelta(metrica({ delta_pct: -12 }), true)).toMatchObject({ subiu: false, bom: false })
  })

  it('variação irrelevante é marcada como estável', () => {
    expect(lerDelta(metrica({ delta_pct: 0.01 }), true)?.estavel).toBe(true)
  })

  it('sem M-1 não inventa variação', () => {
    expect(lerDelta(metrica({ atual: 10 }), true, true)).toBeNull()
    expect(lerDelta(undefined, true)).toBeNull()
  })
})

describe('ordenarUnidades', () => {
  const lista = [
    unidade('A', { metricas: { nps: metrica({ atual: 50 }) } }),
    unidade('B', { metricas: { nps: metrica({ atual: null }) } }),
    unidade('C', { metricas: { nps: metrica({ atual: 90 }) } }),
  ]

  it('nulos ficam por último nas DUAS direções', () => {
    // O `?? -Infinity` da v1 só funcionava em `desc`; em `asc` o dado ausente
    // subia para o topo da lista de trabalho.
    expect(ordenarUnidades(lista, 'nps', 'desc').map((u) => u.nome)).toEqual(['C', 'A', 'B'])
    expect(ordenarUnidades(lista, 'nps', 'asc').map((u) => u.nome)).toEqual(['A', 'C', 'B'])
  })

  it('empate desempata por nome, para a ordem não pular entre renders', () => {
    const empate = [
      unidade('Zulu', { metricas: { nps: metrica({ atual: 10 }) } }),
      unidade('Alfa', { metricas: { nps: metrica({ atual: 10 }) } }),
    ]
    expect(ordenarUnidades(empate, 'nps', 'desc').map((u) => u.nome)).toEqual(['Alfa', 'Zulu'])
  })

  it('ordena por prioridade e por nome', () => {
    const porPrioridade = [unidade('X', { prioridade: 1 }), unidade('Y', { prioridade: 5 })]
    expect(ordenarUnidades(porPrioridade, 'prioridade', 'desc')[0].nome).toBe('Y')
    expect(ordenarUnidades(porPrioridade, 'nome', 'asc')[0].nome).toBe('X')
  })

  it('não muta a lista recebida', () => {
    const original = [...lista]
    ordenarUnidades(lista, 'nps', 'asc')
    expect(lista).toEqual(original)
  })
})

describe('filtrarUnidades', () => {
  const lista = [
    unidade('BOTAFOGO', { cidade: 'Rio de Janeiro', consultor: 'MARISE' }),
    unidade('PÁTIO BRASIL', { cidade: 'Brasília', consultor: 'ANDERSON' }),
  ]

  it('busca sem acento e sem caixa', () => {
    expect(filtrarUnidades(lista, 'patio').map((u) => u.nome)).toEqual(['PÁTIO BRASIL'])
    expect(filtrarUnidades(lista, 'BRASILIA').map((u) => u.nome)).toEqual(['PÁTIO BRASIL'])
  })

  it('busca por consultor e por cidade', () => {
    expect(filtrarUnidades(lista, 'marise')).toHaveLength(1)
    expect(filtrarUnidades(lista, 'rio')).toHaveLength(1)
  })

  it('termo vazio devolve tudo', () => {
    expect(filtrarUnidades(lista, '  ')).toHaveLength(2)
  })

  it('normalizar tira acento', () => {
    expect(normalizar('Piçarras / SC')).toBe('picarras / sc')
  })
})

describe('enquadrar', () => {
  it('enquadra pelo bbox, não pela média das coordenadas', () => {
    // A média jogava o centro num ponto sem nenhuma unidade quando a rede é nacional.
    const v = enquadrar(
      { min_lat: -30, min_lng: -55, max_lat: -5, max_lng: -35 },
      { lat: null, lng: null },
    )
    expect(v.latitude).toBeCloseTo(-17.5)
    expect(v.longitude).toBeCloseTo(-45)
    expect(v.zoom).toBeGreaterThan(3)
    expect(v.zoom).toBeLessThan(6)
  })

  it('bbox degenerado (uma unidade só) não estoura o zoom', () => {
    const v = enquadrar(
      { min_lat: -23.5, min_lng: -46.6, max_lat: -23.5, max_lng: -46.6 },
      { lat: null, lng: null },
    )
    expect(Number.isFinite(v.zoom)).toBe(true)
    expect(v.zoom).toBeLessThanOrEqual(11)
  })

  it('sem bbox cai no Brasil inteiro', () => {
    expect(enquadrar(null, { lat: null, lng: null }).zoom).toBeLessThan(4)
  })

  const REDE_NACIONAL = { min_lat: -29, min_lng: -55, max_lat: 3, max_lng: -35 }

  it('card estreito afasta o zoom, senão as unidades das pontas ficam fora', () => {
    // O defeito real: com o mapa de volta ao lado da carteira, o card caiu para ~420x300
    // e a conta antiga — que embutia uma viewport de 512x512 — deixava Boa Vista e o
    // Nordeste fora do quadro.
    const largo = enquadrar(REDE_NACIONAL, { lat: null, lng: null }, { largura: 900, altura: 700 })
    const estreito = enquadrar(REDE_NACIONAL, { lat: null, lng: null }, { largura: 420, altura: 300 })
    expect(estreito.zoom).toBeLessThan(largo.zoom)
  })

  it('cabe nas DUAS dimensões: quem manda é a mais apertada', () => {
    // Card baixo e largo: é a ALTURA que corta. Ignorar isso era o erro da conta antiga,
    // que só olhava o span de longitude.
    const baixo = enquadrar(REDE_NACIONAL, { lat: null, lng: null }, { largura: 900, altura: 200 })
    const quadrado = enquadrar(REDE_NACIONAL, { lat: null, lng: null }, { largura: 900, altura: 900 })
    expect(baixo.zoom).toBeLessThan(quadrado.zoom)
  })

  it('a rede nacional inteira cabe no card estreito, com folga para a bolha', () => {
    const { zoom, latitude, longitude } = enquadrar(
      REDE_NACIONAL,
      { lat: null, lng: null },
      { largura: 420, altura: 300 },
    )
    // Graus de longitude que o card comporta neste zoom (512 px = 360 graus no zoom 0).
    const grausNaLargura = (420 / (512 * 2 ** zoom)) * 360
    expect(grausNaLargura).toBeGreaterThan(REDE_NACIONAL.max_lng - REDE_NACIONAL.min_lng)
    expect(latitude).toBeCloseTo(-13)
    expect(longitude).toBeCloseTo(-45)
  })

  it('viewport absurda (0x0, antes do primeiro layout) não zera o zoom', () => {
    const v = enquadrar(REDE_NACIONAL, { lat: null, lng: null }, { largura: 0, altura: 0 })
    expect(v.zoom).toBeGreaterThanOrEqual(2)
    expect(Number.isFinite(v.zoom)).toBe(true)
  })
})

describe('auxiliares', () => {
  it('rotula a competência em pt-BR', () => {
    expect(rotuloMesCompetencia('2026-06')).toBe('Jun/2026')
  })

  it('monta a query omitindo o que está vazio', () => {
    expect(queryDaCarteira({ mes: '2026-07', uf: '', consultor: undefined })).toBe('?mes=2026-07')
    expect(queryDaCarteira({})).toBe('')
  })
})
