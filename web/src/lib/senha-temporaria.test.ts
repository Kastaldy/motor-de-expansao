import { describe, expect, it } from 'vitest'
import {
  AJUDA_GERAR_OUTRA,
  ROTULO_GERAR_OUTRA,
  avisoDaSenha,
  gruposDaSenha,
  podeFechar,
  recadoDaRedefinicao,
} from './senha-temporaria'

describe('o aviso que acompanha a senha', () => {
  it('diz que ela aparece UMA VEZ — é o que impede o admin de fechar achando que reconsulta', () => {
    expect(avisoDaSenha(2)).toContain('uma única vez')
  })

  it('diz o prazo em português, e concorda no singular', () => {
    expect(avisoDaSenha(2)).toContain('2 horas')
    expect(avisoDaSenha(1)).toContain('1 hora')
    expect(avisoDaSenha(1)).not.toContain('1 horas')
  })

  it('avisa que a pessoa terá de criar a própria senha', () => {
    // Sem isso o admin repassa a temporária como se fosse definitiva, e a pessoa estranha o
    // modal obrigatório na entrada.
    expect(avisoDaSenha(2)).toContain('própria senha')
  })
})

describe('o botão de emitir outra', () => {
  it('não se chama "rever": o gesto INVALIDA a anterior', () => {
    // Um rótulo que sugira consulta faria o admin clicar achando que só olha — e a senha que
    // ele acabou de ditar pararia de funcionar.
    expect(ROTULO_GERAR_OUTRA.toLowerCase()).not.toContain('rever')
    expect(ROTULO_GERAR_OUTRA.toLowerCase()).not.toContain('ver ')
    expect(ROTULO_GERAR_OUTRA.toLowerCase()).toContain('gerar')
  })

  it('a ajuda diz, em palavras, que a anterior morre', () => {
    expect(AJUDA_GERAR_OUTRA).toContain('invalida')
  })
})

describe('fechar o painel', () => {
  it('só depois de copiar ou confirmar que anotou', () => {
    // Fechar por engano perde a senha para sempre, e o sintoma aparece do outro lado da linha:
    // a pessoa não entra e ninguém entende por quê.
    expect(podeFechar(false, false)).toBe(false)
    expect(podeFechar(true, false)).toBe(true)
    expect(podeFechar(false, true)).toBe(true)
  })
})

describe('o recado da redefinição', () => {
  it('distingue derrubar a senha de alguém de arrumar o acesso de quem nunca entrou', () => {
    expect(recadoDaRedefinicao('ana', true)).toContain('apagada')
    expect(recadoDaRedefinicao('ana', false)).not.toContain('apagada')
  })

  it('nunca carrega a senha — o recado fica na tela depois do painel fechar', () => {
    expect(recadoDaRedefinicao('ana', true)).not.toMatch(/[a-z0-9]{4}-[a-z0-9]{4}/)
  })
})

describe('a senha fatiada para ditar', () => {
  it('devolve os grupos, porque ela vai ser lida em voz alta', () => {
    expect(gruposDaSenha('kvth-9rqm-2xbf')).toEqual(['kvth', '9rqm', '2xbf'])
  })

  it('não inventa grupo vazio se a forma mudar', () => {
    expect(gruposDaSenha('semhifen')).toEqual(['semhifen'])
    expect(gruposDaSenha('')).toEqual([])
  })
})
