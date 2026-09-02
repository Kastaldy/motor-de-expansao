/** Cliente do backend do piloto. Tudo passa pelo proxy /api do Vite. */

import type {
  AcaoImobiliaria,
  AcessosFicha,
  AcessosResumo,
  AlvoEvento,
  ExecutivaPayload,
  FaixaAlunos,
  MePayload,
  MetodologiaPayload,
  MunicipioItem,
  OportunidadesPayload,
  Cobertura1k,
  EstadosPayload,
  HexagonosPayload,
  MunicipioPayload,
  PontoPayload,
  PontoResolvido,
  RedeCarteira,
  RedeFicha,
  RedeFiltros,
  RedeQuery,
  ViabilidadeIn,
  ViabilidadeOut,
} from './types'

/** Query string da rede, omitindo o que esta vazio. */
function queryRede(q: RedeQuery = {}): string {
  const p = new URLSearchParams()
  for (const [chave, valor] of Object.entries(q)) {
    if (valor) p.set(chave, String(valor))
  }
  const texto = p.toString()
  return texto ? `?${texto}` : ''
}

/** A primeira leitura de uma UF carrega a particao inteira — pode passar de 15 s. */
const TIMEOUT_LEITURA = 90_000
/**
 * Downloads pesados (PDF, XLSX). O PDF baixa tiles de basemap (7 mapas — a camada
 * "entorno" saiu no BLK-RELPON-14) e em area densa/cache frio passa de 1 min; a
 * planilha monta 60 meses de formulas.
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

/**
 * Quanto tempo a blob URL fica viva depois do clique.
 *
 * NAO e' folga arbitraria: e' o tempo que o browser do CELULAR leva para pegar o
 * arquivo. Ver `baixar`.
 */
export const VIDA_DA_BLOB_URL_MS = 60_000

/**
 * Dispara o download no browser a partir do blob recebido.
 *
 * **A ordem aqui é o conserto de um defeito de produção (06/08/2026).** O Miguel
 * gerou o Relatório Pontual pelo celular, o PDF ficou pronto — o `POST
 * /api/relatorio/pontual` respondeu 200 — e a tela virou um JSON `{"detail":"Not
 * Found"}`. No log do servidor:
 *
 *     15:52:51  POST /api/relatorio/pontual...  200 OK
 *     15:53:11  GET  /03470ca0-da3b-4ee0-9f41-c1d32ff00d97  404 Not Found
 *
 * Aquele UUID é o caminho de uma blob URL (`blob:https://host/<uuid>`): o browser
 * navegou para ela como se fosse URL comum do site.
 *
 * A causa era a versão anterior fazer `click()`, `remove()` e `revokeObjectURL()`
 * TUDO SÍNCRONO. No desktop o download é despachado durante o próprio `click()` e
 * revogar logo depois não custa nada. No celular ele é adiado: quando o browser vai
 * buscar o blob, ele já não existe — e a âncora que carregava o `download` também já
 * saiu do DOM. Sem blob e sem atributo, sobra uma navegação para um caminho que o
 * servidor não tem.
 *
 * Por isso a limpeza é agendada, não imediata. O custo é segurar o arquivo na memória
 * do browser por um minuto; o benefício é o download funcionar em celular, que é onde
 * o time de campo abre isto.
 */
export function baixar(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.rel = 'noopener'
  document.body.appendChild(a)
  a.click()
  // A âncora sai do DOM junto com a revogação: removê-la antes de o browser
  // processar o clique tira o `download` do caminho e vira navegação.
  setTimeout(() => {
    a.remove()
    URL.revokeObjectURL(url)
  }, VIDA_DA_BLOB_URL_MS)
}

/** Resolução única de `/api/me` por carga de página — ver o comentário em `api.me`. */
let _me: Promise<MePayload> | null = null

export const api = {
  health: () => pedir<{ status: string; data_ok: boolean }>('/api/health', {}, 10_000),

  /** Quem sou eu + que abas posso usar (controle temporário de acesso). A SPA
   *  esconde o que está fora da lista; o bloqueio real é do backend (middleware).
   *
   *  MEMOIZADA desde o Bloco A, quando passou a ter DOIS chamadores na abertura: o
   *  `main.tsx`, que resolve o perfil do país antes de montar a árvore, e o `useEffect`
   *  do `App.tsx`, que lê as abas. Sem a memo seriam duas requisições por carga — e
   *  `/api/me` é gravada na trilha de acesso (DEC-027), então a duplicata inflaria a
   *  contagem de ações que a aba Acessos publica. Falha NÃO é memoizada: o `catch`
   *  limpa, para um erro de rede na abertura não condenar a sessão inteira. */
  me: (): Promise<MePayload> =>
    (_me ??= pedir<MePayload>('/api/me', {}, 10_000).catch((e) => {
      _me = null
      throw e
    })),

  ufs: () => pedir<{ ufs: string[] }>('/api/ufs'),

  /** Oportunidades imobiliárias (camada de oferta, READ-ONLY, sem PII). Lê o
   *  viaveis.parquet do coletor já joinado ao M1; `uf` opcional filtra no servidor.
   *  `limite` sobe o teto de itens (default 500 no servidor, cap 3000 na rota) —
   *  o Mapa Territorial pede o teto para a camada de pins cobrir a UF inteira. */
  oportunidades: (uf?: string, limite?: number) => {
    const q = new URLSearchParams()
    if (uf) q.set('uf', uf)
    if (limite != null) q.set('limite', String(limite))
    const qs = q.toString()
    return pedir<OportunidadesPayload>(`/api/oportunidades${qs ? `?${qs}` : ''}`, {}, 30_000)
  },

  /** Dossiê PDF do coletor para um imóvel (quando existe; 404 = sem dossiê). */
  dossie: (id: string) =>
    pedirArquivo(
      `/api/oportunidades/${encodeURIComponent(id)}/dossie`,
      { method: 'GET' },
      `dossie_${id}.pdf`,
      { falha: 'Falha ao abrir o dossiê', rede: 'Não foi possível abrir o dossiê.' },
    ),

  /**
   * Rastro de um gesto da camada imobiliária na trilha de acesso (DEC-027).
   *
   * A tela é restrita (aba `imobiliaria`) e quase tudo que se faz nela é
   * client-side — abrir a ficha de um imóvel já carregado, marcar visita, trocar
   * o recorte não geram requisição nenhuma. Sem esta chamada a trilha só saberia
   * dizer "abriu a aba e baixou N dossiês". O corpo é vazio de propósito: quem
   * registra é o middleware do backend; aqui só importa a rota + a query.
   *
   * Não bloqueia a UI e NUNCA propaga erro: rastro não pode quebrar interação.
   * `keepalive` para o registro sobreviver a uma navegação logo em seguida.
   */
  eventoImobiliaria: (acao: AcaoImobiliaria, alvo: AlvoEvento = {}) => {
    const q = new URLSearchParams()
    for (const [chave, valor] of Object.entries(alvo)) {
      if (valor != null && String(valor).trim()) q.set(chave, String(valor))
    }
    const qs = q.toString()
    void fetch(`/api/imobiliaria/evento/${acao}${qs ? `?${qs}` : ''}`, {
      method: 'POST',
      keepalive: true,
    }).catch(() => {})
  },

  /** Manual do funil: o que cada camada mede e com que régua corta. Estático —
   *  não depende de UF nem de município, então a tela busca uma vez e guarda. */
  metodologia: () => pedir<MetodologiaPayload>('/api/metodologia', {}, 15_000),

  /* ---- Aba Acessos (emenda DEC-027; restrita por allowlist no backend) ---- */

  /** Painel de uso do piloto: agregados da trilha + série longa do rollup.
   *  Para quem está fora da allowlist o backend devolve 404 — a rota "não existe". */
  acessosResumo: (dias = 30) =>
    pedir<AcessosResumo>(`/api/acessos/resumo?dias=${dias}`, {}, 30_000),

  /** Ficha de um usuário: janelas por dia + contagem por feature (sem conteúdo). */
  acessosUsuario: (nome: string, dias = 30) =>
    pedir<AcessosFicha>(
      `/api/acessos/usuario/${encodeURIComponent(nome)}?dias=${dias}`,
      {},
      30_000,
    ),

  /**
   * Ranking NACIONAL por estado. Lê as 27 partições com projeção de 4 colunas
   * (~1,5 s na primeira vez, cacheado no servidor depois) — é a única rota que
   * compara UFs, e por isso tem timeout próprio.
   */
  estados: () => pedir<EstadosPayload>('/api/estados', {}, 120_000),

  /**
   * Ranking NACIONAL por HEXÁGONO — os melhores do Brasil, sem escolher estado.
   *
   * `uf`/`municipio` são filtros SOBRE a lista nacional, aplicados no servidor depois
   * da ordenação: nunca antes dela. Mesma varredura das 27 partições de `estados()`,
   * e por isso o mesmo timeout longo na primeira chamada.
   */
  hexagonos: (opts: { limite?: number; uf?: string; municipio?: string; porMunicipio?: boolean } = {}) => {
    const q = new URLSearchParams()
    if (opts.limite) q.set('limite', String(opts.limite))
    if (opts.uf) q.set('uf', opts.uf)
    if (opts.municipio) q.set('municipio', opts.municipio)
    if (opts.porMunicipio) q.set('por_municipio', 'true')
    const texto = q.toString()
    return pedir<HexagonosPayload>(`/api/hexagonos${texto ? `?${texto}` : ''}`, {}, 120_000)
  },

  /** Visão de UF inteira: funil por UF + recomendação de municípios. */
  ufView: (uf: string) => pedir<MunicipioPayload>(`/api/uf/${encodeURIComponent(uf)}`),

  /* ---- Modo de PONTO ---- */

  /**
   * Ficha de um ponto. NÃO carrega a partição da UF — lê só a partição do município
   * e um punhado de hexes, então cabe no timeout curto em vez dos 90 s da leitura de
   * UF. É o que torna viável o fluxo "cole o link, veja a ficha".
   */
  ponto: (lat: number, lng: number) =>
    pedir<PontoPayload>(`/api/ponto?lat=${lat}&lng=${lng}`, {}, 30_000),

  /**
   * Texto colado -> coordenada. Só é chamada quando o front NÃO resolveu sozinho
   * (`lib/entrada-ponto`): link curto do celular, link de place sem coordenada, ou
   * endereço escrito. Pode fazer requisição externa (expandir redirect + geocode),
   * daí o timeout próprio.
   */
  resolverPonto: (q: string) =>
    pedir<PontoResolvido>(`/api/resolver-ponto?q=${encodeURIComponent(q)}`, {}, 25_000),

  /** PROTOTIPO — geometria do raio de 1 km, SOB DEMANDA. Fora do payload do mapa de
   *  proposito: custa ~2,4 s e ~3,9 MB na UF de SP, e so' quem liga a chave deve pagar. */
  cobertura: (uf: string, municipio?: string) =>
    pedir<Cobertura1k>(
      `/api/cobertura/${encodeURIComponent(uf)}` +
        (municipio ? `?municipio=${encodeURIComponent(municipio)}` : ''),
    ),

  /** Visão Executiva: rede Ultra real agregada por estado (Growth API). `mes`
   *  opcional (YYYY-MM) escolhe a competência; sem ele, a mais recente. */
  executiva: (uf: string, mes?: string) =>
    pedir<ExecutivaPayload>(
      `/api/executiva/${encodeURIComponent(uf)}${mes ? `?mes=${encodeURIComponent(mes)}` : ''}`,
    ),

  /* ---- Visão Executiva 2.0: a rede como carteira acionável (DEC-023) ---- */

  /** Vocabulário dos filtros, RÉGUAS vigentes e contadores de qualidade.
   *  As réguas vêm do servidor de propósito: a tela nunca as repete. */
  redeFiltros: (mes?: string) =>
    pedir<RedeFiltros>(`/api/rede/filtros${mes ? `?mes=${encodeURIComponent(mes)}` : ''}`),

  /** Nível 1 — a carteira da rede inteira, priorizada. Sem filtro = Brasil todo. */
  redeCarteira: (q: RedeQuery = {}) => pedir<RedeCarteira>(`/api/rede/carteira${queryRede(q)}`),

  /** Nível 2 — a ficha de uma unidade (série de 12 meses, funil, coorte, recomendações). */
  redeUnidade: (id: string, mes?: string) =>
    pedir<RedeFicha>(
      `/api/rede/unidade/${encodeURIComponent(id)}${mes ? `?mes=${encodeURIComponent(mes)}` : ''}`,
    ),

  /** Atribuição de consultor / master franqueado. Única escrita do piloto.
   *  `versao` faz a concorrência otimista: 409 = outra pessoa gravou antes. */
  redeCadastroAtribuir: (id: string, versao: number, campos: Record<string, string>) =>
    pedir<{ unidade_id: string; versao: number; valores: Record<string, string> }>(
      `/api/rede/cadastro/${encodeURIComponent(id)}`,
      {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ versao, campos }),
      },
      30_000,
    ),

  /** Exports da carteira. `formato` decide a extensão da rota. */
  redeCarteiraArquivo: (formato: 'csv' | 'xlsx' | 'pdf', q: RedeQuery = {}) =>
    pedirArquivo(
      `/api/rede/carteira.${formato}${queryRede(q)}`,
      { method: 'GET' },
      `carteira_rede_ultra.${formato}`,
      {
        falha: 'Falha ao gerar o arquivo da carteira',
        timeout: 'A geração demorou demais e o pedido foi cancelado. Tente de novo.',
        rede: 'Não foi possível gerar o arquivo da carteira.',
      },
    ),

  /** Ficha da unidade em PDF. */
  redeUnidadePdf: (id: string, mes?: string) =>
    pedirArquivo(
      `/api/rede/unidade/${encodeURIComponent(id)}.pdf${mes ? `?mes=${encodeURIComponent(mes)}` : ''}`,
      { method: 'GET' },
      `ficha_${id}.pdf`,
      {
        falha: 'Falha ao gerar a ficha em PDF',
        timeout: 'A geração demorou demais e o pedido foi cancelado.',
        rede: 'Não foi possível gerar a ficha em PDF.',
      },
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

  /** Registra na trilha (DEC-027) o OK do aviso de confidencialidade. Corpo vazio:
   *  o registro É a linha que o middleware grava para a chamada. */
  cienciaConfidencialidade: () =>
    pedir<{ ok: boolean }>('/api/ciencia-confidencialidade', { method: 'POST' }),

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
    /**
     * Marca que a coordenada é o CENTROIDE do hexágono, não um endereço exato — o
     * gerador imprime o aviso na capa e na Realização do PDF. Parâmetro PRÓPRIO de
     * propósito: `rotulo` é texto livre do operador e não pode carregar convenção
     * nenhuma (endereço com parênteses seria mutilado). Omitido = sem aviso.
     */
    origemCentroideHex?: boolean
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
    if (opts.origemCentroideHex) q.set('origem_centroide_hex', 'true')
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
