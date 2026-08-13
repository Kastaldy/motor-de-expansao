import { num } from '../lib/format'
import type { RankingComparacao } from '../lib/ranking-comparacao'

/**
 * Tabela de N colunas (2 a 5) com o melhor e o pior marcados.
 *
 * Uma linha por dimensao, uma coluna por item. O melhor de cada linha em branco
 * (--tx-max, a cor de SELECAO deste produto) e o pior em vermelho semantico. Linha
 * que nao separou ninguem fica apagada inteira — o numero continua visivel para
 * auditoria, sem virar argumento.
 *
 * Nao decide nada: recebe o `RankingComparacao` ja calculado por
 * `lib/ranking-comparacao`, que conta vitorias em vez de somar posicoes.
 */
export default function TabelaRanking({ ranking }: { ranking: RankingComparacao }) {
  const { itens, melhor, pior, dimensoesDecisivas, frase } = ranking
  if (!itens.length) return null

  // As dimensoes vem na mesma ordem em todos os itens (o ranqueador garante).
  const linhas = itens[0].porDimensao.map((d) => d.chave)
  const colunas = `minmax(96px, 1.2fr) repeat(${itens.length}, minmax(72px, 1fr))`

  return (
    <div style={{ display: 'grid', gap: 12 }}>
      <div style={{ overflowX: 'auto' }}>
        {/* `gap` de COLUNA zerado de propósito (o respiro virou padding dentro da célula).
            Com gap, a faixa de fundo de cada linha sairia picotada nos vãos e deixaria de
            funcionar como trilho — e é justamente o trilho que faltava: "não tem um limite
            de quando começa um parâmetro e outro" (Juan, 2026-08-13). Numa tabela larga o
            olho percorre muito espaço vazio entre o rótulo e o número, e sem faixa ele
            perde a linha no meio do caminho. */}
        <div style={{ display: 'grid', gridTemplateColumns: colunas, gap: 0, minWidth: 320 }}>
          <span />
          {itens.map((it, i) => (
            <span
              key={it.indice}
              title={it.rotulo}
              style={{
                font: `${melhor?.indice === it.indice ? 700 : 500} 10.5px/1.25 var(--f-ui)`,
                color:
                  melhor?.indice === it.indice
                    ? 'var(--tx-max)'
                    : pior?.indice === it.indice
                      ? 'var(--tx-off)'
                      : 'var(--tx-muted)',
                textAlign: 'right',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                paddingBottom: 4,
                // Espelha o padding do corpo: com `gap: 0` na grade, é ele que mantém as
                // colunas alinhadas entre cabeçalho e linhas.
                paddingLeft: 10,
                paddingRight: i === itens.length - 1 ? 6 : 0,
              }}
            >
              {it.rotulo}
            </span>
          ))}

          {/* Contagem de vitorias logo abaixo do nome: e' a evidencia do ranking. */}
          <span
            style={{
              font: '500 9.5px/1 var(--f-num)',
              color: 'var(--tx-sub)',
              paddingBottom: 8,
              paddingLeft: 6,
            }}
          >
            lidera em
          </span>
          {itens.map((it, i) => (
            <span
              key={`v-${it.indice}`}
              className="num"
              style={{
                font: '700 11px/1 var(--f-num)',
                color: it.vitorias ? 'var(--ac-text)' : 'var(--tx-off)',
                textAlign: 'right',
                paddingBottom: 8,
                paddingLeft: 10,
                paddingRight: i === itens.length - 1 ? 6 : 0,
              }}
            >
              {it.vitorias}/{dimensoesDecisivas.length}
            </span>
          ))}

          {linhas.map((chave, i) => {
            const ref = itens[0].porDimensao.find((d) => d.chave === chave)!
            const decisiva = dimensoesDecisivas.includes(chave)
            return (
              <Linha
                key={chave}
                rotulo={ref.rotulo}
                unidade={ref.unidade}
                decisiva={decisiva}
                faixa={i % 2 === 1}
                celulas={itens.map((it) => it.porDimensao.find((d) => d.chave === chave)!)}
              />
            )
          })}
        </div>
      </div>

      <p
        style={{
          margin: 0,
          paddingTop: 10,
          borderTop: '1px solid var(--line-soft)',
          font: '400 11.5px/1.55 var(--f-ui)',
          color: 'var(--tx-narrative)',
        }}
      >
        {frase}
      </p>
    </div>
  )
}

function Linha({
  rotulo,
  unidade,
  decisiva,
  faixa,
  celulas,
}: {
  rotulo: string
  unidade: string
  decisiva: boolean
  /** Linha ímpar: ganha o fundo do trilho. */
  faixa: boolean
  celulas: { valor: number | null; melhor: boolean; pior: boolean }[]
}) {
  /* O TRILHO. Cada célula da linha repete o mesmo fundo e a mesma borda inferior — em
     grade CSS não existe "elemento linha" para pintar de uma vez. Junto com o `gap: 0` da
     grade, isso vira uma faixa contínua da esquerda à direita, que é o que devolve o
     limite entre um parâmetro e o outro. */
  const trilho = {
    background: faixa ? 'var(--surf-raised)' : 'transparent',
    borderBottom: '1px solid var(--line-soft)',
    padding: '7px 0',
  } as const

  return (
    <>
      <span
        style={{
          ...trilho,
          font: '500 11px/1.4 var(--f-ui)',
          color: decisiva ? 'var(--tx-muted)' : 'var(--tx-off)',
          paddingLeft: 6,
          paddingRight: 10,
        }}
      >
        {rotulo}
      </span>
      {celulas.map((c, i) => {
        const fr = fracaoNaLinha(c.valor, celulas)
        return (
          <span
            key={i}
            style={{
              ...trilho,
              display: 'grid',
              gap: 4,
              justifyItems: 'end',
              minWidth: 0,
              paddingLeft: 10,
              paddingRight: i === celulas.length - 1 ? 6 : 0,
            }}
          >
            <span
              className="num"
              style={{
                font: `${c.melhor ? 700 : 500} 11px/1.3 var(--f-num)`,
                color: c.melhor
                  ? 'var(--tx-max)'
                  : c.pior
                    ? 'var(--neg)'
                    : decisiva
                      ? 'var(--tx-soft)'
                      : 'var(--tx-off)',
                textAlign: 'right',
                fontVariantNumeric: 'tabular-nums',
              }}
            >
              {formatar(c.valor, unidade)}
            </span>
            {/* MESMA linguagem da comparação de pontos: barra relativa ao maior da linha,
                turquesa no melhor e vermelho no pior. A COR vem do veredito que o
                ranqueador já calculou, não de um limiar inventado aqui — por isso ela
                continua certa nas dimensões em que menos é melhor, onde a barra mais
                comprida é a perdedora. */}
            {fr != null && (
              <span
                aria-hidden
                style={{
                  display: 'block',
                  width: '100%',
                  height: 7,
                  borderRadius: 4,
                  background: 'var(--line-soft)',
                  overflow: 'hidden',
                }}
              >
                <span
                  style={{
                    display: 'block',
                    width: `${Math.round(fr * 100)}%`,
                    height: '100%',
                    borderRadius: 4,
                    background: c.melhor
                      ? 'var(--ac)'
                      : c.pior
                        ? 'var(--neg)'
                        : decisiva
                          ? 'var(--tx-rank)'
                          : 'var(--line-mid)',
                  }}
                />
              </span>
            )}
          </span>
        )
      })}
    </>
  )
}

/**
 * Quanto esta célula ocupa em relação à MAIOR da linha.
 *
 * `null` quando o valor falta ou quando o maior da linha é zero: barras todas vazias não
 * dizem nada, e uma barra cheia sobre zero afirmaria vantagem onde não há grandeza.
 * Negativos entram pelo módulo — crescimento pode ser negativo, e a barra sumiria
 * justamente na linha que importa.
 */
function fracaoNaLinha(
  valor: number | null,
  celulas: { valor: number | null }[],
): number | null {
  if (valor == null) return null
  const teto = Math.max(...celulas.map((c) => Math.abs(c.valor ?? 0)))
  if (!(teto > 0)) return null
  return Math.abs(valor) / teto
}

function formatar(v: number | null, unidade: string): string {
  if (v == null) return num(v)
  if (unidade === 'R$') return `R$ ${num(v)}`
  if (unidade === '%') return `${num(v, 1)}%`
  if (unidade === 'p.p.') return `${v > 0 ? '+' : ''}${num(v, 1)}`
  if (unidade === 'score') return num(v, 1)
  return num(v)
}
