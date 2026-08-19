import { useState } from 'react'

import { num } from '../lib/format'
import type { PontoCensoDetalhe, PontoConcorrencia } from '../lib/types'

/**
 * "Detalhamento dos dados" — os numeros BRUTOS da area.
 *
 * SAIU DAQUI a estatistica descritiva (minimo, mediana e maximo por setor): "nao faz
 * sentido o usuario ver isso" (Juan, 2026-08-12). Era leitura de analista — quem escolhe
 * imovel quer o dado CONCRETO: em que setor o imovel caiu, quanto do raio o IBGE cobre e
 * quem sao os concorrentes, com suas distancias. Amplitude entre setores interessa a quem
 * audita o motor, nao a quem decide abertura.
 *
 * Nenhum numero e' derivado aqui: tudo vem calculado do `/api/ponto`.
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
