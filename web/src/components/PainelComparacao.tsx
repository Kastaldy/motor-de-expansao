import TabelaRanking from './TabelaRanking'
import { DIMENSOES } from '../lib/comparacao'
import { MAX_COMPARADOS, ranquear } from '../lib/ranking-comparacao'
import type { Hex } from '../lib/types'

/**
 * Comparacao de 2 a 5 hexagonos, no mapa.
 *
 * NAO substitui o "Somar" (cenario multi-hex): sao perguntas diferentes. Somar
 * responde "quanto vale este pedaco de cidade junto"; comparar responde "qual destes
 * e' melhor, e por que". O painel troca sozinho quando ha 2..5 hexes selecionados.
 *
 * O ranking CONTA vitorias por dimensao — nao soma posicoes. Somar assumiria que uma
 * posicao em residual vale o mesmo que uma em renda, e isso e' um peso entre camadas
 * do M1, decisao que exige DEC.
 */
export default function PainelComparacao({
  hexes,
  onLimpar,
}: {
  hexes: Hex[]
  onLimpar: () => void
}) {
  const rotulos = hexes.map((h, i) => h.mun ?? `Hexágono ${i + 1}`)
  const ranking = ranquear(DIMENSOES, hexes, rotulos)

  return (
    /* SEM caixa nem teto de largura: este painel vive DENTRO da janela flutuante, que já
       tem fundo, borda e tamanho — e que o operador redimensiona. O `maxWidth: 420` que
       estava aqui era a herança de quando ele ficava solto no canto do mapa, e fazia a
       tabela parar de crescer quando a janela crescia (relato do Juan, 2026-08-12). */
    <div style={{ display: 'grid', gap: 10, width: '100%' }}>
      <div style={{ font: '700 12px/1 var(--f-ui)', color: 'var(--tx-max)' }}>
        Comparando {hexes.length} hexágonos
      </div>

      <TabelaRanking ranking={ranking} />

      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
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
        {hexes.length < MAX_COMPARADOS && (
          <span style={{ font: '400 10.5px/1.3 var(--f-ui)', color: 'var(--tx-sub)', flex: 1 }}>
            Clique em mais hexágonos — até {MAX_COMPARADOS}.
          </span>
        )}
      </div>
    </div>
  )
}
