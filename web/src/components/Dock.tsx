import type { Tela } from '../App'
import { telaLiberada, type Aba, type TelaControlada } from '../lib/acesso'

/* Dock vertical fixo. No piloto so as duas telas do escopo estao ativas; as
   demais aparecem desabilitadas para o operador entender que o mapa e a
   viabilidade sao um recorte, nao o produto inteiro. */

/* CARIMBO DE PAÍS — fica colado na logo, acima da navegação.

   O mesmo binário do piloto também é o que serve a base da Argentina (muda só o
   `MOTOR_DATA_DIR`; ver `piloto_rep/LEIA-ME.md` no repo Motor-Argentina). Sem
   carimbo as duas instâncias são idênticas na tela, e com as duas abertas o
   operador não sabe em qual está. Este é o carimbo do BRASIL, fixo.

   Não é botão e não tem hover: informa a identidade da instância, não é destino
   de clique. E a sigla escrita acompanha a bandeira porque cor sozinha não é
   acessível.

   Desenhada em SVG e não em PNG: entra no bundle, sobrevive offline, não borra em
   tela 2x e não pede um arquivo a mais ao servidor por 26px de imagem. */
const CARIMBO_BRASIL = (
  <div
    role="img"
    title="Base de dados: Brasil"
    aria-label="Motor de Expansão — Brasil"
    style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: 3,
      marginTop: -2,
      marginBottom: 8,
      flexShrink: 0,
    }}
  >
    <svg
      viewBox="0 0 24 17"
      width={26}
      height={18}
      role="img"
      aria-hidden="true"
      style={{
        borderRadius: 3,
        display: 'block',
        /* Anel claro em vez de sombra: o verde encosta no cromo escuro do Dock e
           sem ele a bandeira perde a silhueta de retângulo. */
        boxShadow: '0 0 0 1px rgba(255,255,255,.22)',
      }}
    >
      <rect width="24" height="17" rx="2" fill="#009b3a" />
      <path d="M12 2.2 21.4 8.5 12 14.8 2.6 8.5Z" fill="#ffdf00" />
      <circle cx="12" cy="8.5" r="3.4" fill="#002776" />
    </svg>
    <span
      style={{
        font: '600 8px/1 var(--f-ui)',
        letterSpacing: '.1em',
        color: 'var(--tx-off)',
        textTransform: 'uppercase',
      }}
    >
      BR
    </span>
  </div>
)

const ICONES: Record<string, React.JSX.Element> = {
  exec: (
    <>
      <path d="M4 19V9M10 19V5M16 19v-7M22 19H2" />
    </>
  ),
  dom: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <circle cx="12" cy="12" r="4" />
    </>
  ),
  cart: (
    <>
      <path d="M4 6h16M4 12h16M4 18h10" />
    </>
  ),
  viab: (
    <>
      <path d="M3 17l5.5-6 4 3.5L21 6" />
      <path d="M15 6h6v6" />
    </>
  ),
  /* Predio — a camada de oferta imobiliaria (imoveis de locacao coletados). */
  oport: (
    <>
      <path d="M3 21h18M5 21V7l7-4 7 4v14M9 9h.01M9 13h.01M9 17h.01M15 9h.01M15 13h.01M15 17h.01" />
    </>
  ),
  /* Pulso de atividade — o painel de acessos (restrito; some para quem não pode). */
  acessos: (
    <>
      <path d="M22 12h-3.5l-3 8-7-16-3 8H2" />
    </>
  ),
}

/**
 * O Dock NAO lista os MODOS DE ANALISE.
 *
 * "Análise de ponto" e "Explorar uma região" sairam daqui a pedido do Juan (2026-08-12):
 * eles sao escolha de PERGUNTA, e essa escolha se faz na tela de inicio, onde cada card
 * explica o que o modo responde e do que ele precisa. Repetidos como dois ícones sem
 * rótulo, viravam um segundo caminho mudo para a mesma decisão — e dois pinos quase
 * iguais, ainda por cima.
 *
 * O ícone de início tambem saiu: quem volta ao menu agora clica na LOGO, que ja estava
 * ali em cima e nao fazia nada.
 */
const ITENS: { id: string; tela: Tela | null; titulo: string }[] = [
  { id: 'exec', tela: 'executiva', titulo: 'Visão executiva' },
  { id: 'dom', tela: null, titulo: 'Expansão de domínio (fora do piloto)' },
  { id: 'cart', tela: null, titulo: 'Carteira e plano (fora do piloto)' },
  { id: 'oport', tela: 'oportunidades-imob', titulo: 'Oportunidades imobiliárias' },
  { id: 'viab', tela: 'viabilidade', titulo: 'Viabilidade do ponto' },
  /* Aba restrita (emenda DEC-027): telaLiberada e deny-by-default — para quem não
     está na allowlist o ícone simplesmente não existe, como toda tela vetada. */
  { id: 'acessos', tela: 'acessos', titulo: 'Acessos e uso do piloto' },
]

export default function Dock({
  tela,
  onTela,
  abas = null,
}: {
  tela: Tela
  onTela: (t: Tela) => void
  /** Abas permitidas ao usuário (controle temporário). `null` = sem controle. */
  abas?: Set<Aba> | null
}) {
  // Ícone de tela vetada SOME em vez de aparecer desabilitado: os desabilitados do
  // Dock já significam "fora do piloto", e um terceiro estado ("existe mas não para
  // você") só gastaria a paciência de quem não pode clicar de qualquer jeito.
  const itens = ITENS.filter(
    (it) => it.tela === null || telaLiberada(it.tela as TelaControlada, abas),
  )
  return (
    <nav
      aria-label="Navegação principal"
      style={{
        width: 70,
        flexShrink: 0,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 8,
        padding: '14px 8px',
        background: 'var(--surf-chrome)',
        borderRight: '1px solid var(--line-soft)',
        backdropFilter: 'blur(14px)',
        zIndex: 20,
      }}
    >
      {/* A LOGO É O INÍCIO. Ela já ocupava o topo do Dock sem fazer nada, enquanto um
          ícone de casinha logo abaixo fazia o trabalho — dois elementos para uma função,
          e o mais óbvio dos dois era o inerte. Clicar no logotipo para voltar ao começo é
          a convenção que todo site carrega há vinte anos. */}
      <button
        type="button"
        onClick={() => onTela('inicio')}
        title="Início — escolher a análise"
        aria-label="Início — escolher a análise"
        aria-current={tela === 'inicio' ? 'page' : undefined}
        style={{
          width: 42,
          height: 42,
          borderRadius: 11,
          overflow: 'hidden',
          marginBottom: 6,
          flexShrink: 0,
          background: '#fff',
          display: 'grid',
          placeItems: 'center',
          cursor: 'pointer',
          padding: 0,
          /* O anel diz que ela é o lugar onde você está — mesmo tratamento que os itens
             ativos do Dock recebem, para a logo não virar um botão sem estado. */
          boxShadow: tela === 'inicio' ? '0 0 0 2px var(--ac)' : 'none',
          transition: 'box-shadow .15s ease',
        }}
      >
        <img
          src="/logo-ultra.png"
          alt="Ultra Academia"
          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
        />
      </button>

      {CARIMBO_BRASIL}

      {itens.map((it) => {
        const ativo = it.tela !== null && it.tela === tela
        const disponivel = it.tela !== null
        return (
          <button
            key={it.id}
            type="button"
            title={it.titulo}
            aria-label={it.titulo}
            aria-current={ativo ? 'page' : undefined}
            disabled={!disponivel}
            onClick={() => it.tela && onTela(it.tela)}
            style={{
              width: 42,
              height: 42,
              borderRadius: 11,
              display: 'grid',
              placeItems: 'center',
              background: ativo ? 'var(--ac-a16)' : 'transparent',
              color: ativo
                ? 'var(--ac-text)'
                : disponivel
                  ? 'var(--tx-muted)'
                  : 'var(--tx-rank)',
              opacity: disponivel ? 1 : 0.5,
              transition: 'background .15s ease, color .15s ease',
            }}
          >
            <svg
              width="19"
              height="19"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              {ICONES[it.id]}
            </svg>
          </button>
        )
      })}
    </nav>
  )
}
