import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { api, ApiError } from './api'
import {
  assinarQuedaDeSessao,
  diagnosticarAcesso,
  relatarFalhaDeRede,
  resetarEstadoDaSessao,
  ROTA_SONDA,
} from './sessao'

/**
 * Guarda do pop-up de sessão encerrada.
 *
 * A regressão que estes testes existem para pegar NÃO é "o pop-up não aparece" — é a
 * inversa, e mais cara: **o pop-up aparecer quando o problema é outro**. Dizer "sua
 * sessão expirou" com o backend fora do ar manda o operador relogar num sistema que
 * não vai responder, e ele perde a tarde. Por isso metade dos casos aqui é sobre
 * NÃO anunciar.
 *
 * O mecanismo real está documentado em `sessao.ts`: com a sessão vencida, o Authelia
 * responde 302 pelo `forward_auth` do Caddy, o `fetch` segue para outra origem, o CORS
 * derruba, e o erro chega ao JS como `TypeError` — igualzinho a servidor fora do ar.
 * Quem desempata é a sonda em `/api/health`.
 */

/** Resposta filtrada de redirect: é o que o browser devolve com `redirect: 'manual'`. */
const REDIRECT_OPACO = { type: 'opaqueredirect', status: 0, ok: false } as unknown as Response

function resposta(status: number, corpo: unknown = {}): Response {
  return {
    type: 'basic',
    status,
    ok: status >= 200 && status < 300,
    json: async () => corpo,
    headers: { get: () => null },
  } as unknown as Response
}

beforeEach(() => {
  resetarEstadoDaSessao()
})

afterEach(() => {
  vi.unstubAllGlobals()
  resetarEstadoDaSessao()
})

describe('diagnosticarAcesso — a sonda que separa sessão de servidor', () => {
  it('redirect opaco (o 302 do Authelia) = sessao', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => REDIRECT_OPACO))
    await expect(diagnosticarAcesso()).resolves.toBe('sessao')
  })

  it('401 = sessao (o outro ramo do Authelia)', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => resposta(401)))
    await expect(diagnosticarAcesso()).resolves.toBe('sessao')
  })

  it('200 = ok — em dev, com o backend no ar, nunca vira "sessão expirou"', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => resposta(200, { status: 'ok' })))
    await expect(diagnosticarAcesso()).resolves.toBe('ok')
  })

  it('a sonda também falhar = servidor (nao afirma sessao sem prova)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new TypeError('Failed to fetch')
      }),
    )
    await expect(diagnosticarAcesso()).resolves.toBe('servidor')
  })

  it('500 = servidor', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => resposta(500)))
    await expect(diagnosticarAcesso()).resolves.toBe('servidor')
  })

  it('sonda pede /api/health sem seguir redirect — sem `manual` o 302 fica invisível', async () => {
    const espia = vi.fn(async () => resposta(200))
    vi.stubGlobal('fetch', espia)
    await diagnosticarAcesso()
    expect(espia).toHaveBeenCalledTimes(1)
    const [url, init] = espia.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe(ROTA_SONDA)
    expect(init.redirect).toBe('manual')
  })
})

describe('relatarFalhaDeRede — quem avisa o App', () => {
  it('anuncia a queda quando a sonda diz sessao', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => REDIRECT_OPACO))
    const avisado = vi.fn()
    assinarQuedaDeSessao(avisado)
    await relatarFalhaDeRede()
    expect(avisado).toHaveBeenCalledTimes(1)
  })

  it('NAO anuncia quando a sonda diz servidor', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new TypeError('Failed to fetch')
      }),
    )
    const avisado = vi.fn()
    assinarQuedaDeSessao(avisado)
    await relatarFalhaDeRede()
    expect(avisado).not.toHaveBeenCalled()
  })

  it('NAO anuncia quando a sonda diz ok (blip de rede com a sessão viva)', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => resposta(200)))
    const avisado = vi.fn()
    assinarQuedaDeSessao(avisado)
    await relatarFalhaDeRede()
    expect(avisado).not.toHaveBeenCalled()
  })

  it('seis requisições falhando juntas mandam UMA sonda e avisam UMA vez', async () => {
    const espia = vi.fn(async () => REDIRECT_OPACO)
    vi.stubGlobal('fetch', espia)
    const avisado = vi.fn()
    assinarQuedaDeSessao(avisado)
    await Promise.all(Array.from({ length: 6 }, () => relatarFalhaDeRede()))
    expect(espia).toHaveBeenCalledTimes(1)
    expect(avisado).toHaveBeenCalledTimes(1)
  })

  it('cancelar a assinatura para de avisar', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => REDIRECT_OPACO))
    const avisado = vi.fn()
    assinarQuedaDeSessao(avisado)()
    await relatarFalhaDeRede()
    expect(avisado).not.toHaveBeenCalled()
  })
})

/** Deixa a sonda que `api.pedir` disparou em segundo plano terminar. NAO chama
 *  `relatarFalhaDeRede` de proposito: se o teste a chamasse, ele mesmo dispararia a
 *  sonda e passaria verde mesmo com a chamada apagada de `api.ts`. */
const deixarASondaTerminar = () => new Promise((r) => setTimeout(r, 0))

describe('api.pedir — o caminho por onde a falha real chega', () => {
  it('erro de rede + sonda "sessao" -> ApiError(0) E aviso de sessão', async () => {
    const avisado = vi.fn()
    assinarQuedaDeSessao(avisado)
    let primeira = true
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        if (primeira) {
          primeira = false
          throw new TypeError('Failed to fetch') // o 302 -> CORS chega assim
        }
        return REDIRECT_OPACO // a sonda
      }),
    )
    const espia = globalThis.fetch as unknown as ReturnType<typeof vi.fn>
    await expect(api.ufs()).rejects.toBeInstanceOf(ApiError)
    await deixarASondaTerminar()
    expect(espia).toHaveBeenCalledTimes(2) // a requisicao + a sonda que `api.ts` disparou
    expect(avisado).toHaveBeenCalledTimes(1)
  })

  it('erro de rede com o backend RESPONDENDO -> ApiError(0) e NENHUM aviso de sessão', async () => {
    const avisado = vi.fn()
    assinarQuedaDeSessao(avisado)
    let primeira = true
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        if (primeira) {
          primeira = false
          throw new TypeError('Failed to fetch')
        }
        return resposta(200, { status: 'ok' })
      }),
    )
    await expect(api.ufs()).rejects.toBeInstanceOf(ApiError)
    await deixarASondaTerminar()
    expect(avisado).not.toHaveBeenCalled()
  })

  it('a mensagem de rede não lidera pela porta 8899 (era o sintoma do pedido)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new TypeError('Failed to fetch')
      }),
    )
    const erro = (await api.ufs().catch((e: unknown) => e)) as ApiError
    expect(erro).toBeInstanceOf(ApiError)
    expect(erro.status).toBe(0)
    expect(erro.message).not.toContain('8899')
  })

  it('401 na própria resposta avisa a sessão sem precisar de sonda', async () => {
    const avisado = vi.fn()
    assinarQuedaDeSessao(avisado)
    const espia = vi.fn(async () => resposta(401, { detail: 'Unauthorized' }))
    vi.stubGlobal('fetch', espia)
    await expect(api.ufs()).rejects.toBeInstanceOf(ApiError)
    expect(avisado).toHaveBeenCalledTimes(1)
    expect(espia).toHaveBeenCalledTimes(1) // nenhuma sonda: o status já era prova
  })

  it('403 de aba negada NAO e sessao — o usuário está logado, só não tem a aba', async () => {
    const avisado = vi.fn()
    assinarQuedaDeSessao(avisado)
    vi.stubGlobal('fetch', vi.fn(async () => resposta(403, { detail: 'sem acesso' })))
    await expect(api.ufs()).rejects.toBeInstanceOf(ApiError)
    expect(avisado).not.toHaveBeenCalled()
  })
})
