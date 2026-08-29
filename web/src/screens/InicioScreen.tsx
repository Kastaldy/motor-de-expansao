import { MODOS, type ModoDefinicao, type ModoInicio } from '../lib/inicio'

/**
 * Tela de INICIO do piloto — a porta de entrada do produto.
 *
 * POR QUE ELA SOBE UM NIVEL. O hero "Por onde a Ultra deve crescer?" ja existia, mas
 * vivia DENTRO do `MapScreen` (a `Landing`, acionada por `if (!uf)`): era a porta de
 * entrada de UM produto (o Mapa), nao do produto. Ela perguntava "qual estado?", nunca
 * "qual analise?". Aqui a pergunta passa a ser a escolha do MODO, e a `Landing` do mapa
 * vira o passo seguinte, so' do modo de regiao — por isso o titulo dela encolheu.
 *
 * Esta tela nao busca dado nenhum e nao monta mapa: enquanto a tela ativa nao for
 * `'mapa'` com UF preenchida, deck.gl e MapLibre nem instanciam (`MapScreen.tsx:330`),
 * entao a entrada do app custa zero WebGL e zero leitura de particao de UF.
 *
 * O conteudo dos cards NAO esta aqui: mora em `lib/inicio.ts`, que e' testado.
 */
/** Fator do zoom desta tela. Um lugar só: o `zoom` e a compensação de tamanho
 *  têm de andar juntos, e separados eles saem de sincronia na primeira edição. */
const ZOOM = 0.75

export default function InicioScreen({
  onEscolher,
  modos = MODOS,
}: {
  onEscolher: (modo: ModoInicio) => void
  /** Cards visíveis para este usuário (controle temporário de acesso). */
  modos?: readonly ModoDefinicao[]
}) {
  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        /* ZOOM DE 75%, SÓ NESTA TELA (pedido do Juan, 2026-08-26).

           Fica no contêiner do Início e NÃO no `html`, de propósito. No `html` ele
           valeria para o app inteiro — e aí `getBoundingClientRect`/`innerHeight`
           (px VISUAIS) passam a divergir 25% de `clientWidth`/`contentRect`/estilos
           (px de CSS). O mapa, a Visão Executiva, as listas suspensas e o painel de
           acessos medem num espaço e aplicam no outro: medido, sete lugares passavam
           a errar, dois deles desfazendo correções feitas de propósito. Aqui dentro
           não existe nenhum: o Início é um grid de cartões, sem medição de tela.

           `inset: 0` NÃO precisa de compensação — a porcentagem já resolve no espaço
           zoomado (medido: com `width: 133%` o contêiner saía 1602 px onde o `main`
           tem 1202). O Dock e as demais telas seguem em 100%. */
        zoom: ZOOM,
        overflowY: 'auto',
        display: 'grid',
        placeItems: 'center',
        padding: '32px 24px',
        background:
          'radial-gradient(120% 90% at 50% 26%, var(--bg-lift) 0%, var(--bg-base) 72%)',
      }}
    >
      <div style={{ width: '100%', maxWidth: 1120 }}>
        {/* ---------------- Hero ---------------- */}
        <div style={{ textAlign: 'center', maxWidth: 620, margin: '0 auto' }}>
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
              font: '600 11px/1 var(--f-ui)',
              letterSpacing: '.14em',
              textTransform: 'uppercase',
              color: 'var(--ac-text)',
            }}
          >
            <span
              style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--ac)' }}
            />
            Inteligência de Expansão · Ultra Academia
          </span>

          <h1
            className="story"
            style={{
              font: '400 44px/1.05 var(--f-story)',
              color: 'var(--tx-max)',
              margin: '18px 0 0',
              letterSpacing: '.005em',
            }}
          >
            Por onde a Ultra deve crescer?
          </h1>

          <p
            style={{
              font: '400 15px/1.6 var(--f-ui)',
              color: 'var(--tx-narrative)',
              margin: '16px auto 0',
              maxWidth: 500,
            }}
          >
            Escolha por onde começar. Os três caminhos leem a{' '}
            <strong style={{ color: 'var(--tx-strong)' }}>mesma base</strong> — o que muda
            é a pergunta que você faz a ela.
          </p>
        </div>

        {/* ---------------- Os 3 modos ---------------- */}
        <div
          style={{
            marginTop: 34,
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(290px, 1fr))',
            gap: 16,
            alignItems: 'stretch',
          }}
        >
          {modos.map((modo) => (
            <CardModo key={modo.id} modo={modo} onEscolher={onEscolher} />
          ))}
          {modos.length === 0 && (
            /* Usuário sem nenhum modo de análise (ex.: acesso só à Visão Executiva).
               Ele normalmente nem pousa aqui — telaInicial() o leva direto —, mas a
               logo sempre traz de volta ao Início, e a tela não pode ficar muda. */
            <p
              style={{
                gridColumn: '1 / -1',
                textAlign: 'center',
                font: '400 14px/1.6 var(--f-ui)',
                color: 'var(--tx-narrative)',
                margin: '8px 0 0',
              }}
            >
              Seu usuário não tem acesso aos modos de análise — use o menu à esquerda
              para abrir as áreas liberadas para você.
            </p>
          )}
        </div>

        <p
          style={{
            font: '400 11.5px/1.5 var(--f-ui)',
            color: 'var(--tx-sub)',
            margin: '26px 0 0',
            textAlign: 'center',
          }}
        >
          27 estados · Censo 2022 (IBGE) + rede Ultra e concorrentes mapeados · camada
          visual read-only
        </p>
      </div>
    </div>
  )
}

/**
 * Card de um modo. O card INTEIRO e' o botao — nao um `<div>` com um `<button>` dentro:
 * assim o alvo de clique e o de foco sao o mesmo retangulo e o teclado percorre tres
 * paradas, uma por modo, em vez de tropecar em regioes clicaveis invisiveis.
 */
function CardModo({
  modo,
  onEscolher,
}: {
  modo: ModoDefinicao
  onEscolher: (modo: ModoInicio) => void
}) {
  return (
    <button
      type="button"
      onClick={() => onEscolher(modo.id)}
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'stretch',
        textAlign: 'left',
        gap: 12,
        padding: '20px 20px 18px',
        height: '100%',
        background: 'var(--surf-card)',
        border: '1px solid var(--line)',
        borderRadius: 'var(--r-lg)',
        backdropFilter: 'blur(14px)',
        transition: 'border-color .15s ease, transform .15s ease',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = 'var(--ac-a30)'
        e.currentTarget.style.transform = 'translateY(-2px)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = 'var(--line)'
        e.currentTarget.style.transform = 'none'
      }}
    >
      <span
        style={{
          font: '600 10.5px/1 var(--f-num)',
          textTransform: 'uppercase',
          letterSpacing: '.09em',
          color: 'var(--ac-text)',
        }}
      >
        {modo.eyebrow}
      </span>

      <span
        style={{
          font: '600 17px/1.25 var(--f-ui)',
          color: 'var(--tx-max)',
          letterSpacing: '-.01em',
        }}
      >
        {modo.titulo}
      </span>

      <span style={{ font: '400 13px/1.55 var(--f-ui)', color: 'var(--tx-narrative)' }}>
        {modo.resumo}
      </span>

      <ul
        style={{
          listStyle: 'none',
          margin: '2px 0 0',
          padding: 0,
          display: 'flex',
          flexDirection: 'column',
          gap: 6,
        }}
      >
        {modo.bullets.map((b) => (
          <li
            key={b}
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: 8,
              font: '400 12px/1.45 var(--f-ui)',
              color: 'var(--tx-soft)',
            }}
          >
            <span
              aria-hidden
              style={{
                width: 4,
                height: 4,
                borderRadius: '50%',
                background: 'var(--ac)',
                marginTop: 6,
                flexShrink: 0,
              }}
            />
            {b}
          </li>
        ))}
      </ul>

      {/* `marginTop: auto` cola a chamada no rodape: com resumos de alturas diferentes,
          os tres botoes continuam alinhados na mesma linha. */}
      <span
        style={{
          marginTop: 'auto',
          paddingTop: 14,
          display: 'inline-flex',
          alignItems: 'center',
          gap: 7,
          font: '700 13px/1 var(--f-ui)',
          color: 'var(--ac-text)',
        }}
      >
        {modo.chamada}
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden
        >
          <path d="M5 12h14M12 5l7 7-7 7" />
        </svg>
      </span>
    </button>
  )
}
