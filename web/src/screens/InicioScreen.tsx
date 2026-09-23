import { useEffect, useState } from 'react'

import Arte from '../components/inicio/Artes'
import {
  PassoEndereco,
  PassoRecorte,
  PassoUf,
  PassoUnidade,
} from '../components/inicio/Passos'
import {
  MODOS,
  SUBTITULO_AMBAS,
  TRILHAS,
  modosDaTrilha,
  trilhaInicial,
  trilhasDisponiveis,
  type EntradaInicio,
  type ModoDefinicao,
  type ModoInicio,
  type TrilhaInicio,
} from '../lib/inicio'
import { useUfsDaBase } from '../lib/base-contexto'
import { rodapeDaBase } from '../lib/rodape-base'

/**
 * Tela de INICIO do piloto — a porta de entrada do produto.
 *
 * POR QUE ELA SOBE UM NIVEL. O hero "Por onde a Ultra deve crescer?" ja existia, mas
 * vivia DENTRO do `MapScreen` (a `Landing`, acionada por `if (!uf)`): era a porta de
 * entrada de UM produto (o Mapa), nao do produto. Ela perguntava "qual estado?", nunca
 * "qual analise?". Aqui a pergunta passa a ser a escolha do MODO, e a `Landing` do mapa
 * vira o passo seguinte, so' do modo de regiao.
 *
 * AS DUAS TRILHAS (2026-09-22, mockup "Inicio · Expansao + Operacoes"). Ate' aqui todo
 * card era de EXPANSAO, e quem so' tinha a Visao Executiva pousava numa tela literalmente
 * vazia — `modosLiberados` nao achava um card sequer para ele. Agora a entrada pergunta
 * primeiro QUAL PERGUNTA ("expandir a rede" x "acompanhar a rede") e so' depois em que
 * escala. A pilula de trilha so' aparece para quem tem as DUAS: com uma so', a escolha
 * nao existe e um seletor de um item so' seria ruido.
 *
 * Esta tela nao busca dado nenhum e nao monta mapa: enquanto a tela ativa nao for
 * `'mapa'` com UF preenchida, deck.gl e MapLibre nem instanciam (`MapScreen.tsx:330`),
 * entao a entrada do app custa zero WebGL e zero leitura de particao de UF.
 *
 * O conteudo dos cards NAO esta aqui: mora em `lib/inicio.ts`, que e' testado; as
 * ilustracoes, em `components/inicio/Artes.tsx`.
 */
export default function InicioScreen({
  onEscolher,
  modos = MODOS,
}: {
  /** `entrada` só vem dos cards que fazem um segundo passo antes de navegar. */
  onEscolher: (modo: ModoInicio, entrada?: EntradaInicio) => void
  /** Cards visíveis para este usuário (controle de acesso por aba, `lib/acesso.ts`). */
  modos?: readonly ModoDefinicao[]
}) {
  const ufs = useUfsDaBase()
  const disponiveis = trilhasDisponiveis(modos)
  const [trilha, setTrilha] = useState<TrilhaInicio | null>(() => trilhaInicial(modos))

  /* As abas chegam DEPOIS da primeira pintura (`/api/me` é assíncrono), então a trilha
     escolhida na montagem pode deixar de existir — é o caso de quem só tem a Executiva:
     ele nasce com `expansao` (fail-open) e, quando a resposta chega, essa trilha some.
     Sem isto a tela ficaria mostrando a pergunta errada, sem card nenhum embaixo. */
  useEffect(() => {
    setTrilha((atual) => (atual && disponiveis.includes(atual) ? atual : (disponiveis[0] ?? null)))
    // `join` e não o array: `trilhasDisponiveis` devolve um array novo a cada render.
  }, [disponiveis.join('|')]) // eslint-disable-line react-hooks/exhaustive-deps

  const cards = trilha ? modosDaTrilha(trilha, modos) : []
  const duasTrilhas = disponiveis.length > 1
  const subtitulo = duasTrilhas
    ? SUBTITULO_AMBAS
    : trilha
      ? TRILHAS[trilha].subtitulo
      : ''

  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        overflowY: 'auto',
        display: 'flex',
        flexDirection: 'column',
        gap: 32,
        boxSizing: 'border-box',
        padding: '48px 56px 28px',
        background:
          'radial-gradient(120% 90% at 50% 0%, var(--bg-lift) 0%, var(--bg-base) 60%)',
      }}
    >
      {/* ---------------- Hero ---------------- */}
      <header
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 12,
          textAlign: 'center',
        }}
      >
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 8,
            font: '600 11px/1 var(--f-num)',
            letterSpacing: '.12em',
            textTransform: 'uppercase',
            color: 'var(--ac-text)',
          }}
        >
          <span
            aria-hidden
            style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--ac)' }}
          />
          Inteligência de expansão · Ultra Academia
        </span>

        <h1
          className="story"
          style={{
            font: '400 46px/1.1 var(--f-story)',
            color: 'var(--tx-max)',
            margin: 0,
            letterSpacing: '.005em',
          }}
        >
          Por onde você quer começar?
        </h1>

        {subtitulo && (
          <p
            style={{
              font: '400 15px/1.55 var(--f-ui)',
              color: 'var(--tx-narrative)',
              margin: 0,
              maxWidth: 620,
            }}
          >
            {subtitulo}
          </p>
        )}
      </header>

      {/* ---------------- Pílula de trilha ---------------- */}
      {duasTrilhas && trilha && (
        <div style={{ display: 'flex', justifyContent: 'center' }}>
          <div
            role="group"
            aria-label="O que você quer fazer"
            style={{
              display: 'flex',
              gap: 4,
              padding: 4,
              background: 'var(--surf-card)',
              border: '1px solid var(--line)',
              borderRadius: 999,
            }}
          >
            {disponiveis.map((t) => (
              <BotaoTrilha
                key={t}
                trilha={t}
                ativa={t === trilha}
                onEscolher={() => setTrilha(t)}
              />
            ))}
          </div>
        </div>
      )}

      {/* ---------------- Os cards da trilha ativa ---------------- */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
          gap: 24,
          /* `stretch` alinha o pé dos três cards quando uma descrição quebra em duas
             linhas e as outras não. Só volta a ser seguro porque a altura agora vem da
             PROPORÇÃO do quadro (ver `RAZAO_ARTE`) e não da sobra vertical da tela: o
             que sobra aqui é a diferença de uma linha de texto, não a faixa vazia de
             ~100px que aparecia quando o card era esticado para preencher a tela. */
          alignItems: 'stretch',
          /* Teto de largura para o card não virar um painel deitado em monitor largo: a
             proporção do quadro é fixa, então largura demais vira altura demais. É a
             largura útil do artboard do mockup (1440 - dock - margens), com folga. */
          width: '100%',
          maxWidth: 1320,
          margin: '0 auto',
        }}
      >
        {cards.map((modo) => (
          <CardModo key={modo.id} modo={modo} onEscolher={onEscolher} ufs={ufs} />
        ))}
      </div>

      {cards.length === 0 && (
        /* Usuário sem nenhum card em nenhuma trilha. Ele normalmente nem pousa aqui —
           `telaInicial()` o leva direto —, mas a logo sempre traz de volta ao Início, e
           a tela não pode ficar muda. */
        <p
          style={{
            textAlign: 'center',
            font: '400 14px/1.6 var(--f-ui)',
            color: 'var(--tx-narrative)',
            margin: 0,
          }}
        >
          Seu usuário não tem acesso aos modos de análise — use o menu à esquerda para
          abrir as áreas liberadas para você.
        </p>
      )}

      <div style={{ flexGrow: 1 }} />

      <footer style={{ textAlign: 'center', display: 'grid', gap: 10 }}>
        {/* Quem só tem operações não tem por onde pedir um ponto novo dentro do produto:
            a ponte é humana, e a linha diz isso em vez de oferecer um card que o
            controle de acesso iria barrar. Não é link: não há endereço canônico do time
            declarado no repo, e inventar um manda e-mail para o vazio. */}
        {trilha === 'operacoes' && !disponiveis.includes('expansao') && (
          <p
            style={{
              font: '400 13px/1.5 var(--f-ui)',
              color: 'var(--tx-narrative)',
              margin: 0,
            }}
          >
            Quer avaliar um ponto novo para abrir uma unidade?{' '}
            <strong style={{ color: 'var(--tx-strong)' }}>Fale com o time de Expansão.</strong>
          </p>
        )}

        {/* Sem base carregada nao ha' procedencia a declarar — o <p> inteiro sai, em vez
            de anunciar "0 estados". */}
        {rodapeDaBase(ufs) && (
          <p style={{ font: '400 12px/1.5 var(--f-ui)', color: 'var(--tx-sub)', margin: 0 }}>
            {rodapeDaBase(ufs)}
          </p>
        )}
      </footer>
    </div>
  )
}

/* ---------------------------------------------------------------------------
   Pílula de trilha
   --------------------------------------------------------------------------- */

const ICONE_TRILHA: Record<TrilhaInicio, React.JSX.Element> = {
  // Mapa dobrado: o território, que é o objeto da expansão.
  expansao: (
    <>
      <path d="M9 4L3 6v14l6-2 6 2 6-2V4l-6 2-6-2z" />
      <path d="M9 4v14" />
      <path d="M15 6v14" />
    </>
  ),
  // Cartela/painel: a rede que já existe, lida por indicadores.
  operacoes: (
    <>
      <rect x="3" y="6" width="18" height="13" rx="2" />
      <path d="M3 10h18" />
      <path d="M16 14h2" />
    </>
  ),
}

function BotaoTrilha({
  trilha,
  ativa,
  onEscolher,
}: {
  trilha: TrilhaInicio
  ativa: boolean
  onEscolher: () => void
}) {
  const cheia = trilha === 'expansao' ? 'var(--ac)' : 'var(--ops)'
  const sobre = trilha === 'expansao' ? 'var(--ac-on)' : 'var(--ops-on)'
  return (
    <button
      type="button"
      onClick={onEscolher}
      aria-pressed={ativa}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        height: 44,
        padding: '0 20px',
        border: 0,
        borderRadius: 999,
        font: '700 14px/1 var(--f-ui)',
        cursor: 'pointer',
        background: ativa ? cheia : 'transparent',
        color: ativa ? sobre : 'var(--tx-narrative)',
        transition: 'background .15s ease, color .15s ease',
      }}
    >
      <svg
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden
      >
        {ICONE_TRILHA[trilha]}
      </svg>
      <span>{TRILHAS[trilha].rotulo}</span>
    </button>
  )
}

/* ---------------------------------------------------------------------------
   Card de um modo
   --------------------------------------------------------------------------- */

/** Proporção do quadro da ilustração, tirada do mockup: 378 de largura útil (card de
 *  410 menos os 16+16 de recheio) por 300 de altura. */
const RAZAO_ARTE = '378 / 300'

/**
 * Card de um modo, em ATE' DOIS passos.
 *
 * FECHADO, o card INTEIRO e' o botao — nao um `<div>` com um `<button>` dentro: assim o
 * alvo de clique e o de foco sao o mesmo retangulo e o teclado percorre tres paradas,
 * uma por card, em vez de tropecar em regioes clicaveis invisiveis.
 *
 * ABERTO (so' nos cards de operacoes com `segundoPasso`), ele deixa de ser botao e vira
 * um `<div>`: o painel de escolha tem controles proprios, e botao dentro de botao nao e'
 * HTML valido — o navegador desfaz o aninhamento e o clique interno vira clique no card.
 * A troca e' no ELEMENTO, nao so' no estilo, exatamente por isso.
 */
function CardModo({
  modo,
  onEscolher,
  ufs,
}: {
  modo: ModoDefinicao
  onEscolher: (modo: ModoInicio, entrada?: EntradaInicio) => void
  /** Estados da base, para o painel de "Explorar uma região" não precisar buscar nada. */
  ufs: readonly string[]
}) {
  const [aberto, setAberto] = useState(false)
  const acento = modo.trilha === 'expansao' ? 'var(--ac-text)' : 'var(--ops-text)'
  const borda = modo.trilha === 'expansao' ? 'var(--ac-a30)' : 'var(--ops)'
  const temPasso = modo.segundoPasso !== null

  /* Esc fecha o passo aberto — o mesmo gesto que fecha a ficha da unidade na Visão
     Executiva. Quem abriu por engano não deveria ter de procurar o X. */
  useEffect(() => {
    if (!aberto) return
    const aoTeclar = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setAberto(false)
    }
    window.addEventListener('keydown', aoTeclar)
    return () => window.removeEventListener('keydown', aoTeclar)
  }, [aberto])

  const estilo: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'stretch',
    textAlign: 'left',
    gap: 14,
    padding: 16,
    height: '100%',
    boxSizing: 'border-box',
    background: 'var(--surf-card)',
    border: `1px solid ${aberto ? borda : 'var(--line)'}`,
    borderRadius: 18,
    backdropFilter: 'blur(14px)',
    transition: 'border-color .15s ease, transform .15s ease',
  }

  const corpo = (
    <>
      {/* Quadro da ilustração: PROPORÇÃO, não altura cravada.

          Os 300px do mockup valiam para o artboard de 1440x920 dele. Aplicados direto,
          viravam card achatado em notebook; amarrados à sobra vertical da tela, deixavam
          uma faixa vazia no pé do card quando sobrava espaço. A proporção resolve os
          dois: o quadro acompanha a largura da coluna e reproduz o mockup exatamente na
          largura em que ele foi desenhado.

          `vh` foi tentado e está errado aqui: o app renderiza reduzido (`--escala-app`,
          0,85) e `vh` mede a janela REAL, não o espaço em px de CSS onde o card vive —
          media 15% a menos.

          ABERTO, é este mesmo quadro que hospeda o painel de escolha — daí o
          `position: relative`. O porquê de ser aqui está no cabeçalho de `Passos.tsx`. */}
      <span
        style={{
          position: 'relative',
          aspectRatio: RAZAO_ARTE,
          borderRadius: 12,
          background: 'var(--bg-base)',
          border: '1px solid var(--line-soft)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: 8,
          boxSizing: 'border-box',
        }}
      >
        {!aberto ? (
          <Arte nome={modo.arte} />
        ) : modo.segundoPasso === 'uf' ? (
          <PassoUf ufs={ufs} onEscolher={(e) => onEscolher(modo.id, e)} />
        ) : modo.segundoPasso === 'endereco' ? (
          <PassoEndereco onEscolher={(e) => onEscolher(modo.id, e)} />
        ) : modo.segundoPasso === 'recorte' ? (
          <PassoRecorte onEscolher={(e) => onEscolher(modo.id, e)} />
        ) : modo.segundoPasso === 'unidade' ? (
          <PassoUnidade onEscolher={(e) => onEscolher(modo.id, e)} />
        ) : (
          <Arte nome={modo.arte} />
        )}
      </span>

      <span style={{ display: 'flex', flexDirection: 'column', gap: 6, padding: '0 6px 6px' }}>
        <span
          style={{
            font: '600 11px/1 var(--f-num)',
            letterSpacing: '.12em',
            textTransform: 'uppercase',
            color: acento,
          }}
        >
          {modo.eyebrow}
        </span>

        <span
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
          }}
        >
          <span
            style={{
              font: '700 21px/1.2 var(--f-ui)',
              color: 'var(--tx-max)',
              letterSpacing: '-.01em',
            }}
          >
            {modo.titulo}
          </span>
          {aberto ? (
            <button
              type="button"
              aria-label="Fechar"
              onClick={() => setAberto(false)}
              style={{
                display: 'flex',
                border: 0,
                background: 'transparent',
                padding: 0,
                cursor: 'pointer',
                color: acento,
                flexShrink: 0,
              }}
            >
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden
              >
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
            </button>
          ) : (
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke={acento}
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden
              style={{ flexShrink: 0 }}
            >
              <path d="M5 12h14" />
              <path d="M13 6l6 6-6 6" />
            </svg>
          )}
        </span>

        <span style={{ font: '400 15px/1.5 var(--f-ui)', color: 'var(--tx-narrative)' }}>
          {modo.linha}
        </span>
      </span>
    </>
  )

  if (aberto) return <div style={estilo}>{corpo}</div>

  return (
    <button
      type="button"
      /* Card COM segundo passo nao navega no clique: ele abre a escolha. Quem navega e'
         o painel, com a entrada ja' preenchida. */
      onClick={() => (temPasso ? setAberto(true) : onEscolher(modo.id))}
      style={{ ...estilo, cursor: 'pointer' }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = borda
        e.currentTarget.style.transform = 'translateY(-2px)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = 'var(--line)'
        e.currentTarget.style.transform = 'none'
      }}
    >
      {corpo}
    </button>
  )
}
