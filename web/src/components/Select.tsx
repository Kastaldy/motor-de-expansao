import { useEffect, useId, useMemo, useRef, useState } from 'react'

/* ---------------------------------------------------------------------------
   Dropdown customizado. O <select> nativo abre o popup de opcoes em BRANCO no
   Chrome/Windows por mais que se aplique color-scheme/background — ilegivel no
   tema escuro. Este componente controla o popup, então segue o tema sempre.
   Acessivel: teclado (setas, Enter, Esc), aria-listbox, fecha ao clicar fora.

   Com muitas opcoes (municipios) o popup ganha um campo de BUSCA no topo, que
   filtra por substring insensivel a acento. As opcoes ja chegam ordenadas.
   --------------------------------------------------------------------------- */

export interface SelectProps {
  value: string
  options: { value: string; label: string }[]
  onChange: (v: string) => void
  label: string
  maxWidth?: number
  /** Forca (ou desliga) o campo de busca. Por padrao liga com mais de 8 opcoes. */
  buscavel?: boolean
  /** Texto do botao quando nada esta selecionado (value sem opcao correspondente). */
  placeholder?: string
}

const norm = (s: string) =>
  s
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
    .toLowerCase()
    .trim()

export default function Select({
  value,
  options,
  onChange,
  label,
  maxWidth = 150,
  buscavel,
  placeholder,
}: SelectProps) {
  const [aberto, setAberto] = useState(false)
  const [foco, setFoco] = useState(-1)
  const [busca, setBusca] = useState('')
  const raiz = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const listaId = useId()

  const temBusca = buscavel ?? options.length > 8
  const selecionado = options.find((o) => o.value === value)

  const filtradas = useMemo(() => {
    if (!temBusca || !busca.trim()) return options
    const q = norm(busca)
    return options.filter((o) => norm(o.label).includes(q))
  }, [options, busca, temBusca])

  useEffect(() => {
    if (!aberto) return
    function fora(e: MouseEvent) {
      if (raiz.current && !raiz.current.contains(e.target as Node)) setAberto(false)
    }
    document.addEventListener('mousedown', fora)
    return () => document.removeEventListener('mousedown', fora)
  }, [aberto])

  // Ao abrir: limpa a busca, posiciona o foco no valor atual e foca o input.
  useEffect(() => {
    if (!aberto) return
    setBusca('')
    setFoco(options.findIndex((o) => o.value === value))
    if (temBusca) {
      const t = setTimeout(() => inputRef.current?.focus(), 0)
      return () => clearTimeout(t)
    }
  }, [aberto, options, value, temBusca])

  // Digitar na busca recomeca o foco no topo da lista filtrada.
  useEffect(() => {
    if (aberto && busca) setFoco(0)
  }, [busca, aberto])

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
    if (e.key === 'Enter') {
      e.preventDefault()
      if (aberto && foco >= 0 && filtradas[foco]) escolher(filtradas[foco].value)
      else if (!aberto) setAberto(true)
      return
    }
    if (e.key === ' ' && !aberto) {
      // Espaco so abre quando fechado; aberto com busca, o espaco e texto.
      e.preventDefault()
      setAberto(true)
      return
    }
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault()
      if (!aberto) {
        setAberto(true)
        return
      }
      if (!filtradas.length) return
      const passo = e.key === 'ArrowDown' ? 1 : -1
      setFoco((f) => (f + passo + filtradas.length) % filtradas.length)
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
          {selecionado?.label ?? placeholder ?? value}
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
        <div
          style={{
            position: 'absolute',
            top: 'calc(100% + 4px)',
            left: 0,
            zIndex: 40,
            minWidth: '100%',
            width: 'max-content',
            maxWidth: 300,
            background: 'var(--surf-panel)',
            border: '1px solid var(--line-mid)',
            borderRadius: 'var(--r-md)',
            backdropFilter: 'blur(16px)',
            boxShadow: '0 14px 34px -10px rgba(0,0,0,.75)',
            overflow: 'hidden',
          }}
        >
          {temBusca && (
            <div style={{ padding: 6, borderBottom: '1px solid var(--line-soft)' }}>
              <input
                ref={inputRef}
                value={busca}
                onChange={(e) => setBusca(e.target.value)}
                onKeyDown={teclado}
                placeholder="Buscar…"
                aria-label={`Buscar ${label}`}
                style={{
                  width: '100%',
                  boxSizing: 'border-box',
                  background: 'var(--surf-input)',
                  border: '1px solid var(--line)',
                  borderRadius: 7,
                  padding: '7px 9px',
                  font: '500 12.5px/1 var(--f-ui)',
                  color: 'var(--tx-strong)',
                }}
              />
            </div>
          )}

          <ul
            role="listbox"
            id={listaId}
            aria-label={label}
            style={{
              margin: 0,
              padding: 4,
              listStyle: 'none',
              maxHeight: 300,
              overflowY: 'auto',
            }}
          >
            {filtradas.length === 0 ? (
              <li
                style={{
                  padding: '9px',
                  font: '400 12px/1.3 var(--f-ui)',
                  color: 'var(--tx-muted)',
                }}
              >
                Nada encontrado.
              </li>
            ) : (
              filtradas.map((o, i) => {
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
              })
            )}
          </ul>
        </div>
      )}
    </div>
  )
}
