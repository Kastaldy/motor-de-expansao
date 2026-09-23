/**
 * Para onde vai o botao "Sair" do Dock — a metade PURA, testavel sem DOM.
 *
 * O piloto NAO tem sessao propria: quem autentica e' o Authelia, e o app so' recebe
 * o header `Remote-User` que o Caddy repassa depois do `forward_auth`
 * (`web/server/acesso.py`, `deploy/caddy/piloto-ar.Caddyfile.template`). Logo, "sair"
 * nao e' limpar estado local — e' encerrar a sessao NO AUTHELIA. Limpar so' o estado
 * daqui seria pior que nao ter botao: a tela pareceria deslogada e a proxima
 * requisicao continuaria chegando autenticada.
 *
 * O DOMINIO NAO E' CRAVADO AQUI. O portal de login e' `auth.<apex>` do mesmo dominio
 * que serve o piloto (`https://auth.ultra-expansao.tech`, docs/infra_producao.md §
 * "Visao geral"; a mesma URL aparece no `rd=` do `forward_auth` do Caddy). Derivar do
 * `location.hostname` faz o botao valer nas DUAS instancias que existem hoje —
 * `piloto.ultra-expansao.tech` e `piloto-ar.ultra-expansao.tech`, que compartilham o
 * mesmo Authelia — e continuar valendo se o apex mudar, sem recompilar nada.
 *
 * Por que trocar o PRIMEIRO rotulo, e so' em host de piloto conhecido: a regra do
 * apex (dois ultimos rotulos) quebra em dominio ccSLD — `piloto.ultraacademia.com.br`
 * viraria `auth.com.br`, que qualquer terceiro pode registrar, e o botao levaria o
 * operador para FORA da Ultra. O dominio corporativo da Ultra e' exatamente um
 * `.com.br`, entao isso nao e' hipotese. Trocar o primeiro rotulo acerta os dois hosts
 * que existem hoje (`piloto.` e `piloto-ar.` — deploy/caddy/piloto-ar.Caddyfile.template
 * linha 24 e docs/deploy_piloto_web.md §3) e continuaria acertando num `.com.br`.
 * A raiz do dominio nao e' servida por deploy nenhum, entao nao ha' caso a cobrir la'.
 *
 * `null` = nao da' para afirmar que ha' Authelia na frente (dev local, IP nu, host sem
 * ponto). Quem chama NAO deve navegar nesse caso — em dev isso seria um 404 mudo.
 */

/** Hosts em que o piloto roda SEM Authelia na frente (dev local). */
const HOSTS_LOCAIS: ReadonlySet<string> = new Set(['localhost', '127.0.0.1', '0.0.0.0', '::1'])

/**
 * Primeiro rotulo dos hosts em que o piloto e' servido hoje. Vem do deploy, nao de
 * palpite: `piloto-ar.ultra-expansao.tech` esta em
 * deploy/caddy/piloto-ar.Caddyfile.template:24 e `piloto.ultra-expansao.tech` em
 * docs/deploy_piloto_web.md §3. Servir o piloto num rotulo novo exige acrescentar aqui —
 * e' de proposito: e' o que impede a funcao de adivinhar portal para um host qualquer.
 */
const ROTULOS_DO_PILOTO: ReadonlySet<string> = new Set(['piloto', 'piloto-ar'])

/**
 * Host do portal Authelia deste deploy, derivado do host da pagina.
 * Devolve `null` quando o ambiente nao tem portal (ver o cabecalho do modulo).
 */
export function hostDeAutenticacao(hostname: string | null | undefined): string | null {
  const host = (hostname ?? '').trim().toLowerCase().replace(/\.$/, '')
  if (!host) return null
  if (HOSTS_LOCAIS.has(host) || host.endsWith('.localhost')) return null
  // IPv6 chega entre colchetes em `location.hostname`; IPv4 e' so' digitos e pontos.
  // Nenhum dos dois tem apex do qual derivar `auth.` — e nenhum dos dois e' producao.
  if (host.startsWith('[') || host.includes(':') || /^[\d.]+$/.test(host)) return null
  const rotulos = host.split('.').filter(Boolean)
  // Falha FECHADA. Sem um rotulo de piloto conhecido nao ha' de onde derivar o portal
  // sem adivinhar, e adivinhar e' exatamente o que produzia `auth.com.br`. Devolver
  // `null` faz o botao dizer que nao ha' portal — melhor do que navegar para fora.
  if (rotulos.length < 3) return null
  if (!ROTULOS_DO_PILOTO.has(rotulos[0])) return null
  return `auth.${rotulos.slice(1).join('.')}`
}

/**
 * URL de logoff do Authelia, ou `null` se este ambiente nao tem portal.
 *
 * `/logout` e' a rota de encerramento do portal do Authelia 4.38 (a versao fixada em
 * `docker-compose.prod.yml`), e o logoff PRECISA passar por ela: quem invalida a sessao
 * e' o servidor, e limpar estado no cliente so' faria a tela parecer deslogada enquanto
 * a proxima requisicao seguiria autenticada.
 *
 * O `?rd=` VOLTOU, e a razao de ele ter saido caducou em 2026-09-22.
 *
 * Ate' aquele dia este modulo ia de proposito SEM destino, e o motivo escrito era: "o
 * proprio Authelia decide o pouso, e qualquer destino que o piloto pedisse voltaria a
 * bater no `forward_auth` — ou seja, na tela de login, que e' exatamente onde o logoff
 * deve terminar". O raciocinio estava certo enquanto a tela de login era a do Authelia.
 * Desde que a nossa passou a ocupar a raiz de `auth.`, o `/logout` sem destino deixa a
 * pessoa parada na tela do PORTAL — que e' a tela que o produto acabou de substituir.
 * Foi o que o Felipe viu ao clicar em Sair.
 *
 * O destino e' o PROPRIO host de onde a pessoa saiu, e nao a raiz de `auth.`: quem
 * deslogou do piloto-ar deve voltar a entrar no piloto-ar. O caminho passa pelo
 * `forward_auth` daquele host, que manda para a nossa tela com o `rd` preenchido — logo,
 * ao entrar de novo, a pessoa cai onde estava em vez de no portal de paises.
 *
 * NAO e' redirecionamento aberto, e isso nao depende de nos: o `SignOut` do Authelia
 * valida o destino NO SERVIDOR (`safeTargetURL`) antes de navegar, e cai na rota indice
 * dele quando o destino nao passa. Ainda assim so' montamos destino de host que
 * `hostDeAutenticacao` ja' reconheceu — duas travas, nenhuma dependendo da outra.
 */
export function urlDeLogoff(hostname: string | null | undefined): string | null {
  const host = hostDeAutenticacao(hostname)
  if (host === null) return null
  // `hostname` ja' passou pelo crivo de `hostDeAutenticacao`; normalizamos igual a ele
  // para o destino nao carregar o ponto final nem a caixa do host cru.
  const origem = (hostname ?? '').trim().toLowerCase().replace(/\.$/, '')
  return `https://${host}/logout?rd=${encodeURIComponent(`https://${origem}/`)}`
}
