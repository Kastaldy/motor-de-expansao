import { describe, expect, it } from 'vitest'

import {
  CHAVE_TEMA,
  CHAVE_TEMA_LEGADA,
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

  it('quem escolheu o claro na Executiva não volta ao escuro quando a chave muda de nome', () => {
    // A preferência morava em `motor.exec.tema` enquanto o tema era só daquela aba. Sem a
    // leitura da chave antiga, o dia do deploy leria como "o botão parou de funcionar".
    expect(lerTema(deposito({ [CHAVE_TEMA_LEGADA]: 'claro' }))).toBe('claro')
    expect(lerTema(deposito({ [CHAVE_TEMA_LEGADA]: 'escuro' }))).toBe('escuro')
  })

  it('a chave nova VENCE a antiga, e é a única em que se grava', () => {
    // Senão a escolha migrada seria imutável: gravar 'escuro' na chave nova não teria
    // efeito nenhum enquanto a antiga continuasse dizendo 'claro'.
    const d = deposito({ [CHAVE_TEMA_LEGADA]: 'claro' })
    gravarTema('escuro', d)
    expect(lerTema(d)).toBe('escuro')
  })

  it('lixo na chave antiga também cai no padrão', () => {
    expect(lerTema(deposito({ [CHAVE_TEMA_LEGADA]: 'light' }))).toBe(TEMA_PADRAO)
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
