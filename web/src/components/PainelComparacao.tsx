import { useState } from 'react'

import BlocosComparacao from './BlocosComparacao'
import TabelaRanking from './TabelaRanking'
import { type BlocoParametro, DIMENSOES, blocosPorParametro } from '../lib/comparacao'
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
  const [pedidoRelatorio, setPedidoRelatorio] = useState(false)
  const rotulos = hexes.map((h, i) => h.mun ?? `Hexágono ${i + 1}`)
  const ranking = ranquear(DIMENSOES, hexes, rotulos)
  const blocos = blocosPorParametro(DIMENSOES, hexes) as BlocoParametro<unknown>[]

  return (
    /* SEM caixa nem teto de largura: este painel vive DENTRO da janela flutuante, que já
       tem fundo, borda e tamanho — e que o operador redimensiona. O `maxWidth: 420` que
       estava aqui era a herança de quando ele ficava solto no canto do mapa, e fazia a
       tabela parar de crescer quando a janela crescia (relato do Juan, 2026-08-12). */
    <div style={{ display: 'grid', gap: 10, width: '100%' }}>
      <div style={{ font: '700 12px/1 var(--f-ui)', color: 'var(--tx-max)' }}>
        Comparando {hexes.length} hexágonos
      </div>

      {/* UM BLOCO POR PARÂMETRO (pedido do Juan, 2026-08-13), acima do ranking. Responde
          "qual ganha NESTE parâmetro" sem obrigar a ler a tabela inteira. Não ordena a
          lista: ordenar exigiria somar parâmetros num número único, que é score novo e só
          muda por DEC — o ranking abaixo continua CONTANDO vitórias, que é outra coisa. */}
      <BlocosComparacao
        blocos={blocos}
        rotulos={rotulos}
        onRelatorio={() => setPedidoRelatorio(true)}
      />

      {pedidoRelatorio && (
        <p
          style={{
            margin: 0,
            padding: '9px 11px',
            borderRadius: 'var(--r-md)',
            border: '1px dashed var(--ac-a25)',
            font: '400 11.5px/1.5 var(--f-ui)',
            color: 'var(--tx-narrative)',
          }}
        >
          O relatório desta comparação ainda não é gerado — o botão está aqui para o fluxo
          ficar de pé enquanto o formato é definido.
        </p>
      )}

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
