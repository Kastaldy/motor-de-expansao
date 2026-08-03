/* ---------------------------------------------------------------------------
   Parser de coordenada da barra de busca. Puro (sem rede): aceita `lat,lng` em
   ponto ou virgula decimal e links do Google Maps (`@lat,lng` ou `!3d..!4d`).
   Valida o bounding box do Brasil, como o backend (api/coord.py).
   --------------------------------------------------------------------------- */

// Mesmos limites do backend: lat -34..5.5, lng -74..-28.
const BR = { latMin: -34.0, latMax: 5.5, lngMin: -74.0, lngMax: -28.0 }

export interface Coord {
  lat: number
  lng: number
}

function noBrasil(lat: number, lng: number): Coord | null {
  if (Number.isNaN(lat) || Number.isNaN(lng)) return null
  if (lat < BR.latMin || lat > BR.latMax) return null
  if (lng < BR.lngMin || lng > BR.lngMax) return null
  return { lat, lng }
}

/**
 * Coordenada que representa o IMOVEL num estudo pontual.
 *
 * Prefere a coordenada EXATA (busca por endereco/lat,lng) e so cai no centroide do
 * hexagono quando ela nao existe (ponto veio do clique num hex do ranking, onde o
 * centroide e mesmo a unica coordenada disponivel).
 *
 * Por que importa: `hex.lat/hex.lng` sao o centroide do hex res-7, a ate ~1,5 km do
 * endereco. Usa-lo no Relatorio Pontual (a) tirava a foto de satelite (cobertura de
 * 400 m) e o mapa de quadra (~300 m) de outro lugar e (b) na orla jogava o ponto no
 * mar, onde a malha municipal do IBGE nao resolve -> HTTP 400 "fora do Brasil".
 */
export function coordenadaDoEstudo(ponto: {
  hex: { lat: number; lng: number }
  lat?: number
  lng?: number
}): Coord {
  return ponto.lat != null && ponto.lng != null
    ? { lat: ponto.lat, lng: ponto.lng }
    : { lat: ponto.hex.lat, lng: ponto.hex.lng }
}

/**
 * Extrai uma coordenada de texto livre. Retorna `null` se nao reconhecer ou se
 * cair fora do Brasil. Ordem: link do Maps -> par decimal com ponto -> par pt-BR.
 */
export function parseCoordinate(raw: string): Coord | null {
  const s = raw.trim()
  if (!s) return null

  // Google Maps: @lat,lng  ou  !3dlat!4dlng
  let m =
    s.match(/@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/) ||
    s.match(/!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)/)
  if (m) return noBrasil(parseFloat(m[1]), parseFloat(m[2]))

  // Par decimal com ponto: "-15.79, -47.88" ou "-15.79 -47.88"
  m = s.match(/(-?\d+\.\d+)\s*[;, ]\s*(-?\d+\.\d+)/)
  if (m) return noBrasil(parseFloat(m[1]), parseFloat(m[2]))

  // Par pt-BR (virgula decimal), separado por ; ou espaco: "-15,79; -47,88"
  m = s.match(/(-?\d+,\d+)\s*[; ]\s*(-?\d+,\d+)/)
  if (m) {
    return noBrasil(
      parseFloat(m[1].replace(',', '.')),
      parseFloat(m[2].replace(',', '.')),
    )
  }

  // Dois inteiros/decimais soltos como ultimo recurso: "-15 -47"
  m = s.match(/(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)/)
  if (m) return noBrasil(parseFloat(m[1]), parseFloat(m[2]))

  return null
}
