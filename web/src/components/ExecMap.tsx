import { FlyToInterpolator, type Layer } from '@deck.gl/core'
import { IconLayer, ScatterplotLayer } from '@deck.gl/layers'
import DeckGL from '@deck.gl/react'
import { useEffect, useMemo, useState } from 'react'
import { Map } from 'react-map-gl/maplibre'
import 'maplibre-gl/dist/maplibre-gl.css'

import { brl, num, pct } from '../lib/format'
import type { ExecUnidade } from '../lib/types'

/* ---------------------------------------------------------------------------
   Mapa da rede Ultra por estado — bubble map: cada unidade é um círculo cujo
   tamanho é proporcional ao FATURAMENTO. Camada visual (READ-ONLY sobre o M1).
   --------------------------------------------------------------------------- */

const BASEMAP_STYLE =
  'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'
const FLY = new FlyToInterpolator({ speed: 1.6 })

interface ViewState {
  longitude: number
  latitude: number
  zoom: number
  pitch: number
  bearing: number
  transitionDuration?: number
  transitionInterpolator?: FlyToInterpolator
}

export interface ExecMapProps {
  unidades: ExecUnidade[]
  centro: { lat: number | null; lng: number | null }
  /** Bandeira quadrada da Ultra (data URI SVG), plantada no centro de cada bolha. */
  iconeUltra?: string | null
}

export default function ExecMap({ unidades, centro, iconeUltra }: ExecMapProps) {
  const comCoord = useMemo(
    () => unidades.filter((u) => u.lat != null && u.lng != null),
    [unidades],
  )
  // Descritor de icone do deck.gl a partir do data URI (bandeira 128x128,
  // ancorada no centro para cair no meio da bolha).
  const ultraIcon = useMemo(
    () =>
      iconeUltra
        ? { url: iconeUltra, width: 128, height: 128, anchorX: 64, anchorY: 64, mask: false }
        : null,
    [iconeUltra],
  )
  const maxFat = useMemo(
    () => Math.max(1, ...comCoord.map((u) => u.faturamento ?? 0)),
    [comCoord],
  )
  const [hover, setHover] = useState<{ u: ExecUnidade; x: number; y: number } | null>(null)

  const [view, setView] = useState<ViewState>(() => ({
    longitude: centro.lng ?? -47.9,
    latitude: centro.lat ?? -15.78,
    zoom: 6.4,
    pitch: 0,
    bearing: 0,
  }))

  const centroKey = `${centro.lat},${centro.lng}`
  useEffect(() => {
    if (centro.lat == null || centro.lng == null) return
    setView((v) => ({
      ...v,
      longitude: centro.lng!,
      latitude: centro.lat!,
      zoom: 6.6,
      transitionDuration: 700,
      transitionInterpolator: FLY,
    }))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [centroKey])

  const layers = useMemo(() => {
    const arr: Layer[] = [
      new ScatterplotLayer<ExecUnidade>({
        id: 'unidades',
        data: comCoord,
        getPosition: (d) => [d.lng!, d.lat!],
        // área ∝ faturamento (raio ∝ sqrt), para leitura honesta de magnitude.
        getRadius: (d) => 8 + 30 * Math.sqrt((d.faturamento ?? 0) / maxFat),
        radiusUnits: 'pixels',
        radiusMinPixels: 6,
        radiusMaxPixels: 46,
        getFillColor: [200, 0, 30, 170],
        getLineColor: [255, 255, 255, 225],
        lineWidthMinPixels: 1.5,
        stroked: true,
        pickable: true,
        autoHighlight: true,
        highlightColor: [255, 90, 110, 210],
        onHover: (info) =>
          setHover(info.object ? { u: info.object as ExecUnidade, x: info.x, y: info.y } : null),
      }),
    ]
    // Bandeira quadrada da Ultra no centro de cada bolha (igual ao Mapa
    // Territorial). Fica POR CIMA do bubble; pickable:false para nao roubar o
    // hover do circulo de faturamento.
    if (ultraIcon) {
      arr.push(
        new IconLayer<ExecUnidade>({
          id: 'ultra-flags',
          data: comCoord,
          getPosition: (d) => [d.lng!, d.lat!],
          getIcon: () => ultraIcon,
          getSize: 18,
          sizeUnits: 'pixels',
          sizeMinPixels: 12,
          sizeMaxPixels: 22,
          pickable: false,
        }),
      )
    }
    return arr
  }, [comCoord, maxFat, ultraIcon])

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
        layers={layers}
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
            minWidth: 180,
          }}
        >
          <div style={{ font: '700 12.5px/1.2 var(--f-ui)', color: 'var(--tx-max)' }}>
            {hover.u.nome}
          </div>
          <div style={{ height: 1, background: 'var(--line-soft)', margin: '8px 0 2px' }} />
          <LinhaT rotulo="Faturamento" valor={brl(hover.u.faturamento, true)} forte />
          <LinhaT rotulo="Alunos ativos" valor={num(hover.u.ativos)} />
          <LinhaT rotulo="Pagantes" valor={num(hover.u.pagantes)} />
          <LinhaT rotulo="Agregadores" valor={num(hover.u.agregadores)} />
          <LinhaT rotulo="Churn" valor={pct(hover.u.churn, 2)} />
          <LinhaT rotulo="Ticket médio" valor={brl(hover.u.ticket)} />
          <LinhaT rotulo="NPS" valor={num(hover.u.nps)} />
        </div>
      )}
    </div>
  )
}

function LinhaT({ rotulo, valor, forte }: { rotulo: string; valor: string; forte?: boolean }) {
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
