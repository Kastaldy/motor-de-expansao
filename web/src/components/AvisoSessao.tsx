import { Botao, Glass } from './primitives'

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

   Bloqueante, como o AvisoConfidencialidade: sem fechar por Esc nem por clique fora,
   porque não há nada de útil a fazer na tela atrás dele — toda requisição a partir
   daqui volta para o login. Fica em `zIndex` MAIOR que o do aviso de confidencialidade
   (100): se a sessão já estiver vencida na abertura do app, quem falha primeiro é o
   `/api/me`, os dois pop-ups existem ao mesmo tempo e o de sessão é o que precisa ser
   lido.
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
    <div
      role="dialog"
      aria-modal="true"
      aria-label={TITULO_SESSAO}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 120,
        display: 'grid',
        placeItems: 'center',
        background: 'color-mix(in srgb, var(--bg-base) 68%, transparent)',
        backdropFilter: 'blur(7px)',
      }}
    >
      <Glass
        style={{
          width: 'min(520px, calc(100vw - 48px))',
          padding: '26px 28px 24px',
          display: 'flex',
          flexDirection: 'column',
          gap: 14,
          boxShadow: 'var(--sh-pop)',
        }}
      >
        <h2
          style={{
            font: '700 19px/1.25 var(--f-ui)',
            color: 'var(--tx-max)',
            margin: 0,
            display: 'flex',
            alignItems: 'center',
            gap: 10,
          }}
        >
          {TITULO_SESSAO}
          <span aria-hidden style={{ fontSize: 24, lineHeight: 1 }}>
            🔑
          </span>
        </h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {PARAGRAFOS_SESSAO.map((p) => (
            <p
              key={p.slice(0, 24)}
              style={{ font: '400 13px/1.55 var(--f-ui)', color: 'var(--tx-soft)', margin: 0 }}
            >
              {p}
            </p>
          ))}
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 4 }}>
          <Botao onClick={onEntrar}>{ROTULO_BOTAO_SESSAO}</Botao>
        </div>
      </Glass>
    </div>
  )
}
