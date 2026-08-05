import type { CSSProperties, ReactNode } from 'react'

import { COR_SEVERIDADE, type LeituraDelta } from '../lib/exec'
import { num, pct } from '../lib/format'
import { caminhoSparkline } from '../lib/sparkline'
import type { RedeSeveridade, Tom } from '../lib/types'

/* ---------------------------------------------------------------------------
   Primitivas compartilhadas. Os valores saem do template de referencia; o que
   muda aqui e a tipografia (serif para narrativa, mono para numero).
   --------------------------------------------------------------------------- */

const TONS: Record<Tom, { fg: string; bg: string }> = {
  blue: { fg: '#6fa4f7', bg: 'rgba(75,139,245,.16)' },
  green: { fg: '#5fd08c', bg: 'rgba(60,200,120,.15)' },
  amber: { fg: '#e0b25a', bg: 'rgba(217,164,65,.15)' },
  red: { fg: '#ff8a99', bg: 'rgba(255,90,110,.15)' },
  gray: { fg: '#98a4b2', bg: 'rgba(255,255,255,.08)' },
}

export function Chip({ tom = 'gray', children }: { tom?: Tom; children: ReactNode }) {
  const c = TONS[tom]
  return (
    <span
      style={{
        font: '700 10px/1 var(--f-ui)',
        textTransform: 'uppercase',
        letterSpacing: '.05em',
        padding: '4px 8px',
        borderRadius: 'var(--r-sm)',
        color: c.fg,
        background: c.bg,
        flexShrink: 0,
        whiteSpace: 'nowrap',
      }}
    >
      {children}
    </span>
  )
}

/** Rotulo de secao — mono, caixa alta, discreto. */
export function Eyebrow({
  children,
  cor = 'var(--ac)',
  dot = false,
}: {
  children: ReactNode
  cor?: string
  dot?: boolean
}) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 7,
        font: '600 11px/1 var(--f-num)',
        textTransform: 'uppercase',
        letterSpacing: '.09em',
        color: cor,
      }}
    >
      {dot && (
        <span
          style={{
            width: 7,
            height: 7,
            borderRadius: '50%',
            background: cor,
            flexShrink: 0,
          }}
        />
      )}
      {children}
    </div>
  )
}

export function Glass({
  children,
  style,
  onClick,
}: {
  children: ReactNode
  style?: CSSProperties
  onClick?: () => void
}) {
  return (
    <div
      onClick={onClick}
      style={{
        background: 'var(--surf-card)',
        border: '1px solid var(--line)',
        borderRadius: 'var(--r-lg)',
        backdropFilter: 'blur(14px)',
        ...style,
      }}
    >
      {children}
    </div>
  )
}

export function Kpi({
  label,
  valor,
  sub,
  tone,
}: {
  label: string
  valor: string
  sub?: string
  tone?: string
}) {
  return (
    <Glass style={{ flex: 1, padding: '15px 17px', minWidth: 0 }}>
      <div style={{ font: '500 11px/1.2 var(--f-ui)', color: 'var(--tx-label)' }}>
        {label}
      </div>
      <div
        className="num"
        style={{
          font: '700 24px/1 var(--f-num)',
          color: tone ?? 'var(--tx-max)',
          marginTop: 8,
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
      >
        {valor}
      </div>
      {sub && (
        <div
          style={{ font: '400 10.5px/1.3 var(--f-ui)', color: 'var(--tx-sub)', marginTop: 6 }}
        >
          {sub}
        </div>
      )}
    </Glass>
  )
}

export function Botao({
  children,
  onClick,
  variante = 'primario',
  disabled,
  style,
  title,
}: {
  children: ReactNode
  onClick?: () => void
  variante?: 'primario' | 'ghost'
  disabled?: boolean
  style?: CSSProperties
  title?: string
}) {
  const base: CSSProperties = {
    borderRadius: 'var(--r-md)',
    font: '600 13px/1 var(--f-ui)',
    transition: 'filter .15s ease, opacity .15s ease',
    opacity: disabled ? 0.45 : 1,
  }
  const estilo: CSSProperties =
    variante === 'primario'
      ? {
          ...base,
          background: 'var(--ac)',
          color: 'var(--ac-on)',
          fontWeight: 700,
          padding: '12px 18px',
          boxShadow: disabled ? 'none' : 'var(--ac-glow)',
        }
      : {
          ...base,
          background: 'transparent',
          color: 'var(--tx-soft)',
          border: '1px solid var(--line-strong)',
          padding: '11px 14px',
        }
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={title}
      style={{ ...estilo, ...style }}
      onMouseEnter={(e) => {
        if (!disabled) e.currentTarget.style.filter = 'brightness(1.12)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.filter = 'none'
      }}
    >
      {children}
    </button>
  )
}

/**
 * Indicador de carregamento inline. Anima por SMIL (`animateTransform`) e nao por
 * keyframes CSS: nao ha folha de estilo global aqui e assim o icone e' autocontido.
 * Herda a cor do texto de quem o envolve (`currentColor`).
 */
export function Spinner({ tamanho = 14 }: { tamanho?: number }) {
  return (
    <svg width={tamanho} height={tamanho} viewBox="0 0 24 24" aria-hidden>
      <circle
        cx="12"
        cy="12"
        r="9"
        fill="none"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
        strokeDasharray="42 14"
        opacity="0.9"
      >
        <animateTransform
          attributeName="transform"
          type="rotate"
          from="0 12 12"
          to="360 12 12"
          dur="0.8s"
          repeatCount="indefinite"
        />
      </circle>
    </svg>
  )
}

/** Estado vazio / erro — sempre diz o que fazer, nunca so o que falhou. */
export function Aviso({
  titulo,
  corpo,
  acao,
}: {
  titulo: string
  corpo: string
  acao?: ReactNode
}) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 10,
        height: '100%',
        padding: 40,
        textAlign: 'center',
      }}
    >
      <div className="story" style={{ fontSize: 22, color: 'var(--tx-max)' }}>
        {titulo}
      </div>
      <div
        style={{
          font: '400 13px/1.6 var(--f-ui)',
          color: 'var(--tx-narrative)',
          maxWidth: 460,
        }}
      >
        {corpo}
      </div>
      {acao}
    </div>
  )
}

/* ---------------------------------------------------------------------------
   Primitivas da Visão Executiva 2.0 (DEC-023).

   Vivem AQUI, e não dentro de `screens/`, por uma razão medida: a
   `ExecutiveScreen` v1 declarava `Kpi`, `Delta` e `Legenda` locais, homônimos
   dos daqui e divergentes deles. Dois componentes com o mesmo nome e
   comportamento diferente no mesmo produto é bug esperando data.
   --------------------------------------------------------------------------- */

/**
 * Chip de variação vs M-1, com a direção CERTA para cada métrica.
 *
 * Promovido da `ExecutiveScreen` (era local). Recebe a leitura já pronta de
 * `lib/exec.lerDelta`, que sabe que churn subindo é ruim e que churn/NPS variam em
 * PONTOS, não em percentual do percentual.
 */
export function Delta({
  leitura,
  tamanho = 11,
}: {
  leitura: LeituraDelta | null
  tamanho?: number
}) {
  if (!leitura) return null
  const cor = leitura.estavel
    ? 'var(--tx-muted)'
    : leitura.bom
      ? 'var(--pos, #37b26b)'
      : 'var(--neg, #ff5a6e)'
  const texto =
    leitura.modo === 'pct'
      ? pct(leitura.valor, 1)
      : `${num(leitura.valor, 1)} ${'pts'}`
  return (
    <span
      className="num"
      style={{ font: `700 ${tamanho}px/1 var(--f-num)`, color: cor, whiteSpace: 'nowrap' }}
    >
      {leitura.estavel ? '—' : leitura.subiu ? '▲' : '▼'} {leitura.estavel ? '' : texto}
    </span>
  )
}

/** Bolinha do semáforo do diagnóstico. Uma cor por linha, e só uma. */
export function Semaforo({
  nivel,
  rotulo,
  tamanho = 9,
}: {
  nivel: RedeSeveridade
  rotulo?: string
  tamanho?: number
}) {
  return (
    <span
      title={rotulo}
      aria-label={rotulo}
      style={{
        display: 'inline-block',
        width: tamanho,
        height: tamanho,
        borderRadius: '50%',
        background: COR_SEVERIDADE[nivel],
        flexShrink: 0,
        boxShadow: nivel === 'alta' ? `0 0 0 3px ${COR_SEVERIDADE.alta}22` : undefined,
      }}
    />
  )
}

/** Barra segmentada (semáforo da rede, split recorrentes × agregadores). */
export function BarraSegmentada({
  partes,
  altura = 10,
  onParte,
}: {
  partes: { chave: string; valor: number; cor: string; rotulo: string }[]
  altura?: number
  onParte?: (chave: string) => void
}) {
  const total = partes.reduce((s, p) => s + p.valor, 0) || 1
  return (
    <div style={{ display: 'flex', height: altura, borderRadius: altura / 2, overflow: 'hidden', background: 'var(--surf-raised)' }}>
      {partes.map((p) => (
        <button
          key={p.chave}
          type="button"
          title={`${p.rotulo}: ${p.valor}`}
          onClick={onParte ? () => onParte(p.chave) : undefined}
          style={{
            width: `${(100 * p.valor) / total}%`,
            background: p.cor,
            border: 'none',
            padding: 0,
            cursor: onParte ? 'pointer' : 'default',
          }}
        />
      ))}
    </div>
  )
}

/** Sparkline de 12 meses. SVG à mão — o projeto não tem biblioteca de gráficos. */
export function SparklineSvg({
  valores,
  largura = 76,
  altura = 22,
  cor = 'var(--ac)',
}: {
  valores: (number | null)[]
  largura?: number
  altura?: number
  cor?: string
}) {
  const s = caminhoSparkline(valores, largura, altura)
  if (!s.linha) {
    return <span style={{ font: '400 10px/1 var(--f-ui)', color: 'var(--tx-muted)' }}>sem série</span>
  }
  return (
    <svg width={largura} height={altura} aria-hidden style={{ display: 'block' }}>
      {s.area && <path d={s.area} fill={cor} opacity={0.14} />}
      <path d={s.linha} fill="none" stroke={cor} strokeWidth={1.4} strokeLinejoin="round" />
      {s.ultimo && <circle cx={s.ultimo.x} cy={s.ultimo.y} r={1.9} fill={cor} />}
    </svg>
  )
}

/** Régua com meta marcada — usada no NPS, cuja meta oficial da rede é 60. */
export function BarraMeta({
  valor,
  meta,
  minimo = 0,
  maximo = 100,
  altura = 8,
}: {
  valor: number | null
  meta: number
  minimo?: number
  maximo?: number
  altura?: number
}) {
  const fatia = (v: number) => Math.min(100, Math.max(0, (100 * (v - minimo)) / (maximo - minimo)))
  return (
    <div style={{ position: 'relative', height: altura, background: 'var(--surf-raised)', borderRadius: altura / 2 }}>
      {valor !== null && (
        <div
          style={{
            width: `${fatia(valor)}%`,
            height: '100%',
            borderRadius: altura / 2,
            background: valor >= meta ? 'var(--pos, #37b26b)' : 'var(--ac)',
          }}
        />
      )}
      <div
        title={`Meta da rede: ${meta}`}
        style={{
          position: 'absolute',
          left: `${fatia(meta)}%`,
          top: -2,
          width: 2,
          height: altura + 4,
          background: 'var(--tx-soft)',
        }}
      />
    </div>
  )
}
