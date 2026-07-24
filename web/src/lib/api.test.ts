import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from './api'
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
