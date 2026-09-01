import { describe, expect, it } from 'vitest'

import { nomeDasUnidades, rodapeDaBase } from './rodape-base'

const BR = ['SP', 'RJ', 'MG']
const AR = ['BS', 'CA', 'MZ', 'TU']

describe('rodapeDaBase', () => {
  it('credita o IBGE e a rede Ultra na base brasileira', () => {
    expect(rodapeDaBase(BR)).toBe(
      '3 estados · Censo 2022 (IBGE) + rede Ultra e concorrentes mapeados · camada visual read-only',
    )
  })

  it('credita o INDEC e NAO promete rede Ultra na base argentina', () => {
    const t = rodapeDaBase(AR)
    expect(t).toBe(
      '4 províncias · Censo 2022 (INDEC) + concorrentes mapeados · camada visual read-only',
    )
    // O projeto argentino e' greenfield: nao ha uma unidade Ultra no pais.
    expect(t).not.toContain('Ultra')
    expect(t).not.toContain('IBGE')
    expect(t).not.toContain('estados')
  })

  it('a contagem vem da BASE, nunca de uma constante', () => {
    expect(rodapeDaBase(['SP'])).toContain('1 estado ·')
    expect(rodapeDaBase(Array.from({ length: 27 }, (_, i) => ['SP', 'RJ', 'MG', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MT', 'MS', 'PA', 'PB', 'PR', 'PE', 'PI', 'RN', 'RS', 'RO', 'RR', 'SC', 'SE', 'TO', 'AC', 'AL', 'AP', 'AM'][i]))).toContain('27 estados')
  })

  it('sem base nao inventa frase — quem chama nao desenha nada', () => {
    expect(rodapeDaBase([])).toBeNull()
    expect(rodapeDaBase(null)).toBeNull()
  })

  it('base misturada conta as unidades e cala sobre censo e pontos', () => {
    const t = rodapeDaBase(['SP', 'MZ'])
    expect(t).toBe('2 unidades federativas · camada visual read-only')
    expect(t).not.toContain('Censo')
  })
})

describe('nomeDasUnidades', () => {
  it('concorda em genero e numero', () => {
    expect(nomeDasUnidades(BR)).toBe('os 3 estados')
    expect(nomeDasUnidades(AR)).toBe('as 4 províncias')
    expect(nomeDasUnidades(['SP'])).toBe('o estado')
    expect(nomeDasUnidades(['MZ'])).toBe('a província')
  })

  it('degrada para termo neutro quando nao da' + ' para afirmar', () => {
    expect(nomeDasUnidades([])).toBe('as unidades federativas')
    expect(nomeDasUnidades(['SP', 'MZ'])).toBe('as unidades federativas')
  })
})
