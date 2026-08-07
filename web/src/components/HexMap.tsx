import { FlyToInterpolator, type Layer } from '@deck.gl/core'
import { H3HexagonLayer } from '@deck.gl/geo-layers'
import { IconLayer, ScatterplotLayer, TextLayer } from '@deck.gl/layers'
import DeckGL from '@deck.gl/react'
import { cellToLatLng } from 'h3-js'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Map } from 'react-map-gl/maplibre'
import 'maplibre-gl/dist/maplibre-gl.css'

import { alunos, brl, num } from '../lib/format'
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
import type { CrescimentoMunicipal, Hex, Passo, Pin, Pins } from '../lib/types'

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

function scoreDoPasso(h: Hex, passoN: number): number | null {
  if (passoN === 1) return h.censo // score_setor_2022_calibrado
  if (passoN === 5) return h.m1 // score_priorizacao
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

/** Precedencia do dashboard: pop<5k vence, senao NaN, senao faixa de score.
 *  Hexes fora do passo atual entram esmaecidos (holofote no funil). */
function fillDoHex(h: Hex, passoN: number, noPasso: boolean): RGBA {
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
    const score = scoreDoPasso(h, passoN)
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
  searchPin: SearchPin | null
  /**
   * Camera preservada de uma visita anterior ao mapa (ida e volta pela Viabilidade).
   * Quando vem preenchida, o mapa REABRE nela em vez de recomecar no centro do
   * municipio com zoom 9.6 — e o voo automatico ate o `searchPin` e' suprimido no
   * primeiro render, senao ele sobrescreveria justamente o enquadramento restaurado.
   */
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
  searchPin,
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
  // O ref e' consumido no PRIMEIRO run do efeito, com ou sem pin. Consumi-lo so' quando
  // ha pin deixaria a flag armada: uma busca feita depois (mapa restaurado sem pin)
  // cairia no `return` e o mapa nao voaria para o endereco pesquisado.
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

  const camadas = useMemo(() => {
    const base: Layer[] = [
      new H3HexagonLayer<Hex>({
        id: `hex-${passo.n}`,
        data: hexes,
        getHexagon: (d) => d.id,
        extruded: false,
        filled: true,
        stroked: true,
        getFillColor: (d) => fillDoHex(d, passo.n, destaque.has(d.id)),
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
          getFillColor: [passo.n],
          getLineColor: [selecionado, cenarioKey],
          getLineWidth: [selecionado, cenarioKey],
        },
        transitions: { getFillColor: 260 },
      }),

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
  ])

  return (
    <div
      ref={caixaRef}
      onMouseLeave={() => {
        setHover(null)
        setPinHover(null)
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

      {pinHover && !hover && (
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
