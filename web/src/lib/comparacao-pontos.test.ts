import { describe, expect, it } from 'vitest'

import {
  CORES_PONTO,
  chaveDaCoordenada,
  DIMENSOES_PONTO,
  MAX_PONTOS,
  corDoPonto,
  compararPontos,
  ehAreaDesenhada,
  indiceDaMesmaArea,
  indiceDoMesmoPonto,
  motivoSemPdfDeComparacao,
  passaNoEstudo,
  rotuloDoRecorte,
  resumoDoEstudo,
  rotuloDoPonto,
  pinsDaComparacao,
  rotulosDosPontos,
  rotulosPartidosDosPontos,
  subtituloDoDeckDePontos,
} from './comparacao-pontos'
import { corDeIdentidadeRgb, rotulosUnicos } from './comparacao'
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

describe('corDoPonto', () => {
  it('dá cores distintas a todos os pontos que cabem na tela', () => {
    const cores = Array.from({ length: MAX_PONTOS }, (_, i) => corDoPonto(i))
    expect(new Set(cores).size).toBe(MAX_PONTOS)
  })

  it('cicla em vez de devolver indefinido acima do teto', () => {
    expect(corDoPonto(CORES_PONTO.length)).toBe(corDoPonto(0))
    expect(corDoPonto(-1)).toBe(CORES_PONTO[CORES_PONTO.length - 1])
  })

  it('não usa o vermelho da rampa — cor de ponto não é veredito', () => {
    expect(CORES_PONTO).not.toContain('#B92323')
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
    expect(r).toEqual(['São Paulo #1', 'São Paulo #2', 'São Paulo #3'])
  })

  it('numera SÓ quem empata, preservando o nome de quem é único', () => {
    const r = rotulosDosPontos([
      ponto({ bairro: null }),
      ponto({ bairro: 'Bela Vista' }),
      ponto({ bairro: null }),
    ])
    expect(r).toEqual(['São Paulo #1', 'Bela Vista', 'São Paulo #2'])
  })

  it('o número é o ordinal DENTRO do grupo de mesmo nome', () => {
    const r = rotulosDosPontos([
      ponto({ bairro: 'Centro' }),
      ponto({ bairro: 'X' }),
      ponto({ bairro: 'Centro' }),
      ponto({ bairro: 'X' }),
    ])
    expect(r).toEqual(['Centro #1', 'X #1', 'Centro #2', 'X #2'])
  })

  it('fallback de coordenada: sem bairro nem município, o nome é a coordenada', () => {
    const r = rotulosDosPontos([
      ponto({ bairro: null, municipio: null, lat: -16.6869, lng: -49.2648 }),
      ponto({ bairro: null, municipio: null, lat: -16.6869, lng: -49.2648 }),
      ponto({ bairro: null, municipio: null, lat: -15.7939, lng: -47.8828 }),
    ])
    expect(r).toEqual(['-16.6869, -49.2648 #1', '-16.6869, -49.2648 #2', '-15.7939, -47.8828'])
  })

  it('delega para rotulosUnicos — as duas comparações não divergem', () => {
    const ps = [ponto({ bairro: null }), ponto({ bairro: 'Bela Vista' }), ponto({ bairro: null })]
    expect(rotulosDosPontos(ps)).toEqual(rotulosUnicos(ps.map(rotuloDoPonto)))
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

describe('rotulosPartidosDosPontos', () => {
  it('parte o rótulo em nome + "#k" (o sufixo fica fora do ellipsis)', () => {
    expect(
      rotulosPartidosDosPontos([ponto({ bairro: 'Centro' }), ponto({ bairro: 'Centro' }), ponto()]),
    ).toEqual([
      { base: 'Centro', sufixo: '#1' },
      { base: 'Centro', sufixo: '#2' },
      { base: 'Bela Vista', sufixo: null },
    ])
  })
})

describe('pinsDaComparacao', () => {
  it('um pin por item, cada um na cor de identidade do SEU índice', () => {
    const fichas = [
      ponto({ bairro: 'A', lat: -23.5, lng: -46.6 }),
      ponto({ bairro: 'B', lat: -23.6, lng: -46.7 }),
      ponto({ bairro: 'C', lat: -23.7, lng: -46.8 }),
    ]
    const pins = pinsDaComparacao(fichas, 1, ['A', 'B', 'C'])
    expect(pins).toHaveLength(3)
    pins.forEach((p, i) => {
      expect(p.indice).toBe(i)
      expect(p.rgb).toEqual(corDeIdentidadeRgb(i))
      expect(p.lat).toBe(fichas[i].lat)
      expect(p.lng).toBe(fichas[i].lng)
      expect(p.hexId).toBe('87a8100c5ffffff')
      expect(p.geometria).toBeNull()
    })
    expect(pins.map((p) => p.rotulo)).toEqual(['A', 'B', 'C'])
    expect(pins.map((p) => p.ativo)).toEqual([false, true, false])
  })

  it('nenhuma aba aberta: nenhum pin ativo', () => {
    const pins = pinsDaComparacao([ponto(), ponto({ lat: -23 })], null, ['X #1', 'X #2'])
    expect(pins.every((p) => !p.ativo)).toBe(true)
  })

  it('rótulo faltando cai na coordenada, nunca em pin sem nome', () => {
    const pins = pinsDaComparacao([{ lat: -16.68691, lng: -49.26482 }], 0, [])
    expect(pins[0].rotulo).toBe('-16.6869, -49.2648')
    expect(pins[0].hexId).toBeNull()
  })

  it('aceita item de GEOMETRIA: pin no representative_point, contorno preservado', () => {
    const anel: [number, number][] = [
      [-46.6, -23.5],
      [-46.59, -23.5],
      [-46.59, -23.49],
      [-46.6, -23.5],
    ]
    const pins = pinsDaComparacao(
      [ponto({ bairro: 'A' }), { lat: -23.497, lng: -46.594, hex_id: null, geometria: [anel] }],
      1,
      ['A', 'Área desenhada'],
    )
    expect(pins[1]).toMatchObject({
      lat: -23.497,
      lng: -46.594,
      indice: 1,
      rotulo: 'Área desenhada',
      ativo: true,
      hexId: null,
    })
    expect(pins[1].geometria).toEqual([anel])
    expect(pins[1].rgb).toEqual(corDeIdentidadeRgb(1))
  })

  it('lista vazia devolve lista vazia', () => {
    expect(pinsDaComparacao([], null, [])).toEqual([])
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
    expect(c.frase).toContain('menos população que')
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

describe('chaveDaCoordenada', () => {
  /* O defeito de 2026-08-14: a tela guardava "onde o mapa já está" pelo `hex_id`, e um
     hexágono res-7 tem ~5 km2. Medido contra a API, estes dois endereços de Cotia distam
     1,2 km e caem no MESMO hexágono (87a81006bffffff) — com a guarda por hexágono, o
     segundo entrava na lista e trocava a janela, mas o mapa ficava no primeiro. */
  const A = { lat: -23.61369, lng: -46.84487 }
  const B = { lat: -23.60569, lng: -46.83687 }

  it('separa dois endereços que dividem o mesmo hexágono', () => {
    expect(chaveDaCoordenada(A.lat, A.lng)).not.toBe(chaveDaCoordenada(B.lat, B.lng))
  })

  it('a MESMA coordenada continua sendo o mesmo ponto', () => {
    expect(chaveDaCoordenada(A.lat, A.lng)).toBe(chaveDaCoordenada(A.lat, A.lng))
  })

  it('absorve ruído abaixo de ~1 m, que é a razão de existir o arredondamento', () => {
    // O mesmo endereço volta do servidor com o último dígito diferente conforme o caminho
    // (colado, link curto, geocodificado). 30 cm é o mesmo imóvel num raio de 1.000 m.
    expect(chaveDaCoordenada(-23.613690_4, -46.844870_2)).toBe(chaveDaCoordenada(A.lat, A.lng))
  })

  it('é a MESMA noção que `indiceDoMesmoPonto` usa — uma regra, não duas', () => {
    const ponto = (lat: number, lng: number) => ({ lat, lng }) as never
    expect(indiceDoMesmoPonto([ponto(A.lat, A.lng)], B.lat, B.lng)).toBe(-1)
    expect(indiceDoMesmoPonto([ponto(A.lat, A.lng)], A.lat, A.lng)).toBe(0)
  })
})

describe('MAX_PONTOS', () => {
  it('teto de 5 desde 2026-08-13 (pedido do Juan)', () => {
    // Eram 4 porque a comparacao era a tabela de DUAS colunas e o operador escolhia
    // pares. Com os blocos por parametro todos os pontos entram no mesmo bloco, a escolha
    // de par sumiu, e com ela o motivo do teto antigo.
    expect(MAX_PONTOS).toBe(5)
  })

  it('nao passa do tamanho da paleta de identidade', () => {
    // A sexta cor repetiria e duas abas ficariam iguais. Este invariante NAO existia: a
    // paleta ja' dizia no comentario "cinco porque MAX_PONTOS e' 5" enquanto a constante
    // valia 4, e nada travava a divergencia.
    expect(MAX_PONTOS).toBeLessThanOrEqual(CORES_PONTO.length)
  })
})

describe('resumoDoEstudo — a leitura ABSOLUTA, ao lado da relativa', () => {
  const comCriterios = (passas: (boolean | null)[]) =>
    ({
      criterios: passas.map((passa, i) => ({
        chave: `c${i}`,
        rotulo: `Critério ${i}`,
        valor: 1,
        regua: 1,
        unidade: '',
        maior_melhor: true,
        passa,
      })),
    }) as unknown as PontoPayload

  it('conta cumpridos sobre AVALIADOS', () => {
    expect(resumoDoEstudo(comCriterios([true, true, false, true, false]))).toEqual({
      cumpridos: 3,
      avaliados: 5,
    })
  })

  it('sem dado sai dos DOIS lados da fracao, nunca vira reprovacao', () => {
    // Tres criterios, um sem dado: a leitura e' 2 de 2, e nao 2 de 3.
    expect(resumoDoEstudo(comCriterios([true, true, null]))).toEqual({
      cumpridos: 2,
      avaliados: 2,
    })
  })

  it('sem criterio avaliado devolve null — nao ha o que afirmar', () => {
    expect(resumoDoEstudo(comCriterios([null, null]))).toBeNull()
    expect(resumoDoEstudo(comCriterios([]))).toBeNull()
  })

  it('concorda com o portao `passaNoEstudo`', () => {
    expect(passaNoEstudo(comCriterios([true, true, true]))).toBe(true)
    expect(passaNoEstudo(comCriterios([true, false, true]))).toBe(false)
    expect(passaNoEstudo(comCriterios([null]))).toBeNull()
  })
})

describe('subtituloDoDeckDePontos', () => {
  /* A capa afirmava a cidade do PRIMEIRO ponto. No deck de 10/09/2026 os quatro pontos
     eram dois de Posse/GO e dois de Jatai/GO, e a peca inteira saiu "Posse - 4 pontos".
     E' a mesma regra que o deck de HEXAGONOS ja' aplica no MapScreen: a cidade so' entra
     quando ela vale para TODOS. */
  it('nao nomeia cidade nenhuma quando os pontos misturam municipios', () => {
    const fichas = [
      ponto({ municipio: 'Posse' }),
      ponto({ municipio: 'Posse' }),
      ponto({ municipio: 'Jataí' }),
      ponto({ municipio: 'Jataí' }),
    ]
    expect(subtituloDoDeckDePontos(fichas)).toBe('4 pontos')
  })

  it('nomeia a cidade quando TODOS os pontos sao dela', () => {
    expect(subtituloDoDeckDePontos([ponto({ municipio: 'Posse' }), ponto({ municipio: 'Posse' })]))
      .toBe('Posse - 2 pontos')
  })

  it('ponto sem municipio resolvido nao deixa a cidade dos outros afirmar pelo conjunto', () => {
    // Ausencia nao e' concordancia: nao se sabe de onde o ponto e', entao a capa se cala.
    expect(subtituloDoDeckDePontos([ponto({ municipio: 'Posse' }), ponto({ municipio: null })]))
      .toBe('2 pontos')
  })

  it('um ponto so, e a lista vazia, seguem legiveis', () => {
    expect(subtituloDoDeckDePontos([ponto({ municipio: 'Posse' })])).toBe('Posse - 1 pontos')
    expect(subtituloDoDeckDePontos([])).toBe('0 pontos')
  })
})

/* ---------------- Área desenhada (DEC-071) ---------------- */
describe('área desenhada na comparação', () => {
  const anel: [number, number][][] = [[[-46.63, -23.55], [-46.62, -23.55], [-46.62, -23.54], [-46.63, -23.55]]]
  const area = {
    lat: -23.546, lng: -46.624, raio_km: null, hex_id: 'x',
    local: { uf: 'SP', municipio: 'São Paulo', bairro: 'Santana', unidade_tipo: null },
    geometria: anel,
    recorte: { tipo: 'poligono', area_km2: 2.4, n_vertices: 3, metodo: 'x' },
    mercado: { disponivel: true, sam: 1, residual: 1, score_residual: 1, grao: 'geometria', area_km2: 2.4 },
  } as unknown as PontoPayload
  const ponto = {
    lat: -23.546, lng: -46.624, raio_km: 1, hex_id: 'x',
    local: { uf: 'SP', municipio: 'São Paulo', bairro: 'Santana', unidade_tipo: null },
    mercado: { disponivel: true, sam: 1, residual: 1, score_residual: 1 },
  } as unknown as PontoPayload

  it('chama-se "Área desenhada", e não pelo bairro do ponto interno', () => {
    expect(rotuloDoPonto(area)).toBe('Área desenhada')
    expect(rotulosDosPontos([area, area])).toEqual(['Área desenhada #1', 'Área desenhada #2'])
  })

  it('o recorte em texto: área com km², ponto com metros', () => {
    expect(rotuloDoRecorte(area)).toBe('área desenhada de 2,40 km²')
    expect(rotuloDoRecorte(ponto)).toBe('raio de 1.000 m')
  })

  it('buscar a coordenada do ponto interno NÃO abre a área', () => {
    expect(indiceDoMesmoPonto([area], area.lat, area.lng)).toBe(-1)
    expect(indiceDoMesmoPonto([area, ponto], ponto.lat, ponto.lng)).toBe(1)
  })

  it('o PDF de comparação recusa lista com área, dizendo por quê', () => {
    expect(motivoSemPdfDeComparacao([ponto, ponto])).toBeNull()
    expect(motivoSemPdfDeComparacao([ponto, area])).toMatch(/próxima fase/)
  })

  it('a mesma área casa pelos vértices; o ponto nunca casa como área', () => {
    expect(indiceDaMesmaArea([ponto, area], anel)).toBe(1)
    expect(indiceDaMesmaArea([ponto], anel)).toBe(-1)
    expect(ehAreaDesenhada(area)).toBe(true)
    expect(ehAreaDesenhada(ponto)).toBe(false)
  })
})
