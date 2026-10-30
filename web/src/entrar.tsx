import { StrictMode, useRef } from 'react'
import { createRoot } from 'react-dom/client'

import LoginScreen from './screens/LoginScreen'
import { api, ApiError } from './lib/api'
import { destinoSeguro } from './lib/destino'
import { falhaDoStatus, type FalhaLogin } from './lib/login'
import { MAX_TENTATIVAS } from './lib/login-motor'
import './styles/global.css'

/**
 * Ponto de entrada da TELA DE ENTRAR.
 *
 * ELA FALA COM UM SO' BACKEND: o nosso `POST /api/login`. A DEC-081 aposentou o Authelia
 * e levou o login proprio a todas as origens, entao o 404 que antes caia para o primeiro
 * fator do Authelia deixou de existir — a autenticacao propria esta' sempre ligada depois
 * do corte. Um 404 agora e' erro de servidor como outro qualquer, nao um sinal de "tente
 * o outro autenticador".
 *
 * `api.entrar()` fala com `POST /api/login`. A TRAVA DE TENTATIVAS do servidor responde o
 * MESMO 401 com a mesma mensagem de uma senha errada, de proposito: dizer "conta
 * bloqueada" avisaria a quem varre nomes que acertou um. E' por isso que a tela conta as
 * falhas sozinha (`falhas`, em `Entrada`) e nomeia o bloqueio a partir de `MAX_TENTATIVAS`.
 *
 * POR QUE CONTINUA SENDO UM BUNDLE SEPARADO. Quem ainda nao entrou recebe ~23 kB de
 * formulario, e nao os ~1,5 MB da SPA do piloto — que carregam o mapa inteiro e o nome de
 * cada rota interna da API. Servir o bundle do piloto a quem nao autenticou entrega o
 * desenho da casa a quem tocou a campainha.
 *
 * POR QUE O `fetch` CONTINUA RELATIVO. Mesma origem que o backend do piloto: o cookie de
 * sessao e' aceito e nao ha' CORS. Consequencia herdada, e vale repetir porque continua
 * verdadeira: esta pagina **nao funciona** servida de um host que nao seja o do piloto.
 *
 * ELA NAO CHAMA `/api/me` NEM `/api/ufs`. Quem esta' aqui ainda nao entrou, e as duas
 * exigem sessao depois do corte. Por isso nada de `BaseProvider` com dados.
 */

function Entrada() {
  /* Contador de falhas DESTA carga de tela, e ele existe por uma decisao de seguranca
     do servidor: a trava de tentativas responde **o mesmo 401 com a mesma mensagem** de
     uma senha errada, de proposito — dizer "conta bloqueada" avisaria a quem varre nomes
     que acertou um. Sem campo que os separe, contar aqui e' a unica forma de a tela dizer
     algo mais util que "senha incorreta" na enesima tentativa.

     E' PALPITE, e a tela nao finge o contrario: o servidor conta por CONTA e numa janela
     MOVEL; esta contagem e' por aba e some ao recarregar. Erra para o lado seguro — no
     maximo mostra o aviso de bloqueio a quem ainda tinha uma tentativa.

     `useRef` e nao `useState`: e' lido dentro do envio e nao deve provocar redesenho. */
  const falhas = useRef(0)

  async function entrar(
    usuario: string,
    senha: string,
    manter: boolean,
  ): Promise<FalhaLogin | null> {
    /* De onde a pessoa veio. `destinoSeguro` recusa destino de fora do dominio — senao o
       link de login vira redirecionamento aberto: bastaria mandar a' pessoa um link com
       `rd` para um site clonado, e ela seria levada para la' logo apos digitar a senha de
       verdade. O parametro sobrevive ao corte porque quem manda alguem para ca' continua
       podendo dizer para onde devolver.

       O 3o argumento ensina `destinoSeguro` a reconhecer a tela de entrar quando ela NAO
       se chama `entrar.html` (numa raiz de host ela se chama `/`), fechando o laco de
       `rd` aninhado medido em producao. Sem `rd` valido, a raiz: mesma origem, e' o
       piloto. */
    const rd = new URLSearchParams(window.location.search).get('rd')
    const destino = destinoSeguro(rd, window.location.hostname, window.location.href) ?? '/'

    try {
      await api.entrar(usuario, senha, manter)
    } catch (erro) {
      if (!(erro instanceof ApiError)) {
        // Rede caiu, ou o timeout de 15 s estourou. NUNCA "credencial": afirmar que a
        // senha esta' errada porque o servidor nao respondeu e' mentir para a pessoa.
        return 'indisponivel'
      }
      falhas.current += 1
      if (erro.status === 401 && falhas.current >= MAX_TENTATIVAS) return 'bloqueado'
      return falhaDoStatus(erro.status)
    }

    falhas.current = 0

    /* A TROCA DE SENHA NAO E' TRATADA AQUI, e isso e' decisao, nao esquecimento.
       `api.entrar()` devolve `deveTrocarSenha`, mas quem convida para a troca e' o piloto,
       pelo `/api/me` da primeira carga (`deveOferecerTroca` -> o modal). Abrir uma segunda
       tela de troca aqui seria uma segunda redacao da mesma regra — e desde 25/09/2026 a
       troca e' RECOMENDADA, nao obrigatoria, entao esta tela nao tem nada a impor. */
    window.location.assign(destino)
    /* Nao devolve `null`: a navegacao leva alguns instantes e, sem isto, a tela voltaria
       ao estado "parado" com o botao vivo — convidando um segundo envio. */
    return await new Promise(() => {})
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
