import { compararComFrase } from '../lib/comparacao'
import { num } from '../lib/format'
import type { Hex } from '../lib/types'

/**
 * Comparacao A x B de dois hexagonos.
 *
 * NAO substitui o "Somar" (cenario multi-hex): sao perguntas diferentes. Somar
 * responde "quanto vale este pedaco de cidade junto"; comparar responde "qual
 * destes dois e' melhor, e por que". O painel troca sozinho quando ha exatamente
 * 2 hexes selecionados, e volta a somar com 1 ou 3+.
 *
 * Nenhum numero e' derivado aqui. A regra inteira (dimensoes, limiares, quem ganha,
 * a frase) vive em `lib/comparacao.ts`, que e' pura e testada; este componente so'
 * desenha o que ela devolve.
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
  const { deltas, frase, vencedor } = compararComFrase(a, b, rotuloA, rotuloB)

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
      <div style={{ font: '700 12px/1 var(--f-ui)', color: 'var(--tx-max)' }}>
        Comparando 2 hexágonos
      </div>

      {/* Cabecalho das colunas. O vencedor de cada lado fica em --tx-max (SELECAO),
          nunca no turquesa: turquesa e' ACAO e cenario, e reusa-lo aqui faria o
          vencedor ler como botao. */}
      <div
        style={{
          marginTop: 10,
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

function Cabecalho({ texto, destaque }: { texto: string; destaque: boolean }) {
  return (
    <span
      title={texto}
      style={{
        font: `${destaque ? 700 : 500} 10.5px/1.2 var(--f-ui)`,
        color: destaque ? 'var(--tx-max)' : 'var(--tx-muted)',
        textAlign: 'right',
        maxWidth: 92,
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
  rotulo,
  a,
  b,
  ganhaA,
  ganhaB,
  apagada,
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
      <span
        className="num"
        style={{
          font: `${ganhaA ? 700 : 500} 11.5px/1.6 var(--f-num)`,
          color: cor(ganhaA),
          textAlign: 'right',
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        {a}
      </span>
      <span
        className="num"
        style={{
          font: `${ganhaB ? 700 : 500} 11.5px/1.6 var(--f-num)`,
          color: cor(ganhaB),
          textAlign: 'right',
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        {b}
      </span>
    </>
  )
}

/** `null` vira o travessão de `num`, nunca "R$ —" nem "0". */
function formatar(v: number | null, unidade: string): string {
  if (v == null) return num(v)
  if (unidade === 'R$') return `R$ ${num(v)}`
  if (unidade === '%') return `${num(v, 1)}%`
  return num(v)
}
