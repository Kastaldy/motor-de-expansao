import { useEffect, useState } from 'react'

import ExecMap from '../components/ExecMap'
import Select from '../components/Select'
import { api, ApiError } from '../lib/api'
import { brl, num, pct } from '../lib/format'
import type { ExecutivaPayload } from '../lib/types'

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

  useEffect(() => {
    if (!uf) {
      setDados(null)
      return
    }
    let vivo = true
    setCarregando(true)
    setErro(null)
    api
      .executiva(uf)
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
  }, [uf])

  if (!uf) return <ExecLanding ufs={ufs} onUf={onUf} />

  return (
    <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column' }}>
      {dados && <ExecMap unidades={dados.unidades} centro={dados.centro} />}

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
        {dados?.competencia && (
          <span className="num" style={{ font: '500 11px/1 var(--f-num)', color: 'var(--tx-sub)' }}>
            competência {dados.competencia}
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
          <Kpi rotulo="Faturamento / mês" valor={brl(t.faturamento, true)} destaque />
          <Kpi rotulo="Alunos ativos" valor={num(t.ativos)} />
          <Kpi rotulo="Churn médio" valor={pct(t.churn_medio, 2)} />
          <Kpi rotulo="NPS médio" valor={num(t.nps_medio)} />
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
            <Legenda cor="var(--ac)" texto={`${num(t.pagantes)} pagantes`} />
            <Legenda cor="#d94a86" texto={`${num(t.agregadores)} agregadores`} />
          </div>
        </div>
      </header>

      <div style={{ padding: '4px 14px 6px', font: '600 10px/1 var(--f-ui)', letterSpacing: '.08em', textTransform: 'uppercase', color: 'var(--tx-muted)' }}>
        Unidades por faturamento
      </div>
      <div style={{ flex: 1, overflowY: 'auto', padding: '2px 14px 12px', display: 'flex', flexDirection: 'column', gap: 6 }}>
        {dados.unidades.map((u, i) => (
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
                {num(u.ativos)} ativos · churn {pct(u.churn, 1)}
              </span>
            </span>
            <span className="num" style={{ font: '700 13px/1 var(--f-num)', color: 'var(--tx-max)', flexShrink: 0 }}>
              {brl(u.faturamento, true)}
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

function Kpi({ rotulo, valor, destaque }: { rotulo: string; valor: string; destaque?: boolean }) {
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
    </div>
  )
}

function Legenda({ cor, texto }: { cor: string; texto: string }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, font: '400 10.5px/1 var(--f-ui)', color: 'var(--tx-soft)' }}>
      <span style={{ width: 8, height: 8, borderRadius: 2, background: cor }} />
      {texto}
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
