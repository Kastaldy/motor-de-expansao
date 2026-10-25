import { afterEach, describe, expect, it, vi } from 'vitest'

import { api, ApiError, ESPERA_NOVA_TENTATIVA_503_MS, NOVAS_TENTATIVAS_503, repetirEm503 } from './api'

/* A nova tentativa do `/api/me` em 503 (#463, follow-up A). Com o banco vivo mas OCUPADO, o
   servidor deixou de esconder as abas sensíveis e passou a responder o 503 do gate — e a SPA,
   que pedia `/api/me` uma vez só, ficaria sem saber as abas até recarregar a página. */

function roteiro(...respostas: Array<'ok' | number>) {
  const chamadas: number[] = []
  const pedido = async () => {
    chamadas.push(chamadas.length + 1)
    const r = respostas[chamadas.length - 1]
    if (r === 'ok') return 'payload'
    throw new ApiError(`falhou com ${r}`, r)
  }
  return { pedido, chamadas }
}

const semEspera = () => Promise.resolve()

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('repetirEm503', () => {
  it('repete o 503 e devolve o primeiro sucesso', async () => {
    const r = roteiro(503, 503, 'ok')
    const esperas: number[] = []
    const saida = await repetirEm503(r.pedido, {
      esperar: async (ms) => {
        esperas.push(ms)
      },
    })
    expect(saida).toBe('payload')
    expect(r.chamadas).toHaveLength(3)
    expect(esperas).toEqual([ESPERA_NOVA_TENTATIVA_503_MS, ESPERA_NOVA_TENTATIVA_503_MS])
  })

  it('a espera é a do Retry-After do servidor (2 s), e são três tentativas no total', () => {
    expect(ESPERA_NOVA_TENTATIVA_503_MS).toBe(2_000)
    expect(NOVAS_TENTATIVAS_503).toBe(2)
  })

  it('desiste depois das tentativas e devolve o ÚLTIMO 503, para quem chama tratar como sempre', async () => {
    const r = roteiro(503, 503, 503, 'ok')
    await expect(repetirEm503(r.pedido, { esperar: semEspera })).rejects.toMatchObject({
      status: 503,
    })
    expect(r.chamadas).toHaveLength(NOVAS_TENTATIVAS_503 + 1)
  })

  it.each([401, 403, 404, 408, 500, 0])('NÃO repete o status %i', async (status) => {
    /* 401 é sessão (lib/sessao.ts cuida), 403/404 são definitivos, 0 é rede (a sonda de
       sessão já dispara) e 408 é a leitura que demorou demais — nenhum muda em 2 s. */
    const r = roteiro(status, 'ok')
    await expect(repetirEm503(r.pedido, { esperar: semEspera })).rejects.toMatchObject({ status })
    expect(r.chamadas).toHaveLength(1)
  })

  it('erro que não é do cliente da API atravessa sem nova tentativa', async () => {
    let chamadas = 0
    const pedido = async () => {
      chamadas++
      throw new TypeError('quebrou')
    }
    await expect(repetirEm503(pedido, { esperar: semEspera })).rejects.toBeInstanceOf(TypeError)
    expect(chamadas).toBe(1)
  })

  it('para de tentar se quem pediu desmontou durante a espera', async () => {
    const r = roteiro(503, 'ok')
    let vivo = true
    const esperar = async () => {
      vivo = false // o App desmontou enquanto esperava
    }
    await expect(repetirEm503(r.pedido, { esperar, vivo: () => vivo })).rejects.toMatchObject({
      status: 503,
    })
    expect(r.chamadas).toHaveLength(1)
  })

  it('sem 503, é uma chamada só e nenhuma espera', async () => {
    const r = roteiro('ok')
    const esperas: number[] = []
    await repetirEm503(r.pedido, {
      esperar: async (ms) => {
        esperas.push(ms)
      },
    })
    expect(r.chamadas).toHaveLength(1)
    expect(esperas).toEqual([])
  })

  it('ponta a ponta com o `api.me` de verdade: o 503 do servidor vira nova tentativa', async () => {
    /* A memo do `api.me` guarda só o SUCESSO: a falha a limpa, e é isso que deixa a nova
       tentativa ir ao servidor em vez de devolver o mesmo 503 memorizado. */
    const respostas = [
      {
        ok: false,
        status: 503,
        json: async () => ({ detail: 'Piloto ocupado no momento. Tente novamente em instantes.' }),
      },
      { ok: true, status: 200, json: async () => ({ usuario: 'ana', abas: ['mapa', 'executiva'] }) },
    ]
    const fetchFalso = vi.fn(async () => respostas.shift() as unknown as Response)
    vi.stubGlobal('fetch', fetchFalso)

    const me = await repetirEm503(() => api.me(), { esperar: semEspera })
    expect(me.abas).toEqual(['mapa', 'executiva'])
    expect(fetchFalso).toHaveBeenCalledTimes(2)
  })
})
