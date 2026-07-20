import { alunos, num } from '../lib/format'
import type { Hex, Passo } from '../lib/types'
import { Chip, Eyebrow } from './primitives'

/* ---------------------------------------------------------------------------
   Painel narrativo — o elemento-assinatura do piloto.

   Conta a historia do funil em vez de despejar metricas: cada camada declara de
   onde veio e o que sobrou (999 hexagonos -> 314 quentes -> 38 com residual ->
   23 white spaces -> 4 aberturas). A narrativa usa serif; o numero, mono. Essa
   separacao tipografica e o que faz a tela ler como um briefing, nao um painel.
   --------------------------------------------------------------------------- */

export interface NarrativePanelProps {
  passo: Passo
  selecionado: string | null
  onSelecionarHex: (hexId: string) => void
  onAnalisar: (hexId: string) => void
  /** Visão de UF: clicar num item (município) filtra para ele (drill-down). */
  onDrillMunicipio?: (municipio: string) => void
  hexes: Hex[]
}

export default function NarrativePanel({
  passo,
  selecionado,
  onSelecionarHex,
  onAnalisar,
  onDrillMunicipio,
}: NarrativePanelProps) {
  return (
    <aside
      aria-label={`Camada ${passo.n} de 4: ${passo.titulo}`}
      style={{
        width: 394,
        flexShrink: 0,
        display: 'flex',
        flexDirection: 'column',
        background: 'var(--surf-panel)',
        border: '1px solid var(--line-soft)',
        borderRadius: 'var(--r-2xl)',
        backdropFilter: 'blur(18px)',
        overflow: 'hidden',
      }}
    >
      <header style={{ padding: '18px 20px 16px' }}>
        <Eyebrow dot>
          Camada {passo.n} de 4 · {passo.mode}
        </Eyebrow>

        <h2
          className="story"
          style={{
            font: '400 25px/1.15 var(--f-story)',
            color: 'var(--tx-max)',
            margin: '11px 0 0',
            letterSpacing: '.005em',
          }}
        >
          {passo.titulo}
        </h2>

        <p
          style={{
            font: '400 13px/1.6 var(--f-ui)',
            color: 'var(--tx-narrative)',
            margin: '9px 0 0',
          }}
        >
          {passo.narrativa}
        </p>

        <div
          style={{
            marginTop: 15,
            padding: '13px 15px',
            background: 'var(--ac-a10)',
            border: '1px solid var(--ac-a24)',
            borderRadius: 'var(--r-lg)',
            display: 'flex',
            alignItems: 'baseline',
            gap: 9,
            flexWrap: 'wrap',
          }}
        >
          <span
            className="num"
            style={{ font: '700 30px/1 var(--f-num)', color: 'var(--ac-text)' }}
          >
            {num(passo.funil_big)}
          </span>
          <span
            style={{ font: '600 12.5px/1 var(--f-ui)', color: 'var(--tx-soft)' }}
          >
            {passo.funil_unit}
          </span>
          <span
            style={{
              font: '400 10.5px/1.3 var(--f-ui)',
              color: 'var(--tx-muted)',
              width: '100%',
            }}
          >
            filtrados de {passo.funil_from}
          </span>
        </div>
      </header>

      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '4px 14px 12px',
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
        }}
      >
        {passo.itens.length === 0 ? (
          <p
            style={{
              font: '400 12.5px/1.6 var(--f-ui)',
              color: 'var(--tx-muted)',
              padding: '18px 6px',
              margin: 0,
            }}
          >
            Nenhuma região passou neste filtro. Volte uma camada para ver o que
            foi descartado, ou escolha outro município.
          </p>
        ) : (
          passo.itens.map((it) => {
            const ativo = it.hex_id === selecionado
            const acionar = () =>
              it.municipio ? onDrillMunicipio?.(it.municipio) : onSelecionarHex(it.hex_id)
            return (
              <div
                key={it.municipio ?? it.hex_id}
                role="button"
                tabIndex={0}
                onClick={acionar}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    acionar()
                  }
                }}
                style={{
                  padding: '12px 13px',
                  border: `1px solid ${ativo ? 'var(--ac-a30)' : 'var(--line-soft)'}`,
                  borderRadius: 'var(--r-lg)',
                  background: ativo ? 'var(--ac-a08)' : 'var(--surf-raised)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  cursor: 'pointer',
                  transition: 'background .15s ease, border-color .15s ease',
                }}
              >
                <span
                  className="num"
                  aria-hidden
                  style={{
                    font: '700 14px/1 var(--f-num)',
                    color: ativo ? 'var(--ac-text)' : 'var(--tx-rank)',
                    width: 24,
                    textAlign: 'center',
                    flexShrink: 0,
                  }}
                >
                  {passo.n === 4 ? `${it.rank}º` : String(it.rank).padStart(2, '0')}
                </span>

                <span style={{ flex: 1, minWidth: 0 }}>
                  <span
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 7,
                      flexWrap: 'wrap',
                    }}
                  >
                    <span
                      style={{
                        font: '600 14px/1.2 var(--f-ui)',
                        color: 'var(--tx-strong)',
                      }}
                    >
                      {it.titulo}
                    </span>
                    {it.tag && <Chip tom={it.tom}>{it.tag}</Chip>}
                  </span>
                  {it.sub && (
                    <span
                      style={{
                        display: 'block',
                        font: '400 11.5px/1.3 var(--f-ui)',
                        color: 'var(--tx-label)',
                        marginTop: 3,
                      }}
                    >
                      {it.sub}
                    </span>
                  )}
                </span>

                <span style={{ textAlign: 'right', flexShrink: 0 }}>
                  <span
                    className="num"
                    style={{
                      display: 'block',
                      font: '700 15px/1 var(--f-num)',
                      color: 'var(--tx-max)',
                    }}
                  >
                    {it.label === 'residual' ? alunos(it.valor) : num(it.valor)}
                  </span>
                  <span
                    style={{
                      display: 'block',
                      font: '400 9.5px/1 var(--f-ui)',
                      color: 'var(--tx-sub)',
                      marginTop: 4,
                    }}
                  >
                    {it.label}
                  </span>
                </span>
              </div>
            )
          })
        )}

        {selecionado && (
          <button
            type="button"
            onClick={() => onAnalisar(selecionado)}
            style={{
              marginTop: 4,
              padding: '12px',
              borderRadius: 'var(--r-md)',
              border: '1px solid var(--ac-a30)',
              background: 'var(--ac-a12)',
              color: 'var(--ac-text)',
              font: '600 12.5px/1 var(--f-ui)',
            }}
          >
            Testar viabilidade deste ponto →
          </button>
        )}
      </div>

      <footer
        style={{
          padding: '13px 20px',
          borderTop: '1px solid var(--line-soft)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 10,
        }}
      >
        <span style={{ font: '400 11.5px/1 var(--f-ui)', color: 'var(--tx-sub)' }}>
          Camada visual · read-only M1
        </span>
      </footer>
    </aside>
  )
}
