import TabelaComparacao from './TabelaComparacao'
import { compararComFrase } from '../lib/comparacao'
import type { Hex } from '../lib/types'

/**
 * Comparacao A x B de dois hexagonos, no mapa.
 *
 * NAO substitui o "Somar" (cenario multi-hex): sao perguntas diferentes. Somar
 * responde "quanto vale este pedaco de cidade junto"; comparar responde "qual
 * destes dois e' melhor, e por que". O painel troca sozinho quando ha exatamente
 * 2 hexes selecionados, e volta a somar com 1 ou 3+.
 *
 * Nenhum numero e' derivado aqui: a regra (dimensoes, limiares, quem ganha, a frase)
 * vive em `lib/comparacao.ts`, e o desenho da tabela em `TabelaComparacao` — o mesmo
 * que a comparacao de cidades usa, para as duas lerem igual.
 */
export default function PainelComparacao({
  a,
  b,
  onLimpar,
}: {
  a: Hex
  b: Hex
  onLimpar: () => void
}) {
  const rotuloA = a.mun ?? 'Hexágono A'
  const rotuloB = b.mun ?? 'Hexágono B'

  return (
    <div
      style={{
        background: 'var(--surf-panel)',
        border: '1px solid var(--ac-a30)',
        borderRadius: 'var(--r-md)',
        padding: '11px 13px',
        backdropFilter: 'blur(16px)',
        minWidth: 300,
        maxWidth: 360,
      }}
    >
      <div style={{ font: '700 12px/1 var(--f-ui)', color: 'var(--tx-max)', marginBottom: 10 }}>
        Comparando 2 hexágonos
      </div>

      <TabelaComparacao
        comparacao={compararComFrase(a, b, rotuloA, rotuloB)}
        rotuloA={rotuloA}
        rotuloB={rotuloB}
      />

      <div style={{ marginTop: 11, display: 'flex', gap: 8 }}>
        <button
          type="button"
          onClick={onLimpar}
          style={{
            flex: 1,
            padding: '7px 10px',
            borderRadius: 8,
            border: '1px solid var(--line-soft)',
            background: 'var(--surf-raised)',
            color: 'var(--tx-soft)',
            font: '600 11.5px/1 var(--f-ui)',
          }}
        >
          Limpar
        </button>
      </div>
    </div>
  )
}
