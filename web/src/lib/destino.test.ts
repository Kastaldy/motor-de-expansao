import { describe, expect, it } from 'vitest'

import { destinoSeguro } from './destino'

/* Extraido de `authelia.test.ts` na DEC-081: `montarPedido`/`lerResposta` sairam com o
   cliente do `firstfactor`; `destinoSeguro` continua, e a validacao de `rd` e' a mesma.

   PENTEST B6 (11/2026): a regra deixou de aceitar "qualquer subdominio do dominio" e passou
   a exigir o MESMO host. Por isso os cenarios abaixo usam o host do PILOTO tanto na pagina
   quanto no destino -- que e' o setup real pos-P19 (a tela de entrar e' servida pelo proprio
   host do piloto, nao mais por `auth.`). */

const HOST = 'piloto.ultra-expansao.tech'

describe('destinoSeguro', () => {
  it('aceita destino absoluto do MESMO host', () => {
    expect(destinoSeguro(`https://${HOST}/mapa`, HOST)).toBe(`https://${HOST}/mapa`)
  })

  it('RECUSA subdominio irmao, apex e host de fora (B6)', () => {
    // A regra antiga aceitava `*.ultra-expansao.tech`; com um irmao comprometido, isso
    // virava open redirect. Agora so' o proprio host passa.
    expect(destinoSeguro('https://outro.ultra-expansao.tech/x', HOST)).toBeNull()
    expect(destinoSeguro('https://ultra-expansao.tech/', HOST)).toBeNull()
    expect(destinoSeguro('https://piloto-ar.ultra-expansao.tech/', HOST)).toBeNull()
    expect(destinoSeguro('https://ultra-expansao.tech.malicioso.com/', HOST)).toBeNull()
    expect(destinoSeguro('https://outro.com/', HOST)).toBeNull()
    expect(destinoSeguro('//outro.com/', HOST)).toBeNull()
  })

  it('RECUSA o mesmo host em OUTRA porta (B6)', () => {
    expect(destinoSeguro(`https://${HOST}:8443/`, HOST)).toBeNull()
  })

  it('RECUSA credencial embutida na URL (B6)', () => {
    expect(destinoSeguro(`https://usuario:senha@${HOST}/`, HOST)).toBeNull()
  })

  it('RECUSA esquema que nao seja https', () => {
    expect(destinoSeguro(`http://${HOST}/`, HOST)).toBeNull()
    expect(destinoSeguro('javascript:alert(1)', HOST)).toBeNull()
  })

  it('ausencia de destino nao e erro — o chamador usa a raiz', () => {
    expect(destinoSeguro(null, HOST)).toBeNull()
    expect(destinoSeguro('', HOST)).toBeNull()
  })

  it('caminho RELATIVO fica no proprio host — e isso e seguro', () => {
    /* O `rd` pode chegar como caminho, e resolve-lo contra o host atual e' o comportamento
       certo: o destino continua sendo nosso. O guarda existe contra destino de FORA. */
    expect(destinoSeguro('/mapa', HOST)).toBe(`https://${HOST}/mapa`)
    expect(destinoSeguro('::::', HOST)).toBe(`https://${HOST}/::::`)
  })
})

describe('destinoSeguro: o destino NAO pode ser a propria tela de entrar', () => {
  /* O laco de 29/09/2026, medido no access log do Caddy e reproduzido com `curl`:

       GET piloto.ultra-expansao.tech/entrar.html?rd=https://piloto.../
         -> 302 Location: .../?rd=<A TELA DE ENTRAR INTEIRA>

     `entrarNovamente()` manda para `/entrar.html`; esse caminho pode estar atras do
     `forward_auth`, entao o `rd` que o Caddy carimba e' a tela de entrar. Sem desembrulhar,
     obedecer a esse destino devolve a pessoa AO FORMULARIO. */

  it('desembrulha o `rd` que o Caddy carimbou -- a URL LITERAL da producao', () => {
    const doCaddy = `https://${HOST}/entrar.html?rd=https%3A%2F%2F${HOST}%2F`
    expect(destinoSeguro(doCaddy, HOST)).toBe(`https://${HOST}/`)
  })

  it('devolve a pessoa a PAGINA que ela tentava abrir, nao a raiz', () => {
    const doCaddy =
      `https://${HOST}/entrar.html?rd=` + encodeURIComponent(`https://${HOST}/mapa?uf=SP`)
    expect(destinoSeguro(doCaddy, HOST)).toBe(`https://${HOST}/mapa?uf=SP`)
  })

  it('tela de entrar SEM `rd` dentro nao tem destino a recuperar', () => {
    expect(destinoSeguro(`https://${HOST}/entrar.html`, HOST)).toBeNull()
  })

  it('desembrulha ANINHAMENTO repetido (logout seguido de aviso de sessao)', () => {
    const dentro = `https://${HOST}/exec`
    const uma = `https://${HOST}/entrar.html?rd=` + encodeURIComponent(dentro)
    const duas = `https://${HOST}/entrar.html?rd=` + encodeURIComponent(uma)
    expect(destinoSeguro(duas, HOST)).toBe(dentro)
  })

  it('cadeia sem fim nao vira laco sem fim: desiste e devolve null', () => {
    let url = `https://${HOST}/exec`
    for (let i = 0; i < 9; i += 1) {
      url = `https://${HOST}/entrar.html?rd=` + encodeURIComponent(url)
    }
    expect(destinoSeguro(url, HOST)).toBeNull()
  })

  it('com `paginaAtual`, a RAIZ do host tambem e auto-referencia', () => {
    /* Numa raiz de host a tela de entrar nao se chama `entrar.html` -- chama-se `/`. So'
       a pagina atual sabe disso, e por isso ela entra como argumento. */
    const aqui = `https://${HOST}/?rd=qualquer`
    expect(destinoSeguro(`https://${HOST}/`, HOST, aqui)).toBeNull()
    // Sem o argumento, esse mesmo `rd` passaria batido -- e era o buraco que sobrava.
    expect(destinoSeguro(`https://${HOST}/`, HOST)).toBe(`https://${HOST}/`)
  })

  it('`paginaAtual` ignora query e fragmento: quem identifica pagina e o caminho', () => {
    const aqui = `https://${HOST}/?rd=x#frag`
    expect(destinoSeguro(`https://${HOST}/?outra=1`, HOST, aqui)).toBeNull()
  })

  it('o desembrulho NAO afrouxa a regra de host: `rd` interno para fora e recusado', () => {
    const armadilha =
      `https://${HOST}/entrar.html?rd=` + encodeURIComponent('https://sitefalso.com/')
    expect(destinoSeguro(armadilha, HOST)).toBeNull()
    // Nem para um subdominio irmao.
    const irmao =
      `https://${HOST}/entrar.html?rd=` +
      encodeURIComponent('https://piloto-ar.ultra-expansao.tech/')
    expect(destinoSeguro(irmao, HOST)).toBeNull()
  })

  it('o desembrulho NAO afrouxa a regra de esquema', () => {
    const armadilha = `https://${HOST}/entrar.html?rd=` + encodeURIComponent(`http://${HOST}/`)
    expect(destinoSeguro(armadilha, HOST)).toBeNull()
  })

  it('caminho que so PARECE a tela de entrar nao e desembrulhado', () => {
    expect(destinoSeguro(`https://${HOST}/meu-entrar.html`, HOST)).toBe(`https://${HOST}/meu-entrar.html`)
    expect(destinoSeguro(`https://${HOST}/a/entrar.html`, HOST)).toBe(`https://${HOST}/a/entrar.html`)
  })
})
