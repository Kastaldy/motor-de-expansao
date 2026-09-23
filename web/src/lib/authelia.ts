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
 * Para onde o Authelia mandou a pessoa antes de ela cair no login.
 *
 * O `forward-auth` acrescenta `?rd=<url original>` ao redirecionar. Sem repassar isso no
 * `targetURL`, todo mundo entra e é jogado no destino padrão — perdendo a página que
 * estava tentando abrir.
 *
 * SÓ aceita destino do MESMO domínio da instância. Um `rd` apontando para fora vira um
 * redirecionamento aberto: bastaria mandar à pessoa um link de login com `rd` para um
 * site clonado, e ela seria levada para lá logo após digitar a senha de verdade.
 */
export function destinoSeguro(bruto: string | null, hostAtual: string): string | null {
  if (!bruto) return null
  let url: URL
  try {
    url = new URL(bruto, `https://${hostAtual}`)
  } catch {
    return null
  }
  if (url.protocol !== 'https:') return null
  const raiz = dominioRaiz(hostAtual)
  return url.hostname === raiz || url.hostname.endsWith(`.${raiz}`) ? url.toString() : null
}

/** `auth.ultra-expansao.tech` -> `ultra-expansao.tech`. Dois rótulos bastam aqui porque
 *  a instância vive num domínio de dois níveis; não é um parser de sufixo público. */
function dominioRaiz(host: string): string {
  const partes = host.split('.')
  return partes.length <= 2 ? host : partes.slice(-2).join('.')
}
