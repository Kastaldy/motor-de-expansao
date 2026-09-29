import { StrictMode, useRef } from 'react'
import { createRoot } from 'react-dom/client'

import LoginScreen from './screens/LoginScreen'
import { api, ApiError } from './lib/api'
import { destinoSeguro, lerResposta, montarPedido, type Desfecho } from './lib/authelia'
import { falhaDoStatus, type FalhaLogin } from './lib/login'
import { MAX_TENTATIVAS } from './lib/login-motor'
import './styles/global.css'

/**
 * Ponto de entrada da TELA DE ENTRAR.
 *
 * ELA FALA COM OS DOIS, E NESTA ORDEM: tenta o NOSSO backend (`POST /api/login`) e, se
 * ele responder **404**, cai no primeiro fator do Authelia (`POST /api/firstfactor`).
 * Até 25/09/2026 falava só com o Authelia; o PR #417 a trocou só para o nosso backend, e
 * essa troca INCONDICIONAL TIROU TODO MUNDO DO AR em 28/09/2026 — o relato foi "não
 * conseguimos logar no sistema".
 *
 * POR QUE A TROCA SECA QUEBRA, e por que o 404 é o discriminador certo. O corte do P19
 * tem DOIS lados e eles não viram juntos:
 *
 *   - o BACKEND respeita a chave: `/api/login` responde 404 enquanto
 *     `MOTOR_AUTENTICACAO_PROPRIA` está desligada, e desligada é o estado de produção;
 *   - a BORDA ainda manda quem não tem sessão para o host do Authelia, onde o Caddy
 *     serve esta página na raiz e despacha todo o resto — inclusive `/api/*` — para o
 *     Authelia. Ou seja: deste host o `POST /api/login` nem chega ao nosso backend.
 *
 * Nos DOIS casos a resposta é 404, e é por isso que o 404 basta: a página não precisa
 * saber em qual host está nem ler a chave. Quem responde ao login é quem existe.
 *
 * O 404 É SINAL DECLARADO, não palpite: está escrito no docstring da própria rota ("SÓ
 * ATENDE COM A AUTENTICAÇÃO PRÓPRIA LIGADA... responde 404 -- e não 501 ou 403"). E
 * SOMENTE o 404 cai para o Authelia — 401 é credencial recusada e 429 é trava de
 * tentativas, os dois do nosso backend depois do corte. Cair no Authelia num 401
 * gastaria uma tentativa da trava DELE com uma senha que o nosso servidor já recusou.
 *
 * A SENHA CHEGA A SER ENVIADA DUAS VEZES antes do corte, e isso é aceito com razão
 * medida: hoje o primeiro POST cai no nosso próprio Authelia (o catch-all do host de
 * auth), que devolve 404 sem ler o corpo — e é o MESMO serviço que vai receber a senha
 * no segundo POST, pelo caminho que autentica. Não há terceiro, nem rede nova, nem
 * armazenamento. Depois do corte não há segundo envio: `/api/login` responde e pronto.
 *
 * `api.entrar()` existia desde o PR #400 e não tinha chamador; o cliente puro do Authelia
 * (`lib/authelia.ts`) continuou inteiro e sem chamador depois do #417. Esta função religa
 * o segundo sem desligar o primeiro.
 *
 * ELA SEMPRE FOI PUBLICADA — e eu afirmei o contrário aqui, por algumas horas em
 * 25/09/2026. A "medição" que sustentava aquilo rodou `vite build`, o comando cru, e não
 * `npm run build`, que é o que o `Dockerfile.web` executa e que sempre fez os DOIS
 * builds (`vite build && vite build --config vite.entrar.config.ts`). O registro fica
 * porque a lição não é sobre esta página: medir o comando errado produz um defeito
 * convincente, com número e tudo, e o "conserto" dele foi que quase quebrou a
 * separação de bundles que `vite.entrar.config.ts` existe para garantir.
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

/**
 * O primeiro fator do Authelia: a chamada de REDE. A leitura da resposta continua em
 * `lib/authelia.ts`, que é pura de propósito — é ela que quebra em silêncio num bump de
 * versão do Authelia, e por isso é ela que precisa de teste sem DOM e sem servidor.
 *
 * Só é chamada quando o nosso `/api/login` responde 404. `falhas` é o contador DA TELA,
 * compartilhado com o caminho próprio: é ele que nomeia o bloqueio, e a régua de quem
 * bloqueia muda no corte (Authelia hoje, `db/sessoes.py` depois) sem que a tela precise
 * saber de qual dos dois veio a recusa.
 */
async function entrarPeloAuthelia(
  usuario: string,
  senha: string,
  manter: boolean,
  destino: string | null,
  falhas: { current: number },
): Promise<FalhaLogin | null> {
  let status = 0
  let corpo: unknown = null
  try {
    const r = await fetch('/api/firstfactor', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      // O cookie de sessão é o produto desta chamada: sem `same-origin` o navegador não o
      // guardaria, e o login "daria certo" sem autenticar ninguém.
      credentials: 'same-origin',
      body: JSON.stringify(montarPedido(usuario, senha, manter, destino)),
    })
    status = r.status
    corpo = await r.json().catch(() => null)
  } catch {
    // Rede caiu. Nunca "credencial".
    return 'indisponivel'
  }

  /* 404 OU 405 AQUI é o caso em que ninguém autentica: o nosso backend já disse que não é
     ele, e agora quem atendeu diz o mesmo. Aí a tela para de adivinhar e diz isso.

     O 405 entra junto porque é o que o NOSSO backend responde a `POST /api/firstfactor` —
     a rota não existe aqui —, e foi o status MEDIDO no log de 29/09/2026 quando o laço do
     `rd` despejou a tela no host do piloto. Sem ele, `lerResposta` traduzia por
     `indisponivel` ("o servidor pode estar reiniciando"), que é falso e manda a pessoa
     esperar: não há nada reiniciando, há um host sem autenticador. */
  if (status === 404 || status === 405) return 'nao-ligado'

  const desfecho: Desfecho = lerResposta(status, corpo, falhas.current)
  if (desfecho.tipo === 'entrou') {
    falhas.current = 0
    window.location.assign(desfecho.destino)
    // Não devolve `null`: a navegação leva alguns instantes e, sem isto, a tela voltaria
    // ao estado "parado" com o botão vivo — convidando um segundo envio.
    return await new Promise(() => {})
  }
  if (desfecho.tipo === 'segundo-fator') {
    /* O destino exige 2FA. Hoje nenhuma regra de `access_control` exige (as quatro são
       `one_factor`, lidas na VPS em 2026-09-22), então este ramo é rede de segurança — mas
       precisa existir ANTES de alguém ligar 2FA, senão a pessoa fica numa tela em branco,
       autenticada pela metade. O portal do Authelia continua inteiro em `/2fa`, que é o
       que permite passar o bastão. */
    window.location.assign(`/2fa${window.location.search}`)
    return await new Promise(() => {})
  }
  falhas.current += 1
  return desfecho.falha
}

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
    /* DOIS destinos a partir do MESMO `rd` validado, e a diferença não é estilo.
       Para NÓS, sem `rd` o certo é a raiz: mesma origem, é o piloto.
       Para o AUTHELIA, sem `rd` o certo é NÃO mandar `targetURL` — `montarPedido` omite o
       campo quando o destino é falso, e o Authelia usa o padrão dele. Mandar `'/'` seria a
       raiz do host de AUTH, que é esta própria tela de login: a pessoa digitaria a senha
       certa e voltaria ao formulário. Foi esse o laço que apareceu no log de produção em
       28/09/2026 (`entrar.html?rd=...entrar.html?rd=...`).

       O TERCEIRO ARGUMENTO fecha esse laço pelo outro lado, e ele foi preciso porque o
       conserto de 28/09 tratou só o caso `'/'` — não o caso geral, que é um `rd`
       apontando para a tela de entrar em QUALQUER host. `destinoSeguro` desembrulha esse
       `rd` aninhado até achar uma página de verdade; o docstring dela tem a medição. */
    const validado = destinoSeguro(rd, window.location.hostname, window.location.href)
    const destino = validado ?? '/'

    try {
      await api.entrar(usuario, senha, manter)
    } catch (erro) {
      if (!(erro instanceof ApiError)) {
        // Rede caiu, ou o timeout de 15 s estourou. NUNCA "credencial": afirmar que a
        // senha está errada porque o servidor não respondeu é mentir para a pessoa.
        return 'indisponivel'
      }
      if (erro.status === 404) {
        /* O corte do P19 não está virado NESTE ambiente: ou a chave está desligada, ou a
           borda nem entrega o `/api/login` ao nosso backend. Quem autentica é o Authelia,
           e é para ele que a senha vai.

           O 404 NÃO conta como tentativa — e essa ordem importa. Contar aqui inflaria o
           contador que nomeia o bloqueio, e a pessoa veria "muitas tentativas seguidas"
           no primeiro envio, por causa de uma porta fechada que ela nem escolheu. */
        return await entrarPeloAuthelia(usuario, senha, manter, validado, falhas)
      }
      falhas.current += 1
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
