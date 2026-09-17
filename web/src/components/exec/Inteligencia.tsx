import { useCallback, useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'

import { brl, brlCurto, num, pct, pctVar } from '../../lib/format'
import type {
  RedeInteligencia,
  RedeQuadranteChave,
  RedeQuadrantePonto,
  RedeRampaPonto,
  RedeRampaUnidade,
  RedeSinal,
} from '../../lib/types'
import { Glass, Spinner } from '../primitives'

/* ---------------------------------------------------------------------------
   Por trás dos números — o que o motor sabe sobre o CHÃO de cada unidade.

   A carteira e o panorama leem a rede só pela operação (Growth). Estes cards
   cruzam a operação com o que o motor já materializou. Cards soltos, em largura
   cheia e empilhados, no mesmo padrão do Panorama (decisão do Felipe, 14/09 —
   o seletor de abas foi descartado).

   - O que mudou: "o que virou no último mês fechado?"
   - Praça × execução: "essa unidade vai mal por causa do chão ou da gestão?"
   - Rampa: "a unidade nova está no ritmo das outras na mesma idade?"
   - Retenção: "onde a base é frágil?"
   - Sinais: "quem vai aparecer no churn do mês que vem?"

   Concorrência e canibalização ficam SÓ na ficha da unidade.
   --------------------------------------------------------------------------- */

export const COR_QUADRANTE: Record<RedeQuadranteChave, string> = {
  referencia: 'var(--pos)',
  execucao: 'var(--gr-coral)',
  supera: 'var(--gr-azul)',
  limite: 'var(--tx-muted)',
}

export function Titulo({ children, extra }: { children: ReactNode; extra?: ReactNode }) {
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 11, flexWrap: 'wrap' }}>
      <div
        style={{
          font: '600 10.5px/1 var(--f-ui)',
          letterSpacing: '.09em',
          textTransform: 'uppercase',
          color: 'var(--tx-strong)',
        }}
      >
        {children}
      </div>
      {extra && <div style={{ marginLeft: 'auto' }}>{extra}</div>}
    </div>
  )
}

export function Rodape({ children }: { children: ReactNode }) {
  return (
    <div style={{ marginTop: 12, font: '400 10.5px/1.5 var(--f-ui)', color: 'var(--tx-muted)' }}>{children}</div>
  )
}

function Lide({ children }: { children: ReactNode }) {
  return <div style={{ font: '400 12.5px/1.6 var(--f-ui)', color: 'var(--tx-narrative)', marginBottom: 12 }}>{children}</div>
}

export function Chip({
  ativo,
  onClick,
  children,
}: {
  ativo: boolean
  onClick: () => void
  children: ReactNode
}) {
  return (
    <button
      type="button"
      aria-pressed={ativo}
      onClick={onClick}
      style={{
        padding: '4px 8px',
        borderRadius: 'var(--r-sm)',
        border: `1px solid ${ativo ? 'var(--ac)' : 'var(--line-soft)'}`,
        background: ativo ? 'var(--ac-a12)' : 'transparent',
        color: ativo ? 'var(--ac-text)' : 'var(--tx-soft)',
        font: '600 10px/1 var(--f-ui)',
        cursor: 'pointer',
        whiteSpace: 'nowrap',
      }}
    >
      {children}
    </button>
  )
}

/** "smart_fit" -> "Smart Fit". O slug da rede vem do coletor. */
export function nomeRede(slug: string | null | undefined): string {
  if (!slug) return '—'
  return slug
    .replace(/[_-]+/g, ' ')
    .split(' ')
    .filter(Boolean)
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
    .join(' ')
}

export function metros(v: number | null | undefined): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return '—'
  return v >= 1000 ? `${num(v / 1000, 1)} km` : `${num(v)} m`
}

/** Largura medida do contêiner — o SVG precisa dela para não distorcer (ver `ExecCharts`). */
export function useLargura(): [(no: HTMLElement | null) => void, number] {
  const [largura, setLargura] = useState(0)
  const observador = useRef<ResizeObserver | null>(null)
  const medir = useCallback((no: HTMLElement | null) => {
    observador.current?.disconnect()
    if (!no) return
    setLargura(no.getBoundingClientRect().width)
    if (typeof ResizeObserver === 'undefined') return
    const obs = new ResizeObserver(([entrada]) => setLargura(entrada.contentRect.width))
    obs.observe(no)
    observador.current = obs
  }, [])
  useEffect(() => () => observador.current?.disconnect(), [])
  return [medir, largura]
}

const CARD = { padding: '15px 18px', minWidth: 0 } as const

/* ============================ SEÇÃO ============================ */

export function PorTrasDosNumeros({
  dados,
  maduras,
  onMaduras,
  onUnidade,
}: {
  dados: RedeInteligencia | null
  maduras: boolean
  onMaduras: (v: boolean) => void
  onUnidade: (id: string) => void
}) {
  if (!dados) {
    return (
      <Glass style={CARD}>
        <Titulo>Praça, rampa, sinais e retenção</Titulo>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--tx-sub)', font: '400 12px/1 var(--f-ui)' }}>
          <Spinner tamanho={12} /> Cruzando a operação com praça, retenção e rampa…
        </div>
      </Glass>
    )
  }
  return (
    <>
      <PracaExecucao dados={dados} maduras={maduras} onMaduras={onMaduras} onUnidade={onUnidade} />
      <Rampa dados={dados} onUnidade={onUnidade} />
      <SinaisAntecedentes dados={dados} onUnidade={onUnidade} />
      <RiscoRetencao dados={dados} onUnidade={onUnidade} />
      <MovimentacaoConcorrencia dados={dados} />
    </>
  )
}

/* ============================ O QUE MUDOU ============================ */


/* ============================ PRAÇA × EXECUÇÃO ============================ */

/** Mesma DISPOSIÇÃO do gráfico, lida em grade 2x2: em cima faturamento acima da mediana,
 *  embaixo abaixo; à esquerda praça mais fraca, à direita praça boa. Clicar no botão e olhar
 *  o canto do gráfico passa a ser o mesmo gesto (pedido do Felipe, 15/09). */
const ORDEM_QUADRANTES: RedeQuadranteChave[] = ['supera', 'referencia', 'limite', 'execucao']

export function DispersaoPraca({
  pontos,
  cortePraca,
  corteDesempenho,
  destaque,
  onUnidade,
  altura = 320,
}: {
  pontos: RedeQuadrantePonto[]
  cortePraca: number | null
  corteDesempenho: number | null
  destaque?: RedeQuadranteChave | null
  onUnidade?: (id: string) => void
  altura?: number
}) {
  const [medir, medida] = useLargura()
  const [sobre, setSobre] = useState<RedeQuadrantePonto | null>(null)
  const largura = medida > 0 ? medida : 520
  const margem = { esq: 52, dir: 12, topo: 18, base: 34 }
  const w = Math.max(largura - margem.esq - margem.dir, 10)
  const h = altura - margem.topo - margem.base
  const yMax = Math.max(...pontos.map((p) => p.faturamento), corteDesempenho ?? 0) * 1.08 || 1
  const xMin = Math.max(0, Math.floor(Math.min(...pontos.map((p) => p.score_praca)) / 10) * 10)
  const x = (v: number) => margem.esq + ((v - xMin) / (100 - xMin)) * w
  const y = (v: number) => margem.topo + h - (v / yMax) * h

  return (
    <div ref={medir} style={{ position: 'relative' }}>
      <svg viewBox={`0 0 ${largura} ${altura}`} width="100%" height={altura} role="img" aria-label="Praça contra faturamento">
        {[0, 0.25, 0.5, 0.75, 1].map((f) => (
          <g key={f}>
            <line x1={margem.esq} x2={margem.esq + w} y1={y(f * yMax)} y2={y(f * yMax)} stroke="var(--line-soft)" />
            <text x={margem.esq - 6} y={y(f * yMax) + 3} textAnchor="end" style={{ font: '500 8.5px/1 var(--f-num)', fill: 'var(--tx-muted)' }}>
              {brlCurto(f * yMax)}
            </text>
          </g>
        ))}
        {Array.from({ length: Math.floor((100 - xMin) / 10) + 1 }, (_, i) => xMin + i * 10).map((v) => (
          <text key={v} x={x(v)} y={margem.topo + h + 13} textAnchor="middle" style={{ font: '500 8.5px/1 var(--f-num)', fill: 'var(--tx-muted)' }}>
            {v}
          </text>
        ))}
        <text x={margem.esq} y={10} style={{ font: '500 9.5px/1 var(--f-ui)', fill: 'var(--tx-label)' }}>
          Faturamento do mês fechado
        </text>
        <text x={margem.esq + w} y={altura - 3} textAnchor="end" style={{ font: '500 9.5px/1 var(--f-ui)', fill: 'var(--tx-label)' }}>
          Qualidade da praça (0 a 100) →
        </text>

        {cortePraca !== null && corteDesempenho !== null && (
          <g>
            <line x1={margem.esq} x2={margem.esq + w} y1={y(corteDesempenho)} y2={y(corteDesempenho)} stroke="var(--line-strong)" strokeDasharray="4 3" />
            <text x={margem.esq + w - 4} y={y(corteDesempenho) - 5} textAnchor="end" style={{ font: '500 8.5px/1 var(--f-ui)', fill: 'var(--tx-muted)' }}>
              mediana de faturamento
            </text>
            <line x1={x(cortePraca)} x2={x(cortePraca)} y1={margem.topo} y2={margem.topo + h} stroke="var(--line-strong)" strokeDasharray="4 3" />
            <text x={x(cortePraca) + 4} y={margem.topo + 9} style={{ font: '500 8.5px/1 var(--f-ui)', fill: 'var(--tx-muted)' }}>
              mediana de praça
            </text>
          </g>
        )}

        {pontos.map((p) => {
          const cor = p.quadrante ? COR_QUADRANTE[p.quadrante] : 'var(--tx-muted)'
          const apagado = Boolean(destaque && p.quadrante !== destaque)
          return (
            <circle
              key={p.id}
              cx={x(p.score_praca)}
              cy={y(p.faturamento)}
              r={apagado ? 4 : 5.5}
              fill={cor}
              fillOpacity={apagado ? 0.4 : 0.95}
              stroke="var(--bg-base)"
              strokeWidth={1}
              style={{ cursor: onUnidade ? 'pointer' : 'default' }}
              onMouseEnter={() => setSobre(p)}
              onMouseLeave={() => setSobre(null)}
              onClick={() => onUnidade?.(p.id)}
            />
          )
        })}
      </svg>
      {sobre && (
        <div
          style={{
            position: 'absolute',
            left: Math.min(x(sobre.score_praca) + 10, largura - 220),
            top: Math.max(y(sobre.faturamento) - 58, 0),
            width: 210,
            padding: '8px 10px',
            borderRadius: 'var(--r-sm)',
            background: 'var(--bg-base)',
            border: '1px solid var(--line-mid)',
            boxShadow: '0 6px 18px rgba(0,0,0,.18)',
            pointerEvents: 'none',
            font: '400 11px/1.45 var(--f-ui)',
            color: 'var(--tx-sub)',
          }}
        >
          <div style={{ font: '600 12px/1.2 var(--f-ui)', color: 'var(--tx-strong)' }}>{sobre.nome}</div>
          {sobre.quadrante_rotulo && <div>{sobre.quadrante_rotulo}</div>}
          <div>
            Praça {num(sobre.score_praca, 1)} · {brl(sobre.faturamento)}
          </div>
        </div>
      )}
    </div>
  )
}

function PracaExecucao({
  dados,
  maduras,
  onMaduras,
  onUnidade,
}: {
  dados: RedeInteligencia
  maduras: boolean
  onMaduras: (v: boolean) => void
  onUnidade: (id: string) => void
}) {
  const [filtro, setFiltro] = useState<RedeQuadranteChave | null>('execucao')
  const q = dados.quadrante
  const lista = q.pontos.filter((p) => (filtro ? p.quadrante === filtro : true)).sort((a, b) => b.score_praca - a.score_praca)
  const notaCobertura = dados.notas.find((n) => n.includes('quadrante'))

  return (
    <Glass style={CARD}>
      <Titulo
        extra={
          <span style={{ display: 'flex', gap: 6 }}>
            <Chip ativo={maduras} onClick={() => onMaduras(true)}>
              Só com {q.meses_madura}+ meses
            </Chip>
            <Chip ativo={!maduras} onClick={() => onMaduras(false)}>
              Todas
            </Chip>
          </span>
        }
      >
        Praça × execução
      </Titulo>
      <Lide>
        Cada ponto é uma unidade: quanto mais à direita, melhor a praça; quanto mais alto, maior o faturamento. As linhas
        tracejadas são as medianas e dividem as unidades em quatro situações. Clique numa situação para ver quem está nela.
      </Lide>
      {q.n < 4 ? (
        <div style={{ font: '400 12px/1.5 var(--f-ui)', color: 'var(--tx-sub)' }}>
          O recorte tem {q.n} unidade(s) com praça e faturamento fechado — pouco para comparar.
        </div>
      ) : (
        <div style={{ display: 'flex', gap: 22, flexWrap: 'wrap' }}>
          <div style={{ flex: '2 1 460px', minWidth: 0 }}>
            <DispersaoPraca
              pontos={q.pontos}
              cortePraca={q.corte_praca}
              corteDesempenho={q.corte_desempenho}
              destaque={filtro}
              onUnidade={onUnidade}
            />
          </div>
          <div style={{ flex: '1 1 300px', minWidth: 0 }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, marginBottom: 10 }}>
              {ORDEM_QUADRANTES.map((chave) => {
                const ativo = filtro === chave
                return (
                  <button
                    key={chave}
                    type="button"
                    aria-pressed={ativo}
                    onClick={() => setFiltro(ativo ? null : chave)}
                    title={q.explicacao[chave]}
                    style={{
                      textAlign: 'left',
                      padding: '8px 9px',
                      borderRadius: 'var(--r-sm)',
                      border: `1px solid ${ativo ? COR_QUADRANTE[chave] : 'var(--line-soft)'}`,
                      background: ativo ? 'var(--ac-a08)' : 'transparent',
                      cursor: 'pointer',
                    }}
                  >
                    <div className="num" style={{ font: '700 18px/1 var(--f-num)', color: COR_QUADRANTE[chave] }}>
                      {q.contagem[chave]}
                    </div>
                    <div style={{ font: '500 10.5px/1.3 var(--f-ui)', color: 'var(--tx-label)', marginTop: 3 }}>{q.rotulos[chave]}</div>
                  </button>
                )
              })}
            </div>
            {filtro && <div style={{ font: '400 11.5px/1.45 var(--f-ui)', color: 'var(--tx-sub)', marginBottom: 6 }}>{q.explicacao[filtro]}</div>}
            <ul style={{ listStyle: 'none', margin: 0, padding: 0, maxHeight: 200, overflowY: 'auto' }}>
              {lista.map((p) => (
                <li key={p.id}>
                  <button
                    type="button"
                    onClick={() => onUnidade(p.id)}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      gap: 8,
                      width: '100%',
                      padding: '5px 0',
                      border: 0,
                      borderBottom: '1px solid var(--line-soft)',
                      background: 'transparent',
                      cursor: 'pointer',
                      font: '400 11.5px/1.3 var(--f-ui)',
                      color: 'var(--tx-strong)',
                      textAlign: 'left',
                    }}
                  >
                    <span style={{ minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.nome}</span>
                    <span className="num" style={{ font: '500 10.5px/1 var(--f-num)', color: 'var(--tx-muted)', whiteSpace: 'nowrap' }}>
                      praça {num(p.score_praca, 0)} · {brlCurto(p.faturamento)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
      <Rodape>
        Qualidade da praça = score socioeconômico (renda e população, régua absoluta) no raio de 1 km da unidade. Faturamento do último mês fechado. Medianas das {q.n} unidades exibidas
        {q.corte_praca !== null ? `: praça ${num(q.corte_praca, 1)} e ${brl(q.corte_desempenho)}` : ''}. É ponto de partida
        para a conversa, não previsão (DEC-043).{notaCobertura ? ` ${notaCobertura}` : ''}
      </Rodape>
    </Glass>
  )
}

/* ================================ RAMPA ================================ */

export function GraficoRampa({
  curva,
  unidades = [],
  trajetoria,
  formato = 'brl',
  altura = 220,
  onUnidade,
}: {
  curva: RedeRampaPonto[]
  unidades?: RedeRampaUnidade[]
  trajetoria?: { mes: number; valor: number | null }[]
  formato?: 'brl' | 'int'
  altura?: number
  onUnidade?: (id: string) => void
}) {
  const [medir, medida] = useLargura()
  const largura = medida > 0 ? medida : 520
  const margem = { esq: 46, dir: 10, topo: 10, base: 26 }
  const w = Math.max(largura - margem.esq - margem.dir, 10)
  const h = altura - margem.topo - margem.base
  const meses = curva.map((p) => p.mes)
  const mesMax = Math.max(24, ...meses, ...(trajetoria ?? []).map((t) => t.mes))
  // A escala segue a FAIXA da rede (e a trajetória da unidade, na ficha), não os pontos
  // extremos: duas unidades muito acima da curva esmagavam a faixa no pé do gráfico. Ponto
  // acima do teto é desenhado preso na borda, com contorno, e o valor real vai no title.
  const teto = Math.max(...curva.map((p) => p.p75 ?? 0), 1) * 1.6
  const yMax = Math.max(teto, ...(trajetoria ?? []).map((t) => t.valor ?? 0)) * 1.05
  const x = (m: number) => margem.esq + ((m - 1) / Math.max(mesMax - 1, 1)) * w
  const y = (v: number) => margem.topo + h - (Math.min(v, yMax) / yMax) * h
  const fmt = (v: number) => (formato === 'brl' ? brlCurto(v) : num(v))
  const faixa = curva.filter((p) => p.p25 !== null && p.p75 !== null)
  const area = faixa.length
    ? `M${faixa.map((p) => `${x(p.mes)},${y(p.p75 as number)}`).join(' L')} L${[...faixa]
        .reverse()
        .map((p) => `${x(p.mes)},${y(p.p25 as number)}`)
        .join(' L')} Z`
    : ''
  const mediana = curva.filter((p) => p.p50 !== null).map((p) => `${x(p.mes)},${y(p.p50 as number)}`)
  const traj = (trajetoria ?? []).filter((t) => t.valor !== null && t.mes <= mesMax)
  const corFaixa = { abaixo: 'var(--neg)', na_curva: 'var(--tx-sub)', acima: 'var(--pos)' } as const

  return (
    <div ref={medir}>
      <svg viewBox={`0 0 ${largura} ${altura}`} width="100%" height={altura} role="img" aria-label="Rampa de maturação">
        {[0, 0.5, 1].map((f) => (
          <g key={f}>
            <line x1={margem.esq} x2={margem.esq + w} y1={y(f * yMax)} y2={y(f * yMax)} stroke="var(--line-soft)" />
            <text x={margem.esq - 6} y={y(f * yMax) + 3} textAnchor="end" style={{ font: '500 8.5px/1 var(--f-num)', fill: 'var(--tx-muted)' }}>
              {fmt(f * yMax)}
            </text>
          </g>
        ))}
        {[1, 6, 12, 18, 24].filter((m) => m <= mesMax).map((m) => (
          <text key={m} x={x(m)} y={altura - 8} textAnchor="middle" style={{ font: '500 8.5px/1 var(--f-num)', fill: 'var(--tx-muted)' }}>
            {m === 1 ? 'mês 1' : m}
          </text>
        ))}
        {area && <path d={area} fill="var(--ac)" opacity={0.12} />}
        {mediana.length > 1 && <path d={`M${mediana.join(' L')}`} fill="none" stroke="var(--ac)" strokeWidth={1.8} />}
        {traj.length > 1 && (
          <path d={`M${traj.map((t) => `${x(t.mes)},${y(t.valor as number)}`).join(' L')}`} fill="none" stroke="var(--gr-coral)" strokeWidth={2.2} />
        )}
        {traj.map((t) => (
          <circle key={t.mes} cx={x(t.mes)} cy={y(t.valor as number)} r={2.6} fill="var(--gr-coral)" />
        ))}
        {unidades.map((u) =>
          u.valor === null ? null : (
            <circle
              key={u.id}
              cx={x(u.meses_operacao)}
              cy={y(u.valor)}
              r={4.2}
              fill={corFaixa[u.faixa]}
              fillOpacity={0.85}
              stroke={u.valor > yMax ? 'var(--tx-max)' : 'var(--bg-base)'}
              strokeWidth={u.valor > yMax ? 1.5 : 1}
              style={{ cursor: onUnidade ? 'pointer' : 'default' }}
              onClick={() => onUnidade?.(u.id)}
            >
              <title>{`${u.nome} · mês ${u.meses_operacao} · ${fmt(u.valor)} (${pctVar(u.desvio_pct, 0)} vs mediana)`}</title>
            </circle>
          ),
        )}
      </svg>
    </div>
  )
}

function Rampa({ dados, onUnidade }: { dados: RedeInteligencia; onUnidade: (id: string) => void }) {
  const { curva, unidades, janela } = dados.rampa
  const abaixo = unidades.filter((u) => u.faixa === 'abaixo')
  return (
    <Glass style={CARD}>
      <Titulo>Rampa das unidades novas</Titulo>
      {curva.length === 0 ? (
        <Lide>Sem histórico suficiente para a curva.</Lide>
      ) : (
        <>
          <Lide>
            Faturamento de cada unidade nova contra as outras unidades da rede{' '}
            <strong style={{ color: 'var(--tx-strong)' }}>na mesma idade</strong>.{' '}
            <span style={{ color: 'var(--neg)' }}>{abaixo.length}</span> de {unidades.length} estão abaixo do quartil inferior.
          </Lide>
          <div style={{ display: 'flex', gap: 22, flexWrap: 'wrap' }}>
            <div style={{ flex: '2 1 460px', minWidth: 0 }}>
              <GraficoRampa curva={curva} unidades={unidades} onUnidade={onUnidade} />
            </div>
            <div style={{ flex: '1 1 300px', minWidth: 0 }}>
              <TabelaSimples
                cabecalho={['Unidade', 'Mês de vida', 'vs mediana']}
                linhas={unidades.slice(0, 10).map((u) => ({
                  id: u.id,
                  celulas: [
                    u.nome,
                    String(u.meses_operacao),
                    <span key="d" style={{ color: u.faixa === 'abaixo' ? 'var(--neg)' : u.faixa === 'acima' ? 'var(--pos)' : 'var(--tx-sub)' }}>
                      {pctVar(u.desvio_pct, 0)}
                    </span>,
                  ],
                }))}
                onLinha={onUnidade}
              />
            </div>
          </div>
        </>
      )}
      <Rodape>
        Faixa = do quartil inferior ao superior da rede em cada mês de vida; linha = mediana. Pontos = unidades entre o mês{' '}
        {janela[0]} e o {janela[1]}; vermelho = abaixo do quartil inferior. Só meses fechados. A curva mistura safras de anos
        diferentes.
      </Rodape>
    </Glass>
  )
}

/* ========================== SINAIS ANTECEDENTES ========================== */

export function CelulaSinal({ sinal }: { sinal: RedeSinal | undefined }) {
  if (!sinal || sinal.valor === null) return <span style={{ color: 'var(--tx-muted)' }}>—</span>
  const texto = sinal.chave === 'recorrentes_3m_pct' ? pctVar(sinal.valor, 1) : pct(sinal.valor, 1)
  return (
    <span
      className="num"
      title={`${sinal.rotulo}: ${sinal.detalhe}. Pior quartil da rede a partir de ${sinal.limiar_quartil ?? '—'}.`}
      style={{ font: `${sinal.aceso ? 700 : 500} 11.5px/1 var(--f-num)`, color: sinal.aceso ? 'var(--neg)' : 'var(--tx-sub)' }}
    >
      {texto}
    </span>
  )
}

function SinaisAntecedentes({ dados, onUnidade }: { dados: RedeInteligencia; onUnidade: (id: string) => void }) {
  const { unidades, avaliadas, definicoes } = dados.sinais
  const chaves = Object.keys(definicoes)
  // O limiar do quartil é o MESMO para todas as unidades do mês: basta ler de uma.
  const referencia = unidades[0]?.sinais ?? []
  return (
    <Glass style={CARD}>
      <Titulo>Sinais antes do churn</Titulo>
      <Lide>
        Três números que costumam piorar <strong style={{ color: 'var(--tx-strong)' }}>antes</strong> do churn. Em vermelho, a
        unidade está entre as 25% piores da rede naquele número. {unidades.length} de {avaliadas} unidades têm ao menos um
        sinal aceso.
      </Lide>
      {unidades.length === 0 ? null : (
        <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', alignItems: 'flex-start' }}>
          <div style={{ flex: '3 1 620px', minWidth: 0, maxHeight: 360, overflowY: 'auto' }}>
            <TabelaSimples
              cabecalho={['Unidade', ...chaves.map((c) => definicoes[c].rotulo), 'Acesos']}
              linhas={unidades.map((u) => ({
                id: u.id,
                celulas: [
                  u.nome,
                  ...chaves.map((c) => <CelulaSinal key={c} sinal={u.sinais.find((s) => s.chave === c)} />),
                  <span key="n" style={{ color: u.acesos >= 2 ? 'var(--neg)' : 'var(--tx-sub)', fontWeight: 700 }}>
                    {u.acesos}
                  </span>,
                ],
              }))}
              onLinha={onUnidade}
            />
          </div>
          <div style={{ flex: '1 1 280px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
            {chaves.map((c) => {
              const limiar = referencia.find((s) => s.chave === c)?.limiar_quartil
              const acesos = unidades.filter((u) => u.sinais.some((s) => s.chave === c && s.aceso)).length
              const pior = definicoes[c].pior === 'alto'
              return (
                <div key={c} style={{ padding: '10px 12px', borderRadius: 'var(--r-sm)', border: '1px solid var(--line-soft)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 8 }}>
                    <span style={{ font: '600 12px/1.3 var(--f-ui)', color: 'var(--tx-strong)' }}>{definicoes[c].rotulo}</span>
                    <span className="num" style={{ font: '700 16px/1 var(--f-num)', color: acesos ? 'var(--neg)' : 'var(--tx-muted)' }}>
                      {acesos}
                    </span>
                  </div>
                  <div style={{ font: '400 11px/1.45 var(--f-ui)', color: 'var(--tx-sub)', marginTop: 4 }}>
                    {definicoes[c].detalhe.charAt(0).toUpperCase() + definicoes[c].detalhe.slice(1)}.
                  </div>
                  <div style={{ font: '400 10.5px/1.4 var(--f-ui)', color: 'var(--tx-muted)', marginTop: 4 }}>
                    Acende {pior ? 'a partir de' : 'abaixo de'}{' '}
                    <strong className="num" style={{ color: 'var(--tx-strong)' }}>
                      {limiar === null || limiar === undefined
                        ? '—'
                        : c === 'recorrentes_3m_pct'
                          ? pctVar(limiar, 1)
                          : pct(limiar, 1)}
                    </strong>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
      <Rodape>
        Cancelamento solicitado e cobrança: foto do fim do mês, sobre os recorrentes. Recorrentes em 3 meses: variação contra
        três meses fechados antes. Sem régua absoluta validada, então a leitura é relativa à rede.
      </Rodape>
    </Glass>
  )
}

/* ================================ RETENÇÃO ================================ */

export function BarraLtv({
  fragil,
  risco,
  duravel,
  alta,
  altura = 8,
  arredondada = true,
}: {
  fragil: number | null | undefined
  risco: number | null | undefined
  duravel: number | null | undefined
  alta: number | null | undefined
  /** a barra da REDE é mais alta e de canto reto: ela é o gráfico do card, não um detalhe de linha */
  altura?: number
  arredondada?: boolean
}) {
  const partes = [
    { v: fragil ?? 0, cor: 'var(--neg)', rotulo: 'Frágil' },
    { v: risco ?? 0, cor: 'var(--gr-coral)', rotulo: 'Em risco' },
    { v: duravel ?? 0, cor: 'var(--gr-azul)', rotulo: 'Durável' },
    { v: alta ?? 0, cor: 'var(--pos)', rotulo: 'Alta durabilidade' },
  ]
  const total = partes.reduce((s, p) => s + p.v, 0) || 1
  return (
    <div style={{ display: 'flex', height: altura, borderRadius: arredondada ? altura / 2 : 0, overflow: 'hidden', background: 'var(--line-soft)' }}>
      {partes.map((p) => (
        <div key={p.rotulo} title={`${p.rotulo}: ${pct(p.v, 1)}`} style={{ width: `${(100 * p.v) / total}%`, background: p.cor }} />
      ))}
    </div>
  )
}

/** Faixas de risco do mapa de calor: percentil na rede, que é como o modelo se declara. */
const FAIXAS_RISCO: { ate: number; cor: string; rotulo: string }[] = [
  { ate: 25, cor: 'var(--pos)', rotulo: 'baixo' },
  { ate: 50, cor: 'var(--gr-azul)', rotulo: 'moderado' },
  { ate: 75, cor: 'var(--warn)', rotulo: 'alto' },
  { ate: 101, cor: 'var(--neg)', rotulo: 'crítico' },
]

const corDoRisco = (percentil: number | null | undefined) =>
  FAIXAS_RISCO.find((f) => (percentil ?? 0) < f.ate)?.cor ?? 'var(--tx-off)'

/**
 * Retenção prevista em DUAS leituras (pedido do Felipe, 15/09), no lugar das 16 barras de
 * LTV repetidas: um RANKING com barra única (quem cancela primeiro) e um MAPA DE CALOR por
 * consultor (onde o risco está concentrado na carteira de cada um). A composição de LTV
 * vira UMA barra da rede — ela dizia a mesma coisa 16 vezes.
 */
function RiscoRetencao({ dados, onUnidade }: { dados: RedeInteligencia; onUnidade: (id: string) => void }) {
  const r = dados.retencao
  const [vista, setVista] = useState<'ranking' | 'calor'>('ranking')
  const [todas, setTodas] = useState(false)
  const unidades = r.unidades ?? []
  const visiveis = todas ? unidades : unidades.slice(0, 12)

  // Composição média da rede: uma barra só, no lugar de uma por unidade.
  const media = (campo: (u: (typeof unidades)[number]) => number | null | undefined) => {
    const vs = unidades.map(campo).filter((v): v is number => v !== null && v !== undefined)
    return vs.length ? vs.reduce((a, b) => a + b, 0) / vs.length : null
  }
  const composicao = {
    fragil: media((u) => u.ltv_fragil_pct),
    risco: media((u) => u.ltv_em_risco_pct),
    duravel: media((u) => u.ltv_duravel_pct),
    alta: media((u) => u.ltv_alta_durabilidade_pct),
  }

  const porConsultor = [...unidades.reduce((mapa, u) => {
    const chave = u.consultor ?? 'sem consultor'
    mapa.set(chave, [...(mapa.get(chave) ?? []), u])
    return mapa
  }, new Map<string, typeof unidades>())]
    .map(([consultor, us]) => ({
      consultor,
      us: [...us].sort((a, b) => (b.risco_percentil ?? 0) - (a.risco_percentil ?? 0)),
      criticas: us.filter((u) => (u.risco_percentil ?? 0) >= 75).length,
    }))
    .sort((a, b) => b.criticas - a.criticas || b.us.length - a.us.length)

  return (
    <Glass style={CARD}>
      <Titulo
        extra={
          <span style={{ display: 'flex', gap: 6 }}>
            <Chip ativo={vista === 'ranking'} onClick={() => setVista('ranking')}>Ranking</Chip>
            <Chip ativo={vista === 'calor'} onClick={() => setVista('calor')}>Por consultor</Chip>
          </span>
        }
      >
        Retenção prevista
      </Titulo>
      {r.data_artefato === null ? (
        <Lide>Modelo de retenção indisponível neste ambiente.</Lide>
      ) : (
        <>
          <Lide>
            Unidades com <strong style={{ color: 'var(--tx-strong)' }}>maior risco de cancelamento</strong> nos próximos 90
            dias. Cobre {r.cobertas} de {r.no_recorte} unidades do recorte
            {r.fora_do_modelo
              ? `; ${r.fora_do_modelo} ficam de fora porque o próprio modelo não é confiável para elas (unidade nova, poucos alunos ou poucos cancelamentos)`
              : ''}
            .
          </Lide>

          {composicao.fragil !== null && (
            <div style={{ marginBottom: 14 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', font: '500 10px/1.2 var(--f-ui)', color: 'var(--tx-label)', marginBottom: 5 }}>
                <span>Base da rede por durabilidade prevista</span>
                <span className="num" style={{ color: 'var(--tx-muted)' }}>{pct(composicao.fragil, 0)} frágil</span>
              </div>
              <BarraLtv
                fragil={composicao.fragil}
                risco={composicao.risco}
                duravel={composicao.duravel}
                alta={composicao.alta}
                altura={18}
                arredondada={false}
              />
            </div>
          )}

          {vista === 'ranking' ? (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(330px, 1fr))', columnGap: 24 }}>
              {visiveis.map((u) => (
                <button
                  key={u.id}
                  type="button"
                  onClick={() => onUnidade(u.id)}
                  style={{ display: 'flex', alignItems: 'center', gap: 10, width: '100%', padding: '6px 0', border: 0, borderBottom: '1px solid var(--line-soft)', background: 'transparent', cursor: 'pointer', textAlign: 'left' }}
                >
                  <span style={{ flex: 1, minWidth: 0, font: '500 12px/1.3 var(--f-ui)', color: 'var(--tx-strong)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {u.nome}
                  </span>
                  <span style={{ width: 96, height: 7, borderRadius: 4, background: 'var(--surf-raised)', flexShrink: 0 }}>
                    <span
                      style={{
                        display: 'block',
                        width: `${Math.max(u.risco_percentil ?? 0, 2)}%`,
                        height: '100%',
                        borderRadius: 4,
                        background: corDoRisco(u.risco_percentil),
                      }}
                    />
                  </span>
                  <span className="num" style={{ width: 92, textAlign: 'right', font: '600 11px/1 var(--f-num)', color: (u.risco_percentil ?? 0) >= 75 ? 'var(--neg)' : 'var(--tx-sub)' }}>
                    {u.prob_cancel_90d_pct !== null ? `${pct(u.prob_cancel_90d_pct, 1)} em 90d` : `p${num(u.risco_percentil)}`}
                  </span>
                </button>
              ))}
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {porConsultor.map((linha) => (
                <div key={linha.consultor} style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
                  <span style={{ width: 150, flexShrink: 0, font: '500 11.5px/1.3 var(--f-ui)', color: 'var(--tx-label)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {linha.consultor}
                  </span>
                  <span style={{ display: 'flex', gap: 3, flexWrap: 'wrap', flex: 1, minWidth: 0 }}>
                    {linha.us.map((u) => (
                      <button
                        key={u.id}
                        type="button"
                        onClick={() => onUnidade(u.id)}
                        title={`${u.nome} — ${u.prob_cancel_90d_pct !== null ? `${pct(u.prob_cancel_90d_pct, 1)} em 90 dias` : `mais arriscada que ${num(u.risco_percentil)}% da rede`}`}
                        aria-label={u.nome}
                        style={{ width: 15, height: 15, borderRadius: 3, border: 0, padding: 0, cursor: 'pointer', background: corDoRisco(u.risco_percentil) }}
                      />
                    ))}
                  </span>
                  <span className="num" style={{ width: 62, textAlign: 'right', font: '500 10.5px/1 var(--f-num)', color: linha.criticas ? 'var(--neg)' : 'var(--tx-muted)' }}>
                    {linha.criticas ? `${num(linha.criticas)} crítica${linha.criticas > 1 ? 's' : ''}` : '—'}
                  </span>
                </div>
              ))}
              <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', marginTop: 2, font: '400 10.5px/1 var(--f-ui)', color: 'var(--tx-muted)' }}>
                {FAIXAS_RISCO.map((f) => (
                  <span key={f.rotulo} style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
                    <span style={{ width: 9, height: 9, borderRadius: 2, background: f.cor }} /> risco {f.rotulo}
                  </span>
                ))}
              </div>
            </div>
          )}

          {vista === 'ranking' && unidades.length > 12 && (
            <div style={{ marginTop: 8 }}>
              <Chip ativo={todas} onClick={() => setTodas(!todas)}>
                {todas ? 'Mostrar menos' : `Ver as ${num(unidades.length)} unidades`}
              </Chip>
            </div>
          )}
        </>
      )}
      <Rodape>
        A chance em 90 dias só aparece onde o modelo diz que ela é confiável; nas demais, a posição na rede. O mapa por
        consultor mostra onde o risco se concentra — cada quadrado é uma unidade e abre a ficha.
        {r.data_artefato ? ` Modelo de ${r.data_artefato}.` : ''}
      </Rodape>
    </Glass>
  )
}

/* ======================= MOVIMENTAÇÃO DA CONCORRÊNCIA ======================= */

function MovimentacaoConcorrencia({ dados }: { dados: RedeInteligencia }) {
  const m = dados.movimentacao
  const [todas, setTodas] = useState(false)
  // Padrão = só as fotos VALIDADAS (02/08 a 06/09). A foto de 28/05 a 02/08 teve troca de
  // coletor em várias redes: com ela, a SkyFit lia +207 com UMA abertura conferida.
  const [comCautela, setComCautela] = useState(false)
  const redes = (m?.redes ?? [])
    .map((r) => {
      const aberturas = comCautela ? r.aberturas : r.aberturas_conferidas
      const fechamentos = comCautela ? r.fechamentos : r.fechamentos_conferidos
      return { ...r, aberturas, fechamentos, saldo: aberturas - fechamentos }
    })
    .filter((r) => r.aberturas || r.fechamentos || r.em_breve)
    .sort((a, b) => b.saldo - a.saldo || b.aberturas - a.aberturas || b.em_breve - a.em_breve)
  const visiveis = todas ? redes : redes.slice(0, 12)
  const wellhub = (m?.agregadores ?? []).filter((a) => a.agregador === 'wellhub')
  const celula = { padding: '0 8px', borderBottom: '1px solid var(--line-soft)', textAlign: 'right' as const, whiteSpace: 'nowrap' as const }
  const titulo = { ...celula, padding: '0 8px 7px', font: '600 9.5px/1.2 var(--f-ui)', letterSpacing: '.05em', textTransform: 'uppercase' as const, color: 'var(--tx-muted)', borderBottom: '1px solid var(--line-mid)' }
  const saldo = (v: number) => (
    <span style={{ color: v > 0 ? 'var(--gr-coral)' : v < 0 ? 'var(--pos)' : 'var(--tx-off)', fontWeight: 700 }}>
      {v > 0 ? `+${num(v)}` : num(v)}
    </span>
  )
  return (
    <Glass style={CARD}>
      <Titulo
        extra={
          <Chip ativo={comCautela} onClick={() => setComCautela(!comCautela)}>
            Incluir 28/05 a 02/08 (não validado)
          </Chip>
        }
      >
        Crescimento da concorrência
      </Titulo>
      {!m?.disponivel ? (
        <Lide>Histórico de movimentação da concorrência ausente neste ambiente.</Lide>
      ) : (
        <div style={{ display: 'flex', gap: 22, flexWrap: 'wrap', alignItems: 'flex-start' }}>
          <div style={{ flex: '3 1 520px', minWidth: 0, overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', font: '500 11.5px/1 var(--f-num)', color: 'var(--tx-sub)' }}>
              <thead>
                <tr>
                  <th style={{ ...titulo, textAlign: 'left' }}>Rede</th>
                  <th style={titulo}>Unidades</th>
                  <th style={titulo}>Aberturas</th>
                  <th style={titulo}>Fechamentos</th>
                  <th style={titulo}>Saldo</th>
                  <th style={titulo}>Em breve</th>
                </tr>
              </thead>
              <tbody>
                {visiveis.map((r) => (
                  <tr key={r.rede} style={{ height: 30 }}>
                    <td style={{ ...celula, textAlign: 'left' }}>
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, font: '500 12px/1 var(--f-ui)', color: 'var(--tx-strong)' }}>
                        {r.logo ? (
                          <img src={r.logo} alt="" width={18} height={18} style={{ display: 'block', flexShrink: 0 }} />
                        ) : (
                          <span style={{ width: 18, height: 18, borderRadius: 4, background: 'var(--ac-a12)', flexShrink: 0 }} />
                        )}
                        {nomeRede(r.rede)}
                      </span>
                    </td>
                    <td className="num" style={{ ...celula, color: 'var(--tx-strong)' }}>{r.unidades != null ? num(r.unidades) : '—'}</td>
                    <td className="num" style={celula}>{r.aberturas ? num(r.aberturas) : <span style={{ color: 'var(--tx-off)' }}>0</span>}</td>
                    <td className="num" style={celula}>{r.fechamentos ? num(r.fechamentos) : <span style={{ color: 'var(--tx-off)' }}>0</span>}</td>
                    <td className="num" style={celula}>{saldo(r.saldo)}</td>
                    <td className="num" style={celula}>{r.em_breve ? num(r.em_breve) : <span style={{ color: 'var(--tx-off)' }}>0</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {redes.length > 12 && (
              <div style={{ marginTop: 8 }}>
                <Chip ativo={todas} onClick={() => setTodas(!todas)}>
                  {todas ? 'Mostrar menos' : `Ver as ${num(redes.length)} redes`}
                </Chip>
              </div>
            )}
          </div>

          <div style={{ flex: '1 1 240px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div style={{ font: '600 9.5px/1.2 var(--f-ui)', letterSpacing: '.05em', textTransform: 'uppercase', color: 'var(--tx-muted)' }}>
              Agregadores
            </div>
            {wellhub.map((a) => (
              <div key={a.grupo} style={{ padding: '10px 12px', border: '1px solid var(--line-soft)', borderRadius: 'var(--r-md)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 7, font: '600 12px/1.2 var(--f-ui)', color: 'var(--tx-strong)' }}>
                  <img src="/logo-wellhub.png" alt="" width={16} height={16} style={{ display: 'block' }} />
                  Wellhub · {a.grupo === 'independentes' ? 'independentes' : 'unidades de rede'}
                </div>
                <div className="num" style={{ marginTop: 6, font: '400 11.5px/1.5 var(--f-num)', color: 'var(--tx-sub)' }}>
                  {num(a.entradas)} entraram · {num(a.saidas)} saíram · saldo {saldo(a.saldo)}
                </div>
              </div>
            ))}
            <div style={{ padding: '10px 12px', border: '1px dashed var(--line-soft)', borderRadius: 'var(--r-md)', font: '400 11.5px/1.5 var(--f-ui)', color: 'var(--tx-muted)' }}>
              TotalPass · sem histórico de entradas e saídas ainda
            </div>
          </div>
        </div>
      )}
      <Rodape>
        Redes: fotos do cadastro de 02/08 a 06/09, validadas contra a contagem oficial (a foto anterior entra só pelo botão);
        unidades = contagem oficial{m?.data_contagem ? ` de ${m.data_contagem.slice(8, 10)}/${m.data_contagem.slice(5, 7)}` : ''}.
        &quot;Em breve&quot;: anúncios ainda não inaugurados. Wellhub: 31/08 a 12/09. Sem Smart Fit (teto do coletor) e sem estúdios; saída do site nem sempre é fechamento.
      </Rodape>
    </Glass>
  )
}

/* ================================ TABELA ================================ */

function TabelaSimples({
  cabecalho,
  linhas,
  onLinha,
  alinhamento,
}: {
  cabecalho: string[]
  linhas: { id: string; celulas: ReactNode[] }[]
  onLinha: (id: string) => void
  /** por coluna; sem ele, a primeira à esquerda e as demais (números) à direita */
  alinhamento?: ('left' | 'right')[]
}) {
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', font: '400 12px/1.2 var(--f-ui)' }}>
      <thead>
        <tr>
          {cabecalho.map((c, i) => (
            <th
              key={c}
              scope="col"
              style={{
                textAlign: alinhamento?.[i] ?? (i === 0 ? 'left' : 'right'),
                padding: '0 6px 7px',
                font: '600 9.5px/1.2 var(--f-ui)',
                letterSpacing: '.05em',
                textTransform: 'uppercase',
                color: 'var(--tx-muted)',
                borderBottom: '1px solid var(--line-mid)',
                position: 'sticky',
                top: 0,
                background: 'var(--bg-base)',
              }}
            >
              {c}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {linhas.map((l) => (
          <tr key={l.id} onClick={() => onLinha(l.id)} style={{ cursor: 'pointer', height: 28 }}>
            {l.celulas.map((c, i) => (
              <td
                key={i}
                className={i === 0 ? undefined : 'num'}
                style={{
                  padding: '0 6px',
                  textAlign: alinhamento?.[i] ?? (i === 0 ? 'left' : 'right'),
                  borderBottom: '1px solid var(--line-soft)',
                  font: i === 0 ? '500 12px/1 var(--f-ui)' : '500 11.5px/1 var(--f-num)',
                  color: i === 0 ? 'var(--tx-strong)' : 'var(--tx-sub)',
                  whiteSpace: 'nowrap',
                }}
              >
                {c}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}
