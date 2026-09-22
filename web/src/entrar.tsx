import { StrictMode, useRef } from 'react'
import { createRoot } from 'react-dom/client'

import LoginScreen from './screens/LoginScreen'
import { destinoSeguro, lerResposta, montarPedido } from './lib/authelia'
import type { FalhaLogin } from './lib/login'
import './styles/global.css'

/**
 * Ponto de entrada da TELA DE ENTRAR — servida na raiz de `auth.ultra-expansao.tech`.
 *
 * POR QUE É UM BUNDLE SEPARADO do piloto. Esta página divide o host com o portal do
 * Authelia: o Caddy manda a raiz e `entrar-assets/` para o nosso container e todo o
 * resto para o Authelia. Se ela fosse a SPA do piloto, os arquivos dos dois colidiriam
 * no mesmo endereço — e serviríamos o bundle inteiro do piloto sem login, revelando as
 * rotas internas da API a quem nem entrou.
 *
 * POR QUE O `fetch` É RELATIVO. Vivendo no mesmo host do Authelia, `/api/firstfactor` é
 * MESMA ORIGEM: o cookie de sessão é aceito e não há CORS. Essa é a propriedade que
 * sustenta o desenho inteiro — e é também por isso que esta página **não funciona**
 * servida de outro host: ali o `fetch` bateria no backend do piloto, não no Authelia.
 *
 * ESTA PÁGINA NÃO FALA COM O NOSSO BACKEND. Nem `/api/me`, nem `/api/ufs`: quem está
 * aqui ainda não entrou, e as duas rotas estão atrás do login. Por isso nada de
 * `BaseProvider` com dados — o selo do painel cai no crédito do censo sozinho.
 */

function Entrada() {
  /* Contador de falhas DESTA sessão de tela. O Authelia responde 401 tanto para senha
     errada quanto para usuário banido, e não há campo que os separe — mas o banimento é
     determinístico (4 falhas em 2 min, 10 min bloqueado), então a partir da 4ª a tela
     para de dizer "senha incorreta". `useRef` e não `useState`: o valor é lido dentro do
     envio e não deve provocar redesenho. */
  const falhas = useRef(0)

  async function entrar(
    usuario: string,
    senha: string,
    manter: boolean,
  ): Promise<FalhaLogin | null> {
    /* De onde a pessoa veio. O `forward-auth` acrescenta `?rd=<url>` ao mandar quem não
       tem sessão para cá; sem repassar isso, todo mundo entraria e cairia no destino
       padrão, perdendo a página que tentava abrir. `destinoSeguro` recusa destino de
       fora do domínio — senão o link de login vira redirecionamento aberto. */
    const rd = new URLSearchParams(window.location.search).get('rd')
    const destino = destinoSeguro(rd, window.location.hostname)

    let status = 0
    let corpo: unknown = null
    try {
      const r = await fetch('/api/firstfactor', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        // O cookie de sessão é o produto desta chamada: sem `same-origin` o navegador
        // não o guardaria, e o login "daria certo" sem autenticar ninguém.
        credentials: 'same-origin',
        body: JSON.stringify(montarPedido(usuario, senha, manter, destino)),
      })
      status = r.status
      corpo = await r.json().catch(() => null)
    } catch {
      // Falha de rede: o Authelia pode estar reiniciando. Nunca "credencial".
      return 'indisponivel'
    }

    const desfecho = lerResposta(status, corpo, falhas.current)
    if (desfecho.tipo === 'entrou') {
      falhas.current = 0
      window.location.assign(desfecho.destino)
      // Não devolve `null`: a navegação leva alguns instantes e, sem isto, a tela
      // voltaria ao estado "parado" com o botão vivo — convidando um segundo envio.
      return await new Promise(() => {})
    }
    if (desfecho.tipo === 'segundo-fator') {
      /* O destino exige 2FA. Hoje nenhuma regra de `access_control` exige (lido na VPS em
         2026-09-22: as quatro são `one_factor`), então este ramo é rede de segurança —
         mas ele precisa existir ANTES de alguém ligar 2FA, senão a pessoa ficaria numa
         tela em branco, autenticada pela metade. O portal continua inteiro em `/2fa`,
         que é o que permite passar o bastão. */
      window.location.assign(`/2fa${window.location.search}`)
      return await new Promise(() => {})
    }
    falhas.current += 1
    return desfecho.falha
  }

  return <LoginScreen onEntrar={entrar} />
}

const el = document.getElementById('root')
if (!el) throw new Error('#root não encontrado no entrar.html')
createRoot(el).render(
  <StrictMode>
    <Entrada />
  </StrictMode>,
)
