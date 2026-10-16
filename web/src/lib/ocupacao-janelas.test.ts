import { describe, expect, it } from 'vitest'

import {
  FOLGA_TRILHO,
  assinarJanelas,
  deslocamentoDoTrilho,
  janelasAbertas,
  registrarJanela,
  removerJanela,
  type Retangulo,
} from './ocupacao-janelas'

const TELA = 1600
/** O trilho no canto inferior esquerdo, como medido no piloto (1600x900). */
const TRILHO: Retangulo = { esquerda: 76, topo: 520, largura: 300, altura: 300 }
/** A ficha nascendo à esquerda: x 16 no contêiner, 520 de largura, do cabeçalho ao stepper. */
const FICHA: Retangulo = { esquerda: 76, topo: 75, largura: 440, altura: 745 }

describe('deslocamentoDoTrilho', () => {
  it('sem janela, o trilho fica onde está', () => {
    expect(deslocamentoDoTrilho(TRILHO, [], TELA)).toBe(0)
  })

  it('a ficha à esquerda empurra o trilho para depois da borda direita dela', () => {
    const dx = deslocamentoDoTrilho(TRILHO, [FICHA], TELA)
    expect(TRILHO.esquerda + dx).toBe(FICHA.esquerda + FICHA.largura + FOLGA_TRILHO)
  })

  it('duas janelas em degrau empurram para depois da mais à direita', () => {
    const degrau: Retangulo = { ...FICHA, esquerda: FICHA.esquerda + 24, topo: FICHA.topo + 56 }
    const dx = deslocamentoDoTrilho(TRILHO, [degrau, FICHA], TELA)
    expect(TRILHO.esquerda + dx).toBe(degrau.esquerda + degrau.largura + FOLGA_TRILHO)
  })

  it('janela que não alcança a faixa do trilho na vertical não empurra (recolhida no alto)', () => {
    const recolhida: Retangulo = { ...FICHA, altura: 56 }
    expect(deslocamentoDoTrilho(TRILHO, [recolhida], TELA)).toBe(0)
  })

  it('janela à direita, longe do trilho, não empurra', () => {
    const direita: Retangulo = { ...FICHA, esquerda: 1100 }
    expect(deslocamentoDoTrilho(TRILHO, [direita], TELA)).toBe(0)
  })

  it('pula em cadeia: a primeira empurra o trilho para cima da segunda, que empurra de novo', () => {
    const segunda: Retangulo = { esquerda: 560, topo: 400, largura: 300, altura: 300 }
    const dx = deslocamentoDoTrilho(TRILHO, [FICHA, segunda], TELA)
    expect(TRILHO.esquerda + dx).toBe(segunda.esquerda + segunda.largura + FOLGA_TRILHO)
  })

  it('nunca empurra o trilho para fora da tela', () => {
    const larga: Retangulo = { ...FICHA, largura: 1500 }
    const dx = deslocamentoDoTrilho(TRILHO, [larga], TELA)
    expect(TRILHO.esquerda + dx + TRILHO.largura).toBeLessThanOrEqual(TELA)
  })

  it('janela sem tamanho (ainda medindo) é ignorada', () => {
    expect(deslocamentoDoTrilho(TRILHO, [{ ...FICHA, largura: 0 }], TELA)).toBe(0)
  })
})

describe('registro de janelas abertas', () => {
  it('registra, avisa, mantém a referência sem mudança e remove', () => {
    const id = Symbol('t')
    let avisos = 0
    const sair = assinarJanelas(() => avisos++)
    registrarJanela(id, FICHA)
    const antes = janelasAbertas()
    expect(antes).toContainEqual(FICHA)
    registrarJanela(id, { ...FICHA })
    expect(janelasAbertas()).toBe(antes)
    expect(avisos).toBe(1)
    removerJanela(id)
    expect(janelasAbertas()).not.toContainEqual(FICHA)
    expect(avisos).toBe(2)
    removerJanela(id)
    expect(avisos).toBe(2)
    sair()
  })
})
