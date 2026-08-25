/**
 * Captura do mapa como imagem, para o mapa entrar no PDF.
 *
 * POR QUE PRINT, E NAO RENDER NO SERVIDOR. O motor tem um renderizador de mapa (o do
 * Relatorio Pontual), mas ele foi feito para o raio de 1 km de um PONTO: medido em
 * 2026-08-13, gasta ~7,8 s so' carregando os setores censitarios de UMA coordenada, e com
 * o raio dele um hexagono de ~5 km2 sai praticamente vazio — dos 6 concorrentes do
 * entorno, 5 ficavam fora do circulo. Capturar a tela custa perto de zero, enquadra o que
 * o operador escolheu e garante que o relatorio mostre EXATAMENTE o que ele viu, que e' a
 * classe de divergencia que este ciclo passou o dia inteiro corrigindo.
 *
 * DOIS CANVAS, NAO UM. O mapa e' `<DeckGL><Map/></DeckGL>`: o basemap do MapLibre pinta
 * num canvas e as camadas do deck.gl noutro, empilhados. Capturar so' um devolve ou ruas
 * sem hexagono, ou hexagono flutuando no vazio.
 */

/**
 * Um quadro a capturar: o hexagono a enquadrar e, no modo de imovel, ONDE ele esta'.
 *
 * A coordenada existe porque um hexagono res-7 tem ~5 km2 e cabe mais de um endereco
 * dentro: sem a marca, tres imoveis do mesmo bairro produziam tres fotos parecidas e
 * nenhuma dizia qual ponto era o assunto daquela coluna do deck.
 */
export interface AlvoCaptura {
  hexId: string
  lat?: number | null
  lng?: number | null
}

/**
 * Empilha os canvas do mapa num so', na ORDEM EM QUE APARECEM.
 *
 * A ordem e' a do DOM, que e' a ordem de pintura: basemap primeiro, camadas por cima.
 * Inverte-la esconderia o mapa sob as ruas.
 *
 * Canvas de tamanho zero e' PULADO em vez de derrubar a captura: durante o remount que
 * liga o `preserveDrawingBuffer` um dos dois pode ser medido antes de existir de fato.
 *
 * Devolve `null` quando nao ha' nada capturavel — melhor um slide sem mapa, declarando a
 * ausencia, do que um retangulo preto no meio do relatorio.
 */
export function comporCanvas(
  fontes: readonly HTMLCanvasElement[],
  destino: HTMLCanvasElement,
  {
    tipo = 'image/png',
    qualidade,
    recortar = false,
  }: { tipo?: string; qualidade?: number; recortar?: boolean } = {},
): string | null {
  const uteis = fontes.filter((c) => c.width > 0 && c.height > 0)
  if (!uteis.length) return null

  const largura = Math.max(...uteis.map((c) => c.width))
  const altura = Math.max(...uteis.map((c) => c.height))
  if (!(largura > 0) || !(altura > 0)) return null

  const corte = recortar ? recorteCentral(largura, altura) : null
  destino.width = corte ? corte.lado : largura
  destino.height = corte ? corte.lado : altura
  const ctx = destino.getContext('2d')
  if (!ctx) return null

  for (const fonte of uteis) {
    // Cada canvas e' esticado para o quadro comum: com `devicePixelRatio` diferente entre
    // eles (acontece em tela externa), empilhar 1:1 desalinharia as camadas.
    if (corte) {
      // Recorte CENTRADO porque a camera acabou de voar ao centroide do hexagono: o
      // alvo esta' no meio do quadro por construcao. Desenha-se a janela recortada de
      // cada fonte, redimensionada para o quadro comum — a mesma normalizacao de
      // `devicePixelRatio` do caminho sem recorte.
      // Escala POR EIXO. Usar a horizontal nos dois desalinharia a janela recortada
      // assim que as fontes divergissem de proporcao — e a divergencia de proporcao e'
      // justamente o caso que o quadro comum existe para absorver.
      const ex = fonte.width / largura
      const ey = fonte.height / altura
      ctx.drawImage(
        fonte,
        corte.x * ex,
        corte.y * ey,
        corte.lado * ex,
        corte.lado * ey,
        0,
        0,
        corte.lado,
        corte.lado,
      )
    } else {
      ctx.drawImage(fonte, 0, 0, largura, altura)
    }
  }
  return destino.toDataURL(tipo, qualidade)
}

/**
 * Quanto do lado menor do quadro o RECORTE aproveita.
 *
 * O mapa da tela e' uma faixa larga (o painel come a direita), e o hexagono, um miolo no
 * centro dela. Mandar a faixa inteira para o PDF entregava "o mapa todo": a area
 * comparada virava um detalhe e as tres colunas do slide gastavam largura com territorio
 * que ninguem esta' comparando (Juan, 2026-08-19).
 */
export const FATOR_RECORTE = 0.92

/**
 * Quanto do RECORTE o hexagono deve ocupar.
 *
 * Nem 1,0 nem perto: o entorno imediato e' parte da leitura — sao os concorrentes de
 * fora da celula que explicam a disputa. Sobra de ~20% em volta e' o que mostra a
 * vizinhanca sem transformar o hexagono num carimbo.
 */
export const OCUPACAO_DO_HEXAGONO = 0.78

/** Janela quadrada no centro do quadro. Ver `FATOR_RECORTE`. */
export function recorteCentral(
  largura: number,
  altura: number,
): { x: number; y: number; lado: number } {
  const lado = Math.round(Math.min(largura, altura) * FATOR_RECORTE)
  return { x: Math.round((largura - lado) / 2), y: Math.round((altura - lado) / 2), lado }
}

/**
 * Lado do tile sobre o qual a escala de zoom e' definida.
 *
 * 512, e nao 256. O `zoom` que este modulo calcula vai para o `setView` do deck.gl, e o
 * `@math.gl/web-mercator` que fica por baixo dele declara `TILE_SIZE = 512` — a mesma
 * convencao do MapLibre, ja' registrada em `lib/exec.ts`. Com o 256 do slippy map
 * classico a conta devolve um zoom UM NIVEL acima do certo, e o hexagono, que deveria
 * preencher 78% do recorte, sai com ~156% dele: cortado nas duas laterais, que e' o
 * oposto do que este enquadramento existe para fazer.
 */
const LADO_DO_TILE = 512

/** Circunferencia equatorial da Terra, em metros (WGS84). */
const CIRCUNFERENCIA_M = 40_075_016.686

/** Metros por pixel do Web Mercator, no zoom e na latitude dados. */
export function metrosPorPixel(latitude: number, zoom: number): number {
  const escala = LADO_DO_TILE * 2 ** zoom
  return (CIRCUNFERENCIA_M * Math.cos((latitude * Math.PI) / 180)) / escala
}

/**
 * A maior travessia do anel do hexagono, em METROS.
 *
 * Sai do proprio contorno (`cellToBoundary`) e nao de uma constante por resolucao: o
 * mapa ja' desenha res-7 hoje e a conta continua valendo se um dia desenhar outra.
 */
export function larguraDoAnel(anel: readonly (readonly [number, number])[]): number {
  if (anel.length < 2) return 0
  const lats = anel.map(([lat]) => lat)
  const lngs = anel.map(([, lng]) => lng)
  const latMedia = (Math.max(...lats) + Math.min(...lats)) / 2
  const alturaM = (Math.max(...lats) - Math.min(...lats)) * 110_574
  const larguraM =
    (Math.max(...lngs) - Math.min(...lngs)) * 111_320 * Math.cos((latMedia * Math.PI) / 180)
  return Math.max(alturaM, larguraM)
}

/** Piso e teto do zoom de captura: fora disto o basemap perde tile ou vira textura. */
export const ZOOM_CAPTURA_MIN = 10
export const ZOOM_CAPTURA_MAX = 16.5

/**
 * Zoom em que o hexagono preenche `OCUPACAO_DO_HEXAGONO` do recorte.
 *
 * Substitui o `13.2` fixo que estava aqui. Em zoom fixo o enquadramento dependia do
 * tamanho da janela e nunca do hexagono: uma celula res-7 (~2,9 km de travessia, lat
 * -23,5) sai com ~380 px no zoom 13,2, o que e' 42% da altura de uma janela de 900 px e
 * 24% da largura de 1.600 — um miolo no meio de uma faixa. O zoom agora e' DERIVADO do
 * que se quer ver, entao o hexagono ocupa a mesma fatia da foto em qualquer tela.
 *
 * `larguraPx`/`alturaPx` sao do CONTEINER em pixels CSS, nao do canvas: o zoom do mapa
 * fala em pixels CSS, e num monitor com `devicePixelRatio` 2 o canvas tem o dobro.
 */
export function zoomQueEnquadra(
  larguraMetros: number,
  latitude: number,
  larguraPx: number,
  alturaPx: number,
): number {
  const lado = Math.min(larguraPx, alturaPx) * FATOR_RECORTE
  const alvoPx = lado * OCUPACAO_DO_HEXAGONO
  if (!(larguraMetros > 0) || !(alvoPx > 0)) return ZOOM_CAPTURA_MIN
  const mpp = larguraMetros / alvoPx
  /* Invertido a partir do `metrosPorPixel`, e nao com a formula repetida aqui: enquanto
     as duas eram copias, um erro de constante ficava INVISIVEL para o teste — ida e volta
     davam certo entre si e erradas contra o mapa. Uma fonte so'. */
  const zoom = Math.log2(metrosPorPixel(latitude, 0) / mpp)
  if (!Number.isFinite(zoom)) return ZOOM_CAPTURA_MIN
  return Math.min(ZOOM_CAPTURA_MAX, Math.max(ZOOM_CAPTURA_MIN, zoom))
}

/**
 * Quanto esperar depois de mandar o mapa voar, antes de capturar.
 *
 * Duas esperas somadas: a animacao do voo e o carregamento dos tiles do novo
 * enquadramento. Capturar antes rende um quadro borrado ou cinza — e como sao ate' 5
 * hexagonos em sequencia, o erro se repetiria em todos.
 *
 * E' folga deliberada, nao medicao: o `idle` do MapLibre nao esta' exposto aqui, e errar
 * para mais custa segundos, enquanto errar para menos custa um relatorio com mapa cinza.
 */
export const ESPERA_VOO_MS = 900
export const ESPERA_TILES_MS = 700

export function esperaDeCaptura(): number {
  return ESPERA_VOO_MS + ESPERA_TILES_MS
}
