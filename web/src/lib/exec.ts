/**
 * Lógica pura da Visão Executiva — extraída da tela SÓ para ser testável sem DOM.
 *
 * O projeto não tem `@testing-library/react`, e o precedente da casa (`lib/select-filter.ts`,
 * extraído de `Select.tsx`) é este: o que dá para testar sem montar componente sai do
 * componente. Nada aqui toca React.
 */

import type { RedeMetrica, RedeSeveridade, RedeUnidade } from './types'
import { brl, brlCurto, num, pct } from './format'

/** Cor de cada nível do semáforo. Uma definição só, usada na tabela, no mapa e nos chips. */
export const COR_SEVERIDADE: Record<RedeSeveridade, string> = {
  alta: '#ff5a6e',
  media: '#e0b25a',
  ok: '#3cc878',
  sem_base: '#7c8798',
}

export const ORDEM_SEVERIDADE: RedeSeveridade[] = ['alta', 'media', 'ok', 'sem_base']

/**
 * Formata uma métrica pela sua natureza.
 *
 * O pega-ratão que isto blinda: **churn e conversão chegam em PERCENTUAL** desta API
 * (5,93 = 5,93%), enquanto na Viabilidade as taxas chegam em FRAÇÃO (0,0593). Um `pctFrac`
 * aqui mostraria "0,1%" de churn e ninguém desconfiaria.
 */
export function formatarMetrica(valor: number | null | undefined, formato: string): string {
  if (valor === null || valor === undefined || Number.isNaN(valor)) return '—'
  switch (formato) {
    case 'brl':
      return brl(valor, false, valor < 1000 ? 2 : 0)
    case 'brl_curto':
      return brlCurto(valor)
    case 'pct':
      return pct(valor, 1)
    case 'nota':
      return num(valor, 0)
    default:
      return num(valor, 0)
  }
}

/** `12` -> `"12º de 86"`; sem posição, texto honesto em vez de um traço mudo. */
export function rotuloRanking(metrica: RedeMetrica | undefined): string {
  if (!metrica?.rank || !metrica.rank_total) return 'sem posição (unidade nova)'
  return `${metrica.rank}º de ${metrica.rank_total}`
}

/** `-64,2` -> `"64,2% abaixo da média da rede"`. */
export function rotuloVsMedia(metrica: RedeMetrica | undefined): string {
  const v = metrica?.vs_media_pct
  if (v === null || v === undefined) return 'sem comparação com a rede'
  if (Math.abs(v) < 0.05) return 'na média da rede'
  return `${pct(Math.abs(v), 1)} ${v > 0 ? 'acima' : 'abaixo'} da média da rede`
}

/** Título de acessibilidade da célula: o quarteto inteiro em texto. */
export function tituloDaCelula(rotulo: string, metrica: RedeMetrica | undefined, formato: string): string {
  if (!metrica) return rotulo
  return [
    `${rotulo}: ${formatarMetrica(metrica.atual, formato)}`,
    `M-1: ${formatarMetrica(metrica.m1, formato)}`,
    rotuloRanking(metrica),
    rotuloVsMedia(metrica),
  ].join(' · ')
}

export interface LeituraDelta {
  /** variação a exibir, já em módulo */
  valor: number
  /** 'pct' = variação relativa; 'pontos' = diferença absoluta (churn, NPS) */
  modo: 'pct' | 'pontos'
  subiu: boolean
  /** true quando a variação é boa PARA ESTA MÉTRICA (churn subindo é ruim) */
  bom: boolean
  /** abaixo do limiar de ruído: mostra travessão, não seta */
  estavel: boolean
}

const RUIDO = 0.05

/**
 * Lê a variação de uma métrica com a direção CERTA.
 *
 * Dois defeitos do dashboard que o time usa hoje, que isto impede de herdar:
 * 1. churn subindo 40% aparecia com seta verde — o delta usava a mesma direção para
 *    todas as métricas;
 * 2. churn e NPS variavam em "%" relativo, o que confunde: NPS de 2 para 4 vira "+100%".
 *    Aqui essas duas variam em PONTOS.
 */
export function lerDelta(
  metrica: RedeMetrica | undefined,
  bomSubindo: boolean,
  emPontos = false,
): LeituraDelta | null {
  if (!metrica) return null
  if (emPontos) {
    if (metrica.atual === null || metrica.m1 === null) return null
    const d = metrica.atual - metrica.m1
    return {
      valor: Math.abs(d),
      modo: 'pontos',
      subiu: d > 0,
      bom: d > 0 === bomSubindo,
      estavel: Math.abs(d) < RUIDO,
    }
  }
  const d = metrica.delta_pct
  if (d === null || d === undefined) return null
  return {
    valor: Math.abs(d),
    modo: 'pct',
    subiu: d > 0,
    bom: d > 0 === bomSubindo,
    estavel: Math.abs(d) < RUIDO,
  }
}

/** Métricas cuja variação se lê em PONTOS, não em percentual do percentual. */
export const METRICAS_EM_PONTOS = new Set(['churn_pct', 'nps', 'conversao_pct', 'pct_agregador_alunos'])

/**
 * Ordena a carteira no cliente. Nulos SEMPRE por último, **nas duas direções**.
 *
 * O `?? -Infinity` da v1 só funcionava em `desc`: em `asc`, quem não tinha o número subia
 * para o topo da lista de trabalho — o pior lugar possível para um dado ausente.
 */
export function ordenarUnidades(
  unidades: RedeUnidade[],
  chave: string,
  direcao: 'asc' | 'desc',
): RedeUnidade[] {
  const sinal = direcao === 'asc' ? 1 : -1
  const valorDe = (u: RedeUnidade): number | null => {
    if (chave === 'prioridade') return u.prioridade
    if (chave === 'nome') return null
    return u.metricas[chave]?.atual ?? null
  }
  return [...unidades].sort((a, b) => {
    if (chave === 'nome') return sinal * a.nome.localeCompare(b.nome, 'pt-BR')
    const va = valorDe(a)
    const vb = valorDe(b)
    if (va === null && vb === null) return a.nome.localeCompare(b.nome, 'pt-BR')
    if (va === null) return 1
    if (vb === null) return -1
    if (va === vb) return a.nome.localeCompare(b.nome, 'pt-BR')
    return sinal * (va - vb)
  })
}

/**
 * Busca local por nome/cidade/consultor, sem acento e sem caixa.
 *
 * Existe além do filtro do servidor porque digitar não pode custar um round-trip: o
 * payload inteiro já está no cliente.
 */
export function filtrarUnidades(unidades: RedeUnidade[], termo: string): RedeUnidade[] {
  const alvo = normalizar(termo)
  if (!alvo) return unidades
  return unidades.filter((u) =>
    [u.nome, u.cidade, u.consultor, u.uf, u.master_franquia]
      .filter(Boolean)
      .some((campo) => normalizar(String(campo)).includes(alvo)),
  )
}

export function normalizar(texto: string): string {
  return texto
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
    .toLowerCase()
    .trim()
}

const MESES_PT = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']

/** `"2026-06"` -> `"Jun/2026"`. */
export function rotuloMesCompetencia(m: string): string {
  const [ano, mes] = m.split('-')
  const nome = MESES_PT[Number(mes) - 1] ?? mes
  return `${nome.charAt(0).toUpperCase()}${nome.slice(1)}/${ano}`
}

/** `"2026-06"` -> `"jun"` (eixo de gráfico, onde o ano é redundante). */
export function rotuloMesCurto(m: string): string {
  const [, mes] = m.split('-')
  return MESES_PT[Number(mes) - 1] ?? mes
}

/** Lado do tile do basemap: a escala de zoom do MapLibre/deck.gl é definida sobre ele. */
const LADO_DO_TILE = 512
/* Fração do card que o bbox ocupa. O respiro não é estética: o bbox enquadra o CENTRO
   das unidades, e a bolha tem até 40 px de raio — com pouca folga, a unidade da ponta
   aparece cortada pela borda do card. */
const RESPIRO = 0.8

/** Latitude -> fração da altura do mundo em Mercator (0 no topo, 1 embaixo). */
function fracaoMercator(lat: number): number {
  const rad = (Math.max(-85, Math.min(85, lat)) * Math.PI) / 180
  return (1 - Math.log(Math.tan(rad) + 1 / Math.cos(rad)) / Math.PI) / 2
}

/**
 * Enquadramento do mapa a partir do bbox das unidades.
 *
 * A média das coordenadas (o que a v1 fazia) cai no meio do nada quando a rede é
 * nacional: com unidades de SC ao RN, o "centro" fica num ponto sem nenhuma unidade e o
 * zoom fixo corta metade do país.
 *
 * O `viewport` não é refinamento: sem ele, a conta embute a suposição de um card de
 * 512x512. Num card estreito — que é o do mapa desde que ele voltou para o lado da
 * carteira — a mesma conta devolve zoom alto demais e as unidades das pontas ficam
 * FORA do quadro. Como as duas dimensões cortam, o zoom é o menor dos dois: o que faz
 * a largura caber e o que faz a altura caber. A altura passa pela projeção de Mercator,
 * senão o Brasil (que vai de +5 a -33 graus) sai apertado.
 */
export function enquadrar(
  bbox: { min_lat: number; min_lng: number; max_lat: number; max_lng: number } | null,
  centro: { lat: number | null; lng: number | null },
  viewport?: { largura: number; altura: number },
): { latitude: number; longitude: number; zoom: number } {
  if (!bbox) {
    return { latitude: centro.lat ?? -15.78, longitude: centro.lng ?? -47.93, zoom: 3.4 }
  }
  const largura = viewport && viewport.largura > 40 ? viewport.largura : LADO_DO_TILE
  const altura = viewport && viewport.altura > 40 ? viewport.altura : LADO_DO_TILE
  const latitude = (bbox.min_lat + bbox.max_lat) / 2
  const longitude = (bbox.min_lng + bbox.max_lng) / 2
  // Piso em 1e-4 para o bbox degenerado (uma unidade só) não virar divisão por zero.
  const fracaoLng = Math.max((bbox.max_lng - bbox.min_lng) / 360, 1e-4)
  const fracaoLat = Math.max(
    Math.abs(fracaoMercator(bbox.min_lat) - fracaoMercator(bbox.max_lat)),
    1e-4,
  )
  const zoom = Math.min(
    Math.log2((largura * RESPIRO) / (LADO_DO_TILE * fracaoLng)),
    Math.log2((altura * RESPIRO) / (LADO_DO_TILE * fracaoLat)),
  )
  return { latitude, longitude, zoom: Math.min(11, Math.max(2, zoom)) }
}

/**
 * O mapa deve voltar ao enquadramento automático?
 *
 * Duas coisas disparam o reenquadramento e elas NÃO valem o mesmo:
 *
 * - `recorte` — mudou o conjunto de unidades (outro filtro, outra competência). Reenquadra
 *   sempre, mesmo por cima do ajuste manual: o pan antigo aponta para unidades que não
 *   estão mais na tela.
 * - `tamanho` — mudou só a caixa do mapa (janela redimensionada, trilho refluído). Aqui o
 *   ajuste manual PREVALECE. Sem essa distinção, digitar na busca desfazia o zoom da
 *   pessoa: a busca filtra só na tela, não muda o bbox, mas encolhe a tabela — e o trilho
 *   acompanha a altura da carteira.
 */
export function deveReenquadrar(motivo: 'recorte' | 'tamanho', mexeu: boolean): boolean {
  return motivo === 'recorte' || !mexeu
}

/** Query string da carteira, omitindo o que está vazio. */
export function queryDaCarteira(filtros: Record<string, string | undefined>): string {
  const q = new URLSearchParams()
  for (const [chave, valor] of Object.entries(filtros)) {
    if (valor) q.set(chave, valor)
  }
  const texto = q.toString()
  return texto ? `?${texto}` : ''
}
