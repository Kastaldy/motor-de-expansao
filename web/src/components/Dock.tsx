import type { Tela } from '../App'
import BotaoSair from './BotaoSair'
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
      /* `gap: 3` é INTERNO — separa a bandeira da sigla dentro do carimbo, e não tem
         relação com o afastamento externo. Anotado porque os dois já foram confundidos.

         AS MARGENS EXTERNAS são IGUAIS dos dois lados (2026-09-25). Antes eram três
         ajustes avulsos empilhados sobre o `gap: 8` do rail — a logo com
         `marginBottom: 6`, o carimbo com `marginTop: -2` e `marginBottom: 8` —, o que
         dava 12px numa junta e 16px na outra. Zerar tudo deixou as duas em 8px, e aí o
         carimbo ficou COLADO na logo, que é grande. Os 8px daqui somam ao gap e devolvem
         16px de cada lado: afastado da logo, afastado do bloco, e simétrico. */
      gap: 3,
      marginTop: 8,
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
/* ÍCONES BRANCOS (2026-09-25, pedido do Felipe). Cada destino tinha a sua cor —
   turquesa, rosa, coral, verde, azul —, e isso nasceu quando o rail era escuro e
   neutro: ali as cinco cores separavam os destinos sem brigar com nada.

   Sobre o rail ROSA da marca elas deixam de funcionar por duas razões. A primeira é de
   marca: o guia autoriza no máximo DUAS cores de destaque por peça (aqui, turquesa +
   rosa), e cinco ícones coloridos sobre um fundo de marca são cinco cores numa peça
   só. A segunda é de leitura: o ícone `exec` era `--gr-rosa`, a mesma família do fundo
   novo — ele desapareceria dentro dele.

   Branco resolvia as duas: é a cor que o sistema interno da Ultra usa sobre a barra, e
   quem marca o item ativo é o VÉU de fundo, que já existia.

   O LARANJA FOI TESTADO E DESCARTADO (2026-09-25). Medido antes de aplicar e
   confirmado no olho: o laranja da marca sobre o teal do rail dá **1,92:1**, contra o
   mínimo de 3:1 da WCAG para elemento gráfico — as duas cores têm luminância parecida
   e se anulam em vez de se separarem. Clarear não salvava (2,58 no mais claro). Some-se
   a isso que o par rail teal + ícone laranja + card magenta poria as TRÊS cores de
   marca na mesma tela, a única combinação que o guia proíbe. */
const COR_ICONE_BRANCO = 'var(--tx-max)'

export default function Dock({
  tela,
  onTela,
  abas = null,
  tema,
  onTema,
  pais = null,
  onSenha,
}: {
  tela: Tela
  onTela: (t: Tela) => void
  /** Abas permitidas ao usuário (controle temporário). `null` = sem controle. */
  abas?: Set<Aba> | null
  tema: Tema
  onTema: (t: Tema) => void
  /** País da base servida. `null` = ainda não dá para afirmar -> não carimba. */
  pais?: string | null
  /** Abre a troca da própria senha. AUSENTE = o botão não existe — é o que acontece
   *  quando o banco não respondeu ou a pessoa não tem cadastro: um atalho que abre um
   *  formulário fadado a 409 seria pior que atalho nenhum. */
  onSenha?: () => void
}) {
  // Ícone de tela vetada SOME em vez de aparecer desabilitado: um ícone apagado não
  // diz por que está apagado, e "existe mas não para você" só gastaria a paciência de
  // quem não pode clicar de qualquer jeito. (Foi também o que condenou os dois itens
  // "fora do piloto" que viviam aqui — ver ITENS_DOCK em lib/dock-itens.ts.)
  const itens = ITENS_DOCK.filter((it) => it.tela === null || telaLiberada(it.tela, abas))
  return (
    <nav
      aria-label="Navegação principal"
      className="rail-ultra"
      style={{
        width: 70,
        flexShrink: 0,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 8,
        padding: '14px 8px',
        /* Rail TEAL SÓLIDO, como o sistema interno da Ultra (uxplus) — a classe
           `rail-ultra` (tokens.css) traz o teal opaco e o texto branco.

           Era escuro com lavagem turquesa (Juan, 2026-09-09: "a barra lateral clara
           ficou ruim em todas as lavagens de cor"). O Felipe mandou aplicar o guia em
           tudo e mostrou a referência real: lá o rail é a cor prioritária da marca,
           chapada. É a maior superfície contínua do produto e é onde o guia quer o
           teal dominante.

           SEM `backdropFilter`: o fundo agora é opaco, e desfocar o que está atrás de
           uma superfície opaca só custa composição — foi a translucidez que o Felipe
           apontou como errada. O véu branco do gradiente fica, mas só para dar relevo
           ao item ativo. */
        background: 'linear-gradient(180deg, var(--rail-a16), var(--rail-a08)), var(--surf-chrome)',
        borderRight: '1px solid var(--rail-a24)',
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

      {/* BLOCO UNICO da navegacao (2026-09-25, pedido do Felipe: "um fundo que preencha
          toda parte lateral do icone e tenha altura do primeiro icone ate o ultimo,
          sendo dividido por linhas"). Era um chip por icone; virou uma peca so'.

          O fundo, a borda e o raio moram AQUI; cada botao perde os seus e ganha apenas
          a linha que o separa do anterior. O primeiro nao leva linha — encostada na
          borda externa, ela leria como risco solto em vez de divisoria. */}
      <nav
        aria-label="Telas do piloto"
        style={{
          alignSelf: 'stretch',
          display: 'flex',
          flexDirection: 'column',
          background: 'var(--surf-raised)',
          /* SANGRA ATÉ AS BORDAS do rail. O rail tem `padding: '14px 8px'`, e uma
             primeira versão deixou o bloco dentro desse respiro — virou uma faixa com
             margem, não o que o Felipe pediu ("preencha toda a barra na largura").

             A margem negativa cancela o padding em vez de removê-lo: o padding continua
             valendo para o logo e para o trio do rodapé, que PRECISAM dele. Tirá-lo do
             rail encostaria todo mundo na borda para resolver só este bloco.

             Sem raio e sem borda lateral, por consequência: encostado nas duas bordas,
             canto arredondado deixaria dois triângulos de teal nas pontas, e a borda
             vertical cairia exatamente em cima da borda do rail. */
          marginLeft: -8,
          marginRight: -8,
          borderTop: '1px solid var(--line-soft)',
          borderBottom: '1px solid var(--line-soft)',
        }}
      >
      {itens.map((it, indice) => {
        const ativo = it.tela !== null && it.tela === tela
        const disponivel = it.tela !== null
        const cor = COR_ICONE_BRANCO
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
              /* Largura CHEIA do bloco, nao mais um quadrado de 42: o pedido e' que o
                 fundo preencha a lateral inteira. */
              width: '100%',
              /* 52, e nao 42 + `gap`: o pedido foi ~10px a mais entre um icone e outro,
                 e `gap` abriria FRESTAS de teal dentro do bloco — o fundo deixaria de
                 ser contínuo e as divisórias virariam riscos soltos. Crescer a altura
                 da celula afasta os glifos e mantém o bloco inteiro. */
              height: 52,
              borderRadius: 0,
              display: 'grid',
              placeItems: 'center',
              /* CHIP DE FUNDO em todos, não só no ativo (2026-09-25, pedido do
                 Felipe: "adicione um fundo neles igual tem no logout e troca de tema").
                 É a mesma métrica e o mesmo par `--surf-raised` + `--line-soft` dos
                 botões do rodapé — eles já eram os únicos com moldura, e a fileira de
                 cima parecia de outra ordem por não ter.

                 Com os ícones todos brancos, o chip virou o que dá relevo: antes a cor
                 de cada destino fazia esse papel sozinha.

                 O ATIVO continua se distinguindo — sobe do véu de repouso para um véu
                 mais denso, na cor do próprio ícone. Se os dois estados usassem o mesmo
                 fundo, o chip apagaria o "você está aqui" que ele veio reforçar. */
              background: ativo
                ? `color-mix(in srgb, ${cor} 22%, transparent)`
                : 'transparent',
              /* So' a divisoria: o fundo e a moldura sao do bloco. */
              border: 'none',
              borderTop: indice === 0 ? 'none' : '1px solid var(--line-soft)',
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
      </nav>

      {/* `marginTop: auto` empurra o trio do pé do rail para baixo: ele fica longe da
          fila de destinos, que é o que o separa de uma sexta tela. São os controles que
          valem para o app inteiro — a senha, o tema, e a saída da conta (2026-09-10,
          pedido do Felipe). A ORDEM é por quão definitivo é o gesto: o SAIR fica por
          último, no canto, longe da navegação, e o cadeado encabeça porque é o único
          que pode nem aparecer — sem `onSenha` o rodapé volta a ser a dupla de antes,
          e um buraco no meio da pilha leria como controle que sumiu. */}
      <div style={{ marginTop: 'auto', display: 'flex', flexDirection: 'column', gap: 8 }}>
        {onSenha && (
          <button
            type="button"
            title="Trocar a minha senha"
            aria-label="Trocar a minha senha"
            onClick={onSenha}
            style={{
              /* Mesma métrica do BotaoTema (42 / raio 11): são vizinhos no rodapé, e um
                 botão de outro tamanho ali leria como controle de outra ordem. */
              width: 42,
              height: 42,
              flexShrink: 0,
              display: 'grid',
              placeItems: 'center',
              borderRadius: 11,
              border: '1px solid var(--line-soft)',
              background: 'var(--surf-raised)',
              color: 'var(--tx-muted)',
              cursor: 'pointer',
              transition: 'background .15s ease, color .15s ease',
            }}
          >
            <Cadeado />
          </button>
        )}
        <BotaoTema tema={tema} onTema={onTema} />
        <BotaoSair />
      </div>
    </nav>
  )
}

/* Cadeado em `currentColor` e `stroke`, sem preenchimento — herda a cor do botão e
   dispensa variante por tema, igual ao Sol/Lua do BotaoTema. */
function Cadeado() {
  return (
    <svg
      width={18}
      height={18}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      /* Traco FINO, como o guia pede para os line icons: 1,9 destoava do 1,6 dos
         demais icones do rail e engrossava o cadeado contra os vizinhos. */
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <rect x={4.5} y={10.5} width={15} height={9.5} rx={2.2} />
      <path d="M8 10.5V7.6a4 4 0 0 1 8 0v2.9" />
      <circle cx={12} cy={15.2} r={1.35} />
    </svg>
  )
}
