import type { ReactNode } from 'react'

/* ---------------------------------------------------------------------------
   TRILHO + PAINEL "CAMADAS DO MAPA" (Juan, 2026-09-02, sobre desenho do Claude
   Design — arquivo "Barra de Camadas do Mapa", opcao 2a).

   O QUE SUBSTITUIU. As chaves do mapa eram quatro botoes de largura cheia
   empilhados no canto inferior esquerdo (`PilulaRegua`, `PilulaIndependentes`,
   `PilulaImoveis` e o botao solto da comparacao). Num municipio com independentes
   E imoveis coletados isso empilhava quatro faixas de ~34px ENTRE o mapa e a
   legenda — ~136px de territorio coberto exatamente no canto em que o operador
   procura a legenda. Pior: a pilha mudava de altura conforme o recorte, entao a
   legenda subia e descia de lugar sozinha.

   O DESENHO. Um trilho vertical de icones, de altura CONSTANTE — ele nao muda
   quando as condicionais entram ou saem, e e' isso que da' ao canto um ponto de
   referencia fixo. As chaves moram num painel unico que abre a partir do
   primeiro icone. Fechado, o mapa perde so' os 46px do trilho.

   ERAM QUATRO icones (camadas, regua, comparar, legenda). Em 2026-10-14 o dono
   pediu as ferramentas do CLIQUE ao lado da regua, nesta ordem fixa: camadas,
   SELECIONAR PONTO, regua, ANALISAR GEOMETRIA, comparar, legenda. As tres do meio
   disputam o mesmo clique no mapa e por isso sao um estado so'
   (`lib/ferramenta-mapa`): ligar uma desliga a outra. A altura continua constante
   — o que cresceu foi a constante, nao a variacao.

   O TRILHO NAO REPETE O PAINEL — ele o ATALHA. `Ponto`, `Regua`, `Geometria` e `Comparar` sao a
   mesma chave que a linha correspondente do painel, e acendem juntas; o icone e' o
   caminho de um clique para quem ja sabe o que quer, o painel e' o caminho de quem
   esta procurando. Um trilho cujos icones abrissem coisas diferentes das que o
   painel lista seria dois vocabularios no mesmo canto.

   COMECA FECHADO. E' o argumento do proprio desenho ("o mapa so perde os 34px do
   trilho quando o painel esta fechado"): abrir por padrao gastaria ~200px de mapa
   toda vez, inclusive para quem nunca liga camada nenhuma. Quem procura acha pelo
   icone de camadas, que tem `title` e fica aceso enquanto o painel esta aberto.

   FUNDO OPACO, nunca translucido: estes elementos ficam SOBRE o mapa, e com fundo
   translucido a legenda de faixas atravessava o texto. `--surf-mapa` e' preto no
   tema escuro e branco chapado no claro — o que resolve e' a opacidade, nao a cor.
   --------------------------------------------------------------------------- */

/** Uma chave do painel. A identidade visual chega pronta: quem sabe a cor de cada
 *  camada e' quem a desenha no mapa, nao este componente. */
export interface ChaveDeCamada {
  id: string
  titulo: string
  /**
   * A linha de baixo, em mono. Muda com o estado, e e' onde mora a CONTAGEM:
   * apagada diz o que ha' para ver ("318 no recorte"), acesa diz o que esta na
   * tela ("312 · visível"). Sem ela o operador liga a camada sem saber se o
   * recorte tem 3 ou 300 pontos.
   */
  sub: string
  ligado: boolean
  onToggle: () => void
  /**
   * Chave do `ICONE` que representa esta camada (2026-09-23, pedido do Felipe).
   *
   * Opcional porque a ausência tem um comportamento útil e não é um erro: sem
   * ícone, a linha cai no ponto de 8px que era o desenho anterior. Uma chave nova
   * que esqueça o ícone continua legível em vez de abrir um buraco na linha.
   */
  icone?: keyof typeof ICONE | string
  /**
   * Silhueta de MARCA no lugar do traço — hoje só o símbolo do Wellhub na camada de
   * independentes (Felipe, 2026-09-23).
   *
   * É aplicada como MÁSCARA CSS, não como `<img>`, e a diferença é o pedido dele: "ao
   * invés de deixar ela rosa padrão, mude a cor para branco para seguir o padrão do
   * resto dos ícones". Máscara pinta a silhueta com `currentColor`, então a marca
   * obedece à MESMA regra de cor dos ícones de traço — branca apagada, acento acesa —
   * e acompanha a virada do tema claro sozinha. Uma imagem recolorida no arquivo
   * ficaria branca também no tema claro, onde branco é invisível.
   */
  mascara?: string | null
  /** Acento da camada: ponto, filete da linha acesa e trilho do switch. */
  cor: string
  /** O mesmo acento, na versao ja aprovada como COR DE TEXTO nos dois temas. */
  corTexto: string
  /** O acento com alpha, para o fundo da linha acesa sobre o painel opaco. */
  corRealce: string
}

const ICONE: Record<string, React.JSX.Element> = {
  /* Pilha de camadas — abre o painel. */
  camadas: (
    <>
      <path d="M12 3 3 8l9 5 9-5-9-5Z" />
      <path d="m3 13 9 5 9-5" />
    </>
  ),
  /* RÉGUA de verdade — corpo com marcações (Felipe, 2026-09-23: "transforme em uma
     régua de verdade, não duas setas"). A seta de duas pontas dizia "distância" como
     conceito; a régua diz o INSTRUMENTO, que é o que a chave liga. Vale para o trilho
     e para a linha do painel de uma vez, porque os dois leem esta mesma chave — o
     princípio de "o trilho atalha o painel, não o repete" continua valendo. */
  regua: (
    <>
      <rect x="2.5" y="8.5" width="19" height="7" rx="1.6" />
      <path d="M7.3 8.5v2.8M12 8.5v3.4M16.7 8.5v2.8" />
    </>
  ),
  /* ALFINETE com miolo — "Selecionar ponto" (2026-10-14). E' o pin de mapa que todo
     mundo reconhece, e nao a mira (`crosshair`): a mira ja' e' o CURSOR de qualquer
     ferramenta ligada, e repetir o mesmo desenho no botao nao diria qual ferramenta e'. */
  alvo: (
    <>
      <path d="M12 21s-6.2-5.6-6.2-10.2a6.2 6.2 0 0 1 12.4 0C18.2 15.4 12 21 12 21Z" />
      <circle cx="12" cy="10.8" r="2.3" />
    </>
  ),
  /* POLIGONO de cinco lados com os VERTICES marcados — "Analisar geometria" (DEC-071).
     Os vertices sao o que diz "voce desenha clicando ponto a ponto"; um poligono liso
     seria so' uma forma, e nao o gesto que a ferramenta pede. */
  poligono: (
    <>
      <path d="M12 3.5 20 9.3l-3 9.7H7l-3-9.7Z" />
      <circle cx="12" cy="3.5" r="1.4" fill="currentColor" />
      <circle cx="20" cy="9.3" r="1.4" fill="currentColor" />
      <circle cx="17" cy="19" r="1.4" fill="currentColor" />
      <circle cx="7" cy="19" r="1.4" fill="currentColor" />
      <circle cx="4" cy="9.3" r="1.4" fill="currentColor" />
    </>
  ),
  /* Dois quadros sobrepostos — comparar. */
  comparar: (
    <>
      <rect x="3" y="3" width="12" height="12" rx="2" />
      <path d="M9 21h10a2 2 0 0 0 2-2V9" />
    </>
  ),
  /* HEXÁGONO com meia tinta — as cores (o mapa de calor) dos hexágonos. A metade
     preenchida diz "cor"; o contorno inteiro diz que a grade continua mesmo sem ela. */
  hexagono: (
    <>
      <path d="M12 2.8 20 7.4v9.2l-8 4.6-8-4.6V7.4Z" />
      <path d="M12 2.8v18.4l-8-4.6V7.4Z" fill="currentColor" fillOpacity=".35" stroke="none" />
    </>
  ),
  /* Tres filetes — a legenda de faixas. */
  legenda: (
    <>
      <path d="M4 7h16M4 12h16M4 17h10" />
    </>
  ),
  /* --- Ícones das CHAVES do painel (2026-09-23, pedido do Felipe) -------------
     Substituíram o quadradinho de 8px que marcava cada linha. Com quatro chaves
     ele bastava; com a lista crescendo, um quadrado igual em todas as linhas só
     dizia "ligada/apagada" e obrigava a ler o título para saber do que se trata.

     Não inventei símbolos: estes espelham o vocabulário que o MAPA já usa para
     separar as camadas — rede é BANDEIRA (pin com logo), independente é
     MARCADOR pequeno e por baixo da bandeira (DEC-066). O painel passa a falar a
     mesma língua do desenho que ele liga e desliga. */
  /* HALTER — as academias de REDE. Diz ACADEMIA, que é o que a pessoa procura na
     lista; a versão anterior usava a bandeira do pin, que é a linguagem do mapa.
     Uma tentativa de tríplice sobreposto (para sugerir volume) foi desfeita a pedido
     do Felipe — o halter sozinho ficou. */
  halter: (
    <>
      <path d="M3 9.5v5M6 7.5v9M18 7.5v9M21 9.5v5" />
      <path d="M6 12h12" />
    </>
  ),
  /* Telhado + porta: o IMÓVEL disponível. */
  imoveis: (
    <>
      <path d="M4 11 12 4.5 20 11" />
      <path d="M6.2 10v9.5h11.6V10" />
      <path d="M10.3 19.5v-5h3.4v5" />
    </>
  ),
  /* Uma PESSOA — densidade demográfica é gente por km². */
  pessoa: (
    <>
      <circle cx="12" cy="7.8" r="3.3" />
      <path d="M5.4 20c0-3.7 2.9-6.2 6.6-6.2s6.6 2.5 6.6 6.2" />
    </>
  ),
  /* CÉDULA — a renda domiciliar. */
  dinheiro: (
    <>
      <rect x="2.5" y="6" width="19" height="12" rx="2" />
      <circle cx="12" cy="12" r="2.9" />
      <path d="M6 9.4v5.2M18 9.4v5.2" />
    </>
  ),
}

/**
 * Tamanho do ícone na linha do painel. 17 -> 20 em 2026-09-23 ("acho que dá pra
 * aumentar um pouco os ícones ainda").
 *
 * Constante porque o traço SVG e a logo em `<img>` têm de medir o mesmo: eram dois
 * literais `17` em ramos diferentes do mesmo `<span>`, e divergir faria a linha da
 * camada de independentes pular de altura em relação às outras.
 *
 * Fica ABAIXO dos 34px do botão do trilho de propósito — o trilho é alvo de clique,
 * a linha do painel é rótulo com alvo próprio (a linha inteira).
 */
const TAM_ICONE_CHAVE = 20

function BotaoTrilho({
  icone,
  titulo,
  aceso,
  desabilitado = false,
  cor = 'var(--ac-text)',
  onClick,
}: {
  icone: keyof typeof ICONE | string
  titulo: string
  aceso: boolean
  desabilitado?: boolean
  cor?: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={titulo}
      aria-label={titulo}
      aria-pressed={aceso}
      disabled={desabilitado}
      style={{
        width: 34,
        height: 34,
        display: 'grid',
        placeItems: 'center',
        borderRadius: 8,
        border: 'none',
        /* O icone carrega a `cor` SEMPRE (nao so' aceso) desde 2026-09-09 — o trilho
           alterna as cores padrao da Ultra como o Dock, e o aceso passou a se marcar
           pelo fundo tingido da propria cor. */
        background: aceso ? `color-mix(in srgb, ${cor} 16%, transparent)` : 'transparent',
        color: desabilitado ? 'var(--sinal-off)' : cor,
        opacity: desabilitado ? 0.45 : 1,
        cursor: desabilitado ? 'not-allowed' : 'pointer',
        transition: 'background .15s ease, color .15s ease',
      }}
    >
      <svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden
      >
        {ICONE[icone]}
      </svg>
    </button>
  )
}

/** Switch de 34x18. Desenhado aqui e nao com um `<input type=checkbox>` porque o
 *  chrome nativo do Chrome/Windows nao segue o tema — o mesmo motivo que ja tirou o
 *  `<select>` nativo do app (ver `components/Select.tsx`). */
function Switch({ ligado, cor }: { ligado: boolean; cor: string }) {
  return (
    <span
      aria-hidden
      style={{
        width: 34,
        height: 18,
        flex: '0 0 auto',
        marginLeft: 'auto',
        display: 'flex',
        alignItems: 'center',
        justifyContent: ligado ? 'flex-end' : 'flex-start',
        padding: 2,
        boxSizing: 'border-box',
        borderRadius: 9,
        background: ligado ? cor : 'var(--sinal-off)',
        transition: 'background .15s ease',
      }}
    >
      <span
        style={{
          width: 14,
          height: 14,
          borderRadius: 7,
          background: '#fff',
          boxShadow: '0 1px 2px rgba(0,0,0,.3)',
        }}
      />
    </span>
  )
}

function Linha({ chave }: { chave: ChaveDeCamada }) {
  const on = chave.ligado
  return (
    <button
      type="button"
      onClick={chave.onToggle}
      aria-pressed={on}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 11,
        width: '100%',
        textAlign: 'left',
        padding: '8px 13px 8px 12px',
        borderRadius: 8,
        border: 'none',
        cursor: 'pointer',
        background: on ? chave.corRealce : 'transparent',
        /* Filete no lado esquerdo em vez de borda inteira: com quatro linhas, quatro
           molduras viravam grade. O filete diz "esta acesa" sem fechar a linha. */
        boxShadow: on ? `inset 2px 0 0 ${chave.cor}` : 'none',
        transition: 'background .15s ease',
      }}
    >
      {/* Estado pela COR: acento quando acesa, texto normal quando apagada.
          APAGADA NÃO É `--sinal-off` desde 2026-09-23 — o cinza do ponto de 8px
          funcionava para uma marca de 8px, mas num ícone de 17px com traço de 1,7
          ele sumia contra o painel (Felipe: "difícil visualizar assim"). `--tx-max`
          é branco no tema escuro e escuro no claro, então "legível" não vira
          "invisível" quando o tema troca. Quem diz o estado continua sendo o switch,
          o filete e o fundo da linha — o ícone não precisava carregar isso sozinho. */}
      {chave.mascara ? (
        <span
          aria-hidden
          style={{
            width: TAM_ICONE_CHAVE,
            height: TAM_ICONE_CHAVE,
            flex: '0 0 auto',
            backgroundColor: on ? chave.cor : 'var(--tx-max)',
            maskImage: `url(${chave.mascara})`,
            WebkitMaskImage: `url(${chave.mascara})`,
            maskSize: 'contain',
            WebkitMaskSize: 'contain',
            maskRepeat: 'no-repeat',
            WebkitMaskRepeat: 'no-repeat',
            maskPosition: 'center',
            WebkitMaskPosition: 'center',
          }}
        />
      ) : chave.icone && ICONE[chave.icone] ? (
        <svg
          width={TAM_ICONE_CHAVE}
          height={TAM_ICONE_CHAVE}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          /* Traço um pouco mais fino que o do trilho (1,7): num ícone maior o mesmo
             peso de linha fica pesado ao lado do texto de 13px da linha. */
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden
          style={{ flex: '0 0 auto', color: on ? chave.cor : 'var(--tx-max)' }}
        >
          {ICONE[chave.icone]}
        </svg>
      ) : (
        <span
          aria-hidden
          style={{
            width: 8,
            height: 8,
            borderRadius: 2,
            flex: '0 0 auto',
            background: on ? chave.cor : 'var(--sinal-off)',
          }}
        />
      )}
      <span style={{ minWidth: 0 }}>
        <span
          style={{
            display: 'block',
            font: '600 13px/1.25 var(--f-ui)',
            color: 'var(--tx-max)',
          }}
        >
          {chave.titulo}
        </span>
        <span
          className="num"
          style={{
            display: 'block',
            marginTop: 2,
            font: '400 10.5px/1.2 var(--f-num)',
            color: on ? chave.corTexto : 'var(--tx-sub)',
          }}
        >
          {chave.sub}
        </span>
      </span>
      <Switch ligado={on} cor={chave.cor} />
    </button>
  )
}

/**
 * Uma linha ACESA do painel, sem chave: o mesmo desenho da `Linha` ligada (ícone na cor da
 * camada, título, sub em mono, filete e fundo tingidos), mas sem switch e sem clique. É o
 * cabeçalho de estado do painel do desenho ("Área desenhada · 1,2 km² · 4 vértices") — o
 * painel do desenho fala a mesma língua visual do de camadas, em vez de inventar outra.
 */
export function LinhaDeEstado({
  icone,
  titulo,
  sub,
  cor,
  corTexto,
  corRealce,
}: {
  icone: keyof typeof ICONE | string
  titulo: string
  sub: ReactNode
  cor: string
  corTexto: string
  corRealce: string
}) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 11,
        padding: '8px 13px 8px 12px',
        borderRadius: 8,
        background: corRealce,
        boxShadow: `inset 2px 0 0 ${cor}`,
      }}
    >
      <svg
        width={TAM_ICONE_CHAVE}
        height={TAM_ICONE_CHAVE}
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden
        style={{ flex: '0 0 auto', color: cor }}
      >
        {ICONE[icone]}
      </svg>
      <span style={{ minWidth: 0 }}>
        <span style={{ display: 'block', font: '600 13px/1.25 var(--f-ui)', color: 'var(--tx-max)' }}>
          {titulo}
        </span>
        <span
          className="num"
          style={{
            display: 'block',
            marginTop: 2,
            font: '400 10.5px/1.2 var(--f-num)',
            color: corTexto,
          }}
        >
          {sub}
        </span>
      </span>
    </div>
  )
}

/**
 * A CAIXA dos painéis do trilho — "Camadas do mapa" e "Desenhar área" (Vinicius, 2026-10-16:
 * a caixa do desenho deveria "ter as mesmas propriedades da caixa de camadas do mapa").
 *
 * Extraída para os dois painéis serem a MESMA caixa, e não duas cópias de estilo que
 * divergem no primeiro ajuste: fundo opaco do tema, borda, raio, sombra de balão, o
 * cabeçalho em mono maiúsculo com o × e o mesmo respiro. Os dois abrem no mesmo lugar, à
 * direita do trilho, e nunca juntos (`lib/painel-trilho`).
 */
export function PainelDoTrilho({
  rotulo,
  rotuloFechar,
  onFechar,
  children,
  rodape,
}: {
  /** O cabeçalho (vai em maiúsculas pelo CSS). Também é o `aria-label` do grupo. */
  rotulo: string
  /** `aria-label` do ×: diz o que fecha, e não só "Fechar". */
  rotuloFechar: string
  onFechar: () => void
  children: ReactNode
  /** Linha de estado no pé, separada por um filete (`RodapeDoPainel`). */
  rodape?: ReactNode
}) {
  return (
    <div
      role="group"
      aria-label={rotulo}
      style={{
        width: 330,
        flexShrink: 0,
        background: 'var(--surf-mapa)',
        border: '1px solid var(--linha-mapa)',
        borderRadius: 12,
        padding: '11px 8px 9px',
        /* `--sh-pop` e' o token do BALAO que flutua sobre o conteudo, e nao um
           preto cravado: no tema claro ele troca o preto por azul-tinta com menos
           alfa (ver tokens.css). Uma sombra preta chapada sobre o Positron seria a
           unica mancha escura da tela. */
        boxShadow: 'var(--sh-pop)',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 6px 8px 12px',
        }}
      >
        <span
          className="num"
          style={{
            font: '600 10.5px/1 var(--f-num)',
            letterSpacing: '.12em',
            textTransform: 'uppercase',
            color: 'var(--ac-text)',
          }}
        >
          {rotulo}
        </span>
        <button
          type="button"
          onClick={onFechar}
          title={rotuloFechar}
          aria-label={rotuloFechar}
          style={{
            width: 20,
            height: 20,
            display: 'grid',
            placeItems: 'center',
            borderRadius: 5,
            font: '400 15px/1 var(--f-ui)',
            color: 'var(--tx-muted)',
          }}
        >
          ×
        </button>
      </div>

      {children}

      {rodape}
    </div>
  )
}

/**
 * O pé do painel: filete em cima e texto mono pequeno. `pulso` acende o ponto que pisca (a
 * espera do raio de 1 km); `tom: 'erro'` pinta de negativo (a recusa do desenho, que é
 * `role="alert"`).
 */
export function RodapeDoPainel({
  children,
  pulso = false,
  tom = 'neutro',
}: {
  children: ReactNode
  pulso?: boolean
  tom?: 'neutro' | 'erro'
}) {
  return (
    <div
      className="num"
      role={tom === 'erro' ? 'alert' : undefined}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 7,
        margin: '6px 0 0',
        padding: '7px 12px 2px',
        borderTop: '1px solid var(--line-soft)',
        font: '400 10.5px/1.3 var(--f-num)',
        color: tom === 'erro' ? 'var(--neg)' : 'var(--tx-sub)',
      }}
    >
      {pulso && (
        <span
          aria-hidden
          style={{
            width: 8,
            height: 8,
            borderRadius: '50%',
            flexShrink: 0,
            background: 'var(--carga)',
            animation: 'pulse 1s ease-in-out infinite',
          }}
        />
      )}
      {children}
    </div>
  )
}

export default function BarraCamadas({
  chaves,
  selecionarPonto = null,
  regua,
  geometria = null,
  comparar,
  legendaVisivel,
  legendaDisponivel = true,
  onLegenda,
  aviso,
  camadasAberto,
  onAlternarCamadas,
  onFecharCamadas,
  painelDesenho = null,
}: {
  /** Todas as chaves do painel, na ordem fixa do desenho. */
  chaves: ChaveDeCamada[]
  /**
   * O painel de camadas está aberto. CONTROLADO por quem monta o trilho desde 2026-10-16:
   * ele divide o lugar com o painel do desenho e um fecha o outro (`lib/painel-trilho`),
   * então o estado tem de morar onde a ferramenta mora.
   */
  camadasAberto: boolean
  onAlternarCamadas: () => void
  onFecharCamadas: () => void
  /**
   * O painel do DESENHO ("Analisar geometria"), na MESMA caixa e no MESMO lugar do de
   * camadas. Presente = aberto (é a ferramenta ligada); o × dele PAUSA o desenho sem apagar
   * os vértices. Os dois nunca vêm juntos — se viessem, as camadas venceriam.
   */
  painelDesenho?: { conteudo: ReactNode; rodape?: ReactNode; onFechar: () => void } | null
  /**
   * Atalho do trilho para "Selecionar ponto" — a MESMA chave da linha do painel.
   * `null`/ausente = o botao nao aparece (quem monta o trilho sem a analise de pontos
   * nao oferece um botao que nao levaria a lugar nenhum).
   */
  selecionarPonto?: { ligado: boolean; onToggle: () => void } | null
  /** Atalho do trilho para a regua — a MESMA chave da linha correspondente. */
  regua: { ligado: boolean; onToggle: () => void }
  /**
   * Atalho do trilho para "Analisar geometria" (DEC-071) — a MESMA chave da linha do
   * painel. `null`/ausente = o botao nao aparece (sem quem receba a area desenhada, o
   * desenho nao levaria a lugar nenhum).
   */
  geometria?: {
    ligado: boolean
    onToggle: () => void
    /** Vértices guardados de um desenho PAUSADO (0 = nenhum): muda o título do botão. */
    pausado?: number
  } | null
  /** Idem para a comparacao. `null` = fora do drill-down, entao o icone fica inerte. */
  comparar: { ligado: boolean; onToggle: () => void } | null
  legendaVisivel: boolean
  /**
   * A legenda tem o que explicar? Com as cores dos hexágonos desligadas, não: ela traduz
   * cor, e sem cor some junto — o botão fica inerte e diz por quê.
   */
  legendaDisponivel?: boolean
  onLegenda: () => void
  /**
   * Linha de estado no pe do painel (hoje: a espera do raio de 1 km).
   *
   * No PAINEL e nao solta no mapa: o raio e' o que a camada 3 desenha, entao a
   * espera dele pertence ao lugar em que se fala de camada. Ausente = sem aviso.
   */
  aviso?: string | null
}) {
  const aberto = camadasAberto
  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 10, pointerEvents: 'auto' }}>
      {/* TRILHO — altura constante, sempre os mesmos icones, na ordem fixa do dono
          (2026-10-14): camadas, selecionar ponto, regua, analisar geometria, comparar,
          legenda.
          A caixa segue a superficie do TEMA: chegou a ficar escura no claro junto com
          o Dock (2026-09-09) e o Juan reverteu no mesmo dia — "na visão branca ele
          está preto, deixar branco". Quem carrega a cor aqui sao os ICONES. */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 4,
          padding: 6,
          borderRadius: 10,
          background: 'var(--surf-mapa)',
          border: '1px solid var(--linha-mapa)',
          flexShrink: 0,
        }}
      >
        <BotaoTrilho
          icone="camadas"
          titulo={aberto ? 'Fechar as camadas do mapa' : 'Camadas do mapa'}
          aceso={aberto}
          onClick={onAlternarCamadas}
        />
        {/* SELECIONAR PONTO — ACIMA da regua (pedido do dono). Cor PROPRIA, e nao o rosa
            da regua: as duas deixam o cursor em mira, e a cor do botao aceso e' o que diz
            qual das duas esta' esperando o clique. */}
        {selecionarPonto && (
          <BotaoTrilho
            icone="alvo"
            titulo={
              selecionarPonto.ligado
                ? 'Selecionar ponto ligado — clique no mapa para analisar o lugar (Esc desliga)'
                : 'Selecionar um ponto no mapa para analisar'
            }
            aceso={selecionarPonto.ligado}
            cor="var(--gr-azul)"
            onClick={selecionarPonto.onToggle}
          />
        )}
        <BotaoTrilho
          icone="regua"
          titulo={
            regua.ligado
              ? 'Régua ligada — clique na origem e no destino'
              : 'Medir a distância entre dois pontos do mapa'
          }
          aceso={regua.ligado}
          cor="var(--gr-rosa)"
          onClick={regua.onToggle}
        />
        {/* ANALISAR GEOMETRIA — logo ABAIXO da regua (posicao do dono, 2026-10-14). Verde,
            e nao o rosa da regua nem o azul do ponto: as tres poem o cursor em mira, e a
            cor do botao aceso e' o que diz qual delas espera o clique. O MESMO verde pinta
            o poligono em desenho no mapa. */}
        {geometria && (
          <BotaoTrilho
            icone="poligono"
            titulo={
              geometria.ligado
                ? 'Desenhando — clique os vértices da área; feche no 1º vértice ou em Concluir (Esc cancela). Clique de novo para pausar'
                : geometria.pausado
                  ? `Retomar o desenho da área (${geometria.pausado} ${geometria.pausado === 1 ? 'vértice guardado' : 'vértices guardados'})`
                  : 'Desenhar uma área no mapa para analisar'
            }
            aceso={geometria.ligado}
            cor="var(--gr-verde)"
            onClick={geometria.onToggle}
          />
        )}
        <BotaoTrilho
          icone="comparar"
          titulo={
            comparar
              ? comparar.ligado
                ? 'Comparando hexágonos — clique para somar mais'
                : 'Somar vários hexágonos num cenário'
              : 'Comparar hexágonos só dentro de um município'
          }
          aceso={comparar?.ligado ?? false}
          desabilitado={!comparar}
          cor="var(--gr-coral)"
          onClick={() => comparar?.onToggle()}
        />
        <BotaoTrilho
          icone="legenda"
          titulo={
            !legendaDisponivel
              ? 'Legenda escondida: nenhuma camada de cor está ligada'
              : legendaVisivel
                ? 'Esconder a legenda'
                : 'Mostrar a legenda'
          }
          aceso={legendaDisponivel && legendaVisivel}
          desabilitado={!legendaDisponivel}
          onClick={onLegenda}
        />
      </div>

      {/* PAINEL — some por inteiro quando fechado; o trilho e' que fica. Camadas OU
          desenho, na mesma caixa e no mesmo lugar (`lib/painel-trilho`). */}
      {aberto ? (
        <PainelDoTrilho
          rotulo="Camadas do mapa"
          rotuloFechar="Fechar as camadas do mapa"
          onFechar={onFecharCamadas}
          rodape={aviso ? <RodapeDoPainel pulso>{aviso}</RodapeDoPainel> : null}
        >
          {chaves.map((c) => (
            <Linha key={c.id} chave={c} />
          ))}
        </PainelDoTrilho>
      ) : painelDesenho ? (
        <PainelDoTrilho
          rotulo="Desenhar área"
          rotuloFechar="Pausar o desenho (os vértices ficam guardados)"
          onFechar={painelDesenho.onFechar}
          rodape={painelDesenho.rodape}
        >
          {painelDesenho.conteudo}
        </PainelDoTrilho>
      ) : null}
    </div>
  )
}
