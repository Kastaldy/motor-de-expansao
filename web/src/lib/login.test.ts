import { describe, expect, it } from 'vitest'

import {
  MENSAGEM_FALHA,
  falhaDoStatus,
  normalizarUsuario,
  podeEnviar,
  type FalhaLogin,
} from './login'

describe('podeEnviar', () => {
  it('exige os dois campos', () => {
    expect(podeEnviar('felipe.silva', 'segredo', 'parado')).toBe(true)
    expect(podeEnviar('', 'segredo', 'parado')).toBe(false)
    expect(podeEnviar('felipe.silva', '', 'parado')).toBe(false)
  })

  it('usuario so com espaco nao conta como preenchido', () => {
    /* Nao e' capricho: cada ida ao servidor gasta uma das 4 tentativas que o
       `regulation` conta antes de bloquear por 10 minutos. */
    expect(podeEnviar('   ', 'segredo', 'parado')).toBe(false)
  })

  it('senha so com espaco CONTA — espaco e caractere de senha', () => {
    expect(podeEnviar('felipe.silva', '   ', 'parado')).toBe(true)
  })

  describe('campo AUTOPREENCHIDO conta como preenchido', () => {
    /* O defeito, relatado duas vezes: com usuario e senha autopreenchidos o botao
       nascia cinza e so' acordava ao clicar em QUALQUER lugar da tela. O Chrome
       preenche na carga mas segura o valor da senha ate' haver um gesto — entao ler
       o DOM devolvia vazio, e o clique era o gesto que liberava. A habilitacao passa
       a olhar a PRESENCA do autofill, nao o valor. */

    it('os dois autopreenchidos, com valor ainda ilegivel, habilitam', () => {
      expect(podeEnviar('', '', 'parado', { usuario: true, senha: true })).toBe(true)
    })

    it('so a senha autopreenchida, com usuario digitado', () => {
      expect(podeEnviar('felipe.silva', '', 'parado', { senha: true })).toBe(true)
    })

    it('so um campo autopreenchido NAO basta', () => {
      expect(podeEnviar('', '', 'parado', { senha: true })).toBe(false)
      expect(podeEnviar('', '', 'parado', { usuario: true })).toBe(false)
    })

    it('nao afrouxa o resto: `enviando` continua bloqueando', () => {
      // Duplo clique com autofill gastaria duas das 4 tentativas.
      expect(podeEnviar('', '', 'enviando', { usuario: true, senha: true })).toBe(false)
    })

    it('sem autofill o comportamento e' + ' identico ao de antes', () => {
      expect(podeEnviar('', 'segredo', 'parado', {})).toBe(false)
      expect(podeEnviar('felipe.silva', '', 'parado', {})).toBe(false)
      expect(podeEnviar('felipe.silva', 'segredo', 'parado', {})).toBe(true)
    })

    it('`false` explicito nao habilita (nao basta a chave existir)', () => {
      expect(podeEnviar('', '', 'parado', { usuario: false, senha: false })).toBe(false)
    })
  })

  it('nao envia duas vezes enquanto o primeiro envio esta em voo', () => {
    // Duplo clique gastaria DUAS das 4 tentativas com a mesma credencial.
    expect(podeEnviar('felipe.silva', 'segredo', 'enviando')).toBe(false)
  })
})

describe('normalizarUsuario', () => {
  it('tira espaco das pontas e baixa a caixa', () => {
    // O teclado do celular capitaliza a primeira letra sozinho.
    expect(normalizarUsuario('  Felipe.Silva ')).toBe('felipe.silva')
  })

  it('nao mexe no que ja esta normalizado', () => {
    expect(normalizarUsuario('felipe.silva')).toBe('felipe.silva')
  })
})

describe('falhaDoStatus', () => {
  it('401 e 403 sao credencial', () => {
    expect(falhaDoStatus(401)).toBe('credencial')
    expect(falhaDoStatus(403)).toBe('credencial')
  })

  it('429 e bloqueio por tentativas', () => {
    expect(falhaDoStatus(429)).toBe('bloqueado')
  })

  it('erro de servidor NAO vira "senha errada"', () => {
    /* Afirmar que a credencial esta errada por causa de um 500 manda a pessoa trocar
       uma senha que estava certa — e gasta as tentativas dela no caminho. */
    expect(falhaDoStatus(500)).toBe('indisponivel')
    expect(falhaDoStatus(502)).toBe('indisponivel')
    expect(falhaDoStatus(0)).toBe('indisponivel')
  })
})

describe('MENSAGEM_FALHA', () => {
  it('toda falha tem mensagem preenchida', () => {
    const falhas: FalhaLogin[] = ['credencial', 'bloqueado', 'indisponivel', 'nao-ligado']
    for (const f of falhas) expect(MENSAGEM_FALHA[f].trim()).not.toBe('')
  })

  it('a mensagem de credencial NAO revela qual dos dois errou', () => {
    // Dizer "este usuario nao existe" entrega a lista de quem tem conta a quem sonda.
    const m = MENSAGEM_FALHA.credencial.toLowerCase()
    expect(m).toContain('usuário ou senha')
    expect(m).not.toMatch(/não existe|inexistente|não encontrado/)
  })

  it('o bloqueio diz que e bloqueio, e por quanto tempo', () => {
    /* A regua vem do `regulation` do Authelia (4 tentativas / 2 min / ban de 10 min).
       Se ela mudar la, esta mensagem mente — e o teste e o lembrete disso. */
    const m = MENSAGEM_FALHA.bloqueado.toLowerCase()
    expect(m).toContain('bloque')
    expect(m).toContain('10 minutos')
  })

  it('e congelado', () => {
    expect(Object.isFrozen(MENSAGEM_FALHA)).toBe(true)
  })
})
