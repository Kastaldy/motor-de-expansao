import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { api, ApiError } from './api'
import { ehQuedaDeSessao, entradaDoPayload } from './login-motor'
import { assinarQuedaDeSessao, resetarEstadoDaSessao } from './sessao'

describe('entradaDoPayload', () => {
  it('lê o pedido de troca de senha', () => {
    expect(entradaDoPayload({ deve_trocar_senha: true })).toEqual({ deveTrocarSenha: true })
    expect(entradaDoPayload({ deve_trocar_senha: false })).toEqual({ deveTrocarSenha: false })
  })

  it('campo ausente ou de tipo errado NÃO abre a troca', () => {
    // "Não sei" não pode virar "abra a tela de troca": abrir sem necessidade trava a
    // pessoa logo depois de ela entrar.
    for (const bruto of [{}, null, 'sim', { deve_trocar_senha: 'true' }, { deve_trocar_senha: 1 }]) {
      expect(entradaDoPayload(bruto)).toEqual({ deveTrocarSenha: false })
    }
  })
})

describe('ehQuedaDeSessao', () => {
  it('401 do LOGIN não é sessão caída', () => {
    // A armadilha que esta função existe para fechar: `lib/api.ts` anuncia queda de
    // sessão em todo 401, e o anúncio é de MÃO ÚNICA (`jaAnunciado` nunca volta atrás).
    // Sem esta exceção, errar a senha uma vez abriria "Sessão encerrada", travaria a
    // trava para o resto da carga e ofereceria como única saída recarregar a página.
    expect(ehQuedaDeSessao('/api/login')).toBe(false)
  })

  it('401 de qualquer outra rota continua sendo sessão caída', () => {
    // A exceção é CIRÚRGICA: tirar o anúncio das demais rotas devolveria o defeito que
    // o `AvisoSessao` foi criado para resolver — a pessoa via "está rodando na porta
    // 8899?" quando o que tinha acontecido era o login vencer.
    for (const url of ['/api/me', '/api/uf/SP', '/api/relatorio/pontual', '/api/logout']) {
      expect(ehQuedaDeSessao(url)).toBe(true)
    }
  })
})

/* ---------------------------------------------------------------------------
   A LIGAÇÃO, e não só a função.

   Os testes de `ehQuedaDeSessao` acima exercitam a função ISOLADA — e isso não
   prova nada sobre o comportamento real: tirar a chamada dela do `lib/api.ts`
   deixaria todos eles verdes. A garantia que importa é o caminho completo, e é
   ele que este bloco percorre, com o `fetch` falsificado.
   --------------------------------------------------------------------------- */
describe('401 do login não pode virar "Sessão encerrada"', () => {
  let avisos: number

  beforeEach(() => {
    resetarEstadoDaSessao()
    avisos = 0
    assinarQuedaDeSessao(() => {
      avisos += 1
    })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    resetarEstadoDaSessao()
  })

  function responder401() {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: false,
        status: 401,
        type: 'basic',
        json: async () => ({ detail: 'Login ou senha incorretos.' }),
      })),
    )
  }

  it('senha errada NÃO anuncia queda de sessão', async () => {
    responder401()
    await expect(api.entrar('vinicius', 'errada')).rejects.toBeInstanceOf(ApiError)
    expect(avisos).toBe(0)
  })

  it('e a trava de mão única NÃO é acionada — dá para tentar de novo', async () => {
    // `jaAnunciado` em `lib/sessao.ts` nunca volta atrás. Se a primeira senha errada
    // acionasse a trava, a segunda tentativa já nasceria dentro do pop-up de sessão,
    // com "recarregar a página" como única saída. É o vaivém que este teste impede.
    responder401()
    await expect(api.entrar('vinicius', 'errada')).rejects.toBeInstanceOf(ApiError)
    await expect(api.entrar('vinicius', 'errada2')).rejects.toBeInstanceOf(ApiError)
    expect(avisos).toBe(0)
  })

  it('mas 401 de OUTRA rota continua anunciando', async () => {
    // A exceção é cirúrgica. Sem esta metade, "silenciar o 401 do login" poderia virar
    // "silenciar todo 401" sem nenhum teste reclamar — e voltaria o defeito que o
    // `AvisoSessao` existe para resolver.
    responder401()
    await expect(api.me()).rejects.toBeInstanceOf(ApiError)
    expect(avisos).toBe(1)
  })
})

