import { describe, expect, it } from 'vitest'

import {
  CAPACIDADE_UNIDADE_ALUNOS,
  MOTIVO_SEM_MERCADO_PADRAO,
  VISTA_BRASIL,
  ZOOM_PONTO,
  faixaDoResidual,
  motivoSemHexagonos,
  vistaDoPonto,
  vizinhosDesenhaveis,
} from './mapa-ponto'
import type { PontoPayload, PontoVizinho } from './types'

/** Ficha com a forma real do `/api/ponto`, no minimo que estas regras leem. */
function ficha(over: {
  vizinhos?: PontoVizinho[]
  mercadoDisponivel?: boolean
  mercadoMotivo?: string | null
} = {}): PontoPayload {
  return {
    lat: -23.5613,
    lng: -46.6565,
    raio_km: 1,
    hex_id: '87a8100c5ffffff',
    local: { uf: 'SP', municipio: 'São Paulo', bairro: 'Bela Vista', unidade_tipo: 'bairro' },
    censo: {
      disponivel: true,
      motivo: null,
      populacao: 24_310,
      domicilios: 12_004,
      renda_per_capita: 7_412,
      renda_media_domiciliar: 14_120,
      densidade_hab_km2: 12_880,
      score_socioeconomico: 88.4,
      n_setores: 41,
      detalhe: null,
    },
    concorrencia: {
      disponivel: true,
      motivo: null,
      n_concorrentes: 9,
      n_ultra: 0,
      lista: [],
    },
    mercado: {
      disponivel: over.mercadoDisponivel ?? true,
      motivo: over.mercadoMotivo ?? null,
      sam: 4_820,
      residual: 0,
      score_residual: 0,
    },
    vizinhos: over.vizinhos ?? [{ hex_id: '87a8100c5ffffff', residual: 0, score_censo: 88.4 }],
    reguas: null,
    criterios: [],
  }
}

describe('faixaDoResidual', () => {
  it('converte alunos para a rampa de 0-100 usando a capacidade de uma unidade', () => {
    // Metade de uma unidade = meio da rampa. E' o que amarra a cor ao score.
    expect(faixaDoResidual(CAPACIDADE_UNIDADE_ALUNOS / 2)).toBe(50)
    expect(faixaDoResidual(0)).toBe(0)
  })

  it('satura em 100 acima de uma unidade inteira', () => {
    expect(faixaDoResidual(CAPACIDADE_UNIDADE_ALUNOS)).toBe(100)
    // 7.557 alunos: o vizinho da Av. Paulista que revelou por que o mapa precisa existir.
    expect(faixaDoResidual(7_557)).toBe(100)
  })

  it('trava em 0 quando o residual vem negativo, em vez de sair da rampa', () => {
    // Oferta instalada maior que o mercado potencial. E' o hexagono MAIS saturado —
    // tem de pintar como tal, nao com cor indefinida.
    expect(faixaDoResidual(-1_200)).toBe(0)
  })

  it('devolve null sem dado, para o mapa nao pintar zero inventado', () => {
    expect(faixaDoResidual(null)).toBeNull()
    expect(faixaDoResidual(undefined)).toBeNull()
    expect(faixaDoResidual(Number.NaN)).toBeNull()
  })
})

describe('vizinhosDesenhaveis', () => {
  it('descarta vizinho sem celula H3, que nao tem o que pintar', () => {
    const lista = vizinhosDesenhaveis([
      { hex_id: '87a8100c5ffffff', residual: 10, score_censo: null },
      { hex_id: null, residual: 999, score_censo: null },
      { hex_id: '', residual: 999, score_censo: null },
    ])
    expect(lista.map((v) => v.hex_id)).toEqual(['87a8100c5ffffff'])
  })

  it('aguenta lista ausente sem estourar', () => {
    expect(vizinhosDesenhaveis(null)).toEqual([])
    expect(vizinhosDesenhaveis(undefined)).toEqual([])
    expect(vizinhosDesenhaveis([])).toEqual([])
  })
})

describe('vistaDoPonto', () => {
  it('centra na coordenada colada e usa o zoom de entorno', () => {
    // lng vira longitude e lat vira latitude — a troca aqui e' o erro classico.
    expect(vistaDoPonto(-23.5613, -46.6565)).toEqual({
      longitude: -46.6565,
      latitude: -23.5613,
      zoom: ZOOM_PONTO,
    })
  })

  it('parte do Brasil inteiro enquanto nao ha ponto', () => {
    expect(VISTA_BRASIL.zoom).toBeLessThan(ZOOM_PONTO)
    expect(VISTA_BRASIL.latitude).toBeLessThan(0)
    expect(VISTA_BRASIL.longitude).toBeLessThan(0)
  })
})

describe('motivoSemHexagonos', () => {
  it('nao declara nada quando ha hexagono para colorir', () => {
    expect(motivoSemHexagonos(ficha())).toBeNull()
  })

  it('nao declara nada sem ficha: a tela ainda esta pedindo o ponto', () => {
    expect(motivoSemHexagonos(null)).toBeNull()
    expect(motivoSemHexagonos(undefined)).toBeNull()
  })

  it('prefere o motivo do SERVIDOR quando a camada de mercado faltou', () => {
    const semMercado = ficha({
      vizinhos: [],
      mercadoDisponivel: false,
      mercadoMotivo: 'Camada de mercado ausente para esta UF.',
    })
    expect(motivoSemHexagonos(semMercado)).toBe('Camada de mercado ausente para esta UF.')
  })

  it('cai na frase padrao quando o servidor nao mandou motivo', () => {
    expect(motivoSemHexagonos(ficha({ vizinhos: [] }))).toBe(MOTIVO_SEM_MERCADO_PADRAO)
    expect(motivoSemHexagonos(ficha({ vizinhos: [], mercadoMotivo: '   ' }))).toBe(
      MOTIVO_SEM_MERCADO_PADRAO,
    )
  })

  it('declara tambem quando ha vizinhos, mas nenhum com celula H3', () => {
    // Sumir em silencio aqui seria o pior caso: a lista nao esta vazia, mas o mapa
    // continuaria so' com o basemap e o operador leria como falha de rede.
    const semCelula = ficha({ vizinhos: [{ hex_id: null, residual: 500, score_censo: null }] })
    expect(motivoSemHexagonos(semCelula)).toBe(MOTIVO_SEM_MERCADO_PADRAO)
  })
})
