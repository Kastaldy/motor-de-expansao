import type { CSSProperties, ReactNode } from 'react'

import type { Tom } from '../lib/types'

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
