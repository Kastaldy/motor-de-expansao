import { SCORE_BANDS_HEX } from '../lib/colors'

/* Legenda das faixas de score — a escala vermelho->verde do dashboard.
   Compacta, pensada para flutuar num canto sem competir com o resto. */

export default function ScoreLegend({ passoN }: { passoN: number }) {
  const nome =
    passoN === 1
      ? 'Score censitário'
      : passoN === 4
        ? 'Score M1'
        : 'Score residual'
  return (
    <div
      style={{
        background: 'var(--surf-bar)',
        border: '1px solid var(--line-soft)',
        borderRadius: 'var(--r-sm)',
        backdropFilter: 'blur(14px)',
        padding: '7px 9px',
        pointerEvents: 'none',
        width: 'fit-content',
      }}
    >
      <div
        style={{
          font: '500 8.5px/1 var(--f-ui)',
          color: 'var(--tx-label)',
          marginBottom: 5,
          textTransform: 'uppercase',
          letterSpacing: '.06em',
        }}
      >
        {nome}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span className="num" style={{ font: '400 8.5px/1 var(--f-num)', color: 'var(--tx-sub)' }}>
          0
        </span>
        <div style={{ display: 'flex', borderRadius: 2, overflow: 'hidden' }}>
          {SCORE_BANDS_HEX.map((c) => (
            <span key={c} style={{ width: 11, height: 8, background: c }} />
          ))}
        </div>
        <span className="num" style={{ font: '400 8.5px/1 var(--f-num)', color: 'var(--tx-sub)' }}>
          100
        </span>
        <span
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 4,
            marginLeft: 4,
            paddingLeft: 7,
            borderLeft: '1px solid var(--line-mid)',
          }}
        >
          <span style={{ width: 8, height: 8, borderRadius: 2, background: 'rgb(150,150,170)' }} />
          <span style={{ font: '400 8.5px/1 var(--f-ui)', color: 'var(--tx-sub)' }}>&lt; 5k hab</span>
        </span>
      </div>
    </div>
  )
}
