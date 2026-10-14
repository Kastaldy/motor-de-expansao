import { describe, expect, it } from 'vitest'

import { janelaDoHexVisivel } from './janela-hex'

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
