/**
 * "Analisar geometria" — o desenho do polígono à mão no mapa (DEC-070, fase 1).
 *
 * O operador liga a ferramenta no trilho do mapa e clica os vértices. O polígono FECHA de
 * duas formas: clicando de novo perto do 1º vértice (por PIXELS de tela, como a trava da
 * régua) ou no botão "Concluir". Ao fechar, a área vira um item da comparação — a mesma
 * ficha do ponto, com o polígono no lugar do raio de 1,0 km.
 *
 * SEM LIB DE DESENHO, por decisão do dono: o desenho é o molde da régua — o clique do
 * `DeckGL` acrescenta um vértice, e as camadas de linha/polígono desenham o provisório. O
 * que precisa de regra (fechar, desfazer, área, autointerseção, limites) mora AQUI, puro,
 * para o vitest testar sem montar mapa.
 *
 * OS LIMITES SÃO OS DO SERVIDOR (`dashboard/geometria_desenhada.py`): 0,1 a 25 km², até 50
 * vértices, sem autointerseção. A tela avalia antes para o "Concluir" travar com o motivo
 * escrito em vez de deixar o operador esperar um 400; quem DECIDE continua sendo o
 * servidor (a área daqui é uma projeção local equirretangular — na borda dos limites as
 * duas contas podem discordar no último décimo, e aí vale a mensagem do servidor).
 */

import { distanciaMetros, type Coord } from './medicao'
import type { PosicaoGeoJson } from './comparacao-pontos'

export const AREA_MIN_KM2 = 0.1
export const AREA_MAX_KM2 = 25
export const MAX_VERTICES = 50
export const MIN_VERTICES = 3

/**
 * Raio, em PIXELS de tela, em que um clique perto do 1º vértice FECHA o polígono.
 *
 * Em pixels pelo mesmo motivo da trava da régua: em metros a mesma folga seria mínima no
 * zoom de cidade e enorme no de rua. Menor que a trava da régua (28 px) de propósito — ali
 * errar a trava custa refazer um clique; aqui, fechar sem querer encerra o desenho.
 */
export const TOLERANCIA_FECHAR_PX = 12

const RAIO_TERRA_M = 6_371_008.8
const rad = (g: number) => (g * Math.PI) / 180

/** Vértices projetados em METROS num plano local (equirretangular na latitude média). */
function projetar(vs: readonly Coord[]): { x: number; y: number }[] {
  if (!vs.length) return []
  const lat0 = vs.reduce((s, v) => s + v.lat, 0) / vs.length
  const lng0 = vs.reduce((s, v) => s + v.lng, 0) / vs.length
  const k = Math.cos(rad(lat0))
  return vs.map((v) => ({
    x: rad(v.lng - lng0) * RAIO_TERRA_M * k,
    y: rad(v.lat - lat0) * RAIO_TERRA_M,
  }))
}

/** Área do polígono fechado pelos vértices, em km² (fórmula do laço, em valor absoluto). */
export function areaKm2(vs: readonly Coord[]): number {
  if (vs.length < 3) return 0
  const p = projetar(vs)
  let s = 0
  for (let i = 0; i < p.length; i++) {
    const a = p[i]
    const b = p[(i + 1) % p.length]
    s += a.x * b.y - b.x * a.y
  }
  return Math.abs(s) / 2 / 1e6
}

type XY = { x: number; y: number }

function orientacao(a: XY, b: XY, c: XY): number {
  const v = (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)
  return Math.abs(v) < 1e-9 ? 0 : v > 0 ? 1 : -1
}

function noSegmento(a: XY, b: XY, c: XY): boolean {
  return (
    Math.min(a.x, b.x) - 1e-9 <= c.x && c.x <= Math.max(a.x, b.x) + 1e-9 &&
    Math.min(a.y, b.y) - 1e-9 <= c.y && c.y <= Math.max(a.y, b.y) + 1e-9
  )
}

/** Os segmentos AB e CD se tocam (cruzam, encostam ou se sobrepõem)? */
export function segmentosSeCruzam(a: XY, b: XY, c: XY, d: XY): boolean {
  const o1 = orientacao(a, b, c)
  const o2 = orientacao(a, b, d)
  const o3 = orientacao(c, d, a)
  const o4 = orientacao(c, d, b)
  if (o1 !== o2 && o3 !== o4) return true
  if (o1 === 0 && noSegmento(a, b, c)) return true
  if (o2 === 0 && noSegmento(a, b, d)) return true
  if (o3 === 0 && noSegmento(c, d, a)) return true
  if (o4 === 0 && noSegmento(c, d, b)) return true
  return false
}

/**
 * O polígono FECHADO pelos vértices cruza a si mesmo?
 *
 * Compara toda aresta com toda aresta NÃO vizinha (as vizinhas sempre se tocam no vértice
 * comum, e isso não é cruzamento). Com até 50 vértices são ~1.200 pares — nada.
 */
export function temAutointersecao(vs: readonly Coord[]): boolean {
  const n = vs.length
  if (n < 4) return false
  const p = projetar(vs)
  for (let i = 0; i < n; i++) {
    const a = p[i]
    const b = p[(i + 1) % n]
    for (let j = i + 1; j < n; j++) {
      // Vizinhas: j = i+1, e a última com a primeira (i = 0, j = n-1).
      if (j === i + 1 || (i === 0 && j === n - 1)) continue
      if (segmentosSeCruzam(a, b, p[j], p[(j + 1) % n])) return true
    }
  }
  return false
}

/** O que um clique no mapa faz com o desenho em andamento. */
export type AcaoDoClique =
  /** Caiu perto do 1º vértice com pelo menos 3 marcados: fecha o polígono. */
  | { tipo: 'fechar' }
  /** Vértice novo. */
  | { tipo: 'adicionar' }
  /** Já são `MAX_VERTICES`: não cabe outro (a tela diz isso em vez de engolir o clique). */
  | { tipo: 'cheio' }

/**
 * Decide o clique ANTES de mexer no desenho. `metrosPorPixel` vem da câmera (`medicao`);
 * sem ele (câmera ainda sem zoom) o clique nunca fecha — só acrescenta.
 */
export function interpretarClique(
  vs: readonly Coord[],
  clique: Coord,
  metrosPorPixel: number,
  toleranciaPx: number = TOLERANCIA_FECHAR_PX,
): AcaoDoClique {
  if (vs.length >= MIN_VERTICES && Number.isFinite(metrosPorPixel) && metrosPorPixel > 0) {
    if (distanciaMetros(vs[0], clique) <= toleranciaPx * metrosPorPixel) return { tipo: 'fechar' }
  }
  if (vs.length >= MAX_VERTICES) return { tipo: 'cheio' }
  return { tipo: 'adicionar' }
}

/** Acrescenta um vértice. Clique repetido no MESMO lugar do último não vira vértice novo. */
export function adicionarVertice(vs: readonly Coord[], v: Coord): Coord[] {
  const ultimo = vs[vs.length - 1]
  if (ultimo && ultimo.lat === v.lat && ultimo.lng === v.lng) return [...vs]
  if (vs.length >= MAX_VERTICES) return [...vs]
  return [...vs, { lat: v.lat, lng: v.lng }]
}

/** Desfaz o último vértice. */
export function desfazerVertice(vs: readonly Coord[]): Coord[] {
  return vs.slice(0, -1)
}

/** Área com vírgula decimal e "km²" — 2 casas abaixo de 10 km², 1 acima. */
export function formatarKm2(v: number): string {
  const casas = v < 10 ? 2 : 1
  return `${v.toFixed(casas).replace('.', ',')} km²`
}

/** O estado do desenho para a barra flutuante: dá para concluir? Se não, POR QUÊ. */
export interface AvaliacaoDesenho {
  podeConcluir: boolean
  /** Motivo em texto de usuário quando NÃO dá para concluir; `null` quando dá. */
  motivo: string | null
  /** Área do polígono fechado (km²), ou `null` com menos de 3 vértices. */
  areaKm2: number | null
  nVertices: number
}

export function avaliarDesenho(vs: readonly Coord[]): AvaliacaoDesenho {
  const n = vs.length
  if (n < MIN_VERTICES) {
    const faltam = MIN_VERTICES - n
    return {
      podeConcluir: false,
      motivo: `Marque mais ${faltam} ${faltam === 1 ? 'vértice' : 'vértices'} para fechar a área.`,
      areaKm2: null,
      nVertices: n,
    }
  }
  const area = areaKm2(vs)
  if (temAutointersecao(vs)) {
    return {
      podeConcluir: false,
      motivo: 'Fechada assim, a área cruza a si mesma. Desfaça o último vértice e redesenhe.',
      areaKm2: area,
      nVertices: n,
    }
  }
  if (area < AREA_MIN_KM2) {
    return {
      podeConcluir: false,
      motivo: `A área tem ${formatarKm2(area)}; o mínimo é 0,1 km².`,
      areaKm2: area,
      nVertices: n,
    }
  }
  if (area > AREA_MAX_KM2) {
    return {
      podeConcluir: false,
      motivo: `A área tem ${formatarKm2(area)}; o máximo é 25 km².`,
      areaKm2: area,
      nVertices: n,
    }
  }
  return { podeConcluir: true, motivo: null, areaKm2: area, nVertices: n }
}

/** O Polygon GeoJSON do desenho: um anel FECHADO, em `[lng, lat]` (a ordem do GeoJSON). */
export interface PoligonoGeoJson {
  type: 'Polygon'
  coordinates: PosicaoGeoJson[][]
}

export function paraGeoJson(vs: readonly Coord[]): PoligonoGeoJson {
  const anel: PosicaoGeoJson[] = vs.map((v) => [v.lng, v.lat])
  if (anel.length) anel.push([anel[0][0], anel[0][1]])
  return { type: 'Polygon', coordinates: [anel] }
}

/** Ponto-em-polígono por raio (anel em `[lng, lat]`, fechado ou não). */
function contem(anel: readonly PosicaoGeoJson[], lng: number, lat: number): boolean {
  let dentro = false
  for (let i = 0, j = anel.length - 1; i < anel.length; j = i++) {
    const [xi, yi] = anel[i]
    const [xj, yj] = anel[j]
    if (yi > lat !== yj > lat && lng < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) dentro = !dentro
  }
  return dentro
}

/**
 * Um ponto DENTRO do polígono — para o pin provisório, enquanto o servidor ainda lê a área.
 *
 * O servidor devolve o `representative_point` dele, e o pin passa a ser aquele quando a
 * ficha chega. Até lá a tela precisa de um lugar para o pin, e o centroide NÃO serve: num
 * polígono côncavo (um "L", um "U") ele pode cair fora da área. Por isso: o centroide se
 * estiver dentro; senão o meio do trecho interno MAIS LARGO da horizontal que passa por
 * ele (a mesma ideia do `representative_point` do shapely).
 */
export function pontoInterno(anel: readonly PosicaoGeoJson[]): Coord {
  const pts = anel.length > 1 && anel[0][0] === anel[anel.length - 1][0] && anel[0][1] === anel[anel.length - 1][1]
    ? anel.slice(0, -1)
    : [...anel]
  if (!pts.length) return { lat: 0, lng: 0 }
  // Centroide de área (fórmula do laço); polígono degenerado cai na média dos vértices.
  let a = 0
  let cx = 0
  let cy = 0
  for (let i = 0; i < pts.length; i++) {
    const [x0, y0] = pts[i]
    const [x1, y1] = pts[(i + 1) % pts.length]
    const f = x0 * y1 - x1 * y0
    a += f
    cx += (x0 + x1) * f
    cy += (y0 + y1) * f
  }
  const media = {
    lng: pts.reduce((s, p) => s + p[0], 0) / pts.length,
    lat: pts.reduce((s, p) => s + p[1], 0) / pts.length,
  }
  const c = Math.abs(a) < 1e-18 ? media : { lng: cx / (3 * a), lat: cy / (3 * a) }
  if (contem(pts, c.lng, c.lat)) return c
  // Horizontal pela latitude do centroide: cruzamentos ordenados, pares (dentro, fora).
  const xs: number[] = []
  for (let i = 0; i < pts.length; i++) {
    const [x0, y0] = pts[i]
    const [x1, y1] = pts[(i + 1) % pts.length]
    if (y0 > c.lat !== y1 > c.lat) xs.push(x0 + ((c.lat - y0) * (x1 - x0)) / (y1 - y0))
  }
  xs.sort((p, q) => p - q)
  let melhor: Coord | null = null
  let largura = -1
  for (let i = 0; i + 1 < xs.length; i += 2) {
    if (xs[i + 1] - xs[i] > largura) {
      largura = xs[i + 1] - xs[i]
      melhor = { lng: (xs[i] + xs[i + 1]) / 2, lat: c.lat }
    }
  }
  return melhor ?? { lat: pts[0][1], lng: pts[0][0] }
}
