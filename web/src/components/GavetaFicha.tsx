import { useEffect, type ReactNode } from 'react'

/**
 * A gaveta que traz a ficha por cima do mapa, no modo de ponto.
 *
 * NAO E' MODAL de proposito. O mapa continua vivo e clicavel ao lado: a leitura da ficha
 * e' sobre o que esta' desenhado ali, e escurecer o mapa para ler sobre ele seria
 * trabalhar contra a propria tela. Por isso nao ha' backdrop e o foco nao fica preso.
 *
 * FICA MONTADA QUANDO FECHADA. So' o `transform` a tira da tela. Desmontar zeraria o que
 * o operador digitou em metragem e aluguel no bloco de viabilidade — fechar a gaveta para
 * olhar o mapa e perder a conta ao reabrir seria punir quem usou as duas coisas juntas.
 * `visibility: hidden` no fim da transicao e' o que a tira da ordem de tabulacao; sem
 * isso, o Tab pescaria botoes invisiveis fora da tela.
 */
export default function GavetaFicha({
  aberta,
  titulo,
  subtitulo,
  onFechar,
  children,
}: {
  aberta: boolean
  titulo: string
  subtitulo?: string
  onFechar: () => void
  children: ReactNode
}) {
  // Esc fecha. E' o gesto que todo mundo tenta primeiro numa gaveta.
  useEffect(() => {
    if (!aberta) return
    const aoTeclar = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onFechar()
    }
    window.addEventListener('keydown', aoTeclar)
    return () => window.removeEventListener('keydown', aoTeclar)
  }, [aberta, onFechar])

  return (
    <aside
      role="dialog"
      aria-label={titulo}
      aria-hidden={!aberta}
      style={{
        position: 'absolute',
        top: 0,
        right: 0,
        bottom: 0,
        /* 520px cabe a grade de KPI em 2 colunas e a comparacao A x B em 3, sem
           espremer os numeros; 92vw impede a gaveta de cobrir a tela toda no celular. */
        width: 'min(520px, 92vw)',
        display: 'flex',
        flexDirection: 'column',
        background: 'var(--surf-panel)',
        borderLeft: '1px solid var(--line)',
        backdropFilter: 'blur(18px)',
        boxShadow: aberta ? '-24px 0 60px rgba(0,0,0,.42)' : 'none',
        transform: aberta ? 'translateX(0)' : 'translateX(100%)',
        visibility: aberta ? 'visible' : 'hidden',
        transition:
          'transform .26s cubic-bezier(.4,0,.2,1), visibility .26s, box-shadow .26s ease',
        zIndex: 20,
      }}
    >
      <header
        style={{
          flexShrink: 0,
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          padding: '14px 16px',
          borderBottom: '1px solid var(--line-soft)',
        }}
      >
        <div style={{ display: 'grid', gap: 2, minWidth: 0, flex: 1 }}>
          <span
            style={{
              font: '600 14px/1.2 var(--f-ui)',
              color: 'var(--tx-max)',
              letterSpacing: '-.01em',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {titulo}
          </span>
          {subtitulo && (
            <span
              style={{
                font: '400 11.5px/1.3 var(--f-ui)',
                color: 'var(--tx-sub)',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {subtitulo}
            </span>
          )}
        </div>

        <button
          type="button"
          onClick={onFechar}
          title="Fechar a ficha (Esc)"
          aria-label="Fechar a ficha"
          style={{
            flexShrink: 0,
            width: 30,
            height: 30,
            display: 'grid',
            placeItems: 'center',
            borderRadius: 8,
            border: '1px solid var(--line-soft)',
            background: 'var(--surf-raised)',
            color: 'var(--tx-soft)',
            font: '600 15px/1 var(--f-ui)',
          }}
        >
          ×
        </button>
      </header>

      <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>{children}</div>
    </aside>
  )
}
