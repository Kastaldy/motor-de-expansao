import type { RedeComodidadeItem } from '../lib/types'

/**
 * Ícone de cada item que a concorrente OFERECE (ficha da unidade no mapa). Mesmo traço do
 * `IconeTipo`: `stroke: currentColor`, então quem escolhe a cor é a etiqueta que o contém.
 *
 * Decorativo (`aria-hidden`): o rótulo do item vem escrito ao lado, e é ele que informa.
 */
const TRACOS: Readonly<Record<RedeComodidadeItem, readonly string[]>> = Object.freeze({
  musculacao: ['M6 8v8', 'M3 10v4', 'M18 8v8', 'M21 10v4', 'M6 12h12'],
  luta: [
    'M7 12V8a4 4 0 0 1 8 0v1h1a2 2 0 0 1 2 2v2a4 4 0 0 1-4 4H9a2 2 0 0 1-2-2z',
    'M7 12h8',
    'M9 17v3h6v-3',
  ],
  armario: ['M6 3h12v18H6z', 'M6 12h12', 'M14.5 7v1.5', 'M14.5 15.5V17'],
  chuveiro: ['M5 21V7a4 4 0 0 1 8 0', 'M9 10h8', 'M10 13v1', 'M13 13v1', 'M16 13v1', 'M10 17v1', 'M13 17v1', 'M16 17v1'],
  vestiario: ['M10 7a2 2 0 1 1 3 1.7c-.7.4-1 .9-1 1.8', 'M12 10.5 3 17.5h18z'],
  massagem: ['M4 9a2 2 0 1 0 4 0a2 2 0 1 0-4 0', 'M3 16h18', 'M9 13h8a4 4 0 0 1 4 3', 'M6 16v4', 'M18 16v4'],
  cadeira_massagem: [
    'M7 11V7a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v4',
    'M5 11a2 2 0 0 1 2 2v2h10v-2a2 2 0 0 1 4 0v5H3v-5a2 2 0 0 1 2-2z',
    'M6 18v2',
    'M18 18v2',
  ],
})

export default function IconeComodidade({ item, tamanho }: { item: RedeComodidadeItem; tamanho: number }) {
  return (
    <svg
      width={tamanho}
      height={tamanho}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      style={{ display: 'block', flexShrink: 0 }}
    >
      {TRACOS[item].map((d) => (
        <path key={d} d={d} />
      ))}
    </svg>
  )
}
