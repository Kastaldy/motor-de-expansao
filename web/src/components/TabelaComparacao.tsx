import { num } from '../lib/format'
import type { Comparacao } from '../lib/comparacao'

/**
 * A tabela A x B — generica sobre o que esta sendo comparado.
 *
 * Existe separada porque hexagonos e municipios comparam coisas diferentes mas devem
 * LER igual: mesma hierarquia, mesmo tratamento do vencedor, mesmo apagado para a
 * diferenca irrelevante. Duplicar isso garantiria que as duas telas divirjam no
 * primeiro ajuste de estilo.
 *
 * Nao decide nada: recebe a `Comparacao` ja calculada por `lib/comparacao`.
 */
export default function TabelaComparacao<T>({
  comparacao,
  rotuloA,
  rotuloB,
}: {
  comparacao: Comparacao<T>
  rotuloA: string
  rotuloB: string
}) {
  const { deltas, frase, vencedor } = comparacao

  return (
    <>
      {/* O vencedor fica em --tx-max (SELECAO), nunca no turquesa: turquesa e' ACAO
          neste produto, e reusa-lo aqui faria a coluna vencedora ler como botao. */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr auto auto',
          gap: '0 10px',
          alignItems: 'center',
        }}
      >
        <span />
        <Cabecalho texto={rotuloA} destaque={vencedor === 'a'} />
        <Cabecalho texto={rotuloB} destaque={vencedor === 'b'} />

        {deltas.map((d) => {
          const indisponivel = d.a == null || d.b == null
          return (
            <Linha
              key={d.dimensao.chave}
              rotulo={d.dimensao.rotulo}
              a={formatar(d.a, d.dimensao.unidade)}
              b={formatar(d.b, d.dimensao.unidade)}
              ganhaA={!indisponivel && d.relevante && d.vencedor === 'a'}
              ganhaB={!indisponivel && d.relevante && d.vencedor === 'b'}
              // Diferenca abaixo do limiar aparece, mas apagada: o numero continua
              // visivel para auditoria, sem virar argumento.
              apagada={!d.relevante}
            />
          )
        })}
      </div>

      <p
        style={{
          margin: '11px 0 0',
          paddingTop: 10,
          borderTop: '1px solid var(--line-soft)',
          font: '400 11.5px/1.55 var(--f-ui)',
          color: 'var(--tx-narrative)',
        }}
      >
        {frase}
      </p>
    </>
  )
}

function Cabecalho({ texto, destaque }: { texto: string; destaque: boolean }) {
  return (
    <span
      title={texto}
      style={{
        font: `${destaque ? 700 : 500} 10.5px/1.2 var(--f-ui)`,
        color: destaque ? 'var(--tx-max)' : 'var(--tx-muted)',
        textAlign: 'right',
        maxWidth: 96,
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
      }}
    >
      {texto}
    </span>
  )
}

function Linha({
  rotulo, a, b, ganhaA, ganhaB, apagada,
}: {
  rotulo: string
  a: string
  b: string
  ganhaA: boolean
  ganhaB: boolean
  apagada: boolean
}) {
  const cor = (ganha: boolean) =>
    ganha ? 'var(--tx-max)' : apagada ? 'var(--tx-off)' : 'var(--tx-soft)'
  return (
    <>
      <span
        style={{
          font: '500 11px/1.6 var(--f-ui)',
          color: apagada ? 'var(--tx-off)' : 'var(--tx-muted)',
        }}
      >
        {rotulo}
      </span>
      {[
        { v: a, ganha: ganhaA },
        { v: b, ganha: ganhaB },
      ].map(({ v, ganha }, i) => (
        <span
          key={i}
          className="num"
          style={{
            font: `${ganha ? 700 : 500} 11.5px/1.6 var(--f-num)`,
            color: cor(ganha),
            textAlign: 'right',
            fontVariantNumeric: 'tabular-nums',
          }}
        >
          {v}
        </span>
      ))}
    </>
  )
}

/** `null` vira o travessão de `num`, nunca "R$ —" nem "0". */
function formatar(v: number | null, unidade: string): string {
  if (v == null) return num(v)
  if (unidade === 'R$') return `R$ ${num(v)}`
  if (unidade === '%') return `${num(v, 1)}%`
  // Pontos percentuais podem ser negativos e o sinal e' a informacao.
  if (unidade === 'p.p.') return `${v > 0 ? '+' : ''}${num(v, 1)} p.p.`
  return num(v)
}
