import type { ReactNode } from 'react'

import { brl, num } from '../lib/format'
import { ACC, ACC_GLOW, ACC_ON, ACC_TX, corTipo, custoOcup, labelTipo, rsM2 } from '../lib/imovel'
import type { Oportunidade } from '../lib/types'
import IconeTipo from './IconeTipo'
import { Botao, Eyebrow } from './primitives'

/**
 * O DETALHE de uma oportunidade imobiliaria, para viver dentro da janela flutuante
 * do Mapa Territorial (aberta pelo pin da camada de imoveis ou pela secao
 * "Imoveis disponiveis aqui" da ficha do hexagono).
 *
 * E' um RESUMO deliberado, nao a Ficha inteira da aba: aqui o operador esta' lendo o
 * territorio e quer conferir o imovel sem trocar de tela. Os quatro numeros sao os
 * MESMOS do ranking da aba (Aluguel, Custo de ocupacao, Projecao de faturamento,
 * Area); o estudo completo (scatter, mercado, censo, dossie) fica na aba, alcancada
 * pelo botao magenta — o caminho INVERSO do "Ver no Mapa Territorial" que ja existe la'.
 */
export default function FichaImovel({
  op,
  onVerNaAba,
}: {
  op: Oportunidade
  /** Abre a aba de Oportunidades Imobiliarias ja focada NESTE imovel. Ausente = sem botao. */
  onVerNaAba?: () => void
}) {
  const tint = corTipo(op.tipo)
  const r = rsM2(op)
  const ocupacao = custoOcup(op)
  return (
    <div style={{ display: 'grid', gap: 16 }}>
      <div>
        <Eyebrow dot cor={ACC}>Oportunidade imobiliária</Eyebrow>
        <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 11 }}>
          <span
            style={{
              width: 44,
              height: 44,
              borderRadius: 'var(--r-md)',
              display: 'grid',
              placeItems: 'center',
              color: tint,
              background: `${tint}1f`,
              flexShrink: 0,
            }}
          >
            <IconeTipo tipo={op.tipo} tamanho={22} />
          </span>
          <div style={{ minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 7, flexWrap: 'wrap' }}>
              <span style={{ width: 7, height: 7, borderRadius: 2, background: tint, flexShrink: 0 }} />
              <span style={{ font: '400 10.5px/1 var(--f-ui)', color: 'var(--tx-sub)' }}>
                {labelTipo(op.tipo)} para locação
              </span>
            </div>
            <div style={{ marginTop: 4, font: '600 14px/1.3 var(--f-ui)', color: 'var(--tx-max)' }}>
              {op.titulo}
            </div>
          </div>
        </div>
        <div
          className="num"
          style={{ marginTop: 8, font: '400 10.5px/1.4 var(--f-num)', color: 'var(--tx-sub)' }}
        >
          {op.hex_id}
          {op.first_seen ? ` · listado desde ${op.first_seen}` : ''}
        </div>
      </div>

      {/* Os 4 numeros do ranking da aba, com as MESMAS formulas e notas (a ordem aqui
          prioriza custo -> retorno -> tamanho, o pedido do Felipe para o mapa). */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '14px 18px',
          paddingTop: 14,
          borderTop: '1px solid var(--line-soft)',
        }}
      >
        <Stat
          label="Aluguel"
          valor={op.aluguel == null ? '—' : num(op.aluguel)}
          unidade="R$/mês"
          nota={r != null ? `R$ ${num(r, 0)}/m²` : undefined}
        />
        <Stat
          label="Custo de ocupação"
          valor={ocupacao > 0 ? num(ocupacao) : '—'}
          unidade="R$/mês"
          nota="com IPTU e condomínio"
        />
        <Stat
          label="Projeção de faturamento"
          valor={op.fat_proj == null ? '—' : brl(op.fat_proj, true)}
          unidade="/mês"
          cor="var(--pos-text)"
          nota={
            op.alunos_p50 != null
              ? `${num(op.alunos_p50)} alunos (p50/m²)`
              : 'sem base de m² p/ estimar'
          }
        />
        <Stat
          label="Área"
          valor={op.area == null ? '—' : num(op.area)}
          unidade="m²"
          nota={labelTipo(op.tipo)}
        />
      </div>

      {/* Apoio: composicao do custo e a leitura do hexagono em que o imovel cai.
          Ausente = '—', nunca 0 (regra da casa: ausencia nao afirma). */}
      <div style={{ display: 'grid', gap: 6, paddingTop: 12, borderTop: '1px solid var(--line-soft)' }}>
        <LinhaDet rotulo="IPTU" valor={op.iptu == null ? '—' : brl(op.iptu)} />
        <LinhaDet rotulo="Condomínio" valor={op.condominio == null ? '—' : brl(op.condominio)} />
        <LinhaDet
          rotulo="Residual do hexágono"
          valor={op.residual == null ? '—' : `${num(op.residual, 0)} / 100`}
        />
        <LinhaDet
          rotulo="Mercado que sobra"
          valor={op.residual_total == null ? '—' : `${num(op.residual_total)} alunos`}
        />
      </div>

      <div style={{ display: 'grid', gap: 10 }}>
        {onVerNaAba && (
          <Botao
            onClick={onVerNaAba}
            title="Abre a aba de Oportunidades Imobiliárias com este imóvel selecionado"
            style={{
              width: '100%',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 8,
              background: ACC,
              color: ACC_ON,
              boxShadow: ACC_GLOW,
            }}
          >
            Ver na aba de imóveis →
          </Botao>
        )}
        {op.url && (
          <a
            href={op.url}
            target="_blank"
            rel="noreferrer"
            style={{
              font: '600 11.5px/1 var(--f-ui)',
              color: ACC_TX,
              textDecoration: 'underline',
              justifySelf: 'start',
            }}
          >
            Abrir o anúncio original ↗
          </a>
        )}
      </div>
    </div>
  )
}

/** Big number no molde do `HeroStat` da aba (label mono uppercase + valor 22px). */
function Stat({
  label,
  valor,
  unidade,
  nota,
  cor,
}: {
  label: string
  valor: string
  unidade?: string
  nota?: ReactNode
  cor?: string
}) {
  return (
    <div style={{ minWidth: 0 }}>
      <div
        className="num"
        style={{
          font: '400 10px/1 var(--f-num)',
          letterSpacing: '.1em',
          textTransform: 'uppercase',
          color: cor ?? 'var(--tx-sub)',
          marginBottom: 6,
        }}
      >
        {label}
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 5, whiteSpace: 'nowrap' }}>
        <span
          className="num"
          style={{ font: '500 22px/1 var(--f-num)', color: cor ?? 'var(--tx-max)', whiteSpace: 'nowrap' }}
        >
          {valor}
        </span>
        {unidade && <span style={{ font: '400 12px/1 var(--f-ui)', color: 'var(--tx-sub)' }}>{unidade}</span>}
      </div>
      {nota && (
        <div style={{ font: '400 10.5px/1.3 var(--f-ui)', color: 'var(--tx-sub)', marginTop: 5 }}>{nota}</div>
      )}
    </div>
  )
}

function LinhaDet({ rotulo, valor }: { rotulo: string; valor: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 14 }}>
      <span style={{ font: '400 11.5px/1 var(--f-ui)', color: 'var(--tx-label)' }}>{rotulo}</span>
      <span className="num" style={{ font: '500 12px/1 var(--f-num)', color: 'var(--tx-soft)' }}>
        {valor}
      </span>
    </div>
  )
}
