import { useEffect, type ReactNode } from 'react'

/**
 * A JANELA que traz a ficha por cima do mapa, no modo de ponto.
 *
 * ERA UMA GAVETA colada na borda direita (`GavetaFicha`, ate 2026-08-11). Virou janela
 * solta a pedido do Juan: com o mapa da cidade inteira no fundo, um painel grudado na
 * borda corta a faixa direita do territorio de alto a baixo, e e' justamente ali que o
 * pin do imovel costuma cair depois do voo da camera. A janela flutua com respiro nos
 * quatro lados, entao o mapa continua legivel EM VOLTA dela, nao so' ao lado.
 *
 * CONTINUA NAO SENDO MODAL. O mapa segue vivo e clicavel: a leitura da ficha e' sobre o
 * que esta' desenhado ali, e escurecer o mapa para ler sobre ele seria trabalhar contra a
 * propria tela. Por isso nao ha' backdrop e o foco nao fica preso.
 *
 * FICA MONTADA QUANDO FECHADA. So' o `transform` a tira da tela. Desmontar zeraria o que
 * o operador digitou em metragem e aluguel no bloco de viabilidade — fechar para olhar o
 * mapa e perder a conta ao reabrir seria punir quem usou as duas coisas juntas.
 * `visibility: hidden` no fim da transicao e' o que a tira da ordem de tabulacao; sem
 * isso, o Tab pescaria botoes invisiveis fora da tela.
 */
export default function JanelaFicha({
  aberta,
  titulo,
  subtitulo,
  onFechar,
  recuoInferior = 16,
  children,
}: {
  aberta: boolean
  titulo: string
  subtitulo?: string
  onFechar: () => void
  /**
   * Quanto a janela sobe do pe' da tela. Existe porque o stepper do funil ocupa a
   * largura toda quando ha' territorio carregado: com o recuo padrao a janela cobriria
   * os botoes das camadas. Mesmo numero que o botao de abrir ja' usa.
   */
  recuoInferior?: number
  children: ReactNode
}) {
  // Esc fecha. E' o gesto que todo mundo tenta primeiro numa janela por cima de algo.
  useEffect(() => {
    if (!aberta) return
    const aoTeclar = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onFechar()
    }
    window.addEventListener('keydown', aoTeclar)
    return () => window.removeEventListener('keydown', aoTeclar)
  }, [aberta, onFechar])

  return (
    <aside
      role="dialog"
      aria-label={titulo}
      aria-hidden={!aberta}
      style={{
        position: 'absolute',
        /* Abaixo do cabecalho flutuante, que tem 16 de padding e quebra em duas linhas em
           tela estreita. */
        top: 88,
        right: 16,
        bottom: recuoInferior,
        /* 520px cabe a grade de KPI em 2 colunas e a comparacao A x B em 3, sem espremer
           os numeros; 92vw impede a janela de cobrir a tela toda no celular. */
        width: 'min(520px, 92vw)',
        display: 'flex',
        flexDirection: 'column',
        background: 'var(--surf-panel)',
        border: '1px solid var(--line)',
        borderRadius: 'var(--r-xl)',
        /* Sem isto o cabecalho interno pinta o proprio fundo por cima dos cantos
           arredondados e a janela volta a parecer um retangulo cortado. */
        overflow: 'hidden',
        backdropFilter: 'blur(18px)',
        boxShadow: aberta ? '0 24px 64px rgba(0,0,0,.46)' : 'none',
        /* Sai INTEIRA pela direita: `100%` sozinho pararia com a borda de 16px ainda na
           tela, deixando um talho vertical sobre o mapa com a janela "fechada". */
        transform: aberta ? 'translateX(0)' : 'translateX(calc(100% + 24px))',
        opacity: aberta ? 1 : 0,
        visibility: aberta ? 'visible' : 'hidden',
        transition:
          'transform .26s cubic-bezier(.4,0,.2,1), opacity .2s ease, visibility .26s, box-shadow .26s ease',
        zIndex: 26,
      }}
    >
      <header
        style={{
          flexShrink: 0,
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          padding: '14px 16px',
          borderBottom: '1px solid var(--line-soft)',
        }}
      >
        <div style={{ display: 'grid', gap: 2, minWidth: 0, flex: 1 }}>
          <span
            style={{
              font: '600 14px/1.2 var(--f-ui)',
              color: 'var(--tx-max)',
              letterSpacing: '-.01em',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {titulo}
          </span>
          {subtitulo && (
            <span
              style={{
                font: '400 11.5px/1.3 var(--f-ui)',
                color: 'var(--tx-sub)',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {subtitulo}
            </span>
          )}
        </div>

        <button
          type="button"
          onClick={onFechar}
          title="Fechar a ficha (Esc)"
          aria-label="Fechar a ficha"
          style={{
            flexShrink: 0,
            width: 30,
            height: 30,
            display: 'grid',
            placeItems: 'center',
            borderRadius: 8,
            border: '1px solid var(--line-soft)',
            background: 'var(--surf-raised)',
            color: 'var(--tx-soft)',
            font: '600 15px/1 var(--f-ui)',
          }}
        >
          ×
        </button>
      </header>

      <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>{children}</div>
    </aside>
  )
}
