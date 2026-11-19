import type { Layer } from '@deck.gl/core'
import { IconLayer, PathLayer, PolygonLayer } from '@deck.gl/layers'
import DeckGL from '@deck.gl/react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Map } from 'react-map-gl/maplibre'
import 'maplibre-gl/dist/maplibre-gl.css'

import { api, ApiError } from '../../lib/api'
import { corDaFaixaDoServidor } from '../../lib/colors'
import { tracoComHalo } from '../../lib/contorno-halo'
import { num, renda } from '../../lib/format'
import type { CamadaDoMapa, FocoNoMapa, MasterCamadas, MasterMapa, SetorDoTerritorio } from '../../lib/masters'
import { caixaDoContorno, vistaDoTerritorio } from '../../lib/masters'
import type { Tema } from '../../lib/tema'

/* ---------------------------------------------------------------------------
   Mapa do território no painel do master (BLK-MASTERS-04).

   18/11/2026, Juan: "deixe uma parte do relatório nessa aba, o mapa, assim como
   está na carteira, com a área e a opção de ligar a renda e a densidade".
   19/11/2026: o território só DEMARCADO ("não precisa deixar a área colorida, só
   deixe ela demarcada igual fica no motor"): o contorno de cada região, em BRANCO
   sobre o halo escuro do motor (`tracoComHalo`; 19/11/2026, Juan: "mostre o limite do
   território em branco"); e duas camadas, uma por vez: renda e densidade, SEMPRE
   do Censo ("deixe o padrão sempre censitário"), com os polígonos dos setores do
   território inteiro, como na ficha da carteira, em QUALQUER zoom (19/11/2026,
   Juan: "deixe a densidade e a renda (quando ativadas) aparecendo sem limite de
   zoom"; antes, de longe, ia um ponto por setor, e os polígonos só no zoom de
   cidade). Espaço livre e academias concorrentes saíram ("a camada de espaço livre
   e academias concorrentes não precisa ter"); seguem só no PDF. Camada visual,
   READ-ONLY.
   --------------------------------------------------------------------------- */

const BASEMAP = {
  escuro: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
  claro: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
} as const

/** `indice`: a posição do valor na linha do setor, `[renda, densidade, anéis]`. */
const CAMADAS: { chave: CamadaDoMapa; rotulo: string; legenda: string; indice: 0 | 1 }[] = [
  { chave: 'renda_domiciliar', rotulo: 'Renda domiciliar', legenda: 'Renda domiciliar (por domicílio)', indice: 0 },
  { chave: 'densidade', rotulo: 'Densidade demográfica', legenda: 'Densidade (hab/km²)', indice: 1 },
]

const ALTURA = 480
/** O limite do território, em branco (19/11/2026, Juan). */
const BRANCO = [255, 255, 255] as const

/** "A", "A e B", "A, B e C". */
function listaDeNomes(nomes: string[]): string {
  return nomes.length > 1 ? `${nomes.slice(0, -1).join(', ')} e ${nomes[nomes.length - 1]}` : (nomes[0] ?? '')
}

type Vista = { longitude: number; latitude: number; zoom: number; pitch: number; bearing: number }
type Dica = { titulo: string; linhas: string[]; x: number; y: number }

/** O valor de uma camada, como texto, para a dica. */
function textoDoValor(camada: CamadaDoMapa, v: number | null | undefined): string {
  if (v == null) return 'sem leitura'
  return camada === 'renda_domiciliar' ? renda(v) : `${num(v)} hab/km²`
}

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
  const [camada, setCamada] = useState<CamadaDoMapa | null>(null)
  const [camadas, setCamadas] = useState<MasterCamadas | null>(null)
  const [carregandoCamadas, setCarregandoCamadas] = useState(false)
  const [erroCamadas, setErroCamadas] = useState<string | null>(null)
  // Os setores do Censo do território inteiro: a renda e a densidade, em qualquer zoom.
  const [setores, setSetores] = useState<SetorDoTerritorio[] | null>(null)
  const [carregandoSetores, setCarregandoSetores] = useState(false)
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
    setSetores(null)
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

  const def = camada ? CAMADAS.find((c) => c.chave === camada)! : null

  function alternarCamada(chave: CamadaDoMapa) {
    const proxima = camada === chave ? null : chave
    setCamada(proxima)
    if (proxima && !setores && !carregandoSetores) {
      setCarregandoSetores(true)
      setErroCamadas(null) // um erro antigo não fica na tela depois de uma nova tentativa
      api
        .masterSetores(masterId)
        .then((r) => setSetores(r.setores))
        .catch((e: ApiError) => setErroCamadas(e.message))
        .finally(() => setCarregandoSetores(false))
    }
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

  const layers = useMemo(() => {
    if (!mapa) return []
    const arr: Layer[] = []
    const faixas = def && camadas ? camadas.faixas[def.chave] : null

    if (def && faixas) {
      // Os polígonos dos setores do território inteiro, em qualquer zoom (sem os pontos de longe).
      const i = def.indice
      arr.push(
        new PolygonLayer<SetorDoTerritorio>({
          id: 'setores',
          data: setores ?? [],
          getPolygon: (d) => d[2],
          positionFormat: 'XY',
          filled: true,
          stroked: false,
          pickable: true,
          getFillColor: (d) => corDaFaixaDoServidor(d[i], faixas, 150),
          updateTriggers: { getFillColor: [def.chave] },
          onHover: (info) => {
            const d = info.object as SetorDoTerritorio | undefined
            setDica(
              d
                ? { titulo: 'Setor do Censo', linhas: [`${def.rotulo}: ${textoDoValor(def.chave, d[i])}`], x: info.x, y: info.y }
                : null,
            )
          },
        }),
      )
    }

    // O território DEMARCADO: o limite de cada região em branco, por cima do halo escuro do motor
    // (no tema claro, o halo é o que separa o branco do fundo).
    const aneis = mapa.contornos.flatMap((c) =>
      c.poligonos.flatMap((pol) => pol.map((anel) => ({ anel, regiao: c.regiao }))),
    )
    const traco = tracoComHalo(tema, BRANCO, 2.5)
    arr.push(
      new PathLayer<(typeof aneis)[number]>({
        id: 'contorno-halo',
        data: aneis,
        getPath: (d) => d.anel,
        getColor: traco.halo.cor,
        getWidth: traco.halo.largura,
        widthUnits: 'pixels',
        jointRounded: true,
        updateTriggers: { getColor: [tema] },
      }),
      new PathLayer<(typeof aneis)[number]>({
        id: 'contorno',
        data: aneis,
        getPath: (d) => d.anel,
        getColor: traco.traco.cor,
        getWidth: traco.traco.largura,
        widthUnits: 'pixels',
        jointRounded: true,
        updateTriggers: { getColor: [tema] },
      }),
    )

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
  }, [mapa, def, camadas, setores, tema, foco])

  const faixasDaLegenda = def && camadas ? camadas.faixas[def.chave] : null

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
        <div style={centro}>{mapa ? 'Sem território para mostrar.' : 'Carregando o território…'}</div>
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

          <div style={{ ...painel, left: 10, bottom: 24, font: '500 10.5px/1.5 var(--f-ui)', maxWidth: 'calc(100% - 220px)' }}>
            {def ? (
              carregandoCamadas ? (
                <div>Carregando as camadas do território…</div>
              ) : erroCamadas ? (
                <div>{erroCamadas}</div>
              ) : faixasDaLegenda ? (
                <>
                  <div style={{ font: '600 10px/1.4 var(--f-ui)', color: 'var(--tx-label)', marginBottom: 3 }}>
                    {def.legenda} · setores do Censo
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
                  {carregandoSetores && (
                    <div style={{ marginTop: 3 }}>Carregando os setores do Censo…</div>
                  )}
                </>
              ) : null
            ) : (
              <>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  {/* O branco com o contorno escuro, como no mapa (no tema claro, o branco sozinho some). */}
                  <span
                    style={{
                      width: 14,
                      height: 3,
                      background: '#fff',
                      boxShadow: '0 0 0 1px rgba(8, 11, 16, 0.85)',
                      borderRadius: 1,
                    }}
                  />
                  Limite do território: {listaDeNomes(mapa.regioes.map((r) => r.nome))}
                </div>
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
