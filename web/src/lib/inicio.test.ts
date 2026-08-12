import { describe, expect, it } from 'vitest'

import {
  MODOS,
  PASSO_MAX,
  PASSO_MIN,
  modoPorId,
  passoAlvoDoModo,
  type ModoInicio,
} from './inicio'

describe('MODOS', () => {
  it('declara exatamente os 3 modos pedidos, na ordem do menu', () => {
    expect(MODOS.map((m) => m.id)).toEqual(['ponto', 'regiao', 'oportunidades'])
  })

  it('nao repete id', () => {
    expect(new Set(MODOS.map((m) => m.id)).size).toBe(MODOS.length)
  })

  it('so aponta para telas que existem hoje', () => {
    for (const m of MODOS) {
      expect(['mapa', 'ponto', 'oportunidades']).toContain(m.destino)
    }
  })

  it('cada modo abre a SUA tela dedicada', () => {
    // As etapas 1-2 mandavam ponto para a Viabilidade e oportunidades para o mapa,
    // porque as telas proprias ainda nao existiam.
    expect(modoPorId('ponto')?.destino).toBe('ponto')
    expect(modoPorId('oportunidades')?.destino).toBe('oportunidades')
    // Regiao continua no mapa DE PROPOSITO: o funil e' a tela dele.
    expect(modoPorId('regiao')?.destino).toBe('mapa')
  })

  it('todo card tem texto de usuario preenchido', () => {
    for (const m of MODOS) {
      expect(m.eyebrow.trim()).not.toBe('')
      expect(m.titulo.trim()).not.toBe('')
      expect(m.resumo.trim()).not.toBe('')
      expect(m.chamada.trim()).not.toBe('')
      expect(m.bullets.length).toBeGreaterThan(0)
      for (const b of m.bullets) expect(b.trim()).not.toBe('')
    }
  })

  it('mantem os identificadores SEM acento (regra do CLAUDE.md §2)', () => {
    // O texto de usuario e' acentuado de proposito; o `id` nunca.
    for (const m of MODOS) expect(m.id).toMatch(/^[a-z]+$/)
  })

  it('e congelado: o menu nao pode ser mutado em runtime', () => {
    expect(Object.isFrozen(MODOS)).toBe(true)
    for (const m of MODOS) expect(Object.isFrozen(m)).toBe(true)
  })
})

describe('modoPorId', () => {
  it('acha cada modo declarado', () => {
    for (const m of MODOS) expect(modoPorId(m.id)?.titulo).toBe(m.titulo)
  })

  it('devolve null para id desconhecido em vez de estourar', () => {
    expect(modoPorId('inexistente')).toBeNull()
    expect(modoPorId('')).toBeNull()
  })
})

describe('passoAlvoDoModo', () => {
  it('nenhum modo pede passo do mapa — todos tem tela propria ou o funil inteiro', () => {
    // `oportunidades` pedia o passo 5 enquanto reusava o mapa; com tela propria a fila
    // deixou de ser um passo do funil.
    for (const m of MODOS) expect(passoAlvoDoModo(m.id)).toBeNull()
  })

  it('o guarda de faixa continua valendo para quem voltar a usar passo', () => {
    // Protege o contrato: passo fora de 1..5 nunca deve chegar ao backend.
    expect(PASSO_MIN).toBe(1)
    expect(PASSO_MAX).toBe(5)
  })

  it('id desconhecido nao vira passo', () => {
    expect(passoAlvoDoModo('nada' as ModoInicio)).toBeNull()
  })
})
