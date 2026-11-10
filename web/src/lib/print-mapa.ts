/**
 * PRINT LIMPO DO MAPA de um ponto: imagem 16:9 só com o fundo de ruas, o alcance e o pin.
 *
 * Pedido do Vinicius (10/11/2026): um botão na ficha do ponto que entregue uma foto da
 * região para apresentação, SEM hexágono, setor censitário ou número — só o lugar, o
 * recorte em volta dele e um realce capaz de separar zona urbana de rural, ruas de
 * avenidas e de rodovias, e os rios.
 *
 * POR QUE NÃO É A CAPTURA DO MAPA DA TELA (`captura-mapa`). Aquela fotografa o que o
 * operador está vendo, com as camadas do produto por cima e no tema dele (o escuro, na
 * maioria das telas). O print é OUTRA imagem: renderizada num mapa próprio, fora da tela,
 * num tamanho fixo e com um estilo claro de alto contraste. Nada do mapa da tela muda.
 *
 * O ESTILO. Parte do Voyager do CARTO — mesmo fornecedor e mesmos tiles vetoriais que o
 * piloto já usa — baixado na hora e REALÇADO aqui (`realcarEstilo`). Baixar na hora, e não
 * copiar o JSON para o repo, porque o CARTO versiona a URL dos tiles (`/v/AAAAMMDD-NN/`) e
 * uma cópia congelada pararia de achar os tiles na próxima troca. O realce é por REGRA
 * sobre o id da camada: camada que a regra não reconhece segue com a cor do Voyager, então
 * uma renomeação do lado do CARTO piora o realce, nunca quebra o print.
 *
 * Módulo PURO (sem DOM, sem MapLibre): o Vitest roda em node. Quem desenha é
 * `print-mapa-render.ts`.
 */

import { contornosDoItem, circuloGeoJson, type ItemComContorno } from './alcance'
import { metrosPorPixel } from './captura-mapa'

// ---------------------------------------------------------------------------
// Quadro
// ---------------------------------------------------------------------------

/**
 * Tamanho do quadro em pixels CSS — é nele que o mapa enquadra e o zoom é calculado.
 *
 * 1280×720 com densidade 2 sai 2560×1440 (16:9, QHD): nítido em slide e em tela cheia, e
 * com rótulos do tamanho de um mapa de verdade. Renderizar direto a 1920×1080 em
 * densidade 1 deixaria os nomes de rua miúdos demais para ler numa apresentação.
 */
export const LARGURA_PRINT_CSS = 1280
export const ALTURA_PRINT_CSS = 720
export const DENSIDADE_PRINT = 2

/** Folga em volta do alcance, em pixels CSS: o contorno nunca encosta na borda. */
export const FOLGA_PRINT_CSS = 56

/**
 * Folga EXTRA no topo: o pin sobe ~48 px acima da coordenada. Sem ela, um ponto na borda
 * norte de uma isócrona teria a cabeça do pin cortada.
 */
export const FOLGA_PIN_CSS = 40

/** Zoom máximo: os tiles do CARTO vão até o 15, e acima de ~16 a imagem vira textura. */
export const ZOOM_PRINT_MAX = 16

/** Zoom mínimo: abaixo disso as ruas somem dos tiles e a foto deixa de ser de rua. */
export const ZOOM_PRINT_MIN = 9

/** Raio usado quando o item não traz contorno nenhum (o pendente): o estudo de sempre. */
export const RAIO_SEM_CONTORNO_KM = 1

/** Lado do tile do Web Mercator usado pelo MapLibre (ver `captura-mapa`). */
const LADO_DO_TILE = 512

/** Caixa [oeste, sul, leste, norte], em graus. */
export type Caixa = [number, number, number, number]

/** Uma posição GeoJSON `[lng, lat]`. */
type Posicao = [number, number]

/**
 * Os polígonos do ALCANCE do item, na mesma regra do mapa (`contornosDoItem`): a área
 * desenhada, o contorno do servidor (isócrona) ou o círculo do raio. Item sem nada disso
 * ganha o círculo de 1 km — o print sempre tem um recorte a mostrar.
 */
export function alcanceDoPrint(item: ItemComContorno): Posicao[][][] {
  const doItem = contornosDoItem(item)
  if (doItem.length) return doItem
  return [circuloGeoJson(item.lat, item.lng, RAIO_SEM_CONTORNO_KM).coordinates]
}

/**
 * A caixa que o print tem de mostrar INTEIRA: todos os anéis externos do alcance e o
 * próprio ponto (que fica dentro do recorte, mas a garantia é barata). `null` só sem
 * nenhuma coordenada válida.
 */
export function caixaDoPrint(poligonos: readonly Posicao[][][], ponto?: { lat: number; lng: number } | null): Caixa | null {
  const pts: Posicao[] = poligonos.flatMap((p) => p[0] ?? [])
  if (ponto && Number.isFinite(ponto.lat) && Number.isFinite(ponto.lng)) pts.push([ponto.lng, ponto.lat])
  const validos = pts.filter(([x, y]) => Number.isFinite(x) && Number.isFinite(y) && Math.abs(y) < 85)
  if (!validos.length) return null
  const xs = validos.map(([x]) => x)
  const ys = validos.map(([, y]) => y)
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)]
}

/** Longitude/latitude -> coordenada do mundo Web Mercator no zoom 0, em [0, 1]. */
function paraMundo(lng: number, lat: number): [number, number] {
  const x = (lng + 180) / 360
  const s = Math.sin((lat * Math.PI) / 180)
  const y = 0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI)
  return [x, y]
}

/** Inverso de `paraMundo`. */
function doMundo(x: number, y: number): { lng: number; lat: number } {
  const lng = x * 360 - 180
  const lat = (Math.atan(Math.sinh(Math.PI * (1 - 2 * y))) * 180) / Math.PI
  return { lng, lat }
}

export interface QuadroPrint {
  centro: { lng: number; lat: number }
  zoom: number
}

/**
 * Câmera que mostra a caixa INTEIRA no quadro, com a folga de cada lado.
 *
 * Calculada aqui (e não pelo `fitBounds` do MapLibre) para ser TESTÁVEL: o enquadramento é
 * a promessa do botão ("o alcance aparece por completo"), e promessa sem teste regride
 * calada. A conta é a do Web Mercator com tile de 512 px — a mesma convenção do MapLibre.
 * O centro é o meio da caixa NO MUNDO PROJETADO (não em graus), descontada a folga
 * assimétrica do pin no topo.
 */
export function quadroDoPrint(
  caixa: Caixa,
  largura: number = LARGURA_PRINT_CSS,
  altura: number = ALTURA_PRINT_CSS,
  folga: number = FOLGA_PRINT_CSS,
  folgaTopo: number = FOLGA_PRINT_CSS + FOLGA_PIN_CSS,
): QuadroPrint {
  const [o, s, l, n] = caixa
  const [x0, y0] = paraMundo(o, n)
  const [x1, y1] = paraMundo(l, s)
  const dx = Math.max(x1 - x0, 1e-12)
  const dy = Math.max(y1 - y0, 1e-12)
  const uteisX = Math.max(largura - 2 * folga, 1)
  const uteisY = Math.max(altura - folga - folgaTopo, 1)
  let zoom = Math.min(Math.log2(uteisX / (dx * LADO_DO_TILE)), Math.log2(uteisY / (dy * LADO_DO_TILE)))
  if (!Number.isFinite(zoom)) zoom = ZOOM_PRINT_MAX
  zoom = Math.min(ZOOM_PRINT_MAX, Math.max(ZOOM_PRINT_MIN, zoom))
  // Px do mundo por unidade no zoom escolhido; o deslocamento do pin vira fração do mundo.
  const escala = LADO_DO_TILE * 2 ** zoom
  const deslocY = (folgaTopo - folga) / 2 / escala
  const centro = doMundo((x0 + x1) / 2, (y0 + y1) / 2 - deslocY)
  return { centro, zoom }
}

// ---------------------------------------------------------------------------
// Escala gráfica
// ---------------------------------------------------------------------------

/** Distâncias "redondas" que a barra de escala pode mostrar, em metros. */
const DISTANCIAS_ESCALA_M = [50, 100, 200, 250, 500, 1000, 2000, 2500, 5000, 10000, 20000, 25000, 50000]

/**
 * A barra de escala: a maior distância redonda que cabe em `maxPx` pixels CSS.
 * `rotulo` em português, com "km" a partir de 1.000 m.
 */
export function escalaDoPrint(
  latitude: number,
  zoom: number,
  maxPx = 150,
): { metros: number; px: number; rotulo: string } {
  const mpp = metrosPorPixel(latitude, zoom)
  let escolhida = DISTANCIAS_ESCALA_M[0]
  for (const d of DISTANCIAS_ESCALA_M) if (d / mpp <= maxPx) escolhida = d
  const rotulo = escolhida >= 1000 ? `${String(escolhida / 1000).replace('.', ',')} km` : `${escolhida} m`
  return { metros: escolhida, px: escolhida / mpp, rotulo }
}

// ---------------------------------------------------------------------------
// Rótulo e nome do arquivo
// ---------------------------------------------------------------------------

/** "Várzea · Teresópolis/RJ" — o lugar sob o pin, sem número nenhum. */
export function rotuloDoPrint(nome: string | null | undefined, municipio: string | null | undefined, uf: string | null | undefined): string {
  const cidade = [municipio, uf].filter(Boolean).join('/')
  const partes = [nome, cidade].filter((p): p is string => !!p && !!p.trim())
  // O bairro com o mesmo nome da cidade ("Teresópolis · Teresópolis/RJ") não diz nada.
  if (partes.length === 2 && municipio && nome && semAcento(nome) === semAcento(municipio)) return cidade
  return partes.join(' · ')
}

function semAcento(s: string): string {
  return s.normalize('NFD').replace(/[̀-ͯ]/g, '').trim().toLowerCase()
}

/** Pedaço seguro para nome de arquivo: sem acento, minúsculo, hífen no lugar do resto. */
function slug(s: string): string {
  return semAcento(s).replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 60)
}

/**
 * `mapa-varzea-teresopolis-rj-raio-1km.png`. O alcance entra no nome porque o mesmo ponto
 * gera quatro imagens diferentes (1 e 2 km, 5 e 10 min) e o operador costuma baixar mais
 * de uma.
 */
export function nomeDoArquivoPrint(rotulo: string, recorte: string | null | undefined): string {
  const partes = ['mapa', slug(rotulo), recorte ? slug(recorte) : ''].filter(Boolean)
  return `${partes.join('-') || 'mapa'}.png`
}

// ---------------------------------------------------------------------------
// Estilo realçado
// ---------------------------------------------------------------------------

/** O estilo-base: Voyager do CARTO (claro e colorido), na URL estável. */
export const ESTILO_BASE_PRINT = 'https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json'

/** Crédito obrigatório da licença do fundo (OpenStreetMap ODbL + CARTO). */
export const CREDITO_PRINT = '© OpenStreetMap · © CARTO'

/**
 * A PALETA do print. Pensada em camadas de leitura:
 *  - o CHÃO separa o que é cidade do que é campo PELA COBERTURA, não pelo fundo: mata em
 *    verde cheio, pasto e campo em verde-claro, lavoura em palha, rocha em pedra; a cidade
 *    em cinza, com as quadras brancas e os prédios por cima. O fundo (onde o OSM não diz
 *    nada) fica NEUTRO de propósito: medido em 10/11/2026, o centro de Teresópolis não tem
 *    polígono residencial no OSM, e com um fundo esverdeado ele saía com cara de campo;
 *  - a ÁGUA em azul franco (rio com linha mais grossa que a do Voyager, que some no claro);
 *  - as VIAS por hierarquia, como no mapa de referência: rodovia em laranja, avenida em
 *    amarelo, rua coletora em amarelo-claro, rua local em branco com contorno cinza.
 */
export const PALETA_PRINT = Object.freeze({
  fundo: '#efeee9',
  lavoura: '#f0e7bd',
  rocha: '#e3ded3',
  alagado: '#d3e6dc',
  vegetacao: '#c3dcab',
  campo: '#d9e9c4',
  urbano: '#e0dedb',
  urbanoEspecial: '#d6d3d4',
  predio: '#d0c9bf',
  agua: '#9fcdec',
  rio: '#6db3e0',
  rotuloAgua: '#1d6a9e',
  rodovia: '#f39a3b',
  rodoviaContorno: '#c8701b',
  avenida: '#ffd05e',
  avenidaContorno: '#d29f2c',
  coletora: '#fff1b8',
  coletoraContorno: '#d5c07c',
  rua: '#ffffff',
  ruaContorno: '#c5bfb5',
  ferrovia: '#a39f98',
  rotuloRua: '#3f4a58',
  rotuloLugar: '#2f3d4f',
  halo: '#ffffff',
  limite: '#b9aeb8',
  alcance: '#1b3fd0',
})

/** Classe de via que o id da camada do Voyager carrega (`road_pri_fill_noramp`...). */
type ClasseVia = 'mot' | 'trunk' | 'pri' | 'sec' | 'minor' | 'service'

/**
 * Larguras (px) por zoom de cada classe — preenchimento e contorno. Mais largas que as do
 * Voyager: no print a rua é o assunto, e na faixa de zoom do print (≈ 11 a 15) o Voyager
 * desenha a rua local em 0,5–2 px, branca sobre claro, quase invisível.
 */
const LARGURAS: Record<ClasseVia, { fill: [number, number][]; case: [number, number][]; minzoom: number }> = {
  mot: { minzoom: 5, fill: [[8, 1.2], [10, 2.2], [12, 3.6], [14, 7], [16, 12]], case: [[8, 2], [10, 3.4], [12, 5.2], [14, 9.4], [16, 15]] },
  trunk: { minzoom: 5, fill: [[8, 1.2], [10, 2.2], [12, 3.6], [14, 7], [16, 12]], case: [[8, 2], [10, 3.4], [12, 5.2], [14, 9.4], [16, 15]] },
  pri: { minzoom: 7, fill: [[8, 0.8], [10, 1.6], [12, 2.8], [14, 6], [16, 10]], case: [[8, 1.4], [10, 2.6], [12, 4.2], [14, 8], [16, 12.5]] },
  sec: { minzoom: 10, fill: [[10, 0.8], [12, 1.8], [14, 4.4], [16, 8]], case: [[10, 1.3], [12, 2.8], [14, 6], [16, 10]] },
  minor: { minzoom: 12, fill: [[12, 0.6], [13, 1.2], [14, 2.6], [16, 6]], case: [[12, 1.2], [13, 2.2], [14, 4], [16, 8]] },
  service: { minzoom: 14, fill: [[14, 0.8], [16, 3]], case: [[14, 1.6], [16, 4.4]] },
}

const COR_VIA: Record<ClasseVia, { fill: string; case: string }> = {
  mot: { fill: PALETA_PRINT.rodovia, case: PALETA_PRINT.rodoviaContorno },
  trunk: { fill: PALETA_PRINT.rodovia, case: PALETA_PRINT.rodoviaContorno },
  pri: { fill: PALETA_PRINT.avenida, case: PALETA_PRINT.avenidaContorno },
  sec: { fill: PALETA_PRINT.coletora, case: PALETA_PRINT.coletoraContorno },
  minor: { fill: PALETA_PRINT.rua, case: PALETA_PRINT.ruaContorno },
  service: { fill: PALETA_PRINT.rua, case: PALETA_PRINT.ruaContorno },
}

/**
 * `road_pri_case_noramp` -> { classe: 'pri', parte: 'case', tunel: false, alca: false }.
 * `_ramp` são as ALÇAS e acessos (`*_link`): mesma cor da via, largura menor.
 */
export function classeDaVia(
  id: string,
): { classe: ClasseVia; parte: 'fill' | 'case'; tunel: boolean; alca: boolean } | null {
  const m = /^(road|bridge|tunnel)_(mot|trunk|pri|sec|minor|service)_(case|fill)(?:_(ramp|noramp))?(?:_|$)/.exec(id)
  if (!m) return null
  return { classe: m[2] as ClasseVia, parte: m[3] as 'fill' | 'case', tunel: m[1] === 'tunnel', alca: m[4] === 'ramp' }
}

/**
 * Quanto da largura da via a ALÇA leva. Com a largura cheia, um trevo virava uma mancha do
 * tamanho da pista e a hierarquia rodovia > acesso sumia (achado da revisão de 10/11/2026).
 */
export const FATOR_ALCA = 0.6

/** Interpolação linear de zoom, no formato de expressão do MapLibre. */
function porZoom(paradas: readonly [number, number][]): unknown[] {
  return ['interpolate', ['linear'], ['zoom'], ...paradas.flat()]
}

/** Nome em português quando o OSM tem, senão o nome local — nunca o `name:en` do Voyager. */
const NOME_LOCAL = ['coalesce', ['get', 'name:pt'], ['get', 'name']]

/**
 * Camadas do Voyager que NÃO entram no print: pontos de interesse e número de casa são
 * "dado" que o pedido manda tirar; o topo 3D do prédio só suja a textura.
 */
const CAMADAS_FORA = /^(poi_|housenumber|building-top|water_shadow|watername_ocean|watername_sea|place_(country|continent|state))/

/** Uma camada de estilo do MapLibre, só com o que este módulo lê e escreve. */
export interface CamadaEstilo {
  id: string
  type: string
  source?: string
  'source-layer'?: string
  filter?: unknown
  minzoom?: number
  maxzoom?: number
  paint?: Record<string, unknown>
  layout?: Record<string, unknown>
  [k: string]: unknown
}

export interface EstiloMapa {
  version: number
  sources: Record<string, { type: string; [k: string]: unknown }>
  layers: CamadaEstilo[]
  [k: string]: unknown
}

/** A fonte vetorial do estilo (no Voyager, `protomaps`); `null` se não houver. */
function fonteVetorial(estilo: EstiloMapa): string | null {
  const daCamada = estilo.layers.find((c) => c['source-layer'] === 'landuse')?.source
  if (daCamada) return daCamada
  return Object.entries(estilo.sources).find(([, s]) => s.type === 'vector')?.[0] ?? null
}

/* Classes (`kind`) do uso do solo do CARTO que o Voyager não pinta e o print pinta. */
const KINDS_LAVOURA = ['farmland', 'farmyard', 'orchard', 'vineyard', 'plant_nursery', 'greenhouse_horticulture']
const KINDS_ROCHA = ['bare_rock', 'sand', 'beach', 'scree', 'quarry']
const KINDS_ALAGADO = ['wetland', 'marsh', 'swamp']

/** Ids das camadas de chão que o print ACRESCENTA ao Voyager. */
export const ID_LAVOURA = 'print_lavoura'
export const ID_URBANO_ESPECIAL = 'print_urbano_especial'

/** Repinta UMA camada do Voyager pela paleta do print. Devolve a camada (nova) ou `null` para tirar. */
function realcarCamada(c: CamadaEstilo): CamadaEstilo | null {
  if (CAMADAS_FORA.test(c.id)) return null
  const paint = { ...(c.paint ?? {}) }
  const layout = { ...(c.layout ?? {}) }
  const nova: CamadaEstilo = { ...c, paint, layout }

  const via = classeDaVia(c.id)
  if (via) {
    const larg = LARGURAS[via.classe]
    const cor = COR_VIA[via.classe]
    paint['line-color'] = via.tunel ? (via.parte === 'case' ? cor.case : '#f4f2ee') : cor[via.parte]
    const paradas = via.alca
      ? larg[via.parte].map(([z, w]) => [z, Math.round(w * FATOR_ALCA * 100) / 100] as [number, number])
      : larg[via.parte]
    paint['line-width'] = porZoom(paradas)
    paint['line-opacity'] = 1
    // A rua local do Voyager só ganha preenchimento no 15 (antes, o "contorno" faz as vezes
    // de rua, em branco). Aqui contorno e miolo nascem juntos, no zoom da classe.
    nova.minzoom = Math.min(c.minzoom ?? larg.minzoom, larg.minzoom)
    return nova
  }

  switch (c.id) {
    case 'background':
      paint['background-color'] = PALETA_PRINT.fundo
      return nova
    case 'landcover':
    case 'park_national_park':
    case 'park_nature_reserve':
    case 'landuse':
      // Mata fechada num verde, campo/pasto/gramado noutro mais claro: é o que separa a
      // serra do pasto na foto. O resto da lista do Voyager (parque, jardim...) fica no meio.
      paint['fill-color'] = [
        'match',
        ['get', 'kind'],
        ['wood', 'forest', 'nature_reserve', 'national_park'],
        PALETA_PRINT.vegetacao,
        ['grass', 'meadow', 'scrub', 'heath', 'grassland'],
        PALETA_PRINT.campo,
        PALETA_PRINT.vegetacao,
      ]
      paint['fill-opacity'] = c.id === 'park_national_park' || c.id === 'park_nature_reserve' ? 0.55 : 1
      return nova
    case 'landuse_residential':
      paint['fill-color'] = PALETA_PRINT.urbano
      paint['fill-opacity'] = 1
      nova.minzoom = Math.min(c.minzoom ?? 6, 6)
      return nova
    case 'building':
      paint['fill-color'] = PALETA_PRINT.predio
      paint['fill-opacity'] = 0.9
      return nova
    case 'water':
      paint['fill-color'] = PALETA_PRINT.agua
      return nova
    case 'waterway':
      paint['line-color'] = PALETA_PRINT.rio
      paint['line-width'] = porZoom([[8, 1], [11, 1.8], [13, 2.6], [15, 4], [17, 6]])
      return nova
    case 'rail':
    case 'tunnel_rail':
      paint['line-color'] = PALETA_PRINT.ferrovia
      return nova
    case 'boundary_county':
      paint['line-color'] = PALETA_PRINT.limite
      return nova
  }

  if (c.type === 'symbol') {
    if (JSON.stringify(layout['text-field'] ?? '').includes('name')) layout['text-field'] = NOME_LOCAL
    if (/^water/.test(c.id)) {
      paint['text-color'] = PALETA_PRINT.rotuloAgua
      paint['text-halo-color'] = PALETA_PRINT.halo
      paint['text-halo-width'] = 1.4
    } else if (/^roadname/.test(c.id)) {
      paint['text-color'] = PALETA_PRINT.rotuloRua
      paint['text-halo-color'] = PALETA_PRINT.halo
      paint['text-halo-width'] = 1.6
      // Nome de avenida aparece um zoom antes do Voyager: no raio de 1 km o print fica
      // por volta do 14, e é nessa faixa que o operador procura "qual avenida é essa".
      if (c.id === 'roadname_pri' || c.id === 'roadname_major') nova.minzoom = Math.min(c.minzoom ?? 13, 12.5)
      if (c.id === 'roadname_sec') nova.minzoom = Math.min(c.minzoom ?? 15, 14)
      if (c.id === 'roadname_minor') nova.minzoom = Math.min(c.minzoom ?? 16, 15)
    } else if (/^place_/.test(c.id)) {
      paint['text-color'] = PALETA_PRINT.rotuloLugar
      paint['text-halo-color'] = PALETA_PRINT.halo
      paint['text-halo-width'] = 1.6
    }
  }
  return nova
}

/**
 * O Voyager REALÇADO para o print. Não muta a entrada.
 *
 * Além de repintar (`realcarCamada`), REORDENA e ACRESCENTA o chão:
 *   fundo -> lavoura (nova) -> urbano residencial -> urbano especial (nova) -> vegetação ...
 * A vegetação fica POR CIMA do urbano para a praça e o parque dentro do bairro seguirem
 * verdes (no OSM o polígono residencial costuma cobri-los). Sem a fonte vetorial no estilo
 * (CARTO mudou o formato), as duas camadas novas não entram e o resto segue valendo.
 */
export function realcarEstilo(base: EstiloMapa): EstiloMapa {
  const camadas = base.layers.map(realcarCamada).filter((c): c is CamadaEstilo => c != null)
  const fonte = fonteVetorial(base)

  const residencial = camadas.findIndex((c) => c.id === 'landuse_residential')
  const urbano = residencial >= 0 ? camadas.splice(residencial, 1)[0] : null
  const chao: CamadaEstilo[] = []
  if (fonte) {
    chao.push({
      id: ID_LAVOURA,
      type: 'fill',
      source: fonte,
      'source-layer': 'landuse',
      filter: ['in', ['get', 'kind'], ['literal', [...KINDS_LAVOURA, ...KINDS_ROCHA, ...KINDS_ALAGADO]]],
      paint: {
        'fill-color': [
          'match',
          ['get', 'kind'],
          KINDS_ROCHA,
          PALETA_PRINT.rocha,
          KINDS_ALAGADO,
          PALETA_PRINT.alagado,
          PALETA_PRINT.lavoura,
        ],
        'fill-opacity': 1,
      },
    })
  }
  if (urbano) chao.push(urbano)
  if (fonte) {
    chao.push({
      id: ID_URBANO_ESPECIAL,
      type: 'fill',
      source: fonte,
      'source-layer': 'landuse',
      filter: ['in', ['get', 'kind'], ['literal', ['commercial', 'industrial', 'retail', 'railway', 'school', 'university', 'college', 'hospital', 'military', 'garages']]],
      minzoom: 9,
      paint: { 'fill-color': PALETA_PRINT.urbanoEspecial, 'fill-opacity': 1 },
    })
  }
  const fundo = camadas.findIndex((c) => c.type === 'background')
  camadas.splice(fundo + 1, 0, ...chao)

  return { ...base, layers: camadas }
}

// ---------------------------------------------------------------------------
// O alcance desenhado no próprio mapa
// ---------------------------------------------------------------------------

/** Ids da fonte e das camadas do alcance — ficam POR CIMA do fundo, rótulos inclusos. */
export const FONTE_ALCANCE = 'print_alcance'

/**
 * As camadas do contorno: um véu azul quase transparente por dentro (só para a isócrona,
 * de forma irregular, ler como "área"), um halo branco e a linha azul — a do mapa de
 * referência. O véu entra ABAIXO dos rótulos (`antesDe`); as linhas, no topo.
 */
export function camadasDoAlcance(): { veu: CamadaEstilo; halo: CamadaEstilo; linha: CamadaEstilo } {
  return {
    veu: {
      id: 'print_alcance_veu',
      type: 'fill',
      source: FONTE_ALCANCE,
      paint: { 'fill-color': PALETA_PRINT.alcance, 'fill-opacity': 0.06 },
    },
    halo: {
      id: 'print_alcance_halo',
      type: 'line',
      source: FONTE_ALCANCE,
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: { 'line-color': PALETA_PRINT.halo, 'line-width': 7, 'line-opacity': 0.85 },
    },
    linha: {
      id: 'print_alcance_linha',
      type: 'line',
      source: FONTE_ALCANCE,
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: { 'line-color': PALETA_PRINT.alcance, 'line-width': 3.2 },
    },
  }
}

/** O alcance como FeatureCollection GeoJSON (um MultiPolygon). */
export function geojsonDoAlcance(poligonos: readonly Posicao[][][]): {
  type: 'FeatureCollection'
  features: { type: 'Feature'; properties: Record<string, never>; geometry: { type: 'MultiPolygon'; coordinates: Posicao[][][] } }[]
} {
  return {
    type: 'FeatureCollection',
    features: poligonos.length
      ? [{ type: 'Feature', properties: {}, geometry: { type: 'MultiPolygon', coordinates: poligonos.map((p) => p.map((a) => [...a])) } }]
      : [],
  }
}

// ---------------------------------------------------------------------------
// O pin e o nome do lugar — DENTRO do mapa
// ---------------------------------------------------------------------------

/** Fonte GeoJSON do ponto e id da imagem do pin. */
export const FONTE_PONTO = 'print_ponto'
export const IMAGEM_PIN = 'print_pin'

/**
 * Geometria do pin, em px CSS: largura e altura da imagem, e a folga que a sombra ocupa
 * ABAIXO da ponta (a imagem é ancorada pela base e descida dessa folga, para a PONTA cair
 * exatamente na coordenada).
 */
export const PIN = Object.freeze({ largura: 36, altura: 52, sombraAbaixo: 4, raio: 13, haste: 34 })

/** A fonte de rótulo do Voyager (as fontes do CARTO só servem as pilhas que o estilo usa). */
const FONTE_ROTULO_PADRAO = ['Montserrat SemiBold', 'Open Sans Bold', 'Noto Sans Regular', 'Noto Sans CJK JP Regular']

/** A pilha de fonte em negrito que o próprio estilo já usa (senão a do Voyager de hoje). */
export function fonteDeRotulo(estilo: EstiloMapa): string[] {
  for (const c of estilo.layers) {
    const f = c.layout?.['text-font']
    if (Array.isArray(f) && typeof f[0] === 'string' && /SemiBold|Bold/.test(f[0]) && !/Italic/.test(f[0])) return f as string[]
  }
  return FONTE_ROTULO_PADRAO
}

/** O ponto como GeoJSON, com o nome que o rótulo mostra. */
export function geojsonDoPonto(lat: number, lng: number, rotulo: string) {
  return {
    type: 'FeatureCollection' as const,
    features: [{ type: 'Feature' as const, properties: { rotulo }, geometry: { type: 'Point' as const, coordinates: [lng, lat] } }],
  }
}

/**
 * A camada do pin + nome. Por que no MAPA e não pintada por cima depois: o MapLibre dá
 * PRIORIDADE de colisão aos símbolos das camadas de cima. Com o pin e o nome como a última
 * camada, o rótulo do bairro ou da cidade que cairia embaixo deles some, em vez de
 * aparecer atravessado (era o que acontecia com "TERESÓPOLIS" e "RIO VERDE" no primeiro
 * corte, quando o nome era desenhado no canvas por cima do mapa pronto).
 */
export function camadaDoPonto(fonte: string[]): CamadaEstilo {
  return {
    id: 'print_ponto',
    type: 'symbol',
    source: FONTE_PONTO,
    layout: {
      'icon-image': IMAGEM_PIN,
      'icon-anchor': 'bottom',
      'icon-offset': [0, PIN.sombraAbaixo],
      'icon-allow-overlap': true,
      'icon-ignore-placement': false,
      'text-field': ['get', 'rotulo'],
      'text-font': fonte,
      'text-size': 16,
      'text-anchor': 'top',
      'text-offset': [0, 0.55],
      'text-allow-overlap': true,
      'text-ignore-placement': false,
      'text-max-width': 30,
    },
    paint: {
      'text-color': '#1f2a37',
      'text-halo-color': PALETA_PRINT.halo,
      'text-halo-width': 2.2,
    },
  }
}

/** Id da primeira camada de rótulo: o véu do alcance entra antes dela. */
export function primeiraCamadaDeRotulo(estilo: EstiloMapa): string | undefined {
  return estilo.layers.find((c) => c.type === 'symbol')?.id
}
