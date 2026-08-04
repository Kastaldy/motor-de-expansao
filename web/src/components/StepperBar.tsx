import { num } from '../lib/format'
import type { Passo } from '../lib/types'
import { Spinner } from './primitives'

/* ---------------------------------------------------------------------------
   Os 4 passos da recomendacao, na barra inferior do mapa.

   O ultimo passo troca o CTA de "próxima camada" por "Gerar Relatório
   Municipal" — a sintese das 4 camadas vira o PDF (pedido do Felipe).

   Voltar SEMPRE foi possivel (clicar num passo ja percorrido), mas nada dizia
   isso: o CTA era de mao unica e a palavra "voltar" nao aparecia. Dai o botao
   secundario ao lado do CTA e o aria-label/title explicito em cada passo.
   --------------------------------------------------------------------------- */

export interface StepperBarProps {
  passos: Passo[]
  atual: number
  onIr: (n: number) => void
  onGerarRelatorio: () => void
  gerando: boolean
  /** Na visão de UF inteira o passo 4 recomenda municípios — sem relatório. */
  nivelUf?: boolean
}

export default function StepperBar({
  passos,
  atual,
  onIr,
  onGerarRelatorio,
  gerando,
  nivelUf = false,
}: StepperBarProps) {
  const ultimo = atual >= 4
  // No nível da UF, o último passo guia para escolher um município (não gera PDF).
  const ctaUf = ultimo && nivelUf
  const podeVoltar = atual > 1

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
          // O passo é clicável nos dois sentidos; o rótulo precisa dizer isso.
          const rotulo = `${
            ativo ? 'Camada atual,' : feito ? 'Voltar para a camada' : 'Avançar para a camada'
          } ${p.n} de ${passos.length}: ${p.titulo} (${num(p.funil_big)} ${p.funil_unit})`
          return (
            <li
              key={p.n}
              style={{ display: 'contents' }}
            >
              <button
                type="button"
                onClick={() => onIr(p.n)}
                aria-current={ativo ? 'step' : undefined}
                aria-label={rotulo}
                title={rotulo}
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

      {podeVoltar && (
        <button
          type="button"
          onClick={() => onIr(atual - 1)}
          disabled={gerando}
          aria-label={`Voltar para a camada ${atual - 1} de ${passos.length}`}
          title="Voltar uma camada"
          style={{
            flexShrink: 0,
            background: 'var(--surf-pending)',
            color: 'var(--tx-soft)',
            font: '600 12px/1 var(--f-ui)',
            padding: '10px 13px',
            borderRadius: 10,
            border: '1px solid var(--line-strong)',
            opacity: gerando ? 0.6 : 1,
          }}
        >
          ← Camada anterior
        </button>
      )}

      <button
        type="button"
        onClick={ctaUf ? undefined : ultimo ? onGerarRelatorio : () => onIr(atual + 1)}
        disabled={gerando || ctaUf}
        style={{
          flexShrink: 0,
          background: ctaUf ? 'var(--surf-pending)' : 'var(--ac)',
          color: ctaUf ? 'var(--tx-muted)' : 'var(--ac-on)',
          font: '700 12px/1 var(--f-ui)',
          padding: '10px 15px',
          borderRadius: 10,
          boxShadow: ctaUf ? 'none' : 'var(--ac-glow)',
          border: ctaUf ? '1px solid var(--line-strong)' : 'none',
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
        ) : ctaUf ? (
          'Escolha um município ↑'
        ) : ultimo ? (
          'Gerar Relatório Municipal ↓'
        ) : (
          'Próxima camada →'
        )}
      </button>
    </div>
  )
}
