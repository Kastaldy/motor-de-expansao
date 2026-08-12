import { useCallback, useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react'

import {
  ALTURA_CABECALHO,
  geometriaPadrao,
  mover,
  reajustar,
  redimensionar,
  type Ancora,
  type Area,
  type Geometria,
} from '../lib/janela'

/** Onde a janela nasce no eixo Y: abaixo do cabeçalho flutuante do mapa. */
const TOPO_PADRAO = 88

/**
 * A JANELA que traz a ficha por cima do mapa, no modo de ponto.
 *
 * ERA UMA GAVETA colada na borda direita (`GavetaFicha`, ate 2026-08-11). Virou janela
 * solta a pedido do Juan: com o mapa da cidade inteira no fundo, um painel grudado na
 * borda corta a faixa direita do territorio de alto a baixo, e e' justamente ali que o
 * pin do imovel costuma cair depois do voo da camera.
 *
 * E AGORA E' UMA JANELA DE VERDADE: arrasta pela barra de titulo, redimensiona pelo canto
 * inferior direito e recolhe para a barra. Sem isso ela era so' um painel com cantos
 * arredondados — cobria o painel de ranking do Explorar e o operador nao tinha o que
 * fazer a respeito a nao ser fecha-la inteira. A REGRA de onde ela pode ir vive em
 * `lib/janela.ts`, testada; aqui so' se aplica o resultado.
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
  ancora = 'direita',
  children,
}: {
  aberta: boolean
  titulo: string
  subtitulo?: string
  onFechar: () => void
  /** De que lado a janela nasce. Duas na mesma tela precisam de lados distintos. */
  ancora?: Ancora
  /**
   * Quanto a janela sobe do pe' da tela na posicao INICIAL. Existe porque o stepper do
   * funil ocupa a largura toda: com o recuo padrao a janela nasceria cobrindo os botoes
   * das camadas. Depois que o operador arrasta, quem manda e' ele.
   */
  recuoInferior?: number
  children: ReactNode
}) {
  const ref = useRef<HTMLElement | null>(null)
  /** A área onde a janela pode andar: o contêiner que a posiciona, não a tela toda. */
  const [area, setArea] = useState<Area>({ largura: 0, altura: 0 })
  /** `null` = ninguém arrastou nada ainda, então vale a posição de nascença. */
  const [geo, setGeo] = useState<Geometria | null>(null)
  const [recolhida, setRecolhida] = useState(false)
  const [arrastando, setArrastando] = useState(false)

  /* Mede o contêiner e continua medindo: encolher a janela do navegador com a ficha
     aberta deixaria a geometria (que é absoluta) fora da área. */
  useLayoutEffect(() => {
    const pai = ref.current?.parentElement
    if (!pai) return
    const medir = () => setArea({ largura: pai.clientWidth, altura: pai.clientHeight })
    medir()
    const obs = new ResizeObserver(medir)
    obs.observe(pai)
    return () => obs.disconnect()
  }, [])

  useEffect(() => {
    if (!area.largura || !area.altura) return
    setGeo((g) => (g ? reajustar(g, area) : g))
  }, [area])

  const atual =
    geo ?? (area.largura ? geometriaPadrao(area, TOPO_PADRAO, recuoInferior, ancora) : null)

  // Esc fecha. E' o gesto que todo mundo tenta primeiro numa janela por cima de algo.
  useEffect(() => {
    if (!aberta) return
    const aoTeclar = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onFechar()
    }
    window.addEventListener('keydown', aoTeclar)
    return () => window.removeEventListener('keydown', aoTeclar)
  }, [aberta, onFechar])

  /**
   * Arrasto e redimensionamento, no mesmo motor.
   *
   * `setPointerCapture` e' o que faz o gesto sobreviver a sair do elemento: sem ele,
   * puxar rapido tira o cursor da barra de titulo e o movimento morre no meio. Os deltas
   * sao aplicados sobre o estado ANTERIOR (`setGeo(g => ...)`), nao sobre uma foto do
   * render — arrastar rapido dispara varios eventos entre dois renders, e uma foto velha
   * faria a janela tremer para tras.
   */
  const gesto = useCallback(
    (aplicar: (g: Geometria, dx: number, dy: number, a: Area) => Geometria) =>
      (e: React.PointerEvent) => {
        if (!atual) return
        e.preventDefault()
        const alvo = e.currentTarget as HTMLElement
        alvo.setPointerCapture(e.pointerId)
        let ultimoX = e.clientX
        let ultimoY = e.clientY
        setArrastando(true)

        const aoMover = (ev: PointerEvent) => {
          const dx = ev.clientX - ultimoX
          const dy = ev.clientY - ultimoY
          ultimoX = ev.clientX
          ultimoY = ev.clientY
          setGeo((g) => aplicar(g ?? atual, dx, dy, area))
        }
        const aoSoltar = () => {
          setArrastando(false)
          alvo.removeEventListener('pointermove', aoMover)
          alvo.removeEventListener('pointerup', aoSoltar)
          alvo.removeEventListener('pointercancel', aoSoltar)
        }
        alvo.addEventListener('pointermove', aoMover)
        alvo.addEventListener('pointerup', aoSoltar)
        alvo.addEventListener('pointercancel', aoSoltar)
      },
    [atual, area],
  )

  const alturaVisivel = recolhida ? ALTURA_CABECALHO : (atual?.altura ?? 0)

  return (
    <aside
      ref={ref}
      role="dialog"
      aria-label={titulo}
      aria-hidden={!aberta}
      style={{
        position: 'absolute',
        left: atual?.x ?? 0,
        top: atual?.y ?? TOPO_PADRAO,
        width: atual?.largura ?? 0,
        height: alturaVisivel,
        display: 'flex',
        flexDirection: 'column',
        background: 'var(--surf-panel)',
        border: '1px solid var(--line)',
        borderRadius: 'var(--r-xl)',
        /* Sem isto o cabecalho interno pinta o proprio fundo por cima dos cantos
           arredondados e a janela volta a parecer um retangulo cortado. */
        overflow: 'hidden',
        /* A janela PEDE O MOUSE DE VOLTA.
           No modo de ponto ela vive dentro de uma camada com `pointerEvents: none` — que
           existe para o mapa do Explorar receber arraste e clique nos vãos. `none` é
           herdado, então sem esta linha a janela inteira ficava atravessável: os botões,
           os campos de metragem e aluguel e a própria barra de arrasto não respondiam, e
           o clique ia parar no mapa atrás (relato do Juan, 2026-08-12). Não aparecia nos
           testes porque evento disparado por script não passa pelo teste de acerto. */
        pointerEvents: 'auto',
        backdropFilter: 'blur(18px)',
        boxShadow: aberta ? '0 24px 64px rgba(0,0,0,.46)' : 'none',
        /* Sai INTEIRA pela direita: `100%` sozinho pararia com a borda de 16px ainda na
           tela, deixando um talho vertical sobre o mapa com a janela "fechada". */
        transform: aberta ? 'translateX(0)' : 'translateX(calc(100% + 24px))',
        opacity: aberta ? 1 : 0,
        visibility: aberta ? 'visible' : 'hidden',
        /* Nada de transicao DURANTE o gesto: animar cada quadro do arrasto faz a janela
           correr atras do cursor com atraso visivel.

           E a ALTURA nunca entra na lista. Animar `height` custou caro: a janela monta com
           altura 0 e cresce ate' a final, e uma aba em segundo plano CONGELA a transicao
           no comeco — medido, a janela ficava com 1,33px de altura e conteudo invisivel,
           parecendo defeito de layout. Recolher/expandir vira instantaneo, que e' um preco
           menor do que uma janela que as vezes nao tem altura. */
        transition: arrastando
          ? 'none'
          : 'transform .26s cubic-bezier(.4,0,.2,1), opacity .2s ease, visibility .26s, box-shadow .26s ease',
        zIndex: 26,
      }}
    >
      <header
        onPointerDown={gesto(mover)}
        style={{
          flexShrink: 0,
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          padding: '14px 16px',
          height: ALTURA_CABECALHO,
          borderBottom: recolhida ? 'none' : '1px solid var(--line-soft)',
          /* A barra de título É a alça. `grab`/`grabbing` é o que anuncia isso. */
          cursor: arrastando ? 'grabbing' : 'grab',
          /* Sem isto o arrasto seleciona o texto do título em vez de mover a janela. */
          userSelect: 'none',
          touchAction: 'none',
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

        <BotaoChrome
          onClick={() => setRecolhida((r) => !r)}
          title={recolhida ? 'Expandir a ficha' : 'Recolher para a barra'}
          rotulo={recolhida ? 'Expandir a ficha' : 'Recolher a ficha'}
        >
          {recolhida ? '▢' : '—'}
        </BotaoChrome>
        <BotaoChrome onClick={onFechar} title="Fechar a ficha (Esc)" rotulo="Fechar a ficha">
          ×
        </BotaoChrome>
      </header>

      {/* Recolhida, o conteúdo SAI da árvore de leitura mas a janela continua montada —
          o que o operador digitou na viabilidade sobrevive, como no fechar. */}
      {!recolhida && <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>{children}</div>}

      {/* Alça de redimensionar, no canto inferior direito. Some quando recolhida: não há
          altura para ajustar, e a alça ficaria sobre a barra de título. */}
      {!recolhida && (
        <div
          onPointerDown={gesto(redimensionar)}
          role="separator"
          aria-label="Redimensionar a ficha"
          style={{
            position: 'absolute',
            right: 0,
            bottom: 0,
            width: 18,
            height: 18,
            cursor: 'nwse-resize',
            touchAction: 'none',
            /* Duas riscas na diagonal — a convenção de canto redimensionável. */
            background:
              'linear-gradient(135deg, transparent 0 45%, var(--line-strong) 45% 55%, transparent 55% 70%, var(--line-strong) 70% 80%, transparent 80%)',
          }}
        />
      )}
    </aside>
  )
}

/** Os botões do canto da barra: mesmo desenho para recolher e fechar. */
function BotaoChrome({
  onClick,
  title,
  rotulo,
  children,
}: {
  onClick: () => void
  title: string
  rotulo: string
  children: ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      aria-label={rotulo}
      /* Impede que o clique no botão vire arrasto da barra que o contém. */
      onPointerDown={(e) => e.stopPropagation()}
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
        cursor: 'pointer',
      }}
    >
      {children}
    </button>
  )
}
