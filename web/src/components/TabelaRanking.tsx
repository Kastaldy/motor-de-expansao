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
        <div style={{ display: 'grid', gridTemplateColumns: colunas, gap: '0 10px', minWidth: 320 }}>
          <span />
          {itens.map((it) => (
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
              }}
            >
              {it.rotulo}
            </span>
          ))}

          {/* Contagem de vitorias logo abaixo do nome: e' a evidencia do ranking. */}
          <span style={{ font: '500 9.5px/1 var(--f-num)', color: 'var(--tx-sub)', paddingBottom: 8 }}>
            lidera em
          </span>
          {itens.map((it) => (
            <span
              key={`v-${it.indice}`}
              className="num"
              style={{
                font: '700 11px/1 var(--f-num)',
                color: it.vitorias ? 'var(--ac-text)' : 'var(--tx-off)',
                textAlign: 'right',
                paddingBottom: 8,
              }}
            >
              {it.vitorias}/{dimensoesDecisivas.length}
            </span>
          ))}

          {linhas.map((chave) => {
            const ref = itens[0].porDimensao.find((d) => d.chave === chave)!
            const decisiva = dimensoesDecisivas.includes(chave)
            return (
              <Linha
                key={chave}
                rotulo={ref.rotulo}
                unidade={ref.unidade}
                decisiva={decisiva}
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
  celulas,
}: {
  rotulo: string
  unidade: string
  decisiva: boolean
  celulas: { valor: number | null; melhor: boolean; pior: boolean }[]
}) {
  return (
    <>
      <span
        style={{
          font: '500 11px/1.6 var(--f-ui)',
          color: decisiva ? 'var(--tx-muted)' : 'var(--tx-off)',
        }}
      >
        {rotulo}
      </span>
      {celulas.map((c, i) => (
        <span
          key={i}
          className="num"
          style={{
            font: `${c.melhor ? 700 : 500} 11.5px/1.6 var(--f-num)`,
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
      ))}
    </>
  )
}

function formatar(v: number | null, unidade: string): string {
  if (v == null) return num(v)
  if (unidade === 'R$') return `R$ ${num(v)}`
  if (unidade === '%') return `${num(v, 1)}%`
  if (unidade === 'p.p.') return `${v > 0 ? '+' : ''}${num(v, 1)}`
  if (unidade === 'score') return num(v, 1)
  return num(v)
}
