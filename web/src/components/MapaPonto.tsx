import { FlyToInterpolator } from '@deck.gl/core'
import { H3HexagonLayer } from '@deck.gl/geo-layers'
import { ScatterplotLayer } from '@deck.gl/layers'
import DeckGL from '@deck.gl/react'
import { useEffect, useRef, useState } from 'react'
import { Map } from 'react-map-gl/maplibre'

import { HEX_FILL_ALPHA, scoreBandToColor } from '../lib/colors'
import { num } from '../lib/format'
import {
  VISTA_BRASIL,
  faixaDoResidual,
  motivoSemHexagonos,
  vistaDoPonto,
  vizinhosDesenhaveis,
  type VizinhoDesenhavel,
} from '../lib/mapa-ponto'
import type { PontoPayload, PontoVizinho } from '../lib/types'

import 'maplibre-gl/dist/maplibre-gl.css'

/**
 * O mapa do modo de ponto, agora em TELA CHEIA.
 *
 * Sucede o `MiniMapaPonto`, que era uma caixa de 300px dentro da ficha. A tela passou a
 * abrir no mapa e a ficha virou gaveta, entao este componente ganhou duas obrigacoes que
 * a caixa nao tinha: montar SEM ponto nenhum resolvido (a tela abre assim) e DECLARAR na
 * propria superficie quando nao ha' hexagono para colorir — antes esse aviso era uma
 * secao da ficha, e com a ficha fechada ele sumiria em silencio.
 *
 * POR QUE NAO REUSA O `HexMap`. Aquele componente e' do FUNIL: exige um `Passo` e colore
 * segundo a camada ativa. Aqui nao ha' funil — ha' um endereco e a vizinhanca dele.
 * Fabricar um `Passo` falso so' para satisfazer a assinatura acoplaria o modo de ponto a
 * uma semantica que ele nao tem, e obrigaria a carregar a particao inteira da UF.
 *
 * O QUE ELE MOSTRA. Cor por RESIDUAL (alunos nao atendidos), na mesma rampa de 10 faixas
 * do resto do produto — regra visual canonica do projeto. O hexagono do ponto ganha
 * contorno branco, que e' como o mapa grande ja' marca selecao.
 *
 * POR QUE ISSO IMPORTA. Um endereco pode estar num hexagono saturado com residual
 * sobrando a 1 km dali. Medido na Av. Paulista: o hexagono do ponto tem residual 0 e um
 * vizinho tem 7.557 alunos. Sem o mapa, a ficha diria so' "residual 0" e o operador
 * descartaria a regiao inteira.
 */

/** Camera. Local de proposito: nao herda a do `HexMap`, que carrega semantica de funil. */
interface Vista {
  longitude: number
  latitude: number
  zoom: number
  pitch: number
  bearing: number
  transitionDuration?: number
  transitionInterpolator?: FlyToInterpolator
}

const FLY = new FlyToInterpolator({ speed: 1.6 })

/** Mesmo basemap do mapa grande (CARTO Dark Matter), para as telas casarem. */
const BASEMAP = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'

function vistaInicial(ficha: PontoPayload | null): Vista {
  const base = ficha ? vistaDoPonto(ficha.lat, ficha.lng) : VISTA_BRASIL
  return { ...base, pitch: 0, bearing: 0 }
}

export default function MapaPonto({ ficha }: { ficha: PontoPayload | null }) {
  const [hover, setHover] = useState<PontoVizinho | null>(null)
  const [vista, setVista] = useState<Vista>(() => vistaInicial(ficha))

  /* Voa ate' o ponto quando ele MUDA de coordenada — colar o primeiro, trocar de aba
     entre os pontos colados, remover um. Compara pela COORDENADA e nao pela identidade
     do objeto: o `key` da ficha muda a cada re-render do pai e faria a camera voar
     sozinha, cancelando o arraste do operador no meio. */
  const coordenada = ficha ? `${ficha.lat},${ficha.lng}` : null
  const coordenadaAnterior = useRef<string | null>(null)
  useEffect(() => {
    if (!ficha || coordenada == null) return
    if (coordenadaAnterior.current === coordenada) return
    const primeira = coordenadaAnterior.current === null
    coordenadaAnterior.current = coordenada
    setVista((v) => ({
      ...v,
      ...vistaDoPonto(ficha.lat, ficha.lng),
      // Sem transicao na primeira: a tela montou ja' com o ponto (volta da Viabilidade),
      // e um voo partindo do Brasil inteiro seria teatro de 1 segundo antes do trabalho.
      transitionDuration: primeira ? 0 : 900,
      transitionInterpolator: FLY,
    }))
  }, [coordenada, ficha])

  const desenhaveis = ficha ? vizinhosDesenhaveis(ficha.vizinhos) : []
  const motivo = motivoSemHexagonos(ficha)

  const camadas = [
    new H3HexagonLayer<VizinhoDesenhavel>({
      id: 'vizinhos',
      data: desenhaveis,
      getHexagon: (d) => d.hex_id,
      extruded: false,
      stroked: true,
      filled: true,
      pickable: true,
      getFillColor: (d) => scoreBandToColor(faixaDoResidual(d.residual), HEX_FILL_ALPHA),
      // Contorno branco só no hexágono do imóvel — mesma convenção de seleção do mapa
      // grande, onde branco significa "este aqui".
      getLineColor: (d) =>
        d.hex_id === ficha?.hex_id ? [238, 243, 248, 255] : [255, 255, 255, 40],
      getLineWidth: (d) => (d.hex_id === ficha?.hex_id ? 26 : 8),
      lineWidthUnits: 'meters',
      onHover: ({ object }) => setHover((object as PontoVizinho) ?? null),
      updateTriggers: {
        getLineColor: [ficha?.hex_id],
        getLineWidth: [ficha?.hex_id],
      },
    }),
    // A coordenada EXATA do imóvel. O centroide do hexágono fica a até ~1,5 km dela,
    // então marcar só o hexágono esconderia onde o ponto realmente está.
    new ScatterplotLayer({
      id: 'ponto',
      data: ficha ? [{ lat: ficha.lat, lng: ficha.lng }] : [],
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
    <div style={{ position: 'absolute', inset: 0, background: 'var(--bg-lift)' }}>
      <DeckGL
        viewState={vista}
        onViewStateChange={(e) => setVista(e.viewState as Vista)}
        controller={{ dragRotate: false }}
        layers={camadas}
        /* Strings, nao numeros: o `style` do DeckGL e' tipado como CSSStyleDeclaration,
           onde todo valor e' string — `inset: 0` nao compila. */
        style={{ position: 'absolute', top: '0', left: '0', width: '100%', height: '100%' }}
      >
        <Map mapStyle={BASEMAP} attributionControl={{ compact: true }} reuseMaps />
      </DeckGL>

      {/* Legenda / leitura do hover. Canto inferior esquerdo: o direito é do botão que
          puxa a gaveta, e o topo é da caixa de colar. */}
      <div
        style={{
          position: 'absolute',
          left: 16,
          bottom: 16,
          padding: '9px 12px',
          borderRadius: 10,
          background: 'var(--surf-panel)',
          border: '1px solid var(--line-soft)',
          backdropFilter: 'blur(14px)',
          font: '500 11px/1.4 var(--f-ui)',
          color: 'var(--tx-soft)',
          pointerEvents: 'none',
          maxWidth: 260,
        }}
      >
        {hover ? (
          <>
            <span className="num" style={{ color: 'var(--tx-max)', fontWeight: 700 }}>
              {num(hover.residual)} alunos
            </span>{' '}
            de residual
            {hover.hex_id === ficha?.hex_id && (
              <span style={{ color: 'var(--tx-sub)' }}> · hexágono do imóvel</span>
            )}
          </>
        ) : desenhaveis.length > 0 ? (
          <>
            Cor por <strong style={{ color: 'var(--tx-max)' }}>residual</strong>: vermelho é
            saturado, verde tem espaço. Passe o mouse para ver os números.
          </>
        ) : (
          <>O hexágono do imóvel e os 18 vizinhos aparecem aqui quando você colar um ponto.</>
        )}
      </div>

      {/* Motivo declarado. Sem isto, o mapa ficaria só com o basemap e o operador leria
          como falha de rede — e com a ficha fechada não haveria onde mais dizer. */}
      {motivo && (
        <div
          style={{
            position: 'absolute',
            left: '50%',
            transform: 'translateX(-50%)',
            bottom: 16,
            maxWidth: 460,
            padding: '10px 14px',
            borderRadius: 10,
            background: 'var(--surf-panel)',
            border: '1px solid var(--line-soft)',
            backdropFilter: 'blur(14px)',
            font: '400 11.5px/1.5 var(--f-ui)',
            color: 'var(--tx-narrative)',
            textAlign: 'center',
          }}
        >
          <strong style={{ color: 'var(--tx-max)', fontWeight: 600 }}>
            Sem leitura de mercado na vizinhança.
          </strong>{' '}
          {motivo}
        </div>
      )}
    </div>
  )
}
