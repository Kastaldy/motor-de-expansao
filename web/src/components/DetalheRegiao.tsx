import { useState } from 'react'

import { num } from '../lib/format'
import type { PontoCensoDetalhe, PontoConcorrencia } from '../lib/types'

/**
 * "Detalhamento dos dados" — o rastro por tras dos KPIs da regiao.
 *
 * A ficha resume seis numeros; o motor calcula bem mais. Isto abre o resto: as duas
 * AREAS, as duas DENSIDADES, o score do raio contra o do setor do ponto, e COMO a
 * renda foi construida (metodo, uplift, fator temporal, data de referencia).
 *
 * RECOLHIDO por padrao. Quem decide quer os seis numeros; quem AUDITA quer os vinte,
 * e obrigar o primeiro a rolar por cima do segundo torna a ficha ilegivel para os dois.
 *
 * Nenhum numero e' derivado aqui — todos vem do `/api/ponto`, que por sua vez le o
 * motor censitario. A tela so' agrupa e explica.
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
  const r = detalhe.renda

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
        <div style={{ padding: '0 11px 12px', display: 'grid', gap: 14 }}>
          <Grupo titulo="Como o raio foi medido">
            <Linha rotulo="Método" valor={detalhe.metodo ?? '—'} mono />
            <Linha rotulo="Área do círculo" valor={`${num(detalhe.area_circulo_km2, 2)} km²`} />
            <Linha
              rotulo="Área com setor do IBGE"
              valor={`${num(detalhe.area_intersectada_km2, 2)} km²`}
              nota="o IBGE não cobre água nem vazio"
            />
          </Grupo>

          <Grupo titulo="As duas densidades">
            <Linha
              rotulo="Sobre o círculo inteiro"
              valor={`${num(detalhe.densidade_fixa_hab_km2)} hab/km²`}
              nota="divide por πr², inclui água e vazio"
            />
            <Linha
              rotulo="Sobre a área válida"
              valor={`${num(detalhe.densidade_valida_hab_km2)} hab/km²`}
              nota="é esta que a ficha mostra"
            />
          </Grupo>

          <Grupo titulo="Score no raio, e no setor do ponto">
            <Linha rotulo="Média dos setores" valor={num(detalhe.score_medio_raio, 1)} />
            <Linha rotulo="Melhor setor do raio" valor={num(detalhe.score_max_raio, 1)} />
            <Linha
              rotulo="Setor que contém o ponto"
              valor={num(sp.score, 1)}
              // A diferenca entre "a regiao" e "a esquina" e' o que decide um imovel.
              nota="a esquina pode ser pior ou melhor que a região"
            />
          </Grupo>

          <Grupo titulo="O setor do ponto">
            {sp.encontrado ? (
              <>
                <Linha rotulo="Código do setor" valor={sp.cod_setor ?? '—'} mono />
                <Linha rotulo="Renda per capita" valor={`R$ ${num(sp.renda_per_capita)}`} />
                <Linha rotulo="Densidade" valor={`${num(sp.densidade_hab_km2)} hab/km²`} />
                <Linha rotulo="Bairro / distrito" valor={sp.bairro ?? sp.distrito ?? '—'} />
              </>
            ) : (
              <p style={{ font: '400 11.5px/1.5 var(--f-ui)', color: 'var(--tx-muted)', margin: 0 }}>
                O ponto não caiu dentro de nenhum setor da malha — acontece em água, orla
                e setores com geometria inválida. Os números do raio seguem valendo.
              </p>
            )}
          </Grupo>

          <Grupo titulo="Como a renda foi construída">
            <Linha rotulo="Per capita" valor={r.metodo_per_capita ?? '—'} mono />
            <Linha rotulo="Domiciliar" valor={r.metodo_domiciliar ?? '—'} mono />
            <Linha
              rotulo="Uplift domiciliar"
              valor={num(r.uplift_domiciliar, 3)}
              nota="per capita × moradores × composição"
            />
            <Linha rotulo="Fator temporal" valor={num(r.fator_temporal, 3)} />
            <Linha rotulo="Referência" valor={r.data_referencia ?? '—'} />
            <Linha
              rotulo="Uplift lido de"
              valor={[r.uf_uplift, r.cod_municipio_uplift].filter(Boolean).join(' · ') || '—'}
              mono
            />
          </Grupo>

          {concorrencia.disponivel && concorrencia.lista.length > 0 && (
            <Grupo titulo={`Concorrentes no raio (${concorrencia.lista.length})`}>
              {concorrencia.lista.map((c, i) => (
                <Linha
                  key={`${c.rede}-${i}`}
                  rotulo={c.rede ?? 'rede não identificada'}
                  valor={`${num(c.dist_km, 2)} km`}
                />
              ))}
            </Grupo>
          )}
        </div>
      )}
    </div>
  )
}

function Grupo({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'grid', gap: 4 }}>
      <span
        style={{
          font: '600 10.5px/1 var(--f-num)',
          textTransform: 'uppercase',
          letterSpacing: '.07em',
          color: 'var(--tx-muted)',
          marginBottom: 3,
        }}
      >
        {titulo}
      </span>
      {children}
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
      {nota && (
        <span
          style={{
            font: '400 10px/1.3 var(--f-ui)',
            color: 'var(--tx-sub)',
            flex: 1,
            minWidth: 0,
          }}
        >
          {nota}
        </span>
      )}
      {!nota && <span style={{ flex: 1 }} />}
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
