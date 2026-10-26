import { describe, expect, it } from 'vitest'

import {
  ARQUIVO_AUTHELIA,
  COLUNA_SENHA,
  dicaDoFormulario,
  loginProprioDoPayload,
  mensagemDeErroDoPainel,
  recadoDaCriacao,
  rodapeDoPainel,
  textoCorrido,
  tituloDoBotaoCriar,
  tituloDoSeloDaSenha,
} from './painel-usuarios'

/* Os textos da administração de usuários que dependem do login próprio (decisão do dono,
   24/10/2026). Até essa data a tela falava como se a chave já estivesse ligada; com ela
   DESLIGADA — o estado de produção até o corte do P19 — o recado de criação, o rodapé e o
   recado de 503 diziam coisas falsas. Cada bloco abaixo guarda uma delas nos DOIS estados. */

describe('ler a chave do payload', () => {
  it('só `true` de verdade liga; o resto conta como desligado, o lado conservador', () => {
    expect(loginProprioDoPayload({ login_proprio: true })).toBe(true)
    const ruins = [
      null,
      undefined,
      1,
      'sim',
      {},
      { login_proprio: 'true' },
      { login_proprio: 1 },
      { login_proprio: false },
    ]
    for (const ruim of ruins) expect(loginProprioDoPayload(ruim)).toBe(false)
  })
})

describe('a coluna e o selo falam da senha do BANCO', () => {
  it('a coluna se chama "Senha (banco)"', () => {
    expect(COLUNA_SENHA).toBe('Senha (banco)')
  })

  it('a dica diz que é a senha do banco nos quatro casos', () => {
    for (const propria of [true, false]) {
      for (const ligado of [true, false]) {
        expect(tituloDoSeloDaSenha(propria, ligado)).toContain('senha do banco')
      }
    }
  })

  it('desligado, a dica avisa que ela ainda não é usada para entrar', () => {
    const dica = tituloDoSeloDaSenha(false, false)
    expect(dica).toContain('ainda não é usada para entrar')
    expect(dica).toContain('Authelia')
  })

  it('ligado, a dica diz que é ela que o piloto confere', () => {
    const dica = tituloDoSeloDaSenha(true, true)
    expect(dica).toContain('confere na entrada')
    expect(dica).not.toContain('Authelia')
  })

  it('a dica distingue quem já definiu de quem está na inicial', () => {
    expect(tituloDoSeloDaSenha(true, true)).toContain('Já definiu')
    expect(tituloDoSeloDaSenha(false, true)).toContain('senha inicial do banco')
  })
})

describe('o recado depois de criar', () => {
  it('desligado: a pessoa ainda não entra, e o passo do Authelia é o que falta', () => {
    const r = recadoDaCriacao('ana', false)
    expect(r.titulo).toBe('ana foi criado no banco, mas ainda não consegue entrar.')
    expect(r.corpo).toContain(ARQUIVO_AUTHELIA)
    expect(r.corpo).toContain('login ana')
    // A frase que era falsa com a chave desligada não pode voltar.
    expect(r.corpo).not.toContain('levada a trocá-la')
  })

  it('ligado: a frase da senha inicial volta a valer, IDÊNTICA à da decisão do dono', () => {
    const r = recadoDaCriacao('ana', true)
    expect(r.titulo).toBe('ana foi criado e já pode entrar.')
    expect(r.corpo).toContain(
      'A senha inicial é a compartilhada do piloto, e a pessoa será levada a trocá-la no ' +
        'primeiro acesso.',
    )
    // O Authelia segue no recado, mas pelo rollback — durante a janela de observação.
    expect(r.corpo).toContain(ARQUIVO_AUTHELIA)
    expect(r.corpo).toContain('rollback')
  })
})

describe('o formulário de criação', () => {
  it('desligado, não promete troca no primeiro acesso', () => {
    expect(dicaDoFormulario(false)).not.toContain('primeiro acesso')
    expect(dicaDoFormulario(false)).toContain('Authelia')
    expect(tituloDoBotaoCriar(false)).toContain('Authelia')
  })

  it('ligado, diz que a pessoa troca a inicial no primeiro acesso', () => {
    expect(dicaDoFormulario(true)).toContain('primeiro acesso')
    expect(tituloDoBotaoCriar(true)).toContain('senha inicial')
  })
})

describe('o rodapé', () => {
  const desligado = textoCorrido(rodapeDoPainel(false))
  const ligado = textoCorrido(rodapeDoPainel(true))

  it('nunca diz que Redefinir OBRIGA a criar senha nova — a troca é oferecida', () => {
    /* A frase antiga ("obriga a criar uma senha nova na entrada") era falsa nos dois
       estados: desde 25/09/2026 a troca é recomendada, não obrigatória. */
    for (const texto of [desligado, ligado]) expect(texto).not.toContain('obriga a criar')
    expect(ligado).toContain('oferece, não obriga')
  })

  it('desligado: explica por que os gestos de senha não aparecem', () => {
    expect(desligado).toContain('só aparecem com o login próprio ligado')
    expect(desligado).toContain('Authelia')
    expect(desligado).not.toContain('gera uma senha temporária')
  })

  it('ligado: descreve o Redefinir e o Authelia como caminho de volta', () => {
    expect(ligado).toContain('gera uma senha temporária')
    expect(ligado).toContain('rollback')
  })

  it('a coluna aparece com o mesmo nome do cabeçalho, em destaque', () => {
    for (const estado of [false, true]) {
      expect(rodapeDoPainel(estado)).toContainEqual({ forte: COLUNA_SENHA })
    }
  })
})

describe('o recado de erro do painel', () => {
  it('503 NUNCA afirma que nada foi alterado', () => {
    for (const escrita of [false, true]) {
      for (const texto of ['Banco indisponível: PoolTimeout', '503', '']) {
        expect(mensagemDeErroDoPainel(503, texto, { escrita })).not.toContain('nada foi alterado')
      }
    }
  })

  it('503 numa escrita manda conferir a lista antes de repetir', () => {
    const m = mensagemDeErroDoPainel(503, 'Banco indisponível: PoolTimeout', { escrita: true })
    expect(m).toContain('Banco indisponível: PoolTimeout.')
    expect(m).toContain('recarregue a lista')
  })

  it('503 numa leitura é o texto do servidor, com ponto final', () => {
    expect(mensagemDeErroDoPainel(503, 'Banco indisponível: X')).toBe('Banco indisponível: X.')
    expect(mensagemDeErroDoPainel(503, 'Sem banco configurado.')).toBe('Sem banco configurado.')
    expect(mensagemDeErroDoPainel(503, '503')).toBe('O cadastro de usuários está indisponível agora.')
  })

  it('404 com o "Not Found" cru é a allowlist do painel', () => {
    expect(mensagemDeErroDoPainel(404, 'Not Found')).toBe(
      'O painel de acessos não está habilitado para este usuário.',
    )
  })

  it('404 com texto do servidor é OUTRA recusa, e o texto dele vale', () => {
    /* O login próprio desligado nos gestos de senha, ou gente que não existe. Até 24/10/2026
       todo 404 virava "painel não habilitado" — dito a quem administra o painel. */
    const recusa =
      'Redefinir senha e exigir troca só funcionam com o login próprio do piloto ligado.'
    expect(mensagemDeErroDoPainel(404, recusa)).toBe(recusa)
    expect(mensagemDeErroDoPainel(404, 'usuário 9 não existe')).toBe('usuário 9 não existe')
  })

  it('outros status: o texto do servidor, ou o status quando não há texto', () => {
    expect(mensagemDeErroDoPainel(409, 'Login em uso.')).toBe('Login em uso.')
    expect(mensagemDeErroDoPainel(500, '500')).toBe('O servidor recusou o pedido (500).')
  })
})
