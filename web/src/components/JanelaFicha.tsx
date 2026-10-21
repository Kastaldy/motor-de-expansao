import { useCallback, useEffect, useLayoutEffect, useReducer, useRef, useState, type ReactNode } from 'react'

import {
  ALTURA_CABECALHO,
  geometriaPadrao,
  LARGURA_PADRAO,
  mover,
  reajustar,
  redimensionar,
  topoMinimoSobCabecalho,
  type Ancora,
  type Area,
  type Geometria,
} from '../lib/janela'
import { registrarJanela, removerJanela } from '../lib/ocupacao-janelas'
import { Z_JANELA_FICHA, Z_JANELA_FICHA_TOPO } from '../lib/camadas-mapa'

/** Onde a janela nasce no eixo Y: abaixo do cabeçalho flutuante do mapa. Com o cabeçalho
 *  quebrado em duas linhas, nasce abaixo dele (`topoMinimo`), nunca embaixo. */
const TOPO_PADRAO = 88

/**
 * Pilha das janelas ABERTAS, na ordem de abertura (módulo, não estado: os listeners
 * de Esc de instâncias diferentes precisam enxergar a MESMA lista no mesmo evento).
 *
 * Existe porque cada instância registra o próprio keydown no `window`, e com duas
 * janelas abertas — a ficha do hexágono e o detalhe do imóvel, o primeiro par
 * co-aberto do produto — um único Esc disparava os dois `onFechar`: as duas janelas
 * sumiam juntas e a seleção do hexágono ia embora de quebra. Com a pilha, Esc fecha
 * só a do topo (a aberta por último), que é a convenção de janelas empilhadas.
 */
const pilhaAbertas: symbol[] = []

/**
 * Quem esta' no TOPO da pilha tambem fica por cima na TELA.
 *
 * Antes todas as janelas tinham o mesmo `zIndex`, e quem desempatava era a ordem no DOM —
 * que nao tem nada a ver com a ordem em que o operador abriu. Com a ficha de ponto aberta,
 * clicar num hexagono abria a ficha dele ATRAS da do ponto (a do ponto vem depois na
 * arvore), e ela parecia nao ter aberto (pedido do Vinicius, 2026-10-14: a caixa da
 * esquerda nao pode ocultar o que esta' por baixo). Agora a aberta por ultimo — ou a
 * ultima em que o operador clicou — sobe, como em qualquer gerenciador de janelas. O Esc
 * segue a mesma pilha, entao fecha justamente a que esta' a' vista por cima.
 *
 * SO' VALE ENTRE JANELAS SEM CONTEXTO DE EMPILHAMENTO NO MEIO. O `zIndex` de cada janela
 * so' disputa com irmaos do mesmo contexto: ate' 21/10/2026 o conteiner da ficha de ponto
 * tinha `zIndex: 40`, e com isso a janela do ponto pintava por cima de TODAS as do mapa
 * qualquer que fosse a pilha -- a comparacao de hexagonos nascia em degrau e ficava 87,7%
 * coberta, o clique nela nao a trazia para frente e o Esc fechava a janela escondida
 * (print do Vinicius, 21/10). Quem envolver uma janela num ancestral com `zIndex`,
 * `transform`, `filter` ou `opacity < 1` recria o defeito em silencio.
 */
const ouvintesDaPilha = new Set<() => void>()
/**
 * Esc que JA fechou uma janela. Com a pilha reordenavel, fechar a do topo pode tirar a
 * janela da pilha ainda DENTRO do mesmo evento (o React aplica a atualizacao de tecla de
 * forma sincrona) — e a proxima a ouvir o mesmo Esc se via no topo e fechava tambem. Um
 * Esc fecha UMA janela.
 */
const escTratados = new WeakSet<KeyboardEvent>()
function avisarPilha(): void {
  for (const f of ouvintesDaPilha) f()
}
/**
 * Abaixo do CABECALHO do mapa (z 29) e das camadas de 30+ (Metodologia, tooltips do mapa,
 * modais). O cabecalho subiu acima das janelas em 21/10/2026 (pedido do Vinicius): a lista
 * aberta dos seletores dele fica presa no contexto do cabecalho, e com o cabecalho no z 11
 * ela descia SOB as janelas -- trocar de estado ou municipio com uma ficha aberta exigia
 * fecha-la. Por isso a janela tambem nao sobe alem dele (`topoMinimo`).
 */
const Z_JANELA = Z_JANELA_FICHA
const Z_JANELA_TOPO = Z_JANELA_FICHA_TOPO

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
 * FICA MONTADA QUANDO FECHADA. So' o `transform` a tira da tela. Desmontar zeraria o
 * estado de dentro da ficha (o que o operador digitou, a rolagem, a secao aberta) —
 * fechar para olhar o mapa e perder isso ao reabrir seria punir quem usou as duas coisas
 * juntas.
 * `visibility: hidden` no fim da transicao e' o que a tira da ordem de tabulacao; sem
 * isso, o Tab pescaria botoes invisiveis fora da tela.
 */
export default function JanelaFicha({
  aberta,
  titulo,
  subtitulo,
  onFechar,
  recuoInferior = 16,
  /* ESQUERDA como padrão (pedido do Juan, 2026-08-12): as janelas do produto abrem todas
     do mesmo lado. À direita elas nasciam sobre o painel de ranking do Explorar, que é
     justamente o que se lê junto com a ficha. */
  ancora = 'esquerda',
  degrau = 0,
  larguraInicial = LARGURA_PADRAO,
  rodape,
  pedidoDeFrente,
  children,
}: {
  aberta: boolean
  titulo: string
  subtitulo?: string
  onFechar: () => void
  /** De que lado a janela nasce. Duas na mesma tela precisam de lados distintos. */
  ancora?: Ancora
  /**
   * Cascata sobre outra janela do MESMO lado (`geometriaPadrao`): 0 = a posição de sempre,
   * 1 = deslocada uma barra de título para baixo e um recuo para dentro. Só vale para a
   * posição de NASCENÇA — depois que o operador arrasta, quem manda é ele.
   */
  degrau?: number
  /**
   * Quanto a janela sobe do pe' da tela na posicao INICIAL. Existe porque o stepper do
   * funil ocupa a largura toda: com o recuo padrao a janela nasceria cobrindo os botoes
   * das camadas. Depois que o operador arrasta, quem manda e' ele.
   */
  recuoInferior?: number
  /**
   * A largura de NASCENÇA (`geometriaPadrao`). Ausente, a de sempre (`LARGURA_PADRAO`);
   * a ficha de ponto passa `LARGURA_FICHA_PONTO`. Depois que o operador redimensiona,
   * quem manda é ele.
   */
  larguraInicial?: number
  /**
   * Faixa FIXA no pé da janela, fora da área que rola — os botões de ação da ficha
   * (2026-10-14: "Estudo" e "Simulador" da análise de ponto).
   *
   * Fixa porque são a SAÍDA da leitura: com a ficha longa, botões no fim do conteúdo só
   * apareciam depois de rolar tudo, e quem não rolava não sabia que existiam. Ausente,
   * a janela desenha exatamente o que desenhava antes — as outras quatro janelas do mapa
   * não passam a prop.
   */
  rodape?: ReactNode
  /**
   * Contador: cada valor NOVO traz a janela para o topo da pilha, como o clique nela. O da
   * MONTAGEM nao conta. Existe para a ficha de ponto: com a janela ja' aberta e outra por
   * cima (a comparacao, a ficha do hexagono), um ponto novo pedido pelo operador ficaria
   * escondido ate' um clique. Ausente, nada muda.
   */
  pedidoDeFrente?: number
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

  /* O TOPO MINIMO: a borda de baixo do cabeçalho do mapa (`topoMinimoSobCabecalho`). O
     cabeçalho fica ACIMA das janelas (`Z_CABECALHO_MAPA`), então a barra de título que
     subisse por baixo dele ficaria sem alça. Ele é de outro componente (o `MapScreen`; para
     a ficha de ponto, o irmão na árvore), então é achado pelo DOM — o primeiro ancestral
     que contém a `barra-ultra`, como o botão "Ver a ficha" já faz — e medido de novo quando
     muda de altura (é `flex-wrap`: quebra em duas linhas em tela estreita). Sem cabeçalho,
     0: a trava de sempre, só o topo da área. */
  const [topoMinimo, setTopoMinimo] = useState(0)
  useLayoutEffect(() => {
    const pai = ref.current?.parentElement
    if (!pai) return
    let achado: HTMLElement | null = null
    for (let anc: HTMLElement | null = pai; anc && !achado; anc = anc.parentElement) {
      achado = anc.querySelector<HTMLElement>('header.barra-ultra')
    }
    if (!achado) return
    const cabecalho = achado
    const medir = () => {
      const caixa = pai.getBoundingClientRect()
      /* A escala do `#root` (transform), lida do próprio contêiner: tela / layout. */
      const escala = pai.offsetHeight ? caixa.height / pai.offsetHeight : 1
      setTopoMinimo(topoMinimoSobCabecalho(cabecalho.getBoundingClientRect().bottom, caixa.top, escala))
    }
    medir()
    const obs = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(medir)
    obs?.observe(cabecalho)
    window.addEventListener('resize', medir)
    return () => {
      obs?.disconnect()
      window.removeEventListener('resize', medir)
    }
  }, [])

  useEffect(() => {
    if (!area.largura || !area.altura) return
    setGeo((g) => (g ? reajustar(g, area, topoMinimo) : g))
  }, [area, topoMinimo])

  const atual =
    geo ??
    (area.largura
      ? geometriaPadrao(area, Math.max(TOPO_PADRAO, topoMinimo), recuoInferior, ancora, degrau, larguraInicial)
      : null)

  /** Identidade estável desta instância na pilha de janelas abertas. */
  const idJanela = useRef(Symbol('janela'))
  /* `onFechar` costuma vir inline (identidade nova a cada render). Se o efeito da pilha
     dependesse dele, todo re-render tiraria e re-empilharia a janela — e a ordem da
     pilha (que é o dado: quem está no topo) se corromperia. O ref desacopla. */
  const onFecharRef = useRef(onFechar)
  useEffect(() => {
    onFecharRef.current = onFechar
  })

  // Esc fecha. E' o gesto que todo mundo tenta primeiro numa janela por cima de algo.
  // Com mais de uma aberta, fecha SO' a do topo da pilha (ver `pilhaAbertas`).
  useEffect(() => {
    if (!aberta) return
    const id = idJanela.current
    pilhaAbertas.push(id)
    avisarPilha()
    const aoTeclar = (e: KeyboardEvent) => {
      if (e.key !== 'Escape' || escTratados.has(e)) return
      if (pilhaAbertas[pilhaAbertas.length - 1] !== id) return
      escTratados.add(e)
      onFecharRef.current()
    }
    window.addEventListener('keydown', aoTeclar)
    return () => {
      const i = pilhaAbertas.indexOf(id)
      if (i >= 0) pilhaAbertas.splice(i, 1)
      window.removeEventListener('keydown', aoTeclar)
      avisarPilha()
    }
  }, [aberta])

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

  /* Re-renderiza quando a pilha muda, para trocar o `zIndex` (ver `ouvintesDaPilha`). */
  const [, redesenhar] = useReducer((n: number) => n + 1, 0)
  useEffect(() => {
    ouvintesDaPilha.add(redesenhar)
    return () => {
      ouvintesDaPilha.delete(redesenhar)
    }
  }, [])
  const noTopo = aberta && pilhaAbertas[pilhaAbertas.length - 1] === idJanela.current
  /** Clicar em qualquer ponto da janela a traz para cima (e ela passa a ser a do Esc). */
  const trazerParaFrente = () => {
    const id = idJanela.current
    const i = pilhaAbertas.indexOf(id)
    if (i < 0 || i === pilhaAbertas.length - 1) return
    pilhaAbertas.splice(i, 1)
    pilhaAbertas.push(id)
    avisarPilha()
  }
  /* Ver `pedidoDeFrente`. Declarado DEPOIS do efeito que empilha: no render em que a
     janela abre e o pedido muda juntos, ela ja' entra no topo e isto vira no-op. */
  const ultimoPedido = useRef(pedidoDeFrente)
  useEffect(() => {
    if (pedidoDeFrente === ultimoPedido.current) return
    ultimoPedido.current = pedidoDeFrente
    if (!aberta) return
    const id = idJanela.current
    const i = pilhaAbertas.indexOf(id)
    if (i < 0 || i === pilhaAbertas.length - 1) return
    pilhaAbertas.splice(i, 1)
    pilhaAbertas.push(id)
    avisarPilha()
  }, [pedidoDeFrente, aberta])

  /* Avisa ao trilho do mapa onde esta janela esta' (`lib/ocupacao-janelas`), para ele sair
     de baixo dela. Em pixels da TELA: o contêiner + a geometria — e nao o
     `getBoundingClientRect` da propria janela, que na transicao de abrir ainda esta'
     deslocada pelo `transform` e mediria a janela fora do lugar. Roda a cada render: o
     registro descarta retangulo repetido, entao arrastar acorda o trilho e o resto nao. */
  useLayoutEffect(() => {
    const id = idJanela.current
    const pai = ref.current?.parentElement
    if (!aberta || !atual || !pai) {
      removerJanela(id)
      return
    }
    const base = pai.getBoundingClientRect()
    registrarJanela(id, {
      esquerda: base.left + atual.x,
      topo: base.top + atual.y,
      largura: atual.largura,
      altura: alturaVisivel,
    })
  })
  useEffect(() => {
    const id = idJanela.current
    return () => removerJanela(id)
  }, [])

  return (
    <aside
      ref={ref}
      onPointerDownCapture={trazerParaFrente}
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
        zIndex: noTopo ? Z_JANELA_TOPO : Z_JANELA,
      }}
    >
      <header
        /* O arrasto respeita o cabeçalho do mapa (`topoMinimo`): a barra nunca passa por baixo dele. */
        onPointerDown={gesto((g, dx, dy, a) => mover(g, dx, dy, a, topoMinimo))}
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
          {/* SERIF: a voz narrativa dos títulos do produto (design "Paineis do Hexagono",
              2026-08-21). Vale para TODAS as janelas — hexágono, imóvel, comparação e
              ficha do ponto falam com a mesma cara. */}
          <span
            className="story"
            style={{
              font: '400 19px/1.15 var(--f-story)',
              color: 'var(--tx-max)',
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

      {/* O rodapé fixo. Depois do miolo rolável e com `flexShrink: 0`: o miolo cede a altura,
          o rodapé não. Some quando recolhida, como o miolo — a janela vira só a barra.
          O `paddingRight` maior deixa o canto inferior direito livre para a alça de
          redimensionar, que é desenhada por cima (vem depois na árvore): sem ele, o último
          botão ficaria sob a alça e o clique ali viraria redimensionamento. */}
      {!recolhida && rodape != null && (
        <div
          style={{
            flexShrink: 0,
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            padding: '12px 30px 12px 16px',
            borderTop: '1px solid var(--line-soft)',
            background: 'var(--surf-panel)',
          }}
        >
          {rodape}
        </div>
      )}

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
