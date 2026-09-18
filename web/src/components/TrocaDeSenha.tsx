import { useEffect, useRef, useState } from 'react'

import {
  MINIMO_DE_CARACTERES,
  podeEnviar,
  problemasDaSenha,
  textoDaTroca,
  type EstadoDaSenha,
} from '../lib/troca-de-senha'
import { Botao, Campo, Eyebrow, Glass, Spinner } from './primitives'

/* ---------------------------------------------------------------------------
   Troca da PRÓPRIA senha (D26 / migration 016).

   POR QUE ELE EXISTE. `PATCH /api/me/senha` e `api.trocarMinhaSenha` já existiam —
   o que faltava era a ponta: nenhum componente chamava, então os seis cadastros
   ficavam presos em `deve_trocar_senha = true` sem caminho para sair.

   OFERECE, NÃO OBRIGA. Este pop-up não é parede: enquanto o P19 não acontecer,
   quem autentica é o Authelia e a senha do banco não abre porta nenhuma. A
   decisão mora em `deveOferecerTroca`, que é testado — aqui é só o casulo.

   O TEXTO NÃO MORA AQUI. Vem de `lib/troca-de-senha.ts`, que é módulo puro e
   testado, pela mesma razão do `Confirmacao.tsx`: o projeto testa com Vitest em
   ambiente `node`, sem DOM.

   O CASULO É O DO Confirmacao/AvisoConfidencialidade (`role="dialog"`,
   `aria-modal`, `position: fixed`, `inset: 0`, `zIndex: 100`). Não é preferência:
   o app roda dentro de um `transform: scale(0.85)`, e elemento transformado vira
   bloco de contenção do `position: fixed`.
   --------------------------------------------------------------------------- */

export default function TrocaDeSenha({
  estado,
  onTrocar,
  onDispensar,
}: {
  estado: EstadoDaSenha
  /** Devolve `null` em sucesso, ou a mensagem a exibir. Quem chama faz a chamada. */
  onTrocar: (senhaAtual: string, nova: string) => Promise<string | null>
  onDispensar: () => void
}) {
  const [atual, setAtual] = useState('')
  const [nova, setNova] = useState('')
  const [repetida, setRepetida] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [pronto, setPronto] = useState(false)
  const casulo = useRef<HTMLDivElement>(null)

  const { titulo, chamada } = textoDaTroca(estado)
  const problemas = problemasDaSenha(nova, atual)
  const repeteErrado = repetida.length > 0 && repetida !== nova
  const liberado = !enviando && podeEnviar(atual, nova, repetida)

  useEffect(() => {
    casulo.current?.focus()
  }, [])

  async function enviar() {
    if (!liberado) return
    setEnviando(true)
    setErro(null)
    const recado = await onTrocar(atual, nova)
    setEnviando(false)
    if (recado === null) {
      setPronto(true)
      return
    }
    setErro(recado)
    // A senha nova FICA; a atual some. Em 403 ("não confere") é ela que está errada, e
    // deixá-la no campo faz a pessoa clicar de novo na mesma coisa. Apagar a nova junto
    // seria fazê-la digitar tudo outra vez por causa de um campo só.
    setAtual('')
  }

  return (
    <div
      ref={casulo}
      role="dialog"
      aria-modal="true"
      aria-label={titulo}
      tabIndex={-1}
      onKeyDown={(ev) => {
        if (ev.key === 'Escape' && !enviando) {
          ev.stopPropagation()
          onDispensar()
        }
      }}
      onClick={(ev) => {
        // Clique no fundo dispensa — a direção segura. Nunca envia.
        if (ev.target === ev.currentTarget && !enviando) onDispensar()
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
          width: 'min(520px, calc(100vw - 48px))',
          padding: '24px 28px 22px',
          display: 'flex',
          flexDirection: 'column',
          gap: 15,
          boxShadow: 'var(--sh-pop)',
          borderLeft: `4px solid ${pronto ? 'var(--ac)' : 'var(--sev-media)'}`,
        }}
      >
        <Eyebrow cor={pronto ? 'var(--ac)' : 'var(--sev-media)'} dot>
          {pronto ? 'Senha definida' : 'Acesso ao piloto'}
        </Eyebrow>

        <h2
          style={{
            font: '700 clamp(20px, 3vw, 26px)/1.18 var(--f-ui)',
            letterSpacing: '-0.015em',
            color: 'var(--tx-max)',
            margin: 0,
            textWrap: 'balance',
          }}
        >
          {pronto ? 'Pronto — a senha agora é sua' : titulo}
        </h2>

        {pronto ? (
          <>
            <p style={{ font: '400 13px/1.55 var(--f-ui)', color: 'var(--tx-soft)', margin: 0 }}>
              Guarde-a. Enquanto a entrada no piloto continuar pelo Authelia, é ele que pede a
              senha para entrar — esta aqui fica pronta para o dia em que o próprio sistema
              passar a autenticar.
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 2 }}>
              <Botao onClick={onDispensar}>Voltar ao piloto</Botao>
            </div>
          </>
        ) : (
          <>
            <p style={{ font: '400 13px/1.55 var(--f-ui)', color: 'var(--tx-soft)', margin: 0 }}>
              {chamada}
            </p>

            <Campo
              id="senha-atual"
              rotulo={estado.propria ? 'Senha atual' : 'Senha inicial (a que você recebeu)'}
              valor={atual}
              onValor={setAtual}
              desabilitado={enviando}
              foco
            />
            <Campo
              id="senha-nova"
              rotulo={`Senha nova (mínimo de ${MINIMO_DE_CARACTERES} caracteres)`}
              valor={nova}
              onValor={setNova}
              desabilitado={enviando}
            />
            <Campo
              id="senha-repetida"
              rotulo="Repita a senha nova"
              valor={repetida}
              onValor={setRepetida}
              desabilitado={enviando}
              ruim={repeteErrado}
              onEnter={enviar}
            />

            {/* O que falta aparece enquanto se digita, tudo de uma vez. Mostrar um
                problema por vez é o que faz formulário de senha ser odiado. */}
            {nova.length > 0 && (problemas.length > 0 || repeteErrado) && (
              <ul
                style={{
                  margin: 0,
                  paddingLeft: 18,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 3,
                }}
              >
                {problemas.map((p) => (
                  <li
                    key={p.slice(0, 24)}
                    style={{ font: '400 12px/1.45 var(--f-ui)', color: 'var(--tx-muted)' }}
                  >
                    {p}
                  </li>
                ))}
                {repeteErrado && (
                  <li style={{ font: '400 12px/1.45 var(--f-ui)', color: 'var(--tx-muted)' }}>
                    As duas não são iguais.
                  </li>
                )}
              </ul>
            )}

            {erro && (
              <p
                role="alert"
                style={{
                  font: '500 12.5px/1.45 var(--f-ui)',
                  color: 'var(--sev-alta)',
                  background: 'color-mix(in srgb, var(--sev-alta) 12%, transparent)',
                  border: '1px solid color-mix(in srgb, var(--sev-alta) 30%, transparent)',
                  borderRadius: 'var(--r-sm)',
                  padding: '8px 10px',
                  margin: 0,
                }}
              >
                {erro}
              </p>
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
              <Botao variante="ghost" disabled={enviando} onClick={onDispensar}>
                Agora não
              </Botao>
              <Botao disabled={!liberado} onClick={enviar}>
                {enviando ? (
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7 }}>
                    <Spinner /> Definindo…
                  </span>
                ) : (
                  'Definir senha'
                )}
              </Botao>
            </div>
          </>
        )}
      </Glass>
    </div>
  )
}

/* O `Campo` mudou-se para `primitives.tsx` quando a tela de login passou a precisar do
   mesmo componente — as chamadas acima não mudaram, porque lá ele mantém `password` como
   default e a mesma dedução de `autoComplete`. */
