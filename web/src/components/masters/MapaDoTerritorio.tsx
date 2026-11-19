import type { Layer } from '@deck.gl/core'
import { H3HexagonLayer } from '@deck.gl/geo-layers'
import { IconLayer, PolygonLayer } from '@deck.gl/layers'
import DeckGL from '@deck.gl/react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Map } from 'react-map-gl/maplibre'
import 'maplibre-gl/dist/maplibre-gl.css'

import { api, ApiError } from '../../lib/api'
import { corDaFaixaDoServidor } from '../../lib/colors'
import { num, renda } from '../../lib/format'
import type { FocoNoMapa, MasterCamadas, MasterMapa } from '../../lib/masters'
import { caixaDoContorno, rgbDeHex, vistaDoTerritorio } from '../../lib/masters'
import type { Tema } from '../../lib/tema'

/* ---------------------------------------------------------------------------
   Mapa do território no painel do master (BLK-MASTERS-04).

   18/11/2026, Juan: "deixe uma parte do relatório nessa aba, o mapa, assim como
   está na carteira, com a área e a opção de ligar a renda e a densidade". O
   território é o do mapa do relatório em PDF (hexágonos povoados de cada região,
   com a cor da região); as camadas usam as faixas e os botões da ficha da carteira
   (`FichaMapa`), uma por vez. Camada visual, READ-ONLY: nada aqui mexe em score.

   Em hexágono, e não em polígono de setor como a ficha: um território de estado
   inteiro tem dezenas de milhares de setores. A renda e a densidade são as do
   Mapa do motor para o mesmo hexágono.
   --------------------------------------------------------------------------- */

const BASEMAP = {
  escuro: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
  claro: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
} as const

type Camada = 'renda_domiciliar' | 'densidade'

const CAMADAS: { chave: Camada; rotulo: string; legenda: string }[] = [
  { chave: 'renda_domiciliar', rotulo: 'Renda domiciliar', legenda: 'Renda domiciliar (por domicílio)' },
  { chave: 'densidade', rotulo: 'Densidade demográfica', legenda: 'Densidade (hab/km²)' },
]

const ALTURA = 480

type Vista = { longitude: number; latitude: number; zoom: number; pitch: number; bearing: number }
type Dica = { titulo: string; linhas: string[]; x: number; y: number }

export default function MapaDoTerritorio({
  masterId,
  tema,
  foco = null,
  onSairDoFoco,
}: {
  masterId: string
  tema: Tema
  /** A região clicada na lista de onde abrir (18/11/2026, Juan: "ao clicar, dá zoom no mapa"). */
  foco?: FocoNoMapa | null
  onSairDoFoco?: () => void
}) {
  const caixa = useRef<HTMLDivElement>(null)
  const [mapa, setMapa] = useState<MasterMapa | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [vista, setVista] = useState<Vista | null>(null)
  const [zoomArmado, setZoomArmado] = useState(false)
  const [camada, setCamada] = useState<Camada | null>(null)
  const [camadas, setCamadas] = useState<MasterCamadas | null>(null)
  const [carregandoCamadas, setCarregandoCamadas] = useState(false)
  const [erroCamadas, setErroCamadas] = useState<string | null>(null)
  const [dica, setDica] = useState<Dica | null>(null)

  function enquadrar(m: MasterMapa) {
    if (!m.bbox) return
    const largura = caixa.current?.clientWidth || 900
    setVista({ ...vistaDoTerritorio(m.bbox, largura, ALTURA), pitch: 0, bearing: 0 })
  }

  useEffect(() => {
    let vivo = true
    setMapa(null)
    setErro(null)
    setCamada(null)
    setCamadas(null)
    setErroCamadas(null)
    api
      .masterMapa(masterId)
      .then((m) => {
        if (!vivo) return
        setMapa(m)
        enquadrar(m)
      })
      .catch((e: ApiError) => vivo && setErro(e.message))
    return () => {
      vivo = false
    }
  }, [masterId])

  // Região clicada na lista: aproxima nela e traz o mapa para a vista (ele fica acima da lista).
  useEffect(() => {
    if (!foco || !mapa) return
    const largura = caixa.current?.clientWidth || 900
    const bbox = caixaDoContorno(foco.contorno)
    setVista({ ...vistaDoTerritorio(bbox, largura, ALTURA, 60, 13.5), pitch: 0, bearing: 0 })
    caixa.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, [foco, mapa])

  function alternarCamada(chave: Camada) {
    const proxima = camada === chave ? null : chave
    setCamada(proxima)
    if (proxima && !camadas && !carregandoCamadas) {
      setCarregandoCamadas(true)
      setErroCamadas(null)
      api
        .masterCamadas(masterId)
        .then(setCamadas)
        .catch((e: ApiError) => setErroCamadas(e.message))
        .finally(() => setCarregandoCamadas(false))
    }
  }

  /** hex_id -> [renda, densidade], para a cor e a dica. */
  const valores = useMemo(() => {
    const out = new globalThis.Map<string, [number | null, number | null]>()
    for (const [h, r, d] of camadas?.hexes ?? []) out.set(h, [r, d])
    return out
  }, [camadas])

  const layers = useMemo(() => {
    if (!mapa) return []
    const cores = mapa.regioes.map((r) => rgbDeHex(r.cor))
    const faixas = camada && camadas ? camadas.faixas[camada] : null
    const indiceDaCamada = camada === 'densidade' ? 1 : 0
    const arr: Layer[] = [
      new H3HexagonLayer<[string, number]>({
        id: 'territorio',
        data: mapa.hexes,
        getHexagon: (d) => d[0],
        filled: true,
        stroked: false,
        extruded: false,
        pickable: true,
        getFillColor: (d) => {
          if (faixas) return corDaFaixaDoServidor(valores.get(d[0])?.[indiceDaCamada] ?? null, faixas, 170)
          const [r, g, b] = cores[d[1]] ?? [0, 167, 157]
          return [r, g, b, 120]
        },
        updateTriggers: { getFillColor: [camada, camadas] },
        onHover: (info) => {
          const d = info.object as [string, number] | undefined
          if (!d) return setDica(null)
          const v = valores.get(d[0])
          const linhas = camada
            ? [
                camada === 'renda_domiciliar'
                  ? `Renda domiciliar: ${v?.[0] != null ? renda(v[0]) : 'sem leitura'}`
                  : `Densidade: ${v?.[1] != null ? `${num(v[1])} hab/km²` : 'sem leitura'}`,
              ]
            : []
          setDica({ titulo: mapa.regioes[d[1]]?.nome ?? '', linhas, x: info.x, y: info.y })
        },
      }),
    ]
    if (mapa.icone_ultra && mapa.ultra.length) {
      const icone = { url: mapa.icone_ultra, width: 128, height: 128, anchorX: 64, anchorY: 64, mask: false }
      arr.push(
        new IconLayer<[number, number, string]>({
          id: 'ultra',
          data: mapa.ultra,
          getPosition: (d) => [d[1], d[0]],
          getIcon: () => icone,
          getSize: 20,
          sizeUnits: 'pixels',
          pickable: true,
          onHover: (info) => {
            const d = info.object as [number, number, string] | undefined
            setDica(d ? { titulo: d[2] || 'Unidade Ultra', linhas: ['Unidade Ultra'], x: info.x, y: info.y } : null)
          },
        }),
      )
    }
    if (foco) {
      // O limite da região (o hexágono recomendado), em rosa: "como se fosse o raio" (Juan).
      arr.push(
        new PolygonLayer<FocoNoMapa>({
          id: 'regiao-em-foco',
          data: [foco],
          getPolygon: (d) => d.contorno,
          filled: true,
          stroked: true,
          getFillColor: [194, 60, 142, 45],
          getLineColor: [194, 60, 142, 255],
          lineWidthUnits: 'pixels',
          getLineWidth: 3,
        }),
      )
    }
    return arr
  }, [mapa, camada, camadas, valores, foco])

  const faixasDaLegenda = camada && camadas?.disponivel ? camadas.faixas[camada] : null

  return (
    <div
      ref={caixa}
      onPointerDown={() => setZoomArmado(true)}
      onMouseLeave={() => {
        setDica(null)
        setZoomArmado(false)
      }}
      style={{
        position: 'relative',
        height: ALTURA,
        borderRadius: 'var(--r-md)',
        overflow: 'hidden',
        border: '1px solid var(--line-soft)',
        background: 'var(--surf-panel)',
      }}
    >
      {erro ? (
        <div style={{ ...centro, color: 'var(--warn-text)' }}>{erro}</div>
      ) : !mapa || !vista ? (
        <div style={centro}>{mapa ? 'Sem hexágonos para mostrar neste território.' : 'Carregando o território…'}</div>
      ) : (
        <>
          <DeckGL
            viewState={vista}
            onViewStateChange={(e) => setVista(e.viewState as Vista)}
            controller={{ dragRotate: false, scrollZoom: zoomArmado, doubleClickZoom: true }}
            layers={layers}
            style={{ position: 'absolute', top: '0', left: '0', width: '100%', height: '100%' }}
            getCursor={({ isHovering }) => (isHovering ? 'pointer' : 'grab')}
          >
            <Map key={tema} mapStyle={BASEMAP[tema]} attributionControl={{ compact: true }} reuseMaps />
          </DeckGL>

          <div style={{ position: 'absolute', right: 10, top: 10, display: 'flex', flexDirection: 'column', gap: 4, zIndex: 20 }}>
            {(
              [
                ['+', 'Aproximar', 1],
                ['−', 'Afastar', -1],
              ] as const
            ).map(([rotulo, titulo, delta]) => (
              <button
                key={titulo}
                type="button"
                title={titulo}
                aria-label={titulo}
                onClick={() => setVista((v) => (v ? { ...v, zoom: Math.min(15, Math.max(4, v.zoom + delta)) } : v))}
                style={botao}
              >
                {rotulo}
              </button>
            ))}
            <button
              type="button"
              title="Enquadrar o território"
              aria-label="Enquadrar o território"
              onClick={() => {
                enquadrar(mapa)
                onSairDoFoco?.()
              }}
              style={botao}
            >
              ⌖
            </button>
          </div>

          {/* Uma camada por vez, como na ficha da carteira: duas paletas sobrepostas não se leem.
              `bottom: 46`: embaixo à direita mora a atribuição da CARTO/OpenStreetMap. */}
          <div
            style={{
              position: 'absolute',
              right: 10,
              bottom: 46,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'flex-end',
              gap: 5,
              zIndex: 20,
            }}
          >
            {CAMADAS.map((c) => {
              const ativa = camada === c.chave
              return (
                <button
                  key={c.chave}
                  type="button"
                  aria-pressed={ativa}
                  onClick={() => alternarCamada(c.chave)}
                  style={{
                    padding: '6px 10px',
                    borderRadius: 'var(--r-sm)',
                    border: `1px solid ${ativa ? 'var(--ac)' : 'var(--line-soft)'}`,
                    background: ativa ? 'var(--ac-a22)' : 'var(--surf-panel)',
                    backdropFilter: 'blur(10px)',
                    color: ativa ? 'var(--ac-text)' : 'var(--tx-soft)',
                    font: '600 11px/1 var(--f-ui)',
                    cursor: 'pointer',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {ativa ? '● ' : ''}
                  {c.rotulo}
                </button>
              )
            })}
          </div>

          <div style={{ ...painel, left: 10, bottom: 24, font: '500 10.5px/1.5 var(--f-ui)', maxWidth: 'calc(100% - 200px)' }}>
            {camada ? (
              carregandoCamadas ? (
                <div>Carregando renda e densidade do território…</div>
              ) : erroCamadas ? (
                <div>{erroCamadas}</div>
              ) : camadas && !camadas.disponivel ? (
                <div>Renda e densidade indisponíveis para este território.</div>
              ) : faixasDaLegenda ? (
                <>
                  <div style={{ font: '600 10px/1.4 var(--f-ui)', color: 'var(--tx-label)', marginBottom: 3 }}>
                    {CAMADAS.find((c) => c.chave === camada)?.legenda}
                  </div>
                  {faixasDaLegenda.map((f) => (
                    <div key={f.rotulo} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      {/* O rótulo do núcleo é ASCII ("ate") porque também vai ao PDF; na tela sai
                          acentuado, só na exibição. */}
                      <span style={{ width: 10, height: 10, borderRadius: 2, background: `rgb(${f.cor.slice(0, 3).join(',')})` }} />
                      {f.rotulo.replace(/^ate /, 'até ')}
                    </div>
                  ))}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 2, color: 'var(--tx-muted)' }}>
                    <span style={{ width: 10, height: 10, borderRadius: 2, background: 'rgb(120,120,140)', opacity: 0.4 }} />
                    sem leitura
                  </div>
                </>
              ) : null
            ) : (
              <>
                {mapa.regioes.map((r) => (
                  <div key={r.id} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ width: 10, height: 10, borderRadius: 2, background: r.cor, opacity: 0.8 }} />
                    {r.nome}
                  </div>
                ))}
                {mapa.icone_ultra && mapa.ultra.length > 0 && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <img src={mapa.icone_ultra} alt="" width={12} height={12} style={{ borderRadius: 2 }} />
                    {mapa.ultra.length} unidades Ultra no território
                  </div>
                )}
              </>
            )}
          </div>

          {foco && (
            <div
              style={{
                position: 'absolute',
                left: 10,
                top: 10,
                zIndex: 21,
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '7px 10px',
                borderRadius: 'var(--r-sm)',
                background: 'var(--surf-panel)',
                border: '1px solid var(--gr-rosa)',
                backdropFilter: 'blur(10px)',
                font: '600 11.5px/1.3 var(--f-ui)',
                color: 'var(--tx-max)',
              }}
            >
              <span>Região: {foco.nome}</span>
              <button
                type="button"
                onClick={() => {
                  enquadrar(mapa)
                  onSairDoFoco?.()
                }}
                style={{
                  border: 'none',
                  background: 'transparent',
                  color: 'var(--ac-text)',
                  font: '600 11px/1 var(--f-ui)',
                  cursor: 'pointer',
                  padding: 0,
                  textDecoration: 'underline',
                }}
              >
                ver o território inteiro
              </button>
            </div>
          )}

          {dica && (
            <div
              role="tooltip"
              style={{
                position: 'absolute',
                left: dica.x + 14,
                top: dica.y + 14,
                pointerEvents: 'none',
                background: 'var(--surf-panel)',
                border: '1px solid var(--line-mid)',
                borderRadius: 'var(--r-md)',
                padding: '8px 10px',
                backdropFilter: 'blur(16px)',
                boxShadow: 'var(--sh-pop)',
                zIndex: 30,
                font: '400 11.5px/1.5 var(--f-ui)',
                color: 'var(--tx-soft)',
              }}
            >
              <div style={{ font: '600 12px/1.4 var(--f-ui)', color: 'var(--tx-strong)' }}>{dica.titulo}</div>
              {dica.linhas.map((l) => (
                <div key={l}>{l}</div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}

const centro = {
  position: 'absolute',
  inset: 0,
  display: 'grid',
  placeItems: 'center',
  padding: 20,
  textAlign: 'center',
  font: '400 12.5px/1.5 var(--f-ui)',
  color: 'var(--tx-sub)',
} as const

const painel = {
  position: 'absolute',
  padding: '7px 10px',
  borderRadius: 'var(--r-sm)',
  background: 'var(--surf-panel)',
  border: '1px solid var(--line-soft)',
  backdropFilter: 'blur(10px)',
  color: 'var(--tx-soft)',
  zIndex: 20,
  pointerEvents: 'none',
} as const

const botao = {
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
} as const
