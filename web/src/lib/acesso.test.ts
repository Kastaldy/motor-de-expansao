import { describe, expect, it } from 'vitest'

import {
  abasDoPayload,
  modosLiberados,
  telaInicial,
  telaLiberada,
  TODAS_AS_ABAS,
  type Aba,
} from './acesso'
import { MODOS } from './inicio'

const setDe = (...abas: Aba[]) => new Set<Aba>(abas)

describe('abasDoPayload', () => {
  it('aceita o payload do /api/me e devolve o conjunto', () => {
    const s = abasDoPayload({ usuario: 'ana', abas: ['mapa', 'executiva'] })
    expect(s).not.toBeNull()
    expect([...(s as Set<Aba>)].sort()).toEqual(['executiva', 'mapa'])
  })

  it('descarta aba desconhecida em vez de guardar lixo', () => {
    const s = abasDoPayload({ abas: ['mapa', 'dominio', 42] })
    expect([...(s as Set<Aba>)]).toEqual(['mapa'])
  })

  it('payload inesperado vira null (fail-open), nunca conjunto vazio', () => {
    // Conjunto vazio trancaria o app; null significa "sem controle".
    expect(abasDoPayload(null)).toBeNull()
    expect(abasDoPayload('erro')).toBeNull()
    expect(abasDoPayload({})).toBeNull()
    expect(abasDoPayload({ abas: 'mapa' })).toBeNull()
  })

  it('lista vazia vira conjunto vazio valido — usuario sem aba nenhuma', () => {
    const s = abasDoPayload({ abas: [] })
    expect(s).not.toBeNull()
    expect((s as Set<Aba>).size).toBe(0)
  })
})

describe('telaLiberada', () => {
  it('sem controle (null) tudo passa', () => {
    for (const tela of ['inicio', 'ponto', 'mapa', 'oportunidades', 'executiva', 'viabilidade'] as const) {
      expect(telaLiberada(tela, null)).toBe(true)
    }
  })

  it('o inicio esta sempre alcancavel — a porta, nao uma aba', () => {
    expect(telaLiberada('inicio', setDe())).toBe(true)
  })

  it('o modo de ponto pertence a aba mapa', () => {
    expect(telaLiberada('ponto', setDe('mapa'))).toBe(true)
    expect(telaLiberada('ponto', setDe('executiva', 'viabilidade'))).toBe(false)
  })

  it('cada tela exige a sua aba', () => {
    const so = (a: Aba) => setDe(a)
    expect(telaLiberada('executiva', so('executiva'))).toBe(true)
    expect(telaLiberada('executiva', so('mapa'))).toBe(false)
    expect(telaLiberada('viabilidade', so('viabilidade'))).toBe(true)
    expect(telaLiberada('oportunidades', so('oportunidades'))).toBe(true)
    expect(telaLiberada('mapa', so('oportunidades'))).toBe(false)
  })
})

describe('modosLiberados', () => {
  it('sem controle devolve os 3 cards', () => {
    expect(modosLiberados(null)).toEqual(MODOS)
  })

  it('mapa + oportunidades + viabilidade = os 3 cards (perfil do grupo 2)', () => {
    expect(modosLiberados(setDe('mapa', 'oportunidades', 'viabilidade'))).toHaveLength(3)
  })

  it('so executiva = nenhum card de analise', () => {
    expect(modosLiberados(setDe('executiva'))).toHaveLength(0)
  })

  it('so oportunidades = so o card da fila', () => {
    const modos = modosLiberados(setDe('oportunidades'))
    expect(modos.map((m) => m.id)).toEqual(['oportunidades'])
  })
})

describe('telaInicial', () => {
  it('sem controle pousa no inicio', () => {
    expect(telaInicial(null)).toBe('inicio')
  })

  it('quem tem card no inicio pousa no inicio', () => {
    expect(telaInicial(setDe('mapa'))).toBe('inicio')
    expect(telaInicial(new Set(TODAS_AS_ABAS))).toBe('inicio')
  })

  it('so executiva pousa direto na executiva', () => {
    expect(telaInicial(setDe('executiva'))).toBe('executiva')
  })

  it('so viabilidade pousa na viabilidade', () => {
    expect(telaInicial(setDe('viabilidade'))).toBe('viabilidade')
  })

  it('sem aba nenhuma fica no inicio (que explica a situacao)', () => {
    expect(telaInicial(setDe())).toBe('inicio')
  })
})
