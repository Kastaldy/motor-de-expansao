/**
 * O que o operador colou na caixa do modo de ponto — classificado, PURO, sem rede.
 *
 * POR QUE EXISTE. `parseCoordinate` (lib/coord) responde uma coisa so': achei uma
 * coordenada do Brasil, ou `null`. Para a caixa de entrada isso e' pouco, porque `null`
 * hoje mistura quatro situacoes que pedem RESPOSTAS DIFERENTES ao operador:
 *
 *   - "Av. Paulista 1000"                 -> endereco, resolve por geocode
 *   - ".../maps/place/Academia+X/@..."    -> link longo, ja tem coordenada dentro
 *   - "https://maps.app.goo.gl/aBcD"      -> link CURTO: nao ha coordenada nenhuma na
 *                                            URL, e' preciso expandir no servidor
 *   - "38.7223, -9.1393" (Lisboa)         -> parece coordenada, mas cai fora do Brasil
 *
 * O caso do link curto e' o que mais dói na pratica: e' exatamente o que o botao
 * "Compartilhar" do app do Maps gera no celular. Hoje ele falha no parse e segue como
 * TEXTO para o geocode, que devolve "nao encontrei esse endereco" — mensagem que manda
 * o operador procurar erro de digitacao num link que esta perfeito.
 *
 * Aqui so' se CLASSIFICA. Quem resolve link curto e endereco e' o servidor (expandir o
 * link exige requisicao de rede, que nao pode acontecer no front).
 */

import { parseCoordinate, type Coord } from './coord'

export type TipoEntrada =
  | 'vazio'
  | 'coordenada'
  | 'link-curto'
  | 'link-maps'
  | 'endereco'
  | 'fora-do-brasil'

export interface EntradaClassificada {
  tipo: TipoEntrada
  /** So' preenchido quando `tipo === 'coordenada'`. */
  coord: Coord | null
  /** `true` quando resolver a entrada exige ida ao servidor. */
  precisaServidor: boolean
  /** Texto para o operador. Vazio quando nao ha nada a avisar. */
  aviso: string
}

/** Mesmos limites do backend (`api/coord.py`) e de `lib/coord.ts`. */
const BR = { latMin: -34.0, latMax: 5.5, lngMin: -74.0, lngMax: -28.0 }

/** Encurtadores que o app do Google Maps usa ao compartilhar. */
const RE_LINK_CURTO = /(?:maps\.app\.goo\.gl|goo\.gl\/maps)/i

/** Qualquer URL do Google Maps (inclui `/maps/place/...` sem coordenada). */
const RE_LINK_MAPS = /(?:google\.[a-z.]+\/maps|maps\.google\.[a-z.]+)/i

/** Par numerico solto, com ponto ou virgula decimal — "parece coordenada". */
const RE_PAR_NUMERICO =
  /^\s*(-?\d{1,3}(?:[.,]\d+)?)\s*[;, ]\s*(-?\d{1,3}(?:[.,]\d+)?)\s*$/

/**
 * Um par numerico que NAO passou no `parseCoordinate` esta fora da caixa do Brasil?
 *
 * Serve so' para separar "nao entendi o que voce colou" de "entendi, mas isso nao e'
 * Brasil" — duas mensagens bem diferentes para quem esta olhando a tela.
 */
function pareceCoordenadaForaDoBrasil(texto: string): boolean {
  const m = texto.match(RE_PAR_NUMERICO)
  if (!m) return false
  const lat = Number(m[1].replace(',', '.'))
  const lng = Number(m[2].replace(',', '.'))
  if (Number.isNaN(lat) || Number.isNaN(lng)) return false
  return (
    lat < BR.latMin || lat > BR.latMax || lng < BR.lngMin || lng > BR.lngMax
  )
}

export function classificarEntrada(bruto: string): EntradaClassificada {
  const texto = bruto.trim()

  if (!texto) {
    return { tipo: 'vazio', coord: null, precisaServidor: false, aviso: '' }
  }

  // 1. Coordenada legivel aqui mesmo (inclui link longo com `@lat,lng` / `!3d..!4d`).
  //    Vem PRIMEIRO: um link longo ja traz a coordenada, e resolve sem servidor.
  const coord = parseCoordinate(texto)
  if (coord) {
    return { tipo: 'coordenada', coord, precisaServidor: false, aviso: '' }
  }

  // 2. Link curto: nao ha coordenada NENHUMA na URL — so o servidor resolve.
  if (RE_LINK_CURTO.test(texto)) {
    return {
      tipo: 'link-curto',
      coord: null,
      precisaServidor: true,
      aviso:
        'Link curto do Google Maps — vou expandir para achar a coordenada. Se falhar, abra o link no navegador e cole o endereço da barra.',
    }
  }

  // 3. Link do Maps sem coordenada na URL (ex.: `/maps/place/Nome+Do+Lugar`).
  if (RE_LINK_MAPS.test(texto)) {
    return {
      tipo: 'link-maps',
      coord: null,
      precisaServidor: true,
      aviso: 'Link do Google Maps sem coordenada na URL — vou resolver pelo nome do lugar.',
    }
  }

  // 4. Parece coordenada, mas nao e' Brasil. Mensagem propria: dizer "não reconheci"
  //    aqui faria o operador procurar erro de digitação numa coordenada correta.
  if (pareceCoordenadaForaDoBrasil(texto)) {
    return {
      tipo: 'fora-do-brasil',
      coord: null,
      precisaServidor: false,
      aviso:
        'Essa coordenada está fora do Brasil. Confira se a latitude e a longitude não vieram trocadas.',
    }
  }

  // 5. Sobrou texto livre: endereço, resolve por geocode no servidor.
  return { tipo: 'endereco', coord: null, precisaServidor: true, aviso: '' }
}

/**
 * Link de SAIDA para o operador conferir, no proprio Maps, onde o pino caiu.
 *
 * Usa `?q=lat,lng` (e nao `/@lat,lng`) de proposito: a forma com `q` solta um PINO na
 * coordenada exata, enquanto `@` so' centraliza a camera e nao marca nada — o operador
 * ficaria olhando um mapa sem saber qual ponto foi analisado.
 *
 * Sempre com PONTO decimal e sem separador de milhar: a URL nao e' texto de usuario, e
 * `toLocaleString` pt-BR aqui produziria `-23,55` e quebraria o link.
 */
export function linkGoogleMaps(lat: number, lng: number): string {
  return `https://www.google.com/maps?q=${lat},${lng}`
}
