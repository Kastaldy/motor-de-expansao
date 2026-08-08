import { useMemo, useState } from 'react'

import Select from './Select'
import TabelaComparacao from './TabelaComparacao'
import {
  compararMunicipios,
  montarMunicipio,
  municipiosDisponiveis,
} from '../lib/comparacao-municipios'
import type { CrescimentoMunicipio } from '../lib/oportunidades'
import type { Passo } from '../lib/types'

/**
 * Comparar duas CIDADES, na visao de estado.
 *
 * POR QUE POR SELETOR, E NAO POR CLIQUE NA LISTA. No nivel de UF, clicar num item ja
 * significa DRILL-DOWN (entrar naquele municipio) — comportamento que o operador usa
 * o tempo todo. Sequestra-lo para "adicionar a comparacao" quebraria o fluxo
 * principal para servir o secundario. Dois seletores nao disputam nada.
 *
 * Recolhido por padrao: a resposta da tela continua sendo o funil; a comparacao e'
 * uma pergunta que o operador faz quando quer.
 */
export default function ComparadorCidades({
  passos,
  cresMun,
}: {
  passos: readonly Passo[]
  cresMun?: Record<string, CrescimentoMunicipio> | null
}) {
  const [aberto, setAberto] = useState(false)
  const [a, setA] = useState('')
  const [b, setB] = useState('')

  const cidades = useMemo(() => municipiosDisponiveis(passos), [passos])

  const comparacao = useMemo(() => {
    if (!a || !b || a === b) return null
    return compararMunicipios(
      montarMunicipio(a, passos, cresMun),
      montarMunicipio(b, passos, cresMun),
    )
  }, [a, b, passos, cresMun])

  // Menos de duas cidades no funil: nao ha o que comparar, e um seletor vazio so'
  // faria o operador procurar o que nao existe.
  if (cidades.length < 2) return null

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
        Comparar duas cidades
        <span aria-hidden style={{ color: 'var(--tx-muted)' }}>{aberto ? '−' : '+'}</span>
      </button>

      {aberto && (
        <div style={{ padding: '0 11px 12px', display: 'grid', gap: 10 }}>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <Select
              label="Primeira cidade"
              value={a}
              onChange={setA}
              maxWidth={150}
              buscavel
              placeholder="Cidade A…"
              options={cidades.map((c) => ({ value: c, label: c }))}
            />
            <Select
              label="Segunda cidade"
              value={b}
              onChange={setB}
              maxWidth={150}
              buscavel
              placeholder="Cidade B…"
              options={cidades.map((c) => ({ value: c, label: c }))}
            />
          </div>

          {comparacao ? (
            <TabelaComparacao comparacao={comparacao} rotuloA={a} rotuloB={b} />
          ) : (
            <p style={{ font: '400 11px/1.5 var(--f-ui)', color: 'var(--tx-sub)', margin: 0 }}>
              {a && a === b
                ? 'Escolha duas cidades diferentes.'
                : 'Escolha duas cidades do funil para ver onde cada uma leva vantagem.'}
            </p>
          )}
        </div>
      )}
    </div>
  )
}
