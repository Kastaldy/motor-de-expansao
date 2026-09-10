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
 *
 * E A ORDEM DO DOM NAO E' A ORDEM DE PINTURA. O `<DeckGL>` e' o PAI, entao o canvas dele
 * vem ANTES do canvas do `<Map/>` que ele embrulha — `ordenarParaEmpilhar` desfaz isso.
 */

import { cellToBoundary, cellToLatLng, isValidCell } from 'h3-js'

import type { Pins } from './types'

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
  /**
   * De que cidade e' este alvo.
   *
   * O mapa serve UM municipio por vez. Enquanto a captura so' enquadrava hexagono ja'
   * carregado, isto era redundante; desde que a camera voa para fora dele
   * (`quadroDaCaptura`), e' o que permite trazer os concorrentes do entorno CERTO em vez
   * dos da cidade que estava aberta.
   */
  uf?: string | null
  municipio?: string | null
}

/**
 * Empilha os canvas do mapa num so', na ORDEM RECEBIDA.
 *
 * Quem chama e' responsavel pela ordem, e ela e' a de PINTURA: basemap primeiro, camadas
 * por cima. Ate' 10/09/2026 esta nota dizia que a ordem do DOM ja' era essa — nao e', e o
 * modulo passava a lista crua do `querySelectorAll`. Use `ordenarParaEmpilhar`.
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

/** Como o canvas do basemap se identifica no DOM. O MapLibre carimba esta classe nele. */
const CLASSE_DO_BASEMAP = 'maplibregl-canvas'

/**
 * Poe os canvas na ordem de PINTURA: basemap embaixo, camadas do deck.gl por cima.
 *
 * A ordem do DOM e' a INVERSA disso, e foi o que estragou as capturas ate' 10/09/2026. O
 * mapa e' `<DeckGL><Map/></DeckGL>`, entao o canvas do deck (o pai) aparece ANTES do
 * canvas do MapLibre (o filho) no `querySelectorAll` — medido no piloto rodando, com o
 * deck em `deck-events-root` na posicao 0 e o `maplibregl-canvas` na 1. Empilhando nessa
 * ordem, o basemap OPACO era desenhado por ultimo, em cima de tudo: as camadas do deck
 * (alfa medio medido 59,4 de 255) sumiam sob as ruas. O slide "Quem ja disputa o aluno
 * ali" saia com malha viaria e zero pins — a foto negava o proprio assunto dela.
 *
 * A ordem RELATIVA das camadas e' preservada: so' o basemap muda de lugar.
 */
export function ordenarParaEmpilhar(
  canvases: readonly HTMLCanvasElement[],
): HTMLCanvasElement[] {
  const base = canvases.filter((c) => c.className?.includes(CLASSE_DO_BASEMAP))
  const camadas = canvases.filter((c) => !c.className?.includes(CLASSE_DO_BASEMAP))
  return [...base, ...camadas]
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

/**
 * Quanto esperar depois do SALTO, antes de comecar a perguntar se o mapa esta' pronto.
 *
 * A captura NAO anima a camera: ela salta. O voo com `FlyToInterpolator` existe para o
 * operador que esta' olhando a tela, e durante a geracao ninguem esta' — pior, ele
 * introduziu o defeito que custou este ciclo: com a instancia unica de interpolador
 * reaproveitada em sequencia, a transicao entre dois alvos vizinhos virava no-op e a
 * camera NAO SAIA DO LUGAR. Medido em 10/09/2026: `estilo=true tiles=true chegou=false`,
 * com o centro parado no centroide do alvo anterior, 12 s ate' o teto.
 *
 * O piso existe porque, no instante seguinte ao salto, o mapa ainda nao registrou o novo
 * enquadramento e `areTilesLoaded()` responderia `true` sobre o quadro VELHO.
 */
export const ESPERA_APOS_SALTO_MS = 300

/**
 * A camada de pins que a foto DESTE alvo deve usar.
 *
 * `null` significa "nao sobrepoe" — o alvo e' da cidade que o mapa ja' tem aberta, entao os
 * pins da tela ja' sao os dele.
 *
 * O ponto delicado e' a busca que FALHOU. Ela devolvia `null`, e o consumidor faz
 * `pinsDaCaptura ?? pins`: o `null` caia de volta nos pins do municipio CARREGADO, ou seja,
 * uma falha de rede reintroduzia o defeito que este ciclo consertou — concorrente da cidade
 * errada sob o nome certo, que e' pior que concorrente nenhum, porque parece resposta.
 * Agora falha vira camada VAZIA: a foto sai sem pin, e sem pin nao afirma nada.
 * (Achado da revisao automatica do PR #345.)
 */
export function pinsDoAlvo(buscados: Pins | null, mesmaCidade: boolean): Pins | null {
  if (mesmaCidade) return null
  return buscados ?? { concorrentes: [], ultra: [], icones: {} }
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
 * O quadro de UMA captura: onde a camera pousa, e em que zoom.
 *
 * NAO CONSULTA O QUE O MAPA CARREGOU, e e' esse o ponto. Ate' 10/09/2026 o loop de
 * captura achava o centro por `hexes.find(h => h.id === hexId)` sobre a lista que o mapa
 * serve — que e' de UM municipio por vez — e, nao achando, empurrava foto vazia em
 * silencio. Um deck de quatro pontos, dois em Posse/GO e dois em Jatai/GO, saia com mapa
 * so' dos dois do municipio aberto e "Mapa nao capturado para esta area." nos outros
 * dois, como se ninguem disputasse o aluno la'. Centro e travessia saem do PROPRIO id:
 * um hexagono H3 sabe onde fica sem precisar que alguem o tenha carregado.
 *
 * `null` e' "nao ha' o que enquadrar" — id vazio ou malformado —, nunca "o mapa nao
 * tinha esse hexagono".
 *
 * O `isValidCell` NAO e' zelo: o h3-js NAO lanca em id invalido. Medido em 10/09/2026,
 * `cellToLatLng('nao-e-um-hexagono')` devolve 79,24 N / 38,02 E — mar do Artico. Sem a
 * validacao, um `hex_id` corrompido mandaria a camera para la' e o slide traria uma foto
 * de agua vazia, que e' pior que declarar a ausencia: agua vazia parece resposta.
 */
export function quadroDaCaptura(
  hexId: string,
  larguraPx: number,
  alturaPx: number,
): { lat: number; lng: number; zoom: number } | null {
  if (!hexId || !isValidCell(hexId)) return null
  try {
    const [lat, lng] = cellToLatLng(hexId)
    const anel = cellToBoundary(hexId) as [number, number][]
    return {
      lat,
      lng,
      zoom: zoomQueEnquadra(larguraDoAnel(anel), lat, larguraPx, alturaPx),
    }
  } catch {
    // O h3-js lanca em id malformado. Quem nao e' hexagono nao vira quadro.
    return null
  }
}

/**
 * Tolerancia, em GRAUS, para dizer que a camera chegou no alvo.
 *
 * ~0,002 grau e' da ordem de 200 m — folga para o arredondamento do fim do voo, e uma
 * ordem de grandeza menor que a travessia de um hexagono res-7 (~2,9 km), que e' o que a
 * foto enquadra. Serve para aceitar "chegou" sem aceitar "ainda esta' na cidade
 * anterior".
 */
export const TOLERANCIA_ALVO_GRAUS = 0.002

/** A camera esta' parada em cima do alvo? Ver `TOLERANCIA_ALVO_GRAUS`. */
export function chegouNoAlvo(
  centro: { lat: number; lng: number } | null | undefined,
  alvo: { lat: number; lng: number },
  tolerancia: number = TOLERANCIA_ALVO_GRAUS,
): boolean {
  if (!centro) return false
  return (
    Math.abs(centro.lat - alvo.lat) <= tolerancia &&
    Math.abs(centro.lng - alvo.lng) <= tolerancia
  )
}

/** O que se pergunta ao mapa antes de apertar o obturador. */
export interface EstadoDoMapa {
  estiloCarregado: boolean
  tilesCarregados: boolean
  centro: { lat: number; lng: number } | null
}

/**
 * O mapa esta' PRONTO para ser fotografado?
 *
 * Substitui a espera por RELOGIO (900 ms de voo + 700 ms de tiles) que estava aqui. O
 * relogio nao sabe se o mapa acompanhou: medido em 10/09/2026, com a aba estrangulada
 * saiu UMA imagem distinta em quatro — tres colunas do deck com o mesmo quadro de Posse,
 * cada uma sob o nome de outra area —, e na captura 0 o basemap entrou na composicao com
 * 0% de tinta, recem-remontado. Foto do lugar errado SOB O NOME CERTO e' pior que foto
 * nenhuma, e foi por isso que a espera fixa saiu.
 *
 * `alvo` nulo e' a comparacao de HEXAGONOS, que nao marca imovel: ali basta o mapa ter
 * pintado.
 */
export function mapaPronto(
  estado: EstadoDoMapa,
  alvo: { lat: number; lng: number } | null,
  tolerancia: number = TOLERANCIA_ALVO_GRAUS,
): boolean {
  if (!estado.estiloCarregado || !estado.tilesCarregados) return false
  return alvo ? chegouNoAlvo(estado.centro, alvo, tolerancia) : true
}

/**
 * A ORDEM em que a camera visita os alvos: sempre o mais proximo do ultimo visitado.
 *
 * A ordem de captura era a de COLAGEM, e isso e' geografia por acaso. Colar Posse,
 * Jatai, Posse, Jatai fazia a camera atravessar 500 km TRES vezes; por proximidade, o
 * salto longo e' um so'. Cada travessia e' um voo que pode nao chegar dentro do
 * `TETO_PRONTIDAO_MS` — e alvo que nao chega vira coluna sem mapa (medido no deck de
 * 10/09/2026 as 14:10, onde a unica coluna vazia foi justamente a primeira da segunda
 * cidade). Menos travessia, menos chance de perder coluna, e menos segundos de geracao.
 *
 * Devolve INDICES da lista recebida, e nao os alvos reordenados: a imagem de cada area
 * tem de voltar para a posicao dela, que e' por onde o servidor pareia nome e foto.
 *
 * Guloso, e nao a rota otima: com no maximo 5 pontos a diferenca e' nula, e o caixeiro
 * viajante nao paga o proprio custo aqui. Alvo sem quadro (`null`) vai para o fim, sem
 * puxar a rota — nao se voa ate' quem nao tem para onde.
 */
export function ordemDeVoo(
  pontos: readonly ({ lat: number; lng: number } | null)[],
  partida: { lat: number; lng: number } | null,
): number[] {
  const pendentes = pontos.map((_, i) => i).filter((i) => pontos[i] != null)
  const semQuadro = pontos.map((_, i) => i).filter((i) => pontos[i] == null)
  const ordem: number[] = []
  let de = partida
  while (pendentes.length) {
    let melhor = 0
    if (de) {
      let menor = Infinity
      for (let k = 0; k < pendentes.length; k++) {
        const p = pontos[pendentes[k]]!
        // Distancia em graus, sem projecao: aqui so' se COMPARA, nunca se reporta.
        const d = Math.hypot(p.lat - de.lat, p.lng - de.lng)
        if (d < menor) {
          menor = d
          melhor = k
        }
      }
    }
    const i = pendentes.splice(melhor, 1)[0]
    ordem.push(i)
    de = pontos[i]
  }
  return [...ordem, ...semQuadro]
}

/**
 * Teto de espera pela prontidao, por captura. Estourou, a coluna declara a ausencia.
 *
 * 12 s, e nao os 6 s do primeiro corte: no deck de 10/09/2026 os quatro pontos cruzavam
 * ~500 km entre Posse/GO e Jatai/GO, e a PRIMEIRA captura da segunda cidade — voo longo
 * mais tiles de uma praca que o mapa nunca tinha desenhado — nao ficou pronta a tempo. A
 * coluna saiu declarando a ausencia, que e' o comportamento certo com o teto errado. O
 * teto so' custa tempo quando a captura ja' esta' falhando; apertado, ele TRANSFORMA
 * espera em ausencia.
 */
export const TETO_PRONTIDAO_MS = 12_000

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
