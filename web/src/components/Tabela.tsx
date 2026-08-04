import type { CSSProperties, ReactNode } from 'react'

/* ---------------------------------------------------------------------------
   Tabela genérica — a PRIMEIRA do produto.

   `<table>` de verdade, e não uma grade de `<div>`, por duas razões concretas:
   copiar e colar no Excel preserva as colunas (o time de campo faz isso o tempo
   todo), e o leitor de tela anuncia cabeçalho e ordenação sem nenhum ARIA
   inventado — basta `aria-sort` no `<th>`.

   O cabeçalho é `position: sticky`: a carteira tem ~90 linhas e rolar sem
   cabeçalho é o que faz o operador perder a coluna.
   --------------------------------------------------------------------------- */

export interface Coluna<T> {
  chave: string
  rotulo: string
  /** conteúdo da célula */
  render: (item: T, indice: number) => ReactNode
  largura?: number | string
  alinhamento?: 'left' | 'right' | 'center'
  /** false desliga a ordenação nesta coluna (ex.: sparkline) */
  ordenavel?: boolean
  /** dica curta no cabeçalho (o `title` do `<th>`) */
  ajuda?: string
}

export interface TabelaProps<T> {
  colunas: Coluna<T>[]
  dados: T[]
  chaveDe: (item: T) => string
  ordenarPor?: string
  direcao?: 'asc' | 'desc'
  onOrdenar?: (chave: string) => void
  onLinha?: (item: T) => void
  /** destaque de uma linha (a que está aberta na ficha, por exemplo) */
  selecionada?: string
  vazio?: ReactNode
  alturaLinha?: number
}

const CELULA: CSSProperties = {
  padding: '0 10px',
  borderBottom: '1px solid var(--line-soft)',
  whiteSpace: 'nowrap',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
}

export default function Tabela<T>({
  colunas,
  dados,
  chaveDe,
  ordenarPor,
  direcao = 'desc',
  onOrdenar,
  onLinha,
  selecionada,
  vazio,
  alturaLinha = 38,
}: TabelaProps<T>) {
  if (!dados.length) {
    return (
      <div
        style={{
          padding: '34px 20px',
          textAlign: 'center',
          font: '400 13px/1.6 var(--f-ui)',
          color: 'var(--tx-narrative)',
        }}
      >
        {vazio ?? 'Nenhuma unidade no recorte atual.'}
      </div>
    )
  }

  return (
    <table
      style={{
        width: '100%',
        borderCollapse: 'separate',
        borderSpacing: 0,
        tableLayout: 'fixed',
        font: '400 12px/1.2 var(--f-ui)',
      }}
    >
      <thead>
        <tr>
          {colunas.map((c) => {
            const ativa = ordenarPor === c.chave
            const ordenavel = c.ordenavel !== false && Boolean(onOrdenar)
            return (
              <th
                key={c.chave}
                scope="col"
                title={c.ajuda}
                aria-sort={ativa ? (direcao === 'asc' ? 'ascending' : 'descending') : 'none'}
                style={{
                  ...CELULA,
                  position: 'sticky',
                  top: 0,
                  zIndex: 2,
                  height: 32,
                  width: c.largura,
                  textAlign: c.alinhamento ?? 'left',
                  background: 'var(--surf-chrome)',
                  backdropFilter: 'blur(14px)',
                  borderBottom: '1px solid var(--line-mid)',
                  font: '600 10px/1 var(--f-ui)',
                  letterSpacing: '.06em',
                  textTransform: 'uppercase',
                  color: ativa ? 'var(--ac-text)' : 'var(--tx-muted)',
                  cursor: ordenavel ? 'pointer' : 'default',
                  userSelect: 'none',
                }}
                onClick={ordenavel ? () => onOrdenar?.(c.chave) : undefined}
              >
                {c.rotulo}
                {ativa && <span aria-hidden> {direcao === 'asc' ? '▲' : '▼'}</span>}
              </th>
            )
          })}
        </tr>
      </thead>
      <tbody>
        {dados.map((item, i) => {
          const chave = chaveDe(item)
          const ativa = selecionada === chave
          return (
            <tr
              key={chave}
              onClick={onLinha ? () => onLinha(item) : undefined}
              tabIndex={onLinha ? 0 : undefined}
              onKeyDown={
                onLinha
                  ? (e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        onLinha(item)
                      }
                    }
                  : undefined
              }
              style={{
                height: alturaLinha,
                cursor: onLinha ? 'pointer' : 'default',
                background: ativa ? 'var(--ac-a10)' : 'transparent',
              }}
              onMouseEnter={(e) => {
                if (!ativa) e.currentTarget.style.background = 'var(--surf-raised)'
              }}
              onMouseLeave={(e) => {
                if (!ativa) e.currentTarget.style.background = 'transparent'
              }}
            >
              {colunas.map((c) => (
                <td
                  key={c.chave}
                  style={{
                    ...CELULA,
                    textAlign: c.alinhamento ?? 'left',
                    color: 'var(--tx-soft)',
                  }}
                >
                  {c.render(item, i)}
                </td>
              ))}
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}
