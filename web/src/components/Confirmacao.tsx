import { useEffect, useRef, useState } from 'react'

import type { Confirmacao as DadosConfirmacao } from '../lib/confirmacao-admin'
import { loginConfere } from '../lib/confirmacao-admin'
import { Botao, Eyebrow, Glass, Spinner } from './primitives'

/* ---------------------------------------------------------------------------
   Pop-up de confirmação de escrita (pedido do Vinícius, 2026-09-10).

   POR QUE ELE EXISTE. Até aqui, mudar o acesso de alguém não pedia confirmação
   nenhuma — e a troca de perfil era a pior: ela disparava no `onChange` do
   `<select>`, então ESCOLHER a opção já era a escrita. Um clique errado, ou uma
   seta do teclado num select fechado, mudava o acesso de uma pessoa na hora.

   O TEXTO NÃO MORA AQUI. Este arquivo é só o casulo; a frase vem pronta de
   `lib/confirmacao-admin.ts`, que é módulo puro e testado. A divisão não é
   estética: o projeto testa com Vitest em ambiente `node`, sem DOM, então o
   componente não é testável neste repositório e o texto é. O que pode mentir
   ficou do lado que tem teste.

   O CASULO É O DO AvisoConfidencialidade (`role="dialog"`, `aria-modal`,
   `position: fixed`, `inset: 0`, `zIndex: 100`, backdrop com blur, cartão
   `Glass`). Não é preferência: o app inteiro roda dentro de um
   `transform: scale(0.85)`, e elemento transformado vira bloco de contenção do
   `position: fixed`. O molde já provado é o daquele arquivo — inventar outro aqui
   seria descobrir esse detalhe do jeito difícil.

   O QUE ELE DIZ, E O QUE NÃO DIZ. Ele mostra INTENÇÃO. Quem diz o que aconteceu
   é o recado da tela, montado da resposta do servidor — que lê o estado anterior
   com a linha travada e pode responder `mudou: false`. Se este pop-up prometesse
   resultado, seria ele o errado quando o servidor discordasse.
   --------------------------------------------------------------------------- */

export default function Confirmacao({
  dados,
  onConfirmar,
  onCancelar,
  salvando = false,
}: {
  dados: DadosConfirmacao
  onConfirmar: () => void
  onCancelar: () => void
  /** Enquanto o PATCH/POST está em voo: tudo trava e o Escape para de fechar. */
  salvando?: boolean
}) {
  const [digitado, setDigitado] = useState('')
  const casulo = useRef<HTMLDivElement>(null)

  const exigeDigitar = dados.loginParaDigitar !== null
  const liberado =
    !salvando && (!exigeDigitar || loginConfere(digitado, dados.loginParaDigitar as string))
  const perigo = dados.gravidade === 'alta'

  /* O foco entra no diálogo ao abrir. `Botao` e `Glass` não encaminham `ref`, então
     quem recebe o foco é o próprio contêiner (`tabIndex={-1}`) — isso basta para o
     Escape funcionar sem depender de onde o mouse estava, e para o leitor de tela
     anunciar o diálogo. O campo de digitação, quando existe, rouba o foco em
     seguida pelo `autoFocus`, que é onde a pessoa precisa estar. */
  useEffect(() => {
    casulo.current?.focus()
  }, [])

  /* Cada abertura começa com o campo vazio. Sem isto, reabrir o pop-up para OUTRA
     pessoa herdaria o login já digitado e liberaria o botão sem ninguém digitar
     nada — o atrito viraria enfeite. */
  useEffect(() => {
    setDigitado('')
  }, [dados.titulo])

  return (
    <div
      ref={casulo}
      role="dialog"
      aria-modal="true"
      aria-label={dados.titulo}
      tabIndex={-1}
      onKeyDown={(ev) => {
        if (ev.key === 'Escape' && !salvando) {
          ev.stopPropagation()
          onCancelar()
        }
      }}
      onClick={(ev) => {
        // Clique no backdrop cancela — é a direção segura. Nunca confirma.
        if (ev.target === ev.currentTarget && !salvando) onCancelar()
      }}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 100,
        display: 'grid',
        placeItems: 'center',
        background: 'color-mix(in srgb, var(--bg-base) 68%, transparent)',
        backdropFilter: 'blur(7px)',
        outline: 'none',
      }}
    >
      <Glass
        style={{
          width: 'min(600px, calc(100vw - 48px))',
          padding: '24px 28px 22px',
          display: 'flex',
          flexDirection: 'column',
          gap: 16,
          boxShadow: 'var(--sh-pop)',
          // A tarja de perigo é a primeira coisa que o olho pega, antes de ler.
          borderLeft: perigo ? '4px solid var(--sev-alta)' : '4px solid var(--ac)',
        }}
      >
        <Eyebrow cor={perigo ? 'var(--sev-alta)' : 'var(--ac)'} dot>
          {dados.eyebrow}
        </Eyebrow>

        {/* O título GARRAFAL: é ele que responde "o que está sendo feito". A maior
            tipografia do produto até aqui era o número do Kpi, 24px; este passa dela
            de propósito, e `clamp` evita que um nome longo estoure a largura. */}
        <h2
          style={{
            font: '700 clamp(22px, 3.4vw, 30px)/1.18 var(--f-ui)',
            letterSpacing: '-0.015em',
            color: 'var(--tx-max)',
            margin: 0,
            textWrap: 'balance',
          }}
        >
          {dados.titulo}
        </h2>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
          {dados.apoio.map((p) => (
            <p
              key={p.slice(0, 28)}
              style={{ font: '400 13px/1.55 var(--f-ui)', color: 'var(--tx-soft)', margin: 0 }}
            >
              {p}
            </p>
          ))}
        </div>

        {exigeDigitar && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
            <label
              htmlFor="confirmacao-login"
              style={{
                font: '600 10px/1 var(--f-ui)',
                letterSpacing: '.07em',
                textTransform: 'uppercase',
                color: 'var(--tx-muted)',
              }}
            >
              Digite <strong style={{ color: 'var(--tx-max)' }}>{dados.loginParaDigitar}</strong>{' '}
              para liberar
            </label>
            <input
              id="confirmacao-login"
              autoFocus
              autoComplete="off"
              spellCheck={false}
              disabled={salvando}
              value={digitado}
              onChange={(ev) => setDigitado(ev.target.value)}
              /* Enter só vale quando o login já confere — senão a tecla que a pessoa
                 usa para terminar de digitar dispararia a ação incompleta. */
              onKeyDown={(ev) => {
                if (ev.key === 'Enter' && liberado) onConfirmar()
              }}
              style={{
                padding: '9px 11px',
                borderRadius: 'var(--r-sm)',
                border: `1px solid ${liberado ? 'var(--sev-alta)' : 'var(--line-strong)'}`,
                background: 'var(--surf-chrome)',
                color: 'var(--tx-max)',
                font: '500 13px/1.3 var(--f-num)',
                width: '100%',
              }}
            />
          </div>
        )}

        <div
          style={{
            display: 'flex',
            justifyContent: 'flex-end',
            alignItems: 'center',
            gap: 9,
            marginTop: 2,
          }}
        >
          <Botao variante="ghost" disabled={salvando} onClick={onCancelar}>
            Cancelar
          </Botao>
          <Botao
            disabled={!liberado}
            onClick={onConfirmar}
            style={
              perigo
                ? {
                    /* Texto ESCURO sobre o vermelho, não branco: `--sev-alta` é
                       #ff5a6e no tema escuro e #d32d4d no claro, e `--bg-base`
                       contrasta bem com os dois. Branco sobre o vermelho claro
                       ficaria em ~2,9:1 e reprovaria como texto. */
                    background: 'var(--sev-alta)',
                    color: 'var(--bg-base)',
                    boxShadow: 'none',
                  }
                : undefined
            }
          >
            {salvando ? (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7 }}>
                <Spinner /> Aplicando…
              </span>
            ) : (
              dados.rotuloConfirmar
            )}
          </Botao>
        </div>
      </Glass>
    </div>
  )
}
