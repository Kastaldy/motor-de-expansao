import { describe, expect, it } from 'vitest'

import { degrauSobreFichaDePonto, janelaDoHexVisivel, pontoSeleciona } from './janela-hex'

const HEX = '87a8100c5ffffff'
const OUTRO = '87a8100c4ffffff'

describe('janelaDoHexVisivel', () => {
  it('sem hexágono selecionado, não abre', () => {
    expect(
      janelaDoHexVisivel({ selecionado: null, hexDaBusca: null, selecaoDaBusca: false, modoCenario: false }),
    ).toBe(false)
  })

  it('clique direto num hexágono abre a ficha dele', () => {
    expect(
      janelaDoHexVisivel({ selecionado: HEX, hexDaBusca: null, selecaoDaBusca: false, modoCenario: false }),
    ).toBe(true)
  })

  it('seleção vinda da BUSCA não abre: vira ficha de ponto', () => {
    expect(
      janelaDoHexVisivel({ selecionado: HEX, hexDaBusca: HEX, selecaoDaBusca: true, modoCenario: false }),
    ).toBe(false)
  })

  it('clique no MESMO hexágono do ponto buscado abre (o flag distingue, não o id)', () => {
    expect(
      janelaDoHexVisivel({ selecionado: HEX, hexDaBusca: HEX, selecaoDaBusca: false, modoCenario: false }),
    ).toBe(true)
  })

  it('clique em outro hexágono depois da busca abre a ficha dele', () => {
    expect(
      janelaDoHexVisivel({ selecionado: OUTRO, hexDaBusca: HEX, selecaoDaBusca: false, modoCenario: false }),
    ).toBe(true)
    // Mesmo com o flag esquecido ligado, o hex selecionado não é o da busca.
    expect(
      janelaDoHexVisivel({ selecionado: OUTRO, hexDaBusca: HEX, selecaoDaBusca: true, modoCenario: false }),
    ).toBe(true)
  })

  it('nunca abre em modoCenario ("Comparar hexes")', () => {
    for (const selecaoDaBusca of [true, false]) {
      expect(
        janelaDoHexVisivel({ selecionado: HEX, hexDaBusca: null, selecaoDaBusca, modoCenario: true }),
      ).toBe(false)
    }
  })
})

describe('degrauSobreFichaDePonto', () => {
  it('com pontos na lista, a ficha do hexágono e o comparativo nascem em degrau', () => {
    // A ficha de ponto ocupa a esquerda; mandar a do hexágono para a direita a punha em
    // cima da do imóvel e da unidade.
    expect(degrauSobreFichaDePonto(1)).toBe(1)
    expect(degrauSobreFichaDePonto(5)).toBe(1)
  })

  it('sem pontos, a posição de sempre', () => {
    expect(degrauSobreFichaDePonto(0)).toBe(0)
  })
})

describe('pontoSeleciona', () => {
  it('ponto NOVO depois da montagem sempre seleciona o hexágono dele', () => {
    expect(pontoSeleciona({ pinDaMontagem: false, selecaoRestaurada: OUTRO, hexDoPonto: HEX })).toBe(true)
  })

  it('na volta da Viabilidade, a seleção restaurada de OUTRO hexágono fica (a ficha dele volta)', () => {
    expect(pontoSeleciona({ pinDaMontagem: true, selecaoRestaurada: OUTRO, hexDoPonto: HEX })).toBe(false)
  })

  it('na volta, se a seleção restaurada era a do próprio ponto (ou nenhuma), religa', () => {
    expect(pontoSeleciona({ pinDaMontagem: true, selecaoRestaurada: HEX, hexDoPonto: HEX })).toBe(true)
    expect(pontoSeleciona({ pinDaMontagem: true, selecaoRestaurada: null, hexDoPonto: HEX })).toBe(true)
  })
})
