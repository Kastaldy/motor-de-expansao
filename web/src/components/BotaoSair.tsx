import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'

import { Botao, Modal } from './primitives'
import { urlDeLogoff } from '../lib/logoff'

/* ---------------------------------------------------------------------------
   Botão de SAIR do Dock (pedido do Felipe, 2026-09-10: "quando um usuário entra,
   ele não possui a opção de sair do perfil").

   Mora logo ABAIXO do alternador de tema, no pé do rail, pelo mesmo motivo que ele:
   não é um destino, é um controle da sessão inteira — e o Dock é o único chrome
   presente em todas as telas. Métrica idêntica à do `BotaoTema` (42 / raio 11 / ícone
   de 18 px) porque os dois são o mesmo tipo de coisa; um botão de outro tamanho ali
   leria como um controle de outra ordem.

   O QUE ELE FAZ. O piloto não tem sessão própria: quem autentica é o Authelia, e o
   app só recebe o `Remote-User` que o Caddy repassa (`web/server/acesso.py`). Então
   sair é ENCERRAR A SESSÃO NO AUTHELIA — navegar para o `/logout` do portal. Limpar
   estado local seria a pior das opções: a tela pareceria deslogada e a requisição
   seguinte continuaria chegando autenticada. Quem monta a URL é `lib/logoff.ts`, a
   partir do host da página; nenhum domínio é cravado neste arquivo.

   POR QUE PEDE CONFIRMAÇÃO. Este é um ícone de 42 px encostado no alternador de tema,
   cujo clique não custa nada — a vizinhança ensina que clicar ali é barato, e o dedo
   erra. Só que o custo dos dois é assimétrico: o erro no tema se desfaz com outro
   clique, e o erro aqui derruba a sessão e leva embora TODA a análise em tela, que
   não é salva em lugar nenhum (recorte do mapa, ficha aberta, premissas digitadas na
   Viabilidade — DEC-009: premissa digitada sobre um imóvel concreto). Voltar custa
   login no Authelia inteiro, mais 2FA onde estiver ligado, e refazer o que se tinha.
   O preço da confirmação é um clique a mais numa ação feita no máximo uma vez por
   dia; o preço de não confirmar é meio dia de trabalho de alguém. Confirma.

   Cancelar é o caminho seguro, então TUDO cancela: Esc, clique no fundo (o `onFundo`
   do `Modal`) e o botão Cancelar (à esquerda, o primeiro na ordem de foco). Diferente
   do aviso de confidencialidade, que é bloqueante de propósito por ser o oposto — lá o
   único caminho possível é seguir.

   DEV SEM AUTHELIA. Em `localhost` não há portal, e navegar daria um 404 mudo. O botão
   não some (senão ninguém o vê em dev, e o que não se vê não se revisa): ele abre o
   MESMO diálogo, dizendo que não há sessão a encerrar aqui e oferecendo só o
   "Entendi". `urlDeLogoff` devolvendo `null` é o que separa os dois casos.

   POR QUE O PORTAL VAI PARA O `#root`, E NÃO PARA O `body`. Sair do Dock é obrigatório:
   o rail tem `backdrop-filter`, que o torna o bloco de contenção de qualquer descendente
   `position: fixed` — dentro dele, o diálogo cobriria 70 px de tela em vez da tela. Mas o
   destino também não pode ser o `body`: o app inteiro é desenhado a 85% por um
   `transform: scale(var(--escala-app))` aplicado no `#root` (`styles/global.css`), e o
   `body` está FORA dessa escala. Portado para o `body`, este diálogo era o único pedaço
   do piloto em tamanho real — pedia `min(460px, ...)` e desenhava 460 px, enquanto o
   cartão de sessão pedia 520 e pousava em 442: DECLARAVA menos e DESENHAVA mais. O
   `#root` carrega o `transform`, então segue sendo bloco de contenção de `position:
   fixed` (é o `transform` que cria a contenção, não o `backdrop-filter`) e o diálogo
   volta para a escala do resto do app.
   --------------------------------------------------------------------------- */

export const TITULO_SAIR = 'Sair da conta'

/* O alvo do portal — ver o cabeçalho. O `body` fica só como último recurso, para um DOM
   sem a raiz do app: sem ele, `createPortal` receberia `null` e quebraria. */
function alvoDoPortal(): HTMLElement {
  return document.getElementById('root') ?? document.body
}

export default function BotaoSair() {
  const [perguntando, setPerguntando] = useState(false)

  // Lido no clique, e não no módulo: `location` não existe no ambiente node do vitest,
  // e um `null` capturado na carga travaria o botão para sempre.
  const destino =
    perguntando && typeof window !== 'undefined' ? urlDeLogoff(window.location.hostname) : null

  useEffect(() => {
    if (!perguntando) return
    const aoTeclar = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setPerguntando(false)
    }
    window.addEventListener('keydown', aoTeclar)
    return () => window.removeEventListener('keydown', aoTeclar)
  }, [perguntando])

  return (
    <>
      <button
        type="button"
        title={TITULO_SAIR}
        aria-label={TITULO_SAIR}
        aria-haspopup="dialog"
        aria-expanded={perguntando}
        onClick={() => setPerguntando(true)}
        style={{
          /* Mesma métrica do BotaoTema — ver o cabeçalho. */
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
        <IconeSair />
      </button>

      {perguntando && typeof document !== 'undefined'
        ? createPortal(
            <DialogoSair
              destino={destino}
              onCancelar={() => setPerguntando(false)}
              onSair={() => {
                if (destino !== null) window.location.assign(destino)
              }}
            />,
            alvoDoPortal(),
          )
        : null}
    </>
  )
}

/* Porta com seta saindo — o desenho corrente de "sair", no mesmo vocabulário do
   BotaoTema (`stroke: currentColor`, sem preenchimento), para herdar a cor do botão e
   dispensar uma variante por tema. 18 px acompanha o sol/lua vizinho. */
function IconeSair() {
  return (
    <svg
      width={18}
      height={18}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.9}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M15.5 20.2H5.4a1.6 1.6 0 0 1-1.6-1.6V5.4a1.6 1.6 0 0 1 1.6-1.6h10.1" />
      <path d="M15.2 15.9 19.9 12l-4.7-3.9" />
      <path d="M19.9 12H9.3" />
    </svg>
  )
}

function DialogoSair({
  destino,
  onCancelar,
  onSair,
}: {
  destino: string | null
  onCancelar: () => void
  onSair: () => void
}) {
  const semPortal = destino === null
  const titulo = semPortal ? 'Não há sessão para encerrar' : 'Sair da conta?'
  const corpo = semPortal
    ? 'Este ambiente local não tem o portal de autenticação na frente, então ' +
      'não há sessão a encerrar. Em produção, este botão encerra sua sessão e ' +
      'leva de volta à tela de login.'
    : 'Você será levado à tela de login, e a análise aberta agora será perdida — ' +
      'o recorte do mapa, a ficha e as premissas digitadas não ficam salvas. ' +
      'Para voltar, será preciso entrar de novo.'
  return (
    <Modal
      titulo={titulo}
      largura={460}
      zIndex={120}
      paragrafos={[corpo]}
      onFundo={onCancelar}
      acoes={
        semPortal ? (
          <Botao onClick={onCancelar}>Entendi</Botao>
        ) : (
          <>
            <Botao variante="ghost" onClick={onCancelar}>
              Cancelar
            </Botao>
            <Botao onClick={onSair}>Sair</Botao>
          </>
        )
      }
    />
  )
}
