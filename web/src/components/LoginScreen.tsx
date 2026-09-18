import { useState } from 'react'

import {
  AJUDA_LEMBRAR,
  ROTULO_BOTAO,
  ROTULO_LEMBRAR,
  ROTULO_LOGIN,
  ROTULO_SENHA,
  TITULO_LOGIN,
  podeEntrar,
} from '../lib/login'
import { Botao, Campo, Eyebrow, Glass, Spinner } from './primitives'

/* ---------------------------------------------------------------------------
   Tela de ENTRADA (epic do P19). O casulo, e só ele.

   NÃO É UM POP-UP SOBRE O APP — ELE SUBSTITUI O APP. É a diferença que separa
   este componente do `TrocaDeSenha`/`AvisoConfidencialidade`, e por isso ele NÃO
   herda o comportamento de dispensar: não há clique no fundo, não há `Escape` e
   não há botão de fechar. Copiar o casulo daqueles junto com a saída de emergência
   seria oferecer uma porta que não leva a lugar nenhum — atrás dela não há app,
   há 401.

   A LÓGICA NÃO MORA AQUI. Texto, validação e tradução de erro vivem em
   `lib/login.ts`, que é módulo puro e testado: o `vitest.config.ts` roda em
   `environment: 'node'`, sem DOM, e só alcança `.ts`. Mesma divisão do
   `TrocaDeSenha` e do `Confirmacao`, pela mesma razão — o que pode mentir fica do
   lado que tem teste.

   QUEM CHAMA FAZ A CHAMADA. `onEntrar` devolve `null` em sucesso ou a mensagem a
   exibir, no mesmo molde do `onTrocar` do `TrocaDeSenha`. Assim este arquivo não
   conhece `api`, e o `App` continua sendo o único lugar que orquestra.
   --------------------------------------------------------------------------- */

export default function LoginScreen({
  onEntrar,
}: {
  /** `null` = entrou. String = a mensagem que a pessoa deve ler. */
  onEntrar: (login: string, senha: string, lembrar: boolean) => Promise<string | null>
}) {
  const [login, setLogin] = useState('')
  const [senha, setSenha] = useState('')
  const [lembrar, setLembrar] = useState(false)
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  const liberado = !enviando && podeEntrar(login, senha)

  async function enviar() {
    if (!liberado) return
    setEnviando(true)
    setErro(null)
    const recado = await onEntrar(login, senha, lembrar)
    setEnviando(false)
    if (recado === null) return // quem monta a árvore troca a tela; aqui não há o que fazer
    setErro(recado)
    // A SENHA some, o login FICA. Errar a senha é o caso comum; apagar o usuário junto
    // faria a pessoa redigitar as duas coisas por causa de uma. Mesmo raciocínio do
    // `TrocaDeSenha`, que limpa a atual e preserva a nova.
    setSenha('')
  }

  return (
    <div
      role="main"
      aria-label={TITULO_LOGIN}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 100,
        display: 'grid',
        placeItems: 'center',
        background: 'var(--bg-base)',
        padding: 24,
      }}
    >
      <Glass
        style={{
          width: 'min(420px, calc(100vw - 48px))',
          padding: '26px 28px 24px',
          display: 'flex',
          flexDirection: 'column',
          gap: 15,
          boxShadow: 'var(--sh-pop)',
          borderLeft: '4px solid var(--ac)',
        }}
      >
        <Eyebrow cor="var(--ac)" dot>
          Motor de Expansão
        </Eyebrow>

        <h1
          style={{
            font: '700 clamp(20px, 3vw, 26px)/1.18 var(--f-ui)',
            letterSpacing: '-0.015em',
            color: 'var(--tx-max)',
            margin: 0,
            textWrap: 'balance',
          }}
        >
          {TITULO_LOGIN}
        </h1>

        <Campo
          id="login-usuario"
          rotulo={ROTULO_LOGIN}
          tipo="text"
          autoComplete="username"
          valor={login}
          onValor={setLogin}
          desabilitado={enviando}
          foco
          onEnter={enviar}
        />
        <Campo
          id="login-senha"
          rotulo={ROTULO_SENHA}
          autoComplete="current-password"
          valor={senha}
          onValor={setSenha}
          desabilitado={enviando}
          ruim={erro !== null}
          onEnter={enviar}
        />

        <label
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: 8,
            font: '400 12px/1.45 var(--f-ui)',
            color: 'var(--tx-soft)',
            cursor: enviando ? 'default' : 'pointer',
          }}
        >
          <input
            type="checkbox"
            checked={lembrar}
            disabled={enviando}
            onChange={(ev) => setLembrar(ev.target.checked)}
            style={{ marginTop: 2 }}
          />
          <span>
            {ROTULO_LEMBRAR}
            {/* O texto diz o que a caixinha faz E o que ela não faz. Prometer "continue
                conectado" sem o limite faria quem fecha o navegador voltar deslogado no
                dia seguinte sem entender por quê. */}
            <span style={{ display: 'block', color: 'var(--tx-muted)', font: '400 11px/1.4 var(--f-ui)' }}>
              {AJUDA_LEMBRAR}
            </span>
          </span>
        </label>

        {erro !== null && (
          <p
            role="alert"
            style={{
              margin: 0,
              font: '500 12px/1.45 var(--f-ui)',
              color: 'var(--sev-alta)',
            }}
          >
            {erro}
          </p>
        )}

        <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: 10 }}>
          {enviando && <Spinner />}
          <Botao onClick={enviar} disabled={!liberado} variante="primario">
            {ROTULO_BOTAO}
          </Botao>
        </div>
      </Glass>
    </div>
  )
}
