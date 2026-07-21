import { alunos, brl, num, pct } from '../lib/format'
import type { FcfPonto, MelhoriaPayback } from '../lib/types'
import { Glass } from './primitives'

/* ---------------------------------------------------------------------------
   Graficos da Viabilidade. Formas herdadas do template de referencia.
   Todos SVG puro: sem lib de grafico, sem rede, e o texto continua selecionavel.
   --------------------------------------------------------------------------- */

/** Régua demanda × ponto de equilíbrio — a leitura mais importante da tela. */
export function ReguaBreakEven({
  demanda,
  breakeven,
}: {
  demanda: number
  breakeven: number | null
}) {
  const be = breakeven ?? 0
  const escala = Math.max(demanda, be) * 1.22 || 1400
  const bePct = Math.min(96, Math.max(4, (be / escala) * 100))
  const demPct = Math.min(98, Math.max(2, (demanda / escala) * 100))
  const acima = be > 0 && demanda >= be

  return (
    <Glass style={{ padding: '17px 19px' }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'baseline',
          gap: 12,
          marginBottom: 30,
        }}
      >
        <span style={{ font: '600 13px/1 var(--f-ui)', color: 'var(--tx-strong)' }}>
          Demanda assumida vs. ponto de equilíbrio
        </span>
        <span
          style={{
            font: '600 12px/1 var(--f-ui)',
            color: acima ? 'var(--pos-text)' : 'var(--neg)',
          }}
        >
          {be <= 0 ? 'sem equilíbrio calculado' : acima ? 'Acima do equilíbrio' : 'Abaixo do equilíbrio'}
        </span>
      </div>

      <div style={{ position: 'relative', margin: '0 4px' }}>
        <div
          style={{
            height: 16,
            borderRadius: 9,
            background: `linear-gradient(90deg, #c8324a 0%, #d9a441 ${bePct}%, #2ec86e ${Math.min(100, bePct + 9)}%, #39a063 100%)`,
          }}
        />

        {/* Marcador do break-even */}
        {be > 0 && (
          <>
            <div
              style={{
                position: 'absolute',
                left: `${bePct}%`,
                top: -4,
                bottom: -4,
                width: 2,
                background: 'var(--tx-max)',
                borderRadius: 1,
              }}
            />
            <div
              className="num"
              style={{
                position: 'absolute',
                left: `${bePct}%`,
                top: 24,
                transform: 'translateX(-50%)',
                font: '500 10px/1 var(--f-num)',
                color: 'var(--tx-sub)',
                whiteSpace: 'nowrap',
              }}
            >
              equilíbrio {alunos(be)}
            </div>
          </>
        )}

        {/* Knob da demanda assumida */}
        <div
          style={{
            position: 'absolute',
            left: `${demPct}%`,
            top: -2,
            transform: 'translateX(-50%)',
            width: 20,
            height: 20,
            borderRadius: '50%',
            background: acima ? 'var(--pos-text)' : 'var(--neg)',
            border: '3px solid var(--bg-knob)',
            boxShadow: '0 3px 10px rgba(0,0,0,.5)',
          }}
        />
        <div
          className="num"
          style={{
            position: 'absolute',
            left: `${demPct}%`,
            top: -30,
            transform: 'translateX(-50%)',
            font: '600 10.5px/1 var(--f-num)',
            color: 'var(--tx-strong)',
            background: 'rgba(255,255,255,.08)',
            padding: '4px 8px',
            borderRadius: 6,
            whiteSpace: 'nowrap',
          }}
        >
          {alunos(demanda)} · premissa
        </div>
      </div>

      <div
        className="num"
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          marginTop: 44,
          font: '400 10px/1 var(--f-num)',
          color: 'var(--tx-sub)',
        }}
      >
        <span>0</span>
        <span>{alunos(escala)} alunos</span>
      </div>
    </Glass>
  )
}

/** DRE em cascata. Barras descem do faturamento até o lucro líquido. */
export function CascataDre({
  faturamento,
  deducoes,
  impostos,
  custos,
  ebitda,
  lucroLiquido,
}: {
  faturamento: number | null
  deducoes: number | null
  impostos: number | null
  custos: number | null
  ebitda: number | null
  lucroLiquido: number | null
}) {
  // IR/CSLL sobre o lucro = degrau entre EBITDA e lucro líquido. O motor define
  // lucro_liquido = EBITDA − IR − CSLL (simulador.py), sem D&A/despesa financeira.
  const irCsll =
    ebitda !== null && lucroLiquido !== null
      ? Math.round((ebitda - lucroLiquido) * 100) / 100
      : null
  const barras = [
    { rotulo: 'Fat. bruto', valor: faturamento, tipo: 'pos' as const },
    { rotulo: 'Deduções', valor: deducoes, tipo: 'neg' as const },
    { rotulo: 'Impostos', valor: impostos, tipo: 'neg' as const },
    { rotulo: 'Custos op.', valor: custos, tipo: 'neg' as const },
    { rotulo: 'EBITDA', valor: ebitda, tipo: 'res' as const },
    { rotulo: 'IR/CSLL', valor: irCsll, tipo: 'neg' as const },
    { rotulo: 'Lucro líq.', valor: lucroLiquido, tipo: 'res' as const },
  ]

  const teto = Math.max(1, faturamento ?? 1)
  const piso = Math.min(0, ebitda ?? 0, lucroLiquido ?? 0)
  const amplitude = teto - piso || 1
  const H = 130

  return (
    <Glass style={{ padding: '17px 19px', minWidth: 0 }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'baseline',
          marginBottom: 16,
        }}
      >
        <span style={{ font: '600 13px/1 var(--f-ui)', color: 'var(--tx-strong)' }}>
          Composição do resultado
        </span>
        <span
          className="num"
          style={{ font: '400 10px/1 var(--f-num)', color: 'var(--tx-muted)' }}
        >
          DRE steady-state
        </span>
      </div>

      <div
        style={{
          display: 'flex',
          alignItems: 'flex-end',
          gap: 10,
          height: H,
          marginBottom: 8,
        }}
      >
        {barras.map((b) => {
          const v = b.valor ?? 0
          const altura = Math.max(3, (Math.abs(v) / amplitude) * H)
          const cor =
            b.tipo === 'neg'
              ? 'var(--neg-bar)'
              : b.tipo === 'res'
                ? v >= 0
                  ? 'var(--pos)'
                  : 'var(--neg)'
                : 'var(--pos)'
          return (
            <div
              key={b.rotulo}
              style={{
                flex: 1,
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'flex-end',
                height: '100%',
              }}
            >
              <div
                style={{
                  height: altura,
                  background: cor,
                  borderRadius: 3,
                  margin: '0 18%',
                  transition: 'height .3s ease',
                }}
                title={`${b.rotulo}: ${brl(b.valor)}`}
              />
            </div>
          )
        })}
      </div>

      <div style={{ display: 'flex', gap: 10 }}>
        {barras.map((b) => (
          <div key={b.rotulo} style={{ flex: 1, textAlign: 'center', minWidth: 0 }}>
            <div
              className="num"
              style={{
                font: '600 10px/1.2 var(--f-num)',
                color:
                  b.tipo === 'res'
                    ? (b.valor ?? 0) >= 0
                      ? 'var(--pos-text)'
                      : 'var(--neg)'
                    : b.tipo === 'neg'
                      ? 'var(--tx-narrative)'
                      : 'var(--tx-soft)',
              }}
            >
              {b.valor === null ? 'n/d' : brl(b.valor, true)}
            </div>
            <div
              style={{
                font: '400 9px/1.2 var(--f-ui)',
                color: 'var(--tx-muted)',
                marginTop: 4,
              }}
            >
              {b.rotulo}
            </div>
          </div>
        ))}
      </div>
    </Glass>
  )
}

/** Sparkline de maturação — a rampa de alunos, do ZERO ao platô assumido.
 *  `plateau` = alunos assumidos na maturidade (a demanda do operador); `meses` =
 *  duração da rampa, controlada na sidebar. Começa no mês 0 com 0 alunos. */
export function RampaAlunos({ plateau, meses }: { plateau: number; meses: number }) {
  const mat = Math.max(1, Math.round(meses))
  // Horizonte um pouco além da maturação para o platô aparecer plano à direita.
  const horizonte = Math.max(mat + 6, 18)

  const W = 300
  const H = 120
  // Eixo y de base ZERO até o platô (com folga no topo).
  const y = (v: number) => H - (v / Math.max(1, plateau)) * (H * 0.88) - 8
  const x = (m: number) => (m / horizonte) * W

  const pontos: { x: number; y: number }[] = []
  for (let m = 0; m <= horizonte; m += 1) {
    const v = m >= mat ? plateau : (plateau * m) / mat
    pontos.push({ x: x(m), y: y(v) })
  }
  const linha = pontos.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ')
  const area = `0,${H} ${linha} ${W},${H}`
  const xMat = x(mat)

  return (
    <Glass style={{ padding: '17px 19px', flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
      <Cabecalho
        titulo="Rampa de alunos"
        sub={`do zero ao platô no mês ${mat}`}
        valor={alunos(plateau)}
        cor="var(--ac-text)"
      />
      <div style={{ flex: 1, minHeight: 120, marginTop: 12 }}>
        <svg
          viewBox={`0 0 ${W} ${H}`}
          preserveAspectRatio="none"
          style={{ width: '100%', height: '100%', display: 'block' }}
          aria-hidden
        >
          <defs>
            <linearGradient id="rampaGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--ac)" stopOpacity="0.3" />
              <stop offset="100%" stopColor="var(--ac)" stopOpacity="0.02" />
            </linearGradient>
          </defs>
          <polygon points={area} fill="url(#rampaGrad)" />
          {/* marcador do mês de maturação */}
          <line
            x1={xMat}
            y1="0"
            x2={xMat}
            y2={H}
            stroke="var(--ac)"
            strokeWidth="1"
            strokeDasharray="3 3"
            opacity="0.5"
            vectorEffect="non-scaling-stroke"
          />
          <polyline
            points={linha}
            fill="none"
            stroke="var(--ac)"
            strokeWidth="2.5"
            strokeLinejoin="round"
            strokeLinecap="round"
            vectorEffect="non-scaling-stroke"
          />
        </svg>
      </div>
      <div
        className="num"
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          marginTop: 4,
          font: '400 9px/1 var(--f-num)',
          color: 'var(--tx-sub)',
        }}
      >
        <span>mês 0</span>
        <span>mês {horizonte}</span>
      </div>
    </Glass>
  )
}

/**
 * Fluxo de caixa acumulado ao longo de 60 meses — a série REAL do simulador.
 * Mostra a curva mergulhando com o CAPEX e o cruzamento do zero no payback.
 */
export function FluxoCaixa({
  serie,
  payback,
  carencia,
}: {
  serie: FcfPonto[]
  payback: number | null
  carencia: number
}) {
  const pts = serie
    .map((p) => ({ mes: p.mes, fcf: p.fcf }))
    .filter((p): p is { mes: number; fcf: number } => p.fcf !== null)

  if (pts.length < 2) {
    return (
      <Glass style={{ padding: '17px 19px' }}>
        <Cabecalho titulo="Fluxo de caixa acumulado" sub="60 meses" valor="n/d" cor="var(--tx-muted)" />
        <p style={{ font: '400 12px/1.5 var(--f-ui)', color: 'var(--tx-muted)', marginTop: 10 }}>
          Sem série de fluxo para este cenário.
        </p>
      </Glass>
    )
  }

  const W = 620
  const H = 150
  const padL = 8
  const padR = 8
  const maxMes = Math.max(...pts.map((p) => p.mes))
  const vals = pts.map((p) => p.fcf)
  const min = Math.min(...vals, 0)
  const max = Math.max(...vals, 0)
  const range = max - min || 1

  const x = (mes: number) => padL + (mes / maxMes) * (W - padL - padR)
  const y = (fcf: number) => H - ((fcf - min) / range) * H
  const zeroY = y(0)

  const linha = pts.map((p) => `${x(p.mes).toFixed(1)},${y(p.fcf).toFixed(1)}`).join(' ')
  const area = `${x(pts[0].mes).toFixed(1)},${zeroY.toFixed(1)} ${linha} ${x(
    pts[pts.length - 1].mes,
  ).toFixed(1)},${zeroY.toFixed(1)}`

  const fimFcf = pts[pts.length - 1].fcf
  const zeroFrac = Math.max(0, Math.min(1, zeroY / H))

  return (
    <Glass style={{ padding: '17px 19px', flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 10 }}>
        <span>
          <span style={{ display: 'block', font: '600 13px/1 var(--f-ui)', color: 'var(--tx-strong)' }}>
            Fluxo de caixa acumulado
          </span>
          <span style={{ display: 'block', font: '400 10px/1 var(--f-ui)', color: 'var(--tx-muted)', marginTop: 5 }}>
            60 meses · começa no CAPEX{carencia > 0 ? ` · carência de ${carencia}m de aluguel` : ''}
          </span>
        </span>
        <span style={{ textAlign: 'right' }}>
          <span
            className="num"
            style={{ display: 'block', font: '700 13px/1 var(--f-num)', color: fimFcf >= 0 ? 'var(--pos-text)' : 'var(--neg)' }}
          >
            {brl(fimFcf, true)}
          </span>
          <span style={{ display: 'block', font: '400 9.5px/1 var(--f-ui)', color: 'var(--tx-sub)', marginTop: 4 }}>
            no mês 60
          </span>
        </span>
      </div>

      <svg
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        style={{ width: '100%', height: 150, marginTop: 12, display: 'block' }}
        aria-hidden
      >
        <defs>
          <linearGradient id="fcfGrad" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="0" y2={H}>
            <stop offset={zeroFrac} stopColor="var(--pos)" stopOpacity="0.28" />
            <stop offset={zeroFrac} stopColor="var(--neg)" stopOpacity="0.24" />
          </linearGradient>
        </defs>

        {/* área entre a curva e a linha do zero: verde acima, vermelho abaixo */}
        <polygon points={area} fill="url(#fcfGrad)" />

        {/* linha do zero (equilíbrio de caixa) */}
        <line x1={padL} y1={zeroY} x2={W - padR} y2={zeroY} stroke="rgba(255,255,255,.28)" strokeWidth="1" strokeDasharray="4 4" />

        {/* marcador do payback (cruzamento do zero) */}
        {payback != null && payback <= maxMes && (
          <line x1={x(payback)} y1="0" x2={x(payback)} y2={H} stroke="var(--ac)" strokeWidth="1.5" strokeDasharray="3 3" />
        )}

        {/* a curva */}
        <polyline points={linha} fill="none" stroke="var(--tx-max)" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" />
      </svg>

      {/* eixo de meses + rótulo do payback */}
      <div style={{ position: 'relative', height: 16, marginTop: 2 }}>
        <span className="num" style={{ position: 'absolute', left: 0, font: '400 9.5px/1 var(--f-num)', color: 'var(--tx-sub)' }}>
          mês 0
        </span>
        <span className="num" style={{ position: 'absolute', right: 0, font: '400 9.5px/1 var(--f-num)', color: 'var(--tx-sub)' }}>
          mês {maxMes}
        </span>
        {payback != null && payback <= maxMes && (
          <span
            className="num"
            style={{
              position: 'absolute',
              left: `${(payback / maxMes) * 100}%`,
              transform: 'translateX(-50%)',
              font: '600 9.5px/1 var(--f-num)',
              color: 'var(--ac-text)',
              whiteSpace: 'nowrap',
            }}
          >
            payback {payback}m
          </span>
        )}
      </div>
    </Glass>
  )
}

/**
 * Resultado operacional MÊS A MÊS (não acumulado) — o caixa que a operação gera em
 * cada mês (EBITDA − IR/CSLL − PMT). Mostra quando a operação passa a se pagar sozinha
 * (o mês cruza o zero) e estabiliza no positivo. É DISTINTO do payback do investimento
 * (FluxoCaixa), que acumula o capital. Cada ponto é o resultado do mês, não o acumulado.
 */
export function FluxoCaixaOperacional({
  serie,
  mesPositivo,
}: {
  serie: FcfPonto[]
  mesPositivo: number | null
}) {
  const pts = serie
    .map((p) => ({ mes: p.mes, fcf: p.fcf }))
    .filter((p): p is { mes: number; fcf: number } => p.fcf !== null)

  if (pts.length < 2) {
    return (
      <Glass style={{ padding: '17px 19px' }}>
        <Cabecalho titulo="Resultado operacional mês a mês" sub="por mês" valor="n/d" cor="var(--tx-muted)" />
        <p style={{ font: '400 12px/1.5 var(--f-ui)', color: 'var(--tx-muted)', marginTop: 10 }}>
          Sem série de fluxo para este cenário.
        </p>
      </Glass>
    )
  }

  const W = 620
  const H = 150
  const padL = 8
  const padR = 8
  const mesMin = Math.min(...pts.map((p) => p.mes))
  const mesMax = Math.max(...pts.map((p) => p.mes))
  const spanMes = mesMax - mesMin || 1
  const vals = pts.map((p) => p.fcf)
  const min = Math.min(...vals, 0)
  const max = Math.max(...vals, 0)
  const range = max - min || 1

  const x = (mes: number) => padL + ((mes - mesMin) / spanMes) * (W - padL - padR)
  const y = (fcf: number) => H - ((fcf - min) / range) * H
  const zeroY = y(0)

  const linha = pts.map((p) => `${x(p.mes).toFixed(1)},${y(p.fcf).toFixed(1)}`).join(' ')
  const area = `${x(pts[0].mes).toFixed(1)},${zeroY.toFixed(1)} ${linha} ${x(
    pts[pts.length - 1].mes,
  ).toFixed(1)},${zeroY.toFixed(1)}`

  const estavel = pts[pts.length - 1].fcf // resultado do último mês (platô steady)
  const zeroFrac = Math.max(0, Math.min(1, zeroY / H))

  // Mês em que a operação vira positiva (se dentro do eixo — garante narrowing p/ TS).
  const mp =
    mesPositivo != null && mesPositivo >= mesMin && mesPositivo <= mesMax ? mesPositivo : null

  return (
    <Glass style={{ padding: '17px 19px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 10 }}>
        <span>
          <span style={{ display: 'block', font: '600 13px/1 var(--f-ui)', color: 'var(--tx-strong)' }}>
            Resultado operacional mês a mês
          </span>
          <span style={{ display: 'block', font: '400 10px/1 var(--f-ui)', color: 'var(--tx-muted)', marginTop: 5 }}>
            {mp != null
              ? `Opera no positivo a partir do mês ${mp} · estabiliza no platô`
              : 'A operação não fecha o mês no positivo neste cenário'}
          </span>
        </span>
        <span style={{ textAlign: 'right' }}>
          <span className="num" style={{ display: 'block', font: '700 13px/1 var(--f-num)', color: estavel >= 0 ? 'var(--pos-text)' : 'var(--neg)' }}>
            {brl(estavel, true)}
          </span>
          <span style={{ display: 'block', font: '400 9.5px/1 var(--f-ui)', color: 'var(--tx-sub)', marginTop: 4 }}>
            por mês (estável)
          </span>
        </span>
      </div>

      <svg
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        style={{ width: '100%', height: 150, marginTop: 12, display: 'block' }}
        aria-hidden
      >
        <defs>
          <linearGradient id="fcoGrad" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="0" y2={H}>
            <stop offset={zeroFrac} stopColor="var(--pos)" stopOpacity="0.28" />
            <stop offset={zeroFrac} stopColor="var(--neg)" stopOpacity="0.24" />
          </linearGradient>
        </defs>

        <polygon points={area} fill="url(#fcoGrad)" />

        {/* linha do zero: acima = mês no azul, abaixo = mês no vermelho */}
        <line x1={padL} y1={zeroY} x2={W - padR} y2={zeroY} stroke="rgba(255,255,255,.28)" strokeWidth="1" strokeDasharray="4 4" />

        {/* marcador do break-even operacional (mês em que passa a se pagar) */}
        {mp != null && (
          <line x1={x(mp)} y1="0" x2={x(mp)} y2={H} stroke="var(--ac)" strokeWidth="1.5" strokeDasharray="3 3" />
        )}

        {/* a curva do resultado mensal */}
        <polyline points={linha} fill="none" stroke="var(--tx-max)" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" />

        {/* ponto do break-even operacional (cruzamento do zero) */}
        {mp != null && <circle cx={x(mp)} cy={zeroY} r="3.2" fill="var(--ac)" />}
      </svg>

      {/* eixo de meses + rótulo da inauguração */}
      <div style={{ position: 'relative', height: 16, marginTop: 2 }}>
        <span className="num" style={{ position: 'absolute', left: 0, font: '400 9.5px/1 var(--f-num)', color: 'var(--tx-sub)' }}>
          mês {mesMin}
        </span>
        <span className="num" style={{ position: 'absolute', right: 0, font: '400 9.5px/1 var(--f-num)', color: 'var(--tx-sub)' }}>
          mês {mesMax}
        </span>
        {mp != null && (
          <span
            className="num"
            style={{
              position: 'absolute',
              left: `${((mp - mesMin) / spanMes) * 100}%`,
              transform: 'translateX(-50%)',
              font: '600 9.5px/1 var(--f-num)',
              color: 'var(--ac-text)',
              whiteSpace: 'nowrap',
            }}
          >
            se paga · mês {mp}
          </span>
        )}
      </div>
    </Glass>
  )
}

function Cabecalho({
  titulo,
  sub,
  valor,
  cor,
}: {
  titulo: string
  sub: string
  valor: string
  cor: string
}) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 10 }}>
      <span>
        <span
          style={{
            display: 'block',
            font: '600 13px/1 var(--f-ui)',
            color: 'var(--tx-strong)',
          }}
        >
          {titulo}
        </span>
        <span
          style={{
            display: 'block',
            font: '400 10px/1 var(--f-ui)',
            color: 'var(--tx-muted)',
            marginTop: 5,
          }}
        >
          {sub}
        </span>
      </span>
      <span className="num" style={{ font: '700 13px/1 var(--f-num)', color: cor }}>
        {valor}
      </span>
    </div>
  )
}

/** Monta a frase de melhoria do payback (quanto cortar de CAPEX ou aluguel). */
function textoMelhoria(m: MelhoriaPayback): string {
  const partes: string[] = []
  if (m.reduzir_capex != null) partes.push(`reduza o CAPEX em ~${brl(m.reduzir_capex, true)}`)
  if (m.reduzir_aluguel != null) {
    partes.push(`reduza o aluguel em ~${brl(m.reduzir_aluguel, true)}/mês`)
  }
  if (!partes.length) {
    return 'cortes só de CAPEX ou de aluguel não bastam — reveja a demanda assumida ou a metragem'
  }
  return partes.join(' ou ')
}

/** Banner de veredito — a frase que o operador leva para o comitê. */
export function Veredito({
  aprovado,
  margem,
  demanda,
  breakeven,
  payback,
  melhoria,
}: {
  aprovado: boolean
  margem: number | null
  demanda: number
  breakeven: number | null
  payback?: number | null
  melhoria?: MelhoriaPayback | null
}) {
  const cor = aprovado ? 'var(--pos)' : 'var(--warn)'
  return (
    <div
      style={{
        display: 'flex',
        gap: 14,
        alignItems: 'stretch',
        padding: '15px 18px',
        background: 'var(--surf-verdict)',
        border: '1px solid var(--line)',
        borderRadius: 'var(--r-lg)',
        backdropFilter: 'blur(14px)',
      }}
    >
      <span style={{ width: 4, borderRadius: 3, background: cor, flexShrink: 0 }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="story" style={{ font: '400 19px/1.2 var(--f-story)', color: 'var(--tx-max)' }}>
          {aprovado ? 'Viável no cenário assumido' : 'Abaixo do ponto de equilíbrio'}
        </div>
        <div
          style={{
            font: '400 12.5px/1.45 var(--f-ui)',
            color: 'var(--tx-narrative)',
            marginTop: 5,
          }}
        >
          Com {alunos(demanda)} alunos assumidos
          {breakeven ? ` contra ${alunos(breakeven)} de equilíbrio` : ''}, a margem
          EBITDA fica em {pct(margem)}.{' '}
          {aprovado
            ? 'O imóvel fecha a conta nas premissas atuais.'
            : 'Reveja aluguel, metragem ou a demanda assumida antes de levar adiante.'}
          {melhoria && (
            <>
              {' '}
              <strong style={{ color: 'var(--warn-text)' }}>
                O payback{payback != null ? ` (~${num(payback)} meses)` : ''} passa de 40 meses.
              </strong>{' '}
              Para trazê-lo a ~{melhoria.alvo_meses} meses, {textoMelhoria(melhoria)}.
            </>
          )}
        </div>
      </div>
      <span
        style={{
          alignSelf: 'flex-start',
          font: '600 11px/1 var(--f-ui)',
          padding: '7px 11px',
          borderRadius: 8,
          whiteSpace: 'nowrap',
          background: aprovado ? 'rgba(46,200,110,.16)' : 'rgba(217,164,65,.16)',
          border: `1px solid ${aprovado ? 'rgba(46,200,110,.35)' : 'rgba(217,164,65,.4)'}`,
          color: aprovado ? 'var(--pos-pill)' : 'var(--warn-text)',
        }}
      >
        {aprovado ? 'Aprovado para comitê' : 'Requer revisão de premissas'}
      </span>
    </div>
  )
}

export { num }
