import { num } from '../lib/format'
import type { Passo } from '../lib/types'

/* ---------------------------------------------------------------------------
   Os 4 passos da recomendacao, na barra inferior do mapa.

   O ultimo passo troca o CTA de "próxima camada" por "Gerar Relatório
   Municipal" — a sintese das 4 camadas vira o PDF (pedido do Felipe).
   --------------------------------------------------------------------------- */

export interface StepperBarProps {
  passos: Passo[]
  atual: number
  onIr: (n: number) => void
  onGerarRelatorio: () => void
  gerando: boolean
}

export default function StepperBar({
  passos,
  atual,
  onIr,
  onGerarRelatorio,
  gerando,
}: StepperBarProps) {
  const ultimo = atual >= 4

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 14,
        padding: '0 16px',
        height: 60,
        background: 'var(--surf-bar)',
        border: '1px solid var(--line-soft)',
        borderRadius: 'var(--r-xl)',
        backdropFilter: 'blur(16px)',
      }}
    >
      <ol
        style={{
          display: 'flex',
          alignItems: 'center',
          flex: 1,
          margin: 0,
          padding: 0,
          listStyle: 'none',
          minWidth: 0,
        }}
      >
        {passos.map((p, i) => {
          const feito = p.n < atual
          const ativo = p.n === atual
          return (
            <li
              key={p.n}
              style={{ display: 'contents' }}
            >
              <button
                type="button"
                onClick={() => onIr(p.n)}
                aria-current={ativo ? 'step' : undefined}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  flexShrink: 0,
                  padding: '4px 2px',
                  borderRadius: 8,
                }}
              >
                <span
                  aria-hidden
                  className="num"
                  style={{
                    width: 23,
                    height: 23,
                    borderRadius: '50%',
                    display: 'grid',
                    placeItems: 'center',
                    font: '700 11px/1 var(--f-num)',
                    flexShrink: 0,
                    background: ativo
                      ? 'var(--ac)'
                      : feito
                        ? 'rgba(53,201,214,.85)'
                        : 'var(--surf-pending)',
                    color: ativo || feito ? 'var(--ac-on)' : 'var(--tx-muted)',
                    border: ativo || feito ? 'none' : '1px solid var(--line-strong)',
                    boxShadow: ativo ? '0 0 0 4px var(--ac-a22)' : 'none',
                    transition: 'background .2s ease, box-shadow .2s ease',
                  }}
                >
                  {feito ? '✓' : p.n}
                </span>
                <span style={{ textAlign: 'left', minWidth: 0 }}>
                  <span
                    style={{
                      display: 'block',
                      font: '600 11.5px/1.1 var(--f-ui)',
                      color: ativo || feito ? 'var(--tx-strong)' : 'var(--tx-muted)',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {p.titulo}
                  </span>
                  <span
                    className="num"
                    style={{
                      display: 'block',
                      font: '500 9.5px/1.2 var(--f-num)',
                      marginTop: 2,
                      color: ativo
                        ? 'var(--ac)'
                        : feito
                          ? 'var(--tx-label)'
                          : 'var(--tx-off)',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {num(p.funil_big)} {p.funil_unit}
                  </span>
                </span>
              </button>

              {i < passos.length - 1 && (
                <span
                  aria-hidden
                  style={{
                    flex: 1,
                    height: 2,
                    margin: '0 10px',
                    borderRadius: 1,
                    background: feito ? 'var(--ac-a60)' : 'var(--line-mid)',
                    transition: 'background .2s ease',
                    minWidth: 12,
                  }}
                />
              )}
            </li>
          )
        })}
      </ol>

      <button
        type="button"
        onClick={ultimo ? onGerarRelatorio : () => onIr(atual + 1)}
        disabled={gerando}
        style={{
          flexShrink: 0,
          background: 'var(--ac)',
          color: 'var(--ac-on)',
          font: '700 12px/1 var(--f-ui)',
          padding: '10px 15px',
          borderRadius: 10,
          boxShadow: 'var(--ac-glow)',
          opacity: gerando ? 0.6 : 1,
          display: 'flex',
          alignItems: 'center',
          gap: 7,
        }}
      >
        {gerando ? (
          <>
            <Spinner />
            Montando o relatório…
          </>
        ) : ultimo ? (
          'Gerar Relatório Municipal ↓'
        ) : (
          'Próxima camada →'
        )}
      </button>
    </div>
  )
}

function Spinner() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" aria-hidden>
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
