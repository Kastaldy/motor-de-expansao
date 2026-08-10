import { useMemo, useState } from 'react'

import Select from './Select'
import TabelaComparacao from './TabelaComparacao'
import { Botao, Glass } from './primitives'
import {
  MAX_PONTOS,
  compararPontos,
  rotuloDoPonto,
} from '../lib/comparacao-pontos'
import { alunos, num } from '../lib/format'
import type { PontoPayload } from '../lib/types'

/**
 * Os pontos colados: as abas para trocar entre eles, e a comparacao A x B.
 *
 * A COMPARACAO NAO INCLUI VIABILIDADE, de proposito. Por DEC-009 a demanda e' premissa
 * digitada pelo operador, entao dois imoveis com a mesma metragem e o mesmo aluguel
 * produzem DRE, payback e break-even IDENTICOS — duas colunas com os mesmos numeros,
 * que se le como defeito. O que muda entre pontos e' o contexto (quem mora em volta,
 * quanto sobra de mercado, quem ja disputa), e e' isso que a tabela compara. A
 * viabilidade continua embaixo, por ponto.
 */
export default function PainelPontos({
  fichas,
  aberto,
  onAbrir,
  onRemover,
  onAdicionar,
}: {
  fichas: PontoPayload[]
  aberto: number
  onAbrir: (i: number) => void
  onRemover: (i: number) => void
  onAdicionar: () => void
}) {
  const [a, setA] = useState(0)
  const [b, setB] = useState(1)

  const rotulos = useMemo(() => fichas.map(rotuloDoPonto), [fichas])

  // Com 3+ pontos o operador escolhe o par; com 2 nao ha o que escolher.
  const iA = Math.min(a, fichas.length - 1)
  const iB = Math.min(b, fichas.length - 1)
  const comparacao = useMemo(
    () =>
      fichas.length >= 2 && iA !== iB ? compararPontos(fichas[iA], fichas[iB]) : null,
    [fichas, iA, iB],
  )

  return (
    <div style={{ display: 'grid', gap: 16 }}>
      {/* ---- Abas dos pontos ---- */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        {fichas.map((f, i) => {
          const ativo = i === aberto
          return (
            <span
              key={`${f.hex_id}-${i}`}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '7px 8px 7px 11px',
                borderRadius: 999,
                background: ativo ? 'var(--ac-a12)' : 'var(--surf-raised)',
                border: `1px solid ${ativo ? 'var(--ac-a25)' : 'var(--line-soft)'}`,
              }}
            >
              <button
                type="button"
                onClick={() => onAbrir(i)}
                style={{
                  background: 'transparent',
                  border: 0,
                  padding: 0,
                  font: `${ativo ? 700 : 500} 12px/1 var(--f-ui)`,
                  color: ativo ? 'var(--ac-text)' : 'var(--tx-soft)',
                }}
              >
                {rotulos[i]}
              </button>
              <span className="num" style={{ font: '500 10px/1 var(--f-num)', color: 'var(--tx-sub)' }}>
                {alunos(f.mercado?.residual)}
              </span>
              {fichas.length > 1 && (
                <button
                  type="button"
                  onClick={() => onRemover(i)}
                  title={`Remover ${rotulos[i]}`}
                  aria-label={`Remover ${rotulos[i]}`}
                  style={{
                    background: 'transparent',
                    border: 0,
                    padding: '0 2px',
                    color: 'var(--tx-rank)',
                    font: '700 12px/1 var(--f-ui)',
                  }}
                >
                  ×
                </button>
              )}
            </span>
          )
        })}

        {fichas.length < MAX_PONTOS ? (
          <Botao variante="ghost" onClick={onAdicionar}>
            + Adicionar mais um ponto
          </Botao>
        ) : (
          <span style={{ font: '400 11px/1.4 var(--f-ui)', color: 'var(--tx-sub)' }}>
            {/* Teto declarado: sem isto o botao sumiria sem explicacao. */}
            Máximo de {MAX_PONTOS} pontos — remova um para colar outro.
          </span>
        )}
      </div>

      {/* ---- Comparação ---- */}
      {fichas.length >= 2 && (
        <Glass style={{ padding: 18, display: 'grid', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
            <span style={{ font: '600 15px/1.2 var(--f-ui)', color: 'var(--tx-max)' }}>
              Comparando os pontos
            </span>
            <span style={{ font: '400 11px/1 var(--f-ui)', color: 'var(--tx-sub)' }}>
              contexto do entorno — a viabilidade fica por ponto, abaixo
            </span>
          </div>

          {/* Seletores só com 3+: com dois pontos não há par a escolher. */}
          {fichas.length > 2 && (
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <Select
                label="Primeiro ponto"
                value={String(iA)}
                onChange={(v) => setA(Number(v))}
                maxWidth={170}
                options={rotulos.map((r, i) => ({ value: String(i), label: r }))}
              />
              <Select
                label="Segundo ponto"
                value={String(iB)}
                onChange={(v) => setB(Number(v))}
                maxWidth={170}
                options={rotulos.map((r, i) => ({ value: String(i), label: r }))}
              />
            </div>
          )}

          {comparacao ? (
            <TabelaComparacao
              comparacao={comparacao}
              rotuloA={rotulos[iA]}
              rotuloB={rotulos[iB]}
            />
          ) : (
            <p style={{ font: '400 11.5px/1.5 var(--f-ui)', color: 'var(--tx-sub)', margin: 0 }}>
              Escolha dois pontos diferentes para comparar.
            </p>
          )}

          <p style={{ font: '400 11px/1.5 var(--f-ui)', color: 'var(--tx-sub)', margin: 0 }}>
            Cada leitura sai do raio de {num((fichas[iA]?.raio_km ?? 1) * 1000)} m em torno do
            ponto — a mesma régua do Relatório Pontual.
          </p>
        </Glass>
      )}
    </div>
  )
}
