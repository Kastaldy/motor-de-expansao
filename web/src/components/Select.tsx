import { useEffect, useId, useRef, useState } from 'react'

/* ---------------------------------------------------------------------------
   Dropdown customizado. O <select> nativo abre o popup de opcoes em BRANCO no
   Chrome/Windows por mais que se aplique color-scheme/background — ilegivel no
   tema escuro. Este componente controla o popup, então segue o tema sempre.
   Acessivel: teclado (setas, Enter, Esc), aria-listbox, fecha ao clicar fora.
   --------------------------------------------------------------------------- */

export interface SelectProps {
  value: string
  options: { value: string; label: string }[]
  onChange: (v: string) => void
  label: string
  maxWidth?: number
}

export default function Select({ value, options, onChange, label, maxWidth = 150 }: SelectProps) {
  const [aberto, setAberto] = useState(false)
  const [foco, setFoco] = useState(-1)
  const raiz = useRef<HTMLDivElement>(null)
  const listaId = useId()

  const selecionado = options.find((o) => o.value === value)

  useEffect(() => {
    if (!aberto) return
    function fora(e: MouseEvent) {
      if (raiz.current && !raiz.current.contains(e.target as Node)) setAberto(false)
    }
    document.addEventListener('mousedown', fora)
    return () => document.removeEventListener('mousedown', fora)
  }, [aberto])

  useEffect(() => {
    if (aberto) setFoco(options.findIndex((o) => o.value === value))
  }, [aberto, options, value])

  // Fecha sempre que o valor selecionado muda. O setAberto(false) do escolher()
  // pode se perder na cascata de re-render do pai (troca de UF recarrega dados);
  // reagir a `value` garante o fechamento de forma robusta.
  useEffect(() => {
    setAberto(false)
  }, [value])

  function escolher(v: string) {
    setAberto(false)
    onChange(v)
  }

  function teclado(e: React.KeyboardEvent) {
    if (e.key === 'Escape') {
      setAberto(false)
      return
    }
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      if (aberto && foco >= 0) escolher(options[foco].value)
      else setAberto(true)
      return
    }
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault()
      if (!aberto) {
        setAberto(true)
        return
      }
      const passo = e.key === 'ArrowDown' ? 1 : -1
      setFoco((f) => (f + passo + options.length) % options.length)
    }
  }

  return (
    <div ref={raiz} style={{ position: 'relative', minWidth: 0 }}>
      <button
        type="button"
        aria-label={label}
        aria-haspopup="listbox"
        aria-expanded={aberto}
        onClick={() => setAberto((a) => !a)}
        onKeyDown={teclado}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          maxWidth,
          background: '#101a26',
          border: `1px solid ${aberto ? 'var(--ac-a30)' : 'var(--line)'}`,
          borderRadius: 8,
          padding: '6px 9px',
          color: 'var(--tx-strong)',
          font: '500 13px/1 var(--f-ui)',
          cursor: 'pointer',
        }}
      >
        <span
          style={{
            flex: 1,
            minWidth: 0,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            textAlign: 'left',
          }}
        >
          {selecionado?.label ?? value}
        </span>
        <svg
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="var(--tx-muted)"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
          style={{ flexShrink: 0, transform: aberto ? 'rotate(180deg)' : 'none', transition: 'transform .15s' }}
          aria-hidden
        >
          <path d="m6 9 6 6 6-6" />
        </svg>
      </button>

      {aberto && (
        <ul
          role="listbox"
          id={listaId}
          aria-label={label}
          style={{
            position: 'absolute',
            top: 'calc(100% + 4px)',
            left: 0,
            zIndex: 40,
            margin: 0,
            padding: 4,
            listStyle: 'none',
            minWidth: '100%',
            maxWidth: 260,
            maxHeight: 320,
            overflowY: 'auto',
            background: 'var(--surf-panel)',
            border: '1px solid var(--line-mid)',
            borderRadius: 'var(--r-md)',
            backdropFilter: 'blur(16px)',
            boxShadow: '0 14px 34px -10px rgba(0,0,0,.75)',
          }}
        >
          {options.map((o, i) => {
            const ativo = o.value === value
            const emFoco = i === foco
            return (
              <li
                key={o.value}
                role="option"
                aria-selected={ativo}
                onMouseEnter={() => setFoco(i)}
                // Seleciona no mousedown (antes de mouseup/click/foco): sem isto,
                // o click do botao dispara logo apos e REABRE o dropdown.
                onMouseDown={(e) => {
                  e.preventDefault()
                  escolher(o.value)
                }}
                style={{
                  padding: '7px 9px',
                  borderRadius: 7,
                  font: '500 12.5px/1.2 var(--f-ui)',
                  color: ativo ? 'var(--ac-text)' : 'var(--tx-soft)',
                  background: emFoco ? 'var(--ac-a12)' : 'transparent',
                  cursor: 'pointer',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {o.label}
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
