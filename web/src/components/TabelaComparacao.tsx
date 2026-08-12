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
              fracaoA={fracao(d.a, d.b)}
              fracaoB={fracao(d.b, d.a)}
              maiorEhMelhor={d.dimensao.maiorEhMelhor}
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
  rotulo, a, b, ganhaA, ganhaB, apagada, fracaoA, fracaoB, maiorEhMelhor,
}: {
  rotulo: string
  a: string
  b: string
  ganhaA: boolean
  ganhaB: boolean
  apagada: boolean
  /** Quanto o valor de cada lado ocupa em relação ao maior dos dois (0 a 1). */
  fracaoA: number | null
  fracaoB: number | null
  maiorEhMelhor: boolean
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
        {/* A DIREÇÃO precisa estar escrita. "Concorrentes: 4 contra 6" só se lê como bom
            ou ruim sabendo que aqui menos é melhor — e a barra maior, nessa linha, é a
            pior. Sem esta legenda o desenho mentiria para quem passa o olho. */}
        {!maiorEhMelhor && (
          <span style={{ font: '400 9.5px/1.6 var(--f-ui)', color: 'var(--tx-off)' }}>
            {' '}
            · menos é melhor
          </span>
        )}
      </span>
      {[
        { v: a, ganha: ganhaA, fr: fracaoA },
        { v: b, ganha: ganhaB, fr: fracaoB },
      ].map(({ v, ganha, fr }, i) => (
        <span key={i} style={{ display: 'grid', gap: 4, justifyItems: 'end', minWidth: 72 }}>
          <span
            className="num"
            style={{
              /* Menor que a barra em peso visual: aqui também o desenho é que responde
                 "qual é maior", e o número fica como evidência auditável. */
              font: `${ganha ? 700 : 500} 11px/1.3 var(--f-num)`,
              color: cor(ganha),
              textAlign: 'right',
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            {v}
          </span>
          {/* A barra é RELATIVA ao outro lado, não a uma régua absoluta: comparar dois
              pontos responde "qual é maior", e o produto não tem corte publicado de
              "residual bom". Inventar um aqui seria afirmar régua que não existe. */}
          {fr != null && (
            <span
              aria-hidden
              style={{
                display: 'block',
                width: '100%',
                height: 8,
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
                  background: ganha
                    ? 'var(--ac)'
                    : apagada
                      ? 'var(--line-mid)'
                      : 'var(--tx-rank)',
                }}
              />
            </span>
          )}
        </span>
      ))}
    </>
  )
}

/**
 * Quanto ESTE valor ocupa em relacao ao maior dos dois lados.
 *
 * `null` quando nao ha' o que comparar (um dos lados ausente) ou quando o maior e' zero —
 * duas barras vazias nao dizem nada, e uma barra cheia sobre zero seria pior: afirmaria
 * vantagem onde nao ha' grandeza. Negativos (crescimento pode ser negativo) entram pelo
 * modulo, senao a barra sumiria justamente na linha que importa.
 */
function fracao(valor: number | null, outro: number | null): number | null {
  if (valor == null || outro == null) return null
  const teto = Math.max(Math.abs(valor), Math.abs(outro))
  if (teto === 0) return null
  return Math.abs(valor) / teto
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
