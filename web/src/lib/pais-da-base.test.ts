import { describe, expect, it } from 'vitest'

import { paisDaBase, UFS_BRASIL } from './pais-da-base'

/* As 24 províncias que o exportador argentino de fato escreve (rodada de 2026-08-26).
   Estão aqui como AMOSTRA REAL, não como contrato: a função não conhece esta lista, e é
   justamente isso que o teste precisa provar. */
const PROVINCIAS_AR = [
  'BS', 'CA', 'CB', 'CH', 'CR', 'CT', 'ER', 'FO', 'JU', 'LP', 'LR', 'MZ',
  'MI', 'NQ', 'RG', 'SA', 'SJ', 'SL', 'CZ', 'SF', 'SG', 'TI', 'TU', 'CD',
]

describe('paisDaBase', () => {
  it('reconhece a base brasileira', () => {
    expect(paisDaBase(['SP', 'RJ', 'MG'])).toBe('BR')
    expect(paisDaBase([...UFS_BRASIL])).toBe('BR')
  })

  it('reconhece a base argentina sem conhecer as províncias', () => {
    expect(paisDaBase(PROVINCIAS_AR)).toBe('AR')
  })

  it('não afirma nada sem lista — o Dock fica sem carimbo em vez de chutar', () => {
    expect(paisDaBase([])).toBeNull()
    expect(paisDaBase(null)).toBeNull()
    expect(paisDaBase(undefined)).toBeNull()
  })

  it('mistura dos dois universos devolve null, e não a maioria', () => {
    // Base montada errada. Carimbar "Brasil" aqui porque 2 de 3 são UFs seria afirmar
    // sobre um estado que ninguém projetou.
    expect(paisDaBase(['SP', 'RJ', 'MZ'])).toBeNull()
    expect(paisDaBase(['MZ', 'TU', 'SP'])).toBeNull()
  })

  it('tolera espaço e caixa — o código vem do nome da pasta uf=XX', () => {
    expect(paisDaBase([' sp ', 'rj'])).toBe('BR')
    expect(paisDaBase(['mz', 'tu'])).toBe('AR')
  })

  it('entrada corrompida não vira bandeira', () => {
    expect(paisDaBase(['SP', null as unknown as string])).toBeNull()
  })

  it('REGRESSÃO: nenhuma província argentina pode ser UF brasileira', () => {
    // É a invariante que torna a dedução por disjunção válida, e ela é garantida do outro
    // lado — `exportar_piloto_rep.py` aborta se um código colidir. Se um dia entrar uma
    // província nova que colida, este teste cai antes de a bandeira mentir na tela.
    for (const p of PROVINCIAS_AR) expect(UFS_BRASIL.has(p)).toBe(false)
  })
})
