import { Botao, Modal } from './primitives'

/* ---------------------------------------------------------------------------
   Pop-up de SESSÃO ENCERRADA.

   Nasceu de um pedido do Felipe: com o login do Authelia vencido (`inactivity: 30m`),
   o operador via a frase de dev "Ele está rodando na porta 8899?" e entendia que o
   sistema tinha caído — quando bastava entrar de novo. O porquê técnico (302 do
   Authelia -> CORS -> `TypeError` no `fetch`) e a sonda que separa "sessão vencida" de
   "servidor fora do ar" estão em `lib/sessao.ts`; aqui só mora o texto e o botão.

   O que este pop-up NUNCA faz: aparecer por erro de rede genérico. Ele só é montado
   quando a sonda de `lib/sessao.ts` classificou a falha como `sessao`, ou seja, quando
   a borda respondeu mandando para o login. Backend fora do ar segue caindo na mensagem
   inline de sempre, e é isso que impede o operador de perder tempo relogando num
   sistema que não vai responder.

   Bloqueante, como o AvisoConfidencialidade: sem fechar por Esc nem por clique fora
   (nenhum dos dois passa `onFundo` ao `Modal`), porque não há nada de útil a fazer na
   tela atrás dele — toda requisição a partir daqui volta para o login. Fica em `zIndex`
   MAIOR que o do aviso de confidencialidade (100): se a sessão já estiver vencida na
   abertura do app, quem falha primeiro é o `/api/me`, os dois pop-ups existem ao mesmo
   tempo e o de sessão é o que precisa ser lido.

   A casca (véu, cartão, tipografia) vive no `Modal` de `primitives.tsx`. O mount deste
   componente no `App` é guardado por `components/aviso-sessao.test.ts`: sem essa
   asserção, o pop-up podia sumir inteiro com a suíte verde.
   --------------------------------------------------------------------------- */

export const TITULO_SESSAO = 'Sessão encerrada'

export const PARAGRAFOS_SESSAO: readonly string[] = [
  'Seu acesso expirou e você foi desconectado da conta. Isso acontece depois de um ' +
    'tempo com o piloto aberto sem uso.',
  'Não é uma falha do sistema: o servidor respondeu pedindo um novo login.',
  'Clique em "Entrar novamente" para voltar à tela de login. A página vai recarregar, ' +
    'e depois que você entrar o piloto abre de novo.',
]

export const ROTULO_BOTAO_SESSAO = 'Entrar novamente'

export default function AvisoSessao({ onEntrar }: { onEntrar: () => void }) {
  return (
    <Modal
      titulo={TITULO_SESSAO}
      emoji="🔑"
      largura={520}
      zIndex={120}
      paragrafos={PARAGRAFOS_SESSAO}
      acoes={<Botao onClick={onEntrar}>{ROTULO_BOTAO_SESSAO}</Botao>}
    />
  )
}
