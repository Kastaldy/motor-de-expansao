/**
 * `destinoSeguro` — valida o `rd` (para onde devolver depois do login) e desembrulha o
 * caso em que ele aponta para a propria tela de entrar.
 *
 * ## DE ONDE VEIO
 *
 * Isto morava em `lib/authelia.ts`, ao lado do cliente do `firstfactor`. A DEC-081
 * aposentou o Authelia e, com ele, aquele cliente; esta funcao foi extraida para ca'
 * porque e' o pedaco que CONTINUA em uso. O `rd` sobrevive ao corte: quem manda alguem
 * para a tela de login continua podendo dizer para onde devolve-la depois de entrar
 * (`entrarNovamente` em `sessao.ts`, e a borda `forward_auth`, acrescentam
 * `?rd=<url original>`), e `entrar.tsx` continua chamando esta funcao para validar.
 *
 * ## O QUE ELA GARANTE
 *
 * SO' aceita destino `https` do MESMO dominio da instancia. Um `rd` apontando para fora
 * vira um redirecionamento aberto: bastaria mandar a' pessoa um link de login com `rd`
 * para um site clonado, e ela seria levada para la' logo apos digitar a senha de verdade.
 *
 * ## E RECUSA UM DESTINO QUE E' A PROPRIA TELA DE ENTRAR
 *
 * Esta e' a causa do laco relatado em 29/09/2026 — "as vezes entra, as vezes a tela de
 * login recarrega, some o usuario e sobra a senha" —, medida no access log do Caddy e
 * reproduzida com um `curl` sem cookie:
 *
 *     GET piloto.ultra-expansao.tech/entrar.html?rd=https://piloto.../
 *       -> 302 Location: .../?rd=<A TELA DE ENTRAR INTEIRA>
 *
 * `sessao.ts::entrarNovamente()` manda a pessoa para `/entrar.html`, e esse caminho pode
 * estar ATRAS do `forward_auth` da borda — entao o `rd` que o Caddy carimba e' a URL
 * INTEIRA da tela de entrar. A tela abre, le' esse `rd`, ele passa na regra de dominio (e'
 * o mesmo dominio, afinal) e viraria o destino pos-login. Obedecer a esse destino devolve
 * a pessoa **ao formulario de login** em vez de leva-la adiante — foi o laco medido.
 *
 * O CONSERTO E' DESEMBRULHAR, NAO RECUSAR. O `rd` de dentro do `rd` e' exatamente a pagina
 * que a pessoa queria abrir; joga-lo fora a mandaria para a raiz. O laco tem teto porque
 * `rd` aninhado e' dado de fora: uma cadeia infinita nao pode virar laco infinito aqui.
 *
 * `paginaAtual` e' opcional e cobre o outro jeito de um destino ser auto-referente —
 * apontar para ESTA pagina, seja qual for o caminho dela. Numa raiz de host a tela de
 * entrar pode nao se chamar `entrar.html`: pode chamar-se `/`. Sem isso, um `rd` para
 * aquela raiz passaria batido pela regra de cima.
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
    // O destino e' o proprio formulario: o que presta e' o `rd` que ELE carrega.
    candidato = url.searchParams.get('rd')
  }
  return null
}

/**
 * O caminho em que a tela de entrar e' servida — em QUALQUER host do dominio.
 *
 * E' a unica rota de PAGINA que o backend declara por nome (`web/server/app.py`). Saber o
 * nome dela e' o que permite a `destinoSeguro` reconhecer um destino que e' ELA MESMA.
 */
const CAMINHO_DA_TELA_DE_ENTRAR = '/entrar.html'

/** Teto de desembrulhos de `rd` aninhado. Ver `destinoSeguro`. */
const MAX_DESEMBRULHOS = 5

/** A URL, se for `https` e do dominio da instancia. Qualquer outra coisa, `null`. */
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

/** Este destino e' o formulario de login — em qualquer host, ou esta propria pagina? */
function ehATelaDeEntrar(url: URL, daqui: string | null): boolean {
  if (url.pathname === CAMINHO_DA_TELA_DE_ENTRAR) return true
  return daqui !== null && `${url.origin}${url.pathname}` === daqui
}

/** `https://a.b/c?d=1#e` -> `https://a.b/c`. Query e fragmento nao identificam pagina. */
function origemComCaminho(bruto: string | undefined, hostAtual: string): string | null {
  if (!bruto) return null
  try {
    const url = new URL(bruto, `https://${hostAtual}`)
    return `${url.origin}${url.pathname}`
  } catch {
    return null
  }
}

/** `auth.ultra-expansao.tech` -> `ultra-expansao.tech`. Dois rotulos bastam aqui porque
 *  a instancia vive num dominio de dois niveis; nao e' um parser de sufixo publico. */
function dominioRaiz(host: string): string {
  const partes = host.split('.')
  return partes.length <= 2 ? host : partes.slice(-2).join('.')
}
