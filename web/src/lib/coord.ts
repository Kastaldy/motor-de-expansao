/* ---------------------------------------------------------------------------
   Parser de coordenada da barra de busca. Puro (sem rede): aceita `lat,lng` em
   ponto ou virgula decimal e links do Google Maps (`@lat,lng` ou `!3d..!4d`).
   Valida o bounding box do PAIS DA INSTANCIA, como o backend (api/coord.py).
   --------------------------------------------------------------------------- */

import { perfilDoCliente } from './perfil'

export interface Coord {
  lat: number
  lng: number
}

/**
 * Dentro do bbox do pais da instancia. O nome ficou `noBrasil` nesta onda: renomear
 * custa os call sites e o `coord.test.ts` sem mudar comportamento nenhum.
 *
 * A leitura do perfil e no CORPO, e nao numa const de modulo, de proposito (classe (1)
 * da spec §3.5): esta funcao so roda quando o operador DIGITA, sempre depois do
 * bootstrap. O custo e um acesso a objeto; o ganho e validar contra o pais da instancia
 * em vez de contra o Brasil de sempre, mesmo que alguem mude a ordem do bootstrap.
 */
function noBrasil(lat: number, lng: number): Coord | null {
  if (Number.isNaN(lat) || Number.isNaN(lng)) return null
  const bb = perfilDoCliente().bbox
  if (lat < bb.lat_min || lat > bb.lat_max) return null
  if (lng < bb.lng_min || lng > bb.lng_max) return null
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
  return ehCentroideDoHex(ponto)
    ? { lat: ponto.hex.lat, lng: ponto.hex.lng }
    : { lat: ponto.lat as number, lng: ponto.lng as number }
}

/**
 * O estudo caiu no CENTROIDE do hexagono (em vez do endereco exato)?
 *
 * Mesmo teste de `coordenadaDoEstudo` — extraido para que quem precisa AVISAR o
 * usuario sobre a aproximacao (o rotulo do PDF) leia a MESMA regra que escolhe a
 * coordenada, e nao uma copia livre para divergir. `true` = ponto veio do clique
 * num hexagono do ranking; `false` = busca por endereco/lat,lng, coordenada exata.
 */
export function ehCentroideDoHex(ponto: { lat?: number; lng?: number }): boolean {
  return ponto.lat == null || ponto.lng == null
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
