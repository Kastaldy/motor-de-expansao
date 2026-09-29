import { describe, expect, it } from 'vitest'

import { destinoSeguro, lerResposta, montarPedido } from './authelia'

describe('montarPedido', () => {
  it('monta o corpo no formato que o Authelia espera', () => {
    expect(montarPedido('felipe.silva', 'segredo', true, 'https://piloto.ultra-expansao.tech/')).toEqual({
      username: 'felipe.silva',
      password: 'segredo',
      keepMeLoggedIn: true,
      targetURL: 'https://piloto.ultra-expansao.tech/',
      requestMethod: 'GET',
    })
  })

  it('OMITE o targetURL quando nao ha destino, em vez de mandar vazio', () => {
    /* String vazia nao some na serializacao, e o Authelia a trataria como destino de
       verdade — redirecionando para lugar nenhum depois de um login bem-sucedido. */
    const p = montarPedido('felipe.silva', 'segredo', false, null)
    expect('targetURL' in p).toBe(false)
  })
})

describe('lerResposta', () => {
  it('200 com redirect = entrou', () => {
    const r = lerResposta(200, { status: 'OK', data: { redirect: 'https://x.tech/' } }, 0)
    expect(r).toEqual({ tipo: 'entrou', destino: 'https://x.tech/' })
  })

  it('200 SEM redirect = segundo fator, nao "entrou"', () => {
    /* E' o sinal que o `Handle1FAResponse` do Authelia emite (`ctx.ReplyOK()` com o log
       "requires 2FA, cannot be redirected yet"). Ler isso como sucesso deixaria a pessoa
       numa tela em branco, autenticada pela metade. */
    expect(lerResposta(200, { status: 'OK' }, 0)).toEqual({ tipo: 'segundo-fator' })
    expect(lerResposta(200, { status: 'OK', data: {} }, 0)).toEqual({ tipo: 'segundo-fator' })
    expect(lerResposta(200, { status: 'OK', data: { redirect: '   ' } }, 0)).toEqual({
      tipo: 'segundo-fator',
    })
  })

  it('corpo inesperado num 200 NAO vira "entrou"', () => {
    // A API nao tem contrato de estabilidade; um bump pode mudar o corpo sem aviso.
    expect(lerResposta(200, null, 0)).toEqual({ tipo: 'segundo-fator' })
    expect(lerResposta(200, 'texto', 0)).toEqual({ tipo: 'segundo-fator' })
  })

  it('401 nas primeiras tentativas e credencial', () => {
    expect(lerResposta(401, {}, 0)).toEqual({ tipo: 'falhou', falha: 'credencial' })
    expect(lerResposta(401, {}, 2)).toEqual({ tipo: 'falhou', falha: 'credencial' })
  })

  it('401 na 4a falha passa a avisar do BANIMENTO', () => {
    /* A API nao distingue credencial errada de banimento — os dois sao 401. Quem separa
       e' o contador da tela, porque o banimento e' deterministico: 4 falhas em 2 min. */
    expect(lerResposta(401, {}, 3)).toEqual({ tipo: 'falhou', falha: 'bloqueado' })
    expect(lerResposta(401, {}, 9)).toEqual({ tipo: 'falhou', falha: 'bloqueado' })
  })

  it('erro de servidor NUNCA vira credencial', () => {
    expect(lerResposta(500, {}, 0)).toEqual({ tipo: 'falhou', falha: 'indisponivel' })
    expect(lerResposta(502, {}, 3)).toEqual({ tipo: 'falhou', falha: 'indisponivel' })
    expect(lerResposta(0, {}, 3)).toEqual({ tipo: 'falhou', falha: 'indisponivel' })
  })
})

describe('destinoSeguro', () => {
  const host = 'auth.ultra-expansao.tech'

  it('aceita destino do mesmo dominio', () => {
    expect(destinoSeguro('https://piloto.ultra-expansao.tech/mapa', host)).toBe(
      'https://piloto.ultra-expansao.tech/mapa',
    )
    expect(destinoSeguro('https://ultra-expansao.tech/', host)).toBe('https://ultra-expansao.tech/')
  })

  it('RECUSA destino de fora — seria redirecionamento aberto', () => {
    /* Sem isto, bastaria mandar a alguem um link de login com `rd` para um site clonado:
       ela digitaria a senha de verdade e seria levada para la' logo em seguida. */
    expect(destinoSeguro('https://ultra-expansao.tech.malicioso.com/', host)).toBeNull()
    expect(destinoSeguro('https://outro.com/', host)).toBeNull()
    expect(destinoSeguro('//outro.com/', host)).toBeNull()
  })

  it('RECUSA esquema que nao seja https', () => {
    expect(destinoSeguro('http://piloto.ultra-expansao.tech/', host)).toBeNull()
    expect(destinoSeguro('javascript:alert(1)', host)).toBeNull()
  })

  it('ausencia de destino nao e erro — o Authelia usa o padrao dele', () => {
    expect(destinoSeguro(null, host)).toBeNull()
    expect(destinoSeguro('', host)).toBeNull()
  })

  it('caminho RELATIVO fica no proprio host — e isso e seguro', () => {
    /* O `rd` pode chegar como caminho, e resolve-lo contra o host atual e' o
       comportamento certo: o destino continua sendo nosso. O guarda existe contra
       destino de FORA, nao contra caminho. */
    expect(destinoSeguro('/mapa', host)).toBe('https://auth.ultra-expansao.tech/mapa')
    expect(destinoSeguro('::::', host)).toBe('https://auth.ultra-expansao.tech/::::')
  })

  it('o que PARECE relativo mas escapa do host e recusado', () => {
    // `//outro.com/` nao e caminho: o navegador o le como outro host, no mesmo esquema.
    expect(destinoSeguro('//outro.com/', host)).toBeNull()
  })
})

describe('destinoSeguro: o destino NAO pode ser a propria tela de entrar', () => {
  /* O laco de 29/09/2026, medido no access log do Caddy e reproduzido com `curl`:

       GET piloto.ultra-expansao.tech/entrar.html?rd=https://piloto.../
         -> 302 Location: auth.ultra-expansao.tech/?rd=<A TELA DE ENTRAR INTEIRA>

     `entrarNovamente()` manda para `/entrar.html` no host do piloto; esse caminho esta'
     atras do `forward_auth`, entao o `rd` que o Caddy carimba e' a tela de entrar. Sem
     desembrulhar, o Authelia autentica e devolve a pessoa AO FORMULARIO -- no host do
     piloto, onde `/api/login` e' 404 e `/api/firstfactor` e' 405. */

  const hostAuth = 'auth.ultra-expansao.tech'

  it('desembrulha o `rd` que o Caddy carimbou -- a URL LITERAL da producao', () => {
    const doCaddy =
      'https://piloto.ultra-expansao.tech/entrar.html' +
      '?rd=https%3A%2F%2Fpiloto.ultra-expansao.tech%2F'
    expect(destinoSeguro(doCaddy, hostAuth)).toBe('https://piloto.ultra-expansao.tech/')
  })

  it('devolve a pessoa a PAGINA que ela tentava abrir, nao a raiz', () => {
    const doCaddy =
      'https://piloto.ultra-expansao.tech/entrar.html' +
      '?rd=' + encodeURIComponent('https://piloto.ultra-expansao.tech/mapa?uf=SP')
    expect(destinoSeguro(doCaddy, hostAuth)).toBe(
      'https://piloto.ultra-expansao.tech/mapa?uf=SP',
    )
  })

  it('tela de entrar SEM `rd` dentro nao tem destino a recuperar', () => {
    // Null faz `montarPedido` OMITIR o targetURL; mandar a tela de entrar seria o laco.
    expect(destinoSeguro('https://piloto.ultra-expansao.tech/entrar.html', hostAuth)).toBeNull()
  })

  it('desembrulha ANINHAMENTO repetido (logout seguido de aviso de sessao)', () => {
    const dentro = 'https://piloto.ultra-expansao.tech/exec'
    const uma = 'https://piloto.ultra-expansao.tech/entrar.html?rd=' + encodeURIComponent(dentro)
    const duas = 'https://piloto.ultra-expansao.tech/entrar.html?rd=' + encodeURIComponent(uma)
    expect(destinoSeguro(duas, hostAuth)).toBe(dentro)
  })

  it('cadeia sem fim nao vira laco sem fim: desiste e devolve null', () => {
    /* `rd` e' dado de FORA. Um link montado a mao pode aninhar quantas vezes quiser, e o
       teto e' o que impede isso de travar a tela. */
    let url = 'https://piloto.ultra-expansao.tech/exec'
    for (let i = 0; i < 9; i += 1) {
      url = 'https://piloto.ultra-expansao.tech/entrar.html?rd=' + encodeURIComponent(url)
    }
    expect(destinoSeguro(url, hostAuth)).toBeNull()
  })

  it('a tela de entrar do PROPRIO host tambem e recusada', () => {
    // Depois do corte a tela e' servida no host do piloto; a regra nao olha host.
    expect(
      destinoSeguro(
        'https://piloto.ultra-expansao.tech/entrar.html?rd=https%3A%2F%2Fpiloto.ultra-expansao.tech%2F',
        'piloto.ultra-expansao.tech',
      ),
    ).toBe('https://piloto.ultra-expansao.tech/')
  })

  it('com `paginaAtual`, a RAIZ do host de auth tambem e auto-referencia', () => {
    /* Na raiz do host de auth a tela de entrar nao se chama `entrar.html` -- chama-se
       `/`. So' a pagina atual sabe disso, e por isso ela entra como argumento. */
    const aqui = 'https://auth.ultra-expansao.tech/?rd=qualquer'
    expect(destinoSeguro('https://auth.ultra-expansao.tech/', hostAuth, aqui)).toBeNull()
    // Sem o argumento, esse mesmo `rd` passaria batido -- e era o buraco que sobrava.
    expect(destinoSeguro('https://auth.ultra-expansao.tech/', hostAuth)).toBe(
      'https://auth.ultra-expansao.tech/',
    )
  })

  it('`paginaAtual` ignora query e fragmento: quem identifica pagina e o caminho', () => {
    const aqui = 'https://auth.ultra-expansao.tech/?rd=x#frag'
    expect(destinoSeguro('https://auth.ultra-expansao.tech/?outra=1', hostAuth, aqui)).toBeNull()
  })

  it('destino de VERDADE continua passando, com ou sem pagina atual', () => {
    const aqui = 'https://auth.ultra-expansao.tech/'
    expect(destinoSeguro('https://piloto.ultra-expansao.tech/mapa', hostAuth, aqui)).toBe(
      'https://piloto.ultra-expansao.tech/mapa',
    )
  })

  it('o desembrulho NAO afrouxa a regra de dominio', () => {
    /* Tela de entrar nossa, com `rd` para fora: desembrulhar nao pode virar porta de
       redirecionamento aberto. O `rd` de dentro passa pela MESMA regra. */
    const armadilha =
      'https://piloto.ultra-expansao.tech/entrar.html?rd=' +
      encodeURIComponent('https://sitefalso.com/')
    expect(destinoSeguro(armadilha, hostAuth)).toBeNull()
  })

  it('o desembrulho NAO afrouxa a regra de esquema', () => {
    const armadilha =
      'https://piloto.ultra-expansao.tech/entrar.html?rd=' +
      encodeURIComponent('http://piloto.ultra-expansao.tech/')
    expect(destinoSeguro(armadilha, hostAuth)).toBeNull()
  })

  it('caminho que so PARECE a tela de entrar nao e desembrulhado', () => {
    // `/docs/entrar.html.txt` e `/meu-entrar.html` sao paginas de verdade.
    expect(destinoSeguro('https://piloto.ultra-expansao.tech/meu-entrar.html', hostAuth)).toBe(
      'https://piloto.ultra-expansao.tech/meu-entrar.html',
    )
    expect(destinoSeguro('https://piloto.ultra-expansao.tech/a/entrar.html', hostAuth)).toBe(
      'https://piloto.ultra-expansao.tech/a/entrar.html',
    )
  })
})
