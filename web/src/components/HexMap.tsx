import { FlyToInterpolator, type Layer } from '@deck.gl/core'
import { H3HexagonLayer } from '@deck.gl/geo-layers'
import { IconLayer, PolygonLayer, ScatterplotLayer, TextLayer } from '@deck.gl/layers'
import DeckGL from '@deck.gl/react'
import { cellToLatLng } from 'h3-js'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Map } from 'react-map-gl/maplibre'
import 'maplibre-gl/dist/maplibre-gl.css'

import { alunos, brl, distanciaCurta, num } from '../lib/format'
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
import type {
  Cobertura1k,
  CrescimentoMunicipal,
  Hex,
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

/* ---------------------------------------------------------------------------
   Mapa de hexagonos H3 res-7 sobre basemap MapLibre.

   Coloracao FIEL ao dashboard Streamlit (CLAUDE.md §5): faixas de 10 pontos via
   RESIDUAL_SCORE_BANDS (score_band_to_color), corte de <5k hab em cinza e score
   NaN com fill proprio. A opacidade e mais baixa que a do dashboard para as ruas
   do basemap respirarem por baixo (pedido do Felipe).

   Basemap CARTO Dark Matter (online, fallback ao gradiente se faltar rede).
   --------------------------------------------------------------------------- */

const BASEMAP_STYLE =
  'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'

const FLY = new FlyToInterpolator({ speed: 1.6 })

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

/** Alpha das pecas de cobertura = o MESMO do hexagono normal (`HEX_FILL_ALPHA`).
 *  Usar um alpha maior fazia o recorte parecer outra paleta, mais saturada que o resto
 *  do mapa. A leitura tem de ser a de sempre: a cor sai da mesma regua de faixas, e o
 *  que muda entre a parte livre e a coberta e' o SCORE, nao a intensidade da tinta. */
const ALPHA_COBERTURA = HEX_FILL_ALPHA

/** Alpha de UMA sombra de concorrente. Baixo de proposito: o efeito e' CUMULATIVO.
 *  Com 34, uma concorrente escurece ~13%, duas ~25%, tres ~35%, e um aglomerado satura
 *  em quase preto — que e' a leitura desejada ("quanto mais concorrente, mais escuro").
 *  Alto demais e a primeira sombra ja mataria a cor da faixa embaixo. */
const ALPHA_SOMBRA = 34

/** Precedencia do dashboard: pop<5k vence, senao NaN, senao faixa de score.
 *  Hexes fora do passo atual entram esmaecidos (holofote no funil).
 *  Com `raio1km` ligado nos passos 2/3, a contagem de concorrentes vem ANTES de tudo. */
function fillDoHex(h: Hex, passoN: number, noPasso: boolean, raio1km = false): RGBA {
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
    base = h.faixa ? faixaM1ToColor(h.faixa, HEX_FILL_ALPHA) : [...NAN_SCORE_FILL]
  } else {
    const score = scoreDoPasso(h, passoN, raio1km)
    base = score === null ? [...NAN_SCORE_FILL] : scoreBandToColor(score, HEX_FILL_ALPHA)
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
  /** Hexes do cenário multi-hex (contorno turquesa de seleção). */
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
  /** PROTOTIPO: area coberta pelo raio, ja recortada dentro dos hexagonos. */
  cobertura1k?: Cobertura1k | null
  cameraInicial?: ViewState | null
  /** Reporta a camera ao pai a cada mudanca, para sobreviver ao unmount da tela. */
  onCamera?: (v: ViewState) => void
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
  searchPin,
  raio1km = false,
  independentes,
  cobertura1k,
  cameraInicial,
  onCamera,
}: HexMapProps) {
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

  // Ícones deck.gl memoizados por rede (identidade estável evita re-pack do atlas).
  const iconObjs = useMemo(() => {
    const m: Record<string, IconeDeck> = {}
    for (const [rede, url] of Object.entries(pins?.icones ?? {})) m[rede] = iconeDeck(url)
    return m
  }, [pins?.icones])

  // Camera restaurada tem precedencia sobre o centro do municipio: e' ela que devolve
  // o enquadramento de antes quando o operador volta do estudo pontual.
  const [view, setView] = useState<ViewState>(
    () =>
      cameraInicial ?? {
        longitude: centro.lng ?? -47.9,
        latitude: centro.lat ?? -15.78,
        zoom: 9.6,
        pitch: 0,
        bearing: 0,
      },
  )

  // Sobe a camera para o pai a cada mudanca. Sem isso ela morre no unmount da tela
  // (App troca `mapa` por `viabilidade` com render condicional, o que DESMONTA a arvore).
  // Cobre todos os caminhos que mexem em `view`: arraste do usuario e os dois voos
  // automaticos. `onCamera` PRECISA ser estavel no pai (useCallback) — com callback
  // inline, a identidade nova a cada render faria isto disparar em todo render.
  useEffect(() => {
    onCamera?.(view)
  }, [view, onCamera])

  // Voa para o centro do municipio quando ele muda.
  const centroKey = `${centro.lat},${centro.lng}`
  const centroAnterior = useRef(centroKey)
  useEffect(() => {
    if (centro.lat == null || centro.lng == null) return
    if (centroAnterior.current === centroKey) return
    centroAnterior.current = centroKey
    setView((v) => ({
      ...v,
      longitude: centro.lng!,
      latitude: centro.lat!,
      zoom: 9.6,
      transitionDuration: 700,
      transitionInterpolator: FLY,
    }))
  }, [centroKey, centro.lat, centro.lng])

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
      zoom: Math.max(13, v.zoom),
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

  // Cor da camada ativa: veste o "score forte" do tooltip e a borda do rotulo de
  // rank. Os dois dizem "isto e' da camada N" — antes diziam em turquesa, a mesma
  // cor do cenario multi-hex e do pin de busca na MESMA superficie.
  const cor = camadaCor(passo.n)

  const destaque = useMemo(() => new Set(passo.hexes), [passo.hexes])
  const cenarioSet = useMemo(() => new Set(cenario ?? []), [cenario])
  const cenarioKey = (cenario ?? []).join(',')

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

  const camadas = useMemo(() => {
    const base: Layer[] = [
      new H3HexagonLayer<Hex>({
        id: `hex-${passo.n}`,
        data: hexes,
        getHexagon: (d) => d.id,
        extruded: false,
        filled: true,
        stroked: true,
        getFillColor: (d) => {
          const comRaio = raio1km && PASSOS_DA_PRESSAO.has(passo.n)
          // Transparente onde a cobertura ja pinta o hexagono inteiro (ver `hexesCobertos`).
          if (comRaio && hexesCobertos.has(d.id)) return [0, 0, 0, 0]
          return fillDoHex(d, passo.n, destaque.has(d.id), comRaio)
        },
        // Borda neutra e fina; hex SELECIONADO -> contorno claro; hexes do CENÁRIO
        // multi-hex -> contorno turquesa (seleção deliberada, não o funil).
        getLineColor: (d) =>
          d.id === selecionado
            ? [238, 243, 248, 255]
            : cenarioSet.has(d.id)
              ? [53, 201, 214, 255]
              : [8, 11, 16, 55],
        getLineWidth: (d) => (d.id === selecionado ? 55 : cenarioSet.has(d.id) ? 42 : 6),
        lineWidthUnits: 'meters',
        lineWidthMinPixels: 0.5,
        pickable: true,
        autoHighlight: true,
        highlightColor: [236, 240, 245, 40],
        onClick: (info) => {
          if (info.object) onSelecionar(info.object as Hex)
        },
        onHover: (info) => {
          setHover(
            info.object ? { h: info.object as Hex, x: info.x, y: info.y } : null,
          )
        },
        updateTriggers: {
          getFillColor: [passo.n, raio1km, hexesCobertos],
          getLineColor: [selecionado, cenarioKey],
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
              getFillColor: (d) => scoreBandToColor(d.score, ALPHA_COBERTURA),
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
              updateTriggers: { getFillColor: [passo.n] },
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

      /* INDEPENDENTES (BLK-MA-15): circulo, nao bandeira. Elas nao tem marca — sao academias
         de bairro —, entao nao ha logo a exibir, e um icone generico competiria visualmente com
         as bandeiras das cadeias sem acrescentar informacao.

         COR UNICA, de proposito. A tentacao e' colorir por score, mas isso exigiria uma regua
         nova sobre a rampa de 10 faixas que ja colore os hexagonos por baixo — duas escalas de
         cor na mesma tela, medindo coisas diferentes, e' o defeito que o repo ja registrou como
         "dois idiomas". O numero vive no tooltip, onde tem rotulo e contexto. Desenhadas ANTES
         dos concorrentes e da Ultra: onde houver sobreposicao, quem manda na leitura e' a rede
         instalada. */
      ...(independentes?.length
        ? [
            new ScatterplotLayer<PinIndependente>({
              id: 'independentes-pins',
              data: independentes,
              getPosition: (d) => [d.lng ?? 0, d.lat ?? 0],
              getRadius: 5,
              radiusUnits: 'pixels',
              radiusMinPixels: 3,
              radiusMaxPixels: 8,
              getFillColor: [232, 102, 60, 205],
              stroked: true,
              getLineColor: [16, 20, 28, 210],
              lineWidthUnits: 'pixels',
              getLineWidth: 1,
              pickable: true,
              onHover: (info) => {
                const d = info.object as PinIndependente | undefined
                setIndepHover(d ? { d, x: info.x, y: info.y } : null)
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
        getIcon: (d) => iconObjs[d.rede ?? ''] ?? iconObjs.__ultra__,
        // A logo estava pequena demais para ser lida no mapa. A textura do atlas tem 128px
        // (PNG de origem 320x320), entao ha folga ate ~64px CSS sem upscaling — subir para
        // 30 (cap 34) so gasta resolucao que ja existia.
        getSize: 30,
        sizeUnits: 'pixels',
        sizeMinPixels: 10,
        sizeMaxPixels: 34,
        pickable: true,
        onHover: (info) => {
          const p = info.object as Pin | undefined
          setPinHover(
            p ? { titulo: p.label ?? p.rede ?? 'Concorrente', sub: p.nome, x: info.x, y: info.y } : null,
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

    // Ponto buscado: hexagono marcado + pin em BRANCO (anel claro, miolo escuro).
    // Buscar um endereco e' uma forma de SELECIONAR, entao vale a mesma cor do hex
    // selecionado e do item ativo do painel; o turquesa ficou exclusivo do cenario
    // multi-hex, que era a unica marcacao turquesa deliberada do mapa.
    if (searchPin) {
      base.push(
        new H3HexagonLayer<{ id: string }>({
          id: 'search-hex',
          data: [{ id: searchPin.hexId }],
          getHexagon: (d) => d.id,
          extruded: false,
          filled: true,
          stroked: true,
          getFillColor: [238, 243, 248, 45],
          getLineColor: [238, 243, 248, 255],
          getLineWidth: 3,
          lineWidthUnits: 'pixels',
          pickable: false,
        }) as unknown as H3HexagonLayer<Hex>,
      )
      base.push(
        new ScatterplotLayer<SearchPin>({
          id: 'search-pin-ring',
          data: [searchPin],
          getPosition: (d) => [d.lng, d.lat],
          getRadius: 11,
          radiusUnits: 'pixels',
          getFillColor: [255, 255, 255, 240],
          pickable: false,
        }) as unknown as ScatterplotLayer<Hex>,
      )
      base.push(
        new ScatterplotLayer<SearchPin>({
          id: 'search-pin-core',
          data: [searchPin],
          getPosition: (d) => [d.lng, d.lat],
          getRadius: 6,
          radiusUnits: 'pixels',
          // Miolo no fundo do tema (--bg-base): o pin vira uma rosca branca em vez
          // de uma bolha chapada, e continua sem usar matiz nenhuma.
          getFillColor: [8, 11, 16, 255],
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
    searchPin,
    pins,
    iconObjs,
    rotulosRank,
    // PRECISAM estar aqui: o corpo do memo LE as duas para decidir se monta a camada de
    // cobertura. Sem elas, virar a chave nao reconstruia a lista de camadas e a cobertura
    // nunca chegava a existir — o mapa ficava identico e parecia que a camada nao
    // funcionava. Foi exatamente o sintoma relatado ("o hexagono so aparece de uma cor").
    raio1km,
    independentes,
    cobertura1k,
    hexesCobertos,
    hexPorId,
  ])

  return (
    <div
      ref={caixaRef}
      onMouseLeave={() => {
        setHover(null)
        setPinHover(null)
        setIndepHover(null)
      }}
      style={{
        position: 'absolute',
        inset: 0,
        background:
          'radial-gradient(120% 90% at 46% 42%, var(--bg-lift) 0%, var(--bg-base) 76%)',
      }}
    >
      <DeckGL
        viewState={view}
        onViewStateChange={(e) => setView(e.viewState as ViewState)}
        controller={{ dragRotate: false }}
        layers={camadas}
        style={{ position: 'absolute', top: '0', left: '0', width: '100%', height: '100%' }}
        getCursor={({ isHovering }) => (isHovering ? 'pointer' : 'grab')}
      >
        <Map mapStyle={BASEMAP_STYLE} attributionControl={{ compact: true }} reuseMaps />

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
            boxShadow: '0 10px 30px -8px rgba(0,0,0,.7)',
            zIndex: 30,
            minWidth: 196,
          }}
        >
          {/* Cabecalho: Municipio / UF, com o hex id como legenda (como o Streamlit) */}
          <div style={{ font: '600 12.5px/1.25 var(--f-ui)', color: 'var(--tx-max)' }}>
            {municipio ? `${municipio}${uf ? ` / ${uf}` : ''}` : hover.h.id}
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
          <Linha rotulo="Renda per capita" valor={brl(hover.h.renda)} />
          {hover.h.renda_dom !== null && (
            <Linha rotulo="Renda domiciliar" valor={brl(hover.h.renda_dom)} />
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

      {pinHover && !hover && !indepHover && (
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
            boxShadow: '0 10px 30px -8px rgba(0,0,0,.7)',
            zIndex: 30,
            maxWidth: 240,
          }}
        >
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
