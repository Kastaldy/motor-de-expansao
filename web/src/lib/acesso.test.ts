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
  it('sem controle (null) as telas de trabalho passam', () => {
    for (const tela of ['inicio', 'ponto', 'mapa', 'oportunidades', 'executiva', 'viabilidade'] as const) {
      expect(telaLiberada(tela, null)).toBe(true)
    }
  })

  it('a aba acessos e deny-by-default: fail-open NAO a concede (emenda DEC-027)', () => {
    // /api/me fora do ar libera o trabalho, nunca o painel de atividade do time.
    expect(telaLiberada('acessos', null)).toBe(false)
    expect(telaLiberada('acessos', setDe('mapa', 'executiva', 'viabilidade'))).toBe(false)
    expect(telaLiberada('acessos', setDe('acessos'))).toBe(true)
  })

  it('o /api/me pode conceder acessos (vem da allowlist, nao do JSON de abas)', () => {
    const s = abasDoPayload({ usuario: 'felipe', abas: ['mapa', 'acessos'] })
    expect((s as Set<Aba>).has('acessos')).toBe(true)
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

describe('camada imobiliaria', () => {
  it('mapa sozinho NAO abre a tela dedicada (so os pins dentro do Mapa Territorial)', () => {
    // A camada de imoveis DENTRO do mapa e da aba `mapa`; a tela dedicada, nao.
    expect(telaLiberada('oportunidades-imob', setDe('mapa'))).toBe(false)
  })

  it('a aba imobiliaria abre a tela dedicada', () => {
    expect(telaLiberada('oportunidades-imob', setDe('imobiliaria'))).toBe(true)
  })

  it('oportunidades NAO abre mais a tela — regressao do acoplamento antigo', () => {
    // Ate 2026-08-24 a tela reusava o gate de `oportunidades`, e era exatamente isso
    // que impedia restringir os imoveis sem tirar o funil de expansao de quem o usa.
    expect(telaLiberada('oportunidades-imob', setDe('oportunidades'))).toBe(false)
  })

  it('fail-open NAO concede a tela, mas o mapa (com os pins) continua', () => {
    // /api/me fora do ar nao pode escancarar a camada restrita; o trabalho segue.
    expect(telaLiberada('oportunidades-imob', null)).toBe(false)
    expect(telaLiberada('mapa', null)).toBe(true)
  })

  it('`imobiliaria` sobrevive ao abasDoPayload (nao e filtrada como desconhecida)', () => {
    const s = abasDoPayload({ usuario: 'ana', abas: ['mapa', 'imobiliaria'] })
    expect((s as Set<Aba>).has('imobiliaria')).toBe(true)
    expect(telaLiberada('oportunidades-imob', s)).toBe(true)
  })
})
