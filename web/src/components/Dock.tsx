import type { Tela } from '../App'
import BotaoTema from './BotaoTema'
import { telaLiberada, type Aba } from '../lib/acesso'
import { ITENS_DOCK } from '../lib/dock-itens'
import type { Tema } from '../lib/tema'

/* Dock vertical fixo. No piloto so as duas telas do escopo estao ativas; as
   demais aparecem desabilitadas para o operador entender que o mapa e a
   viabilidade sao um recorte, nao o produto inteiro.

   O alternador de tema mora no PE deste rail (2026-08-25), separado dos itens de
   navegacao por um empurrao de `marginTop: auto`. Ele nao e' um destino, e' um
   ajuste da tela inteira — misturado a' fila de icones viraria uma sexta "tela".
   O Dock e' o unico chrome que existe nas cinco, entao e' o unico lugar de onde
   UM botao alcanca o produto todo. */
/* CARIMBO DE PAÍS — fica colado na logo, acima da navegação.

   O mesmo binário do piloto também é o que serve a base da Argentina (muda só o
   `MOTOR_DATA_DIR`; ver `piloto_rep/LEIA-ME.md` no repo Motor-Argentina). Sem
   carimbo as duas instâncias são idênticas na tela, e com as duas abertas o
   operador não sabe em qual está.

   O CARIMBO SEGUE A BASE, e deixou de ser fixo no Brasil (Juan, 2026-08-26: "está
   com o ícone do Brasil… é da Argentina"). Fixo, ele ficava errado exatamente na
   instância em que a dúvida existe — e uma bandeira errada é pior do que nenhuma,
   porque é a leitura errada que este carimbo existe para evitar. Quem descobre o
   país é `lib/pais-da-base.ts`, a partir da lista de UFs que o app já carrega.

   País desconhecido (`null`) NÃO carimba nada: sem lista ainda, ou base misturada.

   Não é botão e não tem hover: informa a identidade da instância, não é destino
   de clique. E a sigla escrita acompanha a bandeira porque cor sozinha não é
   acessível — as duas bandeiras têm azul e branco em comum.

   Desenhada em SVG e não em PNG: entra no bundle, sobrevive offline, não borra em
   tela 2x e não pede um arquivo a mais ao servidor por 26px de imagem. */
const BANDEIRAS: Record<'BR' | 'AR', { nome: string; svg: React.JSX.Element }> = {
  BR: {
    nome: 'Brasil',
    svg: (
      <>
        <rect width="24" height="17" rx="2" fill="#009b3a" />
        <path d="M12 2.2 21.4 8.5 12 14.8 2.6 8.5Z" fill="#ffdf00" />
        <circle cx="12" cy="8.5" r="3.4" fill="#002776" />
      </>
    ),
  },
  AR: {
    nome: 'Argentina',
    svg: (
      <>
        <rect width="24" height="17" rx="2" fill="#74acdf" />
        <rect y="5.7" width="24" height="5.6" fill="#fff" />
        <circle cx="12" cy="8.5" r="1.9" fill="#f6b40e" />
      </>
    ),
  },
}

function Carimbo({ pais }: { pais?: string | null }) {
  // Sigla sem bandeira desenhada (a Colombia, quando entrar) nao carimba nada — a
  // tabela e dado, e acrescentar pais e acrescentar uma entrada.
  const bandeira = pais && pais in BANDEIRAS ? BANDEIRAS[pais as keyof typeof BANDEIRAS] : undefined
  if (!bandeira) return null
  return (
  <div
    role="img"
    title={`Base de dados: ${bandeira.nome}`}
    aria-label={`Motor de Expansão — ${bandeira.nome}`}
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
        /* Anel claro em vez de sombra: o verde do Brasil e a faixa branca da
           Argentina encostam no cromo escuro do Dock, e sem ele a bandeira perde
           a silhueta de retângulo. */
        boxShadow: '0 0 0 1px rgba(255,255,255,.22)',
      }}
    >
      {bandeira.svg}
    </svg>
    <span
      style={{
        font: '600 8px/1 var(--f-ui)',
        letterSpacing: '.1em',
        /* `--tx-muted`, e nao `--tx-off`: medido contra o cromo do Dock (#101822),
           --tx-off da 3,06:1 e --tx-sub 4,37:1 — os dois abaixo do minimo AA de 4,5
           para texto pequeno; --tx-muted da 4,88:1. A sigla existe JUSTAMENTE porque
           cor sozinha nao e' acessivel, entao ela ilegivel anula o proprio motivo de
           estar ali. (`--tx-off` continua certo no lugar dele: rotulo decorativo, que
           esta nao e'.) */
        color: 'var(--tx-muted)',
        textTransform: 'uppercase',
      }}
    >
      {pais}
    </span>
  </div>
  )
}

const ICONES: Record<string, React.JSX.Element> = {
  /* Mapa dobrado — o atalho do Mapa Territorial (o "Explorar uma região" do Início). */
  mapa: (
    <>
      <path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2Z" />
      <path d="M9 4v14M15 6v14" />
    </>
  ),
  /* Carteira de BOLSO (porta-notas com o fecho) — a carteira da rede, coração da
     Visão Executiva (Juan, 2026-09-09: "quero uma carteira de bolso"; a maleta e as
     barrinhas anteriores não liam como carteira). */
  exec: (
    <>
      <path d="M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1" />
      <path d="M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4" />
    </>
  ),
  /* Cifrão — viabilidade é a conta do dinheiro (Juan, 2026-09-09: "algo que remeta
     dinheiro"; antes era uma linha de tendência). */
  viab: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M15.5 9.3c-.5-.9-1.9-1.5-3.5-1.5-1.9 0-3.2.9-3.2 2.1 0 3 6.9 1.5 6.9 4.4 0 1.2-1.5 2.1-3.5 2.1-1.7 0-3.2-.7-3.7-1.7" />
      <path d="M12 5.8v12.4" />
    </>
  ),
  /* Casa com uma pessoa ao lado (o icone classico de corretor) — a camada de oferta
     imobiliaria (Juan, 2026-09-09, sobre referencia de busca de "icone de imoveis";
     antes era um predio pontilhado, que lia como "cidade" e nao como "imovel"). */
  oport: (
    <>
      <circle cx="6.3" cy="9.6" r="2.3" />
      <path d="M2.8 20v-2.1a3.5 3.5 0 0 1 7 0V20" />
      <path d="M12.5 20v-8.4l4.75-3.9L22 11.6V20" />
      <path d="M15.4 20v-4.2h3.7V20" />
      <path d="M2 20h20" />
    </>
  ),
  /* Pulso de atividade — o painel de acessos (restrito; some para quem não pode). */
  acessos: (
    <>
      <path d="M22 12h-3.5l-3 8-7-16-3 8H2" />
    </>
  ),
}

/* A fila de destinos (que itens existem, em que ordem, para onde levam) vive em
   `lib/dock-itens.ts`, testável sem DOM — este componente só desenha o que está
   declarado lá, com os ícones daqui (SVG é desenho, não regra). */

/* Cada destino tem a SUA cor, fixa (Juan, 2026-09-09). Começou como alternância por
   posição na fila, mas posição mente: com o gate de abas escondendo itens, o mesmo
   destino mudava de cor conforme quem olhava — e o pedido seguinte já falava do
   "botão laranja" pelo destino. Verde na viabilidade é semântica ("como dinheiro
   mesmo"), laranja nas oportunidades, turquesa no mapa, magenta na executiva, azul
   nos acessos. Tokens da paleta de série: cada tema entrega o contraste certo. */
const COR_ICONE: Record<string, string> = {
  mapa: 'var(--ac-text)',
  exec: 'var(--gr-rosa)',
  oport: 'var(--gr-coral)',
  viab: 'var(--gr-verde)',
  acessos: 'var(--gr-azul)',
}

export default function Dock({
  tela,
  onTela,
  abas = null,
  tema,
  onTema,
  pais = null,
}: {
  tela: Tela
  onTela: (t: Tela) => void
  /** Abas permitidas ao usuário (controle temporário). `null` = sem controle. */
  abas?: Set<Aba> | null
  tema: Tema
  onTema: (t: Tema) => void
  /** País da base servida. `null` = ainda não dá para afirmar -> não carimba. */
  pais?: string | null
}) {
  // Ícone de tela vetada SOME em vez de aparecer desabilitado: um ícone apagado não
  // diz por que está apagado, e "existe mas não para você" só gastaria a paciência de
  // quem não pode clicar de qualquer jeito. (Foi também o que condenou os dois itens
  // "fora do piloto" que viviam aqui — ver ITENS_DOCK em lib/dock-itens.ts.)
  const itens = ITENS_DOCK.filter((it) => it.tela === null || telaLiberada(it.tela, abas))
  return (
    <nav
      aria-label="Navegação principal"
      className="cromo-escuro"
      style={{
        width: 70,
        flexShrink: 0,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 8,
        padding: '14px 8px',
        /* Rail sempre ESCURO com lavagem turquesa — a classe `cromo-escuro` (tokens.css)
           mantém o cromo escuro mesmo no tema claro (Juan, 2026-09-09: a barra lateral
           clara ficou ruim em todas as lavagens de cor; a caixa escura resolveu). */
        background: 'linear-gradient(180deg, var(--rail-a16), var(--rail-a08)), var(--surf-chrome)',
        borderRight: '1px solid var(--rail-a24)',
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

      <Carimbo pais={pais} />

      {itens.map((it) => {
        const ativo = it.tela !== null && it.tela === tela
        const disponivel = it.tela !== null
        const cor = COR_ICONE[it.id] ?? 'var(--ac-text)'
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
              /* O ativo se marca pelo FUNDO (tinta da própria cor do ícone), já que a
                 cor sozinha deixou de dizer "você está aqui" quando todos ganharam uma. */
              background: ativo ? `color-mix(in srgb, ${cor} 16%, transparent)` : 'transparent',
              color: disponivel ? cor : 'var(--tx-rank)',
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

      {/* `marginTop: auto` empurra o alternador para o pé do rail: ele fica longe da
          fila de destinos, que é o que o separa de uma sexta tela. */}
      <div style={{ marginTop: 'auto' }}>
        <BotaoTema tema={tema} onTema={onTema} />
      </div>
    </nav>
  )
}
