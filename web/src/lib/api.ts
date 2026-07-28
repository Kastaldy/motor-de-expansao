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
/**
 * Downloads pesados (PDF, XLSX). O PDF baixa tiles de basemap (7 mapas — a camada
 * "entorno" saiu no BLK-RELPON-14) e em area
 * densa/cache frio passa de 1 min; a planilha monta 60 meses de formulas.
 */
const TIMEOUT_ARQUIVO = 360_000

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

/** Mensagens de erro de um download binário. Default = as do PDF (era o único). */
interface TextosDownload {
  falha?: string
  timeout?: string
  rede?: string
}

/**
 * Download binário (PDF, XLSX) com timeout, nome do arquivo do servidor e mensagens
 * de erro faláveis. Era `pedirPdf`; virou genérico quando entrou o simulador em Excel
 * — o corpo é idêntico, só os textos mudam.
 */
async function pedirArquivo(
  url: string,
  init: RequestInit,
  nomeSugerido: string,
  textos: TextosDownload = {},
): Promise<{ blob: Blob; filename: string }> {
  const ctrl = new AbortController()
  const t = setTimeout(() => ctrl.abort(), TIMEOUT_ARQUIVO)
  try {
    const r = await fetch(url, { ...init, signal: ctrl.signal })
    if (!r.ok) {
      let detalhe = `${textos.falha ?? 'Falha ao gerar o PDF'} (${r.status})`
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
        textos.timeout ??
          'O relatório demorou demais. Mapas de rua em área densa levam alguns minutos.',
        408,
      )
    }
    throw new ApiError(textos.rede ?? 'Não foi possível gerar o relatório.', 0)
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
    pedirArquivo(
      '/api/relatorio/municipal',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ uf, municipio, solicitante }),
      },
      `relatorio_municipal_${municipio}.pdf`,
    ),

  /**
   * Relatorio Pontual em PDF.
   *
   * NAO manda o payload de viabilidade de volta ao servidor: ele so precisa dos
   * INPUTS (`viabilidadeInputs`) e recalcula o payload inteiro por conta propria,
   * numa unica rodada do motor.
   *
   * Mandar o payload custava um HTTP 431 (Request Header Fields Too Large): a query
   * string carregava o objeto completo e, quando o payload passou a trazer a serie
   * mensal unica (64 linhas) e a grade (30 linhas), ele saltou de ~1 KB para
   * 70 KB URL-encoded, contra o limite de ~16 KB de request line + headers do h11.
   * Fora isso, reenviar um payload que o servidor acabou de calcular — para servir
   * de fallback caso o calculo do servidor falhe — e justamente o padrao de duas
   * fontes de verdade que o FIN-VIAB-01 existe para eliminar.
   */
  relatorioPontual: (opts: {
    lat: number
    lng: number
    rotulo?: string
    solicitante?: string
    infoImovel?: Record<string, unknown>
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
    if (opts.viabilidadeInputs) {
      q.set('viabilidade_inputs_json', JSON.stringify(opts.viabilidadeInputs))
    }

    const fd = new FormData()
    for (const f of (opts.fotos ?? []).slice(0, 2)) fd.append('fotos', f)

    return pedirArquivo(
      `/api/relatorio/pontual?${q.toString()}`,
      { method: 'POST', body: fd },
      'relatorio_pontual.pdf',
    )
  },

  /**
   * Simulador financeiro completo em XLSX, com FÓRMULAS VIVAS (DRE, folha de
   * pagamento, fluxo de caixa dos 60 meses).
   *
   * Manda os MESMOS inputs do /api/viabilidade: o servidor roda o motor uma vez e
   * monta a planilha. `rotulo` vai na query só para nomear o arquivo — o nome final
   * chega no `Content-Disposition`.
   */
  simuladorXlsx: (inputs: ViabilidadeIn, rotulo?: string) => {
    const q = rotulo ? `?rotulo=${encodeURIComponent(rotulo)}` : ''
    return pedirArquivo(
      `/api/simulador/xlsx${q}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(inputs),
      },
      'simulador_viabilidade.xlsx',
      {
        falha: 'Falha ao gerar a planilha',
        timeout: 'A planilha demorou demais e o pedido foi cancelado. Tente de novo.',
        rede: 'Não foi possível gerar a planilha.',
      },
    )
  },
}
