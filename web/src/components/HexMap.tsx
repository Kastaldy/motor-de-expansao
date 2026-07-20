import { FlyToInterpolator } from '@deck.gl/core'
import { H3HexagonLayer } from '@deck.gl/geo-layers'
import { ScatterplotLayer } from '@deck.gl/layers'
import DeckGL from '@deck.gl/react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Map } from 'react-map-gl/maplibre'
import 'maplibre-gl/dist/maplibre-gl.css'

import { alunos, num } from '../lib/format'
import {
  DISCARDED_FILL,
  HEX_FILL_ALPHA,
  NAN_SCORE_FILL,
  POP_MIN_ACIONAVEL,
  scoreBandToColor,
  type RGBA,
} from '../lib/colors'
import type { Hex, Passo } from '../lib/types'

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

/** Precedencia do dashboard: pop<5k vence, senao NaN, senao faixa de score. */
function fillDoHex(h: Hex, passoN: number): RGBA {
  if (h.pop !== null && h.pop < POP_MIN_ACIONAVEL) return [...DISCARDED_FILL]
  const score = scoreDoPasso(h, passoN)
  if (score === null) return [...NAN_SCORE_FILL]
  return scoreBandToColor(score, HEX_FILL_ALPHA)
}

export interface HexMapProps {
  hexes: Hex[]
  passo: Passo
  centro: { lat: number | null; lng: number | null }
  selecionado: string | null
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
  selecionado,
  onSelecionar,
  searchPin,
}: HexMapProps) {
  const [hover, setHover] = useState<{ h: Hex; x: number; y: number } | null>(null)

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

  const camadas = useMemo(() => {
    const base = [
      new H3HexagonLayer<Hex>({
        id: `hex-${passo.n}`,
        data: hexes,
        getHexagon: (d) => d.id,
        extruded: false,
        filled: true,
        stroked: true,
        getFillColor: (d) => fillDoHex(d, passo.n),
        getLineColor: (d) => {
          if (d.id === selecionado) return [238, 243, 248, 255]
          if (destaque.has(d.id)) return [53, 201, 214, 210]
          return [8, 11, 16, 60]
        },
        getLineWidth: (d) =>
          d.id === selecionado ? 55 : destaque.has(d.id) ? 32 : 6,
        lineWidthUnits: 'meters',
        lineWidthMinPixels: 0.5,
        pickable: true,
        autoHighlight: true,
        highlightColor: [53, 201, 214, 80],
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
          getLineColor: [selecionado, passo.n],
          getLineWidth: [selecionado, passo.n],
        },
        transitions: { getFillColor: 260 },
      }),

      new ScatterplotLayer<Hex>({
        id: 'ultra',
        data: hexes.filter((h) => h.ultra > 0),
        getPosition: (d) => [d.lng, d.lat],
        getRadius: 240,
        radiusUnits: 'meters',
        radiusMinPixels: 4,
        radiusMaxPixels: 11,
        getFillColor: [200, 0, 30, 240],
        getLineColor: [255, 255, 255, 230],
        lineWidthMinPixels: 1.5,
        stroked: true,
        pickable: false,
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
  }, [hexes, passo.n, selecionado, destaque, onSelecionar, searchPin])

  return (
    <div
      onMouseLeave={() => setHover(null)}
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
            minWidth: 168,
          }}
        >
          <div className="num" style={{ font: '600 10px/1 var(--f-num)', color: 'var(--tx-sub)' }}>
            {hover.h.id}
          </div>
          <Linha rotulo="Residual" valor={`${alunos(hover.h.oferta)} alunos`} forte />
          <Linha rotulo="Score censo" valor={num(hover.h.censo, 1)} />
          <Linha rotulo="Score M1" valor={num(hover.h.m1, 1)} />
          <Linha rotulo="População" valor={num(hover.h.pop)} />
          <Linha rotulo="Concorrentes" valor={num(hover.h.conc)} />
          {hover.h.ultra > 0 && <Linha rotulo="Unidade Ultra" valor={num(hover.h.ultra)} />}
        </div>
      )}
    </div>
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
