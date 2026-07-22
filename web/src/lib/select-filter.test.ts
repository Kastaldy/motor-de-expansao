import { describe, expect, it } from 'vitest'
import { filtrarOpcoes, norm } from './select-filter'

describe('norm', () => {
  it('tira acento, caixa e espacos', () => {
    expect(norm('São Paulo')).toBe('sao paulo')
    expect(norm('  ÁÇÃÍ  ')).toBe('acai')
  })
})

const OPCOES = [
  { value: 'sp', label: 'São Paulo' },
  { value: 'rj', label: 'Rio de Janeiro' },
  { value: 'mg', label: 'Minas Gerais' },
]

describe('filtrarOpcoes', () => {
  it('filtra por substring insensivel a acento', () => {
    expect(filtrarOpcoes(OPCOES, 'sao')).toEqual([{ value: 'sp', label: 'São Paulo' }])
  })
  it('insensivel a caixa E acento na consulta', () => {
    expect(filtrarOpcoes(OPCOES, 'SÃO')).toEqual([{ value: 'sp', label: 'São Paulo' }])
  })
  it('casa substring no meio do rotulo', () => {
    expect(filtrarOpcoes(OPCOES, 'gerais')).toEqual([{ value: 'mg', label: 'Minas Gerais' }])
  })
  it('busca vazia devolve a MESMA lista (sem copia)', () => {
    expect(filtrarOpcoes(OPCOES, '')).toBe(OPCOES)
    expect(filtrarOpcoes(OPCOES, '   ')).toBe(OPCOES)
  })
  it('nada casa -> lista vazia', () => {
    expect(filtrarOpcoes(OPCOES, 'xyz')).toEqual([])
  })
  it('PRESERVA a ordem de entrada (nao reordena)', () => {
    const desordenado = [
      { value: 'ba', label: 'Bahia' },
      { value: 'am', label: 'Amazonas' },
      { value: 'ac', label: 'Acre' },
    ]
    expect(filtrarOpcoes(desordenado, 'a').map((o) => o.value)).toEqual(['ba', 'am', 'ac'])
  })
})
