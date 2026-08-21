/**
 * Régua do mapa: distância entre dois pontos, com TRAVA nos pins.
 *
 * POR QUE A TRAVA. A medição que interessa não é entre dois cliques quaisquer — é do ponto
 * analisado até uma concorrente ou uma unidade nossa. Clique livre nunca cai exatamente
 * sobre o pin: cada pessoa mede um número diferente para o MESMO par, e o número deixa de
 * servir para decidir. Imantando a ponta no pin, o par vira sempre a mesma distância.
 *
 * Funções PURAS, sem deck.gl e sem React, para o teste não precisar montar mapa.
 */

/** Raio médio da Terra em metros (WGS-84). */
const RAIO_TERRA_M = 6_371_008.8

export interface Coord {
  lat: number
  lng: number
}

/** Ponto imantável no mapa: um pin de concorrente/Ultra, ou o próprio imóvel analisado. */
export interface AlvoMedicao extends Coord {
  /** O que aparece na leitura: "Smart Fit - Paulista", "Ultra Academia", "Ponto analisado". */
  rotulo: string
  /** Origem do alvo — define a cor da ponta e o texto da leitura. */
  tipo: 'ponto' | 'concorrente' | 'ultra'
}

const rad = (graus: number): number => (graus * Math.PI) / 180

/**
 * Distância em METROS pela fórmula de haversine.
 *
 * Haversine e não Vincenty: a Terra como esfera erra ~0,3% contra o elipsoide, o que em
 * 1 km dá 3 m — irrelevante para "a concorrente está a 380 m". Vincenty custaria iteração
 * e casos degenerados (antípodas) que esta tela nunca vai ver.
 */
export function distanciaMetros(a: Coord, b: Coord): number {
  const dLat = rad(b.lat - a.lat)
  const dLng = rad(b.lng - a.lng)
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLng / 2) ** 2
  return 2 * RAIO_TERRA_M * Math.asin(Math.min(1, Math.sqrt(h)))
}

/**
 * Tolerância da trava, em PIXELS de tela.
 *
 * Em pixels e não em metros de propósito: a mesma folga em metros seria generosa no zoom
 * de rua e absurda no de cidade, onde imantaria um pin a quilômetros do clique. O que o
 * operador enxerga como "cliquei no pin" é uma distância de TELA, e é ela que manda.
 */
export const TOLERANCIA_TRAVA_PX = 28

/**
 * Pin mais próximo do clique, dentro da tolerância — ou `null` para medir no ponto livre.
 *
 * `metrosPorPixel` vem da câmera do mapa; sem ele não há como converter a tolerância de
 * tela em distância no terreno.
 */
export function travarNoAlvo(
  clique: Coord,
  alvos: readonly AlvoMedicao[],
  metrosPorPixel: number,
): AlvoMedicao | null {
  if (alvos.length === 0 || !Number.isFinite(metrosPorPixel) || metrosPorPixel <= 0) return null
  const limite = TOLERANCIA_TRAVA_PX * metrosPorPixel
  let melhor: AlvoMedicao | null = null
  let menor = Infinity
  for (const alvo of alvos) {
    const d = distanciaMetros(clique, alvo)
    if (d <= limite && d < menor) {
      menor = d
      melhor = alvo
    }
  }
  return melhor
}

/**
 * Metros por pixel de tela num dado zoom/latitude (Web Mercator, tile de 512 px).
 *
 * O `cos(lat)` não é detalhe: em Mercator o mesmo zoom cobre menos terreno por pixel
 * quanto mais longe do equador, e ignorá-lo faria a trava ser mais frouxa no Sul do país
 * do que no Norte.
 */
export function metrosPorPixel(zoom: number, lat: number): number {
  return (156_543.03392 * Math.cos(rad(lat))) / 2 ** zoom / 2
}
