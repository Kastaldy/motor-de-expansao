import { FlyToInterpolator, type Layer } from '@deck.gl/core'
import { IconLayer, ScatterplotLayer } from '@deck.gl/layers'
import DeckGL from '@deck.gl/react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Map } from 'react-map-gl/maplibre'
import 'maplibre-gl/dist/maplibre-gl.css'

import { COR_SEVERIDADE, enquadrar } from '../lib/exec'
import { brl, num, pct } from '../lib/format'
import type { RedeUnidade } from '../lib/types'

/* ---------------------------------------------------------------------------
   Mapa da rede Ultra — bubble map: cada unidade é um círculo cujo TAMANHO é o
   faturamento e cuja COR é o diagnóstico. Camada visual, READ-ONLY sobre o M1.

   Na Visão Executiva 2.0 ele deixou de ser o plano de fundo em tela cheia e
   passou a ser um card dentro do scroller. Duas consequências que não são
   cosméticas:

   - `scrollZoom: false` é OBRIGATÓRIO. Dentro de um scroller, a roda do mouse
     daria zoom no mapa em vez de rolar a página, e a pessoa ficaria presa.
   - o enquadramento sai do BBOX, não da média das coordenadas: com a rede
     nacional, a média cai num ponto sem nenhuma unidade e o zoom fixo corta
     metade do país.
   --------------------------------------------------------------------------- */

const BASEMAP_STYLE = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'
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

function corHex(hex: string, alpha: number): [number, number, number, number] {
  const h = hex.replace('#', '')
  return [
    parseInt(h.slice(0, 2), 16),
    parseInt(h.slice(2, 4), 16),
    parseInt(h.slice(4, 6), 16),
    alpha,
  ]
}

export interface ExecMapProps {
  unidades: RedeUnidade[]
  centro: { lat: number | null; lng: number | null }
  bbox: { min_lat: number; min_lng: number; max_lat: number; max_lng: number } | null
  /** Bandeira quadrada da Ultra (data URI SVG), plantada no centro de cada bolha. */
  iconeUltra?: string | null
  onUnidade?: (id: string) => void
}

export default function ExecMap({ unidades, centro, bbox, iconeUltra, onUnidade }: ExecMapProps) {
  const comCoord = useMemo(
    () => unidades.filter((u) => u.lat != null && u.lng != null),
    [unidades],
  )
  const ultraIcon = useMemo(
    () =>
      iconeUltra
        ? { url: iconeUltra, width: 128, height: 128, anchorX: 64, anchorY: 64, mask: false }
        : null,
    [iconeUltra],
  )
  const maxFat = useMemo(
    () => Math.max(1, ...comCoord.map((u) => u.metricas.faturamento?.atual ?? 0)),
    [comCoord],
  )
  const [hover, setHover] = useState<{ u: RedeUnidade; x: number; y: number } | null>(null)

  const alvo = useMemo(() => enquadrar(bbox, centro), [bbox, centro])
  const [view, setView] = useState<ViewState>(() => ({ ...alvo, pitch: 0, bearing: 0 }))
  // Zoom pela roda do mouse fica ARMADO por um clique e desarma quando o ponteiro sai.
  //
  // Os dois extremos são ruins: com a roda sempre ativa, quem está só rolando a página
  // passa o ponteiro por cima do card e o mapa engole a rolagem — a pessoa fica presa.
  // Com a roda sempre desligada, não dá para aproximar de uma unidade, que é o que o
  // mapa serve para fazer. Um clique resolve os dois: enquanto não houver clique, a roda
  // rola a página; depois dele, aproxima. Os botões + e - funcionam sempre, para quem
  // não descobrir o clique.
  const [zoomArmado, setZoomArmado] = useState(false)

  const aplicarZoom = useCallback((delta: number) => {
    setView((v) => ({
      ...v,
      zoom: Math.min(16, Math.max(2.5, v.zoom + delta)),
      transitionDuration: 220,
      transitionInterpolator: undefined,
    }))
  }, [])

  const enquadrarTudo = useCallback(() => {
    setView((v) => ({ ...v, ...alvo, transitionDuration: 500, transitionInterpolator: FLY }))
  }, [alvo])

  const chaveAlvo = `${alvo.latitude.toFixed(3)},${alvo.longitude.toFixed(3)},${alvo.zoom.toFixed(2)}`
  useEffect(() => {
    setView((v) => ({
      ...v,
      ...alvo,
      transitionDuration: 700,
      transitionInterpolator: FLY,
    }))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chaveAlvo])

  const layers = useMemo(() => {
    const arr: Layer[] = [
      new ScatterplotLayer<RedeUnidade>({
        id: 'unidades',
        data: comCoord,
        getPosition: (d) => [d.lng!, d.lat!],
        // área ∝ faturamento (raio ∝ sqrt), para leitura honesta de magnitude.
        getRadius: (d) => 7 + 26 * Math.sqrt((d.metricas.faturamento?.atual ?? 0) / maxFat),
        radiusUnits: 'pixels',
        radiusMinPixels: 5,
        radiusMaxPixels: 40,
        getFillColor: (d) => corHex(COR_SEVERIDADE[d.severidade], 175),
        getLineColor: [255, 255, 255, 220],
        lineWidthMinPixels: 1.2,
        stroked: true,
        pickable: true,
        autoHighlight: true,
        highlightColor: [255, 255, 255, 120],
        updateTriggers: { getFillColor: comCoord.map((u) => u.severidade).join() },
        onHover: (info) =>
          setHover(info.object ? { u: info.object as RedeUnidade, x: info.x, y: info.y } : null),
        onClick: (info) => {
          if (info.object && onUnidade) onUnidade((info.object as RedeUnidade).id)
        },
      }),
    ]
    if (ultraIcon) {
      arr.push(
        new IconLayer<RedeUnidade>({
          id: 'ultra-flags',
          data: comCoord,
          getPosition: (d) => [d.lng!, d.lat!],
          getIcon: () => ultraIcon,
          getSize: 15,
          sizeUnits: 'pixels',
          sizeMinPixels: 10,
          sizeMaxPixels: 18,
          pickable: false,
        }),
      )
    }
    return arr
  }, [comCoord, maxFat, ultraIcon, onUnidade])

  return (
    <div
      onMouseLeave={() => {
        setHover(null)
        setZoomArmado(false)
      }}
      onPointerDown={() => setZoomArmado(true)}
      style={{
        position: 'absolute',
        inset: 0,
        background: 'radial-gradient(120% 90% at 46% 42%, var(--bg-lift) 0%, var(--bg-base) 76%)',
      }}
    >
      <DeckGL
        viewState={view}
        onViewStateChange={(e) => setView(e.viewState as ViewState)}
        controller={{ dragRotate: false, scrollZoom: zoomArmado, doubleClickZoom: true }}
        layers={layers}
        style={{ position: 'absolute', top: '0', left: '0', width: '100%', height: '100%' }}
        getCursor={({ isHovering }) => (isHovering ? 'pointer' : 'grab')}
      >
        <Map mapStyle={BASEMAP_STYLE} attributionControl={{ compact: true }} reuseMaps />
      </DeckGL>

      <div
        style={{
          position: 'absolute',
          right: 10,
          top: 10,
          display: 'flex',
          flexDirection: 'column',
          gap: 4,
          zIndex: 20,
        }}
      >
        <BotaoMapa rotulo="Aproximar" onClick={() => aplicarZoom(1)}>
          +
        </BotaoMapa>
        <BotaoMapa rotulo="Afastar" onClick={() => aplicarZoom(-1)}>
          −
        </BotaoMapa>
        <BotaoMapa rotulo="Enquadrar todas as unidades" onClick={enquadrarTudo}>
          ⤢
        </BotaoMapa>
      </div>

      {!zoomArmado && (
        <div
          style={{
            position: 'absolute',
            left: 10,
            bottom: 10,
            padding: '5px 9px',
            borderRadius: 'var(--r-sm)',
            background: 'var(--surf-panel)',
            border: '1px solid var(--line-soft)',
            backdropFilter: 'blur(10px)',
            font: '500 10px/1 var(--f-ui)',
            color: 'var(--tx-muted)',
            pointerEvents: 'none',
            zIndex: 20,
          }}
        >
          clique no mapa para a roda do mouse aproximar
        </div>
      )}

      {hover && (
        <div
          role="tooltip"
          style={{
            position: 'absolute',
            left: Math.min(hover.x + 14, 170),
            top: hover.y + 14,
            pointerEvents: 'none',
            background: 'var(--surf-panel)',
            border: '1px solid var(--line-mid)',
            borderRadius: 'var(--r-md)',
            padding: '10px 12px',
            backdropFilter: 'blur(16px)',
            boxShadow: '0 10px 30px -8px rgba(0,0,0,.7)',
            zIndex: 30,
            minWidth: 178,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: '50%',
                background: COR_SEVERIDADE[hover.u.severidade],
              }}
            />
            <span style={{ font: '700 12.5px/1.2 var(--f-ui)', color: 'var(--tx-max)' }}>
              {hover.u.nome}
            </span>
          </div>
          <div style={{ height: 1, background: 'var(--line-soft)', margin: '8px 0 2px' }} />
          <LinhaT
            rotulo="Faturamento"
            valor={brl(hover.u.metricas.faturamento?.atual ?? null, true)}
            forte
          />
          <LinhaT rotulo="Alunos ativos" valor={num(hover.u.metricas.ativos?.atual ?? null)} />
          <LinhaT rotulo="Churn" valor={pct(hover.u.metricas.churn_pct?.atual ?? null, 1)} />
          <LinhaT rotulo="NPS" valor={num(hover.u.metricas.nps?.atual ?? null)} />
          <LinhaT rotulo="Maturidade" valor={hover.u.coorte_rotulo} />
          {hover.u.alertas.length > 0 && (
            <div
              style={{
                marginTop: 7,
                font: '400 10.5px/1.45 var(--f-ui)',
                color: COR_SEVERIDADE[hover.u.severidade],
              }}
            >
              {hover.u.alertas.map((a) => a.titulo).join(' · ')}
            </div>
          )}
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


function BotaoMapa({
  children,
  rotulo,
  onClick,
}: {
  children: React.ReactNode
  rotulo: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      title={rotulo}
      aria-label={rotulo}
      onClick={onClick}
      style={{
        width: 26,
        height: 26,
        display: 'grid',
        placeItems: 'center',
        borderRadius: 'var(--r-sm)',
        border: '1px solid var(--line-soft)',
        background: 'var(--surf-panel)',
        backdropFilter: 'blur(10px)',
        color: 'var(--tx-soft)',
        font: '600 14px/1 var(--f-ui)',
        cursor: 'pointer',
      }}
    >
      {children}
    </button>
  )
}
