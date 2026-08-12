import { num } from '../lib/format'
import { recomendar, type EntradaRecomendacao, type TipoAcao } from '../lib/recomendacao'

/**
 * "O que fazer com este imovel" — os criterios do territorio, e as acoes possiveis.
 *
 * Duas metades, e a ordem importa. Primeiro os CRITERIOS: cada metrica contra a regua
 * canonica, com passa/reprova, para o operador ver de onde vem o veredito. Depois as
 * ACOES, que sao a resposta a "e agora?".
 *
 * A regra inteira vive em `lib/recomendacao.ts`, pura e testada. Aqui so' se desenha —
 * inclusive a comparacao contra a regua, que ja vem decidida do servidor (`passa`),
 * porque tela e backend discordando sobre o que e "aprovado" seria pior que nao ter
 * o veredito.
 */
export default function Recomendacao(entrada: EntradaRecomendacao) {
  const acoes = recomendar(entrada)

  return (
    <div style={{ display: 'grid', gap: 16 }}>
      {/* ---- Critérios do território ---- */}
      {entrada.criterios.length > 0 && (
        <div style={{ display: 'grid', gap: 7 }}>
          {entrada.criterios.map((c) => (
            <div
              key={c.chave}
              style={{
                display: 'flex',
                alignItems: 'baseline',
                gap: 10,
                padding: '7px 0',
                borderBottom: '1px solid var(--line-soft)',
              }}
            >
              <Selo passa={c.passa} />
              <span
                style={{
                  flex: 1,
                  minWidth: 0,
                  font: '500 12px/1.3 var(--f-ui)',
                  color: 'var(--tx-soft)',
                }}
              >
                {c.rotulo}
              </span>
              <span
                className="num"
                style={{
                  font: '700 12.5px/1 var(--f-num)',
                  color: c.passa === false ? 'var(--neg)' : 'var(--tx-max)',
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {valorFmt(c.valor, c.unidade)}
              </span>
              {/* A regua ao lado do numero: sem ela o operador nao sabe se 66,8 e' bom. */}
              <span
                className="num"
                style={{
                  font: '500 10.5px/1 var(--f-num)',
                  color: 'var(--tx-sub)',
                  minWidth: 78,
                  textAlign: 'right',
                }}
              >
                {c.regua != null
                  ? `${c.maior_melhor ? 'mín.' : 'máx.'} ${valorFmt(c.regua, c.unidade)}`
                  : ''}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* ---- Ações ---- */}
      <div style={{ display: 'grid', gap: 10 }}>
        {acoes.map((a, i) => (
          <div
            key={`${a.tipo}-${i}`}
            style={{
              padding: '12px 14px',
              borderRadius: 'var(--r-md)',
              background: 'var(--surf-raised)',
              borderLeft: `2px solid ${corDoTipo(a.tipo)}`,
              border: '1px solid var(--line-soft)',
              borderLeftWidth: 2,
              borderLeftColor: corDoTipo(a.tipo),
            }}
          >
            <div
              style={{
                font: '600 12.5px/1.3 var(--f-ui)',
                color: 'var(--tx-max)',
                marginBottom: 5,
              }}
            >
              {a.titulo}
            </div>
            <div style={{ font: '400 11.5px/1.55 var(--f-ui)', color: 'var(--tx-narrative)' }}>
              {a.detalhe}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

/** Semantica (bom/ruim), independente do turquesa da marca. */
function corDoTipo(t: TipoAcao): string {
  if (t === 'bloqueio') return 'var(--neg)'
  if (t === 'aviso') return 'var(--info)'
  if (t === 'ok') return 'var(--pos)'
  return 'var(--ac)'
}

function Selo({ passa }: { passa: boolean | null }) {
  // `null` NAO e' reprovado: e' "sem dado para avaliar", e pintar de vermelho faria o
  // operador descartar ponto por ausencia de medicao.
  const cor = passa == null ? 'var(--tx-rank)' : passa ? 'var(--pos)' : 'var(--neg)'
  const texto = passa == null ? 'n/d' : passa ? '✓' : '✕'
  return (
    <span
      title={passa == null ? 'sem dado para avaliar' : passa ? 'passa na régua' : 'reprova na régua'}
      style={{
        width: 20,
        flexShrink: 0,
        font: '700 11px/1 var(--f-num)',
        color: cor,
      }}
    >
      {texto}
    </span>
  )
}

function valorFmt(v: number | null, unidade: string): string {
  if (v == null) return num(v)
  if (unidade === 'R$') return `R$ ${num(v)}`
  if (unidade === 'score') return num(v, 1)
  return num(v)
}
