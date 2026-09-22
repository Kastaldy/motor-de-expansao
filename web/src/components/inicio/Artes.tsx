/**
 * As seis ilustrações dos cards do Início.
 *
 * Vêm do mockup de design ("Início · Expansão + Operações", 2026-09-22) e reproduzem a
 * geometria dele traço a traço. O que MUDOU na portagem foi só a cor: o mockup cravava
 * `#2dd4bf` / `#f472b6` / `rgba(232,238,240,·)` em cada forma, e cor cravada não tem par
 * no tema claro — o Início ficaria com seis retângulos escuros no meio do gelo. Aqui
 * toda cor é token (`--ac` na trilha de expansão, `--ops` na de operações) e a opacidade
 * do mockup vira `fillOpacity`/`strokeOpacity`, que é o mesmo pixel no escuro e segue o
 * tema no claro.
 *
 * As duas malhas de hexágono não estão aqui: 360 polígonos cada, com os seis vértices
 * escritos por extenso, eram 62 KB de marcação por ilustração. Elas moram compactadas
 * em `hexgrid-dados.ts` e a geometria se reconstrói no render (`hexPath`).
 *
 * Todas desenham num `viewBox` 240x150 e escalam com o quadro do card.
 */

import type { ArteInicio } from '../../lib/inicio'
import {
  ANEIS_BRASIL,
  HEXES_BRASIL,
  HEXES_ESTADO,
  RAIO_BRASIL,
  RAIO_ESTADO,
  type HexArte,
} from './hexgrid-dados'

function Quadro({ children }: { children: React.ReactNode }) {
  return (
    <svg
      width="100%"
      height="100%"
      viewBox="0 0 240 150"
      preserveAspectRatio="xMidYMid meet"
      aria-hidden
      style={{ display: 'block' }}
    >
      {children}
    </svg>
  )
}

/* ---------------------------------------------------------------------------
   Malhas de hexágono (trilha de expansão)
   --------------------------------------------------------------------------- */

/**
 * Vértices de um hexágono de topo pontudo, como o exportador do mockup os escrevia:
 * altura = 2R, largura = √3·R. Reconstruir aqui é o que permite guardar só o centro.
 */
function hexPath(h: HexArte, r: number): string {
  const meiaLargura = (Math.sqrt(3) / 2) * r
  const meiaAltura = r / 2
  const p = [
    [h.cx + meiaLargura, h.cy - meiaAltura],
    [h.cx, h.cy - r],
    [h.cx - meiaLargura, h.cy - meiaAltura],
    [h.cx - meiaLargura, h.cy + meiaAltura],
    [h.cx, h.cy + r],
    [h.cx + meiaLargura, h.cy + meiaAltura],
  ]
  return p.map(([x, y]) => `${x.toFixed(2)},${y.toFixed(2)}`).join(' ')
}

function Malha({
  hexes,
  raio,
  alfaTraco,
}: {
  hexes: readonly HexArte[]
  raio: number
  alfaTraco: number
}) {
  return (
    <>
      {hexes.map((h, i) => (
        <polygon
          key={i}
          points={hexPath(h, raio)}
          fill="var(--ac)"
          fillOpacity={h.alfa}
          stroke="var(--ac)"
          strokeOpacity={alfaTraco}
          strokeWidth={0.6}
        />
      ))}
    </>
  )
}

/** Brasil inteiro, com as unidades Ultra aneladas — o card da fila nacional. */
function ArteBrasil() {
  return (
    <Quadro>
      <Malha hexes={HEXES_BRASIL} raio={RAIO_BRASIL} alfaTraco={0.22} />
      {ANEIS_BRASIL.map(([cx, cy]) => (
        <circle
          key={`${cx}-${cy}`}
          cx={cx}
          cy={cy}
          r={7}
          fill="none"
          stroke="var(--ac)"
          strokeWidth={1.2}
        />
      ))}
    </Quadro>
  )
}

/** Um estado em recorte — o card do funil de 5 camadas. */
function ArteEstado() {
  return (
    <Quadro>
      <Malha hexes={HEXES_ESTADO} raio={RAIO_ESTADO} alfaTraco={0.25} />
    </Quadro>
  )
}

/** Raio de 1 km com o pino no centro e concorrentes em volta — o card do ponto. */
function ArtePonto() {
  return (
    <Quadro>
      <circle
        cx={120}
        cy={76}
        r={52}
        fill="var(--ac)"
        fillOpacity={0.08}
        stroke="var(--ac)"
        strokeDasharray="4 4"
      />
      {/* Os quatro pontos laranja são CONCORRENTES, e não unidades Ultra: a mesma
          distinção de cor que o mapa já faz. */}
      {[
        [80, 52],
        [162, 98],
        [150, 40],
        [92, 112],
      ].map(([cx, cy]) => (
        <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r={4} fill="var(--gr-coral)" />
      ))}
      <path
        d="M120 88c-10-12-15-19-15-27a15 15 0 0130 0c0 8-5 15-15 27z"
        fill="var(--ac)"
      />
      <circle cx={120} cy={61} r={5.5} fill="var(--ac-on)" />
    </Quadro>
  )
}

/* ---------------------------------------------------------------------------
   Trilha de operações
   --------------------------------------------------------------------------- */

/** Fundo das caixas internas das artes de operações (janela, cartão, cartela). */
const CAIXA = 'var(--surf-card)'
/** Fundo dos recortes por dentro dessas caixas (KPI, gráfico, linha de tabela). */
const CAIXA_FUNDA = 'var(--bg-base)'

/** Painel com KPIs, série e rosca — o card do panorama da rede. */
function ArtePainel() {
  const kpis = [22, 72, 122, 172]
  return (
    <Quadro>
      <rect
        x={14}
        y={8}
        width={212}
        height={134}
        rx={10}
        fill={CAIXA}
        stroke="var(--ops)"
        strokeOpacity={0.35}
      />
      <path d="M14 18a10 10 0 0110-10h192a10 10 0 0110 10v4H14z" fill={CAIXA_FUNDA} />
      {[24, 32, 40].map((cx) => (
        <circle key={cx} cx={cx} cy={15} r={2.2} fill="var(--tx-max)" fillOpacity={0.25} />
      ))}
      <rect x={150} y={12} width={66} height={6} rx={3} fill="var(--tx-max)" fillOpacity={0.12} />

      {/* Fila de KPIs. O primeiro vem cheio e os outros esmaecidos, como no mockup:
          é a leitura de "um número manda, os outros acompanham". */}
      {kpis.map((x, i) => (
        <g key={x}>
          <rect
            x={x}
            y={28}
            width={44}
            height={26}
            rx={5}
            fill={CAIXA_FUNDA}
            stroke="var(--tx-max)"
            strokeOpacity={0.08}
          />
          <rect
            x={x + 6}
            y={33}
            width={18}
            height={3}
            rx={1.5}
            fill="var(--tx-max)"
            fillOpacity={0.25}
          />
          <rect
            x={x + 6}
            y={40}
            width={i === 0 ? 20 : 26}
            height={7}
            rx={2}
            fill="var(--ops)"
            fillOpacity={i === 0 ? 1 : 0.6}
          />
        </g>
      ))}

      <rect
        x={22}
        y={60}
        width={122}
        height={46}
        rx={5}
        fill={CAIXA_FUNDA}
        stroke="var(--tx-max)"
        strokeOpacity={0.08}
      />
      <polygon
        points="28,96 42,90 56,92 70,82 84,85 98,76 112,78 126,69 138,66 138,102 28,102"
        fill="var(--ops)"
        fillOpacity={0.12}
      />
      <polyline
        points="28,96 42,90 56,92 70,82 84,85 98,76 112,78 126,69 138,66"
        fill="none"
        stroke="var(--ops)"
        strokeWidth={1.6}
        strokeLinejoin="round"
      />

      <rect
        x={150}
        y={60}
        width={68}
        height={46}
        rx={5}
        fill={CAIXA_FUNDA}
        stroke="var(--tx-max)"
        strokeOpacity={0.08}
      />
      <circle
        cx={184}
        cy={83}
        r={15}
        fill="none"
        stroke="var(--ops)"
        strokeOpacity={0.18}
        strokeWidth={7}
      />
      <circle
        cx={184}
        cy={83}
        r={15}
        fill="none"
        stroke="var(--ops)"
        strokeWidth={7}
        strokeDasharray="58.4 94.2"
        transform="rotate(-90 184 83)"
      />

      <rect
        x={22}
        y={112}
        width={196}
        height={24}
        rx={5}
        fill={CAIXA_FUNDA}
        stroke="var(--tx-max)"
        strokeOpacity={0.08}
      />
      {[
        { y: 117, largura: 110, alfa: 0.5 },
        { y: 126, largura: 80, alfa: 0.3 },
      ].map(({ y, largura, alfa }) => (
        <g key={y}>
          <rect x={28} y={y} width={40} height={4} rx={2} fill="var(--tx-max)" fillOpacity={0.22} />
          <rect x={76} y={y} width={largura} height={4} rx={2} fill="var(--ops)" fillOpacity={alfa} />
          <rect x={196} y={y} width={16} height={4} rx={2} fill="var(--tx-max)" fillOpacity={0.18} />
        </g>
      ))}
    </Quadro>
  )
}

/** Silhueta do estado com o master no centro e as unidades penduradas nele. */
const CONTORNO_ESTADO =
  '94.7,146.0 91.1,143.9 89.6,142.0 87.5,141.2 86.4,141.4 83.1,139.3 77.6,138.4 74.5,137.0 72.8,135.3 71.3,135.5 67.3,132.7 64.6,132.3 62.0,129.6 60.4,129.2 59.7,129.8 56.6,129.8 54.0,128.7 53.6,129.0 52.3,126.8 54.3,124.3 55.3,124.3 56.5,123.0 55.7,122.2 52.6,121.8 51.1,123.1 49.5,122.1 48.7,117.5 50.2,116.2 50.2,115.4 48.9,114.1 48.9,112.7 48.3,111.4 46.8,110.1 46.6,106.3 47.6,103.6 47.2,101.9 48.5,99.4 50.4,97.1 51.2,93.3 52.2,93.2 53.0,91.9 54.9,91.3 56.3,89.7 56.9,87.6 57.8,87.3 59.4,85.5 57.7,83.8 57.9,81.9 59.5,81.4 61.2,78.7 64.1,77.8 65.1,76.9 66.7,73.6 71.1,73.6 72.6,72.2 73.6,72.4 74.8,71.2 76.5,68.7 76.0,66.8 77.5,65.5 77.5,64.3 78.1,63.4 77.7,62.2 78.3,61.3 78.6,59.6 81.2,57.0 82.2,57.0 83.3,56.0 84.1,56.2 85.0,55.3 86.9,56.6 89.7,54.0 89.7,52.7 90.8,51.6 90.5,50.6 92.2,46.6 91.6,44.1 92.2,41.1 93.3,39.4 93.1,38.4 93.4,38.1 94.2,38.5 95.0,37.8 94.1,35.5 94.8,34.6 94.5,31.2 94.1,30.6 95.8,29.1 96.2,26.6 98.3,24.5 98.1,23.7 99.4,22.2 99.8,20.9 99.8,18.0 99.4,17.1 99.8,16.1 101.1,15.3 101.9,10.2 103.0,9.4 104.2,6.8 108.5,4.0 108.4,4.7 107.2,6.0 107.6,7.3 105.7,10.2 105.5,12.1 107.9,13.9 113.2,15.1 124.1,21.5 124.8,20.7 124.4,18.0 127.0,13.5 129.2,11.8 130.2,13.5 132.1,14.7 134.2,12.0 136.8,14.4 136.8,15.0 137.8,16.0 138.4,16.0 139.6,17.1 140.7,19.1 141.4,18.5 142.3,18.8 142.1,20.5 143.0,21.5 148.5,18.9 148.6,20.3 148.2,20.7 149.1,21.9 150.2,20.6 152.5,22.1 155.2,22.3 157.8,25.0 158.9,23.7 158.3,22.2 158.7,21.1 158.3,19.3 158.8,18.1 160.3,18.3 161.3,19.8 162.0,19.6 163.4,21.0 164.1,20.6 165.8,21.0 167.0,19.8 168.5,20.0 171.9,18.5 176.5,15.4 182.0,15.4 182.9,14.4 183.2,12.4 184.4,13.4 184.2,14.8 184.9,15.6 187.6,15.1 189.3,14.3 188.9,15.4 187.2,16.2 186.8,16.0 185.4,17.6 185.6,19.9 185.2,20.7 185.6,21.1 185.4,22.0 186.4,22.9 189.9,21.3 190.7,21.4 190.6,22.3 187.1,24.5 187.5,25.4 186.9,26.6 188.4,27.9 186.5,29.6 186.9,30.0 186.5,30.6 187.1,31.5 186.3,32.3 186.9,32.9 186.3,34.6 187.3,35.7 186.9,37.8 188.3,39.1 188.9,38.9 189.9,40.0 190.4,39.8 193.4,43.0 193.0,44.1 191.3,45.3 191.9,46.6 191.5,48.1 191.9,48.5 191.3,49.5 191.5,51.9 189.7,54.7 187.2,54.9 185.7,54.5 185.2,54.0 185.4,53.1 183.4,51.1 181.7,50.3 180.4,51.6 181.2,53.1 180.8,55.0 181.3,57.2 178.8,57.9 176.7,56.6 174.4,56.2 173.2,57.3 173.9,58.4 173.0,59.9 174.9,62.6 174.7,63.4 173.0,64.7 172.6,67.0 174.5,68.3 175.5,73.5 170.6,74.7 169.8,75.3 168.7,74.9 167.0,76.4 166.0,76.2 165.2,76.9 165.4,77.7 164.6,78.8 165.2,80.5 164.6,82.2 163.1,83.8 162.5,86.1 166.7,89.3 167.5,93.5 169.0,95.4 169.0,96.0 164.6,99.8 163.1,101.7 163.1,102.3 161.0,103.8 161.0,104.9 162.4,106.7 163.2,106.2 165.1,106.5 166.3,108.0 166.3,109.3 164.8,110.8 164.2,112.4 165.9,117.1 160.9,120.5 160.5,120.1 158.9,121.7 159.3,122.1 159.0,122.6 152.7,125.8 150.6,124.3 148.9,124.3 146.4,122.6 145.1,123.5 143.5,123.1 142.0,123.5 140.1,122.4 139.0,122.4 135.0,123.5 132.9,122.0 130.0,124.3 128.9,123.7 123.9,129.0 121.2,126.2 120.5,126.9 119.5,126.9 118.6,128.1 117.8,127.7 115.9,128.7 114.8,128.7 114.0,128.1 113.0,128.5 111.5,127.9 110.0,129.4 106.0,129.6 101.5,135.0 101.7,136.6 101.1,137.7 97.6,139.5 95.0,142.1 94.1,144.0 95.2,145.5 94.7,146.0'

const UNIDADES_DA_REDE: readonly (readonly [number, number])[] = [
  [73.7, 76.7],
  [139.1, 116.6],
  [59.9, 119.0],
  [142.6, 91.4],
  [111.3, 123.6],
  [113.7, 43.5],
  [159.1, 60.9],
  [57.3, 93.4],
  [160.9, 42.3],
  [74.6, 107.9],
  [91.2, 129.7],
]

function ArteRede() {
  return (
    <Quadro>
      <polygon
        points={CONTORNO_ESTADO}
        fill="var(--ops)"
        fillOpacity={0.08}
        stroke="var(--ops)"
        strokeOpacity={0.55}
        strokeWidth={1.2}
        strokeLinejoin="round"
      />
      {UNIDADES_DA_REDE.map(([x, y]) => (
        <line
          key={`l-${x}-${y}`}
          x1={120}
          y1={78}
          x2={x}
          y2={y}
          stroke="var(--ops)"
          strokeOpacity={0.45}
          strokeWidth={1}
          strokeDasharray="2.5 2.5"
        />
      ))}
      {UNIDADES_DA_REDE.map(([x, y]) => (
        <circle key={`c-${x}-${y}`} cx={x} cy={y} r={3.6} fill="var(--ops)" />
      ))}
      {/* O master, no centro: o recorte da rede é por região OU por franqueado. */}
      <circle cx={120} cy={78} r={15} fill={CAIXA} stroke="var(--ops)" strokeWidth={1.6} />
      <circle cx={120} cy={74} r={4.2} fill="var(--ops)" />
      <path d="M112 87a8 7 0 0116 0z" fill="var(--ops)" />
    </Quadro>
  )
}

/** Pino ligado a um cartão de métricas — o card da ficha de uma unidade. */
function ArteFicha() {
  return (
    <Quadro>
      <rect
        x={104}
        y={30}
        width={116}
        height={92}
        rx={12}
        fill={CAIXA}
        stroke="var(--ops)"
        strokeOpacity={0.45}
      />
      <rect x={118} y={46} width={60} height={8} rx={4} fill="var(--ops)" />
      <rect x={118} y={64} width={88} height={6} rx={3} fill="var(--tx-max)" fillOpacity={0.25} />
      <rect x={118} y={78} width={70} height={6} rx={3} fill="var(--tx-max)" fillOpacity={0.18} />
      <rect x={118} y={96} width={24} height={14} rx={3} fill="var(--ops)" fillOpacity={0.35} />
      <rect x={148} y={90} width={24} height={20} rx={3} fill="var(--ops)" fillOpacity={0.55} />
      <rect x={178} y={84} width={24} height={26} rx={3} fill="var(--ops)" />
      <line
        x1={76}
        y1={76}
        x2={104}
        y2={76}
        stroke="var(--ops)"
        strokeOpacity={0.5}
        strokeDasharray="3 3"
      />
      <circle
        cx={60}
        cy={76}
        r={16}
        fill="var(--ops)"
        fillOpacity={0.08}
        stroke="var(--ops)"
        strokeOpacity={0.5}
      />
      <g transform="translate(60 74) scale(0.55)">
        <path d="M0 22c-10-12-15-19-15-27a15 15 0 0130 0c0 8-5 15-15 27z" fill="var(--ops)" />
        <circle cx={0} cy={-5} r={5.5} fill="var(--ops-on)" />
      </g>
    </Quadro>
  )
}

const ARTES: Record<ArteInicio, () => React.JSX.Element> = {
  brasil: ArteBrasil,
  estado: ArteEstado,
  ponto: ArtePonto,
  painel: ArtePainel,
  rede: ArteRede,
  ficha: ArteFicha,
}

/** Desenha a arte de um card. Chave desconhecida não desenha nada — o card continua
 *  legível pelo texto, que é quem carrega o significado. */
export default function Arte({ nome }: { nome: ArteInicio }) {
  const Componente = ARTES[nome]
  return Componente ? <Componente /> : null
}
