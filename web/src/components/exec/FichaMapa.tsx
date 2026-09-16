import type { Layer } from '@deck.gl/core'
import { IconLayer, PolygonLayer, ScatterplotLayer } from '@deck.gl/layers'
import DeckGL from '@deck.gl/react'
import { useMemo, useState } from 'react'
import { Map } from 'react-map-gl/maplibre'
import 'maplibre-gl/dist/maplibre-gl.css'

import { api, ApiError } from '../../lib/api'
import { num } from '../../lib/format'
import type { Tema } from '../../lib/tema'
import type { RedeCamadaSetor, RedeFaixaCamada, RedeMapaConcorrente, RedeSetoresEntorno, RedeUnidadeMapa } from '../../lib/types'
import { metros, nomeRede } from './Inteligencia'

/* ---------------------------------------------------------------------------
   Mapa da ficha — a unidade no centro e quem disputa o aluno a até 2 km.

   Camada visual, READ-ONLY. Redes aparecem com a LOGO; independentes, com o
   ícone do Wellhub (todas vêm do feed do agregador) — o MESMO ícone do Mapa
   Territorial, para o operador não aprender duas legendas. A cor por
   vulnerabilidade saiu em 2026-09-15 (pedido do Felipe): o mapa serve para
   LOCALIZAR a concorrência. Anéis de 1 e 2 km dão a escala.

   Mesmas regras do `ExecMap`: basemap CARTO claro/escuro e roda do mouse armada
   por um clique, porque o mapa mora dentro de um scroller.
   --------------------------------------------------------------------------- */

const BASEMAP = {
  escuro: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
  claro: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
} as const


/** Identidade de módulo (estável): um objeto novo por render reempacotaria o atlas do deck.gl. */
const ICONE_WELLHUB = { url: '/logo-wellhub.png', width: 128, height: 128, anchorX: 64, anchorY: 64, mask: false }

type Pino = RedeMapaConcorrente & { temLogo: boolean }

const CAMADAS: { chave: RedeCamadaSetor; rotulo: string; legenda: string }[] = [
  { chave: 'renda_domiciliar', rotulo: 'Renda domiciliar', legenda: 'Renda domiciliar (R$/domicílio)' },
  { chave: 'densidade', rotulo: 'Densidade demográfica', legenda: 'Densidade (hab/km²)' },
]

/** Cor do setor pela faixa do núcleo. Sem leitura = cinza translúcido, nunca a faixa mais baixa. */
function corDaFaixa(valor: number | null, faixas: RedeFaixaCamada[]): [number, number, number, number] {
  if (valor === null) return [120, 120, 140, 50]
  const faixa = faixas.find((f) => f.ate === null || valor <= f.ate) ?? faixas[faixas.length - 1]
  const [r, g, b] = faixa.cor
  return [r, g, b, 150]
}

/**
 * `tema` vem da TELA (a mesma prop que o `ExecMap` recebe), e não do `<html data-tema>`.
 * Ler o atributo na renderização deixava o mapa um passo ATRASADO: trocar o tema não
 * re-renderizava a ficha, e o próximo clique pintava o tema anterior (bug relatado em 15/09).
 */
export default function FichaMapa({
  mapa,
  nome,
  unidadeId,
  tema,
}: {
  mapa: RedeUnidadeMapa
  nome: string
  unidadeId: string
  tema: Tema
}) {
  const [zoomArmado, setZoomArmado] = useState(false)
  // Camada de setor: carregada SÓ na primeira vez que alguém liga uma das duas — o payload
  // de polígonos de uma praça densa passa de 1 MB e a maioria das fichas nunca liga.
  const [camada, setCamada] = useState<RedeCamadaSetor | null>(null)
  const [setores, setSetores] = useState<RedeSetoresEntorno | null>(null)
  const [carregandoSetores, setCarregandoSetores] = useState(false)
  const [erroSetores, setErroSetores] = useState<string | null>(null)

  function alternarCamada(chave: RedeCamadaSetor) {
    const proxima = camada === chave ? null : chave
    setCamada(proxima)
    if (proxima && !setores && !carregandoSetores) {
      setCarregandoSetores(true)
      setErroSetores(null)
      api
        .redeUnidadeSetores(unidadeId)
        .then(setSetores)
        .catch((e: ApiError) => setErroSetores(e.message))
        .finally(() => setCarregandoSetores(false))
    }
  }
  const [view, setView] = useState({ longitude: mapa.lng, latitude: mapa.lat, zoom: 13.4, pitch: 0, bearing: 0 })
  const [hover, setHover] = useState<{ p: Pino; x: number; y: number } | null>(null)

  const pinos: Pino[] = useMemo(
    () => mapa.concorrentes.map((c) => ({ ...c, temLogo: Boolean(c.classe === 'cadeia' && c.rede && mapa.logos[c.rede]) })),
    [mapa],
  )

  const layers = useMemo(() => {
    const anel = tema === 'claro' ? [20, 32, 46, 120] : [255, 255, 255, 110]
    const aoPassar = (info: { object?: unknown; x: number; y: number }) =>
      setHover(info.object ? { p: info.object as Pino, x: info.x, y: info.y } : null)
    const faixas = camada && setores ? setores.faixas[camada] : null
    const arr: Layer[] = [
      ...(camada && setores?.setores.length && faixas
        ? [
            new PolygonLayer<RedeSetoresEntorno['setores'][number]>({
              id: 'camada-setor',
              data: setores.setores,
              // `anel` = [externo, buraco...]: o mesmo formato da camada de setor do Mapa Territorial.
              getPolygon: (d) => d.anel as unknown as number[][],
              positionFormat: 'XY',
              filled: true,
              stroked: false,
              getFillColor: (d) => corDaFaixa(d[camada], faixas),
              updateTriggers: { getFillColor: [camada] },
            }),
          ]
        : []),
      new ScatterplotLayer({
        id: 'aneis',
        data: [1000, 2000],
        getPosition: () => [mapa.lng, mapa.lat],
        getRadius: (r: number) => r,
        radiusUnits: 'meters',
        filled: false,
        stroked: true,
        getLineColor: anel as [number, number, number, number],
        lineWidthMinPixels: 1.2,
      }),
      new IconLayer<Pino>({
        id: 'independentes',
        data: pinos.filter((p) => !p.temLogo),
        getPosition: (d) => [d.lng, d.lat],
        getIcon: () => ICONE_WELLHUB,
        getSize: 22,
        sizeUnits: 'pixels',
        pickable: true,
        onHover: aoPassar,
      }),
      new IconLayer<Pino>({
        id: 'redes',
        data: pinos.filter((p) => p.temLogo),
        getPosition: (d) => [d.lng, d.lat],
        getIcon: (d) => ({ url: mapa.logos[d.rede as string], width: 128, height: 128, anchorX: 64, anchorY: 64, mask: false }),
        getSize: 26,
        sizeUnits: 'pixels',
        pickable: true,
        onHover: aoPassar,
      }),
    ]
    if (mapa.icone_ultra) {
      const icone = { url: mapa.icone_ultra, width: 128, height: 128, anchorX: 64, anchorY: 64, mask: false }
      arr.push(
        new IconLayer({
          id: 'ultra-vizinhas',
          data: mapa.ultra,
          getPosition: (d: { lng: number; lat: number }) => [d.lng, d.lat],
          getIcon: () => icone,
          getSize: 24,
          sizeUnits: 'pixels',
        }),
        new IconLayer({
          id: 'unidade',
          data: [mapa],
          getPosition: () => [mapa.lng, mapa.lat],
          getIcon: () => icone,
          getSize: 40,
          sizeUnits: 'pixels',
        }),
      )
    }
    return arr
  }, [mapa, pinos, tema, camada, setores])

  const redes = pinos.filter((p) => p.classe === 'cadeia').length
  const independentes = pinos.length - redes

  return (
    <div
      onPointerDown={() => setZoomArmado(true)}
      onMouseLeave={() => {
        setHover(null)
        setZoomArmado(false)
      }}
      style={{ position: 'absolute', inset: 0 }}
    >
      <DeckGL
        viewState={view}
        onViewStateChange={(e) => setView(e.viewState as typeof view)}
        controller={{ dragRotate: false, scrollZoom: zoomArmado, doubleClickZoom: true }}
        layers={layers}
        style={{ position: 'absolute', top: '0', left: '0', width: '100%', height: '100%' }}
        getCursor={({ isHovering }) => (isHovering ? 'pointer' : 'grab')}
      >
        <Map key={tema} mapStyle={BASEMAP[tema]} attributionControl={{ compact: true }} reuseMaps />
      </DeckGL>

      <div style={{ position: 'absolute', right: 10, top: 10, display: 'flex', flexDirection: 'column', gap: 4, zIndex: 20 }}>
        {[
          ['+', 'Aproximar', 1],
          ['−', 'Afastar', -1],
        ].map(([rotulo, titulo, delta]) => (
          <button
            key={titulo as string}
            type="button"
            title={titulo as string}
            aria-label={titulo as string}
            onClick={() => setView((v) => ({ ...v, zoom: Math.min(17, Math.max(10, v.zoom + (delta as number))) }))}
            style={botao}
          >
            {rotulo}
          </button>
        ))}
        <button
          type="button"
          title="Centralizar na unidade"
          aria-label="Centralizar na unidade"
          onClick={() => setView((v) => ({ ...v, longitude: mapa.lng, latitude: mapa.lat, zoom: 13.4 }))}
          style={botao}
        >
          ⌖
        </button>
      </div>

      <div style={{ ...painel, left: 10, top: 10, font: '500 11px/1.45 var(--f-ui)' }}>
        <strong style={{ color: 'var(--tx-strong)' }}>{pinos.length}</strong> academias a 2 km · {redes} de rede ·{' '}
        {independentes} independentes
        {mapa.ultra.length ? ` · ${mapa.ultra.length} outra(s) Ultra` : ''}
      </div>

      {/* Chaves das camadas de setor. Uma por vez: duas paletas sobrepostas não se leem. */}
      {/* `bottom: 46`, e não 24: embaixo à direita mora a atribuição da CARTO/OpenStreetMap,
          que é obrigação de licença e ficava tampada pelos botões (pedido do Felipe, 15/09). */}
      <div style={{ position: 'absolute', right: 10, bottom: 46, display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 5, zIndex: 20 }}>
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
          carregandoSetores ? (
            <div>Carregando setores do entorno…</div>
          ) : erroSetores ? (
            <div>{erroSetores}</div>
          ) : setores && !setores.disponivel ? (
            <div>Malha de setores indisponível para este entorno.</div>
          ) : setores ? (
            <>
              <div style={{ font: '600 10px/1.4 var(--f-ui)', color: 'var(--tx-label)', marginBottom: 3 }}>
                {CAMADAS.find((c) => c.chave === camada)?.legenda}
              </div>
              {setores.faixas[camada].map((f) => (
                <div key={f.rotulo} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  {/* O rótulo do núcleo é ASCII ("ate") porque também vai ao PDF (fonte latin-1);
                      na tela ele sai acentuado, só na exibição — o valor bruto não muda. */}
                  <span style={{ width: 10, height: 10, borderRadius: 2, background: `rgb(${f.cor.slice(0, 3).join(',')})` }} />{' '}
                  {f.rotulo.replace(/^ate /, 'até ')}
                </div>
              ))}
            </>
          ) : null
        ) : (
          <>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <img src="/logo-wellhub.png" alt="" width={14} height={14} style={{ display: 'block' }} /> Independentes (Wellhub)
            </div>
            <div style={{ color: 'var(--tx-muted)' }}>Logos = redes · anéis de 1 e 2 km</div>
          </>
        )}
      </div>

      {!zoomArmado && (
        <div style={{ ...painel, right: 44, top: 10, padding: '5px 9px', font: '500 10px/1 var(--f-ui)', color: 'var(--tx-muted)' }}>
          clique para a roda aproximar
        </div>
      )}

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
            padding: '9px 11px',
            backdropFilter: 'blur(16px)',
            boxShadow: 'var(--sh-pop)',
            zIndex: 30,
            minWidth: 190,
            font: '400 11.5px/1.5 var(--f-ui)',
            color: 'var(--tx-soft)',
          }}
        >
          <div style={{ font: '700 12.5px/1.25 var(--f-ui)', color: 'var(--tx-max)' }}>
            {hover.p.nome ?? nomeRede(hover.p.rede)}
          </div>
          <div style={{ color: 'var(--tx-muted)' }}>
            {hover.p.classe === 'cadeia' ? `Rede ${nomeRede(hover.p.rede)}` : 'Independente'} · {metros(hover.p.distancia_m)} de {nome}
          </div>
          {hover.p.plano && (
            <div>
              TotalPass <strong style={{ color: 'var(--tx-strong)' }}>{hover.p.plano}</strong>
              {hover.p.preco_plano != null ? ` (R$ ${num(hover.p.preco_plano, 2)})` : ''}
            </div>
          )}
          {hover.p.plano_wellhub && (
            <div>
              Wellhub <strong style={{ color: 'var(--tx-strong)' }}>{hover.p.plano_wellhub}</strong>
              {hover.p.preco_plano_wellhub != null ? ` (R$ ${num(hover.p.preco_plano_wellhub, 2)})` : ''}
            </div>
          )}
          {hover.p.nota_wellhub !== null && (
            <div>
              Nota Wellhub <strong style={{ color: 'var(--tx-strong)' }}>{num(hover.p.nota_wellhub, 2)}</strong>
              {hover.p.avaliacoes !== null ? ` (${num(hover.p.avaliacoes)} avaliações)` : ''}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

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
