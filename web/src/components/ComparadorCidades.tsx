import { useMemo, useState } from 'react'

import Select from './Select'
import TabelaRanking from './TabelaRanking'
import {
  DIMENSOES_MUNICIPIO,
  montarMunicipio,
  municipiosDisponiveis,
} from '../lib/comparacao-municipios'
import type { CrescimentoMunicipio } from '../lib/oportunidades'
import { MAX_COMPARADOS, ranquear } from '../lib/ranking-comparacao'
import type { Passo } from '../lib/types'

/**
 * Comparar ate 5 CIDADES, na visao de estado.
 *
 * POR QUE POR SELETOR, E NAO POR CLIQUE NA LISTA. No nivel de UF, clicar num item ja
 * significa DRILL-DOWN (entrar naquele municipio) — comportamento que o operador usa
 * o tempo todo. Sequestra-lo para "adicionar a comparacao" quebraria o fluxo
 * principal para servir o secundario.
 *
 * O CRESCIMENTO MUNICIPAL entra como dimensao (`DIMENSOES_MUNICIPIO`), lida como
 * DESVIO para a mediana da UF — nunca como numero absoluto. Comparar "8,7%" com "22%"
 * solto convidaria a ler o CAGED como grandeza nacional, que e' o que a regra proibe;
 * aqui os municipios sao todos da MESMA UF, entao a leitura e' estadual.
 *
 * Recolhido por padrao: a resposta da tela continua sendo o funil.
 */
export default function ComparadorCidades({
  passos,
  cresMun,
}: {
  passos: readonly Passo[]
  cresMun?: Record<string, CrescimentoMunicipio> | null
}) {
  const [aberto, setAberto] = useState(false)
  const [escolhidas, setEscolhidas] = useState<string[]>([])

  const cidades = useMemo(() => municipiosDisponiveis(passos), [passos])

  const ranking = useMemo(() => {
    const validas = escolhidas.filter(Boolean)
    if (validas.length < 2) return null
    const itens = validas.map((n) => montarMunicipio(n, passos, cresMun))
    return ranquear(DIMENSOES_MUNICIPIO, itens, validas)
  }, [escolhidas, passos, cresMun])

  // Menos de duas cidades no funil: nao ha o que comparar, e um seletor vazio so'
  // faria o operador procurar o que nao existe.
  if (cidades.length < 2) return null

  const podeAdicionar = escolhidas.length < MAX_COMPARADOS
  const disponiveis = cidades.filter((c) => !escolhidas.includes(c))

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
        Comparar cidades {escolhidas.length > 0 && `(${escolhidas.length})`}
        <span aria-hidden style={{ color: 'var(--tx-muted)' }}>{aberto ? '−' : '+'}</span>
      </button>

      {aberto && (
        <div style={{ padding: '0 11px 12px', display: 'grid', gap: 10 }}>
          {/* Fichas das escolhidas, com remover. */}
          {escolhidas.length > 0 && (
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {escolhidas.map((c) => (
                <span
                  key={c}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: '5px 7px 5px 10px',
                    borderRadius: 999,
                    background: 'var(--ac-a12)',
                    border: '1px solid var(--ac-a25)',
                    font: '500 11px/1 var(--f-ui)',
                    color: 'var(--ac-chip)',
                  }}
                >
                  {c}
                  <button
                    type="button"
                    onClick={() => setEscolhidas((xs) => xs.filter((x) => x !== c))}
                    aria-label={`Remover ${c}`}
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
                </span>
              ))}
            </div>
          )}

          {podeAdicionar && disponiveis.length > 0 ? (
            <Select
              label="Adicionar cidade à comparação"
              value=""
              onChange={(v) => v && setEscolhidas((xs) => [...xs, v])}
              maxWidth={200}
              buscavel
              placeholder={escolhidas.length ? 'Adicionar cidade…' : 'Escolher cidade…'}
              options={disponiveis.map((c) => ({ value: c, label: c }))}
            />
          ) : (
            <span style={{ font: '400 10.5px/1.4 var(--f-ui)', color: 'var(--tx-sub)' }}>
              {/* Teto declarado: sem isto o seletor sumiria sem explicacao. */}
              Máximo de {MAX_COMPARADOS} cidades — remova uma para trocar.
            </span>
          )}

          {ranking ? (
            <TabelaRanking ranking={ranking} />
          ) : (
            <p style={{ font: '400 11px/1.5 var(--f-ui)', color: 'var(--tx-sub)', margin: 0 }}>
              Escolha ao menos duas cidades para ver onde cada uma leva vantagem — o
              crescimento entra lido contra a mediana deste estado.
            </p>
          )}
        </div>
      )}
    </div>
  )
}
