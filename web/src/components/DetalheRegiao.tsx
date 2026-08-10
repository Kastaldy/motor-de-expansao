import { useState } from 'react'

import { num } from '../lib/format'
import type { PontoCensoDetalhe, PontoConcorrencia, PontoDistribuicao } from '../lib/types'

/**
 * "Detalhamento dos dados" — os numeros BRUTOS da area.
 *
 * A ficha mostra medias. Este bloco mostra o que esta POR TRAS delas: setor a setor,
 * o minimo, a mediana e o maximo do que o raio contem.
 *
 * POR QUE ISSO IMPORTA. Medido na Av. Paulista: a renda per capita media do raio e'
 * R$ 5.838, mas os 331 setores com medicao vao de R$ 780 a R$ 25.272 — 32x de
 * amplitude dentro de 1 km. Duas esquinas do mesmo raio sao negocios diferentes, e a
 * media sozinha esconde exatamente isso.
 *
 * Nenhum numero e' derivado aqui: min, mediana e maximo vem calculados do
 * `/api/ponto`, sobre os setores que o motor intersectou.
 */
export default function DetalheRegiao({
  detalhe,
  concorrencia,
}: {
  detalhe: PontoCensoDetalhe
  concorrencia: PontoConcorrencia
}) {
  const [aberto, setAberto] = useState(false)
  const sp = detalhe.setor_do_ponto
  const dist = detalhe.distribuicao

  return (
    <div
      style={{
        border: '1px solid var(--line-soft)',
        borderRadius: 'var(--r-md)',
        background: 'var(--surf-raised)',
        overflow: 'hidden',
      }}
    >
      <button
        type="button"
        onClick={() => setAberto((v) => !v)}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 8,
          padding: '9px 11px',
          background: 'transparent',
          border: 0,
          color: 'var(--tx-soft)',
          font: '600 11.5px/1 var(--f-ui)',
          textAlign: 'left',
        }}
      >
        Detalhamento dos dados
        <span aria-hidden style={{ color: 'var(--tx-muted)' }}>{aberto ? '−' : '+'}</span>
      </button>

      {aberto && (
        <div style={{ padding: '0 11px 12px', display: 'grid', gap: 16 }}>
          {/* ---- Setor a setor: o que a média esconde ---- */}
          <div style={{ display: 'grid', gap: 6 }}>
            <Titulo>Setor a setor, dentro do raio</Titulo>
            <p style={{ font: '400 11px/1.5 var(--f-ui)', color: 'var(--tx-sub)', margin: 0 }}>
              O raio tem {num(detalhe.n_setores)} setores censitários. Estes são os
              extremos e a mediana de cada leitura — a média da ficha fica no meio disso.
            </p>
            <div style={{ display: 'grid', gap: 3, marginTop: 4 }}>
              <Cabecalho />
              <LinhaDist rotulo="Renda per capita" d={dist.renda_per_capita} prefixo="R$ " />
              <LinhaDist rotulo="Score socioeconômico" d={dist.score} casas={1} />
              <LinhaDist rotulo="População do setor" d={dist.populacao} />
              <LinhaDist rotulo="Densidade" d={dist.densidade_hab_km2} sufixo=" hab/km²" />
            </div>
          </div>

          {/* ---- O setor do ponto ---- */}
          <div style={{ display: 'grid', gap: 4 }}>
            <Titulo>O setor onde o imóvel está</Titulo>
            {sp.encontrado ? (
              <>
                <Linha rotulo="Código do setor" valor={sp.cod_setor ?? '—'} mono />
                <Linha rotulo="Renda per capita" valor={`R$ ${num(sp.renda_per_capita)}`} />
                <Linha rotulo="Score socioeconômico" valor={num(sp.score, 1)} />
                <Linha rotulo="Densidade" valor={`${num(sp.densidade_hab_km2)} hab/km²`} />
                <Linha rotulo="Bairro / distrito" valor={sp.bairro ?? sp.distrito ?? '—'} />
              </>
            ) : (
              <p style={{ font: '400 11.5px/1.5 var(--f-ui)', color: 'var(--tx-muted)', margin: 0 }}>
                O ponto não caiu dentro de nenhum setor da malha — acontece em água, orla
                e setores com geometria inválida. Os números do raio seguem valendo.
              </p>
            )}
          </div>

          {/* ---- Área e densidade ---- */}
          <div style={{ display: 'grid', gap: 4 }}>
            <Titulo>Área e densidade</Titulo>
            <Linha rotulo="Área do círculo" valor={`${num(detalhe.area_circulo_km2, 2)} km²`} />
            <Linha
              rotulo="Área com setor do IBGE"
              valor={`${num(detalhe.area_intersectada_km2, 2)} km²`}
              nota="o IBGE não cobre água nem vazio"
            />
            <Linha
              rotulo="Densidade sobre o círculo"
              valor={`${num(detalhe.densidade_fixa_hab_km2)} hab/km²`}
            />
            <Linha
              rotulo="Densidade sobre a área válida"
              valor={`${num(detalhe.densidade_valida_hab_km2)} hab/km²`}
              nota="é esta que a ficha mostra"
            />
            <Linha rotulo="Score médio do raio" valor={num(detalhe.score_medio_raio, 1)} />
            <Linha rotulo="Melhor setor do raio" valor={num(detalhe.score_max_raio, 1)} />
          </div>

          {/* ---- Concorrentes ---- */}
          {concorrencia.disponivel && concorrencia.lista.length > 0 && (
            <div style={{ display: 'grid', gap: 4 }}>
              <Titulo>Concorrentes no raio ({concorrencia.lista.length})</Titulo>
              {concorrencia.lista.map((c, i) => (
                <Linha
                  key={`${c.rede}-${i}`}
                  rotulo={c.rede ?? 'rede não identificada'}
                  valor={`${num(c.dist_km, 2)} km`}
                />
              ))}
            </div>
          )}

          {detalhe.data_referencia && (
            <p style={{ font: '400 10.5px/1.4 var(--f-ui)', color: 'var(--tx-sub)', margin: 0 }}>
              Fonte: Censo 2022 do IBGE · {detalhe.data_referencia}
            </p>
          )}
        </div>
      )}
    </div>
  )
}

function Titulo({ children }: { children: React.ReactNode }) {
  return (
    <span
      style={{
        font: '600 10.5px/1 var(--f-num)',
        textTransform: 'uppercase',
        letterSpacing: '.07em',
        color: 'var(--tx-muted)',
      }}
    >
      {children}
    </span>
  )
}

function Cabecalho() {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '1fr repeat(3, minmax(58px, auto))',
        gap: 10,
        paddingBottom: 3,
      }}
    >
      <span />
      {['mínimo', 'mediana', 'máximo'].map((t) => (
        <span
          key={t}
          style={{
            font: '500 9.5px/1 var(--f-num)',
            color: 'var(--tx-sub)',
            textAlign: 'right',
            textTransform: 'uppercase',
            letterSpacing: '.05em',
          }}
        >
          {t}
        </span>
      ))}
    </div>
  )
}

function LinhaDist({
  rotulo,
  d,
  prefixo = '',
  sufixo = '',
  casas = 0,
}: {
  rotulo: string
  d: PontoDistribuicao | null
  prefixo?: string
  sufixo?: string
  casas?: number
}) {
  if (!d) {
    return (
      <div style={{ display: 'flex', gap: 10, padding: '4px 0' }}>
        <span style={{ font: '400 11.5px/1.4 var(--f-ui)', color: 'var(--tx-off)' }}>
          {rotulo}
        </span>
        <span style={{ font: '400 11px/1.4 var(--f-ui)', color: 'var(--tx-off)' }}>
          sem medição nos setores
        </span>
      </div>
    )
  }
  const fmt = (v: number | null) => (v == null ? num(v) : `${prefixo}${num(v, casas)}${sufixo}`)
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '1fr repeat(3, minmax(58px, auto))',
        gap: 10,
        padding: '4px 0',
        borderBottom: '1px solid var(--line-soft)',
      }}
    >
      <span style={{ font: '400 11.5px/1.4 var(--f-ui)', color: 'var(--tx-soft)' }}>
        {rotulo}
      </span>
      {[d.min, d.p50, d.max].map((v, i) => (
        <span
          key={i}
          className="num"
          style={{
            // A MEDIANA em destaque: e' o valor tipico do raio, e os extremos existem
            // para dar a amplitude em volta dela.
            font: `${i === 1 ? 700 : 500} 11.5px/1.4 var(--f-num)`,
            color: i === 1 ? 'var(--tx-max)' : 'var(--tx-soft)',
            textAlign: 'right',
            fontVariantNumeric: 'tabular-nums',
          }}
        >
          {fmt(v)}
        </span>
      ))}
    </div>
  )
}

function Linha({
  rotulo,
  valor,
  nota,
  mono,
}: {
  rotulo: string
  valor: string
  nota?: string
  mono?: boolean
}) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'baseline',
        gap: 10,
        padding: '4px 0',
        borderBottom: '1px solid var(--line-soft)',
      }}
    >
      <span style={{ font: '400 11.5px/1.4 var(--f-ui)', color: 'var(--tx-soft)', flexShrink: 0 }}>
        {rotulo}
      </span>
      {nota ? (
        <span
          style={{ font: '400 10px/1.3 var(--f-ui)', color: 'var(--tx-sub)', flex: 1, minWidth: 0 }}
        >
          {nota}
        </span>
      ) : (
        <span style={{ flex: 1 }} />
      )}
      <span
        className={mono ? 'num' : undefined}
        style={{
          font: `${mono ? 500 : 600} 11.5px/1.4 ${mono ? 'var(--f-num)' : 'var(--f-ui)'}`,
          color: 'var(--tx-max)',
          textAlign: 'right',
          fontVariantNumeric: 'tabular-nums',
          wordBreak: mono ? 'break-all' : 'normal',
        }}
      >
        {valor}
      </span>
    </div>
  )
}
