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
 * `api.hexagonos` — a chamada do ranking NACIONAL do Modo 3.
 *
 * O que estes testes protegem: a rota entrega o Brasil inteiro quando NENHUM filtro é
 * passado. Mandar `uf=` ou `municipio=` vazios na query faria o servidor receber
 * strings vazias e — dependendo de como o filtro fosse escrito lá — recortar a lista
 * para nada. O contrato é: filtro ausente não vai na URL.
 */
describe('hexagonos — o ranking nacional', () => {
  function capturarGet(): { url: () => string } {
    let capturada = ''
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        capturada = url
        return {
          ok: true,
          json: async () => ({ reguas: {}, cobertura: {}, itens: [] }),
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
    await api.hexagonos({ uf: '', municipio: '', porMunicipio: false })
    expect(cap.url()).toBe('/api/hexagonos')
  })

  it('leva só os filtros realmente preenchidos', async () => {
    const cap = capturarGet()
    await api.hexagonos({ uf: 'GO', limite: 25 })
    const query = new URLSearchParams(cap.url().split('?')[1] ?? '')
    expect(query.get('uf')).toBe('GO')
    expect(query.get('limite')).toBe('25')
    expect(query.has('municipio')).toBe(false)
    expect(query.has('por_municipio')).toBe(false)
  })

  it('escapa o nome do município em vez de quebrar a URL', async () => {
    const cap = capturarGet()
    await api.hexagonos({ municipio: 'Santa Bárbara d’Oeste', porMunicipio: true })
    const query = new URLSearchParams(cap.url().split('?')[1] ?? '')
    expect(query.get('municipio')).toBe('Santa Bárbara d’Oeste')
    expect(query.get('por_municipio')).toBe('true')
  })
})
