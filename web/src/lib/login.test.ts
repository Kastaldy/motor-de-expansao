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

  it('o bloqueio diz que e bloqueio e oferece uma saida, SEM prometer prazo', () => {
    /* Ate' 25/09/2026 este teste exigia a string "10 minutos", que era o `ban_time` do
       `regulation` do Authelia. A regua passou a ser a NOSSA — `MAX_TENTATIVAS` recusas
       numa janela MOVEL de `JANELA_TENTATIVAS_MIN` minutos (`db/sessoes.py`) — e a
       diferenca nao e' de numero, e' de NATUREZA: la' havia um relogio fixo para esperar;
       aqui a janela DESLIZA, entao o que destrava e' a tentativa mais antiga envelhecer.
       Prometer um prazo mandaria a pessoa esperar algo que nao existe.

       O teste agora PROIBE o prazo em vez de exigi-lo, e cobra a saida que sempre
       funciona: pedir a um administrador para redefinir (redefinir DESTRAVA a conta). */
    const m = MENSAGEM_FALHA.bloqueado.toLowerCase()
    expect(m).toContain('bloque')
    expect(m).not.toMatch(/\d+\s*minutos?/)
    expect(m).toContain('administrador')
  })

  it('e congelado', () => {
    expect(Object.isFrozen(MENSAGEM_FALHA)).toBe(true)
  })
})
