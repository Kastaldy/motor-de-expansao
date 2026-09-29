/**
 * O contrato do `POST /api/firstfactor` do Authelia — a parte PURA, sem rede.
 *
 * POR QUE ISTO EXISTE SEPARADO. Estamos integrando com uma API que os mantenedores do
 * Authelia dizem, com todas as letras, NÃO ser caso de uso pretendido: ela não tem
 * contrato de estabilidade entre versões. Deixar a interpretação da resposta espalhada
 * dentro de um componente React tornaria impossível testá-la sem DOM e sem servidor — e
 * é justamente ela que precisa de teste, porque é o que quebra silenciosamente num bump
 * de versão do Authelia.
 *
 * O CONTRATO, lido no CÓDIGO-FONTE do Authelia (`internal/handlers/response.go`,
 * `Handle1FAResponse`) e na `api/openapi.yml`, não em suposição:
 *
 *   - Corpo: `{username, password, keepMeLoggedIn, targetURL, requestMethod}`
 *   - 200 com `data.redirect` -> autenticado; navegar para lá.
 *   - 200 SEM `data.redirect` -> o destino exige SEGUNDO FATOR. O handler faz
 *     `ctx.ReplyOK()` e loga *"requires 2FA, cannot be redirected yet"*. A ausência do
 *     redirect É o sinal; não há campo de status dizendo isso.
 *   - 401 -> credencial recusada.
 *
 * O que o contrato NÃO distingue: credencial errada de BANIMENTO por tentativas. Os dois
 * chegam como 401. Quem separa os dois é o contador da própria tela — o banimento é
 * determinístico (4 falhas em 2 min, 10 min de bloqueio; `regulation` lido na VPS em
 * 2026-09-22), então a partir da 4ª falha a tela para de dizer "senha incorreta".
 */

import type { FalhaLogin } from './login'

/** Corpo do pedido, no formato que o Authelia espera. */
export interface PedidoPrimeiroFator {
  username: string
  password: string
  keepMeLoggedIn: boolean
  /** Para onde voltar depois de entrar. Ausente = o Authelia usa o padrão dele. */
  targetURL?: string
  requestMethod: 'GET'
}

export function montarPedido(
  usuario: string,
  senha: string,
  manterConectado: boolean,
  destino: string | null,
): PedidoPrimeiroFator {
  return {
    username: usuario,
    password: senha,
    keepMeLoggedIn: manterConectado,
    // `undefined` some na serialização; string vazia NÃO — e o Authelia trataria "" como
    // um destino de verdade, redirecionando para lugar nenhum.
    ...(destino ? { targetURL: destino } : null),
    requestMethod: 'GET',
  }
}

/** O que fazer depois da resposta. */
export type Desfecho =
  | { tipo: 'entrou'; destino: string }
  | { tipo: 'segundo-fator' }
  | { tipo: 'falhou'; falha: FalhaLogin }

/**
 * Interpreta a resposta do primeiro fator.
 *
 * `tentativasFalhas` é quantas falhas ESTA tela já acumulou antes desta — é o que
 * permite nomear o banimento sem um campo que a API não tem.
 */
export function lerResposta(
  status: number,
  corpo: unknown,
  tentativasFalhas: number,
  limiteAteBanir = 4,
): Desfecho {
  if (status === 200) {
    const redirect = redirecionamentoDe(corpo)
    // SEM redirect num 200 é o sinal de segundo fator. Tratar isso como "entrou"
    // deixaria a pessoa numa tela em branco, autenticada pela metade.
    return redirect ? { tipo: 'entrou', destino: redirect } : { tipo: 'segundo-fator' }
  }
  if (status === 401 || status === 403) {
    // A PRÓXIMA tentativa depois desta é a que encontra o banimento; avisar a partir da
    // 4ª falha é o que impede a pessoa de gastar dez minutos repetindo a senha certa.
    const banido = tentativasFalhas + 1 >= limiteAteBanir
    return { tipo: 'falhou', falha: banido ? 'bloqueado' : 'credencial' }
  }
  // Qualquer outra coisa é INDISPONÍVEL, nunca credencial: dizer que a senha está errada
  // por causa de um 500 manda trocar uma senha que estava certa.
  return { tipo: 'falhou', falha: 'indisponivel' }
}

/** `{"status":"OK","data":{"redirect":"..."}}` — defensivo em cada nível, porque o
 *  corpo vem de fora e um bump do Authelia pode mudá-lo sem aviso. */
function redirecionamentoDe(corpo: unknown): string | null {
  if (!corpo || typeof corpo !== 'object') return null
  const data = (corpo as { data?: unknown }).data
  if (!data || typeof data !== 'object') return null
  const redirect = (data as { redirect?: unknown }).redirect
  return typeof redirect === 'string' && redirect.trim() ? redirect : null
}

/**
 * O caminho em que a tela de entrar é servida — em QUALQUER host do domínio.
 *
 * É a única rota de PÁGINA que o backend declara por nome (`web/server/app.py`), e a
 * tela existe nos dois hosts: no do Authelia o Caddy a serve na raiz, no do piloto ela
 * sai do nosso `dist/`. Saber o nome dela é o que permite a `destinoSeguro` reconhecer
 * um destino que é ELA MESMA.
 */
const CAMINHO_DA_TELA_DE_ENTRAR = '/entrar.html'

/** Teto de desembrulhos de `rd` aninhado. Ver `destinoSeguro`. */
const MAX_DESEMBRULHOS = 5

/**
 * Para onde o Authelia mandou a pessoa antes de ela cair no login.
 *
 * O `forward-auth` acrescenta `?rd=<url original>` ao redirecionar. Sem repassar isso no
 * `targetURL`, todo mundo entra e é jogado no destino padrão — perdendo a página que
 * estava tentando abrir.
 *
 * SÓ aceita destino do MESMO domínio da instância. Um `rd` apontando para fora vira um
 * redirecionamento aberto: bastaria mandar à pessoa um link de login com `rd` para um
 * site clonado, e ela seria levada para lá logo após digitar a senha de verdade.
 *
 * ## E RECUSA UM DESTINO QUE É A PRÓPRIA TELA DE ENTRAR
 *
 * Esta é a causa do laço relatado em 29/09/2026 — "às vezes entra, às vezes a tela de
 * login recarrega, some o usuário e sobra a senha" —, medida no access log do Caddy e
 * reproduzida com um `curl` sem cookie:
 *
 *     GET piloto.ultra-expansao.tech/entrar.html?rd=https://piloto.../
 *       -> 302 Location: auth.ultra-expansao.tech/?rd=<A TELA DE ENTRAR INTEIRA>
 *
 * `sessao.ts::entrarNovamente()` manda a pessoa para `/entrar.html` no host do PILOTO, e
 * esse caminho está ATRÁS do `forward_auth` — é o que o docstring de lá afirma, e é
 * verdade. Só que então o `rd` que o Caddy carimba é a URL INTEIRA da tela de entrar. A
 * página abre no host do Authelia, lê esse `rd`, ele passa na regra de domínio (é o mesmo
 * domínio, afinal) e vira o `targetURL`. O Authelia autentica, obedece, e devolve a
 * pessoa **ao formulário de login** — agora no host do piloto, onde `POST /api/login` é
 * 404 e `POST /api/firstfactor` é 405. Ali ninguém autentica, e toda tentativa seguinte
 * lê "não foi possível falar com o servidor de autenticação".
 *
 * O LOGIN TINHA FUNCIONADO. O cookie estava gravado — reabrir o site entrava direto, sem
 * pedir senha, e foi esse o detalhe do relato que desmontou três diagnósticos anteriores.
 * Errado estava o DESTINO, não a credencial. E é por isso que o sintoma era
 * intermitente: quem entrava pela raiz do piloto tinha `rd` limpo e passava; só quebrava
 * quem chegasse pelo aviso de sessão caída ou logo depois do logout.
 *
 * O CONSERTO É DESEMBRULHAR, NÃO RECUSAR. O `rd` de dentro do `rd` é exatamente a página
 * que a pessoa queria abrir; jogá-lo fora a mandaria para o destino padrão do Authelia
 * (`https://ultra-expansao.tech`, que também está atrás do portão e não é o piloto). O
 * laço tem teto porque `rd` aninhado é dado de fora: uma cadeia infinita não pode virar
 * laço infinito aqui.
 *
 * `paginaAtual` é opcional e cobre o outro jeito de um destino ser auto-referente —
 * apontar para ESTA página, seja qual for o caminho dela. Na raiz do host de auth a tela
 * de entrar não se chama `entrar.html`: chama-se `/`. Sem isso, um `rd` para aquela raiz
 * passaria batido pela regra de cima.
 */
export function destinoSeguro(
  bruto: string | null,
  hostAtual: string,
  paginaAtual?: string,
): string | null {
  const daqui = origemComCaminho(paginaAtual, hostAtual)
  let candidato = bruto
  for (let volta = 0; volta < MAX_DESEMBRULHOS; volta += 1) {
    const url = urlDoDominio(candidato, hostAtual)
    if (!url) return null
    if (!ehATelaDeEntrar(url, daqui)) return url.toString()
    // O destino é o próprio formulário: o que presta é o `rd` que ELE carrega.
    candidato = url.searchParams.get('rd')
  }
  return null
}

/** A URL, se for `https` e do domínio da instância. Qualquer outra coisa, `null`. */
function urlDoDominio(bruto: string | null, hostAtual: string): URL | null {
  if (!bruto) return null
  let url: URL
  try {
    url = new URL(bruto, `https://${hostAtual}`)
  } catch {
    return null
  }
  if (url.protocol !== 'https:') return null
  const raiz = dominioRaiz(hostAtual)
  return url.hostname === raiz || url.hostname.endsWith(`.${raiz}`) ? url : null
}

/** Este destino é o formulário de login — em qualquer host, ou esta própria página? */
function ehATelaDeEntrar(url: URL, daqui: string | null): boolean {
  if (url.pathname === CAMINHO_DA_TELA_DE_ENTRAR) return true
  return daqui !== null && `${url.origin}${url.pathname}` === daqui
}

/** `https://a.b/c?d=1#e` -> `https://a.b/c`. Query e fragmento não identificam página. */
function origemComCaminho(bruto: string | undefined, hostAtual: string): string | null {
  if (!bruto) return null
  try {
    const url = new URL(bruto, `https://${hostAtual}`)
    return `${url.origin}${url.pathname}`
  } catch {
    return null
  }
}

/** `auth.ultra-expansao.tech` -> `ultra-expansao.tech`. Dois rótulos bastam aqui porque
 *  a instância vive num domínio de dois níveis; não é um parser de sufixo público. */
function dominioRaiz(host: string): string {
  const partes = host.split('.')
  return partes.length <= 2 ? host : partes.slice(-2).join('.')
}
