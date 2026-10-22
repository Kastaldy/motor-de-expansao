import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, baixar, VIDA_DA_BLOB_URL_MS } from './api'
import type { ViabilidadeIn } from './types'

/**
 * Regressão do HTTP 431 (Request Header Fields Too Large) no Relatório Pontual.
 *
 * A rota é `POST` mas os parâmetros vão na QUERY STRING (o corpo é multipart, por
 * causa das fotos). O front mandava o payload de viabilidade INTEIRO nessa query.
 * Enquanto o payload era uma lista achatada de KPIs (~1 KB) funcionava; quando o
 * FIN-VIAB-01 fez o payload carregar a série mensal única (64 linhas) e a grade de
 * sensibilidade (30 linhas), ele saltou para ~70 KB URL-encoded — contra o limite
 * de ~16 KB de request line + headers do h11/uvicorn. Resultado: 431 e nenhum PDF.
 *
 * O servidor nunca precisou do payload: ele recebe os INPUTS e roda o motor uma vez.
 */

const INPUTS: ViabilidadeIn = {
  lat: -23.31,
  lng: -51.16,
  m2: 1050,
  aluguel: 30000,
  demanda: 2304,
  ticket: 147,
  rampa_meses: 8,
  obra: 600000,
  parcelas_obra: 4,
  equipamentos: 1400000,
  prazo_equipamentos: 60,
  juros_equipamentos_am: 0.018,
  // Franquia parcelada 4x sem juros (default do motor; explicito aqui p/ espelhar
  // o caso golden). So timing de caixa — nao muda EBITDA/margem/break-even.
  parcelas_franquia: 4,
} as ViabilidadeIn

/** Limite conservador: metade do orçamento de ~16 KB do h11. */
const ORCAMENTO_QUERY_BYTES = 8_192

function capturarUrl(): { url: () => string } {
  let capturada = ''
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      capturada = url
      return {
        ok: true,
        headers: { get: () => 'attachment; filename="rel.pdf"' },
        blob: async () => new Blob([new Uint8Array([37, 80, 68, 70])]),
      } as unknown as Response
    }),
  )
  return { url: () => capturada }
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('relatorioPontual — orçamento da query string', () => {
  it('não manda o payload calculado de volta ao servidor', async () => {
    const cap = capturarUrl()
    await api.relatorioPontual({
      lat: -23.31,
      lng: -51.16,
      rotulo: 'Boulevard Londrina',
      viabilidadeInputs: INPUTS,
    })
    // A chave que causava o 431 não pode reaparecer: o servidor recalcula o payload.
    expect(cap.url()).not.toContain('viabilidade_json')
    expect(cap.url()).toContain('viabilidade_inputs_json')
  })

  it('mantém a query bem abaixo do limite do h11, mesmo com rótulo e imóvel longos', async () => {
    const cap = capturarUrl()
    await api.relatorioPontual({
      lat: -23.31,
      lng: -51.16,
      rotulo: 'Boulevard Shopping Londrina - loja âncora do piso L2',
      solicitante: 'Felipe Silva - Estratégia e Growth',
      infoImovel: {
        nome: 'Boulevard Shopping Londrina',
        observacoes: 'Observação longa do operador. '.repeat(20),
        metragem: 1050,
        aluguel: 30000,
        pe_direito: 4.2,
        vagas: 120,
        tipo: 'shopping',
      },
      viabilidadeInputs: INPUTS,
    })
    const query = cap.url().split('?')[1] ?? ''
    expect(query.length).toBeLessThan(ORCAMENTO_QUERY_BYTES)
  })

  it('as fotos vão no corpo multipart, não na query', async () => {
    const cap = capturarUrl()
    const foto = new File([new Uint8Array(4096)], 'fachada.jpg', { type: 'image/jpeg' })
    await api.relatorioPontual({
      lat: -23.31,
      lng: -51.16,
      viabilidadeInputs: INPUTS,
      fotos: [foto],
    })
    expect(cap.url()).not.toContain('fachada')
    expect((cap.url().split('?')[1] ?? '').length).toBeLessThan(ORCAMENTO_QUERY_BYTES)
  })
})

describe('relatorioPontual — modo Estudo (só demográfico)', () => {
  it('soEstudo escreve so_estudo=true e NÃO manda viabilidade nem dados do imóvel', async () => {
    const cap = capturarUrl()
    await api.relatorioPontual({
      lat: -23.48,
      lng: -46.61,
      rotulo: 'Santana',
      soEstudo: true,
      viabilidadeInputs: INPUTS,
      infoImovel: { aluguel: 30000, metragem: 1200 },
    })
    const q = new URLSearchParams(cap.url().split('?')[1] ?? '')
    expect(q.get('so_estudo')).toBe('true')
    expect(q.has('viabilidade_inputs_json')).toBe(false)
    expect(q.has('info_imovel')).toBe(false)
    expect(q.get('rotulo')).toBe('Santana')
  })

  it('sem soEstudo o pedido segue idêntico ao de antes (sem so_estudo na query)', async () => {
    const cap = capturarUrl()
    await api.relatorioPontual({ lat: -23.48, lng: -46.61, viabilidadeInputs: INPUTS })
    const q = new URLSearchParams(cap.url().split('?')[1] ?? '')
    expect(q.has('so_estudo')).toBe(false)
    expect(q.has('viabilidade_inputs_json')).toBe(true)
  })
})

/**
 * Regressão do 404 no celular do Miguel (06/08/2026).
 *
 * O PDF gerava (`POST /api/relatorio/pontual` -> 200) e a tela virava
 * `{"detail":"Not Found"}`. O log do servidor mostrou o que o browser pediu logo
 * depois: `GET /03470ca0-da3b-4ee0-9f41-c1d32ff00d97` — o caminho de uma blob URL,
 * navegado como se fosse URL do site.
 *
 * A causa: `click()`, `remove()` e `revokeObjectURL()` todos SÍNCRONOS. No desktop o
 * download sai durante o `click()`; no celular ele é adiado e encontra o blob já
 * revogado e a âncora já fora do DOM.
 *
 * O teste trava a ordem, que é o que importa: depois do clique, o blob continua vivo.
 */
describe('baixar', () => {
  function palcoFalso() {
    const ancora: Record<string, unknown> = { click: vi.fn(), remove: vi.fn() }
    const doc = {
      createElement: () => ancora,
      body: { appendChild: vi.fn() },
    }
    const criadas: string[] = []
    const revogadas: string[] = []
    const globais = globalThis as unknown as Record<string, unknown>
    const antes = { document: globais.document, URL: globais.URL }
    globais.document = doc
    globais.URL = {
      createObjectURL: () => {
        const u = `blob:https://piloto.ultra-expansao.tech/uuid-${criadas.length}`
        criadas.push(u)
        return u
      },
      revokeObjectURL: (u: string) => revogadas.push(u),
    }
    return {
      ancora,
      criadas,
      revogadas,
      restaurar: () => {
        globais.document = antes.document
        globais.URL = antes.URL
      },
    }
  }

  it('NÃO revoga a blob URL no mesmo tick do clique — era o defeito do celular', () => {
    vi.useFakeTimers()
    const palco = palcoFalso()
    try {
      baixar(new Blob(['%PDF-1.4']), 'relatorio_pontual.pdf')
      expect(palco.ancora.click).toHaveBeenCalled()
      // O ponto do teste: aqui o browser do celular ainda nem começou a baixar.
      expect(palco.revogadas).toEqual([])
      expect(palco.ancora.remove).not.toHaveBeenCalled()
    } finally {
      palco.restaurar()
      vi.useRealTimers()
    }
  })

  it('revoga depois da janela, para não segurar o arquivo na memória para sempre', () => {
    vi.useFakeTimers()
    const palco = palcoFalso()
    try {
      baixar(new Blob(['%PDF-1.4']), 'relatorio_pontual.pdf')
      vi.advanceTimersByTime(VIDA_DA_BLOB_URL_MS + 1)
      expect(palco.revogadas).toEqual(palco.criadas)
      expect(palco.ancora.remove).toHaveBeenCalled()
    } finally {
      palco.restaurar()
      vi.useRealTimers()
    }
  })

  it('o nome do arquivo vai no atributo download, senão o browser navega', () => {
    vi.useFakeTimers()
    const palco = palcoFalso()
    try {
      baixar(new Blob(['%PDF-1.4']), 'ficha_berrini-sp.pdf')
      expect(palco.ancora.download).toBe('ficha_berrini-sp.pdf')
      expect(String(palco.ancora.href)).toContain('blob:')
    } finally {
      palco.restaurar()
      vi.useRealTimers()
    }
  })
})

/**
 * `api.hexagonos` — o Top 10 do recorte (recomendação única, DEC-077).
 *
 * O que estes testes protegem: a rota entrega o Brasil inteiro quando NENHUM filtro é
 * passado. Mandar `uf=` ou `municipio=` vazios na query faria o servidor receber
 * strings vazias e — dependendo de como o filtro fosse escrito lá — recortar a lista
 * para nada. O contrato é: filtro ausente não vai na URL. E `limite`/`por_municipio`
 * NUNCA vão: o Top 10 tem tamanho fixo pela régua, e "um por cidade" contradiria a regra
 * (vizinhos podem ocupar várias vagas).
 */
describe('hexagonos — o Top 10 do recorte', () => {
  function capturarGet(): { url: () => string } {
    let capturada = ''
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        capturada = url
        return {
          ok: true,
          json: async () => ({ recomendacao: {}, cobertura: {} }),
        } as unknown as Response
      }),
    )
    return { url: () => capturada }
  }

  it('sem filtro nenhum, pede o Brasil inteiro — sem query de recorte', async () => {
    const cap = capturarGet()
    await api.hexagonos()
    expect(cap.url()).toBe('/api/hexagonos')
  })

  it('filtro vazio NÃO vira parâmetro vazio na URL', async () => {
    const cap = capturarGet()
    await api.hexagonos({ uf: '', municipio: '' })
    expect(cap.url()).toBe('/api/hexagonos')
  })

  it('com só a UF, leva só a UF', async () => {
    const cap = capturarGet()
    await api.hexagonos({ uf: 'GO' })
    const query = new URLSearchParams(cap.url().split('?')[1] ?? '')
    expect(query.get('uf')).toBe('GO')
    expect(query.has('municipio')).toBe(false)
    expect([...query.keys()]).toEqual(['uf'])
  })

  it('UF + município, com o nome escapado em vez de quebrar a URL', async () => {
    const cap = capturarGet()
    await api.hexagonos({ uf: 'SP', municipio: 'Santa Bárbara d’Oeste' })
    const query = new URLSearchParams(cap.url().split('?')[1] ?? '')
    expect(query.get('uf')).toBe('SP')
    expect(query.get('municipio')).toBe('Santa Bárbara d’Oeste')
    expect([...query.keys()]).toEqual(['uf', 'municipio'])
  })

  it('nunca manda `limite` nem `por_municipio`, nem se um chamador antigo os passar', async () => {
    const cap = capturarGet()
    await api.hexagonos({ uf: 'GO', limite: 25, porMunicipio: true } as never)
    const query = new URLSearchParams(cap.url().split('?')[1] ?? '')
    expect(query.has('limite')).toBe(false)
    expect(query.has('por_municipio')).toBe(false)
    expect(query.get('uf')).toBe('GO')
  })
})

describe('pontoGeometria — a área desenhada vai no CORPO', () => {
  it('POST com o polígono no corpo JSON, e nada dele na URL', async () => {
    let url = ''
    let init: RequestInit | undefined
    vi.stubGlobal(
      'fetch',
      vi.fn(async (u: string, i?: RequestInit) => {
        url = u
        init = i
        return { ok: true, json: async () => ({}) } as unknown as Response
      }),
    )
    // 50 vértices: em query string isto passaria do orçamento da URL.
    const anel: [number, number][] = Array.from({ length: 50 }, (_, k) => [
      -46.63 + 0.01 * Math.cos((2 * Math.PI * k) / 50),
      -23.55 + 0.01 * Math.sin((2 * Math.PI * k) / 50),
    ])
    anel.push(anel[0])
    await api.pontoGeometria({ type: 'Polygon', coordinates: [anel] })
    expect(url).toBe('/api/ponto/geometria')
    expect(init?.method).toBe('POST')
    const corpo = JSON.parse(String(init?.body))
    expect(corpo.geometria.type).toBe('Polygon')
    expect(corpo.geometria.coordinates[0]).toHaveLength(51)
  })
})

/* ---------------- Alcance do ponto e Estudo do recorte (DEC-074) ---------------- */
describe('pontoAlcance — a rota de alcance', () => {
  it('GET /api/ponto/alcance com lat, lng e o alcance cru', async () => {
    let url = ''
    vi.stubGlobal(
      'fetch',
      vi.fn(async (u: string) => {
        url = u
        return { ok: true, json: async () => ({}) } as unknown as Response
      }),
    )
    await api.pontoAlcance(-23.48, -46.61, 'carro_10min')
    const [rota, query] = url.split('?')
    expect(rota).toBe('/api/ponto/alcance')
    const q = new URLSearchParams(query)
    expect(q.get('lat')).toBe('-23.48')
    expect(q.get('lng')).toBe('-46.61')
    expect(q.get('alcance')).toBe('carro_10min')
  })

  it('o estudo da unidade Ultra vai na query do alcance; sem ele, a query é a de antes', async () => {
    const urls: string[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (u: string) => {
        urls.push(u)
        return { ok: true, json: async () => ({}) } as unknown as Response
      }),
    )
    await api.pontoAlcance(-23.48, -46.61, 'raio_2km', { excluirUltraProxima: true })
    await api.pontoAlcance(-23.48, -46.61, 'raio_2km')
    const [com, sem] = urls.map((u) => new URLSearchParams(u.split('?')[1]))
    expect(com.get('excluir_ultra_proxima')).toBe('true')
    expect(com.get('alcance')).toBe('raio_2km')
    expect(sem.has('excluir_ultra_proxima')).toBe(false)
    expect([...sem.keys()]).toEqual(['lat', 'lng', 'alcance'])
  })

  it('503 do serviço de rotas vira a mensagem do servidor, nunca um raio de 1 km calado', async () => {
    const msg = 'O cálculo de tempo de deslocamento está indisponível agora. Tente de novo em instantes ou use o raio.'
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({ ok: false, status: 503, json: async () => ({ detail: msg }) }) as unknown as Response),
    )
    await expect(api.pontoAlcance(-23.48, -46.61, 'carro_10min')).rejects.toMatchObject({ status: 503, message: msg })
  })
})

describe('relatorioPontual — o recorte do Estudo vai no CORPO', () => {
  function capturarTudo(): { url: () => string; corpo: () => FormData } {
    let url = ''
    let corpo = new FormData()
    vi.stubGlobal(
      'fetch',
      vi.fn(async (u: string, i?: RequestInit) => {
        url = u
        corpo = i?.body as FormData
        return {
          ok: true,
          headers: { get: () => 'attachment; filename="rel.pdf"' },
          blob: async () => new Blob([new Uint8Array([37, 80, 68, 70])]),
        } as unknown as Response
      }),
    )
    return { url: () => url, corpo: () => corpo }
  }

  it('alcance no FormData, nada dele na query', async () => {
    const cap = capturarTudo()
    await api.relatorioPontual({ lat: -23.48, lng: -46.61, soEstudo: true, alcance: 'raio_2km' })
    expect(cap.corpo().get('alcance')).toBe('raio_2km')
    expect(cap.url()).not.toContain('alcance')
  })

  it('área desenhada: o Polygon (50 vértices) no corpo, e a URL segue curta', async () => {
    const cap = capturarTudo()
    const anel: [number, number][] = Array.from({ length: 50 }, (_, k) => [
      -46.63 + 0.01 * Math.cos((2 * Math.PI * k) / 50),
      -23.55 + 0.01 * Math.sin((2 * Math.PI * k) / 50),
    ])
    anel.push(anel[0])
    await api.relatorioPontual({
      lat: -23.55,
      lng: -46.63,
      soEstudo: true,
      geometria: { type: 'Polygon', coordinates: [anel] },
    })
    const g = JSON.parse(String(cap.corpo().get('geometria')))
    expect(g.type).toBe('Polygon')
    expect(g.coordinates[0]).toHaveLength(51)
    expect(cap.url()).not.toContain('geometria')
    expect((cap.url().split('?')[1] ?? '').length).toBeLessThan(ORCAMENTO_QUERY_BYTES)
  })

  it('raio de 1 km (ou sem recorte): nenhum campo novo — o pedido de antes, byte a byte', async () => {
    const cap = capturarTudo()
    await api.relatorioPontual({ lat: -23.48, lng: -46.61, soEstudo: true, alcance: 'raio_1km' })
    expect(cap.corpo().has('alcance')).toBe(false)
    expect(cap.corpo().has('geometria')).toBe(false)
  })

  it('fora do modo Estudo o recorte não vai: o relatório completo é do raio de 1 km', async () => {
    const cap = capturarTudo()
    await api.relatorioPontual({ lat: -23.48, lng: -46.61, alcance: 'carro_10min' })
    expect(cap.corpo().has('alcance')).toBe(false)
  })
})
