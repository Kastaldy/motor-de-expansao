/**
 * Renderiza o PRINT LIMPO do mapa de um ponto (regras em `print-mapa.ts`).
 *
 * Um mapa MapLibre próprio, montado FORA DA TELA num quadro fixo de 1280×720 (densidade 2,
 * sai 2560×1440), com o estilo realçado e o contorno do alcance. Depois que os tiles
 * assentam (`idle`), o canvas dele é copiado para um canvas 2D, onde entram a escala e o
 * crédito do fundo. O pin e o nome do lugar são camada do PRÓPRIO mapa (`camadaDoPonto`),
 * para os rótulos do fundo abrirem espaço para eles. O mapa da tela não é tocado: nada de esconder
 * camada, trocar tema ou mexer na câmera do operador.
 *
 * Este arquivo usa DOM e WebGL, então fica fora do Vitest (que roda em node); o que é
 * regra — enquadramento, escala, paleta, nome do arquivo — mora no módulo puro e é testado.
 */

import maplibregl from 'maplibre-gl'

import {
  ALTURA_PRINT_CSS,
  CREDITO_PRINT,
  DENSIDADE_PRINT,
  ESTILO_BASE_PRINT,
  FONTE_ALCANCE,
  FONTE_PONTO,
  IMAGEM_PIN,
  LARGURA_PRINT_CSS,
  PIN,
  caixaDoPrint,
  camadaDoPonto,
  camadasDoAlcance,
  escalaDoPrint,
  fonteDeRotulo,
  geojsonDoAlcance,
  geojsonDoPonto,
  primeiraCamadaDeRotulo,
  quadroDoPrint,
  realcarEstilo,
  type EstiloMapa,
} from './print-mapa'

/**
 * Erro com mensagem PRONTA para o usuário (em português). O botão mostra a mensagem só
 * destes; qualquer outro erro (do MapLibre, em inglês) vira uma frase genérica.
 */
export class ErroPrint extends Error {}

/** O que o print precisa saber do ponto. */
export interface PedidoPrint {
  lat: number
  lng: number
  /** Polígonos do alcance em `[lng, lat]` (`alcanceDoPrint`). */
  poligonos: [number, number][][][]
  /** Nome do lugar sob o pin ("Várzea · Teresópolis/RJ"); vazio = sem rótulo. */
  rotulo: string
}

/**
 * Teto para o fundo assentar. Folgado de propósito: a primeira imagem de uma região
 * baixa tiles e fontes do zero, e errar para menos troca uma espera por uma falha.
 */
export const TETO_PRINT_MS = 30_000

const FONTE_CANVAS = '"Barlow", "Segoe UI", Roboto, Arial, sans-serif'

/* O estilo-base é baixado UMA vez por sessão; falhou, a próxima tentativa baixa de novo. */
let estiloBase: Promise<EstiloMapa> | null = null

function carregarEstiloBase(): Promise<EstiloMapa> {
  if (!estiloBase) {
    estiloBase = fetch(ESTILO_BASE_PRINT)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json() as Promise<EstiloMapa>
      })
      .catch((e) => {
        estiloBase = null
        console.error('[print-mapa] estilo-base', e)
        throw new ErroPrint('Não foi possível baixar o fundo de ruas (CARTO). Confira a conexão e tente de novo.')
      })
  }
  return estiloBase
}

/**
 * Espera o evento, com teto contado SÓ COM A ABA VISÍVEL. O MapLibre desenha (e dispara
 * `load`/`idle`) dentro do `requestAnimationFrame`, que o navegador suspende na aba oculta:
 * um relógio comum daria "demorou demais" a quem clicou e foi ler outra aba.
 */
function esperar(mapa: maplibregl.Map, evento: 'load' | 'idle', tetoMs: number): Promise<void> {
  return new Promise((resolve, reject) => {
    const passo = 250
    let decorrido = 0
    const t = window.setInterval(() => {
      if (!document.hidden) decorrido += passo
      if (decorrido >= tetoMs) {
        window.clearInterval(t)
        reject(new ErroPrint('O fundo de ruas demorou demais para carregar. Tente de novo em instantes.'))
      }
    }, passo)
    mapa.once(evento, () => {
      window.clearInterval(t)
      resolve()
    })
  })
}

/**
 * Gera o PNG 16:9 do ponto. Rejeita com mensagem em português quando o fundo não carrega
 * — melhor dizer que falhou do que entregar uma imagem cinza que parece resposta.
 */
export async function gerarPrintDoMapa(pedido: PedidoPrint, tetoMs: number = TETO_PRINT_MS): Promise<Blob> {
  const estilo = realcarEstilo(await carregarEstiloBase())
  const caixa = caixaDoPrint(pedido.poligonos, pedido)
  if (!caixa) throw new ErroPrint('O ponto não tem coordenada válida para enquadrar.')
  const quadro = quadroDoPrint(caixa)

  const palco = document.createElement('div')
  Object.assign(palco.style, {
    position: 'fixed',
    left: '-100000px',
    top: '0',
    width: `${LARGURA_PRINT_CSS}px`,
    height: `${ALTURA_PRINT_CSS}px`,
    pointerEvents: 'none',
  })
  palco.setAttribute('aria-hidden', 'true')
  document.body.appendChild(palco)

  let mapa: maplibregl.Map | null = null
  /* Tile ou glifo que falha NÃO impede o `idle`: o MapLibre 5 conta tile com erro como
     "carregado". Sem anotar a falha, o PNG sairia sem ruas e seria baixado como se
     estivesse certo (achado da revisão de 10/11/2026). */
  let falhaDoFundo: unknown = null
  try {
    mapa = criarMapa({
      container: palco,
      // O tipo do estilo do MapLibre é mais estreito que o nosso (que é o JSON baixado).
      style: estilo as unknown as maplibregl.StyleSpecification,
      center: [quadro.centro.lng, quadro.centro.lat],
      zoom: quadro.zoom,
      interactive: false,
      attributionControl: false,
      pixelRatio: DENSIDADE_PRINT,
      fadeDuration: 0,
      canvasContextAttributes: { preserveDrawingBuffer: true, antialias: true },
    })
    mapa.on('error', (ev: { error?: unknown; sourceId?: string }) => {
      // As fontes do PRÓPRIO print são GeoJSON local; a falha que importa é a do fundo:
      // tile vetorial, glifo ou sprite do CARTO.
      if (ev.sourceId === FONTE_ALCANCE || ev.sourceId === FONTE_PONTO) return
      falhaDoFundo = ev.error ?? ev
    })
    await esperar(mapa, 'load', tetoMs)

    const camadas = camadasDoAlcance()
    mapa.addSource(FONTE_ALCANCE, { type: 'geojson', data: geojsonDoAlcance(pedido.poligonos) as GeoJSON.FeatureCollection })
    mapa.addLayer(camadas.veu as unknown as maplibregl.LayerSpecification, primeiraCamadaDeRotulo(estilo))
    mapa.addLayer(camadas.halo as unknown as maplibregl.LayerSpecification)
    mapa.addLayer(camadas.linha as unknown as maplibregl.LayerSpecification)
    mapa.addImage(IMAGEM_PIN, imagemDoPin(), { pixelRatio: DENSIDADE_PRINT })
    mapa.addSource(FONTE_PONTO, { type: 'geojson', data: geojsonDoPonto(pedido.lat, pedido.lng, pedido.rotulo) })
    mapa.addLayer(camadaDoPonto(fonteDeRotulo(estilo)) as unknown as maplibregl.LayerSpecification)
    await esperar(mapa, 'idle', tetoMs)
    if (falhaDoFundo) {
      console.error('[print-mapa] fundo de ruas', falhaDoFundo)
      throw new ErroPrint('Parte do fundo de ruas não carregou (CARTO). Tente de novo em instantes.')
    }

    return await comporImagem(mapa.getCanvas(), quadro.centro.lat, mapa.getZoom())
  } finally {
    mapa?.remove()
    palco.remove()
  }
}

/** O construtor do MapLibre lança em inglês sem WebGL; aqui vira frase para o usuário. */
function criarMapa(opcoes: maplibregl.MapOptions): maplibregl.Map {
  try {
    return new maplibregl.Map(opcoes)
  } catch (e) {
    console.error('[print-mapa] WebGL', e)
    throw new ErroPrint('Este navegador não conseguiu montar o mapa (WebGL indisponível ou desligado).')
  }
}

/** Copia o mapa e desenha a escala e o crédito. Coordenadas em px CSS. */
function comporImagem(fonte: HTMLCanvasElement, latitude: number, zoom: number): Promise<Blob> {
  const W = LARGURA_PRINT_CSS
  const H = ALTURA_PRINT_CSS
  const k = DENSIDADE_PRINT
  const tela = document.createElement('canvas')
  tela.width = W * k
  tela.height = H * k
  const ctx = tela.getContext('2d')
  if (!ctx) return Promise.reject(new ErroPrint('O navegador não deixou montar a imagem.'))
  ctx.drawImage(fonte, 0, 0, W * k, H * k)
  ctx.scale(k, k)

  desenharEscalaECredito(ctx, W, H, latitude, zoom)

  return new Promise((resolve, reject) => {
    tela.toBlob((b) => (b ? resolve(b) : reject(new ErroPrint('O navegador não gerou a imagem.'))), 'image/png')
  })
}

/**
 * O pin em gota, vermelho, como IMAGEM do mapa (na densidade do print). A ponta fica a
 * `PIN.sombraAbaixo` px da base da imagem — a sombra no chão ocupa essa sobra —, e a
 * camada desce a imagem dessa folga para a ponta cair exatamente na coordenada.
 */
function imagemDoPin(): ImageData {
  const k = DENSIDADE_PRINT
  const tela = document.createElement('canvas')
  tela.width = PIN.largura * k
  tela.height = PIN.altura * k
  const ctx = tela.getContext('2d')
  if (!ctx) throw new ErroPrint('O navegador não deixou desenhar o pin.')
  ctx.scale(k, k)
  const x = PIN.largura / 2
  const y = PIN.altura - PIN.sombraAbaixo
  const { raio: r, haste: h } = PIN
  const cy = y - h
  const phi = Math.acos(r / h)

  // Sombra no chão: dá o "pousado" sem esconder a rua por baixo.
  ctx.fillStyle = 'rgba(0, 0, 0, 0.25)'
  ctx.beginPath()
  ctx.ellipse(x, y, 7, 2.6, 0, 0, Math.PI * 2)
  ctx.fill()

  const grad = ctx.createLinearGradient(x, cy - r, x, y)
  grad.addColorStop(0, '#ef3b4c')
  grad.addColorStop(1, '#b3162a')
  ctx.fillStyle = grad
  ctx.beginPath()
  ctx.moveTo(x, y)
  ctx.arc(x, cy, r, Math.PI / 2 + phi, Math.PI / 2 - phi + Math.PI * 2)
  ctx.closePath()
  ctx.fill()
  ctx.lineWidth = 1.4
  ctx.strokeStyle = '#7f0e1c'
  ctx.stroke()

  ctx.fillStyle = '#ffffff'
  ctx.beginPath()
  ctx.arc(x, cy, 5, 0, Math.PI * 2)
  ctx.fill()
  return ctx.getImageData(0, 0, tela.width, tela.height)
}

/** Escala gráfica e crédito no canto inferior direito, como no mapa de referência. */
function desenharEscalaECredito(ctx: CanvasRenderingContext2D, W: number, H: number, latitude: number, zoom: number): void {
  const escala = escalaDoPrint(latitude, zoom)
  const margem = 18
  ctx.save()

  // Crédito (obrigação de licença do fundo).
  ctx.font = `500 11px ${FONTE_CANVAS}`
  ctx.textAlign = 'right'
  ctx.textBaseline = 'bottom'
  ctx.lineJoin = 'round'
  ctx.lineWidth = 3
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.9)'
  ctx.strokeText(CREDITO_PRINT, W - margem, H - 10)
  ctx.fillStyle = '#4b5563'
  ctx.fillText(CREDITO_PRINT, W - margem, H - 10)

  // Caixa da escala, acima do crédito.
  const larguraCaixa = escala.px + 70
  const alturaCaixa = 26
  const xCaixa = W - margem - larguraCaixa
  const yCaixa = H - 32 - alturaCaixa
  ctx.fillStyle = 'rgba(255, 255, 255, 0.92)'
  ctx.strokeStyle = 'rgba(31, 42, 55, 0.25)'
  ctx.lineWidth = 1
  ctx.beginPath()
  ctx.roundRect(xCaixa, yCaixa, larguraCaixa, alturaCaixa, 5)
  ctx.fill()
  ctx.stroke()

  const xBarra = xCaixa + 10
  const yBarra = yCaixa + alturaCaixa / 2 + 4
  ctx.strokeStyle = '#1f2a37'
  ctx.lineWidth = 2
  ctx.beginPath()
  ctx.moveTo(xBarra, yBarra - 7)
  ctx.lineTo(xBarra, yBarra)
  ctx.lineTo(xBarra + escala.px, yBarra)
  ctx.lineTo(xBarra + escala.px, yBarra - 7)
  ctx.stroke()

  ctx.font = `600 12px ${FONTE_CANVAS}`
  ctx.textAlign = 'left'
  ctx.textBaseline = 'middle'
  ctx.fillStyle = '#1f2a37'
  ctx.fillText(escala.rotulo, xBarra + escala.px + 8, yCaixa + alturaCaixa / 2)
  ctx.restore()
}
