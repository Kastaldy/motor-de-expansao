import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { api, ApiError } from './api'
import { ehQuedaDeSessao, entradaDoPayload,
  sair,
} from './login-motor'
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


describe('sair de verdade — revoga ANTES de navegar', () => {
  const ehApiError = (e: unknown): e is { status: number } =>
    typeof e === 'object' && e !== null && 'status' in e

  it('revogou no servidor: leva para a NOSSA tela de entrar', async () => {
    const chamou = vi.fn(async () => {})
    const s = await sair(chamou, 'https://auth.exemplo.tech/logout', ehApiError)
    expect(chamou).toHaveBeenCalledTimes(1)
    expect(s).toEqual({ tipo: 'ir', destino: '/entrar.html' })
  })

  it('404 = entrada propria DESLIGADA: quem encerra e o portal do Authelia', async () => {
    /* Mesmo idioma que `api.entrar()` ja usa: 404 e a resposta documentada de "a rota
       existe mas a chave esta desligada neste ambiente". */
    const s = await sair(
      async () => {
        throw { status: 404 }
      },
      'https://auth.exemplo.tech/logout',
      ehApiError,
    )
    expect(s).toEqual({ tipo: 'ir', destino: 'https://auth.exemplo.tech/logout' })
  })

  it('404 sem portal (dev): cai na nossa tela, que existe nos dois mundos', async () => {
    const s = await sair(
      async () => {
        throw { status: 404 }
      },
      null,
      ehApiError,
    )
    expect(s).toEqual({ tipo: 'ir', destino: '/entrar.html' })
  })

  it('503 NAO navega — a sessao continua aberta, e dizer o contrario seria mentir', async () => {
    /* E o defeito inteiro que este caminho existe para evitar: tela deslogada por cima
       de uma sessao viva. O proprio `/api/logout` declara isso inaceitavel. */
    const s = await sair(
      async () => {
        throw { status: 503 }
      },
      'https://auth.exemplo.tech/logout',
      ehApiError,
    )
    expect(s.tipo).toBe('falhou')
    if (s.tipo === 'falhou') expect(s.recado).toContain('continua aberta')
  })

  it('erro que nem e da API (rede caiu) tambem NAO navega', async () => {
    const s = await sair(
      async () => {
        throw new TypeError('Failed to fetch')
      },
      'https://auth.exemplo.tech/logout',
      ehApiError,
    )
    expect(s.tipo).toBe('falhou')
  })
})
