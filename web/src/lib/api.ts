/** Cliente do backend do piloto. Tudo passa pelo proxy /api do Vite. */

import type {
  ExecutivaPayload,
  FaixaAlunos,
  MunicipioItem,
  MunicipioPayload,
  ViabilidadeIn,
  ViabilidadeOut,
} from './types'

/** A primeira leitura de uma UF carrega a particao inteira — pode passar de 15 s. */
const TIMEOUT_LEITURA = 90_000
/** O PDF baixa tiles de basemap (8 mapas); em area densa/cache frio passa de 1 min. */
const TIMEOUT_PDF = 360_000

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function pedir<T>(
  url: string,
  init: RequestInit = {},
  timeout = TIMEOUT_LEITURA,
): Promise<T> {
  const ctrl = new AbortController()
  const t = setTimeout(() => ctrl.abort(), timeout)
  try {
    const r = await fetch(url, { ...init, signal: ctrl.signal })
    if (!r.ok) {
      let detalhe = `${r.status}`
      try {
        const j = await r.json()
        detalhe = j.detail ?? detalhe
      } catch {
        /* resposta sem corpo JSON — fica o status */
      }
      throw new ApiError(String(detalhe), r.status)
    }
    return (await r.json()) as T
  } catch (e) {
    if (e instanceof ApiError) throw e
    if (e instanceof DOMException && e.name === 'AbortError') {
      throw new ApiError('A leitura demorou demais e foi cancelada.', 408)
    }
    throw new ApiError(
      'Não foi possível falar com o servidor. Ele está rodando na porta 8899?',
      0,
    )
  } finally {
    clearTimeout(t)
  }
}

async function pedirPdf(
  url: string,
  init: RequestInit,
  nomeSugerido: string,
): Promise<{ blob: Blob; filename: string }> {
  const ctrl = new AbortController()
  const t = setTimeout(() => ctrl.abort(), TIMEOUT_PDF)
  try {
    const r = await fetch(url, { ...init, signal: ctrl.signal })
    if (!r.ok) {
      let detalhe = `Falha ao gerar o PDF (${r.status})`
      try {
        const j = await r.json()
        detalhe = j.detail ?? detalhe
      } catch {
        /* ignora */
      }
      throw new ApiError(String(detalhe), r.status)
    }
    // O header vem como `attachment; filename="..."`; se faltar, usa o sugerido.
    const cd = r.headers.get('Content-Disposition') ?? ''
    const m = /filename="?([^";]+)"?/.exec(cd)
    return { blob: await r.blob(), filename: m?.[1] ?? nomeSugerido }
  } catch (e) {
    if (e instanceof ApiError) throw e
    if (e instanceof DOMException && e.name === 'AbortError') {
      throw new ApiError(
        'O relatório demorou demais. Mapas de rua em área densa levam alguns minutos.',
        408,
      )
    }
    throw new ApiError('Não foi possível gerar o relatório.', 0)
  } finally {
    clearTimeout(t)
  }
}

/** Dispara o download no browser a partir do blob recebido. */
export function baixar(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export const api = {
  health: () => pedir<{ status: string; data_ok: boolean }>('/api/health', {}, 10_000),

  ufs: () => pedir<{ ufs: string[] }>('/api/ufs'),

  /** Visão de UF inteira: funil por UF + recomendação de municípios. */
  ufView: (uf: string) => pedir<MunicipioPayload>(`/api/uf/${encodeURIComponent(uf)}`),

  /** Visão Executiva: rede Ultra real agregada por estado (Growth API). `mes`
   *  opcional (YYYY-MM) escolhe a competência; sem ele, a mais recente. */
  executiva: (uf: string, mes?: string) =>
    pedir<ExecutivaPayload>(
      `/api/executiva/${encodeURIComponent(uf)}${mes ? `?mes=${encodeURIComponent(mes)}` : ''}`,
    ),

  /** Geocoding de endereço livre -> lat/lng (Nominatim, DEC-010). */
  geocode: (q: string) =>
    pedir<{ found: boolean; lat?: number; lng?: number; nome?: string }>(
      `/api/geocode?q=${encodeURIComponent(q)}`,
      {},
      15_000,
    ),

  municipios: (uf: string) =>
    pedir<{ uf: string; municipios: MunicipioItem[] }>(
      `/api/municipios/${encodeURIComponent(uf)}`,
    ),

  municipio: (uf: string, municipio: string) =>
    pedir<MunicipioPayload>(
      `/api/municipio/${encodeURIComponent(uf)}/${encodeURIComponent(municipio)}`,
    ),

  faixaAlunos: (m2: number, formato?: string) => {
    const q = new URLSearchParams({ m2: String(m2) })
    if (formato) q.set('formato', formato)
    return pedir<FaixaAlunos>(`/api/faixa-alunos?${q.toString()}`, {}, 30_000)
  },

  viabilidade: (body: ViabilidadeIn) =>
    pedir<ViabilidadeOut>('/api/viabilidade', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  relatorioMunicipal: (uf: string, municipio: string, solicitante?: string) =>
    pedirPdf(
      '/api/relatorio/municipal',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ uf, municipio, solicitante }),
      },
      `relatorio_municipal_${municipio}.pdf`,
    ),

  relatorioPontual: (opts: {
    lat: number
    lng: number
    rotulo?: string
    solicitante?: string
    infoImovel?: Record<string, unknown>
    viabilidade?: unknown
    viabilidadeInputs?: ViabilidadeIn
    fotos?: File[]
  }) => {
    const q = new URLSearchParams({
      lat: String(opts.lat),
      lng: String(opts.lng),
    })
    if (opts.rotulo) q.set('rotulo', opts.rotulo)
    if (opts.solicitante) q.set('solicitante', opts.solicitante)
    if (opts.infoImovel && Object.keys(opts.infoImovel).length) {
      q.set('info_imovel', JSON.stringify(opts.infoImovel))
    }
    if (opts.viabilidade) q.set('viabilidade_json', JSON.stringify(opts.viabilidade))
    if (opts.viabilidadeInputs) {
      q.set('viabilidade_inputs_json', JSON.stringify(opts.viabilidadeInputs))
    }

    const fd = new FormData()
    for (const f of (opts.fotos ?? []).slice(0, 2)) fd.append('fotos', f)

    return pedirPdf(
      `/api/relatorio/pontual?${q.toString()}`,
      { method: 'POST', body: fd },
      'relatorio_pontual.pdf',
    )
  },
}
