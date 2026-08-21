import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { CHAVE_VISITAS, alternarVisita, lerVisitas, salvarVisitas } from './visitas'

/** Stub minimo de localStorage (a suite roda em ambiente node, sem DOM). */
function stubStorage() {
  const dados = new Map<string, string>()
  return {
    getItem: (k: string) => dados.get(k) ?? null,
    setItem: (k: string, v: string) => void dados.set(k, v),
    removeItem: (k: string) => void dados.delete(k),
    clear: () => dados.clear(),
    key: () => null,
    get length() {
      return dados.size
    },
  } as Storage
}

const original = (globalThis as { localStorage?: Storage }).localStorage

beforeEach(() => {
  ;(globalThis as { localStorage?: Storage }).localStorage = stubStorage()
})

afterEach(() => {
  ;(globalThis as { localStorage?: Storage }).localStorage = original
})

describe('visitas', () => {
  it('ler/salvar fazem a viagem completa pela chave publicada', () => {
    salvarVisitas(new Set(['im_a', 'im_b']))
    expect(JSON.parse(localStorage.getItem(CHAVE_VISITAS)!).sort()).toEqual(['im_a', 'im_b'])
    expect(lerVisitas()).toEqual(new Set(['im_a', 'im_b']))
  })

  it('alternarVisita liga, desliga e persiste sem mutar o conjunto anterior', () => {
    const antes = new Set<string>()
    const ligado = alternarVisita(antes, 'im_x')
    expect(ligado.has('im_x')).toBe(true)
    expect(antes.size).toBe(0)
    expect(lerVisitas().has('im_x')).toBe(true)

    const desligado = alternarVisita(ligado, 'im_x')
    expect(desligado.has('im_x')).toBe(false)
    expect(lerVisitas().has('im_x')).toBe(false)
  })

  it('storage indisponivel degrada para conjunto vazio, nunca quebra', () => {
    ;(globalThis as { localStorage?: Storage }).localStorage = undefined
    expect(lerVisitas()).toEqual(new Set())
    expect(() => salvarVisitas(new Set(['im_a']))).not.toThrow()
  })

  it('JSON corrompido na chave degrada para conjunto vazio', () => {
    localStorage.setItem(CHAVE_VISITAS, '{nao-e-json')
    expect(lerVisitas()).toEqual(new Set())
  })
})
