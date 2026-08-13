import type { BlocoParametro } from '../lib/comparacao'
import { valorComUnidade } from '../lib/format'
import { Botao } from './primitives'

/**
 * A comparação virada de lado: UM BLOCO POR PARÂMETRO, com todos os itens dentro.
 *
 * POR QUE EXISTE (pedido do Juan, 2026-08-13). A tabela A x B obriga a escolher um par
 * antes de comparar — com 5 pontos na tela são 10 pares, e "qual tem mais residual?" vira
 * uma varredura. Por parâmetro, a resposta está num bloco só.
 *
 * DESTACA, NÃO RANQUEIA (decisão do Juan). Cada bloco diz quem ganha NELE. Uma ordenação
 * geral exigiria somar parâmetros num número único — isso é score novo, e peso entre
 * camadas do M1 só muda por DEC. A leitura de conjunto fica com quem decide.
 *
 * Não decide nada: recebe os blocos já calculados por `lib/comparacao`.
 */
export default function BlocosComparacao({
  blocos,
  rotulos,
  cor,
  onRelatorio,
  rotuloRelatorio = 'Gerar relatório da comparação',
}: {
  blocos: readonly BlocoParametro<unknown>[]
  /** Rótulo de cada item, na MESMA ordem da lista comparada (`indice` aponta para cá). */
  rotulos: readonly string[]
  /** Cor de identidade do item `i` — a mesma da aba/coluna, para ligar sem ler o rótulo. */
  cor?: (i: number) => string
  /** Ausente = o botão não aparece. */
  onRelatorio?: () => void
  rotuloRelatorio?: string
}) {
  return (
    <div style={{ display: 'grid', gap: 14 }}>
      {onRelatorio && (
        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <Botao variante="ghost" onClick={onRelatorio}>
            {rotuloRelatorio}
          </Botao>
        </div>
      )}

      {blocos.map((b) => {
        const comDado = b.valores.filter((v) => v.valor != null)
        // Teto da barra: o maior valor ABSOLUTO do bloco. A barra é relativa aos itens
        // comparados, nunca a uma régua absoluta — o produto não tem corte publicado de
        // "residual bom", e pintar a partir de um limiar não aprovado afirmaria régua
        // inexistente. Negativo entra pelo módulo (crescimento pode ser negativo), senão
        // a barra sumiria justamente na linha que importa.
        const teto = comDado.length ? Math.max(...comDado.map((v) => Math.abs(v.valor!))) : 0

        return (
          <section
            key={b.dimensao.chave}
            style={{
              padding: '11px 12px',
              borderRadius: 'var(--r-md)',
              border: '1px solid var(--line-soft)',
              background: 'var(--surf-raised)',
              display: 'grid',
              gap: 8,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
              <h4 style={{ margin: 0, font: '600 12px/1.2 var(--f-ui)', color: 'var(--tx-max)' }}>
                {b.dimensao.rotulo}
              </h4>
              {/* A DIREÇÃO precisa estar escrita: "Concorrentes: 4 contra 6" só se lê como
                  bom ou ruim sabendo que aqui menos é melhor — e a barra maior, nesse
                  bloco, é a pior. --tx-sub porque carrega significado. */}
              {!b.dimensao.maiorEhMelhor && (
                <span style={{ font: '400 9.5px/1.3 var(--f-ui)', color: 'var(--tx-sub)' }}>
                  menos é melhor
                </span>
              )}
              {/* Diferença abaixo do limiar continua VISÍVEL (auditoria), mas declarada —
                  sem isto o destaque leria como vantagem real. */}
              {comDado.length >= 2 && !b.relevante && (
                <span style={{ font: '400 9.5px/1.3 var(--f-ui)', color: 'var(--tx-sub)' }}>
                  · diferença irrelevante
                </span>
              )}
            </div>

            <div style={{ display: 'grid', gap: 5 }}>
              {b.valores.map((v) => {
                const melhor = b.relevante && b.melhores.includes(v.indice)
                const pior = b.relevante && b.piores.includes(v.indice)
                const fr = v.valor == null || teto === 0 ? null : Math.abs(v.valor) / teto
                return (
                  <div
                    key={v.indice}
                    style={{
                      display: 'grid',
                      gridTemplateColumns: 'minmax(56px, 92px) 1fr auto',
                      alignItems: 'center',
                      gap: 9,
                    }}
                  >
                    <span
                      title={rotulos[v.indice]}
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 5,
                        font: `${melhor ? 700 : 500} 10.5px/1.3 var(--f-ui)`,
                        color: melhor ? 'var(--tx-max)' : 'var(--tx-muted)',
                        overflow: 'hidden',
                      }}
                    >
                      {cor && (
                        <span
                          aria-hidden
                          style={{
                            width: 7,
                            height: 7,
                            borderRadius: 2,
                            background: cor(v.indice),
                            flexShrink: 0,
                          }}
                        />
                      )}
                      <span
                        style={{
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {rotulos[v.indice]}
                      </span>
                    </span>

                    <span
                      aria-hidden
                      style={{
                        display: 'block',
                        height: 8,
                        borderRadius: 4,
                        background: 'var(--line-soft)',
                        overflow: 'hidden',
                      }}
                    >
                      {fr != null && (
                        <span
                          style={{
                            display: 'block',
                            width: `${Math.round(fr * 100)}%`,
                            height: '100%',
                            borderRadius: 4,
                            /* Veste a cor do item; quem perde esmaece pela opacidade e não
                               por outra cor — trocar a cor apagaria a identidade justamente
                               onde se quer comparar. */
                            background: cor ? cor(v.indice) : 'var(--ac)',
                            opacity: !b.relevante ? 0.35 : melhor ? 1 : pior ? 0.4 : 0.6,
                          }}
                        />
                      )}
                    </span>

                    <span
                      style={{
                        display: 'inline-flex',
                        alignItems: 'baseline',
                        gap: 5,
                        justifySelf: 'end',
                      }}
                    >
                      <span
                        className="num"
                        style={{
                          font: `${melhor ? 700 : 500} 11px/1.3 var(--f-num)`,
                          color: melhor
                            ? 'var(--tx-max)'
                            : b.relevante
                              ? 'var(--tx-soft)'
                              : 'var(--tx-off)',
                          fontVariantNumeric: 'tabular-nums',
                        }}
                      >
                        {valorComUnidade(v.valor, b.dimensao.unidade)}
                      </span>
                      {/* SELEÇÃO, nunca o turquesa: turquesa é AÇÃO neste produto, e
                          reusá-lo faria o vencedor ler como botão. */}
                      {melhor && (
                        <span
                          style={{
                            font: '700 8.5px/1 var(--f-ui)',
                            color: 'var(--tx-max)',
                            letterSpacing: '0.04em',
                          }}
                        >
                          MELHOR
                        </span>
                      )}
                    </span>
                  </div>
                )
              })}
            </div>
          </section>
        )
      })}
    </div>
  )
}
