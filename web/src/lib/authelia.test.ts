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
