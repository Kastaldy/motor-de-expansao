import { describe, expect, it } from 'vitest'

import { alternarCalor, alternarCoresHex, legendaDoCalor, SEM_LEITURA_CALOR } from './camadas-calor'
import { DENSIDADE_BANDS, RENDA_DOMICILIAR_SETOR_BANDS } from './colors'

describe('alternarCalor', () => {
  it('ligar um calor desliga as cores dos hexágonos', () => {
    expect(alternarCalor({ calor: null, coresHex: true }, 'densidade')).toEqual({
      calor: 'densidade',
      coresHex: false,
    })
    expect(alternarCalor({ calor: null, coresHex: true }, 'renda')).toEqual({
      calor: 'renda',
      coresHex: false,
    })
  })

  it('desligar o calor NÃO religa as cores sozinho', () => {
    expect(alternarCalor({ calor: 'densidade', coresHex: false }, 'densidade')).toEqual({
      calor: null,
      coresHex: false,
    })
  })

  it('trocar de modo é ligar outro calor: as duas chaves são exclusivas e as cores saem', () => {
    expect(alternarCalor({ calor: 'densidade', coresHex: true }, 'renda')).toEqual({
      calor: 'renda',
      coresHex: false,
    })
  })
})

describe('alternarCoresHex', () => {
  it('ligar as cores dos hexágonos desliga o calor', () => {
    expect(alternarCoresHex({ calor: 'densidade', coresHex: false })).toEqual({
      calor: null,
      coresHex: true,
    })
    expect(alternarCoresHex({ calor: 'renda', coresHex: false })).toEqual({
      calor: null,
      coresHex: true,
    })
  })

  it('desligar as cores não mexe no calor', () => {
    expect(alternarCoresHex({ calor: null, coresHex: true })).toEqual({
      calor: null,
      coresHex: false,
    })
  })

  it('as duas coropletas nunca ficam acesas juntas, em nenhuma sequência de cliques', () => {
    const cliques = [
      (e: Parameters<typeof alternarCoresHex>[0]) => alternarCoresHex(e),
      (e: Parameters<typeof alternarCoresHex>[0]) => alternarCalor(e, 'densidade'),
      (e: Parameters<typeof alternarCoresHex>[0]) => alternarCalor(e, 'renda'),
    ]
    let estados = [{ calor: null, coresHex: true } as Parameters<typeof alternarCoresHex>[0]]
    for (let passo = 0; passo < 4; passo++) {
      estados = estados.flatMap((e) => cliques.map((c) => c(e)))
      for (const e of estados) expect(e.coresHex && e.calor !== null).toBe(false)
    }
  })
})

describe('legendaDoCalor', () => {
  it('uma faixa por corte da régua, com os mesmos rótulos e o alfa do mapa', () => {
    const d = legendaDoCalor('densidade')
    expect(d.titulo).toBe('Densidade demográfica')
    expect(d.unidade).toBe('hab/km²')
    expect(d.faixas.map((f) => f.rotulo)).toEqual(DENSIDADE_BANDS.map(([, r]) => r))
    expect(d.faixas[0].cor).toBe('rgba(254,229,217,0.59)')

    const r = legendaDoCalor('renda')
    expect(r.titulo).toBe('Renda domiciliar')
    expect(r.unidade).toBe('por domicílio/mês')
    expect(r.faixas.map((f) => f.rotulo)).toEqual(RENDA_DOMICILIAR_SETOR_BANDS.map(([, x]) => x))
    expect(r.faixas.at(-1)?.cor).toBe('rgba(0,204,0,0.59)')
  })

  it('o cinza de "sem dado" é o mesmo do HexMap', () => {
    expect(SEM_LEITURA_CALOR.cor).toBe('rgba(120,120,140,.24)')
  })
})
