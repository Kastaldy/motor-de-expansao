import { FlyToInterpolator, type Layer } from '@deck.gl/core'
import { H3HexagonLayer } from '@deck.gl/geo-layers'
import { IconLayer, ScatterplotLayer } from '@deck.gl/layers'
import DeckGL from '@deck.gl/react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Map } from 'react-map-gl/maplibre'
import 'maplibre-gl/dist/maplibre-gl.css'

import { alunos, brl, num } from '../lib/format'
import {
  DISCARDED_FILL,
  HEX_FILL_ALPHA,
  NAN_SCORE_FILL,
  POP_MIN_ACIONAVEL,
  scoreBandToColor,
  type RGBA,
} from '../lib/colors'
import type { Hex, Passo, Pin, Pins } from '../lib/types'

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
  if (passoN === 4) return h.m1 // score_priorizacao
  return h.res // score_oportunidade_residual
}

/** Opacidade relativa dos hexes FORA do passo atual. O funil vira um holofote nos
 *  hexes da camada — sem precisar de borda colorida (pedido do Felipe: tirar as
 *  bordas azuis). Sem isso, as 10 aberturas do passo 4 sumiriam no meio do mapa. */
const DIM_FORA_DO_PASSO = 0.5

/** Precedencia do dashboard: pop<5k vence, senao NaN, senao faixa de score.
 *  Hexes fora do passo atual entram esmaecidos (holofote no funil). */
function fillDoHex(h: Hex, passoN: number, noPasso: boolean): RGBA {
  let base: RGBA
  if (h.pop !== null && h.pop < POP_MIN_ACIONAVEL) base = [...DISCARDED_FILL]
  else {
    const score = scoreDoPasso(h, passoN)
    base = score === null ? [...NAN_SCORE_FILL] : scoreBandToColor(score, HEX_FILL_ALPHA)
  }
  if (noPasso) return base
  return [base[0], base[1], base[2], Math.round(base[3] * DIM_FORA_DO_PASSO)]
}

export interface HexMapProps {
  hexes: Hex[]
  passo: Passo
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
}

interface ViewState {
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
  centro,
  municipio,
  uf,
  pins,
  selecionado,
  cenario,
  onSelecionar,
  searchPin,
}: HexMapProps) {
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

  const [view, setView] = useState<ViewState>(() => ({
    longitude: centro.lng ?? -47.9,
    latitude: centro.lat ?? -15.78,
    zoom: 9.6,
    pitch: 0,
    bearing: 0,
  }))

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

  // Voa e aproxima quando um ponto e buscado.
  useEffect(() => {
    if (!searchPin) return
    setView((v) => ({
      ...v,
      longitude: searchPin.lng,
      latitude: searchPin.lat,
      zoom: Math.max(13, v.zoom),
      transitionDuration: 800,
      transitionInterpolator: FLY,
    }))
  }, [searchPin])

  const destaque = useMemo(() => new Set(passo.hexes), [passo.hexes])
  const cenarioSet = useMemo(() => new Set(cenario ?? []), [cenario])
  const cenarioKey = (cenario ?? []).join(',')

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
        getSize: 16,
        sizeUnits: 'pixels',
        sizeMinPixels: 10,
        sizeMaxPixels: 20,
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
        getSize: 23,
        sizeUnits: 'pixels',
        sizeMinPixels: 14,
        sizeMaxPixels: 28,
        pickable: true,
        onHover: (info) => {
          const p = info.object as Pin | undefined
          setPinHover(p ? { titulo: 'Ultra Academia', sub: p.nome, x: info.x, y: info.y } : null)
        },
      }),
    ]

    // Ponto buscado: hexagono marcado + pin (anel branco + miolo turquesa).
    if (searchPin) {
      base.push(
        new H3HexagonLayer<{ id: string }>({
          id: 'search-hex',
          data: [{ id: searchPin.hexId }],
          getHexagon: (d) => d.id,
          extruded: false,
          filled: true,
          stroked: true,
          getFillColor: [53, 201, 214, 55],
          getLineColor: [125, 227, 236, 255],
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
          getFillColor: [53, 201, 214, 255],
          pickable: false,
        }) as unknown as ScatterplotLayer<Hex>,
      )
    }

    return base
  }, [
    hexes,
    passo.n,
    selecionado,
    destaque,
    cenarioSet,
    cenarioKey,
    onSelecionar,
    searchPin,
    pins,
    iconObjs,
  ])

  return (
    <div
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
            left: hover.x + 14,
            top: hover.y + 14,
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
          {/* O score em destaque e o que colore o mapa NESTE passo (M1 / censo / residual) */}
          <Linha rotulo="Score M1" valor={num(hover.h.m1, 1)} forte={passo.n === 4} />
          <Linha rotulo="Score censitário" valor={num(hover.h.censo, 1)} forte={passo.n === 1} />
          {hover.h.res !== null && (
            <Linha
              rotulo="Score residual"
              valor={num(hover.h.res, 1)}
              forte={passo.n === 2 || passo.n === 3}
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
        </div>
      )}

      {pinHover && !hover && (
        <div
          role="tooltip"
          style={{
            position: 'absolute',
            left: pinHover.x + 14,
            top: pinHover.y + 14,
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

function Linha({ rotulo, valor, forte }: { rotulo: string; valor: string; forte?: boolean }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, marginTop: 5 }}>
      <span style={{ font: '400 11.5px/1 var(--f-ui)', color: 'var(--tx-label)' }}>{rotulo}</span>
      <span
        className="num"
        style={{
          font: `${forte ? 700 : 500} 11.5px/1 var(--f-num)`,
          color: forte ? 'var(--ac-text)' : 'var(--tx-soft)',
        }}
      >
        {valor}
      </span>
    </div>
  )
}
