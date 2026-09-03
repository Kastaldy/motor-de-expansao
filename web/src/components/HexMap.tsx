import { FlyToInterpolator, type Layer } from '@deck.gl/core'
import { H3HexagonLayer } from '@deck.gl/geo-layers'
import { IconLayer, LineLayer, PolygonLayer, ScatterplotLayer, TextLayer } from '@deck.gl/layers'
import DeckGL from '@deck.gl/react'
import { cellToBoundary, cellToLatLng } from 'h3-js'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Map } from 'react-map-gl/maplibre'
import 'maplibre-gl/dist/maplibre-gl.css'

import {
  type AlvoCaptura,
  ESPERA_VOO_MS,
  comporCanvas,
  esperaDeCaptura,
  larguraDoAnel,
  zoomQueEnquadra,
} from '../lib/captura-mapa'
import { CORES_IDENTIDADE, corDeIdentidadeRgb, rotuloDoHex } from '../lib/comparacao'
import { alunos, brl, distanciaCurta, num, renda } from '../lib/format'
import {
  type AlvoMedicao,
  distanciaMetros,
  metrosPorPixel,
  travarNoAlvo,
} from '../lib/medicao'
import { corTipo, corTipoRgb, custoOcup, labelTipo, rsM2 } from '../lib/imovel'
import { sinaisDoRegime } from '../lib/sinais'
import {
  DISCARDED_FILL,
  faixaM1ToColor,
  HEX_FILL_ALPHA,
  NAN_SCORE_FILL,
  POP_MIN_ACIONAVEL,
  camadaCor,
  scoreBandToColor,
  crescClasseToColor,
  type RGBA,
} from '../lib/colors'
import { perfilDoCliente } from '../lib/perfil'
import type { Tema } from '../lib/tema'
import type {
  Cobertura1k,
  CrescimentoMunicipal,
  Hex,
  Oportunidade,
  Passo,
  PecaCobertura,
  Pin,
  PinIndependente,
  Pins,
} from '../lib/types'

/** Objeto de ícone do deck.gl a partir de um data URI (bandeira quadrada). */
interface IconeDeck {
  url: string
  width: number
  height: number
  anchorX: number
  anchorY: number
  mask: boolean
}
function iconeDeck(url: string): IconeDeck {
  return { url, width: 128, height: 128, anchorX: 64, anchorY: 64, mask: false }
}

// Logo do WellHub para os pins de academias INDEPENDENTES (todas vem do feed do WellHub).
// Identidade de modulo (estavel) -> nao dispara re-pack do atlas. So' as independentes usam
// esta marca; as unidades de REDE seguem com a bandeira propria (iconObjs por rede em `conc-pins`).
const ICONE_WELLHUB: IconeDeck = iconeDeck('/logo-wellhub.png')

/* Icones de FOTO, um por unidade sem marca — memoizados por arquivo.
   Passa pelo MESMO `iconeDeck` das marcas, e isso nao e' cosmetico: sem `anchorX/anchorY`
   o deck.gl ancora no rodape da imagem e o pino sai deslocado meio icone; sem `mask: false`
   ele pinta a imagem com `getColor` em vez de mostra-la.
   E o objeto precisa ser ESTAVEL entre renders: devolver um literal novo a cada chamada de
   `getIcon` faz o atlas ser reempacotado a cada quadro. */
/* Objeto simples, e nao `Map`: neste arquivo `Map` e' o componente do `react-map-gl`
   (import no topo), que sombreia o `Map` do JS. */
const _fotoIcones: Record<string, IconeDeck> = {}
function iconeDaFoto(arquivo: string): IconeDeck {
  const ic =
    _fotoIcones[arquivo] ??
    (_fotoIcones[arquivo] = iconeDeck(`/api/pin-concorrente/${encodeURIComponent(arquivo)}`))
  return ic
}

/* ---------------------------------------------------------------------------
   Mapa de hexagonos H3 res-7 sobre basemap MapLibre.

   Coloracao FIEL ao dashboard Streamlit (CLAUDE.md §5): faixas de 10 pontos via
   RESIDUAL_SCORE_BANDS (score_band_to_color), corte de <5k hab em cinza e score
   NaN com fill proprio. A opacidade e mais baixa que a do dashboard para as ruas
   do basemap respirarem por baixo (pedido do Felipe).

   Basemap CARTO (online, fallback ao gradiente se faltar rede): Dark Matter no tema
   escuro, Positron no claro.
   --------------------------------------------------------------------------- */

/* --- O que o tema muda AQUI dentro -----------------------------------------
   Este arquivo pinta em dois motores que NAO leem `var()`: o deck.gl (WebGL, cor em
   [r,g,b,a]) e o MapLibre (estilo por URL). Entao o tema, que no resto do app viaja
   pela cascata de CSS, aqui tem de chegar como VALOR. E' a mesma razao do
   `useCoresDaSeveridade` no ExecMap — a diferenca e' que la' os tokens sao lidos do
   DOM, e aqui a paleta e' curta e fixa o bastante para viver como tabela.

   Dark Matter e Positron sao o par claro/escuro do MESMO desenho cartografico da CARTO:
   ruas, rotulos e hierarquia de vias ficam onde estavam, so' a pele muda.

   O que NAO esta aqui, de proposito:
     · a rampa de score (SCORE_BANDS_HEX) — e' porte 1:1 de `RESIDUAL_SCORE_BANDS`, a
       mesma regua do dashboard e do PDF. Trocar matiz por tema faria o mapa discordar
       do relatorio impresso. So' o ALPHA muda (ver `alphaHex`).
     · o chip do rotulo de rank — escuro nos DOIS temas, porque ele pousa em cima da
       rampa inteira (do vermelho ao verde) e e' o fundo dele que garante o contraste
       do numero, nao o basemap.
     · a linha fina neutra do hexagono e a sombra do concorrente — ambas sao tinta
       ESCURA de baixo alfa, e escurecer funciona sobre os dois basemaps.
   --------------------------------------------------------------------------- */
interface PeleDoMapa {
  basemap: string
  /** Contorno do hex SELECIONADO e do hex do endereco buscado. Contrario do basemap. */
  selecao: RGBA
  /** `highlightColor` do deck.gl: o veu de hover sobre o hexagono. */
  realce: RGBA
  /** Preenchimento do hex do endereco buscado (mesma cor da selecao, bem transparente). */
  selecaoTenue: RGBA
  /** Anel e miolo do pin de endereco — a rosca inverte junto com o fundo. */
  pinAnel: RGBA
  pinMiolo: RGBA
  /**
   * Alpha do preenchimento dos hexes.
   *
   * No escuro sao 115, mais baixo que os 170 do dashboard, para as ruas do Dark Matter
   * respirarem por baixo (pedido do Felipe). No claro isso nao se sustenta: sobre o
   * Positron, 115 lava a rampa inteira em pastel — #EEC828 vira (247,230,158), quase
   * o branco do papel, e o verde e o vermelho param de se distinguir num relance.
   * O claro volta aos 170 CANONICOS do dashboard, e nao a um numero inventado: o
   * Positron e' claro o bastante para as ruas sobreviverem a essa tinta.
   */
  alphaHex: number
}

const PELE: Record<Tema, PeleDoMapa> = {
  escuro: {
    basemap: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
    selecao: [238, 243, 248, 255],
    realce: [236, 240, 245, 40],
    selecaoTenue: [238, 243, 248, 45],
    pinAnel: [255, 255, 255, 240],
    pinMiolo: [8, 11, 16, 255],
    alphaHex: HEX_FILL_ALPHA,
  },
  claro: {
    basemap: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
    // Espelhos de --tx-max e --ac do bloco [data-tema='claro'] (styles/tokens.css).
    // Ao mexer la', mexa aqui: o contorno da selecao no mapa e o item ativo do painel
    // dizem a MESMA coisa, e divergir faria a tela se contradizer.
    selecao: [11, 18, 25, 255],
    realce: [11, 18, 25, 36],
    selecaoTenue: [11, 18, 25, 45],
    pinAnel: [11, 18, 25, 240],
    pinMiolo: [255, 255, 255, 255],
    alphaHex: 170,
  },
}

const FLY = new FlyToInterpolator({ speed: 1.6 })

/**
 * Zoom em que UM hexagono res-7 domina a tela — o enquadramento de "olhar este ponto".
 * E' o mesmo piso que os voos automaticos ja usavam; virou constante para os tres
 * lugares que decidem camera (estado inicial, voo do centro, voo do pin) nao poderem
 * divergir em silencio.
 */
const ZOOM_DO_HEXAGONO = 13
/** Cidade inteira na tela: o padrao de quem abriu um municipio para explorar. */
const ZOOM_DO_MUNICIPIO = 9.6

export interface SearchPin {
  lat: number
  lng: number
  hexId: string
}

/** Capacidade de referencia do score residual no motor
 *  (`SCORE_RESIDUAL_CAPACIDADE_REFERENCIA`): score = 100 * residual / 2500, clip 0-100. */
const CAPACIDADE_REF = 2500

function scoreDoPasso(h: Hex, passoN: number, raio1km = false): number | null {
  if (passoN === 1) return h.censo // score_setor_2022_calibrado
  if (passoN === 5) return h.m1 // score_priorizacao
  /* Com o raio ligado, o score residual sai do MODELO NOVO. Sem isto o mapa misturava
     duas reguas: os hexagonos que alguma concorrente alcanca apareciam recortados com o
     score novo, e todos os outros continuavam com o score de 2 km — cores incongruentes
     lado a lado, medindo coisas diferentes. */
  if (raio1km && h.oferta1k != null) {
    return Math.max(0, Math.min(100, (100 * h.oferta1k) / CAPACIDADE_REF))
  }
  return h.res // score_oportunidade_residual
}

/* A camada 5 ("Para onde crescer") pinta pela FAIXA DE OPORTUNIDADE do M1, nao
   pelo score (BLK-MAPA-FAIXAS-01). Motivo: `faixa_oportunidade` sai de um corte
   sobre `score_percentil_nacional` ([35,50,65,80] em
   `m1/hex_enrichment._definir_faixa_oportunidade`), NAO sobre `score_priorizacao`,
   que era o que pintava aqui. Com a legenda nomeada, manter a cor pelo score
   afirmaria que score 70 = "Alta", o que nao e' verdade. `Hex.faixa` ja chega
   pronta do backend, entao a cor passa a bater exatamente com o rotulo.
   READ-ONLY sobre o M1: so exibicao, nada e' recalculado. */
const PASSO_POR_FAIXA_M1 = 5

/** Opacidade relativa dos hexes FORA do passo atual. O funil vira um holofote nos
 *  hexes da camada — sem precisar de borda colorida (pedido do Felipe: tirar as
 *  bordas azuis). Sem isso, as 10 aberturas do passo 5 sumiriam no meio do mapa. */
const DIM_FORA_DO_PASSO = 0.5

/* Onde a REGUA DO RESIDUAL vale: 2 (Demanda nao atendida) e 3 (Pressao concorrencial).
   So' nestes passos o recorte livre/coberto pode ser pintado pelo score do modelo de 1 km
   — nos demais o mapa mede outra coisa (1 = censo, 4 = crescimento, 5 = faixa do M1) e
   duas reguas lado a lado dariam cores incongruentes, medindo grandezas diferentes. */
const PASSOS_DA_PRESSAO = new Set([2, 3])

/* O alpha das pecas de cobertura e' o MESMO do hexagono normal (`pele.alphaHex`), e por
   isso deixou de ser constante de modulo quando o tema entrou: usar um alpha maior fazia
   o recorte parecer outra paleta, mais saturada que o resto do mapa. A leitura tem de ser
   a de sempre — a cor sai da mesma regua de faixas, e o que muda entre a parte livre e a
   coberta e' o SCORE, nao a intensidade da tinta. */

/** Alpha de UMA sombra de concorrente. Baixo de proposito: o efeito e' CUMULATIVO.
 *  Com 34, uma concorrente escurece ~13%, duas ~25%, tres ~35%, e um aglomerado satura
 *  em quase preto — que e' a leitura desejada ("quanto mais concorrente, mais escuro").
 *  Alto demais e a primeira sombra ja mataria a cor da faixa embaixo. */
const ALPHA_SOMBRA = 34

/** Precedencia do dashboard: pop<5k vence, senao NaN, senao faixa de score.
 *  Hexes fora do passo atual entram esmaecidos (holofote no funil).
 *  Com `raio1km` ligado nos passos 2/3, a contagem de concorrentes vem ANTES de tudo. */
function fillDoHex(
  h: Hex,
  passoN: number,
  noPasso: boolean,
  raio1km = false,
  alphaHex: number = HEX_FILL_ALPHA,
): RGBA {
  /* O hexagono NAO muda de cor com a chave ligada — de proposito.
     Pintar o hexagono inteiro (por contagem ou por alunos perdidos) afirmava que ele
     todo esta sob a concorrente, quando o disco quase sempre cobre so' um PEDACO. Quem
     mostra a cobertura agora e' a camada `cobertura-1km`, desenhada por cima com a
     geometria real da intersecao. Assim o hexagono segue verde/livre por baixo e a
     parte tomada aparece recortada — que e' a leitura do estudo de ponto: "meu imovel
     cai no lado coberto ou no livre?". */
  // Passo 4 — taxa de crescimento DESTE hexagono. Categorico, fora da rampa de
  // score, e ANTES do corte de pop<5k: um hexagono com pouca gente pode ser
  // justamente onde a obra esta, e escondê-lo apagaria o sinal.
  if (passoN === 4) {
    const c = crescClasseToColor(h.cres_hex_classe)
    // O holofote do funil vale aqui tambem: sem ele os hexes do passo ficavam
    // visualmente iguais aos vizinhos e os rotulos de rank pousavam no nada.
    return noPasso ? c : [c[0], c[1], c[2], Math.round(c[3] * DIM_FORA_DO_PASSO)]
  }

  let base: RGBA
  if (h.pop !== null && h.pop < POP_MIN_ACIONAVEL) base = [...DISCARDED_FILL]
  else if (passoN === PASSO_POR_FAIXA_M1) {
    base = h.faixa ? faixaM1ToColor(h.faixa, alphaHex) : [...NAN_SCORE_FILL]
  } else {
    const score = scoreDoPasso(h, passoN, raio1km)
    base = score === null ? [...NAN_SCORE_FILL] : scoreBandToColor(score, alphaHex)
  }
  if (noPasso) return base
  return [base[0], base[1], base[2], Math.round(base[3] * DIM_FORA_DO_PASSO)]
}

/* --- Numeros do ranking sobre o mapa ---------------------------------------
   O rank so existia no painel lateral, entao nao havia como casar "a 3a
   recomendacao" com um hexagono na tela. O rotulo vem de `passo.itens` (que ja
   chega aqui) e e' TETADO em RANK_LABEL_MAX: rotular os ~35k hexes do mapa
   derrubaria o WebGL. --------------------------------------------------------- */
const RANK_LABEL_MAX = 10

interface RotuloRank {
  hexId: string
  texto: string
  position: [number, number]
}

/** Mesma formatacao do painel lateral (NarrativePanel): "1º" no passo 5, "01" nos demais. */
function textoRank(rank: number, passoN: number): string {
  return passoN === 5 ? `${rank}º` : String(rank).padStart(2, '0')
}

/** Uma leitura municipal do passo 4. Fora do JSX principal so por tamanho. */
function BlocoMunicipal({ c }: { c: CrescimentoMunicipal }) {
  return (
    <>
      <Divisoria />
      {c.tend && <Linha rotulo="Emprego formal" valor={c.tend} />}
      {c.emp !== null && (
        <Linha
          rotulo="Variação desde dez/2022"
          valor={`${c.emp >= 0 ? '+' : ''}${num(c.emp, 1)}%`}
        />
      )}
      {c.uf_mediana !== null && (
        <Linha
          rotulo="Mediana do estado"
          valor={`${c.uf_mediana >= 0 ? '+' : ''}${num(c.uf_mediana, 1)}%`}
        />
      )}
      {c.setor && <Linha rotulo="Setor que puxa" valor={c.setor} />}
      {c.salario !== null && <Linha rotulo="Salário de admissão" valor={brl(c.salario)} />}
      {c.empresas !== null && c.empresas > 0 && (
        <Linha rotulo="Empresas a mais" valor={num(c.empresas)} />
      )}
    </>
  )
}

export interface HexMapProps {
  hexes: Hex[]
  passo: Passo
  /** Leitura de crescimento por cidade (passo 4). Chaveada por `Hex.mun`. */
  cresMun?: Record<string, CrescimentoMunicipal>
  centro: { lat: number | null; lng: number | null }
  /** Nome do municipio carregado — cabecalho do tooltip (como o Streamlit). */
  municipio?: string
  uf?: string
  /** Pins de concorrentes (bandeira quadrada) + Ultra + ícones por rede. */
  pins?: Pins
  selecionado: string | null
  /**
   * Hexes do cenário multi-hex, NA ORDEM em que entraram — a ordem é o dado, não um
   * detalhe: o índice de cada um define a cor de identidade do contorno, que precisa bater
   * com a barra dele no painel de comparação.
   */
  cenario?: string[]
  onSelecionar: (h: Hex) => void
  /**
   * Pedido de VOO ate' um hexagono, vindo de fora (o painel de ranking).
   *
   * Separado de `selecionado` de proposito: clicar um hexagono NO MAPA tambem seleciona,
   * e ali voar seria recentrar o que o operador ja' tem sob o cursor. So' quem clica na
   * lista precisa ser levado, porque o item pode estar em qualquer canto do municipio.
   * O `n` que so' cresce permite pedir o MESMO hexagono duas vezes — voltar para ele
   * depois de arrastar o mapa e' um gesto legitimo, e comparar so' o id nao dispararia.
   */
  voarPara?: { hexId: string; n: number } | null
  /**
   * Pedido de CAPTURA: voa até cada hexágono da lista, na ordem, e devolve uma imagem por
   * enquadramento. O `n` que só cresce segue a mesma razão do `voarPara`.
   */
  pedidoCaptura?: { alvos: AlvoCaptura[]; n: number } | null
  /** As imagens, na ordem pedida. Entrada vazia = aquele hexágono não estava carregado. */
  onCapturas?: (imagens: string[]) => void
  searchPin: SearchPin | null
  /**
   * Camera preservada de uma visita anterior ao mapa (ida e volta pela Viabilidade).
   * Quando vem preenchida, o mapa REABRE nela em vez de recomecar no centro do
   * municipio com zoom 9.6 — e o voo automatico ate o `searchPin` e' suprimido no
   * primeiro render, senao ele sobrescreveria justamente o enquadramento restaurado.
   */
  /** PROTOTIPO: quando true, os passos 2 e 3 mostram a cobertura do raio de 1 km. */
  raio1km?: boolean
  /** Academias INDEPENDENTES com score (BLK-MA-15). Lista propria, nunca misturada aos
   *  concorrentes: um universo e' quem disputa, o outro e' quem se compra. Vazia = camada
   *  desligada ou artefato ausente, e o mapa fica exatamente como antes. */
  independentes?: PinIndependente[]
  /** Oportunidades IMOBILIARIAS do recorte (camada de oferta). Mesmo idioma das
   *  independentes: lista-ou-undefined — quem decide se a camada liga e' o MapScreen. */
  imoveis?: Oportunidade[]
  /** Clique num pin de imovel: o MapScreen abre a janela de detalhe dele. */
  onImovel?: (o: Oportunidade) => void
  /** PROTOTIPO: area coberta pelo raio, ja recortada dentro dos hexagonos. */
  cobertura1k?: Cobertura1k | null
  /** Tema do app: escolhe o basemap e as cores que o WebGL nao le' do CSS (ver `PELE`). */
  tema: Tema
  cameraInicial?: ViewState | null
  /** Reporta a camera ao pai a cada mudanca, para sobreviver ao unmount da tela. */
  onCamera?: (v: ViewState) => void
  /**
   * Regua ligada: o clique MEDE em vez de selecionar hexagono.
   *
   * Modo dedicado, e nao clique-no-pin: o clique do mapa ja tem dono (selecionar
   * hexagono e' o gesto central do funil) e roubar esse gesto quebraria a tela para
   * quem nunca vai medir. Com a chave, o unico gesto que muda e' o de quem pediu.
   */
  medindo?: boolean
}

/**
 * Rótulo de EXIBIÇÃO do `status_churn`. Regra permanente do `CLAUDE.md` §2: valor bruto de enum
 * nunca vai à tela — para exibir acentuado usa-se uma camada de LABEL, sem tocar o valor bruto.
 *
 * Dois dos quatro estados são impróprios como texto: `estavel` (sem acento) e `sumiu_recente` (com
 * underscore). Hoje o defeito está DORMENTE porque as unidades do agregador estão todas em `novo`,
 * que por acidente é uma palavra portuguesa válida — assim que a série do GymScraping acumular
 * semanas, o operador leria literalmente "Presença na série: sumiu_recente".
 *
 * As chaves são exatamente `STATUS_CHURN_VALIDOS` (`contrato.py:70`). O fallback devolve o valor
 * cru de propósito: um quinto estado futuro aparece feio, mas aparece — melhor que sumir da tela.
 */
const ROTULO_CHURN: Record<string, string> = {
  novo: 'Série curta demais para julgar',
  estavel: 'Estável',
  piscando: 'Intermitente',
  sumiu_recente: 'Sumiu recentemente',
}

export interface ViewState {
  longitude: number
  latitude: number
  zoom: number
  pitch: number
  bearing: number
  transitionDuration?: number
  transitionInterpolator?: FlyToInterpolator
}

export default function HexMap({
  hexes,
  passo,
  cresMun,
  centro,
  municipio,
  uf,
  pins,
  selecionado,
  cenario,
  onSelecionar,
  voarPara = null,
  pedidoCaptura = null,
  onCapturas,
  searchPin,
  raio1km = false,
  independentes,
  imoveis,
  onImovel,
  cobertura1k,
  tema,
  cameraInicial,
  onCamera,
  medindo = false,
}: HexMapProps) {
  const pele = PELE[tema]
  // O tooltip do passo 4 ficou alto (porte, obra, setor, salario, empresas) e era
  // cortado quando o cursor estava na parte de baixo ou na direita do mapa. Medimos
  // a caixa do mapa e viramos o balao para o lado que tem espaco.
  const caixaRef = useRef<HTMLDivElement>(null)
  /** Leitura da cidade do hexagono sob o cursor — `undefined` se ela nao tem leitura. */
  const cresDoHex = (h: Hex) => (h.mun ? cresMun?.[h.mun] : undefined)
  function ancora(x: number, y: number, altura = 360, largura = 240) {
    const b = caixaRef.current?.getBoundingClientRect()
    const viraY = b ? y + altura + 14 > b.height : false
    const viraX = b ? x + largura + 14 > b.width : false
    return {
      left: x + (viraX ? -14 : 14),
      top: y + (viraY ? -14 : 14),
      transform: `translate(${viraX ? '-100%' : '0'}, ${viraY ? '-100%' : '0'})`,
    }
  }

  const [hover, setHover] = useState<{ h: Hex; x: number; y: number } | null>(null)
  const [pinHover, setPinHover] = useState<{
    titulo: string
    sub: string
    // O Pin INTEIRO, e nao so' titulo/sub: quando ele vem de um agregador (`diag`), o balao abre
    // um bloco com a pressao medida e a conta por tras dela.
    d?: Pin
    x: number
    y: number
  } | null>(null)
  // Balao PROPRIO para a independente: ele carrega numeros com rotulo, e nao o par
  // titulo/subtitulo do pin de concorrente.
  const [indepHover, setIndepHover] = useState<{
    d: PinIndependente
    x: number
    y: number
  } | null>(null)
  // Balao do IMOVEL (camada imobiliaria): os 4 numeros do ranking da aba.
  const [imovelHover, setImovelHover] = useState<{
    d: Oportunidade
    x: number
    y: number
  } | null>(null)
  // Ícones deck.gl memoizados por rede (identidade estável evita re-pack do atlas).
  const iconObjs = useMemo(() => {
    const m: Record<string, IconeDeck> = {}
    for (const [rede, url] of Object.entries(pins?.icones ?? {})) m[rede] = iconeDeck(url)
    return m
  }, [pins?.icones])

  /**
   * O ENQUADRAMENTO INICIAL, em ordem de precedencia.
   *
   * 1. Camera restaurada (volta do estudo pontual) — devolve o que o operador tinha.
   * 2. PIN EXTERNO — alguem ja escolheu um ponto: o mapa NASCE nele, aproximado.
   * 3. Centro do municipio — o padrao de quem abriu uma cidade para explorar.
   *
   * POR QUE O PIN ENTRA AQUI, E NAO SO' NO VOO. Havia (e ha) um efeito que voa ate o
   * `searchPin` com zoom >= 13. Medido em 28/08/2026, chegando pelo ranking nacional,
   * ele NAO surtia efeito: o mapa parava em 9,6 — o enquadramento da cidade inteira —
   * e o operador tinha de dar zoom a mao ate o hexagono que acabara de escolher na
   * lista, que e' exatamente o trabalho que clicar em "Ver no mapa" deveria poupar.
   *
   * Este componente so' MONTA depois que o payload do municipio chega (o pai o renderiza
   * sob `dados &&`), e o pin externo ja existe nesse instante. Entao nao ha nada a
   * esperar: em vez de nascer longe e depender de um voo que corre contra os outros
   * efeitos de camera, ele nasce ja enquadrado. Voo que nao precisa acontecer nao tem
   * como chegar atrasado.
   */
  const [view, setView] = useState<ViewState>(() => {
    if (cameraInicial) return cameraInicial
    if (searchPin) {
      return {
        longitude: searchPin.lng,
        latitude: searchPin.lat,
        zoom: ZOOM_DO_HEXAGONO,
        pitch: 0,
        bearing: 0,
      }
    }
    // Fallback de "centro ausente". Era Brasília cravada (-47,9 / -15,78) — e é leitura
    // de PRIMEIRA RENDERIZAÇÃO (classe (2) da spec §3.5): inicializador de `useState`
    // roda antes de qualquer efeito. É por isso que o perfil é resolvido no `main.tsx`
    // ANTES de a árvore ser importada; aqui um getter tardio não salvaria, e o resultado
    // seria a câmera nascendo no Brasil numa instância argentina.
    const vista = perfilDoCliente().vista_padrao
    return {
      longitude: centro.lng ?? vista.lng,
      latitude: centro.lat ?? vista.lat,
      zoom: ZOOM_DO_MUNICIPIO,
      pitch: 0,
      bearing: 0,
    }
  })

  // Sobe a camera para o pai a cada mudanca. Sem isso ela morre no unmount da tela
  // (App troca `mapa` por `viabilidade` com render condicional, o que DESMONTA a arvore).
  // Cobre todos os caminhos que mexem em `view`: arraste do usuario e os dois voos
  // automaticos. `onCamera` PRECISA ser estavel no pai (useCallback) — com callback
  // inline, a identidade nova a cada render faria isto disparar em todo render.
  useEffect(() => {
    onCamera?.(view)
  }, [view, onCamera])

  // Voa para o centro do municipio quando ele muda.
  //
  // UM PIN EXTERNO VENCE O CENTRO DO MUNICIPIO. Sem esta regra o zoom do pin era
  // desfeito por uma corrida: quem chega pelo ranking nacional muda UF e municipio na
  // mesma passagem, o voo ate' o pin roda de imediato (zoom >= 13) e, quando o payload
  // do municipio finalmente chega, `centro` muda e ESTE efeito afastava a camera de
  // volta para 9.6 — a cidade inteira, que e' exatamente o que o operador acabou de
  // pedir para nao ter de olhar. Os dois voos estao certos; so' a ordem enganava,
  // porque o segundo depende de dado que chega DEPOIS do primeiro.
  //
  // O centro do municipio continua sendo o destino certo quando NINGUEM escolheu um
  // ponto: e' o enquadramento de quem acabou de abrir uma cidade para explorar.
  const centroKey = `${centro.lat},${centro.lng}`
  const centroAnterior = useRef(centroKey)
  useEffect(() => {
    if (centro.lat == null || centro.lng == null) return
    if (centroAnterior.current === centroKey) return
    centroAnterior.current = centroKey
    if (searchPin) {
      setView((v) => ({
        ...v,
        longitude: searchPin.lng,
        latitude: searchPin.lat,
        // Mesmo piso do voo do pin, e pelo mesmo motivo: nunca AFASTAR de quem ja'
        // esta' aproximado. `max` guarda o zoom do operador se ele ja' foi mais fundo.
        zoom: Math.max(ZOOM_DO_HEXAGONO, v.zoom),
        transitionDuration: 700,
        transitionInterpolator: FLY,
      }))
      return
    }
    setView((v) => ({
      ...v,
      longitude: centro.lng!,
      latitude: centro.lat!,
      zoom: ZOOM_DO_MUNICIPIO,
      transitionDuration: 700,
      transitionInterpolator: FLY,
    }))
  }, [centroKey, centro.lat, centro.lng, searchPin])

  // Voa e aproxima quando um ponto e buscado. No PRIMEIRO render com camera restaurada
  // o voo e' pulado de proposito: o pin ja existia antes da ida a Viabilidade, e voar
  // ate ele jogaria o zoom para >=13, desfazendo o enquadramento que acabou de voltar.
  /* IDENTIDADE, nao flag one-shot. A versao anterior era um ref consumido no primeiro
     run do efeito — e o StrictMode invoca efeitos DUAS vezes em dev (montar, limpar,
     montar). A primeira invocacao gastava a flag e a segunda voava assim mesmo, entao
     em desenvolvimento o guard nunca valia e mascarava o bug da camera velha; so' em
     build de producao ele funcionava. Comparando a IDENTIDADE do pin, a regra e'
     idempotente: o voo e' pulado exatamente para o pin que ja existia quando a camera
     foi restaurada, quantas vezes o efeito rodar. Uma busca NOVA gera outro objeto e
     voa normalmente. */
  const pinDaMontagem = useRef(searchPin)
  useEffect(() => {
    if (!searchPin) return
    if (cameraInicial != null && searchPin === pinDaMontagem.current) return
    setView((v) => ({
      ...v,
      longitude: searchPin.lng,
      latitude: searchPin.lat,
      zoom: Math.max(ZOOM_DO_HEXAGONO, v.zoom),
      transitionDuration: 800,
      transitionInterpolator: FLY,
    }))
  }, [searchPin, cameraInicial])

  /* Voa ate' o hexagono pedido pelo painel. A coordenada sai do proprio `hexes` (o `Hex`
     ja' carrega lat/lng), entao nao ha' conversao de H3 aqui — e se o id nao estiver na
     lista carregada, nao se voa para lugar nenhum em vez de voar para o centro do mundo.

     `zoom: max(12, atual)` NUNCA AFASTA: quem ja' esta' com o mapa aproximado num bairro
     e clica no proximo item da lista quer andar ate' ele, nao recomecar de longe. */
  const vooAnterior = useRef(voarPara?.n ?? 0)
  useEffect(() => {
    if (!voarPara || voarPara.n === vooAnterior.current) return
    vooAnterior.current = voarPara.n
    const alvo = hexes.find((h) => h.id === voarPara.hexId)
    if (!alvo) return
    setView((v) => ({
      ...v,
      longitude: alvo.lng,
      latitude: alvo.lat,
      zoom: Math.max(12, v.zoom),
      transitionDuration: 700,
      transitionInterpolator: FLY,
    }))
  }, [voarPara, hexes])

  /* CAPTURA do mapa, um enquadramento por hexágono (pedido do Juan, 2026-08-13).
     Mesmo idioma do `voarPara`: contador que só cresce, para dar para pedir a mesma
     sequência duas vezes.

     O `preserveDrawingBuffer` entra SÓ AQUI. Ele é obrigatório para `toDataURL` não
     devolver imagem em branco — o navegador descarta o buffer depois de pintar —, mas
     custa desempenho em TODO frame, e o mapa é arrastado o tempo todo. Ligá-lo de forma
     permanente cobraria de quem só navega, para servir a um print que acontece uma vez.
     Trocar o flag exige recriar o contexto WebGL, e é o que a `key` do DeckGL faz. */
  const [capturando, setCapturando] = useState(false)
  /**
   * O pin do quadro que esta' sendo capturado AGORA.
   *
   * Substitui o `searchPin` durante a captura, e nao se soma a ele: o `searchPin` e' um
   * so' — o do ponto aberto na janela — entao capturar tres enderecos em sequencia punha
   * a MESMA marca nas tres fotos, e nas duas primeiras ela apontava um imovel que nao era
   * o assunto daquela coluna. Fora do modo de imovel fica `null`, e ai a captura sai sem
   * pin nenhum: um pin de busca antigo no meio do deck se le como "o ponto e' aqui".
   */
  const [marcaCaptura, setMarcaCaptura] = useState<SearchPin | null>(null)
  const capturaAnterior = useRef(pedidoCaptura?.n ?? 0)
  useEffect(() => {
    if (!pedidoCaptura || pedidoCaptura.n === capturaAnterior.current) return
    capturaAnterior.current = pedidoCaptura.n
    let cancelado = false
    const pausa = (ms: number) => new Promise((r) => setTimeout(r, ms))

    void (async () => {
      setCapturando(true)
      // Espera o remount COM o buffer preservado antes do primeiro voo; sem isto a
      // primeira imagem sairia branca e as outras quatro certas, que é o pior dos mundos
      // (parece defeito do hexágono, não da captura).
      await pausa(500)

      const imagens: string[] = []
      for (const pedido of pedidoCaptura.alvos) {
        if (cancelado) return
        const alvo = hexes.find((h) => h.id === pedido.hexId)
        if (!alvo) {
          imagens.push('')
          continue
        }

        /* ZOOM DERIVADO DO HEXAGONO, e nao os 13,2 fixos de antes. Em zoom fixo o
           enquadramento dependia do tamanho da janela: numa tela larga a celula res-7
           saia como um miolo de ~10% da foto e o resto era territorio que ninguem esta'
           comparando ("a print do hexagono que ele esta', nao do mapa todo" — Juan,
           2026-08-19). O recorte quadrado do `comporCanvas` fecha o resto. */
        const caixa = caixaRef.current?.getBoundingClientRect()
        const zoom = zoomQueEnquadra(
          larguraDoAnel(cellToBoundary(pedido.hexId) as [number, number][]),
          alvo.lat,
          caixa?.width || 1200,
          caixa?.height || 800,
        )
        // A marca do imovel entra ANTES do voo, para estar pintada quando o quadro parar.
        setMarcaCaptura(
          pedido.lat != null && pedido.lng != null
            ? { lat: pedido.lat, lng: pedido.lng, hexId: pedido.hexId }
            : null,
        )
        setView((v) => ({
          ...v,
          longitude: alvo.lng,
          latitude: alvo.lat,
          zoom,
          transitionDuration: ESPERA_VOO_MS,
          transitionInterpolator: FLY,
        }))
        await pausa(esperaDeCaptura())
        if (cancelado) return
        const canvases = Array.from(caixaRef.current?.querySelectorAll('canvas') ?? [])
        imagens.push(
          comporCanvas(canvases, document.createElement('canvas'), { recortar: true }) ?? '',
        )
      }

      setMarcaCaptura(null)
      setCapturando(false)
      if (!cancelado) onCapturas?.(imagens)
    })()

    return () => {
      cancelado = true
      setMarcaCaptura(null)
    }
  }, [pedidoCaptura, hexes, onCapturas])

  // Cor da camada ativa: veste o "score forte" do tooltip e a borda do rotulo de
  // rank. Os dois dizem "isto e' da camada N" — antes diziam em turquesa, a mesma
  // cor do cenario multi-hex e do pin de busca na MESMA superficie.
  const cor = camadaCor(passo.n)

  const destaque = useMemo(() => new Set(passo.hexes), [passo.hexes])
  const cenarioSet = useMemo(() => new Set(cenario ?? []), [cenario])
  /* POSICAO na lista, e nao so' "esta ou nao esta": e' o indice que da a cor de identidade,
     a MESMA que o painel usa na barra daquele hexagono. Sem isto os cinco saiam com o
     mesmo contorno turquesa e nada ligava a barra ao desenho.
     `indexOf` e nao um Map: `Map` esta' SOMBREADO neste arquivo pelo componente de mesmo
     nome do `react-map-gl`, e a lista tem no maximo `MAX_COMPARADOS` (5) itens — o `Set`
     acima ja' descarta os outros 15 mil hexagonos antes de chegar aqui. */
  const cenarioLista = useMemo(() => cenario ?? [], [cenario])
  const cenarioKey = cenarioLista.join(',')

  // Posicao do rotulo = centro do proprio H3 (nao o lat/lng servido), para o numero
  // cair no meio do hexagono mesmo quando o filtro de faixa tira o hex do `hexes`.
  const rotulosRank = useMemo(() => {
    const vistos = new Set<string>()
    const out: RotuloRank[] = []
    for (const it of passo.itens) {
      if (out.length >= RANK_LABEL_MAX) break
      if (!it.hex_id || vistos.has(it.hex_id)) continue
      vistos.add(it.hex_id)
      try {
        const [lat, lng] = cellToLatLng(it.hex_id)
        out.push({ hexId: it.hex_id, texto: textoRank(it.rank, passo.n), position: [lng, lat] })
      } catch {
        // hex_id invalido: o item continua no painel, so nao ganha rotulo no mapa.
      }
    }
    return out
  }, [passo.itens, passo.n])

  /* Hexes que a camada de cobertura pinta por inteiro. As pecas `livre` + `coberto`
     LADRILHAM o hexagono (somam 100% da area), entao o preenchimento do proprio hexagono
     tem de sair — senao a mesma cor e' desenhada DUAS vezes no mesmo pixel, o alpha
     soma e o hexagono aparece mais vivo que os vizinhos. Era isso o "triangulo amarelo
     mais claro": nao era score errado (peca e hexagono estao na MESMA faixa), era
     dupla pintura. */
  /* Indice hex_id -> Hex para o hover da camada de cobertura devolver o hexagono certo.
     Objeto simples, nao `new Map`: neste arquivo o identificador `Map` esta OCUPADO pelo
     componente do react-map-gl (import no topo). */
  const hexPorId = useMemo(() => {
    const m: Record<string, Hex> = {}
    for (const h of hexes) m[h.id] = h
    return m
  }, [hexes])

  const hexesCobertos = useMemo(() => {
    const s = new Set<string>()
    for (const p of cobertura1k?.pecas ?? []) s.add(p.hex)
    return s
  }, [cobertura1k])

  /* Qual pin o mapa desenha. Durante a captura manda o do quadro (`marcaCaptura`), que
     e' `null` fora do modo de imovel — e ai a foto sai sem pin, em vez de carregar a marca
     de uma busca antiga para dentro do PDF. */
  const pinNoMapa = capturando ? marcaCaptura : searchPin

  /* --- Regua (BLK-CONC-MEDIR): ponta A -> ponta B, com trava nos pins --- */
  const [medicao, setMedicao] = useState<{ a: AlvoMedicao; b: AlvoMedicao | null } | null>(null)

  /* Tudo que a regua imanta: as bandeiras de concorrente, as unidades nossas e o proprio
     ponto analisado. O ponto entra na lista porque a medicao TIPICA parte dele — sem isso
     a ponta de origem seria um clique livre e o par deixaria de ser reprodutivel. */
  const alvosImantaveis = useMemo<AlvoMedicao[]>(() => {
    const lista: AlvoMedicao[] = []
    if (searchPin) {
      lista.push({
        lat: searchPin.lat,
        lng: searchPin.lng,
        rotulo: 'Ponto analisado',
        tipo: 'ponto',
      })
    }
    for (const p of pins?.concorrentes ?? []) {
      lista.push({ lat: p.lat, lng: p.lng, rotulo: p.nome || p.label || 'Concorrente', tipo: 'concorrente' })
    }
    for (const p of pins?.ultra ?? []) {
      lista.push({ lat: p.lat, lng: p.lng, rotulo: p.nome || 'Ultra Academia', tipo: 'ultra' })
    }
    return lista
  }, [pins, searchPin])

  /* Desligar a regua limpa a medicao: deixar a linha na tela depois da chave desligada
     faria o mapa afirmar uma medicao que o operador nao consegue mais mexer. */
  useEffect(() => {
    if (!medindo) setMedicao(null)
  }, [medindo])

  /* Trocar de municipio/UF tambem limpa. Sem isto a medicao de uma cidade sobrevivia a
     mudanca e o mapa desenhava linha e rotulo sobre um territorio que nao e' o dos pontos
     medidos — um numero correto no lugar errado, que e' pior que numero nenhum. */
  useEffect(() => {
    setMedicao(null)
  }, [municipio, uf])

  function medirNoClique(coordenada: number[] | undefined) {
    if (!coordenada) return
    const clique = { lat: coordenada[1], lng: coordenada[0] }
    const mpp = metrosPorPixel(view.zoom, clique.lat)
    const travado = travarNoAlvo(clique, alvosImantaveis, mpp)
    const ponta: AlvoMedicao = travado ?? { ...clique, rotulo: 'Ponto livre', tipo: 'ponto' }
    setMedicao((atual) =>
      atual == null || atual.b != null ? { a: ponta, b: null } : { a: atual.a, b: ponta },
    )
  }


  const camadas = useMemo(() => {
    const base: Layer[] = [
      new H3HexagonLayer<Hex>({
        id: `hex-${passo.n}`,
        data: hexes,
        getHexagon: (d) => d.id,
        extruded: false,
        filled: true,
        stroked: true,
        /* GEOMETRIA FIEL — o default `highPrecision: 'auto'` nao serve aqui.

           'auto' so' liga a precisao alta com globo, pentagono no dataset, resolucoes
           misturadas ou res<=5. Nada disso vale nesta camada (tudo res-7, mercator),
           entao ela cai no caminho rapido: o deck.gl calcula os 6 vertices de UM
           hexagono — o do centro da tela — e desenha todos os outros como aquele mesmo
           poligono TRANSLADADO. Longe do centro o clone deixa de bater com a celula H3
           real: as celulas saem inclinadas e abrem fresta entre as vizinhas.

           E ele so' recalcula quando o centro anda alem de um limiar — por isso a torcao
           ANDA ao dar zoom ou arrastar (relato do Juan, 2026-08-26: "se eu coloco zoom e
           tiro, os hexagonos ficam tortos").

           DOI MUITO MAIS NA ARGENTINA, e por isso o Brasil nunca reclamou: um pentagono
           H3 res-7 fica a 504 km da costa argentina (-39,10/-57,70) e comprime a grade em
           volta. Erro maximo medido, invariante a rotacao: Grande Sao Paulo 10 m (1% da
           aresta), Estado de SP 81 m (6%), Grande Buenos Aires 1.089 m — 77% da aresta de
           1.406 m. A armadilha: 'auto' ligaria a precisao se houvesse pentagono NO
           DATASET, mas esse esta no oceano, onde nunca havera hexagono povoado.

           Com 42 mil celulas, sem custo perceptivel. */
        highPrecision: true,
        getFillColor: (d) => {
          const comRaio = raio1km && PASSOS_DA_PRESSAO.has(passo.n)
          // Transparente onde a cobertura ja pinta o hexagono inteiro (ver `hexesCobertos`).
          if (comRaio && hexesCobertos.has(d.id)) return [0, 0, 0, 0]
          return fillDoHex(d, passo.n, destaque.has(d.id), comRaio, pele.alphaHex)
        },
        // Borda neutra e fina; hex SELECIONADO -> contorno CONTRÁRIO ao basemap (claro
        // no escuro, escuro no claro); hexes do CENÁRIO
        // multi-hex -> a COR DE IDENTIDADE da posição dele na comparação, a mesma da barra
        // no painel (antes eram todos turquesa, e nada ligava barra a hexágono na tela).
        getLineColor: (d) => {
          if (d.id === selecionado) return pele.selecao
          if (!cenarioSet.has(d.id)) return [8, 11, 16, 55]
          // TETO na cor, e não no clique. O `cenario` cresce além de 5 de propósito — o
          // painel troca para o modo SOMA e ali somar 8 hexágonos é legítimo. Mas a
          // paleta tem 5 cores e `corDeIdentidade` cicla: o 6º hexágono sairia com a cor
          // idêntica à do 1º, que é exatamente o que a paleta existe para impedir.
          //
          // Acima do teto vai um CINZA neutro. Não o turquesa `--ac`: ele é o mesmo
          // `CRESC_ALTA_HEX` que preenche os hexágonos "Em alta" no passo 4, então usá-lo
          // aqui faria o contorno de "está no cenário" colidir com um significado que a
          // camada já dá àquela matiz — no passo 4, um hex do cenário que também fosse
          // "Em alta" ficaria com contorno e preenchimento da mesma cor. Cinza não afirma
          // nada, e a largura de 42 m (getLineWidth) já marca a seleção.
          // As CORES_IDENTIDADE não seguem o tema, e isso é deliberado: são as mesmas
          // cores das barras do painel de comparação, e é essa igualdade que liga a
          // barra ao hexágono. Fazê-las mudar de valor no claro quebraria o par. São de
          // tonalidade média, em linha opaca de 42 m — sobrevivem nos dois basemaps.
          const i = cenarioLista.indexOf(d.id)
          return i < CORES_IDENTIDADE.length ? corDeIdentidadeRgb(i) : [154, 167, 181, 255]
        },
        getLineWidth: (d) => (d.id === selecionado ? 55 : cenarioSet.has(d.id) ? 42 : 6),
        lineWidthUnits: 'meters',
        lineWidthMinPixels: 0.5,
        pickable: true,
        autoHighlight: true,
        highlightColor: pele.realce,
        onClick: (info) => {
          // Com a regua ligada o clique e' da medicao: selecionar hexagono AQUI trocaria
          // a camada colorida embaixo da linha que o operador acabou de tracar.
          if (medindo) return
          if (info.object) onSelecionar(info.object as Hex)
        },
        onHover: (info) => {
          setHover(
            info.object ? { h: info.object as Hex, x: info.x, y: info.y } : null,
          )
        },
        updateTriggers: {
          // `tema` entra nos dois gatilhos: as funções acima o capturam por closure, e
          // sem ele o deck.gl reusa os buffers e o mapa fica com a pele antiga.
          getFillColor: [passo.n, raio1km, hexesCobertos, tema],
          getLineColor: [selecionado, cenarioKey, tema],
          getLineWidth: [selecionado, cenarioKey],
        },
        transitions: { getFillColor: 260 },
      }),

      /* PROTOTIPO — a AREA COBERTA pelo raio de 1 km, ja recortada DENTRO de cada
         hexagono. E' a peca que faltava: pintar o hexagono inteiro de uma cor so'
         escondia a direcao. Aqui da' para ver que o lado norte do hexagono esta sob o
         disco de uma concorrente e o lado sul esta livre — que e' a leitura que o estudo
         de ponto precisa ("meu imovel cai na parte coberta ou na livre?").
         A parte NAO coberta nao e' pintada: fica com a cor da propria camada. */
      ...(raio1km && PASSOS_DA_PRESSAO.has(passo.n) && cobertura1k?.pecas?.length
        ? [
            new PolygonLayer<PecaCobertura>({
              id: 'cobertura-1km',
              data: cobertura1k.pecas,
              getPolygon: (d) => d.anel,
              // OBRIGATORIO aqui. O padrao do deck.gl e' `positionFormat: 'XYZ'`
              // (@deck.gl/core/dist/lib/layer.js:97) e os aneis vem como pares
              // [lng, lat] — DOIS valores. Sem isto a normalizacao do poligono le os
              // vertices de tres em tres, a geometria vira lixo e a camada nao desenha
              // NADA, sem erro no console. O ScatterplotLayer nao sofre disso porque usa
              // `getPosition` por objeto, sem normalizar anel — foi por isso que os
              // circulos apareciam e o recorte nao.
              positionFormat: 'XY',
              filled: true,
              /* Cada peca pinta pela MESMA regua de faixas do mapa, com o score DELA.
                 E' isso que faz a parte livre "melhorar": ali nenhuma concorrente
                 desconta residual, entao o score sobe e a faixa esquenta. A parte coberta
                 cai — e cai MAIS quanto mais concorrente consome, o que da a intensidade
                 da disputa sem empilhar geometria (a versao anterior desenhava uma peca
                 por concorrente e 49 poligonos sobrepostos poluiam o mapa). */
              getFillColor: (d) => scoreBandToColor(d.score, pele.alphaHex),
              /* PICKABLE: sem isto o tooltip morria sobre qualquer hexagono coberto.
                 O preenchimento do hexagono e' zerado onde a cobertura pinta (para nao
                 pintar a mesma cor duas vezes), e o hover passava a nao encontrar
                 geometria — o operador perdia a leitura do hexagono justamente onde ela
                 mais importa. A peca devolve o hexagono a que pertence. */
              onHover: (info) => {
                const d = info.object as PecaCobertura | undefined
                const h = d ? hexPorId[d.hex] : undefined
                setHover(h ? { h, x: info.x, y: info.y } : null)
              },
              // SEM contorno proprio: a linha do alcance ja e' desenhada uma unica vez
              // pela camada `conc-alcance-1km`. Contornar cada peca acrescentaria as
              // ARESTAS DOS HEXAGONOS ao desenho e traria de volta a poluicao.
              stroked: false,
              updateTriggers: { getFillColor: [passo.n, tema] },
              pickable: true,
              // O H3HexagonLayer desenha no MESMO plano (z=0). Com o teste de
              // profundidade ligado as duas geometrias disputam o pixel e a cobertura
              // pode sumir por tras do hexagono, dependendo da ordem de submissao ao
              // WebGL. `depthCompare: 'always'` (nome do luma.gl v9; era `depthTest:
              // false` ate o deck.gl v8) garante que ela pousa por cima, sempre.
              parameters: { depthCompare: 'always' as const },
            }),
          ]
        : []),

      /* SOMBRA por concorrente: uma peca para CADA concorrente que toca o hexagono,
         preta e translucida, SEM contorno. Empilhadas, o alpha se acumula e a area fica
         mais escura quanto mais concorrentes a cobrem — a leitura de adensamento que a
         peca unica (uniao) apaga por construcao.
         Sem contorno de proposito: a poluicao anterior vinha das BORDAS se cruzando, nao
         do empilhamento. Vem DEPOIS das pecas coloridas (escurece a cor da faixa) e ANTES
         do contorno do alcance.

         Desenha em TODOS os passos, e nao so' nos da regua do residual: a densidade de
         concorrentes nao pertence a regua nenhuma — ela responde "quantas me alcancam
         aqui?", que e' verdade em qualquer camada do funil. Quem depende da regua e' o
         recorte COLORIDO acima, nao esta tinta escura (pedido do Felipe, 2026-08-12). */
      ...(raio1km && cobertura1k?.sombras?.length
        ? [
            new PolygonLayer<number[][][]>({
              id: 'cobertura-sombra-1km',
              data: cobertura1k.sombras,
              getPolygon: (d) => d,
              positionFormat: 'XY',
              filled: true,
              stroked: false,
              getFillColor: [4, 7, 12, ALPHA_SOMBRA],
              pickable: false,
              parameters: { depthCompare: 'always' as const },
            }),
          ]
        : []),

      /* CONTORNO do alcance: uma linha so', a fronteira da uniao dos discos.
         Antes era um ScatterplotLayer com um circulo POR concorrente — num aglomerado as
         bordas se cruzavam umas sobre as outras e o mapa virava um emaranhado de arcos.
         A uniao nao tem linha interna: mostra ate onde a concorrencia alcanca, e nada
         mais. Sem preenchimento: quem pinta a area sao as pecas livre/coberto.

         Tambem em TODOS os passos: "ate onde a concorrencia chega" e' um fato geografico,
         nao uma leitura de regua. Enquanto estava preso aos passos 2 e 3, ligar a chave em
         qualquer outra camada nao desenhava nada e parecia defeito. */
      ...(raio1km && cobertura1k?.contorno?.length
        ? [
            new PolygonLayer<number[][][]>({
              id: 'conc-alcance-1km',
              data: cobertura1k.contorno,
              getPolygon: (d) => d,
              positionFormat: 'XY',
              filled: false,
              stroked: true,
              getLineColor: [255, 176, 120, 150],
              lineWidthUnits: 'pixels',
              getLineWidth: 1.1,
              pickable: false,
              parameters: { depthCompare: 'always' as const },
            }),
          ]
        : []),

      /* INDEPENDENTES (BLK-MA-15): logo do WellHub. Todas vem do feed do WellHub, entao a marca
         do agregador as identifica — pedido do Felipe (2026-08-25). SO' as independentes levam a
         logo do WellHub; as unidades de REDE mantem a bandeira propria (camada `conc-pins`).
         O numero vive no tooltip (setIndepHover). Desenhadas ANTES dos concorrentes e da Ultra:
         onde houver sobreposicao, quem manda na leitura e' a rede instalada. */
      ...(independentes?.length
        ? [
            new IconLayer<PinIndependente>({
              id: 'independentes-pins',
              data: independentes,
              getPosition: (d) => [d.lng ?? 0, d.lat ?? 0],
              getIcon: () => ICONE_WELLHUB,
              // Menor que a bandeira das cadeias (30-38): a independente e' camada secundaria e
              // nao pode competir com a rede instalada. Cap 30 evita upscaling do atlas de 128px.
              getSize: 22,
              sizeUnits: 'pixels',
              sizeMinPixels: 10,
              sizeMaxPixels: 30,
              pickable: true,
              onHover: (info) => {
                const d = info.object as PinIndependente | undefined
                setIndepHover(d ? { d, x: info.x, y: info.y } : null)
              },
            }) as unknown as IconLayer<Hex>,
          ]
        : []),

      /* OPORTUNIDADES IMOBILIARIAS (camada de oferta, liga/desliga pela pilula).
         Pontinho por imovel na COR CATEGORICA do tipo — a MESMA paleta da aba
         imobiliaria (galpao rosa, comercial/loja azul, terreno laranja). Nao e' uma
         segunda regua sobre a rampa de score ("dois idiomas"): tipo e' IDENTIDADE,
         como a bandeira das redes, e o rotulo viaja no tooltip, como na aba.
         So entram imoveis COM coordenada (lat/lng sao nullable no payload; `?? 0`
         jogaria o ponto no Golfo da Guine). Desenhadas ANTES dos pins de rede: na
         sobreposicao, a rede instalada vence — mesma precedencia das independentes. */
      ...(imoveis?.length
        ? [
            new ScatterplotLayer<Oportunidade>({
              id: 'imoveis-pins',
              data: imoveis.filter((d) => d.lat != null && d.lng != null),
              getPosition: (d) => [d.lng ?? 0, d.lat ?? 0],
              getRadius: 5.5,
              radiusUnits: 'pixels',
              radiusMinPixels: 3.5,
              radiusMaxPixels: 9,
              getFillColor: (d) => {
                const [r, g, b] = corTipoRgb(d.tipo)
                return [r, g, b, 215]
              },
              stroked: true,
              /* Anel MAGENTA (o acento da camada imobiliaria), nao o anel escuro das
                 independentes: o laranja do 'terreno' (#f2913a) e o laranja das
                 independentes (#e8663c) sao quase a mesma matiz em pontos de ~5 px —
                 com as duas camadas ligadas, o anel e' o que diz de que universo o
                 ponto e' (imovel para alugar vs academia para comprar). */
              getLineColor: [221, 61, 151, 235],
              lineWidthUnits: 'pixels',
              getLineWidth: 1.2,
              pickable: true,
              onClick: (info) => {
                const d = info.object as Oportunidade | undefined
                if (d) onImovel?.(d)
              },
              onHover: (info) => {
                const d = info.object as Oportunidade | undefined
                setImovelHover(d ? { d, x: info.x, y: info.y } : null)
              },
            }) as unknown as ScatterplotLayer<Hex>,
          ]
        : []),

      // Concorrentes: bandeira QUADRADA com a logo da rede (fallback cor+sigla),
      // enxuta (pedido do Felipe). Ultra vem por cima, um pouco maior.
      new IconLayer<Pin>({
        id: 'conc-pins',
        data: pins?.concorrentes ?? [],
        getPosition: (d) => [d.lng, d.lat],
        // Unidade com diagnostico usa a variante com HALO. O fallback para o icone normal importa:
        // se o backend nao mandou a variante, o pin aparece igual aos outros em vez de sumir.
        getIcon: (d) =>
          /* FOTO NO LUGAR DO QUADRADO. A independente não tem logo e caía num quadrado
             cinza com "IND" — três letras iguais em milhares de pinos, que não distinguem
             nada (pedido do Juan, 2026-08-26). Com a foto da unidade, cada pino vira a
             fachada dela.

             O ícone é montado AQUI, e não recebido pronto em `pins.icones` como as marcas:
             logo é da REDE e são ~12 no país inteiro, cabendo num dicionário; foto é da
             UNIDADE e são milhares — embuti-las no payload o levaria a centenas de MB. Por
             URL, o deck.gl empacota sozinho e o navegador guarda em cache.

             Quem decide QUAIS pinos entram é o servidor (`icone_foto`): ele sabe quais
             logos existem e aplica o teto do atlas. */
          (d.icone_foto && d.foto ? iconeDaFoto(d.foto) : undefined) ??
          (d.diag ? iconObjs[`${d.rede ?? ''}__diag`] : undefined) ??
          iconObjs[d.rede ?? ''] ??
          iconObjs.__ultra__,
        // A logo estava pequena demais para ser lida no mapa. A textura do atlas tem 128px
        // (PNG de origem 320x320), entao ha folga ate ~64px CSS sem upscaling — subir para
        // 30 (cap 34) so gasta resolucao que ja existia.
        // 38 contra 30 porque o SVG com halo tem viewBox 160 e nao 128: a razao 38/160 devolve o
        // QUADRADO no mesmo tamanho do pin sem halo (30/128). Sem isso o halo encolheria a marca.
        getSize: (d) => (d.diag ? 38 : 30),
        sizeUnits: 'pixels',
        sizeMinPixels: 10,
        sizeMaxPixels: 43,
        updateTriggers: { getIcon: [iconObjs], getSize: [] },
        pickable: true,
        onHover: (info) => {
          const p = info.object as Pin | undefined
          setPinHover(
            p
              ? {
                  titulo: p.label ?? p.rede ?? 'Concorrente',
                  sub: p.nome,
                  d: p,
                  x: info.x,
                  y: info.y,
                }
              : null,
          )
        },
      }),

      new IconLayer<Pin>({
        id: 'ultra-pins',
        data: pins?.ultra ?? [],
        getPosition: (d) => [d.lng, d.lat],
        getIcon: () => iconObjs.__ultra__,
        // Ultra segue um degrau acima do concorrente (PNG de origem 426x426; mesma folga
        // de textura de 128px), para continuar destacando a rede propria.
        getSize: 40,
        sizeUnits: 'pixels',
        sizeMinPixels: 14,
        sizeMaxPixels: 44,
        pickable: true,
        onHover: (info) => {
          const p = info.object as Pin | undefined
          setPinHover(p ? { titulo: 'Ultra Academia', sub: p.nome, x: info.x, y: info.y } : null)
        },
      }),
    ]

    /* Regua: linha A-B e as duas pontas. Fica no FIM de `base` para desenhar por cima
       de hexagono, cobertura e bandeiras — uma medicao escondida sob o choropleth nao
       serve para nada. */
    if (medicao) {
      const pontas = medicao.b ? [medicao.a, medicao.b] : [medicao.a]
      if (medicao.b) {
        base.push(
          new LineLayer<{ de: AlvoMedicao; para: AlvoMedicao }>({
            id: 'regua-linha',
            data: [{ de: medicao.a, para: medicao.b }],
            getSourcePosition: (d) => [d.de.lng, d.de.lat],
            getTargetPosition: (d) => [d.para.lng, d.para.lat],
            // CONTRARIO ao basemap: era o quase-branco fixo, que sobre o Positron
            // desaparecia — uma regua invisivel nao mede nada. No escuro `pele.selecao`
            // devolve o mesmo (238,243,248); o 235 de alfa e' preservado.
            getColor: [pele.selecao[0], pele.selecao[1], pele.selecao[2], 235],
            getWidth: 2.5,
            widthUnits: 'pixels',
            pickable: false,
          }) as unknown as LineLayer<Hex>,
        )
        /* O NUMERO VAI NO CANVAS, nao em HTML sobreposto.
           Duas tentativas em HTML falharam: este container e' `inset: 0` e a tela tem
           elementos que pintam por cima dele (o header do `MapScreen` no topo, o painel e
           a doca embaixo), entao a leitura ficava escondida com a linha desenhada e o
           numero invisivel. Desenhado pelo deck.gl, o rotulo e' parte do mapa e nenhuma
           camada de DOM o alcanca — e ainda fica ONDE o operador esta olhando, colado a
           medicao, em vez de num canto da tela. */
        const meio = {
          lat: (medicao.a.lat + medicao.b.lat) / 2,
          lng: (medicao.a.lng + medicao.b.lng) / 2,
        }
        base.push(
          new TextLayer<{ meio: typeof meio; texto: string }>({
            id: 'regua-rotulo',
            data: [{ meio, texto: distanciaCurta(distanciaMetros(medicao.a, medicao.b)) }],
            getPosition: (d) => [d.meio.lng, d.meio.lat],
            getText: (d) => d.texto,
            getSize: 15,
            sizeUnits: 'pixels',
            getColor: [8, 11, 16, 255],
            background: true,
            getBackgroundColor: [238, 243, 248, 240],
            backgroundPadding: [7, 4, 7, 4],
            getPixelOffset: [0, -14],
            fontWeight: 700,
            characterSet: 'auto',
            pickable: false,
          }) as unknown as TextLayer<Hex>,
        )
      }

      base.push(
        new ScatterplotLayer<AlvoMedicao>({
          id: 'regua-pontas',
          data: pontas,
          getPosition: (d) => [d.lng, d.lat],
          getRadius: 6,
          radiusUnits: 'pixels',
          radiusMinPixels: 5,
          getFillColor: [8, 11, 16, 235],
          getLineColor: [238, 243, 248, 255],
          lineWidthMinPixels: 2,
          stroked: true,
          pickable: false,
        }) as unknown as ScatterplotLayer<Hex>,
      )
    }

    // Ponto buscado: hexagono marcado + pin de DUAS camadas (anel na cor da selecao,
    // miolo no fundo do tema — no escuro anel claro/miolo escuro, no claro o inverso).
    // Buscar um endereco e' uma forma de SELECIONAR, entao vale a mesma cor do hex
    // selecionado e do item ativo do painel; o turquesa ficou exclusivo do cenario
    // multi-hex, que era a unica marcacao turquesa deliberada do mapa.
    if (pinNoMapa) {
      base.push(
        new H3HexagonLayer<{ id: string }>({
          id: 'search-hex',
          data: [{ id: pinNoMapa.hexId }],
          getHexagon: (d) => d.id,
          extruded: false,
          filled: true,
          stroked: true,
          /* Mesma razao da camada `hex`: o realce do ponto buscado tem de POUSAR
             exatamente sobre a celula de baixo. */
          highPrecision: true,
          getFillColor: pele.selecaoTenue,
          getLineColor: pele.selecao,
          getLineWidth: 3,
          lineWidthUnits: 'pixels',
          pickable: false,
        }) as unknown as H3HexagonLayer<Hex>,
      )
      base.push(
        new ScatterplotLayer<SearchPin>({
          id: 'search-pin-ring',
          data: [pinNoMapa],
          getPosition: (d) => [d.lng, d.lat],
          getRadius: 11,
          radiusUnits: 'pixels',
          getFillColor: pele.pinAnel,
          pickable: false,
        }) as unknown as ScatterplotLayer<Hex>,
      )
      base.push(
        new ScatterplotLayer<SearchPin>({
          id: 'search-pin-core',
          data: [pinNoMapa],
          getPosition: (d) => [d.lng, d.lat],
          getRadius: 6,
          radiusUnits: 'pixels',
          // Miolo no fundo do tema (--bg-base): o pin vira uma rosca em vez de uma
          // bolha chapada, e continua sem usar matiz nenhuma.
          getFillColor: pele.pinMiolo,
          pickable: false,
        }) as unknown as ScatterplotLayer<Hex>,
      )
    }

    // Numero do ranking, por ULTIMO para ficar acima dos pins. `pickable: false`
    // mantem o clique/hover chegando ao H3HexagonLayer por baixo.
    if (rotulosRank.length) {
      base.push(
        new TextLayer<RotuloRank>({
          id: 'rank-labels',
          data: rotulosRank,
          getPosition: (d) => d.position,
          getText: (d) => d.texto,
          getSize: 13,
          sizeUnits: 'pixels',
          fontFamily: "'IBM Plex Mono', ui-monospace, monospace", // --f-num
          fontWeight: 700,
          // O "º" do passo 5 esta fora do characterSet ASCII padrao do TextLayer.
          characterSet: 'auto',
          getColor: [238, 243, 248, 255],
          // Chip escuro: a rampa vai do azul ao vermelho, entao nenhuma cor de texto
          // sozinha fica legivel sobre todas as faixas — o fundo e' que garante o contraste.
          background: true,
          getBackgroundColor: [8, 11, 16, 214],
          // Borda na cor da CAMADA: o chip diz "01..10 desta camada" sem que
          // nenhuma cor toque o fill dos hexes (que segue 100% rampa de score).
          getBorderColor: [cor.rgb[0], cor.rgb[1], cor.rgb[2], 170],
          getBorderWidth: 1,
          backgroundPadding: [6, 4, 6, 4],
          backgroundBorderRadius: 5,
          pickable: false,
        }),
      )
    }

    return base
  }, [
    hexes,
    passo.n,
    cor,
    selecionado,
    destaque,
    cenarioSet,
    cenarioKey,
    onSelecionar,
    pinNoMapa,
    pins,
    iconObjs,
    rotulosRank,
    // PRECISAM estar aqui: o corpo do memo LE as duas para decidir se monta a camada de
    // cobertura. Sem elas, virar a chave nao reconstruia a lista de camadas e a cobertura
    // nunca chegava a existir — o mapa ficava identico e parecia que a camada nao
    // funcionava. Foi exatamente o sintoma relatado ("o hexagono so aparece de uma cor").
    raio1km,
    independentes,
    imoveis,
    onImovel,
    cobertura1k,
    hexesCobertos,
    hexPorId,
    // Mesmo motivo do bloco acima: o corpo LE as duas para montar (ou nao) a regua.
    medindo,
    medicao,
    // `pele` e `tema` andam juntos (um deriva do outro), mas os dois entram: `pele` é o
    // que o corpo do memo lê, e `tema` é o que vai nos `updateTriggers` das camadas.
    pele,
    tema,
  ])

  return (
    <div
      ref={caixaRef}
      onMouseLeave={() => {
        setHover(null)
        setPinHover(null)
        setIndepHover(null)
        setImovelHover(null)
      }}
      style={{
        position: 'absolute',
        inset: 0,
        background:
          'radial-gradient(120% 90% at 46% 42%, var(--bg-lift) 0%, var(--bg-base) 76%)',
      }}
    >
      {/* O DeckGL NÃO precisa de flag: no deck.gl v9 o `preserveDrawingBuffer` já é `true`
          por padrão (está escrito nos próprios tipos), então o canvas das camadas sempre
          foi capturável. Quem descarta o buffer é o BASEMAP — o MapLibre v5 usa
          `preserveDrawingBuffer: false` por padrão. Só ele é recriado na captura, o que
          torna o custo bem menor do que trocar o contexto dos dois. */}
      <DeckGL
        viewState={view}
        onViewStateChange={(e) => setView(e.viewState as ViewState)}
        controller={{ dragRotate: false }}
        layers={camadas}
        style={{ position: 'absolute', top: '0', left: '0', width: '100%', height: '100%' }}
        onClick={(info) => {
          // `info.coordinate` existe mesmo em clique no vazio do mapa — e' isso que
          // permite a ponta livre quando o clique nao cai perto de pin nenhum.
          if (medindo) medirNoClique(info.coordinate as number[] | undefined)
        }}
        getCursor={({ isHovering }) =>
          medindo ? 'crosshair' : isHovering ? 'pointer' : 'grab'
        }
      >
        {/* A `key` carrega DOIS motivos de remontagem, e os dois precisam estar nela.
            `capturando`: atributo de contexto WebGL não se troca num contexto já criado —
            só recriando; e `reuseMaps` sai de cena junto, porque reaproveitar a instância
            devolveria o canvas antigo, sem o buffer, e a imagem sairia branca.
            `tema`: trocar `mapStyle` no ar mantém as camadas do estilo antigo até o novo
            terminar de carregar, e as duas peles aparecem sobrepostas (mesma solução do
            `ExecMap`). */}
        <Map
          key={`${tema}|${capturando ? 'captura' : 'normal'}`}
          mapStyle={pele.basemap}
          attributionControl={{ compact: true }}
          reuseMaps={!capturando}
          canvasContextAttributes={{ preserveDrawingBuffer: capturando }}
        />

      </DeckGL>

      {hover && (
        <div
          role="tooltip"
          style={{
            position: 'absolute',
            ...ancora(hover.x, hover.y),
            pointerEvents: 'none',
            background: 'var(--surf-panel)',
            border: '1px solid var(--line-mid)',
            borderRadius: 'var(--r-md)',
            padding: '10px 12px',
            backdropFilter: 'blur(16px)',
            boxShadow: 'var(--sh-pop)',
            zIndex: 30,
            minWidth: 196,
          }}
        >
          {/* Cabecalho: o BAIRRO deste hexagono, com municipio/UF logo abaixo.
              Era Municipio / UF — a MESMA linha para todos os hexagonos da cidade, entao
              percorrer o mapa de Itaquaquecetuba mostrava "Itaquaquecetuba / SP" quinze
              vezes e o unico distintivo era o id H3, que ninguem le. O nome do bairro e' o
              que o painel da direita ja' usa; o tooltip passa a falar a mesma lingua. */}
          <div style={{ font: '600 12.5px/1.25 var(--f-ui)', color: 'var(--tx-max)' }}>
            {rotuloDoHex(hover.h)}
          </div>
          <div
            style={{ font: '500 10px/1.25 var(--f-ui)', color: 'var(--tx-sub)', marginTop: 2 }}
          >
            {/* Sem repetir: quando o titulo ja' e' o municipio, sobra so' a UF. */}
            {[hover.h.bairro ? municipio || hover.h.mun : null, uf].filter(Boolean).join(' / ')}
          </div>
          <div
            className="num"
            style={{ font: '500 9.5px/1 var(--f-num)', color: 'var(--tx-sub)', marginTop: 3 }}
          >
            {hover.h.id}
          </div>

          {hover.h.faixa && <Linha rotulo="Faixa M1" valor={hover.h.faixa} />}

          <Divisoria />
          {/* O score em destaque e o que colore o mapa NESTE passo (M1 / censo /
              residual) — informacao de CAMADA, entao vai na cor da camada. O M1
              destaca no passo 5 (a main renumerou: a sintese virou a quinta). */}
          <Linha
            rotulo="Score M1"
            valor={num(hover.h.m1, 1)}
            forte={passo.n === 5}
            cor={cor.fg}
          />
          <Linha
            rotulo="Score censitário"
            valor={num(hover.h.censo, 1)}
            forte={passo.n === 1}
            cor={cor.fg}
          />
          {hover.h.res !== null && (
            <Linha
              rotulo="Score residual"
              valor={num(hover.h.res, 1)}
              forte={passo.n === 2 || passo.n === 3}
              cor={cor.fg}
            />
          )}

          <Divisoria />
          <Linha rotulo="Habitantes" valor={num(hover.h.pop)} />
          <Linha rotulo="Renda per capita" valor={renda(hover.h.renda)} />
          {hover.h.renda_dom !== null && (
            <Linha rotulo="Renda domiciliar" valor={renda(hover.h.renda_dom)} />
          )}
          <Linha rotulo="Residual Fitness" valor={`${alunos(hover.h.oferta)} alunos`} />
          <Linha rotulo="Concorrentes 2 km" valor={num(hover.h.conc)} />
          {hover.h.ultra > 0 && <Linha rotulo="Unidade Ultra" valor={num(hover.h.ultra)} />}

          {/* PROTOTIPO — o rateio, hexagono a hexagono. E aqui que o modelo fica
              legivel: da' para ver que a concorrente da borda cobrou so' uma PARTE
              deste hexagono, e que o resto foi para o vizinho. */}
          {raio1km && hover.h.cons1k != null && (
            <>
              <Divisoria />
              <Linha
                rotulo="Perde p/ concorrentes (1 km)"
                valor={`${alunos(hover.h.cons1k)} alunos`}
                forte
              />
              <Linha
                rotulo="No modelo atual (2 km)"
                valor={`${alunos(hover.h.cons2k)} alunos`}
              />
              <Linha
                rotulo="Equivale a"
                valor={`${num((hover.h.cons1k ?? 0) / 2500, 2)} unidade(s)`}
              />
              <Linha rotulo="Concorrentes que alcançam" valor={num(hover.h.conc1k)} />
              <Linha
                rotulo="Residual recalculado"
                valor={`${alunos(hover.h.oferta1k)} alunos`}
                forte
              />
            </>
          )}

          {/* Passo 4 — como a cidade esta indo. Valores MUNICIPAIS. */}
          {passo.n === 4 && hover.h.cres_hex_classe && (
            <>
              <Divisoria />
              <Linha rotulo="Crescimento do hexágono" valor={hover.h.cres_hex_classe} forte />
              {hover.h.cres_hex_taxa !== null && (
                <Linha
                  rotulo="Área construída 16–23"
                  valor={
                    /* A taxa chega a +498.128% num hexagono com 1 pixel construido
                       em 2016. A classe satura, o numero cru nao — e ele destroi a
                       credibilidade do painel. Clamp na exibicao. */
                    hover.h.cres_hex_taxa > 999
                      ? '> +999%'
                      : `${hover.h.cres_hex_taxa >= 0 ? '+' : ''}${num(hover.h.cres_hex_taxa, 1)}%`
                  }
                />
              )}
            </>
          )}
          {/* O bloco municipal vem de `cresMun`, nao do hexagono: e o mesmo valor
              para a cidade inteira e repeti-lo em cada hex custava ~2,2 MB por UF. */}
          {passo.n === 4 && cresDoHex(hover.h) && (
            <BlocoMunicipal c={cresDoHex(hover.h)!} />
          )}
        </div>
      )}

      {/* Balao da INDEPENDENTE (BLK-MA-15). Vence o do concorrente e o do hexagono quando o
          cursor esta sobre um pin dela: e' o objeto mais especifico sob o mouse.

          O QUE ELE DIZ, e por que cada linha esta aqui:
            - o SCORE, com o selo de provisorio quando `flag_score_provisorio` — sem o selo, um
              numero que o G-D1 se recusa a ordenar pareceria um ranking;
            - a PRESSAO, medida da coordenada DESTA academia (grao unidade, DEC-029) — antes do
              BLK-MA-14 todas as academias do hexagono mostrariam o mesmo valor aqui;
            - nota e contagem SEMPRE juntas (DEC-026);
            - o REGIME, porque reguas de regimes diferentes nao se comparam entre si. */}
      {indepHover && (
        <div
          role="tooltip"
          style={{
            position: 'absolute',
            ...ancora(indepHover.x, indepHover.y, 190, 230),
            pointerEvents: 'none',
            background: 'var(--surf-panel)',
            border: '1px solid var(--line-mid)',
            borderRadius: 'var(--r-md)',
            padding: '9px 11px',
            backdropFilter: 'blur(16px)',
            boxShadow: '0 10px 30px -8px rgba(0,0,0,.7)',
            zIndex: 31,
            minWidth: 210,
          }}
        >
          <div style={{ font: '600 12.5px/1.25 var(--f-ui)', color: 'var(--tx-max)' }}>
            {indepHover.d.nome || 'Academia independente'}
          </div>
          <div style={{ font: '400 9.5px/1 var(--f-ui)', color: 'var(--tx-label)', marginTop: 3 }}>
            Academia independente
          </div>

          <Divisoria />
          {/* A DIREÇÃO VAI ESCRITA NOS DOIS NÚMEROS, e não é redundância de texto.

              No resto do piloto todo score segue a convenção "alto = melhor oportunidade de
              ABRIR" (M1, censitário, residual). Este mede o oposto: quanto MAIOR, mais cercada
              está a academia — o que é ruim para ela e bom para quem compra. Um número de 0 a 100
              sem eixo declarado, numa tela onde os vizinhos usam a convenção inversa, é lido ao
              contrário; foi exatamente o que aconteceu na revisão de 2026-08-14.

              O rótulo do composto NÃO diz "vulnerabilidade" (DEC-028, decisão 1): enquanto S3/S4
              estiverem imaturos, afirmar fragilidade da academia é vender o sinal 6 com o rótulo
              do 3. "Score composto" descreve o que ele é — a soma ponderada dos sinais
              disponíveis — sem afirmar o que ainda não se mediu. */}
          {indepHover.d.score !== null && (
            <Linha
              rotulo={indepHover.d.provisorio ? 'Score composto (provisório)' : 'Score composto'}
              valor={`${num(indepHover.d.score, 1)} / 100 ↑`}
              forte
              cor={cor.fg}
            />
          )}
          {indepHover.d.pressao !== null && (
            <Linha
              rotulo="Pressão competitiva"
              valor={`${num(indepHover.d.pressao, 1)} / 100 ↑`}
            />
          )}
          {/* A CONTA POR TRÁS DO NÚMERO (BLK-MA-18). Revisão de Vinicius: 40 pontos pareciam muito
              para uma vizinhança quase vazia — e a desconfiança estava certa. A saturação gasta
              METADE da escala numa única unidade equivalente, então `40,4` é `0,68 concorrentes
              efetivos`, não "40% de pressão". A régua não muda; o que muda é ela deixar de ser
              inverificável: o operador conta os pins no mapa e o número fecha. */}
          {indepHover.d.n_conc !== null && (
            <div
              style={{
                font: '400 9px/1.35 var(--f-ui)',
                color: 'var(--tx-label)',
                marginTop: 3,
                maxWidth: 236,
              }}
            >
              {indepHover.d.n_conc === 0
                ? 'nenhum concorrente num raio de 2 km'
                : `${num(indepHover.d.n_conc)} num raio de 2 km` +
                  (indepHover.d.n_indep !== null
                    ? ` (${num(indepHover.d.n_indep)} independente${indepHover.d.n_indep === 1 ? '' : 's'})`
                    : '')}
              {/* A TERCEIRA PARCELA (DEC-035). Sem ela a conta simplesmente nao fechava: as
                  unidades de rede vindas do agregador entram em `n_conc` e, quando colapsam contra
                  um pin do funil, nao ganham pin proprio. Medido: 28,2% das linhas tem esta parcela
                  maior que zero. Declarar quantas sao e' o que devolve a conferibilidade. */}
              {indepHover.d.n_cadeias_feed !== null &&
                indepHover.d.n_cadeias_feed > 0 &&
                `, ${num(indepHover.d.n_cadeias_feed)} de rede via agregador`}
              {indepHover.d.oferta !== null && indepHover.d.n_conc > 0 && (
                <>
                  {' · '}
                  <strong style={{ fontWeight: 600 }}>
                    {num(indepHover.d.oferta, 2)} equivalente
                    {indepHover.d.oferta === 1 ? '' : 's'}
                  </strong>{' '}
                  depois da distância
                </>
              )}
              {indepHover.d.dist_m !== null && indepHover.d.n_conc > 0 && (
                <>
                  <br />
                  mais próximo a {distanciaCurta(indepHover.d.dist_m)}
                </>
              )}
            </div>
          )}
          <div
            style={{
              font: '400 9px/1.35 var(--f-ui)',
              color: 'var(--tx-label)',
              marginTop: 5,
              maxWidth: 230,
            }}
          >
            ↑ maior = mais cercada por concorrentes
          </div>
          {indepHover.d.nota !== null && (
            <Linha
              rotulo="Nota WellHub"
              valor={`${num(indepHover.d.nota, 1)} · ${num(indepHover.d.n_aval)} aval.`}
            />
          )}
          {/* SINAIS MEDIDOS, por extenso. A linha mostrava o valor bruto (`s1,s6`), que e' enum
              do pipeline e nao diz nada a quem nao leu o contrato — e essa linha existe
              justamente para dizer SOB QUAL REGUA o numero foi composto, porque reguas de
              regimes diferentes nao se comparam entre si (emenda BLK-MA-04-FU1).

              Cada frase vem da coluna "direcao" do §8.1 e MANTEM a direcao, que e' o que
              permite ler o numero. Nenhuma delas afirma fragilidade da academia: descrevem o que
              foi medido, nao o veredito (DEC-028). */}
          {indepHover.d.regime && (
            <>
              <div
                style={{
                  font: '400 9.5px/1 var(--f-ui)',
                  color: 'var(--tx-label)',
                  marginTop: 8,
                  textTransform: 'uppercase',
                  letterSpacing: '.05em',
                }}
              >
                O que foi medido
              </div>
              {sinaisDoRegime(indepHover.d.regime).map((s) => (
                <div key={s.rotulo} style={{ marginTop: 4, maxWidth: 236 }}>
                  <div style={{ font: '600 10.5px/1.2 var(--f-ui)', color: 'var(--tx-soft)' }}>
                    {s.rotulo}
                  </div>
                  <div style={{ font: '400 9px/1.3 var(--f-ui)', color: 'var(--tx-label)' }}>
                    {s.explica}
                  </div>
                </div>
              ))}
            </>
          )}
          {/* DECLARA A REDUNDÂNCIA em vez de escondê-la. No regime `s1,s6` o composto é
              `30 + 40·v6` — o s1 vale 30 pontos FIXOS porque só um agregador existe em disco —,
              então os dois números têm correlação 1,0 e dizem a mesma coisa. Deixar isso implícito
              faria o operador procurar significado numa diferença que não existe. O composto passa
              a informar de verdade quando o churn (s3) amadurecer. */}
          {indepHover.d.regime === 's1,s6' && (
            <div
              style={{
                font: '400 9px/1.35 var(--f-ui)',
                color: 'var(--tx-label)',
                marginTop: 6,
                maxWidth: 230,
              }}
            >
              Hoje o composto acompanha a pressão: o outro sinal medido (presença em agregador) é
              igual para todas.
            </div>
          )}
          {indepHover.d.provisorio && (
            <div
              style={{
                font: '400 9.5px/1.35 var(--f-ui)',
                color: 'var(--tx-label)',
                marginTop: 7,
                maxWidth: 220,
              }}
            >
              Série ainda imatura: o número não ordena um ranking.
            </div>
          )}
        </div>
      )}

      {/* Balao do IMOVEL (camada imobiliaria): titulo, tipo com a cor categorica e os
          MESMOS 4 numeros do ranking da aba (Aluguel, Custo de ocupacao, Projecao de
          faturamento, Area). A ultima linha avisa que o clique abre o detalhe — o pin
          e' o unico ponto clicavel do mapa que NAO seleciona hexagono. */}
      {imovelHover && (
        <div
          role="tooltip"
          style={{
            position: 'absolute',
            ...ancora(imovelHover.x, imovelHover.y, 190, 240),
            pointerEvents: 'none',
            background: 'var(--surf-panel)',
            border: '1px solid var(--line-mid)',
            borderRadius: 'var(--r-md)',
            padding: '9px 11px',
            backdropFilter: 'blur(16px)',
            boxShadow: '0 10px 30px -8px rgba(0,0,0,.7)',
            zIndex: 31,
            minWidth: 216,
            maxWidth: 256,
          }}
        >
          <div style={{ font: '600 12.5px/1.25 var(--f-ui)', color: 'var(--tx-max)' }}>
            {imovelHover.d.titulo}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 3 }}>
            <span
              style={{
                width: 7,
                height: 7,
                borderRadius: 2,
                background: corTipo(imovelHover.d.tipo),
                flexShrink: 0,
              }}
            />
            <span style={{ font: '400 10px/1.2 var(--f-ui)', color: 'var(--tx-sub)' }}>
              {labelTipo(imovelHover.d.tipo)}
              {imovelHover.d.bairro ? ` · ${imovelHover.d.bairro}` : ` · ${imovelHover.d.municipio}`}
            </span>
          </div>

          <Divisoria />
          <Linha
            rotulo="Aluguel"
            valor={
              imovelHover.d.aluguel == null
                ? '—'
                : `${brl(imovelHover.d.aluguel)}${
                    rsM2(imovelHover.d) != null ? ` · R$ ${num(rsM2(imovelHover.d), 0)}/m²` : ''
                  }`
            }
          />
          <Linha
            rotulo="Custo de ocupação"
            valor={custoOcup(imovelHover.d) > 0 ? brl(custoOcup(imovelHover.d)) : '—'}
          />
          <Linha
            rotulo="Projeção de fat."
            valor={imovelHover.d.fat_proj == null ? '—' : `${brl(imovelHover.d.fat_proj, true)}/mês`}
            forte
            cor="var(--pos-text)"
          />
          <Linha
            rotulo="Área"
            valor={imovelHover.d.area == null ? '—' : `${num(imovelHover.d.area)} m²`}
          />
          <div
            style={{ font: '400 9px/1.35 var(--f-ui)', color: 'var(--tx-label)', marginTop: 6 }}
          >
            clique no ponto para abrir os detalhes
          </div>
        </div>
      )}

      {pinHover && !hover && !indepHover && !imovelHover && (
        <div
          role="tooltip"
          style={{
            position: 'absolute',
            ...ancora(pinHover.x, pinHover.y, 96, 200),
            pointerEvents: 'none',
            background: 'var(--surf-panel)',
            border: '1px solid var(--line-mid)',
            borderRadius: 'var(--r-md)',
            padding: '7px 10px',
            backdropFilter: 'blur(16px)',
            boxShadow: 'var(--sh-pop)',
            zIndex: 30,
            maxWidth: 240,
          }}
        >
          {/* FOTO DA UNIDADE, quando a base a trouxe (pedido do Juan, 2026-08-26).
              Vem ANTES do nome, como capa: quem passa o mouse quer reconhecer a casa, e a
              foto faz isso mais rapido que o texto. `onError` esconde a imagem em vez de
              deixar o icone de quebrado — a base pode citar um arquivo que sumiu, e um
              retangulo vazio le pior que nenhum. `loading="lazy"` porque o balao troca a
              cada pino sob o cursor: sem isso, arrastar o mouse pelo mapa dispararia uma
              requisicao por unidade tocada. */}
          {pinHover.d?.foto && (
            <img
              src={`/api/foto-concorrente/${encodeURIComponent(pinHover.d.foto)}`}
              alt=""
              loading="lazy"
              onError={(e) => {
                e.currentTarget.style.display = 'none'
              }}
              style={{
                display: 'block',
                width: '100%',
                height: 96,
                objectFit: 'cover',
                borderRadius: 'var(--r-sm)',
                marginBottom: 7,
                background: 'var(--surf-raised)',
              }}
            />
          )}
          <div style={{ font: '600 12px/1.2 var(--f-ui)', color: 'var(--tx-max)' }}>
            {pinHover.titulo}
          </div>
          {pinHover.sub && (
            <div
              style={{
                font: '400 11px/1.3 var(--f-ui)',
                color: 'var(--tx-sub)',
                marginTop: 2,
              }}
            >
              {pinHover.sub}
            </div>
          )}

          {/* O QUE O HALO PROMETE. A bandeira com halo diz "temos dado extra sobre esta unidade";
              se o balao nao entregasse, o halo seria enfeite. Aqui vem a pressao medida da
              coordenada DELA e a conta por tras do numero.

              Repare no que NAO aparece: score composto. Numa rede, presenca em agregador e churn
              medem negociacao da MARCA, nao fragilidade desta unidade -- o S3 e' correlacionado
              (top 5 = 48,4% das unidades, max 440 numa rede), entao a Panobianco saindo do WellHub
              viraria 440 alvos no mesmo dia. O S6 passa porque e' geografico. (DEC-035) */}
          {pinHover.d?.diag && (
            <>
              <Divisoria />
              {pinHover.d.pressao != null && (
                <Linha
                  rotulo="Pressão competitiva"
                  valor={`${num(pinHover.d.pressao, 1)} / 100 ↑`}
                  forte
                />
              )}
              {pinHover.d.n_conc != null && (
                <div
                  style={{
                    font: '400 9px/1.35 var(--f-ui)',
                    color: 'var(--tx-label)',
                    marginTop: 3,
                    maxWidth: 224,
                  }}
                >
                  {pinHover.d.n_conc === 0
                    ? 'nenhum concorrente num raio de 2 km'
                    : `${num(pinHover.d.n_conc)} num raio de 2 km` +
                      (pinHover.d.n_indep != null
                        ? ` (${num(pinHover.d.n_indep)} independente${pinHover.d.n_indep === 1 ? '' : 's'})`
                        : '')}
                  {pinHover.d.oferta != null && pinHover.d.n_conc > 0 && (
                    <>
                      {' · '}
                      <strong style={{ fontWeight: 600 }}>
                        {num(pinHover.d.oferta, 2)} equivalente
                        {pinHover.d.oferta === 1 ? '' : 's'}
                      </strong>{' '}
                      depois da distância
                    </>
                  )}
                  {pinHover.d.dist_m != null && pinHover.d.n_conc > 0 && (
                    <>
                      <br />
                      mais próximo a {distanciaCurta(pinHover.d.dist_m)}
                    </>
                  )}
                </div>
              )}
              {pinHover.d.nota != null && (
                <Linha
                  rotulo="Nota no WellHub"
                  valor={`${num(pinHover.d.nota, 1)}${
                    pinHover.d.n_aval != null ? ` (${num(pinHover.d.n_aval)} avaliações)` : ''
                  }`}
                />
              )}
              {pinHover.d.churn && (
                <Linha
                  rotulo="Presença na série"
                  valor={ROTULO_CHURN[pinHover.d.churn] ?? pinHover.d.churn}
                />
              )}
              <div
                style={{
                  font: '400 9px/1.35 var(--f-ui)',
                  color: 'var(--tx-label)',
                  marginTop: 6,
                  maxWidth: 224,
                }}
              >
                Listada num agregador — daí o dado extra. Sem score composto: numa rede, presença e
                churn medem negociação da marca, não fragilidade desta unidade.
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}

function Divisoria() {
  return (
    <div
      aria-hidden
      style={{ height: 1, background: 'var(--line-soft)', margin: '7px 0 1px' }}
    />
  )
}

/** `cor` e' a cor do valor em DESTAQUE (cor da camada ativa); default neutro. */
function Linha({
  rotulo,
  valor,
  forte,
  cor = 'var(--tx-max)',
}: {
  rotulo: string
  valor: string
  forte?: boolean
  cor?: string
}) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, marginTop: 5 }}>
      <span style={{ font: '400 11.5px/1 var(--f-ui)', color: 'var(--tx-label)' }}>{rotulo}</span>
      <span
        className="num"
        style={{
          font: `${forte ? 700 : 500} 11.5px/1 var(--f-num)`,
          color: forte ? cor : 'var(--tx-soft)',
        }}
      >
        {valor}
      </span>
    </div>
  )
}
