import { alunos, num } from '../lib/format'
import {
  SCORE_MAX,
  composicaoMercado,
  faixaDaDistribuicao,
  fracaoDoScore,
} from '../lib/medidor'
import type { PontoDistribuicao } from '../lib/types'

/**
 * As peças VISUAIS da ficha: medidor de score, barra do mercado, régua de dispersão.
 *
 * Existem porque uma grade de KPIs responde "quanto é" e não responde "isso é muito?".
 * Cada peça aqui só aparece quando o dado sustenta o desenho — a decisão de aparecer ou
 * não mora em `lib/medidor.ts`, testada. Nenhuma delas colore por limiar de qualidade:
 * o produto não publica corte de "residual bom", e um verde a partir de um número que
 * ninguém aprovou viraria recomendação de abertura.
 */

/** Medidor 0-100 para os scores do produto. Some quando não há score. */
export function MedidorScore({
  rotulo,
  valor,
  nota,
}: {
  rotulo: string
  valor: number | null | undefined
  nota?: string
}) {
  const fr = fracaoDoScore(valor)
  if (fr == null) return null
  return (
    <div style={{ display: 'grid', gap: 6 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 10 }}>
        <span style={{ font: '500 11px/1.2 var(--f-ui)', color: 'var(--tx-label)' }}>{rotulo}</span>
        <span className="num" style={{ font: '700 15px/1 var(--f-num)', color: 'var(--tx-max)' }}>
          {num(valor, 1)}
          <span style={{ font: '400 10px/1 var(--f-num)', color: 'var(--tx-sub)' }}>
            {' '}
            / {SCORE_MAX}
          </span>
        </span>
      </div>
      <div style={{ height: 7, borderRadius: 4, background: 'var(--surf-pending)', overflow: 'hidden' }}>
        <div
          style={{
            width: `${Math.round(fr * 100)}%`,
            height: '100%',
            borderRadius: 4,
            /* Cor ÚNICA em toda a escala. Um gradiente de vermelho a verde afirmaria que
               40 é ruim e 80 é bom — corte que o produto não publica para estes scores. */
            background: 'var(--ac)',
          }}
        />
      </div>
      {nota && <span style={{ font: '400 10.5px/1.35 var(--f-ui)', color: 'var(--tx-sub)' }}>{nota}</span>}
    </div>
  )
}

/**
 * O mercado repartido: quanto já é atendido e quanto sobra.
 *
 * A barra diz o que dois KPIs lado a lado não dizem sem conta de cabeça — se o residual
 * é a maior parte do mercado ou uma sobra marginal.
 */
export function BarraMercado({
  sam,
  residual,
}: {
  sam: number | null | undefined
  residual: number | null | undefined
}) {
  const c = composicaoMercado(sam, residual)
  if (!c) return null
  const pct = Math.round(c.fracaoDisponivel * 100)
  return (
    <div style={{ display: 'grid', gap: 7 }}>
      <div style={{ display: 'flex', height: 10, borderRadius: 5, overflow: 'hidden', background: 'var(--surf-pending)' }}>
        <div
          title={`Já atendido: ${alunos(c.atendido)}`}
          style={{ width: `${100 - pct}%`, background: 'var(--tx-rank)' }}
        />
        <div
          title={`Disponível: ${alunos(c.disponivel)}`}
          style={{ width: `${pct}%`, background: 'var(--ac)' }}
        />
      </div>
      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
        <Legenda cor="var(--tx-rank)" rotulo="Já atendido" valor={alunos(c.atendido)} />
        <Legenda cor="var(--ac)" rotulo="Sobra" valor={`${alunos(c.disponivel)} · ${pct}%`} forte />
      </div>
    </div>
  )
}

function Legenda({
  cor,
  rotulo,
  valor,
  forte,
}: {
  cor: string
  rotulo: string
  valor: string
  forte?: boolean
}) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
      <span aria-hidden style={{ width: 9, height: 9, borderRadius: 3, background: cor, flexShrink: 0 }} />
      <span style={{ font: '400 10.5px/1.2 var(--f-ui)', color: 'var(--tx-sub)' }}>{rotulo}</span>
      <span
        className="num"
        style={{
          font: `${forte ? 700 : 500} 11px/1.2 var(--f-num)`,
          color: forte ? 'var(--tx-max)' : 'var(--tx-soft)',
        }}
      >
        {valor}
      </span>
    </span>
  )
}

/**
 * A régua setor a setor, com a mediana marcada.
 *
 * A ficha mostra a MÉDIA do raio, e média esconde território dividido: dois pontos com a
 * mesma média podem ser lugares completamente diferentes. Os extremos e a mediana já vêm
 * no payload — faltava mostrá-los.
 */
export function ReguaDispersao({
  rotulo,
  dist,
  formatar = (v: number) => num(v),
}: {
  rotulo: string
  dist: PontoDistribuicao | null | undefined
  formatar?: (v: number) => string
}) {
  const f = faixaDaDistribuicao(dist)
  if (!f) return null
  return (
    <div style={{ display: 'grid', gap: 5 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}>
        <span style={{ font: '500 10.5px/1.2 var(--f-ui)', color: 'var(--tx-label)' }}>{rotulo}</span>
        <span className="num" style={{ font: '500 10.5px/1.2 var(--f-num)', color: 'var(--tx-sub)' }}>
          mediana {formatar(f.p50)}
        </span>
      </div>
      <div style={{ position: 'relative', height: 6, borderRadius: 3, background: 'var(--surf-pending)' }}>
        <div style={{ position: 'absolute', inset: 0, borderRadius: 3, background: 'var(--line-mid)' }} />
        {/* A marca da mediana, e não uma barra que preenche: o que se lê aqui é ONDE o
            meio cai entre os extremos, não "quanto" de alguma coisa. */}
        <div
          aria-hidden
          style={{
            position: 'absolute',
            left: `calc(${Math.round(f.posicaoMediana * 100)}% - 1px)`,
            top: -3,
            width: 2,
            height: 12,
            borderRadius: 1,
            background: 'var(--tx-max)',
          }}
        />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <span className="num" style={{ font: '400 9.5px/1 var(--f-num)', color: 'var(--tx-off)' }}>
          {formatar(f.min)}
        </span>
        <span className="num" style={{ font: '400 9.5px/1 var(--f-num)', color: 'var(--tx-off)' }}>
          {formatar(f.max)}
        </span>
      </div>
    </div>
  )
}
