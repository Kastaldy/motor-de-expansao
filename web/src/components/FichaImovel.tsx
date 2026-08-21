import { useEffect, useState } from 'react'

import { brl, num } from '../lib/format'
import {
  ACC,
  ACC_GLOW,
  ACC_ON,
  ACC_TX,
  ALUGUEL_PCT_EXCECAO,
  ALUGUEL_PCT_IDEAL,
  ALUGUEL_PCT_TETO,
  classeAluguelFat,
  corTipo,
  custoOcup,
  labelFaixa,
  labelTipo,
  pctAluguelFat,
  rsM2,
} from '../lib/imovel'
import { alternarVisita, lerVisitas } from '../lib/visitas'
import type { Oportunidade } from '../lib/types'
import IconeTipo from './IconeTipo'
import { CardPainel, LinhaTabela, Pill, TituloSecao } from './PecasPainel'
import { Botao } from './primitives'

/**
 * O DETALHE de uma oportunidade imobiliaria, para viver dentro da janela flutuante
 * do Mapa Territorial (aberta pelo pin da camada de imoveis ou pela secao
 * "Imoveis disponiveis aqui" da ficha do hexagono).
 *
 * DESENHO: porte do painel direito do design "Paineis do Hexagono" (Claude Design,
 * 2026-08-21), adaptado aos tokens/fontes do piloto — hero com o tipo, veredito de
 * custo x retorno, quatro numeros do ranking, composicao do custo com mini-barras,
 * ficha em linhas e o encaixe no hexagono. Pecas de forma em `PecasPainel`.
 *
 * REGUA, NAO OLHO: o veredito compara o ALUGUEL com o faturamento projetado pela
 * regua publicada do modelo de viabilidade (ideal 15% · teto 20% · excecao 30% —
 * `classeAluguelFat` em lib/imovel, os mesmos clusters do simulador). O design de
 * referencia trazia um "teto de 18%" que nao existe no modelo — nao entrou. Linhas
 * da ficha mostram SO campo servido pelo backend; ausente = '—', nunca zero.
 *
 * O estudo completo (scatter, mercado, censo, dossie) fica na aba, alcancada pelo
 * botao magenta — o caminho INVERSO do "Ver no Mapa Territorial" que ja existe la.
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
  const pct = pctAluguelFat(op)
  const cls = classeAluguelFat(pct)
  const dias = diasNoAr(op.first_seen)

  /* Marcador "para visita": a MESMA chave localStorage da aba (`lib/visitas`) — marcar
     aqui aparece la na proxima abertura, e vice-versa. Re-le ao trocar de imovel. */
  const [visita, setVisita] = useState(() => lerVisitas().has(op.id))
  useEffect(() => {
    setVisita(lerVisitas().has(op.id))
  }, [op.id])
  const aoAlternarVisita = () => {
    const prox = alternarVisita(lerVisitas(), op.id)
    setVisita(prox.has(op.id))
  }

  return (
    <div style={{ display: 'grid', gap: 16 }}>
      {/* ---- Hero: o tipo como identidade ---- */}
      <div>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 13 }}>
          <span
            style={{
              width: 56,
              height: 56,
              flexShrink: 0,
              borderRadius: 14,
              background: `${tint}1f`,
              display: 'grid',
              placeItems: 'center',
              color: tint,
              boxShadow: `inset 0 0 0 1px ${tint}33`,
            }}
          >
            <IconeTipo tipo={op.tipo} tamanho={28} />
          </span>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 6 }}>
              <Pill texto="Oportunidade" cor={ACC_TX} />
              <span
                className="num"
                style={{
                  font: '400 9.5px/1 var(--f-num)',
                  letterSpacing: '.1em',
                  textTransform: 'uppercase',
                  color: tint,
                }}
              >
                {labelTipo(op.tipo)} p/ locação
              </span>
            </div>
            <h2
              className="story"
              style={{ margin: 0, font: '400 22px/1.15 var(--f-story)', color: 'var(--tx-max)' }}
            >
              {op.titulo}
            </h2>
            <div style={{ marginTop: 5, font: '400 12px/1.35 var(--f-ui)', color: 'var(--tx-narrative)' }}>
              {[op.bairro, `${op.municipio}/${op.uf}`].filter(Boolean).join(' · ')}
            </div>
          </div>
        </div>
        <div
          className="num"
          style={{
            marginTop: 12,
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            flexWrap: 'wrap',
            font: '400 9.5px/1 var(--f-num)',
            color: 'var(--tx-sub)',
          }}
        >
          <span
            style={{
              padding: '4px 8px',
              borderRadius: 6,
              background: 'var(--surf-raised)',
              border: '1px solid var(--line-soft)',
            }}
          >
            {op.hex_id}
          </span>
          {op.first_seen && <span>listado {op.first_seen}</span>}
          {dias != null && (
            <>
              <span aria-hidden style={{ color: 'var(--tx-off)' }}>·</span>
              <span>{dias === 1 ? '1 dia no ar' : `${num(dias)} dias no ar`}</span>
            </>
          )}
        </div>
      </div>

      {/* ---- Veredito custo x retorno, pela régua 15/20/30 do modelo ---- */}
      {pct != null && cls && op.fat_proj != null ? (
        <CardPainel style={{ background: 'var(--surf-card)', border: '1px solid var(--line-mid)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 9 }}>
            <Pill texto={`Aluguel ${cls.rotulo}`} cor={cls.tom} />
            <span style={{ font: '400 10.5px/1.3 var(--f-ui)', color: 'var(--tx-sub)' }}>
              régua do modelo de viabilidade
            </span>
          </div>
          {/* O % É DO ALUGUEL (a régua 15/20/30 é sobre aluguel, não sobre a ocupação):
              os números em destaque são exatamente os da razão — pôr a OCUPAÇÃO no
              negrito fazia quem dividisse os dois obter outro % que o selo. A ocupação
              completa entra como oração à parte. */}
          <p style={{ margin: 0, font: '400 14px/1.5 var(--f-ui)', color: 'var(--tx-strong)' }}>
            O aluguel de <b className="num">{op.aluguel == null ? '—' : brl(op.aluguel, true)}</b>{' '}
            toma{' '}
            <b style={{ color: 'var(--tx-max)' }}>
              <span className="num">{num(pct, 1)}%</span> da receita
            </b>{' '}
            projetada de{' '}
            <b className="num" style={{ color: 'var(--pos-text)' }}>{brl(op.fat_proj, true)}</b>
            /mês
            {ocupacao > 0 && ocupacao !== op.aluguel && (
              <>
                {' '}
                — com IPTU e condomínio, a ocupação vai a{' '}
                <b className="num">{brl(ocupacao, true)}</b>
              </>
            )}
            .
          </p>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 13 }}>
            <div
              style={{
                flex: 1,
                position: 'relative',
                height: 8,
                borderRadius: 4,
                background: 'var(--surf-pending)',
              }}
            >
              <div
                style={{
                  position: 'absolute',
                  top: 0,
                  bottom: 0,
                  left: 0,
                  width: `${Math.min(100, (pct / ALUGUEL_PCT_EXCECAO) * 100)}%`,
                  background: cls.tom,
                  borderRadius: 4,
                }}
              />
              {/* As marcas da régua, na escala até a exceção (30%). */}
              {[ALUGUEL_PCT_IDEAL, ALUGUEL_PCT_TETO].map((m) => (
                <span
                  key={m}
                  aria-hidden
                  style={{
                    position: 'absolute',
                    top: -2,
                    bottom: -2,
                    left: `${(m / ALUGUEL_PCT_EXCECAO) * 100}%`,
                    width: 1,
                    background: 'var(--line-strong)',
                  }}
                />
              ))}
            </div>
            <span
              className="num"
              style={{ font: '400 10px/1 var(--f-num)', color: 'var(--tx-sub)', whiteSpace: 'nowrap' }}
            >
              máx {ALUGUEL_PCT_EXCECAO}%
            </span>
          </div>
          <div style={{ marginTop: 6, font: '400 9.5px/1.3 var(--f-ui)', color: 'var(--tx-label)' }}>
            marcas: ideal {ALUGUEL_PCT_IDEAL}% · teto {ALUGUEL_PCT_TETO}% — % do faturamento, como na Viabilidade
          </div>
        </CardPainel>
      ) : (
        <CardPainel>
          <div style={{ font: '400 12px/1.5 var(--f-ui)', color: 'var(--tx-sub)' }}>
            Sem base para comparar custo e retorno —{' '}
            {op.aluguel == null
              ? 'o anúncio não traz o aluguel.'
              : 'sem projeção de faturamento para esta área.'}
          </div>
        </CardPainel>
      )}

      {/* ---- Os 4 números do ranking da aba (mesmas fórmulas e notas) ---- */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 9 }}>
        <CardFigura
          rotulo="ALUGUEL"
          valor={op.aluguel == null ? '—' : num(op.aluguel)}
          unidade="R$/mês"
          /* A nota declara a causa CERTA: `rsM2` devolve null tanto sem área quanto sem
             aluguel — culpar a área com o aluguel ausente afirmaria uma falta que não
             existe (a área pode estar no card ao lado). */
          nota={
            op.aluguel == null
              ? 'não informado no anúncio'
              : r != null
                ? `R$ ${num(r, 0)}/m²`
                : 'sem área p/ o m²'
          }
        />
        <CardFigura
          rotulo="CUSTO DE OCUPAÇÃO"
          valor={ocupacao > 0 ? num(ocupacao) : '—'}
          unidade="R$/mês"
          nota="com IPTU e condomínio"
        />
        <CardFigura
          rotulo="PROJEÇÃO DE FATURAMENTO"
          valor={op.fat_proj == null ? '—' : brl(op.fat_proj, true)}
          unidade="/mês"
          cor="var(--pos-text)"
          nota={
            op.alunos_p50 != null
              ? `${num(op.alunos_p50)} alunos × R$ ${num(op.ticket_proj ?? 0)}`
              : 'sem base de m² p/ estimar'
          }
        />
        <CardFigura
          rotulo="ÁREA ÚTIL"
          valor={op.area == null ? '—' : num(op.area)}
          unidade="m²"
          nota={op.alunos_p50 != null ? `${num(op.alunos_p50)} alunos pelo p50` : labelTipo(op.tipo)}
        />
      </div>

      {/* ---- Composição do custo ---- */}
      <div
        style={{
          borderRadius: 14,
          background: 'var(--surf-raised)',
          border: '1px solid var(--line-soft)',
          overflow: 'hidden',
        }}
      >
        <div style={{ padding: '13px 15px 6px' }}>
          <TituloSecao titulo="Composição do custo" nota="R$/mês" gap={0} />
        </div>
        {/* Mesmas cores do CardCusto da aba: aluguel magenta, IPTU âmbar, condomínio
            neutro — as duas telas falam a mesma língua. */}
        {(
          [
            { rotulo: 'Aluguel', v: op.aluguel, cor: ACC },
            { rotulo: 'IPTU', v: op.iptu, cor: 'var(--warn-text)' },
            { rotulo: 'Condomínio', v: op.condominio, cor: 'var(--tx-rank)' },
          ] as const
        ).map((l) => {
          const fr = ocupacao > 0 && l.v != null ? Math.round((l.v / ocupacao) * 100) : 0
          return (
            <div
              key={l.rotulo}
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 52px auto',
                gap: 12,
                alignItems: 'center',
                padding: '8px 15px',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 9,
                  font: '400 12px/1.2 var(--f-ui)',
                  color: 'var(--tx-soft)',
                }}
              >
                <span
                  aria-hidden
                  style={{ width: 7, height: 7, borderRadius: 2, background: l.cor, flexShrink: 0 }}
                />
                {l.rotulo}
              </div>
              <div style={{ height: 5, borderRadius: 3, background: 'var(--surf-pending)', overflow: 'hidden' }}>
                <div style={{ height: '100%', width: `${fr}%`, background: l.cor, borderRadius: 3 }} />
              </div>
              <span
                className="num"
                style={{
                  font: '500 12px/1.2 var(--f-num)',
                  color: 'var(--tx-soft)',
                  width: 62,
                  textAlign: 'right',
                }}
              >
                {l.v == null ? '—' : num(l.v)}
              </span>
            </div>
          )
        })}
        <div
          style={{
            display: 'flex',
            alignItems: 'baseline',
            justifyContent: 'space-between',
            padding: '11px 15px',
            background: 'var(--surf-pending)',
            borderTop: '1px solid var(--line-soft)',
          }}
        >
          <span style={{ font: '400 12px/1.2 var(--f-ui)', color: 'var(--tx-narrative)' }}>
            Custo de ocupação
          </span>
          <span className="num" style={{ font: '500 15px/1 var(--f-num)', color: 'var(--tx-max)' }}>
            {ocupacao > 0 ? num(ocupacao) : '—'}
          </span>
        </div>
      </div>

      {/* ---- Ficha do imóvel: só campo servido pelo backend ---- */}
      <section>
        <TituloSecao titulo="Ficha do imóvel" gap={10} />
        <div
          style={{
            borderRadius: 13,
            background: 'var(--surf-raised)',
            border: '1px solid var(--line-soft)',
            padding: '3px 0',
          }}
        >
          <LinhaTabela rotulo="Tipo" valor={`${labelTipo(op.tipo)} para locação`} />
          <LinhaTabela
            rotulo="Operação"
            valor={op.operacao ? op.operacao.charAt(0).toUpperCase() + op.operacao.slice(1) : '—'}
          />
          <LinhaTabela rotulo="Área útil" valor={op.area == null ? '—' : `${num(op.area)} m²`} />
          <LinhaTabela rotulo="R$/m² de aluguel" valor={r == null ? '—' : `R$ ${num(r, 0)}`} />
          <LinhaTabela rotulo="Faixa M1 do hexágono" valor={labelFaixa(op.faixa) ?? '—'} />
          <LinhaTabela rotulo="Listado desde" valor={op.first_seen ?? '—'} />
        </div>
      </section>

      {/* ---- Como se encaixa no hexágono ---- */}
      <CardPainel>
        <TituloSecao titulo="Como se encaixa no hexágono" nota={op.hex_id.slice(0, 10)} />
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px 14px' }}>
          <EncaixeNum
            valor={op.residual == null ? '—' : `${num(op.residual, 0)} / 100`}
            rotulo="Residual do hexágono"
          />
          <EncaixeNum
            valor={op.residual_total == null ? '—' : num(op.residual_total)}
            rotulo="Alunos que sobram"
            tom="var(--ac-text)"
          />
          <EncaixeNum
            valor={op.alunos_p50 == null ? '—' : num(op.alunos_p50)}
            rotulo="Capacidade do imóvel (p50)"
            tom="var(--pos-text)"
          />
          <EncaixeNum
            valor={op.n_ultra == null ? '—' : num(op.n_ultra)}
            rotulo="Unidades Ultra no hex"
          />
        </div>
        {op.area != null && op.alunos_p50 != null && op.residual_total != null && (
          <p style={{ margin: '13px 0 0', font: '400 11.5px/1.5 var(--f-ui)', color: 'var(--tx-narrative)' }}>
            Os {num(op.area)} m² comportam {num(op.alunos_p50)} alunos pelo p50 —{' '}
            {op.alunos_p50 >= op.residual_total ? 'acima' : 'abaixo'} dos {num(op.residual_total)}{' '}
            ainda livres no hexágono.
          </p>
        )}
      </CardPainel>

      {/* ---- Ações ---- */}
      <div style={{ display: 'grid', gap: 9 }}>
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
        <div style={{ display: 'flex', gap: 9 }}>
          <button
            type="button"
            onClick={aoAlternarVisita}
            style={{
              ...acaoGhost,
              color: visita ? 'var(--warn-text)' : 'var(--tx-soft)',
              borderColor: visita ? 'rgba(233,192,122,.4)' : 'var(--line-mid)',
            }}
          >
            {visita ? '★ Marcado para visita' : '☆ Marcar para visita'}
          </button>
          {op.url && (
            <a href={op.url} target="_blank" rel="noreferrer" style={acaoGhost}>
              Anúncio original ↗
            </a>
          )}
        </div>
      </div>

      <div style={{ font: '400 10.5px/1.5 var(--f-ui)', color: 'var(--tx-sub)' }}>
        Faturamento projetado = alunos p50/m² × ticket
        {op.ticket_proj != null ? ` de R$ ${num(op.ticket_proj)}` : ''}. Dado agregado por{' '}
        <span className="num">hex_id</span>; o contato do corretor fica no dossiê do coletor.
      </div>
    </div>
  )
}

const acaoGhost: React.CSSProperties = {
  flex: 1,
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: 8,
  padding: '11px 12px',
  borderRadius: 12,
  background: 'var(--surf-raised)',
  border: '1px solid var(--line-mid)',
  font: '600 12px/1 var(--f-ui)',
  color: 'var(--tx-soft)',
  cursor: 'pointer',
  textDecoration: 'none',
  textAlign: 'center',
}

/** Card de número do design: rótulo mono uppercase, valor 20px, nota. */
function CardFigura({
  rotulo,
  valor,
  unidade,
  nota,
  cor,
}: {
  rotulo: string
  valor: string
  unidade?: string
  nota?: string
  cor?: string
}) {
  return (
    <div
      style={{
        padding: '12px 13px',
        borderRadius: 13,
        background: 'var(--surf-raised)',
        border: '1px solid var(--line-soft)',
        minWidth: 0,
      }}
    >
      <div
        className="num"
        style={{
          font: '400 9px/1.3 var(--f-num)',
          letterSpacing: '.1em',
          color: cor ?? 'var(--tx-sub)',
          marginBottom: 8,
        }}
      >
        {rotulo}
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 4, whiteSpace: 'nowrap' }}>
        <span className="num" style={{ font: '500 20px/1 var(--f-num)', color: cor ?? 'var(--tx-max)' }}>
          {valor}
        </span>
        {unidade && <span style={{ font: '400 11px/1 var(--f-ui)', color: 'var(--tx-sub)' }}>{unidade}</span>}
      </div>
      {nota && (
        <div style={{ font: '400 10.5px/1.3 var(--f-ui)', color: 'var(--tx-sub)', marginTop: 5 }}>
          {nota}
        </div>
      )}
    </div>
  )
}

function EncaixeNum({ valor, rotulo, tom }: { valor: string; rotulo: string; tom?: string }) {
  return (
    <div>
      <div className="num" style={{ font: '500 15px/1 var(--f-num)', color: tom ?? 'var(--tx-max)' }}>
        {valor}
      </div>
      <div style={{ font: '400 10.5px/1.3 var(--f-ui)', color: 'var(--tx-sub)', marginTop: 4 }}>
        {rotulo}
      </div>
    </div>
  )
}

/** Dias corridos desde o first_seen, por DATA-CALENDÁRIO local (aritmética de exibição).
 *  Não usa `Date.parse`: "AAAA-MM-DD" é interpretado como meia-noite UTC, e em BRT
 *  (UTC-3) um anúncio de ontem daria "0 dias no ar" até ~21h — contradizendo o
 *  "listado {data}" ao lado. */
function diasNoAr(firstSeen: string | null): number | null {
  if (!firstSeen) return null
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(firstSeen)
  if (!m) return null
  const listado = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]))
  const agora = new Date()
  const hoje = new Date(agora.getFullYear(), agora.getMonth(), agora.getDate())
  const dias = Math.round((hoje.getTime() - listado.getTime()) / 86_400_000)
  return Number.isFinite(dias) && dias >= 0 ? dias : null
}
