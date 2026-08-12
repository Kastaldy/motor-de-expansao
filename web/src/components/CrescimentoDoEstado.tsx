import { useState } from 'react'

import { Chip } from './primitives'
import { num } from '../lib/format'
import type { CrescimentoEstado } from '../lib/types'

/**
 * "Como o estado inteiro esta indo" — bloco proprio, ACIMA do funil.
 *
 * POR QUE NAO E' O PASSO 4. O passo 4 do funil descreve as cidades que sobreviveram
 * aos filtros 1-3, ou seja, so' white space: em GO ele lista 10 cidades. Este bloco
 * olha as 246 do estado. Sao respostas a perguntas diferentes, e le-lo como se fosse
 * o mesmo ranking e' o erro facil — por isso ele nao entra na fila de passos, e o
 * texto diz de onde vem.
 *
 * CAGED CONTRA A MEDIANA DA PROPRIA UF, sempre. O percentual sozinho nao tem escala;
 * o que a lista mostra e' a posicao de cada cidade contra a mediana do estado, que
 * viaja no payload e aparece no cabecalho para o operador saber contra o que esta
 * lendo. Comparar cidades de UFs diferentes por este numero seria a leitura nacional
 * que a regra proibe.
 *
 * Recolhido por padrao: a resposta da tela continua sendo o funil.
 */
export default function CrescimentoDoEstado({ dados }: { dados: CrescimentoEstado }) {
  const [aberto, setAberto] = useState(false)

  return (
    <div
      style={{
        margin: '0 0 12px',
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
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          Crescimento do estado
          {dados.mediana_uf != null && (
            <Chip>mediana {num(dados.mediana_uf, 1)}%</Chip>
          )}
        </span>
        <span aria-hidden style={{ color: 'var(--tx-muted)' }}>{aberto ? '−' : '+'}</span>
      </button>

      {aberto && (
        <div style={{ padding: '0 11px 12px', display: 'grid', gap: 10 }}>
          <p style={{ font: '400 11px/1.5 var(--f-ui)', color: 'var(--tx-sub)', margin: 0 }}>
            Emprego formal (CAGED) das{' '}
            <strong style={{ color: 'var(--tx-soft)' }}>
              {num(dados.n_municipios_com_medicao)}
            </strong>{' '}
            cidades com medição, de {num(dados.n_municipios_uf)} no estado — o estado
            inteiro, não só o que passou nos filtros do funil. Cada posição é lida contra
            a mediana da própria UF.
            {dados.n_fora_do_piso > 0 && (
              <>
                {' '}
                {/* Corte declarado: silenciar quantos sairam faria a lista parecer
                    completa, e o piso e' justamente o que impede que um municipio de
                    poucas centenas de empregos lidere por variacao percentual. */}
                {num(dados.n_fora_do_piso)} cidades abaixo de {num(dados.pop_minima)}{' '}
                habitantes ficam fora do ranking.
              </>
            )}
          </p>

          <div style={{ display: 'grid', gap: 5 }}>
            {dados.itens.map((it) => (
              <div
                key={`${it.rank}-${it.titulo}`}
                style={{
                  display: 'flex',
                  alignItems: 'baseline',
                  gap: 8,
                  padding: '5px 0',
                  borderBottom: '1px solid var(--line-soft)',
                }}
              >
                <span
                  className="num"
                  style={{
                    font: '600 10px/1 var(--f-num)',
                    color: 'var(--tx-rank)',
                    width: 20,
                    flexShrink: 0,
                  }}
                >
                  {it.rank}º
                </span>
                <span
                  style={{
                    flex: 1,
                    minWidth: 0,
                    font: '500 12px/1.3 var(--f-ui)',
                    color: 'var(--tx-strong)',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {it.titulo}
                </span>
                {it.tag && (
                  <span
                    style={{
                      font: '500 9.5px/1 var(--f-ui)',
                      color: 'var(--tx-sub)',
                      flexShrink: 0,
                    }}
                  >
                    {it.tag}
                  </span>
                )}
                <span
                  className="num"
                  style={{
                    font: '700 12px/1 var(--f-num)',
                    color: 'var(--tx-max)',
                    flexShrink: 0,
                    fontVariantNumeric: 'tabular-nums',
                  }}
                >
                  {num(it.valor)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
