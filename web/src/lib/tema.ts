/**
 * Tema visual do app — o valor, a persistência e nada mais.
 *
 * O claro nasceu na Visão Executiva, a única tela que sai do monitor: ela é projetada
 * em reunião e impressa em PDF, e num projetor o fundo escuro come o contraste que os
 * gráficos precisam ter. Por isso o `data-tema` morava no CONTAINER daquela aba.
 *
 * Desde 2026-08-25 ele vive no `<html>` e vale para as cinco telas (pedido do Juan). O
 * motivo de subir é o mesmo que fez o claro existir, agora dito para o produto todo:
 * a tela é apresentada, e metade dela clarear enquanto a outra metade continua preta
 * era o pior dos dois mundos. O escuro segue sendo o PADRÃO — ninguém é movido de tema
 * sem pedir.
 *
 * Nada aqui toca React nem lê `window` por conta própria — o depósito entra por
 * parâmetro, e quem escreve o atributo no DOM é o `App`. É o mesmo motivo de
 * `lib/periodo.ts` não ler o relógio: função que alcança o ambiente sozinha não tem
 * teste determinístico.
 */

export type Tema = 'escuro' | 'claro'

/** O tema do produto. Quem nunca escolheu nada entra por aqui. */
export const TEMA_PADRAO: Tema = 'escuro'

/** Chave no `localStorage`. Namespaced: o domínio é compartilhado com outras telas. */
export const CHAVE_TEMA = 'motor.tema'

/**
 * Onde a preferência morava enquanto o tema era só da Executiva.
 *
 * Lida como SEGUNDA opção por `lerTema`, e nunca escrita. Sem isto, quem já tinha
 * escolhido o claro na Executiva voltaria ao escuro no dia do deploy — e leria como
 * "o botão parou de funcionar", não como "a chave mudou de nome". A migração acontece
 * sozinha na primeira gravação, que já sai na chave nova.
 */
export const CHAVE_TEMA_LEGADA = 'motor.exec.tema'

/** Subconjunto do `Storage` que este módulo usa — o bastante para um duble em teste. */
export interface DepositoDeTema {
  getItem(chave: string): string | null
  setItem(chave: string, valor: string): void
}

export function ehTema(valor: unknown): valor is Tema {
  return valor === 'escuro' || valor === 'claro'
}

/** O outro tema. Existe para o botão não repetir a condicional em cada lugar. */
export function outroTema(tema: Tema): Tema {
  return tema === 'claro' ? 'escuro' : 'claro'
}

/**
 * Nome do cookie que leva o tema ATRAVÉS dos subdomínios.
 *
 * POR QUE UM COOKIE, tendo `localStorage`. O `localStorage` é partido por ORIGEM, e o
 * produto vive em DUAS: o piloto em `piloto.<dominio>` e a tela de entrar na raiz de
 * `auth.<dominio>`, host que ela divide com o portal do Authelia (ver `entrar.tsx`).
 * Quem escolhia o claro no piloto gravava na caixa de `piloto.`, e a tela de entrar lia
 * a caixa de `auth.` — sempre vazia, sempre caindo no escuro. O relato do Felipe em
 * 2026-09-25 foi exatamente esse: "a tela de login está vindo no tema escuro, mesmo pra
 * quem já tinha selecionado o tema claro anteriormente".
 *
 * O defeito NÃO aparece em desenvolvimento, e é por isso que atravessou a revisão
 * visual inteira: ali as duas páginas saem do MESMO `localhost:5000`, uma origem só.
 *
 * O cookie resolve porque o escopo dele é o DOMÍNIO, não a origem: gravado em
 * `<dominio>`, os dois subdomínios o leem. E é legível de forma SÍNCRONA — propriedade
 * que o `postMessage` não tem —, o que permite ler antes da primeira pintura; senão a
 * tela nasce preta e clareia, o flash que os dois bootstraps existem para evitar.
 *
 * Espelhado nos bootstraps de `index.html` e `entrar.html` — ao renomear aqui, renomeie
 * lá. `tema.test.ts` tem a guarda que torna o desencontro visível.
 */
export const COOKIE_TEMA = 'motor.tema'

/** Um ano. Preferência de cor não precisa expirar antes disso. */
export const COOKIE_TEMA_MAX_AGE = 31_536_000

/** Subconjunto do `document.cookie` que este módulo usa — duble trivial em teste. */
export interface DepositoDeCookie {
  /** O `document.cookie` cru, no formato `"a=1; b=2"`. */
  ler(): string
  /** Recebe um cookie já montado, como se fosse `document.cookie = valor`. */
  escrever(cookie: string): void
  /** O host de onde a página está sendo servida (`location.hostname`). */
  hospedeiro(): string
}

/**
 * O domínio em que o cookie tem de morar para os dois subdomínios o verem.
 *
 * Sobe UM nível: de `piloto.ultra-expansao.tech` para `ultra-expansao.tech`, que é o
 * escopo que `auth.ultra-expansao.tech` também lê. Subir de mais bate num sufixo público
  * A topologia MUDA no corte do P19 (DEC-067): a partir dele esta pagina e' servida pelo ho
  * st do PILOTO (`deploy/caddy/piloto-br.Caddyfile.template`), e nao pela raiz de `auth.`. 
  * O `auth.` continua existindo -- a instancia AR depende dele --, e o cookie continua sain
  * do com `Domain=<apex>`, entao o mecanismo descrito abaixo segue valendo nos dois casos.
 * (`.tech`, `.com.br`, `.co.uk`) e o navegador DESCARTA o cookie em silêncio — por isso a
 * regra é UM nível, e não "os dois últimos rótulos".
 *
 * Devolve `null` quando `Domain` não se aplica: `localhost`, endereço IP, host de um
 * rótulo só. Ali o cookie host-only já é o certo, e mandar `Domain` o faria ser
 * descartado. O host não é lido daqui nem cravado — entra por parâmetro, como o
 * depósito, e é `dominioCompartilhado` que fica testável sem navegador. Nenhum domínio
 * da Ultra aparece no código: a DEC-047 proíbe host cravado, e esta função serve
 * qualquer instância.
 */
export function dominioCompartilhado(hospedeiro: string | null | undefined): string | null {
  const host = (hospedeiro ?? '').trim().toLowerCase().replace(/\.$/, '')
  if (!host) return null
  if (host === 'localhost' || host.startsWith('[') || /^\d+(\.\d+){3}$/.test(host)) return null
  const rotulos = host.split('.')
  if (rotulos.length < 2) return null
  return rotulos.length >= 3 ? rotulos.slice(1).join('.') : host
}

/** O cookie pronto para atribuir a `document.cookie`. `dominio` nulo = host-only. */
export function montarCookieDeTema(tema: Tema, dominio: string | null): string {
  const partes = [
    `${COOKIE_TEMA}=${tema}`,
    'Path=/',
    `Max-Age=${COOKIE_TEMA_MAX_AGE}`,
    /* `Lax` basta: o cookie só precisa chegar em navegação de primeiro nível, que é como
       se alcança tanto o piloto quanto a tela de entrar. */
    'SameSite=Lax',
  ]
  /* SEM `Secure`, de propósito. O valor é uma preferência de cor — está na tela, não é
     credencial —, e `Secure` faria o navegador descartar o cookie em HTTP, desligando o
     mecanismo em SILÊNCIO no desenvolvimento e em qualquer host interno sem TLS. */
  if (dominio) partes.push(`Domain=${dominio}`)
  return partes.join('; ')
}

/** O tema guardado no `document.cookie` cru, ou `null` se não houver um legível. */
export function lerTemaDoCookie(cru: string | null | undefined): Tema | null {
  if (!cru) return null
  for (const par of cru.split(';')) {
    const corte = par.indexOf('=')
    if (corte < 0) continue
    if (par.slice(0, corte).trim() !== COOKIE_TEMA) continue
    const valor = par.slice(corte + 1).trim()
    if (ehTema(valor)) return valor
  }
  return null
}

/**
 * Tema guardado, ou o padrão.
 *
 * Valor irreconhecível cai no padrão em vez de virar `data-tema="lixo"`: o seletor não
 * casaria, a tela ficaria escura, e o botão passaria a alternar a partir de um estado
 * que ninguém escolheu. Depósito ausente ou que ESTOURA também cai no padrão — em janela
 * anônima e com cookies de terceiros bloqueados, o simples acesso a `localStorage`
 * levanta `SecurityError`, e perder a preferência é aceitável; derrubar a aba não é.
 *
 * ORDEM: `localStorage` desta origem, depois o cookie do domínio, depois a chave legada.
 * O `localStorage` vem primeiro porque é o registro mais direto desta origem — quem
 * acabou de trocar o tema aqui não pode ver um cookie mais velho vencer. O cookie é o
 * que atravessa subdomínios e é a ÚNICA fonte que a tela de entrar tem. Os dois
 * bootstraps de HTML repetem esta mesma ordem; divergir deles é o que produz flash.
 *
 * Cada fonte tem o seu `try`, e não um só ao redor de tudo: um `localStorage` que ESTOURA
 * não pode impedir a leitura do cookie, que é justamente a fonte de quem está na origem
 * mais restrita.
 */
export function lerTema(
  deposito: DepositoDeTema | null | undefined,
  cookie?: DepositoDeCookie | null,
): Tema {
  try {
    const bruto = deposito?.getItem(CHAVE_TEMA)
    if (ehTema(bruto)) return bruto
  } catch {
    /* sem `localStorage` legível; as outras fontes ainda valem */
  }
  try {
    const doCookie = lerTemaDoCookie(cookie?.ler())
    if (doCookie) return doCookie
  } catch {
    /* `document.cookie` inacessível; segue para a chave legada */
  }
  try {
    // Só chega aqui quem nunca gravou na chave nova. A antiga é lida uma vez e não é
    // apagada: remover exigiria `removeItem` no `DepositoDeTema`, e ampliar a interface
    // por causa de uma chave órfã de poucos bytes não se paga.
    const legado = deposito?.getItem(CHAVE_TEMA_LEGADA)
    return ehTema(legado) ? legado : TEMA_PADRAO
  } catch {
    return TEMA_PADRAO
  }
}

/**
 * Guarda a escolha nas DUAS caixas. Falha em silêncio: preferência de tema não vale uma
 * tela quebrada.
 *
 * O `localStorage` serve esta origem e o cookie serve o domínio — é ele que faz a tela de
 * entrar, servida de outro subdomínio, saber o que a pessoa escolheu aqui.
 *
 * A RELEITURA depois de gravar não é zelo: `Domain` recusado (sufixo público, IP, host sem
 * ponto) faz o navegador DESCARTAR o cookie sem erro nenhum — `document.cookie = ...` não
 * devolve nada e não levanta. Sem reler, o mecanismo morreria calado em qualquer domínio
 * cuja forma `dominioCompartilhado` não previsse. Não voltou, grava host-only: o tema
 * deixa de atravessar subdomínios, mas não se perde nesta origem.
 */
export function gravarTema(
  tema: Tema,
  deposito: DepositoDeTema | null | undefined,
  cookie?: DepositoDeCookie | null,
): void {
  try {
    deposito?.setItem(CHAVE_TEMA, tema)
  } catch {
    /* sem persistência; a sessão corrente continua no tema escolhido */
  }
  if (!cookie) return
  try {
    cookie.escrever(montarCookieDeTema(tema, dominioCompartilhado(cookie.hospedeiro())))
    if (lerTemaDoCookie(cookie.ler()) !== tema) {
      cookie.escrever(montarCookieDeTema(tema, null))
    }
  } catch {
    /* sem cookie; o tema vale nesta origem e a tela de entrar cai no padrão */
  }
}

/** O `localStorage`, quando existe. Fora do navegador (SSR, teste) devolve `null`. */
export function depositoDoNavegador(): DepositoDeTema | null {
  try {
    return typeof localStorage === 'undefined' ? null : localStorage
  } catch {
    return null
  }
}

/**
 * O `document.cookie`, quando existe. É a única parte deste módulo que toca o ambiente, e
 * ela não decide nada: o nome, o domínio e os atributos saem de `montarCookieDeTema` e
 * `dominioCompartilhado`, que são testáveis sem navegador.
 */
export function cookieDoNavegador(): DepositoDeCookie | null {
  try {
    if (typeof document === 'undefined' || typeof location === 'undefined') return null
    return {
      ler: () => document.cookie,
      escrever: (cookie: string) => {
        document.cookie = cookie
      },
      hospedeiro: () => location.hostname,
    }
  } catch {
    return null
  }
}
