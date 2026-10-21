/**
 * O ALCANCE de um ponto (DEC-074): de que recorte em volta dele a ficha fala.
 *
 * Quatro opções: o raio de 1 km (o estudo de sempre), o raio de 2 km e 10 min de carro sem
 * trânsito (a isócrona, calculada no servidor pelo serviço de rotas), decididas pelo dono
 * em 19/10/2026; e 5 min de carro, também sem trânsito, pedida pelo Vinicius em 20/10/2026
 * (Emenda 1 da DEC-074 — a análise com trânsito foi considerada e descartada). Trocar o alcance troca o recorte do PRÓPRIO item, no lugar — o ponto
 * continua sendo um só na lista, com o mesmo nome, a mesma cor e a mesma posição.
 *
 * QUEM DECIDE O QUE EXISTE É O SERVIDOR. A lista de alcances vem do `/api/me` (chave
 * `alcances`): os alcances de carro só aparecem quando a instância tem o serviço de rotas
 * configurado, e SOME sem ele — opção apagada que não pode acender mente (a convenção das
 * chaves do mapa). Backend anterior a esta chave não tem a rota de alcance, então sem ela
 * só o raio de 1 km existe e o seletor nem aparece.
 *
 * O CONTORNO que o mapa desenha também sai daqui: o círculo do raio é gerado na tela a
 * partir do `raio_km` (o servidor não manda polígono para círculo), e a isócrona e a área
 * desenhada chegam prontas no payload.
 *
 * Módulo PURO (sem React, sem deck.gl): o Vitest roda em node.
 */

import { latLngToCell } from 'h3-js'
import { ehAreaDesenhada, tipoDoRecorte } from './recorte'
import type { ContornoGeoJson, PontoPayload } from './types'

/** Identificadores CRUS do alcance — NÃO acentuar (são os valores da rota e do payload). */
export type Alcance = 'raio_1km' | 'raio_2km' | 'carro_5min' | 'carro_10min'

/** Os alcances na ordem em que o seletor os mostra: os raios, depois o carro do menor tempo ao maior. */
export const ALCANCES: readonly Alcance[] = Object.freeze(['raio_1km', 'raio_2km', 'carro_5min', 'carro_10min'])

/** O alcance de todo ponto que chega sem dizer o seu: o raio de 1 km de sempre (DEC-021). */
export const ALCANCE_PADRAO: Alcance = 'raio_1km'

/** O raio, em km, dos alcances que são círculo. A isócrona não tem raio. */
export const RAIO_DO_ALCANCE: Readonly<Record<'raio_1km' | 'raio_2km', number>> = Object.freeze({
  raio_1km: 1,
  raio_2km: 2,
})

/** O rótulo de EXIBIÇÃO de cada alcance (a camada de label: o valor cru não muda). */
export const ROTULO_ALCANCE: Readonly<Record<Alcance, string>> = Object.freeze({
  raio_1km: 'Raio de 1 km',
  raio_2km: 'Raio de 2 km',
  carro_5min: '5 min de carro',
  carro_10min: '10 min de carro',
})

export function ehAlcance(v: unknown): v is Alcance {
  return typeof v === 'string' && (ALCANCES as readonly string[]).includes(v)
}

/* Estado do módulo, no molde de `viabilidade-demanda`: nasce só com o raio de 1 km, que é
   o que um backend sem a chave sabe servir. */
let disponiveis: readonly Alcance[] = Object.freeze([ALCANCE_PADRAO])

/** Os alcances que esta instância oferece, na ordem do seletor. Sempre começa no raio de 1 km. */
export function alcancesDisponiveis(): readonly Alcance[] {
  return disponiveis
}

/**
 * Instala a lista vinda do `/api/me` (`alcances`). Chamado UMA vez, pelo `main.tsx`.
 *
 * Defensivo: chave ausente ou malformada deixa só o raio de 1 km e não derruba o app;
 * valor desconhecido é ignorado (um servidor mais novo pode oferecer um alcance que esta
 * tela ainda não sabe desenhar). O raio de 1 km entra SEMPRE — é o estudo de hoje, e o
 * seletor precisa dele para voltar.
 */
export function definirAlcances(p: unknown): void {
  disponiveis = Object.freeze([ALCANCE_PADRAO])
  if (!Array.isArray(p)) return
  const pedidos = new Set(p.filter(ehAlcance))
  disponiveis = Object.freeze(ALCANCES.filter((a) => a === ALCANCE_PADRAO || pedidos.has(a)))
}

/** SÓ para teste: devolve o módulo ao estado de import. */
export function _resetarAlcancesParaTeste(): void {
  disponiveis = Object.freeze([ALCANCE_PADRAO])
}

/**
 * O alcance de um item da lista, ou `null` quando ele é uma ÁREA DESENHADA à mão (que não
 * tem alcance: o recorte é o polígono do operador).
 */
export function alcanceDoItem(
  p: Pick<PontoPayload, 'raio_km' | 'geometria' | 'recorte' | 'mercado'>,
): Alcance | null {
  const tipo = tipoDoRecorte(p)
  return tipo === 'poligono' ? null : tipo
}

/** Uma posição GeoJSON: `[lng, lat]`. */
type Posicao = [number, number]

const RAIO_TERRA_M = 6_371_008.8

/**
 * O círculo de `raioKm` em volta de (lat, lng) como Polygon GeoJSON — um anel fechado de
 * `lados` vértices em `[lng, lat]`.
 *
 * GEODÉSICO (ponto de destino na esfera), e não um círculo em graus: em graus, longitude
 * encolhe com o cosseno da latitude e o "círculo" de Porto Alegre sairia uma elipse. 64
 * lados dão um polígono a menos de 0,2% da área do círculo — invisível no mapa.
 */
export function circuloGeoJson(
  lat: number,
  lng: number,
  raioKm: number,
  lados = 64,
): { type: 'Polygon'; coordinates: Posicao[][] } {
  const d = (raioKm * 1000) / RAIO_TERRA_M
  const f1 = (lat * Math.PI) / 180
  const l1 = (lng * Math.PI) / 180
  const anel: Posicao[] = []
  for (let k = 0; k < lados; k++) {
    const rumo = (2 * Math.PI * k) / lados
    const f2 = Math.asin(Math.sin(f1) * Math.cos(d) + Math.cos(f1) * Math.sin(d) * Math.cos(rumo))
    const l2 =
      l1 +
      Math.atan2(Math.sin(rumo) * Math.sin(d) * Math.cos(f1), Math.cos(d) - Math.sin(f1) * Math.sin(f2))
    anel.push([(l2 * 180) / Math.PI, (f2 * 180) / Math.PI])
  }
  anel.push(anel[0])
  return { type: 'Polygon', coordinates: [anel] }
}

const ehPosicao = (v: unknown): v is Posicao =>
  Array.isArray(v) && v.length >= 2 && Number.isFinite(v[0]) && Number.isFinite(v[1])

const ehAnel = (v: unknown): v is Posicao[] => Array.isArray(v) && v.length >= 4 && v.every(ehPosicao)

const ehPoligono = (v: unknown): v is Posicao[][] => Array.isArray(v) && v.length > 0 && v.every(ehAnel)

/**
 * Os POLÍGONOS de um contorno GeoJSON (Polygon ou MultiPolygon), cada um com seus anéis —
 * o externo primeiro, os buracos depois. Contorno malformado vira lista vazia: o mapa fica
 * sem a linha em vez de quebrar a camada inteira.
 */
export function poligonosDoContorno(c: ContornoGeoJson | null | undefined): Posicao[][][] {
  if (!c || typeof c !== 'object') return []
  if (c.type === 'Polygon') return ehPoligono(c.coordinates) ? [c.coordinates] : []
  if (c.type === 'MultiPolygon' && Array.isArray(c.coordinates)) return c.coordinates.filter(ehPoligono)
  return []
}

/** O mínimo de um item para o mapa saber que contorno desenhar. */
export interface ItemComContorno {
  lat: number
  lng: number
  raio_km?: number | null
  geometria?: Posicao[][] | null
  recorte?: { contorno?: ContornoGeoJson | null } | null
}

/**
 * O contorno que o item REPRESENTA, como lista de polígonos (cada um, lista de anéis).
 *
 * Decisão do dono (19/10/2026): todo item de ponto mostra o seu recorte no mapa — o raio
 * de 1 km também, que antes não era desenhado. A ordem é a da fonte mais exata:
 *  1. a área desenhada (os vértices do operador);
 *  2. o contorno que o servidor mandou (isócrona, ou o desenho normalizado);
 *  3. o círculo do `raio_km`, gerado aqui.
 * Item sem nenhum dos três (o pendente de um ponto, que ainda não sabe o raio) não tem
 * contorno.
 */
export function contornosDoItem(p: ItemComContorno): Posicao[][][] {
  if (p.geometria?.length) return [p.geometria]
  const doServidor = poligonosDoContorno(p.recorte?.contorno)
  if (doServidor.length) return doServidor
  if (typeof p.raio_km === 'number' && p.raio_km > 0) {
    return [circuloGeoJson(p.lat, p.lng, p.raio_km).coordinates]
  }
  return []
}

/** O mínimo de um pin para saber se o alcance dele substitui a marca do hexágono. */
export interface PinComAlcance {
  hexId: string | null
  contornos: readonly unknown[]
  /**
   * A coordenada do pin. Serve quando `hexId` ainda é nulo — o pendente de uma área
   * desenhada já tem contorno, mas não tem `hex_id` até a ficha chegar, e o mapa já
   * seleciona o hexágono da coordenada (`latLngToCell`, como em `pontos-estado`).
   */
  lat?: number | null
  lng?: number | null
}

/**
 * O hexágono que o ALCANCE do ponto substitui como marca — ou `null`.
 *
 * Pedido do Vinicius (20/10/2026): com o recorte desenhado (o círculo de 1 km também), o
 * contorno do hexágono do ponto se sobrepunha ao do alcance, e duas linhas em volta do
 * mesmo ponto não dizem qual é o recorte. Quando o pin tem contorno, o ALCANCE é a única
 * marca do ponto; sem contorno (o pendente, que ainda não sabe o raio) o hexágono segue
 * marcado como sempre.
 *
 * Sem `hexId` mas com contorno (o pendente de uma ÁREA DESENHADA: o polígono já aparece,
 * a ficha ainda não), o hexágono é o da coordenada em res-7 — o mesmo que o ponto ativo
 * seleciona (`pontos-estado`) —, senão as duas marcas apareciam juntas até a ficha chegar.
 */
export function hexSubstituidoPeloAlcance(pin: PinComAlcance | null | undefined): string | null {
  if (!pin || !pin.contornos?.length) return null
  if (pin.hexId) return pin.hexId
  const { lat, lng } = pin
  if (typeof lat !== 'number' || typeof lng !== 'number') return null
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null
  return latLngToCell(lat, lng, 7)
}

/**
 * A seleção que o MAPA contorna: a de sempre, salvo quando ela veio do PONTO ativo
 * (`selecaoDoPonto`) e o alcance dele já está desenhado — aí o contorno é do alcance
 * (`hexSubstituidoPeloAlcance`). Clique DIRETO no hexágono continua marcado, mesmo que
 * seja o hexágono do ponto: ali o operador escolheu a célula, não o recorte.
 */
export function selecaoMarcadaNoMapa(
  selecionado: string | null,
  selecaoDoPonto: boolean,
  pinAtivo: PinComAlcance | null | undefined,
): string | null {
  if (!selecionado || !selecaoDoPonto) return selecionado
  return hexSubstituidoPeloAlcance(pinAtivo) === selecionado ? null : selecionado
}

/**
 * O fator das RÉGUAS DE TOTAIS do item: área do recorte / área do raio de 1 km.
 *
 * Vem do servidor (`recorte.fator_regua`, exato) sempre que ele mandar — a tela não
 * re-decide régua. Payload anterior à chave: o raio dá `raio²` (1 km -> exatamente 1), a
 * área desenhada com área conhecida dá `área / π`; sem nada disso, `null` ("não sei").
 */
export function fatorReguaDoItem(
  p: Pick<PontoPayload, 'raio_km' | 'geometria' | 'recorte' | 'mercado'>,
): number | null {
  const doServidor = p.recorte?.fator_regua
  if (typeof doServidor === 'number' && Number.isFinite(doServidor) && doServidor > 0) return doServidor
  if (!ehAreaDesenhada(p) && typeof p.raio_km === 'number' && p.raio_km > 0) return p.raio_km ** 2
  const area = p.recorte?.area_km2 ?? p.mercado?.area_km2 ?? null
  if (typeof area === 'number' && area > 0) return area / Math.PI
  return null
}

/** "4,0" / "24,7": uma casa, vírgula fixa (sem depender do locale da instância). */
function fatorCurto(f: number): string {
  return f.toFixed(1).replace('.', ',')
}

/**
 * A nota que DECLARA a escala das réguas — ou `null` no raio de 1 km, onde nada escala.
 *
 * As metas de totais (população, residual, concorrentes) multiplicam pelo fator na tela e
 * no PDF juntos (DEC-074); sem a nota, um "precisa de 20.000 pessoas" pareceria outra
 * régua da rede, e não a mesma régua num recorte maior.
 */
export function notaDaReguaEscalada(
  p: Pick<PontoPayload, 'raio_km' | 'geometria' | 'recorte' | 'mercado'>,
): string | null {
  const f = fatorReguaDoItem(p)
  if (f == null || Math.abs(f - 1) < 1e-9) return null
  return `Réguas de totais escaladas ×${fatorCurto(f)} pela área do recorte`
}
