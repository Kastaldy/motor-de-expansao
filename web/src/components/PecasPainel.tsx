import type { CSSProperties, ReactNode } from 'react'

/**
 * Pecas visuais dos PAINEIS redesenhados do mapa (ficha do hexagono e detalhe do
 * imovel) — porte do design "Paineis do Hexagono" do Claude Design (2026-08-21),
 * adaptado aos tokens e fontes do piloto (Instrument Serif / Instrument Sans /
 * IBM Plex Mono), como a aba imobiliaria ja fez com o design dela.
 *
 * Sao pecas de FORMA, nao de dado: nenhuma decide o que aparece nem colore por
 * limiar proprio — quem passa cor ja a tirou de uma regua publicada (faixas do
 * mapa, clusters do modelo de viabilidade) ou usa o neutro.
 */

/** Card padrao dos paineis: superficie levantada com borda suave. */
export function CardPainel({ children, style }: { children: ReactNode; style?: CSSProperties }) {
  return (
    <div
      style={{
        padding: '15px 16px',
        borderRadius: 14,
        background: 'var(--surf-raised)',
        border: '1px solid var(--line-soft)',
        ...style,
      }}
    >
      {children}
    </div>
  )
}

/** Titulo de secao: voz narrativa (serif) + nota mono uppercase a direita. */
export function TituloSecao({
  titulo,
  nota,
  gap = 11,
}: {
  titulo: string
  nota?: string
  /** Espaco abaixo do titulo; 0 quando o bloco seguinte ja tem o proprio respiro. */
  gap?: number
}) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'baseline',
        justifyContent: 'space-between',
        gap: 10,
        marginBottom: gap,
      }}
    >
      <h3
        className="story"
        style={{ margin: 0, font: '400 18px/1.15 var(--f-story)', color: 'var(--tx-max)' }}
      >
        {titulo}
      </h3>
      {nota && (
        <span
          className="num"
          style={{
            font: '400 9px/1 var(--f-num)',
            letterSpacing: '.1em',
            textTransform: 'uppercase',
            color: 'var(--tx-sub)',
            whiteSpace: 'nowrap',
          }}
        >
          {nota}
        </span>
      )}
    </div>
  )
}

/** Linha rotulo/valor das tabelas dos paineis (container da a borda; linha, so o ritmo). */
export function LinhaTabela({ rotulo, valor, tom }: { rotulo: string; valor: string; tom?: string }) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'baseline',
        justifyContent: 'space-between',
        gap: 14,
        padding: '9px 14px',
      }}
    >
      <span style={{ font: '400 12px/1.3 var(--f-ui)', color: 'var(--tx-label)' }}>{rotulo}</span>
      <span
        className="num"
        style={{ font: '500 12px/1.3 var(--f-num)', color: tom ?? 'var(--tx-soft)', textAlign: 'right' }}
      >
        {valor}
      </span>
    </div>
  )
}

/**
 * Regua de 10 tracinhos de um score 0-100 (o "grafico" dos cards de score do
 * design). Preenchidos = score/10 arredondado; a cor vem da faixa PUBLICADA da
 * camada — sem regua, quem chama passa o neutro.
 */
export function Ticks({ score, cor }: { score: number | null | undefined; cor: string }) {
  const cheios = score == null ? 0 : Math.max(0, Math.min(10, Math.round(score / 10)))
  return (
    <div style={{ display: 'flex', gap: 2 }} aria-hidden>
      {Array.from({ length: 10 }, (_, i) => (
        <span
          key={i}
          style={{
            flex: 1,
            height: 4,
            borderRadius: 2,
            background: i < cheios ? cor : 'var(--surf-pending)',
          }}
        />
      ))}
    </div>
  )
}

/** Pilula mono uppercase. Cor em HEX ganha fundo com alfa da propria cor; cor em
 *  var() (que nao compoe alfa em string) cai no fundo neutro levantado. */
export function Pill({ texto, cor }: { texto: string; cor: string }) {
  const fundoDaCor = cor.startsWith('#')
  return (
    <span
      className="num"
      style={{
        padding: '4px 9px',
        borderRadius: 999,
        background: fundoDaCor ? `${cor}26` : 'var(--surf-pending)',
        color: cor,
        font: '500 9px/1 var(--f-num)',
        letterSpacing: '.12em',
        textTransform: 'uppercase',
        whiteSpace: 'nowrap',
      }}
    >
      {texto}
    </span>
  )
}
