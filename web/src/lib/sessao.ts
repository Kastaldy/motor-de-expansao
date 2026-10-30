/**
 * Queda de SESSÃO — como o piloto descobre, e como ele avisa.
 *
 * ## O defeito que isto conserta
 *
 * Com a sessão vencida, uma requisição a `/api/*` protegido volta **401**: a borda faz
 * `forward_auth` ao nosso `/api/verify` e o Caddy copia o 401 ao cliente (DEC-081). O
 * `lib/api.ts` já trata esse 401 direto (`relatarAcessoNegado`), sem precisar de sonda.
 *
 * Sobra o caso em que a falha chega como ERRO DE REDE (`TypeError`): um blip, um timeout
 * de proxy, ou o backend fora do ar. Do lado do JavaScript "sessão vencida" e "servidor
 * caído" podem chegar iguais — foi por isso que o operador já viu a frase de dev "Ele está
 * rodando na porta 8899?" (`api.ts`) quando o problema era outro. Para não adivinhar,
 * depois de uma falha de rede mandamos uma SONDA e classificamos pelo que ela responde.
 *
 * (Até a DEC-081 havia um terceiro caminho: com o Authelia na borda, a sessão vencida
 * virava um **302** cross-origin que o `fetch` seguia e o CORS derrubava como `TypeError`,
 * mascarando a queda; a sonda usava `redirect: 'manual'` para enxergar esse 302 como
 * `opaqueredirect`. Com o Authelia aposentado esse 302 não existe mais — a queda é o 401
 * acima —, então a sonda deixou de precisar do `manual` e do `opaqueredirect`.)
 *
 * ## Como distinguir (e por que NÃO adivinhar)
 *
 * Backend fora do ar e sessão vencida são coisas diferentes: dizer "sua sessão expirou"
 * para quem está com o servidor caído manda a pessoa relogar num sistema que não vai
 * responder. A sonda classifica assim:
 *
 *   - status 401 -> a borda respondeu negando o acesso: SESSÃO.
 *   - resposta 2xx -> a borda respondeu E nos reconhece: a sessão está viva, a falha
 *     original foi outra coisa (blip de rede, timeout de proxy). NÃO é sessão.
 *   - qualquer outro status, ou a sonda também rejeitar -> não dá para afirmar sessão:
 *     fica em `servidor` e o app segue com a mensagem de erro que já tinha.
 *
 * ## Por que a sonda é `/api/health`
 *
 * É a única rota que atravessa os portões do backend sem depender de nada do usuário:
 * está em `ROTAS_LIVRES` (sem gate de aba), fora de `SUPERFICIE_DA_ROTA` (sem gate de
 * país) — as duas em `web/server/acesso.py` — e em `_ROTAS_IGNORADAS` de
 * `src/motor_expansao/dashboard/acesso_log.py:45`, então a sonda NÃO polui a trilha de
 * acesso da DEC-027. Ela é barata e não tem efeito colateral nenhum.
 *
 * ## Em DEV isto fica quieto
 *
 * O `/api/health` atravessa o proxy do Vite e volta 200 -> `ok` -> nenhum pop-up. Com o
 * backend desligado a sonda falha -> `servidor` -> também nenhum pop-up, e a tela continua
 * mostrando o erro inline que sempre mostrou. O pop-up SÓ nasce do diagnóstico `sessao`.
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
    const r = await fetch(ROTA_SONDA, { cache: 'no-store' })
    // 401 = a borda respondeu negando o acesso. (Até a DEC-081 a queda também podia chegar
    // como 302 cross-origin -> `opaqueredirect`, do Authelia; aposentado ele, resta o 401.)
    if (r.status === 401) return 'sessao'
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
 * O aviso é entregue NO MÁXIMO uma vez a cada assinante: com o pop-up já na tela, as
 * outras requisições que falharem junto não têm o que anunciar.
 *
 * A queda fica TRAVADA: quem assina depois do anúncio recebe na hora da assinatura. Não
 * é detalhe — na carga inicial é a regra, não a exceção. No React os efeitos dos FILHOS
 * rodam antes dos do pai, e são as telas que disparam os fetches; com a sessão morta
 * desde o começo, a falha (e o anúncio) chega antes de o `App` conseguir assinar. Sem a
 * trava, o anúncio cai num conjunto vazio, `jaAnunciado` sela o silêncio para o resto da
 * carga e o operador fica com a tela sem dado NENHUM e sem aviso nenhum — que foi
 * exatamente o defeito relatado, e reproduzido em Chrome com a sessão expirada antes do
 * load.
 */
export function assinarQuedaDeSessao(ouvinte: Ouvinte): () => void {
  ouvintes.add(ouvinte)
  if (jaAnunciado) ouvinte()
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
 * Uma resposta que já diz, por si, que o acesso caiu (401 vindo da borda pelo Caddy).
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
 * VAI PARA `/entrar.html`: depois do corte (DEC-081) o matcher `@protegido` da borda cobre
 * só `/api/*`, então `/entrar.html` é servido direto e a pessoa vê a nossa tela de entrar.
 *
 * ERA `window.location.reload()`, e isso recarregaria a MESMA SPA — a primeira chamada
 * levaria 401 de novo, a sobreposição reabriria e o único botão dela faria tudo de novo. A
 * navegação de topo para `/entrar.html` é o que sai desse laço.
 *
 * O `rd` carrega de onde a pessoa veio, para o login devolvê-la à página que ela tentava
 * abrir. `lib/destino.ts::destinoSeguro` valida esse `rd` na outra ponta — RECUSA destino
 * de fora do domínio (senão o link viraria redirecionamento aberto) e desembrulha o `rd`
 * aninhado que a borda pode carimbar apontando para a própria tela de entrar (o laço
 * medido em 29/09/2026).
 */
export function entrarNovamente(): void {
  const destino = `/entrar.html?rd=${encodeURIComponent(window.location.href)}`
  window.location.assign(destino)
}

/** Só para os testes: zera a memo da sonda e o "já anunciei". */
export function resetarEstadoDaSessao(): void {
  sondaEmVoo = null
  jaAnunciado = false
  ouvintes.clear()
}
