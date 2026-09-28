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
    /* "mínimo N" manda a pessoa contar; "faltam 3" não. O número sai da constante de
       propósito: o piso já mudou uma vez (12 -> 8 em 25/09/2026) e um literal aqui envelheceria
       junto com a política que ele documenta. */
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
  it('sem senha própria: não AFIRMA qual das duas credenciais ela tem', () => {
    /* `propria: false` cobre DOIS estados que `/api/me` não distingue — a senha inicial
       compartilhada (quem nasceu pela tela) e uma temporária aleatória que expira (quem foi
       redefinido por admin, porque `SQL_REDEFINIR_SENHA` zera `senha_definida_em_usuario`).
       Até 25/09/2026 a frase afirmava "é a mesma para todo mundo da equipe", falso para o
       segundo — que, sem o bloqueio, lê isso, adia, e é trancado quando a temporária vence. */
    const t = textoDaTroca({ deveTrocar: true, propria: false })
    expect(t.titulo).toBe('Defina a sua senha')
    expect(t.chamada).not.toContain('mesma para todo mundo')
    expect(t.chamada).toContain('temporária')
    expect(t.chamada).toContain('expira')
  })

  it('já tinha senha própria: não diz "primeira"', () => {
    /* O caso em que o admin força a troca de novo. Os dois campos vêm `true`, e a frase
       da primeira vez seria mentira sobre o que já aconteceu. */
    const t = textoDaTroca({ deveTrocar: true, propria: true })
    expect(t.titulo).toBe('Troque a sua senha')
    expect(t.chamada).not.toContain('temporária')
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
    /* Decisão do dono em 25/09/2026: a troca é RECOMENDADA, não obrigatória. Entre 18/09 e
       25/09 ela foi obrigatória, e a parede NÃO estava aqui — era um 403 no servidor
       (`ROTAS_COM_TROCA_PENDENTE` em `web/server/acesso.py`). Então este teste guarda a
       escolha de OFERECER; ele não é, e nunca foi, o alarme de um bloqueio que mora noutra
       camada. Se a obrigatoriedade voltar, quem vai vermelho é o teste do portão de rota. */
    const estado = { deveTrocar: true, propria: false }
    expect(deveOferecerTroca(estado, true)).toBe(false)
    expect(deveOferecerTroca(estado, false)).toBe(true)
  })

  it('quem não deve trocar nunca vê o pop-up', () => {
    expect(deveOferecerTroca({ deveTrocar: false, propria: true }, false)).toBe(false)
  })
})
