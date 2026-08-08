import { H3HexagonLayer } from '@deck.gl/geo-layers'
import { ScatterplotLayer } from '@deck.gl/layers'
import DeckGL from '@deck.gl/react'
import { useState } from 'react'
import { Map } from 'react-map-gl/maplibre'

import { HEX_FILL_ALPHA, scoreBandToColor } from '../lib/colors'
import { num } from '../lib/format'
import type { PontoVizinho } from '../lib/types'

import 'maplibre-gl/dist/maplibre-gl.css'

/**
 * Mini-mapa do modo de ponto: o hexagono do imovel e os 18 vizinhos.
 *
 * POR QUE NAO REUSA O `HexMap`. Aquele componente e' do FUNIL: exige um `Passo`, e
 * colore/rotula segundo a camada ativa. Aqui nao ha funil — ha um endereco e a
 * vizinhanca dele. Fabricar um `Passo` falso so' para satisfazer a assinatura
 * acoplaria o modo de ponto a uma semantica que ele nao tem.
 *
 * O QUE ELE MOSTRA. Cor por RESIDUAL (alunos nao atendidos), na mesma rampa de 10
 * faixas do resto do produto — regra visual canonica do projeto. O hexagono do ponto
 * ganha contorno branco, que e' como o mapa grande ja marca selecao.
 *
 * POR QUE ISSO IMPORTA NA FICHA. Um endereco pode estar num hexagono saturado com
 * residual sobrando a 1 km dali. Medido na Av. Paulista: o hexagono do ponto tem
 * residual 0 e um vizinho tem 7.557 alunos. Sem o mapa, a ficha diria so' "residual 0"
 * e o operador descartaria a regiao inteira.
 */
export default function MiniMapaPonto({
  hexId,
  lat,
  lng,
  vizinhos,
}: {
  hexId: string
  lat: number
  lng: number
  vizinhos: PontoVizinho[]
}) {
  const [hover, setHover] = useState<PontoVizinho | null>(null)

  const comId = vizinhos.filter((v): v is PontoVizinho & { hex_id: string } => !!v.hex_id)

  /* A rampa e' de 0-100 e o residual vem em ALUNOS. 2.500 = capacidade de uma unidade
     inteira (`CAPACIDADE_DEFAULT_CONCORRENTE_ALUNOS`), a mesma referencia que o
     `score_oportunidade_residual` usa — entao a escala do mini-mapa fala a mesma
     lingua do score, sem inventar normalizacao propria. */
  const faixaDoResidual = (alunosResiduais: number | null) =>
    alunosResiduais == null ? null : Math.min(100, (alunosResiduais / 2500) * 100)

  const camadas = [
    new H3HexagonLayer<PontoVizinho & { hex_id: string }>({
      id: 'vizinhos',
      data: comId,
      getHexagon: (d) => d.hex_id,
      extruded: false,
      stroked: true,
      filled: true,
      pickable: true,
      getFillColor: (d) => scoreBandToColor(faixaDoResidual(d.residual), HEX_FILL_ALPHA),
      // Contorno branco só no hexágono do imóvel — mesma convenção de seleção do
      // mapa grande, onde branco significa "este aqui".
      getLineColor: (d) =>
        d.hex_id === hexId ? [238, 243, 248, 255] : [255, 255, 255, 40],
      getLineWidth: (d) => (d.hex_id === hexId ? 26 : 8),
      lineWidthUnits: 'meters',
      onHover: ({ object }) => setHover((object as PontoVizinho) ?? null),
      updateTriggers: { getLineColor: [hexId], getLineWidth: [hexId] },
    }),
    // A coordenada EXATA do imóvel. O centroide do hexágono fica a até ~1,5 km dela,
    // então marcar só o hexágono esconderia onde o ponto realmente está.
    new ScatterplotLayer({
      id: 'ponto',
      data: [{ lat, lng }],
      getPosition: (d: { lat: number; lng: number }) => [d.lng, d.lat],
      getRadius: 55,
      radiusUnits: 'meters',
      radiusMinPixels: 5,
      getFillColor: [238, 243, 248, 255],
      getLineColor: [8, 11, 16, 220],
      lineWidthMinPixels: 2,
      stroked: true,
    }),
  ]

  return (
    <div
      style={{
        position: 'relative',
        height: 300,
        borderRadius: 'var(--r-md)',
        overflow: 'hidden',
        border: '1px solid var(--line-soft)',
        background: 'var(--bg-lift)',
      }}
    >
      <DeckGL
        initialViewState={{ longitude: lng, latitude: lat, zoom: 12.4, pitch: 0, bearing: 0 }}
        controller={{ dragRotate: false }}
        layers={camadas}
        style={{ position: 'absolute', top: '0', left: '0', width: '100%', height: '100%' }}
      >
        <Map mapStyle={BASEMAP} attributionControl={{ compact: true }} reuseMaps />
      </DeckGL>

      <div
        style={{
          position: 'absolute',
          left: 10,
          bottom: 10,
          padding: '7px 10px',
          borderRadius: 8,
          background: 'var(--surf-panel)',
          border: '1px solid var(--line-soft)',
          backdropFilter: 'blur(14px)',
          font: '500 10.5px/1.35 var(--f-ui)',
          color: 'var(--tx-soft)',
          pointerEvents: 'none',
          maxWidth: 220,
        }}
      >
        {hover ? (
          <>
            <span className="num" style={{ color: 'var(--tx-max)', fontWeight: 700 }}>
              {num(hover.residual)} alunos
            </span>{' '}
            de residual
            {hover.hex_id === hexId && (
              <span style={{ color: 'var(--tx-sub)' }}> · hexágono do imóvel</span>
            )}
          </>
        ) : (
          <>
            Cor por <strong style={{ color: 'var(--tx-max)' }}>residual</strong>: vermelho
            é saturado, verde tem espaço. Passe o mouse para ver os números.
          </>
        )}
      </div>
    </div>
  )
}

/** Mesmo basemap do mapa grande (CARTO Dark Matter), para as duas telas casarem. */
const BASEMAP = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'
