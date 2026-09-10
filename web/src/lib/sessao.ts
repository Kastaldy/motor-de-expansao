/**
 * Queda de SESSÃO do Authelia — como o piloto descobre, e como ele avisa.
 *
 * ## O defeito que isto conserta
 *
 * O piloto não tem sessão própria: quem autentica é o Authelia, e o Caddy repassa o
 * usuário no header `Remote-User` (`web/server/acesso.py`, `web/server/app.py:359`).
 * O bloco do host, em `docs/deploy_piloto_web.md` §3, é:
 *
 *     piloto.ultra-expansao.tech {
 *         forward_auth authelia:9091 {
 *             uri /api/verify?rd=https://auth.ultra-expansao.tech
 *             copy_headers Remote-User Remote-Groups Remote-Name Remote-Email
 *         }
 *         reverse_proxy web:8899
 *     }
 *
 * `forward_auth` é açúcar de `reverse_proxy` com `@good status 2xx`: quando o Authelia
 * responde 2xx a requisição segue; quando responde QUALQUER outra coisa, o Caddy copia
 * essa resposta de volta ao cliente — status, headers e corpo. E o Authelia, no
 * endpoint legado `/api/verify` com `rd=`, responde à sessão ausente com **302** para a
 * tela de login (ele só devolve 401 quando o pedido se identifica como XHR ou não
 * aceita `text/html`; o `fetch` do browser manda o Accept curinga (`asterisco/asterisco`,
 * escrito por extenso aqui porque a sequencia literal fecharia este comentario), e o
 * curinga na primeira posicao conta como aceitar `text/html`).
 *
 * Consequência para a SPA: com a sessão expirada — `inactivity: 30m` na config do
 * Authelia, citada em `docs/spec_portal_selecao_pais.md:682` — o `fetch` de `/api/...`
 * recebe um 302 para `https://auth.ultra-expansao.tech/...`, SEGUE o redirect (o
 * default é `redirect: 'follow'`), bate noutra origem que não manda header de CORS e
 * **rejeita com `TypeError`**. Do lado do JavaScript isso é indistinguível de "o
 * servidor não respondeu" — e é por isso que o operador via a frase de dev
 * "Ele está rodando na porta 8899?" (`api.ts`) quando o que aconteceu foi o login
 * vencer. Meia hora parado numa aba aberta bastava.
 *
 * ## Como distinguir (e por que NÃO adivinhar)
 *
 * Backend fora do ar e sessão vencida são coisas diferentes: dizer "sua sessão expirou"
 * para quem está com o servidor caído manda a pessoa relogar num sistema que não vai
 * responder. Então, depois de uma falha de REDE, mandamos uma SONDA e classificamos
 * pelo que ela responde — sem inferir nada do erro original:
 *
 *   - `type === 'opaqueredirect'` (só possível com `redirect: 'manual'`) ou status 401
 *     -> a borda respondeu, e respondeu mandando para o login: SESSÃO.
 *   - resposta 2xx -> a borda respondeu E nos reconhece: a sessão está viva, a falha
 *     original foi outra coisa (blip de rede, timeout de proxy). NÃO é sessão.
 *   - qualquer outro status, ou a sonda também rejeitar -> não dá para afirmar sessão:
 *     fica em `servidor` e o app segue com a mensagem de erro que já tinha.
 *
 * `redirect: 'manual'` é o que torna o 302 VISÍVEL: com o `follow` default o redirect é
 * seguido e some dentro do erro de CORS; com `manual` o browser devolve uma resposta
 * filtrada de tipo `opaqueredirect` — sem corpo e sem headers, mas com o `type`, que é
 * tudo de que precisamos.
 *
 * ## Por que a sonda é `/api/health`
 *
 * É a única rota que atravessa os três portões do backend sem depender de nada do
 * usuário: está em `ROTAS_LIVRES` (sem gate de aba), fora de `SUPERFICIE_DA_ROTA` (sem
 * gate de país) — as duas em `web/server/acesso.py` — e em `_ROTAS_IGNORADAS` de
 * `src/motor_expansao/dashboard/acesso_log.py:45`, então a sonda NÃO polui a trilha de
 * acesso da DEC-027. Ela é barata e não tem efeito colateral nenhum.
 *
 * ## Em DEV isto fica quieto
 *
 * Sem Authelia na frente, o `/api/health` atravessa o proxy do Vite e volta 200 -> `ok`
 * -> nenhum pop-up. Com o backend desligado a sonda falha -> `servidor` -> também
 * nenhum pop-up, e a tela continua mostrando o erro inline que sempre mostrou. O
 * pop-up SÓ nasce do diagnóstico `sessao`.
 */

/** Rota da sonda. Ver o bloco "Por que a sonda é /api/health" acima. */
export const ROTA_SONDA = '/api/health'

/**
 * O que a sonda concluiu. Valores BRUTOS, sem acento (regra do CLAUDE.md §2) — o texto
 * acentuado que o operador lê vive no componente do pop-up.
 */
export type Diagnostico = 'sessao' | 'servidor' | 'ok'

/** Manda a sonda e classifica. Nunca lança: falha de sonda é `servidor`. */
export async function diagnosticarAcesso(): Promise<Diagnostico> {
  try {
    const r = await fetch(ROTA_SONDA, { redirect: 'manual', cache: 'no-store' })
    // `opaqueredirect` = a borda mandou um 3xx (o login do Authelia). 401 cobre o outro
    // ramo do Authelia, o que ele usa quando o pedido se declara XHR.
    if (r.type === 'opaqueredirect' || r.status === 401) return 'sessao'
    if (r.ok) return 'ok'
    return 'servidor'
  } catch {
    return 'servidor'
  }
}

type Ouvinte = () => void

const ouvintes = new Set<Ouvinte>()
let sondaEmVoo: Promise<Diagnostico> | null = null
let jaAnunciado = false

/**
 * Assina o aviso de sessão caída. Devolve a função de cancelar (molde de `useEffect`).
 * O aviso é disparado NO MÁXIMO uma vez por carga de página: com o pop-up já na tela,
 * as outras requisições que falharem junto não têm o que anunciar.
 */
export function assinarQuedaDeSessao(ouvinte: Ouvinte): () => void {
  ouvintes.add(ouvinte)
  return () => {
    ouvintes.delete(ouvinte)
  }
}

function anunciar(): void {
  if (jaAnunciado) return
  jaAnunciado = true
  for (const ouvinte of [...ouvintes]) ouvinte()
}

/**
 * Uma resposta que já diz, por si, que o acesso caiu (401 vindo do Authelia pelo Caddy).
 * Não precisa de sonda: o status é a prova.
 */
export function relatarAcessoNegado(): void {
  anunciar()
}

/**
 * Uma falha de REDE aconteceu. Sonda antes de afirmar qualquer coisa; só anuncia se o
 * diagnóstico for `sessao`.
 *
 * A sonda é MEMOIZADA enquanto estiver no ar: numa tela que dispara seis requisições em
 * paralelo, todas falham juntas e todas chamam isto — sem a memo seriam seis sondas
 * para responder a mesma pergunta.
 */
export function relatarFalhaDeRede(): Promise<Diagnostico> {
  if (jaAnunciado) return Promise.resolve<Diagnostico>('sessao')
  sondaEmVoo ??= diagnosticarAcesso().then((d) => {
    sondaEmVoo = null
    if (d === 'sessao') anunciar()
    return d
  })
  return sondaEmVoo
}

/**
 * Leva o operador de volta ao login DE VERDADE.
 *
 * `reload()` refaz a navegação de topo para a página atual. Sem sessão, essa navegação
 * passa pelo mesmo `forward_auth` do bloco de host citado no topo deste arquivo, o
 * Authelia responde 302 para `https://auth.ultra-expansao.tech/?rd=<url atual>` e o
 * browser SEGUE — navegação de topo não tem CORS, que é exatamente o que impedia o
 * `fetch` de fazer o mesmo. Depois do login, o `rd` traz a pessoa de volta ao piloto.
 *
 * Ou seja: não há URL de login para o front montar à mão, e montar uma seria inventar
 * um domínio que o front não conhece. Quem conhece é o Caddy. Em dev, sem Authelia na
 * frente, isto é só um F5 — não quebra nada.
 */
export function entrarNovamente(): void {
  window.location.reload()
}

/** Só para os testes: zera a memo da sonda e o "já anunciei". */
export function resetarEstadoDaSessao(): void {
  sondaEmVoo = null
  jaAnunciado = false
  ouvintes.clear()
}
