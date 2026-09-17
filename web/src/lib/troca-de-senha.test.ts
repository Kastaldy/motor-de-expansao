import { describe, expect, it } from 'vitest'

import {
  deveOferecerTroca,
  estadoDaSenhaDoPayload,
  MINIMO_DE_CARACTERES,
  mensagemDoErro,
  podeEnviar,
  problemasDaSenha,
  textoDaTroca,
} from './troca-de-senha'

/* A tela de troca existe para tirar as pessoas da senha inicial COMPARTILHADA. O que se
   guarda aqui é o que pode mentir: a leitura defensiva do payload, a política espelhada
   do servidor, e a decisão de OFERECER em vez de OBRIGAR — que é escolha, e escolha sem
   teste vira acidente na próxima edição. */

describe('ler o estado do payload de /api/me', () => {
  it('lê o campo quando ele vem completo', () => {
    expect(estadoDaSenhaDoPayload({ senha: { deve_trocar: true, propria: false } })).toEqual({
      deveTrocar: true,
      propria: false,
    })
  })

  it('payload SEM o campo devolve null, e null não é false', () => {
    /* Backend anterior a 11/09 não manda `senha`. Se a ausência virasse `false`, a
       oferta de troca sumiria para todo mundo — e em silêncio, que é o pior modo. */
    expect(estadoDaSenhaDoPayload({ usuario: 'ana', abas: ['mapa'] })).toBeNull()
  })

  it('não confia no formato: lixo em qualquer posição devolve null', () => {
    for (const ruim of [null, undefined, 42, 'senha', [], { senha: null }, { senha: 'sim' }, { senha: {} }, { senha: { deve_trocar: 'sim' } }]) {
      expect(estadoDaSenhaDoPayload(ruim)).toBeNull()
    }
  })

  it('`propria` ausente não invalida o payload — só ela vira false', () => {
    /* `deve_trocar` é o campo que decide; `propria` só escolhe a frase. Recusar o
       payload inteiro por causa dela tiraria a oferta de quem precisa dela. */
    expect(estadoDaSenhaDoPayload({ senha: { deve_trocar: true } })).toEqual({
      deveTrocar: true,
      propria: false,
    })
  })
})

describe('a política, espelhada do servidor', () => {
  it('senha do tamanho certo não tem problema nenhum', () => {
    expect(problemasDaSenha('cavalo bateria grampo')).toEqual([])
  })

  it('curta demais diz QUANTOS faltam', () => {
    /* "mínimo 12" manda a pessoa contar; "faltam 3" não. */
    const p = problemasDaSenha('curta')
    expect(p).toHaveLength(1)
    expect(p[0]).toContain(`faltam ${MINIMO_DE_CARACTERES - 'curta'.length}`)
  })

  it('recusa espaço nas bordas', () => {
    expect(problemasDaSenha(' cavalo bateria ').join(' ')).toContain('espaço')
  })

  it('recusa passar do máximo', () => {
    expect(problemasDaSenha('x'.repeat(129)).join(' ')).toContain('129'.slice(0, 0) + '128')
  })

  it('avisa que a nova é igual à atual — regra que o SERVIDOR não tem', () => {
    /* Lá ele compara hash e não sabe. Aqui as duas estão na mão, e sem este aviso a
       pessoa "troca" a senha pela mesma e sai achando que trocou. */
    expect(problemasDaSenha('cavalo bateria', 'cavalo bateria').join(' ')).toContain('igual à atual')
    expect(problemasDaSenha('cavalo bateria', 'outra coisa aqui')).toEqual([])
  })

  it('devolve TODOS os problemas de uma vez, não o primeiro', () => {
    /* Corrigir um, tentar, descobrir o próximo é o que faz formulário de senha ser odiado. */
    expect(problemasDaSenha(' curta ').length).toBeGreaterThan(1)
  })

  it('campo vazio não acusa espaço nem igualdade — só o tamanho', () => {
    expect(problemasDaSenha('')).toHaveLength(1)
  })
})

describe('quando o botão libera', () => {
  const boa = 'cavalo bateria grampo'

  it('libera com os dois campos certos e a repetição batendo', () => {
    expect(podeEnviar('senha-inicial-2026', boa, boa)).toBe(true)
  })

  it('não libera se a repetição não bate', () => {
    expect(podeEnviar('senha-inicial-2026', boa, boa + 'x')).toBe(false)
  })

  it('não libera sem a senha atual — o servidor a exige', () => {
    expect(podeEnviar('', boa, boa)).toBe(false)
  })

  it('não libera com senha nova fora da política, mesmo repetida certo', () => {
    expect(podeEnviar('senha-inicial-2026', 'curta', 'curta')).toBe(false)
  })
})

describe('o recado de erro', () => {
  it('o texto do SERVIDOR tem precedência', () => {
    /* As mensagens de `senhas.py` são escritas para quem lê. Uma versão nossa por cima
       criaria duas verdades sobre a mesma recusa. */
    expect(mensagemDoErro(422, 'Essa é a senha inicial, que é a mesma para todo mundo.')).toBe(
      'Essa é a senha inicial, que é a mesma para todo mundo.',
    )
  })

  it('sem texto do servidor, cada status tem o seu', () => {
    expect(mensagemDoErro(403)).toContain('não confere')
    expect(mensagemDoErro(409)).toContain('cadastro')
    expect(mensagemDoErro(503)).toContain('indisponível')
    expect(mensagemDoErro(500)).toBe('Não foi possível trocar a senha agora.')
  })

  it('texto só de espaço conta como ausente', () => {
    expect(mensagemDoErro(403, '   ')).toContain('não confere')
  })

  it('o NÚMERO do status não é recado — conta como ausente', () => {
    /* Quando a resposta não tem corpo JSON, `pedir` põe `String(r.status)` na mensagem
       (api.ts:73). Sem esta guarda, a tela mostraria "403" para quem errou a senha. */
    expect(mensagemDoErro(403, '403')).toContain('não confere')
    expect(mensagemDoErro(503, '503')).toContain('indisponível')
  })
})

describe('a frase muda conforme a pessoa JÁ tem senha própria', () => {
  it('primeira vez: fala da senha inicial compartilhada', () => {
    const t = textoDaTroca({ deveTrocar: true, propria: false })
    expect(t.titulo).toBe('Defina a sua senha')
    expect(t.chamada).toContain('mesma para todo mundo')
  })

  it('já tinha senha própria: não diz "primeira"', () => {
    /* O caso em que o admin força a troca de novo. Os dois campos vêm `true`, e a frase
       da primeira vez seria mentira sobre o que já aconteceu. */
    const t = textoDaTroca({ deveTrocar: true, propria: true })
    expect(t.titulo).toBe('Troque a sua senha')
    expect(t.chamada).not.toContain('mesma para todo mundo')
  })
})

describe('OFERECE, e não OBRIGA', () => {
  it('oferece quando a coluna diz que sim', () => {
    expect(deveOferecerTroca({ deveTrocar: true, propria: false }, false)).toBe(true)
  })

  it('não oferece quando não sabe (banco fora, backend velho)', () => {
    /* `null` é "não sei". Oferecer no escuro poria um pop-up de senha na frente de quem
       talvez nem tenha cadastro. */
    expect(deveOferecerTroca(null, false)).toBe(false)
  })

  it('não oferece de novo depois de dispensado na sessão', () => {
    expect(deveOferecerTroca({ deveTrocar: true, propria: false }, true)).toBe(false)
  })

  it('DISPENSAR é possível — o pop-up não é parede', () => {
    /* Enquanto o P19 não acontece, quem autentica é o Authelia e a senha do banco não
       abre porta nenhuma. Trancar o piloto atrás dela tiraria o acesso dos seis
       cadastros de hoje em troca de zero segurança. Se um dia virar parede, é esta
       função que muda — e é este teste que vai vermelho avisando. */
    const estado = { deveTrocar: true, propria: false }
    expect(deveOferecerTroca(estado, true)).toBe(false)
    expect(deveOferecerTroca(estado, false)).toBe(true)
  })

  it('quem não deve trocar nunca vê o pop-up', () => {
    expect(deveOferecerTroca({ deveTrocar: false, propria: true }, false)).toBe(false)
  })
})
