import { describe, expect, it } from 'vitest'

import {
  CHAVE_TEMA,
  TEMA_PADRAO,
  type DepositoDeTema,
  ehTema,
  gravarTema,
  lerTema,
  outroTema,
} from './tema'

/** Depósito de mentira: um objeto, e opcionalmente um que estoura como o de aba anônima. */
function deposito(inicial: Record<string, string> = {}, explode = false): DepositoDeTema {
  return {
    getItem: (c) => {
      if (explode) throw new DOMException('bloqueado', 'SecurityError')
      return inicial[c] ?? null
    },
    setItem: (c, v) => {
      if (explode) throw new DOMException('bloqueado', 'SecurityError')
      inicial[c] = v
    },
  }
}

describe('tema', () => {
  it('sem escolha guardada, entra no tema do produto', () => {
    expect(lerTema(deposito())).toBe(TEMA_PADRAO)
    expect(TEMA_PADRAO).toBe('escuro')
  })

  it('lê de volta o que gravou', () => {
    const d = deposito()
    gravarTema('claro', d)
    expect(lerTema(d)).toBe('claro')
    gravarTema('escuro', d)
    expect(lerTema(d)).toBe('escuro')
  })

  it('valor estragado cai no padrão, não vira data-tema inválido', () => {
    // `data-tema="dark"` não casa com nenhum seletor: a tela ficaria escura e o botão
    // passaria a alternar a partir de um estado que ninguém escolheu.
    expect(lerTema(deposito({ [CHAVE_TEMA]: 'dark' }))).toBe(TEMA_PADRAO)
    expect(lerTema(deposito({ [CHAVE_TEMA]: '' }))).toBe(TEMA_PADRAO)
  })

  it('depósito ausente ou bloqueado não derruba a aba', () => {
    // Em janela anônima com cookies de terceiros bloqueados, TOCAR no localStorage já
    // levanta SecurityError. Perder a preferência é aceitável; perder a tela não é.
    expect(lerTema(null)).toBe(TEMA_PADRAO)
    expect(lerTema(undefined)).toBe(TEMA_PADRAO)
    expect(lerTema(deposito({}, true))).toBe(TEMA_PADRAO)
    expect(() => gravarTema('claro', deposito({}, true))).not.toThrow()
    expect(() => gravarTema('claro', null)).not.toThrow()
  })

  it('outroTema é involução: ida e volta devolve o mesmo', () => {
    expect(outroTema('escuro')).toBe('claro')
    expect(outroTema('claro')).toBe('escuro')
    expect(outroTema(outroTema('claro'))).toBe('claro')
  })

  it('ehTema só reconhece os dois nomes do projeto', () => {
    expect(ehTema('claro')).toBe(true)
    expect(ehTema('escuro')).toBe(true)
    expect(ehTema('light')).toBe(false)
    expect(ehTema(null)).toBe(false)
    expect(ehTema(undefined)).toBe(false)
  })
})
