import { StrictMode, useRef } from 'react'
import { createRoot } from 'react-dom/client'

import LoginScreen from './screens/LoginScreen'
import { api, ApiError } from './lib/api'
import { destinoSeguro } from './lib/authelia'
import { falhaDoStatus, type FalhaLogin } from './lib/login'
import { MAX_TENTATIVAS } from './lib/login-motor'
import './styles/global.css'

/**
 * Ponto de entrada da TELA DE ENTRAR.
 *
 * ELA FALA COM O NOSSO BACKEND (`POST /api/login`), desde 25/09/2026. Até essa data
 * falava com o Authelia (`/api/firstfactor`), e o docstring daqui afirmava, em letras
 * garrafais, que esta página "NÃO FALA COM O NOSSO BACKEND" — era verdade enquanto o
 * Authelia autenticava, e deixou de ser quando a **DEC-067** foi assinada nos quatro
 * itens. `api.entrar()` existia desde o PR #400 e **não tinha um único chamador**: era
 * a ponte pronta esperando a decisão. Esta é a decisão chegando ao código.
 *
 * ELA NÃO ESTAVA SENDO PUBLICADA. Medido no mesmo dia: `vite build` produzia só o
 * `index.html`, porque o `vite.config.ts` não listava as duas entradas — o
 * `entrar.html` existia no repositório desde o PR #400 e nunca saiu em imagem nenhuma.
 * Corrigido junto, e é o conserto sem o qual todo o resto aqui seria teórico.
 *
 * POR QUE CONTINUA SENDO UM BUNDLE SEPARADO. A razão mudou de endereço, não de peso.
 * Antes era colisão de arquivos com o portal do Authelia no mesmo host; agora é
 * SUPERFÍCIE: quem ainda não entrou recebe 23 kB de formulário, e não os 1,5 MB da SPA
 * do piloto — que carregam o mapa inteiro e o nome de cada rota interna da API. Servir
 * o bundle do piloto a quem não autenticou entrega o desenho da casa a quem tocou a
 * campainha.
 *
 * POR QUE O `fetch` CONTINUA RELATIVO. Mesma origem que o backend do piloto: o cookie
 * de sessão é aceito e não há CORS. A propriedade é a mesma de antes; o que mudou foi
 * QUEM está do outro lado. Consequência herdada, e vale repetir porque continua
 * verdadeira: esta página **não funciona** servida de um host que não seja o do piloto.
 *
 * ELA NÃO CHAMA `/api/me` NEM `/api/ufs`. Quem está aqui ainda não entrou, e as duas
 * exigem sessão depois do corte. Por isso nada de `BaseProvider` com dados.
 */

function Entrada() {
  /* Contador de falhas DESTA carga de tela, e ele existe por uma decisão de segurança
     do servidor: a trava de tentativas responde **o mesmo 401 com a mesma mensagem** de
     uma senha errada, de propósito — dizer "conta bloqueada" avisaria a quem varre nomes
     que acertou um. Sem campo que os separe, contar aqui é a única forma de a tela dizer
     algo mais útil que "senha incorreta" na enésima tentativa.

     É PALPITE, e a tela não finge o contrário: o servidor conta por CONTA e numa janela
     MÓVEL; esta contagem é por aba e some ao recarregar. Erra para o lado seguro — no
     máximo mostra o aviso de bloqueio a quem ainda tinha uma tentativa.

     `useRef` e não `useState`: é lido dentro do envio e não deve provocar redesenho. */
  const falhas = useRef(0)

  async function entrar(
    usuario: string,
    senha: string,
    manter: boolean,
  ): Promise<FalhaLogin | null> {
    /* De onde a pessoa veio. `destinoSeguro` recusa destino de fora do domínio — senão o
       link de login vira redirecionamento aberto: bastaria mandar à pessoa um link com
       `rd` para um site clonado, e ela seria levada para lá logo após digitar a senha de
       verdade. O parâmetro sobrevive ao corte porque quem manda alguém para cá continua
       podendo dizer para onde devolver. */
    const rd = new URLSearchParams(window.location.search).get('rd')
    const destino = destinoSeguro(rd, window.location.hostname) ?? '/'

    try {
      await api.entrar(usuario, senha, manter)
    } catch (erro) {
      if (!(erro instanceof ApiError)) {
        // Rede caiu, ou o timeout de 15 s estourou. NUNCA "credencial": afirmar que a
        // senha está errada porque o servidor não respondeu é mentir para a pessoa.
        return 'indisponivel'
      }
      falhas.current += 1
      if (erro.status === 404) {
        // `MOTOR_AUTENTICACAO_PROPRIA` desligada neste ambiente — a rota existe e
        // responde 404 de propósito. Não é erro de quem digitou, e a mensagem diz isso.
        return 'nao-ligado'
      }
      if (erro.status === 401 && falhas.current >= MAX_TENTATIVAS) return 'bloqueado'
      return falhaDoStatus(erro.status)
    }

    falhas.current = 0

    /* A TROCA DE SENHA NÃO É TRATADA AQUI, e isso é decisão, não esquecimento.
       `api.entrar()` devolve `deveTrocarSenha`, mas quem convida para a troca é o piloto,
       pelo `/api/me` da primeira carga (`deveOferecerTroca` -> o modal). Abrir uma
       segunda tela de troca aqui seria uma segunda redação da mesma regra — e desde
       25/09/2026 a troca é RECOMENDADA, não obrigatória, então esta tela não tem nada a
       impor. */
    window.location.assign(destino)
    /* Não devolve `null`: a navegação leva alguns instantes e, sem isto, a tela voltaria
       ao estado "parado" com o botão vivo — convidando um segundo envio. */
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
