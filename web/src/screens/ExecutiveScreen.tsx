import { useEffect, useMemo, useState } from 'react'

import ExecMap from '../components/ExecMap'
import Select from '../components/Select'
import { api, ApiError } from '../lib/api'
import { brl, num, pct } from '../lib/format'
import type { ExecMetric, ExecUnidade, ExecutivaPayload } from '../lib/types'

/** KPIs pelos quais a lista de unidades pode ser ranqueada. */
const ORDENAR_OPCOES = [
  { value: 'faturamento', label: 'Faturamento' },
  { value: 'ativos', label: 'Alunos ativos' },
  { value: 'churn', label: 'Churn (30d)' },
  { value: 'nps', label: 'NPS' },
  { value: 'ticket', label: 'Ticket médio' },
] as const
type OrdenarKey = (typeof ORDENAR_OPCOES)[number]['value']

function valorKpi(u: ExecUnidade, k: OrdenarKey): string {
  if (k === 'ativos') return num(u.ativos)
  if (k === 'churn') return pct(u.churn, 1)
  if (k === 'nps') return num(u.nps)
  if (k === 'ticket') return brl(u.ticket)
  return brl(u.faturamento, true)
}

const MESES_PT = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']
function labelMes(m: string): string {
  const [a, mm] = m.split('-')
  const nome = MESES_PT[Number(mm) - 1] ?? mm
  return `${nome.charAt(0).toUpperCase()}${nome.slice(1)}/${a}`
}

/* ---------------------------------------------------------------------------
   Visão Executiva — a rede Ultra REAL por estado (Growth API, camada paralela).
   Escolhe-se um estado e vê-se: pins/bolhas das unidades, alunos ativos,
   faturamento, churn e a proporção pagantes × agregadores. READ-ONLY sobre o M1.
   --------------------------------------------------------------------------- */

export interface ExecutiveScreenProps {
  ufs: string[]
  uf: string
  onUf: (uf: string) => void
}

export default function ExecutiveScreen({ ufs, uf, onUf }: ExecutiveScreenProps) {
  const [dados, setDados] = useState<ExecutivaPayload | null>(null)
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  // Competência selecionada (YYYY-MM); vazio = mais recente (default do backend).
  const [mes, setMes] = useState('')

  // Trocar de estado volta para a competência mais recente.
  useEffect(() => setMes(''), [uf])

  useEffect(() => {
    if (!uf) {
      setDados(null)
      return
    }
    let vivo = true
    setCarregando(true)
    setErro(null)
    api
      .executiva(uf, mes || undefined)
      .then((d) => {
        if (vivo) setDados(d)
      })
      .catch((e: ApiError) => {
        if (vivo) {
          setErro(e.message)
          setDados(null)
        }
      })
      .finally(() => {
        if (vivo) setCarregando(false)
      })
    return () => {
      vivo = false
    }
  }, [uf, mes])

  if (!uf) return <ExecLanding ufs={ufs} onUf={onUf} />

  return (
    <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column' }}>
      {dados && (
        <ExecMap unidades={dados.unidades} centro={dados.centro} iconeUltra={dados.ultra_icon} />
      )}

      <header
        style={{
          position: 'relative',
          zIndex: 10,
          margin: '16px 16px 0',
          padding: '9px 12px',
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          background: 'var(--surf-chrome)',
          border: '1px solid var(--line-soft)',
          borderRadius: 'var(--r-xl)',
          backdropFilter: 'blur(14px)',
          flexWrap: 'wrap',
        }}
      >
        <h1 style={{ font: '600 14px/1 var(--f-ui)', letterSpacing: '-.01em', color: 'var(--tx-max)', margin: 0 }}>
          Rede Ultra
        </h1>
        <span aria-hidden style={{ width: 1, height: 20, background: 'var(--line-mid)' }} />
        <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span className="num" style={{ font: '500 11px/1 var(--f-num)', color: 'var(--tx-muted)' }}>
            ESTADO
          </span>
          <Select
            label="Estado"
            value={uf}
            onChange={onUf}
            maxWidth={74}
            options={ufs.map((u) => ({ value: u, label: u }))}
          />
        </label>
        {dados && dados.meses.length > 0 && (
          <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span className="num" style={{ font: '500 11px/1 var(--f-num)', color: 'var(--tx-muted)' }}>
              PERÍODO
            </span>
            <Select
              label="Competência analisada"
              value={dados.mes ?? ''}
              onChange={setMes}
              maxWidth={130}
              options={dados.meses.map((m) => ({ value: m, label: labelMes(m) }))}
            />
          </label>
        )}
        {dados?.referencia && (
          <span className="num" style={{ font: '500 11px/1 var(--f-num)', color: 'var(--tx-sub)' }}>
            até {dados.referencia} · vs {dados.referencia_m1} (M-1)
          </span>
        )}
        <div style={{ flex: 1 }} />
        {dados && (
          <span style={{ font: '400 11.5px/1 var(--f-ui)', color: 'var(--tx-sub)' }}>
            {dados.totais.unidades} unidades · {dados.totais.com_coordenada} no mapa · Growth API · read-only
          </span>
        )}
      </header>

      <div
        style={{
          position: 'relative',
          zIndex: 10,
          flex: 1,
          display: 'flex',
          justifyContent: 'flex-end',
          padding: '14px 16px 16px',
          minHeight: 0,
          pointerEvents: 'none',
        }}
      >
        <div style={{ pointerEvents: 'auto', display: 'flex', minHeight: 0 }}>
          {carregando && !dados ? (
            <PainelMsg>Lendo a rede Ultra em {uf}…</PainelMsg>
          ) : erro ? (
            <PainelMsg>{erro}</PainelMsg>
          ) : dados ? (
            <PainelExecutivo dados={dados} />
          ) : null}
        </div>
      </div>
    </div>
  )
}

function PainelExecutivo({ dados }: { dados: ExecutivaPayload }) {
  const t = dados.totais
  const pctPag = t.pct_pagantes ?? 0
  const pctAgr = t.pct_agregadores ?? 0

  const [ordenar, setOrdenar] = useState<OrdenarKey>('faturamento')
  const unidades = useMemo(
    () =>
      [...dados.unidades].sort(
        (a, b) =>
          ((b[ordenar] as number | null) ?? -Infinity) -
          ((a[ordenar] as number | null) ?? -Infinity),
      ),
    [dados.unidades, ordenar],
  )

  return (
    <aside
      style={{
        width: 400,
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
      <header style={{ padding: '18px 20px 14px' }}>
        <span
          style={{
            font: '600 10.5px/1 var(--f-ui)',
            letterSpacing: '.12em',
            textTransform: 'uppercase',
            color: 'var(--ac-text)',
          }}
        >
          Rede instalada · {dados.uf}
        </span>
        <h2
          className="story"
          style={{ font: '400 25px/1.15 var(--f-story)', color: 'var(--tx-max)', margin: '10px 0 0' }}
        >
          Como está a operação
        </h2>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginTop: 16 }}>
          <Kpi rotulo="Faturamento no mês" valor={brl(t.faturamento.atual, true)} metric={t.faturamento} bomSubindo destaque />
          <Kpi rotulo="Alunos ativos" valor={num(t.ativos.atual)} metric={t.ativos} bomSubindo />
          <Kpi rotulo="Churn (30 dias)" valor={pct(t.churn.atual, 1)} metric={t.churn} bomSubindo={false} modo="pp" />
          <Kpi rotulo="NPS médio" valor={num(t.nps.atual)} metric={t.nps} bomSubindo modo="pts" />
        </div>

        {/* Split pagantes × agregadores */}
        <div style={{ marginTop: 16 }}>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              font: '500 10.5px/1 var(--f-ui)',
              color: 'var(--tx-label)',
              marginBottom: 6,
            }}
          >
            <span>Pagantes {pct(pctPag, 0)}</span>
            <span>Agregadores {pct(pctAgr, 0)}</span>
          </div>
          <div style={{ display: 'flex', height: 10, borderRadius: 5, overflow: 'hidden', background: 'var(--surf-raised)' }}>
            <div style={{ width: `${pctPag}%`, background: 'var(--ac)' }} />
            <div style={{ width: `${pctAgr}%`, background: '#d94a86' }} />
          </div>
          <div style={{ display: 'flex', gap: 16, marginTop: 6 }}>
            <Legenda cor="var(--ac)" texto={`${num(t.pagantes.atual)} pagantes`} delta={t.pagantes.delta_pct} />
            <Legenda cor="#d94a86" texto={`${num(t.agregadores.atual)} agregadores`} delta={t.agregadores.delta_pct} />
          </div>
        </div>
      </header>

      <div
        style={{
          padding: '6px 14px 6px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 8,
        }}
      >
        <span style={{ font: '600 10px/1 var(--f-ui)', letterSpacing: '.08em', textTransform: 'uppercase', color: 'var(--tx-muted)' }}>
          Unidades
        </span>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ font: '500 10px/1 var(--f-ui)', color: 'var(--tx-muted)' }}>ordenar por</span>
          <Select
            label="Ordenar unidades por"
            value={ordenar}
            onChange={(v) => setOrdenar(v as OrdenarKey)}
            maxWidth={150}
            options={ORDENAR_OPCOES.map((o) => ({ value: o.value, label: o.label }))}
          />
        </label>
      </div>
      <div style={{ flex: 1, overflowY: 'auto', padding: '2px 14px 12px', display: 'flex', flexDirection: 'column', gap: 6 }}>
        {unidades.map((u, i) => (
          <div
            key={`${u.nome}-${i}`}
            style={{
              padding: '10px 12px',
              border: '1px solid var(--line-soft)',
              borderRadius: 'var(--r-lg)',
              background: 'var(--surf-raised)',
              display: 'flex',
              alignItems: 'center',
              gap: 12,
            }}
          >
            <span className="num" style={{ font: '700 12px/1 var(--f-num)', color: 'var(--tx-rank)', width: 22, textAlign: 'center', flexShrink: 0 }}>
              {String(i + 1).padStart(2, '0')}
            </span>
            <span style={{ flex: 1, minWidth: 0 }}>
              <span style={{ display: 'block', font: '600 13px/1.2 var(--f-ui)', color: 'var(--tx-strong)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {u.nome}
              </span>
              <span style={{ display: 'block', font: '400 10.5px/1.2 var(--f-ui)', color: 'var(--tx-label)', marginTop: 3 }}>
                {ordenar === 'faturamento'
                  ? `${num(u.ativos)} ativos · churn ${pct(u.churn, 1)}`
                  : `${brl(u.faturamento, true)} · ${num(u.ativos)} ativos`}
              </span>
            </span>
            <span className="num" style={{ font: '700 13px/1 var(--f-num)', color: 'var(--tx-max)', flexShrink: 0 }}>
              {valorKpi(u, ordenar)}
            </span>
          </div>
        ))}
      </div>

      <footer style={{ padding: '11px 20px', borderTop: '1px solid var(--line-soft)' }}>
        <span style={{ font: '400 11px/1 var(--f-ui)', color: 'var(--tx-sub)' }}>
          Fonte: Growth API · camada paralela · read-only M1
        </span>
      </footer>
    </aside>
  )
}

function Kpi({
  rotulo,
  valor,
  metric,
  bomSubindo,
  destaque,
  modo = 'pct',
}: {
  rotulo: string
  valor: string
  metric?: ExecMetric
  bomSubindo?: boolean
  destaque?: boolean
  /** 'pct' = variação relativa (%); 'pp'/'pts' = diferença absoluta (churn/NPS). */
  modo?: 'pct' | 'pp' | 'pts'
}) {
  return (
    <div
      style={{
        padding: '11px 13px',
        borderRadius: 'var(--r-lg)',
        background: destaque ? 'var(--ac-a10)' : 'var(--surf-raised)',
        border: `1px solid ${destaque ? 'var(--ac-a24)' : 'var(--line-soft)'}`,
      }}
    >
      <div className="num" style={{ font: '700 20px/1 var(--f-num)', color: destaque ? 'var(--ac-text)' : 'var(--tx-max)' }}>
        {valor}
      </div>
      <div style={{ font: '500 10px/1 var(--f-ui)', color: 'var(--tx-label)', marginTop: 5, textTransform: 'uppercase', letterSpacing: '.04em' }}>
        {rotulo}
      </div>
      {metric && <Delta metric={metric} bomSubindo={bomSubindo ?? true} modo={modo} />}
    </div>
  )
}

/** Chip de variação vs M-1. `pct` = variação relativa; `pp`/`pts` = diferença
 *  ABSOLUTA em pontos (churn e NPS — percentual relativo confunde). Cor verde/
 *  vermelho conforme a métrica melhora ou piora. */
function Delta({
  metric,
  bomSubindo,
  modo,
}: {
  metric: ExecMetric
  bomSubindo: boolean
  modo: 'pct' | 'pp' | 'pts'
}) {
  let subiu: boolean
  let mudou: boolean
  let texto: string
  if (modo === 'pct') {
    const d = metric.delta_pct
    if (d == null) return null
    subiu = d > 0
    mudou = Math.abs(d) >= 0.05
    texto = pct(Math.abs(d), 1)
  } else {
    if (metric.atual == null || metric.m1 == null) return null
    const d = metric.atual - metric.m1
    subiu = d > 0
    mudou = Math.abs(d) >= 0.05
    texto = `${num(Math.abs(d), 1)} ${modo === 'pp' ? 'pp' : 'pts'}`
  }
  const bom = subiu === bomSubindo
  const cor = !mudou ? 'var(--tx-muted)' : bom ? 'var(--pos, #37b26b)' : 'var(--neg, #ff5a6e)'
  return (
    <div style={{ marginTop: 7, display: 'flex', alignItems: 'baseline', gap: 4 }}>
      <span className="num" style={{ font: '700 11px/1 var(--f-num)', color: cor }}>
        {!mudou ? '—' : subiu ? '▲' : '▼'} {texto}
      </span>
      <span style={{ font: '400 9px/1 var(--f-ui)', color: 'var(--tx-muted)' }}>vs M-1</span>
    </div>
  )
}

function Legenda({ cor, texto, delta }: { cor: string; texto: string; delta?: number | null }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, font: '400 10.5px/1 var(--f-ui)', color: 'var(--tx-soft)' }}>
      <span style={{ width: 8, height: 8, borderRadius: 2, background: cor }} />
      {texto}
      {delta != null && Math.abs(delta) >= 0.05 && (
        <span className="num" style={{ font: '500 9.5px/1 var(--f-num)', color: 'var(--tx-muted)' }}>
          ({delta > 0 ? '+' : '−'}
          {pct(Math.abs(delta), 1)})
        </span>
      )}
    </span>
  )
}

function PainelMsg({ children }: { children: React.ReactNode }) {
  return (
    <aside
      style={{
        width: 394,
        padding: '22px 20px',
        background: 'var(--surf-panel)',
        border: '1px solid var(--line-soft)',
        borderRadius: 'var(--r-2xl)',
        backdropFilter: 'blur(18px)',
        font: '400 13px/1.6 var(--f-ui)',
        color: 'var(--tx-narrative)',
        alignSelf: 'flex-start',
      }}
    >
      {children}
    </aside>
  )
}

function ExecLanding({ ufs, onUf }: { ufs: string[]; onUf: (uf: string) => void }) {
  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        display: 'grid',
        placeItems: 'center',
        padding: 24,
        background: 'radial-gradient(120% 90% at 50% 30%, var(--bg-lift) 0%, var(--bg-base) 72%)',
      }}
    >
      <div style={{ maxWidth: 540, textAlign: 'center' }}>
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 8,
            font: '600 11px/1 var(--f-ui)',
            letterSpacing: '.14em',
            textTransform: 'uppercase',
            color: 'var(--ac-text)',
          }}
        >
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--ac)' }} />
          Visão executiva · rede Ultra
        </span>
        <h1
          className="story"
          style={{ font: '400 42px/1.05 var(--f-story)', color: 'var(--tx-max)', margin: '18px 0 0' }}
        >
          Como está a rede, por estado
        </h1>
        <p style={{ font: '400 15px/1.6 var(--f-ui)', color: 'var(--tx-narrative)', margin: '16px auto 0', maxWidth: 440 }}>
          Escolha um <strong style={{ color: 'var(--tx-strong)' }}>estado</strong> para ver as unidades
          Ultra no mapa e os números reais — faturamento, alunos ativos, churn e a proporção entre
          pagantes e agregadores.
        </p>
        <div
          style={{
            marginTop: 30,
            display: 'inline-flex',
            alignItems: 'center',
            gap: 12,
            padding: '14px 16px',
            background: 'var(--surf-panel)',
            border: '1px solid var(--ac-a30)',
            borderRadius: 'var(--r-lg)',
            backdropFilter: 'blur(16px)',
            boxShadow: 'var(--ac-glow)',
          }}
        >
          <span style={{ font: '600 13px/1 var(--f-ui)', color: 'var(--tx-soft)' }}>Selecione um estado</span>
          {ufs.length ? (
            <Select
              label="Escolha um estado"
              value=""
              onChange={onUf}
              maxWidth={260}
              buscavel
              placeholder="Escolha…"
              options={ufs.map((u) => ({ value: u, label: u }))}
            />
          ) : (
            <span className="num" style={{ font: '500 12px/1 var(--f-num)', color: 'var(--tx-muted)' }}>
              carregando estados…
            </span>
          )}
        </div>
      </div>
    </div>
  )
}
