import { textoInfoRenda } from '../lib/renda-meta'

/**
 * Ícone de informação (ⓘ) ao lado de um rótulo de renda: o `title` e o `aria-label`
 * dizem de que versão de fatores e de quando é o número (`renda_meta` do `/api/me`, E0
 * da renda). Sem proveniência (backend anterior) não desenha nada — nunca um ícone mudo.
 */
export function InfoRenda() {
  const texto = textoInfoRenda()
  if (!texto) return null
  return (
    <span
      role="img"
      title={texto}
      aria-label={texto}
      style={{
        marginLeft: 4,
        cursor: 'help',
        font: '400 10px/1 var(--f-ui)',
        color: 'var(--tx-sub)',
        verticalAlign: 'baseline',
      }}
    >
      ⓘ
    </span>
  )
}
